"""v4：把工具结果反馈给模型，继续决定下一步。"""
import json
import os
from openai import OpenAI

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TEMPERATURE = 0
CALCULATOR_TOOL = {"type": "function", "function": {
    "name": "calculator", "description": "计算算术表达式。",
    "parameters": {"type": "object", "properties": {
        "expression": {"type": "string", "description": "算术表达式，如(12+3)*4；^或**表示乘方"}},
        "required": ["expression"]}}}


def calculator(expression):
    return eval(expression.replace("^", "**"))


def main():
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com/beta", timeout=45, max_retries=1)
    messages = [{"role": "system", "content": "你是中文计算助手，需要计算时使用calculator，以实际工具结果为准。"}]
    while True:
        task = input("$ ")
        if not task.strip():
            continue
        messages.append({"role": "user", "content": task})
        while True:
            message = client.chat.completions.create(
                model=MODEL, messages=messages, tools=[CALCULATOR_TOOL],
                temperature=TEMPERATURE, max_tokens=1600,
                extra_body={"thinking": {"type": "disabled"}}).choices[0].message
            messages.append(message.model_dump(include={"role", "content", "tool_calls"}, exclude_none=True))
            if not message.tool_calls:
                print("助手：", message.content)
                break
            for tool_call in message.tool_calls:
                print("LLM → Tool Call：", tool_call.function.name, tool_call.function.arguments)
                result = calculator(**json.loads(tool_call.function.arguments))
                print("Python → Tool Result：", result)
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": str(result)})


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print()
