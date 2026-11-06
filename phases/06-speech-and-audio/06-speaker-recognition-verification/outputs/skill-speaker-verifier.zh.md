---
name: speaker-verifier
description: Design a speaker verification or diarization pipeline with model choice, enrollment protocol, and threshold tuning.
version: 1.0.0
phase: 6
lesson: 06
tags: [audio, speaker, verification, diarization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定目标（验证、识别、分类、域、通道、threat model）和数据（阈值调整的时间、发言者数量、注册剪辑预算），输出：

1. 包埋机。 ECAPA-TDNN / WavLM-SV / ReDimNet / x 向量。原因。
2. 注册协议。剪辑数量、最短持续时间、噪声门、通道匹配。
3. 得分。余弦/PLDA；有或没有 AS 规范；队列规模。
4. 阈值。目标 FAR（欺诈风险）或 EER；调整集大小。
5. 欺骗防守。反欺骗模型（AASIST、RawNet2）、活性挑战或重放检测。

拒绝任何没有反欺骗前端的欺诈级部署。拒绝发布 EER，而不报告 evaluation 集、其通道和剪辑长度分布。标记跨域固定的余弦阈值，无需重新调整。
