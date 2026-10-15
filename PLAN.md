# 单目录课堂精简规格

目标：同一目录中的 `agent_v0.py`—`agent_v5.py` 六份独立教学程序，在 45 分钟内讲清文本续写、上下文、角色、工具、循环与 Bash 执行。

## 六阶段

| 阶段 | 文件 | 机制 |
|---|---|---|
| v0 | `agent_v0.py` | 独立 Completion、12 个 token、真实 logprobs 与候选概率 |
| v1 | `agent_v1.py` | 文本 history；多轮保存并重新提交 |
| v2 | `agent_v2.py` | system/user/assistant messages |
| v3 | `agent_v3.py` | 内联 calculator；一次工具请求与回填后回答 |
| v4 | `agent_v4.py` | 内联 calculator；`while True` 反馈循环 |
| v5 | `agent_v5.py` | 内联 Bash 工具；当前目录执行，stdout/stderr 回填 |

直接 `python agent_vN.py`，无需切换版本。每份程序自带所需代码，不导入公共本地运行模块。v3/v4 用 `eval(expression)` 计算；v5 只保留 Bash，不带早期版本入口。另行开发的新 v5 本轮不纳入。

统一用 prompt_toolkit 提供 `$ ` 提示，多行粘贴后按 Enter 整段提交，空白输入跳过；Ctrl+D、Ctrl+C 结束。密钥来自环境，模型在每个SDK调用中直接写 `deepseek-flash`。仅v0设置顶部 `TEMPERATURE = 0` 供调节，其余版本不传temperature。SDK非流式，v2关闭thinking，v3—v5顶部 `THINKING = True` 同时控制思考模式与API思考文本展示；每次完整响应后显示，思考与回答共用8192 token预算。API 45秒超时、1次重试。程序末尾仅处理EOF和中断；不设置命令行参数、密钥预查或通用错误包装。

## 工具和循环

- v3 每个用户轮做一轮工具请求，执行并回填后回答；不进入持续工具循环。
- v4/v5 使用 `while True`，没有轮数上限；工具结果进入历史，模型可以继续请求工具或给出最终回答。
- v3—v5将完整SDK assistant消息保留进历史，包括reasoning_content，供工具后续调用与下一用户轮使用。
- v5 的 `run_bash(command)` 直接调用 `subprocess.run(["bash", "-c", command], ...)`，当前目录执行、60 秒超时，stdout 与 stderr 作为结果返回。
- 文件直接保存在当前目录；不配置沙箱、白名单、临时工作区、产物导出、自动虚拟环境或网络代理。原隔离说明归档至 `docs/archive/sandbox-isolated.md`。

## 网页、录制与课程

- metadata 只使用阶段 `id` v0—v5 及 `file` agent_vN.py；网页读取实际文件与 SHA-256，显示相邻文件差异，复制直接运行命令，保留投影字号与安全转义。
- 教师 `verify_live.py`、`preflight.py` 在项目根目录工作。录制为 `live-program-recording`，保存实际 stdout 转录及 source_file/source_sha256，不假称包含完整 SDK events 或未知的返回模型。
- 网页明确标记 REPLAY，不执行历史命令。既有历史 Tag 与旧录制保留追溯，不参与教学运行，也不更改另一工作区的标签。
- 讲稿保留 45 分钟、大纲保留 16 页；v1 通过重启做无历史/有历史对照，v3 先运行 v2 的纯文本回答再运行 v3 的工具请求。温度比较修改 v0 顶部常量。

## 验证要求

- 六份程序分别验证独立输入、历史、结构化消息、单轮工具和反馈循环；检查空白、EOF 与中断。
- v5 在测试目录执行真实 Bash，检查 stdout/stderr、命令超时、文件跨轮保留；报告任务由外部核对 **10 行、平均 24.5°C、最大 29°C、最小 20°C**。
- 网页测试使用普通临时目录，覆盖六阶段、相邻差异、复制、转义、源码与录制对应，不创建临时 Git 仓库。
- 真实 API 与自动测试结果分别记录于 `VALIDATION.md`；测试 fixture 不作为真实输出。外部新闻、API 与历史模板来源继续保留原有事实边界。

课程时间：00—04 完整演示；04—11 token；11—17 history；17—22 roles；22—30 tools；30—39 loop 与 Bash；39—43 案例；43—45 总结。
