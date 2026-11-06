# 测验 · Backpropagation 从头开始（Backpropagation from Scratch）

> **阶段 03 · 深度学习核心 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要反向传播 | 数值差分每个参数要单独跑前向，P 个参数就要 ~P 次；反向传播一次前向 + 一次反向就得到全部梯度 |
| 2 | 链式法则 | `y = f(g(x)) ⇒ dy/dx = f'(g(x))·g'(x)`；同一条路径上局部导数相乘，多条路径的贡献相加 |
| 3 | 计算图 | 节点是运算，前向时值从左往右流，反向时梯度从右往左流；每个节点只做一件事：上游梯度 × 局部导数，再往下传 |
| 4 | 三种局部导数 | 加法：梯度原样分给两个输入；乘法：各自拿到"对方的值 × 上游梯度"；sigmoid：`s(1−s) × 上游梯度` |
| 5 | 梯度累加 `+=` | 一个值被多处使用时，梯度是所有路径之和；所以每次反向前必须 `zero_grad()` |
| 6 | 拓扑排序 | 反向遍历时保证一个节点的梯度已从所有下游累加完毕，才把它继续往下传 |
| 7 | 存激活换速度 | 前向要保存中间值（`data`、`s`）供反向使用：用内存换来"一次反向算完所有梯度"；训练比推理更耗显存 |
| 8 | 梯度消失 | `σ'(z) ≤ 0.25`，每过一层 sigmoid 梯度就再乘一个小于 0.25 的数；越靠近输入层梯度越小，深层 sigmoid 网络难训练 |
| 9 | 训练循环 | 前向 → 计算 loss → `zero_grad` → `backward` → `p.data -= lr * p.grad`；可以 full-batch（XOR）也可以逐样本在线 SGD（圆分类） |

### 核心技能（能动手做到）

- [ ] 从零实现 `Value` 类：`__add__`、`__mul__`、`sigmoid` 的 `_backward`，以及基于拓扑排序的 `backward()`
- [ ] 手推"线性 → sigmoid → 线性 → sigmoid → MSE"两层网络的全部梯度公式，并能写成矩阵形式
- [ ] 写一个中心差分的数值梯度检查函数，验证自己的 autograd 结果（相对误差应在 1e-7 量级以下）
- [ ] 用自己的引擎训练 XOR（full-batch）和圆分类（online SGD），说清两种训练循环的差别
- [ ] 构造一个 6 层 sigmoid 网络，打印每层权重的平均 `|grad|`，亲眼看到梯度消失
- [ ] 给 `Value` 扩展 `relu`、`__pow__` 等运算，并正确写出它们的局部导数
- [ ] 把手写训练循环一一对应到 PyTorch 的 `optimizer.zero_grad()` / `loss.backward()` / `optimizer.step()`

---

## 二、基础自测（选择题）

**Q1.** 一个网络有 P 个参数。用反向传播计算 loss 对全部 P 个参数的梯度，计算代价大约是：

- A. P 次前向传播
- B. 一次前向 + 一次反向，大约是一次前向传播的常数倍（通常 2～3 倍），这个倍数与 P 无关
- C. P² 次乘法
- D. log P 次前向传播

**Q2.** 计算图中有一个乘法节点 `out = a * b`，已知 `a.data = 3`、`b.data = -2`、`out.grad = 0.5`。执行该节点的 `_backward` 后，`a.grad` 和 `b.grad` 分别增加：

- A. `0.5` 和 `0.5`
- B. `-1.0` 和 `1.5`
- C. `1.5` 和 `-1.0`
- D. `-3.0` 和 `-3.0`

**Q3.** 用本节的 `Value` 计算：

```python
a = Value(2.0)
b = Value(-3.0)
c = a * b + a
c.backward()
```

`a.grad` 等于：

- A. `-3.0`
- B. `1.0`
- C. `-2.0`
- D. `2.0`

**Q4.** `backward()` 里先做拓扑排序再逆序调用 `_backward`，其根本原因是：

- A. 减少内存占用
- B. 保证每个节点在把梯度传给它的输入之前，已经从所有使用它的下游节点那里累加完了梯度
- C. 加速前向传播
- D. 让 Python 的递归深度更浅

**Q5.** 关于 sigmoid 网络中的梯度消失，下列说法正确的是：

- A. 只要学习率足够大就能彻底解决
- B. 它是反向传播算法本身的 bug
- C. 每经过一层 sigmoid，梯度都要乘上 `σ'(z) ≤ 0.25`，越靠近输入层的参数梯度往往越小
- D. 它只发生在输出层

**Q6.** 如果在 `train_xor` 的循环里删掉 `net.zero_grad()`，最可能发生的是：

- A. 没有影响，因为 `backward()` 会把梯度重置为 0
- B. 程序直接报错
- C. 每个 epoch 的梯度会叠加到之前所有 epoch 的梯度上，更新方向越来越偏离当前梯度，训练失败
- D. 训练变快，因为梯度更大

**Q7.** 比较 `train_xor` 和 `train_circle` 的训练循环，下列描述正确的是：

- A. 两者完全相同
- B. `train_xor` 把 4 个样本的 loss 相加后做一次 `backward`、一次更新（full-batch 梯度下降）；`train_circle` 每个样本都 `backward` 并更新一次（在线 SGD），且每个 epoch 先打乱数据
- C. `train_xor` 每个样本更新一次，`train_circle` 每个 epoch 更新一次
- D. `train_circle` 不使用反向传播

---

## 三、动手 / 代码题

**Q8.** 本节的平方误差是这样实现的：

```python
def mse_loss(predicted, target):
    diff = predicted + Value(-target)
    return diff * diff
```

而 `Value.__init__` 中 `self._children = set(children)`，所以 `diff * diff` 的输出节点的 `_children` 集合里**只有一个元素**。
(a) `diff * diff` 反向时，`diff.grad` 会得到正确的 `2·diff.data·out.grad` 吗？为什么？
(b) 如果把 `__mul__` 和 `__add__` 的 `_backward` 中所有 `+=` 都改成 `=`，对 `d = Value(3.0); e = d * d; e.backward()`，`d.grad` 会是多少？对 Q3 的表达式，`a.grad` 又会是多少？

**Q9.** 写一个函数 `grad_check(net, data, h=1e-5)`：用中心差分 `(L(θ+h) − L(θ−h)) / 2h` 逐个计算 `net.parameters()` 的数值梯度，与 `backward()` 得到的解析梯度比较，返回最大相对误差。在 `Network([2, 4, 1])`（`random.seed(42)`）和 XOR 数据上测试。

**Q10.** 给 `Value` 增加两个运算，并写出 `_backward`：
(a) `relu()`：输出 `max(0, x)`，导数在 `x > 0` 时为 1，否则为 0；
(b) `__pow__(k)`：仅支持整数次幂 `k`。
然后用 `(p - t) ** 2` 验证：`p = Value(0.8)`、`t = 1.0` 时 `p.grad` 应为多少？

---

## 四、面试高频题

**Q11.**（基础必考）请手推一个两层全连接网络（sigmoid 激活、MSE 损失）的反向传播，写出每一层 `W`、`b` 的梯度，并写成矩阵形式。

**Q12.**（原理深挖）数值微分、前向模式自动微分、反向模式自动微分各自的计算复杂度是什么？为什么深度学习框架都用反向模式？

**Q13.**（原理深挖）梯度消失和梯度爆炸是怎么产生的？如何诊断？有哪些缓解手段？

**Q14.**（工程实践）训练时显存主要花在哪些地方？为什么训练比推理更耗显存？梯度检查点（gradient checkpointing）是怎样用计算换显存的？

**Q15.**（追问型）PyTorch 为什么默认"累加"梯度而不是覆盖？有什么场景主动利用了这一点？`torch.no_grad()` 和 `.detach()` 分别在什么时候用？

---

## 五、参考答案与解析

### Q1 — 答案：B

反向模式自动微分的一个关键性质：对**标量输出**（loss），一次反向遍历就能得到对所有输入的偏导，代价与一次前向同阶（常数倍，通常认为 2～3 倍）。A 是数值差分（前向差分 P 次，中心差分 2P 次）的代价，正是讲义说的"230 万次前向"。C、D 没有依据。

### Q2 — 答案：B

乘法的局部导数：`∂out/∂a = b`、`∂out/∂b = a`。所以 `a.grad += b.data × out.grad = −2 × 0.5 = −1.0`，`b.grad += a.data × out.grad = 3 × 0.5 = 1.5`。C 把两者弄反了——记住"**交换**：各自拿对方的值"。A 是加法节点的行为。

### Q3 — 答案：C

`c = a·b + a`，`∂c/∂a = b + 1 = −3 + 1 = −2`。`a` 被用了两次（乘法和加法），两条路径的梯度相加：乘法路径贡献 `b.data × 1 = −3`，加法路径贡献 `1`，合计 −2（实际运行结果 `a.grad = -2.0`、`b.grad = 2.0`）。A（−3）正是把 `+=` 写成 `=` 时得到的错误答案，见 Q8。

### Q4 — 答案：B

`_backward` 做的是"把**自己的** `grad` 乘局部导数后传给输入"。如果某个节点还没收齐所有下游传来的梯度就往下传，下游拿到的就是不完整的梯度。拓扑排序保证"所有用到 v 的节点都排在 v 之后"，逆序处理时它们一定先于 v 执行。A、C 无关；D 反而是这种递归实现的一个隐患（图很深时会超过 Python 默认递归深度）。

### Q5 — 答案：C

反向传播本身是精确的（B 错），问题在于它要穿过的函数：每层乘一个 `σ'(z) = s(1−s) ≤ 0.25`。用本节代码构造一个 `Network([2, 8, 8, 8, 8, 8, 1])`（`random.seed(0)`，输入 `[0.5, -0.3]`，目标 1.0）实测：单样本反向后各层权重的平均 `|grad|` 从输出层的约 0.146 降到第一层的约 5.8e−6，相差两万多倍。严格说梯度还要乘权重，权重大时也可能放大，但对于常规初始化，sigmoid 的这个上界决定了梯度大概率逐层缩小。A 错：增大学习率会让后面几层先爆掉；D 错：恰恰是离输出最远的层受影响最大。

### Q6 — 答案：C

`backward()` 里只把**根节点**的 `grad` 设为 1.0，所有参数的梯度都是 `+=` 累加的（A 错）。不清零的话，第 t 个 epoch 的"梯度"其实是前 t 个 epoch 梯度之和，更新步长越来越大、方向越来越陈旧。实测删掉 `zero_grad()` 后，XOR 的 loss 在 0.50～0.52 之间来回震荡，最终输出 `[0.0, 0.4992, 1.0, 0.4992]`，没有学会。

### Q7 — 答案：B

`train_xor`：`total_loss = total_loss + loss` 累加 4 个样本，循环结束后一次 `zero_grad` + `backward` + 更新，是 **full-batch 梯度下降**。`train_circle`：每个样本 `zero_grad` → `backward` → 更新，是**在线 SGD**（batch size = 1），并且每个 epoch 先 `random.shuffle`。实际工程中最常用的是两者折中：mini-batch SGD。

### Q8 — 参考答案

(a) **正确**。`_backward` 是闭包，它引用的是 `self` 和 `other` 两个变量，此时二者指向同一个对象 `diff`：

```python
def _backward():
    self.grad += other.data * out.grad   # diff.grad += diff.data * out.grad
    other.grad += self.data * out.grad   # diff.grad += diff.data * out.grad（再加一次）
```

两行各加一次，合计 `2·diff.data·out.grad`，正是 `d(x²)/dx = 2x`。`_children` 用 `set` 只影响拓扑排序（避免同一节点被重复访问），不影响梯度计算。实测 `d = Value(3.0); e = d * d; e.backward()` 得到 `d.grad = 6.0`。

(b) 改成 `=` 后：
- `d * d`：第二行覆盖第一行，`d.grad = 3.0`（正确应为 6.0）；
- Q3 的 `a·b + a`：逆拓扑序先处理加法节点，`a.grad = 1`；再处理乘法节点，`a.grad = b.data × 1 = −3`，把加法路径的贡献覆盖掉了，最终 `a.grad = −3.0`（正确应为 −2.0）。

这就是讲义强调 "The `+=` is critical" 的原因：多元链式法则要求**对所有路径求和**。

### Q9 — 参考答案

```python
def total_loss(net, data):
    loss = Value(0.0)
    for inputs, target in data:
        loss = loss + mse_loss(net([Value(v) for v in inputs]), target)
    return loss


def grad_check(net, data, h=1e-5):
    loss = total_loss(net, data)
    net.zero_grad()
    loss.backward()
    analytic = [p.grad for p in net.parameters()]

    max_rel = 0.0
    for p, g in zip(net.parameters(), analytic):
        old = p.data
        p.data = old + h
        lp = total_loss(net, data).data
        p.data = old - h
        lm = total_loss(net, data).data
        p.data = old                      # 一定要恢复原值
        numeric = (lp - lm) / (2 * h)
        rel = abs(numeric - g) / max(1e-8, abs(numeric) + abs(g))
        max_rel = max(max_rel, rel)
    return max_rel


random.seed(42)
net = Network([2, 4, 1])
xor_data = [([0.0, 0.0], 0.0), ([0.0, 1.0], 1.0), ([1.0, 0.0], 1.0), ([1.0, 1.0], 0.0)]
print(f"max relative error: {grad_check(net, xor_data):.2e}")
```

实测输出 `max relative error: 1.75e-08`，说明手写反向传播是正确的。要点：
- 用**中心差分**（误差 O(h²)）而不是前向差分（误差 O(h)）；
- `h` 不能太小（浮点抵消误差）也不能太大（截断误差），1e-5 左右是常用值；
- 用**相对误差**比较，分母加一个下限防止除以 0；经验上 < 1e-7 很好，> 1e-3 基本可以断定有 bug；
- 扰动后**必须恢复**参数原值，否则后面的检查全错；
- 数值检查要跑 2P 次前向，只能用于小网络调试，这正好说明了反向传播的价值。

### Q10 — 参考答案

```python
def relu(self):
    out = Value(max(0.0, self.data), (self,), 'relu')

    def _backward():
        self.grad += (1.0 if self.data > 0 else 0.0) * out.grad

    out._backward = _backward
    return out

def __pow__(self, k):
    assert isinstance(k, int), "only int powers"
    out = Value(self.data ** k, (self,), f'**{k}')

    def _backward():
        self.grad += k * self.data ** (k - 1) * out.grad

    out._backward = _backward
    return out

Value.relu = relu
Value.__pow__ = __pow__

p = Value(0.8); t = 1.0
loss = (p - t) ** 2
loss.backward()
print(p.grad)          # -0.3999999999999999
```

`d(p−t)²/dp = 2(p−t) = 2 × (0.8 − 1) = −0.4`，实测输出 `-0.3999999999999999`（浮点误差）。注意：
- `p - t` 能工作，是因为代码已经实现了 `__sub__`（`self + (-other)`），`t` 是 float，`-t` 直接是 float 取负，再由 `__add__` 包装成 `Value`；
- ReLU 在 `x = 0` 处不可导，工程上约定导数取 0（PyTorch 也是如此）；
- 局部导数要用**前向时的输入值** `self.data`，闭包正好捕获了它。

### Q11 — 参考回答要点

单样本、列向量记法，损失 `L = ‖a2 − y‖²`（与本节一致，不带 ½）：

```text
前向：z1 = W1·x + b1,  a1 = σ(z1),  z2 = W2·a1 + b2,  a2 = σ(z2)

反向：
δ2 = ∂L/∂z2 = 2(a2 − y) ⊙ a2 ⊙ (1 − a2)
∂L/∂W2 = δ2 · a1ᵀ          ∂L/∂b2 = δ2
δ1 = ∂L/∂z1 = (W2ᵀ · δ2) ⊙ a1 ⊙ (1 − a1)
∂L/∂W1 = δ1 · xᵀ           ∂L/∂b1 = δ1
```

- 规律：**权重梯度 = 本层 delta × 本层输入的转置**；**bias 梯度 = delta**；**delta 往前传 = 乘权重转置，再逐元素乘激活导数**。
- 形状自检：`∂L/∂W` 的形状必须和 `W` 一样。`δ2` 是 `(n2, 1)`、`a1ᵀ` 是 `(1, n1)`，乘出来 `(n2, n1)` 与 `W2` 一致。
- mini-batch：把列向量换成矩阵 `X: (B, n0)`，`∂L/∂W = Δᵀ·A`（或按约定转置），bias 梯度对 batch 维求和。
- 加分点：说明讲义里 `dL/da1 = dL/dz2 * W2` 是标量写法，矩阵形式要用 `W2ᵀ`；提到如果用 sigmoid + 交叉熵，`δ2` 会化简为 `a2 − y`，`σ'` 被抵消（下一节损失函数会讲）。

### Q12 — 参考回答要点

| 方法 | 计算 n 个输入、m 个输出的全部导数 | 特点 |
|------|------------------------------|------|
| 数值微分（有限差分） | 约 n（前向差分）或 2n（中心差分）次函数求值 | 实现简单，但有截断 / 舍入误差，只适合做梯度检查 |
| 前向模式 AD | 约 n 次"带导数的前向"（每次得到一列 Jacobian） | 不需要存中间结果；输入少、输出多时高效 |
| 反向模式 AD（反向传播） | 约 m 次反向（每次得到一行 Jacobian） | 需要存储前向的中间值；输出少、输入多时高效 |

- 深度学习的典型情形：参数 n 动辄上亿，输出是**一个标量 loss**（m = 1），所以反向模式一次反向即可得到全部梯度，代价与前向同阶。
- 代价：必须存储前向激活，显存占用与网络深度、batch size、序列长度成正比。
- 加分点：前向模式通过对偶数（dual numbers）实现；JAX 同时提供 `jvp`（前向）和 `vjp`（反向）；Hessian-向量积可以用"前向套反向"高效计算。

### Q13 — 参考回答要点

- 成因：反向传播中第 l 层的梯度 ≈ 后面所有层"激活导数 × 权重"的连乘。连乘的因子普遍 < 1 → **消失**；普遍 > 1 → **爆炸**。sigmoid / tanh 的饱和区导数接近 0，是消失的主要来源；权重初始化过大、RNN 中同一矩阵反复相乘，是爆炸的常见来源。
- 诊断：
  - 按层打印梯度范数（本节练习 5）：前几层梯度比后几层小几个数量级 → 消失；
  - loss 突然变成 NaN / Inf、梯度范数暴涨 → 爆炸；
  - 前几层权重几乎不变、激活值全部贴近 0 或 1 → 饱和。
- 缓解：
  - 激活函数：ReLU / GELU 替代 sigmoid（正区间导数为 1）；
  - 初始化：Xavier（tanh/sigmoid）、He（ReLU），让每层输出方差保持稳定；
  - 归一化：BatchNorm / LayerNorm；
  - 结构：残差连接给梯度提供"恒等通路"；LSTM / GRU 的门控；
  - 爆炸专用：梯度裁剪（按范数裁剪，讲义练习 4 用的是按值裁剪到 [−1, 1]）、降低学习率、warmup。
- 常见误区：以为"梯度消失是反向传播的问题"——算法本身是精确的，问题在网络结构和激活函数。

### Q14 — 参考回答要点

- 显存组成：
  1. **参数**；
  2. **梯度**（与参数同样大小）；
  3. **优化器状态**（如 Adam 的一阶、二阶矩，各一份参数大小）；
  4. **激活值**：前向中为反向保存的中间结果，规模与 batch size × 序列长度 × 层数成正比，大模型训练中往往是最大头；
  5. 临时缓冲区。
- 推理只需要参数 + 当前层的激活（加上 LLM 的 KV cache），不存梯度、不存优化器状态、不需要为反向保存所有层的激活，所以显存小得多。本节 `Value` 把每个中间结果都留在图里，正是"为反向保存激活"的原型。
- 梯度检查点：前向时只在少数"检查点"层保存激活，其余丢弃；反向到某段时，从最近的检查点**重新做一次前向**恢复这段的激活。典型代价是多约一次前向的计算，换来激活显存从 O(L) 降到约 O(√L)（L 为层数，按 √L 分段时）。
- 加分点：混合精度（激活用 FP16/BF16）、ZeRO / FSDP 把参数、梯度、优化器状态分片到多卡，都是同一个问题的不同解法。

### Q15 — 参考回答要点

- 为什么累加：
  - 数学上必须如此：一个参数在图中被多次使用（权重共享、RNN 时间步、本节 `a·b + a`），总梯度就是各路径之和，引擎内部本来就要 `+=`；
  - 设计上把"何时清零"交给用户，就能支持更多用法。
- 主动利用的场景：**梯度累积**（gradient accumulation）——显存放不下大 batch 时，连续做 k 次小 batch 的 `backward()` 而不清零，再一次 `step()`，等价于 batch size 扩大 k 倍（loss 通常要除以 k）；多任务 / 多个 loss 分别 `backward` 后合并也是同理。
- 代价：忘了 `zero_grad()` 就会像 Q6 那样训练失败；PyTorch 中常用 `optimizer.zero_grad(set_to_none=True)`。
- `torch.no_grad()`：一个上下文管理器，内部的运算不构建计算图、不保存激活，用于推理、评估、手动更新参数（就像本节的 `p.data -= lr * p.grad` 不应该被记录到图里）。
- `.detach()`：返回一个与原张量共享数据、但脱离计算图的新张量，用于"截断"梯度流：如 RL 中的 target 值、GAN 训练判别器时阻止梯度传回生成器、把张量转成 NumPy 前。
- 加分点：推理时还可以用 `torch.inference_mode()`，比 `no_grad` 开销更小。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 04 机器学习中的微积分](../../../01-math-foundations/04-calculus-for-ml/docs/zh.md)：导数、偏导数、梯度。
- [阶段 01 · 05 链式法则与自动微分](../../../01-math-foundations/05-chain-rule-and-autodiff/docs/zh.md)：本节直接用到的链式法则和计算图思想。
- [阶段 03 · 02 多层网络和 Forward Pass](../../02-multi-layer-networks/docs/zh.md)：本节要"学起来"的正是上一节的 Layer / Network 结构与圆分类任务。

### 本节被哪些后续内容用到
- [阶段 03 · 04 Activation Functions](../../04-activation-functions/docs/zh.md)：用 ReLU 等解决本节暴露的 sigmoid 梯度消失。
- [阶段 03 · 05 Loss Functions](../../05-loss-functions/docs/zh.md)：本节用的 MSE 之外，分类更合适的交叉熵，以及 softmax + CE 的简洁梯度。
- [阶段 03 · 06 Optimizers](../../06-optimizers/docs/zh.md)：把 `p.data -= lr * p.grad` 升级为 Momentum、Adam。
- [阶段 03 · 08 Weight 初始化和训练稳定性](../../08-weight-initialization/docs/zh.md)：本节 `sqrt(2/n_inputs)` 缩放背后的方差分析。
- [阶段 03 · 10 构建您自己的迷你框架](../../10-mini-framework/docs/zh.md)：把标量 `Value` 扩展为张量级的自动求导框架。
- [阶段 03 · 13 调试神经网络](../../13-debugging-neural-networks/docs/zh.md)：梯度检查、梯度范数监控等调试手段。
- [阶段 10 · 34 Gradient Checkpointing](../../../10-llms-from-scratch/34-gradient-checkpointing/docs/zh.md)：用重计算换显存，直接建立在"反向需要保存激活"之上。

### 延伸关键词
`reverse-mode AD` · `forward-mode AD / JVP / VJP` · `micrograd` · `gradient checking` · `梯度裁剪` · `梯度累积` · `torch.no_grad / detach` · `gradient checkpointing`
