---
name: attention-variant-picker
description: Pick a full / sliding-window / sparse / differential attention topology for a new model given context length, retrieval demands, and compute profile.
version: 1.0.0
phase: 7
lesson: 15
tags: [attention, transformer, long-context, inference, memory]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="attention-variant-picker"></a>

# Attention 变体选择器

帮助开发人员为新的 transformer 或他们要扩展到更长上下文的现有拓扑选择并证明 attention 拓扑的合理性。

<a id="inputs-to-gather"></a>

## 要收集的输入

1. **训练时和inference的目标上下文长度**（通常不同——许多模型以16K训练并在inference扩展）。
2. ** 检索需求 ** 的 1-5 级：1 = 纯聊天，5 = 大海捞针 / RAG / 具有长存储库上下文的代码。
3. **Inference 内存预算** 每个请求 KV cache 容差（每层每 token 的字节数是正确的单位）。
4. **培训成本容忍度** — 从头开始培训SWA很便宜；将差分 attention 改造为预训练模型的成本很高。
5. **H硬件目标** — Hopper+具有完整的FlashAttention-3，Ada具有FA2，较旧的GPUs受掩模限制。

<a id="decision-rules"></a>

## 决策规则

- **Context ≤ 16K 且检索 ≤ 3**：完整的 attention 和 FlashAttention。不要过早优化。
- **Context 16–128K 和检索 ≤ 3**：混合 SWA + 全局，比例为 5:1，窗口 1024（Gemma 3 形状）。在折叠 KV 的同时保持检索的可行性。
- **Context > 128K**：完整的 SWA，每 4-6 层有一个全局层，加上位置插值/YaRN 缩放（第 04 课）。
- **检索= 5并且训练预算允许**：仅考虑前4层中的差分attention（KV加倍的一半，大部分接收器取消获胜）。
- **您正在运送公共 API**：更喜欢稳定的模式（完整、SWA、Gemma-3 混合）。除非您有内核工程师，否则请跳过本机稀疏/DIFF。
- **无法更改基础模型**：SWA可以通过屏蔽在inference处进行改装；微分和稀疏不能。

<a id="always-flag"></a>

## 始终标记

- 低于 7B 的 Pure-SWA 模型通常在推理基准测试中明显失败。建议反对。
- 窗口大小 < 512 几乎永远都不正确。变得更大或使用不同的拓扑。
- 论文中的差分 attention 报告是针对小型模型 (3-7B)。截至 2026 年初，扩大规模的证据还很薄弱。
- 每个变体都与 RoPE / YaRN 缩放交互（第 04 课）。明确说明职位方案。

<a id="output-format"></a>

## 输出格式

返回：

1. **Recommendation** — 单个命名拓扑（例如“Gemma-3 mix，W=1024，5:1 SWA:global”）。
2. **Justification** — 将每个输入映射到上面的决策规则。
3. **KV cache 估计** — 在目标上下文中，每层每 token 的字节数和批次 1 的 GB 数。
4. **迁移路径** — 如果基础模型已经训练好，如何改造。
5. **已知风险** — 哪些基准/工作负载可能会下降。
