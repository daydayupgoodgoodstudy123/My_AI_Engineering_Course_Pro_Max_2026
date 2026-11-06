# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 17 节 原生稀疏 Attention（DeepSeek NSA） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`、`typing`），无需 GPU

---

## 1. 这份代码在考察什么

代码用纯 Python 实现了 NSA 的三个分支和门控融合，并做两类计算：

1. **一次 NSA 前向（Step 1）**：1024 个 token、16 维，信号放在第 3、17、28 块（块大小 32）；对一个与信号对齐的 query 依次计算压缩分支、top-k 块选择、选择分支、滑动窗口分支，最后用门控加权；打印各分支的 key 数、选中的块以及是否命中信号块。
2. **计算量估算（Step 2、3）**：用公式 `N/l + k·l + W` 估算 4k–256k 上下文下每个 query 需要看的 key 数，与全注意力的 N 比较；再在 64k 下扫描 `(l, k)`。

对应讲义的核心概念：三分支结构、"压缩分数兼作路由信号"、计算预算公式、收益随长度增长。

> 一句话：**把"全注意力看 N 个 key"变成"看 N/l 个摘要 + k 个块 + W 个近邻"，并用数字展示 64k 时约 25 倍的节省**。但它只做前向、不训练，压缩用均值、门控是随机权重，key 计数也有重复——"原生可训练"这一核心卖点在代码里并没有被演示（见 3.6、3.7）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `dot` / `softmax` / `attention` | 函数 | 单个 query 的缩放点积注意力，返回权重和输出 | 注意力原语 |
| `compress_mean` | 函数 | 每 `l` 个向量取均值，得到块摘要（向上取整块数） | 压缩分支（mean-pool 版） |
| `top_k_blocks` | 函数 | 按分数取前 k 个块的下标，再按位置排序 | 块选择 |
| `fine_grained_keys` | 函数 | 取出选中块的原始 K、V | 选择分支的数据加载 |
| `sliding_window` | 函数 | 取最后 `W` 个 K、V | 滑动窗口分支 |
| `gate` | 函数 | `sigmoid(q · Wg[i])`，输出 3 个门控值 | 分支门控 |
| `NSAConfig` | dataclass | `l, k, W` 三个超参 | 配置 |
| `nsa_step` | 函数 | 串起三个分支与门控，返回输出和统计信息 | NSA 前向 |
| `synthesize_sequence` | 函数 | 生成"信号块 + 噪声"的 K、V 和对齐的 query | 合成数据 |
| `count_full_attention` / `count_nsa` | 函数 | 每 query 的 key 数公式 | 计算预算 |
| `main` | 函数 | Step 1–3 | 入口 |

数据流：`synthesize_sequence` → `K, V, q`；随机生成门控权重 `Wg` → `nsa_step`：`compress_mean(K), compress_mean(V)` → `attention`（压缩分支，得到 `cmp_w`）→ `top_k_blocks(cmp_w)` → `fine_grained_keys` → `attention`（选择分支）→ `sliding_window` → `attention`（窗口分支）→ `gate` → 加权求和 → 打印统计；Step 2/3 只调用 `count_nsa`。

---

## 3. 逐段精讲

### 3.1 注意力原语

```python
def attention(q, K, V):
    d = len(q)
    scale = math.sqrt(d)
    scores = [dot(q, k) / scale for k in K]
    w = softmax(scores)
    d_v = len(V[0])
    out = [sum(w[j] * V[j][c] for j in range(len(V))) for c in range(d_v)]
    return w, out
```

- 单个 query 对一组 key 做缩放点积注意力：分数 `(len(K),)`，权重 `(len(K),)`，输出 `(d_v,)`。
- 三个分支都复用这个函数，只是传入的 K、V 不同——这正是 NSA 的思路："对同一个 query，在三种不同视图的 KV 上各做一次注意力"。
- 这里没有因果 mask：场景是 decode，K、V 都是"已生成的历史"，query 是当前位置。

### 3.2 压缩分支：`compress_mean`

```python
def compress_mean(K, l):
    n = len(K)
    d = len(K[0])
    n_blocks = (n + l - 1) // l
    out = []
    for b in range(n_blocks):
        start, end = b * l, min((b + 1) * l, n)
        block = K[start:end]
        summary = [sum(row[c] for row in block) / len(block) for c in range(d)]
        out.append(summary)
    return out
```

- `(n + l - 1) // l` 是向上取整：1024 个 token、l = 32 得到 32 个块；若 n 不能整除，最后一块较短，`min(...)` 与 `len(block)` 保证不越界、均值正确。
- K 和 V 都被压缩（`nsa_step` 中分别调用），得到 `K_cmp`、`V_cmp` 各 32 个向量。
- docstring 说明："Real NSA uses a learned MLP here — mean-pool is the pedagogical baseline." 均值的问题是**稀释**：块里只有一个关键 token 时，信号被除以 l。测验 Q9 的实验显示，单 needle 情形下 mean-pool 的 top-4 命中率只有约 32%，而理想的"块内最大点积"为 100%。

### 3.3 选择分支：`top_k_blocks` + `fine_grained_keys`

```python
def top_k_blocks(scores, k):
    indexed = sorted(range(len(scores)), key=lambda i: -scores[i])
    return sorted(indexed[:k])
```

- 按分数降序排列块下标，取前 k 个，再按位置升序返回（保持原始顺序，便于连续读取）。
- `nsa_step` 传入的是压缩分支的**softmax 权重** `cmp_w`。softmax 单调，用权重或原始分数排序结果相同。这就是讲义说的"compressed-branch scores double as the signal for top-k selection"。

```python
def fine_grained_keys(K, V, l, block_indices):
    k_out, v_out = [], []
    for b in block_indices:
        start, end = b * l, min((b + 1) * l, len(K))
        k_out.extend(K[start:end])
        v_out.extend(V[start:end])
    return k_out, v_out
```

- 把选中块的**原始** K、V 拼起来，选择分支在这 `k × l = 128` 个 token 上做普通注意力。
- 这里选择块大小与压缩块大小相同（都是 l）；讲义也写"`b` the selected block size (typically equals `l`)"。

### 3.4 滑动窗口与门控

```python
def sliding_window(K, V, W):
    n = len(K)
    start = max(0, n - W)
    return K[start:], V[start:]

def gate(q, Wg):
    logits = [dot(q, Wg[i]) for i in range(3)]
    return [1.0 / (1.0 + math.exp(-x)) for x in logits]
```

- 窗口取最后 W 个 token；`max(0, ...)` 处理序列短于 W 的情况。
- 门控是"一层线性 + sigmoid"，每个门在 (0, 1) 之间、互相独立，三者之和不必为 1（讲义："They do not have to sum to 1"）。
- ⚠️ `Wg` 在 `main` 中是随机高斯权重，从未训练，所以打印的门控值 `0.337 / 0.364 / 0.457` 没有语义——讲义练习 3 要求验证的"随机 query 时接近均匀、query 命中远处块时偏向选择分支"需要训练才能出现。

### 3.5 `nsa_step`：组合与统计

```python
    K_cmp = compress_mean(K, cfg.l)
    V_cmp = compress_mean(V, cfg.l)
    cmp_w, cmp_out = attention(q, K_cmp, V_cmp)

    picks = top_k_blocks(cmp_w, cfg.k)
    K_sel, V_sel = fine_grained_keys(K, V, cfg.l, picks)
    if K_sel:
        _, sel_out = attention(q, K_sel, V_sel)
    else:
        sel_out = [0.0] * len(q)

    K_win, V_win = sliding_window(K, V, cfg.W)
    _, win_out = attention(q, K_win, V_win)

    g = gate(q, Wg)
    combined = [g[0] * cmp_out[i] + g[1] * sel_out[i] + g[2] * win_out[i]
                for i in range(len(cmp_out))]
```

- 完全对应讲义公式 `out = g_cmp * out_cmp + g_sel * out_sel + g_win * out_win`。
- `if K_sel:` 防止 k = 0 时对空列表做 softmax（`max([])` 会报错）；`sel_out = [0.0] * len(q)` 隐含假设 `d_v == d`。
- 统计信息：

```python
        "total_keys": len(K_cmp) + len(K_sel) + len(K_win),
```

  ⚠️ 直接相加没有去重。本次运行选中块 `[3, 6, 17, 28]`，窗口覆盖位置 896–1023（块 28–31），块 28 的 32 个 key 同时被两个分支注意。去重后细粒度 key 为 224 个，总数 256 而不是 288（测验 Q5、Q10）。

### 3.6 合成数据：信号占满整块

```python
    pattern = [rng.gauss(0, 1) for _ in range(d)]
    ...                                   # 归一化为单位向量
    K = [[rng.gauss(0, 0.3) for _ in range(d)] for _ in range(n)]
    V = [[rng.gauss(0, 1) for _ in range(d)] for _ in range(n)]
    for b in signal_blocks:
        start, end = b * l, min((b + 1) * l, n)
        for i in range(start, end):
            K[i] = list(pattern)
    q = list(pattern)
```

- 信号块中**每个** token 的 key 都等于 pattern，query 也是 pattern，所以 `q · k_signal = 1`，块均值也正好是 pattern——mean-pool 不会稀释信号，top-k 选择必然命中。
- 噪声 key 每维 `N(0, 0.3²)`，与 query 的点积约 `N(0, 0.09)`；块均值后噪声进一步缩小。
- 即便如此，压缩分支的权重仍然很"平"：信号块约 0.039，均匀值 1/32 ≈ 0.031。说明压缩分支的输出本身区分度不高，但作为排序信号足够。
- 这个设定让 Step 1 的"signal blocks retrieved: [3, 17, 28] (missed: [])"几乎是必然结果。把信号改成单个 token 才是真正的 needle 测试（测验 Q9）。

### 3.7 计算量公式与扫描

```python
def count_nsa(N: int, l: int, k: int, W: int) -> int:
    return (N // l) + (k * l) + W
```

- 对应讲义 `N/l + k·b + W`（b = l）。
- ⚠️ 用 `N // l`（向下取整），而 `compress_mean` 是向上取整；N 不是 l 的倍数时少算一个压缩 key（N = 1000、l = 32 时 31 对 32）。
- ⚠️ 不去重（同 3.5），也不计门控、压缩 MLP 和 softmax 等固定开销；它统计的是"key 数"，不是 FLOPs 或时间。
- **收益上限**：`N / (N/l + k·l + W) → l`。Step 2 中节省倍数从 6.4（4k）增长到 46.5（256k），继续增大 N 会逼近 64（2²⁴ 时 63.6）。讲义"The benefit grows with sequence length"成立，但有天花板。
- Step 3 的扫描显示 l 并非越大越好：`(l, k) = (128, 8)` 与 `(64, 8)` 都是 2,048 个 key，因为选择分支 `k·l` 随 l 线性增长；`(128, 32)` 升到 5,120。

### 3.8 "原生可训练"在代码里体现了吗？

- 代码只有前向，没有损失、没有反向、没有参数更新；`gate` 的权重是随机的，压缩是固定的均值。结尾 takeaway "Gradient flows through the compressed-branch scores, so top-k selection is natively trainable" 是对讲义的复述，并没有被代码验证。
- 从 `nsa_step` 的结构可以读出梯度路径：`K_cmp`（及压缩 MLP）的梯度只来自 `cmp_out`；`picks` 是整数下标，选择分支的损失不会经由它传回压缩分支；选中块上的 `attention(q, K_sel, V_sel)` 对 `q` 和原始 K/V 可微。讲义说 top-k 是"a no-op on the forward computational graph"不够准确——它改变了 `sel_out` 在哪些 token 上计算；更准确的说法是它在**反向**图上不传梯度（测验 Q12）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| mean-pool 压缩 | 无参数、易懂 | 单 token 信号被稀释为 1/l，路由不可靠；真实 NSA 用可学习 MLP，与模型联合训练 |
| 选择复用压缩分支分数 | 不需要额外路由器，这是 NSA 的核心设计 | 选择本身无梯度，路由质量依赖压缩分支学得好 |
| 选择块大小 = 压缩块大小 | 代码简单 | 讲义也这样假设；真实实现中二者可以不同，压缩也可以带重叠步长 |
| 随机门控权重 | 演示门控融合的形式 | 门控值无意义；需训练后才会"按 query 偏向某分支" |
| 单 query、无 batch、无多头 | 纯 Python 可读 | 无法体现 GQA 组共享选择与 kernel 的访存摊薄（NSA 实际速度来源） |
| 信号占满整块的合成数据 | 保证演示成功 | 过于理想，无法暴露 mean-pool 的弱点 |
| 计数公式不去重、向下取整 | 与讲义公式一致 | 选中块与窗口重叠时高估，N 非整数倍时略低估；且 key 数 ≠ 实际耗时 |
| 不建模 KV 存储 | 聚焦计算量 | 容易误以为 NSA 降低了 KV cache 容量；实际需保留全部原始 KV |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许 `tuple[List[float], dict]` 等注解 |
| 向上取整整除 | `(n + l - 1) // l` | 不用 `math.ceil` 的整数写法 |
| 切片 | `K[start:end]`、`K[start:]` | 取子列表；越界的 end 会自动截断 |
| `min` / `max` 防越界 | `min((b + 1) * l, n)`、`max(0, n - W)` | 处理最后一块不完整、序列比窗口短的情况 |
| `sorted` + `key=lambda` | `sorted(range(len(scores)), key=lambda i: -scores[i])` | 按分数降序排下标；`-` 号实现降序 |
| 切片后再排序 | `sorted(indexed[:k])` | 取前 k 个后按位置升序 |
| `list.extend` | `k_out.extend(K[start:end])` | 把一个列表的元素逐个追加（`append` 会追加整个列表） |
| 空列表的真值 | `if K_sel:` | 空列表为假，用于防止对空序列做 softmax |
| `[0.0] * n` | `sel_out = [0.0] * len(q)` | 全零列表 |
| 嵌套列表推导式 | `[[rng.gauss(0, 0.3) for _ in range(d)] for _ in range(n)]` | 生成 n × d 的矩阵 |
| `list(x)` 复制 | `K[i] = list(pattern)` | 每个位置一份独立副本，避免多个位置共享同一列表对象 |
| `@dataclass` | `class NSAConfig: l: int; k: int; W: int` | 用关键字参数构造配置：`NSAConfig(l=l, k=k, W=W)` |
| 返回字典作为统计 | `info = {"cmp_keys": ..., "gates": g}` | 灵活返回多项结果，按键取用 |
| 带条件的推导式 | `[b for b in info["selected_blocks"] if b in signal_blocks]` | 过滤出命中的信号块 |
| 数字下划线 | `65_536`、`131_072` | 可读性分隔符 |
| f-string 格式符 | `{nsa:>10,}`、`{full/nsa:>8.1f}x`、`{info['gates'][0]:.3f}` | 千分位、右对齐、小数位；f-string 内可写表达式与字典取值 |
| 元组列表遍历 + 解包 | `for N_prod, l_prod, k_prod, W_prod in [(4_096, 32, 8, 256), ...]:` | 一次取出一组配置 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行，测验中可复用各函数 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（约 0.05 秒），完整关键输出：

```text
Step 1: synthetic N=1024, d=16, signal at blocks [3, 17, 28]
        config: l=32 (compression block), k=4 (top-k), W=128 (sliding window)
  compressed branch keys : 32
  selected branch keys   : 128  (blocks [3, 6, 17, 28])
  sliding window keys    : 128
  total keys attended    : 288
  full-attention keys    : 1024  (3.6x more)
  gate weights (cmp/sel/win): 0.337 / 0.364 / 0.457

  signal blocks retrieved: [3, 17, 28]  (missed: [])

Step 2: compute savings at production context lengths
         N    l    k     W    NSA keys   full keys    savings
      4096   32    8   256         640      4,096       6.4x
     16384   32   16   512       1,536     16,384      10.7x
     32768   64   16   512       2,048     32,768      16.0x
     65536   64   16   512       2,560     65,536      25.6x
    131072   64   16   512       3,584    131,072      36.6x
    262144   64   16   512       5,632    262,144      46.5x

Step 3: block-size vs top-k sweep (cost at N=65536, W=512)
     l    k      keys   vs full
    32    8     2,816     23.3x
    32   16     3,072     21.3x
    32   32     3,584     18.3x
    64    8     2,048     32.0x
    64   16     2,560     25.6x
    64   32     3,584     18.3x
   128    8     2,048     32.0x
   128   16     3,072     21.3x
   128   32     5,120     12.8x
```

逐项解读：

- **Step 1 的 key 数**：`32 + 128 + 128 = 288`，与讲义"`32 + 128 + 128 = 288` keys per query versus 1024 ... 3.5x fewer"一致（代码打印 3.6 是四舍五入的 3.56）。去重后为 256（块 28 与窗口重叠）。
- **选中块**：3 个信号块全部命中，第 4 个名额给了噪声块 6——k = 4 大于信号块数时总会带上一个"陪跑"块。这也是信号占满整块的理想设定下的结果。
- **门控值**：随机权重的 sigmoid 输出，没有含义。
- **Step 2**：节省倍数随 N 增长（6.4 → 46.5），64k、128k 分别为 25.6、36.6 倍，对应讲义的"25x"和"36x"。增长逐渐放缓，极限为 l = 64。
- **Step 3**：64k 下最省的是 `(64, 8)` 与 `(128, 8)`（各 2,048 个 key，32 倍），但 k = 8 意味着每个 query 只能精确读取 8 个远处块，召回可能不足——讲义练习 1 要求在"95% needle 召回"约束下选预设，这张表只给出了成本的一半信息。

---

## 7. 动手改一改

1. **去重计数**：在 `nsa_step` 中计算选择块与窗口的交集，打印"去重后的细粒度 key 数"（Step 1 应为 224），并把 `count_nsa` 的压缩项改为向上取整。
2. **单 needle 测试**：改写 `synthesize_sequence`，只让一个随机位置的 key 等于 pattern，重复 200 次统计 top-4 命中率（mean-pool 约 32%）；再试试把压缩改为"块内 key 与 query 点积的最大值"（理想上限）或"块内向量的逐维最大值"，比较命中率。
3. **讲义练习 1 · 预设扫描**：取三组 `(l, k, W)`，在 1024 或 4096 长度上用单 needle 测试测召回，找出"召回 ≥ 95% 时 key 数最少"的预设。
4. **讲义练习 3 · 门控**：构造两类 query——随机 query 和与远处某块对齐的 query；手工设定或用简单梯度下降学习 `Wg`，使后者的 `g_sel` 明显更大。
5. **讲义练习 4 · KV 预算**：写函数计算 70B 级模型（80 层、8 KV 头、head_dim 128、BF16）在 128k 下的 KV 存储（全注意力约 42.9 GB，NSA 约 43.6 GB）与每步读取 key 数（131,072 对 3,584），并求读取量打平的长度（约 1,560）。
6. **进阶 · 梯度路径**：用 PyTorch 或手写自动微分实现 `nsa_step`，打印 `K_cmp` 的梯度只来自压缩分支、`picks` 不产生梯度，验证测验 Q12 的分析。

---

## 8. 常见坑

- **以为 NSA 降低了 KV cache 容量**：所有原始 KV 都要保留，节省的是每步的读取与计算。
- **把 key 数当成速度**：稀疏访存、分支与门控开销、kernel 设计决定实际速度；短序列下 NSA 可能更慢（讲义：16k 以下不划算）。
- **重复计数**：选中块与滑动窗口可能重叠，统计"读了多少 KV"时要去重。
- **用 mean-pool 判断 NSA 的召回能力**：均值会稀释单 token 信号；真实 NSA 的压缩 MLP 是学出来的。
- **以为 top-k 有梯度**：选择下标不可微，路由质量靠压缩分支的端到端训练"顺带"学到。
- **以为收益无限增长**：每 query key 数的节省倍数上限约为 l。
- **把稠密模型直接换成 NSA**：讲义明确说必须继续训练，否则模型不会通过稀疏模式路由信息。
- **混淆 NSA 与推理期剪枝**：H2O、StreamingLLM 永久丢弃 KV；NSA 保留全部 KV，按 query 动态选择。
