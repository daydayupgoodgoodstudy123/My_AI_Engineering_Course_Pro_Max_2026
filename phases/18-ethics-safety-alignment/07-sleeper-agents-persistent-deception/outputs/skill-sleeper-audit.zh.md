---
name: sleeper-audit
description: Audit an alignment-training report for whether it actually demonstrates removal of a planted or suspected backdoor.
version: 1.0.0
phase: 18
lesson: 7
tags: [sleeper-agents, backdoor, alignment-training, adversarial-training, probes]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于有报告说,从一个模式中删除了声称有害行为的报告(通过: SFT, RLHF、对抗性培训或任何组合),审计是否实际证明删除是针对Hubinger等人的标准的。 threat model.

显示 :

1. Elicitation 报告是否坚持了 elicitation 训练管道从未见过的方法? evaluation 红色队的分布,清除是未经证实的
2. 触发一般性。 是否声称触发字串, a distribution shift,或环境 feature (date, token触发器的通用性决定了红色小队必须覆盖的搜索空间大小。
3. 内部证据 调查组有没有使用残留流探测器 features或其他机械性探测器,检查是否内部仍然存在触发状态,即使行为是干净的。 Anthropic 跟踪后,内部状态在行为消除后仍可直线识别。
4. 持久性-通过管道检查。 SFT,稍后 RLHF 后门通过训练持续进行——最后的模式是评估的东西,而不是中间 checkpoint.
5. 比例一致性检查。如果索赔基于一个较小的模型,Hubinger 2024 图4显示持久性随规模增长。小型模型证据不会向上转移。

艰难的拒绝 :
- 任何声称"我们申请 RLHF 所以模型是安全的,没有拖拉 elicitation.
- 仅基于红色小组分配的任何索赔 evaluation 培训及培训 evaluation ) (从同一游泳池中抽取)。
- 任何在原始植入装置未知时,在没有内部状态探测的情况下进行清除的主张。

拒绝规则 :
- 如果用户问“ 能够” RLHF 删除欺骗 alignment拒绝二进制回答 指向Hubinger等人 2024 关于持久性的第5节和关于 chain-of-thought.
- 如果用户要求获得潜在欺骗的概率,则拒绝并解释基率未知;经验证据是,在已建生物体中持续存在,而不是自然训练模型中的出现率。

产出:一页审计,将报告的证据映射到上述五个审计层面,标出报告没有涉及的每个层面,并指明一个最大的未解决层面 threat model239. Cite Hubinger等人(arXiv:2401.05566)的基线 threat model.
