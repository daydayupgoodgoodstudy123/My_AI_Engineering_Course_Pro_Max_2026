# 代码讲解 · tuning.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 12 节 Hyperparameter 调整 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python tuning.py`（无命令行参数；纯 Python 训练数百个小模型，本环境完整跑完约 30 分钟，见第 6 节） ｜ **依赖**：`numpy`、标准库 `itertools`、`time`；`optuna`（可选，未安装时自动跳过最后一个演示）

---

## 1. 这份代码在考察什么

调参本身就是一个"优化问题"：输入是一组超参数，输出是验证集分数，而每评估一次都要完整训练一个模型，非常昂贵。这份代码围绕同一个被调模型（自写的梯度提升 `GBMForTuning`），从零实现了三种搜索策略：

1. **Grid Search**：`itertools.product` 穷举，体会组合数的指数增长。
2. **Random Search**：从 `int` / `float` / `log_float` 分布采样，体会"同样预算下覆盖更密"以及对数尺度采样。
3. **Bayesian Optimization**：自己写高斯过程（RBF 核 + Cholesky 求后验）和 Expected Improvement 采集函数，体会"利用历史结果决定下一步"。
4. **公平比较**：同样的评估次数下，用 best-so-far 曲线比较三者的收敛速度。
5. **工程工具对照**：如果装了 Optuna，用它做同样的搜索并输出超参数重要性。

> 一句话：**搜索策略的差别在于"下一个点怎么选"**——网格按事先画好的格子走，随机搜索闭着眼睛撒点，贝叶斯优化先建一个"分数地图"再决定去哪儿。代码同时暴露了调参的真实痛点：哪怕只有 400 条数据，完整跑一遍也要约半小时。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `make_data` | 函数 | 生成 8 维非线性回归数据并按 60/20/20 切成训练/验证/测试 | 三分划分 |
| `SimpleTree` | 类 | 用字典表示节点的回归树，候选阈值为 10%–90% 分位数 | 被调模型的基学习器 |
| `GBMForTuning` | 类 | 梯度提升，暴露 5 个超参数（含行采样 `subsample`） | 被调模型 |
| `neg_mse` | 函数 | 负 MSE，越大越好 | 统一"最大化"约定 |
| `grid_search` | 函数 | 穷举网格，返回最优参数、分数和历史 | Grid Search |
| `sample_param` | 函数 | 按规格采样：类别列表 / `int` / `float` / `log_float` | 搜索空间与采样尺度 |
| `random_search` | 函数 | 采样 n_iter 组参数并评估 | Random Search |
| `SimpleBayesianOptimizer` | 类 | 参数向量化、RBF 核 GP、EI、`suggest/observe/optimize` | Bayesian Optimization |
| `convergence_curve` | 函数 | 把历史转成"截至第 i 次的最优分数" | 收敛曲线 |
| `demo_*`（5 个） | 函数 | 网格、随机、贝叶斯、三方对比、Optuna | — |

数据流：`make_data` → 搜索函数产生一组组超参数 → `GBMForTuning(**params).fit(训练集)` → `neg_mse(验证集)` 打分 → 记录历史、更新最优 → 最优参数在训练集上重训，并在测试集上报告一次。

---

## 3. 逐段精讲

### 3.1 数据与三分划分

```python
def make_data(n_samples=400, n_features=8, seed=42):
    rng = np.random.RandomState(seed)
    X = rng.randn(n_samples, n_features)
    y = (
        2.0 * X[:, 0]
        + np.sin(3 * X[:, 1])
        - 0.5 * X[:, 2] ** 2
        + 0.3 * X[:, 3] * X[:, 4]
        + rng.normal(0, 0.3, n_samples)
    )
    split = int(n_samples * 0.6)
    val_split = int(n_samples * 0.8)
```

- 目标包含线性项、正弦、平方、交互项，后 3 个特征是纯噪声——树模型需要足够的深度/树数量才能拟合，超参数确实"有得调"。
- 噪声标准差 0.3，不可约误差约 0.09，是验证 MSE 的理论下限。
- 按位置切成 240 / 80 / 80。因为样本是独立同分布生成的，不打乱也没问题；真实数据必须先打乱（或按时间切）。
- 三分的意义：**验证集用来选超参数，测试集只在最后报告一次**——所有 demo 都遵循了这一点。

### 3.2 `SimpleTree`：用字典表示的回归树

```python
    def _build(self, X, y, depth):
        if depth >= self.max_depth or len(y) < self.min_samples_split:
            return {"value": np.mean(y)}
        # ...
        for f in range(n_features):
            thresholds = np.percentile(X[:, f], np.linspace(10, 90, 10))
            for t in thresholds:
                left = y[X[:, f] <= t]
                right = y[X[:, f] > t]
                if len(left) < 2 or len(right) < 2:
                    continue
                gain = var_total - np.var(left) * len(left) - np.var(right) * len(right)
```

- 分裂准则与上一节相同：平方误差和（`方差 × 样本数`）的下降量。
- 候选阈值固定为 10%–90% 之间的 10 个分位数，每个节点最多评估 `特征数 × 10` 个切分，换取速度；每侧至少 2 个样本。
- `min_samples_split` 是被调的超参数之一：节点样本少于它就直接成为叶子，是一种预剪枝正则化。
- 叶子是 `{"value": 均值}`，内部节点是 `{"feature", "threshold", "left", "right"}`。预测时用 `"value" in node` 判断是否为叶子——用**键是否存在**来判断，不会被均值恰好为 0.0 这种情况误导（对比上一节 `TreeNode` 必须小心使用 `is not None`）。

### 3.3 `GBMForTuning`：被调的模型

```python
    def fit(self, X, y):
        rng = np.random.RandomState(42)
        self.init_pred = np.mean(y)
        pred = np.full(len(y), self.init_pred)

        for _ in range(self.n_estimators):
            residuals = y - pred

            if self.subsample < 1.0:
                n_sub = max(1, int(len(y) * self.subsample))
                idx = rng.choice(len(y), n_sub, replace=False)
                X_sub, r_sub = X[idx], residuals[idx]
            else:
                X_sub, r_sub = X, residuals
            # ...
            tree.fit(X_sub, r_sub)
            pred += self.learning_rate * tree.predict(X)
```

- 与上一节的梯度提升相同，只是把 5 个"旋钮"都暴露为构造参数：`n_estimators`、`learning_rate`、`max_depth`、`min_samples_split`、`subsample`。
- **`subsample`（随机梯度提升）**：每棵树只在不放回抽取的一部分样本上拟合残差，但更新预测时对**全部样本**调用 `tree.predict(X)`。这给每棵树注入随机性，起到降方差的正则化作用。
- `rng = np.random.RandomState(42)` 写在 `fit` 内部：同一组超参数无论训练多少次结果都完全一样，所以不同搜索方法之间的差别只来自"选了哪些超参数"，而不是训练的随机性。代价是无法评估"同一组超参数在不同随机种子下的波动"。
- ⚠️ `fit` 没有清空 `self.trees`；本文件每次都新建模型，所以不受影响。

```python
def neg_mse(model, X, y):
    pred = model.predict(X)
    return -np.mean((pred - y) ** 2)
```

返回**负** MSE，让所有搜索函数统一做"最大化"——这与 sklearn 的 `scoring="neg_mean_squared_error"` 约定一致。打印时再取负号还原成 MSE。

### 3.4 `grid_search`：`itertools.product` 穷举

```python
def grid_search(param_grid, X_train, y_train, X_val, y_val):
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    best_score = -float("inf")
    best_params = None
    history = []

    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        model = GBMForTuning(**params)
        model.fit(X_train, y_train)
        score = neg_mse(model, X_val, y_val)
        history.append((params.copy(), score))
```

- `itertools.product(*values)`：`*` 把列表"拆开"作为多个参数传入，`product([20, 50, 100], [0.01, …], [2, 3, 5])` 依次产生所有 3 × 4 × 3 = 36 个组合元组。
- `dict(zip(keys, combo))`：把 `('n_estimators', 'learning_rate', 'max_depth')` 与 `(20, 0.01, 2)` 配对成字典，再用 `**params` 解包成关键字参数传给模型构造函数。这是"超参数字典 → 模型"的通用写法。
- `history` 保存每次的 `(参数, 分数)`，后面用来画收敛曲线。`.copy()` 是防御式写法，避免以后修改字典时历史记录被连带改动。
- 网格的遍历顺序是字典序（先固定 `n_estimators=20` 把其他组合走一遍），所以"前 k 次"的结果高度依赖排列顺序——这会影响第 6 节收敛曲线的解读。

### 3.5 `sample_param`：搜索空间的规格与对数尺度

```python
def sample_param(spec, rng):
    if isinstance(spec, list):
        return rng.choice(spec)
    name, low, high = spec[0], spec[1], spec[2]
    if name == "int":
        return rng.randint(low, high + 1)
    if name == "float":
        return rng.uniform(low, high)
    if name == "log_float":
        return np.exp(rng.uniform(np.log(low), np.log(high)))
    return low
```

| 规格 | 采样方式 | 典型用途 |
|------|---------|---------|
| `[a, b, c]` | 等概率选一个 | 类别型（激活函数、优化器） |
| `("int", lo, hi)` | 闭区间整数均匀；`randint` 上界是开区间，所以 `hi + 1` | 树深、树的数量 |
| `("float", lo, hi)` | 线性均匀 | `subsample` 这类在线性尺度上起作用的参数 |
| `("log_float", lo, hi)` | 先在 `[ln lo, ln hi]` 上均匀采样再取指数 | 学习率、正则强度 |

- **为什么学习率要用 log_float**：`("log_float", 0.005, 0.5)` 下，`lr < 0.05` 的概率是 50%，每个数量级概率相同；若用线性均匀，概率只有约 9%，几乎所有试验都挤在 0.05–0.5（测验 Q8 有模拟验证）。
- 这个"规格元组"的设计和 Optuna 的 `suggest_int` / `suggest_float(log=True)` / `suggest_categorical` 一一对应。
- ⚠️ 未知规格名时静默返回 `low`，拼错 `"log_flaot"` 不会报错，只会悄悄地让这个超参数恒定不变；生产代码应该 `raise ValueError`。

### 3.6 `random_search`

```python
    for _ in range(n_iter):
        params = {k: sample_param(v, rng) for k, v in param_distributions.items()}
        int_params = {}
        for k, v in params.items():
            if k in ("n_estimators", "max_depth", "min_samples_split"):
                int_params[k] = int(v)
            else:
                int_params[k] = v
```

- 字典推导式一次采样所有超参数；每次试验各维度都是新值，这就是讲义所说"同样预算下覆盖更密"的来源。
- 把整数型超参数显式转成 `int`：对 `random_search` 来说是防御性的（`randint` 本身返回整数），但在贝叶斯优化里，同样的转换写了三遍（`demo_bayesian` 的 `objective`、打印前、`demo_comparison` 的字典推导），可以抽成一个公共函数。
- 种子固定为 42，所以不同 `n_iter` 的调用之间是**前缀关系**：`n_iter=25` 的前 10 次与 `n_iter=10` 完全一样（测验 Q10）。

### 3.7 `SimpleBayesianOptimizer`：GP + EI

**(1) 把超参数映射到单位超立方体**

```python
    def _params_to_vec(self, params):
        vec = []
        for k in self.param_names:
            v = params[k]
            spec = self.param_space[k]
            if isinstance(spec, list):
                vec.append(spec.index(v) / max(1, len(spec) - 1))
            elif spec[0] == "log_float":
                vec.append(
                    (np.log(v) - np.log(spec[1])) / (np.log(spec[2]) - np.log(spec[1]))
                )
            else:
                vec.append((v - spec[1]) / max(1e-10, spec[2] - spec[1]))
        return np.array(vec)
```

- 每个维度都被缩放到 [0, 1]，`log_float` 先取对数再缩放。这样 RBF 核里的"距离"在各维度上可比，且学习率从 0.005 到 0.05 与从 0.05 到 0.5 在 GP 眼里距离相同——与采样尺度保持一致。
- ⚠️ 类别型参数被编码成 `下标 / (类别数 − 1)`，相当于给无序类别强加了顺序和距离，这是简化。

**(2) RBF 核与 GP 后验**

```python
    def _rbf_kernel(self, X1, X2, length_scale=0.3):
        dists = np.sum((X1[:, None, :] - X2[None, :, :]) ** 2, axis=2)
        return np.exp(-0.5 * dists / length_scale ** 2)

    def _predict(self, X_new):
        # ...
        K = self._rbf_kernel(X_obs, X_obs) + 1e-4 * np.eye(len(X_obs))
        K_star = self._rbf_kernel(X_new, X_obs)

        try:
            L = np.linalg.cholesky(K)
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_centered))
            mu = K_star @ alpha + y_mean
            v = np.linalg.solve(L, K_star.T)
            var = 1.0 - np.sum(v ** 2, axis=0)
            var = np.maximum(var, 1e-6)
        except np.linalg.LinAlgError:
            # ... 退化为伪逆，方差固定 0.1
```

- **广播求两两距离**：`X1[:, None, :]` 形状 `(n1, 1, d)`，`X2[None, :, :]` 形状 `(1, n2, d)`，相减得到 `(n1, n2, d)`，沿最后一维求平方和得到 `(n1, n2)` 的距离矩阵——不写循环的标准技巧。
- **后验均值** `μ = K*·K⁻¹·(y − ȳ) + ȳ`：先对 y 去均值（相当于先验均值取观测平均），再加回来。
- **Cholesky 解法**：`K = L·Lᵀ`，用两次三角求解代替求逆，数值更稳、更快。`v = L⁻¹·K*ᵀ`，于是 `K*·K⁻¹·K*ᵀ` 的对角线就是 `sum(v ** 2, axis=0)`，后验方差 = 先验方差 1 减去它。
- `1e-4 * np.eye(...)`：给对角线加一点"噪声/抖动"，既表示观测有噪声，也防止重复点让矩阵奇异。已观测点处的后验方差约等于这个值，远离所有观测时方差回到 1。
- ⚠️ 简化：长度尺度固定 0.3、信号方差固定 1，没有像正式实现那样通过最大化边际似然来学习；y 只减了均值没有除以标准差，分数的尺度会影响探索与利用的平衡。

**(3) Expected Improvement**

```python
    def _expected_improvement(self, mu, var, best_y):
        sigma = np.sqrt(var)
        z = (mu - best_y) / (sigma + 1e-10)
        ei = sigma * (z * self._norm_cdf(z) + self._norm_pdf(z))
        return ei
```

- 展开就是 `(μ − y*)·Φ(z) + σ·φ(z)`：第一项奖励"预测更好"（利用），第二项奖励"不确定性大"（探索）。
- ⚠️ `_norm_cdf` 用的是 `0.5·(1 + tanh(√(2/π)·x))` 近似，最大绝对误差约 0.018；而且 `np.vectorize` 包一层 `np.tanh` 完全没必要（`np.tanh` 本身就是逐元素的）。精确写法见测验 Q9。

**(4) `suggest` / `observe` / `optimize`**

```python
    def suggest(self):
        if len(self.X_observed) < self.n_initial:
            return self._sample_random()

        n_candidates = 500
        candidates = [self._sample_random() for _ in range(n_candidates)]
        X_cand = np.array([self._params_to_vec(c) for c in candidates])

        mu, var = self._predict(X_cand)
        best_y = max(self.y_observed)
        ei = self._expected_improvement(mu, var, best_y)

        best_idx = np.argmax(ei)
        return candidates[best_idx]
```

- 前 `n_initial = 10` 次纯随机，给 GP 一些"起始数据"（冷启动）。
- 之后每一步：随机生成 500 个候选点，用 GP 预测、算 EI，取最大者。这是"用随机采样近似最大化采集函数"——简单粗暴但有效；正式库会在采集函数上做多起点的梯度优化。
- `optimize` 是一个标准的 ask-tell 循环：`suggest`（问下一个点）→ 评估目标函数 → `observe`（告诉结果），与 Optuna 的 `study.ask()` / `study.tell()` 思路一致。

### 3.8 演示函数

- **`demo_grid_search`**：36 个组合，打印最优参数、验证 MSE、耗时和测试 MSE。最优参数在训练集上重训后只评估一次测试集。⚠️ 讲义建议"用最佳超参数在全部训练数据上重训"，这里只用了训练集（240 条），没有并上验证集（80 条）。
- **`demo_random_search`**：5 个超参数（比网格多 `min_samples_split`、`subsample`），预算 10/25/50/100，再额外跑一次 100 次。由于种子相同，这些调用是前缀关系，一共训练了 285 个模型，其中 185 个是重复计算（测验 Q10 给出用 `convergence_curve` 一次搞定的写法）。
- **`demo_bayesian`**：同样的 5 维空间、50 次评估。
- **`demo_comparison`**：三种方法用**相同的评估次数**（= 网格大小 36）比较，并打印第 6、11、21、36 次时的 best-so-far。⚠️ 公平性的细节：网格只能取 36 个离散点，而随机和贝叶斯在连续的更大空间里搜（`n_estimators` 可到 200、`max_depth` 可到 8），所以这不只是"策略"之差，也是"搜索空间"之差。
- **`demo_optuna`**：`try: import optuna`，没装就打印提示并跳过；装了则跑 50 次 TPE 搜索，并用 `optuna.importance.get_param_importances` 打印各超参数的重要性条形图（`"#" * int(v * 40)`）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 统一最大化 `neg_mse` | 三种搜索共用"分数越大越好" | 与 sklearn 约定一致；打印时要记得取负 |
| `GBMForTuning.fit` 固定种子 | 同一组超参结果确定，比较只反映搜索策略 | 看不到随机种子带来的波动；严肃比较应多种子平均 |
| 规格元组 `("log_float", lo, hi)` | 简洁地描述分布与尺度 | 未知规格静默返回 `low`；Optuna/Hyperopt 有更完整的空间定义 |
| 参数归一化到 [0, 1] 再进 GP | 让 RBF 距离在各维度可比 | 类别型被强行赋予顺序 |
| GP 超参数（ℓ = 0.3、方差 1）写死 | 代码短、无需额外优化 | 对目标尺度敏感；正式实现最大化边际似然 |
| 500 个随机候选取 EI 最大 | 不需要梯度，易实现 | 高维时候选太稀疏；库中用多起点优化 |
| Cholesky + 抖动 1e-4，失败退回伪逆 | 数值稳定、可兜底 | 退回分支方差恒为 0.1，EI 失去意义 |
| tanh 近似正态 CDF | 不依赖 SciPy | 最大误差约 0.018；用 `math.erf` 即可精确 |
| 纯 Python 递归树 + 大量试验 | 让每一步都可见 | 完整运行约 30 分钟；真实调参用 LightGBM/XGBoost + 并行 + 剪枝 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 多返回值 | `return (X[:split], y[:split], ...)`；`X_tr, y_tr, X_val, y_val, X_te, y_te = make_data()` | 一次返回 6 个数组并解包 |
| 字典作为树节点 | `{"value": np.mean(y)}`；`if "value" in node:` | 用 `in` 判断键是否存在 |
| `itertools.product` + `*` 解包 | `itertools.product(*values)` | 笛卡尔积；`*` 把列表展开成多个位置参数 |
| `dict(zip(...))` | `params = dict(zip(keys, combo))` | 把两个序列配对成字典 |
| `**` 解包关键字参数 | `GBMForTuning(**params)` | 字典 → 关键字参数 |
| 字典推导式（含条件表达式） | `{k: int(v) if k in ("n_estimators", "max_depth") else v for k, v in params.items()}` | 一行构造并按条件转换值 |
| `isinstance` | `isinstance(spec, list)`、`isinstance(v, float)` | 运行时判断类型，分派不同逻辑 |
| `list.index` | `spec.index(v)` | 返回元素首次出现的下标 |
| `.copy()` | `params.copy()` | 浅拷贝字典，避免共享引用 |
| `@staticmethod` | `_norm_cdf`、`_norm_pdf` | 不需要 `self` 的方法，仍可通过 `self._norm_cdf` 调用 |
| `np.vectorize` + `lambda` | `np.vectorize(lambda v: np.tanh(v * 0.7978845608))(x)` | 把标量函数包装成可作用于数组的函数（本质是循环） |
| 广播与 `None` 增维 | `X1[:, None, :] - X2[None, :, :]` | 生成所有点对的差，得到三维数组 |
| `np.linalg` | `cholesky`、`solve`、`pinv` | 矩阵分解、解线性方程组、伪逆 |
| `try` / `except` 具体异常 | `except np.linalg.LinAlgError:`；`except ImportError:` | 数值失败时兜底；可选依赖缺失时跳过 |
| 闭包 | `demo_bayesian` 内的 `def objective(params):` 使用外层的 `X_tr` 等 | 内部函数"记住"外部变量，可作为回调传给 `optimize` |
| 函数内 `import` | `import optuna` 写在 `demo_optuna` 内 | 可选依赖只在需要时导入 |
| `time.time()` | `start = time.time()` … `elapsed = time.time() - start` | 测耗时（更推荐 `time.perf_counter()`） |
| f-string 格式 | `f"{n_iter:>3d}"`、`f"{-best_score:.4f}"`、`f"{k:>20s}"`、`f"{'-'*6}"` | 右对齐、保留小数、在花括号里写表达式 |
| 字符串重复 | `"#" * int(v * 40)` | 用字符画条形图 |

---

## 6. 运行结果解读

> 运行说明：按规范先在临时副本中以 `timeout 60` 运行，仅完成了网格搜索部分（单是 36 个组合就用了约 51 秒）。为了拿到其余演示的真实输出，又在临时副本中不限时完整运行了一次（共两次）。本环境**未安装 optuna**，最后一个演示被跳过。

完整运行总耗时约 30 分钟（期间机器上还有其他任务，仅供量级参考）。

```text
=== GRID SEARCH ===
  Total combinations: 36
  Best params: {'n_estimators': 100, 'learning_rate': 0.3, 'max_depth': 2}
  Best val neg_mse: -0.5412 (MSE = 0.5412)
  Time: 53.6s
  Test MSE: 0.4581
```

- 36 个组合花了约 54 秒。最优组合的三个值**全部落在网格边界**：树的数量取了最大值 100、学习率取了最大值 0.3、深度取了最小值 2。这是讲义"搜索范围太窄"的典型信号——真正的最优很可能在网格之外（更多的树、更浅的树）。
- 测试 MSE 0.4581 比验证 MSE 0.5412 还低，说明这 80 个验证样本恰好偏"难"。小验证集上的分数噪声很大，这也是为什么挑出来的最优分数不能直接当最终结果。

```text
=== RANDOM SEARCH ===
  n_iter= 10  best_mse=0.7870  time=36.7s
  n_iter= 25  best_mse=0.5172  time=100.8s
  n_iter= 50  best_mse=0.5172  time=214.3s
  n_iter=100  best_mse=0.5172  time=374.8s

  Best params (100 trials):
    n_estimators: 184
    learning_rate: 0.1335
    max_depth: 2
    min_samples_split: 6
    subsample: 0.7806
  Test MSE: 0.4172
```

- `best_mse` 单调不增，且 25 次之后就没再改进——各次调用是前缀关系（见 3.6）。第 25 次以内找到的那组就是 100 次里的最优。
- 平均每次试验约 3.7 秒，比网格慢，因为随机搜索会采到 `n_estimators` 接近 200、`max_depth` 到 8 的昂贵配置。
- 最优配置与网格的结论一致：很浅的树（深度 2）+ 较多的树 + 中等学习率。5 维空间里随机搜索用 25 次就超过了 36 个格点的网格（0.5172 vs 0.5412）。

```text
=== BAYESIAN OPTIMIZATION ===
  Best params (50 trials):
    n_estimators: 187
    learning_rate: 0.1842
    max_depth: 2
    min_samples_split: 20
    subsample: 0.9485
  Best val MSE: 0.4442
  Test MSE: 0.3711
```

- 50 次贝叶斯优化的最优验证 MSE 0.4442，明显好于 100 次随机搜索的 0.5172，测试 MSE 也最低（0.3711）。前 10 次是随机初始化，之后 40 次由 GP + EI 引导。
- 又是边界：`min_samples_split=20` 是上限、`max_depth=2` 是下限、`n_estimators=187` 逼近上限 200。在这份数据上，"更强的正则化（浅树、大叶子）+ 更多的树"是方向，搜索空间应该朝这个方向扩展。

```text
=== HEAD-TO-HEAD: GRID vs RANDOM vs BAYESIAN ===
  Budget: 36 evaluations each
  Grid search   best MSE: 0.5412
  Random search best MSE: 0.5411
  Bayesian opt  best MSE: 0.4836

    Eval    Grid MSE  Random MSE   Bayes MSE
       6      2.5292      1.5381      1.5381
      11      0.8460      1.5381      1.2383
      21      0.8460      0.8613      0.5150
      36      0.5412      0.5411      0.4836
```

- 同样 36 次评估：随机搜索与网格打平（0.5411 vs 0.5412），贝叶斯优化最好（0.4836）。在只有 3 个超参数、且网格恰好覆盖了好区域边缘的情况下，随机搜索的优势并不明显——讲义也说"网格只在超参数很少时有竞争力"。
- **第 6 次时随机搜索和贝叶斯优化完全相同（1.5381）**：两者都用 `RandomState(42)`，并以相同顺序对同样的三个超参数采样，贝叶斯优化的前 `n_initial=10` 次就是随机搜索的前 10 次。从第 11 次开始贝叶斯优化由 GP 选点，立刻拉开差距（1.2383 vs 1.5381），到第 21 次已降到 0.5150，而随机搜索还在 0.8613——**"利用历史结果"带来的收敛速度优势**在这张表里一目了然。
- 网格前几次很差（第 6 次 2.5292），因为字典序遍历先跑的都是 `n_estimators=20` 加小学习率的欠拟合组合；网格的收敛曲线形状完全取决于遍历顺序。

```text
=== OPTUNA (if installed) ===
  Optuna not installed. Install with: pip install optuna
  Skipping Optuna demo.

All tuning demos complete.
```

本环境没有安装 optuna，演示按设计跳过。

---

## 7. 动手改一改

1. **去掉重复计算**：按测验 Q10，用一次 100 次随机搜索 + `convergence_curve` 打印 4 个预算下的结果，计时对比。
2. **精确的正态 CDF**：用 `math.erf` 替换 `_norm_cdf`（测验 Q9），去掉无用的 `np.vectorize`，看看 BO 的结果是否变化。
3. **标准化 y**：在 `_predict` 中把 `y_centered` 再除以 `y_obs.std()`，预测完再乘回去（方差也要乘以 `std²`），对比贝叶斯优化的收敛曲线。
4. **实现 successive halving**：以 `n_estimators` 作为预算（例如 10 → 30 → 90 棵树），81 个随机配置，保留前 1/3，统计总训练树数并与"81 个配置都训练 90 棵树"对比（测验 Q11 给出通用版本）。
5. **检查边界**：给 `grid_search` 加一个检查，若最优值落在某个维度的最小或最大取值上，打印警告；再按警告扩大网格重跑。
6. **更公平的比较**：让三种方法使用同一个搜索空间（例如网格就取连续空间上的均匀格点），并对随机搜索和贝叶斯优化各换 5 个种子取平均 best-so-far 曲线。

---

## 8. 常见坑

- **线性尺度搜学习率**：大部分试验会挤在最大的那个数量级。学习率、正则强度用 log-uniform。
- **最优值落在边界不自知**：本次网格搜索的三个最优值全部在边界上，说明范围太窄。
- **用验证集选完超参又用它报告结果**：打印的 "Best val MSE" 是被挑选过的乐观值，最终性能看测试集（只看一次）或嵌套 CV。
- **重复计算**：固定种子 + 不同预算多次从头跑，结果是前缀关系，完全可以只跑最大预算一次。
- **规格拼写错误被静默吞掉**：`sample_param` 遇到未知类型返回 `low`，该超参数会悄悄地固定不变。
- **以为装了库的 demo 一定会跑**：`demo_optuna` 在未安装时会跳过；剪枝功能也必须在训练过程中多次 `trial.report` 才会生效（测验 Q16）。
