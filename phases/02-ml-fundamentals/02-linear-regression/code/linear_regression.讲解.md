# 代码讲解 · linear_regression.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 02 节 线性回归 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python linear_regression.py`（无命令行参数，是一个从上到下顺序执行的脚本） ｜ **依赖**：从零实现部分仅用 Python 标准库（`random`；`math` 被导入但未使用）；最后的对照部分可选用 `numpy` + `scikit-learn`，没装时会被 `try/except ImportError` 跳过

---

## 1. 这份代码在考察什么

1. **ML 训练循环的最小完整形态**：模型 `ŷ = wx + b` → 损失 MSE → 梯度 → 参数更新 → 重复。后面从逻辑回归到神经网络，都是这个循环。
2. **两种求解方式的对照**：迭代的梯度下降 vs 一步到位的闭式解，并借此学会"用闭式解检验 GD 是否收敛"。
3. **多元回归 + 特征标准化**：三个量纲完全不同的房屋特征，标准化后才能用同一个学习率训练。
4. **多项式回归**：用 `x, x², …` 做特征，仍然是"线性"回归；阶数越高训练 R² 越高，但不代表更好。
5. **Ridge 正则**：在损失里加 `α·Σw²`，梯度里多出 `2αw`，观察权重被收缩。
6. **评估**：R² 的手写实现，以及训练/测试切分后的对比。

> 一句话：**所有模型都是纯 Python 列表 + 循环写成的**，没有任何"魔法"——每一个梯度公式都能在代码里逐字对上。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 顶部数据生成 | 脚本 | `y = 3x + 7 + N(0, 2²)`，100 个点 | 合成数据 + 已知真值 |
| `LinearRegression` | 类 | 一元回归，批量梯度下降 | MSE、梯度、学习率 |
| `LinearRegressionNormal` | 类 | 一元回归闭式解 | 正规方程（一元形式） |
| `MultipleLinearRegression` | 类 | 多元回归，逐特征计算梯度 | 超平面拟合 |
| `standardize` | 函数 | 每列减均值除标准差 | 特征缩放 |
| `PolynomialRegression` | 类 | 自动构造 `x¹…x^degree` 特征后做 GD | 多项式回归 |
| `RidgeRegression` | 类 | 多元回归 + L2 惩罚 | 正则化 |
| 训练/测试切分段 | 脚本 | 前 80 个训练、后 20 个测试 | 泛化评估 |
| sklearn 对照段 | 脚本（可选） | 用库函数做同类实验 | 生产中的写法 |

执行顺序就是文件顺序：生成一元数据 → GD 训练 → 闭式解 → 生成房价数据并标准化 → 多元 GD → 多项式（2 阶 vs 5 阶）→ Ridge → 切分评估 → sklearn。

---

## 3. 逐段精讲

### 3.1 生成数据：已知答案的"考卷"

```python
TRUE_W = 3.0
TRUE_B = 7.0
N_SAMPLES = 100

random.seed(42)
X = [random.uniform(0, 10) for _ in range(N_SAMPLES)]
y = [TRUE_W * x + TRUE_B + random.gauss(0, 2.0) for x in X]
```

- 用合成数据的好处：**真实参数已知**，可以直接检查学到的 w、b 对不对。
- `random.gauss(0, 2.0)` 加入标准差为 2 的高斯噪声。正因为有噪声，即使完美优化，学到的也不会恰好是 3 和 7。
- `random.seed(42)` 固定随机序列，每次运行结果相同。
- `_` 是约定俗成的"我不需要这个循环变量"。

### 3.2 `LinearRegression`：梯度下降的五个动作

```python
    def predict(self, X):
        return [self.w * x + self.b for x in X]

    def compute_cost(self, X, y):
        predictions = self.predict(X)
        n = len(y)
        cost = sum((pred - actual) ** 2 for pred, actual in zip(predictions, y)) / n
        return cost

    def compute_gradients(self, X, y):
        predictions = self.predict(X)
        n = len(y)
        dw = (2 / n) * sum((pred - actual) * x for pred, actual, x in zip(predictions, y, X))
        db = (2 / n) * sum(pred - actual for pred, actual in zip(predictions, y))
        return dw, db
```

梯度公式的来历（链式法则）：`MSE = (1/n)Σ(ŷᵢ − yᵢ)²`，对 w 求导，外层平方给出 `2(ŷᵢ − yᵢ)`，内层 `ŷᵢ = wxᵢ + b` 对 w 的导数是 `xᵢ`，对 b 的导数是 1：

| 代码 | 公式 | 直觉 |
|------|------|------|
| `dw` | `(2/n)·Σ(ŷ−y)·x` | 误差 × 输入：x 越大的样本对 w 的"责任"越大 |
| `db` | `(2/n)·Σ(ŷ−y)` | 平均误差：整体偏高就把 b 往下调 |

- `zip(predictions, y, X)` 一次把三个列表按位置配对。
- 注意 `pred - actual`（预测减真实）的顺序：这样梯度的符号直接可用，更新时用减号。顺序写反，梯度就反了，模型会越训越差。

```python
    def fit(self, X, y, epochs=1000, print_every=200):
        for epoch in range(epochs):
            dw, db = self.compute_gradients(X, y)
            self.w -= self.lr * dw
            self.b -= self.lr * db
            cost = self.compute_cost(X, y)
            self.cost_history.append(cost)
            if epoch % print_every == 0:
                print(...)
        return self
```

- **批量梯度下降**：每一步都用全部 100 个样本算梯度。
- w 和 b 用的是**同一时刻**算出的梯度（先算好 `dw, db` 再一起更新），这是"同时更新"，不能先更新 w 再用新 w 算 b 的梯度。
- `cost_history` 记录每轮损失，方便画学习曲线。
- `return self` 允许链式写法 `LinearRegression().fit(X, y).predict(...)`，这是 sklearn 的惯例。
- ⚠️ `lr=0.005`、1000 轮**并没有收敛**：学到 `3.1433x + 6.5432`，而这份数据上的最优解是 `3.0756x + 6.9853`。原因是 x 在 [0,10] 未中心化，w 与 b 强耦合，损失曲面狭长（Hessian 条件数约 121），b 方向走得极慢。把 lr 提到 0.02（稳定上限约 0.031），或先对 x 中心化，1000 轮内就能收敛。

### 3.3 `r_squared`：比"猜均值"好多少

```python
    def r_squared(self, X, y):
        predictions = self.predict(X)
        y_mean = sum(y) / len(y)
        ss_res = sum((actual - pred) ** 2 for actual, pred in zip(y, predictions))
        ss_tot = sum((actual - y_mean) ** 2 for actual in y)
        return 1 - (ss_res / ss_tot)
```

- `ss_tot` 是"永远预测均值"这个最笨模型的误差平方和，`ss_res` 是本模型的。R² 就是"模型把笨模型的误差消掉了多少比例"。
- 和 MSE 不同，R² 与 y 的量纲无关，便于跨任务比较。
- ⚠️ 这里 `y_mean` 用的是**被评估数据自己的均值**（与 sklearn 的 `r2_score` 相同）。测试集上若 `ss_tot` 为 0（所有 y 相同）会除以零。
- 这个方法在 4 个类里被复制了 4 次——为了让每个类能独立阅读；工程上应抽成一个公共函数。

### 3.4 `LinearRegressionNormal`：一元闭式解

```python
    def fit(self, X, y):
        n = len(X)
        x_mean = sum(X) / n
        y_mean = sum(y) / n
        numerator = sum((X[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((X[i] - x_mean) ** 2 for i in range(n))
        self.w = numerator / denominator
        self.b = y_mean - self.w * x_mean
        return self
```

- 这是正规方程 `w = (XᵀX)⁻¹Xᵀy` 在**单特征**时的展开：`w = cov(x, y) / var(x)`，`b = ȳ − w·x̄`。
- `b = ȳ − w·x̄` 说明拟合直线必过均值点 (x̄, ȳ)。
- 先减均值再相乘（"中心化"写法）比直接用 `Σxy − n·x̄·ȳ` 数值上更稳定，避免两个大数相减丢精度。
- ⚠️ 所有 x 都相同时 `denominator = 0`，会抛 `ZeroDivisionError`——此时斜率本来就无法确定。
- 讲义标题叫 Normal Equation，但代码并没有构造矩阵求逆；多特征的矩阵版本可用 `np.linalg.lstsq` 实现。

### 3.5 多元回归 + 标准化

```python
def standardize(X):
    n_features = len(X[0])
    n_samples = len(X)
    means = [sum(X[i][j] for i in range(n_samples)) / n_samples for j in range(n_features)]
    stds = []
    for j in range(n_features):
        variance = sum((X[i][j] - means[j]) ** 2 for i in range(n_samples)) / n_samples
        stds.append(variance ** 0.5)
    X_scaled = []
    for i in range(n_samples):
        row = [(X[i][j] - means[j]) / stds[j] if stds[j] > 0 else 0 for j in range(n_features)]
        X_scaled.append(row)
    return X_scaled, means, stds
```

- 数据：面积 500–3000、卧室 1–5、房龄 0–50，量纲相差上千倍；价格是几十万的量级。
- 每列 `(x − mean)/std`，标准差用的是**总体标准差**（除以 n，与 NumPy `std` 默认一致）。
- `if stds[j] > 0 else 0` 是条件表达式：常数列标准差为 0，直接置 0 避免除零。
- 返回 `means, stds` 是为了以后把**同一套**统计量用在新数据上。⚠️ 本脚本在全部 100 条数据上做标准化、也在同一份数据上评估 R²，没有切分；真实项目中统计量只能用训练集计算。
- y 也被标准化了（`y_scaled`），所以学到的权重是"特征变化 1 个标准差，价格变化多少个标准差"。

```python
    def fit(self, X, y, epochs=1000, print_every=200):
        n = len(y)
        n_features = len(X[0])
        for epoch in range(epochs):
            predictions = self.predict(X)
            errors = [pred - actual for pred, actual in zip(predictions, y)]
            for j in range(n_features):
                grad = (2 / n) * sum(errors[i] * X[i][j] for i in range(n))
                self.weights[j] -= self.lr * grad
            grad_b = (2 / n) * sum(errors)
            self.bias -= self.lr * grad_b
```

- 先算好整轮的 `errors`，再对每个特征 j 求 `(2/n)·Σ errorᵢ·xᵢⱼ`。由于 `errors` 在循环外算好，更新 `weights[0]` 不影响 `weights[1]` 的梯度，仍是"同时更新"。
- 向量化写法就是 `grad = (2/n)·Xᵀ·errors`，复杂度 O(n·d)。
- 输出的 `Bias (standardized): 0.0000` 不是巧合：X 每列和 y 都均值为 0，推导可得 `grad_b = 2b`，b 从 0 出发就永远是 0。

### 3.6 多项式回归

```python
    def make_features(self, X):
        return [[x ** (d + 1) for d in range(self.degree)] for x in X]
```

- 嵌套列表推导：每个 x 变成 `[x¹, x², …, x^degree]`。`d + 1` 是因为 `range` 从 0 开始，而 x⁰=1 的常数项已由 `bias` 负责。
- 之后的 `fit` 与多元回归一模一样——这就是"多项式回归 = 在新特征上做线性回归"。
- 数据预处理：`X_poly_norm = x / x_max` 把 x 压到 [0, 0.98]，避免 `x⁵` 数值爆炸；y 做了标准化。
- ⚠️ 在 [0,1] 上 `x, x², …, x⁵` 彼此高度相关，损失曲面极其狭长，2000 轮 GD 仍未收敛（2 阶闭式解训练 R² 约 0.678，GD 只到 0.6408）。生产中会用闭式解、正交多项式或 sklearn 的 `PolynomialFeatures` + `LinearRegression`。
- ⚠️ 这里打印的 cost 是用**更新前**的 `errors` 算的，而 `LinearRegression` 打印的是更新后的 cost，两者口径不同（不影响结果）。

### 3.7 Ridge：梯度里多一项 `2αw`

```python
            mse = sum(e ** 2 for e in errors) / n
            reg_term = self.alpha * sum(w ** 2 for w in self.weights)
            cost = mse + reg_term
            for j in range(n_features):
                grad = (2 / n) * sum(errors[i] * X[i][j] for i in range(n))
                grad += 2 * self.alpha * self.weights[j]
                self.weights[j] -= self.lr * grad
            grad_b = (2 / n) * sum(errors)
            self.bias -= self.lr * grad_b
```

- `α·Σw²` 对 wⱼ 求导是 `2αwⱼ`，与代码完全对应。整理一下更新式：`w ← (1 − 2·lr·α)·w − lr·∂MSE`，每一步先把 w 按比例"衰减"一点——这就是深度学习里 **weight decay** 名字的由来。
- 偏置 `grad_b` **没有**正则项：惩罚 b 只会阻止模型拟合 y 的整体平移，没有防过拟合的作用。
- 收敛结果 `[0.7052, 0.2647, -0.2558]` 与闭式解 `(XᵀX/n + αI)⁻¹Xᵀy/n` 完全一致。
- ⚠️ 本实现的惩罚没有除以 n，与 sklearn 的约定不同：sklearn `Ridge` 最小化 `|y − Xw|² + alpha·|w|²`，因此这里的 `alpha=0.1` 相当于 sklearn 的 `alpha = 0.1 × 100 = 10`。

### 3.8 训练/测试切分与 sklearn 对照

```python
split_idx = int(0.8 * len(X))
X_train, X_test = X[:split_idx], X[split_idx:]
y_train, y_test = y[:split_idx], y[split_idx:]
```

- 直接按顺序切前 80 / 后 20。因为数据本来就是独立随机生成的，顺序切等价于随机切；真实数据（可能按时间或类别排序）必须先打乱，时间序列则必须按时间切。
- 结果测试 R²（0.9663）略高于训练 R²（0.9537），20 个测试样本的抽样波动足以解释。

```python
try:
    from sklearn.linear_model import LinearRegression as SklearnLR
    ...
except ImportError:
    print("scikit-learn not installed. Install with: pip install scikit-learn")
```

- `try/except ImportError` 让可选依赖缺失时脚本不崩溃。
- `import ... as SklearnLR` 避免与本文件自定义的 `LinearRegression` 重名。
- ⚠️ sklearn 部分用 `np.random` 生成了**另一份**数据，所以系数（2.9197 / 7.2858）与前面从零实现的结果不可直接比较；讲义说"从零实现与 sklearn 结果相同"，需要在同一份数据上对比才成立。
- `scaler.fit_transform(X_tr)` + `scaler.transform(X_te)`：标准化统计量只在训练集上拟合，这是防数据泄漏的标准写法。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表 + 循环 | 每个公式都能逐字对上代码 | 比 NumPy 慢百倍；生产用 NumPy/sklearn |
| 一元回归同时给 GD 和闭式解 | 用精确解检验 GD | GD 未收敛时容易误读成"噪声导致的偏差" |
| 批量梯度下降 | 最简单、曲线平滑 | 大数据用 mini-batch SGD |
| 标准化 X 和 y | 一个学习率适配所有特征 | 权重需要换算回原始单位才有业务含义 |
| 用 GD 解多项式回归 | 展示"多项式 = 线性回归" | 特征高度相关，GD 很慢；生产用闭式解或正交基 |
| Ridge 惩罚不除以 n | 公式最直接 | α 的数值与 sklearn 不可直接互换 |
| 每个类重复写 `r_squared` | 每个类独立可读 | 重复代码；工程上应抽成公共函数 |
| 脚本式顶层代码 | 从上往下读就是一堂课 | 被 import 时会执行全部训练；工程上应放进 `main()` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `TRUE_W = 3.0` | 全大写命名表示"不应被修改的常量"（只是约定） |
| `_` 占位变量 | `for _ in range(N_SAMPLES)` | 循环变量用不到时的惯用写法 |
| 列表推导式 | `[self.w * x + self.b for x in X]` | 一行生成新列表 |
| 嵌套列表推导 | `[[x ** (d + 1) for d in range(self.degree)] for x in X]` | 外层遍历样本，内层生成每个样本的特征 |
| 生成器表达式 + `sum` | `sum(e ** 2 for e in errors)` | 不建中间列表 |
| `zip` 配对三个序列 | `zip(predictions, y, X)` | 按位置同时取出多个列表的元素 |
| 条件表达式 | `... / stds[j] if stds[j] > 0 else 0` | 一行内的 if/else |
| 增强赋值 | `self.w -= self.lr * dw`、`grad += ...` | `a -= b` 等价于 `a = a - b` |
| 多返回值与解包 | `return dw, db` / `dw, db = self.compute_gradients(X, y)` | 返回元组再解包 |
| `return self` | `fit` 的最后一行 | 支持链式调用 |
| 列表乘法初始化 | `[0.0] * n_features` | 生成全 0 列表（元素是不可变的 float，所以安全） |
| 切片 | `X[:split_idx]`、`X[split_idx:]` | 取前一段 / 后一段 |
| `round` | `[round(w, 4) for w in multi_model.weights]` | 四舍五入到 4 位小数用于打印 |
| f-string 格式符 | `f"{epoch:4d}"`、`f"{cost:.4f}"` | 宽度 4 的整数、保留 4 位小数 |
| `import ... as` | `from sklearn.linear_model import LinearRegression as SklearnLR` | 起别名避免重名 |
| `try / except ImportError` | sklearn 对照段 | 可选依赖缺失时优雅降级 |

---

## 6. 运行结果解读

实际运行（约 1.7 秒，环境中已装 numpy 和 scikit-learn）的关键输出：

```text
=== Training Linear Regression (Gradient Descent) ===
  Epoch    0 | Cost: 263.0919 | w: 1.3073 | b: 0.2174
  Epoch  200 | Cost: 7.4251 | w: 3.6454 | b: 3.2610
  Epoch  400 | Cost: 4.9453 | w: 3.4099 | b: 4.8006
  Epoch  800 | Cost: 3.7984 | w: 3.1906 | b: 6.2336
Learned: y = 3.1433x + 6.5432
R-squared: 0.9566

=== Normal Equation (Closed-Form) ===
Learned: y = 3.0756x + 6.9853
R-squared: 0.9572
```

- 损失从 263 迅速降到个位数：前期 w 冲过头（3.65），之后 w 慢慢回落、b 慢慢上升——典型的"狭长山谷"中 w 与 b 此消彼长。
- GD 的 R²（0.9566）略低于闭式解（0.9572），印证 GD 还没走到谷底。闭式解偏离真值 3/7 的部分才是噪声造成的。

```text
=== Multiple Linear Regression (3 features) ===
  Epoch    0 | Cost: 0.9582
  Epoch  200 | Cost: 0.1195
  Epoch  800 | Cost: 0.1193
Weights (standardized): [0.7716, 0.2773, -0.2739]
Bias (standardized): 0.0000
R-squared: 0.8807
```

- 标准化后 200 轮就基本收敛——对比上面未中心化的一元回归，这就是特征缩放的威力。
- 面积影响最大（0.77）；卧室为正、房龄为负，符号与生成公式一致。换算回原始单位约为 `53.7/平方英尺、10145/间卧室、−1008/年`，截距约 46192。
- R² ≈ 0.88：剩下 12% 的方差主要来自 σ=20000 的噪声。

```text
Degree 2:  R-squared: 0.6408
Degree 5:  R-squared: 0.6686
```

- R² 不高，主要因为噪声相对信号很大：即使用真实曲线预测，这份数据的 R² 也只有约 0.676；另外 GD 尚未收敛。
- 5 阶训练 R² 更高是必然的（模型更灵活），不能说明它更好。

```text
Ridge weights: [0.7052, 0.2647, -0.2558]
Plain weights: [0.7716, 0.2773, -0.2739]
```

- 三个权重都被收缩，最大的权重（面积）缩得最多（绝对值）。L2 惩罚 `0.0633` 约占总 cost 0.188 的三分之一。

```text
Train R-squared: 0.9537
Test R-squared:  0.9663
...
Coefficient (w): 2.9197
Intercept (b): 7.2858
R-squared (test): 0.9686
```

- 测试 R² 高于训练 R² 属于小样本波动。sklearn 部分是另一份随机数据，数值不能与前面逐一对比。

---

## 7. 动手改一改

1. 在一元回归前把 x 中心化（`x - x_mean`），训练后再把 b 换算回来，确认 1000 轮内就能与闭式解一致；再试 lr = 0.02、0.03、0.035，找到发散的临界点（理论值约 0.031）。
2. 画（或打印）`model.cost_history` 的前 50 个值，观察损失下降曲线的形状。
3. 把 `MultipleLinearRegression.fit` 改写成 NumPy 向量化版本：`grad = 2/n * X.T @ (X @ w + b - y)`，对比速度。
4. 用 `np.linalg.lstsq` 求多项式回归 1、2、5、10 阶的闭式解，再从同一分布生成一份测试数据，画出训练 R² 和测试 R² 随阶数的变化，找到过拟合开始的位置。
5. 实现讲义练习中的 Lasso：梯度里加 `alpha * sign(w)`，观察哪个权重最先被压到 0 附近；再思考为什么 GD 很难让它"精确"等于 0（提示：近端梯度 / soft-thresholding）。
6. 实现 mini-batch SGD（每轮打乱数据、每 16 个样本更新一次），对比收敛速度和 cost 曲线的平滑程度。

---

## 8. 常见坑

- **梯度符号写反**：`pred - actual` 与 `actual - pred` 差一个负号，写反后损失会越训越大。
- **只更新了一部分参数就重算梯度**：w、b 必须用同一轮的误差同时更新。
- **把"没收敛"当成"学到的结果"**：判断收敛要看损失曲线是否走平，或与闭式解对比，而不是只看轮数。
- **忘记特征缩放**：量纲差异大时 GD 要么极慢，要么学习率一大就发散。
- **用全量数据算标准化统计量再评估**：测试集信息泄漏，评估偏乐观。
- **直接照搬正则系数**：本实现的 α 与 sklearn 的 alpha 相差 n 倍。
- **用训练 R² 选模型复杂度**：训练 R² 随特征数/阶数单调不减，必须看验证集。
