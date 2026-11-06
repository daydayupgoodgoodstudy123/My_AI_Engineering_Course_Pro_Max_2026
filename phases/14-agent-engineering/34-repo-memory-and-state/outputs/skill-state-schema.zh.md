---
name: state-schema
description: Generate project-specific JSON Schemas for agent state and task board, a Python StateManager with atomic writes, and a migration scaffold so schema bumps cannot corrupt the workbench.
version: 1.0.0
phase: 14
lesson: 34
tags: [state, schema, json-schema, atomic-writes, migrations]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给回购和 agent 生产出工作台的系统第一状态文件

显示 :

1. `schemas/agent_state.schema.json` 包含所需的密钥、允许状态值、数组- vs- null 门类和 a `schema_version` integer.
2. `schemas/task_board.schema.json` 包含任务代号模式、允许所有者、允许状态和接受数组。
3. `tools/state_manager.py` exposing `load`, `commit`, 和 `update` 使用临时和重命名原子写作。
4. `tools/migrate_state.py` 用于下一个图案的脚架,如果文件来自未知版本,则会断开。
5. `agent_state.json` 和 `task_board.json` 种子于 `schema_version: 1` 和新的积压。

艰难的拒绝 :

- 一种没有 `schema_version` 。 移民不是可选的。
- Allowing `null` 中,需要矩阵。 `null` 是一个刻录错误, 以数据形式伪装 。
- 使用普通文字的作家 `open(path, "w")`。 Atoron 只写; 部分文件会腐蚀真相的来源 。
- Storing tokens国家是用来调查与回购有关的事实的

拒绝规则 :

- 如果回购没有版本控制, 拒绝发送国家文件。 Atoron 写另加 git 维系生命的就是维系生命
- 如果项目没有至少一个验收命令来验证 `done` 转换, 拒绝 `status: done` 累积值。 添加 `done` 不接受检查是戏剧
- 如果项目打算在没有锁定战略的情况下共享各个流程的状态,则在运输前展示这一发现;原子重命名是必要的,但还不够。

产出结构:

```
<repo>/
├── agent_state.json
├── task_board.json
├── schemas/
│   ├── agent_state.schema.json
│   └── task_board.schema.json
└── tools/
    ├── state_manager.py
    └── migrate_state.py
```

结尾处指向“ 下一步要读什么” :

- 启动时给经理打电话的初始化脚本第35课
- 课程38 verification gate 读到状态 得分完成。
- 课程40 handoff 产生器消耗同样的计划。
