---
name: resolution-budget-planner
description: Pick between square-resize, AnyRes, M-RoPE, and NaFlex for a mixed-aspect-ratio VLM workload and emit a per-task token budget plan.
version: 1.0.0
phase: 12
lesson: 06
tags: [vlm, patch-n-pack, naflex, anyres, m-rope, token-budget]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于工作量,VLM将看到的图像描述(OCR文件、图表、UI截图、自然照片、视频框架)和每个请求的总数 token budget 每个图像类选一个分辨率战略,并产生可调制的配置。

显示 :

1. 每图像级策略。 对于每个申报的类别( OCR、 图表、 UI、 照片、 视频框架), 请选择 { quare- reference, AnyRes, M-RoPE引用任务分辨率的敏感性
2. Token budget 每个图像。 包含分钟_像素, 最大_像素( Qwen2.5- VL 样式) , 以及所选策略的预期序列长度。 如果任何单个图像超过40%, 则标出标记 LLM context.
3. 批量包装计划。如果请求被批次,请具体说明是否使用 `cu_seqlens` (斜面图),厚厚的块对角面遮罩,或未加划线的单图像 inference。请注意,当批量偏差大于2x时,可节省的瓦伦。
4. Encoder 建议:SigLIP 2 NaFlex, 用于混合工作量;Quen2.5-VL, 原为 agent UIS; CLIP-336 + 冻结的 AnyRes-encoder 部署; 生 ViT 仅用照片显示路径,为 224。
5. 故障模式警报器 Tokens- 选定配置的每图象;潜伏费用30吨/秒 prefill; 上下文填充百分比; 典型OCR基准的预期准确度 delta 相对于平方大小。

艰难的拒绝 :
- 建议对 OCR 或图表任务进行方形调整,而不引用用户将损失的基准数 。
- 提出一种能够产生更多成果的战略 tokens ưμ㼯A LLM 允许。 总是预算与声明相对 context window.
- 将“任何反光”视为普遍答案——其多倍式的瓷砖管理费可能超过 LLM 上下文,一个图像完成编码前。

拒绝规则 :
- 如果用户声明 token budget 低于256 tokens 每一个图像,拒绝任何其它的,除了只用照片的语义任务之外——没有多少集合在预算中回收了OCR的准确性。
- 如果用户想要密集的预测输出( 分解、 深度) ViT register tokens 在 encoder,在启用登记册的情况下,拒绝并指向 DINOv2 / SigLIP 2。
- 如果用户 LLM 工作量包括文件或截图、拒绝和建议更大的上下文或OCR-第一条管道。

产出:一页预算计划,每类战略表格,批量包装计划, encoder 尾端是相关的ARXiv文件,其中2307.06304份为NaViT,2502.14786份为SigLIP 2/NaFlex,2502.13923份为Quen2.5-VL。
