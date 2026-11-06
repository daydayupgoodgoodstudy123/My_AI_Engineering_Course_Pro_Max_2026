# 代码讲解 · main.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 07 节 正则化（Regularization） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 4 秒跑完） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码用纯 Python 实现了本节讲到的几种正则化/归一化"零件"，再把其中两种（dropout、weight decay）装进一个小网络里做对照实验：

1. **Dropout 的两种模式**：训练时随机置零并除以 `1-p`，推理时原样输出；反向传播必须复用同一个 mask。
2. **L2 正则的惩罚项和梯度**：`(λ/2)·Σw²` 和 `λ·w`，以及在 SGD 里它就是 weight decay。
3. **三种归一化的区别**：BatchNorm 沿 batch 维、LayerNorm 和 RMSNorm 沿特征维；RMSNorm 不减均值。
4. **BatchNorm 的训练/推理切换**：running mean/var 如何用 EMA 积累，推理时如何使用。
5. **怎样做（以及怎样不该做）正则化对照实验**：测量方式、数据规模、正则强度都会左右结论——本次实际运行的结果就和代码末尾写死的结论不一致，这本身就是一课。

> 一句话：**正则化的每个零件都只有几行代码，难的是在正确的位置、用正确的强度、以正确的方式评估它。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Dropout` | 类 | `forward`（训练随机置零 + 缩放 / 推理恒等）、`backward`（按 mask 回传） | Inverted dropout |
| `l2_regularization` / `l2_gradient` | 函数 | 计算 `(λ/2)·Σw²` 和 `λ·w` | L2 正则 |
| `BatchNorm` | 类 | 对 batch（二维列表）逐特征归一化，维护 `running_mean/var` | 批归一化 |
| `LayerNorm` | 类 | 对单个样本（一维列表）在特征维归一化 | 层归一化 |
| `RMSNorm` | 类 | 对单个样本除以均方根，无 β | RMS 归一化 |
| `sigmoid`、`make_circle_data` | 函数 | 数值稳定的 sigmoid；圆形二分类数据 | 与上一节相同 |
| `RegularizedNetwork` | 类 | 2→16→1 网络，可选 dropout 与 weight decay，`backward` 里直接做 SGD 更新 | 被正则化的模型 |
| `if __name__ == "__main__":` | 演示入口 | STEP 1–5：dropout、L2、三种归一化、BN 训练/推理、四种配置对照 | — |

调用关系：`RegularizedNetwork` 只用到了 `Dropout`（以及 `sigmoid`），`BatchNorm`/`LayerNorm`/`RMSNorm` 和 `l2_*` 函数只在 STEP 1–4 的独立演示中出现，并没有接入网络。

---

## 3. 逐段精讲

### 3.1 `Dropout.forward`：inverted dropout

```python
class Dropout:
    def __init__(self, p=0.5):
        self.p = p
        self.training = True
        self.mask = None

    def forward(self, x):
        if not self.training:
            return list(x)
        self.mask = []
        output = []
        for val in x:
            if random.random() < self.p:
                self.mask.append(0)
                output.append(0.0)
            else:
                self.mask.append(1)
                output.append(val / (1 - self.p))
        return output
```

- `random.random() < self.p`：`random.random()` 在 [0, 1) 均匀分布，所以这个条件以概率 p 成立，即"以概率 p 丢弃"。mask 中 0 表示丢弃，1 表示保留，等价于讲义的 `mask[i] ~ Bernoulli(1 - p)`。
- 保留的值除以 `1 - p`：期望 `E[out] = (1-p)·val/(1-p) + p·0 = val`。这就是 **inverted dropout**——把缩放挪到训练阶段，推理阶段什么都不用做。
- `self.training` 标志模仿 PyTorch 的 `module.training`，由外部切换（对应 `model.train()` / `model.eval()`）。
- 推理时 `return list(x)` 返回**副本**而非原列表本身，避免调用者修改输出时意外改到输入。
- **mask 必须保存下来**：反向传播要用同一个 mask。这是 dropout 层"有状态"的地方。
- ⚠️ 简化：p=1 时会除以 0；PyTorch 对 p 的合法范围有检查。

### 3.2 `Dropout.backward`：梯度走同一条路

```python
    def backward(self, grad_output):
        grads = []
        for g, m in zip(grad_output, self.mask):
            if m == 0:
                grads.append(0.0)
            else:
                grads.append(g / (1 - self.p))
        return grads
```

- 前向是 `out = val · m / (1-p)`，对 val 求导就是 `m / (1-p)`：被丢弃的位置梯度为 0，保留的位置梯度乘同样的 `1/(1-p)`。
- 注意 `RegularizedNetwork` 并没有调用这个方法，而是在自己的 `backward` 里用列表推导重写了一遍相同逻辑（见 3.8）。

### 3.3 L2 正则：惩罚项与梯度

```python
def l2_regularization(weights, lambda_reg):
    penalty = 0.0
    for w in weights:
        penalty += w * w
    return lambda_reg * 0.5 * penalty


def l2_gradient(weights, lambda_reg):
    return [lambda_reg * w for w in weights]
```

- 惩罚项带 `0.5`：`d/dw [(λ/2)w²] = λw`，系数 1/2 是为了让梯度干净。
- 梯度与权重**成正比**：大权重被拉得更狠，这就是"不让任何一个权重独大"。
- 这两个函数是给 STEP 2 演示用的；网络中的 weight decay 直接写在 `backward` 的更新式里（3.8）。

### 3.4 `BatchNorm`：沿 batch 维归一化 + running 统计量

```python
    def forward(self, batch):
        batch_size = len(batch)
        if self.training:
            mean = [0.0] * self.num_features
            for sample in batch:
                for j in range(self.num_features):
                    mean[j] += sample[j]
            mean = [m / batch_size for m in mean]

            var = [0.0] * self.num_features
            for sample in batch:
                for j in range(self.num_features):
                    var[j] += (sample[j] - mean[j]) ** 2
            var = [v / batch_size for v in var]

            for j in range(self.num_features):
                self.running_mean[j] = (1 - self.momentum) * self.running_mean[j] + self.momentum * mean[j]
                self.running_var[j] = (1 - self.momentum) * self.running_var[j] + self.momentum * var[j]
        else:
            mean = list(self.running_mean)
            var = list(self.running_var)
        # ...
                x_h = (sample[j] - mean[j]) / math.sqrt(var[j] + self.eps)
                normalized.append(x_h)
                out_sample.append(self.gamma[j] * x_h + self.beta[j])
```

- 输入是二维列表 `batch[样本][特征]`。外层循环遍历样本、内层遍历特征，对**每个特征 j** 在所有样本上求均值和方差——这就是"沿 batch 维"。
- 训练模式：用当前 batch 的 `mean/var` 归一化，同时用 EMA 更新 running 统计量：`running = 0.9·running + 0.1·当前`（momentum=0.1，与 PyTorch 默认值和讲义一致）。
- 推理模式：直接用 running 统计量，单个样本也能归一化，输出与 batch 中其他样本无关。
- 初始化 `running_mean = 0`、`running_var = 1`：未训练时推理等于"不归一化"（`(x-0)/√(1+ε) ≈ x`），是一个安全的默认值。
- `eps=1e-5` 放在开方里，防止方差为 0 时除以 0。
- `γ=1、β=0` 初始化：一开始就是纯归一化，训练中网络可以学着"撤销"归一化。
- `self.x_hat` 保存归一化结果，供反向传播使用（这里没有实现 backward）。
- ⚠️ 简化：①方差用 `/ batch_size`（有偏估计），PyTorch 在更新 `running_var` 时用的是无偏估计（`/ (B-1)`）；②没有实现反向传播，BN 的反向比较复杂（梯度会流过 mean 和 var）；③三重 Python 循环，效率很低。

### 3.5 `LayerNorm` 与 `RMSNorm`：沿特征维归一化

```python
class LayerNorm:
    # ...
    def forward(self, x):
        mean = sum(x) / len(x)
        var = sum((xi - mean) ** 2 for xi in x) / len(x)

        self.x_hat = []
        output = []
        for j in range(self.num_features):
            x_h = (x[j] - mean) / math.sqrt(var + self.eps)
            self.x_hat.append(x_h)
            output.append(self.gamma[j] * x_h + self.beta[j])
        return output
```

```python
class RMSNorm:
    def __init__(self, num_features, eps=1e-6):
        self.gamma = [1.0] * num_features
        self.eps = eps
        self.num_features = num_features

    def forward(self, x):
        rms = math.sqrt(sum(xi * xi for xi in x) / len(x) + self.eps)
        output = []
        for j in range(self.num_features):
            output.append(self.gamma[j] * x[j] / rms)
        return output
```

- 两者的输入都是**单个样本**（一维列表），统计量只在这个样本的特征之间计算，因此**没有 `training` 标志、没有 running 统计量**，训练推理完全一致——这正是 Transformer 选择它们的原因。
- LayerNorm 的 `mean`、`var` 是**标量**（一个样本一个），而 BatchNorm 的是**向量**（每个特征一个）。对比两段代码里 `mean[j]` 和 `mean` 的写法，就能看出归一化轴的区别。
- RMSNorm：只算 `√(mean(x²) + ε)`，不减均值、没有 β，参数和计算都更少。`eps` 默认 1e-6，与 LayerNorm 的 1e-5 不同，两者都是常见取值。
- 对比讲义公式 `rms = sqrt((1/D)·Σx²)`，代码把 ε 放进了开方里，避免全零输入时除以 0。
- ⚠️ `mean` 用 `len(x)` 计算，而输出循环用 `self.num_features`，两者需要相等；代码没有检查。

### 3.6 `RegularizedNetwork.__init__` 与 `forward`

```python
class RegularizedNetwork:
    def __init__(self, hidden_size=16, lr=0.05, dropout_p=0.0, weight_decay=0.0):
        random.seed(0)
        # ...
        self.dropout = Dropout(p=dropout_p) if dropout_p > 0 else None
```

- `random.seed(0)` 放在构造函数里，保证四种配置拿到**相同的初始权重**，对照实验才公平。
- `dropout_p=0` 时 `self.dropout = None`，后面用 `if self.dropout` 判断是否启用——用 `None` 表示"没有这个组件"，比创建一个 p=0 的 Dropout 更省计算。

```python
    def forward(self, x, training=True):
        # ... 计算 z1 和 h = ReLU(z1)
        if self.dropout and training:
            self.dropout.training = True
            self.h = self.dropout.forward(self.h)
        elif self.dropout:
            self.dropout.training = False
            self.h = self.dropout.forward(self.h)

        self.z2 = sum(self.w2[i] * self.h[i] for i in range(self.hidden_size)) + self.b2
        self.out = sigmoid(self.z2)
        return self.out
```

- dropout 放在**隐藏层激活之后、输出层之前**，这是 MLP 中最常见的位置。
- `training` 参数相当于把 `model.train()/eval()` 下沉为每次前向的参数。
- 注意 `self.h` 被覆盖成 dropout **之后**的值，所以 `backward` 中 `w2` 的梯度 `d_out * self.h[i]` 自动用的是"被丢弃/放大后"的激活，这是正确的。

### 3.7 `backward`：反向传播 + SGD 更新 + weight decay 一步完成

```python
    def backward(self, target):
        eps = 1e-15
        p = max(eps, min(1 - eps, self.out))
        d_loss = -(target / p) + (1 - target) / (1 - p)
        d_sigmoid = self.out * (1 - self.out)
        d_out = d_loss * d_sigmoid

        d_h_dropout = [d_out * self.w2[i] for i in range(self.hidden_size)]
        if self.dropout and self.dropout.mask is not None:
            d_h_dropout = [g * m / (1 - self.dropout.p) if m else 0.0
                           for g, m in zip(d_h_dropout, self.dropout.mask)]

        for i in range(self.hidden_size):
            d_relu = 1.0 if self.z1[i] > 0 else 0.0
            d_h = d_h_dropout[i] * d_relu
            self.w2[i] -= self.lr * (d_out * self.h[i] + self.weight_decay * self.w2[i])
            for j in range(2):
                self.w1[i][j] -= self.lr * (d_h * self.x[j] + self.weight_decay * self.w1[i][j])
            self.b1[i] -= self.lr * d_h
        self.b2 -= self.lr * d_out
```

梯度链路：`loss → out → z2 → h(dropout 后) → h(dropout 前) → z1 → w1, b1`。

- **dropout 的反向**：`d_h_dropout` 先是对 dropout 输出的梯度 `d_out·w2[i]`，再乘 `m/(1-p)`——与 `Dropout.backward` 完全一致。讲义 Build It 中的版本漏掉了这一步（`d_h = d_out * self.w2[i] * d_relu`），会给被丢弃的神经元传错误的梯度；`main.py` 修复了这个问题。
- **先算完再更新**：`d_h_dropout` 在循环前一次性用**旧的** `w2` 算好。如果在循环里边更新 `w2[i]` 边用它算 `d_h`，就会用到"半更新"的权重。
- **weight decay 写进梯度**：`grad + weight_decay * w`，配合 SGD 就等于每步 `w *= (1 - lr·λ)`。
- **偏置不衰减**：`b1`、`b2` 的更新里没有 weight decay 项，符合工程惯例。
- `self.dropout.mask is not None` 的保护：如果从未在训练模式下前向过，mask 为 None，避免 `zip(…, None)` 报错。
- ⚠️ 简化：把"求梯度"和"优化器更新"耦合在一个函数里，只能用 SGD。上一节的做法（`compute_grads` 返回梯度，再交给优化器）更解耦。

### 3.8 `evaluate` 与 `train_model`：训练准确率怎么来的

```python
    def evaluate(self, data):
        # ...
        for x, y in data:
            pred = self.forward(x, training=False)
            # ... 累加 loss 和 correct

    def train_model(self, train_data, test_data, epochs=300):
        history = []
        for epoch in range(epochs):
            total_loss = 0.0
            correct = 0
            for x, y in train_data:
                pred = self.forward(x, training=True)
                self.backward(y)
                # ... 用 pred 累加训练 loss 和 correct
            train_loss = total_loss / len(train_data)
            train_acc = correct / len(train_data) * 100
            test_loss, test_acc = self.evaluate(test_data)
```

- 测试准确率：`evaluate` 在 `training=False` 下计算，dropout 关闭。
- 训练准确率：在训练循环里"顺手"统计，用的是 **dropout 开启**时、**本步更新之前**的预测。
- ⚠️ 这两个数字不是同一种测量，带 dropout 的模型训练准确率会被低估，所以第 6 节里会出现负的 gap。正确做法是每个 epoch 末尾也用 `self.evaluate(train_data)` 在 eval 模式下评估训练集。
- 逐样本 SGD、数据不打乱，与上一节相同。

### 3.9 演示入口的 STEP 3–5

```python
    random.seed(42)
    batch = [[random.gauss(5, 2) for _ in range(4)] for _ in range(8)]
    sample = batch[0]

    bn = BatchNorm(4)
    bn_out = bn.forward(batch)
    ln = LayerNorm(4)
    ln_out = ln.forward(sample)
    rn = RMSNorm(4)
    rn_out = rn.forward(sample)
```

- STEP 3：同一个样本 `batch[0]` 分别过三种归一化。BN 需要整个 batch（输出取第 0 个样本），LN/RMSNorm 只需要这一个样本。

```python
    bn2 = BatchNorm(4)
    bn2.training = True
    for step in range(10):
        batch = [[random.gauss(3 + step * 0.1, 1) for _ in range(4)] for _ in range(16)]
        bn2.forward(batch)
```

- STEP 4：喂 10 个 batch（均值从 3.0 漂移到 3.9、方差 1），然后切到推理模式用 running 统计量归一化 `[5, 5, 5, 5]`。

```python
    all_data = make_circle_data(n=300, seed=42)
    train_data = all_data[:150]
    test_data = all_data[150:]
```

- STEP 5：300 个点前后对半切分。由于数据本身是随机生成、没有顺序结构，直接切片就是随机划分。然后四种配置（无正则 / dropout 0.3 / wd 0.01 / 两者都有）各训练 300 个 epoch。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| inverted dropout（训练时缩放） | 推理代码无需感知 dropout | 无明显代价，是业界标准 |
| `training` 标志由外部切换 | 模仿 `model.train()/eval()` | 忘记切换就会出 bug；框架会递归设置所有子模块 |
| BN 用 EMA 维护 running 统计量 | 推理时不依赖 batch，单样本可用 | 需要足够多的 batch 才收敛；PyTorch 对 running_var 用无偏估计 |
| LN/RMSNorm 无 running 统计量 | 训练推理一致，与 batch 无关 | 每个样本都要现算统计量 |
| 归一化层只做前向 | 聚焦"归一化轴"这一核心区别 | 没法训练 γ、β；框架用 autograd 自动求导 |
| weight decay 写进 SGD 更新式 | 最直接地展示"梯度 + λw" | 与优化器耦合，换 Adam 就不再是解耦衰减 |
| 偏置不做 weight decay | 偏置不是过拟合的主要来源 | 与生产惯例一致（再加上 norm 层参数） |
| 训练准确率边训练边统计 | 省一次前向 | 与测试准确率口径不同，带 dropout 时 gap 失真 |
| 构造函数内 `random.seed(0)` | 各配置初始权重相同 | 只测一个种子，结论不稳健 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类与实例属性 | `self.training = True`、`self.mask = None` | 实例属性在方法之间共享状态，前向存、反向取 |
| 默认参数 | `def __init__(self, p=0.5)`、`hidden_size=16, lr=0.05, dropout_p=0.0` | 超参数的默认值 |
| `not` 与提前返回 | `if not self.training: return list(x)` | 先处理简单分支，减少嵌套 |
| `None` 作为"没有这个组件" | `self.dropout = Dropout(...) if dropout_p > 0 else None` | 条件表达式 + `None`；后面用 `if self.dropout:` 判断 |
| 真值判断 | `if self.dropout and training:`、`if m else 0.0` | 对象非 None 即为真；整数 0 为假、1 为真 |
| `is not None` | `self.dropout.mask is not None` | 判断是否为 None 要用 `is` / `is not` |
| `elif` | `elif self.dropout:` | 多分支条件 |
| 列表乘法初始化 | `[1.0] * num_features`、`[0.0] * self.num_features` | 生成同值列表（元素为不可变 float，安全） |
| 列表推导式 + 条件表达式 | `[g * m / (1 - self.dropout.p) if m else 0.0 for g, m in zip(...)]` | 每个元素按条件选值 |
| 嵌套列表推导式 | `[[random.gauss(5, 2) for _ in range(4)] for _ in range(8)]` | 生成 8×4 的二维列表 |
| `zip` | `zip(grad_output, self.mask)` | 梯度和 mask 按位置配对 |
| 生成器表达式 + `sum` | `sum((xi - mean) ** 2 for xi in x)`、`sum(1 for v in output if v > 0)` | 求和、计数，不建中间列表 |
| `list(...)` 拷贝 | `list(self.running_mean)`、`list(x)` | 返回副本，防止外部修改内部状态 |
| 切片 | `all_data[:150]`、`all_data[150:]` | 前 150 个 / 第 150 个之后 |
| 多重赋值解包 | `train_loss, train_acc, test_loss, test_acc = history[-1]` | 一次取出元组的 4 个值 |
| f-string 嵌套与格式符 | `[f'{v:.1f}' for v in output]`、`f"{name:30s} {train_acc:>9.1f}%"` | `.1f` 一位小数；`>9` 右对齐占 9 位；`30s` 左对齐占 30 位 |
| f-string 内表达式 | `f"{sum(test_input)/len(test_input):.1f}"`、`f"Train pass {trial+1}"` | 花括号里可以写任意表达式 |
| 字符串乘法 | `"=" * 60` | 分隔线 |
| `random.random/gauss/seed` | `random.random() < self.p` | [0,1) 均匀分布实现伯努利采样 |
| `math.sqrt/log/exp` | `math.sqrt(var[j] + self.eps)` | 标准数学函数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示 |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py`，约 4 秒完成。

**STEP 1：Dropout**

```text
  Input:          [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
  Train pass 1:   ['2.0', '0.0', '0.0', '0.0', '10.0', '12.0', '14.0', '0.0']  (4/8 active)
  Train pass 2:   ['0.0', '0.0', '0.0', '8.0', '0.0', '0.0', '14.0', '16.0']  (3/8 active)
  Train pass 3:   ['0.0', '4.0', '6.0', '0.0', '10.0', '12.0', '0.0', '0.0']  (4/8 active)
  Eval pass:      ['1.0', '2.0', '3.0', '4.0', '5.0', '6.0', '7.0', '8.0']
  Train mean: ~4.5 (scaled by 1/(1-p))
  Eval mean:   4.5 (no scaling needed)
```

- 每次保留的个数不固定（4、3、4），因为每个神经元独立抛硬币，不是"恰好丢一半"。
- 保留值都是原值 ×2（p=0.5）。三次的实际均值分别是 4.75、4.75、4.0，围绕期望 4.5 波动。
- "Train mean: ~4.5" 打印的是**输入均值**，也就是训练输出的期望值，并不是上面某次前向的真实均值。
- 推理模式原样输出，均值正好 4.5。

**STEP 2：L2 正则**

```text
  L2 penalty: 0.084750
  L2 grads:   ['0.0050', '-0.0120', '0.0300', '0.0010', '-0.0250']
```

- `Σw² = 0.25 + 1.44 + 9 + 0.01 + 6.25 = 16.95`，`0.01 × 0.5 × 16.95 = 0.08475`。
- 梯度就是 `0.01·w`，符号与权重相同（更新时减去它，就是把权重往 0 拉）；3.0 的梯度最大。

**STEP 3：三种归一化**

```text
  Raw sample: ['4.71', '4.65', '4.78', '6.40']
  BatchNorm:  ['-1.13', '0.22', '-0.40', '0.89']
  LayerNorm:  ['-0.58', '-0.66', '-0.49', '1.73']
  RMSNorm:    ['0.91', '0.90', '0.92', '1.23']

  LayerNorm output: mean=0.0000, std=1.0000
  RMSNorm output:   mean=0.9900, rms=1.0000
```

- **BatchNorm** 的结果取决于同一 batch 里的其他 7 个样本：第 1 个特征 4.71 比该特征的 batch 均值小，所以是 -1.13。同样是约 4.7 的值，在不同特征上归一化后差别很大，因为每个特征的 batch 统计量不同。
- **LayerNorm** 只看这一个样本：4 个值的均值约 5.14，前三个低于均值变负，6.40 明显偏大变成 1.73；输出均值 0、标准差 1。
- **RMSNorm** 只除以均方根（约 5.2）：所有值仍为正，相对大小不变，输出 rms=1，但均值 0.99 远离 0。这个例子直观说明"RMSNorm 只归一化尺度、不做中心化"。

**STEP 4：BatchNorm 训练 vs 推理**

```text
  Running mean after 10 batches: ['2.317', '2.248', '2.306', '2.351']
  Running var  after 10 batches: ['0.921', '0.992', '0.986', '0.910']
  Eval mode uses running stats, not batch stats
  Input [5,5,5,5] -> ['2.796', '2.763', '2.713', '2.777']
```

- 真实 batch 均值从 3.0 漂到 3.9，但 running_mean 只有约 2.3。原因是它从 0 开始，10 次 EMA 后初始值 0 仍占 `0.9¹⁰ ≈ 35%` 的权重。running 统计量**还没收敛**。
- running_var 约 0.92–0.99，接近真实方差 1（初始值恰好是 1，且 16 个样本的有偏方差略小于 1）。
- 推理时 `[5,5,5,5]` 被归一化成约 2.78；如果 running_mean 已收敛到约 3.5，结果应约为 1.5。这提醒我们：**BN 模型训练步数太少时，推理效果可能明显差于训练效果**。

**STEP 5：四种配置对照**

```text
--- No regularization ---
    Epoch   0: train_acc=68.7%, test_acc=68.7%, gap=0.0%
    Epoch 299: train_acc=99.3%, test_acc=97.3%, gap=2.0%
--- Dropout p=0.3 ---
    Epoch 299: train_acc=96.0%, test_acc=98.0%, gap=-2.0%
--- Weight decay 0.01 ---
    Epoch 299: train_acc=96.7%, test_acc=94.0%, gap=2.7%
--- Dropout + weight decay ---
    Epoch 150: train_acc=84.7%, test_acc=92.0%, gap=-7.3%
    Epoch 299: train_acc=87.3%, test_acc=90.7%, gap=-3.3%

FINAL COMPARISON
  No regularization                   99.3%      97.3%     2.0%
  Dropout p=0.3                       96.0%      98.0%    -2.0%
  Weight decay 0.01                   96.7%      94.0%     2.7%
  Dropout + weight decay              87.3%      90.7%    -3.3%

  Key insight: regularization reduces the train-test gap.
  The model with dropout + weight decay generalizes best,
  even if its training accuracy is lower.
```

这组结果值得仔细读，因为它**和最后三行写死的结论并不一致**：

1. **基线本身几乎不过拟合**（gap 2.0%）。圆形边界很简单、数据没有标签噪声，16 个隐藏单元的网络学得很好，正则化几乎没有发挥空间。
2. **负 gap 是测量口径造成的**。带 dropout 的配置，训练准确率是在 dropout 开启时边训练边统计的，测试准确率却是在 eval 模式下算的。在 eval 模式下重新评估训练集：Dropout p=0.3 的训练准确率实为 99.3%（真实 gap 1.3%），Dropout + weight decay 实为 93.3%（真实 gap 2.7%）。
3. **Dropout p=0.3 的测试准确率最高（98.0%）**，是这次实验中唯一真正带来收益的配置。
4. **weight decay 0.01 在这里偏强**：每步收缩 `lr·λ = 5e-4`，45,000 步累积下来，w1、w2 的 L2 范数从约 15.8 降到 5.5，模型被压得欠拟合，测试准确率降到 94.0%。
5. **Dropout + weight decay 测试准确率最低（90.7%）**，是典型的"正则化过度 → 欠拟合"，并不是"泛化最好"。

结论：要让这个实验真正演示正则化的价值，需要先制造过拟合（更少数据、标签噪声、更大网络），并用一致的口径测量 gap。

---

## 7. 动手改一改

1. **修正测量口径**：在 `train_model` 的每个 epoch 末尾加一行 `train_loss, train_acc = self.evaluate(train_data)`，重新运行，确认负 gap 消失。
2. **制造过拟合**：把训练集缩到 `all_data[:40]`，并随机翻转其中 15% 的标签，`hidden_size` 改成 64。再比较四种配置的测试准确率，看正则化是否开始"赚钱"。
3. **扫 weight decay**：λ 取 `[0, 1e-4, 1e-3, 1e-2]`，打印最终测试准确率和权重 L2 范数，找出这个任务上的合适强度。
4. **验证 dropout 期望**：对同一输入调用 `Dropout(p=0.3).forward` 10,000 次，按位置求平均，确认结果接近原输入。
5. **把 BatchNorm 接入网络**：在 `z1` 和 ReLU 之间插入 BN（需要改成 mini-batch 训练，并补全 BN 的反向传播），对比讲义练习 3 中不同学习率下的稳定性。
6. **实现 early stopping**：监控验证 loss，patience=20，保存/恢复最佳权重（注意 `w1` 是嵌套列表，要用 `copy.deepcopy`）。

---

## 8. 常见坑

- **训练和评估口径不一致**：边训练边统计的准确率包含 dropout 噪声和"更新前"的预测，拿它和 eval 模式下的测试准确率相减，得到的 gap 没有意义。
- **dropout 反向没用 mask**：讲义 Build It 版本就有这个问题，被丢弃的神经元收到错误梯度，代码不会报错，只是训练效果莫名变差。
- **训练和推理都缩放了**：用了 inverted dropout，推理时就不能再乘 `1-p`，否则输出整体偏小。
- **BN 的 running 统计量没收敛**：训练步数少或刚初始化时，推理输出会有系统偏差（STEP 4）。
- **训练模式下 batch size 为 1**：BN 的输出退化为常数 β，PyTorch 会直接报错。
- **正则化叠加过度**：dropout、weight decay、数据增强一次全加上，很容易像 STEP 5 那样欠拟合。一次只改一个变量。
