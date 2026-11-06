# 测验 · ControlNet、LoRA 与条件控制（ControlNet, LoRA & Conditioning）

> **阶段 08 · 生成式 AI · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 文本是笨拙的控制信号 | 提示词只能确定画面的一小部分（讲义说约 10%），位置、姿态、透视等空间信息很难用文字高效描述 |
| 2 | ControlNet 结构 | 复制预训练 U-Net 的编码器半边并训练这份副本读入条件图（边缘/深度/姿态），原模型冻结，副本输出经 zero-conv 加回原解码器 |
| 3 | Zero convolution | 初始化为 0 的 1×1 卷积；训练开始时 ControlNet 是 no-op，不会破坏预训练模型，之后逐步学出增量 |
| 4 | 多 ControlNet 组合 | `features += w_a·control_a(depth) + w_b·control_b(pose)`；权重之和约为 1.0 是安全默认值，各设 1.0 容易过冲 |
| 5 | LoRA | 冻结 `W`，学习 `ΔW = B·A`（`A: r×d`，`B: d×r`，`r ≪ d`），新参数 `2dr` 而不是 `d²`；推理时可以用 `α` 缩放 |
| 6 | LoRA 的使用与部署 | 注意力层常用 rank 4–16，重度微调用 64–128；`α` 常用 0.5–1.5；合并进权重略快，但失去运行时调 `α` 和热切换的能力 |
| 7 | IP-Adapter | 用 CLIP 图像编码器把参考图变成 image token，与文本 token 一起注入 cross-attention，不用 LoRA 就能"照着参考图的风格生成" |
| 8 | 工具分工 | ControlNet ≈ 空间结构，LoRA ≈ 语义（风格/主体/概念）；另有 Textual Inversion、DreamBooth、T2I-Adapter 等 |
| 9 | 多租户服务 | 同一底座上热加载上百个 LoRA（`load_lora_weights` + `set_adapters`）；每个激活的 ControlNet 都要多跑一次前向 |

### 核心技能（能动手做到）

- [ ] 运行 `code/main.py`，解释为什么 r = 1、2、4 都能把秩 1 的目标增量拟合到 MSE ≈ 0
- [ ] 把目标增量改成秩 2，验证 r = 1 的残差停在 `σ₂²`（第二奇异值的平方）附近，而 r ≥ 2 降到 0
- [ ] 给定层维度 `d` 和秩 `r`，手算 LoRA 参数量和压缩倍数（如 `d=640, r=16` → 20,480 vs 409,600）
- [ ] 能用梯度推导说明：为什么 zero-init 的门控/卷积在第 0 步仍有梯度，而"副本网络和门控都置 0"会卡住
- [ ] 能为"品牌风格 + 指定姿态 + 参考产品图"这类需求设计 ControlNet + LoRA + IP-Adapter 组合，并给出合理权重
- [ ] 能说清 LoRA 合并与热切换的取舍，以及多租户服务中 ControlNet 的额外算力开销

---

## 二、基础自测（选择题）

**Q1.** ControlNet 把旁路输出接回主干时使用"初始化为 0 的 1×1 卷积"，最主要的目的是：

- A. 减少 ControlNet 的参数量
- B. 训练开始时 ControlNet 的输出为 0，整个模型的行为与原始预训练模型完全一致，不会被随机初始化的旁路破坏
- C. 让旁路网络输出的特征保持稀疏
- D. 加快推理速度，因为大部分卷积核是 0

**Q2.** 对一个 `640×640` 的注意力投影矩阵加 rank `r = 16` 的 LoRA，新增的可训练参数量是：

- A. 409,600
- B. 20,480
- C. 10,240
- D. 256

**Q3.** 关于 ControlNet 的训练方式，下列说法正确的是：

- A. 用条件图重新训练整个 U-Net
- B. 复制 U-Net 的解码器半边，冻结编码器
- C. 复制 U-Net 的编码器半边并训练这份副本，原始 U-Net 保持冻结
- D. 只微调 U-Net 中的 cross-attention 层

**Q4.** IP-Adapter 让模型"参考一张图片的风格/主体"，它的注入方式是：

- A. 把参考图经 VAE 编码后拼接到潜变量的通道维
- B. 用 CLIP 图像编码器生成 image token，与文本 token 一起注入 cross-attention
- C. 用参考图替换文本编码器，完全不再使用提示词
- D. 把参考图转成边缘图，再交给 ControlNet

**Q5.** 标准 LoRA 初始化时通常 `A` 随机、`B = 0`。如果 `A` 和 `B` **都**初始化为 0，会怎样？

- A. 训练更稳定，收敛更快
- B. 与标准初始化等价
- C. `ΔW = 0`，且 `A`、`B` 的梯度都为 0，参数永远不会更新
- D. 模型输出会立刻变成随机噪声

**Q6.** 把一个 LoRA 合并（merge）进底座权重 `W' = W + α·B·A` 后，**失去**的是：

- A. LoRA 学到的风格
- B. 运行时调节 `α` 和按请求热切换不同 LoRA 的能力
- C. 使用 CFG 的能力
- D. 与 ControlNet 组合使用的能力

**Q7.** 同时启用 Pose ControlNet 和 Depth ControlNet，各自权重都设为 1.0，讲义指出的常见问题是：

- A. 两者会互相抵消，结果等于不用 ControlNet
- B. 通常会过冲（overshoot），权重之和约为 1.0 是更安全的默认值
- C. diffusers 不允许同时加载两个 ControlNet
- D. 只有最后加载的 ControlNet 会生效

**Q8.** 按讲义的"ControlNet ≈ ?，LoRA ≈ ?"分工，下列需求与工具搭配**最不合理**的是：

- A. 指定人物姿态 → ControlNet-Openpose
- B. 复刻某品牌的画风 → 在约 30 张精选图上训练 LoRA
- C. 精确控制画面布局 → ControlNet-Canny / Scribble
- D. 精确控制画面里物体的位置 → 只靠加大 LoRA 的 `α`

---

## 三、动手 / 代码题

**Q9.** 阅读 `train_lora` 的更新部分：

```python
    A = randn_matrix(r, d, rng, scale=0.2)
    B = [[0.0] * r for _ in range(d)]
    for step in range(steps):
        # ...
        Ax = matmul_mat_vec(A, x)
        for i in range(d):
            for k in range(r):
                grad_B = err[i] * Ax[k]
                B[i][k] -= lr * grad_B
        for k in range(r):
            for j in range(d):
                grad_A = sum(err[i] * B[i][k] for i in range(d)) * x[j]
                A[k][j] -= lr * grad_A
```

(a) 第 0 步时（`B` 全为 0），如果先算出两个梯度、再**同时**更新，`grad_A` 是多少？
(b) 按代码的实际写法，第 0 步 `A` 会不会被更新？为什么？
(c) 这里的 `grad_B = err[i] * Ax[k]` 对应的是哪个损失函数的梯度？

**Q10.**（找问题 + 扩展）`main()` 里有这样两段：

```python
    delta = rng.choice([1, 2, 3])
    delta_matrix = zeros(d, d)
    u = [rng.gauss(0, 1) for _ in range(d)]
    v = [rng.gauss(0, 1) for _ in range(d)]
    for i in range(d):
        for j in range(d):
            delta_matrix[i][j] = u[i] * v[j] * 0.5
```

(a) 变量 `delta` 起了什么作用？目标增量 `delta_matrix` 的秩是多少？
(b) 输出 `takeaway: LoRA needs rank >= true delta rank to converge exactly.` 被当前实验证明了吗？
(c) 改写这段代码，构造秩为 `delta` 的目标增量，并预测 `delta = 2` 时 r = 1 / 2 / 4 的残差表现。

**Q11.** `controlnet_toy` 中：

```python
    w_side = rng.gauss(0, 0.1)
    gate = 0.0          # zero-conv init
    # ...
        pred = x + gate * w_side * c
        err = pred - target
        grad_gate = 2 * err * w_side * c
        grad_wside = 2 * err * gate * c
```

(a) 第 0 步时哪个参数的梯度为 0？哪个不为 0？
(b) 如果把 `w_side` 也初始化为 `0.0`，训练会怎样？这对理解真实 ControlNet "副本从预训练权重复制、只有连接处置 0"有什么启发？
(c) 实际运行时 `gate ≈ 0.833`、`w_side ≈ 0.840`，它们的乘积约等于多少？为什么最终两者几乎相等？

---

## 四、面试高频题

**Q12.**（基础必考）讲讲 LoRA 在扩散模型中的用法：加在哪些层？rank 和 `α` 怎么选？参数量和文件大小大概是多少？为什么低秩就够用？

**Q13.**（原理深挖）ControlNet 为什么要"复制编码器 + zero convolution"，而不是直接微调整个 U-Net，或从零训练一个条件模型？zero-conv 初始输出为 0，为什么还能学到东西？

**Q14.**（场景设计）电商客户要求：用自家品牌的画风、让模特摆出指定姿势、手里拿着他们给的那款产品（有参考图）。请设计生成管线，给出各组件和权重，并说明质检要点。

**Q15.**（工程实践）你在做一个文生图 SaaS，同一个 SDXL/Flux 底座要服务上百个用户自定义 LoRA 和十几种 ControlNet。说说 LoRA 应该合并还是热切换、ControlNet 的成本怎么估算、显存怎么规划。

**Q16.**（追问型）每一层的 `ΔW` 明明是线性相加的，为什么同时叠加两个 LoRA 的效果常常不是"两者效果之和"？实际中怎么处理？

**Q17.**（对比型）比较 ControlNet、T2I-Adapter、IP-Adapter、LoRA、DreamBooth、Textual Inversion：各自控制什么、体量多大、什么时候用？

---

## 五、参考答案与解析

### Q1 — 答案：B

zero-conv 的权重和偏置都初始化为 0，所以训练开始时旁路贡献为 0，模型输出与原 SD **完全一致**（讲义："ControlNet starts as identity — no harm even before training"）。如果用随机初始化，第一步就会往主干特征里注入大噪声，破坏预训练模型的生成能力。A 错：1×1 卷积参数很少，但这不是置 0 的目的；D 错：训练后权重不再是 0。

### Q2 — 答案：B

`2·d·r = 2 × 640 × 16 = 20,480`，原矩阵 `640² = 409,600`，正好是讲义中"约 20 倍压缩"的例子。C 是只算了 `A` 或 `B` 一个矩阵的错误答案；A 是全量更新的参数量。

### Q3 — 答案：C

讲义原文：*Clone* the encoder half of the U-Net. Freeze the original. Train the clone……副本带着预训练权重出发，学会读取条件图；原模型完全冻结，所以 ControlNet 可以作为独立的小模型发布、按需挂载。

### Q4 — 答案：B

IP-Adapter 用 CLIP 图像编码器得到 image token，与文本 token 并行注入 cross-attention，是一个约 20MB 量级的小适配器。A 是 inpainting 模型拼接 mask/原图通道的做法；D 混淆成了 ControlNet。

### Q5 — 答案：C

`B·A` 对 `A` 的梯度含因子 `B`，对 `B` 的梯度含因子 `A`。两者都为 0 时梯度都为 0，这是一个**鞍点**，梯度下降永远离不开。标准做法 `B = 0, A ≠ 0` 同时满足两点：①`ΔW = 0`，训练开始时不改变模型；②`B` 的梯度 `∝ A·x ≠ 0`，可以立即开始学习。这和 ControlNet 的 zero-conv 思想完全一致（见 Q11）。

### Q6 — 答案：B

讲义 Pitfalls 与 Production note：合并后没有运行时加法，单步大约快 3–5%，但 `α` 和底座都被"冻住"了，也没法按请求切换 LoRA。建议两种版本都保留。风格本身（A）不会丢失。

### Q7 — 答案：B

两个 ControlNet 的残差都加到同一组特征上，各 1.0 相当于总共"推"了两倍的强度，常常会过冲、互相打架。讲义给出的安全默认值是"权重之和 ≈ 1.0"（配套 skill 文件放宽到总和 ≤ 1.5，并拒绝 3 个以上各 1.0 的组合）。

### Q8 — 答案：D

位置、构图属于**空间结构**，应该交给 ControlNet；LoRA 管语义（风格、主体、概念），调大 `α` 只会让风格过度、画面崩坏（讲义：`α = 2~3` 会过度风格化，保持 `α ≤ 1.5`），控制不了物体放在哪。

### Q9 — 参考答案

(a) `grad_A[k][j] = (Σᵢ err[i]·B[i][k])·x[j]`。`B` 全为 0 时求和为 0，所以 **`grad_A = 0`**。这正是"`B = 0` 初始化"的特性：第 0 步只有 `B` 在学。

(b) **会更新**。代码先用 `grad_B` 原地更新了 `B`，再用**已经更新过的** `B` 计算 `grad_A`，所以第 0 步 `A` 也拿到了非零梯度。这是一种"交替/顺序更新"（类似 Gauss–Seidel），严格来说不是同一点上的联合梯度；在小学习率下影响很小，但面试时能指出来是加分点。PyTorch 的标准做法是先 `backward()` 算出全部梯度，再由 `optimizer.step()` 统一更新。

(c) `err = pred − target`，`∂pred[i]/∂B[i][k] = Ax[k]`，所以 `grad_B = err[i]·Ax[k]` 是 **`½·Σᵢ err[i]²`**（半平方误差）的梯度。少了因子 2，相当于把学习率减半，不影响收敛点。

### Q10 — 参考答案

(a) `delta` **没有被使用**——它只是消耗了一次随机数。`delta_matrix[i][j] = 0.5·u[i]·v[j]` 是外积 `0.5·u·vᵀ`，**秩恒为 1**。（种子 17 下 `delta` 实际取到 3，看得出作者原意可能是构造秩为 `delta` 的增量。）

(b) **没有被证明**。目标秩为 1，r = 1、2、4 都满足 `r ≥ 1`，输出都是 `0.00000`，实验里没有 `r < 真实秩` 的对照组。

(c) 改写：

```python
    delta = 2
    delta_matrix = zeros(d, d)
    for _ in range(delta):                     # 叠加 delta 个秩 1 外积
        u = [rng.gauss(0, 1) for _ in range(d)]
        v = [rng.gauss(0, 1) for _ in range(d)]
        for i in range(d):
            for j in range(d):
                delta_matrix[i][j] += u[i] * v[j] * 0.5
```

在同样种子下实测（`steps=4000`）：

| lr | r = 1 | r = 2 | r = 4 |
|----|-------|-------|-------|
| 0.01（默认） | `nan`（发散） | 0.0 | 0.0 |
| 0.003 | ≈ 10.70 | 0.0 | 0.0 |

解读：
- r ≥ 2 时能精确表示秩 2 的增量，残差降到 0；
- r = 1 时最好也只能学到最优秩 1 近似（Eckart–Young 定理），残差 = `‖Δ − Δ₁‖_F² = σ₂²`。用 NumPy 算出该增量的 `σ₂² ≈ 11.30`，评估时只用 500 个样本估计，所以测出约 10.7；
- 默认 `lr = 0.01` 下 r = 1 甚至发散：残差永远消不掉，单样本 SGD 的梯度噪声一直存在，因子被推大后步长失稳。这也提醒我们：**秩不够时，问题不只是"拟合得差"，训练也可能变得不稳定**。

### Q11 — 参考答案

(a) `gate = 0` 时 `grad_wside = 2·err·gate·c = 0`；`grad_gate = 2·err·w_side·c ≠ 0`（`w_side` 是随机小数）。所以**先动的是门控**，门控离开 0 之后，旁路的 `w_side` 才开始拿到梯度。真实 ControlNet 也一样：zero-conv 的权重梯度正比于输入特征（不为 0），所以 zero-conv 先学；它变成非零后，梯度才流进 ControlNet 副本。

(b) 两者都为 0 时，两个梯度都恒为 0，`gate` 和 `w_side` **永远停在 0**——和 Q5 的 LoRA 双零初始化一样是鞍点。启发：ControlNet 只把**连接处**（zero-conv）置 0，副本本身从预训练编码器复制而来，有有意义的非零权重，所以既能保证"开局 no-op"，又不会让梯度消失。

(c) `0.833 × 0.840 ≈ 0.700`，正好等于目标里的系数 `0.7`。两者几乎相等是因为乘积参数化 `gate·w_side` 在（小学习率的）梯度流下有一个守恒量：`gate² − w_side²` 近似不变。开局时它等于 `−w_side₀²`，是个很小的负数，所以收敛后 `gate` 比 `w_side` 略小一点，两者接近"平衡"。另外这组输出在第 100 步就已经收敛，`trace[::2][:6]` 只打印了第 100/300/500/700 步，**看不到"从 0 爬升"的过程**——想看到爬升，需要打印前 100 步（见代码讲解第 7 节）。

### Q12 — 参考回答要点

- **位置**：主要挂在 U-Net/DiT 注意力的线性投影（Q/K/V/out）上，也可以扩展到 FFN 或卷积层。
- **公式**：`W' = W + α·B·A`，`A ∈ R^{r×d}`，`B ∈ R^{d×r}`，`B` 零初始化。
- **超参**：讲义建议注意力层 rank 4–16，重度个性化 64–128（品牌风格的例子是 rank 32、约 30 张图）；`α` 推理时常用 0.5–1.5，超过 1.5 容易过度风格化。
- **体量**：每层 `2dr` 而不是 `d²`；整模型的 LoRA 文件通常 20–200MB，底座约 5GB。
- **为什么够用**：预训练模型已具备通用能力，适配一个风格/主体只需要在少数方向上调整权重——"更新量的内在秩很低"。
- **常见误区**：LoRA 不是只能用于 LLM；讲义指出 LoRA 原本为 LLM 提出，后来移植到扩散模型。还有跨底座混用的问题：SDXL 的 LoRA 用不到 SD 1.5 上（维度不匹配）。

### Q13 — 参考回答要点

- **对比方案**：
  - 从零训练条件模型：每种条件（姿态、深度、边缘……）都训一个大模型，成本不可接受；
  - 直接微调整个 U-Net：在约百万级（prompt, condition, image）三元组上调整全部权重，容易灾难性遗忘，也无法与其他条件、LoRA 自由组合。
- **ControlNet 的做法**：复制编码器半边，副本带着预训练能力出发学习"怎么读条件图"；原模型冻结、能力不受影响；副本以小模型形式独立发布，可以按需挂载、按权重组合多个。
- **zero-conv 为什么能学**：设 `y = W·f + b`，`W = 0, b = 0`。`∂L/∂W = ∂L/∂y · fᵀ`，`f` 是副本输出的特征（非零），所以 `W` 第一步就有梯度；而 `∂L/∂f = Wᵀ·∂L/∂y = 0`，副本第一步拿不到梯度，等 `W` 变成非零后才开始学。本节 `controlnet_toy` 中 `gate` / `w_side` 的动态正是这一过程的标量版本。
- **加分点**：训练使用标准扩散损失；推理时 ControlNet 权重可调，并且可以多个叠加。

### Q14 — 参考回答要点

一个合理的组合（参考讲义 Use It 表与 skill 文件）：

| 组件 | 选择 | 权重/参数 | 作用 |
|------|------|----------|------|
| 底座 | SDXL（LoRA/ControlNet 生态最成熟）或 Flux | — | — |
| 风格 | 品牌画风 LoRA（约 30 张精选图，rank 32） | `α ≈ 0.8`，≤ 1.5 | 语义：画风 |
| 姿态 | ControlNet-Openpose | ≈ 0.8–1.0；多个 ControlNet 时权重和约为 1 | 空间：姿态 |
| 产品外观 | IP-Adapter（参考产品图） | 0.4–0.8 | 参考图的外观 |
| 文本 | 描述场景、模特、产品 + 负向提示词 | CFG 按底座设定 | 其余语义 |
| 复现 | 固定 seed、记录全部权重 | — | 可复现、可 A/B |

- **质检**：ControlNet 是否漂移（姿态是否对上）、LoRA 是否过饱和、IP-Adapter 的身份/外观是否泄漏到不该出现的地方、手和肢体解剖结构；产品细节（logo、文字）不对时用 inpainting 局部重绘（第 09 节）。
- **加分点**：讲义练习 3 建议扫描各组件权重、画出 FID 与提示词遵循度的权衡曲线，而不是拍脑袋定权重。

### Q15 — 参考回答要点

- **LoRA：热切换，不合并**。合并只快约 3–5%，却冻住了 `α` 和底座；把 LoRA 以 rank-r 增量的形式常驻显存，用 `pipe.load_lora_weights()` + `pipe.set_adapters([...], adapter_weights=[...])` 按请求激活。切换成本只是 `2·d·r·num_layers` 个权重，MB 级、亚秒完成。思路与 LLM 侧的 LoRAX / S-LoRA 多租户服务相同。
- **ControlNet：额外的一条前向通道**。每个激活的 ControlNet 都要跑一次副本前向，两个 ControlNet 就是每步多两次前向，不会合并成一次。讲义建议按每个 ControlNet 约 1.5 倍单步成本来做预算；它也会挤占可用的 batch 空间。
- **显存**：底座可以 4-bit 量化（接第 07 节 Flux-on-8GB），LoRA 增量也能量化到 8/4-bit，QLoRA 风格加载能在 4-bit Flux 上叠 5–10 个 LoRA。
- **加分点**：按"底座 + 激活的 ControlNet 组合"给请求分组做 batching；热门 LoRA 常驻显存、冷门的放 CPU 内存做 LRU；一定要校验 LoRA 与底座是否匹配。

### Q16 — 参考回答要点

- 单层上确实是线性的：`W' = W + α₁B₁A₁ + α₂B₂A₂`。
- 但网络整体是**非线性**的：多层堆叠、softmax 注意力、激活函数、归一化都会让"两个增量的效果"互相耦合，输出不等于各自效果之和（讲义："they interact in non-linear ways"）。
- 两个 LoRA 若作用于同一概念（如都在改人脸），会互相争夺同一组方向，导致过饱和或特征打架（skill 文件要求对此给出警告）。
- **处理方式**：分别降低 `α`（如各 0.6–0.8），保证总强度不过高；用网格扫描找最佳组合；必要时把多个概念合并成一个 LoRA 联合训练；讲义练习 2 要求亲手验证"什么时候线性被打破"。

### Q17 — 参考回答要点

| 工具 | 控制什么 | 体量（讲义） | 何时用 |
|------|---------|-------------|-------|
| ControlNet | 空间结构（姿态、深度、边缘） | 70–360MB | 精确布局、构图 |
| T2I-Adapter | 同上，更轻 | 约 70MB | 边缘设备、推理预算紧 |
| IP-Adapter | 参考图的风格或主体 | 约 20MB | 文字描述不出的"那种感觉" |
| LoRA | 风格、主体、概念 | 20–200MB | 个性化、风格化，最通用 |
| DreamBooth | 全量微调一个主体 | 2–5GB | 身份要求极强、算力充足 |
| Textual Inversion | 学一个新词向量 | 约 10KB | 已基本被 LoRA 取代；跨 checkpoint 漂移严重 |

- 一句话：**ControlNet 管"在哪、什么形状"，LoRA 管"是什么、什么风格"，IP-Adapter 管"像这张图"**，三者可以叠加使用。

---

## 六、关联知识点

### 前置知识
- [阶段 08 · 07 潜空间扩散与 Stable Diffusion](../../07-latent-diffusion-stable-diffusion/docs/zh.md)：U-Net 编码器/解码器、cross-attention、CFG，是 ControlNet 和 IP-Adapter 的挂载点。
- [阶段 11 · 08 LoRA 微调](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：LoRA 在 LLM 上的原始形态。
- [阶段 01 · 11 奇异值分解](../../../01-math-foundations/11-singular-value-decomposition/docs/zh.md)：低秩近似、Eckart–Young 定理，解释"秩不够时残差 = 剩余奇异值的平方和"。
- [阶段 12 · 02 CLIP 对比预训练](../../../12-multimodal-ai/02-clip-contrastive-pretraining/docs/zh.md)：IP-Adapter 依赖的 CLIP 图像编码器。

### 本节被哪些后续内容用到
- [阶段 08 · 09 局部重绘、扩图与图像编辑](../../09-inpainting-outpainting-editing/docs/zh.md)：ControlNet-Openpose + Inpaint 修手/脸，ControlNet-Seg + Inpaint 换背景。
- [阶段 08 · 10 视频生成](../../10-video-generation/docs/zh.md)：开源视频模型（如 WAN 2.2）同样用 LoRA 做快速微调。
- [阶段 08 · 04 条件 GAN 与 Pix2Pix](../../04-conditional-gans-pix2pix/docs/zh.md)：回看"草图→照片、分割图→照片"这类任务如何从 GAN 迁移到 ControlNet。
- [阶段 08 · 14 评估：FID、CLIP 分数、人类偏好](../../14-evaluation-fid-clip-score/docs/zh.md)：衡量组件权重带来的质量与提示词遵循度权衡。

### 延伸关键词
`zero convolution` · `LoRA rank / alpha` · `LoRA merge vs hot-swap` · `S-LoRA / LoRAX` · `IP-Adapter-FaceID` · `T2I-Adapter` · `DreamBooth` · `Textual Inversion` · `LCM-LoRA` · `Eckart–Young` · `QLoRA`
