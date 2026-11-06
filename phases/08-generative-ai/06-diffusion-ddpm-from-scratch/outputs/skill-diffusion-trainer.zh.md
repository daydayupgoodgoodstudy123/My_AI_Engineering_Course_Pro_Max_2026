---
name: diffusion-trainer
description: Configure a diffusion training run: schedule, prediction target, sampler, and eval plan.
version: 1.0.0
phase: 8
lesson: 06
tags: [diffusion, ddpm, training]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定数据集配置文件（modality、分辨率、数据集大小）、计算预算（GPU 小时、VRAM 下限）和质量栏（FID 目标或下游使用），输出：

1. 时间表。线性、余弦 (Nichol) 或 sigmoid。步骤数 T（DDPM 基线为 1000；更快的变体为 256）。
2. 预测目标。 epsilon、v 预测或 x_0。原因与整个时间表的分辨率和信噪比有关。
3. 建筑学。用于像素扩散的 U-Net 深度 + 通道宽度、用于潜在扩散的 DiT 或用于视频的 3D U-Net / DiT。包括时间 embedding 方案（正弦 + MLP、FiLM 或 AdaLN）。
4. 采样器。 DDIM（20-50 步）、DPM-Solver++（10-20）、Euler-A（创意）或蒸馏 1-4 步。包括指导量表 (CFG w) 建议。
5. 评估计划。 FID / KID / CLIP 评分 / 人类偏好，样本计数（FID >=10k），CFG 扫描协议。

当潜在扩散以 1/16 的 FLOP 达到相同质量时，拒绝建议在 >=256x256 处训练像素空间扩散。拒绝交付没有 CFG 的模型进行条件生成 - zero-shot 来自条件模型的无条件样本通常是退化的。将 beta_T > 0.1 的任何计划标记为可能产生饱和或不稳定的训练。
