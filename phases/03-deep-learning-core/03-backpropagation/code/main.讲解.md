# 代码讲解 · main.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 03 节 Backpropagation 从头开始 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，纯 Python 标量自动求导，完整跑完约 20 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这是一个 micrograd 风格的**标量自动求导引擎**，外加一个用它训练的小型 MLP。读懂它，你就读懂了 PyTorch `loss.backward()` 的核心思想：

1. **计算图是在前向时"顺手"建好的**：每次 `+`、`*`、`sigmoid` 都生成一个新的 `Value` 节点，记住"我是谁算出来的"以及"梯度该怎么往回传"。
2. **每种运算只需要知道自己的局部导数**：加法原样分发、乘法交换相乘、sigmoid 乘 `s(1−s)`。链式法则会把它们自动串起来。
3. **梯度必须累加（`+=`）**：一个值被多处使用时，梯度是各路径之和；所以每步训练前要 `zero_grad()`。
4. **拓扑排序决定反向的顺序**：保证每个节点在"往下传"之前已经收齐了所有梯度。
5. **完整训练循环**：前向 → loss → 清零 → 反向 → 梯度下降。XOR 用 full-batch，圆分类用在线 SGD。

> 一句话：**autograd = 前向时记录计算图 + 反向时按拓扑逆序、对每个节点执行"上游梯度 × 局部导数"并累加。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Value` | 类 | 一个标量节点：`data`、`grad`、`_backward`、`_children`、`_op` | 计算图节点 |
| `__add__` / `__radd__` / `__mul__` / `__rmul__` / `__neg__` / `__sub__` | 魔术方法 | 运算符重载，生成新节点并定义局部反向规则 | 局部导数 |
| `Value.sigmoid` | 方法 | sigmoid 激活及其反向 | `σ' = σ(1−σ)` |
| `Value.backward` | 方法 | 拓扑排序 + 逆序调用 `_backward` | 反向传播 |
| `mse_loss` | 函数 | `(pred − target)²` | 平方误差 |
| `Neuron` / `Layer` / `Network` | 类 | 由 `Value` 搭出的 MLP；`parameters()` 收集参数，`zero_grad()` 清零 | 全连接网络 |
| `train_xor` | 函数 | 2-4-1 网络，full-batch 梯度下降 1000 轮 | 批量梯度下降 |
| `generate_circle_data` / `train_circle` | 函数 | 生成圆内/圆外数据，2-8-1 网络在线 SGD 2000 轮 | 随机梯度下降 |

数据流：`[Value(x1), Value(x2)]` → `Network.__call__`（层层调用 `Neuron.__call__`，过程中建图）→ 预测 `Value` → `mse_loss` → `loss.backward()` 把梯度写进每个参数的 `.grad` → 手动 `p.data -= lr * p.grad`。

---

## 3. 逐段精讲

### 3.1 `Value`：计算图的节点

```python
class Value:
    def __init__(self, data, children=(), op=''):
        self.data = data
        self.grad = 0.0
        self._backward = lambda: None
        self._children = set(children)
        self._op = op

    def __repr__(self):
        return f"Value(data={self.data:.4f}, grad={self.grad:.4f})"
```

| 属性 | 含义 |
|------|------|
| `data` | 前向计算出来的数值 |
| `grad` | `∂L/∂(这个值)`，初始为 0，反向时累加 |
| `_backward` | 一个无参函数：把 `self.grad` 按局部导数分给输入节点。叶子节点（输入、参数）没有输入，所以默认是什么都不做的 `lambda: None` |
| `_children` | 产生这个值的输入节点（讲义里叫 children，指图中的"上游"），用于拓扑排序 |
| `_op` | 产生它的运算符号，只用于调试 / 可视化 |

- `children=()` 用空元组作默认值（不可变对象，避免"可变默认参数"陷阱）。
- `set(children)` 去重：`diff * diff` 的两个输入是同一个对象，集合里只保留一个，拓扑排序时不会重复访问。梯度仍然正确，原因见 3.3。
- `__repr__` 让 `print(v)` 显示 `Value(data=..., grad=...)`，调试时非常方便。

### 3.2 加法：梯度原样分发

```python
    def __add__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data + other.data, (self, other), '+')

        def _backward():
            self.grad += out.grad
            other.grad += out.grad

        out._backward = _backward
        return out

    def __radd__(self, other):
        return self.__add__(other)
```

- 第一行把普通数字"升级"为 `Value`，这样 `v + 1` 也能工作。
- `∂(a+b)/∂a = ∂(a+b)/∂b = 1`，所以两个输入都直接拿到 `out.grad`——加法节点是梯度的"分发器"。
- **闭包**：`_backward` 定义在 `__add__` 内部，它"记住"了当时的 `self`、`other`、`out`。等到反向时才被调用，依然能访问这三个对象——这是整个引擎能工作的关键语法。
- `__radd__`：当左边是普通数字、右边是 `Value` 时（如 `2 + v`），Python 先尝试 `int.__add__`，失败后调用 `v.__radd__(2)`。加法满足交换律，直接转给 `__add__`。

### 3.3 乘法、取负、减法

```python
    def __mul__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data * other.data, (self, other), '*')

        def _backward():
            self.grad += other.data * out.grad
            other.grad += self.data * out.grad

        out._backward = _backward
        return out

    def __rmul__(self, other):
        return self.__mul__(other)

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + (-other)
```

- `∂(a·b)/∂a = b`、`∂(a·b)/∂b = a`：每个输入拿到"**对方的值** × 上游梯度"。注意用的是前向时的 `data`——这就是反向传播必须保存前向值的原因。
- **为什么是 `+=`？** 以 `c = a * b + a` 为例，`a` 同时流向乘法和加法两个节点，正确梯度 `∂c/∂a = b + 1` 需要把两条路径的贡献相加。若写成 `=`，后执行的会覆盖先执行的，实测会得到 `a.grad = -3.0`（正确值 −2.0）。
- **自乘 `d * d` 为什么是对的**：此时 `self` 和 `other` 是同一个对象，两行 `+=` 各加一次 `d.data * out.grad`，合计 `2·d·out.grad`，正好是 `d(x²)/dx = 2x`。
- `__neg__` 和 `__sub__` 不需要自己的 `_backward`：它们**复用**乘法和加法，梯度自然正确。`self + (-other)` 中若 `other` 是 float，`-other` 就是普通取负，再由 `__add__` 包装。
- ⚠️ 没有实现 `__rsub__`、`__truediv__`、`__pow__`：`1 - v`、`v / 2`、`v ** 2` 都会报 `TypeError`。讲义练习 1、3 让你补上它们。

### 3.4 `sigmoid`：复用前向结果

```python
    def sigmoid(self):
        x = max(-500, min(500, self.data))
        s = 1.0 / (1.0 + math.exp(-x))
        out = Value(s, (self,), 'sigmoid')

        def _backward():
            self.grad += (s * (1 - s)) * out.grad

        out._backward = _backward
        return out
```

- sigmoid 作为一个"整体运算"实现，而不是拆成 `exp`、`+`、`/` 多个节点——它的导数可以直接用输出表示 `σ' = s(1−s)`，闭包捕获了前向时的 `s`，反向时**零额外计算**。这和 PyTorch 中"融合算子（fused op）"的思路一致：节点更少、更快、更省内存。
- 夹紧到 ±500 防止 `math.exp` 溢出抛 `OverflowError`。
- `s(1−s)` 的最大值是 0.25（`s = 0.5` 时），这就是讲义"梯度消失"一节的根源。

### 3.5 `backward`：拓扑排序 + 逆序传播

```python
    def backward(self):
        topo = []
        visited = set()

        def build_topo(v):
            if v not in visited:
                visited.add(v)
                for child in v._children:
                    build_topo(child)
                topo.append(v)

        build_topo(self)
        self.grad = 1.0
        for v in reversed(topo):
            v._backward()
```

- `build_topo` 是深度优先搜索的**后序遍历**：先递归处理所有输入，再把自己加入 `topo`。所以 `topo` 中每个节点都排在它的所有输入之后；`reversed(topo)` 则保证"用到 v 的节点"都在 v 之前被处理——v 的梯度先收齐，再往下传。
- `visited` 集合防止共享子图被重复加入（例如同一个权重被多个样本使用）。`Value` 没有定义 `__eq__`/`__hash__`，所以按对象身份（id）哈希，两个数值相同的不同节点不会被误判为同一个。
- `self.grad = 1.0`：起点 `∂L/∂L = 1`。
- ⚠️ 递归实现在图很深时会超出 Python 默认递归深度（1000）而抛 `RecursionError`。本节的小网络没问题，但长链（比如上千步的累加）就会出事；工程上改用显式栈的迭代版 DFS。
- ⚠️ 每次 `backward()` 都重新建一遍拓扑序，且图在训练中不会被释放复用——对标量引擎来说这是最简单的做法。

### 3.6 `mse_loss`

```python
def mse_loss(predicted, target):
    diff = predicted + Value(-target)
    return diff * diff
```

- 单输出的平方误差 `(pred − target)²`，没有 ½ 系数，所以 `∂L/∂pred = 2(pred − target)`，与讲义推导一致。
- 用"加上一个取负的常数节点"表达减法——写讲义时还没有 `__sub__`；代码中虽然已经有了 `__sub__`，这里保留了原来的写法。`target` 是 float，`Value(-target)` 是一个叶子节点，它也会得到梯度，但没有人用它。

### 3.7 `Neuron` / `Layer` / `Network`

```python
class Neuron:
    def __init__(self, n_inputs):
        scale = (2.0 / n_inputs) ** 0.5
        self.weights = [Value(random.uniform(-scale, scale)) for _ in range(n_inputs)]
        self.bias = Value(0.0)

    def __call__(self, x):
        act = sum((wi * xi for wi, xi in zip(self.weights, x)), self.bias)
        return act.sigmoid()

    def parameters(self):
        return self.weights + [self.bias]
```

- **初始化**：权重在 `[-√(2/n), √(2/n)]` 上均匀分布，按输入个数缩放，防止输入多时加权和太大、sigmoid 一上来就饱和。⚠️ `√(2/n)` 是 He 初始化的**标准差**（为 ReLU 设计），这里却用作均匀分布的**边界**，实际标准差只有 `√(2/(3n))`；对 sigmoid 网络，Xavier 初始化更常用。这些细节在第 08 节展开。
- `sum(生成器, self.bias)`：`sum` 的第二个参数是**起始值**，从 `bias` 开始累加每个 `wi * xi`，一行完成 `w·x + b`。因为起始值是 `Value`，后续都是 `Value + Value`，不需要 `__radd__`；若省略起始值，`sum` 会从整数 0 开始，第一步 `0 + Value` 就要靠 `__radd__`。
- `__call__` 让对象可以像函数一样调用：`neuron(x)`。这与 PyTorch `nn.Module` 的用法一致。

```python
class Layer:
    # ...
    def __call__(self, x):
        out = [n(x) for n in self.neurons]
        return out[0] if len(out) == 1 else out

class Network:
    # ...
    def __call__(self, x):
        for layer in self.layers:
            x = layer(x)
            if not isinstance(x, list):
                x = [x]
        return x[0] if len(x) == 1 else x

    def zero_grad(self):
        for p in self.parameters():
            p.grad = 0.0
```

- `Layer` 只有一个神经元时返回单个 `Value`，否则返回列表；`Network` 每层后再"包回"列表，最后若只剩一个输出再拆开。⚠️ 这种"返回类型随长度变化"的设计让调用者用起来方便（`pred.data` 直接可用），但容易出错；张量框架统一返回张量，形状由 shape 表达。
- `parameters()` 逐层收集所有 `Value` 参数：2-4-1 网络有 `(2+1)×4 + (4+1)×1 = 17` 个，2-8-1 网络有 33 个。
- `zero_grad()` 只清零**参数**的梯度。中间节点每次前向都是新建的，不需要清零。

### 3.8 `train_xor`：full-batch 梯度下降

```python
    for epoch in range(1000):
        total_loss = Value(0.0)
        for inputs, target in xor_data:
            x = [Value(i) for i in inputs]
            pred = net(x)
            loss = mse_loss(pred, target)
            total_loss = total_loss + loss

        net.zero_grad()
        total_loss.backward()

        for p in net.parameters():
            p.data -= learning_rate * p.grad
```

- 4 个样本的 loss **加在一起**构成一张大图，然后只做一次 `backward`：每个参数的梯度自动是 4 个样本梯度之和（又一次体现了 `+=` 的意义——同一个权重被 4 个样本共享）。
- 更新写在 `p.data` 上而不是 `p` 本身：直接改数值，不会被记录进计算图。PyTorch 中对应地要在 `torch.no_grad()` 下更新参数（或交给 `optimizer.step()`）。
- `learning_rate = 1.0` 对这个求和形式的小问题是可以的；如果把 loss 改成取平均，等效学习率会变成原来的 1/4。
- 训练三步曲的顺序：`zero_grad` → `backward` → 更新。把 `zero_grad` 放在前向之前或之后都可以，只要在 `backward` 之前。

### 3.9 `generate_circle_data` 与 `train_circle`：在线 SGD

```python
def generate_circle_data(n=100):
    data = []
    for _ in range(n):
        x1 = random.uniform(-1.5, 1.5)
        x2 = random.uniform(-1.5, 1.5)
        label = 1.0 if x1 * x1 + x2 * x2 < 1.0 else 0.0
        data.append(([x1, x2], label))
    return data
```

```python
    for epoch in range(2000):
        random.shuffle(circle_data)
        total_loss_val = 0.0
        for inputs, target in circle_data:
            x = [Value(i) for i in inputs]
            pred = net(x)
            loss = mse_loss(pred, target)
            net.zero_grad()
            loss.backward()
            for p in net.parameters():
                p.data -= learning_rate * p.grad
            total_loss_val += loss.data
```

- 数据：`[-1.5, 1.5]²` 中均匀采样 80 个点，半径 1 的圆内标 1。圆面积占比 `π/9 ≈ 35%`，实际这 80 个点中有 24 个在圆内（30%）。
- **在线 SGD**：每个样本都做一次"前向 → 清零 → 反向 → 更新"。好处是更新频繁、每步的图很小；每个 epoch 先 `random.shuffle` 打乱顺序，避免网络受样本顺序影响。
- `total_loss_val` 用 `loss.data`（普通 float）累加，只用于打印，不参与建图。
- 每 200 个 epoch 在**训练集**上算一次准确率。⚠️ 没有独立的测试集，100% 只说明拟合了训练数据；最后用 5 个手选点做了一个非常粗略的"泛化"检查。
- ⚠️ 讲义说在线 SGD "breaks symmetry faster"，这个说法不严谨：打破对称性靠的是**随机初始化**（每个神经元权重不同），与 batch 大小无关。在线 SGD 的真实好处是更新更频繁、梯度噪声有助于跳出平坦区域。

### 3.10 入口

```python
if __name__ == "__main__":
    train_xor()
    train_circle()
```

两个实验各自在函数开头设置随机种子（`seed(42)`、`seed(7)`），互不干扰，结果可复现。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 标量级 `Value` 节点 | 每个乘加都是一个节点，链式法则看得清清楚楚 | 极慢（本脚本约 20 秒）；框架以张量为节点，一个矩阵乘就是一个节点 |
| 闭包保存反向规则 | 前向时就"顺便"把局部导数需要的值捕获进来 | 每个节点一个闭包对象，内存开销大 |
| 梯度 `+=` 累加 | 多元链式法则要求对所有路径求和 | 每步必须 `zero_grad()`，忘了就训练失败 |
| 递归拓扑排序 | 代码最短 | 深图会 `RecursionError`；改用迭代 DFS |
| sigmoid 作为融合算子 | 直接用 `s(1−s)`，节点少、无额外计算 | 每加一种激活都要手写导数（框架同样如此，只是写好了） |
| `sqrt(2/n)` 均匀初始化 | 按输入数缩放，缓解饱和 | 与 He / Xavier 的标准定义不完全一致 |
| MSE + sigmoid 输出 | 与上一节一致，推导简单 | 分类任务应用交叉熵，梯度更好（下一节、第 05 节） |
| 手动 `p.data -= lr * p.grad` | 展示优化器的本质 | 生产中用 `torch.optim` 的 SGD / Adam |
| 在训练集上报准确率 | 演示训练过程 | 应划分验证 / 测试集评估泛化 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数用不可变对象 | `children=(), op=''` | 默认值只创建一次，用元组 / 字符串避免共享可变对象的坑 |
| `lambda` | `self._backward = lambda: None` | 匿名函数；这里表示"什么都不做"的默认反向函数 |
| `set` 集合 | `set(children)`、`visited = set()` | 去重、O(1) 判断成员；对象默认按身份哈希 |
| `__repr__` | `return f"Value(data={self.data:.4f}, ...)"` | 定义对象的打印形式 |
| 运算符重载 | `__add__`、`__mul__`、`__neg__`、`__sub__` | 让 `a + b`、`a * b`、`-a`、`a - b` 作用于 `Value` |
| 反射运算符 | `__radd__`、`__rmul__` | 左操作数不是 `Value` 时（如 `2 * v`）的回退方法 |
| `isinstance` | `other if isinstance(other, Value) else Value(other)` | 运行时类型判断，把数字自动包装成 `Value` |
| 嵌套函数与闭包 | `def _backward(): self.grad += out.grad` | 内部函数记住外部作用域的变量，稍后调用仍可访问 |
| 函数作为属性 | `out._backward = _backward` | 函数是"一等公民"，可以赋值给属性、稍后调用 |
| 递归函数 | `build_topo(child)` | 函数调用自身实现 DFS；注意递归深度上限 |
| `reversed` | `for v in reversed(topo)` | 逆序遍历列表，不复制 |
| `sum` 带起始值 | `sum((wi * xi for ...), self.bias)` | 第二个参数是累加初值，可以是任意支持 `+` 的对象 |
| `__call__` | `def __call__(self, x)` → `net(x)` | 让实例像函数一样被调用 |
| 列表拼接 / 扩展 | `self.weights + [self.bias]`、`params.extend(...)` | `+` 返回新列表；`extend` 原地追加多个元素 |
| `random.shuffle` | `random.shuffle(circle_data)` | 原地打乱列表 |
| f-string 宽度与精度 | `f"Epoch {epoch:4d} | Loss: {total_loss.data:.6f}"` | `4d` 占 4 位右对齐；`.6f` 六位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才训练，被导入时只提供类和函数 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，耗时约 22 秒）的输出：

```text
==================================================
Training on XOR
==================================================
Epoch    0 | Loss: 1.067385
Epoch  100 | Loss: 0.805927
Epoch  200 | Loss: 0.190474
Epoch  300 | Loss: 0.035562
Epoch  400 | Loss: 0.015281
...
Epoch  900 | Loss: 0.003385

XOR Results:
  [0.0, 0.0] -> 0.0251 (rounded: 0, expected 0)
  [0.0, 1.0] -> 0.9677 (rounded: 1, expected 1)
  [1.0, 0.0] -> 0.9796 (rounded: 1, expected 1)
  [1.0, 1.0] -> 0.0286 (rounded: 0, expected 0)

==================================================
Training on Circle Classification
==================================================
Epoch    0 | Loss: 17.1256 | Accuracy: 70.0%
Epoch  200 | Loss: 0.3585 | Accuracy: 100.0%
Epoch  400 | Loss: 0.1224 | Accuracy: 100.0%
...
Epoch 1800 | Loss: 0.0132 | Accuracy: 100.0%

Sample Circle Results:
  [0.0, 0.0] -> 1.0000 (inside, expected inside) OK
  [0.5, 0.5] -> 0.9901 (inside, expected inside) OK
  [1.2, 1.2] -> 0.0000 (outside, expected outside) OK
  [0.0, 1.2] -> 0.0004 (outside, expected outside) OK
  [-0.3, 0.3] -> 1.0000 (inside, expected inside) OK
```

逐段解读：

- **XOR 的 loss 曲线**：前 100 轮几乎不动（1.07 → 0.81），然后在 100～300 轮间骤降——这是 sigmoid 网络常见的"平台期 → 突破"：一开始隐藏单元还没分化出有用特征，梯度很小；一旦找到方向，loss 迅速下降。总 loss 1.07 意味着平均每个样本误差约 `√(1.07/4) ≈ 0.52`，基本等于瞎猜。
- **XOR 结果**：四个输出都在正确一侧，但不像上一节手工权重那样贴近 0/1（0.0251、0.9677），继续训练会更接近。
- **圆分类 epoch 0**：准确率 70.0% 恰好等于"全部猜圆外"的比例（80 个点里 56 个在圆外）——第一轮训练后网络还只学会了"多数类"。loss 17.13 是这一轮 80 个样本的平方误差之和（边训练边累加）。
- **圆分类 epoch 200 起**：训练集准确率 100%，loss 持续下降。注意这是**训练集**上的数字。
- **5 个手选点**：都判对，其中圆心 `[0,0]` 和 `[-0.3, 0.3]` 输出 1.0000，远离圆的 `[1.2, 1.2]` 输出 0.0000，说明网络学到了一个以原点为中心的封闭边界，而且置信度很高。

---

## 7. 动手改一改

1. **补齐运算**：实现 `__rsub__`、`__truediv__`、`__pow__`（整数幂），用 `(pred - target) ** 2` 重写 `mse_loss`，确认梯度与原版一致（讲义练习 1、3）。
2. **梯度检查**：写一个中心差分的 `grad_check`，验证 `Network([2, 4, 1])` 在 XOR 上的所有梯度（参考测验 Q9，相对误差应在 1e−7 以下）。
3. **换 ReLU**：给 `Value` 加 `relu()`，让 `Neuron` 支持选择激活函数，隐藏层用 ReLU、输出层仍用 sigmoid，比较 XOR 的收敛速度（讲义练习 2）。
4. **看见梯度消失**：构造 `Network([2, 8, 8, 8, 8, 8, 1])`，做一次前向和反向，按层打印权重的平均 `|grad|`（实测从输出层约 0.15 降到第一层约 6e−6）。
5. **梯度裁剪**：在 `backward()` 之后把所有 `p.grad` 夹到 `[-1, 1]`，训练一个 4 层以上的 sigmoid 网络，对比有无裁剪的 loss 曲线（讲义练习 4）。
6. **迭代版拓扑排序**：用显式栈改写 `build_topo`，然后构造一条 5000 个加法组成的长链，验证递归版会 `RecursionError` 而迭代版不会。

---

## 8. 常见坑

- **把 `+=` 写成 `=`**：变量被多次使用时梯度被覆盖，结果悄悄出错，不会报异常。
- **忘记 `zero_grad()`**：梯度跨步累加，训练震荡或发散（实测 XOR 会卡在 loss ≈ 0.5）。
- **局部导数用错了值**：乘法要用**对方的** `data`；sigmoid 要用前向时的 `s`，而不是重新对 `grad` 求 sigmoid。
- **在计算图里更新参数**：参数更新必须作用于 `p.data`（PyTorch 中在 `no_grad` 下），否则更新操作本身会被记录进图。
- **递归深度**：长链计算图会触发 `RecursionError`。
- **只看训练集准确率**：100% 训练准确率不代表模型泛化好，要留出验证集。
