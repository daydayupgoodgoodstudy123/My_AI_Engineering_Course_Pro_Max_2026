---
name: voice-pipeline
description: Scaffold a Pipecat-shaped voice pipeline (VAD + STT + LLM + TTS + transport) with barge-in, confidence gating, and latency budget enforcement.
version: 1.0.0
phase: 14
lesson: 22
tags: [voice, pipecat, livekit, webrtc, latency]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以语音产品(语言、运输、供应商)为规格,架设了基于框架的管道。

显示 :

1. `Frame` 类型 `kind`, `payload`, `direction` (下游/上游)。
2. Processors: `VAD`, `STT`, `LLM`, `TTS`, `Transport`。每个 `process(frame)`.
3. `link()` 帮助链链处理器向前和向后。
4. 取消框架处理: UPSTREAM 路径从传输到 TTS 到 LLM 转到STT,在每个阶段都放弃待完成的工作。
5. 观察员:每个阶段的潜伏度;通过处理器,每框架发出一个OTel横穿(第23条)。
6. STT上的信任门:低于门槛值,发出“请重复”文本框,而不是文字记录。

艰难的拒绝 :

- 管道没有 UPSTREAM 处理。 插座不能被允许使用 。
- LLM 电话没有 streaming。第一个token 隐居占支配地位;必须紧紧地排队。
- 将错误的记录输入 LLM 产生错误的答复。

拒绝规则 :

- 如果冷藏的端到端的延迟时间超过1500米,则拒绝发运。 优化链条或使用多式代理( LiveKit 直接投递) 。
- 如果产品是电话第一,而管道没有SIP适配器,则拒绝。通过LiveKit SIP或平台(Vapi/Retell)的路线。
- 如果产品携带PII音频,在运输过程中没有加密,则拒绝。

输出: `frames.py`, `processors.py`, `pipeline.py`, `observers.py`, `README.md` 解释潜伏预算、 驳船设计、 运输选择。 结尾处的“ 下一步读什么” 指向课程 23 (OTel), 课 24 ()observability 后端),或 WebRTC 特定内容的 LiveKit 文档。
