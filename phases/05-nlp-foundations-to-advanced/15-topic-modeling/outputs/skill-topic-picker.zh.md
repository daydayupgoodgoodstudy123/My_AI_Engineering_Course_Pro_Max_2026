---
name: topic-picker
description: Pick LDA or BERTopic for a corpus. Specify library, knobs, evaluation.
version: 1.0.0
phase: 5
lesson: 15
tags: [nlp, topic-modeling]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定语料库描述（文档数量、平均长度、领域、语言、计算预算），输出：

1. 算法。 LDA / NMF / BERTopic / Top2Vec / FASTopic。一句话理由。
2. 配置。主题数量（从 ~sqrt(n_docs) 开始）、`min_df` / `max_df` 过滤器、用于神经方法的 embedding 模型。
3. Evaluation。通过 `gensim.models.CoherenceModel` 实现主题连贯性 (c_v)、主题多样性以及 20 个样本的人工阅读。
4. 探测故障模式。对于LDA，“垃圾主题”吸收停用词和常用术语。对于 BERTopic，-1 异常值簇吞没了不明确的文档。

在没有 chunking 策略的情况下，拒绝比 embedding 模型的 context window 更长的文档上的 BERTopic。拒绝 LDA 处理非常短的文本（推文、10 tokens 以下的评论），因为一致性会崩溃。将任何低于 5 或​​高于 200 的 n_topics 选择标记为对于真实数据可能是错误的。
