"""v2：用 system/user/assistant messages 表示多轮对话。"""
import os
import sys

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TEMPERATURE = 0


def main(client):
    messages = [{"role": "system", "content": "你是简洁的中文实验助手。不知道的信息请说不知道。"}]
    while True:
        try:
            question = input("$ ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question.strip():
            continue
        messages.append({"role": "user", "content": question})
        print(f"Messages → {messages}")
        response = client.chat.completions.create(
            model=MODEL, messages=messages, temperature=TEMPERATURE, max_tokens=500,
            extra_body={"thinking": {"type": "disabled"}})
        choice = response.choices[0]
        if choice.finish_reason != "stop":
            raise RuntimeError("回复被截断或异常停止")
        answer = choice.message.content or ""
        print(f"助手：{answer}")
        messages.append({"role": "assistant", "content": answer})


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
