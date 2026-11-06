# 测验 · 缓存、请求速率限制与成本优化（Caching, Rate Limiting & Cost Optimization）

> **阶段 11 · LLM 工程 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/caching_cost.py](../code/caching_cost.py) ｜ 代码讲解：[code/caching_cost.讲解.md](../code/caching_cost.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | LLM 调用的成本构成 | 成本 = 输入 token × 输入单价 + 输出 token × 输出单价（按每百万 token 计价）；输出单价通常是输入的 4–5 倍，system prompt 每次请求都被重复计费 |
| 2 | 单位经济学算账 | 讲义例子：1 万 DAU × 每人 10 次 × (1000 输入 + 500 输出)，按 $2.50/$10 计，每天 $750、每月 $22,500 |
| 3 | Provider prompt caching | 由模型厂商在服务端缓存相同前缀：Anthropic 显式 `cache_control`，命中省 90%、写入多付 25%；OpenAI 自动前缀匹配，命中省 50%，前缀需 ≥1,024 token |
| 4 | Exact cache（精确缓存） | 对 `model + messages + temperature` 做 SHA-256 哈希查表；只适用于 temperature = 0 的确定性调用 |
| 5 | Semantic cache（语义缓存） | 把查询 embedding 后与历史查询算余弦相似度，超过阈值（讲义建议 0.92–0.95）就返回缓存答案，能接住"换个说法"的重复问题，但有误命中风险 |
| 6 | Token bucket 限流 | 每个用户一个容量 N、每秒补充 R 的桶；允许突发（一次用光整桶），长期平均速率不超过 R；常与"每分钟请求数"限制叠加 |
| 7 | Model routing（模型路由） | 用分类器把简单问题送到便宜模型、复杂问题送到贵模型；讲义称可省 40–70% 模型成本，前提是分类准确 |
| 8 | 成本追踪 | 每次调用记录时间戳、模型、输入/输出 token、延迟、成本、用户、缓存命中与否、请求类别，才能知道钱花在哪 |
| 9 | 预算告警与 circuit breaker | 70% 告警、85% 降级到便宜模型、95% 只返回缓存/拒绝新请求；告警只是通知，breaker 必须真正拦截请求 |
| 10 | Batch API 与优化栈顺序 | OpenAI Batch API 异步处理、五折、24 小时内返回、单批最多 50,000 个请求，只适合离线任务；优化按"provider 缓存 → 精确缓存 → 语义缓存 → 路由 → 限流 → 压缩 → 批处理"逐层叠加 |

### 核心技能（能动手做到）

- [ ] 给定 DAU、调用频次、平均 token 数和单价，能在一分钟内估出日/月成本，并指出 system prompt 占比
- [ ] 能算出 provider prompt caching 在"部分输入命中缓存"时的真实节省比例（不是简单的 90%），并考虑首次写入溢价
- [ ] 用 `hashlib` + `json.dumps(sort_keys=True)` 实现精确缓存，说清缓存键里必须包含哪些字段
- [ ] 实现基于 embedding 的语义缓存（含阈值、TTL、淘汰策略），并能解释为什么词袋向量做不好语义缓存
- [ ] 实现 token bucket 限流，手算 `retry_after` 秒数
- [ ] 读出本节代码中路由分类器、精确缓存键、预算告警的 bug，并给出修复
- [ ] 设计 70/85/95 三级降级的 circuit breaker，并让它真正影响请求路径

---

## 二、基础自测（选择题）

**Q1.** 讲义"问题"一节的场景：10,000 DAU，每人每天 10 次查询，每次 1,000 输入 token、500 输出 token，单价按输入 $2.50 / 百万、输出 $10.00 / 百万。**每月**（30 天）LLM 费用约为：

- A. $750
- B. $7,500
- C. $22,500
- D. $225,000

**Q2.** 关于三家厂商的 provider prompt caching，下列说法与讲义一致的是：

- A. Anthropic 需要在 prompt 中显式加 `cache_control` 标记，命中享 90% 折扣、写入需多付 25%；OpenAI 自动匹配前缀，命中享 50% 折扣，前缀至少 1,024 token
- B. OpenAI 需要显式标记，Anthropic 是自动的
- C. 三家都是命中享 90% 折扣，区别只在缓存时长
- D. provider caching 能识别"意思相同但措辞不同"的查询

**Q3.** 本节 `ExactCache.get("gpt-4o-mini", messages, temperature=0.7)` 的行为是：

- A. 若之前用 temperature=0.0 存过同样的 messages，仍返回那条缓存
- B. 抛出 `ValueError`，提示 temperature 必须为 0
- C. 把 0.7 一起哈希，作为一条独立的缓存键去查
- D. 直接返回 `None`，并把 `misses` 计数加 1，不查缓存

**Q4.** 本节 `simple_embed` 是"小写 + 按空格切词 + 词频 L2 归一化"的词袋向量。`"What is the return policy?"` 与 `"How do I return an item?"` 的余弦相似度约为多少？在演示的阈值 0.75 下是否命中？

- A. 约 0.95，命中
- B. 约 0.18，不命中
- C. 0，不命中，因为标点不同
- D. 约 0.80，命中

**Q5.** 本节 `TokenBucketRateLimiter` 的 free 档：容量 50,000、每秒补充 500 token。某用户桶里只剩 500 token，又发来一个需要 2,000 token 的请求，`check` 返回的 `retry_after_seconds` 是：

- A. 4.0
- B. 1.5
- C. 60
- D. 3.0

**Q6.** 运行 `route_model("Analyze the pros and cons of serverless architecture", "pro")`，结果是 `gpt-4o-mini (simple)`。最主要的原因是：

- A. 这句话不超过 5 个单词
- B. `SIMPLE_KEYWORDS` 里的 `"hi"` 用子串匹配命中了 `"architecture"`，而且 simple 的判断写在 complex 之前
- C. `"pros"` 被列为简单关键词
- D. pro 档用户只能使用 gpt-4o-mini

**Q7.** 关于 OpenAI Batch API，下列说法正确的是：

- A. 异步处理、全部 token 五折，24 小时内返回结果，单批最多 50,000 个请求；适合夜间文档处理、批量分类、评估跑批，不适合实时对话
- B. 与实时 API 同价，但延迟更低
- C. 只对缓存命中的 token 打五折
- D. 适合面向用户的实时问答，因为能把并发请求合并

**Q8.** 代码演示 `claude-sonnet-4`：2,000 输入 token（其中 1,500 命中缓存）+ 500 输出 token，输出为 "Savings per call: $0.004050 (30.0%)"。缓存折扣明明是 90%，为什么整体只省 30%？

- A. 代码把缓存单价写错了，应该是 $0.03 / 百万
- B. Anthropic 的实际缓存折扣只有 30%
- C. 折扣只作用于 1,500 个被缓存的输入 token；剩余 500 个输入 token 和全部输出 token 按原价计，而输出（$15 / 百万）本来就占这次调用成本的一半以上
- D. 缓存要 5 分钟后才生效，第一次调用不打折

---

## 三、动手 / 代码题

**Q9.** 阅读 `run_demo` 中"优化后"流水线（节选）：

```python
    for q in queries:
        messages = [{"role": "user", "content": q}]
        cached = exact_c.get("gpt-4o", messages, 0.0)
        if cached:
            tracker_after.log_call("gpt-4o-mini", 0, 0, latency_ms=5, cache_status="hit")
            continue
        sem_cached = semantic_c.get(q)
        if sem_cached:
            tracker_after.log_call("gpt-4o-mini", 0, 0, latency_ms=15, cache_status="hit")
            continue
        route = route_model(q)
        result = simulate_llm_call(route["model"], q)
        tracker_after.log_call(route["model"], result["input_tokens"], result["output_tokens"], latency_ms=result["latency_ms"], cache_status="miss")
        exact_c.put(route["model"], messages, 0.0, result["response"])
        semantic_c.put(q, result["response"])
```

1. 如果把 `"Hello"` 在 `queries` 里放两次，第二次会命中精确缓存吗？为什么？
2. 实际运行输出 `Cache hit rate: 0%`、`SAVINGS: 67.3% cost reduction`、`Latency improvement: 0.0% faster`。这 67.3% 来自哪里？为什么延迟毫无改善？
3. `tracker_after.summary()["cache_savings"]` 永远是多少？为什么？
4. 打印的标题是 "caching + routing + rate limiting"，代码里真的用了限流吗？

**Q10.** 下面是本节的复杂度分类器：

```python
SIMPLE_KEYWORDS = ["what time", "hours", "address", "phone", "price", "return policy", "hello", "hi", "thanks", "yes", "no"]
COMPLEX_KEYWORDS = ["analyze", "compare", "explain why", "write code", "debug", "architect", "design", "trade-off", "evaluate"]

def classify_complexity(query):
    q = query.lower()
    if len(q.split()) <= 5 or any(kw in q for kw in SIMPLE_KEYWORDS):
        return "simple"
    if any(kw in q for kw in COMPLEX_KEYWORDS):
        return "complex"
    return "medium"
```

1. 找出演示中被误判为 simple 的查询，并指出各自是被哪条规则"误伤"的。
2. 改写 `classify_complexity`：关键词按整词匹配，且 complex 优先判断。
3. 用修复后的分类器重跑"优化后"流水线，节省比例会变高还是变低？这说明了什么？
4. pro 档路由表是 `simple → gpt-4o-mini`、`medium → claude-sonnet-4`、`complex → gpt-4o`。对照 `MODEL_PRICING`，这张表有什么不合理之处？

**Q11.** "Budget Alerts Demo" 的实际输出如下（预算 $0.01，每次调用 gpt-4o 5,000 入 / 2,000 出）：

```text
  Total spent: $0.162500 / $0.01
  ALERT [STOP]: Budget 95% consumed: $0.03/$0.01
  ALERT [THROTTLE]: Budget 85% consumed: $0.07/$0.01
  ALERT [WARNING]: Budget 70% consumed: $0.10/$0.01
```

1. 告警为什么是"先 STOP、后 WARNING"的倒序？文案"95% consumed: $0.03"有什么问题？
2. 即使告警顺序正确，这个 `CostTracker` 作为 circuit breaker 还缺什么？
3. 写一个 `budget_level(total, budget)` 函数和一个 `guarded_route(query, tracker)`，实现讲义练习 5 的三级降级。

**Q12.** 讲义中有两处成本算术，请用计算验证并改正：

1. "A 1,500-token system prompt sent with every request costs **$3.75 per million requests** just for that prefix. At 100K requests per day, that is **$375/day**."（单价 $2.50 / 百万输入 token）
2. "A 2,000-token system prompt that costs **$0.005** normally costs **$0.000625** on cache hits. Over 100K requests, that saves **$437.50/day**."（Anthropic，命中折扣 90%）

---

## 四、面试高频题

**Q13.**（基础必考）一个 LLM 应用的账单主要由哪些部分构成？如果让你把成本降一半，你会按什么顺序上哪些手段？

**Q14.**（原理深挖）语义缓存的阈值怎么定？它最大的风险是什么？缓存键里除了查询文本还应该包含什么？缓存怎么失效？

**Q15.**（工程实践）在多实例部署的 API 服务里实现按用户的 token 限流，你会怎么做？本节的单机 `TokenBucketRateLimiter` 搬到生产会遇到哪些问题？

**Q16.**（场景设计）你负责一个多租户 SaaS 的 AI 助手，每个租户有月度预算。请设计成本控制方案：计量、归因、告警、降级、止损。

**Q17.**（追问型）你上线了模型路由，成本降了 60%。老板问："质量有没有掉？" 你怎么证明？路由器本身应该怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：C

每日输入：`10,000 × 10 × 1,000 / 1,000,000 × $2.50 = $250`；每日输出：`10,000 × 10 × 500 / 1,000,000 × $10 = $500`；合计 $750/天，× 30 = **$22,500/月**（已用 Python 计算验证）。A 是一天的费用；B 只算了输入（$250 × 30）；D 多乘了 10。注意输出 token 只有输入的一半，却贡献了 2/3 的成本——输出单价是输入的 4 倍。

（讲义开头写"GPT-5 costs $5 per million input tokens and $15 per million output"，但紧接着的算式用的是 $2.50/$10，即代码里 `gpt-4o` 的价格；讲义自己也说明"Prices below are illustrative"。）

### Q2 — 答案：A

讲义表格：Anthropic "Explicit cache_control markers | 90% on cache hits (pay 25% extra on write) | 1,024 tokens (Sonnet/Opus), 2,048 (Haiku) | 5 min default"；OpenAI "Automatic prefix matching | 50% on cache hits | 1,024 tokens"。B 把两家说反了；C 错，OpenAI 是 50%、Gemini 约 75%；D 是语义缓存的能力，provider caching 只认**完全相同的前缀**（讲义："Provider caching only works for identical prefixes"）。

### Q3 — 答案：D

```python
    def get(self, model, messages, temperature=0.0):
        if temperature > 0:
            self.misses += 1
            return None
```

temperature > 0 意味着同一输入每次输出可能不同，缓存"第一次的答案"会改变产品行为，所以直接跳过。演示输出 `With temp=0.7: MISS (non-deterministic, skip cache)` 印证了这一点。A 错，不会跨 temperature 复用；B 不会抛错；C 是一种可选设计，但本代码没有这样做（`put` 在 temperature > 0 时也直接 `return`）。副作用：这类请求也被计入 `misses`，会拉低 `hit_rate`，统计时最好单独记为 "bypass"。

### Q4 — 答案：B

两句切词后为 `[what, is, the, return, policy?]` 与 `[how, do, i, return, an, item?]`，唯一的公共词是 `return`，相似度 = `(1/√5)·(1/√6) = 1/√30 ≈ 0.1826`（已实际计算）。远低于 0.75，不命中。演示的 6 条查询全部 MISS，`hit_rate` 为 0.0。C 错，相似度不是 0（有公共词 `return`），但标点确实有影响：`"What is the return policy?"` 与 `"what is the return policy"`（去掉问号）的相似度只有 0.8，因为 `policy?` 和 `policy` 被当成两个词。A、D 是用真正的语义 embedding 才可能出现的数值。词袋向量只看字面重合，**根本不理解"语义"**，这正是讲义说生产要用 `text-embedding-3-small` 一类模型的原因。

### Q5 — 答案：D

```python
        if bucket["tokens"] < tokens_needed:
            deficit = tokens_needed - bucket["tokens"]
            wait = deficit / bucket["refill_rate"]
```

`deficit = 2000 − 500 = 1500`，`wait = 1500 / 500 = 3.0` 秒（已运行验证：`{'allowed': False, 'reason': 'token_limit', 'tokens_available': 500, 'retry_after_seconds': 3.0}`）。A 是用 2000/500 忘了减去已有的 500；B 是用 1500/1000；C 是每分钟请求数限制（`rate_limit`）时的重试上限，不是 token 限制。

### Q6 — 答案：B

`any(kw in q for kw in SIMPLE_KEYWORDS)` 用的是**子串**匹配。`"architecture"` 中含有 `"hi"`（arc-**hi**-tecture），于是第一条 `if` 就返回 simple，后面虽然同时命中 `"analyze"` 和 `"architect"` 两个复杂关键词，也没有机会被判断。A 错，这句有 8 个词；C 错，关键词表中没有 `"pros"`；D 错，pro 档的 complex 路由到 gpt-4o。同类误伤还有 `"this"`（含 hi）、`"monoliths"`（含 no）、`"something"`（含 hi），详见 Q10。

### Q7 — 答案：A

讲义："OpenAI's Batch API processes requests asynchronously at a 50% discount. You submit a batch of up to 50,000 requests, and results come back within 24 hours." 适用场景列了夜间文档处理、批量分类、评估跑批、数据增强；"Not for: real-time user-facing queries"。B、D 恰好相反（延迟是小时级）；C 混淆了 Batch 折扣与 prompt caching 折扣。

### Q8 — 答案：C

逐项计算（单价 $3 入 / $0.30 缓存入 / $15 出，每百万 token）：

| 项 | 无缓存 | 有缓存 |
|----|--------|--------|
| 未缓存输入 | 2000 × 3e-6 = $0.006000 | 500 × 3e-6 = $0.001500 |
| 缓存输入 | — | 1500 × 0.3e-6 = $0.000450 |
| 输出 | 500 × 15e-6 = $0.007500 | $0.007500 |
| 合计 | **$0.013500** | **$0.009450** |

节省 $0.00405，占 30.0%。输出 $0.0075 占无缓存成本的 55.6%，缓存对它毫无作用。A 错，0.30 正好是 3.00 的 10%，与"90% off"一致；B 错，折扣本身是 90%；D 错，缓存写入后几秒内即可命中。补充：代码**没有建模 25% 的写入溢价**——第一次调用实际为 `1500 × 3.75e-6 + 500 × 3e-6 + 500 × 15e-6 = $0.014625`，比不用缓存还贵，要靠后续命中摊回来。

### Q9 — 参考答案

1. **不会命中。** `get` 用的键是 `"gpt-4o"`，而 `put` 用的是 `route["model"]`（"Hello" 路由到 `gpt-4o-mini`）。`_hash` 把 model 放进了键里，两次哈希不同，所以永远查不到。已实际验证：`put('gpt-4o-mini', ...)` 之后 `get('gpt-4o', ...)` 返回 `None`。修复：要么先路由再查缓存（`get(route["model"], ...)`），要么让缓存键不含模型（若认为不同模型的答案可以互用）。前者更严谨。
2. 10 条查询两两都不完全相同，语义缓存又用词袋（相似度只有 0.0–0.26），所以缓存命中为 0；**67.3% 的节省全部来自模型路由**：优化前 10 次都用 gpt-4o，共 $0.029060；优化后 8 次走 gpt-4o-mini（每次约 $0.00017）、2 次走 claude-sonnet-4（$0.004044、$0.004086），共 $0.009516。延迟没有改善是因为 `simulate_llm_call` 的延迟只与输出 token 数有关（`200 + output_tokens × 2`），与模型无关，而且没有任何缓存命中能贡献 5 ms/15 ms 的快速返回。讲义"Before and After"表中 52% 命中率、P95 从 2,800ms 降到 900ms 的数字，本代码无法复现。
3. **永远是 0**（如果有命中的话）。`cache_savings` 用日志里的 `input_tokens`/`output_tokens` 重算"本该花的钱"，但命中时记录的是 `log_call("gpt-4o-mini", 0, 0, ...)`，token 为 0，算出来自然是 0。正确做法：命中时记录"若未命中会用的模型和预估 token 数"，或单独记一个 `avoided_cost` 字段。
4. **没有。** "After" 循环里没有调用 `rate_limiter`；`run_demo` 开头创建的 `tracker = CostTracker(monthly_budget=100.0)` 也从未使用。标题与实现不符。

### Q10 — 参考答案

1. 实际运行逐条检查（"命中"列为匹配到的关键词）：

| 查询 | 分类结果 | 被哪条规则判为 simple |
|------|---------|----------------------|
| Summarize this quarterly earnings report | simple | 恰好 5 个词；另外 `"this"` 含 `"hi"` |
| Analyze the trade-offs between microservices and monoliths | simple | `"monoliths"` 含 `"no"`（同时命中 analyze、trade-off） |
| Compare TCP vs UDP protocols | simple | 恰好 5 个词（同时命中 compare） |
| Analyze the pros and cons of serverless architecture | simple | `"architecture"` 含 `"hi"`（同时命中 analyze、architect） |
| How do I return something? | simple | 5 个词；`"something"` 含 `"hi"`（这条判 simple 本身没问题） |

2. 参考实现（已运行验证）：

```python
import re

def _has(q, keywords):
    return any(re.search(r"\b" + re.escape(k) + r"\b", q) for k in keywords)

def classify_complexity(query):
    q = query.lower()
    if _has(q, COMPLEX_KEYWORDS):           # 复杂优先：宁可多花钱，不要答错
        return "complex"
    if len(re.findall(r"[a-z0-9'-]+", q)) <= 5 or _has(q, SIMPLE_KEYWORDS):
        return "simple"
    return "medium"
```

3. **变低**：修复后 "Compare TCP vs UDP protocols" 与 "Analyze the pros and cons..." 被正确送往 gpt-4o，"优化后"总成本从 $0.009516 升到 $0.015053，节省比例从 67.3% 降到约 **48.2%**。说明原来的 67.3% 有相当一部分是**把复杂问题错误降级到小模型**换来的——账面省钱，实际可能是质量事故。任何"路由省了多少钱"的数字，都必须和"误路由率/质量指标"一起报告。
4. **价格倒挂**：`claude-sonnet-4` 是 $3/$15，比 `gpt-4o` 的 $2.50/$10 还贵，于是"中等"问题反而比"复杂"问题花钱多。在修复后的演示中，2 个 medium 查询花了 $0.00813，比 2 个 complex 查询（约 $0.00589）还多。路由表应保证档位越高价格（或能力）单调不降，或者明确说明 medium 用 Sonnet 是出于质量考虑。另外讲义 Tier 表写 Free 档 "GPT-4o-mini only"，而路由表给 free 的 simple 分配的是 `gpt-4.1-nano`，二者也不一致。

### Q11 — 参考答案

1. 第一次调用就花了 $0.0325，已是预算的 325%。`_check_budget` 用 `if / elif / elif`，**每次调用最多只追加一条告警**，且先检查最高级别：第 1 次加 stop，第 2 次 stop 已存在、进入 elif 加 throttle，第 3 次加 warning。于是告警顺序与严重度相反。文案用的是固定字符串 "95% consumed"，而 `${total:.2f}` 显示的是**当时的累计**（$0.03 → $0.07 → $0.10），实际比例是 325%、650%、975%，文案严重误导；同时 `:.2f` 把 $0.0325 显示成 $0.03，小额预算时精度不够。修复：从低到高逐级检查（不用 elif），所有已越过的阈值一次性补齐，文案写实际百分比。
2. 它**只记录、不拦截**：告警产生后，后续 `log_call` 照常记账，没有任何代码读 `alerts` 来改变路由或拒绝请求。真正的 circuit breaker 要在**调用之前**检查状态，并且需要按月重置、按租户隔离、持久化（进程重启不能清零）。
3. 参考实现：

```python
def budget_level(total, budget):
    pct = total / budget if budget > 0 else 1.0
    if pct >= 0.95: return "stop"
    if pct >= 0.85: return "throttle"
    if pct >= 0.70: return "warning"
    return "ok"

def guarded_route(query, tracker, semantic_cache):
    level = budget_level(tracker.total_cost(), tracker.monthly_budget)
    if level == "stop":
        hit = semantic_cache.get(query)
        return ("cache", hit["response"]) if hit else ("reject", "预算已用尽，请稍后再试")
    route = route_model(query)
    if level == "throttle":
        route["model"] = "gpt-4o-mini"          # 85% 以上：全部降到最便宜的模型
    if level == "warning":
        print("WARN: budget > 70%")             # 生产中应发到告警通道并去重
    return ("call", route["model"])
```

关键点：判断发生在调用前；stop 档仍可服务缓存（讲义："reject new requests, return cached responses only"）。

### Q12 — 参考答案

1. 每次请求的前缀成本 = `1500 / 1,000,000 × $2.50 = $0.00375`。所以是 **每千次请求 $3.75**，每百万次请求是 **$3,750**，"$3.75 per million requests" 少了 1000 倍。后半句 `100K × $0.00375 = $375/天`（月 $11,250）是对的，说明讲义只是把单位写错了。
2. 2,000 token × $2.50/百万 = $0.005（这是 gpt-4o 的价格；若按 Sonnet 的 $3 应为 $0.006）。打九折后应是 `$0.005 × 10% = $0.0005`，不是 $0.000625（$0.000625 相当于只打了 87.5% 的折扣）；100K 次节省应为 `(0.005 − 0.0005) × 100,000 = $450/天`，不是 $437.50。若再考虑每 5 分钟缓存过期后需要重新写入（+25%），实际节省会略低于 $450，但这不是讲义得出 $437.50 的算法。

结论：做成本估算时把"单价单位（每百万 token）× 每次 token 数 × 请求量"三段分开写，最不容易出错。

### Q13 — 参考回答要点

- **构成**：输入 token（system prompt + RAG 上下文 + 历史对话 + 用户消息 + 工具定义）、输出 token（单价最高）、embedding、向量库与基础设施。讲义："System prompts are the silent killer"。
- **先度量**：按模型/功能/用户记录 token 与成本，找出占比最大的那一块，不要盲目优化。
- **按投入产出比排序**（讲义优化栈）：
  1. Provider prompt caching：把稳定内容放在前面（system prompt、工具定义、固定文档），几乎零成本，讲义估 30–50%；
  2. 精确缓存（10–20%）与语义缓存（15–30%）：FAQ 类产品收益最大；
  3. 模型路由（40–70%）：大部分简单请求交给小模型；
  4. Prompt 压缩、限制 `max_tokens`、精简 RAG 上下文；
  5. 离线任务走 Batch API（五折）；
  6. 限流与 circuit breaker：不是省钱，而是防止 bug/滥用烧穿预算。
- 讲义估计 1–5 层叠加后可从 $22,500/月降到 $4,000–6,000/月。
- 加分点：说明各层收益**不是简单相加**（缓存命中的请求不再经过路由），要用真实流量回放测算；同时盯住质量指标。

### Q14 — 参考回答要点

- **阈值**：在真实查询对上标注"应该命中/不应命中"，画出精确率–召回率曲线来选。讲义建议 0.92–0.95；skill 文件给出分级：0.98+ 极保守、0.95 适合事实问答、0.90 激进、0.85 仅用于低风险场景。阈值与 embedding 模型强相关，换模型必须重调。
- **最大风险是误命中（false positive）**：例如 "How do I cancel my order?" 与 "How do I cancel my subscription?" 字面和语义都很像，答案却完全不同；否定、数字、实体名（"iPhone 15" vs "iPhone 16"）尤其危险。缓解：高阈值、命中后做轻量校验、分级返回（练习 3：0.98 直接返回、0.90 附"基于相似问题"提示）。
- **缓存键还应包含**：模型与 system prompt 版本、RAG 知识库版本、租户/用户权限范围（防止 A 用户的私有答案被 B 用户命中——这是安全问题）、语言、工具可用性。个性化或依赖实时数据的请求不应缓存。
- **失效**：TTL；数据源更新时按标签主动失效；prompt/模型升级时整体换命名空间；LRU/LFU 控制容量。
- 加分点：生产用向量索引（讲义：线性扫描只适合 <1,000 条，之后用 ANN）；指出本节词袋实现连同义改写都识别不了。

### Q15 — 参考回答要点

- **状态集中**：多实例时桶状态必须放在共享存储（Redis），否则每个实例各有一个桶，实际额度 = N × 实例数。
- **原子性**：本节是 `check` 和 `consume` 两步，并发下两个请求可能同时通过检查后各自扣减，导致超额。生产用 Redis Lua 脚本或 `INCRBY` + 过期时间在一次原子操作中"补充 + 判断 + 扣减"。
- **token 数事先未知**：输出 token 要调用结束才知道。常见做法是先按 `输入 token + max_tokens` **预留**，返回后按 `usage` 实际值**结算**多退少补；本节 `consume` 后桶可以变成负数，就是这个问题的体现。
- **多维度限制**：每分钟请求数（RPM）、每分钟 token 数（TPM）、每日/每月配额，以及全局对上游厂商的限额（避免把厂商的 429 传给所有用户）。
- **返回语义**：HTTP 429 + `Retry-After` 头；客户端指数退避加抖动。
- 本节实现的其他问题：`request_timestamps` 是列表，每次过滤 O(n)；`utilization` 用"累计使用 / 容量"计算，会超过 1，名字有误导；进程重启状态丢失。
- 加分点：比较 token bucket（允许突发）与滑动窗口（更平滑）、漏桶（恒定速率输出）的适用场景。

### Q16 — 参考回答要点

- **计量**：每次调用记录 tenant_id、user_id、feature、model、输入/缓存输入/输出 token、成本、延迟、缓存状态；成本在写日志时按当时价格计算并固化（价格会变）。
- **归因**：共享成本（system prompt 缓存写入、embedding、向量库）按用量分摊；做成按租户、按功能的看板。
- **告警**：70% 发通知给租户管理员和内部运营；预测型告警（讲义练习 2：用过去 7 天均值外推月度成本，超预算 20% 即告警，并考虑工作日/周末差异）。
- **降级**：85% 起把路由切到便宜模型、缩短 `max_tokens`、关闭高成本功能（如长上下文、多轮 agent）；95% 只返回缓存或明确拒绝，并提供"升级套餐/追加额度"入口。
- **止损**：单请求成本上限、单用户每分钟 token 上限、agent 迭代上限；全局 kill switch 防止 bug 造成的循环调用。
- **一致性**：预算状态集中存储、原子扣减；月初自动重置；所有降级行为要对用户透明。
- 常见误区：只做告警不做拦截（本节 `CostTracker` 就是这样）；只看总账不看单租户，导致一个大客户拖垮整体毛利。

### Q17 — 参考回答要点

- **离线评估**：准备覆盖各难度的标注集，比较"全部用大模型"与"路由后"的任务质量（准确率、LLM-as-judge 打分、人工抽检），同时统计路由器的混淆矩阵——尤其是"复杂被判为简单"的比例（Q10 显示关键词路由正是在这里出错）。
- **线上验证**：shadow 流量（小比例请求同时发给大模型对比）、A/B 测试看用户满意度、追问率、重新生成率、人工转接率。
- **路由器设计**：
  - 从关键词规则升级为 embedding 最近邻分类（讲义练习 4）或小模型分类器；
  - **级联（cascade）**：先用小模型回答，用置信度/自检/校验器判断，不合格再升级到大模型；
  - 不确定时偏向大模型（误判为复杂只是多花钱，误判为简单会答错）；
  - 路由表保证价格/能力单调（Q10 第 4 问的价格倒挂）。
- 加分点：能说出商业路由产品（讲义 Further Reading 中的 Martian、Not Diamond）的思路是"从你的流量中学习成本/质量权衡"；报告节省时同时报告质量变化。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 09 Function Calling 与工具使用](../../09-function-calling/docs/zh.md)：讲义声明的先修课；工具定义也是每次请求都重复计费的"固定前缀"。
- [阶段 11 · 04 Embeddings 与向量表示](../../04-embeddings/docs/zh.md)：语义缓存的核心就是 embedding + 余弦相似度。
- [阶段 11 · 05 Context Engineering](../../05-context-engineering/docs/zh.md)：上下文预算直接决定输入 token 成本。
- [阶段 10 · 12 Inference Optimization](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：理解 provider prompt caching 背后的 KV cache 复用。

### 本节被哪些后续内容用到
- [阶段 11 · 15 Prompt 缓存与上下文缓存](../../15-prompt-caching/docs/zh.md)：讲义明确指出本节讲应用层缓存，第 15 节深入 provider 层缓存，两者结合可省 50–95%。
- [阶段 11 · 13 构建生产环境中的 LLM 应用](../../13-production-app/docs/zh.md)：把缓存、限流、成本追踪组装进完整的生产流水线。
- [阶段 17 · 14 Prompt 缓存与语义缓存的经济性](../../../17-infrastructure-and-production/14-prompt-semantic-caching/docs/zh.md)：更深入的缓存经济学。
- [阶段 17 · 15 批处理 APIs](../../../17-infrastructure-and-production/15-batch-apis/docs/zh.md)：Batch API 五折的工程实践。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../../17-infrastructure-and-production/16-model-routing/docs/zh.md)、[阶段 13 · 21 LLM 路由层](../../../13-tools-and-protocols/21-llm-routing-layer/docs/zh.md)：生产级路由。
- [阶段 17 · 19 AI 网关](../../../17-infrastructure-and-production/19-ai-gateways/docs/zh.md)：把限流、缓存、计量放在网关层统一实现。
- [阶段 17 · 27 LLMs 的 FinOps](../../../17-infrastructure-and-production/27-finops-llms/docs/zh.md)：多租户成本归因与单位经济性。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：agent 场景下的预算与止损。

### 延伸关键词
`unit economics` · `prompt caching / cache_control` · `cached_tokens` · `semantic cache / GPTCache` · `ANN 向量索引` · `token bucket / sliding window / leaky bucket` · `RPM / TPM` · `429 + Retry-After` · `model routing / cascade` · `circuit breaker` · `Batch API` · `prompt compression` · `FinOps`
