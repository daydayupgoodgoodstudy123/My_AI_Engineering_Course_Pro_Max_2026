# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 11 节 LLM Observability 与评估仪表盘 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`hashlib`、`math`、`random`、`time`、`re`、`collections`、`dataclasses`）；没有真实的 OTel SDK、ClickHouse 或 LLM-judge

---

## 1. 这份代码在考察什么

讲义的综合项目是一个自托管的 LLM 可观测平台：OpenTelemetry SDK（GenAI 语义约定）→ OTLP HTTP → Collector（tail sampling）→ ClickHouse / Postgres / S3 → eval 任务（DeepEval、RAGAS、LLM-judge）→ 漂移检测（PSI）→ Prometheus Alertmanager → Slack/PagerDuty → Next.js 看板；验收标准是注入"1% 泄漏假 SSN"的回归后 5 分钟内告警。

`main.py` 的 docstring 说它抓住的"最难的架构原语"是：**tail-sampling collector + 以子 span 形式存在的 eval**——错误 trace 必留、成功 trace 采样、每条 trace 都可以挂上携带分数的 eval span。用标准库实现了整条链路的缩微版：

1. `Span` 数据模型（带 GenAI 属性）；
2. `TailSampler`（错误必留、高风险 eval 必留、其余按比例）；
3. `SpanStore`（内存版 ClickHouse，按用户、模型聚合）；
4. 三个启发式 eval（faithfulness、toxicity、PII）；
5. 基于 prompt 哈希分桶的 PSI 漂移检测；
6. 阈值告警器；
7. 200 条合成 trace + 1% 注入的 PII 回归。

> 一句话：**这份代码让你看清 span、采样、eval、告警之间的数据依赖**；同时它在"采样后的成本统计""哈希当 embedding""可观测数据里存明文 PII""告警没有时间窗"这几处埋着可观测系统最典型的坑。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Span` | dataclass | trace_id、span_id、parent、name、时间、attributes、events、status；`is_llm()` | OTel span / GenAI semconv |
| `TailSampler` | dataclass | `decide(trace)`：错误必留、高毒性/高 PII 必留、其余按 `sample_rate` | tail sampling |
| `SpanStore` | dataclass | 存 span，并按用户、模型计数、按用户累计成本 | ClickHouse 替身 + 成本归因 |
| `eval_faithfulness` | 函数 | 回复词中有多少比例出现在上下文里 | DeepEval faithfulness 替身 |
| `eval_toxicity` | 函数 | 关键词命中比例 × 10，封顶 1 | toxicity 替身 |
| `eval_pii_leak` | 函数 | SSN 正则 0.95、邮箱 0.6、否则 0.05 | PII LLM-judge 替身 |
| `prompt_fingerprint` | 函数 | SHA-256 首字节 mod 8 | embedding 分桶替身 |
| `psi` | 函数 | 两组桶计数的 PSI | 漂移指标 |
| `synth_trace` | 函数 | 生成 root + llm_call 两个 span，可注入 PII 回复 | 合成流量 |
| `enrich_with_evals` | 函数 | 给每个 LLM span 加一个 eval 子 span | eval span |
| `alerter` | 函数 | 扫描全部 eval span，PII > 0.8 或毒性 > 0.5 即告警 | Alertmanager 替身 |
| `main` | 函数 | 200 条 trace：生成 → eval → 采样 → 入库；记录指纹；打印、告警、PSI | 端到端演示 |

数据流：`synth_trace` → `enrich_with_evals` → `sampler.decide` →（保留时）`store.insert_trace`；同时（不论是否保留）`prompt_fingerprint` → 基线/当前两组 → `psi`；最后 `alerter(store)`。

---

## 3. 逐段精讲

### 3.1 `Span`：最小化的 OTel span

```python
@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    start_ms: int
    duration_ms: int
    attributes: dict
    events: list[dict] = field(default_factory=list)
    status: str = "ok"

    def is_llm(self) -> bool:
        return "gen_ai.system" in self.attributes
```

- `trace_id` 把同一次请求的所有 span 串起来，`parent_span_id` 构成树：root（`chat_turn`）→ `llm_call` → `eval`。这就是看板上 trace 瀑布图的数据基础。
- `is_llm()` 用"是否带 `gen_ai.system` 属性"判断一个 span 是不是 LLM 调用——这正是 GenAI 语义约定的意义：不同 SDK 产生的 span 只要属性规范，就能用同一条规则识别。
- `events` 字段从未被使用；`status` 只有默认值 `"ok"`，整个演示中没有任何 span 是 `"error"`。
- 真实 OTel 的 trace_id 是 16 字节随机数、span_id 是 8 字节，这里用 `t0008_1` 这样的可读字符串。

### 3.2 `TailSampler`：在 trace 结束后做决定

```python
@dataclass
class TailSampler:
    sample_rate: float = 0.10
    rng: random.Random = field(default_factory=lambda: random.Random(3))

    def decide(self, trace: list[Span]) -> bool:
        if any(s.status == "error" for s in trace):
            return True
        for s in trace:
            if s.name == "eval" and (
                s.attributes.get("toxicity", 0) > 0.5
                or s.attributes.get("pii_leak", 0) > 0.8
            ):
                return True
        return self.rng.random() < self.sample_rate
```

- 三条规则依次判断：有错误必留 → 有高风险 eval 必留 → 否则以 `sample_rate` 概率保留。这对应讲义 Build It 第 1 步（错误 100%、成功 10%）和练习 5（toxicity > 0.5 必留）。
- `decide` 接收的是**完整 trace**（一个 span 列表），这就是"tail"的含义：只有 trace 结束、所有 span 都到齐，才能看到错误和 eval 分数。真实 Collector 要在内存里缓冲 span 并等待一段决策时间。
- `rng` 的默认工厂是 `random.Random(3)`，但 `main` 里传入了与流量生成共用的 `rng`（种子 5），两者交错消耗随机数。
- ⚠️ 由于没有任何 span 是 error，第一条规则在演示中**一次都没触发**。
- ⚠️ 第二条规则之所以能生效，是因为 `main` 里先 `enrich_with_evals` 再 `decide`——eval 跑在 100% 的流量上。讲义的架构是"eval 任务读最近 15 分钟的**采样** trace"，顺序相反。两种顺序的成本与漏检风险见测验 Q4、Q9。

### 3.3 `SpanStore`：内存版 ClickHouse 与成本归因

```python
@dataclass
class SpanStore:
    spans: list[Span] = field(default_factory=list)
    by_user: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_model: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    cost_by_user: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    def insert_trace(self, trace: list[Span]) -> None:
        self.spans.extend(trace)
        for s in trace:
            if s.is_llm():
                u = s.attributes.get("user_id", "anon")
                m = s.attributes.get("gen_ai.request.model", "unknown")
                self.by_user[u] += 1
                self.by_model[m] += 1
                self.cost_by_user[u] += s.attributes.get("cost_usd", 0.0)
```

- 写入时就做聚合（物化视图的思路），读取看板时不必再扫描全表。ClickHouse 里常用 `AggregatingMergeTree` / 物化视图实现同样的效果。
- `defaultdict(float)` 让 `+=` 不需要先判断键是否存在。
- ⚠️ **成本统计发生在采样之后**：只有被保留的 trace 才计入。实测真实总成本 5.05 美元，看板只显示 1.29 美元（约 25%），而且用户排序被打乱——看板说 u_01 最省钱（0.21），真实 u_01 是第二贵的（1.26）。讲义把"每用户成本"称为关键产品指标，这里恰恰算错了。成本、请求数这类计数应在采样前导出，或按 `1/采样概率` 加权。
- ⚠️ 整个 span（包括 attributes 里的 `prompt`、`response` 原文）原样入库，见 3.5。

### 3.4 三个 eval 替身

```python
def eval_faithfulness(response: str, context: str) -> float:
    r = set(response.lower().split())
    c = set(context.lower().split())
    if not r:
        return 0.0
    return len(r & c) / len(r)


def eval_toxicity(response: str) -> float:
    bad = {"hate", "kill", "stupid", "garbage"}
    words = response.lower().split()
    hits = sum(1 for w in words if w in bad)
    return min(1.0, hits / max(1, len(words)) * 10)


def eval_pii_leak(response: str) -> float:
    import re
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", response):
        return 0.95
    if re.search(r"[\w.+-]+@[\w.-]+", response):
        return 0.6
    return 0.05
```

- **faithfulness**：回复中的词有多少比例出现在上下文中（不是 Jaccard，分母只有回复）。正常回复 "the weather in Tokyo is mild" 与上下文 "relevant weather context Tokyo mild" 的重叠为 `{weather, tokyo, mild}`，得分 3/6 = 0.5；泄漏回复得 0.0。真实的 DeepEval/RAGAS faithfulness 用 LLM 把回答拆成若干 claim，再逐条判断是否被上下文支持。
- **toxicity**：命中率 × 10 再封顶到 1。"you are stupid" 命中 1/3 → 3.33 → 1.0；单个词 "garbage" 也是 1.0——极短文本里一个词就"满分"。
- **PII**：SSN 形如 `ddd-dd-dddd` 得 0.95；任何含 `@` 的片段（甚至 `a@b`）得 0.6；不带横线的 `123456789` 得 0.05（漏检）。
- `import re` 写在函数体内：每次调用都执行一次 import 语句（模块已缓存，开销小但不规范），通常应放在文件开头。
- 三个分数的阈值（PII > 0.8、toxicity > 0.5）在 `TailSampler` 和 `alerter` 里各写了一遍，是重复的"魔法数字"。

### 3.5 合成流量与注入回归：`synth_trace`

```python
def synth_trace(trace_id: str, leak_pii: bool, rng: random.Random) -> list[Span]:
    model = rng.choice(["claude-sonnet-4-7", "gpt-5-4", "gemini-3-pro"])
    user = rng.choice(["u_01", "u_02", "u_03", "u_04"])
    root = Span(..., name="chat_turn", start_ms=int(time.time() * 1000),
                duration_ms=rng.randint(400, 2400), attributes={"app_id": "chatbot"})
    prompt = rng.choice([...4 个 Tokyo 天气相关句子...])
    resp = "your ssn is 123-45-6789" if leak_pii else "the weather in Tokyo is mild"
    ...
    llm = Span(..., name="llm_call",
               start_ms=root.start_ms + 50, duration_ms=root.duration_ms - 80,
               attributes={
                   "gen_ai.system": model.split("-")[0],
                   "gen_ai.request.model": model,
                   "gen_ai.usage.input_tokens": rng.randint(80, 800),
                   "gen_ai.usage.output_tokens": rng.randint(20, 300),
                   "user_id": user,
                   "prompt": prompt,
                   "response": resp,
                   "context": ctx,
                   "cost_usd": round(rng.uniform(0.002, 0.05), 4),
               })
    return [root, llm]
```

- 子 span 的时间嵌套在父 span 内：开始晚 50 ms、时长少 80 ms，瀑布图上 llm_call 落在 chat_turn 之内。
- 注入回归：`leak_pii=True` 时回复固定为 `"your ssn is 123-45-6789"`。`main` 中每条 trace 以 1% 概率注入；种子 5 下 200 条里出现了 5 次（t0008、t0152、t0154、t0186、t0196），比期望的 2 次多，P(≥5) 约 5%。
- ⚠️ `gen_ai.system` 被设为 `model.split("-")[0]`，即 `claude`、`gpt`、`gemini`。按 OTel GenAI 语义约定，它应是提供方/系统标识（如 openai、anthropic），模型名放在 `gen_ai.request.model`。
- ⚠️ `cost_usd` 是随机数，与 input/output token 数无关；真实系统按"token 数 × 模型单价"计算（`code/ts/src/pricing.ts` 就是做这件事的）。
- ⚠️ `prompt`、`response` 以明文写入 attributes。注入回归后，5 条 SSN 原文全部进入了 `SpanStore`——可观测平面本身成了 PII 的二次泄漏点。生产中应在 eval 之后、落库之前打码，或只存哈希与分数。
- `start_ms=int(time.time() * 1000)`：所有 trace 的时间几乎相同（同一秒内生成），时间维度在这个模拟里没有意义，也就无法计算 MTTR。

### 3.6 `enrich_with_evals`：eval 作为子 span

```python
def enrich_with_evals(trace: list[Span]) -> list[Span]:
    out = list(trace)
    for s in trace:
        if s.is_llm():
            ...
            ev = Span(trace_id=s.trace_id, span_id=f"{s.span_id}_eval",
                      parent_span_id=s.span_id, name="eval",
                      start_ms=s.start_ms + s.duration_ms,
                      duration_ms=120,
                      attributes={
                          "faithfulness": eval_faithfulness(resp, ctx),
                          "toxicity": eval_toxicity(resp),
                          "pii_leak": eval_pii_leak(resp),
                      })
            out.append(ev)
    return out
```

- `out = list(trace)` 先复制一份，再往副本里追加，不修改调用方传入的列表——遍历 `trace` 的同时向 `out` 追加是安全的。
- eval span 的 `parent_span_id` 指向被评估的 LLM span，`trace_id` 相同：这就是讲义说的"Eval span — Child span carrying an eval score linked to the original LLM call span"。好处是在看板上可以从任何一个低分直接跳转到原始调用。
- eval span 的开始时间 = LLM span 结束时间，模拟"同步 eval"；讲义的 eval 是异步批处理，真实时间会晚得多（最多 15 分钟），这直接影响 MTTR。
- eval 分数的属性名（`faithfulness`、`toxicity`、`pii_leak`）是自定义的，没有命名空间前缀。

### 3.7 漂移检测：`prompt_fingerprint` 与 `psi`

```python
def prompt_fingerprint(prompt: str, n_bins: int = 8) -> int:
    h = hashlib.sha256(prompt.encode()).digest()
    return h[0] % n_bins


def psi(a: list[int], b: list[int], n_bins: int = 8) -> float:
    ca = [0] * n_bins
    cb = [0] * n_bins
    for v in a:
        ca[v] += 1
    for v in b:
        cb[v] += 1
    total_a = max(sum(ca), 1)
    total_b = max(sum(cb), 1)
    score = 0.0
    for i in range(n_bins):
        pa = max(ca[i] / total_a, 0.0001)
        pb = max(cb[i] / total_b, 0.0001)
        score += (pa - pb) * math.log(pa / pb)
    return score
```

- PSI 公式 `Σ (p_a − p_b) · ln(p_a / p_b)`：每一项都 ≥ 0（两个因子同号），等价于 `KL(a‖b) + KL(b‖a)`。
- `max(..., 0.0001)` 是空桶平滑：否则 `ln(0)` 或除以 0 会出错。两边都为空的桶截断后相等，贡献为 0。
- `max(sum(ca), 1)` 防止空列表时除以 0。
- `h[0]`：`digest()` 返回 `bytes`，索引得到 0–255 的整数。
- ⚠️ **这不是 embedding 漂移**：4 个固定 prompt 的指纹是 `[6, 7, 4, 4]`——两个不同句子撞进同一个桶，8 个桶中 5 个永远为空。哈希的雪崩效应还会让语义相近的 prompt 落到无关的桶里。讲义要求的是对 sentence-transformers 的 prompt embedding 计算 PSI。
- ⚠️ **样本太小、噪声接近阈值**：基线 151 条、当前 49 条，而 prompt 分布全程没有变化。用相同样本量模拟 5,000 次无漂移情形，PSI 均值 0.056、95 分位 0.170，约 2.7% 超过 0.2。本次的 0.083 完全是抽样噪声。
- 漂移统计用的是**全部** 200 条 trace（在采样判断之外记录），注释特意说明"input distribution, not output"。

### 3.8 `alerter` 与 `main`

```python
def alerter(store: SpanStore) -> list[str]:
    alerts: list[str] = []
    pii_events = [s for s in store.spans
                  if s.name == "eval" and s.attributes.get("pii_leak", 0) > 0.8]
    if pii_events:
        alerts.append(f"PII LEAK DETECTED: {len(pii_events)} events "
                      f"(first trace: {pii_events[0].trace_id})")
    ...
```

- 告警条件是"库里存在任意一个 PII > 0.8 的 eval span"——"只要出现一次就告警"，对 1% 这种低频事件是合理的策略。
- 两个相邻的 f-string 会被 Python 自动拼接成一个字符串。
- ⚠️ **没有时间窗口**：扫描全量 `store.spans`，无法回答"最近 5 分钟有没有"，也无法判断告警何时恢复；没有记录告警时间，MTTR 无法测量。真实系统用 Prometheus 规则（如 `increase(pii_leak_total[5m]) > 0`）+ Alertmanager 路由。

`main` 的主循环：

```python
    for i in range(200):
        leak = rng.random() < 0.01
        trace = synth_trace(f"t{i:04d}", leak_pii=leak, rng=rng)
        trace = enrich_with_evals(trace)
        if sampler.decide(trace):
            store.insert_trace(trace)
        llm_span = trace[1]
        fp = prompt_fingerprint(llm_span.attributes.get("prompt", ""))
        (current_fps if i > 150 else baseline_fps).append(fp)
```

- `TailSampler(sample_rate=0.20, ...)`：演示用 20%，讲义是 10%，类默认值也是 0.10。
- `trace[1]` 硬编码"第二个 span 是 LLM span"，依赖 `synth_trace` 的返回顺序；更稳妥的写法是 `next(s for s in trace if s.is_llm())`。
- `(current_fps if i > 150 else baseline_fps).append(fp)`：用条件表达式选出列表对象再调用方法，`i ≤ 150` 进基线（151 条），其余 49 条进当前窗口。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 先 eval 再采样 | 保证高风险 trace 一定被保留 | 要对 100% 流量跑 eval；讲义是对采样后数据跑批量 eval，生产常用"便宜规则全量 + LLM-judge 抽样"两级 |
| 写入时聚合成本 | 看板查询快 | 只聚合了采样后的数据，成本被低估约 4 倍；应在采样前导出计数指标或按 1/p 加权 |
| 启发式 eval（词重叠、关键词、正则） | 无需模型即可运行 | 精度低；生产用 DeepEval/RAGAS/LLM-judge，并用人工标注集校准 |
| 哈希分桶代替 embedding | 无需 embedding 模型 | 不反映语义分布；样本小、桶空，PSI 噪声接近阈值 |
| 告警扫描全量 | 实现最简 | 无时间窗、无法测 MTTR、无法恢复；生产用 Prometheus 规则 + Alertmanager |
| attributes 存原文 | 方便调试和 eval | 可观测平面自身存储 PII；应在 eval 后打码、存哈希，并做访问控制 |
| `gen_ai.system` = 模型名前缀 | 随手可得 | 不符合语义约定，跨 SDK 聚合会出错 |
| 单进程内存实现 | 一个脚本跑完 | 讲义要求 1k spans/s 持续摄入，需要 Collector 水平扩展 + ClickHouse 批量写入 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 默认值 | `status: str = "ok"`、`sample_rate: float = 0.10` | 有默认值字段放在后面 |
| `field(default_factory=lambda: ...)` | `field(default_factory=lambda: defaultdict(float))`、`lambda: random.Random(3)` | 每个实例一个新对象 |
| `collections.defaultdict` | `defaultdict(int)`、`defaultdict(float)` | 缺键自动初始化为 0 / 0.0 |
| 联合类型 | `parent_span_id: str | None` | 根 span 没有父节点 |
| `any` + 生成器 | `any(s.status == "error" for s in trace)` | 有一个为真就返回 True，短路求值 |
| `dict.get` 默认值 | `s.attributes.get("toxicity", 0)` | 缺键时返回 0 |
| 多行条件 | `if s.name == "eval" and (... or ...):` | 括号内可以换行 |
| 集合运算 | `len(r & c) / len(r)` | 交集大小 |
| `str.split()` | `response.lower().split()` | 按任意空白切分 |
| 函数内 import | `def eval_pii_leak(...): import re` | 合法但不推荐，通常放文件顶部 |
| `re.search` + `\b` | `re.search(r"\b\d{3}-\d{2}-\d{4}\b", response)` | 单词边界，避免匹配更长数字的一部分 |
| `bytes` 索引 | `hashlib.sha256(...).digest()[0]` | 取第一个字节，得到 0–255 的 int |
| 列表乘法初始化 | `[0] * n_bins` | 创建 n 个 0（不可变元素时安全） |
| `math.log` | `math.log(pa / pb)` | 自然对数 |
| `rng.choice` / `rng.uniform` | `rng.choice(["u_01", ...])`、`rng.uniform(0.002, 0.05)` | 随机选元素 / 区间均匀浮点 |
| `round(x, n)` | `round(rng.uniform(...), 4)` | 保留 4 位小数 |
| `time.time()` | `int(time.time() * 1000)` | 当前 Unix 时间（秒）转毫秒 |
| 复制列表 | `out = list(trace)` | 浅拷贝，追加不影响原列表 |
| 条件表达式选对象 | `(current_fps if i > 150 else baseline_fps).append(fp)` | 表达式结果是列表对象，再调用方法 |
| 生成器转 dict | `dict((k, round(v, 4)) for k, v in ...)` | 等价于字典推导式 `{k: round(v, 4) for ...}` |
| 相邻字符串自动拼接 | `f"PII LEAK DETECTED: ... " f"(first trace: ...)"` | 编译期拼成一个字符串 |
| f-string 格式符 | `{psi_val:.3f}`、`{i:04d}` | 三位小数；补零到 4 位 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，种子 5；`start_ms` 依赖当前时间，但不影响任何输出）：

```text
ingested spans     : 165
spans by model     : {'gpt-5-4': 24, 'claude-sonnet-4-7': 14, 'gemini-3-pro': 17}
cost by user       : {'u_02': 0.3625, 'u_03': 0.3835, 'u_04': 0.3294, 'u_01': 0.2116}

ALERTS:
  - PII LEAK DETECTED: 5 events (first trace: t0008)

PSI (current vs baseline): 0.083
```

逐项解读（补充数据来自额外的实测脚本）：

- **165 个 span = 55 条 trace × 3**：5 条 PII 泄漏 trace 因 `pii_leak = 0.95 > 0.8` 被必留；其余 195 条中 50 条被 20% 采样选中。"错误必留"规则触发 0 次（没有 error span）。
- **spans by model**：24 + 14 + 17 = 55，只计 LLM span。
- **cost by user 合计 1.287 美元**：真实 200 条 trace 的总成本是 5.051 美元。真实每用户成本为 u_01 1.2642、u_02 1.2389、u_03 1.4292、u_04 1.1189——看板的排序（u_01 最低）与真实排序（u_04 最低）不同。
- **PII 告警**：5 次泄漏全部被捕获，第一条是 t0008。注意 5 次中有 4 次落在 i > 150 的"当前窗口"里，但 PSI 监测的是 **prompt**（输入）分布，回复里的泄漏不会反映到 PSI 上——输出质量问题要靠 eval 分数趋势发现，而不是输入漂移。
- **PSI = 0.083**：低于 0.2，不告警。但 prompt 分布全程没有变化，这个数完全是抽样噪声（无漂移模拟的 95 分位约 0.170）。讲义 Use It 里的"weekly PSI 0.08 (below 0.2 threshold)"与此巧合地一致。

---

## 7. 动手改一改

1. **修正成本归因**：在 `main` 里、`sampler.decide` 之前，把每条 trace 的成本累加到一个独立的 `true_cost_by_user`；再给 `SpanStore` 加一个按 `1/p` 加权的版本（p 为该 trace 的采样概率），比较三者。
2. **先采样后 eval**（讲义架构）：把顺序改成 `decide`（只用 error 规则 + 10% 采样）→ 对保留的 trace 才 `enrich_with_evals`；重复 1,000 次，统计"5 次泄漏至少被发现一次"的比例，与理论值 `1 − 0.9⁵ ≈ 0.41` 对比。再加一个"便宜的 SSN 正则预标记"，看比例如何回到 100%。
3. **PSI 显著性**：写一个置换检验——把基线和当前两组指纹合并、随机打乱、按原大小重新切分，重复 1,000 次得到 PSI 的零分布，报告本次 PSI 的 p 值。再把当前窗口的 prompt 换成一批"购物"类问题，确认 PSI 显著升高。
4. **按 app 分开算漂移**（讲义练习 3）：给 trace 随机分配两个 `app_id`，只让其中一个 app 的 prompt 分布发生变化，比较全局 PSI 与按 app PSI 的灵敏度。
5. **时间窗告警与 MTTR**：用 `start_ms = 基准时间 + i × 1000`（每秒一条）模拟时间，在第 100 条时"部署"泄漏版本（之后 1% 泄漏），告警器每 30 秒运行一次、只看最近 5 分钟，输出 MTTR（参考测验 Q12）。
6. **进阶**：把 `gen_ai.system` 改成符合约定的提供方标识，并用 `opentelemetry-sdk` 的 `InMemorySpanExporter` 真实产生 span，验证属性能被 `is_llm()` 识别。

---

## 8. 常见坑

- **在采样后的数据上算计数类指标**：成本、请求数、错误率都会偏差；采样前导出指标，或按采样概率加权。
- **eval 与采样的顺序不清**：先采样会漏掉低频高危事件，先 eval 成本高；需要"便宜规则全量 + 贵 judge 抽样"。
- **用哈希当 embedding**：哈希只区分字面，不反映语义；漂移检测要基于语义表示。
- **把 PSI 阈值当成统计检验**：小样本下噪声就能接近 0.2；要配合样本量、置信区间或连续窗口确认。
- **可观测系统存明文 PII**：trace 里的 prompt/response 会被看板用户、备份、归档看到；eval 后、落库前打码。
- **告警没有时间窗**：无法测 MTTR，也无法自动恢复。
- **语义约定属性填错**：`gen_ai.system` 填模型名前缀会让跨 SDK 的聚合与过滤失效。
- **阈值散落多处**：PII 0.8、toxicity 0.5 在采样器和告警器中各写一次，改一处忘一处；应集中成配置。
