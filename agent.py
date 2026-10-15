"""v3：模型生成Tool Call，Python验证参数并真正执行。"""
import json
import math
from common import call, run
from tools import TOOLS, execute


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


def chat_demo(client, args):
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


def main(client, args):
    if args.tokens:
        return token_demo(client, args)
    if args.chat:
        return chat_demo(client, args)
    task = args.task or "请计算(12345 * 6789) / (17 + 29)，简短回答。"
    messages = [{"role": "system", "content": "你是中文计算助手，使用工具时以工具结果为准。"},
                {"role": "user", "content": task}]
    print(f"用户：{task}")
    plain = call(client.chat.completions.create, model=args.model, messages=messages,
                 temperature=args.temperature, max_tokens=220,
                 extra_body={"thinking": {"type": "disabled"}})
    print(f"[不使用工具] {plain.choices[0].message.content}")
    print("Tool Schema →", json.dumps(TOOLS, ensure_ascii=False))
    response = call(client.chat.completions.create, model=args.model, messages=messages,
                    tools=TOOLS, tool_choice="required", temperature=args.temperature,
                    max_tokens=300, extra_body={"thinking": {"type": "disabled"}})
    message = response.choices[0].message
    if response.choices[0].finish_reason != "tool_calls" or not message.tool_calls:
        raise RuntimeError("未得到完整Tool Call")
    if len(message.tool_calls) > 4:
        raise RuntimeError("工具请求数量超限")
    messages.append(message.model_dump(include={"role", "content", "tool_calls"}, exclude_none=True))
    for tool_call in message.tool_calls:
        print("LLM → Tool Call：", tool_call.function.name, tool_call.function.arguments)
        result = execute(tool_call)  # 真正执行在这里；模型只输出名称和参数。
        print("Python Function → Tool Result：", result)
        messages.append({"role": "tool", "tool_call_id": tool_call.id,
                         "content": json.dumps(result, ensure_ascii=False)})
    final = call(client.chat.completions.create, model=args.model, messages=messages,
                 temperature=args.temperature, max_tokens=220,
                 extra_body={"thinking": {"type": "disabled"}})
    if final.choices[0].finish_reason != "stop":
        raise RuntimeError("最终回答被截断")
    print("LLM → 最终回答：", final.choices[0].message.content)


if __name__ == "__main__":
    run(main, "v3-tools")
