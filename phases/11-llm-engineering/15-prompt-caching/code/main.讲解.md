# 代码讲解 · main.py

> **所属小节**：阶段 11 · LLM 工程 · 第 15 节 Prompt 缓存与上下文缓存 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`typing`），不调用任何真实 API，不需要 API key 和网络

---

## 1. 这份代码在考察什么

讲义 Build It 的步骤 1–4 演示了三家 API 的真实调用方式，但那些代码需要 API key 才能跑。`main.py` 是讲义步骤 5 提到的"三家提供商记账器"（"a simulated three-provider accountant"）：不发请求，只用**计费规则**模拟一段流量，算出每种缓存模式的写入次数、读取次数和总成本。它考察的是：

1. **前缀缓存的计费模型**：写入（write）付溢价、读取（read）打折、过期后重新写入。
2. **TTL 的作用**：同样的流量，5 分钟 TTL 和 1 小时 TTL 的写入次数差多少、成本差多少。
3. **三家的定价差异**：Anthropic 显式（1.25× 写 / 0.1× 读）、OpenAI 自动（无溢价 / 0.5× 读）、Gemini 显式（0.25× 读 + 存储费）。
4. **节省率的上限**：后缀（用户消息）永远按原价计费，所以节省率不可能达到折扣率本身。

> 一句话：**把"缓存能省多少钱"变成一个可以改参数、可以复算的小账本**。同时要看清它和真实计费的几处出入——TTL 不随命中刷新、没有最小 token 门槛、`misses` 恒为 0——这些出入恰好会让结论偏离现实。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PRICES` | 模块级常量（嵌套 dict） | 三家每 1K 输入 token 的基础价、写入价、读取价、存储价 | 计费倍率 |
| `Request` | dataclass | 一个请求：前缀 token 数、后缀 token 数、前缀 key | 可缓存前缀 vs 用户输入 |
| `CacheEntry` | dataclass | 缓存条目：token 数、写入时刻、TTL | 服务端缓存对象 |
| `ProviderStats` | dataclass + `@property` | 累计 writes/reads/misses 与输入成本、存储成本 | 计费账本 |
| `simulate_anthropic` | 函数 | 按 TTL 模拟显式缓存，5m/1h 选择不同写入价 | `cache_control` + `ttl` |
| `simulate_openai` | 函数 | 固定 3600 秒 TTL、无写入溢价 | 自动缓存 |
| `simulate_gemini` | 函数 | 同上逻辑 + 结束后按 token·小时计存储费 | `CachedContent` |
| `baseline_cost` | 函数 | 不缓存时的成本（全部按基础价） | 对照组 |
| `make_traffic` | 函数 | 生成 n 个请求，前缀 key 轮换 | 流量模型 |
| `print_report` | 函数 | 打印一家的账单与节省率 | 报表 |
| `main` | 函数 | 500 请求、3 个前缀、每个 15K token、4 秒一个，跑 4 种配置 | 场景 |

数据流：`make_traffic` 生成请求列表 → 四个 `simulate_*` 各自遍历一遍、按"命中 / 过期"累加成本 → `baseline_cost` 算对照 → `print_report` 输出节省率与每 1K 请求成本。

---

## 3. 逐段精讲

### 3.1 价格表 `PRICES`

```python
PRICES = {
    "anthropic_claude_opus_4_7": {"base": 0.015, "cache_write_5m": 0.01875, "cache_write_1h": 0.030, "cache_read": 0.0015},
    "openai_gpt_5": {"base": 0.005, "cache_write": 0.005, "cache_read": 0.0025},
    "gemini_3_pro": {"base": 0.00125, "cache_write": 0.00125, "cache_read": 0.0003125, "storage_per_1k_per_hour": 0.0000125},
}
```

单位是"美元 / 1K token"。把它们换算成倍率更好理解：

| 提供商 | 写入 / 基础 | 读取 / 基础 | 其它 |
|-------|------------|------------|------|
| Anthropic | 1.25×（5m）、2.0×（1h） | 0.1× | — |
| OpenAI | 1.0×（无溢价） | 0.5× | — |
| Gemini | 1.0× | 0.25× | 存储 `$0.0000125 / 1K / 小时` |

- 这些倍率与讲义表格一致（"90% off input / 25% surcharge"、"50% off"、"read at ~25% of normal"、1h TTL "costs 2x the write premium"）。
- 绝对价格是代码作者设定的示例值（文件头注释称是"April 2026 published rates"），讲义开篇用的是 $3/M 的价格。做选型时应以各家官方价目为准，代码也提示"Override by editing PRICES"。
- ⚠️ Gemini 的存储单价在这里非常小（每百万 token·小时仅 $0.0125），导致本场景存储费只有 $0.0006，几乎可以忽略。若把存储单价提高 360 倍（$4.5/M·h 量级），本场景存储费也只有约 $0.20，结论不变；但对"多天保留巨型语料"的场景，存储费会成为主要成本，务必按真实价目代入。

### 3.2 三个 dataclass

```python
@dataclass
class Request:
    prefix_tokens: int
    suffix_tokens: int
    prefix_key: str

@dataclass
class CacheEntry:
    tokens: int
    written_at: int  # request index
    ttl_seconds: int

@dataclass
class ProviderStats:
    writes: int = 0
    reads: int = 0
    misses: int = 0
    input_cost: float = 0.0
    storage_cost: float = 0.0

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.storage_cost
```

- `Request` 把一个请求抽象成"可缓存前缀 + 不可缓存后缀"，正对应讲义布局里断点上下两部分。`prefix_key` 代表"前缀的内容身份"：真实系统里相当于前缀 token 序列的哈希，两个请求 key 相同就意味着前缀逐字节相同。
- `CacheEntry.written_at` 的注释写的是"request index"，但实际存的是**秒数**（`now_seconds`），注释有误。
- `ProviderStats.total_cost` 用 `@property` 做成只读计算属性，调用时不加括号：`stats.total_cost`。
- ⚠️ `misses` 字段在整个文件里从未被加 1，所以报表中 `misses` 列恒为 0（见 3.6 与测验 Q10）。

### 3.3 `simulate_anthropic`：显式缓存 + TTL

```python
def simulate_anthropic(requests: Iterable[Request], ttl_seconds: int, seconds_between: int) -> ProviderStats:
    p = PRICES["anthropic_claude_opus_4_7"]
    write_rate = p["cache_write_1h"] if ttl_seconds > 300 else p["cache_write_5m"]
    stats = ProviderStats()
    cache: dict[str, CacheEntry] = {}
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
    return stats
```

逐行看：

- **写入价的选择**：`ttl_seconds > 300` 就用 1h 价。Anthropic 只提供 5m 和 1h 两档，所以这个二分判断足够；但如果有人传 `ttl_seconds=600`，会按 1h 价收费却只活 10 分钟，属于不合法输入。
- **时间轴**：`now_seconds = i * seconds_between`，请求严格等间隔到达。真实流量有突发和空闲，这是最大的简化之一。
- **过期判断**：`entry is None`（从没写过）或"距写入已过 ≥ TTL"。利用 `or` 的短路：`entry` 为 `None` 时不会去访问 `entry.written_at`，所以不会抛 `AttributeError`。
- **三项成本**：过期 → 前缀按写入价；命中 → 前缀按读取价；无论如何 → 后缀按基础价。

⚠️ **最关键的偏差：TTL 不随命中刷新。** 命中分支没有更新 `written_at`，于是缓存在"写入后 300 秒"必然过期，哪怕这 300 秒里被读了 25 次。Anthropic 的 5 分钟缓存在每次命中后会重新计时（滑动 TTL）。默认场景下：

| 计时语义 | 写入次数 | 成本 | 节省 |
|---------|---------|------|------|
| 代码（从写入起算） | 21 | $19.6838 | 83.0% |
| 滑动 TTL（命中续期） | 3 | $15.0263 | 87.0% |

两者差 $4.66；按代码的结果，你会得出"1 小时 TTL 更划算"的结论（$15.53 < $19.68），而按滑动语义，5 分钟 TTL 反而更便宜（$15.03 < $15.53），因为同样只写 3 次、写入单价却低。修正只需在 `else` 分支加一行 `entry.written_at = now_seconds`（测验 Q9）。

### 3.4 `simulate_openai`：自动缓存

```python
        expired = entry is None or (now_seconds - entry.written_at) >= 3600
        if expired:
            stats.writes += 1
            stats.input_cost += (r.prefix_tokens / 1000) * p["cache_write"]
```

- 与 Anthropic 版几乎一样，只是 TTL 硬编码为 3600 秒，写入价等于基础价（无溢价）。
- 讲义说 OpenAI 的 TTL 是 "Up to 1 hour (best-effort)"——"尽力而为、最长 1 小时"。代码把它建模成"确定活满 1 小时"，属于**乐观假设**；真实环境下低频前缀可能更早被驱逐。
- 因为写入没有溢价，OpenAI 模式**永远不会比不缓存更贵**，最坏情况就是等于原价——这是自动缓存"零风险"的根源。

### 3.5 `simulate_gemini`：显式缓存 + 存储费

```python
    # Storage cost: each entry lives for ttl, billed per token-hour
    for entry in cache.values():
        hours = entry.ttl_seconds / 3600
        stats.storage_cost += (entry.tokens / 1000) * p["storage_per_1k_per_hour"] * hours
```

- 遍历结束后，对 `cache` 里**最终剩下的**每个条目按"token 数 × 存储单价 × TTL 小时数"计费。本场景 3 个条目 × 15K × 1 小时：`3 × 15 × 0.0000125 × 1 = $0.0005625`，打印为 `$0.0006`。
- ⚠️ 两处简化：
  1. 如果某个前缀中途过期被重写，旧条目在 `cache[...] = ...` 时被覆盖，它那段时间的存储费就**丢了**；
  2. 每个条目都按**完整 TTL** 计费，即使流量在 TTL 中途就结束了（本场景总时长约 2,000 秒，不到 1 小时，却按 1 小时收费）。
- ⚠️ 与讲义不一致：讲义表格写明 Gemini Pro 最小可缓存 **32,768** token，而 `main` 里的前缀只有 15,000 token，按讲义规则根本建不了缓存，但模拟器没有门槛检查，照样给出 72.6% 的节省率。

### 3.6 `baseline_cost` 与 `make_traffic`

```python
def baseline_cost(requests: list[Request], provider: str) -> float:
    p = PRICES[provider]
    return sum((r.prefix_tokens + r.suffix_tokens) / 1000 * p["base"] for r in requests)

def make_traffic(n_requests: int, n_prefixes: int, prefix_size: int, suffix_size: int) -> list[Request]:
    return [
        Request(prefix_tokens=prefix_size, suffix_tokens=suffix_size, prefix_key=f"prefix_{i % n_prefixes}")
        for i in range(n_requests)
    ]
```

- 基线：每个请求 15.4K token 全按原价。Anthropic `500 × 15.4 × 0.015 = $115.50`，OpenAI $38.50，Gemini $9.625。
- 流量：`i % n_prefixes` 让 3 个前缀按 0,1,2,0,1,2… 轮换，同一前缀每 `3 × 4 = 12` 秒出现一次。可以把它想成"3 个不同的 agent（或 3 个租户）交替请求"。
- 由于所有请求的前缀和后缀长度完全一样，`misses` 的另一种来源（前缀太短）也不会出现。

### 3.7 `print_report` 与 `main`

```python
    savings = 1 - (stats.total_cost / baseline) if baseline > 0 else 0
    ...
    print(f"  per 1K req  ${stats.total_cost * 1000 / n:>7.4f}")
```

- 节省率 = `1 − 缓存成本 / 不缓存成本`；`if baseline > 0 else 0` 防止除零（条件表达式）。
- "per 1K req" 把总成本折算成每 1,000 个请求的成本，方便与流量规模相乘做预算。
- `if stats.storage_cost:` 只有 Gemini 会打印存储行（0.0 在布尔上下文中为假）。
- `main` 里 `print(f"Scenario: ...\n")` 的 f-string 没有任何占位符，这里写成普通字符串即可；场景描述也是硬编码的，改了参数要记得同步修改这行文字。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不调真实 API，只模拟计费 | 无需 key、秒级跑完、结果可复现 | 没有真实的命中/驱逐行为；生产中应读响应里的 `cache_read_input_tokens` 等字段统计 |
| 用 `prefix_key` 字符串代表前缀身份 | 简单直观 | 真实系统以 token 序列逐字节比较；可以对前缀做哈希来模拟 |
| 请求等间隔到达 | 时间轴好算 | 真实流量有突发与空窗，命中率需要用真实请求日志回放（讲义练习 2） |
| TTL 从写入时刻起算 | 实现最简单 | 与 Anthropic 的滑动 TTL 不符，默认场景多算 18 次写入，并可能导致 5m/1h 选型结论反转 |
| 不检查最小可缓存长度 | 场景里前缀够长（对 Anthropic/OpenAI 而言） | Gemini Pro 门槛 32,768 > 15,000；小前缀会被高估节省（测验 Q10） |
| `misses` 字段保留但不使用 | 预留扩展 | 报表上永远显示 0，易误导 |
| 存储费按最终条目 × 完整 TTL | 简单 | 漏算被覆盖条目、多算未用满的时长；本场景金额很小，影响不大 |
| 只算输入 token | 缓存只影响输入价 | 输出 token 成本往往不可忽略，算总账时要另加 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，旧版本 Python 也能写 `dict[str, CacheEntry]` 这类新式注解 |
| 模块文档字符串 | 文件开头的 `"""Prompt caching accountant. ..."""` | 用 `help(main)` 或 `main.__doc__` 能看到 |
| `@dataclass` | `class Request:` / `class ProviderStats:` | 自动生成 `__init__`、`__repr__`、`__eq__`；字段默认值 `writes: int = 0` |
| `@property` | `def total_cost(self) -> float` | 把方法伪装成属性，`stats.total_cost` 不加括号 |
| 类型注解 | `requests: Iterable[Request]`、`-> ProviderStats`、`cache: dict[str, CacheEntry] = {}` | 只是提示，运行时不检查；`Iterable` 来自 `typing` |
| 嵌套字典 | `PRICES["openai_gpt_5"]["cache_read"]` | 两级查表 |
| 条件表达式 | `p["cache_write_1h"] if ttl_seconds > 300 else p["cache_write_5m"]` | 一行内的 if/else |
| `dict.get` | `cache.get(r.prefix_key)` | key 不存在时返回 `None` 而不是抛 `KeyError` |
| 短路求值 | `entry is None or (now_seconds - entry.written_at) >= ...` | 左边为真时右边不执行，避免访问 `None` 的属性 |
| `enumerate` | `for i, r in enumerate(requests)` | 同时拿到下标和元素 |
| 增量赋值 | `stats.writes += 1`、`stats.input_cost += ...` | 原地累加 |
| `dict.values()` | `for entry in cache.values()` | 只遍历值 |
| 生成器表达式 + `sum` | `sum((...) / 1000 * p["base"] for r in requests)` | 不建中间列表，边算边加 |
| 列表推导式 | `[Request(...) for i in range(n_requests)]` | 批量构造对象 |
| 取模轮换 | `f"prefix_{i % n_prefixes}"` | 让 key 在 0..n−1 间循环 |
| 关键字参数 | `make_traffic(n_requests=500, n_prefixes=3, ...)` | 调用时写出参数名，可读性高 |
| f-string 格式符 | `{stats.writes:>5}`、`{stats.input_cost:>7.4f}`、`{savings*100:>5.1f}` | `>` 右对齐、宽度、保留小数位；表达式可以直接写在花括号里 |
| 真值测试 | `if stats.storage_cost:` | `0.0` 为假，非零为真 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行（测验里正是 import 它来做实验） |

---

## 6. 运行结果解读

实际运行（Python 3，`cd code && python3 main.py`，瞬时完成）：

```text
Scenario: 500 requests, 3 rotating prefixes (15K tok each), 4s apart


Anthropic Claude Opus 4.7 (5-min TTL)
  writes    21  reads   479  misses     0
  input cost  $19.6838
  vs no-cache $115.5000  ->  saves  83.0%
  per 1K req  $39.3675

Anthropic Claude Opus 4.7 (1-hour TTL)
  writes     3  reads   497  misses     0
  input cost  $15.5325
  vs no-cache $115.5000  ->  saves  86.6%
  per 1K req  $31.0650

OpenAI GPT-5 (automatic)
  writes     3  reads   497  misses     0
  input cost  $19.8625
  vs no-cache $38.5000  ->  saves  48.4%
  per 1K req  $39.7250

Gemini 3 Pro (explicit, 1-hour)
  writes     3  reads   497  misses     0
  input cost  $ 2.6359
  storage     $ 0.0006
  vs no-cache $ 9.6250  ->  saves  72.6%
  per 1K req  $ 5.2730
```

（`Scenario` 后出现两个空行，是因为字符串末尾的 `\n` 加上 `print_report` 开头的 `\n`。）

逐项解读（数字均已用 Python 复算）：

- **Anthropic 5 分钟：21 次写入**。总时长 `499 × 4 = 1996` 秒，每个前缀在 0/300/600/…/1800 秒各写一次（7 次），3 个前缀共 21 次。成本 = 写入 `21 × 15 × 0.01875 = $5.906` + 读取 `479 × 15 × 0.0015 = $10.778` + 后缀 `500 × 0.4 × 0.015 = $3.00` = $19.684。写入次数是"TTL 不续期"造成的，按真实的滑动 TTL 应为 3 次、$15.03（第 3.3 节）。
- **Anthropic 1 小时：3 次写入**。2,000 秒内都没过期。成本 = `$1.35 + $11.1825 + $3.00 = $15.5325`。节省 86.6% 而不是 90%，差额来自后缀 $3.00（全价）和 3 次写入溢价。
- **OpenAI：48.4%**。无写入溢价，但读取只有 5 折；上限 `15000/15400 × 50% ≈ 48.7%`。绝对成本 $19.86 与 Anthropic 5m 的 $19.68 几乎一样——基础价低 3 倍，折扣也小得多，两者在这个场景里打平。
- **Gemini：72.6%**。读取 0.25×，上限约 `15000/15400 × 75% ≈ 73.1%`；存储费 $0.0006 可以忽略。但请记住：按讲义表格，15K 前缀达不到 Gemini Pro 的 32,768 门槛（第 3.5 节）。
- **`misses` 全是 0**：不是"完美命中"，而是代码从不统计 miss。
- **跨提供商对比要小心**：四行的基础价完全不同（$15 / $5 / $1.25 每百万 token），"节省百分比"只能在同一提供商内比较；跨家比较应看绝对成本或每 1K 请求成本。

敏感性实验（改 `seconds_between`，原代码，Anthropic 5m / 1h、OpenAI 的写入次数与总成本）：

| 间隔 | 5m 写入 | 5m 成本 | 1h 写入 | 1h 成本 | OpenAI 写入 | OpenAI 成本 |
|-----|--------|--------|--------|--------|------------|------------|
| 4 秒 | 21 | $19.68 | 3 | $15.53 | 3 | $19.86 |
| 30 秒 | 126 | $46.85 | 15 | $20.66 | 15 | $20.31 |
| 60 秒 | 251 | $79.20 | 27 | $25.79 | 27 | $20.76 |
| 100 秒 | 500 | $143.63 | 42 | $32.21 | 42 | $21.33 |

100 秒间隔时同一前缀每 300 秒才来一次，正好卡在 `>= 300` 的过期边界，5 分钟 TTL 全部是写入，成本比不缓存（$115.5）**高 24%**；OpenAI 因为没有写入溢价，始终不亏。

---

## 7. 动手改一改

1. **修正滑动 TTL**：在 `simulate_anthropic` 命中分支加 `entry.written_at = now_seconds`，重跑并确认 5 分钟 TTL 变为 3 次写入、$15.0263；再思考 OpenAI/Gemini 是否也该续期（讲义对二者的说明分别是"best-effort"和"user-set"）。
2. **加入最小门槛与 misses 统计**：给三个模拟器加 `min_tokens` 参数（Anthropic 1,024、OpenAI 1,024、Gemini Pro 32,768），不足门槛的请求记 `misses += 1` 并全价计费；看看 Gemini 一行会变成什么。
3. **打印盈亏平衡表**：写一个函数，对 n = 0…10 打印"1 写 + n 读"在 Anthropic 5m（1.25/0.1）、1h（2.0/0.1）下的平均成本倍率，验证讲义的 0.675× 与 0.205×，并找出各自的回本点（5m 读 1 次，1h 读 2 次）。
4. **真实流量回放**（讲义练习 2）：把 `make_traffic` 换成读取一个请求日志（每行：时间戳、前缀哈希、前缀 token 数、后缀 token 数），用真实时间戳替代 `i * seconds_between`，计算四种模式的命中率与节省。
5. **输出 token 与总账单**：给 `Request` 加 `output_tokens` 字段和每家的输出价，打印"总成本中缓存能影响的比例"，体会"缓存只打折输入"。
6. **进阶：多断点**：Anthropic 允许在多个内容块上放 `cache_control`。把前缀拆成"全局 system（所有请求共享）+ 租户手册（按租户不同）"两段，各自有 key 和 TTL，模拟多租户场景（对应测验 Q16）。

---

## 8. 常见坑

- **把模拟结果当真实账单**：TTL 语义、门槛、驱逐策略任何一处与真实计费不符，结论都可能反转（本代码的 5m vs 1h 就是例子）。上线后一定用响应里的 usage 字段核对。
- **以为缓存一定省钱**：请求间隔 ≥ TTL 时，每次都付写入溢价，比不缓存更贵（间隔 100 秒的实验）。
- **只看节省百分比**：不同提供商基础价不同，48% 的折扣可能比 87% 的折扣在绝对值上更便宜，跨家要比绝对成本。
- **把动态字段放在断点之上**：时间戳、请求 ID、随机排序的工具列表都会让前缀每次不同，`cache_read_input_tokens` 永远为 0。
- **忽略最小可缓存长度**：块太小时提供商静默不缓存，不会报错。
- **误读中文讲义**：中文机翻版开篇把"first-token latency 降低 40–85%"译成了"潜伏率上升"，方向相反；有疑义时以英文版为准。
- **讲义自身的小矛盾**：盈亏平衡处说"至少读两次才回本"，但按它给的倍率读 1 次即回本（1.35 < 2）；"工具重排只会打破 OpenAI 的缓存而不会打破 Anthropic 的"与它在陷阱一节"工具重排会打破每一次命中"的说法也不一致——工具定义位于前缀中，顺序一变，任何前缀缓存都会 miss。
