# 测验 · 自动编码器和变分自动编码器（Autoencoders & Variational Autoencoders, VAE）

> **阶段 08 · 生成式 AI · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 普通自编码器（AE） | `z = encoder(x)`，`x̂ = decoder(z)`，只优化重构 MSE；编码空间没有结构，随机取点解码得到噪声——它是压缩模型，不是生成模型 |
| 2 | VAE 编码器输出分布 | 编码器输出 `μ(x)` 和 `log σ²(x)`，定义 `q(z|x) = N(μ, diag(σ²))`；输出 `log σ²` 是为了让网络输出不受约束 |
| 3 | 重参数化技巧 | 把采样写成 `z = μ + σ·ε`，`ε ~ N(0, I)`；随机性被移到与参数无关的 `ε` 上，梯度可以流过 `μ`、`σ` |
| 4 | ELBO | `log p(x) ≥ E_q[log p(x|z)] - KL[q(z|x) || p(z)]`；当 `q(z|x)` 等于真实后验时取等 |
| 5 | 损失与闭式 KL | `loss = ||x - x̂||² + β · Σᵢ (σᵢ² + μᵢ² - log σᵢ² - 1)/2`；两个高斯之间的 KL 有闭式解，不要用蒙特卡洛估 |
| 6 | β 的权衡 | β 小 → 重构好、样本清晰，但编码空间不够"高斯"；β 大 → 编码空间干净、更解耦，但样本更糊（β-VAE） |
| 7 | 后验坍塌（posterior collapse） | KL 项赢了：`q(z|x) → N(0, I)`，`z` 不再携带 `x` 的信息；对策：β 退火、free bits、对不活跃维度跳过 KL |
| 8 | 样本模糊的根源 | 高斯解码器似然 ⇔ MSE，MSE 的贝叶斯最优解是条件**均值**，多个合理数字的平均就是一个模糊的数字 |
| 9 | 生成 = 一次前向 | 推理时扔掉编码器，`z ~ N(0, I)` → 解码器；不像扩散那样迭代 |
| 10 | VAE 是潜空间扩散的第一层 | SD 1/2/XL/3、Flux 都用 VAE 做像素 ↔ latent 的转换；SD 的 VAE 把 512×512×3 压到 64×64×4；1024² 时 VAE 解码往往是显存峰值，需要 slicing / tiling，并注意 fp16 下的 NaN |

### 核心技能（能动手做到）

- [ ] 手推一维高斯 `KL[N(μ, σ²) || N(0, 1)] = (σ² + μ² - log σ² - 1)/2`，并写出它对 `μ`、`log σ²` 的梯度 `μ` 和 `(σ² - 1)/2`
- [ ] 不用 NumPy / PyTorch，手写一个单隐层 VAE 的前向和反向（包括重参数化路径），并用有限差分做梯度检查（误差 < 1e-6）
- [ ] 扫描 β（0.01 / 0.2 / 1 / 5），记录重构误差与每维 KL，识别"不活跃维度"和后验坍塌
- [ ] 区分三种用法：训练时 `ε` 随机采样；重构评估时 `ε = 0` 用均值；生成时扔掉编码器直接从 `N(0, I)` 采样
- [ ] 实现 β warm-up 调度，说明它为什么能缓解后验坍塌
- [ ] 算出 Stable Diffusion VAE 的压缩比，并能为 1024² 推理配置 VAE slicing / tiling、选对 fp16-fix 或 bf16

---

## 二、基础自测（选择题）

**Q1.** 普通自编码器即使重构 MSE 很低，也不能直接用来生成新样本，最根本的原因是：

- A. 它的重构误差还不够低
- B. 编码空间没有被约束成一个已知的、可以采样的分布，随机取一个点解码多半落在训练数据从未覆盖的"空洞"里
- C. 它没有解码器
- D. 它的编码器无法反向传播

**Q2.** VAE 中"重参数化技巧"解决的核心问题是：

- A. 让 KL 项变小
- B. 从 `q(z|x)` 采样这一步不可导；改写成 `z = μ + σ·ε` 后，随机性来自与参数无关的 `ε`，梯度能流过 `μ` 和 `σ`
- C. 让解码器输出离散值
- D. 减少推理时的计算量

**Q3.** 二维 latent，编码器输出 `μ = [1, 0]`，`log σ² = [0, ln 4]`。`KL[q(z|x) || N(0, I)]` 约等于：

- A. 0.50
- B. 1.31
- C. 2.00
- D. 0.81

**Q4.** 训练 VAE 时观察到：所有 latent 维度的 KL 都接近 0，重构误差一直很高，解码器输出几乎与输入无关。最可能的原因和对策是：

- A. 过拟合；增加 dropout
- B. 后验坍塌；从 β≈0 开始退火、使用 free bits 或降低 β
- C. 梯度爆炸；加梯度裁剪
- D. latent 维度太大；把维度减到 1

**Q5.** 编码器为什么输出 `log σ²` 而不是直接输出 `σ`？

- A. `log σ²` 可以取任意实数，网络输出无需加约束，`exp` 之后天然为正
- B. 为了让 KL 项变成线性函数
- C. 因为 σ 必须是负数
- D. 为了减少参数量

**Q6.** VAE 生成的图像普遍偏模糊，讲义给出的根本原因是：

- A. 学习率太高
- B. 高斯解码器似然等价于 MSE 重构损失，而 MSE 的最优预测是条件均值——多个合理细节被平均成一个模糊结果
- C. latent 维度太大
- D. KL 项恰好等于 0

**Q7.** Stable Diffusion 的 VAE 把 512×512×3 的图像编码成 64×64×4 的 latent。总元素数的压缩比是：

- A. 8 倍
- B. 32 倍
- C. 48 倍
- D. 64 倍

**Q8.** 关于 VAE 在 Stable Diffusion / Flux 推理流水线中的角色，哪项正确？

- A. 每一步去噪都要调用一次 VAE 解码器
- B. 纯文生图只在最后解码一次；img2img / inpainting 还要先编码一次；1024² 时解码往往是整条流水线的激活显存峰值
- C. 推理时 VAE 被完全移除
- D. 它使用离散码本，输出 token 给 Transformer

---

## 三、动手 / 代码题

**Q9.** 下面是本节 `backward` 中处理重参数化的几行。请回答：
(a) `d_lv_recon` 的公式 `0.5 * d_z * sigma * eps` 是怎么来的？
(b) 为什么要用 `(z - mu) / max(sigma, 1e-8)` 反推 `eps`，有没有更简单的写法？
(c) `forward` 里对 `log_sigma2` 做了 `clamp(..., -6, 6)`，而 `backward` 完全没管这个 clamp，这会带来什么问题？

```python
    # reparameterization: z = mu + sigma * eps, sigma = exp(0.5 * log_sigma2)
    # d z / d mu = 1, d z / d log_sigma2 = 0.5 * sigma * eps
    d_mu_recon = d_z[:]
    eps_used = [(z[i] - mu[i]) / max(sigma[i], 1e-8) for i in range(len(z))]
    d_lv_recon = [0.5 * d_z[i] * sigma[i] * eps_used[i] for i in range(len(z))]

    # KL term: 0.5 * sum(exp(lv) + mu^2 - lv - 1)
    # d KL / d mu = mu ; d KL / d lv = 0.5 * (exp(lv) - 1)
    d_mu = [d_mu_recon[i] + beta * mu[i] for i in range(len(mu))]
    d_lv = [d_lv_recon[i] + beta * 0.5 * (math.exp(log_sigma2[i]) - 1)
            for i in range(len(mu))]
```

**Q10.** 保持 `main()` 的其他设置不变（`random.Random(7)`、40 个 epoch、`lr=0.01`、`z_dim=2`），只改 β，得到最后一个 epoch 的平均值以及在训练集上（`eps=0`）算出的每维 KL：

```text
beta=0.01: recon 0.332 KL 4.530 per-dim KL [3.55, 0.965]
beta=0.2:  recon 0.369 KL 1.428 per-dim KL [1.422, 0.006]
beta=1.0:  recon 0.497 KL 1.189 per-dim KL [1.219, 0.01]
beta=5.0:  recon 2.118 KL 0.702 per-dim KL [0.673, 0.005]
```

已知训练数据是两个簇（中心 `[1,1,1,1,-1,-1,-1,-1]` 和它的相反数），每维加了 σ=0.2 的独立高斯噪声。请解释：
(a) 为什么重构误差在 0.33 左右就降不下去了？
(b) 为什么 β ≥ 0.2 时第二个 latent 维度的 KL 几乎为 0？
(c) β=5 时发生了什么？哪个 β 对这份数据最"划算"？

**Q11.** 为本节代码补两个工具函数：
1. `beta_schedule(epoch, warmup=10, beta_max=0.2)`：前 `warmup` 个 epoch 让 β 从 0 线性升到 `beta_max`，之后保持不变；
2. `active_dims(data, params, threshold=0.05)`：用 `eps = 0` 前向，统计每个 latent 维度在数据集上的平均 KL，返回大于阈值的维度个数。

并把 `main()` 的训练循环改成使用 `beta_schedule`。

---

## 四、面试高频题

**Q12.**（基础必考）请推导 VAE 的 ELBO。它为什么是 `log p(x)` 的下界？什么时候取等？代码里的 `||x - x̂||²` 对应什么样的解码器似然？

**Q13.**（原理深挖）为什么需要重参数化技巧？如果不用它，还能怎么对采样操作求梯度？离散 latent 怎么办？

**Q14.**（原理深挖）什么是后验坍塌？它为什么会发生？列出至少三种缓解方法并说明原理。

**Q15.**（工程实践）Stable Diffusion 为什么要在 VAE 的 latent 空间里做扩散，而不是在像素空间？部署 1024² 的 SDXL / Flux 服务时，VAE 这一环有哪些常见的显存与数值问题，怎么处理？

**Q16.**（场景设计）你要为一个"文本 → 音乐"系统设计 tokenizer / 编码器，下游是一个 Transformer。你会选连续 VAE 还是 VQ-VAE / RVQ？上线后如何监控编码器是否健康？

**Q17.**（追问型）面试官追问："既然 VAE 生成的图很糊，为什么 2026 年所有潜空间扩散模型还要用它？不糊的办法有哪些？"

---

## 五、参考答案与解析

### Q1 — 答案：B

普通 AE 只优化重构，编码器可以把训练样本映射到编码空间里任意零散的位置，只要解码器能还原即可。于是编码空间"坑坑洼洼"，训练样本之间是大片没有被训练过的区域，随机采一个点解码得到噪声。VAE 用 KL 项把每个 `q(z|x)` 拉向 `N(0, I)`，让编码空间连续、致密，才有了"从先验采样再解码"的能力。A 错：重构再好也解决不了"从哪里采样"的问题。

### Q2 — 答案：B

"从分布里采一个数"这个操作对分布参数没有梯度。重参数化把它改写成确定性函数 `z = μ + σ·ε` 加上一个与参数无关的纯噪声 `ε`，于是 `∂z/∂μ = 1`、`∂z/∂σ = ε`，反向传播可以照常进行。它不会改变 KL 大小（A），也与推理速度无关（D）。

### Q3 — 答案：B

逐维计算 `(σ² + μ² - log σ² - 1)/2`：
- 第 1 维：`σ² = 1`，`(1 + 1 - 0 - 1)/2 = 0.5`
- 第 2 维：`σ² = 4`，`(4 + 0 - ln 4 - 1)/2 = (3 - 1.386)/2 ≈ 0.807`

合计 ≈ **1.31**。A 只算了第 1 维，D 只算了第 2 维。注意：方差偏大（σ² = 4）和均值偏移（μ = 1）都会被 KL 惩罚。

### Q4 — 答案：B

这是后验坍塌的典型症状：KL 项把 `q(z|x)` 完全压成先验，`z` 不含任何关于 `x` 的信息，解码器只能输出"平均样本"，重构误差居高不下。讲义给出的对策：β 退火（从 β=0 起步逐渐升到 1）、free bits（每维 KL 低于某个阈值时不惩罚）、对不活跃维度跳过 KL；以及"不要一开始就用大 β，从 β≈0.01 开始升"。A、C、D 都对不上"KL≈0 + 重构差"这个组合。

### Q5 — 答案：A

σ 必须为正，如果直接输出 σ，需要加 `softplus` / `exp` 之类的约束；讲义指出 `softplus` 在 σ≈0 附近梯度会消失。输出 `log σ²` 时网络输出是任意实数，`σ = exp(0.5 · log σ²)` 天然为正，KL 公式里也直接出现 `log σ²`，计算方便。本节代码还额外把 `log σ²` 夹到 `[-6, 6]`，防止 `exp` 溢出或 σ 过小。

### Q6 — 答案：B

高斯解码器 `p(x|z) = N(x̂, σ_x² I)` 的负对数似然就是（缩放后的）MSE。对同一个 `z`，若存在多种合理的 `x`（同一个数字的多种笔画），MSE 最优的 `x̂` 是它们的**均值**——一个模糊的平均数字。讲义给出的修法：用离散解码器（VQ-VAE、NVAE），或者只把 VAE 当编码器、在 latent 上叠加扩散模型（Stable Diffusion 的做法）。

### Q7 — 答案：C

`512 × 512 × 3 = 786,432`；`64 × 64 × 4 = 16,384`；`786,432 / 16,384 = 48`。拆开看：空间上每边下采样 8 倍，面积缩小 64 倍；通道从 3 变成 4（反而增加了）。所以 64 倍（D）是只算了空间面积，32 倍（B）是一个常见的误算。

### Q8 — 答案：B

去噪循环全部在 latent 空间里进行，VAE 解码器只在最后调用一次（A 错）；img2img / inpainting 要先把输入图编码成 latent，所以多一次编码。讲义的 Production note 指出：1024² 时解码器要把 `128×128×16` 的 latent 上采样回 `1024×1024×3`，常常是整条流水线的激活显存峰值。C 错：没有 VAE 就回不到像素空间；D 描述的是 VQ-VAE。

### Q9 — 参考答案

**(a)** `z = μ + σ·ε`，`σ = exp(0.5 · lv)`（`lv` 即 `log σ²`）。链式法则：`∂z/∂lv = ε · ∂σ/∂lv = ε · 0.5 · exp(0.5 · lv) = 0.5 · σ · ε`。所以 `∂L/∂lv = ∂L/∂z · 0.5 · σ · ε`，正是代码里的 `0.5 * d_z[i] * sigma[i] * eps_used[i]`。再加上 KL 项对 `lv` 的梯度 `β · 0.5 · (exp(lv) - 1)`，得到 `d_lv`。我用有限差分验证过这套反向传播，最大绝对误差约 1e-9。

**(b)** `forward` 返回的字典里没有存 `eps`，所以 `backward` 只能从 `z = μ + σ·ε` 反解出来；`max(sigma, 1e-8)` 防止除以 0。更简单、也更稳的写法是让 `forward` 把 `eps` 一起存进返回值（`"eps": eps`），`backward` 直接用。反解在 σ 很小时会放大浮点误差，虽然这里有 `log σ² ≥ -6`（σ ≥ e⁻³ ≈ 0.05）兜底，问题不大。

**(c)** clamp 的真实导数是：在 `[-6, 6]` 内为 1，超出时为 0。`backward` 默认它恒为 1（相当于"直通估计"，straight-through）。当某个 `log σ²` 被夹住时，代码仍会把梯度传给 `W_sig`、`b_sig`，推动一个实际上已经不起作用的预激活值继续变化，严格说这是梯度与前向不一致。在本例中 `log σ²` 很少碰到 ±6，影响可以忽略；在 PyTorch 里用 `torch.clamp` 时自动求导会正确地给出 0 梯度。

### Q10 — 参考答案

**(a) 重构误差的下限是噪声能量。** 每个样本 = 簇中心 + 8 维独立噪声（σ=0.2）。这份噪声与簇身份无关、彼此独立，2 维 latent 不可能（也不值得）把它编码下来，最好的重构就是输出簇中心，此时期望误差 = `8 × 0.2² = 0.32`。β=0.01 / 0.2 的 0.33 / 0.37 已经贴着这个下限。

**(b) 数据里真正的结构只有"属于哪个簇"这 1 bit。** 一个 latent 维度就足够区分两个簇；第二个维度如果也携带信息，就要额外付出 KL 代价却换不来重构收益，于是优化把它关掉——`q(z₂|x) ≈ N(0, 1)`，KL ≈ 0。这就是"不活跃维度"（inactive dimension），可以看作**局部的后验坍塌**，在这里是合理的；只有当 β 极小（0.01）时 KL 几乎不要钱，第二维才"顺便"也编码了一些东西（KL 0.965）。

**(c) β=5：KL 压力过大，连第一维也被压缩**（KL 只有 0.67），编码器无法把两个簇清晰地分开，解码器经常输出两簇之间的"平均"，重构误差飙到 2.1——这是走向后验坍塌的过程。性价比最高的是 **β=0.2**：重构已接近噪声下限，总 KL 比 β=0.01 低三倍以上，编码空间也更接近先验（对采样更友好）。这就是讲义练习 1 说的 Pareto 最优。

### Q11 — 参考答案

```python
import math, random
from main import init_vae, sample_mixture, forward, backward, apply_update

def beta_schedule(epoch, warmup=10, beta_max=0.2):
    """线性 warm-up：前 warmup 个 epoch 从 0 爬到 beta_max，之后保持。"""
    return beta_max * min(1.0, epoch / warmup)

def kl_per_dim(data, params):
    z_dim = len(params["enc"]["b_mu"])
    totals = [0.0] * z_dim
    for x in data:
        fwd = forward(x, params, [0.0] * z_dim)     # eps 不影响 mu / log_sigma2
        for i, (m, lv) in enumerate(zip(fwd["mu"], fwd["log_sigma2"])):
            totals[i] += 0.5 * (math.exp(lv) + m * m - lv - 1)
    return [t / len(data) for t in totals]

def active_dims(data, params, threshold=0.05):
    return sum(1 for k in kl_per_dim(data, params) if k > threshold)

rng = random.Random(7)
params = init_vae(8, 10, 2, rng)
data = sample_mixture(60, 8, rng)
for epoch in range(40):
    beta = beta_schedule(epoch)                     # 唯一的改动
    for x in data:
        eps = [rng.gauss(0, 1) for _ in range(2)]
        fwd = forward(x, params, eps)
        apply_update(params, backward(x, fwd, params, beta), 0.01)
print([round(k, 3) for k in kl_per_dim(data, params)], active_dims(data, params))
```

实测输出：`[1.455, 0.011] 1`，即 warm-up 后仍然只有 1 个活跃维度（第二维 KL 只有 0.011，低于阈值）。

要点：
- `backward(x, fwd, params, beta)` 本来就接收 β 参数，所以只需在每个 epoch 开头算出当前 β 传进去，反向传播代码一行不用改。
- warm-up 的原理：训练初期解码器还很弱，如果 KL 一开始就满额，最省事的解就是"让 `q(z|x)` 等于先验、解码器输出均值"，一旦掉进去很难出来；先让编码器学会把信息放进 `z`，再逐步加上 KL 约束。
- 阈值要根据数据量级选；文献里常用"`μ` 在数据集上的方差 > 0.01"来定义活跃单元（active units）。

### Q12 — 参考回答要点

- **推导**：
  `log p(x) = log ∫ p(x|z) p(z) dz = log E_{q(z|x)}[ p(x|z) p(z) / q(z|x) ]`
  `≥ E_q[ log p(x|z) ] - KL[ q(z|x) || p(z) ]`（Jensen 不等式，log 是凹函数）
- **为什么是下界、何时取等**：`log p(x) - ELBO = KL[ q(z|x) || p(z|x) ] ≥ 0`，当近似后验等于真实后验时取等。所以最大化 ELBO 同时在做两件事：提高似然、让 `q` 逼近真实后验。
- **与代码对应**：若解码器 `p(x|z) = N(x̂, s² I)`，则 `-log p(x|z) = ||x - x̂||² / (2s²) + 常数`。本节代码直接用 `Σ(x - x̂)²`，相当于固定 `s² = 1/2`；β 则在调节重构项与 KL 项的相对权重（某种意义上等价于改变 `s²`）。
- 加分点：说明 `E_q[log p(x|z)]` 用单个样本 `z = μ + σ·ε` 做蒙特卡洛估计，而 KL 项因两边都是高斯而用闭式解。
- 常见误区：把 β-VAE 的 loss 当成严格的 ELBO——β ≠ 1 时它已经不是 `log p(x)` 的下界了。

### Q13 — 参考回答要点

- **为什么需要**：损失是 `E_{z~q_φ(z|x)}[f(z)]`，期望的分布本身依赖参数 φ，不能把梯度直接搬进期望里。重参数化改写为 `E_{ε~N(0,I)}[f(μ_φ + σ_φ·ε)]`，期望的分布不再依赖 φ，梯度可以进到期望内部，用单样本估计且方差低。
- **替代方案**：score function 估计（REINFORCE / 对数导数技巧）`∇E[f] = E[f(z) ∇ log q(z)]`，对任何分布都适用，但方差很大，通常需要 baseline 等降方差手段。
- **离散 latent**：没法直接重参数化。常见做法：Gumbel-Softmax（连续松弛）、VQ-VAE 的直通估计（straight-through estimator，前向取最近码字，反向把梯度原样复制给编码器输出）。
- 加分点：指出重参数化要求分布属于"位置-尺度族"或有可微的采样变换；扩散模型里 `x_t = √ᾱ_t·x₀ + √(1-ᾱ_t)·ε` 也是同一个思想。

### Q14 — 参考回答要点

- **定义**：KL 项把 `q(z|x)` 压成先验 `N(0, I)`，`z` 与 `x` 无关，解码器忽略 `z`、靠自身"幻觉"输出。
- **原因**：KL 项是一个"不用 `z` 就能直接降到 0"的项；当解码器足够强（例如自回归解码器能自己建模 `x`），或训练早期解码器还没学会利用 `z` 时，优化很容易滑向"KL=0"这个平凡解。
- **缓解**：
  1. **β 退火 / KL warm-up**：β 从 0 逐渐升到目标值，让编码器先学会编码信息（Q11）。
  2. **free bits**：每维 KL 低于阈值 λ 时不惩罚（`max(λ, KL_i)`），保证每维至少能携带 λ nats 信息。
  3. **对不活跃维度跳过 KL** 或减弱解码器（让它必须依赖 `z`）。
  4. 更小的初始 β（讲义：从 β≈0.01 开始升）。
- **监控**：每维 KL、活跃维度数、重构误差；技能文件里要求设定后验坍塌报警阈值。
- 常见误区：看到某些维度 KL≈0 就认为一定坏了——如 Q10 所示，数据本身信息量少时，多余维度被关掉是正常的。

### Q15 — 参考回答要点

- **为什么在 latent 里做扩散**：像素空间维度高（512² 图像 78 万维），扩散每一步都是全分辨率的 U-Net / DiT 前向，成本 = 步数 × 单步成本。VAE 先把图像压缩 48 倍（512×512×3 → 64×64×4），去掉人眼不敏感的高频细节，扩散模型只需在小得多的空间里"干重活"。讲义的说法："VAE 做粗压缩，扩散模型做重活"。
- **显存问题**：1024² 时解码器把 `128×128×16` 的 latent 上采样到 `1024×1024×3`，常常是整条流水线的激活显存峰值。处理：`diffusers` 的 `pipe.vae.enable_slicing()`（按 batch 切片逐个解码）和 `pipe.vae.enable_tiling()`（分块解码，显存与块大小相关而不是整张图，代价是可能有细微接缝）。
- **数值问题**：旧版 SD / SDXL 的 VAE 在 fp16 下大分辨率会静默产生 NaN（激活值超出 fp16 范围）。处理：用社区的 `madebyollin/sdxl-vae-fp16-fix`，或用 bf16（动态范围与 fp32 相同）跑解码器。
- 加分点：img2img / inpainting 还要额外编码一次；VAE 质量决定了整条流水线的细节上限（文字、人脸细节常常坏在 VAE 上）。

### Q16 — 参考回答要点

- **选择**：下游是 Transformer（自回归建模）→ 选**离散** latent：VQ-VAE 或 RVQ（残差量化）。理由：Transformer 天然建模离散 token 序列，讲义的 Use It 表："Discrete latents (for transformer modelling) → VQ-VAE, RVQ"；音频可以直接参考 Encodec、SoundStream、DAC。如果下游是扩散 / flow matching，则选连续 VAE。
- **RVQ 的好处**：多级码本逐级量化残差，用几个小码本就能达到高保真，码率也能按级数调节。
- **健康监控**：
  - 重构质量（MSE / 频谱距离 / 主观听感）；
  - **码本利用率**：技能文件规定码本使用率低于 20% 要报警（码本坍塌是常见问题，需要死码重置等策略）；
  - 若是连续 VAE：每维 KL、活跃维度数，后验坍塌报警阈值。
- 加分点：说明码率（token/秒）直接决定下游 Transformer 的序列长度和推理成本。

### Q17 — 参考回答要点

- **为什么还用**：在潜空间扩散里，VAE 的任务不是"生成"，而是**感知压缩**：把图像压到一个紧凑、平滑的 latent 空间，让扩散模型在里面便宜地工作。latent 的 KL 正则（通常 β 很小）保证这个空间是规整的，扩散模型才容易学；最终的锐利细节由扩散模型生成，VAE 解码器只负责高保真还原。
- **让 VAE 不糊的办法**：
  1. 换解码器似然：离散 / 分类解码器（讲义提到 VQ-VAE、NVAE），或 Bernoulli 似然（讲义练习 2）；
  2. 只把 VAE 当编码器，生成交给 latent 上的扩散 / flow matching（Stable Diffusion 的路线）；
  3. 降低 β（更清晰但编码空间更不规整）；
  4. 层级 VAE（NVAE）提升表达力。
- 常见误区：以为"潜空间扩散里的 VAE 是生成器的一部分所以它的模糊会传给最终图"——实际上它在训练时就是作为高保真自编码器训练的，β 极小，重构很清晰。
- 加分点：能顺带解释 1024² 下 VAE 解码是显存峰值、要 tiling（与 Q15 呼应）。

---

## 六、关联知识点

### 前置知识
- [阶段 08 · 01 生成模型——分类法和历史](../../01-generative-models-taxonomy-history/docs/zh.md)：VAE 属于"桶 2：显式近似密度"。
- [阶段 03 · 03 反向传播](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：本节代码的手写 backward 就是链式法则。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 散度的定义与性质。
- [阶段 01 · 06 概率与分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：多元高斯、对角协方差。
- [阶段 01 · 10 降维](../../../01-math-foundations/10-dimensionality-reduction/docs/zh.md)：自编码器是非线性版的 PCA。

### 本节被哪些后续内容用到
- [阶段 08 · 06 DDPM 从零实现](../../06-diffusion-ddpm-from-scratch/docs/zh.md)：扩散同样优化（加权的）ELBO，前向加噪也用了 `√ᾱ·x₀ + √(1-ᾱ)·ε` 这种重参数化形式。
- [阶段 08 · 07 潜空间扩散与 Stable Diffusion](../../07-latent-diffusion-stable-diffusion/docs/zh.md)：VAE 作为像素 ↔ latent 的编解码器。
- [阶段 08 · 10 视频生成](../../10-video-generation/docs/zh.md)：时空 VAE 把视频压成 latent。
- [阶段 08 · 19 视觉自回归 VAR](../../19-visual-autoregressive-var/docs/zh.md)：多尺度 VQ tokenizer，离散 latent 的延伸。
- [阶段 06 · 13 神经音频编解码器](../../../06-speech-and-audio/13-neural-audio-codecs/docs/zh.md)：Encodec / RVQ，音频版的 VQ-VAE。
- [阶段 12 · 11 Chameleon 早期融合 token](../../../12-multimodal-ai/11-chameleon-early-fusion-tokens/docs/zh.md)：用 VQ 图像 tokenizer 把图像变成 Transformer 能处理的 token。

### 延伸关键词
`ELBO / Jensen 不等式` · `重参数化 (reparameterization)` · `β-VAE / FactorVAE / TCVAE` · `free bits / KL annealing` · `active units` · `VQ-VAE / RVQ / codebook collapse` · `Gumbel-Softmax` · `NVAE` · `sd-vae-ft-ema` · `VAE tiling / slicing` · `bf16 vs fp16`
