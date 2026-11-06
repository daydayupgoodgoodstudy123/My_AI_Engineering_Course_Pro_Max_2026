---
name: search-policy
description: Pick a search strategy (ReAct, ToT, LATS, evolutionary) given task shape, token budget, and evaluator quality.
version: 1.0.0
phase: 14
lesson: 04
tags: [tree-of-thoughts, lats, mcts, search, value-function]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以任务形状(单一回答/多回答/不限时间)为单位, a token budget,以及现有的评估员(标尺测试/超常测试/自我评价),提出含有混凝土的搜索策略建议 parameters.

显示 :

1. 决定. 一项: ReAct,光束托盘(带光束宽k)、BFSTO(带最大深度)、有剪接的外勤部托盘、MCTS LATS(带迭代和UCTc)、进化搜索(只有评价员是编程和可检查的)。
2. Parameters。对于每个策略,具体的数值默认值:光束宽度、深度上限、分流系数K, rollouts 超时(UCTc)(默认值1.4),超时。
3. Value function。指定一个节点的得分。选项:单位测试通过率,目标的数字距离,触发 LLM 得分,以格式(保证/可能/不可能或1.10或投票)或环境奖励。
4. Token budget 最坏情况 tokens =分支_度数  深度 * avg_prompt_符号。 显示数字。 如果超过用户预算, 请推荐一个更便宜的战略 。
5. 失败模式。 对于所选的每一种战略,请列出前二种失败模式及其缓解措施(如 LATS + 噪音评价器 - > 添加工具背景的校验 CRITIC05课

艰难的拒绝 :

- 评估员不可靠时建议搜索( 仅进行自我评价, 没有地面真相) 。 ReAct + CRITIC.
- 设定分支系数 K 高于 5, 没有令人信服的理由。 K=3-5 是纸张默认值; K=10 爆炸成本 。
- 应用 LATS 来进行聊天式任务。 搜索无助于没有程序目标的 {A} 对话 。
- 进化搜索, 没有机器检查的健身。 只有在健身程序( 运行测试、 测量速度、 校验定理) 时, 阿尔法演算才有趣 。

拒绝规则 :

- 如果 token budget < 5x单轨费用,拒绝查询和建议 ReAct + 反射(列松03)。
- 如果挂在墙上的预算 < 10秒, 拒绝 LATS 并推荐 ReAct.
- 如果任务纯粹是信息检索,则拒绝搜索,并建议进行再工作网络查询(Lesson 02)。

产出:建议块(选定战略, parameters, value function,预算估计数)加上“下一个读什么”的说明,指向第05号课(CRITIC用于评价人的可靠性,关于进化变异的教程11(阿尔法亚沃),或关于基准级验证的教程30(由电子学驱动的开发)。
