<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="openai-agents-sdk-handoffs-guardrails-tracing"></a>

# OpenAI Agents SDK：Handoffs、Guardrails 与追踪

> OpenAI Agents SDK 是轻量级的多 -agent 框架 API。五个原始元素: Agent, Handoff, Guardrail. . . . . 会话, 追踪. Handoffs 工具名称 `transfer_to_<agent>`. Guardrails 输入或输出时进行旅行。 默认情况下, 正在追踪 。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop阶段14 -06(工具使用)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 五个原始人的名字 OpenAI Agents SDK.
- Explain handoffs:为什么它们被建为工具,模型的形状是什么,背景转移如何。
- 区分输入 guardrails, 输出 guardrails工具 guardrails; 解释 `run_in_parallel` 阻塞模式 。
- 执行 Stdrb 运行时间 handoffs + guardrails + 横线跟踪。

<a id="the-problem"></a>

## 问题

Agents 无法进行清洁的委托 最终把一切塞进一个 prompt. Agents 不使用 guardrails 船舶 PII, 政策破坏输出, 或者永远循环 。 OpenAI的 SDK 将三种原始的 多种的agent 工作可以牵引。

<a id="the-concept"></a>

## 概念

<a id="five-primitives"></a>

### 五个原始人

1. **Agent.** LLM + 说明+工具+ handoffs.
2. **Handoff.** Delegation 向另一个 agent。作为名为“F2”的工具,代表模型 `transfer_to_<agent_name>`.
3. **Guardrail.** 输入时验证( 第一个) agent 仅),产出(最后 agent 仅此选项),或工具调用(每个函数工具)。
4. **Session.** 自动对齐对话历史
5. **Tracing.** 内置的间隔 LLM generations, tool calls, handoffs, guardrails.

<a id="handoffs-as-tools"></a>

### Handoffs 用作工具

模型看到 `transfer_to_billing_agent` 在其工具列表中。 调用它表示运行时间 :

1. 复制对话背景( 或者通过 `nest_handoff_history` beta).
2. 初始化目标 agent 并附有指示。
3. 继续目标运行 agent.

这是监督员的模型(Lesson 13/Lesson 28),已成产品。

<a id="guardrails"></a>

### Guardrails

三种味道:

- **输入 guardrails.** 开始跑 agent输入。 在任何 LLM call.
- **输出 guardrails.** 运行在最后 agent发现PII泄漏,违反政策,反应不灵验
- **Tool guardrails.** 运行每个功能工具。 校验参数、 检查权限、 审计执行 。

Mode:

- **Parallel** (默认). Guardrail LLM 运行于主控 LLM下方 tail latency。如果被绊倒,主 LLM丢弃工作( )token waste).
- **Blocking** (`run_in_parallel=False`). Guardrail LLM 先跑,如果绊倒,就不行 tokens 浪费在主电话上。

提高绊线 `InputGuardrailTripwireTriggered` / `OutputGuardrailTripwireTriggered`.

<a id="tracing"></a>

### 追踪

默认的 LLM generation, tool call, handoff, 和 guardrail 发出一个波段。 `OPENAI_AGENTS_DISABLE_TRACING=1` 选择退出。 `add_trace_processor(processor)` 粉丝横穿至您自己的后端 OpenAI's.

<a id="sessions"></a>

### Sessions

`Session` 将对话历史保存在后端( SQLite、 Redis、 自定义) 。 `Runner.run(agent, input, session=session)` 自动装入和附加 。

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **Handoff drift.** Agent 手拿开 Agent B 手又回到 Agent A. 添加一个跳计数器。
- **Guardrail bypass.** Tool guardrails 只对功能工具开火; 内置工具( 文件阅读器、 网络检索) 需要单独策略 。
- **Over-tracing.** 敏感内容的间隔。 配对 OTel GenAI 内容捕获规则( 课程23) —— 外部存储, ID 引用 。

```figure
ae-agent-handoff
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行 SDK 形状,以标准lib :

- `Agent`, `FunctionTool`, `Handoff` (作为传输语义的函数工具)
- `Runner` 含有投入/产出/工具 guardrails, handoff 调度,跳台。
- 显示一个简单的横线发射程序 trace shape.
- 分层 agent 依据用户的查询,将信息转到账单或支持; guardrail 一次输入旅行。

运行：

```
python3 code/main.py
```

该 trace 显示两个成功 handoffs,一个输入 guardrail 旅行,和一棵横树 反映什么真实 SDK emits.

<a id="use-it"></a>

## 实际应用

- **OpenAI Agents SDK** 用于 OpenAI- 头等货
- **Claude Agent SDK** (第17段) Claude- 头等货
- **LangGraph** (教训13) 当你想要明确状态和持久恢复。
- **Custom** 需要精确控制时(语音、多供应商、联合部署)

<a id="ship-it"></a>

## 交付成果

`outputs/skill-agents-sdk-scaffold.md` 脚架 Agents SDK 带有分级的应用程序 agent, handoffs,输入/产出/工具 guardrails,会话商店,和 trace processor.

<a id="exercises"></a>

## 练习

1. 添加a handoff 跳转计数器: N 调换后拒绝 。 Trace 行为。
2. Implement `nest_handoff_history` 作为一种选项——在传输之前将先前的信件折成一个摘要。
3. 写入屏蔽输出 guardrail。比较 prompts 那样会让它与那些通过的人相撞
4. Wire `add_trace_processor` 改为 JSON 记录器,它每条波段的形状是什么?
5. 读 SDK 医生,把你的小玩具端到 `openai-agents-python`你做错了什么?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Agent | "LLM + 说明” | Agent 类型 SDK; 拥有工具和 handoffs |
| Handoff | "Transfer" | 使用模型调用工具将调用权下放给另一个 agent |
| Guardrail | "政策检查" | 输入/输出/工具调用时的验证 |
| Tripwire | "Guardrail trip" | 例外在 guardrail rejects |
| Session | 历史商店 | 运行中的对话内存持续 |
| 追踪 | "Spans" | Built-in observability over LLM +工具+ handoff + guardrail |
| Blocking guardrail | 顺序检查 | Guardrail 先运行;否 token 旅行时浪费 |
| Parallel guardrail | "当前检查" | Guardrail 运行并排; 低潜伏, 废物 tokens 旅行时 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI Agents SDK docs](https://openai.github.io/openai-agents-python/) 原始人, handoffs, guardrails,追踪
- [Claude Agent SDK overview](https://platform.claude.com/docs/en/agent-sdk/overview) — Claude- 优雅的对口人
- [Anthropic建设有效 Agents](https://www.anthropic.com/research/building-effective-agents) - 何时达到 handoffs 完全没有
- [GenAI语义学公约](https://opentelemetry.io/docs/specs/semconv/gen-ai/) - 标准 Agents SDK 横跨地图
