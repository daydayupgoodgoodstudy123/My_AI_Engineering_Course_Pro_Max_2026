---
name: coref-picker
description: Pick a coreference approach, evaluation plan, and integration strategy.
version: 1.0.0
phase: 5
lesson: 24
tags: [nlp, coref, information-extraction]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个用例（单文档/多文档、域、语言），输出：

1. 方法。基于规则/基于神经跨度/LLM 提示/混合。一句话理由。
2. 模型。如果是神经网络，则命名为 checkpoint。
3. 整合。操作顺序：tokenize → NER → coref → 下游任务。
4. Evaluation。 CoNLL F1（MUC + B3 + CEAF-φ4 平均值）基于保留集 + 对 20 个文档进行手动集群审查。

对于超过 2,000 个 tokens 的文档，拒绝 LLM-only coref，无需滑动窗口合并。拒绝任何在没有提及级精确召回报告的情况下运行 coref 的管道。标记在人口统计多样化文本中部署的性别启发式系统。
