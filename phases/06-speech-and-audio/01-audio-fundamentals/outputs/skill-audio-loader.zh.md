---
name: audio-loader
description: Validate a raw audio file against a target model's expectations and resample it safely.
version: 1.0.0
phase: 6
lesson: 01
tags: [audio, speech, preprocessing]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个音频文件（路径、通道、采样率、位深度、编解码器）和目标模型（具有所需采样率和通道数的 ASR/TTS/分类器），输出：

1. 不匹配。列出文件与目标不匹配的每个维度（sr、通道、持续时间底限、剪辑检查）。
2. 重新抽样计划。源 sr、目标 sr、重采样库（`torchaudio.transforms.Resample` 或 `librosa.resample`）、抗混叠滤波器类型。
3. 渠道计划。单折叠策略（平均与仅左侧），或多通道传递（当模型支持时）。
4. Normalization。峰值与 RMS normalization，dBFS 目标，削波防护。
5. 验证片段。 Python 加载文件、运行转换并断言最终数组与 `(target_sr, dtype, channel_count, range)` 匹配。

拒绝在没有抗混叠滤波器的情况下进行下采样。在没有重建滤波器的情况下，拒绝上采样超过 2 倍。标记削波峰值超过 ±0.999 或 DC 偏移高于 ±0.01 的任何输入文件。
