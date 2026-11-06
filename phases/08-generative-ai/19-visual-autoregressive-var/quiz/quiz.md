# 测验 · 视觉 Autoregressive 建模（VAR）：下一尺度预测（Visual Autoregressive Modeling (VAR): Next-Scale Prediction）

> **阶段 08 · 生成式 AI · 第 19 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 光栅顺序 AR 的"生成顺序问题" | PixelCNN、DALL-E 1、Parti 把 2D 网格压成 1D 光栅顺序，早期 token 在不知道全图的情况下就要"表态" |
| 2 | 下一尺度预测（next-scale prediction） | 不再逐 token 生成，而是按分辨率逐级生成：1×1 → 2×2 → … → 最终网格，每一级以之前所有级为条件 |
| 3 | 多尺度残差 VQ tokenizer | `f ≈ Σ_k upsample(embed(z_k))`：第 k 级编码前 k−1 级没表达出的残差；解码器把各级嵌入上采样求和；训练一次后冻结 |
| 4 | 尺度内并行、尺度间因果 | 第 k 级的所有 token 在一次前向中并行预测；注意力按尺度做块因果（block-causal）mask，看得到 1..k 级、看不到 k+1..K 级 |
| 5 | 前向次数 vs 序列长度 | 前向次数 = 尺度数 K（如 256² 时约 10 次，DiT 需 28–50 步）；但总 token 数是 `Σ s_k²`，代码的 (1,2,4,8) 共 85 个 |
| 6 | 位置编码 | `(scale, row, col)` 三元组：同一个 (row, col) 在不同尺度含义不同，模型必须知道"第几级、哪个位置" |
| 7 | 训练目标 | 与 GPT 相同的交叉熵，只是"序列"按尺度组织：给定真实的前 k−1 级 token，预测第 k 级的离散码 |
| 8 | 尺度内条件独立假设 | 并行采样意味着同一尺度内各位置在给定前面尺度时独立采样；粗尺度已定下结构，所以这个近似可以接受 |
| 9 | 缩放律 | 讲义：VAR 的 ImageNet FID 随算力呈幂律下降，像 GPT 的困惑度一样可预测 |
| 10 | 与扩散的关系 | 都把生成拆成一串更容易的条件子问题：扩散沿"噪声 / 时间"轴，VAR 沿"分辨率"轴；文本条件版本有 VAR-CLIP、HART 等 |

### 核心技能（能动手做到）

- [ ] 能用 NumPy 实现多尺度残差量化：平均池化下采样、最近邻上采样、逐级减残差，并验证"各级上采样求和 ≈ 原图"
- [ ] 能算出任意尺度表的前向次数、总 token 数和每级的可见上下文长度（如 (1,2,4,8) → 4 次、85 个 token、0/1/5/21 个前序 token）
- [ ] 能写出 `block_causal_mask(scales)`，并验证每一行可见的 token 数
- [ ] 能解释代码中直方图预测器为什么在细尺度上大量退化成均匀分布，并给出改进
- [ ] 能分析 tokenizer：逐级累加的重建误差、码本中重复 / 死码的现象
- [ ] 能从任务需求（分辨率、算力、FID 目标）出发设计尺度表、码本大小与位置编码，并说清每个选择的理由

---

## 二、基础自测（选择题）

**Q1.** VAR 相比 VQGAN + GPT 这类"光栅顺序逐 token"生成，主要解决的问题是：

- A. 码本太小，表达力不够
- B. 2D 网格被强行排成 1D 顺序，早期 token 在没有全局上下文时就必须确定
- C. 扩散模型采样步数太多
- D. 离散 token 无法用交叉熵训练

**Q2.** 按本节代码的尺度表 `SCALES = (1, 2, 4, 8)`，生成一张图需要多少次 transformer 前向？序列总共多少个 token？

- A. 4 次，85 个
- B. 85 次，85 个
- C. 4 次，64 个
- D. 8 次，64 个

**Q3.** 关于多尺度残差 VQ，下列说法正确的是：

- A. 每一级对原始特征 `f` 的下采样版本各自独立量化，互不相关
- B. 第 k 级量化的是前 k−1 级重建后剩下的残差，解码器把各级嵌入上采样后求和
- C. 只有最后一级的 token 参与解码，前面各级只用于训练
- D. 每一级必须配一个独立的解码器网络

**Q4.** 在 VAR 的块因果注意力里，第 k 级的 token 可以关注：

- A. 只有第 k 级自身的 token
- B. 第 1..k 级的 token（前面各级 + 本级），不能关注第 k+1..K 级
- C. 所有尺度的全部 token
- D. 只有紧挨着的第 k−1 级

**Q5.** VAR 在同一尺度内并行采样所有位置。这隐含的假设是：

- A. 同一尺度内各位置的 token 完全相同
- B. 给定之前所有尺度后，同一尺度内各位置条件独立
- C. 同一尺度的 token 与之前的尺度无关
- D. 同一尺度内仍按光栅顺序逐个生成

**Q6.** 为什么 VAR 的位置编码要包含 `(scale, row, col)` 而不是一个扁平的 1D 序号？

- A. 为了减少参数量
- B. 同一个 (row, col) 在不同尺度对应完全不同的空间范围和语义，模型必须知道它在第几级
- C. 为了支持文本条件
- D. 只有解码器才需要位置信息

**Q7.** 关于 VAR 与扩散模型的比较，下列说法**错误**的是：

- A. 扩散沿噪声 / 时间轴拆分问题，VAR 沿分辨率轴拆分问题
- B. 讲义称 256×256 时 VAR 约 10 次前向，而 DiT 需要 28–50 步
- C. VAR 不需要 tokenizer，直接在像素空间逐级预测连续值
- D. 两者都把一个难的生成问题拆成一串更容易的条件分布

**Q8.** skill 文件为 ImageNet 256×256 给出的尺度表是 `1, 2, 3, 4, 5, 6, 8, 10, 13, 16`。这个尺度表对应的总 token 数是：

- A. 671
- B. 680
- C. 256
- D. 1024

---

## 三、动手 / 代码题

**Q9.** `main.py` 末尾有一段"注意力检查"：

```python
print("scale-ordered attention check: every scale k only sees scales 1..k-1")
for k, scale in enumerate(SCALES):
    n_pos = scale * scale
    prior_seen = sum(s * s for s in SCALES[:k])
    print(f"  scale {k} (size {scale}x{scale}, {n_pos} tokens):"
          f" attends to {prior_seen} prior tokens")
```

(a) 写出它打印的 4 行；(b) 这段代码真的"检查"了注意力 mask 吗？标题里的 "1..k-1" 和循环里的 `scale {k}` 有什么不一致？(c) 用 NumPy 写一个 `block_causal_mask(scales)`，返回 `(T, T)` 的布尔矩阵（`True` 表示可以 attend），并说明对 (1,2,4,8) 每一级第一行有多少个 `True`。

**Q10.** 阅读残差 tokenizer：

```python
def tokenize_multiscale(img, codebooks):
    residual = img.copy()
    tokens = []
    for scale, book in zip(SCALES, codebooks):
        coarse = downsample(residual, scale)
        tok = encode(coarse, book)
        recon = book[tok]
        residual = residual - upsample(recon, IMG)
        tokens.append(tok)
    return tokens
```

(a) 对 `make_patterns` 里的棋盘格图案（`kind == 3`，像素在 0 和 1 之间交替），前三级（1×1、2×2、4×4）下采样后各看到什么？信息是在哪一级被编码的？(b) 程序打印训练集重建 MSE 为 0.00029。我额外统计了"只用前 K 级重建"的 MSE：K=1、2、3、4 时分别约为 0.112、0.100、0.079、0.00029。这说明了什么？低重建误差能证明"多尺度结构有用"吗？

**Q11.** 程序的生成部分只打印了形状和数值范围：

```text
  trial 0: scales=[(1, 1), (2, 2), (4, 4), (8, 8)]  range=[-0.43, 1.17]
```

已知训练图案的像素都在 [0, 1] 内。结合下面两个函数，解释生成质量为什么很差：

```python
def context_key(prev_tokens):
    return tuple(int(t.mean() * 1000) for t in prev_tokens) if prev_tokens else ()

# generate() 中：
        probs = table.get(ctx)
        if probs is None:
            probs = np.ones(CODEBOOK) / CODEBOOK
        size = scale * scale
        flat = np.array([sample_categorical(probs, rng) for _ in range(size)], dtype=np.int32)
```

（提示：我统计了 300 次生成中各尺度走到 `probs is None` 分支的比例：1×1 为 0%，2×2 约 10%，4×4 约 86%，8×8 约 97%。）

**Q12.** 在 Q11 的基础上，改写 `fit_predictor` 与 `generate`，让预测器**按位置**给出分布，并以**全部前序 token**作为上下文（不加拉普拉斯平滑）。给出代码并讨论：效果会怎样变化？这种"查表"方案的根本局限是什么，真实 VAR 用什么替代它？

---

## 四、面试高频题

**Q13.**（基础必考）请解释 VAR 的"下一尺度预测"，它和 VQGAN / DALL-E 1 这种光栅顺序的"下一 token 预测"有什么本质区别？推理成本怎么算？

**Q14.**（原理深挖）VAR 的多尺度 tokenizer 为什么必须是**残差**的？如果每一级独立地量化 `f` 的下采样版本，会出什么问题？码本应该共享还是分级？

**Q15.**（追问型）"同一尺度内并行采样"会不会出问题？什么情况下这个近似最差？VAR 的设计如何缓解？

**Q16.**（工程实践）对比 VAR 与 DiT 在 256×256 上的推理计算量：前向次数、每次处理的 token 数、能否用 KV cache。为什么 VAR 推理更快？

**Q17.**（场景设计）团队要做一个文生图产品，在"VAR 类（离散、下一尺度）"和"DiT + flow matching（连续）"之间选型。你会考虑哪些因素？如果选 VAR，要怎么加文本条件？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义 The Problem 一节：像素和 token 在 2D 网格里，但 AR 模型必须按 1D 光栅顺序访问，左上角的 token 生成时完全不知道全图会变成什么。VAR 通过改变"生成什么"来解决：每一步生成一整张更高分辨率的 token 图。A、C、D 都不是 VAR 的动机——VAR 本身仍用离散码本和交叉熵。

### Q2 — 答案：A

每个尺度一次前向，共 4 次；总 token 数 `1 + 4 + 16 + 64 = 85`。C 只数了最后一级；B 是逐 token AR 的情形。注意"前向次数少"不等于"序列短"：VAR 的序列比只看最后一级要长（这里 85 vs 64），注意力的计算量按总长度算。

### Q3 — 答案：B

讲义：各级"不是独立的"，训练目标是各级残差之和重建 `f`；第 k 级捕捉前 k−1 级遗漏的部分。代码 `tokenize_multiscale` 中 `residual = residual - upsample(recon, IMG)` 正是这一步，`detokenize_multiscale` 把各级 `upsample(book[tok], IMG)` 相加。A 描述的是非残差方案（skill 文件明确拒绝）；C、D 都与"解码器对所有尺度之和解码"矛盾。

### Q4 — 答案：B

讲义关键术语 "Causal-across-scales"：第 k 级可以关注 1..k 级，但不能关注 k+1..K 级。同级之间不做因果遮挡（讲义："no intra-scale causality"），所以 mask 是"块下三角"。D 只看上一级会丢掉更粗尺度的全局信息。

### Q5 — 答案：B

并行采样等价于把 `p(z_k | z_<k)` 分解为各位置的乘积 `Π p(z_k[i,j] | z_<k)`，即给定前面所有尺度后同级位置条件独立。它是近似：如果同一尺度上两个位置需要"协调"（比如二选一的对称结构），独立采样可能产生互相矛盾的组合。粗到细的设计让大部分结构在更粗的尺度上已经确定，从而降低这种风险。

### Q6 — 答案：B

尺度 2 的 (0,0) 覆盖图像左上的四分之一，尺度 8 的 (0,0) 只覆盖一个小块。只给扁平序号，模型就得自己从序号推出"这是第几级的哪个位置"。讲义术语表和 skill 文件都要求 `(scale, row, col)` 三元组，skill 文件还明确拒绝扁平 1D 位置："LM 需要尺度标签才能应用正确的条件分布"。

### Q7 — 答案：C

VAR 离不开 tokenizer：它在多尺度 VQ 的**离散码**上做交叉熵预测，最后由 VAE 解码器把各级嵌入之和变成图像。A、B、D 都是讲义 Relationship to Diffusion 一节的原意。

### Q8 — 答案：B

`1 + 4 + 9 + 16 + 25 + 36 + 64 + 100 + 169 + 256 = 680`。⚠️ skill 文件示例输出写的是 "Total tokens 671"，这是算术错误，应为 680。这道题也提醒：尺度表不是严格的 2 倍递增，VAR 实际用的是这种更密的尺度序列，序列长度比"最后一级 256 个 token"多出约 1.65 倍。

### Q9 — 参考答案

(a) 输出：

```text
  scale 0 (size 1x1, 1 tokens): attends to 0 prior tokens
  scale 1 (size 2x2, 4 tokens): attends to 1 prior tokens
  scale 2 (size 4x4, 16 tokens): attends to 5 prior tokens
  scale 3 (size 8x8, 64 tokens): attends to 21 prior tokens
```

(b) 没有检查任何 mask——它只是按公式算了"前面各级的 token 总数"并打印，结果必然正确。真正的检查应该构造 mask（或者从模型中取出注意力权重），验证跨尺度可见、未来尺度不可见。另外标题用 1 起始的 "scales 1..k-1"，循环打印却是 0 起始的 `scale 0..3`，两种编号混用，容易让人误读（打印的 `scale k` 其实对应标题里的第 k+1 级）。

(c) 参考实现（已运行验证）：

```python
import numpy as np

def block_causal_mask(scales):
    sizes = [s * s for s in scales]
    scale_id = np.repeat(np.arange(len(scales)), sizes)   # 每个 token 属于第几级
    return scale_id[:, None] >= scale_id[None, :]         # 行 = query，列 = key；True = 可以 attend

mask = block_causal_mask((1, 2, 4, 8))
print(mask.shape)                          # (85, 85)
print(mask.sum(axis=1)[[0, 1, 5, 21]])     # [ 1  5 21 85]
```

每一级第一个 token 可见的数量分别是 1、5、21、85——等于"前面各级 + 本级全部"。与 (a) 中 0、1、5、21 的差别正好是本级 token 数：(a) 统计的是"条件里有多少前序 token"，mask 则还允许同级互相看（尺度内无因果）。

### Q10 — 参考答案

(a) 棋盘格每个 2×2 块都是两个 0 两个 1，平均为 0.5。所以下采样到 1×1、2×2、4×4 后**每个格子都是 0.5**——三个粗尺度只能编码"整体亮度 0.5"，看不到任何纹理。所有信息（±0.5 的交替残差）都在最后的 8×8 级才被编码。实际训练出的 8×8 码本里正好有 −0.534、−0.492、0.466、0.5 这些接近 ±0.5 的码字，用于表达它。这说明高频细节只能在细尺度表达——也是"粗到细"自然对应"低频到高频"的直观例子。

(b) 几乎所有重建精度都来自最后一级：前三级合起来 MSE 仍有 0.079，加上 8×8 一级后降到 0.00029。原因是本代码的最后一级就是**全分辨率、逐像素的标量量化**（16 个码字量化一个残差值），它几乎可以修补任何前面没做好的部分。所以低重建误差只说明"最细一级足够细"，**不能**证明粗尺度学到了有用的结构。真实 VAR 的最后一级是 `H/p × W/p`（远小于像素数），每个 token 还要经过解码器，粗尺度的质量才真正重要。评估多尺度 tokenizer 时，应该看"逐级累加"的重建曲线，而不是只看最终值。

### Q11 — 参考答案

三个原因叠加：

1. **上下文键太细、几乎不泛化**。`context_key` 把每一个前序尺度压成"平均 token 序号 ×1000 取整"。训练集只有 64 张图，第 3、4 级见过的上下文分别只有 11、12 种。生成时前面各级是采样出来的，组合出的平均序号几乎总是训练中没见过的值，于是 `table.get(ctx)` 返回 `None`，退回到 16 个码字的**均匀分布**——4×4 级约 86%、8×8 级约 97% 的生成走了这个分支。按 token 数加权，一张 85 token 的图里约 76 个 token 是纯随机的。
2. **同一尺度共用一个与位置无关的分布**。即使上下文命中，`flat` 也是对同一个 `probs` 独立采样 `size` 次，每个位置的分布完全一样，无法生成"中间亮、四周暗"之类的空间结构。真实 VAR 的 transformer 对每个位置输出各自的 logits。
3. **拉普拉斯平滑把概率分给了没见过的码字**：`fit_predictor` 用 `np.ones(CODEBOOK)` 初始化计数，样本少时平滑项占比很大，采样容易抽到训练中从未出现的码字，进一步制造没见过的上下文。

结果就是输出范围 [−0.43, 1.17] 远超 [0, 1]。我另外统计过：生成图与最近训练图的平均 MSE 约 0.10，而验证集图像与最近训练图只有约 0.00016。演示只打印形状和范围，掩盖了这个问题——又一次说明"生成模型必须做分布级评估"（第 14 节）。

### Q12 — 参考答案

```python
def full_ctx(prev):
    return tuple(int(x) for t in prev for x in t.reshape(-1))   # 全部前序 token 原样拼起来


def fit_predictor_pos(token_streams, smoothing=0.0):
    preds = [dict() for _ in SCALES]
    for stream in token_streams:
        for k, s in enumerate(SCALES):
            ctx = full_ctx(stream[:k])
            for i in range(s):
                for j in range(s):
                    table = preds[k].setdefault((ctx, i, j), np.full(CODEBOOK, smoothing))
                    table[int(stream[k][i, j])] += 1.0
    for table in preds:
        for key in table:
            table[key] = table[key] / table[key].sum()
    return preds


def generate_pos(preds, codebooks, rng):
    drawn = []
    for k, s in enumerate(SCALES):
        ctx = full_ctx(drawn)                       # 只依赖已生成的前序尺度
        grid = np.zeros((s, s), dtype=np.int32)
        for i in range(s):                          # 这两层循环彼此独立 → 可以并行
            for j in range(s):
                p = preds[k].get((ctx, i, j))
                if p is None:
                    p = np.ones(CODEBOOK) / CODEBOOK
                grid[i, j] = sample_categorical(p, rng)
        drawn.append(grid)
    return detokenize_multiscale(drawn, codebooks), drawn
```

我用相同数据（种子 0、64 张训练图）跑了 300 次：生成图与最近训练图的平均 MSE 从原版的约 0.10 降到约 0.0086；每张图退回均匀分布的 token 数从约 76 个降到约 7 个。剩下的退化来自**尺度内条件独立**：同一上下文下若训练集有几张不同的图，各位置独立采样可能拼出训练中不存在的组合，下一级的上下文就又没见过了。

局限：这是一个**查表记忆器**——上下文必须精确命中训练样本才有用，本质上是在复刻训练集，没有泛化能力；上下文空间随尺度指数爆炸。真实 VAR 用 transformer 代替查表：用 `(scale, row, col)` 位置编码 + 块因果注意力把任意前序 token 映射成每个位置的 logits，在没见过的上下文上也能给出合理分布。这正是 docstring 里说的 "A real VAR swaps the histogram for a transformer... the harness around them stays the same"。

### Q13 — 参考回答要点

- **定义**：VAR 把图像表示为 K 级从粗到细的 token 图（多尺度残差 VQ），自回归的单位是"一整级"：`p(z_1, …, z_K) = Π_k p(z_k | z_1, …, z_{k−1})`，每一级内所有位置并行预测。
- **与光栅 AR 的区别**：①顺序：光栅 AR 的早期 token 只看到"左边和上面"，VAR 每一级都看到整张更粗的图，没有方向偏置；②粒度：光栅 AR 需要 `h×w` 次前向（如 16×16 = 256 次），VAR 只需 K 次（256² 时约 10 次）；③归纳偏置：粗到细对应自然图像"低频稳定、高频依赖低频"的统计规律。
- **推理成本**：前向次数 = K；但总 token 数 `Σ s_k²` 比最后一级多（skill 示例为 680 vs 256）；配合对已生成尺度的 KV cache，每次前向只需计算新一级的 token。
- **效果**（以讲义为准）：类条件 ImageNet 上达到或超过同算力的 DiT，且 FID 随算力呈幂律下降。
- **常见误区**：说"VAR 没有自回归"——它在尺度之间仍是严格自回归的，只是尺度内并行。

### Q14 — 参考回答要点

- **残差的作用**：第 k 级只编码前 k−1 级没表达出来的部分，于是 `f ≈ Σ upsample(embed(z_k))`，粗级负责低频、细级负责高频，各级分工明确、信息不重复；解码器只需对"总和"解码。
- **非残差会怎样**：各级独立量化下采样的 `f`，细级会重复编码粗级已有的低频信息，"给定前面各级预测下一级"的条件分布就变得含糊——下一级既要重复粗级内容又要加细节。skill 文件因此拒绝非残差方案："没有残差求和，下一尺度条件分布定义不清，模型优化的目标与论文证明的不同"。
- **共享 vs 分级码本**：讲义说各级使用**同一个**码本（典型 4096–16384），skill 文件也默认共享，并只在"码本大小按小尺度的像素数校准、且处理了码本坍缩"时才接受分级码本。⚠️ 本节玩具代码为每级各拟合了一个 16 码字的标量码本（`train_codebooks`），与讲义的设定不同；它的码本里还出现了大量重复码字（如 1×1 级有 6 个 0.5），等于浪费了码本容量——这正是需要监控"码本利用率"的原因（skill 文件：校准批上利用率低于 50% 就缩小 V）。
- **训练**：像 VQGAN 一样训练一次（感知损失、对抗损失等），然后冻结；所有生成能力都在上面的 transformer 里。
- **加分点**：联系音频编解码里的 RVQ（残差向量量化）——同样是"逐级量化残差"，只是 VAR 的各级还有不同的空间分辨率。

### Q15 — 参考回答要点

- **假设**：同一尺度内各位置在给定前面尺度后条件独立，`p(z_k | z_<k) ≈ Π_{i,j} p(z_k[i,j] | z_<k)`。
- **最差情形**：同一级里存在需要"协调"的多模态选择——例如某个区域可以是 A 或 B 两种纹理，相邻位置独立采样可能一半选 A 一半选 B，产生不一致的拼接。尺度越粗、每个 token 覆盖面积越大，单个 token 的多模态越强，这种风险越大；Q12 的玩具实验里也能看到这种"拼出训练中不存在的组合"的现象。
- **VAR 的缓解**：①粗到细：大部分全局结构在前几级（token 很少）就定下来，后面细级的不确定性主要是局部细节，近似独立更合理；②每一级都能看到之前所有尺度的完整信息，没有光栅顺序那种"只看到一半"的问题；③采样时常用 top-k / top-p、CFG 等手段降低低概率组合的出现。
- **对比**：MaskGIT 类方法在同一分辨率上多轮迭代、每轮只确定一部分 token，用迭代换一致性；VAR 用"多分辨率"换一致性。
- **加分点**：指出这和 Q12 中"上下文命中但仍退化"的现象是同一个原因。

### Q16 — 参考回答要点

- **前向次数**：VAR 为 K（讲义：256² 约 10 次）；DiT 为采样步数（讲义：28–50 步）。
- **每次处理的 token**：DiT 每一步都对整张潜变量的全部 token 做一次完整前向；VAR 第 k 次前向只需为第 k 级的 `s_k²` 个新 token 计算，前面各级的 key / value 可以缓存（尺度间是因果的，已生成的尺度不会再变）。
- **总计算量粗估**：VAR 所有前向加起来大致相当于"一次处理 `Σ s_k²` 个 token"（skill 示例为 680 个）；DiT 则是"步数 × 每步 token 数"。因此 VAR 的推理计算量通常小一个数量级以上。
- **代价**：VAR 的最后几级 token 多，注意力长度达到全部 680 个 token；离散 tokenizer 的重建质量是上限；KV cache 带来显存开销。
- **常见误区**：只比较"10 次 vs 50 次"，忽略每次前向的 token 数与缓存；或认为 VAR 每次都要重算整个序列。

### Q17 — 参考回答要点

- **质量上限**：VAR 的上限受离散 tokenizer 的重建质量约束（细节、文字等）；连续潜空间 + flow matching 没有量化损失。讲义提到 HART 等工作正是为了补这块（据其论文，HART 用"离散 token + 连续残差 token"的混合 tokenizer，残差部分由一个小的扩散模块建模）。
- **速度**：VAR 约 K 次前向、可以 KV cache；flow matching 底座 + 蒸馏也能做到 1–4 步（第 13 节）。两者都能满足低延迟，需在目标分辨率上实测。
- **生态与工具链**：DiT + flow matching 有成熟的开源权重、ControlNet / LoRA 生态和部署经验；VAR 与 LLM 共享"离散 token + 交叉熵 + transformer"的范式，更容易和多模态 LLM 统一（参考阶段 12 的 Chameleon、Emu3 等"一切皆 token"的路线）。
- **加文本条件**：①把 CLIP / T5 文本嵌入作为额外条件，通过 adaLN 调制注入（讲义练习 5）；②在序列前部拼接文本 token 或用 cross-attention；③训练时随机丢弃条件以支持 CFG；④位置编码保留 `(scale, row, col)`，并给文本条件预留序列长度（skill 文件：K × 平均尺度面积超过最大序列长度减去文本余量时，拒绝使用下一尺度预测）。
- **评估**：按第 14 节的四支柱比较两种方案：FID / CMMD、CLIP score、人工偏好、失败案例。
- **加分点**：能说出两条路线在 2024–2026 年都在演进，选型更多取决于团队栈、可控性需求和与 LLM 统一的长期规划，而不是单一指标。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 03 多头注意力](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：块因果 mask 只是注意力 mask 的一种形状。
- [阶段 07 · 07 GPT 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：VAR 的训练目标就是"按尺度组织"的 next-token 交叉熵。
- [阶段 08 · 02 自编码器与 VAE](../../02-autoencoders-vae/docs/zh.md)：VQ-VAE / VQGAN tokenizer 的基础。
- [阶段 08 · 06 从零实现 DDPM](../../06-diffusion-ddpm-from-scratch/docs/zh.md)：讲义一直在拿扩散做对照。

### 本节被哪些后续内容用到
- [阶段 08 · 14 Evaluation — FID、CLIP 分数、人类偏好](../../14-evaluation-fid-clip-score/docs/zh.md)：VAR 与 DiT 的比较依据是 ImageNet FID；玩具生成的问题也只有分布级评估才能发现。
- [阶段 08 · 13 Flow Matching 与 Rectified Flows](../../13-flow-matching-rectified-flows/docs/zh.md)、[阶段 04 · 23 Diffusion Transformers 与 Rectified Flow](../../../04-computer-vision/23-diffusion-transformers-rectified-flow/docs/zh.md)：VAR 在速度和质量上的主要竞争路线。
- [阶段 07 · 13 缩放定律](../../../07-transformers-deep-dive/13-scaling-laws/docs/zh.md)：理解"VAR 呈现类似 GPT 的幂律缩放"这一结论。
- [阶段 07 · 12 KV Cache 与 Flash Attention](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：跨尺度缓存 key / value 是 VAR 推理快的关键之一。
- [阶段 06 · 13 神经音频编解码器](../../../06-speech-and-audio/13-neural-audio-codecs/docs/zh.md)：音频中的残差向量量化（RVQ），与多尺度残差 VQ 同源。
- [阶段 12 · 11 Chameleon 早期融合 token](../../../12-multimodal-ai/11-chameleon-early-fusion-tokens/docs/zh.md)、[阶段 12 · 12 Emu3：用下一 token 预测做生成](../../../12-multimodal-ai/12-emu3-next-token-for-generation/docs/zh.md)：把图像离散化后交给 LLM 统一建模的路线。

### 延伸关键词
`VQ-VAE / VQGAN` · `Residual VQ (RVQ)` · `MaskGIT / Muse` · `LlamaGen` · `VAR-CLIP` · `HART` · `block-causal attention` · `codebook utilization / dead codes` · `top-k / top-p sampling` · `Classifier-free guidance` · `ImageNet 256 FID`
