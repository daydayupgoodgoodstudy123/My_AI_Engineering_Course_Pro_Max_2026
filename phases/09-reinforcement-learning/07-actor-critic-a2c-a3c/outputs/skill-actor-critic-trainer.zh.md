---
name: actor-critic-trainer
description: Produce an A2C / A3C / GAE configuration for a given environment, with advantage estimation and loss weights specified.
version: 1.0.0
phase: 9
lesson: 7
tags: [rl, actor-critic, gae]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定环境和计算预算，输出：

1. 并行性。 A2C（GPU 批处理）与 A3C（CPU 异步）以及工作人员数量。
2. Rollout 长度 T。每次更新每个环境的步骤。
3. 优势估计器。 n步或GAE(λ)；指定 λ。
4. 损失weights。 `c_v`（值）、`c_e`（熵）、gradient 剪辑。
5. Learning rates。 Actor 和 critic（如果使用则分开）。

在地平线> 1000的环境中拒绝单工作人员A2C（太on-policy，太慢）。无优势拒绝发货normalization。将任何带有 `c_e = 0` 的运行和观察到的熵 < 0.1 标记为熵崩溃。
