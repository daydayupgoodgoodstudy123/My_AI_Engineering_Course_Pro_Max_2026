# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 22 节 面向 LLMs 的差分隐私 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`math`、`random`），无第三方包

---

## 1. 这份代码在考察什么

这份代码在一个二维、线性可分的二分类玩具问题上，用纯 Python 实现了 DP-SGD 的两个核心动作，**梯度裁剪 + 高斯噪声**，并扫描噪声乘数 σ ∈ {0, 0.5, 1, 2, 4}，打印"近似 ε"与测试准确率，用来演示讲义所说的隐私—效用权衡：σ 越大，噪声越多，ε 越小，准确率越低。

对照讲义 Use It，需要先说明代码**没有**做到的部分：

| 讲义 Use It 的描述 | 代码实际情况 |
|-----------------|------------|
| 扫描噪声乘数 σ | 有（0 / 0.5 / 1 / 2 / 4） |
| 扫描裁剪范数 C | **没有**，C 固定为 1.0 |
| 跟踪 (ε, δ) 预算 | 只有一个粗略的"代理值"，docstring 自己也说"without a real privacy accountant"；而且该代理值**不是**有效的上界（见 3.4） |
| canary 攻击 + log-loss 检验 | **没有实现**（测验 Q11 给出了实现和实测结果） |

此外，代码的裁剪方式有一个实现问题：权重梯度和偏置梯度**分别**裁剪，导致单样本敏感度为 √2·C（见 3.3）。

> 一句话：**用 100 行代码看清"裁剪 + 加噪"如何以准确率为代价换取隐私；同时以它为反例，学会审视 ε 是怎么算出来的。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random.seed(59)` | 模块级语句 | 固定随机性 | 可复现 |
| `sigmoid(z)` | 函数 | 逻辑函数 | 逻辑回归 |
| `gen(n)` | 函数 | x ~ N(0, I₂)，标签 `y = 1[0.6·x0 − 0.4·x1 > 0]`，无标签噪声 | 线性可分数据 |
| `clip(g, C)` | 函数 | 把向量的 L2 范数裁剪到 ≤ C | 逐样本裁剪 |
| `dp_sgd(data, epochs, lr, sigma, C)` | 函数 | batch = 1 的 DP-SGD：逐样本梯度 → 裁剪 → 加 `N(0, (σC)²)` → 更新 | DP-SGD |
| `accuracy(model, data)` | 函数 | 阈值 0 的分类准确率 | 效用 |
| `analytical_epsilon(sigma, steps, delta)` | 函数 | `√(2 ln(1.25/δ)) · √steps / σ` | （粗略的）隐私会计 |
| `main()` | 函数 | 生成数据，对 5 个 σ 训练、评估、打印 ε 与准确率 | 隐私—效用扫描 |

数据流：`gen(500)` 训练集、`gen(200)` 测试集 → 对每个 σ：`dp_sgd(train_data, ...)` → `accuracy(model, test_data)` + `analytical_epsilon(...)` → 打印一行 → TAKEAWAY。

---

## 3. 逐段精讲

### 3.1 `gen`：一个"太容易"的问题

```python
def gen(n: int) -> list[tuple[list[float], int]]:
    data = []
    for _ in range(n):
        x = [random.gauss(0.0, 1.0), random.gauss(0.0, 1.0)]
        y = 1 if 0.6 * x[0] - 0.4 * x[1] > 0 else 0
        data.append((x, y))
    return data
```

- 标签由一条过原点的直线 `0.6·x0 − 0.4·x1 = 0` 确定，**没有标签噪声**，完全线性可分。无噪声 SGD 的准确率接近 1（实测 30 个种子平均为 0.993）。
- 只有 2 个特征加 1 个偏置，共 3 个参数。噪声的"维度诅咒"在这里几乎不存在，所以较大的 σ 也不会让效用断崖式下跌。真实 LLM 有数十亿参数，同样的 σ 会造成严重得多的效用损失，这也是讲义强调 LoRA + DP-SGD 的原因。

### 3.2 `clip`：L2 范数裁剪

```python
def clip(g: list[float], C: float) -> list[float]:
    n = math.sqrt(sum(x * x for x in g))
    if n <= C:
        return g
    return [x * C / n for x in g]
```

- 范数不超过 C 时原样返回，超过时等比例缩放到恰好为 C，**方向不变**。
- 例：`clip([3, 4], 1) = [0.6, 0.8]`（范数 5 → 1）。
- 这个函数对任意长度的向量都适用，所以修复 3.3 的问题时只需传入 3 维向量。

### 3.3 `dp_sgd`：逐样本裁剪 + 加噪

```python
def dp_sgd(data, epochs: int, lr: float, sigma: float, C: float) -> list[float]:
    w = [0.0, 0.0]
    b = 0.0
    for _ in range(epochs):
        random.shuffle(data)
        for x, y in data:
            z = b + sum(wi * xi for wi, xi in zip(w, x))
            err = sigmoid(z) - y
            grad_w = [err * xi for xi in x]
            grad_b = err
            grad_w = clip(grad_w, C)
            grad_b = max(-C, min(C, grad_b))
            # add noise proportional to sigma * C.
            noise_w = [random.gauss(0.0, sigma * C) for _ in range(2)]
            noise_b = random.gauss(0.0, sigma * C)
            w = [wi - lr * (gi + ni) for wi, gi, ni in zip(w, grad_w, noise_w)]
            b -= lr * (grad_b + noise_b)
    return w + [b]
```

与讲义 DP-SGD 五步的对应：

| 讲义步骤 | 代码 | 差异 |
|---------|------|------|
| 1. 采样 mini-batch | `random.shuffle` 后逐个取，batch = 1 | 真实 DP-SGD 用 Poisson 子采样、batch 成百上千，以获得"子采样放大"，并让相对噪声变小 |
| 2. 逐样本梯度 | `grad_w = err * x`、`grad_b = err` | 逻辑回归的梯度有解析式；深度网络需要 vmap 或 Opacus 之类的工具 |
| 3. 裁剪到 C | `clip(grad_w, C)` + `grad_b` 单独截断 | ⚠️ **分开裁剪**：完整梯度范数最大为 √2·C |
| 4. 求和加噪 `σ·C` | 每个样本都加 `N(0, (σC)²)` | batch = 1 时"求和"就是它自己 |
| 5. 更新 | `w -= lr * (g + noise)` | — |

- ⚠️ **敏感度 bug**：`grad_w` 的范数 ≤ C，`|grad_b|` ≤ C，三维梯度的范数最大为 `√(C² + C²) = √2·C`。噪声标准差仍为 σC，相当于噪声乘数只有 σ/√2，真实 ε 会更大。修正方法是把 `[grad_w0, grad_w1, grad_b]` 拼成一个向量后一起裁剪（测验 Q10）。修正后实测 30 个种子的平均准确率为：σ = 0 → 0.993，σ = 1 → 0.958，σ = 4 → 0.861，与原实现相近。
- `max(-C, min(C, grad_b))` 是标量的"夹逼"（clamp）写法。
- ⚠️ `random.shuffle(data)` **原地**打乱传入的列表，即 `main` 中的 `train_data`。5 个 σ 的运行共用同一个列表和全局随机数流，彼此并不独立；某个 σ 的结果会受前面运行消耗了多少随机数的影响。
- 每个 epoch 中每个样本恰好被使用一次，10 个 epoch 共 10 次。这一点决定了隐私会计应该数"10 次"，而不是 5000 次（见 3.4）。

### 3.4 `analytical_epsilon`：一个不成立的"代理"

```python
def analytical_epsilon(sigma: float, steps: int, delta: float = 1e-5) -> float:
    """Rough Gaussian-mechanism composition proxy.
    Each step contributes roughly 1/(2*sigma^2); composition bounds epsilon
    by sum. Real accountants (RDP, Moments) give tighter bounds."""
    return math.sqrt(2 * math.log(1.25 / delta)) * math.sqrt(steps) / sigma
```

- 公式含义：单步高斯机制的经典校准 `σ = √(2 ln(1.25/δ)) / ε`，反解得到单步 `ε₁ = √(2 ln(1.25/δ)) / σ`，再乘以 `√T`。δ = 1e-5 时，`√(2 ln 125000) = 4.8448`。
- 存在的问题（测验 Q9）：
  1. **docstring 与公式不符**：docstring 说"每步贡献 1/(2σ²)、按求和组合"（RDP 风格），公式却是 `√T × ε₁`。
  2. **单步公式超出适用范围**：经典高斯机制公式只在 ε < 1 时成立，σ = 1 时单步 ε₁ = 4.84。
  3. **√T 组合不是有效上界**：用精确的高斯 DP 组合（T 次噪声乘数为 σ 的高斯机制，等价于 μ = √T/σ 的 μ-GDP）计算，在同样的"5000 步都涉及该样本"假设下，σ = 1 时 ε ≈ 2801，代码给出的 342.6 约**低估了 8 倍**。docstring 中"Real accountants give tighter bounds"的说法，暗示这个代理值是一个偏松的上界，这并不成立。
  4. **步数多算了**：每个样本只参与 10 步，其余步骤对它而言只是后处理。按 T = 10 精确计算：σ = 1 → ε ≈ 17.9；考虑 √2 敏感度 bug 后 ≈ 28.4；σ = 4 → 3.3 或 5.0。
  5. **σ = 0 被替换**：`main` 中调用的是 `analytical_epsilon(max(sigma, 0.01), ...)`，所以 σ = 0 时打印 34257.95，而不是 ∞。
- 结论：表中的 approx-epsilon **只能用来看相对大小**（与 1/σ 成正比），绝对数值没有意义。正式工作应使用 Opacus 等库提供的 RDP/PRV accountant，并配合 Poisson 子采样。

### 3.5 `main`：扫描 σ

```python
    for sigma in (0.0, 0.5, 1.0, 2.0, 4.0):
        model = dp_sgd(train_data, epochs=epochs, lr=0.05, sigma=sigma, C=C)
        acc = accuracy(model, test_data)
        eps = analytical_epsilon(max(sigma, 0.01), steps=epochs * len(train_data), delta=delta)
        print(f"  sigma={sigma:4.1f}  approx-epsilon={eps:7.2f}  test-accuracy={acc:.3f}")
```

- 每个 σ 只训练一次。测试集只有 200 个样本，准确率每变化 0.005 对应 1 个样本。
- `delta = 1e-5`，远小于 1/n = 1/500 = 0.002，满足"δ ≪ 1/n"的惯例。
- `{sigma:4.1f}`：宽度 4、1 位小数；`{eps:7.2f}`：宽度 7、2 位小数，让列对齐。

### 3.6 TAKEAWAY 逐句核对

| 句子 | 评价 |
|------|------|
| "sigma=0 is standard SGD with no privacy (infinite epsilon)" | 正确，但与上方打印的 34257.95 矛盾 |
| "increasing sigma adds noise, shrinks epsilon, and costs accuracy" | 趋势正确（30 个种子平均单调下降），但**本次单次运行**并不单调（σ = 2 为 0.860，σ = 4 为 0.935） |
| "real deployments target epsilon in [1, 10]" | 与讲义的谨慎措辞冲突。讲义说约 1–10 的例子"are illustrative — not recommended defaults"，没有通用的安全 ε |
| "Nasr et al. 2025 shows extraction-based threats persist under moderate epsilon" | 讲义正文没有给出支撑这一具体结论的证据；讲义中的 Nasr 等人工作是作为"训练数据提取能恢复大量记忆"的证据引用的，并未说明是在 DP 模型上 |
| "DP is necessary but not sufficient" | 与讲义的立场一致（还需要防置信度泄露、审计等） |

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 逻辑回归 + 解析梯度 | 逐样本梯度可以直接写出来，不需要框架 | 无法体现 LLM 中逐样本梯度的显存问题；生产中用 Opacus（PyTorch）或 JAX 的 vmap |
| batch = 1、按顺序打乱 | 实现最简单 | 没有子采样放大，相对噪声极大；真实 DP-SGD 用 Poisson 子采样和大 batch |
| w 与 b 分开裁剪 | 写起来直观 | 敏感度变为 √2·C，破坏了 DP 保证的前提；应联合裁剪所有参数的梯度 |
| 闭式"代理 ε" | 不引入 accountant 依赖 | 既多算步数、又用了不成立的组合公式，数值无意义；应使用 RDP/PRV accountant |
| 每个 σ 只跑一次 | 输出简短 | 结论被噪声主导（准确率非单调）；应多种子取均值和区间 |
| 线性可分、3 参数的玩具问题 | 运行快，结果易解释 | 低估高维模型中 DP 噪声的效用代价 |
| 没有 canary 攻击 | 代码量小 | 讲义 Use It 和练习 2 的核心实验缺失；无法从经验上看到 DP 对成员推断的抑制（测验 Q11 补上了这一实验：AUC 0.968 → 0.490） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 第 10 行 | 推迟注解求值 |
| 模块级种子 | `random.seed(59)` | import 时执行，使结果可复现 |
| 类型注解 | `-> list[tuple[list[float], int]]` | 返回 (特征列表, 标签) 的列表 |
| 条件表达式 | `y = 1 if 0.6 * x[0] - 0.4 * x[1] > 0 else 0` | 一行 if-else |
| 生成器表达式求和 | `math.sqrt(sum(x * x for x in g))` | L2 范数 |
| 提前返回 | `if n <= C: return g` | 未超限时直接返回原向量（注意返回的是**同一个**列表对象，不是副本） |
| 列表推导式 | `[x * C / n for x in g]`、`[random.gauss(0.0, sigma * C) for _ in range(2)]` | 逐元素缩放；生成 2 个噪声值 |
| `zip` 三路并行 | `zip(w, grad_w, noise_w)` | 同时遍历参数、梯度和噪声 |
| 夹逼写法 | `max(-C, min(C, grad_b))` | 把标量限制在 [−C, C] 内 |
| 原地打乱 | `random.shuffle(data)` | 会修改调用方传入的列表 |
| 关键字参数调用 | `dp_sgd(train_data, epochs=epochs, lr=0.05, sigma=sigma, C=C)` | 提高可读性，避免参数顺序出错 |
| 默认参数 | `delta: float = 1e-5` | 科学计数法字面量 |
| 元组遍历 | `for sigma in (0.0, 0.5, 1.0, 2.0, 4.0):` | 遍历固定的超参数网格 |
| f-string 宽度与精度 | `{sigma:4.1f}`、`{eps:7.2f}`、`{acc:.3f}` | 对齐输出 |
| 列表拼接返回 | `return w + [b]` | `[w0, w1, b]` |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，约 0.1 秒，退出码 0）：

```text
======================================================================
DP-SGD TOY (Phase 18, Lesson 22)
======================================================================
  sigma= 0.0  approx-epsilon=34257.95  test-accuracy=0.995   ← σ=0 被替换为 0.01，ε 应为 ∞
  sigma= 0.5  approx-epsilon= 685.16  test-accuracy=0.955
  sigma= 1.0  approx-epsilon= 342.58  test-accuracy=0.980   ← 比 σ=0.5 还高：单次运行噪声
  sigma= 2.0  approx-epsilon= 171.29  test-accuracy=0.860
  sigma= 4.0  approx-epsilon=  85.64  test-accuracy=0.935   ← 比 σ=2 还高：单次运行噪声

======================================================================
TAKEAWAY: sigma=0 is standard SGD with no privacy (infinite epsilon).
increasing sigma adds noise, shrinks epsilon, and costs accuracy.
real deployments target epsilon in [1, 10] via accountants like
Moments Accountant. Nasr et al. 2025 shows extraction-based threats
persist under moderate epsilon -- DP is necessary but not sufficient.
======================================================================
```

逐项解读：

- **approx-epsilon 列**：严格与 1/σ 成正比（685.16 = 2 × 342.58 = 4 × 171.29 = 8 × 85.64），只是代理公式的数值，不代表真实的隐私损失（3.4）。对照更合理的估计（GDP 精确组合，T = 10，不计子采样放大）：σ = 0.5 / 1 / 2 / 4 分别约为 46 / 18 / 7.5 / 3.3。
- **test-accuracy 列**：单次运行不单调。附加实验对每个 σ 跑 30 个种子（每次重新生成数据），平均准确率为 0.993 / 0.981 / 0.958 / 0.923 / 0.868，标准差为 0.006 / 0.014 / 0.030 / 0.058 / 0.096。均值单调下降、方差单调上升，这才是"噪声换隐私"的真实图景。
- **"效用崩溃点"**（讲义练习 1）：在这个 3 参数问题上，σ ≤ 4 时没有断崖。但 σ = 4 时最差的种子只有 0.69，**可靠性先于平均效用崩溃**。
- **隐私的经验效果**（测验 Q11 的附加实验）：插入一个错标的 canary，σ = 0 时成员推断 AUC = 0.968，σ = 1 时 AUC = 0.490（随机水平），直观地说明了噪声对单样本影响的遮蔽作用。

---

## 7. 动手改一改

1. **修复裁剪**：把 `[grad_w0, grad_w1, grad_b]` 合成一个向量后一起裁剪、一起加噪（测验 Q10），确认准确率变化不大，但现在敏感度确实为 C。
2. **独立实验**：每个 σ 用 `random.seed(base + k)` 重新生成数据，并传入 `list(train_data)` 的副本，避免原地 shuffle 带来的耦合；跑 30 个种子报告均值和标准差（测验 Q12）。
3. **扫描 C**（讲义 Use It）：固定 σ = 1，扫描 C ∈ {0.1, 0.5, 1, 2, 5}。C 太小，梯度被过度截断，学得慢；C 太大，噪声 σC 过大。观察准确率是否在中间某个 C 处最高。
4. **canary 攻击**（讲义练习 2）：实现测验 Q11 的 canary + log-loss 检验和 AUC，扫描 σ ∈ {0, 0.25, 0.5, 1}，画出 "AUC–σ" 曲线；再尝试让 canary 重复出现 k 次，观察 AUC 如何随 k 上升（这对应"用户级 vs 样本级 DP"）。
5. **正规 accountant**：改为 Poisson 子采样（每步以概率 q 选入每个样本）、batch 求和后只加一次噪声；用精确的高斯 DP 组合或 RDP 公式（可借助 `scipy.stats.norm`）计算 ε，与 `analytical_epsilon` 对比。
6. **进阶**：用 PyTorch + Opacus 在一个小型文本分类器（或 LoRA 微调的小语言模型）上复现 σ 扫描，记录 Opacus accountant 给出的 ε，并在相同 ε 下比较全参数 DP 与 LoRA DP 的效用差异。

---

## 8. 常见坑

- **分开裁剪各参数块**：敏感度会变成各块裁剪阈值的平方和再开方（本例为 √2·C），而噪声仍按 C 加，DP 保证就失效了。
- **把代理 ε 当真**：代码的 approx-epsilon 既不是上界，也不是下界；报告 ε 时必须写明 accountant、δ、采样方式和隐私单位。
- **把 σ = 0 的 ε 写成有限值**：没有噪声就没有 DP，ε = ∞。
- **单次运行下结论**：本例准确率随 σ 非单调变化，完全是噪声造成的。
- **原地修改共享数据**：`random.shuffle(data)` 会改动调用方的列表，多次实验之间相互耦合。
- **混淆样本级与用户级隐私**：同一个用户的多条数据会使对该用户的有效 ε 成倍增加；canary 重复插入的实验能直观演示这一点。
- **以为 LoRA + DP 保护了一切**：只有 adapter 所用的微调数据受保护，基座模型的记忆不在保证范围内。
- **只看训练、不看部署**：暴露置信度或 logprobs 会引入 DP Reversal 风险（讲义），这需要训练之外的防护。
- **被中文讲义误导**：机器翻译丢失了大量 ε、δ、σ 符号（如"(, )-DP"），并把 canary 译成"加那利岛"，请以英文讲义为准。
