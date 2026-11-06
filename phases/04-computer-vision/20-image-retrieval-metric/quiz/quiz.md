# 测验 · 图像检索和度量学习（Image Retrieval & Metric Learning）

> **阶段 04 · 计算机视觉 · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 检索系统的两大决策 | embedding（用什么模型出向量）+ 索引（怎么大规模找近邻）；2026 年两者都已是"现成品"，难点在定义"什么算相似" |
| 2 | 度量学习（metric learning） | 训练编码器，让 embedding 空间里的距离反映业务想要的相似性 |
| 3 | 四类损失 | Contrastive（成对）、Triplet（三元组 + margin）、NT-Xent / InfoNCE（batch 内负例）、Proxy-based（每类一个可学习代理，只需类别标签） |
| 4 | Triplet loss | `L = max(0, d(a,p) - d(a,n) + margin)`：拉近正例、推远负例，并保持至少 margin 的间隔 |
| 5 | 难例挖掘 | 简单负例损失为 0、不提供梯度；semi-hard（`d(a,p) < d(a,n) < d(a,p) + margin`）是 FaceNet 的经典配方 |
| 6 | 余弦 vs L2 | 单位向量下 `‖a-b‖² = 2 - 2cos(a,b)`，两者排序等价；要与训练时的度量保持一致 |
| 7 | Recall@K | 至少有一个正确结果落在 Top-K 的查询比例；同时报告 @1/@5/@10；去重场景更看重 precision@K |
| 8 | FAISS 索引选型 | `IndexFlatIP/L2` 精确暴力（约 1M 以内）、`IndexIVFFlat` 分桶近似（约 10M）、`IndexHNSW` 图索引、1 亿以上用 `IndexIVFPQ` |
| 9 | 实例级 vs 类别级 | "找猫"用现成 CLIP/DINOv2 就行；"找这一件商品"需要度量学习微调 |

### 核心技能（能动手做到）

- [ ] 用 `F.pairwise_distance` 写出 triplet loss，并能手算给定距离下的损失值
- [ ] 读懂并手工追踪 `semi_hard_negatives`：最难正例、semi-hard 负例窗口、回退到最难负例的逻辑
- [ ] 用 `topk` + 标签比较实现 Recall@K，并说明为什么在归一化向量上内积 Top-K = 余弦 Top-K
- [ ] 能指出 batch 内没有同类样本时挖掘函数的边界问题，并写出修复
- [ ] 能实现一个 proxy-based 损失（每类一个可学习代理 + 余弦 + 交叉熵）并与 triplet 对比
- [ ] 能根据数据规模选择 FAISS 索引，并说清 IndexFlatIP 前必须 L2 归一化的原因
- [ ] 能区分实例级与类别级检索，并据此决定"直接用预训练模型"还是"做度量学习微调"

---

## 二、基础自测（选择题）

**Q1.** 一个视觉搜索产品，用户输入**文字**，在**图片库**里检索。首选哪类 embedding 骨干？

- A. 监督训练的 ResNet-50 分类模型
- B. CLIP 或 SigLIP：图文在同一个 embedding 空间，文本查询与图片的余弦相似度开箱即有意义
- C. 手工设计的 ORB 局部描述子
- D. DINOv2：它是最强的自监督图像特征，所以一定最好

**Q2.** 两个 L2 归一化后的 embedding 余弦相似度为 0.5，它们的**平方**欧氏距离是：

- A. 0.5
- B. 1.0
- C. 1.5
- D. 2.0

**Q3.** 一个三元组的距离为 `d(a,p) = 0.5`、`d(a,n) = 0.6`，`margin = 0.2`。它的 triplet loss 是多少？这个负例属于哪一类？

- A. 0，简单负例
- B. 0.1，semi-hard 负例
- C. 0.3，最难（hard）负例
- D. 0.1，最难（hard）负例

**Q4.** 线上评测显示 recall@10 = 0.95，但 recall@1 = 0.42。最合理的结论是：

- A. 模型严重过拟合
- B. 评测代码一定写错了
- C. embedding 空间的整体结构是对的（相关项基本都在前 10），但前几名的排序噪声大；可加重排（re-ranking）阶段或继续微调
- D. 应该换用更大的 K 汇报指标

**Q5.** 下列哪个场景**最需要**做度量学习微调，而不能只依赖现成的 CLIP / DINOv2 特征？

- A. 在相册里找出所有"猫"的照片
- B. 电商"拍照找同款"：找到**这一件**具体商品（同一 SKU），而不是同类商品
- C. 按场景粗分"室内 / 室外"
- D. 用文字"海边日落"检索图片

**Q6.** 你要为 2 亿个 512 维向量建索引，内存有限。按讲义，最合适的选择是：

- A. `IndexFlatL2`，精确最好
- B. `IndexFlatIP`
- C. `IndexIVFPQ`：倒排分桶 + 乘积量化压缩
- D. 不需要索引，直接用 NumPy 做矩阵乘法

**Q7.** 对"重复图片检测"系统来说，哪个指标通常更重要？

- A. recall@100
- B. precision@K：每一个误报都是用户可见的错误
- C. 训练损失
- D. 索引构建时间

**Q8.** 关于 proxy-based 损失（如 ProxyNCA），下列说法正确的是：

- A. 必须提供（anchor, positive, negative）三元组
- B. 只需要类别标签；每个类学一个"代理向量"，对"样本与各代理的相似度"做交叉熵，无需挖掘样本对，训练快且稳定，但小数据集上可能过拟合代理
- C. 必须使用超大 batch 或动量队列
- D. 只能用于文本检索

---

## 三、动手 / 代码题

**Q9.**（手工追踪）`batch` 里 4 个样本，标签 `labels = [0, 0, 1, 1]`，`margin = 0.2`。假设 `torch.cdist(emb, emb)` 得到下面的距离矩阵：

```text
       0     1     2     3
0   0.00  0.50  0.55  0.90
1   0.50  0.00  0.30  0.80
2   0.55  0.30  0.00  0.40
3   0.90  0.80  0.40  0.00
```

对照本节代码：

```python
    positives = dist.clone()
    positives[~same_class] = float("-inf")
    positives.fill_diagonal_(float("-inf"))
    pos_idx = positives.argmax(dim=1)

    semi_hard = dist.clone()
    semi_hard[same_class] = float("inf")
    d_ap = dist[torch.arange(N), pos_idx].unsqueeze(1)
    semi_hard[dist <= d_ap] = float("inf")
    semi_hard[dist >= d_ap + margin] = float("inf")
    neg_idx = semi_hard.argmin(dim=1)

    fallback = semi_hard[torch.arange(N), neg_idx] == float("inf")
    if fallback.any():
        hardest = dist.clone()
        hardest[same_class] = float("inf")
        neg_idx = torch.where(fallback, hardest.argmin(dim=1), neg_idx)
```

1. 写出 `pos_idx` 和 `neg_idx`，并指出哪些 anchor 触发了 `fallback`。
2. 计算每个 anchor 的 triplet loss（忽略 `pairwise_distance` 的 1e-6 修正）以及 batch 平均值。

**Q10.**（找边界 bug）如果某个 anchor 在当前 batch 里**没有任何同类样本**，`semi_hard_negatives` 会返回什么样的 `pos_idx`？这会对训练造成什么影响？在本节 `main()` 的设置（6 类、batch 48）下这种情况常见吗？请给出修复方案。

**Q11.** 讲义练习 2 要求实现 ProxyNCA 风格的损失："每个类一个可学习的 proxy，对余弦相似度做标准交叉熵"。请写一个 `ProxyLoss(nn.Module)`，可以直接替换 `main()` 里的 triplet loss + 挖掘（输入 `emb` 和 `y`，输出标量损失），并说明 `scale` 参数的作用。

---

## 四、面试高频题

**Q12.**（基础必考）对比 Contrastive loss、Triplet loss、InfoNCE、Proxy-based loss：它们各需要什么监督信号？各自的优缺点和适用场景是什么？

**Q13.**（原理深挖）Triplet loss 为什么需要难例挖掘？为什么 FaceNet 选 semi-hard 而不是 hardest negative？batch-hard 又是什么？

**Q14.**（场景设计）设计一个电商"拍照找同款"系统：商品库 5000 万张图，要求找到同一 SKU。从数据、模型、索引、评测、上线讲一遍。

**Q15.**（工程实践）用 FAISS 做向量检索时有哪些常见坑？`IndexFlatIP`、`IndexIVFFlat`、`IndexHNSW`、`IndexIVFPQ` 怎么选？`nprobe` 怎么调？

**Q16.**（追问型）离线 recall@10 达到 0.98，上线后用户却反馈"搜出来的都不对"。可能是哪些原因？你会怎么排查？

---

## 五、参考答案与解析

### Q1 — 答案：B

文字查询要求文本和图像落在同一个空间，CLIP / SigLIP 正是用第 18 节的对比损失训练出这种空间。A 和 D 都是纯图像特征，没有文本塔，无法直接编码文字查询（D 用于以图搜图时很强）；C 是传统局部特征，适合几何匹配，不懂语义。

### Q2 — 答案：B

单位向量：`‖a-b‖² = ‖a‖² + ‖b‖² - 2a·b = 2 - 2cos = 2 - 1 = 1`。这个恒等式说明归一化后"余弦最大"与"L2 最小"给出相同排序，这也是 FAISS 中 `IndexFlatIP` 与 `IndexFlatL2` 在归一化向量上结果一致的原因。

### Q3 — 答案：B

`max(0, 0.5 - 0.6 + 0.2) = 0.1`。负例比正例远（0.6 > 0.5），但没有远出 margin（0.6 < 0.5 + 0.2 = 0.7），正好落在 semi-hard 窗口里，损失为正、梯度有效。若 `d(a,n) < d(a,p)` 才叫 hard；若 `d(a,n) ≥ 0.7` 则是简单负例，损失为 0。

### Q4 — 答案：C

讲义原话：recall@10 > 0.95 而 recall@1 < 0.5 说明"embedding 空间结构正确，但排序有噪声"，可以更长时间微调或加重排步骤。工业上常用两阶段：向量召回 Top-K，再用更强的模型（如交叉编码器或局部特征几何验证）对候选重排。A、B 没有依据；D 是"粉饰指标"，不解决问题。

### Q5 — 答案：B

讲义区分了两类问题：类别级（"找猫"）现成特征就很好；实例级（"找这一件商品"）需要在同类、外观相近的物体之间做细粒度区分，现成 embedding 表现不佳，需要用实例级标注做 triplet / InfoNCE 微调。A、C 是类别级；D 是图文检索，CLIP 直接可用。

### Q6 — 答案：C

讲义：约 1M 以内用 Flat；约 10M 用 `IndexIVFFlat`；1 亿以上结合乘积量化用 `IndexIVFPQ`。2 亿 × 512 × 4 字节 ≈ 410 GB，Flat 索引既放不进内存、暴力搜索也太慢；PQ 把每个向量压缩到几十字节。D 的暴力矩阵乘法本质上就是 Flat 索引。

### Q7 — 答案：B

讲义："For duplicate detection, precision@K matters more because every false positive is a user-visible mistake."去重是"宁可漏、不可错"的场景（误判会把不同图片当重复删除或合并）；视觉搜索才以 recall@K 为核心产品信号。

### Q8 — 答案：B

讲义表格：Proxy-based "Requires: Class labels only；Pros: Fast, stable, no mining；Cons: Can overfit to proxies on small datasets"。A 是 triplet；C 是 InfoNCE 的缺点；D 无依据。

### Q9 — 参考答案

**1. 索引：** `pos_idx = [1, 0, 3, 2]`，`neg_idx = [2, 2, 0, 1]`，anchor 1 和 anchor 3 触发 `fallback`。

| anchor | 最难正例（`d_ap`） | semi-hard 窗口 `(d_ap, d_ap+0.2)` 里的负例 | 选中的负例 | 是否回退 |
|--------|------------------|------------------------------------------|-----------|---------|
| 0 | 1（0.50） | (0.50, 0.70)：样本 2（0.55） | 2 | 否 |
| 1 | 0（0.50） | (0.50, 0.70)：无（样本 2 是 0.30，太近；样本 3 是 0.80，太远） | 最难负例 2（0.30） | 是 |
| 2 | 3（0.40） | (0.40, 0.60)：样本 0（0.55） | 0 | 否 |
| 3 | 2（0.40） | (0.40, 0.60)：无（0.90、0.80 都超出窗口） | 最难负例 1（0.80） | 是 |

**2. 损失：** `max(0, d_ap - d_an + 0.2)`：

- anchor 0：0.50 - 0.55 + 0.2 = **0.15**
- anchor 1：0.50 - 0.30 + 0.2 = **0.40**（负例比正例还近，hard）
- anchor 2：0.40 - 0.55 + 0.2 = **0.05**
- anchor 3：0.40 - 0.80 + 0.2 = -0.2 → **0**（回退后的最难负例依然足够远，已满足约束）

batch 平均 = (0.15 + 0.40 + 0.05 + 0) / 4 = **0.15**。（我用 NumPy 按同样的逻辑复现过，结果一致。）

注意 anchor 1：semi-hard 窗口为空时，代码回退到"最难负例"，这个负例比正例还近，损失最大——回退机制保证了"已经出错的样本"不会被漏掉。

### Q10 — 参考答案

- **会发生什么**：该 anchor 那一行的 `positives` 全部被设成 `-inf`（异类被 mask，对角线也被 `fill_diagonal_`），`argmax` 在全相等时返回**第一个下标 0**。于是 `pos_idx` 指向样本 0——它可能是**其他类别**的样本，甚至就是 anchor 自己（当 anchor 就是 0 号时）。
- **影响**：若样本 0 是异类，triplet loss 会把 anchor **拉向一个异类样本**，梯度方向完全错误；若是自己，`d_ap ≈ 0`，等于只在推远负例。随后 `d_ap` 也错了，semi-hard 窗口跟着错。
- **常见吗**：6 类、batch 48 时，某个 anchor 的类别在其余 47 个样本中一个都没有的概率是 `(5/6)^47 ≈ 2×10⁻⁴`，在本例中极少发生；但类别数多（如人脸 re-ID 上万个身份）、随机采样时会非常常见。
- **修复**：
  1. 采样层面：用 **P×K 采样**（每个 batch 选 P 个类、每类 K 张，K ≥ 2），从根本上保证每个 anchor 都有正例（Hermans et al. 2017 的做法）；
  2. 代码层面：记录有效 anchor 并只对它们计算损失：

```python
    has_pos = (same_class & ~torch.eye(N, dtype=torch.bool, device=emb.device)).any(dim=1)
    # ... 原有挖掘逻辑 ...
    return pos_idx, neg_idx, has_pos

# 训练时：
pos_idx, neg_idx, valid = semi_hard_negatives(emb, y)
loss = triplet_loss(emb[valid], emb[pos_idx[valid]], emb[neg_idx[valid]])
```

同理，如果整个 batch 只有一个类，`hardest` 全是 `inf`，负例也会退化成下标 0，同样需要过滤。

### Q11 — 参考答案

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class ProxyLoss(nn.Module):
    def __init__(self, num_classes, emb_dim, scale=16.0):
        super().__init__()
        self.proxies = nn.Parameter(torch.randn(num_classes, emb_dim))  # 每类一个代理
        self.scale = scale

    def forward(self, emb, labels):
        p = F.normalize(self.proxies, dim=-1)
        e = F.normalize(emb, dim=-1)
        logits = self.scale * e @ p.T          # (N, C)：样本与每个代理的余弦 × scale
        return F.cross_entropy(logits, labels)


# 在 main() 中替换：
# proxy_loss = ProxyLoss(num_classes, 64)
# opt = torch.optim.Adam(list(enc.parameters()) + list(proxy_loss.parameters()), lr=3e-3)
# ...
# loss = proxy_loss(enc(x), y)
```

要点：

- **代理也是参数**，必须加入优化器，否则代理永远是随机向量。
- **`scale` 的作用**等同于 CLIP 的温度：余弦只在 [-1, 1]，不放大的话 softmax 过于平坦、梯度弱；太大则过于尖锐、不稳定。常见取值 10–30，也可设为可学习参数。
- 不需要挖掘，每个样本一次就和**所有类**比较，所以收敛通常比 triplet 快；代价是类别数极大（百万 SKU）时代理矩阵很大，且每个类需要足够样本，否则代理会过拟合。
- 严格意义上的原始 ProxyNCA 在分母中排除正类代理（NCA 形式），这里用的是讲义描述的"标准交叉熵"版本（也常被称为 Normalized Softmax）。

### Q12 — 参考回答要点

| 损失 | 监督信号 | 优点 | 缺点 | 适用 |
|------|---------|------|------|------|
| Contrastive（成对） | (x1, x2, 是否相似) | 简单，任何"成对标签"都能用 | 负例少时收敛慢；margin 难调 | 有成对标注、规模小 |
| Triplet | (a, p, n) | 直观，直接控制相对 margin | 需要挖掘，组合数爆炸，挖掘成本高 | 人脸、re-ID、实例检索微调 |
| InfoNCE / NT-Xent | 正例对 + batch 内其他样本作负例 | 一次利用 N-1 个负例，适合大规模 | 需要大 batch 或动量队列（MoCo） | 自监督预训练、图文对齐（CLIP） |
| Proxy-based | 仅类别标签 | 快、稳、无需挖掘 | 小数据易过拟合代理；类别极多时代理矩阵大 | 有类别标签、类别数中等 |

- **工程建议（讲义）**：先用预训练骨干（DINOv2 / CLIP）在自己的测试集上评估，只有现成 embedding 不够好时才加度量学习微调。
- **加分点**：指出这些损失之间的联系——InfoNCE 可看作"多负例的 softmax 版对比损失"，proxy 损失可看作"把负例换成类中心"的 InfoNCE。

### Q13 — 参考回答要点

- **为什么要挖掘**：随机三元组中绝大多数负例已经很远，`d(a,n) > d(a,p) + margin`，损失为 0、梯度为 0，训练很快就"无事可做"。只有难的三元组才提供信息。
- **为什么不用 hardest**：每次都选最近的负例，容易选到标注错误的样本或本身就难以区分的离群点，梯度噪声大；训练早期还可能导致**塌缩**（所有 embedding 挤到一点，`d(a,p) = d(a,n) = 0`，损失卡在 margin）。FaceNet 发现 semi-hard（比正例远、但在 margin 内）更稳定，至今仍是 triplet 的默认配方。
- **batch-hard**（Hermans et al. 2017，讲义推荐阅读）：用 P×K 采样，每个 anchor 在 batch 内取最难正例和最难负例；配合合理的 batch 结构，在 person re-ID 上效果很好。本节代码的"最难正例 + semi-hard 负例 + 回退最难负例"可以看作两者的折中。
- **常见误区**：在单位向量上用很大的 margin（如 1.0）——归一化后的距离最大只有 2，margin 要与距离尺度匹配。

### Q14 — 参考回答要点

- **数据**：以 SKU 为实例标签；同一 SKU 的多视角商品图 + 用户实拍图构成正例；同品类相似款作为难负例。用户实拍（query）与商家白底图（gallery）存在明显域差异，训练数据必须覆盖这两种域。
- **模型**：讲义配方——DINOv2 骨干 + embedding 头，用 triplet 或 InfoNCE 在实例级标注上微调；可先做主体检测、裁剪商品区域再编码。
- **索引**：5000 万 × 768 维 float32 ≈ 150 GB，需 IVF + PQ 或 HNSW 等压缩/近似索引，并做分片；向量 L2 归一化后用内积。
- **两阶段**：向量召回 Top-K（如 200）→ 重排（更强的模型、局部特征几何验证、类目/价格等业务特征）→ 返回结果。
- **评测**：留出查询集（用户实拍），报告 recall@1/5/10；按 SKU 而不是按图片划分训练/测试，防止同一 SKU 泄漏；线上看点击、加购转化。
- **上线**：新商品增量编码入库；模型升级需全量重建索引（新旧向量空间不兼容）；监控召回率与延迟。

### Q15 — 参考回答要点

- **常见坑**：
  - 用 `IndexFlatIP` 却没有 L2 归一化——变成内积检索，范数大的向量"霸榜"；
  - 训练用余弦、检索用 L2（或反之）而向量又没归一化，"最近"的含义悄悄变了（讲义："mixing them silently changes what 'nearest' means"）；
  - IVF 类索引需要 `train`，训练样本要有代表性、数量足够；
  - 查询和库用了不同的编码器版本或预处理；
  - 返回的分数语义不同：IP 越大越近，L2 越小越近，混用会把排序弄反。
- **选型**（讲义）：Flat 精确、约 1M 以内；IVFFlat 约 10M 量级；HNSW 查询快、索引占用大；1 亿以上用 IVFPQ。
- **`nprobe`**：IVF 把向量分成 nlist 个桶，查询时只搜最近的 nprobe 个桶。nprobe 越大召回越高、越慢；做法是在验证集上画"recall vs 延迟"曲线，取满足延迟预算的最小 nprobe。
- **加分点**：用 Flat 索引的结果作为"真值"来评估近似索引的召回损失，把"模型误差"和"索引误差"分开。

### Q16 — 参考回答要点

- **评测本身有问题**：
  - 离线是类别级 recall（同类即算对），线上用户要的是实例级（同款）——本节的 `recall_at_k` 就是"标签相同即算命中"；
  - 数据泄漏：同一实例/近重复图片同时出现在训练集与评测库中，或查询图本身就在库里；
  - 查询集分布与线上不符（离线用干净图，线上是模糊、遮挡、各种角度的实拍）。
- **系统问题**：线上与离线的预处理不一致（resize、色彩空间、归一化）；线上近似索引参数（nprobe、PQ 压缩）造成召回损失；模型更新后库里还是旧向量。
- **排查顺序**：抽样线上 bad case 人工标注 → 用同样的数据离线复现 → 分别用 Flat 与线上索引对比，定位"模型问题还是索引问题" → 检查预处理一致性 → 重建贴近线上的评测集。
- **加分点**：强调 recall@K 要搭配 precision、nDCG 和线上点击指标一起看。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 18 开放词表视觉——CLIP](../../18-open-vocab-clip/docs/zh.md)：InfoNCE 对比损失、图文共享空间，本节"以文搜图"的基础。
- [阶段 04 · 17 自监督视觉 — SimCLR、DINO、MAE](../../17-self-supervised-vision/docs/zh.md)：DINO 系列特征是讲义推荐的通用检索骨干。
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：余弦、L2 及单位向量下的等价关系。
- [阶段 02 · 06 KNN 与距离](../../../02-ml-fundamentals/06-knn-and-distances/docs/zh.md)：最近邻检索的基本思想。

### 本节被哪些后续内容用到
- [阶段 04 · 27 多目标跟踪与视频记忆](../../27-multi-object-tracking/docs/zh.md)：跟踪中的 re-ID 外观特征就是度量学习的产物。
- [阶段 05 · 14 信息检索与搜索](../../../05-nlp-foundations-to-advanced/14-information-retrieval-search/docs/zh.md)：文本检索中的同类指标与索引。
- [阶段 06 · 06 说话人识别与验证](../../../06-speech-and-audio/06-speaker-recognition-verification/docs/zh.md)：声纹 embedding 同样依赖度量学习。
- [阶段 11 · 04 Embeddings](../../../11-llm-engineering/04-embeddings/docs/zh.md) 与 [阶段 11 · 06 RAG](../../../11-llm-engineering/06-rag/docs/zh.md)：向量检索在 LLM 应用中的核心角色。
- [阶段 19 · 66 交叉编码器重排](../../../19-capstone-projects/66-reranker-cross-encoder/docs/zh.md)：本节提到的"召回 + 重排"两阶段架构。
- [阶段 19 · 68 RAG 评测：精确率与召回率](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md)：检索评测指标的系统化。

### 延伸关键词
`FaceNet` · `batch-hard / P×K sampling` · `ProxyNCA / Normalized Softmax` · `ArcFace / CosFace` · `MoCo 动量队列` · `DINOv2` · `FAISS (IVF / HNSW / PQ)` · `nprobe` · `re-ranking / geometric verification` · `mAP / nDCG`
