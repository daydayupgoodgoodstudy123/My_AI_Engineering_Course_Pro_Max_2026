---
name: training-budget-estimator
description: Estimate (N, D, hours, GPU count) for a new transformer training run given compute budget and deployment constraints.
version: 1.0.0
phase: 7
lesson: 13
tags: [scaling-laws, training, chinchilla]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定训练目标（目标损失/目标 MMLU/目标下游指标）、计算预算（美元或 FLOP）、inference 数量（tokens/月）和约束（目标设备、内存、延迟），输出：

1. 计算制度。龙猫优化、过度训练（inference 优化）、训练不足（原型）。一句话原因与 inference 卷相关。
2. N 和 D。具体值。打印 `D/N` 比率。如果训练过度，请注意与龙猫最优相比的损失惩罚。
3. 训练挂钟。小时 × GPU-给定假设训练吞吐量的计数（对于密集，MFU ≈ 40%，对于 MoE 约为 30%）。预算精度（bf16 / fp8）和optimizer（AdamW / Muon）。
4. 数据来源。命名为语料库或综合预算。如果所需的 `D` 超过可用的高质量 tokens，则进行标记。
5. 风险提示。一种特定的故障模式：数据污染、optimizer 规模不稳定、上下文长度 tokenizer 不匹配、evaluation 套件 saturation。

如果它能提供高 inference 容量（inference 成本化合物），则拒绝在 Chinchilla 最优下训练 >8B 的密集模型。在未定义保留的 evaluation 套件的情况下，拒绝设置目标损失。标记任何在架构搜索而不是数据管理上花费超过预算 1% 的计划——众所周知，回报很小。在提交全部预算之前，需要大规模运行 1% 的预算来验证假设。
