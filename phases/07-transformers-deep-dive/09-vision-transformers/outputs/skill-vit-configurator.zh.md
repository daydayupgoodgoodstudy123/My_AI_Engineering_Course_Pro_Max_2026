---
name: vit-configurator
description: Pick a ViT variant, patch size, and pretraining source for a new vision task.
version: 1.0.0
phase: 7
lesson: 9
tags: [transformers, vit, vision]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定视觉任务（分类/分割/检测/检索）、图像分辨率、数据集大小（标记+未标记）和部署目标，输出：

1. 骨干。其中之一：DINOv2 ViT-L/14（默认用于检索/分类）、SAM 3 encoder（分割）、SigLIP（视觉语言）、ConvNeXt（延迟关键）。一句话理由。
2. Patch 尺寸。 16 用于 224 的标准分类，14 用于 DINOv2，8 用于高分辨率的密集预测。标志序列长度`(H/P)^2 + 1`和attention花费`O(N^2)`。
3. Pretraining 源码。 Checkpoint 名称。对于小型标记组 (<10k)：DINOv2 features 冷冻 + 线性探针。对于 >100k：微调最后的块。说出原因。
4. 训练食谱。 Optimizer (AdamW)、lr、增强（RandAug、MixUp、随机擦除）、标签平滑（典型值为 0.1）、EMA。
5. 风险提示。数据机制风险（数据太少，无法进行完全微调）、分辨率不匹配（预训练 224 → 部署 1024，无位置插值）、寄存器 token 缺失（可能会损害 DINOv2 features）。

拒绝建议在少于 100 万张图像上从头开始训练 ViT — CNN 基线将获胜。在没有明确讨论 Flash Attention + 分层变体 (Swin) 的情况下，拒绝推荐产生序列长度 > 4096 的 patch 大小。标记任何更改输入分辨率而不插值位置 embeddings 的部署。
