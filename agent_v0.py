"""v0：文本续写与真实 token 概率。"""
import math
import os
from openai import OpenAI
from prompt_toolkit import prompt

def main():
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com/beta", timeout=45, max_retries=1)
    while True:
        prefix = prompt("$ ")
        if not prefix.strip():
            continue
        choice = client.completions.create(
            model="deepseek-flash", prompt=prefix, max_tokens=12, logprobs=5).choices[0]
        logprobs = choice.logprobs
        context = prefix
        print("Pr[token | context]；top-k 候选概率不重新归一化。")
        for token, logprob, candidates in zip(
                logprobs.tokens, logprobs.token_logprobs, logprobs.top_logprobs):
            print(f"\n上下文：{context!r}")
            for candidate, lp in candidates.items():
                probability = f"{math.exp(lp):.4%}" if lp > -9999 else "低于API显示范围"
                print(f"  候选 {candidate!r} logprob={lp:.4f} p={probability}")
            print(f"→ 生成 {token!r} p={math.exp(logprob):.4%}")
            context += token
        print(f"\n完整续写：{prefix}{choice.text}")

if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print()
