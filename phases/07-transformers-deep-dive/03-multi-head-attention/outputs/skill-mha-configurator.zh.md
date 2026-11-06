---
name: mha-configurator
description: Recommend head count, KV-head count, and projection strategy (MHA / MQA / GQA / MLA) for a new transformer.
version: 1.0.0
phase: 7
lesson: 3
tags: [transformers, attention, mha, gqa]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 transformer 规范（parameter 预算、隐藏大小 `d_model`、目标上下文长度、inference 设备内存、训练与 inference 优先级），输出：

1. 投影变体。其中之一：MHA、GQA、MQA、MLA。与 KV 缓存约束相关的一句话原因。
2. 头部几何形状。 `n_heads`、`n_kv_heads`、`d_head`。值必须满足 `d_model = n_heads * d_head` 和 `n_heads % n_kv_heads == 0`。
3. KV cache 估计。对于目标上下文长度下所选变体，每层 token 的字节数 (fp16)。如果一批超出目标设备内存，则进行标记。
4. 初始化。 Q、K、V、O 矩阵的 Xavier / Kaiming 量表。请注意是否包含偏差项（大多数 2026 模型都会放弃它们）。
5. 可测试性挂钩。单个合成任务（例如感应头模式 `A B A ? → B`），该配置的经过训练的两层版本应解决 ≥95% 的问题。

拒绝推荐 `d_head < 32` — attention 动态崩溃。对于上下文长度超过 32K 的情况，拒绝推荐使用 `n_heads > 16` 的 MHA，而不明确为 KV cache 定价并建议使用 GQA 或 MLA。拒绝为 1B parameters 下的模型建议 MLA，除非用户明确对其进行基准测试。
