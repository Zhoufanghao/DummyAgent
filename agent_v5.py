"""v5：用 Bash 执行任务，再把真实结果交回模型。"""
import json
import os
import subprocess
from openai import OpenAI
from prompt_toolkit import prompt

THINKING = True
BASH_TIMEOUT = 60
SYSTEM_PROMPT = "使用 bash 完成当前目录中的任务，中文回复。"

BASH_TOOL = {"type": "function", "function": {
    "name": "bash", "description": "执行 Bash 命令，返回退出码和输出。",
    "parameters": {"type": "object", "properties": {
        "command": {"type": "string"}}, "required": ["command"]}}}

def run_bash(command):
    print(f"\n$ {command}", flush=True)
    try:
        result = subprocess.run(
            ["bash", "-c", command], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", timeout=BASH_TIMEOUT)
        output = f"exit_code: {result.returncode}\n{result.stdout}"
    except subprocess.TimeoutExpired:
        output = "命令超时。"
    print(output, flush=True)
    return output

def main():
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com/beta", timeout=45, max_retries=1)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        task = prompt("$ ")
        if not task.strip():
            continue
        messages.append({"role": "user", "content": task})
        while True:
            message = client.chat.completions.create(
                model="deepseek-flash", messages=messages, tools=[BASH_TOOL],
                max_tokens=8192,
                extra_body={"thinking": {"type": "enabled" if THINKING else "disabled"}}).choices[0].message
            messages.append(message)
            if THINKING:
                print("思考：", message.reasoning_content)
            if not message.tool_calls:
                print("助手：", message.content)
                break
            for tool_call in message.tool_calls:
                arguments = json.loads(tool_call.function.arguments)
                output = run_bash(arguments["command"])
                messages.append({"role": "tool", "tool_call_id": tool_call.id,
                                 "content": output})

if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print()
