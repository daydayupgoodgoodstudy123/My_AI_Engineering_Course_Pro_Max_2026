# 代码讲解 · autodiff.py

> **所属小节**：阶段 01 · 数学基础 · 第 05 节 Chain Rule & 自动微分 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python autodiff.py` ｜ **依赖**：仅 Python 标准库（`random`、`math`）；最后一个演示可选用 PyTorch 对拍（未安装则自动跳过）

---

## 1. 这份代码在考察什么

这是一个约 100 行核心代码的**微型 autograd 引擎**（思路与 Andrej Karpathy 的 micrograd 相同，讲义也直接称之为 micrograd），目标是让你看清 PyTorch `loss.backward()` 背后到底发生了什么：

1. **把数字包装成节点**：`Value` 同时保存数值 `data`、梯度 `grad`、输入节点 `_prev` 和反向函数 `_backward`。
2. **运算即建图**：每次 `+`、`*`、`tanh` 等运算都会新建一个节点，并用**闭包**记住"怎么把梯度传回输入"。
3. **反向模式自动微分**：`backward()` 先拓扑排序，再逆序执行每个节点的 `_backward`，从 `dy/dy = 1` 出发把梯度传回所有叶子。
4. **梯度累加**：所有反向函数都用 `+=`，正确处理"一个值被多处使用"的情况。
5. **从标量到神经网络**：用 `Neuron` → `Layer` → `MLP` 搭出 2-4-1 的网络，在 XOR 上完成完整训练循环。
6. **验证正确性**：手算期望值 + `assert`、梯度检查（与中心差分对比）、可选的 PyTorch 对拍。

> 一句话：**每个运算只需要知道自己的局部导数，链式法则 + 拓扑排序负责把它们拼成整个网络的梯度。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Value` | 类 | 标量节点：数值、梯度、输入、反向闭包 | 计算图节点 |
| `__add__` / `__mul__` / `__pow__` | 魔术方法 | 带反向函数的原子运算 | 局部导数 |
| `__radd__` / `__rmul__` / `__neg__` / `__sub__` / `__rsub__` / `__truediv__` | 魔术方法 | 由原子运算组合而成，梯度"白送" | 链式法则的组合性 |
| `relu` / `tanh` / `exp` / `log` | 方法 | 激活函数与常用非线性 | 局部导数 |
| `backward` | 方法 | 拓扑排序 + 逆序执行 `_backward` | 反向模式自动微分 |
| `Neuron` / `Layer` / `MLP` | 类 | 用 `Value` 搭建的多层感知机 | 神经网络结构 |
| `gradient_check` | 函数 | 自动微分 vs 数值微分 | 梯度检查 |
| `demo_*` × 8 | 演示函数 | 手算验证、训练、对拍 | — |

数据流：`demo_*` 用 `Value` 写出表达式（前向时自动建图）→ 对输出调用 `.backward()` → 读取各叶子节点的 `.grad` → 与手算/数值/PyTorch 结果比较。训练 demo 在此基础上增加"清零 → 反向 → 更新"的循环。

---

## 3. 逐段精讲

### 3.1 `Value` 的五个字段

```python
class Value:
    def __init__(self, data, children=(), op=''):
        self.data = float(data)
        self.grad = 0.0
        self._backward = lambda: None
        self._prev = set(children)
        self._op = op
```

| 字段 | 含义 |
|------|------|
| `data` | 前向计算出的数值。`float(data)` 统一转成浮点，`Value(0)` 和 `Value(0.0)` 行为一致（讲义版本没有这一步） |
| `grad` | 最终输出对这个节点的偏导数，初始为 0，反向传播时被**累加** |
| `_backward` | 一个无参函数，执行时把本节点的梯度按局部导数传给输入。叶子节点没有输入，默认 `lambda: None` 什么都不做 |
| `_prev` | 产生这个节点的输入节点集合（计算图的边） |
| `_op` | 产生它的运算符号，仅用于调试/可视化 |

- 前缀 `_` 是 Python 约定的"内部属性"，提示外部不要直接改。
- `children=()` 用不可变的空元组做默认参数，避免"可变默认参数"陷阱。
- `_prev` 用 `set`：同一个节点即使出现两次（如 `x * x`）也只记一次，拓扑排序不会重复访问。**注意**：去重不影响梯度正确性，因为 `x * x` 的 `_backward` 里 `self` 和 `other` 都是 `x`，两行 `+=` 会给 `x` 加两次，得到 `2x`（实测 `x=3` 时梯度为 6.0）。
- `Value` 没有重写 `__eq__` / `__hash__`，所以放进 `set` 时按**对象身份**区分。如果有人"好心"地按 `data` 实现 `__eq__`，两个数值相同的不同节点就会被当成同一个，计算图会出错。

### 3.2 加法与乘法：闭包记住"怎么回传"

```python
    def __add__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data + other.data, (self, other), '+')
        def _backward():
            self.grad += out.grad
            other.grad += out.grad
        out._backward = _backward
        return out

    def __mul__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data * other.data, (self, other), '*')
        def _backward():
            self.grad += other.data * out.grad
            other.grad += self.data * out.grad
        out._backward = _backward
        return out
```

- **第一行**：如果 `other` 是普通数字，先包装成 `Value`，这样 `x + 1`、`x * 2` 都能用。
- **前向**：计算结果，并把 `(self, other)` 记为输入。
- **反向（局部导数 × 上游梯度）**：
  - 加法：`∂(a+b)/∂a = 1`，所以梯度**原样分发**给两个输入。
  - 乘法：`∂(ab)/∂a = b`，所以 a 收到 `b × 上游梯度`，b 收到 `a × 上游梯度`——**交换相乘**。
- **闭包**：内部函数 `_backward` 引用了外层的 `self`、`other`、`out`。即使 `__add__` 已经返回，这些变量仍被闭包"捕获"着，等到反向传播时再使用。这正是"前向时保存中间值、反向时使用"的实现方式，也是训练比推理更占内存的原因。
- **为什么是 `+=`**：一个节点可能被多个运算使用，总梯度是各路贡献之和（多元链式法则）。若写成 `=`，后执行的反向函数会覆盖先前的贡献（测验 Q9 给出了具体反例：`f = x*y + x` 会得到 3 而不是 4）。

### 3.3 组合运算：反射方法与"白送"的梯度

```python
    def __radd__(self, other):
        return self.__add__(other)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + (-other)

    def __rsub__(self, other):
        return other + (-self)
```

- **反射方法**：`2 * x` 时 Python 先调用 `int.__mul__(2, x)`，int 不认识 `Value`，返回 `NotImplemented`，Python 再尝试 `x.__rmul__(2)`。加法和乘法满足交换律，所以直接转调即可。`sum(...)` 从整数 0 开始累加，第一步 `0 + v` 也依赖 `__radd__`。
- **减法 = 加上相反数**，取负 = 乘以 -1。它们没有自己的 `_backward`，梯度通过底层的 `*` 和 `+` 自动正确传播。
- `__rsub__` 处理 `5 - x`：变成 `5 + (-x)`，最终走 `x` 的 `__radd__`。
- ⚠️ 只有 `__truediv__` 没有 `__rtruediv__`，所以 `2 / x` 会报 `TypeError`（测验 Q11 中补上）。

### 3.4 幂、除法与非线性函数

```python
    def __pow__(self, n):
        out = Value(self.data ** n, (self,), f'**{n}')
        def _backward():
            self.grad += n * (self.data ** (n - 1)) * out.grad
        out._backward = _backward
        return out

    def __truediv__(self, other):
        return self * (other ** -1) if isinstance(other, Value) else self * (Value(other) ** -1)
```

- 幂法则 `d(xⁿ)/dx = n·xⁿ⁻¹`。⚠️ 这里 `n` 只能是普通数字（常数指数），不支持 `x ** y` 这种两边都是 `Value` 的情况。
- 除法 `a / b = a · b⁻¹`，又是一个用已有运算组合出来的例子。⚠️ 当 b 为 0 时，`0.0 ** -1` 会抛 `ZeroDivisionError`。
- 条件表达式 `A if 条件 else B` 一行处理"除数是不是 `Value`"两种情况。

```python
    def relu(self):
        out = Value(max(0, self.data), (self,), 'relu')
        def _backward():
            self.grad += (1.0 if out.data > 0 else 0.0) * out.grad
        out._backward = _backward
        return out

    def tanh(self):
        import math
        t = math.tanh(self.data)
        out = Value(t, (self,), 'tanh')
        def _backward():
            self.grad += (1 - t ** 2) * out.grad
        out._backward = _backward
        return out
```

| 运算 | 前向 | 局部导数 | 实现细节 |
|------|------|---------|---------|
| `relu` | `max(0, x)` | x>0 时 1，否则 0 | 在 x=0 处取 0（次梯度的一种约定） |
| `tanh` | `tanh(x)` | `1 - tanh²(x)` | 复用前向算出的 `t`，不重复计算 |
| `exp` | `eˣ` | `eˣ` | 复用前向的 `e` |
| `log` | `ln x` | `1/x` | 用 `self.data`；⚠️ x ≤ 0 时前向就会报 `math domain error` |

- 复用前向结果（`t`、`e`）是 autograd 的常见优化：反向公式能用输出表示时就直接用输出。
- `import math` 写在方法内部，每次调用都会执行 import 语句（Python 会命中模块缓存，开销很小），但放在文件顶部更规范。

### 3.5 `backward()`：拓扑排序 + 逆序传播

```python
    def backward(self):
        topo = []
        visited = set()
        def build_topo(v):
            if v not in visited:
                visited.add(v)
                for child in v._prev:
                    build_topo(child)
                topo.append(v)
        build_topo(self)

        self.grad = 1.0
        for v in reversed(topo):
            v._backward()
```

- **拓扑排序**：`build_topo` 是深度优先搜索的**后序遍历**——先递归处理所有输入，再把自己加进 `topo`。因此 `topo` 里每个节点都排在它的所有输入之后。
- **逆序执行**：`reversed(topo)` 从输出开始。轮到某个节点时，所有使用它的下游节点都已执行完 `_backward`，它的 `grad` 已经累加完整，可以安全地继续往输入传。
- **种子梯度** `self.grad = 1.0`：`dy/dy = 1`。注意这里是赋值而不是累加。
- `visited` 防止同一节点被重复加入（图中共享节点很常见）。
- ⚠️ **不会自动清零**：重复调用 `backward()` 会把梯度再加一遍（实测 `y = x**3` 调用两次后 `x.grad = 24`）。训练循环必须手动清零参数梯度。
- ⚠️ **递归深度**：`build_topo` 每深入一层图就递归一次，Python 默认上限约 1000。实测对 1500 个 `Value` 求和后调用 `backward()` 会抛 `RecursionError`（测验 Q12 给出了用显式栈的非递归写法）。

### 3.6 手算验证的 demo：`demo_basic` / `demo_complex` / `demo_neuron`

```python
    x1 = Value(2.0)
    x2 = Value(3.0)
    a = x1 * x2
    b = a + Value(1.0)
    y = b.relu()
    y.backward()
    # ...
    assert abs(x1.grad - 3.0) < 1e-6
    assert abs(x2.grad - 2.0) < 1e-6
```

- 和讲义中的计算图完全对应：`y = relu(x1·x2 + 1) = relu(7) = 7`；relu 处局部导数 1，加法原样传递，乘法交换相乘，所以 `dy/dx1 = x2 = 3`、`dy/dx2 = x1 = 2`。
- 用 `assert abs(实际 - 期望) < 1e-6` 而不是 `==`，是浮点比较的标准写法。断言失败会直接抛 `AssertionError`，程序停止——这让 demo 同时充当了**单元测试**。

```python
    w1 = Value(0.5)
    w2 = Value(-1.5)
    x1 = Value(3.0)
    x2 = Value(2.0)
    b = Value(0.1)

    y = (w1 * x1 + w2 * x2 + b).relu()
    y.backward()
    # ...
    pre = w1.data * x1.data + w2.data * x2.data + b.data
    if pre > 0:
        # ... 断言五个梯度分别等于 x1, x2, w1, w2, 1
    else:
        assert abs(w1.grad) < 1e-6
        assert abs(w2.grad) < 1e-6
        print("  PASSED (relu inactive, all grads zero)\n")
```

- 这组参数的预激活是 `1.5 - 3.0 + 0.1 = -1.4 < 0`，ReLU 处于"关闭"状态，5 个梯度全部为 0——实际运行走的是 `else` 分支。这恰好演示了"死亡 ReLU"：神经元输出恒为 0 时，它的参数收不到梯度、无法学习。
- 代码用 `if pre > 0` 把两种情况都写了断言，换一组参数（如 `b = 2.0`）就能看到"激活"分支。讲义练习 3 要求验证全部五个梯度，用激活分支的参数更有意义。

### 3.7 `Neuron` / `Layer` / `MLP`：用标量节点搭网络

```python
class Neuron:
    def __init__(self, n_inputs):
        self.w = [Value(random.uniform(-1, 1)) for _ in range(n_inputs)]
        self.b = Value(0.0)

    def __call__(self, x):
        act = sum((wi * xi for wi, xi in zip(self.w, x)), self.b)
        return act.tanh()

    def parameters(self):
        return self.w + [self.b]
```

- `__call__` 让对象可以像函数一样调用：`neuron(x)`。PyTorch 的 `nn.Module` 也是这样设计的（`model(x)` 实际调用 `forward`）。
- `sum(生成器, self.b)`：`sum` 的第二个参数是**起始值**。从 `self.b` 开始累加 `wᵢ·xᵢ`，一行完成 `w·x + b`，而且结果自然是 `Value`。
- 权重用 `random.uniform(-1, 1)` 初始化，偏置初始化为 0。
- `parameters()` 返回所有可学习参数的列表，供训练循环清零和更新。

```python
class Layer:
    # ...
    def parameters(self):
        return [p for n in self.neurons for p in n.parameters()]


class MLP:
    def __init__(self, sizes):
        self.layers = [Layer(sizes[i], sizes[i + 1]) for i in range(len(sizes) - 1)]

    def __call__(self, x):
        for layer in self.layers:
            x = layer(x)
        return x[0] if len(x) == 1 else x
```

- `[p for n in self.neurons for p in n.parameters()]` 是**双层列表推导**：外层遍历神经元，内层遍历每个神经元的参数，把嵌套列表"摊平"。
- `MLP([2, 4, 1])` 生成两层：`Layer(2, 4)` 和 `Layer(4, 1)`。参数量 = 4×(2+1) + 1×(4+1) = **17**。
- `__call__` 中 `x` 依次穿过每一层；最后一层只有一个输出时直接返回标量 `Value`，便于计算 loss。
- 每个神经元都是逐个标量运算，比矩阵实现慢得多，但每一步都清清楚楚地出现在计算图里。

### 3.8 XOR 训练循环

```python
    random.seed(42)
    model = MLP([2, 4, 1])

    xs = [[Value(0), Value(0)], [Value(0), Value(1)],
          [Value(1), Value(0)], [Value(1), Value(1)]]
    ys = [-1.0, 1.0, 1.0, -1.0]

    for step in range(100):
        preds = [model(x) for x in xs]
        loss = sum((p + Value(-y)) ** 2 for p, y in zip(preds, ys))

        for p in model.parameters():
            p.grad = 0.0
        loss.backward()

        lr = 0.05
        for p in model.parameters():
            p.data -= lr * p.grad
```

- **XOR**：输入相同输出 -1，不同输出 +1（用 ±1 是为了匹配 tanh 的值域）。XOR 不是线性可分的，单个神经元学不会，需要隐藏层——这是它作为经典测试题的原因。
- **训练四步**：
  1. 前向：对 4 个样本预测，`loss = Σ(pred - y)²`（`p + Value(-y)` 等价于 `p - y`）。
  2. 清零：把上一步残留在参数上的梯度清掉。
  3. 反向：`loss.backward()`，一次得到 17 个参数的梯度。
  4. 更新：`p.data -= lr * p.grad`——直接改 `data`，**不经过** `Value` 运算，所以不会建图。这对应 PyTorch 中 `with torch.no_grad():` 下的参数更新。
- **为什么只清零参数**：每一步都重新调用 `model(x)`，所有中间节点都是新建的（梯度从 0 开始），这就是**动态图**；只有跨步复用的参数需要手动清零。
- ⚠️ `xs` 里的输入也是 `Value`，同样会收到梯度并一直累加（从不清零）。它们不被更新，所以不影响结果，只是多余的计算。
- ⚠️ `lr = 0.05` 写在循环内部，每一步都重新赋值一次，放在循环外更规范。

### 3.9 `gradient_check`：用数值导数检验 autodiff

```python
def gradient_check(build_expr, x_val, h=1e-7):
    x = Value(x_val)
    y = build_expr(x)
    y.backward()
    autodiff_grad = x.grad

    y_plus = build_expr(Value(x_val + h)).data
    y_minus = build_expr(Value(x_val - h)).data
    numerical_grad = (y_plus - y_minus) / (2 * h)

    diff = abs(autodiff_grad - numerical_grad)
    return autodiff_grad, numerical_grad, diff
```

- `build_expr` 是一个"给我一个 `Value`，返回表达式结果"的函数。同一个函数被调用三次：一次用于自动微分，两次（`x ± h`）用于中心差分。
- 每次都新建 `Value`，三次计算互不干扰。
- `demo_gradient_check` 用 5 个表达式（多项式、`tanh(x²)`、有理分式、`exp(x)·x`、`log(x²+1)`）覆盖了几乎所有算子，阈值 `1e-5`。
- 注意 `(x+1) / (x^2+1)` 那一项实际写成 `(x + 1) * ((x ** 2 + 1) ** -1)`，绕开了 `/` 运算符——效果相同。
- ⚠️ 只检查单变量、单点（x=0.5），而且用的是绝对误差。严格的梯度检查应在多个随机点、多个变量上用相对误差（见测验 Q15 及上一节测验）。

### 3.10 可选依赖：`demo_verify_pytorch`

```python
    try:
        import torch
    except ImportError:
        print("  PyTorch not installed, skipping verification.\n")
        return
```

和上一节 NumPy 的处理方式相同：装了 PyTorch 就做对拍，没装就跳过，保证脚本在纯标准库环境下也能完整运行。对拍内容是同一个 `relu(x1*x2 + 1)`，两者梯度都应为 3.0 和 2.0。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 标量级节点（每个数一个 `Value`） | 每个运算的梯度都看得见 | 极慢、极占内存；PyTorch 以张量为节点，一个节点对应一次矩阵运算 |
| 闭包保存 `_backward` | 局部导数和所需中间值天然绑定 | 内存随图大小增长；框架用 `grad_fn` 对象 + 保存的张量 |
| `+=` 累加梯度 | 正确处理多路径 | 必须手动清零（PyTorch 的 `zero_grad()`） |
| 递归 DFS 拓扑排序 | 代码短小直观 | 深图会 `RecursionError`；工业引擎用依赖计数 + 任务队列 |
| `sub`、`div`、`neg` 由原子运算组合 | 少写反向代码，梯度自动正确 | 多出中间节点；常用运算在框架中有融合实现 |
| `__pow__` 只支持常数指数 | 覆盖 `x²`、`x⁻¹` 等常见需求 | `x ** y`（y 也是变量）需要额外的 `y·ln x` 梯度 |
| relu 在 0 处导数取 0 | 简单的次梯度约定 | 与 PyTorch 的约定一致 |
| demo 中用 `assert` | demo 即测试，结果错立刻报错 | 生产中用 pytest 组织测试 |
| PyTorch 可选 | 无依赖也能运行 | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数（不可变） | `children=(), op=''` | 用元组/字符串做默认值，避免可变默认参数共享的问题 |
| `_` 前缀命名 | `self._backward`、`self._prev` | 约定为"内部使用" |
| `lambda` | `self._backward = lambda: None` | 什么都不做的占位函数 |
| `set` | `set(children)`、`visited = set()` | 去重、O(1) 成员判断；对象默认按身份哈希 |
| 条件表达式 | `other if isinstance(other, Value) else Value(other)` | 一行 if-else |
| 嵌套函数与闭包 | `def _backward(): self.grad += out.grad` | 内部函数捕获外层变量，稍后执行时仍可使用 |
| 函数是对象 | `out._backward = _backward` | 把函数赋给属性，之后用 `v._backward()` 调用 |
| 运算符重载 | `__add__`、`__mul__`、`__pow__`、`__neg__`、`__sub__`、`__truediv__` | 让 `+ * ** - /` 作用于 `Value` |
| 反射运算符 | `__radd__`、`__rmul__`、`__rsub__` | 处理 `2 + x`、`3 * x`、`5 - x`（左操作数是数字） |
| `__call__` | `Neuron.__call__`、`MLP.__call__` | 让实例可以像函数一样调用 |
| `__repr__` | `f"Value(data={self.data:.4f}, grad={self.grad:.4f})"` | 控制打印格式 |
| 递归 | `build_topo(child)` | 函数调用自身；受递归深度上限约束 |
| `reversed` | `for v in reversed(topo)` | 逆序迭代，不复制列表 |
| `sum` 的起始值 | `sum((wi * xi for ...), self.b)` | 第二个参数指定从哪里开始累加 |
| 生成器表达式 | `(wi * xi for wi, xi in zip(self.w, x))` | 惰性计算，作为 `sum` 的参数 |
| 双层列表推导 | `[p for n in self.neurons for p in n.parameters()]` | 把嵌套列表摊平 |
| 列表拼接 | `self.w + [self.b]` | 两个列表相加得到新列表 |
| 增量赋值 | `p.data -= lr * p.grad`、`self.grad += ...` | 原地修改数值属性 |
| `assert` | `assert abs(x1.grad - 3.0) < 1e-6` | 条件不成立就抛 `AssertionError` |
| `try / except ImportError` | `demo_verify_pytorch` | 可选依赖缺失时优雅跳过 |
| f-string 格式 | `{loss.data:.4f}`、`{y:+.0f}`、`{diff:12.2e}`、`{name:<22}` | `+` 强制显示正负号；`e` 科学计数法；`<` 左对齐 |
| `random.seed` / `random.uniform` | `random.seed(42)` | 固定随机种子保证可复现 |

---

## 6. 运行结果解读

在临时副本中实际运行 `python3 autodiff.py`，输出如下（节选）：

```text
=== Basic: y = relu(x1 * x2 + 1) ===
  y  = 7.0
  dy/dx1 = 3.0  (expected 3.0 = x2)
  dy/dx2 = 2.0  (expected 2.0 = x1)
  PASSED

=== Power: y = x^3, dy/dx at x=2 ===
  dy/dx = 12.0  (expected 12.0 = 3*x^2)     ← 讲义练习 1

=== Complex: f = relu(a*b + c) ===
  f = 4.0  (expected 4.0)
  df/da = -3.0  (expected -3.0 = b)
  df/db = 2.0  (expected 2.0 = a)
  df/dc = 1.0  (expected 1.0)
```

乘法节点"交换相乘"、加法节点"原样分发"的规律一目了然。

```text
=== Single neuron: y = relu(w1*x1 + w2*x2 + b) ===
  pre_act = -1.4
  y = 0.0
  dy/dw1 = 0.0
  ...
  PASSED (relu inactive, all grads zero)
```

预激活为负，ReLU 关闭，所有梯度为 0（见 3.6）。

```text
=== Gradient Checking ===
  Expression                 Autodiff    Numerical         Diff
  x^3 + 2x + 1             2.75000000   2.75000000     1.17e-09  OK
  tanh(x^2)                0.94001485   0.94001485     2.07e-10  OK
  (x+1) / (x^2+1)         -0.16000000  -0.16000000     1.03e-09  OK
  exp(x) * x               2.47308191   2.47308191     1.21e-10  OK
  log(x^2 + 1)             0.80000000   0.80000000     5.50e-10  OK
  ALL CHECKS PASSED
```

- 验证一行：`x³ + 2x + 1` 的导数 `3x² + 2` 在 0.5 处为 `0.75 + 2 = 2.75` ✔；`log(x²+1)` 的导数 `2x/(x²+1) = 1/1.25 = 0.8` ✔。
- 差值在 1e-9～1e-10，主要来自数值差分的舍入误差，autodiff 本身是精确的（到机器精度）。

```text
=== Mini MLP Training on XOR ===
  step   0  loss = 4.1491
  step  20  loss = 2.9166
  step  40  loss = 1.4733
  step  60  loss = 0.6011
  step  80  loss = 0.2936
  step  99  loss = 0.1783

  Predictions after training:
    input=[0,0]  target=-1  pred=-0.853 (-)
    input=[0,1]  target=+1  pred=+0.771 (+)
    input=[1,0]  target=+1  pred=+0.801 (+)
    input=[1,1]  target=-1  pred=-0.753 (-)
```

- 初始 loss ≈ 4.15：4 个样本、每个误差约为 1（预测接近 0，目标 ±1），平方和约为 4。
- 100 步后 loss 降到 0.178，4 个预测的**符号全部正确**，网络学会了 XOR。数值离 ±1 还有距离，多训练几步会更接近。

```text
=== Verify against PyTorch ===
  PyTorch not installed, skipping verification.

All demos passed.
```

本次运行环境未安装 PyTorch，所以对拍被跳过（**未实际运行此部分**）。按讲义，装了 PyTorch 时应打印两边的梯度都是 `3.0, 2.0` 并输出 `MATCH`。

---

## 7. 动手改一改

1. **激活状态的单神经元**（讲义练习 3）：把 `demo_neuron` 的 `b` 改成 `2.0`（预激活变为 0.5），确认 5 个梯度分别等于 `x1, x2, w1, w2, 1`。
2. **验证 tanh 导数**（讲义练习 2）：对 `Value(0.0).tanh()` 和 `Value(2.0).tanh()` 反向传播，确认梯度为 1 和约 0.0707。
3. **补齐运算**：实现 `__rtruediv__` 和 `sigmoid`，并用 `gradient_check` 验证（参考测验 Q11）。
4. **对偶数前向模式**（讲义练习 4）：写一个 `Dual(value, deriv)` 类，实现 `+ * ** tanh`，对 `x³ + 2x + 1` 在 0.5 处求导，与 `gradient_check` 里的 2.75 对比。
5. **非递归拓扑排序**：用显式栈改写 `build_topo`，让"对 5000 个 `Value` 求和"这类 5000 层深的图也能反向传播（参考测验 Q12）。
6. **观察"忘记清零"**：删掉训练循环里的清零两行，打印每 20 步的 loss 和 `max(abs(p.data) for p in model.parameters())`，再把 lr 改成 0.2 对比（参考测验 Q10）。

---

## 8. 常见坑

- **用 `=` 代替 `+=` 累加梯度**：变量只用一次时测不出来，一旦被复用（残差、权重共享）梯度就错了。
- **忘记清零梯度**：梯度跨步累加，相当于不衰减的动量；loss 可能看起来下降，但参数会无界增长。
- **重复调用 `backward()`**：本引擎不会自动清零，第二次调用会把所有梯度再加一遍。
- **自己重写 `__eq__`**：会改变哈希/集合行为，使不同节点被误判为同一节点，拓扑排序出错。
- **在 `Value` 运算里更新参数**：如果写成 `p = p - lr * p.grad`，会创建新节点并把更新过程也记进计算图；应像代码那样直接修改 `p.data`。
- **深图递归溢出**：长链式求和或展开很多步的循环网络会触发 `RecursionError`。
- **定义域问题**：`log` 输入必须为正、`x ** -1` 输入不能为 0，前向阶段就会抛异常。
