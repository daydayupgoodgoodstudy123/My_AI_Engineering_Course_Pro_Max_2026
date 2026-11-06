# 代码讲解 · convex.py

> **所属小节**：阶段 01 · 数学基础 · 第 18 节 凸优化 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python convex.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`），不需要 NumPy

---

## 1. 这份代码在考察什么

这是一份约 20KB 的"演示型"脚本：前面是几个小而纯的工具函数（凸性检查、2×2 Hessian 特征值、梯度下降、牛顿法、拉格朗日求解器），后面是 9 个 `demo_*` 把讲义里的每个结论都跑一遍、打印出来。学习目标：

1. **凸性能"测"吗**：用随机采样直接检查凸函数的定义——理解它能证伪、不能证明。
2. **曲率决定一切**：Hessian 特征值的符号判断凸 / 鞍点，特征值之比（条件数）决定梯度下降有多慢。
3. **一阶 vs 二阶**：同一个病态二次函数，牛顿法 1 步、GD 几百上千步；但在 Rosenbrock 这种非凸函数上，纯牛顿法会"走错路"。
4. **约束优化的三件套**：拉格朗日乘子（等式约束）、正则化即约束（L1 菱形 vs L2 圆）、对偶（下界与强对偶）。
5. **全部手写**：没有 NumPy，2×2 矩阵求逆、矩阵乘向量都展开成标量公式，每一步都看得见。

> 一句话：**用最小的二维例子，把"凸 → 好优化、条件数 → 速度、约束 → 乘子"这条主线跑通。** 讲解聚焦核心约 60% 的代码，ASCII 画图与总结打印只简要带过。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `check_convexity(f, dim, ...)` | 函数 | 随机采样检查 `f(tx+(1−t)y) ≤ t·f(x)+(1−t)·f(y)` | 凸函数定义 |
| `hessian_eigenvalues_2d(H)` | 函数 | 用迹和行列式求 2×2 矩阵特征值 | 曲率、特征值 |
| `is_positive_semidefinite_2d(H)` | 函数 | 两个特征值都 ≥ 0（带容差） | 半正定 ⇒ 凸 |
| `invert_2x2(H)` / `mat_vec_2d(M, v)` | 函数 | 2×2 求逆、矩阵乘向量 | 牛顿步 `H⁻¹g` |
| `GradientDescent` | 类 | 一步 GD 更新（**文件中未被使用**） | — |
| `optimize_gd(grad_f, x0, ...)` | 函数 | 固定步长梯度下降，返回轨迹 | 一阶方法 |
| `newtons_method(grad_f, hessian_f, x0, ...)` | 函数 | 纯牛顿法（无线搜索），返回轨迹 | 二阶方法 |
| `lagrange_solve(f_grad, g_val, g_grad, x0, ...)` | 函数 | x 梯度下降 + λ 梯度上升 | 拉格朗日乘子、原始-对偶 |
| `demo_convexity_checker` 等 9 个 `demo_*` + `print_summary` | 演示函数 | 每个主题一个演示 | — |
| `if __name__ == "__main__":` | 入口 | 按顺序调用全部演示 | — |

数据流：每个优化器都返回 `history`（轨迹列表），演示函数再从轨迹里挑若干步打印、统计收敛步数。函数本身不打印（`check_convexity` 在传了 `label` 时除外），"算"和"展示"是分开的。

---

## 3. 逐段精讲

### 3.1 凸性检查器：用采样检验定义

```python
def check_convexity(f, dim, bounds=(-5, 5), samples=2000, label=""):
    violations = 0
    worst_violation = 0.0
    for _ in range(samples):
        x = [random.uniform(*bounds) for _ in range(dim)]
        y = [random.uniform(*bounds) for _ in range(dim)]
        t = random.uniform(0, 1)
        mid = [t * xi + (1 - t) * yi for xi, yi in zip(x, y)]
        lhs = f(mid)
        rhs = t * f(x) + (1 - t) * f(y)
        gap = lhs - rhs
        if gap > 1e-10:
            violations += 1
            worst_violation = max(worst_violation, gap)
    is_convex = violations == 0
    status = "CONVEX" if is_convex else "NOT CONVEX"
    # ... 打印 ...
    return is_convex, violations
```

- 一行一行对应定义：随机取两点 x、y 和权重 t，算出连线上的点 `mid`，比较"函数在 mid 的值"(`lhs`) 与"弦在 mid 的高度"(`rhs`)。凸函数要求 `lhs ≤ rhs`。
- `random.uniform(*bounds)`：`*` 把元组 `(-5, 5)` 拆成两个位置参数，等价于 `random.uniform(-5, 5)`。
- `f` 接收的是**列表**（哪怕一维也是 `[x]`），所以演示里写 `lambda x: x[0] ** 2`。这样一维、二维函数可以共用一个接口。
- `1e-10` 容差：真凸函数在 t≈0/1 或 x≈y 时 `lhs` 与 `rhs` 几乎相等，浮点误差可能让 gap 出现 1e-16 的正值，不能算违反。
- 额外记录 `worst_violation`，帮助判断违反是"实质性的"还是"擦边的"。
- ⚠️ **单向可靠**：报告 NOT CONVEX 时找到了实打实的反例；报告 CONVEX 只代表"在 `bounds` 内采样 2000 次没找到反例"。例如 `-cos(x/10)` 在 `[−5, 5]` 内是凸的，默认参数会报 CONVEX，把 `bounds` 放到 `(−50, 50)` 才会发现违反。
- ⚠️ 使用全局 `random` 状态，可复现性依赖演示里的 `random.seed(42)`。

### 3.2 2×2 Hessian 的特征值与半正定判断

```python
def hessian_eigenvalues_2d(H):
    a, b = H[0][0], H[0][1]
    c, d = H[1][0], H[1][1]
    trace = a + d
    det = a * d - b * c
    discriminant = trace ** 2 - 4 * det
    if discriminant < 0:
        return None, None
    sqrt_disc = math.sqrt(discriminant)
    e1 = (trace + sqrt_disc) / 2
    e2 = (trace - sqrt_disc) / 2
    return e1, e2


def is_positive_semidefinite_2d(H):
    e1, e2 = hessian_eigenvalues_2d(H)
    if e1 is None:
        return False
    return e1 >= -1e-10 and e2 >= -1e-10
```

- 2×2 矩阵的特征方程是 `λ² − tr·λ + det = 0`，求根公式 `λ = (tr ± √(tr² − 4det))/2`。这避免了引入任何线性代数库。
- 返回 `e1 ≥ e2`，所以演示里 `e1 / e2` 就是条件数（前提是 e2 > 0）。
- 对称矩阵 `b = c` 时判别式 `= (a − d)² + 4b² ≥ 0`，一定有实特征值；`discriminant < 0` 的分支只在传入非对称矩阵时才会走到，此时返回 `(None, None)`，`is_positive_semidefinite_2d` 判为 False。
- `-1e-10` 容差：数值上等于 0 的特征值（例如半正定但不正定的矩阵）不应因为 `-1e-17` 的舍入被判成"不是半正定"。
- 演示中的几个结论：`[[10,0],[0,2]]` 条件数 5；`[[2,0],[0,-2]]` 有正有负 → 鞍点；`[[2,3],[3,2]]` 特征值 5 和 −1 → 对角元全正也不代表凸；Rosenbrock 在极小点 (1, 1) 处的 Hessian `[[802,-400],[-400,200]]` 特征值 1001.60 和 0.40，**条件数 2508**——极小点附近是一条极其狭长的山谷，这就是 GD 在 Rosenbrock 上慢的原因。

### 3.3 梯度下降：带"安全阀"的最朴素实现

```python
def optimize_gd(grad_f, x0, lr=0.01, steps=1000, tol=1e-12):
    x = list(x0)
    history = [x[:]]
    for _ in range(steps):
        g = grad_f(x)
        if sum(gi ** 2 for gi in g) < tol:
            break
        x = [xi - lr * gi for xi, gi in zip(x, g)]
        if any(math.isnan(xi) or math.isinf(xi) for xi in x):
            break
        history.append(x[:])
    return history
```

- `x = list(x0)` 复制起点，不改调用方的列表；`history.append(x[:])` 存的是**副本**，否则列表里全是同一个对象的引用。
- 停止条件是梯度平方范数 `‖∇f‖² < tol`，不是函数值。
- `any(math.isnan(...) or math.isinf(...))`：学习率过大时 x 会发散到 inf/nan，这里及时停下，避免后续计算报错——这是一个"安全阀"。
- 收敛步数 = `len(history) − 1`（history 包含起点）。
- 上面还有一个 `GradientDescent` 类（`step(params, grads)`），和 `optimize_gd` 里的更新公式完全一样，但**整个文件没有使用它**，可以视为留给读者的"面向对象版本"示意。

### 3.4 牛顿法：用 Hessian 逆替代学习率

```python
def newtons_method(grad_f, hessian_f, x0, steps=100, tol=1e-12):
    x = list(x0)
    history = [x[:]]
    for _ in range(steps):
        g = grad_f(x)
        if sum(gi ** 2 for gi in g) < tol:
            break
        H = hessian_f(x)
        H_inv = invert_2x2(H)
        if H_inv is None:
            break
        dx = mat_vec_2d(H_inv, g)
        x = [x[0] - dx[0], x[1] - dx[1]]
        if any(math.isnan(xi) or math.isinf(xi) for xi in x):
            break
        history.append(x[:])
    return history
```

```python
def invert_2x2(H):
    det = H[0][0] * H[1][1] - H[0][1] * H[1][0]
    if abs(det) < 1e-15:
        return None
    return [
        [H[1][1] / det, -H[0][1] / det],
        [-H[1][0] / det, H[0][0] / det],
    ]
```

- 更新 `x ← x − H⁻¹g`，与 GD 的 `x ← x − lr·g` 并列看：牛顿法把一个标量学习率换成了一个矩阵 `H⁻¹`，在曲率大的方向走小步、曲率小的方向走大步。
- `invert_2x2` 用伴随矩阵公式 `[[d, −b], [−c, a]] / det`；行列式接近 0 时返回 `None`，牛顿法随之停止。
- 对二次函数 `50x² + y²`，`H = diag(100, 2)` 为常数，`H⁻¹g = (x, y)`，一步就到 (0, 0)。
- ⚠️ 这是**纯牛顿法**：不检查 H 是否正定，也没有线搜索，总是走"整步"。在 Rosenbrock 上从 (0.5, 0.5) 出发（该点 Hessian 行列式为 −19600，不定），第 2 步函数值从 0.26 升到 6.24。生产实现会用线搜索 / 信赖域 / Hessian 修正（见测验 Q12 的阻尼牛顿法）。
- ⚠️ 显式求逆在 2×2 时无所谓；n 维时应解线性系统 `H·dx = g`（见第 17 节），而不是求 `H⁻¹`。

### 3.5 拉格朗日求解器：原始下降 + 对偶上升

```python
def lagrange_solve(f_grad, g_val, g_grad, x0, lr=0.01,
                   lr_lambda=0.01, steps=5000):
    x = list(x0)
    lam = 0.0
    history = []
    for _ in range(steps):
        fg = f_grad(x)
        gv = g_val(x)
        gg = g_grad(x)
        x = [
            xi - lr * (fgi + lam * ggi)
            for xi, fgi, ggi in zip(x, fg, gg)
        ]
        lam = lam + lr_lambda * gv
        if any(math.isnan(xi) or math.isinf(xi) for xi in x):
            break
        history.append((x[:], lam, gv))
    return history
```

- 拉格朗日函数 `L(x, λ) = f(x) + λ·g(x)`。`fgi + lam * ggi` 正是 `∂L/∂xᵢ`，所以 x 沿 `−∇ₓL` 下降；`∂L/∂λ = g(x)`，λ 沿 `+g` **上升**。约束问题的解是 L 的鞍点（对 x 最小、对 λ 最大），因此一个降、一个升。
- `zip(x, fg, gg)` 同时遍历三个列表——zip 可以接任意多个可迭代对象。
- 直观理解：约束被违反（g > 0）时 λ 变大，相当于加重"罚款"把 x 拉回约束面；收敛时 g → 0，λ 停止变化。
- 演示 1：`min x² + y²` s.t. `x + y − 1 = 0`，从 (2, 2) 出发，λ 先上冲到约 0.71（第 54 步），然后回落、越过 0，在第 365 步左右下探到约 −1.08，约 1000 步后稳定到 **−1**，与解析解一致。λ 为负是因为 g 写成了 `x + y − 1`（等式约束的乘子符号不受限制）。
- 演示 2：`min (x−3)² + (y−3)²` s.t. `x + 2y = 4`，用更小的步长 0.002 跑 20000 步，得到 `x = 2, y = 1, λ = 2`，误差 2.75e-14。
- ⚠️ `history` 里存的 `gv` 是**更新前**的 x 处的约束值，而 x 是更新后的值：第 1 行显示 x = y = 1.96，但 g 列是 3.0（初始点 (2, 2) 处的值）。收敛后差别可以忽略。
- ⚠️ 这种原始-对偶梯度法对步长比较敏感（两个演示用了不同的 lr 和步数），不保证一般问题收敛；生产中用增广拉格朗日法（加 `ρ/2·g²` 项）或专门的 QP / 凸优化求解器。

### 3.6 条件数实验：闭包与默认参数

```python
    for c in conditions:
        def grad_f(x, c=c):
            return [2 * c * x[0], 2 * x[1]]

        def hess_f(x, c=c):
            return [[2 * c, 0], [0, 2]]

        def f_val(x, c=c):
            return c * x[0] ** 2 + x[1] ** 2

        start = [10.0, 10.0]
        lr = 0.9 / (2 * c)

        gd_hist = optimize_gd(grad_f, start, lr=lr, steps=2000)
        newton_hist = newtons_method(grad_f, hess_f, start, steps=50)
```

- 对 `f = c·x² + y²`，Hessian 特征值是 2c 和 2，条件数恰好是 c。
- `lr = 0.9/(2c)`：让陡峭方向的收缩因子固定为 `1 − 0.9 = 0.1`（稳定上限是 `lr < 2/λ_max = 1/c`），平缓方向的收缩因子则是 `1 − 0.9/c`，越来越接近 1。这样设计保证每个 c 下 GD 都**稳定**，比较的纯粹是"条件数对速度的影响"。
- **`def grad_f(x, c=c)` 的用意**：Python 闭包是**晚绑定**的——函数体里的 `c` 在调用时才去查。默认参数在 `def` 执行时求值，相当于把当前的 c "拍照"存下来。本例中函数在同一轮循环里就被调用，不写 `c=c` 结果也一样；但如果把这些函数存进列表、循环结束后再调用，没有 `c=c` 的版本会全部用到最后一个 c（=100）。这是防御式写法。
- 结果：c = 1, 5, 10, 50, 100 时 GD 分别需要 8, 85, 179, 926, 1860 步，牛顿法始终 1 步。步数大约与条件数成正比（理论估算见测验 Q10）。

### 3.7 正则化几何：L2 投影与 L1 顶点

```python
    x_l2 = [3.0 / math.sqrt(13), 2.0 / math.sqrt(13)]
```

```python
    for x_cand in [i * 0.001 for i in range(1001)]:
        y_cand = 1.0 - x_cand
        val = (x_cand - 3) ** 2 + (y_cand - 2) ** 2
        if val < best_val:
            best_val = val
            best_x = [x_cand, y_cand]

    for y_cand_raw in [i * 0.001 for i in range(1001)]:
        x_cand = 1.0 - y_cand_raw
        val = (x_cand - 3) ** 2 + (y_cand_raw - 2) ** 2
        # ...
```

- 目标 `(x−3)² + (y−2)²` 是"到点 (3, 2) 距离的平方"，所以 L2 单位圆约束下的解就是把 (3, 2) **投影**到单位圆上：`(3, 2)/√13 ≈ (0.832, 0.555)`，两个坐标都非零。代码直接写出了这个解析解，而不是数值求解。
- ⚠️ 这个投影公式只在目标函数"各向同性"（等高线是圆）时成立；一般的损失（椭圆等高线）需要真正求解约束问题。
- L1 部分用 0.001 步长枚举菱形边界，找到最优点 (1, 0)，目标值 8，恰好是顶点——第二个坐标被"压"成了 0，这就是稀疏性。
- ⚠️ 两个循环其实扫描的是**同一条边**（第一象限的 `x + y = 1`，只是参数化方式不同），并没有扫描整个菱形边界，打印的 "Scanning diamond boundary..." 有误导性。本例中无约束最优点 (3, 2) 在第一象限，最优点必然在这条边上，所以结论没错；如果把目标中心改到 (−3, 2)，扫描结果就会出错，而下面硬编码的 4 个顶点比较仍会正确给出 (−1, 0)。
- 函数开头定义的 `unconstrained_min()` 没有被调用，属于遗留代码。

### 3.8 Rosenbrock：一阶 vs 二阶的真实差距

```python
    def rosenbrock_grad(x):
        dx = -2 * (1 - x[0]) + 200 * (x[1] - x[0] ** 2) * (-2 * x[0])
        dy = 200 * (x[1] - x[0] ** 2)
        return [dx, dy]

    def rosenbrock_hessian(x):
        h00 = 2 - 400 * x[1] + 1200 * x[0] ** 2
        h01 = -400 * x[0]
        h10 = -400 * x[0]
        h11 = 200
        return [[h00, h01], [h10, h11]]
```

- `f = (1−x)² + 100(y − x²)²`：梯度用链式法则手推（`200·(y − x²)·(−2x)` 就是第二项对 x 求导），Hessian 再求一次导。这个函数是凸优化之外的经典测试函数：极小点在 (1, 1)，但位于一条弯曲的狭长山谷里，且**整体非凸**。
- 结果：纯牛顿法 5 步到达 (1, 1)，中途第 2 步函数值上升；GD（lr = 0.001）10000 步后 f 仍有 1.64e-5，没达到 1e-6 的阈值——极小点附近条件数约 2508，GD 每步只能挪一点点。
- ⚠️ 打印语句写的是 `Newton converged (f < 1e-12)`，但 `newtons_method` 实际的停止条件是 `‖∇f‖² < 1e-12`，而且即使因 Hessian 奇异或达到步数上限而退出，也会打印 "converged"。

### 3.9 对偶演示与 ASCII 地形（简述）

- `demo_duality_intuition` 是**纯打印的手推过程**：`min x² + y²` s.t. `x + y ≥ 1`，写成 `1 − x − y ≤ 0`，求出对偶函数 `d(λ) = λ − λ²/2`，最大值在 λ* = 1，`d* = p* = 0.5`，约束活跃且互补松弛 `λ·(1 − x − y) = 0`。代码里 `lam_star = 1.0` 是直接写死的，没有数值求解。
- `demo_convex_vs_nonconvex_landscape` 在字符网格上逐行"扫描"函数值，`|val − threshold|` 小于阈值的位置画 `*`。其中 `elif val < threshold: line += " "` 与 `else: line += " "` 两个分支做的事情完全一样，是冗余分支。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库、2×2 展开公式 | 每个数都看得见，不被 NumPy 抽象挡住 | 只能处理二维；生产用 NumPy / SciPy / CVXPY |
| 采样法检查凸性 | 实现简单，适用于任何"黑盒"函数 | 只能证伪；严格证明靠 Hessian 或凸函数运算规则 |
| 优化器返回完整 `history` | 方便打印轨迹、统计收敛步数 | 大规模问题内存开销大；生产中只记录日志 / 指标 |
| 纯牛顿法（无线搜索） | 公式最干净，二次函数上展示"一步到位" | 非凸 / 远离极小点时不稳；需线搜索、信赖域或 Hessian 修正 |
| 显式 `invert_2x2` | 2×2 求逆是一行公式 | n 维时应解线性系统，不求逆 |
| NaN/Inf 安全阀 | 学习率过大时优雅停止 | 生产中还会记录发散原因、自动降学习率 |
| 原始-对偶梯度法解约束问题 | 直接体现"x 降、λ 升"的鞍点结构 | 步长敏感；生产用增广拉格朗日、内点法、SQP |
| L2 解析投影 + L1 枚举 | 直观展示"圆 vs 菱形" | 只适用于本例的各向同性目标；L1 扫描只覆盖一条边 |
| 对偶部分硬编码 | 讲清推导过程即可 | 可用数值方法（对 λ 做投影梯度上升）验证 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `for _ in range(n)` | `for _ in range(samples)` | 不需要循环变量时用 `_` |
| 字符串乘法 | `"=" * 65`、`'-' * 48` | 快速生成分隔线 |
| 多重赋值 | `a, b = H[0][0], H[0][1]` | 一行给多个变量赋值 |
| 返回多个值 | `return e1, e2`；`return None, None` | 实际返回一个元组，调用方解包 `e1, e2 = ...` |
| `None` 哨兵与 `is None` | `if H_inv is None: break` | 用 `None` 表示"算不出来" |
| 条件表达式 | `"CONVEX" if is_convex else "NOT CONVEX"` | 一行版 if-else |
| 参数解包 `*` | `random.uniform(*bounds)` | 把元组拆成多个位置参数 |
| 默认参数 | `def check_convexity(f, dim, bounds=(-5, 5), samples=2000, label="")` | 调用时可省略；默认值在 `def` 执行时求值一次 |
| 列表推导式 | `[t * xi + (1 - t) * yi for xi, yi in zip(x, y)]` | 一行生成新列表 |
| 生成器表达式 | `sum(gi ** 2 for gi in g)`；`max(v for _, v in corner_vals)` | 不建中间列表，直接喂给 `sum` / `max` |
| `zip` 多个序列 | `zip(x, fg, gg)` | 同时遍历三个列表 |
| `any()` | `any(math.isnan(xi) or math.isinf(xi) for xi in x)` | 只要有一个为真就返回 True（短路） |
| 列表切片复制 | `history.append(x[:])` | 存副本而不是引用 |
| 元组作为记录 | `history.append((x[:], lam, gv))`；`x, lam, gv = history[i]` | 轻量"结构体"，按位置解包 |
| `lambda` 匿名函数 | `lambda x: x[0] ** 2` | 把一个简单函数当参数传入 |
| 嵌套函数 | `demo_newtons_method` 里的 `def f(x)`、`def grad_f(x)` | 只在该演示中使用的局部函数 |
| 闭包晚绑定与 `c=c` | `def grad_f(x, c=c)` | 用默认参数"冻结"循环变量的当前值 |
| f-string 格式符 | `{label:30s}`（左对齐宽 30）、`{'Step':>6s}`（右对齐）、`{i:6d}`、`{p[0]:12.8f}`、`{gd_final:14.2e}` | 打印对齐的表格 |
| 隐式字符串拼接 + 括号续行 | `print(f"..." f"...")`、`print(f"..." + (f"..." if ... else ""))` | 长语句跨行书写 |
| `float('inf')` | `best_val = float('inf')` | "当前最优值"的初始值，任何数都比它小 |
| `math` 模块 | `math.sqrt`、`math.exp`、`math.sin`、`math.cos`、`math.isnan`、`math.isinf` | 标量数学函数 |
| 类（未使用） | `class GradientDescent: def step(self, params, grads)` | 面向对象版本的优化器写法示意 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行演示 |

---

## 6. 运行结果解读

已在临时副本中实际运行（Python 3.13，耗时约 0.2 秒）。关键输出：

```text
  f(x) = x^2                      CONVEX      violations: 0/2000
  f(x) = max(0, x) [ReLU]         CONVEX      violations: 0/2000
  f(x) = sin(x)                   NOT CONVEX  violations: 1017/2000  worst: 1.989821
  f(x) = -x^2                     NOT CONVEX  violations: 2000/2000  worst: 22.057393
  f(x,y) = x^2 - y^2 [saddle]     NOT CONVEX  violations: 994/2000  worst: 22.098641
```

上面 5 个凸函数零违反；`−x²` 是严格凹函数，每一次采样都违反（2000/2000）；`x² − y²` 约一半违反——沿 x 方向凸、沿 y 方向凹。

```text
  Rosenbrock at minimum (1, 1)
  Eigenvalues: 1001.60, 0.40
  Condition number: 2508.0
```

极小点处半正定（正定），但条件数 2508，预示 GD 会很慢。

```text
  Newton's method: 1 steps to converge
       1    0.00000000    0.00000000      0.00000000
  Gradient descent (lr=0.015): 500 steps taken
       1   -5.00000000    9.70000000   1344.09000000
       5   -0.31250000    8.58734026     78.62522519
  GD reached f < 1e-10 at step 454
```

`50x² + y²`：牛顿 1 步。GD 的 x 分量收缩因子是 `1 − 0.015·100 = −0.5`，所以 x 在正负之间跳（10 → −5 → 2.5 …），但很快衰减；y 分量收缩因子 0.97，是瓶颈，第 454 步 f 才降到 1e-10，500 步时梯度仍未达到停止阈值。

```text
    Cond #    GD steps    Newton steps   GD final loss
         1           8               1        2.00e-14
       100        1860               1        2.48e-13
```

条件数扩大 100 倍，GD 步数从 8 增加到 1860；牛顿法不受影响。

```text
       1    1.9600    1.9600    0.0300    3.000000    7.683200
      50    0.5626    0.5626    0.7047    0.162437    0.632955
     500    0.5192    0.5192   -1.0232    0.038803    0.539240
    1000    0.5000    0.5000   -1.0001    0.000033    0.500036
  lambda = -1.000000
  Constraint violation: 2.66e-15
  ...
  Solution: x = 2.000000, y = 1.000000
  lambda = 2.000000
```

λ 先上升（初始约束被大幅违反，g = 3 > 0）再回落、越过 0，过冲到约 −1.08（第 365 步附近，表中第 500 步还是 −1.0232），最后稳定在 −1：原始-对偶动力学带有阻尼振荡。第二个问题也精确收敛到解析解。

```text
  Projected solution: (0.832050, 0.554700)
  Best on edges: (1.0000, 0.0000), objective = 8.0000
    (  1.0,   0.0)  objective = 8.0 <-- best corner
```

L2 解两个坐标都非零；L1 解落在顶点 (1, 0)。

```text
       1    0.489796    0.239796      0.26030929
       2    0.989592    0.729496      6.23991465     ← 纯牛顿法的函数值上升了
       5    1.000000    1.000000      0.00000000
    9999    0.995951    0.991902      0.00001642     ← GD 一万步仍未到 1e-6
  Newton converged (f < 1e-12) in 5 steps
  GD did not reach f < 1e-06 in 10000 steps (final: 1.64e-05)
```

对偶部分输出 `Primal objective: 0.5`、`Dual objective: 0.5`、`Complementary slackness: ... = 0.0`，验证了强对偶和互补松弛。

---

## 7. 动手改一改

1. 完成讲义练习 1：用 `check_convexity` 测试 `x⁴`、`x·y`、`max(x, 0)`；再测 `-math.cos(x[0] / 10)`，分别用默认 `bounds` 和 `bounds=(-50, 50)`，体会"CONVEX 不等于证明"。
2. 把 `demo_regularization_geometry` 的 L1 扫描改成真正扫描菱形的 4 条边，然后把目标中心从 (3, 2) 改为 (−3, 2)，对比修改前后 "Best on edges" 的结果（正确答案是顶点 (−1, 0)，目标值 8）。
3. 给 `newtons_method` 加上回溯线搜索和"Hessian 不正定时退回负梯度"（参考测验 Q12），在 Rosenbrock 上从 (0.5, 0.5) 和 (−1.2, 1) 出发，验证函数值单调下降。
4. 给 `optimize_gd` 加动量（heavy-ball：`v = β·v − lr·g; x = x + v`），在 `c = 100` 的二次函数上调 β，观察所需步数是否从约 κ 量级降到约 √κ 量级。
5. 把 `lagrange_solve` 改造成支持**不等式约束**的版本：λ 更新后做投影 `lam = max(0.0, lam + lr_lambda * gv)`，用它数值求解 `demo_duality_intuition` 的问题，验证 λ → 1。
6. 修正两个小问题：让 `history` 记录更新后的 x 对应的约束值；把 Rosenbrock 演示的输出改成如实反映停止原因（梯度阈值 / Hessian 奇异 / 步数上限）。

---

## 8. 常见坑

- **把采样检查的 "CONVEX" 当成证明**：它只覆盖 `bounds` 内的随机点，区间外或极小区域内的非凸性都可能漏掉。
- **学习率超过 `2/λ_max`**：GD 会振荡甚至发散；`lr = 1/c` 恰好使陡峭方向振荡不收敛。最大特征值定步长上限，最小特征值定速度。
- **以为牛顿法每步都下降**：Hessian 不定或离极小点远时，纯牛顿步可能让函数值上升（Rosenbrock 演示第 2 步）。
- **拉格朗日乘子的符号**：λ 的正负取决于约束写成 `g = x + y − 1` 还是 `1 − x − y`；不等式约束 `g ≤ 0` 才要求 `λ ≥ 0`。
- **闭包晚绑定**：在循环里定义函数并稍后调用，会全部用到循环变量的最后一个值；用默认参数 `c=c` 或 `functools.partial` 固定。
- **轨迹存引用而不是副本**：`history.append(x)` 之后若原地修改 x，历史记录会被一起改掉；本文件每次都创建新列表并存 `x[:]`，规避了这个问题。
