"""v4：每个用户任务进入显式Agent Loop；跨任务保留上下文。"""
import json
import math
from common import call, run, inputs
from tools import TOOLS, execute


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


def calculator_demo(client, args):
    system = {"role": "system", "content": "你是中文计算助手，需要计算时使用calculator，以实际工具结果为准。"}
    messages = [system]
    examples = ["先用calculator计算(12345 * 6789) / (17 + 29)，等结果返回后，再用calculator把该结果除以3。每轮只请求一次计算，最后简短汇报。"]
    print("Tool Schema →", json.dumps(TOOLS, ensure_ascii=False))
    for task in inputs(args, examples, "你（:quit退出，:reset清空历史）：", args.task):
        if task.strip() == ":reset":
            messages = [system]
            print("已清空对话历史。")
            continue
        messages.append({"role": "user", "content": task})
        print(f"用户：{task}")
        if args.demo:
            plain = call(client.chat.completions.create, model=args.model, messages=messages,
                         temperature=args.temperature, max_tokens=220,
                         extra_body={"thinking": {"type": "disabled"}})
            print(f"[不使用工具] {plain.choices[0].message.content}")
        try:
            agent_loop(client, args, messages)
        except RuntimeError as error:
            if args.demo or args.task is not None:
                raise
            print(f"[本任务停止] {error}；可继续输入下一个任务。")


def agent_loop(client, args, messages):
    iteration = 0
    while iteration < args.max_iterations:
        iteration += 1
        print(f"\n[Agent Loop {iteration}/{args.max_iterations}] 调用LLM")
        response = call(client.chat.completions.create, model=args.model, messages=messages,
                        tools=TOOLS, tool_choice="auto", temperature=args.temperature,
                        max_tokens=1600, extra_body={"thinking": {"type": "disabled"}})
        choice = response.choices[0]
        message = choice.message
        if not message.tool_calls:
            if choice.finish_reason != "stop":
                raise RuntimeError("LLM被截断或异常停止，不能算作任务完成")
            print("LLM → 最终回答：", message.content)
            messages.append({"role": "assistant", "content": message.content or ""})
            return
        if choice.finish_reason != "tool_calls" or len(message.tool_calls) > 4:
            raise RuntimeError("Tool Call不完整或数量超限")
        messages.append(message.model_dump(include={"role", "content", "tool_calls"}, exclude_none=True))
        for tool_call in message.tool_calls:
            print("LLM → Tool Call：", tool_call.function.name, tool_call.function.arguments)
            result = execute(tool_call)  # 外部执行，再把观察结果放回上下文。
            print("Python Function → Tool Result：", result)
            messages.append({"role": "tool", "tool_call_id": tool_call.id,
                             "content": json.dumps(result, ensure_ascii=False)})
        # 下一轮模型现在能看到刚才的结果；下一条用户任务重新计数。
    raise RuntimeError("达到最大迭代次数，任务尚未确认完成")


def main(client, args):
    if args.tokens:
        return token_demo(client, args)
    if args.chat:
        return chat_demo(client, args)
    calculator_demo(client, args)


if __name__ == "__main__":
    run(main, "v4-agent-loop")
