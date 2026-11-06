# 代码讲解 · caching_cost.py

> **所属小节**：阶段 11 · LLM 工程 · 第 11 节 缓存、请求速率限制与成本优化 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python caching_cost.py` ｜ **依赖**：仅标准库（`hashlib`、`time`、`json`、`math`；`dataclasses` 被导入但未使用）。不调用任何真实 API，所有 LLM 调用都是模拟的。

---

## 1. 这份代码在考察什么

这份代码把讲义"优化栈"中的五个组件各写成一个最小实现，再串成一条"优化前 vs 优化后"的演示流水线：

1. **成本计算**：`MODEL_PRICING` 价格表 + `calculate_cost`，把 token 数换算成美元，支持"部分输入命中 provider 缓存"。
2. **精确缓存**：`ExactCache` 用 SHA-256 哈希 `model + messages + temperature` 作为键。
3. **语义缓存**：`SemanticCache` 用相似度阈值匹配"意思相近"的历史查询（本实现用词袋向量代替真正的 embedding）。
4. **限流**：`TokenBucketRateLimiter` 同时做 token 桶和每分钟请求数限制。
5. **成本追踪与预算告警**：`CostTracker` 记账、按模型汇总、70/85/95% 三级告警。
6. **模型路由**：`classify_complexity` + `route_model` 用关键词规则选模型。

> 一句话：**把"每次 API 调用都是一笔金融交易"落成可以算账的代码**。同时这份代码有好几处 bug（缓存键不一致、子串匹配误路由、告警顺序颠倒），演示里的"省 67.3%"并不来自缓存——读懂这些问题比读懂正确的部分更有价值。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MODEL_PRICING` | 常量字典 | 13 个模型的输入/输出/缓存输入单价（美元/百万 token） | 成本构成 |
| `calculate_cost` | 函数 | 按未缓存输入、缓存输入、输出三段计费 | 单位经济学、provider caching |
| `ExactCache` | 类 | 哈希键 → 响应，带 TTL、容量上限、命中统计 | 精确缓存 |
| `simple_embed` / `cosine_similarity` | 函数 | 词频向量 + 归一化后的点积 | embedding 的玩具替代 |
| `SemanticCache` | 类 | 线性扫描找最相似的历史查询，超过阈值返回 | 语义缓存 |
| `TokenBucketRateLimiter` | 类 | 三档（free/pro/enterprise）token 桶 + RPM 限制 | 限流 |
| `CostTracker` | 类 | 记录每次调用、汇总、预算告警、缓存节省 | 成本追踪、circuit breaker |
| `SIMPLE_KEYWORDS` / `COMPLEX_KEYWORDS` / `classify_complexity` / `route_model` | 常量 + 函数 | 关键词分类 → 按档位查路由表 | 模型路由 |
| `simulate_llm_call` | 函数 | 按词数伪造 token 数与延迟 | 模拟调用 |
| `run_demo` | 函数 | 九段演示 | 串联全部组件 |

数据流（"优化后"流水线）：`查询 → ExactCache.get → SemanticCache.get → route_model → simulate_llm_call → CostTracker.log_call → 写回两级缓存`。

---

## 3. 逐段精讲

### 3.1 价格表与 `calculate_cost`

```python
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00, "cached_input": 1.25},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cached_input": 0.075},
    ...
    "claude-sonnet-4": {"input": 3.00, "output": 15.00, "cached_input": 0.30},
    ...
}

def calculate_cost(model, input_tokens, output_tokens, cached_input_tokens=0):
    if model not in MODEL_PRICING:
        return {"error": f"Unknown model: {model}"}
    pricing = MODEL_PRICING[model]
    non_cached = input_tokens - cached_input_tokens
    input_cost = (non_cached / 1_000_000) * pricing["input"]
    cached_cost = (cached_input_tokens / 1_000_000) * pricing["cached_input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total = input_cost + cached_cost + output_cost
```

- 单价单位是"美元 / 百万 token"，所以先 `/ 1_000_000` 再乘单价。
- `cached_input_tokens` 是 `input_tokens` 的**子集**：先减出未缓存部分按原价，缓存部分按 `cached_input` 价。
- 价格表里的折扣比例与讲义一致：OpenAI 系 `cached_input` 多为原价的 50%（如 gpt-4o 1.25/2.50）或 25%（gpt-4.1 系），Anthropic 系为 10%（Sonnet 0.30/3.00，即"命中省 90%"）。
- ⚠️ 只建模了"读缓存"的折扣，没有 Anthropic 的 **25% 写入溢价**，因此第一次写缓存那次调用被低估。
- ⚠️ 未知模型返回 `{"error": ...}` 而不是抛异常；调用方 `CostTracker.log_call` 直接取 `cost["total_cost"]`，会得到 `KeyError: 'total_cost'`（已实际验证）。"静默返回错误字典"在财务代码里尤其危险。
- 返回值逐项 `round(..., 6)`：精确到百万分之一美元，便于打印；累计大量调用时舍入误差会累积，生产中通常用整数（如"微美元"）或 `Decimal` 记账。

### 3.2 `ExactCache`：哈希 + TTL + 容量上限

```python
    def _hash(self, model, messages, temperature):
        key_data = json.dumps({"model": model, "messages": messages, "temperature": temperature}, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(self, model, messages, temperature=0.0):
        if temperature > 0:
            self.misses += 1
            return None
        key = self._hash(model, messages, temperature)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.ttl:
                self.hits += 1
                entry["access_count"] += 1
                return entry["response"]
            del self.cache[key]
        self.misses += 1
        return None
```

- **为什么序列化再哈希**：`messages` 是列表套字典，不可哈希，不能直接当 dict 的键。`json.dumps(..., sort_keys=True)` 把它变成**规范化字符串**（键顺序固定），再用 SHA-256 得到 64 位十六进制摘要作为键。
- **为什么 temperature > 0 不缓存**：非确定性输出缓存起来会改变产品行为（用户每次都拿到同一个"随机"答案）。讲义："only works for temperature=0 deterministic calls"。
- **惰性过期**：只有在 `get` 时才检查 TTL，过期就 `del`。没有被再次访问的过期条目会一直占着位置，直到被容量淘汰。
- `put` 的淘汰策略：

```python
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache, key=lambda k: self.cache[k]["timestamp"])
            del self.cache[oldest_key]
```

  这是 **FIFO**（按写入时间淘汰），不是 LRU——`access_count` 被维护了却从未用于淘汰。`min(...)` 每次 O(n) 扫描；生产用 `OrderedDict.move_to_end` 或 Redis 的 `maxmemory-policy allkeys-lru`。
- ⚠️ temperature > 0 的请求也计入 `misses`，会拉低统计出的命中率（演示里 3 次查询 1 次命中，`hit_rate: 0.3333`，其中一次 miss 其实是"绕过"）。

### 3.3 `simple_embed` 与 `cosine_similarity`：词袋"伪 embedding"

```python
def simple_embed(text):
    words = text.lower().split()
    vocab = {}
    for w in words:
        vocab[w] = vocab.get(w, 0) + 1
    norm = math.sqrt(sum(v * v for v in vocab.values()))
    if norm == 0:
        return {}
    return {k: v / norm for k, v in vocab.items()}

def cosine_similarity(a, b):
    if not a or not b:
        return 0.0
    all_keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in all_keys)
    return dot
```

- 向量用**稀疏字典**表示：键是词，值是归一化后的词频。
- 因为两边都已 L2 归一化，余弦相似度就等于点积，所以函数只算了 `dot`，没有再除以范数——这是正确的简化，但函数名容易让人误以为它能处理未归一化的向量。
- `set(a) | set(b)` 取并集其实没必要：只有交集上的项乘积非零，遍历 `a` 的键就够了。
- ⚠️ **它不懂语义**：只看字面词重合。演示中三对"同义问题"的相似度分别是 0.1826、0.2、0.2582（已实际计算），全部低于阈值 0.75。
- ⚠️ `split()` 不去标点：`"policy?"` 和 `"policy"` 是两个不同的词，`"What is the return policy?"` vs `"what is the return policy"` 只有 0.8。
- 讲义的生产版本用 `text-embedding-3-small` 得到稠密向量再算余弦；本实现只是为了"无依赖可运行"。

### 3.4 `SemanticCache`：线性扫描 + 阈值

```python
    def get(self, query):
        query_embedding = simple_embed(query)
        now = time.time()
        best_match = None
        best_sim = 0.0
        for entry in self.entries:
            if now - entry["timestamp"] > self.ttl:
                continue
            sim = cosine_similarity(query_embedding, entry["embedding"])
            if sim > best_sim:
                best_sim = sim
                best_match = entry
        if best_match and best_sim >= self.threshold:
            ...
            return {"response": ..., "similarity": round(best_sim, 4), "original_query": best_match["query"]}
```

- 对所有未过期条目算相似度，取**最大值**，再与阈值比较。O(n) 线性扫描，讲义："Linear scan works for <1,000 entries. Beyond that, use ANN"。
- 返回值除了答案，还带 `similarity` 和 `original_query`，便于日志审计"为什么命中"——这是个好习惯，误命中排查全靠它。
- 默认阈值 0.85，演示用 0.75；讲义建议 0.92–0.95。阈值与向量类型强相关，词袋向量的 0.75 与 OpenAI embedding 的 0.75 含义完全不同。
- ⚠️ 过期条目只被 `continue` 跳过，从不删除；`put` 满了时用 `sort` + `pop(0)` 淘汰最旧条目（O(n log n)），同样是 FIFO 而不是 LRU（讲义练习 1 要求改成 LRU）。
- ⚠️ 缓存键只有查询文本，没有模型、system prompt 版本、租户等维度——多租户场景下可能把 A 用户的答案返回给 B 用户。

### 3.5 `TokenBucketRateLimiter`：token 桶 + RPM

```python
        self.tiers = {
            "free": {"capacity": 50_000, "refill_rate": 500, "max_requests_per_min": 10},
            "pro": {"capacity": 500_000, "refill_rate": 5_000, "max_requests_per_min": 60},
            "enterprise": {"capacity": 5_000_000, "refill_rate": 50_000, "max_requests_per_min": 300},
        }

    def _refill(self, bucket):
        now = time.time()
        elapsed = now - bucket["last_refill"]
        refill = int(elapsed * bucket["refill_rate"])
        if refill > 0:
            bucket["tokens"] = min(bucket["capacity"], bucket["tokens"] + refill)
            bucket["last_refill"] = now
```

- **懒补充**：不用后台线程定时加 token，而是在每次 `check` 时按"距上次补充的时间 × 速率"一次性补上，`min` 封顶到容量。
- 只有 `refill > 0` 时才更新 `last_refill`：这样不足 1 个 token 的零头时间不会丢，会累积到下次。这个细节写对了。
- free 档容量 50,000、每秒补 500：从空到满需要 100 秒。
- `check` 的两道闸：

```python
        bucket["request_timestamps"] = [t for t in bucket["request_timestamps"] if now - t < 60]
        if len(bucket["request_timestamps"]) >= bucket["max_rpm"]:
            return {"allowed": False, "reason": "rate_limit", "retry_after_seconds": 60 - (now - bucket["request_timestamps"][0])}
        if bucket["tokens"] < tokens_needed:
            deficit = tokens_needed - bucket["tokens"]
            wait = deficit / bucket["refill_rate"]
            return {"allowed": False, "reason": "token_limit", ...}
```

  - RPM 用**滑动窗口日志**：保留最近 60 秒的时间戳，数量达到上限就拒绝，`retry_after` = 最早那条时间戳滑出窗口还要多久。
  - token 不足时，`retry_after = 缺口 / 补充速率`，例如缺 1,500、速率 500 → 3.0 秒（测验 Q5）。
- ⚠️ `check` 与 `consume` 分两步，不是原子操作，并发下可能超额；`consume` 不检查余额，桶可以变成负数。
- ⚠️ `get_usage` 的 `utilization = total_tokens_used / capacity`：累计使用量除以桶容量，长期运行会超过 1，名字有误导。
- ⚠️ 讲义表格写的是 "Daily Token Limit 50,000"，但 token 桶每秒补 500，一天最多可用约 4,320 万 token——token 桶限制的是**速率**，不是日配额，两者是不同的机制。
- ⚠️ `retry_after_seconds` 在 `rate_limit` 分支没有 `round`，会打印一长串小数。

### 3.6 `CostTracker`：记账、汇总、告警

```python
    def _check_budget(self):
        total = self.total_cost()
        pct = total / self.monthly_budget if self.monthly_budget > 0 else 0
        if pct >= 0.95 and not any(a["level"] == "stop" for a in self.alerts):
            self.alerts.append({"level": "stop", "message": f"Budget 95% consumed: ${total:.2f}/${self.monthly_budget:.2f}", ...})
        elif pct >= 0.85 and not any(a["level"] == "throttle" for a in self.alerts):
            ...
        elif pct >= 0.70 and not any(a["level"] == "warning" for a in self.alerts):
            ...
```

- 每次 `log_call` 后检查一次预算，每个级别只告警一次（`any(...)` 去重）。
- ⚠️ **`if/elif` 导致每次最多加一条告警，且从最高级开始**。演示里第一次调用就花了预算的 325%，于是第 1、2、3 次调用依次加上 stop、throttle、warning——顺序与严重度相反，文案"95% consumed: $0.03"也与实际 325% 不符（详见测验 Q11）。
- ⚠️ 只记录不拦截：没有任何代码读取 `alerts` 去改路由或拒绝请求，所以它是"告警器"而不是讲义所说的 circuit breaker。
- `total_cost()` 每次都对全部日志求和，`log_call` 又每次调用它，记录 n 条的总代价是 O(n²)；生产中维护一个累计值即可。

```python
    def cache_savings(self):
        cache_hits = [e for e in self.logs if e["cache_status"] == "hit"]
        ...
        for e in cache_hits:
            full_cost = calculate_cost(e["model"], e["input_tokens"], e["output_tokens"])
            saved += full_cost["total_cost"]
```

- 思路是"命中的请求如果真调用了要花多少钱"。⚠️ 但演示中命中时记录的 token 都是 0，算出来的节省永远是 0；应记录被避免调用的预估 token 与模型。
- `summary()` 汇总总调用数、总成本、平均成本、平均延迟、命中率、按模型拆分、预算余量——对应讲义"Cost Tracking"列出的字段（缺少"请求类别"）。

### 3.7 模型路由：关键词分类

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

- 三条规则：≤5 个词或命中简单关键词 → simple；命中复杂关键词 → complex；其他 → medium。
- ⚠️ **子串匹配**：`"hi"` 命中 `this`、`something`、`architecture`；`"no"` 命中 `monoliths`、`know`、`not`。
- ⚠️ **simple 先于 complex 判断**：一句话同时含 "analyze" 和 "architecture" 时，被 "hi" 抢先判为 simple。
- ⚠️ "≤5 个词就是简单"：`"Compare TCP vs UDP protocols"` 正好 5 个词，被判为 simple。
- 实际运行：路由演示 5 条中有 2 条明显误判（"Summarize this quarterly earnings report"、"Analyze the trade-offs..."），全流水线 10 条中 "Compare..." 与 "Analyze the pros and cons..." 也被降到 gpt-4o-mini。

```python
    routing_table = {
        "simple": {"free": "gpt-4.1-nano", "pro": "gpt-4o-mini", "enterprise": "gpt-4o-mini"},
        "medium": {"free": "gpt-4o-mini", "pro": "claude-sonnet-4", "enterprise": "claude-sonnet-4"},
        "complex": {"free": "gpt-4o-mini", "pro": "gpt-4o", "enterprise": "claude-opus-4"},
    }
    model = routing_table[complexity].get(tier, "gpt-4o-mini")
```

- 二维查表：先按复杂度、再按用户档位。未知档位兜底为 gpt-4o-mini。
- ⚠️ **价格倒挂**：pro 档 medium 用 Sonnet（$3/$15），比 complex 用的 gpt-4o（$2.50/$10）更贵。
- ⚠️ free 档 simple 用 `gpt-4.1-nano`，与讲义 Tier 表 "GPT-4o-mini only" 不一致。

### 3.8 `simulate_llm_call` 与 `run_demo`

```python
def simulate_llm_call(model, query):
    input_tokens = len(query.split()) * 4 + 500
    output_tokens = 150 + (len(query.split()) * 2)
    latency = 200 + (output_tokens * 2)
```

- 输入 = 500（模拟 system prompt）+ 每词 4 token；输出 = 150 + 每词 2 token；延迟只取决于输出 token 数，**与模型无关**——所以"优化后"延迟不可能因为换了小模型而下降。
- `run_demo` 的九段：价格表 → 10 万次请求成本对比 → Anthropic 缓存节省 → 精确缓存 → 语义缓存 → 限流 → 路由 → 优化前后对比 → 预算告警 → 按模型拆分。
- ⚠️ "优化后"流水线中 `exact_c.get("gpt-4o", ...)` 与 `exact_c.put(route["model"], ...)` 使用了**不同的模型名**，由于模型是哈希键的一部分，精确缓存永远不会命中（已用重复查询验证）。
- ⚠️ 标题写 "caching + routing + rate limiting"，但循环里没有调用限流器；开头创建的 `tracker` 也从未使用。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 价格写死在字典里 | 简单、可离线运行 | 价格经常变；生产从配置中心加载，日志里固化"当时单价" |
| `json.dumps(sort_keys=True)` + SHA-256 做键 | 规范化、定长、冲突概率可忽略 | 消息里若有时间戳等易变字段会导致永不命中，需先剔除 |
| 词袋向量代替 embedding | 无依赖、可解释 | 不懂语义，演示 0 命中；生产用 embedding 模型 + 向量索引 |
| 线性扫描语义缓存 | 代码短 | O(n)；生产用 Redis Vector / pgvector / ANN |
| FIFO 淘汰 | 实现容易 | 热点条目可能被淘汰；用 LRU/LFU |
| 懒补充的 token 桶 | 无需后台线程 | 单进程内存状态；生产用 Redis + Lua 原子脚本 |
| check / consume 分离 | 调用后才知道真实 token 数 | 有竞态；用"预留 + 结算" |
| 关键词路由 | 零成本、零延迟 | 子串误伤、规则脆弱；用 embedding 分类器或级联 |
| `if/elif` 三级告警 | 每级只告一次 | 跨级时顺序颠倒；应逐级检查，并真正拦截请求 |
| 模拟 LLM 调用 | 无需 API key | token/延迟公式与模型无关，"延迟改善"无法体现 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 数字下划线分隔 | `1_000_000`、`50_000` | 只是让大数字易读，等价于 `1000000` |
| 嵌套字典 | `MODEL_PRICING["gpt-4o"]["input"]` | 两层查表 |
| 默认参数 | `def calculate_cost(..., cached_input_tokens=0)` | 调用时可省略 |
| `json.dumps(..., sort_keys=True)` | `_hash` 中 | 序列化为字符串并固定键顺序，保证同内容同字符串 |
| `hashlib.sha256(...).hexdigest()` | `_hash` 中 | 对字节串求哈希，返回 64 位十六进制字符串；`.encode()` 把 str 转 bytes |
| `min(iterable, key=lambda ...)` | `min(self.cache, key=lambda k: self.cache[k]["timestamp"])` | 按自定义规则取最小元素；遍历字典得到的是键 |
| `dict.get(key, default)` | `vocab.get(w, 0) + 1`、`a.get(k, 0)` | 键不存在时返回默认值，常用于计数 |
| 字典推导式 | `{k: v / norm for k, v in vocab.items()}` | 一行生成新字典 |
| 集合并集 | `set(a) \| set(b)` | 两个字典键的并集 |
| 生成器表达式 | `sum(v * v for v in vocab.values())`、`any(kw in q for kw in SIMPLE_KEYWORDS)` | 不建中间列表，`any` 遇到第一个 True 就短路 |
| `in` 判断子串 | `kw in q` | 对字符串是**子串**判断，这正是 "hi" 误伤 "this" 的原因 |
| 列表推导式过滤 | `[t for t in bucket["request_timestamps"] if now - t < 60]` | 保留满足条件的元素 |
| `list.sort(key=...)` / `pop(0)` | `self.entries.sort(key=lambda e: e["timestamp"])` | 原地排序；`pop(0)` 删除并返回首元素（O(n)） |
| 条件表达式 | `round(...) if total > 0 else 0` | 三元运算，防止除零 |
| `del` | `del self.cache[key]` | 删除字典条目 |
| 切片 | `list(MODEL_PRICING.items())[:6]`、`query[:50]` | 取前 6 项 / 前 50 个字符 |
| `sorted(..., reverse=True)` | `sorted(breakdown.items(), key=lambda x: x[1]["cost"], reverse=True)` | 按成本降序排序，返回新列表 |
| f-string 格式符 | `{cost:.6f}`、`{data['input_tokens']:,}`、`{rate:.0%}`、`{x:.1f}` | 6 位小数、千分位、百分比（自动乘 100）、1 位小数 |
| f-string 内嵌条件 | `f"{'HIT' if result else 'MISS'}"` | 花括号里可以写表达式 |
| 字符串乘法 | `"=" * 60` | 重复 60 次画分隔线 |
| `time.time()` | 多处 | 当前 Unix 时间戳（秒，浮点数），用于 TTL 与限流 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示，被 import 时不执行 |
| 未使用的导入 | `from dataclasses import dataclass, field` | 导入了但没用，可删除 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时不到 1 秒，结果确定，无随机性）：

```text
--- Model Pricing ---
  gpt-4o: $0.007500 per 1K in + 500 out        ← 1000×2.5e-6 + 500×10e-6
  gpt-4o-mini: $0.000450 per 1K in + 500 out   ← 约为 gpt-4o 的 1/17
  ...
--- Cost Comparison: 100K Requests ---
  gpt-4o: $750.00
  gpt-4o-mini: $45.00
  claude-sonnet-4: $1050.00                    ← 比 gpt-4o 还贵 40%
  claude-haiku-3.5: $280.00

--- Anthropic Cache Savings ---
  Without cache: $0.013500
  With 1500 cached tokens: $0.009450
  Savings per call: $0.004050 (30.0%)          ← 输出占 55.6%，缓存只作用于输入

--- Exact Cache ---
  First lookup: MISS
  Second lookup: HIT -> You can return items within 30 days.
  With temp=0.7: MISS (non-deterministic, skip cache)
  Stats: {'hits': 1, 'misses': 2, 'hit_rate': 0.3333, 'cache_size': 1}

--- Semantic Cache ---
  'What is the return policy?' -> MISS (stored)
  'How do I return an item?' -> MISS (no match)      ← 相似度 0.1826
  'What are your store hours?' -> MISS (stored)
  'When does the store open?' -> MISS (no match)     ← 0.2
  'Tell me about quantum computing' -> MISS (stored)
  'Explain quantum mechanics' -> MISS (no match)     ← 0.2582
  Stats: {'hits': 0, 'misses': 6, 'hit_rate': 0.0, 'cache_size': 3}

--- Rate Limiting ---
  Request 1..5: OK
  Request 11: BLOCKED (rate_limit)               ← free 档每分钟 10 次
  Request 12: BLOCKED (rate_limit)
  Usage: {... 'tokens_remaining': 40000, ..., 'total_tokens_used': 10000, 'utilization': 0.2}

--- Model Routing ---
  'What time do you close?' -> gpt-4o-mini (simple)
  'Summarize this quarterly earnings report' -> gpt-4o-mini (simple)            ← 5 个词 + "this" 含 "hi"
  'Analyze the trade-offs between microservices and m' -> gpt-4o-mini (simple)  ← "monoliths" 含 "no"
  'Hello' -> gpt-4o-mini (simple)
  'Write code for a binary search tree with deletion' -> gpt-4o (complex)

--- Full Pipeline: Before vs After Optimization ---
  [Before] Total cost: $0.029060  Avg latency: 520.8ms
  [After]  Total cost: $0.009516  Avg latency: 520.8ms  Cache hit rate: 0%
  SAVINGS: 67.3% cost reduction
  Latency improvement: 0.0% faster

--- Budget Alerts Demo ---
  Total spent: $0.162500 / $0.01
  ALERT [STOP]: Budget 95% consumed: $0.03/$0.01      ← 顺序颠倒
  ALERT [THROTTLE]: Budget 85% consumed: $0.07/$0.01
  ALERT [WARNING]: Budget 70% consumed: $0.10/$0.01

--- Cost Breakdown by Model ---
  claude-opus-4: 10 calls, $1.200000, 30,000 in / 10,000 out
  claude-sonnet-4: 30 calls, $0.360000, 45,000 in / 15,000 out
  gpt-4o: 10 calls, $0.130000, 20,000 in / 8,000 out
  gpt-4o-mini: 50 calls, $0.012000, 40,000 in / 10,000 out
  Total: $1.702000
```

逐项解读：

- **价格对比**：同样 10 万次请求，gpt-4o-mini $45、gpt-4o $750，差 16.7 倍——这就是路由能省钱的根本原因。
- **Anthropic 缓存 30%**：不是 90%，因为 25% 的输入没缓存、输出全价（测验 Q8）。
- **精确缓存**：第二次查询命中；temperature = 0.7 的查询被绕过但计入 miss，所以命中率显示 33%。
- **语义缓存 0 命中**：词袋向量只看字面重合，同义改写全部失败。这段演示其实证明了"语义缓存需要真正的语义 embedding"。
- **限流**：前 10 次放行、第 11、12 次因 RPM 被拒；token 还剩 40,000（10 次 × 1,000），因为运行太快，补充的 token 不足 1 个，被 `int()` 截断为 0。
- **优化前后 67.3%**：缓存命中为 0，节省**全部来自路由**；而路由又包含误判——用修复后的分类器重算（复杂问题正确送往 gpt-4o），节省降到约 48.2%（测验 Q10）。延迟不变是因为模拟延迟与模型无关。
- **预算告警**：每次调用 $0.0325，第一次就超过预算 3 倍；`if/elif` 让告警按 stop → throttle → warning 倒序出现。
- **按模型拆分**：10 次 Opus 调用花了 $1.20，占总额 70.5%；50 次 mini 只占 0.7%——"少数贵调用决定账单"，这是做成本归因的意义。

---

## 7. 动手改一改

1. **修复精确缓存键**：在"优化后"循环里先 `route = route_model(q)`，再用 `exact_c.get(route["model"], ...)`；把 `queries` 里的 "Hello" 复制一份，确认第二次 `Cache hit rate` 不再是 0%。
2. **修复路由分类器**：改为整词匹配（`re.search(r"\b...\b")`）并让 complex 优先判断；重跑后对比节省比例从 67.3% 变成多少，并解释为什么"修 bug 反而省得少了"。
3. **替换为真实 embedding**（讲义 Use It 部分）：用 `sentence-transformers` 或 OpenAI embedding 替换 `simple_embed`，阈值设 0.92，看看演示中的三对同义问题能否命中；再构造一对"字面像但意思不同"的问题测试误命中。
4. **讲义练习 1：LRU 淘汰**：给每个条目加 `last_access`，满了淘汰最久未访问的；或改用 `collections.OrderedDict`。用 100 条带热点的查询对比 FIFO 与 LRU 的命中率。
5. **讲义练习 5：真正的 circuit breaker**：先修复 `_check_budget`（逐级检查、文案写实际百分比），再写一个调用前检查的 `guarded_route`：85% 以上一律 gpt-4o-mini，95% 以上只返回缓存，用 $1.00 预算模拟 1,000 次请求验证三个阈值依次触发。
6. **进阶：预留—结算式限流**：调用前按 `input_tokens + max_tokens` 预留，返回后按实际 `output_tokens` 退还差额；再用 `threading` 起 20 个并发请求，观察原来的 check/consume 两步法是否会超额。

---

## 8. 常见坑

- **缓存键不一致**：查和写用了不同的字段（本例的模型名），缓存"看起来在工作"但永远不命中。上线前一定要用重复请求测命中率。
- **用子串匹配做关键词分类**：`"hi" in "this"` 为真。用正则 `\b` 或先分词再比较。
- **只算缓存折扣、忘了写入溢价**：Anthropic 写缓存要多付 25%，缓存 5 分钟过期，低频调用的 prompt 用缓存可能反而更贵。
- **把"缓存折扣 90%"当成"整体省 90%"**：折扣只作用于被缓存的输入部分，输出 token 往往才是大头。
- **语义缓存阈值拍脑袋**：不同 embedding 模型的相似度分布差别很大，阈值必须在标注数据上调；误命中是正确性事故，不只是成本问题。
- **语义缓存不分租户**：可能把一个用户的私有信息返回给另一个用户。
- **告警不拦截**：只发告警的"熔断器"挡不住一个死循环的 agent。
- **单机内存限流**：多实例部署时每个实例各有一个桶，实际额度被放大；进程重启状态清零。
- **报告节省不报告质量**：路由把复杂问题降级到小模型最省钱，也最容易出事故。
