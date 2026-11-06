# 测验 · Vision Transformers（ViT）（Vision Transformers (ViT)）

> **阶段 07 · Transformers 深入 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Patchify | 把 `H × W × C` 图像切成不重叠的 `P × P` 块并展平，得到 `N × (P·P·C)` 序列，`N = (H/P)·(W/P)`；224×224、P=16 → 196 个长 768 的向量 |
| 2 | Patch size 是杠杆 | P 越小 token 越多、分辨率越细，但 attention 代价按 token 数平方增长；P 越大越粗、越便宜 |
| 3 | 线性 patch embedding | 一个可学习矩阵把展平的 patch 投影到 `d_model`，等价于 `Conv2d(C, d_model, kernel_size=P, stride=P)` |
| 4 | `[CLS]` + 位置编码 | 在序列前加可学习的 `[CLS]`，其最终隐状态作为图像表示；位置编码可以是可学习的（原始 ViT）、2D 正弦或 2D RoPE |
| 5 | 编码器与 BERT 完全相同 | `LayerNorm → Self-Attention → + → LayerNorm → MLP → +` 堆 L 层，没有任何视觉专用层 |
| 6 | Head | 分类取 `[CLS]` → 线性层 → softmax；DINOv2、SAM 等丢弃 `[CLS]`，直接用 patch embedding |
| 7 | 归纳偏置与数据量 | ViT 没有 CNN 的局部性与平移不变性先验，需要大量数据（或强自监督）才能追上 CNN；DeiT 用蒸馏、DINOv2 用自监督解决 |
| 8 | 重要变体 | DeiT（蒸馏）、Swin（层次化 + 移位窗口，亚二次复杂度）、DINOv2（自监督特征）、SigLIP（sigmoid 对比损失）、register tokens |
| 9 | 参数量 | ViT-Base（12 层、d=768）约 86M，ViT-Large 约 307M，ViT-Huge 约 632M；ResNet-50 约 25M |

### 核心技能（能动手做到）

- [ ] 用纯 Python 实现 `patchify`，验证 patch 数等于 `(H/P)·(W/P)`、展平维度等于 `P·P·C`
- [ ] 用 NumPy 的 `reshape + transpose` 一行写出等价的 patchify，并与纯 Python 版逐元素对齐（光栅顺序）
- [ ] 实现 2D 正弦位置编码（`d_model` 一半编码行、一半编码列），说出为什么要求 `d_model % 4 == 0`
- [ ] 手算 ViT-Base/16 的参数量（每层 attention `4d²`、FFN `8d²`、LayerNorm `4d`，再加位置编码、`[CLS]`、head、patch embedding），得到约 86M
- [ ] 给定分辨率与 patch size，算出序列长度 `(H/P)² + 1` 并估算 attention 代价的变化
- [ ] 用 Hugging Face `ViTModel` 取出 `last_hidden_state`，说出 `(1, 197, 768)` 每一维的含义

---

## 二、基础自测（选择题）

**Q1.** 一张 `224 × 224 × 3` 的图像，用 `16 × 16` 的 patch 切分，得到的 patch 数与每个展平 patch 的长度分别是：

- A. 196 个，长度 256
- B. 196 个，长度 768
- C. 14 个，长度 768
- D. 256 个，长度 588

**Q2.** 保持 224×224 输入不变，把 patch size 从 16 改为 8，全局 self-attention 的分数矩阵计算量大约变为原来的：

- A. 2 倍
- B. 4 倍
- C. 16 倍
- D. 不变

**Q3.** ViT 的"线性 patch embedding"在 PyTorch 中最常见的等价写法是：

- A. `nn.Conv2d(C, d_model, kernel_size=P, stride=1)`
- B. `nn.Conv2d(C, d_model, kernel_size=P, stride=P)`
- C. `nn.MaxPool2d(kernel_size=P)`
- D. `nn.Embedding(P * P * C, d_model)`

**Q4.** 为什么在中小规模数据集上从零训练的 ViT 往往打不过同等算力的 CNN？

- A. ViT 的参数量太少
- B. ViT 缺少 CNN 的局部性、平移不变性等归纳偏置，需要更多数据才能学到这些规律
- C. ViT 无法处理彩色图像
- D. ViT 的 attention 只能看局部窗口

**Q5.** 关于 ViT 的 Transformer encoder，下列说法**正确**的是：

- A. 它在每层中加入了卷积层来提取局部特征
- B. 它和 BERT 的 encoder 结构一致，没有视觉专用层；视觉相关的设计集中在 patchify、位置编码和 `[CLS]` 池化
- C. 它使用因果掩码，按光栅顺序从左上到右下生成
- D. 它必须使用 encoder-decoder 结构

**Q6.** 一个在 224×224（P=16）上预训练的 ViT，要在 384×384 上微调。最需要处理的问题是：

- A. 词表大小不匹配
- B. patch 数从 196 变为 576，预训练的位置编码数量对不上，需要对位置编码做 2D 插值
- C. `[CLS]` token 必须删除
- D. 必须把 patch size 改成 24 才能保持 196 个 patch，否则无法加载权重

**Q7.** 下列关于 ViT 变体的描述，**错误**的是：

- A. DeiT 通过蒸馏，使 ViT 只用 ImageNet-1k 就能训练好
- B. Swin 用层次化结构和移位窗口，把注意力代价降到亚二次
- C. DINOv2 是自监督训练的，不需要标签
- D. SigLIP 是一个纯视觉自监督模型，不涉及文本

**Q8.** 在 `param_count_vit(d_model, n_layers, n_heads, ...)` 中，把 `n_heads` 从 12 改成 1，计算出的参数量会：

- A. 变为原来的 1/12
- B. 变为原来的 12 倍
- C. 不变
- D. 只有 FFN 部分变化

---

## 三、动手 / 代码题

**Q9.** 阅读下面的参数估算函数（摘自 `code/main.py`）：

```python
def param_count_vit(d_model, n_layers, n_heads, ffn_expansion, num_patches, num_classes):
    per_layer = 4 * d_model ** 2 + 2 * d_model * int(ffn_expansion * d_model) + 4 * d_model
    pos_emb = (num_patches + 1) * d_model
    head = d_model * num_classes
    return per_layer * n_layers + pos_emb + d_model + head + 2 * d_model
```

(1) 对 ViT-Base/16（d=768、12 层、FFN 扩展 4、196 个 patch、1000 类），分别算出 `per_layer`、12 层合计、`pos_emb`、`head`，再加上 `main()` 里额外加的 patch embedding `16·16·3·768`，总数是多少？(2) `per_layer` 中的 `4 * d_model` 对应什么？源码注释写的是 "Norms: 2 * d_model per layer"，哪个对？(3) 这个估算忽略了哪些参数？

**Q10.** 对 `pos_2d(4, 4, 48)` 返回的位置编码，位于第 2 行、第 3 列的 patch（`pe[2][3]`），其第 0、1、24、25 维分别等于什么？为什么函数开头要 `assert d_model % 4 == 0`？

```python
def pos_2d(H, W, d_model):
    assert d_model % 4 == 0, "d_model must be divisible by 4 for 2D sinusoidal"
    half = d_model // 2
    pe = [[[0.0] * d_model for _ in range(W)] for _ in range(H)]
    for i in range(H):
        for j in range(W):
            for k in range(half // 2):
                theta_row = i / (10000 ** (2 * k / half))
                pe[i][j][2 * k] = math.sin(theta_row)
                pe[i][j][2 * k + 1] = math.cos(theta_row)
            for k in range(half // 2):
                theta_col = j / (10000 ** (2 * k / half))
                pe[i][j][half + 2 * k] = math.sin(theta_col)
                pe[i][j][half + 2 * k + 1] = math.cos(theta_col)
    return pe
```

**Q11.** 用 NumPy 写出与 `code/main.py` 中 `patchify` **逐元素一致**的向量化版本 `patchify_np(img, P)`（输入形状 `(H, W, C)`，输出 `(N, P*P*C)`），并说明 `reshape` / `transpose` 每一步的维度含义。

---

## 四、面试高频题

**Q12.**（基础必考）从一张 224×224 的 RGB 图像开始，完整描述 ViT-B/16 做图像分类的前向过程，并写出每一步的张量形状。

**Q13.**（原理深挖）CNN 有哪些归纳偏置？ViT 缺少它们意味着什么？DeiT 和 DINOv2 分别怎么解决 ViT"吃数据"的问题？

**Q14.**（工程实践）你拿到一个在 224 分辨率上预训练的 ViT，要部署到 1024 分辨率的分割任务。会遇到哪些问题？怎么处理？

**Q15.**（场景设计）你只有 5000 张带标签的工业缺陷图片（10 类），GPU 资源有限。如何选骨干网络和训练方案？什么情况下你会改用 CNN？

**Q16.**（追问型）分类时用 `[CLS]` token 和对所有 patch token 做平均池化有什么区别？什么是 register tokens，它们解决了什么问题？

**Q17.**（追问型）ViT 的全局注意力和 Swin 的窗口注意力，计算复杂度分别是多少？Swin 如何让不同窗口之间交换信息？

---

## 五、参考答案与解析

### Q1 — 答案：B

`224 / 16 = 14`，网格是 14 × 14 = 196 个 patch；每个 patch 展平后长度 `16 × 16 × 3 = 768`。A 漏乘了通道数 3；C 只算了一边；D 是 P=14 时的 patch 数 `16 × 16 = 256` 搭配了 `14·14·3 = 588`，对应的是 ViT-H/14，不是本题。巧合的是 ViT-Base 的 `d_model` 也是 768，但这是两回事：一个是"原始像素维度"，一个是"模型隐藏维度"。

### Q2 — 答案：C

P 从 16 变 8，每边 patch 数翻倍，token 数从 196 变成 784（4 倍）；attention 分数矩阵是 `N × N`，所以计算量约为 4² = 16 倍。这就是讲义说的"更小的 patch = 更多 token、更细的分辨率、平方级的 attention 代价"。

### Q3 — 答案：B

kernel 大小 P、步长 P 的卷积恰好"一次看一个不重叠的 P×P 块，做一次线性组合"，输出通道数为 `d_model`——与"展平后乘一个 `(P·P·C, d_model)` 矩阵"在数学上等价。A 的 stride=1 会产生大量重叠窗口；C 是池化，没有可学习参数；D 的 `Embedding` 是按整数 id 查表，不适用于连续像素值。

### Q4 — 答案：B

CNN 的卷积核天然只看局部邻域（局部性），并在所有位置共享权重（平移等变），这些先验让 CNN 用较少数据就能学好。ViT 的全局 attention 从第一层起就能看整张图，没有这些先验，必须从数据中"学出"它们。讲义：没有 >100M 的标注图像或强自监督预训练，在同等算力下 CNN 仍然更强。D 错，原始 ViT 是全局注意力。

### Q5 — 答案：B

讲义："Identical to BERT. No vision-specific layers. This is the pedagogical punchline of the paper." 代码最后的 takeaway 也说"所有视觉相关的聪明之处都在 patchify + 位置方案 + `[cls]` 池化"。C 错，ViT 是双向 encoder，不做自回归生成。

### Q6 — 答案：B

`(384/16)² = 24² = 576` 个 patch，而预训练的可学习位置编码只有 196 + 1 个。通常把 14×14 的位置编码网格做 2D 插值到 24×24 再微调。配套 skill 明确要求：任何改变输入分辨率的部署都必须对位置编码做插值。D 不是必须的：Transformer 本身可以处理任意长度的序列，只有位置编码需要适配。

### Q7 — 答案：D

SigLIP 是"ViT + 文本编码器"的图文配对模型，用 sigmoid 对比损失训练（讲义称其为 CLIP 的继任者），必然涉及文本。A、B、C 都与讲义表格一致。

### Q8 — 答案：C

多头注意力只是把 `d_model` 维的 Q/K/V **切分**成 `n_heads` 份，每份 `d_model / n_heads` 维；Q、K、V、O 四个投影矩阵的总形状始终是 `d_model × d_model`，参数量 `4d²` 与头数无关。所以函数签名里虽然有 `n_heads`，函数体完全没用到它。头数影响的是计算的组织方式和表达能力，而不是参数量。

### Q9 — 参考答案

(1) ViT-Base/16：

| 项 | 计算 | 数值 |
|----|------|------|
| `per_layer` | `4·768² + 2·768·3072 + 4·768` = 2,359,296 + 4,718,592 + 3,072 | 7,080,960 |
| 12 层合计 | `7,080,960 × 12` | 84,971,520 |
| `pos_emb` | `197 × 768` | 151,296 |
| `[CLS]` | `768` | 768 |
| `head` | `768 × 1000` | 768,000 |
| 最终 LayerNorm | `2 × 768` | 1,536 |
| patch embedding（`main()` 里加） | `16·16·3·768` | 589,824 |
| **合计** | | **86,482,944 ≈ 86.5M** |

与运行输出 `ViT-Base/16 … ~86.5M params` 一致，也与讲义的 "~86M" 吻合。可以看到 98% 的参数在 12 个 Transformer 层里，其中 FFN 占了 2/3。

(2) `4 * d_model` 是每层**两个** LayerNorm（attention 前一个、MLP 前一个），每个有 γ 和 β 各 `d_model` 个参数，共 `2 × 2d = 4d`。代码是对的，源码注释 "2 * d_model per layer" 写错了（它可能想说"每个 LayerNorm 2d"）。

(3) 忽略了所有**偏置项**：Q/K/V/O 投影的偏置（4d）、FFN 两层的偏置（4d + d）、patch embedding 的偏置（d）、分类头的偏置（1000）。每层约 `9d ≈ 6.9K`，12 层约 83K，相对 86M 可以忽略，所以函数名里写的是"Approximate"。

### Q10 — 参考答案

`d_model = 48`，`half = 24`，前 24 维编码行、后 24 维编码列。当 `k = 0` 时 `10000 ** 0 = 1`，所以 `theta_row = i`、`theta_col = j`：

| 维度 | 公式 | 值 |
|------|------|----|
| `pe[2][3][0]` | `sin(2)` | ≈ 0.9093 |
| `pe[2][3][1]` | `cos(2)` | ≈ -0.4161 |
| `pe[2][3][24]` | `sin(3)` | ≈ 0.1411 |
| `pe[2][3][25]` | `cos(3)` | ≈ -0.9900 |

（已用代码验证。）

`d_model % 4 == 0` 的原因：先把 `d_model` 一分为二给行和列（需要被 2 整除），每一半又要成对存放 `(sin, cos)`（`half` 也要被 2 整除），所以总共要被 4 整除。若不满足，`range(half // 2)` 会漏掉维度，或者列编码的 `half + 2k + 1` 下标越界/错位。

### Q11 — 参考答案

```python
import numpy as np

def patchify_np(img, P):
    img = np.asarray(img)                        # (H, W, C)
    H, W, C = img.shape
    assert H % P == 0 and W % P == 0
    gh, gw = H // P, W // P
    x = img.reshape(gh, P, gw, P, C)             # (网格行, 块内行, 网格列, 块内列, 通道)
    x = x.transpose(0, 2, 1, 3, 4)               # (网格行, 网格列, 块内行, 块内列, 通道)
    return x.reshape(gh * gw, P * P * C)         # 光栅顺序展开网格；块内按 (di, dj, c) 展平
```

验证（`make_image`、`patchify` 来自 `code/main.py`）：

```python
img = make_image(24, 24, 3, seed=0)
p, _ = patchify(img, 6)
assert np.allclose(patchify_np(img, 6), np.array(p))   # 通过
```

每一步的含义：①`reshape(gh, P, gw, P, C)` 把高度拆成"第几个块 × 块内第几行"，宽度同理；②`transpose(0, 2, 1, 3, 4)` 把两个"块编号"维度挪到前面，两个"块内坐标"挪到后面；③最后一次 `reshape` 把块编号展平成 `N = gh·gw`（行优先，即光栅顺序），把块内 `(di, dj, c)` 展平成 `P·P·C`——与纯 Python 版 `for di: for dj: patch.extend(image[i+di][j+dj])` 的顺序完全一致。常见错误是漏掉 `transpose`，直接 `reshape(N, P*P*C)`，这样得到的"patch"其实是若干行像素拼起来的条带。

### Q12 — 参考回答要点

1. 输入 `(B, 3, 224, 224)`。
2. Patch embedding：`Conv2d(3, 768, kernel=16, stride=16)` → `(B, 768, 14, 14)` → 展平并转置 → `(B, 196, 768)`。
3. 在最前面拼接可学习的 `[CLS]` → `(B, 197, 768)`；加位置编码（形状 `(1, 197, 768)`）。
4. 12 层 pre-norm encoder block：`x = x + MHSA(LN(x))`，`x = x + MLP(LN(x))`，MLP 隐藏维 3072，形状保持 `(B, 197, 768)`。
5. 最后 LayerNorm，取第 0 个位置（`[CLS]`）→ `(B, 768)` → 线性层 → `(B, num_classes)` → softmax。

- 加分点：说明 Hugging Face `ViTModel` 输出的 `last_hidden_state` 形状正是 `(1, 197, 768)`；能指出 attention 矩阵是 `197 × 197`，每层每头一份。
- 常见误区：把 768（像素维）和 768（d_model）混为一谈；忘记 `[CLS]` 导致序列长度写成 196。

### Q13 — 参考回答要点

- **CNN 的归纳偏置**：①局部性（卷积核只看邻域）；②平移等变/权重共享（同一个核滑过所有位置）；③层次化（池化逐步扩大感受野）。这些先验相当于"免费的知识"，数据少时很有用。
- **ViT 缺少它们意味着**：第一层就是全局 attention，任何两个 patch 都能直接交互，表达能力更强，但"图像是局部相关的"这类规律需要从大量数据中学出来；数据不足时容易过拟合、泛化差。原始 ViT 需要 ImageNet-21k 或更大规模的预训练才能追上 ResNet。
- **DeiT（2021）**：引入蒸馏（用一个强 teacher 指导训练）和更强的数据增强/正则，使 ViT 只用 ImageNet-1k 就能训练好。
- **DINOv2（2023）**：自监督——不需要标签，通过图像增广 + 动量 teacher 学习，可以利用海量无标注图像，得到通用的视觉特征。
- **加分点**：指出数据足够大时，少先验反而是优势（上限更高），这是"scaling 胜过手工先验"的典型例子；Swin 则是反向操作，把局部性和层次化重新加回 ViT。

### Q14 — 参考回答要点

- **序列长度爆炸**：P=16 时 `(1024/16)² = 4096` 个 patch，attention 矩阵 4096×4096，显存和计算按平方增长。配套 skill 要求：序列长度超过 4096 时必须明确讨论 FlashAttention 和层次化变体（Swin）。
- **位置编码不匹配**：预训练只有 14×14 的位置编码，需要 2D 插值到 64×64；不插值直接部署是常见事故。
- **任务头**：分割是密集预测，不用 `[CLS]`，而是把 patch token 重新排回 `(64, 64, d)` 的特征图，接分割解码器/上采样。
- **工程手段**：用 FlashAttention 降低显存；选层次化骨干（Swin）或窗口注意力；或使用专为高分辨率分割设计的编码器（如 SAM 系列）。
- **常见误区**：以为"Transformer 能处理任意长度"就可以直接换分辨率——模型本身可以，但位置编码分布和 attention 代价都会出问题。

### Q15 — 参考回答要点

- **默认方案**：冻结的 DINOv2 骨干提特征 + 训练一个线性分类头（linear probe）。配套 skill：标注少于 10k 时，用冻结的 DINOv2 特征 + 线性探针；超过 100k 时再考虑微调最后几个 block。
- **理由**：5000 张图从零训练 ViT 必然打不过 CNN（skill 明确拒绝在少于 1M 图像时从零训练 ViT）；DINOv2 是在海量无标注数据上自监督训练的，特征通用，冻结后只训练很小的头，不易过拟合、算力消耗低。
- **训练配方**：AdamW、数据增强（RandAug、MixUp、Random Erasing）、label smoothing 0.1、EMA。
- **什么时候改用 CNN**：部署在边缘设备、延迟极其敏感时（讲义：CNN 在边缘设备和延迟敏感任务上仍然胜出；skill 中对应 ConvNeXt）。
- **加分点**：提到缺陷可能很小，需要关注输入分辨率与 patch size（小缺陷可能被 16×16 的 patch "平均掉"），以及类别不平衡问题。

### Q16 — 参考回答要点

- **`[CLS]` vs 平均池化**：`[CLS]` 是一个没有图像内容的可学习 token，通过每一层的 attention 从所有 patch 中聚合信息，最终隐状态作为整张图的表示；平均池化则直接对所有 patch 的输出取平均，不需要额外 token，在不少后续工作中效果相当甚至更好。密集任务（DINOv2 特征、SAM 分割）则直接使用 patch embedding，不依赖 `[CLS]`。
- **Register tokens**（Darcet et al. 2023）：在输入中额外加入几个可学习 token，它们不对应任何 patch，输出时直接丢弃。讲义说它们"吸收 attention sink"——模型原本会挪用一些信息量少的背景 patch 来存放全局信息，导致这些 patch 的特征和注意力图出现异常高的值（伪影）；加入 registers 后这部分计算有了专门的位置，patch 特征更干净，改善了 DINOv2 的特征质量。
- **加分点**：把 register 和 LLM 中"注意力集中到首 token（attention sink）"的现象联系起来；配套 skill 把"缺少 register token 可能伤害 DINOv2 特征"列为风险项。

### Q17 — 参考回答要点

- **ViT 全局注意力**：N 个 patch 两两计算，复杂度 O(N²·d)，N 随图像边长平方增长，所以 attention 代价对图像边长是四次方关系。
- **Swin 窗口注意力**：只在 M×M 的局部窗口内计算 attention，复杂度 O(N·M²·d)，对 N 线性（讲义称为"亚二次"）。
- **跨窗口通信**：相邻两层交替使用常规窗口划分与**移位窗口**（shifted windows，窗口偏移半个窗口大小），使上一层不同窗口的 patch 在下一层落入同一窗口；再加上 patch merging 逐层下采样，形成类似 CNN 的层次化特征金字塔，方便做检测和分割。
- **取舍**：Swin 重新引入了局部性先验，数据效率更高、适合高分辨率密集任务；代价是实现更复杂，失去了"任意两 patch 一步直达"的全局建模。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 05 完整的 Transformer](../../05-full-transformer/docs/zh.md)：encoder block 的结构。
- [阶段 07 · 06 BERT——掩码语言建模](../../06-bert-masked-language-modeling/docs/zh.md)：ViT 的 encoder 与 BERT 完全相同，`[CLS]` 的用法也来自 BERT。
- [阶段 07 · 04 位置编码](../../04-positional-encoding/docs/zh.md)：正弦编码与 RoPE，本节推广到 2D。
- [阶段 04 · 03 CNN：从 LeNet 到 ResNet](../../../04-computer-vision/03-cnns-lenet-to-resnet/docs/zh.md)：对比 CNN 的归纳偏置。
- [阶段 04 · 14 Vision Transformers 入门](../../../04-computer-vision/14-vision-transformers/docs/zh.md)：ViT 的视觉侧入门。

### 本节被哪些后续内容用到
- [阶段 07 · 10 音频 Transformers — Whisper 架构](../../10-audio-transformers-whisper/docs/zh.md)：同样的"把模态切成 token 序列"思路用于音频。
- [阶段 04 · 17 自监督视觉](../../../04-computer-vision/17-self-supervised-vision/docs/zh.md)：DINO 系列自监督训练。
- [阶段 04 · 18 开放词表 CLIP](../../../04-computer-vision/18-open-vocab-clip/docs/zh.md)：ViT 作为图文对比学习的图像编码器（SigLIP 的前身）。
- [阶段 04 · 24 SAM 3 开放词表分割](../../../04-computer-vision/24-sam3-open-vocab-segmentation/docs/zh.md)：ViT 骨干 + 可提示的 mask decoder。
- [阶段 12 · 01 Vision Transformer 与 patch token](../../../12-multimodal-ai/01-vision-transformer-patch-tokens/docs/zh.md)：多模态模型中的视觉 token。
- [阶段 12 · 06 任意分辨率 Patch-n-Pack](../../../12-multimodal-ai/06-any-resolution-patch-n-pack/docs/zh.md)：处理可变分辨率与位置编码插值。

### 延伸关键词
`MAE (masked autoencoder)` · `position embedding interpolation` · `2D RoPE` · `patch merging` · `distillation token` · `NaViT` · `FlexiViT` · `linear probe`
