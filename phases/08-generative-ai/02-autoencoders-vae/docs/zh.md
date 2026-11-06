<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="autoencoders--variational-autoencoders-vae"></a>

# 自动编码器和变分自动编码器 (VAE)

> 普通自动编码器先压缩然后重建。它记住了。它不会生成。添加一个技巧——强制代码看起来呈高斯分布——然后你就得到了一个采样器。这个技巧，即 `z = μ + σ·ε` 的重新参数化，就是为什么您在 2026 年使用的每个潜在扩散和流匹配图像模型在输入处都有一个 VAE 。

**类型：** 构建
**语言：** Python
**先决条件：** 第 3 阶段·02（反向传播）、第 3 阶段·07 (CNNs)、第 8 阶段·01（分类）
**时间：** ~75分钟

<a id="the-problem"></a>

## 问题

将 784 像素的 MNIST 数字压缩为 16 位数的代码，然后重建。普通的自动编码器可以很好地重建 MSE，但代码空间却是一团糟。在代码空间中选择一个随机点，对其进行解码，然后就会得到噪声。它没有采样器。这是一个装扮的压缩模型。

你真正想要的是：(a) 代码空间是一个干净、平滑的分布，你可以从中采样——比如各向同性高斯 `N(0, I)`，(b) 解码任何样本都会产生一个可信的数字，(c) encoder 和 decoder 仍然可以很好地压缩。三个目标，一种架构，一种损失。

Kingma 的 2013 VAE 通过训练 encoder 输出 *distribution* `q(z|x) = N(μ(x), σ(x)²)` 来解决这个问题，将该分布拉向先前的分布`N(0, I)` 通过 KL 惩罚，然后在解码之前从 `q(z|x)` 得到 sampling `z`。在inference时刻，放下encoder，采样`z ~ N(0, I)`，解码。 KL 惩罚是强制代码空间结构化的原因。

2026 年，VAEs 很少单独发货——它们在原始图像质量方面已被扩散超越——但它们是每个潜在 diffusion model（SD 1/2/XL/3、Flux、AudioCraft）的首选 encoder。学习 VAE，您就可以了解您使用的每个图像管道的不可见第一层。

<a id="the-concept"></a>

## 概念

![Autoencoder 与 VAE：重新参数化技巧](../assets/vae.svg)

**Autoencoder.** `z = encoder(x)`，`x̂ = decoder(z)`，损失= `||x - x̂||²`。代码空间非结构化。

**VAE encoder.** 输出两个向量：`μ(x)` 和 `log σ²(x)`。这些定义了 `q(z|x) = N(μ, diag(σ²))`。

**重新参数化技巧。** Sampling从`q(z|x)`是不可微分的。 将示例重写为`z = μ + σ·ε`在哪里`ε ~ N(0, I)`。 现在`z`是一个确定性函数`(μ, σ)`加上一个非parameter噪音 -gradients流过`μ`和`σ`。

**Loss.** 证据下限 (ELBO)，两项：

```
loss = reconstruction + β · KL[q(z|x) || N(0, I)]
     = ||x - x̂||²  + β · Σ_i ( σ_i² + μ_i² - log σ_i² - 1 ) / 2
```

重建将`x̂`推向`x`。 KL 将 `q(z|x)` 推向先前。他们进行权衡。小 β (<1) = 样本更清晰，代码空间更少高斯分布。大 β (>1) = 更干净的代码空间，更模糊的样本。 β-VAE (Higgins 2017) 使这个旋钮出名并启动了解缠结研究。

**Sampling.** 在inference：绘制`z ~ N(0, I)`，通过decoder转发。一个 forward pass — 没有像扩散那样的迭代 sampling。

```figure
vae-latent-grid
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 实现了一个小型 VAE，无需 numpy 或火炬。输入是从 8 维 2 分量高斯混合中提取的 8 维合成数据。 Encoder 和 decoder 是单隐藏层 MLP。我们实现 tanh 激活、forward pass、损失和手写的 backward pass。不是生产——教学。

<a id="step-1-encoder-forward"></a>

### 步骤1：encoder转发

```python
def encode(x, enc):
    h = tanh(add(matmul(enc["W1"], x), enc["b1"]))
    mu = add(matmul(enc["W_mu"], h), enc["b_mu"])
    log_sigma2 = add(matmul(enc["W_sig"], h), enc["b_sig"])
    return mu, log_sigma2
```

`log σ²` 而不是 `σ`，因此网络输出不受约束（σ 的 softplus 是一个陷阱 - gradients 在 σ ≈ 0 处死亡）。

<a id="step-2-reparameterize-and-decode"></a>

### 第 2 步：重新参数化和解码

```python
def reparameterize(mu, log_sigma2, rng):
    eps = [rng.gauss(0, 1) for _ in mu]
    sigma = [math.exp(0.5 * lv) for lv in log_sigma2]
    return [m + s * e for m, s, e in zip(mu, sigma, eps)]

def decode(z, dec):
    h = tanh(add(matmul(dec["W1"], z), dec["b1"]))
    return add(matmul(dec["W_out"], h), dec["b_out"])
```

<a id="step-3-the-elbo"></a>

### 第三步：ELBO

```python
def elbo(x, x_hat, mu, log_sigma2, beta=1.0):
    recon = sum((a - b) ** 2 for a, b in zip(x, x_hat))
    kl = 0.5 * sum(math.exp(lv) + m * m - lv - 1 for m, lv in zip(mu, log_sigma2))
    return recon + beta * kl, recon, kl
```

精确的封闭形式 KL，因为两个分布都是高斯分布。不要进行数值积分。预计到 2026 年，人们仍然会使用 monte-carlo KL 发送代码——它无缘无故地慢了 3 倍。

<a id="step-4-generate"></a>

### 第四步：生成

```python
def sample(dec, z_dim, rng):
    z = [rng.gauss(0, 1) for _ in range(z_dim)]
    return decode(z, dec)
```

这就是生成模型。五行。

<a id="pitfalls"></a>

## 陷阱

- **后塌陷。** KL术语驱动`q(z|x) → N(0, I)`如此积极，以至于`z`没有携带有关`x`的信息。修复：β 退火（开始 β=0，逐渐增加到 1）、释放位或跳过非活动维度上的 KL。
- **模糊样本。** 高斯 decoder 似然意味着 MSE 重建，这是 L2（平均值）的贝叶斯最优 — 一组可信数字的平均值是模糊数字。修复：离散 decoder（VQ-VAE，NVAE），或仅使用 VAE 作为 encoder 和潜在的堆栈扩散（这就是稳定扩散的作用）。
- **β太大，太早。** 见后塌陷。从 β≈0.01 开始并斜坡。
- **Latent dim 太小。** 16-D 适用于 MNIST，256-D 适用于 ImageNet 256²，2048-D 适用于 ImageNet 1024²。 Stable Diffusion 的 VAE 压缩 512×512×3 → 64×64×4（空间区域下采样因子 32 倍，通道下采样因子 32 倍）。

<a id="use-it"></a>

## 实际应用

2026 VAE 堆栈：

| 情况 | 挑选 |
|-----------|------|
| 用于扩散的图像潜伏 encoder | 稳定扩散 VAE (`sd-vae-ft-ema`) 或通量 VAE |
| 音频潜伏 encoder | 编码解码器（元）、SoundStream 或 DAC（描述） |
| 视频潜伏 | Sora的时空patches、Latte VAE、WAN VAE |
| 解开表示学习 | β-VAE，因子VAE，TCVAE |
| 离散潜伏（用于 transformer 建模） | VQ-VAE，RVQ（剩余VQ） |
| 持续的潜在生成 | 普通 VAE，然后在该 latent space 中调节流/diffusion model |

潜在的 diffusion model 是一个 VAE，其中 diffusion model 位于 encoder 和 decoder 之间。 VAE 进行粗压缩，diffusion model 进行繁重的压缩。视频（VAE + 视频扩散 DiT）和音频（Encodec + MusicGen transformer）具有相同的模式。

<a id="ship-it"></a>

## 交付成果

保存`outputs/skill-vae-trainer.md`。

技能要求：数据集配置文件 + 潜在暗淡目标 + 下游使用（重建、sampling 或潜在扩散输入）和输出：架构选择（普通/β/VQ/RVQ）、β 调度、潜在暗淡、decoder 可能性（高斯与分类）和 evaluation 计划（侦察 MSE、KL 每暗淡、`q(z|x)` 和 `N(0, I)` 之间的 Fréchet 距离）。

<a id="exercises"></a>

## 练习

1. **Easy.** 将`code/main.py`中的`β`更改为`0.01`、`0.1`、`1.0`、 `5.0`。记录最终重建的MSE和KL。哪个 β 最适合您的合成数据？
2. **Medium.** 将高斯 decoder 似然替换为伯努利似然（cross-entropy 损失）。比较相同合成数据的二值化版本的样本质量。
3. **Hard.** 将 `code/main.py` 扩展为迷你 VQ-VAE：用 K=32 条目的码本中的最近邻查找替换连续的 `z`。比较重建 MSE 并报告使用了多少个码本条目（码本崩溃是真实的）。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| 自动编码器 | 编码解码网络 | `x → z → x̂`，学习MSE。不具有生成性。 |
| VAE | 带采样器的 AE | Encoder 输出分布、KL 惩罚形状代码空间。 |
| 埃尔博 | 证据下限 | `log p(x) ≥ recon - KL[q(z\|x) \|\| p(z)]`;紧时`q = p(z\|x)`。 |
| 重新参数化 | `z = μ + σ·ε` | 将随机节点重写为确定性+纯噪声。通过 sampling 启用反向传播。 |
| 事先 | `p(z)` | 潜在的目标分布，通常为 `N(0, I)`。 |
| 后塌陷 | “吉隆坡任期获胜” | Encoder 忽略 `x`，输出先验； decoder一定是产生了幻觉。 |
| β-VAE | 可调谐 KL weight | `loss = recon + β·KL`。较高的 β = 更解缠但更模糊。 |
| VQ-VAE | 离散潜伏 | 将连续的 `z` 替换为最接近的码本向量；启用 transformer 建模。 |

<a id="production-note-the-vae-is-the-hottest-path-in-a-diffusion-server"></a>

## 生产说明：VAE 是扩散服务器中最热的路径

在稳定的 Diffusion / Flux / SD3 管道中，每个请求都会调用 VAE 两次 - 一次用于编码（如果进行 img2img/修复），一次用于解码。在 1024² 时，decoder 通道通常是整个管道中最大的单个激活内存峰值，因为它将 `128×128×16` 潜伏值上采样回 `1024×1024×3`。两个实际后果：

- **对解码进行切片或平铺。** `diffusers` 公开 `pipe.vae.enable_slicing()` 和 `pipe.vae.enable_tiling()`。平铺用一个小接缝工件换取 `O(tile²)` 内存，而不是 `O(H·W)`。对于消费者 GPUs 上的 1024²+ 至关重要。
- **bf16 decoder，最终调整大小的fp32数字。** SD 1.x VAE以fp32发布，*默默生成NaNs* 当在 1024²+ 下投射到 fp16 时。 SDXL 附带 `madebyollin/sdxl-vae-fp16-fix` — 始终更喜欢 fp16-fix 变体或使用 bf16。

<a id="further-reading"></a>

## 进一步阅读

- [Kingma & Welling (2013)。自动编码变分贝叶斯](https://arxiv.org/abs/1312.6114) — VAE 论文。
- [Higgins 等人。 （2017）。 β-VAE：使用受约束的变分框架学习基本视觉概念](https://openreview.net/forum?id=Sy2fzU9gl) - 解开的β-VAE。
- [van den Oord 等人。 （2017）。神经离散表示学习](https://arxiv.org/abs/1711.00937) — VQ-VAE。
- [Vahdat 和考茨 (2021)。 NVAE：深度分层变分自动编码器](https://arxiv.org/abs/2007.03898) - 最先进的图像 VAE。
- [Rombach 等人。 （2022）。具有潜在特征的高分辨率图像合成 Diffusion Models](https://arxiv.org/abs/2112.10752) — 稳定扩散； VAE 为 encoder。
- [Défossez 等人。 （2022）。高保真神经音频压缩](https://arxiv.org/abs/2210.13438) — 编码器，音频 VAE 标准。
