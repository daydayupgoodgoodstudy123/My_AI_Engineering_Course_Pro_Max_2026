---
name: vad-tuner
description: Pick VAD model, threshold, silence hangover, pre-roll, and turn-detection strategy for a voice agent.
version: 1.0.0
phase: 6
lesson: 14
tags: [vad, silero, cobra, turn-detection, flush-trick]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定工作负载（消费者/呼叫中心/边缘/可访问性；噪音概况；语言组合；延迟），输出：

1. VAD。 Silero VAD（默认）·Cobra（商业精度）·pyannote 分割（二值化级）·WebRTC VAD（传统/小型）。一句话理由。
2. Parameters。阈值 (0.3-0.5)、最小语音 (200-300 毫秒)、沉默宿醉 (400-800 毫秒)、预滚动 (250-500 毫秒)。
3. 语义转向检测。是否启用（LiveKit 转弯检测器或自定义 MLP）。原因与预期的用户语音模式相关。
4. 冲洗技巧。是否启用（如果 STT 支持 — Kyutai / Deepgram）。预期节省延迟。
5. 守卫。拒绝短于最短持续时间的语音；始终保持预卷；每个用户的沉默宿醉覆盖上限；如果 VAD 服务关闭，则失败打开（将所有内容视为语音）。

拒绝仅使用能源 VAD 进行生产——噪音太大。拒绝零沉默——宿醉——会打断用户。当专用 Silero 可用时，拒绝基于 Whisper 的 VAD（速度较慢、准确度较低）。

输入示例：“用于航空公司重新预订的呼叫中心 IVR。嘈杂的背景（机场）。英语 + 西班牙语。< 500 毫秒转弯检测。”

输出示例：
- VAD：Cobra（商业），具有抗噪音优势。如果成本过高，可以回退到 Silero。
- Parameters：阈值0.4（机场本底噪声较高）；最短语音 300 毫秒；静默宿醉 600 毫秒（用户经常在 IVR 期间暂停以读取航班号）；预卷 400 毫秒
- 语义转向：启用 LiveKit 转向检测器 - 句子中间常见停顿（“我需要更改我的航班......到明天”）。
- 同花技巧：在 Deepgram streaming 上启用。预期节省：400 毫秒 → 150 毫秒转弯延迟。
- 守卫：如果 Cobra/Deepgram 无法访问，则故障打开； audit log 用于调整的每个 VAD 触发事件。
