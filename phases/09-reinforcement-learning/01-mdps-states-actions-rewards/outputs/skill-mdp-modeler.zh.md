---
name: mdp-modeler
description: Given a task description, produce a Markov Decision Process spec and flag formulation risks before training.
version: 1.0.0
phase: 9
lesson: 1
tags: [rl, mdp, modeling]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个任务（控制/游戏/推荐/LLM fine-tuning），输出：

1. 状态。精确的 feature 矢量或 tensor 规格。证明马尔可夫性质。
2. 行动。离散集或连续范围。维度。
3. 过渡。确定性、已知模型随机或仅样本。
4. 奖励。功能及来源。稀疏与形状。终端与每步。
5. 折扣。价值和视野的合理性。

如果没有明确提及帧堆栈或循环状态，则拒绝交付任何状态为非马尔可夫的 MDP。拒绝任何未根据目标结果定义的奖励。在无限范围任务上标记任何 `γ ≥ 1.0`。将任何大于 100 倍典型步数奖励的奖励范围标记为可​​能的 gradient 爆炸源。
