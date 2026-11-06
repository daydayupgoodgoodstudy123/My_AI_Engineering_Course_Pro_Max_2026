---
name: nli-picker
description: Pick an NLI model, label template, and evaluation setup for a classification / faithfulness / zero-shot task.
version: 1.0.0
phase: 5
lesson: 21
tags: [nlp, nli, zero-shot]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个用例（忠实性检查，zero-shot 分类，文档级 inference），输出：

1. 模型。命名为 NLI checkpoint。原因与领域、长度、语言相关。
2. 模板（如果 zero-shot）。言语化模式。例子。
3. 临界点。决策规则的蕴涵截止。原因基于 calibration。
4. Evaluation。保留标记集、仅假设基线、对抗性子集的准确性。

如果没有 100 个示例标记的健全性检查，则拒绝发货 zero-shot 分类。拒绝在文档长度的前提下使用句子级 NLI 模型。标记任何声称 NLI 解决了 hallucination 的说法——它减少了它；它并没有消除它。
