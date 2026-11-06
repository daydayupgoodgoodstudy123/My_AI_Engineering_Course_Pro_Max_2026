---
name: workbench-audit
description: Audit a repo for the seven agent workbench surfaces and report which are missing, partial, or healthy before any agent work begins.
version: 1.0.0
phase: 14
lesson: 31
tags: [workbench, audit, reliability, agent-engineering]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定仓库路径和 agent 将运行在它的产品, 审计7个工作台表面 并产生准备状态报告。

七面图:

1. 说明: 根文件 agent 案文第一(例如,第1款) `AGENTS.md`简而言之,这是通往更深层次规则的路线。
2. 状态: 一个耐久、机器可读的文件, 它记录任务、 触摸文件、 阻塞器、 下一步动作 。
3. 范围:每份任务清单允许的文件、被禁止的文件、接受标准、 rollback plan.
4. 反馈: 一种捕捉命令、 stdout、 stderr、退出代码并将结果反馈到循环的运行者。
5. 验证: 运行测试、 输入、 输入和确认接受标准的门 。
6. 审查:第二个通过,角色不同,建筑商无法标志自己的工作。
7. Handoff:一个总结变化的文物,为什么,剩下的是什么,以及下一个最佳动作。

显示 :

- 每表面得分: 0 缺失, 1 部分, 2 健康。 每个得分都绑在您所观察到的文件或进程上 。
- 由杠杆排列的三个优先事项:如果首先增加的缺失表面,则消除了最失败的模式。
- 一个 `workbench_audit.json` 可机器读报告加a `workbench_audit.md` 人类可读摘要。
- 开始器 patch 最小表面的数值:最小的文件更改, 将分数从 0 移动到 1 。

艰难的拒绝 :

- 没有文件路径或进程参考的“健康”分数。 审计没有证据, 就会腐烂。
- 单一组合 "agent 配置” 表面。 组合表面隐藏任务中断时失败的表面 。
- 跳过验证是因为测试缓慢。 如果验证不在工作台, 建筑者会标记自己的作业 。

拒绝规则 :

- 如果回购根本没有测试命令, 请拒绝校验分, 并显示为屏蔽结果 。
- 如果回购没有版本控制历史, 请拒绝 handoff 得分,并表面 作为阻塞发现。
- 如果 agent 产品作为根运行或不受限制的文件访问,拒绝范围评分,直到 sandbox 或写入列表。

产出结构:

```
workbench-audit/
├── workbench_audit.json
├── workbench_audit.md
├── patches/
│   └── <weakest-surface>.patch
└── README.md
```

结尾处指向“ 下一步要读什么” :

- 32课,最起码的回购布局
- 深度说明的33课
- 课程38 verification gate.
