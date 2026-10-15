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

## v3-tools

- 真实演示完整3次LLM调用：无工具回答、工具请求、收到Python结果后的回答。
- 本次无工具回答乘积为83809845，真实Python乘积为83810205；只说明本次观察，不宣称模型每次都会算错。
- 工具结果1821960.9782608696；匹配tool_call_id并回填role=tool；最终模型约为1,821,960.98。
- 参数/未知工具/非法AST/除零/幂资源滥用测试通过；离线回放通过。calculator采用Python浮点数，有正常舍入误差。

## v4-agent-loop

- 真实轨迹：先算1821960.9782608696，下一轮以该返回值/3，得到607320.3260869565，第三轮最终汇报。
- 确认下一次API请求包含上一轮tool result；未用框架隐藏循环。
- 单元测试验证观察回填、最大迭代耗尽不报告完成、length截断不充当最终回答。
- 已核实2026-09-10官方更新：deepseek-flash当前对应DeepSeek-V4.1-Flash，所有保留录制均采用该ID。
