# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 24 节 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`collections.Counter`、`dataclasses`、`typing`）；不连接任何平台，不调用任何模型

---

## 1. 这份代码在考察什么

Langfuse、Phoenix、Opik 这类平台的核心流水线可以概括为四步：**接收 span → 按 session 分组 → 评估打分 → 汇总成看板**。这份代码用标准库把这四步各写成一个小函数：

1. `TraceCollector.ingest`：接收 GenAI 风格的 span（第 23 节的属性名）。
2. `TraceCollector.by_session`：按 `session_id` 分组——平台里的"Sessions"视图。
3. `scripted_llm_judge`：给每个 session 打 0–1 分并判 PASS/WARN/FAIL——对应讲义的 LLM-as-judge。
4. `categorize_failures` + `summarize` + `main`：统计失败原因、按分数排序、打印摘要——对应看板。

> 一句话：**可观测平台 = 采集 + 分组 + 评估 + 汇总**。但要看清：这里的"LLM-judge"**根本不是 LLM，也不看回答内容**，只是对 span 元数据的启发式扣分；而且演示代码对每个 session 评估了 3 次。理解这些简化，正好对应讲义列出的失败模式——"没有评估策略""judge 没有依据"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SpanEvent` | dataclass | trace id、session id、span 名、状态、属性 | 平台接收的一条 span |
| `SessionSummary` | dataclass | 每个 session 的 span 数、错误数、分数、失败原因 | 看板上的一行 |
| `TraceCollector` | 类 | `ingest` 追加 span；`by_session` 分组 | Tracing / 采集 |
| `scripted_llm_judge` | 函数 | 按 4 条规则扣分，返回 `(score, verdict)` | LLM-as-judge（简化版） |
| `categorize_failures` | 函数 | 统计错误 span 的 `error.reason` | 失败分类 |
| `summarize` | 函数 | 对每个 session 生成摘要，按分数升序 | 看板汇总 |
| `main` | 函数 | 造 3 个 session 的 span，打印摘要与汇总 | 演示 |

数据流：`main` 构造 `ok_spans` / `err_spans` / `slow_spans` → `collector.ingest` 逐条接收 → `summarize`：`by_session` 分组 → 每组 `scripted_llm_judge` + `categorize_failures` → `SessionSummary` 列表按分数排序 → 打印（循环中再次调用 judge）→ 再次 `summarize` 计算总错误数。

---

## 3. 逐段精讲

### 3.1 数据模型：`SpanEvent` 与 `SessionSummary`

```python
@dataclass
class SpanEvent:
    trace_id: str
    session_id: str
    name: str
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionSummary:
    session_id: str
    trace_count: int
    error_count: int
    eval_score_mean: float
    failure_reasons: Counter
```

- 三层标识：**session**（一次会话，可能包含多次 agent 运行）⊃ **trace**（一次 agent 运行）⊃ **span**（一步操作）。平台的"Sessions"视图按 session 分组，"Traces"视图按 trace。
- `status` 只有 `"ok"` / `"error"`，对应 OTel span 的状态码。
- ⚠️ `SpanEvent` 没有开始/结束时间。讲义 skill 文件要求的"latency distribution"无从计算，演示数据里叫 `slow_spans` 的 session 也只能用 token 数代替"慢"。
- ⚠️ 字段命名不准：`trace_count` 在 `summarize` 里被赋值为 `len(spans)`——实际是 **span 数**（`s001` 只有一条 trace `t001`，却得到 4）；`eval_score_mean` 只是单次评分，不是均值。打印时作者也写成了 `spans=...`，说明自己也意识到了这一点。

### 3.2 `TraceCollector`：采集与分组

```python
class TraceCollector:
    def __init__(self) -> None:
        self.spans: list[SpanEvent] = []

    def ingest(self, span: SpanEvent) -> None:
        self.spans.append(span)

    def by_session(self) -> dict[str, list[SpanEvent]]:
        result: dict[str, list[SpanEvent]] = {}
        for span in self.spans:
            result.setdefault(span.session_id, []).append(span)
        return result
```

- `setdefault(key, [])`：键不存在时先放入空列表并返回它，存在时直接返回已有列表，然后 `.append`——一行完成"分组"。等价于 `collections.defaultdict(list)`。
- 分组结果按**首次出现顺序**排列（Python 3.7+ 字典保持插入顺序）。
- ⚠️ 每次调用都**从头重算**，没有缓存；`main` 中它被调用了 6 次。真实平台在写入时就建好按 session/trace 的索引。
- 真实平台还要处理：乱序到达、同一 span 重复上报（去重）、trace 尚未结束（何时可以评估）、数据保留期等。

### 3.3 `scripted_llm_judge`：启发式扣分

```python
def scripted_llm_judge(session_spans: list[SpanEvent]) -> tuple[float, str]:
    errors = sum(1 for s in session_spans if s.status == "error")
    has_tool = any(s.name.startswith("tool_call") for s in session_spans)
    has_final = any(s.attributes.get("gen_ai.output.reference_id")
                    for s in session_spans)
    tokens_over = any(s.attributes.get("tokens", 0) > 2000 for s in session_spans)
    score = 1.0
    if errors:
        score -= 0.4
    if not has_final:
        score -= 0.3
    if not has_tool:
        score -= 0.1
    if tokens_over:
        score -= 0.1
    score = max(0.0, score)
    if score >= 0.8:
        verdict = "PASS"
    elif score >= 0.5:
        verdict = "WARN"
    else:
        verdict = "FAIL"
    return score, verdict
```

| 规则 | 条件 | 扣分 | 想表达的含义 |
|------|------|------|-------------|
| 出错 | 任一 span `status == "error"` | 0.4 | 运行失败 |
| 无输出 | 没有任何 span 带输出引用 | 0.3 | 没给出答案 |
| 无工具 | 没有 `tool_call*` span | 0.1 | 没查资料就回答 |
| token 超标 | 任一 span `tokens > 2000` | 0.1 | 成本/冗长 |

- 三个 session 的分数：`s001` 满分 1.0；`s002` = 1 − 0.4 − 0.3 − 0.1；`s003` = 1 − 0.1 − 0.1 = 0.8（刚好卡在 PASS 门槛）。
- ⚠️ **这不是 LLM-judge**：它不读回答内容，只看元数据。实测一个"有工具、有输出、无错误"但答案完全编造的 session 得 **1.0 PASS**。讲义的失败模式"Self-rolled LLM-judge without grounding"在这里更进一步——连 LLM 都没有。真实做法是从外部存储按 `reference_id` 取回正文，交给 judge 模型按 rubric 打分，并对事实性结论调用外部工具核实（CRITIC，第 05 节）。
- ⚠️ `has_final` 名不副实：它检查的是"**任一** span 有输出引用"，而不是"最后一步给出了最终答案"。
- ⚠️ `if errors:` 只看有无，5 个错误与 1 个错误扣分相同（实测 0.6 WARN）。
- ⚠️ `max(0.0, score)` 永远不会生效：全部扣分之和为 0.9，最低约 0.1。
- ⚠️ **浮点累积**：`s002` 的分数实际是 `0.19999999999999998`，打印 `:.2f` 才显示 0.20。分数恰好落在门槛上时（如 `s003` 的 0.8），浮点误差可能改变判决；用整数分值或 `round` 后再比较更稳妥。
- `s.attributes.get("tokens", 0)`：属性缺失时默认 0，避免 `KeyError`。注意 `tokens` 不是 OTel GenAI 的标准属性名（标准里是分输入/输出的 token 用量属性），这里是简化。

### 3.4 `categorize_failures`：失败原因计数

```python
def categorize_failures(session_spans: list[SpanEvent]) -> Counter:
    reasons: Counter = Counter()
    for span in session_spans:
        if span.status != "error":
            continue
        reason = span.attributes.get("error.reason", "unknown")
        reasons[reason] += 1
    return reasons
```

- `Counter` 是"计数字典"：不存在的键默认值为 0，所以可以直接 `+= 1`；`most_common()` 按次数降序返回。
- 没写 `error.reason` 的错误被归为 `"unknown"`——看板上 `unknown` 占比高，本身就是"埋点质量差"的信号。
- 跨 session 汇总"Top 失败原因"只需把多个 `Counter` 相加（`Counter.update`），代码没有做这一步（测验 Q11 补上了）。

### 3.5 `summarize`：生成看板行

```python
def summarize(collector: TraceCollector) -> list[SessionSummary]:
    summaries: list[SessionSummary] = []
    for session_id, spans in collector.by_session().items():
        score, _ = scripted_llm_judge(spans)
        summaries.append(SessionSummary(
            session_id=session_id,
            trace_count=len(spans),
            error_count=sum(1 for s in spans if s.status == "error"),
            eval_score_mean=score,
            failure_reasons=categorize_failures(spans),
        ))
    summaries.sort(key=lambda s: s.eval_score_mean)
    return summaries
```

- `score, _ = ...`：`_` 表示丢弃判决——这正是后面不得不再调一次 judge 的原因。
- `summaries.sort(key=...)`：按分数**升序**，最差的 session 排在最前面。这是看板的好习惯：先看最需要关注的。
- 用关键字参数构造 dataclass，字段一目了然。

### 3.6 `main`：演示数据与重复评估

```python
    print("\nsummary per session (what Langfuse/Phoenix/Opik show)")
    for summary in summarize(collector):
        score, verdict = scripted_llm_judge(collector.by_session()[summary.session_id])
        ...
    total_errors = sum(s.error_count for s in summarize(collector))
    total_sessions = len(collector.by_session())
    print(f"\naggregate: {total_errors} errors across {total_sessions} sessions")
```

- 三组演示数据：`s001` 正常（2 次 chat + 1 次工具）；`s002` chat 被限流（`rate_limited`）；`s003` 用 OpenAI、token 2500。
- ⚠️ **重复评估**：`summarize` 调用 2 次（各评 3 次），循环里再为每个 session 评 1 次，judge 共被调用 **9 次**（实测），`by_session()` 被调用 6 次。若 judge 是真实 LLM：评估费用 ×3；而且 LLM 输出不确定，排序用的分数（第一次）和打印的分数（第二次）可能不一致。修复方法：在 `SessionSummary` 中保存 `verdict`，只调用一次 `summarize`（测验 Q10）。
- ⚠️ 讲义说看板会显示"failure rate, top failure reasons, eval score distribution"，代码只打印了总错误数（还写成了 "1 errors"）。测验 Q11 补全了这些指标。
- 最后三行打印三个平台的定位，是讲义"Picking one"的摘要。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 内存列表存 span | 最简单 | 无持久化、无索引；平台用列式存储（如 ClickHouse）并建 session/trace 索引 |
| 每次查询都重新分组 | 代码短 | O(N) 重算；生产写入时建索引或物化视图 |
| 元数据启发式代替 LLM-judge | 可复现、零成本 | 看不到内容，编造的答案也能满分；生产用 rubric + judge 模型 + 外部依据 + 人工校准 |
| 固定扣分与门槛 | 易懂 | 未经校准；浮点累积在门槛附近不稳定；应用人工标注集校准门槛 |
| 只区分"有无错误" | 简化 | 错误数量、错误严重性都丢失 |
| span 无时间戳 | 简化 | 无法给出延迟分布；生产 span 必带起止时间 |
| 按分数升序排序 | 先看最差的 | —— |
| 判决不存入摘要 | 疏忽 | 导致重复评估；应存储评估结果（平台里评估结果本身也是一种数据，可追溯） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可写 `dict[str, list[SpanEvent]]` 等新式注解 |
| `@dataclass` + `field(default_factory=dict)` | `attributes: dict[str, Any] = field(default_factory=dict)` | 每个实例一个独立的新字典 |
| `collections.Counter` | `reasons[reason] += 1`、`.most_common()` | 计数字典，缺省键为 0；可直接相加合并 |
| `dict.setdefault` | `result.setdefault(span.session_id, []).append(span)` | 键不存在时插入默认值并返回，常用于分组 |
| 生成器表达式求和 | `sum(1 for s in spans if s.status == "error")` | 计数满足条件的元素个数 |
| `any()` | `any(s.name.startswith("tool_call") for s in session_spans)` | 只要有一个为真就返回 True，并提前停止 |
| `str.startswith` | `s.name.startswith("tool_call")` | 前缀判断 |
| `dict.get(k, default)` | `s.attributes.get("tokens", 0)` | 键缺失时返回默认值 |
| 增强赋值 | `score -= 0.4` | 等价于 `score = score - 0.4` |
| `if / elif / else` 链 | 判决 PASS / WARN / FAIL | 按门槛从高到低依次判断 |
| 返回元组 + 解包 | `return score, verdict`、`score, _ = ...` | 一次返回多个值；`_` 表示不使用的值 |
| `list.sort(key=lambda ...)` | `summaries.sort(key=lambda s: s.eval_score_mean)` | 原地按指定字段排序 |
| 关键字参数构造对象 | `SessionSummary(session_id=..., trace_count=...)` | 按名字传参，顺序无关、可读性好 |
| 列表拼接 | `ok_spans + err_spans + slow_spans` | 两个列表 `+` 得到新列表 |
| f-string 格式 | `f"score={score:.2f}"`、`f"x{count}"` | 两位小数；直接插值 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，瞬间完成）：

```text
summary per session (what Langfuse/Phoenix/Opik show)
  s002  verdict=FAIL  score=0.20  spans=2  errors=1
    failure: rate_limited x1
  s003  verdict=PASS  score=0.80  spans=2  errors=0
  s001  verdict=PASS  score=1.00  spans=4  errors=0

aggregate: 1 errors across 3 sessions

Langfuse: prompt versions tied to traces.
Phoenix: RAG relevancy + drift/clustering.
Opik: optimization + guardrail enforcement.
```

逐项解读：

- **排序**：按分数升序，最差的 `s002` 在最上面。
- **`s002` 0.20 FAIL**：有错误（−0.4）、唯一的 chat 出错没有输出（−0.3）、没有工具调用（−0.1）。真实值 `0.19999999999999998`。失败原因 `rate_limited x1` 来自 `error.reason` 属性——在真实平台上，这类失败应该触发"重试/退避/切换 provider"的告警，而不是质量问题。
- **`s003` 0.80 PASS**：没有工具（−0.1）、token 2500 超过 2000（−0.1）。名为 "slow" 却没有任何延迟数据；它恰好压在 PASS 门槛上。
- **`s001` 1.00 PASS**：有工具、有输出、无错误、token 都在 2000 以下。
- **`spans=` 列**：来自 `trace_count` 字段，实际是 span 数。
- **aggregate**：3 个 session 中共 1 个错误 span。讲义所说的失败率应为 1/3 ≈ 33.3%（测验 Q11 的看板函数输出了这个值以及分数分桶、按 provider 平均分：anthropic 0.6、openai 0.8）。
- 看不到的部分：这次运行中 judge 被调用了 9 次——输出里看不出来，但在使用真实 LLM-judge 时会直接体现为账单。

---

## 7. 动手改一改

1. 修复重复评估：给 `SessionSummary` 加 `verdict` 字段，`main` 只调用一次 `summarize`；用一个计数包装器确认 judge 只被调用 3 次（测验 Q10）。
2. 补全看板：失败率、判决分布、分数分桶（注意先 `round`）、跨 session 的 Top 失败原因、按 provider 的平均分（测验 Q11）。
3. 给 `SpanEvent` 加 `start_ms` / `end_ms`，计算每个 session 的端到端耗时与 P50/P95，并把"慢"作为单独的判据而不是用 token 代替。
4. （讲义练习 2）写一个真正的 judge 接口：`judge(question, answer, rubric) -> dict`，先用规则实现（如检查答案是否引用了检索到的来源 id），再留出替换为 LLM 调用的位置；把 judge 的模型版本和 rubric 版本写进评估结果。
5. 在 `invoke_agent` span 上加 `prompt.version`，构造两个版本的数据，按版本对比分数，体会"bisect to the prompt"（测验 Q12）。
6. （讲义练习 4）加一个"记录时 guardrail"：`ingest` 时扫描属性值，发现形如邮箱、手机号的字符串就替换为 `[REDACTED]`，并在 span 上标记 `guardrail.pii_redacted = True`。

---

## 8. 常见坑

- **把元数据规则当质量评估**：没有错误、调用了工具、有输出，不代表答案正确。
- **同一对象重复评估**：真实 LLM-judge 既花钱又不确定，结果必须存下来复用。
- **指标命名与含义不符**：`trace_count` 实为 span 数、`eval_score_mean` 不是均值，会误导看板读者。
- **浮点分数直接和门槛比较**：`1 − 0.4 − 0.3 − 0.1` 不等于 0.2；用整数分或先取整。
- **门槛决定可见性**：只统计 `< 0.5` 的 FAIL 时，大量 WARN 级回归会被忽略（测验 Q12）。
- **把基础设施错误混进质量指标**：`rate_limited` 是容量问题，应和"回答质量差"分开统计和告警。
- **没有 `error.reason`**：错误都归为 `unknown`，失败分类就失去意义。
- **全量采集一切**：trace 量随流量线性增长，规模化时必须采样（skill 文件的拒绝规则）。
