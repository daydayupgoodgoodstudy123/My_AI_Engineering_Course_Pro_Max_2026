---
name: embedding-picker
description: Pick embedding model, dimension, and retrieval mode for a given corpus and deployment.
version: 1.0.0
phase: 5
lesson: 22
tags: [nlp, embeddings, retrieval]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定语料库（大小、语言、域、平均长度）、部署目标（云/边缘/本地）、延迟预算和存储预算，输出：

1. 模型。命名为 checkpoint 或 API。一句话理由。
2. 维度。完整/俄罗斯套娃截断/int8 量化。原因与存储预算有关。
3. 模式。密集/稀疏/多向量/混合。原因。
4. 如果 model card 需要，则查询前缀/模板。
5. Evaluation计划。与域相关的 MTEB 任务 + 使用 nDCG@10 进行保留域评估。

拒绝在没有域验证的情况下将 Matryoshka 截断为 <64 个暗点的建议。对于 10k 段以下的语料库，拒绝 ColBERTv2（开销不合理）。标记长文档语料库 (>8k tokens) 路由到具有 512-token 窗口的模型。
