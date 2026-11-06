# 测验 · 损失函数（Loss Functions）

> **阶段 03 · 深度学习核心 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 损失函数是唯一的优化目标 | 优化器只看 loss 的梯度，不看 accuracy / F1；loss 没表达你在乎的东西，模型就会找"最便宜"的方式满足它 |
| 2 | MSE | `(1/n)Σ(ŷ − y)²`，回归默认选择；误差平方放大离群点；梯度 `2(ŷ − y)/n` 与误差成正比 |
| 3 | 二元交叉熵 BCE | `−[y·log p + (1−y)·log(1−p)]`；`−log 0.99 ≈ 0.01`、`−log 0.01 ≈ 4.6`，严惩"自信地错"；实现时要把 p 夹到 `[eps, 1−eps]` |
| 4 | sigmoid + BCE 的梯度 | 对 logit `z` 的梯度化简为 `p − y`，sigmoid 的饱和被 log 抵消；而 sigmoid + MSE 的梯度 `2(p − y)·p(1−p)` 在饱和区趋近 0 |
| 5 | softmax + 交叉熵 | `CE = −log p_target`；对 logits 的梯度为 `p − onehot`；10 类随机猜的 loss 是 `ln 10 ≈ 2.3` |
| 6 | Label smoothing | 目标改为 `(1−α)·onehot + α/K`（α=0.1、K=5 时真类 0.92、其余 0.02），阻止 logits 被推向无穷，缓解过度自信 |
| 7 | 对比损失 InfoNCE | 在 `相似度/τ` 上做 softmax 交叉熵，让正样本对的相似度在所有候选中最高；温度 τ 控制分布的尖锐程度 |
| 8 | Triplet loss | `max(0, d(a,p) − d(a,n) + margin)`；负样本足够远就没有梯度，依赖难例挖掘 |
| 9 | Focal loss | `−α(1 − p_t)^γ·log p_t`，γ=2 时 `p_t = 0.9` 的易样本权重只有 0.01；用于极度不平衡（如目标检测的背景框） |
| 10 | 选型 | 回归：MSE（关注大误差）/ MAE、Huber（抗离群点）；二分类：BCE；多分类：CE（+ label smoothing）；不平衡：Focal；表示学习：对比 / triplet |

### 核心技能（能动手做到）

- [ ] 从零实现 MSE、BCE、softmax 交叉熵、label smoothing 交叉熵、InfoNCE，并写出各自的梯度
- [ ] 推导 sigmoid + BCE、softmax + CE 对 logits 的梯度都等于 `p − y`，并用中心差分验证
- [ ] 给定一组 logits 和目标类，手算 softmax、CE loss 和梯度向量（如 STEP 3 的 `[2.0, 1.0, 0.1, -1.0, 3.0]`）
- [ ] 解释温度 τ 在"正样本已最相似"和"存在更相似的难负样本"两种情况下对 InfoNCE 的不同影响
- [ ] 识别并修复"先算 `dL/dp` 再乘 `σ'`"在 sigmoid 饱和时的数值问题
- [ ] 面对一个新任务（离群点、多标签、极度不平衡、无标签表示学习），选出合适的损失并说明理由

---

## 二、基础自测（选择题）

**Q1.** 真实标签为 1。预测 `p = 0.01` 和 `p = 0.99` 时，BCE 损失分别约为：

- A. 0.98 和 0.0001
- B. 4.61 和 0.01
- C. 2.30 和 0.10
- D. 0.99 和 0.01

**Q2.** 输出层为 `p = σ(z)`、损失为 BCE。损失对 logit `z` 的梯度 `∂L/∂z` 等于：

- A. `(p − y)·p(1 − p)`
- B. `p − y`
- C. `−y / p`
- D. `2(p − y)`

**Q3.** STEP 3 中 logits 为 `[2.0, 1.0, 0.1, -1.0, 3.0]`、目标类是下标 4，softmax 结果为 `[0.2333, 0.0858, 0.0349, 0.0116, 0.6343]`。CE 对 logits 的梯度向量是：

- A. `[0.2333, 0.0858, 0.0349, 0.0116, 0.6343]`
- B. `[0, 0, 0, 0, -0.3657]`
- C. `[0.2333, 0.0858, 0.0349, 0.0116, -0.3657]`
- D. `[-0.2333, -0.0858, -0.0349, -0.0116, 0.3657]`

**Q4.** 5 分类、`α = 0.1` 的 label smoothing，真实类别的目标概率是：

- A. 0.90
- B. 0.92
- C. 0.98
- D. 0.10

**Q5.** 一个正负样本各占 50% 的二分类任务。如果模型**只能输出一个常数** c（完全不看输入），使 MSE 最小的 c 和使 BCE 最小的 c 分别是：

- A. MSE：0.5；BCE：0 或 1
- B. 都是 0.5
- C. MSE：0.5；BCE：不存在最小值
- D. MSE：0；BCE：0.5

**Q6.** 关于 InfoNCE 中的温度 τ，下列说法正确的是：

- A. τ 越小，loss 一定越大
- B. τ 越小 softmax 越尖锐：如果正样本的相似度已经是最高的，loss 会趋近 0；如果有负样本比正样本更相似，loss 会被急剧放大
- C. τ 只起到学习率的作用，不影响 loss 的值
- D. τ → ∞ 时 loss → 0

**Q7.** Focal loss 取 `γ = 2`。`p_t = 0.9` 的简单样本与 `p_t = 0.1` 的困难样本，其调制因子 `(1 − p_t)^γ` 分别是：

- A. 0.01 和 0.81
- B. 0.1 和 0.9
- C. 0.81 和 0.01
- D. 0.9 和 0.1

---

## 三、动手 / 代码题

**Q8.** STEP 5 的输出是：

```text
  Anchor-positive similarity: 0.9946
  Anchor-negative similarities: ['0.4161', '0.5445', '0.5705', '0.0445', '-0.5513', '-0.0406', '-0.2231']
  Contrastive loss (tau=0.07): 0.0042
  Contrastive loss (tau=0.5):  0.9391
  Lower temperature = sharper = higher loss for imperfect separation
```

(a) 最后一行打印的结论和上面两个数字矛盾吗？为什么低温度下 loss 反而更小？
(b) 什么情况下"低温度 → 更高 loss"才成立？请构造一个例子说明。
(c) τ → ∞ 时，这个例子（1 个正样本 + 7 个负样本）的 loss 会趋近多少？

**Q9.** `LossComparisonNetwork.backward` 中 BCE 分支是这样算梯度的：

```python
        else:
            eps = 1e-15
            p = max(eps, min(1 - eps, self.out))
            d_loss = -(target / p) + (1 - target) / (1 - p)

        d_sigmoid = self.out * (1 - self.out)
        d_out = d_loss * d_sigmoid
```

(a) 数学上，`d_out` 应该化简成什么？
(b) 当 `z2 = −40`、`target = 1` 时，以及 `self.out == 1.0`（`z2` 大于约 37）、`target = 0` 时，这段代码算出的 `d_out` 分别是多少？正确值应该是多少？
(c) 改写这段代码，并说明这和 PyTorch 推荐使用 `BCEWithLogitsLoss` / `F.cross_entropy` 的原因有什么关系。

**Q10.** 关于 STEP 4 的 label smoothing：

```text
  Hard target loss:    0.455241
  Smooth target loss:  0.653241
  Smoothing increases loss by 0.198000
  This prevents overconfidence by targeting 0.9 instead of 1.0
```

(a) 打印的 "targeting 0.9" 准确吗？
(b) 证明：平滑 loss − 硬 loss = `(α/K)·Σ_{i≠t}(x_t − x_i)`（x 为 logits，t 为目标类），并用它验证 0.198。这个式子说明 label smoothing 在"惩罚"什么？
(c) 写出 `label_smoothed_cce` 对 logits 的梯度函数，并用中心差分验证。

---

## 四、面试高频题

**Q11.**（基础必考）分类任务为什么用交叉熵而不用 MSE？请说出真正的原因。

**Q12.**（原理深挖）从最大似然估计的角度推导 MSE、BCE、多分类交叉熵分别对应什么概率假设。交叉熵和 KL 散度是什么关系？

**Q13.**（工程实践）PyTorch 中 `BCELoss` 与 `BCEWithLogitsLoss`、`CrossEntropyLoss` 与 `NLLLoss` 有什么区别？列举几个与损失函数相关的常见 bug。

**Q14.**（场景设计）一个风控 / 缺陷检测任务，正样本只占 1%。你会如何选择和设计损失函数？如何评估？

**Q15.**（原理深挖）CLIP / SimCLR 这类对比学习中，温度、batch size、负样本数各起什么作用？什么是表征坍缩，InfoNCE 如何避免它？

**Q16.**（结合大模型）LLM 预训练用的是什么损失？它和 perplexity 是什么关系？loss 从 2.0 降到 1.9 意味着什么？

---

## 五、参考答案与解析

### Q1 — 答案：B

`−ln 0.01 ≈ 4.605`，`−ln 0.99 ≈ 0.01005`，相差约 460 倍——这正是讲义说的"交叉熵严惩自信的错误、几乎不罚自信的正确"。A 是 MSE 的值（`(0.01−1)² = 0.9801`、`(0.99−1)² = 0.0001`，与代码 STEP 2 的表格一致）；C 是 `p = 0.1` 和 `p = 0.9` 的 CE。

### Q2 — 答案：B

`∂L/∂p = −y/p + (1−y)/(1−p) = (p − y)/(p(1−p))`，`∂p/∂z = p(1−p)`，相乘后 `p(1−p)` 恰好抵消，得到 `p − y`。这就是"log 抵消 sigmoid 饱和"：无论 z 多大多小，只要预测错了，梯度就接近 ±1。A 是 sigmoid + **MSE**（不含系数 2）的梯度形式，饱和时 `p(1−p) → 0`，梯度消失。

### Q3 — 答案：C

softmax + CE 对 logits 的梯度是 `p − onehot`：非目标类就是它的概率，目标类是 `0.6343 − 1 = −0.3657`。与代码输出 `Gradient: ['0.2333', '0.0858', '0.0349', '0.0116', '-0.3657']` 一致。梯度下降会减小非目标类的 logit、增大目标类的 logit；所有分量之和为 0（softmax 的平移不变性）。D 是负梯度（更新方向），不是梯度本身。

### Q4 — 答案：B

真类：`1 − α + α/K = 1 − 0.1 + 0.02 = 0.92`；其他类：`α/K = 0.02`。讲义里"10 类时变成 0.91"、"目标封顶在 0.9"都是在说同一件事的近似；代码 STEP 4 打印的 "targeting 0.9 instead of 1.0" 对 5 类来说并不精确（见 Q10）。

### Q5 — 答案：B

设正类比例为 50%：
- MSE：`0.5(c−1)² + 0.5c²`，在 `c = 0.5` 取最小值 0.25；
- BCE：`−0.5·ln c − 0.5·ln(1−c)`，同样在 `c = 0.5` 取最小值 `ln 2 ≈ 0.693`（例如 c = 0.3 或 0.7 时都是 0.780）。

所以"MSE 会让模型对所有输入都预测 0.5"并不是 MSE 独有的缺陷——在**不使用输入信息**的前提下，两种损失的最优常数都是类别先验 0.5。讲义 "The Problem" 一节用这个例子论证 MSE 不适合分类，论证并不成立。MSE 不适合分类的真正原因是梯度行为和概率解释（见 Q11）。而且代码 STEP 6 的实验里，MSE 训练的网络同样达到了 99% 准确率。

### Q6 — 答案：B

相似度除以 τ 再做 softmax：τ 越小，相似度之间的差距被放大得越厉害。
- 正样本已是最高（代码 STEP 5 的情况，0.9946 远高于其余）：τ = 0.07 时正样本几乎独占概率，loss 只有 0.0042；τ = 0.5 时 loss 为 0.9391。
- 存在比正样本更相似的难负样本：τ 越小，这个错误被放大得越严重，loss 急剧上升。

所以 A 错。C 错：τ 直接改变 loss 的值和梯度分布（低温让梯度集中在最难的负样本上）。D 错：τ → ∞ 时所有候选概率趋于均等，loss → `ln(候选数)`。

### Q7 — 答案：A

`(1 − 0.9)² = 0.01`，`(1 − 0.1)² = 0.81`。简单样本的损失被压低到原来的 1%，困难样本基本保留，所以模型的"注意力"集中到难样本上。`γ = 0` 时调制因子恒为 1，focal loss 退化为（带 α 权重的）标准交叉熵。

### Q8 — 参考答案

(a) **矛盾**。打印的结论说"低温度 → 更高 loss"，但输出是低温度（0.07）的 loss 0.0042 远小于高温度（0.5）的 0.9391。原因：这个例子里正样本是 anchor 加小噪声得到的，相似度 0.9946，比所有负样本（最高 0.5705）都高得多——**分离是完美的**。低温把 `0.9946/0.07 ≈ 14.2` 和 `0.5705/0.07 ≈ 8.2` 的差距放大到 `e^6` 量级，正样本独占几乎全部概率，loss → 0。打印语句里的"for imperfect separation"这个前提在这个例子中并不满足，所以这行结论与输出矛盾（这是源代码演示上的一个问题）。

(b) 当某个负样本比正样本更相似时（不完美分离），低温度会放大这个"排序错误"。例如在同一个 anchor 下，构造一个相似度只有约 0.57 的"弱正样本"和一个相似度约 0.9985 的"难负样本"（anchor 加极小噪声），实测：

```text
tau=0.07: loss ≈ 6.09
tau=0.5 : loss ≈ 1.94
```

低温下 loss 大幅上升，梯度也会集中到这个难负样本上——这就是讲义说的"更低温度 = 更难的负样本 = 更激进的分离"。

(c) τ → ∞ 时所有 `相似度/τ → 0`，8 个候选（1 正 + 7 负）的 softmax 都趋于 1/8，loss → `ln 8 ≈ 2.079`。实测 τ = 10 时 loss ≈ 2.003，已接近这个上界。这也是 InfoNCE 的一个常用诊断基准：loss 停在 `ln(候选数)` 附近，说明模型完全没区分出正样本。

### Q9 — 参考答案

(a) `d_loss · d_sigmoid = (p − y)/(p(1−p)) · p(1−p) = p − y`，所以 `d_out` 在数学上就是 `self.out − target`。

(b) 实测：

| 情况 | 代码算出的 `d_out` | 正确值 `p − y` |
|------|------------------|---------------|
| `z2 = −40`，`target = 1`（`p ≈ 4.2e−18`，自信地错） | 约 `−0.00425` | 约 `−1.0` |
| `self.out == 1.0`，`target = 0`（自信地错） | `0.0` | `1.0` |

原因：`p` 被夹到 `[1e−15, 1 − 1e−15]` 后，`d_loss` 用的是夹过的 p，而 `d_sigmoid` 用的是**真实的** `self.out`，两边不再抵消。`z2 = −40` 时 `d_sigmoid ≈ 4.2e−18`，`d_loss ≈ −1e15`，乘积只有 0.004；`self.out` 恰好等于 1.0 时 `d_sigmoid = 0`，梯度直接变成 0。讽刺的是，这恰恰是交叉熵本该给出**最强梯度**的"自信地错"的情形。本节的正常训练中 z2 不会大到这种程度，所以输出没有受影响，但这是一个潜在的数值 bug。

(c) 直接使用化简后的梯度：

```python
    def backward(self, target):
        if self.loss_type == "mse":
            d_out = 2.0 * (self.out - target) * self.out * (1 - self.out)
        else:
            d_out = self.out - target          # sigmoid + BCE 的化简梯度
        for i in range(self.hidden_size):
            d_relu = 1.0 if self.z1[i] > 0 else 0.0
            d_h = d_out * self.w2[i] * d_relu
            self.w2[i] -= self.lr * d_out * self.h[i]
            for j in range(2):
                self.w1[i][j] -= self.lr * d_h * self.x[j]
            self.b1[i] -= self.lr * d_h
        self.b2 -= self.lr * d_out
```

在本节数据上，修改后 200 轮的结果与原版完全一致（loss 0.0219、准确率 99.0%），但在饱和区不再丢失梯度。与 PyTorch 的关系：`BCEWithLogitsLoss` / `F.cross_entropy` 接收 **logits**，内部把 sigmoid/softmax 与 log 合并成一个数值稳定的算子（log-sum-exp 技巧），反向直接用 `p − y`。先 `sigmoid` 再 `BCELoss`（或先 `softmax` 再取 log）就会遇到本题这类精度问题——讲义 "Use It" 一节说的正是这个。

### Q10 — 参考答案

(a) 不准确。5 类、α = 0.1 时真类目标是 `1 − 0.1 + 0.1/5 = 0.92`，其余类各 0.02。"0.9" 只是 `1 − α` 的近似，忽略了均匀分布部分也分给了真类的 `α/K`。

(b) 记 `LSE = log Σ_j e^(x_j)`，则 `−log p_i = LSE − x_i`。设平滑目标为 `s_i`（`Σ s_i = 1`）：

```text
smooth = Σ s_i (LSE − x_i) = LSE − Σ s_i x_i
hard   = LSE − x_t
smooth − hard = x_t − Σ s_i x_i
              = x_t − (1 − α + α/K)·x_t − (α/K)·Σ_{i≠t} x_i
              = (α/K)·Σ_{i≠t} (x_t − x_i)
```

代入：`α/K = 0.02`，`x_t = 3.0`，其余 logits 为 `2.0, 1.0, 0.1, −1.0`，差值之和 `1 + 2 + 2.9 + 4 = 9.9`，`0.02 × 9.9 = 0.198`，与输出完全一致。

含义：额外的损失正比于"真类 logit 比其他类高出多少"的总和。模型越想把真类 logit 拉得远高于其他类（越自信），这一项就越大——label smoothing 惩罚的正是**过大的 logit 间隔**，这就是它防止过度自信的机制。

(c)

```python
def label_smoothed_cce_gradient(logits, target_index, num_classes, alpha=0.1):
    probs = softmax(logits)
    grads = []
    for i in range(num_classes):
        s = 1.0 - alpha + alpha / num_classes if i == target_index else alpha / num_classes
        grads.append(probs[i] - s)
    return grads

logits = [2.0, 1.0, 0.1, -1.0, 3.0]
g = label_smoothed_cce_gradient(logits, 4, 5)
h = 1e-6
num = []
for i in range(5):
    lp = logits[:]; lp[i] += h
    lm = logits[:]; lm[i] -= h
    num.append((label_smoothed_cce(lp, 4, 5) - label_smoothed_cce(lm, 4, 5)) / (2 * h))
print([f"{x:.4f}" for x in g])
print(max(abs(a - b) for a, b in zip(g, num)))
```

实测输出 `['0.2133', '0.0658', '0.0149', '-0.0084', '-0.2857']`，与数值梯度的最大差约 1.2e−10。梯度仍是"预测分布 − 目标分布"的形式 `p − s`。注意下标 3：它的概率 0.0116 已经低于平滑目标 0.02，梯度为负，会被**往上推**——硬标签永远不会这样做。

### Q11 — 参考回答要点

- 常见但不完整的说法："MSE 会让模型输出 0.5"——不使用输入时，MSE 和 CE 的最优常数都是类别先验（Q5），这不是根本原因。
- 真正的原因：
  1. **梯度**：sigmoid / softmax 输出层 + MSE，梯度含 `p(1−p)` 因子，预测"自信地错"时（p 接近 0 或 1）梯度趋近 0，学不动；CE 的 log 恰好抵消这个因子，梯度为 `p − y`，错得越离谱梯度越大。
  2. **概率解释**：CE 是伯努利 / 多项分布的负对数似然，最小化它就是最大似然估计，输出可以解释为校准的概率；MSE 对应高斯噪声假设，与离散标签不匹配。
  3. **凸性**：对于 logistic regression，CE 关于参数是凸的；sigmoid + MSE 则是非凸的。
  4. **惩罚形状**：CE 对自信的错误给出无界的惩罚（`−log p → ∞`），MSE 最大只有 1。
- 实践补充：在浅层网络、数据简单时，MSE 也能训练出不错的分类器（本节 STEP 6 中 MSE 同样达到 99%），差距在深层、饱和、类别多时才明显。
- 加分点：说出知识蒸馏中有时会对 logits 用 MSE（logit matching），以及回归中的"分类化"技巧（把连续值分桶后用 CE）。

### Q12 — 参考回答要点

- 最大似然：最小化 `−Σ log P(yᵢ | xᵢ; θ)`。
  - 回归，假设 `y = f(x) + ε`，`ε ~ N(0, σ²)`：`−log P ∝ (y − f(x))²/(2σ²)` → **MSE**。若假设拉普拉斯噪声 → **MAE**。
  - 二分类，假设 `y ~ Bernoulli(p)`：`−log P = −[y log p + (1−y) log(1−p)]` → **BCE**。
  - 多分类，假设 `y ~ Categorical(p)`：`−log p_y` → **交叉熵**。
- 交叉熵与 KL：`H(q, p) = H(q) + KL(q ‖ p)`。真实分布 q 固定时，`H(q)` 是常数，最小化交叉熵等价于最小化 KL 散度。one-hot 标签时 `H(q) = 0`，两者相等（讲义练习 5）；soft target（label smoothing、知识蒸馏）时两者相差一个常数，梯度相同。
- 加分点：不同损失 = 不同的噪声 / 分布假设；选损失其实是在选"你认为数据是怎么生成的"。

### Q13 — 参考回答要点

| API | 输入 | 内部做了什么 |
|-----|------|------------|
| `BCELoss` | 概率（已过 sigmoid） | 直接算 `−[y log p + …]`，p 接近 0/1 时数值不稳定 |
| `BCEWithLogitsLoss` | logits | sigmoid + BCE 融合，用 log-sum-exp 技巧，数值稳定；支持 `pos_weight` |
| `NLLLoss` | log 概率 | 只取 `−log p_target` |
| `CrossEntropyLoss` / `F.cross_entropy` | logits + 类别下标（或概率目标） | `log_softmax` + `NLLLoss`，数值稳定；支持 `label_smoothing`、`weight`、`ignore_index` |

- 常见 bug：
  1. 先 `softmax` 再传给 `CrossEntropyLoss`——相当于做了两次 softmax，梯度变小、训练变慢，但不会报错；
  2. 先 `sigmoid` 再用 `BCEWithLogitsLoss`（同理）；
  3. 目标格式不对：`CrossEntropyLoss` 默认要 `long` 型类别下标，形状 `(N,)`，不是 one-hot；
  4. reduction 的 mean / sum 混用，导致等效学习率随 batch size 变化（本节代码中 `mse_gradient`、`bce_gradient` 都除以了 n，与均值形式的损失对应）；
  5. 序列任务忘了用 `ignore_index` 屏蔽 padding；
  6. 自己写 `log(p)` 不加 eps，遇到 p = 0 得到 `-inf` / NaN。
- 加分点：能解释 log-sum-exp：`log Σ e^(xᵢ) = m + log Σ e^(xᵢ − m)`，`m = max xᵢ`。

### Q14 — 参考回答要点

- 问题：1% 正样本时，"全猜负"就有 99% 准确率，标准 CE 的梯度被大量简单负样本主导。
- 损失层面：
  - **类别权重**：`BCEWithLogitsLoss(pos_weight=...)` 或 CE 的 `weight`，常取类别频率的倒数或其平方根；
  - **Focal loss**：`(1 − p_t)^γ` 压低易样本权重（讲义：目标检测中 99% 候选框是背景）；γ 常取 2，α 平衡正负；
  - 难例挖掘（OHEM）：只对 loss 最大的一部分样本反向。
- 数据层面：过采样少数类 / 欠采样多数类、数据增强；保持验证集分布与线上一致。
- 评估：不用 accuracy；看 PR-AUC、少数类 recall / precision、F1，或业务指标（如固定误报率下的召回率）；训练后调分类阈值，而不是固定 0.5。
- 常见误区：同时使用重采样和大权重导致过度补偿，概率失去校准；需要概率输出时要做校准（如 Platt scaling、温度缩放）。

### Q15 — 参考回答要点

- InfoNCE 本质：把"在一组候选中找出正样本"当成一个分类问题，loss 是 `相似度/τ` 上的 softmax 交叉熵。
- 温度 τ：
  - 小 τ：分布尖锐，梯度集中在最难的负样本上，分离更激进，但太小会训练不稳定；
  - 大 τ：分布平滑，所有负样本差不多一视同仁，学到的表征区分度较弱；
  - CLIP 把 τ 设为可学习参数（初始化为 0.07）。
- batch size 与负样本数：batch 内其他样本充当负样本，负样本越多，InfoNCE 对互信息的下界越紧、任务越难、表征越好，所以 SimCLR 依赖很大的 batch。注意 SimCLR 中 N 张图生成 2N 个视图，每个正样本对实际有 `2(N−1)` 个负样本（讲义"batch 256 → 255 个负样本"的说法是简化）。MoCo 用队列（memory bank）在小 batch 下获得大量负样本。
- 表征坍缩：所有输入都映射到同一个向量，"正样本对相似"这个目标被平凡满足。InfoNCE 的分母要求正样本比所有负样本都更相似，坍缩时所有相似度相同，loss = `ln(候选数)`，不是最小值，所以负样本项天然防止坍缩。不使用负样本的方法（BYOL、SimSiam）要靠 stop-gradient、预测头等结构来避免坍缩。
- 加分点：triplet loss 是"只有一个负样本 + hinge"的特例；对比学习的效果高度依赖数据增强的选择。

### Q16 — 参考回答要点

- 损失：下一个 token 预测的交叉熵。对序列中每个位置，模型输出词表大小的 logits，取真实下一个 token 的 `−log p`，在所有位置上取平均（padding 位置用 `ignore_index` 屏蔽）。
- 与 perplexity：`PPL = exp(平均交叉熵)`（交叉熵以 nat 为单位时）。直观上是"模型在每一步平均相当于在多少个等可能选项中犹豫"。
- loss 2.0 → 1.9：PPL 从 `e^2 ≈ 7.39` 降到 `e^1.9 ≈ 6.69`，约下降 9.5%；对预训练来说这是可观的进步，但要在相同的 tokenizer 和数据分布下比较才有意义（不同词表的 loss 不可直接比较）。
- 起点参考：随机初始化时 loss 约为 `ln(词表大小)`（如 5 万词表约 10.8），与本节"10 类随机猜 = ln 10 ≈ 2.3"同理——训练初期 loss 明显偏离这个值，通常意味着初始化或数据有问题。
- 加分点：label smoothing 在原始 Transformer 的机器翻译实验中使用了 0.1，但在 decoder-only LLM 预训练中并不常见，因为它会改变概率分布、影响 PPL 的解释。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：熵、交叉熵、KL 散度的定义。
- [阶段 02 · 03 逻辑回归](../../../02-ml-fundamentals/03-logistic-regression/docs/zh.md)：sigmoid + BCE 的经典组合与最大似然解释。
- [阶段 03 · 04 Activation Functions](../../04-activation-functions/docs/zh.md)：sigmoid 饱和、softmax 的数值稳定写法。

### 本节被哪些后续内容用到
- [阶段 03 · 06 Optimizers](../../06-optimizers/docs/zh.md)：拿到 loss 的梯度之后如何更新参数。
- [阶段 03 · 07 正则化](../../07-regularization/docs/zh.md)：label smoothing 与 L2、Dropout 一样属于防过拟合 / 过度自信的手段。
- [阶段 02 · 17 不平衡数据](../../../02-ml-fundamentals/17-imbalanced-data/docs/zh.md)：类别权重、重采样，与 focal loss 互补。
- [阶段 04 · 17 自监督视觉](../../../04-computer-vision/17-self-supervised-vision/docs/zh.md)：SimCLR 等对比学习方法中的 InfoNCE。
- [阶段 04 · 20 图像检索与度量学习](../../../04-computer-vision/20-image-retrieval-metric/docs/zh.md)：triplet loss 与难例挖掘。
- [阶段 05 · 22 Embedding 模型深入](../../../05-nlp-foundations-to-advanced/22-embedding-models-deep-dive/docs/zh.md)：文本 embedding 训练中的对比损失。
- [阶段 12 · 02 CLIP 对比预训练](../../../12-multimodal-ai/02-clip-contrastive-pretraining/docs/zh.md)：图文对比学习与可学习温度。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：next-token 交叉熵与 perplexity。

### 延伸关键词
`最大似然估计` · `KL 散度` · `log-sum-exp` · `BCEWithLogitsLoss` · `Huber / Smooth L1` · `NT-Xent` · `难例挖掘（hard negative mining）` · `知识蒸馏` · `perplexity` · `概率校准`
