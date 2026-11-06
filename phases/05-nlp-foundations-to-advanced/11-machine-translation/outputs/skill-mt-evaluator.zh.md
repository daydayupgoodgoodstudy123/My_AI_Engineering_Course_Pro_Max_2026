---
name: mt-evaluator
description: Evaluate a machine translation output for shipping.
version: 1.0.0
phase: 5
lesson: 11
tags: [nlp, translation, evaluation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定源文本和候选翻译，输出：

1. 自动分数估计。您所期望的 BLEU 和 chrF 范围。说明是否有参考资料。
2. 五点人工验证清单：内容保存（无 hallucinations）、正确的目标语言、语域/形式匹配、术语与术语表的一致性（如果提供）、无截断或长度爆炸。
3. 一个需要探讨的特定领域问题。法律：命名实体、法规引用。医学：药物名称、剂量。 UI：占位符变量，例如 `{name}`。
4. 信心旗帜。 “发货”/“发货并审核”/“不发货”。与发现问题的严重性相关。

如果不对输出进行语言 ID 检查，则拒绝发货。拒绝在没有参考的情况下进行评估，除非用户明确选择无参考评分（COMET-QE、BLEURT-QE）。将超过 1000 tokens 的任何内容标记为可能需要分块翻译。
