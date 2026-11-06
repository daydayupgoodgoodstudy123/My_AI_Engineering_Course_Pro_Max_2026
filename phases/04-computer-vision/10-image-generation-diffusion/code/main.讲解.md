# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 10 节 图像生成 — Diffusion Models ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数；有 GPU 自动用 `cuda`） ｜ **依赖**：`numpy`、`torch`（`torch.nn`、`torch.nn.functional`、`torch.utils.data`）、标准库 `math`；无需联网

---

## 1. 这份代码在考察什么

一个能在 CPU 上很快跑完的**最小 DDPM**：在 100 张 16×16 的"彩色圆"上训练 3 个 epoch，然后分别用 DDPM（200 步）和 DDIM（20 步）采样。

1. **噪声调度**：β → α → ᾱ 的预计算，以及 `ᾱ` 曲线的含义（还剩多少信号）。
2. **前向加噪的闭式公式**：`x_t = √ᾱ_t·x_0 + √(1−ᾱ_t)·ε`，一行 `q_sample` 实现，靠广播让每张图用自己的 t。
3. **时间条件网络**：正弦时间嵌入 + MLP，注入一个两层的小 U-Net。
4. **训练目标**：随机 t、随机 ε、预测 ε、MSE——整个训练步不到 10 行。
5. **两种采样器**：DDPM 祖先采样（逐步、随机）和 DDIM（跳步、确定性），以及它们和公式的逐项对应。

> 一句话：**扩散 = 学会"去掉一点点噪声"，然后把这件事重复很多次**；训练只是一个 MSE 回归，难点全在调度和采样公式里。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `linear_beta_schedule(T, beta_start, beta_end)` | 函数 | 线性 β 调度 | 噪声调度 |
| `precompute_schedule(betas)` | 函数 | 预计算 α、ᾱ、√ᾱ、√(1−ᾱ)、√(1/α)，放进字典 | 闭式公式所需的系数 |
| `q_sample(x0, t, noise, schedule)` | 函数 | 一步得到任意 t 的 `x_t` | 前向过程闭式解 |
| `timestep_embedding(t, dim)` | 函数 | 正弦/余弦时间嵌入 | 时间条件 |
| `TinyUNet` | `nn.Module` | 两层 U-Net，瓶颈处加时间偏置，输出与输入同形状的噪声预测 | `ε_θ(x_t, t)` |
| `train_step(...)` | 函数 | 随机 t + ε → `x_t` → 预测 ε → MSE → 更新 | DDPM 训练目标 |
| `sample_ddpm(...)` | 函数（`@torch.no_grad()`） | T 步祖先采样 | DDPM 采样 |
| `sample_ddim(...)` | 函数（`@torch.no_grad()`） | 在时间步子序列上确定性采样（可设 η） | DDIM 采样 |
| `synthetic_circles(...)` | 函数 | 16×16、[-1,1] 范围的黑底彩色圆 | 合成数据 |
| `main()` | 演示入口 | T=200 调度、训练 3 个 epoch、两种采样 | — |

数据流：训练时 `x0 → q_sample(x0, t, ε) → x_t → TinyUNet(x_t, t) → ε̂ → MSE(ε̂, ε)`；采样时 `x_T ~ N(0,I) → [TinyUNet → 更新公式] × 步数 → x_0`。

---

## 3. 逐段精讲

### 3.1 噪声调度：一次预计算，处处查表

```python
def linear_beta_schedule(T=1000, beta_start=1e-4, beta_end=2e-2):
    return torch.linspace(beta_start, beta_end, T)


def precompute_schedule(betas):
    alphas = 1.0 - betas
    alphas_cumprod = torch.cumprod(alphas, dim=0)
    return {
        "betas": betas,
        "alphas": alphas,
        "alphas_cumprod": alphas_cumprod,
        "sqrt_alphas_cumprod": torch.sqrt(alphas_cumprod),
        "sqrt_one_minus_alphas_cumprod": torch.sqrt(1.0 - alphas_cumprod),
        "sqrt_recip_alphas": torch.sqrt(1.0 / alphas),
    }
```

| 字典键 | 符号 | 用在哪里 |
|--------|------|---------|
| `betas` | `β_t` | DDPM 采样的噪声标准差 `√β_t` 和系数 `β_t/√(1−ᾱ_t)` |
| `alphas` | `α_t = 1 − β_t` | 中间量 |
| `alphas_cumprod` | `ᾱ_t = ∏ α_s` | DDIM |
| `sqrt_alphas_cumprod` | `√ᾱ_t` | `q_sample` 的信号系数 |
| `sqrt_one_minus_alphas_cumprod` | `√(1−ᾱ_t)` | `q_sample` 的噪声系数、DDPM 系数 |
| `sqrt_recip_alphas` | `1/√α_t` | DDPM 均值 |

- `torch.cumprod(alphas, dim=0)`：累乘，`ᾱ_t = α_0·α_1·…·α_t`。
- **为什么预计算**：训练和采样时只需按下标取值（"gather by index"），不用每次重新累乘。
- **下标约定**：代码中 t 取 `0..T−1`，下标 0 对应论文里的第 1 步；讲义伪代码写的是 `1..T`，两者只差一个偏移。
- `main()` 用的是 `T=200`、`beta_end=0.04`（为了少步数也能把信号破坏得差不多）。用 NumPy 按同一公式计算：`ᾱ` 在 t = 0 / 50 / 100 / 150 / 199 时约为 0.9999 / 0.770 / 0.357 / 0.099 / 0.0172。最后一步仍保留 `√0.0172 ≈ 0.13` 倍的信号，并非纯噪声（测验 Q3）。

### 3.2 `q_sample`：闭式前向加噪

```python
def q_sample(x0, t, noise, schedule):
    sqrt_a = schedule["sqrt_alphas_cumprod"].to(x0.device)[t].view(-1, 1, 1, 1)
    sqrt_one_minus_a = schedule["sqrt_one_minus_alphas_cumprod"].to(x0.device)[t].view(-1, 1, 1, 1)
    return sqrt_a * x0 + sqrt_one_minus_a * noise
```

- 就是讲义的 `x_t = √ᾱ_t·x_0 + √(1−ᾱ_t)·ε`。
- `.to(x0.device)`：调度张量默认在 CPU 上，先搬到与数据相同的设备，避免 GPU 训练时报设备不一致。（每次调用都搬一次有少量开销，生产代码通常在初始化时就把调度放到目标设备上。）
- `[t]`：`t` 是长度为 B 的整数张量，花式索引得到 `(B,)`，每张图一个系数。
- `.view(-1, 1, 1, 1)`：变成 `(B,1,1,1)`，与 `(B,C,H,W)` 广播相乘。漏掉它时 `(B,)` 会和最后一维 W 对齐广播——当 `B == W`（本例 batch 16、图宽 16！）时**不会报错**，却是完全错误的结果。这是本文件最隐蔽的潜在 bug 场景。
- 由于 `√ᾱ² + √(1−ᾱ)² = 1`，单位方差的数据加噪后方差仍为 1（variance preserving）。

### 3.3 `timestep_embedding`：正弦时间嵌入

```python
def timestep_embedding(t, dim=64):
    half = (dim + 1) // 2
    freqs = torch.exp(-math.log(10000) * torch.arange(half, device=t.device) / half)
    args = t[:, None].float() * freqs[None]
    emb = torch.cat([args.sin(), args.cos()], dim=-1)
    return emb[:, :dim]
```

- `freqs[k] = 10000^(−k/half)`：从 1 到约 1/10000 的一组几何级数频率，与 Transformer 正弦位置编码完全相同。`exp(−log(10000)·k/half)` 只是 `10000^(−k/half)` 的数值写法。
- `t[:, None] * freqs[None]`：`(B,1) × (1,half)` 广播成 `(B,half)`，每个时间步乘以每个频率。
- `torch.cat([sin, cos], dim=-1)`：拼成 `(B, 2·half)`。
- `half = (dim + 1) // 2` 与 `emb[:, :dim]`：讲义版本是 `dim // 2`，dim 为奇数时会少一维；这里向上取整再截断，保证输出正好 `dim` 维。`dim=64` 时两者等价。
- 好处：相邻 t 的嵌入相近（平滑），任意 t 都有唯一编码，维度与 T 无关（测验 Q5）。

### 3.4 `TinyUNet`：两层 U-Net + 时间偏置

```python
class TinyUNet(nn.Module):
    def __init__(self, img_channels=3, base=16, t_dim=64):
        super().__init__()
        self.t_mlp = nn.Sequential(
            nn.Linear(t_dim, base * 4),
            nn.SiLU(),
            nn.Linear(base * 4, base * 4),
        )
        self.t_dim = t_dim
        self.enc1 = nn.Conv2d(img_channels, base, 3, padding=1)
        self.enc2 = nn.Conv2d(base, base * 2, 4, stride=2, padding=1)
        self.mid = nn.Conv2d(base * 2, base * 2, 3, padding=1)
        self.dec1 = nn.ConvTranspose2d(base * 2, base, 4, stride=2, padding=1)
        self.dec2 = nn.Conv2d(base * 2, img_channels, 3, padding=1)
        self.time_proj = nn.Linear(base * 4, base * 2)

    def forward(self, x, t):
        t_emb = self.t_mlp(timestep_embedding(t, self.t_dim))
        t_proj = self.time_proj(t_emb)[:, :, None, None]
        h1 = F.silu(self.enc1(x))
        h2 = F.silu(self.enc2(h1)) + t_proj
        h3 = F.silu(self.mid(h2))
        d1 = F.silu(self.dec1(h3))
        d2 = torch.cat([d1, h1], dim=1)
        return self.dec2(d2)
```

`base=16`、输入 `(B, 3, 16, 16)` 时：

| 步骤 | 形状 | 说明 |
|------|------|------|
| `t_emb` | `(B, 64)` | 正弦嵌入 → `Linear → SiLU → Linear` |
| `t_proj` | `(B, 32, 1, 1)` | 投影到瓶颈通道数，再补两个空间维 |
| `h1` | `(B, 16, 16, 16)` | 编码第 1 级 |
| `h2` | `(B, 32, 8, 8)` | 步长 2 下采样 + **时间偏置**（广播到每个位置） |
| `h3` | `(B, 32, 8, 8)` | 瓶颈 |
| `d1` | `(B, 16, 16, 16)` | 转置卷积上采样 |
| `d2` | `(B, 32, 16, 16)` | 与 `h1` 拼接（skip connection） |
| 输出 | `(B, 3, 16, 16)` | 每个像素的噪声预测 |

- 就是第 07 节 U-Net 的"迷你版"：一次下采样、一次上采样、一条 skip。输出层**没有激活函数**——噪声 ε 的取值是整个实数轴。
- `SiLU`（`x·sigmoid(x)`）是扩散模型里最常用的激活函数，平滑、无死区。
- 时间条件以"加法偏置"的方式进入：同一张图所有位置加同一个向量，等价于告诉每个通道"现在噪声有多大，你该多激进地去噪"。
- `kernel=4, stride=2, padding=1` 的卷积/转置卷积正好让尺寸减半/翻倍。
- 参数量 37,395（`t_mlp` 8,320 + 各卷积 26,995 + `time_proj` 2,080）。
- ⚠️ 简化：没有归一化层、没有残差块、没有 attention，时间只在一处注入。讲义说现代模型会在**每一级**都注入时间嵌入；真实图像要"scale up the depth and width"。

### 3.5 `train_step`：整个训练就是一个 MSE

```python
def train_step(model, x0, schedule, optimizer, device, T=1000):
    model.train()
    x0 = x0.to(device)
    bs = x0.size(0)
    t = torch.randint(0, T, (bs,), device=device)
    noise = torch.randn_like(x0)
    x_t = q_sample(x0, t, noise, schedule)
    pred = model(x_t, t)
    loss = F.mse_loss(pred, noise)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    return loss.item()
```

与讲义"训练损失"六步一一对应：取 `x_0` → 均匀采样 t（`randint` 上界不包含，所以是 `0..T−1`）→ 采样 ε（`randn_like` 自动匹配形状和设备）→ `q_sample` → 网络预测 → MSE。

- **每张图独立的 t**：一个 batch 同时覆盖多个噪声水平，梯度方差更小（测验 Q8c）。
- **为什么训练与 T 无关**：多亏闭式公式，一步训练只需一次前向，不需要真的模拟 t 步加噪。
- `main()` 调用时必须传 `T=T`（200），与调度长度一致；否则默认 `T=1000` 会让 `randint` 生成超出调度长度的下标而报错。
- 损失的参照值：网络输出全 0 时 MSE ≈ `E[ε²] = 1`；低于 1 说明网络确实学到了"从 `x_t` 中分离噪声"。

### 3.6 `sample_ddpm`：逐步祖先采样

```python
    x = torch.randn(shape, device=device)
    # ...
    for t in reversed(range(T)):
        t_batch = torch.full((shape[0],), t, dtype=torch.long, device=device)
        eps = model(x, t_batch)
        coef = betas[t] / sqrt_one_minus_a[t]
        mean = sqrt_recip_alphas[t] * (x - coef * eps)
        if t > 0:
            x = mean + torch.sqrt(betas[t]) * torch.randn_like(x)
        else:
            x = mean
    return x
```

逐项对应讲义公式 `x_{t−1} = (1/√α_t)·(x_t − β_t/√(1−ᾱ_t)·ε) + √β_t·z`：

| 代码 | 公式项 |
|------|-------|
| `sqrt_recip_alphas[t]` | `1/√α_t` |
| `coef = betas[t] / sqrt_one_minus_a[t]` | `β_t/√(1−ᾱ_t)` |
| `mean` | 后验均值 |
| `torch.sqrt(betas[t]) * torch.randn_like(x)` | `√β_t·z`（方差取 `σ_t² = β_t`） |
| `t == 0` 时 `x = mean` | 最后一步不加噪声 |

- `reversed(range(T))`：从 `T−1` 倒数到 0。
- `torch.full((B,), t)`：把标量 t 扩成一个 batch 的时间步，模型接口要求 `(B,)`。
- 每一步都要跑一次模型：`T=200` 就是 200 次前向，这正是扩散"慢"的来源。
- `model.eval()` 放在开头：本模型没有 BN/Dropout，影响不大，但这是好习惯。
- ⚠️ 没有对输出或中间的 `x̂_0` 做裁剪，欠训练时样本取值可能远超 [−1, 1]。

### 3.7 `sample_ddim`：跳步的确定性采样

```python
    ts = torch.linspace(T - 1, 0, steps + 1).long()
    for i in range(steps):
        t = int(ts[i])
        t_prev = int(ts[i + 1])
        t_batch = torch.full((shape[0],), t, dtype=torch.long, device=device)
        eps = model(x, t_batch)
        a_t = alphas_cumprod[t]
        a_prev = alphas_cumprod[t_prev]
        x0_pred = (x - torch.sqrt(1 - a_t) * eps) / torch.sqrt(a_t)
        sigma = eta * torch.sqrt((1 - a_prev) / (1 - a_t) * (1 - a_t / a_prev).clamp_min(0))
        dir_xt = torch.sqrt((1 - a_prev - sigma ** 2).clamp_min(0)) * eps
        noise = sigma * torch.randn_like(x) if eta > 0 else 0
        x = torch.sqrt(a_prev) * x0_pred + dir_xt + noise
    return x
```

每一步做三件事：

1. **估计干净图像**：由闭式公式反解 `x̂_0 = (x_t − √(1−ᾱ_t)·ε̂)/√ᾱ_t`。
2. **算"指向 x_t 的方向"**：`dir_xt = √(1 − ᾱ_prev − σ²)·ε̂`。
3. **跳到 t_prev**：`x_prev = √ᾱ_prev·x̂_0 + dir_xt + σ·z`——形式上就是"用估计的 `x_0` 和估计的噪声，按 t_prev 的噪声水平重新合成一次"。

- **时间步子序列**：`main()` 中 `steps=20, T=200`，`ts = [199, 189, …, 19, 9, 0]`（`linspace` 后 `.long()` 向零截断），模型调用 20 次，比 DDPM 的 200 次快 10 倍。
- **η**：`eta=0`（默认）时 `sigma=0`、`noise=0`，整个过程确定性；`eta=1` 时 σ 等于 DDPM 后验的标准差，对应讲义说的"recovers DDPM"。
- `.clamp_min(0)`：数值保护。理论上 `1 − ᾱ_t/ᾱ_prev ≥ 0`、`1 − ᾱ_prev − σ² ≥ 0`，但浮点误差可能让它们略小于 0，开方会得到 `nan`。
- `int(ts[i])`：把 0 维张量转成 Python 整数再索引，比讲义版直接用张量索引更清晰。
- ⚠️ **最后一步的细节**：最后一次迭代 `t_prev = 0`，`a_prev = ᾱ_0 = 0.9999`，输出的是"第 0 个时间步"的 `x`，仍含约 `0.01·ε̂` 的噪声，而不是 `x̂_0` 本身。讲义版本写了 `a_prev = ... if t_prev >= 0 else 1.0`，但 `t_prev` 永远不会是负数，那个分支走不到；本文件干脆删掉了它。更严谨的做法是最后一步令 `a_prev = 1` 或直接返回 `x0_pred`（测验 Q10b）。
- ⚠️ 第一步 `√ᾱ_199 ≈ 0.131`，`ε̂` 的误差会被放大约 7.6 倍传给 `x̂_0`；常见实现会把 `x0_pred` 裁剪到 [−1, 1]，这里没有做。

### 3.8 `synthetic_circles` 与 `main()`

```python
    T = 200
    schedule = precompute_schedule(linear_beta_schedule(T=T, beta_start=1e-4, beta_end=0.04))
    # ...
    data = synthetic_circles(num=100, size=16)
    loader = DataLoader(TensorDataset(data), batch_size=16, shuffle=True)

    model = TinyUNet(img_channels=3, base=16).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    # ...
    for epoch in range(3):
        losses = []
        for (batch,) in loader:
            losses.append(train_step(model, batch, schedule, opt, device, T=T))
        print(f"epoch {epoch}  mse {np.mean(losses):.4f}")

    s_ddpm = sample_ddpm(model, schedule, shape=(2, 3, 16, 16), T=T, device=device)
    s_ddim = sample_ddim(model, schedule, shape=(2, 3, 16, 16), steps=20, T=T, device=device)
```

- 数据与第 09 节 GAN 的合成圆相同思路，只是缩小到 16×16、半径 3–5，背景 −1、颜色在 [−0.3, 1.0]。
- 100 张图、batch 16 → 每 epoch 7 个 batch，3 个 epoch 共 21 次参数更新——只为验证管道，远不足以生成像样的圆（讲义练习 2 建议 20 个 epoch）。
- `T=200, beta_end=0.04`：相比默认的 `T=1000, beta_end=0.02`，用更少的步数、更大的 β 把信号破坏到 `ᾱ_T ≈ 0.017`，让 CPU 上的 DDPM 采样只需 200 次前向。
- 两个采样器从**不同的**随机噪声出发（各自调用 `torch.randn`），所以不能直接比较两组图；要比较 DDPM 与 DDIM，需要固定同一个初始噪声（讲义练习 2）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 预计算调度并查表 | 训练/采样都只需按下标取值 | 应在初始化时放到目标设备，避免反复 `.to()` |
| ε 预测 + MSE | 目标尺度恒定、训练稳定 | 也可用 v 预测、x₀ 预测，或加权损失 |
| 每张图独立随机 t | 梯度方差小 | 也可做重要性采样 |
| 正弦嵌入 + MLP | 平滑、与 T 无关 | — |
| 只在瓶颈注入时间 | 代码最短 | 真实模型在每个残差块注入 |
| 两层、无归一化的 U-Net | CPU 上秒级训练 | 真实模型用多级残差块 + GroupNorm + attention |
| T=200、β 到 0.04 | 采样快 | 终点 SNR 不为 0，与纯噪声起点略有不一致 |
| DDIM 不裁剪 `x̂_0` | 代码贴近公式 | 生产实现通常裁剪或做 dynamic thresholding |
| DDIM 最后一步到 `ᾱ_0` 而非 1 | 实现简单 | 残留 0.01 量级噪声；可令最后一步 `a_prev = 1` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def linear_beta_schedule(T=1000, beta_start=1e-4, beta_end=2e-2)` | 调用时可只覆盖部分参数 |
| 科学计数法字面量 | `1e-4`、`2e-2` | 即 0.0001、0.02 |
| 字典字面量 | `precompute_schedule` 的返回值 | 用键名取系数，`schedule["betas"]` |
| 整除 | `(dim + 1) // 2` | 向下取整的除法 |
| `reversed(range(T))` | DDPM 循环 | 倒序遍历 `T−1, …, 0` |
| 条件表达式 | `sigma * torch.randn_like(x) if eta > 0 else 0` | 张量与 Python 数 0 都能参与后续加法 |
| 单元素元组解包 | `for (batch,) in loader` | `TensorDataset` 每项是 `(tensor,)` |
| 列表收集 + 求均值 | `losses.append(...)`、`np.mean(losses)` | 统计一个 epoch 的平均损失 |
| 张量索引技巧 | `t[:, None]`、`freqs[None]`、`[:, :, None, None]` | `None` 插入长度为 1 的新轴，用于广播 |
| `view(-1, 1, 1, 1)` | `q_sample` | `-1` 让 PyTorch 自动推断该维大小 |
| `int(tensor)` | `t = int(ts[i])` | 把 0 维张量转成 Python 整数 |
| f-string 格式符 | `f"{float(schedule['alphas_cumprod'][0]):.4f}"` | f-string 内用单引号取字典键，外层用双引号 |
| 装饰器 | `@torch.no_grad()` | 采样函数不建计算图 |
| 类继承 + `super()` | `class TinyUNet(nn.Module)` | 继承 PyTorch 模块 |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 调度数值和参数量是确定值（已用 NumPy 按同一公式核对），其余为根据代码推出的预期：

```text
schedule: T=200  alpha_bar[0]=0.9999  alpha_bar[-1]=0.0172
params: 37,395
epoch 0  mse 0.xxxx
epoch 1  mse 0.xxxx
epoch 2  mse 0.xxxx

sampled DDPM: (2, 3, 16, 16)  range [a, b]
sampled DDIM: (2, 3, 16, 16)  range [c, d]
```

逐行解读：

- `alpha_bar[0]=0.9999`：第一步只加了 `β_0 = 1e-4` 的噪声，几乎是原图。`alpha_bar[-1]=0.0172`：200 步后信号系数 `√ᾱ ≈ 0.13`，已接近纯噪声但不是精确的纯噪声。
- `params: 37,395`：一个非常小的网络，CPU 上训练很快。
- `mse`：初始化时网络输出接近 0，MSE ≈ 1（ε 的方差）；训练中应稳步低于 1。注意不同 t 的难度差别很大，epoch 平均值会带一些随机波动。
- 采样结果：形状正确是 `(2, 3, 16, 16)`；由于只训练了 21 步且没有裁剪，`range` 很可能超出数据范围 [−1, 1]，DDIM 因为第一步 `1/√ᾱ ≈ 7.6` 的放大效应可能更明显。数值越界本身不是 bug，而是"模型还远没训练好"的信号。要真正看到圆，需要训练更多 epoch，并把样本 `(x + 1)/2` 裁剪到 [0,1] 后保存成图片。

---

## 7. 动手改一改

1. 可视化前向过程：取一张图，画出 `t ∈ {0, 50, 100, 150, 199}` 时的 `q_sample` 结果（讲义练习 1），验证最后一张"几乎"是噪声。
2. 在 `sample_ddim` 中加入 `x0_pred = x0_pred.clamp(-1, 1)`，并让最后一步 `a_prev = 1`，对比样本数值范围。
3. 把训练改为 20 个 epoch，固定同一个初始噪声 `x_T`，比较 DDPM（200 步）和 DDIM（20 步，η=0）的结果是否相似（讲义练习 2）。
4. 实现余弦调度 `cosine_beta_schedule`，替换线性调度重新训练（讲义练习 3、测验 Q11）。
5. 把时间嵌入注入到 `h1` 和 `d1` 两处（各加一个 `Linear` 投影），对比相同 epoch 下的 MSE。
6. 按 t 分桶记录训练损失（如每 50 步一个桶），画出"损失 vs 噪声水平"的曲线，观察哪段噪声水平最难。

---

## 8. 常见坑

- **广播维度没对齐**：`q_sample` 少了 `view(-1, 1, 1, 1)`，在 batch 大小恰好等于图像宽度时不报错但结果全错。
- **训练与采样的 T 不一致**：`train_step` 默认 `T=1000`，调度长度却是 200，下标会越界；换调度也必须重训。
- **下标约定混乱**：论文 t 从 1 开始，代码从 0 开始；搬公式时容易错位一步。
- **DDPM 最后一步还加噪声**：最终图像带噪点。
- **DDIM 不裁剪 `x̂_0`**：早期步的误差被 `1/√ᾱ` 放大，样本发散。
- **把 MSE 降低当作生成质量**：ε 的 MSE 与样本质量相关但不等价，最终仍要看样本和 FID。
