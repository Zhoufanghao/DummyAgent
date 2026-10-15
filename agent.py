"""v2：把文本history改成有角色的messages。"""
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


def main(client, args):
    if args.tokens:
        return token_demo(client, args)
    messages = [{"role": "system", "content": "你是简洁的中文实验助手。不知道的信息请说不知道。"}]
    questions = iter(["我的实验编号是 A102。", "我的实验编号是什么？"])
    while True:
        try:
            question = next(questions) if args.demo else input("你（:quit退出）：")
        except (StopIteration, EOFError):
            break
        if question == ":quit":
            break
        messages.append({"role": "user", "content": question})
        print(f"Messages → {messages}")
        response = call(client.chat.completions.create, model=args.model,
                        messages=messages, temperature=args.temperature, max_tokens=160,
                        extra_body={"thinking": {"type": "disabled"}})
        if response.choices[0].finish_reason != "stop":
            raise RuntimeError("回复未正常完成，请缩短输入或使用回放")
        answer = response.choices[0].message.content
        print(f"助手：{answer}")
        messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    run(main, "v2-chat")
