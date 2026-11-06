# 测验 · 视觉与语言联合 Pretraining（Vision-Language Pretraining）

> **阶段 19 · 综合项目 · 第 62 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两种能力、两个目标 | "排序"（给 caption 找图）靠对比损失 InfoNCE；"生成"（给图写 caption）靠语言建模（LM）损失；只训一个只能得到半个系统 |
| 2 | InfoNCE | 图像、文本 embedding 各自 L2 归一化，`S = I·Tᵀ × scale`（N×N），对角线是正样本、其余 `N² − N` 个是负样本，对行和列各做一次交叉熵再取平均 |
| 3 | 温度 τ 与 logit scale | `scale = 1/τ`；τ 太小 → softmax 过尖、梯度只来自最难的负样本；τ 太大 → 分布过平、梯度消失。CLIP 把它当作可学习参数，初始 τ = 0.07（scale ≈ 14.29），上限 scale = 100 |
| 4 | LM 损失 | decoder 通过 cross-attention 读图像 memory，预测下一个 token；输入 `ids[:, :-1]`、目标 `ids[:, 1:]`，padding 用 `ignore_index` 排除 |
| 5 | 组合目标 | `total = contrastive + lm_weight × lm`，CoCa / BLIP / SigLIP 系都用多任务配方，权重各不相同 |
| 6 | 梯度流向 | 本节代码中：vision encoder 同时收到两种损失的梯度；projector 与 text encoder **只**收到 InfoNCE 的梯度；decoder **只**收到 LM 的梯度 |
| 7 | 初始 loss 健全性检查 | 均匀随机时 InfoNCE ≈ `ln N`（N=16 时 2.77），LM ≈ `ln V`（V=512 时 6.24）；本次实测初始为 3.05 与 6.50，略高于均匀基线 |
| 8 | 模型谱系 | CLIP：只有对比；CoCa：对比 + captioning（本节的结构）；BLIP/BLIP-2：再加 image-text matching 头；SigLIP：把 softmax InfoNCE 换成逐对 sigmoid 损失 |
| 9 | 模拟语料 | 200 对确定性生成的 (图像, caption)；图像只按 `i % 7` 有 7 档亮度，caption 是**公差为 3 的等差数列**——这决定了 loss 下降的真正来源 |
| 10 | Demo 的意义 | 50 步只用于确认"梯度管线端到端接通、加 LM 不会破坏对比目标"，不是在学真实的视觉-语言对齐 |

### 核心技能（能动手做到）

- [ ] 写出双向 InfoNCE：归一化 → 相似度矩阵 × scale → 行/列两次 `cross_entropy(·, arange(N))` → 平均
- [ ] 给定 2×2 的小 embedding 与 scale，手算 InfoNCE 两个方向的 loss，并解释为什么两个方向的值可以不同
- [ ] 正确理解 `log_tau` 实际是 `log(1/τ)`，能说出训练中打印的 `tau 14.286 → 14.060` 意味着温度在**升高**
- [ ] 用"冻结一部分输入"或"打乱图像"的消融实验判断 LM 损失的下降到底来自图像还是来自文本自身规律
- [ ] 把 InfoNCE 换成 SigLIP 的 sigmoid 逐对损失，并说出它为什么更适合超大 batch
- [ ] 画出本节模型每个模块分别接收哪种损失的梯度，并指出讲义表格中与代码不一致的地方

---

## 二、基础自测（选择题）

**Q1.** batch size N = 16 的 InfoNCE 中，相似度矩阵里正样本对和负样本对分别有多少个？

- A. 16 个正样本、16 个负样本
- B. 16 个正样本、240 个负样本
- C. 1 个正样本、15 个负样本
- D. 256 个正样本、0 个负样本

**Q2.** `PretrainConfig.init_log_tau = math.log(1.0 / 0.07)`，训练日志第一行打印 `tau 14.286`。下列解释正确的是：

- A. 温度 τ = 14.286，softmax 非常平坦
- B. 这是相似度矩阵对角线的平均值
- C. 这是 InfoNCE 的初始 loss
- D. 这是 `exp(log_tau) = 1/0.07` 即 logit scale（逆温度），真正的温度 τ = 0.07；代码把它乘到相似度上，变量名与打印标签都叫 tau 但含义相反

**Q3.** 在本节 `MultimodalModel` 中，**只对 LM 损失**反向传播时，哪些模块会收到非零梯度？

- A. vision encoder 和 cross-attention decoder
- B. vision encoder、projector 和 decoder
- C. 只有 decoder
- D. 全部模块，包括 text encoder 和 `log_tau`

**Q4.** 已归一化的图像 embedding `I = [[1, 0], [0, 1]]`、文本 embedding `T = [[0.6, 0.8], [0, 1]]`，scale = 10。按本节 `info_nce_loss` 计算，总 loss 约为：

- A. 0.065
- B. 1.063
- C. 0.564
- D. 2.773

**Q5.** 关于 InfoNCE 的温度，下列说法正确的是：

- A. 温度越小越好，因为可以让正样本概率接近 1
- B. 温度只影响推理时的检索排序，不影响训练梯度
- C. 温度太小时 softmax 过尖，梯度几乎只来自最难的那个负样本，训练噪声大；太大时分布过平，梯度变弱
- D. 温度必须固定为 0.07，否则 loss 不收敛

**Q6.** `lm_loss` 中 `F.cross_entropy(flat_logits, flat_target, ignore_index=padding_id)` 的作用是：

- A. 目标为 `PAD_ID = 0` 的位置不计入 loss，平均时分母也只算非 padding 位置
- B. 把 padding 位置的 logits 置为 0
- C. 跳过所有输入中含 0 的样本
- D. 把 padding 位置的 loss 乘以 0.5

**Q7.** `MultimodalModel.forward` 中 `inputs = text_ids[:, :-1]`、`targets = text_ids[:, 1:]`。对于一条长度为 6、后面补 10 个 0 的 caption（`max_text_len = 16`），下列说法正确的是：

- A. 每个 caption token 都会被预测一次
- B. padding 位置既不作为输入也不作为目标
- C. 最后一个真实 token 永远不会被预测
- D. 第一个 token `ids[:, 0]` 永远不会被预测（没有 BOS），实际参与 loss 的目标只有 5 个

**Q8.** 下列哪个模型的训练目标与本节代码的结构"对比损失 + 图像条件下的 captioning LM 损失，在同一个模型里"最接近？

- A. CLIP
- B. CoCa
- C. SigLIP
- D. GPT-2

---

## 三、动手 / 代码题

**Q9.** 运行结果：LM loss 从 6.5010 降到 4.7041。讲义说这证明"gradient is wired correctly"。阅读 `make_mock_corpus` 的 caption 生成部分：

```python
        length = min(6 + (i % 8), max_len)
        ids = np.zeros((max_len,), dtype=np.int64)
        base = (i * 17) % (vocab_size - 50)
        for j in range(length):
            ids[j] = 1 + (base + j * 3 + (i % 5)) % (vocab_size - 1)
```

1. 写出第 0 条和第 1 条 caption 的前几个 token，指出它们有什么共同规律。
2. LM 下降的主要来源是"看图"还是"文本规律"？设计两个消融实验来验证。
3. 讲义英文版说 mock corpus 是 "random caption ids"，练习 4 又说换成"依赖图像的 Markov 链"后 loss 会降得更多"because there is actual learnable signal"。这两句话与代码是否一致？

**Q10.** 关于温度参数：

```python
    scale = log_tau.exp().clamp(min=1e-3, max=100.0)
    sim = (img_n @ txt_n.T) * scale
```

讲义公式写的是 `S = I Tᵀ / tau`。

1. 代码中的 `log_tau` 实际是谁的对数？讲义公式里的 τ 与代码打印的 "tau" 是什么关系？
2. 训练中打印的 "tau" 从 14.286 降到 14.060，真实温度是升高还是降低了？
3. `clamp(max=100.0)` 一旦生效，`log_tau` 的梯度会怎样？CLIP 为什么也要设这个上限？

**Q11.** 完成讲义练习 1：写一个 SigLIP 风格的 `siglip_loss(image_emb, text_emb, log_t, bias)`，对 N×N 每一对独立做二分类（对角线为正、其余为负）。然后回答：在 `torch.eye(4, 8)` 这种"完美对角"输入上、取 `t = 10, b = −10`（SigLIP 论文的初始化）时，loss 是多少？为什么不是 0？

**Q12.** 讲义"Combining the losses"一节的表格写着 LM 损失影响 "Encoder + projection + decoder"，正文也说 "The two losses share gradients into the encoder and projection"。

1. 阅读 `forward`：decoder 拿到的 `memory` 是 projector 之前还是之后的张量？
2. 用什么最小实验能验证 projector 是否收到 LM 梯度？给出代码思路和你预期的结果。
3. 如果希望 projector 真正被两种损失共享，可以怎么改？代价是什么？

---

## 四、面试高频题

**Q13.**（基础必考）请解释 CLIP 的 InfoNCE 损失：输入是什么、相似度矩阵怎么构造、标签是什么、为什么要做"双向"？

**Q14.**（原理深挖）为什么对比学习强烈依赖大 batch？温度为什么要可学习？SigLIP 把 softmax 换成 sigmoid 解决了什么问题？

**Q15.**（原理深挖）CLIP、CoCa、BLIP（BLIP-2）、LLaVA 在预训练目标上分别有什么区别？为什么要把对比损失和 captioning 损失放在一个模型里？

**Q16.**（工程实践）在 64 张 GPU 上训练 CLIP 式对比模型，全局 batch 32K。负样本从哪里来？显存和通信的瓶颈在哪？有哪些常见技巧？

**Q17.**（追问型）你的多任务预训练跑完后，captioning loss 降了很多。面试官追问："你怎么证明模型是真的'看了图'才写出 caption，而不是只学会了语言先验？" 你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：B

N×N = 256 个元素，对角线 16 个是匹配的正样本，其余 `N² − N = 240` 个是负样本（讲义 "the `N^2 - N` mismatched pairs as negatives"）。A 低估了负样本数；C 是**单行**视角（每个图像 1 个正样本、15 个负样本），不是整个矩阵；D 把所有对都当成正样本。

### Q2 — 答案：D

`exp(log(1/0.07)) = 14.286`。代码中 `sim = cos × exp(log_tau)`，乘的是 `1/τ`，所以 `log_tau` 实际是 **log(1/τ)**，打印的 "tau" 是 logit scale（逆温度）。真正的温度是 0.07。A 把逆温度当成温度，方向完全反了；B 的对角均值在日志里是 `diag`；C 初始 loss 是 3.0456。

### Q3 — 答案：A

我们实测"只对 LM 反传"：encoder 29 个参数张量有梯度（范数约 0.53），decoder 45 个参数张量有梯度（约 1.20），而 projector、text encoder、`log_tau` 的 `grad` 都是 `None`。原因：decoder 的 `memory` 是 ViT 输出的全部 token（projector 之前），所以 LM 梯度经 cross-attention 回到 encoder 但不经过 projector。B 是讲义表格的说法，与代码不符（见 Q12）；C 漏了 encoder；D 中 text encoder 和 `log_tau` 只出现在 InfoNCE 里。

### Q4 — 答案：C

`sim = I·Tᵀ × 10 = [[6, 0], [8, 10]]`。

- 图→文（行）：第 0 行 `ln(e⁶ + e⁰) − 6 ≈ 0.0025`；第 1 行 `ln(e⁸ + e¹⁰) − 10 ≈ 0.1269`；平均 **0.0647**。
- 文→图（列，即 `sim.T`）：第 0 行 `[6, 8]` 目标 0：`ln(e⁶ + e⁸) − 6 ≈ 2.1269`；第 1 行 `[0, 10]` 目标 1：≈ 0.00005；平均 **1.0635**。
- 总 loss = (0.0647 + 1.0635)/2 ≈ **0.564**（已用代码实际计算）。

A 只是图→文方向；B 只是文→图方向；D 是 `ln 16`，与此题无关。这个例子说明**两个方向可以差很多**：文本 0 与图像 1 的相似度（0.8）高于与图像 0（0.6），所以"文本 0 找图"会找错，而"图像 0 找文本"仍然对。

### Q5 — 答案：C

讲义 "Temperature matters"：τ 太小（如 0.01）时梯度只来自最难的负样本，训练噪声大；τ 太大时 softmax 变平、梯度消失。我们算了一个例子：正样本分数 0.9、负样本 0.85/0.5/0.1，scale = 1 时概率 `[0.326, 0.31, 0.218, 0.146]`（太平）；scale = 14.3 时 `[0.67, 0.328, 0.002, 0.0]`（几乎只剩最难负样本 0.85 在竞争）；scale = 100 时 `[0.993, 0.007, 0, 0]`。A 忽略了过尖的问题；B 错，温度直接决定梯度大小；D 错，0.07 只是 CLIP 的初始值，可学习。

### Q6 — 答案：A

`ignore_index` 使这些位置既不贡献 loss，也不计入平均的分母。测试 `test_pad_positions_excluded` 验证了"含两个 PAD 目标的 4 位置 loss"等于"只取前 2 个位置的 loss"。B、D 都不是 `ignore_index` 的行为；C 错，它看的是**目标**而不是输入，且按位置而不是按样本。注意：padding 仍然会作为**输入**送进 decoder（`inputs` 里含 0），只是对应的目标被忽略。

### Q7 — 答案：D

长度 6 的 caption：`inputs` 是位置 0–14，`targets` 是位置 1–15。真实 token 位于 0–5，于是被预测的真实目标是位置 1–5，共 5 个；位置 0 没有前文可依（没有 BOS token），永远不会被预测。A 错，第一个 token 没被预测；B 错，padding 会作为输入（只是目标被忽略）；C 错，最后一个真实 token（位置 5）会被位置 4 预测，只是"预测它之后的 token"那一步的目标是 PAD、被忽略。生产中会在开头加 `<bos>`，让第一个词也以图像为条件被预测——对 captioning 来说第一个词恰恰最依赖图像。

### Q8 — 答案：B

讲义 "Use It"："CoCa (2022). Image-text contrastive plus image-captioning LM loss in one model. The exact pattern this lesson builds." A（CLIP）只有对比损失；C（SigLIP）只是把 InfoNCE 换成 sigmoid 逐对损失，本身不做 captioning；D（GPT-2）是纯文本 LM。

### Q9 — 参考答案

1. 实际运行 `make_mock_corpus(1, 200, 512, 16)`：第 0 条是 `[1, 4, 7, 10, 13, 16, 0, ...]`，第 1 条是 `[19, 22, 25, 28, 31, 34, 37, 0, ...]`。规律：**每条 caption 都是公差为 3 的等差数列**（`np.diff` 全为 3）。只要看到前一个 token x，就能以接近 100% 的把握预测下一个是 x + 3（取模），与图像无关。
2. 主要来源是**文本规律**。我们做了两个消融：
   - **训练时把所有图像置零**：50 步后 LM loss 最后 10 步均值 5.016，与正常训练的 5.004 几乎相同；
   - **训练后打乱 batch 内图像与 caption 的对应**：评估 LM loss 由 4.689 变为 4.697，置零 memory 为 4.748，差异极小。
   - 再把正常训练延长到 300 步，LM loss 降到约 0.148——模型已经学会了"+3"规则。
   结论：LM loss 的下降证明了"decoder 的梯度管线是通的"，但**不能**证明 cross-attention 学到了图像条件。
3. 不一致。caption 并不是 "random"，而是高度可预测的等差数列；它与图像的关联也很弱（图像只有 `i % 7` 决定的 7 档亮度，caption 由 `i * 17` 和 `i % 5` 决定）。练习 4 的"依赖图像的 Markov 链"才会让 LM 必须看图；但说"loss 会降得更多"不一定成立——现在的等差数列本身已经几乎可以被完美预测。

### Q10 — 参考答案

1. `scale = exp(log_tau)` 乘在 cos 相似度上，等价于除以 `τ = 1/scale`。所以 `log_tau = log(1/τ) = −log τ`。讲义公式的 τ 是**温度**（0.07），代码打印的 "tau" 是 **1/τ**（14.286）。变量名应该叫 `logit_scale`（CLIP 官方实现就叫 `logit_scale`）。
2. scale 从 14.286 降到 14.060，意味着 τ 从 0.0700 升到约 0.0711——**温度在升高**，softmax 在变平。50 步内变化很小，说明 `log_tau` 的学习率与其他参数相同（5e-4）时它移动得很慢。
3. `clamp` 在超出区间时对输入的梯度为 0：scale 一旦超过 100，`log_tau` 就收不到梯度、停在边界。CLIP 设上限 100 是为了防止温度被学得过小导致训练不稳定（logits 过大，softmax 饱和）。下限 `1e-3` 防止 scale 过小使所有相似度都被压成 0。

### Q11 — 参考答案

```python
def siglip_loss(image_emb, text_emb, log_t, bias):
    img = F.normalize(image_emb, dim=-1)
    txt = F.normalize(text_emb, dim=-1)
    logits = img @ txt.T * log_t.exp() + bias          # (N, N)
    labels = 2 * torch.eye(len(img)) - 1               # 对角 +1，其余 −1
    return -F.logsigmoid(labels * logits).sum() / len(img)
```

实测：`siglip_loss(eye(4,8), eye(4,8), log(10), −10)` ≈ **0.693**（= 4 × ln 2 / 4）。原因：完美对角时正样本 cos = 1、负样本 cos = 0；正样本 logit = `10 × 1 − 10 = 0`，`−log σ(0) = ln 2`；负样本 logit = `−10`，`−log σ(10) ≈ 4.5e-5`。所以 loss 主要来自 4 个正样本，各贡献 ln 2。

这正是 SigLIP 初始化的用意：负样本远多于正样本（N² − N vs N），bias 初始化为 −10 让模型一开始就预测"大多数对都不匹配"，避免初期被海量负样本的梯度淹没；训练中 t 和 b 都会学习，使正样本 logit 变成正数。与 InfoNCE 不同，sigmoid 损失**每一对独立计算**，不需要对整行做 softmax 归一化。

### Q12 — 参考答案

1. `memory, image_emb = self.encode_image(images)`，其中 `encode_image` 返回 `(tokens, self.projector(cls))`。`memory` 是 ViT 的全部原始 token（`(B, 5, 128)`，projector **之前**），只有 CLS 经过 projector 用于对比损失。所以 decoder 的 `DecoderConfig.vision_dim = cfg.vision_hidden`。
2. 实验：构建模型，取一个 batch，只对 `lm` 调用 `backward()`，检查 `model.projector` 所有参数的 `.grad`。我们实测为 `None`（projector 0 个参数有梯度），而 encoder 和 decoder 有梯度；反过来只对 `contrast` 反传，decoder 无梯度。因此讲义表格中 "LM → projection" 一项与代码不符；"InfoNCE → text head" 一项对应的是 `TextSideEncoder`（它只有一个 embedding 表）。
3. 改法：让 projector 作用于全部 token（`self.projector(tokens)`，形状 `(B, 5, embed_dim)`），把投影后的 token 作为 decoder memory（`vision_dim = embed_dim`），CLS 位置的投影结果同时作为对比用的图像 embedding。这就是 LLaVA 式"投影后的视觉 token 进 LM"的做法。代价：两个目标争夺同一个投影空间——对比损失希望全局向量可分、LM 希望 token 级信息丰富，可能互相干扰；需要调 `lm_weight` 或给两者各留一个投影头（CoCa 就为对比和生成使用不同的池化/投影）。

### Q13 — 参考回答要点

- **输入**：一个 batch 的 N 对 (图像, 文本)，经各自 encoder 得到 `(N, D)` 的图像与文本 embedding。
- **相似度矩阵**：两者各自 L2 归一化，`S = I·Tᵀ / τ`，形状 `(N, N)`，`S[i, j]` 是第 i 张图与第 j 段文本的缩放余弦相似度。
- **标签**：`arange(N)`——第 i 行的正确类别是第 i 列，即"对角线是正样本"。本质上是一个 N 分类问题，其余 N − 1 个样本当作负样本。
- **双向**：对行做交叉熵（图→文检索）、对列做交叉熵（文→图检索），取平均。两个方向的 softmax 归一化对象不同，loss 可以不同（见 Q4），只做一个方向会让另一个方向的检索能力变弱。
- **初始健全性检查**：随机初始化时 loss 应接近 `ln N`。
- 加分点：InfoNCE 是互信息的下界，batch 越大界越紧；"In-batch negatives"不需要额外采样负样本。

### Q14 — 参考回答要点

- **大 batch**：负样本全部来自 batch 内，N 越大负样本越多、越可能包含"难负样本"，对比任务越难、学到的表示越细；同时 InfoNCE 的互信息下界上限是 `ln N`。CLIP 用 32K batch。
- **温度可学习**：合适的 τ 与数据难度、batch 大小、训练阶段都有关，人工调很难；把 `log(1/τ)` 设为参数让模型自己找。需要上限（CLIP 为 100）防止发散。
- **SigLIP**：
  - softmax 需要整行归一化，分布式训练时每张卡都要拿到全局的相似度行，需要 all-gather 全部 embedding 并计算 `N × N` 矩阵；
  - sigmoid 损失每一对独立，可以分块计算，显存与通信更友好，batch 可以做得更大，小 batch 下表现也更好；
  - 需要 bias 项（初始 −10）处理正负样本极度不平衡（见 Q11）。
- 常见误区：以为"温度越小越好"——过小会使训练对少数难负样本（可能是假负样本，即实际匹配但未配对的数据）过度敏感。

### Q15 — 参考回答要点

| 模型 | 目标 | 能力 |
|------|------|------|
| CLIP | 只有 InfoNCE | 检索、零样本分类强；不能直接生成 caption |
| CoCa | InfoNCE + captioning LM（同一模型） | 检索与生成兼得，本节结构 |
| BLIP | ITC（对比）+ ITM（图文匹配二分类头）+ LM | 三个损失；ITM 用难负样本 |
| BLIP-2 | 冻结图像 encoder 与 LLM，用 Q-Former 训练 ITC/ITM/ITG 再接 LLM | 训练代价低 |
| LLaVA | 第一阶段只训投影层对齐，第二阶段解冻 LLM 做视觉指令微调（LM 损失） | 对话式多模态 |

- **为什么合在一起**：对比损失学"全局语义对齐"，适合检索；LM 损失学"细粒度、按 token 的 grounding"，适合生成。两者共享视觉 encoder，可以互相提供监督信号，一次预训练得到两种能力（讲义："Multi-objective pretraining gets both in one pass"）。
- 加分点：多任务需要调权重，讲义练习 5 让你比较 `lm_weight = 0` 与 `1` 时的对比损失——我们实测 50 步后对比 loss 分别是 2.3603 与 2.3622，说明在此 demo 中 LM 损失没有拖累排序目标。

### Q16 — 参考回答要点

- **负样本来源**：每张卡算出本地 512 个样本的 embedding，通过 **all-gather** 拿到全局 32K 个 embedding，用本地样本对全局样本计算 `512 × 32K` 的相似度行，这样每个样本都有 32K − 1 个负样本。梯度只回传到本地 embedding（或用支持梯度的 all-gather）。
- **瓶颈**：
  - 显存：`N × N` 相似度矩阵（32K × 32K 的 FP32 约 4GB）；
  - 通信：每步 all-gather 全部 embedding；
  - softmax 需要整行，无法简单分块。
- **技巧**：
  - 只计算本地行（每卡 `512 × 32K`）而不是全矩阵；
  - 混合精度、gradient checkpointing 降低 encoder 显存；
  - 换用 SigLIP 的 sigmoid 损失，分块计算并以环形方式交换文本 embedding；
  - 温度上限、warmup 防止早期发散；
  - 数据去重，减少"假负样本"（同一张图的不同 caption 被当作负样本）。
- 常见误区：只在单卡 batch 内做对比，有效负样本数被卡数稀释，效果大幅下降。

### Q17 — 参考回答要点

- **核心思路**：做"去掉图像信息"的消融，看 caption 质量是否明显下降。
- **具体做法**：
  1. **打乱配对**：评估时把 batch 内的图像随机打乱，计算 caption 的 LM loss / CIDEr；若与正确配对几乎相同，说明模型没在用图（本节 demo 实测：4.689 vs 4.697，几乎没看图）；
  2. **置零/噪声 memory**：用全零或随机 memory 替换图像 token；
  3. **纯文本基线**：用同样的数据只训一个没有图像输入的 LM，对比 loss；
  4. **注意力可视化**：检查 cross-attention 权重是否落在与词相关的区域；
  5. **条件化测试集**：构造"同一个文本前缀、不同图像应得不同续写"的样本，测准确率。
- **数据层面**：确保数据中 caption 确实依赖图像（本节的等差数列 caption 完全不依赖图像，练习 4 就是为此设计的）。
- 加分点：多模态评估中这类"盲测基线"非常重要——很多 VQA 基准只用文本问题就能答对相当比例（下一节第 63 节会讨论评估方法）。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 59 Vision Transformer Encoder](../../59-vit-transformer/docs/zh.md)：本节直接 import 它的 `VisionEncoder`。
- [阶段 19 · 60 用于 Modality Alignment 的投影层](../../60-projection-layer-modality-align/docs/zh.md)：`MLPProjector` 来自这里，上一节用 cosine 对齐，本节换成 InfoNCE。
- [阶段 19 · 61 Cross-Attention 融合](../../61-cross-attention-fusion/docs/zh.md)：本节 LM 损失用的 `VisionLanguageDecoder`。
- [阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：next-token 交叉熵与训练循环。
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../../12-multimodal-ai/02-clip-contrastive-pretraining/docs/zh.md)：InfoNCE 与可学习温度的原始出处。

### 本节被哪些后续内容用到
- [阶段 19 · 63 多模态 Evaluation](../../63-multimodal-eval/docs/zh.md)：用 Recall@K、CIDEr 等评估本节训练出的检索与生成能力。
- [阶段 12 · 03 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former](../../../12-multimodal-ai/03-blip2-qformer-bridge/docs/zh.md)：ITC + ITM + ITG 三损失。
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../../12-multimodal-ai/05-llava-visual-instruction-tuning/docs/zh.md)：两阶段训练（对齐 → 指令微调）。
- [阶段 12 · 24 多模态 RAG 与跨模态检索](../../../12-multimodal-ai/24-multimodal-rag-cross-modal/docs/zh.md)：联合 embedding 空间在检索中的应用。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../65-hybrid-retrieval-bm25-dense/docs/zh.md)：稠密检索同样依赖对比训练出的 embedding。

### 延伸关键词
`InfoNCE` · `CLIP loss` · `logit scale / temperature` · `in-batch negatives` · `hard negative mining` · `SigLIP sigmoid loss` · `CoCa` · `ITC / ITM / ITG` · `multi-task loss weighting` · `all-gather negatives` · `blind baseline ablation`
