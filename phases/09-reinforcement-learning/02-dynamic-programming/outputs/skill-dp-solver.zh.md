---
name: dp-solver
description: Solve a small tabular MDP exactly via policy iteration or value iteration. Report convergence behavior.
version: 1.0.0
phase: 9
lesson: 2
tags: [rl, dynamic-programming, bellman]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个具有已知模型的 MDP，输出：

1. 选择。策略迭代与价值迭代。原因与 |S|, |一个|, γ.
2. 初始化。 V_0，启动策略。收敛灵敏度。
3. 停下来。超标准公差 ε。预期扫描次数。
4. 验证。 V*(s_0) 计算准确。提取贪婪策略。
5. 使用。如何使用此基线来调试/评估基于 sampling 的方法。

拒绝在状态空间 > 10⁷ 上运行 DP。拒绝在没有超范数检查的情况下声称收敛。将无限范围任务上的任何 γ ≥ 1 标记为保证违规。
