# 单快照教学重构验证记录

日期：2026-10-15（Asia/Shanghai）。上一轮 Tag 版记录见 `docs/archive/VALIDATION-tagged-stages.md`，原隔离方案见 `docs/archive/sandbox-isolated.md`。

## 六份独立脚本

| 文件 | 行数 | 教学主线 |
|---|---:|---|
| agent_v0.py | 38 | 独立 Completion、真实 logprobs、上下文与候选概率 |
| agent_v1.py | 31 | 保存并重发双方文本 history |
| agent_v2.py | 31 | system/user/assistant messages |
| agent_v3.py | 50 | calculator、一次工具执行与回填后回答 |
| agent_v4.py | 48 | calculator、连续工具反馈循环 |
| agent_v5.py | 61 | Bash 执行、命令结果反馈循环 |

六份代码共259行，处于同一快照，均只依赖标准库与 OpenAI SDK。工具直接内联，不导入其他课堂文件或教师工具；旧 `agent.py`、`tools.py` 已删除。

运行入口直接为 `main()`，仅在文件末尾处理 EOF/Ctrl-C；Bash 另处理命令超时。没有 CLI、密钥预检查、通用错误包装、finish_reason 检查、工具数量限制或恢复分支。v3/v4 直接用 eval 计算表达式；v4/v5 无固定循环次数上限。默认温度0、v0生成12个token；SDK为非流式，Chat关闭thinking，超时45秒、最多重试1次。

## 行为验证

完整测试 **41项全部通过，无失败、无跳过**：

- 六脚本交互与配置10项：独立依赖、跳过空白、多轮输入、双方历史、消息角色、真实概率转换、v3单轮工具边界、EOF/Ctrl-C及模型调用期间中断。
- calculator与反馈循环6项：算式计算、原始Python错误传播、Schema参数、工具结果进入下一次请求、v4连续101次工具请求后正常回答、v5完成一项任务后接受下一项。
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

已逐一真实运行六份脚本，各输入两轮后EOF；使用请求模型 `deepseek-flash`。新记录保存为 `recordings/v0.json`—`recordings/v5.json`，绑定实际源文件名和SHA。所有源码SHA与当前文件一致。

- v0 的两个前缀独立续写，逐位置展示API返回的logprobs；温度0本次仍有0/-9999显示，不解释为完整模型分布。
- v1/v2 第二轮均实际恢复 A102，输出中的history/messages包含此前双方内容。
- v3 实际调用calculator并回填786.1550561797753，再在下一轮恢复结果。
- v4 先计算1821960.9782608696，再根据工具结果除以3得到607320.3260869565；下一用户轮保留两步结果。
- v5 实际使用完整Bash的cd、组合命令、heredoc及重定向：读取CSV、写analysis.py、独立执行脚本、读取result.json/report.md；第二用户轮重新读取同一组文件。
- 教师独立读取产物确认 **count=10、mean=24.5°C、max=29°C、min=20°C**；数据未改动，三个实际产物的SHA写入录制。固定答案未进入课堂Agent。

录制是原始程序stdout/stderr合并转录，不是完整SDK请求/响应归档；`model_requested`只表示请求配置，不冒充返回模型。输入单独存于inputs字段，未把人工回显混入transcript。教师验收结果存于validation字段，不修改原始程序输出。

彩排在一次性目录运行源码的逐字节副本，数据由教师脚本复制。课堂 `agent_v5.py` 本身直接操作启动目录，无临时实验目录、沙箱、白名单、自动虚拟环境或产物导出。

## 网页与保留证据

网页已从当前六份文件重建，并在浏览器实际检查全部阶段：源码与相邻差异、独立运行命令、两条保存输入、REPLAY标识及来源SHA均正确，无来源不匹配提示；复制命令与18px投影字号工作正常。页面不查询Git，也不执行API或历史命令。

原Tag版六份录制原样保存在 `recordings/archive/2026-10-15/before-single-files/`，已与原Git内容逐字节核对；原隔离说明也逐字节保存。既有历史与Tag仅供追溯，本轮没有创建或更新教学Tag，也没有修改另一工作区及其新版v5。
