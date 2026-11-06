---
name: memory-auditor
description: Audit a multi-agent system's shared-memory design for provenance, versioning, verifier separation, and projection schema. Flag memory-poisoning exposure before production.
version: 1.0.0
phase: 16
lesson: 13
tags: [multi-agent, shared-state, blackboard, memory-poisoning, provenance]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


假设一个多...agent 代码库或建筑文档,审计共享的模拟设计和标记内存中毒。

显示 :

1. **Topology.** 完整信息库,主题分割黑板,每 -agent 视图, 还是混合? 名称数据结构( 列表、 dict、 pandas 框架、 矢量存储、 SQL 将作家和读者的粗略上层线以稳定状态计数。
2. **验证场** 每一篇记录上都写着: 写作id, 时间戳, prompt 散列或 prompt 文本,工具呼叫 trace,源 URI 或工具名。列出当前字段和缺失的字段。
3. **更新模型。** 日志是只附着的, 还是作家变异了? 如果突变了, 什么是货币控制机制(锁、乐观的版本, 没有任何)? 更正应该是超版条目, 而不是在位编辑 — — 标出任何不这样做的设计 。
4. **验证分离。** 是否有只读的 agent 能够独立访问源码吗? 它能写到主池(它不应该)吗? 它的输出去向何方?
5. **预测计划** 如果设计使用预测(LangGraph 如何记录新模式? agents 宣布他们所消费的预测?
6. **中毒风险得分** 每个轴的分数 1-5 : [来源完整性], [突变后的超分数], [核查员独立性], [预测方案清晰度]。一个在任何轴上分数低于3的系统被标出。

艰难的拒绝 :

- 任何审计只要没有标明缺少的核查者,独立源码访问的不可写核查者就是负载减量;其他每次减量都没有装饰。
- 推荐"添加更多检测"的审计。测试不会发现内存中毒,因为中毒会产生可信的结果,通过检测。
- 审计建议将内容作为唯一的来源。 *what* 被写,不是 *who* 或 *从哪*.

拒绝规则 :

- 如果代码库隐藏外部服务(Redi、Postgres、矢量DB)中的共享状态,且没有检查工具,则说明若无生产读取功能,审计就无法完成。
- 如果系统少于3个 agents注意内存中毒风险较低,但来源仍然是廉价的保险。
- 如果系统使用一个内设国家管理的框架(LangGraph 检查员,AutoGen 池,审计框架的担保,而不是重新交付。

输出: 一份两页的报告。 从一个一句话摘要开始 (“ 共享状态是完整的信息集合, 没有源代码和验证器 —— 高中毒风险 ” ) , 然后上面的六个部分。 最后有一个优先行动列表 : 三个更改, 每个标签 [critical] [应当] 或 [nice-to-have],估计执行时间。
