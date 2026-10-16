# DummyAgent · teach

45 分钟，面向泛工科本科生：从文本续写出发，依次加入对话历史、结构化消息、工具请求、反馈循环和 Bash 执行。

六个阶段放在同一目录中，每份脚本独立完整。直接运行 `python agent_vN.py`，无需逐阶段切换 Git 版本，也不需要公共运行模块。

## 课程幻灯片

[Slidev 课程](slides/README.md) 共 16 页，按 45 分钟组织，侧重从文字生成到工具执行与反馈循环的原理。正文、可编辑图示和讲者备注位于 [slides/slides.md](slides/slides.md)；进入 `slides/` 后运行 `npm run dev` 开始放映。另有 [课堂演示提示词](slides/课堂演示提示词.md)、[可编辑 PPTX](slides/从文字接龙到AI-Agent-可编辑.pptx) 和 [课程 PDF](slides/从文字接龙到AI-Agent.pdf)。

普通 HTML 放映页中，第 8 页 v3、第 10 页 v4 直接显示完整提示词，并有“复制提示词”按钮；第 12 页 v5 提供空白任务输入区，可现场编辑并复制，第 13 页继续验收。第 3—7 页只显示生成、history、角色和模板占位原理，不展示可执行提示词或复制区；v0—v2 的终端输入从教师讲稿或提示词清单取用。

## 安装与启动

在项目根目录准备 Python 3.12+；v5 还需要 Bash。首次使用可建立虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
export DEEPSEEK_API_KEY="替换为你的密钥"
python api_demo.py
```

已有环境可直接激活，也可从自己的环境文件加载 `DEEPSEEK_API_KEY`。程序只读取环境变量，不自动加载 `.env`。依赖为 OpenAI Python SDK 与 `prompt_toolkit`，其余使用标准库。SDK 连接 DeepSeek 的 Beta 地址，所有请求直接写 `model="deepseek-flash"`；模型别名与公开模板的依据见 [来源说明](docs/sources.md)。

`api_demo.py` 是 8 行的最小 Completion 示例：创建客户端、提交文本前缀、打印 `response.choices[0].text`。先用它确认 API 可用，再运行 `python agent_v0.py`，加入交互和概率展示。它与 v0 使用相同的 Beta 地址和 Completion 接口，不需要 messages 或工具定义。

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

所有阶段均使用 API 默认采样设置，不传 temperature。所有版本均为非流式请求，SDK 超时 45 秒、最多重试 1 次；这些设置不限制整项任务的总时长。

v0 一次请求获得整段续写，再逐位置打印上下文、实际生成项和返回的候选概率；`max_tokens=12` 是生成上限，每次输入相互独立。只展示 API 返回的 top 候选，不代表完整词表分布，也不把候选概率当作答案正确率。v1—v5 在同一进程中保留上下文，重新请求时提交此前对话；程序退出后不保存对话历史。

v3/v4 的 calculator 都直接使用 `eval(expression)`，乘方写 Python 的 `**`。v3 的第一次响应可以含多个工具调用，程序逐个执行并回填，但只处理这一轮；随后不带 tools 请求一次回答。v4/v5 在每次回填后继续请求模型，直到不再请求工具，没有固定循环次数上限。

v5 的 `THINKING` 同时控制 API 思考模式和 `reasoning_content` 显示。思考文本在完整响应返回后显示，8192 token 由思考与回答共用；完整 assistant 消息保留进历史，供后续工具请求使用。实际执行仍以工具结果为准。

## 课堂演示

按顺序打开六份源码，每次只观察新增机制。完整流程见 [45 分钟讲稿](docs/teacher_script.md)、[16 页大纲](docs/slides_outline.md) 和 [可粘贴提示词](slides/课堂演示提示词.md)。代码细节在 Terminal 讲，幻灯片聚焦生成、上下文、执行和反馈。

- v0：输入“牛顿第二定律告诉我们，”，查看续写及候选概率。
- v1/v2：先说“我的实验编号是 A102，请记住。”，再问“我的实验编号是什么？”。
- v3：在第 8 页点击“复制提示词”后切到终端，计算下列复杂表达式，区分请求、执行和结果回填。
- v4：在第 10 页点击“复制提示词”后切到终端，核算下列采购付款任务，观察规则判断与实际工具反馈。
- v5：第 12 页由教师在空白输入区编辑自由任务并复制，第 13 页核对实际执行和任务结果，不安排固定提示词。

### v3：复杂表达式

启动 `python agent_v3.py`，粘贴：

```text
计算((12345 * 6789 - 9876 * 5432) / 3 + 2468 * 1357) * 7 - 1233
```

本地独立验算基准为 **93824436**。观察模型请求了什么表达式、程序实际执行了什么、返回值如何进入回答。v3 首轮可以含多个工具调用，只处理一轮回填；这道题本身可以用一次 calculator 完成。

### v4：采购付款核算

启动 `python agent_v4.py`，将下面三行整段粘贴为一条输入：

```text
采购367件单价129.80元的材料、284件单价87.60元的材料，以及159件单价216.40元的材料。
商家规则：原价满10万元打九三折，否则打九七折；折扣后再减1280.45元优惠券。优惠后的商品金额不足10万元，另收385.60元运费，否则免运费。商品金额另加13%的税，运费不计税。
请核算最终付款金额，保留两位小数，并说明实际触发了哪些优惠和运费规则。
```

本地独立验算：原价合计 **106922.60 元**，触发九三折；券后商品金额 **98157.5680 元**，低于 10 万元，收 **385.60 元**运费；按券后商品金额加 13% 税，运费不计税，最终付款 **111303.65 元**。详见 [任务与验算](docs/loop_examples.md)。

v3、v4 采用不同题目，不能据此作严格性能比较。采购规则虽有多个步骤，也可以合并为一次计算；v4 允许反馈后继续执行，不保证每次多次调用或成功。上述数字是本地独立验算，**没有新增模型实测或录制**。

### v5：教师自由演示

先约定交付物或验收标准，在第 12 页的空白任务输入区现场编辑并复制，再粘贴到 `python agent_v5.py` 中运行；第 13 页检查实际工具结果，涉及文件时重新打开保存的文件。不预设固定提示词，也不要求完成温度报告。

Bash 每次调用启动新的非交互进程，单次超时 60 秒；文件跨调用保留，上次调用的 `cd` 或 `export` 不会自动延续。详细行为及可选温度案例见 [Bash 说明](docs/bash.md)。

### 历史录制与可选备用

现有 `recordings/` 和 `verify_live.py` 仍使用此前的两道 v3/v4 同题任务与 v5 温度报告任务；它们**不对应本次更换的提示词**，也不决定本次 v5 自由演示内容。历史题面、答案和证据边界见 [循环案例](docs/loop_examples.md)、[Bash 说明](docs/bash.md) 与 [验证记录](VALIDATION.md)。不要把历史 REPLAY 当作新题的运行结果。

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

彩排会请求 API，默认仍运行历史题面，不是本次新题的彩排。教师脚本在一次性目录中运行实际程序，保存输入、时间、请求模型、源码 SHA 和原始 stdout/stderr 转录；v5 另保存独立统计验收和产物 SHA。执行目录随后清理，不保留实际报告文件；查看 REPLAY 时应核对转录中的文件读取内容。

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
| `api_demo.py` | 单次 Completion，验证 API 可用 |
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
