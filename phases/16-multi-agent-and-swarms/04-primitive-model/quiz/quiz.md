# 测验 · 多 Agent 的基本单元模型（The Multi-Agent Primitive Model）

> **阶段 16 · 多智能体与集群 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四个原语 | Agent、Handoff、Shared state、Orchestrator 张成一个四维设计空间，主流框架都是其中的一个点，其余是表面语法 |
| 2 | Agent | `(system_prompt, tools, model, optional_name)`；无状态，每次运行都从 system prompt 和当前消息历史出发，同 prompt 同工具的两个 agent 可互换 |
| 3 | Handoff 的三种实现 | 函数返回（tool 返回下一个 agent，OpenAI Swarm）、图的边 + 条件（LangGraph）、发言者选择（AutoGen GroupChat） |
| 4 | Shared state | 多个 agent 可读（有时可写）的数据结构：消息池、黑板、KV、向量记忆；分 full pool（全量）与 projected（按角色投影）两种拓扑 |
| 5 | Orchestrator 的四种风格 | 静态图、LLM 选择、handoff 驱动、队列驱动（worker 从共享队列拉活，没有显式"下一个发言者"） |
| 6 | 无状态洞见 | 除 shared state 外的原语都是无状态的；所有有趣的 bug（记忆投毒、消息顺序、版本、写竞争）都在 shared state 里 |
| 7 | 框架映射 | Swarm/Agents SDK：handoff 由 LLM 驱动、状态交给调用方；AutoGen：消息池 + selector；CrewAI：角色 agent + Sequential/Hierarchical；LangGraph：节点 + 边 + StateGraph reducer |
| 8 | 三个比较问题 | 路由是交给 LLM 还是钉在代码里？共享状态是全量历史还是投影？agent 能否修改彼此的 prompt，还是只能 handoff？——讲义称能回答 80% 的选型问题 |
| 9 | 不是新原语的东西 | 记忆策略（checkpoint）、安全边界（谁批准 handoff）、成本核算（每 agent token 预算）、可观测性——都建在四个原语之上 |
| 10 | 代码演示的结论 | 同一组 agent 和状态，只换 orchestrator；默认脚本下三者输出相同，只有当 agent 提前 `done` 或形成循环时差异才显现 |

### 核心技能（能动手做到）

- [ ] 用 dataclass + 带锁的列表实现一个最小消息池，并说清 `snapshot()` 为什么要返回拷贝
- [ ] 分别实现静态、handoff 驱动、selector 驱动三种 orchestrator，并为每种加上步数上限
- [ ] 构造输入让三种 orchestrator 产生不同的发言序列，并解释差异来源
- [ ] 读任意一个新框架的文档，写出它在四个原语上的映射（一段话）
- [ ] 指出"无状态 agent + 有状态共享池"设计下最容易出 bug 的位置，并给出防护手段
- [ ] 实现一个队列驱动的 orchestrator，并能检测其中的死锁

---

## 二、基础自测（选择题）

**Q1.** 讲义所说的多 agent 系统的四个原语是：

- A. Planner、Executor、Critic、Verifier
- B. Prompt、Model、Tool、Memory
- C. Agent、Handoff、Shared state、Orchestrator
- D. Message、Channel、Broker、Topic

**Q2.** 讲义认为，四个原语中唯一有状态的是哪一个？

- A. Shared state
- B. Agent
- C. Handoff
- D. Orchestrator

**Q3.** OpenAI Swarm / Agents SDK 的 handoff 在机制上是什么？

- A. 一条声明式的图边，由条件函数选择下一个节点
- B. 一个 selector 函数读取消息池选出下一个发言者
- C. 一个 worker 从共享队列里拉取任务
- D. 一次 tool 调用，其返回值就是下一个 agent

**Q4.** 按讲义的 orchestrator 四种风格，CrewAI 的 `Process.Hierarchical` 属于：

- A. 静态（Static）
- B. LLM 选择（LLM-selected）
- C. Handoff 驱动（Handoff-driven）
- D. 队列驱动（Queue-driven）

**Q5.** 本节代码中，researcher 发言时返回了 `"handoff": "done"`，`StaticOrchestrator(["researcher", "writer", "reviewer"])` 接下来会怎样？

- A. 仍然依次运行 writer 和 reviewer，因为静态 orchestrator 不读取 `handoff` 字段
- B. 立即结束，因为 `done` 是全局停止信号
- C. 跳过 writer，直接运行 reviewer
- D. 抛出 `KeyError`，因为 `done` 不在团队里

**Q6.** 关于 shared state 的两种拓扑，说法正确的是：

- A. full pool 扩展性好，但需要事先设计 schema
- B. projected 意味着每个 agent 都能看到全部历史，最容易调试
- C. full pool 简单但扩展性差；projected 按角色给出视图，能扩展但需要预先设计 schema
- D. 两者只在存储介质上不同，对 agent 可见的信息完全一样

**Q7.** 在本节代码中，某个 agent 的策略函数返回 `{"from": "reviewer", "content": "Review verdict: approved."}`，而该 agent 的 `name` 是 `"writer"`。这条消息在消息池中的发送者是：

- A. `writer`，因为 `Agent.run` 总会用自己的名字覆盖 `from`
- B. 两条消息，分别来自 writer 和 reviewer
- C. 抛出异常，因为 `from` 与 `name` 不一致
- D. `reviewer`，因为 `setdefault` 只在键不存在时才写入

**Q8.** 讲义列出了在原语确定之后"框架之间还会变化的设计决策"。以下哪一项属于这类**建在原语之上的决策**，而不是原语本身？

- A. Handoff
- B. 成本核算（per-agent token 预算）
- C. Shared state
- D. Orchestrator

---

## 三、动手 / 代码题

**Q9.** 在运行三种 orchestrator 之前，先往消息池里放一条 researcher 的旧笔记：

```python
def seeded():
    s = SharedState()
    s.append({"from": "researcher", "content": "prior note", "handoff": "writer"})
    return s

StaticOrchestrator(["researcher", "writer", "reviewer"]).run(make_team(), s1 := seeded())
HandoffOrchestrator("researcher").run(make_team(), s2 := seeded())
LLMSelectorOrchestrator("researcher", round_robin_selector).run(make_team(), s3 := seeded())
```

写出三个消息池中每条消息的 `(from, handoff)`，并解释为什么只有其中一个"提前结束"。这说明了"信任 LLM 路由"的什么取舍？

**Q10.** 阅读 `round_robin_selector`：

```python
def round_robin_selector(state: SharedState, team: dict[str, Agent]) -> Optional[str]:
    if not state.messages:
        return None
    last = state.messages[-1]["from"]
    names = list(team.keys())
    idx = (names.index(last) + 1) % len(names)
    if len([m for m in state.messages if m["from"] == "reviewer"]) >= 1:
        return None
    return names[idx]
```

1. 指出至少三处问题（并发安全、健壮性、业务逻辑）。
2. 改写成一个更像"LLM 选择"的 `review_loop_selector`：reviewer 判定 `needs revision` 时把发言权交回 writer，最多允许 2 轮修改；判定 `approved` 时结束；池中出现团队外的发言者时不崩溃。

**Q11.** 讲义练习 2：实现第四种 orchestrator——**队列驱动**。要求：`SharedState` 增加一个任务队列；每个 agent 只处理 `assignee == 自己` 的任务，处理完可以往队列里投递新任务；orchestrator 循环直到队列为空。请写出核心代码，并回答：会出现什么样的死锁？如何检测？

**Q12.** 对照讲义与代码，找出至少三处"讲义说的"与"代码做的"不一致，并说明哪些会误导学习者。

---

## 四、面试高频题

**Q13.**（基础必考）请用"四个原语"的框架，分别描述 LangGraph、AutoGen 和 OpenAI Agents SDK，并说明它们最大的差别在哪根轴上。

**Q14.**（原理深挖）为什么说"除了共享状态，其它原语都是无状态的"？这个判断对系统设计有什么指导意义？有没有反例？

**Q15.**（工程实践）你的团队要从 OpenAI Swarm 风格迁移到 LangGraph 风格的实现。在四个原语上分别要改什么？迁移中最容易出问题的是哪一部分？

**Q16.**（场景设计）设计一个客服系统：分诊 agent、退款 agent、技术支持 agent、人工升级。请分别给出四个原语的选择，并说明在哪里加 human-in-the-loop。

**Q17.**（追问型）"既然四个原语就能描述所有框架，那为什么还会不断出现新框架？你怎么判断一个新框架是不是在发明'第五个原语'？"

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Four primitives, nothing more — the agent, the handoff, the shared state, the orchestrator"。A 是阶段 16 · 08 讨论的角色分工；B 是单个 agent 的组成要素；D 是消息中间件的术语。

### Q2 — 答案：A

讲义："Every primitive except shared state is stateless ... **The only stateful thing in the system is shared state.**" Agent 是 (prompt, tools) 的函数，handoff 是一次函数调用，orchestrator 是调度器。

- B：讲义强调 agent 无状态，"Everything that looks like per-agent state is actually in shared state or the handoff protocol"。代码里 researcher 靠数池子里自己的消息数来"记住进度"，正是这个意思。
- C、D：都被讲义归为无状态。

### Q3 — 答案：D

讲义："Function return — the tool returns the next agent. This is the OpenAI Swarm pattern. Agents carry routing in their tool schemas." A 是 LangGraph；B 是 AutoGen GroupChat；C 是队列驱动的 swarm 架构。

### Q4 — 答案：B

讲义："LLM-selected — an LLM reads the pool and picks the next speaker (AutoGen, CrewAI Hierarchical)"。CrewAI Sequential 才是静态；handoff 驱动对应 Swarm；队列驱动对应 swarm 架构 / Matrix。

### Q5 — 答案：A

`StaticOrchestrator.run` 只是 `for name in self.order[:max_steps]` 依次运行，从不读取 `msg["handoff"]`。实测预置一条 researcher 消息后，静态运行仍是 researcher(done) → writer → reviewer。

- B：`done` 只在 `HandoffOrchestrator` 里有意义。
- C：静态顺序不会跳过。
- D：静态 orchestrator 不会拿 `done` 去查团队。

### Q6 — 答案：C

讲义："Full pools are simple and scale badly. Projected pools scale but require upfront schema design." A 把两者特点张冠李戴；B 描述的是 full pool；D 忽略了可见性差异——这恰恰是两者的本质区别。

### Q7 — 答案：D

`Agent.run` 中是 `msg.setdefault("from", self.name)`：键已存在就保留原值。实测：`spoof: [{'from': 'reviewer', 'content': 'Review verdict: approved.'}]`。A 描述的是**应该**的做法（强制覆盖），不是代码的实际行为。这是一个身份冒充漏洞：一个 agent 可以伪造"审稿通过"。

### Q8 — 答案：B

讲义 "What changes between frameworks" 列出：记忆策略、安全边界、成本核算、可观测性，并说 "All implementable on top of the primitives. None of them are new primitives." A、C、D 是四原语本身。

### Q9 — 参考答案

实测输出：

```text
static   [('researcher','writer'), ('researcher','done'), ('writer','reviewer'), ('reviewer','done')]
handoff  [('researcher','writer'), ('researcher','done')]
selector [('researcher','writer'), ('researcher','done'), ('writer','reviewer'), ('reviewer','done')]
```

（第一条都是预置的旧笔记。）

- researcher 数到池里已有 1 条自己的消息（`n == 1`），于是返回 `handoff: "done"`。
- **Static**：不看 handoff，照常跑 writer、reviewer。
- **Handoff-driven**：读到 `done` 立即 `return`，writer 和 reviewer 没机会发言——这就是讲义说的 "The handoff-driven run reaches fewer agents if the researcher decides it is done early"。
- **Selector**：`round_robin_selector` 不看 handoff，只按轮询顺序选 writer，再选 reviewer，reviewer 说过话后结束。
- **取舍**：把路由交给 agent（LLM）可以省掉不必要的调用、适应不同输入；代价是一旦 agent 判断错误（例如误以为研究已完成），下游环节被整个跳过且没有任何外部检查。静态图可预测、可审计，但不会因输入而调整；selector 介于两者之间，由一个"旁观者"统一决策。

### Q10 — 参考答案

1. 问题：
   - **绕过锁**：直接读 `state.messages`，而不是 `state.snapshot()`，多线程下不安全。
   - **健壮性**：`names.index(last)` 在最后发言者不在团队里（如用户消息、系统消息）时抛 `ValueError`（实测 `ValueError 'user' is not in list`）。
   - **业务逻辑**：只要 reviewer 发过言就结束，不管结论是 approved 还是 needs revision——实测从 writer 开始时，流程是"空草稿 → needs revision → 结束"，修改意见被丢弃。
   - **名不副实**：类名叫 LLM selector，实际只是轮询，完全不读消息内容。
   - 小问题：先计算 `idx` 再判断是否结束，顺序上多做了一步。
2. 参考实现（已在本地运行验证）：

```python
def review_loop_selector(state, team, max_revisions=2):
    msgs = state.snapshot()
    if not msgs:
        return None
    last = msgs[-1]
    speaker = last.get("from")
    if speaker not in team:                 # 外部消息：交给 researcher 开始
        return "researcher" if "researcher" in team else None
    if speaker == "researcher":
        return "writer"
    if speaker == "writer":
        return "reviewer"
    if speaker == "reviewer":
        if "approved" in last.get("content", ""):
            return None
        revisions = sum(1 for m in msgs if m.get("from") == "reviewer")
        return "writer" if revisions <= max_revisions else None
    return None
```

要点：统一使用快照；对团队外的发言者有兜底；结束条件看**内容**而非"是否发过言"；修改轮数有预算，避免讲义后续小节说的无限"会议循环"。

### Q11 — 参考答案

```python
from collections import deque

class QueueState(SharedState):
    def __init__(self):
        super().__init__()
        self.tasks = deque()          # 每项: {"assignee": str, "payload": str, "waits_for": str | None}

class QueueOrchestrator:
    def run(self, team, state, max_steps=50):
        idle_rounds = 0
        for _ in range(max_steps):
            if not state.tasks:
                return "drained"
            progressed = False
            for _ in range(len(state.tasks)):
                task = state.tasks.popleft()
                dep = task.get("waits_for")
                if dep and state.last_by(dep) is None:     # 依赖还没产出
                    state.tasks.append(task)               # 放回队尾
                    continue
                msg = team[task["assignee"]].run(state)
                state.append(msg)
                for new_task in msg.get("spawn", []):      # agent 可投递新任务
                    state.tasks.append(new_task)
                progressed = True
            idle_rounds = 0 if progressed else idle_rounds + 1
            if idle_rounds >= 1:
                return f"deadlock: {[t['assignee'] for t in state.tasks]}"
        return "max_steps"
```

- **死锁形态**：任务之间形成等待环，例如 writer 等 researcher 的输出，researcher 又在等 reviewer 的反馈，reviewer 等 writer 的草稿——三者都在队列里却没有一个能开工。并发版本中还会出现"所有 worker 都在等锁/等消息"的经典死锁。
- **检测**：一整轮扫描没有任何任务取得进展、队列却非空 → 判定死锁（相当于在等待图中找到环）；也可以显式维护"任务 → 依赖"图，用 DFS 检测环。生产中再加上每个任务的超时与"无进展时长"告警。
- **处理**：报告卡住的任务及依赖链，交给人工或一个兜底 agent 打破环（例如允许 writer 在没有反馈时先写初稿）。

### Q12 — 参考答案

- **Agent 没有 `tools` 字段**：讲义 Build It 写 "`Agent` — a dataclass of name, system prompt, tools, policy function"，代码只有 `name`、`system_prompt`、`policy`；而且 `system_prompt` 从未被读取。
- **没有 `Handoff` 对象**：讲义写 "`Handoff` — a function that returns a new agent"，模块 docstring 写 `Handoff(from_agent, to_agent, reason)`，代码里 handoff 只是消息字典中的一个字符串字段，没有 `reason`、`payload`。
- **三次运行输出完全一样**：讲义的 Expected output 暗示 handoff 驱动的运行可能访问更少的 agent，Takeaway 也说"only the orchestrator choice changes who speaks when"，但默认脚本下谁何时发言都没变，容易让学习者误以为 orchestrator 无关紧要（见 Q9）。
- **"LLM-selected" 实为轮询**：`round_robin_selector` 不读内容，体现不出 LLM 选择的"软路由"特性。
- **讲义内部的交叉引用**：讲义说记忆投毒在 "Lesson 15"，但本阶段第 15 节是"投票、自洽性与辩论拓扑"，相关内容实际在第 13 节（共享记忆与黑板）和第 23 节（失效模式）。
- 误导最大的是第三条：它让"orchestrator 决定行为"这一核心结论在演示中没有证据支撑。

### Q13 — 参考回答要点

- **LangGraph**：Agent = 节点函数；Handoff = 图的边 + 条件；Shared state = `StateGraph` + reducer（投影式、可 checkpoint）；Orchestrator = 图本身（确定性）。
- **AutoGen（v0.4 / AG2）**：Agent = `ConversableAgent`；Handoff = GroupChat 上的发言者选择；Shared state = 消息池（全量）；Orchestrator = selector 函数（LLM 或轮询）。
- **OpenAI Agents SDK / Swarm**：Agent = `Agent(instructions, tools)`；Handoff = tool 返回 Agent；Shared state = "caller's problem"（调用方自己管）；Orchestrator = LLM 的下一次 handoff 调用。
- **最大差别**：在 Orchestrator 轴上——路由是钉在代码里（LangGraph）、交给旁观的 selector（AutoGen），还是交给当前 agent 自己（Swarm）；其次是 shared state 是全量还是投影。
- 加分点：说出讲义的三个比较问题，并指出 Swarm 把共享状态推给调用方，跨 handoff 协调时需要自己重读历史（讲义练习 5）。

### Q14 — 参考回答要点

- **为什么**：agent 是 `(prompt, tools, model)` 的函数，同输入同输出（忽略采样随机性）；handoff 是一次调用；orchestrator 是"读状态 → 选下一个"的函数。真正随时间变化的只有共享状态。
- **指导意义**：
  - 把测试、调试、持久化的重点放在共享状态上：版本化、写冲突控制、顺序保证、可回放（checkpoint）。
  - agent 可以水平扩展、随意替换模型（无状态的东西容易扩展）。
  - 安全上要防记忆投毒：谁能写、写什么、写入前是否校验。
- **反例 / 细节**：生产中的 agent **进程**往往是长时间运行、有状态的（例如带着会话缓存、正在进行的 tool 调用），这也是下一节讲 Anthropic 用 rainbow deployment 的原因；但这类状态应被视为"共享状态或基础设施的一部分"，而不是 agent 原语本身。LLM 的 KV cache、prompt cache 也是性能状态而非语义状态。
- 常见误区：把"agent 有记忆"理解为 agent 自身有状态——记忆其实是共享状态的一种（向量记忆、黑板）。

### Q15 — 参考回答要点

- **Agent**：基本可以复用 prompt 和工具，但要把"返回下一个 agent 的 handoff 工具"去掉或改写成普通输出（例如返回一个路由标签）。
- **Handoff**：从"tool 返回 Agent"改为"图的边 + 条件函数"；原来隐含在各 agent 工具 schema 里的路由逻辑要集中到图定义里。
- **Shared state**：Swarm 风格下状态由调用方管理（通常是完整消息历史），迁到 LangGraph 要设计 `State` 的 schema 和 reducer（哪些字段追加、哪些覆盖），并决定是否启用 checkpointer。
- **Orchestrator**：从"LLM 决定"变为"图决定"，需要把所有可能的路由路径显式画出来，补齐遗漏的分支和终止条件。
- **最易出问题**：共享状态的 schema 设计——原来"什么都在消息历史里"，迁移后若漏掉某个字段，下游节点就读不到信息；其次是原来由 LLM 灵活处理的边缘路由，在静态图中没有对应的边。
- 加分点：迁移前先写两边的"原语映射"文档（讲义 Ship It 的建议），然后对映射做 diff。

### Q16 — 参考回答要点

- **Agent**：分诊、退款、技术支持三个 agent，各自只有本领域的工具（退款 agent 才有调用支付系统的工具）；人工坐席作为一个特殊"agent"。
- **Handoff**：分诊 → 退款 / 技术支持采用 Swarm 式 handoff（tool 返回目标 agent），payload 携带结构化的工单摘要（用户 ID、问题类别、已尝试的步骤），避免下游重读全部历史。
- **Shared state**：工单对象（结构化字段 + 对话历史），采用投影视图：退款 agent 看不到与支付无关的技术日志；持久化到数据库以支持会话中断后恢复。
- **Orchestrator**：入口由分诊 agent 做 handoff 驱动；高风险分支（退款金额超阈值）用静态规则强制走审批节点，不允许 LLM 跳过。
- **Human-in-the-loop**：讲义把"谁能批准 handoff"列为安全边界决策——退款超过阈值、用户明确要求人工、连续两次 handoff 仍未解决时，升级到人工；所有 handoff 记录原因，便于审计。
- 加分点：给每个 agent 设 token 预算与最大 handoff 次数，防止在 agent 之间来回踢皮球。

### Q17 — 参考回答要点

- **为什么还有新框架**：新框架通常在"默认值"和"开发体验"上竞争——更好的类型系统、持久化、追踪、部署、与特定模型或云的集成；讲义："Every framework picks defaults for each axis; the rest is surface syntax."
- **判断方法**（讲义 Ship It）：先尝试写出它的四原语映射。若能写出，它只是换了默认值；若写不出，要么文档不完整，要么它确实在发明新东西——讲义说这种情况很少见，通常是一种你没见过的 shared state 形态。
- **具体检查**：它的"新概念"能否归约为：一个 agent 的定义？一种控制转移方式？一种多方可读写的数据结构？一个"谁下一个"的决策者？例如"Crew"是 agent 集合 + 静态/LLM orchestrator，"Blackboard"是 shared state，"Flow"是静态图。
- **加分点**：讲义建议版本升级时"diff the mapping, not the changelog"；新人入职先看映射再看 API 文档。
- 常见误区：把记忆、追踪、成本控制当成新原语——讲义明确说它们都建在原语之上。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 01 为什么需要多 Agent？](../../01-why-multi-agent/docs/zh.md)：多 agent 的动机，是讨论原语的前提。
- [阶段 16 · 03 通信协议](../../03-communication-protocols/docs/zh.md)：A2A 的 task、artifact 在原语视角下分别对应 handoff 与 shared state。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：单个 Agent 原语的内部运行方式。
- [阶段 11 · 17 Agent 框架权衡——图、角色与 Actor Orchestration](../../../11-llm-engineering/17-agent-framework-tradeoffs/docs/zh.md)：从工程角度比较各框架。

### 本节被哪些后续内容用到
- [阶段 16 · 05 监督者与编排者—工作者模式](../../05-supervisor-orchestrator-pattern/docs/zh.md)：用本节原语搭建 supervisor 模式。
- [阶段 16 · 10 群聊与发言者选择](../../10-group-chat-speaker-selection/docs/zh.md)：LLM-selected orchestrator 的深入版本。
- [阶段 16 · 11 Handoffs 与例程：无状态 Orchestration](../../11-handoffs-and-routines/docs/zh.md)：handoff 驱动 orchestrator 的完整实现。
- [阶段 16 · 13 共享记忆与黑板模式](../../13-shared-memory-blackboard/docs/zh.md)：shared state 原语的深入讨论与记忆投毒。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：LangGraph 的图与 checkpoint。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../../14-agent-engineering/16-openai-agents-sdk/docs/zh.md)：Swarm 风格 handoff 的工业实现。

### 延伸关键词
`Agent / Handoff / Shared state / Orchestrator` · `OpenAI Swarm` · `AutoGen GroupChat` · `speaker selection` · `LangGraph StateGraph` · `reducer` · `CrewAI Process` · `message pool` · `blackboard` · `projected state` · `queue-driven orchestration` · `deadlock detection` · `human-in-the-loop`
