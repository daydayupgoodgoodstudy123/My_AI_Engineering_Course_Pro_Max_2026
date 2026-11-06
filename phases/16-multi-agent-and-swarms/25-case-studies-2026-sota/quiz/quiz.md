# 测验 · 案例研究与 2026 年前沿进展（Case Studies and the 2026 State of the Art）

> **阶段 16 · 多智能体与集群 · 第 25 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：本节讲义标注"Languages: —"、没有 Build It 小节，但 `code/` 下有一个"案例映射器"脚本，本测验同时覆盖讲义与这份代码。讲义中的数字与事件（如 Opus 4.7、Moltbook 被收购等）均照讲义转述，未做独立核实。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Anthropic Research 系统 | supervisor-worker 的生产参考：Opus 4 规划与综合、Sonnet 4 子 agent 并行研究；讲义：比单 agent Opus 4 高 +90.2%，每次查询约 15 倍 token |
| 2 | "token 用量解释 80% 方差" | 讲义：BrowseComp 上 80% 的表现方差可由 token 用量单独解释——多 agent 的胜利很大程度来自每个子 agent 都有一个新的 context window |
| 3 | Research 系统的四条设计经验 | 按查询复杂度扩展投入（简单 1 个 agent、3–10 次工具调用；中等 3 个；复杂 10+）；先广后窄；rainbow deploy；验证不可省 |
| 4 | MetaGPT | 把软件工程 SOP 编码成角色 prompt（PM、架构师、项目经理、工程师、QA），`Code = SOP(Team)`；角色之间传递结构化工件（PRD、架构文档、代码） |
| 5 | ChatDev 与 MacNet | ChatDev 的 communicative dehallucination：先向同伴索要细节再回答；MacNet（arXiv:2406.07155）用 DAG 把规模扩展到 1000+ agent |
| 6 | OpenClaw / Moltbook | 人口规模（population-scale）案例：本地 ReAct 循环 agent；讲义：Moltbook 上线数日约 2.3M agent 账号；涌现的经济活动、规模化 prompt injection、监管快速介入 |
| 7 | Rainbow deployment | agent 长时间运行且有状态：新版本上线时保留旧运行时，直到其上的在途 agent 跑完 |
| 8 | 2026 年 4 月框架格局 | LangGraph、CrewAI 生产领先；AG2 是社区维护的 AutoGen 延续；Microsoft AutoGen 进入维护模式、并入 Microsoft Agent Framework（RC）；OpenAI Agents SDK 是 Swarm 的生产继任者；Google ADK 原生支持 A2A；主流框架都支持 MCP，多数支持 A2A |
| 9 | 三个案例的六个共同模式 | 编排者 + 工作者、结构化 handoff 契约、验证作为一等角色、扩展靠拓扑与底座而非堆数量、成本重要且要披露、安全姿态显式 |
| 10 | 选参考案例的规则 | 研究/知识任务 → Anthropic Research；工程/工具链 → MetaGPT/ChatDev；网络效应社交产品 → OpenClaw/Moltbook；经典企业自动化 → CrewAI 或 LangGraph |

### 核心技能（能动手做到）

- [ ] 对任意一个多 agent 设计，说出最接近的参考案例，并列出可以照搬的 3–4 个设计决策
- [ ] 解释"15 倍 token 换 +90.2%"背后的机制（新上下文窗口）以及它对成本决策的含义
- [ ] 用 communicative dehallucination 和结构化 handoff 契约改造一个现有的多 agent 流水线
- [ ] 读懂 `map_to_case` 的 if 链优先级，找出哪些输入字段从不影响结果、哪些输入会被映射到不合理的案例
- [ ] 把规则映射改造成"打分 + 解释"的映射器，并补上讲义中"企业自动化 → CrewAI/LangGraph"这一分支
- [ ] 按 skill 文件的 hard reject 规则，为设计方案写一个检查器（验证、prompt injection、MCP/A2A、MAST 审计）

---

## 二、基础自测（选择题）

**Q1.** 讲义转述的 Anthropic Research 系统关键数字是：

- A. 比单 agent 高 +15%，token 用量为单 agent 的 90 倍
- B. 比单 agent Opus 4 高 +90.2%，每次查询约 15 倍 token
- C. 比单 agent 高 +41.77%，token 与单 agent 持平
- D. 比单 agent 低 10%，但成本只有 1/15

**Q2.** 讲义说 BrowseComp 上 80% 的表现方差可由 token 用量单独解释。它对"多 agent 为什么赢"的解释是：

- A. 子 agent 使用了更大的模型
- B. 多 agent 天然不会产生幻觉
- C. 编排者会对子 agent 的答案做多数投票
- D. 每个子 agent 都得到一个新的 context window，系统整体能投入更多 token 去探索

**Q3.** ChatDev 的 "communicative dehallucination" 指的是：

- A. agent 在回答前先向同伴索要具体信息（例如设计 agent 先问程序员打算用什么语言），而不是自行猜测
- B. 用一个外部事实库自动删除幻觉内容
- C. 多个 agent 投票，少数派的回答被视为幻觉
- D. 降低采样温度到 0 以消除幻觉

**Q4.** MacNet（arXiv:2406.07155）能把 ChatDev 扩展到 1000+ agent，讲义给出的关键原因是：

- A. 所有 agent 在同一个群聊里自由发言
- B. 使用了更长的上下文窗口
- C. 用 DAG 显式编码角色节点与 handoff 边，路由明确且可离线计算
- D. 每个 agent 都是独立训练的小模型

**Q5.** 运行本节代码，`internal-automation`（`task_type="automation"`、`roles_distinct=True`）被映射到哪个案例？

- A. Anthropic Research
- B. MetaGPT / ChatDev
- C. OpenClaw / Moltbook
- D. CrewAI / LangGraph 企业自动化参考

**Q6.** Rainbow deployment 在本节语境下的含义是：

- A. 新版本上线时保留旧运行时版本，直到其上仍在运行的长时 agent 完成
- B. 按颜色区分不同 agent 的日志
- C. 先把新版本发给 1% 用户，再逐步放量
- D. 每个子 agent 使用不同厂商的模型

**Q7.** 按讲义的 2026 年 4 月框架格局，关于 Microsoft AutoGen 的说法正确的是：

- A. 是当前生产领先的框架，推荐作为默认选择
- B. 已改名为 AG2，由微软继续维护
- C. 是 OpenAI Swarm 的继任者
- D. 进入维护模式，并入 Microsoft Agent Framework（2026 年 2 月 RC）；AG2 是社区维护的 AutoGen v0.2 延续

**Q8.** 阅读 `map_to_case`，下列哪组 `Design` 字段**从不改变**映射结果？

```python
def map_to_case(d: Design) -> str:
    if d.task_type == "population" or d.user_facing_network:
        return "openclaw_moltbook"
    if d.task_type == "engineering" or d.roles_distinct:
        return "metagpt_chatdev"
    if d.task_type == "research":
        return "anthropic_research"
    if d.verification_required and d.runtime_duration_hours >= 1:
        return "anthropic_research"
    return "anthropic_research"
```

- A. `task_type` 与 `roles_distinct`
- B. `user_facing_network` 与 `task_type`
- C. `n_agents_expected`、`verification_required`、`runtime_duration_hours`
- D. 所有字段都会影响结果

---

## 三、动手 / 代码题

**Q9.** 继续分析 Q8 的 `map_to_case`：

1. 一个"研究任务，但角色分工明确"（`task_type="research"`、`roles_distinct=True`）的设计会被映射到哪里？一个"面向公众用户的研究助手"（`task_type="research"`、`user_facing_network=True`）呢？这合理吗？
2. 对 4 种 `task_type` × 其余 4 个布尔/二值字段（verification、hours∈{0.5, 2.0}、roles_distinct、user_facing_network）的全部 64 种组合运行映射，三类案例各占多少？说明了什么？
3. 讲义"Choosing a reference"写了"Classic enterprise automation → CrewAI or LangGraph"，代码里这条规则体现在哪里？

**Q10.** 把 `map_to_case` 改写成"打分 + 解释"的版本 `score_cases(d)`：每个案例累加带理由的分数，返回最佳案例、各案例得分和命中理由；新增 `enterprise_automation` 案例；`n_agents_expected` 与"长时 + 需验证"也要参与打分。给出实现，并说明它对 Q9 中两个"不合理"输入的输出。

**Q11.** 讲义的框架表有 8 行，代码的 `FRAMEWORK_LANDSCAPE` 只有 7 行：

```python
FRAMEWORK_LANDSCAPE = [
    ("LangGraph", "production", "structured graph + checkpointing + HITL"),
    ("CrewAI", "production", "role-based crews; Sequential/Hierarchical"),
    ("AG2", "community maintenance", "GroupChat + speaker selection"),
    ("Microsoft Agent Framework", "RC (Feb 2026)", "orchestration patterns + enterprise"),
    ("OpenAI Agents SDK", "production", "Swarm successor; tool-return handoffs"),
    ("Google ADK", "production (Apr 2025)", "A2A-native; Google Cloud"),
    ("Anthropic Claude Agent SDK", "production", "agent + Research extension"),
]
```

1. 少了哪一行？少了它会让读者误解什么？
2. 打印语句是 `f"  {name:30s} {status:22s} {best_for:30s}"`。`best for` 列有几行超过了 30 个字符？`:30s` 会截断吗？如果以后在它右边再加一列（例如 `notes`），会发生什么？如何修？
3. 讲义说"protocol compatibility is no longer a differentiator -- handoff semantics are"。请从本阶段学过的内容出发，说出 OpenAI Agents SDK 的"tool-return handoff"、LangGraph 的图 + checkpoint、CrewAI 的 Sequential/Hierarchical 三种 handoff 语义各适合什么场景。

**Q12.** `outputs/skill-case-study-mapper.md` 列出了若干 hard reject 与 refusal 规则。写一个 `lint_design(d, uses_mcp, uses_a2a, has_correctness_req, has_mast_audit, production)`，至少检查：有正确性要求却不验证、人口规模/面向用户网络却无 prompt-injection 威胁模型、不采用 MCP/A2A、声称可上生产却没做 MAST 审计。用代码中的 `agent-marketplace` 设计（`verification_required=False`）测试它。

---

## 四、面试高频题

**Q13.**（基础必考）Anthropic 的多 agent Research 系统为什么比单 agent 好那么多？它付出了什么代价？什么情况下不该用这种架构？

**Q14.**（原理深挖）MetaGPT 的 `Code = SOP(Team)` 和 ChatDev 的 communicative dehallucination 分别解决了多 agent 系统的哪类失败？请对应到第 23 节的 MAST 分类。

**Q15.**（工程实践）长时间运行、有状态的 agent 为什么需要 rainbow deployment？和普通无状态服务的蓝绿部署、金丝雀发布有什么不同？

**Q16.**（场景设计）你要做一个"成千上万个用户 agent 互相交易服务"的平台。参考 OpenClaw / Moltbook 案例，列出你最担心的三类风险以及对应的工程手段。

**Q17.**（追问型）2026 年选多 agent 框架时，讲义说"MCP + A2A 是标配，差异在 handoff 语义"。如果面试官追问"那你为什么选 LangGraph 而不是 CrewAI"，你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："**+90.2%** improvement over single-agent Opus 4 on internal research evals… **15x tokens per query** vs single-agent." A 把两个数字颠倒了；C 的 41.77% 是第 23 节 MAST 中 Specification Problems 的占比；D 与讲义相反——多 agent 赢在准确率、输在成本。

### Q2 — 答案：D

讲义："multi-agent wins largely because each subagent gets a fresh context window." 子 agent 用的是 Sonnet 4，比编排者的 Opus 4 小，所以 A 错；B 错，讲义明确说该系统"was observed to hallucinate without explicit verifier roles"；C 没有依据，编排者做的是综合（synthesis）而不是投票。

### Q3 — 答案：A

讲义："Agents request specifics before answering — a designer agent asks the programmer what language is intended before sketching UI, rather than guessing." B 是外部检索核验；C 是投票；D 是采样参数，都不是这个机制。它便宜、却"承重"（load-bearing）：把"猜"变成"问"，直接减少 specification 类失败。

### Q4 — 答案：C

讲义："Each DAG node is a role specialization; edges encode handoff contracts. The scale is possible because routing is explicit and offline-computable." A 恰好相反——讲义的经验是"DAGs scale further than chat"；B、D 都不是讲义给出的原因。

### Q5 — 答案：B

实际输出：

```text
design: 'internal-automation'
  type=automation  n_agents=3  verification=True  hours=0.5

  closest case study: MetaGPT / ChatDev (SOP role-decomposition)
```

`task_type` 不是 population，`user_facing_network=False`，于是进入第二个分支；`roles_distinct=True` 命中，返回 `metagpt_chatdev`。D 是讲义"经典企业自动化 → CrewAI 或 LangGraph"的建议，但代码的 `CASES` 里根本没有这个选项（见 Q9）。

### Q6 — 答案：A

讲义："Rainbow deploys. Keep old runtime versions alive until their in-flight agents finish." 原因是 agent 长时间运行且有状态，直接替换运行时会打断在途任务。C 是金丝雀发布（canary），关注的是"新版本对新流量是否安全"，与"旧版本上的在途任务能否跑完"是不同问题；B、D 无关。

### Q7 — 答案：D

讲义框架表："Microsoft AutoGen | Maintenance mode (Feb 2026) | — | merged into Microsoft Agent Framework RC"；"AG2 | Community maintained | GroupChat + speaker selection | AutoGen v0.2 continuation"。A 描述的是 LangGraph；B 混淆了 AG2 与微软；C 描述的是 OpenAI Agents SDK。

### Q8 — 答案：C

- `n_agents_expected` 在函数里根本没出现。
- 最后两个分支都返回 `"anthropic_research"`，所以 `verification_required` 与 `runtime_duration_hours` 的判断是否成立都不影响结果——第 4 个 `if` 是死逻辑。
- A、B 中的 `task_type`、`roles_distinct`、`user_facing_network` 都会改变结果。

`Design` 有 7 个字段（含 `name`），真正影响映射的只有 3 个。skill 文件里"Anthropic Research if… verification mandatory, multi-hour runs"的判断依据在代码中没有起作用。

### Q9 — 参考答案

1. 已运行验证：
   - `research` + `roles_distinct=True` → `metagpt_chatdev`。因为"工程或角色分明"的分支排在"研究"之前。但 Anthropic Research 系统本身也有明确角色（lead 编排者、研究子 agent、verifier），"有角色"不该压过"任务类型是研究"。
   - `research` + `user_facing_network=True` → `openclaw_moltbook`。第一个分支对 `user_facing_network` 一票否决。一个面向公众的研究助手并不是"agent 与 agent 构成社交网络"的人口规模系统；这个字段名本身也有歧义（"面向用户"还是"agent 组成的网络"）。
2. 64 种组合中（已枚举运行）：OpenClaw / Moltbook **40** 种，MetaGPT / ChatDev **16** 种，Anthropic Research **8** 种。只要 `user_facing_network=True`（占一半组合）就必然是 OpenClaw，再加上全部 population 类型——映射器严重偏向排在最前的规则。if 链的顺序就是隐含的优先级，规则越靠前"抢走"的输入越多。
3. 代码里**没有体现**。`CASES` 只有三个案例；`automation` 类型要么因 `roles_distinct` 进 MetaGPT，要么因 `user_facing_network` 进 OpenClaw，要么落入默认的 Anthropic Research。讲义 "Classic enterprise automation → CrewAI or LangGraph" 在代码中缺失，这是讲义与代码的一处不一致。

### Q10 — 参考答案

```python
def score_cases(d):
    s = {"anthropic_research": 0.0, "metagpt_chatdev": 0.0,
         "openclaw_moltbook": 0.0, "enterprise_automation": 0.0}
    why = {k: [] for k in s}

    def add(k, w, reason):
        s[k] += w
        why[k].append(f"+{w} {reason}")

    t = d.task_type
    if t == "research":    add("anthropic_research", 3, "research task")
    if t == "engineering": add("metagpt_chatdev", 3, "engineering task")
    if t == "population":  add("openclaw_moltbook", 3, "population-scale task")
    if t == "automation":  add("enterprise_automation", 3, "classic automation")
    if d.roles_distinct:      add("metagpt_chatdev", 1, "distinct roles")
    if d.user_facing_network: add("openclaw_moltbook", 2, "user-facing agent network")
    if d.n_agents_expected >= 100: add("openclaw_moltbook", 1, ">=100 agents")
    if d.verification_required and d.runtime_duration_hours >= 1:
        add("anthropic_research", 1, "long verified runs")
    best = max(s, key=s.get)
    return best, s, why[best]
```

`enterprise_automation` 需要在 `CASES` 里补一项，例如 `framework: "CrewAI or LangGraph"`、patterns 为"确定性流程图、checkpoint、human-in-the-loop 审批"。

已运行结果：

| 设计 | 结果 | 命中理由 |
|---|---|---|
| research-assistant | anthropic_research（4） | research task +3，long verified runs +1 |
| codegen-team | metagpt_chatdev（4） | engineering +3，distinct roles +1 |
| agent-marketplace | openclaw_moltbook（6） | population +3，user-facing +2，≥100 agents +1 |
| internal-automation | enterprise_automation（3） | classic automation +3（MetaGPT 仅 1 分） |
| research + roles_distinct | anthropic_research（4 vs 1） | 任务类型权重压过"有角色" |
| research + user_facing | anthropic_research（4 vs 2） | 不再被一票否决 |

要点：权重让"任务类型"成为主信号、其他字段成为修正项；返回理由便于审计（与第 24 节"结论要由数据生成"同一原则）；平分时 `max` 取字典中先出现的键，应显式定义平局规则或返回"需要人工判断"。权重本身是拍定的，应该用一批已标注的历史设计来校准。

### Q11 — 参考答案

1. 缺少 **Microsoft AutoGen（Maintenance mode, Feb 2026）** 这一行。讲义特意把它列出来，就是提醒"不要再基于 AutoGen 起新项目"；代码只列出 Microsoft Agent Framework，读者看不到 AutoGen 的状态变化，也看不到 AG2 与 AutoGen 的关系。
2. 有 4 行超过 30 个字符（已计算）：LangGraph 39、CrewAI 41、Microsoft Agent Framework 35、OpenAI Agents SDK 37。`:30s` 只是**最小宽度**，不足补空格、超出**不截断**。因为它是最后一列，目前只表现为行长不一，以及短行末尾多出空格（输出里能看到）；一旦右边再加一列，超长的行会把后面的列整体推右，表格错位。修法：最后一列不定宽；或截断 `f"{best_for[:30]:30s}"`；或用 `textwrap.shorten(best_for, 30)`；或先计算各列最大长度再动态定宽。
3. handoff 语义对比（结合阶段 14 与本阶段内容）：
   - **OpenAI Agents SDK 的 tool-return handoff**：一个 agent 通过"调用一个返回另一个 agent 的工具"把控制权交出去，对话历史随之移交。适合客服分流、意图路由这类"谁来接手"清晰、链路短的场景（阶段 16 · 11 Handoffs 与例程）。
   - **LangGraph 的图 + checkpoint**：节点与边显式定义，状态在每步持久化，支持中断、恢复与人工审批。适合流程已知、需要可恢复与审计的生产工作流——讲义称其为"recommended default for production"。
   - **CrewAI 的 Sequential / Hierarchical process**：角色化的 crew，按顺序传递或由 manager 分派。适合 SOP 清楚的角色分解（与 MetaGPT 思路相近）。
   选择依据：控制流是否已知、是否需要持久化与恢复、角色是否稳定、是否需要人在回路。

### Q12 — 参考答案

```python
def lint_design(d, uses_mcp=True, uses_a2a=True, has_correctness_req=True,
                has_mast_audit=False, production=False):
    issues = []
    if has_correctness_req and not d.verification_required:
        issues.append("REJECT: correctness-critical task without verification")
    if d.user_facing_network or d.task_type == "population":
        issues.append("REQUIRE: prompt-injection threat model for cross-agent messages")
    if not (uses_mcp or uses_a2a):
        issues.append("REJECT: no MCP/A2A adoption without justification")
    if production and not has_mast_audit:
        issues.append("REFUSE: run a MAST-style audit (Lesson 23) before mapping")
    return issues
```

对 `agent-marketplace`（`production=True`）运行结果：

```text
['REJECT: correctness-critical task without verification',
 'REQUIRE: prompt-injection threat model for cross-agent messages',
 'REFUSE: run a MAST-style audit (Lesson 23) before mapping']
```

说明：原代码对 `verification_required=False` 的 marketplace 设计照样给出推荐，没有任何警告，而讲义的共同模式第 3 条是"Verification as first-class role"、skill 文件第一条 hard reject 就是"Designs that ignore verification when the task has correctness requirements"。`Design` 本身没有"是否有正确性要求""是否用 MCP/A2A"等字段，所以只能作为参数传入——更好的做法是把这些字段加进 `Design`。

### Q13 — 参考回答要点

- **为什么好**：
  - 讲义：BrowseComp 80% 的方差可由 token 用量解释——子 agent 各有新的 context window，可以并行做大范围搜索，避免单个上下文被塞满后的质量下降；
  - 编排者（Opus 4）负责规划与综合，子 agent（Sonnet 4）负责广度搜索，"先广后窄"；
  - 按复杂度扩展投入：简单问题 1 个 agent、3–10 次工具调用，复杂研究 10+ 子 agent。
- **代价**：约 15 倍 token；长时有状态运行带来的部署复杂度（rainbow deploy）；需要额外的验证角色，否则会幻觉。讲义 Ship It："An independent verifier costs ~20-30% of your token budget"。
- **不该用的情况**：简单查询（1 个 agent 就够）；子任务强耦合、需要共享大量上下文的任务（如单个文件的精细修改）；成本敏感、准确率提升不足以覆盖 15 倍 token 的业务。呼应第 24 节 MedAgentBoard："multi-agent does NOT dominate single-LLM on most categories"。
- 加分点：指出"多 agent 的收益有相当部分来自花更多推理 token"，因此评估时要和"同等 token 预算的单 agent"比较。

### Q14 — 参考回答要点

- **MetaGPT `Code = SOP(Team)`**：每个角色有窄而专的 prompt，角色之间传递有 schema 的工件（PRD、架构文档、代码）。
  - 解决 **Specification Problems**：角色契约写清"做什么、不做什么"，避免"两个 agent 都以为自己是 reviewer"；
  - 解决部分 **Coordination Failures**：结构化工件减少信息在自然语言对话中丢失或走样；
  - QA Engineer 角色补上 **Verification Gap**。
- **ChatDev communicative dehallucination**：接收方在动手前主动询问缺失的细节，把"猜测"变成"澄清"。
  - 主要对应 **Specification Problems**（任务欠规格时不再臆测）与 **Coordination Failures**（信息不对称时主动同步）。
- **MacNet 的 DAG**：把路由显式化，避免自由群聊里的发言者混乱，属于结构化拓扑对协调失败的预防。
- 加分点：讲义经验"Structure matters more than size. A tight 5-role SOP team beats a 50-agent unstructured group."

### Q15 — 参考回答要点

- **问题**：agent 一次运行可能持续数小时（讲义："Expect multi-hour agent runs to be routine"），且在内存或会话中持有状态。若直接把运行时替换成新版本，在途任务会中断、丢状态，或者以新代码继续执行旧状态导致不一致。
- **Rainbow deployment**：多个版本同时存活（"彩虹"），新请求进入新版本，旧版本只服务已有的在途 agent，直到它们自然结束再下线。
- **与蓝绿 / 金丝雀的区别**：
  - 蓝绿：两套环境一次性切换流量，假设请求短、可随时切走；
  - 金丝雀：按比例把新流量导到新版本，验证新版本质量；
  - rainbow：关心的是**旧版本上的长时任务能否完成**，可能同时有 3 个以上版本存活；需要按版本路由（session 粘性）、按版本的监控与资源回收。
- **配套手段**：durable execution / checkpoint（中断后能从检查点用兼容代码恢复）、状态 schema 的版本化与迁移、每个版本的最大存活时间。
- 加分点：联系阶段 15 的 durable execution 与阶段 17 的渐进式发布。

### Q16 — 参考回答要点

- **风险 1：规模化 prompt injection**。讲义："One malicious prompt in a viral agent profile propagates to thousands of agent-to-agent interactions in hours"，"Prompt injection is the new XSS"。手段：所有跨 agent 消息与 agent 资料默认视为不可信输入；指令与数据通道分离；对工具调用做权限最小化和高风险动作的人工确认；内容过滤与异常传播检测（某条内容被大量 agent 转发即告警）。
- **风险 2：涌现经济活动中的欺诈与失控**。agent 之间用 token 支付买卖服务，可能出现刷单、价格操纵、恶意 agent 骗取支付。手段：交易限额与托管、声誉系统（阶段 16 · 21）、异常交易检测、可审计的交易日志。
- **风险 3：监管与合规**。讲义："Regulation is faster than design cycles"，举例 China restricted OpenClaw on government computers。手段：从第一天起做数据驻留、审计日志、按地区开关功能、明确的服务条款与身份标识。
- **额外**：病毒式增长带来的突发负载（讲义"design for deploy-burst-load"）、级联故障（第 23 节的 circuit breaker）。
- 常见误区：把单系统的最佳实践（验证、角色清晰）当作足够——讲义："still apply but are not sufficient"。

### Q17 — 参考回答要点

- 先承认前提：两者都支持 MCP（以及多数支持 A2A），协议不是差异点。
- **选 LangGraph 的理由**（视场景而定）：
  - 流程可以画成图，需要显式的状态、条件分支和循环；
  - 需要 checkpoint：长时任务可中断、恢复、回放，支撑 rainbow deploy 与故障恢复；
  - 需要 human-in-the-loop 审批节点；
  - 讲义把它列为"recommended default for production"。
- **什么时候反而选 CrewAI**：问题天然是"几个角色按 SOP 协作"（如内容生产、调研报告），Sequential/Hierarchical 两种 process 就够，开发速度更重要。
- **回答结构**：任务的控制流是否已知 → 是否需要持久化与恢复 → 角色是否稳定 → 团队熟悉度与生态 → 用内部 benchmark（第 24 节）在同等成本下实测，而不是凭营销选择。
- 加分点：提到"从案例出发而非从零开始"（讲义 Ship It 第一条），说明自己的设计最接近哪个参考案例。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 05 监督者与编排者—工作者模式](../../05-supervisor-orchestrator-pattern/docs/zh.md)：Anthropic Research 系统所属的拓扑。
- [阶段 16 · 08 角色专业化：规划者、Critic、执行者与验证者](../../08-role-specialization/docs/zh.md)：MetaGPT / ChatDev 的角色分解基础。
- [阶段 16 · 11 Handoffs 与例程：无状态 Orchestration](../../11-handoffs-and-routines/docs/zh.md)：OpenAI Agents SDK 的 handoff 语义来源。
- [阶段 16 · 12 A2A：Agent 与 Agent 之间的通信协议](../../12-a2a-protocol/docs/zh.md)：框架格局里"多数支持 A2A"的含义。
- [阶段 16 · 21 Agent 经济体系、Token 激励与声誉](../../21-agent-economies/docs/zh.md)：Moltbook 涌现经济活动的理论背景。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：用 MAST 理解各案例的设计动机。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../24-evaluation-coordination-benchmarks/docs/zh.md)：读懂案例中的数字需要的评测清单。

### 本节被哪些后续内容用到
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：rainbow deploy 与渐进式发布的工程实现。
- [阶段 18 · 15 Indirect Prompt Injection：生产环境的攻击面](../../../18-ethics-safety-alignment/15-indirect-prompt-injection/docs/zh.md)：人口规模下 prompt injection 的攻防。
- [阶段 19 · 10 综合项目：多 Agent 软件工程团队](../../../19-capstone-projects/10-multi-agent-software-team/docs/zh.md)：MetaGPT / ChatDev 思路的完整实践。
- [阶段 19 · 05 综合项目：自主研究 Agent](../../../19-capstone-projects/05-autonomous-research-agent/docs/zh.md)：参照 Anthropic Research 系统构建研究型多 agent。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)、[阶段 14 · 15 基于角色的 Agent 团队](../../../14-agent-engineering/15-crewai-role-based-crews/docs/zh.md)：LangGraph 与 CrewAI 的具体用法。

### 延伸关键词
`supervisor-worker` · `fresh context window` · `rainbow deployment` · `SOP as prompts` · `communicative dehallucination` · `MacNet DAG` · `population-scale agents` · `prompt injection as XSS` · `LangGraph` · `CrewAI` · `AG2` · `Microsoft Agent Framework` · `OpenAI Agents SDK` · `Google ADK` · `MCP + A2A`
