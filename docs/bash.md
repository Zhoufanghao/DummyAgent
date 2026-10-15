# Bash 执行方式

`agent_v5.py` 是独立的 Bash Agent。它在启动程序的当前目录中直接执行模型请求的命令：

```python
subprocess.run(["bash", "-c", command], stdin=subprocess.DEVNULL,
               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
               text=True, errors="replace", timeout=60)
```

`run_bash(command)` 将 stdout 与 stderr 一起作为工具结果交回模型；单次命令超时为 60 秒。模型看见结果后，在同一个 `while True` 循环里继续请求工具或给出最终回答。代码不设置循环轮数上限。

文件直接保存在命令所在目录，退出后仍然保留。例如从包含 `data/temperature.csv` 的项目根目录启动：

```bash
python agent_v5.py
```

在 `$ ` 后输入：

```text
读取 data/temperature.csv，计算温度平均值、最大值和最小值，保存 report.md。先检查数据，再生成 analysis.py 并执行，最后重新读取检查文件。
```

Bash 工具没有额外的沙箱、命令或文件白名单，也不准备临时实验目录、执行产物导出、自动创建虚拟环境或配置网络代理。执行行为与从启动目录运行相应 Bash 命令一致。

课堂只需定位 `agent_v5.py` 中的工具 Schema、`run_bash`、工具结果回填和循环。后续 Bash 功能可直接在这几个位置扩展。
