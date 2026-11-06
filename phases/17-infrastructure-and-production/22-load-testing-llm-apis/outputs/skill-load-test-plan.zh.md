---
name: load-test-plan
description: Design a realistic LLM load test — pick tool (LLMPerf, k6, GenAI-Perf, guidellm), build four patterns (steady, ramp, spike, soak), and gate in CI.
version: 1.0.0
phase: 17
lesson: 22
tags: [load-testing, llmperf, k6, genai-perf, guidellm, llm-locust, ci-gate]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于工作量(终点、TTFT/TPOT/error的SLA)、目标规模(货币、RPS)和CI姿态(PR门或只放出),产生一个负载测试计划。

显示 :

1. 工具. LLMPerf 用于基准运行; k6+ streaming 光学界面门扩展; NVIDIA 引用运行的 GenAI-Perf; 大合成的指南。 LLM- 卢克斯,只要已经上卢克斯了
2. Prompt 平均 + stddev 输入 tokens 使用实际流量(如果有的话)或已公布的发行量( 共享 GPT / HumanEval) 。 Forbird- roll- with- 1-prompt.
3. 四个模式,稳住,斜坡,刺,泡泡,每个模式:目标RPS,持续时间,预期失败模式。
4. 光学控制门。具体阈值:TTFT P95 < X, 5xx < 5%,TPOT < Y. 运行时间/公关:3-5分钟。
5. Metric alignment。请注意报告工具是GenAI-Perf型(ITL不包括TTFT)还是LLMPerf型(ITL包括TTFT)。选择一个并保持一致。
6. 产出:一个致力于检索的脚本文件(k6 JS, LLMPerf CLI)。

艰难的拒绝 :
- 装有制服的装入测试 prompts拒绝 - 数字是谎言
- 装入测试 streaming 支持。 LLM 终点为 streaming 默认。
- 比较工具之间的数字,而不承认衡量定义的差异。

拒绝规则 :
- 如果团队打算 运行Locust股票没有 LLM防弹扩展,拒绝 盖尔陷阱
- 如果CI门预算低于每公关60秒,
- 如果 prompt 分发数据不详,需要有文件记载的公开分发(分享),并注明这一假设。

输出: 带有工具的一页计划, prompt 分布,四个模式,目标,CI门阈值, alignment。以单一的 CI 输出结束: 公关绿色, 只有当所有阈值都达到时, 3 运行稳定 。
