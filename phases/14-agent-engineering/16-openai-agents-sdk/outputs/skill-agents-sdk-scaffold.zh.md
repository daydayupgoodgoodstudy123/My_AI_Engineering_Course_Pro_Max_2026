---
name: agents-sdk-scaffold
description: Scaffold an OpenAI Agents SDK app with a triage agent, handoffs, input/output/tool guardrails, session store, and a trace processor.
version: 1.0.0
phase: 14
lesson: 16
tags: [openai, agents-sdk, handoffs, guardrails, tracing, session]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给出产品领域和专家名单 agents,脚架 OpenAI Agents SDK app.

显示 :

1. `Agent` 每个专家加1人 `triage` agent 只不过 handoffs (无域工具) 。
2. `FunctionTool` 每个域工具, 并输入输入图案、 清晰描述( 说明模型何时使用) 和执行 sandbox.
3. `Handoff` 从分级到每个专家。 验证工具名称 `transfer_to_<agent>` convention.
4. `InputGuardrail` 默认为平行模式,除非 guardrail LLM 相对于主要模式而言,是很大的——然后使用阻塞。
5. `OutputGuardrail` 总是阻断安全关键输出的标注。
6. Per-tool guardrails 中,可以触摸网络或文件系统的功能工具。
7. `Session` 存储( SQLite 默认值; 用于 prod 的 Rediis) 。
8. `add_trace_processor` 线条横绕到后端 OpenAI的 trace UI.

艰难的拒绝 :

- Triage agents 带有域工具。 Trigage handoffs 仅此;混合会淡化路由器的决定。
- Guardrails 使输入/输出发生变异 Guardrails 批准或拒绝——它们不改写。
- Silent handoff 循环。 需要跳反转( 默认为 3) 。

拒绝规则 :

- 如果用户想要"不" guardrails拒绝任何能影响付费用户或PII的产品。
- 如果产品只有两名专家,建议通过 `Agents` 使用直接分类器(课程12),而不是分级+handoffs 减少 token 成本.
- 如果在测试中禁用追踪, 拒绝发送。 多步失败是不可调试的 。 traces.

输出: `agents.py`, `tools.py`, `guardrails.py`, `app.py`, `README.md` 和分层...agent rationale, guardrail modes, trace 处理器和会话后端。 结尾处为“ 下一步读什么” , 指向课程 23 (OTel GenAI), 课 24 (OTel GenAI)observability 后端),或课程17 Claude Agent SDK translation.
