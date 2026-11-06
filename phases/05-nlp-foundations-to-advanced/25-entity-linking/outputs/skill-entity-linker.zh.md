---
name: entity-linker
description: Design an entity linking pipeline — KB, candidate generator, disambiguator, evaluation.
version: 1.0.0
phase: 5
lesson: 25
tags: [nlp, entity-linking, knowledge-graph]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个用例（领域 KB、语言、容量、延迟预算），输出：

1. 知识库。维基数据/维基百科/自定义知识库。版本日期。刷新节奏。
2. 候选生成器。别名索引、embedding 或混合。目标提及回忆@K.
3. 消歧器。先验 + 上下文、基于 embedding、生成式或 LLM 提示。
4. 零策略。最高分、分类器或显式 NIL 候选者的阈值。
5. Evaluation。提及 30 时的召回率、top-1 准确率、保留集上的 NIL 检测 F1。

拒绝任何没有提及回忆基线的 EL 管道（如果不知道候选生成器出现了正确的实体，就无法评估消歧器）。使用 LLM 提示的 EL 拒绝任何管道，而不将输出限制为有效的 KB id。标记流行度偏见影响少数实体（例如名称冲突）而没有域 fine-tuning 的系统。
