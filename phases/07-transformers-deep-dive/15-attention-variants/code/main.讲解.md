# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 15 节 Attention 变体 — 滑动窗口、稀疏、差分 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码不训练模型，而是用纯 Python 把几种 attention 变体的"形状"和"账单"摆在你面前：

1. **掩码就是拓扑**：全因果、滑动窗口、局部 + 跨步三种掩码，在 8 个 token 上画成 ASCII 图，并数出各自关注了多少个格子。
2. **带掩码的 softmax 怎么写**：被遮住的位置权重为 0，整行被遮住时不产生 NaN。
3. **差分注意力的计算方式**：两组权重相减，`A1 − λ·A2`，权重可以为负。
4. **KV cache 的显存账**：Llama-3-70B 形状、128K 上下文下，全注意力、SWA、Gemma-3 5:1 混合、差分注意力分别要多少 GB。
5. **批判性阅读**：代码的 attention sink 演示用的是随机向量，输出并没有展示出汇点——学会对照输出检验注释，本身就是这节课的一部分。

> 一句话：**attention 变体的本质是"改掩码 + 改账单"**，这份代码把两者都算给你看。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `NEG_INF` | 常量 | `float("-inf")`，表示"不可见" | 掩码填充值 |
| `causal_mask(n)` | 函数 | 下三角掩码 | 全因果 attention |
| `swa_mask(n, window)` | 函数 | 每行只开放最近 `window` 个位置 | 滑动窗口 attention |
| `strided_mask(n, window, stride)` | 函数 | 局部窗口 + 每隔 `stride` 列开放一列 | 局部 + 跨步稀疏 |
| `count_nonmasked(M)` | 函数 | 数值为 0.0 的格子数 | 计算量的代理指标 |
| `render(M, label)` | 函数 | 把掩码画成 `x` / `.` 图 | 可视化 |
| `softmax(xs)` | 函数 | 数值稳定的 softmax | — |
| `attention_row(q, Ks, Vs, mask_row)` | 函数 | 单个 query 的带掩码 attention | 缩放点积 attention |
| `diff_attention_row(...)` | 函数 | 两次 attention 的权重相减 | 差分注意力 |
| `kv_cache_bytes(...)` | 函数 | KV cache 字节数公式 | 推理显存 |
| `main()` | 函数 | 三段演示：掩码图、汇点演示、KV 账单 | — |

调用关系：`main` → `render(causal/swa/strided_mask)` → `count_nonmasked`；`diff_attention_row` → 两次 `attention_row` → `softmax`；最后 `kv_cache_bytes` 算出全注意力基线，其他变体按比例缩放。

---

## 3. 逐段精讲

### 3.1 三种掩码

```python
NEG_INF = float("-inf")


def causal_mask(n):
    M = [[NEG_INF] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            M[i][j] = 0.0
    return M


def swa_mask(n, window):
    M = [[NEG_INF] * n for _ in range(n)]
    for i in range(n):
        lo = max(0, i - window + 1)
        for j in range(lo, i + 1):
            M[i][j] = 0.0
    return M
```

- **加性掩码约定**：0.0 表示"可见"（加到分数上不改变分数），`-inf` 表示"不可见"（加上后 `exp(-inf) = 0`）。这和 PyTorch 里 `attn_mask` 的浮点约定一致。
- **先全部填 `-inf`，再打开允许的位置**：默认拒绝，只放行需要的，逻辑更不容易出错。
- `[[NEG_INF] * n for _ in range(n)]`：每一行都是新建的列表。如果写成 `[[NEG_INF] * n] * n`，n 行会指向同一个列表对象，改一格等于改整列。
- **SWA 的窗口**：位置 i 看 `[i − window + 1, i]`，正好 `window` 个位置（含自己）。`max(0, ...)` 处理序列开头窗口不满的情况。`window ≥ n` 时退化为全因果；`window = 1` 时只看自己。
- 讲义的 Step 1 里 `causal_mask` 用的是一行列表推导，代码里用的是双重循环，两种写法结果相同。

### 3.2 局部 + 跨步稀疏掩码

```python
def strided_mask(n, window, stride):
    M = [[NEG_INF] * n for _ in range(n)]
    for i in range(n):
        lo = max(0, i - window + 1)
        for j in range(lo, i + 1):
            M[i][j] = 0.0
        for j in range(0, i + 1, stride):
            M[i][j] = 0.0
    return M
```

- 两个循环叠加：先打开局部窗口，再打开第 0、stride、2·stride…… 列（只要不超过 i，保持因果）。
- 被两个循环同时打开的格子只是重复赋值 0.0，不会重复计数。
- ⚠️ 这里的"跨步列"是**从序列开头起算的固定列**（0、3、6……），所有 query 共享同一批"汇总位置"。Child et al.（2019）原论文的 strided 模式是按相对距离 `(i − j) mod stride == 0` 取位置。两种都是常见稀疏模式，读论文时要注意区分。
- 讲义称这类模式的计算量为 `O(N·√N)`（窗口与步长都取约 √N 时）。

### 3.3 计数与可视化

```python
def count_nonmasked(M):
    return sum(1 for row in M for v in row if v == 0.0)


def render(M, label):
    n = len(M)
    print(f"{label}  ({count_nonmasked(M)} / {n*n} cells attended)")
    for i in range(n):
        cells = "".join("x" if M[i][j] == 0.0 else "." for j in range(n))
        print(f"  {i:>2} | {cells}")
    print()
```

- `sum(1 for row in M for v in row if v == 0.0)`：带两层 `for` 和一个 `if` 的生成器表达式，等价于"双重循环 + 计数器"。
- 被关注的格子数是 attention 计算量的代理：每个格子对应一次 `q·k` 点积。
- `"x" if ... else "."` 条件表达式 + `"".join(...)` 把一行拼成字符串，画出来和讲义里的示意图一致。

### 3.4 带掩码的 attention：先过滤、再 softmax、再放回

```python
def softmax(xs):
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps)
    return [e / s for e in exps]


def attention_row(q, Ks, Vs, mask_row):
    d = len(q)
    scores = []
    for k, m in zip(Ks, mask_row):
        if m == NEG_INF:
            scores.append(NEG_INF)
        else:
            s = sum(qi * ki for qi, ki in zip(q, k)) / math.sqrt(d)
            scores.append(s)
    finite = [s for s in scores if s != NEG_INF]
    if not finite:
        return [0.0] * len(Vs[0]), [0.0] * len(scores)
    shifted = softmax(finite)
    weights = []
    k = 0
    for s in scores:
        if s == NEG_INF:
            weights.append(0.0)
        else:
            weights.append(shifted[k])
            k += 1
    # ...（按权重对 V 加权求和）
    return out, weights
```

- **softmax 减最大值**：`exp(x − m)` 与 `exp(x)` 归一化后结果相同，但避免了大分数时 `exp` 溢出。
- **被遮住的位置根本不算点积**：直接记 `-inf`，省掉无用计算——这就是稀疏 attention"省计算"的最朴素形式。
- **只对有限值做 softmax**：再用游标 `k` 按顺序把权重放回原位置，被遮住的位置填 0。这样完全避免了 `-inf` 参与算术。
- **整行被遮住时返回全 0**：如果对全 `-inf` 的行直接 softmax，`m = -inf`，`x − m = nan`，所有权重变成 `nan`。PyTorch 里 padding 掩码遇到整行被遮时也会出现同样的 NaN 问题。
- 除以 `math.sqrt(d)`：缩放点积，防止 softmax 饱和。
- ⚠️ 函数返回 `(out, weights)` 两个值，`main` 里只用到了 `weights`（`_, w_single = ...`），因为演示关心的是权重分布。

### 3.5 差分注意力

```python
def diff_attention_row(q1, q2, K1, K2, V, mask_row, lam):
    _, w1 = attention_row(q1, K1, V, mask_row)
    _, w2 = attention_row(q2, K2, V, mask_row)
    diff = [a - lam * b for a, b in zip(w1, w2)]
    d_v = len(V[0])
    out = [0.0] * d_v
    for w, v in zip(diff, V):
        for j in range(d_v):
            out[j] += w * v[j]
    return out, diff
```

- 对应公式 `DiffAttn = (A1 − λ·A2)·V`：两组独立的 Q/K 得到两份权重，相减后再对**同一份 V** 加权求和。
- 因为 `w1`、`w2` 各自和为 1，`diff` 的和为 `1 − λ`；个别位置可以为负。
- 设计意图：如果两张图里都有一个"共模"成分（比如都把权重倒给第 0 个 token），相减就能把它抵消，剩下与内容相关的差异。
- ⚠️ 简化之处：λ 是固定传入的常数，真实模型中是可学习参数；DIFF Transformer 论文还会对每个头的输出做归一化并乘以 `(1 − λ_init)` 来稳定幅度，这里没有。
- ⚠️ 这个函数用了两组 K、一组 V，所以按它的结构，推理时 KV cache 应为全注意力的 **1.5 倍**（K1、K2、V），而 `main` 里是按 `full * 2` 打印的（详见 3.7 节）。

### 3.6 汇点演示：读输出，而不是只读注释

```python
    rng = random.Random(0)
    d = 8
    K = [[rng.gauss(0, 1) for _ in range(d)] for _ in range(8)]
    V = [[rng.gauss(0, 1) for _ in range(d)] for _ in range(8)]
    q = [rng.gauss(0, 1) for _ in range(d)]
    mask = causal_mask(8)[7]
    _, w_single = attention_row(q, K, V, mask)
    # ...
    q1 = q[:]
    q2 = [x + 0.2 * rng.gauss(0, 1) for x in q]
    K2 = [[x + 0.2 * rng.gauss(0, 1) for x in row] for row in K]
    _, w_diff = diff_attention_row(q1, q2, K, K2, V, mask, lam=0.5)
```

- `random.Random(0)`：独立的随机数生成器对象并固定种子，不影响全局 `random` 状态，结果可复现。
- `causal_mask(8)[7]`：取最后一行，即第 7 个 token 作为 query，能看到全部 8 个位置。
- `q[:]`：切片复制一份列表，后续修改 `q1` 不会影响 `q`。
- ⚠️ **演示和注释对不上**：K、V、q 都是独立高斯随机数，没有任何机制让位置 0 特殊。实际输出中位置 0 的权重是 0.018，是 8 个里最小的，并不存在"汇点"。attention sink 是训练出来的现象，随机向量不会自发产生。
- ⚠️ **差分没有起到"抵消"作用**：`q2`、`K2` 只是 `q`、`K` 加了 0.2 倍的小噪声，A2 ≈ A1，于是 `A1 − 0.5·A2 ≈ 0.5·A1`，输出的差分权重基本是单注意力权重减半，也没有出现注释中说的负权重。要看到真正的抵消效果，需要让 A2 主要捕捉共模成分（测验 Q10 给出了一个可运行的构造）。

### 3.7 KV cache 账单

```python
def kv_cache_bytes(n_layers, n_kv_heads, d_head, seq_len, dtype_bytes=2):
    return 2 * n_layers * n_kv_heads * d_head * seq_len * dtype_bytes
```

```python
    n_layers, n_kv_heads, d_head = 80, 8, 128
    N = 131072
    full = kv_cache_bytes(n_layers, n_kv_heads, d_head, N)
    # ...
    for window in (4096, 1024):
        reduced = full * (window / N)
    # ...
    gemma3_ratio = 1 / 6
    gemma_total = full * (5 / 6) * (1024 / N) + full * (1 / 6)
    # ...
    diff = full * 2
```

- **公式拆解**：`2`（K 和 V 两份）× 层数 × KV 头数 × 每头维度 × 序列长度 × 每元素字节数（fp16 = 2）。这里 8 个 KV 头是 GQA 配置（查询头更多，KV 头共享）。
- 全注意力：`2 × 80 × 8 × 128 × 131072 × 2 ≈ 42.9 GB`（按 1e9 字节为 1 GB）——单个请求就要占掉一张 80GB 卡的一半多。
- **SWA**：每层只保留最近 W 个 token，按 `W / N` 缩放，W=1024 时缩小 128 倍。
- **Gemma-3 5:1 混合**：5/6 的层按 SWA 缩放，1/6 的层保留全量，合计约为全注意力的 17%，缩小约 5.8 倍。全局层贡献了其中约 96%。
- **差分注意力**：代码按 2 倍计。如 3.5 节所说，按 `diff_attention_row` 自身的结构应为 1.5 倍；若按论文做法减半头数，则与基线大体持平。2 倍可以看作"Q/K/V 全部复制一份"的上界。
- ⚠️ `gemma3_ratio = 1 / 6` 定义了却没有使用，下面一行直接写了 `(1 / 6)`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 掩码用二维 Python 列表 + `-inf` | 直观，可以直接打印成图 | 生产中用布尔张量或 FlexAttention 的 `mask_mod` 函数，不物化 N×N |
| 被遮住的位置跳过点积 | 体现"稀疏 = 少算" | 真实内核按块跳过，需要块对齐的掩码模式 |
| 只对有限值做 softmax | 避免 `-inf` 运算和整行 NaN | PyTorch 中需要显式处理全遮蔽行 |
| 只算单个 query 行 | 代码短，聚焦权重分布 | 真实实现是批量矩阵运算 |
| 固定 λ | 便于演示 | 真实模型 λ 可学习，并配每头归一化 |
| 随机向量做汇点演示 | 无需训练 | 不能真正产生 attention sink；应构造带汇点的输入或用训练好的模型 |
| KV 按比例缩放估算 | 一行公式就能比较 | 真实系统还要算 GQA 分组、量化、分页块的碎片 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `float("-inf")` | `NEG_INF = float("-inf")` | 负无穷；`math.exp(-inf) == 0.0` |
| 列表乘法与列表推导 | `[[NEG_INF] * n for _ in range(n)]` | 外层推导保证每行是独立的列表 |
| `range(start, stop, step)` | `range(0, i + 1, stride)` | 带步长的整数序列 |
| `max` / `min` | `max(0, i - window + 1)` | 夹住下界 |
| 生成器表达式（嵌套 + 条件） | `sum(1 for row in M for v in row if v == 0.0)` | 两层循环 + 过滤后计数 |
| 条件表达式 | `"x" if M[i][j] == 0.0 else "."` | 一行内的 if/else |
| `str.join` | `"".join(...)`、`" ".join(f"{w:.3f}" for w in w_single)` | 把多个字符串拼成一个 |
| `zip` | `for k, m in zip(Ks, mask_row)` | 并行遍历多个序列 |
| 列表推导带过滤 | `[s for s in scores if s != NEG_INF]` | 只保留有限值 |
| 空列表的真值 | `if not finite:` | 空列表为假 |
| 多返回值（元组） | `return out, weights`；`_, w1 = attention_row(...)` | `_` 丢弃不用的值 |
| 切片复制 | `q1 = q[:]` | 浅拷贝一份列表 |
| `random.Random(seed)` | `rng = random.Random(0)`、`rng.gauss(0, 1)` | 独立的可复现随机数生成器；高斯采样 |
| 函数内 import | `main` 里的 `import random` | 合法，但通常放文件顶部 |
| 默认参数 | `dtype_bytes=2` | fp16 默认 2 字节 |
| 元组解包赋值 | `n_layers, n_kv_heads, d_head = 80, 8, 128` | 一行给多个变量赋值 |
| f-string 格式 | `{i:>2}`、`{w:+.3f}`、`{full / 1e9:>6.1f}`、`{N/window:.0f}` | 右对齐、带符号 3 位小数、宽 6 一位小数、取整 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时副本中执行一次）。

**第一段：掩码形状**

```text
full causal  (36 / 64 cells attended)
   ...
   7 | xxxxxxxx

sliding window (W=4)  (26 / 64 cells attended)
   0 | x.......
   1 | xx......
   2 | xxx.....
   3 | xxxx....
   4 | .xxxx...
   5 | ..xxxx..
   6 | ...xxxx.
   7 | ....xxxx

local (W=2) + strided (stride=3)  (24 / 64 cells attended)
   0 | x.......
   1 | xx......
   2 | xxx.....
   3 | x.xx....
   4 | x..xx...
   5 | x..xxx..
   6 | x..x.xx.
   7 | x..x..xx
```

- 全因果：`8·9/2 = 36`。
- SWA：前 4 行窗口未满（1+2+3+4 = 10），后 4 行各 4 个（16），共 26。从第 4 行开始，窗口像一条宽度为 4 的对角带向右下滑动。
- 局部 + 跨步：第 0 列和第 3 列是所有后续行共享的"跨步列"（第 6 列对第 6、7 行也是），其余是宽度 2 的局部带。第 2 行的 `xxx` 来自局部窗口（1、2）加跨步列 0。n 只有 8 时节省不明显，n 越大相对全因果省得越多。

**第二段：汇点演示**

```text
single attn weights: 0.018 0.068 0.335 0.031 0.054 0.112 0.156 0.227
  (notice the weight bleeding to position 0 — the attention sink)
diff   attn weights: +0.008 +0.030 +0.169 +0.013 +0.033 +0.039 +0.097 +0.112
  (lambda=0.5 subtracts the sink component; negative weights allowed)
```

- 位置 0 的权重 0.018 是全行最小，注释所说的"汇点"并不存在（原因见 3.6 节）。
- 差分权重之和约为 0.501 ≈ `1 − λ = 0.5`，每个值约等于单注意力权重的一半，没有负值——说明 A2 几乎就是 A1 的拷贝，差分只是在整体缩放。
- 这段输出最值得学的是：**注释和输出不一致时，相信输出，并追问原因**。

**第三段：KV cache 账单**

```text
=== KV cache @ 128K context, Llama-3-70B-ish (80 layers, 8 KV heads, d_head=128, fp16) ===
  full attention              :   42.9 GB
  SWA window= 4096             :    1.3 GB   (32x shrink)
  SWA window= 1024             :    0.3 GB   (128x shrink)
  Gemma-3 mix (5:1, W=1024)   :    7.4 GB   (5.8x shrink)
  differential attention (2x) :   85.9 GB   (pays 2x for sink-free weights)
```

- 单个 128K 请求的全注意力 KV 就要 42.9 GB。
- 纯 SWA 立省 32～128 倍，但长程检索会变差。
- 5:1 混合是折中：7.4 GB，其中约 7.1 GB 来自 1/6 的全局层。
- 差分注意力的 85.9 GB 是"全部复制一份"的上界估计，参见 3.7 节的讨论。
- 注意两行 SWA 的冒号都比其他行右移了一格：`{window:>5}` 把 4 位数的 4096、1024 补成 5 位宽（`window= 4096`），而后面的空格数是按 4 位写死的，所以没对齐。纯显示问题。

---

## 7. 动手改一改

1. 验证讲义练习 1：断言 `swa_mask(n, n) == causal_mask(n)` 对 n = 1..20 都成立；写 `swa_cells(n, W)` 闭式公式并与 `count_nonmasked` 对比。
2. 把 `strided_mask` 改成按相对距离取跨步位置（`(i − j) % stride == 0`），画出来与原版对比。
3. 加一个 BigBird 风格的 `bigbird_mask(n, window, n_global, n_random, seed)`：局部窗口 + 前 `n_global` 个全局 token（双向可见，保持因果时只做"被所有人看"）+ 每行若干随机位置。
4. 重写汇点演示：让 `K[0]` 带一个强"汇点"方向，`q1 = 内容 + 汇点`、`q2 = 汇点`，观察差分后位置 0 的权重是否接近 0（参考测验 Q10）。
5. 把 `diff = full * 2` 改成按结构计算：K1、K2、V 三份 → 1.5 倍；再加一个"头数减半"的选项，打印对比。
6. 进阶：参数化混合比例，打印 `s:g` 从 1:1 到 7:1、上下文从 32K 到 1M 的 KV 表，找出"再增加 SWA 层几乎不再省显存"的拐点。

---

## 8. 常见坑

- **`[[x] * n] * n` 共享行**：二维列表必须用推导式逐行新建，否则改一格等于改整列。
- **掩码约定混用**：有的 API 用布尔值（True = 可见或 True = 遮住，各家不同），有的用加性 `0 / -inf`。拼接不同来源的掩码前先确认约定。
- **整行被遮住导致 NaN**：padding 与稀疏模式叠加时最常见，必须单独处理。
- **以为加了掩码就省了计算**：稠密内核仍会计算整个 N×N，要用块稀疏内核才能兑现收益。
- **只看感受野不看检索**：`L × W` 是理论上限，不等于能在 100K token 之外精确找到一个数字。
- **相信注释不看输出**：本文件的汇点演示就是反例——注释写着"汇点"，输出里位置 0 的权重最小。
