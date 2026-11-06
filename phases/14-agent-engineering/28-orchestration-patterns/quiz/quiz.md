# 测验 · Orchestration 模式：监督者、Swarm 与层级结构（Orchestration Patterns: Supervisor, Swarm, Hierarchical）

> **阶段 14 · Agent 工程 · 第 28 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四种反复出现的编排模式 | supervisor-worker、swarm / peer-to-peer、hierarchical、debate |
| 2 | Supervisor-worker | 中心路由 LLM 分派给专家；决定"回到自己 / 交给专家 / 终止"；专家之间不直接通信，所有路由经过 supervisor |
| 3 | 2026 LangChain 建议 | 用**直接的 tool call** 实现 supervision，而不是 `create_supervisor` 库，以便精细控制每个专家看到的上下文（context engineering） |
| 4 | Swarm | 通过共享工具面直接 handoff，没有中心路由；跳数更少、延迟更低，但没有单点控制、更难推理 |
| 5 | Hierarchical | supervisor 管 sub-supervisor 再管 worker；LangGraph 用嵌套子图、CrewAI 用嵌套 crew；**只有当单个 supervisor 的上下文预算装不下所有专家描述时**才需要 |
| 6 | Debate | 并行提议 + 迭代交叉批评（Lesson 25）；严格说更像"验证"而非编排，但在框架里作为一种拓扑出现 |
| 7 | CrewAI 的 Flow vs Crew | Flow：确定性、事件驱动，生产推荐起点；Crew：自主的基于角色协作；与四种模式正交 |
| 8 | Anthropic 的原则与决策顺序 | "It's about building the right system for your needs"：单 Agent + workflow 模式 → supervisor（2–4 个专家）→ swarm（延迟优先）→ hierarchical（上下文预算不够时）→ debate（准确率重于成本） |
| 9 | 三种典型错误 | 拓扑先行（先说"要多 Agent"再找问题）、swarm 中来回弹跳（A→B→A→B，用 hop counter）、伪层级（为"企业级"堆三层，实际只有两个团队，应压平） |
| 10 | 本节代码的成本口径 | 3 个任务时 ops：supervisor 6、swarm 5、hierarchical 9、debate 15；分别是 2N、N+（入口不匹配的任务数）、3N、(k+2)N |

### 核心技能（能动手做到）

- [ ] 给定一个业务场景，按 Anthropic 的决策顺序选出最小够用的拓扑，并说出"为什么不选另外几种"
- [ ] 读懂本节四个函数，手算任意任务列表下每种模式的 ops 数
- [ ] 为 swarm 实现带"超限升级"的 hop counter，并构造 A→B→A 弹跳用例验证（讲义练习 2）
- [ ] 把本节的"debate"改成真正带交叉批评轮次的辩论，并设置轮数上限
- [ ] 用 tool call 的方式实现 supervisor，控制每个专家只看到它需要的上下文
- [ ] 判断一个层级结构是不是"伪层级"，并给出压平方案

---

## 二、基础自测（选择题）

**Q1.** "中心 LLM 负责把请求分派给专家；专家之间不直接通信，所有路由都经过它"——这描述的是哪种模式？

- A. Swarm / peer-to-peer
- B. Debate
- C. Supervisor-worker
- D. CrewAI Crew 模式中的自由协作

**Q2.** 讲义提到的 2026 年 LangChain 关于 supervision 的建议是：

- A. 用直接的 tool call 实现 supervision，而不是 `create_supervisor`，以便精细控制每个专家看到的上下文
- B. 一律使用 `create_supervisor`，因为它是官方推荐的库
- C. 放弃 supervisor，全部改用 swarm
- D. 每个专家都应该看到完整的对话历史

**Q3.** 讲义认为什么时候才需要 hierarchical（层级）编排？

- A. 只要是"企业级"项目
- B. 专家数量超过 2 个时
- C. 需要最低延迟时
- D. 单个 supervisor 的上下文预算装不下所有专家的描述时

**Q4.** Swarm 中出现 A → B → A → B 的来回弹跳，讲义推荐的手段是：

- A. 增加更多专家
- B. 加 hop counter（跳数计数器），超过 N 次 handoff 就拒绝
- C. 降低模型 temperature
- D. 改成 debate

**Q5.** 本节代码中，任务数为 N、辩手数为 3 时，`debate` 返回的 ops 是多少？

- A. 5N
- B. 3N
- C. 4N
- D. 2N + 3

**Q6.** 按讲义的决策顺序，一个新项目应该从哪里开始？

- A. 先上 hierarchical，以便日后扩展
- B. 先上 swarm，因为延迟最低
- C. 单个 Agent + workflow 模式（Lesson 12），不够用时再加拓扑
- D. 先上 debate，因为准确率最高

**Q7.** 关于 CrewAI 的 Flow 与 Crew，下列说法与讲义一致的是：

- A. Crew 是确定性的事件驱动模式，推荐作为生产起点
- B. Flow 与 Crew 是同一个东西的两个名字
- C. Flow 只能实现 debate 拓扑
- D. Flow 是确定性、事件驱动的自动化，推荐作为生产起点；Crew 是自主的基于角色协作

**Q8.** 把本节 `main` 中的三个任务全部换成 `"the CLI crashes on ctrl-c"`（都是 bug），supervisor-worker 与 swarm 的 ops 分别是：

- A. 6 与 3
- B. 6 与 6
- C. 3 与 6
- D. 6 与 9

---

## 三、动手 / 代码题

**Q9.** 阅读 swarm 实现：

```python
def swarm(tasks: list[str]) -> tuple[list[str], int]:
    trace: list[str] = []
    ops = 0
    for task in tasks:
        current = list(SPECIALISTS)[0]
        hops = 0
        while hops < 3:
            ops += 1
            label = classify(task)
            if current == label:
                trace.append(f"swarm[{current}]: {SPECIALISTS[current](task)}")
                break
            trace.append(f"swarm[{current}] handoff -> {label}")
            current = label
            hops += 1
    return trace, ops
```

1. 在本节的演示数据下，hop counter 有没有真正起过作用？为什么？
2. 如果让 `classify` 依次返回 `bug, refund, bug, refund, ...`（模拟 A→B→A 弹跳），`swarm(["weird ticket"])` 的 trace 和 ops 是什么？任务最终被谁处理了？
3. 指出其中的缺陷并改写：超过跳数时要有明确的结果；同时检测"回到已访问过的 Agent"。

**Q10.** 阅读 `debate`：

```python
        for debater in ("alpha", "beta", "gamma"):
            ops += 1
            label = classify(task)
            proposals.append(label)
            trace.append(f"{debater} proposes {label}")
        ops += 1
        convergent = Counter(proposals).most_common(1)[0][0]
```

1. 讲义对 debate 的定义是"parallel proposers + iterative cross-critique"。这段代码实现的是什么？缺了什么？
2. 如果三位辩手分别提出 `bug`、`refund`、`sales`，`convergent` 会是什么？为什么？这样的平局处理合理吗？
3. 给出一个带"交叉批评轮次 + 轮数上限 + 平局升级"的改写思路（伪代码即可）。

**Q11.** 关于 `hierarchical`：

```python
        top_label = "customer_ops" if classify(task) != "sales" else "commercial"
        ...
        sub_label = classify(task)
```

1. 画出这段代码隐含的层级树。对照 outputs 中 skill 的 hard reject "Hierarchical that bottoms out at 1 specialist per branch. Flatten."，这个演示有什么问题？
2. 每个任务 3 个 op，其中两次分类调用的是同一个函数。在真实系统中，两层路由各自的价值应该是什么？
3. 讲义练习 3：12 个专家的领域，假设每个专家描述约 400 token，supervisor 的路由 prompt 预算为 3,000 token（其余留给对话与输出）。扁平 supervisor 是否装得下？如果拆成 3 个 sub-supervisor，每层的路由 prompt 各需要多少？

**Q12.** 阅读路由函数：

```python
def classify(text: str) -> str:
    t = text.lower()
    if "refund" in t:
        return "refund"
    if "crash" in t or "error" in t or "bug" in t:
        return "bug"
    if "pricing" in t or "quote" in t:
        return "sales"
    return "sales"
```

1. `classify("how do I reset my password")` 与 `classify("refund for the crash")` 分别返回什么？各说明什么问题？
2. 倒数第二个 `if` 有什么问题？
3. 讲义推荐"tool-call-based supervision"。请用伪代码写一个 supervisor：把每个专家注册成一个工具，并在调用时只传递该专家需要的上下文；同时为"无法识别"的请求提供兜底路由。

---

## 四、面试高频题

**Q13.**（基础必考）说说 supervisor-worker、swarm、hierarchical、debate 四种多 Agent 编排模式的区别，以及各自适用的场景。

**Q14.**（原理深挖）为什么 Anthropic 和很多团队都建议"先用单 Agent + workflow，再考虑多 Agent"？多 Agent 引入了哪些额外成本？

**Q15.**（工程实践）你负责一个客服系统，需要在退款、技术故障、销售报价三类请求之间分派。你会选哪种拓扑？请给出实现要点和需要的可观测性/防护措施。

**Q16.**（场景设计）一个已上线的 swarm 系统中，部分请求在两个 Agent 之间来回转了十几次才结束，延迟和成本都飙升。你会如何排查和修复？

**Q17.**（追问型）如果业务方说"我们是企业级系统，所以要做三层层级架构"，你会怎么回应？什么证据能说明真的需要层级？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："A central routing LLM dispatches to specialist agents... Specialists do not talk to each other; all routing goes through the supervisor." A 恰好相反（没有中心路由）；B 是并行提议 + 批评；D 的 Crew 模式是"autonomous role-based collaboration"，讲义说它"typically supervisor with an LLM router"，但题干描述的模式本身是 supervisor-worker。

### Q2 — 答案：A

讲义："do supervision through direct tool calls rather than `create_supervisor`. Gives finer context engineering control — you decide exactly what each specialist sees." B 与建议相反；C 不是建议内容；D 恰恰是精细 context engineering 要避免的——专家只应看到完成其任务所需的信息。

### Q3 — 答案：D

讲义："When you need it: when a single supervisor's context budget cannot hold descriptions of all specialists." 决策顺序里也写着"Hierarchical — only when supervisor context budget fails"。A 正是讲义批评的 "Fake hierarchy"；B 太早（2–4 个专家用 supervisor 即可）；C 对应的是 swarm。

### Q4 — 答案：B

讲义："Bouncing handoffs in swarm. A -> B -> A -> B. Use hop counters." skill 也把"Swarm without hop counter"列为 hard reject（"Bouncing is a certainty"）。A、C、D 都不能直接阻止弹跳。注意：hop counter 只是止损，超限后的处理（升级、兜底）同样重要（见 Q9）。

### Q5 — 答案：A

每个任务：3 位辩手各 1 op + 汇总 1 op + 执行专家 1 op = 5 op，N 个任务共 5N。实测 N = 1、3、10 时分别为 5、15、50。一般地，k 位辩手时为 (k+2)N。注意"汇总"只是 `Counter` 多数投票，并不是 LLM 调用，代码依然把它算作 1 个 op——成本口径并不严格（见讲解第 3 节）。

### Q6 — 答案：C

讲义决策顺序第 1 条："Single agent + workflow patterns (Lesson 12) — start here." Anthropic 原话："Success in the LLM space isn't about building the most sophisticated system. It's about building the right system for your needs." A 是伪层级；B、D 都是在没有证据时就选择更复杂的拓扑。

### Q7 — 答案：D

讲义："Flow for deterministic event-driven automation (recommended starting point for production). Crew for autonomous role-based collaboration." A 把两者说反了；B 错；C 错，讲义说 Flow 通常对应 supervisor 或 hierarchical 拓扑。

### Q8 — 答案：B

已实测：`[6, 6, 9, 15]`。supervisor 恒为每任务 2 op → 6。swarm 的入口 Agent 固定为 `list(SPECIALISTS)[0]`，即 `refund`；bug 任务需要先 handoff（1 op）再处理（1 op），每任务 2 op → 6。所以"swarm 最短"只在任务恰好命中入口 Agent 时成立；演示中 swarm 的 5 来自第一个任务正好是 refund（1 op）。

### Q9 — 参考答案

1. **没有起作用**。`classify` 是确定性的、与"当前是哪个 Agent"无关，第一次 handoff 就会直接到达正确的专家，第二次循环必然 `current == label` 并 `break`。演示中最多只有 1 次 handoff，`hops < 3` 的上限从未被触及。
2. 实测结果：

```text
['swarm[refund] handoff -> bug', 'swarm[bug] handoff -> refund', 'swarm[refund] handoff -> bug'] 3
```

   ops = 3。三次 handoff 之后 `hops == 3`，`while` 循环退出——**没有任何 Agent 处理这个任务，trace 里也没有任何"放弃/升级"的记录**，任务被静默丢弃。
3. 缺陷：①超限后无结果、无告警，比无限循环更隐蔽；②只计跳数，不识别"回到已访问 Agent"这种明确的弹跳信号；③入口 Agent 固定。改写：

```python
def swarm(tasks, max_hops=3, fallback="human_queue"):
    trace, ops = [], 0
    for task in tasks:
        current, visited = list(SPECIALISTS)[0], []
        while True:
            ops += 1
            label = classify(task)
            if label == current:
                trace.append(f"swarm[{current}]: {SPECIALISTS[current](task)}")
                break
            visited.append(current)
            if label in visited or len(visited) >= max_hops:   # 弹跳或超限
                trace.append(f"swarm[{current}] ESCALATE -> {fallback} "
                             f"(path={visited + [label]})")
                break
            trace.append(f"swarm[{current}] handoff -> {label}")
            current = label
    return trace, ops
```

   在弹跳用例中，第二次 handoff 目标 `refund` 已在 `visited` 中，立即升级到人工队列，并把完整路径写进 trace，便于排查。生产中这一事件还应作为 span/指标上报（skill："Observability hooks per handoff"）。

### Q10 — 参考答案

1. 实现的是**多数投票**（类似 self-consistency）：三个"辩手"各自独立调用同一个确定性的 `classify`，结果必然一致，然后取众数。缺少的是讲义所说的"iterative cross-critique"：辩手看不到彼此的提议，没有批评与修改的轮次，也没有轮数上限（skill："round cap on debate"）。因为三个辩手完全相同，这里的多数投票也不会带来任何准确率提升，只是把成本放大到每任务 5 op。
2. `Counter(["bug","refund","sales"]).most_common(1)` 实测返回 `[('bug', 1)]`：三者计数都为 1，`most_common` 在并列时保持**插入顺序**，所以第一个发言的 alpha 胜出。这相当于"平局时听第一个人的"，结果取决于发言顺序，并不合理。
3. 改写思路：

```python
def debate(task, debaters, max_rounds=2):
    proposals = {d: d.propose(task) for d in debaters}            # 并行提议
    for r in range(max_rounds):
        if len(set(proposals.values())) == 1:                     # 已收敛
            break
        others = lambda d: {k: v for k, v in proposals.items() if k != d}
        proposals = {d: d.revise(task, proposals[d], critique=others(d))
                     for d in debaters}                           # 交叉批评后修订
    votes = Counter(proposals.values()).most_common()
    if len(votes) > 1 and votes[0][1] == votes[1][1]:             # 平局
        return judge.decide(task, proposals)                      # 或升级给人
    return votes[0][0]
```

   要点：辩手要有差异（不同模型/提示/温度）才有意义；轮数上限防止无限争论；平局交给独立 judge 或人工。

### Q11 — 参考答案

1. 层级树：

```text
top
├── customer_ops
│   ├── refund
│   └── bug
└── commercial
    └── sales
```

   `commercial` 分支下只有一个专家 `sales`——正是 skill 所说"bottoms out at 1 specialist per branch"，应当压平。整个系统只有 3 个专家，按讲义 2–4 个专家用 supervisor 即可，这个 hierarchical 是为了演示而构造的"伪层级"（讲义："Fake hierarchy... Collapse"）。代价是每任务 3 op（实测 3 个任务共 9 op），比 supervisor 多 50%。
2. 真实系统中两层路由的分工：顶层只需要知道"部门"级别的粗粒度描述（例如"客户运营：退款、故障、账户"），负责粗分；子 supervisor 掌握本部门所有专家的详细描述与工具说明，负责细分。两层各自只加载自己需要的描述，这样才能突破单个上下文的预算——如果两层用的是同一个分类器、同一份信息，就只是多付了一次调用。
3. 计算：
   - 扁平：12 × 400 = 4,800 token > 3,000 token，装不下（这还没算专家工具 schema）。
   - 分 3 组、每组 4 个专家：顶层路由 prompt 只需 3 个部门描述，假设每个也约 400 token，共 1,200 token；每个 sub-supervisor 需要 4 × 400 = 1,600 token。两层都在 3,000 token 以内。
   - 代价：每个请求多一次路由调用（延迟、成本、多一个出错点）。这就是讲义所说"scales to large agent populations at the cost of operational complexity"。也可以先考虑让 supervisor 按需检索专家描述（工具检索）来避免加层。

### Q12 — 参考答案

1. 实测：`classify("how do I reset my password")` → `"sales"`；`classify("refund for the crash")` → `"refund"`。
   - 前者：任何无法识别的请求都**默认**落到 sales——账户问题被当成销售线索，用户收到一份报价。正确做法是返回 `"unknown"` 并走兜底（澄清问题或人工）。
   - 后者：多意图请求只取第一个命中的意图（规则顺序决定优先级），"因为崩溃要退款"其实需要 bug 与 refund 两个专家协作。此外 `"error" in t` 是子串匹配，`"terrors"` 也会被判为 bug（已实测）。
2. `if "pricing" in t or "quote" in t: return "sales"` 之后紧跟 `return "sales"`，这个判断是**冗余**的——不管命不命中都返回 sales。它看起来像有规则，实际上把"兜底"伪装成了"识别"。
3. 伪代码（tool-call-based supervision）：

```python
TOOLS = [
    {"name": "refund_agent", "description": "处理退款，需要发票号与金额",
     "parameters": {"invoice_id": "str", "reason": "str"}},
    {"name": "bug_agent", "description": "记录技术故障，需要产品、复现步骤",
     "parameters": {"product": "str", "steps": "str"}},
    {"name": "sales_agent", "description": "报价与套餐咨询",
     "parameters": {"product": "str", "seats": "int"}},
    {"name": "escalate_to_human", "description": "无法判断或多意图时使用",
     "parameters": {"summary": "str"}},
]

def supervisor(user_msg):
    call = llm(messages=[system_prompt, user_msg], tools=TOOLS)   # supervisor 只负责选工具 + 抽参数
    if call is None:
        return llm_reply                                          # 自己回答（loop back to self）
    agent = AGENTS[call.name]
    return agent.run(**call.args)            # 专家只看到抽取出的参数，而不是完整对话
```

   要点：每个专家是一个工具；supervisor 通过工具参数决定"专家看到什么"（这就是讲义说的"finer context engineering control"）；`escalate_to_human` 作为显式兜底，避免默认落入某个专家。

### Q13 — 参考回答要点

| 模式 | 结构 | 优点 | 缺点 | 适用 |
|------|------|------|------|------|
| Supervisor-worker | 中心路由 + 专家，专家互不通信 | 单点控制、易调试、易审计 | 每次多一跳、supervisor 是瓶颈 | 2–4 个职责清晰的专家 |
| Swarm | 专家之间直接 handoff，无中心 | 跳数少、延迟低 | 难推理、可能弹跳 | 延迟优先且专家边界清楚 |
| Hierarchical | supervisor 套 sub-supervisor | 支撑大量专家 | 层数多、延迟和运维复杂度高 | 单个 supervisor 上下文装不下 |
| Debate | 并行提议 + 交叉批评 | 准确率提升 | 成本最高 | 准确率重于成本 |

- 框架对应：LangGraph（supervisor、swarm、嵌套子图）、OpenAI Agents SDK handoffs、CrewAI Hierarchical Process / Flow / Crew。
- 加分点：说出本节演示的成本排序（3 任务时 6/5/9/15 ops）以及它对入口 Agent 的依赖（Q8）。

### Q14 — 参考回答要点

- 讲义引用 Anthropic："Success in the LLM space isn't about building the most sophisticated system. It's about building the right system for your needs."
- **多 Agent 的额外成本**：
  - 调用次数与延迟增加（路由、handoff、汇总都是额外推理）；
  - 上下文在 Agent 之间传递时会丢信息或被误解；
  - 失效模式增多：弹跳、级联错误、职责不清（见 Lesson 26 的 MASFT）；
  - 调试与可观测性更难：一个请求的 trace 分散在多个 Agent 中；
  - 安全面扩大：Agent 之间传递的内容也可能携带注入（Lesson 27）。
- **单 Agent + workflow 的优势**：prompt chaining、routing、parallelization、orchestrator-workers、evaluator-optimizer 等模式足以覆盖大部分需求，确定性更高。
- 常见误区：skill 的 hard reject——"Calling 3 LLM calls in sequence 'multi-agent.' That's a prompt chain."

### Q15 — 参考回答要点

- **选择**：3 个职责清晰的专家 → supervisor-worker；若有合规/审计需求，skill 明确拒绝 swarm，选 supervisor 或 hierarchical。
- **实现要点**：
  - 用 tool-call-based supervision：三个专家 + `escalate_to_human` 作为工具；
  - supervisor 只做路由和参数抽取，专家只拿到需要的字段（发票号、产品、复现步骤）；
  - 多意图请求（"崩溃了要退款"）允许 supervisor 依次调用多个专家；
  - 退款等有副作用的动作需要额度上限和人工确认。
- **可观测性**：每次路由、每次专家调用都记 OTel GenAI span（Lesson 23），记录路由决策与理由；统计路由分布、兜底率、误路由率。
- **防护**：最大循环次数；supervisor 的路由准确率做成离线评测（Lesson 30）；无法识别时显式兜底，而不是像本节 `classify` 那样默认落到 sales。

### Q16 — 参考回答要点

- **排查**：
  - 从 trace 中提取 handoff 路径，统计弹跳对（A↔B）出现频率与对应请求类型；
  - 检查两个 Agent 的职责描述是否重叠或互相指向（"这不是我的事，去找 B"）；
  - 检查 handoff 时传递的上下文是否丢失了关键信息，导致接收方判断错误。
- **止血**：加 hop counter 与已访问集合，超限立即升级到人工或默认处理者，并上报指标（Q9）。
- **根治**：
  - 澄清职责边界，必要时合并两个 Agent；
  - handoff 时附带结构化的"交接摘要"；
  - 对边界模糊的请求类型，改由一个 supervisor 统一决策——这正是讲义说的 swarm "harder to reason about" 的代价。
- 加分点：把弹跳用例加入回归评测集，防止修复后复发。

### Q17 — 参考回答要点

- 引用讲义："Fake hierarchy. Three layers because 'enterprise'; two actual teams. Collapse."
- **需要层级的证据**：
  - 专家数量多（如 10+），单个 supervisor 的路由 prompt 装不下所有专家描述，或路由准确率因描述过多明显下降（可做实验：逐步增加专家数量，观察路由准确率曲线）；
  - 自然存在的组织/领域分区，每个分区内部有多个专家；
  - 不同分区有不同的权限或合规边界。
- **反证**：任何一个分支只有 1 个专家（skill："bottoms out at 1 specialist per branch. Flatten"）；层数多于实际团队数；每层路由使用相同的信息。
- **回应方式**：先用 supervisor 上线，同时监控路由准确率与上下文占用，达到阈值再加层；把"企业级"的诉求落到审计、权限、可观测性上，而不是层数上。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：决策顺序的第一步——单 Agent + workflow 模式。
- [阶段 14 · 25 多 Agent 辩论与协作](../../25-multi-agent-debate/docs/zh.md)：debate 拓扑的完整讲解。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：LangGraph 中的 supervisor 与嵌套子图。
- [阶段 14 · 15 基于角色的 Agent 团队：角色、任务与流程](../../15-crewai-role-based-crews/docs/zh.md)：CrewAI 的 Crew 与 Flow。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)：handoffs-as-tools。

### 本节被哪些后续内容用到
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../29-production-runtimes/docs/zh.md)：选定拓扑后，如何在生产中运行它。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：用评测比较不同拓扑的准确率与成本。
- [阶段 16 · 05 监督者与编排者—工作者模式](../../../16-multi-agent-and-swarms/05-supervisor-orchestrator-pattern/docs/zh.md)：supervisor 模式深入。
- [阶段 16 · 06 层级架构及其失效模式](../../../16-multi-agent-and-swarms/06-hierarchical-architecture/docs/zh.md)：层级结构的失效分析。
- [阶段 16 · 09 并行、Swarm 与网络化架构](../../../16-multi-agent-and-swarms/09-parallel-swarm-networks/docs/zh.md)：swarm 拓扑深入。
- [阶段 16 · 11 Handoffs 与例程：无状态 Orchestration](../../../16-multi-agent-and-swarms/11-handoffs-and-routines/docs/zh.md)：handoff 机制。
- [阶段 11 · 17 Agent 框架权衡——图、角色与 Actor Orchestration](../../../11-llm-engineering/17-agent-framework-tradeoffs/docs/zh.md)：框架层面的取舍。
- [阶段 19 · 10 多 Agent 软件工程团队](../../../19-capstone-projects/10-multi-agent-software-team/docs/zh.md)：综合项目中的多 Agent 编排。

### 延伸关键词
`supervisor-worker` · `swarm` · `handoff` · `hierarchical / nested subgraph` · `debate` · `tool-call-based supervision` · `context engineering` · `hop counter` · `fake hierarchy` · `CrewAI Flow / Crew` · `create_supervisor` · `Building Effective Agents`
