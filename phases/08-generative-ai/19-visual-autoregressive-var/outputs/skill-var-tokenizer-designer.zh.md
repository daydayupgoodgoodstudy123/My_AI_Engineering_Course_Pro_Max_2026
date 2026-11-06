---
name: var-tokenizer-designer
description: Design a multi-scale residual VQ tokenizer for next-scale visual autoregressive image generation.
version: 1.0.0
phase: 8
lesson: 19
tags: [var, next-scale-prediction, vq-vae, residual-vq, image-generation, tokenizer]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定图像目标（分辨率、通道、颜色与灰度、数据集大小、下游 LM 计算预算、目标 FID），输出：

1. 规模时间表。列出从 1x1 到 (H/p) x (W/p) 的 K 个分辨率级别。 256x256 默认为 10 个比例，512x512 默认为 14 个比例。根据 LM 的有效序列长度（尺度区域之和）和每遍并行尺度内预算来证明 K 的合理性。
2. 密码本。所有尺度的单一共享码本大小 V（典型 4096 / 8192 / 16384）。从数据集大小和 decoder 容量中选择 V。确认 calibration 批次或收缩 V 上的码本使用率保持在 50% 以上。
3. 剩余共享。确认尺度 1..K 通过求和上采样 embeddings（残余 VQ）一起重建潜在值。说明 patch 大小 p 和 VAE 主干（VQGAN 式鉴别器开/关，感知损失 weight）。
4. Decoder。 VAE decoder 映射将潜在值求和回像素。从 VQGAN decoder、VAR 纸 decoder 或较轻的 MAGVIT 风格 decoder 中进行选择。针对 FID 目标和 decoder VRAM 进行调整。
5. 位置 embedding。使用每个尺度的学习 embedding 和尺度内的 2D 正余弦来确认 (scale_index, row, col) 三元组。拒绝平坦的一维头寸； LM 需要刻度标签来应用正确的条件。

拒绝 VAR 的非残差多尺度 tokenizer。如果没有残差求和，下一个尺度的条件就会变得不明确，LM 优化的目标与论文证明的不同。拒绝单独的每尺度码本，除非将 V 校准到较小尺度的像素计数并且减轻码本崩溃。当 K x 平均尺度区域超过 LM 的最大序列长度减去文本调节的净空时，完全拒绝下一尺度预测。

输入示例：“ImageNet 类条件 256x256，数据集 1.2M，LM 预算 1.5B 参数，目标 FID 低于 5.0。”

输出示例：
- 比例表：K=10，尺寸 1、2、3、4、5、6、8、10、13、16。总计 tokens 671。
- 密码本：共享，V=4096。预计 ImageNet 在 256 上的使用率为 70-80%。
- 剩余分享：已确认； p=16，具有感知+对抗性损失的VQGAN主干，残差和重建f。
- Decoder：VQGAN decoder，4个上采样块，无需额外的精炼器。
- 位置 embedding：（尺度、行、列）三重、学习尺度 token + 尺度内的 2D 正余弦。
