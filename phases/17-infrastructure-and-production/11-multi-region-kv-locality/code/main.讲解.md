# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 11 节 多区域 LLM 服务与 KV Cache 局部性 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数；如需结果完全可复现，用 `PYTHONHASHSEED=0 python main.py`） ｜ **依赖**：仅标准库（`random`、`statistics`、`dataclasses`）；无需 GPU、无需网络

---

## 1. 这份代码在考察什么

这是一个"多区域前缀缓存路由模拟器"：3 个区域 × 每区 4 个副本，1000 个请求从三个区域随机发出，每个请求带有 40 个热门前缀之一。比较三种路由策略：

1. **ROUND_ROBIN**：完全不看缓存，按请求序号轮流分给 12 个副本。
2. **REGIONAL**：只在请求来源区域内做 cache-aware 路由，有命中就去命中的副本，否则选队列最短的。
3. **GLOBAL**：在所有区域中找命中副本，用 `80 ms + RTT` 作为代价选最优；若代价比本地未命中（800 ms）还高则回到本地。

输出每种策略的命中率、平均 / P50 / P99 TTFT、跨区域请求数和跨区域费用。它对应讲义的"round-robin 有害""cache-aware routing""跨区域多了网络项（GORGO）"三部分。

> 一句话：**命中与否决定 10 倍的 TTFT 差距，路由器的任务就是"让请求去对的缓存"**——不过这份模拟器的 REGIONAL 策略有一个让队列深度恒为 0 的 bug，导致它严重低估了区域内路由的效果（见 3.5）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `REGIONS`、`REPLICAS_PER_REGION` | 常量 | 3 个区域、每区 4 个副本 | 多区域拓扑 |
| `CACHE_HIT_MS` / `CACHE_MISS_MS` | 常量 | 80 ms / 800 ms | 讲义 2K prompt 的命中/未命中 TTFT |
| `CROSSREGION_RTT`、`rtt()` | 字典 + 函数 | 区域对之间的 RTT（65 / 75 / 130 ms），同区为 0 | 跨区域网络延迟 |
| `CROSSREGION_COST_PER_REQ` | 常量 | 每次跨区域 $0.0004 | 跨区域流量账单 |
| `Replica` | `@dataclass` | 副本：区域、编号、前缀缓存集合、队列深度 | 有状态的推理副本 |
| `Request` | `@dataclass` | 请求：来源区域、前缀哈希、服务副本、TTFT、是否跨区域 | — |
| `make_replicas` / `make_workload` | 函数 | 生成 12 个副本；生成 1000 个请求（来源与前缀均匀随机） | 工作负载 |
| `simulate` | 函数 | 按策略逐个路由请求、更新缓存与队列、统计指标 | 路由算法 |
| `report` / `main` | 函数 | 打印三种策略的结果 | — |

数据流：`make_workload()` → 为每种策略复制一份请求 → `simulate(strategy, reqs)` → 每个请求选副本 → 判断命中 → 计算 TTFT（+ RTT）→ 更新缓存 → 汇总 → `report`。

---

## 3. 逐段精讲

### 3.1 常量与 `rtt()`：把讲义的数字写进模型

```python
CACHE_HIT_MS = 80
CACHE_MISS_MS = 800
CROSSREGION_RTT = {
    ("us-east-1", "us-west-2"): 65,
    ("us-east-1", "eu-west-1"): 75,
    ("us-west-2", "eu-west-1"): 130,
}

def rtt(a: str, b: str) -> int:
    if a == b:
        return 0
    key = (a, b) if (a, b) in CROSSREGION_RTT else (b, a)
    return CROSSREGION_RTT.get(key, 200)
```

- 80 / 800 ms 来自讲义"Llama 3.3 70B FP8、H100、2K prompt"的命中/未命中 TTFT，固定不随提示长度变化（讲义练习 1 需要你自己把它线性化，见测验 Q10）。
- 字典只存了一个方向，`rtt()` 先查 `(a, b)`，查不到就查 `(b, a)`——用元组作为字典键表示"无序的区域对"的一种简单写法（也可以用 `frozenset({a, b})` 作键）。
- `.get(key, 200)`：没有登记的区域对默认 200 ms。
- RTT 被**整体加一次**到 TTFT 上（请求过去、首 token 回来恰好是一个往返）。注意讲义正文"440 ms round-trip"把 220 ms 的 RTT 又翻了一倍，代码的处理才是正确的。

### 3.2 `Replica` 与 `Request`：可变默认值要用 `field`

```python
@dataclass
class Replica:
    region: str
    idx: int
    prefix_cache: set = field(default_factory=set)
    queue_depth: int = 0


@dataclass
class Request:
    origin_region: str
    prefix_hash: str
    served_by: Replica | None = None
    ttft_ms: float = 0
    crossregion: bool = False
```

- `prefix_cache: set = field(default_factory=set)`：每个副本都要有**自己的**空集合。如果写成 `= set()`，dataclass 会直接报错（防止所有实例共享同一个可变对象）。
- `Replica | None`：Python 3.10 的联合类型写法；文件开头的 `from __future__ import annotations` 让它在更早的版本里也能作为注解使用。
- 副本的"缓存"被简化为一个前缀哈希的集合，容量上限 12（见 3.5），不区分 KV 块，也不区分前缀长度。

### 3.3 `make_workload`：均匀随机的请求

```python
def make_workload(n: int = 1000, seed: int = 7) -> list[Request]:
    rng = random.Random(seed)
    reqs = []
    hot_prefixes = [f"prefix_{i}" for i in range(40)]
    for _ in range(n):
        origin = rng.choice(REGIONS)
        prefix = rng.choice(hot_prefixes)
        reqs.append(Request(origin_region=origin, prefix_hash=prefix))
    return reqs
```

- 40 个前缀、3 个区域，二者**独立**均匀抽取。真实流量中前缀往往有区域性（例如欧洲客户用自己的系统提示）和长尾分布（少数前缀极热），这里都没有建模。
- `main` 为每种策略重新构造 `Request` 对象（只拷贝来源与前缀），保证三种策略面对完全相同的请求序列，又不会互相污染 `served_by` 等字段。

### 3.4 `simulate`：三种路由策略

```python
        if strategy == "ROUND_ROBIN":
            chosen = replicas[i % len(replicas)]
        elif strategy == "REGIONAL":
            local = [rep for rep in replicas if rep.region == r.origin_region]
            matches = [rep for rep in local if r.prefix_hash in rep.prefix_cache]
            if matches:
                chosen = min(matches, key=lambda x: x.queue_depth)
            else:
                chosen = min(local, key=lambda x: x.queue_depth)
        elif strategy == "GLOBAL":
            matches = [rep for rep in replicas if r.prefix_hash in rep.prefix_cache]
            best_cost = float("inf")
            for rep in matches:
                c = CACHE_HIT_MS + rtt(r.origin_region, rep.region)
                if c < best_cost:
                    best_cost = c
                    chosen = rep
            if chosen is None or best_cost > CACHE_MISS_MS:
                local = [rep for rep in replicas if rep.region == r.origin_region]
                chosen = min(local, key=lambda x: x.queue_depth)
```

- **ROUND_ROBIN**：`i % 12` 在**全部 12 个副本**之间轮转，所以 2/3 的请求跨区域（每次运行都是 664 次）。真实的 ALB 通常是区域内轮询，这里等于"全球轮询"，额外放大了 RTT 惩罚。
- **REGIONAL**：先筛出本区域副本，再筛出命中的副本；有命中选队列最短者，否则在本区域内选队列最短者。这正是讲义描述的"prefix-hash match + least-queue-depth 回退"。
- **GLOBAL**：在全部命中副本中选 `80 + RTT` 最小者，这是 GORGO"联合最小化 prefill + 网络延迟"的极简版。由于最大 RTT 只有 130 ms，`80 + 130 = 210 < 800`，只要有任何区域命中就会跨过去——`best_cost > CACHE_MISS_MS` 的回退条件在这组参数下永远不会触发。
- `float("inf")` 作为"最小值搜索"的初值；`min(..., key=lambda x: x.queue_depth)` 按队列深度取最小。
- ⚠️ GLOBAL 完全没有数据驻留约束：一次运行中 312 个欧盟来源请求里有 190 个被送到美国区域，违反讲义"Partition routers by residency boundary before optimizing for cache"。

### 3.5 命中、驱逐与队列更新：两个隐藏问题

```python
        cross = chosen.region != r.origin_region
        hit = r.prefix_hash in chosen.prefix_cache
        if hit:
            hits += 1
            r.ttft_ms = CACHE_HIT_MS + rtt(r.origin_region, chosen.region)
        else:
            r.ttft_ms = CACHE_MISS_MS + rtt(r.origin_region, chosen.region)
            chosen.prefix_cache.add(r.prefix_hash)
            if len(chosen.prefix_cache) > 12:
                chosen.prefix_cache.pop()
        chosen.queue_depth = max(0, chosen.queue_depth + (1 if rng.random() < 0.4 else 0) - 1)
```

- TTFT = 命中 80 ms 或未命中 800 ms，再加 RTT；未命中时把前缀加入该副本缓存（模拟 prefill 后 KV 驻留）。
- ⚠️ **问题一：`queue_depth` 永远是 0**。更新式从 0 出发只有两种结果：40% 概率 `0 + 1 − 1 = 0`，60% 概率 `max(0, 0 − 1) = 0`。实测 10 万步最大值仍为 0。于是所有 `min(..., key=queue_depth)` 都退化为"取列表第一个"：
  - REGIONAL 的未命中请求全部落到每个区域的 0 号副本（实际统计：us-east-1/0 服务 365 个、us-west-2/0 服务 323 个、eu-west-1/0 服务 312 个，其余 9 个副本一个请求都没有）；
  - 每个区域实际只有 12 个缓存槽来装 40 个前缀，REGIONAL 命中率因此只有约 31%。
  - 这个 bug 让"REGIONAL 只比 ROUND_ROBIN 略好、GLOBAL 遥遥领先"的结论失真。改用"未命中时按前缀哈希一致性分配 + LRU 驱逐"后，REGIONAL 命中率升到 88.0%、平均 TTFT 166 ms、零跨区域，与修正后的 GLOBAL（96.0%、166 ms、648 次跨区域）平均 TTFT 相同（测验 Q9）。这恰好印证了讲义"Often the answer is to keep routing regional"。
- ⚠️ **问题二：`set.pop()` 驱逐任意元素，且不可复现**。集合没有顺序，`pop()` 弹出的元素取决于哈希表布局；而 Python 对字符串的哈希默认按进程随机化（`PYTHONHASHSEED`）。所以虽然代码固定了 `random.Random(7)` 和 `random.Random(11)`，每次运行的命中率仍会波动：实测 GLOBAL 在 86.3%–89.2%、ROUND_ROBIN 在 26.5%–28.9% 之间。真实 KV 缓存一般用 LRU 类策略，可以用 `collections.OrderedDict` 实现（`move_to_end` + `popitem(last=False)`）。
- `cross` 在 `if` 之后统一计算；`r.served_by` 与 `r.crossregion` 把结果写回请求对象，便于事后分析（测验里的逐区域统计就是读这两个字段得到的）。

### 3.6 汇总：分位数与费用

```python
    ttfts.sort()
    p50 = ttfts[len(ttfts) // 2]
    p99 = ttfts[int(len(ttfts) * 0.99) - 1]
    return {
        "strategy": strategy,
        "hit_rate": hits / len(reqs),
        "mean_ttft": statistics.mean(ttfts),
        ...
        "crossregion_cost": crossregion_count * CROSSREGION_COST_PER_REQ,
    }
```

- P50 取下标 500，P99 取下标 989（`int(1000 × 0.99) − 1`）。与第 08 节的 `percentiles` 函数（取下标 990）相差一位，样本量大时无关紧要，但说明"分位数的实现细节要统一"。
- TTFT 只可能取 {80, 145, 155, 210, 800, 865, 875, 930} 这几个离散值（命中/未命中 + 0/65/75/130 ms），所以 P50、P99 会"卡"在这些值上。
- 跨区域费用只是 `次数 × $0.0004`，1000 个请求不到 $0.3，用于说明"跨区域有账单"，量级是示意。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 命中/未命中固定为 80 / 800 ms | 直接使用讲义的数字 | 不随提示长度变化，无法回答"多长提示值得跨区"；生产中用 `prefill(L)` 模型或实测 |
| 缓存 = 前缀集合，容量 12 | 代码最短 | `set.pop()` 随机驱逐、跨进程不可复现；真实引擎按 KV 块做 LRU / 基数树管理 |
| 队列深度用随机游走模拟 | 想表达"负载"维度 | 更新式写错导致恒为 0，平局规则退化为"选第一个"；生产中用副本实时上报的排队数 |
| 未命中时选队列最短副本 | 讲义描述的回退规则 | 不加一致性哈希时，同一前缀会分散到不同副本，浪费缓存；生产中常用一致性哈希 + 负载上限 |
| GLOBAL 只比较 `80 + RTT` | GORGO 思路的最小实现 | 不考虑远端排队、跨区费用、RTT 抖动，也不考虑驻留；生产中要先按驻留分区再优化 |
| ROUND_ROBIN 跨所有区域 | 展示最坏情况 | 夸大了 RTT 惩罚；真实 ALB 多为区域内轮询 |
| 不建模 KV 事件延迟 | 简化 | 真实路由器的索引会滞后于副本状态，产生"假命中" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让 `Replica | None`、`list[Request]` 等注解在旧版本中也可用 |
| `@dataclass` + `field(default_factory=...)` | `prefix_cache: set = field(default_factory=set)` | 可变默认值必须用工厂函数，确保每个实例一份 |
| 联合类型 | `served_by: Replica | None = None` | 值可以是 `Replica` 或 `None` |
| 元组作字典键 | `CROSSREGION_RTT[("us-east-1", "us-west-2")]` | 元组不可变、可哈希，适合作复合键 |
| `dict.get(key, default)` | `CROSSREGION_RTT.get(key, 200)` | 查不到时返回默认值，不抛 `KeyError` |
| 条件表达式选键 | `key = (a, b) if (a, b) in CROSSREGION_RTT else (b, a)` | 处理无序区域对 |
| 双重 for 的列表推导式 | `[Replica(r, i) for r in REGIONS for i in range(REPLICAS_PER_REGION)]` | 等价于两层嵌套循环，外层在前 |
| 带过滤的推导式 | `[rep for rep in local if r.prefix_hash in rep.prefix_cache]` | 只保留满足条件的元素 |
| `min` + `key=lambda` | `min(local, key=lambda x: x.queue_depth)` | 按指定属性取最小；并列时返回**第一个** |
| `float("inf")` | `best_cost = float("inf")` | 正无穷，作为最小值搜索的初值 |
| `enumerate` | `for i, r in enumerate(reqs):` | 同时得到下标和元素 |
| `set` 操作 | `in`、`.add()`、`.pop()`、`len()` | `pop()` 弹出任意元素，不保证顺序 |
| 整除与取模 | `len(ttfts) // 2`、`i % len(replicas)` | 地板除；取模实现轮转 |
| 独立随机数生成器 | `random.Random(seed)` | 可复现的随机序列（但管不住字符串哈希的随机化） |
| `statistics.mean` | `statistics.mean(ttfts)` | 求均值 |
| f-string 中的表达式 | `{row['hit_rate']*100:5.1f}%`、`{row['crossregion']:4}` | 花括号内可以做运算再格式化 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行 `main()`，测验中的分析脚本就是 import 后调用 `simulate` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`；由于 `set.pop()` 与字符串哈希随机化，每次运行数字略有不同，以下为其中一次）：

```text
Strategy       hit         mean     P50      P99      cross   cost
------------------------------------------------------------------
ROUND_ROBIN    hit= 26.5%  mean=  669ms  P50=  800ms  P99=  930ms  cross= 664  cross_cost=$0.266
REGIONAL       hit= 30.9%  mean=  578ms  P50=  800ms  P99=  800ms  cross=   0  cross_cost=$0.000
GLOBAL         hit= 88.4%  mean=  216ms  P50=  145ms  P99=  800ms  cross= 595  cross_cost=$0.238

Read: REGIONAL beats ROUND_ROBIN on cache hit. GLOBAL is
only better when prefill cost dominates network latency.
```

逐项解读：

- **ROUND_ROBIN**：命中率约 27%，P50 = 800 ms（多数请求未命中），P99 = 930 ms（未命中 + 130 ms RTT）。664 次跨区域是 `i % 12` 的确定结果（每次运行都相同）。
- **REGIONAL**：命中率约 31%，零跨区域，P99 = 800 ms。命中率低的原因是队列深度恒为 0、所有未命中挤到 0 号副本（见 3.5），不是区域路由本身的缺陷。
- **GLOBAL**：命中率约 88%，P50 = 145 ms（多数是"命中 + 65 ms RTT"），平均 216 ms。它能借用其它区域 0 号副本里的缓存，相当于把 3 × 12 = 36 个缓存槽拼在一起，因此大幅领先。
- **5 次不同 `PYTHONHASHSEED` 的实测**：REGIONAL 30.1%–31.2%，GLOBAL 86.3%–89.2%，ROUND_ROBIN 26.5%–28.9%——结论方向稳定，但具体数字不可复现。
- **"Read:" 的结论**："GLOBAL is only better when prefill cost dominates network latency"——在这组参数下 prefill（800 ms）总是远大于 RTT（≤ 130 ms），所以 GLOBAL 总是跨。修正 REGIONAL 的 bug 后，两者平均 TTFT 相同（都约 166 ms），GLOBAL 只是多付了跨区域流量与合规风险。

---

## 7. 动手改一改

1. **（入门）** 用 `PYTHONHASHSEED=0` 运行两次，确认结果一致；再把 `prefix_cache` 改成 `collections.OrderedDict` 实现 LRU，去掉对哈希种子的依赖。
2. **（入门）** 修正队列深度：例如每次被选中 `+1`，每处理完 k 个请求所有副本 `−1`；或者干脆在未命中时用 `zlib.crc32(prefix) % 4` 选副本。比较 REGIONAL 的命中率变化（参考测验 Q9：约 88%）。
3. **（进阶）** 讲义练习 1：把 `CACHE_MISS_MS` 改成 `0.4 × prompt_len`，给请求加上随机提示长度（如 200–16,000 token），统计 GLOBAL 在哪些长度上选择跨区域，验证临界长度约为 `(80 + RTT) / 0.4`。
4. **（进阶）** 讲义练习 5：为 GLOBAL 加入驻留约束（EU 请求只能在 eu-west-1），报告命中率、平均 TTFT、跨区域数的变化（参考测验 Q11）。
5. **（进阶）** 让工作负载更真实：前缀按 Zipf 分布抽取，并让每个区域有自己偏好的前缀子集；观察 REGIONAL 与 GLOBAL 的差距如何变化。
6. **（挑战）** 模拟 KV 事件延迟：路由器的索引在副本驱逐后 N 个请求才更新，统计"路由器以为命中但实际未命中"的比例，以及它对 P99 TTFT 的影响。

---

## 8. 常见坑

- **轮询打散前缀**：同前缀请求分到不同副本，命中率趋近 `1 / 副本数`。
- **平局规则退化为固定顺序**：本代码的 `queue_depth` 恒为 0，`min` 总选第一个副本，造成热点和缓存浪费；任何"按负载选择"的逻辑都要验证负载指标真的在变化。
- **以为固定了随机种子就能复现**：`set` 的迭代/弹出顺序依赖字符串哈希，而字符串哈希默认按进程随机化。
- **用 `set.pop()` 当驱逐策略**：驱逐的是任意元素，不是最久未用的；会让热门前缀被误删。
- **只看命中率不看 TTFT**：GLOBAL 命中率更高，但每个跨区域命中都要付 RTT；修正后它与 REGIONAL 的平均 TTFT 相同。
- **跨驻留边界路由**：TTFT 再好也不能把欧盟数据送出欧盟；要先分区再优化。
- **把商用跨区域推理当成 KV 感知路由**：Bedrock CRI / 多集群网关解决的是可用性。
- **RTT 重复计算**：RTT 已经是往返时间，不要再乘 2（讲义正文的"440 ms"即属此类）。
- **DR 只备份权重**：tokenizer、量化配置、chat template、引擎配置、LoRA 清单缺一不可（讲义的 32%）。
