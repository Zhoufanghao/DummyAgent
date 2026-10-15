#!/usr/bin/env python3
"""教师离线预检：逐阶段检查独立源码、结构和真实录制来源，不调用API。"""

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from verify_live import ROOT, SCENARIOS, STAGES, materialize, runtime_hashes, validate_events


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_structure(directory, stage):
    """检查每阶段自身职责，避免把旧入口或公共框架带回课堂代码。"""
    source = (directory / "agent.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename=f"{stage}/agent.py")
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    require("main" in functions and "cli" in functions, f"{stage}: 需要main(client)及cli()")
    require([arg.arg for arg in functions["main"].args.args] == ["client"],
            f"{stage}: main只接受client")
    require(not functions["cli"].args.args, f"{stage}: cli不接受参数")
    require(all(not (directory / name).exists() for name in
                ("common.py", "run_stage.py", "sandbox.py", "lab.py")),
            f"{stage}: 仍含已移除的运行辅助模块")
    has_tools = (directory / "tools.py").is_file()
    require(has_tools == (stage in STAGES[3:]), f"{stage}: 工具文件不符合阶段职责")
    sources = [source]
    if has_tools:
        tools = (directory / "tools.py").read_text(encoding="utf-8")
        ast.parse(tools, filename=f"{stage}/tools.py")
        sources.append(tools)
    joined = "\n".join(sources)
    require(all(token not in joined for token in
                (":quit", ":reset", "argparse", "from common", "import common", "from sandbox", "from lab")),
            f"{stage}: 课堂运行源码仍有旧交互或辅助依赖")
    require(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "input" and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant) and node.args[0].value == "$ "
                for node in ast.walk(tree)), f"{stage}: 输入提示应为'$ '")
    require("EOFError" in source, f"{stage}: 未处理Ctrl+D结束")
    constants = {target.id: node.value for node in tree.body if isinstance(node, ast.Assign)
                 for target in node.targets if isinstance(target, ast.Name)}
    require("MODEL" in constants and "TEMPERATURE" in constants,
            f"{stage}: 缺少顶部模型/温度配置")
    if stage == "v0-token":
        require("Pr[token | context]" in source, "v0: 缺少真实token概率说明")
        require(isinstance(constants.get("TOKEN_STEPS"), ast.Constant)
                and constants["TOKEN_STEPS"].value == 12, "v0: TOKEN_STEPS应为12")
    else:
        require("complete_tokens" not in functions and "logprobs" not in source,
                f"{stage}: 不应残留v0概率演示")
    if stage in STAGES[4:]:
        require(isinstance(constants.get("MAX_ITERATIONS"), ast.Constant)
                and constants["MAX_ITERATIONS"].value == 100,
                f"{stage}: MAX_ITERATIONS应为100")
    if stage == "v5-execution":
        require("calculator" not in joined and "def agent_loop" in source,
                "v5: 只保留隔离bash工具与Agent循环")
    # -S禁止SDK/site-packages。导入必须安全；只有cli()才建立SDK连接。
    harness = "import agent; assert callable(agent.main) and callable(agent.cli)"
    result = subprocess.run([sys.executable, "-S", "-c", harness], cwd=directory,
                            capture_output=True, text=True, timeout=10)
    require(result.returncode == 0, f"{stage}: 无SDK导入失败：{result.stderr}")


def check_recording(directory, stage, commit, path):
    recording = json.loads(path.read_text(encoding="utf-8"))
    require(recording.get("kind") == "live-api-recording" and recording.get("stage") == stage,
            f"{stage}: 录制类型或阶段不符")
    hashes = runtime_hashes(directory)
    require(recording.get("source_sha256") == hashes["agent.py"], f"{stage}: agent.py与录制SHA不符")
    require(recording.get("runtime_sha256") == hashes, f"{stage}: 运行文件与录制SHA不符")
    require(recording.get("source_commit") == commit, f"{stage}: 录制不属于当前阶段提交")
    require(recording.get("mode") == "interactive", f"{stage}: 不是自由交互录制")
    require(recording.get("inputs") == list(SCENARIOS[stage]), f"{stage}: 彩排输入不符")
    require(recording.get("recorded_at") and recording.get("transcript"), f"{stage}: 录制缺少时间或转录")
    require(recording.get("model_requested"), f"{stage}: 录制缺少请求模型")
    validate_events(stage, recording["events"], SCENARIOS[stage])
    if stage == "v5-execution":
        require(recording.get("validation", {}).get("statistics") ==
                {"count": 10, "mean": 24.5, "max": 29, "min": 20},
                "v5: 录制缺少固定报告独立验收")
        require("[独立验收通过]" in recording["transcript"], "v5: 转录缺少验收结果")
    return recording


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--recordings", type=Path, help="默认检查仓库recordings目录")
    parser.add_argument("--structure-only", action="store_true", help="新彩排前仅检查已提交源码结构")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    recordings = args.recordings or repo / "recordings"
    try:
        with tempfile.TemporaryDirectory(prefix="agent-preflight-") as folder:
            for stage in STAGES:
                directory = Path(folder) / stage
                directory.mkdir()
                commit = materialize(repo, stage, directory)
                check_structure(directory, stage)
                if not args.structure_only:
                    check_recording(directory, stage, commit, recordings / f"{stage}.json")
                evidence = "结构" if args.structure_only else "结构、真实API录制来源及运行文件SHA"
                print(f"PASS {stage} · {evidence}")
        print("PASS 离线预检；未调用API或执行历史工具")
    except (ValueError, OSError, KeyError, SyntaxError, subprocess.SubprocessError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
