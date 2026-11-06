---
name: sim2real-planner
description: Plan a sim-to-real transfer pipeline for a given robot + task, covering DR, SI, and safety.
version: 1.0.0
phase: 9
lesson: 11
tags: [rl, sim2real, robotics, domain-randomization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个机器人平台、一个任务以及对真实硬件时间的访问，输出：

1. 现实差距清单。可疑来源按预期影响（接触、传感、驱动延迟、视觉）排名。
2. parameters 博士。精确的列表、范围、分布。根据实际测量结果证明每个范围的合理性。
3. SI 步骤。其中parameters来测量；测量方法。
4. 教师/学生分裂。老师使用哪些特权信息；学生使用什么 obs。
5. 安全信封。低液位限制、紧急停止、备用控制器。

在没有 (a) zero-shot sim 变体测试、(b) 安全防护罩、(c) rollback 计划的情况下拒绝部署。将任何大于 3 倍测量的真实变异性的 DR 范围标记为可​​能过度随机。
