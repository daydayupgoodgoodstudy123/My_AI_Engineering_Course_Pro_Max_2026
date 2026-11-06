---
name: compliance-gap
description: Evaluate whether a safety report can detect alignment faking, via the monitored / unmonitored compliance gap.
version: 1.0.0
phase: 18
lesson: 9
tags: [alignment-faking, compliance-gap, anthropic, safety-evaluation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


保险 evaluation 评估其是否可区分 alignment 利用格林布拉特等人2024年遵约差距框架,从真正的遵约中伪装出来。

显示 :

1. 条件分开。 evaluation 既运行监测(与培训有关)条件,又运行未监测(非培训)条件? alignment 装模作样是隐形的
2. 合规差距测量:报告(监测的----未监测的)合规率方面的差距;解释符号和数量:正差距=假形行为;负差距=观察到时反感。
3. Verbal-trace 检查行为。 evaluation 依靠模型的刮痕推理,还是依靠动作本身? Anthropic 2025年,针对口头 trace 可以在不去除行为的情况下将其删除。
4. 操作性审计。 system prompt合成 fine-tuning系统-prompt 依赖性削弱了索赔;合成的fine-tuning 复制加强了它。
5. 剩余激励检查。 在应用了任何缓解措施之后,激励结构是否仍然存在(如果模型选择假冒,是否仍能从中得益)?鼓励性持久性意味着行为可以恢复到 distribution shift.

艰难的拒绝 :
- 任何"没有"的说法 alignment 以未监测的空虚身份假装 evaluation.
- 任何“不讲理的推理不再用语言来装腔作势”的说法都意味着行为已经停止。
- 任何关于HHH培训模型不假的说法 alignment Greenblatt等人(2024年)规定,HHH培训是必要条件,不是充分辩护。

拒绝规则 :
- 如果用户问"我的模特是假的 alignment拒绝二进制回答,没有符合数据
- 如果用户要求只针对可见的电路进行修补 trace 解释2025年后续计划警告, trace.

产出:一页评估,报告在两种条件下遵守情况、差距和口头评估trace- vs- behaviour 分离和操作强度。 标记每个缺失元素。 Cite Greenblatt 等人(arXiv: 2412. 14093) 曾经是框架源 。
