# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 11 节 专家混合 (MoE) ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

用不到 150 行纯 Python，把 MoE 层里最关键的三个机制拆开给你看：

1. **top-k 路由 + softmax 门控**：路由器给每个专家打分，选 k 个，只在被选中的专家之间归一化权重，输出是加权和。
2. **无辅助损失负载均衡（DeepSeek-V3）**：每个专家一个偏置，**只参与选择、不参与门控**；按使用量高于/低于目标值 `∓γ` 调整。
3. **负载监控**：统计 1000 个 token 的专家使用次数，用熵衡量均衡程度（上限 `ln 8`）。
4. **参数量对比**：toy MoE 与"DeepSeek-V3 形状"的总参数/激活参数估算。

> 一句话：**MoE = 一个打分器 + 一个 top-k + 一个加权和**；难点不在前向，而在"让专家们被均匀地使用"。

⚠️ 先说结论：在本文件的默认参数下（`gamma=0.15`），偏置更新**并没有收敛**，而是在两个状态之间精确地来回振荡（见第 6 部分）；参数量估算部分也有明显偏差（见 3.7）。这两点恰好是很好的学习材料。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `silu(x)` | 函数 | `x · sigmoid(x)` | 专家内部的激活函数（SwiGLU 的组成部分） |
| `make_expert(d_in, d_hidden, rng)` | 函数 | 生成一个 `(d_in, d_hidden)` 的随机权重矩阵 | 一个"专家" |
| `apply_expert(x, W)` | 函数 | `silu(x @ W)` | 专家前向 |
| `route(hidden, W_router, top_k, bias)` | 函数 | 打分、按"分数 + 偏置"选 top-k、按原始分数算门控 | 路由器 + 无辅助损失技巧 |
| `moe_layer_forward(x, experts, W_router, top_k, bias)` | 函数 | 单个 token 的 MoE 输出 = Σ gate × expert(x) | MoE 层前向 |
| `update_bias(bias, usage_counts, target, gamma)` | 函数 | 超目标的专家偏置 −γ，欠目标的 +γ | DeepSeek-V3 偏置更新 |
| `run_epoch(tokens, ...)` | 函数 | 让所有 token 过一遍 MoE 层，统计每个专家被选中的次数 | 负载统计 |
| `entropy(counts)` | 函数 | 使用分布的熵 | 均衡程度指标 |
| `dense_active_params(...)` | 函数 | 计算总/激活参数（**未被调用**） | — |
| `main()` | 入口 | 构建 8 个专家 + 路由器，跑 11 轮"统计 → 更新偏置"，再打印参数估算 | — |

数据流：`main → run_epoch → moe_layer_forward → route + apply_expert`；每轮之间 `update_bias` 修改偏置，下一轮 `route` 用新偏置选择专家。

---

## 3. 逐段精讲

### 3.1 专家：一个线性层 + SiLU

```python
def silu(x):
    return x / (1.0 + math.exp(-x))


def make_expert(d_in, d_hidden, rng):
    """Tiny 'expert': input -> silu -> output. Linear for illustration."""
    scale = math.sqrt(2.0 / (d_in + d_hidden))
    W = [[rng.gauss(0, scale) for _ in range(d_hidden)] for _ in range(d_in)]
    return W


def apply_expert(x, W):
    d_hidden = len(W[0])
    out = [0.0] * d_hidden
    for i, xi in enumerate(x):
        if xi == 0.0:
            continue
        for j in range(d_hidden):
            out[j] += xi * W[i][j]
    return [silu(v) for v in out]
```

- `silu(x) = x · σ(x) = x / (1 + e⁻ˣ)`，是 SwiGLU 中门控支路使用的激活。
- 每个专家只有一个 `(16, 32)` 矩阵，Xavier 初始化（`sqrt(2 / (fan_in + fan_out))`）。真实专家是完整的 SwiGLU FFN：`W_down · (silu(W_gate · x) ⊙ (W_up · x))`，三个矩阵、先升维再降回 `d_model`。
- ⚠️ 这里专家输出维度是 `d_hidden = 32`，而不是 `d_model = 16`，所以 MoE 输出无法与输入做残差相加。由于本代码只关心路由统计，没有影响；但这不是一个能堆叠的真实层。
- ⚠️ `math.exp(-x)` 在 x 非常负（如 −1000）时会溢出抛 `OverflowError`；本例数值很小不会触发。
- 讲义 Build It 写的是"SwiGLU-ish experts (one linear each, for illustration)"，与代码一致。

### 3.2 路由：选择用偏置，门控不用

```python
def route(hidden, W_router, top_k, bias):
    E = len(W_router)
    scores = [sum(h * w for h, w in zip(hidden, W_router[e])) for e in range(E)]
    biased = [s + b for s, b in zip(scores, bias)]
    top_idx = sorted(range(E), key=lambda i: -biased[i])[:top_k]
    chosen = [scores[i] for i in top_idx]
    m = max(chosen)
    exps = [math.exp(c - m) for c in chosen]
    s = sum(exps)
    gates = [e / s for e in exps]
    return top_idx, gates
```

逐行看：

1. `scores`：路由器就是一个 `(E, d_model)` 的线性层，第 e 个分数是 token 向量与 `W_router[e]` 的点积——"这个 token 和专家 e 有多匹配"。
2. `biased`：分数加上专家偏置。偏置大的专家更容易进入 top-k。
3. `top_idx`：按**加偏置后**的分数降序排序，取前 k 个下标。`sorted(range(E), key=lambda i: -biased[i])` 是"argsort 降序"的纯 Python 写法。
4. `chosen` / `gates`：**用原始 `scores`** 在被选中的 k 个专家之间做 softmax（减最大值防溢出）。

这正是讲义强调的 DeepSeek-V3 技巧："Bias affects selection, not gate weight"——偏置只负责把 token 挪到空闲专家，模型对已选专家的加权仍由它自己的打分决定，因此均衡机制不会扭曲预测。

- 只在 top-k 内做 softmax（先选再归一化），门控和为 1。另一种常见做法是先对全部 E 个分数 softmax 再取 top-k（Switch 风格），这样门控和小于 1。
- ⚠️ 简化：DeepSeek-V3 实际用 sigmoid 计算亲和度，再在选中的专家间归一化；这里用 softmax，思想一致。
- 复杂度：每个 token 打分 O(E·d)，排序 O(E log E)；E 很大时生产中用 `topk` 算子（部分排序）。

### 3.3 MoE 层前向

```python
def moe_layer_forward(x, experts, W_router, top_k, bias):
    top_idx, gates = route(x, W_router, top_k, bias)
    d_hidden = len(experts[0][0])
    out = [0.0] * d_hidden
    for e_idx, gate in zip(top_idx, gates):
        h = apply_expert(x, experts[e_idx])
        for j in range(d_hidden):
            out[j] += gate * h[j]
    return out, top_idx
```

- 对应讲义伪代码 `h + Σ_{e∈top_k} gate · Expert_e(norm(h))` 中的求和部分（这里没有 norm 和残差）。
- 只有 k = 2 个专家被计算——这就是"稀疏激活"：8 个专家的参数都在，但每个 token 只付 2 个专家的计算。
- `zip(top_idx, gates)` 保证下标和权重一一对应。
- 返回 `top_idx` 是为了给 `run_epoch` 统计使用量。
- ⚠️ 真实实现不会逐 token 循环：会先把整个 batch 的 token 按专家分组（dispatch），每个专家对自己的一组 token 做一次大矩阵乘，再按原顺序合并回去（combine）。在专家并行中，dispatch/combine 就是跨 GPU 的 all-to-all。

### 3.4 偏置更新：符号式、固定步长

```python
def update_bias(bias, usage_counts, target, gamma):
    """Aux-loss-free balance: nudge bias up/down based on usage vs target."""
    for e in range(len(bias)):
        if usage_counts[e] > target:
            bias[e] -= gamma
        elif usage_counts[e] < target:
            bias[e] += gamma
    return bias
```

- 规则就是讲义描述的："每步之后检查每个专家的使用量是否高于/低于目标，按 `±γ` 推一下偏置"。只看**符号**，不看偏差大小。
- 这个更新**不经过反向传播**、不产生梯度，也不往损失函数里加任何项——"auxiliary-loss-free"。
- `bias` 是原地修改（列表是可变对象），同时也被 `return`，所以 `bias = update_bias(...)` 写法也成立。
- ⚠️ 固定步长的符号控制器（bang-bang 控制）在 γ 偏大时会**过冲并振荡**。本例 `γ = 0.15`，而路由分数的差距本身不大，于是每次调整都矫枉过正——详见第 6 部分。

### 3.5 统计与熵

```python
def run_epoch(tokens, experts, W_router, top_k, bias):
    usage = [0] * len(experts)
    for x in tokens:
        _, top_idx = moe_layer_forward(x, experts, W_router, top_k, bias)
        for e in top_idx:
            usage[e] += 1
    return usage


def entropy(counts):
    total = sum(counts)
    if total == 0:
        return 0.0
    ps = [c / total for c in counts if c > 0]
    return -sum(p * math.log(p) for p in ps)
```

- 每个 token 选 2 个专家，1000 个 token 共产生 2000 次选择，目标是每个专家 `1000 × 2 / 8 = 250` 次。
- `_` 接收不需要的返回值（MoE 输出），只用 `top_idx`。
- ⚠️ 为了统计使用量，`run_epoch` 也把专家前向完整算了一遍，其实只需要调用 `route`。这是本文件运行耗时（约 0.8 秒）的主要来源。
- 熵：均匀时最大为 `ln 8 ≈ 2.079`。`if c > 0` 过滤掉零计数（`0 · log 0` 按约定为 0，直接 `log(0)` 会报错）。
- 熵对轻度不均衡不敏感：使用量 206–301（相对偏差 ±20%）时熵仍有 2.072。实践中更常看"最大负载 / 平均负载"。

### 3.6 `main()`：构造与迭代

```python
    rng = random.Random(42)
    d_model = 16
    d_hidden = 32
    n_experts = 8
    top_k = 2
    n_tokens = 1000

    experts = [make_expert(d_model, d_hidden, rng) for _ in range(n_experts)]
    W_router = [[rng.gauss(0, 0.3) for _ in range(d_model)] for _ in range(n_experts)]

    # Synthetic tokens with some structure so routing isn't uniform to start.
    tokens = [[rng.gauss(0, 1) for _ in range(d_model)] for _ in range(n_tokens)]

    bias = [0.0] * n_experts
    target = n_tokens * top_k / n_experts
```

- 所有随机量共用一个 `random.Random(42)`，保证结果可复现。
- ⚠️ 注释说 token "有一些结构"，但实际是独立同分布的标准高斯向量，没有任何结构；初始的不均衡完全来自随机路由权重 `W_router` 的差异。
- 之后循环 10 次：`update_bias → run_epoch → 打印`。注意 token 集合每轮都相同（同一批数据反复路由），这和真实训练中每步不同 batch 不一样。

### 3.7 参数量估算

```python
    ffn_params = d_model * d_hidden * 3  # SwiGLU-like: W1, W2, W3
    # ...
    d = 7168
    shared = 1
    routed = 256
    active = 8
    layers = 61
    ffn_full = 3 * d * int(d * 2.67)
    fine_expert = ffn_full // 8
    total_moe_per_layer = (shared + routed) * fine_expert
    active_moe_per_layer = (shared + active) * fine_expert
    # ...
    print(f"  llama-3-70b FFN total: ~{32 * ffn_full / 1e9:.0f}B  (all active every token)")
```

- 思路正确：总参数 = `(共享 + 路由) × 专家大小`，激活 = `(共享 + k) × 专家大小`。
- ⚠️ toy MoE 按"SwiGLU 三个矩阵"算 `16 × 32 × 3`，但本文件的 toy 专家实际只有一个矩阵。
- ⚠️ DeepSeek-V3 的估算偏大：①每个专家按 `3·d·(2.67d)/8 ≈ 51.4M` 估算，真实专家中间维度是 2048，即 `3 × 7168 × 2048 ≈ 44.0M`；②61 层全部按 MoE 计，真实模型前 3 层是 dense FFN。结果打印出 FFN 总量约 806B，比整个模型的 671B 还多。按真实配置算约为 658B 总、24B 激活（见测验 Q11）。
- ⚠️ "llama-3-70b" 一行复用了 DeepSeek 的 `d = 7168` 和 32 层，得到约 13B；Llama 3 70B 实际是 `d = 8192`、FFN 中间维度 28672、80 层，FFN 约 56B。打印的对比因此不成立。
- `dense_active_params()` 函数定义了但从未调用，参数 `d_model` 也未使用，属于残留代码。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 专家只用一个线性层 + SiLU | 代码短，突出路由逻辑 | 真实专家是三矩阵 SwiGLU，输出回到 `d_model` 并做残差 |
| 逐 token 循环路由 | 直观，易读 | 生产中按专家分组 dispatch/combine，用 grouped GEMM；跨卡时是 all-to-all |
| 选择用 `scores + bias`、门控用 `scores` | 复现 DeepSeek-V3 的解耦思想 | V3 用 sigmoid 亲和度；还有一个很小的序列级辅助损失作为补充 |
| top-k 内 softmax | 门控和为 1，易于理解 | Switch 风格是全体 softmax 后取 top-k |
| 符号式固定步长更新 | 与讲义描述一致，最简单 | γ 大易振荡、γ 小收敛慢；可用衰减或比例更新 |
| 同一批 token 反复路由 | 便于观察偏置的作用 | 真实训练中每步 batch 不同，统计噪声更大 |
| 熵作为均衡指标 | 一个数概括分布 | 对轻度不均衡不敏感，应同时看最大负载比 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 嵌套列表推导 | `[[rng.gauss(0, scale) for _ in range(d_hidden)] for _ in range(d_in)]` | 生成二维矩阵 |
| 列表乘法初始化 | `[0.0] * d_hidden`、`[0] * len(experts)` | 一维列表初始化（元素不可变，安全） |
| `enumerate` | `for i, xi in enumerate(x)` | 同时拿到下标和值 |
| `zip` | `zip(hidden, W_router[e])`、`zip(top_idx, gates)` | 按位置配对 |
| 生成器表达式 | `sum(h * w for h, w in zip(...))` | 不建中间列表的求和 |
| `sorted` + `key` + `lambda` + 切片 | `sorted(range(E), key=lambda i: -biased[i])[:top_k]` | 取负号实现降序，切片取前 k 个（argsort + top-k） |
| 多返回值 | `return top_idx, gates`；`top_idx, gates = route(...)` | 返回元组并解包 |
| `_` 占位 | `_, top_idx = moe_layer_forward(...)` | 丢弃不需要的返回值 |
| `if / elif` | `if usage_counts[e] > target: ... elif ...` | 等于目标时两个分支都不进 |
| 可变对象原地修改 | `bias[e] -= gamma` | 列表在函数内被修改，调用者看到的也会变 |
| 推导式中的过滤 | `[c / total for c in counts if c > 0]` | 跳过零计数 |
| 早返回 | `if total == 0: return 0.0` | 处理边界情况 |
| f-string 格式符 | `f"{u:>4}"`、`f"{it:>2}"`、`f"{entropy(usage):.3f}"`、`f"{x / 1e9:.1f}B"` | 右对齐占宽、保留小数 |
| `str.join` | `" ".join(f"{u:>4}" for u in usage)` | 把多个字符串用空格拼起来 |
| 整除 | `ffn_full // 8` | 结果为整数 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 0.8 秒）：

```text
=== MoE routing: auxiliary-loss-free balance ===
config: 8 experts, top-2, 1000 tokens, target usage = 250 per expert

iteration  0  usage:  260  206  278  265  216  301  253  221  entropy=2.072
iteration  1  usage:  228  247  253  236  271  279  215  271  entropy=2.076
iteration  2  usage:  267  299  211  270  220  249  260  224  entropy=2.073
iteration  3  usage:  228  247  253  236  271  279  215  271  entropy=2.076
iteration  4  usage:  267  299  211  270  220  249  260  224  entropy=2.073
...
iteration 10  usage:  267  299  211  270  220  249  260  224  entropy=2.073
max entropy (uniform) = ln(8) = 2.079
```

- **iteration 0**（偏置全 0）：使用量 206–301，相对目标 250 偏差最多约 20%，熵 2.072——轻度不均衡。
- **iteration 1 之后**：使用量在两组数字之间**精确交替**（奇数轮为状态 A，偶数轮为状态 B），根本没有收敛。讲义 Build It 第 2 步说"usage converges to a uniform distribution over a few iterations"，与实际输出不符。
- **为什么是周期 2**：对比 A 与 B，A 中超目标的专家（下标 2、4、5、7）在 B 中全部欠目标，反之亦然。于是相邻两次更新的方向完全相反，`Δ(A) + Δ(B) = 0`，偏置在两个值之间来回跳。
- **怎么修**：把 `gamma` 调小。本地用同一组数据跑 50 轮，最大偏差（|使用量 − 250| 的最大值）：`γ=0.15` 一直在 35/49 之间振荡；`γ=0.05` 降到约 11–15；`γ=0.02` 降到约 5–7；`γ=0.01` 降到约 3–4（但前 10 轮几乎看不出变化）。符号式更新总会留下一个小幅的极限环，步长越小环越小、收敛越慢。

```text
=== parameter counts (FFN portion, per layer) ===
  toy MoE       : total=     12288  active=      3072
  deepseek-v3-ish per layer:  total=13.2B  active=0.5B
  deepseek-v3 FFN total (×61 layers): ~806B total,  ~28B active
  llama-3-70b FFN total: ~13B  (all active every token)
```

- toy：`8 × 1536 = 12288` 总、`2 × 1536 = 3072` 激活，激活占 1/4（= k/E）。
- DeepSeek-V3：每层总量是激活量的 `257 / 9 ≈ 28.6` 倍，这个比例是对的；但绝对数偏大（806B > 671B）。按真实配置约 658B 总 / 24B 激活。
- Llama 3 70B 一行用错了维度和层数，实际 FFN 约 56B。正确的结论是：V3 的 FFN 总量约为 Llama 3 70B 的 12 倍，每 token 激活的 FFN 计算却不到它的一半。

---

## 7. 动手改一改

1. **调 γ**：把 `gamma=0.15` 改成 0.05、0.02、0.01，并把迭代次数从 10 改为 50（讲义练习 1 写的是 50 次），打印每轮 `max(|usage − target|)`，画出收敛曲线。
2. **比例更新**：改写 `update_bias` 为 `bias[e] -= gamma * (usage[e] - target) / target`，与符号式更新比较收敛速度和最终抖动。
3. **验证解耦**：写一个 `route_coupled`，让门控也用 `biased` 分数，统计 1000 个 token 上两种实现的门控差异（平均绝对差）。
4. **哈希路由（讲义练习 2）**：用 `hash(tuple(round(v, 3) for v in x)) % E` 选专家，对比均衡程度；思考为什么可学习路由更好（哈希路由与内容无关，专家无法专门化）。
5. **真实的 SwiGLU 专家**：把专家改为三个矩阵 `W_gate (d, h)`、`W_up (d, h)`、`W_down (h, d)`，输出回到 `d_model`，再加残差 `x + moe(x)`，并修正 toy 参数量统计。
6. **修正参数估算**：用 DeepSeek-V3 的真实配置（专家中间维度 2048、58 个 MoE 层 + 3 个 dense 层）和 Llama 3 70B 的配置（d=8192、中间维度 28672、80 层）重写第 3.7 节的估算。

---

## 8. 常见坑

- **偏置进入门控**：均衡机制会直接改写模型输出；DeepSeek-V3 的关键就是只在选择时用偏置。
- **γ 过大导致振荡**：本文件就是现成的例子；符号式更新需要小步长或衰减。
- **用熵判断均衡**：熵接近 `ln E` 不代表每个专家都接近目标，±20% 的偏差熵也只差 0.007。
- **把激活参数当显存需求**：显存要装下全部专家；37B 激活的模型需要 671B 的权重存储。
- **专家输出维度与残差不匹配**：真实专家必须输出 `d_model` 维，才能和输入相加。
- **用经验公式估算具体模型**：`d_ff ≈ 2.67 d`、"细粒度 = 1/8" 只是粗略经验，算具体模型时应直接用 config 中的数值，并注意哪些层是 dense。
