# 测验 · 批处理 APIs：作为行业标准的五折优惠（Batch APIs — the 50% Discount as Industry Standard）

> **阶段 17 · 基础设施与生产 · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 行业通行的 batch 报价 | OpenAI、Anthropic、Google 以及多数推理平台都提供异步 batch API：输入和输出一律 5 折，承诺 24 小时内返回 |
| 2 | 三家的接口形态 | OpenAI：上传 JSONL，`/v1/batches`；Anthropic Message Batches：JSONL，支持 `cache_control`；Vertex AI Batch Prediction：BigQuery 或 GCS 输入 |
| 3 | "异步"不等于"慢" | 24 小时是**上限承诺**，讲义：典型 P50 为 2–6 小时；provider 把 batch 安排在 GPU 空闲的低峰时段 |
| 4 | 与 prompt 缓存叠加 | 共享系统提示的缓存读取再便宜 10 倍，batch 再打 5 折；讲义称叠加后约为"同步无缓存"的 10% |
| 5 | 叠加效果取决于 token 构成 | 只有**共享前缀**能吃到缓存折扣；每个文档自己的输入和输出只享受 5 折。代码的三个场景实际是 24.3%、17.1%、41.3%，不是 10% |
| 6 | 三条车道 | interactive（用户在等，TTFT 重要，同步 + 缓存）、semi-interactive（几分钟可以，异步队列 + 回退）、batch（"明早给我"，batch + 缓存） |
| 7 | 决策规则 | "如果用户察觉不到 24 小时延迟，就一定 batch"；"production 不是延迟规格，SLA 才是" |
| 8 | 部分交互陷阱 | 看起来交互、实际能等 5–10 分钟的功能（如带"刷新"按钮的日报）被做成同步，讲义例子中 50 个并发刷新的成本是"batch + 邮件送达"的 10 倍 |
| 9 | 输出格式陷阱 | 各家 batch 文件格式不同，"一个通用 batch 客户端"必须给每家写适配器；网关的多厂商 batch 也只是薄封装 |
| 10 | 缓存启用方式差异 | 配套 skill：OpenAI batch 的缓存对 ≥ 1024 token 的 prompt 自动生效；Anthropic batch 需要显式 `cache_control` 块 |

### 核心技能（能动手做到）

- [ ] 写出 sync / sync + cache / batch / batch + cache 四种配置的成本公式，并用闭式解代替逐条循环
- [ ] 给定共享前缀、每文档输入、输出 token 数，算出叠加折扣占基线的比例，并说明它的下限为什么是 5%
- [ ] 把一个工作负载按用户的真实延迟预期分到三条车道之一，并说出理由
- [ ] 识别"部分交互"与"把 production 当作实时"的误判
- [ ] 为 batch 设计 P99 迟到时的下游行为（溢出到同步、邮件送达、状态通知）和监控告警
- [ ] 指出 `main.py` 中"约 10%"的标题与实际输出不一致的原因

---

## 二、基础自测（选择题）

**Q1.** 讲义所说的、2026 年各大 provider 通行的 batch API 报价是：

- A. 输入和输出一律 5 折，承诺 24 小时内返回
- B. 只有输入 5 折，输出原价
- C. 9 折，1 小时内返回
- D. 免费，但只能在周末运行

**Q2.** 关于"24-hour turnaround"，与讲义一致的理解是：

- A. 每个 batch 都会正好在 24 小时后返回
- B. 24 小时是典型 P50
- C. 24 小时是上限承诺，典型 P50 约 2–6 小时，provider 利用低峰时段调度
- D. 超过 24 小时未完成的部分会按同步价格补收费用

**Q3.** 运行 `main.py`，"Nightly doc summarization (50k docs)" 的 BATCH + CACHE 是基线的 **24.3%**，而不是标题所说的约 10%。主要原因是：

- A. 代码忘了对 batch 打 5 折
- B. 缓存写入溢价太高
- C. 50k 个文档太少，缓存没来得及生效
- D. 只有 4,000 token 的共享前缀能吃到缓存折扣；每个文档自己的 2,000 token 输入和 200 token 输出（$15/M）只能享受 5 折，它们在叠加后占了成本的大头

**Q4.** 一个"客户健康日报"每晚生成，页面上有"刷新"按钮，用户点了之后等 10 分钟也能接受，团队把它做成了同步调用。按讲义，这属于：

- A. 正确的 interactive 车道
- B. 部分交互陷阱：它其实能容忍分钟级延迟，应走异步 / batch 并通过邮件等方式送达，而不是同步
- C. 输出格式陷阱
- D. 并行缓存陷阱

**Q5.** 按 `main.py` 的价格（输入 $3/M、输出 $15/M），50,000 个文档、共享前缀 4,000 token、每文档 2,000 token、输出 200 token 的**同步无缓存**成本是：

- A. $750
- B. $900
- C. $1,050
- D. $1,350

**Q6.** 按 `main.py` 的模型（缓存读取 = 基础输入的 1/10，batch 再打 5 折），当共享前缀在 token 构成中占绝对主导（每文档输入和输出都趋近 0）时，BATCH + CACHE 占同步基线的比例趋近于：

- A. 5%
- B. 10%
- C. 0%
- D. 25%

**Q7.** 讲义中的"output-schema trap"指的是：

- A. batch 返回的 JSON 字段会随机变化
- B. 各家 batch 的文件格式不同（OpenAI / Anthropic 的 JSONL、Vertex 的 BigQuery 表或 GCS），想做"一个通用 batch 客户端"就得为每家写适配器
- C. batch 不支持结构化输出
- D. batch 的输出 token 价格不同

**Q8.** 按本节配套 skill，关于 batch 中使用 prompt 缓存，正确的是：

- A. 两家都必须显式加 `cache_control`
- B. 两家都完全不支持在 batch 中使用缓存
- C. OpenAI batch 需要 `cache_control`，Anthropic 自动缓存
- D. OpenAI 对 ≥ 1024 token 的 prompt 自动缓存；Anthropic Message Batches 需要在可缓存部分显式加 `cache_control` 块，batch 折扣与缓存读价可叠加

---

## 三、动手 / 代码题

**Q9.**（讲义练习 1）10 万个文档，共享系统提示 3,000 token，输出 500 token。讲义没有给出每文档自己的输入长度，请分别按 0、500、2,000 token 计算 SYNC 与 BATCH + CACHE 的成本，以及节省的金额和比例。结果说明了什么？

**Q10.** `cost_sync` 和 `cost_sync_cache` 都用 `for` 循环逐条累加：

```python
def cost_sync_cache(docs: int, prefix_tokens: int, per_doc_tokens: int, out_tokens: int) -> float:
    cost = (prefix_tokens / 1e6) * CACHE_WRITE_5MIN
    for i in range(docs):
        if i > 0:
            cost += (prefix_tokens / 1e6) * CACHED_INPUT
        cost += (per_doc_tokens / 1e6) * BASE_INPUT
        cost += (out_tokens / 1e6) * BASE_OUTPUT
    return cost
```

1. 写出四种配置的闭式公式（不用循环），并验证与原函数在三个场景上的结果一致。
2. 由公式推导：BATCH + CACHE / SYNC 的比例由哪些量决定？要做到讲义说的"约 10%"，需要满足什么条件？

**Q11.** 找出本节讲义、代码与标题之间至少 4 处不一致或过于乐观的假设。（提示：讲义 The Problem 的 $2,000 → $180；`cost_sync_cache` 中缓存写了几次；batch 内部请求的执行方式与上一节的"并行陷阱"。）

**Q12.** 按讲义与 skill 的规则写一个 `triage(expect_s, p99_sla_s=None) -> str`：P99 SLA < 60 秒必须 interactive；用户预期 < 15 分钟不能用 batch（≤ 10 秒算 interactive，否则 semi-interactive）；≥ 24 小时直接 batch；介于两者之间（如"明早给我"）走 batch，但必须配溢出到同步的通道。对"聊天（2 秒，P99 5 秒）""刷新日报（10 分钟）""夜间简报（10 小时）""批量标注（3 天）"四个负载给出结果。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 batch API？provider 为什么愿意打 5 折？哪些工作负载应该用它？

**Q14.**（原理深挖）"batch + 缓存 ≈ 同步无缓存的 10%"这句话在什么条件下成立？请用公式说明，并举出它不成立的例子。

**Q15.**（工程实践）把一个每晚 5 万文档的同步摘要管道迁移到 batch API，你会怎么做？要处理哪些工程细节和失败情况？

**Q16.**（场景设计）batch 承诺 24 小时，但你观察到 P99 是 20 小时。你如何对用户沟通？下游系统在边缘情况下应该怎么表现（讲义练习 4）？

**Q17.**（追问型）用户抱怨"我的报告花了 3 个小时"。这是 batch 车道分错了，还是正常现象？请给出判定标准（讲义练习 3）。

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Every major provider ships an async batch API with a 50% discount and ~24-hour turnaround." 以及 "Batch discount across providers: 50% flat on input + output."

- B 错：输入输出都打折。
- C、D 是编造的条件。

### Q2 — 答案：C

讲义："Batch is 'I promise to return within 24 hours' — not 'this will take 24 hours.' Typical P50 is 2-6 hours. Provider schedules your batch during off-peak windows when GPU inventory is underutilized."

- A、B 都把上限当成了常态。
- D 讲义没有这种说法。

### Q3 — 答案：D

拆开这个场景的成本（实际计算）：

| 部分 | SYNC | BATCH + CACHE |
|------|------|---------------|
| 共享前缀 4,000 token | $600 | 约 $30 |
| 每文档 2,000 token | $300 | $150 |
| 输出 200 token | $150 | $75 |
| 合计 | $1,050 | 约 $255（24.3%） |

缓存把前缀从 $600 压到约 $30，但每文档输入和输出只能打 5 折，二者合计 $225，占叠加后成本的 88%。

- A 错：`cost_batch_cache = cost_sync_cache × 0.5`，打了折。
- B 错：写入溢价只付一次（$0.015），可以忽略。
- C 错：代码假设第 2 个文档起就全部命中，与文档数量无关。

### Q4 — 答案：B

讲义的例子："a nightly customer health report with 'refresh' button. User clicks refresh; wait 10 minutes is fine. Team ships it as synchronous. 50 concurrent refreshes cost 10x what batched-and-delivered-via-email would cost." 判断问题是："What does 24-hour mean for this user?"

- A 错：用户可以等，不需要同步。
- C、D 是另外两类陷阱。

注意：skill 规定"用户预期低于 15 分钟的不能承诺 batch"，所以 10 分钟的刷新更适合 **semi-interactive**（异步队列）或"预先 batch 生成 + 送达"，而不是让用户点了按钮再提交一个 24 小时的 batch。

### Q5 — 答案：C

每文档：`4,000 × 3/1e6 + 2,000 × 3/1e6 + 200 × 15/1e6 = 0.012 + 0.006 + 0.003 = $0.021`；`× 50,000 = $1,050`（与运行输出一致）。

- A 漏了每文档的 2,000 token（这正是讲义 "Stack with caching" 一节示例的算法，它只写了前缀和输出）。
- B 漏了输出。
- D 把输出按 $30/M 算了。

### Q6 — 答案：A

前缀主导时，SYNC ≈ `P × p_in`，BATCH + CACHE ≈ `0.5 × P × 0.1 p_in`，比例 → `0.5 × 0.1 = 5%`。

- B 的 10% 是讲义的口号数字，需要前缀占比很高且输出很少才能接近（例如前缀 4,000、无每文档输入、输出 20 token 时约 6.1%）。
- C 错：缓存读取不是免费的。
- D 是没有缓存、只看前缀时也到不了的数字。

### Q7 — 答案：B

讲义："Batch file formats differ per provider ... Writing 'one batch client' across providers means adapter code per provider. Gateways that advertise multi-provider batch (Portkey, LiteLLM some tiers) still thin-wrap the raw format."

- A、C、D 都不是讲义所说的问题。

### Q8 — 答案：D

skill 的迁移步骤："OpenAI ... Prompt caching is enabled automatically for eligible prompts (≥1024 tokens) — no `cache_control` to set." "Anthropic ... Cache reuse requires explicit `cache_control` blocks ... batch discount stacks with cached-read pricing."

- A、C 把两家的机制说错或说反。
- B 错：两家都可以在 batch 中使用缓存。

### Q9 — 参考答案

用 `main.py` 中的函数实际计算：

| 每文档输入 | SYNC | BATCH + CACHE | 占基线 | 节省 |
|-----------|------|---------------|-------|------|
| 0 | $1,650.00 | $420.01 | 25.5% | $1,229.99 |
| 500 | $1,800.00 | $495.01 | 27.5% | $1,304.99 |
| 2,000 | $2,250.00 | $720.01 | 32.0% | $1,529.99 |

说明：

- 绝对节省金额随规模增长，但**比例**离 10% 很远：500 token 输出（$15/M）每文档就要 $0.0075，batch 后仍有 $0.00375，是叠加后成本的主体（每文档输入为 0 时，10 万文档的输出部分 $375 占 $420 的 89%）。
- 结论：叠加折扣的比例由 token 构成决定，估算时要按"前缀 / 每文档输入 / 输出"三段分别算，不能直接套"10%"。

### Q10 — 参考答案

1. 闭式公式（记 N = 文档数，P = 前缀，D = 每文档输入，O = 输出，单价单位 $/M）：

```python
def closed(docs, p, d, o, batch=False, cache=False):
    pin, pout, pread, pwrite = 3.0, 15.0, 0.3, 3.75
    if cache:
        prefix = p * pwrite + (docs - 1) * p * pread   # 写 1 次，读 N-1 次
    else:
        prefix = docs * p * pin
    c = (prefix + docs * d * pin + docs * o * pout) / 1e6
    return c * (0.5 if batch else 1.0)
```

在三个场景上实际验证：SYNC 分别为 $1,050.00 / $1,230.00 / $93.00，BATCH + CACHE 分别为 $255.01 / $210.00 / $38.41，与原函数输出完全一致。闭式解是 O(1)，原循环是 O(N)。

2. 忽略唯一一次写入，比例为：

   `ratio = 0.5 × (0.1·P·p_in + D·p_in + O·p_out) / (P·p_in + D·p_in + O·p_out)`

   它只取决于 P、D、O 三者的相对大小（与 N 无关）。要接近 10%，分子中的 `D·p_in + O·p_out` 必须远小于 `P·p_in`：共享前缀很长、每条输入很短、输出极少——典型的是"长系统提示 + 短条目分类 + 单个标签输出"。比例的理论下限是 5%。

### Q11 — 参考答案

1. **标题与输出不一致**：`main()` 标题和模块 docstring 都写"~10% of sync bill"，实际三个场景是 24.3%、17.1%、41.3%。
2. **讲义 The Problem 的数字无法复现**：讲义说 5 万文档同步 $2,000/晚，叠加后 $180/晚（约 9%）；用本节代码的价格和第一个场景参数，是 $1,050 → $255（24.3%）。讲义 "Stack with caching" 一节的公式只写了 4,000 前缀与 200 输出、漏掉了每文档内容；即使按它算（每文档输入 0），也是 $750 → $105（14.0%）。
3. **缓存命中被假设为 100%**：`cost_sync_cache` 只写一次前缀，之后每个文档都读取。batch 内的请求由 provider 并行调度，上一节的"并行陷阱"（首个写入完成前到达的请求都 miss）在 batch 里同样可能发生，代码没有建模这种不确定性。
4. **TTL 被忽略**：5 分钟 TTL 只有在请求持续到达时才会一直有效；讲义说同步跑这个管道要 4 小时，代码默认缓存全程有效。
5. **"Large report draft"一行很说明问题**：BATCH（50.0%）比 SYNC + CACHE（82.6%）更便宜，说明在"前缀小、每条内容大"的场景下 batch 比缓存更重要，"总是叠加"带来的增量只有 50% → 41.3%。
6. 讲义把 "next hour" 也列为 batch 车道的用户预期，但 batch 只承诺 24 小时；skill 又规定 15 分钟以内的预期不能用 batch。"1 小时"这类预期实际处在灰色地带，需要配溢出通道。

### Q12 — 参考答案

```python
def triage(expect_s: float, p99_sla_s: float | None = None) -> str:
    if p99_sla_s is not None and p99_sla_s < 60:
        return "interactive"
    if expect_s < 15 * 60:
        return "interactive" if expect_s <= 10 else "semi-interactive"
    if expect_s >= 24 * 3600:
        return "batch"
    return "batch + spillover"

for name, e, s in [("chat", 2, 5), ("refresh report", 600, None),
                   ("nightly brief", 10 * 3600, None), ("bulk labeling", 3 * 86400, None)]:
    print(f"{name:15} -> {triage(e, s)}")
```

实际运行输出：

```text
chat            -> interactive
refresh report  -> semi-interactive
nightly brief   -> batch + spillover
bulk labeling   -> batch
```

要点：

- 判断依据是**用户的真实延迟预期**，不是"它是不是生产功能"（讲义："Production is not a latency spec — SLA is."）。
- "明早给我"（10 小时）低于 24 小时的承诺上限：典型 P50 只有 2–6 小时，所以可以 batch，但要有"临近截止仍未完成就溢出到同步"的通道（skill 的 spillover lane）。
- 阈值（10 秒、15 分钟）应来自产品与用户研究，这里按 skill 的规则取值。

### Q13 — 参考回答要点

- **是什么**：把大量请求打包成文件（OpenAI / Anthropic 用 JSONL，Vertex 用 BigQuery / GCS）异步提交，provider 承诺 24 小时内返回结果，价格 5 折。
- **为什么能打折**：讲义——provider 把 batch 安排在低峰时段，用掉原本闲置的 GPU；对 provider 来说，可以自由调度、做大批量、填满利用率，成本远低于必须立即响应的同步请求。
- **适用负载**：内容生成管道、文档分类、数据抽取、报告生成、批量标注、商品打标——任何能容忍 24 小时延迟的任务；有共享系统提示时再叠加缓存。
- **不适用**：用户在等待的交互功能；P99 SLA 很紧的任务；15 分钟内必须出结果的任务。
- 加分点：说出"异步不是慢"，典型 P50 2–6 小时；以及"production ≠ 实时"。

### Q14 — 参考回答要点

- 公式（见 Q10）：`ratio ≈ 0.5 × (0.1·P·p_in + D·p_in + O·p_out) / (P·p_in + D·p_in + O·p_out)`，下限 5%。
- **成立的条件**：共享前缀占输入的绝大部分、每条内容短、输出很短。例如长系统提示 + 短条目分类 + 单标签输出。
- **不成立的例子**：
  - 本节代码三个场景：24.3%（摘要，输出 200）、17.1%（分类）、41.3%（长报告，每条 15K 输入 + 2K 输出）；
  - 输出 token 多：输出单价是输入的 5 倍，且不能缓存；
  - 没有共享前缀，或前缀里有动态内容（上一节的陷阱）——只剩 50%。
- 加分点：指出 batch 内并行执行可能导致缓存命中率低于 100%，估算时应使用实测的 cached tokens 比例。

### Q15 — 参考回答要点

- **构建请求文件**：每行一个请求，带唯一 ID（如 `custom_id`）以便把结果映射回文档；共享系统提示放在最前并按各家方式启用缓存（Anthropic 显式 `cache_control`，OpenAI 自动）。
- **分片与限额**：按 provider 的单文件大小 / 请求数上限拆分成多个 batch，分别提交和跟踪。
- **轮询与回调**：轮询状态或使用 webhook（skill："instrument a success/failure webhook"）。
- **部分失败**：逐行检查结果，失败的行重新组 batch 重试，保证幂等（以 ID 去重）。
- **溢出通道**：临近截止仍未完成的部分改走同步（skill 的 spillover lane）。
- **多厂商适配**：为每家写格式适配器（输出格式陷阱），不要假设一个客户端能通吃。
- **监控**：batch 完成延迟 P95，超过 12 小时告警（skill）；cached tokens 比例；单文档成本。
- **下游**：聚类与执行摘要等后续步骤改为"等 batch 完成后触发"，而不是串在同步流程里。

### Q16 — 参考回答要点

- **沟通**：对用户承诺的是"截止时间"而不是"即时"，例如"每天早上 8 点前送达"，并在 UI 上显示状态（排队中 / 处理中 / 已完成）。P99 20 小时意味着每 100 次有 1 次接近 20 小时，承诺的截止时间要留出余量。
- **提交时间前移**：如果要求早上 8 点交付，而 P99 是 20 小时，就要在前一天中午之前提交，或者接受少量任务需要溢出。
- **边缘情况的下游行为**：
  - 到达预设的截止阈值（如提交后 12 小时，或交付前 2 小时）仍未完成 → 未完成的部分溢出到同步执行；
  - 先交付已完成部分，并明确标注"部分结果"，剩余部分完成后补发；
  - 邮件 / 通知送达，而不是让用户在页面上等待。
- **监控**：完成时间分布（P50 / P95 / P99）、溢出比例、溢出带来的额外成本。
- 常见误区：只看 P50（2–6 小时）就向用户承诺"几小时内"。

### Q17 — 参考回答要点

- **判定标准**：看用户的**预期**而不是实际耗时。
  - 如果这是"明早看"的报告，3 小时完全在 batch 的正常范围内（P50 2–6 小时），用户的抱怨说明预期没有被管理好，应改进沟通与送达方式（邮件、完成通知）。
  - 如果用户是点了按钮在页面上等，说明这是 interactive 或 semi-interactive 的需求被错放进了 batch——skill 规定 15 分钟以内的预期不能承诺 batch。
- **可以落地的规则**：为每个功能写明"用户可接受的最长等待时间"；< 10 秒 → interactive；< 15 分钟 → semi-interactive（异步队列 + 回退）；"按天"→ batch。
- **改进**：对确实需要更快的场景，用同步 + 缓存；对 batch 场景提供进度提示与送达通知。
- 加分点：定期（skill 建议每季度）重新分车道，因为产品形态变化会改变用户预期。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 14 Prompt 缓存与语义缓存的经济性](../../14-prompt-semantic-caching/docs/zh.md)：缓存读写价格与"并行陷阱"，本节的叠加折扣以它为基础。
- [阶段 17 · 02 Inference 平台经济性：Fireworks、Together、Baseten、Modal、Replicate、Anyscale](../../02-inference-platform-economics/docs/zh.md)：推理平台的 batch 档位与定价方式。
- [阶段 11 · 11 缓存、请求速率限制与成本优化](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：应用层成本优化的基本手段。

### 本节被哪些后续内容用到
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../16-model-routing/docs/zh.md)：另一个与 batch、缓存并列的降本杠杆。
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../19-ai-gateways/docs/zh.md)：网关对多厂商 batch 的封装。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../27-finops-llms/docs/zh.md)：把车道划分纳入成本治理。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：interactive 车道关心的延迟指标。

### 延伸关键词
`Batch API` · `JSONL` · `/v1/batches` · `Message Batches` · `Vertex AI Batch Prediction` · `turnaround SLA` · `workload triage` · `stacked discount` · `cache_control` · `spillover lane` · `off-peak scheduling` · `idempotency`
