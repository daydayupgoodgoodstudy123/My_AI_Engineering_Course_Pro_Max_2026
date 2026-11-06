<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="statistics-for-machine-learning"></a>

# 机器学习统计

> 通过统计数据，您可以了解您的模型是否确实有效或只是运气好。

**类型：** 构建
**语言：** Python
**先决条件：** 第 1 阶段，第 06 课（概率与分布）、第 07 课（贝叶斯定理）
**时间：** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 从头开始计算描述性统计、Pearson/Spearman 相关性和协方差矩阵
- 执行假设检验（t 检验、卡方）并正确解释 p 值和置信区间
- 使用引导重采样为任何指标构建置信区间，无需分布假设
- 使用效应大小测量区分统计显着性和实际显着性

<a id="the-problem"></a>

## 问题

您训练了两个模型。模型 A 在测试集上的得分为 0.87。模型 B 得分 0.89。您部署模型 B。三周后，生产指标比以前更差。发生了什么？

模型 B 实际上并没有优于模型 A。0.02 的差异是噪音。您的测试集太小，或方差太大，或两者兼而有之。你将随机性装扮成改进。

这种情况经常发生。 Kaggle 排行榜变动。无法重现的论文。 A/B 测试根据数百个样本宣布获胜者。根本原因总是一样的：有人跳过了统计。

统计学为您提供了区分信号和噪声的工具。它告诉您何时存在真正的差异、您应该有多大的信心以及您需要多少数据才能信任结果。每个机器学习管道、每个模型比较、每个实验都需要统计数据。没有它，你就是在猜测。

<a id="the-concept"></a>

## 概念

<a id="descriptive-statistics-summarizing-your-data"></a>

### 描述性统计：总结您的数据

在对任何内容进行建模之前，您需要知道数据是什么样的。描述性统计将数据集压缩为几个捕捉其形状的数字。

**集中趋势测度**回答“中间在哪里？”

```
Mean:   sum of all values / count
        mu = (1/n) * sum(x_i)

Median: middle value when sorted
        Robust to outliers. If you have [1, 2, 3, 4, 1000], the mean is 202
        but the median is 3.

Mode:   most frequent value
        Useful for categorical data. For continuous data, rarely informative.
```

均值就是平衡点。中位数是中间标记。当它们出现分歧时，你的分布就会倾斜。收入分布的平均值>>中位数（来自亿万富翁的右偏）。训练期间的损失分布通常具有平均值 << 中值（简单样本的左偏）。

**传播的度量**回答“数据的分散程度如何？”

```
Variance:   average squared deviation from the mean
            sigma^2 = (1/n) * sum((x_i - mu)^2)

Standard deviation:  square root of variance
                     sigma = sqrt(sigma^2)
                     Same units as the data, so more interpretable.

Range:      max - min
            Sensitive to outliers. Almost never useful alone.

IQR:        Q3 - Q1 (interquartile range)
            The range of the middle 50% of the data.
            Robust to outliers. Used for box plots and outlier detection.
```

**Percentiles** 将排序后的数据分为 100 等份。第 25 个百分位 (Q1) 意味着 25% 的值低于此点。第 50 个百分位数是中位数。第 75 个百分位数是 Q3。

```
For latency monitoring:
  P50 = median latency        (typical user experience)
  P95 = 95th percentile       (bad but not worst case)
  P99 = 99th percentile       (tail latency, often 10x the median)
```

在 ML 中，您关心 inference 延迟的百分位数、预测置信度分布以及理解错误分布。平均误差较低但 P99 误差严重的模型对于安全关键型应用可能毫无用处。

**样本与总体统计。** 计算样本方差时，除以 (n-1) 而不是 n。这是贝塞尔的修正。它补偿了样本均值不是真实总体均值的事实。当分母为 n 时，您会系统性地低估真实方差。对于 (n-1)，估计是无偏的。

```
Population variance: sigma^2 = (1/N) * sum((x_i - mu)^2)
Sample variance:     s^2     = (1/(n-1)) * sum((x_i - x_bar)^2)
```

实际上：如果 n 很大（数千个样本），则差异可以忽略不计。如果 n 很小（几十个样本），那就很重要。

<a id="correlation-how-variables-move-together"></a>

### 相关性：变量如何一起移动

相关性衡量两个变量之间线性关系的强度和方向。

**皮尔逊相关系数**衡量线性关联：

```
r = sum((x_i - x_bar)(y_i - y_bar)) / (n * s_x * s_y)

r = +1:  perfect positive linear relationship
r = -1:  perfect negative linear relationship
r =  0:  no linear relationship (but there might be a nonlinear one!)

Range: [-1, 1]
```

皮尔逊假设该关系是线性的，并且两个变量大致呈正态分布。它对异常值很敏感。单个极值点可以将 r 从 0.1 拖至 0.9。

**斯皮尔曼等级相关** 测量单调关联：

```
1. Replace each value with its rank (1, 2, 3, ...)
2. Compute Pearson correlation on the ranks

Spearman catches any monotonic relationship, not just linear.
If y = x^3, Pearson gives r < 1 but Spearman gives rho = 1.
```

**何时使用每个：**

```
Pearson:    Both variables are continuous and roughly normal.
            You care about the linear relationship specifically.
            No extreme outliers.

Spearman:   Ordinal data (rankings, ratings).
            Data is not normally distributed.
            You suspect a monotonic but not linear relationship.
            Outliers are present.
```

**黄金法则：** 相关性并不意味着因果关系。冰淇淋销量和溺水死亡人数是相关的，因为两者都会在夏季增加。您的模型的准确性和 parameters 的数量是相关的，但添加 parameters 不会自动提高准确性（请参阅：overfitting）。

<a id="covariance-matrix"></a>

### 协方差矩阵

两个变量之间的协方差衡量它们如何一起变化：

```
Cov(X, Y) = (1/n) * sum((x_i - x_bar)(y_i - y_bar))

Cov(X, Y) > 0:  X and Y tend to increase together
Cov(X, Y) < 0:  when X increases, Y tends to decrease
Cov(X, Y) = 0:  no linear co-movement
```

对于 d features，协方差矩阵 C 是 d x d 矩阵，其中 C[i][j] = Cov(feature_i,特征_j）。对角线条目 C[i][i] 是每个 feature 的方差。

```
C = | Var(x1)      Cov(x1,x2)  Cov(x1,x3) |
    | Cov(x2,x1)  Var(x2)      Cov(x2,x3) |
    | Cov(x3,x1)  Cov(x3,x2)  Var(x3)     |

Properties:
  - Symmetric: C[i][j] = C[j][i]
  - Positive semi-definite: all eigenvalues >= 0
  - Diagonal = variances
  - Off-diagonal = covariances
```

**连接到PCA。** PCA特征分解协方差矩阵。 eigenvectors 是主成分（最大方差的方向）。 eigenvalues 告诉您每个组件捕获了多少方差。这正是第 10 课所涵盖的内容，但现在您知道为什么协方差矩阵是正确的分解对象：它对数据中的所有成对线性关系进行编码。

**连接到相关性。**相关矩阵是标准化变量的协方差矩阵（每个变量除以其标准差）。 相关性使协方差归一化，因此所有值都落在[-1, 1]。

<a id="hypothesis-testing"></a>

### 假设检验

假设检验是在不确定性下做出决策的框架。您从声明开始，收集数据，并确定数据是否与声明一致。

**设置：**

```
Null hypothesis (H0):        the default assumption, usually "no effect"
Alternative hypothesis (H1): what you are trying to show

Example:
  H0: Model A and Model B have the same accuracy
  H1: Model B has higher accuracy than Model A
```

**p 值** 是假设 H0 为真时看到与您观察到的极端数据的概率。这不是 H0 为真的概率。这是统计学中最常见的误解。

```
p-value = P(data this extreme | H0 is true)

If p-value < alpha (typically 0.05):
    Reject H0. The result is "statistically significant."
If p-value >= alpha:
    Fail to reject H0. You do not have enough evidence.
    This does NOT mean H0 is true.
```

** 置信区间** 给出 parameter 的一系列合理值：

```
95% confidence interval for the mean:
    x_bar +/- z * (s / sqrt(n))

where z = 1.96 for 95% confidence

Interpretation: if you repeated this experiment many times, 95% of the
computed intervals would contain the true mean. It does NOT mean there
is a 95% probability the true mean is in this specific interval.
```

置信区间的宽度告诉您精度。宽的区间意味着高的不确定性。窄间隔意味着您的估计是精确的（但如果您的数据有偏差，则不一定准确）。

<a id="the-t-test"></a>

### t 检验

t 检验比较平均值。有好几种口味。

**单样本 t 检验：** 总体平均值与假设值不同吗？

```
t = (x_bar - mu_0) / (s / sqrt(n))

degrees of freedom = n - 1
```

**双样本t检验（独立）：**两组均值不同吗？

```
t = (x_bar_1 - x_bar_2) / sqrt(s1^2/n1 + s2^2/n2)

This is Welch's t-test, which does not assume equal variances.
Always use Welch's unless you have a specific reason for equal variances.
```

**配对 t 检验：** 当测量成对出现时（同一模型在相同数据分割上评估）：

```
Compute d_i = x_i - y_i for each pair
Then run a one-sample t-test on the d_i values against mu_0 = 0
```

在 ML 中，配对 t 检验很常见：您在相同的 10 个交叉验证折叠上运行两个模型，并成对比较它们的分数。

<a id="chi-squared-test"></a>

### 卡方检验

卡方检验检查观察到的频率是否与预期频率匹配。对于分类数据很有用。

```
chi^2 = sum((observed - expected)^2 / expected)

Example: does a language model's output distribution match the
training distribution across categories?

Category    Observed   Expected
Positive       120        100
Negative        80        100
chi^2 = (120-100)^2/100 + (80-100)^2/100 = 4 + 4 = 8

With 1 degree of freedom, chi^2 = 8 gives p < 0.005.
The difference is significant.
```

<a id="ab-testing-for-ml-models"></a>

### ML 模型的 A/B 测试

ML 中的 A/B 测试与 Web A/B 测试不同。模型比较具有特定的挑战：

```
1. Same test set:    Both models must be evaluated on identical data.
                     Different test sets make comparison meaningless.

2. Multiple metrics: Accuracy alone is not enough. You need precision,
                     recall, F1, latency, and fairness metrics.

3. Variance:         Use cross-validation or bootstrap to estimate
                     the variance of each metric, not just point estimates.

4. Data leakage:     If the test set was used during model selection,
                     your comparison is biased. Hold out a final test set.
```

**程序：**

```
1. Define your metric and significance level (alpha = 0.05)
2. Run both models on the same k-fold cross-validation splits
3. Collect paired scores: [(a1, b1), (a2, b2), ..., (ak, bk)]
4. Compute differences: d_i = b_i - a_i
5. Run a paired t-test on the differences
6. Check: is the mean difference significantly different from 0?
7. Compute a confidence interval for the mean difference
8. Compute effect size (Cohen's d) to judge practical significance
```

<a id="statistical-significance-vs-practical-significance"></a>

### 统计意义与实际意义

结果可能具有统计学意义，但实际上毫无意义。有了足够的数据，即使是微小的差异也会变得具有统计显着性。

```
Example:
  Model A accuracy: 0.9234
  Model B accuracy: 0.9237
  n = 1,000,000 test samples
  p-value = 0.001

Statistically significant? Yes.
Practically significant? A 0.03% improvement is not worth the
engineering cost of deploying a new model.
```

**E效果大小** 量化差异有多大，与样本大小无关：

```
Cohen's d = (mean_1 - mean_2) / pooled_std

d = 0.2:  small effect
d = 0.5:  medium effect
d = 0.8:  large effect
```

始终报告 p 值和效应大小。 p 值告诉您差异是否真实。效应大小告诉你它是否重要。

<a id="multiple-comparison-problem"></a>

### 多重比较问题

当你检验许多假设时，有些假设会偶然“显着”。如果您在 alpha = 0.05 时测试 20 个事物，即使没有任何东西是真实的，您也预计会出现 1 个误报。

```
P(at least one false positive) = 1 - (1 - alpha)^m

m = 20 tests, alpha = 0.05:
P(false positive) = 1 - 0.95^20 = 0.64

You have a 64% chance of at least one false positive.
```

**Bonferroni 校正：** 将 alpha 除以测试次数。

```
Adjusted alpha = alpha / m = 0.05 / 20 = 0.0025

Only reject H0 if p-value < 0.0025.
Conservative but simple. Works when tests are independent.
```

在 ML 中，当您比较多个指标的模型、测试许多 hyperparameter 配置或评估多个数据集时，这一点很重要。

<a id="bootstrap-methods"></a>

### 引导方法

Bootstrapping 通过使用替换对数据进行重新采样来估计统计数据的 sampling 分布。无需对基础分布进行假设。

**算法：**

```
1. You have n data points
2. Draw n samples WITH replacement (some points appear multiple times,
   some not at all)
3. Compute your statistic on this bootstrap sample
4. Repeat B times (typically B = 1000 to 10000)
5. The distribution of bootstrap statistics approximates the
   sampling distribution
```

**Bootstrap置信区间（百分位法）：**

```
Sort the B bootstrap statistics
95% CI = [2.5th percentile, 97.5th percentile]
```

**为什么引导程序对 ML 很重要：**

```
- Test set accuracy is a point estimate. Bootstrap gives you
  confidence intervals.
- You cannot assume metric distributions are normal (especially
  for AUC, F1, precision at k).
- Bootstrap works for ANY statistic: median, ratio of two means,
  difference in AUC between two models.
- No closed-form formula needed.
```

**用于模型比较的Bootstrap：**

```
1. You have predictions from Model A and Model B on the same test set
2. For each bootstrap iteration:
   a. Resample test indices with replacement
   b. Compute metric_A and metric_B on the resampled set
   c. Store diff = metric_B - metric_A
3. 95% CI for the difference:
   [2.5th percentile of diffs, 97.5th percentile of diffs]
4. If the CI does not contain 0, the difference is significant
```

这比配对 t 检验更稳健，因为它不做出分布假设。

<a id="parametric-vs-non-parametric-tests"></a>

### 参数与非参数测试

**参数测试**假设特定分布（通常是正态分布）：

```
t-test:         assumes normally distributed data (or large n by CLT)
ANOVA:          assumes normality and equal variances
Pearson r:      assumes bivariate normality
```

**非参数检验**不做分布假设：

```
Mann-Whitney U:     compares two groups (replaces independent t-test)
Wilcoxon signed-rank: compares paired data (replaces paired t-test)
Spearman rho:       correlation on ranks (replaces Pearson)
Kruskal-Wallis:     compares multiple groups (replaces ANOVA)
```

**何时使用非参数：**

```
- Small sample size (n < 30) and data is clearly non-normal
- Ordinal data (ratings, rankings)
- Heavy outliers you cannot remove
- Skewed distributions
```

**何时使用参数：**

```
- Large sample size (CLT makes the test statistic approximately normal)
- Data is roughly symmetric without extreme outliers
- More statistical power (better at detecting real differences)
```

在 ML 实验中，通常有较小的 n（5 或 10 个交叉验证折叠），因此像 Wilcoxon 符号秩这样的非参数检验通常比 t 检验更合适。

<a id="central-limit-theorem-practical-implications"></a>

### 中心极限定理：实际意义

CLT 表示，随着 n 的增长，样本均值的分布接近正态分布，无论基本总体分布如何。

```
If X_1, X_2, ..., X_n are iid with mean mu and variance sigma^2:

    X_bar ~ Normal(mu, sigma^2 / n)    as n -> infinity

Works for n >= 30 in most cases.
For highly skewed distributions, you might need n >= 100.
```

**为什么这对 ML 很重要：**

```
1. Justifies confidence intervals and t-tests on aggregated metrics
2. Explains why averaging over cross-validation folds gives stable
   estimates even when individual folds vary wildly
3. Mini-batch gradient descent works because the average gradient
   over a batch approximates the true gradient (CLT in action)
4. Ensemble methods: averaging predictions from many models gives
   more stable output than any single model
```

** CLT 不做什么：**

```
- Does NOT make your data normal. It makes the MEAN of samples normal.
- Does NOT work for heavy-tailed distributions with infinite variance
  (Cauchy distribution).
- Does NOT apply to dependent data (time series without correction).
```

<a id="common-statistical-mistakes-in-ml-papers"></a>

### ML 论文中常见的统计错误

1. **在训练集上进行测试。**保证overfitting。始终保留模型在训练期间从未见过的数据。

2. **没有置信区间。** 报告没有不确定性的单个准确度数字会使结果无法重现且无法验证。

3. **忽略多重比较。** 测试 50 种配置并报告最佳配置而不进行修正会增加误报率。

4. ** 令人困惑的统计意义和实际意义。** 对于 0.01% 的精度改进，p 值为 0.001 没有意义。

5. **在不平衡数据上使用准确性。** 在具有 99% 负类的数据集上达到 99% 的准确性意味着模型什么也没学到。使用精确率、召回率、F1 或 AUC。

6. **Cherry-picking 指标。** 仅报告模型获胜的指标。诚实的 evaluation 报告所有相关指标。

7. **在训练/测试拆分中泄漏信息。** 在拆分之前进行归一化，或使用未来数据来预测过去。

8. **没有方差估计的小测试集。** 对 100 个样本进行评估并声称 2% 的改进是噪声，而不是信号。

9. ** 当数据不独立时假设独立。** 来自同一患者的医学图像，来自同一文档的多个句子。组内的观察结果是相关的。

10. **P-hacking.** 尝试不同的测试、子集或排除标准，直到得到 p < 0.05。结果是搜索的产物。

<a id="building-it"></a>

## 构建它

您将实施：

1. **从头开始的描述性统计**（均值、中位数、众数、标准差、百分位数、IQR）
2. **相关函数**（Pearson和Spearman，带有协方差矩阵）
3. **H假设检验**（单样本t检验、双样本t检验、卡方检验）
4. **Bootstrap 置信区间**（对于任何统计量，无需假设）
5. **A/B测试模拟器**（生成数据、测试、检查I类和II类错误）
6. **统计与实际意义演示**（表明大n使一切“显着”）

一切从头开始，仅使用 `math` 和 `random`。没有numpy，没有scipy。

```figure
f3-bootstrap-resample
```

<a id="key-terms"></a>

## 关键术语

| 术语 | 定义 |
|---|---|
| 平均值 | 值的总和除以计数。对异常值敏感。 |
| 中位数 | 排序数据的中间值。对异常值具有鲁棒性。 |
| 标准差 | 方差的平方根。措施以原始单位传播。 |
| 百分位数 | 低于给定百分比的数据的值。 |
| IQR | 四分位数范围。 Q3 减去 Q1。中间的价差50%。 |
| 皮尔逊相关系数 | 测量两个变量之间的线性关联。范围 [-1、1]。 |
| 斯皮尔曼相关系数 | 使用排名来衡量单调关联。 |
| 协方差矩阵 | 所有 features 之间的成对协方差矩阵。 |
| 零假设 | 默认假设没有影响或没有差异。 |
| p 值 | 在原假设成立的情况下，这种极端数据的概率。 |
| 置信区间 | 给定置信水平下 parameter 的合理值范围。 |
| t检验 | 测试均值是否存在显着差异。使用 t 分布。 |
| 卡方检验 | 测试观察到的频率是否与预期频率不同。 |
| 效应大小 | 差异的大小，与样本大小无关。科恩的 d 很常见。 |
| 邦费罗尼校正 | 将显着性阈值除以测试数量以控制误报。 |
| 引导程序 | 通过替换重新采样以估计 sampling 分布。 |
| I 类错误 | 误报。当 H0 为真时拒绝 H0。 |
| II 类错误 | 假阴性。当 H0 为假时未能拒绝。 |
| 统计功效 | 正确拒绝假 H0 的概率。功效 = 1 减去 II 类错误率。 |
| 中心极限定理 | 随着样本量的增加，样本均值收敛于正态分布。 |
| 参数测试 | 假设数据服从特定分布（通常是正态分布）。 |
| 非参数检验 | 不做任何分布假设。适用于等级或标志。 |
