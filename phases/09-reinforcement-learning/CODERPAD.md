# 09-reinforcement-learning：CoderPad 练习

本章 12 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
核心 6 cases、加分 2 cases。题目是原课程中的一个编码切面，不要求运行完整训练、云服务或 GPU。
相同基础 kernel 会在相关课程复用；请在复盘中区分“未见题”与“重复练习”。
运行方法：进入任一项目的 `coderpad/`，阅读 README/PROMPT，再执行：

```bash
python3 run_tests.py --list
python3 run_tests.py --core
```

初始失败是 TODO 的正常起点；计时结束后才打开 solution 或使用 `--solution`。
面试官材料、评分与复盘模板均在每套目录；计时器自行设置。

| 课号 | 主题与题目入口 | 核心 | 加分 |
| --- | --- | --- | --- |
| 01 | [MDPs, States, Actions & Rewards](01-mdps-states-actions-rewards/coderpad/README.md) | Bellman 最优备份 | 马尔可夫状态分布 |
| 02 | [Dynamic Programming — Policy Iteration & Value Iteration](02-dynamic-programming/coderpad/README.md) | Bellman 最优备份 | 折扣回报 |
| 03 | [Monte Carlo Methods — Learning from Complete Episodes](03-monte-carlo-methods/coderpad/README.md) | 折扣回报 | 均值与总体方差 |
| 04 | [Temporal Difference — Q-Learning & SARSA](04-q-learning-sarsa/coderpad/README.md) | Q-learning 更新 | 折扣回报 |
| 05 | [Deep Q-Networks (DQN)](05-dqn/coderpad/README.md) | Q-learning 更新 | 梯度范数裁剪 |
| 06 | [Policy Gradient — REINFORCE from Scratch](06-policy-gradients-reinforce/coderpad/README.md) | 折扣回报 | 数值稳定的 Softmax |
| 07 | [Actor-Critic — A2C and A3C](07-actor-critic-a2c-a3c/coderpad/README.md) | Actor-Critic Advantage | 梯度下降一步更新 |
| 08 | [Proximal Policy Optimization (PPO)](08-ppo/coderpad/README.md) | PPO Clipped Surrogate | Actor-Critic Advantage |
| 09 | [Reward Modeling & RLHF](09-reward-modeling-rlhf/coderpad/README.md) | 偏好对的稳定 Loss | 分类混淆矩阵指标 |
| 10 | [Multi-Agent RL](10-multi-agent-rl/coderpad/README.md) | Quorum 与重复选票 | Q-learning 更新 |
| 11 | [Sim-to-Real Transfer](11-sim-to-real-transfer/coderpad/README.md) | 评估锚点漂移 | 阈值异常检测 |
| 12 | [RL for Games — AlphaZero, MuZero, and the LLM-Reasoning Era](12-rl-for-games/coderpad/README.md) | Bellman 最优备份 | 探索与利用调度 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
