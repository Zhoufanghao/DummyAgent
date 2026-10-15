"""Independent artifact acceptance and host export boundary checks."""

import contextlib
import csv
import io
import json
import math
import os
from pathlib import Path
import statistics
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import lab


class LabArtifacts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-lab-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name).resolve()
        lab.seed(self.workspace)
        with lab.SOURCE.open(encoding="utf-8", newline="") as stream:
            values = [float(row["temperature"]) for row in csv.DictReader(stream)]
        self.expected = {"count": len(values), "mean": statistics.mean(values),
                         "max": max(values), "min": min(values)}
        (self.workspace / "analysis.py").write_text("# fixture script\nprint('fixture')\n")
        self.write_statistics(self.expected)
        self.report = ("# 温度统计报告\n\n"
                       f"样本数：{self.expected['count']}\n"
                       f"平均温度：{self.expected['mean']} °C\n"
                       f"最高温度：{self.expected['max']} °C\n"
                       f"最低温度：{self.expected['min']} °C\n")
        (self.workspace / "report.md").write_text(self.report, encoding="utf-8")

    def write_statistics(self, actual):
        (self.workspace / "result.json").write_text(json.dumps(actual), encoding="utf-8")

    def test_seed_is_independent_copy(self):
        source = lab.SOURCE.read_bytes()
        (self.workspace / "data/temperature.csv").write_text("modified")
        self.assertEqual(lab.SOURCE.read_bytes(), source)

    def test_complete_artifacts_accepted(self):
        expected, report = lab.verify(self.workspace)
        self.assertEqual(expected, self.expected)
        self.assertEqual(report, self.report)

    def test_wrong_and_nonfinite_results_rejected(self):
        for value in [self.expected["mean"] + 1, math.nan, math.inf, True, "22"]:
            with self.subTest(value=value):
                self.write_statistics({**self.expected, "mean": value})
                with self.assertRaises(ValueError):
                    lab.verify(self.workspace)

    def test_oversized_number_is_validation_error(self):
        self.write_statistics({**self.expected, "mean": 10 ** 400})
        with self.assertRaises(ValueError):
            lab.verify(self.workspace)

    def test_extra_result_fields_rejected(self):
        self.write_statistics({**self.expected, "extra": "unrequested"})
        with self.assertRaises(ValueError):
            lab.verify(self.workspace)

    def test_report_must_match_numeric_results(self):
        report = self.report.replace(f"最高温度：{self.expected['max']}", "最高温度：9999")
        (self.workspace / "report.md").write_text(report, encoding="utf-8")
        with self.assertRaises(ValueError):
            lab.verify(self.workspace)

    def test_tampered_input_rejected(self):
        (self.workspace / "data/temperature.csv").write_text("temperature\n999\n")
        with self.assertRaises(ValueError):
            lab.verify(self.workspace)

    def test_report_symlink_rejected_before_read(self):
        report = self.workspace / "report.md"
        report.unlink()
        report.symlink_to(lab.SOURCE)
        with self.assertRaises(ValueError):
            lab.verify(self.workspace)

    def test_report_hardlink_rejected_before_read(self):
        report = self.workspace / "report.md"
        report.unlink()
        report.hardlink_to(self.workspace / "data/temperature.csv")
        with self.assertRaises(ValueError):
            lab.verify(self.workspace)

    def test_publish_copies_only_three_verified_files(self):
        with tempfile.TemporaryDirectory(prefix="teacher-export-") as folder:
            previous = Path.cwd()
            try:
                os.chdir(folder)
                with contextlib.redirect_stdout(io.StringIO()):
                    destination = lab.publish(self.workspace)
            finally:
                os.chdir(previous)
            self.assertTrue(destination.is_relative_to(Path(folder).resolve()))
            self.assertEqual({path.name for path in destination.iterdir()},
                             {"analysis.py", "result.json", "report.md"})
            self.assertEqual((destination / "report.md").read_text(), self.report)
            for name in ("analysis.py", "result.json", "report.md"):
                self.assertFalse((destination / name).is_symlink())
                self.assertNotEqual((destination / name).stat().st_ino,
                                    (self.workspace / name).stat().st_ino)


class AcceptanceFeedback(unittest.TestCase):
    def test_failed_acceptance_and_tool_failure_both_reach_next_llm_request(self):
        # Explicit unit fixtures, never represented as live model output.
        import agent
        call = NS(id="fixture-call", function=NS(name="bash", arguments='{"command":"pwd"}'))
        tool_message = NS(content=None, tool_calls=[call], model_dump=lambda **kwargs: {
            "role": "assistant", "tool_calls": [{"id": call.id, "type": "function",
            "function": {"name": call.function.name, "arguments": call.function.arguments}}]})
        replies = iter([
            NS(choices=[NS(finish_reason="stop", message=NS(tool_calls=None, content="premature fixture"))]),
            NS(choices=[NS(finish_reason="tool_calls", message=tool_message)]),
            NS(choices=[NS(finish_reason="stop", message=NS(tool_calls=None, content="repaired fixture"))]),
        ])
        observed = []

        def fixture_response(method, **params):
            observed.append(json.loads(json.dumps(params["messages"])))
            return next(replies)

        args = NS(demo=True, model="unit-fixture", temperature=0, max_iterations=3)
        client = NS(chat=NS(completions=NS(create=object())))
        with patch.object(agent, "call", side_effect=fixture_response), \
                patch.object(agent, "execute", return_value={"ok": False, "error": "fixture failure"}), \
                patch.object(lab, "publish", side_effect=[ValueError("fixture mismatch"), Path("fixture-export")]), \
                contextlib.redirect_stdout(io.StringIO()):
            agent.agent_loop(client, args, [{"role": "user", "content": "fixture task"}],
                             tools=[agent.BASH], workspace=Path("unused-fixture-workspace"))
        self.assertEqual(len(observed), 3)
        self.assertIn("外部验收未通过", observed[1][-1]["content"])
        self.assertIn("fixture mismatch", observed[1][-1]["content"])
        self.assertEqual(observed[2][-1]["role"], "tool")
        self.assertIn("fixture failure", observed[2][-1]["content"])


class InteractiveExports(unittest.TestCase):
    """自由任务导出只检查安全边界，不套用固定温度报告的验收标准。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-free-task-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name).resolve()
        self.teacher_temp = tempfile.TemporaryDirectory(prefix="teacher-free-export-")
        self.addCleanup(self.teacher_temp.cleanup)
        self.export_root = Path(self.teacher_temp.name).resolve()

    def export(self):
        with patch.object(lab.Path, "cwd", return_value=self.export_root), \
                contextlib.redirect_stdout(io.StringIO()):
            return lab.export_outputs(self.workspace)

    def test_each_output_can_be_exported_without_the_other_two(self):
        lab.seed(self.workspace)
        contents = {"analysis.py": "print('independent fixture')\n",
                    "result.json": '{"free_task": true}\n',
                    "report.md": "# 自由任务\n这份报告没有固定温度统计字段。\n"}
        for name, text in contents.items():
            with self.subTest(name=name):
                source = self.workspace / name
                source.write_text(text, encoding="utf-8")
                destination = self.export()
                self.assertTrue(destination.is_relative_to(self.export_root / "lab-runs"))
                self.assertEqual({path.name for path in destination.iterdir()}, {name})
                exported = destination / name
                self.assertEqual(exported.read_text(encoding="utf-8"), text)
                self.assertFalse(exported.is_symlink())
                self.assertNotEqual(exported.stat().st_ino, source.stat().st_ino)
                source.unlink()

    def test_empty_workspace_has_no_export(self):
        self.assertIsNone(self.export())
        self.assertFalse((self.export_root / "lab-runs").exists())

    def test_input_data_and_empty_whitelisted_files_are_not_exported(self):
        lab.seed(self.workspace)
        (self.workspace / "analysis.py").write_text("")
        self.assertIsNone(self.export())
        self.assertFalse((self.export_root / "lab-runs").exists())

    def test_unexpected_file_is_rejected(self):
        (self.workspace / "notes.txt").write_text("not a permitted artifact")
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse((self.export_root / "lab-runs").exists())

    def test_symlink_is_rejected_before_export(self):
        (self.workspace / "report.md").symlink_to(lab.SOURCE)
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse((self.export_root / "lab-runs").exists())

    def test_hardlink_is_rejected_before_export(self):
        lab.seed(self.workspace)
        (self.workspace / "result.json").hardlink_to(self.workspace / "data/temperature.csv")
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse((self.export_root / "lab-runs").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
