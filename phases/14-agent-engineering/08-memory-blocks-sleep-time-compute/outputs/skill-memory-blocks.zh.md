---
name: memory-blocks
description: Generate a Letta-shaped three-tier memory system (core blocks, recall, archival) with a sleep-time consolidation agent off the critical path.
version: 1.0.0
phase: 14
lesson: 08
tags: [memory, letta, blocks, sleep-time, consolidation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于目标运行时间、主要模型和(可能更强的)睡眠时间模型,产生了一个三层内存系统,其中明确有块型和合成。

显示 :

1. `Block` 类型 `label`, `value`, `limit`, `description`, `version`, `history`。每个写缓冲版本并记录旧值。 `near_limit(threshold=0.8)`.
2. 一个 `BlockStore` 至少有三个默认区块: `human` (关于用户的事实) `persona` (agent ),以及 `task` 允许用户定义的区块 。
3. 一个 `Recall` 存储 - 转动会话的日志。 自动写下每个转弯。 尾部会被删除, 但仍然可以检索 。
4. 一个 `Archival` 存储 - 至少两个后端( Vctor, KV) 。 插入返回记录id。 无效, 而不是在矛盾时删除 。
5. 一个 `PrimaryAgent` 手柄转弯,只发布原始文字。在关键路径上没有总结。
6. 一个 `SleepTimeAgent` 横跨两圈的: 总结超过阈值的区块, 无效的归档记录, 写入 `learned_context` 进入共享的街区。

艰难的拒绝 :

- 任何在用户定位转弯时同步运行的内存操作, 除了直接查看。 总结、 合并、 无效属于睡眠时间通行证 。
- 以矛盾方式删除归档记录。 无效, 历史仍然可以审计 。
- 写入人或安全块时不使用审查步骤。 这些块将塑造全球的行为; 静默地写下掩码错误 。

拒绝规则 :

- 如果运行时间不能持续横跨会话, 拒绝运送被称为“ 模拟” 的产品。 降低要求 。
- 如果睡眠时间 agent 没有 trace 输出, 拒绝。 静态合并是一个解调死区 。
- 如果用户要求“不取消, 总是信任最新的写作”,

输出: 每个组件有一个文件加 a `README.md` ,并命名默认的区块、睡眠时间节奏和矛盾解析策略。结尾处指向“下一个读什么”如果 agent 需要图形推理 相对于内存, 或者课程23 如果产品需要 OTel 覆盖的内存操作。
