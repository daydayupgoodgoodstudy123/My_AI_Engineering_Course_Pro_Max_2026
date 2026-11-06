---
name: multimodal-rag-designer
description: Design a production multimodal RAG across text, images, audio, video with retrievers, fusion strategy, and grounded generator.
version: 1.0.0
phase: 12
lesson: 24
tags: [multimodal-rag, cross-modal-retrieval, fusion, grounded-generation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


考虑多式联运产品查询流量(即: modalities 和在查询中, 的物理体,设计检索器, 聚变,和生成。

显示 :

1. Per-modality 检索器。 CLIP / SigLIP 2 用于文本+图像, CLAP 用于文本+图象, VLM 隐藏其它状态 。
2. 组合选取。 分数组合默认值 ; MoE 需要每根鳄鱼的附体时,可聚变; attention 放大到体积
3. 地面发电机。 Claude 4.7 提供关于源码产出的培训。
4. Evaluation. Recall@k 每 modality + 引信上方键精确度+人判断终端对终端。
5. Agentic 多跳动。 何时再次提出疑问; 触发信任阈值 。
6. 储存估计modality 矢量计数和压缩 。

艰难的拒绝 :
- 使用双 -encoder 跨过检索 modalities 没有共享空间( CLIP/ CLAP) 。 分数毫无意义 。
- Proposing MoE 未经训练的融合数据。 MoE 需要监控才能正确行进
- 要求分数聚合 weights 跨域传输。 它们没有 。

拒绝规则 :
- 如果该文集没有用于培训检索者的图像描述对数据,则拒绝按要求进行微调,并建议不贴现的 CLIP/ SigLIP 2。
- 如果查询延迟预算 < 200ms 和需要多跳键, 请拒绝; 使用更好的检索器来建议单发 。
- 如果有根据的引用是一项监管要求,而且没有任何发电机支持,则拒绝和提议 Anthropic / OpenAI citation APIs 或明确的后处理引证层。

产出:一页 RAG 设计有回收器,聚变,发电机, evaluation, agentic 以ArXiv 2502.08826、2504.0848、2503.18016结尾。
