---
name: qa-architect
description: Choose QA architecture, retrieval strategy, and evaluation plan.
version: 1.0.0
phase: 5
lesson: 13
tags: [nlp, qa, rag]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定要求（语料库大小、问题类型、事实性约束、延迟预算），输出：

1. 建筑学。提取式、带提取式阅读器的 RAG、带生成式阅读器的 RAG 或闭卷式 LLM。一句话理由。
2. 猎犬。无、BM25、密集（将 encoder 命名为 `all-MiniLM-L6-v2`）或混合。
3. 读者。 SQuAD 调整模型 (`deepset/roberta-base-squad2`)、LLM（按名称）或域微调 DistilBERT。
4. Evaluation。 EM + F1 用于提取基准；答案准确率+引用准确率+拒绝calibration进行生产。说出您正在测量的内容以及测量方法。

拒绝针对监管或合规性敏感问题的闭卷 LLM 答案。拒绝任何没有检索回忆基线的 QA 系统（在不知道检索器出现正确段落的情况下，您无法评估读者）。将需要多跳推理的问题标记为需要专门的多跳检索器，例如经过 HotpotQA 训练的系统。
