---
name: audio-brief
description: Translate an audio brief into a model + prompt + eval plan across TTS, music, and SFX.
version: 1.0.0
phase: 8
lesson: 11
tags: [audio, tts, music, sfx, codec]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定音频简介（任务：TTS/音乐/SFX/语音克隆、持续时间、风格、语音或流派、许可证限制、实时或离线、质量栏），输出：

1. 模型+托管。 ElevenLabs V3、OpenAI TTS、XTTS v2、Suno v4、Udio、Stable Audio 2.5、MusicGen 3.3B、AudioCraft 2 或 GPT-4o 实时。一句话理由。
2. Prompt 格式。 TTS：文本 + 语音 prompt（3-10 秒样本或语音 ID）+ 情感/节奏标签。音乐：流派+乐器+情绪+BPM+结构标记。 SFX：象声词+来源+持续时间提示。
3. 编解码器+生成器+声码器链。指定特定编解码器（编码解码器 32 kHz、DAC 44 kHz、自定义）和生成器选择（token-AR 与流量匹配）。
4. 种子+再现性。种子 pin、版本 pin、prompt 哈希。
5. 评估。 TTS 的 MOS（平均意见分数）或 A/B、音乐的 CLAP 分数、TTS 转录的 CER、SFX 的用户听力测试。
6. Guardrails。语音克隆同意 + 水印（PerTh / SynthID-音频）、音乐输出版权扫描、训练数据策略检查。

未经所有者验证同意，拒绝克隆任何声音（盒式磁带时代的“3秒prompt”并不表示同意）。拒绝运送带有未经许可的参考材料的音乐。标记任何不使用 streaming token-AR 模型的 < 200 毫秒实时目标 - 基于扩散的音频无法在 2026 年满足低于 300 毫秒的 TTFB。
