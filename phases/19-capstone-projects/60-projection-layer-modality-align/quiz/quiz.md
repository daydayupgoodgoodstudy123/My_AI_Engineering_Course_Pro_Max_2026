# 测验 · 用于 Modality Alignment 的投影层（Projection Layer for Modality Alignment）

> **阶段 19 · 综合项目 · 第 60 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 模态对齐问题 | 视觉 encoder 输出的向量（768 维）与文本 embedding（512 维）处在各自训练出来的基底里，彼此没有对应关系，需要一个"桥" |
| 2 | 两层 MLP 投影 | `Linear(768, 1024) → GELU → Linear(1024, 512)`，参数 `768·1024 + 1024 + 1024·512 + 512 = 1,312,256`（讲义："about 1.3M"） |
| 3 | 先池化再投影 | 图像 197 个 token 要压成 1 个向量才能与 1 个 caption 向量比较；本节用 CLS pooling，讲义提到 SigLIP 用平均池化 |
| 4 | Mock 文本表 | `MockTextEmbedding`：固定随机的 `4096 × 512` 表（std `1/√512`），caption 向量 = 非 padding token 的 embedding 平均（id 0 是 padding） |
| 5 | 余弦对齐损失 | `1 − cos(image, text)`，范围 0（同向）到 2（反向）；随机向量在高维几乎正交，初始损失约 1 |
| 6 | 冻结两端 | 视觉 encoder 与文本表都 `requires_grad=False`，只训练投影层；这是 adapter 式 VLM 的"第一阶段"做法 |
| 7 | 训练配置 | 32 对合成样本循环使用，200 步，每步 batch = 1，Adam、lr 3e-4；本地实测损失 1.0684 → 0.7984，余弦 −0.068 → +0.202 |
| 8 | 演示中的 encoder | `train()` 里实际用的是 4 层、8 头、`mlp_ratio=2` 的 ViT（约 19.5M 参数），**随机初始化**，并非讲义所说的 86M 预训练模型 |
| 9 | 余弦损失的尺度不变性 | 损失先 `F.normalize` 再点积，投影输出整体放大任意倍损失不变；所以 L2 正则主要收缩"无用方向"（讲义练习 4） |
| 10 | per-pair vs 对比学习 | 本节逐对拉近；第 62 节的 InfoNCE 还要求"离自己的 caption 比离别人的更近"，能防止所有图像坍缩到同一个方向 |

### 核心技能（能动手做到）

- [ ] 写出两层 MLP 投影与余弦对齐损失，并手算投影层参数量
- [ ] 实现带 padding mask 的平均池化，并解释为什么 `clamp(min=1.0)` 能防止除零
- [ ] 正确冻结模块（`requires_grad_(False)` + `eval()` + `no_grad`），并验证只有投影层在更新
- [ ] 诊断"损失下降了但什么也没学到"：检查不同样本特征的相似度、单方向能达到的余弦上界、留出集表现
- [ ] 预先缓存冻结 encoder 的特征，用 mini-batch 训练投影层，并在全部样本上评估平均损失
- [ ] 把逐对余弦损失改成带温度的对比损失（InfoNCE），说明两者的差别

---

## 二、基础自测（选择题）

**Q1.** 本节默认配置下 `MLPProjector(768, 1024, 512)` 的参数量是：

- A. 1,310,720
- B. 1,312,256
- C. 2,097,152
- D. 786,432

**Q2.** 第 0 步的损失是 1.0684（余弦 −0.068）。这个"约等于 1"的初始值说明：

- A. 投影层初始化有 bug，输出与文本方向相反
- B. 损失函数写错了，应该接近 0
- C. 学习率太大，第一步就发散了
- D. 随机初始化的投影输出与文本向量在 512 维空间中几乎正交（余弦约 0），损失 `1 − cos ≈ 1` 是正常起点

**Q3.** 运行 `main.py` 时，真正被优化器更新的参数是：

- A. 只有投影层的 1,312,256 个参数；视觉 encoder（`train()` 中为 4 层、约 19.5M 参数、随机初始化）和文本表都被冻结
- B. 投影层 + 视觉 encoder 的最后一层
- C. 投影层 + 文本 embedding 表
- D. 讲义所说的 86M ViT-Base 全部参数

**Q4.** `MockTextEmbedding` 对 `ids = [[5, 7, 0, 0]]` 的输出是：

- A. 4 个 embedding 的平均（包括 id 0 的那一行两次）
- B. id 5 与 id 7 两行 embedding 之**和**
- C. id 5 与 id 7 两行 embedding 的**平均**：mask 掉 id 0，再除以非 padding 的个数 2
- D. 只取第一个 token（id 5）的 embedding

**Q5.** demo 打印 `initial loss 1.0684`、`final loss 0.7984`、`loss drop 0.2701`。关于这两个数字，最准确的说法是：

- A. 它们分别是第 0 步（第 0 对样本）和第 199 步（第 7 对样本）的**单样本**损失，比较的不是同一个样本，噪声很大
- B. 它们是全部 32 对样本的平均损失
- C. 它们是在留出集上的损失
- D. 它们是最后 25 步的滑动平均

**Q6.** 我们额外测量发现：32 张合成图像经冻结 encoder 得到的 CLS 向量两两余弦**最小也有 0.99997**；训练后投影层对 32 张图的输出两两余弦 ≥ 0.9999993，与"所有 caption 方向的平均"余弦达 0.998；在全部 32 对上的平均余弦为 0.1867，而"任何单一方向"能达到的上界是 0.1870。这说明：

- A. 投影层已经学会了逐对对齐，只是还需要更多步数
- B. 文本表冻结导致梯度无法传播
- C. 由于输入几乎完全相同，投影层只能把所有图像映射到"平均 caption 方向"，并没有学到任何逐对对应关系
- D. 余弦损失有 bug，最大只能到 0.19

**Q7.** 把投影层最后一层的权重和 bias 都乘以 10，余弦对齐损失会：

- A. 变为原来的 10 倍
- B. 变为原来的 1/10
- C. 变成 NaN
- D. 完全不变：损失在计算前对两边做了 `F.normalize`，只看方向不看长度

**Q8.** 下列关于业界 VLM 投影层的描述，正确的是：

- A. BLIP-2 在 Q-Former 之后用两层 GELU MLP 投影到 LLM 维度
- B. LLaVA-1.5 第一阶段冻结视觉 encoder 和 LLM，只训练两层 MLP 投影；第二阶段再解冻 LLM
- C. MiniGPT-4 用两层 MLP 投影，并在第一阶段就微调整个 LLM
- D. 最早的 LLaVA（2023 年 4 月）就使用两层 GELU MLP

---

## 三、动手 / 代码题

**Q9.** Q6 的现象需要你亲手复现：

1. 写一段代码，计算 32 张图像的 CLS 两两余弦，以及"所有归一化 caption 向量的平均向量"的范数（它就是单一方向能达到的平均余弦上界）。
2. 解释为什么 `make_pair` 生成的 32 张图像在随机初始化的 encoder 下几乎无法区分。
3. 如何设计合成数据，使"图像内容"与"caption"之间真的存在可学习的对应关系？

**Q10.** 改造 `train()`：

1. encoder 冻结、输入固定，却在 200 步里重复计算了 200 次前向。请改为**预先计算并缓存**全部 32 个 CLS 特征。
2. 改为 mini-batch（或 full-batch）训练，并在训练前后对**全部 32 对**计算平均损失，替代单样本的 `initial_loss` / `final_loss`。
3. 我们发现：对缓存的 CLS 特征先做标准化（减均值、除标准差）再 full-batch 训练，32 对训练样本的平均余弦能到 **1.0**。这说明投影层真的"学会了对齐"吗？还需要什么评估？

**Q11.** 讲义练习 2 与第 62 节都指向带温度的对比损失。请实现：

```python
def contrastive_loss(image_emb, text_emb, tau=0.07) -> torch.Tensor: ...
```

要求对称（image→text 与 text→image 两个方向的交叉熵取平均）。然后说明：为什么 Q6 中"所有图像坍缩到同一方向"的解在逐对余弦损失下是一个不错的局部解，而在对比损失下却很差？`tau` 太小或太大分别会怎样？

**Q12.** `test_loss_drops_over_steps` 没有调用被测的 `train()`，而是在 `_train_small` 里复制了一份训练循环。

1. 这样写有什么问题？
2. `train()` 为什么难以直接在小配置下测试？（提示：看 `encoder_cfg` 与 `make_pair` 的写法。）
3. 给出一种重构方案：让 `train()` 可以注入 encoder 与样本对，然后写出一个直接测试 `train()` 的单元测试。

---

## 四、面试高频题

**Q13.**（基础必考）什么是模态对齐（modality alignment）？在"视觉 encoder + 投影层 + LLM"的架构中，投影层起什么作用？为什么第一阶段通常只训练投影层？

**Q14.**（原理深挖）投影层用一层线性还是两层 MLP？各自的表达能力与风险是什么？讲义说"single linear projection can rotate and rescale but cannot fix the basis if the two spaces have curvature mismatches"，你怎么理解？

**Q15.**（原理深挖）逐对余弦损失与 CLIP/SigLIP 式的对比损失有什么区别？为什么前者容易出现"坍缩"？

**Q16.**（工程实践）你要为一个 7B LLM 接上视觉能力，预算有限。请描述两阶段训练的数据、冻结策略、监控指标，以及如何判断投影层"学到了东西"。

**Q17.**（追问型）本节 demo 损失从 1.07 降到 0.80，打印"ok: projector learned an alignment direction"。作为 reviewer，你会如何质疑这个结论？

---

## 五、参考答案与解析

### Q1 — 答案：B

`fc1`：`768 × 1024 + 1024 = 787,456`；`fc2`：`1024 × 512 + 512 = 524,800`；合计 1,312,256（demo 打印 `projector params : 1,312,256`）。A 漏了两层的 bias；C 是文本表 `4096 × 512` 的大小；D 只是 `fc1` 的权重。

### Q2 — 答案：D

512 维空间中两个随机方向的余弦近似服从均值 0、标准差约 `1/√512 ≈ 0.044` 的分布，所以初始余弦接近 0、损失接近 1。实测 −0.068，处在正常波动范围内。A 错，−0.068 并不是"相反"（相反时余弦接近 −1、损失接近 2）；B 错，只有完全对齐时才是 0；C 错，第 0 步的损失在更新之前就已计算。

### Q3 — 答案：A

`train()` 中：

```python
encoder_cfg = ViTConfig(image_size=224, patch_size=16, hidden=cfg.vision_hidden,
                        depth=4, heads=8, mlp_ratio=2.0)
encoder = VisionEncoder(encoder_cfg).eval()
freeze(encoder)
...
opt = torch.optim.Adam(projector.parameters(), lr=cfg.lr)
```

我们实例化后统计 encoder 参数为 19,501,056；它没有加载任何预训练权重。优化器只接收投影层参数。讲义写"The vision encoder has 86M parameters"，指的是第 59 节的默认 ViT-Base，与本节代码实际使用的不一致。B、C 与代码不符；D 是讲义的说法。

### Q4 — 答案：C

```python
embed = self.table(ids)                         # (1, 4, 512)
mask = (ids != 0).float().unsqueeze(-1)         # (1, 4, 1)：[1, 1, 0, 0]
denom = mask.sum(dim=1).clamp(min=1.0)          # (1, 1)：2
pooled = (embed * mask).sum(dim=1) / denom      # (1, 512)
```

padding 位置被乘以 0，分母只数非 padding 的 token。测试 `test_pooling_ignores_padding` 验证了 `[1,2,3,4]` 与 `[1,2,3,4,0,0]` 的输出相同。`clamp(min=1.0)` 防止全是 padding 时除以 0。注意 `nn.Embedding` 并没有设置 `padding_idx`，id 0 那一行也是随机向量——忽略它完全靠这里的 mask。

### Q5 — 答案：A

`initial_loss` 在 `step == 0` 记录，此时用的是 `pairs[0]`；`final_loss` 在 `step == 199` 记录，用的是 `pairs[199 % 32] = pairs[7]`。两者是不同样本的单次损失，`loss drop` 混合了"训练效果"和"样本差异"。训练日志也能看到明显的噪声（第 125 步 0.7592、第 150 步 0.9145）。更可靠的指标是全部 32 对的平均损失：我们统计前 32 步的平均损失为 1.005、最后 32 步为 0.832（见 Q10）。

### Q6 — 答案：C

当 32 个输入几乎相同时，任何确定性函数的 32 个输出也几乎相同——投影层只能输出一个方向 `u`。此时平均余弦 `= (1/32) Σ cos(u, t_i)`，在 `u` 取所有归一化 caption 向量的平均方向时达到最大值 `‖mean(t̂_i)‖`。32 个 caption 由随机 token 组成，彼此近似正交（实测平均 |cos| 0.036），平均向量的范数约 `1/√32 ≈ 0.18`（实测 0.1870）。训练后的投影层达到 0.1867，几乎正好是这个上界——**它学到的是"平均 caption 方向"，而不是逐对对齐**。A 错，多训练也无法超过上界；B 错，文本表冻结不影响投影层的梯度；D 错，余弦损失本身可以到 0，是数据让它到不了。

### Q7 — 答案：D

`cosine_alignment_loss` 先 `F.normalize(image_emb, dim=-1)`，把每个向量除以自身 L2 范数，再与归一化的文本向量做点积。输出整体乘以正数不改变方向，损失不变。这正是讲义练习 4 所说的"cosine is scale-invariant, so the penalty mostly shrinks unused directions"：L2 正则不会被损失"抵抗"，它可以随意缩小权重而不影响损失，直到数值精度或梯度方向受到影响。注意 `fc2` 的 bias 也必须一起放大，否则方向会改变。

### Q8 — 答案：B

- B 正确：LLaVA-1.5 使用两层 GELU MLP 投影；第一阶段（特征对齐预训练）冻结视觉 encoder 与 LLM，只训练投影层，第二阶段解冻 LLM 做视觉指令微调。讲义"Use It"一节的描述与此一致。
- A 错：BLIP-2 在 Q-Former 之后使用的是**一个全连接层**把 query 输出线性投影到 LLM 的输入维度。讲义说"two-layer MLP ... is what BLIP-2's Q-Former projection head ships with under the hood"，与 BLIP-2 论文不符。
- C 错：MiniGPT-4 用的是单个线性投影层（讲义也这样写），并且冻结 LLM。
- D 错：最早的 LLaVA 使用单个线性层，两层 MLP 是 LLaVA-1.5 的改进。讲义"This is the recipe LLaVA shipped in 2023"的说法较笼统。

### Q9 — 参考答案

1. 代码（我们实际运行过，结果如 Q6 所述）：

   ```python
   import torch, torch.nn.functional as F
   from main import AlignConfig, ViTConfig, VisionEncoder, MockTextEmbedding, make_pair, freeze

   cfg = AlignConfig()
   torch.manual_seed(cfg.seed)                                   # 与 train() 相同的初始化
   enc = VisionEncoder(ViTConfig(image_size=224, patch_size=16, hidden=768,
                                 depth=4, heads=8, mlp_ratio=2.0)).eval()
   freeze(enc)
   text = MockTextEmbedding(cfg.vocab_size, cfg.text_hidden, seed=cfg.seed + 1)
   pairs = [make_pair(cfg.seed + 1000 + i, cfg.vocab_size, cfg.max_caption_len)
            for i in range(cfg.pairs)]
   with torch.no_grad():
       cls = torch.cat([enc(img)[1] for img, _ in pairs])        # (32, 768)
       txt = torch.cat([text(ids) for _, ids in pairs])          # (32, 512)
   cn = F.normalize(cls, dim=-1)
   print("CLS pairwise cos min:", (cn @ cn.T).min().item())      # 0.99997
   upper = F.normalize(txt, dim=-1).mean(0).norm().item()
   print("single-direction upper bound:", upper)                 # 0.1870
   ```

2. 原因有三层：(a) `synthesize_image` 的所有图像共享同一个确定的颜色梯度，只是 σ = 0.1 的噪声不同，裁剪后右下大片饱和为 1；(b) encoder 是随机初始化的，没有学过"哪些像素差异重要"；(c) 16×16 的 patch 投影对独立噪声有平均效应，最终 CLS 主要由共享的梯度结构和位置编码决定。所以 32 个特征几乎重合。
3. 让 caption 成为图像内容的函数。例如定义 4 个"类别"，类别 k 的图像使用不同的通道排列/翻转（或画不同形状），caption 的 token 从类别专属的词表区间 `[1 + 100k, 1 + 100(k+1))` 中采样。我们用这种数据做了实验：在缓存并标准化的特征上用 24 对训练、8 对留出，留出集上逐对余弦只有 0.18（同类 caption 的具体 token 是随机的，无法预测），但"预测向量最接近哪一类的 caption 中心"的准确率为 **100%**——投影层学到了可泛化的类别级对应关系。

### Q10 — 参考答案

```python
def train_cached(cfg: AlignConfig, steps: int = 200, batch_size: int = 32):
    torch.manual_seed(cfg.seed)
    encoder = VisionEncoder(ViTConfig(image_size=224, patch_size=16, hidden=cfg.vision_hidden,
                                      depth=4, heads=8, mlp_ratio=2.0)).eval()
    freeze(encoder)
    text = MockTextEmbedding(cfg.vocab_size, cfg.text_hidden, seed=cfg.seed + 1)
    pairs = [make_pair(cfg.seed + 1000 + i, cfg.vocab_size, cfg.max_caption_len)
             for i in range(cfg.pairs)]
    with torch.no_grad():                                         # 只算一次
        X = torch.cat([encoder(img)[1] for img, _ in pairs])      # (N, 768)
        T = torch.cat([text(ids) for _, ids in pairs])            # (N, 512)

    projector = MLPProjector(cfg.vision_hidden, cfg.projection_hidden, cfg.text_hidden)
    opt = torch.optim.Adam(projector.parameters(), lr=cfg.lr)

    def eval_all() -> float:
        with torch.no_grad():
            return cosine_alignment_loss(projector(X), T).item()

    before = eval_all()
    g = torch.Generator().manual_seed(cfg.seed)
    for step in range(steps):
        idx = torch.randperm(len(X), generator=g)[:batch_size]
        loss = cosine_alignment_loss(projector(X[idx]), T[idx])
        opt.zero_grad(set_to_none=True); loss.backward(); opt.step()
    after = eval_all()
    return projector, before, after
```

1. 缓存后，encoder 只做 32 次前向而不是 200 次；原 demo 约 14.7 秒的运行时间几乎全部花在重复的 encoder 前向上。我们实测上面的 `train_cached`（full-batch，200 步）总耗时约 3.8 秒（其中大部分是构造 encoder 与 32 次前向）。
2. `eval_all()` 在全部样本上计算平均损失，前后可比；mini-batch 的梯度噪声也比 batch = 1 小得多。实测全部 32 对的平均损失 1.0161 → 0.8097，对应平均余弦约 0.19——仍然贴着 Q6 的单方向上界，说明换了训练方式，"坍缩到平均方向"的问题依旧存在，根源在数据与特征。
3. **不能说明**。32 对样本的 caption 是彼此无关的随机 token，标准化后 32 个特征彼此可分，一个 130 万参数的 MLP 完全可以把 32 个点"记住"映射到 32 个任意方向——这是**记忆**，不是对齐。必须在**留出集**上评估（新的图像、新的 caption），并且数据本身要存在可学习的对应关系（Q9 第 3 问）。在 Q9 的类别数据上，留出集的类别检索准确率 100%，那才是"学到了对齐"的证据。

### Q11 — 参考答案

```python
import torch
import torch.nn.functional as F

def contrastive_loss(image_emb: torch.Tensor, text_emb: torch.Tensor, tau: float = 0.07) -> torch.Tensor:
    if image_emb.shape[0] != text_emb.shape[0]:
        raise ValueError("batch size mismatch")
    img = F.normalize(image_emb, dim=-1)
    txt = F.normalize(text_emb, dim=-1)
    logits = img @ txt.T / tau                    # (B, B)：第 i 行是图 i 对所有 caption 的相似度
    labels = torch.arange(img.shape[0], device=img.device)
    return 0.5 * (F.cross_entropy(logits, labels) + F.cross_entropy(logits.T, labels))
```

- **坍缩解**：逐对余弦损失只要求 `cos(u_i, t_i)` 大，不关心 `u_i` 与别的 caption 的关系。当所有 `u_i` 都指向平均 caption 方向时，每对都能拿到约 0.19 的余弦，这是一个"稳定但无用"的解。对比损失要求 `cos(u_i, t_i)` 比 `cos(u_i, t_j)`（j ≠ i）**都大**；所有 `u_i` 相同时，每一行 logits 的大小顺序只取决于 caption 与平均方向的夹角，正确样本排第一的概率约 1/B，交叉熵约 `ln B`，损失很大，梯度会推动不同图像分开。
- **温度**：`tau` 太小，logits 被放大，softmax 接近 one-hot，梯度集中在最难的负样本上、方差大、训练不稳（讲义："gradient noise"）；`tau` 太大，所有 logits 接近，softmax 接近均匀，区分信号太弱，损失停在高位（讲义："loss plateaus high"）。CLIP 把 `1/tau` 作为可学习参数（并设上限）。
- 我们在 Q9 的类别数据（标准化特征、32 对 full-batch）上用 `tau = 0.07` 训练 200 步，训练集检索准确率为 100%，逐对余弦约 0.81。

### Q12 — 参考答案

1. **问题**：测试测的是测试文件里的一份**副本**，`train()` 的任何回归（比如把 `zero_grad` 删了、把 `projector` 的参数漏传给优化器）都不会被发现；`train` 被导入却没有使用。此外它也比较的是第 0 步与第 39 步两个不同样本的单次损失。讲义说测试覆盖"the training loop reduces loss between step 0 and step 200"，实际并不是。
2. **难测的原因**：`train()` 里把 `ViTConfig(image_size=224, ..., depth=4, heads=8)` 写死了，`make_pair` 也总是生成 224×224 的图像——没法换成 32×32 的小模型，200 步完整运行要十几秒。
3. **重构**：依赖注入。

   ```python
   def train(cfg, encoder=None, pairs=None, log=print):
       torch.manual_seed(cfg.seed)
       if encoder is None:
           encoder = VisionEncoder(ViTConfig(image_size=224, patch_size=16,
                                             hidden=cfg.vision_hidden, depth=4, heads=8, mlp_ratio=2.0))
       encoder = encoder.eval(); freeze(encoder)
       if pairs is None:
           pairs = [make_pair(cfg.seed + 1000 + i, cfg.vocab_size, cfg.max_caption_len)
                    for i in range(cfg.pairs)]
       ...  # 其余逻辑不变，print 改为 log

   class TestTrainFunction(unittest.TestCase):
       def test_train_reduces_mean_loss(self):
           cfg = AlignConfig(vision_hidden=64, projection_hidden=128, text_hidden=32,
                             vocab_size=64, max_caption_len=4, pairs=4, steps=40, lr=1e-3, seed=7)
           torch.manual_seed(0)
           enc = VisionEncoder(ViTConfig(image_size=32, patch_size=16, hidden=64,
                                         depth=2, heads=4, mlp_ratio=2.0))
           pairs = [(torch.randn(1, 3, 32, 32), torch.randint(1, 64, (1, 4))) for _ in range(4)]
           proj, stats = train(cfg, encoder=enc, pairs=pairs, log=lambda *a: None)
           first = sum(stats.losses[:4]) / 4               # 第一轮 4 个样本的平均
           last = sum(stats.losses[-4:]) / 4               # 最后一轮
           self.assertLess(last, first)
           self.assertTrue(all(not p.requires_grad for p in enc.parameters()))
   ```

   这样测试的是真正的 `train()`，比较的是"同一组样本"的平均损失，并顺带验证了冻结。

### Q13 — 参考回答要点

- **模态对齐**：让来自不同模态的表示在同一个向量空间中可比较、可互相替代——图像特征经过变换后，能被语言模型当作"词向量"来理解。
- **投影层的作用**：维度转换（如 1024 → 4096）+ 基底转换，把视觉 encoder 的特征翻译成 LLM 输入 embedding 空间中的"视觉 token"。在 LLaVA 式架构中，**每个 patch token** 都会被投影，作为一串前缀 token 送进 LLM；本节为了演示只投影了一个 CLS。
- **为什么先只训投影层**：视觉 encoder（如 CLIP ViT）和 LLM 都已有强大的预训练表示，先冻结它们，用大量图文对只训练一个很小的桥（讲义："the heavy parts stay frozen, the light bridge trains"）。好处：计算便宜、不会破坏两端已有能力、收敛快；之后再解冻 LLM 做指令微调。
- 加分点：提到 BLIP-2 的 Q-Former 用 32 个可学习 query 把视觉 token 压缩成固定数量，再线性投影；Flamingo 则用门控 cross-attention 把视觉信息注入 LLM 各层。

### Q14 — 参考回答要点

- **单层线性**：只能做旋转、缩放、剪切和平移（仿射变换）；若两个空间的语义结构"线性相关"，它就够用且最不容易过拟合（MiniGPT-4、最早的 LLaVA 都用线性层）。
- **两层 MLP**：中间的 GELU 提供非线性，可以表示更复杂的映射；LLaVA-1.5 报告两层 MLP 比线性投影效果更好。讲义所说的"curvature mismatch"可以理解为：两个空间中语义相近的点集分布在"弯曲"的结构上，线性映射无法把一个空间的弯曲结构展平到另一个空间，非线性才能做到。
- **风险**：参数更多、更容易过拟合小数据；在本节这种"输入几乎相同"的数据上，层数再多也无济于事（Q6）。
- 讲义练习 3 建议对比单层线性与两层 MLP 的损失差距，并指出"非线性在自然图像特征上更重要，在合成特征上不那么重要"。
- 加分点：更深的桥（Q-Former、cross-attention adapter、带 token 压缩的 resampler）主要是为了**减少视觉 token 数**和**选择性提取信息**，而不仅仅是增加非线性。

### Q15 — 参考回答要点

- **逐对余弦**：每个样本独立计算 `1 − cos(u_i, t_i)`，没有负样本。只要存在一个与大多数 caption 都"有点像"的方向，模型就能把所有输出放在那里获得中等分数——坍缩解（Q6）。
- **对比损失（InfoNCE，CLIP）**：一个 batch 内构造 B×B 相似度矩阵，对每一行/列做 softmax 交叉熵，要求正样本相似度高于所有负样本。坍缩会让损失接近 `ln B`，因此被强烈惩罚。
- **SigLIP**：把 softmax 换成逐元素的 sigmoid 二分类（正样本标签 1、负样本标签 0），不需要全局归一化，便于大 batch 分布式训练；讲义第 59 节提到它用于第 62 节。
- **代价**：对比学习需要足够大的 batch 提供负样本，还要处理"假负样本"（batch 中语义相同的不同样本）。
- 结论：逐对损失适合演示"桥能被训练"，真正的对齐预训练应使用对比目标或生成式目标（让 LLM 根据视觉 token 生成 caption 的 next-token 损失，LLaVA 第一阶段就是后者）。

### Q16 — 参考回答要点

- **架构**：预训练视觉 encoder（如 CLIP/SigLIP ViT）+ 两层 MLP 投影 + 7B LLM；所有 patch token（或经 2×2 合并后的 token）作为视觉前缀。
- **阶段 1（对齐）**：数据为大规模图文对（caption）；冻结视觉 encoder 与 LLM，只训投影层；目标是 LLM 在视觉前缀条件下生成 caption 的 next-token 损失（或对比损失）。成本低，几小时到一两天量级（视规模而定）。
- **阶段 2（指令微调）**：数据为多轮视觉问答/指令数据；解冻 LLM（全参数或 LoRA），投影层继续训练，视觉 encoder 通常仍冻结或用小学习率。
- **监控**：训练/验证损失；留出集上的图文检索 Recall@K；固定的一组探针图片的生成描述（人工抽查）；视觉 token 范数是否与文本 embedding 范数量级相当（尺度失配会让 LLM 忽略或被视觉 token 主导）。
- **判断"学到了东西"**：在留出数据上评测；做消融——把图像换成随机噪声或打乱图文配对，指标应明显下降。若打乱后指标不变，说明模型只是在利用语言先验（与本节 Q6 的"平均方向"是同一类问题）。
- 常见误区：只看训练损失下降；只用合成数据验证。

### Q17 — 参考回答要点

- **单样本比较**：初始与最终损失来自不同样本（pair 0 vs pair 7），不能直接相减；应报告全部样本的平均损失（Q5、Q10）。
- **上界分析**：图像特征两两余弦 ≥ 0.99997，投影层只能学到"平均 caption 方向"，平均余弦 0.1867 正好贴着单方向上界 0.1870——"alignment direction"是**一个**方向，不是图文对应（Q6）。
- **没有留出集**：即便训练集上损失很低，也可能只是记忆 32 个点（Q10 第 3 问中标准化后训练集余弦可达 1.0）。
- **数据本身没有可学的对应**：caption 是随机 token，与图像无关；任何"对齐"结论都缺乏前提（Q9）。
- **encoder 与讲义不一致**：演示用的是随机初始化的 4 层小 ViT，而非讲义所说的冻结的 86M 预训练 encoder。
- **判据过弱**：`drop > 0.0` 就打印 ok，噪声足以让它通过。
- **建议**：设计有对应关系的合成数据、缓存特征、mini-batch、在留出集上报告检索准确率与平均余弦，并做"打乱配对"的对照实验。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 59 Vision Transformer Encoder](../../59-vit-transformer/docs/zh.md)：本节冻结使用的 `VisionEncoder`，CLS 输出的来源。
- [阶段 19 · 58 视觉 Encoder 的图像 Patches](../../58-vision-encoder-patches/docs/zh.md)：`synthesize_image` 夹具的来源，理解为什么图像之间差异很小。
- [阶段 19 · 32 Token 与位置 Embeddings](../../32-token-positional-embeddings/docs/zh.md)：文本 embedding 表的基本概念。
- [阶段 03 · 05 Loss Functions](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：余弦、交叉熵等损失的基础。
- [阶段 04 · 05 Transfer Learning & Fine-Tuning](../../../04-computer-vision/05-transfer-learning/docs/zh.md)：冻结主干、只训练头部的迁移学习思想。

### 本节被哪些后续内容用到
- [阶段 19 · 61 Cross-Attention 融合](../../61-cross-attention-fusion/docs/zh.md)：从"一个向量对齐"走向"每个文本 token 关注每个视觉 token"。
- [阶段 19 · 62 视觉与语言联合 Pretraining](../../62-vision-language-pretraining/docs/zh.md)：把逐对损失推广为批内对比损失（InfoNCE）。
- [阶段 19 · 63 多模态 Evaluation](../../63-multimodal-eval/docs/zh.md)：用检索与留出评测判断对齐质量。
- [阶段 12 · 03 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former](../../../12-multimodal-ai/03-blip2-qformer-bridge/docs/zh.md)、[阶段 12 · 05 LLaVA 与视觉指令微调](../../../12-multimodal-ai/05-llava-visual-instruction-tuning/docs/zh.md)：真实系统中的投影桥。
- [阶段 04 · 25 Vision-Language Models — ViT-MLP-LLM 模式](../../../04-computer-vision/25-vision-language-models/docs/zh.md)：本节正是 "ViT-MLP-LLM" 中的 MLP。

### 延伸关键词
`modality alignment` · `projection head` · `MLP projector` · `LLaVA-1.5` · `Q-Former` · `cosine similarity` · `InfoNCE` · `temperature` · `representation collapse` · `feature caching` · `held-out evaluation` · `frozen backbone` · `dependency injection`
