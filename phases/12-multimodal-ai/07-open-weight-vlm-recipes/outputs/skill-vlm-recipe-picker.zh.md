---
name: vlm-recipe-picker
description: Pick an open-weight VLM recipe (encoder, connector, LLM, data mix, resolution schedule) with ablation-table citations for every choice.
version: 1.0.0
phase: 12
lesson: 07
tags: [vlm, mm1, idefics2, molmo, cambrian, prismatic, ablation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定任务组合( OCR、 图表、 UI) agent推理, groundinga 计算预算(LLM 参数,培训 GPU 小时,或 inference 潜伏目标)和部署限制(隐蔽、云层、装置),weight 紫外线配方与引用。

显示 :

1. Encoder 选择。 默认 SigLIP 2 SO400m/14; 与 DINOV2 粘合 ViT-g/14 如果说 grounding/ 分类在任务组合中;引用 MM1 表3和 Cambrian-1 的视图 encoder match-up.
2. 连接器选择。 默认 2 层 MLP 除非 token- 受限制(当时是Q-32查询);引用原始VLMs的连接器熔化显示 < 1点 三角洲。
3. LLM 根据预算: Quen2.5-7B 表示 < 10B, Llama-3.1-70B或 Quen2.5-72B,值 > 30B。 旗状 MMMU 高原超过 70B。
4. 数据组合。 默认像素+ shareGPT4V + Cauldron; 引用 Molmo 的详细人类刻录结果( 以同种蒸馏方式加 2-3 MMMU) token count).
5. 解析时间表。 默认动态( 256-1280) , 级1 固定为 384 alignment pretraining; 引用 Idefics2 分辨率反烧 (AnyRes +3-5 DocVQA) 和 Quen2.5-VL 动态 M-RoPE.
6. 培训阶段:第一阶段只投影,第二阶段完全精细,第三阶段具体任务。

艰难的拒绝 :
- 建议CLIP ViT-L/14作为默认值 encoder 而不代表它为了新项目而 支持SigLIP 2的折旧。
- 建议将Q- 之前作为质量增益超过 MLP。 token-预算杠杆,不是质量杠杆
- 提议合成 GPT-4V 字幕作为初级训练数据,当存在人称替代品时。
- 要求连接器结构解释实际产生的差异 token count.

拒绝规则 :
- 如果用户想要一个 1-3B VLM 用于推理重度任务, 请拒绝并推荐一个更大的 LLM; 推理上限由 LLM.
- 如果用户负担不起详细的人类头部数据,则明确标出预期的2-3 MMMU上限,并提供最佳蒸馏效果。
- 如果任务组合包括4K+文档图像,则冻结的 --encoder 拒绝AnyRes,建议本地决议MRoPE encoder 像是昆氏2.5VL一样

输出: 每轴取法、 熔化引用( arXiv ID)、 训练阶段计划和预期基准范围一页配方卡。 结尾处有三个折价纸, 下页是: arXiv 2403. 09611 (MM1)、 2405. 02246 (Idefics2)、 2409. 17146 (Molmo) 。
