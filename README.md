# 从文字接龙到 AI Agent：用一个 API 构建智能体

45 分钟，面向泛工科本科生。六个独立教学版本依次展示文本续写、history、messages、工具请求、反馈循环与隔离执行；仅使用标准库和 OpenAI Python SDK。

默认模型为 **DeepSeek-V4.1-Flash**，API ID 为 `deepseek-flash`。2026-10-15 核查的[官方更新](https://api-docs.deepseek.com/updates/)记录了这一别名映射；别名可能更新，开课前须重新核对。历史 V3 仅用于公开 Chat Template 对照。源码对应的真实调用证据见录制与 [VALIDATION.md](VALIDATION.md)。

## 启动

需要 Python **3.12+**、Git。支持 macOS；Linux 执行阶段需 Docker。Windows 请用 WSL。

```bash
cd /Users/zfh/work/DummyAgent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
source ~/.config/api-keys/llm.env
```

密钥只从 `DEEPSEEK_API_KEY` 环境变量读取，不打印、不入库。若个人环境文件没有 `export`，可用 `set -a; source ~/.config/api-keys/llm.env; set +a`。`DEEPSEEK_MODEL` 可覆盖默认模型。温度、token 数和循环上限等本阶段可调项放在各版 `agent.py` 顶部。

## 六个独立版本

本轮精简快照使用独立 Tag 命名空间 `teaching-cleanup/<阶段ID>`；现有共享的 v0—v5 标签不改动。下表保留简短阶段 ID，实际切换时须加 `teaching-cleanup/` 前缀。先结束当前程序，再切换并直接启动。例如：

```bash
git switch --detach teaching-cleanup/v0-token
python agent.py
```

程序用 `$ ` 等待输入，空白行跳过；Ctrl+D 正常结束，Ctrl+C 平稳退出。每版只有自由交互，不解析命令行参数或聊天内命令。要开始全新对话，结束后重新启动。

| 阶段 ID | 课堂运行文件 | 该版机制 |
|---|---|---|
| v0-token | `agent.py` | 独立前缀续写、真实 logprobs 与候选概率；不保存历史 |
| v1-memory | `agent.py` | 应用保存并重新提交文本 history |
| v2-chat | `agent.py` | system/user/assistant messages 多轮对话 |
| v3-tools | `agent.py`、`tools.py` | calculator；一轮工具请求、执行、回填后回答 |
| v4-agent-loop | `agent.py`、`tools.py` | calculator；工具结果推动下一轮决策 |
| v5-execution | `agent.py`、`tools.py` | Bash；共享隔离实验目录与产物导出 |

将上面命令中 `teaching-cleanup/` 后的阶段 ID 替换为表中任意一项。v3 不会持续循环请求工具；多步任务用 v4。v5 只保留 Bash 工具。这里的 v5 是原受限基线的精简参考；另行开发中的新版 Bash 能力待最终 v5 确定后再合入、精简。SDK 调用、history/messages 和循环直接写在对应 `agent.py` 中；教师脚本不参与课堂程序运行。

默认 `TEMPERATURE = 0`；v0 的 `TOKEN_STEPS = 12`。温度对照直接修改 v0 顶部的 `TEMPERATURE`，比较 0 与 0.8，结束后改回 0 再切换版本。API 单次超时 45 秒，最多重试 1 次；v4/v5 的 `MAX_ITERATIONS = 100` 是每个用户任务的上限，达到上限表示停止，不能据此认定任务完成。

课堂结束后回到最终分支：

```bash
git switch codex/teaching-cleanup
```

## 现场输入与离线备份

每次启动后手工输入问题。例如在 v5 的 `$ ` 后输入：

```text
读取 data/temperature.csv，计算温度平均值、最大值和最小值，保存 Markdown 报告。先检查数据，再生成 analysis.py 并执行，最后重新读取检查文件。
```

固定 CSV 的独立基准为 **10 行、平均 24.5°C、最大 29°C、最小 20°C**。它是课堂验证任务，不是 Agent 的内置分支；其他输入按用户自己的任务执行。统计核对由教师脚本和测试完成，不由 Agent 用固定答案判断自己成功。

在最终分支运行 `python build_viewer.py`，再双击生成的 `web/index.html`，可离线展示六阶段源码、差异和真实轨迹。页面是本地生成物，切换六个教学 Tag 时不会被旧页面覆盖。轨迹明确标记 **REPLAY**，只展示已发生的运行，不调用 API、不执行历史工具、不重建报告；网络失败不会自动切换。现场需要文件时，可打开已核实的 [examples/final-report.md](examples/final-report.md)。

新版本彩排与真实 API 录制使用独立教师脚本，默认解析 `teaching-cleanup/` 下的六个教学 Tag：

```bash
python verify_live.py
```

录制需绑定到本轮命名空间中的真实快照，核对模型、时间、源码 SHA 和真实输入；重新绑定后的结果以验证记录为准，不能把旧输出当作新代码的验证。重构前的 Tag 原样保留在 `archive/2026-10-15/pre-cleanup/<tag>`，对应旧录制原样保留在 `recordings/archive/2026-10-15/pre-cleanup/`；此前 `archive/2026-10-15/<tag>` 与 `recordings/archive/2026-10-15/` 的第一代归档继续保留。当前课堂录制放在 `recordings/`。

## 执行隔离

v5 优先使用本地已有 Docker 镜像，否则 macOS 使用 Seatbelt；没有可用后端即拒绝执行。Docker 需提前启动并执行 `docker pull python:3.12-slim`，程序不会自动联网拉镜像。

同一会话保持一个临时实验目录，各轮可继续读取或修改先前产物。结束时先做文件安全检查，将已有非空产物导出到当前目录的 `lab-runs/run-*/`，再清理临时目录。无产物的问答也能正常结束。

`tools.py` 包含参数校验、隔离后端、目录准备与安全导出。后续 Bash 扩展集中修改 `BASH` Schema、`execute`、`run_bash`，目录生命周期由 `seed`、`export_outputs` 负责；保持这几个直接可读的函数边界，不引入额外框架。保留禁网、数据只读、文件白名单、超时、输出与文件大小限制；仅允许写 `analysis.py`、`result.json`、`report.md`。支持的命令见工具 Schema。接口不支持管道、shell 重定向、cd 和后台任务；字面 Python heredoc 转成等价 `python3 -c`，避免 Bash 创建子进程。

命令过滤之外还必须有 OS 隔离，详见 [安全边界与历史实测](docs/sandbox.md)。Codex 嵌套沙箱可能阻止 Seatbelt 启动；此时在普通终端预检或展示真实轨迹，不解除隔离。新版本实际隔离验证的通过、失败和跳过分别记录在 [VALIDATION.md](VALIDATION.md)。

## 教师入口与检查

- [45 分钟教师讲稿](docs/teacher_script.md)
- [16 页 PPT 内容大纲](docs/slides_outline.md)
- [官方新闻、API 与模板来源](docs/sources.md)
- `python chat_template_demo.py`：固定公开 V3 模板的普通文本消息子集，保留完整 Jinja 原文与 SHA；不声称代表 Flash 托管 API 内部格式。
- `python build_viewer.py`：从真实 Git Tags 重建完全离线网页；不拿工作区代码冒充历史版本。

```bash
python preflight.py
python -m unittest discover -s tests -v
```

预检离线核对 Tag、课堂文件依赖、源码与录制对应关系及报告基准。测试 fixture 只作测试数据，不作为课堂真实输出；隔离测试不可运行时报告 skip 原因。完整验收还包括逐 Tag 的真实 API 冒烟、v5 统计核验和网页检查；具体结果见 [VALIDATION.md](VALIDATION.md)。

讲授中的 Stage 5 是新闻案例；代码 Tag 的 v5 是隔离执行，安排在 30—39 分钟内。
