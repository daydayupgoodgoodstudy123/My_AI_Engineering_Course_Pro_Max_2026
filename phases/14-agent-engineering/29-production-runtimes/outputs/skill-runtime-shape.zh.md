---
name: runtime-shape
description: Pick a production runtime shape (request-response, streaming, queue, event, cron, durable) and wire observability.
version: 1.0.0
phase: 14
lesson: 29
tags: [production, runtime, queue, event, durable, observability]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给任务类别( 预想时间、 步数、 触发类型、 潜伏预算) 选择运行时间形状 。

Decision:

1. < 30s, 用户等待 - > **request-response**.
2. 进步的 UX 或声音 - > **streaming**.
3. 分钟到小时,用户不等待 - > **queue-based**.
4. 对外部事件的反应 - > **event-driven**.
5. 定期家务 -- > **cron**.
6. 以上任何费用高的恢复营业费用 - > 添加 **durable execution**.

显示 :

1. 堆叠中的脚架
2. Observability: OTel GenAI 横线( 列松 23), 后端有线( 列松 24) 。
3. 队列: DLQ + 重试策略 + 队列深度度量。
4. 用于事件: 明确订阅者注册 + 重播路径 。
5. 对于 cron: 锁定文件或分布式锁定以防止重复运行 。
6. 耐久性:检查员后端+恢复语义。

艰难的拒绝 :

- Synchronous HTTP 5分钟的任务。用户挂断;工人堆积起来。
- 以队列为基础, 没有 DLQ 。 失败的工作会消失 。
- 背景工作无 trace 导出。 用户未投诉, 失败将隐性 。
- "没有持久的状态,我们只是再试一次。" checkpoint.

拒绝规则 :

- 如果产品有SLA+重播要求,则拒绝 swarm 地形学+不可耐久运行时间。
- 如果任务有合规性,则由垃圾事件驱动,没有审计线索。
- 如果用户想要 cron + no lock, 拒绝。 重叠 cron 运行最多只能重复工作, 最坏的是数据腐败 。

输出:运行时脚手架+ observability 勾勾 + README 与 SLA, 重新尝试政策, 检查器选择。 结尾处指向课程23 (OTel), 课24 ()observability),或课程17(管理 Agents 由长期托管的。
