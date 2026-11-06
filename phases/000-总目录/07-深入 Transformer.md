# Phase 07 深入 Transformer — Transformers Deep Dive

[返回总目录](README.md) · [前一章](06-语音与音频.md) · [后一章](08-生成式%20AI.md)

本章共 **16 节**。

**掌握目标**：能手算自注意力，解释位置编码、掩码、编码器解码器及推理效率。

**章节衔接**：从 Phase 05 的注意力和 Phase 03 的训练循环出发，连接语言模型、视觉、音频及多模态架构。

**为什么有用**：处于现代大模型主干架构层。注意力、位置、掩码和缓存共同决定模型如何访问序列信息，也连接语言、视觉、音频和高效推理。

**章节练习**：实现小型注意力和 Transformer block，检查维度、因果掩码与缓存前后输出的一致性。

小节中的“衔接”说明知识如何复用，不代表必须按编号完成所有分支；原课的具体前置要求见教材。建议练习可配合原课代码完成，CoderPad 的实际题目范围以各自 `PROMPT.md` 为准。

## 注意力与完整结构

### 07.01 [为什么需要 Transformer](../07-transformers-deep-dive/01-why-transformers/docs/en.md) — Why Transformers — The Problems with RNNs

- **掌握**：理解 RNN 的顺序计算、长依赖和压缩瓶颈。
- **衔接**：回顾序列模型的问题，明确自注意力要解决什么。
- **为什么有用**：位于序列架构的设计动机层。先理解顺序计算和长依赖瓶颈，才能判断注意力带来的改变，以及它仍需付出的计算成本。
- **建议练习**：比较 RNN 与注意力的数据依赖，指出可并行部分。

入口：[中文教材](../07-transformers-deep-dive/01-why-transformers/docs/zh.md) · [原课代码](../07-transformers-deep-dive/01-why-transformers/code/) · [CoderPad](../07-transformers-deep-dive/01-why-transformers/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/01-why-transformers/quiz/quiz.md)

### 07.02 [从零实现自注意力](../07-transformers-deep-dive/02-self-attention-from-scratch/docs/en.md) — Self-Attention from Scratch

- **掌握**：掌握 Q、K、V、缩放点积和掩码。
- **衔接**：是多头注意力及所有 Transformer 变体的核心。
- **为什么有用**：位于 Transformer 信息交互的核心层。每个位置通过内容选择其他位置的信息，是理解语言上下文和跨模态融合的共同操作。
- **建议练习**：手算小矩阵的权重，再核对代码与每行权重和。

入口：[中文教材](../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md) · [原课代码](../07-transformers-deep-dive/02-self-attention-from-scratch/code/) · [CoderPad](../07-transformers-deep-dive/02-self-attention-from-scratch/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/02-self-attention-from-scratch/quiz/quiz.md)

### 07.03 [多头注意力](../07-transformers-deep-dive/03-multi-head-attention/docs/en.md) — Multi-Head Attention

- **掌握**：理解分头、并行注意力和输出投影。
- **衔接**：在单头基础上增加多种关系表示。
- **为什么有用**：位于注意力表示容量的扩展层。多个头提供不同投影与关系视角，实际实现还需要正确处理维度、分头和合并。
- **建议练习**：跟踪 reshape 与 transpose，检查合并后维度。

入口：[中文教材](../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md) · [原课代码](../07-transformers-deep-dive/03-multi-head-attention/code/) · [CoderPad](../07-transformers-deep-dive/03-multi-head-attention/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/03-multi-head-attention/quiz/quiz.md)

### 07.04 [位置编码](../07-transformers-deep-dive/04-positional-encoding/docs/en.md) — Positional Encoding — Sinusoidal, RoPE, ALiBi

- **掌握**：区分正弦编码、RoPE、ALiBi 的位置处理方式。
- **衔接**：补足注意力本身缺少序列顺序信息的问题。
- **为什么有用**：位于序列顺序与相对位置的表达层。内容相同但顺序不同会改变含义，位置机制让注意力能够区分距离、方向和排列。
- **建议练习**：比较相同内容在不同位置的编码与注意力分数。

入口：[中文教材](../07-transformers-deep-dive/04-positional-encoding/docs/zh.md) · [原课代码](../07-transformers-deep-dive/04-positional-encoding/code/) · [CoderPad](../07-transformers-deep-dive/04-positional-encoding/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/04-positional-encoding/quiz/quiz.md)

### 07.05 [完整 Encoder 与 Decoder](../07-transformers-deep-dive/05-full-transformer/docs/en.md) — The Full Transformer — Encoder + Decoder

- **掌握**：理解残差、归一化、前馈层及交叉注意力。
- **衔接**：把前几节部件组装成完整序列到序列网络。
- **为什么有用**：位于可复用模型主干的组装层。残差、归一化和前馈网络与注意力共同构成完整 block，理解这些连接才能阅读实际模型。
- **建议练习**：画出一层数据流，区分 padding 与 causal mask。

入口：[中文教材](../07-transformers-deep-dive/05-full-transformer/docs/zh.md) · [原课代码](../07-transformers-deep-dive/05-full-transformer/code/) · [CoderPad](../07-transformers-deep-dive/05-full-transformer/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/05-full-transformer/quiz/quiz.md)

## 语言、视觉与音频分支

### 07.06 [BERT 与掩码语言建模](../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/en.md) — BERT — Masked Language Modeling

- **掌握**：理解双向编码、掩码预测和任务微调。
- **衔接**：从完整结构分出面向理解任务的 encoder 路线。
- **为什么有用**：位于面向理解的预训练表示层。双向上下文适合编码与分类任务，也帮助区分表征学习目标和逐步生成目标。
- **建议练习**：构造掩码训练样本，说明预测目标与可见上下文。

入口：[中文教材](../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/zh.md) · [原课代码](../07-transformers-deep-dive/06-bert-masked-language-modeling/code/) · [CoderPad](../07-transformers-deep-dive/06-bert-masked-language-modeling/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/06-bert-masked-language-modeling/quiz/quiz.md)

### 07.07 [GPT 与因果语言建模](../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/en.md) — GPT — Causal Language Modeling

- **掌握**：理解 next-token prediction 与自回归生成。
- **衔接**：与 BERT 对照，为 Phase 10 的 Mini GPT 铺路。
- **为什么有用**：位于自回归语言建模的核心架构层。因果掩码和下一个 token 目标连接预训练与生成，是理解 GPT 类模型的基本路径。
- **建议练习**：构造移位标签，验证模型不能看到未来 token。

入口：[中文教材](../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md) · [原课代码](../07-transformers-deep-dive/07-gpt-causal-language-modeling/code/) · [CoderPad](../07-transformers-deep-dive/07-gpt-causal-language-modeling/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/07-gpt-causal-language-modeling/quiz/quiz.md)

### 07.08 [T5 与 BART](../07-transformers-deep-dive/08-t5-bart-encoder-decoder/docs/en.md) — T5, BART — Encoder-Decoder Models

- **掌握**：理解 encoder-decoder 的文本转换与去噪目标。
- **衔接**：连接原始 Transformer、翻译和摘要任务。
- **为什么有用**：位于条件文本生成的架构分支。编码器读取输入、解码器产生目标序列，为翻译、摘要和去噪任务提供清楚的职责划分。
- **建议练习**：把同一文本转换成两种预训练输入与目标。

入口：[中文教材](../07-transformers-deep-dive/08-t5-bart-encoder-decoder/docs/zh.md) · [原课代码](../07-transformers-deep-dive/08-t5-bart-encoder-decoder/code/) · [CoderPad](../07-transformers-deep-dive/08-t5-bart-encoder-decoder/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/08-t5-bart-encoder-decoder/quiz/quiz.md)

### 07.09 [视觉 Transformer](../07-transformers-deep-dive/09-vision-transformers/docs/en.md) — Vision Transformers (ViT)

- **掌握**：理解图像 patch、位置与分类表示。
- **衔接**：将 Transformer 序列接口复用到 Phase 04 图像。
- **为什么有用**：位于图像表示与通用序列主干的连接处。把图像变成 patch 序列后可复用注意力，也为 VLM 的视觉编码器提供结构基础。
- **建议练习**：计算不同 patch 大小对应的 token 数与注意力开销。

入口：[中文教材](../07-transformers-deep-dive/09-vision-transformers/docs/zh.md) · [原课代码](../07-transformers-deep-dive/09-vision-transformers/code/) · [CoderPad](../07-transformers-deep-dive/09-vision-transformers/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/09-vision-transformers/quiz/quiz.md)

### 07.10 [音频 Transformer](../07-transformers-deep-dive/10-audio-transformers-whisper/docs/en.md) — Audio Transformers — Whisper Architecture

- **掌握**：理解音频特征编码与文本解码的组合。
- **衔接**：连接 Phase 06 的 Whisper 和序列对齐问题。
- **为什么有用**：位于声音特征到文本生成的模型层。音频编码和语言解码共享 Transformer 思路，但输入长度、时间尺度和对齐需求不同。
- **建议练习**：标注 Mel 特征到文本输出之间的形状与掩码。

入口：[中文教材](../07-transformers-deep-dive/10-audio-transformers-whisper/docs/zh.md) · [原课代码](../07-transformers-deep-dive/10-audio-transformers-whisper/code/) · [CoderPad](../07-transformers-deep-dive/10-audio-transformers-whisper/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/10-audio-transformers-whisper/quiz/quiz.md)

## 容量、效率与综合实现

### 07.11 [混合专家 MoE](../07-transformers-deep-dive/11-mixture-of-experts/docs/en.md) — Mixture of Experts (MoE)

- **掌握**：掌握 router、top-k 专家、负载均衡与稀疏激活。
- **衔接**：在 Transformer 前馈层上扩展容量与计算分配。
- **为什么有用**：位于模型容量与每次计算量的分配层。稀疏激活可以让部分参数按需工作，但同时引入路由、负载和通信问题。
- **建议练习**：模拟路由分配，区分总参数和每 token 激活参数。

入口：[中文教材](../07-transformers-deep-dive/11-mixture-of-experts/docs/zh.md) · [原课代码](../07-transformers-deep-dive/11-mixture-of-experts/code/) · [CoderPad](../07-transformers-deep-dive/11-mixture-of-experts/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/11-mixture-of-experts/quiz/quiz.md)

### 07.12 [KV Cache 与注意力优化](../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/en.md) — KV Cache, Flash Attention & Inference Optimization

- **掌握**：理解重复计算、prefill、decode 和内存访问。
- **衔接**：将模型结构连接到实际推理性能。
- **为什么有用**：位于模型结构到推理性能的连接层。缓存减少重复计算，注意力实现优化内存访问，帮助解释速度与上下文长度的关系。
- **建议练习**：比较有无 KV cache 的计算次数和缓存尺寸。

入口：[中文教材](../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md) · [原课代码](../07-transformers-deep-dive/12-kv-cache-flash-attention/code/) · [CoderPad](../07-transformers-deep-dive/12-kv-cache-flash-attention/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/12-kv-cache-flash-attention/quiz/quiz.md)

### 07.13 [Scaling Laws](../07-transformers-deep-dive/13-scaling-laws/docs/en.md) — Scaling Laws

- **掌握**：理解参数、数据、计算预算与拟合关系。
- **衔接**：从单模型实现推进到训练规模和资源分配。
- **为什么有用**：位于训练资源规划与经验预测层。规模关系提供预算分配的分析框架，但需要明确拟合数据和适用范围，不能把趋势当保证。
- **建议练习**：固定计算预算，比较增加参数或数据的两种方案。

入口：[中文教材](../07-transformers-deep-dive/13-scaling-laws/docs/zh.md) · [原课代码](../07-transformers-deep-dive/13-scaling-laws/code/) · [CoderPad](../07-transformers-deep-dive/13-scaling-laws/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/13-scaling-laws/quiz/quiz.md)

### 07.14 [从零构建 Transformer](../07-transformers-deep-dive/14-build-a-transformer-capstone/docs/en.md) — Build a Transformer from Scratch — The Capstone

- **掌握**：整合 embedding、注意力、前馈层与训练循环。
- **衔接**：检验前面结构知识，再进入变体与加速专题。
- **为什么有用**：位于架构知识的端到端验证层。亲自组装和训练，能检查掩码、标签与梯度是否协同正确，让结构理解落到运行行为。
- **建议练习**：让小模型拟合简单序列任务，并检查掩码与损失。

入口：[中文教材](../07-transformers-deep-dive/14-build-a-transformer-capstone/docs/zh.md) · [原课代码](../07-transformers-deep-dive/14-build-a-transformer-capstone/code/) · [CoderPad](../07-transformers-deep-dive/14-build-a-transformer-capstone/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/14-build-a-transformer-capstone/quiz/quiz.md)

### 07.15 [注意力变体](../07-transformers-deep-dive/15-attention-variants/docs/en.md) — Attention Variants — Sliding Window, Sparse, Differential

- **掌握**：区分滑动窗口、稀疏与差分注意力的目标。
- **衔接**：针对标准全注意力的成本或噪声问题做改造。
- **为什么有用**：位于注意力的效率与表达改进层。不同变体限制或重组信息访问，适合分析计算节省会影响哪些依赖与上下文能力。
- **建议练习**：画出可访问位置，比较长距离依赖是否仍可传递。

入口：[中文教材](../07-transformers-deep-dive/15-attention-variants/docs/zh.md) · [原课代码](../07-transformers-deep-dive/15-attention-variants/code/) · [CoderPad](../07-transformers-deep-dive/15-attention-variants/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/15-attention-variants/quiz/quiz.md)

### 07.16 [投机解码](../07-transformers-deep-dive/16-speculative-decoding/docs/en.md) — Speculative Decoding — Draft, Verify, Repeat

- **掌握**：理解小模型起草、大模型验证及接受修正。
- **衔接**：承接自回归和缓存，连接 Phase 10 推理优化。
- **为什么有用**：位于自回归生成的加速层。起草与验证利用模型间能力差异减少串行等待，同时需要保证接受和修正过程符合目标采样。
- **建议练习**：在小概率分布上检查接受率、修正和采样一致性。

入口：[中文教材](../07-transformers-deep-dive/16-speculative-decoding/docs/zh.md) · [原课代码](../07-transformers-deep-dive/16-speculative-decoding/code/) · [CoderPad](../07-transformers-deep-dive/16-speculative-decoding/coderpad/README.md) · [课后测验](../07-transformers-deep-dive/16-speculative-decoding/quiz/quiz.md)
