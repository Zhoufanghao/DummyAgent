"""教师程序录制回归；只运行本地fixture脚本，不请求API。"""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import preflight
import verify_live


class RecordingTests(unittest.TestCase):
    def fixture_repo(self):
        temporary = tempfile.TemporaryDirectory(prefix="program-recording-unit-fixture-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        shutil.copytree(verify_live.ROOT / "data", root / "data")
        return root

    def run_fixture(self, root, stage="v0"):
        with contextlib.redirect_stdout(io.StringIO()):
            return verify_live.verify_stage(root, stage)

    def test_real_subprocess_records_exact_combined_output_and_eof_without_git(self):
        root = self.fixture_repo()
        source = ("# explicit local unit fixture; no model/API\n"
                  "import sys\nfrom types import SimpleNamespace as NS\n"
                  "client = NS(completions=NS(create=lambda **kwargs: None))\n"
                  "client.completions.create(model='unit-fixture-model')\n"
                  "questions = list(sys.stdin)\n"
                  "print('fixture stdout', flush=True)\n"
                  "print('fixture stderr', file=sys.stderr, flush=True)\n"
                  "print('questions:', len(questions))\n")
        (root / "agent_v0.py").write_text(source)
        recording = self.run_fixture(root)
        self.assertEqual(recording["transcript"], "fixture stdout\nfixture stderr\nquestions: 2\n")
        self.assertEqual(recording["kind"], "live-program-recording")
        self.assertEqual(recording["source_file"], "agent_v0.py")
        self.assertEqual(recording["source_sha256"], verify_live.file_sha256(root / "agent_v0.py"))
        self.assertEqual(recording["model_requested"], "unit-fixture-model")
        self.assertFalse((root / ".git").exists())
        self.assertNotIn("events", recording)
        self.assertNotIn("source_commit", recording)
        self.assertNotIn("runtime_sha256", recording)

    def test_inline_requested_model_is_consistent_and_ignores_environment_override(self):
        source = ("client.completions.create(model='deepseek-flash')\n"
                  "client.chat.completions.create(model='deepseek-flash')\n")
        with patch.dict(os.environ, {"DEEPSEEK_MODEL": "unit-configured-model"}):
            self.assertEqual(verify_live.requested_model(source), "deepseek-flash")

    def test_unknown_dynamic_and_conflicting_requested_models_stay_unknown(self):
        sources = ("print('unit fixture')\n",
                   "client.completions.create(model=selected_model)\n",
                   "client.completions.create(**request)\n",
                   "client.completions.create(model=123)\n",
                   "client.completions.create(model='deepseek-flash')\n"
                   "client.chat.completions.create(model='other-fixture-model')\n",
                   "client.completions.create(model='deepseek-flash')\n"
                   "client.chat.completions.create(model=selected_model)\n")
        for source in sources:
            with self.subTest(source=source):
                self.assertIsNone(verify_live.requested_model(source))

    def test_preflight_uses_file_hash_without_importing_or_requiring_function_names(self):
        root = self.fixture_repo()
        path = root / "agent_v0.py"
        path.write_text("raise RuntimeError('must not execute during preflight')\n")
        preflight.check_structure(root, "v0")
        recording = {"kind": "live-program-recording", "stage": "v0", "source_file": path.name,
                     "source_sha256": verify_live.file_sha256(path), "model_requested": None,
                     "inputs": list(verify_live.SCENARIOS["v0"]), "recorded_at": "unit-fixture",
                     "transcript": "explicit unit fixture transcript\n"}
        saved = root / "recording.json"
        verify_live.save_recording(saved, recording)
        self.assertEqual(preflight.check_recording(root, "v0", saved), recording)
        path.write_text("print('changed unit fixture')\n")
        with self.assertRaisesRegex(ValueError, "SHA"):
            preflight.check_recording(root, "v0", saved)

    def test_preflight_rejects_local_runtime_dependencies(self):
        root = self.fixture_repo()
        (root / "tools.py").write_text("# unit fixture helper\n")
        (root / "agent_v0.py").write_text("import tools\n")
        with self.assertRaisesRegex(ValueError, "独立运行"):
            preflight.check_structure(root, "v0")

    def test_failed_process_does_not_write_success_recording_or_print_key(self):
        root = self.fixture_repo()
        (root / "agent_v0.py").write_text("import sys\nprint('unit fixture failure')\nsys.exit(2)\n")
        destination = root / "recordings"
        output = io.StringIO()
        with patch.object(verify_live, "ROOT", root), \
                patch.dict(os.environ, {"DEEPSEEK_API_KEY": "UNIT-SECRET-MUST-NOT-PRINT"}), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = verify_live.main(["--stage", "v0", "--output-dir", str(destination)])
        self.assertEqual(result, 1)
        self.assertFalse(destination.exists())
        self.assertIn("unit fixture failure", output.getvalue())
        self.assertNotIn("UNIT-SECRET-MUST-NOT-PRINT", output.getvalue())

    def test_v5_records_independently_checked_statistics_and_actual_artifact_hashes(self):
        root = self.fixture_repo()
        analysis = ("import csv, json, statistics\nfrom pathlib import Path\n"
                    "with open('data/temperature.csv') as stream:\n"
                    "    values = [float(row['temperature']) for row in csv.DictReader(stream)]\n"
                    "stats = dict(count=len(values), mean=statistics.mean(values), max=max(values), min=min(values))\n"
                    "Path('result.json').write_text(json.dumps(stats))\n"
                    "Path('report.md').write_text('样本数：10\\n平均温度：24.5 °C\\n最高温度：29 °C\\n最低温度：20 °C\\n')\n")
        source = ("# explicit local unit fixture; no API\nimport subprocess, sys\nfrom pathlib import Path\n"
                  "from types import SimpleNamespace as NS\n"
                  "client = NS(completions=NS(create=lambda **kwargs: None))\n"
                  "client.completions.create(model='unit-fixture-model')\nlist(sys.stdin)\n"
                  f"Path('analysis.py').write_text({analysis!r})\n"
                  "subprocess.run([sys.executable, 'analysis.py'], check=True)\n"
                  "print('unit fixture artifacts complete')\n")
        (root / "agent_v5.py").write_text(source)
        recording = self.run_fixture(root, "v5")
        self.assertEqual(recording["transcript"], "unit fixture artifacts complete\n")
        self.assertEqual(recording["validation"]["statistics"],
                         {"count": 10, "mean": 24.5, "max": 29, "min": 20})
        self.assertEqual(set(recording["validation"]["artifact_sha256"]), set(verify_live.ARTIFACTS))
        self.assertEqual(recording["data_sha256"], verify_live.file_sha256(root / "data/temperature.csv"))
        path = root / "recordings/v5.json"
        verify_live.save_recording(path, recording)
        preflight.check_recording(root, "v5", path)
        (root / "data/temperature.csv").write_text("temperature\n0\n")
        with self.assertRaisesRegex(ValueError, "CSV"):
            preflight.check_recording(root, "v5", path)

    def test_teacher_import_needs_only_standard_library(self):
        result = subprocess.run([sys.executable, "-S", "-c", "import preflight, verify_live"],
                                cwd=verify_live.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
