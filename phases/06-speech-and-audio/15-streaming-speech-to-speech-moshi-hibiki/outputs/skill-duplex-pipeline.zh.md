---
name: duplex-pipeline
description: Pick full-duplex (Moshi) vs pipeline (VAD + STT + LLM + TTS) architecture for a voice-agent workload.
version: 1.0.0
phase: 6
lesson: 15
tags: [moshi, hibiki, full-duplex, voice-agent, streaming]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定工作负载（延迟目标、工具调用需求、语言覆盖范围、硬件预算、云与边缘），输出：

1. 建筑学。全双工（Moshi / GPT-4o 实时 / Gemini Live）与管道（LiveKit + STT + LLM + TTS，第 12 课）。一句话理由。
2. 模型。 Moshi · Hibiki · Hibiki-Zero · Sesame CSM · GPT-4o 实时 · Gemini 2.5 Live · 传统管道。原因。
3. 规模。每个会话 GPU 成本（Moshi 拥有一个槽）、最大并发会话数、冷启动影响。
4. 工具调用路径。如果需要 - 混合管道（双工 + 用于 tool calls 的外部 LLM）或纯管道。解释权衡。
5. 语言覆盖范围。全双工模型的语言支持范围较窄； pipeline继承了LLM的多语言能力。

拒绝需要工具调用/检索的企业 agents 的全双工架构 - Moshi 是一个对话模型，而不是 agent 框架。仅在 250 毫秒以下会话 agents 中拒绝管道 - 阶段加起来。在一个 GPU 上拒绝 Moshi 超过 4 个并发会话 — 命中争用。

输入示例：“语言学习语音伴侣 — 会话流利度练习。英语 + 法语。响应速度 < 250 毫秒。每日活动 10k。”

输出示例：
- 架构：全双工（Moshi）。低于 250 毫秒的延迟要求 + 对话流畅性符合 Moshi 的优势。
- 型号：莫西. EN + FR 均得到良好支持。 CC-BY 4.0 许可证。
- 规模：每 4-6 个并发会话一个 L4 GPU → 峰值时约为 1500 个 GPUs，10k DAU（10% 并发）。使用 Kyutai Pocket TTS + 本地 Whisper 规划设备上的灯光模式以实现安静路径。
- Tool calling：最小——“显示语法提示”和“翻译这个短语”可以通过一个微小的 LLM sidecar 进行路由；大部分互动都是开放式对话，Moshi 的亮点就在于此。
- 语言覆盖：EN + FR（母语）； ES / DE / JP 通过 Hibiki-Zero 改编（每种新语言需要 1000 小时的音频）。
