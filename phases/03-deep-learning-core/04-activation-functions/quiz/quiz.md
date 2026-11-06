# 测验 · 激活函数（Activation Functions）

> **阶段 03 · 深度学习核心 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么必须有非线性 | `W2(W1x + b1) + b2 = Ax + c`：没有激活函数，100 层网络也只等于 1 层线性变换 |
| 2 | Sigmoid | 值域 (0,1)，`σ' = σ(1−σ) ≤ 0.25`；两端饱和、输出恒正（非零中心），深层网络梯度消失 |
| 3 | Tanh | 值域 (−1,1)、以 0 为中心，`tanh' = 1 − tanh² ≤ 1`；比 sigmoid 好，但两端仍饱和；`tanh(x) = 2σ(2x) − 1` |
| 4 | ReLU | `max(0, x)`，正区间导数恒为 1，计算便宜、激活稀疏；代价是"死神经元"（输入恒负 → 输出、梯度恒为 0） |
| 5 | Leaky ReLU | 负区间保留小斜率 α（常取 0.01），死神经元仍有梯度、可以恢复；PReLU 让 α 可学习 |
| 6 | GELU | `x·Φ(x)`（Φ 为标准正态 CDF），常用 tanh 近似；平滑、允许小负值（最小约 −0.17），BERT / GPT 等 Transformer 的默认选择 |
| 7 | Swish / SiLU | `x·σ(x)`，由自动搜索发现；与 GELU 形状和效果都很接近，用于 EfficientNet 等 |
| 8 | Softmax | 只用于输出层，把 logits 变成和为 1 的概率分布；实现时先减最大值防溢出（平移不变性保证结果不变） |
| 9 | 选型速查 | Transformer 隐藏层 → GELU；CNN / 简单 MLP → ReLU；RNN → tanh（门用 sigmoid）；输出层：二分类 sigmoid、多分类 softmax、回归不加激活 |

### 核心技能（能动手做到）

- [ ] 从零实现 sigmoid、tanh、ReLU、Leaky ReLU、GELU、Swish、softmax 及其导数，并用中心差分验证每个导数
- [ ] 用 `gradient_scan` 统计各激活函数在 [−5, 5] 上导数接近 0 的比例，并能指出这个指标忽略了什么
- [ ] 写一个死神经元检测器，并能通过调整 bias 人为制造死神经元
- [ ] 在相同初始化下训练 sigmoid / ReLU / GELU 三个网络，比较收敛速度并解释差异
- [ ] 设计一个能真正测出"梯度消失"的实验（多层、合理初始化、测反向梯度而非前向激活）
- [ ] 写出数值稳定的 softmax，并说明为什么减去最大值结果不变
- [ ] 面对一个新架构（Transformer / CNN / RNN / 输出层），给出激活函数选择并说出理由

---

## 二、基础自测（选择题）

**Q1.** 关于 tanh 与 sigmoid 的关系，下列等式正确的是：

- A. `tanh(x) = σ(x) − 0.5`
- B. `tanh(x) = 2σ(2x) − 1`
- C. `tanh(x) = σ(x)²`
- D. `tanh(x) = 1 − σ(x)`

**Q2.** 下列哪种情况最容易导致 ReLU 网络中出现大量死神经元？

- A. 使用 He 初始化
- B. 对输入做了标准化
- C. 学习率过大，某次更新把一批神经元的 bias 推到很大的负值
- D. 改用 Adam 优化器

**Q3.** 关于 GELU（`x·Φ(x)`），下列说法正确的是：

- A. 它是单调递增函数
- B. 它的输出范围是 [0, +∞)
- C. 它在 x ≈ −0.75 附近取得最小值约 −0.17，负半轴允许小的负输出
- D. 它在 x < 0 时导数恒为 0

**Q4.** 代码中的 softmax 先计算 `max_x = max(xs)`，再对 `x - max_x` 求指数。这样做的主要原因是：

- A. 让输出的和更精确地等于 1
- B. 防止 `math.exp` 在 logits 很大时溢出；由于 softmax 的平移不变性，结果与不减时完全相同
- C. 让输出变成 one-hot
- D. 让梯度更大，训练更快

**Q5.** 一个图像多标签分类任务：一张图可以同时包含"猫""狗""人"中的任意几个。输出层最合适的激活是：

- A. 对 3 个 logits 做 softmax
- B. 对每个类别的 logit 各自做 sigmoid
- C. ReLU
- D. tanh

**Q6.** 运行 `gradient_scan` 得到 `Sigmoid: 9% dead zone`、`Tanh: 41% dead zone`。由此得出"sigmoid 比 tanh 更不容易梯度消失"，这个结论：

- A. 正确，sigmoid 导数接近 0 的区间更小
- B. 错误：这个指标只统计 `|g| < 0.01` 的点数，忽略了导数本身的大小——sigmoid 导数最大只有 0.25，tanh 最大为 1，多层连乘时起决定作用的是导数的量级
- C. 正确，因为 sigmoid 输出恒为正
- D. 无法判断，因为两个函数值域不同

**Q7.** 讲义说 sigmoid 输出恒为正会导致梯度下降"之"字形（zig-zag）前进。根本原因是：

- A. sigmoid 的导数可能为负
- B. 下一层某个神经元对其所有输入权重的梯度为 `δ·hᵢ`，当所有 `hᵢ > 0` 时这些梯度同号，权重只能整体同增或同减，难以沿最优方向直接前进
- C. sigmoid 计算慢
- D. sigmoid 输出可能超过 1

---

## 三、动手 / 代码题

**Q8.** STEP 3 的"梯度消失实验"实际输出如下（节选）：

```text
Sigmoid through 10 layers:
  Layer  1: magnitude = 0.505242 ##########
  Layer  5: magnitude = 0.506911 ##########
  Layer 10: magnitude = 0.662811 #############

ReLU through 10 layers:
  Layer  1: magnitude = 0.020967
  Layer  5: magnitude = 0.000099
  Layer  6: magnitude = 0.000000
  Layer 10: magnitude = 0.000000
```

对应代码：

```python
def vanishing_gradient_experiment(activation_fn, name, n_layers=10, n_inputs=5):
    random.seed(42)
    values = [random.gauss(0, 1) for _ in range(n_inputs)]
    # ...
    for layer in range(n_layers):
        weights = [random.gauss(0, 1) for _ in range(n_inputs)]
        z = sum(w * v for w, v in zip(weights, values))
        activated = activation_fn(z)
        magnitude = abs(activated)
        # ...
        values = [activated] * n_inputs
```

(a) 这个结果看起来是"sigmoid 没有消失、ReLU 反而消失了"，和讲义结论相反。请解释原因：这个实验实际测的是什么？
(b) 设计一个能真正测出"梯度消失"的实验（可以用 NumPy），并给出你预期的结论。

**Q9.** 代码中 GELU 及其导数是这样写的：

```python
def gelu(x):
    return 0.5 * x * (1 + math.tanh(math.sqrt(2 / math.pi) * (x + 0.044715 * x ** 3)))


def gelu_derivative(x):
    phi = 0.5 * (1 + math.erf(x / math.sqrt(2)))
    pdf = math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
    return phi + x * pdf
```

(a) 这两个函数之间有什么不一致？会带来多大误差？
(b) 写出 tanh 近似版 GELU 的精确导数 `gelu_tanh_derivative(x)`，并用中心差分验证。

**Q10.** STEP 4 的死神经元检测输出 `Dead (never fired): 0`、`Dead neuron rate: 0.0%`，而讲义说"实践中 10%–40% 的 ReLU 神经元可能在训练中死亡"。
(a) 为什么这个检测器在默认参数下一个死神经元也没找到？
(b) 只修改一行代码，让检测器能"制造"出死神经元，并说明你观察到的现象。

---

## 四、面试高频题

**Q11.**（基础必考）请比较 sigmoid、tanh、ReLU、GELU 的公式、导数范围、优缺点和典型使用场景。

**Q12.**（原理深挖）什么是 dead ReLU？它是怎么产生的？训练中如何检测？有哪些缓解办法？

**Q13.**（原理深挖）为什么 BERT、GPT 等 Transformer 用 GELU 而不是 ReLU？现在很多开源大模型的 FFN 又用了 SwiGLU，它和 Swish 是什么关系？

**Q14.**（工程实践）激活函数和权重初始化之间有什么关系？为什么 ReLU 配 He 初始化、tanh 配 Xavier 初始化？

**Q15.**（追问型）softmax 有哪些数值问题？二分类时 softmax 和 sigmoid 是什么关系？温度（temperature）参数起什么作用？

---

## 五、参考答案与解析

### Q1 — 答案：B

`2σ(2x) − 1 = 2/(1+e^(−2x)) − 1 = (1 − e^(−2x))/(1 + e^(−2x)) = (e^x − e^(−x))/(e^x + e^(−x)) = tanh(x)`。所以 tanh 就是"拉伸并平移到以 0 为中心"的 sigmoid：值域从 (0,1) 变成 (−1,1)，`x=0` 处导数从 0.25 变成 1（讲义说的"四倍"）。代码 STEP 1 中 `x=1.0` 时 `sigmoid=0.7311`、`tanh=0.7616`，可以验证 `2σ(2) − 1 = 2×0.8808 − 1 ≈ 0.7616`。

### Q2 — 答案：C

死神经元的本质是：对**所有**训练样本，`w·x + b ≤ 0`，于是输出恒为 0、梯度恒为 0，再也不会被更新。最常见的诱因是一次过大的梯度更新把 bias 推到很负（或权重方向变得与所有输入"背对"），这就是讲义说的"large negative biases"。A、B 都是**预防**死神经元的做法；D 与死神经元无直接关系（Adam 的自适应步长有时反而会放大这个问题，但不是"最容易导致"的原因）。

### Q3 — 答案：C

GELU 在负半轴先下降后回升，在 x ≈ −0.75 附近取到最小值约 −0.17（实测 −0.1700），然后随 x → −∞ 趋近 0——所以它**非单调**（A 错），输出可以为负（B 错）。D 错：负半轴导数不恒为 0，例如 `gelu_derivative(-3) ≈ −0.012`。但也要注意，x 很负时导数确实非常接近 0（`gelu_derivative(-5) ≈ −7e−6`），所以讲义说 GELU "完全避免了死神经元问题"有些夸大：`gradient_scan` 中 GELU 在 [−5, −3.1] 上都被统计为 near-zero（20% dead zone）。

### Q4 — 答案：B

`softmax(x + c) = softmax(x)`：分子分母同乘 `e^c`，相互抵消。减去最大值后所有指数的参数都 ≤ 0，`exp` 的结果在 (0, 1] 之间，不可能上溢；最大项恰好是 `e^0 = 1`，分母至少为 1，也不会出现除以 0。代码输出 `softmax([10, 10, 10]) = [0.333..., 0.333..., 0.333...]` 也体现了平移不变性：三个相等的 logit 无论多大都是均匀分布。

### Q5 — 答案：B

多标签分类中，各类别**不互斥**，"是否有猫"和"是否有狗"是独立的二分类问题，所以每个 logit 各自过 sigmoid，配合二元交叉熵（BCE）。softmax（A）强制所有类别概率之和为 1，隐含"只能属于一个类"的假设，适用于**多类单标签**。ReLU、tanh 的输出都不是概率。

### Q6 — 答案：B

`gradient_scan` 只数 `|g| < 0.01` 的点。sigmoid 导数只在 |x| > 4.6 左右才小于 0.01，所以"死区"只有 9%；tanh 导数在 |x| > 3 后就小于 0.01，所以有 41%。但梯度消失看的是**多层连乘**：sigmoid 每层最多乘 0.25，tanh 在 0 附近可以接近 1。用一个 10 层、宽 64 的网络（tanh 和 sigmoid 都用 Xavier 风格初始化）实测，第 1 层与第 10 层梯度范数之比：sigmoid 约 1.7e−6，tanh 约 0.25（见 Q8）。这道题说明：**选一个合适的度量**和读懂度量的局限同样重要。另外 Leaky ReLU 的 0% 也只是因为负区间导数恰好是 `0.01`，而判断条件是 `< 0.01`——若把 α 设成 0.009，它会立刻变成 51%。

### Q7 — 答案：B

对下一层某个神经元，`∂L/∂wᵢ = δ · hᵢ`，其中 `δ` 是该神经元的误差信号（对所有 i 相同）。sigmoid 使得所有 `hᵢ > 0`，于是所有 `∂L/∂wᵢ` 与 `δ` 同号：这一步要么全部增大、要么全部减小。如果最优方向需要"一部分增大、一部分减小"，就只能分多步"之"字形逼近。以 0 为中心的 tanh（以及配合归一化层）可以缓解这个问题。A 错：sigmoid 导数恒为正。

### Q8 — 参考答案

(a) 这个实验测的是**前向激活值的绝对值**，而不是反向传播的梯度；而且它的设置让结果主要取决于"权重尺度"和"激活函数的值域"，而非梯度流动：
- 每一"层"只有一个神经元：`z = Σ wᵢ·v`（因为 `values = [activated] * n_inputs`，5 个输入其实是同一个数），即 `z = v·Σwᵢ`，`Σwᵢ ~ N(0, 5)`。
- **sigmoid**：不管 z 是多少，输出都在 (0,1)，而且 z 小时约等于 0.5，所以"magnitude"永远在 0.5 附近；这反映的是 sigmoid 的值域，不说明梯度没消失。
- **ReLU**：只要某一层 `z ≤ 0`，输出就是 0，此后 `z = 0·Σw = 0`，永远是 0——这是一条"死链"。而且第 1 层的输入本身很小（0.02），每层乘一个随机系数，也会快速衰减。
- **GELU**：小输入时 `gelu(x) ≈ x/2`，加上随机符号和缩放，同样迅速衰减到 0。

所以这个实验既没测梯度，也没用合理的初始化，它的输出与讲义"sigmoid 梯度消失、ReLU 保持梯度"的结论**并不矛盾，而是根本没在测这件事**。（这是源代码设计上的一个问题。）

(b) 一个合理的实验：多层、每层多个神经元、按激活函数选择初始化尺度，做一次真正的反向传播，比较第一层和最后一层的梯度范数：

```python
import numpy as np

def sigmoid(z):
    return 1 / (1 + np.exp(-z))

ACTS = {
    "sigmoid": (sigmoid, lambda z: sigmoid(z) * (1 - sigmoid(z)), 1.0),  # Xavier 风格
    "tanh":    (np.tanh, lambda z: 1 - np.tanh(z) ** 2,          1.0),  # Xavier 风格
    "relu":    (lambda z: np.maximum(0, z), lambda z: (z > 0) * 1.0, 2.0),  # He
}

def grad_ratio(name, depth=10, width=64, batch=256, seed=0):
    f, df, gain = ACTS[name]
    rng = np.random.default_rng(seed)
    h = rng.standard_normal((batch, width))
    Ws = [rng.standard_normal((width, width)) * np.sqrt(gain / width) for _ in range(depth)]
    zs = []
    for W in Ws:                      # 前向，保存每层 z
        z = h @ W
        zs.append(z)
        h = f(z)
    g = np.ones_like(h) / h.size      # 令 L = mean(h_last)
    norms = []
    for W, z in zip(reversed(Ws), reversed(zs)):   # 反向
        gz = g * df(z)                # dL/dz = dL/dh ⊙ f'(z)
        norms.append(np.linalg.norm(gz))
        g = gz @ W.T                  # dL/dh_prev
    return norms[-1] / norms[0]       # 第 1 层 / 第 10 层

for name in ACTS:
    print(f"{name:8s} layer1/layer10 grad norm = {grad_ratio(name):.2e}")
```

实测输出：

```text
sigmoid  layer1/layer10 grad norm = 1.68e-06
tanh     layer1/layer10 grad norm = 2.45e-01
relu     layer1/layer10 grad norm = 1.92e+00
```

结论：sigmoid 的梯度经过 10 层后缩小到约百万分之一；tanh 只衰减到约 1/4；ReLU（配 He 初始化）基本保持量级。这才是讲义想展示的现象。

### Q9 — 参考答案

(a) `gelu` 用的是 **tanh 近似**公式，而 `gelu_derivative` 返回的是**精确 GELU**（`x·Φ(x)`）的导数 `Φ(x) + x·φ(x)`。前向和反向用的不是同一个函数。在 [−5, 5] 上用中心差分比较，最大误差约 8.7e−4（出现在 x ≈ 2 附近）。对本节的小实验影响很小，但在梯度检查时会被判为"不一致"，原则上前向、反向必须对应同一个函数。（PyTorch 中 `F.gelu(x)` 默认是精确版，`F.gelu(x, approximate="tanh")` 才是近似版，两者的反向分别对应。）

(b)

```python
import math

def gelu_tanh_derivative(x):
    c = math.sqrt(2 / math.pi)
    u = c * (x + 0.044715 * x ** 3)
    t = math.tanh(u)
    return 0.5 * (1 + t) + 0.5 * x * (1 - t * t) * c * (1 + 3 * 0.044715 * x * x)

def max_err(deriv, h=1e-6):
    xs = [-5 + i * 0.01 for i in range(1001)]
    return max(abs((gelu(x + h) - gelu(x - h)) / (2 * h) - deriv(x)) for x in xs)

print(f"original gelu_derivative : {max_err(gelu_derivative):.1e}")
print(f"gelu_tanh_derivative     : {max_err(gelu_tanh_derivative):.1e}")
```

实测输出：

```text
original gelu_derivative : 8.7e-04
gelu_tanh_derivative     : 7.5e-10
```

推导：`gelu(x) = 0.5·x·(1 + tanh(u))`，`u = c(x + 0.044715x³)`。乘积法则：`0.5(1 + tanh u) + 0.5x · (1 − tanh²u) · du/dx`，其中 `du/dx = c(1 + 3·0.044715x²)`。

### Q10 — 参考答案

(a) 检测器的设置是：权重、偏置、输入都服从 N(0,1)，**没有训练**。对每个神经元，`z = w·x + b` 是均值为 `b`、标准差约 `‖w‖`（约 2.2）的正态变量，1000 个样本里几乎一定有正数，所以每个神经元都会激活。讲义说的 10%–40% 指的是**训练过程中**（尤其学习率大时）神经元被梯度更新"推死"，不是初始化时就死。

(b) 把 bias 那一行改成整体负偏移：

```python
    biases = [random.gauss(0, 1) - 5 for _ in range(hidden_size)]
```

现象：死神经元和"几乎不激活"（<5%）的神经元大量出现。实测在同样的随机种子下，偏移 −3 时 20 个神经元中 2 个死亡、4 个很弱；偏移 −5 时 2 个死亡、14 个很弱；偏移 −8 时 12 个死亡。被"推死"的神经元在整个输入分布上都不再激活，梯度恒为 0，靠自身永远无法恢复——这就是为什么要防止过大的学习率，或者改用 Leaky ReLU / GELU 给负区间留一点梯度。

### Q11 — 参考回答要点

| 激活 | 公式 | 导数范围 | 优点 | 缺点 | 典型场景 |
|------|------|---------|------|------|---------|
| sigmoid | `1/(1+e^(−x))` | (0, 0.25] | 输出像概率 | 饱和、梯度消失、非零中心、`exp` 开销 | 二分类输出层、门控（LSTM 门） |
| tanh | `(e^x−e^(−x))/(e^x+e^(−x))` | (0, 1] | 零中心 | 两端仍饱和 | RNN / LSTM 隐藏状态 |
| ReLU | `max(0,x)` | {0, 1} | 计算极快、正区间不衰减、稀疏激活 | 死神经元、非零中心、x=0 不可导 | CNN、普通 MLP 的默认 |
| GELU | `x·Φ(x)` | 约 [−0.13, 1.13] | 平滑、负区间有小梯度、在 Transformer 上效果好 | 计算稍贵 | Transformer（BERT、GPT） |

- 回答结构：先说"为什么要非线性"，再按"饱和 → 不饱和 → 平滑"的演进讲。
- 加分点：ReLU 的稀疏性（约一半神经元输出 0）有正则化效果；`x=0` 处框架约定导数取 0；输出层激活要和损失函数配对（sigmoid + BCE、softmax + CE），框架里通常直接用带 logits 的损失。

### Q12 — 参考回答要点

- 定义：ReLU 神经元对整个数据分布都满足 `w·x + b ≤ 0`，输出恒为 0，梯度恒为 0，永远不再更新。
- 成因：学习率过大导致一次更新把 bias 推到很负；初始化不当（bias 过负、权重过大）；输入分布漂移。
- 检测：统计每个神经元在一批数据上的激活率（就是本节 `dead_neuron_detector` 的做法），激活率为 0 的比例持续上升就要警惕；监控每层激活为 0 的比例、梯度为 0 的比例。
- 缓解：
  - 降低学习率、用 warmup、梯度裁剪；
  - He 初始化、bias 初始化为 0 或小正数；
  - BatchNorm / LayerNorm 让 pre-activation 分布稳定在 0 附近；
  - 换 Leaky ReLU / PReLU / ELU / GELU，让负区间也有梯度。
- 常见误区：以为"死神经元越少越好"——ReLU 本来就让很多神经元在**单个样本**上输出 0（稀疏性），这是正常的；只有在**所有样本**上都不激活才算死。

### Q13 — 参考回答要点

- GELU 的优势（讲义观点）：处处平滑，负区间允许小的负输出和非零梯度，可以理解为"按输入为正的概率对输入加权"的软门控；在 Transformer 的实验中比 ReLU 效果更好，因此成为 BERT、GPT 等模型的默认选择。
- 需要客观看待：这些优势主要是**经验结论**，GELU 与 ReLU 的差距通常不大；计算上 GELU 比 ReLU 贵一些（可用 tanh 近似或融合算子加速）。
- SwiGLU：属于"门控线性单元（GLU）"家族，FFN 写成 `(Swish(xW) ⊙ xV)·W2`，即用 Swish 激活的一支去"门控"另一支线性投影。Swish（SiLU）就是本节的 `x·σ(x)`。LLaMA 等开源大模型的 FFN 采用了 SwiGLU；为了保持参数量不变，通常把隐藏层维度缩小到约 2/3。
- 加分点：说出"FFN 中的激活函数选择对模型质量有可测量但不大的影响，而对推理成本（算子是否能融合、是否需要额外矩阵）有实际影响"。

### Q14 — 参考回答要点

- 目标：让每层输出的方差（前向）和梯度的方差（反向）在层与层之间大致保持不变，既不消失也不爆炸。
- Xavier（Glorot）：`Var(W) = 2/(n_in + n_out)`（或 `1/n_in`），推导假设激活在 0 附近近似线性且以 0 为中心——适合 tanh（以及 sigmoid 的中心区域）。
- He（Kaiming）：`Var(W) = 2/n_in`。ReLU 把一半的输入置零，输出方差约减半，所以要乘 2 补回来。
- 本节的 Q8 实验正是这个思想：ReLU 用 `gain = 2`、tanh / sigmoid 用 `gain = 1`。若 ReLU 也只用 `gain = 1`，信号的方差每层大约减半，10 层后也会显著衰减。
- 加分点：归一化层（BatchNorm、LayerNorm）和残差连接降低了对初始化的敏感性；本节 `ActivationNetwork` 用固定的 `gauss(0, 0.5)` 对浅层网络够用，深层网络就不行了（第 08 节展开）。

### Q15 — 参考回答要点

- 数值问题：
  - 上溢：`exp(1000)` 溢出 → 减去最大值；
  - 下溢 + 取对数：概率很小时 `log(softmax)` 变成 `log(0) = −inf` → 用 `log_softmax`（`x − max − log Σ exp(x − max)`，即 log-sum-exp 技巧），并且用框架提供的"softmax + 交叉熵"融合损失（如 `F.cross_entropy` 直接吃 logits）。
- 与 sigmoid 的关系：两类时 `softmax([z1, z2])₁ = e^(z1)/(e^(z1)+e^(z2)) = σ(z1 − z2)`。所以二分类既可以用 1 个 logit + sigmoid，也可以用 2 个 logits + softmax，二者等价。
- 温度：`softmax(z / T)`。T < 1 分布更尖锐（更接近 argmax），T > 1 更平滑（更均匀）；T → 0 退化为 one-hot，T → ∞ 趋于均匀分布。应用：LLM 采样控制随机性、知识蒸馏中软化教师分布、对比学习中的温度超参数。
- 加分点：softmax 不改变 logits 的排序，所以只要 argmax 时可以直接比较 logits；softmax 的雅可比矩阵 `diag(p) − ppᵀ`，与交叉熵结合后梯度简化为 `p − y`（下一节）。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 02 多层网络和 Forward Pass](../../02-multi-layer-networks/docs/zh.md)：线性层叠加仍是线性，激活函数为什么必不可少。
- [阶段 03 · 03 Backpropagation 从头开始](../../03-backpropagation/docs/zh.md)：激活函数的导数在反向传播中逐层相乘，这是梯度消失的根源。
- [阶段 01 · 06 概率与分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：GELU 中的标准正态 CDF Φ(x)。

### 本节被哪些后续内容用到
- [阶段 03 · 05 Loss Functions](../../05-loss-functions/docs/zh.md)：输出层激活与损失的配对（sigmoid + BCE、softmax + CE）。
- [阶段 03 · 08 Weight 初始化和训练稳定性](../../08-weight-initialization/docs/zh.md)：Xavier / He 初始化如何与激活函数配合。
- [阶段 03 · 13 调试神经网络](../../13-debugging-neural-networks/docs/zh.md)：监控死神经元、饱和与梯度范数。
- [阶段 05 · 08 CNN 和 RNN 处理文本](../../../05-nlp-foundations-to-advanced/08-cnns-rnns-for-text/docs/zh.md)：RNN / LSTM 中 tanh 与 sigmoid 门的用法。
- [阶段 07 · 05 完整 Transformer](../../../07-transformers-deep-dive/05-full-transformer/docs/zh.md)：FFN 子层中的 GELU。
- [阶段 10 · 14 开源模型架构解读](../../../10-llms-from-scratch/14-open-models-architecture-walkthroughs/docs/zh.md)：现代开源大模型中的 SwiGLU 等 FFN 激活选择。

### 延伸关键词
`饱和（saturation）` · `zero-centered` · `dead ReLU` · `PReLU / ELU / SELU` · `GLU / SwiGLU / GeGLU` · `log-sum-exp` · `softmax temperature` · `Xavier / He 初始化`
