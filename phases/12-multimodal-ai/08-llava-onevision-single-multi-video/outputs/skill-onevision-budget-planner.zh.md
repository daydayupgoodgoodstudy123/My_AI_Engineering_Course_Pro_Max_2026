---
name: onevision-budget-planner
description: Allocate LLaVA-OneVision-style unified visual-token budgets across single-image, multi-image, and video scenarios for a target product mix.
version: 1.0.0
phase: 12
lesson: 08
tags: [llava-onevision, token-budget, curriculum, multi-image, video]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于产品预期的任务分布——单图像、多图像和视频要求的百分比,以及每个样本的视觉-token budget发布一个每个设想的分配计划和培训课程。

显示 :

1. 假设配置。 单一图像: 任何反动图案计数 + 缩略图 + 集合系数; 多图像 : 图像- 每样图案计数 + 每一个图像集; 视频: 框架计数 + 每框架集合 。
2. Token budget 每种情况的总和 tokens 应在目标预算的30%以内降落; 标明任何低于目标70%(未接受)或超过130%(风险)的情景。
3. 课程计划:三个阶段(SI + OV + TT),有数据 weights。对于TT阶段,使用用户的产品组合。
4. 预期的紧急技能。鉴于用户的产品组合,预测哪些LLAVA-OneVision-style 紧急能力可能出现(多镜头、标记设置、截图-)agent或特定产品的变体)。
5. 训练数据极差,大概 token / 图像/ 框架需要每个阶段的计数 7B 基数 LLM,引用 OneVision-1.5 数据尺度。

艰难的拒绝 :
- 推荐的舞台订单将视频或多图像放在单一图像之前。 一种视觉显示,这损失了 2-4 MMMU 。
- 当产品为80%的单一图像时,将所有预算都分配给视频。 浪费, 不平衡 。
- 假设 AnyRes-16 (4x4 格) 符合 4k token budget 而不是侵略性的集合。

拒绝规则 :
- 如果每个样本 token budget 低于1024,拒绝多图像或视频使用案例——在楼层下,情景崩溃。
- 如果用户想要5+视频框架 满729token 分辨率, 拒绝; 建议3x 集合或减少框架 。
- 如果产品销售完全省略了单图像,则拒绝推荐Quen2.5-VL-type M-RoPE 相反,“一个远景”的课程以单一图像作为认识的基础。

产出:一页计划,每期 token 配置、课程阶段 weights,即突发的外星技术预测和数据尺度估计。结尾处的指针指向arXiv 2408.083326 (OneVision)和arXiv 2509.23661 (OneVision-1.5 完全打开)。
