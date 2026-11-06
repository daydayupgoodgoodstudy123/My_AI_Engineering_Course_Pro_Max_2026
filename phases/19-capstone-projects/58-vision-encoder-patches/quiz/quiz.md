# 测验 · 视觉 Encoder 的图像 Patches（Vision Encoder Patches）

> **阶段 19 · 综合项目 · 第 58 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Patch embedding 是"像素的 tokenizer" | 把图像切成 P×P 的方块，每块展平后经一次线性投影变成一个 token；224×224、P=16 → 14×14 = 196 个 patch |
| 2 | 为什么不用逐像素 token | 224×224×3 有 150,528 个值；注意力是序列长度的平方，`150,528² / 196² = 589,824`，约 59 万倍的差距（讲义："a 590,000x reduction"） |
| 3 | 每个 patch 的维度 | `(3, 16, 16)` 展平为 768 个数，再投影到 `hidden`（ViT-Base 为 768） |
| 4 | `Conv2d` 技巧 | `Conv2d(3, hidden, kernel_size=P, stride=P)` 无 padding，等价于 unfold + linear：每个输出位置就是 patch 像素与一个滤波器的点积 |
| 5 | 输出整形 | Conv 输出 `(B, hidden, 14, 14)` → `flatten(2)` 得 `(B, hidden, 196)` → `transpose(1, 2)` 得 `(B, 196, hidden)`，patch 按行优先排列 |
| 6 | 2D 正弦位置编码 | 维度一半编码行、一半编码列；每一半再分 sin/cos 两个 quarter，频率 `ω_i = 10000^(−i/quarter)`；固定计算、0 参数；要求 `dim % 4 == 0` |
| 7 | CLS token | 可学习的 `(1, 1, hidden)` 向量（`trunc_normal`，std 0.02），拼在序列最前面；本节代码给它的位置编码是全 0 |
| 8 | 参数量 | 投影 `3·P·P·hidden + hidden = 590,592`，CLS 768，位置 0，合计 **591,360**（ViT-B/16、224 分辨率） |
| 9 | 输出形状 | `(B, num_patches + 1, hidden)`，默认配置为 `(1, 197, 768)` |
| 10 | 等价性作为健全性检查 | 用同一组权重比较 Conv2d 路径与 unfold-then-linear 路径，最大误差应在浮点容差内（本节实测 2.7e-6）；对不上说明 unfold 的维度顺序写错了 |

### 核心技能（能动手做到）

- [ ] 给定图像尺寸、patch 大小、通道数和 hidden，算出 patch 数、序列长度和投影层参数量
- [ ] 用 `Tensor.unfold` + `permute` + `reshape` 手写 patch 展平，并说清每一维的含义与顺序
- [ ] 解释为什么 `Conv2d(kernel=stride=P)` 与"展平后乘矩阵"数值相同，以及 `permute` 写错时会发生什么
- [ ] 手算 2D 正弦位置编码某个位置、某个维度的数值，并说明为什么所有位置向量的范数都相同
- [ ] 改造前端以支持非正方形输入或运行时改变分辨率（重新生成或插值位置编码）
- [ ] 读懂并运行本节 9 个单元测试，说明每个测试保护的性质

---

## 二、基础自测（选择题）

**Q1.** 一张 336×336 的 RGB 图像，用 patch 大小 14 切分，再拼上 1 个 CLS token。序列长度是：

- A. 576
- B. 257
- C. 441
- D. 577

**Q2.** 本节默认配置（224 分辨率、P=16、hidden=768）下 `VisionFrontEnd` 的可训练参数量是：

- A. 591,360
- B. 590,592
- C. 589,824
- D. 742,656

**Q3.** `x.unfold(2, P, P).unfold(3, P, P)` 得到形状 `(b, c, gh, gw, ph, pw)`。要与 `Conv2d` 权重 `(hidden, c, P, P)` 展平后的顺序对齐，下一步应该是：

- A. `permute(0, 2, 3, 4, 5, 1)`，把通道放到最后
- B. 不做 permute，直接 `reshape(b, gh * gw, c * ph * pw)`
- C. `permute(0, 2, 3, 1, 4, 5)`，得到 `(b, gh, gw, c, ph, pw)` 再 reshape
- D. `permute(0, 4, 5, 1, 2, 3)`

**Q4.** 运行 `main.py` 时，`pos[1, :8]`（即 `model.pos_embed[0, 1, :8]`）打印出来全是 `+0.000`。原因是：

- A. 位置编码还没训练，所以是 0
- B. 下标 1 对应第一个 patch（第 0 行第 0 列）；前 192 维是 `sin(row · ω)`，row = 0 时全为 0
- C. CLS 的位置编码是 0
- D. `sinusoidal_2d` 有 bug，前 8 维总是 0

**Q5.** `sinusoidal_2d(14, 14, 768)` 生成的 196 个位置向量，它们的 L2 范数：

- A. 随行号增大而增大
- B. 全部相同，等于 `sqrt(384) ≈ 19.60`
- C. 全部等于 1
- D. 全部等于 `sqrt(768) ≈ 27.71`

**Q6.** 讲义说正弦位置编码"lets you swap resolutions without retraining"。用默认配置构造 `VisionFrontEnd(FrontEndConfig())`，再输入一张 256×256 的图像，结果是：

- A. 自动对位置编码做插值，输出 `(1, 257, 768)`
- B. 输出 `(1, 197, 768)`，多余的像素被裁掉
- C. 输出 `(1, 257, 768)`，但位置编码只加到前 197 个 token
- D. 抛出 `ValueError: spatial mismatch`：`PatchEmbed` 严格检查输入尺寸，位置表也在构造时按 14×14 固定

**Q7.** 讲义说 patch 化让注意力计算量降低了约 590,000 倍。这个倍数来自：

- A. `(150,528 / 196)² = 768² = 589,824`
- B. `150,528 / 196 = 768`
- C. `196² = 38,416`
- D. `150,528² ≈ 22.6 billion`

**Q8.** 在本节 `VisionFrontEnd` 中，CLS token 加上的位置编码是：

- A. 一个可学习的位置向量
- B. 第 (0, 0) 个网格位置的正弦编码
- C. 全 0 向量（`cls_pos = torch.zeros(1, cfg.hidden)`）
- D. 每次前向随机生成

---

## 三、动手 / 代码题

**Q9.** 某同学把参考实现写成了下面这样，测试 `test_conv2d_matches_unfold_reference` 失败了：

```python
def unfold_then_linear_v2(x, weight, bias, patch_size):
    patches = x.unfold(2, patch_size, patch_size).unfold(3, patch_size, patch_size)
    b, c, gh, gw, ph, pw = patches.shape
    flat = patches.permute(0, 2, 3, 4, 5, 1).reshape(b, gh * gw, ph * pw * c)
    w_flat = weight.reshape(weight.shape[0], -1)
    return flat @ w_flat.T + bias
```

1. 指出错误，并解释为什么"形状完全正确"却数值不对。
2. 给出两种修复方式（改输入一侧 / 改权重一侧）。
3. 用一张 1×1×4×4、像素值为 0..15 的图像、P=2，写出正确实现下 4 个 patch 的展平结果。

**Q10.** 讲义练习 3 要求支持非正方形输入。请修改 `FrontEndConfig` 与 `VisionFrontEnd`，使其支持 `image_h ≠ image_w`（例如 224×320），并让 `forward` 在输入尺寸与配置不同时**按实际网格重新生成**正弦位置表（而不是报错）。写出关键代码，并说明 CLS 的位置如何处理。

**Q11.** 手算位置编码（`grid = 14`、`dim = 768`，所以 `half = 384`、`quarter = 192`）：

1. `sinusoidal_2d` 返回表中的第 15 行对应网格的哪个 (row, col)？在 `model.pos_embed` 中又是第几行？
2. 写出该行第 0、192、384、576 维的值（保留 4 位小数）。
3. 已知同一张表中：自身点积 384、与右邻 (0,1) 的点积约 378.77、与 (0,13) 约 318.99、与 (13,13) 约 253.98（均以 (0,0) 为基准）。这说明了正弦位置编码的什么性质？

**Q12.** 原版 ViT 使用的是**可学习**的位置 embedding；在更高分辨率上微调时，需要把预训练好的位置表插值到新网格。请写一个函数 `resize_pos_embed(pos, old_grid, new_grid)`：输入 `(1, 1 + old_grid², D)`（含 CLS），输出 `(1, 1 + new_grid², D)`，用 `F.interpolate` 做双三次插值。

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述 ViT 的 patch embedding：从 `(B, 3, 224, 224)` 的图像到送入 Transformer 的 token 序列，每一步的张量形状、参数量分别是多少？

**Q14.**（原理深挖）为什么 `Conv2d(kernel_size=P, stride=P)` 与 "unfold + Linear" 数学上等价？生产代码为什么更常用 Conv2d？如果换成 kernel 大于 stride 的重叠卷积，还等价吗？

**Q15.**（原理深挖）图像 Transformer 的位置编码有哪些方案？固定 2D 正弦、可学习 1D、2D RoPE 各有什么优缺点？如何处理推理分辨率与训练分辨率不同的情况？

**Q16.**（工程实践）patch 大小选 14、16 还是 32？对文档 OCR、细粒度定位、视频这类任务，你会如何权衡 token 数与细节？

**Q17.**（追问型）在 patch 前端这一层，CLS token 对所有图像的输出都一样吗？那它是怎么变成"整张图的摘要"的？有没有不用 CLS 的做法？

---

## 五、参考答案与解析

### Q1 — 答案：D

`336 / 14 = 24`，`24 × 24 = 576` 个 patch，加 1 个 CLS 得 577。A 漏了 CLS；B 是 224 分辨率、P=14 的结果（16×16 = 256，+1 = 257）；C 是 `21²`，与题设无关。`FrontEndConfig.grid_size` 会先检查 `image_size % patch_size == 0`，336 能被 14 整除。

### Q2 — 答案：A

投影层：权重 `768 × 3 × 16 × 16 = 589,824`，bias 768，共 590,592；CLS token 768；正弦位置编码用 `register_buffer` 注册，不是参数。合计 591,360（实际运行打印 `front-end params : 591,360`）。B 漏了 CLS；C 只有投影权重；D 是"若改用 197 个可学习位置 embedding"时的数字（`591,360 + 197 × 768 = 742,656`）。

### Q3 — 答案：C

`Conv2d` 的权重形状是 `(out, c, kh, kw)`，`weight.reshape(out, -1)` 后每一行按 **c → kh → kw** 的顺序展平。输入侧也必须按 `(c, ph, pw)` 的顺序展平，所以把 `(gh, gw)` 移到前面、保持 `(c, ph, pw)` 相对顺序不变：`permute(0, 2, 3, 1, 4, 5)`。A 是"通道最后"（einops 里 `(p1 p2 c)` 的常见写法），形状对但顺序与权重不匹配（我们实测最大误差 2.59）；B 不 permute 时 `reshape` 会把 `(c, gh, gw, ph, pw)` 直接摊平，patch 之间的像素被混在一起；D 维度顺序完全错乱。

### Q4 — 答案：B

`pos_embed` 的第 0 行是 CLS（全 0），第 1 行才是表中的第 0 个位置，也就是网格 (0, 0)。`sinusoidal_2d` 的前 `quarter = 192` 维是 `sin(row · ω_i)`，row = 0 时全是 0；第 192–383 维是 `cos(0) = 1`。所以 "pos[1, :8]" 恰好落在全 0 的区间，这一行"签名"其实看不出任何东西。C 说的是第 0 行；A 错，正弦编码不需要训练；D 错，换成 `pos[15, :8]`（网格 (1,1)）就能看到 `0.841, 0.815, 0.789, ...`。

### Q5 — 答案：B

每个位置在行的一半里有 192 对 `(sin(r·ω_i), cos(r·ω_i))`，每对的平方和为 1，贡献 192；列的一半同理再贡献 192。总平方和 384，范数 `sqrt(384) ≈ 19.5959`，与位置无关（已实测：最小 19.59592，最大 19.59592）。讲义说"The position embedding norms are uniform within a row"——其实是**所有位置**都相同，不只是同一行内。这也解释了 demo 中 patch token 的范数都在 21–23 左右：位置向量贡献了约 19.6 的固定"底座"。

### Q6 — 答案：D

`PatchEmbed.forward` 中：

```python
if x.shape[2] != self.cfg.image_size or x.shape[3] != self.cfg.image_size:
    raise ValueError(f"spatial mismatch: ...")
```

位置表在 `__init__` 中按 `cfg.grid_size` 生成并注册为 buffer，不会随输入改变。实测抛出 `ValueError: spatial mismatch: got (256, 256), expected (224, 224)`。讲义说正弦编码"可以换分辨率而无需重训练"，这是**正弦公式本身**的性质；本节代码并没有实现这一能力，需要像 Q10 那样在 forward 中按实际网格重新生成位置表。

### Q7 — 答案：A

注意力分数矩阵是 `L × L`。逐像素：`L = 224 × 224 × 3 = 150,528`（讲义把每个通道值都算作一个 token）；patch：`L = 196`。比值 `(150,528 / 196)² = 768² = 589,824`。B 是序列长度之比，不是注意力代价之比；C、D 分别是两种情况下的绝对数量（讲义原文："196 * 196 = 38,416"、"150,528 * 150,528 = 22.6 billion"）。

### Q8 — 答案：C

```python
pos = sinusoidal_2d(cfg.grid_size, cfg.grid_size, cfg.hidden)
cls_pos = torch.zeros(1, cfg.hidden)
full = torch.cat([cls_pos, pos], dim=0).unsqueeze(0)
self.register_buffer("pos_embed", full, persistent=False)
```

CLS 不对应任何空间位置，给它全 0 的位置编码是合理的选择（它本身就是可学习的，位置信息可以被吸收进 CLS 参数里）。实测 CLS 输出范数 0.534，正是 `trunc_normal(std=0.02)` 在 768 维上的期望量级（`0.02 × sqrt(768) ≈ 0.554`）。

### Q9 — 参考答案

1. **错误**：`permute(0, 2, 3, 4, 5, 1)` 把通道放到了最后，展平顺序是 `(ph, pw, c)`；而 `weight.reshape(out, -1)` 的顺序是 `(c, kh, kw)`。两边都是 768 维，矩阵乘法形状完全合法，但第 k 个输入元素与第 k 个权重元素对应的已经不是同一个"(通道, 行, 列)"——相当于把权重打乱后再做点积，所以数值不对（我们实测与 Conv2d 的最大差 2.59）。这类 bug 不会报错，只能靠等价性测试发现。
2. **修复**：
   - 改输入一侧：`patches.permute(0, 2, 3, 1, 4, 5).reshape(b, gh * gw, c * ph * pw)`（即原代码）；
   - 改权重一侧：保留通道最后的输入，把权重也换成通道最后：`w_flat = weight.permute(0, 2, 3, 1).reshape(weight.shape[0], -1)`。
3. 已运行验证，正确实现得到（每行一个 patch，行优先）：

   ```text
   patch (0,0): [ 0,  1,  4,  5]
   patch (0,1): [ 2,  3,  6,  7]
   patch (1,0): [ 8,  9, 12, 13]
   patch (1,1): [10, 11, 14, 15]
   ```

   注意第 0 个 patch 是 `[0, 1, 4, 5]` 而不是 `[0, 1, 2, 3]`——它是左上角的 2×2 方块，不是第一行的前 4 个像素。

### Q10 — 参考答案

```python
@dataclass(frozen=True)
class FrontEndConfig:
    image_h: int = 224
    image_w: int = 224
    patch_size: int = 16
    in_channels: int = 3
    hidden: int = 768

    def grid(self, h: int | None = None, w: int | None = None) -> tuple[int, int]:
        h = h or self.image_h; w = w or self.image_w
        if h % self.patch_size or w % self.patch_size:
            raise ValueError(f"patch_size {self.patch_size} must divide ({h}, {w})")
        return h // self.patch_size, w // self.patch_size


class VisionFrontEnd(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.proj = nn.Conv2d(cfg.in_channels, cfg.hidden, cfg.patch_size, cfg.patch_size)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, cfg.hidden))
        nn.init.trunc_normal_(self.cls_token, std=0.02)
        self._pos_cache: dict[tuple[int, int], torch.Tensor] = {}

    def _pos(self, gh, gw, device):
        key = (gh, gw)
        if key not in self._pos_cache:
            pos = sinusoidal_2d(gh, gw, self.cfg.hidden)            # (gh*gw, D)
            cls_pos = torch.zeros(1, self.cfg.hidden)                # CLS 仍用 0
            self._pos_cache[key] = torch.cat([cls_pos, pos]).unsqueeze(0)
        return self._pos_cache[key].to(device)

    def forward(self, x):
        gh, gw = self.cfg.grid(x.shape[2], x.shape[3])               # 只检查能否整除
        tokens = self.proj(x).flatten(2).transpose(1, 2)             # (B, gh*gw, D)
        cls = self.cls_token.expand(x.shape[0], -1, -1)
        return torch.cat([cls, tokens], dim=1) + self._pos(gh, gw, x.device)
```

要点：`sinusoidal_2d` 本身已经支持 `grid_h ≠ grid_w`（行、列各自用 `torch.arange(grid_h)` / `arange(grid_w)` 生成），所以只需让配置和前向传播按实际网格调用它；224×320 → 14×20 = 280 个 patch，输出 `(B, 281, D)`。CLS 不属于网格，继续使用全 0 位置。注意这样做在数学上"能运行"，但如果模型只在 14×14 上训练过，新网格的行/列编码范围（例如列号到 19）从未见过，效果仍需验证。

### Q11 — 参考答案

1. 表是按行优先 `reshape(grid_h * grid_w, dim)` 的，第 15 行 → `divmod(15, 14) = (1, 1)`，即第 1 行第 1 列；在 `pos_embed` 中因为前面多了 CLS，是第 16 行。
2. 已运行验证：
   - 第 0 维 = `sin(row · ω_0) = sin(1 × 1) = 0.8415`
   - 第 192 维 = `cos(row · ω_0) = cos(1) = 0.5403`
   - 第 384 维 = `sin(col · ω_0) = sin(1) = 0.8415`
   - 第 576 维 = `cos(col · ω_0) = cos(1) = 0.5403`

   （第 1 维是 `sin(ω_1)`，`ω_1 = 10000^(−1/192) ≈ 0.9532`，值为 0.8153。）
3. 点积随空间距离单调下降：`384 → 378.77 → 318.99 → 253.98`。原因是 `sin(a)sin(b) + cos(a)cos(b) = cos(a − b)`，两个位置的点积等于 `Σ cos((r1 − r2)·ω_i) + Σ cos((c1 − c2)·ω_i)`，**只取决于行差和列差**，与绝对位置无关。这让注意力可以通过点积"感知"相对距离，而且行、列两个方向是分开编码的（(0,1) 与 (1,0) 的点积相同，都是 378.77）。

### Q12 — 参考答案

```python
import torch
import torch.nn.functional as F

def resize_pos_embed(pos: torch.Tensor, old_grid: int, new_grid: int) -> torch.Tensor:
    """pos: (1, 1 + old_grid**2, D) -> (1, 1 + new_grid**2, D)."""
    cls_pos, grid_pos = pos[:, :1], pos[:, 1:]
    d = grid_pos.shape[-1]
    if grid_pos.shape[1] != old_grid * old_grid:
        raise ValueError("pos length does not match old_grid")
    grid_pos = grid_pos.reshape(1, old_grid, old_grid, d).permute(0, 3, 1, 2)   # (1, D, H, W)
    grid_pos = F.interpolate(grid_pos, size=(new_grid, new_grid),
                             mode="bicubic", align_corners=False)
    grid_pos = grid_pos.permute(0, 2, 3, 1).reshape(1, new_grid * new_grid, d)
    return torch.cat([cls_pos, grid_pos], dim=1)

# 例：224/16=14 -> 384/16=24
pos = torch.randn(1, 1 + 14 * 14, 768)
print(resize_pos_embed(pos, 14, 24).shape)   # torch.Size([1, 577, 768])
```

要点：CLS 的位置单独保留不插值；插值前要把序列还原成 2D 网格（`reshape` + `permute` 成 `(N, C, H, W)`，`F.interpolate` 要求通道在第 1 维）；插值后再展平回序列。可学习位置表在固定分辨率上通常拟合得更好，而正弦编码可以直接按新网格重新计算——这正是讲义练习 1 所说的"learned positions win at fixed resolution; sinusoidal wins when you change resolution after training"。

### Q13 — 参考回答要点

- **形状**：
  1. 输入 `(B, 3, 224, 224)`；
  2. `Conv2d(3, 768, 16, stride=16)` → `(B, 768, 14, 14)`；
  3. `flatten(2)` → `(B, 768, 196)`，`transpose(1, 2)` → `(B, 196, 768)`；
  4. 拼接 CLS（`(1, 1, 768)` 沿 batch 扩展）→ `(B, 197, 768)`；
  5. 加位置编码 `(1, 197, 768)`（广播到 batch）→ `(B, 197, 768)`。
- **参数量**：投影 `3·16·16·768 + 768 = 590,592`；CLS 768；正弦位置 0（若为可学习则 `197 × 768 = 151,296`）。
- **本质**：每个 patch 独立地做一次线性变换——这一层没有任何 patch 之间的交互，交互全靠后面的自注意力（第 59 节）。
- 加分点：说出 patch 的"信息损失"——一个 16×16 区域被压成一个向量，细粒度空间信息靠后续层和高分辨率分支弥补（讲义："downstream multimodal stacks often run a second high-resolution branch"）。

### Q14 — 参考回答要点

- **等价性**：kernel = stride = P、无 padding 时，卷积窗口恰好不重叠地覆盖每个 patch；第 k 个输出通道在位置 (i, j) 的值 = `Σ_{c,u,v} W[k,c,u,v] · x[c, iP+u, jP+v] + b[k]`，这正是"把 patch 展平成向量后与 `W[k]` 展平后的向量做点积"。把 k 遍历一遍，就是一次矩阵乘 `flat @ W_flatᵀ + b`。
- **为什么用 Conv2d**：一个算子完成切块 + 投影，少一次显式 reshape/拷贝；cuDNN 等库对卷积高度优化；权重格式与预训练模型（如 timm、HF）一致，便于加载。讲义："faster on GPU and uses one fewer reshape"。
- **重叠卷积**：kernel > stride 时相邻 patch 共享像素，不再等价于"切块 + 线性"，而是真正的卷积 stem；它引入了局部归纳偏置，有工作用小卷积堆叠的 stem 提升训练稳定性。讲义把"更深的卷积 stem"称为 hybrid ViT。
- 加分点：用本节的 `unfold_then_linear` 写等价性测试，是检查权重格式转换（如从 JAX 转到 PyTorch）的常用手段。

### Q15 — 参考回答要点

- **可学习 1D 位置 embedding**（原版 ViT）：简单，固定分辨率下拟合最好；换分辨率时需要把表 reshape 成 2D 网格后插值（Q12），插值后通常还要微调。
- **固定 2D 正弦**（本节）：0 参数、确定；任意网格都能直接计算（Q10）；行列分开编码，点积只依赖相对位移（Q11）。缺点是外推到训练中没见过的坐标范围时效果不一定好。
- **2D RoPE**：把旋转位置编码分别作用于行、列坐标，注意力分数天然只依赖相对位置，在支持动态分辨率的新一代视觉编码器中常见；讲义 59 节也把"2D RoPE"列为位置处理的变体之一。
- **其他**：ALiBi 等偏置型方法；条件位置编码（用卷积生成位置信息）。
- **分辨率变化的处理**：插值（可学习表）、按新网格重新计算（正弦/RoPE）、或者训练时就使用多种分辨率/长宽比（讲义提到"dynamic resolution via interpolated positions"）。
- 常见误区：以为正弦编码"天然支持任意分辨率"就不需要做任何处理——代码层面仍需按新网格生成，而且模型对新坐标范围的泛化需要验证。

### Q16 — 参考回答要点

- **token 数随 P² 反比变化**：224 分辨率下 P=32 → 49、P=16 → 196、P=14 → 256 个 token；注意力代价按平方增长。
- **细节**：P 越小，每个 token 覆盖的区域越小，细粒度信息（小字、细线、小物体）越容易保留；讲义："The cost is a loss of fine-grained spatial detail inside one patch"。
- **任务权衡**：
  - 分类/检索：P=16 或 32 足够；
  - 文档 OCR、图表：需要高分辨率 + 较小 patch，token 数可达上千，常配合切图（tiling）、动态分辨率、token 合并/池化来控制长度；
  - 视频：时间维度再乘一个帧数，通常对时空做联合 patch（tubelet）或对帧做下采样。
- **工程手段**：先用小分辨率全局视图 + 高分辨率局部裁剪；在投影后对相邻 token 做 2×2 合并减少 4 倍长度。
- 加分点：讲义"Use It"一节提到不同家族在 patch 大小（14 vs 16）、动态分辨率上的差异；具体选择应以目标任务的评测为准。

### Q17 — 参考回答要点

- **在前端这一层，是的**：CLS token 是一个与图像无关的参数，前端只给它加了全 0 的位置编码，所以对任何图像，CLS 输出都完全相同。测试 `test_cls_token_broadcasts_without_leakage` 验证的正是"batch 中每个样本的 CLS 都一样"。
- **如何变成摘要**：后续每一层自注意力中，CLS 作为 query 去关注所有 patch token，把信息逐层汇聚进来；最后一层的 CLS 输出才是图像级表示（第 59 节）。它在前端"空白"，正是为了不偏向任何 patch。
- **不用 CLS 的做法**：对所有 patch token 做平均池化（讲义第 59 节称 SigLIP 使用平均池化）；用一个可学习 query 做注意力池化；或者干脆把所有 patch token 都交给下游语言模型（多数 VLM 的做法，第 60 节起）。
- **register tokens**：DINOv2 一类的工作额外加入几个可学习 token，吸收全局信息、让注意力图更干净（讲义 Further Reading 与第 59 节提到）。
- 加分点：指出 CLS 的位置编码为 0 是一种设计选择，也有实现给 CLS 一个单独的可学习位置。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 02 从零实现卷积](../../../04-computer-vision/02-convolutions-from-scratch/docs/zh.md)：理解 kernel、stride 与"卷积 = 滑动点积"。
- [阶段 04 · 14 Vision Transformers (ViT)](../../../04-computer-vision/14-vision-transformers/docs/zh.md)、[阶段 07 · 09 Vision Transformers (ViT)](../../../07-transformers-deep-dive/09-vision-transformers/docs/zh.md)：ViT 的整体结构。
- [阶段 07 · 04 位置编码 — 正弦、RoPE、ALiBi](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：1D 正弦编码的公式，本节把它拓展到 2D。
- [阶段 19 · 32 Token 与位置 Embeddings](../../32-token-positional-embeddings/docs/zh.md)：文本侧的 token + 位置 embedding，对照本节的"像素 tokenizer"。

### 本节被哪些后续内容用到
- [阶段 19 · 59 Vision Transformer Encoder](../../59-vit-transformer/docs/zh.md)：直接加载本节的 `VisionFrontEnd`，在其上堆叠 12 层 Transformer。
- [阶段 19 · 60 用于 Modality Alignment 的投影层](../../60-projection-layer-modality-align/docs/zh.md)：复用本节的 `synthesize_image` 生成图文对。
- [阶段 12 · 01 Vision Transformers 与 Patch-Token 基本单元](../../../12-multimodal-ai/01-vision-transformer-patch-tokens/docs/zh.md)：多模态视角下的 patch token。
- [阶段 12 · 06 任意分辨率视觉：Patch-n'-Pack 与 NaFlex](../../../12-multimodal-ai/06-any-resolution-patch-n-pack/docs/zh.md)：动态分辨率与可变长度 patch 序列。
- [阶段 04 · 18 开放词表视觉——CLIP](../../../04-computer-vision/18-open-vocab-clip/docs/zh.md)：CLIP 的图像塔同样从 patch embedding 开始。

### 延伸关键词
`patch embedding` · `Conv2d stem` · `Tensor.unfold` · `einops rearrange` · `2D sinusoidal position` · `learned position interpolation` · `2D RoPE` · `CLS token` · `register tokens` · `dynamic resolution` · `token merging` · `register_buffer`
