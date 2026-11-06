---
name: sequence-architecture-picker
description: Pick sequence architecture (RNN, transformer, SSM, hybrid) given length, throughput, and training budget.
version: 1.0.0
phase: 7
lesson: 1
tags: [transformers, architecture, rnn, ssm]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个序列问题（最大长度、批次形状、训练 tokens 预算、inference 延迟目标、设备类别），输出：

1. 主要架构。其中之一：transformer，状态空间模型（Mamba/RWKV），混合SSM+attention，RNN。一句话理由与主导约束相关。
2. 上下文长度策略。如transformer：全attention截止，滑动窗口大小，RoPE缩放因子。如果是SSM：扫描块大小。如RNN：隐藏宽度。
3. 训练 FLOP 配置文件。来自架构 + 上下文的每个 token 的近似 FLOPs；请注意规格是否符合计算预算。
4. Inference 内存配置文件。 KV cache 用于 transformers，SSM 的状态大小，每个 token 内存用于 RNNs。标记目标设备是否可以容纳单批 1。
5. 风险提示。已知此选择在规范范围内具有一种特定的故障模式（例如，在不带 Flash Attention 的 24GB GPU 上，64K 上下文中的 transformer OOM）。

在没有明确说明 gradient 流和并行度惩罚的情况下，拒绝推荐纯 RNN 用于高于 1B tokens 的任何训练运行。拒绝为 >64K 上下文推荐完整的 attention transformer，而不说明 `O(N^2)` 内存成本。如果没有指定的后备方案，拒绝推荐用于生产的全新架构（发布时间<12 个月前）。
