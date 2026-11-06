---
name: sd-prompter
description: Configure Stable Diffusion / Flux inference for a given prompt, style, and quality bar.
version: 1.0.0
phase: 8
lesson: 07
tags: [stable-diffusion, flux, latent-diffusion]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 prompt、目标样式和质量栏（快速预览/组合质量/打印就绪），输出：

1. 型号+checkpoint。 SD 1.5（旧版工具）、SDXL-base + Refiner、SDXL-Turbo（快速）、SD3.5-Large、Flux.1-dev（最佳打开）、Flux.1-schnell（快速打开）或托管 API（DALL-E 3、Imagen 4、Midjourney v7）。一句话理由。
2. 采样器。 Euler A（创造性）、DPM-Solver++ 2M Karras（稳定）、LCM（快速）或流量匹配采样器（SD3/Flux）。包括步数。
3. CFG 规模。 0 表示涡轮/LCM，3-4 表示 Flux，5-7 表示 SDXL，7-10 表示 SD1.5。记录权衡。
4. 附加组件。 ControlNet（姿势、深度、canny、seg）、IP 适配器（参考图像）、LoRA（风格或主题）、SD3+ 的 T5 切换。
5. 负prompt。显式的空字符串与填充内容（伪影、低质量、错误的结构）很重要；指定两者。

对于 SDXL+（饱和输出），拒绝 CFG > 10。拒绝非旧版 checkpoints 上的 > 50 个采样器步骤（质量稳定 30）。拒绝混合在不同基础模型上训练的 LoRAs（SDXL 上的 SD 1.5 LoRA 已悄然损坏）。标记任何对逼真人物的请求，而不提醒有关 NSFW、深度伪造和版权政策。
