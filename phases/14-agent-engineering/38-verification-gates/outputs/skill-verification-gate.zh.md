---
name: verification-gate
description: Generate a deterministic verification gate that combines scope, rule, and feedback artifacts into a single verification_report.json per task, plus CI wiring that refuses to merge without a green verdict.
version: 1.0.0
phase: 14
lesson: 38
tags: [verification, gate, deterministic, ci, override-log]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


根据项目的接受标准和现有的工作台工艺品, verification gate 并覆盖 audit log.

显示 :

1. `tools/verify_agent.py` exposing `verify(task_id, artifacts) -> VerdictReport`。纯函数,确定函数,无 LLM calls.
2. `outputs/verification/<task_id>.json` 成为了真相判决的唯一来源
3. `tools/override.py` 将签名的覆盖条目附加到 `outputs/verification/overrides.jsonl` (必须包括理由、用户代号、时间戳、查找代码)
4. 失败的 CI 工作流程 `passed: false` 并显示报告内嵌。
5. `docs/verification.md` 列出每张支票 其严重程度 其来源的文物 以及超标策略

艰难的拒绝 :

- 一张支票,它叫 LLM门是确定性管道; LLM 判决属于复审者
- 覆盖路径 agent 无需签名即可进入。 覆盖是人类独有的。
- 一份忽略了文物路径的核查报告。 报告必须可审计 。
- 块数发现工作流程可以静悄悄地降低级别。 块数在写时固定, 而不是在读取时固定 。

拒绝规则 :

- 如果工程没有接受指令, 拒绝将大门运到存在之前。 一个证明什么都没有的大门就是剧院 。
- 如果规则报告不存在,请拒绝跳过规则检查; 失败已关闭。
- 如果反馈日志不存在, 请拒绝跳过接受检查; 缺少日志本身是一个块 。
- 如果覆盖条目不是版本控制的, 请拒绝连接覆盖路径; 退出记录会击败大门 。

产出结构:

```
<repo>/
├── tools/
│   ├── verify_agent.py
│   └── override.py
├── outputs/verification/
│   ├── overrides.jsonl
│   └── <task_id>.json
├── docs/verification.md
└── .github/workflows/verify.yml
```

结尾处指向“ 下一步要读什么” :

- 课程39 reviewer agent 绿色判决后,它又开始上升
- 课程40 handoff 包括包里的判决
- 用来对着一个真实的样本应用程序 运行大门的41课
