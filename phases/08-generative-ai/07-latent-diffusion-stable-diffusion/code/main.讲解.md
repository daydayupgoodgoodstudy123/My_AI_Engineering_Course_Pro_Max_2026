# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 07 节 潜空间扩散（Latent Diffusion）与 Stable Diffusion ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 8 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy/PyTorch

---

## 1. 这份代码在考察什么

这份代码把 Stable Diffusion 拆成了能用纯 Python 跑通的最小骨架。它要你亲手验证三件事：

1. **"潜空间"只是换了一个数据域**：用一个玩具编码器 `encode(x) = 0.5·x` 把数据映射到 `z`，然后在 `z` 上原封不动地套用第 06 节的 DDPM（同样的加噪公式、同样的噪声预测 MSE、同样的反向采样），最后 `decode` 回去。
2. **条件扩散怎么做**：把类别 one-hot 和时间步 embedding 一起拼进网络输入，网络学的是 `ε(z_t, t, c)`。
3. **Classifier-Free Guidance（CFG）**：训练时以 10% 概率把类别换成 "null 类"，推理时组合 `(1+w)·ε_c − w·ε_u`，**不用重训**就能调节条件强度。
4. **手写反向传播**：一个 2 层隐藏层的 tanh MLP 的前向、反向、SGD 更新全部手写，帮你看清 PyTorch `loss.backward()` 背后在算什么。

> 一句话：**Stable Diffusion = VAE（换数据域）+ DDPM（同一个损失）+ 条件注入 + CFG**，这份代码把每一块都缩到了一维标量。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sin_embed(t, T, dim)` | 函数 | 把整数时间步编码成 8 维正弦/余弦向量 | 时间步 embedding（与 Transformer 位置编码同源） |
| `one_hot(c, num)` | 函数 | 类别 → one-hot 向量 | 条件输入（SD 中对应文本 embedding） |
| `NULL_CLASS = 2` | 常量 | 第 3 个"类别"，表示"无条件" | CFG 的 null token |
| `tanh` / `tanh_grad` / `matmul` / `add` / `randn_matrix` | 工具函数 | 纯列表实现的激活、矩阵乘、初始化 | 神经网络基础算子 |
| `init_net` / `forward` / `backward` / `apply` | 函数 | 3 层 MLP 的初始化、前向、手写反传、SGD 更新 | 噪声预测网络（SD 中是 U-Net/DiT） |
| `make_schedule(T)` | 函数 | 线性 β 调度，返回 `alphas` 与累乘 `alpha_bars` | DDPM 前向加噪调度 |
| `encode` / `decode` | 函数 | `z = 0.5x`、`x = 2z` | 第一阶段 VAE 的玩具替身 |
| `sample_data(rng)` | 函数 | 从两类高斯混合（均值 ±2，std 0.4）采样 `(x, c)` | 训练数据 |
| `main()` | 函数 | 训练 4000 步 → 定义闭包 `sample(c, w)` → 扫描 `w` 打印类均值 | 两阶段流水线 + CFG 实验 |

数据流：`sample_data → encode → 加噪得 z_t → forward([z_t], t_emb, c_emb) → backward(目标 = ε) → apply`；采样时 `z ~ N(0,1) → 40 步反向（每步两次 forward 做 CFG）→ decode`。

---

## 3. 逐段精讲

### 3.1 玩具 VAE 与数据：`encode` / `decode` / `sample_data`

```python
def encode(x):
    return x * 0.5


def decode(z):
    return z * 2.0


def sample_data(rng):
    c = rng.randrange(2)
    x = rng.gauss(-2.0 if c == 0 else 2.0, 0.4)
    return x, c
```

- 数据是两团一维高斯：类别 0 在 −2 附近，类别 1 在 +2 附近，标准差 0.4。
- `encode` 把 `x` 缩到一半，于是 `z` 的两团中心在 ±1、std 0.2。`decode` 是它的精确逆。
- 这个线性映射看起来"什么也没做"，但它恰好演示了真实 SD 里 VAE 的一个关键作用：**改变数据尺度**。真实 SD 1.x 的 VAE 潜变量方差偏大，所以要再乘 `scaling_factor ≈ 0.18215` 把它拉回到单位方差附近；这里的 `0.5` 也让 `z` 的量级更接近标准正态噪声。
- ⚠️ 刻意的简化：真实 VAE 是卷积网络，会**降维**（512²×3 → 64²×4）且有损；这里维度不变、完全无损。讲义正文说它是 "identity encoder"，代码实际是 ×0.5 的线性缩放，理解成"可逆的线性编码器"即可。

### 3.2 条件信号：`sin_embed` 与 `one_hot`

```python
def sin_embed(t, T, dim=8):
    out = []
    half = dim // 2
    for i in range(half):
        freq = 1.0 / (10000 ** (i / max(half - 1, 1)))
        out.append(math.sin(t * freq))
        out.append(math.cos(t * freq))
    return out[:dim]


def one_hot(c, num):
    v = [0.0] * num
    v[c] = 1.0
    return v
```

- `sin_embed` 用 4 个频率（1、约 0.046、约 0.0022、1e-4）分别取 sin、cos，**交错**放进长度 8 的列表。高频分量区分相邻时间步，低频分量编码粗粒度位置——与 Transformer 正弦位置编码同一个思路。
- `max(half - 1, 1)` 防止 `dim = 2` 时 `half - 1 = 0` 导致除零；`out[:dim]` 保证奇数 `dim` 时长度正确。
- 参数 `T` 在函数体里**没有用到**，只是保持接口一致。
- `one_hot(c, 3)`：类别 0 → `[1,0,0]`，类别 1 → `[0,1,0]`，`NULL_CLASS = 2` → `[0,0,1]`。**null 也是一个可学习的"类别"**——这正是 SD 里"空提示词 embedding"的玩具版。

### 3.3 噪声预测网络：`init_net` 与 `forward`

```python
def init_net(x_dim, t_dim, c_dim, hidden, rng):
    return {
        "W1": randn_matrix(hidden, x_dim + t_dim + c_dim, rng),
        "b1": [0.0] * hidden,
        "W2": randn_matrix(hidden, hidden, rng),
        "b2": [0.0] * hidden,
        "W3": randn_matrix(x_dim, hidden, rng),
        "b3": [0.0] * x_dim,
    }


def forward(x_t, t_emb, c_emb, net):
    inp = x_t + t_emb + c_emb
    pre1 = add(matmul(net["W1"], inp), net["b1"])
    h1 = tanh(pre1)
    pre2 = add(matmul(net["W2"], h1), net["b2"])
    h2 = tanh(pre2)
    out = add(matmul(net["W3"], h2), net["b3"])
    return out, {"inp": inp, "h1": h1, "h2": h2}
```

- `inp = x_t + t_emb + c_emb` 中的 `+` 是**列表拼接**，不是数值相加：`[z_t]`（1）+ 8 + 3 = 长度 12。所以 `W1` 是 32×12。
- 条件注入方式是**输入拼接**——最简单的条件化。真实 SD 用 cross-attention（`Q = 图像特征，K = V = 文本 token`），讲义 Step 4 说明了这一点，但"条件 → 影响噪声预测"的本质相同。
- 网络结构：`12 → 32 (tanh) → 32 (tanh) → 1`，输出是对噪声 ε 的预测。
- 返回值里的 `cache` 字典保存反向传播需要的中间激活，就是 autograd 的"保存张量供反向使用"。
- 参数用 `dict` 存放，键名 `W1/b1/...`，方便 `backward` 和 `apply` 统一遍历。

### 3.4 手写反向传播：`backward` 与 `apply`

```python
def backward(target, out, cache, net):
    grads = {k: None for k in net}
    for part in net:
        if isinstance(net[part][0], list):
            grads[part] = [[0.0] * len(net[part][0]) for _ in net[part]]
        else:
            grads[part] = [0.0] * len(net[part])
    d_out = [2 * (a - b) for a, b in zip(out, target)]
    for i in range(len(d_out)):
        grads["b3"][i] += d_out[i]
        for j in range(len(cache["h2"])):
            grads["W3"][i][j] += d_out[i] * cache["h2"][j]
    d_h2 = [sum(net["W3"][i][j] * d_out[i] for i in range(len(d_out)))
            for j in range(len(cache["h2"]))]
    d_pre2 = [d_h2[j] * tanh_grad(cache["h2"])[j] for j in range(len(cache["h2"]))]
    # ... W2/b2、W1/b1 同理
    return grads
```

- **初始化梯度**：用 `isinstance(net[part][0], list)` 区分矩阵（列表的列表）和向量，建同形状的全 0 结构。
- `d_out = 2·(out − target)`：损失 `(out − ε)²` 对 `out` 的导数。这就是 DDPM 的"简化损失" `‖ε − ε_θ‖²`，单样本、单维度，所以不用求平均。
- 链式法则的三步重复出现：
  1. `dW = d_pre ⊗ 上一层激活`（外积），`db = d_pre`；
  2. `d_h_prev = Wᵀ · d_pre`（`d_h2` 那行对 `i` 求和，就是转置矩阵乘）；
  3. `d_pre = d_h ⊙ tanh'(pre)`，而 `tanh'(pre) = 1 − tanh²(pre) = 1 − h²`，所以 `tanh_grad` 直接接收**激活后**的 `h`，不必存 `pre`。
- `apply` 就是朴素 SGD：`w -= lr * g`，**原地修改**列表，batch size = 1。
- ⚠️ 性能小坑：`tanh_grad(cache["h2"])[j]` 写在列表推导内部，每个 `j` 都会把整个 32 维列表重算一遍，O(H) 的操作变成了 O(H²)。结果正确，但应在循环外先算一次 `g = tanh_grad(cache["h2"])`。

### 3.5 加噪调度：`make_schedule`

```python
def make_schedule(T):
    betas = [1e-4 + (0.02 - 1e-4) * t / (T - 1) for t in range(T)]
    alphas = [1 - b for b in betas]
    bars, cum = [], 1.0
    for a in alphas:
        cum *= a
        bars.append(cum)
    return alphas, bars
```

- 线性 β 从 1e-4 增到 0.02，`ᾱ_t = Π(1 − β_s)`，用一个累乘变量 `cum` 在 O(T) 内算完。
- ⚠️ **值得注意的不一致**：1e-4 → 0.02 是 DDPM 论文为 **T = 1000** 设计的取值，这里 `T = 40`，算出来 `alpha_bars[39] ≈ 0.667`。也就是说训练时最"吵"的时间步 `z_t = 0.817·z₀ + 0.577·ε`，信号仍占主导；而采样从纯 `N(0,1)` 开始，起点分布和训练分布对不上（终端 SNR 不为 0）。后果是生成的样本整体被往 0 拉（见第 6 节 `w=0` 时类均值只有 −1.68 / +1.89）。把 β 上限调到 0.2（`ᾱ_T ≈ 0.013`）就能明显缓解，见测验 Q11。

### 3.6 训练循环：潜空间 + 标签丢弃

```python
    for step in range(4000):
        x0, c = sample_data(rng)
        z0 = encode(x0)
        t = rng.randrange(T)
        eps = rng.gauss(0, 1)
        z_t = math.sqrt(alpha_bars[t]) * z0 + math.sqrt(1 - alpha_bars[t]) * eps
        use_c = NULL_CLASS if rng.random() < 0.1 else c
        c_emb = one_hot(use_c, num_classes_inc_null)
        t_emb = sin_embed(t, T, t_dim)
        out, cache = forward([z_t], t_emb, c_emb, net)
        grads = backward([eps], out, cache, net)
        apply(net, grads, 0.01)
```

这几行就是讲义说的 "The loss function is identical to Lesson 06"：

| 行 | 作用 | 与像素空间 DDPM 的区别 |
|----|------|----------------------|
| `z0 = encode(x0)` | 把数据搬到潜空间 | **唯一的新增步骤** |
| `t = rng.randrange(T)` | 均匀采样时间步 | 相同 |
| `z_t = √ᾱ·z₀ + √(1−ᾱ)·ε` | 闭式一步加噪 | 相同，只是作用在 `z` 上 |
| `use_c = NULL_CLASS if ... < 0.1` | 10% 概率丢弃条件 | CFG 需要的训练改动 |
| `backward([eps], ...)` | 目标是噪声 ε | 相同 |

- 标签丢弃让**同一套权重**同时学到 `ε(z_t, c)` 和 `ε(z_t, ∅)`，推理时才能做 CFG，不用另训一个无条件模型。
- ⚠️ 真实 SD 中 VAE 是预先训练好并冻结的，`encode` 的结果通常会预先算好缓存，以节省训练时间。

### 3.7 采样闭包：CFG + DDPM 反向一步

```python
    def sample(c_target, w):
        z = rng.gauss(0, 1)
        for t in range(T - 1, -1, -1):
            t_emb = sin_embed(t, T, t_dim)
            eps_c, _ = forward([z], t_emb, one_hot(c_target, num_classes_inc_null), net)
            eps_u, _ = forward([z], t_emb, one_hot(NULL_CLASS, num_classes_inc_null), net)
            eps_cfg = (1 + w) * eps_c[0] - w * eps_u[0]
            beta_t = 1 - alphas[t]
            mean = (z - beta_t / math.sqrt(1 - alpha_bars[t]) * eps_cfg) / math.sqrt(alphas[t])
            if t > 0:
                z = mean + math.sqrt(beta_t) * rng.gauss(0, 1)
            else:
                z = mean
        return decode(z)
```

- `sample` 定义在 `main` 内部，是一个**闭包**：直接使用外层的 `net`、`rng`、`alphas`、`T` 等变量，不用层层传参。
- 每步**两次前向**：一次用目标类别，一次用 null 类。这就是 CFG 推理成本翻倍的来源（真实实现会把两者拼成 batch 一起算）。
- `eps_cfg = (1 + w)·ε_c − w·ε_u`：`w = 0` 退化为普通条件采样；`w > 0` 沿着 `ε_c − ε_u` 方向外推。diffusers 的 `guidance_scale` 等于这里的 `1 + w`。
- 反向均值公式 `μ = (z − β_t/√(1−ᾱ_t)·ε̂) / √α_t`，方差取 `σ_t² = β_t`，与第 06 节完全相同；`t = 0` 时不再加噪。
- 最后 `decode(z)`：采样在潜空间完成，**只在最后解码一次**——这正是 SD 推理的结构（VAE 解码器只在最后跑一次）。

### 3.8 CFG 扫描

```python
    for w in [0.0, 1.0, 3.0, 7.0]:
        samples = {0: [], 1: []}
        for _ in range(200):
            c = rng.randrange(2)
            samples[c].append(sample(c, w))
        m0 = sum(samples[0]) / len(samples[0])
        m1 = sum(samples[1]) / len(samples[1])
        print(f"  w={w:.1f}: class 0 mean {m0:+.2f}  class 1 mean {m1:+.2f}")
```

- 每个 `w` 采 200 个样本，类别随机，所以每类大约 100 个（不严格相等）。
- 只统计**均值**，用来观察"引导越强，类均值是否越往外推"。更完整的实验还应看方差（多样性）——CFG 的代价正是多样性下降。
- `{m0:+.2f}`：`+` 表示正数也显示正号，便于对齐比较。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 线性 `encode/decode` 代替 VAE | 突出"扩散不关心数据原来在哪个空间" | 真实 VAE 是卷积网络，8 倍下采样、有损，还要配 `scaling_factor` |
| 一维标量数据 | 纯 Python 也能几秒跑完，结果一眼可读 | 无法体现空间结构；真实潜变量是 `C×H×W` 张量 |
| 条件用输入拼接 | 实现最简单 | SD 用 cross-attention；SD3/Flux 用 MMDiT 联合注意力 |
| null 当作第 3 个类别 | 让 CFG 的"无条件分支"有可学习的 embedding | 真实系统里是空提示词经文本编码器得到的 embedding |
| 手写反传 + 单样本 SGD | 看清梯度流 | 生产中用 autograd + AdamW + 大 batch + EMA 权重 |
| `T = 40` 沿用 T=1000 的 β 区间 | 简短、与上一节一致 | 终端 SNR 不为 0；应按 T 缩放 β 或用 cosine 调度 |
| 每步两次独立前向 | 公式和代码一一对应 | 生产中把条件/无条件拼成 batch=2 一次算完 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表乘法初始化 | `[0.0] * num`、`[0.0] * hidden` | 生成定长全零列表；元素是不可变的 float，所以安全 |
| 列表 `+` 拼接 | `inp = x_t + t_emb + c_emb` | 对列表来说 `+` 是拼接，不是逐元素相加；逐元素加要用 `add()` |
| 列表推导式 | `[math.tanh(x) for x in v]` | 一行生成新列表 |
| 嵌套列表推导 | `[[rng.gauss(0, scale) for _ in range(cols)] for _ in range(rows)]` | 生成矩阵；外层每次都新建内层列表，避免"同一行被共享" |
| `_` 占位变量 | `for _ in range(rows)` | 表示循环变量用不到 |
| 生成器表达式 + `sum` | `sum(w * xi for w, xi in zip(row, x))` | 不建中间列表的点积 |
| `zip` | `zip(out, target)` | 按位置配对两个序列 |
| 字典推导式 | `{k: None for k in net}` | 用已有字典的键生成新字典 |
| `isinstance` | `isinstance(net[part][0], list)` | 运行时区分矩阵（列表的列表）与向量 |
| `dict.items()` | `for k, v in net.items()` | 同时遍历键和值 |
| 原地修改可变对象 | `v[i][j] -= lr * grads[k][i][j]` | `apply` 不返回新对象，直接改 `net` 里的列表 |
| 条件表达式 | `NULL_CLASS if rng.random() < 0.1 else c` | 三元表达式 |
| 多返回值（元组） | `return out, {...}`；`out, cache = forward(...)`；`eps_c, _ = forward(...)` | 返回元组并解包；不需要的用 `_` 丢弃 |
| `random.Random(seed)` | `rng = random.Random(11)` | 独立的随机数生成器实例，保证可复现、不污染全局随机状态 |
| `range` 倒序 | `range(T - 1, -1, -1)` | 从 T−1 数到 0（终点 −1 不包含） |
| 闭包（嵌套函数） | `def sample(c_target, w):` 定义在 `main` 里 | 内层函数可以读取外层函数的局部变量 |
| f-string 格式符 | `f"{step+1:5d}"`、`f"{m0:+.2f}"` | `5d` 宽度 5 的整数；`+.2f` 带正负号、保留 2 位小数 |
| 模块级常量 | `NULL_CLASS = 2` | 全大写命名，约定为常量 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 8 秒）的完整输出：

```text
=== training class-conditional latent diffusion with CFG dropout ===
  step  1000
  step  2000
  step  3000
  step  4000

=== CFG sweep: per-class mean over 200 samples ===
  w=0.0: class 0 mean -1.68  class 1 mean +1.89
  w=1.0: class 0 mean -1.93  class 1 mean +2.29
  w=3.0: class 0 mean -1.75  class 1 mean +2.37
  w=7.0: class 0 mean -1.71  class 1 mean +2.39

takeaway: same DDPM loss, just running on encoded z.
          CFG scales conditioning strength without retraining.
```

逐行解读：

- **训练部分**只打印进度，不打印 loss。想看收敛可以自己累加 `(out[0] − eps)²` 每 1000 步打印一次。
- **`w=0.0`**：两类均值 −1.68 / +1.89，符号正确，说明条件生效、潜空间扩散 + 解码这条链路是通的。但两者都比真实均值 ±2 更靠近 0，主要原因是 3.5 节说的终端 SNR 不匹配（采样起点比训练时的 `z_T` "更像噪声"），再加上小网络、单样本 SGD 的拟合误差。
- **`w=1 → 7`**：class 1 的均值 +1.89 → +2.29 → +2.37 → +2.39，**单调外推并越过真实均值 +2**——这就是 CFG "把样本推向条件最典型的方向"的效果，也对应讲义练习 1 的问题"在多大的 `w` 时类均值越过真实数据均值"。
- **class 0 不单调**（−1.93 → −1.75 → −1.71）：每类约 100 个样本，统计误差约 ±0.04，解释不了这么大的波动，主要还是模型本身对 class 0 的条件/无条件预测差异学得不够好。玩具实验里 CFG 的效果不一定完美对称。
- 用 3.5 节的修正版调度（β 上限 0.2）在同一种子下重跑，得到 `w=0/1/3/7` 时 class 1 均值 +2.06 / +2.36 / +2.56 / +2.82、class 0 均值 −1.77 / −1.98 / −2.15 / −2.16，趋势变得更清晰。

---

## 7. 动手改一改

1. **扩大 `w` 的扫描范围**：改成 `[0, 1, 3, 7, 15]`，同时打印每类样本的标准差。观察"均值外推、方差缩小"的质量-多样性权衡。
2. **修正调度**：把 `0.02` 改成 `0.2`（或按 `1000 / T` 缩放整组 β），打印 `alpha_bars[-1]`，对比 `w=0` 时类均值是否更接近 ±2。
3. **去掉标签丢弃**：把 `0.1` 改成 `0.0`，再跑 `w=3`，验证没有训练过的 null 分支会让 CFG 失效。
4. **换编码器尺度**：把 `encode` 改成 `x * 5.0`、`decode` 改成 `z / 5.0`，模拟"忘了乘 scaling_factor"的情况，观察样本质量如何恶化。
5. **加 loss 监控 + 修性能坑**：在训练循环里累计 MSE 并每 500 步打印；把 `backward` 里的 `tanh_grad(...)` 提到循环外，用 `time.perf_counter()` 对比提速。
6. **（进阶）讲义练习 2**：把线性编码器换成 `tanh` MLP 编码器/解码器，先用重建损失训练它，再冻结并在新的 `z` 上重训扩散，体会"两阶段分别训练"。

---

## 8. 常见坑

- **把列表 `+` 当成向量加法**：`[1] + [2]` 得到 `[1, 2]` 而不是 `[3]`。本文件正是利用拼接来构造网络输入，逐元素加要用 `add()`。
- **CFG 约定混用**：讲义用 `(1+w)·ε_c − w·ε_u`，diffusers 用 `guidance_scale = 1 + w`。拿"甜区 3–7"去调库参数时注意差 1。
- **训练不丢弃条件却在推理时用 CFG**：`ε_u` 来自从未训练过的输入，结果不可预期。
- **调度与 T 不匹配**：照搬 T=1000 的 β 到小 T，`ᾱ_T` 远大于 0，采样起点与训练分布不一致。
- **忘记潜变量缩放**：真实 SD 中编码后乘 `scaling_factor`、解码前除以它，漏掉任何一边都会出问题。
- **在潜空间里比较"像素"指标**：采样在 `z` 空间完成，评估要先 `decode` 回数据空间（本代码 `sample` 的返回值已经解码）。
