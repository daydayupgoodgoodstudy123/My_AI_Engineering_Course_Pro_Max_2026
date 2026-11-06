---
name: structured-output-picker
description: Choose a structured output approach, schema design, and validation plan.
version: 1.0.0
phase: 5
lesson: 20
tags: [nlp, llm, structured-output]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个用例（提供商、延迟预算、模式复杂性、容错能力），输出：

1. 机制。本机供应商 structured output、讲师重试、Outlines FSM 或 XGrammar CFG。一句话理由。
2. 架构设计。字段顺序（首先推理，最后回答）、“未知”的可为空字段、枚举与正则表达式、必填字段。
3. 失败策略。最大重试次数、后备模型、优雅的 `null` 处理、分配外拒绝。
4. 验证计划。模式符合率（目标100%）、语义有效性（LLM-判断）、字段覆盖率、延迟p50/p99。

拒绝任何将 `answer` 或 `decision` 放在推理字段之前的设计。拒绝使用没有 schema 的裸 JSON 模式。在仅 FSM 库后面标记递归模式。
