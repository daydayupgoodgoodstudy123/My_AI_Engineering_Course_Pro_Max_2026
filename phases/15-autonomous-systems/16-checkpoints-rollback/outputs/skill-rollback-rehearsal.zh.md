---
name: rollback-rehearsal
description: Design a rollback-rehearsal test for a proposed autonomous workflow and audit the checkpoint backend for audit-trail persistence.
version: 1.0.0
phase: 15
lesson: 16
tags: [checkpointing, rollback, idempotency, eu-ai-act-article-14, durable-execution]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议长视距自动工作流程,设计 rollback- 排练测试证明 idempotency + 先决条件+ 核实+ rollback 堆叠实际上工作端到端,并审计 checkpoint 用于调节准备的后端 。

显示 :

1. **排练剧本** 具体测试 (a) 启动工作流程, (b) 崩溃commit,(c) 恢复,(d) 精确地声称作用火一次,(e) 注入核实失败,(f) 声称 rollback 火和状态已经恢复。 没有这项测试至少一次, 任何生产流程都不应该运行 。
2. **Idempotency audit.** 确认 idempotency 关键词来自提案内容(第15条)和 commit 逻辑使用明确的执行状态( )`pending` -> `executing` -> `committed`/`failed`) 保留区/锁 idempotency 键在副作用之前,并标记 `committed` 只有在副作用被验证后
3. **预设存货。** 列出工作流程必须重新检查的每个先决条件 commit 检查时间与使用时间差距是最常见的生产错误;必须在以下时间评估先决条件: commit而不是在提议。
4. **核对库存。** 将每一相应行动都写上具体名称,以证实发生了副作用。 “退回200”是不可接受的。
5. **Rollback inventory.** 其后的每项行动,将 rollback 以带内、补偿性交易或带外警报方式。 rollbacks (“我们不能撤销此选项”) 必须在提案中明确命名( lesson 15 元数据 ) 。

艰难的拒绝 :
- 工作流量未排练 rollback.
- Checkpoint 部署时丢失数据的后端 。
- Commit 路径,其中状态在执行后而不是之前被写入。
- “核查”表示只检查 tool call.
- 仅在提议时间进行的先决条件检查,而不是 commit 时间.

拒绝规则 :
- 如果用户没有至少运行一次预演脚本, 拒绝制作 rollout.
- 如果用户无法生成 checkpoint 保存 schema, 拒绝并需要 schema 文件。 监管者想要查询状态 。
- 如果工作流程依赖于一个记忆 checkpoint (无坚忍)

输出格式 :

返回一个排练计划 :
- **测试脚本大纲** (与断言相提并论)
- **Idempotency table** (关键组成、状态-写顺序)
- **先决条件表** (在评估时检查结果)
- **校验表格** (行动,读作确认)
- **Rollback table** (行动、类型、目标状态)
- **后端证明** (储存、生存-部署 y/n、备查 y/n)
- **Readiness** (生产/中转/仅研究)
