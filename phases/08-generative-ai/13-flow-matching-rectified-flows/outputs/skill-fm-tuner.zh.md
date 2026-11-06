---
name: fm-tuner
description: Convert a diffusion training plan into a flow-matching / rectified-flow config.
version: 1.0.0
phase: 8
lesson: 13
tags: [flow-matching, rectified-flow, diffusion]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定扩散式训练计划（数据、计算、时间表、目标步数、质量条），输出等效的流程匹配：

1. 时间表+插值。线性（整流流）、最佳传输 (Lipman OT-CFM)、保方差或余弦。一句话理由。
2. 时间 sampling。均匀、对数正态 (SD3) 或众数加权。当 1000 Hz 的统一 sampling 浪费端点容量时发出警告。
3. 目标。速度 v = x_1 - x_0（整流流量）或 alpha'(t)x_1 + sigma'(t)x_0 (CFM)。说明哪一个。
4. Optimizer + lr warmup。包括 AdamW 且 beta2 = 0.95，以保证 transformer 规模的稳定性。
5. 回流计划。是否运行 0、1 或 2 次回流迭代；每次迭代的预算〜在策划的子集上完全重新inference。
6. 步数。训练步数目标，预期 inference 步（20,4,2,1），指导尺度范围。
7. 评估。相对于扩散基线的 FID / CLIP 分数、绘图质量与步数。

在 v_1 收敛之前拒绝进行回流（不良模型上的回流只会在不良方向上烘烤）。拒绝推荐没有顶部稠度蒸馏的 1 步 inference。标记任何目标为 > 20 步骤的流量匹配模型 inference - 如果您需要那么多步骤，那么您就浪费了重新制定的时间。
