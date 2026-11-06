---
name: durable-execution-review
description: Review a proposed long-running agent deployment for correct durable-execution shape (activities, determinism, checkpoint backend, human-input state, HITL-on-resume).
version: 1.0.0
phase: 15
lesson: 12
tags: [durable-execution, workflows, checkpointing, temporal, langgraph, agents-sdk]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


假设一个长期的 agent 部署(临时+ OpenAI Agents SDK, LangGraph 使用 PostgreSQL 检查器, 微软 Agent Framework, Claude 代码路由、云花耐久物体或内部等同物,根据耐久执行模式对设计进行审计。

显示 :

1. **活动清单。** 列出每项活动(LLM call, tool call, HTTP 请求, 文件写入) 。 对于每个对象, 请确认它是一个活动, 包含重试策略、 超时, 以及 idempotency 键。 LLM 活动信封外的电话是个可靠漏洞
2. **工作流的决定性因素** 识别工作流程代码( 墙钟、 随机、 外部状态) 中的非定義读数。 每个必须登记为副作用活动, 重放返回相同的值。 隐藏的非定时法是重放漂移的最常见原因 。
3. **Checkpoint backend.** 命名后端( PostgreSQL、 SQLite、 Redis、 耐久对象) 。 确认它能生存。 SQLite 只能运行。 Redis 需要 AOF 或快照配置。 Cloudflare 耐久对象是透明的, 但需要独特的密钥学科 。
4. **人的投入状态。** 确认 HITL 的暂停是一个头等工作流程状态, 而不是一个投票循环。 工作流程应该屏蔽在外部信号上( 批准队列、 Webhook, ) `interrupt()` 原始的) 完全恢复 当批准到达。
5. **高科技反射政策** 对于崩溃后的任何恢复, 请声明执行下一次活动前是否需要新的 HITL 。 如果没有此选项, durable execution 加上在崩溃前给予的批准, 当上下文改变时可以重新发射一个已核准的动作。 对长视野至关重要 。

艰难的拒绝 :
- Agent SDK 使用 LLM 电话不是作为活动包装的。
- Checkpoint 无法幸存的后端
- 嵌入墙时钟或随机不活动包装的工作流程。
- 人的投入是模拟投票圈而不是信号
- 长视距运行(超过一小时),没有HITL反射政策。
- 运行时没有预算的断开开关( 列松 13) , 以耐久性为顶端 。

拒绝规则 :
- 如果用户提出一个没有明确表达的持久工作流程 idempotency 影响、废物和需要 idempotency 先用钥匙,否则会双倍执行
- 如果用户无法显示重播测试( 运行工作流程、 崩溃中运行、 重放、 不声明双重副作用) , 拒绝并需要在生成前进行此测试 。
- 如果用户提议在无 HITL 情况下进行24小时无人看守运行 checkpoint35分钟的降解( Lesson 12 注释)使得这成为了可靠性问题,即使持久性是正确的。

输出格式 :

返回设计-审查备忘录, 内容为:
- **活动表** (活动,重试政策,超时, idempotency key)
- **决定因素审计** (非定时读数和如何处理)
- **Checkpoint backend** (名称, 生存部署 y/ n, 重播测试状态)
- **HITL 状态形状** (一等/投票/缺失)
- **HITL 模拟策略** (明确,附有理由说明)
- **Readiness** (生产/中转/仅研究)
