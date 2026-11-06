# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 23 节 失效模式：MAST、群体思维、同质化与级联错误 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`time`、`dataclasses`、`enum`）

---

## 1. 这份代码在考察什么

这份代码用不到 200 行标准库 Python 演示了讲义的三条主线：

1. **失败要先命名**：用规则把事故症状映射到 MAST 三个根类别（spec / coord / verify）和 Groupthink 五个家族标签。
2. **级联放大与熔断**：一个"负载越高越容易失败"的下游服务 + 每请求最多 4 次的朴素重试，对比有无 circuit breaker 时下游承受的总调用数。
3. **Circuit breaker 状态机**：CLOSED / OPEN / HALF_OPEN 三态、滑动窗口错误率、冷却时间。

讲义还提到 STRATUS 的 detection agent，但代码里**没有实现**（见 3.6）。另外模拟只把调用量放大到约 1.64 倍，而不是讲义叙述的 10 倍（见 3.4、第 6 节）。

> 一句话：**把"多 agent 系统为什么会失败"变成可以归类、可以计数、可以用熔断器截断的工程对象**——同时看清这个玩具模拟在哪些地方过于简化。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MAST_CATEGORIES` | 字典 | 三个根类别的代码 → 描述（含占比） | MAST 分类法 |
| `GROUPTHINK` | 字典 | 五个 Groupthink 家族的代码 → 描述 | Groupthink 家族 |
| `categorize_incident` | 函数 | 症状字典 → 第一个命中的 MAST 类别 | 事故分类 |
| `detect_groupthink` | 函数 | 症状字典 → 全部命中的 Groupthink 标签 | 同质化检测 |
| `BreakerState` | Enum | CLOSED / OPEN / HALF_OPEN | 熔断器状态 |
| `CircuitBreaker` | dataclass | `allow()` 决定是否放行，`record()` 记录结果并转移状态 | 熔断器 |
| `DownstreamService` | dataclass | 有效失败率 = 10% + 0.02 × load | 会退化的下游 |
| `simulate_retry_storm` | 函数 | 200 个请求、每个最多 4 次尝试，可选 breaker | retry storm |
| `demo_incident_categorization` / `demo_retry_storm` / `main` | 函数 | 打印两段演示与 Takeaways | 演示入口 |

数据流：`main()` → 5 个事故字典依次经过 `categorize_incident` + `detect_groupthink` 打印 → `simulate_retry_storm(200, False)` 与 `simulate_retry_storm(200, True)`（同一种子）→ 打印对比 → 打印 Takeaways。

---

## 3. 逐段精讲

### 3.1 两张分类表

```python
MAST_CATEGORIES = {
    "spec": "Specification Problem (41.77% of failures)",
    "coord": "Coordination Failure (36.94% of failures)",
    "verify": "Verification Gap (21.30% of failures)",
}

GROUPTHINK = {
    "monoculture": "monoculture collapse (same base model → correlated errors)",
    "conformity": "conformity bias (agents align with loudest peer)",
    ...
}
```

- 用短代码作键（`"spec"`），长描述作值，打印时两者都输出，便于日志聚合后再按代码统计分布。
- 占比数字直接写在描述里，来自讲义："Specification Problems (41.77%)…Coordination Failures (36.94%)…Verification Gaps (21.30%)"。
- 两张表是**正交**的两个维度：一个事故可以有 MAST 类别、也可以有 Groupthink 标签，也可以只有其一。

### 3.2 `categorize_incident`：首个命中即返回

```python
def categorize_incident(symptoms: dict) -> tuple[str, str]:
    if symptoms.get("role_conflict") or symptoms.get("task_ambiguity"):
        return "spec", MAST_CATEGORIES["spec"]
    if symptoms.get("state_drift") or symptoms.get("message_lost") or symptoms.get("sync_error"):
        return "coord", MAST_CATEGORIES["coord"]
    if symptoms.get("no_verifier") or symptoms.get("hallucination_propagation"):
        return "verify", MAST_CATEGORIES["verify"]
    return "unknown", "no MAST category matched"
```

- `dict.get(key)` 键不存在时返回 `None`（假值），所以症状字典可以只写出现的症状。
- 规则是**有优先级的 if 链**：spec > coord > verify。实测 `{"role_conflict": True, "state_drift": True}` 只返回 `spec`，`state_drift` 被吞掉。真实审计中一个事故常有多个成因，首个命中会系统性地让排在前面的类别占比偏高（测验 Q12 给出了返回全部命中的改法）。
- `unknown` 被当作正常返回值而不是异常——这与 `outputs/skill-mast-auditor.md` 的要求一致："Ignoring MAST-unknown incidents" 是 hard reject，未知事故说明分类法需要扩展。
- 这里的"分类器"是关键词规则，真实 MAST 审计是人工或 LLM 读 trace 后打标签。

### 3.3 `detect_groupthink`：全部命中都收集

```python
def detect_groupthink(symptoms: dict) -> list[tuple[str, str]]:
    hits = []
    if symptoms.get("correlated_errors"):
        hits.append(("monoculture", GROUPTHINK["monoculture"]))
    if symptoms.get("agreement_rate_spike"):
        hits.append(("conformity", GROUPTHINK["conformity"]))
    ...
    return hits
```

- 与 3.2 不同，这里是**多个独立的 if**，每命中一个就追加，返回列表。
- 症状键名本身就是讲义提到的"慢失败代理指标"：`agreement_rate_spike`（一致率**异常升高**→ 从众）、`retry_amplification`（重试放大 → 级联）、`coordination_drop_long_horizon`（长程任务协调下降 → ToM 不足）。注意是 *spike*：同质化让 agent 越来越一致，而不是越来越不一致（测验 Q11 讨论了讲义练习 2 在这一点上的措辞问题）。

### 3.4 `CircuitBreaker`：三态状态机

```python
@dataclass
class CircuitBreaker:
    failure_threshold: float = 0.5
    window_size: int = 20
    open_cooldown_s: float = 0.5
    state: BreakerState = BreakerState.CLOSED
    outcomes: list[bool] = field(default_factory=list)
    opened_at: float = 0.0

    def _error_rate(self) -> float:
        if not self.outcomes:
            return 0.0
        recent = self.outcomes[-self.window_size:]
        return 1.0 - (sum(recent) / len(recent))
```

- `outcomes` 记录每次调用成败（`True` = 成功）。`sum(recent)` 利用 `True == 1` 统计成功次数，错误率 = 1 − 成功率。
- `outcomes[-20:]` 取最后 20 个，就是"按次数计的滑动窗口"。
- `field(default_factory=list)`：dataclass 中可变默认值必须这样写，否则所有实例会共享同一个列表。

```python
    def allow(self) -> bool:
        if self.state == BreakerState.OPEN:
            if time.monotonic() - self.opened_at >= self.open_cooldown_s:
                self.state = BreakerState.HALF_OPEN
            else:
                return False
        return True

    def record(self, success: bool) -> None:
        self.outcomes.append(success)
        if self.state == BreakerState.HALF_OPEN:
            if success:
                self.state = BreakerState.CLOSED
            else:
                self.state = BreakerState.OPEN
                self.opened_at = time.monotonic()
        elif self.state == BreakerState.CLOSED:
            if self._error_rate() > self.failure_threshold and len(self.outcomes) >= self.window_size:
                self.state = BreakerState.OPEN
                self.opened_at = time.monotonic()
```

状态转移表：

| 当前状态 | 事件 | 新状态 |
|---|---|---|
| CLOSED | `record` 后窗口错误率 > 0.5 且累计样本 ≥ 20 | OPEN（记录 `opened_at`） |
| OPEN | `allow` 时距打开 < 0.5 s | 仍 OPEN，返回 `False`（短路） |
| OPEN | `allow` 时距打开 ≥ 0.5 s | HALF_OPEN，返回 `True`（放行一个探测） |
| HALF_OPEN | 探测成功 | CLOSED |
| HALF_OPEN | 探测失败 | OPEN（重新计时） |

- 默认参数下"错误率 > 0.5"等价于最近 20 次中失败 ≥ 11 次。
- `len(self.outcomes) >= self.window_size` 是**最小样本量**保护：前几次偶然失败不会立刻熔断。
- 用 `time.monotonic()` 而不是 `time.time()` 是正确的习惯：单调时钟不受系统改时间影响。
- ⚠️ 但**冷却按墙钟计**而模拟按"请求序号"推进：整个程序约 0.04 秒跑完，breaker 一旦打开就再也等不到 0.5 秒，模拟中永远不会进入 HALF_OPEN。HALF_OPEN 分支在本次运行中从未执行。实测把 `open_cooldown_s` 设为 0 后，breaker 每次打开后立刻半开放行，结果变成 `(328, 189, 0)`，与无 breaker 完全一样。
- ⚠️ HALF_OPEN 期间 `allow()` 不限制放行数量，单线程下没问题，并发场景下会一次放出一大批"探测"请求。
- ⚠️ CLOSED → OPEN 时没有清空窗口；回到 CLOSED 后窗口里仍是旧的失败记录，若下一次失败就可能立刻再次打开。生产实现通常在状态切换时重置计数。

### 3.5 `DownstreamService` 与 `simulate_retry_storm`

```python
@dataclass
class DownstreamService:
    base_failure_rate: float = 0.1
    load: int = 0

    def handle(self, rng: random.Random) -> bool:
        effective_rate = self.base_failure_rate + (self.load * 0.02)
        effective_rate = min(effective_rate, 0.99)
        return rng.random() > effective_rate
```

- `rng.random()` 均匀落在 [0, 1)，大于失败率就算成功，所以成功概率 = 1 − 有效失败率。
- 退化模型：每 1 单位 load 增加 2 个百分点失败率，封顶 99%。

```python
def simulate_retry_storm(requests: int, use_breaker: bool, seed: int = 0) -> tuple[int, int, int]:
    rng = random.Random(seed)
    service = DownstreamService()
    breaker = CircuitBreaker()
    ...
    for _ in range(requests):
        attempts_for_req = 0
        while attempts_for_req < 4:
            if use_breaker and not breaker.allow():
                short_circuits += 1
                break
            service.load = min(total_calls // 10, 50)
            total_calls += 1
            ok = service.handle(rng)
            if use_breaker:
                breaker.record(ok)
            if ok:
                successes += 1
                break
            attempts_for_req += 1
    return total_calls, successes, short_circuits
```

- `random.Random(seed)` 创建**独立的**随机数生成器，两次模拟用同一种子，便于对比（但因为 breaker 改变了调用次数，两次实际消耗的随机数序列在熔断后就不再对齐）。
- 每个请求最多尝试 4 次，失败立即重试，**没有退避、没有 jitter、没有重试预算**——这正是讲义"naive retries"的写照。
- ⚠️ `service.load = min(total_calls // 10, 50)`：load 是**累计调用数 / 10**，单调递增、永不下降。它更像"时间推进"而非"当前负载"：
  - 累计 0 / 100 / 200 / 328 / 450 次时，有效失败率分别为 0.10 / 0.30 / 0.50 / 0.74 / 0.99（已计算）。
  - breaker 短路只能让 load 停止增长，无法让下游"恢复"。所以这个模拟只能展示"breaker 减少了打到下游的调用"，展示不了"breaker 让下游喘口气后重新可用"。
- ⚠️ 短路分支只计数后 `break`，请求没有得到任何降级结果，与讲义"degraded-mode responses served"不符。
- 返回三元组 `(total_calls, successes, short_circuits)`，调用方用解包 `total_no_cb, succ_no_cb, _ = ...` 丢弃不需要的值。

### 3.6 演示函数与"缺席"的组件

```python
    for inc in incidents:
        name = inc.pop("name")
        cat, desc = categorize_incident(inc)
        gt = detect_groupthink(inc)
```

- `inc.pop("name")` 取出并**删除**名字键，剩下的字典只含症状。它会修改原列表里的字典（这里无副作用，因为列表是局部变量）。
- 讲义 Build It 列出 `FailureTaxonomy`、`CircuitBreaker`、`RetryStormSimulator`、`DetectionAgent` 四个组件，实际代码只有 `CircuitBreaker` 是类；`FailureTaxonomy` 和 `RetryStormSimulator` 以函数形式存在；`DetectionAgent`（以及 STRATUS 的 diagnosis / validation）**完全没有实现**，只在 Takeaways 里打印了一句 "STRATUS-style detection / diagnosis / validation adds 1.5x mitigation success"。讲义"Expected output"第 3 条"detection agent flags the pattern and names the MAST category"在实际输出中并不存在。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 关键词规则做分类 | 简单、可解释、零依赖 | 真实审计要读 trace，人工或 LLM 打标签，并允许多标签 |
| `categorize_incident` 首个命中即返回 | 代码短 | 多因事故被归到排在前面的类别，分布失真；应返回全部命中并区分主次因 |
| 按次数的滑动窗口 + 最小样本量 | 实现简单，避免冷启动误熔断 | 生产多用时间窗口（如最近 10 秒）+ 最小请求数；`outcomes` 应用 `deque(maxlen=...)` 防止无限增长 |
| 墙钟冷却（`time.monotonic`） | 贴近真实熔断器 | 在离散模拟中永不半开；模拟应使用"逻辑时钟"（tick 或请求序号） |
| 默认阈值 0.5 | 下游基线失败率就有 10%，阈值必须明显高于基线 | 讲义建议生产 5–10%，前提是基线错误率远低于此 |
| load = 累计调用 / 10 | 一行代码制造"越调越坏" | 无法表现恢复；应使用"每 tick 的调用数"作为负载 |
| 朴素立即重试、最多 4 次 | 用来制造放大 | 生产应有指数退避 + jitter + 每请求/全局重试预算 |
| 短路后直接放弃 | 代码简单 | 应返回缓存或默认值（降级），并单独统计降级次数 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟类型注解求值；可以在旧版本 Python 中使用 `tuple[str, str]` 等写法 |
| 类型注解 | `def categorize_incident(symptoms: dict) -> tuple[str, str]:` | 标注参数与返回值类型，运行时不强制检查 |
| `@dataclass` | `class CircuitBreaker:` 上方 | 根据类属性自动生成 `__init__`、`__repr__` 等 |
| `field(default_factory=list)` | `outcomes: list[bool] = field(default_factory=list)` | 可变默认值必须用工厂函数，每个实例各有一个新列表 |
| `Enum` | `class BreakerState(Enum): CLOSED = "closed"` | 有名字的常量集合，比裸字符串更不容易拼错；用 `==` 比较 |
| `dict.get` | `symptoms.get("role_conflict")` | 键不存在返回 `None` 而不是抛 `KeyError` |
| `dict.pop` | `name = inc.pop("name")` | 取出并删除键 |
| 元组返回与解包 | `cat, desc = categorize_incident(inc)`、`total_cb, succ_cb, sc = ...` | 一次返回多个值；`_` 表示丢弃 |
| 列表切片 | `self.outcomes[-self.window_size:]` | 取最后 N 个元素，不足 N 个时取全部 |
| 布尔值求和 | `sum(recent)` | `True` 当 1、`False` 当 0，直接得到成功次数 |
| `while` + `break` | `while attempts_for_req < 4: ... break` | 成功或被短路时提前跳出重试循环 |
| 独立随机数生成器 | `rng = random.Random(seed)` | 不影响全局 `random` 状态，结果可复现 |
| 单调时钟 | `time.monotonic()` | 只增不减，适合测量时间间隔 |
| 字符串乘法 | `"=" * 72` | 生成 72 个等号的分隔线 |
| f-string 宽度 | `f"total_calls={total_no_cb:4d}"` | `:4d` 表示整数右对齐占 4 位 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行（测验 Q10、Q11 的实验就是 import 本模块完成的） |

---

## 6. 运行结果解读

实际运行（Python 3，约 0.04 秒）：

```text
========================================================================
INCIDENT CATEGORIZATION — map symptoms to MAST + Groupthink families
========================================================================

  incident: two agents both reviewing
    MAST:       spec — Specification Problem (41.77% of failures)

  incident: agent A thinks done; agent B still running
    MAST:       coord — Coordination Failure (36.94% of failures)

  incident: hallucinated fact crosses agents
    MAST:       verify — Verification Gap (21.30% of failures)

  incident: 3 agents all give same wrong answer
    MAST:       unknown — no MAST category matched
    Groupthink: monoculture — monoculture collapse (same base model → correlated errors)
    Groupthink: conformity — conformity bias (agents align with loudest peer)

  incident: payment retries cascade to inventory
    MAST:       unknown — no MAST category matched
    Groupthink: cascade — cascading reliability failures (retry storms)

========================================================================
RETRY STORM — 200 requests against a 10% baseline-failing service
========================================================================
  no circuit breaker:  total_calls= 328  success= 189
  with circuit breaker: total_calls= 140  success= 113  short_circuited=87
  ...
```

逐项解读：

- **前三个事故**各命中一个 MAST 类别，是规则表的直接映射。
- **后两个事故**MAST 为 `unknown`，只有 Groupthink 标签。说明规则表没有把"相关错误""重试放大"映射到任何 MAST 根类别——按 skill 文件的要求，这类 `unknown` 应作为"分类法需要扩展"的信号报告，而不是丢掉。
- **无 breaker：328 次调用、189 次成功**。放大倍数 328 / 200 = 1.64x（种子 0–4 下为 319–337 次）。逐请求统计：130 个请求一次成功，32 / 18 / 9 个请求分别在第 2 / 3 / 4 次成功，11 个请求 4 次全失败（189 + 11 = 200）。讲义与 docstring 中的"10x load"在这里并没有出现。
- **有 breaker：140 次调用、113 次成功、87 次短路**。breaker 在第 113 个请求（累计第 140 次调用，此时 load = 13、有效失败率约 0.36，窗口内失败已 ≥ 11/20）打开；之后由于墙钟冷却 0.5 秒永远等不到，剩余 200 − 113 = 87 个请求全部被短路。所以"113 次成功"全部来自熔断前。
- **怎么看这组对比**：breaker 让下游少承受了 188 次调用（−57%），代价是少了 76 次成功。讲义的说法是"Success count may drop, but downstream survives"。但要注意：在这个模型里下游的失败率由累计调用数决定，"survives"只体现为调用数停止增长，模拟里并没有恢复过程。
- **阈值扫描**（测验 Q10 的完整表格）：阈值 0.05 → 26 次调用即熔断；0.7 → 280 次；0.9 → 从不熔断，结果与无 breaker 相同。

---

## 7. 动手改一改

1. **讲义练习 1**：把 `CircuitBreaker()` 改成 `CircuitBreaker(failure_threshold=t)`，对 t ∈ {0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9} 打印三元组，复现测验 Q10 的表格，并画出"总调用数 vs 成功数"的取舍曲线。
2. **修复墙钟问题**：给 `CircuitBreaker` 加一个 `now` 参数（或注入一个 `clock` 函数），在模拟中用"请求序号"作为逻辑时间，冷却设为例如 20 个请求。观察 HALF_OPEN → CLOSED / OPEN 的往返是否出现。
3. **让负载可恢复**：把 `load` 改成"最近 50 次尝试中真正打到下游的调用数"（用 `deque` 记录每个时间步的调用），再配合第 2 题，观察 breaker 打开后下游失败率回落、半开探测成功、重新关闭的完整周期。
4. **加重试预算与退避**：每个请求最多 2 次重试、全局重试量不超过首发请求量的 10%；比较"仅预算 / 仅 breaker / 两者都有"三种配置的总调用数与成功数。
5. **讲义练习 2**：实现 3 个并行 agent 的一致率监控（参考测验 Q11），用"逐步相关"的模拟触发报警；思考为什么报警要用双向阈值。
6. **进阶：实现 `DetectionAgent`**：输入一段时间序列指标（重试率、一致率、错误率），输出症状字典交给 `categorize_incident` / `detect_groupthink`，并在应用"打开 breaker"这一缓解后用 validation 函数检查重试率是否回落——补齐讲义声称而代码缺失的 STRATUS 环节。

---

## 8. 常见坑

- **模拟里用墙钟**：离散事件模拟的"时间"应该是逻辑时钟；否则结果依赖机器速度，而且像本例这样某些分支永远不会执行。
- **以为 breaker 会提高成功率**：短期内 breaker 通常**降低**成功数（拒绝了本可能成功的请求），它的价值是保护下游、防止全局雪崩。评估时要看系统整体可用性与恢复时间。
- **阈值低于基线错误率**：下游基线就有 10% 失败时把阈值设成 5%，正常波动就会熔断。阈值要相对基线设定，并设置最小样本量。
- **`outcomes` 无限增长**：每次调用都 `append`，长期运行会占满内存；用 `collections.deque(maxlen=window_size)` 即可。
- **状态切换不重置窗口**：从 HALF_OPEN 回到 CLOSED 后窗口里仍是旧失败，可能立即再次熔断，形成抖动。
- **短路即失败**：没有降级路径的 breaker 只是把"慢失败"变成"快失败"；用户体验仍然是报错。
- **首个命中式分类**：多因事故只记一个类别，审计分布会偏向规则表中靠前的类别。
- **把一致率下降当作同质化信号**：monoculture / conformity 让一致率**上升**；一致率骤降更可能是某个 agent 出故障或协调崩溃。
