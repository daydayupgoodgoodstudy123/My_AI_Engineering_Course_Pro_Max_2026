# 代码讲解 · statistics.py

> **所属小节**：阶段 01 · 数学基础 · 第 15 节 机器学习统计 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 statistics.py`（无命令行参数，约 1 秒跑完全部演示） ｜ **依赖**：仅 Python 标准库（`math`、`random`），不用 NumPy / SciPy

---

## 1. 这份代码在考察什么

讲义的口号是"统计学告诉你模型是真的好，还是只是运气好"。这份代码只用 `math` 和 `random`，把一个"模型评估统计工具箱"从零搭起来：

1. **描述统计**：均值、中位数、众数、样本方差、线性插值百分位、IQR——知道数据长什么样。
2. **相关与协方差**：Pearson（线性）、Spearman（单调，含并列秩处理）、协方差矩阵。
3. **假设检验的完整链路**：从 t 统计量、Welch 自由度，到**亲手用不完全 Beta / Gamma 函数算出 p 值**，而不是调用 `scipy.stats`。
4. **不依赖分布假设的方法**：bootstrap 置信区间与模型对比。
5. **用模拟理解统计概念**：A/B 测试模拟器、多重比较、统计显著 vs 实际显著、功效分析——让"第一类错误""功效"这些抽象概念变成可数的频率。

> 一句话：**每一个 p 值都能追溯到一行行可读的 Python**，这样你在面试或评审实验报告时，才能说清楚这个数是怎么来的、什么时候不可信。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `mean` / `median` / `mode` / `variance` / `std_dev` / `percentile` / `iqr` | 函数 | 描述统计 | 集中趋势、离散程度、贝塞尔校正 |
| `covariance` / `pearson_correlation` / `rank_data` / `spearman_correlation` / `covariance_matrix` | 函数 | 两变量关系 | 协方差、线性相关、秩相关 |
| `t_statistic_one_sample` / `t_statistic_two_sample` / `welch_df` | 函数 | 计算 t 统计量与自由度 | 单样本 / Welch t 检验 |
| `t_cdf_approx` + `_regularized_beta` + `_beta_continued_fraction` + `_log_beta_function` | 数值函数 | t 分布的 CDF | 正则化不完全 Beta 函数 |
| `p_value_two_sided` / `one_sample_ttest` / `two_sample_ttest` / `paired_ttest` | 函数 | 返回 `{t, df, p}` 字典 | 三种 t 检验 |
| `chi_squared_test` + `chi_squared_p_value` + `_gamma_series` / `_gamma_continued_fraction` | 函数 | 卡方检验及其 p 值 | 正则化不完全 Gamma 函数 |
| `bootstrap_statistic` / `bootstrap_compare` | 函数 | 重采样置信区间 / 两组差值 CI | Bootstrap |
| `cohens_d` / `interpret_cohens_d` / `bonferroni_correction` | 函数 | 效应量与多重比较校正 | 实际显著性、FWER |
| `generate_normal` | 函数 | Box-Muller 生成正态样本 | 采样 |
| `ab_test_simulator` / `run_multiple_ab_tests` / `statistical_vs_practical_significance` | 模拟函数 | 把上面的工具组合成实验 | 第一/二类错误、功效 |
| `if __name__ == "__main__":` | 演示入口 | 11 段演示（含功效模拟） | — |

调用关系呈"金字塔"：底层是 `mean`/`variance`/`percentile`；中层是各种统计量和数值积分函数；顶层的检验函数（`two_sample_ttest` 等）把"统计量 + 自由度 + p 值"打包成字典；最上层的模拟器再反复调用检验函数。

---

## 3. 逐段精讲

> 文件较大（约 22KB），下面聚焦最核心的部分；数值积分只讲思路，不逐行推导。

### 3.1 描述统计：方差的 `sample` 开关与线性插值百分位

```python
def variance(data, sample=True):
    n = len(data)
    m = mean(data)
    total = sum((x - m) ** 2 for x in data)
    if sample and n > 1:
        return total / (n - 1)
    return total / n
```

- 默认 `sample=True`，除以 `n − 1`（**贝塞尔校正**）：样本均值是"离样本最近的点"，用它算出的偏差平方和系统性偏小，除以 `n − 1` 正好把期望补回总体方差。
- `n > 1` 的守卫：只有一个样本时 `n − 1 = 0`，退化成除以 `n`，返回 0 而不是崩溃。

```python
def percentile(data, p):
    s = sorted(data)
    n = len(s)
    k = (p / 100) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)
```

- 把第 p 百分位映射到"下标" `k = p/100 × (n − 1)`；k 是整数就直接取值，否则在相邻两个元素间**线性插值**，权重是到两侧的距离。这与 NumPy `np.percentile` 默认的 `linear` 方法一致。
- 例：本文件的 15 个数据，P25 的 `k = 3.5`，取第 3、4 个元素 23 和 31 的平均 → 27.00。
- 百分位的定义有十几种约定（Excel、R、NumPy 各不相同），小样本时结果会有差别——对比不同工具的 P99 时要先确认约定。

```python
def mode(data):
    counts = {}
    for x in data:
        counts[x] = counts.get(x, 0) + 1
    max_count = max(counts.values())
    modes = [k for k, v in counts.items() if v == max_count]
    modes.sort()
    return modes[0]
```

- 字典计数 → 找最大次数 → 收集所有并列众数 → 返回最小的一个。
- ⚠️ 演示数据中 15 个值互不相同，每个都"出现 1 次"，于是 `Mode: 12` 只是最小值，没有统计意义。讲义也说了：众数对连续数据"rarely informative"。

### 3.2 相关：Pearson 的分母约定与 Spearman 的并列秩

```python
def pearson_correlation(x, y):
    n = len(x)
    mx = mean(x)
    my = mean(y)
    sx = std_dev(x, sample=False)
    sy = std_dev(y, sample=False)
    if sx == 0 or sy == 0:
        return 0.0
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / n
    return cov / (sx * sy)
```

- 协方差除以 `n`，标准差也用**总体**版本（`sample=False`），分子分母口径一致，`n` 与 `n − 1` 的选择会被约掉——r 的值与用样本口径算出的完全相同。这对应讲义公式 `r = Σ(xᵢ−x̄)(yᵢ−ȳ) / (n·s_x·s_y)`。
- 常数序列（标准差为 0）时相关系数无定义，这里约定返回 `0.0`。

```python
def rank_data(data):
    indexed = sorted(enumerate(data), key=lambda pair: pair[1])
    ranks = [0.0] * len(data)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) - 1 and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks
```

- `enumerate` 保留原始下标，按值排序后，就知道"排第 i 名的是原来的第几个元素"。
- 内层 `while` 找出一段**值相同**的区间 `[i, j]`，给它们统一赋平均秩 `(i + j)/2 + 1`（`+1` 把 0 起始的下标转为 1 起始的名次）。例：`[10, 20, 20, 30] → [1.0, 2.5, 2.5, 4.0]`。
- `spearman_correlation` 就是"对秩做 Pearson"，一行搞定——这正是讲义的定义。

### 3.3 协方差矩阵：注意数据的摆放方向

```python
def covariance_matrix(data):
    d = len(data)
    n = len(data[0])
    means = [mean(data[i]) for i in range(d)]
    matrix = [[0.0] * d for _ in range(d)]
    for i in range(d):
        for j in range(i, d):
            cov = sum(
                (data[i][k] - means[i]) * (data[j][k] - means[j])
                for k in range(n)
            ) / (n - 1)
            matrix[i][j] = cov
            matrix[j][i] = cov
    return matrix
```

- 这里的 `data` 是"**每个元素是一个特征的全部样本**"（d 行 × n 列），调用方式是 `covariance_matrix([feature1, feature2, feature3])`。上一节 `distances.py` 的 `compute_covariance` 正好相反（每行是一个样本）。NumPy 的 `np.cov` 默认也是"每行一个变量"（`rowvar=True`）——这是最常见的维度错误来源之一。
- `j` 从 `i` 开始，只算上三角再镜像到下三角，利用**对称性**省一半计算。
- 除以 `n − 1`，是无偏的样本协方差。

### 3.4 t 统计量与 Welch 自由度

```python
def t_statistic_two_sample(data1, data2):
    # ...
    v1 = variance(data1, sample=True)
    v2 = variance(data2, sample=True)
    se = math.sqrt(v1 / n1 + v2 / n2)
    if se == 0:
        return 0.0
    return (m1 - m2) / se


def welch_df(data1, data2):
    # ...
    num = (v1 / n1 + v2 / n2) ** 2
    denom = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
    if denom == 0:
        return n1 + n2 - 2
    return num / denom
```

- 分母 `√(s₁²/n₁ + s₂²/n₂)` 是均值差的标准误，**不假设两组方差相等**——这就是 Welch t 检验，讲义建议"默认就用 Welch"。
- 自由度用 Welch–Satterthwaite 公式，结果通常不是整数（例如 17.74），这也是后面 t 分布 CDF 要支持非整数自由度的原因。
- 符号约定：`t = (m1 − m2)/se`，即"第一组减第二组"。演示中 B 更好时 t 为负，读结果时要注意。

### 3.5 从 t 值到 p 值：正则化不完全 Beta 函数

```python
def t_cdf_approx(t_val, df):
    x = df / (df + t_val * t_val)
    if t_val < 0:
        return 0.5 * _regularized_beta(x, df / 2, 0.5)
    return 1.0 - 0.5 * _regularized_beta(x, df / 2, 0.5)


def p_value_two_sided(t_val, df):
    p_left = t_cdf_approx(abs(t_val), df)
    return 2.0 * (1.0 - p_left)
```

- 数学事实：自由度为 ν 的 t 分布，尾部概率 `P(T > |t|) = ½ · I_x(ν/2, ½)`，其中 `x = ν/(ν + t²)`，`I_x(a, b)` 是**正则化不完全 Beta 函数**。所以只要能算 `I_x`，就能算任意 t 的 p 值。
- 双侧 p 值 = 2 × 单侧尾部概率。
- `_regularized_beta` 用**连分式**（continued fraction）求 `I_x`，并在 `x` 较大时利用对称性 `I_x(a,b) = 1 − I_{1−x}(b,a)` 换到收敛快的一侧——这是《Numerical Recipes》中的经典做法。`_beta_continued_fraction` 里的 `tiny = 1e-300` 是为了防止除以 0（Lentz 算法的标准技巧）。
- `_log_beta_function` 用 `math.lgamma`（Gamma 函数的对数）计算 `log B(a,b)`，再 `exp`：直接算 Gamma 函数在参数稍大时就会溢出，**在对数空间计算**是数值稳定性的通用套路（第 13 节）。
- 名字叫 `approx`，但精度其实很高：用 SciPy 对照，几组 t 值的 p 值误差都在 1e-10 量级以内。
- ⚠️ `_beta_function` 定义了但没有被调用，是遗留的辅助函数。

### 3.6 三种 t 检验：配对检验 = 差值的单样本检验

```python
def one_sample_ttest(data, mu_0=0):
    n = len(data)
    t = t_statistic_one_sample(data, mu_0)
    df = n - 1
    p = p_value_two_sided(t, df)
    return {"t_statistic": t, "df": df, "p_value": p}


def paired_ttest(data1, data2):
    diffs = [a - b for a, b in zip(data1, data2)]
    return one_sample_ttest(diffs, mu_0=0)
```

- `paired_ttest` 只有两行：先求每对的差，再检验"差值的均值是否为 0"。这正是讲义写的做法，也说明了配对检验为什么强大——折与折之间的难度差异在求差时被抵消了。
- 返回字典而不是元组，调用方用 `result["p_value"]` 取值，可读性好、不怕顺序记错。
- ⚠️ `t_statistic_one_sample` 没有处理标准差为 0 的情况：`paired_ttest([1,2,3],[2,3,4])` 的差值全是 −1，会抛 `ZeroDivisionError`（双样本版本则有 `se == 0` 的保护）。

### 3.7 卡方检验：正则化不完全 Gamma 函数

```python
def chi_squared_test(observed, expected):
    chi2 = sum(
        (o - e) ** 2 / e for o, e in zip(observed, expected) if e > 0
    )
    df = len(observed) - 1
    p = chi_squared_p_value(chi2, df)
    return {"chi2": chi2, "df": df, "p_value": p}


def chi_squared_p_value(chi2, df):
    if chi2 <= 0:
        return 1.0
    return 1.0 - _lower_incomplete_gamma_ratio(df / 2.0, chi2 / 2.0)
```

- 统计量就是讲义公式 `Σ(O − E)²/E`，生成器表达式里的 `if e > 0` 跳过期望为 0 的格子，避免除零。
- 自由度 = 类别数 − 1（**拟合优度检验**；列联表的独立性检验自由度是 `(行−1)(列−1)`，本代码没有实现）。
- 卡方分布 CDF = 正则化下不完全 Gamma 函数 `P(df/2, χ²/2)`，p 值 = `1 − P`。`_lower_incomplete_gamma_ratio` 在 `x < a + 1` 时用级数展开（收敛快），否则用连分式——同样是"根据参数区间选收敛快的算法"。
- 讲义示例 `χ² = 8, df = 1` 用这套函数算出 p ≈ 0.0047，与讲义"p < 0.005"一致。

### 3.8 Bootstrap：置信区间与两组比较

```python
def bootstrap_statistic(data, stat_func, n_bootstrap=5000, ci=95):
    n = len(data)
    bootstrap_stats = []
    for _ in range(n_bootstrap):
        sample = [data[random.randint(0, n - 1)] for _ in range(n)]
        bootstrap_stats.append(stat_func(sample))
    bootstrap_stats.sort()
    lower_pct = (100 - ci) / 2
    upper_pct = 100 - lower_pct
    ci_lower = percentile(bootstrap_stats, lower_pct)
    ci_upper = percentile(bootstrap_stats, upper_pct)
    return {
        "estimate": stat_func(data),
        # ...
        "std_error": std_dev(bootstrap_stats, sample=True),
    }
```

- `stat_func` 是参数——传 `mean` 就是均值的 CI，传 `median` 就是中位数的 CI，**任何统计量都行**，这正是 bootstrap 的威力。
- `random.randint(0, n - 1)`（两端都包含）随机挑下标，一共挑 n 次 = **有放回抽样**。
- **百分位法**：95% CI 取 bootstrap 分布的 2.5% 和 97.5% 分位数；bootstrap 统计量的标准差就是标准误（SE）的估计。
- `bootstrap_stats.sort()` 之后 `percentile` 内部又排序一次，是无害的冗余。

```python
def bootstrap_compare(data1, data2, stat_func, n_bootstrap=5000, ci=95):
    # ...
    for _ in range(n_bootstrap):
        s1 = [data1[random.randint(0, n1 - 1)] for _ in range(n1)]
        s2 = [data2[random.randint(0, n2 - 1)] for _ in range(n2)]
        diffs.append(stat_func(s2) - stat_func(s1))
    # ...
    significant = ci_lower > 0 or ci_upper < 0
```

- 判定规则：差值的 CI 不包含 0 即为显著。
- ⚠️ 两组是**各自独立**重采样的，适合两组独立样本（如 A/B 测试的两组用户）。讲义"Bootstrap for model comparison"描述的却是**配对**做法（重采样测试集下标，在同一批样本上同时算 A、B 的指标）。如果用这个函数比较"两个模型在同一测试集上的逐样本得分"，会丢掉配对信息、CI 偏宽。配对版本的写法见测验 Q10。

### 3.9 效应量、多重比较与 Box-Muller

```python
def cohens_d(data1, data2):
    # ...
    pooled = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    if pooled == 0:
        return 0.0
    return (m1 - m2) / pooled
```

- 合并标准差是两组方差按自由度加权平均后开方；`interpret_cohens_d` 用 0.2 / 0.5 / 0.8 三个阈值给出 negligible / small / medium / large。
- `bonferroni_correction` 很直接：阈值 `α/m`，逐个比较。

```python
def generate_normal(n, mu=0, sigma=1):
    samples = []
    for _ in range(n // 2 + 1):
        u1 = random.random()
        u2 = random.random()
        while u1 == 0:
            u1 = random.random()
        z0 = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
        z1 = math.sqrt(-2 * math.log(u1)) * math.sin(2 * math.pi * u2)
        samples.append(mu + sigma * z0)
        samples.append(mu + sigma * z1)
    return samples[:n]
```

- **Box-Muller 变换**：两个独立均匀随机数 → 两个独立标准正态数，再通过 `μ + σz` 平移缩放。下一节"采样方法"会系统讲这类"把均匀分布变成目标分布"的技巧。
- `while u1 == 0` 防止 `log(0)`；每轮产生 2 个样本，所以循环 `n // 2 + 1` 次后用 `[:n]` 截取。
- 其实标准库已有 `random.gauss`，这里自己写是为了展示原理（文件中相关性演示部分用的仍是 `random.gauss`）。

### 3.10 模拟器：把概念变成频率

`ab_test_simulator` 生成两组正态数据，同时跑 Welch t 检验、Cohen's d 和 bootstrap 比较；`run_multiple_ab_tests` 在"真实效应为 0"时重复 20 次检验，数一数有几次假阳性，再做 Bonferroni 校正；主程序最后的功效模拟重复 200 次实验，统计"检测到真实效应"的比例：

```python
    for _ in range(n_sims):
        a = generate_normal(50, 50, 10)
        b = generate_normal(50, 53, 10)
        res = two_sample_ttest(a, b)
        if res["p_value"] < 0.05:
            detected += 1
```

- 这就是**功效的定义**：真实效应存在时，检验能拒绝 H0 的概率。模拟出 0.32 和 0.84，与理论值（约 0.32、0.85）吻合。
- ⚠️ 文件开头的 `random.seed(42)` 在**模块导入时**执行一次，之后所有演示共享同一个随机流——改动前面任何一个演示的抽样次数，后面所有结果都会变。
- ⚠️ `statistical_vs_practical_significance` 的小样本组在这个种子下得到 `p = 0.0279`、`d = −0.58`、"Significant: True"，与"小样本不显著、大样本才显著"的预期叙事不符。这其实是一次假阳性，也是"小样本中显著结果会夸大效应量"的活例子（测验 Q12）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用 `math` + `random`，自己算 p 值 | 看清 p 值从哪来，不把检验当黑盒 | 生产用 `scipy.stats.ttest_ind/ttest_rel/chisquare/bootstrap` |
| 检验函数返回字典 | 字段自描述，便于扩展 | 正式库常返回带命名字段的结果对象 |
| 默认 Welch t 检验 | 不假设等方差，更稳健 | 方差确实相等时功效略低 |
| 用连分式 / 级数 + `lgamma` 计算特殊函数 | 数值稳定、精度高 | 实现复杂；生产直接用 `scipy.special.betainc/gammainc` |
| `variance` 用 `sample` 开关 | 一个函数同时支持总体/样本口径 | 调用方必须清楚自己要哪个；NumPy 的 `np.var` 默认是总体口径（`ddof=0`），与此相反 |
| 百分位法 bootstrap、独立重采样 | 最简单、最好懂 | 偏态时覆盖率不准（可用 BCa）；同一测试集上比较模型应配对重采样 |
| 模块级固定随机种子 | 结果可复现 | 演示之间相互耦合；更好的做法是每个实验用独立的 `random.Random(seed)` 实例 |
| 文件名 `statistics.py` | 与主题同名，直观 | 与标准库 `statistics` 模块重名，同目录下 `import statistics` 会导入这个文件 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 整除与取余 | `mid = n // 2`、`n % 2 == 0` | `//` 向下取整除法；`%` 取余，用来判断奇偶 |
| 默认参数 | `def variance(data, sample=True)`、`max_iter=300, tol=1e-15` | 不传时使用默认值 |
| 关键字参数调用 | `std_dev(x, sample=False)`、`one_sample_ttest(diffs, mu_0=0)` | 按名字传参，清晰且不怕顺序错 |
| 字典计数 | `counts[x] = counts.get(x, 0) + 1` | 键不存在时 `get` 返回默认值 0 |
| 字典遍历 | `[k for k, v in counts.items() if v == max_count]` | `items()` 同时取键和值，配合带条件的推导式 |
| 带条件的生成器表达式 | `sum((o - e) ** 2 / e for o, e in zip(...) if e > 0)` | 只对满足条件的元素求和 |
| `sum(1 for ...)` 计数 | `sum(1 for r in corrected if r["significant"])` | 数一数有多少个元素满足条件 |
| `sorted` + `enumerate` + `lambda` | `sorted(enumerate(data), key=lambda pair: pair[1])` | 按值排序，同时保留原下标 |
| `while` 循环 | `rank_data` 中的双层 `while`、`while u1 == 0:` | 循环次数事先不确定时使用 |
| `math` 函数 | `math.floor`、`math.ceil`、`math.lgamma`、`math.exp`、`math.log` | 取整、对数 Gamma、指数、自然对数 |
| 科学计数法字面量 | `tiny = 1e-300`、`tol=1e-15` | `1e-300` 表示 10⁻³⁰⁰ |
| 下划线前缀函数 | `_regularized_beta`、`_gamma_series` | 约定为"内部函数"，不建议外部直接调用（并非强制） |
| `for _ in range(...)` | `for _ in range(n_bootstrap)` | 循环变量用不到时用 `_` |
| 返回字典、嵌套取值 | `return {"t_statistic": t, ...}`、`result['small_sample']['p_value']` | 用字典组织多个返回值 |
| 条件表达式 | `significant_count / n_tests if true_effect == 0 else None` | 一行 if/else；`None` 表示"不适用" |
| 函数作为参数 | `bootstrap_statistic(data, mean)`、`stat_func(sample)` | 把函数当成普通值传递 |
| 切片 | `samples[:n]` | 取前 n 个 |
| f-string 格式符 | `f"{mean(data):.2f}"`、`f"[{row[0]:7.3f} ...]"`、`f"{0.05/20:.4f}"` | `.2f` 两位小数；`7.3f` 宽度 7、三位小数；大括号里可以放表达式 |
| 字符串运算 | `print("\n" + "=" * 60)` | `*` 重复字符串、`+` 拼接 |
| 模块级代码 | 文件开头的 `random.seed(42)` | 导入或运行文件时立即执行 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行演示 |

---

## 6. 运行结果解读

已在临时目录实际运行（Python 3.13，耗时约 0.9 秒）。关键输出与解读：

```text
Mean:     45.00
Median:   43.00
Mode:     12              ← 所有值都只出现一次，返回的只是最小值
Std Dev:  22.68
P25:      27.00           ← (23 + 31) / 2，线性插值
P75:      60.00           ← (56 + 64) / 2
IQR:      33.00
Skewed data: [1, ..., 9, 1000]
Mean:   104.50  (pulled by outlier)
Median: 5.50  (robust to outlier)
```

```text
Quadratic relationship (y = x^2):
  Pearson:  0.9746        ← 不是直线
  Spearman: 1.0000        ← 严格单调
No relationship (random):
  Pearson:  -0.0399       ← 10 个随机点，接近 0 但不为 0
```

```text
3-feature covariance matrix:
  [  0.878    0.947    0.213]
  [  0.947    1.253    0.260]   ← f2 = f1 + 噪声(0.5)，理论 Var(f2)=1.25，Cov(f1,f2)=Var(f1)
  [  0.213    0.260    1.278]   ← f3 与 f1 独立，理论协方差为 0；这里的 0.21 来自 100 个样本的抽样波动
```

```text
ONE-SAMPLE T-TEST   t = 2.3911, df = 49, p = 0.0207   ← 真实均值 52 ≠ 50，被检测到
TWO-SAMPLE T-TEST   t = -2.4599, p = 0.0169, Cohen's d = -0.6351 (medium)
PAIRED T-TEST       Mean diff 0.0220, t = -16.5000, p = 0.0000   ← t 为负是因为内部用 a − b
CHI-SQUARED         chi2 = 8.5000, df = 3, p = 0.0367
```

配对检验的 t 高达 16.5：10 折中 B 每折都比 A 高 0.02～0.03，差值几乎没有波动。如果误用独立的 Welch 检验，t 只有约 −2.69（测验 Q9）。

```text
Bootstrap mean:   100.51  95% CI: [96.63, 104.29]  SE: 1.94   ← 理论 SE = 15/√50 ≈ 2.12
Bootstrap median: 98.96  95% CI: [94.68, 105.33]  SE: 2.51   ← 中位数比均值更"抖"
Bootstrap model comparison:  Diff 0.0378  95% CI [0.0220, 0.0538]  Significant: True
```

```text
Test 1: No real effect      p = 0.4710  Significant: False  Cohen's d = 0.0722 (negligible)
Test 2: Real effect = 5     p = 0.0000  Significant: True   Cohen's d = -0.5601 (medium)
```

注意 Test 2 的 `Observed diff: 5.73` 是 `B − A`，而 Cohen's d 是 `A − B`，所以符号相反。

```text
Tests significant (uncorrected): 1/20     ← 恰好等于期望值 20 × 0.05 = 1
Tests significant (Bonferroni):  0/20
Small sample (n=30):     p = 0.0279  d = -0.5823 (medium)      Significant: True   ← 假阳性 + 效应夸大
Large sample (n=100000): p = 0.0019  d = -0.0139 (negligible)  Significant: True   ← 显著但可忽略
Power (n=50, effect=3, std=10):  0.32
Power (n=200, effect=3, std=10): 0.84
```

最后两组是本节最重要的结论：**p 值依赖样本量，效应量不依赖**；样本少时功效低，即使碰巧显著，效应量也不可信。

---

## 7. 动手改一改

1. 给 `t_statistic_one_sample` 加上 `s == 0` 的保护，使 `paired_ttest([1,2,3],[2,3,4])` 不再崩溃，并思考此时 p 值应该返回什么。
2. 实现 `paired_bootstrap_compare`（重采样同一组下标），在两个模型共享样本难度的模拟数据上，与 `bootstrap_compare` 比较 CI 宽度。
3. 把 `run_multiple_ab_tests` 的 `n_tests` 改成 1000，统计未校正的假阳性率是否接近 0.05；再实现 Holm-Bonferroni 校正并对比。
4. 修改功效模拟，画出（或打印）n = 20, 50, 100, 200, 400 时的功效曲线，并与公式 `n ≈ 2(1.96 + 0.84)²σ²/Δ² ≈ 175` 对照。
5. 实现 Wilcoxon 符号秩检验的统计量（对差值的绝对值排秩，可复用 `rank_data`），并验证 n = 5 时双侧精确 p 值最小为 0.0625。
6. 把模块级的 `random.seed(42)` 改为每个演示使用独立的 `random.Random(seed)` 实例，让各演示的结果互不影响。

---

## 8. 常见坑

- **文件名遮蔽标准库**：本文件叫 `statistics.py`，在同一目录下写 `import statistics` 会导入它而不是标准库的 `statistics` 模块，报出莫名其妙的 `AttributeError`。
- **总体 vs 样本方差口径**：本文件 `variance` 默认是样本口径（`n − 1`），NumPy 的 `np.var` 默认是总体口径（`ddof=0`），pandas 的 `.var()` 默认又是样本口径，混用时数字对不上。
- **符号约定不统一**：`observed_diff` 是 `B − A`，而 t 统计量和 Cohen's d 是 `A − B`，报告方向时容易写反。
- **配对数据用了独立检验**：同一测试集 / 同一批 CV 折上的两个模型必须用配对方法，否则功效大幅下降。
- **把 bootstrap 当成"造数据"**：重采样不会增加信息，小样本或有偏样本的 bootstrap CI 同样不可靠。
- **只看 p 值**：大样本中 d = 0.014 也能 p < 0.01；小样本中显著的结果往往夸大效应。永远同时报告效应量和置信区间。
