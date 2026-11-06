# 代码讲解 · main.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 05 节 Loss Functions ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 0.5 秒跑完） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码把常见损失函数逐个"手搓"出来，再做一个 MSE 与交叉熵的训练对比：

1. **回归损失**：MSE 及其梯度，理解"平方"带来的离群点敏感。
2. **分类损失**：BCE、softmax + 交叉熵，以及它们的梯度；重点是 softmax + CE 的梯度为什么是漂亮的 `p − onehot`。
3. **数值稳定性**：`log(0)` 用 eps 夹紧，softmax 减最大值，对比损失里同样减最大值。
4. **正则化思想**：label smoothing 如何把硬目标变软。
5. **表示学习**：InfoNCE 风格的对比损失和温度 τ 的作用。
6. **训练对比**：同一个网络、同一组初始权重，分别用 MSE 和 BCE 训练。

和上一节一样，这份代码也值得**带着批判看**：STEP 5 的结论文字与自己打印的数字矛盾，STEP 6 的实验并没有显示出讲义所说的"交叉熵收敛更快"，BCE 的反向写法还藏着一个饱和区的数值问题。

> 一句话：**损失函数决定梯度，梯度决定模型学什么**；选损失和实现损失时，都要盯住"在最需要梯度的地方，梯度是否足够大"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `mse` / `mse_gradient` | 函数 | 均方误差及其对每个预测值的梯度 | 回归损失 |
| `binary_cross_entropy` / `bce_gradient` | 函数 | 二元交叉熵（带 eps 夹紧）及其对概率 p 的梯度 | 二分类损失 |
| `softmax` | 函数 | 减最大值的数值稳定 softmax | 输出层 |
| `categorical_cross_entropy` / `cce_gradient` | 函数 | 多分类交叉熵及其对 logits 的梯度 `p − onehot` | 多分类损失 |
| `label_smoothed_cce` | 函数 | 平滑目标下的交叉熵 | Label smoothing |
| `cosine_similarity` / `contrastive_loss` | 函数 | 余弦相似度；单 anchor 的 InfoNCE | 对比学习 |
| `sigmoid` / `make_circle_data` | 函数 | 工具函数与圆形数据（同上一节） | — |
| `LossComparisonNetwork` | 类 | 2-8-1（ReLU 隐藏层 + sigmoid 输出）网络，可选 MSE / BCE | 损失对训练的影响 |
| `if __name__ == "__main__":` | 入口 | STEP 1～6 依次演示 | — |

调用关系：STEP 1～5 直接调用各个损失函数并打印；STEP 6 用 `make_circle_data` 生成数据，构造两个 `LossComparisonNetwork`（`loss_type="mse"` 与 `"bce"`）分别训练。

---

## 3. 逐段精讲

### 3.1 MSE 与梯度

```python
def mse(predictions, targets):
    assert len(predictions) == len(targets), "predictions and targets must have the same length"
    n = len(predictions)
    total = 0.0
    for p, t in zip(predictions, targets):
        total += (p - t) ** 2
    return total / n


def mse_gradient(predictions, targets):
    # ...
    for p, t in zip(predictions, targets):
        grads.append(2.0 * (p - t) / n)
    return grads
```

- `MSE = (1/n)Σ(p − t)²`，梯度 `∂MSE/∂pᵢ = 2(pᵢ − tᵢ)/n`。梯度与误差**成正比**：误差大的样本"说话声音大"——这对回归是好事（大误差需要大修正），也是离群点会主导训练的原因。
- `assert len(...) == len(...)`：和前几节不同，这里**显式检查长度**，防止 `zip` 静默截断。这是一个好习惯。
- 梯度里的 `/ n` 与 loss 的"取平均"对应。如果 loss 改成求和，梯度就不该除以 n——两者必须一致。

### 3.2 BCE：eps 夹紧

```python
def binary_cross_entropy(predictions, targets, eps=1e-15):
    # ...
    for p, t in zip(predictions, targets):
        p_clipped = max(eps, min(1 - eps, p))
        total += -(t * math.log(p_clipped) + (1 - t) * math.log(1 - p_clipped))
    return total / n


def bce_gradient(predictions, targets, eps=1e-15):
    # ...
    for p, t in zip(predictions, targets):
        p_clipped = max(eps, min(1 - eps, p))
        grads.append((-(t / p_clipped) + (1 - t) / (1 - p_clipped)) / n)
    return grads
```

- 公式 `BCE = −[t·log p + (1−t)·log(1−p)]`。当 `t = 1` 时只剩 `−log p`，`t = 0` 时只剩 `−log(1−p)`。
- **为什么要夹紧**：p 恰好为 0 或 1 时 `math.log(0)` 会抛 `ValueError: math domain error`（Python 不会返回 `-inf`）。夹到 `[1e−15, 1 − 1e−15]` 后，最大单样本损失约为 `−ln(1e−15) ≈ 34.5`。
- 梯度 `∂BCE/∂p = −t/p + (1−t)/(1−p)`：t = 1 且 p → 0 时趋于 −∞，"自信地错"得到巨大的修正信号。
- 代码的 `bce_gradient` 除以了 n，与均值形式的 `binary_cross_entropy` 对应；讲义 Step 2 中的版本没有除以 n，两者不一致，以代码为准。
- ⚠️ 这里的梯度是对**概率 p** 的，不是对 logit 的。真实网络中通常直接对 logit 求导，此时 sigmoid 与 log 合并后梯度化简为 `p − t`（见 3.8）。

### 3.3 softmax + 多分类交叉熵

```python
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

- 目标用**类别下标** `target_index` 而不是 one-hot 向量：one-hot 中只有目标类为 1，`−Σ yᵢ log pᵢ` 只剩 `−log p_target`，直接取下标更高效（PyTorch 的 `F.cross_entropy` 也接收下标）。
- `cce_gradient` 是对 **logits** 的梯度：`p − onehot`。`list(probs)` 先复制一份 softmax 结果，再把目标类减 1。推导：`L = −x_t + log Σ e^(x_j)`，`∂L/∂x_i = p_i − [i = t]`。
- 梯度各分量之和为 0：softmax 只关心 logits 的相对大小，整体平移不改变结果，所以沿"全 1 方向"的梯度为 0。
- ⚠️ 先算 softmax 再取 log 的做法在极端 logits 下会丢精度（概率下溢为 0 后只能靠 eps 兜底）。生产中用 log-softmax：`log p_t = x_t − m − log Σ e^(x_j − m)`。

### 3.4 Label smoothing

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

- 平滑目标 `s = (1 − α)·onehot + α/K`：真类 `1 − α + α/K`，其余 `α/K`。α = 0.1、K = 5 时是 0.92 / 0.02。
- loss 变成"对平滑分布的交叉熵" `−Σ sᵢ log pᵢ`，所有类都参与，不再只有目标类。
- 硬目标要求 `p_target → 1`，这需要 logit 间隔趋于无穷；平滑目标的最优解是有限的 logits，从而抑制过度自信。可以证明平滑后多出的损失恰好是 `(α/K)·Σ_{i≠t}(x_t − x_i)`——真类 logit 领先越多，罚得越多（测验 Q10）。
- ⚠️ 入口处打印 "targeting 0.9 instead of 1.0"，对 5 类其实是 0.92；`num_classes` 需要调用者传入且必须等于 `len(logits)`，代码没有检查。

### 3.5 余弦相似度与对比损失

```python
def cosine_similarity(a, b):
    assert len(a) == len(b), "vectors must have the same length"
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

- 零向量保护：模长接近 0 时返回相似度 0，避免除以 0。
- `contrastive_loss` 就是"以正样本为正确类别"的 softmax 交叉熵：候选是 1 个正样本 + 若干负样本，logit 是 `余弦相似度 / τ`。注意**分母包含正样本本身**（`exp_pos + sum(exp_negs)`），这与 SimCLR 的 NT-Xent 一致。
- 同样**减去最大值**防溢出：τ = 0.07 时相似度 1 对应 logit 约 14.3，还不会溢出，但 τ 再小、维度再多就可能出问题，养成习惯很重要。
- `max(sim_negs) if sim_negs else sim_pos` 处理"没有负样本"的边界情况（此时 loss 恒为 0）。
- ⚠️ 简化：只算一个 anchor、没有梯度、相似度不可学习。真实实现会一次算出 batch 内 `2N × 2N` 的相似度矩阵，再对每行做交叉熵。

### 3.6 STEP 2 中的"置信度表"

```python
    for conf in [0.01, 0.1, 0.5, 0.9, 0.99]:
        ce = -(1.0 * math.log(max(1e-15, conf)))
        ms = (conf - 1.0) ** 2
        print(f"    p={conf:.2f}: CE={ce:.4f}, MSE={ms:.4f}, ratio={ce/max(0.0001, ms):.1f}x")
```

- 对真实标签 1，逐个列出 CE 和 MSE。`max(0.0001, ms)` 防止除以 0。
- 读表要看**同一列内**的变化：CE 从 0.01（p=0.99）到 4.6（p=0.01），相差约 460 倍，MSE 只从 0.0001 到 0.98。`ratio` 一列（CE/MSE）在 p 接近 1 时最大（100.5x），它说明的是"两种损失量纲不同"，并不直接支持"CE 更严惩错误"的论点——支持这个论点的是 CE 列本身无上界，以及梯度的行为。

### 3.7 `LossComparisonNetwork` 的前向

```python
class LossComparisonNetwork:
    def __init__(self, loss_type="bce", hidden_size=8, lr=0.1):
        random.seed(0)
        # ...
        self.w1 = [[random.gauss(0, 0.5) for _ in range(2)] for _ in range(hidden_size)]
        # ...

    def forward(self, x):
        # ...
        for i in range(self.hidden_size):
            z = self.w1[i][0] * x[0] + self.w1[i][1] * x[1] + self.b1[i]
            self.z1.append(z)
            self.h.append(max(0.0, z))

        self.z2 = sum(self.w2[i] * self.h[i] for i in range(self.hidden_size)) + self.b2
        self.out = sigmoid(self.z2)
        return self.out
```

- 和上一节的 `ActivationNetwork` 几乎相同，只是隐藏层固定为 **ReLU**（`max(0.0, z)`），变量换成了损失类型 `loss_type`。
- `random.seed(0)` 在 `__init__` 中，MSE 与 BCE 两个网络的初始权重完全相同，是干净的对照实验。

### 3.8 `backward`：两种损失、一个饱和区隐患

```python
    def backward(self, target):
        if self.loss_type == "mse":
            d_loss = 2.0 * (self.out - target)
        else:
            eps = 1e-15
            p = max(eps, min(1 - eps, self.out))
            d_loss = -(target / p) + (1 - target) / (1 - p)

        d_sigmoid = self.out * (1 - self.out)
        d_out = d_loss * d_sigmoid
```

- 统一写成"`dL/dp` × `dp/dz`"的链式法则：
  - MSE：`d_out = 2(p − y)·p(1−p)`。p 接近 0 或 1 时 `p(1−p) → 0`，**饱和区梯度消失**——这就是讲义说的"MSE gradient flattens near 0 and 1"。
  - BCE：`d_out = [(p − y)/(p(1−p))]·p(1−p) = p − y`，饱和被抵消。
- ⚠️ **数值隐患**：BCE 分支里 `d_loss` 用的是夹紧后的 p，而 `d_sigmoid` 用的是真实的 `self.out`，二者在极端情况下不再抵消。实测 `z2 = −40`、`target = 1` 时，代码得到 `d_out ≈ −0.00425`（应为 −1）；`self.out` 恰好等于 1.0（`z2` 大于约 37）、`target = 0` 时，`d_out = 0`（应为 1）。也就是说，在交叉熵本该给出最强梯度的"自信地错"情形，这段代码反而把梯度弄没了。本次训练中 z2 没有到这种程度，所以输出不受影响；修正方法是 BCE 分支直接写 `d_out = self.out - target`（测验 Q9）。PyTorch 的 `BCEWithLogitsLoss` 就是这么做的。

```python
        for i in range(self.hidden_size):
            d_relu = 1.0 if self.z1[i] > 0 else 0.0
            d_h = d_out * self.w2[i] * d_relu
            self.w2[i] -= self.lr * d_out * self.h[i]
            for j in range(2):
                self.w1[i][j] -= self.lr * d_h * self.x[j]
            self.b1[i] -= self.lr * d_h
        self.b2 -= self.lr * d_out
```

- 与上一节相同：先用旧的 `w2[i]` 算出 `d_h`，再更新 `w2[i]`；ReLU 的导数 `d_relu` 用激活前的 `z1[i]` 判断。

### 3.9 `compute_loss` 与 `train`

```python
    def compute_loss(self, pred, target):
        if self.loss_type == "mse":
            return (pred - target) ** 2
        else:
            eps = 1e-15
            p = max(eps, min(1 - eps, pred))
            return -(target * math.log(p) + (1 - target) * math.log(1 - p))
```

- 单样本损失，仅用于打印；`train` 里先 `forward` 拿到 `pred`，接着 `backward` 更新，再用（更新前的）`pred` 计算 loss，所以打印的是"边训练边统计"的值。
- `train` 返回 `(avg_loss, accuracy)` 元组的列表，入口处用 `final_loss, final_acc = results[-1]` 解包最后一个 epoch。
- ⚠️ MSE 和 BCE 的 loss **量纲不同**，不能拿 "MSE 最终 0.0086 < BCE 最终 0.0219" 说明 MSE 更好或更差；要比较就比准确率、或者在同一种度量下比。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 每个损失独立成纯函数，并配一个梯度函数 | 公式与代码一一对应，方便单独测试 | 生产中用框架的融合损失（`F.cross_entropy` 等）和自动求导 |
| `assert` 检查长度 | 防止 `zip` 静默截断 | `assert` 在 `python -O` 下会被跳过，正式校验应 `raise ValueError` |
| eps = 1e-15 夹紧概率 | 防止 `log(0)` 报错 | 夹紧会让梯度在饱和区失真；更好的做法是直接从 logits 计算（log-sum-exp） |
| 多分类目标用下标 | 只需取目标类概率，高效 | 软标签（蒸馏、label smoothing）需要分布形式的目标 |
| softmax / 对比损失都减最大值 | 数值稳定 | — |
| 对比损失只算单个 anchor | 突出公式本身 | 实际用 batch 相似度矩阵，一次算全部 |
| BCE 反向写成 `dL/dp × σ'` | 与 MSE 分支结构统一，便于对照 | 饱和时梯度失真；应直接用 `p − y` |
| 两个网络 `random.seed(0)` 同初始化 | 对照实验只有一个变量 | 单一种子，结论的统计意义有限 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `assert` 语句 | `assert len(predictions) == len(targets), "..."` | 条件为假时抛 `AssertionError` 并附带信息；常用于开发期自检 |
| 默认参数 | `eps=1e-15`、`temperature=0.07`、`loss_type="bce"` | 科学计数法 `1e-15` 表示 10⁻¹⁵ |
| 嵌套 `max/min` 夹紧 | `max(eps, min(1 - eps, p))` | 把 p 限制在 `[eps, 1-eps]` |
| `list()` 复制 | `grads = list(probs)` | 新建一个列表，修改它不影响 `probs` |
| 原地减法 | `grads[target_index] -= 1.0` | 修改列表中的一个元素 |
| 条件表达式 + 函数调用 | `max(sim_pos, max(sim_negs)) if sim_negs else sim_pos` | 空列表时 `max([])` 会报错，先判断再调用 |
| 列表推导 | `[cosine_similarity(anchor, neg) / temperature for neg in negatives]` | 对每个负样本计算缩放相似度 |
| 嵌套列表推导 | `[[random.gauss(0, 1) for _ in range(8)] for _ in range(7)]` | 生成 7 个 8 维向量 |
| f-string 内嵌列表推导 | `f"{[f'{g:.4f}' for g in mse_gradient(preds, targets)]}"` | 把每个数格式化成字符串后打印列表（所以输出带引号） |
| 字符串方法 | `loss_type.upper()` | `"mse" → "MSE"` |
| 元组列表与解包 | `losses.append((avg_loss, accuracy))`；`final_loss, final_acc = results[-1]` | 一次返回 / 取出多个值 |
| 布尔比较 | `(pred >= 0.5) == (y >= 0.5)` | 判断预测类别与真实类别是否一致 |
| `if __name__ == "__main__":` | 文件末尾 | 被导入时只提供函数和类 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，约 0.5 秒）的输出（节选）：

```text
STEP 1: MSE Loss
  Predictions: [0.9, 0.1, 0.7, 0.4]
  Targets:     [1.0, 0.0, 1.0, 0.0]
  MSE Loss:    0.067500
  MSE Grads:   ['-0.0500', '0.0500', '-0.1500', '0.2000']
```

- `(0.01 + 0.01 + 0.09 + 0.16)/4 = 0.0675`；梯度 `2(p − t)/4`：误差最大的第 4 个样本（0.4 vs 0）梯度最大。

```text
STEP 2: Binary Cross-Entropy
  BCE Loss:    0.269555
  BCE Grads:   ['-0.2778', '0.2778', '-0.3571', '0.4167']

  CE loss at different confidence levels (true label = 1):
    p=0.01: CE=4.6052, MSE=0.9801, ratio=4.7x
    p=0.50: CE=0.6931, MSE=0.2500, ratio=2.8x
    p=0.99: CE=0.0101, MSE=0.0001, ratio=100.5x
```

- BCE 梯度：`−1/(0.9·4) = −0.2778`、`1/(0.6·4) = 0.4167`，同样是错得最多的样本梯度最大，但相对差距比 MSE 更大（与 1/p 成正比）。
- 置信度表的读法见 3.6。

```text
STEP 3: Categorical Cross-Entropy + Softmax
  Softmax: ['0.2333', '0.0858', '0.0349', '0.0116', '0.6343']
  CCE Loss: 0.455241
  Gradient: ['0.2333', '0.0858', '0.0349', '0.0116', '-0.3657']
```

- `−ln 0.6343 = 0.4552`；梯度 = `p − onehot`，目标类为 `0.6343 − 1 = −0.3657`。

```text
STEP 4: Label Smoothing
  Hard target loss:    0.455241
  Smooth target loss:  0.653241
  Smoothing increases loss by 0.198000
```

- 差值恰好是 `(α/K)·Σ_{i≠t}(x_t − x_i) = 0.02 × (1 + 2 + 2.9 + 4) = 0.198`。即使模型已经把目标类放在第一位，平滑目标仍然在"惩罚"它把其他类压得太低。

```text
STEP 5: Contrastive Loss
  Anchor-positive similarity: 0.9946
  Contrastive loss (tau=0.07): 0.0042
  Contrastive loss (tau=0.5):  0.9391
  Lower temperature = sharper = higher loss for imperfect separation
```

- ⚠️ 最后一行与上面的数字**矛盾**：低温度的 loss 反而更小。原因是本例分离完美（正样本 0.9946 远高于最大的负样本 0.5705），低温只会让正样本更"独占"概率。"低温 → 更高 loss"只在存在比正样本更相似的难负样本时成立（测验 Q8 给了反例：τ = 0.07 时 6.09，τ = 0.5 时 1.94）。

```text
STEP 6: MSE vs Cross-Entropy on Classification
--- Training with MSE ---
    Epoch   0: loss=0.2071, accuracy=67.0%
    Epoch  50: loss=0.0192, accuracy=98.0%
    Epoch 199: loss=0.0086, accuracy=99.0%
--- Training with BCE ---
    Epoch   0: loss=0.5542, accuracy=68.5%
    Epoch  50: loss=0.0444, accuracy=98.0%
    Epoch 199: loss=0.0219, accuracy=99.0%
```

- 两者最终都达到 99% 训练准确率，第 50 轮都是 98%。额外逐轮统计可以看到：BCE 在前 4 轮略快（第 3 轮 92.5% vs 85.0%），但 MSE 第 5 轮先达到 95%，BCE 要到第 8 轮。所以**在这个浅层 ReLU 网络上，并没有观察到讲义和结尾 "Key Takeaway" 所说的"交叉熵明显收敛更快"**。原因是输出层很少进入饱和区——MSE 的劣势在输出饱和、网络更深、类别更多时才明显。
- 两列 loss 的数值不能横向比较（量纲不同），见 3.9。

---

## 7. 动手改一改

1. **修复 BCE 反向**：把 BCE 分支改为 `d_out = self.out - target`，构造一个让 `z2` 很大的初始化（例如把 `b2` 设成 50），对比原版和修复版的第一步梯度。
2. **制造饱和、重做对比**：把 `w2` 的初始化改成 `random.gauss(0, 5)`（让输出一开始就饱和），重跑 MSE vs BCE，观察两者的差距是否变大，并打印每个 epoch 的平均 `|d_out|`（讲义练习 4）。
3. **Huber loss**：实现 `huber(pred, target, delta=1.0)` 及梯度，在含 5% 离群点的 `y = sin(x)` 回归上与 MSE 比较（讲义练习 1）。
4. **Focal loss**：在 BCE 分支加入 `(1 − p_t)^γ` 权重（注意梯度要重新推导或用数值梯度验证），在 90/10 的不平衡数据上比较少数类召回率（讲义练习 2）。
5. **温度扫描**：对 STEP 5 的 anchor，把 τ 从 0.01 扫到 10，分别在"正样本最相似"和"加入一个难负样本"两种设置下画出 loss 曲线，验证 τ → ∞ 时 loss → `ln(候选数)`。
6. **KL 与交叉熵**：实现 `kl_divergence(q, p)`，验证 one-hot 目标时它与交叉熵相等、soft target 时两者只差一个常数 `H(q)`（讲义练习 5）。

---

## 8. 常见坑

- **`math.log(0)` 报错**：Python 抛 `ValueError` 而不是返回 `-inf`；必须夹紧，或者从 logits 直接计算。
- **先 softmax / sigmoid 再用"带 logits"的损失**：等于做了两次激活，不报错但训练变慢。
- **链式法则拆开算在饱和区失真**：`dL/dp` 用夹紧值、`dp/dz` 用真实值，梯度不再抵消（本文件 BCE 分支）。
- **不同损失的数值直接比较**：MSE 与 BCE 的 loss 量纲不同，只能比各自的下降趋势或共同的指标。
- **loss 均值与梯度不对应**：loss 取均值时梯度要除以 n，取和时不除，混用会让等效学习率随 batch 大小变化。
- **温度方向记反**：低温不等于"loss 一定更大"，要看正样本是否已经排在第一。
