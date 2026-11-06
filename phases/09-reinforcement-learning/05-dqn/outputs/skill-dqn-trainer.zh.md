---
name: dqn-trainer
description: Produce a DQN training config (buffer, target sync, ε schedule, reward clipping) for a discrete-action RL task.
version: 1.0.0
phase: 9
lesson: 5
tags: [rl, dqn, deep-rl]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定离散动作环境（观察形状、动作计数、视野、奖励规模），输出：

1. 网络。架构（MLP / CNN / Transformer），feature 昏暗，深度。
2. 重播缓冲区。容量、小批量大小、warmup 大小。
3. 目标网络。同步策略（每 C 步硬同步或 τ 软同步）。
4. 探索。 ε 开始/结束/日程长度。
5. 损失。 Huber vs MSE，gradient 剪辑值，奖励剪辑规则。
6. 双DQN。除非有明确的禁用理由，否则默认开启。

拒绝运送没有目标网络、没有重播缓冲区或 ε 保持为 1 的 DQN。拒绝连续操作任务（路由到 SAC / TD3）。将任何> 10×每步平均值的奖励范围标记为需要剪裁或缩放 normalization。
