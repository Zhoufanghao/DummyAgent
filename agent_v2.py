"""v2：用 system/user/assistant messages 表示多轮对话。"""
import os
from openai import OpenAI
from prompt_toolkit import prompt

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TEMPERATURE = 0


def main():
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com/beta", timeout=45, max_retries=1)
    messages = [{"role": "system", "content": "你是简洁的中文实验助手。不知道的信息请说不知道。"}]
    while True:
        question = prompt("$ ")
        if not question.strip():
            continue
        messages.append({"role": "user", "content": question})
        print(f"Messages → {messages}")
        response = client.chat.completions.create(
            model=MODEL, messages=messages, temperature=TEMPERATURE, max_tokens=500,
            extra_body={"thinking": {"type": "disabled"}})
        answer = response.choices[0].message.content
        print(f"助手：{answer}")
        messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print()
