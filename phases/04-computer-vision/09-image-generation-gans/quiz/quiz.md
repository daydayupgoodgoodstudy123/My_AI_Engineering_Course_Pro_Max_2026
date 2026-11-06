# 测验 · 图像生成 — GANs（Image Generation — GANs）

> **阶段 04 · 计算机视觉 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 生成器与判别器 | G：噪声 `z ~ N(0, I)` → 图像；D：图像 → 一个标量（是真图的 logit/概率）。用"学出来的损失"替代 MSE，避免生成模糊的平均图 |
| 2 | Minimax 目标 | `min_G max_D E_x[log D(x)] + E_z[log(1 − D(G(z)))]`；全局均衡点 `p_G = p_data`，此时 D 处处输出 0.5，JS 散度为 0 |
| 3 | 非饱和损失 | 训练初期 `D(G(z)) ≈ 0`，`log(1 − D(G(z)))` 梯度消失；改用 `L_G = −E[log D(G(z))]`，梯度在此处最大 |
| 4 | DCGAN 五条规则 | 用带步长卷积代替池化；G、D 都用 BN（G 输出层和 D 输入层除外）；去掉全连接；G 用 ReLU + 输出 tanh；D 用 LeakyReLU(0.2) |
| 5 | 交替训练与 `detach` | 每个 batch 先更新 D 一次、再更新 G 一次；D 步里对 `G(z)` 做 `detach()`，不让 D 的损失往 G 里传梯度 |
| 6 | DCGAN 优化器 | `Adam(lr=2e-4, betas=(0.5, 0.999))`，较小的 β1 降低动量，适应不断变化的对抗目标 |
| 7 | 三种失败模式 | 模式崩溃（样本多样性下降）、D 完胜（D 准确率≈100%、G 梯度消失）、振荡（两个损失剧烈摆动不收敛） |
| 8 | 稳定化技巧 | 谱归一化（限制 D 每层的 Lipschitz 常数）、TTUR（D 学习率是 G 的 2–4 倍）、标签平滑、Wasserstein 损失 |
| 9 | 评估 | 必须肉眼看样本；FID（Inception-v3 特征分布距离，越低越好）是社区标准；IS 较脆弱；Precision/Recall 分别衡量质量和覆盖度 |

### 核心技能（能动手做到）

- [ ] 写出 DCGAN 的 G 和 D，并用转置卷积尺寸公式推出 `1 → 4 → 8 → 16 → 32` 的空间变化
- [ ] 写出完整的 `train_step`（D 步 + G 步、BCE-with-logits、`detach`），并说清每一行对应哪个损失公式
- [ ] 算出均衡状态下本节代码打印的 D、G 损失理论值，并据此读训练曲线
- [ ] 把判别器的 BatchNorm 换成 `spectral_norm`，并正确处理卷积的 bias
- [ ] 实现 one-sided 标签平滑与 TTUR，并能解释各自针对哪种失败模式
- [ ] 正确采样：`eval()` → 生成 → `train()`，把 tanh 输出从 [-1,1] 映射到 [0,1]

---

## 二、基础自测（选择题）

**Q1.** 训练初期判别器对假图的输出 `D(G(z)) = sigmoid(s) = 0.01`。对 D 的 logit `s` 求导，饱和损失 `log(1 − D(G(z)))` 与非饱和损失 `−log D(G(z))` 的梯度大小分别约为：

- A. 0.01 和 0.99
- B. 0.99 和 0.01
- C. 两者都约为 0.5
- D. 两者都约为 0

**Q2.** 假设训练达到理论均衡：D 对任何输入都输出 0.5。本节代码 `train_step` 返回的 `loss_d` 与 `loss_g` 约为：

- A. 0 和 0
- B. 0.693 和 0.693
- C. 1.386 和 0.693
- D. 0.5 和 0.5

**Q3.** 下列哪一条**不是** DCGAN 的架构规则？

- A. 用带步长的卷积代替池化
- B. G 的输出层使用 tanh
- C. D 的每一层使用 LeakyReLU(0.2)
- D. 在 D 中用最大池化做下采样，并在末尾接两层全连接

**Q4.** 无论输入什么噪声，生成器都输出几乎一样的图像；D 损失很低，G 损失来回振荡。这是：

- A. 振荡（oscillation）
- B. 模式崩溃（mode collapse）
- C. 正常收敛
- D. 数据集太大

**Q5.** 同事报告：D 损失趋近 0，G 损失越来越大并且停在高位。下列哪个修复**最不对症**？

- A. 给判别器加谱归一化
- B. 对真实标签做标签平滑（用 0.9 代替 1.0）
- C. 降低判别器学习率或减小判别器容量
- D. 把判别器的学习率提高 4 倍，让它更快收敛

**Q6.** DCGAN 用 `Adam(betas=(0.5, 0.999))` 而不是默认的 `(0.9, 0.999)`，原因是：

- A. 默认值在 CUDA 上不可用
- B. 较小的 β1 意味着更短的动量记忆；对抗博弈中对手每一步都在变，长动量会让优化器在过时的方向上走太久，引起不稳定
- C. β1 越小学习率越大
- D. 这是教程里流传的笔误

**Q7.** 关于 FID，下列说法正确的是：

- A. FID 越高说明生成质量越好
- B. 它比较真实图像与生成图像在 Inception-v3 特征空间中的分布（均值与协方差），越低越好
- C. 它是生成图与最近真实图之间的像素 MSE
- D. 它只衡量多样性，不衡量质量

---

## 三、动手 / 代码题

**Q8.** 对于本节代码的 `Generator(z_dim=64, img_channels=3, feat=32)`：

```python
        self.net = nn.Sequential(
            nn.ConvTranspose2d(z_dim, feat * 4, 4, 1, 0, bias=False),
            nn.BatchNorm2d(feat * 4),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(feat * 4, feat * 2, 4, 2, 1, bias=False),
            # ...
            nn.ConvTranspose2d(feat, img_channels, 4, 2, 1, bias=False),
            nn.Tanh(),
        )

    def forward(self, z):
        return self.net(z.view(z.size(0), -1, 1, 1))
```

(a) 输入 `z` 形状 `(32, 64)`，写出每个转置卷积之后的形状，并用尺寸公式验证。
(b) 计算 G 的参数总量（`main()` 第一行会打印它）。
(c) 讲义说"四个转置卷积都是 `kernel_size=4, stride=2, padding=1`，所以每层都把尺寸翻倍"，这句话准确吗？

**Q9.** 关于 D 步中的 `detach`：

```python
    opt_d.zero_grad()
    d_real = D(real)
    d_fake = D(G(z).detach())
    loss_d = (F.binary_cross_entropy_with_logits(d_real, torch.ones_like(d_real))
              + F.binary_cross_entropy_with_logits(d_fake, torch.zeros_like(d_fake)))
    loss_d.backward()
    opt_d.step()

    opt_g.zero_grad()
    d_fake = D(G(z))
    # ...
```

(a) 在**本文件这种写法**下，如果删掉 `.detach()`，G 的参数更新会被污染吗？代价是什么？
(b) 换一种写法：每次迭代开头同时 `opt_d.zero_grad(); opt_g.zero_grad()`，之后不再清零。这时删掉 `.detach()` 会发生什么？从梯度方向解释为什么这很糟糕。

**Q10.** `main()` 中使用 `Discriminator(..., use_sn=True)`。阅读：

```python
        def conv(in_c, out_c, bn):
            c = nn.Conv2d(in_c, out_c, 4, 2, 1, bias=not bn)
            if use_sn:
                c = spectral_norm(c)
            layers.append(c)
            if bn and not use_sn:
                layers.append(nn.BatchNorm2d(out_c))
            layers.append(nn.LeakyReLU(0.2, inplace=True))
```

(a) `use_sn=True` 时，第 2、3 个卷积层有没有偏置？有没有 BN？这合理吗？
(b) 给出修正写法。
(c) 原代码下 D 的参数量是多少？修正后是多少？

**Q11.** 在 `train_step` 的基础上实现两个稳定化技巧：①one-sided 标签平滑（真实标签用 0.9）；②TTUR（D 学习率 4e-4、G 学习率 1e-4）。写出需要改动的代码，并说明它们各自针对讲义中的哪种失败模式。

---

## 四、面试高频题

**Q12.**（基础必考）写出 GAN 的目标函数，推导固定 G 时的最优判别器，并说明均衡时 G 在最小化什么散度。

**Q13.**（原理深挖）GAN 训练为什么不稳定？模式崩溃的成因是什么？请列举至少四种工业界常用的稳定化手段并说明原理。

**Q14.**（原理深挖）谱归一化做了什么？它和 WGAN / WGAN-GP 中的 Lipschitz 约束是什么关系？

**Q15.**（工程实践）你训练了一个人脸生成 GAN，怎么评估它？FID 有哪些使用陷阱？

**Q16.**（场景设计）2026 年做图像生成，什么时候还会选 GAN，什么时候选扩散模型？GAN 的思想在扩散时代还在哪里发挥作用？

---

## 五、参考答案与解析

### Q1 — 答案：A

设 `D = sigmoid(s)`。
- 饱和形式：`d/ds log(1 − sigmoid(s)) = −sigmoid(s) = −0.01`，幅度只有 0.01，G 几乎拿不到信号；
- 非饱和形式：`d/ds [−log sigmoid(s)] = −(1 − sigmoid(s)) = −0.99`，幅度 0.99。

两者推动方向相同（都想让 `D(G(z))` 变大），但在 G 最弱、最需要学习的初期，梯度大小相差约 100 倍，这就是讲义所说的"every modern GAN trains with this variant"。

### Q2 — 答案：C

`loss_d` 是两项 BCE 之和：真图 `−log 0.5` + 假图 `−log(1 − 0.5)` = `2 ln2 ≈ 1.386`；`loss_g = −log 0.5 = ln2 ≈ 0.693`。这两个数也正好是训练刚开始（D 随机初始化、输出接近 0.5）时的近似值。读曲线时：D 损失长期在 1.4 附近、G 损失在 0.7 附近小幅波动，往往是健康的对抗状态；D 损失→0 才是警报。B 忽略了 `loss_d` 是两项相加。

### Q3 — 答案：D

DCGAN 规则恰好相反：去掉池化（用带步长卷积），在较深结构中去掉全连接层。A、B、C 都是讲义列出的规则。

### Q4 — 答案：B

"噪声变了输出不变"就是模式崩溃：G 找到了少数几种能骗过 D 的样本就不再探索。讲义给出的信号是"D loss low、G loss oscillating、sample variety drops"，修复包括 minibatch discrimination、谱归一化、类别条件。

### Q5 — 答案：D

症状是"D 完胜"：D 太强导致 G 梯度消失。对症做法是削弱 D 或换不饱和的损失：A 限制 D 的陡峭程度；B 不让 D 对真图过度自信；C 让 D 学慢一点、小一点。D 选项会让 D 更强，雪上加霜。注意讲义里 TTUR 是"D 学得比 G 快"，它针对的是**振荡**，而不是 D 完胜——同一个旋钮在不同失败模式下方向相反，这正是这道题的陷阱。

### Q6 — 答案：B

Adam 的 β1=0.9 相当于对约 10 步的梯度做指数平均。对固定目标这很好，但 GAN 里每一步 D 和 G 都在改变对方的损失地形，长动量会让更新"惯性"太大、反应迟钝，引起振荡。Radford 等人发现 β1=0.5 稳定得多，此后成为 GAN 的默认值。

### Q7 — 答案：B

FID 把两组图片送进 Inception-v3 取特征，各自拟合一个高斯（均值 μ、协方差 Σ），再算两个高斯之间的 Fréchet 距离：`‖μ_r − μ_g‖² + Tr(Σ_r + Σ_g − 2(Σ_r Σ_g)^{1/2})`。同时受质量（均值偏移）与多样性（协方差）影响，越低越好。C 是像素级度量，恰恰是讲义说的"不适合衡量生成质量"的那类。

### Q8 — 参考答案

(a) 转置卷积输出尺寸：`H_out = (H_in − 1)·stride − 2·padding + kernel_size`。

| 层 | 参数 (k, s, p) | 输出形状 |
|----|---------------|---------|
| `z.view` | — | `(32, 64, 1, 1)` |
| ConvT1 | (4, 1, 0) | `(0·1 − 0 + 4) = 4` → `(32, 128, 4, 4)` |
| ConvT2 | (4, 2, 1) | `(3·2 − 2 + 4) = 8` → `(32, 64, 8, 8)` |
| ConvT3 | (4, 2, 1) | `(7·2 − 2 + 4) = 16` → `(32, 32, 16, 16)` |
| ConvT4 + Tanh | (4, 2, 1) | `(15·2 − 2 + 4) = 32` → `(32, 3, 32, 32)` |

`z.view(z.size(0), -1, 1, 1)` 把噪声向量当成一张 1×1、64 通道的"图像"，第一个转置卷积相当于一个全连接层把它投影成 4×4 的特征图。

(b) `ConvTranspose2d` 权重形状是 `(in, out, k, k)`，且都没有 bias：
- `64·128·16 = 131,072`；`128·64·16 = 131,072`；`64·32·16 = 32,768`；`32·3·16 = 1,536`
- 三个 BN：`2·(128 + 64 + 32) = 448`
- 合计 **296,896**，即 `G params: 296,896`。

(c) 不准确。只有后三个转置卷积是 `(4, 2, 1)`、把尺寸翻倍；第一个是 `(4, 1, 0)`，作用是把 1×1 的噪声"展开"成 4×4。代码与讲义的代码块本身都是对的，只是讲义的文字描述有误。

### Q9 — 参考答案

(a) **不会被污染，但浪费计算。** 删掉 `detach` 后，`loss_d.backward()` 会一路反传进 G，为 G 的参数算出梯度并累加到 `.grad` 里；`opt_d.step()` 只更新 D 的参数，所以 D 的更新不受影响；接着 `opt_g.zero_grad()` 把这些梯度清空，G 步重新计算。代价是多做一次穿过 G 的反向传播，以及保留 G 的计算图所需的显存。

(b) **会污染 G 的更新。** D 步的损失里关于假图的那一项是 `−log(1 − D(G(z)))`，它对 G 参数的梯度方向是"让 `D(G(z))` 变小"，也就是让假图**更容易被识破**——与 G 自己的目标完全相反。这些梯度会残留在 G 的 `.grad` 里，再与 G 步的梯度相加，等于部分抵消了 G 的学习信号，训练变慢甚至失败。所以讲义说 `detach` 是"critical"、忘记它是"经典新手 bug"：在更常见的"统一在开头清零"或"复用同一份 `fake` 张量"的写法里，它确实会出错。`detach` 让代码对 `zero_grad` 的位置不敏感，是更稳妥的写法。

### Q10 — 参考答案

(a) `use_sn=True` 时：第 2、3 层调用 `conv(..., bn=True)`，于是 `bias=not bn = False`；又因为 `use_sn` 为真，BN 也不会被添加。结果这两层**既没有 bias 也没有 BN**。卷积后不接 BN 时去掉 bias 没有道理（`bias=False` 的前提是"后面有 BN 的 β 代替偏置"），这会让模型少一点表达能力。讲义 Step 6 的 `build_sn_discriminator` 里所有卷积都使用默认的 `bias=True`。影响不大但属于实现瑕疵。

(b) 修正：bias 只在"真的加了 BN"时才去掉。

```python
        def conv(in_c, out_c, bn):
            use_bn = bn and not use_sn
            c = nn.Conv2d(in_c, out_c, 4, 2, 1, bias=not use_bn)
            if use_sn:
                c = spectral_norm(c)
            layers.append(c)
            if use_bn:
                layers.append(nn.BatchNorm2d(out_c))
            layers.append(nn.LeakyReLU(0.2, inplace=True))
```

(c) 原代码：`(3·32·16 + 32) + 32·64·16 + 64·128·16 + (128·16 + 1) = 1,568 + 32,768 + 131,072 + 2,049 = 167,457`，即 `D params: 167,457`。修正后第 2、3 层各多出 64 和 128 个 bias：`167,457 + 192 = 167,649`。（`spectral_norm` 把 `weight` 换成参数 `weight_orig`，并新增 `weight_u`、`weight_v` 两个 buffer，参数个数不变。）

### Q11 — 参考答案

```python
def train_step(G, D, real, z, opt_g, opt_d, device, real_label=0.9):
    real = real.to(device)

    opt_d.zero_grad()
    d_real = D(real)
    d_fake = D(G(z).detach())
    loss_d = (F.binary_cross_entropy_with_logits(d_real, torch.full_like(d_real, real_label))  # ① 标签平滑
              + F.binary_cross_entropy_with_logits(d_fake, torch.zeros_like(d_fake)))
    loss_d.backward()
    opt_d.step()

    opt_g.zero_grad()
    d_fake = D(G(z))
    loss_g = F.binary_cross_entropy_with_logits(d_fake, torch.ones_like(d_fake))  # G 的目标仍是 1.0
    loss_g.backward()
    opt_g.step()
    return loss_d.item(), loss_g.item()

# ② TTUR：D 学得比 G 快（这里是 4 倍）
opt_g = torch.optim.Adam(G.parameters(), lr=1e-4, betas=(0.5, 0.999))
opt_d = torch.optim.Adam(D.parameters(), lr=4e-4, betas=(0.5, 0.999))
```

- **标签平滑**只作用于 D 的真实标签（one-sided），不改假标签、也不改 G 的目标。它让 D 不会对真图过度自信，logit 不会被推到极端，从而缓解**"D 完胜、G 梯度消失"**。
- **TTUR** 让 D 在每一步都更接近当前 G 下的最优判别器，G 收到的梯度更"准"，讲义把它列为**振荡**的修复手段。
- 注意平滑后 `loss_d` 的最小值不再是 0，读曲线时基线会变化。

### Q12 — 参考回答要点

- **目标**：`min_G max_D V(D,G) = E_{x~p_data}[log D(x)] + E_{z~p_z}[log(1 − D(G(z)))]`。
- **最优判别器**：固定 G，把 V 写成对 x 的积分 `∫ [p_data(x) log D(x) + p_g(x) log(1 − D(x))] dx`，对每个 x 逐点最大化 `a·log y + b·log(1 − y)`，得 `y = a/(a+b)`，即 `D*(x) = p_data(x) / (p_data(x) + p_g(x))`。
- **代回去**：`V(D*, G) = −log 4 + 2·JSD(p_data ‖ p_g)`，所以在 D 最优时，G 在最小化 JS 散度；最小值在 `p_g = p_data` 时取得，此时 `D* ≡ 0.5`，与讲义一致。
- **加分点**：指出这一分析假设 D 每一步都能达到最优、模型容量无限，实践中都不成立；当两个分布支撑集几乎不重叠时 JS 散度饱和为常数 `log 2`、梯度消失——这正是 WGAN 改用 Wasserstein 距离的动机。

### Q13 — 参考回答要点

- **不稳定的根源**：①不是最小化一个固定目标，而是在找两个玩家的鞍点/纳什均衡，梯度下降在博弈中天然可能绕圈（振荡）；②D 太强时 BCE 饱和，G 梯度消失；③高维数据分布支撑集低维，JS 散度对"几乎不重叠的分布"不敏感。
- **模式崩溃**：G 的目标只是"骗过当前的 D"，并没有任何项奖励多样性。若某几个样本恰好能骗过 D，G 就把所有 z 都映射过去；D 随后学会识别它们，G 再跳到另一个模式——表现为样本多样性下降或在少数模式间来回跳。
- **常用手段**：
  - 非饱和 G 损失（梯度不消失）；
  - 谱归一化（限制 D 的 Lipschitz 常数，避免 D 过陡）；
  - TTUR（D、G 不同学习率）；
  - 标签平滑（D 不过度自信）；
  - WGAN-GP / R1 梯度惩罚（约束 D 的梯度）；
  - minibatch discrimination / minibatch std（让 D 能看到 batch 内多样性，惩罚崩溃）；
  - 类别条件、更大 batch（讲义提到的模式崩溃修复）。
- **常见误区**：认为"D 损失越低越好"——D 完胜恰恰意味着 G 学不动了。

### Q14 — 参考回答要点

- **谱归一化**：把每层权重除以它的最大奇异值（谱范数）`W_SN = W / σ(W)`，σ 用幂迭代近似估计（每次前向迭代一步，`u`、`v` 存为 buffer），开销很小。线性层的 Lipschitz 常数就是 σ(W)，LeakyReLU 是 1-Lipschitz，所以逐层归一化后整个 D 的 Lipschitz 常数被约束在约 1 以内（讲义说"guarantees 1-Lipschitz"，严格说是一个近似的上界：幂迭代是估计值，卷积的谱范数也是按展平后的权重矩阵计算的）。
- **为什么有用**：D 不能变得任意陡峭，就不会把真假图的 logit 推到极端导致 G 梯度消失；也不依赖 batch 统计量，可以替代 BN。
- **与 WGAN 的关系**：WGAN 用 Wasserstein-1 距离替代 JS 散度，其对偶形式要求 critic 是 1-Lipschitz 函数。原始 WGAN 用权重裁剪粗暴实现，容量受损；WGAN-GP 在真假插值点上惩罚 `(‖∇D‖ − 1)²`；SN 则从结构上限制每层。三者都在"约束 D 的平滑性"。
- **加分点**：SN 常与 hinge loss 搭配（SN-GAN、BigGAN）；讲义建议"换上 SN 往往不再需要 TTUR"。

### Q15 — 参考回答要点

- **肉眼检查**：每个 epoch 固定一组 z 生成 64 张样本网格，观察质量与多样性随训练的变化；讲义称之为"Non-negotiable"。
- **FID**：用足够多的样本（常见 1 万到 5 万张）和同一套预处理，与真实集比较；同时记录训练过程中的 FID 曲线，选最优 checkpoint。
- **Precision / Recall**：分别看"生成样本是否落在真实分布内"（质量）和"真实分布是否被覆盖"（多样性），能把 FID 混在一起的两件事拆开——模式崩溃通常表现为 precision 高、recall 低。
- **FID 陷阱**：①样本数小时有偏（偏高），不同样本数的 FID 不可比；②图像缩放、压缩、预处理实现不同会显著改变数值，要用同一实现（如 `torch_fidelity`）；③Inception 是在 ImageNet 上训练的，对人脸、医学等域外数据的特征未必敏感；④FID 低不代表没有记忆训练集，需要做最近邻检索检查。
- **业务侧**：人脸场景还要做身份多样性、偏见与隐私检查。

### Q16 — 参考回答要点

- **选 GAN**：讲义给出的场景——实时生成（延迟 <10 ms，单次前向即可出图）、风格迁移、有精确控制的图像到图像翻译（Pix2Pix、CycleGAN）、数据域窄且有成对数据时。
- **选扩散**：追求照片级质量、多样性和文本条件控制时，扩散模型全面胜出；训练更稳定，不会模式崩溃，但推理需要多步去噪（见第 10、11 节）。
- **GAN 思想仍在发挥作用**：①Stable Diffusion 的 VAE（自编码器）训练时用了感知损失 + patch 判别器的对抗损失，保证解码图像锐利；②对抗蒸馏（如 SDXL Turbo 所用的 Adversarial Diffusion Distillation）把多步扩散压缩到 1–4 步；③超分辨率等任务常用 GAN 损失恢复高频细节。讲义也指出，归一化选择、潜空间、特征损失这些让扩散实用化的技巧最早都是在 GAN 上被理解的。
- **加分点**：能把选择落到延迟、可控性、数据量、训练稳定性四个维度上讨论。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：卷积、步长与 BatchNorm 的使用。
- [阶段 03 · 06 优化器](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：Adam 的 β1/β2 与动量。
- [阶段 03 · 07 正则化](../../../03-deep-learning-core/07-regularization/docs/zh.md)：BatchNorm 的训练/推理行为。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 散度、JS 散度。
- [阶段 04 · 07 语义分割——U-Net](../../07-semantic-segmentation-unet/docs/zh.md)：转置卷积与棋盘格伪影。

### 本节被哪些后续内容用到
- [阶段 04 · 10 图像生成 — Diffusion Models](../../10-image-generation-diffusion/docs/zh.md)：取代 GAN 成为主流的生成范式，训练稳定、无模式崩溃。
- [阶段 04 · 11 Stable Diffusion](../../11-stable-diffusion/docs/zh.md)：潜空间扩散，其 VAE 的训练借用了对抗损失。
- [阶段 08 · 03 GANs — 生成器与判别器](../../../08-generative-ai/03-gans-generator-discriminator/docs/zh.md)：更系统的 GAN 理论与实现。
- [阶段 08 · 04 Conditional GANs & Pix2Pix](../../../08-generative-ai/04-conditional-gans-pix2pix/docs/zh.md)：条件 GAN 与图像翻译（讲义练习 3 的延伸）。
- [阶段 08 · 05 StyleGAN](../../../08-generative-ai/05-stylegan/docs/zh.md)：讲义提到的高分辨率人脸生成。
- [阶段 08 · 14 生成模型评估：FID 与 CLIP Score](../../../08-generative-ai/14-evaluation-fid-clip-score/docs/zh.md)：FID 等指标的细节。

### 延伸关键词
`WGAN / WGAN-GP` · `Hinge loss` · `R1 正则` · `Minibatch std` · `SN-GAN / BigGAN` · `StyleGAN3` · `CycleGAN` · `Adversarial Diffusion Distillation` · `torch_fidelity` · `Precision/Recall for GANs`
