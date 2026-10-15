"""课堂支撑：配置、真实录制和纯文本回放；关键机制保留在 agent.py。"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

EVENTS = []


def call(method, **params):
    """调用真实 SDK；只记录请求参数/响应，不记录认证头。"""
    request_snapshot = json.loads(json.dumps(params, ensure_ascii=False))
    started = time.monotonic()
    response = method(**params)
    EVENTS.append({"endpoint": method.__qualname__, "request": request_snapshot,
                   "response": response.model_dump(mode="json"),
                   "elapsed_seconds": round(time.monotonic() - started, 3)})
    return response


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="AI Agent课堂：默认交互，--demo运行固定示例")
    parser.add_argument("--demo", action="store_true", help="固定课堂输入")
    parser.add_argument("--record", type=Path, help="保存本次真实运行")
    parser.add_argument("--replay", type=Path, help="离线显示录制，不执行API或工具")
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--steps", type=int, default=12, help="token位置数，1—64")
    parser.add_argument("--max-iterations", type=int, default=100, help="每个任务的LLM轮次上限，默认100，范围1—1000")
    parser.add_argument("--prompt", help="单次续写前缀（不进入交互）")
    parser.add_argument("--calculator", action="store_true", help="使用计算工具循环")
    parser.add_argument("--chat", action="store_true", help="使用角色对话")
    parser.add_argument("--tokens", action="store_true", help="重看最初的token演示")
    parser.add_argument("--task", help="替换工具/Agent任务")
    args = parser.parse_args(argv)
    if not 0 <= args.temperature <= 2 or not 1 <= args.steps <= 64 or not 1 <= args.max_iterations <= 1000:
        parser.error("temperature需0—2；steps需1—64；max-iterations需1—1000")
    if args.demo and (args.task is not None or args.prompt is not None):
        parser.error("--demo使用固定示例，请勿同时指定--task或--prompt")
    return args


def read_input(prompt):
    while True:
        try:
            value = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\n会话结束。")
            return None
        if value.strip() == ":quit":
            return None
        if value.strip():
            return value


def inputs(args, demo_questions, prompt, initial=None):
    if args.demo:
        yield from demo_questions
    elif initial is not None:
        yield initial
    else:
        print("[交互] :quit退出；有历史的版本可用:reset清空对话。")
        while (value := read_input(prompt)) is not None:
            yield value


def run(main, stage):
    args = parse_args()
    if args.replay:
        record = json.loads(args.replay.read_text(encoding="utf-8"))
        if record.get("kind") != "live-api-recording" or record.get("stage") != stage:
            raise SystemExit("需要与当前Tag一致的真实录制文件")
        print(f"[回放 REPLAY · {record['stage']} · {record['recorded_at']}]\n不请求API、不执行工具。")
        print(record["transcript"])
        return
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("先 source ~/.config/api-keys/llm.env；需要 DEEPSEEK_API_KEY")
    from openai import OpenAI, APIError
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com/beta", timeout=45, max_retries=1)
    args.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
    transcript = io.StringIO()
    EVENTS.clear()

    class Tee:
        def write(self, value):
            sys.__stdout__.write(value)
            sys.__stdout__.flush()
            return transcript.write(value)

        def flush(self):
            sys.__stdout__.flush()

    try:
        with contextlib.redirect_stdout(Tee()):
            print(f"[实时 LIVE · {stage}] model={args.model} · https://api.deepseek.com/beta")
            main(client, args)
    except APIError as error:
        print(f"API失败：{type(error).__name__}，HTTP {getattr(error, 'status_code', None)}。可使用 --replay。", file=sys.stderr)
        raise SystemExit(1) from None
    except (ValueError, RuntimeError, OSError) as error:
        print(f"演示未完成：{error}", file=sys.stderr)
        raise SystemExit(1) from None
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        record = {"kind": "live-api-recording", "stage": stage,
                  "recorded_at": datetime.now(timezone.utc).isoformat(),
                  "model_requested": args.model, "events": EVENTS,
                  "mode": "demo" if args.demo else "single" if args.task is not None or args.prompt is not None else "interactive",
                  "settings": {"max_iterations": args.max_iterations, "temperature": args.temperature, "steps": args.steps},
                  "source_sha256": hashlib.sha256(Path(__file__).with_name("agent.py").read_bytes()).hexdigest(),
                  "transcript": transcript.getvalue()}
        args.record.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[已录制] {args.record}")
