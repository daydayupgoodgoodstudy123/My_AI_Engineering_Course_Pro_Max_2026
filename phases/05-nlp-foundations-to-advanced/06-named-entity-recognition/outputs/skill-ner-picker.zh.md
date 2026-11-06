---
name: ner-picker
description: Pick the right NER approach for a given extraction task.
version: 1.0.0
phase: 5
lesson: 06
tags: [nlp, ner, extraction]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定任务描述（领域、标签集、语言、延迟、数据量），输出：

1. 方法。基于规则+地名词典、CRF、BiLSTM-CRF 或 transformer 微调。
2. 起始模型。将其命名（spaCy 模型 ID，如 `en_core_web_sm` / `en_core_web_trf`，拥抱面部 checkpoint ID，如 `dslim/bert-base-NER`，或“自定义，从头开始训练”）。
3. 标签策略。基于 BIO、BILOU 或 span。用一句话来证明。
4. Evaluation。使用`seqeval`。始终报告实体级 F1，从不报告 token 级。

拒绝为 500 个以下标记示例推荐 fine-tuning 和 transformer，除非用户已经拥有预训练的领域模型（例如用于医疗的 BioBERT）。将嵌套实体标记为需要基于跨度或多遍模型。如果用户在使用开箱即用的 CoNLL-2003 标签时提到“生产规模”，则需要进行地名词典审核。
