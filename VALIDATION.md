# 单快照教学重构验证记录

日期：2026-10-15（Asia/Shanghai）。上一轮 Tag 版记录见 `docs/archive/VALIDATION-tagged-stages.md`，原隔离方案见 `docs/archive/sandbox-isolated.md`。

## 六份独立脚本

| 文件 | 行数 | 教学主线 |
|---|---:|---|
| agent_v0.py | 39 | 独立 Completion、真实 logprobs、上下文与候选概率 |
| agent_v1.py | 32 | 保存并重发双方文本 history |
| agent_v2.py | 32 | system/user/assistant messages |
| agent_v3.py | 51 | calculator、一次工具执行与回填后回答 |
| agent_v4.py | 49 | calculator、连续工具反馈循环 |
| agent_v5.py | 62 | Bash 执行、命令结果反馈循环 |

六份代码共265行，处于同一快照，均只依赖标准库、OpenAI SDK 和提供交互输入的 prompt_toolkit。工具直接内联，不导入其他课堂文件或教师工具；旧 `agent.py`、`tools.py` 已删除。

运行入口直接为 `main()`，仅在文件末尾处理 EOF/Ctrl-C；Bash 另处理命令超时。没有 CLI、密钥预检查、通用错误包装、finish_reason 检查、工具数量限制或恢复分支。v3/v4 恢复直接 `eval(expression)`，不做数学符号转换；乘方使用 Python 的 `**`。v4/v5 无固定循环次数上限。默认温度0、v0生成12个token；SDK为非流式，Chat关闭thinking，超时45秒、最多重试1次。

六版统一使用 `prompt_toolkit.prompt("$ ")`。支持 bracketed paste 的终端中，粘贴内的换行属于同一条消息，粘贴结束后按 Enter 才提交；没有添加输入包装或本地共享模块。

## 行为验证

完整测试 **45项全部通过，无失败、无跳过**：

- 六脚本交互与配置10项：独立依赖、跳过空白、多轮输入、双方历史、消息角色、真实概率转换、v3单轮工具边界、EOF/Ctrl-C及模型调用期间中断。
- 真实终端输入2项：每项覆盖全部六版，共12个PTY会话。中文多行、空行和混合CRLF/LF粘贴在Enter前不提交；Enter后保留换行且仅调用一次SDK；继续验证空白跳过、普通单行、Ctrl+D及未提交内容时的Ctrl+C。prompt_toolkit真实运行，仅SDK为离线fixture。
- calculator与反馈循环8项：算式计算、Python `**`乘方及优先级、长算式实际执行与回填、原始Python错误传播、Schema参数、工具结果进入下一次请求、v4连续101次工具请求后正常回答、v5完成一项任务后接受下一项。
- 直接Bash6项：启动目录与文件原位保留、管道/重定向/子目录、stderr合并与非零退出、stdin不抢占课堂输入、超时反馈、非UTF-8输出。
- 教师统计验收6项：基于实际CSV独立计算、结果字段/数值、报告标签和单位；允许工作目录同时存在其他文件。
- 程序录制7项：实际子进程输出与EOF、源码SHA、无Git/固定内部接口依赖、失败不保存成功记录、未知请求模型不伪造、v5数据及产物SHA。
- 网页6项：普通目录读取、相邻源码差异、文本转义、源码变化标记、缺失文件及录制类型检查。

测试命令：

```bash
python -m unittest discover -s tests -v
python preflight.py
```

## 真实程序彩排

已逐一重新真实运行六份脚本，各输入两轮后EOF；使用请求模型 `deepseek-flash`。新记录保存为 `recordings/v0.json`—`recordings/v5.json`，绑定实际源文件名和SHA。所有源码SHA与当前文件一致。教师脚本按 bracketed paste 边界提交各题，v3/v4 第一题的两处换行作为同一条输入保留。

- v0 的两个前缀独立续写，逐位置展示API返回的logprobs；温度0本次仍有0/-9999显示，不解释为完整模型分布。
- v1/v2 第二轮均实际恢复 A102，输出中的history/messages包含此前双方内容。
- v3/v4 使用完全相同的两道观察依赖题。取末六位再立方题中，v3 只执行第一步，后续调用以助手正文中的 DSML 文本出现，没有执行或最终答案；v4 实际执行两次工具调用，得到 `256373415452969682`。
- 奇偶分支再求余题中，v3 同样止于第一步真实工具结果；v4 观察偶数结果后选择分支，实际执行三次调用，最终余数为 `499882649`。两题标准值均由教师侧整数运算独立核对；题面见 `docs/loop_examples.md`。v3 的观察结论是“未完成”，不是已产生错误数值。
- v5 实际通过Bash读取CSV、写analysis.py、独立执行脚本、读取result.json/report.md；第二用户轮重新读取同一组文件。
- 教师独立读取产物确认 **count=10、mean=24.5°C、max=29°C、min=20°C**；数据未改动，三个实际产物的SHA写入录制。固定答案未进入课堂Agent。

录制是原始程序stdout/stderr合并转录，不是完整SDK请求/响应归档；`model_requested`只表示请求配置，不冒充返回模型。完整输入另存于inputs字段；终端库自身的输入回显和管道彩排时的非TTY提示按原样保留，教师脚本不补写或清洗转录。教师验收结果存于validation字段，不修改原始程序输出。

彩排在一次性目录运行源码的逐字节副本，数据由教师脚本复制。课堂 `agent_v5.py` 本身直接操作启动目录，无临时实验目录、沙箱、白名单、自动虚拟环境或产物导出。

## 网页与保留证据

网页已从当前六份文件与新录制重建，通过网页构建回归及来源预检。此前浏览器检查过全部阶段、复制命令与18px投影字号；本轮没有重做浏览器交互检查。页面不查询Git，也不执行API或历史命令。

原Tag版六份录制原样保存在 `recordings/archive/2026-10-15/before-single-files/`，已与原Git内容逐字节核对；原隔离说明也逐字节保存。既有历史与Tag仅供追溯，本轮没有创建或更新教学Tag，也没有修改另一工作区及其新版v5。

乘方修复前的 v3/v4 录制原样保存在 `recordings/archive/2026-10-15/before-caret-power/`；修复后、替换为同题对照前的录制原样保存在 `recordings/archive/2026-10-15/before-loop-examples/`。新的课堂录制来自实际重新运行，未修改旧输出或替换旧 SHA 冒充运行结果。

本轮输入调整前的六份录制原样保存在 `recordings/archive/2026-10-15/before-multiline-input/`。当前脚本已撤回乘方符号兼容逻辑，案例与彩排统一使用 Python 表达式 `**`。

长算式 `((12345 * 6789 - 9876 * 5432) / 3 + 2468 * 1357) * 7 - 123**3` 的精确值为 `91964802`，两个 calculator 返回 `91964802.0`；该式经过模拟真实工具请求的执行与回填回归。
