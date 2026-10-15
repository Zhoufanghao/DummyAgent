# 修改后验证记录

日期：2026-10-15（Asia/Shanghai）。本文件对应当前六个教学Tag；初版记录见docs/archive/VALIDATION-initial.md。

## 三项要求

- 代码、网页、教师讲稿和PPT大纲统一使用 `Pr[token | context]`。旧录制原文保留在归档目录，不修改历史输出。
- 六个版本的公共CLI默认 `max_iterations=100`，允许1—1000；v4/v5按每个用户任务重新计数，达到上限不报告完成。
- 六个版本无参数均自由交互，只有 `--demo` 使用固定示例；`--prompt`（v0）或 `--task`（v1—v5）可做单次自定输入。
- v1—v5保存跨用户轮的双方历史，支持 `:reset`；v0每个前缀独立；`:quit`、EOF、Ctrl-C可结束。
- v3仍只有一次工具请求/执行/回填后回答；v4才引入持续工具反馈循环。
- v5同一会话共享隔离目录，只有demo强制CSV报告验收；自由任务退出时安全导出实际存在的白名单文件。

## 真实API验证

全部调用默认DeepSeek-V4.1-Flash（API ID `deepseek-flash`），请求/响应与源码SHA保存在recordings。

| Tag | 固定demo API次数 | 自由交互 API次数 | 实际核验 |
|---|---:|---:|---|
| v0-token | 1 | 2 | 两个任意前缀互相独立，逐位置真实logprobs及新公式 |
| v1-memory | 4 | 2 | 自由输入Z987并在下一轮恢复；demo保留无历史/有历史对照 |
| v2-chat | 2 | 2 | 自由输入蓝色并在下一轮恢复；system/user/assistant角色正确 |
| v3-tools | 3 | 3 | 18*7经工具得126；下一用户轮从历史恢复126 |
| v4-agent-loop | 4 | 5 | 先17*19再/7；下一任务使用前次结果*2；各任务从Loop 1/100开始 |
| v5-execution | 8 | 6 | 自由三轮：查看CSV列名→写普通文本report.md→跨轮读取；无CSV格式验收，安全导出单个文件 |

- v5 demo在真实macOS Seatbelt沙箱完成生成脚本、执行、检查和导出，独立核验count=10、mean=24.5、max=29、min=20。
- 新版temperature=0真实对照也已重新录制；13份当前录制逐一匹配对应新版Tag的agent.py SHA，7份归档录制仍逐一匹配原Tag。

## 回归与交付

- 完整 `python3 -m unittest discover -s tests -v`：63项全部通过，含原有24项真实沙箱验证/集成检查。
- 新增11项跨六Tag交互回归，覆盖默认交互、跳过空白、退出/EOF/Ctrl-C、demo不读stdin、history/roles/reset、v3单轮工具边界、v4每任务迭代重置、v5共享workspace且不强制publish。
- 新增6项自由产物导出检查：可单独导出任一允许文件、不要求固定统计格式、空目录/空文件无导出、拒绝越界名称及软硬链接。
- preflight逐Tag核对默认交互、demo、默认100轮、真实源码SHA和无SDK回放；网页从更新后的真实Tag构建，来源/转义/复制命令结构测试通过。
- 旧六Tag以原annotated tag对象保留在 `archive/2026-10-15/<tag>`；旧7份录制逐字节归档在recordings/archive/2026-10-15/。
- 自动浏览器file://预览仍受URL策略限制，未绕过；Docker分支未在本机实测。原有文件/网络/进程/超时边界保持。
