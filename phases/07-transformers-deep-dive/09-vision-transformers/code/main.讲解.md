# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 09 节 Vision Transformers (ViT) ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

ViT 论文最重要的结论是：**Transformer encoder 一行都不用改，图像只要变成 token 序列就能喂进去**。所以这份代码只实现 ViT 的"前端"——把图像变成序列的那几步，再顺手算一算真实 ViT 的参数量：

1. **Patchify**：把 `24 × 24 × 3` 的图像切成 16 个 `6 × 6 × 3` 的块，并按光栅顺序展平成长度 108 的向量。
2. **线性投影**：用一个 `(108, 48)` 的随机矩阵把每个 patch 映射到 `d_model = 48` 维（Xavier 初始化）。
3. **`[CLS]` + 2D 位置编码**：在序列前加一个可学习的 `[CLS]` 向量，给每个 patch 加上"行正弦 + 列正弦"拼接的位置编码。
4. **参数量估算**：从 ViT-Tiny 到 ViT-Huge，按公式估算参数量，体会"参数几乎都在 Transformer 层里"。

> 一句话：**ViT 的"视觉智慧"全在 patchify、位置方案和 `[CLS]` 池化里**——这正是代码最后打印的 takeaway。

⚠️ 不包含训练、attention 和 encoder 层本身；讲义说明了原因："任何实际规模的 ViT 都需要 PyTorch 和数小时 GPU 时间"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `make_image(H, W, C, seed)` | 函数 | 生成 `H × W × C` 的随机图像，像素值归一化到 [0, 1] | 输入图像 |
| `patchify(image, patch_size)` | 函数 | 切块 + 展平，返回 `(patches, (grid_h, grid_w))` | Step 1：patchify |
| `linear_project(patches, d_model, rng)` | 函数 | 每个 patch 乘一个随机矩阵，得到 `d_model` 维 token | Step 2：线性 embedding |
| `cls_and_pos(tokens, grid_h, grid_w, rng)` | 函数 | 前置 `[CLS]`，给 patch token 加 2D 位置编码 | Step 3：`[CLS]` + 位置编码 |
| `pos_2d(H, W, d_model)` | 函数 | 一半维度编码行、一半编码列的 2D 正弦位置编码 | 2D sinusoidal PE |
| `param_count_vit(...)` | 函数 | 估算 encoder + 位置编码 + `[CLS]` + head 的参数量 | 模型规模 |
| `main()` | 入口 | 串起前端流程并打印形状；打印五种 ViT 配置的参数量 | — |

数据流：`make_image → patchify → linear_project → cls_and_pos(内部调用 pos_2d)`，得到 `(17, 48)` 的 token 序列；参数量部分独立调用 `param_count_vit`。

---

## 3. 逐段精讲

### 3.1 造一张"图像"

```python
def make_image(H, W, C=3, seed=0):
    rng = random.Random(seed)
    return [[[rng.randint(0, 255) / 255.0 for _ in range(C)] for _ in range(W)] for _ in range(H)]
```

- 三层嵌套列表推导：最外层是行（H），中间是列（W），最内层是通道（C）。所以访问方式是 `image[行][列][通道]`，对应 NumPy 里 `(H, W, C)` 的 **channels-last** 布局（PyTorch 的 `Conv2d` 则用 `(C, H, W)`）。
- `randint(0, 255) / 255.0`：模拟 8 位像素再归一化到 [0, 1]，这是图像预处理的第一步（真实的 `ViTImageProcessor` 还会减均值、除标准差）。
- 讲义说"`(R, G, B)` 元组"，代码实际用的是长度为 3 的列表，用法相同。

### 3.2 Patchify：切块与光栅顺序

```python
def patchify(image, patch_size):
    H = len(image)
    W = len(image[0])
    C = len(image[0][0])
    assert H % patch_size == 0 and W % patch_size == 0
    patches = []
    grid = []
    for row_idx, i in enumerate(range(0, H, patch_size)):
        grid_row = []
        for col_idx, j in enumerate(range(0, W, patch_size)):
            patch = []
            for di in range(patch_size):
                for dj in range(patch_size):
                    patch.extend(image[i + di][j + dj])
            patches.append(patch)
            grid_row.append((row_idx, col_idx))
        grid.append(grid_row)
    return patches, (H // patch_size, W // patch_size)
```

- `range(0, H, patch_size)` 以步长 P 遍历每个块的左上角 → 块之间**不重叠**。
- 外两层循环走"网格"（先行后列，**光栅顺序 / 行优先**），内两层循环走"块内像素"（也是先行后列），`extend` 把每个像素的 C 个通道值依次追加。所以一个 patch 向量的布局是 `[(di=0,dj=0) 的 RGB, (0,1) 的 RGB, …]`，长度 `P·P·C = 6·6·3 = 108`。讲义强调："Raster order … Every ViT uses this ordering."
- `assert` 保证图像边长能被 P 整除；真实处理器会先 resize/crop 到 224 这样的尺寸。
- 返回值第二项是网格大小 `(4, 4)`，后续 `cls_and_pos` 要靠它知道每个 token 在第几行第几列。
- ⚠️ 函数里构建的 `grid`（记录每个 patch 的 `(row_idx, col_idx)`）**没有被返回**，属于残留代码；`enumerate` 得到的 `row_idx/col_idx` 也只在这里用到。
- 复杂度：每个像素恰好访问一次，O(H·W·C)。

### 3.3 线性投影：一个矩阵乘法

```python
def linear_project(patches, d_model, rng=None):
    if rng is None:
        rng = random.Random(0)
    in_dim = len(patches[0])
    scale = math.sqrt(2.0 / (in_dim + d_model))
    W = [[rng.gauss(0, scale) for _ in range(d_model)] for _ in range(in_dim)]
    out = []
    for patch in patches:
        row = [0.0] * d_model
        for i, x in enumerate(patch):
            if x == 0.0:
                continue
            for j in range(d_model):
                row[j] += x * W[i][j]
        out.append(row)
    return out, W
```

- 本质是 `out = patches @ W`，`W` 形状 `(108, 48)`。这就是讲义说的"等价于 kernel=P、stride=P 的卷积"：卷积核在每个不重叠块上做的也正是"展平后点乘一组权重"，`d_model` 个输出通道就是 `W` 的 48 列。
- `scale = sqrt(2 / (fan_in + fan_out))` 是 **Xavier/Glorot 初始化**（高斯版本），让投影前后的方差大致保持，避免数值一开始就爆炸或消失。
- 循环顺序是"对 patch 的每个输入维 i，把 `x · W[i]` 累加到输出"——外积累加的写法。`if x == 0.0: continue` 跳过零像素，是对稀疏输入的小优化；随机图像几乎没有精确的 0，所以这里基本不触发。
- ⚠️ 没有偏置项；真实的 `Conv2d` patch embedding 默认带偏置。
- 返回 `W` 是为了在需要时检查或复用权重（`main()` 里接收为 `W_proj` 但没再使用）。

### 3.4 `[CLS]` 与位置编码的拼装

```python
def cls_and_pos(tokens, grid_h, grid_w, rng=None):
    """Prepend learnable [CLS] and add 2D sinusoidal positional encoding."""
    if rng is None:
        rng = random.Random(1)
    d_model = len(tokens[0])
    cls = [rng.gauss(0, 0.02) for _ in range(d_model)]
    pe = pos_2d(grid_h, grid_w, d_model)
    out = [list(cls)]
    idx = 0
    for i in range(grid_h):
        for j in range(grid_w):
            t = [tokens[idx][k] + pe[i][j][k] for k in range(d_model)]
            out.append(t)
            idx += 1
    return out
```

- `[CLS]` 用 `N(0, 0.02²)` 初始化——小标准差是 BERT/ViT 中可学习 token 的常见初始化。在真实模型里它是 `nn.Parameter`，会被训练；这里只是一个随机向量。
- 用 `idx` 按顺序取 token，同时用 `(i, j)` 双循环取位置编码。因为 `patchify` 是光栅顺序，第 `idx` 个 token 恰好对应第 `i = idx // grid_w` 行、第 `j = idx % grid_w` 列——**两边的顺序必须一致**，否则位置编码就贴错了位置。
- 位置编码是**加**到 token 上，而不是拼接，维度保持 `d_model` 不变（与原始 Transformer 一致）。
- ⚠️ `[CLS]` 本身没有加位置编码。原始 ViT 使用可学习的位置编码，长度是 `N + 1`，`[CLS]` 也有一个位置（参数量公式里的 `(num_patches + 1) * d_model` 正是这个意思）。这里用的是 2D 正弦编码，而 `[CLS]` 没有行列坐标，所以干脆不加。

### 3.5 2D 正弦位置编码

```python
def pos_2d(H, W, d_model):
    """2D sinusoidal: split d_model in half, encode row and col independently."""
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

- 思路就是讲义练习 2：**行坐标和列坐标各用一份 1D 正弦编码，然后拼起来**。前 `half = 24` 维只依赖行号 i，后 24 维只依赖列号 j。
- 每一半内部和第 04 节的 1D 正弦编码一样：频率 `1 / 10000^(2k/half)` 从 1 逐渐降低，`(sin, cos)` 成对排列在相邻维度。低维变化快（分辨相邻位置）、高维变化慢（分辨远距离位置）。
- `assert d_model % 4 == 0`：先对半分给行/列，每一半又要成对放 `(sin, cos)`，所以要被 4 整除。
- 例：`pe[0][0]` 的所有 sin 维都是 `sin(0) = 0`、cos 维都是 `cos(0) = 1`，所以第一个 patch 加完位置编码后，第 0 维的值不变——这就是运行结果里 `cell [0,0] of p1` 等于纯投影值的原因。
- ⚠️ `[[0.0] * d_model for _ in range(W)]` 这种写法是对的：每行都新建一个列表。如果写成 `[[0.0] * d_model] * W`，W 个元素会指向**同一个**列表，改一处全变。

### 3.6 参数量估算

```python
def param_count_vit(d_model, n_layers, n_heads, ffn_expansion, num_patches, num_classes):
    # ...
    # Norms: 2 * d_model per layer (LayerNorm gamma+beta)
    per_layer = 4 * d_model ** 2 + 2 * d_model * int(ffn_expansion * d_model) + 4 * d_model
    pos_emb = (num_patches + 1) * d_model
    head = d_model * num_classes
    return per_layer * n_layers + pos_emb + d_model + head + 2 * d_model
```

| 项 | 公式 | 含义 |
|----|------|------|
| attention | `4 · d²` | Q、K、V、O 四个 `d × d` 投影 |
| FFN | `2 · d · (4d) = 8d²` | 升维到 4d 再降回 d |
| LayerNorm | `4 · d` | 每层两个 LN，各有 γ、β |
| 位置编码 | `(N + 1) · d` | 可学习位置编码，含 `[CLS]` 的位置 |
| `[CLS]` | `d` | 返回式中单独的 `+ d_model` |
| head | `d · num_classes` | 分类线性层 |
| 最终 LN | `2 · d` | encoder 输出后的 LayerNorm |

- 每层 `12d²` 是 Transformer 参数量的经典估算：attention 占 1/3，FFN 占 2/3。
- **`n_heads` 在函数体里没有被使用**——这是对的：多头只是把 d 维切分，参数总量不变。
- patch embedding 不在函数里，`main()` 中另外加上 `patch * patch * 3 * d`。
- ⚠️ 源码注释写"Norms: 2 * d_model per layer"，但代码用的是 `4 * d_model`（两个 LayerNorm × (γ+β)）。代码是对的，注释有误。
- ⚠️ 忽略了所有偏置项（每层约 `9d`），所以是"approximate"。

### 3.7 `main()`：配置表

```python
    for name, d, L, H_heads, exp, patch in [
        ("ViT-Tiny/16",   192, 12, 3, 4, 16),
        # ...
        ("ViT-Huge/14",  1280, 32, 16, 4, 14),
    ]:
        grid_n = (224 // patch) ** 2
        params = param_count_vit(d, L, H_heads, exp, grid_n, num_classes=1000)
        params += patch * patch * 3 * d
```

- 遍历一个元组列表，用**元组解包**一次取出 6 个字段。
- `grid_n = (224 // patch) ** 2`：224 分辨率下的 patch 数，P=16 时 196，P=14（ViT-Huge）时 256。
- 名字里的 `/16`、`/14` 就是 patch size，这是 ViT 系列的命名惯例。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只实现前端，不实现 encoder | 讲义的核心观点：encoder 与 BERT 完全相同 | 无法训练；真实实现用 PyTorch / timm / HF |
| 用三重循环 patchify | 每一步都看得见，顺序一目了然 | 慢；生产中用 `Conv2d(kernel=P, stride=P)` 或 `reshape + permute` |
| 显式矩阵乘做投影 | 展示"patch embedding 就是一个线性层" | 无偏置；生产中由卷积一步完成切块 + 投影 |
| 2D 正弦位置编码 | 无需训练、可推广到任意网格大小 | 原始 ViT 用可学习编码，换分辨率时需插值 |
| `[CLS]` 不加位置编码 | 2D 正弦编码没有给 `[CLS]` 定义坐标 | 可学习编码方案会为 `[CLS]` 单独留一个位置 |
| 参数估算忽略偏置 | 公式简洁，突出 `12d²/层` 的主项 | 与官方数字有少量偏差（ViT-B：86.5M vs 约 86M） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def make_image(H, W, C=3, seed=0)` | 调用时可省略 |
| 嵌套列表推导 | `[[[... for _ in range(C)] for _ in range(W)] for _ in range(H)]` | 生成三维嵌套列表；`_` 表示循环变量不用 |
| 列表乘法 vs 推导 | `[0.0] * d_model`、`[[0.0] * d_model for _ in range(W)]` | 内层用乘法（元素是不可变的 float，安全），外层必须用推导式避免共享引用 |
| `range(start, stop, step)` | `range(0, H, patch_size)` | 以步长遍历 |
| `enumerate` | `for row_idx, i in enumerate(range(0, H, patch_size))` | 同时拿到序号与值 |
| `assert` | `assert H % patch_size == 0 and W % patch_size == 0`；`assert d_model % 4 == 0, "..."` | 条件不成立时抛 `AssertionError`，逗号后是错误信息 |
| `list.extend` | `patch.extend(image[i + di][j + dj])` | 把一个像素的 C 个通道值逐个加入 |
| 整除 `//` 与取余 `%` | `H // patch_size`、`d_model % 4` | 整除结果是 int |
| 幂运算 | `10000 ** (2 * k / half)`、`d_model ** 2` | 可用于浮点指数 |
| `None` 哨兵默认值 | `rng=None` … `if rng is None: rng = random.Random(0)` | 可选地注入随机源 |
| `continue` | `if x == 0.0: continue` | 跳过本轮循环 |
| 多返回值（元组） | `return patches, (H // patch_size, W // patch_size)`；`patches, grid = patchify(...)` | 返回元组并解包 |
| 元组解包遍历 | `for name, d, L, H_heads, exp, patch in [...]` | 一次取出多个字段 |
| f-string 格式符 | `f"{name:<14}"`、`f"{d:<5}"`、`f"{params / 1e6:.1f}M"`、`f"{x:.4f}"` | `<14` 左对齐占 14 格；`.1f` 一位小数 |
| 科学计数法字面量 | `1e6` | 等于 `1000000.0` |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时不到 0.1 秒）：

```text
=== ViT front-end sanity ===
image:               (24, 24, 3)
patch size:          6x6
grid:                4 x 4 = 16 patches
flat patch size:     108
d_model:             48
sequence length:     17  (patches + CLS)
cell [0,0] of CLS:   -0.0051
cell [0,0] of p1:    0.3437
```

- `grid: 4 x 4 = 16`：`24 / 6 = 4`，验证了讲义练习 1 的 `(H/P)·(W/P)`。
- `flat patch size: 108`：`6·6·3`，即 `P·P·C`。（讲义 Build It 把它说成"108-d embedding vector"，准确说 108 是展平后的原始 patch 维度，embedding 维度是 `d_model = 48`。）
- `sequence length: 17`：16 个 patch + 1 个 `[CLS]`，对应真实 ViT-B/16 的 197 = 196 + 1。
- `cell [0,0] of CLS: -0.0051`：`[CLS]` 是 `N(0, 0.02²)` 的小随机数。
- `cell [0,0] of p1: 0.3437`：第一个 patch 位于 (0, 0)，第 0 维的位置编码是 `sin(0) = 0`，所以这个值就是纯投影结果。

```text
=== parameter counts (approximate) ===
  ViT-Tiny/16     d=192    L=12   heads=3    patches=196   ~5.7M params
  ViT-Small/16    d=384    L=12   heads=6    patches=196   ~22.0M params
  ViT-Base/16     d=768    L=12   heads=12   patches=196   ~86.5M params
  ViT-Large/16    d=1024   L=24   heads=16   patches=196   ~304.1M params
  ViT-Huge/14     d=1280   L=32   heads=16   patches=256   ~631.7M params
```

- 与讲义给出的 ViT-Base ~86M、ViT-Huge ~632M 吻合；Large 的 304.1M 比讲义的 ~307M 少约 1%。被忽略的偏置项在 Large 上只有约 0.2M（每层约 `9d`），解释不了全部差距，剩下的差异来自不同资料的统计口径；作为估算，误差 1% 已经足够。
- 规律：参数量 ≈ `12 · L · d²`。d 翻倍参数约 ×4；层数翻倍参数 ×2。
- 对比讲义提到的 ResNet-50（约 25M）：ViT-Base 是它的 3 倍多，ViT-Small 与之相当。

---

## 7. 动手改一改

1. **验证公式**：把 `patch_size` 改为 4、8、12，检查 patch 数是否为 `(24/P)²`、展平维度是否为 `P²·3`；改成 5 会发生什么？（`assert` 失败。）
2. **NumPy 版 patchify**：用 `reshape(gh, P, gw, P, C).transpose(0, 2, 1, 3, 4).reshape(N, P*P*C)` 实现，并用 `np.allclose` 与纯 Python 版比较（见测验 Q11）。
3. **可学习位置编码 vs 正弦**：写一个 `learned_pos(N, d)`，返回 `N + 1` 个 `N(0, 0.02²)` 随机向量（含 `[CLS]` 的位置），替换 `cls_and_pos` 中的正弦编码。
4. **位置编码插值**：把 4×4 的位置编码网格用双线性插值扩展到 8×8，模拟"224 → 448 分辨率微调"时对位置编码的处理。
5. **补全偏置**：在 `param_count_vit` 中加上 Q/K/V/O、FFN、patch embedding 和 head 的偏置，看 ViT-Base 变成多少。
6. **进阶**：用 PyTorch 写 `nn.Conv2d(3, 48, kernel_size=6, stride=6)`，把 `W_proj` 重排成卷积核形状 `(48, 3, 6, 6)` 加载进去，验证输出与 `linear_project` 一致（注意 channels-last 与 channels-first 的转换）。

---

## 8. 常见坑

- **patch 内部展平顺序不一致**：训练用 `(di, dj, c)`、推理用 `(c, di, dj)`，结果是"同一个 patch"被解释成完全不同的向量；加载预训练权重时尤其要对齐。
- **光栅顺序与位置编码不对应**：token 按行优先排列，位置编码却按列优先生成，模型的空间感会被打乱。
- **漏掉 `[CLS]`**：序列长度、位置编码数量都会差 1，加载 HF 权重时报形状不匹配。
- **换分辨率不插值位置编码**：序列长度变了，位置编码对不上；就算长度凑巧一致，空间对应关系也错了。
- **列表乘法共享引用**：`[[0.0] * d] * W` 生成的 W 行是同一个对象，修改任何一行都会改全部。
- **把展平维度和 `d_model` 混淆**：ViT-B/16 两者都是 768 只是巧合；本代码里 108 和 48 就不同。
