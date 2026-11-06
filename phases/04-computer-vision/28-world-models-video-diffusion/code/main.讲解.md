# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 28 节 世界模型与视频扩散 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：`torch`（`torch.nn`；文件还导入了 `torch.nn.functional` 但没有使用）；CPU 即可，不加载任何预训练模型，无需联网

---

## 1. 这份代码在考察什么

讲义自己说得很清楚："Not a working video generator; a structural demo that every piece shapes correctly."——这不是一个能生成视频的模型，而是一个**形状正确的 video DiT 骨架**。它要你搞懂的是：

1. **视频为什么贵**：用整数算一算 5 秒 360p 视频的 token 数和注意力对数，直观感受全联合注意力的平方爆炸。
2. **3D patch 化**：一个"步长等于卷积核"的 `nn.Conv3d`，把 `(N, C, T, H, W)` 的视频潜变量切成时空小块并投影成 token。
3. **分解注意力（divided attention）**：先在每个空间位置上沿时间做注意力，再在每一帧内沿空间做注意力——TimeSformer 和大多数 video DiT 的核心。
4. **张量形状体操**：`view / permute / reshape` 如何把同一组 token 在"时间序列视角"和"空间序列视角"之间来回切换。
5. **输出头的设计**：每个 token 输出 `C × p_t × p_h × p_w` 个数，为 unpatchify 回视频做准备。

> 一句话：**video DiT = 3D patch 化 + 3D 位置编码 + 分解 / 窗口注意力 + AdaLN + rectified flow**；这份代码实现了其中的第 1 和第 3 项，并把"为什么必须分解"算给你看。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `VideoPatch3D` | `nn.Module` | `Conv3d(kernel=stride=(2,2,2))` + 展平成 token 序列 | 时空 patch 化 |
| `DividedAttentionBlock` | `nn.Module` | 时间注意力 → 空间注意力 → MLP，均为 pre-LN 残差 | 分解注意力（TimeSformer 式） |
| `TinyVideoDiT` | `nn.Module` | patch 化 → 2 个分解注意力块 → 线性输出头 | 极简 video DiT 骨架 |
| `count_tokens(T, H, W, p_t, p_h, p_w)` | 函数 | 计算时空 token 数 | 讲义练习 1 |
| `main()` | 演示入口 | 打印 token / 注意力对数；跑一次前向并打印形状与参数量 | — |

数据流：`(1, 4, 8, 16, 16)` 视频潜变量 →（`VideoPatch3D`）→ `(1, 256, 64)` token + `grid=(4, 8, 8)` →（2 × `DividedAttentionBlock`）→ `(1, 256, 64)` →（`out` 线性层）→ `(1, 256, 32)`。

---

## 3. 逐段精讲

### 3.1 `count_tokens` 与注意力代价估算

```python
def count_tokens(T, H, W, p_t=2, p_h=8, p_w=8):
    return (T // p_t) * (H // p_h) * (W // p_w)
```

```python
    tokens = count_tokens(150, 480, 360, p_t=2, p_h=8, p_w=8)
    T_tok = 150 // 2
    S_tok = (480 // 8) * (360 // 8)
    print(f"  tokens per clip: {tokens:,}")
    print(f"  attention pairs (joint): {tokens ** 2:,}")
    # Divided temporal: T^2 attention at every spatial position.
    # Divided spatial:  (H*W)^2 attention at every timestep.
    divided_time = S_tok * T_tok ** 2
    divided_space = T_tok * S_tok ** 2
```

- 5 秒 × 30 fps = 150 帧，时间方向 2 帧一组 → 75 个时间 token；空间 8×8 一块 → `60 × 45 = 2,700` 个空间 token；总计 202,500 个 token。
- 全联合注意力要算 `N²` 对：`202,500² ≈ 4.1 × 10¹⁰`。
- 分解注意力：
  - 时间：每个空间位置一条长度 75 的序列，共 2,700 条 → `2,700 × 75²`；
  - 空间：每个时间步一条长度 2,700 的序列，共 75 条 → `75 × 2,700²`。
  - 合计约 `5.6 × 10⁸`，比联合注意力少约 73 倍，其中空间项占约 97%。
- `//` 是整除：尺寸不能被 patch 整除时会**静默丢弃余数**（真实模型会先 padding 或要求尺寸对齐）。
- ⚠️ 参数顺序：函数签名是 `(T, H, W)`，但传入的是 `(150, 480, 360)`，而 "360p" 的高应是 360、宽是 480。因为 `p_h = p_w = 8`，交换后乘积相同，不影响结果；如果两个方向的 patch 大小不同就会算错。
- ⚠️ 这里只数了"注意力分数对"，没有乘以特征维、头数和层数，也没算 MLP；它是一个量级估算，用来说明"为什么必须分解"。

### 3.2 `VideoPatch3D`：用 3D 卷积做 patch 化

```python
class VideoPatch3D(nn.Module):
    def __init__(self, in_channels=4, dim=64, patch_t=2, patch_h=2, patch_w=2):
        super().__init__()
        self.proj = nn.Conv3d(
            in_channels, dim,
            kernel_size=(patch_t, patch_h, patch_w),
            stride=(patch_t, patch_h, patch_w),
        )

    def forward(self, x):
        x = self.proj(x)
        n, c, t, h, w = x.shape
        tokens = x.reshape(n, c, t * h * w).transpose(1, 2)
        return tokens, (t, h, w)
```

- **为什么卷积就是 patch 化**：当 `stride == kernel_size` 时，卷积窗口之间不重叠、也没有空隙，每个输出位置恰好"看"一个 `2×2×2` 的时空小块，并用一组共享的线性权重把它投影成 `dim` 维向量——这与"切块 + 展平 + 线性层"数学上等价，但写法更简洁、实现更高效。这和 ViT 用 `Conv2d(kernel=stride=patch)` 做 patch embedding 是同一个技巧。
- 输入 `(N, C, T, H, W)` = `(1, 4, 8, 16, 16)`：这里的 4 通道对应潜空间（例如 VAE 编码后的视频潜变量），而不是 RGB。
- 卷积输出 `(1, 64, 4, 8, 8)`；`reshape(n, c, t*h*w)` 把三个空间维展平成一维（顺序是 t → h → w，即 token 下标 = `t·(h·w) + h·w_size + w`）；`transpose(1, 2)` 把通道放到最后，得到 Transformer 习惯的 `(N, seq, dim)` = `(1, 256, 64)`。
- 同时返回 `grid = (t, h, w)`：后续的分解注意力需要知道"256 个 token 是怎么由 4 × 8 × 8 排成的"，才能正确地重新分组。
- 讲义 Step 1 的版本还把 `patch_t/h/w` 存成了属性，这里省略了。

### 3.3 `DividedAttentionBlock`：时间注意力

```python
    def forward(self, x, grid):
        T, H, W = grid
        n, seq, d = x.shape

        xt = x.view(n, T, H * W, d).permute(0, 2, 1, 3).reshape(n * H * W, T, d)
        a, _ = self.time_attn(self.ln1(xt), self.ln1(xt), self.ln1(xt), need_weights=False)
        xt = (xt + a).reshape(n, H * W, T, d).permute(0, 2, 1, 3).reshape(n, seq, d)
```

形状变化（以 `n=1, T=4, H=W=8, d=64` 为例）：

| 步骤 | 形状 | 含义 |
|------|------|------|
| `x` | `(1, 256, 64)` | t-major 排列的 token |
| `.view(n, T, H*W, d)` | `(1, 4, 64, 64)` | 拆出时间维和空间维 |
| `.permute(0, 2, 1, 3)` | `(1, 64, 4, 64)` | 空间维放前面，时间维放中间 |
| `.reshape(n*H*W, T, d)` | `(64, 4, 64)` | **64 条长度为 4 的时间序列**，作为 batch 送入注意力 |
| 注意力 + 残差后 reshape/permute/reshape | `(1, 256, 64)` | 还原回 t-major 的原始排列 |

- **核心技巧**：`nn.MultiheadAttention` 只会在"序列维"上做注意力。把空间位置挪到 batch 维、时间留在序列维，注意力就只在"同一空间位置的不同帧"之间发生——这就是时间注意力。
- `batch_first=True`：输入格式是 `(batch, seq, dim)`，否则默认是 `(seq, batch, dim)`。
- `need_weights=False`：不返回注意力权重矩阵，可以走更快的计算路径、省内存。
- **Pre-LN 残差**：`xt + attn(LN(xt))`，先归一化再注意力，再加回原输入——这是现代 Transformer 的标准写法，训练更稳定。
- **为什么 permute 后要用 reshape**：`permute` 只改步长不搬数据，结果不连续，`view` 无法合并维度，`reshape` 会在必要时复制一份连续内存。而第一行的 `x.view(n, T, H*W, d)` 只是**拆分**一个维度，即使输入是 `VideoPatch3D` 中 `transpose` 产生的非连续张量也可以用 `view`。
- ⚠️ `self.ln1(xt)` 被调用了 3 次（分别作为 Q、K、V），结果相同却算了 3 遍。更好的写法是 `h = self.ln1(xt); a, _ = self.time_attn(h, h, h, need_weights=False)`。

### 3.4 `DividedAttentionBlock`：空间注意力与 MLP

```python
        xs = xt.view(n, T, H * W, d).reshape(n * T, H * W, d)
        a, _ = self.space_attn(self.ln2(xs), self.ln2(xs), self.ln2(xs), need_weights=False)
        xs = (xs + a).reshape(n, T, H * W, d).reshape(n, seq, d)

        xs = xs + self.mlp(self.ln3(xs))
        return xs
```

- 这次不需要 permute：t-major 的排列本来就是"每一帧的 64 个 token 连在一起"，直接 `reshape(n*T, H*W, d)` 得到 `(4, 64, 64)`——**4 条长度为 64 的空间序列**，注意力只在同一帧内部发生。
- 最后是标准的 Transformer 前馈层：`Linear(64→256) → GELU → Linear(256→64)`，同样是 pre-LN 残差。
- **为什么这样设计**：一次时间 + 一次空间，信息可以在两步之内从任意 `(t₁, h₁, w₁)` 传到任意 `(t₂, h₂, w₂)`（先沿时间、再沿空间），代价却从 `(THW)²` 降到 `HW·T² + T·(HW)²`。代价是"斜向"的时空交互只能间接完成。
- ⚠️ 讲义 Step 3 正文写的是"Two O(T² + (HW)²) operations instead of one O((THW)²)"，这只是**单条序列**的代价；乘上序列条数后，总代价应为 `(H·W)·T² + T·(H·W)²`（讲义 Concept 部分和本文件 `main()` 的计算是对的）。

### 3.5 `TinyVideoDiT`：把零件串起来

```python
class TinyVideoDiT(nn.Module):
    def __init__(self, in_channels=4, dim=64, depth=2, heads=2):
        super().__init__()
        self.in_channels = in_channels
        self.dim = dim
        self.patch = VideoPatch3D(in_channels=in_channels, dim=dim, patch_t=2, patch_h=2, patch_w=2)
        self.blocks = nn.ModuleList([DividedAttentionBlock(dim, heads) for _ in range(depth)])
        self.out = nn.Linear(dim, in_channels * 2 * 2 * 2)

    def forward(self, x):
        tokens, grid = self.patch(x)
        for blk in self.blocks:
            tokens = blk(tokens, grid)
        return self.out(tokens), grid
```

- `nn.ModuleList`：用列表保存多个子模块，PyTorch 才能正确注册它们的参数（用普通 Python 列表的话，`model.parameters()` 会漏掉这些块，优化器也不会更新它们）。
- 输出头 `Linear(64, 4 × 2 × 2 × 2 = 32)`：每个 token 负责预测自己覆盖的 2×2×2 时空小块里 4 个通道的全部数值，这样才能 unpatchify 回 `(N, 4, 8, 16, 16)`（测验 Q11 给出了 `unpatchify` 的写法和往返验证）。在扩散 / rectified flow 训练中，这个输出就是预测的噪声或速度场。
- ⚠️ 刻意省略的部分（因此它"不是能工作的视频生成器"）：
  - **没有位置编码**：讲义 Step 2 的 `rope_3d` 没有被放进 `main.py`。没有位置信息时，注意力对序列内的排列是"等变"的——模型分不清第 1 帧和第 4 帧、左上角和右下角；
  - **没有时间步 / 文本条件**：真实 DiT 用 AdaLN 把扩散时间步和提示词注入每个块；
  - **没有训练目标**：没有加噪、没有 rectified flow 损失；
  - **patch 大小写死**：`VideoPatch3D` 的 `2, 2, 2` 和输出头的 `2 * 2 * 2` 分别硬编码，改其中一处而忘了另一处就会不匹配；
  - `self.in_channels`、`self.dim` 存了但没用；顶部导入的 `F` 也没有使用。

### 3.6 `main()` 的模型部分

```python
    torch.manual_seed(0)
    vid = torch.randn(1, 4, 8, 16, 16)
    model = TinyVideoDiT(in_channels=4, dim=64, depth=2, heads=2)
    out, grid = model(vid)
    # ...
    print(f"  params  {sum(p.numel() for p in model.parameters()):,}")
```

- `torch.manual_seed(0)` 固定随机初始化，保证可复现（不过打印的只有形状和参数量，与随机数无关）。
- `sum(p.numel() for p in model.parameters())`：遍历所有可训练参数张量，累加元素个数，这是统计参数量的标准写法。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `Conv3d(kernel=stride)` 做 patch 化 | 一行实现"切块 + 线性投影"，高效 | 等价于不重叠切块；有的模型先用因果 3D VAE 压缩时间再 patch 化 |
| 分解注意力（时间 → 空间） | 代价从 `(THW)²` 降到 `HW·T² + T·(HW)²` | 时空斜向交互需两步；高分辨率时空间项仍很大，还会配合窗口注意力 |
| `MultiheadAttention(batch_first=True)` | 直接用 PyTorch 内置实现 | 生产中用 FlashAttention / SDPA 等高效内核 |
| pre-LN 残差 | 训练稳定，现代标准 | 真实 DiT 用 AdaLN（由时间步和条件生成 LN 的缩放 / 平移） |
| 不加位置编码、不加条件 | 结构演示，只验证形状 | 真实模型必须有 3D RoPE / 可学习位置编码与 AdaLN |
| 用整数算 token 和注意力对数 | 不跑模型也能说明"为什么必须分解" | 只是量级估算，未计入头数、层数、特征维 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 整除 `//` 与幂 `**` | `150 // 2`、`T_tok ** 2` | 整除向下取整；`**` 是乘方 |
| f-string 千分位 | `f"{tokens:,}"` | `:,` 每三位加逗号，大数更易读 |
| 类继承 + `super().__init__()` | `class VideoPatch3D(nn.Module)` | 先初始化父类，子模块和参数才能被注册 |
| 关键字参数 | `nn.Conv3d(in_channels, dim, kernel_size=(...), stride=(...))` | 按名字传参，清晰且不怕顺序错 |
| 元组解包 | `n, c, t, h, w = x.shape`、`T, H, W = grid`、`a, _ = self.time_attn(...)` | `_` 表示丢弃不需要的返回值 |
| 返回多个值 | `return tokens, (t, h, w)` | 实际返回一个元组 |
| 列表推导式 + `nn.ModuleList` | `nn.ModuleList([DividedAttentionBlock(dim, heads) for _ in range(depth)])` | 批量创建子模块并正确注册 |
| 张量形状操作 | `view`、`reshape`、`permute`、`transpose` | `view` 要求内存布局兼容；`reshape` 必要时复制；`permute` / `transpose` 只改维度顺序 |
| 生成器表达式 | `sum(p.numel() for p in model.parameters())` | 不建中间列表直接求和 |
| 模块调用 | `self.ln1(xt)`、`model(vid)` | 调用实例会触发 `forward` |
| 注释掉的说明 | `# Divided temporal: T^2 attention at every spatial position.` | 解释公式含义的行内注释 |
| `tuple(...)` | `tuple(vid.shape)` | 把 `torch.Size` 转成普通元组打印 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

> 未实际运行完整脚本（当前环境缺少 `torch`，按规范不安装依赖）。其中 token 计数部分是纯整数运算，我用同样的公式复算过，数值确定；模型部分的形状由代码直接决定；参数量是按各层公式手算的（见测验 Q10），请以你本地运行结果为准。

预期输出：

```text
[token count for 5s 360p video (150 frames, 480x360)]
  tokens per clip: 202,500
  attention pairs (joint): 41,006,250,000
  divided time total: 15,187,500
  divided space total: 546,750,000
  divided total: 561,937,500

[model shapes]
  input   (1, 4, 8, 16, 16)
  tokens grid (4, 8, 8)
  output  (1, 256, 32)
  params  137,696
```

逐行解读：

- **202,500 个 token**：`75 × 60 × 45`。仅仅 5 秒、360p、8×8 的 patch，token 数就是一张 256×256 图片（16×16 patch → 256 个 token）的近 800 倍。
- **410 亿个注意力对**：fp16 下单个头、单层的分数矩阵约 82 GB——全联合注意力在这个尺寸上完全不现实。
- **分解后约 5.6 亿**：少了约 73 倍；时间项只有 1,519 万，空间项 5.47 亿占绝对主导。想进一步降本，应在空间侧下功夫（窗口注意力、更大的空间 patch、更强的 VAE 压缩）。
- **`tokens grid (4, 8, 8)`**：`(8, 16, 16)` 在三个方向各除以 2，与讲义 Step 5 的预期一致。
- **`output (1, 256, 32)`**：256 个 token，每个输出 `4 × 2 × 2 × 2 = 32` 个数，正好可以 unpatchify 回 `(1, 4, 8, 16, 16)`。
- **`params 137,696`**：Conv3d 2,112 + 每个分解注意力块 66,752 × 2 + 输出头 2,080。其中每个块里两个注意力共 33,280、MLP 33,088，各占一半左右。

---

## 7. 动手改一改

1. **加位置编码**：把讲义 Step 2 的 `rope_3d` 加到 `TinyVideoDiT.forward` 中 patch 化之后（`t_dim + h_dim + w_dim = 64`，且三者都取偶数，例如 22 + 22 + 20），确认输出形状不变。思考：为什么三个维度都必须是偶数？
2. **省掉重复的 LayerNorm**：把 `self.ln1(xt)` 只算一次，验证输出与原实现数值一致。
3. **实现 unpatchify**：按测验 Q11 写 `unpatchify`，并用"手工 patchify → unpatchify"的往返测试验证。
4. **换成全联合注意力**（讲义练习 2）：写一个 `JointAttentionBlock`，直接在 `(n, 256, 64)` 上做一次注意力。比较参数量（同量级，联合版只少了一个注意力层，且与输入大小无关）和在更大输入（如 `(1, 4, 32, 64, 64)`）上的前向耗时与显存（差距巨大）——参数量与输入长度无关、计算量却随 token 数平方增长，正是"为什么必须分解"的答案。
5. **参数化 patch 大小**：让 `TinyVideoDiT` 接收 `patch=(pt, ph, pw)`，同时用于 `VideoPatch3D` 和输出头，消除硬编码。
6. **加时间步条件**：仿照第 23 节的 AdaLN，用一个小 MLP 把扩散时间步 `t` 映射成每个 LayerNorm 的 `scale` 和 `shift`。

---

## 8. 常见坑

- **`view` 用在不连续张量上**：`permute` / `transpose` 之后合并维度要用 `reshape`（或先 `.contiguous()`），否则报 "view size is not compatible with input tensor's size and stride"。
- **token 排列顺序搞错**：patch 化按 t → h → w 展平，分解注意力和 unpatchify 都必须遵守同一顺序；任何一处写反，形状仍然正确，但时间和空间会被"打乱"，且不会报错。
- **忘记 `batch_first=True`**：`nn.MultiheadAttention` 默认输入是 `(seq, batch, dim)`，写错不会报错，但注意力会在错误的维度上计算。
- **用普通列表存子模块**：`self.blocks = [Block(), Block()]` 不会注册参数，训练时它们不更新；必须用 `nn.ModuleList`。
- **以为分解注意力"免费"**：时间项和空间项相加仍可能非常大（本例空间项 5.47 亿），高分辨率下还需要窗口注意力等手段。
- **尺寸不能被 patch 整除**：`Conv3d` 和 `//` 都会静默丢弃边缘，unpatchify 回来的视频会比输入小。
