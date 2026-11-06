# 代码讲解 · main.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 10 节 构建您自己的迷你框架 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，纯 CPU 约 30 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`），不用 NumPy

---

## 1. 这份代码在考察什么

这是阶段 03 的"收官作业"：把前 9 节散落在各处的零件（神经元、反向传播、激活函数、损失、优化器、正则化、初始化）**组装成一个可复用的框架**。它要你搞懂的不是某个公式，而是"框架的骨架"：

1. **统一接口的威力**：所有层都是 `Module`，都有 `forward / backward / parameters / train / eval`，于是可以像积木一样任意组合。
2. **反向传播的工程实现**：每层在 forward 时缓存什么、backward 时返回什么、梯度为什么要**累加**（`+=`）。
3. **训练/评估模式**：为什么 Dropout、BatchNorm 需要一个 `training` 开关，以及 `Sequential` 怎样把开关递归传下去。
4. **职责分离**：损失只管算 loss 和 `∂L/∂pred`；优化器只看一张扁平的参数表；DataLoader 只管打乱和切批——三者互不知道对方的内部结构。
5. **与 PyTorch 的映射**：写完之后，`nn.Sequential(...)`、`optimizer.zero_grad()`、`model.eval()` 每一行背后发生了什么，你都能讲出来。

> 一句话：**PyTorch 不是魔法，而是一套组织代码的模式**——这份 600 行的纯 Python 就是它的骨架，只是缺了 autograd、张量和 GPU。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 / PyTorch 对应物 |
|---------|------|------|---------------|
| `Module` | 基类 | 定义 `forward/backward/parameters/train/eval` 接口和 `training` 标志 | `nn.Module` |
| `Linear` | Module | `y = Wx + b`，He 初始化，缓存输入，累加梯度 | `nn.Linear` |
| `ReLU` / `Sigmoid` / `Tanh` | Module | 激活函数，缓存掩码或输出给 backward 用 | `nn.ReLU` 等 |
| `Dropout` | Module | 训练时随机置零并放大 `1/(1-p)`，评估时恒等 | `nn.Dropout` |
| `BatchNorm` | Module | 标准化 + `γ/β` 仿射，维护 running 统计量（⚠️ 简化版） | `nn.BatchNorm1d` |
| `Sequential` | 容器 Module | 正序 forward、逆序 backward、汇总参数、递归切换模式 | `nn.Sequential` |
| `MSELoss` / `BCELoss` | 可调用类 | `__call__` 算 loss 并缓存，`backward()` 返回 `∂L/∂pred` | `nn.MSELoss` / `nn.BCELoss` |
| `SGD` / `Adam` | 优化器 | `step()` 更新参数，`zero_grad()` 清零梯度 | `torch.optim.SGD/Adam` |
| `DataLoader` | 可迭代类 | 打乱 + 切批，`yield (inputs, targets)` | `torch.utils.data.DataLoader` |
| `make_circle_data` | 函数 | 生成 500 个二维点，圆内（`x²+y²<1.5`）为 1 | 玩具数据集 |
| `train_framework` / `train_with_sgd` / `train_with_dropout` | 函数 | 三组对照实验：Adam、SGD、Adam+Dropout | 训练循环 |
| `sample_predictions` | 函数 | 对 8 个手选点打印预测 | 推理演示 |

数据流：`DataLoader` 产出批次 → 训练循环逐样本调用 `model.forward(x)` → `criterion(pred, t)` 算 loss → `optimizer.zero_grad()` → `criterion.backward()` 得到 `∂L/∂pred` → `model.backward(grad)` 逆序穿过各层并把梯度累加进各层的 `*_grads` → `optimizer.step()` 通过参数四元组原地修改权重。

---

## 3. 逐段精讲

### 3.1 `Module`：所有层共同的"合同"

```python
class Module:
    def __init__(self):
        self.training = True

    def forward(self, x):
        raise NotImplementedError

    def backward(self, grad):
        raise NotImplementedError

    def parameters(self):
        return []

    def train(self):
        self.training = True

    def eval(self):
        self.training = False
```

- `forward/backward` 抛 `NotImplementedError`：这是"抽象方法"的轻量写法——子类必须覆盖，否则一调用就报错，提醒你漏实现了。
- `parameters()` 默认返回空列表：ReLU、Sigmoid 这类**无参数层**直接继承即可，`Sequential` 汇总参数时不用做特殊判断。
- `training` 默认 `True`，与 PyTorch 一致：新建的模型处于训练模式。
- ⚠️ 与 PyTorch 的差别：PyTorch 的 `nn.Module` 只要求你写 `forward`，`backward` 由 autograd 自动生成；这里每层都要手写 `backward`。

### 3.2 `Linear`：初始化、前向、反向、参数表

```python
class Linear(Module):
    def __init__(self, fan_in, fan_out):
        super().__init__()
        std = math.sqrt(2.0 / fan_in)
        self.weights = [[random.gauss(0, std) for _ in range(fan_in)] for _ in range(fan_out)]
        self.biases = [0.0] * fan_out
        self.weight_grads = [[0.0] * fan_in for _ in range(fan_out)]
        self.bias_grads = [0.0] * fan_out
        # ...
        self.input = None
```

- `std = √(2/fan_in)` 是 **He（Kaiming）初始化**，专为 ReLU 设计：ReLU 砍掉一半输出，方差减半，乘 2 补回来，保证信号逐层传递时方差大致不变（第 08 节）。
- 权重形状是 `fan_out × fan_in`（每行对应一个输出神经元），与 PyTorch `nn.Linear.weight` 的 `[out_features, in_features]` 一致。
- 偏置初始化为 0 是常规做法。
- `super().__init__()` 一定要调用，否则 `self.training` 不存在，`Dropout` 之类的判断会 `AttributeError`。

```python
    def forward(self, x):
        self.input = x
        output = []
        for i in range(self.fan_out):
            val = self.biases[i]
            for j in range(self.fan_in):
                val += self.weights[i][j] * x[j]
            output.append(val)
        return output

    def backward(self, grad):
        input_grad = [0.0] * self.fan_in
        for i in range(self.fan_out):
            self.bias_grads[i] += grad[i]
            for j in range(self.fan_in):
                self.weight_grads[i][j] += grad[i] * self.input[j]
                input_grad[j] += grad[i] * self.weights[i][j]
        return input_grad
```

这是整个框架里最重要的 10 行，三条公式全在里面（g 为上游传来的 `∂L/∂y`）：

| 代码 | 公式 | 含义 |
|------|------|------|
| `bias_grads[i] += grad[i]` | `∂L/∂bᵢ = gᵢ` | 偏置的梯度就是上游梯度 |
| `weight_grads[i][j] += grad[i] * self.input[j]` | `∂L/∂Wᵢⱼ = gᵢ·xⱼ`（即 `g·xᵀ`） | 需要 forward 时缓存的输入 x |
| `input_grad[j] += grad[i] * self.weights[i][j]` | `∂L/∂xⱼ = Σᵢ Wᵢⱼ·gᵢ`（即 `Wᵀg`） | 返回给上一层继续传 |

- **为什么 forward 要缓存 `self.input`**：权重梯度需要输入值。这就是训练时"激活值占显存"的根源——推理不需要缓存。
- **为什么用 `+=`**：梯度是**累加**到 `weight_grads` 上的，所以优化器必须在每次 backward 前 `zero_grad()`。反过来，这也使"多次 backward、一次 step"的梯度累积成为可能（讲义练习 5）。
- `input_grad` 在每次 backward 时新建，所以它本身不需要清零。

```python
    def parameters(self):
        params = []
        for i in range(self.fan_out):
            for j in range(self.fan_in):
                params.append((self.weights, i, j, self.weight_grads))
            params.append((self.biases, i, None, self.bias_grads))
        return params
```

- 每个**标量参数**对应一个四元组 `(容器, 行, 列, 梯度容器)`。二维权重用 `[i][j]` 定位，一维偏置用 `j=None` 标记。
- 关键在于：元组里存的是**列表对象的引用**，不是数值的拷贝。优化器执行 `container[i][j] -= ...` 时，改的就是 `Linear` 内部那份 `self.weights`。
- ⚠️ 简化：PyTorch 中一个参数是一整个张量（`weight` 是一个 `Parameter`），优化器以张量为单位做向量化更新；这里拆成了一个个标量，所以慢得多。

### 3.3 激活模块：各自缓存"backward 需要的最少信息"

```python
class ReLU(Module):
    def forward(self, x):
        self.mask = [1.0 if v > 0 else 0.0 for v in x]
        return [max(0.0, v) for v in x]

    def backward(self, grad):
        return [g * m for g, m in zip(grad, self.mask)]


class Sigmoid(Module):
    def forward(self, x):
        self.output = []
        for v in x:
            v = max(-500, min(500, v))
            self.output.append(1.0 / (1.0 + math.exp(-v)))
        return self.output

    def backward(self, grad):
        return [g * o * (1 - o) for g, o in zip(grad, self.output)]
```

- ReLU 的导数是 0 或 1，所以缓存一个 0/1 掩码就够了；`v > 0` 时为 1，`v == 0` 时取 0（次梯度的一种约定，PyTorch 也取 0）。
- Sigmoid 导数 `σ'(z) = σ(z)(1-σ(z))`，只依赖**输出**，所以缓存输出而不是输入，backward 不用再算一次 `exp`。Tanh 同理：`1 - tanh²(z)`。
- `max(-500, min(500, v))`：`math.exp(-v)` 在 `-v > 709` 左右会抛 `OverflowError`。夹紧到 ±500 后，`exp(500) ≈ 1.4e217` 仍在 float 范围内，输出被正确算成接近 0 或 1。
- ⚠️ 注意 `Sigmoid.forward` 返回的就是 `self.output` 这个列表本身。外部如果原地修改返回值，会把缓存一起改掉。本代码没有这样做，但写框架时要警惕这种"别名（aliasing）"问题。

### 3.4 `Dropout`：inverted dropout 与 `training` 开关

```python
class Dropout(Module):
    def forward(self, x):
        if not self.training:
            return x
        self.mask = [0.0 if random.random() < self.p else 1.0 / (1 - self.p) for _ in x]
        return [v * m for v, m in zip(x, self.mask)]

    def backward(self, grad):
        if self.mask is None:
            return grad
        return [g * m for g, m in zip(grad, self.mask)]
```

- 以概率 p 置零，其余乘 `1/(1-p)`：这样每个元素的期望不变（`(1-p)·x/(1-p) = x`），评估时直接 `return x` 即可，不用再缩放——这就是 **inverted dropout**，PyTorch 也这么做。
- 掩码里直接存缩放后的值（0 或 `1/(1-p)`），backward 乘同一个掩码：被丢弃的神经元梯度为 0，保留的梯度同样被放大。
- `if not self.training: return x` 是 train/eval 模式存在的根本原因之一。
- ⚠️ 小瑕疵：切到 eval 后 `self.mask` 仍保留着最后一次训练的掩码，如果在 eval 模式下调用 `backward`，会用到过期掩码。本代码 eval 时不做 backward，所以不触发。

### 3.5 `BatchNorm`：有两套 forward，且都是简化版（⚠️ 重点）

```python
    def forward_batch(self, batch):
        # ...
        if self.training:
            # 逐特征计算 batch 均值 mean[j]、方差 var[j]
            self.std_inv = [1.0 / math.sqrt(v + self.eps) for v in var]
            # x_norm = (x - mean) * std_inv；output = gamma * x_norm + beta
            # running_mean / running_var 做指数滑动平均
        else:
            # 用 running_mean / running_var 标准化
```

`forward_batch` 是**教科书式的 BN 前向**：训练时用当前 batch 的均值方差标准化，同时用动量 0.1 更新 running 统计量；评估时用 running 统计量。这与讲义的描述一致。

但框架里所有层都是**单样本**处理的，`Sequential.forward` 实际调用的是下面这个 `forward`：

```python
    def forward(self, x):
        if self.training:
            for j in range(self.size):
                self.running_mean[j] = (1 - self.momentum) * self.running_mean[j] + self.momentum * x[j]

            self.std_inv = [1.0 / math.sqrt(v + self.eps) for v in self.running_var]
            self.x_norm = [(x[j] - self.running_mean[j]) * self.std_inv[j] for j in range(self.size)]
            return [self.gamma[j] * self.x_norm[j] + self.beta[j] for j in range(self.size)]
        else:
            # 用 running 统计量标准化
```

- 单个样本无法计算有意义的 batch 方差（只有一个样本时方差为 0，标准化后全是 0）。讲义版的 `forward` 直接调用 `forward_batch([x])`，就会遇到这个问题；代码版换成了"用滑动平均当均值、用 `running_var` 当方差"的折中方案。
- ⚠️ 问题：在这条路径里 `running_var` **从来不会被更新**，始终是 1.0，所以并没有真正"除以标准差"。实测 `BatchNorm(2).forward([3.0, -1.0])` 输出约 `[2.70, -0.90]`（只减去了 `0.1·x` 的滑动均值）。
- ⚠️ `backward` 也只做了 `grad · γ · std_inv`，把均值、方差当常数，忽略了它们对 x 的依赖。完整 BN 的反向（N 为 batch 大小，`dx̂ = dy·γ`）是 `dx = (std_inv / N) · (N·dx̂ - Σdx̂ - x̂·Σ(dx̂·x̂))`。
- `backward` 中 `self.x_norm if not isinstance(self.x_norm[0], list) else self.x_norm[0]` 是为了兼容两套 forward 留下的不同形状缓存：走过 `forward_batch` 时只取第一个样本，同样是简化。
- 好在本文件的 3 个实验**都没有用到 BatchNorm**，它只是"框架里有这个组件"的展示。真正的 BN 需要整个框架以 `[batch, features]` 为单位前向/反向——PyTorch 所有层都约定第 0 维是 batch，原因就在这里。

### 3.6 `Sequential`：组合模式的教科书实现

```python
class Sequential(Module):
    def __init__(self, *modules):
        super().__init__()
        self.modules = list(modules)

    def forward(self, x):
        for module in self.modules:
            x = module.forward(x)
        return x

    def backward(self, grad):
        for module in reversed(self.modules):
            grad = module.backward(grad)
        return grad

    def parameters(self):
        params = []
        for module in self.modules:
            params.extend(module.parameters())
        return params

    def train(self):
        self.training = True
        for module in self.modules:
            module.train()
    # eval() 对称
```

- `*modules` 让你写 `Sequential(Linear(2,16), ReLU(), ...)`，不用先套一层列表。
- forward 正序，backward 用 `reversed()` 逆序——链式法则要求梯度从 loss 一端往输入一端传。
- `train()/eval()` **必须覆盖并递归**：基类版本只改自己的 `training`，不会影响子模块里的 Dropout。PyTorch 的 `nn.Module.train()` 同样是递归遍历所有子模块。
- `count_parameters()` 返回 `len(self.parameters())`，因为每个四元组就是一个标量参数，所以得到的是标量参数总数（本网络为 465）。
- 由于 `Sequential` 本身是 `Module`，它可以嵌套进另一个 `Sequential`——这就是组合模式（composite pattern）。

### 3.7 损失函数：`__call__` 前向 + `backward()` 反向

```python
class BCELoss:
    def __call__(self, predicted, target):
        self.predicted = predicted
        self.target = target
        eps = 1e-7
        n = len(predicted)
        self.loss = 0
        for p, t in zip(predicted, target):
            p = max(eps, min(1 - eps, p))
            self.loss += -(t * math.log(p) + (1 - t) * math.log(1 - p))
        self.loss /= n
        return self.loss

    def backward(self):
        # ...
            grads.append((-t / p + (1 - t) / (1 - p)) / n)
        return grads
```

- 实现了 `__call__`，所以可以写 `criterion(pred, t)`，和 PyTorch 的用法一样。
- 计算时**缓存**预测和目标，`backward()` 不带参数就能算梯度——这是"有状态的损失对象"。
- 把 p 夹到 `[1e-7, 1-1e-7]`：防止 `log(0)` 和 backward 里除以 0。
- BCE 梯度 `(-t/p + (1-t)/(1-p))/n` 再乘上 Sigmoid 的 `p(1-p)`，化简后正好是 `(p - t)/n`。这里 n=1（单输出），所以送进最后一个 Linear 的梯度就是 `p - t`，简洁而稳定。
- `MSELoss` 同理：loss 为 `Σ(p-t)²/n`，梯度为 `2(p-t)/n`。本文件没有用到它。
- ⚠️ 生产中更推荐 `BCEWithLogitsLoss`：直接接收 logits，用 log-sum-exp 技巧避免先算 p 再取 log 带来的精度损失，也不需要这些 clamp。

### 3.8 `SGD` 与 `Adam`：只认参数四元组

```python
class Adam:
    def __init__(self, parameters, lr=0.001, beta1=0.9, beta2=0.999, eps=1e-8):
        self.params = parameters
        # ...
        self.t = 0
        self.m = [0.0] * len(parameters)
        self.v = [0.0] * len(parameters)

    def step(self):
        self.t += 1
        for idx, (container, i, j, grad_container) in enumerate(self.params):
            if j is not None:
                g = grad_container[i][j]
            else:
                g = grad_container[i]

            self.m[idx] = self.beta1 * self.m[idx] + (1 - self.beta1) * g
            self.v[idx] = self.beta2 * self.v[idx] + (1 - self.beta2) * g * g

            m_hat = self.m[idx] / (1 - self.beta1 ** self.t)
            v_hat = self.v[idx] / (1 - self.beta2 ** self.t)

            update = self.lr * m_hat / (math.sqrt(v_hat) + self.eps)
            # 按 j 是否为 None 写回 container
```

- **优化器不知道网络结构**：它只拿到 `model.parameters()` 返回的扁平列表，按下标 `idx` 为每个标量维护一份 `m`、`v`。这和 PyTorch 的 `optimizer.state[param]` 本质相同。
- `m`：梯度的指数滑动平均（一阶矩，动量）；`v`：梯度平方的滑动平均（二阶矩，用于自适应缩放步长）。
- **偏差修正**：m、v 从 0 起步，前几步会偏小；除以 `1 - β^t` 修正。`t` 在 `step()` 开头自增，所以第一步 t=1，不会除以 0。
- 更新量 `lr · m_hat / (√v_hat + eps)`：梯度大的参数步子被压小，梯度小的被放大，每个参数有"自己的学习率"。
- `SGD.step` 只有一行：`container[i][j] -= self.lr * grad_container[i][j]`。
- `zero_grad()` 两个类各写了一份，逻辑完全相同（遍历四元组置 0）。工程上会抽到一个 `Optimizer` 基类，PyTorch 正是如此（`torch.optim.Optimizer`）。
- ⚠️ 约束：`Adam` 构造时就固定了 `len(parameters)`，之后如果模型结构变化（比如冻结或新增层），m、v 的下标就对不上了。

### 3.9 `DataLoader`：生成器实现的批迭代器

```python
class DataLoader:
    def __iter__(self):
        indices = list(range(len(self.data)))
        if self.shuffle:
            random.shuffle(indices)
        for start in range(0, len(indices), self.batch_size):
            batch_indices = indices[start:start + self.batch_size]
            batch = [self.data[i] for i in batch_indices]
            inputs = [item[0] for item in batch]
            targets = [item[1] for item in batch]
            yield inputs, targets

    def __len__(self):
        return (len(self.data) + self.batch_size - 1) // self.batch_size
```

- `__iter__` 里用了 `yield`，所以它是一个**生成器函数**：每次 `for batch_inputs, batch_targets in loader:` 都会重新执行 `__iter__`，于是**每个 epoch 都重新打乱一次**。
- 打乱的是下标而不是数据本身，原始 `train_data` 不被修改。
- `__len__` 用 `(N + B - 1) // B` 实现向上取整：400 个样本、batch 16 → 25 批；最后一批不满时也会保留（PyTorch 中对应 `drop_last=False`）。
- 把 `(x, y)` 对"转置"成 `inputs` 列表和 `targets` 列表，相当于 PyTorch 的默认 `collate_fn`。

### 3.10 训练循环 `train_framework()`：注意它其实是逐样本更新

```python
    for epoch in range(100):
        # ...
        for batch_inputs, batch_targets in loader:
            for x, t in zip(batch_inputs, batch_targets):
                pred = model.forward(x)
                loss = criterion(pred, t)
                total_loss += loss

                optimizer.zero_grad()
                grad = criterion.backward()
                model.backward(grad)
                optimizer.step()

                predicted_class = 1.0 if pred[0] >= 0.5 else 0.0
                # 统计正确数
```

- 顺序是 `forward → loss → zero_grad → backward → step`。`zero_grad` 只要在 backward 之前就行，和 PyTorch 惯用的"先 zero_grad 再 forward"等价。
- ⚠️ **刻意的简化**：每个样本都做一次完整的 `zero_grad → backward → step`，所以实际上是 **batch size = 1** 的随机优化，DataLoader 的 `batch_size=16` 只起到"分组"的作用。原因是框架的层只支持单样本，且每层只缓存最近一次 forward。讲义练习 5 要你把它改成真正的 mini-batch（每批累积梯度、一次 step）。
- 打印的 "Train Accuracy" 用的是**更新前**的预测、且模型处于训练模式，所以它是"边学边考"的滑动指标，不等于训练结束后在训练集上的准确率。
- 训练完 `model.eval()`，再在 100 个测试样本上评估。本网络没有 Dropout/BN，`eval()` 实际不影响结果，但养成习惯很重要。

### 3.11 数据与三组对照实验

```python
def make_circle_data(n=500, seed=42):
    random.seed(seed)
    data = []
    for _ in range(n):
        x = random.uniform(-2, 2)
        y = random.uniform(-2, 2)
        label = 1.0 if x * x + y * y < 1.5 else 0.0
        data.append(([x, y], [label]))
    return data
```

- 在 `[-2,2]²` 方形内均匀撒点，落在半径 `√1.5 ≈ 1.22` 的圆内为正类。这是一个**非线性可分**问题，单层感知器做不到，需要多层 + 非线性激活。
- 每个训练函数开头 `random.seed(42)` 再建模型，`make_circle_data` 内部又 `random.seed(42)`。结果是：三个实验的**初始权重相同**（Dropout 的构造不消耗随机数）、**数据相同**，对比只差在优化器和 Dropout 上，是一个公平的对照设计。
- `train_with_sgd` 用 `lr=0.1`（SGD 通常需要比 Adam 大的学习率），`train_with_dropout` 在前两个隐藏层后加 `Dropout(0.3)`。
- `sample_predictions(model, data)` 的第二个参数 `data` 没有被使用（调用时传 `None`），属于无害的遗留参数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表，不用 NumPy | 每一次乘加都看得见，便于理解 | 比 NumPy/PyTorch 慢几个数量级；生产中用张量 + 向量化 + GPU |
| 每层手写 `backward` | 强迫你理解每层的局部梯度 | PyTorch 用 autograd 自动生成，支持任意计算图 |
| 梯度用 `+=` 累加，`zero_grad` 单独调用 | 支持梯度累积，接口与 PyTorch 一致 | 忘记 `zero_grad` 会导致梯度越积越大（经典 bug） |
| 参数用 `(container, i, j, grad)` 四元组 | 优化器与网络结构完全解耦 | 标量级更新很慢；PyTorch 以整个张量为单位 |
| 单样本前向/反向 | 代码最简单，不用处理批维度 | 无法实现真正的 BatchNorm，也无法向量化；生产中第 0 维是 batch |
| 训练循环逐样本 `step` | 与单样本层配套 | DataLoader 的 batch 形同虚设；应改为批内梯度平均后一次 step |
| Sigmoid 输出 + BCELoss，配合 clamp | 概念清晰，与讲义一一对应 | 生产中用 `BCEWithLogitsLoss` 融合，数值更稳定 |
| He 初始化 `√(2/fan_in)` | 适配 ReLU，保持方差稳定 | 最后一层接 Sigmoid 时也用了 He，可接受；PyTorch `nn.Linear` 默认是 Kaiming-uniform 变体 |
| BatchNorm 简化前向/反向 | 展示 running 统计量与 train/eval 的区别 | 不是真正的 BN；需要批输入和完整反向公式 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类与继承 | `class Linear(Module):` | 子类自动拥有父类的方法，可以覆盖（override） |
| `super().__init__()` | `Linear.__init__` 第一行 | 调用父类构造函数，初始化 `self.training` |
| `raise NotImplementedError` | `Module.forward` | 表示"子类必须实现"，是抽象方法的简易写法 |
| 条件表达式（三元） | `1.0 if v > 0 else 0.0` | 一行内的 if/else，返回一个值 |
| 列表推导 / 嵌套列表推导 | `[[random.gauss(0, std) for _ in range(fan_in)] for _ in range(fan_out)]` | 生成二维列表；`_` 表示"这个循环变量我不用" |
| `[0.0] * n` vs 推导式 | `self.biases = [0.0] * fan_out`；二维用 `[[0.0] * fan_in for _ in range(fan_out)]` | 一维用乘法没问题；二维**不能**写 `[[0.0]*n]*m`，那样 m 行是同一个列表对象 |
| `zip` | `zip(grad, self.mask)` | 按位置配对多个序列 |
| `reversed()` | `for module in reversed(self.modules)` | 逆序迭代，不复制列表 |
| `*args` 可变参数 | `def __init__(self, *modules)` | 把任意个位置参数收成一个元组 |
| `list.extend` | `params.extend(module.parameters())` | 把另一个列表的元素逐个追加 |
| for 循环中的元组解包 | `for container, i, j, grad_container in self.params:` | 每个元素是四元组，直接拆成 4 个变量 |
| `enumerate` + 嵌套解包 | `for idx, (container, i, j, grad_container) in enumerate(self.params):` | 同时拿到下标和四元组内容，注意括号 |
| `is not None` | `if j is not None:` | 判断 None 要用 `is`，不要用 `==` |
| `isinstance` | `isinstance(self.x_norm[0], list)` | 运行时判断类型 |
| `__call__` | `BCELoss.__call__` | 让对象可以像函数一样被调用：`criterion(pred, t)` |
| `__iter__` + `yield`（生成器） | `DataLoader.__iter__` | 让对象可被 `for` 遍历；`yield` 每次产出一批，按需计算 |
| `__len__` | `DataLoader.__len__` | 让 `len(loader)` 可用 |
| 整除 `//` | `(len(self.data) + self.batch_size - 1) // self.batch_size` | 向下取整的除法；加 `B-1` 实现向上取整 |
| 可变对象的引用语义 | 四元组里存 `self.weights` | 列表按引用传递，优化器原地修改即影响模型 |
| `random` 模块 | `random.seed`、`random.gauss`、`random.uniform`、`random.random`、`random.shuffle` | 固定种子、高斯采样、均匀采样、[0,1) 随机数、原地打乱 |
| `math` 模块 | `math.sqrt`、`math.exp`、`math.log`、`math.tanh` | 标量数学函数（不支持列表，所以要逐元素循环） |
| f-string 格式符 | `f"{epoch:3d}"`、`f"{avg_loss:.6f}"`、`f"{point[0]:5.1f}"`、`f"{predicted_region:7s}"` | `3d` 宽 3 的整数；`.6f` 6 位小数；`5.1f` 宽 5、1 位小数；`7s` 宽 7 的字符串（左对齐） |
| 字符串乘法 | `"=" * 70` | 重复字符串，用来画分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行实验，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（`timeout 60 python3 main.py`，约 31 秒）的关键输出：

```text
Model: 4 linear layers (2->16->16->8->1)
Total parameters: 465                              ← 48 + 272 + 136 + 9

  Epoch   0 | Loss: 0.445426 | Train Accuracy: 77.0%   ← 第一个 epoch 就学到大半
  Epoch  10 | Loss: 0.092734 | Train Accuracy: 96.5%
  Epoch  60 | Loss: 0.031912 | Train Accuracy: 99.0%
  Epoch  90 | Loss: 0.098226 | Train Accuracy: 97.5%   ← loss 反弹：batch=1 + lr=0.01 的噪声
  Epoch  99 | Loss: 0.078514 | Train Accuracy: 97.8%

  Test Accuracy: 94.0% (94/100)

  Sample Predictions:
    (  0.0,   0.0) -> 0.9999 (inside , expected inside ) OK
    (  1.0,   0.0) -> 0.9999 (inside , expected inside ) OK   ← 1² = 1 < 1.5，在圆内
    (  1.5,   1.5) -> 0.0000 (outside, expected outside) OK
    (  2.0,   0.0) -> 0.0000 (outside, expected outside) OK

  SGD Test Accuracy: 95.0%
  Dropout Test Accuracy: 98.0%

COMPARISON
  Adam (no dropout):     94.0%
  SGD (no dropout):      95.0%
  Adam + Dropout(0.3):   98.0%
```

逐条解读：

- **465 个参数**：与手算一致，说明 `parameters()` 的四元组恰好一一覆盖了所有权重和偏置。
- **loss 不是单调下降**：epoch 60 的 0.032 到 epoch 90 又回到 0.098。原因是每个样本更新一次（batch=1）且 Adam 学习率 0.01 偏大，更新噪声很大。这也是讲义练习 2（学习率调度）和练习 5（真正的 mini-batch）的动机。
- **训练 97.8% vs 测试 94.0%**：有一定泛化差距。测试集只有 100 个样本，每错 1 个就差 1 个百分点。
- **样例预测都是 0.9999 / 0.0000**：远离边界的点模型非常"自信"。真正难的是圆边界附近（半径约 1.22）的点，测试集上的错误基本都在那里。
- **三组对比**：Dropout 版本最高（98%），SGD 与 Adam 相当。但要谨慎解读：只有一个随机种子、测试集 100 个样本，1–4 个百分点的差异在噪声范围内。要下结论，应多跑几个种子取均值和方差。

---

## 7. 动手改一改

1. **数值梯度检查**：对 `Linear(2, 1)` 任选一个权重 `w`，用 `(L(w+1e-5) - L(w-1e-5)) / 2e-5` 计算数值梯度，与 `weight_grads` 对比，相对误差应小于 `1e-6`。
2. **抽出优化器基类**：写一个 `Optimizer` 基类，把 `zero_grad()` 和"按 j 读写参数"的逻辑放进去，`SGD`、`Adam` 继承它，消除重复代码。
3. **真正的 mini-batch（讲义练习 5）**：每个 batch 只 `zero_grad` 一次、`step` 一次，梯度除以 `len(batch_inputs)`。对比 100 个 epoch 后的测试准确率和 loss 曲线的平滑程度。
4. **加 `set_lr()` 并接入余弦调度（讲义练习 2）**：warmup 5 个 epoch，然后余弦衰减到 0，观察 epoch 60 之后 loss 反弹的现象是否消失。
5. **Adam 加 weight decay（讲义练习 4）**：分别实现"L2 加到梯度里"（`g += wd * w`）和"AdamW 解耦衰减"（`w -= lr * wd * w`），比较两者对权重范数的影响。
6. **`save()/load()`（讲义练习 3）**：用 `json` 把每个 `Linear` 的 `weights`、`biases` 存成文件，再加载到新模型，验证 `sample_predictions` 输出完全一致。

---

## 8. 常见坑

- **忘记 `optimizer.zero_grad()`**：`Linear.backward` 用 `+=`，梯度会跨样本越积越大，loss 先降后炸。顺序上只要保证 zero_grad 在本次 backward 之前（或上一次 step 之后）即可，绝不能放在 backward 和 step 之间。
- **自定义容器忘了递归 `train()/eval()`**：只改了容器自己的 `training`，里面的 Dropout 仍处于训练模式，评估结果随机波动。
- **先把整批都 forward 完再 backward**：每层只缓存最近一次 forward 的 `self.input` / `self.mask`，这样做会让前面样本的 backward 用到最后一个样本的缓存，梯度全错。
- **二维列表用 `[[0.0] * n] * m` 初始化**：m 行共享同一个列表对象，改一行等于改所有行。本代码正确地用了列表推导。
- **以为加了 `BatchNorm` 就有批归一化效果**：本框架的单样本 `BatchNorm.forward` 不更新 `running_var`，也不使用批统计量，只是一个演示组件。
- **用单次运行比较优化器优劣**：测试集只有 100 个样本、只有一个种子，94% vs 95% vs 98% 不足以说明哪个方法更好。
