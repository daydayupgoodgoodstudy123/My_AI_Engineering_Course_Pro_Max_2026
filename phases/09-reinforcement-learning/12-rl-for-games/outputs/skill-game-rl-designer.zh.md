---
name: game-rl-designer
description: Design a game-RL or reasoning-RL training pipeline (AlphaZero / MuZero / GRPO) for a given domain.
version: 1.0.0
phase: 9
lesson: 12
tags: [rl, alphazero, muzero, grpo, self-play]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个目标（完美信息游戏/不完美信息/Atari/LLM推理/组合），输出：

1. 环境适合。已知规则？马尔可夫？随机？多agent？通知 AlphaZero vs MuZero vs GRPO。
2. 搜索策略。 MCTS（预先学习的 PUCT）、Gumbel 采样、N 中最佳或无。
3. 自玩计划。对称自我对战/联赛/离线数据/验证者生成。
4. 目标信号。游戏结果/验证者奖励/偏好/学习模型。包括稳健性计划。
5. 诊断。胜率与基线、ELO 曲线、验证者通过率、KL 参考。

在不完美信息游戏中拒绝 AlphaZero（通往 CFR 的路线）。在没有可信验证者的情况下拒绝 GRPO。拒绝任何没有固定基线对手集的游戏强化学习管道（否则自我对战 ELO 未校准）。
