---
name: asr-picker
description: Pick ASR model, decoding strategy, chunking, and LM fusion for a given deployment target.
version: 1.0.0
phase: 6
lesson: 04
tags: [audio, asr, speech-recognition]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定部署目标（语言列表、域、延迟预算、硬件、离线/streaming、剪辑持续时间），输出：

1. 模型。 Whisper-large-v3-turbo / Parakeet-TDT / Canary-Flash / wav2vec 2.0 / Moonshine。一言以蔽之。
2. 解码。贪婪/波束宽度/temperature 回退/LM 融合 weight。原因与质量预算相关。
3. Chunking 和 VAD。块长度、步幅、是否使用 Silero-VAD 或 Whisper 自己的门。
4. 语言政策。强制语言与自动 LID；如何处理跨语言框架。
5. 评估计划。域测试集上的 WER、每个说话人的覆盖率、静音片段上的 hallucination 速率。

拒绝任何没有 VAD 选通的长格式 Whisper 部署（hallucination-在静音时容易出现）。拒绝报告没有文字 normalization 的 WER（下方，点状条）。标记任何没有 LM 的波束宽度 > 16；毛坯上的原始光束没有帮助。
