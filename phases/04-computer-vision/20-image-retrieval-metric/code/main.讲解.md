# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 20 节 图像检索和度量学习 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，全程 CPU） ｜ **依赖**：`torch`（`torch.nn`、`torch.nn.functional`）；无需 NumPy、FAISS 或联网

---

## 1. 这份代码在考察什么

度量学习的全部要素都浓缩在这 90 行里：

1. **Triplet loss**：用"锚点–正例–负例"三元组和 margin 塑造 embedding 空间。
2. **难例挖掘**：在 batch 内为每个 anchor 选"最难正例"和"semi-hard 负例"，选不到时回退到"最难负例"——这一块是本文件最值得逐行读懂的代码。
3. **向量化编程**：用 `cdist`、布尔掩码、`inf` 填充、`argmin/argmax`、`torch.where` 在一个 N×N 矩阵上一次性完成所有 anchor 的挖掘，没有 Python 循环。
4. **Recall@K 评测**：用 `topk` + 标签比较实现检索系统最常用的指标。
5. **L2 归一化的 embedding**：编码器输出单位向量，让距离、余弦和 margin 都在一个固定尺度上。

> 一句话：**度量学习 = 一个编码器 + 一个"拉近/推远"的损失 + 一个挑选"有教育意义的样本"的挖掘策略**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `triplet_loss(anchor, positive, negative, margin=0.2)` | 函数 | `relu(d_ap - d_an + margin).mean()` | Triplet loss |
| `semi_hard_negatives(emb, labels, margin=0.2)` | 函数 | 为每个 anchor 返回最难正例下标、semi-hard 负例下标（必要时回退到最难负例） | 难例挖掘（FaceNet） |
| `recall_at_k(...)` | 函数 | 计算 Top-K 中至少有一个同类结果的查询比例 | Recall@K |
| `Encoder` | `nn.Module` 类 | 128 → 128 → 64 的 MLP，输出 L2 归一化 | embedding 模型 |
| `main()` | 演示入口 | 6 类原型 + 噪声的合成数据，训练 200 步，再在 200 个库样本、50 个查询上测 recall@1/5/10 | 端到端训练与评测 |

数据流：`sample()` 生成 `(x, y)` → `enc(x)` 得到单位向量 → `semi_hard_negatives` 选出下标 → 用下标从同一个 `emb` 里取正例、负例 → `triplet_loss` → 反向传播；训练完后 `recall_at_k` 评估。

---

## 3. 逐段精讲

### 3.1 Triplet loss

```python
def triplet_loss(anchor, positive, negative, margin=0.2):
    d_ap = F.pairwise_distance(anchor, positive, p=2)
    d_an = F.pairwise_distance(anchor, negative, p=2)
    return F.relu(d_ap - d_an + margin).mean()
```

- `F.pairwise_distance(x1, x2, p=2)` 按行计算 L2 距离：输入都是 `(N, d)`，输出 `(N,)`。（PyTorch 实现里会给差值加一个很小的 `eps=1e-6`，避免距离为 0 时开方的梯度出问题。）
- `F.relu(z)` 就是 `max(0, z)`，所以每个三元组的损失是 `max(0, d_ap - d_an + margin)`：
  - 负例已经比正例远出 margin → 损失 0，不产生梯度（简单负例）；
  - 否则 → 损失为正，梯度把 anchor 拉向正例、推离负例。
- ⚠️ 与讲义公式的差别：讲义写的是**平方**距离 `‖f(a)-f(p)‖² - ‖f(a)-f(n)‖² + margin`（FaceNet 原论文的形式），代码用的是**不平方**的距离（讲义 Step 1 的代码也是如此）。两种写法都常见，但同一个 margin 在两种写法下含义不同，调参时要注意自己用的是哪一种。
- 因为编码器输出单位向量，距离的取值在 [0, 2]，`margin = 0.2` 相对这个尺度是合理的；如果 embedding 不归一化，margin 就失去了固定的参照。

### 3.2 挖掘第一步：每个 anchor 的"最难正例"

```python
def semi_hard_negatives(emb, labels, margin=0.2):
    dist = torch.cdist(emb, emb)
    same_class = labels[:, None] == labels[None, :]
    N = emb.size(0)

    positives = dist.clone()
    positives[~same_class] = float("-inf")
    positives.fill_diagonal_(float("-inf"))
    pos_idx = positives.argmax(dim=1)
```

- `torch.cdist(emb, emb)`：`(N, N)` 的两两 L2 距离矩阵，第 (i, j) 个元素是样本 i 与样本 j 的距离。
- `labels[:, None] == labels[None, :]`：**广播**出 `(N, N)` 的布尔矩阵，"i 与 j 同类"为 True（对角线自然也是 True）。
- 找最难正例的套路是"**把不想要的位置填成永远不会被选中的值，再取极值**"：
  - 异类位置填 `-inf`（`~same_class` 是按位取反）；
  - 对角线（自己和自己，距离 0）也填 `-inf`，`fill_diagonal_` 末尾的下划线表示**原地修改**；
  - 剩下的都是同类、非自身的样本，`argmax` 取**距离最大**的那个——即"最难（最远）正例"。
- 为什么先 `clone()`：后面还要用原始 `dist`，原地修改前必须复制一份。
- ⚠️ 边界情况：如果某个 anchor 在 batch 里没有任何同类样本，这一行全是 `-inf`，`argmax` 返回下标 0——可能是一个异类样本，甚至是 anchor 自己，产生错误的梯度。本例 6 类、batch 48，发生概率约 `(5/6)^47 ≈ 2×10⁻⁴`，几乎碰不到；类别多时要用 P×K 采样或过滤无效 anchor（见测验 Q10）。

### 3.3 挖掘第二步：semi-hard 负例窗口

```python
    # Semi-hard: d_ap < d_an < d_ap + margin. Exclude same-class, diagonals,
    # negatives closer than the positive, and those past the margin boundary.
    semi_hard = dist.clone()
    semi_hard[same_class] = float("inf")
    d_ap = dist[torch.arange(N), pos_idx].unsqueeze(1)
    semi_hard[dist <= d_ap] = float("inf")
    semi_hard[dist >= d_ap + margin] = float("inf")
    neg_idx = semi_hard.argmin(dim=1)
```

- 这次要找最小值，所以把不合格的位置填 `+inf`，四道过滤：
  1. `same_class`（含对角线）→ 不是负例；
  2. `dist <= d_ap` → 比正例还近，是 hard 负例，不在 semi-hard 范围；
  3. `dist >= d_ap + margin` → 已经远出 margin，是简单负例；
  4. 剩下的就是 `d_ap < d_an < d_ap + margin` 的 semi-hard 负例。
- `dist[torch.arange(N), pos_idx]` 是**成对的高级索引**：取第 i 行第 `pos_idx[i]` 列，得到每个 anchor 的 `d_ap`，形状 `(N,)`；`.unsqueeze(1)` 变成 `(N, 1)`，才能和 `(N, N)` 的 `dist` 按行广播比较。
- `argmin` 在 semi-hard 窗口里选**最近**的那个，即"最难的 semi-hard 负例"。
- 对比讲义 Step 2 的代码：讲义版本**少了第 3 道过滤**（`dist >= d_ap + margin`），与它自己"within margin"的文字描述不一致；`main.py` 补上了这一行，是更忠实于定义的实现。

### 3.4 挖掘第三步：没有 semi-hard 时回退到最难负例

```python
    fallback = semi_hard[torch.arange(N), neg_idx] == float("inf")
    if fallback.any():
        hardest = dist.clone()
        hardest[same_class] = float("inf")
        neg_idx = torch.where(fallback, hardest.argmin(dim=1), neg_idx)
    return pos_idx, neg_idx
```

- 若一行全是 `inf`，`argmin` 返回 0，而且该位置的值仍是 `inf`——用这个特征识别"窗口为空"的 anchor，得到布尔向量 `fallback`。
- 对这些 anchor，改用"所有异类中最近的那个"（最难负例）。两种情况：
  - 所有负例都在 margin 之外 → 最难负例也很远，损失为 0，正常；
  - 有负例比正例还近，但窗口内没有 → 回退选中这个 hard 负例，损失最大，**确保已经出错的样本被纠正**。
- `torch.where(cond, a, b)`：按元素选择，`cond` 为 True 取 `a`，否则取 `b`。
- `if fallback.any()` 只是省一次计算的小优化。
- 设计权衡：纯 semi-hard 更稳定（FaceNet 结论），但会漏掉 hard 负例；纯 hardest 学得猛但易塌缩。这里的组合是两者的折中。

### 3.5 Recall@K

```python
def recall_at_k(query_emb, gallery_emb, query_labels, gallery_labels, k=1):
    sim = query_emb @ gallery_emb.T
    _, top_k = sim.topk(k, dim=-1)
    matches = (gallery_labels[top_k] == query_labels[:, None]).any(dim=-1)
    return matches.float().mean().item()
```

- `sim (Q, G)`：查询与库的内积。因为两边都是单位向量，内积 = 余弦；按讲义的恒等式 `‖a-b‖² = 2 - 2cos`，余弦 Top-K 也就等于 L2 最近 Top-K。
- `sim.topk(k, dim=-1)` 返回 `(值, 下标)`，下标形状 `(Q, k)`。
- `gallery_labels[top_k]`：用 `(Q, k)` 的下标张量去索引一维标签，得到 `(Q, k)` 的"命中样本的标签"。
- `== query_labels[:, None]` 广播比较，`.any(dim=-1)` 判断每个查询的 Top-K 里**是否至少一个同类**。
- `.float().mean()` 得到命中比例，`.item()` 转成 Python 数。
- ⚠️ 这是**类别级** recall：只要标签相同就算命中。实例级检索（找同一件商品）需要实例 ID 作为标签。另外，查询和库是分别采样的，查询不在库中，所以不会出现"自己检索到自己"的虚高。

### 3.6 编码器

```python
class Encoder(nn.Module):
    def __init__(self, in_dim=128, emb_dim=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, 128), nn.ReLU(),
            nn.Linear(128, emb_dim),
        )

    def forward(self, x):
        return F.normalize(self.net(x), dim=-1)
```

- 两层 MLP，把 128 维输入映射到 64 维 embedding，最后 L2 归一化——所有输出都在单位球面上。
- ⚠️ 简化：真实系统的编码器是 DINOv2 / CLIP 之类的大骨干，度量学习一般只在其上加一个 embedding 头做微调（讲义 "Use It" 部分的配方）。

### 3.7 训练与评测主流程

```python
    torch.manual_seed(0)
    num_classes = 6
    dim = 128
    protos = F.normalize(torch.randn(num_classes, dim), dim=-1)

    def sample(bs=48):
        labels = torch.randint(0, num_classes, (bs,))
        x = protos[labels] + 0.15 * torch.randn(bs, dim)
        return x, labels
    # ...
    for step in range(200):
        x, y = sample(48)
        emb = enc(x)
        pos_idx, neg_idx = semi_hard_negatives(emb, y)
        loss = triplet_loss(emb, emb[pos_idx], emb[neg_idx])
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 40 == 0:
            print(f"step {step:3d}  triplet {loss.item():.4f}")
```

- 数据：6 个随机单位向量作类原型，每个样本 = 原型 + `0.15 × N(0, I)` 噪声。注意 128 维噪声的总范数约 `0.15 × √128 ≈ 1.7`，比原型本身还大；但沿"区分两个类"的方向上噪声标准差只有 0.15，而两个原型相距约 √2。所以类别是可分的，编码器要学的是"压掉与类别无关的噪声方向"。
- 每步：前向得到 `emb` → 在**同一个 batch 内**挖掘 → `emb[pos_idx]`、`emb[neg_idx]` 用下标取出正例、负例（不需要另外采样三元组）→ 损失。
- 梯度从三个位置（anchor、正例、负例）都流回编码器，因为它们都来自同一个 `emb`。挖掘本身（`argmin/argmax`）不可导，只决定"用谁"。
- 讲义 Step 4 用的是 batch 32、`torch.manual_seed` 写在外面，`main.py` 改成了 batch 48 并封装进 `main()`，逻辑相同。

```python
    enc.eval()
    with torch.no_grad():
        gx, gy = sample(200)
        g_emb = enc(gx)
        qx, qy = sample(50)
        q_emb = enc(qx)
        for k in [1, 5, 10]:
            r = recall_at_k(q_emb, g_emb, qy, gy, k=k)
            print(f"  recall@{k}: {r:.3f}")
```

- 200 个库样本（每类约 33 个）、50 个查询。`enc.eval()` 对这个没有 Dropout/BN 的模型没有实际影响，但是好习惯。
- recall@K 随 K **单调不减**（Top-5 包含 Top-1），所以三行数字一定是非递减的。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 输出 L2 归一化 | 距离有界（[0, 2]），margin 有固定含义；内积 = 余弦 | 丢失范数信息（有时范数能表示置信度） |
| 不平方的 L2 距离 | 与讲义代码一致，直观 | FaceNet 用平方距离；换写法要重调 margin |
| batch 内挖掘（online mining） | 无需离线构造三元组，每步都基于最新的 embedding | 依赖 batch 内有足够的同类样本 → 生产用 P×K 采样 |
| 最难正例 + semi-hard 负例 + 回退 | 兼顾稳定性与对错误样本的纠正 | 超参数（margin）敏感；也可用 batch-hard 或 InfoNCE |
| 掩码 + `inf` + `argmin/argmax` 向量化 | 无 Python 循环，GPU 友好 | N×N 矩阵显存随 batch 平方增长 |
| 类别级 recall@K | 合成数据只有类别标签 | 实例级检索要用实例 ID；大规模用 FAISS 而不是全量矩阵乘 |
| 两层 MLP 编码器 | CPU 几秒可训练 | 生产用 DINOv2 / CLIP 骨干 + embedding 头微调 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def triplet_loss(..., margin=0.2)`、`def sample(bs=48)` | 调用时可省略 |
| 类继承与 `super()` | `class Encoder(nn.Module)`、`super().__init__()` | 继承 `nn.Module` 才能自动注册参数 |
| `float("inf")` / `float("-inf")` | `positives[~same_class] = float("-inf")` | 正负无穷，常用作"永远不会被选中"的填充值 |
| 元组解包与 `_` | `_, top_k = sim.topk(k, dim=-1)`、`x, y = sample(48)` | 丢弃不需要的返回值 |
| 嵌套函数 / 闭包 | `main` 里的 `sample` 读取外层的 `protos`、`dim` | 内层函数访问外层局部变量 |
| `with` 上下文管理器 | `with torch.no_grad():` | 块内不记录梯度 |
| `for` 遍历列表 | `for k in [1, 5, 10]:` | 依次计算多个 K |
| f-string 格式符 | `{loss.item():.4f}`、`{step:3d}`、`recall@{k}: {r:.3f}` | 控制小数位与对齐 |
| 一行多语句 | `opt.zero_grad(); loss.backward(); opt.step()` | 分号分隔 |
| 张量广播比较 | `labels[:, None] == labels[None, :]` | `None` 插入新维度，`(N,1)` 与 `(1,N)` 广播成 `(N,N)` |
| 布尔掩码与取反 | `positives[~same_class] = ...`、`semi_hard[dist <= d_ap] = ...` | 用布尔矩阵选元素并赋值；`~` 对布尔张量取反 |
| 成对高级索引 | `dist[torch.arange(N), pos_idx]` | 取 `(i, pos_idx[i])` 位置的元素 |
| 原地方法（下划线后缀） | `positives.fill_diagonal_(...)` | PyTorch 约定：以 `_` 结尾的方法原地修改张量 |
| `torch.where` | `torch.where(fallback, hardest.argmin(dim=1), neg_idx)` | 按条件逐元素二选一 |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 挖掘逻辑我用 NumPy 按完全相同的步骤复现，并在一个 4 样本的手工距离矩阵上验证过（见测验 Q9）。根据代码，输出格式如下（具体数值依赖 PyTorch 随机数，这里不编造）：

```text
step   0  triplet ?.????
step  40  triplet ?.????
step  80  triplet ?.????
step 120  triplet ?.????
step 160  triplet ?.????
  recall@1: ?.???
  recall@5: ?.???
  recall@10: ?.???
```

可以确定或合理预期的部分：

- 训练日志 5 行（step 0、40、80、120、160）。损失量级在 margin（0.2）附近或以下：每个三元组损失 = `max(0, d_ap - d_an + 0.2)`，而且挖掘只挑"有损失"的负例。随着各类聚成紧凑的簇、类间距离超过 margin，semi-hard 窗口变空、回退到的最难负例也足够远，损失会趋向 0。
- 三个 recall 一定满足 `recall@1 ≤ recall@5 ≤ recall@10`。
- 类别在"区分方向"上的信噪比很高（原型间距约 1.41，噪声标准差 0.15），训练后 recall 预期很高、可能接近 1.0；这只是类别级检索，比真实的实例级检索容易得多。具体数值需实际运行确认。

---

## 7. 动手改一改

1. **可视化**（讲义练习 1）：训练前后各取 300 个样本的 embedding，用 PCA 降到 2 维画散点图，观察 6 个簇的形成。
2. **挖掘策略消融**：分别换成"随机负例"、"只用最难负例"、"本文件的 semi-hard + 回退"，比较损失曲线和 recall@1；再把噪声从 0.15 加到 0.6 重复一次。
3. **平方距离版本**：把 `triplet_loss` 改成平方距离（与讲义公式一致），观察同一 margin 下的训练效果差异，并重新调 margin。
4. **修复边界情况**：实现 P×K 采样器（每 batch 6 类 × 8 张），并给 `semi_hard_negatives` 加上"无正例 anchor"的过滤（见测验 Q10）。
5. **ProxyNCA**（讲义练习 2）：实现测验 Q11 的 `ProxyLoss`，与 triplet 比较达到相同 recall@1 所需的步数。
6. **接 FAISS**：把 `g_emb` 转成 `float32` NumPy 数组放进 `faiss.IndexFlatIP`，验证检索结果与 `recall_at_k` 的矩阵乘法版本一致。

---

## 8. 常见坑

- **忘记 L2 归一化**：用内积当余弦，范数大的向量会"霸榜"；margin 也失去固定尺度。
- **挖掘前修改了原矩阵**：没有 `clone()` 就原地填 `inf`，后面用到的 `dist` 已经被破坏。
- **batch 里没有正例**：`argmax` 在全 `-inf` 行上返回 0，悄悄选到错误的"正例"；用 P×K 采样避免。
- **只用最难负例**：训练早期容易塌缩（所有 embedding 挤成一团，损失卡在 margin 附近）。
- **margin 与距离尺度不匹配**：单位向量距离最大为 2，margin 设成 1.0 往往太大；平方距离与非平方距离的 margin 也不能混用。
- **把类别级 recall 当成实例级效果**：本文件的 recall@K 只要求"同类"，实际业务"找同款"要严格得多。
