# 测验 · 概率和分布（Probability and Distributions）

> **阶段 01 · 数学基础 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/probability.py](../code/probability.py) ｜ 代码讲解：[code/probability.讲解.md](../code/probability.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 样本空间、事件与三条公理 | 概率把事件映射到 [0,1]：非负、全空间为 1、互斥事件可加；其余结论都由此推出 |
| 2 | 条件概率与独立 | `P(A|B) = P(A∩B)/P(B)`；独立当且仅当 `P(A∩B) = P(A)·P(B)`；`P(A|B)` 与 `P(B|A)` 一般不相等 |
| 3 | PMF vs PDF | 离散变量的 PMF 直接给出概率；连续变量的 PDF 是**密度**，要对区间积分才是概率，单点密度可以大于 1 |
| 4 | 常见分布 | Bernoulli（二分类）、Categorical（多分类 / softmax 输出）、Uniform（初始化）、Normal（钟形曲线）、Poisson（稀有事件计数，均值 = 方差 = λ） |
| 5 | 期望与方差 | `E[X] = Σ xᵢ·P(xᵢ)`；`Var(X) = E[(X-μ)²] = E[X²] - (E[X])²`；损失函数本质上是期望 |
| 6 | 联合与边缘分布 | 边缘分布 = 对另一个变量求和；联合概率处处等于边缘之积才独立 |
| 7 | 中心极限定理（CLT） | 独立同分布、方差有限的变量，其均值近似服从正态分布，标准差按 `σ/√n` 缩小 |
| 8 | 对数概率 | `log(ab) = log a + log b`，把连乘变成求和，避免长序列概率下溢 |
| 9 | Softmax 与数值稳定 | `softmax(z)ᵢ = e^{zᵢ} / Σⱼ e^{zⱼ}`；先减去最大 logit 防止溢出，结果不变；log-softmax 用 log-sum-exp 实现 |
| 10 | 交叉熵 | 分类时交叉熵 = 正确类别的负对数概率 `-log qᵧ`，即负对数似然（NLL） |
| 11 | 采样 | 离散分布用累积分布 + 均匀随机数查找；正态分布可用 Box-Muller 变换；其他方法有逆变换采样、拒绝采样、重参数化技巧 |

### 核心技能（能动手做到）

- [ ] 从零实现 Bernoulli / Categorical / Poisson 的 PMF 和 Uniform / Normal 的 PDF，并能说出各自的均值与方差
- [ ] 实现 `expected_value` / `variance`，算出公平骰子 `E[X] = 3.5`、`Var(X) ≈ 2.9167`
- [ ] 实现 `sample_categorical`（累积分布查找）和 Box-Muller 正态采样，并用经验频率 / 样本均值方差验证
- [ ] 实现数值稳定的 `softmax`、`log_softmax`、`cross_entropy_loss`，对 `[100, 101, 102]` 这类大 logits 不溢出
- [ ] 从联合分布表求边缘分布，并判断两个变量是否独立
- [ ] 用实验验证 CLT：均匀分布样本均值的标准差 ≈ `0.2887/√n`
- [ ] 能在对数空间计算长序列的概率，并知道 float64 / float32 大致在什么时候下溢

---

## 二、基础自测（选择题）

**Q1.** 从一副 52 张的扑克牌中抽一张。已知抽到的是 King，它是人头牌（J、Q、K）的概率为 a；已知抽到的是人头牌，它是 King 的概率为 b。(a, b) 等于：

- A. (1, 1/3)
- B. (1/3, 1)
- C. (1/13, 1/3)
- D. (1/3, 1/3)

**Q2.** 正态分布 `N(μ=0, σ=0.1)` 在 `x = 0` 处的 `normal_pdf` 值约为 3.99。下列说法正确的是：

- A. 这不可能，概率不能超过 1，一定是代码写错了
- B. 这是合法的：PDF 是密度不是概率，`P(X = 0)` 实际上是 0，只有对区间积分才得到概率
- C. 说明 `P(X = 0) = 3.99`
- D. 说明这个分布的积分不等于 1

**Q3.** 根据讲义中的天气-带伞联合分布表：

| | 不带伞 | 带伞 |
|---|---|---|
| 晴天 | 0.40 | 0.10 |
| 雨天 | 0.05 | 0.45 |

`P(带伞 | 雨天)` 等于：

- A. 0.45
- B. 0.55
- C. 0.818
- D. 0.9

**Q4.** 代码中对 `[0,1)` 均匀分布取 n 个样本求平均，重复 10000 次。`n = 30` 时这些平均值的标准差约为 0.0524。若 `n = 120`，标准差约为：

- A. 0.0524（不变）
- B. 0.026
- C. 0.013
- D. 0.0024

**Q5.** 下面哪一组 logits 的 softmax 结果与 `[0, 1, 2]` **完全相同**？

- A. `[0, 2, 4]`
- B. `[-5, -4, -3]`
- C. `[0, 0.5, 1]`
- D. `[2, 1, 0]`

**Q6.** 一个刚初始化的语言模型，词表大小为 50,000，对每个位置都输出近似均匀的分布。此时交叉熵 loss（自然对数）大约是：

- A. 0.693
- B. 4.7
- C. 10.8
- D. 50000

**Q7.** 关于 λ = 3 的泊松分布，下列说法正确的是：

- A. `P(X = 3)` 是唯一的最大概率
- B. 均值和方差都是 3，且 `P(X = 2) = P(X = 3)`
- C. 方差是 9
- D. `P(X = 0) = 0`，因为平均会发生 3 次

**Q8.** 讲义写道：概率连乘"大约 30 项后会下溢"。在 Python 的 float64 中，`0.01 ** n` 要到 n 约为多少时才真正变成 `0.0`？

- A. 约 30
- B. 约 50
- C. 约 162
- D. 永远不会变成 0

---

## 三、动手 / 代码题

**Q9.** 阅读 `sample_categorical`：

```python
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

调用 `sample_categorical([0.33, 0.33, 0.33], 1000)`，返回列表的长度一定是 1000 吗？请找出问题、解释原因，并给出一个更健壮（且更快）的实现。

**Q10.** `poisson_pmf` 的实现是：

```python
def poisson_pmf(k, lam):
    return (lam ** k) * math.exp(-lam) / factorial(k)
```

`poisson_pmf(171, 100.0)` 和 `poisson_pmf(200, 3)` 会发生什么？请改写成在对数空间计算的版本。

**Q11.** 讲义练习 3：一个 5 分类模型输出 logits `[2.0, 0.5, -1.0, 3.0, 0.1]`，正确类别是索引 3。用本节的 `cross_entropy_loss` 计算 loss；如果正确类别是索引 2 呢？两者相差多少，为什么恰好是这个数？最后写出用 PyTorch `nn.CrossEntropyLoss` 验证的代码。

**Q12.** 讲义练习 1：用**逆变换采样**实现指数分布 `Exp(λ)` 的采样器（PDF `λe^{-λx}`，CDF `1 - e^{-λx}`），λ = 2 时采 10000 个样本，验证样本均值、方差，并把直方图密度与真实 PDF 对比。

---

## 四、面试高频题

**Q13.**（基础必考）为什么分类任务的损失函数用交叉熵？它和最大似然估计、负对数似然是什么关系？为什么一般不用 MSE？

**Q14.**（原理深挖）softmax 为什么要先减去最大值？log-softmax 怎么实现才稳定？为什么 PyTorch 的 `CrossEntropyLoss` 要求输入 logits 而不是 softmax 之后的概率？

**Q15.**（工程实践）LLM 生成文本时，temperature、top-k、top-p 分别是怎么作用在输出分布上的？temperature → 0 和 → ∞ 分别会怎样？

**Q16.**（原理深挖）中心极限定理说的是什么？它成立需要什么条件？在机器学习中有哪些具体体现？

**Q17.**（追问型）语言模型评估里常见的 perplexity（困惑度）是什么？它和交叉熵、对数概率有什么关系？一个模型的 perplexity 是 20 意味着什么？

---

## 五、参考答案与解析

### Q1 — 答案：A

- `P(人头牌 | King) = P(King 且 人头牌) / P(King) = (4/52)/(4/52) = 1`：所有 King 都是人头牌。
- `P(King | 人头牌) = (4/52)/(12/52) = 1/3`：这是讲义和代码 `conditional_probability(4/52, 12/52)` 算出的 0.3333。

这道题强调**条件概率不对称**：`P(A|B) ≠ P(B|A)`。二者通过贝叶斯定理联系（下一节内容）。混淆它们是"检察官谬误"等经典错误的根源。

### Q2 — 答案：B

`normal_pdf(0, 0, 0.1) = 1/(0.1·√(2π)) ≈ 3.99`。PDF 是密度（单位长度上的概率），σ 越小曲线越窄越高，峰值可以远大于 1；但曲线下总面积仍是 1。连续变量取任何单点的概率都是 0，概率只能来自区间积分：`P(a ≤ X ≤ b) = ∫ f(x) dx`。讲义原话："f(x) can be greater than 1 (density, not probability)"。

### Q3 — 答案：D

`P(雨天) = 0.05 + 0.45 = 0.5`（边缘分布），`P(带伞 | 雨天) = 0.45 / 0.5 = 0.9`。A 是联合概率 `P(雨天, 带伞)`；B 是边缘概率 `P(带伞)`；C 是反过来的 `P(雨天 | 带伞) = 0.45/0.55 ≈ 0.818`。另外可以验证不独立：`P(晴天, 不带伞) = 0.40`，而 `P(晴天)·P(不带伞) = 0.5 × 0.45 = 0.225`，不相等（代码输出 `Independent? False`）。

### Q4 — 答案：B

均值的标准差是 `σ/√n`。`[0,1)` 均匀分布的 `σ = 1/√12 ≈ 0.2887`，`n = 30` 时 `0.2887/√30 ≈ 0.0527`（与实测 0.0524 吻合）。n 变成 4 倍，标准差缩小为 `1/√4 = 1/2`，约 0.026。C 是误以为按 1/n 缩小（除以 4）；D 是 `σ/n`。"精度提高一倍需要 4 倍样本"是 CLT 最实用的推论之一。

### Q5 — 答案：B

softmax 对**平移不变**：所有 logits 同时加减一个常数 c，分子分母同乘 `e^c`，结果不变。`[-5,-4,-3] = [0,1,2] - 5`。这正是"减最大值"技巧成立的原因，代码中 `softmax([100,101,102])` 输出 `[0.0900, 0.2447, 0.6652]`，与 `softmax([0,1,2])` 相同。A、C 是**缩放**，会改变分布的尖锐程度（相当于改变温度）；D 改变了顺序。

### Q6 — 答案：C

均匀分布时每个 token 的概率是 `1/50000`，交叉熵 `= -ln(1/50000) = ln 50000 ≈ 10.82`。B（4.7）是误用了以 10 为底的对数；A（0.693 = ln 2）是二分类均匀预测的值。工程意义：训练刚开始的 loss 应接近 `ln(类别数)`。如果初始 loss 远高于这个值，通常说明初始化让 logits 过大（模型"自信地猜错"），这是一个很好用的排错检查点。

### Q7 — 答案：B

泊松分布均值 = 方差 = λ = 3。λ 为整数时，`P(X=λ) / P(X=λ-1) = λ/λ = 1`，所以 `P(2) = P(3) ≈ 0.2240`（代码输出两者都是 0.2240），众数有两个，A 错。D 错：`P(X=0) = e⁻³ ≈ 0.0498`，"平均 3 次"不代表不可能 0 次。

### Q8 — 答案：C

实测：`0.01 ** n` 在 n = 162 时变为 `0.0`（n = 161 时还是 `1e-322`，处于次正规数范围）。float64 最小正规数约 `2.2e-308`，次正规数可以低到约 `5e-324`，所以 0.01 连乘大约 154 次后开始损失精度、162 次后归零。代码中 `0.01^50 = 1e-100` 也没有下溢。若用 **float32**（最小次正规数约 `1.4e-45`），实测 23 次就变成 0——讲义"约 30 项"的说法更接近 float32 的情况。

但讲义的核心结论完全正确：真实语言模型的句子动辄成百上千个 token，单个 token 概率常常远小于 0.01，原始概率连乘必然下溢；而对数概率之和（代码中 `50 × ln 0.01 = -230.26`）始终是一个普通的有限数。

### Q9 — 参考答案

**不一定**。实测 `random.seed(0)` 下返回的列表长度是 **995**，有 5 个样本被**静默丢弃**。

原因：`[0.33, 0.33, 0.33]` 的累积和最大只有 0.99。当 `r = random.random()` 落在 `[0.99, 1)` 时，`r <= c` 对所有 c 都不成立，内层循环正常结束、没有 `append`，也没有任何报错。即使概率向量"数学上"和为 1，浮点累加也可能略小于 1（例如对随机 logits 做 softmax 后累加，实测约 3% 的 8 维概率向量累积和为 `0.9999999999999998`），留下极小的丢样本概率。另一个边界问题：若第 0 类概率为 0 而 `r` 恰好为 0.0，`r <= c` 会选中这个零概率类别。

更健壮的实现：

```python
import bisect
import random

def sample_categorical_fixed(probs, n=1):
    cumulative = []
    total = 0.0
    for p in probs:
        total += p
        cumulative.append(total)
    samples = []
    for _ in range(n):
        r = random.random() * total               # 按实际总和缩放，不要求恰好为 1
        i = bisect.bisect_right(cumulative, r)    # 二分查找：O(log k)
        samples.append(min(i, len(probs) - 1))    # 兜底，防浮点边界越界
    return samples
```

实测：`[0.33, 0.33, 0.33]` 返回 1000 个样本，计数 `[329, 336, 335]`；`[0.1, 0.3, 0.4, 0.2]` 采 10 万次的经验频率为 `[0.1, 0.299, 0.4, 0.202]`。

改进点：
1. `r` 乘以 `total`，自动处理未精确归一化的概率；
2. `bisect_right` 找第一个"累积值 > r"的位置，复杂度从 O(k) 降到 O(log k)（词表 5 万时差距明显），同时跳过零概率类别；
3. `min(...)` 兜底，保证一定返回合法下标；
4. 生产中直接用 `random.choices(range(k), weights=probs, k=n)` 或 `np.random.choice` / `torch.multinomial`。

### Q10 — 参考答案

两者都抛 `OverflowError`（已实测）：
- `poisson_pmf(171, 100.0)`：`100.0 ** 171 = 1e342` 超过 float64 上限（约 1.8e308），报 `OverflowError: (34, 'Numerical result out of range')`。
- `poisson_pmf(200, 3)`：`3 ** 200` 是 Python 大整数，没问题；但 `factorial(200) ≈ 7.9e374`，float 除以它时需要把这个整数转成 float，报 `OverflowError: int too large to convert to float`。

可数学上两个概率都是完全正常的数（第一个约 3.0e-11）。修复：在对数空间计算，最后再取指数：

```python
import math

def poisson_pmf_log(k, lam):
    # log P = k·log(λ) - λ - log(k!)，用 lgamma(k+1) = log(k!) 避免算阶乘
    return math.exp(k * math.log(lam) - lam - math.lgamma(k + 1))

print(poisson_pmf_log(171, 100.0))   # 2.9976001681978143e-11
print(poisson_pmf_log(200, 3))       # 1.676790706191975e-281
print(poisson_pmf_log(3, 3))         # 0.22404180765538767（与原实现一致）
```

要点：中间量（`λᵏ`、`k!`）巨大，而结果本身不大——这正是对数空间计算的典型场景。`math.lgamma` 直接给出 `log Γ(k+1) = log k!`，无需构造大整数。注意 `lam = 0` 时 `math.log(0)` 会报错，需单独处理。

### Q11 — 参考答案

```python
from probability import cross_entropy_loss, softmax

logits = [2.0, 0.5, -1.0, 3.0, 0.1]
print(softmax(logits))                 # 约 [0.2415, 0.0539, 0.0120, 0.6565, 0.0361]
print(cross_entropy_loss(logits, 3))   # 0.420881199680712
print(cross_entropy_loss(logits, 2))   # 4.4208811996807125
```

- 目标为 3 时 loss ≈ **0.4209**（= `-ln 0.6565`），模型对正确类别给了最高概率，loss 较小。
- 目标为 2 时 loss ≈ **4.4209**，恰好多了 **4.0**。原因：`log_softmax(z)ᵢ = zᵢ - logsumexp(z)`，两类的 loss 之差只取决于 logits 之差 `z₃ - z₂ = 3.0 - (-1.0) = 4.0`，log-sum-exp 项相互抵消。这也说明：正确类别的 logit 落后其他类别越多，loss 就近似线性地增大，对它的梯度 `q_y - 1` 不会趋于 0——"错得越离谱，纠正的力度越大"，不会出现饱和。

PyTorch 验证（本环境未安装 PyTorch，**未实际运行**，预期输出约 0.4209）：

```python
import torch
import torch.nn as nn

logits = torch.tensor([[2.0, 0.5, -1.0, 3.0, 0.1]])   # 形状 (batch=1, classes=5)
target = torch.tensor([3])                              # 类别下标，形状 (batch,)
loss = nn.CrossEntropyLoss()(logits, target)
print(loss.item())
```

注意 `nn.CrossEntropyLoss` 接收的是**未经 softmax 的 logits** 和**整数类别下标**，内部做的正是 log-softmax + NLL。

### Q12 — 参考答案

思路：若 `U ~ Uniform(0,1)`，则 `X = F⁻¹(U)` 服从 CDF 为 F 的分布。解 `u = 1 - e^{-λx}` 得 `x = -ln(1 - u)/λ`。

```python
import math
import random

def sample_exponential(lam, n=1):
    # 逆变换：F(x) = 1 - e^(-λx)  =>  x = -ln(1 - u) / λ
    return [-math.log(1.0 - random.random()) / lam for _ in range(n)]

def exponential_pdf(x, lam):
    return lam * math.exp(-lam * x) if x >= 0 else 0.0

random.seed(0)
lam = 2.0
xs = sample_exponential(lam, 10000)
mean = sum(xs) / len(xs)
var = sum((x - mean) ** 2 for x in xs) / len(xs)
print(f"sample mean = {mean:.4f} (theory {1/lam:.4f})")
print(f"sample var  = {var:.4f} (theory {1/lam**2:.4f})")

width = 0.25
for b in range(6):
    lo, hi = b * width, (b + 1) * width
    frac = sum(lo <= x < hi for x in xs) / len(xs)
    density = frac / width                       # 直方图高度（密度）
    mid = (lo + hi) / 2
    print(f"[{lo:.2f},{hi:.2f})  hist={density:.3f}  pdf(mid)={exponential_pdf(mid, lam):.3f}")
```

实测输出：

```text
sample mean = 0.4971 (theory 0.5000)
sample var  = 0.2414 (theory 0.2500)
[0.00,0.25)  hist=1.556  pdf(mid)=1.558
[0.25,0.50)  hist=0.968  pdf(mid)=0.945
[0.50,0.75)  hist=0.579  pdf(mid)=0.573
[0.75,1.00)  hist=0.368  pdf(mid)=0.348
[1.00,1.25)  hist=0.208  pdf(mid)=0.211
[1.25,1.50)  hist=0.137  pdf(mid)=0.128
```

要点：
- 用 `1 - random.random()` 而不是 `random.random()`：`random.random()` 的取值范围是 `[0, 1)`，可能恰好返回 0；`1 - u` 落在 `(0, 1]`，`log` 永远不会遇到 0。（本节代码的 Box-Muller 直接写 `math.log(u1)`，理论上就存在这个极小概率的 `ValueError`。）
- 直方图要除以组宽才是**密度**，才能和 PDF 比较；`frac` 本身是概率。
- 第一个格子 PDF 取值 1.558 > 1，再次说明密度可以大于 1。

### Q13 — 参考回答要点

- **定义**：交叉熵 `H(p, q) = -Σ pᵢ log qᵢ`。分类时真实分布 p 是 one-hot（正确类别为 1），所以 `H = -log q_y`——只看模型给正确类别的概率。
- **与最大似然的关系**：数据集似然 `Π q(yᵢ|xᵢ)`，取对数再取负得到 `-Σ log q(yᵢ|xᵢ)`，即负对数似然（NLL）。所以**最小化平均交叉熵 = 最大化似然**。进一步，`H(p,q) = H(p) + KL(p‖q)`，而 `H(p)` 与模型无关，所以也等价于最小化 KL 散度。
- **为什么不用 MSE**：
  1. 梯度：softmax + 交叉熵对 logits 的梯度是 `q - p`，简洁且不会饱和；sigmoid/softmax + MSE 的梯度中含有 `q(1-q)` 这样的因子，模型"自信地错了"（q 接近 0 或 1）时梯度反而很小，学得很慢。
  2. 概率含义：交叉熵对"给正确类别很低概率"施加对数级的重罚（`-log 0.01 ≈ 4.6`），符合概率建模的直觉；MSE 的惩罚有上界。
  3. 对 logistic 回归，交叉熵损失关于参数是凸的，MSE 则不是。
- **加分点**：提到 label smoothing 是把 one-hot 的 p 换成"软"分布；初始 loss ≈ `ln K` 可以用来检查初始化（Q6）。

### Q14 — 参考回答要点

- **为什么减最大值**：`e^{1000}` 在 float64 中直接溢出（实测 `math.exp(1000.0)` 报 `OverflowError`，NumPy/PyTorch 中则得到 `inf`，进而出现 `inf/inf = nan`）。由于平移不变性（Q5），减去 `m = max(z)` 后结果不变，而最大的指数变成 `e⁰ = 1`，其余都在 (0, 1] 之间，分母至少为 1，不会溢出也不会除以 0。
- **稳定的 log-softmax**：`log softmax(z)ᵢ = zᵢ - logsumexp(z)`，其中 `logsumexp(z) = m + log Σ e^{zⱼ - m}`。代码中的 `log_softmax` 正是这样实现的。实测 `log_softmax([1000.0, 0.0])` 得到 `[0.0, -1000.0]`，完全精确；如果先算 softmax 再取 log，第二项的概率 `e^{-1000}` 下溢为 0，`log(0)` 得 `-inf`。
- **为什么 `CrossEntropyLoss` 收 logits**：它内部把 log-softmax 和 NLL 融合计算，全程在对数空间进行，数值稳定；梯度也可以直接写成 `softmax(z) - onehot(y)`。如果用户先 softmax 再传入，就等于做了两次 softmax，结果错误且梯度变小。
- **常见误区**：在模型最后一层加了 `nn.Softmax` 又用 `nn.CrossEntropyLoss`；或者自己写 `torch.log(torch.softmax(z))` 导致 `-inf`/`nan`。正确做法是用 `F.log_softmax` + `F.nll_loss`，或直接 `F.cross_entropy`。

### Q15 — 参考回答要点

- **基础**：模型输出 logits `z`，经 softmax 得到下一个 token 的 Categorical 分布，再从中采样（讲义："Language models sample the next token from the predicted distribution"）。
- **temperature T**：采样前把 logits 除以 T，即 `softmax(z / T)`。
  - `T < 1`：分布更尖锐，更保守、更确定；`T → 0` 退化为 **greedy**（总选概率最大的 token）。
  - `T > 1`：分布更平坦，更多样也更容易胡言乱语；`T → ∞` 趋向均匀分布。
  - 这和 Q5 中"缩放 logits 会改变分布尖锐程度"是同一回事（本节代码可视化中 `[2,1,0]` vs `[10,1,0]` 也展示了这一点）。
- **top-k**：只保留概率最大的 k 个 token，其余置零后重新归一化再采样。
- **top-p（nucleus）**：按概率从大到小排序，保留累积概率刚好达到 p 的最小集合，再归一化采样。候选集大小随分布形状自适应：模型很确定时只剩一两个候选，不确定时候选更多。
- **实现上**就是本节的 `sample_categorical`：在截断/重归一化后的概率上做累积分布查找。
- **工程实践**：代码生成、事实问答常用低温或 greedy；创意写作用较高温度配合 top-p。几种方法可以组合使用（常见顺序是先温度缩放，再 top-k/top-p 截断），具体顺序以所用推理框架的实现为准。

### Q16 — 参考回答要点

- **内容**：设 X₁…Xₙ **独立同分布**，均值 μ、方差 σ² **有限**，则样本均值 `X̄ₙ` 标准化后 `√n(X̄ₙ - μ)/σ` 依分布收敛到标准正态。通俗说：均值近似服从 `N(μ, σ²/n)`，不管原始分布长什么样。
- **条件**：独立（或弱相关）、同分布（有更一般的版本）、**方差有限**。讲义说"适用于任何初始分布"是简化说法——方差无穷的分布（如柯西分布）的样本均值不会收敛到正态。
- **与大数定律的区别**：大数定律说均值收敛到 μ（"收敛到哪"）；CLT 进一步描述了均值在 μ 附近的波动形状和大小（"怎么波动"，标准差 `σ/√n`）。
- **ML 中的体现**：
  1. mini-batch 梯度是样本梯度的平均，其噪声标准差约按 `1/√B` 缩小——batch 扩大 4 倍，梯度噪声减半；这也是"线性缩放学习率"等经验法则讨论的背景。
  2. 评估指标的置信区间：在 n 个测试样本上测得准确率 p，标准误约为 `√(p(1-p)/n)`；1000 条样本、准确率 80% 时标准误约 1.3 个百分点，两个模型差 0.5% 可能只是噪声。
  3. A/B 测试的显著性检验。
  4. 讲义提到的：测量误差近似正态、权重初始化常用正态分布。
- **加分点**：本节代码的 CLT 实验数据（n = 1/2/5/30 时标准差 0.287/0.204/0.129/0.052）正好符合 `0.2887/√n`。

### Q17 — 参考回答要点

- **定义**：对一段 N 个 token 的文本，`PPL = exp(-(1/N) Σ log q(xᵢ | x<ᵢ))`，即**平均交叉熵（以 e 为底）的指数**。
- **关系**：交叉熵 / NLL 是平均每个 token 的"惊讶程度"（单位为 nat）；perplexity 把它换算回"等效的候选数"。全部在对数空间累加，正是本节"对数概率防下溢"的应用——直接把几千个 token 的概率相乘必然下溢。
- **直观含义**：PPL = 20 表示模型平均而言就像在 20 个等可能的候选里猜下一个 token。均匀猜测时 PPL 等于词表大小（50,000 词表下初始 loss ≈ 10.82，PPL ≈ 50,000，见 Q6）。
- **注意事项**：
  1. 只有**同一个 tokenizer**、同一份评测数据时 PPL 才可比——分词粒度不同，每个 token 的平均信息量不同。
  2. PPL 低不等于下游任务表现好，它只衡量语言建模的拟合程度。
  3. 训练日志里的 loss 一般就是平均 NLL，`exp(loss)` 即 PPL。
- **加分点**：能说出以 2 为底时对应"bits per token / bits per byte"，以及 `loss` 每下降 0.1，PPL 约下降 10%（`e^{-0.1} ≈ 0.905`）。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 04 机器学习微积分](../../04-calculus-for-ml/docs/zh.md)：积分 = 曲线下面积，期望、PDF 归一化都依赖它。
- 高中概率：古典概型、排列组合（代码中的 `factorial`、`combinations`）。

### 本节被哪些后续内容用到
- [阶段 01 · 07 贝叶斯定理](../../07-bayes-theorem/docs/zh.md)：在条件概率基础上推导 `P(A|B)` 与 `P(B|A)` 的关系（Q1）。
- [阶段 01 · 09 信息论](../../09-information-theory/docs/zh.md)：熵、交叉熵、KL 散度的系统讲解。
- [阶段 01 · 13 数值稳定性](../../13-numerical-stability/docs/zh.md)：溢出、下溢与 log-sum-exp 技巧。
- [阶段 01 · 15 机器学习统计](../../15-statistics-for-ml/docs/zh.md)：置信区间、假设检验、A/B 测试，以及 CLT 的实际应用（Q16）。
- [阶段 01 · 16 Sampling 方法](../../16-sampling-methods/docs/zh.md)：逆变换采样、拒绝采样、MCMC。
- [阶段 02 · 14 朴素贝叶斯](../../../02-ml-fundamentals/14-naive-bayes/docs/zh.md)：条件独立假设 + 对数概率求和。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：交叉熵与 MSE 的选择。
- [阶段 08 · 02 自编码器与 VAE](../../../08-generative-ai/02-autoencoders-vae/docs/zh.md)：连续潜变量分布与重参数化技巧。
- [阶段 10 · 10 评估](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：perplexity 等语言模型评估指标。

### 延伸关键词
`log-sum-exp` · `NLL` · `KL 散度` · `label smoothing` · `temperature / top-k / top-p` · `逆变换采样` · `Box-Muller` · `次正规数（subnormal）` · `perplexity` · `大数定律`
