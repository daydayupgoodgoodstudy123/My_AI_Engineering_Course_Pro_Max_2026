---
name: realtime-voice-pipeline
description: Pick transport, VAD, streaming STT, LLM, streaming TTS, and orchestration for a target end-to-end latency.
version: 1.0.0
phase: 6
lesson: 11
tags: [voice-agent, livekit, pipecat, silero, streaming, latency]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定目标（延迟 P50/P95、语言、渠道、离线与云端、通话量），输出：

1. 运输。 WebRTC（LiveKit / Daily）·WebSocket·SIP 中继（Twilio / Telnyx）。原因与抖动容限+用例有关。
2. VAD+轮流。 Silero VAD（开放，99.5% TPR）·Cobra（商业）·LiveKit 转弯检测器。阈值、最短语音持续时间、沉默残留。
3. Streaming STT。 Parakeet TDT（最快打开）·Kyutai STT（带同花技巧）·Deepgram Nova-3（API，~150 ms）·Whisper-streaming。原因。
4. LLM + streaming。在 TTS 启动之前固定前 20 个 tokens。模型 + streaming 配置 + guardrails 用于 prompt injection。
5. Streaming TTS。 Kokoro-82M（约 100 毫秒 TTFA）·Orpheus·Cartesia Sonic·ElevenLabs Turbo。语音包或克隆防护（第 8 课）。
6. Orchestration。 LiveKit Agents·Pipecat·Vapi·Retell·定制Rust。原因与团队技能+规模有关。
7. Observability。 P50/P95/P99每阶段直方图；误报中断率；掉话率； WER 随叫随到样品。

拒绝部署在 STT 之前缓冲整个话语。拒绝不流式传输的 TTS。按平均延迟拒绝 evaluation — 需要 P95。每月拒绝管理平台（Vapi / Retell）超过 10 万分钟，无需与构建您自己的平台进行成本比较。

输入示例：“用于汽车保险报价的语音 agent。< 500 毫秒 P95。英语，美国。每周 50k 分钟。合规性：HIPAA 相关（日志中没有 PII）。”

输出示例：
- 传输：LiveKit Agents + Twilio SIP。 HIPAA 模式选择加入已在呼叫中心规模得到验证。
- VAD：Silero VAD @ 阈值 0.45，最小语音 220 毫秒，静音残留 400 毫秒。 LiveKit 转弯检测器覆盖。
- STT：Deepgram Nova-3 英语（~150 毫秒 P95）；如果需要本地审计，则回退到 Parakeet-TDT。
- LLM: GPT-4o streaming 通过 OpenAI 实时 API;使用后置过滤器防范 prompt injection；将第一个 20 tokens 固定到 TTS。
- TTS：Cartesia Sonic 2（~150 ms TTFA，未使用语音克隆 - 预定义语音）。
- Orchestration：LiveKit Agents。 Observability 通过 Hamming AI 进行生产。
- 日志：在持久化之前使用正则表达式 + NER 剥离 CVV / SSN / DOB。保留30天。
