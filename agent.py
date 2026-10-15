"""v0：原始 Completion，逐位置查看真实 logprobs。"""
import math
import os
import sys

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TEMPERATURE = 0
TOKEN_STEPS = 12


def complete_tokens(client, prompt):
    response = client.completions.create(
        model=MODEL, prompt=prompt, max_tokens=TOKEN_STEPS,
        temperature=TEMPERATURE, logprobs=5)
    choice = response.choices[0]
    probabilities = choice.logprobs
    if not probabilities or not probabilities.top_logprobs:
        raise RuntimeError("API没有返回logprobs；请勿用编造概率代替")
    print("Pr[token | context]；以下逐位置展开一次真实响应（不是每Token发一次请求）。")
    print("只展示top-k候选；exp(logprob)不重新归一化；-9999是极低概率哨兵。")
    context = prompt
    for token, logprob, candidates in zip(
            probabilities.tokens, probabilities.token_logprobs, probabilities.top_logprobs):
        print(f"\n上下文：{context!r}")
        for candidate, lp in sorted(candidates.items(), key=lambda pair: pair[1], reverse=True):
            probability = format(math.exp(lp), '.4%') if lp > -9999 else '低于API显示范围'
            print(f"  候选 {candidate!r:14} logprob={lp:9.4f} p={probability}")
        print(f"→ 生成 {token!r} p={math.exp(logprob):.4%}")
        context += token
    print(f"\n完整续写：{prompt}{choice.text}\n停止原因：{choice.finish_reason}")


def main(client):
    while True:
        try:
            prompt = input("$ ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if prompt.strip():
            complete_tokens(client, prompt)


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
