---
name: mc-evaluator
description: Evaluate a policy via Monte Carlo rollouts and produce a convergence report with DP-comparison if available.
version: 1.0.0
phase: 9
lesson: 3
tags: [rl, monte-carlo, evaluation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个环境（情景式，带有重置+步骤 API）和策略，输出：

1. 方法。首次访问与每次访问 MC。原因。
2. 剧集预算。目标数、方差诊断、预期标准误差。
3. 探索计划。 ε 时间表（如果需要）或探索开始。
4. 黄金标准比较。 DP 最佳 V*如果是表格； 否则从a的界限Q-learning/PPO基线。
5. 终止检查。最大步数上限、超时、非终止轨迹的处理。

拒绝在没有有限期限上限的非偶发性任务上运行 MC。对于表格任务，拒绝报告每个州少于 100 集的 V^π 估计值。将任何具有零方差操作的策略标记为探索风险。
