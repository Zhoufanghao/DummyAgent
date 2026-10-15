#!/usr/bin/env python3
"""教师专用真实彩排：临时导出阶段，预置自由输入，核对后保存真实录制。"""

import argparse
import contextlib
import csv
from datetime import datetime, timezone
import hashlib
import importlib
import io
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
STAGES = ("v0-token", "v1-memory", "v2-chat", "v3-tools", "v4-agent-loop", "v5-execution")
STAGE_REFS = {stage: f"teaching-cleanup/{stage}" for stage in STAGES}
SCENARIOS = {
    "v0-token": ("牛顿第二定律告诉我们，", "热力学第一定律告诉我们，"),
    "v1-memory": ("我的实验编号是 A102，请记住。", "我的实验编号是什么？"),
    "v2-chat": ("我的实验编号是 A102，请记住。", "我的实验编号是什么？"),
    "v3-tools": ("请用calculator计算 (123.4 * 56.7) / 8.9，并简短汇报结果。", "刚才的计算结果是什么？"),
    "v4-agent-loop": (
        "先用calculator计算(12345 * 6789) / (17 + 29)，等结果返回后，"
        "再用calculator把该结果除以3。每轮只请求一次计算，最后简短汇报。",
        "刚才两次计算的最终结果是什么？"),
    "v5-execution": (
        "先用bash读取data/temperature.csv检查数据。然后生成并保存analysis.py，"
        "用独立的bash调用执行python3 analysis.py。脚本统计temperature列，保存result.json，"
        "唯一字段为count、mean、max、min；并保存report.md，使用固定中文标签样本数、平均温度、"
        "最高温度、最低温度展示对应数值，温度单位°C。执行后，再用bash读取result.json和report.md"
        "核对实际内容，最后简短汇报。所有代码和报告都必须由你通过工具实际生成。",
        "请用bash再次读取上轮保存的result.json和report.md，核对它们的数值；不要重新生成文件。"),
}


def git(repo, *args, binary=False):
    result = subprocess.run(["git", "-C", str(repo), *args], check=True,
                            capture_output=True, text=not binary, timeout=30)
    return result.stdout


def stage_refs():
    refs = json.loads(os.environ.get("DUMMY_AGENT_STAGE_REFS", "{}"))
    if (not isinstance(refs, dict) or any(key not in STAGES or not isinstance(value, str)
                                         or not value for key, value in refs.items())):
        raise ValueError("DUMMY_AGENT_STAGE_REFS 必须是六个阶段到非空 Git ref 的 JSON 对象")
    return {**STAGE_REFS, **refs}


def materialize(repo, stage, destination):
    """仅导出指定的真实提交；不使用工作区冒充已提交阶段。"""
    ref = stage_refs()[stage]
    commit = git(repo, "rev-parse", f"{ref}^{{commit}}").strip()
    archive = git(repo, "archive", commit, binary=True)
    destination = Path(destination).resolve()
    with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
        for member in contents.getmembers():
            path = (destination / member.name).resolve()
            if (not path.is_relative_to(destination) or member.issym() or member.islnk()
                    or not (member.isfile() or member.isdir())):
                raise ValueError("阶段归档含有不安全的路径或文件类型")
        contents.extractall(destination, filter="data")
    return commit


def runtime_hashes(directory):
    directory = Path(directory)
    paths = ["agent.py"]
    if (directory / "tools.py").is_file():
        paths.append("tools.py")
    if (directory / "data/temperature.csv").is_file():
        paths.append("data/temperature.csv")
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in paths}


def verify_artifacts(destination, source=ROOT / "data/temperature.csv"):
    """独立核对已导出的三个产物；不把模型的完成声明当成验收。"""
    original = Path(destination).absolute()
    if original.is_symlink() or not original.is_dir():
        raise ValueError("产物目录必须是真实目录")
    destination = original.resolve()
    names = {"analysis.py", "result.json", "report.md"}
    if {path.name for path in destination.iterdir()} != names:
        raise ValueError("验收目录必须且只能包含analysis.py、result.json、report.md")
    for name in names:
        path = destination / name
        if (path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1
                or not 0 < path.stat().st_size <= 256 * 1024):
            raise ValueError(f"不安全或缺失的产物：{name}")
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


def validate_events(stage, events, questions):
    """核对真实请求中的机制证据；不要求模型逐字复述固定答案。"""
    if not events:
        raise ValueError(f"{stage}没有真实API调用")
    for event in events:
        response = event["response"]
        if not response.get("id") or not response.get("model"):
            raise ValueError("响应缺少真实API的id/model")
        reasons = ("stop", "length") if stage == "v0-token" else ("stop", "tool_calls")
        if response["choices"][0]["finish_reason"] not in reasons:
            raise ValueError("API回复被截断或异常结束")
    if stage != "v0-token" and events[-1]["response"]["choices"][0]["finish_reason"] != "stop":
        raise ValueError("模型未正常回答后结束")
    if stage == "v0-token":
        if [event["request"]["prompt"] for event in events] != list(questions):
            raise ValueError("v0的两个输入必须独立提交")
        for event in events:
            probs = event["response"]["choices"][0].get("logprobs")
            if not probs or not probs.get("tokens") or not probs.get("top_logprobs"):
                raise ValueError("v0缺少真实token概率")
        return
    if stage == "v1-memory":
        first = events[0]["response"]["choices"][0]["text"].strip()
        if (len(events) != 2 or questions[0] not in events[1]["request"]["prompt"]
                or first not in events[1]["request"]["prompt"]):
            raise ValueError("v1第二轮未提交双方历史")
        if "A102" not in events[1]["response"]["choices"][0]["text"]:
            raise ValueError("v1第二轮真实回答未保留实验编号A102")
        return
    second = next((index for index, event in enumerate(events) if any(
        message.get("role") == "user" and message.get("content") == questions[1]
        for message in event["request"].get("messages", []))), None)
    if second is None or second == 0:
        raise ValueError("缺少跨用户轮的第二个自由输入")
    history = events[second]["request"]["messages"]
    previous_answer = events[second - 1]["response"]["choices"][0]["message"].get("content")
    if not any(message.get("role") == "assistant" and message.get("content") == previous_answer
               for message in history):
        raise ValueError("第二轮缺少上轮助手回答")
    if stage == "v2-chat":
        if [message["role"] for message in history] != ["system", "user", "assistant", "user"]:
            raise ValueError("v2结构化消息顺序不符")
        if "A102" not in (events[-1]["response"]["choices"][0]["message"].get("content") or ""):
            raise ValueError("v2第二轮真实回答未保留实验编号A102")
        return
    calls = [(index, call) for index, event in enumerate(events)
             for call in event["response"]["choices"][0]["message"].get("tool_calls") or []]
    wanted = "bash" if stage == "v5-execution" else "calculator"
    if not calls or any(call["function"]["name"] != wanted for _, call in calls):
        raise ValueError(f"{stage}缺少对应工具调用或混入其他阶段工具")
    if stage == "v4-agent-loop" and len({index for index, _ in calls if index < second}) < 2:
        raise ValueError("v4第一项任务缺少两轮独立工具决策")
    if stage == "v5-execution":
        successful = set()
        for event in events:
            for message in event["request"].get("messages", []):
                if message.get("role") == "tool":
                    result = json.loads(message["content"])
                    if result.get("ok") is True:
                        successful.add(message["tool_call_id"])
        commands = [(index, json.loads(call["function"]["arguments"])["command"])
                    for index, call in calls if call["id"] in successful]
        execute = next((index for index, command in commands
                        if re.search(r"\bpython3\s+analysis\.py(?:\s|$)", command)), None)
        if execute is None or not any(index < execute and "temperature.csv" in command
                                      for index, command in commands):
            raise ValueError("v5缺少先读取CSV、再成功执行python3 analysis.py的证据")
        first_checks = "\n".join(command for index, command in commands if execute < index < second)
        second_checks = "\n".join(command for index, command in commands if index >= second)
        if not all(name in first_checks for name in ("result.json", "report.md")):
            raise ValueError("v5第一轮缺少执行后的结果与报告检查")
        if not all(name in second_checks for name in ("result.json", "report.md")):
            raise ValueError("v5缺少跨用户轮读取同一组产物的证据")


class RecordingClient:
    """仅包装SDK的create；原始请求参数在SDK调用前深复制。"""

    def __init__(self, client):
        self.events = []
        self.completions = SimpleNamespace(create=self.wrap(client.completions.create, "completions.create"))
        self.chat = SimpleNamespace(completions=SimpleNamespace(
            create=self.wrap(client.chat.completions.create, "chat.completions.create")))

    def wrap(self, method, endpoint):
        def create(**params):
            request = json.loads(json.dumps(params, ensure_ascii=False))
            started = time.monotonic()
            response = method(**params)
            self.events.append({"endpoint": endpoint, "request": request,
                                "response": response.model_dump(mode="json"),
                                "elapsed_seconds": round(time.monotonic() - started, 3)})
            return response
        return create


@contextlib.contextmanager
def stage_module(directory):
    previous = {name: sys.modules.pop(name, None) for name in ("agent", "tools")}
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(directory))
    try:
        yield importlib.import_module("agent")
    finally:
        sys.path.pop(0)
        sys.dont_write_bytecode = before
        for name, module in previous.items():
            sys.modules.pop(name, None)
            if module is not None:
                sys.modules[name] = module


class Tee:
    def __init__(self, stream, transcript):
        self.stream, self.transcript = stream, transcript

    def write(self, text):
        self.stream.write(text)
        self.stream.flush()
        return self.transcript.write(text)

    def flush(self):
        self.stream.flush()


def verify_stage(repo, stage, client):
    questions = SCENARIOS[stage]
    recording_client = RecordingClient(client)
    transcript = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="agent-rehearsal-") as folder:
        root = Path(folder).resolve()
        snapshot, output = root / "source", root / "output"
        snapshot.mkdir()
        output.mkdir()
        commit = materialize(repo, stage, snapshot)
        hashes = runtime_hashes(snapshot)
        pending = iter(questions)
        count = 0

        def classroom_input(prompt):
            nonlocal count
            if prompt != "$ ":
                raise ValueError("课堂输入提示应为'$ '")
            try:
                question = next(pending)
            except StopIteration:
                print(prompt + "^D")
                raise EOFError from None
            count += 1
            print(prompt + question)
            return question

        previous_cwd = Path.cwd()
        try:
            os.chdir(output)
            with stage_module(snapshot) as agent, \
                    patch("builtins.input", side_effect=classroom_input), \
                    contextlib.redirect_stdout(Tee(sys.stdout, transcript)):
                print(f"[实时 LIVE · {stage}] model={agent.MODEL} · source={commit}")
                agent.main(recording_client)
                if count != len(questions):
                    raise ValueError("程序未读取完整的预置自由输入")
                if "[本任务停止]" in transcript.getvalue():
                    raise ValueError("彩排存在未完成的任务")
                validate_events(stage, recording_client.events, questions)
                validation = {"scenario": "interactive", "inputs": len(questions)}
                if stage == "v5-execution":
                    runs = list((output / "lab-runs").glob("run-*"))
                    if len(runs) != 1:
                        raise ValueError("应导出且仅导出一组实验产物")
                    expected, report = verify_artifacts(runs[0], snapshot / "data/temperature.csv")
                    if expected != {"count": 10, "mean": 24.5, "max": 29.0, "min": 20.0}:
                        raise ValueError("课堂CSV基准发生改变")
                    validation["statistics"] = expected
                    validation["artifact_sha256"] = {
                        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in runs[0].iterdir()}
                    print(f"[独立验收通过] {expected}\n{report}")
                model = agent.MODEL
                settings = {name.lower(): getattr(agent, name) for name in
                            ("TEMPERATURE", "TOKEN_STEPS", "MAX_ITERATIONS") if hasattr(agent, name)}
        finally:
            os.chdir(previous_cwd)
    return {"kind": "live-api-recording", "stage": stage,
            "recorded_at": datetime.now(timezone.utc).isoformat(), "model_requested": model,
            "mode": "interactive", "settings": settings, "inputs": list(questions),
            "source_commit": commit, "source_sha256": hashes["agent.py"],
            "runtime_sha256": hashes, "events": recording_client.events,
            "validation": validation, "transcript": transcript.getvalue()}


def save_recording(path, recording):
    """调用方完成全部验收后才进入写入；替换操作避免留下半个JSON。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".recording-", suffix=".json", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(recording, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, action="append", help="仅验证指定阶段；可多次使用")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, help="默认写入仓库recordings目录")
    parser.add_argument("--overwrite", action="store_true", help="允许替换已有录制")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    output = (args.output_dir or repo / "recordings").resolve()
    stages = args.stage or STAGES
    try:
        stage_refs()
        if not os.environ.get("DEEPSEEK_API_KEY"):
            raise ValueError("需要环境变量DEEPSEEK_API_KEY")
        for stage in stages:
            if (output / f"{stage}.json").exists() and not args.overwrite:
                raise ValueError(f"已有录制：{stage}.json；请另选--output-dir或明确指定--overwrite")
        from openai import OpenAI
        with OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/beta",
                    timeout=45, max_retries=1) as client:
            for stage in stages:
                recording = verify_stage(repo, stage, client)
                path = output / f"{stage}.json"
                save_recording(path, recording)
                print(f"PASS {stage} · 已保存真实自由交互录制：{path}")
    except (ValueError, OSError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"FAIL {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        # SDK异常的完整消息可能附带请求信息；只显示类型，认证信息不写入转录。
        print(f"FAIL {type(error).__name__}；本次未完成的阶段未写入录制", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
