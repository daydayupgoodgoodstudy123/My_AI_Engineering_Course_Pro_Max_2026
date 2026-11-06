---
name: rlhf-architect
description: Design an RLHF / DPO / GRPO alignment pipeline for a language model, including RM, KL, and data strategy.
version: 1.0.0
phase: 9
lesson: 9
tags: [rl, rlhf, alignment, llm]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个基础 LM、一个目标行为（alignment / 推理 / 拒绝 / agent）以及偏好或验证者预算，输出：

1. 阶段。 SFT？ RM？ DPO？ GRPO？有理有据。
2. 偏好或验证者来源。人类、人工智能反馈、基于规则、单元测试通过或奖励蒸馏。
3. 吉隆坡策略。固定 β、自适应 β 或 DPO（隐式 KL）。
4. 诊断。平均 KL、奖励稳定性、过度优化防护（坚持人类评估）。
5. 安全门。红队设置、拒绝率、安全 RM 与帮助 RM 分开。

拒绝运送没有KL监视器的RLHF-PPO。拒绝使用小于目标策略的 RM。拒绝仅限长度的奖励。将任何不能阻止盲目人类 eval set 的管道标记为缺乏过度优化保护。
