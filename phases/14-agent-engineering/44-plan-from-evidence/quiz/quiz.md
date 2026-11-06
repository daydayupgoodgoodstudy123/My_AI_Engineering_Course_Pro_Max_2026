# 测验 · 制定有证据支撑的执行计划（Build an Evidence-Backed Execution Plan）

> **阶段 14 · Agent 工程 · 第 44 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 计划 ≠ 待办清单 | 讲义："A plan is not a prettier to-do list. It is a dependency graph in which every change has a reason and every terminal node has proof." |
| 2 | 弱计划的样子 | 把请求改成将来时："Update the API / Add tests / Update documentation"——没有发现了什么、为什么是这些文件、哪个契约先变、什么能并行 |
| 3 | 每个工作项的五个承诺 | Identifier（稳定引用）、Change（最小行为/契约变更）、Evidence（支撑它的仓库事实）、Dependencies（必须先成立的工作）、Proof（关闭该项的精确检查） |
| 4 | 先定契约，再做实现 | 多个 surface 依赖同一行为时先定义行为；测试、实现、文档、集成共享一个契约，而不是各自发明四个版本 |
| 5 | 证据要能改变计划 | 已有 helper 可删掉新抽象；兼容性测试会强制加迁移步骤；部署约束把 schema 变更移到别的任务；公开响应类型改变实现与文档的顺序。讲义："If the evidence cannot change the plan, it is probably not evidence for that decision." |
| 6 | 为中断而设计 | 工作项要小到另一个会话能判断：哪项完成了、跑了哪个 proof、改了哪些产物、哪些依赖已解锁、下一个安全项是什么；计划要存放在工作旁边，而不是聊天里的勾选框 |
| 7 | 六条拒绝规则 | ID 重复、无证据、无 proof、依赖未知项、存在环——这五条是机械检查；"第一个不可逆动作发生在相关不确定性解决之前"需要判断 |
| 8 | 执行波次（waves） | 用拓扑排序按层分组：同一波内的项依赖都已完成、彼此独立，可以并行；示例得到 `[['contract'], ['docs', 'implementation'], ['integration']]` |
| 9 | 环意味着什么 | 依赖环通常暴露了一个未解决的产品分歧或错误的拆分（讲义练习 2） |
| 10 | 本节代码的边界 | 环报错列出**所有剩余项**而非环本身；空字符串证据可通过；不可逆动作检查、工作项状态字段都没有实现；示例中 "Reject normalized duplicates" 悄悄决定了第 43 节留下的大小写 unknown |

### 核心技能（能动手做到）

- [ ] 把第 43 节的 task frame 转成带 ID、变更、证据、依赖、proof 的工作项列表
- [ ] 手算 `execution_waves`：给定依赖关系写出每一波的内容和顺序（波内按字母序）
- [ ] 读懂 `validate()` 的五条机械检查，并解释为什么"存在未知依赖时跳过环检测"
- [ ] 写一个能找出**真正的环路径**（如 `a -> b -> a`）的 DFS 函数
- [ ] 为不可逆工作项（迁移）加上"必须先有人类批准项"的检查
- [ ] 实现"给定已完成集合，求下一批安全可执行项"，支撑会话中断后的恢复

---

## 二、基础自测（选择题）

**Q1.** 讲义认为执行计划与待办清单的本质区别是：

- A. 计划的排版更清晰、更好看
- B. 计划每一步写得更详细
- C. 计划用将来时描述要做的事
- D. 计划是一张依赖图：每个变更都有理由（证据），每个终点都有证明（proof）

**Q2.** 运行 `python3 code/main.py`，示例计划的 `waves` 是：

- A. `[['contract'], ['implementation'], ['docs'], ['integration']]`
- B. `[['contract'], ['docs', 'implementation'], ['integration']]`
- C. `[['contract', 'docs', 'implementation', 'integration']]`
- D. `[['implementation', 'docs'], ['contract'], ['integration']]`

**Q3.** 讲义列出的六条拒绝规则中，哪一条"需要判断、应被显式指出"，而不是机械检查？

- A. 第一个不可逆动作发生在相关不确定性解决之前
- B. 工作项 ID 重复
- C. 依赖图中存在环
- D. 依赖了不存在的工作项

**Q4.** 有三个工作项：`a` 依赖 `b`，`b` 依赖 `a`，`c` 依赖 `a`（证据、proof 都齐全）。`validate()` 实际返回：

- A. `['dependency cycle among: a, b']`
- B. `['c depends on unknown items: a']`
- C. `['dependency cycle among: a, b, c']`
- D. `[]`

**Q5.** `validate([WorkItem("a", "a", ("",), (), "t")])`（证据是一个空字符串）实际返回：

- A. `['a has no repository evidence']`
- B. `[]`
- C. `['a has no proof command']`
- D. 抛出 `ValueError`

**Q6.** 讲义说"如果证据无法改变计划，它大概就不是这个决定的证据"。下列哪一条是**真正能改变计划**的证据？

- A. 列出本次阅读过的 12 个文件名
- B. 统计 `app/accounts.py` 有 240 行
- C. 引用 README 中的项目简介
- D. 发现 `app/validators.py:12` 已有 `normalize_email()`，于是删掉计划中"新建规范化模块"的工作项

**Q7.** 关于"为中断而设计"，下列做法最符合讲义的是：

- A. 计划存放在工作旁边，工作项足够小，使新会话能判断哪项已完成、跑过哪个 proof、改了哪些产物、哪些依赖已解锁、下一个安全项是什么
- B. 在聊天记录里用勾选框标记进度
- C. 把整个任务作为一个大工作项，避免中途状态不一致
- D. 只记录最后执行到的那一步

**Q8.** 绕过 `validate()`，直接调用 `execution_waves`，传入两个 ID 都是 `"a"` 的工作项（第一个无依赖，第二个依赖 `"b"`）和一个无依赖的 `"b"`。实际结果是：

- A. 抛出 `ValueError: work item ids must be unique`
- B. `[['a', 'b'], ['a']]`
- C. `[['b'], ['a']]`——第一个 `a` 被字典静默覆盖丢失
- D. `[['a', 'b']]`

---

## 三、动手 / 代码题

**Q9.** `execution_waves` 发现没有可执行项时这样报错：

```python
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise ValueError(f"dependency cycle among: {cycle}")
```

1. 用 Q4 的例子说明这个报错为什么会误导人。
2. 写一个 `find_cycle(items)`，返回一条真正的环路径（如 `['a', 'b', 'a']`），没有环时返回 `None`。

**Q10.** 审视示例计划本身：

```python
WorkItem("contract", "Define duplicate-email behavior", ("tests/test_accounts.py:44",), (), "review contract"),
WorkItem("implementation", "Reject normalized duplicates", ("app/accounts.py:18",), ("contract",), "python3 -m unittest tests.test_accounts"),
```

1. 对照讲义"Proof: The exact check that closes the item"，`contract` 的 proof 有什么问题？
2. 第 43 节的 task frame 留下了 unknown "Whether email comparison is case-insensitive"。本节的 `implementation` 写的是 "Reject **normalized** duplicates"。这说明了什么？
3. 讲义练习 1 要求"Add a migration item that requires explicit human approval"。如果直接加一个依赖 `contract` 的 `migration` 项，它会落在第几波？为什么这违反了第六条拒绝规则？请给出修正后的依赖结构和它的波次。

**Q11.** 讲义要求计划可恢复："which dependencies are now unblocked; what the next safe item is"。请写 `next_safe_items(items, completed)`，返回所有"自身未完成、依赖全部完成"的工作项 ID（排序后），并给出示例计划在 `completed` 依次为 `{}`、`{"contract"}`、`{"contract", "docs"}`、`{"contract", "docs", "implementation"}` 时的输出。

**Q12.** 讲义练习 5："Render the plan as Markdown while keeping JSON as the source of truth." 请写 `render_markdown(document)`：输入是 `outputs/evidence-plan.json` 解析出的字典，按波次输出每个工作项的变更、依赖、证据和 proof；并说明为什么要以 JSON 而不是 Markdown 为唯一真相来源。

---

## 四、面试高频题

**Q13.**（基础必考）让 agent 在改代码前先出计划，一个"好计划"应该满足什么条件？你审批计划时看哪三点？

**Q14.**（原理深挖）执行波次是怎么算出来的？它和 PERT/CPM 中的关键路径有什么区别？依赖环在工程上通常意味着什么？

**Q15.**（工程实践）agent 会话经常在中途被打断（超时、上下文耗尽、人工中止）。你如何设计计划的存储格式和工作项粒度，让新会话能安全地继续？

**Q16.**（场景设计）任务是"给用户表的 email 加唯一约束并在 API 返回 409"。请画出依赖图，标出哪些项可以并行、哪些项是不可逆的、应该在哪里放人类审批点。

**Q17.**（追问型）你说"每个工作项都要有证据"。如果 agent 编造证据（比如写了一个不存在的 `docs/api.md:72`），你的计划校验能发现吗？怎么加强？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义开篇："A plan is not a prettier to-do list. It is a dependency graph in which every change has a reason and every terminal node has proof." A、B 只是形式上的改进；C 恰恰是讲义批评的弱计划特征（"Weak plans repeat the request in future tense"）。

### Q2 — 答案：B

实测输出与仓库中 `outputs/evidence-plan.json` 一致。`contract` 无依赖，第一波；`implementation`、`docs` 都只依赖 `contract`，第二波一起就绪，`sorted` 后 `docs` 在前；`integration` 依赖二者，第三波。讲义："Implementation and documentation can proceed together after the contract is fixed. Integration waits for both." A 把可以并行的两项串行化了；C 忽略了依赖；D 违反了依赖顺序。

### Q3 — 答案：A

讲义："The first five checks are mechanical. The last requires judgment and should be called out explicitly." 判断"哪个动作不可逆、它依赖哪个不确定性"需要理解业务语义（迁移、发布、删除数据、对外发邮件），无法仅从图结构推出。B、C、D 都可以由程序判定，本节代码也都实现了；A 没有实现（见 Q10）。

### Q4 — 答案：C

实测 `['dependency cycle among: a, b, c']`。第一轮：`a` 等 `b`、`b` 等 `a`、`c` 等 `a`，没有任何项就绪，代码把 `remaining` 中的**全部**项都列为"环成员"。但 `c` 并不在环里，它只是被环堵住的下游。A 是理想的报错（见 Q9）；B 错，`a` 是已知项；D 错，环一定会被检测到。

### Q5 — 答案：B

实测 `[]`。检查是 `if not item.evidence:`，判断的是元组是否为空；`("",)` 是含一个元素的非空元组，所以通过。同样 `("   ",)`、`("trust me",)` 也能通过。对比 proof 的检查用了 `item.proof.strip()`，证据却没有逐条 `strip()`——两者标准不一致。修法：`if not any(e.strip() for e in item.evidence):`，再进一步检查 `路径:行号` 格式。

### Q6 — 答案：D

讲义列出的第一种情况就是 "An existing helper removes a planned new abstraction." D 直接删掉了一个工作项。A、B、C 都是"装饰性"的信息，不论内容如何计划都不会变，按讲义的标准它们不是这个决定的证据。

### Q7 — 答案：A

讲义 "Design for Interruption" 列出的五个可判断项与 A 一一对应，并且明确说 "Do not encode state only in checked boxes inside a chat. Store the plan next to the work." B 正是被否定的做法；C 让"完成到哪了"无法判断；D 丢失了已完成产物和 proof 的信息。注意：本节 `WorkItem` 并没有 status/artifacts 字段，可恢复性需要自己扩展（见 Q11）。

### Q8 — 答案：C

实测 `[['b'], ['a']]`。`remaining = {item.id: set(item.depends_on) for item in items}` 是字典推导式，重复的键后者覆盖前者，第一个 `a`（无依赖）被静默丢弃。`execution_waves` 自身不检查 ID 唯一性，只有 `validate()` 检查；`plan_document` 在有 issue 时不会调用 `execution_waves` 输出波次，所以正常流程不会出错，但直接调用这个函数的代码会得到错误的计划。A 是 `validate` 的消息而不是 `execution_waves` 的异常。

### Q9 — 参考答案

1. 对 `a↔b` 加下游 `c` 的例子，报错是 `dependency cycle among: a, b, c`。读者会以为三者构成环，可能去拆 `c` 的依赖——而 `c` 完全正常。项目大时，一个小环会让几十个下游项都被列出来，真正的环被淹没。
2. 参考实现（DFS 三色标记，已实际运行验证：对 Q4 的例子输出 `a -> b -> a`，对示例计划输出 `None`）：

```python
def find_cycle(items):
    graph = {i.id: list(i.depends_on) for i in items}
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    stack: list[str] = []

    def dfs(n):
        color[n] = GREY
        stack.append(n)
        for d in graph.get(n, []):
            if color.get(d) == GREY:                 # 回到正在访问的祖先 → 有环
                return stack[stack.index(d):] + [d]
            if color.get(d) == WHITE:
                found = dfs(d)
                if found:
                    return found
        color[n] = BLACK
        stack.pop()
        return None

    for n in sorted(graph):                          # sorted 让结果可复现
        if color[n] == WHITE:
            cycle = dfs(n)
            if cycle:
                return cycle
    return None
```

要点：GREY 表示"在当前递归栈中"，遇到 GREY 节点即发现回边；`stack[stack.index(d):]` 截出环上的节点。在 `execution_waves` 中可以改为 `raise ValueError("dependency cycle: " + " -> ".join(find_cycle(items)))`，同时单独列出"被环阻塞的下游项"。递归深度在极大图上可能超限，可改为显式栈的迭代版本。

### Q10 — 参考答案

1. `"review contract"` 不是一个精确的检查：谁来 review、通过的标准是什么、结果记录在哪里都不清楚，它和讲义批评的 "Tests pass" 一样空泛。更好的 proof 是一个可执行的契约测试，例如"新增 `test_duplicate_email_returns_409`，在实现之前运行它应当失败（红），实现后通过（绿）"，或者"契约文档 `docs/contracts/duplicate-email.md` 经 owner 批准，批准记录在 PR 中"。代码的 `validate` 只检查 proof 非空，所以无法发现这个问题。
2. 第 43 节把"邮件比较是否大小写不敏感"列为 unknown，讲义倾向于把这类改变产品行为的问题视为 human unknown。本节的 `implementation` 却直接写成"拒绝**规范化后**重复的邮件"——计划**悄悄回答了一个尚未被授权回答的问题**，这正是第 43 节说的"assumption 是对缺口的不受控回答"。正确做法是在 `implementation` 之前加一个决策项（由人批准规范化规则），或在 `contract` 项的证据/proof 中明确引用这个决定。
3. 实测：在示例中加 `WorkItem("migration", "Add unique index on lower(email)", ..., ("contract",), ...)`，波次变为 `[['contract'], ['docs', 'implementation', 'migration'], ['integration']]`——迁移落在**第二波**，与实现并行，而"是否按小写唯一"还没人决定。迁移在生产环境中通常是不可逆或代价很高的，这正违反了第六条："the first irreversible action occurs before the relevant uncertainty is resolved"。

修正：增加审批项，并让迁移和实现都依赖它：

```python
appr = WorkItem("approve-normalization", "Human decides case-insensitive uniqueness",
                ("tests/test_accounts.py:44",), ("contract",), "decision recorded in decisions/0001.md")
impl = WorkItem("implementation", "Reject normalized duplicates",
                ("app/accounts.py:18",), ("contract", "approve-normalization"), "python3 -m unittest tests.test_accounts")
mig  = WorkItem("migration", "Add unique index on lower(email)",
                ("migrations/0006_accounts.py:1",), ("approve-normalization",), "python3 manage.py migrate --check")
# integration 改为依赖 implementation、docs、migration
```

实测波次：`[['contract'], ['approve-normalization', 'docs'], ['implementation', 'migration'], ['integration']]`。文档可以与审批并行（文档写的是已确定的 409 契约），而实现与迁移要等人类决定之后。还可以加一个机械检查：被标记为不可逆的项，其祖先中必须包含一个审批项；对原始插法，这个检查实测返回 `['migration is irreversible but no approval item precedes it']`。

### Q11 — 参考答案

```python
def next_safe_items(items: list[WorkItem], completed: set[str]) -> list[str]:
    return sorted(
        i.id for i in items
        if i.id not in completed and set(i.depends_on) <= set(completed)
    )
```

实测输出：

| `completed` | `next_safe_items` |
|-------------|------------------|
| `{}` | `['contract']` |
| `{'contract'}` | `['docs', 'implementation']` |
| `{'contract', 'docs'}` | `['implementation']` |
| `{'contract', 'docs', 'implementation'}` | `['integration']` |

与 `execution_waves` 的区别：波次是"假设全部按计划完成"时的静态分层；`next_safe_items` 是根据**真实完成情况**动态计算的，第三行就体现了这一点——`docs` 先完成，`integration` 仍然要等 `implementation`。要让它在中断后可用，`completed` 必须来自持久化的状态：给每个工作项加 `status`、`proof_ran_at`、`artifacts` 字段，存在仓库里的 `evidence-plan.json` 中；判断"完成"时以 proof 的真实记录（第 37 节 feedback record）为准，而不是 agent 的自述。

### Q12 — 参考答案

```python
def render_markdown(doc: dict) -> str:
    lines = [f"# Execution plan ({doc['status']})", ""]
    by_id = {it["id"]: it for it in doc["items"]}
    for n, wave in enumerate(doc["waves"], 1):
        lines.append(f"## Wave {n}")
        for item_id in wave:
            it = by_id[item_id]
            deps = ", ".join(it["depends_on"]) or "none"
            lines.append(f"- **{it['id']}**: {it['change']} (after: {deps})")
            lines.append(f"  - evidence: {', '.join(f'`{e}`' for e in it['evidence'])}")
            lines.append(f"  - proof: `{it['proof']}`")
        lines.append("")
    if doc["issues"]:
        lines += ["## Issues", *[f"- {i}" for i in doc["issues"]]]
    return "\n".join(lines).rstrip() + "\n"
```

对实际生成的 `evidence-plan.json` 运行，输出三个小节 "Wave 1 / Wave 2 / Wave 3"，第二波下依次是 `docs` 和 `implementation`，每项带依赖、证据和 proof（已实际运行验证）。注意 blocked 计划的 `waves` 为空，此时应改为按 `items` 原顺序列出并突出 Issues 小节。

为什么 JSON 是唯一真相来源：

- 机器可读：下一节的委派、gate、恢复逻辑都要读它；Markdown 难以可靠解析；
- 单一来源避免漂移：人改了 Markdown 而 JSON 没变，两者就会矛盾；Markdown 应当始终是"生成物"，可以在 CI 中检查"重新渲染结果与提交的 Markdown 一致"；
- 讲义："It becomes the delegation contract in the next lesson."——契约必须是结构化数据。

### Q13 — 参考回答要点

- **好计划的条件**：是一张依赖图；每个工作项有稳定 ID、最小变更、仓库证据、依赖、一个明确的 proof；先定契约再做实现；不可逆动作排在相关不确定性解决之后；工作项小到可以中断恢复；存放在仓库中。
- **审批时看三点**（讲义 Use It）：
  1. 每个路径和行为主张都有仓库收据；
  2. 每个工作项有一个清晰的完成证明；
  3. 图把昂贵或不可逆的工作推迟到它依赖的不确定性解决之后。
- 讲义原话："Approve the plan, not a vague promise to be careful."
- 加分点：一个工作项有两个 proof 命令通常说明它应该拆分（讲义练习 3）。

### Q14 — 参考回答要点

- **波次算法**：Kahn 拓扑排序的分层版本。维护 `remaining: id → 未完成依赖集合`；每轮取出所有依赖集合是"已完成集合"子集的项作为一波；加入已完成集合并从 `remaining` 删除；某一轮没有任何项就绪而 `remaining` 非空，说明存在环。时间复杂度本实现为 O(波数 × 项数)，对计划规模足够。
- **与 PERT/CPM 的区别**：代码文件头引用了 PERT（1958）和 CPM（1959），但只用了"依赖图 + 拓扑分层"这一部分。CPM 需要每项的工期，计算最早/最晚开始时间与浮动时间，找出决定总工期的关键路径；本节没有工期，波次只回答"什么可以并行"，不回答"哪条链决定完成时间"。
- **环的工程含义**：讲义练习 2 与 quiz："a hidden unresolved decision or bad decomposition"。例如"实现要等文档定下错误格式、文档要等实现确定字段"——其实缺的是一个"契约"节点，二者都应依赖它。
- 加分点：同一波内的项可并行，但前提是它们写的文件不重叠（下一节的隔离与 owned paths）。

### Q15 — 参考回答要点

- **存储**：计划以 JSON 存在仓库（如 `outputs/evidence-plan.json`），与代码一起提交；Markdown 只是渲染视图。
- **工作项字段**：除五个承诺外，增加 `status`（todo / in_progress / done / blocked）、`proof_ran_at`、`proof_exit_code`、`artifacts`（改动的文件）、`notes`。
- **粒度**：一个工作项一个 proof；一个会话内能完成；完成后仓库处于一致状态（测试通过），中断不会留下"半个变更"。
- **恢复流程**：新会话读取计划 → 用真实记录核对每个 done 项的 proof → 计算 `next_safe_items` → 选择一个开始；遇到 in_progress 项先检查其产物是否完整，必要时回滚到上一个一致点。
- **与 handoff 的配合**：会话结束时 handoff 包指向计划文件和最后一个 proof 记录（第 40 节）。
- 常见误区：只在聊天里维护进度；或把多个变更塞进一个工作项，导致"到底完成到哪"无法判断。

### Q16 — 参考回答要点

- **工作项与依赖**（示意）：
  1. `contract`：定义重复邮件行为（409、错误体格式），proof：契约测试先红；
  2. `decide-normalization`（人类审批）：大小写/空白规范化规则；依赖 `contract`；
  3. `audit-existing-data`：查询现有重复数据（只读），proof：查询结果记录；可与 2 并行；
  4. `docs`：API 文档写 409；依赖 `contract`；
  5. `implementation`：应用层查重；依赖 `contract`、`decide-normalization`；
  6. `migration`（不可逆）：清理/合并已有重复 + 加唯一索引；依赖 `decide-normalization`、`audit-existing-data`，并需单独的上线审批；
  7. `integration`：完整验收；依赖 4、5、6。
- **可并行**：2、3、4 在 `contract` 之后可并行；5 与 6 在决定之后可并行开发，但上线顺序需协调。
- **不可逆项**：迁移（尤其是合并或删除已有重复账户）；审批点放在 `decide-normalization` 和迁移上线前。
- 加分点：说明应用层检查无法防止并发竞态，数据库唯一约束才是最终保证；这也是迁移不能省略的原因。

### Q17 — 参考回答要点

- **当前代码发现不了**：`validate` 只检查证据元组非空，`"docs/api.md:72"` 是否存在、第 72 行是否与"409 响应"有关，都不验证；甚至空字符串也能通过（Q5）。
- **加强方法**：
  1. 格式检查：证据必须是 `路径:行号` 或命令收据；
  2. 存在性检查：在仓库根目录下检查文件存在、行号在范围内；
  3. 相关性检查：要求证据附带一段摘录（如该行文本），校验时比对文件内容是否匹配，防止"文件存在但内容无关"；
  4. 命令收据可重放：证据是命令输出时，校验器重跑命令并比对关键结果；
  5. 由不同角色复核（第 39 节 reviewer），抽查证据是否支撑对应的变更。
- 加分点：把"证据能否改变计划"作为评审问题——如果把这条证据删掉计划不变，它就是装饰。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 43 在 Agent 编写代码前界定任务](../../43-frame-the-task-before-code/docs/zh.md)：讲义列出的先修课；task frame 是本节计划的输入，其 unknowns 决定了计划中的审批点。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：每个工作项的 proof 最终落为 scope contract 的 acceptance criteria。
- [阶段 14 · 02 ReWOO 与 Plan-and-Execute：解耦 Planning](../../02-rewoo-plan-and-execute/docs/zh.md)：先规划再执行的 agent 架构。
- [阶段 14 · 11 结合 HTN 与演化搜索的 Planning](../../11-planning-htn-and-evolutionary/docs/zh.md)：任务分解与依赖结构的另一种视角。

### 本节被哪些后续内容用到
- [阶段 14 · 45 通过隔离与合并契约委派 Agent 任务](../../45-delegate-with-isolation/docs/zh.md)：讲义明确说 `outputs/evidence-plan.json` 会成为下一节的委派契约；同一波内的工作项可以交给并行 worker。
- [阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：计划中的状态与 proof 记录支撑跨会话恢复。
- [阶段 14 · 49 梳理假设，优先验证风险最高的一项](../../49-map-assumptions-and-risk/docs/zh.md)：按风险而非固定顺序排列工作（与讲义引用的 Boehm 螺旋模型同一思路）。
- [阶段 14 · 50 选择足以改变决策的最小实现范围](../../50-choose-the-smallest-testable-slice/docs/zh.md)：把工作项切到最小可验证的粒度。

### 延伸关键词
`dependency graph` · `topological sort` · `Kahn's algorithm` · `execution waves` · `cycle detection` · `PERT / CPM` · `critical path` · `spiral model` · `irreversible action` · `resumable plan` · `single source of truth` · `contract-first`
