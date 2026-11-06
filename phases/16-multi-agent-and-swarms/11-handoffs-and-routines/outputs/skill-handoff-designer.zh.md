---
name: handoff-designer
description: Design a handoff topology for a Swarm/Agents-SDK-style system: which agents exist, which handoffs they can call, what context transfers.
version: 1.0.0
phase: 16
lesson: 11
tags: [multi-agent, swarm, handoff, openai-agents-sdk]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于用户需要完成的任务(通常分为三类或基于技能的路线),产生 handoff 地貌图已准备好 OpenAI Swarm 或该 OpenAI Agents SDK.

显示 :

1. **Agent roster.** 每个 agent:名称、一罪状目的、工具、其他哪些 agents 它可以手牵手。
2. **Handoff functions.** 工具签名 agent. 每个 handoff 函数返回目标 Agent.
3. **环境转移政策。** 在每个 handoff 边缘: 完整历史、 最后N条信息或摘要快照。 理由说明 。
4. **Guardrails.** 输入验证 agent (what prompts 允许触发 handoffs 向敏感专家提供), handoff 必要时
5. **循环检测** 检测乒乓的规则(例如,“A向B发牌;B向A发牌”一次以上)。
6. **后退行为。** 如果为 handoff 目标丢失( 已移动) agent, 验证失败) agent 处理会话。
7. **会话/记忆计划。** 是否使用 Agents SDK 会话,呼叫者管理的内存,或完全没有内存。

艰难的拒绝 :

- 任意 handoff 设计时没有环形探测
- Handoff 函数,将完整历史传递给拥有不同工具权限(安全风险)的专家。
- 假设的设计 Swarm无国籍行为,但需要多转体记忆——使用 Agents SDK 倒不如说是上课

拒绝规则 :

- 如果任务需要平行执行, 请拒绝 Swarm 推荐主管(Lesson 05)代替。
- 如果任务需要决定性的审计/重播,拒绝和建议 LangGraph 静态图。
- 如果任务只是一个简单的阶段的DAG(研究编号 __审查),建议 CrewAI 顺序代替。

产出:一页 handoff 简短。 结束于关于如何 prompt injection 可能会引发不必要的 handoffs 和什么,你说什么? guardrails 挡住它
