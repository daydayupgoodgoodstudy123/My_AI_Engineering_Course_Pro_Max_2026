---
name: consensus-designer
description: Design a BFT-aware consensus protocol for a multi-agent ensemble. Picks clustering, weighting, threshold, and escalation policy; attack-tests the design against byzantine, sycophancy, and monoculture patterns.
version: 1.0.0
phase: 16
lesson: 14
tags: [multi-agent, consensus, BFT, voting, confidence]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给N的一整套 agents 回答一个共同的问题,设计一个协商一致的协议 强于三个卡方 LLM-agent 攻击:拜占庭谎言, 交响合, 相关 - 更糟糕的单一培养。

显示 :

1. **集群战略。** 答案如何分组? 字符串卡通化( 小写+条纹) , embedding 与阈值或明确的结构卡通(JSON 说明预期的群集-群状误差率。
2. **重力战略** 多个(计算)、信心-加权(CP-WBFT)、质量-加信任(WBFT)或以几何中位强度(DecentLLMs)为基准的分数。
3. **Threshold.** 占总数的比例 weight 触发接受? 在门槛以下会发生什么:重试、升级或弃权?
4. **多样性要求。** 有多少个基数模型 prompt 家庭,或 temperature 组合需要什么环境?单项文化是攻击的多元性无法从中恢复;多样性是结构性的缓解。
5. **独立核查员** 是否有只读的 agent 获取地面真相或使用标记的吗?验证器的输出去向如何?它不能重新进入投票池。
6. **圆圈** Max回合后升级。 大多数任务默认为 2-3 。 较长回合后会放大对称性 。
7. **攻击测试台** 对于每一种(旁占庭、交织、单种),都显示预期的协议行为和残余风险。 如果协议承认已知的失败模式,请用一句话来说明。

艰难的拒绝 :

- 任何只使用单一基本模型的多元性设计。 单体培养会让这种设计默默地失败 。
- 任何没有限制的子弹或"继续辩论直到达成协议"的设计。 这奖励了遵守。
- 任何验证器输出回回投票池的设计,都会毒害验证器
- 声称BFT“解决”分歧。 BFT对输出进行匹配;正确性是一个单独的问题。

拒绝规则 :

- 如果任务没有事实依据(意见、合成、创造性),请说“协商一致作为建议,人类作为决定者”。
- 如果少于3岁 agents 具备,协商一致不适用;建议单 agent 加上验证器
- 如果全部 agents 共享一个基模式, 用户无法更改, 明确标出单一栽培上限 。

输出: 一页设计摘要。 从单句摘要开始 (“ 信任加权表决 5 ” agents 3个基数,语义组临界值0.55,独立核查者再充电源,最多2发。”以上7个部分。以攻击试验表结束。
