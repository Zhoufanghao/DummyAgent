# 从文字接龙到 AI Agent：用一个 API 构建智能体

45 分钟，面向泛工科本科生。六份独立 Python 文件依次展示文本续写、history、messages、工具调用、反馈循环与 Bash 执行；所有阶段同时放在项目根目录，依赖标准库、OpenAI Python SDK 和用于交互输入的 `prompt_toolkit`。

所有 SDK 调用直接使用 `model="deepseek-flash"`，对应的模型别名为 **DeepSeek-V4.1-Flash**。2026-10-15 核查的[官方更新](https://api-docs.deepseek.com/updates/)记录了这一别名映射；开课前须重新核对。公开 V3 仅用于历史 Chat Template 对照。

## 文件分工

`teach` 分支保留 37 个与当前课堂直接相关的文件：

| 文件 | 用途 |
|---|---|
| `agent_v0.py`—`agent_v5.py` | 六阶段独立课堂程序 |
| `data/` | 温度 CSV、公开 V3 模板原文 |
| `docs/` | 讲稿、大纲、来源、循环案例、Bash 说明 |
| `recordings/v0.json`—`recordings/v5.json` | 与当前源码匹配的六份真实录制 |
| `build_viewer.py`、`web/stages.json` | 构建六阶段源码、差异与回放网页 |
| `chat_template_demo.py`、`preflight.py`、`verify_live.py` | 模板演示、离线预检、真实彩排 |
| `tests/` | 教学行为及教师工具回归 |
| `requirements.txt`、`requirements-lock.txt` | 依赖范围与固定版本 |
| `README.md`、`VALIDATION.md`、`.gitignore` | 使用说明、验证证据与生成文件忽略规则 |

旧归档、旧运行示例和实施计划已移出当前文件树，原文仍可从 Git 历史查阅。运行环境 `.venv/` 留在本地，不纳入版本控制。

## 启动

在包含 `agent_v0.py`—`agent_v5.py` 的本项目目录运行。需要 Python **3.12+**；执行阶段需要 Bash。依赖可在教师已经配置好的 Python 环境中安装：

```bash
python -m pip install -r requirements-lock.txt
source ~/.config/api-keys/llm.env
python agent_v0.py
```

密钥由 `DEEPSEEK_API_KEY` 提供；若环境文件没有 `export`，可用 `set -a; source ~/.config/api-keys/llm.env; set +a`。模型名直接写在 SDK 调用中；程序不自动创建虚拟环境或设置代理。

各阶段都是自由交互，使用 `prompt_toolkit.prompt("$ ")` 提示输入。在支持 bracketed paste 的终端中，多行粘贴会整体保留换行，粘贴后按一次 Enter 提交；空白输入跳过，Ctrl+D 结束，Ctrl+C 退出。程序不处理聊天内命令。要开始全新对话，结束后重新启动。

| 阶段 | 直接运行 | 机制 |
|---|---|---|
| v0 | `python agent_v0.py` | 独立前缀续写、真实 logprobs 与候选概率 |
| v1 | `python agent_v1.py` | 保存并重新提交文本 history |
| v2 | `python agent_v2.py` | system/user/assistant messages |
| v3 | `python agent_v3.py` | calculator：一次工具请求、执行、回填后回答 |
| v4 | `python agent_v4.py` | calculator：工具结果推动下一轮决策 |
| v5 | `python agent_v5.py` | Bash：在当前目录执行命令并反馈结果 |

每份文件都包含自己所需的 SDK 调用、历史、工具定义和执行函数，无本地公共运行模块。v1 起不保留 token 演示；v5 仅有 Bash 工具。v3/v4 的 `calculator` 直接用 `eval(expression)` 求值；幂运算使用 Python 的 `**`。v4/v5 使用 `while True`，模型返回最终回答时结束当前任务，没有循环轮数上限。

只有 v0 设置 `TEMPERATURE = 0`，并生成 `TOKEN_STEPS = 12` 个 token；比较温度时修改 `agent_v0.py` 顶部常量为 0.8，之后恢复 0。v1—v5 不传 temperature，使用 API 默认值。单次 API 超时 45 秒，最多重试 1 次。

v2—v4 固定关闭 thinking；v3/v4 没有思考开关，也不打印 reasoning_content，`max_tokens` 分别为 500、1600。只有 v5 顶部保留 `THINKING = True`，控制 thinking 模式与 DeepSeek API 返回的 `reasoning_content` 展示。v5 使用非流式请求，完整响应后一次展示思考文本；`max_tokens = 8192` 由思考与回答共用，完整 message 保留进历史供后续调用。实际工具执行仍以 Tool Result 为证据。

## v3 与 v4 的同题对照

单个复杂算式通常一次 calculator 调用就能完成。演示 loop 时，在 v3 和 v4 各自新启动的程序中输入同一题：

```text
先用calculator计算123456789 * 987654321，得到整数A后，取A的末6位作为B；
再用calculator计算B**3 + 17 * B。请给出A、B和最终整数。
每次只请求当前一步的计算，必须等工具返回后再进行下一步，不要把整条流程合成一个表达式。
```

标准答案为 A = `121932631112635269`、B = `635269`、最终整数 = `256373415452969682`。本次关闭 thinking 的真实彩排中，v3 只执行第一步，随后输出未执行的 DSML 调用文本，没有最终数值；v4 实际执行两次 calculator 并得到正确终值。模型也可能自行算出终值，不预设 v3 失败，课堂以实际 Tool Result、步骤和最终数值判读。更多题面、标准答案及判读方法见 [循环对照案例](docs/loop_examples.md)。

## Bash 文件任务

在根目录运行 `python agent_v5.py`，然后输入：

```text
读取 data/temperature.csv，计算温度平均值、最大值和最小值，保存 report.md。先检查数据，再生成 analysis.py 并执行，最后重新读取检查文件。
```

Bash 直接在程序启动目录运行，`run_bash(command)` 用 `subprocess.run(["bash", "-c", command], ...)` 执行命令，stdout 与 stderr 回填到模型，单次命令超时 60 秒。生成文件直接留在当前目录，无临时工作区或退出导出步骤。具体方式见 [Bash 执行说明](docs/bash.md)。

固定 CSV 的独立基准为 **10 行、平均 24.5°C、最大 29°C、最小 20°C**。统计核对由教师脚本和测试完成，Agent 不含固定答案或内置报告验收分支。

## 网页与真实录制

```bash
python build_viewer.py
```

打开生成的 [web/index.html](web/index.html)，可离线查看六份文件、相邻文件的差异、源码 SHA-256 与真实输出；复制按钮直接给出 `python agent_vN.py`。网页从本项目文件读取源码，不查询 Git。

```bash
python verify_live.py
```

独立教师脚本运行六份实际程序，保存 `recordings/v0.json`—`recordings/v5.json`。新记录的类型为 `live-program-recording`，包含实际程序输出转录（stdout/stderr 合并）、`source_file` 和 `source_sha256`；它不捕获完整 SDK 请求与响应。页面只展示已知的请求模型，不编造 API 返回模型。彩排输入保存在独立的 `inputs` 列表，网页单列展示；终端库自身的输入回显按原样保留，不由教师脚本补写。源码变化后应重新验证并录制。

轨迹明确标记 **REPLAY**，只展示已经发生的运行，不调用 API、不执行历史命令、不重新生成文件。网络失败时可手工展示已有真实回放；需要实际报告文件时，在终端重新运行 v5 任务。旧版本只在 Git 历史和既有标签中保留，不参与当前课堂运行与网页构建。

## 教师入口与验证

- [45 分钟教师讲稿](docs/teacher_script.md)
- [16 页 PPT 内容大纲](docs/slides_outline.md)
- [官方新闻、API 与模板来源](docs/sources.md)
- `python chat_template_demo.py`：固定公开 V3 模板的普通文本消息子集，不声称代表 Flash 托管 API 内部格式。

```bash
python preflight.py
python -m unittest discover -s tests -v
```

预检、录制和网页构建是独立教师工具，课堂程序不导入它们。测试数据不充当真实运行证据；具体验证结果见 [VALIDATION.md](VALIDATION.md)。

讲稿中的教学 Stage 5 是新闻案例；代码 v5 是 Bash 执行，放在 30—39 分钟内。
