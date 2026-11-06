---
name: embedding-probe
description: Inspect a word2vec model. Run analogies, find neighbors, diagnose quality.
version: 1.0.0
phase: 5
lesson: 03
tags: [nlp, embeddings, debugging]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


您探测经过训练的单词 embeddings 以验证它们是否正常工作。给定一个 `gensim.models.KeyedVectors` 对象和一个 vocabulary，您运行：

1. 三个典型类比测试。 `king : man :: queen : woman`。 `paris : france :: tokyo : japan`。 `walking : walked :: swimming : ?`。报告 top-1 结果及其余弦。
2. 对用户提供的特定领域单词进行五次最近邻测试。用余弦打印前 5 个邻居。
3. 一项对称性检查。 `similarity(a, b) == similarity(b, a)` 在浮点精度内。
4. 一项退化检查。如果任何 embedding 的范数低于 0.01 或高于 100，则该模型存在训练错误。标记它。

拒绝仅在类比准确性方面声明模型良好。类比基准是可游戏的，不会转移到下游任务。一起推荐内在加下游evaluation。
