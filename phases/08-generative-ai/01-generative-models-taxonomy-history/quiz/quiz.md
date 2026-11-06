# 测验 · 生成模型——分类法和历史（Generative Models — Taxonomy & History）

> **阶段 08 · 生成式 AI · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 生成模型的任务 | 从未知分布 `p_data(x)` 的样本中学一个 sampler（采样器），可选地还能给出 `log p(x)` |
| 2 | 为什么难 | 512×512 RGB 图像约 786k 维，数据集中在一个薄薄的低维流形上（manifold hypothesis），样本却只有千万级，暴力估计密度不可行 |
| 3 | 桶 1：显式、可精确计算的密度 | 自回归 `p(x) = ∏ p(xᵢ | x<ᵢ)`（PixelCNN、WaveNet、GPT）与 normalizing flow（RealNVP、Glow）；精确似然，但 AR 推理串行、flow 要求可逆结构 |
| 4 | 桶 2：显式、近似的密度 | 优化 `log p(x)` 的下界 ELBO：VAE（编码器 + 解码器 + 变分后验），DDPM（训练去噪器，隐式优化一个加权 ELBO） |
| 5 | 桶 3：隐式密度 | GAN：生成器 `G(z)` + 判别器 `D(x)`，推理一次前向，但训练不稳定，**无法评估某个点的 `p(x)`** |
| 6 | 桶 4：score-based / 连续时间 | 直接学 score `∇ₓ log p(x)`；Song & Ermon 把扩散推广为 SDE；flow matching 免仿真训练、路径更直、采样步数更少 |
| 7 | 桶 5：离散码上的 token 自回归 | 先用 VQ-VAE / 残差量化把数据压成短的离散 token 序列，再用 Transformer 建模；本质是"桶 1 + 一个学出来的 tokenizer" |
| 8 | 五问分诊（five-question triage） | 建模对象是什么？密度显式还是隐式？一次出样还是迭代？条件是什么？用什么指标评估？ |
| 9 | 五种推理成本形状 | AR：串行 decode 主导延迟（KV cache、continuous batching、投机解码适用）；扩散/flow：`num_steps × step_cost`；GAN：一次前向，TTFT ≈ 总延迟 |
| 10 | 代码中的显式 vs 隐式 | histogram / KDE 能回答"这个点有多可能"，最近样本加噪的"GAN 式"生成器只能吐样本 |

### 核心技能（能动手做到）

- [ ] 用纯 Python 从两模高斯混合中采样，并用直方图（滑动窗口）和高斯 KDE 估计任意点的密度
- [ ] 用梯形法把密度函数积分成区间概率，并能解释为什么本节输出里 histogram 是 0.025、KDE 是 0.033
- [ ] 拿到任意一篇生成模型论文，能在 5 分钟内回答五问分诊，并把它放进五个桶之一
- [ ] 能把 PixelCNN、Glow、VAE、DDPM、StyleGAN、Flux.1、VALL-E 等模型正确归类，并说出各自的核心取舍
- [ ] 能用 `步数 × 单步成本` 估算扩散模型延迟，并把论文里的"比扩散快 N 倍"翻译成"少了多少步 / 每步便宜了多少"
- [ ] 能根据业务需求（是否需要似然、延迟预算、是否窄领域）给出家族选择，并说出该家族的典型失败模式

---

## 二、基础自测（选择题）

**Q1.** 以下哪一组模型**都**能直接给出像素/数据空间上精确（tractable）的 `log p(x)`？

- A. GAN 与 StyleGAN2
- B. VAE 与 DDPM
- C. PixelCNN 与 Glow
- D. VQGAN 编码器 + Transformer 与 StyleGAN

**Q2.** 关于 DDPM（Ho 2020）的训练目标，以下描述最准确的是：

- A. 直接最大化精确的 `log p(x)`
- B. 训练一个去噪器，隐式地优化一个加权的 ELBO（`log p(x)` 的下界）
- C. 最小化判别器区分真假样本的分类损失
- D. 对离散 token 做 next-token 交叉熵

**Q3.** 某扩散模型需要 50 步采样，每步 U-Net 前向 40 ms；蒸馏后的版本只需 4 步，但每步变成 45 ms。端到端延迟大约加速了多少？

- A. 约 1.1 倍
- B. 约 11 倍
- C. 约 12.5 倍
- D. 约 50 倍

**Q4.** 用五问分诊审一篇论文时，发现模型"推理只需一次前向就能出图"。按讲义的说法，这**通常**意味着：

- A. 它是逐像素自回归模型
- B. 它是对抗训练的（GAN 类），或是从迭代模型蒸馏出来的
- C. 它一定能给出精确的 `log p(x)`
- D. 它一定是 normalizing flow

**Q5.** VALL-E、AudioLM 这类模型最准确的描述是：

- A. 在原始波形上逐采样点自回归（每秒上万步）
- B. 先用 VQ-VAE / 残差量化器把音频压成离散 token，再用 Transformer 对 token 序列建模
- C. 由判别器指导训练的 GAN
- D. 直接学习连续时间 SDE 的 score 场

**Q6.** 为什么不能把本节代码里的直方图密度估计直接用到 512×512 RGB 图像上？

- A. 因为像素值是整数，直方图只能处理实数
- B. 因为维度约 786k，哪怕每维只切 2 个 bin 也需要 `2^786432` 个格子，而样本只有千万量级，且数据集中在低维流形上，几乎所有格子都是空的
- C. 因为直方图无法处理多峰分布
- D. 因为图像数据不服从任何概率分布

**Q7.** 在本节代码中，把 `kde_density` 的 `bandwidth` 从 0.3 调到 1.0，两峰之间低谷 `x = 0` 处的估计密度会怎样？（真实值约 0.024）

- A. 明显变大（约 0.026 → 0.088），因为过度平滑把峰上的概率质量"摊"进了低谷
- B. 明显变小，因为核变宽后每个样本的贡献被除以了更大的 bandwidth
- C. 不变，KDE 的结果与 bandwidth 无关
- D. 变成负数

**Q8.** 关于 flow matching（Lipman 2023），以下哪项是讲义强调的优势？

- A. 免仿真（simulate-free）训练、路径更直，采样比 DDPM 快 4–10 倍
- B. 不需要任何训练数据
- C. 引入了判别器，因此能给出精确似然
- D. 只能用于离散 token，不能用于图像

---

## 三、动手 / 代码题

**Q9.** 阅读本节的 `histogram_density`，写出下面调用的输出，并回答：结果大于 1 是 bug 吗？这个"直方图"和教科书里固定网格的直方图有什么不同？

```python
def histogram_density(samples, x, bin_width=0.25):
    """Explicit density via histogram. Returns p(x) as (count in bin) / (n * bin_width)."""
    n = len(samples)
    lo, hi = x - bin_width / 2, x + bin_width / 2
    count = sum(1 for s in samples if lo <= s < hi)
    return count / (n * bin_width)

print(histogram_density([0.0, 0.1, 0.2, 1.0], 0.0))
```

**Q10.** 运行 `main.py` 得到：

```text
integrate p(x in [-0.5, 0.5]):
  histogram: 0.025
  kde:       0.033
```

已知：真实混合分布在该区间的概率约 0.0295；2000 个样本中落在 `[-0.5, 0.5)` 的比例恰好是 0.025。请回答：
(a) 为什么 histogram 的积分几乎精确等于样本比例？
(b) 为什么 KDE 的结果偏高？
(c) `integrate_density(kde_density, samples, -0.5, 0.5)`（`steps=200`，`n=2000`）一共调用了多少次 `kde_density`、多少次核函数计算？怎样把调用次数减半？

```python
def integrate_density(density_fn, samples, lo, hi, steps=200):
    xs = [lo + (hi - lo) * i / steps for i in range(steps + 1)]
    total = 0.0
    for i in range(steps):
        a, b = xs[i], xs[i + 1]
        total += 0.5 * (density_fn(samples, a) + density_fn(samples, b)) * (b - a)
    return total
```

**Q11.** 隐式生成器给不出 `p(x)`，那只能**比较样本统计量**来评估它（这正是 FID 等指标的思路）。请写一个函数 `two_sample_stats(a, b)`，分别返回两组样本的（均值、标准差、`x < 0` 的比例），并用它对比 `implicit_generator(train, 2000, rng)` 生成的样本与 `sample_mixture` 新采的 2000 个真样本。理论上混合分布的均值、标准差和负值比例分别是多少？

---

## 四、面试高频题

**Q12.**（基础必考）请按"建模的是什么"把生成模型分成五类，每类各举 1–2 个代表模型，并说出它的核心优点和代价。

**Q13.**（原理深挖）什么是显式密度与隐式密度？为什么 GAN 不能用来做似然打分？如果业务要做"异常检测 / 给样本打似然分"，你会选哪类生成模型？

**Q14.**（原理深挖）VAE 和扩散模型都在优化 ELBO，为什么扩散模型的样本清晰得多？score `∇ₓ log p(x)` 和扩散模型的去噪器是什么关系？

**Q15.**（工程实践）自回归、扩散/flow matching、GAN 三类模型的推理成本形状有什么不同？各自的主要优化手段是什么？

**Q16.**（场景设计）你要为三个需求选型：①电商 App 里实时（<50 ms）生成固定风格的人脸头像；②通用文生图服务；③给检测系统用的、需要精确 `log p(x)` 的密度估计。分别选哪个家族，为什么？各自要警惕什么失败模式？

**Q17.**（追问型）一篇新论文摘要写着"采样速度比扩散模型快 100 倍"。你会问哪三个问题来判断这个加速在真实场景下是否成立？

---

## 五、参考答案与解析

### Q1 — 答案：C

PixelCNN 是自回归模型，`log p(x) = Σ log p(xᵢ | x<ᵢ)` 每一项都能直接算；Glow 是 normalizing flow，通过可逆变换和雅可比行列式得到精确 `log p(x)`。二者都属于"桶 1：显式、可精确计算"。

- A 错：GAN 是隐式密度，只有采样器。
- B 错：VAE 和 DDPM 只能给出 `log p(x)` 的下界（ELBO），是"近似"的显式密度。
- D 是迷惑项：Transformer 在**离散 token 序列**上的似然是精确的，但从 token 回到像素经过了有损的量化/解码，并不是像素空间的精确 `log p(x)`；而 StyleGAN 根本没有密度。

### Q2 — 答案：B

讲义原话："Diffusion models train a denoiser that implicitly optimizes a weighted ELBO"。DDPM 实际训练的是"预测加入的噪声 ε"的 MSE，这个简化目标可以看作 ELBO 的一个加权版本。A 错在"精确"；C 是 GAN；D 是 GPT/token-AR。

### Q3 — 答案：B

原始：`50 × 40 = 2000 ms`；蒸馏：`4 × 45 = 180 ms`；`2000 / 180 ≈ 11.1` 倍。C（12.5 倍）是只看步数比 `50/4` 的错误算法，忽略了单步成本也变了。这正是讲义"Production note"的要点：**扩散类成本 = 步数 × 单步成本**，任何"加速"都要拆成这两项来看。

### Q4 — 答案：B

讲义第 3 问："Iterative means slower inference; one-shot usually means adversarial or distilled." 关键词是"通常"。A 恰好相反（逐像素 AR 是最串行的）；C、D 都用了"一定"——flow 也能一次出样，但一次出样不代表就是 flow，更不代表有精确似然（GAN 就没有）。

### Q5 — 答案：B

这是"桶 5：离散码上的 token 自回归"。音频先被神经编解码器（VQ-VAE / 残差量化）压成每秒几十到几百个离散 token，再用 Transformer 建模——讲义说它就是"桶 1 + 一个学出来的 tokenizer"。A 描述的是 WaveNet（桶 1，直接在波形上自回归）；C、D 是其他桶。

### Q6 — 答案：B

直方图需要的格子数随维度**指数增长**（维度灾难）。786k 维时，就算每维只切 2 个 bin，格子数也是天文数字，千万级样本几乎全部落在不同格子里，绝大多数格子为空，估计毫无意义。再加上流形假设：真实图像只占据这个高维空间里极薄的一层，均匀切格浪费在空白区域。这正是"每个生成模型都是用一个难题换一个稍微不那么难的问题"的原因。A、C、D 都不是根本原因（直方图在一维里就能处理多峰，本节代码就演示了）。

### Q7 — 答案：A

实测：`bandwidth=0.3` 时 `p(0) ≈ 0.0258`，`bandwidth=1.0` 时 `≈ 0.0879`，而真实值约 0.0235（`bandwidth=0.05` 时为 0.0222，更接近但方差更大）。KDE 的估计等于"真实密度与高斯核的卷积"，核越宽越平滑；在低谷处（密度是凸的），平滑会把两侧高峰的质量拉进来，造成**正偏差**。B 错在只看了分母，忽略了更宽的核让远处样本也贡献了可观的权重。这就是经典的偏差-方差权衡：带宽小 → 方差大、偏差小；带宽大 → 方差小、偏差大。

### Q8 — 答案：A

讲义："Flow matching (Lipman 2023) is the 2024-2026 hotness: simulate-free training, straighter paths, 4-10x faster sampling than DDPM." 并指出 Stable Diffusion 3、Flux 都用了 flow matching。B、C、D 都是编造的属性。

### Q9 — 参考答案

输出：

```text
2.0
```

计算过程：窗口为 `[-0.125, 0.125)`，落入的样本是 `0.0` 和 `0.1`，`count = 2`；`2 / (4 × 0.25) = 2.0`。

- **大于 1 不是 bug**：这是**概率密度**，不是概率。密度只需满足"非负且积分为 1"，在很窄的区间上可以远大于 1（窗口宽 0.25，密度 2.0，对应的概率是 `2.0 × 0.25 = 0.5`，正好是 4 个样本中 2 个）。
- **与固定网格直方图的不同**：教科书直方图先把数轴切成固定的格子，查询点落在哪个格子就用哪个格子的计数；这里则是**以查询点 `x` 为中心**开一个宽 `bin_width` 的窗口，实际上是"矩形核（boxcar kernel）的 KDE"，也叫滑动窗口估计。它的结果随 `x` 平滑移动，不受网格起点影响。
- 区间用 `lo <= s < hi` 半开半闭，保证相邻窗口不会把同一个样本数两次。

### Q10 — 参考答案

**(a)** 对滑动窗口直方图做积分：`∫ (1/(n·w)) Σ 1[s 在以 x 为中心的窗口内] dx`。交换求和与积分后，每个样本的贡献 = "以它为中心、宽 w 的区间与 `[lo, hi]` 的重叠长度"÷`(n·w)`。完全落在区间内部（离边界大于 `w/2`）的样本贡献恰好 `1/n`，所以积分≈样本比例，只在边界附近有少量"半个样本"的误差；梯形步长 `1/200 = 0.005` 远小于窗口宽 0.25，离散误差可忽略。

**(b)** KDE 的期望等于真实密度与高斯核（带宽 0.3）的卷积，在一阶近似下偏差约为 `h²/2 · p''(x)`。区间 `[-0.5, 0.5]` 位于两峰之间的低谷，密度是凸的（`p'' > 0`），所以平滑带来**正偏差**——右侧那个更宽、更重的峰（中心 +2、σ=0.9、权重 0.6）的尾部质量被"抹"了进来，结果 0.033 高于真值 0.0295。直方图恰好偏低（0.025）则是样本的随机波动。

**(c)** 循环 200 次，每次调用 `density_fn` 两次 → **400 次** `kde_density`；每次遍历 2000 个样本 → **80 万次**核函数（`exp`）计算，复杂度 `O(steps · n)`。相邻区间共享端点（第 i 段的 `b` 就是第 i+1 段的 `a`），可以先把 201 个网格点的密度各算一次：

```python
def integrate_density_fast(density_fn, samples, lo, hi, steps=200):
    h = (hi - lo) / steps
    ys = [density_fn(samples, lo + h * i) for i in range(steps + 1)]   # 201 次
    return h * (0.5 * ys[0] + sum(ys[1:-1]) + 0.5 * ys[-1])
```

调用次数从 400 降到 201，结果完全相同（这就是梯形公式的标准写法）。

### Q11 — 参考答案

```python
import random
from main import sample_mixture, implicit_generator

def two_sample_stats(a, b):
    def stats(xs):
        n = len(xs)
        mean = sum(xs) / n
        std = (sum((x - mean) ** 2 for x in xs) / n) ** 0.5
        frac_neg = sum(1 for x in xs if x < 0) / n
        return mean, std, frac_neg
    return stats(a), stats(b)

rng = random.Random(42)
train = sample_mixture(2000, rng)
fake = implicit_generator(train, 2000, rng)
real = sample_mixture(2000, random.Random(7))
for name, s in zip(["fake", "real"], two_sample_stats(fake, real)):
    print(name, "mean=%.3f std=%.3f frac_neg=%.3f" % s)
```

实测输出：

```text
fake mean=0.467 std=2.143 frac_neg=0.406
real mean=0.331 std=2.153 frac_neg=0.427
```

理论值：
- 均值 `0.4 × (-2) + 0.6 × 2 = 0.4`
- 方差 `E[x²] - (E[x])² = 0.4 × (4 + 0.36) + 0.6 × (4 + 0.81) - 0.16 = 4.47`，标准差 ≈ **2.114**（生成器额外加了 σ=0.1 的噪声，方差再 +0.01，几乎不变）
- 负值比例 ≈ 0.4（左峰在 0 右侧的尾巴和右峰在 0 左侧的尾巴大致抵消）

两组统计量都在理论值附近波动，说明这个"生成器"在一阶、二阶矩上是对的。要点：对隐式模型，**只能用样本对样本的方式评估**（矩匹配、MMD、FID 用 Inception 特征的均值和协方差做的就是同一件事）；而且这种生成器本质上是"记住训练集再加点噪声"，统计量再好也可能只是复制——这也是评估生成模型时要单独检查 memorization 的原因。

### Q12 — 参考回答要点

| 桶 | 建模方式 | 代表 | 优点 | 代价 |
|----|---------|------|------|------|
| 1 显式·可精确 | AR 分解 / 可逆变换 | PixelCNN、WaveNet、GPT；RealNVP、Glow | 精确似然，训练损失干净 | AR 推理串行慢；flow 必须可逆，结构受限 |
| 2 显式·近似 | 优化 ELBO 下界 | VAE、DDPM | 训练稳定；扩散是 2026 年图像/视频/3D 的主力骨干 | 只有下界；扩散需要多步迭代采样 |
| 3 隐式 | 生成器 vs 判别器 | GAN、StyleGAN 1/2/3 | 一次前向，快；窄领域写实度极高 | 训练不稳定（模式崩溃），没有 `p(x)` |
| 4 score / 连续时间 | 学 `∇ₓ log p(x)` 或速度场 | Score SDE、flow matching（SD3、Flux） | 免仿真训练、路径直、步数少 | 仍是迭代采样，需要 ODE/SDE 求解器 |
| 5 离散 token AR | tokenizer + Transformer | Parti、AudioLM、VALL-E | 复用 LLM 的整套扩展与推理工程 | tokenizer 有损，伪影上限由它决定；序列长 |

- 加分点：顺带讲出时间线——2013 VAE → 2014 GAN → 2019 StyleGAN → 2020 DDPM → 2022 Stable Diffusion → 2023–2024 flow matching 胜出（SD3、Flux.1）→ 一步/少步采样（consistency、rectified flow + 蒸馏）。
- 常见误区：把扩散和 score-based 当成对立的两派——它们是同一件事的离散/连续两种视角。

### Q13 — 参考回答要点

- **定义**：显式密度 = 模型能对任意给定点算出（精确或下界的）`log p(x)`；隐式密度 = 模型只定义了一个采样过程，没有办法评估某一点的概率。
- **GAN 为什么不行**：`G(z)` 把低维 `z` 映射到高维空间，生成分布通常集中在一个低维流形上，在高维空间里甚至没有良定义的密度；判别器 `D(x)` 输出的是"像不像真的"，不是归一化的概率，不能当似然用。本节代码里的 `implicit_generator` 就是最小示例：只能吐样本，`p(x)` 一栏只能写 N/A。
- **选型**：需要精确 `log p(x)` 时首选 **normalizing flow**（讲义："Only family with exact log p(x)"，对连续数据）；序列/离散数据可用自回归模型；能接受下界时可用 VAE 的 ELBO 或扩散模型的 ELBO 估计（但扩散算似然很贵）。
- 加分点：提到似然高不等于样本质量好（两者可以脱节）；异常检测里还要注意"似然模型给分布外数据打高分"的已知现象，需要用似然比等方法校正。

### Q14 — 参考回答要点

- **为什么扩散更清晰**：
  - VAE 一步从压缩的低维 latent 解码出整张图，解码器常用高斯似然（等价于 MSE），对多种可能的细节会"取平均"→ 模糊；
  - 扩散把生成拆成很多小步，每一步只去掉一点噪声，单步的条件分布接近高斯，用简单的高斯假设就足够准确；latent 与数据同维，没有信息瓶颈。
- **score 与去噪器的关系**：score 是 `∇ₓ log p(x)`，指向"密度增加最快的方向"。在加噪后的分布 `p_t` 上，预测噪声的网络与 score 只差一个缩放：`ε_θ(x_t, t) ≈ -√(1-ᾱ_t) · ∇ log p_t(x_t)`。所以 DDPM 学去噪 ≈ 学一族不同噪声水平下的 score；Song 等人把它写成连续时间 SDE，统一了两种视角。
- **再往后**：flow matching 直接回归一条概率路径上的速度场，免仿真、路径更直，所以采样步数更少（讲义：比 DDPM 快 4–10 倍）。
- 常见误区：说"扩散不是似然模型"——DDPM 恰恰优化的是加权 ELBO，属于显式近似密度。

### Q15 — 参考回答要点

| 家族 | 成本形状 | 主要优化手段 |
|------|---------|------------|
| 自回归（桶 1、5） | 与 LLM 一样是 prefill + decode，串行 decode 主导延迟 | KV cache、continuous batching、投机解码（speculative decoding）、量化 |
| 扩散 / VAE / flow matching（桶 2、4） | 没有 LLM 意义上的 decode；成本 = `num_steps × step_cost`，每步是全分辨率 latent 上的一次 U-Net / Transformer 前向 | 减步数（DDIM、DPM-Solver、蒸馏）、增大 batch、降精度（bf16 / fp8 / int4）、在 latent 空间而非像素空间做 |
| GAN（桶 3） | 一次前向，没有调度、没有 KV cache，TTFT ≈ 总延迟 | 常规的模型压缩、批处理即可 |

- 加分点：讲义的口诀——看到"比扩散快"，翻译成"步数更少 × 单步成本不变"或"步数不变 × 单步更便宜"，其余都是营销。
- 结论：StyleGAN 在窄领域 UX 上仍有优势，原因就是一次前向的延迟形状。

### Q16 — 参考回答要点

1. **实时固定风格人脸（<50 ms）→ StyleGAN 2/3（桶 3）**。讲义："Photoreal faces, narrow domain — StyleGAN 2/3, still sharpest, fastest inference"。一次前向满足延迟预算。失败模式：模式崩溃（多样性不足）、训练不稳定、域外输入质量骤降。
2. **通用文生图 → 潜空间扩散 + flow matching（SD3、Flux.1 一类）**；要更快就用 rectified flow + 蒸馏（SDXL-Turbo、LCM 一类）。失败模式：步数/采样器漂移、为刷 CLIP score 而过拟合指标（CLIP-score gaming）、文字与构图错误。
3. **需要精确 `log p(x)` → normalizing flow**。不能选 GAN（没有似然），扩散只有下界且估计昂贵。失败模式：可逆结构限制表达力，样本质量通常不如扩散。

- 加分点：先问清"有没有现成的开源骨干已经覆盖这个领域"，能微调就别从零训练（这正是本节 `skill-model-chooser` 的规则之一）。

### Q17 — 参考回答要点

1. **加速来自哪里？** 是步数减少（蒸馏/少步采样器），还是单步更便宜（更小的网络、更低分辨率 latent）？对比时单步成本、硬件、batch、精度是否一致？
2. **加了条件之后还成立吗？** 文生图常用 classifier-free guidance，每步要跑有条件 + 无条件两次前向；很多少步方法在加 guidance、换复杂 prompt 后质量明显下降。
3. **高分辨率下还成立吗？质量有没有对齐？** 在 1024² 甚至视频上，单步成本随 token 数快速增长；必须在**同等 FID / CLIP score / 人类偏好**下比较速度，而不是拿一个质量更差的结果说更快。

- 加分点：主动提出看 Pareto 曲线（质量 vs 步数/延迟），而不是单点对比。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 06 概率与分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：概率密度、混合高斯、期望与方差。
- [阶段 01 · 16 采样方法](../../../01-math-foundations/16-sampling-methods/docs/zh.md)：从分布中采样、蒙特卡洛估计。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 散度、交叉熵，是理解 ELBO 的基础。
- [阶段 07 · 07 GPT 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：自回归分解 `∏ p(xᵢ | x<ᵢ)` 的最典型实例。

### 本节被哪些后续内容用到
- [阶段 08 · 02 自动编码器和 VAE](../../02-autoencoders-vae/docs/zh.md)：桶 2 的第一个代表，ELBO 的完整推导。
- [阶段 08 · 03 GANs — 生成器与鉴别器](../../03-gans-generator-discriminator/docs/zh.md)：桶 3，隐式密度与对抗训练。
- [阶段 08 · 05 StyleGAN](../../05-stylegan/docs/zh.md)：讲义里"窄领域写实度仍难被超越"的那个家族。
- [阶段 08 · 06 DDPM 从零实现](../../06-diffusion-ddpm-from-scratch/docs/zh.md)：桶 2 的扩散模型，"去噪器隐式优化加权 ELBO"。
- [阶段 08 · 07 潜空间扩散与 Stable Diffusion](../../07-latent-diffusion-stable-diffusion/docs/zh.md)：通用文生图的主流选型。
- [阶段 08 · 13 Flow Matching 与 Rectified Flows](../../13-flow-matching-rectified-flows/docs/zh.md)：桶 4 的 2024–2026 主角。
- [阶段 08 · 14 评估：FID、CLIP 分数、人类偏好](../../14-evaluation-fid-clip-score/docs/zh.md)：五问分诊的第 5 问。
- [阶段 08 · 19 视觉自回归 VAR](../../19-visual-autoregressive-var/docs/zh.md)：桶 5（token AR）在图像上的新形态。
- [阶段 06 · 13 神经音频编解码器](../../../06-speech-and-audio/13-neural-audio-codecs/docs/zh.md)：桶 5 里"学出来的 tokenizer"在音频上的实现。
- [阶段 07 · 12 KV Cache 与 Flash Attention](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：AR 家族推理优化的核心手段。

### 延伸关键词
`manifold hypothesis` · `核密度估计 (KDE) 与带宽选择` · `normalizing flow / 雅可比行列式` · `ELBO` · `score matching` · `probability flow ODE` · `VQ-VAE / RVQ` · `consistency models` · `rectified flow` · `classifier-free guidance` · `memorization 检测`
