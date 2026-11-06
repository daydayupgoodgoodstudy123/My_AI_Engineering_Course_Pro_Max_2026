---
name: horizon-reality-check
description: Given a task you want to hand to an agent, decide whether the current frontier's horizon covers it with enough margin.
version: 1.0.0
phase: 15
lesson: 1
tags: [autonomous-agents, metr, time-horizon, reliability, deployment]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


考虑拟议的自主任务(什么是 agent 人类专家需要多长时间,失败的代价是什么,应该做一个现实检查,看目前的前沿模型的视野是否真的覆盖了它。

显示 :

1. **专家-时间估计数。** 询问用户专家完成时间的中位数, 以分钟或小时计。 如果无法估算, 请拒绝并引导他们先测量一个小样本 。
2. **教室比例。** 将所选模型的 50% METR 地平线除以专家时间估计。 标出任何低于 4x 的比例 — 成功概率为 50% , 您想要宽大幅度 。 在 2x 或以下的比值中, 除非 HITL 正在循环所有重大动作, 否则拒绝部署 。
3. **可靠性预算。** 估计轨道长度 tool calls,然后按每步可靠性计算端到端成功率 0.95, 0.99, 0.995。如果任务长度超过假设每步可靠率50%的成功阈值,则要求 checkpoints 或将任务分开。
4. **以 Eval-vs-deptement 调整。** 应用基准地平线与部署-通俗地平线之间的20-40%差。 Anthropic 2024 alignment- 假研究或2026年国际工业安全报告,向利益攸关方说明理由。
5. **需要的控件 。** 根据主机室,列出最低控制范围:预算上限、迭代上限、杀机开关、高光线 checkpoint 点, 金丝雀 tokens以及轨迹审计时间表。

艰难的拒绝 :
- 任何在地平线比低于2x时的部署,每次相应行动均不使用高射线。
- 任何关于模型“ 能做” 任务的说法, 仅以METR 地平线为基础。 地平线是物流曲线上的50%的标记; 尾部故障得到保证 。
- 把 METR 测得的任务时长视为能力下限，而不是上限。

拒绝规则 :
- 如果用户无法估计任务的专家时间, 请拒绝并先要求他们测量一个小样本。 其它的都是猜测。
- 如果拟议的任务费用超过用户按全额模式定价的最坏情况的预算,那么在进行之前,拒绝并建议从13学程中控制预算。
- 如果用户描述一项任务, 涉及不可逆转的行动( 金融交易、 生产数据库写作、 给客户的邮件) , 没有 HITL 层, 请拒绝 。 地平线参数无法明确不可逆的部署 。

输出格式 :

以下列方式返回一个简短的备忘录:
- **任务摘要** (一句话)
- **专家时间估计数** (单位)
- **教室比例** (有明确编号)
- **端对端可靠性估计** (按每步3个费率计算)
- **最低控制** (bulleted)
- **继续,坚持,坚持** (明确判决加一罪理由)
