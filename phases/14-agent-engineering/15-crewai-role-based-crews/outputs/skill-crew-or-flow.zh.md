---
name: crew-or-flow
description: Pick CrewAI Crew or Flow for a given task, and scaffold the minimal implementation.
version: 1.0.0
phase: 14
lesson: 15
tags: [crewai, crews, flows, multi-agent, role-based]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


任务说明是,挑选(自主的)船员或流动人员(确定性),然后挑脚手架。

Decision:

1. 任务是否包含SLA、遵守或决定性的重播要求?
2. 任务探索性( 研究、 第一稿、 脑震荡) ? - > 船员 。
3. 4+专家 LLM集约?
4. 任务是否由3名专家按固定顺序进行?

船员须提供:

1. Agent 定义:作用、目标、背面(紧凑, 200字)、工具。
2. 任务定义:说明,预期_输出, agent.
3. 使用正确进程组( 顺序) | Hierarchical).
4. 测试 harness 运行组员的样本输入和检查_产出得到实现。

用于流动,生产:

1. `@start` 条目函数。
2. `@listen(topic)` 步骤组成 DAG 。
3. 明亮的事件主题; 没有神奇的广播 。
4. 重播 harness:如果有一个启动有效载荷,则可以确定地重新运行。

艰难的拒绝 :

- 船员没有后台,后台有载荷
- 流动没有明确的主题名称。“ 连锁” 违背了审计目的 。
- 由两名专家组成的等级制船员,经理的间接费用不赚钱。

拒绝规则 :

- 如果用户要求船员执行只执行命令的合规任务,则拒绝并迁移到流动。
- 如果用户要求流动,进行开放式研究,则拒绝流动,迁移到船员队伍。
- 如果背面超过200字,则拒绝并需要修改。 背景预算是有限的。

输出: `agents.py`, `tasks.py`, `crew.py` 或 `flow.py`,加上 `README.md` 以“下一步读什么”结尾,指向第24课(Langfuse/AgentiOps) observability或13课 如果流动需要耐久 恢复语义。
