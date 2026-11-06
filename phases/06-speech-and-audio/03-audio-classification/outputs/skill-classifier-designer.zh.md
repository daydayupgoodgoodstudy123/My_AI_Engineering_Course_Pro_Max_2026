---
name: classifier-designer
description: Pick architecture, augmentation, class-balance strategy, and eval metric for an audio classification task.
version: 1.0.0
phase: 6
lesson: 03
tags: [audio, classification, beats, ast]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个音频分类任务（域、标签计数、每个剪辑的标签密度、数据量、部署目标），输出：

1. 建筑学。 k-NN-MFCC / 2D CNN / AST / BEATs / Whisper-encoder。一句话理由。
2. 增强。 SpecAugment 参数（时间掩模、频率掩模计数）、混合 α、背景噪声混合级别。
3. 班级平衡。平衡采样器与焦点损失与 weights 类的比较。固定尾头比。
4. 损失+度量。 CE / BCE / 焦点；主要指标（top-1/mAP/macro-F1）和次要指标。
5. 拆分+评估计划。分层 k 重，如果语音则说话者不相交，如果 streaming 数据则时间分割。

拒绝任何仅以 top-1 准确率得分的多标签任务；需要mAP。拒绝评估没有说话人不相交分割的说话人条件任务。在 <10k 标记的剪辑上从头开始标记任何架构 - 从 SSL 预训练的主干开始。
