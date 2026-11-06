<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="feature-engineering--selection"></a>

# Feature 工程与选择

> 一个好的 feature 相当于一千个数据点。

**类型：** 构建
**语言：** Python
**先决条件：** 第 1 阶段（ML 统计、线性代数）、第 2 阶段第 1-7 课
**时间：** ~90 分钟

<a id="learning-objectives"></a>

## 学习目标

- 实施数值变换（标准化、最小-最大缩放、对数变换、分箱）并解释每种变换何时适用
- 为分类features构建one-hot、标签和目标编码，并识别目标编码中的data leakage风险
- 从头开始构建 TF-IDF 向量化器并解释为什么它在文本分类方面优于原始字数统计
- 应用基于过滤器的 feature 选择（方差阈值、相关性、互信息）来降低维度

<a id="the-problem"></a>

## 问题

你有一个数据集。你选择一个算法。你训练它。结果很平庸。您尝试更高级的算法。还是很平庸。您花了一周时间调整 hyperparameters。边际改善。

然后有人将原始数据转换为更好的 features，并且简单的逻辑回归击败了经过调整的 gradient 增强的整体。

这种情况经常发生。在经典机器学习中，数据的表示比算法的选择更重要。无论学习者多么老练，包含“平方英尺”和“卧室数量”的房价模型都会击败包含“地址作为原始字符串”的模型。该算法只能与您提供的内容一起工作。

Feature 工程是将原始数据转换为表示形式的过程，使模型更容易找到模式。 Feature选择就是丢弃features添加噪声而不添加信号的过程。它们共同构成了经典机器学习中影响力最高的活动。

<a id="the-concept"></a>

## 概念

<a id="the-feature-pipeline"></a>

### Feature 管道

```mermaid
flowchart LR
    A[Raw Data] --> B[Handle Missing Values]
    B --> C[Numerical Transforms]
    B --> D[Categorical Encoding]
    B --> E[Text Features]
    C --> F[Feature Interactions]
    D --> F
    E --> F
    F --> G[Feature Selection]
    G --> H[Model-Ready Data]
```

<a id="numerical-features"></a>

### 数值 Features

原始数据很少可以用于模型。常见变换：

**Scaling:** 将 features 放在同一范围内，以便基于距离的算法（K-Means、KNN、SVM）平等对待所有 features。最小-最大缩放映射到 [0、1]。标准化（z 分数）映射到平均值 = 0，标准差 = 1。

**Log 变换：** 压缩右偏分布（收入、人口、字数）。将乘法关系转变为加法关系。

**Binning:** 将连续值转换为类别。当 feature 和目标之间的关系是非线性但逐步的（例如年龄组）时很有用。

**多项式 features:** 创建 x^2、x^3、x1*x2 项。让线性模型以更多 features 为代价捕获非线性关系。

<a id="categorical-features"></a>

### 分类 Features

模型需要数字。类别需要编码。

**One-hot 编码：** 为每个类别创建一个二进制列。 “颜色=红/蓝/绿”变为三列：is_red、is_blue、is_green。对于低基数 features 效果很好，但在许多类别中会爆炸。

**标签编码：** 将每个类别映射到一个整数：红色=0，蓝色=1，绿色=2。引入错误排序（模型可能认为绿色 > 蓝色 > 红色）。仅适用于根据单个值进行分割的基于树的模型。

**目标编码：** 将每个类别替换为该类别的目标变量的平均值。强大但危险：data leakage的高风险。必须仅根据训练数据进行计算并应用于测试数据。

<a id="text-features"></a>

### 短信Features

**Count 矢量化器：** 计算每个单词在文档中出现的次数。 “猫坐在垫子上”变成 {the: 2, cat: 1, sat: 1, on: 1, mat: 1}。

**TF-IDF:** 词频-逆文档频率。根据单词在文档中的独特程度来衡量单词的权重。像“the”这样的常用词的值很低 weight。稀有、独特的单词获得较高的 weight。

```
TF(word, doc) = count(word in doc) / total words in doc
IDF(word) = log(total docs / docs containing word)
TF-IDF = TF * IDF
```

<a id="missing-values"></a>

### 缺失值

真实的数据有漏洞。策略：

- **Drop rows:** 仅当缺失数据很少且随机时
- **均值/中位数插补：** 简单，保留分布形状（中位数对异常值更稳健）
- **模式插补：** 对于分类 features
- **指示列：** 在插补之前添加二进制列“was_this_missing”。数据缺失这一事实本身就可以提供信息
- **正向/反向填充：** 用于时间序列数据

<a id="feature-interaction"></a>

### Feature互动

有时，关系在于组合。单独使用“身高”和“weight”的预测能力低于“BMI = weight / height^2”。 Feature 交互乘以 feature 空间，因此请使用领域知识来选择正确的交互。

<a id="feature-selection"></a>

### Feature选型

更多 features 并不总是更好。不相关的 features 添加噪声，增加训练时间，并可能导致 overfitting。

**过滤方法（预型号）：**
- 相关性：去掉features 彼此高度相关（多余）
- 互信息：衡量了解 feature 在多大程度上减少了目标的不确定性
- 方差阈值：删除几乎没有变化的 features

**包装方法（基于模型）：**
- L1 正则化（Lasso）：将不相关的 feature weights 驱动到恰好为零
- 递归feature消除：训练，删除最不重要的feature，重复

**为什么选择很重要：** 具有 10 个良好 features 的模型通常会优于具有 10 个良好 features 和 90 个噪声模型的模型。嘈杂的 features 使模型有机会过度拟合不可泛化的训练数据模式。

```figure
feature-scaling
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-numerical-transforms-from-scratch"></a>

### 第 1 步：从头开始进行数值变换

```python
import math


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

<a id="step-2-categorical-encoding-from-scratch"></a>

### 第 2 步：从头开始分类编码

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

<a id="step-3-text-features-from-scratch"></a>

### 步骤 3：从头开始发短信 features

```python
def count_vectorize(documents):
    vocab = {}
    idx = 0
    for doc in documents:
        for word in doc.lower().split():
            if word not in vocab:
                vocab[word] = idx
                idx += 1

    vectors = []
    for doc in documents:
        vec = [0] * len(vocab)
        for word in doc.lower().split():
            vec[vocab[word]] += 1
        vectors.append(vec)

    return vectors, vocab


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

<a id="step-4-missing-value-imputation-from-scratch"></a>

### 步骤 4：从头开始缺失值插补

```python
def impute_mean(values):
    present = [v for v in values if v is not None]
    if not present:
        return [0.0] * len(values), 0.0
    mean = sum(present) / len(present)
    return [v if v is not None else mean for v in values], mean


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


def impute_mode(values):
    present = [v for v in values if v is not None]
    if not present:
        return values, None
    counts = {}
    for v in present:
        counts[v] = counts.get(v, 0) + 1
    mode = max(counts, key=counts.get)
    return [v if v is not None else mode for v in values], mode


def add_missing_indicator(values):
    return [0 if v is not None else 1 for v in values]
```

<a id="step-5-feature-selection-from-scratch"></a>

### 第五步：从头开始选择Feature

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


def mutual_information(feature, target, n_bins=10):
    feat_min = min(feature)
    feat_max = max(feature)
    bin_width = (feat_max - feat_min) / n_bins if feat_max != feat_min else 1.0
    feat_binned = [
        min(int((f - feat_min) / bin_width), n_bins - 1) for f in feature
    ]

    n = len(feature)
    target_classes = sorted(set(target))

    feat_bins = sorted(set(feat_binned))
    p_feat = {}
    for b in feat_bins:
        p_feat[b] = feat_binned.count(b) / n

    p_target = {}
    for t in target_classes:
        p_target[t] = target.count(t) / n

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


def variance_threshold(features, threshold=0.01):
    n_features = len(features[0])
    n_samples = len(features)
    selected = []

    for j in range(n_features):
        col = [features[i][j] for i in range(n_samples)]
        mean = sum(col) / n_samples
        var = sum((v - mean) ** 2 for v in col) / n_samples
        if var >= threshold:
            selected.append(j)

    return selected


def remove_correlated(features, threshold=0.9):
    n_features = len(features[0])
    n_samples = len(features)

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

<a id="step-6-full-pipeline-and-demo"></a>

### 第 6 步：完整流程和演示

```python
import random


def make_housing_data(n=200, seed=42):
    random.seed(seed)
    data = []
    for _ in range(n):
        sqft = random.uniform(500, 5000)
        bedrooms = random.choice([1, 2, 3, 4, 5])
        age = random.uniform(0, 50)
        neighborhood = random.choice(["downtown", "suburbs", "rural"])
        has_pool = random.choice([True, False])

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

        data.append({
            "sqft": sqft_with_missing,
            "bedrooms": bedrooms,
            "age": age_with_missing,
            "neighborhood": neighborhood,
            "has_pool": has_pool,
            "price": price,
        })
    return data


if __name__ == "__main__":
    data = make_housing_data(200)

    print("=== Raw Data Sample ===")
    for row in data[:3]:
        print(f"  {row}")

    sqft_raw = [d["sqft"] for d in data]
    age_raw = [d["age"] for d in data]
    prices = [d["price"] for d in data]

    print("\n=== Missing Value Handling ===")
    sqft_missing = sum(1 for v in sqft_raw if v is None)
    age_missing = sum(1 for v in age_raw if v is None)
    print(f"  sqft missing: {sqft_missing}/{len(sqft_raw)}")
    print(f"  age missing: {age_missing}/{len(age_raw)}")

    sqft_indicator = add_missing_indicator(sqft_raw)
    age_indicator = add_missing_indicator(age_raw)
    sqft_imputed, sqft_fill = impute_median(sqft_raw)
    age_imputed, age_fill = impute_mean(age_raw)
    print(f"  sqft filled with median: {sqft_fill:.0f}")
    print(f"  age filled with mean: {age_fill:.1f}")

    print("\n=== Numerical Transforms ===")
    sqft_scaled = standardize(sqft_imputed)
    age_scaled = min_max_scale(age_imputed)
    sqft_log = log_transform(sqft_imputed)
    age_binned = bin_values(age_imputed, n_bins=5)
    print(f"  sqft standardized: mean={sum(sqft_scaled)/len(sqft_scaled):.4f}, std={math.sqrt(sum(v**2 for v in sqft_scaled)/len(sqft_scaled)):.4f}")
    print(f"  age min-max: [{min(age_scaled):.2f}, {max(age_scaled):.2f}]")
    print(f"  age bins: {sorted(set(age_binned))}")

    print("\n=== Categorical Encoding ===")
    neighborhoods = [d["neighborhood"] for d in data]

    ohe, ohe_cats = one_hot_encode(neighborhoods)
    print(f"  One-hot categories: {ohe_cats}")
    print(f"  Sample encoding: {neighborhoods[0]} -> {ohe[0]}")

    le, le_map = label_encode(neighborhoods)
    print(f"  Label encoding map: {le_map}")

    te, te_map = target_encode(neighborhoods, prices, smoothing=10)
    print(f"  Target encoding: {({k: round(v) for k, v in te_map.items()})}")

    print("\n=== Text Features ===")
    descriptions = [
        "large modern house with pool",
        "small cozy cottage near downtown",
        "spacious family home with large yard",
        "modern apartment downtown with view",
        "rustic cabin in rural area",
    ]
    cv, cv_vocab = count_vectorize(descriptions)
    print(f"  Vocabulary size: {len(cv_vocab)}")
    print(f"  Doc 0 non-zero features: {sum(1 for v in cv[0] if v > 0)}")

    tf, tf_vocab = tfidf(descriptions)
    print(f"  TF-IDF vocabulary size: {len(tf_vocab)}")
    top_words = sorted(tf_vocab.keys(), key=lambda w: tf[0][tf_vocab[w]], reverse=True)[:3]
    print(f"  Doc 0 top TF-IDF words: {top_words}")

    print("\n=== Polynomial Features ===")
    sample_row = [sqft_scaled[0], age_scaled[0]]
    poly = polynomial_features(sample_row, degree=2)
    print(f"  Input: {[round(v, 4) for v in sample_row]}")
    print(f"  Polynomial: {[round(v, 4) for v in poly]}")
    print(f"  Features: [x1, x2, x1^2, x2^2, x1*x2]")

    print("\n=== Feature Selection ===")
    feature_matrix = [
        [sqft_scaled[i], age_scaled[i], float(sqft_indicator[i]), float(age_indicator[i])]
        + ohe[i]
        for i in range(len(data))
    ]

    print(f"  Total features: {len(feature_matrix[0])}")

    surviving_var = variance_threshold(feature_matrix, threshold=0.01)
    print(f"  After variance threshold (0.01): {len(surviving_var)} features kept")

    surviving_corr = remove_correlated(feature_matrix, threshold=0.9)
    print(f"  After correlation filter (0.9): {len(surviving_corr)} features kept")

    binary_prices = [1 if p > sum(prices) / len(prices) else 0 for p in prices]
    print("\n  Mutual information with target:")
    feature_names = ["sqft", "age", "sqft_missing", "age_missing"] + [f"neigh_{c}" for c in ohe_cats]
    for j in range(len(feature_matrix[0])):
        col = [feature_matrix[i][j] for i in range(len(feature_matrix))]
        mi = mutual_information(col, binary_prices, n_bins=10)
        print(f"    {feature_names[j]}: MI={mi:.4f}")

    print("\n  Correlation with price:")
    for j in range(len(feature_matrix[0])):
        col = [feature_matrix[i][j] for i in range(len(feature_matrix))]
        corr = correlation(col, prices)
        print(f"    {feature_names[j]}: r={corr:.4f}")
```

<a id="use-it"></a>

## 实际应用

使用 scikit-learn，这些转换是可组合的管道：

```python
from sklearn.preprocessing import StandardScaler, OneHotEncoder, PolynomialFeatures
from sklearn.impute import SimpleImputer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import mutual_info_classif, VarianceThreshold
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

numeric_pipe = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
])

categorical_pipe = Pipeline([
    ("encoder", OneHotEncoder(sparse_output=False)),
])

preprocessor = ColumnTransformer([
    ("num", numeric_pipe, ["sqft", "age"]),
    ("cat", categorical_pipe, ["neighborhood"]),
])
```

从头开始的版本准确地显示了每个转换内部发生的情况。库版本添加了边缘情况处理、稀疏矩阵支持和管道组合，但数学原理是相同的。

<a id="ship-it"></a>

## 交付成果

本课产生：
- `outputs/prompt-feature-engineer.md` - 用于根据原始数据系统地设计 features 的 prompt

<a id="exercises"></a>

## 练习

1. 将稳健的缩放（使用中位数和四分位数范围而不是平均值和标准差）添加到数值变换中。将其与具有极端异常值的数据的标准缩放进行比较。
2. 实现留一法目标编码：对于每一行，计算目标均值，排除该行自己的目标值。展示与朴素目标编码相比，这如何减少 overfitting。
3. 构建一个结合方差阈值、相关过滤和互信息排序的自动化 feature 选择管道。将其应用于住房数据集，并比较所有 features 与选定的 features 的模型性能（使用简单线性回归）。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| Feature工程 | “制作新专栏” | 将原始数据转换为向模型公开模式的表示形式 |
| 标准化 | “让它变得正常” | 减去平均值并除以标准差，因此 feature 的平均值 = 0 且 std = 1 |
| 独热编码 | “制作虚拟变量” | 为每个类别创建一个二进制列，其中每行恰好有一列为 1 |
| 目标编码 | “使用答案进行编码” | 将每个类别替换为该类别的平均目标值，并进行平滑以防止 overfitting |
| TF-IDF | “花哨的字数” | 词频乘以逆文档频率：根据词在整个语料库中的独特程度进行加权 |
| 插补 | “填空” | 用估计值（平均值、中位数、众数或模型预测）替换缺失值 |
| Feature精选 | “扔掉坏专栏” | 删除添加噪声或冗余的 features，仅保留那些有目标信号的 |
| 互信息 | “一件事告诉你多少关于另一件事的信息” | 通过观察变量 X 获得的变量 Y 不确定性减少的度量 |
| Data leakage | “一不小心就被骗了” | 在训练期间使用在预测时无法获得的信息，给出错误乐观的结果 |

<a id="further-reading"></a>

## 进一步阅读

- [Feature 工程与选择 (Max Kuhn & Kjell Johnson)](http://www.feat.engineering/) - 免费在线书籍，涵盖 feature 工程的全部内容
- [scikit-learn 预处理指南](https://scikit-learn.org/stable/modules/preprocessing.html) - 所有标准转换的实用参考
- [Target Encoding Done Right (Micci-Barreca, 2001)](https://dl.acm.org/doi/10.1145/507533.507538) - 关于平滑目标编码的原始论文
