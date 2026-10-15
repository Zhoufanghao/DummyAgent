"""v1：应用保存文本 history，每轮重新提交完整对话。"""
import os
import sys

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TEMPERATURE = 0


def main(client):
    history = "请续写下面的中文对话，只回答最后一个问题；不知道的信息请说不知道。\n"
    while True:
        try:
            question = input("$ ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question.strip():
            continue
        history += f"用户：{question}\n助手："
        print(f"提交给API的文本：{history!r}")
        response = client.completions.create(
            model=MODEL, prompt=history, max_tokens=120,
            temperature=TEMPERATURE, stop=["\n用户："])
        choice = response.choices[0]
        if choice.finish_reason != "stop":
            raise RuntimeError("回复被截断或异常停止")
        answer = choice.text.strip()
        print(f"助手：{answer}")
        history += answer + "\n"


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
