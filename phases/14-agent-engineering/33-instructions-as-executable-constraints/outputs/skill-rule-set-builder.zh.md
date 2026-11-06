---
name: rule-set-builder
description: Interview a project owner, classify their existing prose instructions into five operational categories, and emit a versioned agent-rules.md plus a Python checker stub.
version: 1.0.0
phase: 14
lesson: 33
tags: [rules, instructions, constraints, checker, workbench]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


发出回执和任何现有的书信指示(第2条)`AGENTS.md`, `CONTRIBUTING.md`,在文件上),产生一个五类规则,设定工作台可以执行。

这五个类别:

1. `startup` 工作开始前必须真实的是什么?
2. `forbidden` 永远不能发生的事
3. `definition_of_done` 证明任务已经完成的是什么?
4. `uncertainty` - 什麽 agent 不确定时会
5. `approval` - 需要人类的签字

显示 :

1. `docs/agent-rules.md` 以一个 `##` 每一规则都包含 `category`, `check`,以及一行描述。
2. `tools/rule_checker.py` 以 a 为单位 `RuleChecker` 类别显示一种方法 `check`。每种方法都采用 `TurnTrace` 数据分类和返回 `bool`.
3. `tools/rule_report.py` 运行一个自动检查器 trace, 发出 `rule_report.json`.
4. 迁移记录:哪条流言成为了哪条规则, 被删除为渴望,为什么。

艰难的拒绝 :

- 无规则 `check` 字段。只有期望的规则属于入职文件,而不是工作台规则集。
- 单一的“ 注意” 规则。 请指定一个类别, 检查或删除它 。
- 需要检查 LLM 规则检查必须确定性且便宜,这样他们就能跑遍每个转弯
- 规则文件超过200行。 按类别拆分到 `agent-rules.{startup,forbidden,done,uncertainty,approval}.md` 和母指数的路径。

拒绝规则 :

- 如果 agent 产品不能提供a `TurnTrace` (无仪器),至少拒绝为检查器安装电线 `read_state_file`, `edited_files`, 和 `tests_exit_code` 记录。
- 如果现有的指令大多是渴望( > 50%), 请在发布规则之前先显示发现值。 规则集看起来会很薄; 正确 。
- 如果因过去发生的一起事件而增加一条规则,应附上事故的ID,以便今后的审查能够确定是否仍然需要。

产出结构:

```
<repo>/
├── docs/
│   └── agent-rules.md
├── tools/
│   ├── rule_checker.py
│   └── rule_report.py
└── docs/migration-notes.md
```

结尾处指向“ 下一步要读什么” :

- 课程36,每个任务 scope contracts 从而扩大了禁忌的范围。
- 38课 verification gates 使用规则报告。
- 课程39 reviewer agent 得分规则的遵守。
