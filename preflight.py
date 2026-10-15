"""离线备课检查：真实Tags、可运行回放、API录制、固定报告，不调用网络。"""
import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from run_stage import TAGS, ROOT


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_stage(tag):
    source = subprocess.run(["git", "show", f"{tag}:agent.py"], cwd=ROOT,
                            capture_output=True, check=True).stdout
    ast.parse(source, filename=f"{tag}/agent.py")
    recording_path = ROOT / "recordings" / f"{tag}.json"
    recording = json.loads(recording_path.read_text(encoding="utf-8"))
    require(recording["kind"] == "live-api-recording" and recording["stage"] == tag,
            f"{tag}: 录制类型或阶段不符")
    require(recording["source_sha256"] == hashlib.sha256(source).hexdigest(),
            f"{tag}: agent.py与录制源码SHA不符")
    require(recording["model_requested"] == "deepseek-flash", f"{tag}: 非默认Flash录制")
    events = recording["events"]
    require(bool(events), f"{tag}: 没有真实响应")
    for event in events:
        require(bool(event["response"].get("id")), f"{tag}: 缺少API响应ID")
        require(event["response"]["model"] == "deepseek-flash", f"{tag}: API返回模型不符")
    playback = subprocess.run([sys.executable, "-S", str(ROOT / "run_stage.py"), tag,
                               "--replay", str(recording_path)], cwd=ROOT,
                              capture_output=True, text=True, timeout=15)
    require(playback.returncode == 0, playback.stderr)
    require("回放 REPLAY" in playback.stdout and recording["transcript"] in playback.stdout,
            f"{tag}: 回放标识或内容不符")
    return events


def main():
    try:
        all_events = {}
        for tag in TAGS:
            all_events[tag] = check_stage(tag)
            print(f"PASS {tag} · Git源码SHA + 真实API录制 + 独立无SDK回放")
        probs = all_events["v0-token"][0]["response"]["choices"][0]["logprobs"]
        require(len(probs["tokens"]) == len(probs["top_logprobs"]) > 0, "token位置数据不完整")
        require(any(0 < math.exp(lp) < 1 for top in probs["top_logprobs"] for lp in top.values()),
                "主token演示缺少非退化概率")
        e = all_events["v1-memory"]
        require("A102" not in e[1]["request"]["prompt"] and "A102" in e[3]["request"]["prompt"],
                "history对照不成立")
        e = all_events["v2-chat"]
        require([m["role"] for m in e[1]["request"]["messages"]] ==
                ["system", "user", "assistant", "user"], "structured messages不完整")
        for tag in ("v3-tools", "v4-agent-loop", "v5-execution"):
            calls = [e["response"]["choices"][0]["message"].get("tool_calls") for e in all_events[tag]]
            require(any(calls), f"{tag}: 缺少真实tool call")
            require(all_events[tag][-1]["response"]["choices"][0]["finish_reason"] == "stop",
                    f"{tag}: 模型未正常结束")
        e = all_events["v4-agent-loop"]
        require(sum(bool(v["response"]["choices"][0]["message"].get("tool_calls")) for v in e) >= 2,
                "v4缺少多轮工具决策")
        require("[独立验收通过]" in json.loads((ROOT / "recordings/v5-execution.json").read_text())["transcript"],
                "v5未通过独立验收")
        result = json.loads((ROOT / "examples/final-result.json").read_text())
        require(result == {"count": 10, "mean": 24.5, "max": 29, "min": 20}, "示例统计错误")
        require((ROOT / "web/index.html").is_file(), "缺少静态网页，运行python build_viewer.py")
        subprocess.run([sys.executable, str(ROOT / "chat_template_demo.py")], cwd=ROOT,
                       check=True, capture_output=True)
        print("PASS 核心机制、固定报告与公开模板SHA；全程未调用API或执行历史工具")
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
