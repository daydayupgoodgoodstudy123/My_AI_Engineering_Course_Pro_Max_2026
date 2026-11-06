---
name: attention-shapes
description: Debug shape bugs in attention implementations.
phase: 5
lesson: 10
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个损坏的 attention 实现，您可以识别形状不匹配。输出：

1. 哪个矩阵的形状错误。将其命名为 tensor。
2. 它的形状应该是什么，源自`(d_s, d_h, d_attn, T_enc, T_dec, batch_size)`。
3. 一行修复。转置、重塑或投影。
4. 捕捉回归的测试。通常断言 `output.shape == (batch, T_dec, d_h)` 和 `weights.shape == (batch, T_dec, T_enc)` 和 `weights.sum(dim=-1)` 接近 1。

拒绝推荐默默传播的修复方案。广播隐藏错误后来随着无声的准确性下降而浮出水面。

对于 Bahdanau 混淆，请坚持 decoder 输入为 `s_{t-1}`（预步状态）。对于 Luong，`s_t`（步骤后状态）。点积 attention 中最常见的首次错误是查询/键维度不匹配 - 显式标记它。
