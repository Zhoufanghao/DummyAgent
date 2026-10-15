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

| Tag | 新机制 | 实时演示 |
|---|---|---|
| v0-token | Completion + 真实logprobs | `python run_stage.py v0-token --demo --temperature 0.8` |
| v1-memory | 应用维护文本history | `python run_stage.py v1-memory --demo` |
| v2-chat | system/user/assistant | `python run_stage.py v2-chat --demo` |
| v3-tools | 一轮真实calculator调用 | `python run_stage.py v3-tools --demo` |
| v4-agent-loop | 依赖前次结果的反复决策 | `python run_stage.py v4-agent-loop --demo` |
| v5-execution | Bash + 真正OS隔离 | `python run_stage.py v5-execution --demo` |

`python run_stage.py v2-chat` 是交互聊天，输入 `:quit` 结束。最终版 `python agent.py --calculator --demo` 可重看计算循环；`--chat` 重看对话；`--tokens --temperature 0.8` 重看token。

## 断网也能授课

六份 `recordings/<tag>.json` 和温度对照 `recordings/v0-token-temperature0.json` 均来自已验证的真实API调用，包含请求快照、响应、耗时、模型、源码SHA与终端转录。

```bash
python run_stage.py v5-execution --replay recordings/v5-execution.json
```

回放明确标为 **REPLAY**，不需要SDK或密钥，不调用API、不执行工具、不重建报告。开场可同时打开已保留的 `examples/final-report.md`。默认不会在网络失败时悄悄切换回放。

重新彩排请另存文件，保留课堂备份：

```bash
python run_stage.py v0-token --demo --temperature 0.8 --record recordings/rehearsal-token.json
python run_stage.py v5-execution --demo --record recordings/rehearsal-agent.json
```

API单次超时45秒，最多重试1次；工具超时8秒；默认8轮，`--max-iterations`最高12。截断、超限、验收失败均不标记任务成功。模型文字仍可能变化；固定CSV的正确结果不变：**10行、平均24.5°C、最大29°C、最小20°C**。

## 执行隔离

`v5-execution` 优先使用本地已有Docker镜像，否则macOS使用Seatbelt；没有可用后端即拒绝执行。Docker需提前启动并执行 `docker pull python:3.12-slim`；程序不会自动联网拉镜像。

本机已实测macOS Seatbelt：禁网、数据只读、临时目录隔离、仅3个允许写的文件、禁子进程、输出/文件大小上限、超时、环境变量清理。执行后由可信代码独立核对结果并导出到当前目录 `lab-runs/run-*/`，临时实验目录随即清理。

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
