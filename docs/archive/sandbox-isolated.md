# 执行工具的安全边界

本文对应 `teaching-cleanup/v5-execution`：原受限基线的精简参考。共享 v0—v5 标签保持原样；正在另行扩展的新版 Bash 能力暂不合入，待最终 v5 确定后再精简。

v5 的 `tools.py` 集中放置 Bash 工具、参数校验、隔离后端、实验目录准备与产物导出；课堂上直接展示 `agent.py` 的决策循环。这里把执行限制单独写清楚，避免把“禁止几个命令”误当作沙箱。

## 使用方式

宿主程序用临时目录建立独立实验工作区，只复制 `data/temperature.csv`。工具调用为 `run_bash(command, workspace, timeout=8)`。切换到 `teaching-cleanup/v5-execution` 后运行 `python agent.py`，在 `$ ` 后输入任务。同一会话持续使用这个目录，下一轮可以读取或修改先前产物；Ctrl+D 或 Ctrl+C 结束会话。再次启动会得到新的实验目录和空白对话。

会话结束时对已有产物进行文件安全检查，安全导出到当前目录 `lab-runs/run-*/` 后清理临时目录。没有生成文件的普通问答也可正常结束。自由交互不强制生成 CSV 报告，不在运行时用固定答案验收任务；固定 CSV 的统计结果和报告由外部教师验证脚本与测试独立核对。检查文件是否安全与检查用户任务是否完成是不同问题，教师仍需结合工具反馈和实际文件判断。

每个任务最多调用模型 100 轮，由 `agent.py` 顶部 `MAX_ITERATIONS` 控制；达到上限即停止，不能据此宣称任务完成。下一条用户任务重新计数，对话历史和实验文件继续保留。命令、文件、超时与 OS 隔离限制不随任务改变。

支持单个前台命令：`python3`、`ls`、`cat`、`pwd`、`head`、`wc`、`printf`、`echo`。推荐：

```bash
python3 - <<'PY'
import csv, statistics
from pathlib import Path
with open('data/temperature.csv') as f:
    values = [float(row['temperature']) for row in csv.DictReader(f)]
text = f'平均值：{statistics.mean(values)}；最大值：{max(values)}；最小值：{min(values)}'
Path('report.md').write_text('# 温度报告\n\n' + text, encoding='utf-8')
print(text)
PY
```

这是一种刻意受限的 Bash 接口。`tools.py` 把上述**字面 Python here-document**转成等价的 `python3 -c SOURCE`，再让 Bash 用 `exec` 替换自身，避免 Bash 为 here-document 创建子进程和临时文件。显示、记录的工具参数保留原始命令。每次调用只有一个前台程序；不支持管道、后台、重定向或多个串接命令。

后续扩展集中在 `tools.py`：用 `BASH` Schema 描述能力，`execute` 校验并分发，`run_bash` 承接执行与隔离；`seed` 和 `export_outputs` 管理目录准备与导出。保留直接函数边界，不引入额外框架。教师预检和真实录制默认解析 `teaching-cleanup/` Tag，录制须重新绑定对应快照后才用于说明本轮行为。

## 真正由操作系统执行的限制

| 项目 | 限制 |
| --- | --- |
| 可读输入 | 隔离实验目录、必要的只读系统/解释器运行库 |
| 可写文件 | 仅 `analysis.py`、`result.json`、`report.md` |
| 输入数据 | `data/temperature.csv` 只读 |
| 宿主用户文件 | 不授予读取和写入权限；宿主目录不作为可写工作区 |
| 网络 | 拒绝网络；macOS 也不开放 Mach 服务 |
| 子进程 | macOS 不授予 `process-fork`；Docker `--pids-limit=1` |
| 环境变量 | 执行程序不接收 API Key；macOS 只传入最小环境，Docker 不转发宿主环境变量 |
| 命令时限 | 默认 8 秒，调用方最多指定 15 秒；到期终止进程组，Docker 另行删除容器 |
| 输出 | 合并 stdout/stderr，边读取边限制到 16 KiB，超限终止 |
| 产物 | 单个文件最大 256 KiB；只允许上述三个产物，不接受符号链接或硬链接 |
| 迭代次数 | 由主程序 Agent Loop 独立限制 |

命令文本会先拒绝 `rm`、`sudo`、`curl` 等明显误操作；模型也可能用 Python 表达同样的行为，所以文本过滤**不构成安全边界**。实际文件、网络、进程访问由下列后端限制。

### macOS：Seatbelt

`/usr/bin/sandbox-exec` 使用 `(deny default)` 配置，只开放少量读取路径、三个输出文件的写入和执行当前程序的权限。没有开放网络、Mach 服务、进程创建和 sysctl。未放行整个 `/System`，因为 `/System/Volumes/Data` 可能形成宿主数据卷的另一条访问路径。

需要注意：它是文件、网络与进程权限沙箱，不是独立虚拟机。macOS 版本没有设置可证明的进程内存配额；课堂代码演示应使用固定可信任务，面对主动对抗的任意代码应选资源约束更完整的容器/虚拟机。

在某些上层沙箱中再次启动 Seatbelt 会出现 `sandbox_apply: Operation not permitted`。`backend_status()` 会实际探测；若失败，`run_bash` 返回 `sandbox_unavailable`，不在宿主直接执行。课堂可在普通终端预检，也可以使用已标注来源的真实运行回放。

### Docker：备用后端

需要本地 Docker、已启动的 daemon，以及提前缓存的 `python:3.12-slim`：

```bash
docker pull python:3.12-slim
```

运行使用 `--network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=1 --memory=128m --cpus=1`，非 root 用户，输入目录只读挂载，仅三个预建输出文件单独以可写方式挂载。执行时使用 `--pull=never`，不会为了临时调用下载镜像。进程超时后，还会调用 `docker rm -f`，因为只终止 Docker CLI 不能保证容器停止。

重构前的本机记录没有验证 Docker 后端；新版本当前验证状态以 [VALIDATION.md](../VALIDATION.md) 为准。换到 Docker 环境后，须运行同一组集成测试再用于课堂。不要把 Docker daemon 配置为远程主机，文件挂载应对应当前本地实验目录。

## 本轮验证与历史证据

本轮移植后，在允许启动本机 macOS Seatbelt 的终端权限下运行隔离测试：**25 项通过、0 项跳过**，包含新增的 Ctrl+C 执行清理回归。Docker 后端仍未实测。完整命令、执行环境与本轮其他验证见 [VALIDATION.md](../VALIDATION.md)。

下面保留重构前的详细实测记录，作为限制设计的历史证据：

- 2026-10-15，macOS Darwin 24.6.0，arm64；Python 3.13；实际后端 `macos-seatbelt`。
- 在允许启动 Seatbelt 的终端权限下运行 `python3 -m unittest discover -s tests -p test_sandbox.py -v`：**24 项通过**。
- 正常路径真实执行 Python `csv/statistics/json/pathlib`，计算测试数据均值 22、最大值 24、最小值 20，并成功保存 Markdown 报告。
- 拒绝验证使用独立临时哨兵文件，不读取真实密钥：宿主文件读取失败、宿主写入失败、输入改写失败、Data 卷别名访问失败、网络失败、`os.fork()` 失败；报告路径不能通过硬链接别名改写输入或宿主文件。
- 超时、16 KiB 输出上限、256 KiB 单文件上限、符号/硬链接检查、无后端时拒绝执行均通过。普通嵌套沙箱内的后端不可用情况也已观察到；该环境应回放，不解除隔离后继续执行。
