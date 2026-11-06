---
name: bert-finetuner
description: Scope a BERT fine-tune for a new classification, extraction, or retrieval task.
version: 1.0.0
phase: 7
lesson: 6
tags: [bert, fine-tuning, nlp]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定下游任务（分类/NER/检索/重新排名/NLI）、标记数据大小和部署约束（延迟、设备），输出：

1. 骨干选择。模型名称（ModernBERT-base/large、DeBERTa-v3、multilingual-e5 等）以及一句话原因。对于需要 ≤8K 上下文的英语任务，首选 ModernBERT。
2. 头部规格分类：`[CLS]` → dropout → 线性（num_classes）。 NER：根据 token 线性 + CRF 可选。检索：平均池+对比损失。
3. 训练食谱。 Optimizer（AdamW，lr 2e-5 典型），warmup % (6–10%)，历元 (3–5)，batch size，fp16/bf16。
4. 评估计划。适合任务的指标（分类的准确性 + F1、NER 的实体级 F1、检索的 MRR/NDCG）。保留分割尺寸。
5. 失效模式检查。其中一个风险是：标签泄漏、类别不平衡、上下文截断、预训练和微调语料库之间的 tokenizer 不匹配。

拒绝在生成输出（文本生成）上微调 BERT — 建议仅使用 decoder。当少数类别低于 10% 时，拒绝发布未经类别分层评估的微调。将任何解冻整个骨干网的微调标记为可能过度拟合，标记示例数少于 1,000 个。
