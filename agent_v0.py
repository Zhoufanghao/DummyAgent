"""v0：文本续写与真实 token 概率。"""
import math
import os
from openai import OpenAI

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TEMPERATURE = 0
TOKEN_STEPS = 12


def main():
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com/beta", timeout=45, max_retries=1)
    while True:
        prompt = input("$ ")
        if not prompt.strip():
            continue
        choice = client.completions.create(
            model=MODEL, prompt=prompt, max_tokens=TOKEN_STEPS,
            temperature=TEMPERATURE, logprobs=5).choices[0]
        context = prompt
        print("Pr[token | context]；top-k 候选概率不重新归一化。")
        for token, logprob, candidates in zip(
                choice.logprobs.tokens, choice.logprobs.token_logprobs, choice.logprobs.top_logprobs):
            print(f"\n上下文：{context!r}")
            for candidate, lp in sorted(candidates.items(), key=lambda pair: pair[1], reverse=True):
                probability = format(math.exp(lp), ".4%") if lp > -9999 else "低于API显示范围"
                print(f"  候选 {candidate!r:14} logprob={lp:9.4f} p={probability}")
            print(f"→ 生成 {token!r} p={math.exp(logprob):.4%}")
            context += token
        print(f"\n完整续写：{prompt}{choice.text}")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print()
