# 测验 · 优化（Optimization）

> **阶段 01 · 数学基础 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/optimizers.py](../code/optimizers.py) ｜ 代码讲解：[code/optimizers.讲解.md](../code/optimizers.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 训练 = 优化 | 找到让损失 `L(w)` 最小的权重 `w`；梯度指向损失**上升**最快的方向，所以要沿负梯度走 |
| 2 | 梯度下降与学习率 | `w = w - lr·∇L`；lr 太大越过谷底甚至发散，太小则爬得极慢；没有公式，只能实验 |
| 3 | Batch / SGD / Mini-batch | 全量梯度精确但慢；单样本噪声大但快；mini-batch（32–256）折中，是实际默认；噪声有助于逃离鞍点和浅局部极小 |
| 4 | Momentum | `v = β·v + g; w = w - lr·v`；在一致方向上加速、在来回震荡方向上抵消；稳态下等效学习率约为 `lr/(1-β)` |
| 5 | Adam | 一阶矩 `m`（梯度的滑动平均）+ 二阶矩 `v`（梯度平方的滑动平均），除以 `√v̂` 给每个参数自适应步长；默认 `lr=1e-3, β1=0.9, β2=0.999, ε=1e-8` |
| 6 | 偏差修正 | `m、v` 从 0 初始化，早期偏向 0；除以 `1-βᵗ` 修正冷启动 |
| 7 | 学习率调度 | Step / 指数衰减 / 余弦退火 / Warmup+衰减；早期大步、后期小步；长训练一定要用 |
| 8 | 凸 vs 非凸、鞍点 | 凸函数任何局部极小都是全局极小；神经网络损失非凸，高维下真正的障碍是**鞍点**而非局部极小 |
| 9 | Rosenbrock 函数 | `f = (1-x)² + 100(y-x²)²`，最小值在 (1,1)，弯曲狭长的山谷，是检验优化器的经典基准 |

### 核心技能（能动手做到）

- [ ] 手推 Rosenbrock 的梯度 `∂f/∂x = -2(1-x) - 400x(y-x²)`、`∂f/∂y = 200(y-x²)`，并用数值差分验证
- [ ] 不用框架，从零实现 `GradientDescent`、`SGDMomentum`、`Adam` 三个类（统一 `step(params, grads)` 接口），在 Rosenbrock 上复现"Adam 约 767 步把 loss 降到 1e-4 以下，GD 5000 步仍未到"
- [ ] 做一次学习率扫描，找出 GD 在 Rosenbrock 上发散的临界区间（0.002 收敛良好、0.005 在 7 步内发散）
- [ ] 解释 `SGDMomentum(lr=1e-4, β=0.9)` 与 `GradientDescent(lr=1e-3)` 结果几乎相同的原因
- [ ] 实现指数衰减与"warmup + 余弦退火"调度，并观察它对 Adam 后期 loss 尖峰的影响
- [ ] 在鞍点 `f = x² - y²` 上对比三种优化器，说明为什么从 `y=0` 精确出发时谁都逃不出去

---

## 二、基础自测（选择题）

**Q1.** 动量更新 `v = β·v + g`、`w = w - lr·v`。若梯度长期保持常数 `g`，β=0.9，稳态时 `v` 约为：

- A. `g`
- B. `0.9g`
- C. `10g`
- D. `0.1g`

**Q2.** Adam 中引入偏差修正 `m̂ = m / (1 - β1ᵗ)` 的主要原因是：

- A. 防止梯度爆炸
- B. `m、v` 初始化为 0，训练早期的估计系统性偏小，需要放大还原
- C. 让学习率随时间自动衰减
- D. 让 Adam 在凸问题上保证收敛到全局最优

**Q3.** 用本节代码 `Adam(lr=0.01)` 在 Rosenbrock 上从 `(-1, 1)` 出发，此处梯度为 `(-4, 0)`。第一步之后参数约为：

- A. `(-0.96, 1.0)`
- B. `(-0.99, 1.0)`
- C. `(-0.9996, 1.0)`
- D. `(-0.99, 0.99)`

**Q4.** 关于鞍点，下列说法正确的是：

- A. 鞍点处梯度不为零，只是很小
- B. 鞍点处梯度为零，Hessian 同时有正特征值和负特征值
- C. 鞍点是局部极小值的一种，只是不够深
- D. 高维非凸函数中，鞍点比局部极小值少得多

**Q5.** 余弦退火 `lr = lr_min + 0.5·(lr_max - lr_min)·(1 + cos(π·t/T))`，在训练进行到一半（`t = T/2`）时，学习率等于：

- A. `lr_max`
- B. `lr_min`
- C. `(lr_max + lr_min) / 2`
- D. `0.5·lr_max`

**Q6.** 关于 batch GD、SGD、mini-batch，下列说法**错误**的是：

- A. Mini-batch 梯度是全量梯度的无偏估计，batch 越大方差越小
- B. SGD 每步只看一个样本，单步很快但梯度噪声大
- C. Mini-batch 的梯度噪声只会拖慢训练，没有任何好处
- D. 实际训练中说的"SGD"几乎都是指 mini-batch SGD

**Q7.** 关于凸函数与梯度下降，最准确的是：

- A. 凸函数一定恰好有一个极小值点
- B. 凸函数的任何局部极小都是全局极小；在合适的学习率下梯度下降能收敛到它
- C. 神经网络的损失函数通常是凸的
- D. 只要是凸函数，任何学习率下梯度下降都会收敛

---

## 三、动手 / 代码题

**Q8.** 运行 `optimizers.py`，`demo_momentum_effect` 和 `demo_learning_rate_effect` 打印了下面几行（摘录）：

```text
# LEARNING RATE EFFECT ON GRADIENT DESCENT
    0.0001   -0.446368    0.206459      2.09718513  slow
    0.0010    0.939826    0.883023      0.00362714  converged

# MOMENTUM EFFECT ON SGD   (lr=0.0001)
    0.00   -0.446368    0.206459      2.09718513
    0.90    0.940412    0.884127      0.00355685
```

(a) 为什么 `β=0.00` 那一行和 `GD lr=0.0001` 那一行**逐位完全相同**？(b) 为什么 `lr=0.0001, β=0.9` 的结果和 `GD lr=0.001` 几乎一样？请从代码的更新公式出发解释。

**Q9.** 阅读 `demo_saddle_point`：

```python
    start = [0.01, 0.01]
    steps = 200
    # ...
        escaped = abs(final[1]) > 1.0
```

GD（lr=0.01）的输出是 `0.000176    0.524849   -0.275466  no`。(a) 手算验证 `x、y` 这两个数；(b) GD 真的"没有逃离"鞍点吗？至少要多少步才会被判定为 escaped？(c) 如果把起点改成 `[0.01, 0.0]`，三种优化器的结果会怎样？这说明了什么？

**Q10.**（找 bug）一位同学把 `Adam.step` 改成了下面这样，运行 `optimize(Adam(lr=0.01), rosenbrock, rosenbrock_gradient, [-1.0, 1.0])` 时程序直接崩溃。指出问题并修复；顺带说明为什么 `optimize` 里的 `try/except` 没能兜住它。

```python
    def step(self, params, grads):
        if self.m is None:
            self.m = [0.0] * len(params)
            self.v = [0.0] * len(params)

        self.m = [self.beta1 * m + (1 - self.beta1) * g for m, g in zip(self.m, grads)]
        self.v = [self.beta2 * v + (1 - self.beta2) * g ** 2 for v, g in zip(self.v, grads)]

        m_hat = [m / (1 - self.beta1 ** self.t) for m in self.m]
        v_hat = [v / (1 - self.beta2 ** self.t) for v in self.v]
        self.t += 1

        return [p - self.lr * mh / (vh ** 0.5 + self.epsilon)
                for p, mh, vh in zip(params, m_hat, v_hat)]
```

**Q11.**（扩展）讲义练习 4 要求给 GD 加指数衰减 `lr = lr_0 · 0.999^step`。请：(a) 写一个继承 `GradientDescent` 的 `GDExpDecay` 类；(b) 再写一个 `cosine_with_warmup(step, total, lr_max, lr_min=0.0, warmup=0)` 函数，并让 Adam 使用它；(c) 预测并解释：在 Rosenbrock 上 `lr_0=0.0005` 加衰减后，5000 步的结果比不加衰减更好还是更差？

---

## 四、面试高频题

**Q12.**（基础必考）请对比 SGD、SGD+Momentum、Adam 的更新公式与适用场景。为什么很多 CV 任务最终精度上 SGD+Momentum 仍有优势，而 Transformer / LLM 训练几乎都用 Adam 系列？

**Q13.**（原理深挖）推导 Adam 的偏差修正：为什么是除以 `1 - β1ᵗ`？`β2 = 0.999` 时如果不做修正，训练前几步会发生什么？

**Q14.**（原理深挖）为什么说高维神经网络训练中"鞍点比局部极小更麻烦"？SGD 的噪声和 Momentum 分别如何帮助逃离鞍点？"平坦极小值泛化更好"又是什么意思？

**Q15.**（工程实践）大模型预训练为什么几乎都用"线性 warmup + 余弦衰减"？warmup 解决的是什么问题？如果训练中途出现 loss spike 或 NaN，你会按什么顺序排查？

**Q16.**（追问型）Adam 加 L2 正则与 AdamW 有什么区别？为什么说 AdamW 的权重衰减是"解耦"的？训练 Transformer 时为什么推荐 AdamW？

---

## 五、参考答案与解析

### Q1 — 答案：C

稳态时 `v = β·v + g` ⇒ `v(1-β) = g` ⇒ `v = g/(1-β) = 10g`。所以 β=0.9 的动量在一致方向上把有效步长放大约 10 倍——这就是"小球越滚越快"。在来回震荡的方向上，正负梯度相互抵消，`v` 保持很小。这也解释了为什么用动量时 lr 通常要比纯 GD 小。

### Q2 — 答案：B

`m₀ = 0`，第一步 `m₁ = (1-β1)·g = 0.1g`，严重偏小；`v₁ = (1-β2)·g² = 0.001g²` 偏小得更厉害。除以 `1-β1ᵗ` 后 `m̂₁ = g`、`v̂₁ = g²`，恢复为无偏估计。随着 t 增大，`βᵗ → 0`，修正项趋于 1，自动失效。它与梯度爆炸（A）、学习率衰减（C）、收敛性保证（D）都无关。

### Q3 — 答案：B

`t=1` 时偏差修正后 `m̂ = g`、`v̂ = g²`，于是步长 `lr·g/(|g|+ε) ≈ lr·sign(g)`。x 方向 `g=-4`，所以 `x = -1 - 0.01·(-1) = -0.99`；y 方向 `g=0`，`0/(0+1e-8) = 0`，y 不变。实际运行 `Adam(lr=0.01).step([-1.0, 1.0], [-4.0, 0.0])` 得到 `[-0.990000000025, 1.0]`（那一点点差别来自 ε）。A 是 `GD(lr=0.01)` 的结果 `-1 - 0.01·(-4) = -0.96`。这道题说明：**Adam 的单步位移量级约为 lr，与梯度大小基本无关**。

### Q4 — 答案：B

鞍点是梯度为零的驻点，但在某些方向是极小、某些方向是极大，即 Hessian 特征值有正有负。`f = x² - y²` 在原点的 Hessian 是 `diag(2, -2)`。D 说反了：高维空间中，要让所有方向都向上弯（局部极小）需要所有特征值都为正，这在随机的高维函数中概率很低，所以鞍点远比局部极小多。

### Q5 — 答案：C

`cos(π/2) = 0`，所以 `lr = lr_min + 0.5·(lr_max - lr_min) = (lr_max + lr_min)/2`。t=0 时为 `lr_max`（A），t=T 时为 `lr_min`（B）。D 只在 `lr_min = 0` 时成立。

### Q6 — 答案：C

讲义明确指出："The noise in SGD and mini-batch is not a bug. It helps escape shallow local minima and saddle points." 噪声带来随机扰动，帮助逃离鞍点和尖锐极小。A 正确：随机采样的 mini-batch 梯度期望等于全量梯度，方差约按 `1/B` 下降。

### Q7 — 答案：B

凸函数的关键性质是"局部极小即全局极小"。A 错：凸函数可能没有极小值（如 `eˣ`），也可能有一整片极小值（如常数函数）。D 错：即使是 `f = x²`，学习率过大（lr > 1）时 GD 也会发散。讲义里"Gradient descent always finds it"隐含了"学习率合适"的前提。

### Q8 — 参考答案

(a) 当 `momentum = 0` 时，`SGDMomentum.step` 中 `velocity = 0·v + g = g`，更新就是 `p - lr·g`，与 `GradientDescent.step` 的 `p - self.lr * g` 是**同一组浮点运算**（`0.0 * v` 精确为 0，`0.0 + g` 精确为 g），所以每一步结果逐位相同。

(b) 由 Q1，梯度方向稳定时 `v ≈ g/(1-β) = 10g`，所以 `lr·v ≈ 0.0001 × 10g = 0.001g`——**有效学习率约为 `lr/(1-β) = 0.001`**。Rosenbrock 山谷底部的梯度变化缓慢，正好满足"梯度方向基本一致"的条件，于是两者轨迹几乎重合（0.940412 vs 0.939826）。不完全相同是因为动量有"惯性"，需要大约 `1/(1-β) = 10` 步才能跟上梯度的变化。

延伸：`β=0.99` 等效于 lr ≈ 0.01，而 GD 在 lr=0.005 时就发散了，但动量版本却收敛到 `(1.000000, 1.000000)`。原因是动量对历史梯度做了平均，在陡峭方向上的来回震荡被抵消，因此可以承受更大的等效步长——这正是动量的价值。

### Q9 — 参考答案

(a) `f = x² - y²` 的梯度是 `(2x, -2y)`，GD 更新：
- `x ← x - 0.01·2x = 0.98x`，200 步后 `0.01 × 0.98²⁰⁰ ≈ 0.01 × 0.0176 = 0.000176`；
- `y ← y + 0.01·2y = 1.02y`，200 步后 `0.01 × 1.02²⁰⁰ ≈ 0.01 × 52.48 = 0.5248`。
- `f = 0.000176² - 0.5248² ≈ -0.2755`。

(b) GD **已经在逃离**——y 以每步 2% 的速度指数增长，只是 200 步还不够跨过 `|y| > 1` 这个人为阈值。需要 `1.02ⁿ > 100`，即 `n > ln100/ln1.02 ≈ 232.6`，**第 233 步**之后才会判定为 escaped。所以这个 demo 展示的是"GD 逃得慢"，而不是"GD 逃不掉"。SGD+Momentum（有效 lr 约 10 倍）和 Adam（步长约为 lr，与梯度大小无关）逃得快得多。

(c) 起点 `[0.01, 0.0]` 时，y 方向梯度 `-2y` 恒为 0：GD、Momentum 的 y 更新恒为 0；Adam 的 `m̂_y = 0`，步长 `0/(0+ε) = 0`。**三者都永远停在 `y = 0`**，x 则收敛到 0，最终停在鞍点上（实测分别为 `x≈1.8e-4、-2.1e-8、-2.0e-7`，y 都是 `0.0`）。这说明确定性的一阶方法无法从"精确位于鞍点稳定流形上"的位置逃出，需要**扰动**：mini-batch 噪声、随机初始化，或者显式加噪声（perturbed GD）。这正是讲义说"噪声不是 bug"的原因。

### Q10 — 参考答案

问题：`self.t` 在计算 `m_hat` **之后**才自增。第一步时 `self.t = 0`，`1 - self.beta1 ** 0 = 1 - 1 = 0`，`m / 0` 抛出 `ZeroDivisionError: float division by zero`。

修复：把 `self.t += 1` 移回到计算 `m、v` 之前（与原代码一致），保证第一步 `t = 1`：

```python
    def step(self, params, grads):
        if self.m is None:
            self.m = [0.0] * len(params)
            self.v = [0.0] * len(params)

        self.t += 1                      # 先自增，t 从 1 开始

        self.m = [self.beta1 * m + (1 - self.beta1) * g for m, g in zip(self.m, grads)]
        self.v = [self.beta2 * v + (1 - self.beta2) * g ** 2 for v, g in zip(self.v, grads)]

        m_hat = [m / (1 - self.beta1 ** self.t) for m in self.m]
        v_hat = [v / (1 - self.beta2 ** self.t) for v in self.v]

        return [p - self.lr * mh / (vh ** 0.5 + self.epsilon)
                for p, mh, vh in zip(params, m_hat, v_hat)]
```

为什么 `try/except` 没兜住：`optimize` 只捕获 `except (OverflowError, ValueError)`，而 `ZeroDivisionError` 是 `ArithmeticError` 的子类，与这两者是**兄弟关系**而非父子关系，因此异常继续向上抛出，程序崩溃。这也提醒我们：`try/except` 只应捕获你预期的异常，正好可以让这种真正的 bug 暴露出来。

### Q11 — 参考答案

```python
import math
from optimizers import GradientDescent, Adam, optimize, rosenbrock, rosenbrock_gradient


class GDExpDecay(GradientDescent):
    def __init__(self, lr=0.001, decay=0.999):
        super().__init__(lr)
        self.lr0 = lr
        self.decay = decay
        self.t = 0

    def step(self, params, grads):
        self.lr = self.lr0 * self.decay ** self.t   # 先算本步学习率
        self.t += 1
        return super().step(params, grads)          # 复用父类的更新公式


def cosine_with_warmup(step, total, lr_max, lr_min=0.0, warmup=0):
    if step < warmup:                                   # 线性 warmup
        return lr_max * (step + 1) / warmup
    progress = (step - warmup) / max(1, total - warmup)  # 0 → 1
    return lr_min + 0.5 * (lr_max - lr_min) * (1 + math.cos(math.pi * progress))


class AdamCosine(Adam):
    def __init__(self, lr_max, total, warmup=100, **kw):
        super().__init__(lr=lr_max, **kw)
        self.lr_max, self.total, self.warmup = lr_max, total, warmup

    def step(self, params, grads):
        self.lr = cosine_with_warmup(self.t, self.total, self.lr_max, 0.0, self.warmup)
        return super().step(params, grads)


for opt in [GradientDescent(0.0005), GDExpDecay(0.0005)]:
    h = optimize(opt, rosenbrock, rosenbrock_gradient, [-1.0, 1.0], 5000)
    print(type(opt).__name__, h[-1], rosenbrock(h[-1]))
```

(c) **更差**。实测：恒定 lr 时 loss = `0.0408`，加 `0.999^step` 衰减后 loss = `2.11`（几乎停在 `(-0.45, 0.21)`）。原因是"学习率预算"：`Σ 0.999ᵗ ≈ 1/(1-0.999) = 1000`，5000 步的总位移相当于恒定 lr 只走了约 1000 步；而在 Rosenbrock 上 GD 本来就"太慢"而不是"太震荡"，衰减只会让它更慢。即使 `lr_0=0.002`，衰减后 loss 也从 `5.6e-5` 变差到 `0.075`。

反过来，对 Adam 用"warmup 100 步 + 余弦衰减到 0"效果显著：恒定 lr 的 Adam 在收敛后 loss 会间歇性跳回 `1e-4 ~ 6e-3` 量级（第 2125 步 loss 跳回 `1.8e-4`，第 2000 步之后的最大值约 `6e-3`），因为 Adam 的步长约为 lr、不会随梯度变小而自动缩小；加上余弦衰减后第 2000 步之后的最大 loss 降到约 `6e-15`，最终 loss 约 `3e-30`。**结论：衰减调度要用在"步长过大导致无法稳定"的场景，而不是"本来就走不动"的场景。**

### Q12 — 参考回答要点

- 公式：
  - SGD：`w -= lr·g`
  - Momentum：`v = β·v + g; w -= lr·v`（PyTorch 写法，β 常取 0.9）
  - Adam：`m = β1·m + (1-β1)·g; v = β2·v + (1-β2)·g²`，偏差修正后 `w -= lr·m̂/(√v̂ + ε)`
- 特点：Momentum 在一致方向加速、在震荡方向抑制；Adam 在此基础上按每个参数的历史梯度幅度缩放步长，对超参数不敏感，开箱即用。
- 为什么 CV 中 SGD+M 常有更好的最终精度：讲义的解释是 SGD 的噪声使其不易停在尖锐极小（sharp minima），更容易落入泛化好的平坦极小；Adam 收敛快但可能泛化略差。代价是 SGD+M 需要更仔细地调 lr 与调度。
- 为什么 Transformer 用 Adam(W)：参数规模大、不同模块（embedding、attention、LayerNorm）梯度尺度差异巨大，稀疏更新的 embedding 需要自适应步长；SGD 在 Transformer 上很难调好、经常不收敛或很慢。
- 加分点：Adam 需要为每个参数额外存 `m、v` 两份状态，显存是参数的 2 倍（混合精度下通常用 fp32 存），这是 ZeRO、8-bit Adam、Adafactor 等优化的动机。

### Q13 — 参考回答要点

- 推导：`m_t = (1-β1)·Σᵢ₌₁ᵗ β1^(t-i)·gᵢ`。若梯度平稳 `E[gᵢ] = E[g]`，则 `E[m_t] = E[g]·(1-β1)·Σ β1^(t-i) = E[g]·(1 - β1ᵗ)`。所以 `m_t / (1-β1ᵗ)` 是 `E[g]` 的无偏估计。`v` 同理，修正因子为 `1 - β2ᵗ`。
- 不修正的后果：β2 = 0.999 时，`1 - β2ᵗ` 在前几百步都很小（t=1 时为 0.001，t=100 时约 0.095）。不修正的话 `v` 被严重低估，`√v` 很小，`m/√v` 偏大——尤其当 `β1` 的修正因子（t=1 时 0.1）与 `β2` 的修正因子（t=1 时 0.001）不一致时，第一步的有效步长约是 `lr × 0.1/√0.001 ≈ 3.16·lr`，早期更新过猛，可能直接把参数推到很差的区域。
- 加分点：偏差修正后，Adam 第一步的位移约为 `lr·sign(g)`（见 Q3），这正是"Adam 的 lr 近似于每步最大位移"这一直觉的来源；也说明 warmup 和偏差修正解决的是相关但不同的问题。

### Q14 — 参考回答要点

- 为什么鞍点更麻烦：驻点处 Hessian 有 n 个特征值，局部极小要求全部为正。高维随机函数中，"全部为正"的概率随维度指数下降，所以大多数驻点是鞍点；而且研究发现高维网络里的局部极小，其 loss 大多已接近全局最优（讲义："Most local minima have loss values close to the global minimum"）。鞍点附近梯度接近 0，优化会长时间停滞，看起来像"收敛"了。
- 如何逃离：
  - **SGD 噪声**：随机扰动让参数偏离鞍点的"稳定方向"，一旦在负曲率方向有分量，就会被指数放大（见 Q9 中 y 每步 ×1.02）。
  - **Momentum**：累积的速度让参数冲过平坦区域，并在一致的负曲率方向上加速。
  - **Adam**：按 `√v̂` 归一化后，即使梯度很小，步长也约为 lr，不会在平坦区"龟速"移动。
- 平坦极小 vs 尖锐极小：平坦极小附近 loss 对参数扰动不敏感，训练集与测试集分布的轻微差异不会导致 loss 大涨，因此泛化更好（Li et al. 2018 的 loss landscape 可视化）。大 batch 训练噪声小，更容易陷入尖锐极小，这是大 batch 需要配合 lr 缩放和 warmup 的原因之一。
- 常见误区：认为"局部极小是深度学习的主要障碍"；认为"梯度为 0 就是收敛到最优"。

### Q15 — 参考回答要点

- 为什么 warmup：训练初期参数是随机的，梯度方向不稳定、幅度可能很大；Adam 的二阶矩 `v` 在前几百步也还没估准。此时用大 lr 容易一步把参数推到很差的区域，造成 loss 发散或注意力 logits 爆炸。线性 warmup 让 lr 从很小开始逐步上升，给优化器状态和网络（如 LayerNorm 统计、注意力分布）"热身"的时间。
- 为什么余弦衰减：前期保持较大 lr 快速下降，后期平滑地降到很小，帮助在极小值附近稳定收敛（对比 Q11 中恒定 lr 的 Adam 后期反复出现 loss 尖峰）。相比 step decay 没有突变，超参数也少（只需总步数）。
- loss spike / NaN 的排查顺序：
  1. 确认数据：是否有异常 batch（超长样本、全是 padding、脏数据）。
  2. 看梯度范数曲线：spike 前梯度范数是否先暴涨 → 加 / 收紧**梯度裁剪**（如 `max_norm=1.0`）。
  3. 降低峰值 lr 或延长 warmup。
  4. 检查数值精度：fp16 溢出 → 使用 bf16 或 loss scaling；检查 softmax、log 等是否做了数值稳定处理。
  5. 检查 Adam 的 ε、β2（大模型常用 β2=0.95 以更快适应梯度变化）。
  6. 必要时从最近的 checkpoint 回滚并跳过问题数据。
- 加分点：本节代码中 `optimize` 检测到 NaN/Inf 或 `|g| > 1e15` 就提前 `break`，这是一个最朴素的"发散保护"；生产训练中对应的是 NaN 检测 + 自动回滚。

### Q16 — 参考回答要点

- Adam + L2：把 `λ·w` 加到梯度里，`g' = g + λ·w`，再走 Adam 的 `m/√v` 流程。问题是正则项也被 `√v̂` 除掉了：梯度历来很大的参数，`√v̂` 大，实际得到的衰减反而小；正则强度因参数而异，与"所有权重都向 0 收缩"的本意不符。
- AdamW（解耦权重衰减）：Adam 的自适应更新只用原始梯度 `g`，权重衰减单独作用在参数上：`w ← w - lr·(m̂/(√v̂+ε) + λ·w)`。衰减强度对所有参数一致，与梯度统计量"解耦"。
- 为什么 Transformer 推荐 AdamW：实践中泛化更好、正则强度更易调；超参数 `weight_decay`（如 0.01–0.1）与 lr 的耦合更弱。工程上通常**不对 bias 和 LayerNorm 参数做权重衰减**。
- 与本节的联系：讲义 Use It 部分给出了 `torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01)`，并建议 "Use AdamW for transformers"；结合第 07 节"L2 正则 = 高斯先验"，可以说 AdamW 才是真正意义上对每个参数施加相同强度的先验收缩。
- 常见误区：认为"在 Adam 里加 L2 和用 AdamW 是一回事"——对 SGD 而言二者等价，对自适应优化器不等价。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 04 机器学习微积分](../../04-calculus-for-ml/docs/zh.md)：导数、偏导、梯度的含义，用于推导 Rosenbrock 的梯度。
- [阶段 01 · 05 Chain Rule & 自动微分](../../05-chain-rule-and-autodiff/docs/zh.md)：神经网络中梯度从哪里来。

### 本节被哪些后续内容用到
- [阶段 01 · 13 数值稳定性](../../13-numerical-stability/docs/zh.md)：梯度爆炸 / NaN、ε 的作用、混合精度。
- [阶段 01 · 18 凸优化](../../18-convex-optimization/docs/zh.md)：凸性、收敛性理论的严格版本。
- [阶段 03 · 03 反向传播](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：为优化器提供梯度。
- [阶段 03 · 06 优化器](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：在真实神经网络上使用并扩展本节实现的优化器。
- [阶段 03 · 09 学习率调度](../../../03-deep-learning-core/09-learning-rate-schedules/docs/zh.md)：step、余弦、warmup 等调度的系统讲解。
- [阶段 03 · 10 迷你框架](../../../03-deep-learning-core/10-mini-framework/docs/zh.md)：把本节的优化器类集成进自己的小框架。
- [阶段 03 · 13 调试神经网络](../../../03-deep-learning-core/13-debugging-neural-networks/docs/zh.md)：loss 不降、发散时如何排查学习率与优化器问题。
- [阶段 10 · 04 预训练 Mini-GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：AdamW + warmup + 余弦在 LLM 预训练中的实战。
- [阶段 19 · 44 余弦学习率与 Warmup](../../../19-capstone-projects/44-cosine-lr-warmup/docs/zh.md)、[阶段 19 · 45 梯度裁剪与 AMP](../../../19-capstone-projects/45-gradient-clipping-amp/docs/zh.md)：训练稳定性的工程实现。

### 延伸关键词
`Nesterov 动量` · `RMSProp` · `AdaGrad` · `AdamW` · `Lion` · `Adafactor` · `8-bit Adam` · `梯度裁剪 (Gradient Clipping)` · `Hessian / 二阶方法` · `Sharpness-Aware Minimization (SAM)` · `学习率范围测试 (LR Range Test)` · `大 batch 训练与线性缩放规则`
