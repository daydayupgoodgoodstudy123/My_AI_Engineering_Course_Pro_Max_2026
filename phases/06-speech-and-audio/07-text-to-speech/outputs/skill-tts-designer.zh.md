---
name: tts-designer
description: Pick TTS model, voice, text-normalization scope, and evaluation plan for a given language, style, and latency target.
version: 1.0.0
phase: 6
lesson: 07
tags: [audio, tts, speech-synthesis]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定目标（语言、语音风格、延迟预算、CPU 与 GPU、许可证约束）和内容（域、OOV 密度、标点符号丰富度），输出：

1. 模型。 Kokoro / XTTS v2 / F5-TTS / VITS / StyleTTS 2 / 商业 API。一句话理由。
2. 文本前端。 Normalization 范围（数字、日期、URL）、phonemizer（espeak-ng 与 g2p-en）、OOV 后备。
3. 声音。预设名称或参考剪辑规格（秒数、本底噪声、重音匹配）。
4. 质量目标。克隆时通过 Whisper、SECS 瞄准 UTMOS、CER。
5. Evaluation计划。 20 个话语测试集，涵盖数字、同形异义词、专有名词、长句子。

拒绝任何没有文本规范化器的生产 TTS。拒绝未经用户同意的语音克隆和水印。标记任何要求使用英语以外语言的 Kokoro 部署。
