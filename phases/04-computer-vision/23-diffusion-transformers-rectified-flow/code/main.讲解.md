# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 23 节 Diffusion Transformers 与 Rectified Flow ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，`device` 写死为 `"cpu"`） ｜ **依赖**：`numpy`、`torch`（`torch.nn`、`torch.nn.functional`）、标准库 `math`；无需联网、无需预训练权重

---

## 1. 这份代码在考察什么

SD3、FLUX 等 2026 年主流文生图模型的"心脏"可以浓缩成两句话：**去噪器是 DiT，训练目标是 rectified flow**。这份 160 行的代码把两者都从零实现了一遍：

1. **DiT 的骨架**：patch 卷积切 token → 位置编码 → 若干 Transformer 块 → 线性头 → unpatchify 还原成图。
2. **AdaLN-Zero 条件注入**：由时间步嵌入预测 `scale, shift, gate`，并零初始化，让每个块从恒等映射开始。
3. **Rectified flow 训练**：`x_t = (1-t)x₀ + tε`，回归速度 `v = ε - x₀`——和第 10 节的 DDPM 结构相同，只换了"插值方式"和"回归目标"。
4. **Euler 采样**：从纯噪声出发，`x ← x - dt·v`，比较 20 步与 4 步（"schnell-like"）的输出。
5. **张量形状功夫**：`flatten/transpose`、`view/permute/reshape` 在 patch 与图像之间来回转换，是读任何 ViT/DiT 代码的基本功。

> 一句话：**把 U-Net 换成 Transformer、把加噪日程换成直线插值**——这就是从 Stable Diffusion 1.5 到 SD3/FLUX 的核心变化。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `timestep_embedding(t, dim)` | 函数 | 把标量 t 编码成 `dim` 维正弦/余弦特征 | 时间步嵌入 |
| `AdaLNZero` | `nn.Module` | 无仿射 LayerNorm + 零初始化的线性层，输出调制后的 `h` 和 `gate` | AdaLN-Zero |
| `DiTBlock` | `nn.Module` | AdaLN → 多头自注意力 → 门控残差；AdaLN → MLP → 门控残差 | DiT 块 |
| `TinyDiT` | `nn.Module` | patch 嵌入、位置编码、时间 MLP、4 个块、输出头、unpatchify | Diffusion Transformer |
| `rectified_flow_train_step(...)` | 函数 | 采样 t 和噪声，构造 `x_t`，对速度做 MSE 并更新一步 | Rectified flow 训练 |
| `rectified_flow_sample(...)` | 函数（`@torch.no_grad()`） | 从 t = 1 到 0 的 Euler 积分 | ODE 采样 |
| `synthetic_blobs(...)` | 函数（NumPy） | 生成黑底上随机位置/半径/颜色的彩色圆斑 | 玩具数据集 |
| `main()` | 演示入口 | 打印数据形状、参数量，训练 300 步，分别用 20 步和 4 步采样 | 端到端冒烟测试 |

数据流：`synthetic_blobs` → 随机抽 batch → `rectified_flow_train_step`（内部调用 `TinyDiT(x_t, t)`）→ 训练完后 `rectified_flow_sample` 反复调用 `TinyDiT(x, t)` 生成样本。

---

## 3. 逐段精讲

### 3.1 时间步嵌入

```python
def timestep_embedding(t, dim):
    half = dim // 2
    freqs = torch.exp(-math.log(10000) * torch.arange(half, device=t.device) / half)
    args = t[:, None].float() * freqs[None]
    return torch.cat([args.sin(), args.cos()], dim=-1)
```

- 与 Transformer 的正弦位置编码同源：48 个频率 `fₖ = 10000^(-k/48)`，从 1 递减到约 1.2×10⁻⁴，分别取 sin 和 cos，拼成 96 维。
- `t[:, None] * freqs[None]`：`(N, 1) × (1, 48)` 广播成 `(N, 48)`。
- ⚠️ 尺度细节：第 10 节的 DDPM 中 t 是 0–1000 的整数步，而这里 rectified flow 的 t 在 [0, 1]。于是 `args = t·fₖ` 最大只有 1，所有频率都还没"转完一圈"，大多数维度近似是 `sin(t·fₖ) ≈ t·fₖ`、`cos ≈ 1`——嵌入基本退化成 t 的线性函数，失去了多尺度分辨率。网络仍然能读出 t，所以能训练；但生产实现（例如 FLUX 的参考代码）通常先把 t 乘以 1000 再做正弦嵌入。

### 3.2 AdaLN-Zero：零初始化的条件调制

```python
class AdaLNZero(nn.Module):
    def __init__(self, dim, cond_dim):
        super().__init__()
        self.norm = nn.LayerNorm(dim, elementwise_affine=False)
        self.mlp = nn.Linear(cond_dim, dim * 3)
        nn.init.zeros_(self.mlp.weight)
        nn.init.zeros_(self.mlp.bias)

    def forward(self, x, cond):
        scale, shift, gate = self.mlp(cond).chunk(3, dim=-1)
        h = self.norm(x) * (1 + scale.unsqueeze(1)) + shift.unsqueeze(1)
        return h, gate.unsqueeze(1)
```

- `LayerNorm(elementwise_affine=False)`：只做标准化，**没有**自己的 γ、β——仿射参数改由条件 `cond` 动态生成，这就是"adaptive" LayerNorm。
- `self.mlp(cond)` 输出 `(N, 3·dim)`，`chunk(3, dim=-1)` 切成三份各 `(N, dim)`：`scale`、`shift`、`gate`。
- `(1 + scale)`：写成 1 加偏移，零初始化时缩放因子正好是 1，不改变标准化结果。
- `unsqueeze(1)`：`(N, dim)` → `(N, 1, dim)`，同一张图的所有 token 共享一组调制参数。
- **零初始化的效果**：`scale = shift = gate = 0`，配合下面 `x + gate·(...)` 的残差，每个块初始是恒等映射。第一步反向传播时，DiT 块内部只有产生 gate 的那部分权重拿到梯度，注意力/MLP、scale/shift 以及 `time_mlp` 的梯度都是 0（块外的 `patch`、`pos`、`head` 经恒等路径正常拿到梯度，推导见测验 Q9）；从第二步起梯度才流遍全网。讲义："this stabilises deep transformer diffusion models dramatically."
- ⚠️ 与 DiT 原论文的小差别：原论文在条件向量进入调制线性层之前先过一个 SiLU，并用一个 `6·dim` 的线性层一次产生两组 (shift, scale, gate)；这里两个 `AdaLNZero` 各产生一组，数学上等价，只是少了那个 SiLU。原论文还把最后的输出层也零初始化，这里 `head` 用默认初始化。

### 3.3 DiT 块

```python
class DiTBlock(nn.Module):
    def __init__(self, dim=96, heads=3, mlp_ratio=4, cond_dim=96):
        super().__init__()
        self.adaln1 = AdaLNZero(dim, cond_dim)
        self.attn = nn.MultiheadAttention(dim, heads, batch_first=True)
        self.adaln2 = AdaLNZero(dim, cond_dim)
        self.mlp = nn.Sequential(
            nn.Linear(dim, dim * mlp_ratio),
            nn.GELU(),
            nn.Linear(dim * mlp_ratio, dim),
        )

    def forward(self, x, cond):
        h, gate1 = self.adaln1(x, cond)
        a, _ = self.attn(h, h, h, need_weights=False)
        x = x + gate1 * a
        h, gate2 = self.adaln2(x, cond)
        x = x + gate2 * self.mlp(h)
        return x
```

- 标准的 pre-norm Transformer 块，只是把 LayerNorm 换成了 AdaLN，残差前多乘一个 gate：
  - `x = x + gate₁ · Attention(AdaLN₁(x))`
  - `x = x + gate₂ · MLP(AdaLN₂(x))`
- `nn.MultiheadAttention(96, 3, batch_first=True)`：3 个头，每头 32 维；`batch_first=True` 让输入布局为 `(N, tokens, dim)`。`self.attn(h, h, h)` 三个参数分别是 Q、K、V，都用 `h` 即**自注意力**。
- `need_weights=False`：不返回注意力权重矩阵，省内存，PyTorch 也能走更快的实现；返回值第二项是 `None`，用 `_` 丢弃。
- MLP 先扩到 4 倍宽度（384）再压回，激活函数是 GELU——与 ViT 相同。
- 这里只有图像 token 和时间条件；SD3 的 MMDiT 会再加一路文本 token，两路各自做 AdaLN、QKV 投影和 MLP，但在注意力里拼在一起（讲义 "MMDiT" 一节）。

### 3.4 `TinyDiT`：patchify → 块 → unpatchify

```python
class TinyDiT(nn.Module):
    def __init__(self, image_size=16, patch_size=2, in_channels=3, dim=96, depth=4, heads=3):
        super().__init__()
        self.patch_size = patch_size
        self.image_size = image_size
        self.num_patches = (image_size // patch_size) ** 2
        self.in_channels = in_channels
        self.patch = nn.Conv2d(in_channels, dim, kernel_size=patch_size, stride=patch_size)
        self.pos = nn.Parameter(torch.zeros(1, self.num_patches, dim))
        self.time_mlp = nn.Sequential(
            nn.Linear(dim, dim * 2),
            nn.SiLU(),
            nn.Linear(dim * 2, dim),
        )
        self.blocks = nn.ModuleList([DiTBlock(dim, heads, cond_dim=dim) for _ in range(depth)])
        self.norm_out = nn.LayerNorm(dim, elementwise_affine=False)
        self.head = nn.Linear(dim, patch_size * patch_size * in_channels)
        nn.init.trunc_normal_(self.pos, std=0.02)
```

- **Patch 嵌入**：`Conv2d(3, 96, kernel_size=2, stride=2)` 等价于"把每个 2×2×3 的小块展平后乘一个线性矩阵"，16×16 的图变成 8×8 = 64 个 token。
- **位置编码**：可学习的 `(1, 64, 96)`，用截断正态（std 0.02）初始化——讲义版本是全零，`main.py` 加了这一行，避免所有位置一开始完全相同。（DiT 原论文用固定的 2D 正弦位置编码。）
- `time_mlp`：96 → 192 → 96，SiLU 激活，把正弦嵌入变成条件向量。
- `nn.ModuleList`：用列表推导创建 4 个块。必须用 `ModuleList` 而不是普通 `list`，否则这些块的参数不会注册到模型里，优化器看不到。
- `head`：每个 token 输出 `2×2×3 = 12` 个数，即这个 patch 的速度预测。
- 参数量（按层公式计算的确定值）：patch 1,248 + pos 6,144 + time_mlp 37,152 + 4 个块 × 167,328 + head 1,164 = **715,020**。

```python
    def forward(self, x, t):
        n = x.size(0)
        x = self.patch(x)
        x = x.flatten(2).transpose(1, 2) + self.pos
        t_emb = self.time_mlp(timestep_embedding(t, self.pos.size(-1)))
        for blk in self.blocks:
            x = blk(x, t_emb)
        x = self.norm_out(x)
        x = self.head(x)
        return self._unpatchify(x, n)

    def _unpatchify(self, x, n):
        p = self.patch_size
        h = w = int(self.num_patches ** 0.5)
        x = x.view(n, h, w, p, p, self.in_channels).permute(0, 5, 1, 3, 2, 4)
        x = x.reshape(n, self.in_channels, h * p, w * p)
        return x
```

形状变化（batch 32）：

| 步骤 | 形状 |
|------|------|
| 输入 `x` | `(32, 3, 16, 16)` |
| `self.patch(x)` | `(32, 96, 8, 8)` |
| `flatten(2)` → `transpose(1, 2)` → `+ pos` | `(32, 64, 96)` |
| `t_emb` | `(32, 96)` |
| 4 个 `DiTBlock` | `(32, 64, 96)` |
| `norm_out` → `head` | `(32, 64, 12)` |
| `view(n, 8, 8, 2, 2, 3)` | `(32, 8, 8, 2, 2, 3)` |
| `permute(0, 5, 1, 3, 2, 4)` | `(32, 3, 8, 2, 8, 2)`：(批, 通道, 块行, 块内行, 块列, 块内列) |
| `reshape(n, 3, 16, 16)` | `(32, 3, 16, 16)` |

- `permute` 之后张量在内存中不连续，所以最后必须用 `reshape`（必要时自动拷贝），`view` 会报错。
- `int(self.num_patches ** 0.5)` 假设图像是正方形。
- 输出与输入同形——它预测的是每个像素的速度。

### 3.5 Rectified flow 训练步

```python
def rectified_flow_train_step(model, x0, optimizer, device):
    model.train()
    x0 = x0.to(device)
    n = x0.size(0)
    t = torch.rand(n, device=device)
    epsilon = torch.randn_like(x0)
    x_t = (1 - t[:, None, None, None]) * x0 + t[:, None, None, None] * epsilon
    target_v = epsilon - x0
    pred_v = model(x_t, t)
    loss = F.mse_loss(pred_v, target_v)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    return loss.item()
```

- 每个样本独立采一个 `t ~ U(0, 1)`；`t[:, None, None, None]` 把 `(N,)` 变成 `(N, 1, 1, 1)`，与 `(N, 3, 16, 16)` 广播。
- 插值：`t = 0` 时是干净数据，`t = 1` 时是纯噪声，中间是两者的直线混合（讲义公式 `x_t = (1 - t)·x₀ + t·ε`）。
- 目标：`v = ε - x₀ = dx_t/dt`，与 t 无关、沿整条直线恒定。
- 与 DDPM 对比：结构完全一样（采时间、加噪、回归、MSE），只是 DDPM 用 `√ᾱ` 日程加噪、回归 ε；这里用直线插值、回归 v。
- 为什么损失降不到 0：网络只看到 `x_t`，不知道是哪一对 `(x₀, ε)` 产生了它，能学到的最好结果是条件期望 `E[ε - x₀ | x_t]`（测验 Q15）。

### 3.6 Euler 采样器

```python
@torch.no_grad()
def rectified_flow_sample(model, shape, steps=20, device="cpu"):
    model.eval()
    x = torch.randn(shape, device=device)
    dt = 1.0 / steps
    t = torch.ones(shape[0], device=device)
    for _ in range(steps):
        v = model(x, t)
        x = x - dt * v
        t = t - dt
    return x
```

- 从 `t = 1` 的纯噪声出发，每步沿预测速度的**反方向**走 `dt`（因为 v 指向"数据→噪声"，而我们要从噪声回到数据），走 `steps` 步到 `t = 0`。
- `@torch.no_grad()` 装饰器：采样不需要梯度。
- 每一步都要一次完整的前向，所以"步数 = 网络调用次数"——这正是少步采样值钱的原因。
- ⚠️ 浮点累减：`t = t - dt` 重复 `steps` 次，最后的 t 可能不是精确的 0（例如 `-1e-8`），不影响这里的结果；严谨的实现会用 `t = 1 - i·dt` 直接计算。
- 1 步采样的极端情况：从 `x = ε`、`t = 1` 出发，最优速度是 `ε - E[x₀]`，一步后得到 `E[x₀]`——整个数据集的平均图像。4 步虽然好一些，但没有经过蒸馏，仍会明显偏向平均、偏模糊。真正的 "schnell" 是蒸馏出来的，不是简单少走几步。

### 3.7 合成数据与主流程

```python
def synthetic_blobs(num=200, size=16, seed=0):
    rng = np.random.default_rng(seed)
    out = np.zeros((num, 3, size, size), dtype=np.float32)
    yy, xx = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    for i in range(num):
        cx, cy = rng.uniform(4, size - 4, size=2)
        r = rng.uniform(2, 4)
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 < r ** 2
        colour = rng.uniform(-1, 1, size=3)
        for c in range(3):
            out[i, c][mask] = colour[c]
    return torch.from_numpy(out)
```

- 黑底（0）上一个随机圆斑：圆心在 [4, 12)、半径 [2, 4)、RGB 各取 [-1, 1)。数值范围 [-1, 1]，与扩散模型常用的归一化一致。
- `out[i, c][mask] = colour[c]`：先取出第 i 张图第 c 个通道（一个 `(16, 16)` 视图），再用布尔掩码赋值，修改会写回 `out`。
- 我用 NumPy 跑了同样的生成（`seed=0`，结果确定）：128 张图中前景像素约占 12%，`E[x₀²] ≈ 0.039`。所以速度目标的均方值 `E[v²] = E[ε²] + E[x₀²] ≈ 1.04`——"永远预测 0"的基线 MSE 约为 1.04。

```python
    torch.manual_seed(0)
    device = "cpu"
    data = synthetic_blobs(num=128, size=16)
    # ...
    opt = torch.optim.Adam(model.parameters(), lr=3e-4)

    batch = 32
    for step in range(300):
        idx = np.random.choice(len(data), batch)
        x0 = data[idx]
        loss = rectified_flow_train_step(model, x0, opt, device)
        if step % 50 == 0:
            print(f"step {step:3d}  rf_mse {loss:.4f}")
```

- `np.random.choice(128, 32)`：有放回地抽 32 个下标；`data[idx]` 用 NumPy 整数数组索引张量。⚠️ NumPy 全局随机数没有设种子（只设了 `torch.manual_seed(0)`），所以每次运行抽到的 batch 不同，日志数值不可复现。
- 300 步、学习率 3e-4，对扩散模型来说非常短——讲义也只期望"faint blobs of colour"（淡淡的色斑）。
- 采样部分分别用 20 步和 4 步生成 4 张图，打印取值范围和形状。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 在像素空间、16×16 上训练 | CPU 可跑，无需 VAE | 生产在 VAE 潜空间（如 1024² → 128²）训练 |
| AdaLN-Zero 条件 | 便宜、稳定，DiT 论文中效果最好 | 文本条件还需要 MMDiT 联合注意力或交叉注意力 |
| 可学习位置编码 + trunc_normal | 实现简单 | DiT 原论文用 2D 正弦编码；FLUX 等用 RoPE 类位置编码 |
| t ∈ [0,1] 直接做正弦嵌入 | 与 rectified flow 的 t 定义一致 | 嵌入接近线性；生产实现常先乘 1000 |
| `t ~ U(0, 1)` | 最简单 | SD3 用偏向中间时间步的采样（如 logit-normal） |
| Euler 采样 | 一行更新，rectified flow 下 20+ 步已足够 | 可用 Heun 等高阶方法；少步需蒸馏 |
| 无 EMA、无学习率调度 | 代码短 | 生产标配 EMA 权重、warmup + 余弦/常数调度、bf16 |
| 无条件生成 | 聚焦训练目标本身 | 文生图需文本编码器（CLIP + T5）和 CFG |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 整除 | `half = dim // 2`、`image_size // patch_size` | 结果为整数 |
| 幂与开方 | `(image_size // patch_size) ** 2`、`self.num_patches ** 0.5` | `** 0.5` 开平方，再用 `int()` 取整 |
| 类继承与 `super()` | `class DiTBlock(nn.Module)`、`super().__init__()` | 注册子模块和参数 |
| `nn.ModuleList` + 列表推导 | `nn.ModuleList([DiTBlock(...) for _ in range(depth)])` | 让列表中的模块参数被正确注册 |
| 元组解包（含 `_`） | `scale, shift, gate = ....chunk(3, dim=-1)`、`a, _ = self.attn(...)` | 一次接收多个返回值 |
| 链式赋值 | `h = w = int(self.num_patches ** 0.5)` | 两个变量赋同一个值 |
| 装饰器 | `@torch.no_grad()` | 整个采样函数不记录梯度 |
| 关键字参数 | `TinyDiT(image_size=16, patch_size=2, ...)`、`need_weights=False` | 按名字传参，可读性好 |
| `None` 索引扩维 | `t[:, None]`、`freqs[None]`、`t[:, None, None, None]` | 插入大小为 1 的维度用于广播 |
| `.chunk` | `self.mlp(cond).chunk(3, dim=-1)` | 沿某维等分成若干块 |
| `view` / `permute` / `reshape` | `_unpatchify` 中 | `view` 要求内存连续；`permute` 重排维度；`reshape` 必要时会拷贝 |
| `flatten(2)` / `transpose(1, 2)` | `x.flatten(2).transpose(1, 2)` | 从第 2 维起展平；交换两个维度 |
| `nn.init` 原地初始化 | `nn.init.zeros_(...)`、`nn.init.trunc_normal_(self.pos, std=0.02)` | 下划线结尾表示原地修改 |
| 生成器表达式 + 千分位 | `f"{sum(p.numel() for p in model.parameters()):,}"` | 统计参数量并加千分位逗号 |
| f-string 格式符 | `{loss:.4f}`、`{s20.min():.2f}`、`{tuple(data.shape)}` | 控制小数位；`torch.Size` 转元组打印 |
| NumPy 布尔掩码赋值 | `out[i, c][mask] = colour[c]` | 对视图赋值会写回原数组 |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 数据生成只依赖 NumPy，已单独运行验证（形状、取值范围、前景比例、`E[x₀²]`）；参数量按层公式计算。根据代码，输出格式如下：

```text
data shape: (128, 3, 16, 16)
params: 715,020
step   0  rf_mse ?.????
step  50  rf_mse ?.????
step 100  rf_mse ?.????
step 150  rf_mse ?.????
step 200  rf_mse ?.????
step 250  rf_mse ?.????

[sample] steps=20
  samples range [?.??, ?.??]  shape (4, 3, 16, 16)
[sample] steps=4 (schnell-like)
  samples range [?.??, ?.??]  shape (4, 3, 16, 16)
```

- 前两行是确定值：数据形状 `(128, 3, 16, 16)`，参数量 `715,020`。两个 `shape` 也确定为 `(4, 3, 16, 16)`。
- **训练损失**：一开始所有 DiT 块都是恒等映射，输出头直接作用在归一化后的 patch 特征上，预测与目标不相关，第一行损失预计在 1 以上（"预测 0"的基线约 1.04，再加上随机预测本身的方差）。之后应下降到 1 以下。作为参照：若网络只学会"根据 t 把 `x_t` 逐像素乘一个系数"这种最简单的线性规则，按本数据的统计量算出的平均 MSE 约 0.31；要更低必须利用圆斑的空间结构。每一行只是单个 batch 的损失，t 是随机采的，所以曲线会抖动；NumPy 未设种子，数值也不可复现。具体数值不编造。
- **样本范围**：训练只有 300 步，样本大概率还带有明显噪声，取值范围可能超出数据的 [-1, 1]；4 步采样通常比 20 步更模糊、更接近"平均图像"（见 3.6 节）。需实际运行确认。

---

## 7. 动手改一改

1. **步数对比**（讲义练习 1）：把训练加到 2000 步，用 1、4、10、20、50 步采样，把样本存成图片对比；验证 1 步采样几乎就是数据集的平均图像。
2. **时间嵌入尺度**：把 `timestep_embedding(t, ...)` 改成 `timestep_embedding(t * 1000, ...)`，比较相同步数下的损失曲线。
3. **类别条件 + CFG**（讲义练习 2）：按测验 Q10 实现 `CondTinyDiT`，按颜色划分 10 类，用 w = 1、3、5 采样，观察颜色是否与类别一致。
4. **去掉 Zero**：把 `AdaLNZero` 的零初始化删掉（保留默认初始化），把 `depth` 加到 12，比较训练初期的稳定性。
5. **Heun 采样器**：每步先用 Euler 预测 `x'`，再在 `x'` 处求一次速度，取两次速度的平均更新 `x`；比较 10 步 Heun 与 20 步 Euler（网络调用次数相同）。
6. **按时间分桶记录损失**：把 t 分成 10 个桶分别统计 MSE，观察哪段时间步最难学。

---

## 8. 常见坑

- **采样方向写反**：v 指向"数据→噪声"，从噪声采样要 `x - dt·v`；写成 `+` 会越走越噪。
- **训练与采样的 t 约定不一致**：本节 t = 0 是数据、t = 1 是噪声；有的库（以及部分论文）约定相反，混用会完全失败。
- **`view` 用在 `permute` 之后**：内存不连续会报错，用 `reshape` 或先 `.contiguous()`。
- **普通 list 装子模块**：不用 `nn.ModuleList`，块的参数不会被优化器看到，模型"训练了个寂寞"。
- **以为少走几步就是 schnell**：没经过蒸馏的模型直接减少步数，样本会变模糊、偏向平均图像。
- **只看损失判断好坏**：rectified flow 的损失有不可约的下界，且不同 t 的难度差别很大；要看样本质量和 FID 等指标。
