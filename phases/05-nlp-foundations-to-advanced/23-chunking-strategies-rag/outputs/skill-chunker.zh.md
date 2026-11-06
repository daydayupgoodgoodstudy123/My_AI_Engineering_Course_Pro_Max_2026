---
name: chunker
description: Pick a chunking strategy, size, and overlap for a given corpus and query distribution.
version: 1.0.0
phase: 5
lesson: 23
tags: [nlp, rag, chunking]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定语料库（文档类型、平均长度、域）和查询分布（事实/分析/多跳），输出：

1. 策略。递归/句子/语义/父文档/后期/上下文。原因。
2. 块大小。 Token 计数。原因与查询类型相关。
3. 重叠。默认0；如果 >0 则证明合理。
4. 最小/最大执行。 `min_tokens`、`max_tokens` 守卫。
5. Evaluation计划。 Recall@5 上的 50 个查询分层 eval set（事实、分析、多跳）。

拒绝任何 chunking 策略，而不执行最小/最大块大小。拒绝超过 20% 的重叠，而没有消融表明有帮助。标记语义 chunking 建议，不带最小 token 下限。
