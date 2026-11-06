# 测验 · Diffusion Transformers 与 Rectified Flow（Diffusion Transformers & Rectified Flow）

> **阶段 04 · 计算机视觉 · 第 23 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 从 U-Net 到 DiT | DiT 用类 ViT 的 Transformer 在（潜空间）patch 上做去噪，替代卷积 U-Net；SD3、FLUX、Z-Image、Qwen-Image 等 2026 年主流模型都不再用 U-Net |
| 2 | Patchify / Unpatchify | 用 stride = patch 的卷积把图切成 token；输出头再把每个 token 还原成 `p×p×C` 的像素块 |
| 3 | AdaLN-Zero | 由条件向量（时间步、类别/文本）预测 `scale, shift, gate`，作用在无仿射参数的 LayerNorm 之后；调制层零初始化，使每个块初始为恒等映射 |
| 4 | MMDiT 与 FLUX | MMDiT（SD3）：文本、图像两路各自权重、共享联合注意力；FLUX：前若干层双流、后若干层拼接后单流共享权重 |
| 5 | Rectified flow | `x_t = (1 - t)·x₀ + t·ε`，网络回归速度 `v = ε - x₀`；采样时从 t = 1 的噪声沿速度反向积分到 t = 0 |
| 6 | Euler 采样 | `x ← x - dt·v(x, t)`，`t ← t - dt`；轨迹接近直线，20–30 步即可，而老 DDPM 体系要 50+ 步 DDIM 甚至 1000 步 |
| 7 | 文本编码器 | SD3：两个 CLIP + T5-XXL；FLUX：CLIP-L + T5-XXL；T5-XXL 编码器约 4.7B 参数，是提示词理解提升的重要原因 |
| 8 | CFG 依然适用 | 训练时约 10% 概率丢弃条件，推理时混合有/无条件预测；rectified-flow 模型常用 guidance 3.5–5，低于 SD1.5 的 7.5 |
| 9 | 步数蒸馏 | LCM、SDXL Turbo、FLUX schnell 等把多步教师蒸馏成 1–4 步学生；生产中常同时提供"全质量"与"turbo/schnell"两个版本 |

### 核心技能（能动手做到）

- [ ] 写出 `AdaLNZero` 与 `DiTBlock`，说清零初始化后块为什么是恒等映射、第一步哪些参数有梯度
- [ ] 逐层推出 `TinyDiT` 的张量形状，并解释 `_unpatchify` 中 `view → permute → reshape` 的每一维含义
- [ ] 不看讲义写出 rectified flow 的训练步（采样 t、构造 `x_t`、速度目标、MSE）与 Euler 采样器，并手算一个一维例子
- [ ] 解释"单个样本的路径是直线，为什么 1 步采样仍然不行"，并推出 1 步 Euler 从纯噪声出发会得到什么
- [ ] 给 `TinyDiT` 加上类别条件与 classifier-free guidance（训练时随机丢弃条件、采样时混合两次预测）
- [ ] 根据画质、延迟、许可证，在 SD3.5、FLUX.1-dev、FLUX.1-schnell、Z-Image 之间做选型，并用 `diffusers` 跑通推理

---

## 二、基础自测（选择题）

**Q1.** 2024 年以后的主流文生图模型（SD3、FLUX、Z-Image）都用 DiT 取代了 U-Net 去噪器。下列哪项**最能**解释这一转变？

- A. GPU 不再支持卷积
- B. Transformer 的扩展性更可预测（与 LLM 同样的规模化规律），擅长长距离依赖，并能通过联合/交叉注意力自然地与文本编码器结合
- C. DiT 的参数量一定比 U-Net 少
- D. Transformer 不需要时间步条件

**Q2.** 一维情形下，`x₀ = 2`、`ε = -1`、`t = 0.25`。按本节的 rectified flow 定义，`x_t` 和速度目标 `v` 分别是：

- A. `x_t = 1.25`，`v = -3`
- B. `x_t = 0.25`，`v = 3`
- C. `x_t = 1.25`，`v = 3`
- D. `x_t = 1.75`，`v = -1`

**Q3.** 本节的 Euler 采样器从 `t = 1` 走到 `t = 0`。每一步正确的更新是：

- A. `x ← x + dt·v`
- B. `x ← x - dt·v`
- C. `x ← x - v`
- D. `x ← x + dt·ε`

**Q4.** `AdaLNZero` 中 `self.mlp` 的权重和偏置都初始化为 0。刚初始化的 `DiTBlock` 对输入 `x` 的输出是：

- A. 全 0
- B. `LayerNorm(x)`
- C. `x` 本身（恒等映射）
- D. 随机噪声

**Q5.** 关于 MMDiT（SD3）与 FLUX 的结构，下列说法正确的是：

- A. MMDiT 把文本 token 和图像 token 拼接后，所有层共享同一套权重
- B. MMDiT 中文本流与图像流各有一套权重，在联合注意力中交互；FLUX 前若干层是这种双流块，后面的层把两路拼接后用共享权重的单流块，以便在更深的网络中更高效
- C. FLUX 只有单流块
- D. 两者都用交叉注意力把文本注入 U-Net

**Q6.** 关于 classifier-free guidance（CFG）在 rectified-flow 模型中的使用，下列说法正确的是：

- A. Rectified flow 改变了条件机制，CFG 不再适用
- B. 训练时以约 10% 的概率丢弃文本条件，推理时用 `v = v_uncond + w·(v_cond - v_uncond)` 混合；2026 年的模型常用 w ≈ 3.5–5，低于 SD1.5 的 7.5
- C. CFG 只能用于 DDPM 的噪声预测，不能用于速度预测
- D. CFG 的 guidance scale 越大越好

**Q7.** SD3 生成 1024×1024 图像时，VAE 把图像压缩到 128×128 的潜空间，DiT 的 patch 大小为 2。送进 Transformer 的图像 token 数是：

- A. 256
- B. 1024
- C. 4096
- D. 16384

---

## 三、动手 / 代码题

**Q8.** 阅读 `TinyDiT.forward` 与 `_unpatchify`：

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

`main()` 中 `image_size=16, patch_size=2, in_channels=3, dim=96`，输入 `x` 为 `(32, 3, 16, 16)`：

1. 写出 `self.patch(x)`、`flatten(2).transpose(1, 2)` 之后、`t_emb`、`self.head(x)` 之后、`_unpatchify` 输出的形状。
2. `permute(0, 5, 1, 3, 2, 4)` 之后各维度分别代表什么？为什么最后一步用 `reshape` 而不是 `view`？

**Q9.**（原理深挖）结合 `AdaLNZero` 与 `DiTBlock`：

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

```python
    def forward(self, x, cond):
        h, gate1 = self.adaln1(x, cond)
        a, _ = self.attn(h, h, h, need_weights=False)
        x = x + gate1 * a
        h, gate2 = self.adaln2(x, cond)
        x = x + gate2 * self.mlp(h)
        return x
```

1. 在**第一次**反向传播时，下面哪些参数的梯度为 0、哪些不为 0？(a) `attn` 的权重；(b) `adaln1.mlp` 中产生 `gate` 的那部分权重；(c) `adaln1.mlp` 中产生 `scale`、`shift` 的那部分权重；(d) `TinyDiT.time_mlp` 的权重；(e) `TinyDiT.head` 的权重。
2. 既然一开始注意力和 MLP 都"没有梯度"，模型是怎么开始学习的？为什么这种初始化反而让深层 DiT 训练更稳定？
3. `scale.unsqueeze(1)` 的作用是什么？

**Q10.** 讲义练习 2 要求给模型加类别条件。请在不改动 `DiTBlock` 的前提下：

1. 写一个 `CondTinyDiT(TinyDiT)`，用 `nn.Embedding` 加入类别条件（预留一个"空类别"下标用于无条件）；
2. 写训练步：以 10% 的概率把类别替换成空类别；
3. 写带 CFG 的 Euler 采样器 `sample_cfg(model, y, shape, steps=20, w=4.0)`。

---

## 四、面试高频题

**Q11.**（基础必考）请对比 DDPM 与 rectified flow：前向过程、训练目标、采样方式分别是什么？为什么 rectified flow 能用更少的步数？

**Q12.**（原理深挖）讲讲 DiT 的结构：图像如何变成 token、时间步与文本条件如何注入、为什么用 AdaLN-Zero？MMDiT 的"联合注意力"和 SD1.5 的"交叉注意力"有什么区别？

**Q13.**（原理深挖）FLUX schnell、SDXL Turbo、LCM 这类 1–4 步模型是怎么做到的？代价是什么？

**Q14.**（工程实践）公司要上线一个文生图服务，要求可商用、单张图延迟 < 2 秒，GPU 预算有限。你会怎么选模型、设置采样参数、优化部署？

**Q15.**（追问型）面试官追问："既然 rectified flow 的插值路径是直线，那为什么不直接 1 步采样？"请从"条件路径 vs 边缘速度场"的角度回答，并说出用本节 Euler 采样器从纯噪声走 1 步会得到什么。

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义把这次转变类比为 NLP 中从 RNN 到 Transformer："both architectures solved the same problem, but transformers scaled and now dominate"。DiT 把扩散去噪变成序列建模：扩展性随参数和数据可预测地提升、全局注意力擅长长距离结构，并可通过联合/交叉注意力与 Transformer 文本编码器结合。C 不对，FLUX.1 达 12B 参数；D 不对，DiT 通过 AdaLN 注入时间步。

### Q2 — 答案：A

`x_t = (1 - 0.25)·2 + 0.25·(-1) = 1.5 - 0.25 = 1.25`；`v = ε - x₀ = -1 - 2 = -3`。验证：如果网络完美预测 `v = -3`，从 `t = 0.25` 用一步 Euler 走到 0：`x = 1.25 - 0.25·(-3) = 2 = x₀`。对**单个已知配对**来说路径确实是直线，一步就能回到数据——但网络并不知道配对，见 Q15。

### Q3 — 答案：B

`v = dx_t/dt = ε - x₀` 指向"从数据到噪声"的方向。采样是从 `t = 1`（噪声）往 `t = 0`（数据）走，`t` 每步减少 `dt`，所以 `x_{t-dt} = x_t - dt·v(x_t, t)`。代码就是 `x = x - dt * v; t = t - dt`。A 方向反了，会越走越"噪"；C 少了步长；D 与模型无关。

### Q4 — 答案：C

零初始化 → `scale = shift = gate = 0`。注意力分支：`x + 0·a = x`；MLP 分支：`x + 0·mlp(h) = x`。整个块就是恒等映射。讲义："AdaLNZero starts as an identity mapping because its MLP weights are initialised to zero. Training nudges the block away from identity; this stabilises deep transformer diffusion models dramatically." B 是 `h` 的值，但 `h` 只在被 gate 乘之后才进入残差。

### Q5 — 答案：B

讲义：MMDiT "two streams with separate weights for text and image tokens that share a joint attention"；FLUX "first N blocks double-stream like SD3, later blocks concatenate and share weights (single-stream) for efficiency at higher depth"。A 描述的是 FLUX 的单流部分而非 MMDiT；D 描述的是 SD1.5 那一代 U-Net。

### Q6 — 答案：B

讲义："Rectified flow changes the sampler, not the conditioning." CFG 只是把有条件和无条件两次预测线性外推，对噪声预测和速度预测都成立。2026 年模型常用 3.5–5，因为 rectified-flow 模型默认就更贴合提示词。D 错：guidance 过大会导致过饱和、伪影和多样性下降。另外，像 FLUX.1-schnell 这种蒸馏模型训练时就没有 CFG，讲义示例中用 `guidance_scale=0.0`。

### Q7 — 答案：C

`128 / 2 = 64`，`64 × 64 = 4096` 个图像 token（还要加上文本 token）。自注意力复杂度与 token 数的平方成正比，这就是为什么 DiT 必须在 VAE 潜空间而不是像素空间工作：像素空间 1024×1024、patch 2 会有 26 万个 token。本节 `TinyDiT` 中 16×16、patch 2 只有 64 个 token。

### Q8 — 参考答案

1. 形状（N = 32）：
   - `self.patch(x)`：`Conv2d(3, 96, kernel_size=2, stride=2)` → `(32, 96, 8, 8)`；
   - `flatten(2)` → `(32, 96, 64)`，`transpose(1, 2)` → `(32, 64, 96)`，再加 `self.pos (1, 64, 96)`（广播）——64 个 token，每个 96 维；
   - `t_emb`：`timestep_embedding(t, 96)` 为 `(32, 96)`，经 `time_mlp` 仍是 `(32, 96)`；
   - 4 个 DiT 块不改变形状 `(32, 64, 96)`；`self.head(x)` → `(32, 64, 12)`（12 = `2 × 2 × 3`）；
   - `_unpatchify` 输出 `(32, 3, 16, 16)`，与输入同形——这是速度场的预测。
2. `view(n, h, w, p, p, C)` 把每个 token 的 12 维解释为 `(块内行, 块内列, 通道)`；`permute(0, 5, 1, 3, 2, 4)` 变成 `(n, C, h, p_行, w, p_列)`；`reshape(n, C, h·p, w·p)` 时，像素行号 = `块行 × p + 块内行`、列号 = `块列 × p + 块内列`，正好把 8×8 个 2×2 小块拼回 16×16。`permute` 只改变"步长"不移动数据，结果在内存中**不连续**，`view` 要求连续内存会报错；`reshape` 会在必要时自动复制成连续张量。（另：这个模型的参数量为 715,020，是由结构决定的确定值。）

### Q9 — 参考答案

1. 第一次反向传播时 `scale = shift = gate = 0`：
   - (a) `attn` 权重：**0**。注意力输出 `a` 只以 `gate1·a` 的形式进入残差，`∂L/∂a = gate1 · ∂L/∂x = 0`。MLP 分支同理。
   - (b) 产生 `gate` 的权重：**不为 0**。`∂L/∂gate1 = a · ∂L/∂x`，`a` 不为 0，所以 gate 那部分权重（和偏置）能拿到梯度。
   - (c) 产生 `scale`、`shift` 的权重：**0**。它们只影响 `h`，而 `h` 只经由 `a`（再乘 gate = 0）影响输出。
   - (d) `time_mlp`：**0**。条件向量只通过 `self.mlp(cond)` 进入，`∂L/∂cond = Wᵀ · ∂L/∂(scale, shift, gate)`，而 `W` 全为 0。
   - (e) `head`：**不为 0**。块是恒等映射，`head` 直接作用在 `LayerNorm(patch(x) + pos)` 上；`patch` 与 `pos` 也通过这条恒等路径拿到梯度。
2. 第一步更新后，gate 权重变为非零（Adam 第一步对每个参数的更新量约为学习率量级），从第二步起 `gate ≠ 0`，梯度开始流向注意力、MLP、scale/shift 和 `time_mlp`。好处：每个块从恒等映射出发，深层网络在训练初期等价于一个浅网络，不会因为几十层随机残差分支叠加而让激活和梯度爆炸；网络再逐步"打开"每个块的贡献。这与 ResNet 中把残差分支最后一层 BN 的 γ 初始化为 0 是同一个思想。
3. `self.mlp(cond)` 的输出是 `(N, dim)`，而 `x` 是 `(N, tokens, dim)`。`unsqueeze(1)` 变成 `(N, 1, dim)`，让同一个样本的所有 token 共享同一组 scale/shift/gate（条件是整张图的，不是逐 token 的），通过广播作用到每个 token。

### Q10 — 参考答案

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class CondTinyDiT(TinyDiT):
    def __init__(self, num_classes=10, **kwargs):
        super().__init__(**kwargs)
        dim = self.pos.size(-1)
        self.num_classes = num_classes
        self.class_emb = nn.Embedding(num_classes + 1, dim)   # 下标 num_classes 为"空类别"

    def forward(self, x, t, y):
        n = x.size(0)
        x = self.patch(x)
        x = x.flatten(2).transpose(1, 2) + self.pos
        cond = self.time_mlp(timestep_embedding(t, self.pos.size(-1))) + self.class_emb(y)
        for blk in self.blocks:
            x = blk(x, cond)
        x = self.head(self.norm_out(x))
        return self._unpatchify(x, n)


def cond_train_step(model, x0, y, optimizer, p_uncond=0.1):
    model.train()
    n = x0.size(0)
    t = torch.rand(n)
    eps = torch.randn_like(x0)
    x_t = (1 - t[:, None, None, None]) * x0 + t[:, None, None, None] * eps
    drop = torch.rand(n) < p_uncond                                   # 约 10% 丢弃条件
    y_in = torch.where(drop, torch.full_like(y, model.num_classes), y)
    loss = F.mse_loss(model(x_t, t, y_in), eps - x0)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    return loss.item()


@torch.no_grad()
def sample_cfg(model, y, shape, steps=20, w=4.0):
    model.eval()
    x = torch.randn(shape)
    null = torch.full_like(y, model.num_classes)
    dt = 1.0 / steps
    t = torch.ones(shape[0])
    for _ in range(steps):
        v_c = model(x, t, y)
        v_u = model(x, t, null)
        v = v_u + w * (v_c - v_u)          # CFG 外推
        x = x - dt * v
        t = t - dt
    return x
```

要点：

- 类别向量与时间向量**相加**作为条件，与 DiT 原论文的做法一致；讲义练习说"concatenating"也可以，但要相应修改 `cond_dim`。
- 由于 AdaLN 的调制层零初始化，类别条件同样从"无影响"开始逐步学会。
- CFG 每步要两次前向，推理成本翻倍；实际中常把有条件和无条件拼成一个 batch 一次算完。
- 数据侧需要给 `synthetic_blobs` 生成标签（例如按颜色把 10 种颜色作为 10 类）。

### Q11 — 参考回答要点

- **DDPM**：前向是按噪声日程逐步加噪的马尔可夫链/SDE，`x_t = √ᾱ_t·x₀ + √(1-ᾱ_t)·ε`；网络预测噪声 ε；反向是另一个随机过程，原始采样需要上千步，DDIM 等确定性采样也要几十步。
- **Rectified flow**：定义数据与噪声之间的**直线插值** `x_t = (1-t)x₀ + tε`；网络回归速度 `v = ε - x₀`（MSE）；采样是解一个 ODE，从 t = 1 向 t = 0 积分，Euler 即可。
- **为什么步数少**：学到的轨迹更接近直线，直线用大步长积分误差小；讲义：典型 20–30 步 Euler，而老体系 50+ 步 DDIM；再蒸馏可到 1–4 步。
- **联系**：二者都是"把噪声变成数据"的连续时间模型，训练目标都是回归某个量（ε 或 v）；rectified flow 是 flow matching 的一种特例，SD3 称之为 Rectified Flow Matching。
- **加分点**：SD3 论文还研究了训练时 t 的采样分布（偏向中间时间步，如 logit-normal 采样）以改善效果；CFG 完全兼容。

### Q12 — 参考回答要点

- **Token 化**：VAE 编码到潜空间 → `Conv2d(kernel=p, stride=p)` 切 patch → 加位置编码 → 一串 token；输出端线性头 + unpatchify 还原。
- **条件注入**：时间步走正弦嵌入 + MLP；类别/池化文本向量加到同一个条件向量上；AdaLN 从条件向量预测每个块的 `scale, shift, gate`。
- **为什么 AdaLN-Zero**：比在 token 序列里额外拼条件 token 或交叉注意力更便宜；零初始化让每个块从恒等映射开始，深层训练稳定（见 Q9）；DiT 论文中它是几种条件方式里效果最好的。
- **MMDiT 联合注意力 vs 交叉注意力**：
  - SD1.5：图像 token 做 Q，文本 token 只做 K/V，文本表示本身在 U-Net 中不更新，信息单向流动；
  - MMDiT：文本和图像 token 拼成一个序列做自注意力，Q/K/V 都来自两种模态，但两种模态各自用一套投影和 MLP 权重；文本表示也随层更新，信息双向流动，提示词遵循和文字渲染明显更好。
- **FLUX**：先双流（保留模态差异），后单流（拼接共享权重，节省参数和计算）。

### Q13 — 参考回答要点

- **共同思想**（讲义）："distil a slow many-step model into a fast few-step model"。
- **LCM**：一致性蒸馏，学生学习"从轨迹上任意一点 `x_t` 一步预测终点 `x₀`"，使同一条轨迹上不同点的预测一致；LCM-LoRA 让已有模型获得 4 步推理能力。
- **SDXL Turbo / FLUX schnell**：讲义归为对抗式扩散蒸馏（adversarial diffusion distillation）一类，在蒸馏损失之外加判别器损失，让 1–4 步的结果足够锐利。
- **代价**：多样性下降、细节和提示词遵循度可能变差；通常把 CFG "蒸进"模型，推理时不再支持（或不需要）调 guidance（schnell 用 `guidance_scale=0.0`）；需要额外的训练成本；许可证可能与原模型不同（FLUX.1-schnell 为 Apache 2.0，FLUX.1-dev 为非商用）。
- **工程**：生产中通常同时提供全质量模型与 turbo/schnell 版本，按场景路由（预览用快模型，最终出图用慢模型）。

### Q14 — 参考回答要点

- **许可证先行**：可商用 → 讲义表中 FLUX.1-schnell（Apache 2.0）、Qwen-Image（Apache 2.0）、Z-Image（宽松许可）可选；FLUX.1-dev 为非商用；SD3.x 需看 SAI 社区许可的条款。
- **延迟**：schnell 4 步、无 CFG（单次前向/步），最容易满足 2 秒；全质量模型 20–30 步且 CFG 翻倍计算，需更强 GPU。
- **显存**：FLUX 12B 的 DiT + T5-XXL 编码器（约 4.7B）在 bf16 下需要几十 GB；手段包括 bf16、权重量化（8-bit/4-bit）、把文本编码器放到别的卡或 CPU 并缓存常用提示词的文本嵌入、模型 CPU offload（牺牲延迟）。
- **吞吐**：动态批处理、固定分辨率桶、编译优化（`torch.compile` / TensorRT）、注意力加速内核。
- **质量与安全**：采样步数和 guidance 做 A/B；加安全过滤（提示词与图像双向审核）和水印。
- **监控**：P50/P95 延迟、GPU 利用率、失败率、人工质量抽检。

### Q15 — 参考回答要点

- **条件路径是直线，边缘速度场不是**：对一个**固定配对** `(x₀, ε)`，`x_t` 确实沿直线运动、速度恒为 `ε - x₀`。但训练时成千上万条直线在空间中交叉，网络在点 `x_t` 只能学到所有经过此处的配对的**平均速度** `v*(x_t, t) = E[ε - x₀ | x_t]`。由这个平均速度场定义的 ODE 轨迹是弯曲的，所以一步积分会有很大的离散误差。
- **1 步会得到什么**：从 `t = 1` 出发时 `x₁ = ε`，它与 `x₀` 独立，所以 `v*(ε, 1) = ε - E[x₀]`。一步 Euler：`x = ε - 1·(ε - E[x₀]) = E[x₀]`——无论初始噪声是什么，都得到**数据集的平均图像**（一团模糊）。这正是"直线插值 ≠ 一步生成"的直观证明。本节代码里 `steps=4` 的"schnell-like"采样只是步数少，并没有经过蒸馏，第一步同样会被拉向平均图像，因此效果通常明显差于 20 步。
- **怎么真正做到少步**：①Reflow（Liu et al. 提出的再矫正）：用训练好的模型生成 (噪声, 样本) 配对再训练，使配对之间的路径不再交叉，轨迹更直；②蒸馏（LCM、对抗蒸馏、schnell）；③更好的求解器（高阶方法）在 10–20 步内降低误差。
- **加分点**：能指出"速度场是条件期望"这一点，也解释了为什么训练损失降不到 0——同一个 `x_t` 对应很多个可能的 `ε - x₀`。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 10 图像生成 — Diffusion Models](../../10-image-generation-diffusion/docs/zh.md)：DDPM、噪声预测、正弦时间嵌入——本节逐项替换的对象。
- [阶段 04 · 14 Vision Transformers (ViT)](../../14-vision-transformers/docs/zh.md)：patch embedding 与位置编码，DiT 的骨架。
- [阶段 07 · 02 从零实现 self-attention](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：`nn.MultiheadAttention` 背后的计算。
- [阶段 04 · 11 Stable Diffusion](../../11-stable-diffusion/docs/zh.md)：VAE 潜空间、CLIP 文本编码器、classifier-free guidance。

### 本节被哪些后续内容用到
- [阶段 08 · 13 Flow Matching 与 Rectified Flows](../../../08-generative-ai/13-flow-matching-rectified-flows/docs/zh.md)：流匹配的系统推导与 reflow。
- [阶段 08 · 07 潜空间扩散 / Stable Diffusion](../../../08-generative-ai/07-latent-diffusion-stable-diffusion/docs/zh.md) 与 [阶段 08 · 08 ControlNet、LoRA 与条件控制](../../../08-generative-ai/08-controlnet-lora-conditioning/docs/zh.md)：在潜空间模型上做条件控制与微调。
- [阶段 04 · 28 世界模型与视频扩散](../../28-world-models-video-diffusion/docs/zh.md) 与 [阶段 08 · 10 视频生成](../../../08-generative-ai/10-video-generation/docs/zh.md)：DiT + 流匹配扩展到时空 token。
- [阶段 12 · 13 Transfusion：自回归 + 扩散](../../../12-multimodal-ai/13-transfusion-autoregressive-diffusion/docs/zh.md)：把扩散目标并入统一的 Transformer。
- [阶段 08 · 14 评估：FID 与 CLIP Score](../../../08-generative-ai/14-evaluation-fid-clip-score/docs/zh.md)：讲义练习 3 中的 FID 评估。

### 延伸关键词
`DiT` · `AdaLN-Zero` · `MMDiT` · `double-stream / single-stream` · `flow matching` · `reflow` · `logit-normal timestep sampling` · `Euler / Heun ODE solver` · `classifier-free guidance` · `LCM / ADD / schnell` · `T5-XXL` · `diffusers FluxPipeline`
