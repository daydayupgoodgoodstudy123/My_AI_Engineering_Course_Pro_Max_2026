---
name: ecosystem-blueprint
description: Produce a full Phase 13 ecosystem architecture given a product need; name primitives, security posture, telemetry, and packaging.
version: "1.0.0"
phase: "13"
lesson: "23"
tags: [mcp, capstone, ecosystem, architecture, a2a, otel]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


需要产品(研究、总结、自动化、 agent- 驱动工作流程,产生完整的结构。

显示 :

1. MCP 定义 `server/discover`,每个请求的协议元数据、工具、资源, prompts,并列出缓存策略。 `ui://` Apps.
2. 扩展。 如果工作不同步, 请声明 `io.modelcontextprotocol/tasks` 设计 `tasks/get`, `tasks/update`, 和 `tasks/cancel`。保持初始控点 `resultType: task`,使投票结果 `resultType: complete`,并且不使用 `tasks/result` 或 `tasks/list`.
3. 安全姿势 OAuth 2.1 范围组,RBAC矩阵网关,按散列货单,两条审计规则。
4. A2A 确定任何子项目agent 电话。 Agent Cards.
5. 遥测,OTel GenAI跨越等级,输出和后端选择。
6. Packaging. AGENTS.md, SKILL.md, 和部署表面(Docker 作曲, K8s) 。
7. 绘制第13阶段的课目。 traces 继续说

艰难的拒绝 :
- 任何将不信任的投入、敏感数据以及相应行动合并在一起的架构(《二规则》)。
- 任何没有 trace 传播到 MCP 和 A2A hops.
- 任何建筑,如果没有至少一个后退提供者 LLM layer.
- 任何当前 MCP 取决于 `initialize`, `Mcp-Session-Id`, `tasks/result`, 或 `tasks/list`.

拒绝规则 :
- 如果直接满足产品需求 LLM 拒绝将整个生态系统划为脚架
- 如果该小组缺乏门户的业务能力,建议一个管理良好的网关,并记录信托转移。
- 如果结构涉及付款,则需要单独审查付款授权协议和明确签字。

产出:一页蓝图,原始人,安全态势 A2A 跳、 遥测计划、 包装和课程地图。 最后一句话要确定部署最困难的操作风险 。
