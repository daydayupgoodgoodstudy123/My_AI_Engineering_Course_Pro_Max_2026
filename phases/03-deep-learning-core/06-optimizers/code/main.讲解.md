# 代码讲解 · main.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 06 节 优化器（Optimizers） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 5 秒跑完） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这份代码把 `torch.optim` 里最常用的四个优化器拆成纯 Python 的十几行，让你看清"优化器"其实只是**一个带状态的 `step(params, grads)` 函数**：

1. **SGD 的本质**：`w -= lr·g`，以及学习率太大/太小在最简单的二次函数上是什么样子。
2. **动量的状态**：`velocities` 如何跨步保存，以及它会把有效步长放大 `1/(1-β)` 倍（这一点在运行结果里会暴露出来）。
3. **Adam 的两个矩与偏差修正**：`m`、`v`、`t` 三个状态怎么更新，为什么要除以 `1-βᵗ`。
4. **AdamW 的解耦权重衰减**：只多了一行 `params[i] * (1 - wd·lr)`，却和"把 L2 加进梯度"有本质区别。
5. **公平对比的难度**：同一个网络、同一份数据、同一个初始化，四种优化器的收敛速度和终点各不相同，而且结果会受超参数强烈影响。

> 一句话：**优化器 = 状态 + 更新规则**。手写一遍之后，`optimizer.step()` 对你来说就不再是黑箱。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SGD` | 类 | 无状态，`w -= lr·g` | 随机梯度下降 |
| `SGDMomentum` | 类 | 维护 `velocities`，`v = β·v + g; w -= lr·v` | 动量 |
| `Adam` | 类 | 维护 `m`、`v`、`t`，带偏差修正的自适应更新 | Adam |
| `AdamW` | 类 | Adam + 先对权重做 `(1 - wd·lr)` 收缩 | 解耦权重衰减 |
| `sigmoid` | 函数 | 带输入裁剪的 sigmoid，防止 `math.exp` 溢出 | 数值稳定 |
| `make_circle_data` | 函数 | 生成 200 个点，`x²+y²<1.5` 为正类 | 非线性二分类数据 |
| `OptimizerTestNetwork` | 类 | 2→8→1 的 ReLU + sigmoid 网络，手写前向与反向，逐样本训练 | 被优化的对象 |
| `bias_correction_demo` | 函数 | 恒定梯度 1.0 下打印前 10 步 m、v 的原始值与修正值 | 偏差修正 |
| `if __name__ == "__main__":` | 演示入口 | STEP 1–4：一维 SGD、偏差修正、四优化器对比、权重衰减效果 | — |

数据流：`train` 对每个样本执行 `forward → compute_grads → get_params（拍平成一维列表）→ optimizer.step（原地修改列表）→ set_params（写回网络）`。优化器只认识"一维浮点列表"，完全不知道网络结构——这和 PyTorch 中优化器只拿到 `model.parameters()` 是同一种解耦思想。

---

## 3. 逐段精讲

### 3.1 SGD：无状态的最简优化器

```python
class SGD:
    def __init__(self, lr=0.01):
        self.lr = lr

    def step(self, params, grads):
        for i in range(len(params)):
            params[i] -= self.lr * grads[i]
```

- **原地修改**：`params[i] -= ...` 直接改调用者传进来的列表，不返回新列表。这和 PyTorch `optimizer.step()` 原地更新 `param.data` 的语义一致，所以调用方在 `step` 之后要用 `set_params` 把列表写回网络。
- SGD 没有任何跨步状态，所以 `__init__` 里只存了 lr。下面三个优化器都多了"记忆"，这是它们与 SGD 的根本区别。

### 3.2 SGDMomentum：懒初始化的速度向量

```python
class SGDMomentum:
    def __init__(self, lr=0.01, beta=0.9):
        self.lr = lr
        self.beta = beta
        self.velocities = None

    def step(self, params, grads):
        if self.velocities is None:
            self.velocities = [0.0] * len(params)
        for i in range(len(params)):
            self.velocities[i] = self.beta * self.velocities[i] + grads[i]
            params[i] -= self.lr * self.velocities[i]
```

- **懒初始化（lazy init）**：构造时不知道参数有多少个，所以先设 `None`，第一次 `step` 时按 `len(params)` 建零向量。Adam/AdamW 用的是同一个套路。
- **公式**：`v = β·v + g`，**没有 `(1-β)` 系数**。这与 PyTorch `torch.optim.SGD(momentum=0.9)` 的写法相同。后果是梯度方向稳定时 `v → g/(1-β) = 10g`，**有效学习率变成 `lr/(1-β)`**。
- ⚠️ 讲义说 β=0.9 时动量"大致是最近 10 个梯度的平均"。更准确的说法是：记忆窗口约 10 步，但数值上是**加权和**，量级约为梯度的 10 倍。这一点直接解释了后面 STEP 3 中 SGD+Momentum 表现反而更差的现象（见第 6 节）。

### 3.3 Adam：两个矩 + 偏差修正

```python
    def step(self, params, grads):
        if self.m is None:
            self.m = [0.0] * len(params)
            self.v = [0.0] * len(params)

        self.t += 1

        for i in range(len(params)):
            self.m[i] = self.beta1 * self.m[i] + (1 - self.beta1) * grads[i]
            self.v[i] = self.beta2 * self.v[i] + (1 - self.beta2) * grads[i] ** 2

            m_hat = self.m[i] / (1 - self.beta1 ** self.t)
            v_hat = self.v[i] / (1 - self.beta2 ** self.t)

            params[i] -= self.lr * m_hat / (math.sqrt(v_hat) + self.epsilon)
```

逐行对应讲义公式：

| 代码 | 公式 | 含义 |
|------|------|------|
| `self.t += 1` | t ← t+1 | 步数计数器，**在循环外只加一次**，所有参数共享 |
| `self.m[i] = β1·m + (1-β1)·g` | 一阶矩 EMA | 平滑后的梯度方向（动量） |
| `self.v[i] = β2·v + (1-β2)·g²` | 二阶矩 EMA | 梯度平方的均值，衡量每个参数的梯度尺度 |
| `m_hat`、`v_hat` | `m/(1-β1ᵗ)`、`v/(1-β2ᵗ)` | 偏差修正，补偿零初始化 |
| `params[i] -= lr·m̂/(√v̂+ε)` | 更新 | 逐参数归一化后的步长 |

为什么这样设计：

- `self.t` 放在 `for` 外面：如果放在循环里，每处理一个参数就加一，t 会变成"参数个数 × 步数"，偏差修正直接失效。这是手写 Adam 最常见的 bug 之一。
- `m` 用 `(1-β1)` 的 EMA 写法（与动量类不同），所以稳态下 `m ≈ g`，`m̂/√v̂` 的量级约为 1，更新量约等于 lr。**Adam 的步长与梯度绝对大小无关**，这是它对超参不敏感的根源。
- ε 加在 `sqrt` 之外：`√v̂ + ε` 而不是 `√(v̂ + ε)`，与原论文和 PyTorch 一致；两种写法在 v̂ 极小时行为不同。
- ⚠️ 简化：真实框架对整个张量做向量化运算，这里用 Python `for` 循环逐个标量更新，慢几个数量级，但每一步都看得见。

### 3.4 AdamW：只多了一行

```python
            m_hat = self.m[i] / (1 - self.beta1 ** self.t)
            v_hat = self.v[i] / (1 - self.beta2 ** self.t)

            params[i] = params[i] * (1 - self.weight_decay * self.lr)
            params[i] -= self.lr * m_hat / (math.sqrt(v_hat) + self.epsilon)
```

- 关键在于：`m`、`v` 只用**原始梯度** `grads[i]` 计算，衰减项完全不进入自适应统计量。
- 衰减写成乘法 `w·(1 - λ·lr)`，展开就是 `w - lr·λ·w`，即讲义公式中的 `- lr * lambda * w`。每个参数都按**同一比例**收缩，不受 `√v̂` 影响——这就是"解耦（decoupled）"。
- 顺序：代码是**先衰减、后 Adam 更新**，衰减作用在本步更新前的旧 w 上，这和 PyTorch `AdamW` 的实现顺序一致。⚠️ 讲义 Build It 中的写法是先做 Adam 更新、再对新 w 衰减（`params[i] -= self.lr * self.weight_decay * params[i]` 放在后面），二者每步相差 `lr²` 量级，实际效果几乎一样，但读代码时别被两种顺序搞糊涂。
- ⚠️ 简化：衰减对所有参数一视同仁，包括偏置 `b1`、`b2`。生产中通常用 parameter groups 把 bias 和 LayerNorm 参数的 `weight_decay` 设为 0。

### 3.5 数据与网络：被优化的"实验台"

```python
def sigmoid(x):
    x = max(-500, min(500, x))
    return 1.0 / (1.0 + math.exp(-x))

def make_circle_data(n=200, seed=42):
    random.seed(seed)
    data = []
    for _ in range(n):
        x = random.uniform(-2, 2)
        y = random.uniform(-2, 2)
        label = 1.0 if x * x + y * y < 1.5 else 0.0
        data.append(([x, y], label))
    return data
```

- `sigmoid` 先把输入夹到 [-500, 500]：`math.exp(1000)` 会抛 `OverflowError`，夹紧后 `exp(500)` 仍可表示。这是上一节损失函数里讲过的数值稳定技巧。
- 圆形数据：半径 √1.5 ≈ 1.22 的圆内为 1，圆外为 0，线性模型无法分开，必须有隐藏层。

```python
class OptimizerTestNetwork:
    def __init__(self, optimizer, hidden_size=8):
        random.seed(0)
        # ...
        self.w1 = [[random.gauss(0, 0.5) for _ in range(2)] for _ in range(hidden_size)]
        self.b1 = [0.0] * hidden_size
        self.w2 = [random.gauss(0, 0.5) for _ in range(hidden_size)]
        self.b2 = 0.0
```

- **`random.seed(0)` 写在构造函数里**：保证四个优化器拿到**完全相同的初始权重**，对比才公平。这是做对照实验的基本素养。
- 参数总数 = 8×2（w1）+ 8（b1）+ 8（w2）+ 1（b2）= 33。

### 3.6 拍平与还原：`get_params` / `set_params`

```python
    def get_params(self):
        params = []
        for row in self.w1:
            params.extend(row)
        params.extend(self.b1)
        params.extend(self.w2)
        params.append(self.b2)
        return params
```

- 把结构化的权重**拍平成一维列表**，顺序是 `w1（逐行）→ b1 → w2 → b2`。`set_params` 必须按**完全相同的顺序**写回，`compute_grads` 产生的梯度列表也必须是这个顺序——三者任何一个顺序不一致，梯度就会被加到错误的参数上，且不会报错。
- `extend` 一次追加多个元素，`append` 追加一个元素；`b2` 是标量所以用 `append`。
- 为什么要拍平：让优化器完全不关心网络结构，只处理"一串数"。PyTorch 里优化器拿到的是参数张量的列表，思路相同。

### 3.7 手写反向传播：`compute_grads`

```python
    def compute_grads(self, target):
        eps = 1e-15
        p = max(eps, min(1 - eps, self.out))
        d_loss = -(target / p) + (1 - target) / (1 - p)
        d_sigmoid = self.out * (1 - self.out)
        d_out = d_loss * d_sigmoid

        grads = [0.0] * (self.hidden_size * 2 + self.hidden_size + self.hidden_size + 1)
        idx = 0
        for i in range(self.hidden_size):
            d_relu = 1.0 if self.z1[i] > 0 else 0.0
            d_h = d_out * self.w2[i] * d_relu
            grads[idx] = d_h * self.x[0]
            grads[idx + 1] = d_h * self.x[1]
            idx += 2
        # ... b1、w2、b2 的梯度同理
        grads[idx] = d_out
        return grads
```

- `d_loss` 是二元交叉熵对输出概率 p 的导数，`d_sigmoid` 是 sigmoid 的导数，二者相乘得到对 `z2` 的梯度 `d_out`。数学上它可以化简成 `out - target`，这里保留了链式法则的原始形态，方便对照上一节。
- `d_relu`：ReLU 的导数在 z>0 时为 1，否则为 0。**一个神经元如果对所有样本都有 `z1 ≤ 0`，它的所有梯度恒为 0，永远不会再被更新**——这就是"死 ReLU"，第 6 节会看到它如何拖垮 SGD+Momentum。
- 梯度列表的填写顺序 `w1 → b1 → w2 → b2` 与 `get_params` 一致。
- ⚠️ 依赖隐式状态：`compute_grads` 使用 `forward` 时存下的 `self.x`、`self.z1`、`self.h`、`self.out`，所以必须先 `forward` 再 `compute_grads`。真实框架用计算图自动管理这些中间量。

### 3.8 训练循环：逐样本更新（batch size = 1）

```python
    def train(self, data, epochs=300):
        losses = []
        for epoch in range(epochs):
            total_loss = 0.0
            correct = 0
            for x, y in data:
                pred = self.forward(x)
                grads = self.compute_grads(y)
                params = self.get_params()
                self.optimizer.step(params, grads)
                self.set_params(params)
                # ... 累加 loss 与 correct
```

- **每个样本更新一次**，相当于 mini-batch 大小为 1 的纯随机梯度下降，一个 epoch 有 200 次 `step`，300 个 epoch 共 60,000 步。这意味着 Adam 的 `t` 很快就过了偏差修正起作用的区间。
- 统计 loss 和准确率用的是**更新前**的预测 `pred`，所以每个 epoch 的数字是"边训练边统计"，不是 epoch 结束后在全量数据上的重新评估。
- ⚠️ 数据没有打乱，每个 epoch 都按同样的顺序遍历。真实训练每个 epoch 都会 shuffle。
- 打印间隔 `epoch % 75 == 0 or epoch == epochs - 1`，所以输出 epoch 0、75、150、225、299。

### 3.9 偏差修正演示

```python
def bias_correction_demo():
    beta1 = 0.9
    beta2 = 0.999
    gradient = 1.0
    # ...
    for t in range(1, 11):
        m = beta1 * m + (1 - beta1) * gradient
        v = beta2 * v + (1 - beta2) * gradient ** 2
        m_hat = m / (1 - beta1 ** t)
        v_hat = v / (1 - beta2 ** t)
```

- 梯度恒为 1.0，所以"真实"的一阶矩和二阶矩都应该是 1。原始 m、v 从 0 慢慢爬升，修正后立刻等于 1。
- 恒定梯度下 `m_t = 1 - β1ᵗ`，除以 `1 - β1ᵗ` 恰好得到 1，所以修正值是**精确的** 1.0000，不是近似。
- `range(1, 11)` 让 t 从 1 开始：t=0 时 `1 - β⁰ = 0`，会除以 0。

### 3.10 主程序 STEP 3 与 STEP 4

```python
    for name, history in results.items():
        final_loss, final_acc = history[-1]
        first_90 = None
        for epoch, (loss, acc) in enumerate(history):
            if acc >= 85.0:
                first_90 = epoch
                break
```

- 统计"第一次达到 85% 的 epoch"。⚠️ 变量名叫 `first_90`，阈值却是 85.0，打印文案也写的 "reached 85%"；变量名是历史遗留，读代码时以阈值为准。

```python
    opt_adam = Adam(lr=0.001)
    opt_adamw = AdamW(lr=0.001, weight_decay=0.1)
    # ...
    for step in range(100):
        grads = [random.gauss(0, 0.1) for _ in range(10)]
        opt_adam.step(weights_adam, list(grads))
        opt_adamw.step(weights_adamw, list(grads))
```

- 10 个大权重（[-5, 5] 均匀分布），喂同样的随机噪声梯度，看 AdamW 的衰减能把范数缩多少。
- `list(grads)` 给每个优化器传一份拷贝。这里的优化器不修改 grads，拷贝是防御式写法。
- ⚠️ 这里对比的是"不带任何正则的 Adam"和 AdamW，并没有演示讲义学习目标里说的"AdamW vs Adam+L2"。而且 100 步 × `lr·wd = 1e-4` 只能让权重缩小约 1%，差距很难看出来（见第 6 节）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 优化器只接收一维 `params` / `grads` 列表 | 优化器与网络结构解耦，同一个类能优化任何模型 | 需要手写拍平/还原，顺序必须一致；框架用参数张量列表 + autograd |
| 原地修改 `params` | 与 `torch.optim` 语义一致，不额外分配内存 | 调用方必须记得 `set_params` 写回 |
| 状态懒初始化（`None` → 零列表） | 构造时不必知道参数个数 | 同一个优化器实例不能换一组不同长度的参数复用 |
| 动量不带 `(1-β)` | 与 PyTorch SGD 一致 | 有效 lr 被放大 `1/(1-β)`，换优化器时必须重新调 lr |
| AdamW 先衰减后更新 | 与 PyTorch 实现顺序一致，衰减基于旧权重 | 对 bias/LayerNorm 也衰减；生产中用 parameter groups 排除 |
| `random.seed(0)` 写在网络构造函数里 | 四个优化器共享同一初始化，对比公平 | 只测了一个种子；严谨的对比要跑多个种子取均值和方差 |
| 逐样本更新、不打乱 | 代码最简单 | 梯度噪声大、顺序固定；实际用 mini-batch + 每 epoch shuffle |
| 纯 Python 标量循环 | 每个运算可见 | 极慢；框架会做向量化、融合 kernel（如 fused AdamW） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `class` 与 `__init__` | `class Adam: def __init__(self, lr=0.001, ...)` | 定义类；构造函数的默认参数就是"默认超参数" |
| 默认参数 | `def __init__(self, lr=0.01, beta=0.9)` | 不传时使用默认值，传了就覆盖：`SGDMomentum(lr=0.05, beta=0.9)` |
| 增强赋值 | `params[i] -= self.lr * grads[i]`、`self.t += 1` | `a -= b` 等价于 `a = a - b`，对列表元素就是原地修改该位置 |
| 列表乘法 | `[0.0] * len(params)` | 生成长度为 n、元素全为 0.0 的列表（元素是不可变的 float，所以安全） |
| `None` 哨兵与 `is None` | `if self.velocities is None:` | 用 `None` 表示"尚未初始化"，判断用 `is` |
| 嵌套列表推导式 | `[[random.gauss(0, 0.5) for _ in range(2)] for _ in range(hidden_size)]` | 生成 8×2 的二维列表；`_` 表示"不使用的循环变量" |
| `list.extend` / `append` | `params.extend(row)`、`params.append(self.b2)` | `extend` 逐个追加可迭代对象的元素，`append` 追加一个元素 |
| 条件表达式 | `1.0 if self.z1[i] > 0 else 0.0` | 一行写 if/else，常用于 ReLU 导数 |
| 生成器表达式 + `sum` | `sum(self.w2[i] * self.h[i] for i in range(self.hidden_size))` | 不建中间列表直接求和 |
| 元组解包 | `for x, y in data:`、`final_loss, final_acc = history[-1]`、`for name, opt in configs:` | 一次取出多个值 |
| `enumerate` + 嵌套解包 | `for epoch, (loss, acc) in enumerate(history):` | 同时拿到下标和元素，元素本身又是元组 |
| 负索引 | `history[-1]` | 取最后一个元素 |
| 字典 | `results[name] = history`；`results.items()` | 按名字存每个优化器的训练历史；`.items()` 同时遍历键和值 |
| `list(...)` 拷贝 | `list(large_weights)`、`list(grads)` | 生成新列表，避免两个优化器改同一个对象 |
| `max/min` 夹紧 | `max(-500, min(500, x))`、`max(eps, min(1 - eps, self.out))` | 经典的 clamp 写法，防止溢出和 `log(0)` |
| f-string 格式符 | `f"{t:4d}"`、`f"{m:.4f}"`、`f"{name:40s}"`、`f"{epoch:3d}"` | `d` 整数、`.4f` 四位小数、`40s` 字符串左对齐占 40 宽 |
| 字符串乘法 | `"=" * 60`、`"-" * 55` | 打印分隔线 |
| `random.seed` / `uniform` / `gauss` | `random.gauss(0, 0.5)` | 固定种子保证可复现；均匀分布与正态分布采样 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示；被 import 时只导入类和函数 |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py`（约 5 秒），关键输出如下。

**STEP 1：SGD 最小化 `(x-3)²`**

```text
    Step  0: x=8.600000, loss=31.360000
    Step  5: x=4.835008, loss=3.367254
    Step 10: x=3.601295, loss=0.361556
    Step 15: x=3.197032, loss=0.038822
    Step 19: x=3.080705, loss=0.006513
```

每步 `x - 3` 乘以 `1 - 2·lr = 0.8`，所以 `x = 3 + 7·0.8^(step+1)`：Step 0 是 `3 + 5.6 = 8.6`，Step 19 是 `3 + 7·0.8²⁰ ≈ 3.0807`。loss 每步乘以 0.64，呈几何级数下降。这是"线性收敛"的标准样子。

**STEP 2：偏差修正**

```text
  Step | m_raw  | m_corrected | v_raw    | v_corrected
     1 | 0.1000 | 1.0000      | 0.001000 | 1.000000
     2 | 0.1900 | 1.0000      | 0.001999 | 1.000000
   ...
    10 | 0.6513 | 1.0000      | 0.009955 | 1.000000
```

- 真实梯度恒为 1。m_raw 第 1 步只有 0.1（小 10 倍），第 10 步爬到 0.65；v_raw 第 10 步还不到 0.01（小 100 倍），**v 的偏差比 m 严重得多、持续得也久得多**（β2=0.999 要上千步才接近 1）。
- 修正后两列都恰好是 1：恒定梯度下修正是精确的。

**STEP 3：四个优化器在圆形数据集上**

```text
--- SGD (lr=0.05) ---
    Epoch   0: loss=0.5857, accuracy=67.0%
    Epoch 299: loss=0.0179, accuracy=99.0%
--- SGD+Momentum (lr=0.05, beta=0.9) ---
    Epoch   0: loss=0.5641, accuracy=71.0%
    Epoch  75: loss=0.2073, accuracy=93.0%
    Epoch 150: loss=0.2086, accuracy=93.0%
    Epoch 299: loss=0.2069, accuracy=93.0%
--- Adam (lr=0.001) ---
    Epoch   0: loss=0.8418, accuracy=45.5%
    Epoch 299: loss=0.0336, accuracy=99.5%
--- AdamW (lr=0.001, wd=0.01) ---
    Epoch   0: loss=0.8414, accuracy=45.5%
    Epoch 299: loss=0.0612, accuracy=99.0%

FINAL COMPARISON
  SGD (lr=0.05)                           : acc=99.0%, loss=0.0179, reached 85%: epoch 4
  SGD+Momentum (lr=0.05, beta=0.9)        : acc=93.0%, loss=0.2069, reached 85%: epoch 5
  Adam (lr=0.001)                         : acc=99.5%, loss=0.0336, reached 85%: epoch 30
  AdamW (lr=0.001, wd=0.01)               : acc=99.0%, loss=0.0612, reached 85%: epoch 32
```

逐条解读：

- **SGD 表现最好**（loss 最低）。这个小问题上，lr=0.05 的逐样本 SGD 已经足够。
- **SGD+Momentum 卡在 93%**，从 epoch 75 起 loss 几乎不动。原因是有效学习率 = `0.05/(1-0.9) = 0.5`，是 SGD 的 10 倍；早期的大步把 ReLU 神经元推死了。额外统计训练后的死神经元数：SGD 1 个，SGD+Momentum **5 个**（共 8 个），只剩 3 个神经元拟合不了圆。把动量版本的 lr 改成 0.005 后，最终 loss≈0.016、准确率 99%。**这与讲义"动量更快"并不矛盾，矛盾的是"同一个 lr 直接比较"这种实验设计**。
- **Adam / AdamW 起步慢**（epoch 0 只有 45.5%，epoch 30 左右才过 85%）：lr=0.001 时每步移动约 0.001，比 SGD 的 `0.05 × 梯度` 小很多。但它们稳定地下降，最终也到 99% 以上。
- **AdamW 的 loss 比 Adam 略高**（0.0612 vs 0.0336）：权重衰减把权重往 0 拉，输出不那么"自信"，训练 loss 稍高是正则化的正常代价。这个数据集没有单独的测试集，看不出泛化收益。
- Adam 和 AdamW 的 epoch 0 几乎相同（0.8418 vs 0.8414），因为 `1 - 1e-5` 的每步衰减在早期影响极小。

**STEP 4：权重衰减效果**

```text
  Initial weight L2 norm: 10.0550
  After 100 steps:
    Adam  weight L2 norm: 10.0433
    AdamW weight L2 norm: 9.9434
    AdamW shrinks weights 1.0x more
```

- AdamW 每步衰减因子 `1 - 0.001×0.1 = 0.9999`，100 步累积 `≈ 0.990`，只缩了 1%，所以比值 `10.0433/9.9434 ≈ 1.01`，四舍五入成 "1.0x"。方向是对的，但幅度太小，"1.0x more" 这个文案也容易让人误以为没有区别。
- 把步数改成 10000 后实测：Adam 10.1851，AdamW 3.7862，比值约 2.69，和 `0.9999¹⁰⁰⁰⁰ ≈ e⁻¹ ≈ 0.37` 的估算一致。

---

## 7. 动手改一改

1. **公平地比较动量**：把 `SGDMomentum` 的 lr 改成 0.005，重新运行，确认最终准确率回到 99%。再试 `lr=0.01、0.02`，找出它开始"变坏"的临界点。
2. **写一个 RMSProp 类**：按讲义公式 `s = β·s + (1-β)·g²; w -= lr·g/(√s + ε)`，用 β=0.9、lr=0.001 加入 `configs` 对比。
3. **写 `AdamL2`**：继承 `Adam`，在 `step` 开头 `grads = [g + l2 * p for g, p in zip(grads, params)]`。在 STEP 4 里加入它，用 10000 步对比 Adam、AdamL2、AdamW 三者的权重范数。
4. **统计死神经元**：训练结束后，对每个隐藏神经元检查是否存在某个样本使 `z1 > 0`，打印每个优化器的死神经元个数，验证第 6 节的解释。
5. **加梯度裁剪**：在 `train` 里调用 `optimizer.step` 之前，若梯度 L2 范数超过 1.0 就整体按比例缩放。观察 SGD+Momentum(lr=0.05) 的死神经元是否减少。
6. **多种子对比**：把 `random.seed(0)` 改成构造参数 `seed`，每个优化器跑 5 个种子，报告最终准确率的均值和标准差。单种子的结论有多可靠？

---

## 8. 常见坑

- **换优化器不重调 lr**：动量版 SGD 的有效步长是 `lr/(1-β)`，Adam 的步长约等于 lr，三者的 "lr=0.05" 根本不是一回事。本次运行中的 93% 就是这个坑。
- **`t` 放错位置**：Adam 的 `self.t += 1` 必须每次 `step` 只加一次，放进参数循环里会让偏差修正失效。
- **`range(1, ...)` 写成 `range(0, ...)`**：偏差修正在 t=0 时分母为 0，`ZeroDivisionError`。
- **拍平顺序不一致**：`get_params`、`set_params`、`compute_grads` 三处的参数顺序必须完全相同，错位不会报错，但梯度会更新到错误的参数上，表现为"loss 不降"或"莫名其妙发散"。
- **把 Adam 的 `weight_decay` 当成 AdamW**：PyTorch 中 `Adam(weight_decay=...)` 是 L2 式（加到梯度上），`AdamW(weight_decay=...)` 才是解耦式。
- **对偏置和归一化参数也做衰减**：本代码为简洁对所有参数衰减，真实项目中应通过 parameter groups 排除。
