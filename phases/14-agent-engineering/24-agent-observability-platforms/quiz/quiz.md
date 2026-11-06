# 测验 · Agent 可观测性（Observability）：Langfuse、Phoenix、Opik（Agent Observability: Langfuse, Phoenix, Opik）

> **阶段 14 · Agent 工程 · 第 24 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 平台在 OTel 之上补什么 | OTel GenAI（第 23 节）只给 schema；平台负责接收 span、跑评估、存 prompt 版本、暴露回归 |
| 2 | Langfuse（MIT） | 讲义：每月 6M+ SDK 安装、19k+ GitHub stars；tracing + 带版本和 playground 的 prompt 管理 + 评估（LLM-as-judge、用户反馈、自定义）+ session replay；2025 年 6 月把原商业模块以 MIT 开源 |
| 3 | Arize Phoenix（Elastic License 2.0） | 更深的 agent 评估：trace 聚类、异常检测、RAG 检索相关性；原生 OpenInference 自动埋点；**没有 prompt 版本管理**，定位为漂移/行为回归工具 |
| 4 | Comet Opik（Apache 2.0） | 通过 A/B 实验自动优化 prompt；guardrails（PII 脱敏、话题约束）；LLM-judge 幻觉检测 |
| 5 | 厂商 benchmark 只能参考方向 | 讲义：Comet 自测 Opik 记录 + 评估 23.44 s，Langfuse 327.15 s（约 14 倍）——"take vendor benchmarks as directional" |
| 6 | 行业数据 | 讲义引 Maxim 2026：89% 的组织已有 agent 可观测性；质量问题是生产首要障碍（32% 受访者） |
| 7 | 选型表 | 一站式 + prompt 管理 → Langfuse；RAG 评估 + 漂移 → Phoenix；自动优化 + guardrails → Opik；要避开 ELv2 → Langfuse 或 Opik；接 Datadog/New Relic → 都可以（都导出 OTel） |
| 8 | 三个失败模式 | 只有 tracing 没有评估（"expensive logging"）；自造的 LLM-judge 没有外部事实依据（CRITIC，第 05 节）；prompt 版本没有和 trace 关联，回归时无法二分定位 |
| 9 | LLM-as-judge | 另一个 LLM 按 rubric（评分细则）给 agent 输出打分；rubric 需要产品决策，判断事实需要外部工具 |
| 10 | 看板的基本要素 | 按 session 分组、失败率、失败原因分布、评估分数分布、延迟与成本 |

### 核心技能（能动手做到）

- [ ] 说出三个平台的许可证、最强项和不适合的场景，并按需求选型
- [ ] 手算本节 `scripted_llm_judge` 对任意 session 的分数与判决
- [ ] 指出本节"LLM-judge"其实只是元数据启发式规则，说出它会漏掉什么
- [ ] 重构演示代码，避免对同一 session 重复评估（真实 LLM-judge 每次都要花钱且结果不确定）
- [ ] 从 span 中算出失败率、分数分布、Top 失败原因、按 provider 的平均分
- [ ] 把 prompt 版本写进 trace，按版本对比分数，定位回归

---

## 二、基础自测（选择题）

**Q1.** 三个平台的许可证分别是：

- A. Langfuse Apache 2.0、Phoenix MIT、Opik ELv2
- B. 三者都是 MIT
- C. Langfuse ELv2、Phoenix Apache 2.0、Opik MIT
- D. Langfuse MIT、Phoenix Elastic License 2.0、Opik Apache 2.0

**Q2.** 讲义说某个平台"No prompt versioning — positioned as a drift/behavioral-regression tool alongside broader platforms"。它是：

- A. Arize Phoenix
- B. Langfuse
- C. Comet Opik
- D. Datadog LLM Observability

**Q3.** Comet 自测 Opik 记录 + 评估耗时 23.44 s，Langfuse 327.15 s。按讲义的态度，你应该：

- A. 直接采信，选 Opik，因为快了约 14 倍
- B. 认为数据造假，完全忽略
- C. 只把它当方向性参考，在自己的语料和负载上实测再决定
- D. 换算成每条 trace 的耗时写进采购合同

**Q4.** 讲义所说"Tracing without evaluation is just expensive logging"对应的是哪种失败模式？

- A. prompt 版本没有和 trace 关联
- B. 没有评估策略
- C. LLM-judge 没有外部依据
- D. 采样率过低

**Q5.** 按 `scripted_llm_judge` 的规则，session `s003`（`invoke_agent` + 一个 `chat`，该 chat 有 `gen_ai.output.reference_id`、`tokens=2500`，没有 tool_call，没有错误）的分数和判决是：

- A. 1.00，PASS
- B. 0.80，PASS
- C. 0.70，WARN
- D. 0.40，FAIL

**Q6.** 运行一次 `main.py`，`scripted_llm_judge` 一共被调用了几次（共 3 个 session）？

- A. 3 次
- B. 4 次
- C. 6 次
- D. 9 次

**Q7.** 线上质量在某天突然下降，但你无法确定是哪一次 prompt 修改导致的。按讲义，最可能缺了什么？

- A. prompt 版本没有和 trace 关联，无法按版本二分定位
- B. 没有开启 session replay 的动画效果
- C. 许可证不是 MIT
- D. trace 的采样率太高

**Q8.** 讲义引用的 Maxim 2026 行业数据是：

- A. 32% 的组织有 agent 可观测性；首要障碍是成本（89%）
- B. 89% 的组织没有可观测性
- C. 89% 的组织已有 agent 可观测性；质量问题是生产首要障碍（32% 受访者）
- D. 只有 6% 的组织使用开源平台

---

## 三、动手 / 代码题

**Q9.** `scripted_llm_judge` 的打分规则：

```python
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
    if score >= 0.8:   verdict = "PASS"
    elif score >= 0.5: verdict = "WARN"
    else:              verdict = "FAIL"
```

1. 手算 `s002`（`invoke_agent` + 一个 `status="error"` 的 `chat`，`error.reason="rate_limited"`，`tokens=0`）的分数。Python 里 `score` 的精确值是多少？
2. 构造一个 session：有工具调用、有带 `gen_ai.output.reference_id` 的 chat、tokens 300、无错误，但最终答案是**编造的**。它得几分？说明这个"judge"缺了什么。
3. 一个 session 里有 5 个错误 span 与只有 1 个错误 span，分数有差别吗？`max(0.0, score)` 这一行会生效吗？

**Q10.** `main` 中的打印逻辑：

```python
    for summary in summarize(collector):
        score, verdict = scripted_llm_judge(collector.by_session()[summary.session_id])
        ...
    total_errors = sum(s.error_count for s in summarize(collector))
```

1. 为什么 judge 被调用了 9 次？`by_session()` 被重算了几次？
2. 如果 judge 是真正的 LLM 调用，这会造成哪两类问题？
3. 改写 `SessionSummary` 和 `main`，让每个 session 只评估一次。另外，`trace_count` 与 `eval_score_mean` 这两个字段名有什么问题？

**Q11.** 讲义说本节代码会给出"failure rate, top failure reasons, eval score distribution"的看板摘要，但实际只打印了 `aggregate: 1 errors across 3 sessions`。请写一个 `dashboard(collector)`，输出：失败率、判决分布、分数分桶、Top 失败原因、按 `gen_ai.provider.name` 的平均分。注意分桶时的浮点问题。

**Q12.**（prompt 版本与回归定位）在 `invoke_agent` span 上增加属性 `prompt.version`。构造 40 个 session：前 20 个用 `v1`，全部正常；后 20 个用 `v2`，其中下标能被 3 整除的 session 的 `chat` span 出错（`error.reason="schema_mismatch"`）。按版本统计平均分和非 PASS 数，并说明这为什么就是讲义说的"bisect to the prompt"。

---

## 四、面试高频题

**Q13.**（基础必考）Langfuse、Phoenix、Opik 各自最强的是什么？如果只能选一个，你如何决策？

**Q14.**（原理深挖）LLM-as-judge 有哪些常见问题？如何让一个 judge 值得信任？

**Q15.**（工程实践）日均百万次 agent 调用，老板说"全量采集，一条都别丢"。你怎么回应？采样策略如何设计？

**Q16.**（场景设计）一家医疗公司做 RAG 问答 agent：数据含 PII、法务要求 OSS 许可证不能是 ELv2、团队已经在用 Datadog。给出可观测性方案。

**Q17.**（追问型）周一发版后，用户投诉"答非所问"变多了。你如何用可观测平台在一小时内找到原因？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义标题即标注：Langfuse (MIT)、Arize Phoenix (Elastic License 2.0)、Comet Opik (Apache 2.0)。A、C 把许可证张冠李戴；B 错。许可证影响很大：ELv2 限制把软件作为托管服务提供给第三方，所以选型表里"Open licensing, no ELv2"只推荐 Langfuse 或 Opik。

### Q2 — 答案：A

讲义 Phoenix 部分原话。Phoenix 的强项是 trace 聚类、异常检测、RAG 检索相关性和 OpenInference 自动埋点；它与更全面的平台搭配使用。B 的 Langfuse 恰恰以"prompt management with versioning + playground"为卖点；C 的 Opik 强在自动优化与 guardrails；D 不是讲义讨论的三家开源平台之一。

### Q3 — 答案：C

已计算：`327.15 / 23.44 ≈ 13.96`，即讲义说的"~14x gap"。但这是厂商自测（"from Comet's own measurement"），讲义明确说"take vendor benchmarks as directional"，练习 5 也要求"Ignore vendor-published numbers; measure your own"。A 盲信厂商数据；B 走向另一个极端；D 把方向性数字当成合同指标。

### Q4 — 答案：B

讲义："No eval strategy. Tracing without evaluation is just expensive logging." 只采集不评估，你只知道"发生了什么"，不知道"做得好不好"。A 是第三种失败模式；C 是第二种；D 不是讲义列出的失败模式（skill 文件反而要求在规模化时必须采样）。

### Q5 — 答案：B

`errors = 0`（不扣）；`has_final` 为真（不扣）；`has_tool` 为假，扣 0.1；`tokens_over`（2500 > 2000）为真，扣 0.1。`1.0 − 0.1 − 0.1 = 0.8`，满足 `>= 0.8`，判 PASS（实际输出 `s003 verdict=PASS score=0.80`）。注意这个 session 在代码里叫 `slow_spans`，但"慢"并没有被度量（span 没有时间信息），只用 token 数做了代理；它刚好卡在 PASS 门槛上。A 忘了扣分；C、D 计算错误。

### Q6 — 答案：D

`summarize(collector)` 内部对每个 session 调一次 judge（3 次）；`for` 循环里又对每个 session 再调一次（3 次）；最后 `total_errors = sum(... summarize(collector))` 又整体重算一遍（3 次），合计 **9 次**（已用计数包装器实测）。只需要 3 次。详见 Q10。

### Q7 — 答案：A

讲义："Prompt versions not tied to traces. When prod regresses, you cannot bisect to the prompt that caused it." 把 prompt 版本作为 trace 属性记录后，就可以按版本对比分数（见 Q12）。B 与定位无关；C 是许可证问题；D 采样率高只会让数据更多。

### Q8 — 答案：C

讲义："Per Maxim (2026 field analysis): 89% of organizations have agent observability in place; quality issues are the top production barrier (32% of respondents cite them)." A 把两个数字对调并改了障碍类型；B 说反；D 是编造的。

### Q9 — 参考答案

1. `s002`：有错误扣 0.4；唯一的 chat 出错、没有 `gen_ai.output.reference_id`，扣 0.3；没有 tool_call 扣 0.1；tokens 为 0 不扣。`1.0 − 0.4 − 0.3 − 0.1`，Python 中实际值为 **`0.19999999999999998`**（浮点累积误差），打印时 `:.2f` 显示为 `0.20`，判 FAIL。这个误差在门槛附近可能改变判决，生产中应使用整数分值或 `round()` 后再比较。
2. 实测该 session 得 **1.0，PASS**。因为这个"judge"**从不看内容**：它只检查"有没有出错的 span、有没有输出引用、有没有工具调用、token 多不多"。编造的答案、答非所问、语气不当、越权回答都无法发现。真正的 LLM-as-judge 需要：读取输出正文（从外部存储按 reference_id 取回）、有领域 rubric（讲义练习 2：factual correctness、tone、scope adherence）、对事实类判断调用外部工具核实（讲义："judges need external tools for factual verification"，即 CRITIC 模式）。
3. 没有差别：`if errors:` 只判断"有没有"，5 个错误与 1 个错误都只扣 0.4（实测 5 个错误 + 有工具 + 有输出 = 0.6，WARN）。`max(0.0, score)` 永远不会生效：所有扣分加起来是 `0.4 + 0.3 + 0.1 + 0.1 = 0.9`，最低分约 0.1。两者都说明规则是拍脑袋定的，没有经过校准。

### Q10 — 参考答案

1. 见 Q6：`summarize` 被调用 2 次（各 3 次 judge），循环中再调 3 次，共 9 次。`by_session()` 被调用了 **6 次**：两次 `summarize` 各 1 次，循环中每个 session 1 次（3 次），`total_sessions` 1 次。
2. 若 judge 是真实 LLM 调用：
   - **成本**：评估费用变成 3 倍（每次调用都要付 token 费）；
   - **一致性**：LLM 输出不确定，同一个 session 第一次评 PASS、第二次评 WARN，看板上的排序（来自第一次）和打印的判决（来自第二次）可能互相矛盾。
3. 改写思路：把判决存进摘要，只评一次。

```python
@dataclass
class SessionSummary:
    session_id: str
    span_count: int            # 原名 trace_count，实际数的是 span
    error_count: int
    eval_score: float          # 原名 eval_score_mean，实际只是单次分数
    verdict: str
    failure_reasons: Counter

def summarize(collector):
    out = []
    for sid, spans in collector.by_session().items():
        score, verdict = scripted_llm_judge(spans)     # 每个 session 只调一次
        out.append(SessionSummary(sid, len(spans),
                                  sum(s.status == "error" for s in spans),
                                  score, verdict, categorize_failures(spans)))
    out.sort(key=lambda s: s.eval_score)
    return out

summaries = summarize(collector)                      # 只算一次，后面复用
for s in summaries:
    print(f"  {s.session_id}  verdict={s.verdict}  score={s.eval_score:.2f} ...")
total_errors = sum(s.error_count for s in summaries)
```

字段名问题：`trace_count` 实际是 **span 数**（`s001` 只有 1 条 trace `t001`，却显示 `spans=4`）；`eval_score_mean` 不是任何意义上的"均值"，只是单次评分。命名不准会让看板读者误解指标。

### Q11 — 参考答案

```python
from collections import Counter, defaultdict

def dashboard(collector):
    sessions = collector.by_session()
    verdicts, scores, reasons = Counter(), [], Counter()
    by_provider = defaultdict(list)
    for sid, spans in sessions.items():
        score, verdict = scripted_llm_judge(spans)          # 每个 session 只评一次
        verdicts[verdict] += 1
        scores.append(score)
        reasons.update(categorize_failures(spans))          # Counter 相加
        provider = next((s.attributes["gen_ai.provider.name"] for s in spans
                         if "gen_ai.provider.name" in s.attributes), "unknown")
        by_provider[provider].append(score)
    n = len(sessions)
    print(f"sessions={n}  failure_rate={verdicts['FAIL'] / n:.1%}")
    print("verdicts:", dict(verdicts))
    print("score buckets:", Counter(f"{round(s, 1):.1f}" for s in scores))
    print("top failure reasons:", reasons.most_common(3))
    print("mean score by provider:",
          {p: round(sum(v) / len(v), 2) for p, v in by_provider.items()})
```

对本节数据的实际输出：

```text
sessions=3  failure_rate=33.3%
verdicts: {'PASS': 2, 'FAIL': 1}
score buckets: Counter({'1.0': 1, '0.2': 1, '0.8': 1})
top failure reasons: [('rate_limited', 1)]
mean score by provider: {'anthropic': 0.6, 'openai': 0.8}
```

浮点陷阱：如果用 `int(s * 10) / 10` 分桶，`s002` 的 `0.19999999999999998 × 10 = 1.9999999999999998`，`int` 后变成 1，会被错分到 `0.1` 桶（实测踩过这个坑）。应先 `round`。另外注意 provider 归属依赖 `invoke_agent` span 上的 `gen_ai.provider.name`——这正是第 23 节强调"缺 provider 属性多 provider 看板会坏"的原因；本节数据里 chat span 没有 provider，只能从同 session 的其他 span 推断。

### Q12 — 参考答案

```python
by_ver = defaultdict(list)
for sid, spans in c.by_session().items():
    ver = spans[0].attributes.get("prompt.version", "unknown")   # invoke_agent 是第一个 span
    by_ver[ver].append(scripted_llm_judge(spans)[0])
for v, sc in sorted(by_ver.items()):
    print(v, "n=", len(sc), "mean=", round(sum(sc) / len(sc), 3),
          "non_pass=", sum(1 for s in sc if s < 0.8))
```

实际输出：

```text
v1 n= 20 mean= 1.0 non_pass= 0
v2 n= 20 mean= 0.86 non_pass= 7
```

（v2 中下标 21、24、27、30、33、36、39 共 7 个 session 出错，每个扣 0.4 得 0.6，判 WARN；平均 `(13 × 1.0 + 7 × 0.6) / 20 = 0.86`。注意若只统计 `< 0.5` 的 FAIL，会得到 0 个——判决门槛的选择会直接决定回归能否被看见。）

为什么这就是"bisect"：当 prompt 版本作为 trace 属性存在时，质量指标可以直接按版本切片；版本多时可按发布时间顺序二分比较，快速锁定第一个变差的版本。若没有这个属性，只能看到"某天以后分数下降"，而那天可能同时发生了模型升级、工具变更、流量变化，无法归因。Langfuse 的 prompt 管理把这件事产品化了（讲义："Versioned prompts tied to traces"）。

### Q13 — 参考回答要点

- **Langfuse（MIT）**：一站式——tracing、带版本与 playground 的 prompt 管理、评估（LLM-judge、用户反馈、自定义）、session replay；讲义："end-to-end observability with tight prompt-management loop"。
- **Phoenix（ELv2）**：RAG 检索相关性、trace 聚类、异常/漂移检测、OpenInference 自动埋点；没有 prompt 版本；常与 Arize AX 或其他平台搭配。
- **Opik（Apache 2.0）**：自动 prompt 优化（A/B 实验）、guardrails（PII 脱敏、话题约束）、LLM-judge 幻觉检测。
- **决策方法**：
  1. 先看硬约束：许可证（是否接受 ELv2）、是否必须自托管、是否已有 Datadog 等；
  2. 再看主要痛点：prompt 迭代频繁 → Langfuse；RAG 质量与漂移 → Phoenix；需要自动优化与内容护栏 → Opik；
  3. 用 OTel GenAI 作为统一埋点层，保留切换平台的自由（"they all export OTel"）；
  4. 在自己的数据上做 POC 实测，而不是看厂商 benchmark。
- skill 文件："If the user asks for 'one platform for everything,' refuse... No single platform dominates all three axes."

### Q14 — 参考回答要点

- **常见问题**：
  - 没有 rubric 或 rubric 模糊，分数含义不稳定；
  - 事实性判断靠 judge 自己的知识，会把看起来合理的幻觉判为正确（讲义："Self-rolled LLM-judge without grounding"）；
  - 偏差：偏好更长的回答、偏好与自己同源模型的输出、受选项顺序影响；
  - 不确定性：同一输入多次评分结果不同；
  - 成本：每条 trace 都调一次大模型，费用可观。
- **让 judge 可信**：
  1. 由产品定义验收标准，写成分项 rubric（正确性、范围遵守、语气、拒答质量），每项给出例子；
  2. 用一批人工标注样本校准 judge，度量与人工的一致率，定期复核；
  3. 事实类判断给 judge 工具（检索、执行代码、查数据库），即 CRITIC 模式（第 05 节）；
  4. 固定 judge 的模型版本与 prompt 版本，并把它们也记入 trace；
  5. 低温度/多次投票降低方差；对高风险样本抽检人工复核。
- 常见误区：把元数据启发式规则（如本节 `scripted_llm_judge`）当成质量评估。

### Q15 — 参考回答要点

- **回应**：skill 文件明确拒绝"no sampling, capture everything"——trace 量与流量线性增长，存储、带宽、平台费用和查询性能都会失控；而且全量捕获内容还放大了隐私风险。
- **采样策略**：
  - **head-based**（请求开始时决定）：实现简单、开销低，但可能丢掉恰好出错的请求；
  - **tail-based**（在 collector 等 trace 完成后决定）：保留所有错误、高延迟、低评估分、guardrail 触发的 trace，正常 trace 按比例保留；
  - 按 session 采样，保证同一会话的 trace 要么全留、要么全丢；
  - 新版本发布初期、重点客户提高采样率。
- **指标与 trace 分离**：计数、延迟分布、token 成本等用 metrics 全量统计（便宜），trace 用于排查细节。
- **评估也要采样**：LLM-judge 对抽样 trace 运行，对所有失败 trace 运行。
- 加分点：说明采样决策要随 trace context 传播（第 23 节 `traceparent` 的 flags）。

### Q16 — 参考回答要点

- **许可证**：排除 Phoenix（ELv2），在 Langfuse（MIT）与 Opik（Apache 2.0）中选；已有 Datadog 可同时用 Datadog LLM Observability（讲义：v1.37+ 原生映射 GenAI 属性）做运维看板。
- **推荐组合**：OTel GenAI 统一埋点 → collector 分流：
  - 运维指标（延迟、错误率、成本）→ Datadog；
  - 质量与 prompt 迭代 → 自托管 Langfuse（prompt 版本 + LLM-judge + session replay），或 Opik（若更需要 PII guardrail 与自动优化）。
- **PII**：内容默认不内联进 span，外部存储 + 引用 ID（skill："Storing PII in span bodies"是硬性拒绝）；在 collector 或平台侧做 PII 脱敏/密钥擦除；自托管、数据不出域；访问控制与审计。
- **RAG 质量**：记录 `gen_ai.data_source.id`；评估检索相关性与回答忠实度；Phoenix 虽不能用，可以用 Langfuse/Opik 的自定义评估实现 RAG 相关性打分。
- **评估**：医学事实类判断必须有依据（检索权威资料），并做人工抽检。

### Q17 — 参考回答要点

1. **确认现象**：在看板上按时间看 LLM-judge 分数（如 relevance、scope adherence）和用户反馈，确认下降的起点与发版时间吻合。
2. **按维度切片**：按 prompt 版本、模型（`gen_ai.response.model`）、agent 名、工具、数据源、客户端版本切分质量指标，找出下降集中在哪个切片（Q12 的方法）。
3. **看差异**：对比新旧版本的 prompt diff、模型路由变化、检索配置变化；Phoenix 式的 trace 聚类可以发现"新出现的一类行为"。
4. **抽样复盘**：用 session replay 打开若干低分 trace，看检索结果是否相关、工具是否被调用、模型是否忽略了指令。
5. **验证与回滚**：在离线评估集上复现，确认根因后回滚或修复，并把这些失败样本加入回归测试集（第 30 节评估驱动开发）。
- 前提条件：prompt 版本已关联到 trace、有持续运行的评估、关键属性齐全。缺任何一项，一小时内基本无法定位。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：三个平台共同消费的 span schema。
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../05-self-refine-and-critic/docs/zh.md)：LLM-judge 需要外部工具做事实核验。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：评估方法基础。
- [阶段 11 · 12 Guardrails，安全及内容过滤](../../../11-llm-engineering/12-guardrails/docs/zh.md)：Opik 的 guardrails 所对应的概念。

### 本节被哪些后续内容用到
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../26-failure-modes-agentic/docs/zh.md)：建立失败原因分类体系。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：把线上失败变成评估集。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：生产可观测栈的整体选型。
- [阶段 19 · 11 综合项目 11：LLM Observability 与评估仪表盘](../../../19-capstone-projects/11-llm-observability-dashboard/docs/zh.md)：动手搭建完整看板。

### 延伸关键词
`Langfuse` · `Arize Phoenix` · `OpenInference` · `Comet Opik` · `LLM-as-judge` · `rubric` · `prompt versioning` · `session replay` · `trace clustering` · `drift detection` · `tail-based sampling` · `Elastic License 2.0`
