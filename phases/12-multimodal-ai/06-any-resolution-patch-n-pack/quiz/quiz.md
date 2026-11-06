# 测验 · 任意分辨率视觉：Patch-n'-Pack 与 NaFlex（Any-Resolution Vision: Patch-n'-Pack and NaFlex）

> **阶段 12 · 多模态 AI · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 固定方形的三种失败 | 讲义：resize 会挤压文字（squished text）、crop 会丢内容（cropped content）、pad 会把 token 浪费在填充上（wasted tokens on padding） |
| 2 | Patch-n'-Pack（NaViT） | 每张图按原生分辨率切 patch → 各自展平 → 拼成一条长序列 → 用块对角（block-diagonal）mask 隔离各图 → 每个 patch 携带自己的位置信息 |
| 3 | 块对角 mask | 形状 `(N_total, N_total)`，同一图像内为 1、跨图为 0；非零元素数 = `Σ n_i²`。可由累积长度 `offsets = [0, n_0, n_0+n_1, ...]` 构造 |
| 4 | `cu_seqlens` | FlashAttention varlen 路径直接用累积长度张量在各段内做注意力，不需要稠密 mask；讲义称"~10x faster than a dense mask" |
| 5 | Token dropping | NaViT 训练时随机丢弃部分 patch（如 50%），既正则化又加速；SigLIP 2 继承了这一点 |
| 6 | AnyRes（LLaVA-NeXT） | encoder 冻结在 336 时的实用方案：从预定义网格中选最接近长宽比的一个，每块 576 token，再加一张缩略图；1344×1344 用 4×4 时约 9800 token |
| 7 | M-RoPE（Qwen2-VL） | 每个 patch 带 3D 位置 `(t, row, col)`，旋转位置编码天然支持任意 H、W、T，无需位置表；token 数随原生面积 `O(H·W/P²)` 增长，没有切块的乘法开销 |
| 8 | NaFlex（SigLIP 2） | 一个 checkpoint 在推理时支持多种序列长度（256 / 729 / 1024 token），训练时用 NaViT 式打包和分数位置 |
| 9 | 按任务分配预算 | 讲义：OCR/文档 1024–4096；图表/UI 729–1024；自然照片 256–576；视频每帧 64–128 |
| 10 | 生产规则 | 讲义："pick a per-task max-pixels cap, encode at native aspect ratio up to that cap, pack the batch, and skip padding"；Qwen2.5-VL 暴露 `min_pixels` / `max_pixels` |

### 核心技能（能动手做到）

- [ ] 给定一批 `(H, W)` 与 patch 大小，算出每张图的网格、token 数、打包总长、`cu_seqlens` 和块对角 mask 的非零比例
- [ ] 写出块对角 mask 和"打包 + 二维位置 id + 段 id"的构造代码
- [ ] 比较 square-resize、AnyRes、原生分辨率三种策略的 token 数，并加上 `max_pixels` 上限重新计算
- [ ] 估算稠密 mask 的内存，说明为什么生产中用 `cu_seqlens` 而不是稠密 mask
- [ ] 读代码时识别出"宽×高"与 `(h, w)` 的顺序错位、AnyRes 打分函数的缺陷，以及"原生打包 = 最少 token"这一错误结论
- [ ] 能根据任务（OCR、图表、照片、视频）选择策略并给出每张图的 token 预算

---

## 二、基础自测（选择题）

**Q1.** 讲义列出的"把所有图像 resize 成固定方形"等旧做法的三种失败模式是：

- A. 训练变慢、推理变慢、显存增加
- B. 文字被挤压变形、内容被裁掉、token 浪费在填充上
- C. 颜色失真、亮度变化、对比度降低
- D. 位置编码溢出、梯度消失、过拟合

**Q2.** 一个 batch 中有 336×336、224×224、448×336 三张图，patch 大小 14。用 Patch-n'-Pack 打包后：

- A. 每张图都被 pad 到 768 个 token，总长 2304
- B. 每张图都被 resize 到 576 个 token，总长 1728
- C. 总长 1600，mask 是 1600×1600 的下三角因果矩阵
- D. 各图分别为 576、256、768 个 token，总长 1600，mask 是 1600×1600 的块对角矩阵

**Q3.** 讲义练习 2：四张图的长度为 256、576、729、1024。块对角 mask 的非零元素个数及其占整个 mask 的比例约为：

- A. 1,977,329 个，约 29.6%
- B. 2,585 个，约 0.04%
- C. 6,682,225 个，100%
- D. 3,341,112 个，约 50%

**Q4.** 代码玩具示例打印 `cu_seqlens (FlashAttn varlen): [0, 6, 14]`，它的含义是：

- A. 第一张图有 6 个 token，第二张图有 14 个 token
- B. 两张图的高度分别是 6 和 14
- C. 打包序列中第 0 张图占位置 `[0, 6)`，第 1 张图占 `[6, 14)`；varlen 注意力据此只在各段内部计算
- D. mask 中有 6 行和 14 列

**Q5.** 关于 Qwen2-VL 的 M-RoPE，下列说法正确的是：

- A. 它用一张固定大小的可学习位置表，超出范围时做双线性插值
- B. 每个 patch 带一个 3D 位置 `(t, row, col)`，通过旋转位置编码作用在 query/key 上，因此可直接处理任意 H、W 和视频长度
- C. 它把图像切成固定的 336×336 块再加缩略图
- D. 它只支持正方形图像

**Q6.** 关于 SigLIP 2 的 NaFlex，正确的是：

- A. 同一个 checkpoint 在推理时可以选择不同的序列长度（如 256、729、1024 token），语义任务用少的、OCR/图表用多的，无需重训
- B. 每种分辨率需要一个单独的 checkpoint
- C. 它不使用任何位置信息
- D. 它是 LLaVA-NeXT 的切块方法的别名

**Q7.** 代码对 5 张图的工作负载输出：

```text
TOTAL                          43229      2880          8064
native vs square :  15.01x tokens, preserves OCR + layout detail
```

而代码最后打印"native-pack (NaViT / NaFlex / M-RoPE): multi-aspect batch, maximum fidelity, minimum tokens"。下列理解正确的是：

- A. 原生打包在任何情况下 token 都最少
- B. square-resize 会产生最多的 token
- C. AnyRes 的 token 一定比原生多
- D. 不设上限时原生分辨率的 token 最多（本例是 square 的 15 倍）；打包省掉的是 **padding 的浪费**，而不是相对于缩小图像的 token 数。生产中要配合 `max_pixels` 上限，"minimum tokens"的说法不成立

**Q8.** 讲义练习 3：一张 1792×896 的图，patch 14。(a) resize 成 336 方形；(b) AnyRes 2×1 + 缩略图；(c) 原生分辨率（M-RoPE 式，不合并 patch）。三者的 token 数分别是：

- A. 576、1152、4096
- B. 196、1728、8192
- C. 576、1728、8192
- D. 576、2880、16384

---

## 三、动手 / 代码题

**Q9.** 阅读代码中工作负载的定义：

```python
@dataclass
class Image:
    name: str
    h: int
    w: int
...
    workload = [
        Image("receipt 600x1500 (1:2.5)", 600, 1500),
        Image("chart 1280x720 (16:9)", 1280, 720),
        Image("phone screen 1170x2532", 1170, 2532),
        Image("photo 2048x1536 (4:3)", 2048, 1536),
        Image("receipt 504x1260 (1:2.5)", 504, 1260),
    ]
```

1. 图像尺寸的惯例写法是"宽×高"。按这个惯例，收据和手机截图应当是竖的还是横的？代码实际把它们当成了什么方向？
2. 这个错位会影响 `native` 列吗？会影响 AnyRes 的哪一列？请给出修正方向后 receipt、chart、phone 的 AnyRes 网格。
3. 修正后 AnyRes 的总 token 数变了吗？为什么？

**Q10.** 阅读 `anyres_cost` 的网格选择：

```python
    if img.h <= tile and img.w <= tile:
        grid_r, grid_c = 1, 1
    else:
        best = None
        for gr in range(1, 4):
            for gc in range(1, 4):
                if gr * gc > 6:
                    continue
                ...
                score = abs(ratio - tile_ratio) + 0.1 * (gr + gc)
                ...
    tile_tokens = grid_r * grid_c * tile_grid * tile_grid
    thumb_tokens = thumb_grid * thumb_grid
```

1. 2048×1536 的照片被分到了 1×1 网格，总 token 1152。打分函数忽略了什么？这时"1 块 + 缩略图"有什么浪费？
2. 一张 336×336 的小图，`anyres_cost` 返回多少 token？与第 05 节代码 base 的 576 有何不同？
3. `if gr * gc > 6: continue` 实际排除了哪些网格？
4. 提出一个更合理的选择准则。

**Q11.** 稠密 mask 与 `cu_seqlens`。

1. 如果对本节 5 张图的工作负载（原生共 43,229 个 token）构造稠密 mask，有多少个元素？分别以 1 字节布尔和 4 字节 float32 存储需要多少内存？代码为什么只对玩具示例调用 `build_dense_mask`？
2. 讲义 NaViT 步骤 5 要求"每个 patch 携带位置信息"，但 `pack_batch` 只返回长度。写一个 `pack_with_positions(images, patch, keep=1.0)`，返回每个 token 的 `(row, col)`、所属图像 id 和 `cu_seqlens`，并支持按比例随机丢弃 patch（讲义练习 4）。
3. 用长度 256、576、729、1024 的四张图测试：`keep = 0.5` 时 mask 的非零比例怎么变化？非零元素的绝对数量怎么变化？

**Q12.** 给原生分辨率加上 `max_pixels` 上限。写一个函数：给定 `(H, W)`、patch 14 和 token 上限 1024，在**保持长宽比**的前提下缩放，使 token 数不超过上限。用修正方向后的 5 张图计算结果，并回答：为什么讲义说 `min_pixels` 和 `max_pixels` 两个边界都重要？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 Patch-n'-Pack？它解决了什么问题？块对角 mask 如何构造，生产中为什么用 `cu_seqlens`？

**Q14.**（原理深挖）比较 AnyRes、NaFlex、M-RoPE 三种任意分辨率方案：各自的前提条件、token 开销、优缺点和适用场景。

**Q15.**（原理深挖）ViT 原本用固定大小的可学习位置表。要支持任意分辨率，位置编码可以怎么做？为什么 RoPE 类方法更容易处理可变尺寸？

**Q16.**（场景设计）你要为一个"拍照报销 + 图表分析 + 商品照片"三合一的应用设计视觉 token 预算，LLM 上下文 32k。请给出每类图片的策略、token 上限和批处理方案。

**Q17.**（工程实践）在训练中使用 packing（多张图拼进一条序列），除了注意力 mask，还有哪些地方必须"按图像"处理？如果漏掉会出现什么 bug？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义学习目标："Name the three failure modes of square-resize: squished text, cropped content, wasted tokens on padding." 对应 The Problem 中的三种旧做法：resize（挤压变形、缩小后看不清图表标签）、crop（丢掉大部分图像）、pad 到最长边（"wastes 50%+ of tokens on padding for portrait images"）。其它选项都不是讲义的分类。

### Q2 — 答案：D

`336/14 = 24 → 576`，`224/14 = 16 → 256`，`448×336 → 32 × 24 = 768`，合计 1600（已计算）。讲义："becomes one 1600-token sequence with a 1600x1600 block-diagonal mask. No padding." A 是 pad 方案；B 是 resize 方案；C 的因果 mask 是语言模型用的，视觉 encoder 内部是双向注意力，只需隔离不同图像。

### Q3 — 答案：A

总长 `256 + 576 + 729 + 1024 = 2585`，mask 共 `2585² = 6,682,225` 个元素；非零元素 `256² + 576² + 729² + 1024² = 65,536 + 331,776 + 531,441 + 1,048,576 = 1,977,329`，占 `29.6%`（已用 Python 计算）。也就是说稠密 mask 中超过 70% 的计算是被屏蔽掉的"无用功"，这正是 varlen 路径快的原因。

### Q4 — 答案：C

`cu_seqlens` 是累积长度（cumulative sequence lengths）：`[0, n_0, n_0 + n_1]`。玩具示例中图 A 为 6 个 token、图 B 为 8 个 token，所以是 `[0, 6, 14]`。A 把累积值误当成每段长度（图 B 是 `14 − 6 = 8`）。代码中 `build_dense_mask` 正是用 `cu_seqlens[b]` 和 `cu_seqlens[b+1]` 作为每块的上下界。

### Q5 — 答案：B

讲义："each patch carries a 3D position (temporal, height, width). The query/key rotations handle arbitrary H, W, and temporal length." 以及 "no position tables"。A 描述的是传统 ViT 位置表插值；C 是 AnyRes；D 错。

### Q6 — 答案：A

讲义："A single model serves multiple sequence lengths (256, 729, 1024 tokens) at inference ... one checkpoint, pick your token budget at inference based on the task. For a semantic task ... 256 tokens. For OCR or chart understanding, 1024 tokens. No retraining." C 错：NaFlex 使用"absolute fractional positions per patch"。

### Q7 — 答案：D

原生 43,229 个 token，是 square（2,880）的 15.01 倍、AnyRes（8,064）的 5.36 倍。打包的价值在于：不同长宽比的图像不必 pad 到同一长度，计算不浪费在填充上；它并不减少相对于"缩小图像"的 token 数。代码中 "native vs anyres: 5.36x tokens, no tile + thumbnail blow-up" 和 "minimum tokens" 的措辞都与数字矛盾；讲义 Use It 说"The numbers that drop out are the reason every 2026 open VLM uses patch-n'-pack"，但这组数字恰恰说明：**不加 `max_pixels` 上限的原生分辨率不可用**（一张 2048×1536 照片就要 15,914 个 token）。讲义 Token budgets 一节和生产规则才是完整答案：设上限 + 原生长宽比 + 打包。

### Q8 — 答案：C

- (a) `(336/14)² = 576`；
- (b) 2×1 网格 2 块 + 缩略图 1 块：`3 × 576 = 1,728`；
- (c) `1792/14 = 128`，`896/14 = 64`，`128 × 64 = 8,192`（已计算）。

token 最少的是 (a)，保留细节最多的是 (c)。(b) 是中间方案：每块的有效分辨率相当于原图缩小到 672×336（缩小约 2.7 倍），比 (a) 的 336×336 清晰得多。补充：按笔者对 Qwen2-VL 论文的理解，它在 ViT 之后会把相邻 2×2 个 patch 合并成一个 token，实际送入 LLM 的数量约为 `8192 / 4 = 2048`——讲义写的是"H/14 x W/14 tokens"，阅读原论文时可核对这一细节。

### Q9 — 参考答案

1. 按"宽×高"惯例：收据 600×1500 是**竖的**（高 1500），手机截图 1170×2532 也是**竖的**（讲义："Mobile device screenshots are 1170x2532 (0.46:1)"）；图表 1280×720 是横的（16:9），照片 2048×1536 是横的（4:3）。但构造函数是 `Image(name, h, w)`，代码把 600 当高、1500 当宽，于是收据和手机截图变成了**横的**，图表和照片变成了**竖的**——四张图方向全部反了。
2. `native` 列是 `(h//14) × (w//14)`，交换 h 和 w 后乘积不变（本例中向下取整的结果也相同），不受影响。受影响的是 AnyRes 的 **grid** 列：原输出 receipt 1×2、chart 2×1、phone 1×2；按正确方向（已运行验证）应为 receipt 2×1、chart 1×2、phone 2×1，照片仍为 1×1。
3. 总数不变，仍为 8,064。因为打分函数只依赖长宽比，交换方向后网格也跟着转置，块数相同。但在真实系统中网格方向至关重要：方向反了，每块图像要被拉伸近 6 倍（例如 2.5:1 被塞进 1:2 的布局），文字严重变形——这正是本节要避免的"squished text"。

### Q10 — 参考答案

1. 打分 `|ratio − tile_ratio| + 0.1·(gr + gc)` **只看长宽比，不看图像有多大**。2048×1536 的长宽比约 1.33：1×1 得分 `0.33 + 0.2 = 0.53`，2×2 得分 `0.33 + 0.4 = 0.73`，于是选了 1×1。结果是一张 300 万像素的照片被缩到 336×336，再加一张同样是"整图缩到 336×336"的缩略图——两份 576 token 内容几乎相同，白白多花了 576 个 token。
2. 进入 `if` 分支，网格 1×1，但 `thumb_tokens` 仍然被加上，返回 **1,152**（已运行验证）。第 05 节代码的 base（336×336）是 576、不加缩略图。小图不应该再加缩略图。
3. `gr` 和 `gc` 都在 1～3 之间，乘积大于 6 的只有 3×3 = 9。所以这一行只排除了 3×3；而讲义 Token budgets 一节恰恰提到"AnyRes 3x3 + thumbnail"用于 OCR。
4. 更合理的准则（与 LLaVA-NeXT 的思路一致）：在允许的网格集合中，选择使"原图缩放后能保留的有效像素"最大、同时浪费（填充）最少的网格；分辨率不超过单块时不切块、不加缩略图；并给总 token 设置上限。

### Q11 — 参考答案

1. `43,229² = 1,868,746,441`，约 18.7 亿个元素。1 字节布尔约 1.87 GB，float32 约 7.5 GB；如果像 `build_dense_mask` 那样用 Python 的 `list[list[int]]`，每个元素是一个对象引用（8 字节指针），仅指针就要约 15 GB，而且双重循环需要数十亿次迭代。所以代码只对 14 个 token 的玩具示例构造稠密 mask。生产中用 `cu_seqlens`，只需 `B + 1` 个整数。
2. 参考实现（已实际运行）：

```python
import random
from main import Image

def pack_with_positions(images, patch, keep=1.0, seed=0):
    rng = random.Random(seed)
    pos_ids, seg_ids, cu = [], [], [0]
    for b, img in enumerate(images):
        gh, gw = img.grid(patch)
        cells = [(r, c) for r in range(gh) for c in range(gw)]
        if keep < 1.0:
            k = max(1, round(len(cells) * keep))
            cells = sorted(rng.sample(cells, k))     # 保留原来的二维坐标
        pos_ids += cells
        seg_ids += [b] * len(cells)
        cu.append(cu[-1] + len(cells))
    return pos_ids, seg_ids, cu
```

   关键点：丢弃 patch 时**保留被留下 patch 的原始 `(row, col)`**，而不是重新编号，否则位置信息就错了；`seg_ids` 可用来构造 mask 或做每张图的池化。
3. 测试 224/336/378/448（对应 256/576/729/1024 个 token）：
   - `keep = 1.0`：`cu_seqlens = [0, 256, 832, 1561, 2585]`，非零比例 0.2959；
   - `keep = 0.5`：`cu_seqlens = [0, 128, 416, 780, 1292]`，非零比例仍为 0.2959。

   每张图按同一比例丢弃时，`Σ n_i² / N²` 不变（每项都乘以 1/4，分母也乘以 1/4），所以**比例不变**；但非零元素的**绝对数量**降到约 1/4（从 1,977,329 降到约 49 万），注意力计算量也随之降到约 1/4——这就是 token dropping 能加速训练的原因。若改为"整个 batch 一起均匀随机丢弃"，各图实际保留数会有波动，比例会小幅变化。

### Q12 — 参考答案

```python
import math

def capped(h, w, cap=1024, p=14):
    s = min(1.0, math.sqrt(cap * p * p / (h * w)))   # 只缩小、不放大
    gh = max(1, int(h * s) // p)
    gw = max(1, int(w * s) // p)
    return gh, gw, gh * gw
```

修正方向后（高×宽）的结果（已运行）：receipt `50 × 20 = 1000`、chart `24 × 42 = 1008`、phone `47 × 21 = 987`、photo `27 × 36 = 972`、receipt2 `50 × 20 = 1000`。合计约 4,967 个 token，比不设上限的 43,229 少约 89%，且保持了各自的长宽比。

两个边界都重要：
- `max_pixels` 防止超大图像（如 4096×4096 的医学影像或 2532 像素高的截图）产生上万个 token，撑爆上下文和延迟预算；
- `min_pixels` 防止极小图像（如 50×50 的图标）只得到一两个 token，视觉信息不足以让模型理解，此时应适度放大到一个最小 token 数。

讲义练习 5 要求阅读 Qwen2-VL 论文中的相关描述加以验证。

### Q13 — 参考回答要点

- **问题**：Transformer 的 batch 要求等长序列；不同分辨率、长宽比的图像要么 resize（失真、丢细节），要么 pad（浪费计算）。
- **Patch-n'-Pack**：每张图按原生网格切 patch，展平后**拼接**成一条长序列；用块对角 mask 保证图像之间互不注意；每个 patch 带自己的二维位置（2D RoPE 或分数位置）。讲义示例：576 + 256 + 768 = 1600 个 token、1600×1600 的块对角 mask。
- **mask 构造**：`offsets = [0, n_0, n_0+n_1, ...]`；`M[i, j] = 1` 当且仅当 i、j 落在同一个 `[offsets[b], offsets[b+1])` 区间。PyTorch 可用 `torch.block_diag` 构造。
- **为什么用 `cu_seqlens`**：稠密 mask 是 `O(N²)` 内存，且约 70% 是屏蔽位置（Q3）；FlashAttention 的 varlen 接口直接按累积长度在各段内计算，不分配 mask、不做无用计算，讲义称约快 10 倍。
- 加分点：NaViT 训练时还会随机丢弃 patch，进一步提速并起正则化作用。

### Q14 — 参考回答要点

| | AnyRes（LLaVA-NeXT） | NaFlex（SigLIP 2） | M-RoPE（Qwen2-VL） |
|---|---|---|---|
| 前提 | encoder 冻结在固定分辨率（如 336） | encoder 用 NaViT 式打包训练 | encoder 与 LLM 使用 RoPE 类位置编码 |
| 做法 | 选网格切块 + 缩略图，每块独立编码 | 原生长宽比，推理时选择 256/729/1024 的 token 预算 | 原生分辨率，每个 patch 带 `(t, row, col)` 位置 |
| token 开销 | `(块数 + 1) × 576`，乘法增长 | 由预算决定，可控 | 随面积增长，需 `max_pixels` 上限 |
| 优点 | 不用改 encoder，局部细节 + 全局上下文 | 一个 checkpoint 适配多种任务 | 天然支持任意尺寸和视频时间维 |
| 缺点 | 块边界切断物体；大图 token 爆炸 | 需要重新训练 encoder | 需要配套的打包与上限策略 |

- 讲义选型：encoder 冻结只支持单一分辨率时用 AnyRes；混合工作负载用 SigLIP 2 NaFlex；Agent UI 截图等用 Qwen2.5-VL 原生动态分辨率（技能文件 Encoder recommendation）。
- 常见误区：技能文件："Treating AnyRes as the universal answer — its multiplicative tile overhead can exceed the LLM context before one image finishes encoding."

### Q15 — 参考回答要点

- **固定位置表 + 插值**：原始 ViT 为 `(H/P) × (W/P)` 个位置学一张表；分辨率变化时对表做二维插值。简单，但插值后的位置向量是训练中没见过的，分辨率差别大时效果下降。
- **分数位置（fractional positions）**：把位置归一化到 `[0, 1]`（例如 `row / gh`），无论图像多大，坐标都在同一范围内，再查表或用连续函数编码。讲义：NaFlex 使用 "absolute fractional positions per patch"。
- **2D / 3D RoPE（M-RoPE）**：把 query/key 的不同维度分组，分别按行号、列号（以及时间）旋转。注意力分数只依赖**相对**位移，不依赖绝对表长，所以任何 H、W 都能直接计算，不需要插值；时间维度同样适用于视频。
- **为什么 RoPE 更易处理可变尺寸**：没有"表长度"这个硬上限，位置是通过旋转角度连续定义的；而且相对位置的性质在不同分辨率间更一致。
- 加分点：打包时每张图的位置 id 必须**从 0 重新开始**（Q17）。

### Q16 — 参考回答要点

- **报销单据（OCR）**：竖长、文字小，按原生长宽比编码，`max_pixels` 对应约 1024–2048 token（讲义 OCR 1024–4096）；或用 SigLIP 2 NaFlex 1024 档。禁止 square-resize（技能文件："Recommending square-resize for OCR or chart tasks without citing which benchmark number the user will lose" 属于硬性拒绝）。
- **图表**：讲义建议 729–1024 token，用 Qwen2.5-VL 式动态分辨率并设 `max_pixels`。
- **商品照片**：256–576 token 足够，语义任务不必花高分辨率。
- **预算校验**：32k 上下文中，单张图不超过 40%（技能文件："Flag if any single image exceeds 40% of the LLM context"），即约 13k token；一次请求若含多张图，总和也要留出文本空间。
- **批处理**：请求间长宽比差异大（超过 2 倍），用 FlashAttention varlen + `cu_seqlens` 打包；不要 pad。
- **监控**：每张图 token 数分布、prefill 延迟、OCR 字段准确率。

### Q17 — 参考回答要点

- **位置 id**：每张图的 `(row, col)` 要从 0 开始重新编号；若沿用打包序列的全局下标，第二张图的位置就会接在第一张后面，模型以为它们是同一张大图。
- **注意力 mask / `cu_seqlens`**：必须与实际打包顺序一致；丢弃 patch 后要同步更新（Q11）。
- **池化与输出拆分**：做分类或对比学习时，需要按 `seg_ids` 对每张图分别池化；送入 LLM 时要按 `cu_seqlens` 把视觉 token 切回各自的样本。
- **loss 归一化**：若按 token 平均 loss，大图会主导梯度；需要决定按图像还是按 token 归一化。
- **负载均衡**：多卡训练时，每张卡上打包的总 token 数应接近，否则快卡等慢卡。
- **漏掉的后果**：图像间信息泄露（mask 错误）、位置混乱（位置 id 未重置）、样本错位（拆分错误）——通常不会报错，只会让指标莫名变差，所以要写单元测试：例如验证 mask 非零数等于 `Σ n_i²`，打乱 batch 顺序后每张图的输出不变。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 01 Vision Transformers 与 Patch-Token 基本单元](../../01-vision-transformer-patch-tokens/docs/zh.md)：patch 网格与 token 数的计算基础。
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：AnyRes 与 576 token/图的由来。
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../02-clip-contrastive-pretraining/docs/zh.md)：SigLIP / SigLIP 2 的训练目标。
- [阶段 07 · 04 位置编码 — 正弦、RoPE、ALiBi](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：RoPE 的原理，是理解 M-RoPE 的前提。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：FlashAttention 与 varlen 接口。

### 本节被哪些后续内容用到
- [阶段 12 · 09 Qwen-VL 系列与动态帧率视频](../../09-qwen-vl-family-dynamic-fps/docs/zh.md)：M-RoPE 与动态分辨率在视频上的扩展。
- [阶段 12 · 10 InternVL3：原生多模态 Pretraining](../../10-internvl3-native-multimodal/docs/zh.md)：讲义提到的 V2PE。
- [阶段 12 · 17 视频语言模型：时间 Tokens 与 Grounding](../../17-video-language-temporal-grounding/docs/zh.md)：视频每帧的 token 预算。
- [阶段 12 · 22 文档与图解理解](../../22-document-diagram-understanding/docs/zh.md)：高分辨率 OCR 场景。
- [阶段 12 · 25 多模态 Agents 与计算机操作（综合项目）](../../25-multimodal-agents-computer-use/docs/zh.md)：UI 截图的分辨率处理。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：生产推理中的变长序列批处理。

### 延伸关键词
`NaViT` · `Patch-n'-Pack` · `block-diagonal mask` · `cu_seqlens / varlen attention` · `token dropping` · `AnyRes` · `NaFlex` · `M-RoPE` · `2D RoPE` · `fractional positions` · `min_pixels / max_pixels` · `visual token budget` · `sequence packing`
