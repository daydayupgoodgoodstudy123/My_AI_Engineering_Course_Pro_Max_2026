# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 19 节 视觉 Autoregressive 建模（VAR）：下一尺度预测 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：NumPy（讲义头部写的是 "Python (with PyTorch)"，但代码实际只用了 NumPy，不需要 PyTorch）

---

## 1. 这份代码在考察什么

这是一个**极简的 VAR 骨架**：不训练神经网络，用 k-means 标量码本做 tokenizer、用"条件直方图"代替 transformer，但保留了 VAR 的三个结构性要素：

1. **多尺度残差 VQ**：8×8 灰度图被拆成 1×1、2×2、4×4、8×8 四级 token，第 k 级编码前面各级没表达出来的残差，解码 = 各级上采样后求和。
2. **尺度间因果的训练数据**：第 k 级的预测只以第 1..k−1 级为条件（`stream[:k]`）。
3. **尺度内并行的采样**：每一级的所有位置在"一次前向"里同时采样，生成一张图只需 4 次"前向"。
4. **序列长度账**：打印每一级在条件中能看到多少前序 token（0 / 1 / 5 / 21）。

同时，它也是一份很好的"反面教材"：生成部分几乎是随机的，而程序只打印形状和数值范围——读懂它为什么失败，比读懂它怎么运行更有价值。

> 一句话：**这份代码搭好了 VAR 的"脚手架"（多尺度 tokenizer + 尺度顺序 + 尺度内并行），但它的"大脑"只是一张查表，所以能重建却几乎不会生成。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `IMG`、`SCALES`、`CODEBOOK` | 常量 | 图像 8×8；尺度 (1,2,4,8)；每级 16 个码字 | 尺度表、码本大小 |
| `make_patterns(rng, n)` | 函数 | 从 5 种图案（纯色、渐变、圆环、棋盘、十字）随机生成 n 张 8×8 图 | 玩具数据集 |
| `fit_codebook(samples, k)` | 函数 | 对标量做 k-means，返回排序后的 k 个码字 | 码本学习 |
| `encode(values, codebook)` | 函数 | 每个值映射到最近码字的下标 | 量化（VQ） |
| `downsample` / `upsample` | 函数 | 平均池化 / 最近邻放大 | 尺度变换 |
| `tokenize_multiscale(img, codebooks)` | 函数 | 逐级量化残差，返回 4 个 token 网格 | 残差 VQ 编码 |
| `detokenize_multiscale(tokens, codebooks)` | 函数 | 各级码字上采样后求和 | 解码 |
| `train_codebooks(images)` | 函数 | 按尺度顺序逐级在残差上拟合码本 | tokenizer 训练 |
| `context_key(prev_tokens)` | 函数 | 把前序各级压成一个可哈希的元组 | 条件上下文（极简版） |
| `fit_predictor(token_streams)` | 函数 | 每级一个"上下文 → token 直方图"的字典 | 代替 transformer |
| `sample_categorical` / `generate` | 函数 | 逐级查表并并行采样，最后解码 | 下一尺度生成 |
| `reconstruction_mse` | 函数 | 编码再解码的平均 MSE | tokenizer 质量 |
| `main()` | 入口 | 训练 tokenizer 与预测器、打印重建误差、生成 3 次、打印注意力账 | — |

数据流：`make_patterns → train_codebooks → tokenize_multiscale（得到 token 流）→ fit_predictor → generate（K 次查表 + 并行采样）→ detokenize_multiscale`。

---

## 3. 逐段精讲

### 3.1 全局常量与玩具数据

```python
IMG = 8
SCALES = (1, 2, 4, 8)
CODEBOOK = 16


def make_patterns(rng: np.random.Generator, n: int) -> np.ndarray:
    """Return n grayscale 8x8 patterns drawn from a tiny library."""
    out = np.zeros((n, IMG, IMG), dtype=np.float32)
    yy, xx = np.mgrid[0:IMG, 0:IMG].astype(np.float32)
    for i in range(n):
        kind = int(rng.integers(0, 5))
        if kind == 0:
            out[i] = rng.uniform(0.1, 0.9)
        elif kind == 1:
            out[i] = (xx + yy) / (2 * (IMG - 1))
        # ... kind 2 圆环、kind 3 棋盘
        else:
            mid = IMG // 2
            cross = ((xx == mid) | (yy == mid)).astype(np.float32)
            out[i] = cross * 0.9 + 0.05
    return out
```

- 尺度表每级翻倍，最后一级 8×8 就是**全分辨率**。⚠️ 这与真实 VAR 不同：真实 VAR 在 VAE 潜空间上做（最后一级是 `H/p × W/p`，256² 时为 16×16），尺度表也更密（skill 文件示例为 1,2,3,4,5,6,8,10,13,16）。
- `np.mgrid[0:IMG, 0:IMG]` 一次生成行坐标网格 `yy` 和列坐标网格 `xx`，后面用它们向量化地画渐变、圆环、棋盘和十字，不需要逐像素循环。
- 5 种图案的频率特性差别很大：纯色只有直流分量；渐变、圆环以低频为主；棋盘是最高频（每个 2×2 块的均值都是 0.5）；十字介于两者之间。这让"粗尺度能看到什么"变得很直观。
- 所有像素都落在 [0, 1] 内——这是后面判断"生成结果是否合理"的一个简单依据。
- ⚠️ 讲义 Build It 写的是 "2D Gaussian rings" 数据和 "VAR-style transformer"，与这份代码（图案库 + 直方图）不一致，以代码为准。

### 3.2 `fit_codebook` 与 `encode`：一维 k-means 量化

```python
def fit_codebook(samples, k, iters=30, seed=0):
    rng = np.random.default_rng(seed)
    flat = samples.reshape(-1)
    if flat.size < k:
        raise ValueError(f"need >= {k} samples for codebook init, got {flat.size}")
    idx = rng.choice(flat.size, size=k, replace=False)
    centers = flat[idx].astype(np.float32)
    for _ in range(iters):
        dists = (flat[:, None] - centers[None, :]) ** 2
        assign = dists.argmin(axis=1)
        for j in range(k):
            mask = assign == j
            if mask.any():
                centers[j] = flat[mask].mean()
    return np.sort(centers)


def encode(values, codebook):
    dists = (values[..., None] - codebook[None, None, :]) ** 2
    return dists.argmin(axis=-1).astype(np.int32)
```

- 标准 Lloyd k-means：随机选 k 个样本做初始中心 → 每个样本分配给最近中心 → 中心更新为簇均值，重复 30 次。
- **广播求距离**：`flat[:, None]` 形状 `(N, 1)`，`centers[None, :]` 形状 `(1, k)`，相减得到 `(N, k)` 的距离矩阵，一行代码完成所有样本到所有中心的距离。`encode` 同理，`values[..., None]` 在最后加一维与码本对齐。
- `if mask.any()`：没有样本被分到的中心保持不变——这就是**死码（dead code）**。
- `np.sort(centers)`：排序后，token 下标的大小与码字数值的大小一致。这一点被 `context_key` 隐式利用（"平均 token 序号"约等于"平均亮度"）。
- ⚠️ 初始化用 `replace=False` 只保证选中的**下标**不重复，不保证**值**不重复。数据里有大量完全相同的值（例如所有渐变图在 1×1 级的均值都是 0.5），会选出重复的初始中心，最终码本里出现重复码字。我额外打印过码本：1×1 级的 16 个码字里有 6 个是 0.5、4 个约 0.263，有效码字远少于 16 个。真实 VQ 训练会用 k-means++ 初始化、死码重启、EMA 更新等方法维持**码本利用率**（skill 文件要求校准批上利用率 > 50%）。
- ⚠️ 这里是**标量**量化（每个 token 只代表一个灰度值）；真实 VQ 的码字是高维向量（如 32 维），tokenizer 还有编码器 / 解码器网络。

### 3.3 `downsample` / `upsample`：尺度之间的桥

```python
def downsample(img, target):
    h, w = img.shape
    if target == h:
        return img.copy()
    factor = h // target
    return img.reshape(target, factor, target, factor).mean(axis=(1, 3))


def upsample(grid, target):
    h, w = grid.shape
    if target == h:
        return grid.copy()
    factor = target // h
    return grid.repeat(factor, axis=0).repeat(factor, axis=1)
```

- **reshape 技巧做平均池化**：把 `(8, 8)` 看成 `(target, factor, target, factor)`，第 1、3 轴就是每个池化块内部的行列，对它们求均值即完成池化。例如 target=2 时 factor=4，`(2, 4, 2, 4)` 对轴 (1,3) 求均值得到 2×2。
- **最近邻上采样**：`repeat` 把每个元素沿行、沿列各复制 `factor` 次。
- 两者都要求尺寸整除（8 能被 1、2、4、8 整除）。⚠️ 真实 VAR 的尺度表（如 13、16）不能整除，需要双线性 / 区域插值；VAR 论文的上采样后还会接一个小卷积来减少插值伪影。
- `w` 解包后没有使用，只是为了与 `img.shape` 的二元组对齐（假定图像是方的）。

### 3.4 `tokenize_multiscale` / `detokenize_multiscale`：残差 VQ 的核心

```python
def tokenize_multiscale(img, codebooks):
    """Residual VQ: each scale tokenizes what previous scales missed."""
    residual = img.copy()
    tokens: list[np.ndarray] = []
    for scale, book in zip(SCALES, codebooks):
        coarse = downsample(residual, scale)
        tok = encode(coarse, book)
        recon = book[tok]
        residual = residual - upsample(recon, IMG)
        tokens.append(tok)
    return tokens


def detokenize_multiscale(tokens, codebooks):
    """Decoder: sum upsampled scale embeddings."""
    out = np.zeros((IMG, IMG), dtype=np.float32)
    for tok, book, scale in zip(tokens, codebooks, SCALES):
        out = out + upsample(book[tok], IMG)
    return out
```

这就是讲义公式 `f ≈ Σ_k upsample(embed(z_k))` 的直接实现：

| 步骤 | 代码 | 含义 |
|------|------|------|
| 看残差的粗略版本 | `coarse = downsample(residual, scale)` | 第 k 级只看"当前还没解释掉的部分"在该分辨率下的样子 |
| 量化 | `tok = encode(coarse, book)` | 得到 `scale×scale` 的整数 token 网格 |
| 查表还原 | `recon = book[tok]` | **花式索引**：用整数数组索引码本，得到同形状的码字值 |
| 更新残差 | `residual -= upsample(recon, IMG)` | 把这一级已解释的部分减掉 |

- 解码就是把每一级的 `upsample(book[tok], IMG)` 加起来。只要编码和解码用同一套 `upsample`，"编码时减掉的"和"解码时加回的"完全一致，误差只剩最后一级的量化误差。
- `book[tok]` 中 `tok` 是 int32 数组，NumPy 会返回与 `tok` 同形状的数组——这就是 embedding 查表（`nn.Embedding`）的标量版。
- 直观例子：棋盘格在 1×1、2×2、4×4 级下采样后处处是 0.5，三级只编码"整体亮度 0.5"，±0.5 的交替纹理全部留给 8×8 级——高频细节只能由细尺度表达。
- ⚠️ 与讲义的差异：讲义说"各级使用同一个码本"，这里每级各有一个码本（`codebooks` 是 4 个数组的列表）。对标量 VQ 而言分级码本更合理（粗级码字是亮度，细级码字是 ±残差），但 skill 文件默认共享码本，只在满足条件时才接受分级码本。

### 3.5 `train_codebooks`：按尺度顺序逐级训练

```python
def train_codebooks(images):
    residuals = images.copy()
    books: list[np.ndarray] = []
    for scale in SCALES:
        pooled = np.stack([downsample(r, scale) for r in residuals])
        book = fit_codebook(pooled, CODEBOOK)
        books.append(book)
        recon = np.stack([upsample(book[encode(p[None], book)[0]], IMG)
                          for p in pooled])
        residuals = residuals - recon
    return books
```

- 和 `tokenize_multiscale` 是同一套残差逻辑，只不过是对整个训练集"边走边拟合"：先用所有图的 1×1 均值拟合第 1 级码本，再在减掉第 1 级重建的残差上拟合第 2 级码本，以此类推。
- `p[None]` 把 `(s, s)` 变成 `(1, s, s)`，`encode(...)[0]` 再去掉这一维。⚠️ 这一对 `[None]`/`[0]` 其实多余——`encode` 对二维输入同样可以广播；去掉它们结果不变。
- 第 1 级 `pooled` 只有 64 个标量（64 张图各 1 个），要拟合 16 个码字，所以对重复值特别敏感（见 3.2）。
- ⚠️ 简化：真实多尺度 VQ tokenizer 是端到端训练的（编码器、量化器、解码器 + 感知损失 / 对抗损失），而不是逐级独立做 k-means。

### 3.6 `context_key` 与 `fit_predictor`：用直方图代替 transformer

```python
def context_key(prev_tokens):
    """Hashable summary of all previous scales' tokens."""
    return tuple(int(t.mean() * 1000) for t in prev_tokens) if prev_tokens else ()


def fit_predictor(token_streams):
    predictors = [{} for _ in SCALES]
    for stream in token_streams:
        for k in range(len(SCALES)):
            ctx = context_key(stream[:k])
            table = predictors[k].setdefault(ctx, np.ones(CODEBOOK, dtype=np.float64))
            for tok in stream[k].reshape(-1):
                table[int(tok)] += 1.0
    for table in predictors:
        for key, counts in table.items():
            table[key] = counts / counts.sum()
    return predictors
```

- **尺度间因果**体现在 `stream[:k]`：预测第 k 级时，上下文只来自第 0..k−1 级的**真实** token（teacher forcing），与 GPT 训练时用真实前缀预测下一个 token 完全同构。
- `context_key` 把每个前序尺度压成一个整数（平均 token 序号 ×1000 取整），整个上下文是一个元组，可以当字典键。因为码本已排序，平均序号大致反映平均亮度。
- `setdefault(ctx, np.ones(...))`：第一次遇到某个上下文时以全 1 计数初始化（**拉普拉斯平滑**），之后对第 k 级所有位置的 token 计数，最后归一化成概率。
- ⚠️ 两个关键简化，也是生成失败的根源：
  1. **上下文几乎不泛化**：64 张训练图只产生了 1 / 8 / 11 / 12 种上下文（我额外打印过）。生成时只要采样结果的平均序号与训练中任何一张图不完全相同，就查不到。
  2. **与位置无关**：同一级所有位置的 token 被混进同一个直方图，模型不知道"中心应该亮、角落应该暗"。
- 在遍历 `table.items()` 时给 `table[key]` 重新赋值是安全的：只改值、不增删键，不会触发"字典在迭代中改变大小"的错误。

### 3.7 `generate`：K 次"前向"，尺度内并行

```python
def generate(predictors, codebooks, rng):
    """One VAR sample: K passes, parallel-within-scale, causal across scales."""
    drawn: list[np.ndarray] = []
    for k, scale in enumerate(SCALES):
        ctx = context_key(drawn[:k])
        table = predictors[k]
        probs = table.get(ctx)
        if probs is None:
            probs = np.ones(CODEBOOK) / CODEBOOK
        size = scale * scale
        flat = np.array([sample_categorical(probs, rng) for _ in range(size)],
                        dtype=np.int32)
        drawn.append(flat.reshape(scale, scale))
    image = detokenize_multiscale(drawn, codebooks)
    return image, drawn
```

- 外层循环 4 次 = 4 次"transformer 前向"。每次用**已经生成的**前序尺度构造上下文（推理时没有真实 token，只能用自己的采样结果），然后一次性采出该级的 `scale²` 个 token。
- 列表推导里的 `size` 次采样彼此独立、可以并行——这就是"尺度内并行"。它隐含的假设是：给定前面所有尺度，同级各位置**条件独立**。
- `table.get(ctx)` 查不到时退回均匀分布。⚠️ 这个兜底分支在细尺度上几乎总是被触发：我统计了 300 次生成，各级走到兜底分支的比例为 0% / 约 10% / 约 86% / 约 97%，折算下来一张 85 token 的图约有 76 个 token 是纯随机抽的。
- `sample_categorical` 用 `rng.choice(len(probs), p=probs)` 做一次分类采样。⚠️ 逐个调用很慢，NumPy 可以用 `rng.choice(CODEBOOK, size=size, p=probs)` 一次采完。
- 生成结果没有任何质量检查，`main` 只打印形状和 min/max（见第 6 节）。

### 3.8 `reconstruction_mse` 与 `main`

```python
def main() -> None:
    rng = np.random.default_rng(0)
    train_imgs = make_patterns(rng, 64)
    val_imgs = make_patterns(rng, 16)

    codebooks = train_codebooks(train_imgs)
    train_token_streams = [tokenize_multiscale(img, codebooks) for img in train_imgs]
    predictors = fit_predictor(train_token_streams)
    # ... 打印配置与重建 MSE、生成 3 次、打印注意力账
    for k, scale in enumerate(SCALES):
        n_pos = scale * scale
        prior_seen = sum(s * s for s in SCALES[:k])
```

- `np.random.default_rng(0)` 是 NumPy 新式随机数生成器（`Generator`），比旧的 `np.random.seed` 更推荐；训练数据、验证数据和生成都从它取随机数，全程可复现。
- 重建 MSE 在训练集和验证集上都计算——验证集图案来自同一个 5 类图案库，所以不存在真正的"泛化"问题。
- 最后一段"注意力检查"只是算术：第 k 级之前所有尺度的 token 总数 `Σ_{j<k} s_j²`。⚠️ 它没有构造或检查任何 mask；标题写 "scales 1..k-1"（1 起始），打印却用 `scale 0..3`（0 起始），两种编号混用。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 8×8 灰度图、5 种图案 | 秒级运行，频率特性一目了然 | 真实 VAR 在 VAE 潜空间上做，ImageNet 256² |
| 标量 k-means 码本、每级 16 个 | 不需要训练网络 | 端到端训练的向量量化器；共享码本 4096–16384；监控利用率 |
| 尺度每级翻倍、最后一级为全分辨率 | 整除，池化/放大最简单 | 更密的尺度表 + 插值；最后一级为 `H/p × W/p` |
| 残差逐级减去 | 与讲义公式完全对应 | 一致——这是 VAR tokenizer 的核心 |
| 直方图 + 平均序号上下文代替 transformer | 不需要深度学习就能跑通"尺度顺序" | 上下文不泛化、与位置无关，生成几乎随机；真实 VAR 用带块因果 mask 的 transformer |
| 拉普拉斯平滑 | 避免零概率 | 样本少时平滑占比大，会抽到没见过的码字 |
| 只打印生成的形状与范围 | 代码短 | 掩盖了生成失败；应做分布级评估（第 14 节） |
| "注意力检查"只是计数 | 直观说明序列长度 | 应真正构造 mask 并测试（见测验 Q9） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring | 文件开头的三引号字符串 | 说明模块用途，`help(main)` 可见 |
| `from __future__ import annotations` | 文件第 30 行 | 推迟注解求值，旧版本 Python 也能写 `list[np.ndarray]` 这类注解 |
| 类型注解 | `def make_patterns(rng: np.random.Generator, n: int) -> np.ndarray:` | 标注参数和返回值类型，不影响运行 |
| 复杂返回类型 | `-> tuple[np.ndarray, list[np.ndarray]]`、`list[dict[tuple, np.ndarray]]` | 内置泛型写法（PEP 585） |
| 模块级常量 | `IMG = 8`、`SCALES = (1, 2, 4, 8)` | 全大写表示常量；元组不可变 |
| `zip` 多序列并行遍历 | `for scale, book in zip(SCALES, codebooks)` | 同时拿到尺度和对应码本 |
| `enumerate` | `for k, scale in enumerate(SCALES)` | 同时拿到下标和值 |
| 切片取前缀 | `stream[:k]`、`SCALES[:k]` | 取前 k 个元素，`k=0` 时为空 |
| 条件表达式 | `tuple(...) if prev_tokens else ()` | 空列表为假值，返回空元组 |
| 生成器 → 元组 | `tuple(int(t.mean() * 1000) for t in prev_tokens)` | 元组可哈希，能当字典键 |
| `dict.setdefault` | `predictors[k].setdefault(ctx, np.ones(...))` | 键不存在时插入默认值并返回 |
| `dict.get` | `table.get(ctx)` | 键不存在返回 `None` 而不是抛 `KeyError` |
| `raise ValueError(f"...")` | `fit_codebook` 里 | 输入不合法时抛出带说明的异常 |
| 多行 f-string 拼接 | `print(f"  scale {k} ..." f" attends to ...")` | 相邻字符串字面量自动拼接 |
| NumPy 广播 | `flat[:, None] - centers[None, :]`、`values[..., None]` | 用 `None` 增加维度，实现两两相减 |
| 布尔掩码 | `mask = assign == j`、`flat[mask].mean()`、`(xx == mid) \| (yy == mid)` | 用布尔数组选元素；`\|` 是逐元素或 |
| 花式索引 | `book[tok]` | 用整数数组查表，结果与 `tok` 同形状 |
| `reshape` + `mean(axis=...)` | `img.reshape(target, factor, target, factor).mean(axis=(1, 3))` | 一行完成平均池化 |
| `repeat` | `grid.repeat(factor, axis=0).repeat(factor, axis=1)` | 最近邻放大 |
| `np.mgrid` | `yy, xx = np.mgrid[0:IMG, 0:IMG]` | 一次得到坐标网格 |
| `np.random.default_rng` | `rng = np.random.default_rng(0)`；`rng.integers`、`rng.uniform`、`rng.choice` | 新式随机数生成器 |
| `-> None` 与 `if __name__ == "__main__":` | `def main() -> None:` | 无返回值的入口函数，直接运行时才执行 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，NumPy 2.5.3，约 0.2 秒）的完整输出：

```text
image size: 8x8
scales: (1, 2, 4, 8)
codebook size per scale: 16
reconstruction MSE on train: 0.00029
reconstruction MSE on val:   0.00015

generation: 4 transformer passes, all positions parallel within a scale
  trial 0: scales=[(1, 1), (2, 2), (4, 4), (8, 8)]  range=[-0.43, 1.17]
  trial 1: scales=[(1, 1), (2, 2), (4, 4), (8, 8)]  range=[-0.06, 1.33]
  trial 2: scales=[(1, 1), (2, 2), (4, 4), (8, 8)]  range=[-0.51, 1.12]

scale-ordered attention check: every scale k only sees scales 1..k-1
  scale 0 (size 1x1, 1 tokens): attends to 0 prior tokens
  scale 1 (size 2x2, 4 tokens): attends to 1 prior tokens
  scale 2 (size 4x4, 16 tokens): attends to 5 prior tokens
  scale 3 (size 8x8, 64 tokens): attends to 21 prior tokens
```

**重建 MSE 很低，但要看它从哪来。** 我额外统计了"只用前 K 级重建"的训练集 MSE：K=1、2、3、4 时约为 0.112、0.100、0.079、0.00029。前三级几乎没把误差降下来，最后的 8×8 级（全分辨率逐像素量化）一下子补齐了所有细节。所以 0.00029 主要说明"最细一级足够细"，而不能证明粗尺度学到了好的结构。验证集 MSE（0.00015）反而更低，是因为验证图来自同一个图案库、且只有 16 张，存在抽样波动。

**生成结果其实是失败的。** 训练图像素都在 [0, 1]，生成图的范围却到了 −0.51 和 1.33。原因见 3.6、3.7：细尺度的上下文几乎总是没见过的，退回均匀分布后，从 ±0.5 量级的残差码字里随机抽取并叠加，数值自然越界。我额外统计了 300 次生成：约 15% 的像素落在 [0, 1] 之外；生成图与最近训练图的平均 MSE 约 0.10，而验证图与最近训练图只有约 0.00016——生成的图不像任何一种图案。程序只打印形状和范围，看不出这些问题。

**注意力账。** 0 / 1 / 5 / 21 是"前面各级 token 总数"。总序列长度为 85，而生成只需 4 次"前向"——这就是 VAR 的效率来源：前向次数等于尺度数，而不是 token 数。如果把本级也算进去（块因果 mask 允许同级互看），每级第一个 token 能看到的数量是 1 / 5 / 21 / 85。

---

## 7. 动手改一改

1. **画出逐级重建曲线**：写一个函数，对每张图只用前 K 级 token 解码，打印 K=1..4 的平均 MSE，复现第 6 节的 0.112 / 0.100 / 0.079 / 0.00029。
2. **检查码本利用率**：统计每一级 16 个码字中有多少个互不相同、多少个在训练集上从未被使用；再把 `fit_codebook` 的初始化改成"从**去重后的**值里选"（`np.unique`），对比利用率和重建误差。
3. **给生成加质量指标**：对每次生成计算"与最近训练图的 MSE"和"越出 [0, 1] 的像素比例"，替代只打印 min/max。
4. **写真正的块因果 mask**：实现 `block_causal_mask(SCALES)`，返回 85×85 布尔矩阵，断言每一行可见的 token 数，并把结果打印成一个按尺度分块的小图。
5. **位置感知 + 全上下文的预测器**：把查表的键改成 `(全部前序 token 的元组, i, j)`、去掉拉普拉斯平滑，观察兜底次数和生成质量的变化（参考测验 Q12：最近训练图 MSE 从约 0.10 降到约 0.0086）；再思考为什么这本质上是在记忆训练集。
6. **换一个尺度表**：把 `SCALES` 改成 `(1, 2, 8)` 或 `(2, 4, 8)`，看重建误差和总 token 数怎么变（讲义练习 1 的玩具版）。

---

## 8. 常见坑

- **把低重建误差当成好 tokenizer**：最后一级若是全分辨率逐像素量化，几乎任何前级结构都能被它补齐；要看逐级累加的误差和码本利用率。
- **k-means 初始化选到重复值**：`replace=False` 只保证下标不重复；数据中大量重复值会产生重复码字和死码。
- **上下文键过细导致"查不到就随机"**：精确匹配的查表模型没有泛化能力，生成时上下文来自模型自己的采样，分布与训练时不同（exposure bias）。
- **尺度内并行 ≠ 位置无关**：并行的是"同时采样"，每个位置仍应有自己的分布；本代码把它们混成一个直方图。
- **只看形状和数值范围就宣布生成成功**：必须看样本本身或做分布级评估。
- **尺寸不能整除时的池化 / 放大**：`reshape` 技巧要求整除，换成 VAR 真实尺度表（3、5、13 等）会直接报错，需要改用插值。
