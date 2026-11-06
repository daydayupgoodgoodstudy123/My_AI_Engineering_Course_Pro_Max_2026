# 测验 · 优化器（Optimizers）

> **阶段 03 · 深度学习核心 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | SGD | `w = w - lr * g`，梯度在 mini-batch 上估计；所有参数共用一个 lr，窄谷中来回震荡、在鞍点附近爬得极慢 |
| 2 | Momentum（动量） | `m = β·m + g; w -= lr·m`；同向梯度累加、反向梯度抵消；稳态下 `m ≈ g/(1-β)`，β=0.9 时有效步长放大约 10 倍 |
| 3 | RMSProp | `s = β·s + (1-β)·g²; w -= lr·g/(√s + ε)`；按每个参数梯度的 RMS 缩放，实现"逐参数自适应学习率" |
| 4 | Adam | 一阶矩 m（动量）+ 二阶矩 v（RMSProp）两个 EMA；更新量 `lr·m̂/(√v̂ + ε)`，量级约等于 lr，与梯度尺度无关 |
| 5 | 偏差修正（bias correction） | m、v 从 0 初始化，早期偏向 0；除以 `1-βᵗ` 补偿。β1=0.9 只影响前几十步，β2=0.999 要上千步才可忽略 |
| 6 | AdamW（解耦权重衰减） | Adam + L2 时，正则项梯度也被 `√v̂` 缩放，不同参数受到的正则不均匀；AdamW 直接 `w -= lr·λ·w`，不经过自适应因子 |
| 7 | 学习率是最重要的超参数 | 10 倍的 lr 变化比多数架构改动影响更大；SGD 0.01–0.1，Adam/AdamW 1e-4–3e-4，微调 1e-5–5e-5 |
| 8 | 按场景选优化器 | Transformer/LLM → AdamW；CNN/ResNet → SGD+Momentum（lr=0.1）；GAN → Adam（β1=0.5）；不确定 → AdamW lr=3e-4 |
| 9 | 训练循环顺序 | `zero_grad → forward → loss → backward → (clip) → step → (scheduler.step)`，顺序错了会出现隐蔽 bug |

### 核心技能（能动手做到）

- [ ] 不看讲义，从零写出 `SGD`、`SGDMomentum`、`Adam`、`AdamW` 四个类的 `step(params, grads)`，原地修改 `params`
- [ ] 手算 Adam 前两步的 `m、v、m̂、v̂` 和更新量，并说明"不做偏差修正时第 1 步的更新会偏大约 3.16 倍"
- [ ] 写出 Adam+L2（`g += λ·w` 后再进 Adam）与 AdamW（`w *= 1 - lr·λ`）两种实现，并说清楚二者的数学差异
- [ ] 跑通 `code/main.py`，能解释为什么 `SGD+Momentum(lr=0.05)` 卡在 93%，以及把 lr 降到 0.005 为什么就能恢复到 99%
- [ ] 写出 PyTorch 标准训练循环（AdamW + `clip_grad_norm_` + 调度器），顺序正确
- [ ] 给定模型类型（LLM 预训练 / 微调 / ResNet / GAN），说出优化器和默认超参，并给出一条理由

---

## 二、基础自测（选择题）

**Q1.** 本节代码中的动量写法是 `m = β·m + g`（注意没有 `(1-β)`）。若 β=0.9、梯度长期恒为 g，则 m 的稳态值约为：

- A. g
- B. 0.1·g
- C. 10·g
- D. 0.9·g

**Q2.** Adam（β1=0.9、β2=0.999、ε 可忽略、带偏差修正），第 1 步时某参数梯度为 `g = 0.5`，lr=0.001。这一步该参数的更新量大小约为：

- A. 0.0005（= lr·g）
- B. 0.001（= lr）
- C. 0.0001
- D. 0.01

**Q3.** 接 Q2，如果**去掉偏差修正**、直接用 `m₁/(√v₁ + ε)`，第 1 步的更新量会：

- A. 比修正后小约 10 倍
- B. 比修正后大约 3.16 倍
- C. 与修正后完全相同
- D. 比修正后大约 1000 倍

**Q4.** 在 t=100 步时（β1=0.9、β2=0.999），下面关于偏差修正的说法哪个正确？

- A. 两个修正因子都已约等于 1，可以忽略
- B. 一阶矩的修正已可忽略，但二阶矩的修正仍会把 v 放大约 10 倍
- C. 一阶矩的修正仍然很大，二阶矩的修正已可忽略
- D. 偏差修正只在第 1 步起作用

**Q5.** 为什么在 Adam 中"把 L2 正则加到 loss 里"不等价于权重衰减？

- A. 因为 Adam 不计算正则项的梯度
- B. 因为正则项的梯度 `λ·w` 也会被除以 `√v̂`，梯度方差大的参数受到的正则反而更弱
- C. 因为 L2 正则只对偏置生效
- D. 因为 Adam 的一阶矩会把正则项抵消为 0

**Q6.** 要微调一个预训练的 BERT 做文本分类，下面哪组配置最符合本节给出的经验默认值？

- A. SGD，lr=0.1，momentum=0.9
- B. AdamW，lr=2e-5，weight_decay=0.01
- C. Adam，lr=1e-2，β1=0.5
- D. RMSProp，lr=1e-3，不加 weight decay

**Q7.** 下面哪个 PyTorch 训练步骤顺序是正确的？

- A. `zero_grad → forward → loss → backward → clip_grad_norm_ → optimizer.step → scheduler.step`
- B. `forward → loss → optimizer.step → backward → zero_grad`
- C. `zero_grad → forward → loss → backward → scheduler.step → clip_grad_norm_ → optimizer.step`
- D. `forward → loss → backward → clip_grad_norm_ → optimizer.step`（整个训练从不调用 `zero_grad`）

---

## 三、动手 / 代码题

**Q8.** `main.py` 的 STEP 1 用 SGD 最小化 `f(x) = (x - 3)²`：

```python
x = [10.0]
sgd = SGD(lr=0.1)
for step in range(20):
    grad = [2.0 * (x[0] - 3.0)]
    sgd.step(x, grad)
    loss = (x[0] - 3.0) ** 2
    if step % 5 == 0 or step == 19:
        print(f"    Step {step:2d}: x={x[0]:.6f}, loss={loss:.6f}")
```

(a) 写出第一行打印（Step 0）的 x 和 loss；(b) 推导 `x_t` 的闭式解；(c) lr 取多少时一步就到最优？lr 超过多少会发散？

**Q9.** 实际运行 `main.py`，STEP 3 的最终对比是：

```text
SGD (lr=0.05)                     : acc=99.0%, loss=0.0179, reached 85%: epoch 4
SGD+Momentum (lr=0.05, beta=0.9)  : acc=93.0%, loss=0.2069, reached 85%: epoch 5
Adam (lr=0.001)                   : acc=99.5%, loss=0.0336, reached 85%: epoch 30
AdamW (lr=0.001, wd=0.01)         : acc=99.0%, loss=0.0612, reached 85%: epoch 32
```

讲义说"加了动量通常更快"，为什么这里 SGD+Momentum 反而卡在 93% 且 loss 从第 75 个 epoch 起几乎不再下降？请结合 `SGDMomentum.step` 的写法和网络里的 ReLU 解释，并给出一个最小改动的修复方案。

**Q10.** 本节代码没有"Adam + L2 正则"的实现。请继承 `Adam` 写一个 `AdamL2` 类，使它在进入 Adam 之前把 `λ·w` 加到梯度上；然后对照 `AdamW.step` 里的这两行，说明二者在数学上的区别：

```python
params[i] = params[i] * (1 - self.weight_decay * self.lr)
params[i] -= self.lr * m_hat / (math.sqrt(v_hat) + self.epsilon)
```

**Q11.** STEP 4（Weight Decay Effect）的实际输出是：

```text
  Initial weight L2 norm: 10.0550
  After 100 steps:
    Adam  weight L2 norm: 10.0433
    AdamW weight L2 norm: 9.9434
    AdamW shrinks weights 1.0x more
```

(a) 用 `lr=0.001, weight_decay=0.1` 估算 100 步内 AdamW 的衰减部分让范数缩小了多少，解释为什么打印出 "1.0x"；(b) 只改一个数字让差异肉眼可见，并预测大致结果。

---

## 四、面试高频题

**Q12.**（基础必考）写出 Adam 的完整更新公式，解释每一项的作用，并说明为什么需要偏差修正。Adam 相比 SGD 额外占用多少显存？

**Q13.**（原理深挖）Adam + L2 正则 和 AdamW 有什么区别？为什么在 SGD 里二者等价，到了 Adam 就不等价？

**Q14.**（工程实践）为什么很多 CNN（如 ResNet）仍然用 SGD + Momentum，而 Transformer/LLM 几乎清一色用 AdamW？

**Q15.**（场景设计）你在用 AdamW 微调一个 7B 模型，训练几百步后 loss 突然飙升甚至出现 NaN。从优化器和学习率这一侧，你会按什么顺序排查和调整？

**Q16.**（追问型）有人说"Adam 的 lr 可以理解为每个参数每步最大移动量"。这句话对吗？它对梯度非常小（甚至长期接近 0）的参数意味着什么？ε 起什么作用？

---

## 五、参考答案与解析

### Q1 — 答案：C

稳态时 `m = 0.9·m + g` ⇒ `m = g/(1-0.9) = 10·g`。也就是说本节代码这种"不带 `(1-β)`"的动量（也是 PyTorch `SGD(momentum=0.9)` 的写法）会让**有效步长变成 `lr/(1-β)`**，β=0.9 时放大 10 倍。讲义里"约等于最近 10 个梯度的平均"只描述了"记忆窗口约 10 步"，严格说它是**加权和**而不是平均。带 `(1-β)` 的 EMA 写法（如 Adam 的 m）稳态才是 g，即 A。B、D 是把系数搞反了。

### Q2 — 答案：B

第 1 步：`m₁ = 0.1·0.5 = 0.05`，`v₁ = 0.001·0.25 = 0.00025`；修正后 `m̂ = 0.05/0.1 = 0.5`，`v̂ = 0.00025/0.001 = 0.25`，`√v̂ = 0.5`。更新量 = `0.001 × 0.5/0.5 = 0.001`。结论：Adam 第一步的更新量就是 `lr·sign(g)`，**与梯度大小无关**。A 是 SGD 的答案。

### Q3 — 答案：B

不修正：`m₁/√v₁ = 0.1·g / (√0.001·|g|) = 0.1/0.0316 ≈ 3.16`。所以第一步会比修正后**大约 3.16 倍**，而不是"小 10 倍"。很多人只看到 `m₁` 偏小 10 倍（A），却忘了分母 `√v₁` 偏小 `√1000 ≈ 31.6` 倍，两者合起来反而是偏大。这正是偏差修正对训练稳定性重要的原因：早期步子过大很容易把模型推到坏区域。

### Q4 — 答案：B

`1 - 0.9¹⁰⁰ ≈ 0.99997`，一阶矩修正可以忽略；但 `1 - 0.999¹⁰⁰ ≈ 0.095`，二阶矩还要除以 0.095，即放大约 10.5 倍。β2=0.999 的"记忆"约 1000 步，直到几千步后修正才真正可以忽略。讲义"~50 步后无关"的说法只适用于一阶矩。代码 STEP 2 打印到第 10 步时 `v_raw` 只有 0.009955（真实值是 1），也能看出 v 的偏差远比 m 严重。

### Q5 — 答案：B

Adam+L2 的梯度是 `g + λw`，这个整体会被 `√v̂` 归一化：梯度方差大的参数，`√v̂` 大，正则项被缩得更小；梯度小的参数则相反。正则强度因此依赖梯度统计量，而不是统一地"按比例收缩"。AdamW 把衰减从梯度里**解耦**出来，直接 `w -= lr·λ·w`。A 错：Adam 会把它当普通梯度处理；C、D 都与机制无关。

### Q6 — 答案：B

讲义给的经验值：微调预训练模型用 AdamW，lr=1e-5～5e-5，wd=0.01。A 是 ResNet 从零训练的配方，用在微调上会直接把预训练权重冲掉；C 的 lr 大了几百倍，β1=0.5 是 GAN 的习惯；D 不是主流做法。

### Q7 — 答案：A

`backward` 计算梯度 → 裁剪 → `optimizer.step` 用梯度更新参数 → `scheduler.step` 更新下一步的 lr。B 在 backward 之前 step，用的是旧的（或空的）梯度；C 把 scheduler 放在 optimizer 前面，会让第一个 lr 值被跳过（讲义特别点名的隐蔽 bug）；D 从不 `zero_grad`，PyTorch 的 `.grad` 会**累加**，梯度越来越大。

### Q8 — 参考答案

(a) `grad = 2·(10-3) = 14`，`x = 10 - 0.1·14 = 8.6`，`loss = 5.6² = 31.36`，打印：

```text
    Step  0: x=8.600000, loss=31.360000
```

(b) `x_{new} - 3 = (x - 3) - lr·2(x - 3) = (1 - 2·lr)(x - 3)`。lr=0.1 时每步乘 0.8，所以第 step 次更新后 `x = 3 + 7 × 0.8^(step+1)`。验证 Step 19：`3 + 7 × 0.8²⁰ = 3 + 7 × 0.011529 = 3.080705`，与实际输出一致。

(c) `|1 - 2·lr| < 1` 才收敛，即 `0 < lr < 1`。`lr = 0.5` 时系数为 0，一步到 x=3；`lr = 1` 时系数为 -1，在 10 和 -4 之间永远震荡；`lr > 1` 时 |系数| > 1，发散。对一般二次函数，这个阈值是 `2/L`（L 为曲率，这里 `f'' = 2`）。这就是"lr 太大会发散"的最小模型。

### Q9 — 参考答案

原因有两层：

1. **有效学习率放大 10 倍**。`SGDMomentum.step` 写的是 `v = β·v + g; w -= lr·v`，稳态下 `v ≈ g/(1-β) = 10g`，相当于 SGD 用 lr=0.5。同样标着 `lr=0.05`，momentum 版本的实际步子是 SGD 的 10 倍，两者并不是公平对比。
2. **大步长把 ReLU 神经元推"死"**。隐藏层只有 8 个 ReLU，步子过大时某些神经元的 `w1·x + b1` 在所有样本上都变成负数，梯度恒为 0（`d_relu = 0.0`），再也恢复不了。用训练后的权重统计：SGD(lr=0.05) 只有 1 个死神经元，SGD+Momentum(lr=0.05) 有 **5 个**。剩下 3 个神经元不够拟合圆形边界，所以 loss 停在 0.207、准确率停在 93%。

修复：把 lr 按 `(1-β)` 缩小，即 `SGDMomentum(lr=0.005, beta=0.9)`，有效步长与 SGD(0.05) 相当；实测最终 loss≈0.016、准确率 99%，死神经元降到 2 个。另一种做法是改用带 `(1-β)` 的 EMA 动量。教训：**换优化器时 lr 必须重新调，不能沿用旧值**。

### Q10 — 参考答案

```python
class AdamL2(Adam):
    def __init__(self, lr=0.001, beta1=0.9, beta2=0.999, epsilon=1e-8, l2=0.01):
        super().__init__(lr, beta1, beta2, epsilon)
        self.l2 = l2

    def step(self, params, grads):
        # L2 正则 (λ/2)·w² 的梯度是 λ·w，把它加进梯度后再交给 Adam
        grads = [g + self.l2 * p for g, p in zip(grads, params)]
        super().step(params, grads)
```

数学区别：

- **AdamL2**：`g' = g + λw`，然后 `w -= lr · m̂(g')/(√v̂(g') + ε)`。正则项进入了 m 和 v，被自适应因子 `1/√v̂` 缩放；梯度方差大的参数正则被"稀释"，方差小的参数正则被放大。
- **AdamW**：先 `w *= (1 - lr·λ)`（每个参数都按同一比例收缩），再做纯 Adam 更新。m、v 只统计真实损失的梯度，衰减强度与梯度统计无关。

注意本节代码的 AdamW 是**先衰减、再做 Adam 更新**（衰减作用在旧的 w 上，与 PyTorch 实现顺序一致）；讲义 Build It 里的写法是先 Adam 更新、再对新 w 衰减。两者每步只差 `lr²·λ` 量级的项，结论相同。

### Q11 — 参考答案

(a) 每步衰减因子 `1 - lr·λ = 1 - 0.001×0.1 = 0.9999`，100 步后 `0.9999¹⁰⁰ ≈ 0.990`，只缩小约 1%：`10.055 × 0.990 ≈ 9.955`，再叠加随机梯度带来的抖动，得到 9.9434。Adam 的范数是 10.0433，比值 `10.0433/9.9434 ≈ 1.01`，用 `:.1f` 格式化就成了 "1.0x"。演示的结论没有错，但**步数太少**，效果几乎看不出来（打印语句 "shrinks weights 1.0x more" 本身也容易误导）。

(b) 把 `for step in range(100)` 改成 `range(10000)`。衰减因子变为 `0.9999¹⁰⁰⁰⁰ ≈ e⁻¹ ≈ 0.37`，预计 AdamW 范数约 3.7～3.8，Adam 仍在 10 左右，比值约 2.7。实测：Adam 10.1851、AdamW 3.7862，比值 2.69。也可以把 `weight_decay` 调大，但改步数更能说明"衰减是逐步累积的"。

### Q12 — 参考回答要点

- 公式：
  - `m_t = β1·m_{t-1} + (1-β1)·g_t`（一阶矩，动量，平滑方向）
  - `v_t = β2·v_{t-1} + (1-β2)·g_t²`（二阶矩，逐参数尺度）
  - `m̂ = m_t/(1-β1ᵗ)`，`v̂ = v_t/(1-β2ᵗ)`（偏差修正）
  - `w -= lr · m̂/(√v̂ + ε)`
- 默认值：lr=1e-3，β1=0.9，β2=0.999，ε=1e-8。调参顺序：先调 lr，再调 β2，几乎不动 β1 和 ε。
- 偏差修正：m、v 从 0 起步，前若干步严重偏向 0；不修正时第 1 步 `m₁/√v₁ ≈ 3.16·sign(g)`，步子偏大。β2 越接近 1，偏差持续越久。
- 显存：每个参数额外存 m 和 v 两个状态，即优化器状态 = 2 × 参数量（SGD+Momentum 只需 1 份）。
- 加分点：能说出混合精度训练下，Adam 每个参数大约需要 16 字节（fp16 权重和梯度各 2 字节 + fp32 主权重、m、v 各 4 字节），这正是 ZeRO 等优化器状态切分技术要解决的问题。
- 常见误区：把 `v` 说成"方差"。它是梯度平方的均值（未中心化的二阶矩），不是方差。

### Q13 — 参考回答要点

- 在 SGD 中：loss 加 `(λ/2)·w²` ⇒ 梯度多 `λw` ⇒ `w -= lr·(g + λw) = (1 - lr·λ)w - lr·g`，与"每步把 w 乘以 `(1 - lr·λ)`"完全一样，所以 L2 = weight decay。
- 在 Adam 中：`λw` 进入了 m、v，最终被 `1/(√v̂ + ε)` 缩放。不同参数的有效衰减系数变成 `λ/√v̂`，梯度大的参数几乎不被正则，梯度小的参数被过度正则，等价性被打破。
- AdamW（Loshchilov & Hutter）：把衰减从梯度路径里拿出来，`w -= lr·m̂/(√v̂+ε) + lr·λ·w`，每个参数按同一比例收缩。讲义指出它在几乎所有任务上比 Adam+L2 收敛到更好的解，是 BERT、GPT、LLaMA、Stable Diffusion 的默认选择。
- 工程实践：PyTorch 的 `torch.optim.Adam(weight_decay=...)` 实现的是 L2 式（加到梯度上），`torch.optim.AdamW(weight_decay=...)` 才是解耦式；LLM 训练中通常不对 bias 和 LayerNorm 参数做 weight decay（通过 parameter groups 分组）。
- 常见误区：以为 AdamW 只是"Adam 加了 weight_decay 参数"。

### Q14 — 参考回答要点

- 讲义观点：SGD 倾向于找到更**平坦**的极小值，往往泛化更好；CNN 的配方（SGD lr=0.1、momentum=0.9、wd=1e-4，加 step/cosine 调度）经过多年验证，成熟稳定。
- Transformer 的特点：不同模块（embedding、attention、LayerNorm、输出层）的梯度尺度差异很大，且梯度稀疏（embedding 只有出现过的 token 有梯度）。单一 lr 的 SGD 很难同时照顾到所有参数；Adam 的逐参数自适应对这种异质性特别有效。
- 实践共识：Transformer/LLM 用 AdamW + warmup + cosine 衰减；"不要在没有量化依据的情况下对抗共识"。
- 加分点：说出 Adam 在 CNN 上也能训练，但常见现象是训练集收敛快、测试精度略低，因此有了 AdamW、SWA 等改进；也可以提到 Adam 的显存是 SGD+Momentum 的约 2 倍，超大模型上这本身就是成本。

### Q15 — 参考回答要点

按"成本低、最可能"排序：

1. **学习率**：先看 lr 是否太大（微调通常 1e-5～5e-5）；是否有 warmup（讲义建议前 1–10% 步数线性升温）。warmup 不足是早期发散的常见原因。
2. **梯度裁剪**：加 `clip_grad_norm_(max_norm=1.0)`，并记录每步裁剪前的梯度范数，定位 loss 飙升前是否有梯度尖峰。
3. **β2**：讲义说 lr 之后调 β2。β2=0.999 时 v 对突然变大的梯度反应很慢（记忆约 1000 步），`m̂/√v̂` 会瞬间变大；LLM 训练常把 β2 降到 0.95（如 LLaMA 的配置），让 v 跟得更快。
4. **数值精度**：若优化器状态或计算用 fp16，ε=1e-8 会下溢为 0（fp16 能表示的最小正数约 6e-8），分母可能接近 0；混合精度时还要关注 loss scaling，或改用 bf16，必要时调大 ε。
5. **训练循环本身**：确认顺序是 `zero_grad → forward → loss → backward → clip → step → scheduler.step`，没有遗漏 `zero_grad` 导致梯度累加。
6. **数据侧**：检查出问题的 batch 是否有异常样本（超长序列、label 错误）。

- 加分点：能说"出现 spike 时回滚到最近的 checkpoint，跳过对应数据，降低 lr 继续"这种大模型训练的常规操作。
- 常见误区：一上来就改模型结构，或只把 lr 降 10 倍却不看梯度范数曲线。

### Q16 — 参考回答要点

- 基本正确：`m̂/√v̂` 的量级通常 ≤ 1 左右（梯度方向稳定时约等于 1，方向来回翻转时 m̂ 被抵消、远小于 1），所以每步更新量大致被 lr 约束，**与梯度的绝对尺度无关**（把 loss 乘以 100，Adam 的轨迹几乎不变，SGD 的步长却放大 100 倍）。Q2 中第一步更新量恰为 lr 就是例证。
- 不严格的地方：它不是硬上限。若某参数长期梯度接近 0，`v` 衰减得很小，一旦出现一个较大的梯度，m̂ 先响应而 √v̂ 跟得慢（β2 记忆更长），比值可能明显大于 1，产生偶发的大步。
- 对稀疏/小梯度参数的含义：Adam 会"放大"它们的更新（除以很小的 √v̂），这正是它对 embedding 等稀疏参数友好的原因，但也是不稳定的潜在来源。
- ε 的作用：防止除以 0，并给有效步长设一个上界 `lr·|m̂|/ε`；ε 越大，Adam 越接近"带动量的 SGD"（分母近似常数）。
- 加分点：把这和梯度裁剪联系起来：裁剪限制的是梯度范数，Adam 的归一化限制的是逐参数步长，两者互补。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 05 Loss Functions](../../05-loss-functions/docs/zh.md)：本节的圆形数据集和二元交叉熵梯度都来自上一节。
- [阶段 03 · 03 Backpropagation 从头开始](../../03-backpropagation/docs/zh.md)：`compute_grads` 就是手写的反向传播。
- [阶段 01 · 08 优化](../../../01-math-foundations/08-optimization/docs/zh.md)：梯度下降、学习率、鞍点的数学基础。
- [阶段 01 · 04 机器学习中的微积分](../../../01-math-foundations/04-calculus-for-ml/docs/zh.md)：导数与梯度。

### 本节被哪些后续内容用到
- [阶段 03 · 07 正则化](../../07-regularization/docs/zh.md)：L2 / weight decay 的完整讨论，以及它与 AdamW 的关系。
- [阶段 03 · 08 Weight 初始化和训练稳定性](../../08-weight-initialization/docs/zh.md)：初始化不当时，再好的优化器也救不回梯度消失/爆炸。
- [阶段 03 · 09 Learning Rate Schedules 和 Warmup](../../09-learning-rate-schedules/docs/zh.md)：本节反复提到的 warmup + cosine，在下一节完整实现。
- [阶段 03 · 10 构建您自己的迷你框架](../../10-mini-framework/docs/zh.md)：把本节的优化器封装进自己的框架。
- [阶段 03 · 11 PyTorch 简介](../../11-intro-to-pytorch/docs/zh.md)：`torch.optim` 的实际用法。
- [阶段 10 · 04 预训练 mini-GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：用 AdamW 训练语言模型。
- [阶段 19 · 44 Cosine LR + Warmup](../../../19-capstone-projects/44-cosine-lr-warmup/docs/zh.md) 与 [阶段 19 · 45 梯度裁剪与 AMP](../../../19-capstone-projects/45-gradient-clipping-amp/docs/zh.md)：本节"训练循环顺序"在工程项目中的落地。
- [阶段 19 · 78 ZeRO 参数切分](../../../19-capstone-projects/78-zero-parameter-sharding/docs/zh.md)：Adam 的 m、v 状态如何在多卡间切分。

### 延伸关键词
`Nesterov 动量` · `AdaGrad` · `AMSGrad` · `LAMB / LARS（大 batch 优化器）` · `Lion` · `LR range test` · `梯度裁剪（clip by global norm）` · `parameter groups（不衰减 bias/LayerNorm）` · `optimizer state sharding（ZeRO）`
