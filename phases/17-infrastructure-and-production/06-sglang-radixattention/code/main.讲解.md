# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 06 节 前缀缓存服务：RadixAttention 与 KV 复用 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`collections.defaultdict`、`random`），无需 GPU

---

## 1. 这份代码在考察什么

这是一个**以"段"为单位的玩具 radix-tree KV 缓存**加两种调度顺序：

- `RadixCache`：用"路径元组 → [block 数, 最近使用时间]"的字典表示 radix tree，支持最长前缀匹配（`walk`）、插入（`insert`）和 LRU 叶子驱逐（`_evict_one`）。
- `FCFS`：按到达顺序处理。
- `CACHE_AWARE`：离线按"最热分支得分"排序后处理。
- 两种工作负载：固定顺序的 RAG（`[SYSTEM, TOOLS, DOC_x, Q_i]`）和打乱前三段顺序的 scrambled RAG。

输出只有一个指标：**前缀缓存命中率**（复用的 prompt token / 总 prompt token）。

对应讲义概念：radix tree 作为 KV 索引、cache-aware 调度、分支级 LRU、"prompt 顺序是缓存键"。

> 一句话：**命中率取决于三件事——前缀是否真的相同（模板顺序）、缓存放不放得下（容量）、调度是否让同一分支的请求挨在一起**。但要注意：默认参数下前两种调度的结果完全相同（69.1%），代码声称的"超过 80%"并未出现，原因在 3.3 与 3.4（第 6 节有实验）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `KV_BUDGET_BLOCKS = 160`、`BLOCK_TOKENS = 16` | 常量 | 缓存容量 160 block（2,560 token） | HBM 中 KV 预算 |
| `token_count` | 函数 | 段名 → token 数：SYSTEM 2000、TOOLS 300、DOC 500、Q 60 | prompt 组成 |
| `Request` | `@dataclass` | 请求 id + 段列表 | prompt 模板 |
| `RadixCache` | 类 | `walk` 最长前缀匹配、`insert` 插入缺失节点、`_evict_one` 驱逐 LRU 叶子 | RadixAttention、分支级 LRU |
| `simulate` | 函数 | 按调度顺序逐个请求 walk + insert，统计命中 | 调度策略对比 |
| `workload_rag` / `workload_scrambled` | 函数 | 80 个请求、4 个文档；后者打乱前三段 | 模板顺序纪律 |
| `report` / `main` | 函数 | 打印 4 行结果与 KEY FINDING | 实验 |

数据流：`workload_*()` → `simulate(requests, scheduler)`（内部新建 `RadixCache`，CACHE_AWARE 先排序）→ 每个请求 `walk`（统计复用）+ `insert`（补齐路径、必要时驱逐）→ `report` 打印命中率。

---

## 3. 逐段精讲

### 3.1 以"段"为粒度的 token 与 block

```python
def token_count(seg: str) -> int:
    if seg == "SYSTEM":
        return 2000
    if seg.startswith("DOC_"):
        return 500
    if seg.startswith("Q_"):
        return 60
    if seg == "TOOLS":
        return 300
    return 100
```

- 每个请求的 prompt = 2000 + 300 + 500 + 60 = 2,860 token；80 个请求共 228,800 token。
- 换算成 block（`ceil(token / 16)`）：SYSTEM 125、TOOLS 19、DOC 32、Q 4，**一条完整路径 180 block**，而预算只有 160——默认配置下缓存连一个完整请求都放不下（见 3.3）。
- 真实 RadixAttention 以 **token** 为粒度匹配（两个 prompt 可以在任意 token 处分叉），这里以"整段"为粒度，是一种简化：段名相同即视为 token 完全相同。

### 3.2 `RadixCache` 的表示与 `walk`

```python
class RadixCache:
    def __init__(self, budget_blocks: int = KV_BUDGET_BLOCKS):
        self.budget = budget_blocks
        self.used = 0
        self.time = 0
        self.nodes: dict[tuple[str, ...], list[int]] = {}

    def walk(self, segments: list[str]) -> int:
        reused = 0
        self.time += 1
        for i in range(1, len(segments) + 1):
            key = tuple(segments[:i])
            if key in self.nodes:
                reused += token_count(segments[i - 1])
                self.nodes[key][1] = self.time
            else:
                break
        return reused
```

- 树没有显式的父子指针，而是"**路径元组即节点**"：`("SYSTEM",)`、`("SYSTEM","TOOLS")`……每个节点只存**最后一段**的 block 数。元组可以做字典键（不可变、可哈希），列表不行。
- `walk` 从长度 1 的前缀开始逐段查找，遇到第一个不存在的节点就停——这就是最长前缀匹配。沿途把节点的 `last_used` 更新为当前时间，供 LRU 使用。
- `self.time` 是逻辑时钟，每个请求 +1；`insert` 新建的节点也用同一个时间。
- 命中的计量单位是 token（不是 block），所以命中率 = 复用 token / 总 token。

### 3.3 `insert` 与 `_evict_one`：分支级 LRU 及其问题

```python
    def insert(self, segments: list[str]) -> None:
        for i in range(1, len(segments) + 1):
            key = tuple(segments[:i])
            if key in self.nodes:
                continue
            blocks = (token_count(segments[i - 1]) + BLOCK_TOKENS - 1) // BLOCK_TOKENS
            while self.used + blocks > self.budget and self._evict_one():
                pass
            self.nodes[key] = [blocks, self.time]
            self.used += blocks

    def _evict_one(self) -> bool:
        leaves = [k for k in self.nodes if not any(
            other != k and other[: len(k)] == k for other in self.nodes)]
        if not leaves:
            return False
        victim = min(leaves, key=lambda k: self.nodes[k][1])
        self.used -= self.nodes.pop(victim)[0]
        return True
```

- **插入**：沿路径补齐缺失节点；放不下就反复驱逐，直到放得下或没有可驱逐的叶子。`while cond and self._evict_one(): pass` 利用短路求值：先判断是否超预算，超了才调用驱逐，驱逐失败（返回 False）就退出循环——此时会**超预算强行插入**。
- **叶子**：没有任何其他节点以它为前缀的节点。按 `last_used` 最小者驱逐，这就是讲义的"从最久未用的叶子开始，整段驱逐"（分支级 LRU）。
- ⚠️ **会驱逐当前正在插入的路径**。插桩第一个请求 `[SYSTEM, TOOLS, DOC_3, Q_13]`：
  1. SYSTEM → used 125；TOOLS → 144；
  2. 插 DOC（+32 = 176 > 160）：唯一叶子是 `(SYSTEM, TOOLS)`——DOC 的父节点——被驱逐，used 125 → 157；
  3. 插 Q（+4 = 161 > 160）：唯一叶子是刚插入的 DOC，被驱逐，used 125 → 129。
  
  结果：缓存里只剩 `(SYSTEM,)` 和一个**孤儿** `(SYSTEM, TOOLS, DOC_3, Q_13)`。孤儿永远走不到（`walk` 在 TOOLS 处就停了），却占着 block，直到下次被当作 LRU 叶子清掉。真实 SGLang 用引用计数保护正在被运行请求使用的节点，只驱逐引用计数为 0 的节点。
- 之后每个请求都重复这个过程，所以**只有 SYSTEM 能被复用**：`79 × 2000 = 158,000` token，命中率 `158,000 / 228,800 = 69.1%`——与调度顺序无关。
- `_evict_one` 每次扫描全部节点对，O(n²)；真实实现在树上维护叶子集合和按时间排序的堆。

### 3.4 `simulate`：两种调度顺序

```python
    if scheduler == "CACHE_AWARE":
        branch_count: dict[tuple[str, ...], int] = defaultdict(int)
        for r in requests:
            for i in range(1, len(r.segments) + 1):
                branch_count[tuple(r.segments[:i])] += 1

        def score(r: Request) -> int:
            return max(branch_count[tuple(r.segments[:i])] * sum(
                token_count(s) for s in r.segments[:i])
                for i in range(1, len(r.segments) + 1))
        order = sorted(requests, key=score, reverse=True)
    else:
        order = list(requests)
```

- `branch_count` 统计每个前缀被多少请求共享（**事先看到了全部请求**，是离线统计）。
- `score(r)` = 该请求所有前缀中"共享人数 × 前缀 token 数"的最大值，即"它所在的最热分支的价值"。按 score 降序排列，意图是先处理热分支上的请求。
- ⚠️ 在固定顺序 RAG 中，所有请求都以 `SYSTEM, TOOLS` 开头，深度 2 的得分 `80 × 2300 = 184,000` 是每个请求的最大值，**所有请求得分相同**；`sorted` 是稳定排序，于是 CACHE_AWARE 的顺序与 FCFS 完全一样。它没能把同一个文档的请求聚在一起。
- 在 scrambled 负载中，首段不同的请求得分不同（50,000、36,800、16,800……），排序恰好把相同首段的请求聚到了一起，所以 CACHE_AWARE（26.5%）明显好于 FCFS（8.4%）。
- 主循环：

```python
    for r in order:
        prompt_tokens = sum(token_count(s) for s in r.segments)
        total += prompt_tokens
        reused = cache.walk(r.segments)
        saved += reused
        cache.insert(r.segments)
```

  每个请求先 walk 记复用，再 insert 补齐。没有并发、没有时间、没有 decode——所以讲义"Use It"说的"报告吞吐差异"并没有实现，代码只报告命中率。

### 3.5 工作负载与打乱

```python
def workload_rag(n: int = 80, docs: int = 4, seed: int = 1) -> list[Request]:
    rng = random.Random(seed)
    for i in range(n):
        doc = f"DOC_{rng.randrange(docs)}"
        q = f"Q_{i}"
        reqs.append(Request(i, ["SYSTEM", "TOOLS", doc, q]))
    rng.shuffle(reqs)
```

- 4 个文档的出现次数（seed=1）：DOC_3 27、DOC_0 20、DOC_1 18、DOC_2 15。问题 `Q_i` 每个都唯一，永远不会命中。
- `rng.shuffle(reqs)` 打乱到达顺序，模拟不同文档的请求交错到达——这正是 cache-aware 调度应该发挥作用的场景。
- scrambled 版本对每个请求的 `[SYSTEM, TOOLS, doc]` 做 `shuffle`，6 种排列的实际分布为 18/16/13/12/11/10。

### 3.6 理论上限

固定顺序 RAG 在缓存足够大时的最高命中率：SYSTEM+TOOLS 除第一个请求外全部命中（`79 × 2300`），每个文档只在首次出现时 miss（`76 × 500`），问题永不命中：

`(181,700 + 38,000) / 228,800 = 96.0%`

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 以"段"为粒度、路径元组即节点 | 代码极短、易于打印 | 无法表示段内部分共享；真实 radix tree 以 token 为粒度并会分裂节点 |
| 每节点只存最后一段的 block | 与 radix tree"节点拥有一段 token"一致 | — |
| 分支级 LRU（只驱逐叶子） | 保证剩下的是从根出发的完整前缀 | 未保护当前路径，会驱逐父节点、产生孤儿；生产用引用计数 |
| 预算 160 block | 想让驱逐"咬人" | 小于一条路径的 180 block，任何调度都只能保住 SYSTEM，两种策略结果相同 |
| 离线全局排序的 CACHE_AWARE | 演示"热分支优先" | 需要预知所有请求；分数平局时退化为 FCFS；生产用在线的最长前缀匹配排序并防止饥饿 |
| 只报告命中率 | 聚焦核心指标 | 没有吞吐、TTFT，无法复现讲义的 29% / 6.4x |
| scrambled 只在 6 种排列间打乱 | 演示顺序的影响 | 大缓存下仍有 79.5% 命中率；真实的"前缀中插入动态内容"才会让命中率接近 0 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class Request: rid: int; segments: list[str]` | 简单数据容器 |
| 元组作字典键 | `self.nodes[tuple(segments[:i])]` | 元组不可变、可哈希；列表不能作键 |
| 可变的字典值 | `self.nodes[key][1] = self.time` | 值用 `list` 而不是 `tuple`，才能原地更新时间戳 |
| 变长元组类型注解 | `dict[tuple[str, ...], list[int]]` | `tuple[str, ...]` 表示任意长度的字符串元组 |
| 切片比较判断前缀 | `other[: len(k)] == k` | 元组切片后整体比较 |
| `any()` + 生成器 | `not any(other != k and ... for other in self.nodes)` | 只要有一个满足就为真，短路求值 |
| `min(..., key=lambda)` | `min(leaves, key=lambda k: self.nodes[k][1])` | 按时间戳找最久未用的叶子 |
| `dict.pop(key)` | `self.nodes.pop(victim)[0]` | 删除并返回值 |
| `while cond and f(): pass` | 驱逐循环 | 短路求值：条件不满足就不调用 `f`；`f` 返回 False 时退出 |
| `defaultdict(int)` | `branch_count[...] += 1` | 不存在的键默认 0，省去判断 |
| 嵌套函数（闭包） | `def score(r)` 定义在 `simulate` 内，读取外层的 `branch_count` | 闭包捕获外层变量 |
| 稳定排序 | `sorted(requests, key=score, reverse=True)` | 键相同时保持原有相对顺序（本文件中导致 CACHE_AWARE == FCFS） |
| `random.Random(seed)` | `rng.randrange(docs)`、`rng.shuffle(reqs)` | 可复现的随机；`shuffle` 原地打乱 |
| 向上取整整除 | `(n + BLOCK_TOKENS - 1) // BLOCK_TOKENS` | 不用 `math.ceil` |
| f-string 百分比格式 | `{res['hit_rate']:6.1%}` | 自动乘 100 并加 `%` |
| f-string 对齐 | `{res['saved']:>6}`、`{res['total']:<6}`、`{label:44}` | 右对齐、左对齐、固定宽度 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，不到 1 秒）：

```text
RAG workload | FCFS                           hit_rate= 69.1%   saved=158000/228800 tok   reqs=80
RAG workload | CACHE_AWARE                    hit_rate= 69.1%   saved=158000/228800 tok   reqs=80
RAG scrambled prefix | FCFS                   hit_rate=  8.4%   saved= 19300/228800 tok   reqs=80
RAG scrambled prefix | CACHE_AWARE            hit_rate= 26.5%   saved= 60700/228800 tok   reqs=80

KEY FINDING
  Fixed ordering + cache-aware scheduler : hit rate clears 80% on RAG.
  Scrambled prefix order : hit rate collapses — the tree cannot find shared paths.
```

逐项解读：

- **RAG 两行完全相同**：`158,000 = 79 × 2000`，只复用了 SYSTEM。原因有二：预算 160 < 一条路径 180 block（3.3）；所有请求 score 相同，CACHE_AWARE 顺序等于 FCFS（3.4）。KEY FINDING 的"超过 80%"在默认参数下不成立。
- **scrambled 两行**：FCFS 8.4% 是"预算太小 + 首段只有约 1/3 是 SYSTEM"共同作用；CACHE_AWARE 把首段相同的请求聚在一起，提升到 26.5%。

我们改变 KV 预算并加入"真正按分支分组"的顺序（`sorted(requests, key=lambda r: tuple(r.segments[:-1]))`）做了对照（均已实际运行）：

| KV 预算 | RAG FCFS | RAG CACHE_AWARE（原版） | RAG 按分支分组 | scrambled FCFS | scrambled CACHE_AWARE |
|--------|---------|------------------------|---------------|----------------|----------------------|
| 160 | 69.1% | 69.1% | 69.1% | 8.4% | 26.5% |
| 180 | 82.5% | 82.5% | **96.0%** | 17.6% | 58.2% |
| 250 | 89.3% | 89.3% | **96.0%** | 19.5% | 61.5% |
| 400 | 96.0% | 96.0% | 96.0% | 29.9% | 70.4% |
| 10,000 | 96.0% | 96.0% | 96.0% | 79.5% | 79.5% |

结论：

1. **容量是前提**：预算放不下一条路径时，调度无能为力。
2. **调度在"容量紧张但够用"时价值最大**：预算 180–250 时，按分支分组把命中率从 82–89% 提到理论上限 96%；容量充足（≥ 400）时顺序又不重要了。
3. **顺序纪律的损失是永久的**：即使缓存无限大，打乱顺序也只有 79.5%（vs 96.0%），因为不同排列之间完全无法共享；而在容量有限时，这个差距会被成倍放大（96% vs 30% 左右）。

---

## 7. 动手改一改

1. **保护当前路径**：在 `insert` 期间把当前路径上的节点加入一个"pinned"集合，`_evict_one` 跳过它们；观察孤儿节点是否消失，以及在预算 160 时会发生什么（提示：会被迫超预算，说明预算本身不合理）。
2. **真正的分支分组调度**：把 CACHE_AWARE 的排序改为按 `tuple(r.segments[:-1])` 分组，或在线实现"每次从等待队列中选与当前缓存最长前缀匹配的请求"，在预算 180 下复现 96.0%。
3. **讲义练习 2**：把 scrambled 的打乱扩展到 `[SYSTEM, TOOLS, DOC, HISTORY]` 四段（24 种排列），并加一个"在最前面插入时间戳段"的版本，比较命中率。
4. **讲义练习 3**：加一个函数，按 Llama 3.1 8B（32 层、8 KV 头、head_dim 128、BF16）把 block 数换算成字节，打印常驻 SYSTEM 分支的显存（约 262MB）与 16 条序列各存一份的显存（约 4.19GB）。
5. **加吞吐**：假设 prefill 每 token 0.04ms、decode 每 token 0.5ms、每请求输出 200 token，按"未命中的 prompt token"计算 prefill 时间，输出端到端时间与相对加速，看命中率 69% → 96% 能带来多少收益。
6. **token 粒度**：把 `segments` 换成真实的 token 列表，实现会在分叉点分裂节点的 radix tree，测试"同一文档、问题前 20 token 相同"时的部分共享。

---

## 8. 常见坑

- **缓存容量小于一条路径**：本文件默认参数就是这样，导致所有调度策略结果相同；做实验前先算"一个请求需要多少 block"。
- **驱逐正在使用的节点**：会产生走不到的孤儿节点，白白占用 KV；生产实现必须用引用计数保护。
- **离线排序冒充在线调度**：真实调度器看不到未来的请求，还要处理饥饿与公平。
- **得分平局**：只看"最热层"的得分会让所有请求打平，稳定排序退化为 FCFS。
- **把"人眼看来相同"当成前缀相同**：顺序不同、空格不同、JSON 键顺序不同，在 radix tree 里都是不同的路径。
- **在前缀前部放动态内容**：时间戳、请求 ID、用户名放在 system prompt 开头，会让后面所有内容都无法复用。
- **只报告命中率**：命中率要换算成 prefill 时间、TTFT 和吞吐，才能和讲义的 29% / 6.4x 对照。
