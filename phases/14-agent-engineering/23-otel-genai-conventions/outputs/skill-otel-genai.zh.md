---
name: otel-genai
description: Instrument an agent with OpenTelemetry GenAI semantic conventions — invoke_agent, chat, tool_call spans with correct attributes and opt-in content capture.
version: 1.0.0
phase: 14
lesson: 23
tags: [opentelemetry, genai, observability, tracing, semantic-conventions]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 agent 运行时间,有线OTel GENAI语义学会议。

显示 :

1. `invoke_agent` 间隔 agent 运行。 远程的客户端 agent 服务, 内部处理。 Name: emplement `invoke_agent {gen_ai.agent.name}`.
2. `chat` 间隔 LLM 调用 `gen_ai.operation.name=chat`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`.
3. `tool_call` 每个工具调用的横线 `gen_ai.tool.name` 并酌情, `gen_ai.data_source.id` (RAG 文体/内存存储)
4. 选择内容捕获:默认的 OFF;当 On 将输入/产出储存到外部并记录 `*.reference_id` 双肩上
5. 内容传播:使用 W3C trace 上下文标题, 使多进程运行 (D)Claude Agent SDK CLI 子进程) 缝入一个 trace.

艰难的拒绝 :

- 获取完整 prompts默认情况下,PII和秘密渗漏风险;也违反了规格。
- Missing `gen_ai.provider.name`。多供应商仪表板断开。
- 孤儿的工具横跨。 总是通过活动环境来建立父母与子女的关系 。

拒绝规则 :

- 如果运行时间不能跨越进程边界传播上下文, 请拒绝。 多进程 trace 缝针是用来 Claude Agent SDK + 国家牵头单位用户。
- 如果产品受到监管限制(HIPAA、GDPR),则拒绝内含内容捕获。
- 如果后端未设置 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`,警告:收藏家升级时,属性名称可能会改变。

输出: `tracer.py`, `attributes.py`, `content_store.py`, `README.md` 解释横跨结构、 稳定性选择使用和内容获取政策。 结尾处为“ 下一步读什么” , 指向 24 课( 后端: 朗富斯、 凤凰城、 Opik) 或 17 课 Claude Agent SDK trace- 通俗的传播
