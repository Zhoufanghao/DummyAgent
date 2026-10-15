"""可信的实验目录准备和独立验收；不替模型生成计算程序或报告。"""
import csv
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import tempfile
from sandbox import validate_workspace

SOURCE = Path(__file__).resolve().parent / "data" / "temperature.csv"


def seed(workspace):
    (workspace / "data").mkdir()
    shutil.copyfile(SOURCE, workspace / "data" / "temperature.csv")


def verify(workspace):
    validate_workspace(workspace)  # 导出前再次拒绝软/硬链接与超限文件。
    if (workspace / "data" / "temperature.csv").read_bytes() != SOURCE.read_bytes():
        raise ValueError("输入CSV发生改变")
    if not (workspace / "analysis.py").is_file() or not (workspace / "analysis.py").stat().st_size:
        raise ValueError("缺少模型生成的analysis.py")
    with SOURCE.open(encoding="utf-8", newline="") as file:
        values = [float(row["temperature"]) for row in csv.DictReader(file)]
    expected = {"count": len(values), "mean": statistics.mean(values),
                "max": max(values), "min": min(values)}
    actual = json.loads((workspace / "result.json").read_text(encoding="utf-8"))
    if not isinstance(actual, dict) or set(actual) != set(expected):
        raise ValueError("result.json必须包含且仅包含count/mean/max/min")
    for key, value in expected.items():
        if (type(actual[key]) not in (int, float) or not -1e15 <= actual[key] <= 1e15
                or not math.isclose(actual[key], value, rel_tol=1e-9)):
            raise ValueError(f"统计不符：{key}")
    report = (workspace / "report.md").read_text(encoding="utf-8")
    text = report.replace("*", "")
    for label, key in [("样本数", "count"), ("平均温度", "mean"), ("最高温度", "max"), ("最低温度", "min")]:
        match = re.search(re.escape(label) + r"[\s：:|]*(-?\d+(?:\.\d+)?)", text)
        if not match or not math.isclose(float(match[1]), expected[key], rel_tol=1e-9):
            raise ValueError(f"报告需用固定标签展示正确结果：{label}")
    return expected, report


def publish(workspace):
    expected, report = verify(workspace)
    # cwd由教师控制；模型不能选择宿主的导出位置。
    root = Path.cwd() / "lab-runs"
    root.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="run-", dir=root))
    for name in ("analysis.py", "result.json", "report.md"):
        shutil.copyfile(workspace / name, destination / name)
    print(f"[独立验收通过] {expected}")
    print(f"[已导出报告] {destination / 'report.md'}\n{report}")
    return destination


def export_outputs(workspace):
    """自由任务只做文件安全检查，不强制CSV报告格式或统计目标。"""
    validate_workspace(workspace)
    names = [name for name in ("analysis.py", "result.json", "report.md")
             if (workspace / name).is_file() and (workspace / name).stat().st_size]
    if not names:
        return None
    root = Path.cwd() / "lab-runs"
    root.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="run-", dir=root))
    for name in names:
        shutil.copyfile(workspace / name, destination / name)
    print(f"[已安全导出产物] {destination}；文件：{', '.join(names)}")
    return destination
