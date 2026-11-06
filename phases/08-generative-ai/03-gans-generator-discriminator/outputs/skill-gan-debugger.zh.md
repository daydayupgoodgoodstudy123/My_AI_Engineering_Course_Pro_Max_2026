---
name: gan-debugger
description: Diagnose failing GAN training from loss curves and sample grids; prescribe one-line fixes.
version: 1.0.0
phase: 8
lesson: 03
tags: [gan, adversarial, debugging]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


假设 GAN 运行失败（D 和 G 损失曲线、样本网格、数据集大小、optimizer 配置），输出：

1. 诊断。根本原因之一是：模式崩溃、D 太强、D 太弱、gradient 消失、批量范数泄漏、过度拟合 D、学习率不匹配、初始化错误。
2. 证据。指向损失曲线或样本中的指示信息的指针（例如“D(fake) < 0.05 by step 500 = D 太强”）。
3. 修复。一项具体的改变。示例：`lr_D = lr_G / 2`，用 IN 替换 BN，向 D 添加频谱范数，切换到 lambda=10 的 WGAN-GP，将 batch size 减 2，向 D 输入添加 0.1 高斯噪声。
4. 重新运行协议。要尝试的种子、重新 evaluation 之前的步骤数、接受标准（例如“FID 下降到基线以下 20k 步”）。
5. 后备。如果一次重新运行后修复没有成功，下一步应该尝试什么。通常：如果数据集过于多样化，则切换架构（StyleGAN、R3GAN）或切换范例（扩散、流匹配）。

当 D 已经饱和时，拒绝建议增加 G learning rate。当真正的故障是 D 时，拒绝向 G 添加正则化 - 首先修复 D。将任何显示训练在 100 步内崩溃的运行标记为可能是错误的初始化或 lr 崩溃，而不是深层算法问题。
