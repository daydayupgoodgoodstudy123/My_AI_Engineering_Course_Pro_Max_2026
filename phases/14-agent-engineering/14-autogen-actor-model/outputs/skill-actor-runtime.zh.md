---
name: actor-runtime
description: Build an AutoGen v0.4-shaped actor runtime with private state, inbox-per-actor, message-only IPC, fault isolation, and a dead-letter queue.
version: 1.0.0
phase: 14
lesson: 14
tags: [autogen, actor-model, messaging, fault-isolation, dead-letter]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


假设一个多...agent 任务, 产生 actor 运行时间和 agent actors needed.

显示 :

1. 一个 `Message` 类型 `sender`, `recipient`, `topic`, `body`, `mid`.
2. 一个 `Actor` 基类 `receive(message, runtime)`. Actor 州是私人的。
3. 一个 `Runtime` 并排一个队 `send()`, `run_until_idle()`,并排成一个死字队列。处理者中的例外会转到 DLQ;不传播。
4. 一名地形学助手:圆形罗宾(固定旋转),选择者(LLM 或自定义广播。
5. Observability 以每封信的钩子显示: 释放 OTel 横贯 `gen_ai.agent.name` 和 `gen_ai.operation.name` 23课

艰难的拒绝 :

- 传递该发送器的同步信息将发送器阻断,直到接收器返回。 这是 v0. 2 模式; 它打破了断层隔离 。
- 横贯共享变异状态 actors. Actors 是否通过信件读取状态 。
- 传播处理者例外的运行时间。 失败属于 DLQ; 允许其它 actors 继续跑

拒绝规则 :

- 如果任务只有两个 actors 背部和背部固定,拒绝 actor 提出 prompt 链( Lesson 12) 。 Actors 3级时的挣钱 actors 或自动货币。
- 如果用户想要“ 更容易调试” 的同步模式, 拒绝。 建议记录 + 追踪 (Lesson 23) 。
- 如果域名严格是单一专家的要求/答复,建议使用路径(Lesson 12)而不是 actor team.

输出: `message.py`, `actor.py`, `runtime.py`, `teams.py`, `README.md` 解释 DLQ 政策、 地形选择以及 OTel 的宽度。 结尾处用“ 阅读下一步” 表示 25 (多agent 辩论) actors 谈判,如果需要追查,课程23(OTel),或微软 Agent 框架,如果你想 前瞻性的运行时间。
