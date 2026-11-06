---
name: multilingual-picker
description: Pick source language, target model, and evaluation plan for a multilingual NLP task.
version: 1.0.0
phase: 5
lesson: 18
tags: [nlp, multilingual, cross-lingual]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定要求（目标语言、任务类型、每种语言可用的标记数据），输出：

1. fine-tuning 的源语言。默认英文；如果目标语言具有类型上接近的高资源语言，请检查 LANGRANK 或 qWALS。
2. 基础模型。 XLM-R（分类）、mT5（生成）、NLLB（翻译）、Aya-23（生成 LLM）。
3. Few-shot 预算。如果有的话，从 100-500 个目标语言示例开始。 Zero-shot 仅当标签不可行时。
4. Evaluation计划。每种语言的准确性（不是聚合）、跨语言一致性、非拉丁文字的实体级 F1。

拒绝交付没有每种语言 evaluation 的多语言模型 - 聚合指标隐藏了长尾故障。将 tokenization 覆盖率低的脚本（阿姆哈拉语、提格里尼亚语、许多非洲语言）标记为需要具有字节回退的模型（SentencePiece 与 byte_fallback=True，或字节级 tokenizer 类似GPT-2)。
