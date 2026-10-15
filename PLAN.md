# 实施计划

目标：用同一个 `agent.py` 的六次演进，讲清文本续写、上下文、角色、工具、循环、隔离执行。面向泛工科本科生，45分钟。

## 版本与验收

| 顺序 | Tag | 唯一新增机制 | 验证后提交条件 |
|---|---|---|---|
| 0 | v0-token | 原始 Completion + 真实 logprobs | DeepSeek 实际请求成功；逐位置展示上下文/候选/概率/选中 token；录制可回放 |
| 1 | v1-memory | history 文本 | 独立调用与带历史调用对照；实验编号恢复；保留token演示 |
| 2 | v2-chat | 结构化 messages | system/user/assistant 多轮对话；官方开源Chat Template示意与API边界说明 |
| 3 | v3-tools | 一轮工具调用 | schema、tool call、Python执行、tool result、最终回答都可见；参数验证 |
| 4 | v4-agent-loop | 直接可见的循环 | 多步工具依赖与反馈；最大迭代；截断/失败不冒充完成 |
| 5 | v5-execution | 受限Bash | OS隔离、禁网、目录限制、超时、危险操作防护；CSV→代码→执行→检查→Markdown |

每版先运行本地检查和真实API演示，再 `git commit`、创建对应 annotated tag。失败先修复，不提前占用Tag。公共支持代码处理录制和错误，关键SDK调用、history、messages、tool dispatch、循环始终在教学代码中可读。

## 交互与参数修订

- 课堂概率统一写作 `Pr[token | context]`，表示给定上下文时下一个 token 的条件概率。
- 六个版本默认自由交互；`--demo` 明确选择固定示例。v0 每次接受独立续写前缀；v1 文本 history、v2 结构化 messages 均支持多轮；v3 保留跨用户轮历史但每轮只进行一次工具调用与回填；v4 每个任务进入循环；v5 在同一个隔离目录支持多轮任务。
- `:quit` 退出交互；有历史的版本用 `:reset` 清空模型上下文。v5 重置对话不删除实验产物。
- v0 的 `--prompt`、其他版本的 `--task` 可执行一次自定输入。它们无需 `--demo`，结束后直接退出。
- v4/v5 每个任务默认最多 100 轮，`--max-iterations` 范围 1—1000；达到上限保持未确认完成状态。
- v5 的固定 CSV 数值验收只用于 `--demo`；自由任务仍保留目录、文件、命令、超时和 OS 隔离限制。
- 修订时先保留旧 Tag 到 `archive/2026-10-15/<原Tag>`，旧录制移入 `recordings/archive/2026-10-15/`；逐阶段验证、提交、替换六个课程 Tag，再从真实 Tag 重建网页。新代码不得与旧录制冒充同一次验证。

## 并行交付

1. 官方文档核实：OpenAI SDK、DeepSeek Completion/logprobs/tool calling；模型ID以实际可用探测为准。
2. 可视化：标准库Git读取六个Tag、difflib生成静态网页，展示真实代码、差异、能力、录制输出。
3. 课程：45分钟教师讲稿、PPT逐页内容大纲、2—3个官方新闻案例及日期/来源。
4. 最终检查：六Tag导出独立运行；离线回放明确标识；最终统计结果核对；网页浏览器检查；密钥不入库。

## 稳定性与事实边界

- API key只从环境读取；不把环境变量、凭据写入录制。
- 限制请求超时、输出长度和Agent步数；固定CSV；低temperature不保证完全确定性。
- 保存真实API请求/响应和终端转录；回放不调用API也不执行历史命令。
- 候选概率仅由API logprob取exp；不对top-k重新归一化，不声称覆盖完整词表。
- Chat Template只展示一个明确标注的开源模型，不声称是远程API当前内部格式。
- 命令过滤只作额外防护；实际执行必须由OS沙箱/容器隔离，无后端则拒绝。

## 课程时间

00—04最终演示；04—11 token；11—17 history；17—22 roles；22—30 tools；30—39 loop与隔离；39—43案例；43—45总结。
