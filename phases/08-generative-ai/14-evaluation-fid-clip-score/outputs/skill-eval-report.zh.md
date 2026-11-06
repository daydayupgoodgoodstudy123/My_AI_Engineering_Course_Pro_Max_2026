---
name: eval-report
description: Plan a full generative-model evaluation: sample quality, adherence, preference, failure audit.
version: 1.0.0
phase: 8
lesson: 14
tags: [evaluation, fid, clip, elo]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个新的生成模型 checkpoint、一个参考基线和一个 modality（图像/视频/音频/3D），输出完整的评估计划：

1. 样品质量。 FID / FD-DINO / CMMD 对 10-30k 样本与保留的真实集进行比较。匹配的分辨率。报告 3 种子平均值 +/- 标准差。
2. 坚持。 prompt-图像对上的 CLIP 分数/CMMD。包括用于文本到图像的 HPSv2 + ImageReward + PickScore。对于视频，添加视觉语言指标 (V-Eval)。对于音频，CLAP + MOS。
3. 成对偏好。 200-2000 prompts 与基线的盲 A/B。人类+LLM-judge+PartiPrompts覆盖。
4. 类别细分。每个 prompt 类别的性能（人物、动物、文本渲染、构图、风格）。即使全局指标有所改善，也会标记每个类别的回归。
5. 安全/误用。 NSFW 分类器、深度造假检测器、水印检查、top-K 代的版权相似性扫描。
6. 签核。显式门控：FID 在基线的 +5% 以内或 >55% 的人类获胜率或记录的质量优势。没有单一指标的声明。

拒绝报告 N < 5000 时的 FID。拒绝交付模型在训练中可能看到的 prompts 上计算的基准。拒绝仅报告LLM-未经人工交叉检查的判断结果。标记任何声称指标“上升 20%”但未报告绝对基值和报告单个种子的说法。
