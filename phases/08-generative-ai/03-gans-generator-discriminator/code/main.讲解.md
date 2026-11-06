# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 03 节 GANs — 生成器与鉴别器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 2–3 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

一个**手写前向、手写反向、手写 minimax 循环**的一维 GAN：生成器把 4 维噪声映射成 1 个实数，判别器判断这个实数来自真实分布 `0.5·N(-2, 0.4²) + 0.5·N(2, 0.4²)` 还是来自生成器。它要你看清：

1. **对抗训练的两个步骤**：D 步用 BCE 区分真（1）假（0）；G 步让假样本"骗过"D。
2. **非饱和 G 损失**：`-log D(G(z))` 对 D 的 logit 的梯度是 `p - 1`，在 D 自信时依然有力。
3. **梯度如何穿过 D 流回 G**：G 步要先对 D 求"输入的梯度" `∂L/∂x̂`，再进入 G 的反向传播，但**只更新 G**。
4. **失败模式实时可见**：训练前 400 步就出现了模式崩溃（一个峰被饿死），之后才慢慢恢复。
5. **监控指标的局限**：按符号数模式的检测器，看不见"落在两峰之间"的伪样本。

> 一句话：**GAN 没有写下 `log p(x)`，它的"损失"本身是另一个正在学习的网络**——这份代码让你在 200 行里亲手摸到这件事有多微妙。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sigmoid` | 函数 | 数值稳定的 sigmoid | D 的输出概率 |
| `leaky_relu` / `leaky_grad` | 函数 | 斜率 0.2 的 LeakyReLU 及其导数 | DCGAN 推荐的激活 |
| `randn_matrix` / `matmul` / `add` / `init_mlp` | 工具 | 纯列表线性代数；单隐层 MLP 参数字典 | 网络结构 |
| `forward_g(z, G)` | 前向 | 4 → 16 → 1，输出层线性 | 生成器 `G: z → x̂` |
| `forward_d(x, D)` | 前向 | 1 → 16 → 1，输出过 sigmoid | 判别器 `D: x → [0, 1]` |
| `sample_real` / `sample_noise` | 数据 | 真实两峰数据；`N(0, I)` 噪声 | `p_data`、`p(z)` |
| `update_d(reals, fakes, D, lr)` | 训练步 | 对真样本（标签 1）、假样本（标签 0）累积 BCE 梯度，平均后 SGD | D 步 |
| `update_g(noise_batch, G, D, lr)` | 训练步 | 非饱和损失，梯度经 D 传到 `x̂`，再进 G | G 步 |
| `main()` | 演示入口 | 800 步交替训练，每 100 步打印 D 输出与模式计数 | minimax 循环 + 监控 |

数据流：`噪声 → G → 假样本 → update_d（与真样本一起训练 D）`；`新噪声 → G → D（只读）→ ∂L/∂x̂ → G 的梯度 → 更新 G`。

---

## 3. 逐段精讲

### 3.1 数值稳定的 sigmoid

```python
def sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)
```

- 直接写 `1 / (1 + math.exp(-x))`，当 `x = -1000` 时 `exp(1000)` 会抛 `OverflowError`。
- 分两种情况：`x ≥ 0` 时 `exp(-x) ≤ 1`；`x < 0` 时改用等价形式 `eˣ / (1 + eˣ)`，`exp(x) < 1`。两条路径都只对非正数求指数，**永远不会溢出**。
- 这正是 PyTorch 推荐 `BCEWithLogitsLoss`（在 logit 上直接算）而不是"先 sigmoid 再 BCE"的原因：数值稳定性。

### 3.2 LeakyReLU 与网络结构

```python
def leaky_relu(x, a=0.2):
    return x if x > 0 else a * x

def leaky_grad(x, a=0.2):
    return 1.0 if x > 0 else a

def forward_g(z, G):
    pre1 = add(matmul(G["W1"], z), G["b1"])
    h = [leaky_relu(v) for v in pre1]
    pre2 = add(matmul(G["W2"], h), G["b2"])
    return pre2, h, pre1

def forward_d(x, D):
    pre1 = add(matmul(D["W1"], x), D["b1"])
    h = [leaky_relu(v) for v in pre1]
    pre2 = add(matmul(D["W2"], h), D["b2"])
    return sigmoid(pre2[0]), h, pre1, pre2[0]
```

- **LeakyReLU（斜率 0.2）**：负半轴保留 0.2 的梯度，避免 ReLU 的"神经元死亡"。讲义的变体表里 DCGAN 就规定了 LeakyReLU——对判别器尤其重要，因为 G 的梯度全部要从 D 里穿过来，D 里"死掉"的单元会切断 G 的学习信号。
- `leaky_grad` 接收的是**预激活值 `pre1`**（与上一节 VAE 的 `tanh_grad` 接收输出不同），因为 LeakyReLU 的导数只取决于输入的正负。
- **G 输出层是线性的**：生成的是任意实数，不加激活；**D 输出层过 sigmoid**：得到"是真样本"的概率。
- 两个前向函数都返回**中间量**（`h`、`pre1`、`pre2`），供手写反向传播使用。
- 规模：G 是 4 → 16 → 1，D 是 1 → 16 → 1。初始化标准差 0.3。

### 3.3 数据：两个分得很开的峰

```python
def sample_real(n, rng):
    out = []
    for _ in range(n):
        if rng.random() < 0.5:
            out.append([rng.gauss(-2.0, 0.4)])
        else:
            out.append([rng.gauss(2.0, 0.4)])
    return out
```

- 两个峰中心相距 4，标准差只有 0.4，中间 `|x| < 1` 的区域几乎没有真实数据（约 0.5%）。这是一个**故意设计的难题**：G 的输出是噪声的连续函数，要把一团连续的 `z` 分成两个分开的峰，就必须在中间"快速跳过"，这对一个小 MLP 并不容易——后面会看到 G 在中间留下了一座"桥"。
- 每个样本包成 `[x]`（长度 1 的列表），以便和 `matmul` 的向量接口一致。

### 3.4 D 步：真=1、假=0 的 BCE

```python
def update_d(reals, fakes, D, lr):
    """Gradient step on D to maximize log D(x) + log(1 - D(G(z)))."""
    grads = {k: None for k in D}
    for part in D:
        if isinstance(D[part][0], list):
            grads[part] = [[0.0] * len(D[part][0]) for _ in D[part]]
        else:
            grads[part] = [0.0] * len(D[part])

    def accumulate(x, target):
        p, h, pre1, pre2 = forward_d(x, D)
        dL_dpre2 = p - target
        grads["b2"][0] += dL_dpre2
        for j in range(len(h)):
            grads["W2"][0][j] += dL_dpre2 * h[j]
        dh = [D["W2"][0][j] * dL_dpre2 for j in range(len(h))]
        dpre1 = [dh[j] * leaky_grad(pre1[j]) for j in range(len(h))]
        for j in range(len(h)):
            grads["b1"][j] += dpre1[j]
            for k in range(len(x)):
                grads["W1"][j][k] += dpre1[j] * x[k]

    for x in reals:
        accumulate(x, 1.0)
    for x in fakes:
        accumulate(x, 0.0)

    n = len(reals) + len(fakes)
    # ... 对每个参数执行 D[part][...] -= lr * grads[part][...] / n
```

- **梯度清零**：先按 D 的形状建一个全 0 的 `grads` 字典——相当于 PyTorch 的 `optimizer.zero_grad()`。注意 `[[0.0] * cols for _ in rows]` 用推导式生成**每行独立**的列表，而不是 `[[0.0] * cols] * rows`（那样所有行共享同一个列表）。
- **`dL_dpre2 = p - target`**：sigmoid + BCE 对 logit 的梯度化简为"预测 - 标签"（推导见测验 Q9）。真样本希望 `p → 1`，假样本希望 `p → 0`。
- **闭包 `accumulate`**：嵌套函数直接读写外层的 `grads` 和 `D`，避免每次都传一堆参数。它对列表做的是 `+=` 原地修改，所以不需要 `nonlocal`。
- **梯度累加再平均**：先对全部 64 个样本（32 真 + 32 假）累加，最后除以 `n` 再更新——这就是 mini-batch 梯度下降里"对 batch 取平均"。
- 传进来的 `fakes` 只是数值，D 步**完全不碰 G**。PyTorch 里对应 `fake.detach()`，防止 D 的损失把梯度传给 G。

### 3.5 G 步：梯度穿过 D 回到 G

```python
def update_g(noise_batch, G, D, lr):
    """Non-saturating G loss: maximize log D(G(z)). Gradient flows through both."""
    # ... grads 清零同上
    for z in noise_batch:
        x_hat, g_h, g_pre1 = forward_g(z, G)
        p, d_h, d_pre1, d_pre2 = forward_d(x_hat, D)
        # dL/dpre2_D where L = -log(p) is -(1/p) * p*(1-p) = p - 1
        dL_dpre2 = p - 1.0
        # back through D to get dL / d x_hat
        dh_D = [D["W2"][0][j] * dL_dpre2 for j in range(len(d_h))]
        dpre1_D = [dh_D[j] * leaky_grad(d_pre1[j]) for j in range(len(d_h))]
        dL_dxhat = [0.0] * len(x_hat)
        for j in range(len(d_h)):
            for k in range(len(x_hat)):
                dL_dxhat[k] += D["W1"][j][k] * dpre1_D[j]
        # now back through G
        grads["b2"] = [grads["b2"][i] + dL_dxhat[i] for i in range(len(x_hat))]
        for i in range(len(x_hat)):
            for j in range(len(g_h)):
                grads["W2"][i][j] += dL_dxhat[i] * g_h[j]
        dh_G = [sum(G["W2"][i][j] * dL_dxhat[i] for i in range(len(x_hat)))
                for j in range(len(g_h))]
        dpre1_G = [dh_G[j] * leaky_grad(g_pre1[j]) for j in range(len(g_h))]
        # ... 累加 G 的 b1、W1 梯度
    # ... 只对 G 执行 SGD 更新
```

这段是整份代码的核心，分三段看：

1. **非饱和损失的 logit 梯度**：`L = -log p`，`dL/dpre2 = p - 1`。D 越确信这是假样本（`p → 0`），梯度越接近 -1，G 得到的推力越强。若用原始的 `log(1 - p)`，梯度是 `-p`，在 `p → 0` 时消失——讲义说的"saturates and kills gradients"。
2. **穿过 D 求 `∂L/∂x̂`**：和 D 步的反向几乎一样，区别在最后一步——D 步求的是对 `W1` 的梯度（`dpre1 * x`），这里求的是**对输入 `x̂` 的梯度**（`W1ᵀ · dpre1`）。D 的参数只被读取，不被累加梯度，也不被更新。这就是"梯度流过 D，但 D 冻结"。
3. **进入 G**：`∂L/∂x̂` 就是 G 输出层的上游梯度，后面就是普通 MLP 的反向传播。
- `grads["b2"] = [...]` 这一行用的是**重新赋值**而不是 `+=` 原地修改，效果一样（每次都基于旧值加上新值），只是风格不统一。
- 讲义强调"Fresh fakes for G"：`main` 在 G 步前**重新采噪声**。G 步本来就会用最新的 D 重新前向，所以这里新噪声的主要意义是让 G 步与 D 步使用独立样本，减少两步之间的相关性。

### 3.6 主循环与监控

```python
    batch, g_lr, d_lr = 32, 0.02, 0.01
    for step in range(1, 801):
        reals = sample_real(batch, rng)
        noise = sample_noise(batch, z_dim, rng)
        fakes = [forward_g(z, G)[0] for z in noise]
        update_d(reals, fakes, D, d_lr)

        noise = sample_noise(batch, z_dim, rng)
        update_g(noise, G, D, g_lr)

        if step % 100 == 0:
            probe_fakes = [forward_g(z, G)[0][0] for z in sample_noise(400, z_dim, rng)]
            mode_a = sum(1 for v in probe_fakes if v < 0)
            mode_b = 400 - mode_a
            d_real = mean([forward_d(x, D)[0] for x in sample_real(100, rng)])
            d_fake = mean([forward_d([v], D)[0] for v in probe_fakes])
            warn = "  [!] mode collapse" if min(mode_a, mode_b) < 50 else ""
```

- **一步 D、一步 G**，讲义 Step 2 的标准交替。
- **学习率 `g_lr = 0.02` 是 `d_lr = 0.01` 的两倍**：刻意让 D 稍弱一点。讲义的第一条 Pitfall 就是"D 太强"，降低 D 学习率是最常见的平衡手段。
- **监控三件事**：`D(real)` 和 `D(fake)` 的均值（两者都接近 0.5 表示 D 分不清），以及按符号统计的两个模式计数。任一模式少于 50/400（12.5%）就打印模式崩溃警告。
- ⚠️ 监控本身也在消耗 `rng`：每 100 步额外采 400 个噪声和 100 个真样本，这会改变后续训练用到的随机数——删掉监控代码，训练结果就会不同。
- ⚠️ 讲义 Step 3 写的是每 200 步、500 个样本，练习 1 提到 `D_LR`、`G_LR` 常量；代码里实际是每 100 步、400 个样本，学习率是局部变量 `d_lr`、`g_lr`。以代码为准。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一维两峰数据 | 能直接数模式、能打印样本，失败模式肉眼可见 | 真实任务是图像；用 FID、precision/recall 评估 |
| 手写反向传播 | 看清"梯度穿过 D 但只更新 G" | 生产用 autograd，配合 `detach()` 与分开的两个优化器 |
| 非饱和 G 损失 | 训练早期 G 也有强梯度 | 理论上不再严格对应 JS 散度，但实践标准做法 |
| `g_lr = 2 × d_lr` | 防止 D 过强导致 G 梯度消失 | 生产中常用 TTUR、谱归一化、梯度惩罚来平衡 |
| LeakyReLU | 保证梯度能穿过 D 回到 G | — |
| 纯 SGD、无动量 | 代码简单 | GAN 实践常用 Adam（β₁ 取较小值） |
| 按符号数模式 | 一行代码就能检测"一个峰被饿死" | 看不见"模式之间的伪样本"（见第 6 节）；应配合分布距离指标 |
| 小网络（16 个隐藏单元） | 秒级跑完 | 容量有限，难以干净地分开两个峰 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 条件表达式 | `return x if x > 0 else a * x` | 一行 if/else |
| 默认参数 | `def leaky_relu(x, a=0.2)` | 调用时可省略 `a` |
| 多返回值 | `return sigmoid(pre2[0]), h, pre1, pre2[0]` | 实际返回一个元组 |
| 元组解包 | `p, h, pre1, pre2 = forward_d(x, D)` | 一次接住多个返回值 |
| 下标取单个返回值 | `forward_g(z, G)[0]`、`forward_g(z, G)[0][0]` | 先取元组第 0 个（输出列表），再取列表第 0 个（标量） |
| 字典推导式 | `grads = {k: None for k in D}` | 用 D 的键建同结构的字典 |
| 嵌套列表推导式 | `[[0.0] * len(D[part][0]) for _ in D[part]]` | 每行都是独立的新列表（不要写成 `[[0.0]*c]*r`） |
| 嵌套函数 / 闭包 | `def accumulate(x, target):` 定义在 `update_d` 内部 | 内层函数可读写外层变量引用的对象 |
| 原地修改 vs 重新赋值 | `grads["W2"][0][j] += ...` vs `grads["b2"] = [...]` | 前者修改原列表，后者把名字绑定到新列表 |
| `isinstance` | `isinstance(D[part][0], list)` | 区分矩阵与向量 |
| 生成器表达式计数 | `sum(1 for v in probe_fakes if v < 0)` | 统计满足条件的元素个数 |
| `min` 判断 | `min(mode_a, mode_b) < 50` | 两个计数中较小者是否过少 |
| 字符串条件赋值 | `warn = "  [!] mode collapse" if ... else ""` | 用空串表示"不打印" |
| 跨行 f-string | `print(f"step {step:4d}: ..." f"modeA={mode_a:3d} ...")` | 相邻字符串字面量自动拼接 |
| f-string 格式符 | `{step:4d}`、`{d_real:.2f}`、`{...:+.2f}` | 宽度 4 的整数；两位小数；带正负号 |
| `range(1, 801)` | 主循环 | 从 1 到 800（不含 801），便于 `step % 100 == 0` 判断 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 2.6 秒）的输出：

```text
=== training 1-D GAN on two-mode Gaussian mixture ===
step  100: D(real)=0.52  D(fake)=0.51  modeA=355  modeB= 45  [!] mode collapse
step  200: D(real)=0.52  D(fake)=0.50  modeA=392  modeB=  8  [!] mode collapse
step  300: D(real)=0.52  D(fake)=0.46  modeA=399  modeB=  1  [!] mode collapse
step  400: D(real)=0.53  D(fake)=0.44  modeA=387  modeB= 13  [!] mode collapse
step  500: D(real)=0.56  D(fake)=0.46  modeA=309  modeB= 91
step  600: D(real)=0.57  D(fake)=0.50  modeA=228  modeB=172
step  700: D(real)=0.59  D(fake)=0.53  modeA=207  modeB=193
step  800: D(real)=0.57  D(fake)=0.55  modeA=161  modeB=239

=== final 10 generator samples ===
  G(z) = -0.30
  G(z) = -0.33
  G(z) = -0.02
  G(z) = +1.76
  G(z) = +2.28
  G(z) = -2.26
  G(z) = -0.36
  G(z) = -0.26
  G(z) = -2.47
  G(z) = +0.23
```

逐段解读：

- **第 100–400 步：模式崩溃**。几乎所有样本都在负半轴（modeB 最低只剩 1/400），正峰被"饿死"。注意此时 `D(real)` 与 `D(fake)` 都在 0.5 附近——D 很弱，它还没学会"正半轴缺假样本"这件事，所以也没有推动 G 去覆盖正峰。这印证了讲义的话："The discriminator stops correcting it because it's never seen as a fake."
- **第 500–800 步：逐渐恢复**。`D(real)` 慢慢升到 0.57–0.59、`D(fake)` 低于它，说明 D 开始找到真假差异，梯度把 G 的一部分输出推向正峰，两个模式的计数趋于平衡。
- **最后的 10 个样本：漏网之鱼**。6 个样本落在 `-0.36 ~ +0.23` 之间，这是真实数据几乎不存在的区域。我按 `main()` 完全相同的过程复现最终模型、另取 2000 个样本测得：**35.4%** 的生成样本落在 `|x| < 1`，真实数据只有约 0.5%；生成分布与真实分布的一维 W1 距离约 0.88。而 step 800 那一行的 modeA/modeB（161/239）看起来"很健康"——因为检测器只看符号。
- **为什么 G 会"架桥"**：G 是 `z` 的连续函数，要把一团连续的高斯噪声分成两个分离的峰，网络需要在 `z` 空间里形成很陡的过渡；16 个隐藏单元、800 步 SGD 还做不到，于是一部分 `z` 被映射到中间。这也是真实 GAN 中"模式之间出现怪异插值样本"的一维版本。
- 讲义说代码能展示"模式崩溃 + 梯度消失"两种失败。本次运行清楚地展示了前者；D 始终不强（`D(real)` 最高 0.59），没有出现梯度消失。

---

## 7. 动手改一改

1. **调学习率比**（讲义练习 1）：把 `d_lr` 改成 `5 * g_lr`（即 0.1），观察 `D(real)`、`D(fake)` 是否拉开、模式计数如何变化。（我用相同设置但不打印监控的版本试过一次，在这个种子和 800 步内 D 并没有强到饱和——实验结论要以你自己的运行为准。）
2. **换成饱和损失**：把 `update_g` 里的 `dL_dpre2 = p - 1.0` 改成 `dL_dpre2 = -p`，对比训练前期 G 的学习速度。
3. **更好的分布指标**：写 `wasserstein_1d(a, b)`（排序后逐对相减取平均）和 `gap_fraction(xs)`（`|x| < 1` 的比例），加进每 100 步的日志里，看它们与 modeA/modeB 讲述的故事有何不同。
4. **给 D 输入加噪声**：在 `update_d` 里对真假样本都加 `rng.gauss(0, 0.1)`，观察早期模式崩溃是否缓解。
5. **加大容量 / 训练更久**：把 `hidden` 改成 32、步数改成 3000，看低密度区的"桥"是否变窄。
6. **进阶**：按讲义练习 2 改成 WGAN（去掉 sigmoid、真样本 `dL_dpre2 = -1`、假样本 `+1`、G 步 `-1`、D 权重裁剪到 ±0.01）。只改这些时训练几乎不动——想想为什么，再试着每个 G 步训练 5 次 D、或放宽裁剪范围。

---

## 8. 常见坑

- **D 步把梯度传给 G**：D 步必须把假样本当常数（这里传的是数值；PyTorch 里要 `fake.detach()`），否则 D 的损失会"帮倒忙"地更新 G。
- **G 步顺手更新了 D**：G 步只读 D，绝不能写 D；PyTorch 里要分开两个优化器，并在每步前 `zero_grad()`。
- **sigmoid 溢出**：朴素的 `1/(1+exp(-x))` 在大负数时溢出；用分段写法或在 logit 上直接算 BCE。
- **只看 `D(real)` / `D(fake)` 的均值**：它们接近 0.5 不代表 G 学好了，可能只是 D 太弱，或者平均值掩盖了局部的大偏差。
- **只按"覆盖了几个模式"评估**：会漏掉落在模式之间的伪样本；要配合分布距离（W1、FID）或 precision 指标。
- **`[[0.0] * c] * r` 初始化梯度矩阵**：所有行共享同一个列表，累加一行等于累加所有行。本代码用推导式正确地避开了这个坑。
