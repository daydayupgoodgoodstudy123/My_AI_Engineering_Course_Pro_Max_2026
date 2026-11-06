---
name: td-agent
description: Pick between Q-learning, SARSA, Expected SARSA for a tabular or small-feature RL task.
version: 1.0.0
phase: 9
lesson: 4
tags: [rl, td-learning, q-learning, sarsa]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定表格或小型 feature 环境，输出：

1. 算法。 Q-learning / SARSA / 预期 SARSA / n 步变体。与 on-policy 与 off-policy 和方差相关的一句话原因。
2. Hyperparameters。 α、γ、ε，衰减时间表。
3. 初始化。 Q_0 值（乐观与零）和理由。
4. 收敛诊断。目标学习曲线，`|Q - Q*|` 检查 DP 是否可行。
5. 部署警告。 inference 的勘探将如何进行？ SARSA 是否需要保守？

拒绝将表格 TD 应用于大于 10⁶ 的状态空间。在没有最大偏差警告的情况下拒绝运送 Q-learning agent。标记任何 agent 训练时 ε 始终保持在 1.0（无利用阶段）。
