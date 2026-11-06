# 代码讲解 · trees.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 04 节 决策树和随机森林 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python trees.py`（无命令行参数，依次运行 8 个演示，约 6 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`），不需要 NumPy 或 sklearn

---

## 1. 这份代码在考察什么

1. **不纯度度量**：Gini、熵、信息增益、方差减小——决策树"选哪个问题来问"的数学依据。
2. **递归建树**：`_build` 如何在"停止"与"继续分裂"之间做决定，树如何用嵌套字典表示。
3. **贪心搜索最佳分裂**：遍历特征 × 阈值，以及这种朴素实现的复杂度代价。
4. **随机森林 = bootstrap + 特征随机化 + 投票/平均**：两种随机性如何让树变得多样。
5. **MDI 特征重要性**：训练时顺手累加的不纯度下降。
6. **实验与评估意识**：深度与过拟合、树的数量与稳定性、分类树与回归树——同时也要学会审视演示本身的结论是否站得住（见 3.8）。

> 一句话：**一棵树就是一个递归函数 + 一个贪心搜索；一片森林就是把这棵树在不同的随机数据和随机特征上种很多遍再投票。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `gini_impurity` / `entropy` | 函数 | 计算一组标签的不纯度 | Gini、熵 |
| `information_gain` | 函数 | 父节点不纯度 − 加权子节点不纯度 | 信息增益 |
| `variance_reduction` / `_variance` / `_mean` | 函数 | 回归树的分裂准则与叶子值 | 方差减小 |
| `majority_vote` | 函数 | 返回出现次数最多的标签 | 叶子预测 |
| `DecisionTree` | 类 | `fit` / `predict` / `_build` / `_best_split` / `_split_data` / `print_tree` | CART 风格二叉树 |
| `RandomForest` | 类 | bootstrap 训练多棵树，投票或平均，汇总重要性 | Bagging + 特征随机化 |
| `accuracy` / `train_test_split` | 函数 | 评估与切分工具 | — |
| `generate_classification_data` | 函数 | 圆内为类 0，圆外再按 `x1+x2>1` 分为类 1/2 | 非线性边界 |
| `generate_regression_data` | 函数 | `y = sin(x)·x + 噪声` | 回归树 |
| 8 个 `demo_*` / `print_summary` | 演示 | 不纯度、增益、深度、Gini vs 熵、森林规模、重要性、回归、稳定性 | — |

调用关系：`DecisionTree.fit → _build（递归）→ _best_split → information_gain / variance_reduction`；`RandomForest.fit` 循环创建 `DecisionTree` 并 `fit` 在 bootstrap 样本上；`predict` 收集所有树的结果再投票/平均。

---

## 3. 逐段精讲

### 3.1 不纯度：用字典计数

```python
def gini_impurity(labels):
    n = len(labels)
    if n == 0:
        return 0.0
    counts = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return 1.0 - sum((c / n) ** 2 for c in counts.values())


def entropy(labels):
    # ... 同样的计数
    return -sum(
        (c / n) * math.log2(c / n) for c in counts.values() if c > 0
    )
```

- `counts.get(label, 0) + 1` 是"字典计数"的经典写法：键不存在时返回默认值 0。等价于 `collections.Counter(labels)`。
- 标签可以是任意可哈希的值（整数、字符串），所以 `demo_information_gain` 里可以直接用 `"cat"`、`"dog"`。
- `if c > 0` 防止 `log2(0)`；不过计数来自实际出现的标签，c 必然 > 0，这里是防御性写法。
- ⚠️ 纯节点的熵会打印成 `-0.0000`：`-sum([1·log2(1)])` = `-0.0`，浮点数的负零。数学上没问题，展示上可以写成 `0.0 - sum(...)` 或最后加 `+ 0.0` 规避。

```python
def information_gain(parent_labels, left_labels, right_labels, criterion="gini"):
    measure = gini_impurity if criterion == "gini" else entropy
    # ...
    if n_left == 0 or n_right == 0:
        return 0.0
    parent_impurity = measure(parent_labels)
    child_impurity = (
        (n_left / n) * measure(left_labels)
        + (n_right / n) * measure(right_labels)
    )
    return parent_impurity - child_impurity
```

- `measure = gini_impurity if ... else entropy`：**函数是一等公民**，可以像变量一样赋值、传递，避免写两份几乎相同的代码。
- 子节点按样本数加权：一个只有 1 个样本的纯子节点不应该和 100 个样本的子节点同等重要。
- 空子节点返回增益 0，等于宣布"这不是有效分裂"。
- `variance_reduction` 结构完全相同，只是把不纯度换成方差（`_variance` 用总体方差，除以 n）。

### 3.2 `DecisionTree._build`：四个停止条件 + 递归

```python
    def _build(self, X, y, depth):
        # ...
        if all_same:
            return {"leaf": True, "value": y[0] if self.task == "classification" else _mean(y)}

        if self.max_depth is not None and depth >= self.max_depth:
            return self._make_leaf(y)

        if len(y) < self.min_samples_split:
            return self._make_leaf(y)

        best_feature, best_threshold, best_gain = self._best_split(X, y)

        if best_feature is None or best_gain <= 0:
            return self._make_leaf(y)

        left_X, left_y, right_X, right_y = self._split_data(
            X, y, best_feature, best_threshold
        )
        # ... min_samples_leaf 检查
        weight = len(y) / self.n_samples
        self.feature_importances_[best_feature] += weight * best_gain

        left_child = self._build(left_X, left_y, depth + 1)
        right_child = self._build(right_X, right_y, depth + 1)

        return {
            "leaf": False,
            "feature": best_feature,
            "threshold": best_threshold,
            "left": left_child,
            "right": right_child,
        }
```

停止条件（任一满足就变成叶子）：

| 条件 | 含义 | 类型 |
|------|------|------|
| `all_same` | 节点已纯（回归时所有 y 相同） | 自然停止 |
| `depth >= max_depth` | 达到最大深度 | 预剪枝 |
| `len(y) < min_samples_split` | 样本太少，不值得再分 | 预剪枝 |
| `best_gain <= 0` 或找不到分裂 | 没有任何分裂能降低不纯度（比如所有样本特征相同但标签不同） | 自然停止 |

- 树用**嵌套字典**表示：内部节点存 `feature`、`threshold`、`left`、`right`，叶子存 `value`。简单直观，`print_tree` 和 `_predict_one` 都只需按键访问。
- **MDI 重要性在这里顺手累加**：`(该节点样本数 / 总样本数) × 增益`，与讲义公式、sklearn 的定义一致。`fit` 最后把它归一化到和为 1。
- ⚠️ 开头 `if self.task == "classification": all_same = ... else: all_same = ...` 两个分支完全相同，是可以合并的冗余代码。
- ⚠️ `min_samples_leaf` 的检查在 `_best_split` 里已经做过，这里的再次检查实际上不会触发，属于双保险。
- ⚠️ 增益只要 > 0 就分裂，所以会出现"两个子叶子预测同一类"的分裂（见 6 节输出）：不纯度下降了，但预测没变。sklearn 提供 `min_impurity_decrease` 和 `ccp_alpha` 来抑制。
- 递归深度：不限深时最坏情况下树深可达 n−1，Python 默认递归上限约 1000，极端数据上会触发 `RecursionError`；生产实现用显式栈。

### 3.3 `_best_split`：贪心地试遍所有（特征, 阈值）

```python
        if self.max_features is None:
            feature_indices = list(range(self.n_features))
        elif self.max_features == "sqrt":
            k = max(1, int(math.sqrt(self.n_features)))
            feature_indices = random.sample(range(self.n_features), k)
        elif isinstance(self.max_features, int):
            # ... 校验后取 min(max_features, n_features) 个
        else:
            feature_indices = list(range(self.n_features))

        for feature_idx in feature_indices:
            values = sorted(set(X[i][feature_idx] for i in range(len(X))))
            if len(values) <= 1:
                continue

            for i in range(len(values) - 1):
                threshold = (values[i] + values[i + 1]) / 2.0
                left_y = [y[j] for j in range(len(X)) if X[j][feature_idx] <= threshold]
                right_y = [y[j] for j in range(len(X)) if X[j][feature_idx] > threshold]
                # ... min_samples_leaf 过滤，计算 gain，更新 best
```

- **特征随机化**就在这里：`max_features="sqrt"` 时每次分裂随机抽 `⌊√d⌋` 个特征。注意是**每个节点**重新抽，而不是每棵树抽一次——这正是随机森林与"随机子空间法"的区别。
- `random.sample(range(n), k)` 无放回地抽 k 个不重复下标。
- `sorted(set(...))` 去重并排序；阈值取**相邻不同取值的中点**，m 个不同取值只有 m−1 个有意义的阈值。
- ⚠️ **复杂度**：每个阈值都用两个列表推导把全部样本扫一遍，单特征 O(m²)，一次分裂 O(d·m²)。这是脚本跑 6 秒的主因。高效做法是排序一次后从左到右扫描、增量维护两侧类别计数，降到 O(m log m)（测验 Q11 给出了完整实现）。
- ⚠️ 与 sklearn 的差异：本节只有 2 个特征时 `⌊√2⌋ = 1`，每个节点只看 1 个随机特征。如果抽到的特征在该节点上是常数（只有一个取值），或者它带来的增益不为正，节点就直接变成叶子，哪怕另一个特征其实能分得很好。sklearn 不把常数特征计入 `max_features`，会继续抽取其他特征，直到至少找到一个有效划分。
- ⚠️ 讲义说回归时默认用 `d/3` 个特征，但代码中 `RandomForest` 的回归任务仍默认 `"sqrt"`（本节回归数据只有 1 个特征，所以没影响）。
- 用的是全局 `random`，所以森林的结果依赖之前所有代码对全局随机状态的消耗。

### 3.4 预测与打印

```python
    def _predict_one(self, x, node):
        if node["leaf"]:
            return node["value"]
        if x[node["feature"]] <= node["threshold"]:
            return self._predict_one(x, node["left"])
        return self._predict_one(x, node["right"])
```

- 从根走到叶子，每次 O(1)，总复杂度 O(树深)。这就是树模型推理极快的原因。
- 约定 `<=` 走左边，与 `_split_data`、`_best_split` 保持一致——三处约定不一致是手写树最常见的 bug。
- `print_tree` 同样递归，每深入一层缩进加 4 个空格；`node=None` 作默认参数，第一次调用时从根开始。

### 3.5 `RandomForest`：bootstrap + 投票

```python
    def fit(self, X, y):
        self.trees = []
        n = len(X)
        for _ in range(self.n_trees):
            indices = [random.randint(0, n - 1) for _ in range(n)]
            X_boot = [X[i] for i in indices]
            y_boot = [y[i] for i in indices]

            tree = DecisionTree(
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                max_features=self.max_features,
                criterion=self.criterion,
                task=self.task,
            )
            tree.fit(X_boot, y_boot)
            self.trees.append(tree)
```

- `random.randint(0, n - 1)` 两端都包含，抽 n 次就是有放回抽样；约 63.2% 的原样本会被抽到，其余是 OOB 样本。代码没有利用 OOB 样本，可以作为练习加上 OOB 误差估计。
- `self.trees = []` 在 `fit` 开头重置，保证重复调用 `fit` 不会把旧树累积进来。
- 每棵树完全独立，天然可以并行（sklearn 的 `n_jobs`）。

```python
    def predict(self, X):
        all_preds = [tree.predict(X) for tree in self.trees]
        predictions = []
        for i in range(len(X)):
            if self.task == "classification":
                votes = {}
                for preds in all_preds:
                    v = preds[i]
                    votes[v] = votes.get(v, 0) + 1
                predictions.append(max(votes, key=votes.get))
            else:
                predictions.append(
                    sum(preds[i] for preds in all_preds) / len(all_preds)
                )
        return predictions
```

- `all_preds` 是"树 × 样本"的二维列表，外层循环按样本取出每棵树的票。
- `max(votes, key=votes.get)`：在字典的**键**中找"值最大"的那个，即得票最多的类别；平票时取先出现的键。
- 分类用**硬投票**；sklearn 实际上用的是**软投票**（平均各树的类别概率再取最大），概率输出更平滑。
- 回归直接取平均，"平均许多分段常数函数"会得到更平滑的曲线。
- `feature_importances` 把每棵树归一化后的 MDI 相加再归一化，等价于 sklearn 的"各树重要性取平均"。

### 3.6 数据生成与切分

```python
        if x1 ** 2 + x2 ** 2 + noise < 3:
            label = 0
        elif x1 + x2 + noise > 1:
            label = 1
        else:
            label = 2
```

- 类 0 是半径约 √3 的圆盘，圆外再被直线 `x1 + x2 = 1` 分成两类。圆形边界对"轴对齐切分"的树来说并不友好，需要很多次切分去逼近（阶梯状边界），所以浅树准确率很低。
- `noise` 让边界附近的标签带有随机性，任何模型都达不到 100% 测试准确率。
- ⚠️ `generate_*` 和 `train_test_split` 内部都会调用 `random.seed(seed)`，**重置全局随机状态**。这让结果可复现，但也是一种隐蔽的副作用：调用它们之后，后续随机森林的随机性完全由这里的种子决定。更好的做法是使用独立的 `random.Random(seed)` 实例。

### 3.7 演示一览

| 演示 | 看什么 |
|------|-------|
| `demo_split_criteria` | 同一组分布下 Gini 与熵的数值对照 |
| `demo_information_gain` | 三个候选分裂中，把 cat 完全分开的 B 增益最大 |
| `demo_decision_tree` | 深度 1/2/3/5/10/None 的训练与测试准确率，以及 depth=3 的树结构 |
| `demo_gini_vs_entropy` | 两种准则的测试准确率差异 |
| `demo_random_forest` | 1–100 棵树的训练/测试准确率 |
| `demo_feature_importance` | 两个有效特征 + 两个噪声特征的 MDI |
| `demo_regression_tree` | 回归树的深度与 MSE，及随机森林回归 |
| `demo_single_tree_vs_forest` | 单树与森林在 5 次扰动下的准确率均值和标准差 |

### 3.8 ⚠️ 两个需要批判性看待的演示

**`demo_single_tree_vs_forest` 有数据泄漏**：

```python
        indices = [random.randint(0, len(X) - 1) for _ in range(len(X))]
        X_sub = [X[i] for i in indices]
        y_sub = [y[i] for i in indices]
        X_tr, y_tr, X_te, y_te = train_test_split(X_sub, y_sub, seed=trial)
```

先 bootstrap 再切分，重复的样本会同时出现在训练集和测试集。实测每次 40 个测试点中有 18–27 个与训练集中的点完全相同，所以这里的准确率（0.94 / 0.965）明显高于干净切分下的约 0.85。而且两者标准差都是 0.0200，打印的"森林更稳定"的结论并没有被这组数字支持。正确做法：先切出固定测试集，只在训练集内部做扰动。

**`demo_random_forest` 的结论与输出不符**：打印语句说"Test accuracy plateaus but does not decrease"，但输出中 50 棵树的测试准确率是 0.8833，低于 10 棵树的 0.95。原因是每个 n 都重新训练了一片新森林、随机状态不同，加上测试集只有 60 个样本（1 个样本 = 1.7 个百分点），噪声很大。换几个种子重复 50 棵树的实验，测试准确率在 0.90–0.95 之间波动。要验证"树多不会变差"，应对每个 n 多次重复取平均，或让同一片森林逐步加树、在同一个更大的测试集上评估。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表 + 字典 | 零依赖，每一步都可见 | 慢；生产用 sklearn / LightGBM 等 C/C++ 实现 |
| 嵌套字典表示树 | 结构直观，易打印、易递归 | 内存与访问效率低；sklearn 用并行数组存节点 |
| 每个阈值重扫全部样本 | 代码最短、最好懂 | O(m²)；生产用排序扫描或直方图分桶 |
| 中点作阈值、`<=` 走左 | 与 CART/sklearn 约定一致 | 三处约定必须一致 |
| 增益 > 0 即分裂 | 规则简单 | 产生"无效"分裂；生产加最小增益或后剪枝 |
| 硬投票 | 直观 | 没有概率输出；sklearn 用软投票 |
| MDI 在建树时累加 | 零额外开销 | 偏向高基数特征；可补充置换重要性 |
| 在函数内重置全局随机种子 | 每个演示独立可复现 | 隐蔽副作用；更好的是传入独立的 `random.Random` |
| 只支持数值特征 | 保持分裂逻辑统一 | 类别特征需先编码，缺失值无法处理 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 字典计数 | `counts[label] = counts.get(label, 0) + 1` | `get` 的第二个参数是键不存在时的默认值 |
| 函数作为值 | `measure = gini_impurity if criterion == "gini" else entropy` | 函数可赋给变量后再调用 |
| 带条件的生成器 | `sum(... for c in counts.values() if c > 0)` | 过滤后求和 |
| `set` 去重 + `sorted` | `sorted(set(X[i][feature_idx] for i in range(len(X))))` | 得到有序的不重复取值 |
| 带过滤的列表推导 | `[y[j] for j in range(len(X)) if X[j][feature_idx] <= threshold]` | 按条件挑选元素 |
| `max(..., key=...)` | `max(counts, key=counts.get)` | 按自定义规则找最大；遍历字典得到的是键 |
| `sorted(..., key=lambda ...)` | `sorted(zip(feature_names, importances), key=lambda x: -x[1])` | 匿名函数定义排序依据，取负号实现降序 |
| `isinstance` | `isinstance(self.max_features, int)` | 根据参数类型走不同分支 |
| `raise ValueError` | `raise ValueError("max_features must be at least 1 ...")` | 参数不合法时主动报错 |
| 嵌套字典 | `{"leaf": False, "feature": ..., "left": {...}}` | 用字典表示树节点 |
| 递归 | `_build`、`_predict_one`、`print_tree` | 函数调用自身处理子问题 |
| `None` 作默认参数 | `def print_tree(self, node=None, indent="")` | 第一次调用时再决定从根开始 |
| `random.sample` / `randint` / `shuffle` / `seed` | 特征子集、bootstrap、切分 | 无放回抽样 / 闭区间随机整数 / 原地打乱 / 固定种子 |
| 字符串乘法 | `"#" * int(imp * 40)`、`"-" * 30` | 画文本条形图和分隔线 |
| f-string 格式符 | `f"{name:<30s}"`、`f"{g:>8.4f}"`、`f"{n:>8d}"` | 左对齐字符串、右对齐浮点、右对齐整数 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行演示 |

---

## 6. 运行结果解读

实际运行（约 6.3 秒）的关键输出：

```text
  Distribution                       Gini  Entropy
  Pure node [A,A,A,A]              0.0000  -0.0000
  Balanced [A,A,B,B]               0.5000   1.0000
  Imbalanced [A,A,A,B]             0.3750   0.8113
  Three classes [A,A,B,C]          0.6250   1.5000
  Uniform 4-class                  0.7500   2.0000
```

- 纯节点都为 0（`-0.0000` 是浮点负零）；二分类均衡时取最大值 0.5 / 1.0；4 类均匀时为 `1 − 1/4` 和 `log₂4`。

```text
  Parent Gini: 0.6600
  Feature A: ...     0.1433       0.3710
  Feature B: ...     0.3600       0.9710
  Feature C: ...     0.0100       0.0200
```

- 两种准则数值不同，但排序一致：B > A > C。

```text
   Max Depth   Train Acc    Test Acc
           1      0.5312      0.4750
           2      0.6750      0.6250
           3      0.8438      0.8250
           5      0.9563      0.8250
          10      1.0000      0.8500
        None      1.0000      0.8500
```

- 深度 1–3 明显欠拟合（圆形边界需要多次切分）。深度 ≥ 10 训练集 100%，训练与测试相差 15 个百分点，是典型的过拟合信号；不过在这 40 个测试样本上，深树的测试准确率并没有比深度 5 更差——"深树测试变差"在这次运行中并不明显，小测试集的结论需要谨慎。

```text
Feature 0 <= -1.1527?
  Yes:
    Feature 1 <= 2.5769?
      Yes:
        Feature 0 <= -1.7091?
          Yes:
            Predict: 2
          No:
            Predict: 2
```

- 根节点用 `x0 ≤ −1.15` 把左侧区域分出去，那里 50 个训练样本中有 45 个是类 2。`x0 ≤ −1.7091` 这个节点左右都预测 2：左边 29 个全是类 2，右边是 3 个类 0 + 13 个类 2，Gini 降低了约 0.016，但多数类没变——"有增益但没用"的分裂。

```text
  depth=3     Gini acc: 0.8250  Entropy acc: 0.8000  Diff: 0.0250
  depth=10    Gini acc: 0.8500  Entropy acc: 0.9000  Diff: 0.0500
```

- 差异是 1–2 个测试样本，属于噪声范围，与"两者几乎一样"的结论相符。

```text
   N Trees   Train Acc    Test Acc
         1      0.9292      0.8667
         5      0.9458      0.9500
        25      0.9708      0.9333
        50      0.9708      0.8833
       100      0.9708      0.9500
```

- 从 1 棵到 5 棵树提升明显；之后在 0.88–0.95 之间波动，并非严格"平台"（原因见 3.8）。

```text
  important_2            0.4807  ###################
  important_1            0.4348  #################
  noise_2                0.0491  #
  noise_1                0.0354  #
```

- 两个有效特征占了约 92%；噪声特征也分到了 3%–5%，这正是 MDI 对连续噪声特征的偏差，置换重要性会把它们压到接近 0。

```text
   Max Depth   Train MSE    Test MSE
           1      0.3259      0.3543
           3      0.0681      0.0709
           5      0.0293      0.0433
          10      0.0031      0.0599
  Random Forest (50 trees, depth=5) Test MSE: 0.0410
```

- 回归树的过拟合非常清楚：深度 10 训练 MSE 几乎为 0，测试 MSE 反而比深度 5 高。森林在相同深度下测试 MSE 略好于单棵树。噪声方差为 0.04（σ=0.2），测试 MSE 0.041 已接近这个下限。

```text
  Single tree:   mean = 0.9400, std = 0.0200
  Random forest: mean = 0.9650, std = 0.0200
```

- 准确率因数据泄漏被抬高，两者标准差相同，不能据此得出"森林更稳定"（见 3.8）。

---

## 7. 动手改一改

1. 修好 `entropy` 的负零显示问题，并把 `_build` 开头重复的 if/else 合并成一行。
2. 用测验 Q11 的"排序 + 扫描"思路重写 `_best_split`，对比整个脚本的运行时间。
3. 修正 `demo_single_tree_vs_forest`：先切出固定测试集，只在训练集内部 bootstrap，试验 20 次后再比较均值和标准差。
4. 给 `RandomForest` 加上 OOB 评估：记录每棵树没抽到的样本下标，用"没见过该样本的树"投票，计算 OOB 准确率，与测试准确率对比。
5. 把硬投票改为软投票：叶子存类别分布，`predict_proba` 平均各树的概率。
6. 实现置换重要性（测验 Q12），在 `demo_feature_importance` 的数据上与 MDI 对比；再加一列与标签无关的高基数特征，观察两种方法的差异。

---

## 8. 常见坑

- **左右分支约定不一致**：建树用 `<=`、预测用 `<` 会让恰好等于阈值的样本走错方向。
- **先 bootstrap/过采样再切分**：重复样本跨越训练集和测试集，评估严重虚高。
- **用小测试集上的单次结果下结论**：几十个测试样本时，一两个样本的差别就足以让"趋势"反转。
- **在函数内部重置全局随机种子**：会悄悄改变后续所有随机操作，调试时很难察觉。
- **`[[0] * d] * k` 一类的共享引用**：本文件用列表推导避开了，但自己扩展代码时要注意。
- **把 MDI 当成真实重要性**：它偏向高基数特征、在相关特征间分摊，且基于训练集计算。
- **期望树模型外推**：回归树在训练范围之外只会输出边缘叶子的常数。
