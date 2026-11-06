# 代码讲解 · features.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 08 节 Feature 工程与选择 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python features.py`（无命令行参数，瞬间完成） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy / pandas / scikit-learn

---

## 1. 这份代码在考察什么

这份代码把 sklearn 预处理模块里最常用的十几个变换**全部用纯 Python 重写一遍**，然后在一份模拟的房价数据上串成一条完整的特征流水线：

1. **数值变换**：Min-Max、标准化、对数、等宽分箱、二次多项式特征——每个都只有几行，能看清它们到底做了什么。
2. **类别编码**：one-hot、label、带平滑的 target encoding，以及它们各自的风险。
3. **文本特征**：词频向量与 TF-IDF 的完整计算过程。
4. **缺失值处理**：均值/中位数/众数填充 + 缺失指示列。
5. **特征选择**：Pearson 相关、分箱互信息、方差阈值、相关性去冗余。
6. **流水线思维**：缺失 → 变换 → 编码 → 组装特征矩阵 → 选择，对应讲义开头的 Feature Pipeline 流程图。

> 一句话：**每个预处理函数都是"统计一些量 + 套一个公式"**。理解了这一点，就能理解为什么这些"统计量"只能来自训练集——这是数据泄漏问题的根源，而本文件的演示为了简洁恰好没有做训练/测试切分，读的时候要特别留意。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `min_max_scale` / `standardize` / `log_transform` / `bin_values` / `polynomial_features` | 函数 | 数值变换 | 缩放、偏态处理、离散化、特征交互 |
| `one_hot_encode` / `label_encode` / `target_encode` | 函数 | 类别编码，同时返回"编码表" | 类别特征处理 |
| `count_vectorize` / `tfidf` | 函数 | 文本 → 向量，同时返回词表 | 词袋模型、TF-IDF |
| `impute_mean` / `impute_median` / `impute_mode` / `add_missing_indicator` | 函数 | 缺失值填充与指示列 | 缺失值处理 |
| `correlation` / `mutual_information` | 函数 | 特征与目标（或特征之间）的关联度 | 过滤式特征选择 |
| `variance_threshold` / `remove_correlated` | 函数 | 返回保留的特征下标 | 低方差过滤、冗余去除 |
| `make_housing_data` | 函数 | 生成带缺失值的房价数据（字典列表） | 模拟真实表格数据 |
| `if __name__ == "__main__":` | 入口 | 依次演示所有变换并做特征选择 | 端到端流水线 |

数据流：`make_housing_data` → 按列抽出 `sqft`、`age`、`neighborhood`、`price` → 填充缺失 + 指示列 → 缩放 → 编码 → 拼成 7 列的 `feature_matrix` → 方差阈值、相关性过滤 → 逐列计算与目标的互信息和相关系数。文本部分使用一组独立的 5 条房屋描述，没有并入特征矩阵。

注意一个约定：所有函数都**按列**处理（输入是一列值的列表），而不是按行。这和 pandas / sklearn "每次处理一列或几列"的思路一致。

---

## 3. 逐段精讲

### 3.1 缩放与对数：最基础的数值变换

```python
def min_max_scale(values):
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return [0.0] * len(values)
    return [(v - min_val) / (max_val - min_val) for v in values]

def standardize(values):
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(variance) if variance > 0 else 1.0
    return [(v - mean) / std for v in values]

def log_transform(values):
    return [math.log(v + 1) for v in values]
```

| 函数 | 公式 | 结果 | 何时用 |
|------|------|------|-------|
| `min_max_scale` | `(v − min)/(max − min)` | 落在 [0, 1] | 需要有界输入；对离群点敏感 |
| `standardize` | `(v − μ)/σ` | 均值 0、标准差 1 | 距离类、梯度下降类模型的默认选择 |
| `log_transform` | `ln(v + 1)` | 压缩大值 | 收入、人口、计数等右偏分布 |

- **两个除零保护**：常数列 `max == min` 时 Min-Max 返回全 0；方差为 0 时标准化令 `std = 1.0`（结果也是全 0）。常数列没有信息量，后面的方差阈值会把它删掉。
- 标准化用的是**总体方差**（除以 n），与 sklearn `StandardScaler` 一致；统计学里的样本方差除以 n−1，样本量大时差别很小。
- `log(v + 1)` 即 `log1p`：`+1` 让 0 也能取对数。⚠️ 输入 ≤ −1 时会抛 `ValueError`，代码没有处理负值。
- ⚠️ 这些函数只返回变换后的值，**不返回统计量**（`min`、`max`、`mean`、`std`），所以无法用训练集的统计量去变换测试集。对比上一节 KNN 代码中 `standardize` 返回 `(X_scaled, means, stds)` 的设计，以及 sklearn 的 `fit` / `transform` 分离，这里是简化。

### 3.2 分箱与多项式特征

```python
def bin_values(values, n_bins=5):
    min_val = min(values)
    max_val = max(values)
    bin_width = (max_val - min_val) / n_bins
    if bin_width == 0:
        return [0] * len(values)
    result = []
    for v in values:
        bin_idx = int((v - min_val) / bin_width)
        bin_idx = min(bin_idx, n_bins - 1)
        result.append(bin_idx)
    return result
```

- **等宽分箱**：把 `[min, max]` 等分成 `n_bins` 段，`int(...)` 向下取整得到箱号。
- `min(bin_idx, n_bins - 1)`：最大值恰好算出 `n_bins`，越界一格，要并入最后一个箱。例如 `bin_values([0,10,20,30,40,50], 5)` 得到 `[0, 1, 2, 3, 4, 4]`。
- 等宽分箱对偏态数据效果差（大多数样本挤在一两个箱里）；另一种是**等频分箱**（按分位数切，sklearn `KBinsDiscretizer(strategy="quantile")`）。

```python
def polynomial_features(row, degree=2):
    n = len(row)
    result = list(row)
    if degree >= 2:
        for i in range(n):
            result.append(row[i] ** 2)
        for i in range(n):
            for j in range(i + 1, n):
                result.append(row[i] * row[j])
    return result
```

- 注意它处理的是**一行**（一个样本），不是一列：输出 = 原始特征 + 各特征的平方 + 两两乘积。`[x1, x2]` → `[x1, x2, x1², x2², x1·x2]`。
- `j` 从 `i + 1` 开始：只生成 `i < j` 的交互项，避免 `x1·x2` 和 `x2·x1` 重复。
- ⚠️ 只实现了二次：`degree=3` 时的输出和 `degree=2` **完全相同**，参数被静默忽略（讲义写的是 "Creates x^2, x^3, x1*x2 terms"）。生产中用 `sklearn.preprocessing.PolynomialFeatures`。
- 特征数增长：d 个特征的二次展开有 `d + d(d+1)/2` 列，d=100 时就超过 5000 列——这就是讲义说的 "at the cost of more features"，也是 SVM 一节中核技巧要避免的问题。

### 3.3 三种类别编码

```python
def one_hot_encode(values):
    categories = sorted(set(values))
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}
    n_cats = len(categories)

    encoded = []
    for v in values:
        row = [0] * n_cats
        row[cat_to_idx[v]] = 1
        encoded.append(row)

    return encoded, categories

def label_encode(values):
    categories = sorted(set(values))
    cat_to_int = {cat: i for i, cat in enumerate(categories)}
    return [cat_to_int[v] for v in values], cat_to_int
```

- **`sorted(set(values))`**：先去重再排序，保证类别顺序**确定**（`set` 本身无序，不排序的话每次运行列顺序可能不同，训练和推理的列就对不上）。运行结果中顺序是 `['downtown', 'rural', 'suburbs']`（字母序）。
- `cat_to_idx` 是"类别 → 列号"的查找表，用字典推导一行建好。两个函数都把这张表一起返回，推理时必须复用同一张表。
- label encoding 的 `{'downtown': 0, 'rural': 1, 'suburbs': 2}` 只是字母序，与房价高低无关——用在线性模型上就会产生讲义说的"虚假顺序"。
- ⚠️ 推理时遇到训练集中没有的类别，`cat_to_idx[v]` 会抛 `KeyError`。sklearn 的 `OneHotEncoder(handle_unknown="ignore")` 会把它编码为全 0 行。

```python
def target_encode(feature_values, target_values, smoothing=10):
    global_mean = sum(target_values) / len(target_values)

    category_stats = {}
    for feat, target in zip(feature_values, target_values):
        if feat not in category_stats:
            category_stats[feat] = {"sum": 0.0, "count": 0}
        category_stats[feat]["sum"] += target
        category_stats[feat]["count"] += 1

    encoding = {}
    for cat, stats in category_stats.items():
        cat_mean = stats["sum"] / stats["count"]
        weight = stats["count"] / (stats["count"] + smoothing)
        encoding[cat] = weight * cat_mean + (1 - weight) * global_mean

    return [encoding[v] for v in feature_values], encoding
```

- **两遍扫描**：第一遍累计每个类别的目标和与计数，第二遍算出平滑后的编码。
- **平滑公式**：`encoding = w·类别均值 + (1 − w)·全局均值`，`w = n/(n + smoothing)`。样本少的类别被拉向全局均值，避免"某类只有 1 个样本、恰好很贵"导致编码极端。这是讲义 Further Reading 中 Micci-Barreca 方法的思想。
- 嵌套字典 `{"sum": ..., "count": ...}` 让代码可读性更好（也可用两个并行字典或 `defaultdict`）。
- ⚠️ 演示中 `target_encode(neighborhoods, prices, ...)` 在**全部 200 行**上计算，且没有任何训练/测试切分。真实项目中必须只在训练集上计算，而且训练集内部还要用 K 折或留一法（测验 Q11）来避免"自己的标签参与自己的编码"。

### 3.4 文本特征：词频与 TF-IDF

```python
def tfidf(documents):
    n_docs = len(documents)

    vocab = {}
    idx = 0
    for doc in documents:
        for word in doc.lower().split():
            if word not in vocab:
                vocab[word] = idx
                idx += 1

    doc_freq = {}
    for doc in documents:
        seen = set()
        for word in doc.lower().split():
            if word not in seen:
                doc_freq[word] = doc_freq.get(word, 0) + 1
                seen.add(word)

    vectors = []
    for doc in documents:
        words = doc.lower().split()
        word_count = len(words)
        tf_map = {}
        for word in words:
            tf_map[word] = tf_map.get(word, 0) + 1

        vec = [0.0] * len(vocab)
        for word, count in tf_map.items():
            tf = count / word_count
            idf = math.log(n_docs / doc_freq[word])
            vec[vocab[word]] = tf * idf
        vectors.append(vec)

    return vectors, vocab
```

三遍扫描，各司其职：

1. **建词表**：`lower().split()` 做最简单的分词（小写 + 按空白切分），按首次出现的顺序给每个词分配列号。
2. **统计文档频率 df**：每篇文档用一个 `seen` 集合保证同一个词**在同一篇中只计一次**——df 数的是"多少篇文档包含它"，不是总出现次数。
3. **算 TF-IDF**：`TF = 词在本篇的次数/本篇总词数`，`IDF = ln(N/df)`，两者相乘填入对应列。

- `count_vectorize` 是同一套建词表逻辑，只保留第 3 步的计数部分。
- 为什么 TF-IDF 优于原始词频：在全部文档中都出现的词（如 "with"）IDF 小，只在少数文档出现的词（如 "pool"）IDF 大，向量突出"这篇文档的特色"。
- ⚠️ 简化：没有去标点、停用词、词干化；出现在所有文档中的词 IDF 恰好为 0；推理时遇到词表外的新词会 `KeyError`；没有对文档向量做 L2 归一化（sklearn 默认会做）。
- 建词表的代码在两个函数中重复了一遍，工程上应抽成一个函数。

### 3.5 缺失值处理

```python
def impute_median(values):
    present = sorted(v for v in values if v is not None)
    if not present:
        return [0.0] * len(values), 0.0
    n = len(present)
    if n % 2 == 0:
        median = (present[n // 2 - 1] + present[n // 2]) / 2
    else:
        median = present[n // 2]
    return [v if v is not None else median for v in values], median

def add_missing_indicator(values):
    return [0 if v is not None else 1 for v in values]
```

- 缺失值用 Python 的 `None` 表示，判断一律用 `is not None`（不能用 `!= None`，也不能用 `if v`——后者会把 0 当成缺失）。
- **中位数**：排序后取中间；偶数个时取中间两个的平均。`n // 2` 是整除。
- 每个填充函数都返回 `(填充后的列, 填充值)`：填充值要保存下来，用于推理时填充新数据——这里比缩放函数设计得更好。
- `impute_mode` 用字典计数 + `max(counts, key=counts.get)` 求众数，适合类别特征；全部缺失时原样返回（仍含 `None`）。
- **顺序很重要**：演示中先 `add_missing_indicator(sqft_raw)`，再 `impute_median(sqft_raw)`——填充之后就分不清哪些是原本缺失的了。
- 演示中 `sqft` 用中位数、`age` 用均值，正好对照讲义："median is more robust to outliers"。需要提醒的是：均值/中位数填充会在填充值处形成一个"尖峰"、缩小方差，并不能保持原分布形状。

### 3.6 相关系数与互信息

```python
def correlation(x, y):
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / n
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x) / n)
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y) / n)
    if std_x == 0 or std_y == 0:
        return 0.0
    return cov / (std_x * std_y)
```

Pearson 相关 `r = cov(x, y)/(σx·σy)`，取值 [−1, 1]，只度量**线性**关系。常数列的标准差为 0，约定返回 0。

```python
def mutual_information(feature, target, n_bins=10):
    feat_min = min(feature)
    feat_max = max(feature)
    bin_width = (feat_max - feat_min) / n_bins if feat_max != feat_min else 1.0
    feat_binned = [
        min(int((f - feat_min) / bin_width), n_bins - 1) for f in feature
    ]
    # ...
    mi = 0.0
    for b in feat_bins:
        for t in target_classes:
            joint_count = sum(
                1 for fb, tv in zip(feat_binned, target) if fb == b and tv == t
            )
            p_joint = joint_count / n
            if p_joint > 0:
                mi += p_joint * math.log(p_joint / (p_feat[b] * p_target[t]))

    return mi
```

- **思路**：互信息定义在离散变量上，所以先把连续特征**等宽分箱**（复用 `bin_values` 的逻辑），再用频率估计 `p(x)`、`p(y)`、`p(x, y)`，套公式 `I(X;Y) = Σ p(x,y)·log(p(x,y)/(p(x)·p(y)))`。
- `if p_joint > 0`：`0·log 0` 按约定取 0，跳过可以避免 `log(0)` 报错。
- 用的是自然对数，单位是 nats。二分类目标的互信息上限是 `ln 2 ≈ 0.693`（特征完全决定目标时）。
- 二值特征（0/1）分箱后落在第 0 箱和第 9 箱，计算照样正确。
- ⚠️ 结果依赖箱数：箱太多时每箱样本很少，互信息会被高估。`joint_count` 每次都重新扫描全部数据，复杂度 `O(箱数 × 类别数 × n)`，用一次遍历建列联表会更高效。
- 演示中目标是 `binary_prices`：价格高于均值记 1，否则记 0——把回归问题转成二分类，才能使用这个只支持离散目标的实现。

### 3.7 方差阈值与相关性去冗余

```python
def variance_threshold(features, threshold=0.01):
    # ...
    for j in range(n_features):
        col = [features[i][j] for i in range(n_samples)]
        mean = sum(col) / n_samples
        var = sum((v - mean) ** 2 for v in col) / n_samples
        if var >= threshold:
            selected.append(j)
    return selected

def remove_correlated(features, threshold=0.9):
    # ...
    to_remove = set()
    for i in range(n_features):
        if i in to_remove:
            continue
        col_i = [features[r][i] for r in range(n_samples)]
        for j in range(i + 1, n_features):
            if j in to_remove:
                continue
            col_j = [features[r][j] for r in range(n_samples)]
            corr = abs(correlation(col_i, col_j))
            if corr >= threshold:
                to_remove.add(j)

    return [i for i in range(n_features) if i not in to_remove]
```

- 两个函数都返回**保留下来的列下标**，而不是新矩阵——调用方可以据此同时筛选特征名、训练集和测试集。
- `[features[i][j] for i in range(n_samples)]`：从"行列表"中取出第 j 列。
- **方差阈值**：二值特征的方差是 `p(1−p)`，例如缺失率 3% 的指示列方差约 0.029，仍高于 0.01 被保留。注意方差的大小与特征尺度有关：标准化后的列方差都恰好是 1，阈值对它们毫无作用（本例 `sqft` 就是如此）；Min-Max 后的列方差取决于分布形状。所以方差阈值最适合用在同尺度的特征（如 0/1 二值特征）上，或者在缩放前按各列量纲分别设定阈值。
- **贪心去冗余**：按列顺序扫描，与第 i 列高度相关（`|r| ≥ 0.9`）的后续列被删除，**保留靠前的那一个**。`to_remove` 用集合存储，`in` 判断是 `O(1)`。
- ⚠️ 只看两两相关：三个 one-hot 列加起来恒等于 1，是完全共线的，但两两之间的相关系数只有约 −0.5，所以一个都不会被删（测验 Q12）。

### 3.8 模拟数据与主流程

```python
        sqft_with_missing = sqft if random.random() > 0.05 else None
        age_with_missing = age if random.random() > 0.08 else None

        price = (
            50 * sqft
            + 20000 * bedrooms
            - 1000 * age
            + (50000 if neighborhood == "downtown" else 10000 if neighborhood == "suburbs" else 0)
            + (15000 if has_pool else 0)
            + random.gauss(0, 20000)
        )
```

- 价格由一个**已知的线性公式**加噪声生成：每平方英尺 +50、每间卧室 +20000、房龄每年 −1000、市中心 +50000、郊区 +10000、泳池 +15000。知道真实公式，才能判断特征选择的结果是否合理。
- 缺失是**完全随机**的（约 5% 和 8%），所以缺失指示列理论上不该与价格有关——运行结果也印证了这一点（见第 6 节）。
- 价格用的是**真实的** `sqft` 和 `age`，缺失只发生在"观测"上。
- 链式条件表达式 `A if c1 else B if c2 else C` 从左到右判断，等价于 if/elif/else。
- 注意 `bedrooms` 和 `has_pool` 影响价格，但没有被放进 `feature_matrix`——它们的影响会变成模型看不到的"噪声"。

```python
    feature_matrix = [
        [sqft_scaled[i], age_scaled[i], float(sqft_indicator[i]), float(age_indicator[i])]
        + ohe[i]
        for i in range(len(data))
    ]
```

用列表拼接 `+` 把数值特征、指示列和 one-hot 列拼成一行，共 `2 + 2 + 3 = 7` 列——这一步相当于 sklearn 的 `ColumnTransformer` 把多个子流水线的输出横向拼接。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 每个变换一个小函数、按列处理 | 每个公式一眼可见，便于对照讲义 | sklearn 用统一的 `fit` / `transform` 接口，可放进 `Pipeline` |
| 缩放函数不返回统计量 | 代码最短 | 无法复用到测试集；应返回参数或做成带 `fit` 的类 |
| 编码函数返回编码表 | 推理时可以复用 | 还需处理未见类别（`handle_unknown`） |
| 全量数据上做所有统计 | 演示简单 | 数据泄漏；先切分，只在训练集上 fit |
| target encoding 只做平滑 | 讲清核心公式 | 训练集内部仍有自我泄漏；用 K 折 / 留一法 |
| TF-IDF 用 `ln(N/df)`、按空白分词 | 与讲义公式一致 | sklearn 默认平滑 IDF + L2 归一化 + 正则分词 |
| 互信息用等宽分箱估计 | 只需计数 | 对箱数敏感；sklearn 对连续特征用 k 近邻估计 |
| 相关性去冗余只看两两 | 简单直观 | 发现不了多列共线；可用 VIF 或矩阵条件数 |
| 多项式特征只实现二次 | 足够演示交互项 | `degree` 参数名不副实；用 `PolynomialFeatures` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `None` 与 `is not None` | `[v if v is not None else median for v in values]` | 用 `None` 表示缺失；判断必须用 `is`，不能用 `if v`（0 也是假值） |
| 条件表达式 | `std = math.sqrt(variance) if variance > 0 else 1.0` | 三元表达式 |
| 链式条件表达式 | `50000 if ... == "downtown" else 10000 if ... == "suburbs" else 0` | 相当于 if / elif / else |
| `set` 去重 + `sorted` | `categories = sorted(set(values))` | 得到确定顺序的唯一值列表 |
| 字典推导 | `{cat: i for i, cat in enumerate(categories)}` | 一行构建"类别 → 下标"映射 |
| `dict.get(key, 默认值)` | `doc_freq.get(word, 0) + 1` | 计数的惯用写法 |
| 嵌套字典 | `category_stats[feat]["sum"] += target` | 每个类别存一组统计量 |
| `dict.items()` | `for cat, stats in category_stats.items()` | 同时遍历键和值 |
| `max(..., key=dict.get)` | `max(counts, key=counts.get)` | 找出值最大的键（众数） |
| `set` 的 `add` / `in` | `seen.add(word)`、`if j in to_remove` | `O(1)` 的成员判断 |
| 字符串方法 | `doc.lower().split()` | 转小写后按空白切分 |
| 整除与取余 | `n // 2`、`n % 2 == 0` | 求中位数位置、判断奇偶 |
| 列表拼接 | `[...] + ohe[i]` | 两个列表首尾相接成新列表 |
| `sorted` 的 `key` 与 `reverse` | `sorted(tf_vocab.keys(), key=lambda w: tf[0][tf_vocab[w]], reverse=True)[:3]` | 按 TF-IDF 值降序取前 3；排序是稳定的 |
| 生成器表达式计数 | `sum(1 for v in sqft_raw if v is None)` | 统计满足条件的元素个数 |
| `list.count` | `feat_binned.count(b)` | 统计某个值出现的次数 |
| `round` | `{k: round(v) for k, v in te_map.items()}` | 不给位数时四舍五入为整数 |
| f-string 格式符 | `f"{sqft_fill:.0f}"`、`f"MI={mi:.4f}"` | `.0f` 不保留小数，`.4f` 保留 4 位 |
| 多返回值 | `sqft_imputed, sqft_fill = impute_median(sqft_raw)` | 函数返回元组，调用处解包 |

---

## 6. 运行结果解读

实际运行：在临时副本目录执行 `python3 features.py`，耗时不到 0.1 秒，结果固定可复现。

**① 缺失值**

```text
  sqft missing: 6/200
  age missing: 20/200
  sqft filled with median: 2753
  age filled with mean: 25.2
```

缺失比例约 3% 和 10%，与生成时的 5%、8% 量级一致（随机波动）。`sqft` 在 `uniform(500, 5000)` 上的理论中位数是 2750，实测 2753；`age` 在 `uniform(0, 50)` 上的理论均值是 25，实测 25.2。

**② 数值变换**

```text
  sqft standardized: mean=-0.0000, std=1.0000
  age min-max: [0.00, 1.00]
  age bins: [0, 1, 2, 3, 4]
```

标准化后均值为 0（`-0.0000` 是浮点误差造成的负零显示）、标准差为 1；Min-Max 后范围正好是 [0, 1]；5 个箱都有样本。

**③ 类别编码**

```text
  One-hot categories: ['downtown', 'rural', 'suburbs']
  Sample encoding: downtown -> [1, 0, 0]
  Label encoding map: {'downtown': 0, 'rural': 1, 'suburbs': 2}
  Target encoding: {'downtown': 228152, 'suburbs': 188042, 'rural': 190398}
```

- 市中心的编码明显最高，符合生成公式中 +50000 的设定。
- 有意思的是：郊区（+10000）的编码反而略低于农村（+0）。原因是 target encoding 只看**边际均值**——每个类别里房子的面积、房龄、卧室数分布不同，加上 σ=20000 的噪声，约 60～70 个样本的均值差异会掩盖 10000 的真实效应。这说明 target encoding 编码的是"这个类别的平均目标"，不是"这个类别的独立贡献"。

**④ 文本特征**

```text
  Vocabulary size: 21
  Doc 0 non-zero features: 5
  Doc 0 top TF-IDF words: ['house', 'pool', 'large']
```

5 篇描述共 21 个不同的词；第 0 篇 5 个词各出现一次。`house`、`pool` 只出现在第 0 篇，TF-IDF 最高（0.3219）；`large` 与 `modern` 并列第三（0.1833），由于排序稳定、`large` 先进入词表而排在前面；`with` 出现在 3 篇中，权重只有 0.1022。

**⑤ 多项式特征**

```text
  Input: [0.475, 0.7427]
  Polynomial: [0.475, 0.7427, 0.2257, 0.5517, 0.3528]
```

`0.475² ≈ 0.2257`，`0.7427² ≈ 0.5517`，`0.475 × 0.7427 ≈ 0.3528`，与 `[x1, x2, x1², x2², x1·x2]` 一一对应。

**⑥ 特征选择**

```text
  Total features: 7
  After variance threshold (0.01): 7 features kept
  After correlation filter (0.9): 7 features kept

  Mutual information with target:
    sqft: MI=0.3886
    age: MI=0.0358
    sqft_missing: MI=0.0000
    age_missing: MI=0.0020
    neigh_downtown: MI=0.0158

  Correlation with price:
    sqft: r=0.8196
    age: r=-0.2578
    sqft_missing: r=0.0609
    age_missing: r=-0.0761
    neigh_downtown: r=0.2639
    neigh_rural: r=-0.1145
    neigh_suburbs: r=-0.1482
```

- 两个过滤器都没删任何特征：所有列方差都 > 0.01；没有两两相关 ≥ 0.9 的列（one-hot 的完全共线是多列关系，见 3.7）。
- **sqft 是最强特征**（MI 0.39、r 0.82）：生成公式中面积贡献的方差最大（`50 × 4500` 的取值范围，约 22.5 万）。
- **age 负相关**（r = −0.26），符合 −1000/年的设定。
- **缺失指示列几乎无用**（MI ≈ 0、|r| < 0.08）：因为缺失是完全随机生成的。这正好提醒：指示列只在"缺失本身有含义"时才有价值，不能无脑添加。
- **市中心为正、另两类为负**：one-hot 列与价格的相关反映的是"和其他类别相比"的效应。

---

## 7. 动手改一改

1. **Robust Scaling**（讲义练习 1）：实现 `robust_scale(values)`，用中位数和四分位距（IQR）代替均值和标准差；在 `sqft` 中插入几个 `1e6` 的极端值，对比三种缩放后其余数据的分布范围。
2. **fit / transform 分离**：把 `standardize` 改写为 `fit_standardize(values) -> (mean, std)` 和 `transform_standardize(values, mean, std)`，先切分 160/40，再只用训练集拟合。
3. **留一法 target encoding**（讲义练习 2）：实现 `loo_target_encode`，并加一列唯一 ID，对比朴素编码与留一法编码和价格的相关系数（预期 1.0 vs 0）。
4. **真正的多项式特征**：让 `polynomial_features` 支持任意 `degree`（提示：`itertools.combinations_with_replacement(range(n), d)` 枚举所有 d 次单项式）。
5. **VIF 检测共线**：对 7 列特征矩阵，逐列以其余列为自变量做最小二乘回归，计算 `VIF = 1/(1 − R²)`，观察三个 one-hot 列的 VIF。
6. **自动特征选择流水线**（讲义练习 3）：把 `bedrooms`、`has_pool` 也加入特征矩阵，串联方差阈值 → 相关性过滤 → 按互信息排序取前 k 个，用简单线性回归比较全部特征与选择后特征的测试误差。

---

## 8. 常见坑

- **在全量数据上拟合预处理**：本文件为了演示在 200 行全量数据上算中位数、均值、标准差和目标均值；真实项目中这会把测试集信息泄漏进训练。
- **`if v:` 判断缺失**：0、0.0、空字符串都是"假值"，会被误当成缺失；必须写 `v is not None`。
- **类别顺序不固定**：用 `list(set(values))` 而不排序，每次运行列顺序可能不同，模型上线后特征错位。
- **推理时出现新类别 / 新词**：`one_hot_encode` 和 `tfidf` 会 `KeyError`；要么预留"未知"类别，要么使用支持 `handle_unknown` 的实现。
- **先填充、后加指示列**：填充之后已经不知道哪些值原本缺失，指示列全为 0。
- **只用两两相关去冗余**：发现不了 one-hot 的完全共线等多列关系；线性模型要去掉一个基准列或加正则。
- **相信 `degree` 参数**：`polynomial_features(..., degree=3)` 不会生成三次项，阅读别人的代码时要核实参数是否真的生效。
