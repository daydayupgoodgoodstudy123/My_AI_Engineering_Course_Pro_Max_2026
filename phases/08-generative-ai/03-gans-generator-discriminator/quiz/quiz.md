# 测验 · GANs — 生成器与鉴别器（GANs — Generator vs Discriminator）

> **阶段 08 · 生成式 AI · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要 GAN | VAE 的 MSE 损失奖励"接近均值"，于是模糊；GAN 想要一个奖励"像真的（plausibility）"的损失——它没有闭式解，只能学出来，这个学出来的损失就是判别器 |
| 2 | 生成器与判别器 | `G: z → x̂`，把 `N(0, I)` 噪声映射成样本；`D: x → [0, 1]`，真 → 1、假 → 0 |
| 3 | minimax 目标 | `min_G max_D E_real[log D(x)] + E_fake[log(1 - D(G(z)))]`；G 从未写下 `log p(x)`，是隐式密度模型 |
| 4 | D 的损失 | 真=1、假=0 的二元交叉熵：`loss_D = -[log D(x) + log(1 - D(G(z)))]` |
| 5 | 非饱和（non-saturating）G 损失 | 用 `-log D(G(z))` 代替 `log(1 - D(G(z)))`；D 很自信时原损失梯度趋于 0，新损失反而给出强梯度 |
| 6 | 交替训练 | 一步 D、一步 G，循环；G 的那一步要用新采样的噪声；梯度要穿过 D 回到 G，但只更新 G |
| 7 | 均衡 | G 完美匹配 `p_data` 时 D 只能猜，处处输出 0.5，G 不再得到梯度 |
| 8 | 三大失败模式 | 模式崩溃（只生成部分模式）、梯度消失（D 学得太快，log D 饱和）、训练不稳定（对学习率、batch 等极敏感） |
| 9 | 让 GAN 能用的改进 | DCGAN（卷积 + BN + LeakyReLU）、WGAN / WGAN-GP（Wasserstein 距离 + 梯度惩罚）、谱归一化（约束 D 的 Lipschitz 常数）、Progressive GAN、StyleGAN 1/2/3、R3GAN |
| 10 | 2026 年的 GAN | 不再是开放域 SOTA，但 StyleGAN 仍是窄领域写实标杆；对抗损失作为组件存在：扩散训练中的判别器损失、对抗蒸馏（SDXL-Turbo、SD3-Turbo）把多步扩散压到 1–4 步；推理一次前向，TTFT ≈ 总延迟 |

### 核心技能（能动手做到）

- [ ] 推导 sigmoid + BCE 对 logit 的梯度 `p - target`，以及非饱和 G 损失的 `p - 1`，并说出饱和版本为什么是 `-p`
- [ ] 不用框架，手写一个 1-D GAN 的 D 步、G 步（梯度穿过 D 回传到 G 的输出再进入 G），并跑通 800 步训练
- [ ] 读懂训练日志里 `D(real)`、`D(fake)`、modeA/modeB，判断 D 过强、模式崩溃等状态
- [ ] 为生成样本设计比"按正负号数模式"更可靠的分布指标（如 1-D Wasserstein 距离、落在低密度区的比例），并解释为什么需要它
- [ ] 把 BCE GAN 改成 WGAN（去掉 sigmoid、换损失、权重裁剪），并能解释裁剪 0.01 时训练为何几乎不动
- [ ] 拿到一条失败的 GAN 训练曲线，能给出"一个根因 + 一个具体修改 + 重跑协议"

---

## 二、基础自测（选择题）

**Q1.** 设 D 对一个假样本的输出 `p = D(G(z)) = σ(a)`，`a` 是 D 的 logit。当 D 非常自信（`p ≈ 0.01`）时，G 的两种损失对 `a` 的梯度分别约为：

- A. 饱和版 `log(1 - p)`：约 -0.99；非饱和版 `-log p`：约 -0.01
- B. 饱和版 `log(1 - p)`：约 -0.01；非饱和版 `-log p`：约 -0.99
- C. 两者都约为 0
- D. 两者都约为 -1

**Q2.** 按讲义，如果 G 完美匹配了 `p_data`，D 会：

- A. 处处输出 1
- B. 处处输出 0
- C. 处处输出 0.5，G 不再获得梯度
- D. 在真样本上输出 1，在假样本上输出 0

**Q3.** 已知最优判别器 `D*(x) = p_data(x) / (p_data(x) + p_g(x))`。在某点 `x₀` 处 `p_data(x₀) = 0.3`，`p_g(x₀) = 0.1`，则 `D*(x₀)` 为：

- A. 0.25
- B. 0.50
- C. 0.75
- D. 3.00

**Q4.** 训练日志显示：第 500 步起 `D(real) ≈ 0.99`、`D(fake) < 0.05`，生成样本几乎不再变化。根据讲义和本节技能文件，**最不应该**采取的措施是：

- A. 把 D 的学习率降到原来的 1/2–1/5
- B. 给 D 的输入加少量高斯噪声
- C. 把 G 的学习率调大，让它"追上" D
- D. 改用 WGAN-GP 或给 D 加谱归一化

**Q5.** 关于"模式崩溃（mode collapse）"，最准确的描述是：

- A. 判别器输出全部变成 NaN
- B. 生成器只产出少数几种输出（例如只生成两个真实模式中的一个），即便数据是多样的；被冷落的模式不会被生成，所以 D 也不会因它而纠正 G
- C. 生成样本变得模糊
- D. 生成器的参数全部变为 0

**Q6.** 讲义提醒"BN 泄露统计量"：把真样本 batch 和假样本 batch 送进同一个 BatchNorm 层会出问题。推荐的替代方案是：

- A. 增大 batch size
- B. 改用 instance norm 或谱归一化
- C. 去掉激活函数
- D. 把真假样本拼成一个 batch 再 BN 就没问题了

**Q7.** 谱归一化（spectral normalization）在 GAN 中的作用是：

- A. 把生成器输出归一化到 [-1, 1]
- B. 约束判别器每层权重的谱范数，从而约束 D 的 Lipschitz 常数（斜率），稳定训练
- C. 对图像做傅里叶变换去噪
- D. 加速生成器推理

**Q8.** 2026 年对抗训练最主要的"存活形态"是：

- A. 开放域文生图、视频生成的主力独立生成器
- B. 作为组件：扩散训练中的判别器/感知损失，以及对抗蒸馏（SDXL-Turbo、SD3-Turbo）把 20–50 步扩散压缩成 1–4 步
- C. 大语言模型预训练的主要目标
- D. 已经完全被淘汰，没有任何用途

---

## 三、动手 / 代码题

**Q9.** 本节代码里 D 步和 G 步对 D 的 logit（`pre2`）的梯度分别写成：

```python
# update_d 中的 accumulate(x, target)
        p, h, pre1, pre2 = forward_d(x, D)
        dL_dpre2 = p - target

# update_g 中
        p, d_h, d_pre1, d_pre2 = forward_d(x_hat, D)
        # dL/dpre2_D where L = -log(p) is -(1/p) * p*(1-p) = p - 1
        dL_dpre2 = p - 1.0
```

(a) 推导 `update_d` 里的 `p - target`。
(b) 如果把 G 的损失换回原始的饱和形式（G 最小化 `log(1 - D(G(z)))`），`dL_dpre2` 应改成什么？
(c) 在 `update_g` 里，梯度穿过了 D 的权重 `D["W1"]`、`D["W2"]`，为什么函数结束时 D 的参数却没有被修改？如果不小心也更新了 D 会怎样？

**Q10.** 运行 `main.py`，最后一次日志是 `modeA=161 modeB=239`，没有触发模式崩溃警告；但最后打印的 10 个样本里有 6 个落在 `[-0.4, +0.3]` 附近：

```text
step  800: D(real)=0.57  D(fake)=0.55  modeA=161  modeB=239
...
  G(z) = -0.30
  G(z) = -0.33
  G(z) = -0.02
  G(z) = +1.76
  G(z) = +2.28
  G(z) = -2.26
  G(z) = -0.36
  G(z) = -0.26
  G(z) = -2.47
  G(z) = +0.23
```

真实数据是 `0.5·N(-2, 0.4²) + 0.5·N(2, 0.4²)`。
(a) 为什么代码的模式崩溃检测没有报警？它漏掉了什么？
(b) 写一个函数 `wasserstein_1d(a, b)`（两组等量样本的一维 W1 距离）和一个"低密度区占比"指标 `gap_fraction(xs)`（`|x| < 1` 的比例），说明它们为何更能反映问题。

**Q11.** 按讲义练习 2 把本节 GAN 改成 WGAN：`loss_D = E[D(fake)] - E[D(real)]`，`loss_G = -E[D(fake)]`，每次 D 更新后把 D 的权重裁剪到 `[-0.01, 0.01]`。
(a) `forward_d` 返回的 `sigmoid(pre2[0])` 还要用吗？`update_d` 的 `accumulate` 里 `dL_dpre2` 对真样本、假样本分别是多少？`update_g` 里呢？
(b) 写出权重裁剪函数。
(c) 只改这些、其他超参不变（`d_lr=0.01`、`g_lr=0.02`、每步 1 次 D 更新），你预测结果会更好还是更差？为什么？

---

## 四、面试高频题

**Q12.**（基础必考）讲一下 GAN 的目标函数和训练流程。为什么实际训练 G 时不用原始的 `log(1 - D(G(z)))`？

**Q13.**（原理深挖）固定 G 时最优判别器是什么？代回去以后 G 在优化什么散度？这个散度有什么缺陷，WGAN 是怎么解决的？

**Q14.**（工程实践）你接手一个训练失败的 GAN：给你 D/G 损失曲线和样本网格。请说出你的排查顺序，以及至少 4 种常见病因对应的"症状 → 修复"。

**Q15.**（原理深挖）模式崩溃为什么会发生？有哪些缓解手段？如何量化地检测它？

**Q16.**（场景设计）既然扩散模型质量更好，为什么 SDXL-Turbo / SD3-Turbo 这类实时文生图还要用对抗训练？从推理成本的角度说明 GAN 的"一次前向"优势。

**Q17.**（追问型）"判别器准确率越高说明训练越好"——这句话对吗？`D(real) = D(fake) = 0.5` 一定说明 G 学好了吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

`p = σ(a)`，`dp/da = p(1 - p)`。
- 饱和版 `L = log(1 - p)`：`dL/da = -p(1-p)/(1-p) = -p ≈ -0.01`，几乎没有梯度；
- 非饱和版 `L = -log p`：`dL/da = -(1/p)·p(1-p) = p - 1 ≈ -0.99`，梯度很强。

两者的"最优点"相同（都希望 D 把假样本判为真），但在 D 很自信、G 最需要信号的训练早期，饱和版会让 G 学不动。这正是代码注释 `-(1/p) * p*(1-p) = p - 1` 的来历。

### Q2 — 答案：C

当 `p_g = p_data` 时，真假样本在任何位置出现的概率相同，D 最好的策略就是处处输出 0.5（最优判别器 `p_data/(p_data+p_g) = 1/2`）。此时 D 在真假样本上的"意见"一致，G 拿不到朝任何方向移动的梯度——这就是均衡。D 是"假=0、真=1"那种情况（D 选项）说明 G 还很差。

### Q3 — 答案：C

`D*(x₀) = 0.3 / (0.3 + 0.1) = 0.75`。直觉：在 `x₀` 附近，真样本出现的可能性是假样本的 3 倍，所以"这是真样本"的后验概率是 3/4（假设真假各占一半）。D 选项 3.00 是密度比 `p_data/p_g`，不是概率；A 是 `p_g/(p_data+p_g)`。

### Q4 — 答案：C

症状是"D 太强"（技能文件的例子："D(fake) < 0.05 by step 500 = D too strong"），讲义说"If D reaches >95% accuracy, G is dead"。正确的做法是削弱/约束 D：降 D 学习率 2–5 倍（A）、给 D 输入加噪声（B）、换 WGAN-GP 或加谱归一化（D）。技能文件明确规定：**D 已经饱和时，拒绝推荐调大 G 的学习率**——D 饱和时 G 拿到的梯度信号本身就是坏的，加大步长只会更不稳定。

### Q5 — 答案：B

讲义："the canonical symptom: one of the two real modes stops being generated. The discriminator stops correcting it because it's never seen as a fake." G 找到一个 D 暂时分辨不出的区域就一直"印"它；被冷落的模式里没有假样本，D 也就没有理由去惩罚"那里缺样本"。本节训练日志前 400 步（modeB 掉到 1–13）就是一个活生生的例子。C 是 VAE 的典型问题。

### Q6 — 答案：B

BN 用当前 batch 的均值方差做归一化。真假 batch 分别过 BN 时，每个 batch 都被归一化成"自己的"统计量，D 可能利用 batch 级统计量而不是单样本特征来区分真假；混在一起又会让真假样本的统计量相互影响。讲义推荐 instance norm（逐样本归一化）或谱归一化。A、D 都不能消除"统计量跨样本泄露"这个根本问题。

### Q7 — 答案：B

谱归一化把每层权重矩阵除以它的最大奇异值（谱范数），使每层的 Lipschitz 常数不超过 1，从而限制 D 的"斜率"。D 不会变得任意陡峭，G 得到的梯度更平滑。讲义说它"Still used in 2026 discriminators"。

### Q8 — 答案：B

讲义："The adversarial trick lives on as a component (perceptual losses, distillation), not a standalone generator." 以及 Production note："collapses a 20-50-step diffusion pipeline into 1-4 GAN-style forward passes"。A 错：开放域生成已被扩散 / flow matching 取代；讲义的 Use It 表也说"Anything multi-modal, open-ended — Don't"。

### Q9 — 参考答案

**(a)** D 的损失是 BCE：`L = -[t·log p + (1-t)·log(1-p)]`，`p = σ(a)`。
`dL/dp = -t/p + (1-t)/(1-p)`，`dp/da = p(1-p)`，相乘：
`dL/da = -t(1-p) + (1-t)p = p - t`。
这是 "sigmoid + 交叉熵" 的经典化简：梯度就是"预测 - 标签"，数值稳定且无需单独计算 `log`。真样本 `t=1` 得 `p - 1`，假样本 `t=0` 得 `p`。

**(b)** G 最小化 `L = log(1 - p)`：`dL/da = -p(1-p)/(1-p) = -p`，所以改成：

```python
        dL_dpre2 = -p          # 饱和版：D 越自信（p→0），梯度越接近 0
```

与非饱和版 `p - 1` 对比：两者符号相同（都推动 `a` 变大、让 D 认为假样本更"真"），但 `p→0` 时 `-p → 0`，`p - 1 → -1`。

**(c)** `update_g` 只计算并累加 `grads`（字典的键是 G 的参数名），最后只对 `G[part]` 做 `-= lr * grad`；D 的权重只是被**读取**来计算 `dL/dx̂`（链式法则需要 D 的雅可比），从未被写入。这等价于 PyTorch 里 G 步只调用 `opt_G.step()`（并在 D 步前 `zero_grad`）。
如果在 G 步顺手也更新了 D，D 就会沿着"让假样本被判为真"的方向更新——等于帮 G 作弊，D 失去鉴别能力，对抗信号被破坏，训练会迅速退化。

### Q10 — 参考答案

**(a)** 检测逻辑只看**符号**：`mode_a = sum(1 for v in probe_fakes if v < 0)`。它能发现"某一侧几乎没有样本"，但发现不了"样本落在两峰之间的低密度区"。真实数据在 `|x| < 1` 内几乎没有质量（两峰中心 ±2、σ=0.4，`|x|<1` 已是 2.5σ 之外），而我按 `main()` 完全相同的训练过程复现最终模型、再用独立随机数采 2000 个样本测得：**35.4% 的生成样本落在 `|x| < 1`**，真实数据只有约 0.5%。也就是说 G 学到的是"两个峰 + 中间一座桥"，modeA/modeB 的计数却显得很平衡。

**(b)** 参考实现：

```python
def wasserstein_1d(a, b):
    """等样本量的一维 W1 距离：排序后逐对相减取平均。"""
    assert len(a) == len(b)
    return sum(abs(x - y) for x, y in zip(sorted(a), sorted(b))) / len(a)

def gap_fraction(xs, width=1.0):
    return sum(1 for v in xs if abs(v) < width) / len(xs)
```

- 一维情形下 W1 距离等于两个分布分位数函数之差的积分，排序后逐对相减就是它的经验估计，`O(n log n)`。它对"质量放错了位置"很敏感：本节最终模型 vs 真实数据的 W1 ≈ **0.88**（单位与 x 相同），说明平均每个样本要"搬"将近 0.9 的距离才能对上真实分布。
- `gap_fraction` 是针对这份数据的"领域知识指标"：直接检查低密度区是否被错误填充（35.4% vs 0.5%）。
- 一般结论：只数"覆盖了几个模式"的指标会漏掉"模式之间的伪样本"；要用比较完整分布的指标——低维时用 W1 / 直方图，高维图像用 FID、precision/recall（precision 低正对应"生成了不像真的样本"）。

### Q11 — 参考答案

**(a)** WGAN 的 D（critic）输出的是**未经 sigmoid 的实数分数**，直接用 `pre2`：

```python
# update_d 的 accumulate：loss_D = mean(D(fake)) - mean(D(real))
        _, h, pre1, pre2 = forward_d(x, D)     # 忽略 sigmoid 输出
        dL_dpre2 = -1.0 if target == 1.0 else +1.0

# update_g：loss_G = -mean(D(fake))
        dL_dpre2 = -1.0
```

其余反向传播代码（穿过 `W2`、LeakyReLU、`W1`）完全不变。

**(b)** 每次 D 更新后：

```python
def clip_weights(D, c=0.01):
    for part in D:
        if isinstance(D[part][0], list):
            D[part] = [[max(-c, min(c, w)) for w in row] for row in D[part]]
        else:
            D[part] = [max(-c, min(c, w)) for w in D[part]]
```

**(c)** **会更差**。我按上述改法写了完整版本，在相同种子、800 步、相同学习率下实测：WGAN 的 W1 ≈ 1.73、低密度区占比 ≈ 96%（G 几乎停在初始化附近，输出都挤在 0 附近），而原 BCE 版本是 0.86 / 35%。原因：
- 权重全被夹在 ±0.01，D 的 16 个隐藏单元传给 G 的梯度大约是 `Σ W1[j]·W2[j]` 量级，最多 `16 × 0.01 × 0.01 ≈ 0.0016`，乘上 `g_lr = 0.02`，G 每步几乎不动；
- 原论文的配套设置是每个 G 步训练 D 5 次（n_critic=5）、用 RMSProp 和很小的学习率，并训练更长时间；
- 权重裁剪本身就是一个粗糙的 Lipschitz 约束（裁小了梯度消失、裁大了梯度爆炸），这正是 WGAN-GP 用梯度惩罚替代它的原因。

这个实验说明：换损失函数不等于换"开箱即用"的稳定性，配套的超参与约束方式同样关键。

### Q12 — 参考回答要点

- **目标**：`min_G max_D V(D, G) = E_{x~p_data}[log D(x)] + E_{z~p(z)}[log(1 - D(G(z)))]`。
- **流程**：每轮①采一批真样本 + 一批噪声生成假样本，用 BCE（真=1、假=0）更新 D；②**重新采噪声**，让假样本过 D，把梯度经 D 传回 G，只更新 G。一步 D 一步 G 交替（也可以 k 步 D 一步 G）。
- **为什么不用原始 G 损失**：训练早期 G 很差，D 很容易判假（`D(G(z)) ≈ 0`），`log(1 - D(G(z)))` 在这里是平的，对 logit 的梯度为 `-p ≈ 0`，G 学不动；非饱和形式 `-log D(G(z))` 梯度为 `p - 1 ≈ -1`。两者驱动方向一致，但梯度大小在关键阶段差两个数量级。
- 加分点：指出非饱和形式改变了 G 实际优化的散度（不再严格对应 JS 散度），这是"实践中有效但理论不严格"的典型例子。

### Q13 — 参考回答要点

- **最优判别器**：固定 G，对每个 x 最大化 `p_data·log D + p_g·log(1-D)`，得 `D*(x) = p_data(x) / (p_data(x) + p_g(x))`。
- **代回去**：`V(D*, G) = 2·JS(p_data || p_g) - log 4`。所以在 D 最优的理想情况下，G 在最小化 Jensen-Shannon 散度，最小值在 `p_g = p_data` 时取到，此时 `D* ≡ 1/2`。
- **缺陷**：当两个分布的支撑集几乎不重叠时（高维空间里两个低维流形通常就是如此），JS 散度恒为 `log 2`，对 G 的参数几乎没有梯度——这就是"D 太强 → G 梯度消失"的理论根源。
- **WGAN**：改用 Wasserstein-1（推土机，Earth-Mover）距离，即使支撑集不重叠也随分布的"距离"平滑变化；通过 Kantorovich-Rubinstein 对偶，D 变成一个 1-Lipschitz 的 critic，`loss_D = E[D(fake)] - E[D(real)]`。Lipschitz 约束最初靠权重裁剪，WGAN-GP 改用梯度惩罚（技能文件给出 λ=10）；谱归一化是另一种约束方式。
- 常见误区：把 WGAN 的 D 输出当概率——它是不经 sigmoid 的实数分数。

### Q14 — 参考回答要点

**排查顺序**：先看是否"100 步内就崩"（技能文件：大概率是初始化或学习率爆炸，不是算法问题）→ 看 D/G 损失和 `D(real)`、`D(fake)` 的相对走势 → 看样本网格的多样性 → 再动架构或范式。**先修 D，再碰 G**（技能文件：真实问题在 D 时不要给 G 加正则）。

| 病因 | 症状 | 一行修复 |
|------|------|---------|
| D 太强 / 梯度消失 | `D(real)→1`、`D(fake)→0`（如 500 步内 < 0.05），G 损失飙升或卡住 | `lr_D = lr_G / 2`；给 D 输入加 0.1 高斯噪声；加谱归一化 |
| D 太弱 | `D(real) ≈ D(fake) ≈ 0.5` 但样本很差 | 提高 D 容量/学习率，或每步多训几次 D |
| 模式崩溃 | 样本网格里大量重复，多样性指标下降 | minibatch discrimination、D 输入加噪声、换 WGAN-GP |
| BN 泄露 | 真假 batch 分开过 BN 后行为异常 | BN 换成 instance norm 或谱归一化 |
| 学习率失配 / 初始化不当 | 训练很快发散、NaN | 降学习率、检查初始化 |
| 评估噪声 | FID/IS 抖动很大 | 讲义：评估至少用 1 万个样本 |

- **重跑协议**：固定若干种子，规定多少步后再评估、验收标准（例如"第 2 万步时 FID 低于基线"）；一次重跑没解决就换架构（StyleGAN、R3GAN）或换范式（数据太多样时换扩散 / flow matching）。

### Q15 — 参考回答要点

- **原因**：G 的目标是"骗过当前的 D"，而不是"覆盖整个分布"。G 发现某个区域 D 暂时分不清，就把所有 `z` 都映射过去；D 随后学会识别这个区域，G 又跳到另一个区域——形成"追逐"而非收敛。被丢掉的模式里没有假样本，D 也不会提醒 G"这里缺东西"。
- **缓解**：minibatch discrimination（让 D 看到一批样本的多样性）、D 输入加噪声、WGAN / WGAN-GP（更平滑的梯度）、谱归一化、更好的架构（StyleGAN 的 mapping network 等）、unrolled GAN 等。
- **检测**：低维时统计各模式命中率（如讲义的 modeA/modeB 和练习 3 的"8 个模式捕获了几个"）；高维时看 FID、precision/recall（recall 低 = 覆盖不全）、生成样本与训练集的最近邻距离、样本网格人工检查。
- 加分点：结合本节 Q10 指出"只数模式"会漏掉"模式之间的伪样本"，要同时看 precision（样本是否落在真实流形上）和 recall（是否覆盖所有模式）。

### Q16 — 参考回答要点

- **推理成本形状**：GAN 只有一次 `G(z)` 前向——没有 prefill/decode 两阶段，TTFT ≈ 总延迟；没有 KV cache，唯一的状态是权重，batch 只受激活显存限制；每个请求的 FLOPs 固定，静态 batch 就接近最优，不需要复杂的在途调度。
- **扩散的问题**：成本 = 步数 × 单步成本，20–50 步的完整流水线很难做到实时。
- **对抗蒸馏**：以训练好的扩散模型为老师，用对抗损失（加上蒸馏损失）训练一个只需 1–4 步的学生模型（ADD → SDXL-Turbo，LADD → SD3-Turbo），既保留扩散底座的分布，又拿到 GAN 式的推理成本。讲义："The adversarial loss survives as a training-time knob for turning slow generators into fast ones."
- 加分点：说明少步模型在提高分辨率、加强条件控制时质量可能下降，要按"同等质量下的延迟"来评估。
- 常见误区：把所有少步方法都归为对抗蒸馏——一致性蒸馏（consistency distillation）等是另一条技术路线。

### Q17 — 参考回答要点

- **不对**。D 准确率很高（例如 >95%）恰恰是讲义说的"G is dead"信号：D 太强，G 的梯度消失或变得毫无信息量。GAN 不是分类任务，D 的准确率不是优化目标。
- **`D(real) = D(fake) = 0.5` 也不一定说明 G 好**：
  1. D 可能只是太弱（容量不足、学习率太低），根本没学会区分；
  2. D 的输出是对整个 batch 的平均，平均值相等不代表处处相等——本节 Q10 中 `D(real)=0.57`、`D(fake)=0.55` 很接近，但 35% 的样本落在真实数据几乎不存在的区域；
  3. 要用独立于 D 的指标（W1、FID、precision/recall、人工检查）来评估 G。
- 加分点：说明 GAN 的损失曲线本身不单调、不能直接反映样本质量，这是 GAN 难以调试的根本原因之一（也是 WGAN 宣称"critic 损失与样本质量相关"的卖点）。

---

## 六、关联知识点

### 前置知识
- [阶段 08 · 02 自动编码器和 VAE](../../02-autoencoders-vae/docs/zh.md)：VAE 为什么模糊，是 GAN 的出发点。
- [阶段 08 · 01 生成模型——分类法和历史](../../01-generative-models-taxonomy-history/docs/zh.md)：GAN 属于"桶 3：隐式密度"。
- [阶段 03 · 03 反向传播](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：代码中手写的链式法则。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：二元交叉熵与 sigmoid 的组合。
- [阶段 03 · 06 优化器](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：学习率对 D/G 平衡的影响。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 与 JS 散度。

### 本节被哪些后续内容用到
- [阶段 08 · 04 条件 GAN 与 Pix2Pix](../../04-conditional-gans-pix2pix/docs/zh.md)：给 G 和 D 都加上条件输入，做图像翻译。
- [阶段 08 · 05 StyleGAN](../../05-stylegan/docs/zh.md)：mapping network + 风格调制，GAN 写实度的巅峰。
- [阶段 08 · 06 DDPM 从零实现](../../06-diffusion-ddpm-from-scratch/docs/zh.md)：取代 GAN 成为主流的扩散模型。
- [阶段 08 · 14 评估：FID、CLIP 分数、人类偏好](../../14-evaluation-fid-clip-score/docs/zh.md)：如何量化 GAN 的样本质量与多样性。
- [阶段 04 · 09 图像生成：GAN](../../../04-computer-vision/09-image-generation-gans/docs/zh.md)：计算机视觉视角下的 GAN 实践。

### 延伸关键词
`minimax / 纳什均衡` · `最优判别器与 JS 散度` · `non-saturating loss` · `WGAN / WGAN-GP / 梯度惩罚` · `spectral normalization` · `minibatch discrimination` · `TTUR（双时间尺度更新）` · `precision / recall for generative models` · `adversarial diffusion distillation (ADD / LADD)` · `R3GAN`
