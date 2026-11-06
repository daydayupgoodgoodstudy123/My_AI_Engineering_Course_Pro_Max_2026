---
name: spec-decode-picker
description: Pick a speculative decoding strategy (vanilla / Medusa / EAGLE / lookahead) and tuning parameters for a new LLM inference workload.
version: 1.0.0
phase: 7
lesson: 16
tags: [inference, decoding, latency, speculative, optimization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="speculative-decoding-picker"></a>

# Speculative Decoding 拾取器

帮助工程师在普通推测式、Medusa、EAGLE 或前瞻解码之间进行选择，并针对特定工作负载调整 `N`（草稿长度）。

<a id="inputs-to-gather"></a>

## 要收集的输入

1. **验证器模型** — LLM 产生最终输出。大小很重要（草稿成本必须<验证者加速成本）。
2. **工作负载类型** — 代码、聊天、structured output、摘要。决定接受率。
3. **Sampling 策略** — 贪婪、低 T、高 T、光束。高 T sampling 会降低接受度。
4. **H硬件目标** — 内存预算决定是否可以安装单独的草稿模型。
5. **工程预算** — 美杜莎和EAGLE需要fine-tuning； vanilla 和lookahead 则不然。
6. **延迟目标** — 交互式聊天（<500ms TTFT，每个 token <50ms）与批量（吞吐量优先）。

<a id="decision-rules"></a>

## 决策规则

- **快速启动，无需培训**：具有同系列1B-3B模型的香草草案。 2× 典型值。
- **您可以使用验证者的隐藏状态微调**：EAGLE-2或EAGLE-3。 3–4× 典型值。
- **可以微调，但不能运行两个模型**：Medusa（验证器上有额外的头）。 2–3×。
- **没有训练预算，没有可用的草稿模型**：前瞻解码。 1.3–1.6×。
- **批量服务**：continuous batching更重要；随着批次的增加，投机收益会减少，因为验证者已经饱和。
- **高temperature或随机sampling**：接受度急剧下降。考虑降低 N (2–3) 或禁用。
- **Structured output（JSON，代码）**：接受度高。将 N 推至 7+ 以获得最大加速。

<a id="tuning"></a>

## 调音

- **N（拔模长度）**：从5开始。测量验收。如果 α > 0.9，则推至 7。如果 α < 0.6，则降至 3。
- **Draft temperature**：匹配验证者的temperature。不匹配的草稿 sampling 失去 α。
- **树深度（EAGLE-2 / Medusa）**：3–5 branches；较宽的树仅在 α > 0.8 时有帮助。
- **草图模型尺寸**：α > 0.7 的最小尺寸。 70B 验证者的 1B 草案是典型的；不要低于验证者的 tokenizer / embedding 兼容性。

<a id="always-flag"></a>

## 始终标记

- 检查草案和验证者是否共享tokenizer。不同的 BPE 分割打破了投机保证。
- Spec 解码与 vLLM 中的 continuous batching 交互：当批次已经饱和时，每个请求的加速会下降。
- EAGLE 的隐藏状态输入需要验证器内部结构；并不总是通过 HF APIs 暴露。首选 vLLM 或 SGLang 运行时。
- 美杜莎头需要对验证者自己的输出进行监督微调。数据收集步骤通常是主要成本。

<a id="output-format"></a>

## 输出格式

返回：

1. **Recommendation** — 一种策略名称和调整 parameters（例如“EAGLE-2，N=5，tree_深度=4”）。
2. **预期加速** — 具有明确的 α 假设。
3. **兼容性检查** — tokenizer 匹配、运行时支持、KV cache rollback 支持。
4. **后备计划** — 如果主要策略表现不佳，下一步要尝试什么。
5. **测量计划** — 如何验证代表性样本的接受率和加速。
