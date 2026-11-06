# 代码讲解 · time_series.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 15 节 时间序列基础知识 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python time_series.py`（无命令行参数，依次运行 7 个演示） ｜ **依赖**：仅 `numpy`（不需要 statsmodels / sklearn）

---

## 1. 这份代码在考察什么

1. **平稳性**：用"滚动统计 + 前后两半对比"粗略判断序列是否平稳，并验证一阶差分能去掉线性趋势。
2. **自相关**：手写 ACF，从尖峰的位置读出季节周期，用 `±1.96/√n` 判断显著性。
3. **滞后特征**：把一维序列变成 `(X, y)` 监督学习问题，这是"用普通 ML 模型做时间序列"的桥梁。
4. **Walk-forward 验证**：训练集永远在测试集之前，并且和随机切分做定量对比，看清"随机切分有多乐观"。
5. **AR 模型与多步预测**：AR(p) 就是在滞后特征上做线性回归；递归预测时误差会逐步累积。

> 一句话：**时间序列的核心不在模型，而在"时间顺序"**——特征只能用过去，评估只能向前走。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `make_synthetic_series` | 函数 | 线性趋势 + 周期 30 的正弦 + 噪声 | 趋势 + 季节性 + 残差 |
| `make_seasonal_series` | 函数 | 弱趋势 + 周期 7 和周期 30 两个正弦 + 噪声 | 多重季节性 |
| `difference` | 函数 | 做 `order` 次差分 | 差分去趋势 |
| `check_stationarity` | 函数 | 滚动均值/标准差 + "前后两半"启发式判断 | 平稳性检验 |
| `autocorrelation` | 函数 | 计算 0..max_lag 的 ACF | 自相关 |
| `make_lag_features` | 函数 | 生成滞后特征矩阵与对齐的目标 | 序列 → 监督学习 |
| `walk_forward_split` | 生成器 | 产出 expanding window 的 (训练切片, 测试切片) | Walk-forward 验证 |
| `SimpleAR` | 类 | `lstsq` 拟合的 AR(p)，支持递归多步预测 | 自回归 |
| `mse` / `mae` / `mape` | 函数 | 回归误差指标 | 评估 |
| `demo_*`（7 个） | 演示 | 平稳性、ACF、滞后特征、walk-forward、随机 vs walk-forward、滞后数对比、多步预测 | 讲义各小节 |

数据流：造序列 → `make_lag_features` 得到 `(X, y)` → `walk_forward_split(len(X))` 产生切片 → 每折新建 `SimpleAR` 并 `fit / predict` → 计算 MSE/MAE。多步预测则直接在原始序列上调用 `forecast`。

---

## 3. 逐段精讲

### 3.1 造数据：把"趋势 + 季节 + 噪声"写成公式

```python
def make_synthetic_series(n=500, seed=42):
    rng = np.random.RandomState(seed)
    t = np.arange(n, dtype=float)

    trend = 0.05 * t
    seasonality = 10 * np.sin(2 * np.pi * t / 30)
    noise = rng.normal(0, 2, n)
    series = 50 + trend + seasonality + noise

    return series
```

- 这就是讲义"时间序列 = 趋势 + 季节性 + 残差"的加法模型：基线 50、每步上涨 0.05、振幅 10 / 周期 30 的正弦（类比"月度季节性"）、标准差 2 的高斯噪声。
- `make_seasonal_series` 同理，但叠加了周期 7（振幅 5）和周期 30（振幅 3）两个正弦，用来演示 ACF 在 lag 7、14 处的尖峰。
- 因为生成过程完全已知，你可以对照输出判断每个函数是否"答对了"。

### 3.2 `difference`：差分一次，长度少一

```python
def difference(series, order=1):
    result = series.copy()
    for _ in range(order):
        result = result[1:] - result[:-1]
    return result
```

- `result[1:] - result[:-1]` 是向量化的 `y[t] − y[t−1]`：两个错开一位的切片相减。每差分一次长度减 1。
- 线性趋势 `0.05·t` 差分后变成常数 0.05，于是均值不再漂移；正弦差分后仍是同周期的正弦（振幅变化），噪声差分后方差翻倍。
- ⚠️ 没有提供逆变换。如果在差分序列上建模，预测出来的是"变化量"，要用最后一个真实值加上预测变化量的累加和（`last + np.cumsum(pred_diff)`）才能还原到原尺度。

### 3.3 `check_stationarity`：滚动统计 + 一个经验规则

```python
    for i in range(n):
        start = max(0, i - window + 1)
        segment = series[start:i + 1]
        rolling_mean[i] = segment.mean()
        rolling_std[i] = segment.std() if len(segment) > 1 else 0.0

    first_half_mean = series[:n // 2].mean()
    second_half_mean = series[n // 2:].mean()
    first_half_var = series[:n // 2].var()
    second_half_var = series[n // 2:].var()

    mean_shift = abs(first_half_mean - second_half_mean)
    var_ratio = max(first_half_var, second_half_var) / max(min(first_half_var, second_half_var), 1e-10)

    is_stationary = mean_shift < 0.5 * series.std() and var_ratio < 2.0
```

- **滚动窗口**是"截至第 i 个点（含）的最近 `window` 个点"，开头不足 `window` 个点时用已有的点。注意它**包含当前点 i**——用作平稳性检查没问题，但如果拿去当预测特征就会泄漏目标（测验 Q11 实测：MSE 直接降到 1e−25）。
- **判定规则**：前后两半的均值差小于整体标准差的一半，**并且**方差比小于 2。实测原始序列的均值差约 7.8，超过阈值 4.16，判为非平稳；一阶差分后均值差只有 0.02，判为平稳。
- `max(min(...), 1e-10)` 防止方差为 0 时除零。
- ⚠️ 这是很粗糙的经验法则，不是统计检验。我用 200 条长度为 300 的随机游走测试，有 16 条（8%）被误判为"平稳"——随机游走前后两半的均值碰巧接近时就会漏判。正式场景要用 ADF / KPSS 检验（讲义提到了 ADF，但代码没有实现）。
- ⚠️ 函数算出的 `rolling_mean` / `rolling_std` 在所有演示里都被 `_` 丢弃，只用了 `is_stationary`；另外双重循环的复杂度是 O(n·window)，长序列可以用累加和或卷积向量化。

### 3.4 `autocorrelation`：序列和"错开 k 步的自己"的相关

```python
def autocorrelation(series, max_lag=20):
    n = len(series)
    mean = series.mean()
    var = series.var()
    acf = np.zeros(max_lag + 1)

    for k in range(max_lag + 1):
        if k >= n:
            break
        cov = np.mean((series[:n - k] - mean) * (series[k:] - mean)) if k < n else 0
        acf[k] = cov / var if var > 0 else 0.0

    return acf
```

- `series[:n-k]` 与 `series[k:]` 是错开 k 步的两段等长序列，逐元素相乘再取平均，就是滞后 k 的自协方差；除以方差得到相关系数，lag 0 恒为 1。
- 均值用的是**整体均值**，而不是两段各自的均值，这是 ACF 的标准做法。
- ⚠️ 细节差异：这里的 `np.mean` 除以的是 `n − k`，而教科书和 statsmodels 的标准估计量除以 `n`。所以这里的结果比标准值大 `n/(n−k)` 倍：在 `demo_autocorrelation` 中，lag 7 是 0.6765 vs 标准值 0.6635，lag 30 的差异约 9%。除以 `n` 的版本是有偏的，但能保证整个 ACF 序列是半正定的，在滞后较大时也更稳定。
- `if k < n else 0` 在 `break` 之后已经多余，是无害的冗余代码。

`demo_autocorrelation` 中的显著性阈值 `1.96 / np.sqrt(len(diff_series))` 来自"白噪声的样本 ACF 近似服从 `N(0, 1/n)`"，95% 区间就是 `±1.96/√n`。

### 3.5 `make_lag_features`：时间序列 → 监督学习

```python
def make_lag_features(series, n_lags):
    n = len(series)
    X = np.full((n, n_lags), np.nan)

    for lag in range(1, n_lags + 1):
        X[lag:, lag - 1] = series[:-lag]

    valid_mask = ~np.isnan(X).any(axis=1)
    X_valid = X[valid_mask]
    y_valid = series[valid_mask]

    return X_valid, y_valid
```

- 先用 NaN 填满 `(n, n_lags)` 的矩阵。第 `lag − 1` 列从第 `lag` 行开始填入 `series[:-lag]`，即 `X[t, lag−1] = series[t − lag]`。
- **列顺序：第 0 列是 lag 1（最近），最后一列是 lag p（最远）**。与讲义表格 `lag_2 | lag_1` 的顺序相反，这一点在 `forecast` 中很关键。
- 前 `n_lags` 行至少有一个 NaN，被 `valid_mask` 去掉；目标 `y_valid = series[valid_mask]` 就是 `series[n_lags:]`。
- **目标对齐**：第 t 行的特征全部来自 `t−1 … t−p`，目标是 `series[t]`，严格满足"特征只用过去"。这是整个文件里防止泄漏最关键的一个函数。
- 在**整条序列**上一次性构造滞后特征、之后再切分是安全的，因为每一行只往回看，不会往前看。
- 用 NaN + 掩码的写法比手写下标更不容易出现差一位（off-by-one）的错误。

### 3.6 `walk_forward_split`：只向前走的交叉验证

```python
def walk_forward_split(n_samples, n_splits=5, min_train=50):
    if n_samples <= min_train:
        return

    step = max(1, (n_samples - min_train) // n_splits)

    for i in range(n_splits):
        train_end = min_train + i * step
        test_start = train_end
        test_end = min(train_end + step, n_samples)

        if test_start >= n_samples:
            break

        yield slice(0, train_end), slice(test_start, test_end)
```

- 这是一个**生成器**：每次 `yield` 一对 `slice` 对象，调用方用 `X[train_sl]` 取数据。数据不足时直接 `return`，生成器什么也不产出（讲义版本用的是 `assert`）。
- 训练集总是 `[0, train_end)`，每折增加 `step` 个样本——**expanding window**；测试集紧接其后、长度为 `step`。
- 以 `demo_walk_forward` 为例：`len(X) = 390`、`min_train = 100`，`step = 290 // 5 = 58`，训练集大小依次为 100、158、216、274、332，每折测试 58 个样本——与输出完全一致。
- ⚠️ 整除会丢掉余数：最后 `(n_samples − min_train) % n_splits` 个样本永远不会被测试（测验 Q9）。这些恰恰是最新的数据。
- ⚠️ 没有 gap 参数；如果目标是"未来 k 步的累计值"，训练末尾和测试开头之间需要留出间隔。

### 3.7 `SimpleAR`：AR 模型就是滞后特征上的线性回归

```python
    def fit(self, X, y):
        X_b = np.column_stack([np.ones(len(X)), X])
        theta = np.linalg.lstsq(X_b, y, rcond=None)[0]
        self.bias = theta[0]
        self.weights = theta[1:]
        return self

    def predict(self, X):
        return X @ self.weights + self.bias
```

- 在特征左边拼一列 1，把偏置并入参数向量，`lstsq` 求解最小二乘 `min ‖X_b·θ − y‖²`，`[0]` 取出解（`lstsq` 还会返回残差、秩、奇异值）。
- 讲义片段的注释写的是 "Solve via normal equations"，实际上 `np.linalg.lstsq` 基于 SVD 求解，不会显式构造 `XᵀX`，数值上比正规方程更稳定——这和阶段 01 学过的"不要显式求逆"是同一个道理。
- 与讲义片段不同，实际代码的 `fit` 接收 `(X, y)`，另外提供 `fit_series(series)` 在内部调用 `make_lag_features`。这样同一个模型既能用在 walk-forward 的切片上，也能直接吃一条序列。

```python
    def forecast(self, last_values, n_steps):
        if len(last_values) < self.n_lags:
            raise ValueError(
                f"Need at least {self.n_lags} history points, got {len(last_values)}"
            )
        history = list(last_values[-self.n_lags:])
        predictions = []

        for _ in range(n_steps):
            features = np.array(history[-self.n_lags:][::-1]).reshape(1, -1)
            pred = self.predict(features)[0]
            predictions.append(pred)
            history.append(pred)

        return np.array(predictions)
```

- 这就是讲义的**递归（iterated）多步预测**：每预测一步，就把预测值 `append` 进 `history`，下一步把它当作 lag 1 使用。
- `[::-1]` 把"旧→新"的历史反转成"新→旧"，与训练时第 0 列是 lag 1 的顺序一致。去掉它不会报错，但第 1 步预测会从 71.44 变成 58.54，20 步 MSE 从 54.6 变成 116.3（测验 Q10）。
- `reshape(1, -1)` 把一维的 p 个值变成形状 `(1, p)` 的单个样本，`predict` 返回长度为 1 的数组，所以取 `[0]`。
- 只保留最近 `n_lags` 个值开始，循环里每次也只取最后 `n_lags` 个，`history` 虽然一直变长，但特征长度不变。

### 3.8 三个指标

```python
def mape(y_true, y_pred):
    mask = y_true != 0
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
```

- MSE 对大误差惩罚更重；MAE 和原始数据同单位、好解释；MAPE 与量纲无关，便于跨序列比较。
- `mask = y_true != 0` 跳过真值为 0 的点，避免除零——对应讲义 "undefined when true values are zero"。⚠️ 代价是这些点被悄悄忽略了；真值接近 0（但不为 0）时 MAPE 仍会爆炸。

### 3.9 几个演示的关键点

```python
    rng = np.random.RandomState(42)
    idx = rng.permutation(len(X))
    split = int(len(X) * 0.8)
    train_idx, test_idx = idx[:split], idx[split:]
```

- `demo_random_vs_walk_forward` 中，随机切分版本在**同一个滞后特征矩阵**上做了随机置换，然后与 walk-forward 的平均 MSE 比较，最后用 `if random_mse < wf_mse` 打印对应的结论。两者唯一的区别就是"测试样本是否在时间上晚于训练样本"。
- `demo_lag_comparison` 中 `min_train=max(60, n_lags + 20)` 保证训练样本数明显多于参数个数（对这里所有的 `n_lags` 它都等于 60）；不同 `n_lags` 下 `len(X) = 365 − n_lags`，各折的边界略有不同，比较时要记住这一点。
- `demo_forecasting` 只用前 250 个点训练，然后递归预测 20 步，与真实值逐步对比——展示误差如何随步数增长。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用合成序列 | 生成过程已知，便于验证每一步是否正确 | 真实序列有节假日、断点、缺失值，需要额外处理 |
| 平稳性用经验规则 | 无需 statsmodels，直观易懂 | 会误判（约 8% 的随机游走被判为平稳）；生产用 ADF / KPSS |
| 滞后矩阵用 NaN + 掩码 | 写法简单，不易出错 | 内存多占一倍；pandas 中用 `shift()` 更常见 |
| walk-forward 写成生成器、产出 `slice` | 惰性产生，直接用于 NumPy 切片 | 丢掉了余数样本；没有 gap；sklearn 有 `TimeSeriesSplit` |
| AR 用 `lstsq` 而不是正规方程 | 数值稳定 | 没有正则化；滞后多、样本少时可以换成 Ridge |
| 递归多步预测 | 只需要一个模型 | 误差累积；长周期可用直接策略或多输出 |
| `mape` 跳过 0 | 避免除零 | 静默丢样本；可改用 WAPE 或 MASE |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `for _ in range(n)` | `for _ in range(order):` | 用 `_` 表示"循环变量用不到" |
| 负索引与切片 | `result[1:] - result[:-1]`、`series[:-lag]`、`last_values[-self.n_lags:]` | 错开一位相减；取末尾若干个元素 |
| 步长为 −1 的切片 | `history[-self.n_lags:][::-1]` | 反转列表 |
| 整除 `//` | `n // 2`、`(n_samples - min_train) // n_splits` | 向下取整的除法 |
| 条件表达式 | `segment.std() if len(segment) > 1 else 0.0` | 一行的 if/else |
| 生成器 `yield` 与空 `return` | `yield slice(0, train_end), slice(test_start, test_end)`；`if n_samples <= min_train: return` | 惰性地逐个产出结果；`return` 结束生成器 |
| `slice` 对象 | `X[train_sl]`，其中 `train_sl = slice(0, train_end)` | 等价于 `X[0:train_end]`，可以作为变量传递 |
| `enumerate` + 元组解包 | `for fold, (train_sl, test_sl) in enumerate(walk_forward_split(...))` | 内层括号把生成器产出的二元组拆开 |
| `np.full` 与 NaN 掩码 | `np.full((n, n_lags), np.nan)`、`~np.isnan(X).any(axis=1)` | 用 NaN 占位，再用 `~`（按位取反）选出完整的行 |
| `np.column_stack` | `np.column_stack([np.ones(len(X)), X])` | 在左边拼一列 1 作为偏置项 |
| `np.linalg.lstsq` | `np.linalg.lstsq(X_b, y, rcond=None)[0]` | 最小二乘解；`rcond=None` 使用新版默认的截断阈值 |
| `reshape(1, -1)` | `np.array(...).reshape(1, -1)` | `-1` 让 NumPy 自动推断该维长度 |
| 列表 `append` | `history.append(pred)` | 在列表末尾追加元素 |
| `raise` + f-string | `raise ValueError(f"Need at least {self.n_lags} history points, got ...")` | 带上下文信息的异常 |
| 字符串乘法 | `"#" * int(abs(acf[k]) * 30)`、`'-' * 48` | 画文本条形图和分隔线 |
| f-string 格式符 | `f"{w:+.4f}"`、`f"{error:>+10.2f}"`、`f"{fold+1:>6}"` | `+` 强制显示正负号；`>10` 右对齐占 10 宽 |
| `str.join` + 生成器 | `", ".join(f"{v:.1f}" for v in X[i, :5])` | 拼接格式化后的数字 |

---

## 6. 运行结果解读

实际运行（约 0.2 秒），关键输出如下：

```text
STATIONARITY CHECK
Original series (trend + seasonality):  Mean: 57.46, Std: 8.33   Stationary: False
After first differencing:               Mean: 0.0439, Std: 3.25  Stationary: True

AUTOCORRELATION ANALYSIS
    1   0.2701  ***
    3  -0.5681  ***
    4  -0.6365  ***       ← 半个周期（3.5 天）处是负相关的谷底
    7   0.6765  ***       ← 一个完整周期：峰值
   10  -0.6381  ***
   14   0.6720  ***       ← 两个周期：峰值
Significance threshold (95%): +/-0.1027

LAG FEATURES AND AR MODEL
Feature matrix: (390, 10)
  Lags: [61.0, 59.4, 61.8, 63.0, 58.4, ...] -> Target: 58.2
  Lags: [58.2, 61.0, 59.4, 61.8, 63.0, ...] -> Target: 57.0   ← 上一行的目标变成了这一行的 lag 1
  Lag 1: +0.5891   Lag 2: +0.4419   ...   Bias: +6.6286

WALK-FORWARD VALIDATION
  Fold 1..5  Train 100/158/216/274/332  Test 58   MSE 9.58 / 9.86 / 10.28 / 7.28 / 8.46
Mean MSE: 9.0921

RANDOM SPLIT vs WALK-FORWARD
Random 80/20 split MSE:  5.9230
Walk-forward mean MSE:   9.4137
Ratio (random/wf):       0.6292

LAG COUNT COMPARISON
       1      12.3759 ...   7  5.3206 ...  14  3.9965 ...  30  3.0984

MULTI-STEP FORECASTING
     1      68.64      71.44      -2.80
     6      61.78      61.66      +0.12
    10      57.07      51.09      +5.97
    17      59.13      43.87     +15.27
Forecast MSE:  54.5676   MAE: 5.9113   MAPE: 10.28%
```

逐段解读：

- **平稳性**：原序列均值随趋势上升（前后两半的均值差约 7.8），被判为非平稳；一阶差分后均值接近 0（理论值正是趋势斜率 0.05），被判为平稳。注意差分后的标准差 3.25 比噪声标准差 2 大——噪声差分后方差翻倍（`2·2² = 8`，`√8 ≈ 2.83`），再加上正弦差分的贡献。
- **ACF**：周期 7 的正弦让 ACF 呈现"7 步一个峰、3~4 步一个谷"的波形，峰值正好在 7、14。几乎所有滞后都打了 `***`，因为强季节信号让大部分滞后都远超白噪声阈值 0.10——**显著不等于有用**，选择滞后时还要看幅度和 PACF。
- **滞后特征**：逐行看，上一行的目标就是下一行的 lag 1，直观验证了"特征只用过去"。AR 权重之和约为 0.89（小于 1），模型带有均值回归倾向，长期递归预测会被拉向不动点 `bias / (1 − Σw) ≈ 60.4`（这是用 400 个点拟合的这一个模型；`demo_forecasting` 只用前 250 个点重新拟合，参数不同）。
- **Walk-forward**：每折训练集逐渐变大（expanding window），各折 MSE 在 7.3–10.3 之间波动，平均约 9.1。作为对照（运行脚本之外另行计算）：在 `demo_random_vs_walk_forward` 的设置（`n=500` 的序列、同样的 walk-forward 切分）下，"明天 = 今天"的 persistence 基线 MSE 约为 10.3，AR(10) 约为 9.4，只比基线好一点点——这提醒你始终要和基线比较。
- **随机 vs walk-forward**：随机切分的 MSE（5.92）比 walk-forward（9.41）低了约 37%，这就是"借用未来邻居"带来的乐观偏差。
- **滞后数**：在 `make_seasonal_series` 上，MSE 随滞后数单调下降，从 1 个滞后的 12.38 降到 30 个的 3.10。原因是序列含有周期 30 的成分，滞后数达到 30 才能完整"看到"一个月度周期；样本有 300 多个，参数只有 31 个，还远没到过拟合的程度。这说明"滞后越多越容易过拟合"要结合样本量和真实周期来判断，而不是一条绝对规则。
- **多步预测**：前几步误差在 ±5 以内，第 10 步之后基本都在 +5 以上，第 17 步达到 +15.27。预测曲线在 44 附近走平，而真实值已经随正弦回升到 60 左右——递归预测把自己的误差当作输入，逐步失去对周期的跟踪。20 步的 MSE（54.6）是一步预测（约 9）的 6 倍。

---

## 7. 动手改一改

1. **补上逆差分**：写 `undifference(last_value, diffs)`，用 `last_value + np.cumsum(diffs)` 还原。然后在一阶差分序列上训练 AR，预测后还原，与直接在原序列上训练的结果比较。
2. **修复 walk-forward 的余数**：让最后一折一直延伸到 `n_samples`；再加一个 `gap` 参数，在训练集和测试集之间留出间隔。
3. **加入滚动特征（注意 shift）**：用窗口 7 和 14 的滚动均值、标准差作为额外特征，但窗口必须截止到 t−1。分别用 `SimpleAR`（线性）和 `sklearn.ensemble.GradientBoostingRegressor` 比较有无这些特征时的 walk-forward MSE。对线性模型来说，窗口不超过最大滞后的滚动均值是冗余的。
4. **加入基线**：实现 persistence（`X[:, 0]`）和 seasonal naive（`X[:, 6]`，即 lag 7）两个基线，放进 `demo_walk_forward` 的表格里一起比较。
5. **直接策略多步预测**：为步长 h = 1..20 各训练一个模型（目标是 `y[t+h−1]`，特征只用 t−1 及更早的值），与 `forecast` 的递归结果逐步对比误差。
6. **按标准公式重写 ACF**：分母改用 `n`（即 `np.sum(...) / n`），与原实现比较 lag 30 处的差异；再实现一个简单的 PACF（对 lag 1..k 做线性回归，取 lag k 的系数）。

---

## 8. 常见坑

- **随机切分 / 普通 K 折**：本节实测随机切分的 MSE 比 walk-forward 低 37%，是虚假的乐观。
- **滚动统计包含当前点**：`check_stationarity` 的窗口包含 i 本身，拿去做特征就是直接把答案喂给模型。所有滚动特征都要先 shift 一位。
- **滞后列顺序搞反**：训练时第 0 列是 lag 1，预测时如果按"旧→新"排列特征，代码不会报错，但结果全错。
- **把经验规则当成统计检验**：`is_stationary` 只比较前后两半，会漏判随机游走；趋势出现在中间、或者方差周期性变化时也可能误判。
- **只评估一步预测、实际却要多步**：一步 MSE 约 9，20 步递归 MSE 约 55，上线前必须按实际预测周期评估。
- **不和基线比**：模型看起来"误差不大"，可能只比"明天 = 今天"好一点点，甚至更差。
