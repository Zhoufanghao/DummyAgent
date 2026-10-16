# 教学来源与事实边界

teach 文档核对日期：2026-10-16（北京时间）。Completion 与思考模式说明沿用本日此前的官方文档核对，本轮未重新浏览；v0 简化后已按最终源码重新请求 API，v3/v4 新题未请求模型。新闻、模型别名和公开模板沿用 2026-10-15 的既往核查记录。只采用官方文档、官方发布文章与模型发布者的文件。新闻作为有日期的历史案例使用，不把发布时的功能、套餐或默认设置说成今天所有版本的情况。

## 课堂使用的三个案例

| 案例及原始日期 | 官方来源 | 课堂采用的事实 | 对应代码机制 | 不作出的推断 |
| --- | --- | --- | --- | --- |
| Codex 研究预览，2025-05-16 | [OpenAI: Introducing Codex](https://openai.com/index/introducing-codex/) | 发布材料描述读取与修改代码、运行命令和测试、提供执行证据的编程智能体 | 工具执行、把测试结果放回上下文、继续迭代；对应 v3—v5 | 不声称课堂程序等同于完整产品；不引用已过时的套餐、价格与默认联网状态。原文现已明确标注发布文章过时 |
| MCP 开源发布，2024-11-25 | [Anthropic: Introducing the Model Context Protocol](https://www.anthropic.com/news/model-context-protocol) | 以开放协议连接 AI 应用与外部数据、工具 | 将 v3 中各自编写的工具接入方式放进统一协议；课堂程序未实现 MCP | MCP 本身不提供本课的任务循环、任务目标或可靠性保证 |
| 浏览器提示注入防护进展，2025-11-24 | [Anthropic: Mitigating the risk of prompt injections in browser use](https://www.anthropic.com/news/prompt-injection-defenses) | 外部内容中的恶意指令可能影响 Agent 后续动作，防护仍未彻底解决该问题 | 工具结果进入上下文后仍须保留信任边界；本课简化脚本直接执行 Bash，实际权限由运行环境决定 | 文中的邮件外泄场景是解释性假设例子，不是该文披露的真实事故；不把某项内部评测的成功率推广成通用安全保证 |

讲述配额：第 14 页 40:00—42:00，Codex 与 MCP 各约 60 秒；第 15 页 42:00—44:00 讲提示注入与执行权限。不扩展其他产品。

## API 与实现依据

**课堂请求模型**：六份脚本均直接写 `model="deepseek-flash"`，不从环境覆盖。2026-10-15 查阅 [DeepSeek 官方更新](https://api-docs.deepseek.com/updates/) 时，既往核查记录将该别名对应到 DeepSeek-V4.1-Flash；这不是本次对别名映射的重新核验，也不是固定 checkpoint。本项目录制只记录请求 ID，不能用它证明服务端返回了哪个版本。下文 V3 模板是固定的历史教学对照。

- [DeepSeek: Your First API Call](https://api-docs.deepseek.com/)：OpenAI SDK 可通过配置 DeepSeek 的 `base_url` 与密钥访问 DeepSeek。SDK 名称不决定实际模型提供方。
- [DeepSeek: FIM Completion API (Beta)](https://api-docs.deepseek.com/api/create-completion/)：v0/v1 使用 `/completions` 与 Beta 地址；v0 额外请求 `logprobs`，获取采样 token 与候选项的对数概率。`max_tokens` 是生成上限，不保证恰好生成该数量。只传前缀、不传 `suffix` 时用于续写展示；Completion 接口形式不意味着调用了未经指令训练的基础模型。
- [DeepSeek: Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)：核对 messages、roles、tools、tool_calls、tool_call_id 等字段。工具调用返回的是待执行请求，执行与结果回填由客户端完成。
- [DeepSeek: Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)：v2—v4 显式传 disabled，只有 v5 用顶部 THINKING 开关控制 enabled/disabled。v5 展示的是 API 返回的 reasoning_content，完整 assistant 消息继续回传，以满足工具后续请求的字段要求；这是非流式调用，显示发生在完整响应返回后。
- [MCP specification, revision 2025-06-18: Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)：工具描述、列举与调用协议，以及参数验证、访问控制、超时与使用记录。此链接固定到一个规范版本，不声称它是永久的最新版本。

`exp(logprob)` 是对 API 返回值的直接转换。top-k 候选只覆盖词表的一部分，显示项概率通常不加总为 100%；不得将这几个候选重新归一化后标成 API 原始概率。服务端没有在这些文档中完整说明所有采样内部细节，不声称接口返回了整词表分布。

teach 的所有阶段均使用 API 默认采样设置，不传 temperature；课堂聚焦上下文、实际生成项与返回的 top 候选，不讲采样参数配置或比较。每次运行只按本次真实返回的数值展示，不预设概率形态、生成内容或跨请求一致性。

v0 的 `logprobs=5` 请求候选对数概率，程序只呈现 API 实际返回的项。候选概率不等于整句话为真的概率；显示少数 top 候选也不意味着获得了完整词表分布。2026-10-16 19:46:21（北京时间）按最终源码重新运行两条前缀，真实结果保存在 `recordings/v0.json`，并通过源码 SHA 核对；具体证据见 [验证记录](../VALIDATION.md)。源码改变后须重新请求，不能修改旧转录或只替换 SHA。

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

API 的 `messages` 是应用层协议；服务端可能采用不同的模板、版本与额外包装。当前程序录制只记录请求模型和终端输出，不包含完整原始响应，也不用于断言 API 的返回模型或内部模板；不能仅因 API 别名来自 DeepSeek，就断言其内部仍使用这个公开 V3 checkpoint 的序列化形式。

## 演示证据标识

- **LIVE**：本次确实运行教学脚本并请求 API，记录对应源码 SHA、输入与实际终端输出；它不是完整 SDK 响应归档。
- **REPLAY**：读取已经录制的真实程序输出；应展示录制时间、请求模型与源码来源。若没有真实录制，必须报缺失，不能生成貌似实时的结果。
- **示意**：讲义中的结构示例、伪代码或可能路径；不能冒充 API 输出。
- **本地确定性检查**：固定 CSV 的统计、算式执行和 Bash 退出码，可独立运行验证。它们不证明 LLM 每次会采用同一行动路径。

课堂区分三类输出：API 返回的思考文本（仅 v5 开启时）、结构化工具请求、实际执行结果。它们分别说明不同事情；思考文本和调用描述不能代替工具执行与文件产物证据。

## 本轮课堂任务与证据范围

- 第 8 页 v3 改用复杂表达式，本地有理数验算为 **93824436**。
- 第 10 页 v4 改用采购付款任务，本地十进制验算为 **111303.65 元**；九三折、优惠券、收费运费、仅商品计税，步骤见 [任务与验算](loop_examples.md)。
- 两题没有新增 API 实测，不能用上述独立基准声称模型已经答对。两版采用不同任务，也不作为严格性能比较；v4 可以一次完成计算，不保证多次调用或成功。
- 第 12—13 页 v5 为教师自由演示与通用验收，没有固定提示词或温度报告要求。
- `recordings/` 与 `verify_live.py` 仍采用此前的同题对照和温度报告。历史输入、转录与时间保留，不改写为新题证据；回放时须标明历史任务。
