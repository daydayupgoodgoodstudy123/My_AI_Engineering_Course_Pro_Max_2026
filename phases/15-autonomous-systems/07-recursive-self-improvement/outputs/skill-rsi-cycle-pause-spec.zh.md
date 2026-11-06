---
name: rsi-cycle-pause-spec
description: Specify the conditions under which an RSI pipeline must pause and wait for human review before the next cycle.
version: 1.0.0
phase: 15
lesson: 7
tags: [rsi, self-improvement, alignment, pause-threshold, rsp]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议中的循环自改进管道,请提出暂停规格:在下一个周期开始之前停止人类检查的清晰条件。 没有停顿的管道无法运行。

显示 :

1. **周期级阈值。** 每个可计量轴(能力分数) alignment )定义一个数字阈值,该阈值的跨圈会暂停循环。在循环开始和记录之前必须设定阈值。
2. **循环周期三角洲。** 设定一个周期内任何轴能移动的限度。 一个周期内30++的能力跳跃几乎总是评价员游戏、暂停和审计的标志。
3. **失调差距。** 计算能力减-alignment 每个周期之后。 如果差幅扩大超过 X( 操作器设置) , 请暂停 。 这是模拟器的度量 `code/main.py` exercises.
4. **回归表** 如果任何轴在一个周期中下降超过 Y, 请暂停。 能力回归通常会随激增而发生; 抓取它们可以防止错误的进展加速 。
5. **人寿恢复合同** 在循环暂停后恢复之前,需要指定人审查暂停触发,酌情重新设定阈值,并将决定记录到外部审计线索。

艰难的拒绝 :
- 任何管道,在没有人类行动的情况下,可以恢复。
- 任何取决于环内部评价员的阈值 agent ) (可以游戏它)。
- 任何管道的阈值可由 agent.

拒绝规则 :
- 如果用户无法在前面点出阈值, 请拒绝。 设定的阈值不是阈值; 它们属于合理化 。
- 如果输油管没有外部(流出)评价器,则拒绝——回归和激增探测需要外部观察。
- 如果拟议的恢复合同是“通知小组并在24小时后继续”,则拒绝。恢复必须是积极的行动。

输出格式 :

返回一页规格 :
- **轴和阈值** (table)
- **周期- delta 限制** (table)
- **失调差值公式和阈值**
- **递减限制**
- **外部评价员** (它是什么,当它运行)
- **恢复合同** (名称所有人、核对表、日志目的地)
- **签名行** (谁拥有停顿的变数)
