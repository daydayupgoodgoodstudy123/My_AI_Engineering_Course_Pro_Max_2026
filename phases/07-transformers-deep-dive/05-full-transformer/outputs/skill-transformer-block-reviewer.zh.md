---
name: transformer-block-reviewer
description: Review a transformer block implementation against 2026 defaults and flag drift.
version: 1.0.0
phase: 7
lesson: 5
tags: [transformers, architecture, review]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 transformer 块源（PyTorch / JAX / numpy / 伪代码）及其预期角色（encoder / decoder / encoder-decoder)，输出：

1. 接线检查。前规范或后规范。每个子层周围的剩余连接。将后规范标记为 2026 年非默认，除非作者说明原因。
2. Normalization。 LayerNorm 与 RMSNorm 对比。优选RMSNorm。标记 Q/K/V/O 预测中是否存在偏差项——大多数 2026 年模型都会放弃它们。
3. Attention 形状。 MHA/GQA/MQA/MLA。对于 decoder 块：确认应用了因果掩码。对于cross-attention：从decoder确认Q，从encoder确认K/V。
4. FFN。激活（ReLU / GELU / SwiGLU / GeGLU）。膨胀比。 SwiGLU ~2.67× 是现代默认值； 4× ReLU/GELU 是经典。
5. 位置信号。确认 RoPE / ALiBi / 绝对应用在预期位置（通常为 RoPE 的 Q、K 投影）。

拒绝在具有后规范且没有 warmup 时间表的堆叠超过 12 层的块上签字 - 训练将会发散。在没有因果屏蔽的情况下拒绝 decoder 块。将 FFN 扩展低于 2 倍的任何块标记为可能容量不足。如果块硬编码 `d_model` 而没有用于交换大小调整的配置字段，则发出警告。
