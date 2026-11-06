---
name: marl-picker
description: Choose a MARL algorithm (MADDPG, QMIX, MAPPO, IQL, or extensions) for a given multi-agent task. Consider cooperative vs competitive, action-space type, heterogeneity, reward structure, and scale.
version: 1.0.0
phase: 16
lesson: 20
tags: [multi-agent, MARL, MADDPG, QMIX, MAPPO, CTDE]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


假设一个多...agent 任务描述,选择 MARL 算法。

显示 :

1. **任务分类学** 充分合作(分享奖励)、充分竞争(零和)、混合、一般和 agents。同质和异质。
2. **Observability.** 满( 每个 agent 或通过通讯实现。
3. **活动空间。** 分解( 类似 Atari 的 SMAC) 或连续( 粒子世界, MuJoCo) 。 效果算法选择 。
4. **奖赏结构。** 浓度( 以每步计) 相对于稀薄( 仅限终点) 。 浓度使 MAPPO 变得实用; 稀薄需要信用分配帮助( QMIX 的价值分解) 。
5. **说明性建议。** 以MAPO作为基准开始,以Yu等人(2022年)为基准。
   - 当需要合作+同质+强度微薄的回报信用分配时, QMIX
   - 混合(合作+竞争)+连续行动时MADDPG
   - 当单音限制过强时的扩展( QTRAN、 QPLEX、 FACMAC)
6. **培训基础设施。** 您是否有: 足够的互动数据, 计算预算, 奖励塑造专业知识, 稳定预算( 每试验5- 10种种子) ? 如果不是, 建议 prompt- 各级政策 LLM agents.
7. **部署合同。** CTDE: 部署时间 agent 写好合约,所以时间代码尊重它

艰难的拒绝 :

- 选择非 MAPPO 的第一次运行基线。 MAPPO 是 2026 年的基准; 从那里开始 。
- 使用 QMIX 进行混合合作竞争任务, 价值分解假设为单质聚合。
- 建议对MARL进行培训,以便 LLM-agent 缺乏互动数据或奖励信号的系统。 Prompt- 级别政策将超过数据。
- 培训,不计记录agent 观察和动作。 无法调试 。

拒绝规则 :

- 如果任务互动数据小于~ 1 000 个插件, 建议 prompt- 级别政策或监督 fine-tuning.
- 如果任务不是马尔科维安语( 需要记忆), 但建议不包括经常性的 critics标出缺口
- 如果任务具有一般和竞争性(多重平衡),则仅靠最低运作安保标准不能选择一种;建议机制设计或均衡选择。

输出: 一页简况。 从一个一句话建议开始 (“ MAPPO 基线, 集中化 ” value function; 每-agent discrete actor中方的“技术”和“技术”是“技术”。 evaluation, rollout.
