---
name: horizon-interpretation
description: Review a vendor's time-horizon claim and produce a gap analysis between benchmark claim and deployment reality.
version: 1.0.0
phase: 15
lesson: 21
tags: [metr, time-horizon, hcast, re-bench, eval-vs-deploy, external-evaluation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于供应商公布的时间光谱索赔(例如,“我们的模型以50%的可靠性完成14小时的任务”),因此产生了差距分析,对部署-现实三角洲进行了量化,并标出任何方法上的弱点。

显示 :

1. **方法审计。** 确定任务套件(HCAST、RE-Bench、SWAA或专有性),确认后勤是否合适(斜体、样本大小、置信间隔)。
2. **任务分布合适 。** 将销售商的基准任务分布映射到用户的生产任务分布上。 如果它们从物质上( 供应商衡量 SWE 任务, 生产就是客户支持流程) , 数字不会转移 。
3. **逆价差距** 应用基准地平线与部署现实之间的10-40%差距。 Anthropic 2024 alignment模拟研究和2026年国际AI安全报告关于电子电算游戏。 实际差距取决于电子电算协议;游戏比无结构任务高。
4. **工具缺口。** 基准工具是干净的,而且工具精良。 生产工具更混乱。 估计还有5-30%的可靠性折扣。
5. **Human-in-the-loop assumption.** 基准假设没有高链线。 agents 使用 HITL 运行的可靠性更高,但自主性较低。 相应调整地平线解释 。

艰难的拒绝 :
- 地平线索赔没有源法或样本规模。
- 声称基准地平线预测部署的可靠性。
- 供应商将2025年或更远的地平线数字列为当前数字(翻倍时间~7个月;2025年的数字在一年内是停滞的)。
- 将50%的地平线视为“大部分时间都会有效”——50%的可靠性是一个硬币翻转。

拒绝规则 :
- 如果供应商不披露方法,则拒绝并要求提供源纸或博客文章。
- 如果基准分布不与生产分布重叠,则拒绝并需要内部分配 evaluation.
- 如果供应商在未对其具体的电子交易管道进行博彩审计的情况下引用地平线,则拒绝将数字作为可靠性预测。

输出格式 :

返回一个地平线解释备忘录, 其内容为:
- **来源方法** (精密、合适方法、样本大小、CI)
- **分发重叠** (基准与生产;% 映射)
- **估计逆差** (低/高/高 理由)
- **工具缺口估计** (低/医疗/高)
- **HITL假设** (基准式自主与生产HITL)
- **部署调整后的地平线** (差数和工具折扣后方位数)
- **准备情况裁决** (生产/中转/仅研究)
