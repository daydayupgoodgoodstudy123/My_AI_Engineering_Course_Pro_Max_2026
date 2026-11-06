# 测验 · LLM Observability 与评估仪表盘（LLM Observability & Eval Dashboard）

> **阶段 19 · 综合项目 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：`code/ts/` 下另有一个 TypeScript 的 span 解析 / 汇总 / 定价骨架，本测验以 Python 的 `main.py` 为主。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 可观测平面的职责 | 讲义：成本归因、幻觉检测、漂移监控、越狱信号、SLO 看板、PII 泄漏告警——与模型并列运行 |
| 2 | 统一的摄入 schema | 开源参考实现（Langfuse、Phoenix、OpenLLMetry）都收敛到 OpenTelemetry GenAI semantic conventions；一个 SDK 可以覆盖 OpenAI、Anthropic、Google、LangChain、LlamaIndex、vLLM |
| 3 | 典型生产形态 | OTLP HTTP 摄入 → Collector（采样、扇出）→ ClickHouse 存 span、Postgres 存元数据、S3 存原始事件 → eval 任务、漂移检测、Prometheus → Alertmanager → Slack/PagerDuty；Next.js 15 + Recharts 做 UI |
| 4 | GenAI span 属性 | `gen_ai.system`、`gen_ai.request.model`、`gen_ai.usage.input_tokens`、`gen_ai.response.id` 等；ClickHouse 表按这些字段建列 |
| 5 | Tail sampling | 在 trace **结束后**决定保留与否，可以"看到"错误；讲义配置：错误 trace 100% 保留、成功 trace 保留 10% |
| 6 | Eval 作为子 span | DeepEval（faithfulness、toxicity、answer relevance）、RAGAS、自定义 LLM-judge（PII 泄漏）对采样 trace 打分，结果作为挂在原 LLM span 下的 eval span 写回 |
| 7 | 漂移检测 | 对 prompt embedding 分布做 PSI 或 KL；讲义：PSI > 0.2 通常意味着有意义的漂移；每周与过去 4 周基线比较 |
| 8 | 回归探针与 MTTR | 讲义：故意注入"1% 概率泄漏假 SSN"的 bug，测从部署到 Slack 告警的时间，目标 5 分钟以内 |
| 9 | 每用户成本 | 按 user_id 在时间窗内归因美元成本，是关键产品指标 |
| 10 | 评分表 | span schema 覆盖 25（目标 6+ 个 SDK 家族）+ eval 正确性 20 + MTTR 20 + 1k spans/s 持续摄入 20 + 告警与漂移 15 |

### 核心技能（能动手做到）

- [ ] 读懂 `TailSampler.decide`，说出它保留 trace 的三条规则，以及"先 eval 再采样"和"先采样再 eval"的区别
- [ ] 手算 PSI：`Σ (p_a − p_b) · ln(p_a / p_b)`，并解释空桶为什么要做下限截断
- [ ] 解释为什么在采样后的数据上算"每用户成本"会严重偏差，并给出修正方法
- [ ] 指出本节代码的漂移检测为何不是真正的 embedding 漂移，并用置换/模拟方法估计 PSI 在"无漂移"时的噪声水平
- [ ] 识别可观测平面自身的 PII 风险（原始 prompt/response 落库）并提出脱敏方案
- [ ] 为告警器加上时间窗口和"首次告警时间"，从而能测 MTTR

---

## 二、基础自测（选择题）

**Q1.** 讲义 Key Terms 对 tail sampling 的定义是：

- A. 在请求进入时按固定比例决定是否记录 trace
- B. Collector 在 trace 完成之后再决定保留或丢弃，因此可以"看到"错误等信息
- C. 只保留每个 trace 的最后一个 span
- D. 只保留延迟最长的 10% 的 trace

**Q2.** 运行 `python main.py`，`ingested spans` 为 165。下列解释正确的是：

- A. 200 条 trace 中有 165 条被保留，每条 1 个 span
- B. 采样率 20%，200 × 20% × 4 ≈ 165
- C. 只有 LLM span 被存储
- D. 共保留 55 条 trace，每条包含 root、llm_call、eval 3 个 span，55 × 3 = 165

**Q3.** 本节代码的 PSI 实现如下，对于基线分布 `[0.25, 0.25, 0.25, 0.25]` 和当前分布 `[0.4, 0.3, 0.2, 0.1]`，PSI 约为多少？是否超过讲义的告警阈值？

```python
        score += (pa - pb) * math.log(pa / pb)
```

- A. ≈ 0.228，超过 0.2，会触发告警
- B. ≈ 0.083，低于 0.2
- C. ≈ 0.5，超过 0.2
- D. 0，因为两个分布的总和都为 1

**Q4.** 关于本节代码中 eval 与采样的先后顺序，说法正确的是：

- A. 先采样再 eval，与讲义的"eval 任务读取最近 15 分钟的采样 trace"完全一致
- B. eval 只在被采样的 trace 上运行，所以未被采样的 PII 泄漏会被漏掉
- C. 每条 trace 都先 `enrich_with_evals` 再 `sampler.decide`，因此高 PII 分数的 trace 一定被保留；这与讲义"对采样后的 trace 跑批量 eval"的架构不同
- D. 代码完全没有 eval

**Q5.** 讲义中注入回归探针的目标指标是：

- A. 准确率提升 5%
- B. 从 bug 部署到 Slack 告警的 MTTR 在 5 分钟以内
- C. PSI 低于 0.2
- D. 每秒摄入 1,000 个 span

**Q6.** 本节代码的 `SpanStore.cost_by_user` 只统计被采样保留的 trace。实测所有 200 条 trace 的真实总成本是 5.05 美元，而看板显示的总成本是：

- A. 约 1.29 美元，只有真实值的约 25%，而且用户之间的排序也变了
- B. 5.05 美元，与真实值一致
- C. 约 25.3 美元，因为代码按 1/采样率放大了
- D. 0，因为成本只在 eval span 上记录

**Q7.** 按 OpenTelemetry GenAI 语义约定，`gen_ai.system` 应该填写什么？本节代码填的是什么？

- A. 应填模型全名；代码填的是 `gpt-5-4`
- B. 应填用户 ID；代码填的是 `u_01`
- C. 应填应用名；代码填的是 `chatbot`
- D. 应填 GenAI 提供方/系统标识（如 openai、anthropic）；代码用 `model.split("-")[0]` 填成了 `claude`、`gpt`、`gemini` 这样的模型名前缀

**Q8.** 本节代码的 `prompt_fingerprint` 把 prompt 的 SHA-256 第一个字节对 8 取模作为"分桶"。用它算 PSI 的主要问题是：

- A. SHA-256 太慢
- B. 8 个桶太多
- C. 哈希桶只反映 prompt 的"字面身份"，语义相近的 prompt 会被随机分到不同桶、不同的 prompt 也可能撞到同一桶；它不是讲义所说的 embedding 分布漂移
- D. 哈希值可能为负数，导致索引越界

---

## 三、动手 / 代码题

**Q9.** 阅读 `TailSampler.decide`：

```python
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

1. 在 `main` 的 200 条 trace 中，第一条规则（错误 trace 必留）实际触发了几次？为什么？
2. 种子 5 下注入了 5 次 PII 泄漏（trace t0008、t0152、t0154、t0186、t0196），全部被保留。如果按讲义架构改成"先以 10% 采样、再对保留的 trace 跑 eval"，这 5 次泄漏中至少有一次被看到的概率是多少？
3. 讲义练习 5 要求"保留 100% toxicity > 0.5 的 trace + 其余 10% 分层采样"，并"测量引入的采样偏差"。请说明哪些指标会被这个策略扭曲，以及如何用"逆采样概率加权"修正。

**Q10.** 计算并解释"无漂移时 PSI 的噪声水平"。

`main` 中 prompt 从 4 个固定句子中均匀抽取，分布在整个运行中**没有任何变化**；基线是前 151 条、当前是后 49 条。4 个句子的指纹分别是 `[6, 7, 4, 4]`（两个句子撞进了同一个桶）。实测基线计数 `{4: 71, 6: 46, 7: 34}`、当前计数 `{4: 28, 7: 12, 6: 9}`，PSI = 0.083。

1. 用这两组计数手算 PSI（空桶用 0.0001 截断，空桶两边都为 0 时贡献为 0）。
2. 我们用同样的样本量模拟 5,000 次"无漂移"情形，PSI 均值约 0.056、95 分位约 0.170，约 2.7% 的情形超过 0.2。这说明什么？
3. 给出至少两种让漂移告警更可靠的做法。

**Q11.** 每用户成本的采样偏差。

实测（种子 5）真实成本与看板成本：

| 用户 | 真实成本（全部 200 条） | 看板成本（采样后） |
|---|---|---|
| u_01 | 1.2642 | 0.2116 |
| u_02 | 1.2389 | 0.3625 |
| u_03 | 1.4292 | 0.3835 |
| u_04 | 1.1189 | 0.3294 |

1. 看板上谁是"最省钱的用户"？真实情况呢？
2. 简单地把看板值除以 0.2 能修正吗？为什么不完全行？
3. 生产系统里成本归因应该放在流水线的哪一步？

**Q12.** 可观测平面自身的隐私风险。

1. `synth_trace` 把 `prompt`、`response` 原文写进 LLM span 的 attributes。注入回归后，`SpanStore` 里存了什么？
2. `alerter` 每次都扫描 `store.spans` 全量数据，没有时间窗口。这对讲义的 MTTR 目标有什么影响？
3. 改写 `insert_trace` 与 `alerter`：存储前对 response 做 PII 打码（只保留 eval 分数和哈希），告警器只看最近 5 分钟内的 eval span，并返回首个违规 span 的时间戳。

---

## 四、面试高频题

**Q13.**（基础必考）请设计一个自托管的 LLM 可观测平台：数据从应用到看板经过哪些组件？每个组件的选型理由是什么？

**Q14.**（原理深挖）head sampling 与 tail sampling 有什么区别？tail sampling 的代价是什么？采样会对哪些指标造成偏差，如何修正？

**Q15.**（工程实践）如何检测 LLM 应用的"漂移"？PSI 和 KL 散度有什么区别？阈值 0.2 从哪里来，怎么避免误报？

**Q16.**（场景设计）线上聊天机器人开始以 1% 的概率泄漏假 SSN。请设计一个能在 5 分钟内告警的检测链路，并说明每一环的延迟预算。

**Q17.**（追问型）用 LLM-judge 做在线 eval 有哪些坑？如何验证 judge 本身的可靠性？讲义练习 2 让你把 DeepEval 换成 Phoenix evaluator 并"测量两个评估引擎之间的分数漂移"，这说明了什么？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义 Key Terms："Tail sampling — Collector decides to keep or drop a trace after it completes (can peek errors)"。A 描述的是 head sampling（在 trace 开始时就决定）；C、D 不是标准做法。tail sampling 的价值在于可以"100% 保留错误 trace + 按比例保留成功 trace"（讲义 Build It 第 1 步）。

### Q2 — 答案：D

每条 trace 经 `enrich_with_evals` 后有 3 个 span：`chat_turn`（root）、`llm_call`、`eval`。实测保留了 55 条 trace，55 × 3 = 165；`spans by model` 的计数 24 + 14 + 17 = 55 也印证了这一点（只有 LLM span 计入 by_model）。55 条 = 5 条 PII 泄漏（必留）+ 195 条正常 trace 中被 20% 采样选中的 50 条。

### Q3 — 答案：A

逐项（已用 Python 计算）：
- `(0.25 − 0.4)·ln(0.25/0.4) = (−0.15)(−0.470) = 0.0705`
- `(0.25 − 0.3)·ln(0.25/0.3) = (−0.05)(−0.182) = 0.0091`
- `(0.25 − 0.2)·ln(0.25/0.2) = (0.05)(0.223) = 0.0112`
- `(0.25 − 0.1)·ln(0.25/0.1) = (0.15)(0.916) = 0.1374`

合计 ≈ 0.228 > 0.2，按讲义 Key Terms（"> 0.2 typically signals meaningful drift"）会告警。B 是本节代码运行的实际 PSI；D 错：PSI 的每一项 `(p_a − p_b)·ln(p_a/p_b)` 恒 ≥ 0，只有两个分布完全相同时才为 0。

### Q4 — 答案：C

`main` 中的顺序是 `synth_trace` → `enrich_with_evals` → `sampler.decide`。eval 在 100% 的 trace 上运行，采样器又会"看" eval 分数，所以高 PII 的 trace 一定被保留。讲义的架构则是"A scheduled job reads last-15-min sampled traces and runs DeepEval..."——eval 跑在采样之后。两种顺序的取舍：先 eval 能保证不漏关键事件，但 eval（尤其是 LLM-judge）要对全部流量付费；先采样则便宜，但低频事件可能被采样丢掉（见 Q9.2）。A、B 描述的是讲义的架构，不是代码；D 错。

### Q5 — 答案：B

讲义 Problem："given a deliberately injected regression (a prompt that starts producing PII), the dashboard catches it and fires an alert in under five minutes"；Build It 第 9 步："Measure MTTR: from bug deployed to Slack alert"；评分表"Dashboard UX — MTTR on injected regression (under 5 minutes target)"。D 是"Cost / scale"一项的指标；C 是漂移阈值。

### Q6 — 答案：A

实测：看板总成本 1.287 美元，真实总成本 5.051 美元，约 25%（20% 的随机采样 + 5 条必留的泄漏 trace）。排序也变了：看板上 u_01 最便宜（0.21），真实情况 u_01（1.26）是第二贵的，真正最便宜的是 u_04（1.12）。C 错：代码没有做任何加权；D 错：成本记在 `llm_call` span 的 `cost_usd` 属性上。

### Q7 — 答案：D

按 OTel GenAI 语义约定，`gen_ai.system` 标识的是 GenAI 提供方/系统（例如 openai、anthropic），模型名应放在 `gen_ai.request.model`（以及响应侧的 `gen_ai.response.model`）。代码用 `model.split("-")[0]`，得到 `claude`、`gpt`、`gemini`（实测第一条 LLM span 的值为 `gpt`），这是模型家族名而不是提供方。讲义评分表最高权重（25 分）就是"canonical GenAI spans"的覆盖度，属性取值不规范会让跨 SDK 的聚合出错。

### Q8 — 答案：C

哈希的雪崩效应使得"what is the weather in Tokyo today"和"what's the weather in Tokyo today"落到完全不相关的桶里；同时 4 个句子中有 2 个撞进了同一个桶 4。讲义要求的是"PSI / KL on pooled prompt embeddings (sentence-transformers)"：先用 embedding 模型把 prompt 映射到语义空间，再对 embedding 做聚类或投影后分桶，这样分布变化才对应"用户在问不同类型的问题"。A、B 不是主要问题；D 错：`digest()[0]` 是 0–255 的非负整数。

### Q9 — 参考答案

1. **0 次**。`synth_trace` 生成的 span 都使用默认 `status="ok"`，没有任何代码把 status 设为 `"error"`，所以"错误必留"规则在演示中从未生效。保留的 55 条 = 5 条因 `pii_leak = 0.95 > 0.8` 被保留 + 50 条随机 20% 采样。
2. 每条泄漏 trace 独立地以 10% 概率被保留，至少一条被看到的概率 = `1 − 0.9⁵ ≈ 0.41`（已计算）。也就是说约 59% 的情况下，这个 1% 的回归在采样后的数据里**完全不可见**，eval 任务根本没有机会发现它。这正是"先采样再 eval"的风险：低频高危事件需要在采样前用便宜的规则检查（如正则、小分类器）打标，让 tail sampler 能"看到"它们。
3. 被扭曲的指标：toxicity 平均值、高毒性比例（被严重高估，因为 100% 保留）、按模型/用户的请求数和成本、延迟分布（如果有毒回复的长度不同）。修正：每条保留的 trace 记录它的采样概率 `p`（高毒性为 1.0，其余为 0.1），统计时每条 trace 的权重为 `1/p`，即 Horvitz–Thompson 估计。例如"每用户成本 = Σ cost_i / p_i"。分层采样（按 app、模型分层）可以降低方差。

### Q10 — 参考答案

1. 基线 151 条：桶 4 = 71/151 = 0.4702，桶 6 = 46/151 = 0.3046，桶 7 = 34/151 = 0.2252；当前 49 条：桶 4 = 28/49 = 0.5714，桶 6 = 9/49 = 0.1837，桶 7 = 12/49 = 0.2449；其余 5 个桶两边都是 0，截断成 0.0001 后差为 0，贡献 0。
   - 桶 4：`(0.4702 − 0.5714)·ln(0.4702/0.5714) = (−0.1012)(−0.1949) ≈ 0.0197`
   - 桶 6：`(0.3046 − 0.1837)·ln(0.3046/0.1837) = (0.1209)(0.5059) ≈ 0.0612`
   - 桶 7：`(0.2252 − 0.2449)·ln(0.2252/0.2449) = (−0.0197)(−0.0840) ≈ 0.0017`
   - 合计 ≈ 0.083，与代码输出 0.083 一致。
2. 在**完全没有漂移**的情况下，样本量只有 151 vs 49 时，PSI 的抽样噪声就有均值 0.056、95 分位 0.17，并且约 2.7% 的情况会误报"漂移"（> 0.2）。0.083 完全落在噪声范围内。讲义 Use It 的"weekly PSI 0.08 (below 0.2 threshold)"也只能说明"没发现漂移"，不能说明"确认无漂移"。PSI 阈值 0.2 是在大样本的信用评分场景中形成的经验值，小样本下必须考虑抽样误差。
3. 做法：
   - 增大窗口样本量（讲义用"本周 vs 过去 4 周"）；
   - 用置换检验或 bootstrap 给 PSI 一个 p 值或置信区间，只有显著时告警；
   - 连续多个窗口超阈值才告警（去抖）；
   - 用 embedding 聚类分桶，桶数与样本量匹配，避免大量空桶；
   - 按 app_id 分开计算（讲义练习 3），避免一个 app 的变化被全局稀释。

### Q11 — 参考答案

1. 看板上 u_01 最"省钱"（0.21），真实最省钱的是 u_04（1.12），u_01（1.26）实际排第二。采样让看板的排序变成了随机噪声，"每用户成本"这个讲义所说的"关键产品指标"直接失真。
2. 除以 0.2（乘 5）能得到大致正确的量级（1.287 × 5 ≈ 6.4），但不完全正确：泄漏 trace 是 100% 保留的，乘 5 会把它们的成本放大 5 倍；而且只有 20% 的样本，每个用户的估计方差很大。正确做法是对每条 trace 按其自身的采样概率加权（`1/p`），见 Q9.3。
3. 成本、token 数、请求数这类**计数型指标**应在采样**之前**计算——例如在应用侧或 Collector 的处理器里直接导出 Prometheus 指标（按 user、model 聚合），这样不受采样影响；tail sampling 只决定"哪些 trace 的明细要保留下来供排查"。

### Q12 — 参考答案

1. 每条泄漏 trace 的 `llm_call` span 都在 attributes 里以明文存着 `"your ssn is 123-45-6789"`（实测 5 条全部在库）。可观测平面本身成了 PII 的二次泄漏点：看板用户、日志备份（讲义还有 S3 原始事件归档）都能看到。
2. 告警器看的是累计全量，没有时间维度：(a) 无法计算"从部署到告警"的时间；(b) 一旦出现过一次泄漏，此后每次检查都会再次告警，无法判断"是否已恢复"；(c) 随着数据量增长，全表扫描越来越慢。
3. 示意实现：

```python
import hashlib, re, time

SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

def redact(text: str) -> str:
    return SSN.sub("[ssn]", text)

def insert_trace(self, trace):
    for s in trace:
        for key in ("prompt", "response"):
            if key in s.attributes:
                raw = s.attributes[key]
                s.attributes[f"{key}_sha256"] = hashlib.sha256(raw.encode()).hexdigest()[:16]
                s.attributes[key] = redact(raw)
    self.spans.extend(trace)
    ...

def alerter(store, now_ms=None, window_ms=5 * 60 * 1000):
    now_ms = now_ms or int(time.time() * 1000)
    recent = [s for s in store.spans
              if s.name == "eval" and now_ms - s.start_ms <= window_ms]
    pii = sorted((s for s in recent if s.attributes.get("pii_leak", 0) > 0.8),
                 key=lambda s: s.start_ms)
    if pii:
        return [{"alert": "PII_LEAK", "count": len(pii), "first_ts": pii[0].start_ms}]
    return []
```

   注意：eval 要在打码**之前**运行（否则 PII judge 看不到 SSN），所以顺序是"eval → 打码 → 落库"。MTTR = 告警发出时间 − 回归部署时间；在本模拟中可以把 `start_ms` 改成按 trace 序号递增的模拟时间来测量。

### Q13 — 参考回答要点

- **埋点**：各应用使用 OpenTelemetry SDK + GenAI 语义约定（或 OpenLLMetry 自动埋点），覆盖 OpenAI、Anthropic、Google GenAI、LangChain、LlamaIndex、vLLM。
- **传输**：OTLP HTTP 发到 OpenTelemetry Collector；Collector 做 tail sampling（错误 100%、成功 10%）并扇出。
- **存储**：ClickHouse 存 span（列式，适合按模型、用户、时间做大规模聚合；按 GenAI 属性建列，user_id、app_id 建二级索引）；Postgres 存用户、会话、应用等元数据；S3 存原始事件归档。
- **评估**：定时任务读最近 15 分钟的采样 trace，跑 DeepEval（faithfulness、toxicity、answer relevance）、RAGAS（有检索上下文时）、自定义 LLM-judge（PII 泄漏），结果作为 eval 子 span 写回。
- **漂移**：每周对 prompt embedding 计算 PSI，与过去 4 周基线比较。
- **告警**：Prometheus 导出 eval 分数聚合和延迟分位数，Alertmanager 按严重程度路由到 Slack 或 PagerDuty。
- **UI**：Next.js 15 + Recharts：概览、trace 瀑布图、eval 趋势、漂移、告警。
- 加分点：说明成本类指标在采样前计算；可观测数据本身需要 PII 脱敏和访问控制。

### Q14 — 参考回答要点

- **head sampling**：trace 开始时就按比例决定，实现简单、开销低，但无法根据结果（是否报错、延迟多长、eval 分数）做决定，错误 trace 也会被按比例丢掉。
- **tail sampling**：等 trace 结束再决定，可以"100% 保留错误 / 慢请求 / 高风险"的 trace。代价：Collector 需要在内存中缓冲完整 trace（等所有 span 到齐，有决策等待时间），同一 trace 的 span 必须路由到同一个 Collector 实例（需要按 trace_id 做负载均衡），资源消耗更高。
- **偏差**：任何"按结果有选择地保留"都会让采样后数据的统计量偏离总体——错误率、毒性比例被高估，成本、请求数被低估（本节代码的每用户成本只剩 25%）。
- **修正**：计数类指标在采样前导出；对保留的 trace 记录采样概率并用 `1/p` 加权；分层采样降低方差；讲义练习 5 要求明确测量采样引入的偏差。

### Q15 — 参考回答要点

- **监测对象**：输入侧（prompt embedding 分布、长度、语言、主题聚类）；输出侧（eval 分数趋势：faithfulness、toxicity、拒答率）；检索侧（nDCG、引用忠实度）。
- **PSI**：`Σ (p_a − p_b) ln(p_a/p_b)`，等价于对称化的 KL 散度 `KL(a‖b) + KL(b‖a)`，对两个方向都敏感；KL 是非对称的，且某一侧为 0 时会发散，需要平滑（本节代码用 0.0001 截断）。
- **阈值**：0.1 / 0.25（或讲义的 0.2）是信用评分等领域的经验值，不是统计检验；在小样本或桶数多时，噪声本身就可能接近阈值（见 Q10）。
- **避免误报**：足够大的窗口、bootstrap/置换检验、连续窗口确认、按 app/用户群分开计算、对季节性（工作日 vs 周末）建立同期基线。
- 加分点：漂移本身不等于质量下降，要与 eval 分数联动看；漂移告警应附带"哪些聚类变多/变少了"的解释。

### Q16 — 参考回答要点

- **检测链路**：
  1. 应用 → Collector：OTLP 批量导出间隔（秒级）；
  2. 在采样**之前**用便宜的规则（SSN 正则、小型 PII 分类器）给 span 打 `pii_suspect` 标记，并直接导出一个 Prometheus 计数器——不依赖采样和批量 eval；
  3. tail sampler 对带标记的 trace 100% 保留，供排查；
  4. LLM-judge 对可疑 trace 做二次确认（降低误报），可以异步进行；
  5. Prometheus 抓取间隔（如 15–30 秒）+ 告警规则 `for: 1m` 去抖 → Alertmanager → PagerDuty/Slack。
- **延迟预算**：导出 10 秒 + 抓取 30 秒 + 规则持续 60 秒 + 路由 10 秒，总计约 2 分钟，留有余量满足 5 分钟目标。讲义 Build It 第 4 步的"每 15 分钟读一次采样 trace"的批量 eval 节奏**无法**满足 5 分钟目标，必须有流式的快速路径。
- **1% 的低频事件**：流量足够大时 5 分钟内会出现多次；流量小时要用"任何一次出现即告警"的规则，而不是比例阈值。
- **验证**：讲义 Build It 第 9 步的回归探针——真的部署一个 1% 泄漏的版本，测量 MTTR，作为发布门禁的一部分定期演练。
- 加分点：告警附带首个违规 trace 的链接，并在落库前打码，避免可观测系统成为新的泄漏面。

### Q17 — 参考回答要点

- **LLM-judge 的坑**：自身会出错（误报、漏报）；对措辞、长度、位置有偏好；与被评估模型同家族时可能"自我偏袒"；judge 模型或 prompt 版本一变，分数就漂移；在线跑全量很贵。
- **验证可靠性**：用人工标注集校准（讲义评分表"Eval correctness — DeepEval / RAGAS scores vs hand-labeled set"）；计算与人工标签的一致性（精确率、召回率、Cohen's kappa）；固定 judge 模型版本和 prompt，版本变更要重新校准；定期抽样人工复核。
- **练习 2 的启示**：同一批 trace 用不同评估引擎打分，分数会有系统性差异——"faithfulness 0.82"只有在指定引擎、版本、prompt 的前提下才有意义。看板上的趋势比绝对值更可靠，更换评估引擎时要做并行运行和基线重置，否则会把"换尺子"误判为"质量变化"。
- 加分点：本节代码的 eval 是启发式桩（faithfulness = 词重叠、toxicity = 关键词、PII = 正则），可以作为"快速路径"，再用 LLM-judge 做"慢速确认"，组合成两级评估。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 20 OpenTelemetry GenAI：端到端追踪 Tool Calls](../../../13-tools-and-protocols/20-opentelemetry-genai/docs/zh.md)：GenAI span 与属性。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../../14-agent-engineering/23-otel-genai-conventions/docs/zh.md)：`gen_ai.*` 属性的规范含义。
- [阶段 14 · 24 Agent 可观测性：Langfuse、Phoenix、Opik](../../../14-agent-engineering/24-agent-observability-platforms/docs/zh.md)：现成可观测平台的对比。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：生产可观测栈的选型。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：faithfulness 等评估指标。

### 本节被哪些后续内容用到
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：看板上的延迟与吞吐指标。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../../17-infrastructure-and-production/27-finops-llms/docs/zh.md)：每用户成本归因。
- [阶段 17 · 23 AI 的 SRE](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：告警、MTTR 与事故响应。
- [阶段 19 · 28 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../28-observability-otel-traces/docs/zh.md)：在 harness 中落地 span 与指标。
- [阶段 19 · 08 面向受监管行业的生产级 RAG 聊天机器人](../../08-production-rag-chatbot/docs/zh.md)：漂移看板与 PII 护栏的使用方。

### 延伸关键词
`OpenTelemetry GenAI semconv` · `OTLP` · `OpenTelemetry Collector` · `tail sampling` · `Horvitz–Thompson 加权` · `ClickHouse` · `eval span` · `LLM-as-judge` · `PSI` · `KL divergence` · `bootstrap 置换检验` · `Alertmanager` · `MTTR` · `PII redaction` · `cost attribution`
