# 测验 · 风格GAN（StyleGAN）

> **阶段 08 · 生成式 AI · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | DCGAN 的问题：纠缠 | `z` 直接经转置卷积变成图像，姿态、光照、身份、背景全部纠缠在一起；沿 `z` 的一个方向移动，所有属性一起变 |
| 2 | Mapping network | 8 层 MLP `f: Z → W`，`Z = N(0, I)^512`；`W` 不被强制为高斯，可以学成"适应数据"的形状，因而更解耦 |
| 3 | Synthesis network | 从**学习的常量** `4×4×512` 出发（不再从 `z` 出发），每个分辨率块：上采样 → 卷积 → AdaIN(w) → 噪声 → 卷积 → AdaIN(w) → 噪声，分辨率 4 → 1024 逐级翻倍 |
| 4 | AdaIN | `AdaIN(x, y) = y_scale · (x - mean(x)) / std(x) + y_bias`，scale/bias 由 `w` 的仿射投影得到；"风格"= 特征图的一阶、二阶统计量 |
| 5 | 逐层噪声 | 每层加单通道高斯噪声，乘以学习的逐通道系数；控制随机细节（毛孔、发丝），不影响全局结构 |
| 6 | 风格混合 | 低分辨率层用图像 A 的 `w`、高分辨率层用图像 B 的 `w`：得到 A 的高层属性（姿态、身份）+ B 的精细风格（光照、颜色） |
| 7 | 截断技巧 | `w' = ŵ + ψ·(w - ŵ)`，`ŵ` 是大量样本的平均 `w`；`ψ < 1` 用多样性换质量，演示中常用 `ψ ≈ 0.7` |
| 8 | StyleGAN 1 → 2 → 3 | 2：weight demodulation 取代 AdaIN（消除水滴伪影）、skip/residual 结构、path-length 正则；3：alias-free 卷积（消除纹理粘在像素网格上） |
| 9 | Inversion 与编辑 | 用优化或编码器（e4e、ReStyle、HyperStyle、PTI）找到 `G(w) ≈ x` 的 `w`，再在 W / W+ / StyleSpace 中沿方向编辑；不要在 Z 中编辑 |
| 10 | 生产定位 | 4090 上生成 1024² 人脸 <10 ms，50 步 SDXL + VAE 解码约 3 s（约 300 倍差距）；每个请求 FLOPs 相同，静态 batch 即最优；开放域 / 文本条件生成不要用它 |

### 核心技能（能动手做到）

- [ ] 用纯 Python 实现 mapping MLP、AdaIN、逐层噪声，并验证"AdaIN 后向量的均值 = bias、标准差 = |scale|"
- [ ] 实现截断技巧：采样大量 `w` 求 `ŵ`，对 `ψ ∈ {0, 0.5, 0.7, 1}` 生成并解释输出变化
- [ ] 实现风格混合（前 k 层用 `w_a`、其余用 `w_b`），并能分析在玩具网络与真实 StyleGAN 中"哪些层决定什么"
- [ ] 说清水滴伪影、纹理粘连分别是哪一代修复的、怎么修复的
- [ ] 为真实照片编辑设计 pipeline：选 inversion 方法、latent 空间、编辑方向和身份保持评估（ArcFace、LPIPS）
- [ ] 对比 StyleGAN 与扩散在延迟、服务形态上的差异，并判断一个需求该用哪一个

---

## 二、基础自测（选择题）

**Q1.** StyleGAN 引入 mapping network `f: Z → W` 的主要动机是：

- A. 让生成器参数更少
- B. `Z` 被固定为各向同性高斯，而数据中各种因素的分布并非如此；先映射到一个不被强制为高斯的中间空间 `W`，可以让 latent 空间更解耦
- C. 让判别器更容易训练
- D. 替代合成网络中的卷积层

**Q2.** 对向量 `x = [1, 2, 3, 4]` 做 AdaIN（按总体标准差归一化），`scale = 2`、`bias = 1`。输出向量的均值和标准差分别是：

- A. 均值 2.5，标准差 1.118
- B. 均值 1，标准差 2
- C. 均值 0，标准差 1
- D. 均值 3.5，标准差 3.118

**Q3.** 截断技巧 `w' = ŵ + ψ·(w - ŵ)` 中，当 `ψ = 0` 时：

- A. 等于没有截断，样本最多样
- B. 所有样本都变成同一个输出 `G(ŵ)`（"平均脸"），多样性为零
- C. 生成器输出全为 0
- D. `w'` 变成 `z`

**Q4.** 风格混合时，用图像 A 的 `w` 驱动**低分辨率**的几层、图像 B 的 `w` 驱动**高分辨率**的几层。在训练好的人脸 StyleGAN 中，结果最可能是：

- A. 完全等于 A
- B. 继承 A 的姿态、脸型、身份等高层属性，以及 B 的颜色、光照等精细风格
- C. 继承 B 的姿态和身份，以及 A 的颜色
- D. 输出纯噪声

**Q5.** 将伪影与修复它的版本/技术正确配对的是：

- A. 水滴伪影 → StyleGAN3 的 alias-free 卷积；纹理粘连 → StyleGAN2 的 weight demodulation
- B. 水滴伪影 → StyleGAN2 的 weight demodulation；纹理粘连 → StyleGAN3 的 alias-free 卷积
- C. 两者都由截断技巧修复
- D. 两者都由 mapping network 修复

**Q6.** StyleGAN 逐层注入的噪声主要负责：

- A. 决定人物的身份与姿态
- B. 随机细节（毛孔、发丝位置），不影响全局结构
- C. 代替 mapping network
- D. 提高判别器准确率

**Q7.** 要把一张真实照片里的人"变老一点"，下列做法中技能文件**明确拒绝**的是：

- A. 用 e4e 编码器把照片 invert 到 W 空间，再沿年龄方向移动
- B. 用 PTI（pivotal tuning）提高重建保真度后再编辑
- C. 直接在 Z 空间里找年龄方向并编辑
- D. 编辑后用 ArcFace 余弦相似度检查身份是否保持

**Q8.** 关于 StyleGAN 的推理服务，以下哪项与讲义一致？

- A. 必须用 continuous batching 和 KV cache 才能获得高吞吐
- B. 每个请求的 FLOPs 相同、只需一次前向，静态 batch 即接近最优，continuous batching 没有收益
- C. 每张图需要 50 步采样
- D. 必须先经过 VAE 解码

---

## 三、动手 / 代码题

**Q9.** 运行 `main.py` 的第一段输出如下：

```text
=== compare: style inputs via AdaIN vs no AdaIN ===
sample 5 random z, look at std of output under each mode
  with AdaIN: mean -0.016  std 0.152
  no AdaIN  : mean +0.012  std 0.012
```

相关代码：

```python
def stylegan_forward(w, const, synth, noise_sigma, rng, adain_on=True):
    h = list(const)
    for i in range(3):
        W = synth[f"W{i}"]
        b = synth[f"b{i}"]
        pre = add(matmul(W, h), b)
        h = [leaky(x) for x in pre]
        if adain_on:
            scale = sum(synth[f"scale{i}"][j] * w[j] for j in range(len(w)))
            bias = sum(synth[f"bias{i}"][j] * w[j] for j in range(len(w)))
            h = adain(h, scale, bias)
        if noise_sigma > 0:
            h = [x + noise_sigma * rng.gauss(0, 1) for x in h]
    return h
```

(a) `adain_on=False` 时，5 个不同的 `z` 产生的 5 个输出有什么关系？为什么？
(b) 这里打印的 `std` 是在什么上计算的？它能说明"AdaIN 让输出更多样"吗？
(c) 讲义说这段代码"shows that injecting w via affine-modulation matches or beats concatenating z into the generator's input"。代码真的做了这个对比吗？要公平地对比，应该怎么改？

**Q10.** 阅读 `adain` 与 `mean_std`：

```python
def mean_std(xs):
    m = sum(xs) / len(xs)
    v = sum((x - m) ** 2 for x in xs) / len(xs)
    return m, math.sqrt(v + 1e-8)

def adain(features, scale, bias):
    m, s = mean_std(features)
    return [scale * (f - m) / s + bias for f in features]
```

(a) 证明 `adain` 输出向量的均值恰为 `bias`，标准差约为 `|scale|`。
(b) 这意味着在本玩具网络中，**最后一层**的 AdaIN 对输出起什么作用？`w` 一共通过多少个标量影响输出？与真实 StyleGAN 的 AdaIN 有何不同？
(c) `scale` 是 `w` 的线性函数，可能为负或接近 0。分别会发生什么？真实实现通常怎么避免？

**Q11.** 讲义练习 2 提到"混合正则化（mixing regularization）"。请实现

```python
def stylegan_forward_mix(w_a, w_b, crossover, const, synth, noise_sigma, rng):
    """第 i 层 (i < crossover) 用 w_a 的风格，其余层用 w_b。"""
```

并用 `main()` 同样的初始化（`random.Random(3)`）各采一个 `w_a`、`w_b`，打印 `crossover = 0, 1, 2, 3` 的结果。验证两个边界情况，并解释中间情况为什么几乎等于 `G(w_b)`。

---

## 四、面试高频题

**Q12.**（基础必考）StyleGAN 相对 DCGAN 做了哪些架构改动？每个改动解决了什么问题？

**Q13.**（原理深挖）AdaIN 为什么能代表"风格"？StyleGAN2 为什么用 weight demodulation 取代 AdaIN？请写出 modulation / demodulation 的计算。

**Q14.**（原理深挖）为什么截断技巧要在 `W` 空间而不是 `Z` 空间做？`ψ` 怎么选？path-length 正则化又是在约束什么？

**Q15.**（工程实践）设计一个"上传自拍 → 编辑年龄/笑容"的产品 pipeline。inversion 方法怎么选？在 W、W+、StyleSpace 中哪个空间编辑？编辑方向从哪来？怎么评估身份是否保持？

**Q16.**（场景设计）一家公司要做"虚拟头像生成"服务，峰值 QPS 很高，只生成人脸。你会选 StyleGAN3 还是 SDXL？如果只有 100 张目标风格的图片，怎么做领域适配？

**Q17.**（追问型）讲义的 Production note 写道："Lower ψ at peak load, raise it for premium users." 请评价：调低 ψ 能降低服务负载吗？ψ 在服务层真正控制的是什么？

---

## 五、参考答案与解析

### Q1 — 答案：B

训练数据中各因素的组合分布往往很"弯曲"（例如某些属性组合根本不存在），如果直接用各向同性高斯 `Z` 去覆盖它，`Z` 到图像的映射必须扭曲，导致纠缠。mapping network 让中间空间 `W` "不必是高斯、可以适应数据形状"（讲义："W is not forced to be Gaussian — it learns a data-adapted shape"），合成网络就可以用更线性、更解耦的方式使用它。它不减少参数（A 错，反而多了 8 层 MLP）。

### Q2 — 答案：B

AdaIN 先归一化到均值 0、标准差 1，再乘 `scale`、加 `bias`，所以输出均值 = `bias = 1`，标准差 = `|scale| = 2`。验算：均值 2.5，总体标准差 `√1.25 ≈ 1.118`，归一化后 `[-1.342, -0.447, 0.447, 1.342]`，输出 `[-1.683, 0.106, 1.894, 3.683]`，均值 1、标准差 2。A 是原始统计量，C 是只归一化不重新风格化的结果。这正是"风格 = 一阶、二阶统计量"的含义：AdaIN 把原来的统计量**替换**成由 `w` 决定的统计量。

### Q3 — 答案：B

`ψ = 0` 时 `w' = ŵ`，无论采到什么 `z`，输出都是 `G(ŵ)`——数据集的"平均样本"（人脸模型里就是一张平均脸）。`ψ = 1` 才是不截断（A 描述的是 ψ=1）。本节运行结果中 `psi=0.0` 那一行就是 `G(ŵ)`，随 ψ 增大逐渐靠近 `G(w_test)`。

### Q4 — 答案：B

讲义："You can swap styles between two images by using image A's w for the low-resolution levels and image B's w for the high." 低分辨率层决定粗粒度结构（姿态、脸型、身份），高分辨率层决定细粒度风格（颜色、光照、微纹理）。注意这是训练好的真实 StyleGAN 的行为；本节的玩具网络没有训练，层次分工并不成立（见 Q11）。

### Q5 — 答案：B

讲义 Pitfalls：水滴伪影由 AdaIN 对特征图的归一化引起，StyleGAN2 的 weight demodulation 改为缩放卷积权重来修复；纹理粘连（插值时纹理跟着像素坐标而不是物体走）由 StyleGAN3 的 alias-free 卷积（加窗 sinc 滤波器）修复。截断（C）只是推理时的采样技巧；mapping network（D）是 StyleGAN1 就有的。

### Q6 — 答案：B

讲义："Per-layer noise... Controls stochastic detail without affecting global structure." 本节第三段输出就是演示：同一个 `w`、不同噪声种子，输出有差异。身份与姿态（A）由 `w` 决定。

### Q7 — 答案：C

技能文件："Refuse any pipeline that edits directly in Z (entangled)." Z 空间是纠缠的，沿一个方向移动会同时改变多个属性。A、B 是标准做法；D 是推荐的评估（ArcFace 余弦相似度衡量身份保持）。技能文件还规定：W 中超过 1.5σ 的大幅编辑必须做身份检查。

### Q8 — 答案：B

讲义 Production note："No scheduler, no batcher. Static batch at the target occupancy is optimal. Continuous batching (essential for LLMs and diffusion) provides zero benefit because every request takes the same FLOPs." StyleGAN 只有一次前向、没有 VAE 解码（"no VAE decode"）、没有 KV cache。C、D 描述的是扩散流水线。

### Q9 — 参考答案

**(a) 5 个输出完全相同。** `adain_on=False` 时，`w` 只在 `if adain_on:` 分支里被使用；跳过这个分支后，网络的输入只有固定的 `const`，而噪声 `noise_sigma=0.0`。于是输出与 `z` 完全无关，是一个确定的 6 维向量。我额外打印过两种模式下的前两行，`no AdaIN` 的每一行都是 `[0.02, 0.021, -0.001, 0.03, 0.008, -0.004]`。

**(b)** `flat = [v for row in outs for v in row]` 把 5×6 个数摊平后求标准差，混合了"样本之间"和"同一向量内 6 个维度之间"两种差异。`no AdaIN` 的 0.012 **全部来自维度之间**，样本之间的差异是 0。所以这个对比真正说明的是"关掉 AdaIN 后 `w` 根本进不了网络"，而不是"AdaIN 让输出更多样"。要衡量多样性，应该**逐维度**计算跨样本的标准差再平均。

**(c) 没有做。** 代码里没有"把 `z` 拼接到输入"的基线，"无 AdaIN"模式下生成器干脆不接收任何 latent，这是一个不公平的稻草人对比；而且两个网络都**没有训练**，谈不上谁"更好"。公平对比应该：
1. 实现基线：`h = list(const) + z`（或 `w`）作为第一层输入（第一层输入维度相应增大），其余结构不变；
2. 两种生成器都接一个判别器，在同一数据上训练相同步数；
3. 用同一个分布指标（如 1-D W1 距离、FID）比较，并比较 latent 插值时输出变化是否平滑、是否解耦。

### Q10 — 参考答案

**(a)** 记 `n = (f - m)/s`。`n` 的均值是 `(mean(f) - m)/s = 0`；方差是 `var(f)/s² = v/(v + 1e-8) ≈ 1`。输出 `y = scale·n + bias`：均值 `= scale·0 + bias = bias`；标准差 `= |scale|·std(n) ≈ |scale|`（`v` 极小时会略小于 `|scale|`）。我在本节模型上逐样本验证过：例如某个样本输出均值 -0.0680、标准差 0.2180，恰好等于该样本的 `bias2 = -0.0680`、`|scale2| = 0.2180`。

**(b)** 最后一层的 AdaIN **直接决定了输出向量的均值和标准差**，前面的层只能影响"归一化后的形状"（6 个数之间的相对模式）。在本玩具里每层只有一个标量 scale、一个标量 bias，`w` 一共只通过 **3 层 × 2 = 6 个标量** 影响输出。
真实 StyleGAN 的不同之处：
- 归一化是**逐通道、在空间维度上**进行的（每个特征图单独算均值方差），而不是对整个向量；
- 每层有**逐通道**的 scale/bias（512 个通道就有 2×512 个），由 `w` 经学习的仿射层得到；
- 所以 `w` 在每一层都能独立控制每个通道的统计量，信息量大得多。

**(c)**
- `scale < 0`：归一化后的模式被**翻转**（正负颠倒），输出依然有效但语义相反；
- `scale ≈ 0`：所有维度被压成同一个值 `bias`，信息几乎全部丢失，且反向传播时经过这一层的梯度也接近 0；
- 真实实现：仿射层的 bias 初始化为 1，即 `scale = 1 + affine(w)` 的形式，使初始时 scale 接近 1、远离 0 和负数；StyleGAN2 进一步用 weight demodulation 取代对激活的显式归一化。

### Q11 — 参考答案

```python
def stylegan_forward_mix(w_a, w_b, crossover, const, synth, noise_sigma, rng):
    """第 i 层 (i < crossover) 用 w_a 的风格，其余层用 w_b。"""
    h = list(const)
    for i in range(3):
        w = w_a if i < crossover else w_b
        pre = add(matmul(synth[f"W{i}"], h), synth[f"b{i}"])
        h = [leaky(x) for x in pre]
        scale = sum(synth[f"scale{i}"][j] * w[j] for j in range(len(w)))
        bias = sum(synth[f"bias{i}"][j] * w[j] for j in range(len(w)))
        h = adain(h, scale, bias)
        if noise_sigma > 0:
            h = [x + noise_sigma * rng.gauss(0, 1) for x in h]
    return h
```

用 `main()` 同样的初始化顺序（mapping → synth → const）后各采一个 `w_a`、`w_b`，实测输出：

```text
G(w_a)       ['+0.09', '+0.06', '-0.01', '+0.15', '-0.23', '-0.47']
G(w_b)       ['+0.03', '+0.02', '+0.02', '+0.05', '-0.02', '-0.07']
crossover=0 ['+0.03', '+0.02', '+0.02', '+0.05', '-0.02', '-0.07']
crossover=1 ['+0.03', '+0.03', '+0.02', '+0.04', '-0.02', '-0.07']
crossover=2 ['+0.03', '+0.03', '+0.02', '+0.04', '-0.03', '-0.07']
crossover=3 ['+0.09', '+0.06', '-0.01', '+0.15', '-0.23', '-0.47']
```

- **边界验证**：`crossover=0` 全部用 `w_b`，等于 `G(w_b)`；`crossover=3` 全部用 `w_a`，等于 `G(w_a)`。
- **中间情况几乎等于 `G(w_b)`**：由 Q10 的结论，最后一层（第 2 层）用的是 `w_b`，它的 AdaIN 把输出的均值、标准差直接设成由 `w_b` 决定的值；`w_a` 只能通过前面的层改变"归一化后的相对模式"，在这个未训练的小网络里影响很小（只在第 2、5 维看到 0.01 的变化）。
- **与真实 StyleGAN 的区别**：真实网络经过训练，并且在训练时使用了混合正则化（随机选交叉点、用两个 `w`），迫使相邻层的风格不相关，从而形成"低层管结构、高层管细节"的分工。这个玩具网络既没训练也没有空间维度，所以看不到这种分工——它只是演示了"按层切换 `w`"的机制。

### Q12 — 参考回答要点

| 改动 | 解决的问题 |
|------|-----------|
| mapping network `Z → W`（8 层 MLP） | `Z` 被固定为高斯导致纠缠；`W` 可以适应数据，更解耦 |
| 合成网络从学习的常量开始，不再从 `z` 开始 | latent 不再"一次性"决定一切，而是逐层调制 |
| 每个分辨率都通过 AdaIN 注入 `w` | 每层可以被独立控制，支持风格混合（粗/中/细） |
| 逐层噪声 | 把随机细节（发丝、毛孔）从全局风格中分离出来 |
| 混合正则化 | 训练时随机用两个 `w`，防止相邻层风格相关，增强分层解耦 |
| 截断技巧（推理时） | 在质量和多样性之间提供一个旋钮 |
| progressive growing（StyleGAN1） | 先低分辨率后高分辨率，稳定高分辨率训练 |

- 加分点：说出后续 StyleGAN2（weight demodulation、path-length 正则、去掉 progressive growing 改用 skip/residual 结构）和 StyleGAN3（alias-free）各修了什么。

### Q13 — 参考回答要点

- **AdaIN 与风格**：在风格迁移研究中，特征图的逐通道均值和方差可以很好地刻画"纹理/风格"，而空间分布刻画"内容"。AdaIN 把每个通道归一化后，用 `w` 给出的 scale/bias 替换其统计量——相当于"保留内容的空间结构、替换风格统计量"。
- **为什么换掉**：AdaIN 对每个特征图单独归一化，抹掉了特征之间相对幅度的信息；生成器为了绕过这一点，学会在特征图中制造一个很强的局部尖峰来"偷渡"信号强度，表现为图像上的水滴状伪影（讲义的说法是"AdaIN zeroed out mean"）。
- **modulation / demodulation**（StyleGAN2）：不再归一化激活，而是直接作用于卷积权重：
  - 调制：`w'_{ijk} = s_i · w_{ijk}`（`s_i` 是由 latent 得到的第 i 个输入通道的 scale）；
  - 解调：`w''_{ijk} = w'_{ijk} / √( Σ_{i,k} (w'_{ijk})² + ε )`，按"假设输入单位方差时输出也单位方差"来归一化每个输出通道 j。
  - 这样统计上达到与 AdaIN 类似的效果，但基于期望统计量而不是逐样本的实际统计量，消除了水滴伪影。
- 加分点：说明 demodulation 可以和卷积融合成 grouped convolution 高效实现。

### Q14 — 参考回答要点

- **为什么在 W 截断**：`ŵ` 是 `W` 空间里样本的平均位置，往 `ŵ` 收缩就是往"训练数据中最典型、密度最高"的区域收缩，样本质量提高。`Z` 是各向同性高斯，其均值 0 经过非线性映射后不一定对应高质量区域；而且 `Z` 纠缠，收缩效果不可控。`W` 更解耦，沿 `w - ŵ` 收缩时各属性按比例变得"更典型"，行为更可预测。
- **ψ 的取舍**：`ψ < 1` 提高平均质量、降低多样性（模式覆盖变窄），`ψ = 1` 保留全部多样性但更容易出现低质量样本。演示和产品常用 `ψ ≈ 0.7`；讲义提醒需要多样性（如做数据增强、评估 recall）时用 `ψ = 1.0`。计算 FID 时一般不截断。
- **path-length 正则化**（StyleGAN2）：惩罚"`w` 移动单位距离时图像变化幅度"偏离一个常数，即让 `W → 图像` 的雅可比在各处尺度均匀。效果：`W` 空间更平滑，插值更自然，inversion 也更容易。
- 常见误区：认为截断改变了模型或计算量——它只是推理时对 `w` 做的一个线性插值。

### Q15 — 参考回答要点

1. **Inversion 方法**（技能文件）：e4e（编码器，快、保真度较低，但编辑性好）→ ReStyle（迭代编码器，更准）→ HyperStyle（超网络调整生成器权重）→ PTI（pivotal tuning：先 invert 得到 pivot `w`，再对生成器做小幅微调，高保真）→ 直接在 W 中做优化（慢但灵活）。按"保真度 vs 速度"选。
2. **latent 空间**：W（最解耦、保真度最低）、W+（每层一个 `w`，保真度更高但可能偏离分布、编辑性下降）、StyleSpace（通道级，适合精细局部编辑）。
3. **编辑方向**：InterFaceGAN（在带属性标签的样本上训练线性 SVM，法向量即方向）、GANSpace（对 `W` 做 PCA 找主方向）、StyleSpace 通道、或用属性分类器引导。
4. **评估与预算**：ArcFace 余弦相似度衡量身份保持、LPIPS 衡量与原图的感知差异、属性分类器分数衡量编辑强度；设定 LPIPS 阈值，超过则回滚；W 中超过 1.5σ 的编辑必须做身份检查。
5. **边界**：讲义提醒 inversion 本身是有损的；技能文件规定"把他变成卡通"这类开放域编辑应交给扩散 + IP-Adapter，而不是 StyleGAN。

### Q16 — 参考回答要点

- **选 StyleGAN3**：只生成人脸（窄领域）、高 QPS。讲义：4090 上 1024² 人脸 <10 ms，`num_steps = 1`，无 VAE 解码、无 cross-attention；50 步 SDXL + VAE 解码约 3 s，差约 300 倍，窄领域产品在 TCO 上胜出。
- **服务形态**：每个请求 FLOPs 相同，静态 batch 在目标占用率下即最优，不需要复杂调度；用 `ψ` 控制样本质量/方差。
- **100 张图的领域适配**：讲义 Use It 表——"Domain adaptation from a few images: Freeze mapping network, fine-tune synthesis"；"Avatar pipelines: StyleGAN3 w/ ADA for low-data fine-tune"（ADA：自适应判别器数据增强，防止判别器在小数据上过拟合）。
- **何时改用扩散**：需要文本控制、开放风格、多种主体时（讲义："Multi-modal or text-conditioned generation — Don't — use diffusion"）。

### Q17 — 参考回答要点

- **不能**。截断只是推理时 `w' = ŵ + ψ·(w - ŵ)` 这一次向量运算，生成器的前向计算量与 `ψ` 完全无关，调低 ψ 不会让 GPU 更轻松、不能提高吞吐或降低延迟。
- **ψ 真正控制的是样本分布**：ψ 越小，样本越集中在"平均、典型、高质量"的区域，崩坏样本更少但更千篇一律；ψ 越大，多样性越高、出现怪异样本的风险越大。所以讲义同一段里说"Truncation ψ is the safety knob... the only lever the serving layer has over sample variance"是准确的。
- **合理的产品用法**：按场景而非负载调 ψ——例如面向大众的默认生成用较低 ψ 保证"不翻车"，需要多样性的场景（素材库、数据增强）用较高 ψ；如果把"高 ψ = 更多样"当作付费卖点也说得通，但与"峰值负载"无关。
- 加分点：面试中遇到这类说法，先区分"计算成本旋钮"（步数、分辨率、精度、batch）和"分布旋钮"（ψ、CFG scale、温度），这是判断技术方案时很实用的框架。

---

## 六、关联知识点

### 前置知识
- [阶段 08 · 03 GANs — 生成器与鉴别器](../../03-gans-generator-discriminator/docs/zh.md)：对抗训练、模式崩溃，以及 StyleGAN 在 GAN 变体表中的位置。
- [阶段 08 · 04 有条件 GANs & Pix2Pix](../../04-conditional-gans-pix2pix/docs/zh.md)：FiLM、SPADE 等"用条件调制特征"的思想，AdaIN 是同一家族。
- [阶段 04 · 03 CNN：从 LeNet 到 ResNet](../../../04-computer-vision/03-cnns-lenet-to-resnet/docs/zh.md)：卷积、上采样、通道与特征图。
- [阶段 03 · 07 正则化](../../../03-deep-learning-core/07-regularization/docs/zh.md)：理解 path-length 正则、混合正则化这类"约束 latent 几何"的正则项。

### 本节被哪些后续内容用到
- [阶段 08 · 06 DDPM 从零实现](../../06-diffusion-ddpm-from-scratch/docs/zh.md)：扩散模型用类似 FiLM/AdaIN 的方式注入时间步；接管了开放域生成。
- [阶段 08 · 08 ControlNet、LoRA 与条件控制](../../08-controlnet-lora-conditioning/docs/zh.md)：扩散时代的可控编辑，对应讲义"开放域编辑交给扩散 + IP-Adapter"。
- [阶段 08 · 09 局部重绘、扩图与图像编辑](../../09-inpainting-outpainting-editing/docs/zh.md)：与 StyleGAN inversion 编辑形成对照的扩散编辑方法。
- [阶段 08 · 14 评估：FID、CLIP 分数、人类偏好](../../14-evaluation-fid-clip-score/docs/zh.md)：截断对 FID、precision/recall 的影响。
- [阶段 04 · 09 图像生成：GAN](../../../04-computer-vision/09-image-generation-gans/docs/zh.md)：视觉方向的 GAN 实践。

### 延伸关键词
`mapping network / W 空间` · `AdaIN` · `style mixing / mixing regularization` · `truncation trick (ψ)` · `weight modulation / demodulation` · `path-length regularization` · `alias-free GAN` · `W+ / StyleSpace` · `e4e / ReStyle / HyperStyle / PTI` · `InterFaceGAN / GANSpace` · `ADA (adaptive discriminator augmentation)` · `ArcFace 身份相似度`
