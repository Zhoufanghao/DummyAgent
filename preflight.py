#!/usr/bin/env python3
"""教师离线预检：六份独立文件的语法与真实程序录制来源，不运行课堂代码。"""

import argparse
import ast
import json
from pathlib import Path
import sys

from verify_live import ARTIFACTS, ROOT, SCENARIOS, STAGES, file_sha256


def check_structure(repo, stage):
    path = Path(repo) / f"agent_{stage}.py"
    tree = ast.parse(path.read_bytes(), filename=str(path))
    compile(tree, str(path), "exec")
    local_modules = {file.stem for file in Path(repo).glob("*.py")}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports = [(node.module or "").split(".")[0]]
        else:
            continue
        if any(name in local_modules for name in imports):
            raise ValueError(f"{path.name}应独立运行，不能导入仓库中的其他Python文件")


def check_recording(repo, stage, path):
    repo = Path(repo)
    filename = f"agent_{stage}.py"
    recording = json.loads(Path(path).read_text(encoding="utf-8"))
    if (recording.get("kind") != "live-program-recording" or recording.get("stage") != stage
            or recording.get("source_file") != filename):
        raise ValueError(f"{stage}: 录制类型、阶段或源文件不符")
    if recording.get("source_sha256") != file_sha256(repo / filename):
        raise ValueError(f"{stage}: 源文件与录制SHA不符")
    if recording.get("inputs") != list(SCENARIOS[stage]):
        raise ValueError(f"{stage}: 彩排输入不符")
    if (not isinstance(recording.get("transcript"), str) or not recording["transcript"].strip()
            or not recording.get("recorded_at") or "model_requested" not in recording):
        raise ValueError(f"{stage}: 录制缺少时间、请求模型配置或原始终端输出")
    if stage == "v5":
        if recording.get("data_sha256") != file_sha256(repo / "data/temperature.csv"):
            raise ValueError("v5: 输入CSV与录制SHA不符")
        validation = recording.get("validation", {})
        if validation.get("statistics") != {"count": 10, "mean": 24.5, "max": 29, "min": 20}:
            raise ValueError("v5: 缺少正确的教师独立统计验收")
        hashes = validation.get("artifact_sha256", {})
        if set(hashes) != set(ARTIFACTS) or any(not isinstance(value, str) or len(value) != 64
                                               for value in hashes.values()):
            raise ValueError("v5: 缺少实际产物SHA")
    return recording


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structure-only", action="store_true", help="彩排前仅检查六份源码结构")
    args = parser.parse_args(argv)
    try:
        for stage in STAGES:
            check_structure(ROOT, stage)
            if not args.structure_only:
                check_recording(ROOT, stage, ROOT / "recordings" / f"{stage}.json")
            evidence = "独立源码与语法" if args.structure_only else "独立源码、语法和真实程序录制SHA"
            print(f"PASS {stage} · {evidence}")
        print("PASS 离线预检；未调用API或执行课堂程序")
    except (ValueError, OSError, KeyError, SyntaxError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
