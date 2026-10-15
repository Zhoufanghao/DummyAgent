# v5：Bash 执行与反馈循环

`agent_v5.py` 将 calculator 换成 Bash，保留“请求模型 → 执行工具 → 回填结果 → 再次请求”的循环。每份课堂脚本独立运行，v5 只提供 Bash 工具。

## 启动与文件任务

在项目根目录运行 `python agent_v5.py`，在 `$ ` 后粘贴任务，按 Enter 提交：

```text
读取 data/temperature.csv，计算温度平均值、最大值和最小值，保存 report.md。
先检查数据，再生成 analysis.py 并执行，最后重新读取检查文件。
```

标准统计是 **10 行、平均 24.5°C、最大 29°C、最小 20°C**，由教师根据 CSV 独立核对。Agent 没有固定答案或内置报告验收分支。任务完成后可继续输入“再次读取上轮的 report.md，不要重新生成”，观察文件跨用户轮保留。

## 一次 Bash 调用

源码中的执行位置是：

```python
subprocess.run(["bash", "-c", command], stdin=subprocess.DEVNULL,
               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
               text=True, errors="replace", timeout=60)
```

- 每次调用启动新的非交互 Bash，从 Agent 的启动目录开始执行。可使用管道、重定向、`cd`、子目录和脚本；`stdin` 不读取课堂输入。
- 文件直接写到命令指定的位置，之后的工具调用和用户轮可继续读取，退出 Agent 后也保留。
- 上一次 Bash 的 `cd`、局部变量和 `export` 不自动带入下一次调用；需要时把目录切换和后续操作写在同一条命令中。
- 正常结束时返回 `exit_code: N` 和 stdout/stderr 合并输出。非零退出码也会回填给模型，供下一步判断。
- 单次调用超过 60 秒时返回“命令超时。”，不附带退出码或部分输出。这是命令超时，不是整项任务的总时限。

模型继续请求工具时，程序继续执行并回填；模型不再请求工具时，打印最终回答并接受下一题。循环没有固定轮数上限。

## 思考模式与完成证据

顶部 `THINKING = True` 同时开启 API 思考模式和 `reasoning_content` 打印；改为 False 关闭。调用为非流式，完整响应返回后才显示思考文本。每次响应最多生成 8192 token，思考与回答共用；SDK 超时 45 秒、最多重试 1 次。

完整 assistant 消息直接加入历史，保留后续工具请求需要的字段。思考文本描述的操作应与实际工具结果分开判断；最终仍要检查退出码、文件内容和独立统计结果。

当前实现直接在主机目录执行 Bash，没有沙箱、命令筛选、输出截断、自动虚拟环境或产物导出。课堂操作定位在 `agent_v5.py` 的 Schema、`run_bash`、结果回填和循环四处。

## 手工运行与教师彩排

手工运行后，可在实际目录打开生成的文件。教师 `verify_live.py` 则复制程序和数据到一次性目录，运行结束后只保留转录、验收统计和产物 SHA；实际产物随执行目录清理。网页 REPLAY 展示的是既有转录，不会重新执行或恢复这些文件。

单独彩排 v5 并保留新的录制：

```bash
rehearsal_dir=$(mktemp -d)
python verify_live.py --stage v5 --output-dir "$rehearsal_dir"
```

需要更新仓库录制时使用 `python verify_live.py --stage v5 --overwrite`，再运行 `python preflight.py` 和 `python build_viewer.py`。当前录制的独立统计验收见 [验证记录](../VALIDATION.md)。
