# 代码讲解 · main.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 04 节 Activation Functions ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 1 秒跑完） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码是一个"激活函数实验室"，分五步：

1. **实现**：sigmoid、tanh、ReLU、Leaky ReLU、GELU、Swish、softmax 及（除 softmax 外的）导数，全部是"输入一个 float、输出一个 float"的纯函数。
2. **扫描导数**：在 [−5, 5] 上数一数每个激活函数的导数有多少地方接近 0（"死区"）。
3. **多层信号实验**：把一个信号连续穿过 10 个"层"，看幅度如何变化。
4. **死神经元检测**：统计随机 ReLU 层中每个神经元在 1000 个样本上的激活次数。
5. **训练对比**：同一个 2-8-1 网络、同一组初始权重，分别用 sigmoid / ReLU / GELU 作隐藏层激活，在圆形数据上训练 200 轮。

读这份代码时要带着**批判的眼光**：第 1、4、5 步很扎实；第 2、3 步的度量方式有明显局限，第 3 步的输出甚至和讲义结论"看起来相反"。弄明白为什么，比记住结论更有价值。

> 一句话：**激活函数决定了梯度能否顺利流过网络**；用数据验证结论时，要先确认你测的就是你想测的东西。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sigmoid` / `tanh_act` / `relu` / `leaky_relu` / `gelu` / `swish` 及 `*_derivative` | 函数 | 标量激活函数与导数（导数以**激活前的 x** 为输入） | 各激活函数的定义与梯度 |
| `softmax(xs)` | 函数 | 数值稳定的 softmax | 输出层概率分布 |
| `gradient_scan` | 函数 | 统计导数绝对值 < 0.01 的采样点比例 | 饱和区 / 死区 |
| `vanishing_gradient_experiment` | 函数 | 单神经元链式前向 10 层，打印激活幅度 | （试图展示）梯度消失 |
| `dead_neuron_detector` | 函数 | 随机 ReLU 层，统计每个神经元的激活次数 | 死神经元 |
| `make_circle_data` | 函数 | 生成圆内 / 圆外二分类数据 | 实验数据 |
| `ActivationNetwork` | 类 | 可插拔激活函数的 2-8-1 网络，手写前向 / 反向 / 训练 | 激活函数对训练的影响 |
| `if __name__ == "__main__":` | 入口 | 依次执行 STEP 1～5 | — |

调用关系：所有实验都只依赖顶部的激活函数；`ActivationNetwork` 接收"激活函数 + 导数"两个函数对象作为参数，这样同一个类就能比较不同激活。

---

## 3. 逐段精讲

### 3.1 sigmoid 与 tanh：饱和型激活

```python
def sigmoid(x):
    x = max(-500, min(500, x))
    return 1.0 / (1.0 + math.exp(-x))


def sigmoid_derivative(x):
    s = sigmoid(x)
    return s * (1 - s)


def tanh_act(x):
    return math.tanh(x)


def tanh_derivative(x):
    t = math.tanh(x)
    return 1 - t * t
```

- 所有 `*_derivative` 都接收**激活前的 x**（也就是 z），在内部重新算一次激活值。这样接口统一，但会重复计算；上一节的 `Value.sigmoid` 则是把前向的 `s` 存在闭包里复用。
- `sigmoid'` 最大 0.25（x=0），`tanh'` 最大 1（x=0）——讲义说的"tanh 好四倍"。两者在 |x| 大时导数都趋近 0，这就是**饱和**。
- `tanh_act` 不叫 `tanh` 是为了避免和 `math.tanh` 混淆。

### 3.2 ReLU 与 Leaky ReLU：分段线性

```python
def relu(x):
    return max(0.0, x)


def relu_derivative(x):
    return 1.0 if x > 0 else 0.0


def leaky_relu(x, alpha=0.01):
    return x if x > 0 else alpha * x


def leaky_relu_derivative(x, alpha=0.01):
    return 1.0 if x > 0 else alpha
```

- ReLU 在 x=0 处不可导，代码约定导数为 0（`x > 0` 才返回 1），与 PyTorch 一致。
- Leaky ReLU 的负区间导数是 `alpha`，默认 0.01：死神经元仍有一点梯度，能"复活"。
- 两者的计算只有一次比较，远比 `exp` 便宜——这是 ReLU 在 CNN 中流行的工程原因之一。

### 3.3 GELU 与 Swish：平滑门控

```python
def gelu(x):
    return 0.5 * x * (1 + math.tanh(math.sqrt(2 / math.pi) * (x + 0.044715 * x ** 3)))


def gelu_derivative(x):
    phi = 0.5 * (1 + math.erf(x / math.sqrt(2)))
    pdf = math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
    return phi + x * pdf


def swish(x):
    return x * sigmoid(x)


def swish_derivative(x):
    s = sigmoid(x)
    return s + x * s * (1 - s)
```

- GELU 精确定义是 `x·Φ(x)`，`Φ` 是标准正态分布的累积分布函数，可以用 `math.erf` 精确算：`Φ(x) = 0.5·(1 + erf(x/√2))`。`gelu` 用的是 BERT/GPT 时代常用的 **tanh 近似**，与精确值的最大差约 4.7e−4。
- ⚠️ **前向与反向不一致**：`gelu_derivative` 返回的是**精确 GELU** 的导数 `Φ(x) + x·φ(x)`（乘积法则：`d(x·Φ)/dx = Φ + x·Φ'`，`Φ' = φ` 是正态密度），而不是 tanh 近似版的导数。用中心差分检查，最大误差约 8.7e−4。对本节实验影响很小，但原则上前向、反向必须对应同一个函数（修正版见测验 Q9）。
- Swish 导数用乘积法则：`d(x·σ)/dx = σ + x·σ(1−σ)`，代码正确。
- GELU 与 Swish 的共同点：平滑、非单调（负半轴有一个小"凹坑"）、负输入时输出小的负值。STEP 1 的输出里 `gelu(-1.0) = -0.1588`、`swish(-1.0) = -0.2689` 就是这个凹坑。

### 3.4 softmax：减最大值防溢出

```python
def softmax(xs):
    max_x = max(xs)
    exps = [math.exp(x - max_x) for x in xs]
    total = sum(exps)
    return [e / total for e in exps]
```

- 平移不变性：`softmax(x − c) = softmax(x)`。减去最大值后所有指数参数 ≤ 0，`exp` 不会上溢；最大项为 `e⁰ = 1`，分母 ≥ 1，也不会除以 0。
- 没有提供 `softmax_derivative`：softmax 的导数是一个雅可比矩阵 `diag(p) − ppᵀ`，不是逐元素的；实践中几乎总是和交叉熵合并求导（结果为 `p − y`），下一节会讲。

### 3.5 `gradient_scan`：导数"死区"扫描

```python
def gradient_scan(name, derivative_fn, start=-5, end=5, n=100):
    step = (end - start) / n
    near_zero = 0
    healthy = 0
    for i in range(n):
        x = start + i * step
        g = derivative_fn(x)
        if abs(g) < 0.01:
            near_zero += 1
        else:
            healthy += 1
    pct_dead = near_zero / n * 100
    print(f"{name:15s}: {healthy:3d} healthy, {near_zero:3d} near-zero ({pct_dead:.0f}% dead zone)")
```

- 在 `x = -5.0, -4.9, …, 4.9` 共 100 个点上求导，`|g| < 0.01` 记为 near-zero。注意终点 5.0 不包含在内，所以 ReLU 的 51 个 near-zero 点是 `-5.0 … 0.0`（含 0，因为 `relu_derivative(0) = 0`）。
- ⚠️ 这个指标的局限：
  - 它只看"是不是接近 0"，**不看导数有多大**。sigmoid 只有 9% 死区，看起来比 tanh（41%）还"健康"，但 sigmoid 导数最大只有 0.25，多层连乘时衰减得更快。
  - 阈值是硬的：Leaky ReLU 负区间导数恰好是 0.01，而条件是 `< 0.01`，所以它"0% 死区"；α 只要改成 0.009 就会变成 51%。
  - Swish 的 1% 来自 x = −1.3 附近——那是导数**过零点**（函数的最小值处），不是饱和区；GELU 的 20% 来自 x ≤ −3.1 的整段负区间，说明 GELU 在很负的输入下梯度也几乎为 0。
- 正确的读法：这是一个"导数在哪些输入区间几乎为 0"的粗略画像，不能直接推出"哪个激活函数梯度消失更严重"。

### 3.6 `vanishing_gradient_experiment`：一个需要批判阅读的实验

```python
def vanishing_gradient_experiment(activation_fn, name, n_layers=10, n_inputs=5):
    random.seed(42)
    values = [random.gauss(0, 1) for _ in range(n_inputs)]

    print(f"\n{name} through {n_layers} layers:")
    for layer in range(n_layers):
        weights = [random.gauss(0, 1) for _ in range(n_inputs)]
        z = sum(w * v for w, v in zip(weights, values))
        activated = activation_fn(z)
        magnitude = abs(activated)
        bar = "#" * int(magnitude * 20)
        print(f"  Layer {layer+1:2d}: magnitude = {magnitude:.6f} {bar}")
        values = [activated] * n_inputs
```

- 每"层"只有**一个神经元**：5 个 N(0,1) 权重与输入做点积，激活后把同一个值复制 5 份作为下一层输入，所以从第 2 层起 `z = activated × Σwᵢ`。
- `random.seed(42)` 在函数开头，三种激活用的是**同一串随机权重**，比较是公平的。
- ⚠️ 它测的是**前向激活值的大小**，不是反向梯度。实际输出：
  - sigmoid 的幅度一直在 0.5 左右（第 6 层 0.07 是因为那一层 z 很负）——这只是 sigmoid 值域 (0,1) 的体现；
  - ReLU 从第 1 层的 0.021 迅速衰减，第 6 层起恒为 0：某一层 `z ≤ 0` 后输出为 0，之后 `z = 0 × Σw = 0`，永远是 0；
  - GELU 小输入时约等于 `x/2`，同样迅速衰减到 0。
- 所以这个实验的输出与讲义"sigmoid 梯度消失、ReLU 保持梯度"的结论**看起来相反**，但并不矛盾——它根本没测梯度，也没用与激活函数匹配的初始化。测验 Q8 给出了一个用 NumPy 做的正确实验：10 层、宽 64，sigmoid 第 1 层梯度只有第 10 层的约 1.7e−6，tanh 约 0.25，ReLU（He 初始化）约 1.9。
- `"#" * int(magnitude * 20)` 用字符串重复画一个文本柱状图，幅度 0.5 对应 10 个 `#`。

### 3.7 `dead_neuron_detector`：统计激活率

```python
def dead_neuron_detector(n_inputs=5, hidden_size=20, n_samples=1000):
    random.seed(0)
    weights = [[random.gauss(0, 1) for _ in range(n_inputs)] for _ in range(hidden_size)]
    biases = [random.gauss(0, 1) for _ in range(hidden_size)]

    fire_counts = [0] * hidden_size

    for _ in range(n_samples):
        inputs = [random.gauss(0, 1) for _ in range(n_inputs)]
        for neuron_idx in range(hidden_size):
            z = sum(w * x for w, x in zip(weights[neuron_idx], inputs)) + biases[neuron_idx]
            if relu(z) > 0:
                fire_counts[neuron_idx] += 1

    dead = sum(1 for c in fire_counts if c == 0)
    rarely_fire = sum(1 for c in fire_counts if 0 < c < n_samples * 0.05)
    healthy = hidden_size - dead - rarely_fire
    # ...
    for i, c in enumerate(fire_counts):
        status = "DEAD" if c == 0 else "WEAK" if c < n_samples * 0.05 else "OK"
        bar = "#" * (c * 40 // n_samples)
```

- 思路正是工程中检测死神经元的标准做法：喂一批数据，统计每个神经元**有多少比例的样本**输出 > 0。从未激活 = DEAD，激活率 < 5% = WEAK。
- `"DEAD" if ... else "WEAK" if ... else "OK"` 是**链式条件表达式**，从左到右判断。
- `c * 40 // n_samples` 用整除把激活次数映射成 0～40 个 `#`。
- ⚠️ 默认参数下结果是 **0 个死神经元**：权重、偏置都是 N(0,1)，`z` 的标准差约 2.2，1000 个样本里几乎一定有正值。讲义说的"10%–40% 死亡"发生在**训练过程中**（如学习率过大把 bias 推到很负），而不是随机初始化时。把 bias 整体减 5（`random.gauss(0, 1) - 5`）就能看到大量 DEAD / WEAK（见测验 Q10）。

### 3.8 `ActivationNetwork`：同一网络、不同激活

```python
class ActivationNetwork:
    def __init__(self, activation_fn, activation_deriv, hidden_size=8, lr=0.1):
        random.seed(0)
        self.act = activation_fn
        self.act_d = activation_deriv
        # ...
        self.w1 = [[random.gauss(0, 0.5) for _ in range(2)] for _ in range(hidden_size)]
        self.b1 = [0.0] * hidden_size
        self.w2 = [random.gauss(0, 0.5) for _ in range(hidden_size)]
        self.b2 = 0.0
```

- **函数作为参数**：`activation_fn`、`activation_deriv` 直接传函数对象，`self.act(z)` 调用。这是"策略模式"的最简形式，PyTorch 里对应 `nn.Sequential(nn.Linear, nn.GELU(), ...)` 的可替换模块。
- `random.seed(0)` 写在 `__init__` 里，三个网络的初始权重**完全相同**（实测 `w1`、`w2` 逐元素相等），唯一变量就是激活函数——这是一个干净的对照实验。
- 权重用 `gauss(0, 0.5)`，bias 为 0；输出层固定 sigmoid（二分类概率）。

```python
    def backward(self, target):
        error = self.out - target
        d_out = error * self.out * (1 - self.out)

        for i in range(self.hidden_size):
            d_h = d_out * self.w2[i] * self.act_d(self.z1[i])
            self.w2[i] -= self.lr * d_out * self.h[i]
            for j in range(2):
                self.w1[i][j] -= self.lr * d_h * self.x[j]
            self.b1[i] -= self.lr * d_h
        self.b2 -= self.lr * d_out
```

- 对照上一节的公式：`d_out = ∂L/∂z2`（这里 `error = out − target`，相当于损失 `½(out − y)²`，梯度方向用 `-=`）。`d_h = d_out · w2[i] · act'(z1[i])` 是隐藏单元 i 的 delta。
- **顺序很关键**：在同一次循环里，先用**旧的** `self.w2[i]` 算出 `d_h`，然后才更新 `self.w2[i]`。如果把这两行对调，`d_h` 就会用到更新后的权重，不再是真实梯度。
- 激活导数用 `self.act_d(self.z1[i])`，以**激活前**的 `z1` 为输入——这就是前向要保存 `z1` 的原因。
- ⚠️ 输出层是 sigmoid + 平方误差，`d_out` 中多了 `out(1 − out)` 这一项，输出饱和时梯度会很小；下一节会看到 sigmoid + 交叉熵能消掉这一项。

```python
    def train(self, data, epochs=200):
        losses = []
        for epoch in range(epochs):
            total_loss = 0
            correct = 0
            for x, y in data:
                pred = self.forward(x)
                self.backward(y)
                total_loss += (pred - y) ** 2
                if (pred >= 0.5) == (y >= 0.5):
                    correct += 1
```

- 在线 SGD：每个样本前向 + 反向 + 更新。loss 和准确率是"边训练边统计"的（用每个样本更新**前**的预测），不是 epoch 结束后的精确值。
- `(pred >= 0.5) == (y >= 0.5)` 比较两个布尔值，巧妙地把"预测类别 == 真实类别"写成一行。
- 返回每个 epoch 的平均 loss 列表，供最后对比。

### 3.9 入口：打印对比

```python
    for name, losses in results.items():
        improvement = (1 - losses[-1] / losses[0]) * 100 if losses[0] > 0 else 0
```

- 用"相对改善百分比"比较三种激活。`if losses[0] > 0 else 0` 防止除以 0（讲义里的版本没有这个保护）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 激活函数写成标量纯函数 | 公式一目了然，便于逐个测试 | 慢；框架对整个张量逐元素计算，并用融合算子 |
| 导数以 x（激活前）为输入 | 接口统一，任意激活都能插进 `ActivationNetwork` | 重复计算激活值；框架会缓存前向结果 |
| GELU 前向用 tanh 近似、导数用精确式 | （可能是疏忽）两种公式都常见 | 前向、反向应对应同一函数；PyTorch 用 `approximate="none"/"tanh"` 显式区分 |
| `gradient_scan` 用固定阈值 0.01 | 简单直观 | 忽略导数量级，结论容易被误读 |
| 信号实验只测前向幅度 | 代码短 | 不能说明梯度消失；应做多层宽网络的反向实验 |
| 死神经元检测用随机初始化 | 演示检测方法 | 没训练就看不到死亡；应在训练中周期性统计 |
| 每个实验函数内部 `random.seed` | 各实验可复现、互不影响；对照实验初始化相同 | 修改全局随机状态 |
| 输出层 sigmoid + MSE | 与前两节一致 | 分类应用 BCE，梯度更好 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `math` 函数 | `math.exp`、`math.tanh`、`math.erf`、`math.sqrt`、`math.pi` | 标准库数学函数；`erf` 用于计算正态分布 CDF |
| 默认参数 | `leaky_relu(x, alpha=0.01)`、`gradient_scan(..., start=-5, end=5, n=100)` | 不传就用默认值 |
| 条件表达式 | `1.0 if x > 0 else 0.0` | 一行 if-else |
| 链式条件表达式 | `"DEAD" if c == 0 else "WEAK" if c < ... else "OK"` | 多分支的一行写法，从左到右判断 |
| 函数作为参数 | `gradient_scan("Sigmoid", sigmoid_derivative)`、`ActivationNetwork(act_fn, act_d_fn)` | 函数是对象，可以传递、保存、稍后调用 |
| 列表推导 | `[math.exp(x - max_x) for x in xs]` | 一行生成新列表 |
| 生成器计数 | `sum(1 for c in fire_counts if c == 0)` | 带条件的计数 |
| 列表复制元素 | `[activated] * n_inputs`、`[0] * hidden_size` | 生成 n 个相同元素的列表 |
| 字符串重复 | `"#" * int(magnitude * 20)` | 画文本柱状图 |
| 整除 `//` | `c * 40 // n_samples` | 向下取整的除法 |
| 布尔比较 | `(pred >= 0.5) == (y >= 0.5)` | 两个布尔值是否相等 |
| `enumerate` | `for i, c in enumerate(fire_counts)` | 同时拿到下标和元素 |
| 字典 | `results = {}`、`results[name] = losses`、`results.items()` | 键值对存储；`items()` 同时遍历键和值 |
| f-string 宽度 / 对齐 | `f"{name:15s}"`、`f"{healthy:3d}"`、`f"{status:4s}"`、`f"{x:5.1f}"` | `15s` 字符串占 15 位左对齐；`3d` 整数占 3 位右对齐；`5.1f` 总宽 5、一位小数 |
| 多行 f-string 拼接 | `print(f"... " f"...")` | 相邻字符串字面量自动拼接 |
| 列表负索引 | `losses[-1]` | 取最后一个元素 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，约 1 秒）的关键输出：

```text
STEP 1: Activation Function Values
  x= -1.0  sigmoid=0.2689  tanh=-0.7616  relu=0.0000  gelu=-0.1588  swish=-0.2689
  x=  0.0  sigmoid=0.5000  tanh=0.0000  relu=0.0000  gelu=0.0000  swish=0.0000
  x=  1.0  sigmoid=0.7311  tanh=0.7616  relu=1.0000  gelu=0.8412  swish=0.7311
  x=  2.0  sigmoid=0.8808  tanh=0.9640  relu=2.0000  gelu=1.9546  swish=1.7616

  softmax([2.0, 1.0, 0.1]) = [0.6590011388859679, 0.24243297070471392, 0.09856589040931818]
  softmax([10, 10, 10])    = [0.3333333333333333, 0.3333333333333333, 0.3333333333333333]
```

- `swish(1) = 1 × σ(1) = 0.7311 = sigmoid(1)`；`swish(-1) = -σ(-1) = -0.2689`。
- `gelu(2) = 1.9546`：x 较大时 GELU ≈ x（Φ(2) ≈ 0.977）；`gelu(-1) = -0.1588`，负半轴的小凹坑。
- softmax 把 `[2, 1, 0.1]` 变成 `[0.659, 0.242, 0.099]`，保持排序；三个相等的 logit 得到均匀分布。

```text
STEP 2: Gradient Dead Zones
Sigmoid        :  91 healthy,   9 near-zero (9% dead zone)
Tanh           :  59 healthy,  41 near-zero (41% dead zone)
ReLU           :  49 healthy,  51 near-zero (51% dead zone)
Leaky ReLU     : 100 healthy,   0 near-zero (0% dead zone)
GELU           :  80 healthy,  20 near-zero (20% dead zone)
Swish          :  99 healthy,   1 near-zero (1% dead zone)
```

- 按 3.5 的分析解读：sigmoid 的 9% 在 |x| ≥ 4.6；tanh 的 41% 在 |x| ≥ 3；ReLU 的 51% 是整个非正半轴；GELU 的 20% 是 x ≤ −3.1；Swish 的 1% 是导数过零点 x ≈ −1.3；Leaky ReLU 的 0% 是阈值边界效应。

```text
STEP 3: Vanishing Gradient Experiment
Sigmoid: Layer 1 0.505242 … Layer 10 0.662811（始终在 0.5 附近）
ReLU:    Layer 1 0.020967 … Layer 5 0.000099，Layer 6 起 0.000000
GELU:    Layer 1 0.010659 … Layer 7 0.000001，Layer 8 起 0.000000
```

- 见 3.6：测的是前向幅度，sigmoid 被值域"托住"在 0.5，ReLU 一旦遇到负的 z 就整链归零。不要据此得出"ReLU 梯度消失更严重"。

```text
STEP 4: Dead Neuron Detection
  Dead (never fired):     0
  Barely alive (<5%):     0
  Healthy:                20
  Neuron  2:  500/1000 fires [OK  ] ####################
  Neuron 11:  750/1000 fires [OK  ] ##############################
```

- 随机初始化下 20 个神经元都健康，激活率从 18.7% 到 75% 不等（bias 越正，激活率越高）。

```text
STEP 5: Training Comparison (Circle Dataset)
--- Training with Sigmoid ---
    Epoch   0: loss=0.2222, accuracy=65.0%
    Epoch  50: loss=0.1693, accuracy=71.5%
    Epoch 100: loss=0.0609, accuracy=96.0%
    Epoch 199: loss=0.0319, accuracy=97.5%
--- Training with ReLU ---
    Epoch  50: loss=0.0212, accuracy=98.0%
    Epoch 199: loss=0.0102, accuracy=99.5%
--- Training with GELU ---
    Epoch  50: loss=0.0220, accuracy=98.0%
    Epoch 199: loss=0.0056, accuracy=99.5%

=== Final Loss Comparison ===
  Sigmoid   : start=0.2222 -> end=0.0319 (improvement: 85.6%)
  ReLU      : start=0.2232 -> end=0.0102 (improvement: 95.4%)
  GELU      : start=0.2225 -> end=0.0056 (improvement: 97.5%)
```

- 数据中 200 个点有 57 个在圆内（28.5%），所以"全猜圆外"的准确率是 71.5%。sigmoid 网络在第 50 轮的准确率恰好是 71.5%——它在前 50 轮基本只学会了预测多数类，之后才突破；ReLU、GELU 在第 50 轮就已达到 98%。
- 最终 loss：GELU（0.0056）< ReLU（0.0102）< sigmoid（0.0319）。在这个只有一个隐藏层的浅网络里，sigmoid 的劣势主要体现为**收敛慢**（导数小），而不是完全学不动；层数越深，差距会越大。
- 这是在**训练集**上、单一随机种子下的结果，GELU 与 ReLU 的差距不宜过度解读。

---

## 7. 动手改一改

1. **修正 GELU 导数**：写出 tanh 近似 GELU 的导数（参考测验 Q9），用中心差分验证所有 `*_derivative` 函数，打印每个的最大误差。
2. **改进扫描指标**：在 `gradient_scan` 中额外打印导数的最大值和平均值，重新比较 sigmoid 与 tanh。
3. **重做梯度消失实验**：用 NumPy 构造 10 层、宽 64 的网络，sigmoid / tanh 用 Xavier、ReLU 用 He 初始化，打印每层反向梯度范数（参考测验 Q8）；再把层数改到 50（讲义练习 2）。
4. **制造死神经元**：把 `dead_neuron_detector` 的 bias 整体减 3、5、8，观察 DEAD / WEAK 数量；再换成 Leaky ReLU 对比"激活率"的含义有何不同。
5. **PReLU**：在 `ActivationNetwork` 中给每个隐藏单元加一个可学习的负斜率 α，推导 `∂L/∂αᵢ = (d_out · w2[i]) · min(0, z1[i])`，与固定 α 的 Leaky ReLU 比较（讲义练习 1）。
6. **换数据集**：把圆形数据换成 XOR 的四个点（讲义练习 5），比较三种激活的收敛速度。

---

## 8. 常见坑

- **前向与反向公式不对应**：如本文件的 GELU，前向用近似、反向用精确；手写算子一定要做梯度检查。
- **导数函数的输入搞混**：本文件的导数吃的是激活**前**的 z；有的实现（如 `s * (1 - s)`）吃的是激活**后**的值，混用就会算错。
- **只看一个指标下结论**：死区比例、前向幅度都不能直接代表梯度流动，必须测反向梯度。
- **用 softmax 做多标签**：类别不互斥时应该每类单独 sigmoid。
- **softmax 不减最大值**：logits 大于 709 左右时 `math.exp` 直接抛 `OverflowError`。
- **以为 GELU 完全没有死区**：x 很负时 GELU 的导数同样趋于 0，只是比 ReLU 平滑。
