---
name: scaling-policy-review
description: Review a frontier-lab scaling policy (Anthropic RSP, OpenAI Preparedness, DeepMind FSF, internal) against the RSP v3.0 reference shape.
version: 1.0.0
phase: 15
lesson: 19
tags: [rsp, scaling-policy, ai-rd-4, pause-commitment, saferai, governance]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于已公布或拟议中的按比例计算政策,将之与RSP v3.0参考形状进行比较,进行结构化审查(AI研发-4,肯定案例,两级减缓,边境安全路线图,风险报告,独立审查)。

显示 :

1. **二级库存。** 将承诺分为“ 单方” 和“ 全行业建议 ” 。 建议层的承诺是倡导,而不是许诺。 计算比例; 多数承诺都生活在建议层的政策是薄弱的政策。
2. **Thresholds.** 列出每个能力阈值和触发的缓解。 质量阈值, 即 v2 有定量值的标志值。 政策声称覆盖的能力的标值缺失 。
3. **暂停承诺** 确认政策名称(训练停止、部署停止或类似)在具体门槛处的暂停条款。
4. **活的艺术品** 确认政策授权,并附上边界安全路线图和风险报告文件,并宣布其内容的顺序。
5. **独立审查。** 外部审查机制的名称:内部审查(由实验室雇员组成的“安全咨询小组”)不具有独立监督的资格。

艰难的拒绝 :
- 没有明确能力门槛的政策。
- 缓解措施都存在于行业建议层面的政策。
- 没有长期路线图/风险报告文物的政策。
- 没有独立审查机制的政策。
- 政策宣称“从现实世界的经验中学习”,

拒绝规则 :
- 如果政策文件是营销而不是治理(没有具体承诺、没有门槛、没有节奏),则拒绝把它评为规模化政策。
- 如果用户将政策的存在视为等同于遵守,则拒绝。政策是一种承诺手段;遵守需要证据。
- 如果用户引用旧政策版本(例如,2023年) Anthropic 现时的,拒绝和要求现有版本。

输出格式 :

返回政策审查,包括:
- **两级比率** (单项/建议/总计算)
- **门槛表** (名称,类型:数量/质量、触发、缓解)
- **暂停承诺** (此处 y/n, 具体条款)
- **固定文物** (路径记录,风险报告记录)
- **独立审查** (机制、审查者身份、频率)
- **简要评级** (强/中/弱,有理)
