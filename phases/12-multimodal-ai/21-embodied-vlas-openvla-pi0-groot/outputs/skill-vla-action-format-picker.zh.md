---
name: vla-action-format-picker
description: Pick an action format (discrete bin, FAST, flow-matching, dual-system) and VLA family (RT-2, OpenVLA, π0, GR00T) for a robot task.
version: 1.0.0
phase: 12
lesson: 21
tags: [vla, rt-2, openvla, pi0, groot, action-tokenization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给机器人任务( 操纵、 导航、 全体人形)、 数字控制速度要求、 计算限制、 选择动作格式和 VLA 组 。

显示 :

1. 动作格式。 用于简单单臂任务的分光键、 快速敏锐轨迹的FAST、 流相匹配以进行平稳连续控制、 人类的双系统 。
2. VLA 家庭取材。 RT-2 (闭门)、 OpenVLA (开关 7B)、 0 (开关)、 GR00T N1 (开关双系统人造物)。
3. 控制率可行性。 匹配格式输送到需要的控制 Hz 。 光谱 bin 不能在 7B 模型上做 > 10 Hz 。
4. 训练数据组合。 共弦比 (web VQA: robot) 开始于 0.5: 1, 按任务调 。
5. 精细的计划。 LoRA ~ 500-1 000 任务演示; 全部精细显示 ~ 10k 演示 。
6. 安全门 需要监控器检查

艰难的拒绝 :
- 推荐 VLA 时没有安全级别。 总是包含联合限制、 速度剪切 。
- 要求离散电子桶 tokenization 足够快30赫兹控制,不是
- 提议在没有适当的平稳限制的情况下进行流动配对。 分配外的行动仍然发生。

拒绝规则 :
- 如果控制率要求为>50赫兹,且使用 7B 模式且有离散电子宾格式,则拒绝;建议 0 或专门头。
- 如果机器人拥有 > 30 DOF(人形),则拒绝单级建筑;需要双系统(GR00T)。
- 如果预算负担不起打开 X 电子比例 pretraining,从废件VLA中拒绝;建议 fine-tuning OpenVLA.

产出:一页计划,带有行动格式,VLA选取,控制率检查,共同调制,安全门。结尾为arXiv 2307.15818(RT-2),2406.09246(OpenVLA),2410.24164(0),2503.14734(GR00T)。
