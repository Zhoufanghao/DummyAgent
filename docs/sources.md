# 教学来源与事实边界

核查日期：2026-10-15（北京时间）。只采用官方文档、官方发布文章与模型发布者的文件。新闻作为有日期的历史案例使用，不把发布时的功能、套餐或默认设置说成今天所有版本的情况。

## 课堂使用的三个案例

| 案例及原始日期 | 官方来源 | 课堂采用的事实 | 对应代码机制 | 不作出的推断 |
| --- | --- | --- | --- | --- |
| Codex 研究预览，2025-05-16 | [OpenAI: Introducing Codex](https://openai.com/index/introducing-codex/) | 发布材料描述读取与修改代码、运行命令和测试、提供执行证据的编程智能体 | 工具执行、把测试结果放回上下文、继续迭代；对应 v3—v5 | 不声称课堂程序等同于完整产品；不引用已过时的套餐、价格与默认联网状态。原文现已明确标注发布文章过时 |
| MCP 开源发布，2024-11-25 | [Anthropic: Introducing the Model Context Protocol](https://www.anthropic.com/news/model-context-protocol) | 以开放协议连接 AI 应用与外部数据、工具 | 将 v3 中各自编写的工具接入方式放进统一协议；课堂程序未实现 MCP | MCP 本身不提供本课的任务循环、任务目标或可靠性保证 |
| 浏览器提示注入防护进展，2025-11-24 | [Anthropic: Mitigating the risk of prompt injections in browser use](https://www.anthropic.com/news/prompt-injection-defenses) | 外部内容中的恶意指令可能影响 Agent 后续动作，防护仍未彻底解决该问题 | 工具结果进入上下文后仍须保留信任边界；执行权限由应用与沙箱约束 | 文中的邮件外泄场景是解释性假设例子，不是该文披露的真实事故；不把某项内部评测的成功率推广成通用安全保证 |

讲述配额：Codex 约 75 秒、MCP 约 65 秒、提示注入约 80 秒，留 20 秒切换。无需在四分钟中补讲其他产品。

## API 与实现依据

**当前默认模型核验**：2026-10-15 查阅 [DeepSeek 官方更新](https://api-docs.deepseek.com/updates/) 中 2026-09-10 的发布记录，`deepseek-flash` 对应 DeepSeek-V4.1-Flash。本项目实时调用默认采用该 API ID。它是可变别名，不是固定 checkpoint；开课前重新核查并保留每次真实响应中的模型字段。下文 V3 模板是有意固定的历史教学对照，不用于断言 V4.1 的内部格式。

- [DeepSeek: Your First API Call](https://api-docs.deepseek.com/)：OpenAI SDK 可通过配置 DeepSeek 的 `base_url` 与密钥访问 DeepSeek。SDK 名称不决定实际模型提供方。
- [DeepSeek: FIM Completion API (Beta)](https://api-docs.deepseek.com/api/create-completion/)：本课 Stage 0 使用 `/completions` 与 Beta 地址；`logprobs` 返回采样 token 与候选项的对数概率。只传前缀、不传 `suffix` 时用于续写展示。Completion接口形式不意味着调用了未经指令训练的基础模型；本课仍使用当前Flash模型。模型名与能力必须在备课时重新验证，不能永久依赖某个别名。
- [DeepSeek: Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)：核对 messages、roles、tools、tool_calls、tool_call_id 等字段。工具调用返回的是待执行请求，执行与结果回填由客户端完成。
- [MCP specification, revision 2025-06-18: Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)：工具描述、列举与调用协议，以及参数验证、访问控制、超时与使用记录。此链接固定到一个规范版本，不声称它是永久的最新版本。

`exp(logprob)` 是对 API 返回值的直接转换。top-k 候选只覆盖词表的一部分，显示项概率通常不加总为 100%；不得将这几个候选重新归一化后标成 API 原始概率。服务端没有在这些文档中完整说明所有采样内部细节，不声称返回值必然是温度变换前或后的整词表分布。

Temperature 用于说明采样分布的尖锐或平缓；较低温度并不保证跨请求、跨版本逐字一致，也不保证事实或计算正确。当前 Chat 文档还规定某些采样参数在 thinking 模式中不生效，备课应采用已经实测的非思考调用配置。

本项目真实 Completion 测试中，`temperature=0` 可出现所选 token 的 `logprob=0`、其他项 `-9999` 的退化显示；`-9999` 按 API 哨兵值呈现，不渲染成精确的 0% 或当作未调整的原始模型概率。课堂正常候选列表优先展示已验证的 `temperature=0.8` 记录，0 的返回作为采样配置与接口语义的对照。

## 唯一用于课堂的公开 Chat Template

模型：**deepseek-ai/DeepSeek-V3，公开 checkpoint**。示例不是从当前托管 API 中读出的内部提示。

- [官方模型文件，固定版本 tokenizer_config.json](https://huggingface.co/deepseek-ai/DeepSeek-V3/blob/d990f047635ab4866b112caff006a18ce221605f/tokenizer_config.json)
- [该模型文件所在提交，2024-12-26](https://huggingface.co/deepseek-ai/DeepSeek-V3/commit/d990f047635ab4866b112caff006a18ce221605f)

仓库中的 `data/deepseek_v3_chat_template.jinja` 从该固定版本 JSON 的 `chat_template` 字段提取；文件尾额外保留一个换行用于文本编辑。下载 JSON 的 SHA256 为 `637bcd1a08cf7c772ce6a383196b22930921c79c3c73223c5afc0c7f41545546`；字段原始 UTF-8 字节的 SHA256（不含本地文件尾换行）为 `3b8267e54b67df6500f231ffa969955cc9d26b3444a291ced4eb96ca7d3ca1ea`。`python chat_template_demo.py` 校验字段哈希，并用标准库重现普通 system/user/assistant 文本分支；它不执行完整 Jinja 模板，也不实现工具和思考分支。

对仅含 system、user 和普通 assistant 文本的消息，文件中的 Jinja 模板会在开头输出 BOS 与 system 正文，再以 `<｜User｜>`、`<｜Assistant｜>` 标记相应消息，以 `<｜end▁of▁sentence｜>` 结束普通 assistant 回复；`add_generation_prompt=True` 会追加 assistant 开始标记。system 正文在本例中没有单独的 system 特殊 token。

以下是按该公开模板得到的**文本序列化示例**；只是为阅读而换行，换行本身不代表通用边界规则：

```text
<｜begin▁of▁sentence｜>你是实验助手。
<｜User｜>实验编号是 A102。
<｜Assistant｜>已记下。<｜end▁of▁sentence｜>
<｜User｜>实验编号是什么？
<｜Assistant｜>
```

这里的全角竖线与下划块属于官方可见 token 字面形式，不要换成 ASCII 相似字符。它们不是模型无关的标准。这里不混入 Llama、Qwen 或其他模型的标记，也不展开工具或思考分支的模板。

API 的 `messages` 是应用层协议；服务端可能采用不同的模板、版本与额外包装。本课 API 实际返回的模型名应以录制文件为准，不能仅因 API 别名来自 DeepSeek，就断言其内部仍使用这个公开 V3 checkpoint 的序列化形式。

## 演示证据标识

- **LIVE**：本次确实请求了 API，终端应能关联原始响应记录。
- **REPLAY**：读取已经录制的真实响应；应展示录制时间、模型与原始数据来源。若没有真实录制，必须报缺失，不能生成貌似实时的结果。
- **示意**：讲义中的结构示例、伪代码或可能路径；不能冒充 API 输出。
- **本地确定性检查**：固定 CSV 的统计、工具参数校验和沙箱拒绝行为，可独立运行验证。它们不证明 LLM 每次会采用同一行动路径。

课堂可见的 action/tool/result 日志是应用公开记录的行为证据，不是模型隐藏推理链。不要将其标题写成“完整思考过程”。
