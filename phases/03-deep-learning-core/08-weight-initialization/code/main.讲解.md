# 代码讲解 · main.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 08 节 权重初始化和训练稳定性（Weight Initialization and Training Stability） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 11 秒跑完，主要耗时在 50 层前向实验） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码用 5 个实验把"初始化"这件看起来不起眼的事拆开来看：

1. **对称性**：全零初始化时，同一层的神经元输出完全相同（STEP 1）。
2. **方差公式**：用蒙特卡洛采样验证 `Var(z) = fan_in · Var(w) · Var(x)`，看四种初始化下单层输出方差分别是多少（STEP 2）。
3. **深度的指数效应**：64 宽、50 层的网络里，方差系数稍大或稍小都会在几层内爆炸或消失（STEP 3、STEP 4）。
4. **初始化与激活要匹配**：Xavier 配 sigmoid/tanh、Kaiming 配 ReLU。
5. **浅网络 vs 深网络**：在只有一个隐藏层的网络上训练，看初始化对最终 loss 的影响（STEP 5），并体会"为什么浅网络上看不出差别"。

> 一句话：**初始化的目标是让每一层的"方差放大系数"等于 1**。这份代码让你亲眼看到系数偏离 1 时，50 层之后会发生什么，也让你看到衡量指标选不好时会得出错误结论。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `zero_init` / `random_init` / `xavier_init` / `kaiming_init` | 函数 | 生成 `fan_out × fan_in` 的权重矩阵（二维列表） | 四种初始化策略 |
| `sigmoid` / `tanh_act` / `relu` | 函数 | 三种激活函数 | 与初始化配对 |
| `forward_deep` | 函数 | 100 个样本过 50 层（每层 64 宽、新初始化），返回每层的平均绝对激活值 | 方差传播 |
| `magnitude_report` | 函数 | 每 5 层打印一行文本条形图 | 可视化 |
| `symmetry_demo` | 函数 | 4 个神经元、全零权重，展示输出完全相同 | 对称性问题 |
| `variance_analysis` | 函数 | 单层蒙特卡洛：10,000 次采样估计输出方差 | `Var(z)` 公式 |
| `run_experiment` | 函数 | 6 种"初始化 + 激活"组合跑 `forward_deep`，打印 L1/L5/L10/L25/L50 | 深度实验 |
| `training_comparison` | 函数 | 在圆形数据集上用 6 种组合训练 2→8→1 网络 300 个 epoch | 初始化对训练的影响 |
| `if __name__ == "__main__":` | 演示入口 | 依次运行 STEP 1–5 | — |

调用关系：`run_experiment → forward_deep → *_init + 激活函数`，结果字典再交给 `magnitude_report` 逐个打印；`training_comparison` 内部自带数据生成、初始化和手写反向传播，与其他函数独立。

---

## 3. 逐段精讲

### 3.1 四种初始化函数

```python
def zero_init(fan_in, fan_out):
    return [[0.0 for _ in range(fan_in)] for _ in range(fan_out)]


def random_init(fan_in, fan_out, scale=1.0):
    return [[random.gauss(0, scale) for _ in range(fan_in)] for _ in range(fan_out)]


def xavier_init(fan_in, fan_out):
    std = math.sqrt(2.0 / (fan_in + fan_out))
    return [[random.gauss(0, std) for _ in range(fan_in)] for _ in range(fan_out)]


def kaiming_init(fan_in, fan_out):
    std = math.sqrt(2.0 / fan_in)
    return [[random.gauss(0, std) for _ in range(fan_in)] for _ in range(fan_out)]
```

- **形状约定**：外层 `fan_out` 行、内层 `fan_in` 列，即 `weights[输出神经元][输入]`，和 PyTorch `nn.Linear.weight` 的 `(out_features, in_features)` 一致。这样第 i 个神经元的输出就是 `Σⱼ weights[i][j] · x[j]`。
- **方差 → 标准差**：讲义公式给的是方差（`2/(fan_in+fan_out)`、`2/fan_in`），而 `random.gauss(mu, sigma)` 的第二个参数是**标准差**，所以代码先 `math.sqrt`。这是手写初始化最容易错的一步。
- `random_init` 的 `scale` 同样是标准差：`scale=0.01` 意味着 `Var(w) = 1e-4`。
- 四个函数都是正态分布版本；讲义中提到的 Xavier 均匀分布版本（`limit = √(6/(fan_in+fan_out))`）在代码里没有实现。
- ⚠️ 简化：这里的 Xavier 没有增益（gain）参数。对 tanh，PyTorch 推荐的增益是 5/3，缺了它信号会逐层衰减（见第 6 节）。

### 3.2 激活函数

```python
def sigmoid(x):
    x = max(-500, min(500, x))
    return 1.0 / (1.0 + math.exp(-x))


def tanh_act(x):
    return math.tanh(x)


def relu(x):
    return max(0.0, x)
```

- sigmoid 照例先把输入夹到 [-500, 500] 防止 `math.exp` 溢出。STEP 3 中 N(0,1) + ReLU 的激活会长到 10³⁶ 量级，但那一组用的是 ReLU，不经过 sigmoid。
- `tanh_act` 只是 `math.tanh` 的包装，命名加 `_act` 后缀是为了和配置表里的其他激活函数风格统一。
- 三者的关键差别：sigmoid 输出在 (0, 1)、均值约 0.5、零点斜率 1/4；tanh 输出在 (-1, 1)、关于 0 对称、零点斜率 1；ReLU 把负半轴置 0。这些差别决定了该用哪种初始化。

### 3.3 `forward_deep`：50 层前向实验

```python
def forward_deep(init_fn, activation_fn, n_layers=50, width=64, n_samples=100):
    random.seed(42)
    layer_magnitudes = []

    inputs = [[random.gauss(0, 1) for _ in range(width)] for _ in range(n_samples)]

    for layer_idx in range(n_layers):
        weights = init_fn(width, width)
        biases = [0.0] * width

        new_inputs = []
        for sample in inputs:
            output = []
            for neuron_idx in range(width):
                z = sum(weights[neuron_idx][j] * sample[j] for j in range(width)) + biases[neuron_idx]
                output.append(activation_fn(z))
            new_inputs.append(output)
        inputs = new_inputs

        magnitudes = []
        for sample in inputs:
            magnitudes.append(sum(abs(v) for v in sample) / width)
        mean_mag = sum(magnitudes) / len(magnitudes)
        layer_magnitudes.append(mean_mag)

    return layer_magnitudes
```

- **`random.seed(42)` 放在函数开头**：每个配置都用相同的输入数据和相同的随机数序列，对比更公平。
- **输入**：100 个样本，每个 64 维，服从 N(0, 1)，方差为 1，正好是"理想的起点"。
- **每层都新建权重**：`init_fn(width, width)`，所有层都是 64 → 64 的方阵，所以 `fan_in = fan_out = 64`，Xavier 的方差 `2/128 = 1/64`，Kaiming 的方差 `2/64`。
- **偏置全 0**：偏置不影响对称性破缺（权重已经随机），也不引入额外方差。
- **指标**：每个样本取 64 个激活的平均绝对值，再对 100 个样本取平均。对 ReLU，`E|ReLU(z)| = σ/√(2π)`，第 1 层 Kaiming 的 `σ = √2`，理论值约 0.564，实测 0.5534。
- 计算量：50 层 × 100 样本 × 64 × 64 ≈ 2000 万次乘加，6 个配置约 1.2 亿次，纯 Python 要跑几秒。
- ⚠️ 指标的局限：平均绝对值对 sigmoid 不敏感——sigmoid 输出总在 0.5 附近，即使信号已经完全消失，这个指标也是 0.5（第 6 节会看到 Zero + Sigmoid 和 Xavier + Sigmoid 数字几乎一样）。更好的指标是"同一神经元在不同样本上的标准差"。

### 3.4 `magnitude_report`：文本条形图

```python
def magnitude_report(name, magnitudes):
    print(f"\n{name}:")
    for i, mag in enumerate(magnitudes):
        if i % 5 == 0 or i == len(magnitudes) - 1:
            if mag > 1e6:
                bar = "X" * 50 + " EXPLODED"
            elif mag < 1e-6:
                bar = "." + " VANISHED"
            else:
                bar_len = min(50, max(1, int(mag * 10)))
                bar = "#" * bar_len
            print(f"  Layer {i+1:3d}: {bar} ({mag:.6f})")
```

- 每 5 层打印一次（第 1、6、11……46 层），再加最后一层（第 50 层）。`i+1` 把 0 起的下标转成 1 起的层号。
- 阈值：大于 1e6 记为 EXPLODED，小于 1e-6 记为 VANISHED，否则画 `int(mag × 10)` 个 `#`，并夹在 [1, 50]。
- `max(1, ...)` 保证正常值至少画一个 `#`，`min(50, ...)` 防止条形太长。
- 括号里用 `:.6f` 打印原始数值，所以爆炸的数字会打印出几十位整数（第 6 节可见）。

### 3.5 `symmetry_demo`：对称性问题

```python
def symmetry_demo():
    weights = zero_init(2, 4)
    biases = [0.0] * 4

    inputs = [0.5, -0.3]
    outputs = []
    for neuron_idx in range(4):
        z = sum(weights[neuron_idx][j] * inputs[j] for j in range(2)) + biases[neuron_idx]
        outputs.append(sigmoid(z))
    # ...
    all_same = all(abs(outputs[i] - outputs[0]) < 1e-10 for i in range(len(outputs)))
    print(f"  All identical: {all_same}")
    print(f"  Effective parameters: 1 (not {len(weights) * len(weights[0])})")
```

- 4 个神经元、每个 2 个输入，全零权重 ⇒ `z = 0` ⇒ 输出都是 `sigmoid(0) = 0.5`。
- `all(...)` 配合生成器表达式检查"所有输出都等于第一个"，用容差 `1e-10` 而不是 `==`，是比较浮点数的好习惯。
- `len(weights) * len(weights[0])` = 4 × 2 = 8 个权重参数；"有效参数 1"是讲义中"512 个神经元等于 1 个"的缩小版说法。
- ⚠️ 这个演示只展示了**前向**的对称；对称性真正致命之处在于**反向**梯度也相同、更新也相同，所以永远打不破。代码没有演示训练过程，可以自己补（见第 7 节练习 1）。

### 3.6 `variance_analysis`：单层方差的蒙特卡洛验证

```python
    configs = [
        ("Random N(0,1)", 1.0),
        ("Random N(0,0.01)", 0.01),
        ("Xavier std", math.sqrt(2.0 / (fan_in + fan_in))),
        ("Kaiming std", math.sqrt(2.0 / fan_in)),
    ]
    # ...
    for name, std in configs:
        random.seed(42)
        output_vars = []
        for _ in range(n_trials):
            inputs = [random.gauss(0, 1) for _ in range(fan_in)]
            weights = [random.gauss(0, std) for _ in range(fan_in)]
            z = sum(w * x for w, x in zip(weights, inputs))
            output_vars.append(z * z)

        mean_output_var = sum(output_vars) / len(output_vars)
        weight_var = std * std
        ratio = mean_output_var
```

- 每次试验都重新采样输入和权重，计算一个神经元的 `z`，重复 10,000 次。因为 z 的均值为 0，`E[z²]` 就是方差，所以直接对 `z * z` 求平均。
- Xavier 这里写成 `2/(fan_in + fan_in)`：假设 `fan_out = fan_in = 64`。
- 理论值：`64 × Var(w)`，即 64、0.0064、1、2。
- ⚠️ `ratio = mean_output_var`：Ratio 列本应是"输出方差 / 输入方差"，但没有做除法。因为输入方差恰好是 1，数值上没错，只是这一列和 Output Var 重复了。
- ⚠️ 只测了线性部分 `z`，没有经过激活函数。所以 Kaiming 显示的 2 是"ReLU 之前"的方差，经过 ReLU 后 `E[ReLU(z)²] = 1`。

### 3.7 `run_experiment`：6 种组合

```python
    configs = [
        ("Zero + Sigmoid", lambda fi, fo: zero_init(fi, fo), sigmoid),
        ("Random N(0,1) + ReLU", lambda fi, fo: random_init(fi, fo, 1.0), relu),
        ("Random N(0,0.01) + ReLU", lambda fi, fo: random_init(fi, fo, 0.01), relu),
        ("Xavier + Sigmoid", xavier_init, sigmoid),
        ("Xavier + Tanh", xavier_init, tanh_act),
        ("Kaiming + ReLU", kaiming_init, relu),
    ]
```

- **函数作为参数**：`forward_deep` 只要求 `init_fn(fan_in, fan_out)` 这样的接口。`random_init` 多一个 `scale` 参数，就用 `lambda fi, fo: random_init(fi, fo, 1.0)` 把它"适配"成两参数函数——这是 lambda 最典型的用法。`zero_init` 外面那层 lambda 其实可以省略，直接传 `zero_init` 也一样。
- 打印索引 `[0, 4, 9, 24, 49]` 对应第 1、5、10、25、50 层。
- 返回 `all_results` 字典，供 STEP 4 的 `magnitude_report` 复用，避免重复跑一遍耗时的前向。

### 3.8 `training_comparison`：浅网络上的训练对比

```python
    def train_with_init(init_name, init_scale, activation_fn, activation_deriv):
        random.seed(0)
        hidden_size = 8
        lr = 0.1

        if init_name == "xavier":
            std_w1 = math.sqrt(2.0 / (2 + hidden_size))
            std_w2 = math.sqrt(2.0 / (hidden_size + 1))
        elif init_name == "kaiming":
            std_w1 = math.sqrt(2.0 / 2)
            std_w2 = math.sqrt(2.0 / hidden_size)
        else:
            std_w1 = init_scale
            std_w2 = init_scale
```

- **嵌套函数**：`train_with_init`、`sigmoid_d`、`relu_d` 定义在 `training_comparison` 内部，只在这里使用，并且能直接访问外层的 `data` 变量（闭包）。
- 每层按自己的 fan 计算标准差：第一层 `fan_in=2, fan_out=8`，第二层 `fan_in=8, fan_out=1`。Xavier 的 `std_w1 = √(2/10) ≈ 0.447`、`std_w2 = √(2/9) ≈ 0.471`；Kaiming 的 `std_w1 = √(2/2) = 1.0`、`std_w2 = √(2/8) = 0.5`。
- ⚠️ **Kaiming 的 `std_w1` 恰好等于 1.0，和 `Random(1.0)` 的第一层完全一样**，两者只在 w2 上不同。所以这组对比很难体现 Kaiming 的优势。

```python
                error = out - target
                d_out = error * out * (1 - out)

                for i in range(hidden_size):
                    d_h = d_out * w2[i] * activation_deriv(z1[i])
                    w2[i] -= lr * d_out * h[i]
                    for j in range(2):
                        w1[i][j] -= lr * d_h * x[j]
                    b1[i] -= lr * d_h
                b2 -= lr * d_out

                total_loss += (out - target) ** 2
```

- 这里的损失是 **MSE** `(out - target)²`（前两节用的是二元交叉熵）。梯度 `error · out · (1 - out)` 是 MSE 对 z2 的导数（省略了常数 2，相当于并入学习率）。
- MSE + sigmoid 输出的梯度里有 `out·(1-out)` 因子，当输出饱和时梯度会很小；这也是为什么分类任务通常用交叉熵。
- `d_h` 在更新 `w2[i]` **之前**计算，用的是旧的 `w2[i]`，顺序正确。
- `activation_deriv` 作为参数传入，sigmoid 用 `s·(1-s)`，ReLU 用 0/1 阶跃，与激活函数一一对应。
- `improvement = (1 - end / start) * 100`：loss 相对第 0 个 epoch 下降的百分比。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 权重形状 `[fan_out][fan_in]` | 与 PyTorch `nn.Linear.weight` 一致，行就是一个神经元 | 无 |
| 只实现正态分布版本 | 代码最短，方差一目了然 | 生产中常用均匀分布版本（`xavier_uniform_`、`kaiming_uniform_`） |
| Xavier 不带 gain | 对应讲义公式 | tanh 网络会逐层衰减；`nn.init` 通过 `gain` / `nonlinearity` 参数修正 |
| 每层都是 64×64 方阵 | `fan_in = fan_out`，Xavier 与 LeCun 的区别消失，便于对比 | 看不出 Xavier 在 `fan_in ≠ fan_out` 时的折中效果 |
| 指标用平均绝对激活值 | 简单直观，对 ReLU 有效 | 被 sigmoid 的 0.5 偏移主导，应改用跨样本标准差，或同时报告均值和标准差 |
| 每个实验开头 `random.seed` | 可复现、配置间公平 | 只有一个种子；有限宽度下的随机波动无法评估 |
| 浅网络做训练对比 | 训练快，纯 Python 可承受 | 初始化的指数效应需要深度才显现，结论偏弱 |
| 纯 Python 三重循环 | 每个乘加都可见 | 很慢；NumPy 一行 `x @ W.T` 就能完成一层 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 嵌套列表推导式 | `[[random.gauss(0, std) for _ in range(fan_in)] for _ in range(fan_out)]` | 生成二维列表；外层是行（fan_out），内层是列（fan_in） |
| `_` 占位变量 | `for _ in range(fan_in)` | 循环变量用不到时的约定写法 |
| 默认参数 | `def random_init(fan_in, fan_out, scale=1.0)`、`n_layers=50, width=64` | 不传则用默认值 |
| 函数作为参数 | `forward_deep(init_fn, activation_fn)`、`activation_fn(z)` | Python 中函数是一等对象，可以传递和调用 |
| `lambda` 适配器 | `lambda fi, fo: random_init(fi, fo, 1.0)` | 把三参数函数包装成两参数函数，满足统一接口 |
| 嵌套函数 / 闭包 | `training_comparison` 内的 `train_with_init`、`sigmoid_d` | 内部函数只在外层可见，并能读取外层变量 `data` |
| `if / elif / else` | `if init_name == "xavier": ... elif ... else` | 根据字符串选择分支 |
| 生成器表达式 + `sum` | `sum(weights[neuron_idx][j] * sample[j] for j in range(width))` | 不建中间列表直接求和 |
| `zip` | `sum(w * x for w, x in zip(weights, inputs))` | 两个列表逐元素配对 |
| `all` + 生成器 | `all(abs(outputs[i] - outputs[0]) < 1e-10 for i in range(len(outputs)))` | 所有元素都满足条件才为 True |
| `enumerate` | `for i, mag in enumerate(magnitudes)` | 同时拿到下标和值 |
| 字典 | `all_results[name] = mags`、`all_results.items()` | 按名字保存每个配置的结果 |
| 元组解包 | `for name, init_fn, act_fn in configs:`、`for name, init_name, scale, act_fn, act_d_fn in configs:` | 一次取出多个字段 |
| 字符串乘法与拼接 | `"X" * 50 + " EXPLODED"`、`row += f" {val:>10.4f}"` | 画条形图、逐段拼接表格行 |
| f-string 格式符 | `f"{name:<30}"`、`f"{val:>10.4f}"`、`f"{'EXPLODED':>10}"`、`f"{i+1:3d}"` | `<` 左对齐、`>` 右对齐、`.4f` 四位小数、`3d` 三位整数 |
| 条件表达式 | `(1 - end / start) * 100 if start > 0 else 0` | 防止除以 0 |
| 科学计数法字面量 | `1e6`、`1e-6`、`1e-10` | 浮点数阈值 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行实验 |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py`，约 11 秒完成。

**STEP 1：对称性**

```text
Symmetry Demo (4 neurons, zero init):
  Neuron 0: output = 0.500000
  Neuron 1: output = 0.500000
  Neuron 2: output = 0.500000
  Neuron 3: output = 0.500000
  All identical: True
  Effective parameters: 1 (not 8)
```

全零权重 ⇒ `z = 0` ⇒ 全是 `sigmoid(0) = 0.5`。不管输入是什么，4 个神经元都给出同样的输出。

**STEP 2：单层方差**

```text
  Strategy                    Weight Var   Output Var      Ratio
  Random N(0,1)                 1.000000      63.1933    63.1933
  Random N(0,0.01)              0.000100       0.0063     0.0063
  Xavier std                    0.015625       0.9874     0.9874
  Kaiming std                   0.031250       1.9748     1.9748
```

与理论值 `64 × Var(w)`（64、0.0064、1、2）相差约 1%，误差来自 10,000 次采样。N(0,1) 一层就把方差放大 64 倍；N(0, 0.01) 一层就缩小到 0.6%。Kaiming 的 2 是 ReLU 之前的方差，过 ReLU 后二阶矩回到 1。

**STEP 3：50 层前向**

```text
Strategy                               L1         L5        L10        L25        L50
Zero + Sigmoid                     0.5000     0.5000     0.5000     0.5000     0.5000
Random N(0,1) + ReLU               3.1305  3614.0573   EXPLODED   EXPLODED   EXPLODED
Random N(0,0.01) + ReLU            0.0313   VANISHED   VANISHED   VANISHED   VANISHED
Xavier + Sigmoid                   0.4994     0.5036     0.5029     0.5037     0.4982
Xavier + Tanh                      0.5465     0.2692     0.1967     0.1494     0.0576
Kaiming + ReLU                     0.5534     0.6239     0.4946     0.3603     0.0971
```

逐行解读：

- **Zero + Sigmoid**：每层都是 0.5——每个神经元恒等于 `sigmoid(0)`，与输入完全无关，网络是"死"的。
- **Random N(0,1) + ReLU**：每层方差系数 `64 × 1 / 2 = 32`，幅度每层约乘 `√32 ≈ 5.7`。第 5 层 3614，第 10 层超过 1e6，第 50 层到了约 4 × 10³⁶（STEP 4 打印的完整数字）。
- **Random N(0,0.01) + ReLU**：每层方差系数 `64 × 1e-4 / 2 = 0.0032`，幅度每层约乘 0.057，第 5 层已小于 1e-6。
- **Xavier + Sigmoid**：数字和零初始化几乎一样，都在 0.5 左右。⚠️ **这并不说明信号被保住了**：sigmoid 输出的 0.5 偏移主导了平均绝对值。额外测量"同一神经元在 100 个样本上的标准差"，第 1 层约 0.20，第 10 层已小于 1e-6——sigmoid 的斜率只有 1/4，区分不同输入的信号每层缩小约 4 倍。讲义中"Xavier + Sigmoid 在第 50 层约为 1.0"与实际运行结果不符。
- **Xavier + Tanh**：从 0.55 缓慢衰减到 0.058。tanh 会压缩大的输入，每层方差系数略小于 1，50 层累积下来降了约一个数量级。把 Xavier 的标准差乘上增益 5/3（PyTorch 对 tanh 的推荐值）后，实测 L1/L5/L10/L25/L50 为 0.689/0.591/0.589/0.606/0.570，基本稳定。
- **Kaiming + ReLU**：前 20 层基本在 0.4–0.7 之间，之后缓慢下降到 0.097。比随机初始化的"几层内爆炸/消失"好得多，但也没有讲义图里说的"第 50 层约 1.0"那么理想。原因是宽度只有 64，每层的放大系数是随机的，期望为 1 不代表每次都是 1，50 层的随机波动会累积；不同随机种子下第 50 层的数值也会不同。

**STEP 4：逐层条形图**

条形图把 STEP 3 的趋势画了出来。值得注意的两点：

```text
Random N(0,1) + ReLU:
  Layer   1: ############################### (3.130516)
  Layer   6: ################################################## (20814.932019)
  Layer  11: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX EXPLODED (94167845.299118)
  ...
  Layer  50: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX EXPLODED (4130928612281126478106021772486770688.000000)
```

- 第 6 层约 2 万，第 11 层约 9400 万，5 层放大约 4500 倍，与 `5.7⁵ ≈ 6000` 的估算同一量级，典型的指数增长。Python float 最大约 1.8e308，所以这里还没溢出成 inf，但已经没有任何意义。

```text
Kaiming + ReLU:
  Layer   1: ##### (0.553402)
  Layer  16: ###### (0.696333)
  Layer  26: ## (0.247098)
  Layer  46: # (0.073889)
  Layer  50: # (0.097118)
```

- Kaiming 的条形长度上下波动，而不是单调变化，说明它在"期望意义上"保持了方差，偏离来自随机性。

**STEP 5：训练对比**

```text
  Config                           Start Loss     End Loss  Improvement
  Random(0.01) + Sigmoid             0.213427     0.205097         3.9%
  Random(1.0) + Sigmoid              0.257682     0.018135        93.0%
  Xavier + Sigmoid                   0.220716     0.022327        89.9%
  Random(0.01) + ReLU                0.222634     0.007044        96.8%
  Random(1.0) + ReLU                 0.395736     0.004482        98.9%
  Kaiming + ReLU                     0.261864     0.004715        98.2%
```

- **Random(0.01) + Sigmoid 几乎学不动**：所有隐藏单元都约等于 0.5，`w2 ≈ 0.01` 加上 `σ' ≤ 0.25`，回传到隐藏层的梯度非常小，300 个 epoch 只降 3.9%。这是"太小 + sigmoid"的典型失败。
- **Random(1.0) + ReLU 的最终 loss 最低**，甚至略优于 Kaiming。这并不推翻本节结论：①第一层 `fan_in = 2`，Kaiming 的 `std_w1 = √(2/2) = 1.0` 与 Random(1.0) 完全相同；②网络只有一个隐藏层，方差的指数效应需要深度才显现。
- **ReLU 系的最终 loss 普遍低于 sigmoid 系**：ReLU 正区间导数为 1，梯度传得更顺畅。
- 这个对比说明的是：**浅网络对初始化相当宽容，深网络才是初始化真正决定成败的地方**（对照 STEP 3）。

---

## 7. 动手改一改

1. **演示对称性在训练中保持**：在 `training_comparison` 中加一个 `"zero"` 选项（`std_w1 = std_w2 = 0`），训练 50 个 epoch 后打印 `w1` 的 8 行，确认它们完全相同。
2. **换一个指标**：在 `forward_deep` 中额外计算"每个神经元跨样本的标准差"的平均值，重新跑 STEP 3，对比 Zero + Sigmoid 与 Xavier + Sigmoid。
3. **加入增益**：写 `xavier_init_gain(fan_in, fan_out, gain)`，用 `gain = 5/3` 配 tanh，确认第 50 层幅度保持在 0.5–0.7。
4. **加入 LeCun 初始化**（讲义练习 1）：`Var(w) = 1/fan_in`。在本代码的方阵设置下它和 Xavier 有什么关系？（提示：`fan_in = fan_out` 时 `2/(fan_in+fan_out) = 1/fan_in`。）
5. **残差缩放**（讲义练习 2）：把每层改成 `x = x + scale · Kaiming层(x)`，分别取 `scale = 1` 和 `1/√(2·50)`，打印残差流幅度随层数的变化。
6. **宽度的影响**：把 `width` 改成 16 和 256（相应减少 `n_samples` 以控制运行时间），观察 Kaiming + ReLU 在第 50 层的偏离是否随宽度增大而减小。

---

## 8. 常见坑

- **把方差当标准差**：公式 `2/fan_in` 是方差，传给 `random.gauss` / `torch.normal` 要开平方。错了就是系统性地偏大或偏小。
- **用错 fan**：卷积层的 `fan_in = 输入通道数 × 卷积核高 × 卷积核宽`，不是输入通道数；线性层权重形状 `(out, in)` 中 `in` 才是 fan_in。
- **只看平均绝对值**：sigmoid 的 0.5 偏移会掩盖信号消失（本代码 STEP 3 的 Xavier + Sigmoid）。至少同时看均值和标准差。
- **以为 PyTorch 默认就是 He 初始化**：`nn.Linear` 默认是 `kaiming_uniform_(a=√5)`，方差只有 `1/(3·fan_in)`；深网络里应显式初始化。
- **在浅网络上得出"初始化无所谓"的结论**：STEP 5 中随机初始化也能训好，但换成 50 层就完全不同。
- **tanh 不加增益**：Xavier 默认增益为 1，tanh 网络会逐层衰减，应使用 `gain = 5/3`。
