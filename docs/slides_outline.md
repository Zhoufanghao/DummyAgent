# PPT 内容大纲

课程：《从文字接龙到 AI Agent：用一个 API 构建智能体》  
时长：45 分钟，16 页主讲内容。这里交付可直接制作 PPT 的逐页大纲，不包含 PPTX 文件。

实时演示默认 DeepSeek-V4.1-Flash，API ID 为 `deepseek-flash`（2026-10-15 核查 [官方更新](https://api-docs.deepseek.com/updates/) 的 2026-09-10 记录）；别名未来可能变化。第 8 页 V3 模板是明确标注的历史模型对照。

每页只承载一个主问题；代码与真实输出以网页版本浏览器、终端为主。正文建议不小于 24 pt，代码不小于 20 pt。每段代码只截取需要解释的部分，不把整个程序缩到一页。可编辑的流程用原生文本和箭头制作，实际 API 输出采用真实录制片段并标明 LIVE/REPLAY。

六个 Tag 各自是独立教学程序：先 `git switch --detach <tag>`，再 `python agent.py`，在 `$ ` 后手工输入本页示例或学生问题。没有命令行参数或内置固定演示；空白行跳过，Ctrl+D 结束，Ctrl+C 平稳退出。v0 输入独立前缀，v1—v5 保存当前会话上下文；重新启动开始新对话。v5 还保留同一会话的实验文件，结束时安全导出。课堂程序只需 `agent.py`，v3 起再带 `tools.py`。

| 页 | 时间 | 标题 | 屏幕内容 | 讲述与演示 | 备注 / 来源 |
| --- | --- | --- | --- | --- | --- |
| 1 | 00:00—00:40 | 从文字接龙到 AI Agent：用一个 API 构建智能体 | 课程题目；一行任务：CSV → 温度统计 → Markdown 报告 | 说明今天理解关键机制，不要求记住全部代码 | 使用用户指定课程名；不增加产品口号 |
| 2 | 00:40—04:00 | 温度报告任务 | 用户原始任务；CSV 局部；结果报告局部 | 切 v5 后运行 agent.py，输入任务；或在网页展示 REPLAY。看到工具请求、结果与文件，独立对照 10 行、24.5 / 29 / 20 ℃ | 录制时间与模型来自真实记录；说明重放不会重新创建文件 |
| 3 | 04:00—05:00 | 最小 Completion 调用 | `OpenAI(...)` 与 `client.completions.create(...)` 中约 8—12 行；框出 prompt 与 logprobs | SDK 是客户端，请求地址指向 DeepSeek。FIM Beta 只传前缀，用于续写 | [FIM API](https://api-docs.deepseek.com/api/create-completion/)，模型与参数以备课实测为准 |
| 4 | 05:00—08:20 | 下一个 token 的条件概率 | 左：当前上下文；右：某一步真实 top-k 与选中的 token；下方公式 `Pr[token \| context]` | token 指下一个生成项，context 指已有上下文。停在一个位置，说明追加已生成 token 后继续；交互可输入任意前缀。Token 不等于汉字；top-k 不覆盖全部概率 | 表格直接取 API logprobs；概率为 exp(logprob)，不另行归一化；非置信度 |
| 5 | 08:20—11:00 | Temperature 与采样 | 相同前缀、不同 temperature 的两次真实输出；只放 2—3 步 | 只改 agent.py 顶部 TEMPERATURE：默认 0，对照 0.8；TOKEN_STEPS 保持 12。比较后改回 0。低温不保证正确或逐字复现 | 当前API模式的参数支持见 [Chat API](https://api-docs.deepseek.com/api/create-chat-completion/) 与 [FIM API](https://api-docs.deepseek.com/api/create-completion/) |
| 6 | 11:00—17:00 | 对话历史 | 上：新会话中只有编号问题；下：带 history 的请求包含 A102。旁边只显示新增的保存与拼接代码 | 新会话只问编号；重启后手工输入 A102 再问编号。直接比较实际请求；可换任意编号。说明有限上下文与长期记忆的区别 | 对比证据是实际提交内容，不能要求无历史模型必然答错 |
| 7 | 17:00—18:30 | 结构化消息 | 三条短 messages：system、user、assistant；各一行作用说明 | 文本拼接改为角色明确的消息。role 表达身份，不赋予宿主机执行权限 | [DeepSeek Chat API](https://api-docs.deepseek.com/api/create-chat-completion/) |
| 8 | 18:30—22:00 | 一个公开模型的 Chat Template | 标注“DeepSeek-V3 公开 checkpoint”；五行序列化示例；结束标记着色 | 只展示该模型的 User、Assistant、EOS；system 正文在 BOS 后。随后切到命令行简易聊天 | [固定版本 tokenizer_config.json](https://huggingface.co/deepseek-ai/DeepSeek-V3/blob/d990f047635ab4866b112caff006a18ce221605f/tokenizer_config.json)。不是对当前托管 API 内部模板的披露 |
| 9 | 22:00—25:00 | Calculator 工具说明 | 一条复杂算式；精简 schema：名称、expression 字符串、必填 | 先展示不调用工具的真实答复，再看 schema。即使纯文本算对，也说明为何需要可检查执行 | 工具说明不是函数实现；calculator 只允许受限算术 |
| 10 | 25:00—30:00 | 一次工具调用 | `LLM → Tool Call → 参数校验 → Python → Tool Result → LLM`；下方放真实 tool_call / result 配对 | 定位真正执行 calculator 的代码与 tool_call_id；默认可自由提问与追问，每个用户轮只进行一次工具请求与回填后的回答 | [DeepSeek Chat API tools 字段](https://api-docs.deepseek.com/api/create-chat-completion/)；外部程序执行；日志不是隐藏思维链 |
| 11 | 30:00—33:30 | Agent Loop | 实际循环约一屏；将“加入结果”“继续”“返回”“达到轮数上限”突出显示 | v3 单轮分支变为 v4 循环。手工输入先计算、等结果再除以 3 的任务，检查前后依赖；每个任务重新计数，对话保留 | 顶部 MAX_ITERATIONS = 100；达到上限只表示停止；不引入框架；投影以真实 agent.py 为准 |
| 12 | 33:30—34:50 | 受限执行环境 | 保留循环轮廓，把 calculator 标成 bash 工具；四项约束：超时、轮数、工作目录、危险操作防护 | v4 → v5 的核心增量是工具能力与隔离。指出真正执行隔离的位置 | cwd 与命令过滤不等于完整沙箱；执行环境不满足要求则停止，不转为宿主机无限制执行 |
| 13 | 34:50—39:00 | 再做一次温度报告 | 三个核验点：读到数据、计算结果、写入文件；实际报告中的三项统计 | 手工输入报告任务或展示对应真实 REPLAY；同一隔离目录可连续提问。结束后查看导出产物；若轨迹有修正，沿错误→下一步讲解 | CSV 基准：10 行，20—29 ℃；24.5 / 29 / 20 ℃。正确性由教师外部验证，文件安全检查保留在 tools.py；没有发生的错误不编造 |
| 14 | 39:00—41:20 | Coding Agent 与 MCP | 两行历史事件：2025-05-16 Codex 研究预览；2024-11-25 MCP 开源发布。分别指向循环与工具接入位置 | Codex 约75秒：读写代码与测试反馈。MCP约65秒：统一接入协议，任务循环仍由应用实现 | [Codex 原始发布](https://openai.com/index/introducing-codex/) 已标过时，仅作历史案例；[MCP 原始发布](https://www.anthropic.com/news/model-context-protocol) |
| 15 | 41:20—43:00 | Prompt Injection 与权限边界 | 日期2025-11-24；外部文件 → 上下文 → 工具请求；执行工具旁注明权限与隔离 | 说明防护进展新闻；用自拟 CSV 注入短句演示信任边界，不执行攻击 | [Anthropic 官方文章](https://www.anthropic.com/news/prompt-injection-defenses)。邮件外泄场景为原文假设示例，不是披露的真实事故 |
| 16 | 43:00—45:00 | 四层机制与完整程序 | token → 上下文 → 工具 → 反馈循环；下方列六个 Git tag | 回到完整 agent.py。退出票：为什么生成函数名不等于执行？ | 参考答：应用须解析校验并调用函数，结果还须进入后续上下文 |

## 第 8 页建议使用的唯一模板文本

```text
<｜begin▁of▁sentence｜>你是实验助手。
<｜User｜>实验编号是 A102。
<｜Assistant｜>已记下。<｜end▁of▁sentence｜>
<｜User｜>实验编号是什么？
<｜Assistant｜>
```

页内必须可见一句：“公开 DeepSeek-V3 模板示例；不代表当前托管 API 的内部模板。”为易读而换行，勿将排版换行解释为每个角色必然都有的特殊 token。

## 代码与输出的呈现约定

- 网页负责源码、差异与离线真实轨迹；终端用 Git 切换 Tag 后运行 agent.py；PPT 不重复铺满完整代码。
- 新增、删除、修改同时有文字或符号提示，不能只靠红绿区分。讲解每次只圈一处机制。
- 新录制由独立 verify_live.py 驱动真实交互，核对源码 SHA；课堂 agent.py 不包含录制包装。概率示例必须从 API 实录抽取，未完成时保留“待录制”，不要编造数值。
- 候选概率主示例使用 temperature=0.8。实测 temperature=0 可显示 0 / -9999 的退化返回；不要将其误讲为温度处理前的原始模型分布，也不要用“100%”暗示事实正确。
- 工具流程展示函数名、经过验证的参数和执行结果。密钥、授权头与完整环境不可出现在截图里。
- LIVE、REPLAY、教学示意采用明确文字，学生无需凭视觉风格猜测证据性质。
- 外部事实的日期和链接放在本页备注；产品现况、套餐价格和榜单排名不进入本课。

## 备用页，不计入主讲 45 分钟

1. **上下文窗口与长期记忆**：history 有界；检索或数据库是额外机制。本课不实现长期记忆。
2. **为什么不能直接 eval**：展示受限算术解析的输入边界，不引导学生复制任意字符串执行代码。
3. **失败也是反馈**：只截取真实彩排中出现的报错、后续请求与改正结果；没有录到就不展示。
4. **停止条件**：模型返回最终答案、轮数上限、工具超时与执行失败分别意味着什么；“停止”不自动等于“完成”。
