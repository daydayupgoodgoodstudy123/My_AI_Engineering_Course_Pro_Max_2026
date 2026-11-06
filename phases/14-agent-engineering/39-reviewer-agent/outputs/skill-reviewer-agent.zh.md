---
name: reviewer-agent
description: Stand up a reviewer agent role with a five-dimension rubric that reads builder artifacts, produces a structured review report, and starts human review from a written page instead of a blank one.
version: 1.0.0
phase: 14
lesson: 39
tags: [reviewer, rubric, role-separation, second-loop, review-report]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给建筑师 agent 已经制作了工作台的艺术品, 站起来的评审者 读取它们,并编写结构化的报告。

显示 :

1. `agents/reviewer.md` 与审评员 system prompt: 仅读取, 5个分位符号, 必须引用每个分数的工艺品路径 。
2. `tools/reviewer.py` 装入 `ReviewerInputs` 工作台的运行 LLM 每一维度计分器
3. `outputs/review/<task_id>.json` 和卡门式的审查报告路径一样
4. `docs/reviewer-rubric.md` 列出五个维度,每个回答的问题, 0 - 1 - 2 标记描述。
5. CI在建筑工任务结束时,将审查报告作为公关评论。

艰难的拒绝 :

- 具有 diff 写入权限的审查器。 构建者和审查者之间的鸿沟是整个信号; 崩溃会破坏可靠性 。
- 标记没有锚说明 每分。 "从0到2的",没有锚崩溃到感觉。
- 检查遗漏引用的报告。 每个得分必须指向文件或 trace entry.
- 分享建筑师的 system prompt。同一模型是好的;相同的 prompt 不是.

拒绝规则 :

- 如果建筑商没有提出核查报告,则拒绝运行审查员。 在需要做出判断之前,必须坚持接受。
- 如果项目完成的任务少于3项,则拒绝要求标注校准。 calibration set.
- 如果要求审查者分数低于最低的可信度,则拒绝并暴露人类不确定的维度。

产出结构:

```
<repo>/
├── agents/reviewer.md
├── tools/reviewer.py
├── outputs/review/
│   └── <task_id>.json
├── docs/reviewer-rubric.md
└── .github/workflows/review.yml
```

结尾处指向“ 下一步要读什么” :

- 课程40 handoff 将核查和审查合并的包。
- 真正的任务第41课 结束建筑/审查师分离
- 5课(自备和 CRITIC单人agent 自我审查基线,这一课程在改进。
