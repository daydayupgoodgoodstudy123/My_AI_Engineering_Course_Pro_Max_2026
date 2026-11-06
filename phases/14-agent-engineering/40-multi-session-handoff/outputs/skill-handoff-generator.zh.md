---
name: handoff-generator
description: Generate end-of-session handoff packets from workbench artifacts, producing both human-readable Markdown and machine-readable JSON keyed to the seven canonical fields.
version: 1.0.0
phase: 14
lesson: 40
tags: [handoff, generator, session-end, packet, next-action]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


工作台(状态、判决、审查、反馈日志、 diff),制作会议结束 handoff 发电机被电线接入 agent runtime.

显示 :

1. `tools/generate_handoff.py` exposing `generate_handoff(snapshot) -> (markdown, payload)`.
2. `outputs/handoff/<session_id>/handoff.md` 和 `handoff.json`.
3. `handoff.schema.json` 覆盖七个所需字段和反馈尾板格式。
4. 会话结束钩脚本运行生成器, 如果缺少任何字段, 则拒绝关闭会话 。
5. `docs/handoff.md` 列出七个字段、其来源和修剪政策。

艰难的拒绝 :

- 一个 handoff 没有 `next_action`状态报告 handoffs 毒害下一场会话。
- 手写摘要的发电机。 agent工作就是离开工作台 进入可基因状态
- 一个 markdown 与 JSON. JSON 来源; markdown 是一个 JSON.
- 反馈尾部超过 30 个条目。 完整日志在版本控制中; 包必须保持小 。

拒绝规则 :

- 如果缺少核查报告, 拒绝生成此包 。 A handoff 没有判决是愿望
- 如果审查报告缺失,而预期有一位人审查员,则拒绝,首先要求审查通过。
- 如果 diff 摘要为空,但会话超过5分钟,在生成异常点之前就浮出水面;怀疑是结扎会话,而不是真正的无操作。

产出结构:

```
<repo>/
├── outputs/handoff/<session_id>/
│   ├── handoff.md
│   └── handoff.json
├── tools/generate_handoff.py
├── handoff.schema.json
└── docs/handoff.md
```

结尾处指向“ 下一步要读什么” :

- 课程41,端到端练习 在真实的样本应用程序。
- 将发电机包装到顶石工作台包里的42课
- 课程29(导出运行时间),用于将会话结尾线线连接成队列、事件和角点触发器。
