---
name: web-desktop-harness
description: Build a WebArena/OSWorld-style harness with execution-based evaluation and trajectory-efficiency metrics.
version: 1.0.0
phase: 14
lesson: 20
tags: [webarena, osworld, harness, trajectory-efficiency]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给目标应用程序( 网络或桌面) 和一份包含金轨的任务列表, 创建一个 eval harness.

显示 :

1. 任务定义 : `(tid, description, gold_steps, success_predicate, state_reset)`.
2. 运行者: 运行 agent,记录每个动作,记录步骤数+已过时间+成功状态。
3. 轨迹效率衡量标准: `agent_steps / gold_steps`. 报告每个任务和总和。
4. 国家重新安排任务——从不执行一个被另一个国家玷污的任务。
5. 失败模式分类器: 对于每个失败, 标记它是否为 grounding 错误元素或一个 planning 错误动作

艰难的拒绝 :

- 任务之间没有状态重置。 交叉任务污染会使所有分数无效 。
- 成功率报告。轨迹效率是2026年的标准。
- Screenshots-only harness 部分没有 DOM 等值。 agents 使用 DOM+View; 给两者, 除非有特定的表面约束 。

拒绝规则 :

- 如果任务没有金色轨迹, 请拒绝。 没有这些轨迹, 您无法测量效率 。
- 如果应用程序没有被锁定到特定版本, 请拒绝。 Drift 将交叉运行比较无效 。
- 如果 agent 具有破坏性工具(删除、发布),需要 sandbox 应用程序副本

输出: `tasks.py`, `runner.py`, `failure_classifier.py`, `report.py`, `README.md` 解释重置策略、金轨来源和 grounding-与-planning 拆分。结尾处为“下一步读什么”指向21课(计算机使用模型)或30课(由电子软件驱动的开发)。
