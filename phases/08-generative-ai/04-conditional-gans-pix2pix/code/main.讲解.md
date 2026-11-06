# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 04 节 有条件 GANs & Pix2Pix ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 2–3 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这是上一节 1-D GAN 的"条件版"：条件是一个类别标签 `c ∈ {0, 1}`，类 0 的真实数据是 `N(-2, 0.3²)`，类 1 是 `N(2, 0.3²)`。生成器要学会"给我类 0，我就给你一个 -2 附近的数"。它要你理解：

1. **条件怎么接进网络**：把 one-hot 向量拼接到 G 和 D 的输入上——讲义说这是"最简单的办法"。
2. **为什么 D 也要看条件**：D 判断的是"这个样本对**这个类**来说像不像真的"，而不是"像不像任意一个真样本"。
3. **从边缘分布到条件分布**：同样的网络结构，多一个输入，G 学到的就从"两峰混合"变成"按类选峰"。
4. **Pix2Pix 的 L1 项在代码里的样子**：`update_g` 预留了 `l1_w` / `targets` 参数，实现了 L1 的次梯度（`main` 默认没启用）。
5. **怎样评估条件生成**：逐类看均值只是第一步，类内的多样性（标准差）同样重要。

> 一句话：**cGAN = 给 G 和 D 都多接一根"条件"线**；Pix2Pix 把这根线换成整张图，再加上 U-Net、PatchGAN 和 L1。这份代码只演示了最核心的那根线。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sigmoid` / `leaky` / `leaky_grad` | 工具函数 | 数值稳定的 sigmoid；LeakyReLU 及导数 | 与上一节相同 |
| `matmul` / `add` / `randn_matrix` / `init_mlp` | 工具函数 | 纯列表线性代数、单隐层 MLP | 网络结构 |
| `one_hot(c, num)` | 函数 | 类别 → one-hot 向量 | 条件编码 |
| `g_forward(z, c, G, num_classes)` | 前向 | `[z ‖ onehot(c)]` → 16 → 1 | 条件生成器 `G(z, c)` |
| `d_forward(x, c, D, num_classes)` | 前向 | `[x ‖ onehot(c)]` → 16 → 1 → sigmoid | 条件判别器 `D(x, c)` |
| `sample_real_conditional(n, num_classes, rng)` | 数据 | 先随机抽类，再从该类的高斯采样，返回 `([x], c)` 对 | 条件数据分布 `p(x | c)` |
| `update_d` + `accumulate_d_grad` | 训练步 | BCE（真=1、假=0），真假样本都带着各自的类 | 条件 D 步 |
| `update_g(..., l1_w=0.0, targets=None)` | 训练步 | 非饱和对抗损失 + 可选的 L1 次梯度 | 条件 G 步 / Pix2Pix 的 L1 项 |
| `init_grads` / `apply_grads` | 工具函数 | 建同形状全 0 梯度；SGD 更新（除以样本数） | `zero_grad` / `optimizer.step` |
| `main()` | 演示入口 | 600 步交替训练，每 150 步打印各类均值，最后逐类采样 | 训练 + 逐类验证 |

数据流：`(x, c)` 真样本对 + `(G(z, c), c)` 假样本对 → `update_d`；新噪声 + 新随机类别 → `G` → `D`（同一个类别）→ 梯度回传 → `update_g`。

---

## 3. 逐段精讲

### 3.1 条件编码：one-hot + 列表拼接

```python
def one_hot(c, num):
    v = [0.0] * num
    v[c] = 1.0
    return v

def g_forward(z, c, G, num_classes):
    inp = z + one_hot(c, num_classes)
    pre1 = add(matmul(G["W1"], inp), G["b1"])
    h = [leaky(v) for v in pre1]
    out = add(matmul(G["W2"], h), G["b2"])
    return out, h, pre1, inp
```

- `z + one_hot(...)` 是 **Python 列表的拼接**：`[0.5, -1.0, 0.2, 0.3] + [0.0, 1.0] → [0.5, -1.0, 0.2, 0.3, 0.0, 1.0]`。G 的第一层因此要接收 `z_dim + num_classes = 6` 维输入（见 `main` 里的 `init_mlp(z_dim + num_classes, ...)`）。
- ⚠️ 如果换成 NumPy 数组，`+` 就变成逐元素相加（形状不同会报错，形状相同则静默出错），必须改用 `np.concatenate` / `torch.cat`。
- one-hot 拼接等价于"每个类别有一个可学习的偏置向量"：`W1 · [z ‖ e_c] = W1_z · z + W1[:, c]`，即类别 `c` 选中 `W1` 的某一列加到隐藏层预激活上。这就是为什么 one-hot 拼接可以看作最简单的 embedding。
- `g_forward` 多返回了 `inp`：反向传播算 `W1` 的梯度时需要它（`dpre1 * inp[k]`），这一点和上一节只返回 `z` 不同。
- 讲义提到更强的条件注入：learned embedding、FiLM、cross-attention。one-hot 只在网络第一层起作用，条件信号可能偏弱，这正是讲义 Pitfalls 里"Condition ignored"的成因之一。

### 3.2 条件判别器：看的是"样本 + 类别"

```python
def d_forward(x, c, D, num_classes):
    inp = x + one_hot(c, num_classes)
    pre1 = add(matmul(D["W1"], inp), D["b1"])
    h = [leaky(v) for v in pre1]
    logit = add(matmul(D["W2"], h), D["b2"])[0]
    return sigmoid(logit), h, pre1, inp, logit
```

- D 的输入是 `[x, onehot(c)]`，共 `1 + num_classes = 3` 维。对应讲义的核心论点：**D must judge whether y is consistent with x**。在本例中就是：一个 `+2` 的样本配上类 0 的标签，即使 `+2` 本身是"真实数据中常见的值"，D 也应该判它为假。
- 这就是 Pix2Pix 里"把条件图和输出图在通道维拼接后送进 D"的一维版本。如果 D 只看 `x`，G 就可以对任何类别都输出任一峰的值来骗过 D。
- 返回值多了 `logit`（未经 sigmoid 的分数），虽然本文件没用到，但便于以后换成 WGAN 或 hinge 损失。

### 3.3 条件数据：返回 `(样本, 类别)` 对

```python
def sample_real_conditional(n, num_classes, rng):
    out = []
    for _ in range(n):
        c = rng.randrange(num_classes)
        if c == 0:
            x = rng.gauss(-2.0, 0.3)
        else:
            x = rng.gauss(2.0, 0.3)
        out.append(([x], c))
    return out
```

- 先均匀抽类别，再从 `p(x | c)` 采样——条件分布的祖先采样。
- 每个元素是元组 `([x], c)`，后面用 `for (x, c) in reals` 直接解包。
- ⚠️ `if c == 0 ... else ...` 把类别中心**写死**了：哪怕 `num_classes=3`，类 2 也会落在 +2。讲义练习 1"加第三个类"需要同时改这里（例如用一个 `centers` 列表按 `c` 取中心）。

### 3.4 D 步：真假样本都带着类别

```python
def update_d(reals, fakes, D, num_classes, lr):
    grads = init_grads(D)
    for (x, c) in reals:
        accumulate_d_grad(x, c, 1.0, D, num_classes, grads)
    for (x, c) in fakes:
        accumulate_d_grad(x, c, 0.0, D, num_classes, grads)
    n = len(reals) + len(fakes)
    apply_grads(D, grads, lr, n)
```

- 与上一节相比，最大的变化是：`accumulate_d_grad` 从闭包变成了**独立的顶层函数**，`grads` 作为参数传入并被原地修改；梯度清零和更新也抽成了 `init_grads` / `apply_grads`。代码复用更好，`update_g` 也能用同一套工具。
- 在 `main` 里，假样本的类别 `cs` **取自同一批真样本**：`fakes = [(g_forward(noise[i], cs[i], ...)[0], cs[i]) ...]`。这保证了 D 每一步看到的真假样本类别分布一致，D 不能靠"类别比例"作弊。
- 梯度公式 `dL_dpre2 = p - target` 与上一节完全相同，只是 `W1` 的梯度用的是拼接后的 `inp`（3 维）。

### 3.5 G 步：对抗损失 + 可选 L1

```python
def update_g(noise, cs, G, D, num_classes, lr, l1_w=0.0, targets=None):
    """Non-saturating G loss + optional conditional L1 toward a target."""
    grads = init_grads(G)
    for i, z in enumerate(noise):
        c = cs[i]
        x_hat, g_h, g_pre1, g_inp = g_forward(z, c, G, num_classes)
        p, d_h, d_pre1, d_inp, d_logit = d_forward(x_hat, c, D, num_classes)
        dL_dpre2 = p - 1.0
        # ... 穿过 D 求 dL_dxhat（与上一节相同）
        if l1_w > 0 and targets is not None:
            for k in range(len(x_hat)):
                dL_dxhat[k] += l1_w * (1.0 if x_hat[k] > targets[i][k] else -1.0)
        grads["b2"] = [grads["b2"][i] + dL_dxhat[i] for i in range(len(x_hat))]
        # ... 进入 G 的反向传播，W1 的梯度乘以 g_inp[k]
    apply_grads(G, grads, lr, len(noise))
```

- **关键：G 和 D 用的是同一个 `c`**。G 生成"类 c 的样本"，D 判断"它作为类 c 的样本是否真实"，梯度告诉 G"怎样才更像类 c"。
- **对抗部分**：非饱和损失 `-log D(G(z, c), c)`，对 logit 的梯度 `p - 1`，和上一节一致。
- **L1 部分（Pix2Pix 的 `λ·||y - G(x)||₁`）**：`|x̂ - y|` 对 `x̂` 的次梯度是 `sign(x̂ - y)`，乘以 `l1_w`，**直接加到 `dL_dxhat` 上**——两种损失在生成器输出处汇合，之后共享同一段反向传播。这正是"总损失 = 对抗 + λ·L1"在梯度层面的样子。
  - ⚠️ `x̂ == y` 时返回 -1 而非 0（次梯度惯例取 0），对浮点数影响可忽略。
  - ⚠️ `main` 没有启用这一项（`l1_w` 默认 0），因为这个 1-D 任务里没有"每个 z 对应的配对目标"。测验 Q10 演示了把目标设成类中心时的效果：均值变准了，但类内标准差从 0.46–0.62 坍缩到 0.06–0.10——L1 让 G 忽略了噪声，对应讲义"λ 太大 → 变糊"。
- **变量名遮蔽**：外层 `for i, z in enumerate(noise)`，内层列表推导式又用 `i`。Python 3 的推导式有独立作用域，所以不是 bug，但读起来容易误解；建议改成 `k`。

### 3.6 `init_grads` / `apply_grads`：把样板代码抽出来

```python
def init_grads(net):
    grads = {}
    for k, v in net.items():
        if isinstance(v[0], list):
            grads[k] = [[0.0] * len(v[0]) for _ in v]
        else:
            grads[k] = [0.0] * len(v)
    return grads

def apply_grads(net, grads, lr, n):
    for k, v in net.items():
        if isinstance(v[0], list):
            for i in range(len(v)):
                for j in range(len(v[i])):
                    v[i][j] -= lr * grads[k][i][j] / n
        else:
            for i in range(len(v)):
                v[i] -= lr * grads[k][i] / n
```

- 这两个函数就是 PyTorch 里 `optimizer.zero_grad()` 和 `optimizer.step()` 的最小版本：前者按参数形状建全 0 的梯度容器，后者做 `参数 -= lr × 平均梯度`。
- 除以 `n` 把"梯度之和"变成"梯度均值"，让学习率与 batch 大小解耦。
- 对比上一节把这些逻辑写在 `update_d` / `update_g` 里各一遍，这里是一次小重构——**同样的逻辑出现两次就该抽函数**。

### 3.7 `main`：训练与逐类验证

```python
    for step in range(1, 601):
        reals = sample_real_conditional(batch, num_classes, rng)
        cs = [c for _, c in reals]
        noise = [[rng.gauss(0, 1) for _ in range(z_dim)] for _ in range(batch)]
        fakes = [(g_forward(noise[i], cs[i], G, num_classes)[0], cs[i]) for i in range(batch)]
        update_d(reals, fakes, D, num_classes, d_lr)

        noise = [[rng.gauss(0, 1) for _ in range(z_dim)] for _ in range(batch)]
        cs = [rng.randrange(num_classes) for _ in range(batch)]
        update_g(noise, cs, G, D, num_classes, g_lr)

        if step % 150 == 0:
            probes = {c: [] for c in range(num_classes)}
            for _ in range(300):
                c = rng.randrange(num_classes)
                z = [rng.gauss(0, 1) for _ in range(z_dim)]
                probes[c].append(g_forward(z, c, G, num_classes)[0][0])
```

- `cs = [c for _, c in reals]`：从 `(x, c)` 对里只取类别，`_` 表示丢弃 `x`。
- G 步**重新抽类别**（`rng.randrange`），而不是沿用 D 步的 `cs`，让 G 在每一步都见到随机的条件组合。
- 监控用字典 `probes = {0: [...], 1: [...]}` 按类收集样本，再分别求均值——这就是讲义 Step 3 "verify per-class output" 的实现。由于类别是随机抽的，每类样本数（`n=144/156` 等）不完全相等。
- ⚠️ 只打印了均值，没有打印标准差；第 6 节会看到，这会让结果显得比实际更好。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| one-hot 拼接到输入 | 最简单，一眼看懂"条件进网络" | 条件只作用于第一层，信号弱；生产用 embedding、FiLM、cross-attention、projection D |
| D 也接收条件 | 让 D 判断"样本与条件是否一致" | 无 |
| 假样本类别取自真样本 batch | 真假类别分布一致，D 不能靠类别比例区分 | 无 |
| 1-D 类别条件而非图像条件 | 秒级跑完，可直接打印每类统计量 | 没有 U-Net、PatchGAN；真正的 Pix2Pix 是图像到图像 |
| 预留 L1 但默认关闭 | 展示 Pix2Pix 损失的梯度结构；本任务没有逐样本配对目标 | 读者容易以为 `main` 用了 L1；Pix2Pix 默认 λ=100 |
| 抽出 `init_grads` / `apply_grads` | 消除重复代码 | 无 |
| 只监控每类均值 | 简单 | 看不见类内多样性问题；应同时监控标准差 / FID |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表拼接 `+` | `inp = z + one_hot(c, num_classes)` | 两个列表首尾相接；⚠️ NumPy 数组的 `+` 是逐元素相加 |
| 列表乘法 + 下标赋值 | `v = [0.0] * num; v[c] = 1.0` | 先建全 0 列表，再把第 c 位设为 1 |
| `rng.randrange(n)` | `c = rng.randrange(num_classes)` | 均匀抽取 `0..n-1` 的整数 |
| 元组作为列表元素 | `out.append(([x], c))` | 把样本和标签打包成一对 |
| for 中解包元组 | `for (x, c) in reals:` | 括号可省略，写成 `for x, c in reals` 也一样 |
| `_` 丢弃变量 | `cs = [c for _, c in reals]` | 只要第二个元素 |
| `enumerate` | `for i, z in enumerate(noise):` | 同时拿下标和元素 |
| 推导式的独立作用域 | `[grads["b2"][i] + dL_dxhat[i] for i in range(...)]` | Python 3 中推导式里的 `i` 不会覆盖外层 `i` |
| 默认参数 + `None` 哨兵 | `l1_w=0.0, targets=None`；`if l1_w > 0 and targets is not None` | 可选功能的常见写法；用 `is not None` 判断 |
| 字典推导式 | `probes = {c: [] for c in range(num_classes)}` | 为每个类建一个空列表；⚠️ 不要用 `dict.fromkeys(range(n), [])`，那样所有键共享同一个列表 |
| `dict.items()` | `for k, v in net.items():` | 同时遍历参数名和参数 |
| 原地修改嵌套列表 | `v[i][j] -= lr * grads[k][i][j] / n` | `v` 是 `net[k]` 的引用，修改直接生效 |
| 字符串累加 | `line += f"  class {c}: mean ..."` | 逐类拼出一行日志 |
| f-string 格式符 | `{step:4d}`、`{mean(...):+.2f}`、`{v:+.2f}` | 宽度 4 整数；带符号两位小数 |
| `" ".join(...)` | `" ".join(f"{v:+.2f}" for v in outs)` | 用空格连接生成器产生的字符串 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 2.3 秒）的输出：

```text
=== conditional GAN on two-mode mixture (class 0 -> -2, class 1 -> +2) ===
step  150:  class 0: mean -0.20  (n=144)  class 1: mean +0.63  (n=156)
step  300:  class 0: mean -0.31  (n=147)  class 1: mean +1.13  (n=153)
step  450:  class 0: mean -1.32  (n=146)  class 1: mean +1.52  (n=154)
step  600:  class 0: mean -2.56  (n=166)  class 1: mean +2.47  (n=134)

=== sampling per class ===
  class 0: -3.23 -1.40 -2.20 -2.37 -3.26 -2.51
  class 1: +2.89 +2.27 +1.77 +2.73 +1.92 +2.87
```

逐段解读：

- **条件被学会了**：第 150 步两类均值都还在 0 附近（-0.20 / +0.63），G 几乎没区分类别；到第 600 步，类 0 → -2.56、类 1 → +2.47，方向完全正确。同一个网络，仅凭输入的 one-hot 不同就产生了截然不同的输出——这正是结尾 takeaway 的意思。
- **但还没"学准"**：
  - 均值**冲过头**了（目标 ±2，实际约 ±2.5），说明训练还在振荡中，600 步时恰好偏向外侧；
  - 类内分布**太宽**：最后 6 个类 0 样本从 -3.26 到 -1.40，而真实数据标准差只有 0.3。我按 `main()` 相同流程复现最终模型，每类取 1000 个样本测得标准差约为 **0.62（类 0）和 0.46（类 1）**，是真实值的 1.5–2 倍。
- **教训**：日志只打印均值，看起来"差不多对了"；加上标准差才发现分布匹配得并不好。评估条件生成模型时，要逐类检查均值、方差（或 FID 等分布指标），同时提防另一个方向的问题——每类单独的模式崩溃（标准差过小）。
- `n=144/156` 等数字只是随机抽到每个类的探测样本数，不是模型输出。

---

## 7. 动手改一改

1. **打印类内标准差**：在每 150 步的日志里，为每个类加上 `statistics.pstdev(probes[c])`，观察它随训练如何变化。
2. **固定 z、换条件**：取同一个 `z`，分别用 `c=0` 和 `c=1` 生成，确认输出确实由条件决定；再看同一个 `z` 在两类下是否位于各自分布的"同一相对位置"。
3. **启用 L1**：把类中心当作目标（`targets = [[-2.0] if c == 0 else [2.0] for c in cs]`），试 `l1_w = 0.1 / 0.5 / 2.0`，记录每类均值和标准差。参考结果：`l1_w=0.5` 时约 `-1.98/0.10`、`+1.99/0.06`——均值更准、多样性坍缩。
4. **去掉 D 的条件**：让 `d_forward` 不拼接 one-hot（D 的输入维度改为 1），观察 G 是否开始忽略类别。
5. **加第三个类**（讲义练习 1）：把 `sample_real_conditional` 改成按 `centers = [-3.0, 0.0, 3.0]` 取中心，`num_classes = 3`。注意这会更难训：我用 600 步和 1500 步各试过一次，类别与中心都还没有对齐——试着加大 `hidden`、增加步数或调整学习率。
6. **进阶：FiLM 条件**：不再拼接 one-hot，而是为每个类学一对 `γ_c, β_c`（长度 = hidden），把 G 的隐藏层改成 `h = leaky(γ_c * pre1 + β_c)`，并推导相应的梯度。

---

## 8. 常见坑

- **把列表 `+` 当成向量加法**：本文件里 `z + one_hot(...)` 是拼接；迁移到 NumPy / PyTorch 时必须改成 `concatenate` / `cat`。
- **忘了调整第一层输入维度**：拼接条件后 G 的输入是 `z_dim + num_classes`，D 是 `1 + num_classes`，少算会导致 `zip` 静默截断（不会报错！）。
- **D 不看条件**：G 会忽略条件，只学到边缘分布。
- **真假样本类别分布不一致**：例如假样本全是类 0，D 可以靠类别作弊；本代码让假样本复用真样本的类别来避免。
- **只看每类均值**：均值对了，方差可能差一倍；也可能某个类单独模式崩溃。
- **数据生成写死类别**：`if c == 0 ... else ...` 在加类别时会悄悄把新类映射到旧中心。
