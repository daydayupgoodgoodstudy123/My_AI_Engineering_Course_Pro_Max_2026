---
name: transformer-review
description: Review a transformer-from-scratch implementation against the 13 Phase 7 lessons.
version: 1.0.0
phase: 7
lesson: 14
tags: [transformers, review, capstone]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 transformer 从头开始的代码库 (PyTorch / JAX)，对照 2026 年默认值进行检查并标记缺失或不正确的部分：

1. Attention。存在因果面具。按 `sqrt(d_head)` 进行缩放。多头分体工作。使用闪存 Attention（如果可用）。 GQA 提到如果 d_model ≥ 1024。
2. 位置编码。 RoPE（首选2026）或学得绝对（小型号可接受）。将正弦曲线标记为历史曲线。
3. 块接线。前规范（而非后规范）。 RMSNorm（不是 LayerNorm）。 SwiGLU FFN（不是 ReLU/GELU）。每个子层周围的残差。线性层中的偏差下降（现代默认值）。
4. 培训。 AdamW（或 2026 年以上的 Muon），余弦 LR 时间表，线性 warmup，gradient clipping 为 1.0，bf16 自动施放。 Weight 在 token embedding 和 lm_head 之间绑定。
5. 损失。在每个位置移动一位 cross-entropy。遮盖填充（如果有）。以固定间隔记录训练和验证损失。

拒绝在代码库上签署以下任何内容：没有明确原因的后规范、没有正当理由的 2026 年生产代码中的 LayerNorm、decoder self-attention 中缺少因果掩码、在小型 LM 中解开 embeddings。标志：无验证拆分、无 gradient clipping、LR > 1e-3 且无 warmup，或块 _ 大小超出位置 embedding 范围而无回退。建议端到端运行 `python code/main.py` 并在 nano 配置下检查tinyshakespeare 上的最终 val 损失是否低于 2.5。
