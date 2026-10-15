# teach：PPT 内容大纲

课程：《从文字接龙到 AI Agent：用一个 API 构建智能体》  
时长：45 分钟，16 页主讲内容。本文件为可直接制作 PPT 的逐页大纲，不包含 PPTX。

所有 SDK 调用直接使用 `model="deepseek-flash"`。2026-10-15 的既往核查将其对应到 DeepSeek-V4.1-Flash，来源与日期见 [sources.md](sources.md)；别名可能变化，不把这次记录当作今天的重新核验。第 8 页只展示明确标注的历史 V3 模板。

六份独立文件 `agent_v0.py`—`agent_v5.py` 同时放在项目根目录，直接运行对应文件，无版本切换。各自内联工具代码，依赖标准库、OpenAI SDK 与 `prompt_toolkit`，按 requirements 安装。输入提示为 `$ `；支持 bracketed paste 的终端中，多行粘贴保留换行，按一次 Enter 提交；空白输入跳过，Ctrl+D 或 Ctrl+C 结束。重新运行开始全新对话；`:quit`、`:reset` 没有特殊含义。每页只承载一个主问题，正文建议不小于 24 pt、代码不小于 20 pt；完整源码和差异交给网页呈现。

| 页 | 时间 | 标题 | 屏幕内容 | 讲述与演示 | 备注 / 来源 |
|---|---|---|---|---|---|
| 1 | 00:00—00:40 | 从文字接龙到 AI Agent | 课程题目；CSV → 温度统计 → Markdown 报告 | 今天理解关键机制，不要求抄完代码 | 使用指定课程名 |
| 2 | 00:40—04:00 | 温度报告任务 | 用户任务、CSV 局部、实际报告 | `python agent_v5.py` 后输入任务；或展示明确标记的 REPLAY。独立核对 10 行、24.5 / 29 / 20 ℃ | 文件直接留在启动目录；回放不会重建文件 |
| 3 | 04:00—05:00 | v0：独立续写 | `OpenAI(...)` 与 `client.completions.create(...)`，框出 prompt/logprobs | SDK 为客户端，服务地址指向 DeepSeek；FIM Beta 只给前缀 | [FIM API](https://api-docs.deepseek.com/api/create-completion/) |
| 4 | 05:00—08:20 | 下一个 token 的条件概率 | 当前上下文、真实 top-k、生成项；公式 `Pr[token \| context]` | 运行 `agent_v0.py`。一次请求完成后逐位置展示真实响应，更新显示的上下文；不是流式或逐 token 请求，token 不等于汉字 | exp(logprob)，不归一化 top-k；候选不是完整分布或事实置信度 |
| 5 | 08:20—11:00 | Temperature 与采样 | 同一前缀、温度 0 与 0.8 的真实输出 | 只改 v0 顶部 TEMPERATURE 并重启，TOKEN_STEPS 保持 12（生成上限）；现场真实比较后恢复 0 | 现有录制只含温度 0；低温不保证正确或逐字复现；[FIM 参数](https://api-docs.deepseek.com/api/create-completion/) |
| 6 | 11:00—17:00 | v1：文本 history | 无编号历史的请求；带 A102 的 history；保存与拼接代码 | `agent_v1.py` 新会话只问编号；重启后先告知 A102 再问。比较实际提交文本 | 不要求无历史模型必然答错；有限上下文不等于长期记忆 |
| 7 | 17:00—18:30 | v2：messages | system/user/assistant 三条短消息 | 打开 `agent_v2.py`，解释身份与顺序；role 不是执行授权 | [Chat API](https://api-docs.deepseek.com/api/create-chat-completion/) |
| 8 | 18:30—22:00 | 一个公开 Chat Template | 标注“公开 DeepSeek-V3 checkpoint”；五行序列化示例 | 运行 `chat_template_demo.py`，再运行 `agent_v2.py` 做两轮对话 | [固定 tokenizer_config.json](https://huggingface.co/deepseek-ai/DeepSeek-V3/blob/d990f047635ab4866b112caff006a18ce221605f/tokenizer_config.json)；不代表当前托管 API 内部模板 |
| 9 | 22:00—25:00 | v3：一次工具请求与回填 | 同一复杂算式；工具名称和 expression；内联 calculator | 先在 `agent_v2.py` 看纯文本回答，再打开 v3 Schema。指出直接 `eval(expression)` 的计算位置，幂运算用 Python 的 `**` | Schema 是说明书；函数实现就在本文件 |
| 10 | 25:00—30:00 | 一轮工具请求的边界 | `LLM → Tool Call → Python → Tool Result → LLM` | 先完成简单计算；28:30 在新 v3 会话输入两步题，查看实际 Tool Result 和终值 | 一次响应可含多个调用，但只执行回填一轮，第二次请求不带 tools；固定关闭 thinking；不预设失败；[Chat API tools 字段](https://api-docs.deepseek.com/api/create-chat-completion/) |
| 11 | 30:00—33:30 | v4：持续反馈循环 | v4 的 while True；同题实际工具轨迹；标准终值 256373415452969682 | 圈出回填后分支差异，再在新 v4 会话粘贴同题。两版均关闭 thinking，核对实际执行、A、B 和终值 | 当前录制中 v4 实际执行两次 calculator；循环无轮数上限，执行仍看 Tool Result |
| 12 | 33:30—34:50 | v5：Bash 执行 | v5 的工具 Schema、run_bash、subprocess 调用、timeout=60 | calculator 换成 Bash，循环保持；`["bash", "-c", command]` 直接执行，stdout/stderr 回填 | 主机启动目录执行、单命令 60 秒、合并 stdout/stderr；顶部 THINKING 控制模式和返回后显示 |
| 13 | 34:50—39:00 | 再做温度报告 | 读到数据、算出结果、写入文件的实际证据 | 运行 `agent_v5.py` 输入开场任务，查看实际报告；按真实错误与反馈讲修正。REPLAY 查看转录中的文件读取内容 | 教师独立核对 10 行、平均 24.5、最大 29、最小 20 ℃；无固定验收分支 |
| 14 | 39:00—41:20 | Coding Agent 与 MCP | 2025-05-16 Codex 研究预览；2024-11-25 MCP 开源发布 | Codex 对应代码与测试反馈循环；MCP 对应统一工具接入，循环仍由应用实现 | [Codex 原始发布](https://openai.com/index/introducing-codex/)只作历史案例；[MCP 原始发布](https://www.anthropic.com/news/model-context-protocol) |
| 15 | 41:20—43:00 | Prompt Injection 与信任边界 | 2025-11-24；外部内容 → 上下文 → 工具请求 | 说明外部内容可能改变任务方向，用自拟 CSV 短句说明；不执行攻击 | [官方防护进展](https://www.anthropic.com/news/prompt-injection-defenses)；原文邮件场景是假设，不是真实事故披露 |
| 16 | 43:00—45:00 | 四层机制与完整程序 | token → 上下文 → 工具 → 反馈循环；六份文件名 | 网页依次选择阶段，回到 v5；退出票：为什么生成函数名不等于执行？ | 参考答：外部程序须解析请求、调用函数并回填结果 |

## 备课操作

在已加载 `DEEPSEEK_API_KEY` 的 Python 环境中安装依赖后执行：

```bash
python -m pip install -r requirements-lock.txt
python preflight.py
python chat_template_demo.py
python build_viewer.py
```

网页从当前六份文件和 `recordings/v0.json`—`recordings/v5.json` 构建。`preflight.py` 不请求 API，只核对语法、独立性与录制来源。新彩排用空目录：

```bash
REHEARSAL_DIR=$(mktemp -d /tmp/dummyagent-rehearsal.XXXXXX)
python verify_live.py --output-dir "$REHEARSAL_DIR"
```

默认目录已有录制，直接运行 `python verify_live.py` 会拒绝覆盖。要更新网页使用的录制，明确运行 `python verify_live.py --overwrite`，再预检、重建。教师脚本临时执行目录结束后删除，JSON 仅保留真实输出和产物验收证据；REPLAY 不会恢复文件。需要现场打开报告时，手工运行 v5 并保留它的启动目录。详细节奏和口述见 [教师讲稿](teacher_script.md)。

## 第 10—11 页的同题比较

28:30—30:00 在新 v3 会话输入，32:00—33:30 在新 v4 会话粘贴完全相同的题目：

```text
先用calculator计算123456789 * 987654321，得到整数A后，取A的末6位作为B；
再用calculator计算B**3 + 17 * B。请给出A、B和最终整数。
每次只请求当前一步的计算，必须等工具返回后再进行下一步，不要把整条流程合成一个表达式。
```

标准答案：`A = 121932631112635269`，`B = 635269`，最终整数 `256373415452969682`。北京时间 2026-10-15 23:24 的当前录制中，两版均关闭 thinking：v3 只执行第一步，随后正文输出未执行的 DSML 调用、没有终值，属于未完成；v4 实际执行两次 calculator 并得到正确终值。其他运行不保证出现同样差异。

模型可能自行算出后续结果或合并表达式，不预设 v3 失败或每次出现同样差异；按实际 Tool Result、步骤要求与终值核验。备用条件分支三步题见 [循环对照案例](loop_examples.md)，主讲不增加页数或课时。

## 第 8 页唯一模板文本

```text
<｜begin▁of▁sentence｜>你是实验助手。
<｜User｜>实验编号是 A102。
<｜Assistant｜>已记下。<｜end▁of▁sentence｜>
<｜User｜>实验编号是什么？
<｜Assistant｜>
```

页内必须可见：“公开 DeepSeek-V3 模板示例；不代表当前托管 API 的内部模板。”为易读而换行，勿把排版换行讲成角色必有的特殊 token。

## 代码与输出约定

六个代码阶段依次称为：独立续写、文本 history、messages、一次工具请求与回填、持续反馈循环、Bash 执行。第 14—15 页为应用案例，不增加新的代码阶段。

所有调用固定 `model="deepseek-flash"`，SDK 超时 45 秒、重试 1 次。仅 v0 设置 TEMPERATURE 供 0/0.8 对照，v1—v5 使用 API 默认温度。v2—v4 固定关闭 thinking，v3/v4 不设思考开关或打印，max_tokens 分别为 500、1600。仅 v5 顶部 `THINKING = True` 控制模式与 reasoning_content 打印；该文本由 DeepSeek API 返回，在非流式完整响应后一次显示。v5 的 8192 token 由思考与回答共用，完整 message 保留 reasoning_content。工具执行仍核对 Tool Result。

- 网页读取六个实际文件及相邻差异，显示 SHA-256；复制命令直接运行 `python agent_vN.py`，不用 Git。
- 新增、删除和修改同时有文字或符号提示，不能只靠红绿；每次只圈一个机制。
- 真实录制由外部 `verify_live.py` 驱动程序，记录输入、UTC 时间、source_file/source_sha256 和原始程序输出；彩排输入独立展示，不伪装成终端回显。它不包含完整 SDK events，未知返回模型不展示。
- 采样概率只用真实 API 返回；温度 0 的 0 / -9999 退化值不是原始完整分布，不能用 100% 暗示事实正确。
- LIVE、REPLAY、教学示意用明确文字。REPLAY 不执行命令、不生成文件；源码变化后重新录制。当前 v3/v4 录制为北京时间 2026-10-15 23:24，v5 为 2026-10-16 00:05；v5 开启 thinking。
- 密钥不出现在截图里。外部事实日期与链接放备注，不增加价格、榜单或产品现况主张。

## 备用页，不计入 45 分钟

1. **上下文与长期记忆**：history 有限，检索或数据库是额外机制。
2. **工具实现在哪里**：同一文件中 Schema 描述接口，calculator 或 run_bash 执行动作。
3. **失败也是反馈**：只展示真实彩排中的错误与后续改变，不编造戏剧性失败。
4. **完成如何判断**：最终文本、工具执行成功、实际产物正确是不同证据。
