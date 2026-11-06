# 代码讲解 · derivatives.py

> **所属小节**：阶段 01 · 数学基础 · 第 04 节 机器学习微积分 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python derivatives.py` ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码把"微积分如何让神经网络学习"拆成 7 个可以运行的小实验：

1. **数值导数**：用中心差分逼近导数，并与 5 个函数的解析导数对拍——这就是后面"梯度检查"的原型。
2. **梯度**：对多元函数逐个维度做差分，得到偏导数向量。
3. **梯度下降**：在 1D（`x²`）和 2D（`x² + y²`）上看参数如何一步步滑向最小值。
4. **Hessian 与临界点分类**：用二阶差分求 Hessian，用特征值区分鞍点和极小值，再看病态的 Rosenbrock 函数。
5. **泰勒展开**：0/1/2 阶近似在离展开点越来越远时如何失效——解释"为什么学习率要小"。
6. **线性回归训练循环**：手推 MSE 梯度、手动更新 `w` 和 `b`，这是所有训练循环的骨架。

> 一句话：**先用"笨办法"（有限差分）算出梯度，再用它驱动梯度下降**——等到下一节学自动微分时，你就知道它在替你省掉什么。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `numerical_derivative(f, x, h)` | 函数 | 中心差分求一元导数 | 导数定义、数值微分 |
| `numerical_gradient(f, point, h)` | 函数 | 对每个维度做中心差分 | 偏导数、梯度 |
| `gradient_descent_1d` / `gradient_descent_nd` | 函数 | 通用梯度下降并记录历史 | 梯度下降（⚠️ 定义了但 demo 中未调用） |
| `hessian_2d(f, x, y, h)` | 函数 | 二阶差分求 2×2 Hessian | 曲率、Hessian |
| `taylor_approx(...)` | 函数 | 0/1/2 阶泰勒近似 | 泰勒展开 |
| `hessian_eigenvalues(H)` | 函数 | 2×2 特征值公式 | 用特征值判断临界点类型 |
| `demo_*` × 7 | 演示函数 | 分主题打印结果 | — |

数据流：`demo_*` 定义具体函数（多为 `lambda` 或内部函数）→ 交给 `numerical_*` / `hessian_2d` / `taylor_approx` 计算 → 打印并与解析结果对比。线性回归 demo 不依赖数值导数，而是直接用**手推的解析梯度**。

---

## 3. 逐段精讲

### 3.1 `numerical_derivative`：中心差分

```python
def numerical_derivative(f, x, h=1e-7):
    return (f(x + h) - f(x - h)) / (2 * h)
```

- 来自导数定义 `f'(x) = lim (f(x+h) - f(x)) / h`，但用的是**中心差分**：在 x 两侧各取一个点。
- **为什么用中心差分**：泰勒展开后，`f''` 等偶次项在相减时抵消，截断误差是 O(h²)；前向差分是 O(h)。同样的 h，中心差分准确得多。
- **函数作为参数**：`f` 是一个可调用对象（普通函数或 `lambda`），这是 Python "函数是一等公民" 的体现——数值导数不关心 f 内部长什么样，任何函数都能求导。
- ⚠️ `h=1e-7` 的取舍：h 太大截断误差大，h 太小则 `f(x+h)` 与 `f(x-h)` 几乎相等，相减会丢失有效数字（灾难性抵消）。中心差分的理论最优 h 约为 `ε^(1/3) ≈ 6e-6`（ε 是双精度机器精度 2.2e-16），默认的 1e-7 稍偏小，所以运行结果中误差在 1e-9 量级而不是更小（测验 Q9 有完整的 h 扫描）。

### 3.2 `numerical_gradient`：逐维扰动

```python
def numerical_gradient(f, point, h=1e-7):
    gradient = []
    for i in range(len(point)):
        point_plus = list(point)
        point_minus = list(point)
        point_plus[i] += h
        point_minus[i] -= h
        partial = (f(point_plus) - f(point_minus)) / (2 * h)
        gradient.append(partial)
    return gradient
```

- **偏导数的定义直接落地**：只扰动第 i 个分量、其他分量不动，就是"把其他变量当常数"。
- `list(point)` 每次都**复制一份**，保证对 `point_plus[i]` 的修改不会影响原始 `point`，也不会影响下一维的计算。如果写成 `point_plus = point`，两个名字指向同一个列表，结果全错。
- **代价**：n 维参数需要 `2n` 次函数求值。一个有 1 亿参数的网络算一次梯度就要 2 亿次前向传播——这就是为什么训练时用反向传播（一次前向 + 一次反向就得到全部梯度），而数值梯度只用于**调试检查**。
- `demo_gradient` 中，`f(x,y) = x² + 3xy + y²` 在 (1, 2) 的数值梯度 `[8, 7]` 与解析梯度 `[2x+3y, 3x+2y]` 一致。

### 3.3 梯度下降：1D 与 2D

```python
def demo_gradient_descent_1d():
    # ...
    x = 5.0
    lr = 0.1
    for step in range(20):
        grad = 2 * x
        x = x - lr * grad
        if step % 4 == 0 or step == 19:
            print(f"  step {step:2d}  x={x:8.4f}  f(x)={x**2:10.6f}")
```

- 核心就一行：`x = x - lr * grad`。对 `f(x) = x²`，`grad = 2x`，所以每步 `x ← (1 - 2·lr)·x = 0.8x`，20 步后 `5 × 0.8²⁰ ≈ 0.0576`，与输出一致。
- 这里用的是**解析梯度** `2 * x`，而 2D 版本用的是**数值梯度**：

```python
    point = [4.0, 3.0]
    lr = 0.1
    for step in range(30):
        grad = numerical_gradient(f, point)
        point = [p - lr * g for p, g in zip(point, grad)]
```

- `[p - lr * g for p, g in zip(point, grad)]` 对每个维度同时更新——这就是向量形式的 `w ← w - lr·∇L`。
- 注意 `(4, 3)` 两个坐标以**相同比例**缩小（每步 ×0.8），所以点沿直线奔向原点：因为 `x² + y²` 的等高线是圆，负梯度直接指向圆心。
- `step % 5 == 0 or step == 29`：只打印部分步骤，避免刷屏。

```python
def gradient_descent_1d(f, df, x0, lr=0.1, steps=20):
    x = x0
    history = []
    for step in range(steps):
        grad = df(x)
        x = x - lr * grad
        history.append((step, x, f(x)))
    return x, history
```

- ⚠️ 文件开头定义的 `gradient_descent_1d` 和 `gradient_descent_nd` 是可复用的通用版本（返回最终点和 `(step, 点, 函数值)` 历史），但 `__main__` 里的 demo **都没有调用它们**，而是把循环写在了 demo 内部。它们适合拿来做练习（例如讲义练习 2：最小化 `(x-3)² + (y+1)²`，实测 100 步后收敛到 `[3.0, -1.0]`）。
- `gradient_descent_nd` 中 `history.append((step, list(point), f(point)))` 用 `list(point)` 存副本，避免历史记录里所有元素指向同一个被不断修改的列表（虽然此处 `point` 每步都是新列表，复制是一种防御性写法）。

### 3.4 `hessian_2d`：二阶有限差分

```python
def hessian_2d(f, x, y, h=1e-5):
    fxx = (f(x + h, y) - 2 * f(x, y) + f(x - h, y)) / (h ** 2)
    fyy = (f(x, y + h) - 2 * f(x, y) + f(x, y - h)) / (h ** 2)
    fxy = (f(x + h, y + h) - f(x + h, y - h) - f(x - h, y + h) + f(x - h, y - h)) / (4 * h ** 2)
    return [[fxx, fxy], [fxy, fyy]]
```

- `fxx`：二阶中心差分 `(f(x+h) - 2f(x) + f(x-h)) / h²`，是"导数的导数"的离散版。
- `fxy`：混合偏导，用四个角点 `(±h, ±h)` 构造。对光滑函数 `∂²f/∂x∂y = ∂²f/∂y∂x`，所以返回的矩阵是**对称的**（`[0][1]` 和 `[1][0]` 用同一个值）。
- **为什么 `h=1e-5` 而不是 `1e-7`**：分母是 `h²`，舍入误差被放大到 `ε/h²` 量级。h=1e-7 时 `h² = 1e-14`，误差会到 1e-2；h=1e-5 时约 1e-6，可以接受。
- ⚠️ 接口不统一：`numerical_gradient` 接收 `f(point)`（一个列表），`hessian_2d` 接收 `f(x, y)`（两个参数）。所以 demo 里为两者分别定义了不同签名的函数。

### 3.5 `hessian_eigenvalues` 与临界点分类

```python
def hessian_eigenvalues(H):
    a, b = H[0][0], H[0][1]
    c, d = H[1][0], H[1][1]
    trace = a + d
    det = a * d - b * c
    discriminant = trace ** 2 - 4 * det
    if discriminant < 0:
        return None, None
    sqrt_disc = discriminant ** 0.5
    return (trace + sqrt_disc) / 2, (trace - sqrt_disc) / 2
```

- 和上一节 `eigenvalues_2x2` 同一个公式：`λ = (tr ± √(tr² - 4det)) / 2`。
- 对**对称**矩阵（Hessian 总是对称的），`tr² - 4det = (a - d)² + 4b² ≥ 0`，判别式永远非负，特征值一定是实数。所以 `discriminant < 0` 返回 `None` 的分支理论上不会被触发，只是防御性代码（极端舍入下可能出现 -1e-16 这样的值）。
- 判断规则：两个特征值都 > 0 → 极小；都 < 0 → 极大；一正一负 → 鞍点。

```python
    print("\nf(x,y) = x^2 - y^2 (saddle function)")
    H = hessian_2d(saddle, 0.0, 0.0)
    e1, e2 = hessian_eigenvalues(H)
    # ...
    print("  Mixed signs --> SADDLE POINT")
```

- ⚠️ 结论字符串是**硬编码**的（`"Mixed signs --> SADDLE POINT"`），并不是根据 `e1, e2` 自动判断得出的。换成别的函数，这行仍会打印同样的结论。练习中可以把它改成自动分类（见第 7 节）。
- **Rosenbrock 函数** `(1-x)² + 100(y-x²)²` 在最小点 (1,1) 处 Hessian 为 `[[802, -400], [-400, 200]]`，特征值 1001.6 和 0.4：都为正，确认是极小值；但两个特征值相差约 2500 倍（**条件数**很大），等高线是一条狭长弯曲的"香蕉形峡谷"。梯度下降在这里会走得极慢——这正是它被用作优化算法基准测试函数的原因。

### 3.6 `taylor_approx`：用导数构造多项式

```python
def taylor_approx(f, f_prime, f_double_prime, x0, h, order=2):
    result = f(x0)
    if order >= 1:
        result += f_prime(x0) * h
    if order >= 2:
        result += 0.5 * f_double_prime(x0) * h ** 2
    return result
```

- 直接对应 `f(x0+h) ≈ f(x0) + f'(x0)·h + ½f''(x0)·h²`。`order` 控制加到第几项。
- 传入三个函数：原函数、一阶导、二阶导。对 `eˣ` 三个都是 `math.exp`；对 `sin` 是 `math.sin`、`math.cos`、`lambda x: -math.sin(x)`。
- **为什么这和优化有关**：一阶近似是梯度下降的"世界观"——它假设函数在附近是线性的；二阶近似是牛顿法的世界观。h 一大，近似就失效，所以梯度下降必须小步走。

### 3.7 线性回归：完整的训练循环

```python
    random.seed(42)
    w = random.gauss(0, 1)
    b = random.gauss(0, 1)
    lr = 0.01

    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [3.0, 5.0, 7.0, 9.0, 11.0]

    for epoch in range(200):
        total_loss = 0
        dw = 0
        db = 0
        for x, y in zip(xs, ys):
            pred = w * x + b
            error = pred - y
            total_loss += error ** 2
            dw += 2 * error * x
            db += 2 * error
        dw /= len(xs)
        db /= len(xs)
        total_loss /= len(xs)
        w -= lr * dw
        b -= lr * db
```

- **梯度推导**：`L = mean((wx + b - y)²)`。由链式法则，`∂L/∂w = mean(2·(wx+b-y)·x)`，`∂L/∂b = mean(2·(wx+b-y)·1)`。代码里的 `dw += 2 * error * x` 和 `db += 2 * error` 就是逐样本累加这两个式子，最后 `/= len(xs)` 取平均。
- **四步骨架**：前向预测（`pred`）→ 计算损失（`total_loss`）→ 计算梯度（`dw, db`）→ 更新参数（`w -= lr * dw`）。讲义说"每个基于梯度的训练循环都遵循这个模式"，PyTorch 只是把第三步换成了 `loss.backward()`。
- **全批量梯度下降**：每个 epoch 用全部 5 个样本算一次梯度、更新一次参数。
- `random.gauss(0, 1)`：从标准正态分布随机初始化；`random.seed(42)` 保证可复现。
- `w -= lr * dw` 是增量赋值，等价于 `w = w - lr * dw`。
- ⚠️ 打印的 `loss` 是**更新前**参数的损失（先累加 loss，后更新 w、b）。
- ⚠️ 200 轮后结果是 `y = 2.08x + 0.73`，**并没有完全收敛**到 `2x + 1`。原因是 x 未中心化导致问题病态（Hessian 条件数约 70），截距方向收敛极慢——详见第 6 节与测验 Q10。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 数值导数用中心差分 | 截断误差 O(h²)，比前向差分准 | 每个维度 2 次函数求值，O(n) 次前向；生产用自动微分 |
| 一阶差分 `h=1e-7`、二阶差分 `h=1e-5` | 二阶差分除以 h²，h 必须更大 | 最优 h 与函数尺度有关；梯度检查一般用 float64、h≈1e-5～1e-6 |
| 线性回归用手推解析梯度 | 展示"推导 → 实现"的完整过程 | 复杂模型手推不现实，交给 autograd |
| 全批量梯度下降 | 数据只有 5 个点，最简单 | 大数据集用 mini-batch SGD |
| 固定学习率 0.01 | 简单、保证稳定 | 本例偏保守，200 轮未收敛；实际会调参、用学习率调度或 Adam，并先做特征标准化 |
| Hessian 只做 2×2 | 能用特征值公式直接分类 | 大模型无法构造 Hessian，只能用 Hessian-向量积或近似 |
| 结论字符串硬编码 | 演示目的明确 | 应根据特征值符号自动判断 |
| 定义了通用 `gradient_descent_*` 但 demo 内联循环 | demo 中每一步都看得见 | 代码重复；通用函数更适合复用和测试 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def numerical_derivative(f, x, h=1e-7)` | 不传 h 就用 1e-7；科学计数法 `1e-7` 即 0.0000001 |
| 函数作为参数 | `numerical_derivative(f, x)` 中的 `f` | 函数是对象，可以像变量一样传递和调用 |
| `lambda` 匿名函数 | `lambda x: x**2`、`lambda x: -math.sin(x)` | 一行定义的小函数，常用于传参 |
| 嵌套函数 | `demo_gradient` 内部的 `def f(point)` | 在函数内部定义函数，只在该 demo 内可见 |
| 元组列表 + 解包遍历 | `for name, f, df in test_cases:` | 每个测试用例是 `(名字, 函数, 导函数)` 三元组 |
| 序列解包 | `x, y = point` | 把二元列表拆成两个变量 |
| `list()` 复制 | `point_plus = list(point)` | 生成新列表，避免修改原数据 |
| 增量赋值 | `point_plus[i] += h`、`w -= lr * dw`、`dw /= len(xs)` | `a op= b` 等价于 `a = a op b` |
| 列表推导式 + `zip` | `[p - lr * g for p, g in zip(point, grad)]` | 逐维度同时更新参数 |
| 返回多个值 | `return x, history`、`return (trace + ...)/2, (...)/2` | 实际返回一个元组，调用方用 `e1, e2 = ...` 接收 |
| `None` 作为返回值 | `return None, None` | 表示"无有效结果" |
| 取模判断 | `if step % 4 == 0 or step == 19` | 每隔 4 步打印一次，并确保打印最后一步 |
| f-string 格式说明符 | `{x:8.4f}`、`{err:12.2e}`、`{name:<12}`、`{'Numerical':>12}` | 宽度 + 精度；`e` 为科学计数法；`<` 左对齐、`>` 右对齐 |
| 字符串乘法 | `"=" * 55`、`"-" * 50` | 重复字符串画分隔线 |
| `math` 函数 | `math.sin`、`math.cos`、`math.exp` | 标准库数学函数 |
| `random.gauss` / `random.seed` | `random.gauss(0, 1)` | 正态分布采样；固定种子保证可复现 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时依次执行 7 个 demo |

---

## 6. 运行结果解读

在临时副本中实际运行 `python3 derivatives.py`，关键输出如下：

```text
At x = 2.0:
Function        Numerical   Analytical        Error
x^2              4.000000     4.000000     4.33e-09
x^3             12.000000    12.000000     6.32e-09
sin(x)          -0.416147    -0.416147     1.12e-10
e^x              7.389056     7.389056     7.50e-09
1/x             -0.250000    -0.250000     1.32e-10
```

数值导数与解析导数在 6 位小数上完全一致，误差在 1e-9～1e-10。误差主要来自**浮点舍入**而不是截断（h²=1e-14 远小于 1e-9），说明 `h=1e-7` 已经偏小。

```text
  Numerical gradient:  [8.0000, 7.0000]
  Analytical gradient: [8.0, 7.0]
```

```text
  step  0  x=  4.0000  f(x)= 16.000000     ← 5 × 0.8
  step  4  x=  1.6384  f(x)=  2.684355     ← 5 × 0.8⁵
  step 19  x=  0.0576  f(x)=  0.003323     ← 5 × 0.8²⁰
```

每步乘以 `1 - 2·lr = 0.8`，是标准的**线性收敛**（误差按固定比例缩小）。

```text
  step  0  ( 3.2000,  2.4000)  f=16.000000
  step 29  ( 0.0050,  0.0037)  f=0.000038
```

两个坐标保持 4:3 的比例同步缩小，沿直线走向原点。

```text
Rosenbrock f(x,y) = (1-x)^2 + 100*(y-x^2)^2
  Hessian at minimum (1,1):
    [  802.00   -400.00]
    [ -400.00    200.00]
  Eigenvalues: 1001.60, 0.40
```

两个特征值都为正 → 极小值；但比值约 2500，极度病态。

```text
Approximating f(x) = e^x near x0 = 1.0
       h    True f(x0+h)     Order 0     Order 1     Order 2
     0.1        3.004166    2.718282    2.990110    3.003701   ← 二阶误差仅 5e-4
     2.0       20.085537    2.718282    8.154845   13.591409   ← 离得远，全都不准
Approximating f(x) = sin(x) near x0 = 0
     1.0        0.841471    0.000000    1.000000    1.000000   ← 一阶 = 二阶
```

- 近处（h=0.1）二阶近似几乎精确；远处（h=2）所有近似都失效——这就是"学习率太大时梯度下降会出问题"的直观版本。
- `sin` 的一阶和二阶完全相同，因为 `sin''(0) = 0`，二阶项为 0（测验 Q6）。

```text
  epoch   0  w=0.3980  b=-0.0208  loss=67.032927
  epoch  40  w=2.1296  b=0.5319  loss=0.040145
  epoch 199  w=2.0757  b=0.7268  loss=0.013675

Learned: y = 2.08x + 0.73
Actual:  y = 2.00x + 1.00
```

- 前 40 轮 loss 从 67 骤降到 0.04（大特征值方向快速收敛），之后进入"慢车道"：loss 每 40 轮只下降约 25%。
- 最终 `b = 0.73` 离 1 还差不少。MSE 对 `(w, b)` 的 Hessian 是 `2·[[11, 3], [3, 1]]`，特征值约 23.66 和 0.34；沿小特征值方向每步误差只缩小到 `1 - 0.01×0.34 ≈ 0.9966`，200 步后才缩小一半左右。
- 实测改进：训练 2000 轮得到 `w=2.0002, b=0.9994`；把 x 中心化后 `lr=0.1` 训练 200 轮直接得到精确的 `w=2.0, b=1.0`（测验 Q10）。

---

## 7. 动手改一改

1. **h 扫描**：对 `x³` 在 x=2 处，用 `h = 1e-1, 1e-3, …, 1e-13` 调用 `numerical_derivative`，打印误差，画出（或观察）U 形曲线，找到最优 h。
2. **二阶导数**（讲义练习 1）：用两次 `numerical_derivative` 实现 `numerical_second_derivative`，验证 `x³` 在 x=2 处为 12。注意默认 `h=1e-7` 会让误差高达 0.08，需要把 h 调大到 1e-4 左右。
3. **用上闲置的函数**（讲义练习 2）：调用 `gradient_descent_nd` 最小化 `(x-3)² + (y+1)²`，从 (0,0) 出发，确认收敛到 (3, -1)。
4. **自动分类临界点**：写 `classify(e1, e2)`，根据特征值符号返回 "minimum" / "maximum" / "saddle"，替换 `demo_hessian` 里硬编码的结论字符串；再测试 `f(x,y) = x² + 3xy + y²` 在原点（应为鞍点）。
5. **学习率实验**：在 `demo_gradient_descent_1d` 中分别试 `lr = 0.5, 0.9, 1.0, 1.1`，观察一步到位、震荡收敛、永久震荡、发散四种行为。
6. **动量**（讲义练习 3）：在 `f(x) = x⁴ - 3x²` 上实现带动量的梯度下降 `v ← β·v + grad; x ← x - lr·v`，与普通梯度下降比较到达极小点（`x = ±√1.5`）所需的步数。

---

## 8. 常见坑

- **h 越小越准？** 不是。h 太小时 `f(x+h) - f(x-h)` 发生灾难性抵消，误差反而变大；二阶差分对 h 更敏感。
- **列表别名**：`point_plus = point` 只是起了个别名，修改 `point_plus[i]` 会改到原列表。必须 `list(point)` 或 `point[:]` 复制。
- **梯度符号写反**：`w = w + lr * grad` 会沿上坡方向走，loss 越来越大。
- **忘了除以样本数**：`dw` 没有 `/= len(xs)` 时，梯度随数据量线性增大，等价于学习率被放大 N 倍，很容易发散。
- **只看 Hessian 对角线判断极值**：`[[2,3],[3,2]]` 对角线全正，却是鞍点。要看特征值（或行列式与迹）。
- **把"loss 还在降"当成"已经收敛"**：本文件的线性回归 loss 已经很小（0.0137），但参数离真值仍有明显偏差。判断收敛要看梯度范数或参数变化量，而不只是 loss。
