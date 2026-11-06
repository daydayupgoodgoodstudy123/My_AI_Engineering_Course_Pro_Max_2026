# 代码讲解 · logistic_regression.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 03 节 逻辑回归 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python logistic_regression.py`（无命令行参数，顺序执行的脚本） ｜ **依赖**：从零实现部分仅用 Python 标准库（`random`、`math`）；最后的对照部分可选用 `numpy` + `scikit-learn`，没装时被 `try/except ImportError` 跳过

---

## 1. 这份代码在考察什么

1. **"线性模型 + sigmoid"**：在线性回归的 `wᵀx + b` 后面加一个 sigmoid，就得到输出概率的分类器。
2. **交叉熵损失与梯度**：BCE 的梯度化简后是 `(p − y)·x`，代码几乎和线性回归一样。
3. **数值稳定**：sigmoid 截断、log 前夹紧概率、softmax 减最大值——三处防御写法都值得记住。
4. **评估分类器**：从零实现混淆矩阵、Precision、Recall、F1，理解"accuracy 不够用"。
5. **决策边界与阈值**：从权重解出边界直线；改变阈值观察 Precision/Recall 的此消彼长。
6. **多分类**：softmax 回归 = 每类一个线性打分 + softmax + 类别交叉熵。

> 一句话：**逻辑回归 = 线性回归的训练循环 + sigmoid + 交叉熵**；本文件的其余部分都在回答"概率出来之后怎么用、怎么评估"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sigmoid(z)` | 函数 | 把任意实数压到 (0,1)，带溢出保护 | sigmoid / logistic 函数 |
| 二分类数据生成 | 脚本 | 中心 (2,2) 与 (5,5) 的两团高斯点，各 100 个，打乱 | 合成数据 |
| `LogisticRegression` | 类 | `predict_proba`、`predict`、BCE 损失、批量 GD | 二分类逻辑回归 |
| `ClassificationMetrics` | 类 | 统计 TP/TN/FP/FN，计算各项指标并打印 | 混淆矩阵、P/R/F1 |
| 决策边界段 | 脚本 | 打印 `w₁x₁ + w₂x₂ + b = 0` 及边界附近点的概率 | 线性决策边界 |
| `SoftmaxRegression` | 类 | k 组权重 + softmax + 类别交叉熵 | 多分类 |
| 三分类数据 | 脚本 | 中心 (1,1)、(5,1)、(3,5)，各 50 个 | — |
| 阈值调节段 | 脚本 | 阈值 0.3–0.7 下的四项指标 | Precision–Recall 权衡 |
| 线性回归对比段 | 脚本 | 对"学习时长→是否通过"做直线拟合，输出越界 | 为什么不能用线性回归分类 |
| sklearn 对照段 | 脚本（可选） | 标准化 + `LogisticRegression` + 各种 metrics | 生产写法 |

数据流：生成数据 → 前 80% 训练、后 20% 测试 → 训练二分类模型 → 指标报告 → 决策边界 → 训练 softmax 模型 → 用二分类模型做阈值扫描 → 线性回归反例 → sklearn。

---

## 3. 逐段精讲

### 3.1 `sigmoid`：先截断再计算

```python
def sigmoid(z):
    z = max(-500, min(500, z))
    return 1.0 / (1.0 + math.exp(-z))
```

- 数学定义 `σ(z) = 1/(1+e⁻ᶻ)`。z 很大时 → 1，z 很负时 → 0，`σ(0) = 0.5`。
- 截断的原因：z 很负时 `math.exp(-z)` 会超过 float 上限（约 1.8e308），Python 的 `math.exp` 会直接抛 `OverflowError`（不像 NumPy 只给警告）。`e^500 ≈ 1.4e217`，仍在范围内，所以 ±500 是安全的。
- 截断几乎不影响结果：`σ(−500)` 本来就小到约 7e-218。
- ⚠️ 截断只防了"溢出"，没防"精度耗尽"：z ≥ 37 左右时 `σ(z)` 会被舍入成恰好 1.0，所以后面计算 log 时还要再夹一次（见 3.3）。

### 3.2 生成并打乱数据

```python
for _ in range(N // 2):
    X.append([random.gauss(2, 1), random.gauss(2, 1)])
    y.append(0)
# ... 类 1 以 (5, 5) 为中心

combined = list(zip(X, y))
random.shuffle(combined)
X, y = zip(*combined)
X = list(X)
y = list(y)
```

- 两团各向同性高斯，两中心相距 `3√2 ≈ 4.24` 个标准差，大致线性可分，但边缘有少量重叠。
- **一起打乱**：先 `zip` 成 (样本, 标签) 对再 `shuffle`，保证打乱后样本和标签仍一一对应。
- `zip(*combined)` 是"解压"惯用法：`*` 把列表拆成多个参数，`zip` 再把第 0 列、第 1 列分别收集起来，得到两个元组；最后转回列表。
- `N // 2` 是整除。打乱后再按顺序切前 80%/后 20%，就等价于随机切分。

### 3.3 `LogisticRegression`：预测与损失

```python
    def predict_proba(self, x):
        z = sum(w * xi for w, xi in zip(self.weights, x)) + self.bias
        return sigmoid(z)

    def predict(self, x, threshold=0.5):
        return 1 if self.predict_proba(x) >= threshold else 0

    def compute_loss(self, X, y):
        n = len(y)
        total = 0.0
        for i in range(n):
            p = self.predict_proba(X[i])
            p = max(1e-15, min(1 - 1e-15, p))
            total += y[i] * math.log(p) + (1 - y[i]) * math.log(1 - p)
        return -total / n
```

- 注意这几个方法处理的是**单个样本** `x`（一个特征列表），而不是整个矩阵——与上一节的 `predict(X)` 风格不同，循环放在调用方。
- `predict_proba` 返回 `P(y=1|x)`；`predict` 用阈值把概率变成 0/1。阈值作为参数暴露出来，为后面的阈值调节做准备。
- 损失就是二元交叉熵：y=1 时只剩 `log p`，y=0 时只剩 `log(1−p)`——"给正确答案分配的概率越低，惩罚越大"。
- `max(1e-15, min(1 - 1e-15, p))` 是 clamp：防止 `math.log(0)` 抛 `ValueError: math domain error`。代价是单样本损失被封顶在约 34.5。
- 名字 `predict_proba` 与 sklearn 一致。

### 3.4 `fit`：梯度就是"误差 × 输入"

```python
    def fit(self, X, y, epochs=1000, print_every=200):
        n = len(y)
        n_features = len(X[0])
        for epoch in range(epochs):
            dw = [0.0] * n_features
            db = 0.0
            for i in range(n):
                p = self.predict_proba(X[i])
                error = p - y[i]
                for j in range(n_features):
                    dw[j] += error * X[i][j]
                db += error
            for j in range(n_features):
                self.weights[j] -= self.lr * (dw[j] / n)
            self.bias -= self.lr * (db / n)
            loss = self.compute_loss(X, y)
            self.loss_history.append(loss)
```

- 推导要点：BCE 对 z 的导数是 `p − y`（sigmoid 的导数 `p(1−p)` 恰好被 log 的导数抵消），再乘 `∂z/∂wⱼ = xⱼ`。所以 `error = p - y[i]` 一行就是全部"反向传播"。
- 与线性回归对比：形式完全一样，只是 p 是 sigmoid 输出；而且**没有因子 2**（MSE 的平方求导才有 2）。
- 先把整轮梯度**累加**到 `dw`、`db`，最后统一除以 n 并更新——批量梯度下降，所有参数同时更新。
- 每轮训练后再完整算一次 loss，相当于把前向计算做了两遍，纯为打印；生产代码会在累加梯度时顺便累加损失（`SoftmaxRegression` 就是这么做的）。
- ⚠️ 没有正则化。如果训练集完全线性可分，权重会一直增大、损失趋近 0 而没有有限最优解；本数据训练集有 2 个点分错，所以不严格可分，但 1000 轮时 loss 仍在下降（未收敛），训到 5000 轮权重会继续增大到约 `[1.70, 1.37]`。
- ⚠️ 没有特征标准化。本数据两个特征量纲相同、都在 0–8 之间，所以影响不大；但 x 均值约 3.5、没有中心化，b 的收敛依然偏慢（1000 轮时 b 从 0 走到 −5.96 仍在变）。

### 3.5 `ClassificationMetrics`：四个计数撑起所有指标

```python
class ClassificationMetrics:
    def __init__(self, y_true, y_pred):
        self.tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        self.tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
        self.fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        self.fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    def precision(self):
        denom = self.tp + self.fp
        return self.tp / denom if denom > 0 else 0

    def f1(self):
        p = self.precision()
        r = self.recall()
        return 2 * p * r / (p + r) if (p + r) > 0 else 0
```

- `sum(1 for ... if ...)` 是"带条件计数"的惯用法：生成器每满足一次条件就产出一个 1。
- 命名规则：第二个字母 P/N 表示**预测**是正/负，第一个字母 T/F 表示预测**对不对**。所以 FP = 预测为正但其实是负（误报），FN = 预测为负但其实是正（漏报）。
- 每个除法都检查分母是否为 0，返回 0 作为约定（sklearn 也是类似处理，并会给出 `zero_division` 警告）。
- `print_confusion_matrix` 的布局是"行 = 真实、列 = 预测，**正类在前**"：`[[TP, FN], [FP, TN]]`。⚠️ sklearn 的 `confusion_matrix` 按标签升序排列，0 在前：`[[TN, FP], [FN, TP]]`——两者正好对角翻转，读输出时要先看清布局。
- ⚠️ 只支持二分类、且正类必须编码为 1。

### 3.6 决策边界

```python
w1, w2 = model.weights
b = model.bias
print(f"Decision boundary: {w1:.4f}*x1 + {w2:.4f}*x2 + {b:.4f} = 0")
if abs(w2) > 1e-10:
    print(f"Solved for x2:     x2 = {-w1/w2:.4f}*x1 + {-b/w2:.4f}")
```

- p = 0.5 ⇔ z = 0 ⇔ `w₁x₁ + w₂x₂ + b = 0`，这是一条直线。把它解成 `x₂ = −(w₁/w₂)·x₁ − b/w₂` 的斜截式，便于画图。
- `abs(w2) > 1e-10` 防止除以 0：w₂ 为 0 时边界是竖线 `x₁ = −b/w₁`，不能写成 x₂ 的函数。
- 打印 `+ -5.9623` 这种"加负数"的格式略显别扭，是直接套 f-string 的结果，无伤大雅。
- 后面打印对角线上几个点的概率：越接近边界，概率越接近 0.5；离得越远越接近 0 或 1——sigmoid 把"到边界的有符号距离"变成了置信度。

### 3.7 `SoftmaxRegression`：多分类

```python
    def softmax(self, scores):
        max_score = max(scores)
        exp_scores = [math.exp(s - max_score) for s in scores]
        total = sum(exp_scores)
        return [e / total for e in exp_scores]

    def predict(self, x):
        probs = self.predict_proba(x)
        return probs.index(max(probs))
```

- **减最大值**：softmax 对所有分数加同一常数不变，减去 max 后最大的指数是 `e⁰ = 1`，不会溢出，分母也至少为 1。
- `probs.index(max(probs))` 是纯 Python 的 argmax：先找最大值，再找它第一次出现的位置。
- `self.weights = [[0.0] * n_features for _ in range(n_classes)]` 必须用列表推导创建；若写成 `[[0.0] * n_features] * n_classes`，k 行会是**同一个列表对象**，改一行就改了所有行——经典坑。

```python
            for i in range(n):
                probs = self.predict_proba(X[i])
                for k in range(self.n_classes):
                    target = 1.0 if y[i] == k else 0.0
                    error = probs[k] - target
                    for j in range(self.n_features):
                        grad_w[k][j] += error * X[i][j]
                    grad_b[k] += error
                true_prob = max(probs[y[i]], 1e-15)
                total_loss -= math.log(true_prob)
```

- `target` 就是 one-hot 编码的第 k 位。softmax + 类别交叉熵的梯度同样是 `p_k − y_k`，与二分类一模一样——这是"交叉熵 + 指数族输出"带来的优雅结果。
- 损失只需要真实类的概率：`−log p_{y}`，因为 one-hot 中其他位都是 0。
- 这里打印的 loss 是本轮**更新前**的损失（边算梯度边累加），与 `LogisticRegression` 打印更新后的损失口径不同。
- 初始所有权重为 0，三类概率各 1/3，损失 `ln 3 ≈ 1.0986`——正好是第 0 轮的输出，可以作为检验实现是否正确的 sanity check。
- ⚠️ k 组权重存在冗余（同时加一个向量不改变输出），没有正则时解不唯一，但不影响预测。

### 3.8 阈值调节与线性回归反例

```python
for t in thresholds:
    y_pred_t = [1 if model.predict_proba(x) >= t else 0 for x in X_test]
    m = ClassificationMetrics(y_test, y_pred_t)
```

- 模型不需要重训，只改变"概率 → 类别"的切分点。阈值低 → 判正的多 → Recall 高、Precision 低；阈值高则反之。
- ⚠️ 这里直接在**测试集**上扫阈值，作为演示没问题；真要选阈值，应该在验证集上选，否则测试分数偏乐观。

```python
    lin_pred = w_lin * h + b_lin
    sig_pred = sigmoid(3 * (h - 4.5))
```

- 线性回归部分复用了上一节的一元闭式解，得到 `0.1455x − 0.2`，在 1 小时处预测 −0.055、10 小时处 1.255，超出 [0,1]。
- ⚠️ 对比列的 `sigmoid(3 * (h - 4.5))` 是**手工挑选**的参数（中心 4.5、斜率 3），不是训练出来的，只是用来展示 S 形曲线的样子。

### 3.9 sklearn 对照

- 先 `StandardScaler` 再 `LogisticRegression()`。sklearn 默认带 L2 正则（`C=1.0`，C 越小正则越强）并使用 lbfgs 求解器，这些都是从零实现里没有的。
- ⚠️ sklearn 段用 `np.random` 生成了另一份数据、做了标准化、带正则，所以讲义说的"从零实现得到相同的决策边界"并不能由这段代码验证；这里四项指标都是 1.0，只是因为两份数据都很好分。
- `classification_report` 一次给出每个类的 precision/recall/F1/support，以及 macro avg（各类简单平均）和 weighted avg（按样本数加权平均）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 单样本接口 `predict_proba(x)` | 公式与代码一一对应，最直观 | 慢；生产用 NumPy 矩阵运算一次处理整批 |
| sigmoid 截断 ±500 + 概率夹紧 1e-15 | 防溢出、防 `log(0)` | 生产直接用 logits 计算损失（log-sum-exp / `BCEWithLogitsLoss`） |
| 不加正则化 | 让梯度公式最干净 | 可分数据上权重发散；sklearn 默认 L2 |
| 不做特征标准化 | 本数据两维量纲相同 | 真实数据必须标准化，否则收敛慢、正则不公平 |
| 指标类只存四个计数 | 所有二分类指标都由它们导出 | 多分类需要 k×k 混淆矩阵 |
| 阈值作为 `predict` 的参数 | 便于演示阈值调节 | 阈值应在验证集上按业务代价选定 |
| softmax 减最大值 | 数值稳定 | 无 |
| 脚本式顶层代码 | 从上到下就是一堂课 | 被 import 时会重新训练；工程上应放进 `main()` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 整除 `//` | `range(N // 2)` | 结果是整数，可以直接用于 `range` |
| `max(a, min(b, x))` 夹紧 | `max(-500, min(500, z))` | 把 x 限制在 [a, b] 区间 |
| 条件表达式 | `1 if ... >= threshold else 0` | 一行的 if/else |
| 默认参数 | `def predict(self, x, threshold=0.5)` | 调用时可覆盖 |
| `zip` + `*` 解压 | `X, y = zip(*combined)` | 把 (样本, 标签) 对拆回两个序列 |
| `random.shuffle` | `random.shuffle(combined)` | **原地**打乱列表，返回 None |
| 带条件的计数 | `sum(1 for t, p in zip(...) if t == 1 and p == 1)` | 生成器表达式 + 过滤条件 |
| 嵌套列表正确初始化 | `[[0.0] * n_features for _ in range(n_classes)]` | 每行都是新列表；`[[0.0]*d]*k` 会共享同一行 |
| `list.index` | `probs.index(max(probs))` | 返回第一个等于该值的下标，实现 argmax |
| `enumerate` + 元组解包 | `for label, (cx, cy) in enumerate(centers)` | 同时拿下标和元素，并把元素再拆成两个变量 |
| 多变量赋值 | `w1, w2 = model.weights` | 列表长度必须正好是 2 |
| 增强赋值 | `dw[j] += error * X[i][j]`、`total_loss -= math.log(...)` | 累加 / 累减 |
| f-string 嵌套表达式 | `f"[{', '.join(f'{p:.3f}' for p in probs)}]"` | 在 f-string 里再用生成器 + `join` 拼接格式化后的数字 |
| f-string 对齐 | `f"{t:>10.1f}"`、`f"{'Threshold':>10}"` | `>10` 右对齐占 10 格 |
| `try / except ImportError` | sklearn 对照段 | 可选依赖缺失时优雅降级 |

---

## 6. 运行结果解读

实际运行（约 1.9 秒，环境中已装 numpy 和 scikit-learn）的关键输出：

```text
=== Training Logistic Regression ===
  Epoch    0 | Loss: 0.6289 | w: [0.074, 0.070] | b: -0.001
  Epoch  200 | Loss: 0.3136 | w: [0.464, 0.333] | b: -2.402
  Epoch  800 | Loss: 0.1462 | w: [0.902, 0.693] | b: -5.391

Train accuracy: 0.9875
Test accuracy:  1.0000
Weights: [0.9886, 0.7629]
Bias: -5.9623
```

- 初始 w=0 时所有 p=0.5，损失为 `ln 2 ≈ 0.693`；第 0 轮更新一步后是 0.6289。
- 损失在 800 轮时仍在下降，权重和 |b| 仍在增长——没有正则、没完全收敛。
- 训练集 160 个样本错 2 个；测试集 40 个全对（小测试集上满分不代表模型完美）。

```text
  Confusion Matrix:
                  Pos   Neg
  Actual Pos       21     0
  Actual Neg        0    19
```

- 测试集正类 21、负类 19，全部分对，所以 P/R/F1 都是 1.0。

```text
Decision boundary: 0.9886*x1 + 0.7629*x2 + -5.9623 = 0
Solved for x2:     x2 = -1.2958*x1 + 7.8152
  [3.0, 3.0] -> prob=0.3301, class=0
  [3.5, 3.5] -> prob=0.5419, class=1
  [5.0, 5.0] -> prob=0.9424, class=1
```

- 边界与对角线交于约 (3.40, 3.40)，略偏向类 0 的中心一侧；斜率 −1.30 而不是理想对称情况下的 −1，反映了有限样本和未收敛。
- [3.5,3.5] 是两中心的中点，概率 0.54 接近 0.5，符合直觉。

```text
=== Multi-class Softmax Regression (3 classes) ===
  Epoch    0 | Loss: 1.0986
  ...
Train accuracy: 0.9917
Test accuracy:  1.0000
  True: 2, Predicted: 2, Probs: [0.029, 0.000, 0.971]
```

- 第 0 轮损失恰为 `ln 3`，验证了初始化与损失实现正确。每行的三个概率加起来为 1。

```text
 Threshold   Accuracy  Precision     Recall         F1
       0.3     0.9500     0.9130     1.0000     0.9545
       0.4     1.0000     1.0000     1.0000     1.0000
       0.5     1.0000     1.0000     1.0000     1.0000
       0.6     0.9750     1.0000     0.9524     0.9756
       0.7     0.9500     1.0000     0.9048     0.9500
```

- 阈值 0.3：多判了 2 个负样本为正（FP=2），Precision 降、Recall 满。阈值 0.7：漏了 2 个正样本（FN=2），Recall 降、Precision 满。典型的权衡曲线。

```text
Linear fit: y = 0.1455*x + -0.2000
     1        0   -0.055    0.000
    10        1    1.255    1.000
```

- 线性回归在两端越界，sigmoid 列始终在 [0,1] 内（但它是手选参数，不是拟合结果）。

---

## 7. 动手改一改

1. 在 `LogisticRegression.fit` 中加入 L2 正则（梯度加 `lam * w[j]`，不惩罚 b），用 `lam = 0.01, 0.1` 训练到 5000 轮，观察权重不再无限增长。
2. 把 `fit` 改写成 NumPy 版：`p = 1/(1+np.exp(-(X @ w + b)))`、`dw = X.T @ (p - y) / n`，对比速度。
3. 改用"从 logits 直接算损失"的稳定写法：`loss = max(z,0) - z*y + log(1 + exp(-|z|))`，去掉 1e-15 的夹紧，验证结果一致。
4. 完成讲义练习 1：生成同心圆数据，先看逻辑回归失败，再加入 `x1², x2², x1·x2` 特征重训。
5. 完成讲义练习 2：为 `SoftmaxRegression` 写一个 3×3 混淆矩阵，计算每个类的 Precision/Recall。
6. 完成讲义练习 3：在 0~1 之间取 100 个阈值计算 TPR、FPR，用梯形法求 AUC，并与"正负样本两两比较"的写法对比。

---

## 8. 常见坑

- **`math.exp` 溢出**：标准库遇到大指数会直接抛 `OverflowError`，必须先截断或改用稳定公式。
- **`log(0)`**：sigmoid 在浮点下会输出恰好的 0.0 或 1.0，损失里要夹紧概率或用 logits 计算。
- **混淆矩阵布局搞反**：本代码是 `[[TP, FN], [FP, TN]]`，sklearn 是 `[[TN, FP], [FN, TP]]`。
- **嵌套列表浅拷贝**：`[[0.0] * d] * k` 让 k 行共享同一个列表。
- **在测试集上调阈值**：测试分数被"选"过就不再是无偏估计。
- **只看 accuracy**：类别不平衡时，全判多数类也能拿到很高的 accuracy。
- **把小测试集上的 100% 当成模型完美**：40 个样本的满分只说明这批样本恰好好分。
