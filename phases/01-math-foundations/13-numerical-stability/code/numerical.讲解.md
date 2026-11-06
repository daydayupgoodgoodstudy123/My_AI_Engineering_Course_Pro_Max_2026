# 代码讲解 · numerical.py

> **所属小节**：阶段 01 · 数学基础 · 第 13 节 数值稳定性 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python numerical.py`（无命令行参数，依次运行 14 个演示，最后打印 `All demos complete.`） ｜ **依赖**：仅 Python 标准库（`math`、`struct`、`random`），不需要 NumPy

---

## 1. 这份代码在考察什么

文件约 24KB：前 170 行是 18 个"工具函数"（朴素版 vs 稳定版成对出现），后面是 14 个演示。它想让你形成这些肌肉记忆：

1. **`exp` / `log` 是数值炸弹**：softmax、log-sum-exp、交叉熵、sigmoid、BCE 都有"朴素版会炸、稳定版不会"的写法，关键技巧只有两个——**减最大值**和**在 log 空间计算**。
2. **相减会吃掉精度**：灾难性抵消让 `E[x²] − E[x]²` 失效，Welford 在线算法和 Kahan 求和是对策。
3. **梯度要能被验证**：用中心差分做数值梯度检查，用相对误差判断对错。
4. **训练的"安全带"**：梯度裁剪（按值 vs 按范数）、NaN/Inf 检测、LayerNorm 的 epsilon。
5. **低精度格式**：用 `struct` 和位运算模拟 float16 / bfloat16，理解范围与精度的取舍，以及 loss scaling。

> 一句话：**每个稳定写法都和朴素写法放在一起跑一遍**——但要注意，Python 的 `float` 是 float64，很多在 float32 / float16 下才会暴露的问题，在这份代码里"炸不起来"（见 3.9 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `softmax_naive` / `softmax_stable` | 函数 | 朴素 vs 减最大值的 softmax | 上溢、平移不变性 |
| `logsumexp_naive` / `logsumexp_stable` | 函数 | 朴素 vs 稳定的 `log Σ exp` | Log-Sum-Exp 技巧 |
| `log_softmax_stable` | 函数 | `z − LSE(z)` | log 空间计算 |
| `cross_entropy_naive` / `cross_entropy_stable` | 函数 | 先 softmax 再 log vs 直接用 log_softmax | 稳定交叉熵 |
| `sigmoid_naive` / `sigmoid_stable` | 函数 | 按正负分支避免 `exp` 上溢 | 稳定 sigmoid |
| `binary_cross_entropy_naive` / `_stable` | 函数 | 概率版 vs logits 版 BCE（⚠️ 定义了但演示中未调用） | softplus 形式 |
| `numerical_gradient` / `check_gradient` | 函数 | 中心差分 + 相对误差判定 | 梯度检查 |
| `clip_by_value` / `clip_by_norm` | 函数 | 两种梯度裁剪 | 梯度爆炸 |
| `check_tensor` | 函数 | 统计 NaN / Inf 个数 | NaN 检测 |
| `simulate_bfloat16` / `simulate_float16` | 函数 | 位截断 / `struct` 'e' 格式模拟低精度 | 浮点格式 |
| `kahan_sum` | 函数 | 带误差补偿的求和 | 舍入误差累积 |
| `welford_variance` / `variance_naive` | 函数 | 在线方差 vs `E[x²] − E[x]²` | 灾难性抵消 |
| `layer_norm` | 函数 | 带 epsilon 的层归一化 | 归一化作为稳定器 |
| `demo_float_precision` … `demo_format_comparison` | 14 个演示 | 依次演示上述概念 | — |

调用关系：`cross_entropy_stable → log_softmax_stable`；`cross_entropy_naive → softmax_naive`；梯度检查的 Test 2 用 `cross_entropy_stable` 作为被检查函数、用 `softmax_stable` 构造解析梯度；混合精度演示调用两个 `simulate_*`；`demo_common_bugs` 复用了 softmax、交叉熵和两种方差函数。

---

## 3. 逐段精讲

### 3.1 softmax 与 log-sum-exp：减最大值

```python
def softmax_naive(logits):
    exps = [math.exp(z) for z in logits]
    total = sum(exps)
    return [e / total for e in exps]


def softmax_stable(logits):
    max_logit = max(logits)
    exps = [math.exp(z - max_logit) for z in logits]
    total = sum(exps)
    return [e / total for e in exps]
```

- 两个版本只差一行：`z - max_logit`。由于 `exp(zᵢ − c) / Σ exp(zⱼ − c) = exp(zᵢ) / Σ exp(zⱼ)`，结果在数学上完全相同。
- 减去最大值后，最大的指数项是 `exp(0) = 1`：**不会上溢**；分母至少为 1：**不会出现 0 作分母**。
- 朴素版在 Python 里的失败方式和 NumPy 不同：`math.exp(1000)` 直接抛 `OverflowError`（而不是返回 inf）；`[-1000, -999, -998]` 时每个 `exp` 都下溢成 0.0，`e / total` 抛 `ZeroDivisionError`（NumPy 下才是 `nan`）。代码里打印的 "would be [nan, nan, nan]" 是 NumPy / IEEE 语义下的说法。

```python
def logsumexp_stable(values):
    c = max(values)
    return c + math.log(sum(math.exp(v - c) for v in values))


def log_softmax_stable(logits):
    c = max(logits)
    lse = c + math.log(sum(math.exp(z - c) for z in logits))
    return [z - lse for z in logits]


def cross_entropy_stable(true_class, logits):
    log_probs = log_softmax_stable(logits)
    return -log_probs[true_class]
```

- `logsumexp_stable` 对应讲义公式 `log Σ exp(xᵢ) = c + log Σ exp(xᵢ − c)`。演示中 `[5, 5, 5]` 的结果是 `5 + ln 3 = 6.0986122887`，`[100, 1, 1]` 的结果约等于 100——LSE 是"平滑版的 max"。
- `log_softmax = z − LSE(z)`：全程只有减法，不会出现 `log(0)`。
- 交叉熵 = 负的"正确类别的 log 概率"。朴素版 `cross_entropy_naive` 先算概率再 `math.log`，当正确类别概率下溢为 0 时会报错；稳定版不会。演示中 `[0, 0, 50]` 且真实类别为 0 时，稳定版直接给出 `50.0000`。
- ⚠️ `[0, 0, 50]` 且真实类别为 2 时打印的是 `-0.0000000000`：`lse` 中的 `log(1 + 2e⁻⁵⁰)` 精确舍入为 0，`50 − 50.0 = 0.0`，取负得到 IEEE 754 的**负零**。它等于 0，不是 bug。

### 3.2 sigmoid 与 BCE：按符号分支

```python
def sigmoid_stable(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = math.exp(x)
        return z / (1.0 + z)
```

- 朴素版 `1 / (1 + exp(−x))` 在 x 为很大的负数时，`exp(−x)` 上溢。稳定版保证 `exp` 的参数**永远 ≤ 0**：x ≥ 0 时用 `exp(−x)`；x < 0 时把分子分母同乘 `exp(x)`，变成 `exp(x) / (1 + exp(x))`。
- 演示表里只有 `x = −710` 这一行朴素版显示 `OVERFLOW`（`math.exp(710)` 超过 float64 上限约 `exp(709.78)`）。

```python
def binary_cross_entropy_stable(y_true, logit):
    max_val = max(0.0, logit)
    return max_val + math.log(math.exp(-max_val) + math.exp(logit - max_val)) - y_true * logit
```

- 这是 `softplus(x) − y·x`：`max_val + log(e^{−m} + e^{x−m})` 正是对 `[0, x]` 两个数做 log-sum-exp，等于 `log(1 + eˣ)`。推导见测验 Q10。
- 它直接吃 **logit** 而不是概率，避免了"sigmoid 先饱和成 1.0，再算 `log(1 − 1.0)`"的问题。PyTorch 推荐 `BCEWithLogitsLoss` 也是这个道理。
- ⚠️ 这两个 BCE 函数在 14 个演示里**都没有被调用**，可以自己补一个演示（见第 7 节）。

### 3.3 数值梯度检查

```python
def numerical_gradient(f, x, h=1e-5):
    grad = []
    for i in range(len(x)):
        x_plus = x[:]
        x_minus = x[:]
        x_plus[i] += h
        x_minus[i] -= h
        grad.append((f(x_plus) - f(x_minus)) / (2 * h))
    return grad


def check_gradient(analytical, numerical, tolerance=1e-5):
    all_ok = True
    for i, (a, n) in enumerate(zip(analytical, numerical)):
        denom = max(abs(a), abs(n), 1e-8)
        rel_error = abs(a - n) / denom
        status = "OK" if rel_error < tolerance else "FAIL"
        # ...
    return all_ok
```

- **中心差分**：每次只扰动一个参数，`x[:]` 复制列表，保证不改动原始参数；误差为 O(h²)，比前向差分的 O(h) 好得多。
- **成本**：n 个参数需要 2n 次函数调用——所以只能用来验证小规模的新层 / 新损失，不能在大模型上整体运行。
- **相对误差**：分母取 `max(|a|, |n|, 1e-8)`，让量级不同的梯度能用同一个阈值比较；`1e-8` 防止两者都为 0 时除以 0。
- **h 的取舍**：`h=1e-5` 是在"截断误差（h 大）"与"灾难性抵消（h 小）"之间的折中，测验 Q11 给出了 h 从 1e-1 扫到 1e-13 的实测误差曲线。
- 演示的三个测试：多项式（误差约 1e-11）、softmax 交叉熵（解析梯度 `softmax(z) − onehot(y)`，误差约 1e-11）、故意写错的梯度 `[1, 1]`（相对误差 0.83 / 0.875，判定 FAIL）——**正例 + 反例**都要有，才能证明检查器本身是有效的。

### 3.4 梯度裁剪

```python
def clip_by_value(gradients, max_val):
    return [max(-max_val, min(max_val, g)) for g in gradients]


def clip_by_norm(gradients, max_norm):
    total_norm = math.sqrt(sum(g ** 2 for g in gradients))
    if total_norm > max_norm:
        scale = max_norm / total_norm
        return [g * scale for g in gradients]
    return list(gradients)
```

- `max(-v, min(v, g))` 是经典的 clamp 写法。按值裁剪会改变方向：`[10, 20, 30]` 裁到 15 后变成 `[10, 15, 15]`，比例从 `1:2:3` 变成 `1:1.5:1.5`。
- 按范数裁剪只缩放长度：范数 37.4166 → 5.0，比例仍是 `1:2:3`。这也是 `torch.nn.utils.clip_grad_norm_` 的做法（它对所有参数计算一个全局范数）。
- 未裁剪时返回 `list(gradients)`（一份拷贝），保证返回值的类型和"是否新对象"在两个分支上一致。
- "梯度爆炸模拟"里每步梯度乘以 3.5，8 步后达到 22518.75，而裁剪后的值始终是 1.0——裁剪把一次灾难性的大步更新变成一次正常步长的更新。

### 3.5 NaN / Inf 检测

```python
def check_tensor(name, values):
    has_nan = any(math.isnan(v) for v in values)
    has_inf = any(math.isinf(v) for v in values)
    n_nan = sum(1 for v in values if math.isnan(v))
    n_inf = sum(1 for v in values if math.isinf(v))
    # ...
```

- 必须用 `math.isnan`，不能用 `v == float('nan')`——NaN 与任何值比较都不相等（演示打印 `nan == nan = False`）。
- `any(...)` 会在遇到第一个 True 时短路返回；`sum(1 for ...)` 统计个数。前两行其实可以由后两行推出（`n_nan > 0`），属于冗余但易读的写法。
- ⚠️ `demo_nan_inf` 中有几行是**直接打印的字符串或预先构造的值**，并没有真的计算：
  - `1.0 / 0.0 = {float('inf')}`：纯 Python 中 `1.0 / 0.0` 会抛 `ZeroDivisionError`，`0.0 / 0.0` 也一样；只有 NumPy / PyTorch 才按 IEEE 754 返回 inf / nan。
  - `max = nan (comparison with nan is always False)`：实测 Python 内置 `max([1.0, 2.0, nan, 4.0, 5.0])` 返回 **5.0**——正因为与 NaN 的比较总是 False，NaN 被"跳过"了（除非它在第一个位置）；`np.max` 才会返回 nan。
  - 实际计算的 `inf - inf`、`inf * 0`、`nan + 1`、`sum(values)` 都正确地得到 nan。

### 3.6 用 `struct` 模拟 float16 和 bfloat16

```python
def simulate_bfloat16(x):
    packed = struct.pack('f', x)
    as_int = int.from_bytes(packed, 'little')
    truncated = as_int & 0xFFFF0000
    repacked = truncated.to_bytes(4, 'little')
    return struct.unpack('f', repacked)[0]


def simulate_float16(x):
    try:
        packed = struct.pack('e', x)
        return struct.unpack('e', packed)[0]
    except (OverflowError, struct.error):
        return float('inf') if x > 0 else float('-inf')
```

- **bfloat16**：先把 x 打包成 4 字节 float32，再当作 32 位整数，用掩码 `0xFFFF0000` 清零低 16 位（即 float32 尾数的低 16 位），保留 1 位符号 + 8 位指数 + 7 位尾数，正好是 bfloat16 的布局。`'little'` 与 `struct.pack('f', …)` 在常见的小端机器上的字节序一致（⚠️ `'f'` 使用本机字节序，大端机器上这里会出错，严谨写法是 `'<f'`）。
- ⚠️ 这是**截断**（向零舍入），而 PyTorch 等框架把 float32 转成 bfloat16 时通常使用**就近舍入（round-to-nearest-even）**。差别在演示里很明显：截断版 `0.1 → 0.0996`、`65504 → 65280`；本机按就近舍入计算则分别为 `0.10009765625` 和 `65536`。讲义说 bfloat16 是"simple truncation of float32"，指的是位布局，而不是标准的舍入方式。
- **float16**：`struct` 的 `'e'` 格式就是 IEEE 754 半精度，打包时自动按就近舍入。超出范围时 `struct.pack` 抛 `OverflowError`，这里转成 ±inf 来模拟硬件行为。
- 边界解读：float16 在 `[32768, 65536)` 区间的间隔是 32，所以 `65000 → 64992`；`65520` 恰好位于 65504 与 65536 的正中间，按"偶数优先"规则向上舍入到 65536，超出最大值，变成 inf。

### 3.7 Kahan 求和

```python
def kahan_sum(values):
    total = 0.0
    compensation = 0.0
    for v in values:
        y = v - compensation
        t = total + y
        compensation = (t - total) - y
        total = t
    return total
```

- 当 `total` 很大、`v` 很小时，`total + v` 会丢掉 v 的低位。`(t - total) - y` 恰好把"这次加法丢掉的部分"（取负）算出来存进 `compensation`，下一轮再补回去。
- 演示中把 `1e-7` 累加一百万次：朴素求和误差 1.85e-12，Kahan 误差 0。
- ⚠️ 这里的 "True value" 是 `1e-7 * 1_000_000` 的浮点计算结果 `0.09999999999999999`，本身也带舍入误差（并不是精确的 0.1），所以"Kahan 误差 0"的含义是"与这次浮点乘法的结果完全一致"。

### 3.8 方差：朴素公式 vs Welford

```python
def welford_variance(values):
    n = 0
    mean = 0.0
    m2 = 0.0
    for x in values:
        n += 1
        delta = x - mean
        mean += delta / n
        delta2 = x - mean
        m2 += delta * delta2
    if n < 2:
        return 0.0
    return m2 / n


def variance_naive(values):
    n = len(values)
    mean_x = sum(values) / n
    mean_x2 = sum(v ** 2 for v in values) / n
    return mean_x2 - mean_x ** 2
```

- 朴素公式先算两个巨大且几乎相等的数 `E[x²]` 和 `E[x]²`，再相减——典型的灾难性抵消。
- Welford 每来一个样本就更新均值，并累加"偏离旧均值 × 偏离新均值"，所有运算都在"偏差"的量级上进行，不会出现大数相减。它还是**单遍、在线**的，适合流式数据（BatchNorm 的 running statistics 就有类似需求）。
- 两者返回的都是总体方差（除以 n），与演示里的真值 `2/3`、`2.0` 一致；样本方差应除以 `n − 1`。
- 演示 2 中 `[1e6, 1e6+1, 1e6+2]`：朴素版 `0.6666259766`（误差 4.07e-05），Welford 精确。本机用 float32 复现，朴素公式甚至得到 **-65536**。

### 3.9 ⚠️ 重要：这份代码大部分演示运行在 float64 下

Python 的 `float` 是 IEEE 754 双精度。讲义里很多数字是 float32 的，因此有几个演示"没能炸起来"：

| 演示 | 讲义 / 打印的说法 | 实际运行结果 | 原因 |
|------|------------------|-------------|------|
| 演示 2：`1.0000001 − 1.0` | 讲义：相对误差 19.2% | `Relative error: 0.0%` | float64 存储误差约 1e-16；19.2% 是 float32 的结果 |
| 演示 4：`[100, 101, 102]` 朴素 softmax | 讲义：会上溢 | 朴素版正常输出 | float64 的 `exp` 上限约 `exp(709)`，float32 才是约 `exp(88.7)` |
| 演示 5：`[500, 501, 502]` 朴素 LSE | 讲义 Step 3 注释：返回 inf | `Naive: 502.4076059644444` | 同上 |
| 演示 13 Bug 1：`[100, -100, -100]` | 标题：log(0) 崩溃 | 概率 `1.38e-87`，`log = −200.00` | `exp(-200)` 在 float64 下不下溢，float32 下才为 0 |
| 演示 13 Bug 3：`1e8 + 1 … 1e8 + 5` | 标题：方差出错 | 朴素版误差 `0.00e+00` | float64 下恰好算对；float32 连 `1e8 + 1` 都无法表示（间隔为 8），朴素方差为 0 |

这些演示的**结论是对的**，只是在 float64 下现象被掩盖了。学习时建议用 `numpy.float32` 重新跑一遍（第 7 节练习 1）。

### 3.10 混合精度与 loss scaling 演示

```python
    random.seed(42)
    n_grads = 1000
    tiny_grads = [random.uniform(1e-9, 1e-5) for _ in range(n_grads)]

    zeros_without_scaling = sum(1 for g in tiny_grads if simulate_float16(g) == 0.0)

    scale = 1024.0
    scaled_grads = [g * scale for g in tiny_grads]
    zeros_with_scaling = sum(1 for g in scaled_grads if simulate_float16(g) == 0.0)
    # ...
    scale_factor = 65536.0
    no_overflow_steps = 0
    growth_interval = 100
    # ...
        if math.isinf(simulate_float16(scaled)):
            scale_factor /= 2
            no_overflow_steps = 0
            # ...
        else:
            no_overflow_steps += 1
            if no_overflow_steps >= growth_interval:
                scale_factor *= 2
```

- **静态 loss scaling**：float16 中比约 3e-8 还小的数会舍入成 0。乘以 1024 后再转换，零的个数从 4 降到 0。
- ⚠️ `uniform(1e-9, 1e-5)` 是**线性均匀**采样，绝大多数值都在 1e-6 量级以上，只有约 0.4% 会下溢，低估了问题。本机改用对数均匀采样 `10**uniform(-9, -3)`（讲义练习 5 的范围），不缩放时约 24% 变成 0，缩放后为 0。另外，这 1000 个梯度全部小于 float16 的最小正规数（约 6.1e-5），处在精度更差的次正规区：例如 `1e-6` 直接转换的相对误差约 1.3%，缩放 1024 倍后再转换只有约 0.02%——loss scaling 不只是"避免变 0"，也保住了精度。
- **动态 loss scaling**：从 65536 开始，溢出就减半并清零计数器，连续 `growth_interval` 步没溢出就加倍。
- ⚠️ 打印条件 `step < 20 or step % 100 == 0` / `step < 100 or step % 100 == 0` 把大部分事件过滤掉了。本机复现：实际共发生 10 次调整（第 102、205、328、446 步加倍，第 105、228、346、452 步减半，等等），scale 一直在 16384 和 32768 之间振荡，但输出只显示了第 0、2 步的两次减半。
- ⚠️ 真实的 GradScaler 还会在发现 inf/NaN 时**跳过这一步的参数更新**；PyTorch 默认的 `growth_interval` 是 2000 步，远大于这里的 100。

### 3.11 LayerNorm 与格式对比表

```python
def layer_norm(values, epsilon=1e-5, gamma=1.0, beta=0.0):
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(var + epsilon)
    return [(v - mean) / std * gamma + beta for v in values]
```

- 用"两遍法"（先算均值，再算偏差平方的均值）求方差，避开了 3.8 节的抵消问题。
- epsilon 加在**方差里、开方之前**（`sqrt(var + eps)`），与 PyTorch `LayerNorm` 一致；讲义公式写的是 `std + epsilon`，两种写法都能防止除以 0，但数值上略有差别。
- 演示 12：不归一化时每层乘 2.5，第 8 层最大值已达 4068.94；加 LayerNorm 后最大值稳定在 2.0 左右。
- 演示 13 Bug 5：常数输入的方差为 0，`1/sqrt(0)` 在 Python 中抛 `ZeroDivisionError`（在 NumPy 中是 inf，再乘以 `v − mean = 0` 就得到 nan）；加 `1e-5` 后为 316.23。
- ⚠️ 演示 14 的格式表中 `float8 … 1-2  240  Forward pass only (H100+)` 一行不够准确：H100 支持的 FP8 有 E4M3 和 E5M2 两种，常用的 E4M3 最大值是 448（240 是按 IEEE 规则保留 inf 时 E4M3 的最大值），E5M2 最大约 57344；而且 FP8 训练方案通常在前向使用 E4M3、在反向的梯度上使用 E5M2，并不是"只用于前向"。
- 用 π 测试精度时，float16 和 bfloat16 恰好都得到 `3.140625`（误差 0.000968）——这是巧合：float16 在 `[2, 4)` 的间隔约 0.00195，π 正好最靠近 3.140625；一般情况下 float16 精度更高，比如 `0.1` 的结果 float16 为 `0.1000`、bfloat16 为 `0.0996`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 朴素版和稳定版成对实现 | 对比最能说明"为什么要这样写" | 生产代码只保留稳定版，并直接用框架算子（`log_softmax`、`logsumexp`、`BCEWithLogitsLoss`） |
| 只用标准库 `math` | 每一步都透明，没有向量化的"魔法" | 与 NumPy 的异常语义不同（抛异常 vs 返回 inf/nan） |
| 用 `try/except` 捕获 `OverflowError` | Python 的 `math.exp` 上溢会抛异常 | NumPy / PyTorch 返回 inf 并继续传播，需要主动检测 |
| 用 `struct` + 位掩码模拟低精度 | 不依赖 NumPy / PyTorch 就能观察 float16 / bfloat16 | bfloat16 用截断，与框架常用的就近舍入不同；生产中直接使用框架的 dtype |
| 中心差分 + 相对误差 + 故意写错的反例 | 既验证梯度，又验证检查器本身 | 生产中用 `torch.autograd.gradcheck`（float64） |
| Welford / Kahan | 展示"改写算法"比"提高精度"更根本 | 框架内部的归约通常用分块 / 成对求和与更高精度累加器 |
| 演示里部分结果用字符串直接打印 | 讲清 IEEE 语义（inf、nan） | 与纯 Python 的真实行为不一致（`1.0/0.0` 会抛异常，`max` 会跳过 NaN），阅读时要区分 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表推导式 | `[math.exp(z - max_logit) for z in logits]` | 一行生成新列表 |
| 生成器表达式 | `sum(math.exp(v - c) for v in values)`、`any(math.isnan(v) for v in values)` | 不建中间列表；`any` 会短路 |
| 条件表达式 | `status = "OK" if rel_error < tolerance else "FAIL"` | 一行二选一 |
| 元组解包 | `x, y = params`；`for i, (a, n) in enumerate(zip(...))` | 把列表 / 元组拆成多个变量 |
| 列表复制 | `x_plus = x[:]`、`list(gradients)` | 浅拷贝，避免修改调用者的数据 |
| 数字字面量下划线 | `1_000_000` | 只为可读性，等于 1000000 |
| 十六进制与位运算 | `as_int & 0xFFFF0000` | 按位与，用掩码清零低 16 位 |
| `struct.pack / unpack` | `struct.pack('f', x)`、`struct.pack('e', x)` | 把数值打包成字节；`'f'` 是 float32，`'e'` 是 float16，`'d'` 是 float64 |
| `int.from_bytes` / `to_bytes` | `int.from_bytes(packed, 'little')` | 字节 ↔ 整数，第二个参数指定字节序 |
| 捕获多种异常 | `except (OverflowError, struct.error):`、`except (OverflowError, ValueError):` | 用元组同时捕获多种异常 |
| 特殊浮点值 | `float('inf')`、`float('nan')`、`-0.0` | IEEE 754 的无穷、非数和负零 |
| `math` 模块 | `math.exp / log / sqrt / isnan / isinf / isclose / pi` | `isclose` 默认相对容差 1e-9，用于浮点比较 |
| 嵌套函数 | `demo_gradient_checking` 里的 `def f1(params)` | 局部定义被检查的函数，作为参数传给 `numerical_gradient` |
| 函数作为参数 | `numerical_gradient(f1, point)` | Python 函数是一等对象 |
| `random` 模块 | `random.seed(42)`、`random.uniform(a, b)`、`random.gauss(0, 1)` | 固定种子保证可复现；均匀分布 / 正态分布采样 |
| f-string 格式符 | `{x:.2e}`、`{x:>8.1f}`、`{s:>14s}`、`{scale:.0f}`、`{'-'*8}` | 科学计数法；右对齐；字符串表达式也能写在花括号里 |
| f-string 套推导式 | `{[f'{p:.6f}' for p in naive_result]}` | 先把每个数格式化成字符串，再打印整个列表 |
| `print(..., end="")` | `print(f"  If true class is 1: ...", end="")` | 不换行，下一个 `print` 接在同一行 |
| 三引号 f-string | `print(f"""\n  Format  Bits ...""")` | 多行文本，适合打印表格 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行演示 |

---

## 6. 运行结果解读

已在临时副本中实际运行（`python3 numerical.py`，Python 3.13，纯标准库，约 1 秒完成）。关键输出：

```text
  0.1 + 0.2 = 0.30000000000000004
  1.0 + 1e-8 == 1.0?  False            ← float64 的 epsilon 约 2.2e-16，所以仍不相等
  Naive sum:   0.1000000000  (error: 1.85e-12)
  Kahan sum:   0.1000000000  (error: 0.00e+00)

  Naive (E[x^2] - E[x]^2): 0.6666259766   ← 灾难性抵消
  Welford (online):         0.6666666667
  Relative error: 0.0%                    ← float64 下看不到讲义的 19.2%（见 3.9）

  exp(709.78) = 1.7928e+308 / exp(710) = OVERFLOW   ← float64 的 exp 上限
  exp(-745) = 5e-324 / exp(-746) = 0.0              ← 最小次正规数，再小就下溢
  float16(65000.0) = 64992.0 / float16(65520.0) = inf

  Extreme logits: [1000.0, 1001.0, 1002.0]
  Stable: ['0.090031', '0.244728', '0.665241']      ← 与 [100,101,102]、[-1000,...] 结果相同（平移不变）

  Equal values: [5.0, 5.0, 5.0]  Stable: 6.0986122887 (= 5 + ln3)
  Loss: -0.0000000000                     ← 负零，见 3.1
  Loss: 50.0000                           ← 自信但错误，loss 很大但有限

      -710.0        OVERFLOW  0.0000000000    ← 朴素 sigmoid 唯一失败的一行

  param 0: analytical=7.00000000 numerical=7.00000000 rel_error=1.29e-11 [OK]
  param 0: analytical=1.00000000 numerical=6.00000000 rel_error=8.33e-01 [FAIL]  ← 反例被正确识别

  inf - inf = nan / inf * 0 = nan / nan == nan = False

  Clip by norm (max=5.0): ['1.3363', '2.6726', '4.0089']
  Direction preserved: [1.0, 2.0, 3.0] == [1.0, 2.0, 3.0]

      0.1000  float16 0.1000  bfloat16 0.0996   ← bfloat16 精度更低（且这里是截断）
  65536.0000  float16    inf  bfloat16 65536.0000   ← float16 范围不够
  Zeros without scaling: 4/1000 (0.4%) → with scaling: 0/1000
  Final scale factor: 16384               ← 实际在 16384 / 32768 间振荡（见 3.10）

  Layer  8: max=     4068.94   vs   Layer  8: max=2.0000   ← LayerNorm 把数值拉回安全区间
  If true class is 1: log(1.38e-87) = -200.00   ← float64 下没有真的出现 log(0)
  Naive:   2.000000  (error: 0.00e+00)          ← Bug 3 在 float64 下没有复现
  loss == 1.0? False (WRONG) / math.isclose(loss, 1.0)? True (CORRECT)
  1/sqrt(var + 1e-5) = 316.23 (safe with epsilon)
All demos complete.
```

---

## 7. 动手改一改

1. **用 float32 重跑**：引入 NumPy，把演示 2、4、5、13 中的计算改成 `np.float32`（如 `np.exp(np.float32(100))`），复现讲义中的 19.2%、`[nan, nan, nan]`、`log(0)` 和负方差；对比 Python `math` 抛异常与 NumPy 返回 inf/nan 的不同语义。
2. **补 BCE 演示**：对 `logit ∈ {−1000, −10, 0, 10, 1000}`、`y ∈ {0, 1}` 比较 `binary_cross_entropy_naive(y, sigmoid_stable(x))` 与 `binary_cross_entropy_stable(y, x)`，并用 `math.log1p` 写出第三个版本。
3. **画误差曲线**：对 `numerical_gradient` 扫描 `h = 10⁻¹ … 10⁻¹³`，记录相对误差，找出误差最小的 h，并解释 U 形曲线。
4. **就近舍入的 bfloat16**：实现 `simulate_bfloat16_rne`（在截断前加上 `0x7FFF + ((as_int >> 16) & 1)`），比较 `0.1`、`65504.0` 在截断与就近舍入下的结果。
5. **修正演示里的硬编码**：把 `demo_nan_inf` 中的 `max = nan` 改为真实计算 `max(values)` 并与 `np.max` 对比；把 `1.0 / 0.0` 改为 `try/except ZeroDivisionError`。
6. **更真实的 loss scaling**：用 `10 ** random.uniform(-9, -3)` 生成梯度；让动态 loss scaling 打印每一次调整，并在溢出时记录"跳过的步数"。

---

## 8. 常见坑

- **以为 float64 就安全了**：`math.exp(710)` 照样上溢；`E[x²] − E[x]²` 在 float64 下照样有误差。稳定写法与精度无关，必须养成习惯。
- **Python 与 NumPy 的异常语义不同**：纯 Python 的 `1.0/0.0`、`math.log(0)`、`math.exp(1000)` 会抛异常；NumPy / PyTorch 返回 inf / nan 并继续传播，问题可能在几百步之后才暴露。
- **用 `==` 判断 NaN 或比较浮点数**：`nan == nan` 为 False；`0.1 * 10 == 1.0` 这类比较要用 `math.isclose`。
- **内置 `max` / `min` 会悄悄跳过 NaN**：日志里的最大值看起来正常，NaN 却被藏起来了；监控时用 `math.isnan` / `np.isfinite`。
- **先 softmax 再 log**：概率下溢为 0 时得到 `-inf`；交叉熵、BCE 一律用 logits 版本。
- **梯度检查的 h 越小越好？** 不是。h 太小会触发灾难性抵消，float64 下一般取 1e-5 左右，并且要在 float64 下运行。
