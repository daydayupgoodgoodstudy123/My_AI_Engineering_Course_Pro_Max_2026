# 代码讲解 · ml_intro.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 01 节 什么是机器学习 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python ml_intro.py`（无命令行参数） ｜ **依赖**：`numpy`（仅此一个第三方库，不需要 sklearn）

---

## 1. 这份代码在考察什么

这份代码用一个"最简单的 ML 算法"——**最近质心分类器（Nearest Centroid）**——把机器学习的完整套路走一遍：

1. **学（fit）**：从训练数据里提炼出一个表示（每一类的均值，即质心）。
2. **预测（predict）**：对新数据，用学到的表示做判断（离哪个质心近就归哪一类）。
3. **评估（score + baseline）**：在没见过的测试集上算准确率，并和随机基线、多数类基线比较。
4. **实验意识**：改变"类别间距"和"特征维度"，观察准确率怎么变——这就是做 ML 实验的基本动作。
5. **NumPy 基本功**：布尔掩码选行、`axis` 参数、`argmin`、`unique`、`permutation`，都是后面每一节都会反复用到的。

> 一句话：**算法本身只有 6 行，真正要学的是"学 → 预测 → 和基线比"这套工作流**——从逻辑回归到 Transformer，流程都一样，只是"表示"越来越复杂。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `NearestCentroid` | 类 | `fit` 求每类均值；`predict` 按最近质心分类；`score` 算准确率 | 模型 = 用参数编码的规则 |
| `generate_classification_data` | 函数 | 生成两个高斯团的二分类数据，`separation` 控制间距 | 合成数据、可控难度 |
| `train_test_split` | 函数 | 随机打乱后按比例切成训练/测试集 | 泛化评估 |
| `random_baseline` | 函数 | 按训练集类别比例随机猜 | 基线 |
| `majority_baseline` | 函数 | 永远猜训练集中最多的那一类 | 基线 |
| `demo_nearest_centroid` | 演示 | 完整跑一遍：训练、看质心、对比基线 | ML 工作流 |
| `demo_varying_difficulty` | 演示 | 改变类间距离，观察准确率 | 数据可分性决定上限 |
| `demo_higher_dimensions` | 演示 | 改变特征维度 | 维度的影响 |
| `demo_multiclass` | 演示 | 3 类问题 | 多分类自然推广 |

数据流：`generate_classification_data → train_test_split → NearestCentroid.fit(train) → score(train/test)`，再与两个 baseline 对比；四个 `demo_*` 函数在 `__main__` 中依次调用。

---

## 3. 逐段精讲

### 3.1 `fit`：每一类求一个均值

```python
class NearestCentroid:
    def __init__(self):
        self.classes = None
        self.centroids = None

    def fit(self, X, y):
        self.classes = np.unique(y)
        self.centroids = np.array([
            X[y == c].mean(axis=0) for c in self.classes
        ])
```

- `np.unique(y)` 返回**排好序、去重后**的类别数组，比如 `[0, 1]` 或 `['cat', 'dog']`。它同时决定了质心的排列顺序：第 i 个质心对应 `self.classes[i]`。
- `y == c` 产生一个布尔数组，`X[y == c]` 用它做**布尔掩码索引**，取出属于类 c 的所有行。
- `.mean(axis=0)` 沿"样本"方向（第 0 轴）求平均，得到一个长度为特征数 d 的向量。`axis=0` 是"把行压扁"，`axis=1` 是"把列压扁"——初学者最容易搞反的地方。
- 最终 `self.centroids` 形状为 `(类别数 k, 特征数 d)`。这就是整个"模型"：二分类二维时只有 4 个数。
- `__init__` 里先置为 `None`，表示"未训练"状态。这是 sklearn 风格：构造时不碰数据，`fit` 时才学习。
- ⚠️ 没有检查"未 fit 就 predict"的情况，此时会因 `None` 不可迭代而报一个难懂的 `TypeError`。sklearn 会抛 `NotFittedError`。

### 3.2 `predict`：算到每个质心的距离，取最近的

```python
    def predict(self, X):
        distances = np.array([
            np.sqrt(((X - c) ** 2).sum(axis=1))
            for c in self.centroids
        ])
        return self.classes[distances.argmin(axis=0)]
```

逐层拆开（设测试样本 n 个、类别 k 个、特征 d 维）：

| 表达式 | 形状 | 含义 |
|-------|------|------|
| `X - c` | `(n, d)` | **广播**：每个样本减去同一个质心 `c`（形状 `(d,)`） |
| `(X - c) ** 2` | `(n, d)` | 每一维的差的平方 |
| `.sum(axis=1)` | `(n,)` | 每个样本各维求和 → 平方欧氏距离 |
| `np.sqrt(...)` | `(n,)` | 欧氏距离 |
| 列表推导 + `np.array` | `(k, n)` | 每个质心一行 |
| `.argmin(axis=0)` | `(n,)` | 对每一列（每个样本）找最小距离所在的**行号**，即类别下标 |
| `self.classes[...]` | `(n,)` | 把下标翻译回真实类别值 |

- 为什么最后要 `self.classes[...]`：`argmin` 给的是 0、1、2 这样的**位置**，而真实标签可能是字符串或不连续的整数。用位置去查 `np.unique` 得到的类别表，才能还原出标签。
- 设计取舍：外层用 Python 列表推导遍历质心（k 次），内层用 NumPy 向量化处理所有样本。k 通常很小，这个循环几乎不花时间，同时比三维广播更容易读懂。
- ⚠️ `np.sqrt` 其实可以省掉：开方是单调函数，不改变 argmin 的结果。保留它是为了让"欧氏距离"的含义一目了然。
- ⚠️ 所有特征在距离里地位相同，**没有任何特征缩放**——这正是讲义 Step 4 说的"距离被最大尺度的特征主导"。

### 3.3 `score`：准确率

```python
    def score(self, X, y):
        return np.mean(self.predict(X) == y)
```

`预测 == 真实` 得到布尔数组，`np.mean` 把 True 当 1、False 当 0 求平均，正好就是准确率。这是 NumPy 里极常见的惯用法。

### 3.4 造数据：两个高斯团

```python
def generate_classification_data(n_per_class=100, n_features=2, separation=2.0, seed=42):
    rng = np.random.RandomState(seed)
    center_0 = np.ones(n_features) * (separation / 2)
    center_1 = np.ones(n_features) * (-separation / 2)
    X_class0 = rng.randn(n_per_class, n_features) + center_0
    X_class1 = rng.randn(n_per_class, n_features) + center_1
    X = np.vstack([X_class0, X_class1])
    y = np.array([0] * n_per_class + [1] * n_per_class)
    shuffle_idx = rng.permutation(len(y))
    return X[shuffle_idx], y[shuffle_idx]
```

- 两类分别以 `(+s/2, +s/2, …)` 和 `(−s/2, −s/2, …)` 为中心，每维都是标准正态噪声（标准差 1）。
- `rng = np.random.RandomState(seed)` 创建一个**独立的随机数生成器**，不影响全局随机状态，结果可复现。
- `np.vstack` 把两块 `(n, d)` 竖着拼成 `(2n, d)`；`[0] * n + [1] * n` 是 Python 列表重复与拼接。
- 最后用**同一个** `shuffle_idx` 同时索引 `X` 和 `y`，保证样本和标签仍一一对应。打乱是为了避免"前一半全是类 0"这种顺序偏差。
- ⚠️ 注意 `separation` 是**每一维**上的间距。两个中心之间的欧氏距离其实是 `separation × √d`，维度越高、中心离得越远——这一点对理解 3.7 的高维实验非常关键。
- 这种"各向同性、等协方差的高斯团"恰好是最近质心的理想情况（此时它等价于贝叶斯最优分类器），所以它能表现很好。真实数据很少这么友好。

### 3.5 手写 `train_test_split`

```python
def train_test_split(X, y, test_fraction=0.3, seed=42):
    rng = np.random.RandomState(seed)
    n = len(y)
    idx = rng.permutation(n)
    split = int(n * (1 - test_fraction))
    return X[idx[:split]], X[idx[split:]], y[idx[:split]], y[idx[split:]]
```

- `rng.permutation(n)` 产生 `0..n-1` 的一个随机排列；前 70% 下标给训练集，后 30% 给测试集。
- 返回顺序 `X_train, X_test, y_train, y_test` 与 sklearn 的 `train_test_split` 保持一致，方便以后无缝替换。
- ⚠️ 没有**分层抽样**（stratify）：训练集和测试集的类别比例可能不一样。实际运行中训练集是 111:99、测试集是 39:51，这就是下面多数类基线只有 0.433 的原因。
- ⚠️ 只切了两份（训练/测试），没有验证集。因为最近质心没有超参数要调，两份就够了；有超参数时必须再切出验证集。

### 3.6 两个基线

```python
def random_baseline(y_train, y_test, seed=42):
    rng = np.random.RandomState(seed)
    classes, counts = np.unique(y_train, return_counts=True)
    probs = counts / counts.sum()
    preds = rng.choice(classes, size=len(y_test), p=probs)
    return np.mean(preds == y_test)


def majority_baseline(y_train, y_test):
    values, counts = np.unique(y_train, return_counts=True)
    majority_class = values[np.argmax(counts)]
    preds = np.full(len(y_test), majority_class)
    return np.mean(preds == y_test)
```

- **随机基线**：按训练集中各类的频率随机猜（`rng.choice(..., p=probs)`）。注意它比讲义里 `rng.choice([0, 1], ...)` 的等概率版本多考虑了类别比例，更公平。
- **多数类基线**：永远猜训练集里最多的类。在类别极度不平衡时（比如 99% 正常交易），这个"笨模型"能拿到 99% 准确率——任何模型都必须先打败它。
- 两个基线都**只看训练集标签**来决定策略，再在测试集上评估——与正常模型遵守同样的规则，不偷看测试集。
- `np.unique(..., return_counts=True)` 同时返回类别和计数，`np.full(n, v)` 生成全是 v 的数组。

### 3.7 四个演示

```python
    improvement_over_random = (test_acc - rand_acc) / rand_acc * 100
    print(f"Nearest Centroid beats random baseline by {improvement_over_random:.1f}%")
```

- `demo_nearest_centroid`：输出的是**相对提升**百分比（`(0.967−0.467)/0.467 ≈ 107%`），不是准确率差值的百分点。面试或写报告时要说清用的是哪种。
- `demo_varying_difficulty`：separation 从 0.5 到 5.0，看准确率如何从约 0.64 爬到 1.0——**数据本身的可分性决定了模型的天花板**。
- `demo_higher_dimensions`：维度从 2 到 50，准确率上升到 1.0。原因见 3.4 的 ⚠️：每维间距固定时，中心距离随 `√d` 增大，而每一维的噪声不变，所以越来越好分。代码末尾的提示也很重要：真实数据中多出来的维度往往是噪声，反而会带来维度灾难。
- `demo_multiclass`：三个中心 `[2,0]`、`[-1,1.7]`、`[-1,-1.7]` 大致呈正三角形排布，`* 0.8` 缩小了噪声。算法一行不改就能处理多分类——因为 `np.unique` 和 `argmin` 天然支持任意多个类别。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 选最近质心作为第一个算法 | 没有梯度、没有迭代、没有超参，纯粹展示"学→预测→评估" | 只能画线性边界；生产用 sklearn 的 `NearestCentroid` 或更强模型 |
| 模仿 sklearn 的 `fit/predict/score` 接口 | 学一次接口，后面所有模型通用 | 缺少参数校验、`NotFittedError` 等健壮性处理 |
| 列表推导遍历质心 + 向量化遍历样本 | 可读性好，k 小时性能足够 | 类别多时可改成三维广播或矩阵乘法 |
| 处处 `RandomState(seed=42)` | 结果完全可复现 | 单一种子下的结果有偶然性，严谨实验应多种子取均值 |
| 同时给随机基线和多数类基线 | 判断模型是否"真的学到了东西" | 生产中还要加规则基线、上一个版本模型等作为对照 |
| 不做特征缩放、不分层切分 | 保持代码最短 | 真实项目应标准化（只用训练集统计量）并做分层切分 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import ... as` | `import numpy as np` | 给模块起别名，NumPy 的通用惯例 |
| 函数默认参数 | `def train_test_split(X, y, test_fraction=0.3, seed=42)` | 调用时可以省略，也可按名字覆盖 |
| 多返回值（元组） | `return X[...], X[...], y[...], y[...]` | 实际返回一个元组，调用方用解包接收 |
| 元组解包 | `X_train, X_test, y_train, y_test = train_test_split(X, y)` | 一次给多个变量赋值 |
| `class` / `self` / `None` | `self.classes = None` | 实例属性；`None` 表示"尚未训练" |
| 列表推导式 | `[X[y == c].mean(axis=0) for c in self.classes]` | 一行生成列表，再交给 `np.array` 堆成矩阵 |
| 列表乘法与拼接 | `[0] * n_per_class + [1] * n_per_class` | `*` 重复列表，`+` 拼接列表（不是逐元素运算！） |
| `enumerate` | `for i, c in enumerate(clf.classes)` | 同时拿到下标和元素 |
| f-string 对齐格式符 | `f"{'Method':<25} {train_acc:>10.3f}"` | `<25` 左对齐占 25 格，`>10.3f` 右对齐占 10 格保留 3 位小数，用来打印表格 |
| f-string 整数格式 | `f"{d:>10d}"` | `d` 表示按整数格式化 |
| 字符串乘法 | `"=" * 60` | 重复字符串，打印分隔线 |
| NumPy 布尔掩码 | `X[y == c]` | 用布尔数组选行 |
| NumPy `axis` | `.mean(axis=0)`、`.sum(axis=1)`、`.argmin(axis=0)` | 指定沿哪个维度归约 |
| NumPy 广播 | `X - c`（`(n,d)` 减 `(d,)`） | 形状自动对齐扩展，无需写循环 |
| 整数数组索引 | `X[idx[:split]]`、`self.classes[...argmin...]` | 用下标数组一次取出多行/多个元素 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（`python3 ml_intro.py`，耗时约 0.2 秒）的关键输出：

```text
Dataset: 300 samples, 2 features, 2 classes
Train: 210 samples, Test: 90 samples

Centroids:
  Class 0: [1.037, 1.009]        ← 真实中心是 [1, 1]，样本均值很接近
  Class 1: [-0.977, -1.105]      ← 真实中心是 [-1, -1]

Method                     Train Acc   Test Acc
--------------------------------------------------
Nearest Centroid               0.919      0.967
Random Baseline                   --      0.467
Majority Baseline                 --      0.433

Nearest Centroid beats random baseline by 107.1%
```

- 学到的质心几乎就是真实中心，说明 105 个左右的样本足以把均值估准。
- **测试准确率（0.967）高于训练准确率（0.919）**：不是 bug。测试集只有 90 个样本，一个样本就值 1.1 个百分点，抽样波动很大；模型只有 4 个参数，不可能过拟合。
- 多数类基线（0.433）比随机基线还低：训练集类 0 多（111 vs 99），于是永远猜 0；但测试集里类 0 反而是少数（39 vs 51）。这正是没有分层切分的后果。

```text
  Separation  Train Acc   Test Acc     Random
         0.5      0.671      0.644      0.467
         1.0      0.767      0.756      0.467
         1.5      0.867      0.867      0.467
         2.0      0.919      0.967      0.467
         3.0      0.990      0.989      0.467
         5.0      1.000      1.000      0.467
```

- 间距越大越好分，准确率单调上升到 1.0。
- `Random` 列恒为 0.467：三个函数都固定 `seed=42`，`randn` 的调用次数与 separation 无关，所以打乱后的标签、切分方式、随机猜测全都一模一样。

```text
  Features   Test Acc
         2      0.933
         5      0.992
        10      1.000
        20      1.000
        50      1.000
```

- 维度越高越准：中心距离 `2√d` 随维度增长，噪声却没变。这是"每个新特征都携带有效信号"的理想情况；真实数据里大量特征是噪声时，结论会反过来。

```text
3-class problem: 300 samples
Centroids:
  Class 0: [1.928, 0.031]
  Class 1: [-0.825, 1.684]
  Class 2: [-1.009, -1.826]

Test accuracy: 0.989
Random baseline (1/3): 0.344
```

- 三类问题同样轻松拿到约 99%，随机基线约 1/3。

---

## 7. 动手改一改

1. 把 `predict` 里的 `np.sqrt` 去掉，确认所有准确率都不变，并解释原因。
2. 给 `train_test_split` 加一个 `stratify` 选项：对每个类别分别打乱、分别按比例切分再合并，验证切分后训练/测试的类别比例一致，多数类基线回到约 0.5。
3. 把 `demo_varying_difficulty` 改成对每个 separation 用 5 个不同种子各跑一次，打印均值 ± 标准差，观察随机基线回到 0.5 附近。
4. 给 `generate_classification_data` 的第二个特征乘以 1000 并换成纯噪声，观察准确率跌到接近随机；再加上标准化（训练集统计量）把它救回来。
5. 构造一个"一类有两个簇"的数据集（比如类 0 在 `[3,3]` 和 `[-3,-3]` 两处，类 1 在原点），观察最近质心为何失败——类 0 的质心正好落在类 1 中间。
6. 把 `predict` 改写成三维广播版本 `X[:, None, :] - self.centroids[None, :, :]`，并与原版对比结果完全一致。

---

## 8. 常见坑

- **`axis` 搞反**：距离矩阵是 `(类别数, 样本数)`，必须 `argmin(axis=0)`；写成 `axis=1` 会返回"离每个质心最近的样本下标"，要么 `IndexError`，要么静默给出错误结果。
- **把 `argmin` 的下标当成标签**：标签是 `['cat','dog']` 或 `[3, 7]` 时会全错，必须用 `self.classes[...]` 翻译回去。
- **列表 `*` 不是逐元素乘**：`[0] * 3` 是 `[0, 0, 0]`；想逐元素运算要先转 NumPy 数组。
- **用全量数据算标准化统计量**：会把测试集信息泄漏进模型，评估结果偏乐观。
- **只看一个种子的结果下结论**：0.919 vs 0.967 这种差距在 90 个测试样本上完全可能是噪声。
- **相对提升 vs 绝对提升**：`107%` 是相对随机基线的提升，绝对提升是 50 个百分点，汇报时别混淆。
