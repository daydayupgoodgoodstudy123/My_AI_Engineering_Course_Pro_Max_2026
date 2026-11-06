# 测验 · Vision Transformers 与 Patch-Token 基本单元（Vision Transformers and the Patch-Token Primitive）

> **阶段 12 · 多模态 AI · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要切 patch | 224×224 RGB 逐像素展开是 150,528 个 token，自注意力对序列长度是平方复杂度，不可行；切成 16×16 patch 只剩 196 个 |
| 2 | Patch embedding | `(H, W, 3)` → `(H/P)×(W/P)` 个 patch，每个展平成 `3P²` 维，乘共享矩阵 `W_E: (3P², D)`；等价于 `Conv2d(3, D, kernel_size=P, stride=P)` |
| 3 | ViT-B/16 标准配置 | 224 分辨率、P=16 → 14×14=196 个 patch，每个 `16×16×3=768` 像素值投影到 D=768，加 `[CLS]` 后序列长 197 |
| 4 | 位置编码 | 早期用可学习的 1D 位置表（换分辨率需插值）；现代用 2D-RoPE 按 (行, 列) 旋转 Q/K，没有位置表，可处理任意网格 |
| 5 | 图像级表示 | `[CLS]`（原始 ViT、CLIP）/ mean pool（讲义：SigLIP、DINOv2 等）/ 喂给 LLM 时不做 pooling，每个 patch 都是 LLM 输入 token |
| 6 | Register tokens | Darcet et al.（2023）：无显式"汇点"时 ViT 会产生高范数的伪影 patch 劫持注意力；加 4–16 个可学习 register 吸收它，改善分割、深度等稠密预测；交给 LLM 前丢弃 |
| 7 | 预训练目标 | 监督（JFT-300M）→ CLIP 对比学习 → MAE（遮 75% 重建像素）→ DINO/DINOv2 自蒸馏 → SigLIP/SigLIP 2（sigmoid 损失 + NaFlex） |
| 8 | 两个缩放杠杆 | patch 越小 token 越多（P14 比 P16 多），分辨率越高 token 按平方增长；序列长 N 翻倍，注意力的 `N²` 项翻 4 倍 |
| 9 | 参数估算 | 每个 block ≈ `12D² + 13D`（含 bias 与 LN）；ViT-B/16 约 85.8M（不含分类头），讲义取整为 ≈86M |
| 10 | 计算量估算 | 每个 block 的 FLOPs ≈ `24ND² + 4N²D`（乘加按 2 次运算计）；本节代码的公式混用了 MAC 与 FLOP 两种口径 |

### 核心技能（能动手做到）

- [ ] 给定 (H, W, P)，手算网格形状和序列长度（含 CLS、register），并能判断不整除时会发生什么
- [ ] 用纯 Python 把一张小图切成 patch、展平、做线性投影，说清每个 patch 的像素顺序
- [ ] 手算任意 ViT 的参数量（patch embed、位置表、block、LN），并与代码输出对上
- [ ] 正确估算前向 FLOPs，区分 MAC 与 FLOP，判断注意力的 `N²` 项何时开始占主导
- [ ] 为下游任务选择 pooling：分类用 CLS/mean，稠密预测关注 register，VLM 直接交出全部 patch token
- [ ] 估算高分辨率图片和视频的视觉 token 预算，并说出降低预算的手段（帧采样、pooling、token merging）

---

## 二、基础自测（选择题）

**Q1.** ViT-B/16 处理 224×224 的图像（含一个 `[CLS]` token、无 register），序列长度是：

- A. 197
- B. 196
- C. 225
- D. 768

**Q2.** 讲义说 patch embedding 在生产代码中通常用一个卷积实现。下列哪个与"每个 P×P×3 patch 展平后乘以 `(3P², D)` 矩阵"在数学上等价？

- A. `Conv2d(3, D, kernel_size=3, stride=1)` 后再做 P×P 最大池化
- B. `Conv2d(3, D, kernel_size=P, stride=1)`
- C. `Conv2d(3, D, kernel_size=P, stride=P)`
- D. `Conv2d(3, 3P², kernel_size=1, stride=P)`

**Q3.** 如果不切 patch，把一张 224×224 RGB 图像的每个像素值都当成一个 token，序列长度是：

- A. 50,176
- B. 196
- C. 768
- D. 150,528

**Q4.** 关于 register tokens，下列说法与讲义一致的是：

- A. 它们是位置编码的一种，替代 2D-RoPE
- B. 它们是额外的可学习 token，用来吸收 ViT 预训练中出现的高范数注意力伪影，改善分割、深度等稠密预测；交给 LLM 之前会被丢弃
- C. 它们存储图像的类别标签，等价于 `[CLS]`
- D. 它们是 VLM 中每张图像必须传给 LLM 的摘要 token

**Q5.** 同一个 patch 14 的 ViT，把输入分辨率从 224 提高到 448（其它不变）。patch token 数和注意力分数矩阵（`N²` 项）分别变为原来的几倍？

- A. 2 倍和 4 倍
- B. 4 倍和 4 倍
- C. 4 倍和 16 倍
- D. 2 倍和 2 倍

**Q6.** 一个 VLM 把视觉 encoder 的输出交给 LLM 做 VQA（视觉问答）。按讲义，通常怎么处理 encoder 的输出？

- A. 不做 pooling，把每个 patch token 都作为 LLM 的输入 token；register token 丢弃
- B. 只把 `[CLS]` 的输出交给 LLM
- C. 只把 register token 交给 LLM
- D. 对所有 patch 做 mean pool，得到一个向量交给 LLM

**Q7.** 相比可学习的 1D 位置表，2D-RoPE 的主要好处是：

- A. 参数更多，表达能力更强
- B. 让模型不再需要自注意力
- C. 把 patch 的顺序固定成行优先，便于展平
- D. 没有位置表，按 (行, 列) 旋转 Q/K 表达相对二维位置，推理时可处理任意网格大小，不需要对位置表插值

**Q8.** 讲义写"SigLIP 2 SO400m/14 … default resolution 384 → 729 patch tokens"。在本节代码中调用 `grid_shape(384, 14)` 会：

- A. 返回 `(27, 27)`
- B. 抛出 `ValueError`，因为 384 不能被 14 整除（代码的 ZOO 因此用的是 378 = 27×14）
- C. 返回 `(28, 28)`，向上取整
- D. 返回 `(27.43, 27.43)`

---

## 三、动手 / 代码题

**Q9.** 代码的计算量公式：

```python
def flops_per_forward(cfg: ViTConfig) -> int:
    n = seq_length(cfg)
    d = cfg.hidden
    attn = 4 * n * d * d + 2 * n * n * d
    mlp = 2 * n * d * 4 * d * 2
    return cfg.depth * (attn + mlp)
```

对 ViT-B/16 @ 224 输出 `28.60B`。

1. 分别数出一个 block 里注意力部分和 MLP 部分的乘加次数（MAC），指出这段代码的口径问题。
2. 给出统一按 FLOPs（1 MAC = 2 FLOPs）和统一按 MACs 的正确公式，并计算 ViT-B/16 @ 224 的结果。
3. 对 Qwen2.5-VL @ 896（N = 4097、D = 1280），注意力 `N²` 项占总 FLOPs 的比例大约是多少？对 ViT-B/16 呢？这说明了什么？

**Q10.** 代码的玩具示例把 8×8 灰度图（像素值 `r*8 + c`）切成 4 个 4×4 patch，用 `fake_W[i][j] = ((i + j) % 5) - 2` 投影到 4 维，输出：

```text
  token 0: [8, -31, -35, -4]
  token 1: [0, -35, -35, 0]
  token 2: [-56, -63, -35, 28]
  token 3: [-64, -67, -35, 32]
```

1. 为什么第 3 维（下标 2）在 4 个 token 上都是 `-35`？
2. 不重新计算点积，如何从 token 0 直接推出 token 2？
3. 这个玩具示例与真实 ViT 的 patch embedding 有哪些不同？（至少说 3 点）

**Q11.** `grid_shape` 只支持正方形图像，且要求整除。讲义练习 1、2 却要处理 1280×720 和 1920×1080。

1. 写一个 `grid_shape_hw(h, w, p, mode="floor")`，支持非正方形，`mode` 可选 `"floor"`（丢弃边缘）或 `"pad"`（补齐到整数个 patch）。
2. 用 `floor` 模式计算：1280×720 @ P14 的 patch 数；1920×1080 @ P14 每帧的 patch 数；30 FPS、5 分钟视频的视觉 token 总数。
3. 与"只保留一个 CLS 向量"相比，1280×720 那张图的 token 数大多少倍？

**Q12.** 代码 `ZOO` 中的最后一项：

```python
    ViTConfig("Qwen2.5-VL ViT @ 896x896", 896, 14, 1280, 32, 16),
```

它用了 `cls_token=True` 的默认值，并且 `pos_embed_params` 会为它算出一个 4097 × 1280 的可学习位置表（5.2M 参数）。

1. 根据讲义自身对现代 backbone 位置编码的描述，指出这个配置哪里不一致。
2. 修改配置使其不含 CLS、不含可学习位置表，参数量和序列长度分别变成多少？
3. 讲义 KEY RATIOS 部分说"That is why high-resolution VLMs need token-merging or pooling"。如果在送入 LLM 前把相邻 2×2 个 patch 合并成 1 个 token，896×896 的图像会给 LLM 多少个视觉 token？

---

## 四、面试高频题

**Q13.**（基础必考）请描述 ViT 如何把一张图片变成 Transformer 的输入序列，写出每一步的张量形状，并估算 ViT-B/16 的参数量。

**Q14.**（原理深挖）ViT 与 CNN 在归纳偏置（inductive bias）上有什么区别？为什么原始 ViT 需要 JFT-300M 这种规模的数据才能超过 ResNet？换分辨率时位置编码会遇到什么问题？

**Q15.**（工程实践）你要为一个"文档 / 截图 OCR 问答"VLM 选择视觉 encoder 与输入设置，会如何权衡 patch 大小、分辨率、预训练目标、pooling 方式和 token 预算？

**Q16.**（场景设计）要做一个能理解 5 分钟 1080p 视频的 VLM，视觉 token 预算怎么估？有哪些降低预算的手段，各自的代价是什么？

**Q17.**（追问型）CLS pooling、mean pooling、register tokens 有什么区别？为什么 ViT 会出现高范数的"伪影 token"，register 为什么能解决它？

---

## 五、参考答案与解析

### Q1 — 答案：A

`224 / 16 = 14`，网格 14×14 = 196 个 patch，加 1 个 `[CLS]` 得 197（代码输出 `seq length : 197 (incl CLS, 0 registers)`）。B 漏了 CLS；C 是把 15×15 误算进来；D 是隐藏维度（也恰好等于每个 patch 的像素数 `16×16×3`），不是序列长度。

### Q2 — 答案：C

卷积核大小 P、步长 P，意味着每个输出位置恰好覆盖一个互不重叠的 P×P×3 patch，输出通道 D 个、每个通道一组 `3P²` 个权重——正好是 `(3P², D)` 的矩阵乘（卷积的 bias 对应线性层的 bias）。讲义："`nn.Conv2d(3, D, kernel_size=P, stride=P)`"。B 的步长为 1，patch 互相重叠，输出网格约为 `(H−P+1)²`；A 是完全不同的结构；D 的 1×1 卷积只看单个像素。

### Q3 — 答案：D

`224 × 224 × 3 = 150,528`（讲义原文数字）。A 是 `224 × 224`，即只算像素位置不算通道。自注意力分数矩阵是 `N × N`，15 万长度意味着约 2.3×10¹⁰ 个分数，"a non-starter"。

### Q4 — 答案：B

讲义："Adding 4–16 learnable register tokens absorbs this load and improves dense-prediction quality (segmentation, depth)"、"Registers get discarded before handoff (they are scaffolding, not content)"。A 错，register 与位置编码无关；C 混淆了 CLS 的作用（且 CLS 也不存标签）；D 正好相反。

### Q5 — 答案：C

网格从 16×16 变为 32×32，patch 数 256 → 1,024，是 4 倍（分辨率按边长翻倍，token 数按面积增长）；注意力分数矩阵 `N×N` 变为 16 倍。讲义："Going from 224 to 384 to 512 almost always helps, at quadratic cost in FLOPs"。A 把 token 数当成随边长线性增长。

### Q6 — 答案：A

讲义："For VLMs that feed patch tokens into an LLM, you skip pooling entirely — every patch becomes an LLM input token. Registers get discarded before handoff"。B、D 只给 LLM 一个向量，细节全丢，无法回答"左上角写了什么字"这类问题；C 把脚手架当内容。

### Q7 — 答案：D

讲义："2D-RoPE rotates the query and key vectors based on the patch's (row, column) index ... No position table. The model handles arbitrary grid sizes at inference." 可学习位置表"ties the model to the training resolution: at inference you have to interpolate the position table if you change the grid"。A 错：RoPE 没有参数；B、C 与位置编码无关。

### Q8 — 答案：B

`384 / 14 = 27.43`，`grid_shape` 检查 `image_size % patch_size != 0` 时抛 `ValueError: image_size (384) must be divisible by patch_size (14)`（已运行验证）。27×27 = 729 对应的分辨率是 `27 × 14 = 378`，所以代码的 ZOO 写的是"SigLIP SO400m/14 @ 378"，而讲义正文和"Use It"一节写的是 384——讲义与代码不一致。实际以 384 输入的模型，卷积步长为 14 时会舍弃边缘不足一个 patch 的像素（384 − 378 = 6 像素），得到的仍是 27×27；代码选择了"不整除即报错"的严格策略。

### Q9 — 参考答案

1. 一个 block 的 MAC（N 个 token、隐藏维 D、MLP 扩 4 倍）：
   - Q、K、V、O 四个 `D×D` 投影：`4ND²`；
   - `QKᵀ`：`N²D`；`softmax · V`：`N²D`，合计 `2N²D`；
   - MLP 两层 `D→4D→D`：`2 × N × D × 4D = 8ND²`。

   代码的 `attn = 4nd² + 2n²d` 是 **MAC** 口径，而 `mlp = 2·n·d·4d·2 = 16nd²` 多乘了一个 2，是 **FLOP** 口径。两者相加既不是 MACs 也不是 FLOPs。skill 文件里写的也是同一个混合公式（"Attention (4 N D^2 + 2 N^2 D per block) and MLP (16 N D^2 per block)"）。

2. 正确公式（忽略 LN、softmax、patch embedding 等小项）：
   - 按 MACs：`L × (12ND² + 2N²D)`
   - 按 FLOPs：`L × (24ND² + 4N²D)`

   ViT-B/16 @ 224（N = 197、D = 768、L = 12，已用 Python 计算）：**17.45 GMACs** / **34.89 GFLOPs**，而代码输出 28.60B。论文和库里常说的"ViT-B/16 约 17.6 GFLOPs"实际上是 MAC 口径（再加上 patch embedding 等小项），比较时一定要先确认口径。

3. 按 FLOPs 公式，`N²` 项占比 `4N²D / (24ND² + 4N²D) = N / (6D + N)`：
   - ViT-B/16 @ 224：`197 / (4608 + 197) ≈ 4.1%`；
   - Qwen2.5-VL @ 896：`4097 / (7680 + 4097) ≈ 34.8%`。

   低分辨率时计算量几乎全在线性层（随 N 线性增长）；分辨率一高，平方项迅速变成大头——这正是高分辨率 VLM 要做 token merging、窗口注意力或 pooling 的原因。

### Q10 — 参考答案

1. 第 3 维的权重是 `fake_W[2][j] = ((2 + j) % 5) − 2`，16 个值为 `[0, 1, 2, −2, −1, 0, 1, 2, −2, −1, 0, 1, 2, −2, −1, 0]`，**总和为 0**。而 4 个 patch 之间只差一个常数偏移（patch 1 = patch 0 + 4，patch 2 = patch 0 + 32，patch 3 = patch 0 + 36，因为像素值是 `r*8 + c`）。权重和为 0 的那一维对常数偏移不敏感，所以 4 个 token 在这一维取值相同，都等于 patch 0 的点积 `−35`。
2. 每一维满足 `token_k[i] = token_0[i] + offset_k × sum(fake_W[i])`。4 行权重的和分别为 `−2, −1, 0, 1`。patch 2 的偏移是 32：`[8 − 64, −31 − 32, −35 + 0, −4 + 32] = [−56, −63, −35, 28]`，与输出一致。同理 token 3（偏移 36）：`[8 − 72, −31 − 36, −35, −4 + 36] = [−64, −67, −35, 32]`。这正是**线性**投影的性质。
3. 与真实 ViT 的不同：
   - 灰度单通道，真实图像是 3 通道，每个 patch 展平后是 `3P²` 维；
   - 权重是确定性的整数模式，真实 `W_E` 是学出来的浮点矩阵，而且有 bias；
   - 没有加位置编码，也没有 `[CLS]`/register；
   - 展平顺序是"patch 内行优先"，而 PyTorch `Conv2d` 权重的布局是 `(D, C, P, P)`，从线性层迁移权重时需要对齐顺序；
   - 像素没有归一化（真实流程先除以 255 再按均值方差标准化）。

### Q11 — 参考答案

1. 参考实现（已运行验证）：

```python
import math

def grid_shape_hw(h: int, w: int, p: int, mode: str = "floor") -> tuple[int, int]:
    if min(h, w, p) <= 0:
        raise ValueError("h, w, p must be positive")
    if mode == "floor":                 # 舍弃右/下边缘不足一个 patch 的像素
        return h // p, w // p
    if mode == "pad":                   # 补零到 p 的整数倍
        return math.ceil(h / p), math.ceil(w / p)
    raise ValueError(f"unknown mode {mode!r}")
```

2. `floor` 模式（已用 Python 计算）：
   - 1280×720：宽 `1280 // 14 = 91`、高 `720 // 14 = 51`，共 **4,641** 个 patch；
   - 1920×1080：宽 137、高 77，每帧 **10,549** 个 patch；
   - 30 FPS × 300 秒 = 9,000 帧，总计 **94,941,000** 个视觉 token（约 9,500 万）。

   注意：真实模型通常会先把图像缩放到 patch 大小（或合并后 token 大小）的整数倍再切分，所以精确数字取决于各模型的预处理规则；这里的数字用于数量级估算。
3. 4,641 个 patch token 对比 1 个 CLS 向量，约 4,641 倍。CLS 表示适合分类和检索，但细节（文字、位置）几乎全部丢失；VLM 做问答需要保留 patch 级 token，代价就是这几千倍的上下文开销。

### Q12 — 参考答案

1. 讲义说现代 backbone 使用 2D-RoPE（并点名"Qwen2-VL's M-RoPE"），"No position table"；而且讲义也说现代 VLM 通常不依赖 CLS。代码却给 Qwen2.5-VL 的 ViT 加了 `[CLS]`（序列长 4,097 而不是 4,096）和一个 `4097 × 1280 = 5,244,160` 参数的可学习位置表。这两项都是套用了 2020 年原始 ViT 的模板。
2. 改为 `ViTConfig("Qwen2.5-VL ViT @ 896x896", 896, 14, 1280, 32, 16, cls_token=False)`，并让 `pos_embed_params` 对使用 RoPE 的配置返回 0（例如给 `ViTConfig` 加 `pos: str = "learned"` 字段，`"rope"` 时位置参数为 0）。结果：序列长度 **4,096**；参数量从 635.7M 变为 **630.4M**（已用 Python 计算：去掉 5,244,160 的位置表和 1,280 的 CLS）。代码中 block 结构仍按标准 ViT（MLP 4 倍、LayerNorm）估算，真实模型的细节可能不同，这里只修正讲义自己指出的两点。
3. 64×64 = 4,096 个 patch，2×2 合并后为 32×32 = **1,024** 个 LLM token，降为 1/4。Qwen2-VL 系列正是在 encoder 输出后做相邻 patch 合并再送入 LLM（细节见阶段 12 · 09）。

### Q13 — 参考回答要点

- **步骤与形状**（以 ViT-B/16、224 为例）：
  1. 输入 `(B, 3, 224, 224)`；
  2. patch embedding（`Conv2d(3, 768, 16, 16)`）→ `(B, 768, 14, 14)` → 展平转置为 `(B, 196, 768)`；
  3. 拼接 `[CLS]` → `(B, 197, 768)`；加位置编码（可学习表 `(197, 768)` 或在注意力中用 2D-RoPE）；
  4. 12 个 pre-norm Transformer block，形状保持 `(B, 197, 768)`；
  5. 最终 LayerNorm，取 CLS 或 mean pool 得到 `(B, 768)`，分类时再接线性头；VLM 则交出 `(B, 196, 768)`。
- **参数量**：patch embed `3×16×16×768 + 768 = 590,592`；位置表 `197×768 = 151,296`；CLS 768；每个 block `12×768² + 13×768 = 7,087,872`，×12 = 85,054,464；最终 LN 1,536。合计 **85,798,656 ≈ 85.8M**（代码输出），讲义取整为 ≈86M；若加 ImageNet-1k 分类头（`768×1000 + 1000`）还会再多约 0.77M。
- 加分点：说明 block 参数中 MLP 占约 2/3；patch embedding 相对很小（不到 1%）。

### Q14 — 参考回答要点

- **CNN 的归纳偏置**：局部感受野、权重共享带来的平移等变性、层级式下采样——这些先验让 CNN 在中小数据上就能学好。
- **ViT 的偏置很弱**：只有 patch 切分隐含"局部性"，其余关系全靠注意力从数据中学，因此需要更多数据。讲义："With enough data (JFT-300M, then LAION) it beat ResNet on ImageNet and kept improving"；讲义也指出用 CNN 特征喂 Transformer 的旧方案"inherits the CNN's biases ... and loses the transformer's appetite for scale"。
- **后续补救**：自监督预训练（MAE、DINO/DINOv2）和图文对比预训练（CLIP/SigLIP）让 ViT 不依赖标注数据也能扩展。
- **换分辨率的问题**：可学习位置表是按训练网格学的，网格变了只能插值，效果会下降；2D-RoPE 没有位置表，可直接处理任意网格（讲义）。
- 加分点：Zhai et al.（2022）的 ViT 缩放律——在固定算力下，模型和数据一起扩大效果可预测地变好。

### Q15 — 参考回答要点

- **patch 大小**：OCR 需要细粒度，倾向 P14（讲义："Patch 14 ... better for OCR and dense tasks, worse for speed"）。
- **分辨率**：文档字体小，分辨率是最大杠杆；但 token 数随面积增长、注意力随 N² 增长。优先选支持原生分辨率/宽高比的方案（NaFlex、patch-n'-pack），避免把长条截图压扁。
- **预训练目标**：需要与文本对齐的语义 → CLIP/SigLIP 系；需要稠密特征 → DINOv2（讲义）。VLM 场景通常用 SigLIP 系。
- **pooling**：不做 pooling，交出全部 patch token；丢弃 register。
- **token 预算**：按 `ceil(H/P) × ceil(W/P)` 估算每页 token 数，与 LLM 上下文和成本对账；超预算时用 token merging（如 2×2 合并）、裁剪/分块（tile）或降低分辨率。
- **工程检查**：用本节的几何计算器先算出序列长度、参数量、FLOPs 和显存，再加载权重（讲义："Ball-park every ViT this way before you load the checkpoint"）。
- 常见误区：只看参数量选 encoder，忽略了分辨率带来的 token 数爆炸。

### Q16 — 参考回答要点

- **预算估算**（P14、`floor` 规则）：1920×1080 每帧约 10,549 个 patch；30 FPS × 300 秒 = 9,000 帧，共约 9,500 万个视觉 token，远超任何 LLM 上下文。
- **降低预算的手段与代价**：
  - **帧采样**（如 1–2 FPS）：直接降 15–30 倍；代价是丢失快速动作和短暂出现的内容。
  - **降低每帧分辨率**：token 按面积下降；代价是小字、细节丢失。
  - **空间 pooling / token merging**（如 2×2 合并）：每帧降 4 倍，保留大致布局；代价是细粒度定位变差。
  - **时间维合并**：相邻帧变化小，合并冗余 token；代价是对快速变化不敏感。
  - **按需检索**：先用低分辨率全局浏览，再对相关片段高分辨率重看；代价是系统复杂度。
- 讲义练习 2 问"哪种最省"：按倍数，帧采样通常最立竿见影；实际系统会组合使用。
- 加分点：给出具体组合的算账，如"1 FPS × 448×252 × 2×2 合并"后的 token 总数，并与目标上下文窗口比较。

### Q17 — 参考回答要点

- **CLS pooling**：序列前加一个可学习 token，最后取它的输出；继承自 BERT，原始 ViT 和 CLIP 使用；适合分类/检索。
- **mean pooling**：对所有 patch 输出取平均；讲义说 SigLIP、DINOv2 和多数现代 VLM 使用；不依赖某一个 token 的"汇总能力"。
- **register tokens**：额外的可学习 token，不代表图像内容，用来吸收注意力中的"全局信息存放"需求。
- **伪影成因**（讲义："ViTs trained without an explicit sink token develop high-norm 'artifact' patches that hijack self-attention"）：模型需要某处存放全局信息，就会占用一些信息量低的背景 patch，使其范数异常高、吸走大量注意力，这些 patch 的局部特征也被破坏，损害分割、深度等稠密任务。
- **register 的作用**：提供专门的"汇点"，伪影从 patch 上消失，patch 特征更干净；用完即丢。讲义："DINOv2 and SigLIP 2 both ship with registers"。
- 加分点：三种方式不互斥——可以有 register 的同时用 mean pool 做图像级表示；VLM 场景则三者都不需要，直接交出 patch。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 09 Vision Transformers (ViT)](../../../07-transformers-deep-dive/09-vision-transformers/docs/zh.md)：ViT 架构本身的详解。
- [阶段 04 · 14 Vision Transformers (ViT)](../../../04-computer-vision/14-vision-transformers/docs/zh.md)：从计算机视觉视角理解 ViT。
- [阶段 04 · 02 从零实现卷积](../../../04-computer-vision/02-convolutions-from-scratch/docs/zh.md)：理解"patch embedding = stride=P 的卷积"。
- [阶段 07 · 02 Self-Attention 从头开始](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：注意力的 `N²` 代价从何而来。
- [阶段 07 · 04 位置编码 — 正弦、RoPE、ALiBi](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：1D 位置表与 RoPE，本节推广到 2D。
- [阶段 04 · 17 自监督视觉 — SimCLR、DINO、MAE](../../../04-computer-vision/17-self-supervised-vision/docs/zh.md)：DINO、MAE 预训练目标。

### 本节被哪些后续内容用到
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../02-clip-contrastive-pretraining/docs/zh.md)：ViT 作为图像塔的对比预训练。
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：patch token 经投影直接送入 LLM。
- [阶段 12 · 06 任意分辨率视觉：Patch-n'-Pack 与 NaFlex](../../06-any-resolution-patch-n-pack/docs/zh.md)：讲义练习 5 的打包与块对角注意力掩码。
- [阶段 12 · 09 Qwen-VL 系列与动态帧率视频](../../09-qwen-vl-family-dynamic-fps/docs/zh.md)：原生分辨率、M-RoPE 与 token 合并。
- [阶段 12 · 18 百万 Token 上下文中的长视频理解](../../18-long-video-million-token/docs/zh.md)：视频视觉 token 预算问题。
- [阶段 19 · 58 视觉 Encoder 的图像 Patches](../../../19-capstone-projects/58-vision-encoder-patches/docs/zh.md)、[阶段 19 · 59 Vision Transformer Encoder](../../../19-capstone-projects/59-vit-transformer/docs/zh.md)：综合项目中完整实现。

### 延伸关键词
`patch embedding` · `Conv2d stride=P` · `[CLS] token` · `mean pooling` · `register tokens` · `2D-RoPE / M-RoPE` · `position interpolation` · `DINOv2` · `MAE` · `SigLIP 2` · `NaFlex` · `patch-n'-pack` · `token merging` · `MACs vs FLOPs`
