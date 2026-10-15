# 执行工具的安全边界

`sandbox.py` 是辅助模块；课堂上仍直接展示 `agent.py` 的决策循环。这里把执行限制单独写清楚，避免把“禁止几个命令”误当作沙箱。

## 使用方式

宿主程序用 `tempfile.mkdtemp(prefix="agent-lab-")` 建立独立实验目录，只复制 `data/temperature.csv`。工具调用为 `run_bash(command, workspace, timeout=8)`。`v5-execution` 默认自由交互，同一会话持续使用这个目录；`:reset` 清空模型上下文，保留实验文件，`:quit` 结束会话。`--task` 执行一个自定任务后退出，`--demo` 才使用固定温度报告任务。

自由交互和 `--task` 不强制生成 CSV 报告；会话结束时对已有产物进行文件安全检查，安全导出后清理临时目录。没有生成文件的普通问答也可正常结束。只有 `--demo` 要求 `validate_workspace(workspace)` 核对固定数据的统计值、结果文件和报告，再导出产物。检查文件是否安全与检查用户任务是否完成是不同问题；自由任务仍须结合工具反馈和实际文件判断结果。

每个任务默认最多 100 轮模型调用，`--max-iterations` 可设为 1—1000；达到上限即停止，不能据此宣称任务完成。自由交互不会放宽下面的命令、文件、超时或 OS 隔离限制。

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

这是一种刻意受限的 Bash 接口。辅助模块把上述**字面 Python here-document**转成等价的 `python3 -c SOURCE`，再让 Bash 用 `exec` 替换自身，避免 Bash 为 here-document 创建子进程和临时文件。显示、记录的工具参数保留原始命令。每次调用只有一个前台程序；不支持管道、后台、重定向或多个串接命令。

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

本次机器没有 Docker；此后端尚未在本机验证。换到 Docker 环境后，必须运行同一组集成测试后再用于课堂。不要把 Docker daemon 配置为远程主机，文件挂载应对应当前本地实验目录。

## 本次实测记录

- 2026-10-15，macOS Darwin 24.6.0，arm64；Python 3.13；实际后端 `macos-seatbelt`。
- 在允许启动 Seatbelt 的终端权限下运行 `python3 -m unittest discover -s tests -p test_sandbox.py -v`：**24 项通过**。
- 正常路径真实执行 Python `csv/statistics/json/pathlib`，计算测试数据均值 22、最大值 24、最小值 20，并成功保存 Markdown 报告。
- 拒绝验证使用独立临时哨兵文件，不读取真实密钥：宿主文件读取失败、宿主写入失败、输入改写失败、Data 卷别名访问失败、网络失败、`os.fork()` 失败；报告路径不能通过硬链接别名改写输入或宿主文件。
- 超时、16 KiB 输出上限、256 KiB 单文件上限、符号/硬链接检查、无后端时拒绝执行均通过。普通嵌套沙箱内的后端不可用情况也已观察到；该环境应回放，不解除隔离后继续执行。
