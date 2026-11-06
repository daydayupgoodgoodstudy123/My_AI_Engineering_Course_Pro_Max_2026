---
name: long-video-strategy-planner
description: Pick brute-context, ring-attention, token-compression, or agentic-retrieval for a long-video understanding task and compute latency + recall expectations.
version: 1.0.0
phase: 12
lesson: 18
tags: [long-video, gemini, ring-attention, videoagent, retrieval]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以视频持续时间、查询复杂性(单一事件与整体摘要)以及开放与封闭的限制,

显示 :

1. 战略选择 粗鲁的文字 环attention (LongVILA), token- 压缩(Video-XL),或 agentic- 检索(视频代理)
2. Token budget会期 * FPS * per-frame-tokens。警告 LLM context.
3. 注意,针头在海雀中 以视频长度百分位数来回想 Gemini 相关时,提交1.5份报告。
4. Latency. Prefill 粗体文字时间; 检索+ VLM agentic.
5. 工程路径, 选择策略的代码片脚架
6. 后退计划。 混合:粗略的全球摘要+ agentic 本地细节 。

艰难的拒绝 :
- 提供2小时的视频 72B型开放。上下文不合适。
- Claiming agentic 检索总是赢的,对于整体总结的问题来说,它会失去 野蛮的背景。
- Recommending token 压缩而不挂税。

拒绝规则 :
- 如果目标是边境召回的90分钟视频(>95%),则拒绝只开放选项并推荐 Gemini 2.5 专业
- 如果用户负担不起工具呼叫环, 请拒绝 agentic- 检索并提议压缩粗体
- 如果用户需要实时( 流到流到流到流到流到流), 拒绝检索( 太慢) 并推荐 streaming Qwen2.5-VL.

产出:一页计划,包括战略、预算、召回、潜伏、工程路径和后退。Gemini 比较时,见A/AC.105/L.50。
