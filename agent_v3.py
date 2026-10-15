"""v3：模型请求工具，Python 执行，回填结果后回答一次。"""
import json
import os
from openai import OpenAI
from prompt_toolkit import prompt

CALCULATOR_TOOL = {"type": "function", "function": {
    "name": "calculator", "description": "计算算术表达式。",
    "parameters": {"type": "object", "properties": {
        "expression": {"type": "string", "description": "算术表达式，如(12+3)*4；乘方使用**"}},
        "required": ["expression"]}}}

def calculator(expression):
    return eval(expression)

def main():
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com/beta", timeout=45, max_retries=1)
    messages = [{"role": "system", "content": "你是中文计算助手，需要计算时使用calculator，以实际工具结果为准。"}]
    while True:
        task = prompt("$ ")
        if not task.strip():
            continue
        messages.append({"role": "user", "content": task})
        message = client.chat.completions.create(
            model="deepseek-flash", messages=messages, tools=[CALCULATOR_TOOL],
            max_tokens=500,
            extra_body={"thinking": {"type": "disabled"}}).choices[0].message
        messages.append(message)
        if message.tool_calls:
            for tool_call in message.tool_calls:
                print("LLM → Tool Call：", tool_call.function.name, tool_call.function.arguments)
                result = calculator(**json.loads(tool_call.function.arguments))
                print("Python → Tool Result：", result)
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": str(result)})
            message = client.chat.completions.create(
                model="deepseek-flash", messages=messages, max_tokens=500,
                extra_body={"thinking": {"type": "disabled"}}).choices[0].message
            messages.append(message)
        print("助手：", message.content)

if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print()
