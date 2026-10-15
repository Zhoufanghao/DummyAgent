# 课堂精简重构验证记录

日期：2026-10-15（Asia/Shanghai）。重构前的验证记录保存在 docs/archive/VALIDATION-pre-cleanup.md；初版记录仍在 docs/archive/VALIDATION-initial.md。

## 运行结构

六个阶段分别维护自身教学机制；v0—v2 只运行 agent.py，v3—v5 再带 tools.py。无 CLI 参数、兼容模式、录制包装或聊天命令；输入提示为 `$ `，EOF/Ctrl+C 结束。教师工具不参与课堂运行。

## 验证进度

- 重构前基线：63项，44通过、19项受嵌套沙箱限制跳过。
- 合并后的原有隔离回归：本机获准的 Seatbelt 执行环境中24项通过、无跳过；Docker未实测。
- 六阶段候选源码的交互、history/messages、单轮工具与反馈循环已完成离线验证。
- Git教学快照、真实API录制与网页验收将在最终工作区记录结果；本阶段快照中的这份文件不预先宣称通过。

录制必须绑定实际提交及运行文件SHA；旧Tag与旧录制原样保留在 archive/2026-10-15/pre-cleanup 命名空间和对应recordings归档目录。不得用修改旧SHA或转录的方式替代真实验证。
