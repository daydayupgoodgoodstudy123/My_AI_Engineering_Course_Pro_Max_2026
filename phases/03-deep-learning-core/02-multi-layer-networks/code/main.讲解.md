# 代码讲解 · main.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 02 节 多层网络和 Forward Pass ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy

---

## 1. 这份代码在考察什么

上一节我们把三个感知器"手工"接成了两层。这一节把它抽象成两个可复用的类，并且只做一件事——**前向传播**：

1. **层的抽象**：一个 `Layer` = 一个权重矩阵 + 一个 bias 向量 + sigmoid；形状约定是 `(本层神经元数, 上一层神经元数)`。
2. **网络的抽象**：一个 `Network` = 一串 `Layer`，前向传播就是"上一层的输出喂给下一层"。
3. **sigmoid 也能模拟逻辑门**：把权重放大到 ±20，sigmoid 就近似阶跃函数，XOR 依然可解。
4. **结构 ≠ 能力**：随机权重的 2-8-1 网络在圆分类上一塌糊涂（17.5%），学习要靠下一节的反向传播。
5. **参数量的直觉**：从 9 个参数的 XOR 网络到 56 万参数的 MNIST 网络，参数量几乎全部集中在第一层大矩阵上。

> 一句话：**前向传播 = 反复做"矩阵乘 + 加偏置 + 激活"**；本节把这条流水线写清楚，下一节再让它学起来。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sigmoid(x)` | 函数 | 带溢出保护的 sigmoid | 激活函数 |
| `Layer` | 类 | 保存 `weights`（二维列表）和 `biases`，`forward` 计算 `σ(W·x + b)` 并缓存输入输出 | 全连接层 |
| `Network` | 类 | 按顺序串联多个 `Layer`；`count_parameters` 统计参数量 | MLP、前向传播 |
| DEMO 1 | 演示 | 手工权重的 2-2-1 网络解 XOR | 用 sigmoid 近似逻辑门 |
| DEMO 2 | 演示 | 随机权重的 2-8-1 网络做圆内/圆外分类 | 未训练网络的表现 |
| DEMO 3 | 演示 | 打印 XOR 网络每一层的中间输出 | 隐藏层表示 |
| DEMO 4 | 演示 | 统计几种经典结构的参数量 | 参数量估算 |

数据流：`inputs`（Python 列表）→ `Network.forward` → 依次调用每个 `Layer.forward` → 返回最后一层输出（一个列表，即使只有一个神经元也是 `[值]`）。

---

## 3. 逐段精讲

### 3.1 `sigmoid`：夹紧防溢出

```python
def sigmoid(x):
    x = max(-500.0, min(500.0, x))
    return 1.0 / (1.0 + math.exp(-x))
```

- 公式 `σ(z) = 1/(1+e^(−z))`，把任意实数压到 (0, 1)：大正数 → 接近 1，大负数 → 接近 0，`σ(0) = 0.5`。
- 为什么夹紧到 ±500：Python 的 `math.exp` 参数超过约 709 时会直接抛 `OverflowError: math range error`（不是返回无穷大）。当 `x` 是很大的负数时 `-x` 很大，就会触发。夹到 ±500 后 `exp(500) ≈ 1.4e217` 仍是有限浮点数。
- ⚠️ 讲义 Step 1 说 "`math.exp(1000)` is infinity"，这在 Python 里不准确：`math.exp(1000)` 会抛异常；返回 `inf`（并给出警告）的是 `numpy.exp(1000)`。
- 更标准的数值稳定写法是分段：`x ≥ 0` 时用 `1/(1+e^(−x))`，`x < 0` 时用 `e^x/(1+e^x)`，这样永远只对非正数求 `exp`，不需要人为夹紧。

### 3.2 `Layer.__init__`：权重矩阵的形状约定

```python
class Layer:
    def __init__(self, n_inputs, n_neurons, weights=None, biases=None):
        if weights is not None:
            self.weights = weights
        else:
            self.weights = [
                [random.uniform(-1, 1) for _ in range(n_inputs)]
                for _ in range(n_neurons)
            ]
        if biases is not None:
            self.biases = biases
        else:
            self.biases = [0.0] * n_neurons
```

- 嵌套列表推导：外层循环 `n_neurons` 次，内层循环 `n_inputs` 次，得到形状 `(n_neurons, n_inputs)` 的二维列表——**每一行是一个神经元对所有输入的权重**。这与 PyTorch `nn.Linear(n_inputs, n_neurons).weight` 的形状 `(out, in)` 一致。
- `weights=None` 的可选参数设计：不传就随机初始化（DEMO 2、4），传了就用手工值（DEMO 1）。判断用 `is not None` 而不是 `if weights:`，因为空列表等"假值"也可能是合法输入，`is None` 只针对"没传"。
- 随机初始化用 `uniform(-1, 1)`、bias 初始化为 0。⚠️ 这是最朴素的做法：没有根据层宽度缩放。对 784 输入的层，`z` 是 784 个随机项之和，方差很大，sigmoid 很容易饱和。Xavier / He 初始化会按 `1/n_in` 缩放方差，这是第 08 节的内容。
- ⚠️ 传入 `weights` 时 `n_inputs`、`n_neurons` 参数**完全被忽略**，也不检查形状是否一致——为了简洁牺牲了健壮性。

### 3.3 `Layer.forward`：逐神经元计算

```python
    def forward(self, inputs):
        self.last_input = inputs
        self.last_output = []
        for neuron_idx in range(len(self.weights)):
            z = sum(
                w * x for w, x in zip(self.weights[neuron_idx], inputs)
            )
            z += self.biases[neuron_idx]
            self.last_output.append(sigmoid(z))
        return self.last_output
```

- 对每个神经元：权重行与输入做点积 → 加 bias → sigmoid。所有神经元的结果组成本层输出向量。数学上就是 `a = σ(W·x + b)`，只是用循环代替了矩阵乘法。
- `self.last_input`、`self.last_output` 把这次前向的输入和激活值**存在层对象上**。本节没用到，但下一节反向传播需要：权重梯度 = 误差 × 本层输入，sigmoid 导数 = `a(1 − a)`。DEMO 3 也借它读取中间结果。
- ⚠️ `zip` 遇到长度不等的序列会**静默截断**：如果上一层输出 4 维而本层权重只有 3 列，第 4 个值会被悄悄丢掉、不报错。生产代码应检查 `len(inputs) == len(self.weights[0])`，或用 `zip(..., strict=True)`（Python 3.10+）。
- ⚠️ 激活函数写死为 sigmoid，输出层和隐藏层只能用同一种激活；PyTorch 把"线性层"和"激活"拆成独立模块（`nn.Linear` + `nn.Sigmoid`），组合更灵活。

### 3.4 `Network`：串联与参数统计

```python
class Network:
    def __init__(self, layers):
        self.layers = layers

    def forward(self, inputs):
        current = inputs
        for layer in self.layers:
            current = layer.forward(current)
        return current

    def count_parameters(self):
        total = 0
        for layer in self.layers:
            for neuron_weights in layer.weights:
                total += len(neuron_weights)
            total += len(layer.biases)
        return total
```

- `forward` 只有 4 行有效逻辑：用 `current` 变量"接力"，每层的输出覆盖 `current` 成为下一层的输入。这就是 `nn.Sequential` 的全部本质。
- `count_parameters` 逐行累加权重个数，再加 bias 个数，等价于公式 `Σ (n_in × n_out + n_out)`。它是讲义练习 3 的参考实现，代码里已经写好了。

### 3.5 DEMO 1：用大权重 sigmoid 解 XOR

```python
    hidden = Layer(
        n_inputs=2,
        n_neurons=2,
        weights=[[20.0, 20.0], [-20.0, -20.0]],
        biases=[-10.0, 30.0],
    )

    output = Layer(
        n_inputs=2,
        n_neurons=1,
        weights=[[20.0, 20.0]],
        biases=[-30.0],
    )
```

| 神经元 | 线性部分 | 近似的逻辑门 |
|--------|---------|-------------|
| 隐藏 1 | `20x1 + 20x2 − 10` | OR（至少一个 1 时 `z ≥ 10`） |
| 隐藏 2 | `−20x1 − 20x2 + 30` | NAND（两个都为 1 时 `z = −10`） |
| 输出 | `20h1 + 20h2 − 30` | AND（两个都≈1 时 `z ≈ 10`） |

- 与上一节的 `[1,1], -0.5` 等参数相比，这里把所有数放大了 20 倍左右，目的是让 `|z| ≥ 10`，sigmoid 输出 ≈ 0.99995 或 0.00005，**近似阶跃**。如果仍用 ±1 量级的权重，sigmoid 输出会在 0.4～0.6 之间徘徊，逻辑门就"糊"了。
- 用 `result[0] >= 0.5` 把概率转成类别；`all_correct` 标志位汇总四个样本的结果。

### 3.6 DEMO 2：随机权重的圆分类

```python
    random.seed(42)

    data = []
    for _ in range(200):
        x = random.uniform(-1, 1)
        y = random.uniform(-1, 1)
        label = 1 if (x * x + y * y) < 0.25 else 0
        data.append(([x, y], label))
    # ...
    random.seed(7)
    circle_net = Network([
        Layer(n_inputs=2, n_neurons=8),
        Layer(n_inputs=8, n_neurons=1),
    ])
```

- 数据：在 `[-1,1]²` 正方形里均匀采样 200 个点，落在半径 0.5 的圆内（`x² + y² < 0.25`）标 1。圆面积 / 正方形面积 = `π·0.25 / 4 ≈ 19.6%`，实际 35 个（17.5%）在圆内——类别明显不平衡。
- **两次 `random.seed`**：`seed(42)` 固定数据，`seed(7)` 固定网络初始权重。分开设种子的好处是：改数据量不会连带改变网络初始化，实验更可控。
- 圆形边界是弯曲的，单个感知器做不到；2-8-1 网络在结构上能做到，但需要训练。
- 实际结果：随机网络对 200 个点的输出全部落在约 0.64～0.70 之间，**全部预测为 1**，所以准确率恰好等于圆内比例 17.5%——比"全猜 0"的 82.5% 差得多。原因是 bias 为 0、输入和权重都很小时，隐藏层输出都在 0.5 附近，网络近似一个常数函数（详见测验 Q9）。

### 3.7 DEMO 3 与 DEMO 4：看中间层、数参数

```python
    for inputs, expected in xor_data:
        xor_net.forward(inputs)
        h = xor_net.layers[0].last_output
        o = xor_net.layers[1].last_output
```

- 调用一次 `forward` 后，从每层的 `last_output` 读出隐藏表示。可以看到 `[0,1]` 和 `[1,0]` 被映射到**同一个**隐藏表示 `[0.999955, 0.999955]`，`[0,0]` 和 `[1,1]` 分别映射到 `[0.000045, 1.0]` 和 `[1.0, 0.000045]`——在隐藏空间里，XOR 变成了线性可分的问题。

```python
    for name, sizes in architectures:
        layers = []
        for i in range(1, len(sizes)):
            layers.append(Layer(n_inputs=sizes[i - 1], n_neurons=sizes[i]))
        net = Network(layers)
        print(f"  {name}: {net.count_parameters():,} parameters")
```

- 用"层宽列表" `[784, 256, 128, 10]` 描述结构，相邻两个数构成一层的 `(n_inputs, n_neurons)`——这是描述 MLP 最常用的写法。
- ⚠️ 为了数参数，这里真的用纯 Python 生成了几十万个随机数（深 MNIST 网络约 56.7 万个），只是为了调用 `count_parameters`。直接用公式算会快得多；不过实测整个脚本不到 0.2 秒就跑完，演示可以接受。
- `{...:,}` 格式符加千位分隔符：`235146 → 235,146`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表、逐神经元循环 | 每个乘加都看得见，对应公式 `σ(W·x+b)` | 极慢、不能批处理；生产中用 `X @ W.T + b` 一次算完整个 batch |
| 权重形状 `(n_neurons, n_inputs)` | 与数学 `W·x` 和 PyTorch `nn.Linear.weight` 一致 | 有的框架（如 Keras）用 `(in, out)`，读代码要先确认约定 |
| 激活函数写死在 `Layer` 里 | 代码最短 | 不能每层选不同激活；框架把线性层与激活拆开 |
| `forward` 缓存 `last_input`/`last_output` | 为反向传播和调试做准备 | 每层多占内存；框架用计算图自动保存所需张量 |
| `uniform(-1, 1)` 初始化、bias 为 0 | 简单 | 不随层宽缩放，宽层易饱和；用 Xavier / He 初始化 |
| 不做形状检查 | 保持代码简洁 | `zip` 静默截断导致"不报错的错误"；应加断言 |
| 演示放在 `if __name__ == "__main__":` 下 | `import main` 时不会执行演示，类可被下一节复用 | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import` 模块 | `import math`、`import random` | 标准库，无需安装 |
| 关键字参数 | `Layer(n_inputs=2, n_neurons=2, weights=..., biases=...)` | 按名字传参，可读性高、顺序无关 |
| 可选参数 `=None` | `weights=None, biases=None` | 用 `None` 表示"没传"，再在函数内判断 |
| `is not None` | `if weights is not None:` | 判断"是否传了值"；不要写成 `if weights:` |
| 列表乘法 | `[0.0] * n_neurons` | 生成 n 个 0.0 |
| 嵌套列表推导 | `[[random.uniform(-1, 1) for _ in range(n_inputs)] for _ in range(n_neurons)]` | 生成二维列表；`_` 表示不用的循环变量 |
| 生成器表达式 + `zip` | `sum(w * x for w, x in zip(self.weights[neuron_idx], inputs))` | 逐元素配对相乘再求和（点积） |
| 实例属性动态添加 | `self.last_input = inputs`（在 `forward` 里才创建） | Python 允许在任意方法里给 `self` 新增属性；但未调用 `forward` 前访问会报 `AttributeError` |
| 生成器 + `sum` 计数 | `sum(1 for _, label in data if label == 1)` | 带条件的计数写法 |
| 条件表达式 | `1 if result[0] >= 0.5 else 0` | 一行 if-else |
| 字符串乘法 | `"=" * 60` | 打印分隔线 |
| f-string 格式符 | `f"{result[0]:.6f}"`、`f"{100 * correct / len(data):.1f}%"`、`f"{net.count_parameters():,}"` | `.6f` 六位小数；`.1f` 一位小数；`,` 千位分隔符 |
| f-string 内嵌表达式 | `f"{'1' if o[0] >= 0.5 else '0'}"` | 花括号里可以写任意表达式（注意内外引号不同） |
| 元组列表 | `architectures = [("2-3-1 (this lesson)", [2, 3, 1]), ...]` | 用元组把"名字"和"结构"绑在一起，循环时解包 |
| `if __name__ == "__main__":` | 文件后半部分 | 直接运行才执行演示，被 `import` 时不执行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13）的输出：

```text
============================================================
DEMO 1: XOR with hand-tuned 2-2-1 network
============================================================
  [0, 0] -> 0.000045 (rounded: 0, expected: 0) OK
  [0, 1] -> 0.999955 (rounded: 1, expected: 1) OK
  [1, 0] -> 0.999955 (rounded: 1, expected: 1) OK
  [1, 1] -> 0.000045 (rounded: 0, expected: 0) OK

XOR solved: True
Parameters: 9

============================================================
DEMO 2: Circle classification with 2-8-1 network
============================================================
  Dataset: 200 points (35 inside, 165 outside)
  Accuracy with random weights: 35/200 (17.5%)
  Parameters: 33
  (Random weights give poor accuracy -- training needed)

============================================================
DEMO 3: Forward pass internals on XOR
============================================================
  Input: [0, 0]
    Hidden: [0.000045, 1.000000]
    Output: 0.000045 -> 0 (expected: 0)
  Input: [0, 1]
    Hidden: [0.999955, 0.999955]
    Output: 0.999955 -> 1 (expected: 1)
  Input: [1, 0]
    Hidden: [0.999955, 0.999955]
    Output: 0.999955 -> 1 (expected: 1)
  Input: [1, 1]
    Hidden: [1.000000, 0.000045]
    Output: 0.000045 -> 0 (expected: 0)

============================================================
DEMO 4: Parameter count for classic architectures
============================================================
  2-3-1 (this lesson): 13 parameters
  2-8-1 (circle): 33 parameters
  784-256-128-10 (MNIST): 235,146 parameters
  784-512-256-128-10 (deep MNIST): 567,434 parameters
```

逐段解读：

- **DEMO 1**：`0.000045 = σ(−10)`、`0.999955 = σ(10)`，四个样本全对。输出"几乎是 0/1"，正是大权重让 sigmoid 近似阶跃的效果。参数 9 个 = `(2×2+2) + (2×1+1)`。
- **DEMO 2**：35/200 在圆内。随机网络把所有点都判为 1，准确率 = 17.5%，比"全猜 0"的 82.5% 还差得多。参数 33 = `(2×8+8) + (8×1+1)`。
- **DEMO 3**：隐藏层把 `[0,1]`、`[1,0]` 映射到同一点 `[0.999955, 0.999955]`；`[0,0]`、`[1,1]` 分别落在 `(0,1)`、`(1,0)` 附近。在隐藏空间里，一个 AND 就能把正类（右上角）和负类分开。
- **DEMO 4**：
  - 784-256-128-10：`200,960 + 32,896 + 1,290 = 235,146`；
  - 784-512-256-128-10：`401,920 + 131,328 + 32,896 + 1,290 = 567,434`；
  - 规律：参数集中在**第一层**（输入维度大的那层），加一层 512 宽的隐藏层让总参数翻了一倍多。这也是 CNN 用卷积（权重共享）代替全连接处理图像的动机之一。

---

## 7. 动手改一改

1. **两层隐藏层**：搭一个 2-4-2-1 网络，对 XOR 的四个输入打印每一层的 `last_output`，观察表示如何逐层变化（讲义练习 1）。
2. **隐藏层宽度对输出分布的影响**：把圆分类网络的隐藏层改成 2、32 个神经元，统计 200 个点上输出的最小值、最大值。宽度变大时输出范围有何变化？为什么？（提示：输出层 `z` 是更多随机项之和。）
3. **形状检查**：给 `Layer.forward` 加上输入长度检查，并在 `Network.__init__` 中检查相邻层的维度是否匹配。
4. **公式版参数统计**：写 `count_parameters_from_sizes(sizes)`，不创建任何 `Layer`，直接用 `Σ(sizes[i-1]·sizes[i] + sizes[i])` 计算，并与 DEMO 4 的结果核对。
5. **可插拔激活函数**：给 `Layer` 增加 `activation` 参数（默认 `sigmoid`），让输出层可以用不同的函数；试试讲义练习 5 的"leaky step"（`z < 0` 时返回 `0.01·z`，否则返回 1.0），看 XOR 是否仍然正确。
6. **批量前向**：用 NumPy 改写 `Layer.forward`，让它接收 `(B, n_inputs)` 的矩阵、一次输出 `(B, n_neurons)`，比较 200 个点上的速度。

---

## 8. 常见坑

- **权重矩阵转置搞反**：`(out, in)` 和 `(in, out)` 两种约定都存在。讲义 mermaid 图里写的 `W1 (2x3)` 是 `x·W` 约定，而表格和代码是 `W·x` 约定 `(3, 2)`，读的时候要注意区分。
- **`zip` 静默截断**：层与层维度不匹配时不会报错，输出却是错的。
- **输出是列表而不是标量**：即使只有一个输出神经元，`forward` 返回的也是 `[值]`，要用 `result[0]` 取值。
- **随机权重下的准确率看起来"有一点"**：不平衡数据上，全猜一类也能有很高（或很低）的准确率，必须和多数类基线比较。
- **以为 `math.exp` 溢出会返回 `inf`**：Python 标准库会抛 `OverflowError`，NumPy 才返回 `inf`。
- **在 `forward` 之前访问 `last_output`**：属性还不存在，会抛 `AttributeError`。
