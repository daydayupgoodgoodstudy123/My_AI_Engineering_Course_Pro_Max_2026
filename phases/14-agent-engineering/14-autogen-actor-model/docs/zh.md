<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="the-actor-model-for-agents--async-messages-and-typed-runtimes"></a>

# 用于 Agents 的 Actor 模型：异步消息与类型化运行时

> Agents 作为 actors: 自动交换信件, 事件驱动处理器, 断层隔离, 自然同值货币。 AutoGen v0. 4 (微软研究, 2025年1月) 重新设计 agent orchestration 围绕这个模型; 框架现在处于维护模式, 使用 Microsoft Agent 框架(公开预览,2025年10月)作为生产的后续。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop阶段14 · 12 (工作流程模式)
**时间：** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 描述 actor 模型: agents 作为 actors,信息作为唯一的 IPC, 失败孤立 actor.
- 姓名 AutoGen v0. 4 的三张 API 层——核心,代理Chat,扩展——和每个图案的目的。
- 解释为什么将电文发送与处理脱钩,造成断层隔离和自然的同价货币。
- 执行标准字 actor 运行时间 Python 并输入一个二-agent 代码审查流进入它。

<a id="the-problem"></a>

## 问题

Most agent 框架同步: 1 agent 生产, 1 agent 消耗, 在调用堆叠中。 失败会崩溃堆叠。 货币币值被挂上。 分发需要重写 。

AutoGen v0. 4 的回答: actor 模型。 agent 是一个 actor 使用私人收件箱。 信件是唯一的交互作用。 运行时将发送从处理中分离出来。 失败会孤立为一个 actor货币是本地的,分配只是不同的运输方式

<a id="the-concept"></a>

## 概念

<a id="actors"></a>

### Actors

一个 actor 具有:

- 私人国家(从未直接从外部接触)。
- 收件箱( 消息队列) 。
- 处理器 : `receive(message) -> effects` 效果可以“复述”,“发送到其它 actor,"新发型 actor更新状态,停止自我

Two actors 无法共享内存。 他们只能发送信件 。

<a id="three-api-layers"></a>

### Three API layers

AutoGen v0.4 将表面分割为三:

1. **Core.** Low-level actor framework. `AgentRuntime`, `Agent`, `Message`, `Topic`。自动交换消息,由事件驱动。
2. **AgentChat.** 任务驱动的高级别 API (取代V. 2. 可交谈的代理商) `AssistantAgent`, `UserProxyAgent`, `RoundRobinGroupChat`, `SelectorGroupChat`.
3. **Extensions.** 合并 - OpenAI, Anthropic亚祖尔,工具,记忆

<a id="why-decoupling-matters"></a>

### 为何要脱钩

在V0.2模型中,调用 `agent_a.chat(agent_b)` 同步区块代理_a 直到代理商_b 返回。 v0. 4 中 `send(agent_b, msg)` 将信件输入代理_b 收件箱和回报。运行时间会晚一点。三种后果:

- **隔绝** Agent B 崩溃不崩溃 Agent A - 运行时间抓住B的操作员的失败并决定该怎么做(log、retry、die-letter)。
- **自然货币。** 多次播放信息; actors 同步处理他们的收件箱 。
- **Distribution-ready.** 收件箱+传输是相同的抽象信息,无论 actor 正在处理中, 或在另一个主机上 。

<a id="topologies"></a>

### Topologies

- **RoundRobinGroupChat.** Agents 以固定的旋转方式旋转。
- **SelectorGroupChat.** 选择器 agent 选择下一个根据对话背景进行的人。
- **Magentic-One.** 参考多agent 网络浏览、代码执行、文件处理小组 建在Chat探员身上

<a id="observability"></a>

### Observability

创建了开放遥测支持。 每条消息都发出一个范围; tool calls carry `gen_ai.*` 2026年《奥特尔·热纳依公约》的语义(第23条)。

<a id="status-maintenance-mode"></a>

### 状态:维护模式

2026年初: AutoGen v0.7.x 稳定,用于研究和原型设计。 微软已将开发活动转移到微软 Agent 框架,生产后继工具(公开预览2025年10月1日;1.0GA目标为Q1 2026结束)。 actor 模型是持久的想法。

```figure
actor-mailbox
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行标准字 actor runtime:

- `Message` 输入有效载荷 `sender`, `recipient`, `topic`, `body`.
- `Actor` 抽象 `receive(message, runtime)`.
- `Runtime` 事件循环, 与共享队列、 交付、 失败孤立 。
- 双actor demo: `ReviewerAgent` 审评代码, `ChecklistAgent` 运行一个核对表; 他们交换信息, 直到达成共识 。

运行：

```
python3 code/main.py
```

该 trace 显示信件发送, 一个模拟失败 actor 而不是打乱对方, 并一致的 共同的判决。

<a id="use-it"></a>

## 实际应用

- **自动Gen v0.4/v0.7** (维修)——研究、原型、多-agent patterns.
- **Microsoft Agent Framework** 生产后继产品(2025年10月公开预览); actor- 装模作样的想法在新鲜的 API.
- **LangGraph swarm topology** (第13条)——通过共用工具采取类似模式 handoffs.
- **Custom actor runtime** - 需要特定运输工具(NATS、RabitMQ、GRPC)。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-actor-runtime.md` 生成最小值 actor 运行时加一个团队模板( RoundRobin 或 Speator) , 用于给定的多功能-agent task.

<a id="exercises"></a>

## 练习

1. 添加一个死字队列: 当操作者升起时, 请将失败的信件停放到人体检查处。 DLQ 多久被玩家击中一次 ?
2. Implement `SelectorGroupChat`:选择器 actor 选择谁处理基于对话状态的下一个消息 。
3. 添加分布式传输: 将进程中的队列替换为 JSON-over-HTTP 服务器是 actors 可在不同的进程中运行。
4. 给每个信件发送 OTel 的线( 或者不打开) 。 Emit `gen_ai.agent.name`, `gen_ai.operation.name` 23课
5. 读取 AutoGen v0. 4 的建筑文章。 将您的玩具移植到真实位置 `autogen_core` API你制作时跳过什么?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Actor | "Agent" | 私有状态+收件箱+处理器;无共享内存 |
| Message | "Event" | 输入有效载荷; 唯一的办法 actors interact |
| Inbox | "Mailbox" | Per-actor 待发信件的队列 |
| 运行时 | "Agent host" | 传递消息和分离失败的事件循环 |
| 主题 | "Channel" | 命名发布订阅路径 actors |
| 错隔 | "让它崩溃" | One actor 失败不崩溃其它 |
| RoundRobinGroupChat | 固定旋转队 | Agents 轮流排列 |
| SelectorGroupChat | 来个"发条团队" | 选择者选择下一个选择者 |
| Magentic-One | 查询小组 | Multi-agent 用于 Web + 代码+ 文件的队 |

<a id="further-reading"></a>

## 进一步阅读

- [AutoGen v0.4, 微软研究](https://www.microsoft.com/en-us/research/articles/autogen-v0-4-reimagining-the-foundation-of-agentic-ai-for-scale-extensibility-and-robustness/) 重新设计员额
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) - 图形形替代
- [GenAI语义学公约](https://opentelemetry.io/docs/specs/semconv/gen-ai/) - 横跨自动Gen 默认发布
