# 测验 · 评估驱动的 Agent 开发（Eval-Driven Agent Development）

> **阶段 14 · Agent 工程 · 第 30 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Anthropic 的起点建议 | "start with simple prompts, optimize them with comprehensive evaluation, and add multi-step agentic systems only when needed"；评估不是最后一步，而是驱动阶段 14 所有选择的外层循环 |
| 2 | 三层评估 | 静态 benchmark（跨模型比较、回归门禁）、自定义离线评估（贴合产品形态）、线上评估（生产环境） |
| 3 | 静态 benchmark 与污染 | SWE-bench Verified、WebArena/OSWorld、GAIA、BFCL V4；讲义：SWE-bench+ 发现 32.67% 的解答泄露，应报告 Verified / 审计后的分数 |
| 4 | 自定义离线评估的三种判定 | LLM-as-judge（Langfuse/Phoenix/Opik）、execution-based（跑补丁、跑测试）、trajectory-based（与金标准动作序列比较；讲义：OSWorld-Human 显示顶级 Agent 步数是金标准的 1.4–2.7 倍） |
| 5 | 线上评估 | session replay、guardrail 触发告警、逐步成本/延迟追踪（OTel span） |
| 6 | Evaluator-optimizer | proposer 生成 → evaluator 评判 → 不通过则带反馈修订，直到通过或达到轮数上限；是 Self-Refine 的推广 |
| 7 | 2026 最佳实践 | eval 与代码放在一起、每个 PR 在 CI 中运行、按分数门禁合并（如"相对 main 退步不超过 5%"）；每个 guardrail、每条学到的规则都对应一个 eval case |
| 8 | 阶段 14 的映射表 | 每一节都能产出 eval case：01 预算耗尽、06 未知工具被拒、26 检测器标出已知失效、27 PVE 拒绝被污染的检索、28 supervisor 路由正确、29 DLQ 处理 N% 失败 |
| 9 | 四种失败方式 | 没有基线、LLM-judge 不做 grounding（用 CRITIC）、对 eval 过拟合（轮换用例）、flaky eval（固定种子、快照状态） |
| 10 | 本节代码的关键问题 | 4 个用例**首轮全部失败**，靠 judge 反馈修订后才"通过"，CI 却报告 100% 通过率；guardrail 用例首轮已把 SSN 转发出去 |

### 核心技能（能动手做到）

- [ ] 为一个 Agent 产品设计三层评估，并说明每层回答什么问题
- [ ] 读懂 `evaluator_optimizer` 与 `ci_gate`，手推任意用例的 rounds、passed 与门禁结论
- [ ] 区分"首轮通过率"（agent 本身的能力）与"修订后通过率"（加了 evaluator-optimizer 的系统能力），并在报告中分别给出
- [ ] 识别并修复 flaky 用例：闭包状态跨运行泄漏、未固定种子
- [ ] 写一个不受浮点误差和样本量影响的 CI 门禁，并按用例比较而不仅仅比较总通过率
- [ ] 实现 trajectory efficiency（步数 / 金标准步数）指标与有 grounding 的 judge

---

## 二、基础自测（选择题）

**Q1.** 讲义提出的三层评估是：

- A. 单元测试、集成测试、端到端测试
- B. 静态 benchmark、自定义离线评估、线上生产评估
- C. 人工评估、LLM 评估、规则评估
- D. 训练集、验证集、测试集

**Q2.** 讲义引用的 Anthropic 建议是：

- A. 一开始就搭建完整的多 Agent 系统，再用评估裁剪
- B. 先上线，靠用户反馈评估
- C. 只看公开 benchmark 排名选模型即可
- D. 从简单 prompt 开始，用全面的评估来优化，只在需要时才加入多步 agentic 系统

**Q3.** 关于静态 benchmark 的数据污染，讲义的建议是：

- A. 总是报告 Verified / 审计后（+-audited）的分数，因为 SWE-bench+ 发现了 32.67% 的解答泄露
- B. 污染不影响排名，可以忽略
- C. 只用自己团队编的 benchmark，不看公开 benchmark
- D. 只报告最高分

**Q4.** Evaluator-optimizer 循环的正确描述是：

- A. 训练一个奖励模型，再用强化学习优化 Agent
- B. 同时运行多个 Agent，选择投票最多的答案
- C. proposer 生成输出 → evaluator 评判 → 不通过则带反馈修订，直到通过或达到轮数上限；是 Self-Refine 的推广
- D. 每次 PR 合并后由人工打分

**Q5.** 运行本节代码，4 个用例中有几个在**第 1 轮**就通过了 judge？

- A. 4 个
- B. 2 个
- C. 1 个
- D. 0 个

**Q6.** 讲义对 flaky eval（非确定性用例）给出的对策是：

- A. 删掉所有 flaky 用例
- B. 固定随机种子、快照状态
- C. 每个用例跑 10 次取最好的一次
- D. 把门禁阈值调高到 50%

**Q7.** `ci_gate` 的核心逻辑是 `regression = baseline_pass_rate - pass_rate`，`if regression > regression_threshold: BLOCK`（阈值 0.05）。基线为 0.95、本次 20 个用例通过 18 个（90%），结果是：

- A. `ALLOW`
- B. `BLOCK`，因为退步了 5%
- C. `BLOCK`，因为通过率低于基线
- D. 抛出异常

**Q8.** 讲义为什么警告"LLM-judge without grounding"？

- A. LLM-judge 太贵
- B. LLM-judge 只能评英文
- C. judge 本身也会幻觉；应采用 CRITIC 模式，让评判依据外部工具得到的事实
- D. LLM-judge 无法给出理由

---

## 三、动手 / 代码题

**Q9.** 阅读评估循环：

```python
def evaluator_optimizer(case: EvalCase) -> CaseResult:
    feedback: str | None = None
    candidate = ""
    for r in range(case.max_rounds):
        candidate = case.proposer(feedback)
        ok, reason = case.judge(candidate)
        if ok:
            return CaseResult(case.cid, case.category, True, r + 1, candidate, reason)
        feedback = reason
    return CaseResult(case.cid, case.category, False, case.max_rounds,
                      candidate, feedback or "unknown")
```

以及 online 用例的 proposer：

```python
    def proposer(feedback: str | None) -> str:
        if feedback and "ssn" in feedback.lower():
            return "refused: will not process social security numbers"
        return "forwarded: ssn 123-45-6789 to downstream system"
```

1. 运行结果是 4/4 PASS、CI gate `ALLOW (pass_rate=100.0%)`。把每个用例的 `max_rounds` 改成 1，结果会怎样？
2. 对 `online_o001` 来说，"第 2 轮通过"在生产中意味着什么？
3. 讲义把 evaluator-optimizer 定位为"wrap any agent flow for reliability"的运行时手段，又把它放进 eval harness。这两种用法应该如何区分？请给出一个修改方案，让报告同时体现两者。

**Q10.** 阅读"flaky"用例：

```python
def _flaky_benchmark_case() -> EvalCase:
    attempt = [0]

    def proposer(feedback: str | None) -> str:
        attempt[0] += 1
        if attempt[0] >= 2:
            return "patch: correct"
        return "patch: wrong first time"
    ...
```

1. 对同一个 `case` 对象连续调用 3 次 `evaluator_optimizer(case)`，`rounds` 依次是多少？为什么？
2. 这个用例为什么被称为 flaky？当前代码有没有任何机制识别或标记它？
3. 按讲义"pin seeds, snapshot state"的思路，给出至少两种修复方法，并说明如何在 CI 中自动发现 flaky 用例。

**Q11.** 阅读 CI 门禁：

```python
def ci_gate(results: list[CaseResult], baseline_pass_rate: float,
            regression_threshold: float = 0.05) -> tuple[bool, str]:
    if not results:
        return False, "no cases"
    pass_rate = sum(1 for r in results if r.passed) / len(results)
    regression = baseline_pass_rate - pass_rate
    if regression > regression_threshold:
        return False, (f"regression {regression:.1%} > threshold "
                       f"{regression_threshold:.1%}")
    return True, f"pass_rate={pass_rate:.1%} baseline={baseline_pass_rate:.1%}"
```

1. 分别计算：基线 0.95、18/20 通过；基线 1.0、19/20 通过；基线 0.80、3/4 通过。三者"退步"在数学上都恰好是 5%，门禁结论分别是什么？为什么不一致？
2. 本节只有 4 个用例，通过率的最小变化单位是多少？5% 的阈值意味着什么？
3. 假设用例 A 从通过变为失败、用例 B 从失败变为通过，总通过率不变。这个门禁能发现 A 的回归吗？
4. 改写门禁，解决以上三个问题。

**Q12.** 阅读自定义"LLM-judge"用例的 judge：

```python
    def judge(candidate: str) -> tuple[bool, str]:
        if "arXiv" in candidate or "cite" in candidate:
            return True, "citations present"
        return False, "missing citations"
```

1. 给出两个能骗过这个 judge 的输出。
2. 写一个有 grounding 的 judge：引用的 arXiv ID 必须出现在本次检索到的来源集合里。
3. 讲义练习 4 要求 trajectory efficiency（步数 / 金标准步数）。写出函数，并计算：Agent 走了 `["search","read","search","read","edit","test","edit","test"]`，金标准为 `["search","read","edit","test"]`，效率比是多少？讲义引用的 OSWorld-Human 数据范围是多少？

---

## 四、面试高频题

**Q13.**（基础必考）Agent 的评估和传统 LLM 评估有什么不同？请说出三层评估分别是什么、各自解决什么问题。

**Q14.**（原理深挖）LLM-as-judge 有哪些已知问题？如何让 judge 更可靠？什么时候不该用 LLM-judge？

**Q15.**（工程实践）如何把 Agent eval 接入 CI 并作为合并门禁？基线怎么存、阈值怎么定、flaky 用例怎么处理、成本怎么控制？

**Q16.**（场景设计）你的 Agent 在 SWE-bench Verified 上分数不错，但上线后用户抱怨它"经常改错文件、改动范围过大"。你会如何建立评估体系来发现并修复这个问题？

**Q17.**（追问型）"我们的 eval 通过率已经 98% 了，为什么线上还是频繁出问题？"——请分析可能的原因。

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Three evaluation layers — static benchmarks, custom offline, online production." A 是传统软件测试金字塔；C 是判定方式的分类（属于第二层内部的选择）；D 是机器学习的数据集划分。

### Q2 — 答案：D

讲义开头引用 Anthropic："start with simple prompts, optimize them with comprehensive evaluation, and add multi-step agentic systems only when needed." 并强调"Evaluation is not the last step. It's the outer loop that drives every other choice in Phase 14." A 与"按需添加"相反；B 是没有离线评估的做法；C 忽略了讲义的核心观点——benchmark 回答"模型是否广泛有能力"，而不是"这个 Agent 是否为我的产品交付了正确的补丁"。

### Q3 — 答案：A

讲义："Contamination is real: SWE-bench+ found 32.67% solution leakage. Always report Verified / +-audited scores." skill 也要求"Always report the +-audited score alongside"。B、D 会让分数虚高；C 走向另一个极端——讲义明确说静态 benchmark 适合跨模型比较和回归门禁。

### Q4 — 答案：C

讲义："Proposer generates output. Evaluator judges. Refine until evaluator passes. This is Self-Refine (Lesson 05) generalized." 代码中的 `max_rounds=3` 就是轮数上限（skill："with a round cap"）。A 是 RLHF 类训练；B 是投票/self-consistency；D 是人工评审。

### Q5 — 答案：D

4 个用例的 proposer 在 `feedback=None` 时都返回错误答案（已实测首轮 judge 结果全为 False），所有用例都是 `rounds=2` 才通过。把 `max_rounds` 改为 1 后，4 个用例全部 FAIL，门禁变成 `BLOCK (regression 95.0% > threshold 5.0%)`（已实测）。这正是 Q9 讨论的问题：报告的 100% 通过率完全来自"judge 告诉 proposer 哪里错了"。

### Q6 — 答案：B

讲义："Flaky evals. Non-deterministic cases cause false alarms. Pin seeds, snapshot state." skill 的 hard reject 也写着"Flaky cases without pinned seeds or snapshot state. False alarms erode the team's trust in evals." A 会丢掉有价值的覆盖；C 是"挑最好结果"，会掩盖真实失败率；D 让门禁失去意义。

### Q7 — 答案：A

`0.95 - 0.9` 在浮点数中等于 `0.04999999999999993`，小于 0.05，于是 `ALLOW`（已实测输出 `(True, 'pass_rate=90.0% baseline=95.0%')`）。从数学上看退步恰好 5%，按 skill 和讲义练习 3 的"≥ 5% 回归就失败"本应 BLOCK；按代码的严格 `>` 也处在边界上——结论由浮点误差决定。详见 Q11。

### Q8 — 答案：C

讲义："LLM-judge without grounding. Judges hallucinate too. CRITIC pattern (Lesson 05) — judge grounds on external tools." skill 还规定：事实类与合规类任务拒绝"全部用 LLM-judge"，必须有执行型或程序化的评估器。A、B、D 都不是讲义的理由。

### Q9 — 参考答案

1. `max_rounds=1` 时 4 个用例全部 FAIL，`ci_gate` 返回 `(False, 'regression 95.0% > threshold 5.0%')`（已实测）。也就是说，Agent 本身的首轮通过率是 **0%**，100% 完全来自修订。
2. 第 1 轮的输出是 `"forwarded: ssn 123-45-6789 to downstream system"`——在生产里这一步已经把 SSN 发给下游系统了，PII 已经泄露。之后"被 judge 提醒后拒绝"无法撤回已发生的动作。guardrail 类用例的含义是"**第一次就必须拦住**"，对它们做"修订后通过"毫无意义。这与 Lesson 27 的结论一致："If validation runs only on the final output, the model already touched the world."
3. 区分两种用法：
   - **运行时可靠性手段**：在生产中把 Agent 包在 evaluator-optimizer 里（judge 是生产系统的一部分），那么被评估的对象就是"Agent + 循环"这个整体，用 final 结果评估是合理的——但前提是生产中 judge 的反馈信息与 eval 中相同。本节的 judge 反馈直接包含答案线索（"missing sticks in recipe"），生产中的 judge 未必能给出这么精确的提示。
   - **评估 Agent 本身**：必须用首轮结果，不能让 judge 的反馈参与。
   - 修改方案：`CaseResult` 增加 `passed_first: bool`；给 `EvalCase` 加 `allow_refine: bool`（guardrail、有副作用的用例设为 False）；报告同时输出 "pass@1"（首轮通过率）和 "pass after refine"（修订后通过率）以及平均轮数；CI 门禁对 pass@1 和 guardrail 用例单独设阈值。

```python
@dataclass
class CaseResult:
    ...
    passed_first: bool = False

def evaluator_optimizer(case):
    feedback, candidate, first = None, "", None
    rounds = case.max_rounds if case.allow_refine else 1
    for r in range(rounds):
        candidate = case.proposer(feedback)
        ok, reason = case.judge(candidate)
        if first is None:
            first = ok
        if ok:
            return CaseResult(case.cid, case.category, True, r + 1, candidate, reason, first)
        feedback = reason
    return CaseResult(case.cid, case.category, False, rounds, candidate, feedback or "unknown", first)
```

### Q10 — 参考答案

1. 实测 `rounds` 依次为 **2、1、1**。`attempt` 是闭包里的列表，属于 case 对象的状态，跨调用保留：第一次运行 attempt 从 0→1（错）→2（对）；第二次运行 attempt 已经是 2，第一次调用就变成 3，直接返回正确答案。
2. 同一个用例的结果取决于"之前是否运行过"、"运行顺序"——这就是 flaky：不是因为代码改了，而是因为环境/状态不同导致结果不同。当前代码把它和其他用例一样计入 PASS，没有任何重复运行、方差统计或 flaky 标记；它的 proposer 也完全忽略 `feedback`，所谓"第二次就对了"只是计数器的副作用。
3. 修复与发现：
   - **每次运行重建状态**：在 runner 中每次评估都调用 `_flaky_benchmark_case()` 工厂函数生成新对象，或给 `EvalCase` 增加 `reset()` / `setup()` 钩子（snapshot state）；
   - **固定随机源**：若 proposer 内部有随机性（例如 LLM 采样），固定 seed、使用 temperature=0，或录制并回放 LLM 响应（cassette）；
   - **环境快照**：execution-based 用例在每次运行前恢复到同一份仓库/数据库快照；
   - **在 CI 中发现**：对每个用例重复运行 N 次（例如夜间任务跑 5 次），结果不一致的标记为 flaky，进入隔离区（不参与门禁，但要求修复），并统计每个用例的历史通过率。

### Q11 — 参考答案

1. 已实测：

| 基线 | 本次 | `baseline - pass_rate`（浮点） | 结论 |
|------|------|-------------------------------|------|
| 0.95 | 18/20 = 0.90 | 0.04999999999999993 | ALLOW |
| 1.0 | 19/20 = 0.95 | 0.050000000000000044 | BLOCK |
| 0.80 | 3/4 = 0.75 | 0.05000000000000004 | BLOCK（提示信息还是令人困惑的 "regression 5.0% > threshold 5.0%"） |

   三者数学上都恰好退步 5%，结论却不同：0.95、0.9、0.05 等十进制小数在二进制浮点中无法精确表示，减法后的误差方向不一。再加上讲义正文写"no regression > 5%"、练习 3 和 skill 写"≥ 5%"，规则本身也不一致。
2. 4 个用例时，每个用例占 25%，通过率只可能是 0、25%、50%、75%、100%。任何一个用例失败都意味着至少 20 个百分点的退步（相对 0.95 的基线）；5% 的阈值在这种样本量下没有意义，而且基线 0.95 本身在 4 个用例下也是不可能达到的通过率。
3. 不能。门禁只比较总通过率，A 退步与 B 进步互相抵消，结果 ALLOW。可 A 可能恰好是一条 guardrail 用例——讲义要求"Every guardrail maps to an eval case"，这类用例的回归应当单独阻断。
4. 参考改写：

```python
def ci_gate(results, baseline: dict[str, bool], max_regress_pct: int = 5,
            must_pass: set[str] = frozenset()):
    if not results:
        return False, "no cases"
    now = {r.cid: r.passed for r in results}
    # 1) 关键用例（guardrail 等）必须通过
    broken_critical = [c for c in must_pass if not now.get(c, False)]
    if broken_critical:
        return False, f"critical cases failed: {broken_critical}"
    # 2) 按用例比较：基线通过、本次失败 = 回归
    regressed = [c for c, ok in baseline.items() if ok and not now.get(c, False)]
    # 3) 用整数比较，避免浮点误差：回归数 * 100 >= 阈值 * 用例数
    if len(regressed) * 100 >= max_regress_pct * len(baseline):
        return False, f"{len(regressed)}/{len(baseline)} cases regressed: {regressed}"
    return True, f"{sum(now.values())}/{len(now)} passed; regressed={regressed}"
```

   要点：基线按用例存储（last-known-good，讲义"Store baselines"）；关键用例单独阻断；用整数运算或 `round` 后比较；阈值语义（`>=`）与文档统一；用例太少时，阈值应以"失败用例数"而不是百分比表达。

### Q12 — 参考答案

1. 能骗过 judge 的输出（已实测都返回 `(True, 'citations present')`）：
   - `"I cannot cite any source"`——包含 "cite"，但没有任何引用；
   - `"see arXiv:9999.99999 (fabricated)"`——包含 "arXiv"，但 ID 是编造的。
   这个 judge 名为 "LLM-judge"，实际是关键词匹配，而且完全没有 grounding——正是讲义所说的"Judges hallucinate too"在规则版本上的体现。
2. 有 grounding 的 judge：

```python
import re

def make_grounded_judge(retrieved_ids: set[str]):
    def judge(candidate: str) -> tuple[bool, str]:
        cited = set(re.findall(r"arXiv:(\d{4}\.\d{4,5})", candidate))
        if not cited:
            return False, "no arXiv citation"
        unknown = cited - retrieved_ids
        if unknown:
            return False, f"cited ids not in retrieved sources: {sorted(unknown)}"
        return True, f"citations grounded: {sorted(cited)}"
    return judge

judge = make_grounded_judge({"2210.03629"})
judge("answer with cite [arXiv:2210.03629]")   # (True, ...)
judge("see arXiv:9999.99999 (fabricated)")     # (False, 'cited ids not in retrieved sources: ...')
judge("I cannot cite any source")              # (False, 'no arXiv citation')
```

   更进一步（CRITIC）：用工具真正获取论文标题/摘要，再让 LLM-judge 判断"引用是否支持该论断"。
3. Trajectory efficiency：

```python
def trajectory_efficiency(agent_steps: list[str], gold_steps: list[str]) -> float:
    return len(agent_steps) / len(gold_steps)

trajectory_efficiency(
    ["search","read","search","read","edit","test","edit","test"],
    ["search","read","edit","test"])          # 2.0
```

   结果为 **2.0**：Agent 用了金标准两倍的步数。讲义 Key Terms 的定义是"Agent step count divided by human expert minimum"，引用 OSWorld-Human 的数据：顶级 Agent 是金标准的 **1.4–2.7 倍**。只看步数比还不够——可以再加"是否包含金标准的关键动作（子序列匹配）"和"是否有危险的多余动作"。

### Q13 — 参考回答要点

- **不同之处**：传统 LLM 评估主要看单轮输出质量；Agent 评估还要看**过程**（工具调用、步骤顺序、效率）、**环境状态**（文件是否改对、副作用是否发生）、**成本与延迟**，以及多步的可靠性。讲义："Agents pass demos. They fail in production in ways demos cannot predict."
- **三层**：
  1. 静态 benchmark：SWE-bench Verified、WebArena/OSWorld、GAIA、BFCL V4——跨模型比较、回归门禁；注意污染（SWE-bench+ 32.67% 泄露）。
  2. 自定义离线：LLM-as-judge、execution-based、trajectory-based——回答"这个 Agent 是否为我的产品做对了事"。
  3. 线上：session replay、guardrail 告警、逐步成本/延迟——发现离线没覆盖的问题。
- 加分点：三层形成闭环——线上失败转为离线用例（讲义："Tie every production failure to a new case"），离线用例在 CI 中门禁。

### Q14 — 参考回答要点

- **已知问题**：judge 本身会幻觉；偏好更长/更自信的回答；位置偏差；对自己同家族模型的输出偏宽松；评分不稳定（同一输入多次评分不同）；rubric 模糊时打分随意。
- **提高可靠性**：
  - grounding：CRITIC 模式，让 judge 调用工具核实事实（Q12）；
  - 明确的 rubric：拆成多个维度（讲义练习 2：factual、tone、scope），每维度给出判定标准与示例；
  - 用人工标注的样本校准 judge，计算与人工的一致率；
  - 固定 temperature、多次评分取多数，记录理由。
- **不该用 LLM-judge 的场景**：skill 规定"refuse 'all LLM-judges' on factual and compliance tasks. Execution-based or programmatic evaluators are required there"——代码能否通过测试、文件是否存在、SSN 是否被转发，都应该用程序判定。
- 常见误区：用关键词匹配冒充 LLM-judge（本节代码），或让被评估的同一个模型给自己打分。

### Q15 — 参考回答要点

- **位置**：eval 用例与 Agent 代码放在同一个仓库（讲义："Evals live next to code"），目录如 `cases/benchmarks/`、`cases/custom/`、`cases/online/`。
- **基线**：按用例存储 main 分支上一次的结果（last-known-good），随 main 的合并更新；记录模型版本、prompt 版本、工具版本。
- **阈值**：总体回归阈值（如 ≥ 5% 失败）+ 关键用例（guardrail、安全）零容忍；样本量小时用"回归用例数"而不是百分比；避免浮点边界（Q11）。
- **flaky**：固定种子与快照；夜间重复运行检测 flaky；flaky 用例隔离但必须修复。
- **成本**：PR 上跑快速子集（冒烟用例 + 与改动相关的用例），合并后或夜间跑全量与 benchmark；缓存 LLM 响应；并行执行。
- **报告**：pass@1 与修订后通过率分开（Q9）、按类别分解、与基线的逐用例差异、成本与延迟变化。
- 加分点：讲义映射表——每个 guardrail、每条学到的规则都有对应用例，缺失的就是覆盖缺口（练习 5）。

### Q16 — 参考回答要点

- **为什么 benchmark 没发现**：SWE-bench 主要看"失败测试变通过、原有测试不被破坏"，不惩罚多余的改动；讲义："Benchmarks answer 'is this model broadly capable?' not 'is this agent shipping the right patches for my product?'"
- **建立评估**：
  1. 从线上投诉中收集真实失败案例，逐个写成可复现的 eval case（讲义练习 1）；
  2. execution-based：跑补丁、跑测试，同时检查改动文件集合是否在预期范围内（对应 Lesson 26 的 scope creep 检测器）；
  3. trajectory-based：与金标准比较步数和改动范围（trajectory efficiency、diff 行数比）；
  4. LLM-judge 增加 "scope" 维度（讲义练习 2 的 rubric），并用人工样本校准；
  5. 线上：session replay + 对"改动文件数异常多"的告警。
- **修复与验证**：调整 prompt/工具（例如限制可编辑路径、要求先给出修改计划），在新用例上验证，通过后加入 CI 门禁防止回归。
- 常见误区：只看 benchmark 分数提高就认为问题解决。

### Q17 — 参考回答要点

- **用例分布与线上不一致**：用例是"happy path"或开发者想象的场景（skill："If the user wants 'just the happy path,' refuse"）；线上新出现的失败没有回流成用例。
- **过拟合 eval**：反复针对同一批用例调 prompt（讲义："Over-fitting to evals... Rotate cases"）。
- **评估方式掩盖问题**：
  - 报告的是修订后通过率，而非首轮通过率（本节代码就是 0% → 100%）；
  - judge 没有 grounding，被"看起来对"的输出骗过；
  - 只比总通过率，关键用例的回归被其他用例的进步抵消。
- **环境差异**：离线用 mock 工具，线上真实工具有超时、限流、脏数据；flaky 用例被重试掩盖。
- **没有线上评估层**：缺少 session replay、guardrail 告警、成本/延迟追踪。
- **基线问题**：基线过旧或没有基线，无法判断"在变差"。
- 回答结构：先承认 98% 只代表"在这些用例上"，再按"覆盖—判定—环境—线上闭环"四个方面排查。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../05-self-refine-and-critic/docs/zh.md)：evaluator-optimizer 是 Self-Refine 的推广；CRITIC 为 judge 提供 grounding。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：evaluator-optimizer 是五种 workflow 模式之一。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../19-benchmarks-swebench-gaia/docs/zh.md)、[阶段 14 · 20 基准评测：WebArena 与 OSWorld](../../20-benchmarks-webarena-osworld/docs/zh.md)：静态 benchmark 层。
- [阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../24-agent-observability-platforms/docs/zh.md)：LLM-as-judge 与 session replay 的平台。
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../26-failure-modes-agentic/docs/zh.md)：每种失效模式都应有对应的 eval case。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：LLM 应用评估的基础方法。

### 本节被哪些后续内容用到
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：把 eval 作为合并与发布的门禁。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)：独立评分者避免"自己评自己"。
- [阶段 14 · 52 在结果产生前设计成功指标](../../52-design-success-metrics/docs/zh.md)：先定义指标，再看结果。
- [阶段 13 · 27 Skill 评估、打包与可移植性](../../../13-tools-and-protocols/27-skill-evals-packaging-and-portability/docs/zh.md)：对 skill 做评估。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../../16-multi-agent-and-swarms/24-evaluation-coordination-benchmarks/docs/zh.md)：多 Agent 场景的评估。
- [阶段 17 · 21 对 LLM Features 进行 A/B 测试：GrowthBook、Statsig 与凭感觉判断的问题](../../../17-infrastructure-and-production/21-ab-testing-llm-features/docs/zh.md)：线上评估的实验方法。
- [阶段 19 · 11 LLM Observability 与评估仪表盘](../../../19-capstone-projects/11-llm-observability-dashboard/docs/zh.md)：综合项目中的评估仪表盘。

### 延伸关键词
`eval-driven development` · `SWE-bench Verified` · `BFCL` · `data contamination` · `LLM-as-judge` · `execution-based eval` · `trajectory efficiency` · `evaluator-optimizer` · `pass@1` · `CI gate` · `baseline / last-known-good` · `flaky test` · `session replay` · `rubric calibration`
