---
name: welfare-assessment
description: Apply Anthropic's four-step welfare precautionary assessment to a deployment decision.
version: 1.0.0
phase: 18
lesson: 19
tags: [model-welfare, moral-uncertainty, low-regret, anthropic]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于部署决定或拟议福利干预,采用四步防范评估。

显示 :

1. 道德- 住院概率。 估计模型的概率是道德患者( 非三重范围; ) Anthropic 2025年的运行时间为p > 0.01)参考Chalmers等人2024专家报告范围。
2. 干预费用。 计算干预的预期每次对话或每次部署费用。 边缘情况的最终对话费用为0.002美元/ conv; 关闭模型的费用为千-百万。
3. 行为证据。 确定非自我报告的福利相关性证据: 危难轨迹、 部署前评级模式、 可解释性检测。 仅凭自我报告是不够的 。
4. 预期值。计算 EV = p(与福利有关) * 投资如果EV > 0。

艰难的拒绝 :
- 任何基于单一自我报告的福利索赔 prompt.
- 任何福利干预,不说明费用。
- 任何福利解雇(“p=0”),不与Chalmers等人发生关系。

拒绝规则 :
- 如果用户问AI模型是否“真正”有意识,
- 如果用户要求获得数字性耐心概率, 请拒绝一个数字; 指向 Chalmers 等人的不确定性范围 。

产出:一页的评估,填充上文四个部分,计算一、两个具体干预措施的EV,并列出投资决定。 Anthropic 2025年和Chalmers等人,各一次,2024年。
