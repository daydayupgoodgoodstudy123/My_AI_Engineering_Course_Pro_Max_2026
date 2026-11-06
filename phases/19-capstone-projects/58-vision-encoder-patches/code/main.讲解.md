# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 58 节 视觉 Encoder 的图像 Patches ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下）；测试：`python3 -m unittest test_main.py` 或 `python3 -m pytest -q test_main.py` ｜ **依赖**：第三方 `torch`（CPU 即可）、`numpy`；标准库 `math`、`dataclasses`

---

## 1. 这份代码在考察什么

这是"视觉-语言"Track（第 58–63 节）的第一块积木：把一张图像变成 Transformer 能吃的 token 序列。它考察：

1. **Patch 切分与展平**：224×224 的图像切成 14×14 个 16×16 的方块，每块 `3 × 16 × 16 = 768` 个像素值。
2. **Conv2d 即线性投影**：`kernel_size = stride = patch_size` 的卷积等价于"展平后乘矩阵"，代码同时提供两种写法并验证数值一致。
3. **2D 正弦位置编码**：一半维度编码行、一半编码列，固定计算、0 参数。
4. **CLS token 与序列组装**：在 196 个 patch token 前拼一个可学习的 CLS，得到 `(B, 197, 768)`。
5. **张量形状直觉**：`flatten`、`transpose`、`unfold`、`permute`、`expand`、`cat` 的配合。

> 一句话：**用一个 Conv2d、一张正弦表和一个 CLS 向量，把 `(B, 3, 224, 224)` 变成 `(B, 197, 768)`**。这一层没有任何 patch 之间的交互——交互留给第 59 节的自注意力。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `FrontEndConfig` | 冻结 dataclass | `image_size`、`patch_size`、`in_channels`、`hidden`；派生 `grid_size`、`num_patches` | 配置与整除检查 |
| `sinusoidal_2d` | 函数 | 生成 `(grid_h · grid_w, dim)` 的 2D 正弦位置表 | 位置编码 |
| `PatchEmbed` | `nn.Module` | 输入检查 + `Conv2d` 投影 + `flatten(2).transpose(1, 2)` | patch 投影 |
| `VisionFrontEnd` | `nn.Module` | `PatchEmbed` + CLS 拼接 + 加位置编码 | 前端整体 |
| `synthesize_image` | 函数 | 用 NumPy 生成确定性的 `(1, 3, 224, 224)` 图像（梯度 + 噪声） | 合成测试夹具 |
| `unfold_then_linear` | 函数 | 用 `unfold` + 矩阵乘实现同样的投影，作为参考实现 | 等价性检查 |
| `describe_token_norms` | 函数 | 返回前几个 token 的 L2 范数字符串 | 调试输出 |
| `main` | 函数 | 打印配置、参数量、输出形状、范数、位置签名、batch 一致性与等价性检查 | 演示 |

数据流：`synthesize_image` → `(1, 3, 224, 224)` → `PatchEmbed`：`Conv2d` → `(1, 768, 14, 14)` → `flatten(2)` → `(1, 768, 196)` → `transpose(1, 2)` → `(1, 196, 768)` → 拼 CLS → `(1, 197, 768)` → `+ pos_embed (1, 197, 768)` → 输出。

---

## 3. 逐段精讲

### 3.1 配置：`FrontEndConfig`

```python
@dataclass(frozen=True)
class FrontEndConfig:
    image_size: int = 224
    patch_size: int = 16
    in_channels: int = 3
    hidden: int = 768

    @property
    def grid_size(self) -> int:
        if self.image_size % self.patch_size != 0:
            raise ValueError(...)
        return self.image_size // self.patch_size

    @property
    def num_patches(self) -> int:
        return self.grid_size * self.grid_size
```

- `frozen=True`：实例不可修改，可以安全地在多个模块之间共享，也可以作为字典键。
- `grid_size` 用 `@property` 按需计算，并在不能整除时报错——比如 `image_size=225` 会立刻失败，而不是在卷积后得到 14×14 却"悄悄丢掉"最后一行像素（无 padding 的卷积会截断）。
- 只支持正方形图像（一个 `image_size`）。讲义练习 3 要求支持非正方形（见测验 Q10）。

### 3.2 2D 正弦位置表

```python
def sinusoidal_2d(grid_h: int, grid_w: int, dim: int) -> torch.Tensor:
    if dim % 4 != 0:
        raise ValueError(...)
    half = dim // 2
    quarter = half // 2

    freq = torch.arange(quarter, dtype=torch.float32)
    inv = torch.exp(-math.log(10000.0) * freq / max(1, quarter))

    rows = torch.arange(grid_h, dtype=torch.float32).unsqueeze(1) * inv.unsqueeze(0)
    cols = torch.arange(grid_w, dtype=torch.float32).unsqueeze(1) * inv.unsqueeze(0)

    row_emb = torch.cat([torch.sin(rows), torch.cos(rows)], dim=1)
    col_emb = torch.cat([torch.sin(cols), torch.cos(cols)], dim=1)

    table = torch.zeros(grid_h, grid_w, dim)
    table[:, :, :half] = row_emb.unsqueeze(1).expand(-1, grid_w, -1)
    table[:, :, half:] = col_emb.unsqueeze(0).expand(grid_h, -1, -1)
    return table.reshape(grid_h * grid_w, dim)
```

以 `dim = 768`、14×14 网格为例：

| 变量 | 形状 | 含义 |
|------|------|------|
| `inv` | `(192,)` | 频率 `ω_i = exp(−ln(10000) · i / 192) = 10000^(−i/192)`，从 1 递减到约 1/10000 |
| `rows` | `(14, 192)` | 外积 `row × ω_i`（`unsqueeze` + 广播实现） |
| `row_emb` | `(14, 384)` | `[sin(rows), cos(rows)]` |
| `col_emb` | `(14, 384)` | 同理，按列号 |
| `table[:, :, :384]` | `(14, 14, 384)` | 行编码沿列方向 `expand` 复制：同一行的所有位置前半段相同 |
| `table[:, :, 384:]` | `(14, 14, 384)` | 列编码沿行方向复制：同一列的所有位置后半段相同 |
| 返回值 | `(196, 768)` | 按行优先展平，第 k 行对应网格 `divmod(k, 14)` |

- `dim % 4 == 0` 的要求来自"两半 × 每半 sin/cos 两段"。
- 这是 Transformer 原始 1D 正弦公式（讲义："Attention Is All You Need ... adapted here to 2D"）的二维版本；与原始 1D 版本的差别是 sin、cos 不交错排列，而是分块拼接——对模型而言只是维度的一个固定置换，没有本质区别。
- **两个重要性质**（已实测，见测验 Q5、Q11）：
  - 每个位置的范数都是 `sqrt(dim/2) = sqrt(384) ≈ 19.596`，因为每对 `sin² + cos² = 1`；
  - 两个位置的点积 = `Σ cos(Δrow · ω_i) + Σ cos(Δcol · ω_i)`，只依赖相对位移：(0,0) 与自身 384、与 (0,1) 378.77、与 (0,13) 318.99、与 (13,13) 253.98。
- `expand` 不复制内存，只创建视图；随后的赋值 `table[...] = ...` 才真正写入。
- 讲义说"norms are uniform within a row"——实际上是所有位置的范数都相同。

### 3.3 `PatchEmbed`：Conv2d 投影

```python
        self.proj = nn.Conv2d(
            cfg.in_channels, cfg.hidden,
            kernel_size=cfg.patch_size, stride=cfg.patch_size, bias=True,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() != 4: raise ValueError(...)
        if x.shape[1] != self.cfg.in_channels: raise ValueError(...)
        if x.shape[2] != self.cfg.image_size or x.shape[3] != self.cfg.image_size:
            raise ValueError(...)
        out = self.proj(x)
        b = out.shape[0]
        out = out.flatten(2).transpose(1, 2)
        return out
```

- 权重形状 `(768, 3, 16, 16)`，参数 `589,824 + 768 = 590,592`（与讲义一致）。
- 卷积窗口不重叠地扫过图像：输出位置 (i, j) 只看像素块 `[16i:16i+16, 16j:16j+16]`，第 k 个通道的值 = 该块与第 k 个滤波器的点积 + bias——这正是"展平后做线性变换"。
- `flatten(2)`：把第 2 维及之后（14, 14）合成一维 196，得 `(B, 768, 196)`；`transpose(1, 2)` 交换后得 `(B, 196, 768)`，即"序列长度在前、特征在后"的 Transformer 约定。展平顺序是行优先：token 0 是左上角，token 13 是第一行最右，token 14 是第二行最左。
- 三重输入检查让错误信息清晰（比如把 NHWC 格式的图像误传进来，会在通道检查处报错）。
- ⚠️ 空间尺寸**严格等于** `image_size`，否则报错——这与讲义"正弦编码可以换分辨率"的说法相冲突：编码公式本身支持任意网格，但这份实现不支持（测验 Q6）。
- `b = out.shape[0]` 赋值后没有使用，是遗留代码。

### 3.4 `VisionFrontEnd`：CLS + 位置编码

```python
        self.patch = PatchEmbed(cfg)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, cfg.hidden))
        nn.init.trunc_normal_(self.cls_token, std=0.02)

        pos = sinusoidal_2d(cfg.grid_size, cfg.grid_size, cfg.hidden)
        cls_pos = torch.zeros(1, cfg.hidden)
        full = torch.cat([cls_pos, pos], dim=0).unsqueeze(0)
        self.register_buffer("pos_embed", full, persistent=False)

    def forward(self, x):
        tokens = self.patch(x)
        b = tokens.shape[0]
        cls = self.cls_token.expand(b, -1, -1)
        tokens = torch.cat([cls, tokens], dim=1)
        tokens = tokens + self.pos_embed
        return tokens
```

- `nn.Parameter` 让 CLS 成为可训练参数（会出现在 `model.parameters()` 里）；`trunc_normal_(std=0.02)` 是 ViT 系常用初始化，截断在 ±2σ 内。
- `register_buffer(..., persistent=False)`：位置表是模块状态的一部分（会随 `.to(device)` 移动），但**不是参数**（不参与梯度、不计入参数量），`persistent=False` 还让它不进入 `state_dict`——因为它可以随时重新计算，没必要存。
- 位置表形状 `(1, 197, 768)`：第 0 行是 CLS 的全 0 位置，第 1–196 行是网格位置。
- `expand(b, -1, -1)`：把 `(1, 1, 768)` 的 CLS 视作 `(b, 1, 768)`，不复制内存；`-1` 表示该维保持不变。
- `torch.cat([cls, tokens], dim=1)`：沿序列维拼接，CLS 在最前。
- `tokens + self.pos_embed`：`(B, 197, 768) + (1, 197, 768)`，广播到每个样本。

### 3.5 合成图像夹具

```python
def synthesize_image(seed: int, image_size: int = 224, channels: int = 3) -> torch.Tensor:
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((channels, image_size, image_size)).astype("float32") * 0.1
    y_coords = np.linspace(0.0, 1.0, image_size, dtype="float32")
    x_coords = np.linspace(0.0, 1.0, image_size, dtype="float32")
    gx, gy = np.meshgrid(x_coords, y_coords, indexing="xy")
    gradient = np.stack([gx, gy, (gx + gy) * 0.5], axis=0).astype("float32")
    img = np.clip(gradient + noise + 0.5, 0.0, 1.0)
    return torch.from_numpy(img).unsqueeze(0)
```

- 三个通道分别是"从左到右变亮""从上到下变亮""对角渐变"，加上 σ = 0.1 的噪声，再整体 +0.5 并裁剪到 [0, 1]。
- `meshgrid(indexing="xy")` 返回的 `gx[i, j] = x_coords[j]`，即随列变化；`gy` 随行变化。
- 因为 +0.5 后大部分像素超过 1 被裁剪，实测像素范围是 `[0.156, 1.000]`，右下区域大面积饱和为 1——作为"有高低频内容"的夹具足够，但不同 seed 的图像只是噪声不同、整体结构完全相同。这一点在第 60 节会造成"所有图像特征几乎一样"的问题。
- `torch.from_numpy` 与 NumPy 数组共享内存，`unsqueeze(0)` 加 batch 维。

### 3.6 参考实现 `unfold_then_linear`

```python
    patches = x.unfold(2, patch_size, patch_size).unfold(3, patch_size, patch_size)
    b, c, gh, gw, ph, pw = patches.shape
    flat = patches.permute(0, 2, 3, 1, 4, 5).reshape(b, gh * gw, c * ph * pw)
    w_flat = weight.reshape(weight.shape[0], -1)
    return flat @ w_flat.T + bias
```

- `Tensor.unfold(dim, size, step)`：在 `dim` 维上以 `step` 为步长取长度为 `size` 的窗口，窗口内容追加为新的最后一维。两次 unfold 后形状 `(b, c, 14, 14, 16, 16)`。
- `permute(0, 2, 3, 1, 4, 5)` → `(b, 14, 14, c, 16, 16)`，再 reshape 成 `(b, 196, 768)`：每个 patch 按 **c → 行 → 列** 展平，与 `weight.reshape(768, -1)` 的展平顺序一致。
- `permute` 产生非连续张量，`reshape` 会在需要时自动复制（`view` 则会报错）。
- 如果把通道放到最后（`permute(0, 2, 3, 4, 5, 1)`），形状依然合法，但与权重顺序不匹配，实测最大误差 2.59（测验 Q9）——这正是讲义说的"If they do not, the unfold math is wrong"。
- 这个函数是讲义练习 2（用 `nn.Unfold` + `nn.Linear` 重写）的手写版本。

### 3.7 `main()`：演示与自检

- 打印配置：`grid 14x14`、`num patches 196`、`seq length 197`。
- `torch.manual_seed(0)` 固定 Conv2d 与 CLS 的随机初始化。
- `model.eval()`：本模块没有 dropout/BN，`eval()` 只是好习惯。
- `with torch.no_grad()`：推理时不建立计算图，省内存。
- **位置签名**：打印 `model.pos_embed[0, 1, :8]`——下标 1 是网格 (0,0)，前 192 维是 `sin(0) = 0`，所以全 0，看不出"签名"（测验 Q4）；改成 `pos_embed[0, 16, :8]`（网格 (1,1)）会更有意义。
- **batch 一致性**：同一张图复制 4 份，检查输出逐行相同（drift 0.000000），确认没有跨样本的信息泄漏。
- **等价性**：用模型自己的 Conv2d 权重跑参考实现，最大误差 `2.68e-6 < 1e-4`。注意这一段的 `model.patch(img)` 没有放在 `no_grad` 里，会多建一张计算图，不影响结果。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| Conv2d 实现 patch 投影 | 一个算子完成切块 + 投影，GPU 上快，权重格式与主流预训练模型一致 | 需要额外的等价性测试来确认理解正确 |
| 固定 2D 正弦位置 | 0 参数、确定、公式上支持任意网格 | 原版 ViT 用可学习 1D 位置；固定分辨率下可学习的往往拟合更好（讲义练习 1） |
| 位置表在 `__init__` 中按固定网格生成 | 简单，前向无额外计算 | 无法换分辨率；应按输入网格动态生成或缓存多个尺寸（测验 Q10） |
| 严格的输入尺寸检查 | 错误尽早暴露 | 与"可换分辨率"的说法冲突；生产中通常允许可整除的任意尺寸 |
| CLS 位置为 0 | CLS 不对应空间位置 | 也可以给 CLS 单独的可学习位置 |
| `persistent=False` 的 buffer | 可重算的状态不必保存 | 若换成可学习位置，必须改为 `nn.Parameter` 并保存 |
| 合成夹具（梯度 + 噪声） | 无需下载数据，完全确定 | 不同 seed 的图像结构相同，不适合需要"图像差异"的实验（第 60 节） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class FrontEndConfig` | 不可变配置对象，可哈希 |
| `@property` | `grid_size`、`num_patches` | 计算属性，像字段一样访问 |
| f-string 中的 `{x!r}` / 格式 | `f"{v:.3f}"`、`f"{v:+.3f}"`、`f"{n_params:,}"` | 3 位小数；带正负号；千分位 |
| `nn.Module` 子类 | `class PatchEmbed(nn.Module)` | `__init__` 中先 `super().__init__()`，再注册子模块与参数 |
| `nn.Parameter` | `self.cls_token = nn.Parameter(torch.zeros(1, 1, D))` | 可训练张量，自动加入 `parameters()` |
| `register_buffer` | `self.register_buffer("pos_embed", full, persistent=False)` | 非参数状态，随设备移动 |
| `nn.init.trunc_normal_` | `nn.init.trunc_normal_(self.cls_token, std=0.02)` | 原地初始化（下划线结尾表示 in-place） |
| `torch.arange` / `torch.exp` | `torch.arange(quarter, dtype=torch.float32)` | 生成等差序列 |
| `unsqueeze` + 广播 | `rows = arange(H).unsqueeze(1) * inv.unsqueeze(0)` | `(H,1) * (1,Q)` → `(H,Q)` 外积 |
| `torch.cat` | `torch.cat([torch.sin(rows), torch.cos(rows)], dim=1)` | 沿指定维拼接 |
| `expand` | `row_emb.unsqueeze(1).expand(-1, grid_w, -1)` | 不复制内存的"复制"；`-1` 表示保持原尺寸 |
| 切片赋值 | `table[:, :, :half] = ...` | 写入张量的一部分 |
| `flatten(start_dim)` | `out.flatten(2)` | 从第 2 维开始合并 |
| `transpose` / `permute` | `transpose(1, 2)`、`permute(0, 2, 3, 1, 4, 5)` | 交换两维 / 任意重排维度 |
| `Tensor.unfold` | `x.unfold(2, P, P)` | 滑动窗口切块 |
| `reshape` 与 `-1` | `weight.reshape(weight.shape[0], -1)` | `-1` 自动推断该维大小 |
| `@` 与 `.T` | `flat @ w_flat.T + bias` | 矩阵乘与转置；bias 广播 |
| 元组解包 | `b, c, gh, gw, ph, pw = patches.shape` | 一次取出 6 个维度 |
| `torch.no_grad()` | `with torch.no_grad(): tokens = model(img)` | 上下文管理器，关闭梯度追踪 |
| `.item()` / `.tolist()` | `img.min().item()`、`norms[:max_show]` | 张量转 Python 标量 / 列表 |
| NumPy 随机与网格 | `np.random.default_rng(seed)`、`np.meshgrid(..., indexing="xy")` | 可复现随机数；坐标网格 |
| `np.clip` / `np.stack` | `np.clip(..., 0.0, 1.0)`、`np.stack([...], axis=0)` | 裁剪数值；沿新维堆叠 |
| `torch.from_numpy` | `torch.from_numpy(img).unsqueeze(0)` | 与 NumPy 共享内存的转换 |
| `", ".join(生成器)` | `", ".join(f"{v:.3f}" for v in head)` | 拼接字符串 |
| `if __name__ == "__main__"` | 文件末尾 | 被测试导入时不执行 `main()` |

---

## 6. 运行结果解读

实际运行（PyTorch CPU，`python3 main.py`，耗时约 1.8 秒）：

```text
  image size : 224
  patch size : 16
  grid size  : 14x14
  num patches: 196
  hidden     : 768
  seq length : 197 (includes CLS)

fixture image shape  : (1, 3, 224, 224)
fixture image dtype  : torch.float32
fixture pixel range  : [0.156, 1.000]

front-end params     : 591,360
output token shape   : (1, 197, 768)
CLS token norm       : 0.534
first 8 token norms  : 0.534, 21.308, 21.554, 22.034, 22.276, 22.601, 22.653, 22.798

position embedding row signature:
  pos[1, :8] = +0.000, +0.000, +0.000, +0.000, +0.000, +0.000, +0.000, +0.000

batch consistency check:
  batch=4 output shape: (4, 197, 768)
  max drift across identical batch rows: 0.000000

unfold reference vs Conv2d projection:
  max abs diff : 2.682209e-06
  ok: unfold reference matches Conv2d to float tolerance
```

逐项解读：

- **196 / 197**：`224 / 16 = 14`，`14² = 196`，加 CLS 得 197，与讲义一致。
- **像素范围 [0.156, 1.000]**：上限被 `np.clip` 截断，说明大量像素饱和。
- **参数 591,360** = 投影 590,592 + CLS 768，与讲义"590,592 parameters in the projection, 768 in the CLS token"一致；位置表是 buffer，不计入。
- **CLS 范数 0.534**：CLS 加的是全 0 位置，范数就是 CLS 参数本身；`trunc_normal(std=0.02)` 的 768 维向量期望范数约 `0.02 × sqrt(768) ≈ 0.554`。
- **patch token 范数 21–23**：位置向量的范数恒为 19.596，再叠加 Conv2d 投影（随机初始化）的输出，两者大致正交，合成后约 21–23。随列号增加缓慢变大，与图像左→右变亮的梯度一致。
- **pos[1, :8] 全 0**：网格 (0,0) 的行编码前 192 维是 `sin(0)`（测验 Q4）。
- **batch drift 0**：同一图像复制 4 份，输出完全相同，CLS 广播没有串样本。
- **等价性误差 2.7e-6**：两条路径的浮点累加顺序不同，误差在 float32 的正常范围内。

---

## 7. 动手改一改

1. **换个位置签名**：把打印改为 `pos_embed[0, 16, :8]`（网格 (1,1)）和 `pos_embed[0, 16, 384:392]`，对照测验 Q11 的手算结果。
2. **讲义练习 2**：用 `nn.Unfold(kernel_size=16, stride=16)` + `nn.Linear(768, 768)` 重写投影，把 Conv2d 的权重 `reshape` 后拷贝进 Linear，断言输出 `allclose`（注意 `nn.Unfold` 的输出形状是 `(B, C·P·P, L)`，需要 `transpose(1, 2)`）。
3. **讲义练习 3**：按测验 Q10 支持 224×320 等非正方形输入，验证输出 `(B, 281, 768)`。
4. **讲义练习 1**：把位置编码换成 `nn.Parameter(torch.zeros(1, 197, 768))` + `trunc_normal_`，再写测验 Q12 的 `resize_pos_embed` 把它插值到 24×24 网格。
5. **讲义练习 4**：用 `time.perf_counter` 测量 batch 为 1、8、64 时 `PatchEmbed` 的耗时，与第 59 节整个 encoder 的耗时比较，验证"patch 投影很少是瓶颈"。
6. **可视化**：取 `sinusoidal_2d(14, 14, 768)`，计算 (7,7) 与所有位置的点积，reshape 成 14×14 画热力图，观察它随距离衰减、且行列方向对称。

---

## 8. 常见坑

- **unfold 后 permute 顺序写错**：形状对、数值错，只能靠等价性测试发现（测验 Q9）。
- **合头/展平时把通道放最后**：PyTorch 的卷积权重是 `(out, in, kh, kw)`，通道在前；einops 教程里常见的 `(p1 p2 c)` 顺序要配合相应的权重排列。
- **把 `pos[1]` 当成第一个位置的"签名"**：第 0 行是 CLS，网格 (0,0) 的前半段又全是 0。
- **图像尺寸不能整除 patch 大小**：无 padding 的卷积会默默截断边缘像素；本节在 `grid_size` 里显式报错。
- **以为正弦编码"自动支持任意分辨率"**：公式支持，实现不一定支持；本节实现会直接抛 `spatial mismatch`。
- **`register_buffer` 与 `nn.Parameter` 混淆**：buffer 不参与训练；若想让位置可学习，必须用 Parameter。
- **`persistent=False` 的 buffer 不在 `state_dict` 里**：加载别人保存的权重时不会覆盖它，这里没问题（它是确定性的），但如果换成可学习位置就必须保存。
- **NCHW 与 NHWC 混淆**：PIL/NumPy 读图通常是 `(H, W, C)`，传给 Conv2d 前要 `permute(2, 0, 1)`；本节的通道检查能捕获这一错误。

---

## 9. 测试在验证什么

测试文件：`code/test_main.py`（9 个测试），直接 `from main import ...`，需在 `code/` 目录下运行。

| 测试类 / 测试 | 验证的性质 | 说明 |
|--------------|-----------|------|
| `TestPatchEmbed.test_patch_count_matches_grid` | `num_patches == (image_size / patch_size)²` | 224/16 → 196；96/16 → 36 |
| `TestPatchEmbed.test_output_shape_includes_cls` | 输出 `(B, num_patches + 1, hidden)` | 64×64、P=16、hidden=32，batch 2 → `(2, 17, 32)` |
| `TestPatchEmbed.test_conv2d_matches_unfold_reference` | Conv2d 与 unfold-then-linear 在 `atol=1e-5` 内一致 | 本节最核心的数学等价性测试 |
| `TestPositionEmbedding.test_sinusoidal_deterministic` | 两次调用结果 `torch.equal` | 无随机状态 |
| `TestPositionEmbedding.test_sinusoidal_shape` | `(14, 14, 64)` → `(196, 64)` | 形状约定 |
| `TestPositionEmbedding.test_sinusoidal_requires_div_by_four` | `dim = 30` 抛 `ValueError` | 输入校验 |
| `TestVisionFrontEnd.test_cls_token_broadcasts_without_leakage` | batch 中每个样本的 CLS 输出非零且彼此相同 | 由于 CLS 在前端与图像无关，这个性质是必然成立的；它主要防止 `expand`/`cat` 写错维度 |
| `TestVisionFrontEnd.test_rejects_wrong_spatial_size` | 48×48 输入到 32×32 配置时报错 | 严格尺寸检查 |
| `TestVisionFrontEnd.test_synthesize_image_is_deterministic` | 同 seed 两次完全相同，形状 `(1, 3, 224, 224)` | 夹具可复现 |

运行方式（在 `code/` 目录下）：

```bash
python3 -m unittest test_main.py -v
# 或
python3 -m pytest -q test_main.py
```

实际运行结果：`9 passed in 1.14s`。

覆盖空白：没有测试检查位置编码的数值性质（范数恒定、点积只依赖相对位移），也没有测试 `permute` 写错时能被发现（可以加一个"错误实现应当不等价"的反例测试）；讲义提到的"reconstruction / 非正方形网格"在代码与测试中都没有实现。
