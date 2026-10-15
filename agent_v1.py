"""v1：保存文本 history，每轮重新提交双方对话。"""
import os
from openai import OpenAI
from prompt_toolkit import prompt

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TEMPERATURE = 0


def main():
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com/beta", timeout=45, max_retries=1)
    history = "请续写下面的中文对话，只回答最后一个问题；不知道的信息请说不知道。\n"
    while True:
        question = prompt("$ ")
        if not question.strip():
            continue
        history += f"用户：{question}\n助手："
        print(f"提交给API的文本：{history!r}")
        response = client.completions.create(
            model=MODEL, prompt=history, max_tokens=120,
            temperature=TEMPERATURE, stop=["\n用户："])
        answer = response.choices[0].text.strip()
        print(f"助手：{answer}")
        history += answer + "\n"


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print()
