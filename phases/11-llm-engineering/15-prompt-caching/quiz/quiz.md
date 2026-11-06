# 测验 · Prompt 缓存与上下文缓存（Prompt Caching and Context Caching）

> **阶段 11 · LLM 工程 · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Prompt caching 的机制 | 请求前缀与近期请求一致时，服务商直接复用上次算好的 KV cache，跳过对这段 token 的 prefill；首次写入付少量溢价，之后每次读取享受大幅折扣 |
| 2 | 只缓存前缀 | 三家都是**前缀匹配**：从第一个 token 到断点必须逐字节相同，第一个不同的 token 之后全部 miss |
| 3 | 缓存友好布局 | system prompt → 工具定义 → few-shot → 检索文档（若复用）→ 历史对话 → 当前用户消息；稳定的在上，易变的在下 |
| 4 | Anthropic 显式模式 | 在内容块上加 `cache_control: {"type": "ephemeral"}`；写入 1.25×、读取 0.1×；默认 TTL 5 分钟，可用 `"ttl": "1h"` 延长（写入 2×） |
| 5 | OpenAI 自动模式 | 无需配置，≥1,024 token 的匹配前缀自动打 5 折，无写入溢价；用 `usage.prompt_tokens_details.cached_tokens` 观察 |
| 6 | Gemini 显式 `CachedContent` | 缓存是一个命名对象，按 token·小时收存储费，读取约为正常价 25%；适合多天复用超大语料；讲义给出的最小可缓存量较高（Flash 4,096、Pro 32,768） |
| 7 | 盈亏平衡 | Anthropic 5 分钟：1 写 + 1 读平均 0.675×，1 写 + 10 读平均 0.205×；按讲义数字，**读 1 次就已回本**；1 小时 TTL 需读 2 次 |
| 8 | 可观测性 | 响应里的 `cache_creation_input_tokens` / `cache_read_input_tokens` 必须进 CI 断言和仪表盘；把 input token 拆成"缓存/非缓存"两列 |
| 9 | 常见 miss 原因 | 顶部动态时间戳、工具顺序变化、近似重复文本、块太小（<1,024 token）静默不缓存 |
| 10 | 与语义缓存的关系 | prompt caching 处理"token 完全相同"的复用，语义缓存处理"意思相同"的复用，二者叠加使用 |

### 核心技能（能动手做到）

- [ ] 给定一个 prompt（system、tools、few-shot、RAG、历史、用户消息），重排成缓存友好布局并标出唯一断点
- [ ] 用 1.25× / 0.1× / 2× 等倍率手算任意"写 1 次 + 读 n 次"的平均成本与盈亏平衡点
- [ ] 读懂 `main.py` 的三家模拟器，说清每一行成本是怎么累加出来的，并能复现 `$19.6838`、`$15.5325` 等输出
- [ ] 找出模拟器与真实计费的差异（TTL 是否在命中时刷新、最小 token 门槛、`misses` 恒为 0），并动手修正
- [ ] 为线上服务设计缓存命中率监控：CI 断言第二次相同请求 `cache_read_input_tokens > 0`，仪表盘按缓存/非缓存拆分
- [ ] 解释 prompt caching 为何能降低 TTFT（首 token 延迟）而基本不影响逐 token 解码速度

---

## 二、基础自测（选择题）

**Q1.** 按讲义与代码 `PRICES` 的设定，Anthropic 的缓存写入与缓存读取分别是基础输入价的多少倍？

- A. 写入 1.0×，读取 0.5×
- B. 写入 2.0×，读取 0.25×
- C. 写入 1.25×，读取 0.5×
- D. 写入 1.25×（5 分钟 TTL），读取 0.1×

**Q2.** 下面四种 prompt 布局，哪一种最有利于前缀缓存命中？

- A. system prompt → 工具定义 → few-shot 示例 → 历史对话 → 当前用户消息
- B. 当前时间戳 → system prompt → 工具定义 → few-shot 示例 → 当前用户消息
- C. system prompt → 当前用户消息 → 工具定义 → few-shot 示例
- D. system prompt → 本轮检索到的文档 → few-shot 示例 → 工具定义 → 当前用户消息

**Q3.** 只考虑一个被缓存的前缀块，Anthropic 5 分钟 TTL（写入 1.25×、读取 0.1×）。与"完全不缓存"相比，写入之后**至少需要被读取几次**才开始省钱？

- A. 0 次（写入本身就更便宜）
- B. 2 次
- C. 1 次
- D. 3 次

**Q4.** 运行 `main.py`，"Anthropic (5-min TTL)" 一行显示 `writes 21  reads 479`，而 1 小时 TTL 只有 `writes 3`。请求每 4 秒一个、3 个前缀轮换，同一前缀每 12 秒就会被用到一次。出现 21 次写入的原因是：

- A. 5 分钟 TTL 下 Anthropic 不支持 3 个以上的前缀
- B. 模拟器把 TTL 从**写入时刻**起算、命中时不刷新，约 2,000 秒的流量被切成 7 个 300 秒窗口，3 个前缀 × 7 = 21
- C. 15K token 的前缀超过了 5 分钟 TTL 的容量上限
- D. 5 分钟 TTL 的写入单价更低，所以模拟器故意多写几次

**Q5.** OpenAI 一行显示 `saves 48.4%`，略低于"缓存读取打 5 折"的 50%。最主要的原因是：

- A. 每个请求的 400 个后缀 token 不在缓存前缀内、仍按原价计费，再加上前 3 次写入按原价，理论上限约为 `15000/15400 × 50% ≈ 48.7%`
- B. OpenAI 的写入有 25% 溢价
- C. OpenAI 的 TTL 只有 5 分钟，中途过期了
- D. 模拟器对 OpenAI 计入了存储费

**Q6.** 在一个已经稳定命中的 Anthropic 缓存配置中，下列哪一项改动**不会**导致缓存 miss？

- A. 在 system prompt 第一行插入 `Current time: 2026-04-22 15:30:02`
- B. 部署时工具定义的顺序因为字典重排而改变
- C. 把 system prompt 里的 "You are helpful." 改为 "You are a helpful assistant."
- D. 只改变位于缓存断点之后的当前用户消息

**Q7.** 关于讲义中的 Gemini 显式上下文缓存（`CachedContent`），下列说法正确的是：

- A. 它与 OpenAI 一样是自动生效的，不需要创建任何对象
- B. 它没有存储费，只在读取时收费
- C. 按 token·小时收存储费、读取约为正常价的 25%；按讲义表格，Pro 模型最小可缓存 32,768 token，因此代码里 15K 的前缀在 Gemini Pro 上其实达不到缓存门槛
- D. 它的最小可缓存量与 Anthropic 相同，都是 1,024 token

**Q8.** 把 `main()` 中的 `seconds_between` 从 4 改为 100（其余不变），Anthropic 5 分钟 TTL 的结果最接近哪一项？

- A. 写 3 次、读 497 次，省约 87%
- B. 500 次全部是写入，成本约 $143.6，比不缓存（$115.5）还贵约 24%
- C. 写 21 次，与原结果相同
- D. 程序因 TTL 过期抛出异常

---

## 三、动手 / 代码题

**Q9.** 阅读 `simulate_anthropic` 的核心逻辑：

```python
    for i, r in enumerate(requests):
        now_seconds = i * seconds_between
        entry = cache.get(r.prefix_key)
        expired = entry is None or (now_seconds - entry.written_at) >= entry.ttl_seconds
        if expired:
            stats.writes += 1
            stats.input_cost += (r.prefix_tokens / 1000) * write_rate
            cache[r.prefix_key] = CacheEntry(tokens=r.prefix_tokens, written_at=now_seconds, ttl_seconds=ttl_seconds)
        else:
            stats.reads += 1
            stats.input_cost += (r.prefix_tokens / 1000) * p["cache_read"]
        stats.input_cost += (r.suffix_tokens / 1000) * p["base"]
```

Anthropic 的 5 分钟缓存在每次命中后会重新计时（滑动 TTL）。

1. 修改代码，让命中时刷新 TTL。
2. 修改后，默认场景（4 秒间隔）的 5 分钟 TTL 结果会变成多少次写入、多少成本、省多少？
3. 若把间隔改成 30 秒，原代码与修改后的写入次数分别是多少？这说明了什么？

**Q10.** 代码里的 `ProviderStats.misses` 在打印时永远是 0，而且模拟器从不检查最小可缓存长度。

1. 指出 `misses` 为什么恒为 0。
2. 给 `simulate_anthropic` 加一个 `min_tokens=1024` 参数：前缀不足门槛时，记一次 `miss`，整段（前缀 + 后缀）按基础价计费。
3. 用 `make_traffic(10, 1, 800, 100)`（10 个请求、单前缀 800 token）对比原代码和修改后的成本。

**Q11.** 手算验证：

1. 复现输出中 "Anthropic Claude Opus 4.7 (1-hour TTL)" 的 `input cost $15.5325`，写出三项组成。
2. 讲义开篇：15,000 token 的 system prompt、每次对话 20 轮、$3/M 输入价，单次对话仅 system prompt 就要 $0.90。若改用 Anthropic 5 分钟缓存（1 次写入 1.25× + 19 次读取 0.1×，假设轮次间隔都在 5 分钟内），单次对话这部分成本是多少？每天 10,000 次对话能从 $9,000 降到多少？

**Q12.** 讲义练习 2 / 3 都需要判断"两次请求之间有多长的前缀可以复用"。请补全函数 `common_prefix_len(a, b)`（输入两个 token 列表，返回从头开始相同的 token 数），并用它说明下面两种布局的差别：

```python
p1 = ["SYS"]*3 + ["t=15:30:01"] + ["TOOLS"]*5 + ["q1"]
p2 = ["SYS"]*3 + ["t=15:30:05"] + ["TOOLS"]*5 + ["q2"]

q1 = ["SYS"]*3 + ["TOOLS"]*5 + ["t=15:30:01", "q1"]
q2 = ["SYS"]*3 + ["TOOLS"]*5 + ["t=15:30:05", "q2"]
```

---

## 四、面试高频题

**Q13.**（基础必考）什么是 prompt caching？它在服务端缓存的到底是什么？为什么只能缓存"前缀"？

**Q14.**（原理深挖）为什么缓存命中能把首 token 延迟（TTFT）降低很多，却基本不改变后续每个 token 的生成速度（TPOT）？缓存的前缀为什么"重读比重算便宜得多"？

**Q15.**（工程实践）上线一个 agent 服务后，你如何保证并持续验证 prompt cache 真的在命中？列出你会做的工程措施。

**Q16.**（场景设计）一个多租户 RAG 客服：每个租户有约 8K token 的专属 system prompt + 产品手册，平均每租户每小时 200 次请求，但分布不均（有的租户 1 小时只有 2–3 次）。请设计缓存布局并选择 TTL / 提供商模式，给出成本推理。

**Q17.**（追问型）prompt caching 和语义缓存（semantic caching）有什么区别？能不能只用其中一个？各自有什么风险？

---

## 五、参考答案与解析

### Q1 — 答案：D

代码 `PRICES["anthropic_claude_opus_4_7"]`：`base 0.015`、`cache_write_5m 0.01875`（= 1.25×）、`cache_write_1h 0.030`（= 2×）、`cache_read 0.0015`（= 0.1×）。讲义："90% off input"、"25% surcharge"。A 是 OpenAI 的模式（无写入溢价、读 5 折）；B 混合了 Anthropic 1h 写入与 Gemini 读取比例；C 的读取倍率错。

### Q2 — 答案：A

前缀缓存要求"稳定在上、易变在下"。A 与讲义的缓存友好布局一致（历史对话可以缓存到上一轮为止，当前用户消息永不缓存）。B 把时间戳放在最顶部，每次请求第一个 token 就不同，全部 miss（讲义陷阱 1）。C 把每次都变的用户消息夹在中间，后面的工具和 few-shot 永远命中不了。D 把"本轮检索文档"（每次不同）放在 few-shot 和工具之前，讲义："interleave dynamic retrievals between few-shots — and the cache never hits"。

### Q3 — 答案：C

设读取 n 次。不缓存成本 `1 + n`；缓存成本 `1.25 + 0.1n`。`1.25 + 0.1n < 1 + n` ⇔ `n > 0.278`，所以 **n = 1** 即省钱：`1.35 < 2`，平均 0.675×，正是讲义给出的"saves 32%"。

注意：讲义原文写"a cached block has to be read at least twice to net-save money"，与它自己紧接着给出的"1 write + 1 read averages 0.675x (saves 32%)"矛盾——按讲义自己的倍率，读 1 次就已回本（B 是讲义原话的字面答案，但与算术不符）。讲义另给的经验法则"TTL 内预计复用 ≥ 3 次才缓存"是留足余量的工程建议。对比：1 小时 TTL（写入 2×）需要 `2 + 0.1n < 1 + n` ⇔ `n > 1.11`，即读 **2 次**才回本。A 错，写入本身比原价贵 25%。

### Q4 — 答案：B

请求时刻 `0, 4, 8, …, 1996` 秒。以 `prefix_0` 为例：0 秒写入；之后每 12 秒读一次，但 `written_at` 从未更新，到 `now - 0 >= 300` 的第一个时刻（300 秒）判定过期重写；如此在 0、300、…、1800 秒各写一次，共 7 次。三个前缀共 21 次。真实 Anthropic 的 5 分钟缓存在每次命中时都会刷新存活时间，按真实语义只会有 3 次写入（见 Q9）。A、C 都是凭空设定；D 把因果说反了，写入次数只由过期判断决定。

### Q5 — 答案：A

基线 `500 × 15.4K × $0.005/1K = $38.50`。缓存后：3 次写入 `3 × 15 × 0.005 = $0.225`；497 次读取 `497 × 15 × 0.0025 = $18.6375`；后缀 `500 × 0.4 × 0.005 = $1.00`；合计 $19.8625，节省 48.4%。即便全部命中，后缀 400 token 也不打折，上限 `15000/15400 × 0.5 ≈ 48.7%`。B 错，`PRICES` 中 OpenAI 的 `cache_write` 等于 `base`；C 错，模拟器给 OpenAI 的是 3600 秒；D 错，只有 Gemini 计存储费。

### Q6 — 答案：D

断点之后的内容本来就不参与前缀匹配，用户消息每次不同是常态。A：动态时间戳在最顶部，每次都 miss；B：工具定义属于缓存前缀，顺序变了 token 序列就变了（讲义："a dict reshuffle between deploys breaks every hit"）；C：近似重复文本，"one byte difference = full miss"。

### Q7 — 答案：C

讲义表格：Gemini 为"Explicit `CachedContent` API"、"Storage-billed; read at ~25% of normal"、"Storage fee per token·hour"、最小可缓存"4,096 tokens (Flash), 32,768 (Pro)"。代码模拟的是 "Gemini 3 Pro"，前缀只有 15,000 token，按讲义的门槛本不能缓存，但 `simulate_gemini` 没有任何门槛检查，照样按 25% 计读取价，因此 72.6% 的节省率在讲义自己的规则下并不成立。A 描述的是 OpenAI；B 与"storage-billed"矛盾；D 是 Anthropic Sonnet/Opus 的门槛。

### Q8 — 答案：B

间隔 100 秒时同一前缀每 `3 × 100 = 300` 秒出现一次，而过期判断是 `>= 300`，所以每次都"刚好过期"。结果（已实际运行）：`writes 500, reads 0`，成本 `500 × (15 × 0.01875 + 0.4 × 0.015) = $143.625`，比不缓存的 $115.5 贵约 24.4%。这说明：**请求间隔超过 TTL 时，缓存只会白付写入溢价**——这正是"TTL 内预计复用次数"必须先估算的原因。即使改成命中刷新 TTL（Q9），这个场景也不会变，因为根本没有命中。A 是修正后 4 秒间隔的结果；C 是原始输出；D 不会发生，模拟器没有抛异常的分支。

### Q9 — 参考答案

1. 在命中分支里刷新时间戳即可：

```python
        else:
            stats.reads += 1
            stats.input_cost += (r.prefix_tokens / 1000) * p["cache_read"]
            entry.written_at = now_seconds        # 命中即续期（滑动 TTL）
```

（`CacheEntry` 是普通可变 dataclass，可以直接改字段；更清晰的做法是把字段改名为 `last_used_at`。）

2. 已实际运行验证：默认场景下变为 **writes 3、reads 497**，成本 **$15.0263**，节省 **87.0%**；比原输出（21 次写入、$19.6838、83.0%）便宜约 $4.66，甚至比 1 小时 TTL（$15.5325）还便宜——因为同样只写 3 次，但写入单价是 1.25× 而不是 2×。
3. 间隔 30 秒时，同一前缀每 90 秒出现一次：原代码 **126 次写入**（成本 $46.85），修正后仍只有 **3 次写入**（$15.03）。说明"TTL 从何时起算"会让模拟结果相差数倍，用模拟器做选型（5m vs 1h）时必须先确认计费语义；在 Anthropic 滑动 TTL 语义下，只要同一前缀的请求间隔稳定小于 5 分钟，就没必要为 1 小时 TTL 付 2× 写入价。

### Q10 — 参考答案

1. `ProviderStats.misses` 默认值为 0，四个 `simulate_*` 函数中没有任何一处执行 `stats.misses += 1`。模拟器把"缓存未命中"全部记成了 `writes`（对 Anthropic/OpenAI 来说首访确实会写入缓存，这在语义上没错），但"不可缓存"的情形（块太小、未加 `cache_control` 等）根本没有建模，于是 `misses` 列永远是 0。
2. 参考实现（已运行验证）：

```python
def simulate_anthropic(requests, ttl_seconds, seconds_between, min_tokens=1024):
    p = PRICES["anthropic_claude_opus_4_7"]
    write_rate = p["cache_write_1h"] if ttl_seconds > 300 else p["cache_write_5m"]
    stats, cache = ProviderStats(), {}
    for i, r in enumerate(requests):
        now = i * seconds_between
        if r.prefix_tokens < min_tokens:                 # 不足门槛：静默不缓存
            stats.misses += 1
            stats.input_cost += (r.prefix_tokens + r.suffix_tokens) / 1000 * p["base"]
            continue
        entry = cache.get(r.prefix_key)
        if entry is None or now - entry.written_at >= entry.ttl_seconds:
            stats.writes += 1
            stats.input_cost += r.prefix_tokens / 1000 * write_rate
            cache[r.prefix_key] = CacheEntry(r.prefix_tokens, now, ttl_seconds)
        else:
            stats.reads += 1
            stats.input_cost += r.prefix_tokens / 1000 * p["cache_read"]
            entry.written_at = now                       # 顺带修正 Q9
        stats.input_cost += r.suffix_tokens / 1000 * p["base"]
    return stats
```

3. `make_traffic(10, 1, 800, 100)`：原代码给出 $0.0408（1 写 9 读），看起来省了约 70%；修正后 `misses 10`、成本 $0.135，与不缓存完全相同。讲义陷阱："Smaller blocks silently do not cache"——不检查门槛的模拟器会高估节省。Gemini 同理应加 `min_tokens=32768`（Pro）。

### Q11 — 参考答案

1. 1 小时 TTL：
   - 写入：`3 × 15 × $0.030 = $1.35`
   - 读取：`497 × 15 × $0.0015 = $11.1825`
   - 后缀：`500 × 0.4 × $0.015 = $3.00`
   - 合计 **$15.5325**。注意后缀 $3.00 占了约 19%，用户消息越长，缓存的相对收益越小。
2. 讲义开篇：`15,000 × 20 × $3/M = $0.90`。缓存后等效 token 倍数 `1.25 + 19 × 0.1 = 3.15`（相对于不缓存的 20），成本 `15,000 × 3.15 × $3/M ≈ $0.1418`，节省约 84.3%。每天 10,000 次对话：从 **$9,000** 降到约 **$1,418**（已用 Python 计算）。前提是相邻两轮间隔都在 5 分钟内；若用户中途离开超过 5 分钟，下一轮要重新写入。

### Q12 — 参考答案

```python
def common_prefix_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n
```

运行结果：`common_prefix_len(p1, p2) == 3`，`common_prefix_len(q1, q2) == 8`。

- p 布局：时间戳在第 4 个位置，两次请求只能共享前 3 个 token，工具定义全部 miss。
- q 布局：时间戳移到工具定义之后，能共享 8 个 token（system + 全部工具）。

推广到真实场景：把这个函数用在两次请求的**真实 token 序列**（用对应模型的 tokenizer 编码）上，就能在 CI 中断言"相邻两次请求的公共前缀 ≥ 断点位置"，提前发现动态字段漂进前缀的问题；这也是讲义练习 3"布局优化器"的核心子程序。

### Q13 — 参考回答要点

- **定义**：服务商把请求前缀经过 prefill 后得到的各层 **KV cache**（注意力中的 Key/Value 张量）保存在服务端；后续请求若前缀逐 token 相同，直接复用这些 K/V，只为新增 token 做计算。讲义："the provider serves the KV-cache from the previous run instead of re-encoding the tokens"。
- **为什么只能是前缀**：因果注意力下，第 i 个位置的 K/V 依赖于前面所有 token。只要前面某个 token 变了，它之后所有位置的 K/V 都会变，无法复用；而前缀相同的部分，K/V 完全确定，可以安全复用。
- **计费形态**：写入有溢价（Anthropic 1.25×），读取大幅折扣（Anthropic 0.1×、OpenAI 0.5×、Gemini 约 0.25× + 存储费）。
- 加分点：这与自托管推理引擎里的 prefix caching / RadixAttention 是同一个思想，只是商业 API 把它暴露成了计费项。

### Q14 — 参考回答要点

- **TTFT 主要由 prefill 决定**：首 token 出来前，模型要对整个输入做一次前向，长 prompt 时 prefill 是大矩阵乘，是算力瓶颈。缓存命中后，前缀部分的 prefill 被跳过，只需处理新增的几百个 token，所以 TTFT 大幅下降（讲义："first-token latency by 40–85%"）。
- **TPOT 由 decode 决定**：每生成一个 token 都要读一遍权重和整段 KV cache，瓶颈是显存带宽；无论 KV 是"算出来的"还是"从缓存读来的"，decode 时都要读同样多的 KV，因此逐 token 速度基本不变。讲义引用的 SARATHI 论文正是解释了这一点。
- **重读比重算便宜**：重算需要对每个前缀 token 做完整的 L 层前向（FLOPs 正比于 `参数量 × token 数`）；读取只是把已存的 K/V 从存储搬到 GPU 显存。讲义引用 Pope et al.（2022）："explains why a cached prefix is ~10× cheaper to reread than to recompute"。
- 常见误区：以为缓存能让"输出"变便宜——缓存只打折**输入** token，输出 token 价格不变。

### Q15 — 参考回答要点

- **CI 断言**：连续发两次相同前缀的请求，断言第二次 `cache_read_input_tokens > 0`（Anthropic）或 `cached_tokens > 0`（OpenAI）；讲义："if `cache_read_input_tokens` stays at zero across requests, your cache keys are drifting"。
- **确定性序列化**：工具列表按名字排序、JSON 用固定键序（`sort_keys=True`）、system prompt 用模板常量；禁止在断点以上出现时间戳、请求 ID、用户名等动态字段（讲义 skill："Refuse to ship a cache plan that places a dynamic field above the breakpoint"）。
- **仪表盘**：把输入 token 拆成"缓存读取 / 缓存写入 / 未缓存"三列，监控读取占比（讲义：预热后大多数 Anthropic 设置应 >80%）；否则"流量下降"会被误读为"缓存生效"。
- **发布门禁**：以命中率为部署 gate，命中率突降时告警（往往意味着有人改了 prompt 或工具顺序）。
- **门槛检查**：确认缓存块超过最小 token 数（Anthropic 1,024 / Haiku 2,048），否则静默不缓存。
- 加分点：对 prompt 做版本化（如 `rubric-v3`），每次改动都清楚地知道会导致一次全量重写。

### Q16 — 参考回答要点

- **布局**：`[公共 system 规则] → [工具定义] → [租户专属 system + 产品手册，约 8K] ‖ 断点 ‖ → [本轮检索片段] → [历史] → [用户消息]`。公共部分放最前，所有租户共享；租户部分紧随其后。
- **按流量分层选 TTL**：
  - 高频租户（每小时 200 次，平均 18 秒一次）：Anthropic 5 分钟 TTL 即可，命中会续期，几乎只写一次；
  - 低频租户（每小时 2–3 次，间隔 20–30 分钟）：5 分钟 TTL 每次都过期，等于每次付 1.25×，比不缓存还贵（参考 Q8）；可选 1 小时 TTL——写入 2×，只要 1 小时内再用 2 次就回本（Q3 的计算）；若连这都达不到，就**不缓存**租户部分，只缓存公共前缀。
- **提供商模式**：若用 OpenAI，自动缓存没有写入溢价，低频租户也不会亏，但只有 5 折；若是多天复用的超大手册，可考虑 Gemini `CachedContent`，但要注意存储费与讲义给出的最小门槛。
- **验证**：按租户统计命中率与"写入次数/读取次数"，定期重算盈亏。
- 加分点：把检索片段稳定排序（按文档 ID），让同一个问题的重复提问也能多命中一段前缀。

### Q17 — 参考回答要点

- **prompt caching**：服务端 KV 复用，要求 token 逐字节相同；不改变模型输出（仍然会真正生成回答），只降低输入成本和 TTFT。几乎没有正确性风险，主要风险是"以为命中其实没命中"。
- **语义缓存**：应用侧用 embedding 相似度判断"这个问题以前答过"，命中时**直接返回旧答案**，跳过模型调用；能省掉输入 + 输出全部成本和延迟。风险是误命中（相似但不同的问题拿到错误答案）、答案过时、跨用户泄露个性化内容。
- **能否只用一个**：可以，但互补。讲义："prompt caching handles *token-identical* reuse, semantic caching handles *meaning-identical* reuse"。agent 多轮对话里每轮的用户消息几乎都不同，语义缓存帮不上忙，但巨大的 system prompt 每轮相同，正是 prompt caching 的主场；FAQ 型客服则语义缓存收益更大。
- 加分点：语义缓存需要设阈值、按租户隔离、加 TTL 和失效策略；prompt caching 需要稳定布局。常见误区：把两者混为一谈，以为开了 prompt caching 就能"缓存回答"。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 01 Prompt Engineering：技术与模式](../../01-prompt-engineering/docs/zh.md)：prompt 由哪些部分组成，决定了能缓存什么。
- [阶段 11 · 05 Context Engineering: 窗口、 预算、 记忆和检索](../../05-context-engineering/docs/zh.md)：讲义："where to slice the prompt so the cache can land"。
- [阶段 11 · 11 缓存、请求速率限制与成本优化](../../11-caching-cost/docs/zh.md)：应用层缓存与语义缓存，与本节的 prompt caching 叠加使用。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：KV cache 与 prefill/decode 两阶段的基础。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：被"缓存"的到底是什么。

### 本节被哪些后续内容用到
- [阶段 11 · 16 Agent State Machines——图、节点与 Checkpoints](../../16-langgraph-state-machines/docs/zh.md)：多轮 agent 每一步都重发大段 system prompt，是 prompt caching 的主场。
- [阶段 17 · 06 前缀缓存服务：RadixAttention 与 KV 复用](../../../17-infrastructure-and-production/06-sglang-radixattention/docs/zh.md)：自托管引擎里的前缀缓存实现。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：prefill/decode 调度与 KV 管理。
- [阶段 17 · 14 Prompt 缓存与语义缓存的经济性](../../../17-infrastructure-and-production/14-prompt-semantic-caching/docs/zh.md)：在基础设施层面重新算账。
- [阶段 17 · 18 生产服务技术栈：KV 卸载与缓存感知路由](../../../17-infrastructure-and-production/18-vllm-production-stack-lmcache/docs/zh.md)：让请求路由到已有缓存的实例。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../../17-infrastructure-and-production/27-finops-llms/docs/zh.md)：把缓存/非缓存 token 拆分进成本归因。

### 延伸关键词
`cache_control` · `ephemeral` · `cache_creation_input_tokens` · `cache_read_input_tokens` · `cached_tokens` · `CachedContent` · `TTL` · `prefix caching` · `RadixAttention` · `TTFT / TPOT` · `prefill / decode` · `semantic cache` · `break-even`
