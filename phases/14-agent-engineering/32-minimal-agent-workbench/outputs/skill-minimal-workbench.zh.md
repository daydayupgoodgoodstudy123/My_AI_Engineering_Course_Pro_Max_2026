---
name: minimal-workbench
description: Lay down the three-file minimum viable agent workbench for any repo — short AGENTS.md router, durable agent_state.json, and a JSON task_board.json keyed to the project's current backlog.
version: 1.0.0
phase: 14
lesson: 32
tags: [workbench, agents-md, state, task-board, scaffold]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


有了回购路线和短时间的积压, 脚架就成了最起码可行的 agent workbench.

显示 :

1. `AGENTS.md` 不超过 80 行。 它必须经过: 国家文件、 任务板、 更深的规则( 即使是空的) 和校验命令。 此文件中没有 Property 教程 。
2. `agent_state.json` 使用这些密钥 : `active_task_id`, `touched_files`, `assumptions`, `blockers`, `next_action`。所有可选字段默认为空数组或空字符串,从不 `null` 用于数组。
3. `task_board.json` 以 A 为单位 JSON 任务矩阵。 `id`, `goal`, `owner` (`builder` | `reviewer` | `human`), `acceptance` (字符串列表),以及 `status` (`todo` | `in_progress` | `done` | `blocked`).
4. `docs/agent-rules.md` 占位符,每表面有一个H2, 以便以后的课能填充它。

艰难的拒绝 :

- `AGENTS.md` 超过80条线或10条线以下。 agent 跳过它,太短,没有路由。
- 引用聊天历史而非回购的州文件。 repo 是记录系统 。
- 任务栏没有 `acceptance`。没有接受标准的任务将成为“看起来不错”的橡胶邮票。
- 任务 `owner` 是 `agent` 或 `model`所有人是角色,而不是实体。

拒绝规则 :

- 如果回购没有校验命令, 请拒绝写入 `AGENTS.md` 指向缺失的大门的路由器比没有路由器还差
- 如果积压有超过12个未打开的任务, 请拒绝并要求用户分割它。 校对:Soup planning theater.
- 如果项目船在追踪文件中有秘密, 拒绝写入国家文件, 并显示秘密泄漏作为阻塞发现先。

产出结构:

```
<repo>/
├── AGENTS.md
├── agent_state.json
├── task_board.json
└── docs/
    └── agent-rules.md
```

结尾处指向“ 下一步要读什么” :

- 将规则占位符变成可执行的限制的第33课
- 耐久国家计划第34课
- 课程36 scope contract 每项任务。
