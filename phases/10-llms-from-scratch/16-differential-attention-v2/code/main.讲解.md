# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 16 节 Differential Attention（V2） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`、`typing`），无 NumPy、无 torch

---

## 1. 这份代码在考察什么

代码用纯 Python 列表实现 softmax、标准注意力和差分注意力，并做三件事：

1. **Step 1 · 噪声抵消玩具**：长度 1024 的序列，在位置 500 放一个信号 logit（4.0），其余是高斯噪声；分支 1 是"训练好的头"（有信号尖峰），分支 2 是"未训练的头"（纯噪声）。比较标准 softmax 与 `A₁ − λA₂` 在不同 λ 下的信号噪声比（SNR）。
2. **Step 2 · 噪声幅度扫描**：固定 λ = 0.8，噪声标准差从 0.25 到 2.0，观察两种注意力的 SNR 如何变化。
3. **Step 3 · 参数量对比**：7B 级配置（hidden 4096、32 头、8 个 KV 头）下基线、DIFF V1、DIFF V2 的注意力参数量。

对应讲义的核心概念：softmax 噪声底、差分相减的共模抵消、λ 的作用、V1/V2 的参数账。

> 一句话：**把"两个 softmax 相减能去掉噪声底"变成可以运行、可以扫参的数字**。但读输出时要清楚：玩具中两个分支的噪声相互独立，差分只能抵消噪声的均值；高噪声下差分反而更差；Step 3 的 V2 差值是口径不一致的结果。这些"不一致"恰恰是理解差分注意力的关键（见第 3、6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 | 是否被 `main` 使用 |
|---------|------|------|---------|------------------|
| `dot` | 函数 | 两个向量点积 | 注意力分数 | 否（仅被未使用的函数调用） |
| `softmax_row` | 函数 | 减最大值的数值稳定 softmax | softmax | 是 |
| `standard_attention` | 函数 | `softmax(QKᵀ/√d)V` | 标准注意力 | **否** |
| `diff_attention` | 函数 | `(softmax(Q₁K₁ᵀ/√d) − λ softmax(Q₂K₂ᵀ/√d))V` | 差分注意力 | **否** |
| `random_projection` / `matmul` | 函数 | 随机投影矩阵、矩阵乘 | Q/K 投影 | **否** |
| `build_signal_plus_noise` | 函数 | 构造"信号 + 噪声"输入序列与对齐的 query | 合成数据 | **否** |
| `snr` | 函数 | `|信号权重| / 平均 |噪声权重|` | 信号噪声比 | 是 |
| `ParamDiff` | dataclass | 三种结构的参数量与差值 | 参数账 | 是 |
| `attention_params_baseline / _diff_v1 / _diff_v2` | 函数 | 各结构的注意力参数量 | V1/V2 参数对比 | 是 |
| `compute_param_diff` | 函数 | 汇总为 `ParamDiff` | 参数账 | 是 |
| `fmt_m` | 函数 | 格式化为 M/K | 输出 | 是 |
| `main` | 函数 | 依次执行 Step 1–3 | 入口 | — |

数据流：`main` 直接用 `rng.gauss` 生成两组 logits → `softmax_row` 得到 A₁、A₂ → 逐个 λ 计算 `A₁ − λA₂` → `snr` → 打印；Step 2 换噪声幅度重复；Step 3 调用 `compute_param_diff` 打印参数量。

> 注意：表中五个"否"的函数构成了一条完整的"输入 → 投影 → 注意力"路径，docstring 称之为"the faithful simulation of DIFF attention"，但 `main` 一次也没有调用它们。Step 1 标题中的 "direct-logit toy" 说明它直接在 logits 上做实验。

---

## 3. 逐段精讲

### 3.1 `softmax_row` 与两个注意力函数

```python
def softmax_row(row: List[float]) -> List[float]:
    m = max(row)
    exps = [math.exp(x - m) for x in row]
    s = sum(exps)
    return [e / s for e in exps]
```

- 先减最大值再取指数：`softmax(x − m) = softmax(x)`，但避免 `exp` 溢出。讲义 Step 1 的代码与此相同。
- 输出每个元素都 > 0、总和为 1——这正是"噪声底"的来源：没有任何位置是精确的 0。

```python
def diff_attention(Q1, K1, Q2, K2, V, lam):
    d = len(Q1[0])
    scale = math.sqrt(d)
    weights = []
    for q1, q2 in zip(Q1, Q2):
        row1 = softmax_row([dot(q1, k) / scale for k in K1])
        row2 = softmax_row([dot(q2, k) / scale for k in K2])
        diff = [a - lam * b for a, b in zip(row1, row2)]
        weights.append(diff)
    out = []
    d_v = len(V[0])
    for w in weights:
        o = [sum(w[j] * V[j][c] for j in range(len(V))) for c in range(d_v)]
        out.append(o)
    return weights, out
```

- 对每个 query，分别用 `(q1, K1)`、`(q2, K2)` 算两行 softmax，逐元素相减（第二行乘 λ），再与 V 加权求和。
- 两个分支**共用同一个 V**，这与讲义公式 `(A₁ − λA₂)V` 一致。
- 差分后的权重可以为负，每行之和为 `1 − λ`；讲义："the value cache still handles signed contributions"。
- `standard_attention` 结构相同，只有一个分支。两者都是 O(N²·d) 的三重循环，纯 Python 实现只适合玩具规模。
- 讲义 Step 2 说"The toy implementation uses V1 for pedagogical clarity"：这里 Q1、Q2 各自的维度由调用者决定，函数本身对 V1/V2 不敏感——V1 与 V2 的区别在于"头怎么切、参数从哪来"，而不是相减本身。

### 3.2 `build_signal_plus_noise` 与投影函数（未被调用）

```python
    pattern = [rng.gauss(0, 1) for _ in range(d_embed)]
    norm = math.sqrt(sum(x * x for x in pattern))
    pattern = [x / norm for x in pattern]
    X = []
    for i in range(n_tokens):
        if i == signal_pos:
            X.append([p + rng.gauss(0, noise_scale * 0.1) for p in pattern])
        else:
            X.append([rng.gauss(0, noise_scale) for _ in range(d_embed)])
    q = list(pattern)
```

- 生成一个单位向量 `pattern`，把它（加少量噪声）放在信号位置；其他位置是纯高斯噪声；query 就是 `pattern` 本身——于是 `q · x_signal ≈ 1`，`q · x_noise` 围绕 0 波动。
- `random_projection` 生成 `d_in × d_out`、元素方差 `1/d_in` 的矩阵，使投影后各分量方差约为 1（注释写"unit-variance columns"）。
- 这条路径本意是：两个分支看到同一序列，但用不同的投影矩阵，模拟真实的差分注意力。⚠️ 但 `main` 没有用它。测验 Q12 给出了调用这些函数的实验。

### 3.3 `snr`：怎么度量"信号噪声比"

```python
def snr(weights_row, signal_pos):
    sig = abs(weights_row[signal_pos])
    noise_vals = [abs(w) for i, w in enumerate(weights_row) if i != signal_pos]
    mean_noise = sum(noise_vals) / len(noise_vals)
    if mean_noise == 0:
        return float("inf")
    return sig / mean_noise
```

- 信号位置权重的绝对值，除以其余 1023 个位置权重绝对值的**平均**。
- 取绝对值是必要的：差分后噪声位置可能为负，负权重同样会把无关 value 混进输出。
- 这个定义对"整行整体缩放"不敏感（分子分母同比例变化），所以 `1 − λ` 的幅度缩小不会直接影响 SNR；真实模型中这种幅度变化需要归一化来处理。

### 3.4 Step 1：λ 扫描

```python
    signal_logit = 4.0
    noise_std = 0.5
    logits_trained = [rng.gauss(0, noise_std) for _ in range(n_tokens)]
    logits_trained[signal_pos] = signal_logit
    logits_untrained = [rng.gauss(0, noise_std) for _ in range(n_tokens)]

    A1 = softmax_row(logits_trained)
    A2 = softmax_row(logits_untrained)
    ...
    for lam in (0.0, 0.3, 0.6, 0.8, 1.0):
        diff = [a1 - lam * a2 for a1, a2 in zip(A1, A2)]
```

- 分支 1：噪声 logits + 位置 500 的尖峰（4.0）。softmax 后信号权重只有 0.0446，其余 1023 个位置合计 0.955——这就是讲义说的"噪声淹没信号"：一个比噪声高 8 个标准差的 logit，在 1024 长度下也只分到 4.5% 的注意力。
- 分支 2：**另一份独立抽样**的噪声 logits，没有尖峰。
- ⚠️ 关键细节：两个分支的噪声不是"共有"的。差分能抵消的只是两者期望相同的部分——约 `1/N` 的均匀底；两路的随机波动独立，相减后方差相加。这决定了：
  - SNR 随 λ 先升后降，0.01 步长扫描的最优点在 λ ≈ 0.77（SNR 92.44）；
  - 噪声越大，波动占比越高，差分越吃亏（Step 2）。
- 若让分支 2 共享分支 1 的噪声（只去掉尖峰），λ = 0.8 时 SNR 升到约 287.6，λ = 1.0 时约 1023——这才是"共模抵消"的真实威力，也是训练要让两个分支学到的关系（测验 Q10）。

### 3.5 Step 2：噪声幅度扫描

```python
    for noise_scale in (0.25, 0.50, 1.0, 1.5, 2.0):
        lrng = random.Random(int(noise_scale * 100))
        l1 = [lrng.gauss(0, noise_scale) for _ in range(n_tokens)]
        l1[signal_pos] = signal_logit
        l2 = [lrng.gauss(0, noise_scale) for _ in range(n_tokens)]
        ...
        diff_s = [a - 0.8 * b for a, b in zip(A1s, A2s)]
```

- 每个噪声水平用独立种子 `int(noise_scale * 100)`（25、50、100、150、200），保证可复现。
- 信号 logit 固定为 4.0，噪声标准差增大意味着"信号相对噪声变弱"，同时噪声分布的长尾让某些无关 token 的权重变大。
- 讲义练习 1 要求找出"标准注意力变得不可用"的交叉点；在这个玩具里实际出现的是**差分与标准注意力的交叉点**：细扫显示在噪声 1.0（35.14 对 34.62）与 1.1（30.47 对 31.02）之间，之后差分更差。

### 3.6 Step 3：参数量

```python
def attention_params_baseline(hidden):
    return 4 * hidden * hidden

def attention_params_diff_v1(hidden, n_heads, d_head):
    q_params = 2 * (hidden * (n_heads * d_head // 2))
    k_params = 2 * (hidden * (n_heads * d_head // 2))
    v_params = hidden * hidden
    o_params = hidden * hidden
    lam_params = 4 * n_heads * (d_head // 2)
    ...

def attention_params_diff_v2(hidden, n_heads, d_head, kv_heads):
    q_params = hidden * (2 * n_heads * d_head)
    k_params = hidden * (kv_heads * d_head)
    v_params = hidden * (kv_heads * d_head)
    o_params = (2 * n_heads * d_head) * hidden
    lam_params = 4 * n_heads * d_head
```

- **基线**：`4h²`，即 MHA（Q、K、V、O 都是 `h × h`），不考虑 GQA。
- **V1**：Q、K 各拆成两半（每半 `h × h/2`），总量仍是 `h²`；V、O 不变；λ 参数是每头 4 个 `d_head/2` 维向量（`λ_q1, λ_k1, λ_q2, λ_k2`），共 `4 × 32 × 64 = 8,192`。所以 V1 只比基线多 8.2K——"保持参数量不变"的设计。
- **V2**：Q 翻倍为 `2h²`；K、V 按 `kv_heads = 8` 算（各 `4096 × 1024`）；O 也按 `2h²` 算；λ 为 `4 × 32 × 128`。
- ⚠️ 两处口径问题：
  1. 基线是 MHA，V2 是 GQA，二者相减把"GQA 省下的 25.2M"混进了"V2 多出的参数"。
  2. 讲义说相减后"the extra dimension is projected back down to match baseline Transformer's O_W"，额外参数"roughly `hidden * hidden`"；代码把 O 也翻倍（`2h²`），多算了 `h²`。
  合起来：`+2h²（33.55M）− 25.17M + λ ≈ 8.4M`，正是输出的 delta。统一口径后（O 为 `h²`），无论 MHA 还是 GQA，V2 都比基线多 `h² ≈ 16.8M`（测验 Q11）。
- 讲义还说 V2 的额外参数是从 MLP up-projection 借来的，实际模型总参数不变；代码只算注意力块，没有体现这一点。
- 结尾 takeaway "V2 brings the parameter cost down" 与输出矛盾：V2 多 8.4M（按正确口径 16.8M），V1 只多 8.2K。V2 的收益在 decode 速度与 kernel 兼容性，而不是参数量。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 直接在 logits 上做玩具（direct-logit toy） | 不需要训练就能展示 softmax 噪声底与相减效果 | 无法体现"两个分支被训练成相关噪声"；独立噪声下只能抵消均值，高噪声时结论反转 |
| 用 `|w|` 的平均作为噪声度量 | 负权重同样是污染，必须取绝对值 | 对整体缩放不敏感，看不到 `1 − λ` 幅度缩小带来的问题 |
| 固定 λ 扫描 | 直观展示 λ 的作用 | 真实模型中 λ 用 `exp(·) − exp(·) + λ_init` 参数化、逐头学习 |
| 纯 Python 列表实现 | 零依赖、每一步可见 | O(N²d) 循环很慢；生产中每个分支调用 FlashAttention（V2 的卖点） |
| 保留未调用的投影/注意力函数 | 为练习预留完整路径 | 读者容易误以为 Step 1 经过了 Q/K 投影 |
| 参数量只算注意力块 | 聚焦差异 | 基线 MHA 与 V2 GQA 混用、O 翻倍，差值失真；V2 实际从 MLP 借参数，总量不变 |
| 不模拟 decode / KV cache | 代码短 | V2 最重要的收益（decode 持平、算术强度提升）没有被量化 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许 `tuple[List[List[float]], ...]` 这类注解 |
| 嵌套类型注解 | `List[List[float]]`、`tuple[List[List[float]], List[List[float]]]` | 二维列表表示矩阵；函数返回两个矩阵 |
| 生成器表达式求和 | `sum(ai * bi for ai, bi in zip(a, b))` | 不建中间列表，直接累加 |
| 列表推导式 | `[math.exp(x - m) for x in row]`、`[a - lam * b for a, b in zip(row1, row2)]` | 逐元素运算 |
| 嵌套列表推导式 | `[[rng.gauss(0, ...) for _ in range(d_out)] for _ in range(d_in)]` | 生成二维矩阵，外层是行 |
| 带条件的推导式 | `[abs(w) for i, w in enumerate(weights_row) if i != signal_pos]` | 过滤掉信号位置 |
| `zip` 同时遍历 | `for q1, q2 in zip(Q1, Q2):` | 成对取两个分支的 query |
| `enumerate` | `for i, w in enumerate(A1)` | 同时取下标和值 |
| `list(x)` 浅复制 | `q = list(pattern)` | 返回新列表，修改 q 不影响 pattern |
| `random.Random(seed)` | `random.Random(17)`、`random.Random(int(noise_scale * 100))` | 独立、可复现的随机数生成器 |
| `rng.gauss(mu, sigma)` | `rng.gauss(0, noise_std)` | 正态分布采样 |
| `float("inf")` | `snr` 中 | 噪声为 0 时返回无穷大 |
| 元组字面量循环 | `for lam in (0.0, 0.3, 0.6, 0.8, 1.0):` | 遍历固定的取值 |
| `@dataclass` | `class ParamDiff:` | 只含字段的结果容器 |
| 整除 | `n_heads * d_head // 2` | `//` 优先级与 `*` 相同，从左到右计算 |
| 数字下划线 | `1_000_000` | 可读性分隔符 |
| f-string 格式符 | `{std_signal:.6f}`、`{d_signal:+.6f}`、`{lam:.1f}`、`{noise_scale:>10.2f}`、`{'noise_std':>10}` | `+` 强制显示正负号；`>` 右对齐 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行，测验中可直接复用函数 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（约 0.04 秒），输出节选：

```text
Step 1: direct-logit toy on length 1024, signal at pos 500
  standard softmax attention (branch 1 only):
    weight on signal position  : 0.044569
    sum of |noise| weights     : 0.955431
    signal-to-noise ratio      : 47.72

  differential attention (lambda=0.0):  SNR 47.72
  differential attention (lambda=0.3):  signal +0.044467  |noise| 0.674752  SNR 67.42
  differential attention (lambda=0.6):  signal +0.044364  |noise| 0.513567  SNR 88.37
  differential attention (lambda=0.8):  signal +0.044296  |noise| 0.490901  SNR 92.31
  differential attention (lambda=1.0):  signal +0.044227  |noise| 0.530741  SNR 85.25

Step 2: noise-amplitude sweep (higher = noisier context)
   noise_std    std SNR    diff SNR (lam=0.8)
        0.25      52.09                173.19
        0.50      48.69                 88.46
        1.00      34.62                 35.14
        1.50      15.93                 11.80
        2.00       8.46                  5.42

Step 3: parameter-count diff, 7B-class config
  baseline attention   : 67.1M
  DIFF V1 attention    : 67.1M  (delta 8.2K)
  DIFF V2 attention    : 75.5M  (delta 8.4M)
```

（Step 1 的多行输出在此合并为单行展示。）

逐项解读：

- **噪声底的直观数字**：信号 logit 比噪声高 8 个标准差，但在 1024 长度下只分到 4.46% 的权重，其余 95.5% 散落在噪声上——这就是讲义开篇的问题。
- **λ = 0 等价于标准注意力**：SNR 完全相同，作为对照。
- **SNR 先升后降**：λ 从 0 到 0.8，`|noise|` 总和从 0.955 降到 0.491，SNR 从 47.7 升到 92.3（约 1.9 倍）；λ = 1.0 时 `|noise|` 反弹到 0.531。细扫最优点 λ ≈ 0.77。讲义 Step 4 声称"3x-10x"，本玩具在默认噪声下只有约 1.9 倍。
- **信号权重几乎不变**：分支 2 在信号位置的权重仅约 0.00034，相减只扣掉很少一点。
- **Step 2 的反转**：噪声 0.25 时差分约 3.3 倍，0.5 时约 1.8 倍，1.0 时持平，1.5、2.0 时差分更差。代码结尾 takeaway 的"reliably improves"在这里并不成立；根因是两路噪声独立（3.4 节）。
- **Step 3**：V1 只多 λ 参数（8,192）；V2 的 8.4M 是"MHA 基线 vs GQA 的 V2 + O 翻倍"的混合口径，统一口径后为 `h² ≈ 16.8M`（3.6 节）。

---

## 7. 动手改一改

1. **讲义练习 4 · λ 细扫**：把 Step 1 的 λ 改为 `[i / 100 for i in range(0, 201)]`，打印 SNR 最大的 λ（约 0.77），并画出（或打印）SNR–λ 曲线；同时打印每个 λ 下整行权重之和，验证是 `1 − λ`。
2. **相关噪声实验**：令 `logits_untrained = list(logits_trained)` 并把信号位置设为 0，重跑 Step 1 与 Step 2，观察 SNR 如何大幅提升，体会"共模抑制"需要噪声相关（测验 Q10）。
3. **讲义练习 1 · 交叉点**：把 Step 2 的噪声水平改为 0.75–1.5、步长 0.05，找出差分与标准注意力 SNR 的交叉点（约在 1.0–1.1 之间）。
4. **修正参数账**：把 `o_params` 改成 `(n_heads * d_head) * hidden`，并让基线也接收 `kv_heads` 参数，分别输出 MHA 与 GQA 口径下的基线和 V2；再乘以 32 层得到整模型差值（约 537M）。
5. **讲义练习 5 · KV cache**：写 `kv_bytes_per_token(layers, kv_heads, d_head, bytes=2)`，证明 GQA 基线与 GQA + DIFF V2 的 KV cache 相同（每层每 token 4,096 字节）。
6. **启用"忠实模拟"路径**：用 `build_signal_plus_noise`、`random_projection`、`matmul`、`standard_attention`、`diff_attention` 写一个经过 Q/K 投影的版本（测验 Q12），比较与 direct-logit 玩具的差别。

---

## 8. 常见坑

- **以为两个 softmax 相减就一定降噪**：只有两路噪声相关时才能大幅抵消；独立噪声只能去掉均值，波动反而叠加。
- **先相减再 softmax**：`softmax(s₁ − s₂)` 仍然非负、和为 1，没有"负权重抵消"的能力，不是差分注意力。
- **忽略权重总和 `1 − λ`**：输出幅度随 λ 变化，没有归一化或合适初始化会影响训练稳定（V1 用每头 RMSNorm，V2 改为初始化方案）。
- **把 λ 当成固定超参**：λ 是每头可学习、可为负的标量，讲义给出了它的重参数化形式。
- **参数对比混用 MHA 与 GQA**：基线与改动版必须在同一口径下比较，否则差值没有意义（Step 3 的 8.4M 就是例子）。
- **以为 V2 省参数**：V2 的注意力参数比基线多约 `h²`（从 MLP 借来以保持总量），它的收益在 decode 速度与 FlashAttention 兼容性。
- **相信未执行的 docstring**：本文件的投影版模拟函数写好了但从未被调用；读代码时要追踪 `main` 真正执行的路径。
- **引用讲义数字前先算一遍**：讲义"每个 token 0.001%、合计约 12%"实际应为 0.0001%；"3x-10x"在本玩具中也没有复现。
