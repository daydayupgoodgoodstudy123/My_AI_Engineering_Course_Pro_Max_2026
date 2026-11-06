---
name: grammar-pipeline
description: Design a classical POS + dependency pipeline for a downstream NLP task.
version: 1.0.0
phase: 5
lesson: 07
tags: [nlp, pos, parsing]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定下游任务（信息提取、重写验证、查询分解、词形还原），您输出：

1. 标签集。 Penn Treebank 用于纯英语遗留管道，Universal Dependency 用于多语言或跨语言。
2. 图书馆。 spaCy 用于大多数生产 (`en_core_web_sm` / `_lg` / `_trf`)，用于学术级多语言的节，用于最高 UD 精度的 trankit。
3. 集成片段。调用库并消耗`.pos_`、`.dep_`、`.head`的3-5行。
4. 要测试的故障模式。名词-动词歧义（`saw`、`book`、`can`）和PP-附着歧义是典型的陷阱。样本 20 个输出和眼球。

拒绝推荐使用自己的解析器。从头开始构建解析器是一个研究项目，而不是一个应用程序任务。将任何使用 POS 标签而不处理小写/大写变体的管道标记为脆弱。
