---
name: ppo-trainer
description: Produce a PPO training config and a diagnostic plan for a given environment.
version: 1.0.0
phase: 9
lesson: 8
tags: [rl, ppo, policy-gradient]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定环境和培训预算，输出：

1. Rollout 尺寸。 `N` envs × `T` 步骤。
2. 更新时间表。 `K` epoch、小批量大小、LR 时间表。
3. 代理参数。 `ε`（剪辑），`c_v`，`c_e`，优势normalization上。
4. 优势。 GAE(`λ`) 具有显式 `γ` 和 `λ`。
5. 诊断计划。 KL，剪辑分数，用警报解释方差阈值。

拒绝`K > 30`或`ε > 0.3`（不安全的信任区域）。拒绝任何 PPO 运行而没有优势 normalization 或 KL/clip 监控。将剪辑分数持续高于 0.4 标记为漂移。
