---
name: marl-architect
description: Pick the right multi-agent RL regime (IPPO, CTDE, self-play, league) for a given task.
version: 1.0.0
phase: 9
lesson: 10
tags: [rl, multi-agent, marl, self-play]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个带有 `n` agents 的任务，输出：

1. 政权分类。合作/对抗/一般和。证明合法。
2. 算法。 IPPO / MAPPO / QMIX / 自战 / 联赛。原因与耦合紧密度和奖励结构有关。
3. 信息访问。集中训练（哪些全局信息发送至 critic）？分散执行？
4. 学分分配。反事实基线、价值分解或奖励塑造。
5. 探索计划。 Per-agent 熵、基于人群的训练或联盟。

在紧耦合的协作任务上拒绝独立的 Q-learning。拒绝推荐具有循环风险的一般和自对弈。标记任何没有固定对手评估的 MARL 管道（精心挑选的自我对弈数字很常见）。
