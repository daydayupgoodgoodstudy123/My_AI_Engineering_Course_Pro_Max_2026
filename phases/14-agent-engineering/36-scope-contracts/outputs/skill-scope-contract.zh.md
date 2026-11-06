---
name: scope-contract
description: Generate per-task scope contracts with allowed/forbidden globs, acceptance criteria, and rollback plan, plus a CI-ready glob-aware checker that runs on every agent diff.
version: 1.0.0
phase: 14
lesson: 36
tags: [scope, contract, globs, diff-check, ci]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给任务描述和回购布局, scope contract 和一张大字眼的支票

显示 :

1. `scope_contract.json` 用于执行字段的任务: `task_id`, `goal`, `allowed_files` (globs), `forbidden_files` (globs), `acceptance_criteria`, `rollback_plan`, `approvals_required`.
2. `tools/scope_check.py` 返回一个 `ScopeReport` 加上任何违规事件的非零出口
3. CI 级(`.github/workflows/scope-check.yml` 或等效的),该检查器在合并 diff 上运行。
4. `outputs/scope/closed/<task_id>.json` 档案协议,所以船与变化历史有合同。

艰难的拒绝 :

- 合同没有 `forbidden_files`负空间是合同的一部分。
- 用于列出原始路径而非代码目录的粗路的合同。 反因在一夜之间使原始路径无效 。
- 一个 `rollback_plan` 字段中显示空或“见运算本”。
- 批准权被列为“个案”。批准权的界限必须包含众多。

拒绝规则 :

- 如果任务描述不限制回购区域, 请拒绝作者 `allowed_files` 仅从描述中找到。 询问任务所在目录 。
- 如果回购没有测试命令, 拒绝添加 `acceptance_criteria` 直至提供或粘结。合同不能核实是愿望。
- 如果 agent 运行时间无法遵守批准边界( no) human-in-the-loop)在运输前就已出现空白;范围逐渐渗入到批准要求的行动中,将是主要的失败。

产出结构:

```
<repo>/
├── scope_contract.json
├── outputs/scope/closed/
│   └── T-XXX.json
├── tools/
│   └── scope_check.py
└── .github/
    └── workflows/
        └── scope-check.yml
```

结尾处指向“ 下一步要读什么” :

- 连接命令的运行时反馈课程37 与合同连接。
- 课程38 verification gate 需要用到范围报告
- 课程39 reviewer agent 审计了关闭的合同档案
