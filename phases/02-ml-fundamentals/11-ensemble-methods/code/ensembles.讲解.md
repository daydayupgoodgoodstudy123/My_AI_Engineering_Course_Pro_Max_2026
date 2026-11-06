# 代码讲解 · ensembles.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 11 节 集成方法 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python ensembles.py`（无命令行参数，约 30 秒） ｜ **依赖**：`numpy`（必需）；`scikit-learn`（可选，仅最后的对比演示使用，未安装时自动跳过）。另 `import` 了标准库 `collections.Counter`，但文件中并未使用

---

## 1. 这份代码在考察什么

这份文件用不到 500 行纯 NumPy 代码，把讲义里四大类集成方法都从零实现了一遍：

1. **AdaBoost**：带样本权重的决策树桩 + 权重更新公式，看"弱学习器如何叠加成强学习器"。
2. **Gradient Boosting**：自己写一棵按方差下降分裂的回归树，再让每棵树拟合残差，看训练/测试误差随树的数量的变化。
3. **Bagging**：bootstrap 采样 + 平均投票，看方差如何被压低。
4. **Stacking**：用手写 K 折生成 out-of-fold 元特征，训练一个元学习器去"决定信任谁"。
5. **工程对照**：最后与 sklearn 的实现做对比。

> 一句话：**集成的核心不是某个复杂的模型，而是"怎么组合"**——是并行地平均（bagging），还是串行地纠错（boosting），还是再学一层（stacking）。读完要能说清每种组合方式在偏差-方差上分别做了什么。同时，这份代码里有几个很有代表性的小 bug（平局 `sign(0)`、循环变量泄漏、sklearn API 变更），下文会一一指出。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `make_classification_data` / `make_regression_data` | 函数 | 生成非线性的合成数据（分类标签为 ±1） | 实验数据 |
| `train_test_split` | 函数 | 打乱后 80/20 划分 | Hold-out |
| `DecisionStump` | 类 | 单次分裂的树，支持样本权重和极性 | AdaBoost 的弱学习器 |
| `AdaBoostScratch` | 类 | 重加权 + 加权投票 | Boosting（指数损失） |
| `TreeNode` / `SimpleRegressionTree` | 类 | 递归建树，按方差下降选分裂 | CART 回归树 |
| `GradientBoostingScratch` | 类 | 每棵树拟合残差，乘学习率累加 | Gradient Boosting |
| `BaggingClassifier` | 类 | bootstrap 训练多棵树，平均后取符号 | Bagging |
| `StackingClassifier` | 类 | K 折生成元特征 → 训练元学习器 → 全量重训基模型 | Stacking |
| `demo_*`（7 个） | 函数 | 分别演示上述方法及与 sklearn 对比 | — |

依赖关系：`AdaBoostScratch` → `DecisionStump`；`GradientBoostingScratch`、`BaggingClassifier`、stacking 的 `TreeWrapper` → `SimpleRegressionTree` → `TreeNode`。分类任务统一使用 **±1 标签**，这让 AdaBoost 的 `y·h(x)` 和 "回归树均值取符号" 两种写法都很自然。

---

## 3. 逐段精讲

### 3.1 数据：非线性边界 + ±1 标签

```python
def make_classification_data(n_samples=300, n_features=5, noise=0.1, seed=42):
    rng = np.random.RandomState(seed)
    X = rng.randn(n_samples, n_features)
    boundary = 0.5 * X[:, 0] + 0.3 * X[:, 1] ** 2 - 0.2 * X[:, 2]
    y = np.where(boundary + rng.normal(0, noise, n_samples) > 0, 1, -1)
    return X, y
```

- 边界里有 `X[:, 1] ** 2` 这个**二次项**，单个树桩或线性模型都无法完美表示——这样才看得出集成的价值。
- 第 4、5 个特征与标签无关，是噪声特征。
- `np.where(cond, 1, -1)` 生成 ±1 标签。因为二次项恒非负，正类偏多：实测约 67% 为 +1。所以**"全部预测 +1" 就有约 67% 的准确率**，看后面的准确率时要以此为基线。
- `train_test_split` 用 `rng.permutation` 打乱下标后切分，并返回 `X_train, X_test, y_train, y_test`（与 sklearn 顺序一致）。

### 3.2 `DecisionStump`：带权重的单次分裂

```python
    def fit(self, X, y, weights):
        n_samples, n_features = X.shape
        best_error = float("inf")

        for f in range(n_features):
            thresholds = np.unique(X[:, f])
            for thresh in thresholds:
                for polarity in [1, -1]:
                    pred = np.ones(n_samples)
                    pred[polarity * X[:, f] < polarity * thresh] = -1
                    error = np.sum(weights[pred != y])
                    if error < best_error:
                        best_error = error
                        self.feature_idx = f
                        self.threshold = thresh
                        self.polarity = polarity
```

- **暴力搜索**：每个特征 × 每个出现过的取值 × 两种极性，选**加权**错误最小的组合。
- **极性（polarity）**：`polarity=1` 时"小于阈值判 −1"，`polarity=-1` 时乘了 −1 把不等号翻转，变成"大于阈值判 −1"。这样同一段代码覆盖了两个方向。两种极性的预测近似互补（只有恰好等于阈值的点在两种极性下都判为 +1），所以"反过来判"总在候选之内，最优加权误差基本不会超过 0.5，AdaBoost 的 α 也就不会为负。
- **加权误差** `np.sum(weights[pred != y])`：AdaBoost 的关键——被前面模型分错的样本权重大，树桩会优先把它们分对。
- ⚠️ 复杂度 O(F · N · N)：每个阈值都重新生成整列预测。生产实现会按特征排序后用前缀和一次扫描，降到 O(F · N log N)。
- `self.alpha` 属性由 AdaBoost 在外面写入，树桩本身不用它。

### 3.3 `AdaBoostScratch`：重加权 + 加权投票

```python
    def fit(self, X, y):
        n = X.shape[0]
        weights = np.full(n, 1 / n)

        for t in range(self.n_estimators):
            stump = DecisionStump()
            stump.fit(X, y, weights)
            pred = stump.predict(X)

            err = np.sum(weights[pred != y])
            err = np.clip(err, 1e-10, 1 - 1e-10)

            alpha = 0.5 * np.log((1 - err) / err)
            weights *= np.exp(-alpha * y * pred)
            weights /= weights.sum()
```

与讲义算法逐行对应：

| 讲义步骤 | 代码 |
|---------|------|
| 初始化 `w_i = 1/N` | `np.full(n, 1 / n)` |
| 训练加权弱学习器 | `stump.fit(X, y, weights)` |
| 加权误差 | `np.sum(weights[pred != y])`（权重已归一化，无需再除以总和） |
| `α = ½·ln((1−err)/err)` | `0.5 * np.log((1 - err) / err)` |
| `w ← w·exp(−α·y·h(x))` | `weights *= np.exp(-alpha * y * pred)` |
| 归一化 | `weights /= weights.sum()` |
| `H(x) = sign(Σ αₜhₜ(x))` | `predict` 中 `np.sign(total)` |

- **为什么 `y * pred` 能区分对错**：标签和预测都是 ±1，分对时乘积为 +1（权重乘 `e^{−α}` 变小），分错时为 −1（权重乘 `e^{α}` 变大）。这就是采用 ±1 标签的好处。
- `np.clip(err, 1e-10, 1 - 1e-10)`：如果某个树桩在加权意义下全对（err = 0），`log(1/0)` 会得到无穷大；夹紧后 α 变成一个很大但有限的数（约 11.5）。
- `predict` 中 `sum(a * s.predict(X) for a, s in zip(...))`：生成器表达式对多个**数组**求和，内置 `sum` 从 0 开始逐个相加，NumPy 广播保证结果是数组。
- ⚠️ `fit` 没有清空 `self.stumps` / `self.alphas`，同一个对象 fit 两次会把两轮的树桩叠在一起（实测 5 轮 fit 两次得到 10 个树桩）。sklearn 的约定是每次 `fit` 都从头开始。
- ⚠️ `np.sign(total)` 在 total 恰好为 0 时返回 0，与 ±1 都不相等。浮点加权和恰好为 0 的概率很小，但树结构的预测就不一定了（见 3.6）。

### 3.4 `SimpleRegressionTree`：按方差下降分裂

```python
    def _build(self, X, y, depth):
        n_samples, n_features = X.shape

        if depth >= self.max_depth or n_samples < self.min_samples_split:
            return TreeNode(value=np.mean(y))

        best_gain = -float("inf")
        # ...
        current_var = np.var(y) * n_samples

        for f in range(n_features):
            thresholds = np.unique(X[:, f])
            if len(thresholds) > 20:
                thresholds = np.percentile(X[:, f], np.linspace(0, 100, 20))

            for thresh in thresholds:
                left_mask = X[:, f] <= thresh
                right_mask = ~left_mask
                # ... 跳过空的一侧
                left_var = np.var(y[left_mask]) * left_mask.sum()
                right_var = np.var(y[right_mask]) * right_mask.sum()
                gain = current_var - left_var - right_var
```

- `np.var(y) * n` 就是**平方误差和（SSE）**：叶子用均值预测时，SSE = n × 方差。`gain` 是分裂前后 SSE 的下降量，也就是 CART 回归树的分裂准则。
- **候选阈值最多 20 个**：取值多于 20 个时，改用 0%–100% 之间均匀的 20 个分位数。这是直方图/分位数近似的最简版本（LightGBM 的直方图、XGBoost 的分位数草图是同一思想），把每个节点的搜索从 O(N) 个阈值降到 20 个。
- 停止条件：达到 `max_depth`、样本太少，或者找不到正增益的分裂（`best_gain <= 0`），都直接返回均值叶子。
- 递归：`node.left = self._build(X[left_mask], ...)`，布尔掩码 `~left_mask` 取反得到右子集。
- **叶子识别**靠 `node.value is not None`：内部节点的 `value` 保持 `None`，叶子一定有一个浮点均值。注意要用 `is not None` 而不是 `if node.value:`——均值恰好为 0.0 的叶子会被当成"假"，导致继续往下走、访问 `None` 子节点而崩溃。
- `predict` 对每个样本做一次 Python 递归，比向量化慢得多，这是整个脚本耗时约 30 秒的主要原因之一。

### 3.5 `GradientBoostingScratch`：一棵树拟合一次残差

```python
    def fit(self, X, y):
        self.initial_pred = np.mean(y)
        current_pred = np.full(len(y), self.initial_pred)

        for _ in range(self.n_estimators):
            residuals = y - current_pred
            tree = SimpleRegressionTree(max_depth=self.max_depth)
            tree.fit(X, residuals)
            update = tree.predict(X)
            current_pred += self.lr * update
            self.trees.append(tree)
```

- `F₀ = mean(y)`：平方损失下 `argmin_c Σ(yᵢ − c)²` 就是均值，对应讲义伪代码第 1 步。
- `residuals = y - current_pred`：平方损失的负梯度，对应讲义的伪残差。
- `current_pred += self.lr * update`：**shrinkage**，每棵树只贡献一小步。学习率小，单棵树的"错误"影响小，泛化更好，但需要更多树。
- 讲义伪代码里有一步线搜索 `γₜ`，代码省略了：对平方损失，叶子值取叶内残差的均值本身就是该叶子上的最优步长，所以不影响正确性。换成对数损失等其他损失时就不能省。
- `predict` 从 `initial_pred` 开始，依次加上每棵树的 `lr × 预测`，与训练时完全同构。
- ⚠️ 没有早停、没有行/列采样，也没有验证集监控——这些都是讲义练习 3 和 XGBoost 的内容。

### 3.6 `BaggingClassifier`：回归树 + 平均 + 取符号

```python
    def fit(self, X, y):
        rng = np.random.RandomState(42)
        n = len(y)

        for _ in range(self.n_estimators):
            idx = rng.choice(n, size=n, replace=True)
            tree = SimpleRegressionTree(max_depth=self.max_depth)
            tree.fit(X[idx], y[idx])
            self.trees.append(tree)

    def predict(self, X):
        predictions = np.array([tree.predict(X) for tree in self.trees])
        return np.sign(np.mean(predictions, axis=0))
```

- `rng.choice(n, size=n, replace=True)`：有放回抽 n 个下标，就是一份 bootstrap 样本。平均约 63.2% 的样本被抽中，其余为 OOB（测验 Q12 给出了 OOB 准确率的实现）。
- **用回归树做分类**：在 ±1 标签上训练回归树，叶子值是叶内标签均值，也就是"+1 的比例 × 2 − 1"，可以看成一个置信度分数。20 棵树的分数取平均再取符号，相当于**软投票**（soft voting）。
- `np.array([...])` 得到 `(n_trees, n_samples)` 的矩阵，`axis=0` 对树求平均。
- ⚠️ **平局问题**：单棵树的叶子若恰好一半 +1、一半 −1，叶子值为 0，`np.sign(0) = 0`，与任何标签都不相等。`demo_bagging` 中用来对比的深度 5 单棵树，在 80 个测试样本里有 **11 个**预测恰好为 0，准确率被压到 0.750；改成 `np.where(pred >= 0, 1, -1)` 后为 0.8125。所以 "Variance reduction: +0.113" 中约一半来自这个平局 bug，真实的 bagging 提升约 0.05。20 棵树平均后几乎不会恰好为 0，所以 bagging 自身不受影响。
- 和 AdaBoost 一样，`fit` 不重置 `self.trees`；随机种子写死为 42，不同实例抽到的 bootstrap 完全一样。

### 3.7 `StackingClassifier`：out-of-fold 元特征 + 逻辑回归元学习器

```python
        for fold in range(self.n_folds):
            val_start = fold * fold_size
            val_end = val_start + fold_size if fold < self.n_folds - 1 else n
            val_idx = indices[val_start:val_end]
            train_idx = np.concatenate([indices[:val_start], indices[val_end:]])

            for m_idx, model_class in enumerate(self.base_models):
                model = model_class()
                model.fit(X[train_idx], y[train_idx])
                meta_features[val_idx, m_idx] = model.predict(X[val_idx])
```

- 这就是讲义强调的"**元特征必须通过交叉验证生成**"：每个样本的元特征都来自一个没见过它的基模型。`meta_features` 的形状是 `(n, 基模型数)`，第 m 列是第 m 个基模型的 OOF 预测。
- `base_models` 传入的是**工厂函数**（`lambda: TreeWrapper(3)`），每折都 `model_class()` 新建一个，避免折间泄漏。参数名叫 `model_class` 是因为传类本身也能用。
- ⚠️ 折没有打乱（`np.arange(n)` 顺序切），依赖于数据已被 `train_test_split` 打乱。

```python
        for _ in range(200):
            logits = meta_features @ self.meta_weights + self.meta_bias
            preds = np.tanh(logits)
            errors = y - preds
            grad_w = -2 * meta_features.T @ errors / n
            grad_b = -2 * np.sum(errors) / n
            self.meta_weights -= self.meta_lr * grad_w
            self.meta_bias -= self.meta_lr * grad_b
```

- 看起来像"tanh 输出 + 均方误差"，但梯度里少了 `(1 − tanh²)` 因子。换个角度，这恰好是对 `log(1 + exp(−2yz))` 的梯度下降（再乘 2），也就是**用 ±1 标签写的逻辑回归**——正是最常用的元学习器（推导见测验 Q11）。
- 训练完元学习器后，再用**全部训练数据**重训每个基模型存入 `self.fitted_models`；预测时先过基模型得到元特征，再算 `sign(logits)`。
- ⚠️ 元特征是 `TreeWrapper.predict` 返回的 `np.sign(...)` 硬标签，丢掉了叶子的置信度；改成直接返回叶子值（软分数）通常更好。

### 3.8 演示函数中值得注意的细节

**(1) 循环变量泄漏：标签写的是 100，实际是 200**

```python
    for n_est in [1, 10, 50, 100, 200]:
        model = GradientBoostingScratch(n_estimators=n_est, learning_rate=0.1)
        # ...
    print(f"  GBM 100 MSE:     {model.mse(X_test, y_test):.4f}")
```

Python 的 `for` 不产生新作用域，循环结束后 `model` 指向**最后一个**（200 棵树）模型，所以打印的 0.2790 与 200 那一行相同，标签 "GBM 100" 是错的。`demo_adaboost` 里的 "AdaBoost 50" 恰好是最后一个（50），所以没出错——同样的写法，一个对一个错，是很典型的隐患。

**(2) 无用的残留代码**

```python
    def make_tree_d3():
        return SimpleRegressionTree(max_depth=3)
    # ...
    make_tree_d3.fit = None
```

`make_tree_d3/d5/d7` 三个函数及给它们设置 `fit` 属性的语句从未被使用（Python 允许给函数对象挂属性，但这里毫无作用），真正使用的是下面的 `TreeWrapper` 和 lambda 列表，可以整体删除。

**(3) sklearn API 变更导致崩溃**

```python
    try:
        from sklearn.ensemble import (
            AdaBoostClassifier,
            # ...
        )
    except ImportError:
        print("  sklearn not installed, skipping comparison.")
        # ...
    ada_sk = AdaBoostClassifier(n_estimators=50, random_state=42, algorithm="SAMME")
```

新版 scikit-learn 已经移除了 `AdaBoostClassifier` 的 `algorithm` 参数（SAMME 成为唯一算法）。在本环境（scikit-learn 1.9.1）上运行会抛 `TypeError: ... unexpected keyword argument 'algorithm'`，脚本在最后一个演示中途崩溃，"All ensemble demos complete." 也不会打印。`try/except ImportError` 只防住了"没装 sklearn"，防不住"装了但 API 变了"。去掉 `algorithm="SAMME"` 即可；实测三种 sklearn 模型的准确率为 AdaBoost 0.88、随机森林 0.89、GBM 0.91。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 分类标签统一用 ±1 | `y·h(x)` 直接判断对错；回归树均值可当置信度 | sklearn 等库通常用 0/1，需要转换（代码中 `(y + 1) // 2`） |
| 树桩暴力搜索所有阈值 | 直观，与定义一一对应 | O(F·N²)；生产中排序 + 前缀和，或直方图 |
| 回归树最多 20 个分位数阈值 | 控制计算量，近似效果足够 | 极端分布下可能错过最佳切点；LightGBM 用直方图且可调 bin 数 |
| 用回归树做 bagging 分类 | 复用同一棵树，平均分数 = 软投票 | 单棵树预测会出现 0（平局），需要显式处理 |
| GBM 省略 γ 线搜索 | 平方损失下叶子均值已是最优 | 其他损失需线搜索或牛顿步（XGBoost 用二阶导） |
| Stacking 手写 K 折 + 全量重训 | 展示无泄漏 stacking 的完整流程 | 未打乱；元特征用硬标签；生产中用 `StackingClassifier(cv=..., stack_method="predict_proba")` |
| 元学习器用 tanh 形式的逻辑回归 | 简单、不易过拟合 | 无正则；命名像 MSE，易误解 |
| 固定随机种子 42 | 结果可复现 | 不同 bagging 实例抽样完全相同 |
| `fit` 不重置模型列表 | 代码更短 | 重复 `fit` 会累积模型，违背 sklearn 约定 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from ... import ...` | `from collections import Counter` | 导入单个名字（本文件导入后未使用） |
| `np.where(cond, a, b)` | `np.where(boundary + ... > 0, 1, -1)` | 按条件逐元素选值 |
| 布尔掩码索引 | `weights[pred != y]`、`y[left_mask]` | 用 True/False 数组筛选元素 |
| 掩码取反 `~` | `right_mask = ~left_mask` | 布尔数组按位取反 |
| 掩码赋值 | `pred[polarity * X[:, f] < polarity * thresh] = -1` | 只修改满足条件的位置 |
| 原地运算 | `weights *= ...`、`weights /= weights.sum()`、`current_pred += ...` | 直接修改数组，不新建对象 |
| 元组解包 shape | `n_samples, n_features = X.shape` | 一次取出行数和列数 |
| 生成器对数组求和 | `sum(a * s.predict(X) for a, s in zip(self.alphas, self.stumps))` | 内置 `sum` 逐个相加，结果是数组 |
| 递归 | `_build` 调用自身构造左右子树；`_predict_one` 沿树向下 | 树结构天然适合递归 |
| `is not None` | `if node.value is not None:` | 判断"有没有值"，不会被 0.0 误判 |
| 无穷大哨兵 | `float("inf")`、`-float("inf")` | 求最小/最大值时的初始值 |
| 列表推导 + `np.array` | `np.array([tree.predict(X) for tree in self.trees])` | 把多棵树的预测堆成二维数组 |
| `enumerate` | `for m_idx, model_class in enumerate(self.base_models)` | 同时拿到下标和元素 |
| `lambda` 工厂 | `[lambda: TreeWrapper(3), lambda: TreeWrapper(5), ...]` | 每次调用返回一个新模型对象 |
| 函数内定义类 | `demo_stacking` 里的 `class TreeWrapper` | 只在该函数内使用的辅助类 |
| 给函数对象设属性 | `make_tree_d3.fit = None` | 合法但罕见；本文件中是无用代码 |
| `try` / `except ImportError` / 函数内 `import` | `demo_sklearn_comparison` | 可选依赖：没装就跳过 |
| 数组整除 | `y_01 = (y + 1) // 2` | 把 ±1 标签映射为 0/1 |
| f-string 格式 | `f"{n_est:>3d}"`、`f"{train_acc:.3f}"`、`f"{bag_acc - single_acc:+.3f}"` | `>3d` 右对齐整数；`+` 强制显示正负号 |
| 字符串重复 | `"=" * 60` | 打印分隔线 |

---

## 6. 运行结果解读

实际运行（在临时副本中执行 `python3 ensembles.py`，约 33 秒）的输出，按演示逐段解读。

```text
ADABOOST FROM SCRATCH
  n_estimators=  1  train_acc=0.828  test_acc=0.750
  n_estimators=  5  train_acc=0.881  test_acc=0.762
  n_estimators= 10  train_acc=0.922  test_acc=0.787
  n_estimators= 25  train_acc=0.950  test_acc=0.800
  n_estimators= 50  train_acc=0.981  test_acc=0.838

  Single stump accuracy: 0.750
  AdaBoost 50 accuracy:  0.838
  Improvement: 0.088
```

- 单个树桩 0.750，只比"全部预测 +1"的基线（约 0.67）好一点。50 个树桩叠加后测试准确率 0.838：**弱学习器的组合学到了树桩无法表达的二次边界**——boosting 在降偏差。
- 训练准确率持续上升到 0.981，与测试准确率的差距逐渐拉大，这是 boosting 轮数增加后方差上升的苗头。

```text
GRADIENT BOOSTING FROM SCRATCH
  n_estimators=  1  train_mse=3.7395  test_mse=4.3711
  n_estimators= 10  train_mse=1.2620  test_mse=1.7324
  n_estimators= 50  train_mse=0.1572  test_mse=0.4450
  n_estimators=100  train_mse=0.0623  test_mse=0.3073
  n_estimators=200  train_mse=0.0260  test_mse=0.2790

  Single tree MSE: 1.3385
  GBM 100 MSE:     0.2790
```

- 1 棵树时 MSE 很大：学习率 0.1 意味着第一棵树只走了 10% 的路。
- 树越多误差越小，200 棵时测试 MSE 0.279，约为单棵深度 3 回归树（1.3385）的 1/5。数据噪声标准差 0.3，不可约误差约 0.09，还有下降空间。
- 训练 MSE 下降得比测试快得多（0.026 vs 0.279），继续加树最终会过拟合，需要早停。
- 最后一行标签应为 "GBM 200"（见 3.8）。

```text
LEARNING RATE vs NUMBER OF TREES
  lr=0.50, n_trees= 20  test_mse=0.3759
  lr=0.10, n_trees=100  test_mse=0.3073
  lr=0.05, n_trees=200  test_mse=0.2967
  lr=0.01, n_trees=500  test_mse=0.4652
```

- 前三组 `lr × n_trees` 都等于 10，学习率越小、树越多，误差越低：0.376 → 0.307 → 0.297，印证了"小步多走泛化更好"。
- 第四组 `0.01 × 500 = 5`，只有前面的一半，模型还没训练够，误差反而最高。程序打印的 *"Lower learning rates need more trees but often generalize better"* 的前半句正说明了这一点：**lr 降 5 倍，树也要相应增加约 5 倍**。另行实测 `lr=0.01, n_trees=1000`，测试 MSE 为 0.2932，比上面四组都低（单这一组训练就要约 18 秒）。

```text
BAGGING CLASSIFIER
  Single tree accuracy: 0.750
  Bagging (20 trees):   0.863
  Variance reduction:   +0.113

STACKING ENSEMBLE
  Tree depth=3 accuracy: 0.825
  Tree depth=5 accuracy: 0.750
  Tree depth=7 accuracy: 0.825
  Stacking accuracy:    0.838
  Meta-learner weights: [0.54838655 0.2129523  0.39293023]
```

- 深度 5 的树比深度 3、7 都差，是 `np.sign(0)` 平局造成的（11 个测试样本预测恰好为 0，见 3.6）。修正后单棵树为 0.8125，bagging 的真实提升约 +0.05。
- 输出标签 "Variance reduction" 其实是准确率之差，并不是方差本身；要量化方差下降，需要像第 10 节那样多次重采样后比较预测的方差。
- Stacking 0.838，略高于最好的单个基模型（0.825）。元学习器给深度 5 的权重最低（0.213），一个原因正是它的输出里有许多 0（不提供信息）。三个基模型都是同一类型的树，多样性有限，这也是 stacking 提升不大的原因——讲义强调 stacking 最好组合**不同模型族**。

```text
FULL COMPARISON
  Single tree (d=5):    0.870
  Bagging (20, d=5):    0.880
  AdaBoost (50 stumps): 0.870
```

换成 500 个样本（测试集 100 个）后，单棵树没有出现平局（0 个零预测），bagging 比单棵树高 1 个百分点，AdaBoost 与单棵树持平。测试集只有 100 个样本，1 个样本就是 1%，这几个数字之间的差异并不显著，不能据此给方法排序。

```text
SKLEARN COMPARISON
  Our AdaBoost:      0.870
Traceback (most recent call last):
  ...
TypeError: AdaBoostClassifier.__init__() got an unexpected keyword argument 'algorithm'
```

- 自己实现的 AdaBoost 为 0.870。
- 随后因 sklearn API 变更而崩溃（见 3.8）。去掉 `algorithm="SAMME"` 后另行实测：sklearn AdaBoost 0.88、随机森林 0.89、GBM 0.91——成熟实现（更好的分裂搜索、正则化、更多树）仍有优势。

---

## 7. 动手改一改

1. **修三个 bug**：去掉 `algorithm="SAMME"`；把 "GBM 100" 改为保存并打印真正的 100 棵树模型；所有 `np.sign(...)` 分类处改为 `np.where(score >= 0, 1, -1)`。重跑后对比 bagging 的提升幅度。
2. **讲义练习 1**：在 `AdaBoostScratch.fit` 中记录每一轮后的训练/测试准确率（可以累加 `alpha * stump.predict(X)` 增量计算，不必每轮重新预测全部树桩），观察何时收敛。
3. **讲义练习 3（早停）**：给 `GradientBoostingScratch` 加验证集，连续 10 轮验证 MSE 不下降就停，看实际需要多少棵树；顺便实现类似 `staged_predict` 的逐轮预测，避免为每个 `n_estimators` 从头训练。
4. **讲义练习 2（随机森林）**：在 `SimpleRegressionTree._build` 里每个节点只随机考察 `max(1, int(np.sqrt(n_features)))` 个特征，用它替换 bagging 中的树，比较准确率与各树预测之间的相关性。
5. **OOB 估计**：按测验 Q12 为 `BaggingClassifier` 增加 `oob_score_`。
6. **更好的 stacking**：让 `TreeWrapper.predict` 返回叶子值（软分数）而不是符号，并加入一个不同类型的基模型（如本阶段第 3 节的逻辑回归），比较元学习器的权重与准确率。

---

## 8. 常见坑

- **`np.sign(0) == 0`**：用 ±1 标签和 `sign` 做分类时，平局会产生第三种"类别"并被计为错误。显式处理平局。
- **循环变量泄漏**：循环后继续使用循环内的变量，拿到的是最后一次迭代的值，打印标签很容易和实际对象不符。
- **`fit` 不重置状态**：在列表上 `append` 的实现，重复 `fit` 会累积模型。
- **只捕获 `ImportError`**：可选依赖装了但版本不同，同样会失败；对外部库的参数要关注版本变更（本例为 `algorithm` 参数被移除）。
- **学习率减小却不增加树**：GBM 中 `lr` 与 `n_estimators` 是一对，单独调一个会得出错误结论。
- **Stacking 用样本内预测做元特征**：元学习器会过度信任过拟合的基模型。务必使用 out-of-fold 预测。
