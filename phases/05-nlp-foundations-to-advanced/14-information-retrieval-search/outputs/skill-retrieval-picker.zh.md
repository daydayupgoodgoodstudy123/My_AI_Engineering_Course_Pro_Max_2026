---
name: retrieval-picker
description: Pick a retrieval stack for a given corpus and query pattern.
version: 1.0.0
phase: 5
lesson: 14
tags: [nlp, retrieval, rag, search]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定要求（语料库大小、查询模式、延迟预算、质量标准、基础设施约束），输出：

1. 堆栈。仅 BM25、仅密集、混合（BM25 + 密集 + RRF）、混合 + 交叉 encoder 重新排序或三向（BM25 + 密集 + 学习稀疏）。
2. 密集encoder。命名具体型号（`all-MiniLM-L6-v2`、`bge-large-en-v1.5`、`e5-large-v2`、`paraphrase-multilingual-MiniLM-L12-v2`）。与语言、领域、上下文长度相匹配。
3. Reranker。如果使用的话，将交叉模型命名为encoder（`cross-encoder/ms-marco-MiniLM-L-6-v2`、`BAAI/bge-reranker-large`）。在 top-30 上标记 ~30-100ms 增加的延迟。
4. Evaluation计划。 Recall@10 是主要的检索指标。多答案的 MRR。首先是基线，然后根据它进行增量改进。

拒绝为具有命名实体、错误代码或产品 SKU 的语料库推荐仅密集，除非用户有证据密集句柄 exact matches。拒绝跳过高风险检索（法律、医学）的重新排名，其中最终的前 5 名决定用户的答案。
