# 测验 · Feature 选择（Feature Selection）

> **阶段 02 · 机器学习基础 · 第 18 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/feature_selection.py](../code/feature_selection.py) ｜ 代码讲解：[code/feature_selection.讲解.md](../code/feature_selection.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要做特征选择 | 维度灾难：特征越多空间越稀疏、噪声越容易被拟合；选对特征 → 训练更快、泛化更好、可解释 |
| 2 | 三大类方法 | Filter（统计量打分，不用模型）、Wrapper（反复训练模型评估子集）、Embedded（训练过程中顺带完成选择） |
| 3 | 方差阈值 | `var(x) < threshold` 的近常数特征直接删；不看目标，"必要但不充分"——高方差的纯噪声它删不掉 |
| 4 | 互信息（MI） | `I(X;Y) = Σ p(x,y)·log(p(x,y) / (p(x)p(y)))`，独立时为 0；能捕捉非线性关系；连续特征需先分箱，箱数影响估计 |
| 5 | RFE（递归特征消除） | 训练 → 按重要性排序 → 删最不重要的 → 重复；考虑特征间相互作用，但要训练约 N − target 次 |
| 6 | L1 / Lasso | 损失加 `alpha·Σ|wᵢ|`，菱形约束让解落在坐标轴上，部分权重恰好为 0；实现上就是梯度步 + 软阈值 |
| 7 | 树模型重要性（MDI） | 累加每次分裂的"样本数 × 不纯度下降"；能处理非线性与交互，但偏向高基数特征 |
| 8 | 置换重要性 | 打乱某一列看验证集性能掉多少；与模型无关、规避基数偏差，但慢，且被相关特征"稀释" |
| 9 | 冗余与单变量排序的陷阱 | 逐个打分的 top-K 会把高度相关的"复制品"一起选进来，反而挤掉真正独立的信号 |

### 核心技能（能动手做到）

- [ ] 从零实现方差阈值，并解释为什么它必须在**标准化之前**的原始特征上使用
- [ ] 从零实现基于等宽分箱的互信息，构造一个"相关系数≈0 但 MI 很高"的例子（如 `y = 1[x² > 1]`）
- [ ] 从零实现 RFE，能读懂它输出的排名，并指出本节实现与 sklearn 排名约定的差异
- [ ] 用"梯度步 + `soft_threshold`"（近端梯度下降）实现 L1 逻辑回归，观察 `alpha`、学习率、迭代次数对非零特征数的影响
- [ ] 从零实现 MDI 树重要性和置换重要性，并在相关特征上解释两者的差异
- [ ] 只在训练集上做特征选择、在测试集上比较"全部特征 vs 选中特征"的准确率，说清楚为什么不能在全量数据上先选再评估

---

## 二、基础自测（选择题）

**Q1.** 下列"方法—类别"的对应中，哪一项与本节讲义一致？

- A. RFE —— Filter
- B. 互信息 —— Wrapper
- C. L1 / Lasso 正则 —— Embedded
- D. 置换重要性 —— Filter

**Q2.** 本节数据中 10 个噪声特征由 `rng.randn(n_samples, 10) * 0.5` 生成。代码用阈值 0.01 做方差过滤，结果是 `surviving: 20 / 20`。对此最准确的解释是：

- A. 阈值设得太高，应该调到 0.5 以上
- B. 方差阈值只看特征自身的波动、不看目标；噪声特征方差约 0.25，远大于 0.01，所以留了下来——它"必要但不充分"
- C. 应该先把所有特征标准化，再做方差阈值，噪声特征就会被删掉
- D. 噪声特征的方差接近 0，是代码计算有误

**Q3.** 设 `x ~ N(0, 1)`，`y = 1 if x² > 1 else 0`。关于 x 与 y 的 Pearson 相关系数 ρ 和互信息 I(X;Y)，正确的是：

- A. ρ ≈ 0，I ≈ 0，x 对 y 没有任何用处
- B. ρ ≈ 0，但 I 明显大于 0
- C. ρ 接近 1，I 接近 0
- D. ρ 和 I 都接近 1

**Q4.** 本节 `mutual_information` 使用 `np.log`（自然对数）。对于一个**类别均衡的二分类**目标 y，任何特征与 y 的互信息最大可能是多少？

- A. 1.0
- B. ln 2 ≈ 0.693
- C. 没有上界，取决于分箱数
- D. 0.5

**Q5.** 本节的 `soft_threshold(w, alpha) = np.sign(w) * np.maximum(np.abs(w) - alpha, 0)`。`soft_threshold(np.array([0.3, -0.05, -0.8]), 0.1)` 的结果是：

- A. `[0.3, 0.0, -0.8]`
- B. `[0.2, -0.15, -0.9]`
- C. `[0.2, 0.0, -0.7]`
- D. `[0.4, 0.05, -0.7]`

**Q6.** 关于 RFE，下列说法**正确**的是：

- A. 用线性模型的 `|w|` 当重要性时，特征是否标准化无所谓
- B. 从 500 个特征每次删 1 个、删到 10 个，需要训练模型 490 次；每轮删掉一批（如末尾 10%）可以显著加速
- C. RFE 只看单个特征与目标的关系，无法考虑特征之间的相互作用
- D. 删掉一个特征后，其余特征的重要性不会改变，所以一次性删掉所有低分特征与逐个删除结果相同

**Q7.** 你在数据里加入一列"随机用户 ID"（每行取值都不同），训练随机森林后发现它的 MDI 重要性排第一。最合理的解释与应对是：

- A. 用户 ID 确实是强特征，应保留
- B. MDI 偏向高基数特征，ID 能把训练样本切得很纯；应在验证集上用置换重要性复核
- C. 这是随机森林的 bug，换 GBDT 就不会出现
- D. 对 ID 做方差阈值即可解决

---

## 三、动手 / 代码题

**Q8.** 本节的分箱函数（原样摘录）：

```python
def discretize(x, n_bins=10):
    min_val, max_val = x.min(), x.max()
    if max_val == min_val:
        return np.zeros_like(x, dtype=int)
    bin_edges = np.linspace(min_val, max_val, n_bins + 1)
    binned = np.digitize(x, bin_edges[1:-1])
    return binned
```

(a) 写出 `discretize(np.array([0.0, 1.0, 2.5, 5.0, 9.99, 10.0]), n_bins=10)` 的输出。
(b) 为什么传给 `np.digitize` 的是 `bin_edges[1:-1]`（只有内部边界），而不是完整的 `bin_edges`？
(c) 为什么要特判 `max_val == min_val`？

**Q9.**（找 bug）运行本节代码，RFE 部分输出的排名是 `Rank 1`（5 个特征）之后直接跳到 `Rank 6`、`Rank 7`……`Rank 20`。下面是 `rfe` 的核心代码（原样摘录）：

```python
def rfe(X, y, n_features_to_select=5, lr=0.1, epochs=100):
    n_total = X.shape[1]
    remaining = list(range(n_total))
    rankings = np.ones(n_total, dtype=int)
    rank = n_total

    while len(remaining) > n_features_to_select:
        X_subset = X[:, remaining]
        w, _ = simple_logistic_importance(X_subset, y, lr, epochs)
        importances = np.abs(w)

        least_idx = np.argmin(importances)
        original_idx = remaining[least_idx]
        rankings[original_idx] = rank
        rank -= 1
        remaining.pop(least_idx)

    for idx in remaining:
        rankings[idx] = 1

    selected_mask = rankings == 1
    return selected_mask, rankings
```

(a) 为什么排名 2~5 不会出现？
(b) sklearn 的 `RFE.ranking_` 约定是：选中的特征为 1，**最后一个**被淘汰的为 2，依此类推。请修改代码使排名连续，并说明为什么 `remaining.pop(least_idx)` 必须在 `remaining[least_idx]` 取值之后（或直接用它的返回值）。

**Q10.** 讲义练习 5：从零实现置换重要性。要求：给定训练好的逻辑回归参数 `w, b` 和验证集，对每一列重复打乱 `n_repeats` 次，返回准确率的平均下降量。然后在本节数据上回答：x1 的三个"复制品"（`info_0`、`info_3`、`corr_0`）的置换重要性各是多少？如果只保留 `info_0`、删掉另外两个复制品再重新训练，`info_0` 的置换重要性会怎么变？为什么？

---

## 四、面试高频题

**Q11.**（基础必考）Filter、Wrapper、Embedded 三类特征选择方法有什么区别？各举两个例子，并说说实际项目里你会怎么组合使用。

**Q12.**（原理深挖）为什么 L1 正则能把权重压到**恰好为 0**，而 L2 只会让权重变小？当多个特征高度相关时，Lasso 会怎么表现？有什么改进？

**Q13.**（原理深挖）树模型自带的 feature importance（MDI）有什么偏差？置换重要性如何缓解？置换重要性在相关特征上又会出什么问题？

**Q14.**（工程实践）同事先在**全部数据**上用互信息选出 top-20 特征，然后在这 20 个特征上做 5 折交叉验证，得到 AUC 0.92，上线后只有 0.80。问题出在哪？正确的流程是什么？

**Q15.**（场景设计）你在做一个风控模型：10 万样本、3000 个候选特征（大量来自自动特征衍生），模型是 GBDT，线上要求特征数尽量少以降低计算和维护成本。请设计一套特征选择方案，并说明如何验证与上线后监控。

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义的分类：Filter = 方差阈值、互信息、卡方检验、相关性过滤；Wrapper = RFE、前向选择、后向消除；Embedded = L1/Lasso、树模型重要性、Elastic Net。L1 在训练中把无用特征的权重压成 0，选择与拟合同时完成，是典型的 Embedded。A、B 都把类别弄反了；D 中置换重要性在讲义对比表里被标为 **Model-agnostic（与模型无关）**——它需要一个训练好的模型，所以不是 Filter。

### Q2 — 答案：B

`rng.randn(...) * 0.5` 的方差是 0.5² = 0.25，远大于阈值 0.01，所以噪声特征全部存活。方差阈值只能删掉"几乎不变"的特征（常数列、99.9% 都是同一个值的列），它**完全不看目标 y**，因此无法区分"有波动的信号"和"有波动的噪声"——讲义原话："a feature can have high variance and still be pure noise"。

C 是一个很隐蔽的错误：标准化后所有特征方差都等于 1，方差阈值就彻底失效了。所以本节代码在**未标准化的** `X_train` 上做方差阈值，而 RFE、L1 用的才是标准化后的数据。这也说明方差阈值对特征的量纲（单位）敏感：同一个特征用"米"和"毫米"表示，方差相差 10⁶ 倍。

### Q3 — 答案：B

`x²` 关于 0 对称，`x > 0` 与 `x < 0` 两侧 y 的分布一模一样，所以线性相关 ρ ≈ 0；但只要知道 |x| 的大小就几乎能确定 y，信息量很大。用本节的 `mutual_information`（10 个等宽箱）在 2000 个样本上实测：ρ ≈ 0.03，MI ≈ 0.40 nats，而 y 的熵 H(Y) ≈ 0.62 nats——x 消除了 y 约 2/3 的不确定性。这正是讲义所说"MI 能捕捉二次、周期等非线性关系，而相关系数会漏掉"。

### Q4 — 答案：B

互信息满足 `I(X;Y) = H(Y) − H(Y|X) ≤ H(Y)`。均衡二分类时 `H(Y) = −2 × 0.5 × ln 0.5 = ln 2 ≈ 0.693`（以 2 为底则是 1 bit）。所以 A 只在用 `log2` 时成立；C 错——分箱数会影响**估计值**，但真实 MI 的上界由 H(Y) 决定（不过箱数过多时，有限样本的估计值会系统性偏高）；D 没有依据。本节运行结果中 MI 最高的 `info_0` 为 0.26 nats，约为上界的 38%。

### Q5 — 答案：C

逐元素：
- `0.3`：`|0.3| − 0.1 = 0.2 > 0`，保持符号 → `0.2`；
- `-0.05`：`0.05 − 0.1 < 0`，被 `maximum(..., 0)` 截成 0 → `0`（NumPy 实际显示为 `-0.`，即负零，数值上等于 0）；
- `-0.8`：`0.8 − 0.1 = 0.7`，恢复负号 → `-0.7`。

软阈值的含义：所有权重都朝 0 方向"收缩" alpha，绝对值小于 alpha 的直接归零——这就是 L1 产生**精确零**的机制。B 是把收缩方向弄反了（远离 0）。

### Q6 — 答案：B

- A 错：`|w|` 的大小与特征量纲直接相关。同一个特征单位从"千元"换成"元"，权重缩小 1000 倍，就会被误判为"不重要"。所以本节代码对 `X_scaled_train` 做 RFE。
- B 对：讲义原文"With 500 features and a target of 10, that is 490 training runs"；可以每轮删一批来加速（sklearn 中是 `step` 参数）。
- C 错：RFE 每轮用**所有剩余特征**一起训练模型，模型看到的是联合效果，所以能考虑交互——这是它比 Filter 更"周到"的原因。
- D 错：重要性是相对的。删掉一个相关特征后，它的"孪生兄弟"会接过权重、变得更重要。这正是要"逐步删、每步重训"的原因。

### Q7 — 答案：B

MDI（Mean Decrease in Impurity）在**训练集**上累计不纯度下降。取值越多的特征，可选的切分点越多，越容易"碰巧"把训练样本切得很纯——随机 ID 每个值都唯一，极端情况下能把每个样本单独切开，于是 MDI 很高，但它在新数据上毫无用处。讲义给出的应对是用**置换重要性**做 sanity check：在验证集上打乱 ID 列，性能几乎不变，说明模型并不真正依赖它。A 是被偏差误导；C 错，GBDT 的 split-gain 重要性同样有这个偏差；D 错，ID 列方差很大，方差阈值删不掉它。

### Q8 — 参考答案

**(a)** 输出 `[0 1 2 5 9 9]`（实际运行验证）。`bin_edges = [0, 1, 2, …, 10]`，内部边界为 `[1, 2, …, 9]`。`np.digitize` 返回"x 落在第几个区间"：0.0 < 1 → 0；1.0 恰好等于边界 1，默认 `right=False` 时区间左闭右开，归入 1；2.5 → 2；5.0 → 5；9.99 和 10.0 都 ≥ 9 → 9。

**(b)** 如果传完整边界 `[0, 1, …, 10]`，同样的输入会得到 `[1 2 3 6 10 11]`：最小值落在 1 号箱而 0 号箱永远为空，**最大值 10.0 因为 ≥ 10 被单独放进第 11 个箱**。去掉首尾边界后，小于第一个内部边界的都归 0，大于等于最后一个内部边界的都归 `n_bins − 1`，恰好得到 `n_bins` 个箱，编号 0 ~ n_bins−1，最大值也被正确地归入最后一个箱。

**(c)** 常数列的 `min == max`，`np.linspace(min, max, 11)` 会得到 11 个相同的边界，分箱没有意义；直接返回全 0 数组，后续计算出的 MI 恰好为 0（只有一个箱，`p(x,y) = p(x)p(y)`），符合"常数特征不含信息"的直觉。

### Q9 — 参考答案

**(a)** `rank` 从 `n_total = 20` 开始，每淘汰一个特征减 1。20 → 5 共淘汰 15 个，分配的排名是 20、19、…、6；循环结束后剩下的 5 个统一记为 1。于是 2~5 被跳过了。排名的**相对顺序**仍然正确（数字越大越早被淘汰），但与 sklearn 的约定不一致，下游如果按"排名 ≤ 6 的特征"之类的规则筛选就会出错。

**(b)** 参考修改：

```python
def rfe_fixed(X, y, n_features_to_select=5, lr=0.1, epochs=100):
    n_total = X.shape[1]
    remaining = list(range(n_total))
    rankings = np.ones(n_total, dtype=int)

    while len(remaining) > n_features_to_select:
        w, _ = simple_logistic_importance(X[:, remaining], y, lr, epochs)
        least_idx = int(np.argmin(np.abs(w)))
        original_idx = remaining.pop(least_idx)          # pop 返回被删除的原始下标
        rankings[original_idx] = len(remaining) - n_features_to_select + 2

    return rankings == 1, rankings
```

pop 之后 `len(remaining)` 已经减 1：最后一次淘汰时剩 5 个，排名 = 5 − 5 + 2 = 2；第一次淘汰时剩 19 个，排名 = 16。在本节数据上实测，选中的特征不变（`info_0, info_1, info_2, info_3, corr_0`），排名变为连续的 `1×5, 2, 3, …, 16`。

关于 `pop` 的顺序：`least_idx` 是在**子集** `X[:, remaining]` 中的位置，不是原始特征编号，必须经 `remaining[least_idx]` 映射回原始编号。如果先 `pop` 再取 `remaining[least_idx]`，拿到的会是后一个特征的编号——典型的"边遍历边修改列表"错误。`original_idx = remaining.pop(least_idx)` 一步到位，既删除又拿到原始编号，最不容易写错。

### Q10 — 参考答案

```python
import numpy as np


def permutation_importance(X_val, y_val, w, b, n_repeats=10, seed=0):
    rng = np.random.RandomState(seed)

    def accuracy(Xm):
        z = Xm @ w + b
        return np.mean(((1.0 / (1.0 + np.exp(-z))) >= 0.5).astype(int) == y_val)

    baseline = accuracy(X_val)
    importances = np.zeros(X_val.shape[1])
    for j in range(X_val.shape[1]):
        drops = []
        for _ in range(n_repeats):
            X_perm = X_val.copy()                         # 不能原地修改验证集
            X_perm[:, j] = rng.permutation(X_perm[:, j])  # 只打乱第 j 列
            drops.append(baseline - accuracy(X_perm))
        importances[j] = np.mean(drops)
    return baseline, importances
```

在本节数据上（前 400 条训练、后 100 条验证，用训练集均值/标准差标准化，`simple_logistic_importance(..., 0.1, 300)` 训练）实测：

```
baseline acc: 0.94
  corr_0   drop=0.103  |w|=1.187
  info_0   drop=0.094  |w|=1.222
  info_3   drop=0.091  |w|=1.207
  info_2   drop=0.062  |w|=0.989
  info_4   drop=0.053  |w|=0.805
  info_1   drop=0.050  |w|=0.845
```

删掉 `info_3`、`corr_0` 等复制品（只保留 `info_0, info_1, info_2` 和 10 个噪声特征）重训后，`info_0` 的置换重要性从约 0.09 **跃升到 0.343**。

原因：x1 的信息被三个几乎相同的特征（两两相关系数约 0.99）**分摊**了。打乱其中一个，另外两个仍携带几乎相同的信息，模型损失不大，所以每个复制品看起来都"只是中等重要"。这就是讲义练习 5 提示的"相关特征会让置换重要性低估"。应对：先按相关性把特征分组，**整组一起打乱**；或先去冗余再计算重要性。

### Q11 — 参考回答要点

| | Filter | Wrapper | Embedded |
|---|---|---|---|
| 原理 | 用统计量给每个特征单独打分 | 训练模型评估特征子集，用模型性能当分数 | 在模型训练过程中完成选择 |
| 例子 | 方差阈值、互信息、卡方、相关性过滤 | RFE、前向选择、后向消除 | L1/Lasso、树模型重要性、Elastic Net |
| 速度 | 很快，与模型无关 | 慢，需反复训练 | 一次训练 |
| 交互 | 看不到特征之间的交互和冗余 | 能考虑 | 能部分考虑 |
| 风险 | 选出冗余特征、漏掉"单独弱、组合强"的特征 | 计算贵，小样本下容易对验证集过拟合 | 依赖模型假设（L1 只适合线性） |

- **组合方式**（讲义的决策流程）：先用方差阈值等低成本 Filter 去掉明显无用的特征 → 特征多时用 MI 粗筛 → 用 L1 或树重要性、或在幸存特征上跑 RFE 精选 → 在留出集上对比"选中特征 vs 全部特征"，没提升就保留全部。
- **加分点**：用本节运行结果举例——MI 与树重要性的 top-5 都漏掉了真正的信号 `info_2`（x3，单独与 y 的相关系数只有约 0.18，被更强的 x1、x2 掩盖了），反而选了 x1 的三个复制品，测试准确率只有 0.90；而 RFE 保留了 `info_2`，准确率 0.96。这说明单变量 Filter 的 top-K 会被冗余特征"占坑"，工程上常用 mRMR（最大相关最小冗余）或先做相关性去重。

### Q12 — 参考回答要点

- **几何解释**：带约束形式 `min loss s.t. Σ|wᵢ| ≤ t`。L1 约束区域是菱形（高维是"多面体"），尖角都在坐标轴上；损失函数的等高线（椭圆）与之相切时，很大概率先碰到尖角，此时某些坐标恰好为 0。L2 约束是圆（球），边界处处光滑，切点几乎不会恰好落在坐标轴上，权重只是变小。
- **优化角度**：L2 惩罚的梯度是 `2λw`，w 越小推力越小，永远到不了 0；L1 的次梯度是 `λ·sign(w)`，不管 w 多小，推力都是常数 λ，能一路推到 0。本节代码的近端梯度下降中，这体现为 `soft_threshold`：每步把 `|w|` 减去 `lr·alpha`，小于它的直接归零。
- **相关特征下的表现**：讲义说 Lasso 会"选一个、把其余置零"。但要注意：①选哪一个往往很随意，数据稍有扰动就换一个，**不稳定**；②需要优化真正收敛。本节代码默认设置（`lr=0.01, epochs=1000`）远未收敛，结果是 8 个非零权重、x1 的三个复制品权重都在 0.53~0.55；把迭代加到 `lr=0.5, epochs=20000` 后非零特征降到 5 个（`info_0, info_1, info_2, info_3, corr_1`），更稀疏了，但仍保留了 x1 的两个复制品。
- **改进**：Elastic Net（L1 + L2）在相关特征间"成组"分配权重，更稳定；Stability Selection（讲义练习 2）在多次子采样上统计入选频率；Group Lasso 按组选特征。
- **常见误区**：认为"Lasso 把权重压成 0 的特征就一定没用"——它可能只是被一个高度相关的兄弟特征替代了。

### Q13 — 参考回答要点

- **MDI 的偏差**：
  1. 偏向高基数（取值多）的连续特征或 ID 类特征：切分点多，在训练集上容易"碰巧"降低不纯度；
  2. 在**训练集**上计算，过拟合的分裂也会贡献重要性；
  3. 相关特征之间会互相分摊重要性，分摊比例随机。
- **置换重要性的改进**：在**验证集**上打乱某列，测量真实性能下降，衡量的是"模型泛化时有多依赖这个特征"；与模型无关，规避了基数偏差。代价是慢（每个特征 × 重复次数都要做一次推理）。
- **置换重要性在相关特征上的问题**：①打乱一个特征，其相关兄弟仍能提供信息，重要性被低估（见 Q10 的实验：三个复制品各约 0.09，去冗余后升到 0.34）；②打乱会产生现实中不存在的特征组合（如"身高 1.5 米、体重 120 公斤"），模型在分布外的表现不可信。应对：按相关性分组置换、条件置换重要性，或使用 SHAP 等方法并结合领域知识解读。
- **加分点**：区分"模型依赖哪些特征"（重要性）和"哪些特征与目标有因果关系"——重要性高不等于因果。

### Q14 — 参考回答要点

- **问题**：**特征选择泄漏（selection bias）**。在全部数据上选特征时，验证折里的样本已经参与了"哪些特征与 y 相关"的判断。特征多、样本少时，总有一些纯噪声特征**碰巧**与全部数据的 y 相关，它们被选中后，CV 的每个验证折都"认识"这种巧合，分数被系统性高估。上线后面对真正的新数据，巧合消失，性能回落。
- **正确流程**：把特征选择当作模型训练的一部分，放进 Pipeline，在**每一折的训练部分**上重新做选择：

  ```python
  from sklearn.pipeline import Pipeline
  from sklearn.feature_selection import SelectKBest, mutual_info_classif
  from sklearn.linear_model import LogisticRegression
  from sklearn.model_selection import cross_val_score

  pipe = Pipeline([
      ("select", SelectKBest(mutual_info_classif, k=20)),
      ("model", LogisticRegression(max_iter=1000)),
  ])
  scores = cross_val_score(pipe, X, y, cv=5, scoring="roc_auc")
  ```

  如果 k 本身也要调，就用嵌套交叉验证（内层选 k，外层评估）。最终的独立测试集只用一次。
- **本节代码的正确示范**：所有选择方法都只用 `X_train` / `X_scaled_train`，标准化的均值和标准差也只从训练集计算，`evaluate_accuracy` 再在留出的 20% 上评估。
- **常见误区**：以为"只有用到 y 的步骤才会泄漏"——标准化、缺失值填充用全量统计量同样会泄漏，只是通常影响较小；有监督的特征选择泄漏影响大得多。

### Q15 — 参考回答要点

一个分阶段、由粗到细的漏斗方案：

1. **低成本过滤**（Filter，几分钟）：删除缺失率过高、常数/近常数（方差阈值）、单一取值占比极高的特征；对高度相关（如 |ρ| > 0.95）的特征组只保留一个（保留与目标 MI 更高、或业务含义更清晰的那个）。
2. **单变量粗筛**：用 MI 或风控常用的 IV（Information Value）去掉几乎无信息的特征，比如从 3000 降到 500。注意：这一步只用来去掉明显无用的，不要用来选最终的 top-K（Q11 提到的冗余陷阱）。
3. **模型精选**（Embedded / Wrapper）：在训练集上训练 GBDT，结合 gain 重要性和验证集上的置换重要性（或 SHAP 均值）排序；在幸存特征上做按比例删除的 RFE（每轮删 10%），画出"特征数—验证 AUC"曲线，选曲线进入平台期的最小特征数。
4. **稳定性检查**：用不同随机种子 / 多次子采样 / 多个时间窗口重复第 3 步，只保留在大多数轮次中都入选的特征（Stability Selection 思想）。
5. **验证**：按**时间**切分（训练用过去、验证用未来），对比"选中特征 vs 全部特征"的 AUC 与 KS；确认精简后性能不降或只降一点，同时推理延迟、特征计算成本明显下降。
6. **上线与监控**：监控每个入模特征的分布漂移（如 PSI）、缺失率、取值范围；监控模型分数分布和线上效果；某特征上游数据源下线时要有降级方案；定期（如每季度）重跑选择流程。

- **加分点**：所有有监督的选择步骤都只在训练集（或 CV 的训练折）上进行；考虑特征的**获取成本与合规性**（有些特征计算贵或涉及敏感信息，宁可略损性能也要去掉）。

---

## 六、关联知识点

### 前置知识
- [阶段 02 · 08 Feature 工程与选择](../../08-feature-engineering/docs/zh.md)：特征工程与基础的 filter 选择方法，本节在其上扩展出 wrapper 与 embedded。
- [阶段 02 · 03 逻辑回归](../../03-logistic-regression/docs/zh.md)：RFE 和 L1 选择都基于逻辑回归的梯度下降。
- [阶段 02 · 04 决策树和随机森林](../../04-decision-trees/docs/zh.md)：Gini 不纯度、分裂增益、MDI 与置换重要性的对比。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：熵、互信息的定义与计算。
- [阶段 01 · 15 机器学习统计学](../../../01-math-foundations/15-statistics-for-ml/docs/zh.md)：方差、相关系数。

### 本节被哪些后续内容用到 / 相关小节
- [阶段 02 · 10 偏差-方差权衡](../../10-bias-variance/docs/zh.md)：去掉噪声特征是降低方差的手段之一；L1 正则在偏差与方差之间做权衡。
- [阶段 02 · 02 线性回归](../../02-linear-regression/docs/zh.md)：练习中实现 Lasso 并对比 Ridge，理解 L1 为何产生稀疏解。
- [阶段 02 · 11 集成方法](../../11-ensemble-methods/docs/zh.md)：随机森林、梯度提升自带的特征重要性。
- [阶段 02 · 12 超参数调优](../../12-hyperparameter-tuning/docs/zh.md)：保留多少个特征（k）、L1 的 alpha 都应通过交叉验证来选。
- [阶段 02 · 13 机器学习管道](../../13-ml-pipelines/docs/zh.md)：把特征选择放进 Pipeline，在每一折内拟合，避免选择泄漏。
- [阶段 01 · 10 降维](../../../01-math-foundations/10-dimensionality-reduction/docs/zh.md)：PCA 等**特征提取**（构造新特征）与本节的**特征选择**（保留原特征子集）是降维的两条路线。
- [阶段 02 · 17 处理不平衡数据](../../17-imbalanced-data/docs/zh.md)：不平衡场景下做特征选择时，评估指标应换成 F1/AUPRC 而不是 accuracy。

### 延伸关键词
`Forward / Backward Selection` · `Stability Selection` · `Elastic Net` · `Group Lasso` · `mRMR（最大相关最小冗余）` · `Boruta` · `SHAP` · `Conditional Permutation Importance` · `Kraskov k-NN 互信息估计` · `Information Value (IV) / PSI` · `Selection bias / Nested CV` · `Curse of dimensionality`
