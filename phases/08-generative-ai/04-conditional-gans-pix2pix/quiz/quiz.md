# 测验 · 有条件 GANs & Pix2Pix（Conditional GANs & Pix2Pix）

> **阶段 08 · 生成式 AI · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要"条件" | 无条件 GAN 只能随机出图；生产需要"给定输入 x 输出对应的 y"（草图→照片、白天→夜晚、上色）。一个 x 往往对应多个合理的 y，MSE 会把它们平均成一团糊，对抗损失不会 |
| 2 | 条件 GAN（cGAN） | Mirza & Osindero 2014：把条件 `c` 同时喂给 G 和 D，`G(z, c)`、`D(x, c)`；G 要匹配的是**条件分布**而不是边缘分布 |
| 3 | 条件判别器看的是"对" | `D(x, y)` 的输入是（条件, 输出）这一对，D 要判断 y 是否**与 x 一致**，而不只是 y 像不像真的；只给 D 看 y 它就无法检查一致性 |
| 4 | Pix2Pix 配方 | Isola 2017：条件是一整张图；G 是 U-Net；D 是 PatchGAN；损失 = 对抗 + λ·L1，λ 默认 100；`z` 以 G 内部 dropout 的形式存在（显式噪声会被忽略） |
| 5 | U-Net 生成器 | 编码器-解码器 + 跨瓶颈的 skip 连接；输入输出共享边缘、轮廓等低层结构时至关重要，没有 skip 高频细节会丢失 |
| 6 | PatchGAN 判别器 | 输出 N×N 的网格，每格判断约 70×70 像素的感受野，再取平均；相当于马尔可夫随机场假设"真实感是局部的"，参数少、训练快、输出更锐利 |
| 7 | L1 vs L2 | L1 对应中位数、L2 对应均值，L1 边缘更锐；λ 太低 → 输出像真的但不忠实于目标，λ 太高 → 又变糊（L1 仍是 Lp 范数） |
| 8 | CycleGAN | 没有配对数据时：两个生成器 `G: X→Y`、`F: Y→X`，加循环一致性损失 `F(G(x)) ≈ x`、`G(F(y)) ≈ y`（马↔斑马、夏↔冬） |
| 9 | 条件注入方式 | one-hot 拼接（最简单）→ 学习的 embedding、FiLM 逐特征仿射调制、cross-attention、projection discriminator、SPADE（用语义图做空间自适应归一化） |
| 10 | 生产定位 | 配对数据 + 窄任务 + 低延迟时 Pix2Pix 一次前向（讲义：512² 约 30 ms），比 20 步 SD img2img（约 1.2 s）快一个数量级以上；开放域交给扩散 + ControlNet；常见打法是"窄任务蒸馏模型 + 扩散兜底" |

### 核心技能（能动手做到）

- [ ] 用列表拼接把 one-hot 条件接到 G 和 D 的输入上，并正确设置两者第一层的输入维度（`z_dim + num_classes`、`1 + num_classes`）
- [ ] 训练一个 1-D 条件 GAN，并**逐类**检验生成分布的均值**和**标准差，而不是只看均值
- [ ] 实现 L1 重构项的次梯度 `λ·sign(x̂ - y)`，并通过实验观察 λ 过大导致的类内多样性坍塌
- [ ] 画出 Pix2Pix 的 U-Net + PatchGAN 架构，说清每个设计解决什么问题
- [ ] 写出 CycleGAN 的完整损失（两个对抗项 + 两个循环一致性项），并说明它为什么需要循环项
- [ ] 给定任务（配对/非配对、样本数、延迟预算、是否任意文本提示），在 Pix2Pix、CycleGAN、SPADE、ControlNet 之间做出选型

---

## 二、基础自测（选择题）

**Q1.** 在 Pix2Pix 中，条件判别器的输入应该是：

- A. 只有生成的输出 y
- B. 条件图 x 与输出 y 组成的一对（拼接后输入）
- C. 只有条件图 x
- D. 只有噪声 z

**Q2.** Pix2Pix 生成器的随机性 `z` 来自哪里？

- A. 输入端拼接的高斯噪声向量
- B. 生成器内部的 dropout；作者发现显式输入的噪声会被网络忽略
- C. 判别器的输出
- D. Pix2Pix 完全没有随机性，也没有 dropout

**Q3.** Pix2Pix 的重构项选择 L1 而不是 L2，主要因为：

- A. L1 计算更快
- B. L2 对应条件均值、L1 对应条件中位数，L1 产生的边缘更锐利、更少模糊
- C. L1 能保证生成器不发生模式崩溃
- D. L2 无法反向传播

**Q4.** 关于 PatchGAN 判别器，以下说法正确的是：

- A. 输出整张图一个真/假分数，参数量比全局判别器更多
- B. 输出一个 N×N 网格，每格对约 70×70 像素的局部感受野打分，再取平均；体现"真实感是局部的"假设
- C. 把图像切成小块后分别送入独立的生成器
- D. 只能用于 CycleGAN

**Q5.** 你要做"马 → 斑马"的图像翻译，只有两堆互不对应的马和斑马照片。按讲义，以下哪个方案**不**合适？

- A. CycleGAN（两个生成器 + 循环一致性损失）
- B. 基于扩散的方案（ControlNet、IP-Adapter）
- C. Pix2Pix，λ=100 的 L1 损失
- D. 先用 CycleGAN 做基线，再评估扩散方案

**Q6.** Pix2Pix 训练中把 L1 权重 λ 设得过大，最可能看到的现象是：

- A. 输出非常锐利但与目标毫无关系
- B. 输出偏模糊、多样性下降，因为 L1 仍是 Lp 范数，主导时退化成"回归一个确定的平均/中位答案"
- C. 判别器准确率降到 0
- D. 训练速度提升 100 倍

**Q7.** U-Net 中跨越瓶颈的 skip 连接在 Pix2Pix 里的主要作用是：

- A. 减少参数量
- B. 把编码器的低层特征（边缘、轮廓等高频细节）直接送到解码器对应层，避免细节在瓶颈中丢失
- C. 替代判别器
- D. 让网络可以接受任意分辨率的文本输入

**Q8.** 讲义的生产对照表（512²、单张 L4）中，Pix2Pix 约 30 ms，SD-Img2Img 20 步约 1.2 s。讲义推荐的"现代打法"是：

- A. 所有任务一律用扩散模型，Pix2Pix 已无价值
- B. 为窄任务部署一个 Pix2Pix 风格（或蒸馏得到）的一次前向模型，对长尾输入用扩散模型兜底
- C. 所有任务一律用 Pix2Pix，扩散模型太慢
- D. 用 CycleGAN 替代所有配对任务

---

## 三、动手 / 代码题

**Q9.** 本节代码这样把条件接入网络：

```python
def one_hot(c, num):
    v = [0.0] * num
    v[c] = 1.0
    return v

def g_forward(z, c, G, num_classes):
    inp = z + one_hot(c, num_classes)
    # ...

def d_forward(x, c, D, num_classes):
    inp = x + one_hot(c, num_classes)
    # ...

# main 中
    G = init_mlp(z_dim + num_classes, hidden, 1, rng)
    D = init_mlp(1 + num_classes, hidden, 1, rng)
```

(a) 当 `z = [0.5, -1.0, 0.2, 0.3]`、`c = 1`、`num_classes = 2` 时，`g_forward` 里的 `inp` 是什么？当 `x = [-2.0]`、`c = 0` 时，`d_forward` 里的 `inp` 是什么？
(b) 如果把 `z` 换成 NumPy 数组 `np.array([0.5, -1.0, 0.2, 0.3])`、`one_hot` 也返回 NumPy 数组，`z + one_hot(...)` 会发生什么？应该怎么写？
(c) 如果只给 G 条件、D 不看条件（`D = init_mlp(1, ...)`），G 会学成什么样？

**Q10.** 阅读 `update_g` 的片段：

```python
def update_g(noise, cs, G, D, num_classes, lr, l1_w=0.0, targets=None):
    """Non-saturating G loss + optional conditional L1 toward a target."""
    grads = init_grads(G)
    for i, z in enumerate(noise):
        c = cs[i]
        # ...
        if l1_w > 0 and targets is not None:
            for k in range(len(x_hat)):
                dL_dxhat[k] += l1_w * (1.0 if x_hat[k] > targets[i][k] else -1.0)
        grads["b2"] = [grads["b2"][i] + dL_dxhat[i] for i in range(len(x_hat))]
        # ...
```

(a) 外层循环变量是 `i`，下面的列表推导式里又用了 `i`。这在 Python 3 中是 bug 吗？为什么？
(b) `l1_w * (1.0 if x_hat[k] > targets[i][k] else -1.0)` 对应 `|x̂ - y|` 的什么？在 `x̂ == y` 时它返回什么，严格来说应该返回什么？
(c) `main()` 从未启用 L1。如果令 `l1_w=0.5`，并把每个样本的 `targets` 设为它所属类的中心（类 0 → `[-2.0]`，类 1 → `[2.0]`），其他不变，你预测每类生成样本的均值和标准差会怎样变化？（真实数据每类标准差为 0.3）

**Q11.** 讲义 Step 3 建议"逐类检查均值"。请写一个函数 `per_class_stats(G, num_classes, z_dim, n=1000, seed=99)`，对每个类生成 `n` 个样本，返回 `(均值, 标准差)` 列表；再写 `check_conditional(stats, centers, std_true, tol_mean=0.3, tol_std_ratio=1.5)`，当任一类均值偏差超过 `tol_mean`，或标准差超过真实值的 `tol_std_ratio` 倍时返回 False。用在 `main()` 训练完的模型上，结果如何？

---

## 四、面试高频题

**Q12.**（基础必考）条件 GAN 和普通 GAN 有什么区别？条件信息一般怎么注入 G 和 D？为什么判别器也必须看到条件？

**Q13.**（原理深挖）逐条解释 Pix2Pix 的设计：U-Net 生成器、PatchGAN 判别器、对抗损失 + L1、λ=100、用 dropout 代替输入噪声。每一条解决了什么问题？

**Q14.**（原理深挖）CycleGAN 如何在没有配对数据的情况下训练？为什么只有对抗损失不够？它有哪些已知局限？

**Q15.**（场景设计）为下面三个需求选型，并说明数据要求和评估方式：①建筑草图 → 效果图渲染，有 5000 对配对数据，要求 50 ms 内出图；②监控视频白天 → 夜晚风格迁移，没有配对数据；③用户输入任意文本描述来编辑图片。

**Q16.**（工程实践）比较几种条件注入方式：输入拼接 one-hot、学习的 embedding、FiLM、cross-attention、projection discriminator、SPADE。各适合什么场景？

**Q17.**（追问型）训练完一个条件 GAN，发现"不管给什么条件，输出都差不多"。可能的原因是什么？怎么检测、怎么修？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Input is the *pair* (condition, output). This is the key difference: D must judge whether y is consistent with x, not just whether y looks real." Pitfalls 里也专门列了一条：要把 `(x, y)` 拼接作为 D 的输入，而不是只给 y，否则 D 无法检查一致性。只看 y（A）会让 G 学会生成"像真的但与输入无关"的图。

### Q2 — 答案：B

讲义："In Pix2Pix, z is dropout inside G (no input noise — Isola found explicit noise got ignored)." 因为配对任务的条件 x 已经携带了大部分信息，加上强 L1 监督，网络会学会无视输入噪声。所以 Pix2Pix 的输出多样性其实很有限——这也是它适合"确定性强的窄任务"的原因之一。

### Q3 — 答案：B

当一个 x 对应多个合理的 y 时，最小化 L2 的最优解是条件**均值**（多种可能的平均 → 糊），最小化 L1 的最优解是条件**中位数**（会落在某个真实的取值上，边缘更锐）。讲义："L1 gives sharper edges than L2 (medians, not means)". L1 本身并不能防止模式崩溃（C 错）。

### Q4 — 答案：B

PatchGAN 输出 N×N 网格，每格的感受野约 70×70 像素，最后取平均。它把"真实感"建模为局部性质（马尔可夫随机场假设），全局结构交给 L1 项去约束。好处是参数更少、训练更快、高频细节更锐，而且可以应用到任意尺寸的图像上。A 说反了；C、D 是编造的。

### Q5 — 答案：C

Pix2Pix 的 L1 项需要每个输入 x 对应的目标 y，没有配对数据就无从计算。技能文件明确规定："Refuse to recommend Pix2Pix when data is unpaired - prescribe CycleGAN or ControlNet instead." 讲义也指出 2026 年非配对翻译多用扩散（ControlNet、IP-Adapter），但 CycleGAN 仍是可用的基线，所以 A、B、D 都合理。

### Q6 — 答案：B

讲义 Pitfalls："L1 weight too high. G produces blurry outputs because L1 is still an L_p norm. Anneal down once training stabilizes." λ 过大时对抗项几乎不起作用，模型退化为一个回归器，输出"确定的折中答案"——多样性消失、细节变糊。A 描述的是 λ 太低（"G drifts to arbitrary real-looking outputs, not faithful ones"）。测验 Q10(c) 在 1-D 代码里复现了这一现象。

### Q7 — 答案：B

编码器层层下采样会丢掉位置精确的高频信息，仅靠瓶颈的低分辨率特征很难还原。skip 连接把编码器第 i 层的特征直接拼到解码器对应层，输入输出共享的边缘、轮廓等低层结构可以"抄近路"过去。讲义："Without the skips, high-frequency detail vanishes."

### Q8 — 答案：B

讲义 Production note 的结论："The modern play is often to ship a Pix2Pix-style distilled model for the narrow task and a diffusion fallback for tail inputs." Pix2Pix 在延迟和静态 batch 吞吐上占优（每个请求 FLOPs 相同），扩散在质量和泛化上占优，两者组合使用。A、C 都是非此即彼的极端；D 与配对任务无关。

### Q9 — 参考答案

**(a)** Python 列表的 `+` 是**拼接**，不是逐元素相加（我实际运行验证过）：

```text
g_forward 的 inp: [0.5, -1.0, 0.2, 0.3, 0.0, 1.0]   # 4 维噪声 + 2 维 one-hot，共 6 维
d_forward 的 inp: [-2.0, 1.0, 0.0]                   # 1 维样本 + 2 维 one-hot，共 3 维
```

所以 G 第一层的输入维度是 `z_dim + num_classes = 6`，D 是 `1 + num_classes = 3`，正好对应 `init_mlp` 的参数。

**(b)** NumPy 数组的 `+` 是**逐元素相加**：4 维和 2 维的数组形状不匹配，会抛出 `ValueError: operands could not be broadcast together`；若形状恰好相同，则会"静默地"把条件加到噪声上——更隐蔽的 bug。应写成 `np.concatenate([z, one_hot(c, num)])`，PyTorch 里是 `torch.cat([z, c_onehot], dim=-1)`。

**(c)** D 不看条件时，它只能判断"这个样本像不像真实数据的**边缘分布**"（两峰混合）。G 只要输出落在任一峰上就能骗过 D，没有任何力量迫使"类 0 → -2、类 1 → +2"。结果 G 很可能学会忽略条件，对任何类都输出混合分布（或塌到某一个峰）——这就是讲义 Pitfalls 的"Condition ignored"。

### Q10 — 参考答案

**(a)** **不是 bug**。Python 3 中列表推导式有自己独立的作用域，推导式里的 `i` 不会覆盖外层循环的 `i`；而且 `targets[i]` 在推导式之前就用完了。退一步说，即使改成普通 `for i in ...` 循环覆盖了 `i`，外层 `for i, z in enumerate(noise)` 下一轮仍会从迭代器取新值。但这种同名遮蔽非常容易误导读者（在 Python 2 里推导式变量会泄漏到外层），工程上应改名，例如 `grads["b2"] = [grads["b2"][k] + dL_dxhat[k] for k in range(len(x_hat))]`。

**(b)** 是 `|x̂ - y|` 对 `x̂` 的**次梯度** `sign(x̂ - y)`，乘以权重 `l1_w`。`x̂ == y` 时代码返回 -1（走了 else 分支）；严格来说该点不可导，次梯度可取 `[-1, 1]` 中任意值，惯例取 0（`torch.sign(0) = 0`）。对浮点数来说恰好相等几乎不会发生，影响可忽略。也可以看出 L1 的梯度大小**恒定**为 λ，不随误差变小而变小——这也是它比 L2 更"推得动"、但在目标附近容易来回抖动的原因。

**(c)** 每类的**均值会被拉到类中心，标准差会大幅坍缩**。我用相同的种子和流程实测（每类 1000 个样本）：

| 设置 | 类 0 均值 / 标准差 | 类 1 均值 / 标准差 |
|------|------------------|------------------|
| 原始 `main()`（无 L1） | -2.55 / 0.62 | +2.46 / 0.46 |
| `l1_w = 0.5`，目标=类中心 | -1.98 / 0.10 | +1.99 / 0.06 |
| `l1_w = 2.0`，目标=类中心 | -1.92 / 0.05 | +2.06 / 0.05 |
| 真实数据 | -2.00 / 0.30 | +2.00 / 0.30 |

解释：L1 的最优解是条件中位数（这里就是类中心），它对所有 `z` 都给出同一个答案，于是 G 学会**忽略噪声**，输出几乎是确定性的。均值变准了，多样性却丢了（0.3 → 0.06–0.10）。这就是 1-D 版本的"λ 太大 → 糊/缺乏多样性"，也解释了 Pix2Pix 作者为什么观察到"显式噪声被忽略"。反过来，无 L1 的原始模型均值偏出约 0.5、标准差偏大，说明纯对抗训练也远不完美。

### Q11 — 参考答案

```python
import random, statistics
from main import g_forward

def per_class_stats(G, num_classes, z_dim, n=1000, seed=99):
    rng = random.Random(seed)            # 独立随机数，不干扰训练用的 rng
    stats = []
    for c in range(num_classes):
        outs = [g_forward([rng.gauss(0, 1) for _ in range(z_dim)], c, G, num_classes)[0][0]
                for _ in range(n)]
        stats.append((statistics.mean(outs), statistics.pstdev(outs)))
    return stats

def check_conditional(stats, centers, std_true, tol_mean=0.3, tol_std_ratio=1.5):
    ok = True
    for c, ((m, s), mu) in enumerate(zip(stats, centers)):
        if abs(m - mu) > tol_mean:
            print(f"class {c}: mean {m:+.2f} off target {mu:+.2f}")
            ok = False
        if s > tol_std_ratio * std_true:
            print(f"class {c}: std {s:.2f} > {tol_std_ratio} x {std_true}")
            ok = False
    return ok
```

需要在 `main()` 末尾加上 `return G`（或在 `main` 内部直接调用）。对 `main()` 训练完的模型，我复现得到每类统计量约为 `[(-2.55, 0.62), (+2.46, 0.46)]`，检查结果：

```text
class 0: mean -2.55 off target -2.00
class 0: std 0.62 > 1.5 x 0.3
class 1: mean +2.46 off target +2.00
class 1: std 0.46 > 1.5 x 0.3    # 0.46 > 0.45，刚好越线
False
```

要点：
- `main()` 的日志只打印均值（-2.56 / +2.47），看起来"方向对了"，但均值偏出约 0.5、类内标准差是真实值的 1.5–2 倍。**只看均值会高估条件生成的质量**。
- 讲义 Pitfalls 的 "Mode collapse per class" 提醒还要做逐类多样性检查——标准差过小（如 Q10(c) 的 0.06）同样要报警，可以再加一个下界。
- 评估用独立的 `random.Random(seed)`，避免改变训练用的随机流。

### Q12 — 参考回答要点

- **区别**：普通 GAN 学 `p(x)`，cGAN 学 `p(x | c)`；G 和 D 都额外接收条件 `c`。
- **注入方式**：最简单是把 one-hot / embedding 拼接到输入（本节代码）；更强的有 FiLM（由条件生成每个通道的缩放和偏移）、cross-attention（文本等序列条件）、SPADE（用语义图做空间自适应归一化）；判别器侧有 projection discriminator（Miyato & Koyama 2018，把条件 embedding 与特征做内积）。
- **D 必须看条件**：否则 D 只能评估边缘分布的真实性，G 输出任意一个"像真的"样本都能过关，条件会被忽略；D 看到 `(x, c)` 才能惩罚"真实但与条件不符"的样本。
- 加分点：讲义建议"在早层就给 D 注入条件，而不是只在最后几层"。

### Q13 — 参考回答要点

| 设计 | 解决的问题 |
|------|-----------|
| U-Net 生成器 | 输入输出共享低层结构，skip 连接让边缘、轮廓等高频细节绕过瓶颈直接到达解码器 |
| PatchGAN 判别器 | 只判断约 70×70 的局部块是否真实（MRF 假设），参数少、训练快、能驱动高频细节；可用于任意尺寸 |
| 对抗 + L1 | 对抗项负责"看起来真实/锐利"（高频），L1 负责"忠实于目标"（低频、全局结构），并稳定训练 |
| λ = 100 | L1 是主要的监督信号，对抗项做"锐化"；λ 太小 → 输出不忠实，λ 太大 → 变糊 |
| dropout 代替输入噪声 | 显式噪声在强条件 + 强 L1 下会被忽略；dropout 在训练和测试时都开启，提供少量随机性 |

- 常见误区：认为 PatchGAN 是"把图像切块分别判别"——实际上是全卷积网络，输出网格的每个位置对应一个重叠的感受野。
- 加分点：说出 Pix2PixHD 用多尺度判别器 + 特征匹配损失把分辨率推到 2048×1024。

### Q14 — 参考回答要点

- **结构**：两个生成器 `G: X → Y`、`F: Y → X`，两个判别器 `D_Y`、`D_X`。
- **损失**：`L = L_adv(G, D_Y) + L_adv(F, D_X) + λ_cyc · ( ||F(G(x)) - x||₁ + ||G(F(y)) - y||₁ )`。
- **为什么需要循环项**：只有对抗损失时，`G` 只需把 x 映射到"任何一个看起来像 Y 的图"，可以完全不保留 x 的内容（甚至所有输入都映射到同一张图）；映射是严重欠约束的。循环一致性要求"翻译过去还能翻译回来"，迫使 G 保留输入的内容信息。
- **局限**：
  1. 难以做几何形状的大变化（擅长纹理/颜色/风格，如马↔斑马、夏↔冬）；
  2. G 可能把还原所需的信息以人眼不可见的方式"藏"在输出里来满足循环项；
  3. 两套 G/D，训练成本翻倍；
  4. 2026 年非配对翻译多用扩散（ControlNet、IP-Adapter），但循环一致性思想仍出现在大量非配对域适应工作里（讲义）。

### Q15 — 参考回答要点

1. **草图 → 渲染，5000 对，50 ms**：Pix2Pix（或高分辨率需求用 Pix2PixHD）。配对数据充足（技能文件：少于 500 对必须配合数据增强 / 预训练）；一次前向满足延迟（讲义：512² 约 30 ms）。架构：U-Net G、带谱归一化的 PatchGAN D、对抗 + L1（可加 VGG 感知损失）。评估：留出配对数据上的 LPIPS、FID（5k 样本）、人工偏好。
2. **白天 → 夜晚，无配对**：CycleGAN 或基于 ControlNet 的扩散方案（讲义 Use It 表：Daytime → nighttime 选 CycleGAN 或 ControlNet-based）。视频还需额外关注时间一致性。评估：FID、人工评估、下游任务效果。
3. **任意文本描述编辑**：扩散 + ControlNet（或 SD3 / Flux.1 + 相应适配器）。技能文件："Flag any request that says 'arbitrary text prompt' - those need diffusion + ControlNet, not a paired GAN."
- 加分点：主动提"窄任务部署 Pix2Pix 式快模型 + 长尾输入用扩散兜底"的混合架构。

### Q16 — 参考回答要点

| 方式 | 机制 | 适用 |
|------|------|------|
| 输入拼接 one-hot | 条件向量直接接到输入 | 类别少、模型小（本节代码）；最简单但条件信号可能偏弱 |
| 学习的 embedding | 类别查表得到稠密向量再拼接/相加 | 类别多 |
| FiLM | 条件生成每个通道的 `γ`、`β`，对特征做 `γ·h + β` | 全局条件、开销低（讲义："cheap conditioning"），StyleGAN 的风格调制、扩散的时间步注入都是同类思路 |
| cross-attention | 特征作为 query，条件序列（如文本 token）作为 key/value | 文本等序列条件，Stable Diffusion 的文本注入方式 |
| projection discriminator | D 的输出 = 无条件分数 + 条件 embedding 与特征的内积 | 让判别器更"重视"条件，缓解条件被忽略（讲义 Pitfalls 的推荐修法） |
| SPADE | 用语义分割图逐像素地生成归一化的缩放和偏移 | 语义图 → 图像（GauGAN），条件本身是空间图 |

### Q17 — 参考回答要点

- **可能原因**：
  1. 条件信号太弱：只在 D 的最后几层或只在 G 的输入注入了 one-hot，网络学会"边缘化"掉条件；
  2. D 不看条件或看得太晚（讲义 Pitfalls 第一条）；
  3. 重构项（如 L1）权重过大、目标与条件关系弱，G 输出折中答案；
  4. 数据中条件与输出的相关性本来就弱或标签有噪声。
- **检测**：固定 `z`、遍历所有条件，比较输出差异；逐类统计均值/标准差/FID（本节 Q11）；用一个在真实数据上训练好的分类器去分类生成样本，看条件准确率。
- **修复**：在 D 的早层注入条件、改用 projection discriminator；更强的条件注入（FiLM、cross-attention）；调整损失权重；逐类做多样性检查，防止某个类单独模式崩溃。
- 加分点：扩散模型里对应的问题用 classifier-free guidance 放大条件信号，可以类比。

---

## 六、关联知识点

### 前置知识
- [阶段 08 · 03 GANs — 生成器与鉴别器](../../03-gans-generator-discriminator/docs/zh.md)：本节代码在它的基础上只多了"条件输入"。
- [阶段 04 · 07 语义分割与 U-Net](../../../04-computer-vision/07-semantic-segmentation-unet/docs/zh.md)：Pix2Pix 生成器的架构来源。
- [阶段 04 · 03 CNN：从 LeNet 到 ResNet](../../../04-computer-vision/03-cnns-lenet-to-resnet/docs/zh.md)：PatchGAN 的感受野概念。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：L1 / L2 损失与其统计含义（中位数 vs 均值）。

### 本节被哪些后续内容用到
- [阶段 08 · 05 StyleGAN](../../05-stylegan/docs/zh.md)：用风格调制（FiLM 的近亲）注入 latent 条件。
- [阶段 08 · 08 ControlNet、LoRA 与条件控制](../../08-controlnet-lora-conditioning/docs/zh.md)：扩散时代的图像条件控制，接管了大部分开放域 img2img 任务。
- [阶段 08 · 09 局部重绘、扩图与图像编辑](../../09-inpainting-outpainting-editing/docs/zh.md)：讲义生产表中的 SD-Inpaint / Img2Img 路线。
- [阶段 08 · 14 评估：FID、CLIP 分数、人类偏好](../../14-evaluation-fid-clip-score/docs/zh.md)：img2img 的 FID、LPIPS 评估。
- [阶段 04 · 09 图像生成：GAN](../../../04-computer-vision/09-image-generation-gans/docs/zh.md)：视觉方向的 GAN 实践。

### 延伸关键词
`cGAN` · `Pix2Pix / Pix2PixHD` · `U-Net skip connection` · `PatchGAN / 马尔可夫随机场` · `L1 vs L2（中位数 vs 均值）` · `CycleGAN / 循环一致性` · `SPADE / GauGAN` · `FiLM` · `projection discriminator` · `LPIPS` · `ControlNet / IP-Adapter`
