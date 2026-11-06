# 测验 · Transfusion：在同一个 Transformer 中结合 Autoregressive 文本与扩散图像（Transfusion: Autoregressive Text + Diffusion Image in One Transformer）

> **阶段 12 · 多模态 AI · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 离散 vs 连续之争 | 离散 VQ token 能直接进 Transformer 词表但量化会丢细节；连续表示（像素/VAE latent）保细节但需要扩散这类连续生成目标 |
| 2 | Transfusion 的赌注 | 与 Chameleon/Emu3 相反：图像保持连续、去掉 VQ，**一个** Transformer 同时用两种损失训练 |
| 3 | 两个损失、一份权重 | 文本 token → 词表 logits 上的交叉熵（NTP）；图像 patch → 扩散/flow matching 的 MSE；梯度在同一次反传里汇入共享主干 |
| 4 | 混合注意力 mask | 文本之间因果；同一张图的 patch 之间双向；图像能看前面的文本，后面的文本能看整张图 |
| 5 | Flow matching 训练目标 | `x_t = (1 − t)·x0 + t·ε`，网络预测速度 `v_θ(x_t, t)`，目标是 `ε − x0`，损失 MSE |
| 6 | 推理两条路径 | 文本逐 token 自回归采样；遇到 `<image>` 后对所有 patch 并行做 10–30 步去噪，以前面的文本为条件 |
| 7 | MMDiT（SD3） | Transfusion 的"兄弟"：每个 block 里文本和图像有各自的 QKV / MLP / norm 权重，只有注意力是联合的 |
| 8 | 相对 Chameleon 的优势 | 讲义：7B 时 FID 领先同规模 Chameleon 式模型 3–5 点；无需训练 VQ tokenizer；图像 patch 可并行去噪 |
| 9 | 两损失的代价 | 损失量级不同，需要调权重（按梯度范数比）；两种目标的"节奏"不匹配会让一个头主导训练 |
| 10 | 下游演化 | Janus-Pro 解耦理解/生成编码器；Show-o 改用离散扩散（掩码预测）；统一生成家族自此快速分化 |

### 核心技能（能动手做到）

- [ ] 给定任意"文本 + 图像"交错序列，画出正确的混合注意力 mask，并能用一行条件表达式实现它
- [ ] 写出 flow matching 的加噪公式、速度目标和 MSE 损失，并解释 `ε − x0` 为什么是速度
- [ ] 用 Euler 法从 `t = 1` 积分到 `t = 0` 完成采样，并解释为什么"直线路径"可以少步
- [ ] 读出 `code/main.py` 中 `build_mask` 对 `<image>`/`</image>` 标签和多图序列的错误，以及 `two_loss_step` 的"假训练"
- [ ] 计算一次"文本 + 图像"生成需要多少次前向，以及开 CFG 后如何变化
- [ ] 估算 MMDiT 模态专属权重带来的参数开销，并根据损失量级与梯度范数设置两损失的权重

---

## 二、基础自测（选择题）

**Q1.** Transfusion 训练时如何处理一条同时含文本和图像的序列？

- A. 先把图像用 VQ-VAE 量化成离散 token，然后整条序列只用 NTP 交叉熵
- B. 一次前向，文本位置用交叉熵、图像 patch 位置用扩散/flow matching 的 MSE，两个损失加权求和后一起反传到共享权重
- C. 文本和图像分别送入两个独立的 Transformer，最后把损失相加
- D. 先训练文本模型，冻结后再训练一个扩散头

**Q2.** 采用 flow matching 时，`x_t = (1 − t)·x0 + t·ε`。网络应预测的速度目标是：

- A. `ε`
- B. `x0`
- C. `x0 − ε`
- D. `ε − x0`

**Q3.** 在 Transfusion 的注意力 mask 中，一个**图像 patch** 位置可以看到：

- A. 同一张图里的所有 patch（包括它后面的），以及图像之前的文本
- B. 只能看到它前面的 patch 和前面的文本（严格因果）
- C. 整条序列的所有位置，包括图像之后的文本
- D. 只能看到同一张图里的 patch，看不到任何文本

**Q4.** MMDiT（Stable Diffusion 3）与 Transfusion 相比，最主要的结构差异是：

- A. MMDiT 用离散 VQ token，Transfusion 用连续 patch
- B. MMDiT 没有注意力层，只有 MLP
- C. MMDiT 每个 block 中文本与图像使用各自的 QKV / MLP 权重，只在注意力处联合；Transfusion 所有权重完全共享
- D. MMDiT 只做文本生成

**Q5.** 讲义练习 4：给定文本 prompt，模型先自回归生成 50 个文本 token，遇到 `<image>` 后对 256 个 patch 做 20 步去噪。不开 CFG、使用 KV cache，大约需要多少次前向？

- A. 约 70 次（50 次文本 + 20 次去噪，每次去噪并行处理全部 256 个 patch）
- B. 约 5,170 次（50 + 256 × 20）
- C. 约 306 次（50 + 256）
- D. 约 1,000 次（固定 1,000 个扩散时间步）

**Q6.** 为什么同一张图内的 patch 之间可以用**双向**注意力，而文本必须因果？

- A. 因为图像 patch 数量比文本少，双向注意力更省算力
- B. 因为双向注意力能避免梯度消失
- C. 因为图像 patch 不需要位置编码
- D. 因为一张图的所有 patch 在扩散中是**同时**被去噪的，不存在"先生成哪个 patch"的顺序；而文本是逐 token 自回归生成的，看到未来 token 会破坏 teacher forcing

**Q7.** 讲义练习 1：图像扩散损失的量级约为文本 NTP 损失的 10 倍。若想让两者对总损失的贡献大致相当，最直接的起始设置是：

- A. `text_w = 0.1, img_w = 1.0`
- B. `text_w = 1.0, img_w = 10.0`
- C. `text_w = 1.0, img_w ≈ 0.1`，再按梯度范数比微调
- D. 两者都设为 1.0，量级差异会被优化器自动消除

**Q8.** 讲义列出的 Transfusion 相对 Chameleon 式模型的优势**不包括**：

- A. 无需单独训练 VQ tokenizer
- B. 推理比纯自回归文本模型更简单，只需一条采样循环
- C. 连续表示避免了量化损失，FID 更好
- D. 同一张图的 patch 可以并行去噪，而不是逐 token 生成

---

## 三、动手 / 代码题

**Q9.** 运行讲义练习 2 的序列 `[T, T, <image>, P, P, P, P, </image>, T]`，`build_mask` 输出：

```text
0 1 . . . . . . . .
1 1 1 . . . . . . .
2 1 1 . . . . . . .
3 1 1 . 1 1 1 1 . .
4 1 1 . 1 1 1 1 . .
5 1 1 . 1 1 1 1 . .
6 1 1 . 1 1 1 1 . .
7 1 1 . . . . . . .
8 1 1 1 1 1 1 1 1 1
```

1. 第 2 行（`<image>`）和第 7 行（`</image>`）有什么问题？如果序列以 `<image>` 开头，第 0 行会是什么？在真实的 softmax 注意力里会出什么错？
2. 对含两张图的序列 `[T, <image>, P, P, </image>, <image>, Q, Q, </image>, T]`，第二张图的 patch `Q` 能看到第一张图吗？这是否合理？
3. 用一行条件表达式重写 `mask[i][j]`，使其符合 Transfusion 的定义（"整条序列因果 + 同一张图内双向"）。

**Q10.** 阅读 `two_loss_step` 与 `train`：

```python
    text_probs = [0.3 + 0.05 * weights["text_scale"] for _ in pair.caption]
    ...
    xt = [[(1 - t) * x + t * n for x, n in zip(row_x, row_n)] ...]
    predicted_vel = [[(n - x) * (0.8 + 0.02 * weights["img_scale"]) ...]]
    ...
        weights["text_scale"] += 1
        weights["img_scale"] += 1
```

1. 输出里 loss 从 1.212 降到 0.357，这是"模型学到了东西"吗？loss 下降的真正原因是什么？
2. 把 `steps` 改成 22，会看到什么不合理的现象？请算出 step 16 的 `text_loss`。
3. `xt` 和 `t` 在函数里起了什么作用？`predicted_vel` 的计算有什么"作弊"之处？
4. 简述一个真正的 two-loss 训练步应包含哪些环节。

**Q11.** 讲义练习 3：一个 32 层、`d = 4096` 的 Transformer，每个 block 的注意力（Q、K、V、O）约 `4d²` 参数，FFN（4 倍扩展）约 `8d²` 参数。

1. Transfusion 式完全共享时，所有 block 合计多少参数？
2. 若改成 MMDiT 式（文本、图像各一套 QKV、O 和 MLP），block 参数变成多少？每个 token 的前向 FLOPs 是否变化？
3. 7B 规模下这值得吗？给出你的判断依据。

**Q12.** 讲义练习 5 问"rectified flow 为什么比 DDPM 少步"。考虑一维数据 `x0 ∈ {−1, +1}`（各 50%），`x_t = (1 − t)x0 + tε`。此时最优速度场为 `v(x, t) = (x − m)/t`，其中 `m = E[x0 | x_t = x] = tanh((1 − t)x / t²)`。用 Euler 法 `x ← x − Δt · v(x, t)` 从 `t = 1` 积分到 `t = 0`：

1. 只走 1 步时，任何初始噪声都会落到哪里？为什么？
2. 若数据只有一个点 `x0 = 1`，走 1 步能否精确到达？
3. 结合两者解释："路径越直，所需步数越少"。

---

## 四、面试高频题

**Q13.**（基础必考）Transfusion 与 Chameleon/Emu3 的根本区别是什么？各自的优缺点？

**Q14.**（原理深挖）请设计 Transfusion 的注意力 mask，并说明每一块为什么这样设计。如果一条序列里有多张图，mask 怎么画？

**Q15.**（原理深挖）解释 flow matching / rectified flow 的训练目标和采样过程，它与 DDPM 的 ε 预测有什么关系？

**Q16.**（工程实践）两损失训练中，文本损失和图像损失量级差 10 倍、token 占比 7:3，你怎么设定和调整损失权重？训练中看到"图像 loss 很快降但文本能力退化"怎么办？

**Q17.**（场景设计）你要做一个"文本 + 音频"的统一生成模型，参照 Transfusion，你会怎么切分模态、设计 mask 和推理流程？什么情况下你会放弃两损失方案？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Forward pass runs once. The loss picks one of two heads per token... The gradient flows through the shared transformer body. Both losses improve the shared weights simultaneously." A 是 Chameleon/Emu3 的做法；C 违背"一个 Transformer"；D 是分阶段训练，不是 Transfusion。

### Q2 — 答案：D

`x_t` 对 `t` 求导：`dx_t/dt = −x0 + ε = ε − x0`，这就是从数据（t=0）走向噪声（t=1）的速度；采样时反向积分即 `x ← x − Δt·v`。讲义："loss = MSE(v_theta(xt, t), ε - x0)"，代码 `target_vel = [[n - x ...]]` 一致。A 是 DDPM 式 ε 预测；B 是 x0 预测；C 符号反了（那是从噪声走向数据的方向，若采用该约定采样公式也要相应变号，但与本节公式不一致）。

### Q3 — 答案：A

同一张图的 patch 之间双向，同时能看到图像之前的文本（讲义："image attends to preceding text"）。B 是 Emu3/Chameleon 式离散 token 的因果生成；C 让图像偷看后文；D 让图像失去文本条件，无法做文生图。

### Q4 — 答案：C

讲义："Each transformer block has separate Q, K, V, and MLP weights for text tokens vs image patches. Attention is joint (cross-modality); everything else is modality-specific." A 错，两者都用连续图像表示；B、D 显然不对。

### Q5 — 答案：A

文本阶段每个 token 一次前向（有 KV cache），共 50 次；图像阶段每个去噪步对 256 个 patch **一起**做一次前向（patch 之间双向注意力），共 20 次；合计约 70 次（再加处理 `<image>` 标签等 1–2 次）。开 CFG 时去噪阶段翻倍为 40 次。B 把 patch 当成逐个生成；C 是 Emu3 式"每个 patch 一个 token"且没算去噪步；D 是 DDPM 训练时的时间步数，与推理步数无关。

### Q6 — 答案：D

讲义："Image patches, however, represent one snapshot; they should attend to each other bidirectionally within the same image block." 扩散对整张图同时去噪，每个 patch 需要看全图来保持全局一致性；文本则是 teacher forcing 训练、逐 token 生成，必须因果。A、B、C 都不是原因（图像 patch 通常比文本多，也需要位置编码）。

### Q7 — 答案：C

量级差 10 倍，最直接是把图像权重设为 0.1，使两项贡献相当；本节代码 `weights = {"text_w": 1.0, "img_w": 0.1}`，outputs 技能文件也写 "Cite Transfusion's ~0.1 default"。但技能文件同时强调"不要只用固定权重，要测梯度范数比"——损失量级 ≠ 梯度量级。A、B 方向反了，会让图像损失进一步主导；D 错，Adam 的逐参数归一化不会平衡两个损失之间的相对贡献。（注："Transfusion 默认 0.1"出自技能文件，讲义正文未给出处；论文中的损失系数 λ 取值请以原文为准。）

### Q8 — 答案：B

讲义明确说 Transfusion 推理有两条路径：文本自回归 + 图像扩散循环；outputs 技能文件还有拒绝规则："If user cannot afford dual inference (NTP + diffusion loops), refuse"。所以"只需一条采样循环"恰恰是它**没有**的优点（Show-o 才是单循环）。A、C、D 都是讲义列出的优势。

### Q9 — 参考答案

1. **标签行的问题**：`in_text` 把 `SEP_OPEN/SEP_CLOSE` 排除在文本之外，它们又不在 `img_ranges` 里（范围从 `<image>` 的下一个位置开始），于是标签"既不是文本也不是图像"：
   - 第 2、7 行**对角线是 0**——标签看不到自己；第 7 行（`</image>`）看不到它前面的图像 patch；第 3–6 行（patch）看不到 `<image>` 标签。
   - 若序列以 `<image>` 开头（已实际运行 `[<image>, P, P, </image>, T]`），第 0 行和第 3 行**全为 0**。真实注意力中整行都是 −∞，softmax 变成 `0/0 = NaN`，NaN 会沿残差传播到整个模型。
2. **多图问题**：已实际运行，`Q` 行只有 `[T]` 和 `Q, Q` 为 1——第二张图看不到第一张图（`same_img` 只允许同一张图内互看，而"图 → 文"分支只放行文本）。这不合理：生成第二张图时应该能参考第一张（例如"把上一张图改成夜景"）。讲义给出的 mask 定义同样漏了"图像看前面的图像"这一项。
3. **一行修正**（Transfusion 的定义：整体因果，再在每张图内部打开双向）：

   ```python
   mask[i][j] = 1 if (j <= i or same_img(i, j)) else 0
   ```

   标签作为普通 token 参与因果注意力即可；若希望 `<image>` 也能看全图，可把它并入图像范围。这样在练习 2 的序列上，第 2 行变为 `1 1 1 . . . . . .`，第 7 行变为 `1 1 1 1 1 1 1 1 .`，patch 行变为 `1 1 1 1 1 1 1 . .`。

### Q10 — 参考答案

1. **不是学习**。`text_scale`、`img_scale` 每步固定 +1，与 loss 无关，没有梯度、没有模型参数。文本"概率"被硬编码为 `0.3 + 0.05·s`，所以 `text_loss = −ln(0.3 + 0.05·s)` 必然下降；图像预测速度 = 真速度 × `(0.8 + 0.02·s)`，`img_loss = (0.2 − 0.02·s)² · mean((ε − x0)²)`，在 s = 10 时为 0。
2. 已实际运行 `steps=22`：step 14 时概率 = 1.0，loss = 0；之后概率 > 1，**text_loss 变负**：step 16 为 `−ln(1.1) = −0.095`，step 20 为 −0.262。`cross_entropy_toy` 只做了 `max(prob, 1e-6)` 的下界保护，没有上界。img_loss 在 step 10 降到 0.000 之后反弹（0.007 → 0.030 → … → 0.161）。
3. `xt` 和 `t` **算出来但从未使用**——"模型"根本不看带噪输入；`predicted_vel` 直接用真实噪声 `n` 和干净图像 `x` 算出，等于把答案交给了模型，只是乘一个缩放系数。
4. 真实的一步应包含：
   - 构造交错序列（文本 token embedding + 图像 patch 线性投影 + 时间步 t 的 embedding）；
   - 对每张图采样 `t` 与 `ε`，把 patch 替换为 `x_t`；
   - 用混合 mask 跑**一次**Transformer 前向；
   - 文本位置接 LM head 算交叉熵，图像位置接回归头算 `MSE(v_θ, ε − x0)`；
   - `loss = text_w · L_text + img_w · L_img`，一次 `backward()`，优化器更新共享权重。

### Q11 — 参考答案

1. 共享：每 block `4d² + 8d² = 12d²`；`12 × 4096² × 32 ≈ 6.44B`（已计算）。
2. MMDiT：QKV、O 和 MLP 都按模态复制 → 每 block `24d²`，合计约 12.9B，**block 参数约翻倍**（norm/adaLN 参数很少，可忽略）。每个 token 只经过自己模态那一套权重，所以**每 token 前向 FLOPs 基本不变**，变的是参数量、显存和优化器状态。
3. 判断依据：
   - 收益：文本与图像的统计特性差异很大，各自一套投影能减少"模态打架"，SD3 实验中这种设计有效；
   - 代价：在固定 7B 预算下，翻倍等于把每个模态的有效容量砍一半，或总参数翻倍、显存/通信成本上升；
   - 经验上：生成为主（图像质量第一）的模型倾向 MMDiT；希望文本能力强、参数利用率高的统一模型倾向完全共享。outputs 技能文件也要求"按参数量给出经验规则"。也有折中：只复制 MLP（类似模态专家 MoE），注意力共享。

### Q12 — 参考答案

已用 Python 实际模拟（6 个随机初始噪声）：

| 步数 | 结果 |
|------|------|
| 1 | `[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]` |
| 2 | `[0.736, −0.885, −0.591, 0.354, −0.768, −0.072]` |
| 4 | `[1.0, −1.0, −1.0, 0.999, −1.0, −0.659]` |
| 10 | 全部落在 ±1.0 |

1. **1 步全部落在 0**：t = 1 时 `m = tanh(0) = 0`，`v = x`，于是 `x − 1·x = 0`。一步 Euler 等于直接输出 `E[x0 | x_1]`，即数据均值——这正是少步扩散"糊图"的一维版本：均值不是任何一个真实样本。
2. **单点数据一步精确**：此时 `m ≡ 1`，`v = (x − 1)/t`，`t = 1` 时 `x − (x − 1) = 1`。因为每条路径都是从 `ε` 指向 `x0` 的直线，速度沿路径恒定，Euler 一步就没有误差。
3. **直线 → 少步**：flow matching 让单个样本的路径是直线，但多个样本的"边缘速度场"是平均出来的，会弯曲（上例在 t≈0.5 附近才分叉到 ±1）。路径越直，Euler 离散误差越小；rectified flow 通过 reflow 等方法进一步把路径拉直，所以讲义说它"converges in fewer inference steps than DDPM"（DDPM 的随机反向过程轨迹弯曲，通常需要更多步）。

### Q13 — 参考回答要点

- **根本区别**：图像表示是离散还是连续。
  - Chameleon/Emu3：VQ tokenizer 把图像变成离散 token，整条序列一个 NTP 损失；
  - Transfusion：图像保持连续 patch，文本用 NTP、图像用扩散/flow matching，两损失共享主干。
- **离散路线**：优点是架构极简（就是 LLM）、一个采样循环、易于复用 LLM 基础设施；缺点是质量受 tokenizer 上限约束、逐 token 生成很慢。
- **Transfusion 路线**：优点是无量化损失（讲义：7B 时 FID 领先 3–5 点）、patch 可并行去噪；缺点是两个损失需要调权重、推理两条循环、训练动态更复杂。
- 加分点：MMDiT 是生成侧的近亲；Show-o 则是"离散 + 并行（掩码扩散）"的折中。

### Q14 — 参考回答要点

- **四块**：
  1. 文本→文本：因果（teacher forcing）；
  2. 图像→同一张图：双向（整张图同时去噪）；
  3. 图像→前文：可见（以文本为条件）；
  4. 后文→图像：可见（看完整张图再写描述/继续对话）。
- **多图**：最简实现是"整条序列因果 + 每张图内部双向"，即 `j <= i or same_img(i, j)`；第二张图能看第一张图（但第一张图看不到第二张）。
- **边界细节**：`<image>`/`</image>` 当作普通 token 参与因果注意力，绝不能出现整行全 0（否则 softmax NaN，见 Q9）；mask 是逐样本构造的，outputs 技能文件："Each sample has a different image span and needs its own block-triangular mask"。
- 加分点：工程上常用 FlexAttention / 自定义 block mask kernel 高效实现；本节代码的 `build_mask` 恰好有标签行全 0 与多图不可见两个错误。

### Q15 — 参考回答要点

- **训练**：采样 `t ~ U(0,1)`、`ε ~ N(0, I)`，构造 `x_t = (1 − t)x0 + tε`，回归速度 `v_θ(x_t, t) ≈ ε − x0`，MSE 损失。
- **采样**：从 `x_1 = ε` 出发，解 ODE `dx/dt = v_θ`，Euler：`x_{t−Δ} = x_t − Δ·v_θ(x_t, t)`，10–30 步。
- **与 DDPM 关系**：DDPM 用方差保持的噪声日程，网络预测 ε；ε、x0、v 三种参数化在给定日程下可以互相换算（都是 `x_t` 与某个目标的线性组合）。flow matching 用线性插值路径，数学更简单、ODE 采样更直接。
- **为什么少步**：单样本路径是直线，边缘速度场相对平滑；rectified flow 进一步拉直路径（Q12 的数值例子）。
- 常见误区：把 "velocity prediction" 和 "ε prediction" 当成完全不同的模型——它们只是同一类扩散模型的不同参数化。

### Q16 — 参考回答要点

- **起点**：损失按各自 token 求平均后，量级差 10 倍 → `img_w ≈ 0.1`（技能文件引用的默认值）。
- **考虑 token 占比**：如果损失是"所有 token 求和再除以总 token 数"，那么 7:3 的占比也会影响有效权重，需要明确"平均口径"。
- **按梯度范数校准**：分别计算两个损失对共享参数的梯度范数，调整权重使比例落在目标范围（技能文件的硬性要求："Balancing losses by fixed weight without measuring gradient-norm ratio" 是拒绝项）。也可以用 GradNorm、不确定性加权等自适应方法。
- **"图像 loss 降、文本退化"**：
  - 降低 `img_w` 或提高纯文本数据的比例；
  - 检查学习率/warmup 是否对两者都合适；
  - 定期跑文本基准（困惑度、下游任务）作为早停信号；
  - 考虑 MMDiT 式模态专属权重或模态专家，减少干扰。
- 加分点：讲义提醒 "Schedule mismatch between NTP and diffusion can cause one head to dominate"——监控两个损失各自的曲线，而不是只看总损失。

### Q17 — 参考回答要点

- **模态切分**：文本离散走 NTP；音频可以走连续 mel/latent + flow matching（Transfusion 式），也可以走离散 codec token（Emu3/MIO 式）。技能文件："text always discrete; images, audio, video can go either way"。
- **mask**：文本因果；一段音频 latent 内部可双向（整段同时去噪），但若要流式输出音频，则要改成按 chunk 因果（chunk 内双向、chunk 间因果）。
- **推理**：文本自回归 → 遇到 `<audio>` → 对该段 latent 去噪 10–30 步 → `</audio>` 后继续文本；开 CFG 时去噪步翻倍。
- **何时放弃两损失**：
  - 只需要理解（音频进、文本出）→ 用 LLaVA 式 late fusion；
  - 模型 < 1B → 技能文件说扩散头会欠拟合，改用离散 token；
  - 负担不起双推理循环、或需要严格低延迟流式 → 离散 token + 流式解码（下一节以后的 MIO 方向）。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 11 Chameleon：仅用 Token 的早期融合 Multimodal Models](../../11-chameleon-early-fusion-tokens/docs/zh.md)：本节反驳的"全离散"路线。
- [阶段 12 · 12 Emu3：通过下一 Token 预测生成图像与视频](../../12-emu3-next-token-for-generation/docs/zh.md)：离散路线的最强代表与 CFG。
- [阶段 08 · 06 Diffusion Models — 从头开始的 DDPM](../../../08-generative-ai/06-diffusion-ddpm-from-scratch/docs/zh.md)：ε 预测与加噪日程。
- [阶段 08 · 13 Flow Matching 与 Rectified Flows](../../../08-generative-ai/13-flow-matching-rectified-flows/docs/zh.md)：本节使用的训练目标。
- [阶段 04 · 23 Diffusion Transformers 与 Rectified Flow](../../../04-computer-vision/23-diffusion-transformers-rectified-flow/docs/zh.md)：DiT 与 MMDiT 的背景。

### 本节被哪些后续内容用到
- [阶段 12 · 14 Show-o 与离散扩散统一模型](../../14-show-o-discrete-diffusion-unified/docs/zh.md)：把连续扩散换成离散掩码扩散，单损失单循环。
- [阶段 12 · 15 Janus-Pro：用于统一 Multimodal Models 的解耦 Encoders](../../15-janus-pro-decoupled-encoders/docs/zh.md)：理解与生成使用不同的视觉编码器。
- [阶段 12 · 16 MIO 与任意模态互转的 Streaming Multimodal Models](../../16-mio-any-to-any-streaming/docs/zh.md)：把统一生成推广到语音、音乐与视频。
- [阶段 12 · 20 全模态模型：Qwen2.5-Omni 与 Thinker-Talker 分工](../../20-omni-models-thinker-talker/docs/zh.md)：另一种多模态输出架构。

### 延伸关键词
`Transfusion` · `MMDiT` · `flow matching` · `rectified flow` · `v-prediction` · `block-causal mask` · `FlexAttention` · `loss weighting / GradNorm` · `VAE latent patch` · `DiT` · `MonoFormer` · `CFG`
