<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="the-multi-agent-primitive-model"></a>

# 多 Agent 的基本单元模型

> 四个原始人,没有别的了 agent, 该 handoff共有状态, 管弦乐队—— 跨越四维的设计空间, 以及主要的多维-agent 2026年框架航运(AutoGen, LangGraph, CrewAI, OpenAI Agents SDK微软 Agent 框架) 是其中的点。 此课从零开始, 在所有四个上运行一个玩具系统, 然后将每个主要框架都映射到相同的轴上, 这样您就可以在一个段落中读取任何新的发布 。

**类型:** 学习
**语言:** Python (stdlib)
**先修要求:** 第14阶段(Agent 工程,第16阶段 01Agent)
**时间:** ~60分钟

<a id="problem"></a>

## 问题

每六个月 一个新的多 -agent 框架船,2023年自动Gen CrewAI 2024年 时间轴: 2024年 LangGraph 和 OpenAI Swarm 2024年4月Google ADK。 Agent 2026年2月的RC框架,每份新闻稿都声称是“正确的抽象”。

如果你一次学会一个,你会烧掉 APIs 医生对什么是"不同"意见不一agent是一个框架,它称之为共同记忆 一个“黑板”,另一个称为“信息池”,第三个称它为“国家格子”。你开始怀疑这个字段只是空虚。

市场营销中,四个原始人很稳定。学习他们一次,读一下每个新的框架。

<a id="concept"></a>

## 概念

<a id="the-four-primitives"></a>

### 四个原始人

1. **Agent** — 一个 system prompt 加上工具列表。 无国籍; 每次运行都从它开始 system prompt 以及当前信息的历史。
2. **Handoff** · 控制从一个系统转移 agent 机械上,是 tool call 返回新 agent 或遵循条件的图形边缘。
3. **共享状态** 超过一个的数据结构 agent 也可以读(有时写) 。 信件库、 黑板、 键值存储、 矢量内存 。
4. **Orchestrator** 选择:清晰的图表(确定性)、 LLM 选择发言者( 软), 最后一位发言者的 handoff 调用 (OpenAI Swarm),或排队上的排程器(swarm architecture).

这就是整个设计空间。 每个框架都为每个轴选择默认值; rest 是表面语法。

<a id="how-every-2026-framework-maps-to-it"></a>

### 每2026年的框架如何绘制

| 框架 | Agent | Handoff | 共享状态 | Orchestrator |
|-----------|-------|---------|--------------|--------------|
| OpenAI Swarm / Agents SDK | `Agent(instructions, tools)` | 工具返回 Agent | 打电话的人的问题 | 该 LLM下一个 handoff call |
| AutoGen v0.4 / AG2 自动 Gen / AG2 | `ConversableAgent` | 组合域选择器 | 信息库 | 选择函数(LLM 或圆柱) |
| CrewAI | `Agent(role, goal, backstory)` | `Process.Sequential / Hierarchical` | 任务产出已链条 | manager LLM 静态顺序 |
| LangGraph | 节点函数 | 图形边缘+条件 | `StateGraph` reducer | 图表,确定 |
| Microsoft Agent Framework | agent + orchestration patterns | pattern-specific | 线条/ 上下文 | pattern-specific |
| 谷歌 ADK 键盘 | agent + A2A card | A2A task | A2A artifacts | 由主机决定 |

表面差异很大,地下:相同的四个把手。

<a id="why-this-matters"></a>

### 为何这重要

一旦你看到原始的,框架比较就变成了一个简短的核对表:

- 管弦乐队相信 LLM 至路线(Swarm)或者它用代码输入路径(LangGraph)?
- 共享全历史( GroupChat) 还是预测( 国家格子缩放器) ?
- 可以 agents 修改对方的 prompts (CrewAI 管理器)或只手动(Swarm)?

这三个问题回答了80%的框架适合一个特定的问题。你停止购物“最好的多个-agent 框架”并开始设计您真正关心的轴。

<a id="the-stateless-insight"></a>

### 无国籍问题的深入了解

除了共同国家之外,每个原始国家都是无国籍的。 Agent 是 (a) 函数prompt工具) Handoff 是一个函数调用。Orchstrator是一个排程器。 **系统里唯一有声的就是共享状态** 有趣的虫子都住在这里:记忆中毒(Lesson 15)、信息订购、发音、写作争论。

隐藏共享状态的框架( A)Swarm将问题推到呼叫者手中。 集中它的框架( )LangGraph checkpoint),使其可以检查,但将协调费用转移到共同国家实施。

<a id="anatomy-of-a-single-primitive"></a>

### 单一原始体的解剖

<a id="agent"></a>

#### Agent

```
Agent = (system_prompt, tools, model, optional_name)
```

没有记忆,没有状态,两个 agents 和相同的 system prompt 工具是可互换的,每件看起来...agent state 实际处于共享状态或 handoff protocol.

<a id="handoff"></a>

#### Handoff

```
Handoff = (from_agent, to_agent, reason, payload)
```

三个执行占多数:

- **函数返回** - 工具返回下一个 agent。这是 OpenAI Swarm pattern. Agents 携带路线在工具图中。
- **图形边** — LangGraph边是宣示性的。 LLM 生成一个值; 条件选择下一个节点。
- **选择演讲人** - AutoGen Gen GroupChat. 选择函数(有时本身是 LLM 接听游泳池的电话 接听下一个演讲的人

<a id="shared-state"></a>

#### 共享状态

```
SharedState = { messages: [], artifacts: {}, context: {} }
```

至少列出一个消息列表。通常更多:结构化的文物( i)CrewAI 任务产出),打字背景(LangGraph 外部内存(MCP,矢量 DB)。

两个主题: **整个池** (每个 agent 看见每条信息) **projected** (agents )整个集合是简单而规模化的。预计集合规模,但需要先期设计。

<a id="orchestrator"></a>

#### Orchestrator

```
Orchestrator = ({state, last_speaker}) -> next_agent
```

四个味道:

- **Static** ——图表在施工时间固定(LangGraph deterministic, CrewAI Sequential).
- **LLM-selected** — 一个 LLM 读完游泳池,然后选下一个扬声器(AutoGen, CrewAI Hierarchical).
- **Handoff-driven** - 水流 agent 决定,拨打 handoff 工具 (Swarm).
- **Queue-driven** 工人从共同队列中拉起;没有明确的下一发言者(swarm 结构,矩阵)

<a id="what-changes-between-frameworks"></a>

### 框架之间的哪些变化

一旦原始物质被固定下来 剩下的设计决定是:

- **记忆战略** 短期与长期检查站(LangGraph checkpointer).
- **安全边界** -谁能批准 handoff (human-in-the-loop).
- **成本会计** — 每-agent token budgets.
- **Observability** 追踪 handoffs持续重播

最原始的动物上都可执行,没有一个是新原始的

```figure
a5-primitive-radar
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行在~150条标准线上的四条原始线 Python。没有真实的 LLM — 每个 agent 是一个脚本化的政策,因此重点始终放在协调结构上。

文件导出 :

- `Agent` 数据类的名称, system prompt工具,政策功能。
- `Handoff` 函数返回新 agent.
- `SharedState` - 一条安全的信息池
- `Orchestrator` - 三个变式: `StaticOrchestrator`, `HandoffOrchestrator`, `LLMSelectorOrchestrator` (simulated).

演示运行相同的三个 -agent 管道 (研究  写  复选) 通过所有三种管弦乐队类型并打印结尾处的信息库。 您可以看到输出只在 *选择下一个*; 该 agents 并且共享状态是相同的

运行：

```
python3 code/main.py
```

预期输出: 3个管弦乐队运行, 每个模式一个。 每个打印最后的信息库 。 handoff- 驱动跑跑到更少 agents 如果研究人员决定早做,那就是 LLM- 微量交易

<a id="use-it"></a>

## 实际应用

`outputs/skill-primitive-mapper.md` 这是一种能读取任何多功能的技巧agent 代码库或框架文档, 返回四种原始映射。 在深度阅读文档前, 运行在新的框架发布上, 以获得一段落的理解 。

<a id="ship-it"></a>

## 交付成果

在采用新框架之前,请为它写出原始的绘图。 如果无法,文件不完整,或者框架正在发明第五个原始框架(罕见-检查未见的共同状态口味 ) 。

将绘图输入您的建筑文档。 当新团队成员加入时, 在您之前给他们发送映射 API 文档。 当框架版本改变时, 将显示映射, 而不是更改日志 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 三次不同时 agent 观察管弦乐队的选择如何改变 agents run.
2. 执行第四个管弦乐队类型:一个队列驱动型 agents 民调是共事的状态。 什么样的僵局会发生,你如何发现?
3. 阅读 LangGraph 快速入门（ https://docs.langchain.com/oss/python/langgraph/workflows-agents ），将其改写为四种基本构件。LangGraph 的哪些抽象与这四种构件一一对应，哪些只是便利封装？
4. 阅读 OpenAI 的 Swarm cookbook（ https://developers.openai.com/cookbook/examples/orchestrating_agents ）。指出四种基本构件中，哪一种在 Swarm 中最易使用，哪一种则交由调用者处理。
5. 在此表格中查找一个框架, 完全隐藏共享状态。 解释当 agents 需要协调 handoffs 无需重读历史。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Agent | "一个 LLM 带工具的" | 一个 `(system_prompt, tools, model)` 3个,无国籍 |
| Handoff | "控制权的转让" | 结构化的调用, 命名下一个 agent 三个执行点:函数返回、图形边缘、扬声器选择。 |
| 共享状态 | "记忆"/"文字" | 多元体中唯一有声明的部分agent 系统,信息池或黑板 |
| Orchestrator | "Coordinator" | 谁决定谁来运行下一个。 LLM selector, handoff- 驱动,或排驱动。 |
| Primitive | "Abstraction" | 每个框架的四轴中有一个参数。 feature. |
| 信件库 | "分享聊天历史" | 完全历史共享状态,很容易解释,比例很差 |
| 预计状况 | "扫荡的风景" | 角色对共享状态的视角。 比例需要计划设计 。 |
| 选择演讲人 | "谁说下一个" | 函数( 通常为 LLM选择下一个 agent 一组人 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI 烹饪手册:管弦乐 Agents 常规和 Handoffs](https://developers.openai.com/cookbook/examples/orchestrating_agents) 最清楚的表述 handoff-driven orchestration
- [自动Gen 稳定文档](https://microsoft.github.io/autogen/stable/) ——GroupChat+选择发言者是 LLM-selected orchestration
- [LangGraph 工作流程和 agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents) - 图形边 orchestration 和基于减少的共享状态
- [CrewAI introduction](https://docs.crewai.com/en/introduction) 作用目标的背书 agents,序列/等级进程
- [AG2(社区自动继续)](https://github.com/ag2ai/ag2) 微软将 v0. 4 移动到维护中后, 即时自动Gen v0. 2 行
