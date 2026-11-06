# 测验 · Anthropic 的工作流模式：优先采用简单方案（Anthropic's Workflow Patterns: Simple Over Complex）

> **阶段 14 · Agent 工程 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：中文讲义为机器翻译，术语翻得很乱（如把 orchestrator-workers 译成"管弦乐手"、把 CrewAI 的 role templating 译成"角色诱惑"），请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Workflow vs Agent | Workflow：LLM 与工具按**预定义代码路径**编排，工程师拥有这张图；Agent：LLM 动态决定用什么工具、走哪一步，模型拥有这张图 |
| 2 | 出处与核心主张 | Schluntz 与 Zhang（Anthropic，2024 年 12 月）《Building Effective Agents》：从直接 API 调用开始，只有当步骤无法预测时才上 agent |
| 3 | Augmented LLM | 五种模式的原子单元：一个 LLM + 检索（search）+ 工具（tools）+ 记忆（memory） |
| 4 | Prompt chaining | 第 N 次调用的输出是第 N+1 次的输入；适合可干净线性分解的任务；步骤间可加程序化 gate |
| 5 | Routing | 分类器 LLM 决定交给哪个下游 LLM / 工具；适合类别差异明显的输入（退款 / bug / 销售） |
| 6 | Parallelization | N 个调用并发后聚合；两种形态：sectioning（不同分块）与 voting（同一 prompt 跑 N 次，多数决或综合） |
| 7 | Orchestrator-workers | orchestrator LLM 动态决定调用哪些 worker 并综合结果；像 agent loop，但不会无限循环 |
| 8 | Evaluator-optimizer | 一个 LLM 提方案、另一个 LLM 评估，循环直到通过；是 Self-Refine 的泛化 |
| 9 | 选型 | 可预测 / 成本受限 / 合规受限 → workflow；开放式研究 / 步数未知 / 新领域 → agent |
| 10 | 框架的门槛 | 只有确实需要 durable state（LangGraph）、actor 并发（AutoGen v0.4）或角色模板（CrewAI）时才引入框架 |

### 核心技能（能动手做到）

- [ ] 不用任何框架，用 10–15 行 Python 写出五种模式中的任意一种
- [ ] 读懂 `ScriptedLLM` 的"列表脚本 + 下标封顶"机制，推算任意 `n` 下 `parallel_vote` 的结果
- [ ] 指出本节 `orchestrator_workers` 与讲义定义的差距（没有 orchestrator LLM），并改造成真正由 LLM 选 worker
- [ ] 修复 `evaluator_optimizer` 在 `max_iter=0` 时的崩溃，并让调用方能区分"通过"与"耗尽轮数"
- [ ] 给 routing 加置信度阈值和标签校验，低于阈值转人工
- [ ] 给定一个业务需求，判断应使用哪种 workflow 还是 agent，并说明步数、成本与可审计性

---

## 二、基础自测（选择题）

**Q1.** 按 Schluntz 与 Zhang 的定义，workflow 与 agent 的根本区别是：

- A. workflow 不调用 LLM，agent 调用 LLM
- B. workflow 只能串行，agent 可以并行
- C. workflow 由工程师预先定义执行路径（工程师拥有图）；agent 由模型动态决定工具与步骤（模型拥有图）
- D. workflow 不能使用工具，agent 可以使用工具

**Q2.** 讲义说五种模式都建立在 "augmented LLM" 之上。它指的是一个 LLM 加上哪三种能力？

- A. 检索（search）、工具（tools）、记忆（memory）
- B. 微调、量化、蒸馏
- C. 规划、反思、投票
- D. 路由、并行、评估

**Q3.** 关于 parallelization 模式，说法正确的是：

- A. 它只能用于把同一个 prompt 跑多次
- B. 它要求所有调用串行执行，以便后一个看到前一个的结果
- C. 它与 orchestrator-workers 完全相同
- D. 它有两种形态：sectioning（把任务切成不同分块并发处理）与 voting（同一 prompt 跑 N 次再聚合）

**Q4.** 讲义说哪一种模式是"Self-Refine（第 05 节）的泛化"？

- A. Prompt chaining
- B. Evaluator-optimizer
- C. Routing
- D. Orchestrator-workers

**Q5.** 本节 `ScriptedLLM` 对列表脚本的处理如下：

```python
        if isinstance(value, list):
            i = self.index.get(prompt, 0)
            self.index[prompt] = min(i + 1, len(value) - 1)
            return value[i]
```

脚本为 `["yes", "yes", "no", "yes", "no"]`。用一个**新的** `ScriptedLLM` 调用 `parallel_vote(prompt, llm, n=7)`，返回的 winner 是：

- A. `"yes"`，因为前 5 票里 yes 占多数
- B. 抛出 `IndexError`，因为脚本只有 5 个元素
- C. 平票，返回 `None`
- D. `"no"`，因为下标封顶后第 6、7 次都返回最后一个元素 `"no"`，最终 no 4 票、yes 3 票

**Q6.** 运行 `main.py` 最后打印 `total llm calls across all five patterns: 20`。这 20 次调用的正确拆分是：

- A. chaining 2 + routing 6 + voting 5 + orchestrator 3 + evaluator-optimizer 4
- B. chaining 2 + routing 3 + voting 5 + orchestrator 4 + evaluator-optimizer 6
- C. chaining 4 + routing 6 + voting 5 + orchestrator 3 + evaluator-optimizer 2
- D. chaining 2 + routing 6 + voting 5 + orchestrator 1 + evaluator-optimizer 6

**Q7.** 讲义把 orchestrator-workers 定义为"An orchestrator LLM dynamically decides which workers to run"。本节 `orchestrator_workers` 实际上是如何决定运行哪些 worker 的？

- A. 调用一次 LLM，让它输出 worker 名单
- B. 随机选一部分 worker
- C. 遍历每个 `Worker`，用它自带的 `handles` 关键字谓词（如 `"python" in t.lower()`）判断，没有 orchestrator LLM
- D. 总是运行全部 worker

**Q8.** 按讲义，下列哪种情况**更适合 agent** 而不是 workflow？

- A. 合规审计要求能直接阅读执行图的报销审批流程
- B. 下一步做什么取决于上一步搜索结果的开放式调研任务
- C. 步骤可以完整枚举的"摘要 → 起标题"流水线
- D. 每个请求成本必须有上限的批量分类任务

---

## 三、动手 / 代码题

**Q9.**（读代码找 bug）阅读 `evaluator_optimizer`：

```python
def evaluator_optimizer(task, proposer, evaluator, max_iter=5):
    trace = []
    feedback = None
    for i in range(max_iter):
        candidate = proposer(task, feedback)
        ok, judge = evaluator(task, candidate)
        trace.append((candidate, "PASS" if ok else "FAIL", judge))
        if ok:
            return candidate, trace
        feedback = judge
    return candidate, trace
```

1. `max_iter=0` 时会发生什么？
2. 跑满 `max_iter` 轮都没通过时，调用方拿到的是什么？它能直接知道"没通过"吗？
3. 讲义练习 3 说要"keep the top-2 outputs across iterations so a late good result doesn't get overwritten by a late bad one"。当前代码返回的是哪一轮的候选？请给出修复版本。

**Q10.**（改造代码）讲义练习 1：给 routing 加置信度阈值，低于阈值转人工。同时注意下面这个实际运行结果：

```python
>>> route("refund pls", classifier, {"default": lambda t: "escalate to human"})
('[unhandled: classify: refund pls]', 'escalate to human')
```

1. 为什么返回的 label 是一串奇怪的字符串？在真实系统中这对应什么风险？
2. 写一个 `route_with_threshold`：分类器返回 `(label, confidence)`；label 不在白名单或 confidence 低于阈值时转人工；并返回可审计的路由记录。
3. tier-1 客服场景下阈值大概怎么定？

**Q11.**（改造代码）讲义说 parallelization 是"Run N LLM calls **concurrently**"，但代码是：

```python
def parallel_vote(prompt, llm, n=5):
    votes = [llm(prompt) for _ in range(n)]
    counts = Counter(votes)
    winner, _ = counts.most_common(1)[0]
    return winner, counts
```

1. 这段代码是并发的吗？`n=0` 和"3 比 3 平票"时分别会怎样？
2. 完成讲义练习 2：用 `concurrent.futures` 实现带超时的并发投票，说明缺票时怎么聚合。
3. 把本节的 `ScriptedLLM` 直接用于多线程投票会有什么问题？

**Q12.**（改造代码）把 `orchestrator_workers` 改造成讲义描述的样子：由一个 orchestrator LLM 根据任务输出要调用的 worker 名单（例如逗号分隔），程序解析、校验后执行，再由 synth 综合。说明你如何防止 orchestrator 输出不存在的 worker 名、输出为空，以及它与 routing、parallelization 的区别。

---

## 四、面试高频题

**Q13.**（基础必考）说说 Anthropic《Building Effective Agents》中 workflow 与 agent 的区别，以及五种 workflow 模式各适合什么场景。

**Q14.**（原理深挖）Orchestrator-workers、parallelization（sectioning）和 agent loop 三者看起来都在"分配子任务"，它们的本质区别是什么？

**Q15.**（工程实践）团队想直接上 LangGraph / AutoGen / CrewAI 做一个新功能。你会如何判断"该不该上框架"？讲义给出的三个"框架值得"的理由是什么？

**Q16.**（场景设计）为一个 SaaS 产品设计客服自动化：用户消息可能是退款、bug 报告、销售咨询或闲聊。请用本节的模式组合出方案，并说明每一步的失败处理与评估方式。

**Q17.**（追问型）Evaluator-optimizer 循环在生产中常见哪些问题？如果 evaluator 和 proposer 是同一个模型，有什么风险？如何设计停止条件？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Workflow. LLMs and tools orchestrated through predefined code paths. Engineers own the graph." / "Agent. LLMs dynamically direct their own tools and take their own steps. The model owns the graph." A 错，两者都调用 LLM；B 错，workflow 有 parallelization 模式；D 错，workflow 的基础单元 augmented LLM 本身就带工具。

### Q2 — 答案：A

讲义："one LLM with three capabilities wired in — search (retrieval), tools (actions), memory (persistence)"。B 是模型训练/压缩手段；C 是 agent 技巧；D 是 workflow 模式本身而不是 augmented LLM 的能力。

### Q3 — 答案：D

讲义："Two shapes: sectioning (different chunks) and voting (same prompt, N runs, majority/synthesis)." A 只说了 voting；B 把并行说成了串行（那是 prompt chaining）；C 错，orchestrator-workers 的分工是**动态**决定的，而 sectioning 的切分是预先确定的。注意本节代码只实现了 voting，没有 sectioning。

### Q4 — 答案：B

讲义："One LLM proposes an answer, another LLM evaluates it. Iterate until the evaluator passes. This is Self-Refine (Lesson 05) generalized." 其余三项都没有"评估—修正"的循环。

### Q5 — 答案：D

`self.index[prompt] = min(i + 1, len(value) - 1)` 让下标停在最后一个位置，之后每次都返回 `value[4] = "no"`。7 票依次为 `yes, yes, no, yes, no, no, no`：no 4 票、yes 3 票，winner 为 `"no"`（已实际运行验证：`Counter({'no': 4, 'yes': 3})`）。A 只看了前 5 票；B 错，封顶机制就是为了避免越界；C 错，代码没有平票处理——实测 `n=6` 时 3 比 3，`most_common` 按插入顺序返回先出现的 `"yes"`，也不会返回 `None`。这道题说明：脚本化测试替身的"边界行为"会直接改变实验结论。

### Q6 — 答案：A

- chaining：summarize + title = 2；
- routing：3 条输入 × (classify + handle) = 6；
- voting：`n=5` = 5；
- orchestrator：任务包含 "python" 和 "style"，security 总是匹配，3 个 worker 各 1 次 = 3（synth 是纯字符串拼接，不调 LLM）；
- evaluator-optimizer：两轮 × (propose + evaluate) = 4。

合计 20。B 低估了 routing（漏了分类调用）；C、D 把 evaluator-optimizer 的轮数或 orchestrator 的调用算错了。

### Q7 — 答案：C

```python
    for worker in workers:
        if worker.handles(task):
            outputs.append((worker.name, worker.fn(task)))
```

选择逻辑是每个 worker 自带的静态谓词：`python_reviewer` 看 "python"、`style_reviewer` 看 "style"、`security_reviewer` 恒为 True。整个函数里没有 orchestrator LLM，更接近"基于规则的多路 routing + sectioning 式 fan-out"。D 不对：本例三个都运行是因为任务文本恰好同时包含 "python" 和 "style"；换成 "review this Go change" 时实测只运行了 `security_reviewer`。

### Q8 — 答案：B

讲义"Where agents beat workflows"：开放式研究（"When the next step depends on what the last step returned"）、步数未知的长任务、新领域。A 对应"Compliance-bound tasks"，C 对应"Predictable tasks"，D 对应"Cost-bound tasks"，都是 workflow 更合适的场景。

### Q9 — 参考答案

1. `range(0)` 不执行循环，`candidate` 从未被赋值，`return candidate, trace` 抛出 `UnboundLocalError: cannot access local variable 'candidate'...`（已实测）。
2. 返回的是**最后一轮**（失败的）候选和 trace。返回值里没有"是否通过"的标志，调用方只能自己去看 `trace[-1][1] == "FAIL"`，很容易把失败结果当作最终答案交给用户。skill 文件也强调需要 `max_iter` 和"fail-pass-through"兜底策略。
3. 当前返回最后一轮候选。如果第 2 轮其实接近通过、第 5 轮反而更差，好结果就被覆盖了。修复版本（evaluator 额外返回一个分数用于排序）：

```python
def evaluator_optimizer_v2(task, proposer, evaluator, max_iter=5, keep=2):
    """evaluator(task, cand) -> (ok, judge_text, score)"""
    if max_iter < 1:
        raise ValueError("max_iter must be >= 1")
    trace, feedback, best = [], None, []
    for _ in range(max_iter):
        candidate = proposer(task, feedback)
        ok, judge, score = evaluator(task, candidate)
        trace.append((candidate, "PASS" if ok else "FAIL", judge, score))
        best = sorted(best + [(score, candidate)], reverse=True)[:keep]  # 保留 top-k
        if ok:
            return candidate, True, trace
        feedback = judge
    return best[0][1], False, trace          # 显式告诉调用方：没有通过
```

要点：参数校验；返回 `passed` 标志；跨轮保留 top-k，耗尽轮数时返回历史最佳而不是最后一个；调用方根据 `passed=False` 决定转人工或降级。若 evaluator 只能给布尔值，也至少要返回 `passed` 标志。

### Q10 — 参考答案

1. 分类器 prompt 不在脚本里，`ScriptedLLM` 返回 `"[unhandled: classify: refund pls]"`；`route` 没有校验 label 是否合法，直接 `handlers.get(label)` 失败后落到 `default`。真实系统中这对应"分类器输出了词表外的标签（大小写不同、多了解释性文字、幻觉出新类别）"，如果没有 `default`，代码会返回 `"no handler for ..."`；更糟的是，如果下游用 label 做字符串匹配，脏标签会进入日志与统计，路由准确率无法评估。
2. 参考实现：

```python
ALLOWED = {"refund", "bug", "sales"}

def route_with_threshold(text, classifier, handlers, threshold=0.8):
    label, conf = classifier(text)                       # 例如要求 LLM 输出 JSON
    label = label.strip().lower()
    record = {"input": text, "label": label, "confidence": conf}
    if label not in ALLOWED or conf < threshold or label not in handlers:
        record["decision"] = "human"
        return "escalate to human", record
    record["decision"] = label
    return handlers[label](text), record
```

  分类器建议用结构化输出（枚举类型的 JSON schema）约束标签；confidence 可来自模型自报、logprob，或多次采样的一致率（借用 voting）。
3. 阈值不是拍出来的，而是用带标签的历史工单离线标定：画"阈值 → 自动处理覆盖率 / 误路由率"曲线，选择满足误路由率目标（例如退款误路由代价高，阈值要更严）的最低阈值。不同类别可以设不同阈值：退款涉及资金，阈值高；销售咨询误路由代价低，阈值可以低一些。

### Q11 — 参考答案

1. 不是并发。列表推导式按顺序调用 `llm`，总延迟是 N 次调用之和。`n=0` 时 `Counter()` 为空，`most_common(1)` 返回 `[]`，`[0]` 抛 `IndexError`；3 比 3 平票时 `most_common` 返回先插入的那个（实测 `n=6` 返回 `"yes"`），平票被悄悄当成了多数。
2. 参考实现（已实测：5 个调用中 1 个挂起 5 秒、超时设 0.5 秒，0.5 秒后返回 `('yes', Counter({'yes': 3, 'no': 1}), 1)`）：

```python
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait

def parallel_vote_timeout(prompt, llm, n=5, timeout=10.0, quorum=None):
    if n <= 0:
        raise ValueError("n must be >= 1")
    quorum = quorum if quorum is not None else n // 2 + 1
    pool = ThreadPoolExecutor(max_workers=n)
    futures = [pool.submit(llm, prompt) for _ in range(n)]
    done, not_done = wait(futures, timeout=timeout)
    pool.shutdown(wait=False, cancel_futures=True)       # 不等挂起的调用
    votes = [f.result() for f in done if f.exception() is None]
    counts = Counter(votes)
    if len(votes) < quorum:                              # 票数不够：不做决定
        return None, counts, len(not_done)
    winner, top = counts.most_common(1)[0]
    if list(counts.values()).count(top) > 1:             # 平票：不做决定
        return None, counts, len(not_done)
    return winner, counts, len(not_done)
```

  缺票时的聚合策略：设定法定票数（quorum），不足则返回"无结论"交给上层（重试或转人工）；对安全类判断（"能不能上线"）可以用"一票否决"而不是多数决；记录缺票数量用于监控。注意 Python 线程无法被强制终止，挂起的调用仍会在后台运行，生产中应在 HTTP 客户端层设置请求超时，或用 `asyncio.wait_for` 取消协程。
3. `ScriptedLLM.__call__` 对 `self.index` 做"读—改—写"，`self.calls.append` 虽然在 CPython 中是原子的，但下标更新不是原子操作：两个线程可能读到同一个 `i`，导致两次返回同一个元素、跳过另一个，投票结果不可复现。需要加 `threading.Lock`，或给每个线程准备独立的替身。

### Q12 — 参考答案

```python
def orchestrator_workers_llm(task, workers, orchestrator_llm, synth, max_workers=3):
    registry = {w.name: w for w in workers}
    prompt = (f"task: {task}\navailable workers: {', '.join(registry)}\n"
              "reply with a comma-separated list of worker names to run")
    raw = orchestrator_llm(prompt)
    picked = [name.strip() for name in raw.split(",")]
    picked = [n for n in dict.fromkeys(picked) if n in registry][:max_workers]  # 去重 + 白名单 + 上限
    if not picked:
        picked = ["security_reviewer"]          # 兜底：至少跑默认 worker，或直接转人工
    outputs = [(n, registry[n].fn(task)) for n in picked]
    return synth(outputs), outputs, raw
```

- **防护**：白名单过滤不存在的名字；`dict.fromkeys` 去重；限制最多调用数控制成本；空结果时走兜底；把 orchestrator 的原始输出 `raw` 写入 trace 便于审计。更稳妥的做法是用结构化输出（JSON schema，worker 名是枚举）。
- **与 routing 的区别**：routing 只选**一个**下游处理者；orchestrator 可以选**多个**并综合结果。
- **与 parallelization（sectioning）的区别**：sectioning 的切分方式是工程师预先写死的；orchestrator 的分工由 LLM 根据具体输入**动态**决定。
- **与 agent 的区别**：orchestrator 只做一次（或有限次）分派与综合，不会根据 worker 结果无限地继续循环。

### Q13 — 参考回答要点

- **区别**：workflow 是工程师预定义的代码路径，成本、步数可控，易调试、易审计；agent 是模型动态决定下一步，能处理开放问题，但失败模式更难推理、成本可能失控。
- **五种模式**：
  - Prompt chaining：线性可分解任务（先写大纲再写正文、先翻译再润色），步骤间可加程序化检查；
  - Routing：输入类别差异大，需要不同 prompt / 模型 / 工具（客服分流、简单问题走小模型）；
  - Parallelization：sectioning（长文档分块审查）或 voting（安全审查多次投票）；
  - Orchestrator-workers：子任务无法事先确定（改动涉及哪些文件由输入决定）；
  - Evaluator-optimizer：有明确评价标准、迭代能带来提升（翻译润色、按规范改写）。
- 加分点：说出"从直接 API 调用开始"的原则，以及 augmented LLM（检索 + 工具 + 记忆）是所有模式的基础单元。

### Q14 — 参考回答要点

| 维度 | Parallelization（sectioning） | Orchestrator-workers | Agent loop |
|------|-----------------------------|---------------------|-----------|
| 谁决定分工 | 工程师写死的切分规则 | orchestrator LLM 按输入动态决定 | 模型每一步动态决定 |
| 子任务数量 | 固定或可由规则算出 | 每次输入可不同 | 不确定 |
| 是否循环 | 否，一次 fan-out + 聚合 | 通常一次分派 + 综合，不无限循环 | 循环直到完成或预算耗尽 |
| 可预测性 / 成本 | 最高 | 中等，可设上限 | 最低，需要轮数预算 |

- 讲义原话："Similar to agent loops but the orchestrator does not loop indefinitely."
- 加分点：指出本节代码的 orchestrator 没有 LLM、本质是规则 fan-out；skill 文件强调不要把 3 个 worker 的 orchestrator 称为"multi-agent"，因为 worker 只是 LLM 调用，不是 agent。

### Q15 — 参考回答要点

- 讲义的出发点：框架会"obscure prompts, hide control flow, and invite premature complexity"，每种模式 10–15 行即可实现，框架的代价"以千行计"。
- **框架值得的三个理由**（讲义"Use It"）：需要 durable state（LangGraph：checkpoint、可恢复、人工审批中断）；需要 actor 模型并发（AutoGen v0.4：异步消息、分布式）；需要角色模板化（CrewAI）。另外，想要 Claude Code 那样的 harness 时用 Claude Agent SDK。
- **判断方法**：先画出流程图并数步数；先用直接 API 调用 + 小函数实现 MVP；当出现"进程重启后要从中断处继续""需要人工审批暂停数小时""多个 agent 需要异步通信"等真实需求时再引入框架。
- 常见误区：把"用了框架"当成"做了 agent"；框架隐藏的 prompt 让调试和评估变难。

### Q16 — 参考回答要点

- **第 1 步 routing**：分类器输出 `{label, confidence}`，标签限定为 `refund / bug / sales / chitchat`；低置信度或词表外标签转人工（见 Q10）。
- **退款分支 = prompt chaining + 程序化 gate**：抽取订单号 → 调用订单系统校验（代码 gate：订单存在、在退款期内、金额阈值）→ 生成回复；超过金额阈值必须人工审批。
- **bug 分支 = parallelization（sectioning）**：并发地做"复现步骤抽取""日志关键字检索""重复工单检索"，聚合后生成工单。
- **销售分支**：检索定价文档（augmented LLM 的检索能力）后回答，复杂报价转销售。
- **回复质量 = evaluator-optimizer**：对外发出的回复由 evaluator 检查语气、政策合规、是否承诺了不该承诺的内容，最多 2 轮，失败转人工。
- **评估**：路由准确率（混淆矩阵）、自动解决率、转人工率、每单 LLM 调用次数与成本、用户满意度；全链路 trace 便于审计。
- 加分点：说明整个系统是 workflow 不是 agent，步数有上限、可审计；只有"开放式技术排查"才考虑在 bug 分支内嵌一个有轮数预算的 agent。

### Q17 — 参考回答要点

- **常见问题**：
  - 没有停止条件或只靠"PASS"字符串判断，evaluator 永远不满意时会空转——必须有 `max_iter`；
  - 耗尽轮数后返回最后一个候选，可能比中间的更差（讲义练习 3）；
  - 反馈只传上一轮的意见，修 A 坏 B，来回振荡；
  - evaluator 过严或过松，PASS 标准不清晰。
- **同一模型自评的风险**：自我偏好（倾向认可自己的风格）、共享盲点（自己不知道的事实也看不出错）、容易被"看起来完整"的答案说服。缓解：用不同模型或不同 prompt 做 evaluator；尽量用可执行的检查（测试、schema 校验、规则）代替纯 LLM 判断；给 evaluator 明确的评分细则。
- **停止条件设计**：`max_iter` + 通过阈值 + "连续两轮无改进即停" + 成本 / 延迟预算；耗尽时返回历史最佳并显式标记未通过，交给人工或降级策略（skill 文件所说的 fail-pass-through）。
- 加分点：指出本节 `max_iter=0` 时 `UnboundLocalError` 的边界 bug，以及返回值缺少 `passed` 标志。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：本节的先修课；理解 agent loop 才能理解"什么时候不需要它"。
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../05-self-refine-and-critic/docs/zh.md)：evaluator-optimizer 的前身。
- [阶段 14 · 06 工具使用与 Function Calling](../../06-tool-use-and-function-calling/docs/zh.md)：augmented LLM 中"工具"能力的实现方式。
- [阶段 11 · 17 Agent 框架权衡——图、角色与 Actor Orchestration](../../../11-llm-engineering/17-agent-framework-tradeoffs/docs/zh.md)：从工程角度对比各类框架。

### 本节被哪些后续内容用到
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：需要 durable state 时的框架选择（LangGraph）。
- [阶段 14 · 14 用于 Agents 的 Actor 模型：异步消息与类型化运行时](../../14-autogen-actor-model/docs/zh.md)：需要 actor 并发时（AutoGen v0.4）。
- [阶段 14 · 15 基于角色的 Agent 团队：角色、任务与流程](../../15-crewai-role-based-crews/docs/zh.md)：需要角色模板时（CrewAI）。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)：orchestrator-workers 的产品化形态。
- [阶段 14 · 28 Orchestration 模式：监督者、Swarm 与层级结构](../../28-orchestration-patterns/docs/zh.md)：更复杂的多 agent 编排。
- [阶段 16 · 05 监督者与编排者—工作者模式](../../../16-multi-agent-and-swarms/05-supervisor-orchestrator-pattern/docs/zh.md)：orchestrator-workers 在多 agent 系统中的展开。
- [阶段 16 · 15 投票、自洽性与辩论拓扑](../../../16-multi-agent-and-swarms/15-voting-debate-topology/docs/zh.md)：voting 的深入讨论。
- [阶段 13 · 21 LLM 路由层：LiteLLM、OpenRouter、Portkey](../../../13-tools-and-protocols/21-llm-routing-layer/docs/zh.md)：模型层面的 routing。

### 延伸关键词
`Building Effective Agents` · `augmented LLM` · `prompt chaining` · `routing` · `sectioning / voting` · `orchestrator-workers` · `evaluator-optimizer` · `context engineering` · `structured output` · `quorum` · `fail-pass-through` · `LLM-as-judge`
