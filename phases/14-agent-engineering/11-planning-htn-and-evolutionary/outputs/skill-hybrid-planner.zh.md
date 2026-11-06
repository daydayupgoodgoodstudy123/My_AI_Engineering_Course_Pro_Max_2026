---
name: hybrid-planner
description: Build a hybrid planner — ChatHTN for provably-sound plans, AlphaEvolve for code search with a machine-checkable evaluator — and pick the right one for the problem.
version: 1.0.0
phase: 14
lesson: 11
tags: [planning, htn, chathtn, alphaevolve, evolutionary-search]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给问题类别( 受政策约束的工作流程) vs code 优化与开放的任务,选择一个规划者并产生一个正确的脚手架。

Decision:

1. 这一问题是否有困难的先决条件/政策/时间安排限制? - > HTN(乍得)
2. 问题是否具有确定性的、机器可检查的健身功能? - > 演化(阿尔法伏)。
3. - 两者都没有? ReAct 改为(Lesson 01)或(Lesson 02)。

对于HTN, 生产:

1. `Operator` 类型 `preconditions`, `effects_add`, `effects_remove`.
2. `Method` 类型 `task`, `preconditions`, `subtasks`.
3. 计划者先尝试方法,然后返回 LLM 分解和缓存成功 LLM decompositions.
4. 拒绝的验证步骤 LLM 引用未知操作员或方法的分解。

用于进化,生产:

1. 候选方案的种子数量。
2. 一位决定性的评价员 返回一个标量的健身。
3. 突变操作员( A)LLM- 驱动或基于规则的)。
4. 选择环( 保留顶部, 变异, 重复) , 早期停止 。

艰难的拒绝 :

- 聊天hTN 位置 LLM 输出直接应用,而不经过操作员-系统验证。健康要求失败。
- 阿尔法演算器,评价员叫它 LLM 法官,必须确定是否适合; LLM 法官们会发出无法恢复的随机噪音。
- 两种模式都用于无期限任务 (“ 写博客文章 ” )。 没有评估员, 没有先决条件 - > 使用 ReAct.

拒绝规则 :

- 如果域名没有明确的操作器图案, 请拒绝 ChatHTN。 建议重组织或平面 ReAct.
- 如果域没有机器检查的功能, 请拒绝 AlphaEvolle 。 建议自定义( Lesson 05) 。
- 如果用户想要"规划器+ LLM 拒绝。 象征正确性和 LLM 勘探是载荷。

输出: `operators.py`, `methods.py`, `planner.py` (HTN)或(HTN) `evaluator.py`, `mutator.py`, `loop.py` (进化)加 `README.md` 以“下一步读什么”结束,指向25号课,如果辩论式的核查符合问题,或者说02号课,如果任务实际上是再生组织形。
