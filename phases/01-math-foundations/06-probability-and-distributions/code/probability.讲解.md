# 代码讲解 · probability.py

> **所属小节**：阶段 01 · 数学基础 · 第 06 节 概率和分布 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python probability.py`（会在当前目录生成 `probability_distributions.png`） ｜ **依赖**：Python 标准库（`math`、`random`）；可视化部分可选用 `matplotlib`（未安装时自动跳过）

---

## 1. 这份代码在考察什么

这份代码把"AI 里用到的概率"拆成一组纯 Python 小函数，每个函数都对应讲义里的一个公式：

1. **概率的基本运算**：阶乘、组合数、条件概率。
2. **PMF 与 PDF**：Bernoulli、Categorical、Poisson（离散）以及 Uniform、Normal（连续）的概率函数。
3. **期望与方差**：加权平均和"离均值多远"的加权平均。
4. **采样**：如何只用 `random.random()`（`[0,1)` 均匀分布）造出 Bernoulli、Categorical、Uniform 和正态分布的样本。
5. **分类模型的概率工具**：数值稳定的 softmax、log-softmax、交叉熵——这三个函数就是每个分类器、每个语言模型输出层背后的东西。
6. **联合/边缘分布与独立性检验**，以及用实验验证**中心极限定理**。

> 一句话：**模型的每次预测都是一个概率分布，每个损失函数都在衡量两个分布的差距**——这份代码让你亲手把这些分布算出来、采出来。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `factorial` / `combinations` | 函数 | 阶乘、组合数（`combinations` 定义了但未使用） | 计数 |
| `conditional_probability` | 函数 | `P(A∩B) / P(B)` | 条件概率 |
| `bernoulli_pmf` / `categorical_pmf` / `poisson_pmf` | 函数 | 离散分布的概率质量函数 | PMF |
| `uniform_pdf` / `normal_pdf` | 函数 | 连续分布的概率密度函数 | PDF |
| `expected_value` / `variance` | 函数 | 离散分布的期望和方差 | 期望、方差 |
| `sample_bernoulli` / `sample_categorical` / `sample_uniform` / `sample_normal_box_muller` | 函数 | 从各分布采样（`sample_uniform` 未在演示中使用） | 采样 |
| `softmax` / `log_softmax` / `cross_entropy_loss` | 函数 | logits → 概率 / 对数概率 / 损失 | 分类输出层 |
| `joint_to_marginals` / `check_independence` | 函数 | 联合分布 → 边缘分布；检验独立 | 联合与边缘分布 |
| `demonstrate_clt` | 函数 | 反复求 n 个样本的均值 | 中心极限定理 |
| `if __name__ == "__main__":` | 演示入口 | 依次打印所有演示，最后画 2×3 的图 | — |

数据流：所有函数都是独立的"纯函数"（除采样函数依赖全局随机状态），`__main__` 按讲义顺序逐个调用并打印，最后在 `try` 块中用 matplotlib 汇总成一张图。

---

## 3. 逐段精讲

### 3.1 模块级随机种子

```python
import math
import random

random.seed(42)
```

- 在**导入时**就固定随机种子，保证每次运行的采样结果一致，便于对照输出。
- ⚠️ 副作用：别的文件 `import probability` 时也会重置全局随机状态。库代码一般不应在模块顶层设种子，而应在 `main` 里设置，或者使用独立的 `random.Random(42)` 实例。

### 3.2 计数与条件概率

```python
def factorial(n):
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def combinations(n, k):
    return factorial(n) // (factorial(k) * factorial(n - k))


def conditional_probability(p_a_and_b, p_b):
    return p_a_and_b / p_b
```

- `factorial` 用循环而不是递归，避免大 n 时递归过深；`range(2, n + 1)` 跳过了乘 1，`factorial(0)` 和 `factorial(1)` 都返回 1。
- `combinations` 用整除 `//`：组合数一定是整数，整除保证结果是 `int` 而不是 `float`。（Python 3.8+ 有现成的 `math.comb`、`math.factorial`。）
- `conditional_probability(4/52, 12/52)` 计算 `P(King | 人头牌) = 1/3`，与讲义例子一致。⚠️ `p_b = 0` 时会除零——条件事件不可能发生时，条件概率本来就没有定义。

### 3.3 PMF：Bernoulli、Categorical、Poisson

```python
def bernoulli_pmf(k, p):
    return p if k == 1 else (1 - p)


def categorical_pmf(k, probs):
    return probs[k]


def poisson_pmf(k, lam):
    return (lam ** k) * math.exp(-lam) / factorial(k)
```

| 分布 | 公式 | 均值 | 方差 | AI 中的用途 |
|------|------|------|------|-----------|
| Bernoulli(p) | `P(1)=p, P(0)=1-p` | p | p(1-p) | 二分类（sigmoid 输出） |
| Categorical(p₁…pₖ) | `P(i)=pᵢ` | — | — | 多分类、下一个 token（softmax 输出） |
| Poisson(λ) | `λᵏe^{-λ}/k!` | λ | λ | 单位时间内稀有事件计数 |

- `bernoulli_pmf` 用条件表达式；⚠️ 它对任何 `k != 1` 都返回 `1 - p`（比如 `k = 5`），没有校验输入。
- `categorical_pmf` 就是查表——Categorical 分布本身就是"一张概率表"。
- ⚠️ `poisson_pmf` 直接计算 `λᵏ` 和 `k!`，k 较大时会溢出：实测 `poisson_pmf(171, 100.0)` 和 `poisson_pmf(200, 3)` 都抛 `OverflowError`，而真实概率是普通的小数。稳妥写法是在对数空间计算：`exp(k·ln λ - λ - lgamma(k+1))`（测验 Q10）。

### 3.4 PDF：Uniform 与 Normal

```python
def uniform_pdf(x, a, b):
    if a <= x <= b:
        return 1.0 / (b - a)
    return 0.0


def normal_pdf(x, mu, sigma):
    coeff = 1.0 / (sigma * math.sqrt(2 * math.pi))
    exponent = -0.5 * ((x - mu) / sigma) ** 2
    return coeff * math.exp(exponent)
```

- `a <= x <= b` 是 Python 的**链式比较**，等价于 `a <= x and x <= b`。
- 均匀分布在 `[a, b]` 上的密度是 `1/(b-a)`，保证总面积为 1。
- `normal_pdf` 把公式拆成"归一化系数 × 指数项"，先算 `(x - mu) / sigma`（标准化后的距离）再平方，可读性好。
- **参数是标准差 σ，不是方差 σ²**。可视化里的图例 `N(0,2)` 指的是 σ = 2；而数学上 `N(μ, σ²)` 的第二个参数通常是**方差**——读论文和调用库时要分清（`np.random.normal`、`scipy.stats.norm` 的 `scale` 参数也都是标准差）。
- PDF 的值可以大于 1：σ 很小时峰值很高（`normal_pdf(0, 0, 0.1) ≈ 3.99`），这不违反任何规则，因为密度不是概率。

### 3.5 期望与方差

```python
def expected_value(values, probabilities):
    return sum(v * p for v, p in zip(values, probabilities))


def variance(values, probabilities):
    mu = expected_value(values, probabilities)
    return sum(p * (v - mu) ** 2 for v, p in zip(values, probabilities))
```

- 直接对应定义：`E[X] = Σ xᵢpᵢ`，`Var(X) = Σ pᵢ(xᵢ - μ)²`。
- 用"先求均值、再求偏差平方的期望"的两遍算法，而不是 `E[X²] - E[X]²`。后者在数值上可能出现两个大数相减的精度损失（当均值远大于标准差时），两遍法更稳。
- 公平骰子：`E[X] = 3.5`，`Var(X) = 35/12 ≈ 2.9167`，标准差约 1.7078。

### 3.6 采样：Bernoulli 与 Categorical

```python
def sample_bernoulli(p, n=1):
    return [1 if random.random() < p else 0 for _ in range(n)]


def sample_categorical(probs, n=1):
    cumulative = []
    total = 0
    for p in probs:
        total += p
        cumulative.append(total)
    samples = []
    for _ in range(n):
        r = random.random()
        for i, c in enumerate(cumulative):
            if r <= c:
                samples.append(i)
                break
    return samples
```

- **Bernoulli**：`random.random()` 落在 `[0, p)` 的概率正好是 p。
- **Categorical（离散版逆变换采样）**：先算累积概率，如 `[0.1, 0.3, 0.4, 0.2]` → `[0.1, 0.4, 0.8, 1.0]`，把 `[0,1)` 切成长度为各类概率的小段；再看随机数 r 落在哪一段。
- `for ... break` 找到第一个 `r <= c` 就停止。复杂度每次 O(k)；k 很大（如 5 万词表）时应改用二分查找 `bisect`，O(log k)。
- ⚠️ **静默丢样本**：如果累积和最后小于 1（概率没有精确归一化，或者浮点累加误差），r 落在最后一段之外时内层循环不会 `append` 任何东西，也不报错。实测 `sample_categorical([0.33, 0.33, 0.33], 1000)` 只返回了 **995** 个样本。修复方法是把 r 乘以 `total`，并在找不到时兜底返回最后一类（测验 Q9）。

### 3.7 采样：Uniform 与 Box-Muller 正态

```python
def sample_uniform(a, b, n=1):
    return [a + (b - a) * random.random() for _ in range(n)]


def sample_normal_box_muller(mu, sigma, n=1):
    samples = []
    for _ in range(n):
        u1 = random.random()
        u2 = random.random()
        z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
        samples.append(mu + sigma * z)
    return samples
```

- **均匀分布**：把 `[0,1)` 线性拉伸平移到 `[a, b)`。
- **Box-Muller 变换**：两个独立的 `[0,1)` 均匀随机数 `u1, u2`，经过 `√(-2 ln u1) · cos(2π u2)` 得到一个标准正态样本 z；再用 `μ + σz` 变换到任意 `N(μ, σ²)`。直觉：`√(-2 ln u1)` 生成二维正态点到原点的距离（半径），`2π u2` 生成均匀的角度。
- ⚠️ 原始 Box-Muller 每次能同时得到**两个**独立正态样本（`cos` 和 `sin` 各一个），这里只用了 `cos`，浪费了一半随机数。
- ⚠️ `random.random()` 的取值范围是 `[0, 1)`，理论上可能恰好返回 0.0，此时 `math.log(0)` 抛 `ValueError: math domain error`。概率约 2⁻⁵³，几乎不会发生，但稳妥写法是 `u1 = 1.0 - random.random()`，取值落在 `(0, 1]`。
- `mu + sigma * z` 体现了一个重要思想：**先从标准分布采样，再做确定性变换**——这正是 VAE 里"重参数化技巧"的核心。

### 3.8 Softmax、log-softmax 与交叉熵

```python
def softmax(logits):
    max_logit = max(logits)
    shifted = [z - max_logit for z in logits]
    exps = [math.exp(z) for z in shifted]
    total = sum(exps)
    return [e / total for e in exps]


def log_softmax(logits):
    max_logit = max(logits)
    shifted = [z - max_logit for z in logits]
    log_sum_exp = max_logit + math.log(sum(math.exp(z) for z in shifted))
    return [z - log_sum_exp for z in logits]


def cross_entropy_loss(logits, target_index):
    log_probs = log_softmax(logits)
    return -log_probs[target_index]
```

这三个函数是本文件最重要的部分：

- **softmax 先减最大值**：数学上 `softmax(z) = softmax(z - c)`（分子分母同乘 `e^{-c}`），减去 `max` 后最大的指数变成 `e⁰ = 1`，其余都 ≤ 1，**不会上溢**；分母至少为 1，**不会除以 0**。不减的话 `math.exp(1000)` 直接抛 `OverflowError`。
- **log-softmax 用 log-sum-exp**：`log softmax(z)ᵢ = zᵢ - log Σⱼ e^{zⱼ}`，而 `log Σ e^{zⱼ} = m + log Σ e^{zⱼ - m}`。注意最后一行用的是**原始** `logits` 减 `log_sum_exp`（`z - log_sum_exp for z in logits`），因为 `log_sum_exp` 已经把 `max_logit` 加回去了。
- **为什么不写 `math.log(softmax(z)[i])`**：当某个概率小到下溢为 0 时，`log(0)` 报错（或在 NumPy 中得到 `-inf`）。log-softmax 全程在对数空间计算，实测 `log_softmax([1000.0, 0.0])` 精确地得到 `[0.0, -1000.0]`。
- **交叉熵**：one-hot 标签下 `H = -log q_target`，只需要取正确类别的对数概率再取负。这就是讲义说的"交叉熵是正确类别的负对数概率"，也就是负对数似然（NLL）。PyTorch 的 `nn.CrossEntropyLoss` 内部做的正是 log-softmax + NLL，所以它要求输入 logits 而不是概率。

### 3.9 联合分布、边缘分布与独立性检验

```python
def joint_to_marginals(joint):
    rows = len(joint)
    cols = len(joint[0])
    marginal_x = [sum(joint[i][j] for j in range(cols)) for i in range(rows)]
    marginal_y = [sum(joint[i][j] for i in range(rows)) for j in range(cols)]
    return marginal_x, marginal_y


def check_independence(joint, marginal_x, marginal_y, tol=1e-9):
    for i in range(len(marginal_x)):
        for j in range(len(marginal_y)):
            if abs(joint[i][j] - marginal_x[i] * marginal_y[j]) > tol:
                return False
    return True
```

- **边缘分布**：X 的边缘是联合表**每行求和**，Y 的边缘是**每列求和**——"把另一个变量求和消掉"。
- **独立性**：当且仅当每个格子都满足 `P(x, y) = P(x)·P(y)`。只要有一个格子不满足就提前 `return False`。
- 用容差 `tol=1e-9` 比较浮点数，避免 `0.1 * 0.3` 这类舍入误差导致误判。
- 演示中的天气-带伞表：`P(晴, 不带伞) = 0.40`，而 `P(晴)·P(不带伞) = 0.5 × 0.45 = 0.225`，不独立——下雨的人更可能带伞，这很符合常识。
- ⚠️ 这里检验的是**给定的真实分布**是否独立。如果联合表是从样本估计出来的，即使真实独立，估计值也几乎不可能精确满足等式，需要用卡方检验等统计方法判断（阶段 01 第 15 节）。

### 3.10 中心极限定理演示

```python
def demonstrate_clt(dist_fn, n_per_sample, n_averages):
    averages = []
    for _ in range(n_averages):
        samples = [dist_fn() for _ in range(n_per_sample)]
        averages.append(sum(samples) / len(samples))
    return averages
```

```python
    for n in [1, 2, 5, 30]:
        avgs = demonstrate_clt(random.random, n, 10000)
        avg_mean = sum(avgs) / len(avgs)
        avg_std = (sum((x - avg_mean) ** 2 for x in avgs) / len(avgs)) ** 0.5
```

- `dist_fn` 是一个**无参函数**，这里直接传 `random.random`（注意没有括号——传的是函数本身，不是调用结果）。换成任何其他采样函数都可以。
- 对每个 n，做 10000 次"取 n 个样本求平均"，再看这 10000 个平均值的均值和标准差。
- 理论：`[0,1)` 均匀分布均值 0.5、标准差 `1/√12 ≈ 0.2887`；n 个样本均值的标准差为 `0.2887/√n`。
- ⚠️ CLT 要求原始分布**方差有限**。讲义说"适用于任何初始分布"是简化说法，柯西分布这类方差无穷的分布就不满足。

### 3.11 可视化：可选依赖与无界面后端

```python
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 3, figsize=(15, 9))
        # ... 6 个子图 ...
        plt.tight_layout()
        plt.savefig("probability_distributions.png", dpi=150)
        print("  Saved: probability_distributions.png")
        plt.close()

    except ImportError:
        print("  matplotlib not available, skipping visualization.")
```

- `matplotlib.use("Agg")` 选择**无图形界面**的后端，在服务器、容器、CI 中也能画图，只保存文件不弹窗。惯例是在 `import matplotlib.pyplot` **之前**调用，代码也是这么写的。
- `plt.subplots(2, 3)` 返回 2×3 的子图数组，用 `axes[0][1]` 定位。
- 直方图 `ax.hist(..., density=True)` 把纵轴归一化为**密度**，不同 n 的直方图才能放在一起比较，也才能和 PDF 对比。
- softmax 子图用 `offset = (idx - 1) * width` 让三组柱子并排而不重叠。
- `plt.close()` 释放图形内存，在循环中画很多图时尤其重要。
- 图片保存在**当前工作目录**，所以应该在代码所在目录（或临时目录）运行。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 全部用纯 Python 函数 | 每个公式一目了然 | 慢；生产用 NumPy / SciPy / PyTorch 向量化实现 |
| 模块顶层 `random.seed(42)` | 输出可复现 | 导入即修改全局随机状态；应在 `main` 中设种子或用独立生成器 |
| `poisson_pmf` 直接算 `λᵏ/k!` | 与公式一一对应 | 大 k 溢出；应用 `lgamma` 在对数空间计算 |
| softmax 减最大值、log-softmax 用 log-sum-exp | 防止上溢 / 下溢 | 几乎没有代价，是业界标准写法 |
| 交叉熵基于 log-softmax 而不是 log(softmax) | 数值稳定、梯度好 | 与 PyTorch `CrossEntropyLoss` 的做法一致 |
| `sample_categorical` 线性扫描累积表 | 最直观 | O(k)；没有兜底会静默丢样本；生产用 `bisect`、`random.choices` 或 `torch.multinomial` |
| Box-Muller 只取 cos 分支 | 代码最短 | 浪费一半随机数；`log(0)` 的边界未处理 |
| 方差用两遍法 | 数值更稳 | 需要遍历两次数据 |
| matplotlib 可选 + `Agg` 后端 | 无依赖、无界面也能跑 | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 整除 `//` | `factorial(n) // (factorial(k) * factorial(n - k))` | 向下取整的除法，整数结果 |
| 增量赋值 | `result *= i`、`total += p` | `a op= b` 即 `a = a op b` |
| 条件表达式 | `p if k == 1 else (1 - p)` | 一行 if-else |
| 链式比较 | `a <= x <= b` | 等价于 `a <= x and x <= b` |
| 默认参数 | `def sample_bernoulli(p, n=1)`、`tol=1e-9` | 调用时可省略 |
| 列表推导式 | `[1 if random.random() < p else 0 for _ in range(n)]` | 推导式里也能用条件表达式 |
| 生成器表达式 | `sum(v * p for v, p in zip(values, probabilities))` | 不建中间列表直接求和 |
| `zip` | `zip(values, probabilities)` | 按位置配对两个序列 |
| `enumerate` | `for i, c in enumerate(cumulative)` | 同时拿到下标和元素 |
| `for ... break` | 找到第一个 `r <= c` 就跳出 | 提前结束循环 |
| 提前 `return` | `check_independence` 中 `return False` | 一旦确定结果就返回 |
| 函数作为参数 | `demonstrate_clt(random.random, n, 10000)` | 传函数对象本身，不加括号 |
| 返回多个值 | `return marginal_x, marginal_y` | 返回元组，用两个变量接收 |
| 列表乘法 | `[1 / 6] * 6` | 生成 6 个相同元素（不可变元素时安全） |
| `list.count` | `cat_samples.count(i)` | 统计某个值出现的次数（每次 O(n)） |
| `str.join` + 推导 | `', '.join(f'{p:.4f}' for p in probs)` | 把多个格式化数字拼成一个字符串 |
| f-string 格式 | `{p:.4f}`、`{x:+d}`、`{raw_product:.2e}`、`{n:2d}` | `+d` 显示正负号的整数；`.2e` 科学计数法 |
| f-string 嵌套引号 | `f"  Softmax: [{', '.join(f'{p:.4f}' for p in probs)}]"` | 外层双引号、内层单引号 |
| `try / except ImportError` | 可视化部分 | 可选依赖缺失时优雅跳过 |
| `math` 函数 | `math.exp`、`math.log`、`math.sqrt`、`math.pi`、`math.cos` | 标准库数学函数 |
| `random` 函数 | `random.seed`、`random.random` | 固定种子；`[0,1)` 均匀随机数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行全部演示 |

---

## 6. 运行结果解读

在临时副本中实际运行 `python3 probability.py`（约 2 秒），关键输出如下：

```text
P(King | Face card) = 0.3333

--- PMF: Poisson (lambda=3) ---
  P(X=0) = 0.0498
  P(X=2) = 0.2240
  P(X=3) = 0.2240        ← λ 为整数时，k=λ-1 与 k=λ 概率相等
  P(X=9) = 0.0027

--- PDF: Normal (mu=0, sigma=1) ---
  f(+0) = 0.3989         ← 1/√(2π)
  f(+1) = 0.2420
  f(+3) = 0.0044         ← 关于 0 对称
```

```text
  Fair die: E[X] = 3.5000, Var(X) = 2.9167, SD = 1.7078
```

```text
--- Sampling: Bernoulli (p=0.3, n=20) ---
  Samples: [0, 1, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 1, 1, 0, 0, 1, 0, 0, 1]
  Empirical mean: 0.5000 (expected 0.3)
```

20 个样本的经验均值是 0.5，离 0.3 差得不少——这不是 bug，而是**小样本的波动**：样本均值的标准差为 `√(0.3×0.7/20) ≈ 0.10`，0.5 大约偏离 2 个标准差，不常见但完全可能。这恰好说明了 CLT/大数定律的另一面：样本少时估计不可靠。

```text
  Counts from 1000 samples: [88, 285, 415, 212]
  Empirical: [0.088, 0.285, 0.415, 0.212]
  Expected:  [0.1, 0.3, 0.4, 0.2]

  Sample mean: 0.0036 (expected 0)
  Sample var:  0.9819 (expected 1)
```

1000 个样本时经验频率已接近真实概率；Box-Muller 的 10000 个样本均值与方差也很接近 N(0,1)。

```text
  Softmax: [0.6590, 0.2424, 0.0986]
  Sum:     1.0000

  Logits:  [100, 101, 102]
  Softmax: [0.0900, 0.2447, 0.6652]     ← 与 softmax([0,1,2]) 相同，无溢出

  Log-softmax: [-0.4170, -1.4170, -2.3170]
  Verify exp:  [0.6590, 0.2424, 0.0986]  ← exp 回去等于 softmax

  Cross-entropy loss: 0.4170             ← = -log(0.6590)
```

- log-softmax 三个值之间恰好相差 1.0 和 0.9，正是 logits 之间的差——log-softmax 只是把 logits 整体平移了 `logsumexp`。
- 目标类别 0 的交叉熵就是 log-softmax 第 0 项取负。

```text
  Raw product: 1.00e-100 (underflows with more terms)
  Log sum:     -230.2585 (stable)
  Recovered:   1.00e-100
```

`0.01⁵⁰ = 1e-100` 在 float64 中还能表示（实测要到约 162 次方才变成 0.0；float32 则约 23 次方就归零）。真实语言模型的序列更长、单个概率更小，所以一定要用对数和：`50 × ln 0.01 = -230.26`。

```text
  Marginal X (weather):  [0.5, 0.5]
  Marginal Y (umbrella): [0.45, 0.55]
  Independent? False

  Averaging uniform [0,1) samples:
    n= 1: mean=0.4971, std=0.2866        ← 理论 0.2887
    n= 2: mean=0.4995, std=0.2044        ← 理论 0.2041
    n= 5: mean=0.5003, std=0.1287        ← 理论 0.1291
    n=30: mean=0.5005, std=0.0524        ← 理论 0.0527
```

均值始终在 0.5 附近，标准差严格按 `0.2887/√n` 缩小，CLT 的定量预测被完美验证。

```text
--- Visualization ---
  Saved: probability_distributions.png
```

生成的 2×3 图（已实际查看）：
- **Bernoulli PMF**：两根柱子 0.3 和 0.7。
- **Poisson PMF (λ=3)**：k=2、3 最高（约 0.224），右侧拖尾。
- **Normal PDF**：`N(0,1)` 峰值约 0.4；`N(0,2)`（σ=2）更矮更宽，峰值约 0.2；`N(2,0.5)`（σ=0.5）又高又窄，峰值约 0.8。
- **Uniform PDF [1, 4]**：高度 1/3 的矩形。
- **CLT**：n=1 时直方图是平的，n=2 呈三角形，n=5 已经像钟形，n=30 是又高又窄的钟形——"均值的分布越来越像正态、越来越集中"一图可见。
- **Softmax**：`[1,1,1]` 输出均匀的 1/3；`[2,1,0]` 有明显偏好；`[10,1,0]` 几乎全部概率（约 0.9998）给了第 0 类——logits 差距越大，分布越尖锐（这就是 temperature 的原理）。

---

## 7. 动手改一改

1. **修复采样器**：给 `sample_categorical` 加上"按 `total` 缩放 + 二分查找 + 兜底"，用 `[0.33, 0.33, 0.33]` 验证返回长度为 n（参考测验 Q9）。
2. **对数空间的泊松**：用 `math.lgamma` 重写 `poisson_pmf`，验证与原实现在小 k 时一致，并能算出 `poisson_pmf(171, 100.0)`（参考测验 Q10）。
3. **逆变换采样**（讲义练习 1）：实现指数分布采样 `x = -ln(1-u)/λ`，采 10000 个样本，对比直方图密度与真实 PDF（参考测验 Q12）。
4. **加载骰子的联合分布**（讲义练习 2）：构造两个不均匀骰子的 6×6 联合表（例如先定义两个边缘分布再相乘，得到独立的情况；再手动改几个格子制造相关），用 `joint_to_marginals` 和 `check_independence` 验证。
5. **温度采样**：写 `sample_with_temperature(logits, T)`，先 `softmax([z / T for z in logits])` 再用 `sample_categorical` 采样，分别取 T = 0.1、1、10 各采 1000 次，观察计数分布的变化。
6. **CLT 换分布**：把 `demonstrate_clt` 的 `dist_fn` 换成指数分布采样器（偏态分布），观察 n=1、5、30 时直方图如何从偏斜变得对称；再换成柯西分布 `math.tan(math.pi * (random.random() - 0.5))`，观察 n 增大时均值的波动为什么**不**缩小。

---

## 8. 常见坑

- **把 PDF 的值当概率**：密度可以大于 1，单点概率为 0；要对区间积分（或在直方图里乘以组宽）。
- **`N(μ, σ)` 还是 `N(μ, σ²)`**：本代码和大多数库的参数是标准差，而数学记号常写方差；传错会让分布宽度差一个平方。
- **不做数值稳定处理的 softmax**：logits 稍大就 `OverflowError` / `nan`；`log(softmax(z))` 可能得到 `-inf`。要用减最大值和 log-sum-exp。
- **把 softmax 后的概率传给 `CrossEntropyLoss`**：等于做了两次 softmax，loss 和梯度都不对。
- **概率没有精确归一化就去采样**：本文件的 `sample_categorical` 会静默少返回样本。
- **`random.random()` 可能为 0**：`math.log(random.random())` 在极小概率下会报错，用 `1 - random.random()`。
- **用小样本下结论**：20 次伯努利试验的经验均值可以偏离真值 0.2，评估模型时也一样，样本量决定了置信区间的宽度。
- **模块顶层设随机种子**：导入即改变全局随机状态，可能让其他模块的"随机"变得意外地可预测。
