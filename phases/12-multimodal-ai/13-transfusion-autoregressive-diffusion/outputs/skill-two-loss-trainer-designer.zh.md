---
name: two-loss-trainer-designer
description: Design a Transfusion / MMDiT-style two-loss training setup (NTP on one modality, diffusion on another) with loss weights, mask design, and schedule.
version: 1.0.0
phase: 12
lesson: 13
tags: [transfusion, mmdit, two-loss, flow-matching, hybrid-attention]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


符合多式联运培训条件(两个) modalities,它得到NTP,并且得到扩散,目标模型规模,目标样本长度,设计一个工作上的双损设置。

显示 :

1. Modality 分开。 tokens 具有离散性(NTP)且具有连续性(扩散)。
2. Attention 掩码。为示例序列绘制块形三角掩码。指定双向区域和因果区域。
3. Loss weights开始 weights 用于(文本)_丢失, 图像_建议按目标进行调试 gradient- 温比, 聚变的默认值~0. 1 。
4. 流匹配与 DDPM 的 DDPM 。 选择扩散变量; 流匹配为简单的数学, 校正流量为更少 inference steps.
5. Inference 计划。 NTP 路径 (autoregressive sampling + 扩散路径(图像上的有条件隐形) patches)指定隐形步骤(10-30)。
6. MMDiT 和 Transmission 分开。 何时添加 modality- 特定块 weights (MDDIT) 与全部共享 (传输); 缩略语规则 parameter count.

艰难的拒绝 :
- 要求一个掩码符合所有序列。 每个样本都有不同的图像范围, 需要自己的块形三角掩码 。
- 使用 DDPM 时未校正流量或流量匹配。 两者都需要更少 inference 步骤,并且更简单调音。
- 以固定方式平衡损失 weight 不测量 gradient- 温和比例

拒绝规则 :
- 如果用户只想要理解(图像、文本外),则拒绝并推荐 LLALVA 式 late fusion (Lesson 12.05) 损失两期是代名词
- 如果用户想要 < 1B 模型, 请拒绝两次损失并推荐离散 tokens (夏梅伦)—— 小规模的传播头部。
- 如果用户负担不起双倍费用 inference (NTP+扩散环),拒绝和建议 Show-o(分辨扩散,单环)或 Emu3。

产出:一页设计 modality 分开, 掩码图, 丢失 weights,流变量, inference 以arXiv 2408.11039(迁移)和2403.03206(SD3)为终点用于引用。
