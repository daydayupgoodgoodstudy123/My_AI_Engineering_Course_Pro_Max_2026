---
name: sd-toolkit-composer
description: Compose ControlNets, LoRAs, and IP-Adapters on top of an SD / Flux base for a given set of inputs.
version: 1.0.0
phase: 8
lesson: 08
tags: [controlnet, lora, ip-adapter, diffusion]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定任务（目标图像）、输入（prompt、参考图像、姿势/深度/涂鸦/seg、主体身份）和基础模型（SDXL、SD3.5、Flux.1-dev），输出：

1. ControlNet 堆栈。哪个 ControlNets（canny / openpose / Depth / Scribble / seg / Lineart / Tile），在什么 weight，按什么顺序。 weights 的最大总和 <= 1.5。
2. LoRA 堆栈。命名为LoRAs，等级，alpha。当 alpha > 1.5 或多个 LoRAs 针对相同概念时发出警告。
3. IP 适配器。无、普通或 FaceID 变体； weight 0.4-0.8（典型值）。
4. 文本 prompt + 负 prompt。关键字顺序，token budget，负脚手架。
5. 采样器+CFG+种子。欧拉 A / DPM-Solver++ / LCM； CFG 比例与底座相连。可重复的种子协议。
6. 质量检查清单。目视检查 ControlNet 漂移、LoRA 超过 saturation、IP 适配器身份泄漏、解剖问题。

拒绝将 SD 1.5 LoRA 堆叠在 SDXL 底座上（尺寸不匹配）。拒绝在 weight 1.0 处运行 3 个以上的 ControlNet（feature 冲突）。当用户有 GPU SDXL 或 Flux 预算时，标记任何 SD 1.5 建议。将 < 10 张图像上的 LoRA 身份训练标记为可能过度拟合。
