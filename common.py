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


def run(main, stage):
    parser = argparse.ArgumentParser(description=f"AI Agent 课堂 · {stage}")
    parser.add_argument("--demo", action="store_true", help="固定课堂输入")
    parser.add_argument("--record", type=Path, help="保存本次真实运行")
    parser.add_argument("--replay", type=Path, help="离线显示录制，不执行API或工具")
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--steps", type=int, default=12, help="token位置数，1—64")
    parser.add_argument("--max-iterations", type=int, default=8, help="LLM轮次上限，1—12")
    parser.add_argument("--prompt", default="牛顿第二定律告诉我们，")
    parser.add_argument("--calculator", action="store_true", help="使用v4的计算工具循环")
    parser.add_argument("--chat", action="store_true", help="重看角色对话，可结合--demo")
    parser.add_argument("--tokens", action="store_true", help="重看最初的token演示")
    parser.add_argument("--task", help="替换工具/Agent任务")
    args = parser.parse_args()
    if args.replay:
        record = json.loads(args.replay.read_text(encoding="utf-8"))
        if record.get("kind") != "live-api-recording" or record.get("stage") != stage:
            parser.error("需要与当前Tag一致的真实录制文件")
        print(f"[回放 REPLAY · {record['stage']} · {record['recorded_at']}]\n不请求API、不执行工具。")
        print(record["transcript"])
        return
    if not 0 <= args.temperature <= 2 or not 1 <= args.steps <= 64 or not 1 <= args.max_iterations <= 12:
        parser.error("temperature需0—2；steps需1—64；max-iterations需1—12")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        parser.error("先 source ~/.config/api-keys/llm.env；需要 DEEPSEEK_API_KEY")
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
                  "source_sha256": hashlib.sha256(Path(__file__).with_name("agent.py").read_bytes()).hexdigest(),
                  "transcript": transcript.getvalue()}
        args.record.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[已录制] {args.record}")
