#!/usr/bin/env python3
"""教师彩排：运行独立课堂文件，保存真实终端输出并核对温度报告。"""

import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
STAGES = tuple(f"v{index}" for index in range(6))
LOOP_SCENARIOS = (
    "先用calculator计算123456789 * 987654321，得到整数A后，取A的末6位作为B；\n"
    "再用calculator计算B**3 + 17 * B。请给出A、B和最终整数。\n每次只请求当前一步的计算，"
    "必须等工具返回后再进行下一步，不要把整条流程合成一个表达式。",
    "先用calculator计算987654321**2 + 123456789得到整数A；看工具返回的A末位："
    "若为奇数，下一步计算A * 123457 + 76543；否则计算A * 76543 + 123457，得到B；"
    "最后用calculator计算B % 1000000007。请给出A、B和最终余数。每次只请求当前一步的计算，"
    "必须拿到工具结果后再选择下一步，不要把流程合成一个表达式。",
)
SCENARIOS = {
    "v0": ("牛顿第二定律告诉我们，", "热力学第一定律告诉我们，"),
    "v1": ("我的实验编号是 A102，请记住。", "我的实验编号是什么？"),
    "v2": ("我的实验编号是 A102，请记住。", "我的实验编号是什么？"),
    "v3": LOOP_SCENARIOS,
    "v4": LOOP_SCENARIOS,
    "v5": (
        "先用bash读取data/temperature.csv检查数据。然后生成并保存analysis.py，"
        "用独立的bash调用执行python3 analysis.py。脚本统计temperature列，保存result.json，"
        "唯一字段为count、mean、max、min；并保存report.md，使用固定中文标签样本数、平均温度、"
        "最高温度、最低温度展示对应数值，温度单位°C。执行后，再用bash读取result.json和report.md"
        "核对实际内容，最后简短汇报。所有代码和报告都必须由你通过工具实际生成。",
        "请用bash再次读取上轮保存的result.json和report.md，核对它们的数值；不要重新生成文件。"),
}
ARTIFACTS = ("analysis.py", "result.json", "report.md")


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def requested_model(source):
    """读取SDK请求中一致的model字符串；动态或混合配置保持未知。"""
    models = set()
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "create" and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "completions"):
            continue
        value = next((keyword.value for keyword in node.keywords if keyword.arg == "model"), None)
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            return None
        models.add(value.value)
    return next(iter(models)) if len(models) == 1 else None


def verify_artifacts(destination, source=ROOT / "data/temperature.csv"):
    """教师独立验收统计和报告；允许工作目录同时存在数据和其他文件。"""
    destination = Path(destination)
    for name in ARTIFACTS:
        path = destination / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"缺少或为空的产物：{name}")
    with Path(source).open(encoding="utf-8", newline="") as stream:
        values = [float(row["temperature"]) for row in csv.DictReader(stream)]
    expected = {"count": len(values), "mean": statistics.mean(values),
                "max": max(values), "min": min(values)}
    actual = json.loads((destination / "result.json").read_text(encoding="utf-8"))
    if not isinstance(actual, dict) or set(actual) != set(expected):
        raise ValueError("result.json必须且只能包含count/mean/max/min")
    for key, value in expected.items():
        number = actual[key]
        if (type(number) not in (int, float) or not -1e15 <= number <= 1e15
                or not math.isclose(number, value, rel_tol=1e-9)):
            raise ValueError(f"统计不符：{key}")
    report = (destination / "report.md").read_text(encoding="utf-8")
    text = report.replace("*", "")
    for label, key in (("样本数", "count"), ("平均温度", "mean"),
                       ("最高温度", "max"), ("最低温度", "min")):
        match = re.search(re.escape(label) + r"[\s：:|]*(-?\d+(?:\.\d+)?)", text)
        if not match or not math.isclose(float(match[1]), expected[key], rel_tol=1e-9):
            raise ValueError(f"报告需用固定标签展示正确结果：{label}")
    if "°C" not in report and "℃" not in report:
        raise ValueError("报告缺少温度单位°C")
    return expected, report


def verify_stage(repo, stage):
    repo = Path(repo).resolve()
    filename = f"agent_{stage}.py"
    source = (repo / filename).read_bytes()
    record = {"kind": "live-program-recording", "stage": stage, "source_file": filename,
              "source_sha256": hashlib.sha256(source).hexdigest(),
              "recorded_at": datetime.now(timezone.utc).isoformat(),
              "model_requested": requested_model(source), "inputs": list(SCENARIOS[stage])}
    with tempfile.TemporaryDirectory(prefix="agent-rehearsal-") as folder:
        workspace = Path(folder)
        script = workspace / filename
        script.write_bytes(source)
        if (repo / "data").is_dir():
            shutil.copytree(repo / "data", workspace / "data")
        if stage == "v5":
            record["data_sha256"] = file_sha256(workspace / "data/temperature.csv")
        # Bracketed paste keeps each question's embedded newlines in one submission.
        keyboard_input = "".join(f"\x1b[200~{question}\x1b[201~\n" for question in SCENARIOS[stage])
        # Closing stdin after these questions supplies the same EOF as Ctrl+D.
        result = subprocess.run([sys.executable, "-u", str(script)], cwd=workspace,
                                input=keyboard_input, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        record["transcript"] = result.stdout
        print(result.stdout, end="", flush=True)
        if result.returncode:
            raise RuntimeError(f"{stage}彩排进程退出码为{result.returncode}；未保存成功录制")
        if not result.stdout.strip():
            raise ValueError(f"{stage}没有终端输出")
        if stage == "v5":
            if file_sha256(workspace / "data/temperature.csv") != record["data_sha256"]:
                raise ValueError("彩排修改了输入CSV")
            expected, _ = verify_artifacts(workspace, repo / "data/temperature.csv")
            if expected != {"count": 10, "mean": 24.5, "max": 29.0, "min": 20.0}:
                raise ValueError("课堂CSV基准发生改变")
            record["validation"] = {"statistics": expected, "artifact_sha256": {
                name: file_sha256(workspace / name) for name in ARTIFACTS}}
            print(f"[教师独立验收通过] {expected}")
    return record


def save_recording(path, recording):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(recording, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, action="append", help="仅验证指定阶段；默认运行六份文件")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "recordings")
    parser.add_argument("--overwrite", action="store_true", help="允许替换已有录制")
    args = parser.parse_args(argv)
    stages = args.stage or STAGES
    try:
        if not os.environ.get("DEEPSEEK_API_KEY"):
            raise ValueError("需要环境变量DEEPSEEK_API_KEY")
        for stage in stages:
            if (args.output_dir / f"{stage}.json").exists() and not args.overwrite:
                raise ValueError(f"已有录制：{stage}.json；请另选--output-dir或明确指定--overwrite")
        for stage in stages:
            print(f"RUN {stage} · agent_{stage}.py", flush=True)
            recording = verify_stage(ROOT, stage)
            destination = args.output_dir / f"{stage}.json"
            save_recording(destination, recording)
            print(f"PASS {stage} · 已保存真实程序运行记录：{destination}")
    except (ValueError, OSError, RuntimeError, SyntaxError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
