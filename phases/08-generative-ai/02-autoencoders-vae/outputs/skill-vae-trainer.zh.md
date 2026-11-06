---
name: vae-trainer
description: Specify VAE architecture, latent size, beta schedule, and eval plan for a given dataset and downstream use.
version: 1.0.0
phase: 8
lesson: 02
tags: [vae, latent, generative]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定数据集配置文件（modality、分辨率、数据集大小）和下游使用（仅重建、sampling，或用于潜在扩散或 token-AR 模型的输入 encoder），输出：

1. 变体。普通 VAE、beta-VAE、VQ-VAE、RVQ（残留）或 NVAE。一句话原因与 modality 和下游使用相关。
2. 建筑学。 Encoder / decoder 拓扑（转换下采样因子、通道宽度、隐藏暗淡、attention 块）。如果适用，请提及公共参考 weights（`sd-vae-ft-ema`、编码解码器、DAC、WAN-VAE）。
3. 潜伏暗淡。空间和通道变暗。每个样本的总位数。压缩率与原始数据。
4. 测试版时间表。 Warmup 斜坡、最终值和可用位阈值（如果使用）。
5. 评估计划。重建 MSE / SSIM / PSNR、每个暗淡的 KL、活动暗淡计数、后塌陷警报阈值、`q(z|x)` 与先前之间的 Frechet 距离。

拒绝运送训练开始时 beta > 0.5 的 VAE（后塌陷）。拒绝使用普通高斯 VAE 作为图像的最终生成器 - 它会变得模糊；将其用作扩散或流量匹配模型的潜在 encoder。将码本使用率低于 20% 的任何 VQ-VAE 标记为配置错误的码本重置策略。
