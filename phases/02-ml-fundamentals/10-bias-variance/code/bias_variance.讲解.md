# 代码讲解 · bias_variance.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 10 节 偏差-方差权衡 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python bias_variance.py`（无命令行参数，约 3–4 秒） ｜ **依赖**：`numpy`（另用标准库 `warnings`）

---

## 1. 这份代码在考察什么

偏差和方差是对"**训练集的随机性**"取期望得到的量，单次训练根本看不到它们。这份代码的核心思路是：**既然我们知道真实函数，就可以反复生成新的训练集，把"期望"直接算出来**。具体考察：

1. **怎么把定义变成代码**：200 个训练集 × 100 个测试点的预测矩阵，按列求均值就是 `E[f̂(x)]`，按列求方差就是 Variance。
2. **复杂度与误差的 U 形关系**：多项式阶数从 1 扫到 15，看 Bias² 下降、Variance 上升。
3. **正则化如何移动平衡点**：固定高阶多项式，扫描 Ridge 的 λ。
4. **数据量的作用**：更多数据压低方差，但对偏差无能为力。
5. **实用诊断**：用训练/测试 MSE 和学习曲线判断欠拟合还是过拟合。

> 一句话：**用一个"上帝视角"的合成实验，把讲义里的分解公式变成看得见的数字**。同时你会发现，几处实验设计上的细节（测试集无噪声、特征没缩放）会让输出和程序自己打印的结论对不上——这些恰好是最好的学习材料。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `true_function(x)` | 函数 | 真实函数 `sin(1.5x) + 0.5x` | 数据生成过程中的 f(x) |
| `generate_data(...)` | 函数 | 在 [−3, 3] 均匀采样 x，加 N(0, 0.5²) 噪声 | `y = f(x) + ε` |
| `fit_polynomial(...)` | 函数 | 构造多项式特征，最小二乘或 Ridge 求系数 | 模型复杂度、L2 正则 |
| `predict_polynomial(x, w)` | 函数 | 用系数做预测 | — |
| `bias_variance_decomposition(...)` | 函数 | **核心**：重复训练，算 Bias²、Variance、Total | 误差分解 |
| `print_decomposition` / `find_optimal` | 函数 | 打印表格、找总误差最小的阶数 | — |
| `demo_basic_decomposition` | 演示 | 7 个阶数的分解表 | U 形曲线 |
| `demo_complexity_tradeoff` | 演示 | 1–15 阶逐个扫描，找偏差/方差交叉点 | 复杂度权衡 |
| `demo_regularization_effect` | 演示 | 10 阶 + λ ∈ {0 … 100} | 正则化换方差 |
| `demo_data_size_effect` | 演示 | 5 阶 + n_train ∈ {10 … 500} | 数据量只降方差 |
| `demo_diagnosis` | 演示 | 1/4/15 阶的训练/测试 MSE 与启发式诊断 | 诊断表 |
| `demo_learning_curves` | 演示 | 1/5/12 阶在不同训练集大小下的平均误差 | 学习曲线 |
| `demo_regularization_sweep` | 演示 | 15 阶 + 11 个 alpha | 正则化扫描 |

调用关系：所有 demo 都依赖 `generate_data` → `fit_polynomial` → `predict_polynomial`；其中 5 个 demo（basic、complexity、regularization_effect、data_size、regularization_sweep）通过 `bias_variance_decomposition` 完成重复训练，`demo_diagnosis` 和 `demo_learning_curves` 则自己写循环。

---

## 3. 逐段精讲

### 3.1 已知真相的数据生成器

```python
def true_function(x):
    return np.sin(1.5 * x) + 0.5 * x


def generate_data(n_samples=30, noise_std=0.5, x_range=(-3, 3), seed=None):
    rng = np.random.RandomState(seed)
    x = rng.uniform(x_range[0], x_range[1], n_samples)
    y = true_function(x) + rng.normal(0, noise_std, n_samples)
    return x, y
```

- 真实函数是"正弦 + 线性"，**不是任何有限阶多项式**，所以任何阶数都有一点偏差——这让实验更接近现实（真实世界里模型族几乎总是"错"的）。
- 噪声标准差 0.5，于是不可约误差 σ² = 0.25，输出表里的 Noise 列恒为 0.2500。
- `np.random.RandomState(seed)` 创建一个**局部**随机数生成器，与全局状态隔离：同一个 seed 永远得到同一份数据，且不会影响别处的随机数。`seed=None` 时从操作系统取熵，每次不同。
- 因为传入的函数是 NumPy 版本（`np.sin`），`x` 可以是整个数组，一次算完所有样本（向量化）。

### 3.2 多项式拟合：`lstsq` 与 Ridge 闭式解

```python
def fit_polynomial(x_train, y_train, degree, lam=0.0):
    X = np.column_stack([x_train ** d for d in range(degree + 1)])
    if lam > 0:
        penalty = lam * np.eye(X.shape[1])
        penalty[0, 0] = 0
        w = np.linalg.solve(X.T @ X + penalty, X.T @ y_train)
    else:
        w = np.linalg.lstsq(X, y_train, rcond=None)[0]
    return w
```

- **设计矩阵**：`np.column_stack` 把 `[1, x, x², …, x^d]` 按列拼成 `(n, d+1)` 的矩阵。多项式回归本质上就是"在扩展特征上的线性回归"，阶数 d 就是复杂度旋钮。
- **无正则**用 `lstsq`：基于 SVD，不需要显式构造 `XᵀX`，数值上更稳；在样本数少于参数数（欠定）时返回**最小范数解**，不会崩溃（测验 Q10）。`[0]` 取返回元组中的系数，其余是残差、秩、奇异值。
- **有正则**用闭式解 `w = (XᵀX + λI)⁻¹ Xᵀy`，但用 `np.linalg.solve` 解方程而不是 `np.linalg.inv` 求逆——"永远不要显式求逆"的工程习惯。λI 让矩阵一定可逆。
- `penalty[0, 0] = 0`：**不惩罚截距**。截距只负责上下平移，惩罚它会引入与复杂度无关的偏差，sklearn 的 `Ridge` 也是如此。
- ⚠️ **没有做特征缩放**：x ∈ [−3, 3] 时 `x¹⁵` 可达约 1.4×10⁷，各列尺度差了好几个数量级。这对 `lstsq` 影响不大，但会让 Ridge 惩罚"厚此薄彼"，是 3.6 节那个反常结果的根源。

```python
def predict_polynomial(x, w):
    degree = len(w) - 1
    X = np.column_stack([x ** d for d in range(degree + 1)])
    return X @ w
```

从系数个数反推阶数，构造同样的特征后做一次矩阵-向量乘法。

### 3.3 核心：`bias_variance_decomposition`

```python
    rng = np.random.RandomState(42)
    x_test = np.linspace(-2.5, 2.5, n_test)
    y_true = true_function(x_test)

    results = {}

    for degree in degrees:
        predictions = np.zeros((n_bootstrap, n_test))

        for b in range(n_bootstrap):
            x_train, y_train = generate_data(
                n_samples=n_train, noise_std=noise_std, seed=rng.randint(0, 100000)
            )
            w = fit_polynomial(x_train, y_train, degree, lam=lam)
            predictions[b] = predict_polynomial(x_test, w)

        mean_pred = predictions.mean(axis=0)
        bias_sq = np.mean((mean_pred - y_true) ** 2)
        variance = np.mean(predictions.var(axis=0))
        total_error = np.mean(np.mean((predictions - y_true) ** 2, axis=1)) + noise_std ** 2
```

把公式逐项对应到代码：

| 公式 | 代码 | 形状 |
|------|------|------|
| 每个训练集 D_b 上的 `f̂_b(x)` | `predictions[b]` | `(n_test,)`，整体 `(200, 100)` |
| `E_D[f̂(x)]` | `predictions.mean(axis=0)` | `(100,)`：沿"训练集"维度平均 |
| `(E[f̂] − f)²` | `(mean_pred - y_true) ** 2` | 每个测试点一个值，再对 x 取平均 |
| `E[(f̂ − E f̂)²]` | `predictions.var(axis=0)` | 每个测试点的方差，再对 x 取平均 |
| σ² | `noise_std ** 2` | 标量，直接加上 |

几个关键设计：

- **测试网格是无噪声的真值** `y_true = true_function(x_test)`：分解公式里的 Bias² 就是相对真实函数 f 定义的，所以这里用真值是对的。
- **测试网格 [−2.5, 2.5] 比训练范围 [−3, 3] 窄**：避免在数据边缘外推。高阶多项式一旦外推，数值会爆炸，这样做能让对比集中在"插值区"。
- **每一轮都生成一份全新的训练集**（`generate_data(seed=rng.randint(...))`）。⚠️ 代码变量名和讲义都叫 "bootstrap"，但这里**并不是** bootstrap（从同一份数据有放回重采样），而是从真实分布重新采样——这恰恰是定义里"对训练集取期望"的正确做法，只是只有在合成数据上才做得到。真实项目中拿不到新数据，才会退而用 bootstrap 近似。
- ⚠️ **`Total` 与 `B+V+N` 必然逐位相等**：对每个测试点有恒等式 `mean_b(p_b − f)² = (p̄ − f)² + mean_b(p_b − p̄)²`（`np.var` 默认 `ddof=0`），而噪声项是直接加上的理论值。所以这两列相等**不是实验验证**，而是代数必然。想要真正验证，需要用带噪声的新标签测误差（测验 Q8 给出实测：5 阶约 0.3016，对比 B+V+N = 0.3007）。讲义 Step 3 的片段里 `total_error` 没有加噪声项，与源码也不一致。
- **随机数的消耗顺序**：`rng` 在函数开头只建一次，循环到下一个阶数时会继续往下抽种子，所以**不同阶数用的是不同的 200 个训练集**；而同一个阶数在不同的调用里，排在第几个决定了它拿到哪些训练集。这就是为什么 5 阶在 `demo_basic_decomposition` 中方差是 0.0495，在 `demo_complexity_tradeoff` 中却是 0.0695——两者都是对同一个量的蒙特卡洛估计，差异就是估计噪声。反过来，`demo_regularization_sweep` 每次只传 `[15]`，每次都从 seed 42 开始，**所有 alpha 共用同一批训练集**（common random numbers），比较起来更公平。

### 3.4 打印与选最优

```python
def find_optimal(results):
    best_degree = min(results, key=lambda d: results[d]["total_error"])
    return best_degree
```

- `min(dict, key=...)` 遍历字典的**键**，按 `key` 函数的返回值比较，返回使总误差最小的那个阶数。比手写循环加 `if` 简洁。
- `print_decomposition` 中 `sorted(results.items())` 按阶数排序后打印，`bvn` 一列就是 3.3 中提到的"必然相等"的那一列。

### 3.5 复杂度扫描与交叉点

```python
    crossover = None
    for d in degrees[:-1]:
        if results[d]["bias_sq"] > results[d]["variance"]:
            if results[d + 1]["bias_sq"] <= results[d + 1]["variance"]:
                crossover = d + 1
                break
```

- 找第一个"上一阶偏差占主导、这一阶方差占主导"的位置。`degrees[:-1]` 去掉最后一个，保证 `d + 1` 不越界。
- ⚠️ 隐含假设 `degrees` 是连续整数（`list(range(1, 16))`），否则 `results[d + 1]` 会 `KeyError`。
- 实际输出交叉点在 4 阶，但总误差最低的是 6 阶（0.3095）：**交叉点 ≠ 最优点**。最优点是 Bias² + Variance 之和最小的位置，不要求两者相等。

### 3.6 正则化：两个 demo，两种结局

```python
    lambdas = [0.0, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
    # ...
    for lam in lambdas:
        results = bias_variance_decomposition([10], lam=lam)
```

- `demo_regularization_effect`（10 阶）结果符合理论：λ 从 0 到 100，方差 2.40 → 0.45，偏差 0.016 → 0.54，总误差在 λ=1 时最低（0.8903），之后回升。
- `demo_regularization_sweep`（15 阶，alpha 0.001–100）却**每一行都是 VARIANCE 占主导**，方差也不随 alpha 单调下降，与程序最后打印的 *"Large alpha: bias dominates"* 相矛盾。

⚠️ 原因（已用实验确认）：

1. **特征没缩放**：Ridge 对每个系数一视同仁地惩罚，而 `x¹⁵` 的尺度是 `x` 的百万倍，高次项只需极小的系数就能让预测大幅摆动，惩罚几乎约束不到它们。
2. **均值被少数极端样本主导**：某些训练集在边缘或中间恰好有大空档，高次项在空档里失控。以 alpha=10 为例，200 次的 MSE 中位数约 0.37，最大值约 2847。
3. 不是 `solve` 的精度问题：换成更稳定的增广 `lstsq` 求解，结果几乎不变。

修复只需在拟合前把 x 缩放到 [−1, 1]，再把系数换算回来（测验 Q11 给出了代码和实测表：缩放后 alpha ≥ 0.1 时偏差占主导，方差稳定在 0.04 左右）。这也是为什么 sklearn 推荐 `PolynomialFeatures → StandardScaler → Ridge` 的管道顺序。

### 3.7 数据量的作用

```python
    sizes = [10, 20, 50, 100, 200, 500]
    # ...
        results = bias_variance_decomposition([5], n_train=n)
```

- n ≥ 20 时：Bias² 稳定在约 0.0011–0.0014，Variance 从 0.22 一路降到 0.0023，与"数据只降方差"的结论吻合。
- n = 10 时 Bias² 竟有 1.41、Variance 235：5 阶有 6 个参数，10 个点离插值阈值很近，个别训练集的拟合会极端离谱。⚠️ 此时 Bias² 也被"污染"了——偏差是用 200 次预测的**均值**估计的，均值本身被极端值拉偏。蒙特卡洛估计在重尾分布下很不稳定，看到这类数字要先怀疑估计方法，而不是理论。

### 3.8 启发式诊断

```python
        if train_mse > 0.5 and test_mse > 0.5 and gap < train_mse * 0.5:
            diagnosis = "HIGH BIAS (underfitting)"
        elif gap > train_mse * 2:
            diagnosis = "HIGH VARIANCE (overfitting)"
        else:
            diagnosis = "REASONABLE FIT"
```

- 把讲义的诊断表翻译成规则：两个误差都高且差距小 → 高偏差；差距超过训练误差 2 倍 → 高方差。
- ⚠️ 阈值 0.5 是**针对这个数据集手调的**（噪声下限 0.25，0.5 约为它的两倍）。换一个数据集、换一个量纲，这些数字就毫无意义。实践中应和"噪声下限 / 人类水平 / 简单基线"比较，而不是用绝对数。
- 这里训练集和测试集都用 `generate_data` 生成（seed 42 与 99），同分布、都带噪声，所以 1 阶模型测试 MSE 略低于训练 MSE（Gap = −0.15）只是抽样波动。
- 函数开头的 `rng = np.random.RandomState(42)` 没有被使用，是残留代码。

### 3.9 学习曲线

```python
    rng = np.random.RandomState(42)
    x_test = np.linspace(-2.5, 2.5, 200)
    y_test = true_function(x_test)
    # ...
            for seed in range(50):
                x_train, y_train = generate_data(n_samples=n, seed=rng.randint(0, 100000))
                try:
                    w = fit_polynomial(x_train, y_train, degree)
                    # ... 计算 train_mse 与 test_mse
                except (np.linalg.LinAlgError, ValueError):
                    continue
```

- 每个训练规模重复 50 次取平均，曲线比单次实验平滑得多。
- `try/except` 防御 SVD 不收敛等罕见异常，出错就跳过这次实验。
- ⚠️ **训练误差和测试误差不可比**：测试标签是**无噪声**真值，训练标签带 σ² = 0.25 的噪声；而且测试 x 只覆盖 [−2.5, 2.5]，训练 x 覆盖 [−3, 3]。于是数据量一大，三个阶数的 Gap 都变成负数（1 阶 n=300 时为 −0.2775），程序打印的 *"High variance (degree 12): train error stays low, test error stays high"* 在大样本时也不成立（12 阶 n=300 时 Test MSE 只有 0.0082）。把测试集改成 `generate_data(n_samples=2000, seed=...)` 这样的同分布数据即可修正，测验 Q9 给出了修正后的实测表。
- 小样本时的巨大数字（12 阶 n=10 的 Test MSE 约 4×10⁹）来自欠定拟合：13 个参数穿过 10 个点，训练误差为 0，点与点之间却剧烈振荡。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用已知的真实函数合成数据 | 只有知道 f(x) 才能精确计算偏差 | 真实数据没有 f(x)，只能用 bootstrap、交叉验证近似 |
| 每轮从真实分布重新采样训练集 | 与"对训练集取期望"的定义完全一致 | 名字叫 bootstrap 但不是 bootstrap，容易混淆 |
| 预测矩阵 `(B, T)` + `axis=0` 聚合 | 向量化，公式与代码一一对应 | 内存 O(B·T)，大规模时可在线累加均值和方差 |
| 噪声项直接加理论值 σ² | 简单 | `Total` 与 `B+V+N` 恒等，无法起到验证作用 |
| 测试网格比训练范围窄 | 避免高阶多项式外推爆炸 | 用于学习曲线时会造成训练/测试分布不一致 |
| `lstsq` 求无正则解 | SVD 稳定，欠定时给最小范数解 | 比正规方程慢一些 |
| Ridge 用 `solve` 闭式解、不惩罚截距 | 与教科书和 sklearn 一致 | 未缩放特征时惩罚失衡；生产中先 `StandardScaler` |
| 用平均值汇总 200 次实验 | 与期望的定义一致 | 对重尾极端值敏感；可同时报告中位数或截尾均值 |
| `warnings.filterwarnings("ignore")` | 让输出干净 | 会掩盖数值问题的警告；调试时应去掉 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import ... as ...` | `import numpy as np` | 起别名，NumPy 的通用约定 |
| 默认参数（含元组、`None`） | `x_range=(-3, 3), seed=None` | 元组是不可变对象，可安全做默认值；`None` 表示"不指定" |
| 关键字参数调用 | `generate_data(n_samples=n_train, noise_std=noise_std, seed=...)` | 按名传参，可读性好、不怕顺序错 |
| 列表推导式喂给 NumPy | `np.column_stack([x_train ** d for d in range(degree + 1)])` | 先生成列的列表，再横向拼成矩阵 |
| 数组的逐元素运算 | `x_train ** d`、`(mean_pred - y_true) ** 2` | NumPy 数组上的算术自动逐元素进行（向量化） |
| `@` 矩阵乘法 | `X.T @ X`、`X @ w` | 等价于 `np.matmul`；`.T` 是转置 |
| 二维索引赋值 | `penalty[0, 0] = 0`；`predictions[b] = ...` | 修改单个元素 / 整行 |
| 取元组的某一项 | `np.linalg.lstsq(...)[0]` | 函数返回多个值时只取需要的那个 |
| `axis` 参数 | `predictions.mean(axis=0)`、`np.mean(..., axis=1)` | `axis=0` 沿行方向压缩（对每列求值），`axis=1` 对每行求值 |
| 嵌套字典 | `results[degree] = {"bias_sq": ..., ...}`；`results[d]["bias_sq"]` | 用字典组织"阶数 → 指标"的结果 |
| `sorted(d.items())` | `for degree, r in sorted(results.items())` | 按键排序后同时拿到键和值 |
| `min` + `key=lambda` | `min(results, key=lambda d: results[d]["total_error"])` | 按自定义标准找最小元素 |
| 切片 | `degrees[:-1]` | 去掉最后一个元素 |
| `float("inf")` | `best_total = float("inf")` | 求最小值时的初始哨兵 |
| 条件表达式 | `"BIAS" if r["bias_sq"] > r["variance"] else "VARIANCE"` | 一行 if/else |
| `try` / `except (A, B)` / `continue` | `except (np.linalg.LinAlgError, ValueError): continue` | 一次捕获多种异常，出错就跳过本轮 |
| f-string 对齐与格式 | `f"{'Degree':>6}"`、`f"{degree:>6d}"`、`f"{lam:>10.3f}"` | `>6` 右对齐占 6 格，`d` 整数，`.3f` 三位小数 |
| 相邻字符串自动拼接 | `print(f"...{r['bias_sq']:>10.4f}  " f"{r['noise']:>10.4f} ...")` | 括号内相邻的字符串字面量会被拼成一个，用于折行 |
| 字符串重复 | `"-" * 70`、`f"  {'-' * 48}"` | 打印分隔线 |
| `warnings` | `warnings.filterwarnings("ignore")` | 全局屏蔽警告 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时依次执行 7 个 demo |

---

## 6. 运行结果解读

实际运行（在临时副本中执行 `python3 bias_variance.py`，约 3.4 秒）的关键输出：

```text
Degree      Bias^2    Variance       Noise       Total       B+V+N
----------------------------------------------------------------------
     1      0.4310      0.0434      0.2500      0.7244      0.7244
     2      0.4124      0.0767      0.2500      0.7391      0.7391
     3      0.0529      0.0397      0.2500      0.3426      0.3426
     5      0.0012      0.0495      0.2500      0.3007      0.3007
     7      0.0005      0.1470      0.2500      0.3975      0.3975
    10      0.0005      0.8690      0.2500      1.1196      1.1196
    15      2.6086    685.4216      0.2500    688.2803    688.2803

Optimal degree: 5
```

- 1、2 阶：Bias² ≈ 0.42 占主导，直线/抛物线抓不住正弦的弯曲（2 阶几乎没改善，因为真实函数是奇函数，偶次项帮不上忙）。
- 3 阶起偏差骤降，5 阶 Bias² 只有 0.0012，总误差 0.3007 已逼近噪声下限 0.25——**典型的"甜点"**。
- 7、10 阶偏差已几乎为 0，方差却快速上升；15 阶方差高达 685，完全失控。U 形曲线一目了然。
- 15 阶的 Bias² 也有 2.6：理论上高阶模型偏差应很小，这里是被极端拟合拉偏的均值（见 3.7）。
- `Total` 与 `B+V+N` 完全一致是代数恒等式，不是实验验证（见 3.3）。

```text
     3      0.0529      0.0397      0.3426          BIAS
     4      0.0486      0.0533      0.3520      VARIANCE
     5      0.0012      0.0695      0.3207      VARIANCE
     6      0.0013      0.0583      0.3095      VARIANCE
     ...
     9      0.5452    109.7721    110.5673      VARIANCE
    10      0.0061      2.6871      2.9433      VARIANCE
    ...
    14   4789.6447  979500.0278  984289.9225      VARIANCE

Bias-variance crossover at degree 4
```

- 交叉点在 4 阶，但总误差最低在 6 阶。
- 9 阶方差 109.8、10 阶反而只有 2.69：高阶区的数字极不稳定。在单独的复现实验中（每个阶数同样 200 个训练集），最差的 5 次贡献了 9 阶 83%、14 阶 95% 的总误差，这些极端样本往往是训练点之间出现了较大空档（例如相邻两点相距 1.3）。读这类表要看**量级和趋势**，不要逐行较真。
- 5 阶方差 0.0695 与上一张表的 0.0495 不同：两张表用的是不同的随机训练集（见 3.3）。

```text
    Lambda      Bias^2    Variance       Total
     0.000      0.0156      2.3985      2.6642
     0.100      0.0086      1.2526      1.5112
     1.000      0.0308      0.6095      0.8903
    10.000      0.2197      0.4370      0.9068
   100.000      0.5432      0.4507      1.2438
```

10 阶 Ridge：方差随 λ 下降、偏差随 λ 上升，总误差在 λ≈1 处触底——正则化扫描的标准形态。

```text
 N_train      Bias^2    Variance       Total
      10      1.4095    235.5828    237.2423
      20      0.0014      0.2233      0.4747
      50      0.0013      0.0251      0.2764
     500      0.0012      0.0023      0.2535
```

n 从 20 增加到 500，方差缩小约 100 倍，偏差纹丝不动，总误差逼近 0.25 的噪声下限。n=10 是插值阈值附近的"灾难区"。

```text
Linear (degree 1):       Train MSE: 0.7997  Test MSE: 0.6493  Diagnosis: HIGH BIAS (underfitting)
Polynomial (degree 4):   Train MSE: 0.3045  Test MSE: 0.3225  Diagnosis: REASONABLE FIT
Polynomial (degree 15):  Train MSE: 0.0647  Test MSE: 3.9481  Diagnosis: HIGH VARIANCE (overfitting)
```

（上面是把多行输出合并后的摘要。）15 阶训练误差 0.065，已经**低于噪声下限 0.25**——模型在拟合噪声，这本身就是过拟合的信号；测试误差 3.95 是训练误差的 60 倍。

```text
  Degree 1 (high bias):
       300      0.7213      0.4439     -0.2775
  Degree 5 (balanced):
       300      0.2497      0.0051     -0.2446
  Degree 12 (high variance):
        10      0.0000  4112260920.5430  4112260920.5430
       300      0.2425      0.0082     -0.2342
```

- 大样本时 Gap 全为负：测试标签无噪声、测试 x 范围更窄（见 3.9），训练误差和测试误差的"地板"不同，这组数字不能按常规学习曲线解读。
- 12 阶 n=10 时训练误差为 0、测试误差上十亿：欠定插值的极端情形。

```text
       Alpha      Bias^2    Variance       Total      Dominant
       0.001      2.0624    315.1559    317.4684      VARIANCE
      10.000      0.3295     31.8656     32.4452      VARIANCE
     100.000      0.5884     47.4248     48.2632      VARIANCE

Optimal alpha: 10.0
```

15 阶 Ridge 在所有 alpha 下都是方差占主导，与程序打印的结论相反——根源是特征未缩放（见 3.6）。

---

## 7. 动手改一改

1. **真正验证分解公式**：在 `bias_variance_decomposition` 里额外用带噪声的测试标签计算经验误差，打印在 `B+V+N` 旁边对比（测验 Q8）。
2. **修学习曲线**：把 `demo_learning_curves` 的测试集改成 `generate_data(n_samples=2000, seed=12345)`，确认 Gap 变为正值，1 阶收敛到约 0.73、5 阶收敛到约 0.25（测验 Q9）。
3. **修正则化扫描**：实现 `fit_polynomial_scaled`（先把 x 除以 3，再把系数除以 `3**d` 换算回来），重跑 `demo_regularization_sweep`，观察偏差何时开始占主导（测验 Q11）。
4. **讲义练习 1**：把 `noise_std` 设为 0，Noise 列变成多少？最优阶数会变高吗？
5. **稳健统计**：在分解函数中同时输出各测试点 MSE 的中位数，或者剔除最差 1% 的训练集后再算方差，对比高阶区的数字是否变得平滑。
6. **讲义练习 5（bagging）**：对 15 阶多项式，从同一份 30 个点里有放回地抽 10 次、拟合 10 个模型取平均，把这个"bagged 模型"放进分解实验，对比方差和偏差的变化。

---

## 8. 常见坑

- **把 `Total == B+V+N` 当作实验验证**：它是恒等式；验证必须用带噪声的独立测试标签。
- **训练/测试误差的口径不一致**：一个对带噪声标签、一个对真值，或者 x 范围不同，学习曲线就会出现"测试比训练还好"的假象。
- **高阶多项式不缩放就加 L2 正则**：惩罚对不同尺度的系数不公平，正则化可能完全失效。用 `StandardScaler` 或先把 x 映射到 [−1, 1]。
- **用 `solve(XᵀX, Xᵀy)` 解欠定问题**：`XᵀX` 奇异；无正则时用 `lstsq`（或加正则）。
- **用平均数汇总重尾结果**：几次灾难性拟合就能让方差翻几十倍，同时看中位数。
- **全局屏蔽警告**：`warnings.filterwarnings("ignore")` 会把溢出、病态矩阵等提示一起藏起来，调试时先注释掉。
