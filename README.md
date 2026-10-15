# 从文字接龙到 AI Agent：用一个 API 构建智能体

45分钟，面向泛工科本科生。同一个 `agent.py` 依次增加 history、messages、tool calling、反馈循环与隔离执行；只用标准库和 OpenAI Python SDK。

默认实际调用 **DeepSeek-V4.1-Flash**，API ID 为 `deepseek-flash`。已于2026-10-15核对[官方映射](https://api-docs.deepseek.com/updates/)并完成真实调用；该别名未来可能更新。历史V3仅用于公开Chat Template对照，不承担实时调用。

## 启动

需要 Python **3.12+**、Git。支持 macOS；Linux 执行阶段需 Docker。Windows 请用 WSL。

```bash
cd /Users/zfh/work/DummyAgent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
source ~/.config/api-keys/llm.env
```

密钥只从 `DEEPSEEK_API_KEY` 环境变量读取，不打印、不入库。若个人环境文件没有 `export`，可用 `set -a; source ~/.config/api-keys/llm.env; set +a`。更换模型才设置 `DEEPSEEK_MODEL`，不设置即使用 Flash。

## 六个真实版本

无需学生掌握Git；`run_stage.py` 从真实Tag临时导出并运行，结束清理临时源码。

所有版本默认进入自由交互；只有 `--demo` 才使用固定课堂输入。交互中输入 `:quit` 退出；维护对话历史的版本可输入 `:reset` 清空历史。

| Tag | 新机制与交互方式 | 启动交互 |
|---|---|---|
| v0-token | 任意文本前缀续写 + 真实logprobs；每次独立，不保存历史 | `python run_stage.py v0-token --temperature 0.8` |
| v1-memory | 应用维护文本history，多轮自由对话 | `python run_stage.py v1-memory` |
| v2-chat | system/user/assistant 结构化多轮对话 | `python run_stage.py v2-chat` |
| v3-tools | 自由提问；一次工具请求、执行、回填后回答；跨用户轮保留上下文 | `python run_stage.py v3-tools` |
| v4-agent-loop | 每个自由任务进入反馈循环，跨用户轮保留上下文 | `python run_stage.py v4-agent-loop` |
| v5-execution | 在同一个隔离实验目录持续执行自由任务 | `python run_stage.py v5-execution` |

各行命令加 `--demo` 即运行固定示例；v1 的 demo 保留“不带历史 / 带历史”的对照。v3 没有 Agent Loop：工具结果回填后只再回答一次；需要继续请求工具的任务应使用 v4。

也可直接执行一条自定输入，不进入交互。`--demo` 与 `--prompt` / `--task` 互斥：

```bash
python run_stage.py v0-token --prompt "热力学第一定律告诉我们，" --temperature 0.8
python run_stage.py v3-tools --task "请计算 (123.4 * 56.7) / 8.9"
python run_stage.py v5-execution --task "查看 data/temperature.csv 的前五行，告诉我列名"
```

最终版 `python agent.py` 默认进入隔离执行交互；`--calculator` 切换到计算工具循环，`--chat` 切换到角色对话，`--tokens --temperature 0.8` 切换到独立续写交互。这些入口都可结合 `--demo`。

## 断网也能授课

`recordings/<tag>.json` 保存对应版本的真实 API 演示，包含请求快照、响应、耗时、模型、源码SHA与终端转录。更新代码后须重新录制并校验对应关系；旧版录制归档到 `recordings/archive/2026-10-15/`，旧版 Tag 保留在 `archive/2026-10-15/<原Tag>`，供追溯使用。温度对照为 `recordings/v0-token-temperature0.json`。

```bash
python run_stage.py v5-execution --replay recordings/v5-execution.json
```

回放明确标为 **REPLAY**，不需要SDK或密钥，不调用API、不执行工具、不重建报告。开场可同时打开已保留的 `examples/final-report.md`。默认不会在网络失败时悄悄切换回放。

重新彩排请另存文件，保留课堂备份：

```bash
python run_stage.py v0-token --demo --temperature 0.8 --record recordings/rehearsal-token.json
python run_stage.py v5-execution --demo --record recordings/rehearsal-agent.json
```

API单次超时45秒，最多重试1次；工具超时8秒；v4/v5 的每个任务默认最多 **100 轮**，`--max-iterations` 可设为 1—1000。达到上限会停止，不等于任务完成。截断、超限、验收失败均不标记任务成功。模型文字仍可能变化；固定CSV的正确结果不变：**10行、平均24.5°C、最大29°C、最小20°C**。

## 执行隔离

`v5-execution` 优先使用本地已有Docker镜像，否则macOS使用Seatbelt；没有可用后端即拒绝执行。Docker需提前启动并执行 `docker pull python:3.12-slim`；程序不会自动联网拉镜像。

本机已实测macOS Seatbelt：禁网、数据只读、临时目录隔离、仅3个允许写的文件、禁子进程、输出/文件大小上限、超时、环境变量清理。交互会话中保持同一个实验目录，便于继续查看或修改先前产物；结束后导出到当前目录 `lab-runs/run-*/`，再清理临时目录。`:reset` 清空模型上下文，实验文件保留。

只有 `--demo` 强制执行固定 CSV 报告任务，并由可信代码独立核对统计结果与报告。自由交互和 `--task` 按用户任务执行，不要求每次生成温度报告；产物仍须通过文件安全检查，任务是否完成应结合工具结果和实际文件判断。

模型可写的文件仅 `analysis.py`、`result.json`、`report.md`；可用命令见工具Schema。不支持管道、shell重定向、cd和后台任务；字面Python heredoc由辅助层转换为等价 `python3 -c`，避免Bash创建子进程。目录限制和命令过滤之外还有OS隔离，详见 [安全边界与实测](docs/sandbox.md)。Docker分支尚未在本机验证。Codex嵌套沙箱可能阻止Seatbelt启动，此时在本机普通终端运行；程序仍拒绝未隔离执行。

## 教师入口

- 双击 [web/index.html](web/index.html)：阶段导航、完整代码、相邻Tag差异、能力说明、真实输出，完全离线，无CDN；字号可切换至投影模式。
- [45分钟教师讲稿](docs/teacher_script.md)
- [16页PPT内容大纲](docs/slides_outline.md)（按请求交付大纲）
- [官方新闻、API与模板来源](docs/sources.md)
- `python chat_template_demo.py`：固定公开V3模板的普通文本消息子集，保留完整Jinja原文与SHA，不声称代表Flash托管API内部格式。

重新构建网页：`python build_viewer.py`。源码和diff直接读取Git Tags，不拿当前工作区冒充旧版本。浏览器自动预览受当前URL策略限制，未完成自动视觉检查；构建、转义和交互结构测试已通过。

## 验证与结构

```bash
python preflight.py
python -m unittest discover -s tests -v
```

`preflight.py` 离线检查全部Tag可导出运行、源码与真实录制对应、关键机制与报告基准。单元测试里的fixture明确标注为测试数据，不作为课堂真实输出；没有隔离后端时，真实隔离集成测试会显示skip原因。

`agent.py` 是教学主线；`common.py` 仅配置/录制；`tools.py` 验证参数并执行；`sandbox.py` 承担OS边界；`lab.py` 准备数据、验收并导出。验收证据见 [VALIDATION.md](VALIDATION.md)。

讲授中的Stage 5是新闻案例；代码Tag的v5是隔离执行，安排在30—39分钟内。不要将两套编号误当成额外课时。
