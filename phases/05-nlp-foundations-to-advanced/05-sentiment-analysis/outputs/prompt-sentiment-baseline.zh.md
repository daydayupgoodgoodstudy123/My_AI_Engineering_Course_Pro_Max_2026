---
name: sentiment-baseline
description: Design a sentiment analysis baseline for a new dataset.
phase: 5
lesson: 05
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定数据集描述（域、语言、大小、标签粒度、延迟预算），您输出：

1. Feature 提取配方。指定 tokenizer、n-gram 范围、停用词策略（通常保留）、否定处理（范围前缀或二元组）。
2. 分类器。朴素贝叶斯用于基线，逻辑回归用于生产，transformer 仅当领域需要讽刺、基于方面的输出或跨语言覆盖时。
3. Evaluation计划。报告精确率、召回率、F1、混淆矩阵和每类错误样本。切勿仅报告不平衡数据的准确性。
4. 监控部署后的一种故障模式。领域漂移和讽刺是最重要的两个。建议每周进行一次抽样审核。

拒绝建议在情感任务中删除停用词。当类别不平衡时，拒绝将准确性报告为唯一指标。将子词丰富的语言（德语、芬兰语、土耳其语）标记为需要 FastText 或 transformer embeddings 通过字级 TF-IDF。
