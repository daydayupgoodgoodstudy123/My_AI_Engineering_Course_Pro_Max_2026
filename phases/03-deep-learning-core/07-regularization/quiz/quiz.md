# 测验 · 正则化（Regularization）

> **阶段 03 · 深度学习核心 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 过拟合与泛化差距 | 训练表现远好于测试表现 = 记住了噪声；`gap = train_acc - test_acc` 是诊断正则化强度的首要指标 |
| 2 | Dropout（inverted dropout） | 训练时每个神经元以概率 p 置 0，保留的除以 `1-p`；推理时原样输出。期望值不变，推理代码不需要知道 dropout |
| 3 | Dropout 的反向传播与集成解释 | 梯度用同一个 mask、乘同一个 `1/(1-p)`；可看作同时训练 2ᴺ 个共享权重的子网络，推理时近似为它们的平均 |
| 4 | L2 / weight decay | 损失加 `(λ/2)·Σw²`，梯度多 `λw`；SGD 下等价于每步 `w *= (1 - lr·λ)`，Adam 下不等价，应该用 AdamW |
| 5 | BatchNorm | 每个特征在 **batch 维**上求均值方差再归一化，`γ、β` 可学习；训练用 batch 统计量，推理用 running 统计量（momentum=0.1） |
| 6 | BatchNorm 为什么有效 | 原论文的"内部协变量偏移"解释被 Santurkar 等（2018）质疑；更被认可的解释是它让 loss 曲面更平滑，允许更大的学习率 |
| 7 | LayerNorm | 每个样本在**特征维**上归一化，与 batch 大小无关、训练推理一致，所以 Transformer 用它；Pre-LN 比 Post-LN 更稳定 |
| 8 | RMSNorm | LayerNorm 去掉减均值和 β：`y = γ·x/rms(x)`；更省计算，LLaMA、Mistral 等现代 LLM 采用 |
| 9 | 数据增强与早停 | 增强 = 扩大有效训练集；早停 = 监控验证 loss，耐心窗口（5–20 epoch）内不改善就停止并回滚到最佳权重 |
| 10 | `model.train()` / `model.eval()` | 控制 dropout 开关和 BN 用哪种统计量；推理前忘记 `eval()` 是最常见的 bug 之一 |

### 核心技能（能动手做到）

- [ ] 从零实现 inverted dropout 的 `forward` / `backward`，并用大量随机试验验证"训练时输出的期望 = 原输入"
- [ ] 从零实现 BatchNorm（含 running mean/var 的 EMA 更新）、LayerNorm、RMSNorm，并验证 LN 输出均值 0、标准差 1，RMSNorm 输出 rms 为 1
- [ ] 在手写 SGD 的反向传播里加入 weight decay，并打印训练前后权重的 L2 范数验证它确实在收缩
- [ ] 正确测量泛化差距：训练集和测试集都在 eval 模式下评估，解释为什么"边训练边统计"的训练准确率会让带 dropout 的模型出现负 gap
- [ ] 为 `RegularizedNetwork` 加上 early stopping（patience + 保存/恢复最佳权重）
- [ ] 根据泛化差距大小（>10% / 5–10% / <5%）给出 dropout 率、weight decay 和其他手段的组合建议

---

## 二、基础自测（选择题）

**Q1.** 使用 inverted dropout，p=0.3。训练时某个神经元的激活值是 2.0 且**没有被丢弃**，它的输出是：

- A. 2.0
- B. 1.4
- C. 约 2.857
- D. 0.6

**Q2.** 为什么主流实现在**训练时**除以 `1-p`（inverted dropout），而不是在测试时乘以 `1-p`？

- A. 这样训练更快
- B. 让训练时输出的期望与推理时一致，推理代码完全不需要知道 dropout 的存在
- C. 这样能减小梯度方差
- D. 这样能让被丢弃的神经元也收到梯度

**Q3.** 一个处于训练模式的 BatchNorm 层，如果某次输入的 batch 大小为 1，默认初始化（γ=1、β=0）下它的输出是：

- A. 和输入完全相同
- B. 全部等于 β（即全 0），输入信息被抹掉
- C. NaN，因为方差为 0
- D. 和 LayerNorm 的输出相同

**Q4.** 关于 RMSNorm，下面哪种说法正确？

- A. 输出的均值一定为 0
- B. 没有 β 参数，输出的均方根约为 1，但均值不一定为 0
- C. 训练时使用 batch 统计量，推理时使用 running 统计量
- D. 比 LayerNorm 多一个可学习参数

**Q5.** 损失为 `L + (λ/2)·Σw²`，用学习率 η 的普通 SGD 更新，单步更新等价于：

- A. `w ← w - η·g - λ`
- B. `w ← (1 - η·λ)·w - η·g`
- C. `w ← (1 - λ)·w - η·g`
- D. `w ← w - η·(g + λ)·w`

**Q6.** BatchNorm 的 `running_mean` 初始化为 0、momentum=0.1。若连续 10 个 batch 的均值都是 3.0，第 10 个 batch 之后 `running_mean` 约为：

- A. 3.0
- B. 约 1.95
- C. 0.3
- D. 约 2.7

**Q7.** 一个含 Dropout 和 BatchNorm 的模型，推理前**忘记调用** `model.eval()`，最可能出现的现象是：

- A. 输出确定但略有偏差
- B. 同一输入多次推理结果不同；BN 用当前 batch 的统计量，batch 很小时输出严重失真
- C. 完全没有影响
- D. PyTorch 会直接报错

---

## 三、动手 / 代码题

**Q8.** `main.py` STEP 1 的实际输出如下（`p=0.5`，`random.seed(42)`）：

```text
  Input:          [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
  Train pass 1:   ['2.0', '0.0', '0.0', '0.0', '10.0', '12.0', '14.0', '0.0']  (4/8 active)
  ...
  Eval pass:      ['1.0', '2.0', '3.0', '4.0', '5.0', '6.0', '7.0', '8.0']
  Train mean: ~4.5 (scaled by 1/(1-p))
  Eval mean:   4.5 (no scaling needed)
```

(a) 为什么保留下来的值恰好是原值的 2 倍？(b) Train pass 1 的实际均值是多少？"Train mean: ~4.5" 这一行打印的到底是什么？(c) 统计激活数的这一行 `active = sum(1 for v in output if v > 0)` 在什么输入下会算错？

**Q9.** STEP 5 的实际最终对比为：

```text
  Config                          Train Acc   Test Acc      Gap
  No regularization                   99.3%      97.3%     2.0%
  Dropout p=0.3                       96.0%      98.0%    -2.0%
  Weight decay 0.01                   96.7%      94.0%     2.7%
  Dropout + weight decay              87.3%      90.7%    -3.3%

  Key insight: regularization reduces the train-test gap.
  The model with dropout + weight decay generalizes best,
  even if its training accuracy is lower.
```

(a) 为什么带 dropout 的配置会出现**负的** gap？请指出 `train_model` 中导致这一现象的写法。(b) 末尾写死的结论"dropout + weight decay generalizes best"和数据是否一致？(c) 你会怎样修改实验，让它真正能体现正则化的价值？

**Q10.** 讲义 Build It 中 `RegularizedNetwork.backward` 的写法如下，而 `code/main.py` 的版本多了几行。请找出讲义版本在 `dropout_p > 0` 时的 bug，并说明 `main.py` 是如何修复的。

```python
    def backward(self, target):
        # ... 计算 d_out
        for i in range(self.hidden_size):
            d_relu = 1.0 if self.z1[i] > 0 else 0.0
            d_h = d_out * self.w2[i] * d_relu
            self.w2[i] -= self.lr * (d_out * self.h[i] + self.weight_decay * self.w2[i])
            for j in range(2):
                self.w1[i][j] -= self.lr * (d_h * self.x[j] + self.weight_decay * self.w1[i][j])
            self.b1[i] -= self.lr * d_h
        self.b2 -= self.lr * d_out
```

**Q11.** 为 `RegularizedNetwork` 写一个函数 `train_with_early_stopping(net, train_data, val_data, max_epochs=1000, patience=20)`：每个 epoch 训练一遍后在验证集上算 loss，记录并保存最佳权重；连续 `patience` 个 epoch 没有改善就停止，最后恢复最佳权重，返回最佳 epoch 和实际训练的 epoch 数。

---

## 四、面试高频题

**Q12.**（基础必考）讲一下 Dropout 的原理：训练和推理时分别怎么做？为什么要缩放？为什么 Transformer 里常用 p=0.1，而 MLP 常用 0.5？

**Q13.**（原理深挖）对比 BatchNorm、LayerNorm、RMSNorm：分别在哪个维度上归一化？训练和推理有什么区别？为什么 Transformer 用 LayerNorm、现代 LLM 又改用 RMSNorm？

**Q14.**（追问型）BatchNorm 在训练和推理时行为不同。如果一个带 BN 的 CNN 在验证集上的效果比训练时差很多，你会怀疑哪些原因？微调时 batch 很小又该怎么处理？

**Q15.**（场景设计）你的模型训练准确率 99%，验证准确率 70%。请给出一个系统的诊断和正则化方案，并说明按什么顺序尝试。

**Q16.**（原理深挖）L2 正则 / weight decay 为什么能提升泛化？它和贝叶斯观点有什么关系？工程上哪些参数通常不做 weight decay？

---

## 五、参考答案与解析

### Q1 — 答案：C

保留的神经元输出 `2.0 / (1 - 0.3) = 2.0 / 0.7 ≈ 2.857`。这样该神经元输出的期望为 `0.7 × 2.857 + 0.3 × 0 = 2.0`，与推理时不做 dropout 的输出一致。B 是"测试时乘以 1-p"那种老式写法在训练时的错误类比；D 是把 p 当成保留概率乘上去。

### Q2 — 答案：B

两种写法期望都对齐，但 inverted dropout 把缩放放在训练阶段，推理阶段 dropout 就是恒等映射，导出、部署、量化时都不用特殊处理（讲义："test code doesn't need to know about dropout at all"）。A、C 都不是设计动机；D 错：被丢弃的神经元梯度为 0，与缩放放在哪里无关。

### Q3 — 答案：B

batch 大小为 1 时，每个特征的 batch 均值就是该样本本身，`x - μ = 0`，方差为 0；分母有 ε 所以不会出现 NaN（C 错），归一化结果全是 0，输出 `γ·0 + β = β`。输入信息被完全抹掉，这就是讲义说的"batch size 为 1 时均值和方差没有意义"。PyTorch 的 `BatchNorm1d` 在训练模式下遇到每通道只有 1 个值的输入会直接报错，也是为了防止这种情况。

### Q4 — 答案：B

`y = γ·x / rms(x)`，没有减均值、没有 β。输出的 rms 约为 1（γ=1 时），但均值不为 0。代码 STEP 3 的输出就是例证：`RMSNorm output: mean=0.9900, rms=1.0000`。C 描述的是 BatchNorm；RMSNorm 只有 γ 一个参数向量，比 LayerNorm 少 β（D 错）。

### Q5 — 答案：B

梯度 = `g + λw`，`w ← w - η(g + λw) = (1 - ηλ)·w - η·g`。所以 SGD 中 L2 正则等价于每步把权重乘以 `(1 - ηλ)`，即 weight decay，衰减系数是 `ηλ` 而不是 λ（C 错）。这种等价性在 Adam 中被打破，因为 `λw` 会被自适应因子缩放（见上一节 AdamW）。

### Q6 — 答案：B

`running_mean = 0.9 × running_mean + 0.1 × 3`，从 0 开始迭代 10 次：`3 × (1 - 0.9¹⁰) = 3 × 0.651 ≈ 1.95`。running 统计量是 EMA，需要足够多的 batch 才能"预热"到真实值。代码 STEP 4 中均值从 3.0 线性增长到 3.9，10 个 batch 后 running_mean 只有约 2.3，也是同样的原因。

### Q7 — 答案：B

`train()` 模式下 dropout 仍然随机置零，同一输入每次结果不同；BN 用当前 batch 的均值方差而不是训练积累的 running 统计量，batch 很小（如 1）时输出严重失真，而且同一样本的预测会受同 batch 其他样本影响。PyTorch 不会报错（D 错），这正是这个 bug 隐蔽的原因。

### Q8 — 参考答案

(a) `p=0.5`，保留的值除以 `1 - 0.5 = 0.5`，即乘以 2：`1.0→2.0`、`5.0→10.0`、`6.0→12.0`、`7.0→14.0`。

(b) 实际均值 = `(2 + 10 + 12 + 14) / 8 = 38 / 8 = 4.75`，不是 4.5。代码中这一行是：

```python
print(f"  Train mean: ~{sum(test_input)/len(test_input):.1f} (scaled by 1/(1-p))")
```

它打印的是**输入**的均值，即训练模式下输出的**期望值**，而不是某一次前向的真实均值。单次前向的均值会在期望附近波动（第 2 次只有 3 个保留，均值 `(8+14+16)/8 = 4.75`），只有对大量随机 mask 取平均才会趋近 4.5。

(c) `v > 0` 把"值为正"当成"未被丢弃"。如果输入里有 0 或负数（例如 dropout 放在 tanh 之后，或者输入本身是 0），未被丢弃的负值/零值会被误计为"丢弃"。更可靠的写法是直接统计 `sum(drop.mask)`。

### Q9 — 参考答案

(a) `train_model` 中的训练准确率是"边训练边统计"的：

```python
for x, y in train_data:
    pred = self.forward(x, training=True)
    self.backward(y)
    # ... 用 pred 统计 correct
```

`pred` 是在 **dropout 开启**的状态下得到的（每次随机丢掉 30% 的隐藏单元），并且是每一步更新**之前**的预测；而测试准确率由 `evaluate` 在 `training=False` 下得到。两者不是同一种测量，带 dropout 的模型训练准确率被系统性低估，于是 gap 变成负数。在 eval 模式下重新评估训练集，真实数字是：

| 配置 | 训练准确率（eval 模式） | 测试准确率 | 真实 gap |
|------|---------------------|-----------|---------|
| No regularization | 99.3% | 97.3% | 2.0% |
| Dropout p=0.3 | 99.3% | 98.0% | 1.3% |
| Weight decay 0.01 | 96.7% | 94.0% | 2.7% |
| Dropout + weight decay | 93.3% | 90.7% | 2.7% |

(b) 不一致。"Dropout + weight decay" 的测试准确率 90.7% 是四个配置里**最低**的，它是欠拟合而不是"泛化最好"。真正测试准确率最高的是 Dropout p=0.3（98.0%）。这段结论是写死的字符串，不随运行结果变化。

(c) 改进思路：

- 让基线真正过拟合：基线 gap 只有 2%，正则化几乎没有发挥空间。可以减少训练样本（如 30 个）、给标签加噪声（随机翻转 10–20%）、加大隐藏层，制造明显的 gap。
- 正确测量：每个 epoch 用 `evaluate(train_data)` 和 `evaluate(test_data)` 都在 eval 模式下评估。
- 调整强度：这里 weight decay 每步收缩 `lr·λ = 0.05 × 0.01 = 5e-4`，150 样本 × 300 epoch = 45,000 步，累积效果非常强（实测 w1、w2 的 L2 范数从约 15.8 降到 5.5，叠加 dropout 后约 5.0），可以把 λ 降到 1e-3 或 1e-4 再比较。
- 多随机种子取平均，150 个测试样本中 1 个样本就是 0.67%，单次运行的差异很可能是噪声。

### Q10 — 参考答案

Bug：讲义版本的 `d_h = d_out * self.w2[i] * d_relu` 完全没有考虑 dropout。

- 对**被丢弃**的神经元：它在前向中输出被置 0，对 loss 没有任何贡献，正确梯度应为 0；讲义版本却仍然给它的 `w1`、`b1` 传了非零梯度。
- 对**保留**的神经元：前向时乘了 `1/(1-p)`，反向也应乘同样的系数；讲义版本漏掉了这个系数。

（`w2` 的梯度 `d_out * self.h[i]` 是对的，因为 `self.h` 已经是 dropout 之后的值。）

`main.py` 的修复：

```python
        d_h_dropout = [d_out * self.w2[i] for i in range(self.hidden_size)]
        if self.dropout and self.dropout.mask is not None:
            d_h_dropout = [g * m / (1 - self.dropout.p) if m else 0.0
                           for g, m in zip(d_h_dropout, self.dropout.mask)]

        for i in range(self.hidden_size):
            d_relu = 1.0 if self.z1[i] > 0 else 0.0
            d_h = d_h_dropout[i] * d_relu
```

先算出对 dropout 输出的梯度，再乘以 `mask / (1-p)`，与 `Dropout.backward` 的逻辑完全一致。另一个细节：`d_h_dropout` 在循环之前一次性用**旧的** `w2` 算好，避免循环中 `self.w2[i]` 被更新后再参与梯度计算。

### Q11 — 参考答案

```python
import copy

def train_with_early_stopping(net, train_data, val_data, max_epochs=1000, patience=20):
    best_loss = float("inf")
    best_epoch = -1
    best_state = None
    waited = 0
    for epoch in range(max_epochs):
        for x, y in train_data:
            net.forward(x, training=True)
            net.backward(y)
        val_loss, val_acc = net.evaluate(val_data)
        if val_loss < best_loss - 1e-6:          # 有实质改善才算
            best_loss, best_epoch, waited = val_loss, epoch, 0
            best_state = copy.deepcopy((net.w1, net.b1, net.w2, net.b2))
        else:
            waited += 1
            if waited >= patience:
                break
    net.w1, net.b1, net.w2, net.b2 = best_state  # 回滚到最佳权重
    return best_epoch, epoch + 1
```

要点：

- 用 `copy.deepcopy` 保存权重。`w1` 是嵌套列表，浅拷贝只复制外层，后续训练会改坏"最佳权重"。
- 监控 **loss** 而不是准确率：loss 更平滑，准确率在小数据集上是离散跳变的。
- `1e-6` 的最小改善量（PyTorch Lightning 等框架里叫 `min_delta`）防止数值噪声不断重置耐心计数。
- 在本节数据上（150 训练 / 150 验证，无正则化）实测：最佳 epoch 为 232，第 253 个 epoch 停止，验证 loss 0.0589、验证准确率 97.3%。
- 注意：严格来说早停应使用独立的**验证集**，不能用最终报告的测试集来选 epoch，否则测试结果偏乐观。

### Q12 — 参考回答要点

- 训练：每个神经元以概率 p 置 0，保留的除以 `1-p`（inverted dropout）；反向传播用同一个 mask 和缩放系数。推理：恒等映射。
- 为什么有效：①打破共适应（co-adaptation），网络不能依赖某个特定神经元，被迫学冗余表示；②集成解释：N 个神经元对应 2ᴺ 个共享权重的子网络，训练时每步采样一个，推理时用完整网络近似它们的平均。
- 为什么缩放：保持期望不变，否则推理时所有神经元都在，下一层输入整体变大 `1/(1-p)` 倍，分布与训练时不一致。
- 不同默认值：Transformer 有 LayerNorm、残差、海量数据和 weight decay，正则化需求小，p=0.1 足够；全连接 MLP 参数密集、更容易共适应，0.5 是经典值；CNN 常用 0.2–0.3（卷积权重共享本身就是一种正则）。
- 加分点：集成平均对线性网络是精确的，对非线性网络只是近似；dropout 位置（激活之后、残差相加之前）；很多大规模预训练配置把 dropout 设为 0 或很小，因为数据量巨大、过拟合风险低。
- 常见误区：推理时还开着 dropout（忘了 `eval()`），或者手写时训练和推理都缩放了一次。

### Q13 — 参考回答要点

| | BatchNorm | LayerNorm | RMSNorm |
|---|---|---|---|
| 归一化维度 | 每个特征在 batch 维上 | 每个样本在特征维上 | 每个样本在特征维上 |
| 计算 | `(x-μ_B)/√(σ²_B+ε)`，再 `γ·x̂+β` | `(x-μ)/√(σ²+ε)`，再 `γ·x̂+β` | `x/√(mean(x²)+ε)`，再 `γ·` |
| 可学习参数 | γ、β | γ、β | 仅 γ |
| 训练 vs 推理 | 不同（batch 统计量 vs running 统计量） | 相同 | 相同 |
| 依赖 batch 大小 | 是，小 batch 下统计量噪声大 | 否 | 否 |
| 典型使用 | CNN | Transformer（BERT、GPT-2 等） | LLaMA、Mistral 等现代 LLM |

- Transformer 选 LN：序列变长、batch 小（生成时常为 1）、训练推理行为必须一致；BN 还会让同一 batch 内不同样本互相影响。
- LLM 选 RMSNorm：Zhang & Sennrich（2019）发现减均值对效果贡献很小，去掉后精度相当、计算更省（讲义给的数字约 10%）；在数十亿参数、数万亿 token 的规模上，这部分开销不可忽略。
- 加分点：Pre-LN（归一化放在子层之前）比 Post-LN 训练更稳定，是现代 LLM 的默认放置方式；BN 的 γ、β 让网络"可以撤销归一化"，不会限制表达能力。

### Q14 — 参考回答要点

- 可能原因：
  1. **忘记 `model.eval()`**：推理仍用 batch 统计量，dropout 也开着。
  2. **running 统计量没收敛**：训练步数少或 momentum 设置不当，running mean/var 偏离真实分布（代码 STEP 4 中 10 个 batch 后 running_mean 只有约 2.3，而后几个 batch 的真实均值已超过 3.5，输入 5 被归一化成约 2.8）。
  3. **训练/推理分布不一致**：训练时的数据增强、预处理与推理时不同，running 统计量对应的是训练分布。
  4. **训练 batch 太小**：batch 统计量噪声大，与 running 统计量差异大，训练时模型适应的是噪声很大的归一化。
- 小 batch 微调的处理：冻结 BN（`eval()` 模式下只用预训练的 running 统计量，并且不更新 γ、β 或以较小学习率更新）；或换用 GroupNorm/LayerNorm 这类与 batch 无关的归一化；多卡时使用同步 BN（SyncBatchNorm）汇总统计量。
- 加分点：能说出 running_var 的更新在 PyTorch 中使用无偏方差（除以 B-1），而前向归一化用的是有偏方差；本节代码两处都用有偏方差，是一个可以接受的简化。

### Q15 — 参考回答要点

1. **先确认问题是真的**：检查训练/验证是否同分布、有无数据泄漏或标签错误；确保两者都在 eval 模式下评估（本节 STEP 5 就是一个"测量方式不一致导致 gap 失真"的例子）。
2. **画学习曲线**：训练/验证 loss 随 epoch 的变化，看验证 loss 从哪个 epoch 开始上升。gap 29% 远超 10%，按讲义属于"重度正则化"区间。
3. **成本最低的手段先上**：
   - 早停（patience 5–20，保存最佳权重）；
   - 数据增强（图像翻转/裁剪/颜色抖动，文本回译，音频加噪）；
   - weight decay 0.01–0.1（Adam 系务必用 AdamW）；
   - dropout 0.3–0.5（Transformer 则从 0.1 开始逐步加）。
4. **从根上解决**：更多数据、更小的模型、迁移学习（用预训练模型微调，而不是从头训）。
5. **一次只改一个变量**，固定随机种子，多跑几个种子再下结论。

- 加分点：区分"过拟合"和"分布偏移"——如果验证集来自不同分布，正则化解决不了问题；提到标签平滑（label smoothing）也是常用的正则化手段。
- 常见误区：一次把所有正则化手段都加满，结果欠拟合（本节 STEP 5 的 "Dropout + weight decay" 就是这样，测试准确率最低）。

### Q16 — 参考回答要点

- 直觉：过拟合的模型往往依赖很大的权重来放大训练数据中的噪声；L2 惩罚让所有权重都偏小，限制有效容量，迫使模型依赖稳健的特征（讲义观点）。权重越大受到的惩罚越大（梯度 `λw` 与权重成正比，代码 STEP 2 中最大的权重 3.0 得到最大的梯度 0.03）。
- 贝叶斯观点：L2 正则 = 给权重加零均值高斯先验后做 MAP 估计；λ 越大，先验越窄。（对比：L1 正则对应拉普拉斯先验，倾向产生稀疏解。）
- 数值：讲义典型值，Transformer 上 AdamW 用 0.01，CNN 上 SGD 用 1e-4，严重过拟合时可到 0.1。
- 工程上不衰减的参数：偏置（bias）、归一化层的 γ/β（以及常见实践中的 embedding）。原因：这些参数数量少，不是过拟合的主要来源；对 γ 做衰减会把归一化后的尺度往 0 拉，干扰网络表达。本节代码的 `backward` 中偏置 `b1`、`b2` 也没有加 weight decay 项。
- 常见误区：在 Adam 里用 `weight_decay` 参数以为就是 AdamW。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 06 优化器](../../06-optimizers/docs/zh.md)：weight decay 与 L2 在 SGD/Adam 中是否等价、AdamW 的来源。
- [阶段 03 · 05 Loss Functions](../../05-loss-functions/docs/zh.md)：二元交叉熵及其梯度，`backward` 的起点；标签平滑也在那一节。
- [阶段 02 · 10 偏差-方差](../../../02-ml-fundamentals/10-bias-variance/docs/zh.md)：过拟合/欠拟合与正则化的经典视角。
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：训练/验证/测试划分，正确测量泛化差距。

### 本节被哪些后续内容用到
- [阶段 03 · 08 Weight 初始化和训练稳定性](../../08-weight-initialization/docs/zh.md)：初始化与归一化一起决定深层网络的激活尺度。
- [阶段 03 · 09 Learning Rate Schedules 和 Warmup](../../09-learning-rate-schedules/docs/zh.md)：学习率调度与正则化共同影响最终泛化。
- [阶段 03 · 13 调试神经网络](../../13-debugging-neural-networks/docs/zh.md)：`train()/eval()` 模式错误、过拟合诊断等调试技巧。
- [阶段 04 · 03 CNN：从 LeNet 到 ResNet](../../../04-computer-vision/03-cnns-lenet-to-resnet/docs/zh.md)：BatchNorm 在 CNN 中的标准用法。
- [阶段 04 · 04 图像分类](../../../04-computer-vision/04-image-classification/docs/zh.md)：数据增强的实战。
- [阶段 07 · 05 完整 Transformer](../../../07-transformers-deep-dive/05-full-transformer/docs/zh.md)：LayerNorm、Pre-norm vs Post-norm、dropout=0.1 的位置。
- [阶段 10 · 14 开源模型架构解读](../../../10-llms-from-scratch/14-open-models-architecture-walkthroughs/docs/zh.md)：RMSNorm 在现代 LLM 中的使用。

### 延伸关键词
`DropConnect` · `Spatial Dropout` · `Stochastic Depth` · `GroupNorm / InstanceNorm` · `SyncBatchNorm` · `Label Smoothing` · `Mixup / CutMix` · `Pre-LN vs Post-LN` · `DeepNorm` · `Double Descent`
