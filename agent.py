"""v0：一次原始 Completion，逐位置查看真实 logprobs。"""
import math
from common import call, run, inputs


def complete_tokens(client, args, prompt):
    context = prompt
    response = call(client.completions.create, model=args.model,
                    prompt=context, max_tokens=args.steps,
                    temperature=args.temperature, logprobs=5)
    choice = response.choices[0]
    probs = choice.logprobs
    if not probs or not probs.top_logprobs:
        raise RuntimeError("API没有返回logprobs；请勿用编造概率代替")
    print("Pr[token | context]；以下逐位置展开一次真实响应（不是每Token发一次请求）。")
    print("只展示top-k候选；exp(logprob)不重新归一化；-9999是极低概率哨兵。")
    for token, logprob, candidates in zip(probs.tokens, probs.token_logprobs, probs.top_logprobs):
        print(f"\n上下文：{context!r}")
        for candidate, lp in sorted(candidates.items(), key=lambda pair: pair[1], reverse=True):
            print(f"  候选 {candidate!r:14} logprob={lp:9.4f} p={format(math.exp(lp), '.4%') if lp > -9999 else '低于API显示范围'}")
        print(f"→ 生成 {token!r} p={math.exp(logprob):.4%}")
        context += token
    print(f"\n完整续写：{prompt}{choice.text}\n停止原因：{choice.finish_reason}")


def token_demo(client, args):
    for prompt in inputs(args, ["牛顿第二定律告诉我们，"], "续写前缀（:quit退出）：", args.prompt):
        if prompt.strip() == ":reset":
            print("v0每次独立续写，没有需要清空的对话历史。")
            continue
        complete_tokens(client, args, prompt)


def main(client, args):
    token_demo(client, args)


if __name__ == "__main__":
    run(main, "v0-token")
