---
name: re-designer
description: Design a relation extraction pipeline with provenance and canonicalization.
version: 1.0.0
phase: 5
lesson: 26
tags: [nlp, relation-extraction, knowledge-graph]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定语料库（领域、语言、数量）和下游使用（KG-RAG、分析、合规性），输出：

1. 提取器。基于模式/监督/LLM/AEVS 混合。原因与精确率与召回率目标相关。
2. 本体论。封闭属性列表（维基数据/域）或具有规范化通行证的开放 IE。
3. 出处。每个三元组都带有源字符跨度+文档ID。审核时不可协商。
4. 合并策略。规范实体 id + 关系 id + 时间限定符；重复数据删除策略。
5. Evaluation。 200 个手工标记的三元组的精确度/召回率 + LLM 提取样本的 hallucination 率。

拒绝任何未经跨度验证（源出处）的基于 LLM 的 RE 管道。拒绝开放 IE 输出流入未经规范化的生产图。对有时间限制的关系（雇主、配偶、职位）标记没有时间限定符的管道。
