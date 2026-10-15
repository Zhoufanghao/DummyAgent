# DummyAgent · teach

45 分钟，面向泛工科本科生：从文本续写出发，依次加入对话历史、结构化消息、工具请求、反馈循环和 Bash 执行。

六个阶段放在同一目录中，每份脚本独立完整。直接运行 `python agent_vN.py`，无需逐阶段切换 Git 版本，也不需要公共运行模块。

## 安装与启动

在项目根目录准备 Python 3.12+；v5 还需要 Bash。首次使用可建立虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
export DEEPSEEK_API_KEY="替换为你的密钥"
python agent_v0.py
```

已有环境可直接激活，也可从自己的环境文件加载 `DEEPSEEK_API_KEY`。程序只读取环境变量，不自动加载 `.env`。依赖为 OpenAI Python SDK 与 `prompt_toolkit`，其余使用标准库。SDK 连接 DeepSeek 的 Beta 地址，所有请求直接写 `model="deepseek-flash"`；模型别名与公开模板的依据见 [来源说明](docs/sources.md)。

每版均以 `$ ` 提示输入。在支持 bracketed paste 的终端中，多行粘贴保留换行，按一次 Enter 整段提交；空白输入跳过。Ctrl+D 或 Ctrl+C 结束程序，重新启动即开始新对话。

## 六阶段

| 文件 / 运行命令 | 教学主线 | 每次响应的生成上限 | thinking |
|---|---|---:|---|
| `python agent_v0.py` | 独立 Completion；上下文、真实 logprobs 与候选概率 | 12 token | Completion 未显式设置 |
| `python agent_v1.py` | 文本 history；保存并重发双方对话 | 120 token | Completion 未显式设置 |
| `python agent_v2.py` | system / user / assistant messages | 500 token | 固定关闭 |
| `python agent_v3.py` | 一轮工具请求、执行和回填，再回答 | 500 token | 固定关闭 |
| `python agent_v4.py` | calculator 的持续反馈循环 | 1600 token | 固定关闭 |
| `python agent_v5.py` | Bash 执行与持续反馈循环 | 8192 token | 顶部 `THINKING = True` 控制 |

只有 v0 设置 `TEMPERATURE = 0`，可在文件顶部改为 0.8 做现场比较，之后恢复默认值。其余版本不传 temperature，使用 API 默认值。所有版本均为非流式请求，SDK 超时 45 秒、最多重试 1 次；这些设置不限制整项任务的总时长。

v0 一次请求获得整段续写，再逐位置打印返回的概率；`TOKEN_STEPS = 12` 是生成上限，每次输入相互独立。v1—v5 在同一进程中保留上下文，重新请求时提交此前对话；程序退出后不保存对话历史。

v3/v4 的 calculator 都直接使用 `eval(expression)`，乘方写 Python 的 `**`。v3 的第一次响应可以含多个工具调用，程序逐个执行并回填，但只处理这一轮；随后不带 tools 请求一次回答。v4/v5 在每次回填后继续请求模型，直到不再请求工具，没有固定循环次数上限。

v5 的 `THINKING` 同时控制 API 思考模式和 `reasoning_content` 显示。思考文本在完整响应返回后显示，8192 token 由思考与回答共用；完整 assistant 消息保留进历史，供后续工具请求使用。实际执行仍以工具结果为准。

## 课堂演示

按顺序打开六份源码，每次只观察新增机制。完整流程见 [45 分钟讲稿](docs/teacher_script.md) 和 [16 页大纲](docs/slides_outline.md)。

- v0：输入“牛顿第二定律告诉我们，”，查看续写及候选概率。
- v1/v2：先说“我的实验编号是 A102，请记住。”，再问“我的实验编号是什么？”。
- v3：输入“请用 calculator 计算 (123.4 * 56.7) / 8.9。”，区分请求、执行和结果回填。
- v4：与 v3 使用同一道多步题，观察回填后能否继续执行下一步。
- v5：生成并执行分析脚本，核对文件产物。

### v3 / v4 同题对照

分别启动 v3 和 v4，粘贴同一题：

```text
先用calculator计算123456789 * 987654321，得到整数A后，取A的末6位作为B；
再用calculator计算B**3 + 17 * B。请给出A、B和最终整数。
每次只请求当前一步的计算，必须等工具返回后再进行下一步，不要把整条流程合成一个表达式。
```

标准终值为 `256373415452969682`。当前保存的真实录制中，v3 只执行第一步，随后输出未执行的调用文本，没有终值；v4 实际执行两次并得到正确终值。固定题不保证每次出现相同差异，完整答案、备用题和判读方法见 [循环案例](docs/loop_examples.md)。

### v5 文件任务

在项目根目录运行 `python agent_v5.py`，然后输入：

```text
读取 data/temperature.csv，计算温度平均值、最大值和最小值，保存 report.md。
先检查数据，再生成 analysis.py 并执行，最后重新读取检查文件。
```

独立基准为 **10 行、平均 24.5°C、最大 29°C、最小 20°C**。手工运行时，文件直接保存在执行目录，退出后仍在；查看实际 `report.md` 核验。每次工具调用启动新的非交互 Bash，单次超时 60 秒；跨轮保留的是文件，上次调用的 `cd` 或 `export` 不会自动延续。详细行为见 [Bash 说明](docs/bash.md)。

## 网页与教师验证

以下命令在项目根目录运行：

```bash
python preflight.py
python chat_template_demo.py
python build_viewer.py
```

预检只检查文件、语法、独立性和录制来源，不请求 API。模板演示使用随附的固定公开 V3 模板。构建后打开 [web/index.html](web/index.html)，离线查看六份实际源码、相邻差异、运行命令及真实录制；网页不执行历史命令，也不生成报告文件。

已有六份录制时，新的真实彩排建议写入另一个目录：

```bash
rehearsal_dir=$(mktemp -d)
python verify_live.py --output-dir "$rehearsal_dir"
```

彩排会请求 API。教师脚本在一次性目录中运行实际程序，保存输入、时间、请求模型、源码 SHA 和原始 stdout/stderr 转录；v5 另保存独立统计验收和产物 SHA。执行目录随后清理，不保留实际报告文件；查看 REPLAY 时应核对转录中的文件读取内容。

要替换仓库中某阶段的录制，明确使用覆盖选项，再重新预检、构建：

```bash
python verify_live.py --stage v3 --stage v4 --overwrite
python preflight.py
python build_viewer.py
```

省略 `--stage` 会运行六版。默认输出到 `recordings/`，已有同名文件且未指定 `--overwrite` 时会拒绝覆盖。源码变化后要重新录制，不能只改旧记录的 SHA。记录不包含完整 SDK 请求/响应，也不证明服务端的实际模型版本。

## 文件分工

| 路径 | 用途 |
|---|---|
| `agent_v0.py`—`agent_v5.py` | 六份独立课堂程序 |
| `data/` | 温度 CSV、公开 V3 模板原文 |
| `docs/` | 讲稿、大纲、来源、循环案例、Bash 说明 |
| `recordings/v0.json`—`recordings/v5.json` | 当前六份真实录制 |
| `build_viewer.py`、`web/stages.json` | 网页构建与阶段说明 |
| `chat_template_demo.py`、`preflight.py`、`verify_live.py` | 教师辅助工具 |
| `tests/` | 教学行为和教师工具回归 |
| `requirements*.txt` | 依赖范围与固定版本 |
| `VALIDATION.md` | 实际验证结果与证据范围 |

教师工具不被课堂程序导入。旧资料通过 Git 历史追溯，不参与当前运行。回归命令为 `python -m unittest discover -s tests -v`，具体现有结果见 [验证记录](VALIDATION.md)。
