# 测验 · 自监督视觉——SimCLR、DINO、MAE（Self-Supervised Vision — SimCLR, DINO, MAE）

> **阶段 04 · 计算机视觉 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、读过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 自监督与 pretext task | 用不需要标签的"代理任务"（匹配视图、重建 patch）学特征；代理任务本身不必是下游任务，预训练后即被丢弃 |
| 2 | 三大家族 | 对比学习（SimCLR、MoCo、CLIP）、师生蒸馏（DINO、BYOL、iBOT）、掩码重建（MAE、BEiT、SimMIM） |
| 3 | InfoNCE | 同一图像的两个增强视图互为正样本，batch 内其他样本都是负样本；对余弦相似度 / τ 做 softmax 交叉熵，τ 常取 0.1 |
| 4 | 负样本与 batch | batch 就是负样本池，SimCLR 需要 512–8192 的 batch；MoCo 用动量队列让负样本数与 batch 大小解耦 |
| 5 | DINO | teacher 是 student 权重的 EMA（m ≈ 0.996），student 去匹配 teacher 的输出，无需负样本；对 teacher 输出做 centering（减去各维均值）和 sharpening（低温度）防止坍塌 |
| 6 | MAE | 遮住 75% 的 patch；大 encoder 只处理可见的 25%，小 decoder（8 层、512 维）加上 mask token 重建像素；只在被遮住的 patch 上计算 MSE |
| 7 | 75% vs 15% | 图像 patch 信息密度低、邻域相关性强，必须大比例遮盖才能逼模型学语义；文本 token 信息密度高，15% 已足够难 |
| 8 | Linear probe | 冻结 encoder，只训练一个线性分类器，衡量特征质量；微调通常再高 2–5 个点，但混入了训练头部的影响 |
| 9 | DINOv2 | 2026 年的生产默认自监督 backbone；`[CLS]` 向量直接用于检索、稠密对应和零样本迁移 |

### 核心技能（能动手做到）

- [ ] 从零写出 `info_nce`：拼接两个视图、构造 `(2N, 2N)` 相似度矩阵、屏蔽对角线、构造 targets，并能手算一个 2 样本的小例子
- [ ] 说出温度 τ 对"对齐良好"和"完全随机"两种嵌入的损失分别有什么影响，并用实验验证
- [ ] 实现 MAE 的随机遮盖（单样本版和批量版），能正确算出保留数量并用 `ids_restore` 还原顺序
- [ ] 实现 DINO 的 centering 缓冲区（EMA 更新），解释 teacher 为什么要 `detach`、为什么温度更低
- [ ] 对任意冻结 encoder 跑一次 linear probe（先缓存特征，再用 SGD + 余弦学习率训练线性头）
- [ ] 根据无标注数据量、算力预算、下游任务，在 SimCLR / MoCo / MAE / DINOv2 之间做出选择

---

## 二、基础自测（选择题）

**Q1.** SimCLR 中 batch 大小为 N（每张图两个视图，共 2N 个嵌入）。对某一个 anchor 来说，有多少个负样本？为什么 SimCLR 需要很大的 batch？

- A. N − 1 个；batch 大只是为了让 BatchNorm 更稳定
- B. 2N − 2 个；batch 本身就是负样本池，负样本太少时对比信号弱，训练效果差
- C. 2N 个；对比损失要除以 batch 大小
- D. 1 个；只有正样本，batch 大小无关紧要

**Q2.** DINO 不使用负样本，靠什么防止"所有输入都输出同一个向量"的坍塌？

- A. 只靠非常大的 batch
- B. 只靠强数据增强
- C. 对 teacher 输出做 centering（减去各维度的 EMA 均值）和 sharpening（使用较低的 teacher 温度）：前者防止某一维独大，后者防止输出坍塌成均匀分布
- D. 给 student 加 Dropout

**Q3.** MAE 遮住 75% 的 patch，而 BERT 只遮住 15% 的 token，根本原因是：

- A. 75% 是随便选的
- B. 图像 patch 的信息密度低，邻近像素几乎能决定被遮住的内容，遮得少时靠局部外推就能解决；必须大比例遮盖才能逼 encoder 学到语义
- C. 文本 token 比图像 patch 大
- D. Transformer 处理图像时只能接受 25% 的输入

**Q4.** 关于 MAE 的非对称 encoder-decoder 设计，正确的是：

- A. encoder 处理全部 patch，被遮住的位置用 mask token 代替
- B. encoder 只处理可见的 25% patch；mask token 只出现在轻量 decoder 中；损失只在被遮住的 patch 上计算；预训练后丢弃 decoder
- C. decoder 和 encoder 一样大，预训练后保留 decoder 用于分类
- D. 损失在全部 patch 上计算，包括可见的 patch

**Q5.** 自监督预训练后的 linear probe 评估中，训练的是：

- A. 整个 encoder 加一个 MLP 头
- B. 只有位置编码
- C. 冻结 encoder，只训练一个线性分类器
- D. 只训练 encoder 的最后一层

**Q6.** 对两组 L2 归一化的嵌入计算 InfoNCE：一组是完全对齐的正样本对（两个视图相同），另一组是完全随机的配对。把温度 τ 从 0.5 降到 0.1，两者的损失分别会怎样？

- A. 都下降
- B. 都上升
- C. 对齐的那组下降（接近 0），随机的那组上升（明显高于 log(2N−1)）
- D. 都不变，温度只影响梯度

**Q7.** DINO 中 teacher 的更新方式是：

- A. 和 student 一样用梯度下降更新
- B. `teacher = m · teacher + (1 − m) · student`，m ≈ 0.996；teacher 不接收梯度，变化得很慢，提供稳定的学习目标
- C. 每个 epoch 把 student 权重直接复制给 teacher
- D. teacher 固定为 ImageNet 预训练模型，从不更新

---

## 三、动手 / 代码题

**Q8.** 本节的 `info_nce`：

```python
def info_nce(z1, z2, tau=0.1):
    N, D = z1.shape
    z = torch.cat([z1, z2], dim=0)
    sim = z @ z.T / tau
    mask = torch.eye(2 * N, dtype=torch.bool, device=z.device)
    sim = sim.masked_fill(mask, float("-inf"))
    targets = torch.cat([torch.arange(N, 2 * N), torch.arange(0, N)]).to(z.device)
    return F.cross_entropy(sim, targets)
```

(1) 令 `z1 = z2 = [[1, 0], [0, 1]]`（两个正交单位向量，两个视图完全相同）。手算 `tau=1` 和 `tau=0.1` 时的损失。
(2) `targets` 为什么是 `[N, …, 2N−1, 0, …, N−1]`？
(3) 如果忘了 `masked_fill` 对角线，随机配对时的损失会接近多少？模型会学到什么？

**Q9.** `main()` 中有这样一行提示：

```python
    print(f"  random pairs:     {loss_random:.3f}  (should be near log(2N-1) = {torch.log(torch.tensor(31.0)):.3f})")
```

这里 `N=16`、`D=32`、`tau=0.1`，嵌入是随机生成后 L2 归一化的。实际打印的 `loss_random` 会接近 3.434 吗？请估算它的量级，解释原因，并说明在什么条件下它才会接近 `log(2N−1)`。

**Q10.** MAE 遮盖：

```python
def random_mask_indices(num_patches, mask_ratio=0.75, seed=0):
    g = torch.Generator().manual_seed(seed)
    n_keep = int(num_patches * (1 - mask_ratio))
    perm = torch.randperm(num_patches, generator=g)
    visible = perm[:n_keep]
    masked = perm[n_keep:]
    return visible.sort().values, masked.sort().values
```

(1) `random_mask_indices(196, 0.75)` 的可见数和遮盖数各是多少？`random_mask_indices(100, 0.9)` 呢？后者有什么问题？如何修复？
(2) 讲义说"真实的 MAE 实现会批量处理，并为每个样本保留各自的 mask"。用 NumPy 写一个 `batched_random_masking(x, mask_ratio)`：输入 `(B, L, D)` 的 patch token，返回可见 token `(B, n_keep, D)`、二值 mask `(B, L)`（1 表示被遮住，按原始 patch 顺序排列）和 `ids_restore`。

**Q11.** `DinoHead` 的 centering：

```python
    def teacher(self, x, temp=0.04):
        out = self.proj(x)
        return F.softmax((out - self.centre) / temp, dim=-1).detach()

    @torch.no_grad()
    def update_centre(self, teacher_out):
        self.centre.mul_(self.momentum).add_(teacher_out.mean(dim=0), alpha=1 - self.momentum)
```

(1) `momentum=0.9`，`centre` 初始为 `[0, 0]`。如果连续两个 batch 的 `teacher_out.mean(dim=0)` 都是 `[1, −1]`，两次更新后的 `centre` 分别是多少？
(2) 为什么 `teacher()` 要 `.detach()`？为什么 teacher 的温度（0.04）比 student（0.1）低？
(3) `main()` 只做了一次 `update_centre`，打印的"max col mean"从更新前到更新后会怎样变化？变化大吗？为什么？

---

## 四、面试高频题

**Q12.**（基础必考）对比 SimCLR、DINO、MAE：各自优化什么目标？是否需要负样本？计算开销和对 batch 的需求如何？各适合什么下游任务？

**Q13.**（原理深挖）详细讲解 InfoNCE：公式、温度的作用、负样本数量的影响，以及 MoCo 是怎么解决 batch 大小限制的。

**Q14.**（原理深挖）什么是表示坍塌（representation collapse）？不同的自监督方法分别用什么机制避免它？

**Q15.**（工程实践 / 场景设计）你有 50 万张无标注的工业质检图片和 2,000 张标注图片，GPU 预算约 150 GPU 小时。你会怎么做？如何评估方案的好坏？

**Q16.**（追问型）讲义中 MAE ViT-L/16 的 linear probe（约 76%）不如 DINO ViT-S/16（约 77%），可 MAE 微调后又很强。为什么会这样？这对实际选型有什么启示？

---

## 五、参考答案与解析

### Q1 — 答案：B

2N 个嵌入中，去掉 anchor 自己和它的正样本，剩下 2N − 2 个都是负样本（例如 N=256 时为 510 个）。InfoNCE 是把正样本和所有负样本放在一起比较，负样本越多，对比信号越"尖锐"。batch 太小时负样本不足，训练效果差。MoCo 用动量队列保存过去 batch 的特征，让负样本数与 batch 大小解耦。

### Q2 — 答案：C

讲义原话："centering 防止某一维独大；sharpening 防止输出坍塌成均匀分布。"二者方向相反、互相制衡：只做 centering，输出会趋于均匀；只做 sharpening，会被某一维主导。A、B 都不是 DINO 防坍塌的核心机制。

### Q3 — 答案：B

关键在信息密度。文本每个 token 有很多合理的补全，遮 15% 已经足够难；图像 patch 与邻域高度相关，遮得少时"抄邻居"就能重建，模型学不到语义。75% 高到简单的空间外推无法解决，encoder 必须表示图像内容。

### Q4 — 答案：B

encoder 只看可见 patch，计算量约为全量的 1/4；mask token 只进入轻量 decoder（8 层、512 维）。讲义称这比朴素的 BEiT 式设计（所有 token 都过 encoder）预训练快约 3 倍。损失是被遮 patch 上的像素 MSE。预训练后丢弃 decoder，只保留 encoder 作为特征提取器。

### Q5 — 答案：C

linear probe 冻结 encoder，只拟合 `Linear(feature_dim → num_classes)`，得到的准确率直接反映特征空间的线性可分性，是"纯粹的特征质量度量"。skill 文件强调：探测期间绝不能更新 encoder，否则就成了微调；特征只需提取一次并缓存。

### Q6 — 答案：C

已用 NumPy 按同一公式模拟（N=16、D=32，各 2000 次）：

| τ | 对齐（相同视图） | 随机配对 |
|---|---------------|---------|
| 0.5 | 约 1.67 | 约 3.50 |
| 0.2 | 约 0.26 | 约 3.80 |
| 0.1 | 约 0.006 | 约 4.80 |
| 0.05 | 约 0.0000 | 约 7.75 |

对齐时，正样本的 logit 为 `1/τ`，降低 τ 会把它与负样本的差距拉大，损失趋近 0；随机时，所有 logit 的波动都被 `1/τ` 放大，log-sum-exp 被少数偶然较大的负样本主导，损失上升。这正是讲义练习 1 要验证的现象。

### Q7 — 答案：B

讲义公式 `teacher_weights = m · teacher_weights + (1 − m) · student_weights`，m ≈ 0.996。teacher 不参与反向传播，是 student 的"时间平均"，比 student 更平滑、更稳定，从而提供一个缓慢移动的目标。BYOL、MoCo、DINO 都使用 EMA teacher（或 EMA 编码器）。

### Q8 — 参考答案

(1) `N=2`，`z = [e1, e2, e1, e2]`。以第 0 行（anchor 为 `e1`）为例，`sim/τ` 为 `[自己, e1·e2, e1·e1(正样本), e1·e2] = [−inf, 0, 1/τ, 0]`：

```text
loss_row0 = −1/τ + log(e^0 + e^(1/τ) + e^0) = log(1 + 2·e^(−1/τ))

τ = 1  : −1 + log(2 + e) = −1 + log(4.71828) = −1 + 1.55144 = 0.5514
τ = 0.1: log(1 + 2·e^(−10)) ≈ 2·e^(−10) ≈ 9.08e-5
```

4 行完全对称，平均值不变。所以 τ=1 时损失约 0.551，τ=0.1 时约 9.1e-5（已用 NumPy 实现的同一公式核对）。即使正样本完全对齐，τ=1 时损失也远不为 0——温度太高，正负样本拉不开差距，这也是 SimCLR 使用 0.1 这类低温度的原因。

(2) `z` 的前 N 行是视图 1，后 N 行是视图 2，第 `i` 个样本的两个视图分别在第 `i` 行和第 `i+N` 行。所以第 `i` 行（`i < N`）的正样本在第 `i+N` 列，第 `i+N` 行的正样本在第 `i` 列——`targets` 正是把这两段拼接起来。然后 `F.cross_entropy` 把每一行当作一个 2N 类的分类问题，"正确类别"就是正样本所在的列。

(3) 对角线是每个嵌入和自己的相似度，L2 归一化后恒为 `1/τ = 10`，是全行最大的 logit。不屏蔽的话，随机配对时损失 ≈ `10 − l_pos ≈ 10` 左右，而且梯度主要在"压低自身相似度"——可归一化向量与自己的点积恒为 1，这部分无法优化，只会稀释有效的学习信号。用 `-inf` 屏蔽后，`exp(-inf) = 0`，自身从分母中消失。

### Q9 — 参考答案

不会。按同样的设定（N=16、D=32、τ=0.1、随机单位向量）用 NumPy 模拟 2000 次，`loss_random` 的均值约 **4.80**，90% 的情况落在 4.0–5.5 之间；`main()` 中具体打印的数值取决于 PyTorch 的随机数，但大概率在这个区间，明显高于 3.434。

原因：`log(2N−1)` 是"所有 31 个候选 logit 都相等"时的损失（即均匀分布的交叉熵）。随机单位向量在 32 维空间中的余弦相似度近似服从均值 0、标准差约 `1/√32 ≈ 0.18` 的分布，除以 τ=0.1 后，logit 的标准差约 1.8。log-sum-exp 对这种波动很敏感（大约多出 `σ²/2 ≈ 1.6`），于是损失 ≈ `log 31 + 1.6 ≈ 5.0`，与模拟结果一致。

只有当 logit 的波动很小时——**τ 较大**（如 τ=1 时模拟均值约 3.45）或**维度 D 很高**（余弦相似度更集中于 0）——随机配对的损失才会接近 `log(2N−1)`。所以代码中的提示"should be near log(2N-1)"在 τ=0.1 时并不准确，更严谨的说法是"不低于约 log(2N−1)，且随 τ 降低而升高"。

### Q10 — 参考答案

(1) 196 × 0.25 = 49.0，可见 49、遮盖 147。`random_mask_indices(100, 0.9)`：`1 − 0.9` 在浮点数中是 `0.09999999999999998`，`100 × 0.0999… = 9.999999999999998`，`int()` 向零截断得到 **9**，而不是期望的 10（已在 Python 中验证）。浮点误差加上截断，导致少保留一个 patch。修复：`n_keep = int(round(num_patches * (1 - mask_ratio)))`。官方 MAE 代码也是 `int(L * (1 - mask_ratio))`，在 0.75 这类二进制可精确表示的比例下没有问题，换比例时要小心。

(2) 以下代码已用 NumPy 实际运行验证（`B=2, L=196`：可见 token 形状 `(2, 49, 8)`，每个样本遮盖 147 个，两个样本的 mask 不同，可见 token 与 mask 一致）：

```python
import numpy as np

def batched_random_masking(x, mask_ratio=0.75, rng=None):
    """x: (B, L, D) patch tokens。每个样本独立随机遮盖，返回可见 token、mask 和还原下标。"""
    rng = rng or np.random.default_rng()
    B, L, D = x.shape
    n_keep = int(round(L * (1 - mask_ratio)))
    noise = rng.random((B, L))                       # 每个样本一组随机数
    ids_shuffle = np.argsort(noise, axis=1)          # 小的在前 = 保留
    ids_restore = np.argsort(ids_shuffle, axis=1)    # 逆排列，用于还原原始顺序
    ids_keep = ids_shuffle[:, :n_keep]
    x_visible = np.take_along_axis(x, ids_keep[:, :, None], axis=1)   # (B, n_keep, D)
    mask = np.ones((B, L))
    mask[:, :n_keep] = 0                              # 0 = 可见，1 = 被遮盖（打乱后的顺序）
    mask = np.take_along_axis(mask, ids_restore, axis=1)               # 还原成原始 patch 顺序
    return x_visible, mask, ids_restore
```

要点：
- 用"对随机噪声 argsort"代替逐样本 `randperm`，一次向量化操作就能为整个 batch 生成各不相同的排列；
- `argsort(ids_shuffle)` 得到逆排列 `ids_restore`，decoder 用它把"可见 token + mask token"放回原始位置；
- 位置编码在遮盖**之前**就已经加到 token 上，所以可见 token 的顺序被打乱也没关系；
- 损失只在 `mask == 1` 的位置上计算。

### Q11 — 参考答案

(1)

```text
第 1 次：centre = 0.9·[0, 0]       + 0.1·[1, −1] = [0.1,  −0.1]
第 2 次：centre = 0.9·[0.1, −0.1]  + 0.1·[1, −1] = [0.19, −0.19]
```

这是指数移动平均（EMA）：`mul_(m)` 先把旧值缩小，`add_(mean, alpha=1−m)` 再加上新值乘以 `1−m`。若均值一直不变，`centre` 会以 `1 − 0.9ᵏ` 的比例逐渐逼近它。下划线结尾的 `mul_`、`add_` 是原地操作，`centre` 是用 `register_buffer` 注册的 buffer——会随模型保存和移动设备，但不是可训练参数。

(2) `.detach()` 切断梯度：teacher 的输出只作为目标，梯度只流向 student。否则损失会同时"拉动"目标本身，最容易的解就是两边一起坍塌（这就是 stop-gradient 的作用；在真实 DINO 中，teacher 的权重通过 EMA 而非梯度更新）。teacher 用更低的温度是 **sharpening**：让 teacher 的分布更"尖"，给 student 一个明确的目标，防止输出坍塌成均匀分布；student 温度较高、分布较平，去学习匹配这个尖锐的目标。

(3) 用 NumPy 按同样的初始化方式模拟 500 次：更新前约 0.131，一次更新后约 0.128（约 87% 的情况下有所下降），而如果把中心直接设为完整的 batch 均值，约为 0.113（均匀分布时为 1/16 = 0.0625）。所以预期是"略有下降"，变化很小。原因是 `momentum=0.9`，一次更新只把中心向 batch 均值移动了 10%，对 logits 的修正有限。这个演示只是展示机制；真实训练中中心会在很多步中持续累积，持续抑制"某一维独大"的趋势。

### Q12 — 参考回答要点

| | SimCLR（对比） | DINO（师生） | MAE（掩码重建） |
|---|---|---|---|
| 目标 | 拉近同一图像两个视图的嵌入，推开 batch 内其他样本（InfoNCE） | student 输出匹配 EMA teacher 在另一视图上的输出（交叉熵） | 从 25% 的可见 patch 重建被遮住 patch 的像素（MSE） |
| 负样本 | 需要，batch 即负样本池 | 不需要，靠 centering + sharpening 防坍塌 | 不需要 |
| batch / 计算 | 需要大 batch（512–8192）或 MoCo 队列 | 两个网络都要前向，多视图 | encoder 只处理 25% 的 token，预训练高效 |
| 特征特点 | 全局语义 | 线性可分性好，适合检索、kNN、稠密对应（DINOv2 为 SOTA） | 需要微调才能发挥；与检测、分割等稠密任务契合 |

- **选型**（参考 SSL 选型 prompt）：
  - 检索 → DINOv2；
  - ViT + 检测/分割 → MAE；
  - ResNet + 分类 → MoCo v3；
  - 无标注数据少于 10 万或算力不足 → 不要从零做 SSL，直接用 DINOv2 预训练权重。
- **加分点**：
  - 三类方法的共同点是利用数据增强或遮盖制造"同一内容的不同观测"；
  - iBOT、DINOv2 把师生蒸馏和掩码预测结合在了一起。

### Q13 — 参考回答要点

- **公式**：对正样本对 `(i, j)`，`L = −log( exp(sim(zᵢ,zⱼ)/τ) / Σ_{k≠i} exp(sim(zᵢ,z_k)/τ) )`，sim 为余弦相似度。本质是一个 `2N−1` 类的 softmax 分类问题，"正确类别"是正样本。实现上用 `(2N, 2N)` 相似度矩阵、屏蔽对角线、`cross_entropy` 一步完成。
- **温度 τ**：
  - 控制分布的尖锐程度，τ 越小，越关注困难负样本（与 anchor 最相似的那些负样本获得更大的梯度权重）；
  - 但 τ 太小，训练不稳定，对噪声敏感；
  - SimCLR 默认 0.1。
- **负样本数**：InfoNCE 可以看作互信息的一个下界，大致形式为 `I ≥ log(K) − L`（K 为候选数），负样本越多，这个下界可以越紧；实践中负样本越多，表示越好，因此需要大 batch。
- **MoCo**：
  - 维护一个先进先出的特征队列，存放过去多个 batch 的 key，负样本数（如 65536）不再受 batch 大小限制；
  - key 编码器用 query 编码器的动量（EMA）更新，保证队列中的特征缓慢变化、彼此一致。
- **常见误区**：以为 batch 大只是为了 BN 统计——真正原因是负样本数量。

### Q14 — 参考回答要点

- **定义**：encoder 对所有输入输出几乎相同的向量（完全坍塌），或者表示只占据很低维的子空间（维度坍塌）。此时自监督损失可能很低，但特征毫无用处。
- **为什么会发生**：如果目标只是"让两个视图的输出一致"，输出常数就是一个平凡的最优解。
- **各方法的对策**：
  - **对比学习**（SimCLR / MoCo）：负样本把不同图像的嵌入推开，常数解的损失很高；
  - **DINO**：centering（减去 EMA 均值，防止某一维独大）+ sharpening（低 teacher 温度，防止输出均匀），再加上 stop-gradient 与 EMA teacher；
  - **BYOL / SimSiam**：在 student 端加 predictor 网络 + stop-gradient，打破对称性；
  - **方差/协方差正则**（如 VICReg）：显式要求每一维有足够的方差、各维之间去相关；
  - **MAE**：重建像素这一目标本身就要求保留输入信息，天然不会坍塌成常数。
- **如何监控**：
  - 观察特征各维的标准差、batch 内样本嵌入的平均余弦相似度；
  - 定期跑 kNN / linear probe。
  讲义练习 2 就是去掉 centering、观察 student 坍塌。

### Q15 — 参考回答要点

- **先看预算**：150 GPU 小时远远不够从零跑完一次自监督预训练。SSL 选型 prompt 的第一条规则就是：`compute_gpu_hours < 200` → 不要从零做 SSL，直接用 DINOv2 预训练权重。
- **推荐流程**：
  1. 用 DINOv2 提取 2,000 张标注图的特征（`[CLS]` 向量），先跑 **linear probe** 作为基线：冻结 encoder，特征只提取一次并缓存，用 SGD + 余弦学习率、无权重衰减，扫一遍学习率；
  2. 同时跑 kNN 分类作为参考；
  3. 若精度不够，再逐步加大投入：微调最后几层或整个 backbone（小学习率），配合强数据增强；
  4. 50 万张无标注图片可以用于：基于 DINOv2 特征做聚类，挑选难例送去标注（主动学习）；或者在预算允许时，用 MAE / DINO 做短时间的领域自适应继续预训练（从 DINOv2 权重出发，而不是从零开始）；
  5. 质检图像往往需要细粒度、局部的缺陷信息，可以考虑使用 patch 级特征，或把 DINOv2 用作检测/分割的 backbone。
- **评估**：
  - 固定一个留出验证集，比较 linear probe、kNN、微调三条线；
  - 质检场景看召回率 / 漏检率而不只看准确率；
  - 记录每种方案的 GPU 小时数。
- **常见误区**：
  - 有了无标注数据就一定要从零预训练；
  - 在 linear probe 中不小心更新了 encoder。

### Q16 — 参考回答要点

- **现象**：MAE 的特征线性可分性较弱，所以 linear probe 分数不高；但它作为微调的初始化非常好，微调后精度很高。
- **原因**：
  - MAE 的目标是重建像素，encoder 需要保留大量与纹理、局部结构相关的信息，语义信息并没有被组织成"线性可分"的形式，需要非线性的头或微调来提取；
  - DINO 的目标是让不同视图的全局输出一致，直接塑造了一个语义聚类良好的嵌入空间，因此线性探测与 kNN 都很强。
- **启示**：
  - 只做冻结特征的检索、kNN、零样本迁移 → 选 DINO / DINOv2；
  - 能负担微调、做检测分割等稠密任务 → MAE 预训练的 ViT 很合适（选型 prompt：ViT + 检测/分割 → MAE）；
  - 评估 SSL 方法时，要同时看 linear probe 和微调两个指标，讲义也指出微调通常再高 2–5 个点，但会混入训练头部的影响。
- **加分点**：提到 iBOT / DINOv2 把掩码预测与师生蒸馏结合，兼顾了两者的优点。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 14 Vision Transformers](../../14-vision-transformers/docs/zh.md)：patch、`[CLS]`、位置编码，MAE 与 DINO 都以 ViT 为主干。
- [阶段 04 · 04 图像分类](../../04-image-classification/docs/zh.md)：数据增强与分类评估，是 linear probe 的基础。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：交叉熵与 softmax，InfoNCE 就是一个特殊的交叉熵。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：熵、互信息，理解"信息密度"和 InfoNCE 的互信息下界。

### 本节被哪些后续内容用到
- [阶段 04 · 18 开放词表视觉——CLIP](../../18-open-vocab-clip/docs/zh.md)：CLIP 就是图文之间的 InfoNCE 对比学习。
- [阶段 04 · 20 图像检索和度量学习](../../20-image-retrieval-metric/docs/zh.md)：DINOv2 特征是现代图像检索的骨干。
- [阶段 04 · 24 SAM 3 与开放词表分割](../../24-sam3-open-vocab-segmentation/docs/zh.md)、[阶段 04 · 26 单目深度和几何估计](../../26-monocular-depth/docs/zh.md)：自监督 ViT 特征在稠密预测中的应用。
- [阶段 04 · 12 视频理解](../../12-video-understanding/docs/zh.md)：VideoMAE 是 MAE 在视频上的推广。
- [阶段 05 · 22 Embedding 模型深入](../../../05-nlp-foundations-to-advanced/22-embedding-models-deep-dive/docs/zh.md)：文本 embedding 同样用 InfoNCE 训练。
- [阶段 07 · 06 BERT 与掩码语言建模](../../../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/zh.md)：15% 掩码的文本版本，对比 MAE 的 75%。
- [阶段 12 · 02 CLIP 对比预训练](../../../12-multimodal-ai/02-clip-contrastive-pretraining/docs/zh.md)：多模态对比学习。

### 延伸关键词
`MoCo v3` · `BYOL / SimSiam` · `iBOT` · `DINOv2` · `VICReg` · `BEiT / SimMIM` · `VideoMAE` · `kNN 评估` · `representation collapse` · `互信息下界` · `hard negatives`
