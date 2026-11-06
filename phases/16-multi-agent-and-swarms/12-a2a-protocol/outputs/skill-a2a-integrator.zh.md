---
name: a2a-integrator
description: Design an A2A integration between two agents — Agent Card, task schemas, auth, streaming or polling.
version: 1.0.0
phase: 16
lesson: 12
tags: [multi-agent, a2a, protocol, interoperability, google]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给两个 agent 需要相互协作、产生 A2A 融合计划: Agent 牌内的东西,任务图案,认证,运输模式。

显示 :

1. **Agent Card.** 名称、版本、技能、终点、支持 modalities (文字、结构、图像、音频、视频),协议_版本, 认证声明 。
2. **任务计划每个技能。** 输入 JSON 系统图+工艺品 JSON 明确,客户会验证
3. **选择了** Bearer token 或签名的请求。 threat model 包括:
4. **运输模式。** 投票对 SSE streaming 和Webhook回调。 Streaming 长期或累进任务; 短期任务的投票。
5. **Rate limits.** 客户和任务限制,防止虐待
6. **Idempotency.** 重复战略 `POST /tasks` 请求( 客户端任务键、 服务器端重复) 。
7. **处理失败 。** 任务说明 `failed` 致命的,致命的, 错误的手工艺图案。
8. **MCP 与 A2A split.** 如果远程 agent 使用 MCP 内部,注意哪些工具被暴露或保存在内部。

艰难的拒绝 :

- Agent 没有声明协议版本的卡片 。
- 当使用情况需要结构时, 任务模式是自由格式文本 。
- 公用互联网部署时没有使用过Auth。

拒绝规则 :

- 如果两者 agents 在同一过程中运行, 拒绝 A2A 并建议直接 PythonJS电话 A2A 用于跨系统边界。
- 如果潜伏要求为100米以下的往返,则拒绝 A2A 并建议直接的RPC 与共同的策略。
- 如果远程 agent 不声明 Agent 牌,拒绝整合,建议先出版一张。

输出: 一页集成简报。 关闭于 Agent Card JSON 粘贴在内部,让工程人员把它扔进 `/.well-known/agent.json`.
