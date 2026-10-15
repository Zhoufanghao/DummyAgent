"""Real OS boundary checks, using disposable sentinel files (never real keys)."""

from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

import tools as sandbox


class CaptureInterruption(unittest.TestCase):
    def test_ctrl_c_stops_and_reaps_child_before_propagating(self):
        processes = []
        original_popen = sandbox.subprocess.Popen

        def start(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process

        with tempfile.TemporaryDirectory(prefix="capture-interrupt-") as folder:
            try:
                with patch.object(sandbox.subprocess, "Popen", side_effect=start), \
                        patch.object(sandbox.selectors, "DefaultSelector") as factory, \
                        patch.object(sandbox.os, "killpg", wraps=sandbox.os.killpg) as kill:
                    selector = factory.return_value.__enter__.return_value
                    selector.get_map.return_value = {1: object()}
                    selector.select.side_effect = KeyboardInterrupt()
                    with self.assertRaises(KeyboardInterrupt):
                        sandbox._capture(
                            [sys.executable, "-c", "import time; time.sleep(30)"],
                            Path(folder), 8)
                    self.assertEqual(len(processes), 1)
                    process = processes[0]
                    kill.assert_called_once_with(process.pid, signal.SIGKILL)
                    self.assertEqual(process.returncode, -signal.SIGKILL)
                    self.assertTrue(process.stdout.closed)
            finally:
                # Also clean up if a regression makes one of the assertions fail.
                for process in processes:
                    if process.poll() is None:
                        sandbox.os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    process.stdout.close()


class SandboxValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-lab-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name).resolve()
        (self.workspace / "data").mkdir()
        (self.workspace / "data/temperature.csv").write_text(
            "temperature\n20\n22\n24\n", encoding="utf-8")

    def test_missing_backend_fails_closed(self):
        with patch("tools.backend_status", return_value="unavailable: test"):
            with patch("tools.subprocess.Popen") as popen:
                result = sandbox.run_bash("printf never-executed", self.workspace)
        self.assertEqual(result["error"], "sandbox_unavailable")
        popen.assert_not_called()

    def test_repository_cannot_be_workspace(self):
        self.assertEqual(sandbox.run_bash("printf no", Path(__file__).parent.parent)["error"],
                         "sandbox_rejected")

    def test_dangerous_shell_operation_rejected(self):
        self.assertEqual(sandbox.run_bash("rm -rf data", self.workspace)["error"],
                         "sandbox_rejected")

    def test_symbolic_links_rejected(self):
        (self.workspace / "report.md").symlink_to("/etc/passwd")
        self.assertEqual(sandbox.run_bash("printf no", self.workspace)["error"],
                         "sandbox_rejected")

    def test_existing_hardlinks_rejected(self):
        (self.workspace / "report.md").hardlink_to(self.workspace / "data/temperature.csv")
        self.assertEqual(sandbox.run_bash("printf no", self.workspace)["error"],
                         "sandbox_rejected")


class SandboxIntegration(SandboxValidation):
    """Skipped only when a real backend is unavailable, with the reason printed."""

    def setUp(self):
        super().setUp()
        status = sandbox.backend_status()
        if status.startswith("unavailable"):
            self.skipTest(status)

    def python(self, source, **kwargs):
        return sandbox.run_bash("python3 - <<'PY'\n" + source + "\nPY",
                                self.workspace, **kwargs)

    def test_csv_computation_and_report(self):
        result = self.python("""import csv, statistics, json
from pathlib import Path
with open('data/temperature.csv') as f:
    values = [float(row['temperature']) for row in csv.DictReader(f)]
stats = dict(mean=statistics.mean(values), max=max(values), min=min(values))
Path('result.json').write_text(json.dumps(stats))
Path('report.md').write_text('# Temperature report\\n' + str(stats))
print(json.dumps(stats))""")
        self.assertEqual(result["exit_code"], 0, result)
        self.assertIn('"mean": 22.0', result["output"])
        self.assertIn("Temperature report", (self.workspace / "report.md").read_text())

    def test_host_secret_sentinel_unreadable(self):
        with tempfile.TemporaryDirectory(prefix="host-sentinel-") as folder:
            sentinel = Path(folder).resolve() / "secret.txt"
            sentinel.write_text("PRIVATE-SENTINEL-NEVER-PRINT")
            result = self.python(f"from pathlib import Path\nprint(Path({str(sentinel)!r}).read_text())")
            self.assertNotEqual(result["exit_code"], 0, result)
            self.assertNotIn("PRIVATE-SENTINEL-NEVER-PRINT", result["output"])

    def test_macos_data_volume_alias_does_not_bypass_policy(self):
        with tempfile.TemporaryDirectory(prefix="host-sentinel-") as folder:
            sentinel = Path(folder).resolve() / "secret.txt"
            sentinel.write_text("PRIVATE-ALIAS-SENTINEL")
            alias = Path("/System/Volumes/Data" + str(sentinel))
            if not alias.exists():
                self.skipTest("macOS Data volume alias is not present")
            result = self.python(f"from pathlib import Path\nprint(Path({str(alias)!r}).read_text())")
            self.assertNotEqual(result["exit_code"], 0, result)
            self.assertNotIn("PRIVATE-ALIAS-SENTINEL", result["output"])

    def test_host_path_unwritable(self):
        with tempfile.TemporaryDirectory(prefix="host-sentinel-") as folder:
            target = Path(folder).resolve() / "must-not-exist.txt"
            result = self.python(f"from pathlib import Path\nPath({str(target)!r}).write_text('oops')")
            self.assertNotEqual(result["exit_code"], 0, result)
            self.assertFalse(target.exists())

    def test_host_hardlink_cannot_alias_writable_output(self):
        with tempfile.TemporaryDirectory(prefix="host-sentinel-") as folder:
            sentinel = Path(folder).resolve() / "host.txt"
            sentinel.write_text("must-stay-unchanged")
            result = self.python(f"""import os
from pathlib import Path
os.link({str(sentinel)!r}, 'report.md')
Path('report.md').write_text('oops')""")
            self.assertNotEqual(result.get("exit_code"), 0, result)
            self.assertEqual(sentinel.read_text(), "must-stay-unchanged")

    def test_input_hardlink_cannot_bypass_read_only(self):
        original = (self.workspace / "data/temperature.csv").read_bytes()
        result = self.python("""import os
from pathlib import Path
os.link('data/temperature.csv', 'report.md')
Path('report.md').write_text('oops')""")
        self.assertNotEqual(result.get("exit_code"), 0, result)
        self.assertEqual((self.workspace / "data/temperature.csv").read_bytes(), original)

    def test_data_read_only(self):
        original = (self.workspace / "data/temperature.csv").read_bytes()
        result = self.python("from pathlib import Path\nPath('data/temperature.csv').write_text('oops')")
        self.assertNotEqual(result["exit_code"], 0, result)
        self.assertEqual((self.workspace / "data/temperature.csv").read_bytes(), original)

    def test_unlisted_output_blocked(self):
        result = self.python("from pathlib import Path\nPath('other.txt').write_text('oops')")
        self.assertNotEqual(result["exit_code"], 0, result)
        self.assertFalse((self.workspace / "other.txt").exists())

    def test_api_environment_not_inherited(self):
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "DUMMY-TEST-SECRET"}):
            result = self.python("import os\nprint(os.environ.get('DEEPSEEK_API_KEY', 'absent'))")
        self.assertEqual(result["exit_code"], 0, result)
        self.assertIn("absent", result["output"])
        self.assertNotIn("DUMMY-TEST-SECRET", result["output"])

    def test_network_blocked(self):
        result = self.python("import socket\nsocket.create_connection(('1.1.1.1', 443), timeout=1)")
        self.assertNotEqual(result["exit_code"], 0, result)

    def test_child_process_blocked(self):
        result = self.python("import os\nos.fork()")
        self.assertNotEqual(result["exit_code"], 0, result)

    def test_timeout(self):
        result = self.python("import time\ntime.sleep(10)", timeout=0.25)
        self.assertEqual(result.get("error"), "timeout", result)

    def test_output_cap(self):
        result = self.python("print('x' * 100000)")
        self.assertEqual(result.get("error"), "output_limit", result)
        self.assertLessEqual(len(result["output"].encode()), sandbox.MAX_OUTPUT_BYTES)

    def test_file_size_cap(self):
        result = self.python("from pathlib import Path\nPath('report.md').write_bytes(b'x' * 300000)")
        self.assertNotEqual(result["exit_code"], 0, result)
        self.assertLessEqual((self.workspace / "report.md").stat().st_size, sandbox.MAX_FILE_BYTES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
