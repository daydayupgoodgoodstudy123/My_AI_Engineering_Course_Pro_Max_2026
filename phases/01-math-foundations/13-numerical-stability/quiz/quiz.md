# 测验 · 数值稳定性（Numerical Stability）

> **阶段 01 · 数学基础 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/numerical.py](../code/numerical.py) ｜ 代码讲解：[code/numerical.讲解.md](../code/numerical.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | IEEE 754 浮点格式 | 符号位 + 指数位 + 尾数位：指数位决定**范围**，尾数位决定**精度**。float32 = 8+23 位（约 7 位十进制有效数字，最大约 3.4e38），float16 = 5+10 位（最大 65504），bfloat16 = 8+7 位（范围同 float32、精度更低） |
| 2 | 舍入误差与机器 epsilon | 0.1 在二进制里是无限循环小数，`0.1 + 0.2 != 0.3`；float32 的 epsilon 约 1.19e-7；浮点数永远用 `math.isclose` / 容差比较，不用 `==` |
| 3 | 灾难性抵消（catastrophic cancellation） | 两个相近的数相减，有效数字被抵消、舍入噪声被放大；典型例子是 `E[x²] − E[x]²` 求方差，修法是先中心化或用 Welford 算法 |
| 4 | 上溢与下溢 | `exp` 是上溢的头号来源（float32 约 `exp(88.7)` 到顶，float64 约 `exp(709.78)`）；下溢把极小值变成 0，紧接着 `log(0) = −inf` |
| 5 | Log-Sum-Exp 技巧 | `log Σ exp(xᵢ) = c + log Σ exp(xᵢ − c)`，取 `c = max(x)`：最大项变成 `exp(0) = 1`，既不会上溢，求和结果也 ≥ 1，不会出现 `log(0)` |
| 6 | 稳定的 softmax / log_softmax / 交叉熵 | softmax 先减最大值；交叉熵在 log 空间直接算 `−(z_y − LSE(z))`，不要先 softmax 再取 log |
| 7 | 稳定的 sigmoid 与 BCE | sigmoid 按 x 的正负分支，避免 `exp(−x)` 上溢；带 logits 的 BCE 写成 `softplus(x) − y·x` |
| 8 | NaN / Inf | `0/0`、`inf − inf`、`inf × 0` 产生 NaN，且会"病毒式"传播；`nan == nan` 为 False；用 `math.isnan / isinf / isfinite` 检测 |
| 9 | 数值梯度检查 | 中心差分 `(f(x+h) − f(x−h)) / 2h` 误差为 O(h²)；h 太大截断误差大、太小被抵消误差吞没；用相对误差判断（< 1e-7 很好，> 1e-3 有问题） |
| 10 | 训练稳定性工具箱 | 混合精度 + loss scaling（float16 防梯度下溢）、bfloat16、按范数梯度裁剪（保方向）、归一化层里的 epsilon、Kahan 求和 |

### 核心技能（能动手做到）

- [ ] 从零实现 `softmax_stable`、`logsumexp_stable`、`log_softmax_stable`、`cross_entropy_stable`，并用 `[1000, 1001, 1002]` 和 `[-1000, -999, -998]` 验证朴素版失败、稳定版正确
- [ ] 推导并实现带 logits 的稳定 BCE，说清它为什么在 `logit = ±1000` 时也不会出现 `log(0)`
- [ ] 写出 `numerical_gradient` + `check_gradient`，对任意小函数做梯度检查，并能画出 / 解释"误差随 h 先降后升"的曲线
- [ ] 用 `np.float32` 复现讲义中 19.2% 的抵消误差和方差公式的失败，再用 Welford / 中心化修好
- [ ] 用 `struct` 的 `'e'` 格式和位运算模拟 float16 / bfloat16，解释 65504、65520 → inf 等边界，并演示 loss scaling 如何救回下溢梯度
- [ ] 实现按值裁剪和按范数裁剪，验证后者保持梯度方向
- [ ] 训练出现 NaN 时，能列出系统化的排查清单（数据 → 前向 → loss → 梯度 → 优化器 → 精度）

---

## 二、基础自测（选择题）

**Q1.** 关于 float16 与 bfloat16，下列说法正确的是：

- A. bfloat16 的尾数位比 float16 多，所以精度更高
- B. bfloat16 与 float32 的指数位相同（8 位），范围约 3.4e38，但只有 7 位尾数
- C. float16 的表示范围与 float32 相同
- D. 用 bfloat16 训练比用 float16 更依赖 loss scaling

**Q2.** 用 log-sum-exp 技巧计算 `log(exp(1000) + exp(1000))`，结果约为：

- A. `inf`
- B. 1000
- C. `1000 + ln 2 ≈ 1000.693`
- D. 2000

**Q3.** 实现交叉熵时，推荐用 `-log_softmax(z)[y]` 而不是 `-log(softmax(z)[y])`，主要原因是：

- A. log_softmax 的计算量更小
- B. 当正确类别的概率极小时，softmax 可能下溢为 0，`log(0) = −inf`；在 log 空间直接计算 `z_y − LSE(z)` 不会出现这个问题
- C. log_softmax 的输出总是正数，便于取负号
- D. log_softmax 不需要减最大值

**Q4.** 用中心差分 `(f(x+h) − f(x−h)) / 2h`，在 `x = 1`、`h = 0.1` 处近似 `f(x) = x³` 的导数（真值为 3），得到：

- A. 3.31
- B. 3.01
- C. 3.00
- D. 2.99

**Q5.** 在纯 Python（不用 NumPy）中，下列哪个表达式的值为 `True`？

- A. `float('nan') == float('nan')`
- B. `math.isnan(max([1.0, float('nan'), 3.0]))`
- C. `math.isnan(float('inf') - float('inf'))`
- D. `1.0 / 0.0 == float('inf')`

**Q6.** 梯度为 `[3.0, 4.0]`（L2 范数为 5），分别做 `clip_by_norm(max_norm=1.0)` 和 `clip_by_value(max_val=1.0)`，结果是：

- A. 按范数：`[0.6, 0.8]`，方向不变；按值：`[1.0, 1.0]`，方向改变
- B. 按范数：`[1.0, 1.0]`；按值：`[0.6, 0.8]`
- C. 两者都得到 `[0.6, 0.8]`
- D. 按范数：`[3.0, 4.0]`（范数大于阈值时不裁剪）；按值：`[1.0, 1.0]`

**Q7.** 关于 float16 混合精度训练中的 loss scaling，正确的是：

- A. 它改变了优化器实际执行的更新量，相当于把学习率放大了 scale 倍
- B. 把 loss 乘以 S，由链式法则所有梯度也乘以 S，从而避开 float16 的下溢区；更新权重前再除以 S，净更新量不变
- C. 它主要解决前向传播中的激活值上溢
- D. 用 bfloat16 训练时同样必须开启 loss scaling

**Q8.** 对数据 `[1000000, 1000001, 1000002]` 用公式 `E[x²] − E[x]²` 求方差，结果明显不准（在 float32 下甚至可能为负数）。根本原因是：

- A. `x²` 上溢成了 inf
- B. 灾难性抵消：`E[x²]` 与 `E[x]²` 都约为 1e12、几乎相等，相减时有效数字被抵消，只剩舍入噪声
- C. 下溢：方差太小，被舍入为 0
- D. 应该除以 n−1 而不是 n

---

## 三、动手 / 代码题

**Q9.** 下面三段代码都取自（或改写自）`numerical.py` 的演示。写出 Python 中**实际**的输出，并逐一解释。

```python
# (a) 来自 demo_cross_entropy
print(cross_entropy_stable(2, [0.0, 0.0, 50.0]))

# (b) 来自 demo_nan_inf：代码里 max 那一行是直接打印字符串 "max = nan"，这里改成真的计算
values = [1.0, 2.0, float('nan'), 4.0, 5.0]
print(sum(values), max(values))

# (c) 来自 demo_catastrophic_cancellation：讲义说这次相减的相对误差是 19.2%
a, b = 1.0000001, 1.0000000
print(abs((a - b) - 1e-7) / 1e-7 * 100)
```

**Q10.** `numerical.py` 定义了下面两个 BCE 函数（但演示里没有调用它们）：

```python
def binary_cross_entropy_naive(y_true, y_pred):
    return -(y_true * math.log(y_pred) + (1 - y_true) * math.log(1 - y_pred))


def binary_cross_entropy_stable(y_true, logit):
    max_val = max(0.0, logit)
    return max_val + math.log(math.exp(-max_val) + math.exp(logit - max_val)) - y_true * logit
```

1. 证明：当 `y_pred = sigmoid(logit)` 时，两者在数学上相等。
2. `binary_cross_entropy_naive(0, sigmoid_stable(1000.0))` 会发生什么？稳定版返回多少？
3. 用 `math.log1p` 把稳定版改写成更常见的形式，并说明 `log1p` 的好处。

**Q11.** 用 `numerical_gradient` 检查 `f(x, y) = x² + 3xy + y³` 在 `(2, 1)` 处的梯度（解析梯度为 `[7, 9]`），把 h 从 `1e-1` 扫到 `1e-13`。

1. 预测 `∂f/∂y` 的数值近似在 `h = 0.1` 时是多少？为什么 `∂f/∂x` 在大 h 下反而几乎精确？
2. 预测 `∂f/∂x` 的相对误差随 h 变化的趋势，并解释原因。
3. 一个有 n 个参数的模型做一次完整的数值梯度检查，需要调用几次 f？这对工程实践意味着什么？

---

## 四、面试高频题

**Q12.**（基础必考）为什么 softmax 要先减最大值？请手推 log-sum-exp 恒等式。PyTorch 的 `nn.CrossEntropyLoss` 为什么要求输入 logits 而不是概率？

**Q13.**（原理深挖）float32、float16、bfloat16 有什么区别？混合精度训练的完整流程是怎样的？为什么用 bfloat16 训练时通常不需要 loss scaling？

**Q14.**（场景设计）大模型训练跑到第 9000 步，loss 突然变成 NaN。请给出你的系统化排查和修复步骤。

**Q15.**（原理深挖）梯度检查怎么做？为什么用中心差分而不是前向差分？h 怎么选？为什么框架做 gradcheck 时推荐用 float64？

**Q16.**（追问型）按值裁剪和按范数裁剪有什么区别？`clip_grad_norm_` 算的是逐个参数的范数还是全局范数？与混合精度一起用时，裁剪应该放在哪一步？

---

## 五、参考答案与解析

### Q1 — 答案：B

bfloat16 = 1 位符号 + 8 位指数 + 7 位尾数，相当于 float32 的高 16 位，所以范围与 float32 相同，但精度更低（约 2–3 位十进制有效数字）。A 反了：float16 有 10 位尾数，精度更高；C 错：float16 只有 5 位指数，最大约 65504（代码中 `float16(70000.0) = inf`）；D 反了：float16 范围小、梯度容易下溢，才需要 loss scaling，bfloat16 通常不需要。

### Q2 — 答案：C

`c = 1000`，`1000 + log(exp(0) + exp(0)) = 1000 + ln 2 ≈ 1000.693`。朴素计算时 `exp(1000)` 在 float64 下也会上溢（Python 的 `math.exp` 会抛 `OverflowError`，NumPy 会得到 `inf`）。B 是常见的"近似直觉"——只有在一个值远大于其他值时，LSE 才约等于最大值（代码中 `[100, 1, 1]` 的结果约为 100.0）。

### Q3 — 答案：B

`log_softmax(z)ᵢ = zᵢ − LSE(z)`，全程只涉及减法和一次稳定的 LSE，不会出现 `log(0)`。代码 `demo_common_bugs` 的 Bug 1 正是这个场景：logits `[100, -100, -100]`、真实类别为 1，概率约 `1.38e-87`，float64 下还勉强能取 log（-200），但在 float32 下 `exp(-200)` 会下溢成 0，`log(0) = −inf`；稳定版直接得到 200.0。A 不是主因；C 错：log 概率 ≤ 0；D 错：log_softmax 内部同样要减最大值。

### Q4 — 答案：B

`((1.1)³ − (0.9)³) / 0.2 = (1.331 − 0.729) / 0.2 = 3.01`。一般地，对 `x³` 有 `(f(x+h) − f(x−h)) / 2h = 3x² + h²`，误差为 h²，即 O(h²)。A（3.31）是前向差分 `(f(1.1) − f(1)) / 0.1` 的结果，误差 `3h + h²`，是 O(h)——这正是讲义推荐中心差分的原因。

### Q5 — 答案：C

`inf − inf` 是 NaN，`math.isnan` 返回 True。A：NaN 与任何值（包括自己）比较都不相等，这也是 `x != x` 可以用来判 NaN 的原因。B：**Python 内置 `max` 不会传播 NaN**——它逐个比较 `x > 当前最大`，与 NaN 的比较永远是 False，所以 NaN 只要不在第一个位置就会被"跳过"，结果是 3.0（本机实测 `max([1.0, 2.0, nan, 4.0, 5.0])` 返回 5.0）；`np.max` 才会返回 nan。D：纯 Python 的 `1.0 / 0.0` 抛出 `ZeroDivisionError`，只有 NumPy / PyTorch 才遵循 IEEE 754 返回 inf（并给出警告）。

### Q6 — 答案：A

按范数：`5 > 1`，缩放系数 `1/5`，得到 `[0.6, 0.8]`，范数为 1，方向不变。按值：每个分量各自夹到 `[-1, 1]`，得到 `[1.0, 1.0]`，方向从 `(3:4)` 变成 `(1:1)`。代码 `demo_gradient_clipping` 用 `[10, 20, 30]` 演示了同样的现象：按值裁剪后比例从 `[1, 2, 3]` 变成 `[1, 1.5, 1.5]`。

### Q7 — 答案：B

反向传播是线性的：`∂(S·L)/∂w = S·∂L/∂w`。float16 最小的正次正规数约 6e-8，比它的一半还小的梯度会被舍入成 0；乘以 S（如 1024）后这些梯度落回可表示范围，更新前除以 S（在 float32 的主权重上进行），净效果与不缩放相同。动态 loss scaling 遇到 inf 就把 S 减半并跳过本步，连续若干步正常就加倍。A 错：除回去之后更新量不变；C 错：它解决的是梯度**下溢**（S 过大反而会造成上溢，所以要动态调整）；D 错：bfloat16 的指数范围与 float32 相同，通常不需要。

### Q8 — 答案：B

`E[x²] ≈ 1.000002e12`，`E[x]² ≈ 1.000002e12`，真正的差只有 0.667，处在第 13 位有效数字上。float64（约 16 位有效数字）下还能剩下几位，所以代码输出 `0.6666259766`、误差 4.07e-05；float32（约 7 位有效数字）下差值完全淹没在舍入误差里，本机实测得到 **-65536**——方差为负，显然荒谬。修复：先减去均值再平方（两遍法），或用 Welford 在线算法（代码中误差为 0）。

### Q9 — 参考答案

实际输出：

```
-0.0
nan 5.0
5.838672220806777e-08
```

- **(a) `-0.0`**：`log_softmax_stable([0, 0, 50])` 中 `lse = 50 + log(1 + 2·e⁻⁵⁰)`，`2·e⁻⁵⁰ ≈ 3.9e-22` 远小于 float64 在 1 附近的精度，`log(1 + …)` 精确地变成 0，于是 `lse = 50.0`、`log_probs[2] = 50 − 50 = 0.0`，取负号得到 IEEE 754 的**负零**。`-0.0 == 0.0` 为 True，不影响计算，只是打印时带了负号——这就是代码输出 `Loss: -0.0000000000` 的原因。
- **(b) `nan 5.0`**：`sum` 会把 NaN 传播出去；而 Python 内置 `max` 用 `>` 比较，与 NaN 的比较全为 False，NaN 被"跳过"，返回 5.0。所以代码中硬编码的 `"max = nan (comparison with nan is always False)"` 对 Python 内置 `max` 并不成立——括号里的理由恰恰解释了为什么 NaN 会被忽略（`np.max` 才会返回 nan）。在训练代码里这比报错更危险：日志里的"最大值"看起来正常，NaN 却被悄悄藏了起来。
- **(c) 约 `5.8e-08`（百分比）**：Python 的 float 是 float64，`1.0000001` 的存储误差在 1e-16 量级，相对 1e-7 的差值来说只有约 6e-10，所以代码打印 `Relative error: 0.0%`。讲义中的 19.2% 是 **float32** 下的结果：`np.float32(1.0000001)` 实际存成 `1.00000011920929`，差值变成 `1.1920929e-07`。要在代码里复现，可以写：

```python
import numpy as np
a32, b32 = np.float32(1.0000001), np.float32(1.0)
d = float(a32 - b32)
print(d, abs(d - 1e-7) / 1e-7 * 100)   # 1.1920928955078125e-07  19.209...
```

### Q10 — 参考答案

1. **推导**：令 `σ = sigmoid(x) = 1/(1+e⁻ˣ)`，则 `log σ = −log(1+e⁻ˣ)`，`log(1−σ) = −x − log(1+e⁻ˣ)`。代入 `−[y·log σ + (1−y)·log(1−σ)]`，得到 `log(1+e⁻ˣ) + (1−y)·x = log(1+eˣ) − y·x = softplus(x) − y·x`。而稳定版中 `m = max(0, x)`，`m + log(e⁻ᵐ + e^{x−m}) = log(1 + eˣ)`（就是对 `[0, x]` 两个数做 log-sum-exp），所以两者相等。本机抽查 `(y, x) = (1, 2.0)、(0, 2.0)、(1, -3.0)、(0, 0.5)`，两种写法结果一致到 1e-15。
2. `sigmoid_stable(1000.0)` 在 float64 下精确等于 1.0，于是朴素版计算 `log(1 − 1.0) = log(0.0)`，Python 抛出 `ValueError: math domain error`（NumPy 下则得到 inf）。稳定版：`m = 1000`，`1000 + log(e⁻¹⁰⁰⁰ + e⁰) − 0 = 1000.0`，正确。
3. 更常见的写法（与稳定版等价）：

```python
def bce_with_logits(y_true, logit):
    return max(logit, 0.0) - logit * y_true + math.log1p(math.exp(-abs(logit)))
```

`math.log1p(t)` 直接计算 `log(1 + t)`，当 t 很小时（`|logit|` 很大，`exp(-|logit|)` 接近 0）不会先把 `1 + t` 舍入成 1 而丢掉 t 的信息；`exp(-|logit|)` 的指数永远 ≤ 0，不会上溢。PyTorch 的 `BCEWithLogitsLoss` 也是基于这种 logits 形式，这就是推荐"把 sigmoid 和 BCE 合并"的原因。

### Q11 — 参考答案

本机实测（相对误差针对 `∂f/∂x`）：

| h | 数值梯度 `[∂x, ∂y]` | `∂f/∂x` 相对误差 |
|---|-------------------|-----------------|
| 1e-1 | `[7.000000000000011, 9.009999999999998]` | 1.5e-15 |
| 1e-3 | `[6.999999999999673, 9.000001000000424]` | 4.7e-14 |
| 1e-5 | `[7.0000000000902665, 9.00000000010337]` | 1.3e-11 |
| 1e-7 | `[6.99999999298484, 8.999999998593466]` | 1.0e-09 |
| 1e-9 | `[7.000000579182597, 9.000000744663339]` | 8.3e-08 |
| 1e-11 | `[6.999911761340627, 9.000089562505309]` | 1.3e-05 |
| 1e-13 | `[6.998845947236987, 9.00612917575927]` | 1.6e-04 |

1. `∂f/∂y` 在 `h = 0.1` 时约为 **9.01**：f 中关于 y 的部分是 `3xy + y³`，中心差分对三次项的截断误差恰好是 `h² = 0.01`。而 f 关于 x 是二次函数（`x² + 3xy`），中心差分对二次函数**没有截断误差**，所以 `∂f/∂x` 在 h=0.1 时也几乎精确。
2. 对 `∂f/∂x` 来说截断误差为 0，误差全部来自**舍入**：`f(x+h)` 与 `f(x−h)` 越来越接近，相减时发生灾难性抵消，误差约为 `ε·|f| / h`（ε ≈ 1e-16），h 每缩小 100 倍、误差就放大约 100 倍。一般函数的总误差 ≈ `C·h² + ε·|f|/h`，呈"先降后升"的 U 形，最优 h 约在 `ε^(1/3) ≈ 1e-5` 附近——这正是代码默认 `h=1e-5`、讲义建议 `1e-5 ~ 1e-7` 的原因。
3. 每个参数要算 `f(x+h)` 和 `f(x−h)` 两次，共 **2n 次**前向计算。一个百万参数的模型就要两百万次前向，所以梯度检查只用于验证新写的层 / 损失函数：在很小的网络、很小的输入上，或者随机抽查少量参数，并用 float64 运行。

### Q12 — 参考回答要点

- **为什么减最大值**：`softmax(z)ᵢ = exp(zᵢ) / Σⱼ exp(zⱼ)`，分子分母同乘 `exp(−c)` 结果不变。取 `c = max(z)` 后最大的指数项为 `exp(0) = 1`：不会上溢；分母 ≥ 1：不会出现 0/0。代码中 `[1000, 1001, 1002]`、`[-1000, -999, -998]` 用稳定版都得到 `[0.090031, 0.244728, 0.665241]`（softmax 对整体平移不变）。
- **推导**：`log Σ exp(xᵢ) = log Σ exp(xᵢ − c)·exp(c) = log[exp(c)·Σ exp(xᵢ − c)] = c + log Σ exp(xᵢ − c)`。
- **CrossEntropyLoss 吃 logits**：它内部等价于 `log_softmax + NLLLoss`，直接用 `z_y − LSE(z)` 计算，既稳定又少一次 exp/log；梯度也简洁：`∂L/∂z = softmax(z) − onehot(y)`（代码 `demo_gradient_checking` 的 Test 2 就是用这个解析梯度通过了检查）。如果先手动 softmax 再传入，就会出现"二次 softmax"或 `log(0)` 的问题。
- **加分点**：在线 softmax / FlashAttention 分块计算时，会维护"当前最大值"和"当前分母"，遇到更大的值时按 `exp(旧max − 新max)` 重新缩放——本质还是 log-sum-exp 技巧。
- **常见误区**：以为减最大值会改变概率；以为 float64 就不需要这个技巧（`exp(710)` 照样上溢）。

### Q13 — 参考回答要点

- **三种格式**：float32（8 位指数 / 23 位尾数，约 7 位有效数字，最大约 3.4e38）；float16（5/10，约 3–4 位有效数字，最大 65504，最小正次正规数约 6e-8）；bfloat16（8/7，约 2–3 位有效数字，范围同 float32）。代码中 `float16(65520.0) = inf`、`bfloat16(100000.0)` 仍是有限值。
- **混合精度流程**（讲义版本）：①保留 float32 主权重；②前向在 float16 / bfloat16 下进行（Tensor Core 加速）；③loss 在 float32 中计算；④反向传播；⑤（float16 时）loss scaling：放大 loss、反向、检查 inf/NaN、除回 scale；⑥在 float32 主权重上更新。实际框架中还会把 softmax、归一化、损失、累加等数值敏感操作保持在 float32。
- **bfloat16 为什么通常不需要 loss scaling**：梯度下溢的根源是指数范围不够，bfloat16 的指数位与 float32 一样多，能表示到约 1e-38 量级的小数。代价是精度低（尾数只有 7 位），所以累加（如矩阵乘的累加器、优化器状态）仍要用 float32。
- **加分点**：知道 bfloat16 与 float32 之间的转换只涉及高 16 位（但框架通常使用"就近舍入"而非简单截断，代码里的 `simulate_bfloat16` 是截断，所以 `0.1` 变成了 `0.0996`）；了解 FP8 训练中常见的 E4M3 / E5M2 两种格式分工。
- **常见误区**：以为"float16 精度更高所以训练更好"——训练中更常见的失败是范围不够导致的上溢 / 下溢。

### Q14 — 参考回答要点

1. **先定位、可复现**：记录出问题的 step 与 batch，固定随机种子，保存 NaN 前一步的 checkpoint 和数据，确认能复现。
2. **查数据**：输入里是否本来就有 NaN / Inf、除零（如归一化时标准差为 0）、异常大的值或错误标签。
3. **查前向**：在各层加 hook，找**第一个**出现非有限值的张量（`torch.isfinite(x).all()`；PyTorch 还提供 `torch.autograd.set_detect_anomaly(True)` 帮助定位反向中的 NaN）；重点关注 `exp`、`log`、`sqrt`、除法、自己写的 softmax / 注意力。
4. **查 loss**：是否用了稳定的 `cross_entropy` / `BCEWithLogits`、`log` 里是否需要 epsilon、mask 后分母是否可能为 0。
5. **查梯度**：每步记录全局梯度范数，NaN 之前通常会先出现梯度尖峰——加梯度裁剪（如 `max_norm=1.0`）、调低学习率或延长 warmup。
6. **查精度**：float16 是否溢出（GradScaler 的 scale 是否持续下降 / 频繁跳步）、是否考虑改用 bfloat16；归一化层的 epsilon 是否太小。
7. **查优化器**：Adam 的 epsilon、权重衰减、学习率调度是否有突变。
- **加分点**：说明 NaN 会在一步内扩散到所有权重，所以"第一个出现 NaN 的位置"才是根因；生产训练中常设置"loss 为 NaN 时跳过本步并告警"，以及从最近的 checkpoint 回滚并跳过坏 batch。

### Q15 — 参考回答要点

- **做法**：对每个参数 θᵢ 计算 `(f(θ + h·eᵢ) − f(θ − h·eᵢ)) / 2h`，与反向传播得到的梯度比较相对误差 `|a − n| / max(|a|, |n|, 1e-8)`；经验阈值：< 1e-7 很好，< 1e-5 可以接受，> 1e-3 基本有 bug。
- **中心 vs 前向**：泰勒展开后，前向差分的误差首项是 `f''(x)·h/2`，为 O(h)；中心差分中偶数阶项相互抵消，误差首项是 `f'''(x)·h²/6`，为 O(h²)。同样的 h，中心差分准确得多（Q4：3.01 vs 3.31）。
- **h 的选择**：总误差 ≈ 截断误差 + 舍入误差 ≈ `C·h² + ε·|f|/h`，h 太小会触发灾难性抵消。float64 下取 `1e-5 ~ 1e-7` 左右。
- **为什么用 float64**：float32 的 ε ≈ 1.2e-7，比 float64 大 8–9 个数量级。按上面的误差模型，最优 h 下的相对误差约为 `ε^(2/3)`：float32 约 1e-5 量级，float64 约 1e-11 量级——float32 的数值梯度本身就不够准，无法支撑 1e-7 量级的比较。PyTorch 的 `torch.autograd.gradcheck` 也建议输入使用双精度。
- **常见误区**：在 ReLU 的拐点、max / abs 等不可导点上做检查，得到虚假的 FAIL；带 dropout 等随机性的函数要先固定随机性。

### Q16 — 参考回答要点

- **按值裁剪**：每个分量独立夹到 `[−v, v]`，实现简单，但会改变梯度方向（Q6）。
- **按范数裁剪**：若 `‖g‖ > max_norm`，整体乘以 `max_norm / ‖g‖`，方向不变、只缩短步长，是 Transformer 训练的标准做法（讲义给出的常见取值：Transformer 1.0、RL 0.5、简单网络 5.0）。
- **全局范数**：`torch.nn.utils.clip_grad_norm_` 把所有参数的梯度拼成一个大向量计算总 L2 范数，再统一缩放，这样各层之间的相对比例保持不变；它会返回裁剪前的总范数，适合写进日志用于监控梯度尖峰。
- **与混合精度的顺序**：使用 float16 + GradScaler 时，梯度里还乘着 scale，必须先 `scaler.unscale_(optimizer)` 把梯度还原，再裁剪，然后 `scaler.step(optimizer)`、`scaler.update()`；否则 max_norm 的含义会被 scale 扭曲。
- **加分点**：指出梯度裁剪并不能修复所有问题——如果每一步都被裁剪，说明学习率过大或模型 / 数据有问题，应该排查根因。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 04 机器学习微积分](../../04-calculus-for-ml/docs/zh.md)：导数、有限差分——梯度检查的数学基础。
- [阶段 01 · 05 Chain Rule 与自动微分](../../05-chain-rule-and-autodiff/docs/zh.md)：反向传播得到的"解析梯度"从哪里来。
- [阶段 01 · 06 概率和分布](../../06-probability-and-distributions/docs/zh.md)：softmax 输出的概率分布。
- [阶段 01 · 09 信息论](../../09-information-theory/docs/zh.md)：交叉熵、KL 散度的定义。
- [阶段 01 · 11 奇异值分解](../../11-singular-value-decomposition/docs/zh.md)：条件数——误差放大的另一种视角。
- [阶段 01 · 12 Tensor 操作](../../12-tensor-operations/docs/zh.md)：在正确的轴上用 `keepdims` 做 max / sum 归约。

### 本节被哪些后续内容用到
- [阶段 01 · 14 范数与距离](../../14-norms-and-distances/docs/zh.md)：L2 范数是按范数梯度裁剪的基础。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：交叉熵、BCE 的稳定实现。
- [阶段 03 · 08 权重初始化](../../../03-deep-learning-core/08-weight-initialization/docs/zh.md)：让激活与梯度在各层保持合适的量级，避免上溢 / 消失。
- [阶段 03 · 13 调试神经网络](../../../03-deep-learning-core/13-debugging-neural-networks/docs/zh.md)：NaN loss、梯度爆炸等故障的系统化排查。
- [阶段 07 · 12 KV Cache 与 Flash Attention](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：分块计算注意力时依赖"在线 softmax"，即增量式的 log-sum-exp。
- [阶段 19 · 45 梯度裁剪与混合精度](../../../19-capstone-projects/45-gradient-clipping-amp/docs/zh.md)：autocast + GradScaler + 全局范数裁剪的完整工程实现。

### 延伸关键词
`ULP / 机器 epsilon` · `次正规数 (subnormal)` · `round-to-nearest-even` · `Kahan / pairwise summation` · `Welford 算法` · `log1p / expm1` · `online softmax` · `torch.autograd.gradcheck` · `GradScaler` · `FP8 (E4M3 / E5M2)` · `torch.use_deterministic_algorithms`
