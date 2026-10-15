# 课堂精简重构验证记录

日期：2026-10-15（Asia/Shanghai）。重构前的记录保存在 `docs/archive/VALIDATION-pre-cleanup.md`；初版记录仍在 `docs/archive/VALIDATION-initial.md`。

## 当前状态

已在 `codex/teaching-cleanup` 分支保存六个精简教学提交，工作区为 v5。用户确认本轮继续优化原版，新 v5 在另一工作区独立迭代，稳定后再精简。本分支使用 `teaching-cleanup/<stage>` 独立标签，现有共享课程标签全部保持不动。六个独立教学 Tag 已创建并完成重新验证；当前 v5 为原受限基线的精简参考，新版扩展能力的合入与精简留待其稳定后进行。

## 教学代码与真实 API

| 阶段 | 提交 | agent.py 行数 | tools.py 行数 | 真实 API 次数 |
|---|---|---:|---:|---:|
| v0-token | 0c226f646a6d | 63 | 无 | 2 |
| v1-memory | 5ee1ddc333ee | 51 | 无 | 2 |
| v2-chat | 11de3eed9b0d | 51 | 无 | 2 |
| v3-tools | 20be0a65e7bc | 73 | 57 | 3 |
| v4-agent-loop | 269b1a4c1ee6 | 76 | 57 | 4 |
| v5-execution | 8461922b285d | 94 | 307 | 7 |

全部实际请求及返回模型均为 `deepseek-flash`。当前六份 `recordings/<stage>.json` 保存真实输入、请求快照、响应、耗时、提交 SHA、运行文件 SHA 与终端转录；均为自由交互，两轮输入后 EOF，不通过内置 demo 或录制入口运行。

- v0 两个前缀独立续写，逐位置展示真实 logprobs。12 token 的 `length` 是有意限制，不能套用聊天阶段的截断失败判断。默认温度 0 本次返回 0/-9999，不能解释为原始模型完整概率分布。
- v1/v2 第二轮实际恢复 A102，并核对提交内容确实包含双方历史及相应消息角色。
- v3 计算后回填一次工具结果再回答，下一轮追问仍可见上轮结果。
- v4 第一项任务经历两轮独立 calculator 决策，第二项任务从新一轮计数开始。
- v5 实际在 macOS Seatbelt 中读取 CSV、生成 analysis.py、独立执行脚本、分别读取 result.json/report.md，再在第二用户轮重新读取同一组产物，最后 EOF 安全导出。
- v5 外部独立核对：count=10、mean=24.5°C、max=29°C、min=20°C。三份产物 SHA 保存在录制的 validation 字段中；固定答案未写入课堂 Agent。

## 回归与结构

- 完整回归 **82 项全部通过，无失败、无跳过**，实际从 Git 导出六阶段，未拿工作区冒充历史版本。新增的两项还核对了实际本地模块依赖与独立命名空间解析。
- 其中隔离与中断检查 **25 项通过，无跳过**。普通受限执行环境会跳过其中 19 项；本轮最终结果在获准的本机 Seatbelt 环境实际运行，包含禁网、宿主读写拒绝、只读数据、链接防护、资源/输出限制与超时。
- 新增 Ctrl+C 执行中断回归：子进程组先终止、回收并关闭输出管道，再传播中断，避免工作区导出/清理后仍有进程写入。
- 六阶段结构预检通过：v0—v2 只有 agent.py，v3—v5 另带 tools.py；旧运行辅助模块均不存在；无 argparse、兼容模式、录制包装及聊天命令处理。
- 提示统一为 `$ `，空白跳过，EOF/Ctrl+C 平稳结束。旧命令字符串作为普通用户输入，历史不被特殊清空。
- 合并后的独立教师验收覆盖 JSON 字段/数值、报告标签与单位，以及导出文件安全检查。没有可用隔离后端时仍拒绝执行。
- Docker 分支本轮未实测，不将其记为通过。

## 网页与证据保留

默认独立教学 Tag 的离线预检、运行文件 SHA 和录制来源检查全部通过。另在一次性克隆中实际切换全部六个 Tag，检查运行文件数量、拒绝旧参数及生成页面跨切换保留。网页已从六个真实独立 Tag 构建，并通过浏览器检查六阶段切换、源码文件选择、相邻差异、对应真实轨迹、两行启动命令复制和 18px 投影字号。REPLAY 明确显示，六阶段无历史来源不匹配提示。

生成的 `web/index.html` 不再跟随 Tag 版本切换，避免课堂切换源码时覆盖已构建页面；构建器和阶段说明仍纳入 Git。新录制仅在真实验证成功后写入，不改旧记录的 SHA 或转录。

本轮开始时的六个旧 annotated Tag 对象原样保留在 `archive/2026-10-15/pre-cleanup/<tag>`，13 份旧录制已逐字节核对并保留在对应 recordings 归档目录。此前第一代归档继续保留。并行更新的 main/v5 未被覆盖。

## 使用与扩展

```bash
git switch --detach teaching-cleanup/v0-token
python agent.py
# Ctrl+D 结束后再切换其他 teaching-cleanup/<stage>
git switch codex/teaching-cleanup
```

本轮没有写入另一工作区的 main 或共享 v0—v5 Tag。首轮候选的真实录制也保存在 `recordings/archive/2026-10-15/cleanup-candidates/`，对应原始提交未改写。

Bash Schema、`execute`/`run_bash`、`seed`/`export_outputs` 分别负责工具接口、执行和文件生命周期，未来新版 v5 的能力可沿这些边界移植；课堂 Agent 不增加版本兼容或插件分派框架。
