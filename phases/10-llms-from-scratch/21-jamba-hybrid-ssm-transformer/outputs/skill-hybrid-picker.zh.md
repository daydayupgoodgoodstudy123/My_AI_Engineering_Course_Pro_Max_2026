---
name: hybrid-picker
description: Pick between pure Transformer, Jamba-style hybrid, and pure SSM for a given workload.
version: 1.0.0
phase: 10
lesson: 21
tags: [jamba, mamba, ssm, hybrid, long-context, memory-budget, architecture]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于工作量的规格(文字长度说明p50/p99、任务组合、记忆预算/ GPU,目标输送量,质量-Vs-速度优先级),在纯度 Transformer (+MoE +MLA),一种Jamba型混合型和纯Mamba型。

显示 :

1. 上下文长度桶:短(16k)、中(16k-64k)、长(64k-256k)或超长(256k+)。
2. 建筑建议。 选择纯 Transformer, 1: 7 混合, 1: 3 混合, 1: 15 混合, 或纯 Mamba。 使用上下文桶加上任务在文字回响中的要求来说明理由 。
3. 内存预算检查。 计算 KV cache + 目标上下文的 SSM 状态。 在计算后确认它符合目标加速器 weights 和激活内存(通常为10-20GB加起来) weights 和 KV cache).
4. 质量权衡披露。 记录所选择的垃圾等级的质量成本。 混合值低于1: 7, 以可测量的数量在内文本检索中降解; 纯 Mamba 在某些州级跟踪任务上失败 。
5. Inference 堆叠兼容性。 确认选中的架构得到目标堆叠的支持( NAME OF TRANSLATORS)vLLM特索瑞特, 特索瑞特... ...LLM, SGLang, llama混合体比纯度工具覆盖率要小 Transformers.

艰难的拒绝 :
- 16k. 建筑费没有正当理由。
- 纯粹的Mamba用于推理重度或多文档交叉引用任务。
- 子-1:15混合比率。在此之下,内含回想是不可靠的。
- 与指定加速器的内存计算预算不匹配的任何建议。

拒绝规则 :
- 如果工作量是短而长的,那么拒绝混合建议,并建议纯粹的 Transformer (如果可能的话,还有司法协助)——混合体具体地反映了长期的工作量。
- 如果加速器是消费者级(24GB或以下),则拒绝混合型模型,并建议采用蒸馏的小型混合型或量化纯度 Transformer.
- 如果工作量是耐潜伏的第1批,而模型是新的(没有现有的部署路径),则拒绝推荐一个有良好支持的纯度 Transformer 与 speculative decoding (第10阶段 - 15)作为较简单的路径。

产出:一页建议,列出背景桶、建筑选择、 KV cache (a) 在目标背景下,质量权衡披露,以及 inference 堆叠兼容性。 结尾为“ 什么样的监视器” 段落, 指定特定的长字符 evaluation (RULER, LongBench, 针头在哈伊斯塔克),这将确认前10公里生产请求中的建议。
