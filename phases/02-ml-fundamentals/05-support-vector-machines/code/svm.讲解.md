# 代码讲解 · svm.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 05 节 支持向量机 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python svm.py`（无命令行参数，约 1–2 秒跑完 9 个演示） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy / scikit-learn

---

## 1. 这份代码在考察什么

这份代码用纯 Python 把 SVM 的核心思想拆成 9 个小实验，每个实验回答一个问题：

1. **hinge loss 长什么样**：为什么 `y·f(x) ≥ 1` 时损失恰好为 0，而 logistic loss 永远大于 0。
2. **线性 SVM 怎么训练**：不解二次规划（QP），直接对"L2 正则 + hinge loss"做次梯度 SGD（原始问题 / primal）。
3. **C 参数是什么**：C 和 SGD 里的 `lambda_param` 如何换算，C 变化时间隔宽度、支持向量数如何变化。
4. **核函数在度量什么**：线性 / 多项式核看"对齐"，RBF 核看"距离近不近"。
5. **核技巧的动机**：线性 SVM 在环形数据上失败；手工加多项式特征后成功——核技巧就是把这一步"隐式"完成。
6. **支持向量与稀疏性**：只有靠近间隔的少数点决定边界，这和逻辑回归"所有点都参与"形成对比。

> 一句话：**用不到 600 行标准库代码，把"最大间隔 → hinge loss → 正则化 → 核技巧"这条主线完整走一遍**，其中有几处为了直观做的简化（尤其是支持向量的判定），读的时候要能分辨出来。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `dot` / `vec_add` / `vec_sub` / `vec_scale` / `vec_norm` | 函数 | 用列表实现的向量运算 | 点积、L2 范数 |
| `linear_kernel` / `polynomial_kernel` / `rbf_kernel` | 函数 | 三种核函数 | 核技巧 |
| `hinge_loss` / `svm_objective` | 函数 | 平均 hinge 损失；加上 `½λ‖w‖²` 的完整目标 | 软间隔 SVM 的无约束形式 |
| `LinearSVM` | 类 | `fit`（SGD）、`predict`、`decision_function`、`margin_width`、`find_support_vectors` | 原始问题求解、间隔、支持向量 |
| `accuracy` / `train_test_split` | 函数 | 评估与数据切分 | — |
| `generate_linear_data` / `generate_noisy_data` / `generate_circular_data` | 函数 | 生成线性可分 / 带噪声 / 环形三类数据 | 可分、不可分、非线性 |
| `compute_kernel_matrix` | 函数 | 计算 n×n 核矩阵（利用对称性） | Gram 矩阵 |
| `demo_*` × 9 | 函数 | 九个演示实验 | 见第 3 节 |
| `if __name__ == "__main__":` | 入口 | 依次调用所有演示 | — |

数据流：`generate_*` 造数据 → `train_test_split` 切分 → `LinearSVM.fit` 训练 → `predict` / `margin_width` / `find_support_vectors` 评估 → `demo_*` 打印表格。核函数相关的两个演示（`demo_kernel_functions`、`demo_kernel_matrix`）只计算核值，不训练核 SVM。

---

## 3. 逐段精讲

### 3.1 向量工具与三个核函数

```python
def dot(a, b):
    return sum(ai * bi for ai, bi in zip(a, b))

def vec_norm(a):
    return math.sqrt(dot(a, a))

def linear_kernel(x, z):
    return dot(x, z)

def polynomial_kernel(x, z, degree=3, c=1.0):
    return (dot(x, z) + c) ** degree

def rbf_kernel(x, z, gamma=0.5):
    diff = vec_sub(x, z)
    return math.exp(-gamma * dot(diff, diff))
```

- 所有向量都是普通 `list`，`dot` 用生成器表达式逐分量相乘再求和，是整份代码的"地基"。
- 三个核函数与讲义公式一一对应：
  - **线性核** `x·z`：就是点积，衡量投影/对齐程度。
  - **多项式核** `(x·z + c)^d`：常数 `c` 让展开式里同时包含低阶项（1 次、0 次），`d` 控制特征交互的最高阶数。
  - **RBF 核** `exp(−γ‖x−z‖²)`：`dot(diff, diff)` 就是平方欧氏距离；距离为 0 时核值为 1，越远越趋近 0。
- 为什么这样设计：核函数只需要两个点就能算，签名统一为 `kernel(x, z, **超参数)`，这样 `compute_kernel_matrix` 可以把任意核当参数传进去（函数是"一等公民"）。
- ⚠️ 简化：本文件只"计算"核值来展示相似度，**没有实现核 SVM 的训练**（那需要对偶问题 + SMO 等求解器）。核技巧的效果是用 `demo_linear_vs_nonlinear` 里的显式特征映射来间接演示的。

### 3.2 hinge loss 与完整目标函数

```python
def hinge_loss(X, y, w, b):
    n = len(X)
    total = 0.0
    for i in range(n):
        margin = y[i] * (dot(w, X[i]) + b)
        total += max(0.0, 1.0 - margin)
    return total / n

def svm_objective(X, y, w, b, lambda_param):
    reg = 0.5 * lambda_param * dot(w, w)
    loss = hinge_loss(X, y, w, b)
    return reg + loss
```

- 这里的 `margin` 是**函数间隔** `yᵢ·(wᵀxᵢ + b)`：正数表示分对，≥ 1 表示在间隔之外。
- `max(0.0, 1.0 - margin)`：这一个 `max` 就把讲义里的约束 `yᵢ(wᵀxᵢ+b) ≥ 1 − ξᵢ, ξᵢ ≥ 0` 消掉了——最优时松弛变量恰好等于 `ξᵢ = max(0, 1 − yᵢf(xᵢ))`，所以带约束的 QP 等价于这个无约束目标。
- `svm_objective` = `(λ/2)‖w‖² + (1/n)Σhinge`，正是讲义 "Training a linear SVM with gradient descent" 一节的 `L(w, b)`。它只在训练过程中被用来**记录**损失曲线，不参与更新。
- 注意 `b` 不进正则项：正则化惩罚的是 `‖w‖`（决定间隔宽度），偏置只是平移超平面，惩罚它没有意义。

### 3.3 `LinearSVM.fit`：次梯度 SGD（本文件的核心）

```python
    def fit(self, X, y):
        n_features = len(X[0])
        n_samples = len(X)
        self.w = [0.0] * n_features
        self.b = 0.0
        self.loss_history = []

        for epoch in range(self.n_epochs):
            indices = list(range(n_samples))
            random.shuffle(indices)

            for i in indices:
                margin = y[i] * (dot(self.w, X[i]) + self.b)

                if margin >= 1:
                    self.w = [
                        wj - self.lr * self.lambda_param * wj
                        for wj in self.w
                    ]
                else:
                    self.w = [
                        wj - self.lr * (self.lambda_param * wj - y[i] * X[i][j])
                        for j, wj in enumerate(self.w)
                    ]
                    self.b -= self.lr * (-y[i])

            if epoch % 100 == 0 or epoch == self.n_epochs - 1:
                loss = svm_objective(X, y, self.w, self.b, self.lambda_param)
                self.loss_history.append((epoch, loss))
```

逐行对应讲义的梯度公式：

| 情况 | 讲义中的梯度 | 代码中的更新 |
|------|------------|------------|
| `margin ≥ 1`（安全区） | `∂L/∂w = λw`，`∂L/∂b = 0` | `w ← w − lr·λ·w`（只做权重衰减），`b` 不变 |
| `margin < 1`（间隔内或分错） | `∂L/∂w = λw − yᵢxᵢ`，`∂L/∂b = −yᵢ` | `w ← w − lr·(λw − yᵢxᵢ)`，`b ← b − lr·(−yᵢ)` |

要点：

- **为什么是"次梯度"**：hinge loss 在 `margin = 1` 处有个折角，不可导。代码把 `margin == 1` 归到"安全区"，取了其中一个合法的次梯度——凸函数的次梯度下降仍能收敛。
- **安全区也要更新 `w`**：即使这个样本没有损失，正则项 `λ/2‖w‖²` 依然存在，所以每一步都把 `w` 往 0 收缩一点（weight decay）。这一步正是"最大化间隔"的来源——不断压小 `‖w‖`，只有违例样本才把它往外推。
- **`random.shuffle(indices)`**：每个 epoch 打乱样本顺序，这是 SGD 的标准做法，避免按固定顺序更新带来的周期性偏差。它用的是全局 `random` 状态，由前面 `generate_*` / `train_test_split` 中的 `random.seed(42)` 间接固定，所以每次运行结果完全一致。
- **`self.b -= self.lr * (-y[i])`**：等价于 `self.b += self.lr * y[i]`，写成"减去学习率乘梯度"的形式是为了与公式 `∂L/∂b = −yᵢ` 字面对应。
- 每一步更新都用列表推导**新建**了一个 `w` 列表——每次 `O(d)`，整轮 `O(n·d)`，与讲义说的原始问题复杂度一致。
- ⚠️ 简化：固定学习率、没有学习率衰减（Pegasos 等算法用 `1/(λt)` 的衰减步长来保证收敛速度）；没有收敛判据，固定跑 `n_epochs` 轮。

### 3.4 预测、决策函数与间隔宽度

```python
    def predict(self, X):
        return [1 if dot(self.w, x) + self.b >= 0 else -1 for x in X]

    def decision_function(self, X):
        return [dot(self.w, x) + self.b for x in X]

    def margin_width(self):
        w_norm = vec_norm(self.w)
        if w_norm == 0:
            return 0.0
        return 2.0 / w_norm
```

- `predict` 只看 `f(x)` 的符号；`decision_function` 返回原始分数（与 sklearn 的同名方法语义一致），分数的绝对值越大离边界越远——但它**不是概率**。
- `margin_width = 2/‖w‖`：点到超平面的距离是 `|wᵀx+b|/‖w‖`，两条间隔边界 `wᵀx+b = ±1` 之间的距离就是 `2/‖w‖`。
- `w_norm == 0` 的保护：训练前或 λ 极大时 `w` 可能全 0，此时直接返回 0 避免除零。

### 3.5 `find_support_vectors`：一个"近似"的支持向量判定

```python
    def find_support_vectors(self, X, y, tol=0.1):
        svs = []
        for i in range(len(X)):
            margin = y[i] * (dot(self.w, X[i]) + self.b)
            if abs(margin - 1.0) < tol:
                svs.append(i)
        return svs
```

- 判定条件 `|yᵢf(xᵢ) − 1| < tol`：函数间隔"差不多等于 1"的点，即落在间隔边界附近的点。这对应**硬间隔**下支持向量的定义（讲义 "The data points that sit exactly on the margin boundaries"）。
- 为什么需要 `tol`：SGD 得到的是近似解，不会有样本恰好满足 `margin == 1.0`；各个演示分别用了 `tol=0.3`、`0.5`。
- ⚠️ 重要简化：对**软间隔** SVM，KKT 条件告诉我们所有 `yᵢf(xᵢ) ≤ 1` 的点（包括间隔内和分错的点）都有 `αᵢ > 0`，都是支持向量；而且在本文件的 `fit` 中，所有 `margin < 1` 的点都在产生梯度。这个函数会**漏掉**间隔深处和分错的点，又会**多算** `1 ≤ margin < 1 + tol` 这些零损失的点。实测 `demo_svm_vs_logistic` 那份数据：`tol=0.5` 统计出 26 个，而真正 `margin < 1` 的点是 22 个（其中 5 个分错），两者只部分重合。所以打印出的 "SVs" 数应理解为"靠近间隔边界的点数"，看趋势即可。

### 3.6 三个数据生成器

```python
def generate_linear_data(n_samples=100, margin=1.0, seed=42):
    random.seed(seed)
    # ...
        val = x1 + x2
        if val > margin / 2:
            # ... label 1
        elif val < -margin / 2:
            # ... label -1

def generate_noisy_data(n_samples=200, noise=0.5, seed=42):
    # ...
        val = x1 - 0.5 * x2 + random.gauss(0, noise)
        label = 1 if val > 0 else -1

def generate_circular_data(n_samples=200, seed=42):
    # ...
        r = random.uniform(0, 3)
        angle = random.uniform(0, 2 * math.pi)
        x1 = r * math.cos(angle) + random.gauss(0, 0.1)
        x2 = r * math.sin(angle) + random.gauss(0, 0.1)
        label = 1 if r > 1.5 else -1
```

| 生成器 | 真实边界 | 特点 | 用在哪个演示 |
|-------|---------|------|------------|
| `generate_linear_data` | `x1 + x2 = 0` | 落在 `|x1+x2| ≤ margin/2` 带内的点**被丢弃**，人为制造一条空白"街道"，所以严格线性可分 | 线性 SVM、支持向量、间隔效应 |
| `generate_noisy_data` | `x1 − 0.5·x2 = 0` | 在打标签前加高斯噪声，边界附近标签会"翻转"，不可分 | C 参数、SVM vs LR |
| `generate_circular_data` | 圆 `r = 1.5` | 内圈 −1、外圈 +1，任何直线都分不开 | 核矩阵、线性 vs 非线性 |

- ⚠️ `generate_linear_data(200, ...)` 实际返回的样本**少于 200**（被丢弃的点不补），所以运行时会看到 "Dataset: 166 samples"。
- `margin` 参数是 `x1+x2` 取值上的空白宽度，对应的几何间隙是 `margin/√2`（因为直线 `x1+x2=c` 的法向量长度为 `√2`）。

### 3.7 `compute_kernel_matrix`：利用对称性只算一半

```python
def compute_kernel_matrix(X, kernel_fn, **kwargs):
    n = len(X)
    K = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            val = kernel_fn(X[i], X[j], **kwargs)
            K[i][j] = val
            K[j][i] = val
    return K
```

- 合法核满足 `K(x,z) = K(z,x)`，所以内层循环从 `j = i` 开始，算一次填两个格子，计算量减半。
- `**kwargs` 把 `gamma=1.0` 之类的超参数原样转发给核函数，`compute_kernel_matrix` 本身不需要知道核有哪些参数。
- `[[0.0] * n for _ in range(n)]` 必须用推导式创建二维列表；若写成 `[[0.0] * n] * n`，n 行会指向**同一个**列表对象，改一格整列都变（经典坑，见第 8 节）。
- 核矩阵大小是 `n²`：这正是讲义说 kernel SVM 难以扩展到大数据集的直接原因。

### 3.8 `demo_c_parameter`：C 与 λ 的换算

```python
    c_values = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
    # ...
    for c in c_values:
        lam = 1.0 / (c * len(X_train))
        svm = LinearSVM(lr=0.001, lambda_param=lam, n_epochs=500)
```

- 讲义有两种写法：`½‖w‖² + C·Σhinge`（经典 SVM，sklearn 的 C）和 `(λ/2)‖w‖² + (1/n)·Σhinge`（SGD 写法）。前者整体除以 `C·n` 就得到后者，对齐系数即 `λ = 1/(C·n)`。
- 因此 C 越大 → λ 越小 → 正则越弱 → `‖w‖` 越大 → 间隔越窄。运行结果中间隔从 6.28 单调降到 1.39，验证了这一点。
- ⚠️ 结果与打印结论不一致：脚本最后打印 "Small C ... better generalization"，但实测测试准确率随 C 增大从 0.867 升到 0.900（见第 6 节）。原因是这份数据的真实边界就是线性的，2 维线性模型几乎不可能过拟合，小 C 反而欠拟合；而且 60 个测试样本里 1 个样本就是 1.67 个百分点，差异并不显著。

### 3.9 `demo_kernel_matrix`：按"类别对"统计平均核值

```python
    K_linear = compute_kernel_matrix(X, linear_kernel)
    K_rbf = compute_kernel_matrix(X, rbf_kernel, gamma=1.0)
    # ...
    for i in range(len(X)):
        for j in range(i + 1, len(X)):
            if y[i] == 1 and y[j] == 1:
                pos_pos_lin.append(K_linear[i][j])
                pos_pos_rbf.append(K_rbf[i][j])
            elif y[i] == -1 and y[j] == -1:
                # ...
            else:
                # ...

    def safe_mean(lst):
        return sum(lst) / len(lst) if lst else 0.0
```

- 思路：一个"好"的核应该让**同类点之间核值大、异类点之间核值小**。对 20 个环形数据点，分别统计 +/+、−/−、+/− 三种组合的平均核值。
- `j` 从 `i + 1` 开始：跳过对角线（自身与自身的核值，RBF 恒为 1，会抬高平均值）和重复的对称项。
- `safe_mean` 是嵌套函数，防止某一类恰好为空时除以 0。
- 这只是一个直观的"可分性"指标，不等于训练一个核 SVM。

### 3.10 `demo_linear_vs_nonlinear`：手工做一次"核技巧"

```python
    X_train_aug = [
        [x[0], x[1], x[0] ** 2, x[1] ** 2, x[0] * x[1]]
        for x in X_train
    ]
    # ...
    svm_aug = LinearSVM(lr=0.0005, lambda_param=0.01, n_epochs=1000)
    svm_aug.fit(X_train_aug, y_train)
```

- 环形边界 `x1² + x2² = 2.25` 在原空间是圆，但在 `(x1, x2, x1², x2², x1·x2)` 这个 5 维空间里是**线性**的：只要 `x1²` 和 `x2²` 两维的权重相等、偏置约为 `−2.25` 倍即可。
- 这就是核技巧要做的事：二次多项式核 `(x·z + c)²` 展开后正好包含这些二次项（带有系数 `√2`、常数项等），核 SVM 不需要显式构造这 5 列。
- 学习率从 `0.001` 降到 `0.0005`、epoch 增到 1000：平方特征的数值范围更大（最大约 9），步长太大更新会抖动。这也提示了：**多项式特征之后最好再标准化**。

### 3.11 `demo_support_vectors` 与 `demo_svm_vs_logistic`

```python
    margins.sort(key=lambda x: x[1])
    # ...
        if m < 0:
            role = "MISCLASSIFIED"
        elif m < 1.0:
            role = "inside margin"
        elif m < 1.2:
            role = "SUPPORT VECTOR"
        else:
            role = "safely classified"
    # ...
    n_sv = sum(1 for _, m in margins if 0.7 < m < 1.3)
    n_safe = sum(1 for _, m in margins if m >= 1.3)
    n_inside = sum(1 for _, m in margins if 0 < m < 0.7)
```

- 把所有训练点按函数间隔从小到大排序，打印最"危险"的 8 个和最"安全"的 3 个，直观看出：绝大多数点 margin 远大于 1，对边界毫无影响。
- ⚠️ 阈值前后不一致：表格里 `m < 1.0` 标为 "inside margin"、`1.0 ≤ m < 1.2` 才标 "SUPPORT VECTOR"；但汇总计数用的是 `0.7 < m < 1.3` 算支持向量、`0 < m < 0.7` 算间隔内。实际运行中 margin = 0.9927 的点在表里显示为 "inside margin"，在计数里却被算作支持向量。此外 `m ≤ 0` 的分错点不属于任何一个计数。

`demo_svm_vs_logistic` 里顺手手写了一个逻辑回归：

```python
            z = dot(w_lr, X_train[i]) + b_lr
            z = max(-500, min(500, z))
            p = 1.0 / (1.0 + math.exp(-z))
            y_01 = (y_train[i] + 1) / 2
            error = p - y_01
```

- `max(-500, min(500, z))`：夹紧 `z`，防止 `math.exp(-z)` 在 `z < −709` 左右时抛 `OverflowError`。
- `(y + 1) / 2` 把 SVM 习惯的 `{−1, +1}` 标签转换为 LR 需要的 `{0, 1}`。
- `error = p − y` 是交叉熵对 logit 的梯度——每个样本都有非零梯度，这就是"LR 用到所有点"的含义。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 解原始问题（hinge + L2 的 SGD），不解对偶 QP | 代码短、复杂度 `O(n·d)`/epoch、和深度学习的训练方式一致 | 无法直接用核；生产中线性用 `LinearSVC`（liblinear），核用 `SVC`（libsvm 的 SMO） |
| 次梯度 + 固定学习率 | 最容易理解 | 收敛慢、对学习率敏感；Pegasos 用 `1/(λt)` 衰减步长 |
| 用 `|margin − 1| < tol` 判定支持向量 | 贴合"在间隔边界上"的直观定义 | 不符合软间隔 KKT 定义；严格做法是看对偶变量 `αᵢ > 0`（sklearn 的 `support_`） |
| 核函数只算值、不训练核 SVM | 聚焦"核在度量什么" | 需要对偶求解器才能真正用核；可用显式特征映射（本文件）或核近似 |
| 显式多项式特征演示核技巧 | 让"升维后线性可分"肉眼可见 | 维度随阶数指数增长，这正是核技巧要避免的 |
| 用 `random.seed(42)` 固定所有随机性 | 结果可复现 | 生产中应使用独立的 `random.Random(seed)` 实例，避免全局状态互相干扰 |
| 纯 Python 列表 | 每一步都看得见 | 比 NumPy 慢几个数量级 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def polynomial_kernel(x, z, degree=3, c=1.0)` | 调用时可省略，也可用关键字覆盖：`degree=2` |
| 生成器表达式 | `sum(ai * bi for ai, bi in zip(a, b))` | 不建中间列表，直接求和 |
| 列表推导式 | `[ai + bi for ai, bi in zip(a, b)]` | 一行生成新列表 |
| 带条件表达式的推导 | `[1 if dot(self.w, x) + self.b >= 0 else -1 for x in X]` | `A if 条件 else B` 是三元表达式 |
| `zip` / `enumerate` | `for j, wj in enumerate(self.w)` | 同时拿下标和元素 |
| 增强赋值 | `total += ...`、`self.b -= ...` | `x -= y` 等价于 `x = x - y` |
| 二维列表初始化 | `[[0.0] * n for _ in range(n)]` | 每行是独立列表；`_` 表示"用不到的循环变量" |
| `**kwargs` 转发 | `compute_kernel_matrix(X, rbf_kernel, gamma=1.0)` → `kernel_fn(X[i], X[j], **kwargs)` | 把任意关键字参数打包成字典再原样展开传下去 |
| 函数作为参数 | `kernel_fn` | 函数是一等对象，可以像变量一样传递 |
| 嵌套函数 | `demo_kernel_matrix` 里的 `def safe_mean(lst)` | 只在外层函数内部可见的小工具 |
| `lambda` 与 `sort(key=...)` | `margins.sort(key=lambda x: x[1])` | 按元组第 2 个元素（margin）原地排序 |
| 元组列表 | `self.loss_history.append((epoch, loss))`、`for epoch, loss in svm.loss_history` | 存成对的数据，遍历时解包 |
| 负索引切片 | `margins[:8]`、`margins[-3:]` | 取前 8 个 / 最后 3 个 |
| `random` 模块 | `random.seed`、`random.uniform`、`random.gauss`、`random.shuffle` | 固定种子、均匀分布、正态分布、原地打乱 |
| `math` 模块 | `math.exp`、`math.log`、`math.sqrt`、`math.cos`、`math.pi` | 标量数学函数 |
| f-string 对齐格式符 | `f"{m:>10.1f}"`、`f"{name:<20s}"`、`f"{n_sv:>6d}"`、`f"{'-' * 10}"` | `>` 右对齐、`<` 左对齐，`10` 为宽度，`.1f` 保留 1 位小数，`d` 整数，`s` 字符串；花括号里可以放表达式 |
| 类与实例属性 | `self.w`、`self.loss_history` | 在 `__init__` 中声明，在 `fit` 中重置 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示 |

---

## 6. 运行结果解读

实际运行命令：在临时副本目录中执行 `python3 svm.py`，约 1.5 秒完成。以下为关键输出（节选）。

**① hinge vs logistic**

```text
    y * f(x)    Hinge loss   Logistic loss
         0.5         0.500           0.474
         1.0         0.000           0.313
         3.0         0.000           0.049
```

`y·f(x) ≥ 1` 后 hinge 恰好为 0，而 logistic 只是逐渐变小。这就是"hinge 稀疏、logistic 稠密"的根源。

**② 线性 SVM（线性可分数据）**

```text
  Dataset: 166 samples, linearly separable
  Weights: [1.5729, 1.5488]
  Bias: -0.0680
  Margin width: 0.9060
  Train accuracy: 1.0000
  Test accuracy: 1.0000
  Support vectors: 18 / 132 training points
       499      0.0277
```

- 两个权重几乎相等、偏置接近 0，说明学到的边界 ≈ `x1 + x2 = 0`，正是数据的真实边界。
- 最终损失 0.0277 可以拆开验算：正则项 `0.5 × 0.01 × (1.5729² + 1.5488²) ≈ 0.0244`，剩下约 0.003 是 hinge 部分——说明有少数点轻微侵入间隔，这是 λ=0.01 的软间隔在"间隔宽度"和"违例"之间的折中。

**③ C 参数扫描**

```text
         C    lambda   Train Acc    Test Acc    Margin     SVs
     0.001   4.16667      0.9042      0.8667    6.2787      64
     1.000   0.00417      0.8917      0.9000    1.4439      38
   100.000   0.00004      0.8875      0.9000    1.3908      33
```

- 符合理论的部分：C ↑ → λ ↓ → 间隔从 6.28 变窄到 1.39，近边界点数从 64 降到 30 多。C ≥ 10 之后几乎不再变化——数据已经被"尽力分开"，再减小正则没有影响。
- 与打印结论相反的部分：测试准确率随 C 增大而**上升**。如 3.8 所述，低容量模型 + 线性真实边界不会过拟合，且差异只有 2 个测试样本。

**④ 核函数对比**

```text
  Point                   Linear   Poly(d=2)   Poly(d=3)  RBF(g=0.5)
  same direction           2.000       9.000      27.000      0.6065
  perpendicular            0.000       1.000       1.000      0.3679
  close                    1.100       4.410       9.261      0.9900
  far same dir             5.000      36.000     216.000      0.0003
  opposite                -1.000       0.000       0.000      0.1353
```

"far same dir" 一行最能说明问题：线性/多项式核认为它"非常相似"（同方向且很长），RBF 核认为它"毫不相似"（离得远）。"close" 一行 RBF 最高（0.99）。

**⑤ 环形数据上的核矩阵**

```text
  Pair                 Linear    RBF(g=1)
  Same (+/+)           0.0738      0.1165
  Same (-/-)          -0.0544      0.3769
  Different           -0.1500      0.0401
```

线性核三组数值都接近 0，看不出类别结构；RBF 核下同类对的平均值明显高于异类对。−/− 内圈点彼此靠得近，所以核值最高；+/+ 外圈点分布在一个大圆环上，彼此相距较远，平均核值反而不高——但仍然是异类对（0.04）的近 3 倍。

**⑥ 线性 vs 非线性**

```text
  Linear SVM: train acc = 0.6937, test acc = 0.5500
  Linear SVM on augmented features: train acc = 0.9875, test acc = 0.9000
```

原始 2 维特征上线性 SVM 接近瞎猜；加上二次项后跃升到 90%——"升维后线性可分"被直接验证。

**⑦ 支持向量 / ⑧ SVM vs LR / ⑨ 间隔效应**

```text
  Support vectors (margin ~ 1.0): 16
  Safely classified (margin >> 1): 102
  Only 16 out of 119 points define the boundary.

  SVM test accuracy:              0.9250
  Logistic regression test acc:   0.9250
  SVM support vectors:            26 / 160

   Data margin    SVM margin   Train Acc    Test Acc
           0.5        0.8179      1.0000      1.0000
           3.0        2.1875      1.0000      1.0000
```

- 119 个训练点里只有十几个靠近间隔边界，其余 102 个 margin 远大于 1——体现稀疏性（注意计数口径的问题见 3.5、3.11）。
- SVM 与 LR 在这份数据上测试准确率相同：两者都是线性分类器，差别主要在"用哪些点"和"输出是否为概率"，而不是精度。
- 数据间隙越大，学到的间隔越宽（0.82 → 2.19），这部分符合预期；但四组测试准确率都是 1.0，"更好的泛化"在这组数字里**并没有被区分出来**。

---

## 7. 动手改一改

1. **修正支持向量计数**：新增 `find_margin_violators`，返回 `margin < 1` 的所有点，在 `demo_svm_vs_logistic` 中和 `tol=0.5` 的结果并排打印，观察两种口径的差异。
2. **统一阈值**：把 `demo_support_vectors` 里表格角色判定和汇总计数改成同一套阈值（例如都用 `m ≤ 0` / `0 < m < 1 − tol` / `|m − 1| ≤ tol` / `m > 1 + tol`）。
3. **Pegasos 步长**：把固定 `lr` 改成第 t 步 `lr_t = 1/(λ·t)`，对比收敛曲线 `loss_history` 和最终间隔。
4. **让 C 的过拟合现象出现**：把 `demo_c_parameter` 换成在环形数据的 5 维增广特征（甚至更高阶多项式特征）上跑，看看大 C 时训练/测试准确率是否开始分叉。
5. **实现 SVR**（讲义练习 5）：把损失换成 ε-insensitive loss `max(0, |y − f(x)| − ε)`，推导次梯度，拟合 `y = sin(x) + noise`，统计管道外的点数。
6. **用 sklearn 对照**：`SVC(kernel="linear", C=...)` 在同一份数据上训练，比较 `support_` 的数量与本文件的近似计数，并验证 `2/‖coef_‖` 与 `margin_width()` 是否接近。

---

## 8. 常见坑

- **把"支持向量"理解成只有边界上的点**：软间隔下间隔内与分错的点同样是支持向量（`αᵢ = C`），而且是最"用力"拉边界的那批。
- **C 和 λ 方向相反**：sklearn 的 `C` 越大正则越弱；SGD 写法里的 `λ` 越大正则越强。换算是 `λ = 1/(C·n)`，调参时别搞反。
- **不做特征缩放**：间隔和 RBF 距离都依赖欧氏几何，量纲大的特征会主导结果；`demo_linear_vs_nonlinear` 里不得不调小学习率就是这个问题的小型体现。
- **二维列表写成 `[[0.0] * n] * n`**：n 行共享同一个列表对象，`K[0][1] = 5` 会让每一行的第 1 列都变成 5。
- **`math.exp` 溢出**：`math.exp(710)` 会抛 `OverflowError`，所以手写 LR 时要像本文件一样先夹紧 `z`。
- **盲信代码里写死的结论**：`print` 出来的总结是作者的预期，不一定是这次实验的结果——第 6 节的 C 参数表就是反例，一定要对照数字自己下结论。
