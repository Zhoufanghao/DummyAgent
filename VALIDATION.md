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

## v5-execution

- 8轮真实DeepSeek-V4.1-Flash调用（API ID deepseek-flash），实际Seatbelt执行。
- 自然发生的反馈修正：第一轮使用&&组合命令被拒；下一轮自行改为单命令，之后读CSV、生成analysis.py、执行、分别读取result.json/report.md、汇报。未人为注入报错。
- 独立验收：count=10、mean=24.5、max=29.0、min=20.0；CSV未变；报告/生成脚本/JSON已导出并保留examples。
- 46项测试全部通过，包含24项沙箱验证/集成测试，11项产物与失败反馈测试，以及工具、循环、快照、回放和网页测试。
- macOS真实测试覆盖禁网、宿主哨兵读写拒绝、Data卷别名、软硬链接、数据只读、环境密钥不继承、禁子进程、超时、16KiB输出/256KiB文件上限、无后端拒绝执行。Docker分支未在本机验证。
- 修复并回归验证超大整数统计值不会让验收抛OverflowError中止，可作为错误反馈继续循环。

## 最终交付检查

- 六Tag均通过git archive导出和Python -S无SDK离线回放；逐一校验agent.py与录制SHA一致。
- 补录同一v0 Tag、同一Flash模型的temperature=0真实对照，网页与讲稿均可调用。
- 静态网页从真实Tag构建，包含新增/删除/修改颜色与符号、字号切换、真实录制来源；HTML转义与Git来源测试通过。
- 自动浏览器file://预览被URL安全策略拒绝，未绕过，未完成自动视觉检查。
- 已扫描全部项目文件、录制与生成网页：未出现实际API密钥值。
- 教师讲稿与16页PPT内容大纲已核对最终命令、8轮实际修正轨迹、报告路径与45分钟时间分配。
