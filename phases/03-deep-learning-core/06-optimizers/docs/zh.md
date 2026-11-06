<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="optimizers"></a>

# Optimizers

> Gradient descent 告诉你向哪个方向移动。它没有说明多远或多快。 SGD 是一个指南针。 Adam 是带有交通数据的 GPS。

**类型：** 构建
**语言：** Python
**先决条件：** 第 03.05 课 (Loss Functions)
**时间：** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 在Python中从头开始实现SGD、动量SGD、Adam和AdamW optimizers
- 解释Adam的偏差校正如何补偿早期训练步骤中的零初始化矩估计
- 演示为什么 AdamW 在相同任务上比使用 L2 正则化的 Adam 产生更好的泛化能力
- 为 transformers、CNNs、GANs 和 fine-tuning 选择适当的 optimizer 和默认 hyperparameters

<a id="the-problem"></a>

## 问题

您计算出 gradients。您知道 weight #4,721 应减少 0.003 以减少损失。但 0.003 的单位是什么？按什么缩放？您是否应该在步骤 1 中移动与步骤 1,000 相同的量？

Vanilla gradient descent 在每一步上将相同的 learning rate 应用于每个 parameter：w = w - lr * gradient。这产生了三个问题，使训练神经网络在实践中变得痛苦。

第一，振荡。损失景观很少呈光滑的碗状。它更像是一条狭长的山谷。 gradient 指向山谷对面（陡峭的方向），而不是沿着山谷（浅的方向​​）。 Gradient descent 在狭窄的维度上来回弹跳，同时沿着有用的维度取得微小的进展。您已经看到了这一点：损失快速下降然后趋于稳定，不是因为模型收敛，而是因为它正在振荡。

其次，一个 learning rate 代表所有 parameters 是错误的。一些 weights 需要大量更新（它们处于早期 underfitting 阶段）。其他人需要微小的更新（它们接近最佳值）。适用于前者的 learning rate 会破坏后者，反之亦然。

第三，鞍点。在高维度中，损失景观具有广阔的平坦区域，其中 gradient 接近于零。 Vanilla SGD 以 gradient 的速度爬行这些内容，实际上为零。模型看起来卡住了。它没有被卡住——它位于一个平坦的区域，另一侧有有用的下降。但SGD没有机制可以推动。

Adam 解决了这三个问题。它为每个 parameter 维护两个运行平均值——均值 gradient（动量，处理振荡）和均方 gradient（自适应速率，处理不同的尺度）。结合前几个步骤的偏差校正，它为您提供了一个 optimizer，它可以解决默认 hyperparameters 的 80% 问题。本课程从头开始构建它，以便您准确了解它在其他 20% 上失败的时间和原因。

<a id="the-concept"></a>

## 概念

<a id="stochastic-gradient-descent-sgd"></a>

### Stochastic Gradient Descent (新加坡元)

最简单的optimizer。在小批量上计算 gradient 并朝相反方向步进。

```
w = w - lr * gradient
```

“随机”意味着您使用数据的随机子集（小批量）来估计 gradient，而不是完整的数据集。这种噪声实际上很有用——它有助于逃避尖锐的局部最小值。但噪声也会引起振荡。

Learning rate 是唯一的旋钮。太高：损失出现偏差。太低：训练需要很长时间。最佳值取决于架构、数据、batch size 以及当前的训练阶段。对于现代网络上的普通 SGD，典型值范围为 0.01 到 0.1。但即使在一次训练中，理想的 learning rate 也会发生变化。

<a id="momentum"></a>

### 势头

球滚下坡的比喻虽然被过度使用，但却很准确。您不必单独步进 gradient，而是保持累积超过 gradients 的速度。

```
m_t = beta * m_{t-1} + gradient
w = w - lr * m_t
```

Beta（通常为 0.9）控制要保留的历史记录量。当 beta = 0.9 时，动量大致是最后 10 个 gradients 的平均值 (1 / (1 - 0.9) = 10)。

为什么这可以修复振荡：gradients 指向同一方向的累积。 Gradients 翻转方向抵消。在那个狭窄的山谷中，“跨”组件每一步都会翻转符号并受到抑制。 “沿着”部分保持一致并得到放大。结果是在有用方向上平滑加速。

实数：在条件恶劣的损失情况下，仅 SGD 就可能需要 10,000 步。对于同一问题，动量 SGD（beta=0.9）通常需要 3,000-5,000 步。加速并不是边际的。

<a id="rmsprop"></a>

### RMS属性

第一个实际有效的 per-parameter 自适应 learning rate 方法。由 Hinton 在 Coursera 讲座中提出（从未正式发表）。

```
s_t = beta * s_{t-1} + (1 - beta) * gradient^2
w = w - lr * gradient / (sqrt(s_t) + epsilon)
```

s_t 跟踪 gradients 平方的运行平均值。 Parameters 与一致大的 gradients 被除以一个大数（较小的有效 learning rate）。 Parameters 与较小的 gradients 除以一个较小的数字（较大的有效 learning rate）。

这就解决了“一个 learning rate 代表所有 parameters”的问题。已经进行了大量更新的 weight 可能已经接近其目标——放慢速度。一直在进行微小更新的 weight 可能训练不足——加快速度。

当 parameter 尚未更新时，Epsilon（通常为 1e-8）可防止被零除。

<a id="adam-momentum--rmsprop"></a>

### Adam：动量+RMSProp

Adam 结合了这两种想法。它维护每个 parameter 的两个指数移动平均线：

```
m_t = beta1 * m_{t-1} + (1 - beta1) * gradient        (first moment: mean)
v_t = beta2 * v_{t-1} + (1 - beta2) * gradient^2       (second moment: variance)
```

**偏差校正**是大多数解释跳过的关键细节。在步骤 1 中，m_1 = (1 - beta1) * gradient。当 beta1 = 0.9 时，即 0.1 * gradient —— 太小了十倍。移动平均线尚未升温。偏差校正补偿：

```
m_hat = m_t / (1 - beta1^t)
v_hat = v_t / (1 - beta2^t)
```

在第 1 步，beta1 = 0.9：m_hat = m_1 / (1 - 0.9) = m_1 / 0.1 = 实际的 gradient。在步骤 100：(1 - 0.9^100) 大约为 1.0，因此校正消失。偏差校正对于前约 10 个步骤很重要，而在约 50 个步骤之后则无关紧要。

更新：

```
w = w - lr * m_hat / (sqrt(v_hat) + epsilon)
```

Adam 默认：lr = 0.001，beta1 = 0.9，beta2 = 0.999，epsilon = 1e-8。这些默认值适用于 80% 的问题。如果没有，请先更改 lr。然后是测试版2。几乎从不改变 beta1 或 epsilon。

<a id="adamw-weight-decay-done-right"></a>

### AdamW：Weight Decay 做得好

L2 正则化将 lambda * w^2 添加到损失中。在普通 SGD 中，这相当于 weight decay（在每一步从 weight 中减去 lambda * w）。在 Adam 中，这种等价性被打破。

Loshchilov & Hutter 的见解：当您将 L2 添加到损失中，然后 Adam 处理 gradient 时，自适应 learning rate 也会缩放正则化项。具有较大 gradient 方差的 Parameters 得到的正则化较少。 Parameters 方差较小的得到更多。这不是您想要的——无论 gradient 统计数据如何，您都需要统一正则化。

AdamW 通过在 Adam 更新后直接将 weight decay 应用于 weights 来修复此问题：

```
w = w - lr * m_hat / (sqrt(v_hat) + epsilon) - lr * lambda * w
```

weight decay 项 (lr * lambda * w) 未按 Adam 的自适应因子缩放。每个 parameter 都会获得相同的比例收缩。

这似乎是一个小细节。它不是。 AdamW 在几乎每个任务上都收敛到比 Adam + L2 正则化更好的解决方案。它是 PyTorch 中默认的 optimizer，用于训练 transformers、diffusion models 和大多数现代架构。 BERT、GPT、LLaMA、稳定扩散——均使用 AdamW 进行训练。

<a id="learning-rate-the-most-important-hyperparameter"></a>

### Learning Rate：最重要的Hyperparameter

```mermaid
graph TD
    LR["Learning Rate"] --> TooHigh["Too high (lr > 0.01)"]
    LR --> JustRight["Just right"]
    LR --> TooLow["Too low (lr < 0.00001)"]

    TooHigh --> Diverge["Loss explodes<br/>NaN weights<br/>Training crashes"]
    JustRight --> Converge["Loss decreases steadily<br/>Reaches good minimum<br/>Generalizes well"]
    TooLow --> Stall["Loss decreases slowly<br/>Gets stuck in suboptimal minimum<br/>Wastes compute"]

    JustRight --> Schedule["Usually needs scheduling"]
    Schedule --> Warmup["Warmup: ramp from 0 to max<br/>First 1-10% of training"]
    Schedule --> Decay["Decay: reduce over time<br/>Cosine or linear"]
```

如果您调整一个 hyperparameter，请调整 learning rate。 learning rate 的 10 倍更改比您做出的任何架构决策都更重要。常见默认值：

- SGD：lr = 0.01 至 0.1
- Adam/AdamW：lr = 1e-4 至 3e-4
- Fine-tuning 预训练模型：lr = 1e-5 至 5e-5
- Learning rate warmup：前 1-10% 步长的线性斜坡

<a id="optimizer-comparison"></a>

### Optimizer 比较

```mermaid
flowchart LR
    subgraph "Optimization Path"
        SGD_P["SGD<br/>Oscillates across valley<br/>Slow but finds flat minima"]
        Mom_P["SGD + Momentum<br/>Smoother path<br/>3x faster than SGD"]
        Adam_P["Adam<br/>Adapts per-parameter<br/>Fast convergence"]
        AdamW_P["AdamW<br/>Adam + proper decay<br/>Best generalization"]
    end
    SGD_P --> Mom_P --> Adam_P --> AdamW_P
```

<a id="when-each-optimizer-wins"></a>

### 当每个 Optimizer 获胜时

```mermaid
flowchart TD
    Task["What are you training?"] --> Type{"Model type?"}

    Type -->|"Transformer / LLM"| AdamW["AdamW<br/>lr=1e-4, wd=0.01-0.1"]
    Type -->|"CNN / ResNet"| SGD_M["SGD + Momentum<br/>lr=0.1, momentum=0.9"]
    Type -->|"GAN"| Adam2["Adam<br/>lr=2e-4, beta1=0.5"]
    Type -->|"Fine-tuning"| AdamW2["AdamW<br/>lr=2e-5, wd=0.01"]
    Type -->|"Don't know yet"| Default["Start with AdamW<br/>lr=3e-4, wd=0.01"]
```

```figure
optimizer-trajectory
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-vanilla-sgd"></a>

### 第 1 步：普通新元

```python
class SGD:
    def __init__(self, lr=0.01):
        self.lr = lr

    def step(self, params, grads):
        for i in range(len(params)):
            params[i] -= self.lr * grads[i]
```

<a id="step-2-sgd-with-momentum"></a>

### 第 2 步：带有动量的 SGD

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

<a id="step-3-adam"></a>

### 步骤3：Adam

```python
import math

class Adam:
    def __init__(self, lr=0.001, beta1=0.9, beta2=0.999, epsilon=1e-8):
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        self.m = None
        self.v = None
        self.t = 0

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

<a id="step-4-adamw"></a>

### 步骤4：AdamW

```python
class AdamW:
    def __init__(self, lr=0.001, beta1=0.9, beta2=0.999, epsilon=1e-8, weight_decay=0.01):
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        self.weight_decay = weight_decay
        self.m = None
        self.v = None
        self.t = 0

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
            params[i] -= self.lr * self.weight_decay * params[i]
```

<a id="step-5-training-comparison"></a>

### 第 5 步：训练比较

使用所有四个 optimizers 在第 05 课的圆形数据集上训练相同的两层网络。比较收敛性。

```python
import random

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


class OptimizerTestNetwork:
    def __init__(self, optimizer, hidden_size=8):
        random.seed(0)
        self.hidden_size = hidden_size
        self.optimizer = optimizer

        self.w1 = [[random.gauss(0, 0.5) for _ in range(2)] for _ in range(hidden_size)]
        self.b1 = [0.0] * hidden_size
        self.w2 = [random.gauss(0, 0.5) for _ in range(hidden_size)]
        self.b2 = 0.0

    def get_params(self):
        params = []
        for row in self.w1:
            params.extend(row)
        params.extend(self.b1)
        params.extend(self.w2)
        params.append(self.b2)
        return params

    def set_params(self, params):
        idx = 0
        for i in range(self.hidden_size):
            for j in range(2):
                self.w1[i][j] = params[idx]
                idx += 1
        for i in range(self.hidden_size):
            self.b1[i] = params[idx]
            idx += 1
        for i in range(self.hidden_size):
            self.w2[i] = params[idx]
            idx += 1
        self.b2 = params[idx]

    def forward(self, x):
        self.x = x
        self.z1 = []
        self.h = []
        for i in range(self.hidden_size):
            z = self.w1[i][0] * x[0] + self.w1[i][1] * x[1] + self.b1[i]
            self.z1.append(z)
            self.h.append(max(0.0, z))

        self.z2 = sum(self.w2[i] * self.h[i] for i in range(self.hidden_size)) + self.b2
        self.out = sigmoid(self.z2)
        return self.out

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

        for i in range(self.hidden_size):
            d_relu = 1.0 if self.z1[i] > 0 else 0.0
            grads[idx] = d_out * self.w2[i] * d_relu
            idx += 1

        for i in range(self.hidden_size):
            grads[idx] = d_out * self.h[i]
            idx += 1

        grads[idx] = d_out
        return grads

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

                eps = 1e-15
                p = max(eps, min(1 - eps, pred))
                total_loss += -(y * math.log(p) + (1 - y) * math.log(1 - p))
                if (pred >= 0.5) == (y >= 0.5):
                    correct += 1
            avg_loss = total_loss / len(data)
            accuracy = correct / len(data) * 100
            losses.append((avg_loss, accuracy))
            if epoch % 75 == 0 or epoch == epochs - 1:
                print(f"    Epoch {epoch:3d}: loss={avg_loss:.4f}, accuracy={accuracy:.1f}%")
        return losses
```

<a id="use-it"></a>

## 实际应用

PyTorch optimizers 处理 parameter 组、gradient clipping 和 learning rate 调度：

```python
import torch
import torch.optim as optim

model = torch.nn.Sequential(
    torch.nn.Linear(784, 256),
    torch.nn.ReLU(),
    torch.nn.Linear(256, 10),
)

optimizer = optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)

scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)

for epoch in range(100):
    optimizer.zero_grad()
    output = model(torch.randn(32, 784))
    loss = torch.nn.functional.cross_entropy(output, torch.randint(0, 10, (32,)))
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    optimizer.step()
    scheduler.step()
```

模式始终为：zero_grad、向前、损失、向后、（剪辑）、步骤、（时间表）。记住这个顺序。出错（例如，在 optimizer.step() 之前调用 Scheduler.step()）是细微错误的常见来源。

对于CNNs，许多从业者仍然更喜欢采用步长或余弦时间表的SGD +动量（lr=0.1，动量=0.9，weight_decay=1e-4）。 SGD 发现更平坦的最小值，通常具有更好的泛化能力。对于 transformers 和 LLMs，AdamW 和 warmup + 余弦衰减是通用默认值。没有经过深思熟虑的理由，不要违背共识。

<a id="ship-it"></a>

## 交付成果

本课产生：
- `outputs/prompt-optimizer-selector.md` - 为任何架构选择正确的 optimizer 和 learning rate 的决策 prompt

<a id="exercises"></a>

## 练习

1. 实现 Nesterov 动量，在“前瞻”位置 (w - lr * beta * v) 而不是当前位置计算 gradient。将收敛性与圆数据集上的标准动量进行比较。

2. 实施一个learning rate warmup时间表：从 0 到最大的线性斜坡_lr 在前 10% 的训练步骤中，然后余弦衰减到 0。 训练与Adam+warmup与Adam没有warmup。 测量在圆形数据集上达到 90% 准确度需要多少个 epoch。

3. 在 Adam 训练期间跟踪每个 parameter 的有效 learning rate。有效率为lr * m_hat / (sqrt(v_hat) + eps)。绘制 10、50 和 200 步后有效率的分布图。所有parameters的更新速度都一样吗？

4. 实施gradient clipping（按全球标准剪辑）。将最大 gradient 范数设置为 1.0。使用高 learning rate（对于 Adam，lr=0.01）进行有削波和无削波的训练。计算有多少次运行发散（损失归于 NaN），无论是否剪切超过 10 个随机种子。

5. 在具有大型 weights 的网络上比较 Adam 与 AdamW。将所有weights初始化为[-5、5]中的随机值（比正常值大得多）。使用权重 _decay=0.1 训练 200 个 epoch。绘制 weights 在 optimizers 训练上的 L2 范数。 AdamW 应显示出更快的 weight 收缩。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| Learning rate | “步长” | gradient 更新上的标量乘数；训练中最有影响力的hyperparameter |
| 新加坡元 | “基本gradient descent” | Stochastic gradient descent：通过减去 lr * gradient 来更新 weights，在小批量上计算 |
| 势头 | “滚球类比” | 过去的指数移动平均线gradients；抑制振荡并加速一致方向 |
| RMS属性 | “自适应learning rate” | 将每个parameter的gradient除以其最近的gradients的运行RMS；均衡 learning rates |
| Adam | “默认optimizer” | 将动量（一阶矩）和 RMSProp（二阶矩）与初始步骤的偏差校正相结合 |
| AdamW | “Adam 做得对” | Adam 与解耦 weight decay；直接将正则化应用于 weights，而不是通过 gradient |
| 偏差校正 | “Warmup 用于运行平均值” | 除以(1 - beta^t)以补偿Adam的矩估计的零初始化 |
| Weight decay | “缩小weights” | 每一步减去 weight 值的一小部分；惩罚大 weights 的正则化器 |
| Learning rate schedule | “随着时间的推移改变lr” | 训练时调整learning rate的功能； warmup + 余弦衰减是现代默认值 |
| Gradient clipping | “限制 gradient 规范” | 缩小规模gradient当向量的范数超过阈值时； 防止爆炸gradient更新 |

<a id="further-reading"></a>

## 进一步阅读

- Kingma & Ba，“Adam：随机优化方法”（2014）——原始 Adam 论文，包含收敛分析和偏差校正推导
- Loshchilov & Hutter，“解耦 Weight Decay 正则化”（2017）——证明了 L2 正则化和 weight decay 在 Adam 中并不等价，并提出了 AdamW
- Smith，“用于训练神经网络的循环 Learning Rates”（2017 年）——介绍了 LR 范围测试和循环调度，无需调整固定的 learning rate
- Ruder，“Gradient Descent 优化算法概述”（2016 年）——对所有 optimizer 变体的最佳单一调查，具有清晰的比较和直觉
