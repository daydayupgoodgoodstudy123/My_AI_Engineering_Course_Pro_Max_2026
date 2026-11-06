<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="orchestration-patterns-supervisor-swarm-hierarchical"></a>

# Orchestration 模式：监督者、Swarm 与层级结构

> Four orchestration 2026年框架的重复模式:主管-工作人员, swarm /对等的,等级的,辩论。 Anthropic指南 : “ 这是为您需要建立正确的系统。 ” 开始简单; 仅在单 agent 加上五个工作流程模式是不够的。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 12(工作流程模式),阶段14 · 25(多至Agent Debate)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出四个重复出现 orchestration 和每个适合的时。
- 描述2026年 LangChain 建议:基于工具的调用监督与主管图书馆。
- Explain Anthropic建立正确的系统的规则 以及它如何阻挡了地形学的选择
- 使用普通脚本执行所有四个 LLM.

<a id="the-problem"></a>

## 问题

队伍达到"多 -agent" 在他们需要它之前,四个模式在框架之间反复出现;一旦可以命名它们,就可以选择正确的模式,或者完全跳过地形学。

<a id="the-concept"></a>

## 概念

<a id="supervisor-worker"></a>

### Supervisor-worker

- 中央路线 LLM 发送到专家 agents.
- 决定: 回到自我, 手向专家, 终止。
- 专家不相互交谈,所有路线都通过主管。

Frameworks: LangGraph `create_supervisor`, Anthropic orchestrator-workers, CrewAI 等级进程。

**2026 LangChain recommendation:** 直接监督 tool calls 而非 `create_supervisor`。给更精细 context engineering 控制——你决定每个专家都看到了什么。

<a id="swarm--peer-to-peer"></a>

### Swarm / 对等对等

- Agents 直接通过共享工具表面手动
- 没有中央路由器
- 潜伏率比主管低(跳跳)。
- 更难解释(没有单一的控制点)。

Frameworks: LangGraph swarm topology, OpenAI Agents SDK handoffs (当所有 agents ) (可以交给所有其他人)。

<a id="hierarchical"></a>

### 分层的

- 管理工人的次级监督员。
- 以嵌入的子集方式在 LangGraph; 嵌入船员 CrewAI.
- 缩放为大 agent 以运作复杂为代价的人口。

需要时:当主管的预算无法记录所有专家的描述时。

<a id="debate"></a>

### Debate

- 平行提议者+迭代交叉曲目(第25条)。
- 不太喜欢 orchestration 更多的核查,但在框架中显示是一种地形选择。

<a id="autonomous-crews-vs-deterministic-flows"></a>

### 自主船员与决定性流动

CrewAI 正式确定两种部署模式:

- **Flow** 确定性事件驱动自动化(建议生产起点)。
- **Crew** 自主作用协作。

这是对上面四种图案的正弦,但地图则显示为地形:流动通常是上层或下层;船员一般是上层或下层的主管。 LLM router.

<a id="anthropics-guidance"></a>

### Anthropic指导

"成功进入 LLM 空间不是建造最先进的系统,而是建设适合你需要的系统。”

决定次序:

1. Single agent +工作流程模式(课程12)——从这里开始。
2. 主管-工作人员——有2-4名专家时。
3. Swarm 潜伏比推理清晰更重要。
4. 等级主义——只有在主管预算失败时。
5. 辩论——准确性比费用更重要。

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **地形学第一思维** 我们需要多 -agent" 之前,确定什么问题多重 --agent solves.
- **Bouncing handoffs 在 swarm.** A - > B - > A - > B. 使用跳跳计数器。
- **假的等级** 三个层次,因为"企业",两个团队,倒闭

```figure
orchestration-pattern
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行所有四种模式的 stdlib 与脚本相对 LLM:

- `Supervisor` - 中央路由器
- `Swarm` 直接对等 handoffs.
- `Hierarchical` - 主管的主管。
- `Debate` 平行提议者+批评。

每个模式处理相同的三点任务(退款/错误/销售)。 Trace 形状不同。

运行：

```
python3 code/main.py
```

产出:每个模式 trace + 行动点数。 主管是最干净的; swarm 最短;等级最深;辩论费用最高。

<a id="use-it"></a>

## 实际应用

- **LangGraph** 用于主管和等级(取消的子集)。
- **OpenAI Agents SDK** 用于 handoffs- 做为工具(监督器形)。
- **CrewAI Flow** 用于确定生产。
- **Custom** 或当你想完全控制。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-orchestration-picker.md` 选一个学说来做它。

<a id="exercises"></a>

## 练习

1. 将上司- 工人转换为 swarm 路由器被移走,什么断路?
2. 添加跳对齐 swarm: 3 后拒绝 handoffs。它会被A - >B - >A弹跳吗?
3. 为12个专业领域构建两级等级系统。 上下文预算在不嵌套的情况下哪里失败 ?
4. 描述生产型工作量的四种模式。 哪种标准( 延迟性、 成本、 准确性、 可调试性) ?
5. Read Anthropic有效建设 Agents张贴,每张地图上都有四张,有没有干净的地图吗?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Supervisor-worker | "路透+专家" | Central LLM 派专家来,他们不互相说话 |
| Swarm | "Peer-to-peer" | Direct handoffs 通过共享工具; 没有中心路由器 |
| 分层的 | 督导长 | 大量人口的密闭子集 |
| Debate | "建议者+批评" | 平行提议者,交叉曲目(第25页) |
| 基于工具的调用监督 | "没有图书馆的超级主审" | 直接执行监督员 tool calls 用于上下文控制 |
| Crew | 自治团队 | CrewAI以角色为基础的协作模式 |
| Flow | "决定性的工作流程" | CrewAI事件驱动的生产模式 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic建设有效 Agents](https://www.anthropic.com/research/building-effective-agents) - 五个模式+ agent 工作流程
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) 主管 swarm,等级
- [CrewAI docs](https://docs.crewai.com/en/introduction) 船员与流动
- [Du等人,精神学会(arXiv:2305.14325)](https://arxiv.org/abs/2305.14325) 辩论模式
