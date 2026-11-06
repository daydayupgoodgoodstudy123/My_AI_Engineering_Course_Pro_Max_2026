---
name: prompt-caching-planner
description: Design a cache-friendly prompt layout and pick the right provider caching mode.
version: 1.0.0
phase: 11
lesson: 15
tags: [llm-engineering, caching, cost]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 prompt (系统+工具+ few-shot + 检索 +历史 + 用户)和使用配置(要求每小时、TTL需要、提供者),输出:

1. 布局。重新排序区域,标记一个缓存断点;解释哪些区域稳定,哪些区域不稳定。
2. 提供模式 Anthropic cache_control, OpenAI 自动,或 Gemini 缓冲器,从TTL和再利用模式中说明理由。
3. 平衡。 期望在 TTL 中读取每部文字; 净成本与数学不相容 。
4. 核实计划。_read_输入_第二次相同请求时的符号 > 0; 仪表板除以缓存和未切换的 tokens.
5. 失败模式。 请列出此设置中缓存会丢失的三个最可能的原因( 动态时间戳、 工具重排序、 近似重复的文本) 以及您如何防止这些原因 。

拒绝发送将动态字段置于断点之上的缓存计划。 拒绝在不重复计算的情况下启用 1 h TTL, 使 2x 写溢价得到偿还 。
