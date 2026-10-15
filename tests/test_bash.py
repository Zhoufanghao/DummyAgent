"""直接 Bash 的行为测试；所有命令仅操作一次性目录。"""
import contextlib
import io
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

import agent_v5


class BashTests(unittest.TestCase):
    def run_in_directory(self, command, folder):
        with contextlib.chdir(folder), contextlib.redirect_stdout(io.StringIO()):
            return agent_v5.run_bash(command)

    def test_uses_the_launch_directory_and_keeps_created_files(self):
        with tempfile.TemporaryDirectory() as folder:
            output = self.run_in_directory("printf 'classroom' > report.md; pwd", folder)
            self.assertIn(str(Path(folder).resolve()), output)
            self.assertEqual((Path(folder) / "report.md").read_text(), "classroom")
            self.assertIn("exit_code: 0", output)

    def test_pipes_redirects_and_subdirectories(self):
        with tempfile.TemporaryDirectory() as folder:
            output = self.run_in_directory(
                "mkdir -p reports; printf 'first\\nsecond\\n' | head -n 1 > reports/result.txt; cat reports/result.txt", folder)
            self.assertIn("first\n", output)
            self.assertNotIn("second", output)
            self.assertEqual((Path(folder) / "reports/result.txt").read_text(), "first\n")

    def test_merges_stderr_and_reports_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            output = self.run_in_directory("printf 'out'; printf 'err' >&2; exit 7", folder)
            self.assertIn("exit_code: 7", output)
            self.assertIn("outerr", output)

    def test_bash_does_not_read_the_interactive_input(self):
        with tempfile.TemporaryDirectory() as folder:
            output = self.run_in_directory("read line || printf 'stdin EOF'", folder)
            self.assertIn("stdin EOF", output)

    def test_timeout_is_a_tool_observation(self):
        command = f"exec {shlex.quote(sys.executable)} -c 'import time; time.sleep(2)'"
        with tempfile.TemporaryDirectory() as folder, patch.object(agent_v5, "BASH_TIMEOUT", 0.05):
            self.assertEqual(self.run_in_directory(command, folder), "命令超时。")

    def test_non_utf8_output_is_readable(self):
        with tempfile.TemporaryDirectory() as folder:
            output = self.run_in_directory("printf '\\377'", folder)
            self.assertIn("\ufffd", output)


if __name__ == "__main__":
    unittest.main()
