"""v2：把文本history改成有角色的messages，默认自由多轮。"""
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


def chat_demo(client, args):
    system = {"role": "system", "content": "你是简洁的中文实验助手。不知道的信息请说不知道。"}
    messages = [system]
    examples = ["我的实验编号是 A102。", "我的实验编号是什么？"]
    for question in inputs(args, examples, "你（:quit退出，:reset清空历史）：", args.task):
        if question.strip() == ":reset":
            messages = [system]
            print("已清空对话历史。")
            continue
        messages.append({"role": "user", "content": question})
        print(f"Messages → {messages}")
        response = call(client.chat.completions.create, model=args.model,
                        messages=messages, temperature=args.temperature, max_tokens=500,
                        extra_body={"thinking": {"type": "disabled"}})
        if response.choices[0].finish_reason != "stop":
            raise RuntimeError("回复未正常完成，请缩短输入或使用回放")
        answer = response.choices[0].message.content
        print(f"助手：{answer}")
        messages.append({"role": "assistant", "content": answer})


def main(client, args):
    if args.tokens:
        return token_demo(client, args)
    chat_demo(client, args)


if __name__ == "__main__":
    run(main, "v2-chat")
