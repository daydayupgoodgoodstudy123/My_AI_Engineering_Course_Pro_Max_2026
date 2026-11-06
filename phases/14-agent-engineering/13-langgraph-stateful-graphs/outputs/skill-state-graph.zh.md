---
name: state-graph
description: Build a LangGraph-shaped state machine with typed state, conditional edges, per-node checkpointing, and durable resume.
version: 1.0.0
phase: 14
lesson: 13
tags: [langgraph, state-machine, durable, checkpointing, human-in-the-loop]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


目标运行时间、状态形状、一组节点功能和检查站后端,都会产生一个状态 agent graph.

显示 :

1. 输入 `State` 记录每个字段。 节点读取状态; 它们返回更新 。
2. 一个 `StateGraph` 与 `add_node`, `add_edge`, `add_conditional_edges`, `set_entry`,加上 `START`/`END` sentinels.
3. 一个 `Checkpointer` 接口 `save(session_id, node, state)` 和 `load_latest(session_id)`。默认为 SQLite;允许 Postgres/Redis/custom。
4. 一个 `Runner` 以连续顺序排列每个节点的状态, `PausedAtNode` 用于 human-in-the-loop,并提供支持 `resume_from` 带有可选 `state_override`.
5. 三名地形学助手:主管(中央路由器), swarm (shared-tool handoffs),等级(专栏)。

艰难的拒绝 :

- 没有明确随机种子或墙上时钟捕捉的非确定性节点。 恢复假设节点输出为可复制的输入状态 。
- 只能保存“ 简洁” 状态的检查站。 将状态序列化或恢复中断 。
- 每个边缘都有条件的图形。 更适合有偶发线性链条 branches.

拒绝规则 :

- 如果用户要求使用状态图而不持续, 请拒绝。 整个点是可持久的恢复; 如果您不需要恢复, 请在课程12中使用工作流程模式 。
- 如果用户要求 "checkpoint 失败也需要状态——那就是调试开始的地方。
- 如果图形的节点超过~ 30, 则拒绝平面版式, 需要嵌套子图。 平面 30 节的图表不可重审 。

输出: `state.py`, `graph.py`, `checkpointer.py`, `runner.py`, `README.md` 解释国家模式、 检查员选择, 并恢复语义。 结尾处指向 14 课 14 actor- 模特替代课程,16课 handoffs/guardrails 平面图,或OTel 的23课横跨图形步骤。
