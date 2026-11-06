---
name: constitution-review
description: Audit a deployment's constitutional layer — hardcoded prohibitions, soft-coded defaults, operator-adjustable bounds, and four-tier hierarchy resolution.
version: 1.0.0
phase: 15
lesson: 17
tags: [constitutional-ai, rule-override, hierarchy, cai, rlaif, hardcoded-prohibition]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


部署的宪法层面system prompt,操作员配置,宣布的原则,根据 Claude 宪法参考和标志缺少硬编码的禁令、模糊的原则或顺序不当的层级。

显示 :

1. **硬码禁止库存。** 列出禁止规定,不论操作员或用户指示如何,不得弯曲。 planning增加的内容是针对部署的(例如,金融服务增加了具体的欺诈禁令)。
2. **软编码默认值 。** 列出操作员可以调整的每一种行为。 对于每一个行为, 请声明声明约束。 “ 调整” 设置是后门覆盖 。
3. **订货** 确认解决方案的顺序是:安全 > 道德 > 指南 > 帮助。 如果帮助在已执行的解决方案者中胜过道德操守,则标为部署中断。
4. **原则模糊标志。** 说明任何原则,其案文允许作出实质性不同的解释。
5. **层层完整。** 除了宪法层面之外,还存在确认运行时间控制(第10、13、14条),仅《宪法》是不够的;仅运行时间是不够的。

艰难的拒绝 :
- 部署时没有任何硬编码的禁止层。
- 操作员配置, 声称推翻硬码禁令( 即使重新命名 ) 。
- 等级命令,将帮助置于道德之上。
- 原则性案文如此笼统,无法评价(“好”)。
- 将《宪法》大赦国际作为运行时间控制的一种替代。

拒绝规则 :
- 如果用户命名硬码禁令,但无法指向运行时间段的后援,则将部署标为单层,拒绝生产。
- 如果操作员配置包括一个可调整的“安全”设置,且没有声明约束,则拒绝。
- 如果用户认为2023年的参与性宪法结论在当前部署中是可以执行的,请检查:2026年的宪法没有纳入这些结论,因此“民主的继承人”是部署不能后退的说法。

输出格式 :

退回宪法审计,包括:
- **硬码楼层** (禁止、执行层: weights / inference /两者)
- **软编码默认** (设置、操作员受约束、用户可见 y/n)
- **级别顺序** (列出;确认的安全 > 道德 > 准则 > 帮助)
- **模糊标志** (原则、具体含糊之处、提议收紧)
- **图层完整性** (宪法y/n,运行时间控制y/n,两者均需)
- **Readiness** (生产/中转/仅研究)
