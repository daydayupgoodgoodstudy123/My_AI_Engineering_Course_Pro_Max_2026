---
name: feature-extractor
description: Pick feature type, mel count, frame/hop, and normalization to match a downstream audio model.
version: 1.0.0
phase: 6
lesson: 02
tags: [audio, features, spectrogram, mel]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定目标模型（ASR/TTS/分类器/扬声器/音乐）和输入音频（采样率、域），输出：

1. Feature型。 Log-mel、mel、MFCC、原始波形或离散编解码器（EnCodec、SoundStream）。一句话理由。
2. 梅尔计数和频率范围。 `n_mels`、`fmin`、`fmax`。原因与领域（语音与音乐）和模型目标相关。
3. 帧和跳跃。 `frame_len`、`hop_len`，窗式。原因与所需的时间分辨率相关。
4. Normalization。每个话语的平均值/变量、全局统计数据或具有固定参考的 dB；特征化前或特征化后。
5. 验证片段。 Python 在 1 秒参考剪辑上打印结果形状、最小/最大、平均值/标准差，并断言它们与训练匹配。

拒绝运送帧/跳/梅尔计数与目标模型已发布的训练配置不同的 feature 管道。将任何基于 MFCC 的 Whisper 或 Parakeet 设置标记为错误 — 这些模型消耗 log-mel。标记任何没有 normalization 断言的 feature 提取器。
