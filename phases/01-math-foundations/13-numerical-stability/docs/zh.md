<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="numerical-stability"></a>

# 数值稳定性

> 浮点是一个有漏洞的抽象。它会在训练期间咬你，而你不会看到它的到来。

**类型：** 构建
**语言：** Python
**先决条件：** 第 1 阶段，课程 01-04
**时间：** ~120 分钟

<a id="learning-objectives"></a>

## 学习目标

- 使用最大减法技巧实现数值稳定的 softmax 和 log-sum-exp
- 识别浮点计算中的溢出、下溢和灾难性取消
- 使用居中的 finite differences 对照数值 gradients 验证分析 gradients
- 解释为什么 bfloat16 比 float16 更适合训练，以及损失缩放如何防止 gradient 下溢

<a id="the-problem"></a>

## 问题

您的模型训练三个小时，然后损失变为 NaN。您添加一条打印语句。 logits 在 9,000 步上表现良好。在步骤 9,001，它们是 `inf`。到步骤 9,002，每个 gradient 都是 `nan`，训练就结束了。

或者：您的模型训练完成，但准确度比论文声称的低 2%。你检查一切。建筑相匹配。 Hyperparameters 匹配。数据匹配。问题在于论文使用了 float32，而您使用了 float16，而没有正确的缩放。三十二位累积的舍入误差悄悄地消耗了您的准确性。

或者：您从头开始实现 cross-entropy 损失。它适用于小型 logits。当logits超过100时，返回`inf`。 softmax 溢出，因为 `exp(100)` 大于 float32 可以表示的大小。每个机器学习框架都通过两行技巧来处理这个问题。你不知道这个伎俩的存在。

数值稳定性不是理论上的问题。这就是一次成功的训练和一次默默失败的训练之间的区别。您要调试的每个严重的机器学习错误最终都会归结为浮点。

<a id="the-concept"></a>

## 概念

<a id="ieee-754-how-computers-store-real-numbers"></a>

### IEEE 754：计算机如何存储实数

计算机按照 IEEE 754 标准将实数存储为浮点值。浮点数由三部分组成：符号位、指数和尾数（有效数）。

```
Float32 layout (32 bits total):
[1 sign] [8 exponent] [23 mantissa]

Value = (-1)^sign * 2^(exponent - 127) * 1.mantissa
```

尾数决定精度（多少位有效数字）。指数决定范围（数字可以有多大或多小）。

```
Format     Bits   Exponent  Mantissa  Decimal digits  Range (approx)
float64    64     11        52        ~15-16          +/- 1.8e308
float32    32     8         23        ~7-8            +/- 3.4e38
float16    16     5         10        ~3-4            +/- 65,504
bfloat16   16     8         7         ~2-3            +/- 3.4e38
```

float32 提供大约 7 位小数的精度。这意味着它可以区分 1.0000001 和 1.0000002，但不能区分 1.00000001 和 1.00000002。 7 位数字之后，一切都是舍入噪声。

float16 给出大约 3 位数字。它可以表示的最大数字是 65,504。对于 logits、gradients 的 ML 来说，这个值小得令人不安，而且激活通常会超过这个值。

bfloat16 是 Google 针对 float16 范围问题的答案。它具有与 float32 相同的 8 位指数（范围相同，最高 3.4e38），但只有 7 个尾数位（精度低于 float16）。对于训练神经网络，范围比精度更重要，因此 bfloat16 通常会获胜。

<a id="why-01--02--03"></a>

### 为什么 0.1 + 0.2 != 0.3

数字0.1无法用二进制浮点数精确表示。在基数 2 中，它是一个重复分数：

```
0.1 in binary = 0.0001100110011001100110011... (repeating forever)
```

Float32 将其截断为 23 位尾数。存储的值约为 0.100000001490116。同样，0.2 存储为大约 0.200000002980232。它们的总和是 0.300000004470348，而不是 0.3。

```
In Python:
>>> 0.1 + 0.2
0.30000000000000004

>>> 0.1 + 0.2 == 0.3
False
```

这对于机器学习很重要，因为：

1. 像 `if loss < threshold` 这样的损失比较可能会给出错误的答案
2. 累积许多小值（gradient 更新数千步）偏离真实总和
3. 如果将浮点数与 `==` 进行比较，校验和和再现性测试会失败

修复：永远不要将浮点数与 `==` 进行比较。使用 `abs(a - b) < epsilon` 或 `math.isclose()`。

<a id="catastrophic-cancellation"></a>

### 灾难性取消

当您减去两个几乎相等的浮点数时，有效数字会取消，并且留下舍入噪声提升为前导数字。

```
a = 1.0000001    (stored as 1.00000011920929 in float32)
b = 1.0000000    (stored as 1.00000000000000 in float32)

True difference:  0.0000001
Computed:         0.00000011920929

Relative error: 19.2%
```

单次减法的相对误差为 19%。在机器学习中，只要您执行以下操作，就会发生这种情况：

- 计算平均值较大的数据的方差：当 E[x] 较大时，`E[x^2] - E[x]^2`
- 减去几乎相等的对数概率
- 使用太小的 epsilon 计算有限差分 gradients

解决方法：重新排列公式以避免减去大的、几乎相等的数字。对于方差，请使用 Welford 算法或首先将数据居中。对于对数概率，始终在对数空间中工作。

<a id="overflow-and-underflow"></a>

### 上溢和下溢

当结果太大而无法表示时，就会发生溢出。当它太小时（比最小可表示正数更接近零），就会发生下溢。

```
Float32 boundaries:
  Maximum:  3.4028235e+38
  Minimum positive (normal): 1.175e-38
  Minimum positive (denorm): 1.401e-45
  Overflow:  anything > 3.4e38 becomes inf
  Underflow: anything < 1.4e-45 becomes 0.0
```

`exp()` 函数是 ML 中溢出的主要来源：

```
exp(88.7)  = 3.40e+38   (barely fits in float32)
exp(89.0)  = inf         (overflow)
exp(-87.3) = 1.18e-38   (barely above underflow)
exp(-104)  = 0.0         (underflow to zero)
```

`log()` 函数却指向另一个方向：

```
log(0.0)   = -inf
log(-1.0)  = nan
log(1e-45) = -103.3      (fine)
log(1e-46) = -inf        (input underflowed to 0, then log(0) = -inf)
```

在ML中，`exp()`出现在softmax、sigmoid和概率计算中。 `log()` 出现在 cross-entropy、对数似然和 KL 散度中。如果没有正确的技巧，组合 `log(exp(x))` 就是一个雷区。

<a id="the-log-sum-exp-trick"></a>

### 对数和指数技巧

直接计算 `log(sum(exp(x_i)))` 在数值上是危险的。如果任何 `x_i` 很大，则 `exp(x_i)` 溢出。如果所有 `x_i` 都非常负，则每个 `exp(x_i)` 下溢为零，并且 `log(0)` 是 `-inf`。

技巧：在求幂之前减去最大值。

```
log(sum(exp(x_i))) = max(x) + log(sum(exp(x_i - max(x))))
```

为什么会这样：减去`max(x)`后，最大的指数是`exp(0) = 1`。不可能有溢出。总和中至少一项为 1，因此总和至少为 1，且 `log(1) = 0`。 `-inf` 不可能发生下溢。

证明：

```
log(sum(exp(x_i)))
= log(sum(exp(x_i - c + c)))                    (add and subtract c)
= log(sum(exp(x_i - c) * exp(c)))               (exp(a+b) = exp(a)*exp(b))
= log(exp(c) * sum(exp(x_i - c)))               (factor out exp(c))
= c + log(sum(exp(x_i - c)))                    (log(a*b) = log(a) + log(b))
```

设置`c = max(x)`，溢出被消除。

这个技巧在机器学习中随处可见：
- Softmax normalization
- Cross-entropy损失计算
- 序列模型中的对数概率求和
- 高斯混合
- 变体 inference

<a id="why-softmax-needs-the-max-subtraction-trick"></a>

### 为什么 Softmax 需要最大减法技巧

Softmax 将 logits 转换为概率：

```
softmax(x_i) = exp(x_i) / sum(exp(x_j))
```

如果没有这个技巧，[100、101、102]的logits会导致溢出：

```
exp(100) = 2.69e43
exp(101) = 7.31e43
exp(102) = 1.99e44
sum      = 2.99e44

These overflow float32 (max ~3.4e38)? No, 2.69e43 < 3.4e38? Actually:
exp(88.7) is already at the float32 limit.
exp(100) = inf in float32.
```

使用技巧，减去 max(x) = 102：

```
exp(100 - 102) = exp(-2) = 0.135
exp(101 - 102) = exp(-1) = 0.368
exp(102 - 102) = exp(0)  = 1.000
sum = 1.503

softmax = [0.090, 0.245, 0.665]
```

概率是相同的。计算是安全的。这不是优化。这是对正确性的要求。

<a id="nan-and-inf-detection-and-prevention"></a>

### NaN 和 Inf：检测和预防

`nan`（不是数字）和`inf`（无穷大）通过计算病毒式传播。 一`nan`在一个gradient更新使weight `nan`，这使得每个后续输出`nan`。 训练一步就死了。

`inf` 如何出现：
- `exp()` 大正数
- 除以零：`1.0 / 0.0`
- `float32` 累加溢出

`nan` 如何出现：
- `0.0 / 0.0`
- `inf - inf`
- `inf * 0`
- `sqrt()` 负数
- `log()` 负数
- 涉及现有 `nan` 的任何算术

检测：

```python
import math

math.isnan(x)       # True if x is nan
math.isinf(x)       # True if x is +inf or -inf
math.isfinite(x)    # True if x is neither nan nor inf
```

预防策略：

1. 将输入钳位至 `exp()`：`exp(clamp(x, -80, 80))`
2. 将 epsilon 添加到分母：`x / (y + 1e-8)`
3. 在`log()`里面添加epsilon：`log(x + 1e-8)`
4. 使用稳定的实现（log-sum-exp，稳定的softmax）
5. Gradient clipping 防止weight爆炸
6. 调试期间每个 forward pass 后检查 `nan`/`inf`

<a id="numerical-gradient-checking"></a>

### 数值 Gradient 检查

分析gradients（来自backpropagation）可能有错误。数值gradient检查通过用finite differences计算gradients来验证它们。

中心差值公式：

```
df/dx ~= (f(x + h) - f(x - h)) / (2h)
```

这是 O(h^2) 的精度，比前向差分 `(f(x+h) - f(x)) / h` 的精度要好得多，后者仅为 O(h)。

选择h：太大，近似值是错误的。太小的和灾难性的取消会破坏答案。 `h = 1e-5` 至 `1e-7` 是典型的。

检查：计算解析和数值 gradients 之间的相对差异。

```
relative_error = |grad_analytical - grad_numerical| / max(|grad_analytical|, |grad_numerical|, 1e-8)
```

经验法则：
- 相对_error < 1e-7：完美，gradient 正确
- relative_error < 1e-5：可接受，可能是正确的
- relative_error > 1e-3：出了问题
- 相对_error > 1：gradient完全错误

实现新层或 loss function 时，请务必检查 gradients。 PyTorch为此提供了`torch.autograd.gradcheck()`。

<a id="mixed-precision-training"></a>

### Mixed Precision 培训

现代 GPUs 拥有专用硬件（Tensor 内核），其计算 float16 矩阵乘法的速度比 float32 快 2-8 倍。 Mixed precision 训练利用了这一点：

```
1. Maintain float32 master copy of weights
2. Forward pass in float16 (fast)
3. Compute loss in float32 (prevents overflow)
4. Backward pass in float16 (fast)
5. Scale gradients to float32
6. Update float32 master weights
```

纯 float16 训练的问题：gradients 通常非常小（1e-8 或更小）。 Float16 将低于 ~6e-8 的任何值下溢为零。您的模型停止学习，因为所有 gradient 更新均为零。

修复方法是损失缩放：

```
1. Multiply loss by a large scale factor (e.g., 1024)
2. Backward pass computes gradients of (loss * 1024)
3. All gradients are 1024x larger (pushed above float16 underflow)
4. Divide gradients by 1024 before updating weights
5. Net effect: same update, but no underflow
```

动态损失缩放自动调整缩放因子。从一个较大的值 (65536) 开始。如果gradients溢出到`inf`，则减半。如果通过 N 步且没有溢出，则将其加倍。

<a id="bfloat16-vs-float16-why-bfloat16-wins-for-training"></a>

### bfloat16 与 float16：为什么 bfloat16 在训练中获胜

```
float16:   [1 sign] [5 exponent]  [10 mantissa]
bfloat16:  [1 sign] [8 exponent]  [7 mantissa]
```

float16 具有更高的精度（10 个尾数位与 7 个尾数位），但范围有限（最大 ~65,504）。 bfloat16 的精度较低，但范围与 float32 相同（最大 ~3.4e38）。

用于训练神经网络：

- 在训练高峰期间，激活和 logits 经常超过 65,504。 float16 溢出； bfloat16 处理它。
- float16 需要损失缩放，但 bfloat16 通常不需要损失缩放，因为它的范围涵盖 gradient 幅度谱。
- bfloat16 是 float32 的简单截断：去掉尾数的底部 16 位。指数转换是微不足道且无损的。

float16 是 inference 的首选，其中值有界并且精度更重要。 bfloat16 是范围更重要的训练的首选。这就是为什么 TPU 和现代 NVIDIA GPUs（A100、H100）具有本机 bfloat16 支持。

<a id="gradient-clipping"></a>

### Gradient Clipping

当 gradients 通过多个层呈指数增长时，会发生 gradients 爆炸（常见于 RNNs、深度网络和 transformers）。单个大的 gradient 可以一步破坏所有 weights。

两种类型的剪辑：

**Clip 按值：** 独立夹紧每个 gradient 元件。

```
grad = clamp(grad, -max_val, max_val)
```

简单但可以改变gradient向量的方向。

**按范数进行剪辑：** 缩放整个 gradient 向量，使其范数不超过阈值。

```
if ||grad|| > max_norm:
    grad = grad * (max_norm / ||grad||)
```

保留 gradient 的方向。这就是 `torch.nn.utils.clip_grad_norm_()` 所做的。这是标准选择。

典型值：`max_norm=1.0` 用于 transformers，`max_norm=0.5` 用于 RL，`max_norm=5.0` 用于更简单的网络。

Gradient clipping 不是黑客。这是一种安全机制。如果没有它，单个异常批次可能会产生足够大的 gradient ，从而毁掉数周的训练。

<a id="normalization-layers-as-numerical-stabilizers"></a>

### Normalization 层作为数值稳定器

批次 normalization、层 normalization 和 RMS normalization 通常表示为帮助训练收敛的正则化器。它们也是数值稳定器。

如果没有 normalization，激活可以通过层呈指数增长或收缩：

```
Layer 1: values in [0, 1]
Layer 5: values in [0, 100]
Layer 10: values in [0, 10,000]
Layer 50: values in [0, inf]
```

Normalization 在每一层重新调整激活值：

```
LayerNorm(x) = (x - mean(x)) / (std(x) + epsilon) * gamma + beta
```

当所有激活都相同时，`epsilon`（通常为 1e-5）可防止被零除。学习到的 parameters `gamma` 和 `beta` 让网络恢复其需要的任何规模。

这使整个网络中的值保持在数字安全范围内，从而防止 forward pass 中的溢出和 gradient 中的 backward pass 中的爆炸。

<a id="common-ml-numerical-bugs"></a>

### 常见的机器学习数值错误

**Bug：几个时期后损失为NaN。**
原因：logits 变得太大，softmax 溢出。或者learning rate太高而weights背离。
修复：使用稳定的softmax（最大减法），减少learning rate，添加gradient clipping。

**Bug：损失卡在日志（num_classes）.**
原因：模型输出的概率接近均匀。通常意味着 gradients 正在消失或者模型根本没有学习。
修复：检查数据标签是否正确，验证loss function，检查是否失效ReLUs。

**Bug：验证精度比预期低1-3%。**
原因：mixed precision 没有适当的损耗缩放。 Gradient 下溢会默默地将小更新归零。
修复：启用动态损失缩放，或切换到 bfloat16。

**Bug：Gradient规范对于某些层来说是0.0。**
原因：ReLU 神经元死亡（所有输入均为负），或 float16 下溢。
修复：使用LeakyReLU或GELU，使用gradient缩放，检查weight初始化。

**Bug：模型适用于一个 GPU，但在另一个 ** 上给出不同的结果。
原因：不确定的浮点累加顺序。 GPU 在不同的硬件上以不同的顺序并行归约求和，并且浮点加法不具有关联性。
修复：接受小的差异（1e-6），或设置 `torch.use_deterministic_algorithms(True)` 并接受速度损失。

**Bug：`exp()`在损失计算中返回`inf`。**
原因：原始 logits 传递到 `exp()` 时没有使用最大减法技巧。
修复：使用 `torch.nn.functional.log_softmax()` 内部实现 log-sum-exp。

**Bug：从float32切换到float16后训练出现分歧。**
原因：float16 无法表示低于 6e-8 的 gradient 幅度或高于 65,504 的激活。
修复：使用带有损失缩放 (AMP) 的 mixed precision，或改用 bfloat16。

```figure
logsumexp-stability
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-demonstrate-floating-point-precision-limits"></a>

### 步骤 1：演示浮点精度限制

```python
print("=== Floating Point Precision ===")
print(f"0.1 + 0.2 = {0.1 + 0.2}")
print(f"0.1 + 0.2 == 0.3? {0.1 + 0.2 == 0.3}")
print(f"Difference: {(0.1 + 0.2) - 0.3:.2e}")
```

<a id="step-2-implement-naive-vs-stable-softmax"></a>

### 步骤 2：实施朴素与稳定 softmax

```python
import math

def softmax_naive(logits):
    exps = [math.exp(z) for z in logits]
    total = sum(exps)
    return [e / total for e in exps]

def softmax_stable(logits):
    max_logit = max(logits)
    exps = [math.exp(z - max_logit) for z in logits]
    total = sum(exps)
    return [e / total for e in exps]

safe_logits = [2.0, 1.0, 0.1]
print(f"Naive:  {softmax_naive(safe_logits)}")
print(f"Stable: {softmax_stable(safe_logits)}")

dangerous_logits = [100.0, 101.0, 102.0]
print(f"Stable: {softmax_stable(dangerous_logits)}")
# softmax_naive(dangerous_logits) would return [nan, nan, nan]
```

<a id="step-3-implement-stable-log-sum-exp"></a>

### 步骤 3：实现稳定的 log-sum-exp

```python
def logsumexp_naive(values):
    return math.log(sum(math.exp(v) for v in values))

def logsumexp_stable(values):
    c = max(values)
    return c + math.log(sum(math.exp(v - c) for v in values))

safe = [1.0, 2.0, 3.0]
print(f"Naive:  {logsumexp_naive(safe):.6f}")
print(f"Stable: {logsumexp_stable(safe):.6f}")

large = [500.0, 501.0, 502.0]
print(f"Stable: {logsumexp_stable(large):.6f}")
# logsumexp_naive(large) returns inf
```

<a id="step-4-implement-stable-cross-entropy"></a>

### 第四步：实现稳定的cross-entropy

```python
def cross_entropy_naive(true_class, logits):
    probs = softmax_naive(logits)
    return -math.log(probs[true_class])

def cross_entropy_stable(true_class, logits):
    max_logit = max(logits)
    shifted = [z - max_logit for z in logits]
    log_sum_exp = math.log(sum(math.exp(s) for s in shifted))
    log_prob = shifted[true_class] - log_sum_exp
    return -log_prob

logits = [2.0, 5.0, 1.0]
true_class = 1
print(f"Naive:  {cross_entropy_naive(true_class, logits):.6f}")
print(f"Stable: {cross_entropy_stable(true_class, logits):.6f}")
```

<a id="step-5-gradient-checking"></a>

### 步骤5：Gradient检查

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
    for i, (a, n) in enumerate(zip(analytical, numerical)):
        denom = max(abs(a), abs(n), 1e-8)
        rel_error = abs(a - n) / denom
        status = "OK" if rel_error < tolerance else "FAIL"
        print(f"  param {i}: analytical={a:.8f} numerical={n:.8f} "
              f"rel_error={rel_error:.2e} [{status}]")

def f(params):
    x, y = params
    return x**2 + 3*x*y + y**3

def f_grad(params):
    x, y = params
    return [2*x + 3*y, 3*x + 3*y**2]

point = [2.0, 1.0]
analytical = f_grad(point)
numerical = numerical_gradient(f, point)
check_gradient(analytical, numerical)
```

<a id="use-it"></a>

## 实际应用

<a id="mixed-precision-simulation"></a>

### Mixed precision模拟

```python
import struct

def float32_to_float16_round(x):
    packed = struct.pack('f', x)
    f32 = struct.unpack('f', packed)[0]
    packed16 = struct.pack('e', f32)
    return struct.unpack('e', packed16)[0]

def simulate_bfloat16(x):
    packed = struct.pack('f', x)
    as_int = int.from_bytes(packed, 'little')
    truncated = as_int & 0xFFFF0000
    repacked = truncated.to_bytes(4, 'little')
    return struct.unpack('f', repacked)[0]
```

<a id="gradient-clipping-1"></a>

### Gradient clipping

```python
def clip_by_norm(gradients, max_norm):
    total_norm = math.sqrt(sum(g**2 for g in gradients))
    if total_norm > max_norm:
        scale = max_norm / total_norm
        return [g * scale for g in gradients]
    return gradients

grads = [10.0, 20.0, 30.0]
clipped = clip_by_norm(grads, max_norm=5.0)
print(f"Original norm: {math.sqrt(sum(g**2 for g in grads)):.2f}")
print(f"Clipped norm:  {math.sqrt(sum(g**2 for g in clipped)):.2f}")
print(f"Direction preserved: {[c/clipped[0] for c in clipped]} == {[g/grads[0] for g in grads]}")
```

<a id="naninf-detection"></a>

### NaN/Inf检测

```python
def check_tensor(name, values):
    has_nan = any(math.isnan(v) for v in values)
    has_inf = any(math.isinf(v) for v in values)
    if has_nan or has_inf:
        print(f"WARNING {name}: nan={has_nan} inf={has_inf}")
        return False
    return True

check_tensor("good", [1.0, 2.0, 3.0])
check_tensor("bad",  [1.0, float('nan'), 3.0])
check_tensor("ugly", [1.0, float('inf'), 3.0])
```

请参阅 `code/numerical.py` 了解演示了所有边缘情况的完整实现。

<a id="ship-it"></a>

## 交付成果

本课产生：
- `code/numerical.py` 具有稳定的 softmax、log-sum-exp、cross-entropy、gradient 检查和 mixed precision 模拟
- `outputs/prompt-numerical-debugger.md` 用于诊断 NaN/Inf 和训练中的数值问题

这些稳定的实现在构建训练循环时的第 3 阶段和实现 attention 机制时的第 4 阶段中重新出现。

<a id="exercises"></a>

## 练习

1. **灾难性取消。** 使用朴素公式计算 [1000000.0, 1000001.0, 1000002.0] 的方差float32 中的 `E[x^2] - E[x]^2`。然后使用 Welford 的在线算法进行计算。将误差与真实方差 (0.6667) 进行比较。

2. **精确搜索。** 找到最小的正 float32 值 `x`，使得 `1.0 + x == 1.0` 位于 Python 中。这是机器 epsilon。验证它是否与 `numpy.finfo(numpy.float32).eps` 匹配。

3. **Log-sum-exp 边缘情况。** 使用以下条件测试您的 `logsumexp_stable` 函数：(a) 所有值相等，(b) 一个值远大于 rest，(c) 所有值都非常负 (-1000)。验证它在幼稚版本失败的情况下给出正确的结果。

4. **Gradient 检查神经网络层。** 实现单个线性层 `y = Wx + b` 及其分析 backward pass。使用 `numerical_gradient` 验证 3x2 weight 矩阵的正确性。

5. **损失缩放实验。** 使用 float16 模拟训练：在 [1e-9、1e-3] 范围内创建随机 gradients，转换为 float16，并测量变成什么分数零。然后应用损失缩放（乘以 1024），转换为 float16，缩小，并再次测量零分数。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| IEEE 754 | 《浮动标准》 | 定义二进制浮点格式、舍入规则和特殊值的国际标准（inf、nan）。每个现代的 CPU 和 GPU 都实现它。 |
| 机器ε | “精度极限” | 给定浮点格式中 1.0 + e != 1.0 的最小值 e。对于float32来说，大约是1.19e-7。 |
| 灾难性取消 | “减法的精度损失” | 当减去几乎相等的浮点数时，有效数字会被抵消，并且舍入噪声在结果中占主导地位。 |
| 溢出 | “数字太大了” | 结果超出最大可表示值并变为 inf。 exp(89) 溢出 float32。 |
| 下溢 | “数量太小了” | 结果比最小可表示正数更接近零，并且变为 0.0。 exp(-104) 下溢 float32。 |
| 对数和指数技巧 | “先减去最大值” | 通过分解 exp(max(x)) 来计算 log(sum(exp(x))) 以防止上溢和下溢。用于 softmax、cross-entropy 和对数概率数学。 |
| 稳定 softmax | “不会爆炸的Softmax” | 在求幂之前减去 max(logits)。数值结果相同，不可能溢出。 |
| Gradient检查 | “验证你的反向传播” | 将 backpropagation 中的分析 gradients 与 finite differences 中的数值 gradients 进行比较，以捕获实现错误。 |
| Mixed precision | “向前float16，向后float32” | 对于速度关键的操作使用较低精度的浮点数，对于数字敏感的操作使用高精度的浮点数。典型的加速比是 2-3 倍。 |
| 损失缩放 | “防止 gradient 下溢” | 在反向传播之前将损失乘以一个大常数，以便 gradients 保持在 float16 的可表示范围内，然后在 weight 更新之前除以相同的常数。 |
| bfloat16 | 《大脑浮点》 | Google 的 16 位格式，具有 8 个指数位（与 float32 范围相同）和 7 个尾数位（精度低于 float16）。首选用于培训。 |
| Gradient clipping | “限制 gradient 规范” | 缩放 gradient 向量，使其范数不超过阈值。防止 gradients 爆炸毁坏 weights。 |
| NaN | “不是一个数字” | 来自未定义操作的特殊浮点值（0/0、inf-inf、sqrt(-1)）。传播到所有后续算术。 |
| 信息 | 《无限》 | 溢出或除以零的特殊浮点值。可以组合产生NaN（inf - inf，inf * 0）。 |
| 数值 gradient | “暴力衍生” | 通过计算 f(x+h) 和 f(x-h) 并除以 2h 来近似导数。验证缓慢但可靠。 |

<a id="further-reading"></a>

## 进一步阅读

- [每个计算机科学家都应该了解浮点运算（Goldberg 1991）](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html) - 权威的参考资料，密集但完整
- [Mixed Precision Training (Micikevicius et al., 2018)](https://arxiv.org/abs/1710.03740)——介绍 float16 训练损失缩放的 NVIDIA 论文
- [AMP：自动Mixed Precision（PyTorch文档）](https://pytorch.org/docs/stable/amp.html)——PyTorch中mixed precision的实用指南
- [bfloat16 格式（Google Cloud TPU 文档）](https://cloud.google.com/tpu/docs/bfloat16)——为什么 Google 为 TPU 选择这种格式
- [Kahan 求和（维基百科）](https://en.wikipedia.org/wiki/Kahan_summation_algorithm) -- 减少浮点和舍入误差的算法
