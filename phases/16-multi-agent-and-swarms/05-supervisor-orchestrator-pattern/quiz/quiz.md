# 测验 · 监督者与编排者—工作者模式（Supervisor / Orchestrator-Worker Pattern）

> **阶段 16 · 多智能体与集群 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 模式结构 | 一个 lead 负责规划、分解、汇总，自己不做具体工作；多个 worker 在各自的上下文中并行执行窄任务并回报 |
| 2 | 生产参照 | 讲义：Anthropic Research 系统以 Claude Opus 4 为 lead、Sonnet 4 为 subagent，内部研究评测比单 agent Opus 4 高 90.2% |
| 3 | Token 主导 | 讲义：BrowseComp 上 80% 的表现差异仅由 token 用量解释；每个 subagent 拿到新鲜（fresh）上下文窗口是主要机制 |
| 4 | 为什么赢 | 三个机制：fresh context（每个 worker 一个干净窗口）、prompt 专门化（lead 只"分解与汇总"）、并行（墙钟 ≈ `max(worker) + plan + synthesis`） |
| 5 | 工程经验 | 按查询复杂度调节投入（简单 1 agent / 3–10 次工具调用，复杂 10+ agent）；先广后窄；rainbow 部署；多 agent 约 15× token |
| 6 | 失败模式 | lead 幻觉出错误计划；worker 过度探索越界；汇总冲突——静默选一边是最糟的 |
| 7 | 何时不用 | 顺序依赖的任务（用 pipeline）、简单查询（单 agent）、强确定性/审计需求（静态图） |
| 8 | LangGraph 的转向 | 从 `create_supervisor` 高层封装转向直接用 tool calling 实现 supervisor，以便控制 supervisor"看到什么"（context engineering） |
| 9 | 上线清单 | lead 用推理级模型、worker 用更快更便宜的模型；worker 超时（> 2× 中位数）；每 worker token 上限；trace plan/worker/synthesis；rainbow rollout |
| 10 | 代码要点 | 线程 fan-out / join；预分配结果槽回传结果；`sleep` 释放 GIL 所以 I/O 型 worker 能并行；无超时、无冲突检测、固定拆 3 份 |

### 核心技能（能动手做到）

- [ ] 用 `threading` 或 `concurrent.futures` 写出"先全部启动、再统一等待"的 fan-out / join，并测出墙钟收益
- [ ] 为 worker 加上超时，并在最终答案中显式标注缺失的子问题
- [ ] 在汇总阶段检测 worker 之间的矛盾并呈现分歧，而不是静默选一个
- [ ] 根据查询复杂度决定 worker 数量，并估算多 agent 相比单 agent 的 token 成本
- [ ] 判断一个任务适合 supervisor、pipeline 还是单 agent，并说出理由
- [ ] 解释 GIL 对 I/O 密集与 CPU 密集 worker 的不同影响

---

## 二、基础自测（选择题）

**Q1.** 讲义引用的 Anthropic Research 系统，其模型搭配与报告的收益是：

- A. Sonnet 4 做 lead、Opus 4 做 subagent，比单 agent 高 15%
- B. 所有 agent 都用 Opus 4，比单 agent 高 80%
- C. GPT 系列做 lead、Claude 做 subagent，比单 agent 高 90.2%
- D. Opus 4 做 lead、Sonnet 4 做 subagent，内部研究评测比单 agent Opus 4 高 90.2%

**Q2.** 讲义称 BrowseComp 上 80% 的表现差异可以由哪个因素单独解释？

- A. token 用量
- B. 模型参数量
- C. 工具调用次数
- D. 子 agent 的数量

**Q3.** 在理想的 supervisor 模式中，总墙钟时间大约是：

- A. `sum(worker_times)`
- B. `sum(worker_times) / worker_count`
- C. `max(worker_times) + plan + synthesis`
- D. `min(worker_times) + plan`

**Q4.** 下列哪个任务**最不适合**用 supervisor 模式？

- A. 同时调研三家竞争对手的产品、定价和融资情况
- B. 先从数据库导出数据，再用导出的数据训练模型，最后用模型生成报告
- C. 总结五篇互相独立的论文各自的贡献
- D. 从法律、财务、技术三个角度分别审查一份合同

**Q5.** 讲义说 Anthropic 采用 rainbow deployment 而不是 blue-green，原因是：

- A. rainbow 部署更便宜，不需要额外机器
- B. blue-green 不支持多个模型同时在线
- C. rainbow 部署可以一次性热替换所有 agent
- D. agent 是长时间运行且有状态的，需要新版本逐步上线、旧版本自然排空，而不是瞬间切换

**Q6.** 两个 worker 对同一事实返回了矛盾的结论，lead 在汇总时最好的做法是：

- A. 在答案中明确呈现分歧（或追加一轮核实），而不是静默选择其中一个
- B. 采用排在前面的 worker 的结论
- C. 采用措辞更自信的那个 worker 的结论
- D. 把两个结论都删掉，避免让用户困惑

**Q7.** 如果把 `Lead.run` 中的线程代码改成下面这样，`wall_clock_seconds` 大约是多少？

```python
for i, sq in enumerate(sub_questions):
    w = Worker(worker_id=i, trace=self.trace)
    th = threading.Thread(target=w.run, args=(sq, results, i))
    th.start()
    th.join()
```

- A. 约 0.1 秒
- B. 约 0.3 秒
- C. 约 0.9 秒
- D. 约 2.7 秒

**Q8.** 把 `fake_web_fetch` 里的 `time.sleep(0.3)` 换成一段耗时约 0.08 秒的纯 Python 数值循环，3 个线程并行的总耗时会：

- A. 降到约 0.08 秒，因为三个线程同时计算
- B. 与顺序执行相当甚至略慢，因为 CPython 的 GIL 使纯 Python 计算无法在线程间并行
- C. 变为 0，因为线程会被编译器优化掉
- D. 程序会死锁，因为 `Trace` 的锁被长时间占用

---

## 三、动手 / 代码题

**Q9.** 讲义练习 2：给 lead 加 worker 超时。要求：总预算 0.5 秒；超时的 worker 在 trace 中记录 `timeout` 事件；最终答案末尾列出缺失的子问题。请写出改造后的 `run` 的核心部分，并回答：Python 线程超时后还在运行，这会带来什么隐患？怎么避免？

**Q10.** 讲义练习 3：在不调用 LLM 的前提下检测 worker 之间的矛盾。假设两个 worker 的摘要是：

```text
W0: "FIPA-ACL ratified in 2000."
W1: "FIPA-ACL was ratified 2002."
```

请写一个 `detect_conflicts(results)`，至少能发现"同一主题、年份不同"这类矛盾；并改写 `synthesize`，在发现矛盾时输出 `DISAGREEMENT:` 段落。讨论这种规则方法的局限。

**Q11.** 成本估算。讲义称多 agent 约为单 agent 的 15 倍 token，内部评测提升 90.2%。

1. 按本节代码的计数方式（每个 worker 800 token、lead 固定 1200 token），worker 数为 3、10、100 时 `total_tokens` 各是多少？
2. 假设某问题单 agent 消耗 20,000 token，按"约 15 倍"估算多 agent 消耗多少？若每百万 token 的价格为 10 美元（假设值），单次成本各是多少？
3. 写一个 `estimate_workers(query)` 的思路，体现讲义"Scale effort to query complexity"，并说明为什么讲义要求"由 lead 估计，而不是调用方"。

**Q12.** 代码评审：找出 `main.py` 中至少五处"演示可以接受、生产必须修改"的问题（提示：plan、join、synthesize、统计、输出文字、trace 字段）。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 orchestrator-worker（supervisor）模式？它为什么能在研究类任务上胜过单 agent？

**Q14.**（原理深挖）讲义说"80% 的差异由 token 用量解释"，"fresh context per subagent"是主要机制。请解释为什么"更多 token、更干净的上下文"会带来更好的结果，以及这对系统设计有什么启示。

**Q15.**（工程实践）你要把一个 supervisor 模式的研究 agent 上线。请给出你的上线清单，包括模型搭配、超时、成本控制、可观测性和发布策略。

**Q16.**（场景设计）用户问："比较 2023 到 2026 年三大开源 agent 框架的演进，并给出选型建议。"请设计 lead 的分解方案、worker 的 prompt 边界和汇总模板，并说明如何处理 worker 之间的矛盾。

**Q17.**（追问型）"既然 supervisor 这么好，为什么不所有任务都用？什么时候你会坚持用单 agent 或静态 pipeline？"

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："This is the pattern behind Anthropic's Research system (Claude Opus 4 as lead, Sonnet 4 as subagents), measured at +90.2% over single-agent Opus 4 on internal research evals." A 把模型角色说反，并混入了"15×"这个 token 倍数；B 混入了"80%"这个方差解释比例；C 的模型搭配错误。

### Q2 — 答案：A

讲义："80% of the variance on BrowseComp is explained by token usage alone — multi-agent wins largely because each subagent gets a fresh context window." B、C、D 都不是讲义给出的结论；D 是一个常见误解——worker 数量本身不是关键，关键是它们一共"花了多少 token、在多干净的上下文里花"。

### Q3 — 答案：C

讲义："Wall-clock time is roughly `max(worker_times) + plan + synthesis`, not `sum(worker_times)`." A 是顺序执行；B 只有在负载完全均衡且没有 plan/synthesis 时才近似成立，且概念错误；D 忽略了必须等最慢的 worker。代码实测：3 个 0.3 秒的 worker 并行总耗时 0.301 秒。

### Q4 — 答案：B

B 是严格的顺序依赖：第二步需要第一步的输出，第三步需要第二步的输出。讲义："Sequential tasks. If step 2 literally needs step 1's output, parallelism buys nothing. Use a pipeline." A、C、D 都可以拆成互相独立的子问题并行处理，正是 supervisor 擅长的场景。

### Q5 — 答案：D

讲义："Rainbow deployments. Agents are long-running and stateful. Traditional blue-green does not work. Anthropic uses rainbow: gradual rollout of new versions while old ones drain." A、B 不是讲义给出的理由；C 恰好相反——rainbow 的要点就是"不热替换"。注意：这里说的"有状态"是指运行中的 agent 进程（正在进行中的长任务），与上一节"Agent 原语是无状态的"讨论的是不同层次。

### Q6 — 答案：A

讲义："The lead must either re-ask (add a round) or note the disagreement explicitly. Silent picking of one side is the worst failure: the user never knows disagreement happened." B、C 都是"静默选边"——C 还会引入"谁更自信谁赢"的偏差；D 让用户失去了重要信息。本节 `outputs/skill-supervisor-designer.md` 也把"隐藏冲突的汇总模板"列为 hard reject。

### Q7 — 答案：C

每启动一个线程就立刻 `join`，主线程会等它结束才启动下一个，三个 worker 实际顺序执行：约 `3 × 0.3 = 0.9` 秒（顺序调用 3 次 `fake_web_fetch` 实测 0.901 秒）。并行的关键是"先全部 start，再统一 join"。

### Q8 — 答案：B

`time.sleep` 和网络 I/O 会释放 GIL，所以线程能重叠等待；纯 Python 计算持有 GIL，同一时刻只有一个线程在执行字节码。实测 3 次 300 万次累加：顺序 0.234 秒，3 线程 0.303 秒——线程还更慢（有切换开销）。A 是对线程的误解；C 不存在；D 错，`Trace` 的锁只在 `log` 的瞬间持有。真实的 LLM worker 主要在等 API 响应，属于 I/O 密集，所以线程/asyncio 是合适的。

### Q9 — 参考答案

核心实现（已在本地运行验证：一个 worker 睡 1 秒，总耗时 0.5 秒，答案末尾出现 `MISSING (timed out): Q -- open problems`，trace 事件为 `start, start, start, done, done, timeout`）：

```python
def run(self, query, timeout=0.5):
    t0 = time.time()
    sqs = self.plan(query)
    results = [None] * len(sqs)
    threads = []
    for i, sq in enumerate(sqs):
        th = threading.Thread(target=Worker(i, self.trace).run,
                              args=(sq, results, i), daemon=True)
        threads.append(th)
        th.start()
    deadline = t0 + timeout
    for th in threads:                                   # 共享同一个截止时间
        th.join(timeout=max(0.0, deadline - time.time()))
    snapshot = list(results)                             # 冻结此刻的结果
    missing = [sqs[i] for i, r in enumerate(snapshot) if r is None]
    for i, r in enumerate(snapshot):
        if r is None:
            self.trace.log(i, "timeout", sqs[i])
    synth = self.synthesize(query, [r for r in snapshot if r is not None])
    if missing:
        synth += "\nMISSING (timed out): " + "; ".join(missing)
    return synth, {"wall": round(time.time() - t0, 3), "missing": len(missing)}
```

要点：

- 每个 `join` 用"剩余预算"而不是固定的 0.5 秒，否则 3 个 worker 最坏要等 1.5 秒。
- **隐患**：`join(timeout)` 只是"不再等待"，线程仍在后台运行，它之后可能写入 `results`、继续消耗 token 和 API 配额；如果不是 daemon 线程，还会阻止进程退出。
- **避免**：汇总前先对 `results` 做快照（如上）；给 worker 传一个 `threading.Event` 作为取消信号，让它在每次工具调用之间检查；真正需要强制终止时用子进程、`asyncio` 的任务取消，或在任务队列层面设置超时。
- 讲义 Ship It 的规则是"超过中位数 2 倍就杀掉"，此时 lead 可以用更窄的范围重派，或不带它继续，但必须在答案中标注（这就是练习 2 问的"需要什么可观测性"）。

### Q10 — 参考答案

```python
import re
from collections import defaultdict

YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

def subject_of(text):                      # 极简主题抽取：年份之前的前两个词
    words = re.findall(r"[A-Za-z][\w-]*", text)
    return " ".join(words[:2]).lower()

def detect_conflicts(results):
    claims = defaultdict(set)              # 主题 -> {(年份, worker 子问题)}
    for r in results:
        for y in YEAR.findall(r.summary):
            claims[subject_of(r.summary)].add((y, r.sub_question))
    conflicts = []
    for subject, pairs in claims.items():
        years = {y for y, _ in pairs}
        if len(years) > 1:
            conflicts.append((subject, sorted(pairs)))
    return conflicts

def synthesize(self, query, results):
    lines = [f"- {r.sub_question}: {r.summary}" for r in results]
    out = f"Answer to '{query}':\n" + "\n".join(lines)
    for subject, pairs in detect_conflicts(results):
        detail = "; ".join(f"{sq} says {y}" for y, sq in pairs)
        out += f"\nDISAGREEMENT: '{subject}' -> {detail}"
    return out
```

对题目中的两个摘要，年份集合分别为 `{'2000'}` 和 `{'2002'}`，但上面"取前两个词当主题"的抽取会得到 `fipa-acl ratified` 与 `fipa-acl was`，**并不相同**，于是 `detect_conflicts` 返回空列表、漏报了矛盾；若把 W1 改写成 `"FIPA-ACL ratified 2002."`，则能检出 `('fipa-acl ratified', [('2000', ...), ('2002', ...)])`（两种情况均已实测）。这正好暴露了规则方法的局限。更稳妥的做法是让 worker 按约定的结构化格式回报（例如 `{"entity": "FIPA-ACL", "attribute": "ratified_year", "value": 2000, "source": ...}`），再按 `(entity, attribute)` 分组比较 `value`。

局限：

- 自由文本的主题/属性抽取很脆弱（同义词、指代、单位换算）；
- 只能发现数值或枚举型冲突，无法发现语义层面的矛盾（"框架 X 适合生产" vs "框架 X 尚不稳定"）；
- 因此生产中常组合：结构化输出约束 + 规则检测 + 必要时一次便宜的 LLM 核查调用。

### Q11 — 参考答案

1. `total_tokens = 800 × N + 1200`：N = 3 → 3,600；N = 10 → 9,200；N = 100 → 81,200（与实测一致）。
2. 20,000 × 15 = 300,000 token。按假设价格每百万 token 10 美元：单 agent 约 0.20 美元，多 agent 约 3.00 美元。是否值得取决于任务价值：讲义 "Only run it when the task value justifies the cost"。
3. `estimate_workers` 思路：先由 lead 用一次便宜的调用判断查询类型——单一事实（1 个 agent，3–10 次工具调用）、少量独立方面的比较（2–4 个 worker）、开放式综述/多实体多维度（5+ 个，必要时先广后窄再追加）；可以用启发式特征辅助（实体数量、比较词、时间跨度、是否需要多来源交叉验证）。之所以由 lead 估计而不是调用方：只有 lead 在规划时真正理解了问题结构，调用方通常不知道问题有多复杂；而且这样系统可以在执行中"先广后窄"动态追加 worker（讲义 "Broad then narrow"）。

### Q12 — 参考答案

- **`plan` 固定拆 3 份**：不随复杂度变化，违背 "Scale effort to query complexity"；子问题只是"原查询 + 后缀"，没有范围边界和输出格式约束，容易导致 worker 越界。
- **`join()` 无超时**：一个卡住的 worker 会让请求永远挂起（Q9）。
- **`synthesize` 只做拼接**：无冲突检测（Q10）、无来源引用；失败的 worker（`None`）被静默过滤，用户不知道答案不完整。
- **统计数字是常数**：每 worker 800 token、lead 1200 token 都是写死的；没有单 agent 基线，看不出"15×"的成本差异；`WorkerResult.wall_time` 算了却从未输出。
- **输出文字是写死的**：`"Parallel actual is ~0.35s"` 并非测量值，实测为 0.301 秒；讲义也写"three 0.3-second workers run in ~0.35 seconds"。
- **trace 字段被借用**：`plan` 事件把子问题数量塞进 `sub_question` 字段，`worker_id=-1` 表示 lead，都是语义不清的魔法值；trace 也没有记录汇总的输入与输出（`outputs/skill-supervisor-designer.md` 要求的最少追踪点之一）。
- **结果在 `run` 和 `synthesize` 中被重复过滤 `None`**：无害但冗余。
- 计时用 `time.time()`，测耗时更推荐单调时钟 `time.perf_counter()`。

### Q13 — 参考回答要点

- **定义**：一个 lead（supervisor/orchestrator）负责理解问题、分解成子问题、分派给多个 worker，并汇总 worker 的结果；lead 自己不执行具体工作。worker 是窄范围、独立上下文的 subagent。
- **为什么胜出**（讲义三机制）：
  1. **fresh context**：每个 worker 只带自己的子问题，不背负 lead 的规划历史和其它材料，单个窗口可以全部用于一个问题；
  2. **prompt 专门化**：lead 的 prompt 只管分解与汇总，worker 的 prompt 只管一个窄问题，输出更聚焦；
  3. **并行**：墙钟从 `sum` 变成 `max`。
- **数据**：讲义：Anthropic Research 系统比单 agent Opus 4 高 90.2%；BrowseComp 80% 的方差由 token 用量解释。
- **代价**：约 15 倍 token；只有任务价值足够高才值得。
- 加分点：说出 lead 只看摘要不看原始材料，本质是上下文工程（context engineering）——控制每个模型"看到什么"。

### Q14 — 参考回答要点

- **更多 token**：研究类任务的瓶颈常常是"读了多少、查了多少"。多 agent 让系统在同样的墙钟时间内消耗更多 token（更多搜索、更多阅读）。
- **更干净的上下文**：单 agent 读完五篇论文后，上下文被大量原文填满，早期内容被"遗忘"或注意力被稀释（讲义 Problem："It forgets the first paper by the time it reaches the fifth"）。每个 worker 只处理一篇/一个方面，相当于把长上下文问题拆成多个短上下文问题，lead 再在压缩后的摘要上推理。
- **设计启示**：
  - 多 agent 的价值主要来自"扩大有效 token 预算 + 压缩信息再传递"，而不是 agent 之间的"社交"；
  - 因此要精心设计 worker 交回的 artifact（结构化、精炼、带来源），控制 lead 看到的内容；
  - 反过来，如果单 agent 的上下文没有被撑满、任务也不可并行，多 agent 只会徒增成本。
- 常见误区：认为"agent 越多越好"——收益来自 token 与上下文，而非 agent 数量本身；worker 数超过子问题的真实独立维度后只会制造重复和冲突。

### Q15 — 参考回答要点

- **模型搭配**：lead 用推理级模型（Opus / o3 级别），worker 用更快更便宜的模型（Sonnet / o4-mini 级别）。
- **复杂度判断**：lead 先估计复杂度，简单问题直接单 agent 回答。
- **超时**：worker 超过中位耗时 2 倍即终止，lead 缩窄范围重派或在答案中标注缺失。
- **成本**：每个 worker 的 token 硬上限（讲义示例：期望汇总输入的 10 倍）；每请求总预算；按任务价值决定是否启用多 agent。
- **可观测性**：记录 lead 的计划、每个 worker 的工具调用与起止时间、汇总的输入与输出；这是事后调试的基础。
- **发布**：rainbow rollout——长时间运行的 agent 不能热替换，新旧版本并存，旧版本处理完手头任务后排空。
- **质量**：汇总冲突显式呈现；worker 输出带来源引用；离线评测集回归。
- 加分点：说明 Python 线程无法强制终止，生产中要用可取消的任务机制。

### Q16 — 参考回答要点

- **复杂度判断**：多实体（三个框架）× 多维度（演进、能力、生态）× 时间跨度，属于复杂查询，适合 supervisor。
- **分解（先广后窄）**：第一轮按框架拆 3 个 worker（每个框架 2023–2026 的关键版本与变化）；必要时第二轮按维度追加（如"生产可用性与社区活跃度"）。不按年份拆，避免同一框架的信息分散在多个 worker 里。
- **worker prompt 边界**：只研究指定框架；只回答指定时间范围；输出固定 JSON 结构（版本、日期、关键变化、来源链接）；明确"不要做比较与推荐"——比较是 lead 的工作。
- **汇总模板**：先给对比表，再给选型建议（按场景），最后列出"分歧与不确定性"小节；每条结论标注来源 worker 与链接。
- **矛盾处理**：结构化字段（如发布日期）用规则比较；发现冲突时，要么追加一个核实 worker 只查该事实，要么在答案中明确写出"来源 A 说…，来源 B 说…"，不得静默选边。
- 加分点：给每个 worker 设 token 上限与超时，lead 的汇总输入只包含 worker 的结构化结果，不包含原始网页。

### Q17 — 参考回答要点

- **成本**：约 15 倍 token，简单问题用 supervisor 是浪费（讲义："Simple queries. Single-agent handles them faster and cheaper"）。
- **顺序依赖**：后一步依赖前一步的输出时并行无收益，用 pipeline（CrewAI Sequential、LangGraph 线性图）。
- **确定性与审计**：supervisor 依赖 LLM 做分派决策，结果不可完全复现；对审计、回放要求高的场景用静态图。
- **协调开销与新失败模式**：lead 可能规划错误、worker 可能越界、汇总可能冲突——都是单 agent 没有的问题。
- **判断方法**：任务能否拆成真正独立的子问题？单 agent 的上下文是否会被撑满？任务价值是否覆盖成本？三者都是"是"才选 supervisor。
- 加分点：本节 `outputs/skill-supervisor-designer.md` 的拒绝规则正是这三条：简单查询、顺序依赖、要求确定性时拒绝使用 supervisor。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：supervisor 是"LLM 选择型 orchestrator + 窄 handoff"的组合。
- [阶段 16 · 01 为什么需要多 Agent？](../../01-why-multi-agent/docs/zh.md)：多 agent 的收益与成本。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../../14-agent-engineering/12-anthropic-workflow-patterns/docs/zh.md)：orchestrator-workers 作为工作流模式之一，以及"先用简单方案"的原则。
- [阶段 11 · 05 Context Engineering: 窗口、 预算、 记忆和检索](../../../11-llm-engineering/05-context-engineering/docs/zh.md)：理解"fresh context"为什么有效。

### 本节被哪些后续内容用到
- [阶段 16 · 06 层级架构及其失效模式](../../06-hierarchical-architecture/docs/zh.md)：把 supervisor 嵌套起来，以及随之而来的漂移问题。
- [阶段 16 · 08 角色专业化：规划者、Critic、执行者与验证者](../../08-role-specialization/docs/zh.md)：worker 角色的进一步细分。
- [阶段 16 · 09 并行、Swarm 与网络化架构](../../09-parallel-swarm-networks/docs/zh.md)：去掉中心 lead 的并行架构。
- [阶段 14 · 28 Orchestration 模式：监督者、Swarm 与层级结构](../../../14-agent-engineering/28-orchestration-patterns/docs/zh.md)：从 agent 工程角度对比几种编排模式。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：worker token 上限与成本控制。
- [阶段 19 · 10 综合项目 10：多 Agent 软件工程团队](../../../19-capstone-projects/10-multi-agent-software-team/docs/zh.md)：在综合项目中落地 supervisor 模式。

### 延伸关键词
`orchestrator-worker` · `supervisor` · `fresh context` · `context engineering` · `fan-out / fan-in` · `scale effort to complexity` · `rainbow deployment` · `worker timeout` · `synthesis conflict` · `GIL` · `concurrent.futures` · `langgraph-supervisor` · `BrowseComp`
