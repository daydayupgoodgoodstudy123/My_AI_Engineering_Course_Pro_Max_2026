---
name: summary-picker
description: Pick extractive or abstractive, name the library, add a factuality check.
version: 1.0.0
phase: 5
lesson: 12
tags: [nlp, summarization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个任务（文档类型、合规性要求、长度、计算预算），输出：

1. 方法。提取的或抽象的。用一句话解释一下为什么。
2. 启动模型/库。命名它。 `sumy.TextRankSummarizer`、`facebook/bart-large-cnn`、`google/pegasus-pubmed` 或 LLM prompt。
3. Evaluation计划。 ROUGE-1、ROUGE-2、ROUGE-L（使用带词干处理的 `rouge-score`）。如果抽象的话还要进行事实检查。
4. 一种需要探测的故障模式。实体交换在抽象新闻摘要中最常见；标记源实体未出现在摘要中的样本。

拒绝对没有事实依据的医疗、法律、金融或监管内容进行抽象总结。将模型 context window 上的输入标记为需要分块映射减少汇总，而不仅仅是截断。
