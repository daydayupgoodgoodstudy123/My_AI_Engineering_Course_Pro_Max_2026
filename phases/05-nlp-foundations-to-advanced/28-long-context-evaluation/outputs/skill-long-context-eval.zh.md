---
name: long-context-eval
description: Design a long-context evaluation battery for a given model and use case.
version: 1.0.0
phase: 5
lesson: 28
tags: [nlp, long-context, evaluation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定目标模型、目标上下文长度和用例，输出：

1. 测试。 NIAH深度×网格长度； RULER 多跳；自定义域任务。
2. Sampling。每个长度的深度为 0、0.25、0.5、0.75、1.0。
3. 指标。检索通过率；推理通过率；首次时间-token；每次查询的成本。
4. 截止。有效检索长度（90%通过）和有效推理长度（70%通过）。两者都报告。
5. 回归。修复了 harness，在每次模型升级、表面增量时重新运行。

拒绝仅信任来自 model card 的 context window。对于任何多跳工作负载，拒绝仅使用 NIAH evaluation。拒绝供应商自我报告的长上下文分数作为独立证据。
