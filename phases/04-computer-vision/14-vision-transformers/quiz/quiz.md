# 测验 · Vision Transformers（ViT）

> **阶段 04 · 计算机视觉 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、读过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | ViT 七步流水线 | patch embedding → 展平成 token → 前置 `[CLS]` → 加位置编码 → N 个 Transformer encoder block → 取 `[CLS]` 输出 → 分类头 |
| 2 | Patch embedding | 一个 `kernel_size = stride = patch_size` 的卷积同时完成"切块"和"线性投影"；224×224、patch 16 → 14×14 = 196 个 token |
| 3 | Class token | 一个可学习向量放在序列最前面；经过 self-attention 汇聚全图信息，分类头只读它 |
| 4 | 可学习位置编码 | 形状 `(1, num_patches+1, dim)`，直接加到 token 上；Transformer 本身对位置无感，必须显式告诉它每个 patch 来自哪里 |
| 5 | Pre-LN encoder block | `x = x + MSA(LN(x))`，`x = x + MLP(LN(x))`；MLP 为 `d → 4d → GELU → d`；比 Post-LN 更容易稳定训练深层网络 |
| 6 | Patch 大小的取舍 | patch 越小 token 越多（8→784、16→196、32→49），细节越多，但 attention 代价按 token 数平方增长 |
| 7 | 归纳偏置与数据量 | ViT 没有 CNN 的局部性、平移等变性先验；只在 ImageNet-1k 上训练时输给 ResNet，在 ImageNet-21k / JFT-300M 上预训练后反超 |
| 8 | DeiT 训练配方 | 强数据增强（RandAugment、Mixup、CutMix、Random Erasing）+ stochastic depth + repeated augmentation +（可选）CNN 教师蒸馏，仅用 ImageNet-1k 训练 ViT-B 达到 81.8% top-1 |
| 9 | Swin / ConvNeXt / MAE | Swin：局部窗口 attention + 移位窗口；ConvNeXt：按 Swin 的设计选择重构的纯 CNN；MAE：遮住 75% 的 patch 再重建，是主流自监督预训练方案 |

### 核心技能（能动手做到）

- [ ] 从零写出 `PatchEmbedding`、Pre-LN `Block`、`ViT`，并打印每一步的张量形状：`(N,3,64,64) → (N,16,192) → (N,17,192) → (N,192) → (N,10)`
- [ ] 手算 tiny ViT（dim=192, depth=6）和 ViT-B/16 的参数量，并说出每一部分的占比
- [ ] 能把 Pre-LN block 改写成 Post-LN，并说清两者在梯度通路上的差别
- [ ] 能在换分辨率微调时正确处理位置编码（对 patch 部分做 2D 插值、`[CLS]` 部分保持不变）
- [ ] 能计算不同 patch 大小下的 token 数和 attention 代价
- [ ] 能根据数据量、推理栈、任务类型在 ViT / Swin / ConvNeXt 之间选型

---

## 二、基础自测（选择题）

**Q1.** ViT-B/16 的 patch embedding 是 `Conv2d(3, 768, kernel_size=16, stride=16)`。输入 224×224 的图像后，输出形状和这一层的参数量分别是：

- A. `(768, 224, 224)`，参数量 768
- B. `(768, 14, 14)`，展平后 196 个 token；参数量 `3·768·16·16 + 768 = 590,592`
- C. `(768, 16, 16)`，展平后 256 个 token；参数量 `3·768·16·16 = 589,824`
- D. `(196, 14, 14)`，参数量 `196·768`

**Q2.** 关于 `[CLS]` token，下列说法**错误**的是：

- A. 它是一个可学习的参数向量，对所有输入图像都相同
- B. 经过若干层 self-attention 后，它可以聚合所有 patch 的信息
- C. 它必须存在，ViT 去掉 `[CLS]` 就无法做分类
- D. 本节代码中，分类头只读取它经过最终 LayerNorm 后的输出

**Q3.** 现代 ViT 普遍采用 Pre-LN（`x + sublayer(LN(x))`）而不是 Post-LN（`LN(x + sublayer(x))`），主要原因是：

- A. Pre-LN 的参数量更少
- B. Pre-LN 中残差主干不经过 LayerNorm，梯度可以沿恒等路径直接回传，深层网络无需 warmup 也能稳定训练
- C. Post-LN 无法在 GPU 上运行
- D. Pre-LN 让 attention 的复杂度从平方降为线性

**Q4.** 输入 224×224，把 patch 从 16 换成 8，token 数和每层 attention 的 query-key 对数分别变为原来的：

- A. 2 倍、4 倍
- B. 4 倍、16 倍
- C. 4 倍、4 倍
- D. 不变，只是每个 token 的维度变小

**Q5.** 下列哪一项**不属于**讲义中 DeiT 在 ImageNet-1k 上训练 ViT 的配方？

- A. RandAugment、Mixup、CutMix、Random Erasing 等强数据增强
- B. Stochastic depth（训练时随机丢弃整个 block）
- C. Repeated augmentation（同一张图在一个 batch 内采样 3 次）
- D. 把 patch embedding 换成 3×3 卷积堆叠的 stem，引入局部性先验

**Q6.** ConvNeXt 这项工作得出的最重要结论是：

- A. Attention 本质上优于卷积，CNN 已无竞争力
- B. CNN 与 Transformer 的差距主要不是"attention vs 卷积"，而是现代训练配方和架构设计（深度可分离卷积、LayerNorm、GELU、倒置瓶颈等）
- C. ConvNeXt 证明了位置编码对 CNN 同样必要
- D. 只要用 BatchNorm，CNN 就能超过 Swin

**Q7.** 关于 MAE 预训练，正确的是：

- A. 随机遮住 15% 的 patch，encoder 处理全部 patch（被遮住的用 mask token 代替）
- B. 随机遮住 75% 的 patch，encoder 只处理可见的 25%，一个小 decoder 重建被遮住的 patch；预训练结束后丢掉 decoder，微调 encoder
- C. 需要人工标注的类别标签
- D. 预训练后保留 decoder 用于分类

---

## 三、动手 / 代码题

**Q8.** 运行 `main()`：

```python
def main():
    torch.manual_seed(0)
    vit = ViT(image_size=64, patch_size=16, num_classes=10, dim=192, depth=6, num_heads=3)
    x = torch.randn(2, 3, 64, 64)

    patches = vit.patch(x)
    print(f"[shapes] input {tuple(x.shape)} -> patches {tuple(patches.shape)}")
    cls = vit.cls_token.expand(x.size(0), -1, -1)
    tokens = torch.cat([cls, patches], dim=1)
    print(f"[shapes] tokens with CLS: {tuple(tokens.shape)}")
    tokens = tokens + vit.pos_embed
    print(f"[shapes] after pos embed: {tuple(tokens.shape)}")
    logits = vit(x)
    print(f"[shapes] output logits:   {tuple(logits.shape)}")
    print(f"[params] total: {sum(p.numel() for p in vit.parameters()):,}")
    # ...
```

(1) 写出这 5 行打印结果（参数量请按模块分解计算）。
(2) `PatchEmbedding.forward` 中 `x.flatten(2).transpose(1, 2)` 两步各把形状从什么变成什么？为什么需要 `transpose`？
(3) 若构造 `ViT(image_size=64, patch_size=12)` 会发生什么？

**Q9.** 本节 `Block.forward`：

```python
    def forward(self, x):
        normed = self.ln1(x)
        a, _ = self.attn(normed, normed, normed, need_weights=False)
        x = x + a
        x = x + self.mlp(self.ln2(x))
        return x
```

(1) 讲义版本写的是 `self.attn(self.ln1(x), self.ln1(x), self.ln1(x), ...)`。两者结果一样吗？代码版本好在哪里？
(2) `need_weights=False` 有什么作用？
(3) 改写成 Post-LN 版本（保留 `ln1`、`ln2` 两个模块）。
(4) 若把 `num_heads` 改为 5（`dim=192`），会怎样？每个头的维度在原配置下是多少？

**Q10.** 用 64×64 图像训练好的 tiny ViT，直接输入 96×96 的图像会在哪一行出错？为什么？请写一个函数 `resize_pos_embed(pos_embed, old_grid, new_grid)`，把位置编码从 4×4 网格插值到 6×6 网格（保留 `[CLS]` 位置不变），并说明还需要修改模型的哪个属性。

---

## 四、面试高频题

**Q11.**（基础必考）以 ViT-B/16、224×224 输入为例，完整讲一遍 ViT 的前向过程和每一步的张量形状。它的约 86M 参数主要花在哪里？

**Q12.**（原理深挖）什么是归纳偏置？CNN 有哪些、ViT 缺哪些？为什么原始 ViT 需要 JFT-300M 才能超过 ResNet？后来哪些方法解决了这个问题？

**Q13.**（原理深挖）Pre-LN 和 Post-LN 有什么区别？为什么 Pre-LN 更稳定？它有没有代价？

**Q14.**（工程实践）你要把一个在 224×224 上预训练的 ViT-B/16 微调到 384×384 的医学影像数据集（约 5 万张）。需要注意哪些问题？

**Q15.**（场景设计）三个需求分别选什么 backbone，为什么？（a）在手机 NPU 上做实时图像分类；（b）服务器 GPU 上做语义分割；（c）只有 3,000 张标注图的细粒度分类，服务端部署。

---

## 五、参考答案与解析

### Q1 — 答案：B

`kernel_size = stride = 16` 时，卷积在 224×224 上不重叠地滑动 `224/16 = 14` 次，得到 `(768, 14, 14)`，展平后 196 个 token。参数量 = 权重 `768 × 3 × 16 × 16 = 589,824` + bias 768 = 590,592。C 混淆了 patch 大小和网格大小，且漏了 bias。这一层等价于"把每个 16×16×3 的 patch 拉平成 768 维向量，再乘一个 768×768 的矩阵"。

### Q2 — 答案：C

`[CLS]` 并非必需：很多后续模型（讲义 quiz 也提到 ConvNeXt 等）用所有 patch token 的全局平均池化（GAP）代替 `[CLS]`，效果相当。A 对：`cls_token` 是 `nn.Parameter`，用 `expand` 复制到 batch 中的每张图。B 对：attention 让它能看到所有 patch。D 对：代码中 `self.head(self.ln(x[:, 0]))`。

### Q3 — 答案：B

Pre-LN 的残差主干 `x → x + f(LN(x)) → …` 是一条纯加法的恒等通路，梯度可以不经过任何 LayerNorm 直接传到浅层；Post-LN 每一层都要经过 LN，深层网络的梯度在初始化时就不稳定，需要 warmup 和较小的学习率。讲义："Post-LN 在没有 warmup 时难以训练超过 6–8 层"。A、C 错；D 是混淆——LN 的位置与 attention 复杂度无关。

### Q4 — 答案：B

token 数 `(224/p)²`：p=16 时 196，p=8 时 784，是 4 倍；attention 的 query-key 对数是 token 数的平方，`196² = 38,416` → `784² = 614,656`，是 16 倍。这就是讲义说"8×8 patch 更精细，但 O(n²) 的 attention 代价扩展得很差"的原因，也是 Swin 用局部窗口的动机。

### Q5 — 答案：D

讲义列出的 DeiT 四项改进：强数据增强、stochastic depth、repeated augmentation、（可选）CNN 教师蒸馏。D 是后来一些"卷积 stem"工作的思路，不属于 DeiT。DeiT 的意义在于证明"大规模预训练数据不是严格必需的"，用训练配方弥补先验的缺失。

### Q6 — 答案：B

ConvNeXt 把 ResNet 一步步向 Swin 的设计靠拢（深度可分离卷积、LayerNorm、GELU、倒置瓶颈），最终纯 CNN 就能追平 Swin，说明差距来自"现代训练配方 + 架构细节"，而非算子本身。讲义还指出 ConvNeXt 在边缘端更容易编译部署。D 错：ConvNeXt 恰恰把 BN 换成了 LayerNorm。

### Q7 — 答案：B

MAE 遮住 75% 的 patch，encoder 只处理 25% 的可见 patch（因此预训练很省算力），轻量 decoder 负责重建像素；预训练后丢弃 decoder，只微调 encoder。A 描述的是 BERT 式 15% 遮盖，且 MAE 的 encoder 不处理 mask token。C 错：MAE 是自监督的，不需要标签。

### Q8 — 参考答案

(1) 预期输出（未实际运行，形状与参数量由代码确定性推出）：

```text
[shapes] input (2, 3, 64, 64) -> patches (2, 16, 192)
[shapes] tokens with CLS: (2, 17, 192)
[shapes] after pos embed: (2, 17, 192)
[shapes] output logits:   (2, 10)
[params] total: 2,822,602
```

参数量分解：

| 模块 | 计算 | 参数量 |
|------|------|-------|
| patch conv | 3·192·16·16 + 192 | 147,648 |
| cls_token | 1·1·192 | 192 |
| pos_embed | 1·17·192 | 3,264 |
| 每个 Block | ln1 384 + attn（`in_proj` 3·192·192+576，`out_proj` 192·192+192）148,224 + ln2 384 + mlp（192·768+768 + 768·192+192）295,872 | 444,864 |
| 6 个 Block | 444,864 × 6 | 2,669,184 |
| 最终 ln | 2·192 | 384 |
| head | 192·10 + 10 | 1,930 |
| **合计** | | **2,822,602** |

与讲义"约 2.8M"一致。注意 MLP 的参数约是 attention 的 2 倍——Transformer 的大部分参数其实在 MLP 里。

(2) `self.proj(x)` 输出 `(2, 192, 4, 4)`；`flatten(2)` 从第 2 维开始展平 → `(2, 192, 16)`；`transpose(1, 2)` → `(2, 16, 192)`。Transformer 约定的输入布局是 `(batch, 序列长度, 特征维)`（`batch_first=True`），而卷积输出是"通道在前"，所以要交换后两维。

(3) `PatchEmbedding.__init__` 中 `assert image_size % patch_size == 0` 失败，抛出 `AssertionError`（64 不能被 12 整除）。如果没有这个断言，卷积会静默丢掉右侧和底部无法组成完整 patch 的像素（输出 5×5，覆盖 60×60），而 `num_patches` 会被算成 `(64 // 12)² = 25`，碰巧不报错却丢失了边缘信息。

### Q9 — 参考答案

(1) 结果完全一样（LayerNorm 是确定性运算），但讲义版本把 `self.ln1(x)` 算了 3 次，浪费计算和显存；代码版本只算一次再复用。此外，三个参数传入同一个张量对象时，`nn.MultiheadAttention` 能识别出这是 self-attention（`query is key is value`），有机会走更快的实现路径。

(2) `need_weights=False` 告诉 `nn.MultiheadAttention` 不需要返回 attention 权重矩阵（默认会返回按头平均的 `(N, L, L)` 权重），这样可以省掉这部分的计算和显存，并允许 PyTorch 使用融合的 scaled-dot-product attention 内核。返回的第二个值此时为 `None`，所以用 `_` 接收。

(3) Post-LN 版本：

```python
    def forward(self, x):
        a, _ = self.attn(x, x, x, need_weights=False)
        x = self.ln1(x + a)                 # 先残差相加，再 LayerNorm
        x = self.ln2(x + self.mlp(x))
        return x
```

区别在于 LN 位于残差相加**之后**，残差主干本身被反复归一化。Post-LN 网络的最后一层输出已经过 LN，所以 `ViT` 末尾的 `self.ln` 可以去掉；Pre-LN 则必须保留最终的 LN，因为残差主干从未被归一化。

(4) `nn.MultiheadAttention` 要求 `embed_dim` 能被 `num_heads` 整除，192 不能被 5 整除，构造时会报错（`embed_dim must be divisible by num_heads`）。原配置每个头的维度为 `192 / 3 = 64`，与 ViT-B 的 `768 / 12 = 64` 相同。

### Q10 — 参考答案

出错位置：`ViT.forward` 中的 `x = x + self.pos_embed`。96×96 的图像经 patch 卷积得到 6×6 = 36 个 token，加上 `[CLS]` 共 37 个，而 `pos_embed` 的形状是 `(1, 17, 192)`，第 1 维 37 与 17 无法广播，抛出 `RuntimeError`。（patch 卷积本身对任意能被 16 整除的尺寸都能工作，问题只在于位置编码的长度是固定的。）

```python
import torch
import torch.nn.functional as F

def resize_pos_embed(pos_embed, old_grid, new_grid):
    """pos_embed: (1, 1 + old_grid**2, dim)，第 0 个位置是 [CLS]。"""
    cls_pos = pos_embed[:, :1]                                  # (1, 1, dim)，保持不变
    patch_pos = pos_embed[:, 1:]                                # (1, old_grid**2, dim)
    dim = patch_pos.shape[-1]
    patch_pos = patch_pos.reshape(1, old_grid, old_grid, dim).permute(0, 3, 1, 2)  # (1, dim, 4, 4)
    patch_pos = F.interpolate(patch_pos, size=(new_grid, new_grid),
                              mode="bicubic", align_corners=False)            # (1, dim, 6, 6)
    patch_pos = patch_pos.permute(0, 2, 3, 1).reshape(1, new_grid * new_grid, dim)
    return torch.cat([cls_pos, patch_pos], dim=1)               # (1, 1 + 36, dim)

# 用法（当前环境无 torch，未实际运行）：
# vit.pos_embed = nn.Parameter(resize_pos_embed(vit.pos_embed.data, 4, 6))
# vit.patch.num_patches = 36
```

要点：
- 位置编码要先恢复成 2D 网格再插值，直接在 1D 序列上插值会破坏行列结构；`[CLS]` 不对应任何空间位置，原样保留。
- `vit.patch.num_patches` 只在构造 `pos_embed` 时用到，运行时并不读取，但为了一致性应同步更新。
- 这正是 skill 文件提到的最常见移植 bug；`timm` 中有现成的 `resize_pos_embed` 工具。插值后通常还要在新分辨率上微调一段时间。
- 如果 patch 大小也变了（如 /16 → /32），不能靠插值解决，应换用对应的架构。

### Q11 — 参考回答要点

- **前向过程**：
  1. 输入 `(B, 3, 224, 224)`；
  2. `Conv2d(3, 768, 16, stride=16)` → `(B, 768, 14, 14)` → flatten + transpose → `(B, 196, 768)`；
  3. 前置 `[CLS]` → `(B, 197, 768)`；
  4. 加可学习位置编码 `(1, 197, 768)`；
  5. 12 个 Pre-LN block（12 头，每头 64 维；MLP 768→3072→768，GELU），形状保持 `(B, 197, 768)`；
  6. 取 `x[:, 0]`，过最终 LayerNorm → `(B, 768)`；
  7. 线性分类头 → `(B, 1000)`。
- **参数分布**（按本节代码的结构计算，合计约 86.57M）：
  - 每个 block 约 7.09M，其中 attention（QKV + 输出投影）约 2.36M、MLP 约 4.72M，12 个 block 共约 85.05M，占绝大多数；
  - patch embedding 约 0.59M，位置编码约 0.15M，1000 类分类头约 0.77M。
- **加分点**：
  - 指出 MLP 参数约是 attention 的 2 倍；
  - attention 的计算量与 token 数平方相关，参数量却与 token 数无关——这就是换分辨率时参数不变、只有位置编码长度要变的原因。

### Q12 — 参考回答要点

- **归纳偏置**：模型结构中预设的、关于数据的假设。
- **CNN 有、ViT 缺的先验**：
  - 局部性（卷积核只看邻域）；
  - 平移等变性（权重共享，同一物体平移后特征也平移）；
  - 层级结构（逐步下采样）。
  ViT 只在切 patch 时有一点点局部性，此后每层都是全局 attention，空间关系全靠位置编码和数据学出来。
- **数据量的影响**：先验少意味着要从数据里学，ImageNet-1k（约 128 万张）不够，ViT 输给 ResNet；在 ImageNet-21k / JFT-300M 上预训练后，学到的规律反而更灵活，迁移后反超。
- **后续解法**：
  - DeiT：强增强 + stochastic depth + repeated augmentation + 蒸馏，用训练配方弥补先验的缺失；
  - MAE / DINO：自监督预训练，不需要标签就能利用数据；
  - Swin：把局部窗口先验加回来。
- **常见误区**：以为"ViT 一定要海量数据"。讲义指出，DeiT、MAE 证明用对配方后，ViT 在小数据上也能训好。

### Q13 — 参考回答要点

- **区别**：
  - Post-LN：`x = LN(x + f(x))`，原始 Transformer（2017）的写法；
  - Pre-LN：`x = x + f(LN(x))`，ViT、GPT-2 之后的主流写法。
- **为什么 Pre-LN 稳定**：残差主干是纯加法，存在一条从输出到输入的恒等梯度通路；每个子层的输入都经过归一化，数值范围可控。Post-LN 的梯度要逐层穿过 LN，深层时浅层梯度在初始化阶段就可能异常，必须依赖 warmup 和小学习率。
- **代价**：
  - 残差主干不断累加、不被归一化，激活幅值随深度增长，所以最后必须再加一个 LayerNorm（本节代码 `self.ln`）；
  - 深层时后面的层对主干的相对贡献变小，有研究认为 Pre-LN 的最终效果可能略逊于调好的 Post-LN。
- **加分点**：
  - 现代 LLM 多用 Pre-RMSNorm；
  - 训练深层 Transformer 时，warmup 与 LN 位置是一起讨论的问题。

### Q14 — 参考回答要点

- **位置编码**：224/16 = 14×14 → 384/16 = 24×24，序列长度从 197 变为 577。要把 patch 部分的位置编码恢复成 2D 网格、双三次插值到 24×24，`[CLS]` 位置保持不变（`timm` 加载时可自动完成）。patch 大小必须保持 16，否则需要换架构。
- **算力**：token 数约为 2.9 倍，attention 代价约 8.5 倍（577² / 197²），显存显著增加，可能需要减小 batch、使用梯度累积、混合精度、梯度检查点。
- **微调策略**：
  - 先做 linear probe 看特征质量，再全量微调；
  - 用较小的学习率加 warmup，可以对浅层用更小的学习率（discriminative / layer-wise LR）；
  - 5 万张图属于中等规模，配合 DeiT 式增强防止过拟合。医学影像与自然图像的分布差异大，优先考虑领域内或自监督（MAE / DINOv2）预训练的权重。
- **数据**：输入归一化的均值/方差要和预训练时一致；若是灰度图，需要复制成 3 通道，或修改 patch 卷积的输入通道（例如把 3 个通道的权重求和）。
- **常见坑**：位置编码长度不匹配却被"非严格加载"静默跳过，模型看似能跑但效果极差——这正是 skill 文件中检查器要拦截的问题。

### Q15 — 参考回答要点

- **（a）手机 NPU 实时分类**：选 ConvNeXt-Tiny 或 EfficientNet-V2-S。讲义和选型 prompt 都指出 Transformer 很少能顺利编译到 NPU，ConvNeXt 在边缘端编译更友好；除非有专门的 MobileViT 支持，否则不选 Transformer。
- **（b）服务器语义分割**：选 Swin-V2 或 ConvNeXt-B。密集预测需要多尺度特征金字塔，层级结构的 backbone 比单一分辨率的 plain ViT 更合适。
- **（c）3,000 张细粒度分类**：选线性探测效果最强的自监督预训练 backbone，通常是 DINOv2 ViT-B；先做 linear probe，再视情况微调。不要选 ViT-L/H，数据太少，纯属浪费算力。
- **加分点**：
  - 推理栈是硬约束，要先于数据量考虑；
  - 给出延迟估算，并在 ONNX 导出、INT8 量化这些环节提前验证。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 02 从零实现 Self-Attention](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：`softmax(QKᵀ/√d)V`，ViT 的核心算子。
- [阶段 07 · 03 多头注意力](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：`nn.MultiheadAttention` 内部做了什么。
- [阶段 04 · 04 图像分类](../../04-image-classification/docs/zh.md)：分类训练流程与评估。
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：对比理解 CNN 的归纳偏置。

### 本节被哪些后续内容用到
- [阶段 04 · 17 自监督视觉](../../17-self-supervised-vision/docs/zh.md)：SimCLR、DINO、MAE 都以 ViT 为主干。
- [阶段 04 · 18 开放词表视觉——CLIP](../../18-open-vocab-clip/docs/zh.md)：CLIP 的图像编码器就是 ViT。
- [阶段 04 · 25 Vision-Language Models](../../25-vision-language-models/docs/zh.md)：ViT-MLP-LLM 模式中的视觉编码器。
- [阶段 04 · 15 实时视觉——边缘部署](../../15-real-time-edge/docs/zh.md)：为什么边缘端仍偏爱 CNN。
- [阶段 07 · 09 Vision Transformers](../../../07-transformers-deep-dive/09-vision-transformers/docs/zh.md)：从 Transformer 视角再看 ViT。
- [阶段 12 · 01 ViT patch tokens](../../../12-multimodal-ai/01-vision-transformer-patch-tokens/docs/zh.md)：多模态模型如何把 patch token 送进 LLM。
- [阶段 19 · 58 视觉编码器 patch](../../../19-capstone-projects/58-vision-encoder-patches/docs/zh.md)、[阶段 19 · 59 ViT Transformer](../../../19-capstone-projects/59-vit-transformer/docs/zh.md)：综合项目中从零搭建视觉编码器。

### 延伸关键词
`DeiT 蒸馏 token` · `stochastic depth` · `Swin shifted window` · `ConvNeXt-V2` · `MAE` · `DINOv2` · `位置编码插值` · `layer-wise LR decay` · `GAP vs [CLS]` · `timm`
