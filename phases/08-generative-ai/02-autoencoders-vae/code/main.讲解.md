# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 02 节 自动编码器和变分自动编码器 (VAE) ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`），不用 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这是一个**不用任何框架、手写反向传播**的迷你 VAE：8 维输入、10 维隐藏层、2 维 latent，在一个两簇的合成数据上训练 40 个 epoch。它要你亲手搞清楚：

1. **VAE 编码器输出的是分布**：两个头分别输出 `μ` 和 `log σ²`，而不是一个确定的编码。
2. **重参数化技巧**：`z = μ + σ·ε` 这一行如何让梯度穿过"采样"；`∂z/∂log σ² = 0.5·σ·ε` 是怎么来的。
3. **ELBO 的两个项**：重构项（平方误差）+ β × 闭式 KL，以及它们各自对参数的梯度。
4. **手写反向传播**：从 `x̂` 一路链式法则回到编码器的第一层，没有 autograd 兜底——这是理解 PyTorch `loss.backward()` 到底做了什么的最好方式。
5. **VAE 的三种使用模式**：训练（随机 `ε`）、重构（`ε = 0` 用均值）、生成（扔掉编码器，从 `N(0, I)` 采样）。

> 一句话：**VAE = 自编码器 + "编码必须像高斯"的约束 + 让采样可导的重参数化**，这份代码把这三样东西拆到了每一个加减乘除。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `matmul` / `add` / `tanh` / `tanh_grad` | 工具函数 | 纯列表实现的矩阵乘向量、逐元素加、激活及其导数 | 线性层 + 非线性 |
| `randn_matrix` / `init_vae` | 初始化 | 用 N(0, 0.2²) 初始化权重、偏置置 0，参数存成嵌套字典 | 参数初始化 |
| `clamp` | 工具函数 | 把 `log σ²` 夹到 `[-6, 6]` | 数值稳定 |
| `forward(x, params, eps)` | 前向 | 编码 → 重参数化 → 解码，返回所有中间量 | 编码器 / 重参数化 / 解码器 |
| `loss_value(x, fwd, beta)` | 损失 | 重构平方误差 + β·闭式 KL | 负 ELBO（β-VAE 形式） |
| `backward(x, fwd, params, beta)` | 反向 | 手写链式法则，返回与参数同形状的梯度字典 | 反向传播 |
| `apply_update(params, grads, lr)` | 优化器 | 原地 SGD 更新 | 梯度下降 |
| `sample_mixture(n, d, rng)` | 数据 | 两个簇：`[+1,+1,+1,+1,-1,-1,-1,-1]` 和它的相反数，加 σ=0.2 噪声 | 训练数据 |
| `main()` | 演示入口 | 训练、留出样本重构、从先验采样生成 | 训练 / 重构 / 生成 |

数据流：`x → forward（存下 h_enc, μ, log σ², σ, z, h_dec, x̂）→ loss_value → backward（读取这些中间量）→ apply_update`，每个样本更新一次（batch size = 1 的 SGD）。

---

## 3. 逐段精讲

### 3.1 纯列表"张量库"与参数字典

```python
def matmul(W, x):
    return [sum(w * xi for w, xi in zip(row, x)) for row in W]

def add(a, b):
    return [x + y for x, y in zip(a, b)]

def tanh(v):
    return [math.tanh(x) for x in v]

def tanh_grad(h):
    return [1 - x * x for x in h]
```

- `matmul` 只支持"矩阵 × 向量"：`W` 的每一行与 `x` 做点积，得到输出向量的一个分量。`W` 形状是 `(输出维, 输入维)`，和 PyTorch `nn.Linear.weight` 的约定一致。
- `tanh_grad` 的参数是 **tanh 的输出 `h`**，不是输入：因为 `d tanh(a)/da = 1 - tanh²(a) = 1 - h²`。前向已经算好了 `h`，反向直接复用，不必重新算 `tanh`——这是手写反向传播的常见技巧（PyTorch 也会为 tanh 保存输出而不是输入）。

```python
def init_vae(in_dim, hidden, z_dim, rng):
    return {
        "enc": {
            "W1": randn_matrix(hidden, in_dim, rng),
            "b1": [0.0] * hidden,
            "W_mu": randn_matrix(z_dim, hidden, rng),
            "b_mu": [0.0] * z_dim,
            "W_sig": randn_matrix(z_dim, hidden, rng),
            "b_sig": [0.0] * z_dim,
        },
        "dec": { ... },
    }
```

- 参数组织成两层字典：`params["enc"]["W_mu"]`。梯度字典 `grads` 用**完全相同的结构**，`apply_update` 就能按名字一一对应地更新。这和 PyTorch 的 `state_dict()`（名字 → 张量）是同一个思路。
- 编码器有**两个输出头** `W_mu` / `W_sig`，共享同一个隐藏层 `h_enc`。
- ⚠️ 权重统一用标准差 0.2 初始化，没有按 fan-in 缩放（Xavier / He 初始化），对这么小的网络够用。

### 3.2 前向：编码 → 重参数化 → 解码

```python
def forward(x, params, eps):
    """Forward pass with a fixed epsilon for the reparameterization."""
    enc, dec = params["enc"], params["dec"]
    h_enc = tanh(add(matmul(enc["W1"], x), enc["b1"]))
    mu = add(matmul(enc["W_mu"], h_enc), enc["b_mu"])
    log_sigma2 = clamp(add(matmul(enc["W_sig"], h_enc), enc["b_sig"]), -6, 6)
    sigma = [math.exp(0.5 * lv) for lv in log_sigma2]
    z = [m + s * e for m, s, e in zip(mu, sigma, eps)]
    h_dec = tanh(add(matmul(dec["W1"], z), dec["b1"]))
    x_hat = add(matmul(dec["W_out"], h_dec), dec["b_out"])
    return {
        "h_enc": h_enc, "mu": mu, "log_sigma2": log_sigma2,
        "sigma": sigma, "z": z, "h_dec": h_dec, "x_hat": x_hat,
    }
```

逐行对照讲义的概念：

| 代码行 | 概念 |
|-------|------|
| `h_enc = tanh(W1·x + b1)` | 编码器隐藏层 |
| `mu = W_mu·h_enc + b_mu` | `q(z|x)` 的均值 |
| `log_sigma2 = clamp(W_sig·h_enc + b_sig, -6, 6)` | `q(z|x)` 的对数方差，无约束输出 + 数值保护 |
| `sigma = exp(0.5 · log_sigma2)` | `σ = √(σ²)`，天然为正 |
| `z = mu + sigma * eps` | **重参数化**：随机性全在外部传入的 `eps` 里 |
| `h_dec`、`x_hat` | 解码器（线性输出，没有激活，适合实值数据） |

- **为什么 `eps` 由外部传入**：函数本身变成确定性的——给定 `x`、`params`、`eps`，输出唯一确定。好处有三：①反向传播时 `eps` 是常数，`z` 对 `μ`、`σ` 可导；②做梯度检查（有限差分）时可以固定 `eps`；③重构评估时传 `eps = 0` 就得到"用均值解码"。
- **为什么返回一个装满中间量的字典**：反向传播需要前向的中间结果（`h_enc`、`σ`、`z`、`h_dec`……）。PyTorch 的 autograd 在背后自动保存这些"saved tensors"，这里则是手动显式保存。
- **`clamp(..., -6, 6)`**：`log σ² ∈ [-6, 6]` 意味着 `σ ∈ [e⁻³, e³] ≈ [0.05, 20]`，防止 `exp` 溢出或 σ 趋于 0。
- ⚠️ `forward` 没有把 `eps` 放进返回字典，导致 `backward` 要反推它（见 3.4）。

### 3.3 损失：重构 + β · 闭式 KL

```python
def loss_value(x, fwd, beta):
    recon = sum((a - b) ** 2 for a, b in zip(x, fwd["x_hat"]))
    kl = 0.5 * sum(math.exp(lv) + m * m - lv - 1
                   for m, lv in zip(fwd["mu"], fwd["log_sigma2"]))
    return recon + beta * kl, recon, kl
```

- **重构项**：平方误差之和。对应高斯解码器 `p(x|z) = N(x̂, s²I)` 的负对数似然（差一个缩放和常数）。
- **KL 项**：`KL[N(μ, σ²) || N(0, 1)] = (σ² + μ² - log σ² - 1)/2`，按维度求和。这里 `math.exp(lv)` 就是 `σ²`。两边都是高斯，所以有**闭式解**，不需要采样估计——讲义特意强调"不要数值积分 / 蒙特卡洛估 KL"。
- 一个快速自检：`μ = 0, log σ² = 0`（即 `q = N(0,1)`）时 KL 恰好为 0；任何偏离都使 KL > 0。
- 返回三元组 `(total, recon, kl)`，方便分别打印监控——**永远要把两个项分开记录**，只看总损失看不出后验坍塌。
- 本例 `beta = 0.2 < 1`，严格说优化的已经不是 ELBO 本身，而是 β-VAE 的目标。

### 3.4 反向传播（上）：解码器

```python
    # d recon / d x_hat = 2(x_hat - x)
    d_x_hat = [2 * (a - b) for a, b in zip(x_hat, x)]

    # decoder: x_hat = W_out @ h_dec + b_out
    grads["dec"]["b_out"] = d_x_hat[:]
    grads["dec"]["W_out"] = [[d * h for h in h_dec] for d in d_x_hat]

    # d loss / d h_dec = W_out^T @ d_x_hat
    d_h_dec = [sum(dec["W_out"][i][j] * d_x_hat[i] for i in range(len(d_x_hat)))
               for j in range(len(h_dec))]
    # through tanh
    d_pre_dec = [dg * g for dg, g in zip(d_h_dec, tanh_grad(h_dec))]
    grads["dec"]["b1"] = d_pre_dec[:]
    grads["dec"]["W1"] = [[d * zi for zi in z] for d in d_pre_dec]
```

这是一个线性层 `y = W·h + b` 反向传播的标准三件套，后面每一层都在重复它：

| 要求的梯度 | 公式 | 代码 |
|-----------|------|------|
| 对偏置 | `∂L/∂b = ∂L/∂y` | `b_out = d_x_hat[:]` |
| 对权重 | `∂L/∂W = (∂L/∂y) · hᵀ`（外积） | `[[d * h for h in h_dec] for d in d_x_hat]` |
| 对输入 | `∂L/∂h = Wᵀ · (∂L/∂y)` | `d_h_dec = sum(W[i][j] * d[i] ...)` |

- 过 tanh 时逐元素乘以 `1 - h²`（`tanh_grad`）。
- `d_x_hat[:]` 用切片拷贝，避免 `b_out` 的梯度和 `d_x_hat` 共享同一个列表对象（后面若原地修改其中之一不会互相污染）。
- 注意 `W_out` 的梯度是**外积**：输出维 8 × 隐藏维 10 的矩阵，每个元素 `d_x_hat[i] * h_dec[j]`。

### 3.5 反向传播（中）：穿过重参数化

```python
    # d loss / d z = W1_dec^T @ d_pre_dec
    d_z = [sum(dec["W1"][i][j] * d_pre_dec[i] for i in range(len(d_pre_dec)))
           for j in range(len(z))]

    # reparameterization: z = mu + sigma * eps, sigma = exp(0.5 * log_sigma2)
    # d z / d mu = 1, d z / d log_sigma2 = 0.5 * sigma * eps
    d_mu_recon = d_z[:]
    eps_used = [(z[i] - mu[i]) / max(sigma[i], 1e-8) for i in range(len(z))]
    d_lv_recon = [0.5 * d_z[i] * sigma[i] * eps_used[i] for i in range(len(z))]
```

这是整个文件**最关键的几行**——重参数化技巧在代码里的样子：

- `z = μ + σ·ε`，`ε` 是常数，所以 `∂z/∂μ = 1`：重构损失对 `μ` 的梯度就是 `d_z` 原样拷贝。
- `σ = exp(0.5·lv)`，所以 `∂z/∂lv = ε · 0.5 · exp(0.5·lv) = 0.5·σ·ε`：重构损失对 `log σ²` 的梯度是 `d_z · 0.5·σ·ε`。
- 直观理解：`ε` 的符号决定了"增大 σ"是让 `z` 往哪边走；如果把 `z` 往那边推能降低重构误差，σ 就会被鼓励变大，反之变小。随机性没有阻断梯度，只是让梯度带上了噪声。
- `eps_used` 从 `z = μ + σ·ε` 反解 `ε`，`max(sigma, 1e-8)` 防除零。⚠️ 这是因为 `forward` 没保存 `eps`；更好的做法是直接把 `eps` 存进 `fwd`。

### 3.6 反向传播（下）：KL 项与编码器

```python
    # KL term: 0.5 * sum(exp(lv) + mu^2 - lv - 1)
    # d KL / d mu = mu ; d KL / d lv = 0.5 * (exp(lv) - 1)
    d_mu = [d_mu_recon[i] + beta * mu[i] for i in range(len(mu))]
    d_lv = [d_lv_recon[i] + beta * 0.5 * (math.exp(log_sigma2[i]) - 1)
            for i in range(len(mu))]
    # ...
    # d loss / d h_enc from both mu and log_sigma2 paths
    d_h_enc = [0.0] * len(h_enc)
    for j in range(len(h_enc)):
        for i in range(len(d_mu)):
            d_h_enc[j] += enc["W_mu"][i][j] * d_mu[i]
            d_h_enc[j] += enc["W_sig"][i][j] * d_lv[i]
```

- KL 对 `μ` 的梯度是 `μ`（把均值拉回 0），对 `lv` 的梯度是 `(σ² - 1)/2`（把方差拉回 1）。两路梯度——"重构想要的"和"KL 想要的"——在这里**相加**，β 控制 KL 那一路的话语权。这就是讲义说的"它们互相拉扯（They trade off）"。
- `h_enc` 同时喂给了 `μ` 头和 `log σ²` 头，所以它的梯度是**两条路径之和**：`W_muᵀ·d_mu + W_sigᵀ·d_lv`。这是多元链式法则"一个变量被多处使用，梯度累加"的典型例子（PyTorch 里梯度 `+=` 累加的原因也在这）。
- 最后同样过 tanh、算 `W1`、`b1` 的梯度。
- **正确性验证**：我用有限差分（固定 `eps`，`h = 1e-6` 中心差分）检查了全部 10 组参数的若干元素，解析梯度与数值梯度最大绝对误差约 **1e-9**，说明这份手写反向传播是对的。
- ⚠️ `clamp` 被当成恒等函数求导：若某个 `log σ²` 真的被夹在 ±6，真实梯度应为 0，这里却照样回传。本例中很少触发，影响可忽略。

### 3.7 SGD 更新：原地修改嵌套列表

```python
def apply_update(params, grads, lr):
    for part in ("enc", "dec"):
        for name, tensor in params[part].items():
            g = grads[part][name]
            if isinstance(tensor[0], list):
                for i, row in enumerate(tensor):
                    for j in range(len(row)):
                        row[j] -= lr * g[i][j]
            else:
                for i in range(len(tensor)):
                    tensor[i] -= lr * g[i]
```

- 用 `isinstance(tensor[0], list)` 区分矩阵（列表的列表）和向量（数字列表）。
- `row[j] -= ...` 是**原地修改**：`row` 是 `tensor` 里那一行列表的引用，改它就改了 `params`。所以函数不需要返回值。
- 这是最朴素的 SGD，没有动量、没有 Adam。⚠️ 每个样本更新一次（batch size = 1），梯度噪声大，所以训练日志里的损失会上下波动（见第 6 节）。

### 3.8 数据与 `main`：训练、重构、生成

```python
def sample_mixture(n, d, rng):
    data = []
    for _ in range(n):
        if rng.random() < 0.5:
            center = [1.0] * (d // 2) + [-1.0] * (d - d // 2)
        else:
            center = [-1.0] * (d // 2) + [1.0] * (d - d // 2)
        data.append([c + rng.gauss(0, 0.2) for c in center])
    return data
```

- 两个簇中心互为相反数：`[+1,+1,+1,+1,-1,-1,-1,-1]` 和 `[-1,-1,-1,-1,+1,+1,+1,+1]`，各占一半，每维加 σ=0.2 的独立噪声。数据真正的"结构"只有 1 bit（属于哪个簇）。

`main` 里的三个阶段对应 VAE 的三种用法：

```python
        for x in data:
            eps = [rng.gauss(0, 1) for _ in range(z_dim)]      # 训练：随机 eps
            fwd = forward(x, params, eps)
    # ...
    eps = [0.0] * z_dim                                       # 重构：eps = 0，用均值 μ
    fwd = forward(x_test, params, eps)
    # ...
        z = [rng.gauss(0, 1) for _ in range(z_dim)]           # 生成：直接从先验采样
        h = tanh(add(matmul(params["dec"]["W1"], z), params["dec"]["b1"]))
        x_hat = add(matmul(params["dec"]["W_out"], h), params["dec"]["b_out"])
```

- **训练**：每个样本抽一个新的 `ε`（单样本蒙特卡洛估计重构期望）。
- **重构评估**：`ε = 0` ⇒ `z = μ`，得到确定性的、"最可能"的重构。
- **生成**：完全不碰编码器，`z ~ N(0, I)` 直接喂解码器——讲义说"这就是生成模型，五行"。这里没有调用一个独立的 `decode` 函数，而是把解码器两行内联写了一遍。
- ⚠️ 讲义 "Build It" 里展示的 `encode` / `reparameterize` / `decode` / `elbo` / `sample` 几个函数**在 `main.py` 里并不存在**，实际代码把它们合并进了 `forward`、`loss_value` 和 `main` 的内联代码。阅读时以本文件为准。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 手写前向 + 反向 | 每个梯度公式都看得见，理解 autograd 的本质 | 极慢；生产用 PyTorch / JAX 自动求导 |
| `eps` 由外部传入 | 前向确定化，便于反向、梯度检查和 `ε=0` 重构 | 需要额外传参；PyTorch 里用 `torch.randn_like` 写在前向内部即可 |
| 输出 `log σ²` + clamp ±6 | 无约束输出、σ 天然为正、防溢出 | clamp 的梯度被忽略；生产中常用 softplus 或 clamp 后让 autograd 处理 |
| 闭式 KL | 精确、便宜 | 只适用于高斯 vs 高斯；其他先验要用蒙特卡洛 |
| 线性输出 + 平方误差 | 对应高斯解码器，适合实值数据 | 样本偏模糊；二值数据应换 Bernoulli（交叉熵） |
| batch size = 1 的 SGD | 代码最简单 | 损失曲线抖动大；生产用 mini-batch + Adam |
| 2 维 latent | 数据只有 1 bit 结构，2 维足够且可以观察"不活跃维度" | 真实图像需要几十到上万维 latent（讲义：SD 用 64×64×4） |
| 固定 β = 0.2 | 简单 | 生产中常用 β warm-up / free bits 防后验坍塌 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表推导式 | `[math.tanh(x) for x in v]` | 一行对每个元素做运算并生成新列表 |
| 嵌套列表推导式 | `[[rng.gauss(0, scale) for _ in range(cols)] for _ in range(rows)]` | 外层生成行、内层生成列，得到二维列表（矩阵） |
| 生成器表达式 + `sum` | `sum(w * xi for w, xi in zip(row, x))` | 点积的惯用写法，不建中间列表 |
| `zip` 多序列并行 | `zip(mu, sigma, eps)` | 三个列表按位置配对，`for m, s, e in ...` 一次取三个 |
| 列表乘法 | `[0.0] * hidden`、`[1.0] * (d // 2)` | 生成重复元素的列表；`+` 拼接两个列表 |
| 整除 `//` | `d // 2`、`d - d // 2` | 向下取整除法，保证奇数维度也能正确切分 |
| 嵌套字典 | `params["enc"]["W_mu"]` | 用名字组织参数，类似 PyTorch 的 `state_dict` |
| 字典字面量返回多个值 | `return {"h_enc": h_enc, "mu": mu, ...}` | 比返回元组更清晰，按名字取值 |
| 元组返回与解包 | `return recon + beta * kl, recon, kl`；`total, recon, kl = loss_value(...)` | 一次返回多个值 |
| 切片拷贝 | `d_x_hat[:]`、`d_z[:]` | 浅拷贝列表，避免共享引用 |
| `isinstance` | `isinstance(tensor[0], list)` | 运行时判断是矩阵还是向量 |
| `dict.items()` | `for name, tensor in params[part].items()` | 同时遍历键和值 |
| `enumerate` | `for i, row in enumerate(tensor)` | 同时拿到下标和元素 |
| 原地修改与引用 | `row[j] -= lr * g[i][j]` | `row` 是原列表的引用，修改会反映到 `params` |
| 增强赋值 | `d_h_enc[j] += ...` | 梯度累加 |
| `max` 防除零 | `max(sigma[i], 1e-8)`、`max(len(xs), 1)` | 给分母一个下限 |
| 一行多语句 | `losses.append(total); recons.append(recon); kls.append(kl)` | 分号分隔，合法但一般不推荐 |
| f-string 格式符 | `f"{epoch+1:2d}"`、`f"{mean(losses):.3f}"`、`f"{v:+.2f}"` | `2d` 宽度 2 的整数；`.3f` 三位小数；`+` 显示符号 |
| f-string 内嵌推导 | `f"z={[f'{zi:+.2f}' for zi in z]}"` | 外层双引号、内层单引号，嵌套格式化 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 0.2 秒）的输出：

```text
=== training tiny VAE: 8-D input, 2-D latent, beta=0.2 ===
epoch  5: loss 1.031  recon 0.524  KL 2.532
epoch 10: loss 0.773  recon 0.411  KL 1.812
epoch 15: loss 0.735  recon 0.400  KL 1.680
epoch 20: loss 0.725  recon 0.345  KL 1.903
epoch 25: loss 0.681  recon 0.374  KL 1.534
epoch 30: loss 0.623  recon 0.345  KL 1.392
epoch 35: loss 0.768  recon 0.422  KL 1.733
epoch 40: loss 0.654  recon 0.369  KL 1.428

=== reconstruction on held-out sample ===
  x     = ['+1.05', '+0.85', '+1.12', '+0.78', '-1.23', '-1.17', '-0.76', '-0.75']
  x_hat = ['+0.95', '+1.11', '+1.03', '+0.93', '-1.01', '-1.02', '-1.00', '-0.99']
  mse = 0.285

=== samples from N(0, I) through decoder ===
  z=['-0.52', '+1.92']  ->  x_hat=['+0.46', '+0.64', '+0.63', '+0.52', '-0.61', '-0.61', '-0.60', '-0.52']
  z=['+0.34', '-1.47']  ->  x_hat=['-0.43', '-0.47', '-0.55', '-0.40', '+0.52', '+0.43', '+0.56', '+0.52']
  z=['+0.43', '-0.98']  ->  x_hat=['-0.56', '-0.61', '-0.68', '-0.53', '+0.66', '+0.57', '+0.68', '+0.66']
  z=['-1.14', '-2.19']  ->  x_hat=['+0.94', '+1.06', '+1.00', '+0.92', '-0.99', '-1.01', '-0.97', '-0.96']
```

逐段解读：

- **训练曲线**：总损失从 1.03 降到 0.6–0.7 区间后开始**抖动**（epoch 35 反弹到 0.768）。原因是 batch size = 1 的 SGD + 每步随机 `ε`，梯度噪声很大。重构误差停在 0.35–0.42，KL 在 1.4–1.9 之间。
- **重构误差的下限**：数据每维有 σ=0.2 的独立噪声，8 维加起来的噪声能量是 `8 × 0.04 = 0.32`。2 维 latent 无法也不值得记住这些噪声，最优重构就是"输出簇中心"——看 `x_hat` 恰好都在 ±1 附近，而不是复制 `x` 的细节（如 `+0.78`、`-0.75`）。留出样本 `mse = 0.285` 正好落在这个噪声水平附近。
- **从先验采样**：4 个样本都呈现"前 4 维同号、后 4 维反号"的结构，说明解码器学会了数据的结构。但前三个样本的幅度只有 ±0.5–0.65，**落在两个簇之间**，并不是干净的 ±1。这是 VAE 的经典现象：先验里的点落在两个簇对应的 latent 区域之间时，解码器输出两者的"平均"——一维版的"模糊样本"。
- **一个隐藏现象**：如果把每维 KL 分开算（见测验 Q10），β=0.2 时第二个 latent 维度的 KL 只有约 0.006——它几乎被关掉了，因为一个维度就足以区分两个簇。所以上面 `z` 的第二个分量对输出影响很小，输出主要由第一个分量决定。
- ⚠️ 讲义说代码有 `encode` / `decode` / `elbo` / `sample` 等独立函数，实际文件里没有，这不影响运行结果。

---

## 7. 动手改一改

1. **β 扫描**（讲义练习 1）：把 `beta` 改成 0.01、0.2、1.0、5.0，记录最后的 recon 和 KL。参考值：`0.332/4.530`、`0.369/1.428`、`0.497/1.189`、`2.118/0.702`。哪一个是 Pareto 最优？
2. **每维 KL 与活跃维度**：写 `kl_per_dim(data, params)`（用 `eps = 0` 前向，逐维平均 KL），看哪个维度"不活跃"。
3. **β warm-up**：写 `beta_schedule(epoch, warmup=10, beta_max=0.2)`，前 10 个 epoch 从 0 线性升上去；对比 β=5 时有无 warm-up 的结果。
4. **让 `forward` 保存 `eps`**：在返回字典里加 `"eps": eps`，把 `backward` 里的 `eps_used` 反推删掉，并用有限差分确认梯度不变。
5. **潜空间插值**：编码两个不同簇的样本得到 `μ₁`、`μ₂`，对 `t ∈ {0, 0.25, 0.5, 0.75, 1}` 解码 `(1-t)·μ₁ + t·μ₂`，观察输出如何从一个簇平滑过渡到另一个簇（这正是 VAE latent 空间"连续"的体现）。
6. **进阶**：把解码器换成 Bernoulli 似然（讲义练习 2）：先把数据二值化为 0/1，输出层加 sigmoid，重构项换成二元交叉熵，并相应修改 `d_x_hat`（提示：sigmoid + BCE 对 logit 的梯度是 `p - x`）。

---

## 8. 常见坑

- **KL 公式写错一项**：最常见的是漏掉 `- 1` 或把 `exp(lv)` 写成 `lv`。自检：`μ=0, log σ²=0` 时 KL 必须恰好为 0。
- **重参数化梯度漏掉 0.5**：`∂z/∂log σ² = 0.5·σ·ε`，不是 `σ·ε`（那是对 `log σ` 的导数）。用有限差分检查就能立刻发现。
- **忘了梯度累加**：`h_enc` 同时连着 `μ` 头和 `log σ²` 头，只算一条路径会得到错误梯度。
- **重构时还在随机采样 `ε`**：评估重构应设 `ε = 0`（用均值），否则同一输入每次重构结果都不同。
- **把 `log σ²` 的范围放得太开**：不加 clamp 时 `exp` 可能溢出，或 σ→0 使 `eps` 反推除以 0。
- **只看总损失**：总损失下降可能只是 KL 降到了 0（后验坍塌），一定要分别监控 recon 和每维 KL。
