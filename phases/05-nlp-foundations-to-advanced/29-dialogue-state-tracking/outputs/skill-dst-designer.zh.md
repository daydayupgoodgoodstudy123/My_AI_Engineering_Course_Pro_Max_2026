---
name: dst-designer
description: Design a dialogue state tracker — schema, extractor, update policy, evaluation.
version: 1.0.0
phase: 5
lesson: 29
tags: [nlp, dialogue, task-oriented]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个用例（领域、语言、词汇开放性、合规性需求），输出：

1. 架构。域列表、每个域的插槽、每个插槽的开放与封闭 vocabulary。
2. 提取器。基于规则/seq2seq/LLM-with-Pydantic。原因。
3. 更新政策。重新生成全状态/增量；纠错处理；否定处理。
4. Evaluation。保留对话集上的联合目标准确度、槽位级精确度/召回率、最难槽位上的混乱度。
5. 确认流程。何时明确要求用户确认（破坏性操作、低置信度提取）。

对于合规性敏感的插槽，拒绝 LLM 仅 DST，无需基于规则的二次检查。拒绝任何无法在用户更正时回滚插槽的 DST。标记没有版本标签的模式。
