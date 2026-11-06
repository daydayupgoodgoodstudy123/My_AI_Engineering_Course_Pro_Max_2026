# 测验 · 失效模式：MAST、群体思维、同质化与级联错误（Failure Modes — MAST, Groupthink, Monoculture, Cascading Errors）

> **阶段 16 · 多智能体与集群 · 第 23 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | MAST 分类法 | Cemri et al.（NeurIPS 2025）从 7 个开源 MAS 的 1642 条执行 trace 归纳出 3 个根类别 + 14 个子类型；这些系统在真实任务上的失败率为 41%–86.7% |
| 2 | 三个根类别的占比 | Specification Problems 41.77%（角色/任务定义不清）、Coordination Failures 36.94%（通信与状态同步）、Verification Gaps 21.30%（没人独立核验） |
| 3 | 每类对应的缓解手段 | Spec → 显式角色契约 + 验收标准 + 派发前 spec 预检；Coord → 版本化共享状态 + 关键消息 ack + 定期状态同步；Verify → 独立只读 verifier + handoff 前置检查 + 结果日志 |
| 4 | Groupthink 家族（arXiv:2508.05687） | 五种"同质化/互相模仿"失败：monoculture collapse、conformity bias、deficient ToM、mixed-motive drift、cascading reliability failures |
| 5 | Monoculture collapse | 多个 agent 共用同一底座模型或训练数据 → 错误高度相关；"三个 agent 共用一个 LLM，就共享它的幻觉"，投票也救不了 |
| 6 | 级联与 retry storm | 下游 10% 失败 → 上游朴素重试 → 下游负载翻倍 → 超时更多 → 再重试……讲义描述的极端情形是数秒内 10 倍负载；修复靠 circuit breaker + 每请求重试预算 |
| 7 | Circuit breaker 状态机 | CLOSED（正常放行、统计错误率）→ 超阈值 OPEN（直接短路，返回缓存/默认值）→ 冷却后 HALF_OPEN（放一个探测请求）→ 成功回 CLOSED、失败回 OPEN |
| 8 | Memory poisoning | 一个 agent 的幻觉写进共享记忆，下游当成事实；症状是"准确率缓慢下降"而非崩溃；在 MAST 中属于共享记忆层的 verification gap |
| 9 | STRATUS 三件套 | Detection（看症状）+ Diagnosis（按 MAST 推断根因）+ Validation（施加缓解后确认症状消失），讲义：缓解成功率提升 1.5x |
| 10 | 静默失败与慢失败代理指标 | 最贵的是"看起来合理但错了"的输出；用一致率、重试率、输出长度分布、版本间编辑距离等 proxy 提前发现漂移；按季度做 MAST 审计 |

### 核心技能（能动手做到）

- [ ] 给定一个多 agent 事故描述，判断它属于 MAST 哪个根类别、是否叠加 Groupthink 标签，并说出对应缓解手段
- [ ] 手写一个带 CLOSED / OPEN / HALF_OPEN 三态、滑动窗口错误率的 circuit breaker，并说清每个状态转移的条件
- [ ] 读懂 `simulate_retry_storm`，解释"无 breaker 328 次调用 / 有 breaker 140 次调用"是怎么来的，并指出这个负载模型的局限
- [ ] 扫描 breaker 阈值，说出"阈值低 → 下游更安全但成功数更少；阈值高 → 形同虚设"的取舍
- [ ] 实现一个慢失败代理指标（如 3 个并行 agent 的两两一致率），并用模拟的相关性漂移触发报警
- [ ] 按"采样 → 分类 → 分布表 → 排序缓解 → 选 2–3 项落地"的流程设计一次 MAST 审计

---

## 二、基础自测（选择题）

**Q1.** 按 MAST（Cemri et al. 2025）的统计，占失败比例**最高**的根类别是：

- A. Verification Gaps（21.30%）
- B. Coordination Failures（36.94%）
- C. Groupthink 家族中的 monoculture collapse
- D. Specification Problems（41.77%）

**Q2.** 讲义说 Verification Gaps 按数量只占 21.30%，却是"单次失败成本最高"的类别。原因是：

- A. 它产生的是看起来合理但错误的输出（静默失败），异常日志与告警都捕捉不到
- B. 它总是导致整个集群宕机
- C. 修复它需要换掉底座模型
- D. 它只出现在使用 MCP 的系统里

**Q3.** 本节代码在默认参数（200 个请求、`seed=0`）下运行，**无** circuit breaker 时 `total_calls` 是多少？

- A. 200
- B. 140
- C. 328
- D. 2000（讲义所说的 10 倍负载）

**Q4.** 本节 `CircuitBreaker` 处于 `HALF_OPEN` 时，下一次 `record(False)` 会让它：

- A. 保持 `HALF_OPEN`，直到窗口内错误率超过阈值
- B. 立即回到 `OPEN`，并把 `opened_at` 重置为当前时间
- C. 回到 `CLOSED`，因为单次失败不算数
- D. 清空 `outcomes` 列表后回到 `CLOSED`

**Q5.** "一个 agent 把幻觉出的事实写进共享记忆，下游 agent 把它当事实继续推理，准确率缓慢下降。"在 MAST 中最贴切的归类是：

- A. Verification Gap（共享记忆层缺少独立核验）
- B. Specification Problem（角色定义不清）
- C. Coordination Failure（消息丢失）
- D. 不属于任何 MAST 类别，只属于 Groupthink

**Q6.** 运行本节代码时，事故 "3 agents all give same wrong answer"（`correlated_errors` + `agreement_rate_spike`）的输出是：

- A. `MAST: verify`，无 Groupthink 标签
- B. `MAST: coord`，Groupthink: `cascade`
- C. `MAST: spec`，Groupthink: `monoculture`
- D. `MAST: unknown`，Groupthink: `monoculture` 和 `conformity`

**Q7.** `CircuitBreaker` 的 `open_cooldown_s=0.5` 用的是 `time.monotonic()` 墙钟时间，而整个模拟只跑几毫秒。由此带来的实际效果是：

- A. 每次 OPEN 后过 0.5 次请求就会进入 HALF_OPEN
- B. breaker 永远不会打开
- C. breaker 一旦打开，本次模拟中再也不会进入 HALF_OPEN，剩余请求全部被短路
- D. 结果与墙钟无关，把 cooldown 改成 0 输出完全不变

**Q8.** STRATUS（NeurIPS 2025）的"三件套"专用 agent 是：

- A. Planner、Executor、Critic
- B. Detection、Diagnosis、Validation
- C. Proposer、Voter、Aggregator
- D. Router、Retriever、Ranker

---

## 三、动手 / 代码题

**Q9.** 阅读下游服务的退化模型与模拟循环：

```python
@dataclass
class DownstreamService:
    base_failure_rate: float = 0.1
    load: int = 0

    def handle(self, rng: random.Random) -> bool:
        effective_rate = self.base_failure_rate + (self.load * 0.02)
        effective_rate = min(effective_rate, 0.99)
        return rng.random() > effective_rate

# simulate_retry_storm 内部
            service.load = min(total_calls // 10, 50)
            total_calls += 1
```

1. `load` 实际衡量的是什么？它会不会因为 breaker 短路而下降？
2. 当累计调用到第 0、100、200、328 次时，有效失败率分别是多少？累计多少次后服务几乎必然失败？
3. 模块 docstring 说"amplifies through retries to 10x load without a breaker"。实际运行的放大倍数是多少？为什么到不了 10x？
4. 如果要让模拟真正体现"breaker 让下游恢复"，负载模型应该怎么改？

**Q10.** 讲义练习 1 要求"改变阈值，观察取舍"。下面是用相同 `seed=0`、200 个请求、`window_size=20` 扫描 `failure_threshold` 的实测结果（breaker 打开后由于墙钟冷却，再未恢复）：

| failure_threshold | total_calls | success | short_circuited | 打开时的请求序号 |
|---|---|---|---|---|
| 0.05 | 26 | 25 | 175 | 25 |
| 0.1 | 41 | 38 | 162 | 38 |
| 0.2 | 110 | 97 | 103 | 97 |
| 0.3 | 111 | 97 | 103 | 97 |
| 0.5（默认） | 140 | 113 | 87 | 113 |
| 0.7 | 280 | 176 | 17 | 182 |
| 0.9 | 328 | 189 | 0 | 从未打开 |

1. 默认阈值 0.5、窗口 20 时，最近 20 次中至少要有几次失败才会打开？
2. 解释这张表体现的取舍。为什么 0.9 等价于没有 breaker？
3. 讲义 Ship It 建议"默认打开阈值 5–10% 错误率"，但代码默认 0.5。在本模拟中直接用 0.05 会出现什么问题？生产中如何避免"刚开始几次偶然失败就熔断"？

**Q11.** 讲义练习 2：实现一个**慢失败代理指标**——3 个并行 agent 的两两一致率（agreement rate），并通过"逐渐让 agent 输出相关"来模拟 monoculture 漂移，触发报警。写出实现，并思考：练习原文说"当一致率**骤降**时报警"，但相关性漂移会让一致率怎样变化？

**Q12.** 讲义 Build It 声称 `code/main.py` 实现了 `FailureTaxonomy`、`CircuitBreaker`、`RetryStormSimulator`、`DetectionAgent` 四个组件，预期输出包括"detection agent 标出模式并命名 MAST 类别""breaker 打开后返回降级响应"。对照真实代码：

1. 哪些组件实际不存在、是用什么形式代替的？
2. "降级响应（degraded-mode responses）"在代码里有没有？被短路的请求最后是什么结果？
3. `categorize_incident` 用 if 链按顺序返回第一个命中的类别。对 `{"role_conflict": True, "state_drift": True}` 它返回什么？这样设计有什么问题？请改成返回全部命中类别。

---

## 四、面试高频题

**Q13.**（基础必考）MAST 把多 agent 系统的失败分成哪三类？各举一个例子，并给出对应的工程缓解手段。

**Q14.**（原理深挖）为什么"多加几个 agent 投票"解决不了 monoculture collapse 和 conformity bias？有哪些真正有效的手段？

**Q15.**（工程实践）请讲清 circuit breaker 的三态状态机、关键参数，以及它与重试预算（retry budget）、指数退避的关系。在多 agent 系统中应该把 breaker 放在哪里？

**Q16.**（场景设计）你负责一个由"检索 agent → 写作 agent → 审核 agent"组成的生产系统，最近用户投诉"答案越来越不靠谱"，但错误日志一切正常。你会如何排查和治理？

**Q17.**（追问型）STRATUS 的 detection / diagnosis / validation 三个 agent 本身也是 LLM，它们会不会也陷入同样的失败模式？怎么设计才能让"监控者"本身可信？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Specification Problems (41.77%) — role ambiguity, unclear task definitions"。三者占比 41.77 / 36.94 / 21.30，合计约 100%。A、B 是另外两个根类别，数字较小；C 不是 MAST 的根类别，而是 arXiv:2508.05687 提出的 Groupthink 家族成员，二者是两套互补的分类。

### Q2 — 答案：A

讲义："A system that produces plausible-but-wrong outputs cannot be detected by exception logs. This is why verification gaps are the most expensive category per-failure even though they are only 21.30% by count." 静默错误会被用户、下游 agent 甚至共享记忆当成正确结果继续使用，发现时往往已经扩散。B 描述的是级联故障，验证缺口通常恰恰"不出事故"；C、D 无依据。

### Q3 — 答案：C

实际运行输出：`no circuit breaker:  total_calls= 328  success= 189`。A 是请求数（每个请求至少调用一次，所以 total ≥ 200）；B 是**有** breaker 时的调用数；D 是讲义叙述中"10x"的想象值——本模拟只放大到 328/200 = 1.64 倍（见 Q9）。

### Q4 — 答案：B

```python
        if self.state == BreakerState.HALF_OPEN:
            if success:
                self.state = BreakerState.CLOSED
            else:
                self.state = BreakerState.OPEN
                self.opened_at = time.monotonic()
```

HALF_OPEN 是"试探"状态：一次探测失败就重新打开并重新计时；一次成功就关闭。A 混淆了 CLOSED 状态的判断逻辑；C 方向反了；D 代码中从不清空 `outcomes`（这本身也是个小问题：列表无限增长，见讲解第 8 节）。

### Q5 — 答案：A

讲义："In MAST terms, this is a verification gap at the shared-memory layer." 缓解手段是第 13 节的 append-only 日志 + provenance（来源记录）+ 不可写的 verifier。B 与角色无关；C 消息并没有丢，反而是"错误消息被可靠地传递了"；D 错在 MAST 有对应类别——不过它确实可能叠加 Groupthink 中的 cascade 特征。

### Q6 — 答案：D

`categorize_incident` 只认 `role_conflict / task_ambiguity / state_drift / message_lost / sync_error / no_verifier / hallucination_propagation` 这些键，`correlated_errors` 与 `agreement_rate_spike` 一个都不命中，于是返回 `unknown`；`detect_groupthink` 则命中 `monoculture` 和 `conformity` 两个标签。实际输出：

```text
  incident: 3 agents all give same wrong answer
    MAST:       unknown — no MAST category matched
    Groupthink: monoculture — monoculture collapse (same base model → correlated errors)
    Groupthink: conformity — conformity bias (agents align with loudest peer)
```

这也提示：MAST 与 Groupthink 是两个正交维度，一个事故可以只落在其中一个上。

### Q7 — 答案：C

breaker 在第 113 个请求（累计第 140 次调用）时打开，之后每次 `allow()` 检查 `time.monotonic() - opened_at >= 0.5`，而整个程序运行约 0.04 秒，条件永远不成立，于是剩余 200 − 113 = 87 个请求全部短路——正好等于输出里的 `short_circuited=87`。A 把秒当成了请求次数；B 与输出矛盾；D 错：实测把 `open_cooldown_s` 改成 0 后结果变成 `(328, 189, 0)`，与无 breaker 完全相同（每次打开后立刻 HALF_OPEN、放行探测，相当于从不短路）。这说明模拟结果依赖墙钟，换到很慢的机器上理论上也可能不同。

### Q8 — 答案：B

讲义：Detection agent 观察症状（高分歧、重试尖峰、准确率漂移）；Diagnosis agent 按 MAST 推断根因；Validation agent 在缓解后确认症状消失。A 是第 08 节的角色专业化；C 像投票/聚合拓扑；D 是 RAG 流水线组件。注意：本节代码**并没有**实现 STRATUS，只在 Takeaways 中打印了一句。

### Q9 — 参考答案

1. `load = min(total_calls // 10, 50)` 是**累计调用次数 / 10**，本质上是"时间/进度"，不是"当前并发负载"。它单调不减，breaker 短路只会让它**不再增长**，但永远不会下降——模拟里下游没有"恢复"这个概念。
2. 有效失败率 = `min(0.1 + 0.02 × min(total//10, 50), 0.99)`（已用 Python 计算）：

   | 累计调用 | load | 有效失败率 |
   |---|---|---|
   | 0 | 0 | 0.10 |
   | 100 | 10 | 0.30 |
   | 200 | 20 | 0.50 |
   | 328 | 32 | 0.74 |
   | 450 | 45 | 1.00 → 截断为 0.99 |

   累计约 450 次后几乎必然失败。
3. 实际放大倍数 328 / 200 = **1.64x**，5 个种子下 319–337 次，都在 1.6–1.7x。原因：每个请求最多 4 次尝试且大部分首发即成功（`seed=0` 时 130 个请求一次成功、只有 11 个请求 4 次都失败）；而且只有 200 个请求，累计调用还没到 450 就结束了。docstring 和讲义中的"10x"是对真实事故的叙述，本模拟并没有复现，这是讲义与代码的一处不一致。
4. 改造方向：用离散时间步（tick）模拟，每个 tick 进入若干新请求；`load` = 本 tick（或最近 N 个 tick）的调用数，而不是累计数；失败的请求在下一 tick 重试（可加指数退避和 jitter）；breaker 的冷却按 tick 计而不是墙钟。这样无 breaker 时可以看到"重试 → 负载上升 → 失败率上升 → 更多重试"的正反馈，有 breaker 时能看到负载回落、HALF_OPEN 探测成功、恢复 CLOSED 的完整周期。

### Q10 — 参考答案

1. 判断条件是 `_error_rate() > failure_threshold` 且 `len(outcomes) >= window_size`。最近 20 次的错误率要**严格大于** 0.5，即失败数 ≥ 11 次。
2. 取舍：阈值越低，breaker 越早熔断，下游承受的总调用越少（26 → 328），但被拒绝的请求越多、成功数越低（25 → 189）；阈值越高，越晚熔断甚至不熔断。0.9 要求最近 20 次里失败 ≥ 19 次，而在 328 次调用结束前有效失败率最高约 0.74，窗口错误率达不到 0.9，于是从未打开，结果与无 breaker 的 `(328, 189)` 完全一致。0.2 与 0.3 几乎相同，是因为在那一段失败率爬升时窗口错误率恰好先后越过两个阈值、打开时机只差一次调用。
3. 0.05 意味着最近 20 次中只要有 2 次失败就熔断，而下游基线失败率就是 10%——**正常波动就会触发熔断**，第 25 个请求后全部被拒，可用性灾难。讲义"5–10%"的建议是针对"基线错误率远低于此"的生产服务。避免误熔断的做法：设置最小请求量（本代码的 `len(outcomes) >= window_size` 就是这个作用）、按时间窗口而不是次数窗口统计、阈值相对基线设置（如基线的 2–3 倍）、HALF_OPEN 放行多个探测请求再决定、对不同错误类型（超时 vs 4xx）区别对待。

### Q11 — 参考答案

参考实现（已实际运行，5 个种子均在漂移开始后 112–171 步内报警）：

```python
import random
from collections import deque

class AgreementMonitor:
    """3 个并行 agent 的两两一致率；相对基线偏离超过 delta 时报警。"""
    def __init__(self, window=50, baseline_n=100, delta=0.15):
        self.window = deque(maxlen=window)
        self.baseline, self.baseline_buf = None, []
        self.baseline_n, self.delta = baseline_n, delta

    def observe(self, answers):
        a, b, c = answers
        agree = ((a == b) + (a == c) + (b == c)) / 3
        if self.baseline is None:                      # 先积累基线
            self.baseline_buf.append(agree)
            if len(self.baseline_buf) >= self.baseline_n:
                self.baseline = sum(self.baseline_buf) / len(self.baseline_buf)
            return None
        self.window.append(agree)
        if len(self.window) < self.window.maxlen:
            return None
        rate = sum(self.window) / len(self.window)
        return rate if abs(rate - self.baseline) > self.delta else None

def simulate(steps=600, seed=0):
    rng = random.Random(seed)
    mon = AgreementMonitor()
    for t in range(steps):
        rho = 0.0 if t < 300 else min(1.0, (t - 300) / 200)   # 第 300 步起逐渐相关
        truth = rng.randint(0, 3)
        shared = truth if rng.random() < 0.7 else rng.randint(0, 3)  # "共同底座模型"的答案
        answers = [shared if rng.random() < rho
                   else (truth if rng.random() < 0.7 else rng.randint(0, 3))
                   for _ in range(3)]
        alert = mon.observe(answers)
        if alert is not None:
            return t, round(mon.baseline, 3), round(alert, 3)

print(simulate())   # (447, 0.61, 0.767)
```

关键观察：**相关性漂移会让一致率上升**（本例基线 0.61 → 报警时 0.767），而不是下降。因为三个 agent 越来越多地抄同一个"共享答案"，包括共享的错误。所以练习原文"when it drops sharply"与"simulate monoculture drift"其实指向相反方向：一致率骤降提示的是协调崩溃或某个 agent 故障，一致率**异常升高**才是 monoculture / conformity 的信号（代码里 `detect_groupthink` 的键名正是 `agreement_rate_spike`）。因此报警要用双向阈值 `abs(rate - baseline)`。更好的代理还可以对比"一致率"与"一致且正确率"（在有标注的 golden set 上），一致率升而正确率不升就是 groupthink。

### Q12 — 参考答案

1. 实际存在的只有 `CircuitBreaker` 类。`FailureTaxonomy` 由两个函数 `categorize_incident` + `detect_groupthink` 和两个字典 `MAST_CATEGORIES` / `GROUPTHINK` 代替；`RetryStormSimulator` 由函数 `simulate_retry_storm` + `DownstreamService` 代替；`DetectionAgent` 和 STRATUS 三件套**完全没有实现**，只在 Takeaways 中打印了一句"adds 1.5x mitigation success"。
2. 没有。短路分支只做 `short_circuits += 1; break`，请求既不算成功也没有拿到缓存/默认结果——在真实系统中相当于直接给用户报错。真正的降级应当在短路时返回缓存或默认值，并单独统计 `degraded` 数。
3. 返回 `('spec', ...)`（已运行验证），`state_drift` 被忽略。问题：一个事故常常同时涉及多个类别（例如角色不清导致两个 agent 同时写状态），首个命中即返回会让审计分布系统性偏向排在前面的 Spec 类别。改法：

```python
MAST_RULES = {
    "spec":   ("role_conflict", "task_ambiguity"),
    "coord":  ("state_drift", "message_lost", "sync_error"),
    "verify": ("no_verifier", "hallucination_propagation"),
}

def categorize_incident_all(symptoms: dict) -> list[tuple[str, str]]:
    hits = [(cat, MAST_CATEGORIES[cat]) for cat, keys in MAST_RULES.items()
            if any(symptoms.get(k) for k in keys)]
    return hits or [("unknown", "no MAST category matched")]
```

审计时再按"主因 / 次因"分别统计。另外按 skill 文件（`outputs/skill-mast-auditor.md`）的要求，`unknown` 不能丢弃，应作为"分类法需要扩展"的信号单独报告。

### Q13 — 参考回答要点

- **Specification Problems（41.77%）**：任务或角色定义不清。例：两个 agent 都以为自己是 reviewer；"总结一下"但用户要的是特定角度；没有成功标准，agent 不知道是否完成。缓解：显式角色契约（写明做什么、**不做什么**）、每个任务的验收测试、派发前由单独 agent 做 spec 预检。
- **Coordination Failures（36.94%）**：通信或状态同步崩溃。例：两个 agent 无同步地写共享状态；消息在队列里丢失或超时；A 认为已完成而 B 仍在执行（state drift）。缓解：版本化共享状态 + 乐观并发控制、关键消息显式 ack（未 ack 则重试）、定期状态同步 checkpoint。
- **Verification Gaps（21.30%）**：输出未经独立核验。例：agent 自称成功无人检查；链式 agent 层层信任上游。缓解：只读、独立数据源的 verifier agent；handoff 契约"A 的输出必须通过检查器 C 才能进入 B"；结果日志用于事后分析。
- 加分点：说出数据来源（7 个开源 MAS、1642 条 trace、失败率 41–86.7%）；指出"按数量排序"与"按单次代价排序"不同，验证缺口最贵；提到 Groupthink 家族是正交的补充维度。

### Q14 — 参考回答要点

- **根因是错误相关性**：投票/多数决的收益来自"各 agent 错误独立"（Condorcet 陪审团定理的前提）。同一底座模型、同一 prompt、同一检索结果下，三个 agent 的错误高度相关，多数决只是把同一个错误重复三遍。
- **Conformity**：辩论/群聊中 agent 会向最自信或最先发言的同伴靠拢，即使它是错的，进一步降低多样性。
- **有效手段**：
  - 模型异构：不同厂商/不同尺寸的底座模型，或不同温度、不同 system prompt；
  - 信息异构：不同检索源、不同工具，避免共享同一份可能被污染的上下文；
  - 独立作答后再汇总（先盲投再讨论），隐藏其他 agent 的置信度或身份；
  - 指定"反方"角色（devil's advocate）；
  - 监控一致率：一致率异常升高是 groupthink 的慢失败信号（见 Q11）；
  - 外部验证：用工具执行、单元测试、golden set 而不是"更多 LLM 意见"做最终裁决。
- 常见误区：把"agent 数量多"当成"可靠性高"；讲义原话"That is not debuggable by 'just add more agents.'"

### Q15 — 参考回答要点

- **三态**：CLOSED（放行并统计滑动窗口错误率）→ 错误率超阈值且样本量足够 → OPEN（直接短路，返回缓存/默认值/友好错误）→ 冷却时间到 → HALF_OPEN（放行少量探测请求）→ 成功则 CLOSED，失败则 OPEN 并重新计时。
- **关键参数**：错误率阈值（讲义建议 5–10%，需高于基线波动）、窗口大小与最小请求数、冷却时间、HALF_OPEN 探测数量；哪些错误计入（超时、5xx 计入，4xx 通常不计）。
- **与重试的关系**：
  - 重试预算（每请求最多 N 次、或全局重试量不超过正常流量的 10%）限制单个请求的放大；
  - 指数退避 + jitter 把重试在时间上摊开，避免同步重试洪峰；
  - breaker 从全局视角切断对"已坏"下游的调用，让它有机会恢复。三者叠加使用；只有退避没有预算和 breaker，仍会出现讲义里的 retry storm（讲义的例子正是"exponential backoff but naive"）。
- **放置位置**：每一个对外部依赖的出站调用（工具调用、其他 agent 的 A2A 调用、模型 API）都包一层；讲义 "Circuit breakers everywhere. Each outbound call to any dependent service."
- 加分点：指出本节代码用墙钟冷却导致模拟中永不恢复、并且没有降级返回值；生产库（如 resilience4j、Envoy 的 outlier detection）都把这些参数做成可配置。

### Q16 — 参考回答要点

- **定性**：错误日志正常 + 质量缓慢下降 = 典型的静默/慢失败，优先怀疑 verification gap、memory poisoning、monoculture drift，而不是崩溃类故障。
- **排查**：
  1. 采样近期 trace（随机或分层采样，至少几百条），人工标注 success/failure，按 MAST + Groupthink 分类，得到分布（参照 skill 文件的审计流程）；
  2. 看慢失败代理指标的时间序列：审核 agent 的通过率是否趋近 100%（审核形同虚设）、写作与审核的一致率是否异常升高、输出长度分布是否漂移、重试率；
  3. 检查共享记忆/缓存：是否有未经验证的条目被反复引用，追溯 provenance；
  4. 用 golden dataset 回归，确认质量下降的起点，对照该时间点的模型/prompt/数据变更。
- **治理**：审核 agent 改为只读、独立数据源，且与写作 agent 使用不同模型；共享记忆改为 append-only + 来源标注 + 写入前验证；建立 golden set 周回归；部署 detection agent 监控代理指标，先只做 detection，噪声大时再加 diagnosis；为各类失败设置 failure budget（超预算即暂停发布）。
- 常见误区：只看异常日志和延迟；手挑几个"离谱案例"代替随机采样（skill 文件明确列为 hard reject）。

### Q17 — 参考回答要点

- **会**。监控 agent 同样有幻觉、同样可能与被监控系统共用底座模型（monoculture），也可能被"大家都说没问题"带偏（conformity）。
- **设计原则**：
  - Detection 尽量基于**确定性指标**（重试率、错误率、一致率、延迟分布、golden set 得分），LLM 只用于解释，而不是作为唯一触发器；
  - Diagnosis 输出的是"假设 + 证据"，需要可追溯到具体 trace；
  - Validation 用缓解前后的**同一组指标**对比，而不是让 LLM 判断"看起来好了"；
  - 监控 agent 与业务 agent 使用不同模型/不同数据源，且对业务状态只读、不可写；
  - 对监控 agent 自身也做抽样人工审查和 golden set 回归；
  - 高风险缓解动作（回滚、熔断全局开关）保留人工确认。
- 加分点：类比 SRE——告警规则本身也要测试（告警演练、混沌工程），呼应阶段 17 的 SRE 与混沌工程小节；讲义提示"Start with the detection agent only; add diagnosis when symptoms are noisy"，逐步引入可以降低监控系统本身的复杂度风险。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 13 共享记忆与黑板模式](../../13-shared-memory-blackboard/docs/zh.md)：memory poisoning、append-only 日志与只读 verifier 的出处。
- [阶段 16 · 14 面向 Agents 的共识与拜占庭容错](../../14-consensus-and-bft/docs/zh.md)：错误 agent 存在时如何仍达成正确结论，与 monoculture 的"相关错误"形成对照。
- [阶段 16 · 15 投票、自洽性与辩论拓扑](../../15-voting-debate-topology/docs/zh.md)：投票为什么依赖错误独立性，conformity bias 如何破坏辩论。
- [阶段 16 · 18 心智理论与涌现协调](../../18-theory-of-mind-coordination/docs/zh.md)：Groupthink 家族中 deficient ToM 的背景。
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../../14-agent-engineering/26-failure-modes-agentic/docs/zh.md)：单 agent 的失败模式，本节是它的多 agent 版本。

### 本节被哪些后续内容用到
- [阶段 16 · 24 Evaluation 与协调基准评测](../../24-evaluation-coordination-benchmarks/docs/zh.md)：如何系统地度量多 agent 系统的失败率与协调质量。
- [阶段 16 · 25 案例研究与 2026 年前沿进展](../../25-case-studies-2026-sota/docs/zh.md)：真实系统如何应对这些失败模式。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)：circuit breaker 在自主系统中的用法。
- [阶段 17 · 23 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：STRATUS 式检测-诊断-验证在生产中的落地。
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../../17-infrastructure-and-production/24-chaos-engineering-llm/docs/zh.md)：主动注入故障来验证 breaker 与降级路径。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：慢失败代理指标需要的可观测性基础设施。

### 延伸关键词
`MAST` · `Groupthink` · `monoculture collapse` · `conformity bias` · `retry storm` · `circuit breaker` · `retry budget` · `exponential backoff + jitter` · `memory poisoning` · `STRATUS` · `silent failure` · `golden dataset` · `failure budget` · `agreement rate`
