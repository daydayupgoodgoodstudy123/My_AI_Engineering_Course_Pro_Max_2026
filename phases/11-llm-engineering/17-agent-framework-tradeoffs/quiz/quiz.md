# 测验 · Agent 框架权衡——图、角色与 Actor Orchestration（Agent Framework Tradeoffs — Graph, Role, and Actor Orchestration）

> **阶段 11 · LLM 工程 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 选框架的核心原则 | 不是"选最好的框架"，而是让框架的**核心抽象**与问题的**形状**匹配；否则抽象会泄漏，胶水代码要写两遍 |
| 2 | 四种核心抽象 | LangGraph = 状态图（白板上画图）；CrewAI = 角色团队（画组织架构）；AutoGen = 多 agent 对话（画聊天）；Agno = 带工具的单 agent（画一个盒子） |
| 3 | 状态问题 | LangGraph：类型化状态 + reducer + checkpointer；CrewAI：任务间通过 `context` 字符串或 `output_pydantic` 传递，无开箱即用的持久化；AutoGen：状态就是聊天记录；Agno：内置 session 存储，但不是图级 checkpointer |
| 4 | 分支由谁决定 | LangGraph：开发者（条件边）；CrewAI：hierarchical 模式下 manager LLM；AutoGen：对话涌现（默认 LLM 选下一个发言者）；Agno：agent 选择调用哪个工具 |
| 5 | 显式路由 vs LLM 路由 | LLM 选路由每一轮都要花 token，灵活但贵、难审计；显式路由（Python 函数/静态边）便宜、可审计 |
| 6 | 开销排序 | 讲义："Agno ≈ LangGraph < CrewAI ≈ AutoGen"，差距主要来自框架额外做了多少次 LLM 路由 |
| 7 | 可观测性 | 四者都能接 OpenTelemetry；LangGraph 每个节点转换是一个 span，AutoGen 粒度是每条 agent 消息 |
| 8 | 不用框架 | 讲义："no framework is cheaper than no framework"；两次 LLM 调用加一个工具，写 30 行纯 Python 即可 |
| 9 | 决策矩阵 | 带审批的长流程 DAG → LangGraph；角色分明的写作流水线 → CrewAI（或 LangGraph 子图）；提议者–批评者对话 → AutoGen；单 agent + 会话记忆 → Agno；大规模并行 fanout + reducer → LangGraph + `Send`；快速原型 → 纯 Python |
| 10 | 规则引擎的局限 | `main.py` 把上述权衡编码成**有序的 if 链**：信号冲突时由判断顺序决定结果，且对 LangGraph 有明显偏向 |

### 核心技能（能动手做到）

- [ ] 拿到一个任务描述，先画出它的"形状"（图 / 组织架构 / 聊天 / 单盒子），再用一句话说明为什么选某个框架
- [ ] 读懂 `recommend()` 的判断顺序，手算任意 `Problem` 的推荐结果
- [ ] 找出决策树中"条件被忽略"与"顺序决定结果"的情形，并补充测试用例
- [ ] 估算 LLM 路由的 token 成本，判断何时应改为显式路由
- [ ] 让交互模式对非法输入（非数字、EOF）保持健壮
- [ ] 为团队设计一个"同一任务、多框架原型"的对比实验（成本、代码行数、可恢复性、人工审批能力）

---

## 二、基础自测（选择题）

**Q1.** 讲义说"框架的核心抽象就是你在白板上推销架构时画的那个东西"。"画一张组织架构图：每个角色有职位描述，由经理分派任务"对应的是哪个框架？

- A. LangGraph
- B. AutoGen
- C. CrewAI
- D. Agno

**Q2.** 在 AutoGen 中，多 agent 对话的分支（下一步由谁行动）默认是怎样决定的？

- A. 由对话涌现：`GroupChatManager` 选择下一个发言者，默认由 LLM 决定；也可以手写 `speaker_selection_method`
- B. 由开发者在编译期写好的条件边决定
- C. 由一个固定的任务列表按顺序执行
- D. 由 agent 选择调用哪个工具决定

**Q3.** 讲义给出的框架额外开销排序（从低到高）以及主要原因是：

- A. LangGraph < Agno < AutoGen < CrewAI，因为图编译很耗时
- B. 四者开销相同，差别只在于代码风格
- C. CrewAI ≈ AutoGen < Agno ≈ LangGraph，因为类型化状态的序列化很贵
- D. Agno ≈ LangGraph < CrewAI ≈ AutoGen，主要差别在于框架额外做了多少次由 LLM 决定的路由

**Q4.** 关于各框架的"状态"能力，下列说法与讲义一致的是：

- A. CrewAI 默认为每个 crew 提供持久化存储，进程重启后可自动恢复
- B. Agno 通过 `storage=` 挂载 SQLite/Postgres 等驱动，会话和用户记忆自动持久化，但它是 session store，不是完整的图级 checkpointer
- C. AutoGen 默认持久化任意工作流状态
- D. LangGraph 没有 checkpointer，需要自己实现恢复

**Q5.** 对 `main.py` 中的 `recommend()`，输入 `Problem(has_roles=True, has_dialogue=True, total_llm_calls=5)`，返回的框架是：

- A. `crewai`
- B. `autogen`
- C. `langgraph`
- D. `plain python`

**Q6.** 输入 `Problem(has_typed_state=True, needs_session_memory=True, total_llm_calls=2)`，`recommend()` 返回的是：

- A. `langgraph`（因为有类型化状态）
- B. `agno`（因为需要会话记忆）
- C. 抛出异常
- D. `plain python`，理由文本却写着"no state"

**Q7.** 固定 `total_llm_calls=10`，把 `Problem` 的 7 个布尔字段穷举成 128 种组合，`recommend()` 返回 `langgraph` 的有多少种？

- A. 120 种
- B. 64 种
- C. 32 种
- D. 7 种

**Q8.** 任务只有"抓取网页 → 调一次 LLM 总结"两步，没有状态、角色、对话、并行和恢复需求。按讲义的建议，应该：

- A. 用 LangGraph，因为以后可能会扩展
- B. 用 CrewAI，定义一个 summarizer 角色
- C. 用纯 Python + 提供商 SDK，不引入框架
- D. 用 AutoGen，让两个 agent 讨论总结结果

---

## 三、动手 / 代码题

**Q9.** `recommend()` 的第一条规则：

```python
    if p.total_llm_calls <= 2 and not any(
        (p.has_roles, p.has_dialogue, p.needs_resume, p.has_parallel_fanout, p.needs_human_interrupt)
    ):
        return Recommendation(
            "plain python",
            "Two or fewer LLM calls with no state, roles, dialogue, fanout, "
            "or resume needs; a framework is pure overhead.",
        )
```

1. 这条规则漏检了哪些字段？构造一个让"理由文本"与输入自相矛盾的例子。
2. 给出修复，并补一个能捕获该问题的测试用例。修复后你的例子会推荐什么？

**Q10.** 自带的 7 个测试用例全部通过（`7/7 cases passed.`），但每个用例几乎只打开一个信号。

1. 写一段代码，固定 `total_llm_calls`，穷举 7 个布尔字段的全部组合，统计每个框架被推荐的次数。
2. 解释 `total_llm_calls` 为 1–2 和 ≥3 时统计结果的差别，以及为什么 `agno` 只有 2 种组合。
3. 这说明了"有序 if 链"式决策树的什么问题？

**Q11.** 用 `python main.py --ask` 进入交互模式：

```python
        total_llm_calls=int(input("Approx LLM calls per run? ").strip() or "1"),
```

1. 在"Approx LLM calls per run?"处输入 `about five`，或者通过管道传入空的标准输入，会发生什么？
2. 修改 `run_interactive`，让非法数字重新询问、EOF 时给出友好提示并返回非 0 退出码。

**Q12.** 讲义提醒"LLM 选路由每一轮都要花 token"，skill 文件还给出了"每日运行量超过 10,000 次就考虑纯 Python"的逃生口，但 `Problem` 里没有这两个维度。

1. 手算：一个 hierarchical crew 每次运行做 10 次 manager 路由决策，每次决策约 800 个输入 token、50 个输出 token；按输入 $3/M、输出 $15/M 计价，每天运行 5,000 次。仅路由一项每天、每月（30 天）各花多少钱？
2. 给 `Problem` 增加 `daily_runs: int = 0` 和 `llm_routing_decisions: int = 0`，在 `recommend()` 里实现：每日运行量 > 10,000 且没有恢复/中断需求时推荐纯 Python；`llm_routing_decisions` 很多时在理由中附带每次运行的路由 token 估算。说明你把新规则放在 if 链的哪个位置、为什么。

---

## 四、面试高频题

**Q13.**（基础必考）比较 LangGraph、CrewAI、AutoGen、Agno 的核心抽象、最适合和最不适合的场景。

**Q14.**（原理深挖）显式路由与 LLM 选择路由各有什么优劣？什么时候值得让 LLM 决定下一步？

**Q15.**（工程实践）团队要为一个新 agent 项目选框架，你会怎么组织评估？看哪些指标？如何控制被框架锁定的风险？

**Q16.**（场景设计）一个电商客服系统：先分诊用户意图，再交给"订单 / 物流 / 售后"专家处理；售后退款需人工审批；服务要能在重启后恢复。你会选什么框架（或组合）？画出结构并说明理由。

**Q17.**（追问型）"既然 LangGraph 什么都能做，为什么不永远选它？"——请反驳这个观点，并说明什么时候"不用任何框架"才是对的。

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："CrewAI → you draw an org chart. Each role has a job description and a manager routes tasks." A 是"画一张图（状态机）"；B 是"画一个 Slack 私聊"；D 是"画一个挂着工具的盒子"。

### Q2 — 答案：A

讲义："AutoGen — the agents decide via chat. Branching is emergent from who speaks next. `GroupChatManager` selects the next speaker; you can hand-write a `speaker_selection_method` but the default is LLM-driven." B 是 LangGraph；C 是 CrewAI 的 sequential 模式；D 是 Agno。

### Q3 — 答案：D

讲义："Rough order of increasing overhead: Agno ≈ LangGraph < CrewAI ≈ AutoGen. The difference is dominated by how much extra LLM routing the framework does." CrewAI 的 hierarchical manager 和 AutoGen 的 `GroupChatManager` 都在"决定谁下一个"上花 token；LangGraph 只在你写了 `llm.invoke` 的地方花 token。A、C 排序错误且归因错误；B 忽略了路由成本。

### Q4 — 答案：B

讲义："Agno. Built-in storage drivers (SQLite, Postgres, Mongo, Redis, DynamoDB) attached to an `Agent` via `storage=` ... Not a full graph checkpointer; a session store." A 错：CrewAI "No durable per-crew store out of the box"；C 错：AutoGen 只有对话记录持久化，"arbitrary workflow state does not unless you write adapters"；D 错：checkpointer 恰是 LangGraph 的一等公民。

### Q5 — 答案：B

判断顺序：第一条要求 `total_llm_calls <= 2`，不满足；第二条（resume/interrupt/fanout）都为假；第三条 `has_dialogue and not has_typed_state` 为真，直接返回 `autogen`，CrewAI 那条根本没机会被检查（已运行验证）。这体现了"有序 if 链"的特点：**信号冲突时，谁写在前面谁赢**。讲义并没有规定"对话优先于角色"，这是代码作者的隐含取舍。

### Q6 — 答案：D

第一条规则的 `any(...)` 只检查了 `has_roles, has_dialogue, needs_resume, has_parallel_fanout, needs_human_interrupt` 五个字段，**没有**检查 `has_typed_state` 和 `needs_session_memory`。于是 2 次调用 + 类型化状态 + 会话记忆的问题被推荐为 `plain python`，理由却写着"with no state"（已运行验证；交互模式输入 `y n n n n n 2 y` 也得到同样结果）。A、B 是"本应"考虑的结果；C 不会发生。

### Q7 — 答案：A

实测（`total_llm_calls=10`）：`{'langgraph': 120, 'agno': 2, 'autogen': 4, 'crewai': 2}`。只要 `needs_resume`、`needs_human_interrupt`、`has_parallel_fanout` 任一为真（128 − 16 = 112 种）就直接返回 `langgraph`；剩下 16 种里又有 8 种落到 `has_typed_state` 或兜底分支，同样是 `langgraph`。120/128 ≈ 94%。

### Q8 — 答案：C

讲义 Skill 第 5 条："If the task is two LLM calls and a tool, write 30 lines of plain Python; no framework is cheaper than no framework"；决策矩阵："Quick prototype, no framework commitment → Plain Python + provider SDK"。skill 文件也明确"Push back on LangGraph for a two-call summarizer; the StateGraph overhead is pure tax"。A 是"为未来过度设计"；B、D 引入了不必要的角色和对话开销。

### Q9 — 参考答案

1. 漏检 `has_typed_state` 和 `needs_session_memory`。反例：`Problem(has_typed_state=True, needs_session_memory=True, total_llm_calls=1)` → `plain python`，理由"no state"与输入矛盾。会话记忆意味着要接存储，按讲义本应考虑 Agno。
2. 修复（把 7 个信号都纳入"是否需要框架"的判断，并让理由与条件一致）：

```python
SIGNALS = ("has_typed_state", "has_roles", "has_dialogue", "has_parallel_fanout",
           "needs_resume", "needs_human_interrupt", "needs_session_memory")

def recommend(p: Problem) -> Recommendation:
    if p.total_llm_calls <= 2 and not any(getattr(p, f) for f in SIGNALS):
        return Recommendation("plain python",
            "Two or fewer LLM calls with no state, memory, roles, dialogue, "
            "fanout, resume, or interrupt needs; a framework is pure overhead.")
    ...
```

补充测试：

```python
        (
            "one-call bot that must remember the user",
            Problem(has_typed_state=True, needs_session_memory=True, total_llm_calls=1),
            "agno",
        ),
```

修复后该例会跳过第一条，依次经过 resume/interrupt/fanout（假）、dialogue（假）、roles（假），落到 `needs_session_memory and not has_roles and not has_dialogue` → `agno`。

讨论：是否把 `has_typed_state` 纳入第一条值得商榷——"有一个 TypedDict"本身不等于需要框架。更严谨的做法是只把 `needs_session_memory` 加进来，而把 `has_typed_state` 从理由文本里删去"no state"的说法。关键是**条件与理由文本必须一致**。

### Q10 — 参考答案

1. 穷举代码（已运行）：

```python
import itertools, collections
from main import Problem, recommend

FIELDS = ["has_typed_state", "has_roles", "has_dialogue", "has_parallel_fanout",
          "needs_resume", "needs_human_interrupt", "needs_session_memory"]

for calls in (1, 2, 3, 10):
    c = collections.Counter()
    for bits in itertools.product([False, True], repeat=len(FIELDS)):
        c[recommend(Problem(total_llm_calls=calls, **dict(zip(FIELDS, bits)))).framework] += 1
    print(calls, dict(c))
```

输出：

```text
1 {'plain python': 4, 'langgraph': 118, 'autogen': 4, 'crewai': 2}
2 {'plain python': 4, 'langgraph': 118, 'autogen': 4, 'crewai': 2}
3 {'langgraph': 120, 'agno': 2, 'autogen': 4, 'crewai': 2}
10 {'langgraph': 120, 'agno': 2, 'autogen': 4, 'crewai': 2}
```

2. 1–2 次调用时，其余 5 个信号全假、只剩 `has_typed_state` 与 `needs_session_memory` 自由变化的 4 种组合全被第一条吞掉成 `plain python`（Q9 的 bug）。其中只有"两者都假"这 1 种是合理的；"只有会话记忆"和"两者都有"本应是 `agno`，"只有类型化状态"本应是 `langgraph`。按 Q9 修复后（7 个信号都纳入），1–2 次调用的统计变为 `{'plain python': 1, 'agno': 2, 'langgraph': 119, 'autogen': 4, 'crewai': 2}`（已运行验证）。≥3 次调用时，`agno` 只有 2 种组合，因为它要求 resume/interrupt/fanout 全假、`has_roles` 和 `has_dialogue` 也全假（否则前面已返回或被排除），剩下的自由度只有 `has_typed_state`：2 种。
3. 问题：
   - **顺序即优先级**：信号冲突时由 if 的先后决定，例如"对话 + 角色"永远是 AutoGen，"类型化状态 + 会话记忆"是 Agno（Agno 那条在 typed-state 那条之前）；这些优先级没有写进文档也没有测试。
   - **强烈偏向 LangGraph**：任何一个"恢复 / 中断 / fanout"信号就一票决定；兜底也是 LangGraph。讲义自己说"no framework is cheaper than no framework"，但 ≥3 次调用、没有任何信号时代码仍推荐 LangGraph。
   - **测试只覆盖单信号的"顺风"用例**，无法发现组合问题。应补充"冲突信号"用例，或改成打分制（每个框架按匹配信号加权打分、输出前两名与理由）。

### Q11 — 参考答案

1. 输入 `about five` 时 `int("about five")` 抛 `ValueError: invalid literal for int() with base 10: 'about five'`，程序带着 traceback 退出（已运行验证）；空的标准输入（如 `printf '' | python main.py --ask`）在第一次 `input()` 就抛 `EOFError: EOF when reading a line`。只有直接回车时 `.strip() or "1"` 才会回退为 1。
2. 参考实现：

```python
def run_interactive() -> int:
    def ask(prompt: str) -> str:
        try:
            return input(prompt)
        except EOFError:
            raise SystemExit("\ninput closed; aborting")       # 退出码非 0

    def yes(prompt: str) -> bool:
        return ask(f"{prompt} [y/N] ").strip().lower().startswith("y")

    def ask_int(prompt: str, default: int = 1) -> int:
        while True:
            raw = ask(prompt).strip()
            if not raw:
                return default
            try:
                n = int(raw)
                if n >= 0:
                    return n
            except ValueError:
                pass
            print("please enter a non-negative integer")

    p = Problem(
        has_typed_state=yes("Typed state / explicit state schema?"),
        # ... 其余字段同原代码 ...
        total_llm_calls=ask_int("Approx LLM calls per run? "),
        needs_session_memory=yes("Needs durable per-user session memory?"),
    )
    ...
```

`raise SystemExit("message")` 会把消息打印到 stderr 并以退出码 1 结束。

### Q12 — 参考答案

1. 每次决策成本：`800 × $3/M + 50 × $15/M = $0.0024 + $0.00075 = $0.00315`。每次运行 10 次决策 → $0.0315；每天 5,000 次 → **$157.5/天**；30 天 → **$4,725/月**（已用 Python 计算）。这还没算决策错误导致的额外轮次。如果路由逻辑其实是确定的，改成显式边就能把这部分降为 0——这就是讲义"When cost per run matters, prefer explicit routing"的含义。
2. 参考实现思路：

```python
@dataclass(frozen=True)
class Problem:
    ...
    daily_runs: int = 0
    llm_routing_decisions: int = 0

def recommend(p: Problem) -> Recommendation:
    # 规则 0：高频、无持久化需求 → 纯 Python（放在最前面）
    if p.daily_runs > 10_000 and not (p.needs_resume or p.needs_human_interrupt):
        return Recommendation("plain python",
            f"{p.daily_runs:,} runs/day: framework and LLM-routing overhead is multiplied "
            "at this volume; hand-written explicit routing with the provider SDK.")
    ...
    rec = ...  # 原有逻辑
    if p.llm_routing_decisions:
        tokens = p.llm_routing_decisions * 850          # 按 800 输入 + 50 输出估算
        rec = Recommendation(rec.framework, rec.reason + f" (LLM routing ≈ {tokens:,} tokens/run)")
    return rec
```

放置位置：逃生口要放在 if 链**最前面**，否则会被"有 fanout → langgraph"等规则先截走；但它不能覆盖"必须恢复 / 必须人工审批"的硬需求，所以加了 `not (needs_resume or needs_human_interrupt)` 的保护。成本估算是附加信息，放在最后包装结果即可，不改变选择本身。

### Q13 — 参考回答要点

| 框架 | 核心抽象 | 最适合 | 最不适合 |
|------|---------|-------|---------|
| LangGraph | `StateGraph`：类型化状态、节点、条件边、checkpointer | 有明确状态、需要人工中断、需要 time-travel 调试的生产流程 | 拓扑未知、松散的角色式头脑风暴 |
| CrewAI | `Crew`：角色（goal、backstory）+ 任务 + 流程（sequential/hierarchical） | 角色驱动、计划短且线性/层级的流程 | 超出轮次历史的复杂状态、复杂分支 |
| AutoGen | `ConversableAgent`：多个 agent 轮流发言直到退出条件 | 提议者–批评者、师生式**对话**，思考在对话中涌现 | DAG 已知的确定性流程、需要跨重启持久状态 |
| Agno | `Agent`：单个 LLM + 工具 + 记忆，可组成团队 | 快速构建单 agent 和轻量团队，内置存储与多模态 | 深度显式分支、需要自定义 reducer 的图 |

- 加分点：用"白板上画什么"来记（图 / 组织架构 / 聊天 / 盒子）；能说出每个框架在状态、分支、可观测性三个维度上的差异。
- 常见误区：按 GitHub star 数或 demo 效果选框架——讲义开篇："Every framework sells the same demo ... and hides the same bug"。

### Q14 — 参考回答要点

- **显式路由**（Python 函数 / 静态边 / `speaker_selection_method`）：零额外 token、确定、可单元测试、可审计（checkpointer 记录走了哪个分支）；缺点是要提前知道所有分支。
- **LLM 选择路由**（hierarchical manager、`GroupChatManager` 默认模式、planner LLM）：灵活，能处理事先未知的分支；但每次决策都花 prompt + completion token，延迟增加，结果不确定，出错难以复现。
- **何时值得 LLM 路由**：分支空间开放、无法枚举（开放式研究、对话式协作）；运行量小、单次价值高；或者作为"兜底"——先用规则路由，规则覆盖不到时再交给 LLM。
- 加分点：混合做法——用便宜的小模型或分类器做路由，或用结构化输出让 LLM 只在有限的命名分支中选择，再交由显式边执行；量化路由成本（Q12 的算法）。讲义的 skill 文件也反对"每条边都由 planner LLM 路由"的图："that is AutoGen with extra steps and burns tokens per turn"（第 16 节 skill）。

### Q15 — 参考回答要点

- **先画形状**：讲义 checklist——画图 / 组织架构 / 聊天 / 盒子；确定谁决定分支；确定状态需求（恢复、time-travel、人工中断）；确定成本预算；评估框架本身的依赖成本。
- **同题多框架原型**（讲义练习 1、2）：同一个任务在 2–3 个候选框架里各做一版，比较：
  - 每次运行的 token 成本与延迟；
  - 代码行数与可读性；
  - 崩溃后能否恢复；
  - 能否在写入步骤前插入人工审批；
  - 可观测性（OTel span 粒度、与现有平台的集成）；
  - 测试便利性（能否注入假 LLM 做确定性测试）。
- **控制锁定风险**：业务逻辑（工具、prompt、领域模型）写成与框架无关的纯函数，框架只负责编排；工具用 MCP 等标准协议暴露；状态 schema 用 Pydantic 独立定义；保留"纯 Python + SDK"的退路。
- 常见误区：在画出形状之前就选框架（讲义："Refuse to reach for a framework before you can draw the graph, the org chart, the chat, or the agent box"）。

### Q16 — 参考回答要点

- **形状**：外层是有明确状态和审批的流程图（分诊 → 专家 → 可能的退款审批 → 回复），需要重启恢复 → 外层选 **LangGraph**。
- **结构**：
  - `triage` 节点（LLM 结构化输出意图）→ 条件边路由到 `order_agent` / `logistics_agent` / `aftersales_agent` 子图（显式路由，不用 manager LLM）；
  - `aftersales_agent` 中 `issue_refund` 前 `interrupt_before`；
  - `PostgresSaver` 作为 checkpointer，`thread_id = user:{id}:ticket:{id}`；
  - 状态：`messages`（`add_messages`）、`intent`、`order_context`、`refund_amount`、`reviewer_decision`。
- **是否用 CrewAI/Agno**：若某个专家内部是"单 agent + 工具 + 会话记忆"，可以用 Agno 实现并作为一个节点嵌入；角色扮演式的 CrewAI 在这里收益不大，分支和审批都更适合显式图。
- **成本**：分诊用小模型；专家内部才用大模型；避免 LLM 选择专家。
- 加分点：讲义决策矩阵允许"CrewAI (sequential) 或 LangGraph subgraphs"——指出何时从 CrewAI 升级到 LangGraph（分支变复杂、需要恢复和审批时）。

### Q17 — 参考回答要点

- **LangGraph 的成本**：要预先命名每一个转换（讲义："forces you to name every transition before you know what the agent will do"）；学习曲线（reducer、checkpointer、interrupt 语义）；依赖与版本漂移；对两步小任务是"纯税"。
- **其他框架更顺手的场景**：对话式协作（AutoGen 原生）、快速单 agent + 记忆（Agno 最薄）、角色流水线（CrewAI 表达成本最低）。
- **不用框架的时机**：两次左右 LLM 调用 + 一个工具；超高频、对延迟和成本极敏感、路由逻辑完全确定的服务；原型阶段尚未确定形状。讲义："No framework is the fastest framework"。
- **决策树本身的提醒**：本节 `main.py` 在 128 种组合中有 120 种推荐 LangGraph，说明"规则引擎式选型"容易把偏好固化进代码；真正的选择应回到问题形状和实测数据。
- 加分点：框架只是 harness，agent 本身（模型 + prompt + 工具）不变；把业务逻辑与编排解耦，就能在框架之间迁移。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 09 Function Calling 与工具使用](../../09-function-calling/docs/zh.md)：所有框架的工具调用都建立在 function calling 之上。
- [阶段 11 · 16 Agent State Machines——图、节点与 Checkpoints](../../16-langgraph-state-machines/docs/zh.md)：本节用来对标的 LangGraph 基础。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：每个框架包装的都是同一个循环。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../../14-agent-engineering/12-anthropic-workflow-patterns/docs/zh.md)：与框架无关的模式库（链、路由、并行、编排者–工作者、评估者–优化者）。

### 本节被哪些后续内容用到
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：图式编排的深入。
- [阶段 14 · 14 用于 Agents 的 Actor 模型：异步消息与类型化运行时](../../../14-agent-engineering/14-autogen-actor-model/docs/zh.md)：AutoGen 的 actor 模型。
- [阶段 14 · 15 基于角色的 Agent 团队：角色、任务与流程](../../../14-agent-engineering/15-crewai-role-based-crews/docs/zh.md)：CrewAI 式角色团队。
- [阶段 14 · 18 生产级 Agent 运行时：快速实例化与类型化工作流](../../../14-agent-engineering/18-agno-and-mastra-runtimes/docs/zh.md)：Agno 等轻量运行时。
- [阶段 14 · 03 Reflexion：语言反馈驱动的 Reinforcement Learning](../../../14-agent-engineering/03-reflexion-verbal-rl/docs/zh.md)：讲义说 Reflexion 映射到 LangGraph 很自然、映射到 CrewAI 很别扭。
- [阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../../14-agent-engineering/24-agent-observability-platforms/docs/zh.md)：为所选框架接入追踪。
- [阶段 14 · 28 Orchestration 模式：监督者、Swarm 与层级结构](../../../14-agent-engineering/28-orchestration-patterns/docs/zh.md)：多 agent 编排模式的系统梳理。

### 延伸关键词
`LangGraph` · `StateGraph` · `CrewAI` · `Crew / Task / Process` · `output_pydantic` · `AutoGen` · `ConversableAgent` · `GroupChatManager` · `speaker_selection_method` · `Agno` · `Team` · `explicit routing` · `LLM-selected routing` · `durable state` · `OpenTelemetry` · `vendor lock-in`
