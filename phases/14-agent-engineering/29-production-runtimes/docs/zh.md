<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="production-runtimes-queue-event-cron"></a>

# 生产运行时：队列、事件与定时任务

> Production agents 运行六种运行状态:请求-回复, streaming, durable execution,基于队列的背景,由事件驱动,并排成日程。在选择框架之前先选择形状。 Observability 在每个形状中都包含载荷。

**类型：** 了解
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 13 (LangGraph阶段14 22(声音)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出六个运行时形状,并按框架/产品模式进行匹配。
- 解释一下 durable execution (LangGraph长视距任务。
- 描述事件驱动运行的时间和时间 Claude Managed Agents fits.
- 解释一下 observability- 多步骤装载索赔 agents.

<a id="the-problem"></a>

## 问题

Production agents 失败的方式a Jupyter 笔记本没有浮出水面: 37 步时网络超时,用户挂断中声调呼叫, 硬币工作在机器重新启动后死亡, 背景工人的记忆力耗尽。 运行时间形状决定了哪些失败是可行的 。

<a id="the-concept"></a>

## 概念

<a id="request-response"></a>

### Request-response

- Synchronous HTTP。用户等待完成。
- 仅可用于短期任务( < 30s)。
- 堆叠: Agno ()Python + FastAPI), Mastra (TypeScript + Express/Hono/Fastify/Koa)。 运输/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运/货运)。
- Observability:标准 HTTP 访问日志 + OTel 横跨。

<a id="streaming"></a>

### Streaming

- 递进输出的 SSE 或 WebSocket 。
- LiveKit将这个扩展至WebRTC, 用于语音/视频( Lesson 22)。
- 堆叠: 任何框架 streaming 支持 + 处理 SSE/WS 的前端。
- Observability:每千人的时间,首先token latency, tail latency.

<a id="durable-execution"></a>

### Durable execution

- 国家每一步都进行检查;失败时自动恢复。
- AutoGen v0. 4 自动 Gen actor 模型分离失败 agent (列松14)
- LangGraph核心差异( 列松 13) 。
- 当步数不详,回收成本高时,至关重要。

<a id="queue-based--background"></a>

### 基于队列/背景

- 工作进入队列,工人接听,结果通过网络路或酒吧/子公司回流。
- 长方圆必须的 agents (每任务几十至100个步骤,每任务 Anthropic电脑使用公告)
- 可选技术栈：Celery（Python）、BullMQ（Node）、SQS + Lambda（AWS），或自行实现。
- Observability:队列深度、每份工作时长分布、DLQ大小。

<a id="event-driven"></a>

### Event-driven

- Agents 订阅触发器:新电子邮件,公关打开,火烧。
- Claude Managed Agents 覆盖这个盒子( Lesson 17) 。
- CrewAI 流程(课程15)结构由事件驱动的确定性工作流程。
- Observability:触发源,事件到启动延迟, agent latency.

<a id="scheduled"></a>

### Scheduled

- Cron-shaped agents 定期运行。
- 组合 durable execution 失败的夜跑会恢复下个勾当
- Stacks: Kubernetes CronJob+一个持久框架;主办方(Render cron, Vercel cron)。

<a id="2026-deployment-patterns"></a>

### 2026 部署模式

- **CrewAI Flows** 用于由事件驱动的生产。
- **Agno** stateless FastAPI 用于 Python microservices.
- **Mastra** 服务器适配器 (Express, Hono, Fastify, Koa) embedding.
- **管道云/活生生的云** 管理声音(Lesson 22)。
- **Claude Managed Agents** 长期的静脉注射

<a id="observability-is-load-bearing"></a>

### Observability 包含载荷

没有开放遥测 GenAI 横跨( 列松 23) 加上 Langfuse/ Phoenix/ Opik 后端 (列松 24), 您无法调试多步 agent 失败于40步,这不能作为生产的选择。这是“我们快速调试”和“我们用更多的记录从零开始重现”之间的区别。

<a id="where-production-runtimes-fail"></a>

### 生产运行时间失效

- **错误的形状选择 。** 正在为一项5分钟的任务获取请求回复。 用户挂断; 工人堆积起来; 重试化合物 。
- **没有 DLQ 。** 给工人排队,不写死字,失败的工作就消失了
- **粗糙的背景工作。** Background agent 运行无 trace 导出。在用户报告前,失败是不可见的。
- **跳过耐久状态 。** 任何运行 > 30秒, 且您负担不起重新启动需求 durable execution.

```figure
wb-runtime-shapes
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 是一个标准多形状演示 :

- 请求-回应端点(平方函数)
- Streaming 处理器( 生成器) 。
- 以 DLQ 为单位的员工 。
- 事件触发登记
- 圆形排程器

运行：

```bash
python3 code/main.py
```

产出:5 traces 显示每个形状在同一任务上的行为。 agent 逻辑,不同的Shell。 Durable execution (第六形状)故意被第13课覆盖 LangGraph checkpointing.

<a id="use-it"></a>

## 实际应用

- **Request-response** 用于聊天式UX。
- **Streaming** 用于渐进式反应。
- **Durable** 做长视距任务
- **Queue** 用于批量/ 合成/ 长运行。
- **Event** 用于 agent reactivity.
- **Cron** 用于家务(初步合并、估价、成本报告)。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-runtime-shape.md` 选择任务运行时间形状并连接 observability requirements.

<a id="exercises"></a>

## 练习

1. 将您的课程 1 移植 ReAct 循环到堆叠中的所有六个形状。 哪一种形状适合哪个产品表面?
2. 向队列演示添加 DLQ。 模拟10%的工作失败; 表面 DLQ 大小 。
3. 写一个折叠式的反演 agent 夜里跑来跑去 与你的前20名对着 traces 从白天开始
4. Implement streaming 与 backpressure: 如果客户端慢, 请暂停 agent。这如何与转折预算相互作用?
5. Read Claude Managed Agents 医生,什么时候你才能移动一个自办的长视距 agent 来管理?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Request-response | "Synchronous" | 用户等待; 仅执行短任务 |
| Streaming | "SSE/WS" (SSE/WS) (SSE/WS) (SSE/WS) (SW) (SSE/WS) | 渐进输出; 更好的 UX; 每块可观察到的延迟值 |
| Durable execution | "从失败中恢复" | 检查状态; 在最后一步重新启动 |
| Queue-based | "背景工作" | 生产者/工人池/DLQ |
| Event-driven | "Trigger-based" | Agent reacts 外部事件 |
| DLQ | "死字队列" | 工作失败时的停车场 |
| Claude Managed Agents | "Hosted harness" | Anthropic- 举行长程静脉冲加缓冲+压缩 |

<a id="further-reading"></a>

## 进一步阅读

- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) — durable execution details
- [Claude Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview) - 长期接待的Async
- [Anthropic,引入计算机使用](https://www.anthropic.com/news/3-5-models-and-computer-use) - "几十到100个步骤,每个任务"
- [AutoGen v0.4 (微软研究)](https://www.microsoft.com/en-us/research/articles/autogen-v0-4-reimagining-the-foundation-of-agentic-ai-for-scale-extensibility-and-robustness/) — actor- 典型的过失隔离
