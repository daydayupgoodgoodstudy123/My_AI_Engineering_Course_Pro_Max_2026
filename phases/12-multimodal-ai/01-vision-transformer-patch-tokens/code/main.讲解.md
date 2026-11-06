# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 01 节 Vision Transformers 与 Patch-Token 基本单元 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）；需要 Python 3.10+（用到 `zip(..., strict=True)` 和 f-string 的 `{x=}` 写法）；无 NumPy、无 PyTorch

---

## 1. 这份代码在考察什么

讲义是 Learn 类型，`main.py` 是讲义"Use It"一节所说的"patch tokenizer and geometry calculator"。它不训练、不推理，只做两件事：

1. **把 patch 化讲具体**：用一张 8×8 的玩具灰度图，演示"切块 → 展平 → 线性投影"三步，得到 4 个 4 维 token。
2. **把 ViT 的几何量算出来**：对 5 个典型 encoder（ViT-B/16、CLIP ViT-L/14、DINOv2 ViT-g/14、SigLIP SO400m/14、Qwen2.5-VL ViT）计算网格、序列长度、分项参数量和每次前向的计算量，最后对比低分辨率与高分辨率的 token 数。

对应讲义的学习目标："Compute sequence length, parameter count, and FLOPs for a ViT of a given (patch size, resolution, hidden dim, depth)"。

> 一句话：**加载任何视觉 backbone 之前，先用纸笔（或这 180 行代码）算出它会吐出多少 token、有多少参数、要多少算力**。同时要看清代码的几处口径问题：计算量公式混用了 MAC 与 FLOP、Qwen2.5-VL 被套上了 CLS 和可学习位置表、只支持整除的正方形图像。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ViTConfig` | dataclass | 名称、分辨率、patch、隐藏维、深度、头数、register 数、是否有 CLS | ViT 超参数 |
| `ZOO` | 列表常量 | 5 个典型 encoder 配置 | 2026 年常用视觉塔 |
| `grid_shape` | 函数 | `image_size // patch_size`，不整除就报错 | patch 网格 |
| `seq_length` | 函数 | 网格面积 + CLS + register | 序列长度 |
| `patch_embed_params` | 函数 | `3P²·D + D` | patch embedding |
| `pos_embed_params` | 函数 | `seq_length · D` | 可学习位置表 |
| `cls_register_params` | 函数 | `(CLS + register 数) · D` | 额外可学习 token |
| `block_params` | 函数 | 注意力 + MLP + 两个 LN | Transformer block |
| `total_params` | 函数 | 汇总成 dict | 参数量估算 |
| `flops_per_forward` | 函数 | 注意力 + MLP 的计算量 × 深度 | 算力估算 |
| `fmt` | 函数 | 转成 K/M/B 可读格式 | 输出格式化 |
| `patch_toy_image` | 函数 | 8×8 图 → 4 个 patch → 4 个 4 维 token | patch 化流程 |
| `print_config` | 函数 | 打印一个配置的全部几何量 | 报表 |
| `main` | 函数 | 玩具演示 → 5 个配置 → KEY RATIOS | 入口 |

数据流：`main` → `patch_toy_image`（独立演示）→ 对 `ZOO` 中每个 `ViTConfig` 调 `print_config`（内部调用 `grid_shape` → `seq_length` → 各 `*_params` → `flops_per_forward` → `fmt`）→ 打印 ViT-B/16 与 Qwen2.5-VL 的序列长度之比。

---

## 3. 逐段精讲

### 3.1 配置与模型库

```python
@dataclass
class ViTConfig:
    name: str
    image_size: int
    patch_size: int
    hidden: int
    depth: int
    heads: int
    registers: int = 0
    cls_token: bool = True

ZOO = [
    ViTConfig("ViT-B/16 @ 224", 224, 16, 768, 12, 12),
    ViTConfig("ViT-L/14 @ 336 (CLIP)", 336, 14, 1024, 24, 16),
    ViTConfig("DINOv2 ViT-g/14 @ 224", 224, 14, 1536, 40, 24, registers=4),
    ViTConfig("SigLIP SO400m/14 @ 378", 378, 14, 1152, 27, 16, registers=4,
              cls_token=False),
    ViTConfig("Qwen2.5-VL ViT @ 896x896", 896, 14, 1280, 32, 16),
]
```

- `image_size` 只有一个数，说明代码只处理**正方形**图像。
- `heads` 被存下来但**没有任何函数使用**：参数量和计算量都与头数无关（多头只是把 D 维切开，总维度不变）。
- `registers`、`cls_token` 两个字段带默认值，必须放在无默认值字段之后（dataclass 的规则）。
- 与讲义的出入：
  - SigLIP 用 **378**（= 27 × 14），讲义写的是 384（"default resolution 384 → 729 patch tokens"）。384 不能被 14 整除，`grid_shape(384, 14)` 会报错；27×27 = 729 对应的正是 378。
  - Qwen2.5-VL 用了默认的 `cls_token=True`，而且会被算上可学习位置表，这与讲义"现代 backbone 用 2D-RoPE（点名 Qwen2-VL 的 M-RoPE）、没有位置表"的说法矛盾（见 3.3 与测验 Q12）。
  - SigLIP 配置里的 `registers=4`、"mean pool"等设定沿用了讲义的说法，实际模型的细节建议对照 SigLIP 2 原论文核实。

### 3.2 网格与序列长度

```python
def grid_shape(image_size: int, patch_size: int) -> tuple[int, int]:
    if image_size <= 0 or patch_size <= 0:
        raise ValueError(f"image_size and patch_size must be positive, got {image_size=} {patch_size=}")
    if image_size % patch_size != 0:
        raise ValueError(f"image_size ({image_size}) must be divisible by patch_size ({patch_size})")
    g = image_size // patch_size
    return (g, g)

def seq_length(cfg: ViTConfig) -> int:
    h, w = grid_shape(cfg.image_size, cfg.patch_size)
    extra = (1 if cfg.cls_token else 0) + cfg.registers
    return h * w + extra
```

- 先做参数校验再计算，`{image_size=}` 会打印成 `image_size=384` 这种"名字=值"的形式。
- 严格要求整除。真实模型对不整除的输入有不同策略：卷积步长为 P 时自然**舍弃**边缘；有的预处理先**缩放**到 P（或合并后 token 尺寸）的整数倍；NaFlex/patch-n'-pack 类方法则**补齐**并配合掩码。skill 文件也规定"patch 不整除且没有声明 padding 方案时拒绝分析"。
- 序列长度 = patch 数 + 额外 token。例如 DINOv2 g/14 @ 224：`16×16 + 1 + 4 = 261`。

### 3.3 参数量：patch embed、位置、CLS/register

```python
def patch_embed_params(cfg: ViTConfig) -> int:
    p = cfg.patch_size
    return 3 * p * p * cfg.hidden + cfg.hidden

def pos_embed_params(cfg: ViTConfig) -> int:
    return seq_length(cfg) * cfg.hidden

def cls_register_params(cfg: ViTConfig) -> int:
    n = (1 if cfg.cls_token else 0) + cfg.registers
    return n * cfg.hidden
```

- patch embedding：矩阵 `(3P², D)` 加 bias `D`。ViT-B/16：`3×16×16×768 + 768 = 590,592`，代码输出 `590.6K`，与讲义"591k"一致。
- 位置表：**每个序列位置**一个 D 维向量，ViT-B/16 为 `197 × 768 = 151,296`（讲义"cls + pos = 768 + 197×768 = 152k"）。
- ⚠️ 两处简化：
  - 位置表的行数用的是 `seq_length`，包含了 register。register 本身没有空间位置，通常不加位置编码，这样会多算 `registers × D` 个参数（每个模型几千个，影响可忽略，但概念上不准确）。
  - 所有配置都被假定使用可学习位置表。对使用 RoPE 的模型（如 Qwen2.5-VL），这一项应为 0；代码给它算出了 `4097 × 1280 = 5,244,160` 个参数（输出中的 `position embed : 5.2M`）。

### 3.4 参数量：Transformer block

```python
def block_params(cfg: ViTConfig) -> int:
    d = cfg.hidden
    qkvo = 4 * d * d + 4 * d
    mlp = 2 * d * 4 * d + d + 4 * d
    ln = 2 * 2 * d
    return qkvo + mlp + ln
```

| 部分 | 权重 | bias / LN 参数 |
|------|------|---------------|
| Q、K、V、O 四个投影 | `4D²` | `4D` |
| MLP `D → 4D → D` | `8D²` | `4D + D` |
| 两个 LayerNorm（γ、β） | — | `4D` |
| 合计 | `12D²` | `13D` |

- ViT-B/16：`12 × 768² + 13 × 768 = 7,087,872`，×12 层 = 85,054,464，与讲义"7.1M / 85M"一致（讲义写的是"12 × 768² + 3k"，3k 只算了 LN，漏了约 7k 的 bias，取整后无影响）。
- ⚠️ 假定 MLP 扩展比固定为 4、激活为普通两层 MLP。并非所有模型如此：例如 SigLIP SO400m 是"shape-optimized"结构，公开的 Hugging Face 配置中 MLP 宽度为 4304（不是 4 × 1152 = 4608）；按 4304 计算，27 个 block 约 411.5M，整体约 413M，比代码的 431.9M 更接近"400M"的名字。DINOv2 g/14 等也有自己的 FFN 设计。做精确估算时要读具体模型的 config。

```python
def total_params(cfg: ViTConfig) -> dict:
    ...
    fl = 2 * cfg.hidden
    total = pe + po + cr + bl + fl
    return {"patch_embed": pe, "position": po, "cls+reg": cr,
            "blocks": bl, "final_ln": fl, "total": total}
```

- `fl = 2D` 是最终 LayerNorm 的 γ 和 β（pre-norm 结构需要）。
- **不含分类头**：ViT-B/16 合计 85,798,656 ≈ 85.8M，讲义取整写成"≈ 86M"。加上 ImageNet-1k 线性头（`768 × 1000 + 1000 = 769,000`）约为 86.6M。

### 3.5 计算量

```python
def flops_per_forward(cfg: ViTConfig) -> int:
    n = seq_length(cfg)
    d = cfg.hidden
    attn = 4 * n * d * d + 2 * n * n * d
    mlp = 2 * n * d * 4 * d * 2
    return cfg.depth * (attn + mlp)
```

- 注意力：`4nd²` 是 Q/K/V/O 投影的乘加次数（MAC），`2n²d` 是 `QKᵀ` 与 `softmax·V` 的 MAC。
- MLP：两层各 `n × d × 4d` 次 MAC，共 `8nd²`；代码再乘 2 得 `16nd²`，变成了 FLOP。
- ⚠️ **口径混用**：注意力按 MAC、MLP 按 FLOP，加起来既不是 MACs 也不是 FLOPs。统一后的公式：
  - MACs：`L × (12nd² + 2n²d)`
  - FLOPs：`L × (24nd² + 4n²d)`

| 配置 | 代码输出 | MACs（统一） | FLOPs（统一） |
|------|---------|-------------|--------------|
| ViT-B/16 @ 224 | 28.60B | 17.45G | 34.89G |
| ViT-L/14 @ 336 | 306.78B | 190.61G | 381.22G |
| DINOv2 ViT-g/14 @ 224 | 500.99B | 303.94G | 607.89G |
| SigLIP SO400m/14 @ 378 | 558.72B | 348.60G | 697.20G |
| Qwen2.5-VL ViT @ 896 | 5671.08B | 3952.67G | 7905.34G |

（后两列已用 Python 按同样的 n、d、L 计算；均忽略 patch embedding、LN、softmax 等小项。）文献中常说的"ViT-B/16 约 17.6 GFLOPs"其实是 MAC 口径，比较不同来源的数字时先确认口径。

- `N²` 项的占比为 `n / (6d + n)`：ViT-B/16 @ 224 约 4%，Qwen2.5-VL @ 896 约 35%。分辨率越高，平方项越重要。

### 3.6 `fmt`：可读格式

```python
def fmt(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1e9:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1e6:.1f}M"
    ...
```

- `1_000_000_000` 中的下划线只是数字分隔符，提高可读性。
- 参数量和 FLOPs 都用同一个函数格式化，所以 FLOPs 也显示成 "B"（十亿），例如 `5671.08B` 即约 5.67 万亿。

### 3.7 玩具 patch 化：`patch_toy_image`

```python
    img = [[(r * 8 + c) % 256 for c in range(8)] for r in range(8)]

    P = 4
    patches = []
    for pr in range(0, 8, P):
        for pc in range(0, 8, P):
            patch = []
            for dr in range(P):
                for dc in range(P):
                    patch.append(img[pr + dr][pc + dc])
            patches.append(patch)
```

- 8×8 灰度图，像素值 `r*8 + c`（0 到 63，`% 256` 在这里不起作用，只是提示"像素在 0–255 之间"）。
- 外两层循环以步长 P 遍历 patch 的左上角 `(pr, pc)`，顺序是 patch 0 左上、1 右上、2 左下、3 右下（**行优先**）。内两层循环把 patch 内的 16 个像素按行优先展平。这就是"carve into a grid of non-overlapping patches, flatten each cube"。

```python
    fake_W = [[((i + j) % 5) - 2 for j in range(P * P)] for i in range(4)]
    embeddings = []
    for patch in patches:
        emb = []
        for row in fake_W:
            s = sum(r * v for r, v in zip(row, patch, strict=True))
            emb.append(s)
        embeddings.append(emb)
```

- `fake_W` 是 `4 × 16` 的整数矩阵（取值 −2..2），每一行是一个输出维度的权重，等价于 `W_E` 的转置；每个 token 的第 i 维 = 第 i 行与 patch 向量的点积。
- `zip(..., strict=True)`（Python 3.10+）：两个序列长度不同时报错，防止静默截断。
- 有趣的现象：4 个 token 的第 3 维都是 −35。因为该行权重之和为 0，而 4 个 patch 之间只差常数偏移（+4、+32、+36）；线性映射对常数偏移的响应 = 偏移 × 权重和（测验 Q10）。
- 与真实 ViT 的差异：单通道、无 bias、无位置编码、权重非学习得到、像素未归一化。

### 3.8 报表与 KEY RATIOS

```python
    print(f"  seq length       : {seq} (incl {'CLS' if cfg.cls_token else 'no CLS'},"
          f" {cfg.registers} registers)")
    ...
    print(f"  ratio: {seq_length(qwen) / seq_length(vit_b):.1f}x more tokens")
```

- f-string 里可以嵌入条件表达式；相邻两个 f-string 自动拼接。没有 CLS 时会打印出略别扭的"incl no CLS"。
- `print_config` 计算了 `cls+reg` 和 `final_ln` 但没有打印，所以打印出的三项（patch embed、position、blocks）加起来比 total 略小。
- KEY RATIOS：`4097 / 197 ≈ 20.8` 倍 token，引出"高分辨率 VLM 需要 token merging 或 pooling"。由于平方项的存在，注意力分数矩阵的差距约为 `20.8² ≈ 432` 倍。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库、只算几何量 | 无依赖、秒级运行，专注概念 | 不验证真实权重；生产中可用 `sum(p.numel() for p in model.parameters())` 核对 |
| 只支持整除的正方形 | 公式简单 | 无法直接做讲义练习 1、2（1280×720、1920×1080）；需扩展为 H×W 并选择舍弃/补齐策略 |
| 统一按"原始 ViT 模板"估算 | 一套公式覆盖所有模型 | 忽略 RoPE（无位置表）、无 CLS、非 4 倍 MLP 等差异，Qwen2.5-VL、SigLIP SO400m 的数字偏大 |
| 位置表含 register | 实现简单 | 概念上不准确（影响极小） |
| 计算量公式混合 MAC/FLOP | 疑为笔误 | 与任何文献口径都对不上；应统一为 `24nd² + 4n²d`（FLOPs） |
| 玩具投影用整数模式权重 | 输出可手算、可复现 | 与学习到的浮点权重不同；但正好展示了线性映射的性质 |
| 不含分类头 | 视觉塔在 VLM 中不需要分类头 | 与"ViT-B/16 = 86.6M"之类含头的数字相比会差约 0.77M |
| `heads` 字段未使用 | 为将来估算注意力显存预留 | 当前可删除或用于估算每头维度 `D/heads` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可写 `tuple[int, int]` |
| `@dataclass` + 默认值 | `registers: int = 0`、`cls_token: bool = True` | 自动生成构造函数；有默认值的字段必须排在后面 |
| 位置参数与关键字参数混用 | `ViTConfig("...", 378, 14, 1152, 27, 16, registers=4, cls_token=False)` | 前面按顺序，后面按名字 |
| 返回元组并解包 | `return (g, g)`、`h, w = grid_shape(...)` | 一次返回/接收多个值 |
| `raise ValueError(...)` | `grid_shape` 中的参数校验 | 输入非法时立即报错 |
| f-string 的 `=` 调试写法 | `f"{image_size=} {patch_size=}"` | 输出 `image_size=384 patch_size=14`（3.8+） |
| 条件表达式 | `(1 if cfg.cls_token else 0)` | 布尔转 0/1；也可直接写 `int(cfg.cls_token)` |
| 整除与取余 | `image_size // patch_size`、`image_size % patch_size` | `//` 向下取整除，`%` 取余数 |
| 数字下划线 | `1_000_000_000` | 只为可读，值不变 |
| f-string 格式符 | `{n / 1e9:.2f}`、`{v:3d}`、`{ratio:.1f}` | 保留小数位、整数宽度 |
| 返回 dict | `total_params` 返回 `{"patch_embed": ..., "total": ...}` | 用键取分项 |
| 嵌套列表推导式 | `[[(r * 8 + c) % 256 for c in range(8)] for r in range(8)]` | 外层生成行、内层生成列，得到二维列表 |
| `range(start, stop, step)` | `range(0, 8, P)` | 以步长 P 遍历，正好是每个 patch 的起点 |
| 四重循环 | `pr, pc, dr, dc` | patch 起点 + patch 内偏移 |
| `zip(..., strict=True)` | 投影的点积 | 长度不一致时报错（3.10+） |
| 生成器表达式 + `sum` | `sum(r * v for r, v in zip(...))` | 点积的纯 Python 写法 |
| `enumerate` | `for i, p in enumerate(patches)` | 同时取下标和元素 |
| 字符串乘法 | `"-" * 60`、`"=" * 60` | 打印分隔线 |
| 负索引 | `qwen = ZOO[-1]` | 取最后一个元素 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行 `main()`，便于在测验中直接调用各函数 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，瞬时完成），节选：

```text
Toy image patch tokenization (8x8 grayscale, patch_size=4)
...
patches (4 total, each length 16):
  patch 0: [0, 1, 2, 3, 8, 9, 10, 11, 16, 17, 18, 19, 24, 25, 26, 27]
  patch 1: [4, 5, 6, 7, 12, 13, 14, 15, 20, 21, 22, 23, 28, 29, 30, 31]
  patch 2: [32, 33, 34, 35, 40, 41, 42, 43, 48, 49, 50, 51, 56, 57, 58, 59]
  patch 3: [36, 37, 38, 39, 44, 45, 46, 47, 52, 53, 54, 55, 60, 61, 62, 63]

linear projection (P*P=16 -> hidden=4):
  token 0: [8, -31, -35, -4]
  token 1: [0, -35, -35, 0]
  token 2: [-56, -63, -35, 28]
  token 3: [-64, -67, -35, 32]
→ 4 tokens of dim 4 ready for the transformer.

ViT-B/16 @ 224
  grid             : 14x14
  seq length       : 197 (incl CLS, 0 registers)
  patch embed      : 590.6K
  position embed   : 151.3K
  blocks total     : 85.1M
  ** total params **: 85.8M
  flops / forward  : 28.60B
...
SigLIP SO400m/14 @ 378
  grid             : 27x27
  seq length       : 733 (incl no CLS, 4 registers)
  ** total params **: 431.9M
  flops / forward  : 558.72B

Qwen2.5-VL ViT @ 896x896
  grid             : 64x64
  seq length       : 4097 (incl CLS, 0 registers)
  position embed   : 5.2M
  ** total params **: 635.7M
  flops / forward  : 5671.08B

KEY RATIOS
  ViT-B/16 @ 224    seq length: 197
  Qwen2.5-VL @ 896  seq length: 4097
  ratio: 20.8x more tokens
```

全部 5 个配置汇总：

| 配置 | 网格 | 序列长 | 参数量 | 代码"flops" |
|------|------|-------|-------|------------|
| ViT-B/16 @ 224 | 14×14 | 197 | 85.8M | 28.60B |
| ViT-L/14 @ 336 (CLIP) | 24×24 | 577 | 303.5M | 306.78B |
| DINOv2 ViT-g/14 @ 224 | 16×16 | 261 | 1.13B | 500.99B |
| SigLIP SO400m/14 @ 378 | 27×27 | 733 | 431.9M | 558.72B |
| Qwen2.5-VL ViT @ 896 | 64×64 | 4097 | 635.7M | 5671.08B |

逐项解读：

- **patch 0** 是左上角 4×4 块：第 0–3 行的第 0–3 列，像素 `0,1,2,3 / 8,9,10,11 / ...`，按行展平。patch 1 是右上角，所以每个值都比 patch 0 大 4；patch 2、3 在下半部分，分别大 32、36。
- **token 的第 3 维全是 −35**：该维权重之和为 0，对常数偏移不敏感（3.7 节）。
- **ViT-B/16 的 85.8M** 与讲义"≈86M"一致（不含分类头）。CLIP ViT-L/14 约 303.5M，与"ViT-L 约 3 亿参数"的常识相符；DINOv2 g/14 约 1.13B，讲义称"1B params"。
- **SigLIP SO400m 的 431.9M**：比名字中的 400M 多出约 30M，主要因为代码把 MLP 宽度固定为 4D（3.4 节）。序列长 733 = 729 个 patch + 4 个 register（沿用讲义设定）。
- **Qwen2.5-VL 的 4097 和 5.2M 位置参数**：都来自套用原始 ViT 模板（CLS + 可学习位置表），与讲义"M-RoPE、无位置表"的描述不符；去掉后为 4096 个 token、约 630.4M 参数。
- **"flops / forward"一列**：口径混用，换成统一的 FLOPs 需要乘以约 1.2–1.4（见 3.5 节表格）。
- **20.8 倍 token**：896 分辨率的 token 数约为 224 的 20.8 倍，注意力矩阵约 432 倍。

---

## 7. 动手改一改

1. **修正计算量公式**：改为 `24nd² + 4n²d`（FLOPs），并新增一个 MACs 版本，打印两列；确认 ViT-B/16 @ 224 为 34.89 GFLOPs / 17.45 GMACs。
2. **支持非正方形与不整除**：把 `image_size` 拆成 `height`、`width`，`grid_shape` 支持 `floor` / `pad` 两种策略，完成讲义练习 1、2（1280×720 @ P14 用 `floor` 得 4,641 个 patch；1080p 每帧 10,549 个，5 分钟 30 FPS 约 9,494 万个）。
3. **区分位置编码类型**：给 `ViTConfig` 加 `pos: str = "learned"`，取值 `"rope"` 时位置参数为 0；把 Qwen2.5-VL 改成 `cls_token=False, pos="rope"`，并加 `merge: int = 1` 字段，输出"送入 LLM 的 token 数"（2×2 合并时为 1,024）。
4. **可配置 MLP 宽度**：加 `mlp_dim: int | None = None`（默认 4D），把 SigLIP SO400m 设为 4304，观察总参数量变化。
5. **讲义练习 3**：用纯 Python 实现对 patch token 的 mean pool（输入 `list[list[float]]`，输出一个向量），并在玩具示例的 4 个 token 上计算。
6. **进阶（讲义练习 5）**：实现 patch-n'-pack——给定多张不同分辨率的图片，输出拼接后的序列长度和块对角注意力掩码（`mask[i][j] = 1` 当且仅当 i、j 属于同一张图）。

---

## 8. 常见坑

- **只按边长估算 token**：token 数随分辨率的**平方**增长，注意力随 token 数再平方增长。
- **MAC 与 FLOP 混淆**：同一个模型可能被报成相差 2 倍的两个数字；本节代码甚至在一个公式里混用了两种口径。
- **把所有 ViT 都当成原始 ViT**：现代模型可能没有 CLS、没有位置表（用 RoPE）、MLP 宽度不是 4 倍、带 register，直接套模板会算错参数和序列长度。
- **分辨率不能被 patch 整除**：不同框架会舍弃、缩放或补齐，结果的网格不同；讲义的"384 → 729"就是一个例子（378 才整除）。
- **忘记 register 不是内容**：交给 LLM 或做稠密预测时要先去掉 register token。
- **把 CLS 当作唯一的图像表示**：现代 VLM 交出全部 patch token；mean pool 也常用。
- **展平顺序不一致**：从线性层权重迁移到 `Conv2d`（或反过来）时，patch 内像素与通道的排列顺序必须对齐。
- **中文讲义翻译质量**：中文版是机器翻译，例如把"multimodal"译成"多式联运"、"register tokens"译成"注册/登记 tokens"、"Phase 4 (Computer Vision)"译成"计算机远景"，阅读时以英文版为准。
