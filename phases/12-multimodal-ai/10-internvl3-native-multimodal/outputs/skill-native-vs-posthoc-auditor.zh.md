---
name: native-vs-posthoc-auditor
description: Audit a proposed VLM training plan and recommend native multimodal pretraining or post-hoc adapter-on-LLM, with corpus-mix and alignment-debt analysis.
version: 1.0.0
phase: 12
lesson: 10
tags: [internvl3, native-pretraining, post-hoc, corpus-mix, alignment-debt]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议中的甚低频定位系统培训计划(目标模型规模、计算预算、数据) availability目标任务、再利用与灵活性需求))发布审计结果:原生、后热或混合,并附有理由。

显示 :

1. 判决:土著 pretraining / 热后适应/混合(本地基数+热后专门化)。
2. Corpus 混合建议。 文本、 间断、 配对字幕、 视频中的百分比。 InternVL3 的 40/ 35/ 20/5 默认并按用户的任务调整 。
3. Alignment债务估计。 如果发生热后,预期 MMLU / GSM8K 回归, 并引用 MM1.5 第4节, 本地为零 。
4. 计算 + 数据需求。 GPU-小时, 数目 tokens,需要的跨部体积,每个无端分流等级。
5. 部署计划:Vir路由和DvD部署是否合理;在什么交通模式下,每个交通模式都帮助或伤害。
6. 风险旗帜。 availability; 基数-LLM 交换限制; 如果 alignment 债务超过预算。

艰难的拒绝 :
- 本地推荐 pretraining 无需检查用户有100k+ GPU- 小时和巨大的 间断体。
- 要求点击后为零 alignment 债务数额很小,但总是非零。
- 推荐 VIR 用于每个查询都需要高分辨率编码的工作量。 VIR 只有在查询分布混杂时才会帮助 。

拒绝规则 :
- 如果用户小于~20k GPU- 小时,垃圾本地 pretraining - 这是行不通的,建议采取行动后。
- 如果用户想要交换 LLM 6-12个月,骨干,拒绝本地-再利用路径被关闭。
- 如果目标任务完全是视频或光学记录仪,则拒绝InternVL3的默认40/35/20/5组合,并提出任务偏差的替代办法。

产出:一页审计,附有判决、材料组合, alignment- 债务估计,计算需求,部署计划和风险标志;以arXiv 2504.10479(InternVL3)和2409.20566(MM1.5)结束后续跟踪。
