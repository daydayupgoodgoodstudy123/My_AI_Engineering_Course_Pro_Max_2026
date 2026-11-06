# 代码讲解 · perceptron.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 01 节 感知器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python perceptron.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`random`、`math`，均在方法内部导入）

---

## 1. 这份代码在考察什么

这份代码用不到 170 行纯 Python，把神经网络的"史前史"完整走了一遍：

1. **感知器是什么**：加权和 + 偏置 + 阶跃函数，一个最小的线性分类器。
2. **"学习"在代码里长什么样**：错误驱动的权重更新 `w += lr * error * x`——预测错了才改，改的方向由误差符号决定。
3. **单层的极限**：AND / OR / NOT 都能学会，XOR 永远学不会（训练 1000 个 epoch 依旧 2 对 2 错）。
4. **多层的威力**：把 OR、NAND、AND 三个感知器分两层接起来，手工设定权重就能实现 XOR。
5. **从手工到自动**：把阶跃换成 sigmoid，用约 20 行手写反向传播，让一个 2-2-1 网络**自己学会** XOR——这是下一节反向传播的预告。

> 一句话：**一个感知器只能画一条直线；把它们堆起来、换成可导的激活函数，再用梯度把误差传回去，就是神经网络。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Perceptron` | 类 | `predict` 做前向判决，`train` 用感知器规则学习 | 线性分类器、感知器学习规则 |
| `test_gate(name, n_inputs, data)` | 函数 | 训练一个感知器并打印权重和逐样本结果 | 实验脚手架 |
| `and_data` / `or_data` / `not_data` / `xor_data` | 模块级列表 | 四个逻辑门的真值表 `(输入, 目标)` | 训练集 |
| 单感知器训练 XOR 的代码块 | 脚本代码 | 演示不可线性可分时永远不收敛 | XOR 问题 |
| `xor_network(x1, x2)` | 函数 | 用手工权重的 OR、NAND、AND 三个神经元组成两层网络 | 多层感知器 |
| `TwoLayerNetwork` | 类 | 2-2-1 的 sigmoid 网络，`forward` + 手写反向传播的 `train` | 前向传播、反向传播 |
| 文件末尾的训练与打印 | 脚本代码 | 训练 10000 个 epoch 并打印 XOR 的四个输出 | — |

数据流：真值表 → `Perceptron.train`（感知器规则）/ `xor_network`（手工权重）/ `TwoLayerNetwork.train`（梯度下降）→ 打印预测与期望。注意这个文件**没有** `if __name__ == "__main__":`，所有演示代码在模块顶层，`import perceptron` 时也会执行。

---

## 3. 逐段精讲

### 3.1 `Perceptron.__init__` 与 `predict`：一个神经元的前向计算

```python
class Perceptron:
    def __init__(self, n_inputs, learning_rate=0.1):
        self.weights = [0.0] * n_inputs
        self.bias = 0.0
        self.lr = learning_rate

    def predict(self, inputs):
        total = sum(w * x for w, x in zip(self.weights, inputs))
        total += self.bias
        return 1 if total >= 0 else 0
```

- `[0.0] * n_inputs` 创建 n 个 0.0 的列表——**全零初始化**。对单个感知器这完全没问题（没有"对称性"问题，因为只有一个神经元），但到了多层网络就不行了，所以后面的 `TwoLayerNetwork` 改用随机初始化。
- `predict` 就是公式 `ŷ = step(w·x + b)`：生成器表达式做点积，加上 bias，再用条件表达式实现阶跃函数。
- `total >= 0` 用的是 **≥**：`z = 0` 时输出 1。这个约定会直接影响结果——本节学到的 NOT 门 `w=[-0.1], b=0.0`，样本 `[0]` 恰好落在 `z = 0` 上，就是靠这个 `>=` 判对的。
- 决策边界是 `w·x + b = 0`：两个输入时就是平面上的一条直线 `w1·x1 + w2·x2 + b = 0`。

### 3.2 `Perceptron.train`：错误驱动的学习规则

```python
    def train(self, training_data, epochs=100):
        for epoch in range(epochs):
            errors = 0
            for inputs, target in training_data:
                prediction = self.predict(inputs)
                error = target - prediction
                if error != 0:
                    errors += 1
                    for i in range(len(self.weights)):
                        self.weights[i] += self.lr * error * inputs[i]
                    self.bias += self.lr * error
            if errors == 0:
                print(f"Converged at epoch {epoch + 1}")
                return
        print(f"Did not converge after {epochs} epochs")
```

- `error = target - prediction` 只可能是 `-1、0、+1`：
  - `+1`（该输出 1 却输出了 0）：权重往 `x` 的方向加，让 `w·x` 变大；
  - `-1`（该输出 0 却输出了 1）：权重往 `x` 的反方向减；
  - `0`：不更新。
- `inputs[i]` 为 0 的那一维权重不会变——这一维对本次判错"没有责任"。bias 相当于一个恒为 1 的输入，所以每次判错都更新。
- **在线更新（online / stochastic）**：每个样本处理完立即改权重，而不是攒一个 epoch 再改。
- **收敛判据**：一整个 epoch 没有任何判错（`errors == 0`）就提前 `return`。对线性可分数据，感知器收敛定理保证这一天一定会到来；对 XOR，它永远不会到来，只能跑满 `epochs` 后打印 "Did not converge"。
- ⚠️ 刻意的简化：没有打乱样本顺序（顺序固定，训练结果完全确定）、没有 pocket（保存最好的权重）、只在判错时更新——所以收敛时得到的是"刚好能分开"的边界，间隔可能为零。

**一个值得深究的细节：学习率的作用。** 因为权重从 0 开始，任意时刻 `w = lr·Σ(error·x)`、`b = lr·Σ error`，学习率只是把所有参数乘了同一个正数，`w·x + b` 的符号不变。所以理论上**学习率不影响预测、不影响收敛 epoch**。实测：`lr = 0.5` 或 `1.0` 时 AND 门都在第 6 个 epoch 收敛（`lr = 1.0` 时学到 `w = [2.0, 1.0]`、`b = −3.0`）；而默认 `lr = 0.1` 却在第 4 个 epoch 收敛——原因见 3.3。

### 3.3 `test_gate` 与逻辑门数据

```python
def test_gate(name, n_inputs, data):
    print(f"=== {name} ===")
    p = Perceptron(n_inputs)
    p.train(data)
    print(f"  Weights: {p.weights}, Bias: {p.bias}")
    for inputs, expected in data:
        result = p.predict(inputs)
        status = "OK" if result == expected else "WRONG"
        print(f"  {inputs} -> {result} (expected {expected}) {status}")
    print()
```

- 数据格式是 `(输入列表, 目标)` 的元组列表，`for inputs, expected in data` 直接解包。
- 把"训练 + 打印权重 + 逐样本验证"封装成一个函数，避免对 AND / OR / NOT 写三遍同样的代码。
- 运行后 AND 门打印 `Bias: -0.20000000000000004`。这个"奇怪"的尾数来自浮点运算 `-0.1 - 0.1`。正是这多出来的 `4e-17`，让 `[1,0]` 的 `z = 0.2 − 0.20000000000000004 ≈ −2.8e−17 < 0` 被判为 0，于是第 4 个 epoch 就"收敛"了。如果用精确的分数运算，`z = 0` 会被判为 1，训练要到第 6 个 epoch 才收敛（`b = −0.3`）。
- ⚠️ 这说明：感知器找到的边界可能**紧贴**某个样本（间隔 ≈ 0），对输入的微小扰动极其敏感。追求"最大间隔"的是 SVM，不是感知器。

### 3.4 单感知器训练 XOR：看它失败

```python
print("=== XOR Gate (single perceptron - will fail) ===")
p_xor = Perceptron(2)
p_xor.train(xor_data, epochs=1000)
for inputs, expected in xor_data:
    result = p_xor.predict(inputs)
    status = "OK" if result == expected else "WRONG"
    print(f"  {inputs} -> {result} (expected {expected}) {status}")
```

- 给了 1000 个 epoch（是默认值的 10 倍），依然不收敛——不是训练得不够，而是**不存在**一条能分开 XOR 的直线。
- 实际发生的事：第 2 个 epoch 结束时权重是 `w = [-0.1, 0.0]`、`b = 0.0`；之后每个 epoch 4 个样本全部判错、4 次更新恰好相互抵消，又回到同一组权重——一个周期为 1 个 epoch 的**死循环**。最终输出 `1, 1, 0, 0`，2 对 2 错。
- 讲义说"这是单感知器无法学会 XOR 的硬证明"，严格说这只是一个**演示**；真正的证明是几何上的：若 `w1·0 + w2·0 + b < 0` 且 `w1 + w2 + b < 0`，相加得 `w1 + w2 + 2b < 0`；而 `w1 + b ≥ 0` 且 `w2 + b ≥ 0` 相加得 `w1 + w2 + 2b ≥ 0`，矛盾。

### 3.5 `xor_network`：手工搭两层网络

```python
def xor_network(x1, x2):
    or_neuron = Perceptron(2)
    or_neuron.weights = [1.0, 1.0]
    or_neuron.bias = -0.5

    nand_neuron = Perceptron(2)
    nand_neuron.weights = [-1.0, -1.0]
    nand_neuron.bias = 1.5

    and_neuron = Perceptron(2)
    and_neuron.weights = [1.0, 1.0]
    and_neuron.bias = -1.5

    hidden1 = or_neuron.predict([x1, x2])
    hidden2 = nand_neuron.predict([x1, x2])
    return and_neuron.predict([hidden1, hidden2])
```

- 逻辑恒等式：`XOR = (x1 OR x2) AND NAND(x1, x2)`，即"至少一个为 1，但不能两个都为 1"。
- 三组参数怎么来的：
  - OR：`x1 + x2 − 0.5 ≥ 0` ⇔ 至少一个为 1；
  - NAND：`−x1 − x2 + 1.5 ≥ 0` ⇔ 不是两个都为 1（就是 AND 的参数整体取反）；
  - AND：`h1 + h2 − 1.5 ≥ 0` ⇔ 两个都为 1。
- 第一层（`hidden1`、`hidden2`）的输出成了第二层的**输入**。在 `(h1, h2)` 空间里，四个样本变成 `(0,1)、(1,1)、(1,1)、(1,0)`，只有正类在 `(1,1)`，一个 AND 就能分开。这就是"隐藏层创造新特征，让问题变得线性可分"。
- ⚠️ 这里**直接给属性赋值**来设定权重，绕过了 `train`。演示目的是"证明存在这样的权重"；问题是真实任务里你根本不知道权重该是多少，所以需要 3.6 的自动学习。
- ⚠️ 每次调用都重新创建 3 个 `Perceptron` 对象，效率低但无所谓——它只是演示。

### 3.6 `TwoLayerNetwork`：初始化与 sigmoid

```python
class TwoLayerNetwork:
    def __init__(self, learning_rate=0.5):
        import random
        random.seed(0)
        self.w_hidden = [[random.uniform(-1, 1), random.uniform(-1, 1)] for _ in range(2)]
        self.b_hidden = [random.uniform(-1, 1), random.uniform(-1, 1)]
        self.w_output = [random.uniform(-1, 1), random.uniform(-1, 1)]
        self.b_output = random.uniform(-1, 1)
        self.lr = learning_rate

    def sigmoid(self, x):
        import math
        x = max(-500, min(500, x))
        return 1.0 / (1.0 + math.exp(-x))
```

- 网络结构 2-2-1：`w_hidden` 是 2×2（每个隐藏神经元一行，对应 2 个输入），`w_output` 是长度 2 的列表。
- **随机初始化**在 [-1, 1] 内：多层网络如果全零初始化，两个隐藏神经元的输出和梯度永远相同，等于只有一个神经元（对称性无法打破）。
- `random.seed(0)` 固定随机种子，保证每次运行得到相同的初始权重和训练结果。⚠️ 但它设置的是**全局**随机状态，会影响程序里其他用 `random` 的代码；更好的做法是 `rng = random.Random(0)` 用独立的生成器。
- `sigmoid` 里 `max(-500, min(500, x))` 是**数值保护**：`math.exp` 的参数超过约 709 就会抛 `OverflowError`，先夹紧再算。
- 默认 `learning_rate=0.5`，但文件末尾实际用的是 `TwoLayerNetwork(learning_rate=2.0)`——对这个小问题，大学习率收敛更快。

### 3.7 `forward`：缓存中间结果

```python
    def forward(self, inputs):
        self.inputs = inputs
        self.hidden_outputs = []
        for i in range(2):
            z = sum(w * x for w, x in zip(self.w_hidden[i], inputs)) + self.b_hidden[i]
            self.hidden_outputs.append(self.sigmoid(z))
        z_out = sum(w * h for w, h in zip(self.w_output, self.hidden_outputs)) + self.b_output
        self.output = self.sigmoid(z_out)
        return self.output
```

- 每个隐藏神经元：`hᵢ = σ(w_hidden[i]·x + b_hidden[i])`；输出：`o = σ(w_output·h + b_output)`。结构上就是"把感知器的阶跃换成 sigmoid 再堆两层"。
- 把 `hidden_outputs`、`output` **存到 `self` 上**，是为了反向传播时复用——这就是 PyTorch 等框架在前向时"保存激活值"的原型（也是训练比推理更耗显存的原因）。
- ⚠️ `self.inputs` 被保存了但后面没有用到（`train` 里直接用局部变量 `inputs`），属于无害的冗余。

### 3.8 `train`：20 行手写反向传播

```python
    def train(self, training_data, epochs=10000):
        for epoch in range(epochs):
            total_error = 0
            for inputs, target in training_data:
                output = self.forward(inputs)
                error = target - output
                total_error += error ** 2

                d_output = error * output * (1 - output)

                saved_w_output = self.w_output[:]
                hidden_deltas = []
                for i in range(2):
                    h = self.hidden_outputs[i]
                    hd = d_output * saved_w_output[i] * h * (1 - h)
                    hidden_deltas.append(hd)

                for i in range(2):
                    self.w_output[i] += self.lr * d_output * self.hidden_outputs[i]
                self.b_output += self.lr * d_output

                for i in range(2):
                    for j in range(len(inputs)):
                        self.w_hidden[i][j] += self.lr * hidden_deltas[i] * inputs[j]
                    self.b_hidden[i] += self.lr * hidden_deltas[i]

            if epoch % 2000 == 0:
                print(f"  Epoch {epoch}, error: {total_error:.4f}")
```

按链式法则拆开（损失取 `L = ½(y − o)²`）：

| 代码 | 数学含义 |
|------|---------|
| `error = target - output` | `y − o`，也就是 `−∂L/∂o` |
| `output * (1 - output)` | sigmoid 导数 `σ'(z_out) = o(1−o)` |
| `d_output` | `−∂L/∂z_out`（输出层的 delta，带负号） |
| `d_output * saved_w_output[i]` | 误差沿权重 `w_output[i]` 传回隐藏单元 i：`−∂L/∂hᵢ` |
| `* h * (1 - h)` | 再乘隐藏层 sigmoid 导数，得到 `−∂L/∂z_hidden[i]` |
| `+= lr * delta * 输入` | 梯度下降：`w ← w − lr·∂L/∂w`，因为 delta 已带负号，所以写成 `+=` |

- **为什么先算 `hidden_deltas` 再更新 `w_output`？** 反向传播要求所有梯度都用**同一组（前向时的）参数**计算。`saved_w_output = self.w_output[:]` 拷贝了一份旧权重，明确表达这个意图。在当前顺序下这份拷贝其实是多余的（更新发生在计算 delta 之后），但它能防止日后有人调换顺序时引入隐蔽 bug。
- 和感知器规则的对比：形式都是 `w += lr * (某种误差) * 输入`，区别在于这里的"误差"是连续的、乘了激活函数导数、并且能传到隐藏层。
- `total_error` 是一个 epoch 内 4 个样本平方误差之和（没有乘 ½），仅用于打印；由于是在线更新，它是用"边训练边变化"的权重算出来的，并非 epoch 结束时的真实损失。
- `epoch % 2000 == 0` 每 2000 个 epoch 打印一次，`range(10000)` 的最后一次打印是 epoch 8000。
- ⚠️ 刻意的简化：只支持 2 个隐藏单元（`range(2)` 写死）、逐样本循环（没有矩阵化）、平方误差而不是分类更常用的交叉熵。下一节会把它推广成任意层数、矩阵运算的版本。

### 3.9 文件末尾：训练并读出结果

```python
net = TwoLayerNetwork(learning_rate=2.0)
net.train(xor_data, epochs=10000)
print()
for inputs, expected in xor_data:
    result = net.forward(inputs)
    predicted = 1 if result >= 0.5 else 0
    print(f"  {inputs} -> {result:.4f} (rounded: {predicted}, expected {expected})")
```

- 网络输出的是 (0, 1) 之间的连续值，用 0.5 作阈值转成类别——这和逻辑回归的做法一致。
- `{result:.4f}` 保留 4 位小数，方便看到"有多确定"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表、不用 NumPy | 每次乘加都看得见，适合第一次理解神经元 | 慢且不能批处理；生产用矩阵运算（下一节） |
| 感知器全零初始化 | 单神经元无对称性问题，且结果确定 | 多层网络必须随机初始化 |
| `step` 用 `>= 0` | 简单的约定 | 边界上的样本归为 1，零间隔解很脆弱 |
| 错误驱动、在线更新、不打乱顺序 | 与经典感知器算法一致，结果可复现 | 生产中会 shuffle、用 mini-batch |
| 手工设定 XOR 网络权重 | 先证明"多层能表示 XOR" | 真实任务不知道权重，需要学习 |
| sigmoid + 平方误差 + 手写反向传播 | 最短路径展示"梯度把误差传回隐藏层" | 分类通常用交叉熵；框架用自动求导 |
| `random.seed(0)` 写在 `__init__` 里 | 保证每次都复现成功的那次训练 | 会修改全局随机状态；更好的是独立 `Random` 实例 |
| 所有演示代码放在模块顶层 | 脚本式教学，从上往下读 | 被 `import` 时也会执行；工程中应放进 `if __name__ == "__main__":` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表乘法 | `[0.0] * n_inputs` | 生成 n 个相同元素的列表（元素是不可变的 float，安全） |
| `class` 与 `__init__` | `class Perceptron: def __init__(self, n_inputs, learning_rate=0.1)` | 定义类与构造函数；`self` 指向实例本身 |
| 默认参数 | `learning_rate=0.1`、`epochs=100` | 调用时不传就用默认值 |
| 条件表达式（三元运算） | `1 if total >= 0 else 0` | 一行写完 if-else，正好实现阶跃函数 |
| 生成器表达式 + `zip` | `sum(w * x for w, x in zip(self.weights, inputs))` | 逐元素配对相乘再求和，即点积 |
| 元组解包 | `for inputs, target in training_data` | 一次取出 `(输入, 目标)` 两个值 |
| 复合赋值 | `self.weights[i] += ...`、`errors += 1` | `a += b` 等价于 `a = a + b` |
| `return` 提前退出 | `if errors == 0: ... return` | 收敛后直接结束训练循环 |
| 嵌套列表推导 | `[[random.uniform(-1, 1), ...] for _ in range(2)]` | 生成 2×2 的嵌套列表；`_` 表示不使用的循环变量 |
| 切片拷贝 | `self.w_output[:]` | 复制一份列表，后续修改原列表不影响拷贝 |
| 函数内 `import` | `import random`、`import math` 写在方法里 | 合法，但通常放在文件顶部 |
| `max` / `min` 夹紧 | `max(-500, min(500, x))` | 把数值限制在区间内（clamp） |
| `%` 取模 | `epoch % 2000 == 0` | 每隔 2000 次执行一次 |
| f-string 格式符 | `f"{total_error:.4f}"`、`f"{inputs} -> {result}"` | `:.4f` 保留 4 位小数；列表会按 `repr` 打印 |

---

## 6. 运行结果解读

实际运行 `python3 perceptron.py`（Python 3.13）的完整输出：

```text
=== AND Gate ===
Converged at epoch 4
  Weights: [0.2, 0.1], Bias: -0.20000000000000004
  [0, 0] -> 0 (expected 0) OK
  [0, 1] -> 0 (expected 0) OK
  [1, 0] -> 0 (expected 0) OK
  [1, 1] -> 1 (expected 1) OK

=== OR Gate ===
Converged at epoch 4
  Weights: [0.1, 0.1], Bias: -0.1
  ...（四个 OK）

=== NOT Gate ===
Converged at epoch 3
  Weights: [-0.1], Bias: 0.0
  [0] -> 1 (expected 1) OK
  [1] -> 0 (expected 0) OK

=== XOR Gate (single perceptron - will fail) ===
Did not converge after 1000 epochs
  [0, 0] -> 1 (expected 0) WRONG
  [0, 1] -> 1 (expected 1) OK
  [1, 0] -> 0 (expected 1) WRONG
  [1, 1] -> 0 (expected 0) OK

=== XOR Gate (multi-layer network - works) ===
  ...（四个 OK）

=== XOR Gate (trained 2-layer network with backpropagation) ===
  Epoch 0, error: 1.2164
  Epoch 2000, error: 0.0017
  Epoch 4000, error: 0.0007
  Epoch 6000, error: 0.0005
  Epoch 8000, error: 0.0003

  [0, 0] -> 0.0074 (rounded: 0, expected 0)
  [0, 1] -> 0.9923 (rounded: 1, expected 1)
  [1, 0] -> 0.9923 (rounded: 1, expected 1)
  [1, 1] -> 0.0094 (rounded: 0, expected 0)
```

逐段解读：

- **AND**：4 个 epoch 收敛。注意 `[1,0]` 的 `z ≈ −2.8e−17`，只是靠浮点舍入"擦边"判对（见 3.3）。
- **OR**：`w = [0.1, 0.1]`、`b = −0.1`，`[0,1]` 和 `[1,0]` 的 `z` 恰好等于 0，靠 `>=` 判为 1——边界紧贴样本。
- **NOT**：bias 为 0 也能实现，`[0]` 落在边界上。三个门都说明：感知器只保证"分开"，不保证"分得好"。
- **单感知器 XOR**：1000 个 epoch 不收敛，权重每个 epoch 循环一次，最终 2 对 2 错。
- **手工两层 XOR**：四个全对，证明多层网络能表示 XOR。
- **反向传播训练的 XOR**：总平方误差从 1.2164 迅速降到 0.0017（前 2000 个 epoch 就基本学会），之后缓慢下降。最终输出离 0/1 都很近（0.0074、0.9923…），四舍五入后全部正确。`[0,1]` 和 `[1,0]` 都显示 0.9923，但更多位数是 0.99235 和 0.99227——网络的解只是近似对称。
- **网络到底学到了什么？** 训练结束后打印参数（额外实验）可以看到：隐藏单元 1 约为 `σ(−5.3·x1 − 5.3·x2 + 7.9)`，即 **NAND**；隐藏单元 2 约为 `σ(−6.8·x1 − 7.0·x2 + 2.9)`，即 **NOR**（只有两个输入都为 0 时才激活）；输出约为 `σ(11.2·h1 − 11.3·h2 − 5.4)`，即 "h1 AND NOT h2"。合起来是 `NAND AND NOT NOR = NAND AND OR = XOR`——和手工版的分解不同，但殊途同归。这说明梯度下降会自己"发明"中间特征。

---

## 7. 动手改一改

1. **NAND 门**：调用 `test_gate("NAND Gate", 2, nand_data)`，验证学到的参数（实测 `w = [-0.2, -0.1]`、`b = 0.2`）构成合法的决策边界。
2. **追踪决策边界**：在 `Perceptron.train` 的每个 epoch 末尾打印直线方程 `x2 = -(w1·x1 + b) / w2`（注意 `w2 = 0` 时要单独处理），观察 AND 训练中边界如何移动。
3. **验证学习率无关性**：把 `lr` 分别设为 0.5、1.0、0.3 训练 AND，比较收敛 epoch 和学到的参数是否只差一个倍数；再用 `fractions.Fraction(1, 10)` 作为学习率，看看精确运算下第几个 epoch 收敛。
4. **多数表决**：构造 3 输入的 8 条真值表，用 `Perceptron(3)` 训练，判断它是否线性可分。
5. **换随机种子**：把 `random.seed(0)` 改成别的值（或把隐藏层改成只有 1 个神经元），观察 `TwoLayerNetwork` 是否还能学会 XOR；再把隐藏单元数扩展成 4（需要把写死的 `range(2)` 改成参数）。
6. **换损失函数**：把 `d_output = error * output * (1 - output)` 改成 `d_output = error`（这正是 sigmoid + 交叉熵的输出层梯度），比较收敛速度。

---

## 8. 常见坑

- **以为多跑几个 epoch 就能收敛**：对不可线性可分的数据（XOR），感知器会永远循环；加 epoch 没用，要换模型。
- **忘记 bias**：没有 bias 时边界必过原点，OR、AND、NAND 都学不会。
- **用 `>` 还是 `>=`**：边界上的样本（`z = 0`）归哪类，取决于这个约定；本节 OR、NOT 学到的解都恰好依赖 `>=`。
- **反向传播中先更新再算梯度**：用更新后的权重去算前一层的梯度，得到的不是真实梯度。要么先算完所有 delta 再更新，要么像代码一样先拷贝旧权重。
- **多层网络全零初始化**：所有隐藏单元永远对称、学到同样的东西；必须随机初始化。
- **`math.exp` 溢出**：参数大于约 709 会抛 `OverflowError`，写 sigmoid 时要夹紧或用数值稳定的分段写法。
