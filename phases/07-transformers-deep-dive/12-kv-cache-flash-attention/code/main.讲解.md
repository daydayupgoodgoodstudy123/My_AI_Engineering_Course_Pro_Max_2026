# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 12 节 KV Cache、Flash Attention 与 Inference 优化 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

推理优化里最重要的两个思想，都可以用几十行纯 Python 说清楚：

1. **KV cache**：前缀 token 的 K、V 算一次就存起来，之后每个新 token 只用一个 query 去"查"缓存。代码用 `KVCache` 类 + `decode_cached` 演示这个过程，并与 `decode_naive` 对比输出。
2. **FlashAttention 的数学核心——online softmax**：`tiled_softmax_dot` 把 K、V 分成小块逐块处理，只维护"运行最大值 m、运行指数和 s、运行输出 out"，最终结果与一次性 softmax 完全一致。
3. **KV cache 显存估算**：`kv_cache_bytes` 给出公式 `2 × N × 层数 × KV 头数 × d_head × 字节数`，并打印 Llama 3 / Qwen2.5 / DeepSeek-V3 在 2K、32K、128K 上下文下的缓存大小。

> 一句话：**推理优化 = 少重算（KV cache）+ 少搬运（FlashAttention）+ 少存（GQA/MLA）**。

⚠️ 读代码前需要知道：本文件的 `decode_naive` 其实**也用了"缓存"**（直接切片预先算好的 K、V），所以两种解码的计数都是 55，并没有演示出讲义所说的 5050 vs 100 的差距。第 3.4 节会解释原因，测验 Q9 给出了真正不用缓存的版本。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `dot(a, b)` | 函数 | 向量点积 | `q · k` |
| `softmax(xs)` | 函数 | 减最大值的数值稳定 softmax | 标准 softmax |
| `attention_full(q, Ks, Vs)` | 函数 | 单个 query 对一组 K/V 的缩放点积 attention | 标准 attention（一次性） |
| `tiled_softmax_dot(q, Ks, Vs, tile)` | 函数 | 分块 + online softmax 计算同样的 attention | FlashAttention 的算法核心 |
| `KVCache` | 类 | 用两个列表存放 K、V，支持 `append` 和 `len()` | KV cache |
| `decode_naive(...)` | 函数 | 每步对 `all_K[:t+1]` 做 attention，计数 | "朴素"解码（实际等价于缓存） |
| `decode_cached(...)` | 函数 | 每步把新 K/V 追加进 `KVCache` 再做 attention | KV-cached 解码 |
| `kv_cache_bytes(...)` | 函数 | KV cache 字节数公式 | 显存估算 |
| `main()` | 入口 | 三段演示：解码对比、分块 softmax 误差、KV 大小表 | — |

数据流：`main` 生成随机 Q/K/V → `decode_naive` 与 `decode_cached`（都调用 `attention_full`）→ 比较输出；再用最后一个 query 对比 `attention_full` 与不同 tile 的 `tiled_softmax_dot`；最后循环调用 `kv_cache_bytes` 打印表格。

---

## 3. 逐段精讲

### 3.1 基础件：点积、softmax、单 query attention

```python
def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def softmax(xs):
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps)
    return [e / s for e in exps]


def attention_full(q, Ks, Vs):
    """Single-query attention against full lists of keys and values."""
    scores = [dot(q, k) / math.sqrt(len(q)) for k in Ks]
    weights = softmax(scores)
    out = [0.0] * len(Vs[0])
    for w, v in zip(weights, Vs):
        for j in range(len(out)):
            out[j] += w * v[j]
    return out
```

- `attention_full` 就是 decode 阶段的 attention：**一个** query（新 token）对**所有**已缓存的 key 打分，除以 `√d` 缩放，softmax 得到权重，再对 value 加权求和。
- 注意这里没有因果掩码——因为传入的 `Ks` 本身就只包含"过去和当前"，未来 token 根本不在列表里。这和第 07 节讲的"前缀平均里未来从未进入求和"是同一个道理。
- 这个函数会**完整地**算出所有分数、存下所有权重（长度 N 的列表），在 GPU 上对应"把 N×N 分数矩阵写到 HBM"。下面的 `tiled_softmax_dot` 就是要避免这一点。

### 3.2 `tiled_softmax_dot`：online softmax

```python
def tiled_softmax_dot(q, Ks, Vs, tile=4):
    """Flash-attention-style incremental softmax(qK^T)V with tile size `tile`."""
    d_head = len(Vs[0])
    scale = 1.0 / math.sqrt(len(q))
    m = float("-inf")
    s = 0.0
    out = [0.0] * d_head
    for start in range(0, len(Ks), tile):
        k_block = Ks[start:start + tile]
        v_block = Vs[start:start + tile]
        scores = [dot(q, k) * scale for k in k_block]
        new_m = max(m, *scores)
        if m == float("-inf"):
            exp_old = 0.0
        else:
            exp_old = math.exp(m - new_m)
        exp_new = [math.exp(sc - new_m) for sc in scores]
        s = s * exp_old + sum(exp_new)
        for j in range(d_head):
            out[j] = out[j] * exp_old + sum(e * v[j] for e, v in zip(exp_new, v_block))
        m = new_m
    return [o / s for o in out]
```

三个"运行状态"：

| 变量 | 含义 | 不变量（处理完前 i 块后） |
|------|------|-----------------------|
| `m` | 目前见过的最大分数 | `m = max(已见分数)` |
| `s` | 指数和 | `s = Σ exp(score − m)` |
| `out` | 未归一化的输出 | `out = Σ exp(score − m) · v` |

每来一块：

1. 算这块的分数，更新最大值 `new_m = max(m, *scores)`；
2. 旧的 `s` 和 `out` 是以 `m` 为基准的，乘以 `exp(m − new_m)` 换算到新基准——这一步是整个算法的关键，保证不变量始终成立；
3. 加上新块以 `new_m` 为基准的贡献；
4. 全部处理完后 `out / s` 就等于 `Σ softmax(score) · v`，与一次性计算在代数上**完全相等**。

为什么这么设计：

- 每次只需要 `tile` 个 K/V 在"手边"（对应 GPU 的 SRAM），永远不需要长度 N 的分数列表——讲义说的"working set 是 `tile × d_head` 的块，而不是整个 `N × d_head`"。
- 因为 `new_m ≥ m`，缩放因子 `exp(m − new_m) ≤ 1`，所有指数都 ≤ 1，不会溢出。
- `max(m, *scores)`：`*` 把列表解包成多个参数，等价于 `max([m] + scores)`。
- 第一块特判 `m == -inf`：此时还没有任何累计，`exp_old` 取 0。
- ⚠️ 这里只演示了**单个 query**。真实的 FlashAttention 还会对 Q 分块（外层循环），每个 Q 块各自维护 `(m, s, out)`，并且在 causal 模式下跳过整块位于对角线上方的 K/V 块。
- ⚠️ 若某块分数全是 `-inf`（被掩码屏蔽）且是第一块，`new_m = -inf`，`math.exp(-inf - (-inf))` 得到 `nan`，结果全部变 NaN。本例没有掩码，不会触发。

### 3.3 `KVCache` 类

```python
class KVCache:
    def __init__(self):
        self.K = []
        self.V = []

    def append(self, k, v):
        self.K.append(k)
        self.V.append(v)

    def __len__(self):
        return len(self.K)
```

- 最简单的缓存：两个不断增长的列表。实现 `__len__` 后就可以直接写 `len(cache)`。
- 讲义中的版本按 `[layer][head]` 组织（每层、每个 KV 头一份），本代码只演示**单层单头**。真实模型中缓存形状通常是 `(层数, 2, batch, KV 头数, 序列长度, d_head)`。
- ⚠️ Python 列表 `append` 是均摊 O(1) 的动态扩容；GPU 上若也"按需增长"连续数组，会遇到频繁重分配与碎片问题——这正是 PagedAttention 用固定大小块 + 页表来管理 KV cache 的原因。

### 3.4 两种解码：为什么计数一样

```python
def decode_naive(all_K, all_V, all_queries):
    outputs = []
    ops = 0
    for t, q in enumerate(all_queries):
        Ks = all_K[:t + 1]
        Vs = all_V[:t + 1]
        out = attention_full(q, Ks, Vs)
        ops += t + 1
        outputs.append(out)
    return outputs, ops


def decode_cached(all_K, all_V, all_queries):
    cache = KVCache()
    outputs = []
    ops = 0
    for q, k, v in zip(all_queries, all_K, all_V):
        cache.append(k, v)
        out = attention_full(q, cache.K, cache.V)
        ops += len(cache)
        outputs.append(out)
    return outputs, ops
```

- 两个函数在第 t 步都让第 t 个 query 对前 `t + 1` 个 K/V 做 attention，`ops` 都累加 `t + 1`，所以 N = 10 时都是 `1 + 2 + … + 10 = 55`，输出也逐位相同（差值 0.00e+00）。
- 关键在于 `decode_naive` 用的 `all_K[:t+1]` 是**预先算好**的——这本身就是"缓存"。真正的无缓存解码，每一步都要把整个前缀重新过一遍模型：重算所有前缀 token 的 K、V 投影（以及 FFN 等），并为所有前缀位置重算 attention。代码打印的星号注释正是在说明这一点："saving comes from not REcomputing earlier hidden states"。
- 讲义 Build It 第 3 步写"Naive: O(N²) = 5050. Cached: O(N) = 100"，与代码不符：代码 N = 10，两者都是 55。测验 Q9 实现了真正的无缓存版本：N = 10 时投影 55 次 vs 10 次、attention 点积 220 次 vs 55 次。
- ⚠️ `ops` 统计的是"点积次数"，没有乘以 `d_head`，只用来比较量级。

### 3.5 KV cache 显存公式与表格

```python
def kv_cache_bytes(N, n_layers, n_heads_kv, d_head, dtype=2):
    """Total KV cache bytes. dtype=2 for fp16/bf16, 1 for int8, 4 for fp32."""
    return 2 * N * n_layers * n_heads_kv * d_head * dtype
```

| 因子 | 含义 |
|------|------|
| `2` | K 和 V 各一份 |
| `N` | 上下文长度（token 数） |
| `n_layers` | 每层都有自己的 KV |
| `n_heads_kv` | **KV 头数**（GQA 下远小于 query 头数） |
| `d_head` | 每个头的维度 |
| `dtype` | 每个数的字节数 |

```python
    configs = [
        ("Llama-3.2-3B",  28, 8,   128),
        # ...
        ("DeepSeek-V3 (MLA)", 61, 1, 512),  # MLA compresses to latent; rough
    ]
    for name, L, h_kv, d_h in configs:
        for N_ctx in [2048, 32768, 131072]:
            b = kv_cache_bytes(N_ctx, L, h_kv, d_h, dtype=2)
            print(f"  {name:<24}  N={N_ctx:>7}  -> {b / 1e9:.2f} GB")
```

- 用的是 `n_heads_kv`，而不是 query 头数——这就是 GQA 省显存的地方：Llama 3 70B 有 64 个 query 头，但只有 8 个 KV 头，缓存缩小 8 倍。
- 公式是 batch = 1 的结果；并发 B 个请求就要再乘 B。
- ⚠️ DeepSeek-V3 一行是粗略估算（注释写明 "rough"）：MLA 每 token 每层实际缓存一个 512 维的压缩潜向量加 64 维的解耦 RoPE 键，共 576 个数；代码按"K、V 各 512"算成 1024 个数，高估约 1.8 倍。
- 用 `1e9` 换算成 GB（十进制）；如果用 `2**30` 则是 GiB，数字会小约 7%。Llama-3-70B 32K 的公式结果是 10.74 GB（= 10.0 GiB），讲义写的"10.4 GB"与两者都略有出入，以公式为准。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 单层单头、单 query | 把机制剥离到最小 | 真实缓存是多层多头多 batch 的张量 |
| Q/K/V 直接随机生成，不做投影 | 聚焦 attention 本身 | 看不出"重算投影"的成本，导致朴素版与缓存版计数相同 |
| `KVCache` 用 Python 列表 | 简单直观 | 生产中用预分配张量 + 分页块（PagedAttention） |
| online softmax 只对 K/V 分块 | 展示 FlashAttention 的数学核心 | 真实 kernel 还要对 Q 分块、融合到一个 GPU kernel 中、处理掩码和反向重算 |
| 测多种 tile 大小 | 证明结果与分块大小无关 | — |
| KV 表格用固定配置 | 让数字说话 | MLA 一行是粗估；真实部署还要加 batch 和其他开销 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 生成器表达式 + `zip` | `sum(x * y for x, y in zip(a, b))` | 点积的惯用写法 |
| 列表推导式 | `[dot(q, k) / math.sqrt(len(q)) for k in Ks]` | 一行算出所有分数 |
| `float("-inf")` | `m = float("-inf")` | 负无穷，作为"还没有最大值"的初始值 |
| 星号解包实参 | `max(m, *scores)` | 把列表拆成多个位置参数 |
| `if / else` 语句 | `if m == float("-inf"): exp_old = 0.0 else: ...` | 处理首块特殊情况 |
| 切片 | `Ks[start:start + tile]`、`all_K[:t + 1]` | 越界部分自动截断，最后一块可以不满 |
| `range(start, stop, step)` | `range(0, len(Ks), tile)` | 按块遍历 |
| 类与 `__init__` | `class KVCache: def __init__(self)` | 定义带状态的对象 |
| 魔术方法 `__len__` | `def __len__(self): return len(self.K)` | 让 `len(cache)` 可用 |
| `enumerate` | `for t, q in enumerate(all_queries)` | 同时得到步号和 query |
| 三路 `zip` | `for q, k, v in zip(all_queries, all_K, all_V)` | 同时遍历三个列表 |
| 多返回值 | `return outputs, ops`；`naive, naive_ops = decode_naive(...)` | 返回元组并解包 |
| 默认参数 | `def kv_cache_bytes(..., dtype=2)`、`tile=4` | 调用时可省略 |
| 嵌套生成器表达式 | `max(abs(a - b) for va, vb in zip(naive, cached) for a, b in zip(va, vb))` | 两层循环写在一个表达式里，求全局最大误差 |
| f-string 格式符 | `f"{err:.2e}"`、`f"{name:<24}"`、`f"{N_ctx:>7}"`、`f"{b / 1e9:.2f}"` | `.2e` 科学计数法；对齐与占宽 |
| 整除 | `N * (N + 1) // 2` | 保证结果是整数 |

---

## 6. 运行结果解读

实际运行（Python 3.13）输出：

```text
=== naive vs KV-cached decoding on N=10 tokens ===
naive attention ops:  55  (O(N^2) = 55)
cached attention ops: 55  (O(N) with per-step cost, unchanged)
outputs match (max abs diff over all tokens): 0.00e+00

* naive has same per-step cost; saving comes from not REcomputing earlier
  hidden states. counting K,V recomputes would make naive O(N^2) in matmuls.
```

- 两者都是 55，输出差为 0——因为两个函数做的是完全相同的计算（见 3.4）。这一段证明了"缓存后的结果与重新计算一致"，但没有证明"省了多少"。
- 想看到差距，需要把 K/V 投影和前缀重算也计入（测验 Q9：投影 55 vs 10，attention 220 vs 55）。

```text
=== tiled-softmax (Flash) vs standard softmax agreement ===
  tile=  1  max abs diff = 2.22e-16
  tile=  2  max abs diff = 1.94e-16
  tile=  4  max abs diff = 2.22e-16
  tile=  8  max abs diff = 1.11e-16
  tile= 32  max abs diff = 1.11e-16
  bit-identical up to floating-point reassociation. no approximation.
```

- 无论 tile 是 1（逐个处理）还是 32（大于序列长度，等于一次性处理），误差都在 `1e-16` 量级，即双精度浮点的机器精度。
- 严格说这不是"bit-identical"（按位完全相同），而是"数学上精确、浮点上因运算顺序不同而有末位差异"——讲义的说法是"modulo fp16 non-associativity"。重点是：**没有任何近似**。

```text
=== KV cache size table (fp16) ===
  Llama-3.2-3B              N= 131072  -> 15.03 GB
  Llama-3-8B                N=  32768  -> 4.29 GB
  Llama-3-70B               N=  32768  -> 10.74 GB
  Llama-3-70B               N= 131072  -> 42.95 GB
  Llama-3.1-405B            N= 131072  -> 67.65 GB
  Qwen2.5-72B               N= 131072  -> 42.95 GB
  DeepSeek-V3 (MLA)         N= 131072  -> 16.37 GB
  ...
takeaway: at 128K context, 70B-class dense models use 10+ GB just for KV.
```

- 缓存大小与 N 严格线性：32K → 128K 正好 ×4。
- Llama-3-70B 在 32K 时约 10.7 GB（讲义的约 10 GB）；128K 时约 43 GB，**单个请求就超过一张 40 GB A100**（讲义说"需要 40 GB A100 的大部分"，实际已经超过）。
- 3B 小模型在 128K 时也要 15 GB——上下文长度对显存的影响往往比模型大小更显著。
- DeepSeek-V3 虽然有 61 层、总参数 671B，但 128K 时的缓存（代码粗估 16.4 GB，按 576 维实际约 9.2 GB）远小于 Llama-3-70B——这就是 MLA 的威力。

---

## 7. 动手改一改

1. **真正的无缓存解码**：给每个 token 一个输入向量 X 和投影矩阵 Wq/Wk/Wv，实现每步重算整个前缀的版本，统计投影与 attention 次数（参考测验 Q9），把 N 改为 100，复现讲义说的量级差距。
2. **加因果掩码的分块 softmax**：给 `tiled_softmax_dot` 增加 `mask` 参数（被屏蔽位置分数为 `-inf`），并修复"首块全屏蔽导致 NaN"的问题（`new_m == -inf` 时跳过该块）。
3. **多 query 分块**：把 `tiled_softmax_dot` 扩展为对一组 queries 同时计算，每个 query 维护自己的 `(m, s, out)`，实现完整的"Q 分块 × K/V 分块"双层循环。
4. **按层按头的缓存**：把 `KVCache` 改成讲义中的 `[layer][head]` 结构，并加一个 `nbytes(dtype)` 方法，用 `kv_cache_bytes` 验证。
5. **前缀缓存（讲义练习 2）**：对一个公共前缀 P 只填充一次 KV，再为 3 个不同的续写分别 `copy` 一份缓存继续解码，统计相比"每次重编码 P"节省的投影次数。
6. **PagedAttention 玩具版（讲义练习 3）**：用 16 token 的块 + 空闲链表管理 KV，模拟 1000 个长度随机的请求，比较与"按最大长度连续预分配"的显存浪费率。

---

## 8. 常见坑

- **以为 KV cache 让总复杂度变成 O(N)**：它让每一步从 O(N²) 降到 O(N)，生成 N 个 token 的总 attention 仍是 O(N²)，而且显存随 N 线性增长。
- **online softmax 只缩放 `s` 不缩放 `out`**：结果只在最大值从不变化时碰巧正确，极难发现。
- **全屏蔽块导致 NaN**：`-inf - (-inf) = nan`，需要跳过或特判。
- **KV 公式用了 query 头数**：GQA 模型要用 KV 头数，否则会高估 4–8 倍。
- **忘记乘 batch**：表格是单请求的大小，并发请求数直接线性放大显存需求。
- **GB 与 GiB 混用**：`1e9` 与 `2**30` 差约 7%，做容量规划时要统一单位。
