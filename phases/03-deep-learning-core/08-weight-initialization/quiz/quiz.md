# 测验 · 权重初始化和训练稳定性（Weight Initialization and Training Stability）

> **阶段 03 · 深度学习核心 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 对称性问题 | 同一层权重相同（全 0 是极端情况）⇒ 输出相同、梯度相同、更新相同，宽度再大也只等于 1 个神经元；随机初始化用来打破对称 |
| 2 | 方差传播 | `Var(z) = fan_in · Var(w) · Var(x)`；每层乘一个系数，系数 >1 指数爆炸、<1 指数消失，深度越大越敏感 |
| 3 | 目标：逐层方差不变 | 选 `Var(w)` 让每层的方差系数等于 1；验证方法是逐层打印激活的统计量（讲义建议幅度保持在 0.5–2.0） |
| 4 | Xavier / Glorot | `Var(w) = 2/(fan_in + fan_out)`，兼顾前向和反向；均匀分布版本 `limit = √(6/(fan_in+fan_out))`；面向 tanh/sigmoid 这类"零点附近近似线性"的激活 |
| 5 | Kaiming / He | `Var(w) = 2/fan_in`；ReLU 把一半输出置 0，`E[ReLU(z)²] = Var(z)/2`，系数 2 正好补回来；GELU/Swish 也常用它 |
| 6 | 初始化要与激活匹配 | sigmoid/tanh → Xavier，ReLU/Leaky ReLU/GELU → Kaiming；用错会让信号逐层衰减或放大 |
| 7 | 残差缩放（GPT-2） | 每次 `x = x + sublayer(x)` 都会累加方差；把残差分支输出投影的初始权重乘 `1/√(2N)`（N 为层数），让残差流不随深度膨胀 |
| 8 | 框架中的初始化 | `nn.init.xavier_uniform_/kaiming_normal_` 等；HuggingFace 模型在 `_init_weights` 里处理；自己搭 Transformer 要手动加残差缩放 |

### 核心技能（能动手做到）

- [ ] 从零实现 `zero_init`、`random_init`、`xavier_init`、`kaiming_init`，并用大量采样验证权重和单层输出的方差符合公式
- [ ] 给定 `fan_in`、`Var(w)`、层数，手算每层方差系数和 L 层后的放大/衰减倍数
- [ ] 跑通 50 层前向实验，读懂结果表，并指出"平均绝对激活值"这个指标在 sigmoid 上会误判
- [ ] 给 Xavier 加上增益（gain）参数，验证 tanh 网络用 `gain = 5/3` 后 50 层的激活幅度保持稳定
- [ ] 实现 GPT-2 式残差缩放，对比有无缩放时残差流幅度随层数的增长
- [ ] 用 PyTorch 的 `nn.init` 为指定激活函数选对初始化，并能说出 `nn.Linear` 的默认初始化具体是什么

---

## 二、基础自测（选择题）

**Q1.** 一个两层 MLP（隐藏层 sigmoid），**所有**权重和偏置都初始化为 0，然后正常用梯度下降训练很多步。隐藏层的各个神经元最终会：

- A. 始终完全相同
- B. 因为 SGD 的随机性逐渐变得不同
- C. 全部变成 0 并停止输出
- D. 只有第一个神经元会被更新

**Q2.** 线性层 `fan_in = 256`，每个权重 `Var(w) = 0.01`，输入 `Var(x) = 1`、均值为 0。单层输出方差和堆叠 10 层（不加激活）后的方差大约是：

- A. 0.01 和 1e-20
- B. 2.56 和约 1.2e4
- C. 256 和约 1.2e24
- D. 1 和 1

**Q3.** 一个 ReLU 层 `fan_in = 512`，用 Kaiming normal 初始化，权重的标准差是：

- A. 0.0625
- B. 约 0.0442
- C. 约 0.0039
- D. 约 0.0884

**Q4.** Kaiming 初始化里的系数 2（相对于 `1/fan_in`）是为了：

- A. 让权重的分布更宽，加快收敛
- B. 补偿 ReLU 把一半的输入置 0，使 `E[ReLU(z)²] = Var(z)/2` 造成的方差减半
- C. 同时照顾前向和反向两个方向
- D. 抵消偏置项带来的额外方差

**Q5.** 一个 `fan_in = fan_out = 100` 的层使用 Xavier **均匀分布**初始化，均匀分布的边界 `limit` 是：

- A. 0.1
- B. 约 0.173
- C. 0.03
- D. 约 0.245

**Q6.** GPT-2 small 有 12 个 Transformer block。按讲义"残差分支的权重乘以 `1/√(2N)`、N 为层数"的做法，缩放系数约为：

- A. 0.289
- B. 0.204
- C. 0.042
- D. 0.5

**Q7.** 关于 PyTorch `nn.Linear(fan_in, fan_out)` 的**默认**权重初始化，下面哪个说法准确？

- A. 全部初始化为 0
- B. 标准 He 正态初始化，`Var(w) = 2/fan_in`
- C. `kaiming_uniform_(a=√5)`，等价于 `U(-1/√fan_in, 1/√fan_in)`，`Var(w) = 1/(3·fan_in)`
- D. Xavier 正态初始化

---

## 三、动手 / 代码题

**Q8.** `main.py` STEP 2 的实际输出：

```text
Variance Analysis (fan_in=64, single layer):
  Strategy                    Weight Var   Output Var      Ratio
  Random N(0,1)                 1.000000      63.1933    63.1933
  Random N(0,0.01)              0.000100       0.0063     0.0063
  Xavier std                    0.015625       0.9874     0.9874
  Kaiming std                   0.031250       1.9748     1.9748
```

(a) 用公式解释每一行的 Output Var。(b) Kaiming 的输出方差约为 2，为什么这不是"放大了信号"，而恰恰是正确的？(c) 为什么 Ratio 列和 Output Var 列完全相同？

**Q9.** STEP 3 中两行结果几乎一样：

```text
Strategy                               L1         L5        L10        L25        L50
Zero + Sigmoid                     0.5000     0.5000     0.5000     0.5000     0.5000
Xavier + Sigmoid                   0.4994     0.5036     0.5029     0.5037     0.4982
```

`forward_deep` 用"每个样本激活绝对值的平均"作为指标：

```python
        magnitudes = []
        for sample in inputs:
            magnitudes.append(sum(abs(v) for v in sample) / width)
        mean_mag = sum(magnitudes) / len(magnitudes)
```

(a) 零初始化显然是"死"网络，为什么它和 Xavier + Sigmoid 的数字一样？这能说明 Xavier + Sigmoid 在 50 层中保住了信号吗？(b) 设计一个更能反映"信号是否还在"的指标，写出代码。

**Q10.** STEP 3 中 `Xavier + Tanh` 从 L1 的 0.5465 逐渐降到 L50 的 0.0576。(a) 解释为什么 Xavier（这里 `Var(w) = 1/64`）配 tanh 仍然会逐层衰减；(b) 写一个带增益参数的 `xavier_init_gain(fan_in, fan_out, gain)`，用 `gain = 5/3` 替换后预测 L50 的幅度大致是多少。

**Q11.** STEP 5 训练对比的实际输出：

```text
  Config                           Start Loss     End Loss  Improvement
  Random(0.01) + Sigmoid             0.213427     0.205097         3.9%
  Random(1.0) + Sigmoid              0.257682     0.018135        93.0%
  Xavier + Sigmoid                   0.220716     0.022327        89.9%
  Random(0.01) + ReLU                0.222634     0.007044        96.8%
  Random(1.0) + ReLU                 0.395736     0.004482        98.9%
  Kaiming + ReLU                     0.261864     0.004715        98.2%
```

(a) `Random(1.0) + ReLU` 的最终 loss 甚至比 `Kaiming + ReLU` 还低，这和本节结论矛盾吗？请结合 `train_with_init` 中 `std_w1`、`std_w2` 的计算说明。(b) 为什么 `Random(0.01) + Sigmoid` 几乎学不动，而 `Random(0.01) + ReLU` 却能学好？

---

## 四、面试高频题

**Q12.**（基础必考）为什么神经网络的权重不能全部初始化为 0？偏置可以初始化为 0 吗？"随机但很小"的初始化又有什么问题？

**Q13.**（原理深挖）推导 Xavier 和 Kaiming 初始化的方差公式。Xavier 为什么是 `2/(fan_in + fan_out)` 这种"折中"形式？

**Q14.**（工程实践）Transformer / LLM 的初始化有哪些特殊之处？为什么要对残差分支做缩放？

**Q15.**（场景设计）你搭了一个 50 层的 MLP，训练一开始 loss 就完全不动（或者第一步就变成 NaN）。你如何判断问题是否出在初始化上？怎么修？

**Q16.**（追问型）既然有 BatchNorm / LayerNorm 和残差连接，初始化还重要吗？有没有"故意初始化为 0"的成功做法？

---

## 五、参考答案与解析

### Q1 — 答案：A

全零时，隐藏层所有神经元的输出都是 `sigmoid(0) = 0.5`。输出层权重 `w2` 也全为 0，所以回传到每个隐藏神经元的梯度 `d_out · w2[i] · σ'` 全是 0，`w1` 第一步不动；`w2` 的梯度 `d_out · h[i]` 对所有 i 相同，更新后 `w2` 各分量仍然相等。此后每一步，各神经元收到的梯度始终相同，对称性永远打不破。SGD 的随机性来自样本顺序，对同一层所有神经元是"同样的随机"，打破不了对称（B 错）。

### Q2 — 答案：B

`Var(z) = 256 × 0.01 × 1 = 2.56`。每层系数 2.56，10 层后 `2.56¹⁰ ≈ 1.2 × 10⁴`。系数只比 1 大一点点，堆叠后就是上万倍——这就是讲义说"能用和崩溃之间的边界极窄"的原因。C 是把 `Var(w)` 当成 1 的结果。

### Q3 — 答案：A

`std = √(2/fan_in) = √(2/512) = √(1/256) = 0.0625`。B 是 `√(1/512)`（LeCun 初始化）；C 是把方差 `2/512` 当成了标准差；D 是 `√(4/512)`。注意公式给的是**方差**，`random.gauss` 和 `torch.normal` 要的是**标准差**，代码里 `std = math.sqrt(2.0 / fan_in)` 正是这一步。

### Q4 — 答案：B

z 关于 0 对称时，ReLU 保留正半部分，`E[ReLU(z)²] = Var(z)/2`，下一层的输入二阶矩只剩一半。让 `fan_in · Var(w) · Var(z)/2 = Var(z)` 得 `Var(w) = 2/fan_in`。C 描述的是 Xavier 的 `fan_in + fan_out` 折中；A、D 与推导无关。

### Q5 — 答案：B

`limit = √(6/(100+100)) = √0.03 ≈ 0.173`。验证：`U(-a, a)` 的方差是 `a²/3 = 0.03/3 = 0.01 = 2/(100+100)`，与 Xavier 的方差公式一致。"6" 就是这样来的：`3 × 2`。

### Q6 — 答案：B

`1/√(2×12) = 1/√24 ≈ 0.204`。"2N" 中的 2 是因为每个 block 里有两个残差分支（attention 和 MLP），一共 24 次残差相加。A 是 `1/√12`。讲义的 Use It 部分写成了 "1/sqrt(N)"，这是把 N 定义成"残差层数"（= 2 × block 数）时的写法，两者说的是同一件事，读论文和代码时要先看清 N 的定义。

### Q7 — 答案：C

PyTorch 的 `nn.Linear.reset_parameters` 调用 `kaiming_uniform_(weight, a=math.sqrt(5))`：增益 `√(2/(1+5)) = √(1/3)`，边界 `√(1/3)·√(3/fan_in) = 1/√fan_in`，方差 `1/(3·fan_in)`，只有标准 He 初始化（`2/fan_in`）的 1/6。所以名字里带 "kaiming"，但**并不是**针对 ReLU 的 He 初始化。讲义说"PyTorch 默认就是 Kaiming uniform，所以已经做了正确选择"是一种简化；层数较深时最好显式调用 `nn.init.kaiming_normal_(w, nonlinearity='relu')` 等函数。

### Q8 — 参考答案

(a) 输入 `x ~ N(0,1)`，单层线性输出 `Var(z) = 64 · Var(w) · 1`：

| 策略 | 公式 | 理论值 | 实测 |
|------|------|-------|------|
| N(0,1) | 64 × 1 | 64 | 63.19 |
| N(0,0.01) | 64 × 0.0001 | 0.0064 | 0.0063 |
| Xavier | 64 × 2/128 | 1 | 0.987 |
| Kaiming | 64 × 2/64 | 2 | 1.975 |

实测值来自 10,000 次蒙特卡洛采样，与理论值相差约 1%。

(b) 这里只算了线性部分 `z`，没有经过 ReLU。实际网络中 z 之后紧跟 ReLU，`E[ReLU(z)²] = Var(z)/2 = 1`，下一层输入的二阶矩正好回到 1。Kaiming 是"预先放大 2 倍，等 ReLU 砍掉一半"。如果后面接的是 tanh，用 Kaiming 就真的偏大了。

(c) 代码里 `ratio = mean_output_var`，并没有除以输入方差。因为输入方差恰好是 1，`Var(z)/Var(x) = Var(z)`，两列在数值上必然相同；这一列是冗余的，只有输入方差不为 1 时才需要真正相除。另外，`output_vars.append(z * z)` 求的是 `E[z²]`，因为 z 的均值为 0，它等于方差。

### Q9 — 参考答案

(a) sigmoid 的输出在 0.5 附近：零初始化时每个神经元都恒为 `sigmoid(0) = 0.5`；Xavier + Sigmoid 时各神经元在 0.5 上下小幅波动。"平均绝对值"这个指标被 0.5 的**偏移**主导，根本看不出信号是否还在。

实际上 Xavier + Sigmoid 的信号也几乎消失了：sigmoid 在 0 附近的斜率只有 1/4，而且输出均值是 0.5 而不是 0。输入中区分不同样本的那部分变化每过一层大约缩小为原来的 1/4，常数偏移 0.5 对所有样本都一样，不携带信息。用下面的指标实测：Xavier + Sigmoid 第 1 层跨样本标准差约 0.204，第 10 层已经小于 1e-6（四舍五入为 0）。也就是说，50 层后网络对所有输入都输出几乎相同的值，和零初始化一样"死"。讲义里"Xavier + Sigmoid 在 50 层后约 1.0、信号稳定"的说法与实际运行结果不符。

(b) 改为度量**同一神经元在不同样本上的标准差**（信号 = 能区分输入的变化）：

```python
import math

def cross_sample_std(inputs):
    """inputs: [n_samples][width]，返回各神经元跨样本标准差的平均值"""
    n, width = len(inputs), len(inputs[0])
    stds = []
    for k in range(width):
        col = [s[k] for s in inputs]
        m = sum(col) / n
        stds.append(math.sqrt(sum((c - m) ** 2 for c in col) / n))
    return sum(stds) / width
```

把它放进 `forward_deep` 每层的统计中：零初始化各层都是 0，Xavier + Sigmoid 迅速降到 0，而 Xavier(gain=5/3) + Tanh 在 50 层保持在 0.63 左右。也可以同时打印均值和标准差，均值反映偏移，标准差反映信号。

### Q10 — 参考答案

(a) Xavier 的推导假设激活在 0 附近斜率为 1（近似恒等映射）。tanh 在 0 点斜率为 1，但只要输入稍微偏离 0，`tanh'(z) < 1`，并且 tanh 会把大值压缩到 ±1 以内，所以每层输出方差都略小于输入方差。系数略小于 1，乘 50 次就衰减了约一个数量级（0.55 → 0.058）。

(b)

```python
def xavier_init_gain(fan_in, fan_out, gain=1.0):
    std = gain * math.sqrt(2.0 / (fan_in + fan_out))
    return [[random.gauss(0, std) for _ in range(fan_in)] for _ in range(fan_out)]

mags = forward_deep(lambda fi, fo: xavier_init_gain(fi, fo, 5 / 3), tanh_act)
```

`5/3` 是 PyTorch `nn.init.calculate_gain('tanh')` 给出的增益，用来补偿 tanh 的压缩。实测各层幅度为 L1 0.689、L5 0.591、L10 0.589、L25 0.606、L50 0.570，基本保持不变。增益是在不改变 Xavier 结构的前提下，针对具体激活函数做的修正；Kaiming 的 `√2` 就是 ReLU 的增益。

### Q11 — 参考答案

(a) 不矛盾。看 `train_with_init` 的设置：

```python
        elif init_name == "kaiming":
            std_w1 = math.sqrt(2.0 / 2)
            std_w2 = math.sqrt(2.0 / hidden_size)
        else:
            std_w1 = init_scale
            std_w2 = init_scale
```

第一层 `fan_in = 2`，Kaiming 的 `std_w1 = √(2/2) = 1.0`，和 `Random(1.0)` **完全一样**；两者只在 `w2` 上不同（0.5 vs 1.0）。更重要的是，这个网络只有**一个隐藏层**，方差爆炸/消失是"每层乘一个系数、层数越多越严重"的指数效应，浅网络里几乎体现不出来。初始化的价值要在深网络（STEP 3）里看。

(b) `Random(0.01) + Sigmoid`：所有隐藏单元输出都约等于 `sigmoid(0) = 0.5`，几乎没有区分度；回传到隐藏层的梯度 `d_out · w2[i] · σ'(z)` 中 `w2[i] ≈ 0.01`、`σ' ≤ 0.25`，非常小；输出层又是 MSE + sigmoid，`d_out = error · out · (1 - out)` 本身就被压小。网络长时间停留在近似对称的状态，300 个 epoch 只降了 3.9%。

`Random(0.01) + ReLU`：ReLU 在正区间导数恒为 1，不会额外缩小梯度；而且 ReLU 输出与 z 成正比，小权重下各神经元的输出虽然小，但依然保留了输入的差异（没有 0.5 这样的常数偏移把信号淹没）。对浅网络来说，小初始化只是"起步慢一点"，所以最终也能学好。

### Q12 — 参考回答要点

- **权重不能全 0（或全相同）**：同一层的神经元结构相同，输入相同、权重相同 ⇒ 输出相同 ⇒ 梯度相同 ⇒ 更新相同，对称性永远保持，宽度为 512 的层等于 1 个神经元（讲义："你为 512 个参数付了钱，只得到 1 个"）。
- **偏置可以初始化为 0**：只要权重是随机的，各神经元的输出已经不同，对称性已被打破；偏置为 0 是最常见的默认做法（代码中 `biases = [0.0] * width`）。
- **"随机但很小"的问题**：对称性破了，但尺度不对。每层方差系数 `fan_in · Var(w) ≪ 1`，信号逐层指数衰减（代码中 N(0, 0.01) + ReLU 第 5 层就小于 1e-6），梯度也随之消失；对 sigmoid/tanh 还会让网络停留在近似线性的区域。
- **"随机但很大"的问题**：信号指数爆炸（N(0,1) + ReLU 第 10 层超过 1e6），或者 sigmoid/tanh 饱和、梯度为 0。
- 加分点：能说出正确的尺度取决于 `fan_in`（和激活函数），所以"固定 std 的随机初始化"在宽层上必然失效。

### Q13 — 参考回答要点

- 前向：`z = Σᵢ wᵢxᵢ`，w 与 x 独立、w 均值为 0 ⇒ `Var(z) = fan_in · Var(w) · E[x²]`。
- 线性/tanh（零点附近斜率为 1）：`E[x²] ≈ Var(z_prev)`，前向方差不变要求 `fan_in · Var(w) = 1`。
- 反向：梯度 `∂L/∂x = Σⱼ wⱼ · ∂L/∂zⱼ`，对 fan_out 个输出求和 ⇒ 反向方差不变要求 `fan_out · Var(w) = 1`。
- 两个条件只有在 `fan_in = fan_out` 时才能同时满足，Glorot & Bengio 取折中，用两者的平均值代替：`Var(w) = 1/((fan_in + fan_out)/2) = 2/(fan_in + fan_out)`。均匀分布版本 `U(-a, a)` 方差为 `a²/3`，得 `a = √(6/(fan_in + fan_out))`。
- ReLU：`E[x²] = Var(z_prev)/2` ⇒ `fan_in · Var(w)/2 = 1` ⇒ `Var(w) = 2/fan_in`（He 等，2015）。Kaiming 通常只保证前向（`mode='fan_in'`），也可选 `fan_out` 模式保证反向。
- 加分点：增益（gain）的统一视角 `Var(w) = gain²/fan`：线性/sigmoid 为 1，tanh 为 5/3，ReLU 为 √2；LeCun 初始化 `1/fan_in`（配 SELU）。
- 常见误区：把方差公式当标准差用；以为 Xavier 对 sigmoid 很合适（sigmoid 斜率只有 1/4 且非零均值，深层效果很差，见代码 Q9）。

### Q14 — 参考回答要点

- 残差流方差累积：`x_{l+1} = x_l + F(x_l)`，若各分支输出近似独立，`Var(x_L) ≈ Var(x_0) + Σ Var(F)`，随层数线性增长。深层时残差流越来越大，后续 LayerNorm 和输出层都要处理越来越大的数值，训练早期不稳定。
- GPT-2 的做法：残差分支末端的投影（attention 的输出投影、MLP 的第二个线性层）初始化时乘 `1/√(2N)`（N 为 block 数，每个 block 两次残差相加），让总方差增量与深度无关。
- 其他常见设置：GPT-2 系列线性层和 embedding 用 `std = 0.02` 的正态初始化（阶段 10 · 04 中提到这个值来自 GPT-2）；HuggingFace 模型在 `_init_weights` 中统一处理；自己从零实现必须手动加上残差缩放。
- 与架构的配合：Pre-LN 把归一化放在分支内部、残差主干不归一化，比 Post-LN 更稳定；但正因为主干不归一化，残差缩放更重要。
- 加分点：能把 `1/√(2N)` 和"N 个独立随机变量求和，方差乘 N，标准差乘 √N"联系起来；指出 warmup 也是为了缓解训练初期的不稳定（下一节内容）。

### Q15 — 参考回答要点

1. **逐层打印激活统计量**：对一批数据做一次前向，记录每层激活的均值、标准差（以及 ReLU 的"死亡比例"、tanh/sigmoid 的饱和比例）。正常情况下各层量级相近（讲义建议幅度在 0.5–2.0 之间）；如果随层数单调指数变大或变小，就是初始化/尺度问题。在 PyTorch 里可以用 forward hook 实现。
2. **逐层打印梯度范数**：反向一次，看前几层的梯度是否比后几层小/大几个数量级（梯度消失/爆炸）。
3. **注意指标陷阱**：sigmoid 的输出有 0.5 偏移，看平均绝对值会误判（本节代码 Q9），应看跨样本标准差。
4. **修复**：
   - 按激活函数换成正确的初始化（ReLU → Kaiming，tanh → Xavier + gain 5/3），偏置置 0；
   - 加归一化层（BatchNorm / LayerNorm）和残差连接，残差分支做缩放；
   - 数据驱动的方法：LSUV（Mishkin & Matas，"All You Need is a Good Init"）先正交初始化，再逐层用一批数据把输出方差缩放到 1；
   - 避免在深层隐藏层用 sigmoid。
5. **排除其他原因**：学习率过大（NaN）、输入未归一化、损失函数数值不稳定。
- 加分点：说出"先在 5 层上验证能跑，再加深"和"在 1 个 batch 上过拟合"这类调试套路（阶段 03 · 13 调试神经网络）。

### Q16 — 参考回答要点

- 归一化层降低了对**前向尺度**的敏感度：每层输出被重新归一化，权重整体放大/缩小几倍不会逐层累积。这就是为什么现代网络对初始化没那么"脆弱"。
- 但初始化依然重要：
  - 对称性仍然需要随机初始化来打破；
  - 残差主干（Pre-LN 结构中）不经过归一化，分支输出的尺度仍会逐层累积，所以 GPT-2 要做残差缩放；
  - 训练初期梯度的尺度、softmax/attention 是否饱和都受初始化影响。
- 故意初始化为 0 的成功做法（关键是不破坏对称性的前提）：
  - **残差块最后一个 BN 的 γ 初始化为 0**：每个残差块初始时是恒等映射，网络相当于"浅网络"起步，深 ResNet 更容易训练（torchvision 的 ResNet 提供 `zero_init_residual` 选项）；
  - **LoRA 的 B 矩阵初始化为 0、A 随机**：`ΔW = B·A = 0`，微调开始时模型输出不变；A 是随机的，梯度能正常流到 B，不会出现对称性问题；
  - 偏置初始化为 0。
- 加分点：总结一句"0 初始化本身不是问题，问题是让**同一层的多个神经元**处于完全相同的状态"。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 04 Activation Functions](../../04-activation-functions/docs/zh.md)：sigmoid/tanh/ReLU 的形状、导数和饱和区，决定了初始化该怎么选。
- [阶段 03 · 07 正则化](../../07-regularization/docs/zh.md)：BatchNorm/LayerNorm 如何降低对初始化尺度的敏感度。
- [阶段 03 · 03 Backpropagation 从头开始](../../03-backpropagation/docs/zh.md)：梯度消失/爆炸来自反向传播中逐层相乘。
- [阶段 01 · 06 概率与分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：方差、独立随机变量之和的方差，是本节推导的基础。
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：溢出、下溢与浮点范围。

### 本节被哪些后续内容用到
- [阶段 03 · 09 Learning Rate Schedules 和 Warmup](../../09-learning-rate-schedules/docs/zh.md)：warmup 与初始化一起保证训练初期的稳定性。
- [阶段 03 · 11 PyTorch 简介](../../11-intro-to-pytorch/docs/zh.md)：`nn.init` 的实际使用。
- [阶段 03 · 13 调试神经网络](../../13-debugging-neural-networks/docs/zh.md)：坏初始化导致的死 ReLU 等问题的诊断与修复。
- [阶段 04 · 03 CNN：从 LeNet 到 ResNet](../../../04-computer-vision/03-cnns-lenet-to-resnet/docs/zh.md)：深层 CNN 与残差结构中的初始化。
- [阶段 10 · 04 预训练 mini-GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：GPT-2 的 `std = 0.02` 初始化。
- [阶段 19 · 35 GPT 模型组装](../../../19-capstone-projects/35-gpt-model-assembly/docs/zh.md)：残差投影按 `1/√(2·num_layers)` 缩放的工程实现。

### 延伸关键词
`LeCun 初始化（SELU）` · `正交初始化` · `LSUV` · `calculate_gain` · `fan_in / fan_out 模式` · `zero_init_residual` · `Fixup / T-Fixup` · `μP（Maximal Update Parametrization）` · `信号传播 / 动力等距（dynamical isometry）`
