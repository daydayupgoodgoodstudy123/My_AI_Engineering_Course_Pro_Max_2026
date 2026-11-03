---
name: otel-genai-instrumentation
description: Produce an instrumentation plan for an agent codebase to emit OTel GenAI spans end-to-end.
version: 1.0.0
phase: 13
lesson: 19
tags: [otel, observability, gen-ai, tracing]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 agent 代码基 (C)LLM 电话,工具调度 MCP 客户端, 子agents),制作OTel GenAI仪器计划。

显示 :

1. 斯潘等级。 根 `agent.invoke_agent` (国内)和儿童: `llm.chat` (CLIENT), `tool.execute` (INTERNAL), `mcp.call` (CLIENT), `subagent.invoke` (INTERNAL).
2. 每个横幅属性检查 。 `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.*`, `gen_ai.tool.name`, `gen_ai.agent.name`.
3. 传承规则。 在每个远程呼叫中输入 W3C 跟踪; for MCP 标准使用 `_meta.traceparent` 是一个临时领域。
4. 内容捕获策略。 默认关闭; 允许使用文档的 env var; 名称为 PII 风险 。
5. 出口者选择。 Jaeger/Tempo/Langfuse/Phoenix/Datadog/Honecomb; OTLP作为电线。

艰难的拒绝 :
- 计划缺失 trace 传播到 MCP 或子-agent boundaries.
- 默认获取内容的任何计划。 prompts 和PII。
- 任何计划,如果没有 `gen_ai.` 或明确的供应商前缀。

拒绝规则 :
- 如果代码库使用内置 OTel 自动仪器的框架( Pydantic AI, ) LangGraph,代理Ops),建议框架钩先。
- 如果出口商的后端在预科阶段,而团队没有SRE支持,建议一个管理好的后端。
- 如果用户要求获取调试测试的内容, 则在未输入同意政策和 PII 编辑管道的情况下拒绝 。

输出:一页计划,包括等级、每行属性核对表、传播规则、内容捕获政策和出口商选择。 `gen_ai.client.operation.duration`).
