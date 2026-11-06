# 测验 · ReWOO 与 Plan-and-Execute：解耦 Planning（ReWOO and Plan-and-Execute: Decoupled Planning）

> **阶段 14 · Agent 工程 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义机翻质量较差（如把 HotpotQA 译成"热锅QA"、Solver 译成"溶剂"），遇到读不通的地方请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | ReAct 的 token 问题 | 每一步的 prompt 都携带之前全部 thought/action/observation，单步 prompt 线性增长、总 token 随深度**二次**增长；工具中途失败时还要从错误里重推整个计划 |
| 2 | ReWOO 三角色 | Planner：问题 → 计划 DAG；Workers：按依赖顺序执行工具（可并行）；Solver：问题 + 计划 + 证据 → 最终答案 |
| 3 | 证据引用 `#E1` | 计划节点参数里的占位符，在**分派时**被替换为前序 worker 的输出；它同时定义了 DAG 的依赖边 |
| 4 | 论文数字 | Xu 等（arXiv:2305.18323，2023 年 5 月）：HotpotQA 上 token 约少 5 倍，同时准确率绝对提升 4 个百分点 |
| 5 | 更清晰的失败模式 | 某个 worker 失败只得到一个错误字符串，Solver 结合原计划看到它并可"优雅降级"；失败定位到**节点**而非**步骤** |
| 6 | Planner 蒸馏 | 因为 Planner 看不到 observation，它的输入只有问题，可以用 175B 教师的计划输出微调 7B 小模型做规划 |
| 7 | Plan-and-Execute | LangChain 2023 年 8 月对 ReWOO 的推广：先列步骤、逐步执行，并可加一个看到执行结果后修改计划的 **replanner** |
| 8 | Plan-and-Act | Erdogan 等（arXiv:2503.09572，ICML 2025）：用合成的显式计划数据训练 planner，面向 30–50 步以上的网页/移动端长程任务 |
| 9 | 模式选型 | 短任务/未知环境 → ReAct；工具已知、结构化、对 token 敏感 → ReWOO；需要中途改计划 → Plan-and-Execute；长程 → Plan-and-Act；值得付费搜索 → ToT/LATS |
| 10 | 从最简单开始 | 讲义引 Anthropic（2024 年 12 月）：一次工具调用 + 总结就别建 ReWOO；40 步研究任务也别只用 ReAct |

### 核心技能（能动手做到）

- [ ] 写出计划 DAG 的数据结构、引用替换（正则 `#E(\d+)`）、拓扑排序执行器和 Solver
- [ ] 把拓扑排序改造成"按层分组"，用线程池并行执行同一层的独立节点，并估算加速比
- [ ] 在执行前校验计划：无环、引用都能解析、工具都存在、参数符合 schema
- [ ] 处理 worker 失败：识别"错误字符串被当成证据继续传下去"的问题，实现跳过下游 / 触发 replanner
- [ ] 用公式解释 ReAct 总 token 为什么二次增长、ReWOO 为什么线性增长，并能用本节代码复现趋势
- [ ] 针对具体任务在 ReAct / ReWOO / Plan-and-Execute / Plan-and-Act 之间做出选择并说明理由

---

## 二、基础自测（选择题）

**Q1.** ReWOO 的三个角色及其分工是：

- A. Actor、Evaluator、Self-Reflection：执行、打分、写反思
- B. Generator、Critic、Refiner：生成、批评、改写
- C. Planner、Workers、Solver：一次性规划出 DAG、按依赖执行工具、汇总证据给出答案
- D. Thought、Action、Observation：在同一个流中交替出现

**Q2.** 讲义转述的 ReWOO 论文在 HotpotQA 上相对 ReAct 的结果是：

- A. token 约少 5 倍，准确率绝对提升约 4 个百分点
- B. token 约少 5 倍，但准确率下降约 4 个百分点
- C. token 约少 4 倍，准确率提升约 5 个百分点
- D. token 基本不变，但延迟降低 5 倍

**Q3.** 为什么说 ReAct 的 token 用量随步数"二次增长"？

- A. 因为每个工具的返回值长度随步数平方增长
- B. 因为 ReAct 每一步都要调用两次 LLM
- C. 因为注意力机制的计算量是序列长度的平方
- D. 因为第 i 步的 prompt 要携带前 i−1 步全部的 thought、action、observation（以及原始问题），单步长度线性增长，累加起来就是二次

**Q4.** 在本节 demo 中，计划节点 `E2` 的参数是 `{"query": "population of #E1"}`。执行时发生了什么？

- A. `topological` 把 `#E1` 替换为 `"Paris"`
- B. `run_workers` 在调用工具前用 `resolve_references` 把 `#E1` 替换为 `evidence["E1"]`（即 `"Paris"`），工具实际收到 `"population of Paris"`
- C. `fake_search` 自己识别 `#E1` 并去查 E1 的结果
- D. Solver 在最后一步才把 `#E1` 替换掉

**Q5.** ReWOO 论文能把 175B 的 Planner 蒸馏到 7B 小模型，关键原因是：

- A. 7B 模型的推理能力已经与 175B 相当
- B. Planner 需要处理的工具返回值很短
- C. Planner 不看 observation，输入只有问题本身，因此可以离线收集"问题 → 计划"对作为监督数据
- D. Solver 会纠正 Planner 的所有错误

**Q6.** 把 ReWOO 改造成 Plan-and-Execute，**最小**的改动是：

- A. 增加一个 replanner：在执行结果（尤其是出错时）回来后，让它看到 observation 并修订剩余计划
- B. 把 DAG 改成线性步骤列表
- C. 去掉 Solver，直接返回最后一个 worker 的输出
- D. 让 Planner 换成更大的模型

**Q7.** 运行本节代码打印 `ratio : 1.76x`，而论文说约 5 倍。正确的理解是：

- A. 这证明论文结论被夸大了，真实只有 1.76 倍
- B. 代码统计的就是真实 token 数，只是任务不同
- C. 无论任务多复杂，ReWOO 相对 ReAct 都固定节省 1.76 倍
- D. 这只是 3 步任务上按字符数的粗略估算；步数越多，ReAct 的二次增长使差距越大，它并没有复现论文的测量

**Q8.** 如果 Planner 生成的计划里，`E1` 的参数引用了不存在的 `#E9`，本节代码会：

- A. 把字面量 `#E9` 原样传给工具
- B. 在 `topological` 中抛出 `RuntimeError("cyclic plan or unresolved reference")`，一个工具都不会执行
- C. 跳过 E1，继续执行其他节点
- D. 交给 Solver 处理

---

## 三、动手 / 代码题

**Q9.** 讲义练习 1 要求并行执行独立节点。阅读本节的拓扑排序：

```python
def topological(plan: Plan) -> list[PlanStep]:
    resolved: list[PlanStep] = []
    known: set[str] = set()
    pending = list(plan.steps)
    while pending:
        progress = False
        rest: list[PlanStep] = []
        for step in pending:
            refs = REFERENCE_RE.findall(str(step.args))
            if all(f"E{r}" in known for r in refs):
                resolved.append(step)
                known.add(step.id)
                progress = True
            else:
                rest.append(step)
        ...
        pending = rest
    return resolved
```

1. 有人说"`while` 的每一轮就是一层，可以直接拿来并行"。对计划 `E1: search(capital of France)`、`E2: search(population of #E1)`、`E3: search(capital of Germany)`，第一轮 `for` 循环会把哪些节点放进 `resolved`？这个说法对吗？
2. 写一个 `levels(plan)` 返回按层分组的列表，并用线程池实现 `run_workers_parallel`。
3. 对一个 6 节点 DAG：`E1、E2` 独立；`E3←E1`、`E4←E2`；`E5←E3,E4`；`E6←E5`。若每个工具耗时相同，并行能把墙钟时间降到串行的多少？

**Q10.** 把 demo 计划中 E1 的工具名写错成 `"serch"`，其余不变。实际运行得到：

```text
E1 -> error: unknown tool 'serch'
E2 -> no result for "population of error: unknown tool 'serch'"
E3 -> unknown
FINAL: The capital of France is error: unknown tool 'serch'; rounded population is unknown.
```

1. 解释错误是怎样一路传播的。讲义说"Solver 会看到错误并优雅降级"，本节代码做到了吗？
2. 给出两处修复：执行前的计划校验，以及执行时对失败节点下游的处理。

**Q11.** `rounded_million` 工具：

```python
def rounded_million(text: str) -> str:
    m = re.search(r"([0-9]+\.?[0-9]*)", text)
    if not m:
        return "unknown"
    return f"{round(float(m.group(1)))} million"
```

不运行代码，写出下列输入的返回值，并指出各自的问题：`"1,634,567 people"`、`"2.5 million"`、`"3.5 million"`、`"error: 404 not found"`。然后给出修复版本。

**Q12.** 用本节的 `run_react_mock` 与 `run_rewoo` 做"token 直觉"实验：

1. 手算 demo 的 `react total = 873`：问题长度 57；三步的 `len(name)+len(str(args))` 分别是 `6+30`、`6+32`、`13+30`（args 依次为 `{'query': 'capital of France'}`、`{'query': 'population of Paris'}`、`{'text': '11.2 million metro'}`），observation 分别为 `Paris`（5）、`11.2 million metro`（18）、`11 million`（10），每步额外加 40。
2. `rewoo total = 495` 由 `planner 157 + worker 108 + solver 230` 组成。这个统计方式有哪些不公平之处？
3. 把计划扩成 n 个相同的 search 步骤，n = 1、3、10、30 时比值大约是多少？趋势说明什么？

---

## 四、面试高频题

**Q13.**（基础必考）ReWOO 和 ReAct 的核心区别是什么？ReWOO 在什么方面占优、付出了什么代价？

**Q14.**（原理深挖）"Reasoning WithOut Observation"为什么能让 Planner 被蒸馏到小模型？静态计划在哪些情况下会失效？Plan-and-Execute 和 Plan-and-Act 分别如何弥补？

**Q15.**（工程实践）LLM 生成的计划 DAG 在执行前后需要做哪些校验和保护？请给出一个可以落地的清单。

**Q16.**（场景设计）为下面四个任务各选一种模式并说明理由：①"把这段话翻译成英文"；②"对比 5 家公司的财报关键指标并出表格"；③"在一个陌生的内部系统里排查一个偶发 bug"；④"在电商网站上完成一个 40 步的比价下单流程"。

**Q17.**（追问型）Plan-and-Execute 的 replanner 什么时候触发？如何防止它变成"每一步都重规划"、退化成高成本的 ReAct？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Planner: user_question -> [plan_dag]；Workers: [plan_dag] -> [evidence]（tool calls, possibly parallel）；Solver: user_question, plan_dag, evidence -> final_answer"。A 是 Reflexion（第 03 节）的三组件；B 接近 Self-Refine / CRITIC（第 05 节）；D 是 ReAct（第 01 节）。

### Q2 — 答案：A

讲义："On HotpotQA the paper measures ~5x fewer tokens while scoring +4 absolute accuracy." 关键在于**省 token 的同时准确率没有下降反而上升**，所以 B 错；C 把两个数字对调了；D 讲的是延迟，论文的核心指标是 token 效率。

### Q3 — 答案：D

设原始 prompt 长 p，每一步给 history 增加 h，则第 i 步的 prompt 长约 `p + (i−1)h`，n 步总和约 `np + h·n(n−1)/2`，是 n 的二次函数。讲义："Each intermediate step also redundantly includes the original prompt." C 是 Transformer 单次前向的计算复杂度，与"多次调用的 token 总量"是两回事；A、B 都与 ReAct 的结构无关。

### Q4 — 答案：B

```python
def run_workers(plan: Plan, tools: ToolRegistry) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for step in topological(plan):
        bound_args = {k: resolve_references(v, evidence) for k, v in step.args.items()}
        evidence[step.id] = tools.dispatch(step.tool, bound_args)
    return evidence
```

`topological` 只用 `#E\d+` **判断依赖**并排序，不做替换（A 错）；替换发生在每个节点**分派之前**，所以讲义说"substituted with prior worker output at dispatch time"。C：工具完全不知道引用的存在；D：Solver 用的是 `{E1}` 这种 `str.format` 占位符，和 `#E1` 是两套机制。

### Q5 — 答案：C

ReWOO = Reasoning WithOut Observation。Planner 的输出只取决于问题和工具目录，不依赖运行时的工具结果，因此"问题 → 计划"可以作为干净的监督样本，从大模型批量采集后微调小模型（讲义："you can fine-tune a 7B model on planner outputs from a 175B teacher"）。A 说反了——正是因为任务被简化，小模型才够用；B 无关；D 错，Solver 只能利用证据，无法修复错误的计划结构。

### Q6 — 答案：A

讲义：Plan-and-Execute "an optional replanner can revise after observing results. This is closer to ReAct than ReWOO (the replanner brings observations back into planning)"。B 恰好是讲义练习 5 讨论的 Plan-and-Act 轨迹形状，与是否有 replanner 无关；C、D 都没有引入"观察 → 修改计划"的回路。

### Q7 — 答案：D

`run_react_mock` 和 `run_rewoo` 统计的都是**字符数**，并用"每步加 40"粗略代替 thought 的长度；任务只有 3 步。测验 Q12 中把步数扩到 30，比值会升到约 11.7 倍——这说明比值强烈依赖步数和常数，既不能拿来否定论文（A），也不是固定值（C），更不是真实 token（B）。代码最后一行自己也写着 "toy approximates the shape"。

### Q8 — 答案：B

`topological` 中 E1 的引用 `E9` 永远不会进入 `known`，第一轮 `progress` 为 `False`，立即抛出 `RuntimeError("cyclic plan or unresolved reference")`。实测自引用 `#E1 → E1` 和悬空引用 `#E9` 都得到这条错误。这是"执行前就失败"的好性质，但错误信息没有指出**是哪条边**出了问题——配套 skill 文件要求"Emit the specific edge that fails"。注意：A 描述的情形在另一种场景下确实会发生——引用写在嵌套结构里（如 `{"items": ["#E1"]}`）时，`topological` 用 `str(step.args)` 能看到依赖，但 `resolve_references` 只替换顶层字符串，工具收到的是字面量 `['#E1']`（已实测）。

### Q9 — 参考答案

1. 第一轮 `for` 循环依次检查 E1（无引用，放入并把 `E1` 加入 `known`）、E2（此时 `E1` 已在 `known` 中，**同一轮**就被放入）、E3（放入）。实测 `topological` 返回 `['E1', 'E2', 'E3']`，且三者都在第一轮完成。所以"一轮 = 一层"的说法**不对**：`known` 在循环内即时更新，同一轮里可能混入有依赖关系的节点，直接并行会让 E2 在 E1 完成前执行。
2. 参考实现（已运行验证）：

```python
from concurrent.futures import ThreadPoolExecutor

def levels(plan):
    out, known, pending = [], set(), list(plan.steps)
    while pending:
        layer = [s for s in pending
                 if all(f"E{r}" in known for r in REFERENCE_RE.findall(str(s.args)))]
        if not layer:
            raise RuntimeError("cyclic plan or unresolved reference")
        out.append(layer)
        known |= {s.id for s in layer}          # 整层算完后才更新 known
        pending = [s for s in pending if s not in layer]
    return out

def run_workers_parallel(plan, tools, max_workers=8):
    evidence = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for layer in levels(plan):
            futs = {s.id: pool.submit(tools.dispatch, s.tool,
                                      {k: resolve_references(v, evidence) for k, v in s.args.items()})
                    for s in layer}
            for sid, f in futs.items():
                evidence[sid] = f.result()
    return evidence
```

3. 分层结果（实测）：`[['E1','E2'], ['E3','E4'], ['E5'], ['E6']]`，共 4 层。每个工具耗时相同时，墙钟时间从 6 个单位降到 4 个单位，即串行的 **2/3**。实测中只给 `search` 加了 0.2 秒延迟：串行 0.80 秒（4 次 search），并行 0.41 秒（2 层 search），结果完全一致。加速比的上限由**关键路径长度**（DAG 最长链）决定，而不是节点数。

### Q10 — 参考答案

1. **传播链**：`dispatch` 把未知工具转成字符串 `error: unknown tool 'serch'` 存为 E1 的证据；E2 的 `#E1` 被替换成这段错误文本，`fake_search` 查不到，返回 `no result for ...`；E3 的 `#E2` 被替换为它，`rounded_million` 找不到数字返回 `unknown`；`ScriptedSolver` 只是 `template.format(**evidence)`，把错误字符串原封不动拼进了最终答案。讲义描述的"Solver 在上下文中看到错误、优雅降级"在本节代码里**并没有实现**——脚本化 Solver 不做任何判断。更糟的情形：如果错误文本里恰好含数字（例如 `error: 404 not found`），`rounded_million` 会返回 `404 million`，把错误伪装成看似合理的答案（已实测）。
2. **修复**（已运行验证）：
   - 执行前校验：遍历节点，检查工具名在注册表中、每个 `#E<k>` 都有对应的节点、能完成拓扑排序。对本例输出 `["E1: unknown tool 'serch'"]`，计划直接打回 Planner 重写，一个工具都不执行。
   - 执行时隔离：记录失败节点集合，若某节点依赖的节点失败，就不再调用工具，而是记为 `skipped: depends on failed [...]`。本例得到 `E2: skipped: depends on failed ['E1']`、`E3: skipped: depends on failed ['E2']`。随后 Solver 可以如实回答"无法确定"，或触发 replanner（这就是 Plan-and-Execute，讲义练习 2）。

### Q11 — 参考答案

| 输入 | 原函数输出 | 问题 |
|------|-----------|------|
| `"1,634,567 people"` | `1 million` | 正则遇到逗号就停，只抓到 `1`；而且没区分"原始人数"和"以百万为单位"，正确应为 `2 million` |
| `"2.5 million"` | `2 million` | Python 的 `round` 是银行家舍入（四舍六入五成双），`round(2.5) = 2` |
| `"3.5 million"` | `4 million` | 同上，`round(3.5) = 4`，与 2.5 的结果放在一起看就很反直觉 |
| `"error: 404 not found"` | `404 million` | 把上游的错误文本当数据解析，错误被伪装成答案 |

修复版本（已运行验证：上述四个输入分别得到 `2 million`、`3 million`、`4 million`、`error: upstream evidence failed`）：

```python
from decimal import Decimal, ROUND_HALF_UP

def rounded_million_v2(text: str) -> str:
    if text.startswith("error"):
        return "error: upstream evidence failed"
    m = re.search(r"(\d[\d,]*\.?\d*)\s*(million)?", text)
    if not m:
        return "unknown"
    value = Decimal(m.group(1).replace(",", ""))
    if m.group(2) is None:                      # 没写 million，按原始人数换算
        value = value / Decimal(1_000_000)
    return f"{value.quantize(Decimal('1'), rounding=ROUND_HALF_UP)} million"
```

启示：ReWOO 中 worker 之间传递的是**字符串**，下游工具必须对上游的格式和错误做防御；更稳妥的做法是让证据带类型（如 `{"ok": bool, "value": ...}`），这也是配套 skill 要求"引用替换后的类型要匹配工具 schema"的原因。

### Q12 — 参考答案

1. 第 i 步计入 `问题长度 + 已有 history + 本步 name+args`，执行后 history 增加 `name+args+obs+40`：
   | 步骤 | 本步计入 | 执行后 history |
   |------|---------|---------------|
   | 第 1 步 | `57 + 0 + 6 + 30 = 93` | `0 + (6 + 30 + 5 + 40) = 81` |
   | 第 2 步 | `57 + 81 + 6 + 32 = 176` | `81 + (6 + 32 + 18 + 40) = 177` |
   | 第 3 步 | `57 + 177 + 13 + 30 = 277` | `177 + (13 + 30 + 10 + 40) = 270` |
   | 收尾（最后一次"写答案"的调用） | `57 + 270 = 327` | — |

   合计 `93 + 176 + 277 + 327 = 873`，与实际运行输出一致（各步数值已用脚本逐一打印核对）。
2. 不公平之处：
   - `worker_chars = 108` 被算了两次（单独一次，又包含在 `solver_chars = 57 + 108 + 65` 里）；
   - ReWOO 的 worker 多数是**纯工具执行**，不消耗 LLM token，论文的节省很大程度来自这里；代码却把它们当作 prompt 计入；
   - 两边都没计 system prompt、工具描述和 few-shot 示例，而这部分在 ReAct 中**每一步都重复**，在 ReWOO 中只出现两次——真实差距会更大；
   - ReAct 的 thought 只用常数 40 近似。
3. 实测（每步都是 `search("capital of France")`）：

| n | ReAct 字符 | ReWOO 字符 | 比值 |
|---|-----------|-----------|------|
| 1 | 231 | 225 | 1.03 |
| 3 | 822 | 449 | 1.83 |
| 10 | 5,442 | 1,233 | 4.41 |
| 30 | 40,512 | 3,473 | 11.66 |

ReAct 是二次增长，ReWOO 是线性增长，比值随步数近似线性上升。所以"5 倍"不是常数，而是取决于任务深度；单步任务几乎没有优势——这也呼应了配套 skill 的建议："计划少于 3 步时推荐 ReAct"。

### Q13 — 参考回答要点

- **结构差异**：ReAct 每一步"想 → 做 → 看"交替，计划隐含在逐步推理中；ReWOO 把推理与观察解耦，一次性生成带 `#E` 引用的计划 DAG，worker 执行，Solver 汇总。
- **ReWOO 的优势**：
  - token 效率：LLM 只调用两次（Planner + Solver），不会在每步重复携带历史；论文 HotpotQA 约少 5 倍 token，准确率 +4；
  - 可并行：独立节点同层并发；
  - 失败定位清楚：错误落在具体节点；
  - Planner 可蒸馏到小模型。
- **代价**：计划是静态的，无法根据中间结果调整策略；对未知环境、需要探索的任务不适用；Planner 一旦出错，整条计划都会受影响。
- 加分点：指出现实中常见的折中是 Plan-and-Execute（带 replanner），以及"计划可审计"带来的安全好处——执行前可以审查计划里有没有危险工具调用。

### Q14 — 参考回答要点

- **可蒸馏的原因**：Planner 的输入是问题 + 工具目录，输出是结构化计划，不依赖运行时环境；可以离线批量生成"问题 → 计划"监督数据，用大模型做教师、小模型做学生；计划质量可以通过"执行后 Solver 能否答对"来打分（讲义练习 4）。
- **静态计划失效的场景**：
  - 下一步做什么取决于上一步的结果（例如先搜索、按结果决定翻哪一页）；
  - 工具失败或返回意外格式，需要换路径；
  - 环境状态会变化（网页、GUI、长程任务）；
  - 步数很多，一次性规划容易遗漏或失去一致性。
- **弥补方式**：
  - Plan-and-Execute：执行后由 replanner 读取 observation 修订剩余计划，保留大部分 token 节省；
  - Plan-and-Act：用合成的显式计划轨迹数据训练 planner，让它在 30–50 步以上的 WebArena 类任务中保持连贯（讲义："where a single ReAct trajectory loses coherence"）。
- 常见误区：认为"Planner 不看 observation"意味着整个系统不看 observation——Solver 和 replanner 都要看。

### Q15 — 参考回答要点

- **执行前（静态校验）**：
  - 结构：节点 id 唯一，拓扑排序成功（无环），每个 `#E<k>` 都有生产者，并报告具体哪条边失败；
  - 工具：每个工具名都在目录中，**不允许**模型发明工具；
  - 参数：按工具 schema 校验参数类型和必填项，引用替换后的类型也要匹配（字符串 vs 整数）；
  - 安全：含破坏性工具时要求人工审批节点（配套 skill 的拒绝规则）；
  - 规模：节点数、并行度上限。
- **执行时**：
  - 按层并行，设置单节点超时与重试（只对幂等工具重试）；
  - 引用替换需递归处理嵌套参数（本节代码只处理顶层字符串）；
  - 失败节点的下游标记为 skipped，不把错误字符串当证据；
  - 证据带结构（ok/value/error），超长输出截断。
- **执行后**：Solver 明确区分"有证据支持的结论"和"因失败而缺失的部分"；必要时触发 replanner；记录每个节点的 trace 便于回放。
- 加分点：把校验器做成独立函数，同时用于 Planner 的自我修正循环（校验失败 → 带着错误信息重新规划）。

### Q16 — 参考回答要点

| 任务 | 推荐 | 理由 |
|------|------|------|
| ① 翻译一段话 | 不用 agent，直接一次 LLM 调用 | 讲义引 Anthropic："从最简单的方案开始"，没有工具需求就不需要循环 |
| ② 5 家公司财报对比 | ReWOO | 工具已知（查财报、抽取指标），5 家公司的检索相互独立可并行，结构固定，对 token 敏感 |
| ③ 陌生系统里排查偶发 bug | ReAct（必要时加 Reflexion/搜索） | 环境未知，下一步高度依赖上一步的观察，需要反应式处理异常 |
| ④ 40 步电商比价下单 | Plan-and-Act（或 Plan-and-Execute + replanner），并配人工确认 | 长程网页任务，单条 ReAct 轨迹在 30–50 步后容易失去连贯；下单是不可逆操作，需要审批 |

- 加分点：说明模式可以组合，例如 ② 的每个子任务内部用短 ReAct，外层用 ReWOO 编排；④ 中付款前加 human-in-the-loop。

### Q17 — 参考回答要点

- **触发条件**（由弱到强）：
  - worker 返回错误或超时；
  - 证据与计划假设不符（例如检索结果为空、格式不对）；
  - 到达预设的检查点（例如每完成一个阶段）；
  - Solver 判断现有证据不足以回答。
- **防止退化**：
  - 默认只在失败或检查点时触发，而不是每一步；
  - 设 replan 次数上限和总 token/成本预算；
  - replanner 只修订**剩余**计划，已成功节点的证据保留复用；
  - 对相同失败重复出现的情况直接中止并上报，而不是无限重试。
- **与 ReAct 的区别**：ReAct 每一步都把全部历史交给模型；Plan-and-Execute 大部分步骤由执行器机械执行，模型只在少数节点介入，因此保留了大部分 token 节省，同时又有纠错能力。
- 常见误区：replanner 看到失败后生成与原计划几乎相同的新计划，陷入循环——应把失败原因作为显式约束写进 replan 的 prompt（与第 03 节 Reflexion 的思路相通）。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：ReWOO 是对 ReAct 循环的解耦改造，要先理解 ReAct 的 token 增长方式。
- [阶段 11 · 02 Few-Shot, Chain-of-Thought, Tree-of-Thought](../../../11-llm-engineering/02-few-shot-cot/docs/zh.md)：Planner 本质上是一次结构化的 chain-of-thought。
- [阶段 13 · 03 并行 Tool Calls 与工具调用中的 Streaming](../../../13-tools-and-protocols/03-parallel-and-streaming-tool-calls/docs/zh.md)：同层节点的并行执行。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../../13-tools-and-protocols/04-structured-output/docs/zh.md)：让 Planner 输出可校验的计划 JSON。

### 本节被哪些后续内容用到
- [阶段 14 · 03 Reflexion：语言反馈驱动的 Reinforcement Learning](../../03-reflexion-verbal-rl/docs/zh.md)：同一类任务多次尝试时，把失败经验带入下一次规划。
- [阶段 14 · 04 Tree of Thoughts 与 LATS：审慎搜索](../../04-tree-of-thoughts-lats/docs/zh.md)：当一条静态计划不够时，对多条计划做搜索。
- [阶段 14 · 11 结合 HTN 与演化搜索的 Planning](../../11-planning-htn-and-evolutionary/docs/zh.md)：更结构化的分层规划。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：讲义引用的"从最简单开始"原则。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)、[阶段 14 · 15 基于角色的 Agent 团队：角色、任务与流程](../../15-crewai-role-based-crews/docs/zh.md)：LangGraph 与 CrewAI Flows 中计划 DAG 的生产实现。
- [阶段 14 · 44 制定有证据支撑的执行计划](../../44-plan-from-evidence/docs/zh.md)：把"先计划后执行"用于 coding agent 工作流。

### 延伸关键词
`ReWOO` · `Planner / Worker / Solver` · `evidence reference #E1` · `plan DAG` · `topological sort` · `parallel tool execution` · `replanner` · `Plan-and-Execute` · `Plan-and-Act` · `planner distillation` · `token efficiency` · `critical path`
