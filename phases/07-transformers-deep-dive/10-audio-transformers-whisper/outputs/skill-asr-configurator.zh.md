---
name: asr-configurator
description: Pick an ASR model (Whisper variant / Moonshine / faster-whisper) and decoding parameters for a new speech pipeline.
version: 1.0.0
phase: 7
lesson: 10
tags: [transformers, whisper, asr, speech]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定语音任务（转录/翻译/streaming/设备上）、语言、音频特征（噪音、口音、持续时间）和延迟/质量目标，输出：

1. 型号选择。其中之一：faster-whisperlarge-v3-turbo（默认生产）、whisperlarge-v3（最高质量、多语言）、whispermedium（中层）、Moonshinebase（边缘）、distil-whisper（英语速度快 2 倍）。一句话理由。
2. Quantization。 int8_float16（CPU 默认）、float16（GPU 默认）、fp32（研究）。标记 VRAM 影响。
3. 解码。波束宽度（典型值为 5，streaming 为 1）、temperature 回退时间表、对数概率阈值、无语音阈值、VAD 门控开/关。
4. Chunking。 30 s 固定窗口与 streaming 块（通常 10 s，2 s 重叠）+ 基于 VAD 的分割。记录合并后的重叠策略。
5. 后处理。时间戳alignment（WhisperX强制alignment），标点符号恢复，二值化（pyannote）。任务所需的标记。

拒绝推荐简单的 OpenAI Whisper（参考实现）用于生产 - `faster-whisper` 在相同的输出下速度提高了 4 倍。拒绝在没有 VAD 的情况下运送 streaming ASR，除非有书面理由。当输入可能是多扬声器时，标记任何单扬声器假设。
