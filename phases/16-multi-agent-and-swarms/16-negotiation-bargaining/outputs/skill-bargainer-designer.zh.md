---
name: bargainer-designer
description: Design a negotiation protocol: which agent narrates, which component generates offers, how private scratchpads separate from public messages, what the round bound is, and how deal rate is monitored.
version: 1.0.0
phase: 16
lesson: 16
tags: [multi-agent, negotiation, bargaining, contract-net, OG-Narrator]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于谈判或任务市场(双方讨价还价、N方拍卖、合同-净额分配),设计协议。

显示 :

1. **Mechanism.** 双方交易,N-投标拍卖,合同-网络广播,或多党联盟。请指出游戏名称。
2. **提供发电机** 确定性(Zeuthen式特许权、Rubinstein平衡、简单线性时间表)或 LLM默认:除非要约必须是定性结构(建议、角色分配),否则必须确定。
3. **叙事层** 或 LLM 国家明确提出哪些建议。 LLM 而不是决定。
4. **私人与公共渠道。** 推理如何 traces ,“私人抓取”+“公共信息”作为两个字段。这是不可谈判的,每个ArXiv:2503.06416。
5. **圆形** 最多三到五轮,两党不限名额,不限名额,奖励合宪性,鼓励情绪上的提议。
6. **保留和BATNA纪律。** 双方必须知道他们的订位价格。 LLM 旁白者不能透露它。
7. **交易率监测。** 该议定书的基线交易率预期(从谈判基准中选择一个数字:27%至89%的范围取决于 LLM 回归警报阈值。
8. **Escalation.** 低于门槛的回合、ZOPA违规事件或对方违反规则走向调解人 agent 或人类。

艰难的拒绝 :

- 任何设计 LLM 计算数字报价而不进行确定性回溯。 arXiv: 2402.15813 显示此结果产生~ 27%的交易率 。
- 任何没有私人和公共频道的设计,对口会读你的推理
- 任何无约束弹壳的设计,保证符合要求的结果。
- 允许单 agent 持有买方和卖方双方的股份(角色谈判)。私人信息财产是机制;合并角色可以消除这种作用。

拒绝规则 :

- 如果任务没有数字回报(定性谈判、合同条款),则可能不适用OG-Narrator分解法。
- 如果用户无法执行单独的抓图( 单- )LLM明确标出泄漏风险,建议采用双调结构。
- 如果谈判与可能撒谎的一方是敌对的,建议调解人 agent 加上已登录的审计报价。

输出: 一页的简况。 从单句摘要开始 (“ 双方讨价还价 : Zeuthen 提供生成器 + ) LLM 旁白,5轮捆绑,分开的刮痕,交易速度警报低于85%。”然后上面的8节。结尾是一条样本信息:对应方所看到的和私人刮痕的特性。
