# 代码讲解 · pipeline.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 13 节 机器学习管道 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python pipeline.py`（无命令行参数，依次运行 9 个演示） ｜ **依赖**：`numpy`（必需）；`demo_sklearn_pipeline` 额外需要 `scikit-learn` 和 `pandas`，没装 sklearn 时会打印 "sklearn not installed, skipping." 并跳过

---

## 1. 这份代码在考察什么

这份 650 多行的脚本，先用 NumPy 从零手写一整套"迷你 sklearn"，再用真正的 sklearn 重做一遍。目的是让你看清 pipeline 这个抽象到底解决了什么问题：

1. **fit / transform 契约**：每个预处理器都是"fit 时学统计量、transform 时只用统计量"的有状态对象，这是防止泄漏的根基。
2. **Pipeline 的执行顺序**：训练时前面的步骤 `fit_transform`、最后的模型 `fit`；预测时前面的步骤只 `transform`。
3. **数据泄漏**：亲手对比"先全量缩放再切分"和"先切分再缩放"两种写法。
4. **按列分流的预处理**：数值列填补 + 标准化，类别列独热编码，最后拼接，也就是 ColumnTransformer 的思想。
5. **交叉验证 + pipeline 工厂**：每折新建 pipeline，只在训练折上 fit。
6. **工程习惯**：未知类别不崩溃、手动实验记录、固定随机种子保证可复现。

> 一句话：**模型不是产品，pipeline 才是**。这份代码教你把"从原始数据到预测"的每一步装进一个能整体 fit、整体复用的对象里。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `make_mixed_data` / `train_test_split_dict` | 函数 | 生成含缺失值的数值 + 类别混合数据（字典形式），并随机切分 | 真实表格数据的缩影 |
| `MedianImputer` / `StandardScaler` / `OneHotEncoder` | 类 | 三个手写预处理器，都实现 `fit / transform / fit_transform` | sklearn 的 transformer 接口 |
| `PipelineFromScratch` | 类 | 若干 transformer + 末尾一个模型 | `sklearn.pipeline.Pipeline` |
| `TransformerPipeline` | 类 | 只由 transformer 组成的链（没有模型），本身也是 transformer | Pipeline 嵌套 |
| `ColumnTransformerScratch` | 类 | 不同列走不同子 pipeline 再横向拼接（定义了但演示中没用到） | `ColumnTransformer` |
| `FullPipeline` | 类 | 把"数值分支 + 类别分支 + 模型"写死在一起，吃字典、吐预测 | 完整生产 pipeline |
| `LogisticRegressionSimple` / `DecisionTreeSimple` | 类 | 两个极简模型，供 pipeline 末端使用 | 第 03、04 节的模型 |
| `cross_validate_pipeline` | 函数 | 手写 K 折交叉验证，接收 pipeline **工厂函数** | 每折独立 fit，防泄漏 |
| `demo_*`（9 个） | 函数 | 泄漏对比、从零 pipeline、混合数据、CV、未知类别、模型对比、sklearn 版、实验记录、可复现性 | 讲义各小节 |

数据流：`make_mixed_data` 产出字典 → `FullPipeline.fit` 从字典中按列名取出数值块和类别块 → 数值块走 `TransformerPipeline(MedianImputer → StandardScaler)`，类别块走 `OneHotEncoder` → `np.hstack` 拼成特征矩阵 → 交给模型。`cross_validate_pipeline` 在外层反复执行"切分 → 新建 → fit → score"。

---

## 3. 逐段精讲

### 3.1 造数据：故意带缺失值的混合类型表格

```python
def make_mixed_data(n_samples=500, seed=42):
    rng = np.random.RandomState(seed)

    age = rng.normal(35, 12, n_samples).clip(18, 80)
    income = rng.lognormal(10.5, 0.8, n_samples)
    score = rng.uniform(300, 850, n_samples)
    # ...
    plan = rng.choice(plans, n_samples, p=[0.5, 0.3, 0.2])

    mask = rng.random(n_samples) < 0.05
    age_with_missing = age.copy()
    age_with_missing[mask] = np.nan
    # ...
    boundary = (
        0.01 * (age - 35)
        + 0.00001 * (income - 40000)
        + 0.002 * (score - 600)
        + 0.5 * (plan == "premium").astype(float)
        - 0.3 * (plan == "free").astype(float)
        + rng.normal(0, 0.5, n_samples)
    )
    target = (boundary > 0).astype(int)
```

- 三个数值列故意用三种分布：年龄近似正态并截断到 [18, 80]，收入是**对数正态**（长尾、量级在几万），信用分是均匀分布。量级差异巨大，正好说明为什么需要标准化。
- `age` 约 5%、`income` 约 3% 被设成 `NaN`，模拟真实数据的缺失。注意：标签 `boundary` 是用**没挖空的** `age`、`income` 算的，相当于"真实世界里值存在，只是我们没采集到"。
- 标签由线性组合 + 高斯噪声决定，`city` **完全不参与**——它是一个纯噪声特征，模型如果在它上面切分就是在过拟合。
- 返回的是 `dict[str, np.ndarray]`，模拟 DataFrame 的"按列名取列"。

```python
def train_test_split_dict(data, test_ratio=0.2, seed=42):
    rng = np.random.RandomState(seed)
    n = len(data["target"])
    idx = rng.permutation(n)
    split = int(n * (1 - test_ratio))
    train_idx, test_idx = idx[:split], idx[split:]

    train = {k: v[train_idx] for k, v in data.items()}
    test = {k: v[test_idx] for k, v in data.items()}
    return train, test
```

- 先生成一个随机排列 `idx`，再对**每一列用同一组下标**取子集，保证同一行的各列不会错位。这就是字典推导式 `{k: v[train_idx] for k, v in data.items()}` 的作用。
- ⚠️ 简化：没有分层抽样（stratify），类别比例在两边可能略有差异；这里标签约 50/50，影响不大。

### 3.2 三个手写 transformer：fit 学状态，transform 用状态

```python
class MedianImputer:
    def __init__(self):
        self.medians = None

    def fit(self, X):
        self.medians = np.nanmedian(X, axis=0)
        return self

    def transform(self, X):
        X_out = X.copy()
        for col in range(X.shape[1]):
            mask = np.isnan(X_out[:, col])
            X_out[mask, col] = self.medians[col]
        return X_out

    def fit_transform(self, X):
        return self.fit(X).transform(X)
```

- **状态只在 `fit` 里产生**：`self.medians` 是训练数据每列的中位数（`np.nanmedian` 计算时跳过 NaN）。`transform` 无论喂进来的是训练集还是测试集，都用这份训练中位数填补——这正是"测试数据不参与统计"的实现方式。
- `fit` 返回 `self`，所以 `fit_transform` 可以写成链式调用 `self.fit(X).transform(X)`，与 sklearn 的约定一致。
- `X.copy()` 保证不修改调用方的数组（防御式编程）；`X_out[mask, col] = ...` 是**布尔掩码赋值**。

```python
class StandardScaler:
    def fit(self, X):
        self.means = np.nanmean(X, axis=0)
        self.stds = np.nanstd(X, axis=0)
        self.stds[self.stds == 0] = 1.0
        return self

    def transform(self, X):
        return (X - self.means) / self.stds
```

- `(X - means) / stds` 利用**广播**：`X` 是 (n, d)，`means` 是 (d,)，自动按列相减。
- `self.stds[self.stds == 0] = 1.0`：常数列标准差为 0，直接除会得到 `inf/NaN`，改成 1 后该列变成全 0，安全无害。
- 用 `nanmean / nanstd` 让它即使放在填补之前也能 fit；但 transform 时 NaN 仍会原样传下去。⚠️ 所以顺序必须是"先填补、后缩放"。

```python
class OneHotEncoder:
    def __init__(self, handle_unknown="ignore"):
        self.categories = None
        self.handle_unknown = handle_unknown

    def fit(self, X):
        self.categories = []
        for col in range(X.shape[1]):
            self.categories.append(sorted(set(X[:, col])))
        return self

    def transform(self, X):
        encoded_cols = []
        for col in range(X.shape[1]):
            cats = self.categories[col]
            for cat in cats:
                encoded_cols.append((X[:, col] == cat).astype(float))
        return np.column_stack(encoded_cols) if encoded_cols else np.zeros((X.shape[0], 0))
```

- `fit` 为每列记录一张**排好序的**类别表。`sorted` 很关键：`set` 对字符串的迭代顺序受哈希随机化影响，不排序的话每次运行列顺序可能不同，模型权重就对不上号了。
- `transform` 对每个已知类别生成一列 0/1。未知类别和所有已知类别都不相等，自然得到全零行——"handle unknown = ignore"其实是这种写法**天然具备**的行为。
- 输出列数只由 fit 时的类别表决定，这保证了训练和推理的特征维度一致。
- ⚠️ `handle_unknown` 参数被保存了但**从未被使用**：传 `"error"` 也不会报错。真实 sklearn 的默认值是 `"error"`。
- ⚠️ 每个类别做一次整列比较，复杂度 O(n × 类别数)，高基数列（几万个取值）会很慢且很稀疏；sklearn 默认输出稀疏矩阵就是为此。

### 3.3 `PipelineFromScratch`：Pipeline 的全部秘密就这十几行

```python
class PipelineFromScratch:
    def __init__(self, steps):
        self.steps = steps

    def fit(self, X, y=None):
        X_current = X.copy() if isinstance(X, np.ndarray) else X
        for name, step in self.steps[:-1]:
            X_current = step.fit_transform(X_current)
        name, model = self.steps[-1]
        model.fit(X_current, y)
        return self

    def predict(self, X):
        X_current = X.copy() if isinstance(X, np.ndarray) else X
        for name, step in self.steps[:-1]:
            X_current = step.transform(X_current)
        name, model = self.steps[-1]
        return model.predict(X_current)
```

- `steps` 是 `[(名字, 对象), ...]` 列表，和 sklearn 的格式一模一样。`self.steps[:-1]` 是除最后一个外的所有 transformer，`self.steps[-1]` 是模型。
- **fit 与 predict 唯一的区别就是 `fit_transform` 与 `transform`**。如果 `predict` 里误用 `fit_transform`，单样本预测时 scaler 会把每个样本标准化成全 0（测验 Q9 有实测）。
- 每一步的输出就是下一步的输入，整个链条像流水线一样逐级传递。
- 和讲义 "Build It · Step 2" 的片段相比，实际代码多了 `isinstance(X, np.ndarray)` 判断：只有 ndarray 才 `.copy()`，以便将来也能接受字典等其他输入。

`TransformerPipeline` 是同一个思路，只是**每一步都是 transformer**、没有模型，并且自己也实现了 `fit / transform / fit_transform`。于是它可以被当成一个普通 transformer 嵌套进别的结构里——`FullPipeline` 的数值分支就是这么用的。这体现了 sklearn 设计里的**组合模式**：一串 transformer 组合起来，仍然是一个 transformer。

### 3.4 按列分流：`ColumnTransformerScratch` 与 `FullPipeline`

```python
class ColumnTransformerScratch:
    def __init__(self, transformers):
        self.transformers = transformers

    def fit(self, data):
        for name, pipeline, columns in self.transformers:
            X_subset = np.column_stack([data[c] for c in columns])
            pipeline.fit(X_subset)
        return self

    def transform(self, data):
        outputs = []
        for name, pipeline, columns in self.transformers:
            X_subset = np.column_stack([data[c] for c in columns])
            outputs.append(pipeline.transform(X_subset))
        return np.hstack(outputs)
```

- 三元组 `(名字, 子 pipeline, 列名列表)` 与 sklearn `ColumnTransformer` 的参数格式一致。对每组列取子矩阵、各自 fit/transform，再用 `np.hstack` 横向拼接。
- ⚠️ 这个类在所有演示里**都没有被用到**，真正跑的是下面这个把两条分支写死的 `FullPipeline`：

```python
class FullPipeline:
    def __init__(self, model, numeric_cols, categorical_cols):
        self.model = model
        self.numeric_cols = numeric_cols
        self.categorical_cols = categorical_cols
        self.num_pipeline = TransformerPipeline([
            ("impute", MedianImputer()),
            ("scale", StandardScaler()),
        ])
        self.cat_encoder = OneHotEncoder(handle_unknown="ignore")

    def fit(self, data):
        X_num = np.column_stack([data[c] for c in self.numeric_cols])
        X_cat = np.column_stack([data[c] for c in self.categorical_cols])

        X_num_processed = self.num_pipeline.fit_transform(X_num)
        X_cat_processed = self.cat_encoder.fit_transform(X_cat)

        X = np.hstack([X_num_processed, X_cat_processed])
        y = data["target"]

        self.model.fit(X, y)
        return self
```

- `np.column_stack([data[c] for c in cols])` 把若干个一维列拼成 (n, k) 矩阵。数值块是 float，类别块是字符串数组，必须分开处理，不能混在一个 ndarray 里。
- 预处理后的列数：3 个数值 + `city` 5 个 + `plan` 3 个 = 11 列。
- `predict` 与 `fit` 结构完全对称，只是把 `fit_transform` 换成 `transform`、`model.fit` 换成 `model.predict`。
- 列名通过构造参数传入，而不是在类里硬编码——对应讲义 "Hardcoded column names → Use column name lists from config"。
- ⚠️ 类别分支没有做缺失值填补（本数据集的类别列没有缺失）；讲义和 sklearn 版本中有 `SimpleImputer(strategy="most_frequent")`。

### 3.5 两个极简模型（了解即可）

```python
    def fit(self, X, y):
        n_samples, n_features = X.shape
        self.weights = np.zeros(n_features)
        self.bias = 0.0

        for _ in range(self.n_iter):
            z = X @ self.weights + self.bias
            pred = self._sigmoid(z)
            dw = (1 / n_samples) * X.T @ (pred - y)
            db = (1 / n_samples) * np.sum(pred - y)
            self.weights -= self.lr * dw
            self.bias -= self.lr * db
```

- `LogisticRegressionSimple` 是批量梯度下降，梯度 `Xᵀ(p − y)/n` 就是交叉熵损失对权重的导数（第 03 节）。`_sigmoid` 里 `np.clip(z, -500, 500)` 防止 `exp` 溢出。
- **因为它用梯度下降，所以对特征尺度敏感**：未缩放时 `income`（几万）的梯度会压倒其他特征。这正是 pipeline 里要放 `StandardScaler` 的理由。
- `DecisionTreeSimple` 用 Gini 不纯度、每个特征只试 10 个分位点阈值（`np.percentile(X[:, f], np.linspace(10, 90, 10))`），节点用字典表示，递归预测。树对特征尺度不敏感，放在 scaler 后面只是为了统一接口。
- ⚠️ `LogisticRegressionSimple.fit` 没有 `return self`，不能链式调用 `.fit(...).predict(...)`；pipeline 不依赖返回值，所以不受影响。
- ⚠️ 叶子值用 `round(np.mean(y))`，Python 的 `round` 是"银行家舍入"，0.5 会舍到 0。

### 3.6 `cross_validate_pipeline`：每一折都是一个全新的 pipeline

```python
def cross_validate_pipeline(pipeline_factory, data, n_folds=5, seed=42):
    rng = np.random.RandomState(seed)
    n = len(data["target"])
    idx = rng.permutation(n)
    fold_size = n // n_folds
    scores = []

    for fold in range(n_folds):
        val_start = fold * fold_size
        val_end = val_start + fold_size if fold < n_folds - 1 else n

        val_idx = idx[val_start:val_end]
        train_idx = np.concatenate([idx[:val_start], idx[val_end:]])

        train_data = {k: v[train_idx] for k, v in data.items()}
        val_data = {k: v[val_idx] for k, v in data.items()}

        pipe = pipeline_factory()
        pipe.fit(train_data)
        score = pipe.score(val_data)
        scores.append(score)

    return scores
```

- 先整体打乱一次，再按位置切成 K 段；最后一折 `val_end = n`，把除不尽的余数样本也收进来。
- `np.concatenate([idx[:val_start], idx[val_end:]])` = "除验证段以外的所有下标"。
- **核心是 `pipe = pipeline_factory()`**：每折调用工厂新建一个未 fit 的 pipeline，于是中位数、均值、类别表、模型参数全部只来自这一折的训练部分。这就是讲义说的 "Cross-validation applies the pipeline per fold"。sklearn 的 `cross_val_score` 用 `clone(estimator)` 实现同一件事。
- `seed` 控制切分方式；同样的 seed → 同样的折 → 同样的分数（见 3.9）。

### 3.7 `demo_data_leakage`：同一个模型，两种缩放方式

```python
    scaler_leaky = StandardScaler()
    X_scaled_leaky = scaler_leaky.fit_transform(X)
    X_train_leaky = X_scaled_leaky[:160]
    X_test_leaky = X_scaled_leaky[160:]
    # ...
    X_train = X[:160]
    X_test = X[160:]
    scaler_clean = StandardScaler()
    X_train_clean = scaler_clean.fit_transform(X_train)
    X_test_clean = scaler_clean.transform(X_test)
```

- 泄漏版：scaler 在全部 200 行上 fit，均值和标准差里包含了 40 条测试样本。
- 干净版：只在前 160 行 fit，测试集用训练统计量 transform。
- 在这个"5 维标准正态"的玩具数据上，两组统计量几乎相同，所以实测差异是 `+0.000`。代码里的打印也坦白了这一点：缩放泄漏通常很小，**真正危险的是 target encoding、特征选择这类会用到标签的泄漏**。演示的意义在于把"正确写法"刻进肌肉记忆。

### 3.8 模型对比与手动实验记录：默认参数绑定的技巧

```python
    for name, model_fn in models:
        def make_pipe(m=model_fn):
            return FullPipeline(
                model=m(),
                numeric_cols=["age", "income", "score"],
                categorical_cols=["city", "plan"],
            )

        scores = cross_validate_pipeline(make_pipe, data, n_folds=5)
        print(f"  {name:>25s}:  {np.mean(scores):.3f} +/- {np.std(scores):.3f}")
```

- `models` 里存的是 `lambda: DecisionTreeSimple(max_depth=3)` 这样的**模型工厂**，再被包进 pipeline 工厂 `make_pipe`，两层工厂保证每折拿到的都是全新模型。
- `def make_pipe(m=model_fn)` 和 `demo_experiment_tracking` 里的 `lambda c=config: ...`，用的都是"**默认参数在定义时求值**"的技巧，用来躲开闭包的延迟绑定陷阱。在本代码里工厂会在当轮循环内被立即调用，所以不加也不会出错，但这是值得养成的防御习惯（测验 Q10 有演示）。
- `demo_experiment_tracking` 用一个字典列表 `experiments` 记录 `run_id / config / mean_accuracy / std_accuracy`，最后 `max(experiments, key=lambda e: e["mean_accuracy"])` 选最佳。这就是 MLflow 的"手工版"：参数 + 指标 + 运行编号。真实项目中还应记录代码版本、数据版本和模型制品。

### 3.9 sklearn 版与可复现性检查

```python
    numeric_pipe = SkPipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", SkScaler()),
    ])

    cat_pipe = SkPipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("encode", SkOHE(handle_unknown="ignore", sparse_output=False)),
    ])

    preprocessor = SkColumnTransformer([
        ("num", numeric_pipe, ["age", "income", "score"]),
        ("cat", cat_pipe, ["city", "plan"]),
    ])

    full_pipe = SkPipeline([
        ("preprocess", preprocessor),
        ("model", GradientBoostingClassifier(n_estimators=100, max_depth=3)),
    ])

    scores = cross_val_score(full_pipe, df, y, cv=5, scoring="accuracy")
```

手写版与 sklearn 版的对照：

| 手写 | sklearn | 备注 |
|------|---------|------|
| `MedianImputer` | `SimpleImputer(strategy="median")` | |
| `StandardScaler` | `sklearn.preprocessing.StandardScaler` | 同名，所以 sklearn 版被重命名为 `SkScaler` |
| `OneHotEncoder` | `OneHotEncoder(handle_unknown="ignore", sparse_output=False)` | `sparse_output=False` 返回稠密数组；该参数名是 sklearn 1.2 起的写法 |
| `FullPipeline` 的两条分支 | `ColumnTransformer` | 按列名路由，需要 pandas DataFrame |
| `cross_validate_pipeline` | `cross_val_score(..., cv=5)` | 分类任务下 `cv=5` 默认是分层 K 折 |

- `import pandas as pd` 写在 `try` 块之后：如果装了 sklearn 却没装 pandas，这里会直接抛 `ImportError`。
- `demo_reproducibility` 用同一个 seed 跑两次 CV，结果逐折相等；换 seed=99 后切分不同、分数不同。判断相等用的是 `abs(a-b) < 1e-10`，而不是 `==`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 所有预处理器统一 `fit / transform / fit_transform` 接口 | pipeline 只依赖接口，不关心具体是什么变换（鸭子类型） | 生产中继承 `sklearn.base.BaseEstimator, TransformerMixin`，自动获得 `get_params`、`clone` 支持 |
| `fit` 返回 `self` | 支持链式调用 `fit(X).transform(X)` | 两个手写模型的 `fit` 没遵守，属于不一致 |
| 数据用 `dict[str, ndarray]` 表示 | 不依赖 pandas，也能按列名取列 | 真实项目用 DataFrame，配合 `ColumnTransformer` |
| CV 接收工厂函数而不是对象 | 强制每折新建，杜绝状态跨折残留 | sklearn 用 `clone()` 自动完成 |
| `FullPipeline` 写死两条分支 | 代码直白，便于初学者跟踪 | 通用写法是 `ColumnTransformerScratch` / sklearn `ColumnTransformer` |
| 未知类别输出零向量 | 线上不因新类别崩溃 | 应同时监控未知类别比例；高基数列考虑合并低频类、哈希编码 |
| 手动 list 记录实验 | 展示实验追踪的本质 | 用 MLflow / wandb 记录参数、指标、制品、代码与数据版本 |
| 所有随机性用 `RandomState(seed)` | 结果可复现 | 还需锁依赖、DVC 版本化数据、配置文件化超参 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import` 与警告过滤 | `warnings.filterwarnings("ignore")` | 屏蔽所有警告，让演示输出干净；正式代码中慎用，可能掩盖真实问题 |
| 类与 `__init__` | `class MedianImputer: def __init__(self): self.medians = None` | 用 `None` 占位，表示"尚未 fit" |
| 返回 `self` 实现链式调用 | `return self.fit(X).transform(X)` | `fit` 返回对象本身，后面可以接着调方法 |
| 切片取"除最后一个外" | `self.steps[:-1]`、`self.steps[-1]` | 负索引从末尾数 |
| `for` 中的元组解包 | `for name, step in self.steps`、`for name, pipeline, columns in self.transformers` | 每个元素是元组，直接拆成多个变量 |
| 字典推导式 | `{k: v[train_idx] for k, v in data.items()}` | 对字典的每个键值对做变换，生成新字典 |
| 列表推导式 | `[data[c] for c in columns]` | 按列名列表取出若干列 |
| 条件表达式 | `X.copy() if isinstance(X, np.ndarray) else X` | 一行的 if/else |
| `isinstance` | `isinstance(X, np.ndarray)` | 运行时判断类型 |
| NumPy 布尔掩码 | `X_out[mask, col] = self.medians[col]`、`y[X[:, f] <= t]` | 用 True/False 数组选出或修改元素 |
| NumPy 拼接 | `np.column_stack`、`np.hstack`、`np.concatenate` | 按列拼一维数组 / 横向拼矩阵 / 拼接一维下标 |
| `RandomState` 随机数 | `rng.permutation(n)`、`rng.choice(plans, n, p=[...])` | 独立的随机数生成器，按概率 `p` 抽样 |
| `.astype` | `(plan == "premium").astype(float)` | 布尔数组转成 0/1 数值 |
| 字典表示树节点 + 递归 | `{"feature": ..., "left": self._build(...)}`、`if "value" in node` | 用 `in` 判断键是否存在来区分叶子 |
| 嵌套函数（闭包） | 在 `demo_cross_validation` 里 `def make_pipeline(): ...` | 函数里定义函数，可访问外层变量 |
| lambda 与默认参数绑定 | `lambda c=config: DecisionTreeSimple(max_depth=c["max_depth"])` | 默认参数在定义时求值，避免闭包延迟绑定 |
| `max(..., key=...)` | `max(experiments, key=lambda e: e["mean_accuracy"])` | 按指定字段取最大的元素 |
| `all` + 生成器 | `all(abs(a-b) < 1e-10 for a,b in zip(run1, run2))` | 全部满足才为 True |
| f-string 格式符 | `f"{name:>25s}"`、`f"{acc_leaky - acc_clean:+.3f}"`、`f"{exp['run_id']:>4d}"` | `>25s` 右对齐占 25 宽；`+.3f` 强制带正负号；`>4d` 整数右对齐 |
| f-string 里的列表推导 | `[f'{s:.3f}' for s in scores]` | 内外引号要不同（外双内单） |
| `try / except ImportError` | sklearn 导入失败时打印提示并 `return` | 可选依赖的标准写法 |
| `if __name__ == "__main__":` | 文件末尾依次调用 9 个 demo | 直接运行时才执行演示，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（NumPy 2.x + scikit-learn 1.9 + pandas，约 6 秒）：

```text
DATA LEAKAGE DEMONSTRATION
  Leaky (scaler fit on all data):    0.925
  Clean (scaler fit on train only):  0.925
  Difference:                        +0.000      ← 玩具数据上缩放泄漏几乎无影响

PIPELINE FROM SCRATCH
  Train accuracy: 0.992
  Test accuracy:  0.967                          ← 线性可分的数据，逻辑回归表现很好

FULL PIPELINE WITH MIXED DATA TYPES
  Train accuracy: 0.812
  Test accuracy:  0.680                          ← 深度 5 的树有明显过拟合（差 13 个点）

CROSS-VALIDATION WITH PIPELINE
  5-fold CV scores: ['0.720', '0.730', '0.740', '0.750', '0.680']
  Mean: 0.724 +/- 0.024                          ← 比单次切分更可靠的估计

HANDLING UNKNOWN CATEGORIES
  Known categories: [np.str_('chicago'), np.str_('houston'), np.str_('la'), np.str_('new_york')]
  'new_york' encoded: [0. 0. 0. 1.]              ← 按字母序排，new_york 在最后
  'seattle' (unknown) encoded: [0. 0. 0. 0.]     ← 未知类别 → 零向量

MODEL COMPARISON VIA PIPELINE
        Logistic Regression:  0.756 +/- 0.017
          Decision Tree d=3:  0.684 +/- 0.054
          Decision Tree d=5:  0.724 +/- 0.024
         Decision Tree d=10:  0.684 +/- 0.078   ← 太浅欠拟合、太深过拟合，方差也最大

SKLEARN PIPELINE (if installed)
  5-fold CV: 0.742 +/- 0.012
  Pipeline steps: ['preprocess', 'model']
  Preprocessor transformers: ['num', 'cat']

EXPERIMENT TRACKING (manual log)
     5  {'model': 'logistic', 'lr': 0.1, 'n_iter       0.758     0.012
  Best run: #5

REPRODUCIBILITY CHECK
  Run 1 == Run 2: True                           ← 同 seed 完全一致
  Run 1 == Run 3: False                          ← 换 seed，切分不同
```

解读要点：

- **逻辑回归赢了树**：标签本来就是特征的线性组合加噪声，线性模型的归纳偏置与数据生成过程吻合；树只能用阶梯逼近斜线边界，还会在纯噪声特征 `city` 上切分。
- **单次切分 vs 交叉验证**：同一个深度 5 的树，单次测试集是 0.680，5 折均值是 0.724，各折之间相差 7 个点——小数据上单次切分的随机性很大，这就是要做 CV 的原因。
- **深度 10 的标准差最大（0.078）**：越复杂的模型对训练数据越敏感，方差越高，与第 10 节偏差-方差权衡一致。
- `Known categories` 一行显示为 `np.str_('chicago')`，是 NumPy 2.x 改变了标量的 `repr` 所致，不是 bug；用 `list(map(str, ...))` 打印会更干净。
- 实验记录表里 `config_str = str(exp["config"])[:40]` 截断了过长的配置，所以第 4、5 行看到的是 `'n_ite`、`'n_iter`。

---

## 7. 动手改一改

1. **补上 `handle_unknown="error"`**：让 `OneHotEncoder.transform` 在 `"error"` 模式下遇到未知类别抛 `ValueError`，并用 `demo_unknown_categories` 验证两种模式。
2. **让 `FullPipeline` 用上 `ColumnTransformerScratch`**：把写死的两条分支改成 `ColumnTransformerScratch([("num", TransformerPipeline([...]), numeric_cols), ("cat", OneHotEncoder(), categorical_cols)])`，确认 CV 分数完全不变。
3. **放大泄漏**：在 `demo_data_leakage` 里加一步"在全量数据上按与标签的相关性选出 top-2 特征"，并把特征数从 5 增加到 500（大部分是纯噪声），对比泄漏版和干净版的差距。
4. **给类别分支加众数填补**：写一个 `MostFrequentImputer`，处理类别列中的缺失值（如 `None` 或空字符串），放在 `OneHotEncoder` 之前。
5. **序列化验证**：用 `pickle` 或 `joblib` 保存 fit 好的 `FullPipeline`，在新进程中加载，对测试集预测，断言结果与保存前逐元素相等。
6. **嵌套交叉验证**：在 `cross_validate_pipeline` 外面再套一层，内层在训练折上从 `max_depth ∈ {3, 5, 10}` 中选最优，外层报告分数，与 `demo_model_comparison` 中"直接取最大值"的结果比较。

---

## 8. 常见坑

- **测试集上调用 `fit_transform`**：等于用测试数据重新估计统计量，既是泄漏又是训练/推理不一致；单样本推理时会把所有特征变成 0。
- **先预处理、后交叉验证**：在 CV 外面 fit 的任何东西（缩放、填补、特征选择、目标编码）都会泄漏验证折的信息。
- **跨折复用同一个 pipeline 对象**：一旦有状态残留（增量学习、缓存），就会把上一折的信息带进下一折；用工厂函数或 `clone`。
- **类别表不排序**：用 `set` 的迭代顺序决定列顺序，不同进程间列顺序可能不同，加载旧模型后特征错位却不会报错。
- **NaN 进了 scaler 的 transform**：`nanmean` 只保证 fit 不出错，transform 时 NaN 原样流向模型；填补必须放在缩放之前。
- **循环里定义闭包/lambda**：不用默认参数绑定的话，循环结束后再调用会全部用到最后一个值。
