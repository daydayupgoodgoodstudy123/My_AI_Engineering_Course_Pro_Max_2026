# 测验 · LLM Observability 技术栈选型（LLM Observability Stack Selection）

> **阶段 17 · 基础设施与生产 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 市场两大类 | 开发平台（LangSmith、Langfuse、Comet Opik）把监控与 eval、prompt 管理、会话回放打包；网关 / 遥测工具（Helicone、SigNoz、OpenLLMetry、Phoenix）只专注 trace 与指标 |
| 2 | 选型四个维度 | 技术栈（LangChain？原生 SDK？多厂商？）、许可证容忍度（只要 MIT？Elastic 可以？商业也行？）、预算、是否必须自托管 |
| 3 | Langfuse | 核心开源（讲义称 MIT）、可 Docker 自托管；云端免费 50K events/月，团队版 $29/月；"开源版 LangSmith" |
| 4 | Phoenix 与 Arize AX | Phoenix：OpenTelemetry 原生、Elastic License 2.0，擅长 RAG 与漂移可视化，但不是持久化的生产后端；Arize AX：商业版，Iceberg/Parquet 零拷贝，声称在规模化时比 Datadog 类方案便宜约 100 倍 |
| 5 | LangSmith | LangChain / LangGraph 场景最佳，$39/用户/月，只有 Enterprise 版能自托管 |
| 6 | Helicone | 基于代理：把 `OPENAI_API_BASE` 指向它即可，15–30 分钟接入；免费 100K 请求/月；附带故障转移、缓存、限流，兼作网关，但对多步 Agent trace 的深度不足 |
| 7 | OpenTelemetry GenAI 语义约定 | `gen_ai.system`、`gen_ai.request.model`、`gen_ai.usage.input_tokens` 等标准属性名，是不同工具之间互通的"胶水" |
| 8 | 生产常见模式 | 每次 LLM 调用发出带 GenAI 约定的 OTel → 网关做日常监控 → 双写到 eval 平台做回归 → 归档到数据湖做长期分析 |
| 9 | 埋点层次陷阱 | 在 Agent 框架内部埋点会被框架绑定；在 HTTP / OpenAI SDK 层（OpenLLMetry 或网关）埋点才可移植 |
| 10 | 采样 | 讲义：超过 1M 请求/天时全量保留不可行；规则是 100% 错误、100% 高成本、5% 成功；聚合指标永远保留 |

### 核心技能（能动手做到）

- [ ] 根据技术栈、许可证、预算、自托管四个维度，为一个团队选出"开发平台 + 网关 + 可选数据湖层"的组合
- [ ] 读懂 `simulate_day` 的保留逻辑，并能手算各采样策略的期望保留比例（如 `0.05 + 0.95 × 0.02 = 6.9%`）
- [ ] 改造模拟器，统计每种策略**丢掉了多少错误 trace 和高成本 trace**，用"丢失的信号"而不是"丢失的条数"评价策略
- [ ] 写出组织级强制要求的 OTel GenAI 属性集合，并用"属性完整率"监控埋点漂移
- [ ] 评估代理型网关（如 Helicone）的额外延迟对 TTFT SLA 的影响
- [ ] 识别成本模型中的口径错误（按 GB 计费 vs 按条 / 按 span 计费、零拷贝仍需自付存储）

---

## 二、基础自测（选择题）

**Q1.** 按讲义的分类，下列哪个工具属于"开发平台"（把监控与 eval、prompt 管理、数据集、会话回放打包在一起）？

- A. Helicone
- B. SigNoz
- C. OpenLLMetry
- D. Langfuse

**Q2.** 讲义推荐的 trace 采样规则是：

- A. 100% 错误、100% 高成本、约 5% 成功请求；聚合指标始终保留
- B. 所有请求一律随机保留 10%
- C. 只保留成功请求，错误请求写日志即可
- D. 只保留聚合指标，原始 trace 全部丢弃

**Q3.** `main.py` 中错误率为 2%。策略 "5% success + 100% errors" 在 1M trace/天时，**期望**保留的 trace 数最接近：

- A. 50,000
- B. 52,000
- C. 69,000
- D. 70,000

**Q4.** 讲义所说的"在错误的层次埋点"指的是：

- A. 在 HTTP 层用 OpenLLMetry 埋点
- B. 在 Agent 框架内部埋点（如只加 LangSmith trace），导致与该框架绑定；在 HTTP / OpenAI SDK 层埋点才可移植
- C. 在网关上埋点
- D. 同时向两个平台双写

**Q5.** 下列哪个是 OpenTelemetry GenAI 语义约定中的属性名（讲义列举的）？

- A. `gen_ai.usage.input_tokens`
- B. `llm.tokens.in`
- C. `openai.prompt_tokens`
- D. `http.llm.model`

**Q6.** 关于 Arize AX 声称的"约 100 倍便宜"，讲义给出的机制是：

- A. 它对 trace 做有损压缩
- B. 它只保留 1% 的 trace
- C. trace 以 Parquet 存在你自己的 S3（Iceberg 数据湖）里，Arize 直接读取（zero-copy），不再按量收取整体式平台的摄入费
- D. 它不支持 OpenTelemetry，因此更省

**Q7.** 按 `main.py` 中的常量（每条 4,500 字节、整体式平台 $0.50/GB），1M trace/天全量保留时，代码算出的"mono"月成本是：

- A. $2.25
- B. $6.75
- C. $675
- D. $67.50

**Q8.** 关于 Phoenix，下列说法与讲义一致的是：

- A. MIT 许可证，是持久化的生产级 trace 后端
- B. OpenTelemetry 原生、Elastic License 2.0，擅长 RAG 与漂移可视化，但主要用于开发期，不是持久化的生产后端
- C. 只能和 LangChain 一起使用
- D. 基于代理，改 `OPENAI_API_BASE` 即可接入

---

## 三、动手 / 代码题

**Q9.** 模拟器的 docstring 说会报告"what's lost under each"，但 `simulate_day` 只返回了丢失的**条数**：

```python
    for i in range(traces_per_day):
        is_error = rng.random() < 0.02
        is_highcost = rng.random() < 0.01
        keep = rng.random() < strategy.sample_rate
        if strategy.keep_errors and is_error:
            keep = True
        if strategy.keep_highcost and is_highcost:
            keep = True
```

1. 改造函数，额外返回 `lost_errors` 与 `lost_highcost`。
2. 用同样的种子（`random.Random(7)`）运行，"10% random sample" 与 "5% success + 100% errors" 分别丢了多少错误 trace、多少高成本 trace？
3. "5% success + errors + $$$" 与 "1% aggregates only" 两个策略在丢失的信号上有什么区别？后者的名字准确吗？

**Q10.** 运行输出的结尾打印：

```text
Read: 100% retention on Datadog-class costs hundreds of $/day.
5% success + 100% errors + high-cost keeps signal, cuts 90% of bill.
```

请对照表格里的数字检查这两句话，并找出成本模型中至少 2 处口径问题（提示：mono 一栏的量级；`ARIZE_AX_PER_GB` 与 `COST_PER_GB_MONTH` 的关系）。按代码的计费方式，每条 trace 要多大，全量保留才会达到 $300/天？

**Q11.**（讲义练习 2）每天 5M 条 trace，Datadog 报价 $150K/月。

1. 按 `main.py` 的常量，5M trace/天每月多少 GB？按代码的 $0.50/GB 算是多少钱？与报价相差多少倍，说明什么？
2. 假设 Arize AX "便宜 100 倍"的说法成立，且迁移一次性投入 $40K（假设值），多久回本？还需要把哪项成本加回去？

**Q12.**（讲义练习 3）写一个 Python 函数 `validate_genai_attrs(attrs: dict) -> list[str]`，检查组织强制要求的 GenAI 属性是否齐全，返回缺失项；再写 `completeness(spans)` 计算"属性完整的 span 比例"（skill 要求的漂移指标）。强制集合参考 skill：`gen_ai.system`、`gen_ai.request.model`、`gen_ai.usage.input_tokens`、`gen_ai.usage.output_tokens`、`gen_ai.request.temperature`、`gen_ai.response.finish_reasons`，外加 `tenant_id`、`user_id`、`task`。

---

## 四、面试高频题

**Q13.**（基础必考）你们刚上线了一个 LLM 功能，现在要选 observability 工具。你会怎么选？请按讲义的四个维度给出决策过程，并举 2–3 个典型组合。

**Q14.**（原理深挖）OpenTelemetry GenAI 语义约定解决了什么问题？讲义里"网关 + eval 平台 + 数据湖"的模式是怎样靠它粘起来的？

**Q15.**（工程实践）"100% 错误 + 100% 高成本 + 5% 成功"这条采样规则在工程上怎么实现？head sampling 与 tail sampling 有什么区别？采样后的指标如何避免偏差？

**Q16.**（场景设计）Helicone 代理带来约 20 ms 额外延迟。P99 TTFT 是 300 ms 时可以接受吗？如果 SLA 是 100 ms 呢？你会怎么设计（讲义练习 5）？

**Q17.**（追问型）"只用 Phoenix 做生产 observability 够不够？"——什么时候够、什么时候不够（讲义练习 4）？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Development platforms ... LangSmith, Langfuse, Comet Opik." Langfuse 提供 eval、prompt 管理、trace、数据集四类功能。

- A Helicone：代理型网关 + 遥测。
- B SigNoz：OpenTelemetry 优先的通用 APM。
- C OpenLLMetry：开源的 LLM OTel 埋点库。

三者都属于"网关 / 遥测工具"。

### Q2 — 答案：A

讲义："Sample by rules: 100% errors, 100% high-cost, 5% success. Keep aggregates always; keep raw for the long tail." 配套 skill 把"高成本"具体化为单次调用 > $0.10。

- B 均匀随机采样会按比例丢掉错误 trace，而错误恰恰是最需要排查的（见 Q9：10% 随机采样丢了约 90% 的错误）。
- C 正好反了。
- D 失去了排查单个请求的能力；讲义要求聚合"始终保留"，原始 trace 也要按规则保留。

### Q3 — 答案：C

一条 trace 被保留的概率 = P(错误) + P(非错误) × 5% = `0.02 + 0.98 × 0.05 = 0.069`，即约 69,000。实际运行输出 `retained=68808`，与期望吻合（随机波动）。

- A 只算了 5%，漏了错误。
- B 低估了错误的贡献（例如误以为错误只额外保留一小部分：50,000 + 2,000）。
- D 是 `5% + 2%` 简单相加，没有扣除"既是错误又被采样到"的重叠（重叠部分 `0.02 × 0.05 = 0.1%`）。

### Q4 — 答案：B

讲义："Instrumenting inside your agent framework (e.g., adding LangSmith traces) couples you to that framework. Instrumenting at the HTTP/OpenAI-SDK layer (via OpenLLMetry or your gateway) is portable." skill 的 Hard reject 也写明：只在框架专用 SDK 里埋点且没有 OTel 回退，应拒绝。

- A、C 都是讲义推荐的可移植层次。
- D 双写是讲义推荐的生产模式。

### Q5 — 答案：A

讲义列举了 `gen_ai.system`、`gen_ai.request.model`、`gen_ai.usage.input_tokens`。B、C、D 都是"看起来合理"的自定义名字，各工具自己发明名字正是 GenAI 约定要解决的互通问题。

### Q6 — 答案：C

讲义："you store traces in your own Parquet on S3; Arize reads directly." 整体式平台按摄入量收费，数据要先拷进它的存储；零拷贝把存储留在你自己的数据湖，平台只负责读取和展示。

- A、B 不是讲义描述的机制。
- D 错，Arize 系（含 Phoenix）都是 OpenTelemetry 原生。

注意："100 倍"是 Arize 的**声称**（讲义用的是 "claims"），代码里 `0.50 / 0.005 = 100` 只是把这个声称写成了常量。

### Q7 — 答案：D

`1,000,000 × 4,500 字节 = 4.5 GB/天`；`4.5 × 30 × $0.50 = $67.50/月`（运行输出 `mono=$   67.50`）。

- A $2.25 是**每天**的费用。
- B $6.75 是 10% 采样的月费用。
- C 多乘了 10。

这个数字与代码自己打印的 "100% retention on Datadog-class costs hundreds of $/day" 相差约 100 倍以上，见 Q10。

### Q8 — 答案：B

讲义："Elastic License 2.0; self-host trivial. Excellent at RAG and drift visualization ... Not designed as persistent production backend."

- A 许可证和定位都错。
- C 那是 LangSmith 的特点（LangChain / LangGraph 优先）。
- D 是 Helicone 的接入方式。

另外留意：讲义开头把 Phoenix 归入"网关 / 遥测工具"，而在生产模式里又把它当作"eval 平台（Phoenix / TruLens）"，Key Terms 中则称为 "dev/eval platform"，分类前后不完全一致。

### Q9 — 参考答案

1. 改造：

```python
def simulate_day(strategy, traces_per_day=1_000_000):
    rng = random.Random(7)
    retained = lost = lost_errors = lost_highcost = 0
    for _ in range(traces_per_day):
        is_error = rng.random() < 0.02
        is_highcost = rng.random() < 0.01
        keep = rng.random() < strategy.sample_rate
        if strategy.keep_errors and is_error:
            keep = True
        if strategy.keep_highcost and is_highcost:
            keep = True
        if keep:
            retained += 1
        else:
            lost += 1
            lost_errors += is_error          # bool 当作 0/1 累加
            lost_highcost += is_highcost
    ...
```

2. 实际运行结果（种子 7，这一天共有 19,956 条错误、10,159 条高成本）：

| 策略 | 丢失的错误 trace | 丢失的高成本 trace |
|------|-----------------|-------------------|
| 10% random sample | 18,005（约 90%） | 9,166（约 90%） |
| 5% success + 100% errors | 0 | 9,447（约 93%） |
| 5% success + errors + $$$ | 0 | 0 |
| 1% aggregates only | 0 | 0 |

3. 后两个策略都不丢错误和高成本 trace，区别只在成功请求的采样率（5% vs 1%），后者保留 39,710 条、成本约为前者一半。名字 "aggregates only" 不准确：代码里它仍然保留 1% 的原始成功 trace 以及全部错误和高成本 trace，而且模拟器根本没有计算任何聚合指标。

要点：评价采样策略要看"丢掉了哪些**有信号的** trace"，而不是总条数。另外每个策略都用同一个种子 `Random(7)`，所以各策略面对的是同一批错误 / 高成本 trace，这是"公共随机数"的对照实验写法，便于横向比较。

### Q10 — 参考答案

- **第一句不成立**：表格里全量保留的 mono 成本是 $67.50/**月**，约 $2.25/天，远不是"hundreds of $/day"。讲义说"超过 1M 请求/天时，全量 trace 保留的成本比 LLM 调用本身还高"，用代码自己的参数也得不出这个结论。
- **第二句基本成立**："5% success + errors + $$$" 保留 78,255 条，是全量的 7.8%，账单减少约 92%（`5.28 / 67.50`），"cuts 90%"是对的。
- **口径问题**：
  1. 每条 trace 只有 4,500 字节，适合单轮问答；多步 Agent trace（含工具调用、检索结果、长上下文）通常大得多。要让全量保留达到 $300/天：`300 / 0.5 = 600 GB/天`，`600 GB / 1M = 600 KB/条`。
  2. 整体式平台在现实中往往按 span 数、索引量或主机数计费，并不只是按 GB 摄入；按 GB 的单一单价会严重低估。
  3. `ARIZE_AX_PER_GB = 0.005` 比 S3 存储单价 `0.023` 还低，但零拷贝的前提是 trace 存在**你自己的** S3 上——你仍要付 S3 存储费。公平的比较应该是 `S3 + Arize` vs `整体式平台`。
  4. `s3_month = gb × 30 × 0.023`：这相当于"保留 30 天窗口的稳态存储量 × 单价"，对 30 天保留期是合理的；如果保留 90 天，应乘 90。代码没有把保留期作为参数。

### Q11 — 参考答案

1. `5M × 4,500 = 22.5 GB/天`，`× 30 = 675 GB/月`，按 $0.50/GB 是 **$337.50/月**。报价 $150K/月是它的约 444 倍（相当于 $222/GB）。说明：要么真实 trace 远大于 4.5 KB，要么 Datadog 类产品不是按这个 GB 单价计费（按 span / 索引 / 保留期等计费）。**练习的第一步应该是把报价拆成单位成本**，而不是直接套代码的常量。
2. 若"100 倍便宜"成立：Arize AX 约 $1.5K/月，每月节省约 $148.5K；一次性迁移 $40K（假设），约 0.27 个月即回本。但要把以下成本加回去：
   - 自有数据湖的 S3 存储与查询（DuckDB / Athena 等）费用；
   - 维护 Iceberg 表、分区、生命周期策略的工程人力；
   - 如果仍需要实时告警，可能还要保留一个轻量的实时通道（网关或 APM）。

   结论：在讲义说的 ">10M traces/day、已有数据湖"的场景下，零拷贝的优势非常明显；没有数据湖的团队要把搭湖成本算进去。

### Q12 — 参考答案

```python
REQUIRED = [
    "gen_ai.system", "gen_ai.request.model",
    "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens",
    "gen_ai.request.temperature", "gen_ai.response.finish_reasons",
    "tenant_id", "user_id", "task",
]

def validate_genai_attrs(attrs: dict) -> list[str]:
    return [k for k in REQUIRED if attrs.get(k) in (None, "", [])]

def completeness(spans: list[dict]) -> float:
    if not spans:
        return 0.0
    ok = sum(1 for s in spans if not validate_genai_attrs(s))
    return ok / len(spans)

spans = [
    {k: 1 for k in REQUIRED},
    {"gen_ai.system": "openai", "gen_ai.request.model": "x"},
]
print(validate_genai_attrs(spans[1])[:3])  # ['gen_ai.usage.input_tokens', 'gen_ai.usage.output_tokens', 'gen_ai.request.temperature']
print(completeness(spans))                 # 0.5
```

（已实际运行验证。）要点：

- 用 `attrs.get(k) in (None, "", [])` 同时识别"缺失"和"空值"；`0` 是合法的 token 数，不能用 `if not attrs.get(k)` 判断。
- `user_id` 可能是个人数据，应写哈希或内部 ID，并与合规要求（如 GDPR）对齐。
- 这个完整率就是 skill 结尾要求监控的"栈漂移"指标：过去 7 天带完整 GenAI 属性的调用占比。

### Q13 — 参考回答要点

- **四个维度**（讲义）：
  1. 技术栈：重度 LangChain / LangGraph → LangSmith 最顺手；原生 SDK 或多厂商 → 在 HTTP/SDK 层用 OTel 埋点。
  2. 许可证：只接受 MIT / Apache → Langfuse、Opik、SigNoz、Helicone；Elastic 可接受 → 加上 Phoenix；商业 → LangSmith、Arize AX。
  3. 预算：免费层（Langfuse 50K events、Helicone 100K 请求）→ $29–$39 级别 → 大规模时看 Arize AX 的零拷贝。
  4. 自托管：必须 → Langfuse / Opik / Phoenix；LangSmith 只有 Enterprise 才能自托管。
- **典型组合**：
  - 小团队快速起步：Helicone（代理 + 网关）+ Langfuse 云免费层；
  - LangChain 团队愿意付费：LangSmith；
  - 强监管、必须自托管：Langfuse 自托管 + SigNoz；
  - 超大规模：OTel → 网关 → Iceberg 数据湖 + Arize AX / DuckDB。
- 加分点：说明"开发平台"和"网关"解决的是不同问题，生产中往往两者都要，用 OTel 粘起来。

### Q14 — 参考回答要点

- **问题**：各家工具自定义属性名，换工具就要重新埋点、历史数据无法对齐。GenAI 约定统一了 `gen_ai.system`、`gen_ai.request.model`、`gen_ai.usage.*`、`gen_ai.response.finish_reasons` 等名字，任何消费 OTel 的工具都能理解（讲义：2025 年发布，2026 年广泛采用）。
- **粘合模式**（讲义四步）：每次调用发出 OTel → 网关（Helicone / Portkey）做日常监控 → 双写到 eval 平台（Phoenix / Langfuse）做回归 → 归档到数据湖（Iceberg）供 Arize AX 或 DuckDB 长期分析。
- **工程实现**：应用只依赖 OTel SDK；通过 OTel Collector 的多个 exporter 实现双写和采样，换后端只改 Collector 配置。
- 加分点：把成本、缓存命中（cached input tokens）、拒答等业务字段也作为标准化的自定义属性；用"属性完整率"监控埋点质量。
- 常见误区：以为接了 OTel 就不需要 eval 平台——OTel 只负责数据格式和传输，回归评测、prompt 管理仍需开发平台。

### Q15 — 参考回答要点

- **head sampling**：请求开始时就决定是否采样（如按 trace ID 哈希保留 5%）。实现简单、开销低，但开始时并不知道这次请求会不会出错、会不会很贵，所以**无法保证 100% 保留错误**。
- **tail sampling**：等 trace 结束后再根据状态、成本、延迟决定是否保留（OTel Collector 支持这种处理器）。讲义的规则本质上需要 tail sampling；`main.py` 的模拟也是在已知 `is_error`、`is_highcost` 之后才决定，等价于 tail sampling。代价是 Collector 要缓冲完整 trace，需要内存和按 trace ID 一致路由。
- **避免指标偏差**：聚合指标（错误率、P99、成本）应在采样**之前**从全量数据计算，或者对采样数据按采样率加权还原；否则"100% 保留错误"会让采样后数据里的错误率被严重高估（例如 `main.py` 的 "5% success + 100% errors" 策略下，保留集中约 29% 是错误，而真实错误率只有 2%）。
- 加分点：给采样后的 trace 打上 `sample_rate` 属性，方便后续加权；对长尾（新模型、新租户）提高采样率。

### Q16 — 参考回答要点

- **P99 TTFT 300 ms**：20 ms 约占 6.7%，通常可接受，换来的是零代码接入、成本归因、缓存和故障转移。
- **SLA 100 ms**：20 ms 占 20% 的预算，再加上网络和 prefill 很可能超标，不宜把代理放在关键路径上。
- **设计选项**：
  - 改为**异步旁路上报**：在 SDK 层用 OpenLLMetry 埋点，批量异步发送，不在请求路径上增加跳数；
  - 网关与推理服务同机房 / 同区域部署，减少网络往返；
  - 只对非延迟敏感的流量走代理。
- **验证方法**：在压测中分别测量有 / 无代理的 TTFT 分布（看 P99 而不是平均值），参考 [阶段 17 · 08](../../08-inference-metrics-goodput/docs/zh.md) 的指标定义。
- 常见误区：只比较平均延迟；忘了代理本身也是可用性风险，需要旁路或故障时直连。

### Q17 — 参考回答要点

- **够用的情况**：开发期、RAG 调试、漂移分析、小规模内部工具；Phoenix 对 embedding 空间散点图、检索质量可视化支持很好，自托管简单。
- **不够的情况**（讲义："Not designed as persistent production backend"）：
  - 需要长期、持久化的海量 trace 存储与查询；
  - 需要网关能力：故障转移、限流、缓存、按租户计费；
  - 需要生产告警（skill 列出的五项：错误率、P99 TTFT、单次成本、prompt-cache 命中率、拒答率）；
  - Elastic License 2.0 与公司的许可证政策冲突时。
- **推荐**：Phoenix 做开发 / eval，生产链路搭配网关（Helicone / Portkey）和持久化后端，通过 OTel 双写。
- 加分点：说明 Elastic License 2.0 不是 OSI 认可的开源许可证，对"只能用 MIT/Apache"的团队是硬约束。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：observability 要采集和告警的核心延迟指标。
- [阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../../14-agent-engineering/24-agent-observability-platforms/docs/zh.md)：从 Agent 视角看同一批工具。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：开发平台里的 eval 与回归测试。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：Phoenix 擅长的 RAG 评测指标。

### 本节被哪些后续内容用到
- [阶段 17 · 14 Prompt 缓存与语义缓存的经济性](../../14-prompt-semantic-caching/docs/zh.md)：缓存命中率是必须告警的指标之一。
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../19-ai-gateways/docs/zh.md)：网关层的遥测与本节的"网关 + eval 平台"模式。
- [阶段 17 · 23 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测](../../23-sre-for-ai/docs/zh.md)：基于 trace 与告警的事故响应。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../27-finops-llms/docs/zh.md)：按租户归因成本依赖 trace 中的 `tenant_id`。
- [阶段 19 · 11 综合项目 11：LLM Observability 与评估仪表盘](../../../19-capstone-projects/11-llm-observability-dashboard/docs/zh.md)：动手搭建仪表盘。
- [阶段 19 · 28 综合项目第 28 课：通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../../19-capstone-projects/28-observability-otel-traces/docs/zh.md)：GenAI span 的完整实现。

### 延伸关键词
`OpenTelemetry` · `GenAI semantic conventions` · `OpenLLMetry` · `OTel Collector` · `tail sampling` · `head sampling` · `zero-copy` · `Apache Iceberg` · `Parquet` · `Elastic License 2.0` · `session replay` · `prompt management` · `cost attribution`
