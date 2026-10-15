"""v1：保持文本 Completion，只增加应用程序维护的 history。"""
import math
from common import call, run


def token_demo(client, args):
    context = args.prompt
    response = call(client.completions.create, model=args.model,
                    prompt=context, max_tokens=args.steps,
                    temperature=args.temperature, logprobs=5)
    choice = response.choices[0]
    probs = choice.logprobs
    if not probs or not probs.top_logprobs:
        raise RuntimeError("API没有返回logprobs；请勿用编造概率代替")
    print("P(x_t | x_<t)；以下逐位置展开一次真实响应（不是每Token发一次请求）。")
    print("只展示top-k候选；exp(logprob)不重新归一化；-9999是极低概率哨兵。")
    for token, logprob, candidates in zip(probs.tokens, probs.token_logprobs, probs.top_logprobs):
        print(f"\n上下文：{context!r}")
        for candidate, lp in sorted(candidates.items(), key=lambda pair: pair[1], reverse=True):
            print(f"  候选 {candidate!r:14} logprob={lp:9.4f} p={format(math.exp(lp), '.4%') if lp > -9999 else '低于API显示范围'}")
        print(f"→ 生成 {token!r} p={math.exp(logprob):.4%}")
        context += token
    print(f"\n完整续写：{args.prompt}{choice.text}\n停止原因：{choice.finish_reason}")


def text_reply(client, args, prompt):
    print(f"提交给API的文本：{prompt!r}")
    response = call(client.completions.create, model=args.model, prompt=prompt,
                    max_tokens=120, temperature=args.temperature, stop=["\n用户："])
    answer = response.choices[0].text.strip()
    print(f"助手：{answer}")
    return answer


def main(client, args):
    if args.tokens:
        return token_demo(client, args)
    instruction = "请续写下面的中文对话，只回答最后一个问题；不知道的信息请说不知道。\n"
    questions = ["我的实验编号是 A102。", "我的实验编号是什么？"]
    print("\n[对照：两次独立调用，没有history]")
    for question in questions:
        text_reply(client, args, instruction + f"用户：{question}\n助手：")
    print("\n[新增：由应用程序保存并重新提交history]")
    history = instruction
    for question in questions:
        history += f"用户：{question}\n助手："
        answer = text_reply(client, args, history)
        history += answer + "\n"
    if "A102" not in answer:
        raise RuntimeError("本次未成功恢复实验编号，可重试或使用已验证回放")


if __name__ == "__main__":
    run(main, "v1-memory")
