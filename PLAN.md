# 课堂精简重构规格

目标：六个独立的 `agent.py` 教学快照，面向泛工科本科生，在 45 分钟内讲清文本续写、上下文、角色、工具、循环与隔离执行。

## 版本与入口

本轮使用 `teaching-cleanup/<阶段ID>` 独立 Tag 命名空间，下表只写阶段 ID；共享的 v0—v5 标签保持原样。v5 是原受限基线的精简参考，正在另行扩展的 Bash 能力暂不合入，待最终 v5 确定后再做精简。

| 阶段 ID | 运行文件 | 核心验收 |
|---|---|---|
| v0-token | `agent.py` | 独立 Completion、12 个 token、真实 logprobs、逐位置候选概率 |
| v1-memory | `agent.py` | 文本 history；第二次请求可见第一轮信息；没有 token 演示 |
| v2-chat | `agent.py` | system/user/assistant messages；没有旧版入口 |
| v3-tools | `agent.py`、`tools.py` | calculator；一次请求与回填后回答，不持续循环 |
| v4-agent-loop | `agent.py`、`tools.py` | calculator；根据实际反馈持续决策；每任务最多 100 轮 |
| v5-execution | `agent.py`、`tools.py` | 仅 Bash；隔离目录、跨轮文件、安全导出；每任务最多 100 轮 |

运行方式统一为 `git switch --detach teaching-cleanup/<阶段ID>` 后 `python agent.py`。只保留自由交互，提示符 `$ `，空白输入跳过，Ctrl+D 结束，Ctrl+C 平稳退出；重新启动即开始全新会话。配置放文件顶部，温度默认 0；密钥与模型覆盖值来自环境。保留 API 超时和重试。

SDK 调用、history、messages、工具分发与循环直接呈现在 `agent.py`。课堂运行不依赖统一参数、兼容分派、录制包装或教师辅助脚本。v5 的沙箱、目录准备与导出合入 `tools.py`；固定 CSV 正确性验收移到教师验证侧。保留 Bash 扩展边界：`BASH` Schema、`execute`、`run_bash`，以及目录准备与导出的 `seed`、`export_outputs`；无需额外框架。

## Git 与教学材料

- 在 `codex/teaching-cleanup` 分支生成六个精简快照，逐阶段验证后创建 `teaching-cleanup/<阶段ID>` 教学 Tag；不更新共享 v0—v5 标签，最终分支内容为本轮 v5 参考版。
- 重构前六 Tag 原样保留为 `archive/2026-10-15/pre-cleanup/<tag>`，旧录制原样移到 `recordings/archive/2026-10-15/pre-cleanup/`；保留第一代归档。
- 网页从真实 Tag 读取源码与相邻差异；复制命令直接切 Tag 并运行 `agent.py`；真实轨迹明确标识 REPLAY。
- README、45 分钟讲稿和 16 页大纲统一为手工输入示例。温度对照通过修改文件顶部常量进行，切换版本前恢复默认值。
- 保留 `preflight.py`、`build_viewer.py`、`chat_template_demo.py` 和测试；真实 API 验证与录制由外部 `verify_live.py` 完成，教师辅助脚本默认解析 `teaching-cleanup/` 命名空间。

## 验证要求

- 六 Tag 独立导出运行，只依赖各自约定的一至两个本地运行文件；检查无跨版本功能或辅助运行模块残留。
- 检查提示符、空白、EOF、中断和普通字符串输入；v0 输入独立，v1/v2 多轮上下文，v3 单次工具边界，v4 每任务轮数重新计数。
- 保留算术参数校验、截断与工具失败处理回归；v5 检查跨轮文件、安全导出、禁网、数据只读、白名单、超时及资源限制，无后端即拒绝执行。
- 逐阶段真实 API 冒烟；v5 手工任务读取 CSV、生成并运行代码、保存结果与报告。外部独立核对 **10 行、平均 24.5°C、最大 29°C、最小 20°C**。
- 录制重新绑定到新命名空间中的真实快照，记录模型、时间、输入、响应与源码 SHA；结果以重新验证为准，不修改旧记录冒充当前验证。网页重建后检查六阶段源码、差异、命令与录制来源。
- 通过、失败、跳过分别记入 `VALIDATION.md`；嵌套沙箱阻止隔离测试时，不把跳过记作通过。

## 事实与安全边界

密钥不打印、不入库、不进入执行环境。候选概率只由 API logprob 取 exp，不重新归一化 top-k；低温不保证正确或逐字复现。Chat Template 只展示明确标注的公开 DeepSeek-V3 历史版本。命令过滤仅是额外检查，实际执行必须有 OS 沙箱或容器隔离。现有新闻日期与来源保留，不引入新的时效性主张。

课程时间：00—04 最终演示；04—11 token；11—17 history；17—22 roles；22—30 tools；30—39 loop 与隔离；39—43 案例；43—45 总结。
