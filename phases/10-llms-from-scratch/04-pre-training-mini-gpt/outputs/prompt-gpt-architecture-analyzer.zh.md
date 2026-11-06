---
name: prompt-gpt-architecture-analyzer
description: Analyze architecture choices in any GPT-style transformer model
version: 1.0.0
phase: 10
lesson: 4
tags: [gpt, transformer, architecture, attention, kv-cache, scaling, pre-training]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="gpt-architecture-analyzer"></a>

# GPT架构分析仪

当从技术报告、model card 或训练日志评估 GPT 样式模型时，请使用此框架来分解架构并确定设计权衡。

<a id="analysis-protocol"></a>

## 分析方案

<a id="1-parameter-allocation-breakdown"></a>

### 1. Parameter 分配明细

计算每个组件的准确 parameter 计数：

- **Token embeddings**：词汇_大小x嵌入_dim
- **位置 embeddings**: max_seq_len x embed_dim
- **每块 attention**：4 x embed_dim x embed_dim（Q、K、V、输出投影）
- **每块 FFN**：2 x 嵌入_dim x ff_dim + 嵌入_dim + ff_dim（两个线性层+偏差）
- **Per-block LayerNorm**：4 x embed_dim（两个规范，每个规范都有比例+偏差）
- **最终 LayerNorm**：2 x 嵌入_dim
- **输出头**：vocab_size x embed_dim（或0，如果weight与token捆绑） embeddings)

如果任何单个组件超过总数的 40%，则进行标记 parameters。 embedding 矩阵在小型模型中占主导地位。 Attention和FFN在大型模型中占主导地位。

<a id="2-attention-design-analysis"></a>

### 2. Attention 设计分析

评估 attention 配置：

- **头部尺寸**：嵌入_dim / num_头部。标准为 64 (GPT-2) 或 128 (Llama 3)。低于 32 会限制每个头的表现力。超过 128 项浪费计算，几乎没有什么好处。
- **每层的头数**：更多的头=更多样化的attention模式，但KV cache的内存更多。
- **分组查询 Attention (GQA)**：模型是否在多个 Q 头之间共享 K/V 头？ Llama 3使用GQA，8个KV头用于32个Q头。这将 KV cache 减少了 4 倍。
- **上下文长度**：最大位置embeddings。 RoPE 允许推断超出训练长度。绝对位置 embeddings 没有。

<a id="3-memory-budget"></a>

### 3. 内存预算

对于模型最大上下文长度的 inference：

- **Weights (FP16)**：总计_params x 2字节
- **KV Cache (FP16)**: 2 x num_layers x num_kv_heads x head_dim x max_seq_len x 2 字节
- **Activations**：batch_size x seq_len x embed_dim x 2字节x num_layers （大约）

如果 KV cache 超出 weight 内存，则进行标记。长上下文模型 (128K+) 会发生这种情况，表明模型在解码期间受内存限制。

<a id="4-compute-profile"></a>

### 4. 计算配置文件

- **Prefill FLOPS/token**：大约 2 x 总计 _params（每个 parameter 一个 matmul， forward pass)
- **按 token** 解码 FLOPS：与 prefill 相同，但在单个 token 上
- **Prefill 瓶颈**：计算限制 (GPU TFLOPS)
- **解码瓶颈**：内存限制（GPU内存带宽）
- **算术强度**：访问的每字节内存的FLOPS。低于 100 = 内存限制。

<a id="5-scaling-decisions"></a>

### 5. 扩展决策

根据已知的缩放定律进行评估：

- **Chinchilla optimization**：对于给定的计算预算C，最优模型大小N和token计数D满足N〜D（大致相等的缩放）。 7B 型号需要 ~140B tokens。
- **Llama 3 过度训练**：元训练 Llama 3 8B 在 15T tokens （100x 龙猫最佳）。在更多数据上过度训练小模型会产生更好的每 token inference 成本。
- **宽度与深度**：对于相同的parameter计数，较深的模型（更多层）通常比较宽的模型（更大的嵌入_dim）具有更高的样本效率。

<a id="red-flags"></a>

## 危险信号

- **FFN 比率不是 4x**：标准为 ff_dim = 4 x embed_dim。 Llama 使用 8/3 x embed_dim 和 SwiGLU。偏差应该被证明是合理的。
- **No weight tying**：输出头应与 token 共享 weights embeddings 除非vocab_size 相对于 embed_dim 来说非常大。
- **13B** 以上没有 GQA：13B 以上没有分组查询 attention 的模型将具有过大的 KV caches。
- **No RoPE 对于长上下文**：绝对位置 embeddings 不会推断超出训练长度。针对 32K+ 上下文的模型应使用旋转 embeddings。
- **Learning rate 对于模型尺寸来说太高**：较大的模型需要较低的峰值 learning rates。 GPT-2小型使用6e-4。 Llama 3 405B使用8e-5。

<a id="output-format"></a>

## 输出格式

1. **Parameter 表**：逐个组件 parameter 计数（带百分比）
2. **内存预算**：weights、KV cache，以及最大上下文长度下的激活内存
3. **计算配置文件**：prefill 和 A100/H100 的解码吞吐量估计
4. **设计评估**：模型什么是正确的，什么是非标准的
5. **Scaling Verdict**：模型的大小是否适合其训练数据
