"""v4：工具结果反馈给模型，每个任务进入显式 Agent Loop。"""
import json
import os
import sys
from tools import TOOLS, execute

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TEMPERATURE = 0
MAX_ITERATIONS = 100


def agent_loop(client, messages):
    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n[Agent Loop {iteration}/{MAX_ITERATIONS}] 调用LLM")
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto",
            temperature=TEMPERATURE, max_tokens=1600,
            extra_body={"thinking": {"type": "disabled"}})
        choice = response.choices[0]
        message = choice.message
        if not message.tool_calls:
            if choice.finish_reason != "stop":
                raise RuntimeError("LLM被截断或异常停止，不能算作任务完成")
            print("LLM → 最终回答：", message.content)
            messages.append({"role": "assistant", "content": message.content or ""})
            return
        if choice.finish_reason != "tool_calls" or len(message.tool_calls) > 4:
            raise RuntimeError("Tool Call不完整或数量超限")
        messages.append(message.model_dump(include={"role", "content", "tool_calls"}, exclude_none=True))
        for tool_call in message.tool_calls:
            print("LLM → Tool Call：", tool_call.function.name, tool_call.function.arguments)
            result = execute(tool_call)
            print("Python Function → Tool Result：", result)
            messages.append({"role": "tool", "tool_call_id": tool_call.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    raise RuntimeError("达到最大迭代次数，任务尚未确认完成")


def main(client):
    messages = [{"role": "system", "content": "你是中文计算助手，需要计算时使用calculator，以实际工具结果为准。"}]
    print("Tool Schema →", json.dumps(TOOLS, ensure_ascii=False))
    while True:
        try:
            task = input("$ ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not task.strip():
            continue
        messages.append({"role": "user", "content": task})
        try:
            agent_loop(client, messages)
        except RuntimeError as error:
            print(f"[本任务停止] {error}；可继续输入下一个任务。")


def cli():
    if len(sys.argv) != 1:
        raise SystemExit("用法：python agent.py（不接受命令行参数）")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("请先设置 DEEPSEEK_API_KEY")
    from openai import APIError, OpenAI
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com/beta", timeout=45, max_retries=1)
    try:
        main(client)
    except KeyboardInterrupt:
        print()
    except APIError as error:
        raise SystemExit(f"API失败：{type(error).__name__}，HTTP {getattr(error, 'status_code', None)}") from None
    except (ValueError, RuntimeError, OSError) as error:
        raise SystemExit(f"运行失败：{error}") from None


if __name__ == "__main__":
    cli()
