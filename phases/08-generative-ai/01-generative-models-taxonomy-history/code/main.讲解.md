# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 01 节 生成模型——分类法和历史 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy

---

## 1. 这份代码在考察什么

本节讲义讲的是"五个桶"的分类法，代码则用一个能在一屏里打印完的一维玩具问题，把其中最根本的一条分界线——**显式密度 vs 隐式密度**——变成你能亲眼看到的数字：

1. **生成模型的出发点**：我们手里只有从 `p_data(x)` 采出来的样本（这里是 2000 个两峰高斯混合样本），并不知道 `p_data` 本身。
2. **显式密度**：直方图和高斯 KDE（kernel density estimation，核密度估计）都能回答"`x = 0` 这个点的密度是多少"，还能积分成"落在某区间的概率"。
3. **隐式密度**：一个"从训练集随机挑一个样本再加点噪声"的生成器，能源源不断地产出新样本，却**永远回答不了** `p(x)`——这正是 GAN 的处境。
4. **估计器的偏差与方差**：同一批样本，直方图和 KDE 给出不同的数（0.025 vs 0.033），带宽/窗口宽度直接决定估计质量。
5. **数值积分**：用梯形法把密度变成概率，顺便体会"密度可以大于 1，但积分必须是 1"。

> 一句话：**能算 `p(x)` 的是显式模型，只能吐样本的是隐式模型**——之后每一节（VAE、GAN、扩散、flow matching）都要先问这个问题。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sample_mixture(n, rng)` | 函数 | 从 0.4·N(-2, 0.6²) + 0.6·N(2, 0.9²) 采 n 个样本 | 真实数据分布 `p_data`（这里我们"作弊"知道它） |
| `histogram_density(samples, x, bin_width)` | 函数 | 以 x 为中心开窗计数，返回密度 | 显式密度（最朴素的非参数估计） |
| `kde_density(samples, x, bandwidth)` | 函数 | 每个样本放一个高斯核，求平均 | 显式密度（平滑的非参数估计） |
| `implicit_generator(samples, k, rng)` | 函数 | 随机挑训练样本 + N(0, 0.1²) 噪声 | 隐式密度 / "GAN 式"生成器 |
| `integrate_density(density_fn, samples, lo, hi, steps)` | 函数 | 梯形法数值积分 | 密度 → 区间概率 |
| `ascii_histogram(samples, ...)` | 函数 | 打印字符画直方图 | 无需画图库的可视化 |
| `main()` | 演示入口 | 依次调用以上函数并打印结果 | — |

数据流：`sample_mixture` 产出 2000 个样本 → 同一批样本分别喂给两个**密度估计器**（能求值、能积分）和一个**生成器**（只能出新样本）→ 打印对比。

---

## 3. 逐段精讲

### 3.1 `sample_mixture`：真实分布（上帝视角）

```python
def sample_mixture(n, rng):
    """Two-mode Gaussian mixture. Mode A at -2 (sigma 0.6), mode B at +2 (sigma 0.9)."""
    samples = []
    for _ in range(n):
        if rng.random() < 0.4:
            samples.append(rng.gauss(-2.0, 0.6))
        else:
            samples.append(rng.gauss(2.0, 0.9))
    return samples
```

- 这是**祖先采样（ancestral sampling）**：先按 0.4 / 0.6 的概率抽"属于哪个峰"（隐变量），再从对应的高斯里抽值。这个"先抽隐变量、再生成数据"的两步结构，就是 VAE、GAN 里"先抽 `z` 再解码"的最简版本。
- `rng` 是外部传入的 `random.Random(42)` 实例，而不是直接用全局 `random`。好处：①可复现；②不同函数共享同一个随机流，结果确定；③不会被别的代码偷偷改种子。
- 现实中我们**不知道**这个函数——生成模型的全部任务，就是只看它吐出的样本，去近似它。
- ⚠️ 两峰的方差不同（0.6 vs 0.9）且权重不同（0.4 vs 0.6），是刻意设计的不对称，让后面的直方图和 KDE 结果有区别可看。

### 3.2 `histogram_density`：以查询点为中心的"直方图"

```python
def histogram_density(samples, x, bin_width=0.25):
    """Explicit density via histogram. Returns p(x) as (count in bin) / (n * bin_width)."""
    n = len(samples)
    lo, hi = x - bin_width / 2, x + bin_width / 2
    count = sum(1 for s in samples if lo <= s < hi)
    return count / (n * bin_width)
```

- 公式：`p̂(x) = (落在窗口里的样本数) / (n · 窗口宽)`。除以 `n` 得到概率，再除以宽度得到**密度**（单位长度上的概率）。所以它可以大于 1。
- 注意这里的窗口**以 `x` 为中心**，不是固定网格。严格说它是"矩形核（boxcar kernel）的 KDE"，也叫滑动窗口估计：结果随 `x` 连续移动，不依赖网格起点。
- `lo <= s < hi` 半开半闭区间，保证样本恰好落在边界上时不会被相邻两个窗口重复计数。
- 复杂度：每次查询 `O(n)`，因为没有预先建索引。⚠️ 生产中会先排序再二分查找（`bisect`），把单次查询降到 `O(log n)`。

### 3.3 `kde_density`：给每个样本放一个高斯"小土堆"

```python
def kde_density(samples, x, bandwidth=0.3):
    """Approximate density via Gaussian kernel density estimate."""
    n = len(samples)
    total = 0.0
    for s in samples:
        u = (x - s) / bandwidth
        total += math.exp(-0.5 * u * u) / math.sqrt(2 * math.pi)
    return total / (n * bandwidth)
```

- 公式：`p̂(x) = (1/(n·h)) Σᵢ K((x - sᵢ)/h)`，其中 `K(u) = exp(-u²/2)/√(2π)` 是标准正态密度，`h` 就是 `bandwidth`。
- 为什么除以 `n·h`：每个核 `K((x-s)/h)/h` 是均值 `s`、标准差 `h` 的正态密度，积分为 1；`n` 个取平均，整体积分仍为 1。少除一个 `h` 是最常见的 KDE bug。
- 与直方图的区别：直方图是"硬"的计数（在窗内算 1，窗外算 0），KDE 是"软"的加权（离得越近权重越大），所以曲线平滑、没有锯齿。
- **带宽是偏差-方差旋钮**：`h` 越大越平滑（偏差大），越小越尖锐（方差大）。实测 `x=0` 处：`h=0.05 → 0.0222`，`h=0.3 → 0.0258`，`h=1.0 → 0.0879`，真实值约 0.0235。
- 讲义把 KDE 称为"approximate density"，可以和桶 2（VAE / 扩散的"近似显式密度"）类比：都是能求值、但不是精确真值的密度。⚠️ 严格说，KDE 是非参数估计，与 ELBO 下界不是同一种"近似"，类比只为帮助记忆。

### 3.4 `implicit_generator`：只能出样本的"GAN 式"生成器

```python
def implicit_generator(samples, k, rng):
    """Implicit generator: sample a training point and add tiny noise. No p(x)."""
    out = []
    for _ in range(k):
        base = rng.choice(samples)
        out.append(base + rng.gauss(0.0, 0.1))
    return out
```

- 每次从训练集随机挑一个点，再加 σ=0.1 的高斯噪声。输出分布看起来和训练数据很像（两个峰都在），但函数**没有任何接口**能告诉你某个 `x` 有多可能。这就是讲义里说的"Only a sampler — no way to evaluate `p(x)` of a given point"。
- 一个有意思的细节：从数学上看，这个生成器的输出分布其实就是"带宽 0.1 的 KDE"。也就是说，**同一个分布，可以被显式地写成密度，也可以只被隐式地实现为采样过程**——显式/隐式说的是模型**暴露了什么接口**，而不是分布本身。
- ⚠️ 这是一个"记忆训练集"的生成器：样本只是训练点的轻微扰动。真实 GAN 也可能出现类似的 memorization（记忆/复制训练样本），这是评估生成模型时必须检查的问题。

### 3.5 `integrate_density`：梯形法把密度变成概率

```python
def integrate_density(density_fn, samples, lo, hi, steps=200):
    """Trapezoid-rule integration of a density over [lo, hi]."""
    xs = [lo + (hi - lo) * i / steps for i in range(steps + 1)]
    total = 0.0
    for i in range(steps):
        a, b = xs[i], xs[i + 1]
        total += 0.5 * (density_fn(samples, a) + density_fn(samples, b)) * (b - a)
    return total
```

- 把 `[lo, hi]` 均分成 200 段，每段用梯形面积 `(f(a) + f(b))/2 · (b - a)` 近似，求和。
- `density_fn` 作为参数传入——函数是 Python 的"一等公民"，同一个积分器可以给 `histogram_density` 和 `kde_density` 复用。这就是**高阶函数**的典型用法。
- `xs` 用 `lo + (hi - lo) * i / steps` 生成，而不是反复 `x += h` 累加，避免浮点误差逐步累积。
- ⚠️ 性能：每段调用两次 `density_fn`，相邻段的端点被重复计算，共 400 次调用、每次 `O(n)`，合计约 80 万次 `exp`。先算好 201 个网格点再求和可以减半（见"动手改一改"）。

### 3.6 `ascii_histogram`：没有 matplotlib 也能看分布

```python
def ascii_histogram(samples, lo=-5.0, hi=5.0, bins=40, height=12):
    width = (hi - lo) / bins
    counts = [0] * bins
    for s in samples:
        if lo <= s < hi:
            counts[int((s - lo) / width)] += 1
    peak = max(counts) or 1
    rows = []
    for row in range(height, 0, -1):
        threshold = peak * row / height
        line = "".join("#" if c >= threshold else " " for c in counts)
        rows.append(line)
    # ...
```

- 这里才是**固定网格**的直方图：`int((s - lo) / width)` 把样本映射到 0–39 号格子。
- 画法是"从上往下逐行扫描"：第 `row` 行的阈值是 `peak · row / height`，计数达到阈值的格子打 `#`。最高的格子在顶行就有 `#`，矮的格子只在底部几行有。
- `max(counts) or 1`：如果所有计数都是 0，`max` 返回 0，`or 1` 把它换成 1，防止后面除以 0 的情况（这里是乘法，但阈值全为 0 会让所有格子都打 `#`）。这是 Python 里很常见的"给假值一个默认值"的惯用法。
- ⚠️ 落在 `[lo, hi)` 之外的样本被静默丢弃；坐标轴标签那一行也只是粗略对齐。

### 3.7 `main`：把三种方法摆在一起对比

```python
def main():
    rng = random.Random(42)
    samples = sample_mixture(2000, rng)
    # ...
    query = 0.0
    print(f"  histogram density: {histogram_density(samples, query):.4f}")
    print(f"  kernel density:    {kde_density(samples, query):.4f}")
    print(f"  implicit generator: N/A (only samples, no density)")
    # ...
    new_samples = implicit_generator(samples, 10, rng)
    print("  " + ", ".join(f"{s:+.2f}" for s in new_samples))
```

- 查询点选 `x = 0`，恰好是两峰之间的低谷——这是密度估计最容易出错的地方，最能体现两种估计器的差异。
- 隐式生成器那一行直接打印 `N/A`，这就是本节的核心结论"写在代码里"。
- `implicit_generator` 用的是**同一个** `rng`，所以它的输出依赖于前面采样消耗了多少随机数；改动前面的代码会改变这 10 个数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一维两峰混合 | 一屏能打印完，真实密度可以手算，便于对比 | 真实数据是百万维，直方图/KDE 完全失效（维度灾难），才需要神经网络生成模型 |
| 纯 Python、不用 NumPy / SciPy | 每一步都看得见 | 慢；生产中用 `scipy.stats.gaussian_kde` 或 `sklearn.neighbors.KernelDensity` |
| 以查询点为中心的窗口 | 结果不依赖网格起点，代码只有 4 行 | 每次查询 `O(n)`；可以排序 + 二分加速 |
| 固定带宽 0.3、窗口 0.25 | 演示用，简单 | 生产中用 Scott / Silverman 规则或交叉验证选带宽 |
| 显式传入 `rng` | 可复现、互不干扰 | 无明显代价，是推荐做法 |
| "复制 + 加噪"的生成器 | 最简单的隐式采样器 | 本质是记忆训练集；真实 GAN 用神经网络 `G(z)` 学一个映射 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `for _ in range(n)` | `sample_mixture` 里的循环 | `_` 表示"这个循环变量我不用" |
| 元组解包赋值 | `lo, hi = x - bin_width / 2, x + bin_width / 2`；`a, b = xs[i], xs[i + 1]` | 一行给多个变量赋值 |
| 链式比较 | `lo <= s < hi` | 等价于 `lo <= s and s < hi`，Python 特有的简洁写法 |
| 生成器表达式 | `sum(1 for s in samples if lo <= s < hi)` | 边遍历边计数，不建中间列表 |
| 列表推导式 | `[lo + (hi - lo) * i / steps for i in range(steps + 1)]` | 一行生成网格点列表 |
| 列表乘法初始化 | `counts = [0] * bins` | 生成 40 个 0；⚠️ 只对不可变元素安全，`[[]] * n` 会共享同一个子列表 |
| `or` 提供默认值 | `peak = max(counts) or 1` | 左边为假值（0、空串、None）时取右边 |
| `str.join` | `"".join("#" if c >= threshold else " " for c in counts)` | 把字符序列拼接成一个字符串，比 `+=` 拼接快 |
| 条件表达式 | `"#" if c >= threshold else " "` | 三元运算，一行写 if/else |
| 函数作为参数 | `integrate_density(kde_density, samples, -0.5, 0.5)` | 高阶函数：把函数当值传递 |
| 默认参数 | `def kde_density(samples, x, bandwidth=0.3)` | 调用时可省略，也可用关键字覆盖 |
| 独立随机数生成器 | `rng = random.Random(42)`；`rng.gauss(...)`、`rng.choice(...)` | 有自己状态的随机数实例，固定种子可复现 |
| f-string 格式符 | `f"{p_hist:.3f}"`、`f"{s:+.2f}"`、`f"{lo:<.1f}"`、`f"{hi:>.1f}"` | `.3f` 三位小数；`+` 总是显示正负号；`<`/`>` 左/右对齐 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 0.2 秒）的完整输出：

```text
=== 2000 samples from a two-mode Gaussian mixture ===
                          #             
                          ####          
           ##             ####          
           ##             #####         
          ###             ######        
         ######         ########        
         ######         ########        
         ######        ##########       
        ########       ###########      
        ########      ############      
        #########     #############     
       ##########  # ###############    
----------------------------------------
-5.0                                5.0

evaluate p(x=0.0) three ways:
  histogram density: 0.0180
  kernel density:    0.0258
  implicit generator: N/A (only samples, no density)

integrate p(x in [-0.5, 0.5]):
  histogram: 0.025
  kde:       0.033

10 new samples from the implicit (GAN-ish) generator:
  -1.32, -2.43, -2.75, +1.48, +2.31, +2.07, +1.22, -2.74, -2.48, +3.57

takeaway: explicit density (buckets 1-2 in the doc) lets you answer
'how likely is this point?'. implicit (bucket 3) does not.
```

逐段解读：

- **字符画**：左边一个窄而矮的峰（中心 -2、σ=0.6、权重 0.4），右边一个宽而高的峰（中心 +2、σ=0.9、权重 0.6）。中间低谷几乎为空——这就是一维版的"数据集中在流形上"。
- **`p(x=0)`**：真实密度约 0.0235。直方图 0.0180（窗口宽只有 0.25，只数到 9 个样本，方差大）；KDE 0.0258（带宽 0.3 的平滑把两侧峰的质量拉进低谷，略偏高）。
- **区间概率**：真实值约 0.0295；样本中实际落在区间内的比例正好是 0.025，滑动窗口直方图的积分几乎精确复现了这个比例；KDE 给出 0.033，同样是平滑带来的正偏差。
- **10 个新样本**：有正有负、集中在 ±2 附近，看上去"像"真数据——但你无法问它"+3.57 这个值有多可能"。
- ⚠️ **讲义与实际输出不一致**：讲义 "Build It" 一节写的示例输出是 `p(x in [-0.5, 0.5]) ≈ 0.38 / 0.41`、"20 new samples"，而代码实际打印 0.025 / 0.033 和 10 个样本，输出格式也不同。按这个混合分布手算，区间概率只有约 0.03，0.38 不可能出现；以实际运行结果为准。

---

## 7. 动手改一改

1. **带宽扫描**：对 `bandwidth in [0.05, 0.1, 0.3, 0.6, 1.0]` 分别打印 `kde_density(samples, 0.0, h)` 和 `kde_density(samples, 2.0, h)`，观察低谷被高估、峰顶被低估的趋势（偏差-方差权衡）。
2. **积分提速**：把 `integrate_density` 改成先算 `steps + 1` 个网格点的密度、再套梯形公式，确认结果不变而调用次数从 400 降到 201。
3. **检查归一化**：用 `integrate_density(kde_density, samples, -8, 8)` 验证 KDE 的积分约等于 1；然后故意把 `kde_density` 的分母改成 `n`（漏掉 `bandwidth`），看积分变成多少。
4. **给隐式生成器做"评估"**：写 `two_sample_stats(a, b)`，比较生成样本与新采真样本的均值、标准差、负值比例（理论值约 0.4 / 2.11 / 0.4）。体会"隐式模型只能用样本对样本来评估"——FID 就是这种思路的高维版。
5. **加速直方图查询**：先 `sorted_samples = sorted(samples)`，再用 `bisect.bisect_left` / `bisect_right` 数窗口内样本，把单次查询从 `O(n)` 降到 `O(log n)`。
6. **进阶**：把 `implicit_generator` 的噪声从 0.1 逐步调到 1.0，用第 4 题的统计量观察输出分布何时开始"跑偏"（标准差明显变大、低谷被填平）。

---

## 8. 常见坑

- **把密度当概率**：`histogram_density` 返回 2.0 并不是 bug，密度乘以区间宽度才是概率。
- **KDE 忘了除以带宽**：分母必须是 `n · h`，否则积分不为 1。
- **直方图的边界**：用 `<=` 和 `<` 组成半开区间，否则边界上的样本会被重复计数或漏数。
- **共享随机数流**：`implicit_generator` 与 `sample_mixture` 共用 `rng`，在中间插入任何调用 `rng` 的代码都会改变后续所有"随机"结果。
- **把一维直觉搬到高维**：直方图 / KDE 在一维很好用，但在图像这种几十万维的空间里会彻底失效——这正是需要 VAE、GAN、扩散等神经生成模型的原因。
- **相信讲义里的示例输出**：本节讲义的示例数字与代码实际输出不符，复现时以真实运行为准。
