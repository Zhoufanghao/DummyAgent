# 验证记录

记录日期：2026-10-15（Asia/Shanghai）。API 响应原文与调用参数见 `recordings/`；不存认证头。

## v0-token

- 已查询真实 `/models`：`deepseek-flash`、`deepseek-v4-pro`；默认采用前者。
- OpenAI SDK 2.54.0；Python 3.13.1；依赖版本见 requirements-lock.txt。
- `/beta/completions` 实际成功，temperature=0.8、12个token、top-5 logprobs。
- 第一位置候选概率实际为45.5274%、25.5110%、18.8320%等；由返回logprob取exp，未归一化。
- 另先探测temperature=0的响应出现0/-9999，因此主录制采用0.8；哨兵不解释成精确概率0。
- 语法检查和离线回放通过；12-token示例因length停止，明确显示停止原因，不宣称整句完成。
