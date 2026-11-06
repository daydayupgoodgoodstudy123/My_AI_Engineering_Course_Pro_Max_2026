---
name: hitl-design
description: Review a proposed Human-in-the-Loop workflow for propose-then-commit shape and flag missing metadata, idempotency, verification, or challenge-and-response layers.
version: 1.0.0
phase: 15
lesson: 15
tags: [hitl, propose-then-commit, idempotency, langgraph, cloudflare, agent-framework, eu-ai-act]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议的高级信息技术处工作流程,根据当时的提议审计 --commit 参考和标出缺失、未详细说明或监管者不相容的内容。

显示 :

1. **提议元数据。** 确认每一项提案的表面:意图(原因), data lineage 爆炸半径(最差的), rollback 计划。 缺少的田地是阻塞; agent 想要X不是建议
2. **Idempotency.** 名称 idempotency 键组成。它必须来自建议内容,因此重试返回相同的记录。包含时钟的键不是 idempotency 键; 它们是记录时间戳 。
3. **Durability.** 名称( PostgreSQL、 Redis、 耐久对象、 带有完整性检查的物件存储) 。 确认批准有效 agent 重新启动, 主机重新启动, 并部署。 模拟队列不符合条件 。
4. **批准表。** 橡胶印章批准( 单个批准按钮) 无法进行本次审计。 需要: 质疑和回应核对表, 并在意向理解、 爆炸辐射校验后予以肯定确认 , rollback 确认核对表是针对特定行动组,而不是一般行动组。
5. **Post-commit verify.** 确认工作流程在执行后重新读取目标资源, 并提醒验证失败。 “ 工具返回了 200” 不进行校验 。

艰难的拒绝 :
- 高科技领域不持续的提案。
- 审批流程,审评者为 agent itself.
- 任何不可逆转的生产行动,不提出质疑和反应。
- Idempotency 带有墙上时钟组件的键。
- 工作流量commit 相应行动没有核实。

拒绝规则 :
- 如果用户命名批准UI, 但无法命名后面的耐久商店, 请拒绝并先要求商店 。
- 如果用户对“ 最大” 的处理_budget_拒绝。预算上限成本,不正确。
- 如果部署触及欧盟的高风险范围和橡胶印章模式仍然存在,则根据第14条拒绝。

输出格式 :

退回一个提议 - 然后commit 审计方式:
- **外地拟议表** (意图/种族/爆炸/ rollback /许可——所有五个都需要)
- **Idempotency note** (关键成分, 重试测试结果)
- **易腐性线** (储存,生存 - 重新开始y/n)
- **核准面** (标注/核对表;如果有核对表,请列出问题)
- **Post-commit verify** (目前 y/n, 它重新读取)
- **Readiness** (生产/中转/仅研究)
