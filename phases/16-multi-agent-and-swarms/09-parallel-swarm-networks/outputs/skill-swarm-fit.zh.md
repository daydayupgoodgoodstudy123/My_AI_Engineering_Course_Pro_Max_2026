---
name: swarm-fit
description: Decide whether a task fits a swarm (decentralized) architecture or a supervisor (centralized) one.
version: 1.0.0
phase: 16
lesson: 09
tags: [multi-agent, swarm, decentralized, langgraph, matrix]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于任务及其产出/确定性要求,建议 swarm 或上下文,并列出特定的队列和 guardrail choices.

显示 :

1. **任务独立检查 。** 子任务是独立的还是相互依存的? Swarm 只有在高度独立时才合适。
2. **会期分配。** 制服变数 Swarm 多数是在不同时期的工作量上获胜。
3. **订购要求。** 严格,放松,或没有。 Swarm 无法维持秩序; 主管有。
4. **调试性需要。** 高级(财务、医疗) 主管。 swarm 使用每个任务 trace IDs.
5. **排队选择** 模拟( )`queue.Queue`用于演示; Kafka / Redis 流/ NATS / 耐久 DB 支持的生产。
6. **工人设计要求。** 必须具备一定的天份; 必须发布每个任务 trace;必须处理后压。
7. **反饥饿计划** 优先老龄、工人专业化、排队
8. **Observability plan.** 每个任务编号, 开始/结束事件, 结果池计划 。

艰难的拒绝 :

- Swarm 要求严格订购的任务的建议。
- Swarm 没有一个能干的工人
- Swarm 生产中没有耐久的排队。

拒绝规则 :

- 如果任务每秒少于10个独立单位,则拒绝 swarm 推荐上司 Swarm 间接费用的利用量低是没有道理的。
- 如果 observability 需要统一一致的要求 trace (审计、合规),拒绝 swarm 和建议 LangGraph 而不是确定性图。

输出: 一份一页的建筑简况。 打开时要做出合适的判断, 结束对目标输送量的具体信息代理建议 。
