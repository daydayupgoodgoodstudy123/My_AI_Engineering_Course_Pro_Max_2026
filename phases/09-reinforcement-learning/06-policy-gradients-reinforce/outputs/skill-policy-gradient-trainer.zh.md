---
name: policy-gradient-trainer
description: Produce a REINFORCE / actor-critic / PPO training config for a given task and diagnose variance issues.
version: 1.0.0
phase: 9
lesson: 6
tags: [rl, policy-gradient, reinforce]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个环境（离散/连续动作、视野、奖励统计），输出：

1. 策略负责人。 Softmax（离散）或高斯（连续）与 parameter 计数。
2. 基线。无（普通），运行意思是，学习了 `V̂(s)` 或 A2C critic。
3. 方差控制。 Reward-to-go 默认打开，返回 normalization、gradient 剪辑值。
4. Entropy bonus。系数 β 和衰减时间表。
5. Batch size。每次更新的剧集数； on-policy数据新鲜度合约。

拒绝 REINFORCE-地平线 > 500 步上无基线。拒绝使用 softmax 头进行连续动作控制。将任何带有 `β = 0` 的运行和观察到的策略熵 < 0.1 标记为熵崩溃。
