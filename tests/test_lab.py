"""教师侧独立核对真实统计与报告，不约束课堂程序的实现结构。"""

import csv
import json
import math
from pathlib import Path
import statistics
import tempfile
import unittest

from verify_live import ROOT, verify_artifacts


class LabArtifacts(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="report-unit-fixture-")
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        with (ROOT / "data/temperature.csv").open(encoding="utf-8", newline="") as stream:
            values = [float(row["temperature"]) for row in csv.DictReader(stream)]
        self.expected = {"count": len(values), "mean": statistics.mean(values),
                         "max": max(values), "min": min(values)}
        (self.workspace / "analysis.py").write_text("# explicit unit fixture\nprint('fixture')\n")
        self.write_statistics(self.expected)
        self.report = ("# 温度统计报告\n\n"
                       f"样本数：{self.expected['count']}\n"
                       f"平均温度：{self.expected['mean']} °C\n"
                       f"最高温度：{self.expected['max']} °C\n"
                       f"最低温度：{self.expected['min']} °C\n")
        (self.workspace / "report.md").write_text(self.report, encoding="utf-8")

    def write_statistics(self, values):
        (self.workspace / "result.json").write_text(json.dumps(values), encoding="utf-8")

    def test_complete_artifacts_and_other_working_files_are_accepted(self):
        (self.workspace / "data").mkdir()
        (self.workspace / "data/extra.csv").write_text("fixture\n")
        (self.workspace / "notes.txt").write_text("other working files are allowed")
        expected, report = verify_artifacts(self.workspace)
        self.assertEqual(expected, {"count": 10, "mean": 24.5, "max": 29, "min": 20})
        self.assertEqual(report, self.report)

    def test_wrong_nonfinite_boolean_and_nonnumeric_results_are_rejected(self):
        for value in (self.expected["mean"] + 1, math.nan, math.inf, True, "24.5", 10 ** 400):
            with self.subTest(value=value):
                self.write_statistics({**self.expected, "mean": value})
                with self.assertRaises(ValueError):
                    verify_artifacts(self.workspace)

    def test_result_requires_exact_statistic_fields(self):
        for values in ({**self.expected, "extra": 1}, {"mean": 24.5}, [], None):
            with self.subTest(values=values):
                self.write_statistics(values)
                with self.assertRaises(ValueError):
                    verify_artifacts(self.workspace)

    def test_report_requires_matching_values_labels_and_temperature_unit(self):
        reports = (self.report.replace("最高温度：29.0", "最高温度：9999"),
                   self.report.replace("最低温度", "minimum"), self.report.replace("°C", ""))
        for report in reports:
            with self.subTest(report=report):
                (self.workspace / "report.md").write_text(report, encoding="utf-8")
                with self.assertRaises(ValueError):
                    verify_artifacts(self.workspace)

    def test_missing_or_empty_script_result_and_report_are_rejected(self):
        for name in ("analysis.py", "result.json", "report.md"):
            path = self.workspace / name
            content = path.read_bytes()
            with self.subTest(name=name):
                path.unlink()
                with self.assertRaises(ValueError):
                    verify_artifacts(self.workspace)
                path.write_bytes(b"")
                with self.assertRaises(ValueError):
                    verify_artifacts(self.workspace)
                path.write_bytes(content)

    def test_acceptance_uses_the_supplied_csv(self):
        source = self.workspace / "fixture.csv"
        source.write_text("temperature\n2\n4\n", encoding="utf-8")
        self.write_statistics({"count": 2, "mean": 3, "max": 4, "min": 2})
        (self.workspace / "report.md").write_text(
            "样本数：2\n平均温度：3 °C\n最高温度：4 °C\n最低温度：2 °C\n", encoding="utf-8")
        expected, _ = verify_artifacts(self.workspace, source)
        self.assertEqual(expected, {"count": 2, "mean": 3, "max": 4, "min": 2})


if __name__ == "__main__":
    unittest.main()
