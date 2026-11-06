<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="loss-functions"></a>

# Loss Functions

> 您的网络做出预测。事实并非如此。到底有多错呢？这个数字就是损失。选择错误的 loss function ，你的模型就会完全针对错误的事情进行优化。

**类型：** 构建
**语言：** Python
**先决条件：** 第 03.04 课 (Activation Functions)
**时间：** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 使用 gradients 从头开始实现 MSE、二进制 cross-entropy、分类 cross-entropy 和对比损失 (InfoNCE)
- 通过演示“对所有内容预测 0.5”故障模式，解释为什么 MSE 分类失败
- 将标签平滑应用于 cross-entropy 并描述它如何防止过度自信的预测
- 为回归、二元分类、多类分类和 embedding 学习任务选择正确的 loss function

<a id="the-problem"></a>

## 问题

最小化分类问题上的 MSE 的模型将自信地预测所有事情的结果都是 0.5。就是把损失降到最低。也是没用的。

loss function 是您的模型实际优化的唯一内容。不是准确性。不是F1成绩。不是您向经理报告的任何指标。 optimizer 采用 loss function 的 gradient 并调整 weights 以使该数字更小。如果 loss function 没有捕捉到你关心的东西，模型会找到数学上最便宜的方式来满足它，而这种方式几乎永远不是你想要的。

这是一个具体的例子。您有一个二元分类任务。两个班级，50/50 分开。你用 MSE 作为你的损失。该模型对每个输入的预测值为 0.5。平均 MSE 为 0.25，这是在没有实际学习任何东西的情况下可能的最小值。该模型的判别能力为零，但它在技术上最小化了您的 loss function。切换到 cross-entropy ，相同的模型被迫将预测推向 0 或 1，因为 -log(0.5) = 0.693 是一个可怕的损失，而 -log(0.99) = 0.01 奖励有信心的正确预测。 loss function 的选择是学习模型和玩度量的模型之间的区别。

情况变得更糟。在自我监督学习中，你甚至没有标签。对比损失完全定义了学习信号：什么算相似，什么算不同，以及模型应该在多大程度上将它们分开。如果对比损失错误，你的 embeddings 就会崩溃到一个点——每个输入都映射到同一个向量。技术上零损失。完全没有价值。

<a id="the-concept"></a>

## 概念

<a id="mean-squared-error-mse"></a>

### 均方误差 (MSE)

回归的默认值。计算预测与目标之间的平方差，以及所有样本的平均值。

```
MSE = (1/n) * sum((y_pred - y_true)^2)
```

为什么平方很重要：它对大误差进行二次惩罚。 2 个错误的成本是 1 个错误的 4 倍。10 个错误的成本是 100 倍。这使得 MSE 对异常值很敏感——一个严重错误的预测主导了损失。

实数：如果您的模型预测房价，大多数房屋的价格下跌了 10,000 美元，但一栋豪宅的价格下跌了 200,000 美元，MSE 将积极尝试修复该豪宅，这可能会损害其他 99 栋房屋的表现。

MSE 的 gradient 的预测为：

```
dMSE/dy_pred = (2/n) * (y_pred - y_true)
```

误差呈线性。错误越大，gradients。这是一个用于回归的 feature（大错误需要大量修正）和一个分类错误（您希望以指数方式而非线性方式惩罚自信的错误答案）。

<a id="cross-entropy-loss"></a>

### Cross-Entropy 损失

loss function 进行分类。植根于信息论——它测量预测概率分布与真实分布之间的差异。

**二进制 Cross-Entropy (BCE):**

```
BCE = -(y * log(p) + (1 - y) * log(1 - p))
```

其中 y 是真实标签（0 或 1），p 是预测概率。

为什么 -log(p) 有效：当真实标签为 1 并且您预测 p = 0.99 时，损失为 -log(0.99) = 0.01。当您预测 p = 0.01 时，损失为 -log(0.01) = 4.6。 460x 的差异就是 cross-entropy 起作用的原因。它残酷地惩罚自信的错误预测，同时几乎不惩罚自信的正确预测。

gradient 讲述了同样的故事：

```
dBCE/dp = -(y/p) + (1-y)/(1-p)
```

当 y = 1 并且 p 接近零时，gradient 为 -1/p，接近负无穷大。该模型收到了一个巨大的信号来纠正其错误。当p接近1时，gradient很小。已经正确了，没有什么可修复的。

**分类 Cross-Entropy:**

用于具有one-hot编码目标的多类分类。

```
CCE = -sum(y_i * log(p_i))
```

只有真正的类别才会造成损失（因为所有其他 y_i 均为零）。如果有 10 个类别，并且正确类别的概率为 0.1（随机猜测），则损失为 -log(0.1) = 2.3。如果正确类别的概率为 0.9，则损失为 -log(0.9) = 0.105。该模型学会将概率质量集中在正确答案上。

<a id="why-mse-fails-for-classification"></a>

### 为什么 MSE 分类失败

```mermaid
graph TD
    subgraph "MSE on Classification"
        P1["Predict 0.5 for class 1<br/>MSE = 0.25"]
        P2["Predict 0.9 for class 1<br/>MSE = 0.01"]
        P3["Predict 0.1 for class 1<br/>MSE = 0.81"]
    end
    subgraph "Cross-Entropy on Classification"
        C1["Predict 0.5 for class 1<br/>CE = 0.693"]
        C2["Predict 0.9 for class 1<br/>CE = 0.105"]
        C3["Predict 0.1 for class 1<br/>CE = 2.303"]
    end
    P3 -->|"MSE gradient<br/>flattens near<br/>saturation"| Slow["Slow correction"]
    C3 -->|"CE gradient<br/>explodes near<br/>wrong answer"| Fast["Fast correction"]
```

当预测接近 0 或 1 时，MSE gradients 趋于平坦（由于 sigmoid saturation）。 Cross-entropy gradients 对此进行了补偿——-log 取消了 sigmoid 的平坦区域，从而在最需要的地方提供了强大的 gradients。

<a id="label-smoothing"></a>

### 标签平滑

标准的 one-hot 标签上写着“这是 100% 3 级，其他都是 0%”。这是一个强有力的主张。标签平滑可以软化它：

```
smooth_label = (1 - alpha) * one_hot + alpha / num_classes
```

当 alpha = 0.1 和 10 个类别时：目标变为 [0.01, 0.01, 0.91, 0.01, ...]，而不是 [0, 0, 1, 0, ...]。该模型的目标是 0.91，而不是 1.0。

为什么会这样：尝试通过 softmax 精确输出 1.0 的模型需要将 logits 推至无穷大。这会导致过度自信，损害泛化能力，并使模型变得脆弱至 distribution shift。标签平滑将目标上限限制在 0.9（alpha=0.1），使 logits 保持在合理的范围内。 GPT 和大多数现代模型使用标签平滑或其等效项。

<a id="contrastive-loss"></a>

### 对比损失

没有标签。没有课。只是成对的输入和问题：这些是相似还是不同？

**SimCLR型对比损失（NT-Xent / InfoNCE）：**

拍摄一张图像。创建它的两个增强视图（裁剪、旋转、颜色抖动）。这些是“正对”——它们应该具有类似的 embeddings。批次中的每个其他图像形成一个“负对”——它们应该具有不同的 embeddings。

```
L = -log(exp(sim(z_i, z_j) / tau) / sum(exp(sim(z_i, z_k) / tau)))
```

其中 sim() 是 cosine similarity，z_i 和 z_j 是正对，总和是所有负数的总和，tau (temperature) 控制分布的尖锐程度。较低的 temperature = 更难的底片 = 更积极的分离。

实数：batch size 256 表示每个正数对有 255 个负数。 Temperature tau = 0.07（SimCLR 默认值）。损失看起来像 softmax 的相似度 - 它希望正对的相似度在所有 256 个选项中最高。

**三元组丢失：**

接受三个输入：锚点、正值（同一类）、负值（不同类）。

```
L = max(0, d(anchor, positive) - d(anchor, negative) + margin)
```

边距（通常为 0.2-1.0）强制规定正距离和负距离之间的最小间隙。如果负数已经足够远，则损失为零——没有 gradient，没有更新。这使得训练变得高效，但需要仔细的三元组挖掘（选择接近锚点的硬负例）。

<a id="focal-loss"></a>

### 焦点损失

对于不平衡的数据集。标准 cross-entropy 平等对待所有正确分类的示例。焦点损失下降-weights 简单示例：

```
FL = -alpha * (1 - p_t)^gamma * log(p_t)
```

其中 p_t 是真实类别的预测概率，gamma 控制聚焦。当 gamma = 0 时，这是标准 cross-entropy。当 gamma = 2（默认值）时：

- 简单示例（p_t = 0.9）：weight = (0.1)^2 = 0.01。有效地被忽略了。
- 困难的例子（p_t = 0.1）：weight =（0.9）^2 = 0.81。完整的 gradient 信号。

Lin 等人引入了焦点损失。对于目标检测，其中 99% 的候选区域是背景（简单负片）。如果没有焦点损失，模型就会淹没在简单的背景示例中，永远无法学会检测物体。有了它，该模型将其能力集中在重要的困难、模糊的案例上。

<a id="loss-function-decision-tree"></a>

### Loss Function 决策树

```mermaid
flowchart TD
    Start["What is your task?"] --> Reg{"Regression?"}
    Start --> Cls{"Classification?"}
    Start --> Emb{"Learning embeddings?"}

    Reg -->|"Yes"| Outliers{"Outlier sensitive?"}
    Outliers -->|"Yes, penalize outliers"| MSE["Use MSE"]
    Outliers -->|"No, robust to outliers"| MAE["Use MAE / Huber"]

    Cls -->|"Binary"| BCE["Use Binary CE"]
    Cls -->|"Multi-class"| CCE["Use Categorical CE"]
    Cls -->|"Imbalanced"| FL["Use Focal Loss"]
    CCE -->|"Overconfident?"| LS["Add Label Smoothing"]

    Emb -->|"Paired data"| CL["Use Contrastive Loss"]
    Emb -->|"Triplets available"| TL["Use Triplet Loss"]
    Emb -->|"Large batch self-supervised"| NCE["Use InfoNCE"]
```

<a id="loss-landscape"></a>

### 损失景观

```mermaid
graph LR
    subgraph "Loss Surface Shape"
        MSE_S["MSE<br/>Smooth parabola<br/>Single minimum<br/>Easy to optimize"]
        CE_S["Cross-Entropy<br/>Steep near wrong answers<br/>Flat near correct answers<br/>Strong gradients where needed"]
        CL_S["Contrastive<br/>Many local minima<br/>Depends on batch composition<br/>Temperature controls sharpness"]
    end
    MSE_S -->|"Best for"| Reg2["Regression"]
    CE_S -->|"Best for"| Cls2["Classification"]
    CL_S -->|"Best for"| Emb2["Representation learning"]
```

```figure
cross-entropy-loss
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-mse-and-its-gradient"></a>

### 步骤1：MSE及其Gradient

```python
def mse(predictions, targets):
    n = len(predictions)
    total = 0.0
    for p, t in zip(predictions, targets):
        total += (p - t) ** 2
    return total / n

def mse_gradient(predictions, targets):
    n = len(predictions)
    grads = []
    for p, t in zip(predictions, targets):
        grads.append(2.0 * (p - t) / n)
    return grads
```

<a id="step-2-binary-cross-entropy"></a>

### 步骤2：二进制Cross-Entropy

log(0) 问题是真实存在的。如果模型准确预测正例为 0，则 log(0) = 负无穷大。剪裁可以防止这种情况发生。

```python
import math

def binary_cross_entropy(predictions, targets, eps=1e-15):
    n = len(predictions)
    total = 0.0
    for p, t in zip(predictions, targets):
        p_clipped = max(eps, min(1 - eps, p))
        total += -(t * math.log(p_clipped) + (1 - t) * math.log(1 - p_clipped))
    return total / n

def bce_gradient(predictions, targets, eps=1e-15):
    grads = []
    for p, t in zip(predictions, targets):
        p_clipped = max(eps, min(1 - eps, p))
        grads.append(-(t / p_clipped) + (1 - t) / (1 - p_clipped))
    return grads
```

<a id="step-3-categorical-cross-entropy-with-softmax"></a>

### 步骤3：用Softmax分类Cross-Entropy

Softmax转换原始logits到概率。 然后我们计算cross-entropy针对单一热点目标。

```python
def softmax(logits):
    max_val = max(logits)
    exps = [math.exp(x - max_val) for x in logits]
    total = sum(exps)
    return [e / total for e in exps]

def categorical_cross_entropy(logits, target_index, eps=1e-15):
    probs = softmax(logits)
    p = max(eps, probs[target_index])
    return -math.log(p)

def cce_gradient(logits, target_index):
    probs = softmax(logits)
    grads = list(probs)
    grads[target_index] -= 1.0
    return grads
```

softmax + cross-entropy 的 gradient 简化得很漂亮：它只是真实类别的（预测概率 - 1），以及所有其他类别的（预测概率）。这种优雅的简化并非巧合——这就是 softmax 和 cross-entropy 配对的原因。

<a id="step-4-label-smoothing"></a>

### 第 4 步：标签平滑

```python
def label_smoothed_cce(logits, target_index, num_classes, alpha=0.1, eps=1e-15):
    probs = softmax(logits)
    loss = 0.0
    for i in range(num_classes):
        if i == target_index:
            smooth_target = 1.0 - alpha + alpha / num_classes
        else:
            smooth_target = alpha / num_classes
        p = max(eps, probs[i])
        loss += -smooth_target * math.log(p)
    return loss
```

<a id="step-5-contrastive-loss-simplified-infonce"></a>

### 第 5 步：对比损失（简化 InfoNCE）

```python
def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return dot / (norm_a * norm_b)

def contrastive_loss(anchor, positive, negatives, temperature=0.07):
    sim_pos = cosine_similarity(anchor, positive) / temperature
    sim_negs = [cosine_similarity(anchor, neg) / temperature for neg in negatives]

    max_sim = max(sim_pos, max(sim_negs)) if sim_negs else sim_pos
    exp_pos = math.exp(sim_pos - max_sim)
    exp_negs = [math.exp(s - max_sim) for s in sim_negs]
    total_exp = exp_pos + sum(exp_negs)

    return -math.log(max(1e-15, exp_pos / total_exp))
```

<a id="step-6-mse-vs-cross-entropy-on-classification"></a>

### 第 6 步：MSE 与 Cross-Entropy 的分类

使用 loss functions 训练第 04 课（圆形数据集）中的相同网络。观看 cross-entropy 收敛速度更快。

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


class LossComparisonNetwork:
    def __init__(self, loss_type="bce", hidden_size=8, lr=0.1):
        random.seed(0)
        self.loss_type = loss_type
        self.lr = lr
        self.hidden_size = hidden_size

        self.w1 = [[random.gauss(0, 0.5) for _ in range(2)] for _ in range(hidden_size)]
        self.b1 = [0.0] * hidden_size
        self.w2 = [random.gauss(0, 0.5) for _ in range(hidden_size)]
        self.b2 = 0.0

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

    def backward(self, target):
        if self.loss_type == "mse":
            d_loss = 2.0 * (self.out - target)
        else:
            eps = 1e-15
            p = max(eps, min(1 - eps, self.out))
            d_loss = -(target / p) + (1 - target) / (1 - p)

        d_sigmoid = self.out * (1 - self.out)
        d_out = d_loss * d_sigmoid

        for i in range(self.hidden_size):
            d_relu = 1.0 if self.z1[i] > 0 else 0.0
            d_h = d_out * self.w2[i] * d_relu
            self.w2[i] -= self.lr * d_out * self.h[i]
            for j in range(2):
                self.w1[i][j] -= self.lr * d_h * self.x[j]
            self.b1[i] -= self.lr * d_h
        self.b2 -= self.lr * d_out

    def compute_loss(self, pred, target):
        if self.loss_type == "mse":
            return (pred - target) ** 2
        else:
            eps = 1e-15
            p = max(eps, min(1 - eps, pred))
            return -(target * math.log(p) + (1 - target) * math.log(1 - p))

    def train(self, data, epochs=200):
        losses = []
        for epoch in range(epochs):
            total_loss = 0.0
            correct = 0
            for x, y in data:
                pred = self.forward(x)
                self.backward(y)
                total_loss += self.compute_loss(pred, y)
                if (pred >= 0.5) == (y >= 0.5):
                    correct += 1
            avg_loss = total_loss / len(data)
            accuracy = correct / len(data) * 100
            losses.append((avg_loss, accuracy))
            if epoch % 50 == 0 or epoch == epochs - 1:
                print(f"    Epoch {epoch:3d}: loss={avg_loss:.4f}, accuracy={accuracy:.1f}%")
        return losses
```

<a id="use-it"></a>

## 实际应用

PyTorch 提供所有标准 loss functions 内置的数值稳定性：

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

predictions = torch.tensor([0.9, 0.1, 0.7], requires_grad=True)
targets = torch.tensor([1.0, 0.0, 1.0])

mse_loss = F.mse_loss(predictions, targets)
bce_loss = F.binary_cross_entropy(predictions, targets)

logits = torch.randn(4, 10)
labels = torch.tensor([3, 7, 1, 9])
ce_loss = F.cross_entropy(logits, labels)
ce_smooth = F.cross_entropy(logits, labels, label_smoothing=0.1)
```

使用`F.cross_entropy`（不是`F.nll_loss`加上手册softmax）。它将 log-softmax 和负对数似然结合在一个数值稳定的操作中。单独应用 softmax 然后取对数不太稳定 - 在大指数的减法中会失去精度。

对于 contrastive learning，大多数团队使用自定义实现或库，例如 `lightly` 或 `pytorch-metric-learning`。核心循环始终相同：计算成对相似性，在正负上创建 softmax，反向传播。

<a id="ship-it"></a>

## 交付成果

本课产生：
- `outputs/prompt-loss-function-selector.md`——可重复使用的prompt，用于选择合适的loss function
- `outputs/prompt-loss-debugger.md` - 当您的损失曲线看起来错误时的诊断 prompt

<a id="exercises"></a>

## 练习

1. 实现Huber损失（平滑L1损失），对于小错误是MSE，对于大错误是MAE。当 5% 的训练目标添加了随机噪声（异常值）时，使用 MSE 与 Huber 训练预测 y = sin(x) 的回归网络。比较最终测试误差。

2. 将焦点损失添加到二元分类训练循环中。创建不平衡数据集（90% 类别 0，10% 类别 1）。比较标准 BCE 与焦点损失 (gamma=2) 在 200 个 epoch 后少数类召回率上的情况。

3. 通过半硬负挖掘实现三元组损失。生成 5 个类别的 2D embedding 数据。对于每个锚点，找到仍比正值更远的最难的负值（半困难）。将收敛性与随机三元组选择进行比较。

4. 运行 MSE 与 cross-entropy 比较，但在训练期间跟踪每一层的 gradient 幅度。绘制每个 epoch 的平均 gradient 范数。验证 cross-entropy 在模型最不确定的早期时期是否会产生更大的 gradients。

5. 实施 KL 散度损失并验证最小化 KL(true || 当真实分布是独热时，预测）给出与 cross-entropy 相同的 gradients。然后尝试软目标（例如 knowledge distillation），其中“真实”分布来自教师模型的 softmax 输出。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| Loss function | “这个模型有多么错误” | 可微函数将预测和目标映射到 optimizer 最小化的标量 |
| 均方误差 | “平均平方误差” | 预测与目标之间的均方差；对大错误进行二次惩罚 |
| Cross-entropy | “分类损失” | 使用 -log(p) 测量预测概率分布与真实分布之间的差异 |
| 二进制 cross-entropy | “公元前” | Cross-entropy 对于两个类：-(y*log(p) + (1-y)*log(1-p)) |
| 标签平滑 | “软化目标” | 用软值（例如 0.1/0.9）替换硬 0/1 目标，以防止过度自信并提高泛化能力 |
| 对比损失 | “拉在一起，推开” | 通过在 embedding 空间中使相似对靠近和使不同对远离来学习表示的损失 |
| 信息NCE | “CLIP/SimCLR 损失” | 标准化 temperature 缩放的 cross-entropy 相似度分数；将 contrastive learning 视为分类 |
| 焦点丧失 | “修复不平衡数据” | Cross-entropy 按 (1-p_t)^gamma 加权至下-weight 简单示例，重点关注困难示例 |
| 三重态损失 | “锚定-阳性-阴性” | 在 embedding 空间中将锚点推向正值而不是负值至少一定幅度 |
| Temperature | “锐度旋钮” | logits/similarities 上的标量除数，控制结果分布的峰值程度；更低=更锐利 |

<a id="further-reading"></a>

## 进一步阅读

- Lin 等人，“密集对象检测的焦点损失”(2017)——引入焦点损失来处理对象检测中的极端类别不平衡 (RetinaNet)
- Chen 等人，“A Simple Framework for Contrastive Learning of Visual Representations”（SimCLR，2020）——定义了具有 NT-Xent 损失的现代 contrastive learning 管道
- Szegedy 等人，“重新思考 Inception 架构”（2016 年）——引入了标签平滑作为正则化技术，现已成为大多数大型模型的标准配置
- Hinton 等人，“在神经网络中提取知识”（2015 年）—— knowledge distillation 使用软目标和 KL 散度，这是模型压缩的基础
