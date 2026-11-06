<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="handoffs-and-routines--stateless-orchestration"></a>

# Handoffs 与例程：无状态 Orchestration

> OpenAI的 Swarm 蒸馏的多-agent orchestration 改为两个原始的: **routines** (指示+工具作为 system prompt) 和 **handoffs** (一个返回另一个工具) Agent没有国家机器,没有分支 DSL LLM 右侧的路线 handoff 工具。 OpenAI Agents SDK 2025年3月)是生产的后续。 Swarm 其整个来源都符合几百行。 API 表面大致是 "agent = prompt + 工具; handoff =函数返回 agent限制:无国籍,所以记忆是打电话者的问题。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段16 -04(初级模型)
**时间：** ~60 分钟

<a id="problem"></a>

## 问题

每一个多 -agent 框架要您学习 DSL : LangGraph 结点和边缘, CrewAI 团队和任务, AutoGen Gen Chat 和 管理器。 DSL 是真正的抽象, 但让事情比需要的要重。

Swarm 向相反的方向推:使用模型已经拥有的工具调用能力。 Handoffs become tool calls。管弦乐 agent 国家机器在 agents' system prompts.

<a id="concept"></a>

## 概念

<a id="two-primitives"></a>

### 两个原始的

**Routine.** 一个 system prompt 定义 agent角色和可用工具。把它想象成一套范围说明: agent;如果用户询问退款,请将退款交给退款 agent."

**Handoff.** 一个工具 agent 返回新 Agent 对象。 Swarm 运行时间检测 Agent 返回值并切换活动 agent 下一回合。 。

这就是整个抽象。

```
def transfer_to_refunds():
    return refund_agent  # Swarm sees Agent return → switch active agent

triage_agent = Agent(
    name="triage",
    instructions="Route the user to the right specialist.",
    functions=[transfer_to_refunds, transfer_to_sales, transfer_to_support],
)
```

分层 agent的 system prompt 让它选择右 handoff 依据 user message. 该 LLM工具呼叫就是路由

<a id="why-it-is-viral"></a>

### 为什么是病毒

- **小 API.** 有两个概念要学习
- **使用模型已经做的。** Tool calling 已经是各供应商之间的生产等级。
- **没有国家机器的负担** 您不描述图形; agents' prompts 描述他们交给谁

<a id="the-stateless-trade"></a>

### 无国籍贸易

Swarm 框架在运行中保留信息历史,但没有任何持续。记忆、连续性、长期任务——所有呼叫者的问题。

生产(OpenAI Agents SDK2025年3月),这是主要变化之一: SDK 添加内置会话管理器, guardrails,同时进行追踪 handoff primitive.

<a id="when-swarmhandoffs-fit"></a>

### 当 Swarm/handoffs fit

- **三角形模式** Front-line agent 将用户引向专家
- **Skill-based handoffs.** "如果任务需要代码, 打电话给编码者; 如果它需要研究, 打电话给研究人员。"
- **简短的,有界限的对话。** 客户支持, 常见问题到卡片, 简单的工作流程 。

<a id="when-swarm-struggles"></a>

### 当 Swarm struggles

- **长会,有共同的记忆。** Handoffs 将对话状态重置为新 agent的 prompt 加上历史。 没有持续状态 agents 没有电话管理员管理的内存 。
- **平行执行。** Handoff 一次性—— 活动 agent 开关。 平行要求调用器 协调多个 Swarm runs.
- **审计和重播。** 无国籍者跑步很难精确地重播; LLM的 handoff 选择不是决定性的。

<a id="openai-agents-sdk-march-2025"></a>

### OpenAI Agents SDK (2025年3月)

生产继承者补充说:

- **会话状态 。** 持续线横穿。
- **Guardrails.** 输入/产出验证钩。
- **Tracing.** 每个 tool call 和 handoff 已经登录。
- **Handoff filters.** 控制环境转让 handoff.

该 handoff 原始生物生存;生产机能学被围绕它而增加。

<a id="swarm-vs-groupchat"></a>

### Swarm 组目录

两者都使用 LLM- 驱动路线,但他们有分歧 **选择下一个**:

- 组域: 选择器( 函数或 LLM)从外面挑选下一个发言者。
- Swarm: 当前 agent 选择它的继承人, 调用 handoff tool.

Swarm 是 "agent 来决定下一步是什么, 集团Chat是“经理决定下一步是什么”。 Swarm决策在活动 agent的 tool call; 集团的生活中 `GroupChatManager`.

```figure
sw-handoff-routing
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements Swarm 从头开始: a Agent 数据类, a handoff 机制(工具返回) Agent运行循环,以探测 agent switches.

演示: 分级 agent 退款、销售或支助专家的路线。 handoff.

Run:

```
python3 code/main.py
```

<a id="use-it"></a>

## 实际应用

`outputs/skill-handoff-designer.md` 设计a handoff 特定任务表: agents 存在, handoffs 它可以调用,什么背景转移。

<a id="ship-it"></a>

## 交付成果

Checklist:

- **Handoff logging.** 每个 handoff 写 trace 与 --agent, 以-agent,背景简介。
- **上下文转让规则。** 决定下一步 handoff:完整历史(昂贵)、最后N条信息或摘要。
- **Guardrail 在 handoff.** 一个 handoff 向拥有不同工具许可的专家提供证明,否则 prompt injection 能够强制不想要 handoffs.
- **循环检测** Two agents 交接和转接是常见的失败; 只需简单的最后K型环检查即可检测 。
- **Fallback agent.** 如果为 handoff 目标不存在, 返回到安全默认值 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`,分解退款 agent。确认第二转 agent 退款 退款 退款
2. 添加循环检测规则: 如果相同, 则 agents 连续三次,逼出出口,设计后退
3. 读 OpenAI Agents SDK 医生 handoff 过滤器。 执行“ 概括- ”handoff" 版本: 即将删除的 agent 将上下文压缩到项目符号摘要中,然后才收到 agent 接管这个案子
4. 比较 Swarm handoff 选择。 prompt injection 更糟,为什么?
5. 阅读 Swarm cookbook（ https://developers.openai.com/cookbook/examples/orchestrating_agents ）。找出 Swarm 的一项明确设计决策，并说明 OpenAI Agents SDK 对该决策做了修改还是予以保留。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Routine | "该 agent prompt" | System prompt + 工具列表。定义角色和可用 handoffs. |
| Handoff | "向另一个人转移 agent" | 活动工具 agent 返回新 Agent运行时开关激活 agent. |
| Stateless | "在运行之间没有记忆" | Swarm 记忆是召唤者的责任。 |
| Active agent | "谁在说话" | 该 agent 正在举行对话。 Handoff 改变这个。 |
| 上下文转移 | "什么行动 handoff" | 即将到来的历法 agent 见:完整、最后N或摘要。 |
| Handoff loop | "Agents ping-pong" | 失败模式, 其中两个 agents 继续互相交还 |
| OpenAI Agents SDK | "Production Swarm" | 2025年3月 接续;增加会议, guardrails,在 handoff primitive. |
| Handoff filter | 转接时的齿轮 | SDK feature 检查和修改上下文 handoff boundary. |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI 烹饪手册——管弦乐 Agents:常规和 Handoffs](https://developers.openai.com/cookbook/examples/orchestrating_agents) 参考表达
- [OpenAI Swarm repo](https://github.com/openai/swarm) 最初执行,作为概念参考
- [OpenAI Agents SDK docs](https://openai.github.io/openai-agents-python/) 生产后再举行会议和追踪
- [Anthropic handoff-在-Claude notes](https://docs.anthropic.com/en/docs/claude-code) 怎样? Claude Code subagents 使用 a handoff- 像是通过模式 `Task`
