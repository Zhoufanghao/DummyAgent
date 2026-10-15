# 验证记录

记录日期：2026-10-15（Asia/Shanghai）。API 响应原文与调用参数见 `recordings/`；不存认证头。

## v0-token

- 已查询真实 `/models`：`deepseek-flash`、`deepseek-v4-pro`；默认采用前者。
- OpenAI SDK 2.54.0；Python 3.13.1；依赖版本见 requirements-lock.txt。
- `/beta/completions` 实际成功，temperature=0.8、12个token、top-5 logprobs。
- 第一位置候选概率实际为45.5274%、25.5110%、18.8320%等；由返回logprob取exp，未归一化。
- 另先探测temperature=0的响应出现0/-9999，因此主录制采用0.8；哨兵不解释成精确概率0。
- 语法检查和离线回放通过；12-token示例因length停止，明确显示停止原因，不宣称整句完成。

## v1-memory

- 4次真实Completion：独立第二次回复“不知道”；重新提交history后回复“A102”。
- 检查第二次请求确实没有编号、第四次请求确实包含完整用户与助手历史；语法/离线回放通过。

## v2-chat

- 两次真实Chat Completion成功；请求角色顺序分别system/user与system/user/assistant/user，第二次恢复A102。
- 禁用thinking以便展示普通回复；检查每次请求为不可变快照（避免后续append污染录制）。
- 语法、无SDK离线回放和快照回归检查通过。公开V3 Chat Template辅助演示随课程材料交付。
