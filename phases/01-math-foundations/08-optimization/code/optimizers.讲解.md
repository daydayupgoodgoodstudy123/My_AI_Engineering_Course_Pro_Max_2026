# 代码讲解 · optimizers.py

> **所属小节**：阶段 01 · 数学基础 · 第 08 节 优化 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python optimizers.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`），无需 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这份脚本用纯 Python 从零实现了深度学习里最常用的三个优化器，并在两个经典"地形"上做对比实验：

1. **三个优化器的更新公式**：`GradientDescent`、`SGDMomentum`、`Adam` 各用十几行代码写成，统一接口 `step(params, grads) → new_params`，让你看清它们到底差在哪一行。
2. **Rosenbrock 函数基准**：弯曲狭长的山谷——"找到谷底容易，沿着谷底走到 (1,1) 很难"，能直观暴露 GD 的慢、动量的加速、Adam 的自适应。
3. **超参数的影响**：学习率扫描（太小太慢 / 太大发散）、动量系数扫描（β 越大有效步长越大）。
4. **鞍点逃逸**：在 `f = x² - y²` 上比较谁能更快离开原点。
5. **训练工程意识**：`optimize` 里的 NaN/Inf/溢出检测、收敛步数统计、ASCII 收敛曲线——都是真实训练循环里"监控与保护"的缩影。

> 一句话：**所有优化器都只是在回答"下一步往哪走、走多远"，这份代码让你用同一个接口、同一个地形，把这三种回答并排比较**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `rosenbrock` / `rosenbrock_gradient` | 函数 | 测试函数及其解析梯度 | 损失函数与梯度 |
| `GradientDescent` | 类 | `p - lr·g` | 普通梯度下降 |
| `SGDMomentum` | 类 | 维护速度 `velocity`，`v = β·v + g; p - lr·v` | 动量 |
| `Adam` | 类 | 维护 `m、v、t`，带偏差修正的自适应步长 | Adam |
| `optimize` | 函数 | 训练循环：反复求梯度、调用 `step`、记录轨迹；遇到 NaN/Inf/溢出提前停止 | 训练循环 + 发散保护 |
| `distance_to_minimum` / `find_convergence_step` | 函数 | 计算到 (1,1) 的欧氏距离；找到 loss 首次 < 1e-4 的步数 | 收敛判据 |
| `print_trajectory` / `print_ascii_convergence` | 函数 | 打印轨迹表格；画 log10(loss) 的 ASCII 曲线 | 可视化 |
| `demo_comparison` | 演示 | 三个优化器在 Rosenbrock 上跑 5000 步 | 优化器对比 |
| `demo_learning_rate_effect` | 演示 | GD 用 4 个学习率 | 学习率敏感性 |
| `demo_momentum_effect` | 演示 | 动量系数 0 / 0.5 / 0.9 / 0.99 | 动量的作用 |
| `demo_saddle_point` | 演示 | 鞍点 `x² - y²` 上 200 步 | 鞍点逃逸 |

数据流：每个 demo 构造"优化器实例 + 目标函数 + 梯度函数 + 起点"，交给 `optimize` 得到轨迹 `history`（参数列表的列表），再交给打印函数展示。**优化器只看梯度，不看损失值**，这与 PyTorch 的 `optimizer.step()` 设计一致。

---

## 3. 逐段精讲

### 3.1 Rosenbrock 函数与手推梯度

```python
def rosenbrock(params):
    x, y = params
    return (1 - x) ** 2 + 100 * (y - x ** 2) ** 2


def rosenbrock_gradient(params):
    x, y = params
    df_dx = -2 * (1 - x) + 200 * (y - x ** 2) * (-2 * x)
    df_dy = 200 * (y - x ** 2)
    return [df_dx, df_dy]
```

- `f(x,y) = (1-x)² + 100(y-x²)²`，全局最小值 `f(1,1) = 0`。
- 梯度用链式法则手推：`∂/∂x (1-x)² = -2(1-x)`；`∂/∂x 100(y-x²)² = 200(y-x²)·(-2x)`。代码把 `(-2 * x)` 单独写出来，就是为了让"外层导数 × 内层导数"的链式结构一目了然。
- 为什么它难：系数 100 让"垂直于山谷"的方向非常陡、"沿着山谷"的方向非常平缓。lr 大了会在两壁之间震荡，lr 小了沿谷底走不动——这正是动量和 Adam 要解决的问题（病态条件数）。
- 起点 `(-1, 1)` 处 `f = 4`，梯度为 `(-4, 0)`：恰好在抛物线 `y = x²` 上，y 方向梯度为 0。

### 3.2 `GradientDescent`：一行算法

```python
class GradientDescent:
    def __init__(self, lr=0.001):
        self.lr = lr

    def step(self, params, grads):
        return [p - self.lr * g for p, g in zip(params, grads)]
```

- 就是讲义里的 `w = w - lr * gradient`，用列表推导对每个参数逐一更新。
- **无状态**：除了 `lr` 不需要记住任何历史。
- 返回新列表而不是原地修改 `params`，避免调用方持有的列表被意外改写（`optimize` 中的 `history` 依赖这一点）。

### 3.3 `SGDMomentum`：速度 = 历史梯度的累积

```python
class SGDMomentum:
    def __init__(self, lr=0.001, momentum=0.9):
        self.lr = lr
        self.momentum = momentum
        self.velocity = None

    def step(self, params, grads):
        if self.velocity is None:
            self.velocity = [0.0] * len(params)
        self.velocity = [
            self.momentum * v + g
            for v, g in zip(self.velocity, grads)
        ]
        return [p - self.lr * v for p, v in zip(params, self.velocity)]
```

- 公式：`v = β·v + g`，`p = p - lr·v`。这是 PyTorch `torch.optim.SGD(momentum=...)` 采用的写法（另一种常见写法是 `v = β·v + (1-β)·g`，两者只差一个 lr 的缩放）。
- **懒初始化**：`velocity` 初始为 `None`，第一次调用 `step` 时才根据参数个数建成全 0 列表。这样构造优化器时不需要知道参数维度。
- 关键直觉：梯度方向稳定时，`v → g/(1-β)`，β=0.9 时有效步长放大约 10 倍；梯度方向来回翻转时，正负相抵，`v` 很小，震荡被抑制。
- ⚠️ **有状态**：一个 `SGDMomentum` 实例只能服务一个优化过程。每个 demo 都新建实例，正是为了避免上一次运行残留的速度污染下一次。
- 当 `momentum=0` 时，`velocity = g`，与 `GradientDescent` 完全等价——`demo_momentum_effect` 中 β=0.00 那一行与 GD lr=0.0001 的结果逐位相同，就是这个原因。

### 3.4 `Adam`：一阶矩 + 二阶矩 + 偏差修正

```python
    def step(self, params, grads):
        if self.m is None:
            self.m = [0.0] * len(params)
            self.v = [0.0] * len(params)

        self.t += 1

        self.m = [
            self.beta1 * m + (1 - self.beta1) * g
            for m, g in zip(self.m, grads)
        ]
        self.v = [
            self.beta2 * v + (1 - self.beta2) * g ** 2
            for v, g in zip(self.v, grads)
        ]

        m_hat = [m / (1 - self.beta1 ** self.t) for m in self.m]
        v_hat = [v / (1 - self.beta2 ** self.t) for v in self.v]

        return [
            p - self.lr * mh / (vh ** 0.5 + self.epsilon)
            for p, mh, vh in zip(params, m_hat, v_hat)
        ]
```

逐行对应讲义公式：

| 代码 | 公式 | 含义 |
|------|------|------|
| `self.t += 1` | `t ← t+1` | 步数从 1 开始计，偏差修正要用 |
| `self.m = [...]` | `m = β1·m + (1-β1)·g` | 梯度的指数滑动平均（方向） |
| `self.v = [...]` | `v = β2·v + (1-β2)·g²` | 梯度平方的指数滑动平均（幅度） |
| `m_hat`、`v_hat` | `m/(1-β1ᵗ)`、`v/(1-β2ᵗ)` | 修正 0 初始化带来的偏小 |
| `return [...]` | `p - lr·m̂/(√v̂ + ε)` | 每个参数有自己的有效步长 |

- **`self.t += 1` 必须放在计算 `m_hat` 之前**：若 t 仍为 0，`1 - β1⁰ = 0`，会触发 `ZeroDivisionError`。
- **为什么除以 `√v̂`**：`m̂/√v̂` 近似"梯度均值 / 梯度均方根"，是一个量级约为 1 的无量纲数。所以 Adam 每步的位移约为 `lr`，**与梯度绝对大小基本无关**。第一步尤其明显：`m̂ = g, v̂ = g²`，步长恰好是 `lr·sign(g)`——从 `(-1,1)` 出发、梯度 `(-4,0)`，第一步后 x 精确地移动 0.01。
- `ε = 1e-8` 加在开方**之后**（与原论文一致），防止 `v̂ = 0` 时除零。y 方向梯度为 0 时，`0/(0+1e-8) = 0`，参数不动。
- ⚠️ 简化：没有 weight decay（AdamW）、没有 AMSGrad 变体、没有梯度裁剪；列表推导而非向量化。

### 3.5 `optimize`：训练循环与发散保护

```python
def optimize(optimizer, func, grad_func, start, steps=5000):
    params = list(start)
    history = [params[:]]
    for _ in range(steps):
        try:
            grads = grad_func(params)
            if any(math.isnan(g) or math.isinf(g) or abs(g) > 1e15 for g in grads):
                break
            params = optimizer.step(params, grads)
            if any(math.isnan(p) or math.isinf(p) or abs(p) > 1e15 for p in params):
                break
            history.append(params[:])
        except (OverflowError, ValueError):
            break
    return history
```

- 这是所有训练循环的骨架：**算梯度 → 优化器更新 → 记录**。
- `list(start)` 和 `params[:]` 都是为了**复制**：`history` 里存的每一项都是独立的列表，后续更新不会改到历史记录。
- 发散保护分三层：
  1. 梯度中出现 NaN / Inf / 绝对值超过 `1e15` → 停止；
  2. 更新后的参数出现同样情况 → 停止（**不把坏参数写入 history**）；
  3. 计算中抛出 `OverflowError`（如 `float ** 2` 溢出）或 `ValueError` → 停止。
- 因此发散时 `history` 会比 `steps + 1` 短，且最后一项是"最后一个还算正常的参数"。例如 GD lr=0.005 只记录了 7 步，最后一项约为 `(462476, 3775)`，loss 约 `4.6e24`。
- ⚠️ 参数 `func` 在函数体内**没有被使用**（损失只在打印时由调用方计算）。保留它是为了接口对称，但属于冗余参数。
- ⚠️ 只捕获 `OverflowError` 和 `ValueError`；`ZeroDivisionError` 等其他错误会直接抛出——对于真正的代码 bug，这反而是好事。
- `any(... for g in grads)`：生成器 + 短路求值，遇到第一个满足条件的元素就返回 `True`。

### 3.6 收敛判据与轨迹打印

```python
def distance_to_minimum(params, target=(1.0, 1.0)):
    return math.sqrt(sum((p - t) ** 2 for p, t in zip(params, target)))


def find_convergence_step(history, func, threshold=1e-4):
    for i, params in enumerate(history):
        if func(params) < threshold:
            return i
    return len(history)
```

- `distance_to_minimum` 衡量"离 (1,1) 有多远"。在 Rosenbrock 上，loss 小不代表距离小：山谷底部 loss 很低，但可能离 (1,1) 还很远。所以表格同时打印 Loss 和 Dist 两列。
- `find_convergence_step` 返回 loss **首次**低于 `1e-4` 的步数；从未达到时返回 `len(history)` 作为"哨兵值"，调用方用 `conv_step < len(history)` 判断是否收敛。
- ⚠️ "收敛"的阈值在不同 demo 中不一致：ASCII 图用 `< 1e-4`，`demo_learning_rate_effect` 却用 `loss < 0.01` 判为 "converged"。所以 GD lr=0.001（loss 0.0036）在学习率表里显示 converged，而 SGD+M（loss 0.0036）在 ASCII 图里显示 did not converge——阅读输出时要注意。

`print_trajectory` 的要点：

```python
    total = len(history) - 1
    interval = max(1, total // steps_to_show)
    # ...
    for i in range(0, total + 1, interval):
        # ...
    if total % interval != 0:
        # 额外打印最后一步
```

- 等间隔抽取约 10 行；`max(1, ...)` 防止 history 很短（例如发散）时 `interval = 0` 导致 `range` 报错。
- 如果最后一步没被抽到，就补打一行，保证总能看到终点。

### 3.7 ASCII 收敛曲线

```python
        max_log = 5.0
        min_log = -8.0
        log_range = max_log - min_log

        bar = []
        for loss in losses:
            log_loss = math.log10(loss + 1e-15)
            log_loss = max(min_log, min(max_log, log_loss))
            normalized = (log_loss - min_log) / log_range
            pos = int(normalized * (width - 1))
            bar.append(pos)
```

- 把 loss 取 `log10`，再**夹紧**到 `[-8, 5]`，线性映射到 0~49 的列位置，画一个 `*`。左边是 `1e-8`，右边是 `1e+5`，越靠左越好。
- `+ 1e-15` 防止 `log10(0)` 抛出 `ValueError`。
- 为什么用对数坐标：loss 从 4 降到 1e-11 横跨 11 个数量级，线性坐标下后期的变化完全看不见。训练曲线通常也用对数纵轴。
- 每隔 `5000 // 40 = 125` 步采样一个点，共 41 行。

### 3.8 四个演示

```python
    configs = [
        ("Gradient Descent", GradientDescent(lr=0.0005)),
        ("SGD + Momentum",   SGDMomentum(lr=0.0001, momentum=0.9)),
        ("Adam",             Adam(lr=0.01)),
    ]
```

- **`demo_comparison`**：三者的学习率**不同**（0.0005 / 0.0001 / 0.01），各自取了一个"不发散"的值，所以这不是严格的公平对比，而是"各自在合理设置下的表现"。注意 SGD+M 的有效学习率约 `0.0001/(1-0.9) = 0.001`，比 GD 的 0.0005 还大，这也是它领先 GD 的原因之一。
- **`demo_learning_rate_effect`**：`diverged = loss > 1e10 or isnan or isinf`；发散时打印的 `'nan' / 'inf'` 是**占位文本**，不是真实数值（真实的最后一步 loss 约 `4.6e24`，是有限数）。
- **`demo_momentum_effect`**：固定 lr=0.0001，只改 β。
- **`demo_saddle_point`**：在函数内部定义 `saddle` 和 `saddle_gradient` 两个**嵌套函数**，只在这个 demo 内使用，不污染模块命名空间。判定 `escaped = abs(final[1]) > 1.0` 是一个人为阈值。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 统一 `step(params, grads)` 接口 | 优化器可互换，训练循环无需改动（鸭子类型） | PyTorch 中优化器持有参数引用并原地更新：`optimizer.step()` |
| 返回新列表、不原地修改 | 无副作用，`history` 安全 | 大模型中会原地更新以节省显存 |
| 状态懒初始化（`None`） | 构造时不需要知道参数维度 | PyTorch 用 `state` 字典按参数懒初始化，思路相同 |
| 解析梯度而非数值差分 | 精确且快 | 真实网络用自动微分（第 05 节） |
| NaN/Inf/1e15 检测后 `break` | 发散时不崩溃、仍能打印结果 | 生产中配合梯度裁剪、loss scaling、自动回滚 checkpoint |
| 三个优化器用不同 lr | 让每个都在"可工作"的设置下展示 | 公平对比应对每个优化器各自做 lr 扫描 |
| 纯 Python 列表 | 每个参数的更新清清楚楚 | 生产中张量化、在 GPU 上批量计算 |
| 恒定学习率 | 聚焦优化器本身 | 实际训练必须配学习率调度（见第 7 节练习） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组解包 | `x, y = params` | 把长度为 2 的列表拆成两个变量 |
| 幂运算 `**` | `(1 - x) ** 2`、`vh ** 0.5`、`self.beta1 ** self.t` | 平方、开方、求幂 |
| 整除 `//` 与取余 `%` | `total // steps_to_show`、`total % interval != 0` | 整数除法；判断能否整除 |
| 列表乘法 | `[0.0] * len(params)`、`[' '] * width` | 创建 n 个相同元素的列表（元素为不可变对象时安全） |
| 列表推导式 | `[p - self.lr * g for p, g in zip(params, grads)]` | 逐元素计算新列表 |
| 三路 `zip` | `zip(params, m_hat, v_hat)` | 同时遍历三个序列 |
| `None` + 懒初始化 | `self.velocity = None` … `if self.velocity is None:` | 用 `is None` 判断是否首次调用 |
| 复制列表 | `list(start)`、`params[:]` | 浅拷贝，避免共享引用 |
| `any` + 生成器 | `any(math.isnan(g) or ... for g in grads)` | 只要有一个为真就返回 True，且短路 |
| `math.isnan` / `math.isinf` | 发散检测 | NaN 不等于任何值（包括自己），必须用 `isnan` 判断 |
| `try / except (A, B)` | `except (OverflowError, ValueError): break` | 用元组同时捕获多种异常 |
| `enumerate` | `for i, params in enumerate(history)` | 同时拿到下标与元素 |
| `range(start, stop, step)` | `range(0, total + 1, interval)` | 按步长取样 |
| 默认参数为元组 | `target=(1.0, 1.0)` | 用不可变的元组作默认值是安全的（不要用列表） |
| 条件表达式 | `"DIVERGED" if diverged else ("converged" if loss < 0.01 else "slow")` | 一行 if-else，可嵌套 |
| 嵌套函数 | `demo_saddle_point` 内的 `def saddle(params)` | 局部定义、局部使用 |
| `str.join` | `''.join(line)` | 把字符列表拼成字符串 |
| f-string 对齐格式 | `{'Step':>6s}`、`{name:<22s}`、`{i:6d}`、`{p[0]:10.6f}`、`{final_loss:.2e}` | `>` 右对齐、`<` 左对齐、数字为宽度；`d` 整数、`f` 定点小数、`e` 科学计数法 |
| 字符串乘法 | `'=' * 60`、`'-' * 52` | 生成分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 4 个 demo |

---

## 6. 运行结果解读

实际运行（`timeout 60 python3 optimizers.py`，约 0.1 秒），关键输出：

```text
Starting point: (-1.0, 1.0), f = 4.0

  Gradient Descent                       ← lr=0.0005
     500   -0.768425    0.598560      3.13386082    1.8134
    1500    0.038803    0.000934      0.92393153    1.3864   ← 先滑到谷底，再沿谷底慢慢爬
    5000    0.798131    0.636104      0.04083385    0.4161   ← 5000 步仍离 (1,1) 0.42

  SGD + Momentum                         ← lr=0.0001, β=0.9
    1000    0.359922    0.126455      0.41065399    1.0830
    5000    0.940412    0.884127      0.00355685    0.1303

  Adam                                   ← lr=0.01
     500    0.933027    0.870275      0.00449236    0.1460
    1000    0.998732    0.997461      0.00000161    0.0028
    5000    0.999992    0.999984      0.00000000    0.0000

  Gradient Descent: final loss: 4.08e-02, converged (< 1e-4): did not converge
  SGD + Momentum:   final loss: 3.56e-03, converged (< 1e-4): did not converge
  Adam:             final loss: 6.35e-11, converged (< 1e-4): step 767

  LEARNING RATE EFFECT ON GRADIENT DESCENT
    0.0001   -0.446368    0.206459      2.09718513  slow
    0.0005    0.798131    0.636104      0.04083385  slow
    0.0010    0.939826    0.883023      0.00362714  converged
    0.0050         nan         nan             inf  DIVERGED   ← 占位文本，实际 7 步内飞到 4.6e24

  MOMENTUM EFFECT ON SGD
    0.00   -0.446368    0.206459      2.09718513   ← 与 GD lr=0.0001 逐位相同
    0.50    0.363386    0.129014      0.40619883   ← 有效 lr 0.0002
    0.90    0.940412    0.884127      0.00355685   ← 有效 lr 0.001，≈ GD lr=0.001
    0.99    1.000000    1.000000      0.00000000   ← 有效 lr 0.01，GD 用这么大早就发散了

  SADDLE POINT ESCAPE: f(x,y) = x^2 - y^2
  Gradient Descent          0.000176    0.524849     -0.275466  no
  SGD + Momentum           -0.000000  4729020.438514  -22363634307887.484375  yes
  Adam                     -0.000000    3.033698     -9.203325  yes
```

逐项解读：

- **GD 的两阶段**：前 1500 步先从山坡滑到谷底（loss 从 4 降到 0.92，Dist 却只从 2.0 降到 1.39），之后沿着平缓的谷底缓慢前进。这就是"找到山谷容易，沿着山谷走很难"。
- **有效学习率**：β=0.5 的结果 `0.363386, 0.129014` 与 GD lr=0.0002 的结果（约 `0.363466, 0.129074`）几乎相同，β=0.9 与 GD lr=0.001 几乎相同——验证了 `lr_eff ≈ lr/(1-β)`。而 β=0.99 等效于 lr=0.01，GD 在 lr=0.005 时就发散了，动量却能稳定收敛——因为动量平均掉了陡峭方向上的来回震荡。
- **Adam 后期的尖峰**：ASCII 曲线中，Adam 在约 1250 步后贴住最左边（loss < 1e-8），但在 2125、2750、3250、3750、4250、4875 步等位置又跳回右侧——例如第 2125 步 loss 回升到约 `1.8e-4`。原因是 Adam 的步长约为 lr、不会随梯度变小而自动缩小，在极小值附近会"过冲"再回来。这正是需要**学习率衰减**的直接证据（给 Adam 加余弦衰减后，2000 步后的最大 loss 可降到 1e-15 量级）。
- **学习率扫描的非单调性**：额外实验表明 GD 在 lr=0.002 时 5000 步 loss 约 `5.6e-5`，但 lr=0.003、0.004 反而变差（约 0.30、0.57），lr=0.005 发散。临界区附近的学习率会在山谷两壁之间震荡，"更大的 lr"并不总是"更快"。
- **鞍点**：GD 的 y 每步乘 1.02，200 步后为 0.5248，未超过人为阈值 1.0，所以标为 `no`，但它其实在逃离，第 233 步就会超过 1。SGD+M 的 y 冲到约 473 万——在 `x² - y²` 这种无下界的函数上，"逃离鞍点"等价于"奔向负无穷"。Adam 每步约前进 lr，200 步后到 3.03（大于 2 是因为梯度持续变大时 `m̂/√v̂` 会略大于 1）。

---

## 7. 动手改一改

1. **（入门）** 讲义练习 1：把 `demo_learning_rate_effect` 的 `rates` 改成 `[0.0001, 0.0005, 0.001, 0.002, 0.003, 0.005, 0.01]`，找出"仍能收敛的最大学习率"，并观察 0.003 为什么反而比 0.002 差。
2. **（入门）** 讲义练习 3：把鞍点 demo 的 `steps` 改成 250，GD 是否变成 `yes`？再把起点改成 `[0.01, 0.0]`，三种优化器还能逃出来吗？在 `saddle_gradient` 返回值上加 `random.gauss(0, 1e-3)` 噪声再试一次。
3. **（进阶）** 讲义练习 4：写 `GDExpDecay`（`lr = lr_0 · 0.999^t`），比较有无衰减的结果，解释为什么在 Rosenbrock 上衰减让 GD 变差（提示：`Σ 0.999ᵗ ≈ 1000`）。
4. **（进阶）** 实现 Nesterov 动量：先按当前速度"往前看"一步，在前瞻点求梯度，再更新速度。需要把 `grad_func` 传给优化器，或者改写 `optimize` 的调用方式。
5. **（进阶）** 给 `Adam` 加 `weight_decay` 参数，分别实现"L2 加到梯度上"和"AdamW 解耦衰减"两种版本，在 Rosenbrock 上（目标点改为带衰减后的新最优）比较差别。
6. **（挑战）** 实现 `cosine_with_warmup(step, total, lr_max, lr_min, warmup)`，给 Adam 套上该调度，重新画 ASCII 曲线，确认 2000 步之后的 loss 尖峰消失。

---

## 8. 常见坑

- **`self.t` 自增的位置**：放到偏差修正之后会让第一步 `1 - β⁰ = 0` 而除零。
- **复用有状态的优化器实例**：`SGDMomentum`、`Adam` 都会记住历史，跑新实验必须新建实例（PyTorch 中则要重新创建或 `load_state_dict`）。
- **用"最终 loss"判断谁更好**：不同优化器用了不同 lr，对比前应对各自做 lr 扫描；同时注意本文件中"converged"的阈值在不同 demo 里不一样（1e-4 vs 0.01）。
- **把 `'nan'/'inf'` 占位符当成真实值**：`demo_learning_rate_effect` 在发散时打印的是固定字符串，真实最后一步是有限的大数。
- **以为 Adam 的步长随梯度变小而变小**：`m̂/√v̂` 量级约为 1，步长约为 lr，所以 Adam 在后期也需要学习率衰减。
- **混淆两种动量写法**：`v = βv + g`（本文件、PyTorch）与 `v = βv + (1-β)g`，同样的 lr 下前者步长大约是后者的 `1/(1-β)` 倍，迁移超参数时要换算。
