---
name: img2img-chooser
description: Pick an image-to-image approach given paired vs unpaired data, domain specificity, and latency budget.
version: 1.0.0
phase: 8
lesson: 04
tags: [pix2pix, img2img, conditional]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定任务描述（源域、目标域、数据 availability - 配对/未配对/N 个样本、延迟预算、质量条），输出：

1. 方法。 Pix2Pix（配对，窄）、Pix2PixHD（配对、高分辨率）、CycleGAN（不配对）、SPADE（分段到图像）或 SD3 / Flux.1 上的 ControlNet 变体（通用、开放域）。
2. 训练数据规范最小对数、分辨率、增强、许可注意事项。
3. 建筑学。 G（U-Net 深度、通道宽度）、D（PatchGAN 感受野、谱范数）、损失 weights（adv、L1、VGG-感知）。
4. Inference 延迟。目标 ms/image 位于单个消费者 GPU（RTX 4090、M3 Max）上，分辨率权衡。
5. 评估。针对保留配对数据的 LPIPS、5k 样本的 FID、特定于任务的指标（seg 任务的 mIoU、超分辨率的 PSNR）、人类偏好。

当数据未配对时，拒绝推荐 Pix2Pix - 改为使用 CycleGAN 或 ControlNet。拒绝在没有增强的情况下训练少于 500 对的配对模型/pretraining 建议。标记任何显示“任意文本 prompt”的请求 - 这些请求需要扩散 + ControlNet，而不是配对的 GAN。
