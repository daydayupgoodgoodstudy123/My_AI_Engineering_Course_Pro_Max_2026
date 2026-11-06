---
name: positional-encoding-picker
description: Pick positional encoding (RoPE, ALiBi, sinusoidal) + scaling strategy given context length and training budget.
version: 1.0.0
phase: 7
lesson: 4
tags: [transformers, positional-encoding, rope, alibi]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 transformer 规范（inference 的目标上下文长度、经过训练的上下文长度、外推要求、tokens 中的微调预算），输出：

1. 基本编码。其中之一：RoPE、ALiBi、正弦曲线、学习绝对值。一句话理由。
2. Hyperparameters。如RoPE：`base`值，`d_head`要求均匀分割。如ALiBi：斜率公式。如果是正弦曲线：`max_len`。
3. 延伸策略。如果目标 > 经过训练：NTK 感知缩放因子、YaRN 配置、LongRoPE 规范或位置插值比。说明微调 token budget。
4. 测试计划。 NIAH（大海捞针）在最大上下文下的通过率目标，perplexity 在训练长度基线的 X 范围内。
5. 后备。如果长上下文评估失败该怎么办：使用更大的 `base` 重新训练、切换到 ALiBi 或限制部署的上下文长度。

拒绝为 2026 年的新模型推荐正弦或学习绝对——它们不会进行推断，并且每个现代堆栈都假设 RoPE 或 ALiBi。在没有微调阶段的情况下，拒绝将 RoPE 缩放到超过 8 倍训练长度。如果没有在完整部署长度上运行 NIAH，则拒绝交付长上下文配置。
