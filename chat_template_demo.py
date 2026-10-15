"""展示公开 DeepSeek-V3 模板的普通文本消息子集，不访问 API。

原文：deepseek-ai/DeepSeek-V3 的 tokenizer_config.json 的 chat_template 字段。
固定版本：d990f047635ab4866b112caff006a18ce221605f（2024-12-26）。
来源：https://huggingface.co/deepseek-ai/DeepSeek-V3/blob/d990f047635ab4866b112caff006a18ce221605f/tokenizer_config.json
data/deepseek_v3_chat_template.jinja 保存完整 Jinja 字段文本；尾部允许一个文件换行。
官方 JSON SHA256：637bcd1a08cf7c772ce6a383196b22930921c79c3c73223c5afc0c7f41545546
提取字段 SHA256：3b8267e54b67df6500f231ffa969955cc9d26b3444a291ced4eb96ca7d3ca1ea
这里仅重现 system/user/普通 assistant 文本分支，不执行 Jinja，不处理 tool/thinking。
该公开 checkpoint 模板不能证明当前托管 API 使用完全相同的内部序列化。
"""
import hashlib
import json
from pathlib import Path


def serialize(messages, add_generation_prompt=True):
    """对应随附模板的纯文本三角色分支；拒绝本课未实现的分支。"""
    for message in messages:
        if (set(message) != {"role", "content"}
                or message["role"] not in {"system", "user", "assistant"}
                or not isinstance(message["content"], str)):
            raise ValueError("只接受 role/content 两字段的 system/user/assistant 文本消息")
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    text = "<｜begin▁of▁sentence｜>" + system
    for message in messages:
        if message["role"] == "user":
            text += "<｜User｜>" + message["content"]
        elif message["role"] == "assistant":
            text += "<｜Assistant｜>" + message["content"] + "<｜end▁of▁sentence｜>"
    if add_generation_prompt:
        text += "<｜Assistant｜>"
    return text


def main():
    template = Path(__file__).parent / "data" / "deepseek_v3_chat_template.jinja"
    raw = template.read_text(encoding="utf-8").removesuffix("\n")
    digest = hashlib.sha256(raw.encode()).hexdigest()
    if digest != "3b8267e54b67df6500f231ffa969955cc9d26b3444a291ced4eb96ca7d3ca1ea":
        raise ValueError("随附模板已变化，请重新核对官方固定版本和子集实现")
    print("公开 DeepSeek-V3 模板；不是当前托管 API 的内部提示抓取。")
    print("固定 revision：d990f047635ab4866b112caff006a18ce221605f")
    print("完整 chat_template UTF-8 SHA256（不含文件尾换行）：", digest)
    messages = [
        {"role": "system", "content": "你是实验助手。"},
        {"role": "user", "content": "实验编号是 A102。"},
        {"role": "assistant", "content": "已记下。"},
        {"role": "user", "content": "实验编号是什么？"},
    ]
    print("\n应用层 Messages：")
    print(json.dumps(messages, ensure_ascii=False, indent=2))
    print("\n严格串接结果（此行没有为阅读额外插入换行）：")
    print(serialize(messages))
    print("\nRole 对应的可见特殊标记有助于表达边界；system 正文在本模板中直接接在 BOS 后。")


if __name__ == "__main__":
    main()
