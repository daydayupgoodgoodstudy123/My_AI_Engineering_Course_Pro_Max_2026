# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 06 节 任意分辨率视觉：Patch-n'-Pack 与 NaFlex ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），无需 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这份代码不处理任何像素，只做**token 记账**——这正是任意分辨率问题的核心：

1. **Patch-n'-Pack 的账本**：给定一批 `(H, W)`，算出每张图的 patch 网格、token 数、打包总长、`cu_seqlens`（FlashAttention varlen 所用的累积长度）以及块对角 mask 的非零比例。
2. **块对角 mask 的样子**：在两张小图（14 个 token）上构造稠密 mask 并打印出来。
3. **三种策略的 token 成本对比**：原生分辨率（native）、方形 resize（square）、LLaVA-NeXT 式切块（AnyRes），对一个包含收据、图表、手机截图、照片的工作负载打印预算表。

> 一句话：**用整数运算把"不同分辨率的图像各需要多少 token、拼在一起后注意力如何隔离"算清楚**。同时这份代码的输出本身就是一个反例：不加上限的原生分辨率 token 最多，与代码最后"minimum tokens"的结论相反；此外工作负载的宽高顺序写反了，AnyRes 的网格打分也有缺陷（见 3.4、3.6）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Image` | dataclass | 保存名称与 `h`、`w`；`grid(p)` 返回网格，`seq(p)` 返回 token 数 | 原生 patch 网格 |
| `PackResult` | dataclass | 打包总长、各图长度、mask 非零数、mask 大小、`cu_seqlens` | 打包结果 |
| `pack_batch` | 函数 | 计算各图长度、总长、`Σ n_i²` 与累积偏移 | Patch-n'-Pack |
| `build_dense_mask` | 函数 | 用 `cu_seqlens` 构造 `N × N` 的 0/1 块对角矩阵 | 块对角 mask |
| `anyres_cost` | 函数 | 按长宽比打分选网格，返回块 token + 缩略图 token | AnyRes |
| `square_cost` | 函数 | 方形 resize 后的 token 数（336/14 → 576） | 固定方形基线 |
| `fmt` | 函数 | 把大数格式化为 K / M（**定义了但从未使用**） | — |
| `demo_toy_pack` | 函数 | 6×4 与 4×8 两张图、patch 2，打印 mask | 可视化 |
| `budget_table` | 函数 | 对工作负载打印 native / square / anyres 三列及汇总比值 | Token 预算 |
| `main` | 函数 | 运行玩具示例、裁剪工作负载尺寸到 14 的倍数、打印预算表和策略建议 | — |

数据流：`Image` 列表 → `pack_batch`（长度、`cu_seqlens`、非零数）→ `build_dense_mask`（仅玩具示例）；`Image` 列表 → `budget_table` → 逐图调用 `seq` / `square_cost` / `anyres_cost` → 汇总比值。

---

## 3. 逐段精讲

### 3.1 `Image`：网格与 token 数

```python
@dataclass
class Image:
    name: str
    h: int
    w: int

    def grid(self, p: int) -> tuple[int, int]:
        return (self.h // p, self.w // p)

    def seq(self, p: int) -> int:
        gh, gw = self.grid(p)
        return gh * gw
```

- `@dataclass` 根据类型注解自动生成 `__init__(self, name, h, w)`、`__repr__` 等方法，适合"只存数据"的小类。
- 网格用**整除** `//`：不足一个 patch 的边缘像素被丢弃。真实系统会先 resize 到 patch 大小的整数倍（Qwen2-VL 类模型按 28 对齐）或者 pad 边缘。
- token 数 = `gh × gw`。336×336、patch 14 → 24 × 24 = 576。
- ⚠️ 构造顺序是 `(name, h, w)`——先高后宽。这与图像尺寸常用的"宽×高"写法相反，是 3.6 节方向错误的根源。

### 3.2 `PackResult` 与 `pack_batch`

```python
@dataclass
class PackResult:
    total_tokens: int
    per_image: list[int]
    mask_nonzero: int
    mask_size: int
    cu_seqlens: list[int] = field(default_factory=list)


def pack_batch(images, patch):
    lens = [img.seq(patch) for img in images]
    total = sum(lens)
    nz = sum(n * n for n in lens)
    offsets = [0]
    for n in lens:
        offsets.append(offsets[-1] + n)
    return PackResult(total, lens, nz, total * total, offsets)
```

- `field(default_factory=list)`：dataclass 中可变默认值（列表、字典）必须用 `default_factory`，否则所有实例会共享同一个列表对象；直接写 `= []` 会被 dataclass 拒绝并报错。
- `nz = Σ n_i²`：块对角 mask 的非零元素数——每张图内部是一个 `n_i × n_i` 的全 1 方块。
- `offsets` 就是讲义的 `offsets = [0, n_0, n_0+n_1, ..., N_total]`，也是 FlashAttention varlen 接口要的 `cu_seqlens`：第 b 张图占打包序列的 `[offsets[b], offsets[b+1])`。
- 这里只计算了长度。讲义 NaViT 第 5 步"每个 patch 携带位置信息"没有实现：真实打包还要为每个 token 生成 `(row, col)` 位置 id（每张图从 0 开始）和所属图像 id（测验 Q11 给出了实现，并加入了 token dropping）。

### 3.3 稠密块对角 mask

```python
def build_dense_mask(pack):
    n = pack.total_tokens
    mask = [[0] * n for _ in range(n)]
    for b in range(len(pack.cu_seqlens) - 1):
        lo = pack.cu_seqlens[b]
        hi = pack.cu_seqlens[b + 1]
        for i in range(lo, hi):
            for j in range(lo, hi):
                mask[i][j] = 1
    return mask
```

- 对每张图的区间 `[lo, hi)`，把 mask 中这一方块全部置 1；其余保持 0。这就是讲义的定义："M[i, j] = 1 iff ... offsets[b] <= i < offsets[b+1] and offsets[b] <= j < offsets[b+1]"。
- 视觉 encoder 内部是**双向**注意力，所以方块是满的，不是因果三角。
- ⚠️ 内存是 `O(N²)`。代码只对 14 个 token 的玩具示例调用它；若对工作负载的 43,229 个 token 构造，需要约 18.7 亿个元素（Python 列表仅指针就约 15 GB）。这正是讲义强调 `cu_seqlens` 的原因："FlashAttention's variable-length path skips the mask entirely"。

### 3.4 AnyRes 的成本与网格选择

```python
def anyres_cost(img, tile=336, thumb=336):
    tile_grid = tile // 14
    thumb_grid = thumb // 14
    if img.h <= tile and img.w <= tile:
        grid_r, grid_c = 1, 1
    else:
        best = None
        for gr in range(1, 4):
            for gc in range(1, 4):
                if gr * gc > 6:
                    continue
                tile_h, tile_w = gr * tile, gc * tile
                ratio = img.h / img.w
                tile_ratio = tile_h / tile_w
                score = abs(ratio - tile_ratio) + 0.1 * (gr + gc)
                if best is None or score < best[0]:
                    best = (score, gr, gc)
        _, grid_r, grid_c = best
    tile_tokens = grid_r * grid_c * tile_grid * tile_grid
    thumb_tokens = thumb_grid * thumb_grid
```

- 在 1～3 行 × 1～3 列的网格中，选"网格长宽比与图像长宽比最接近"的一个；`0.1 × (gr + gc)` 是对块数的惩罚，倾向于少切块。
- 总 token = `块数 × 576 + 576`（缩略图）。
- ⚠️ **打分只看长宽比，不看图像大小**：2048×1536 的大照片长宽比 1.33，1×1 得分 0.53 优于 2×2 的 0.73，于是被缩成一块 336×336——与缩略图内容几乎相同，白白多花 576 个 token，也没得到任何额外细节。
- ⚠️ 小图（≤ 336）也加缩略图：336×336 的图返回 1,152 个 token，而第 05 节代码的 base 是 576。
- ⚠️ `if gr * gc > 6` 在 1～3 的范围内只排除了 3×3，而讲义 Token budgets 恰恰提到"AnyRes 3x3 + thumbnail"用于 OCR。
- `_, grid_r, grid_c = best`：元组解包，`_` 丢弃分数。
- patch 大小 14 被写死在 `tile // 14` 中，没有用函数参数。

### 3.5 方形基线与预算表

```python
def square_cost(img, side=336, patch=14):
    g = side // patch
    return g * g
```

- 不管原图多大，resize 到 336×336 后都是 576 个 token——这是"token 最省但细节最差"的基线。

```python
        print(f"{img.name:<26}{nat:>10}{sq:>10}{ar['total']:>14}   {gr}x{gc}")
    ...
    print(f"\nnative vs square : {native_sum / square_sum:>6.2f}x tokens,"
          f" preserves OCR + layout detail")
    print(f"native vs anyres : {native_sum / anyres_sum:>6.2f}x tokens,"
          f" no tile + thumbnail blow-up past ~2 tiles")
```

- 用 f-string 的对齐格式符（`<26` 左对齐、`>10` 右对齐）排出表格。
- ⚠️ 比值表示"native 用的 token 是另外两者的多少倍"：15.01 倍和 5.36 倍。第二行的注释"no tile + thumbnail blow-up"读起来像在说 native 更省，但数字显示 native 多用了 5 倍多。

### 3.6 `main`：工作负载与尺寸裁剪

```python
    workload = [
        Image("receipt 600x1500 (1:2.5)", 600, 1500),
        Image("chart 1280x720 (16:9)", 1280, 720),
        Image("phone screen 1170x2532", 1170, 2532),
        Image("photo 2048x1536 (4:3)", 2048, 1536),
        Image("receipt 504x1260 (1:2.5)", 504, 1260),
    ]
    for img in workload:
        img.h -= img.h % 14
        img.w -= img.w % 14
```

- 名称按"宽×高"书写，构造函数却是 `(h, w)`：⚠️ 收据（竖）和手机截图（竖，讲义"1170x2532 (0.46:1)"）被当成了横图，图表（16:9 横）和照片（4:3 横）被当成了竖图。`native` 列（乘积）不受影响，但 AnyRes 的网格方向全部转置：原输出 receipt 1×2、chart 2×1、phone 1×2；修正后应为 2×1、1×2、2×1（已运行验证）。
- `img.h -= img.h % 14`：把尺寸裁到 14 的整数倍。因为 `grid` 本来就用整除，这一步对 token 数没有影响，只是让数字更"整齐"；dataclass 默认可变，所以可以原地修改字段。
- 最后打印的"WHEN TO USE EACH STRATEGY"把原生打包描述为"maximum fidelity, minimum tokens"——⚠️ "minimum tokens"与上面的表格矛盾。打包节省的是 **padding**，而不是相对于缩小图像的 token 数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只算 token 不处理像素 | 聚焦预算与 mask 结构，零依赖 | 看不到 resize、切块、位置编码的实际效果 |
| `@dataclass` 表示图像与结果 | 字段清晰、自动生成构造函数 | `(h, w)` 顺序与"宽×高"书写习惯冲突，易出错 |
| 稠密 mask 仅用于玩具示例 | 打印可视化 | 真实规模下 `O(N²)` 内存不可行；生产用 `cu_seqlens` / varlen 注意力 |
| 整除丢弃边缘像素 | 计算简单 | 边缘信息丢失；生产会 resize 到 patch 倍数或 pad |
| AnyRes 打分 = 长宽比误差 + 块数惩罚 | 实现短小 | 忽略图像大小；小图也加缩略图；3×3 被排除 |
| 原生分辨率不设上限 | 展示"最高保真"的 token 量 | 一张照片 15,914 token；生产必须用 `max_pixels` 上限 |
| 不生成位置 id、不做 token dropping | 篇幅控制 | NaViT 的第 5 步和 dropping 都缺失（测验 Q11） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `@dataclass class Image: name: str; h: int; w: int` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=...)` | `cu_seqlens: list[int] = field(default_factory=list)` | 可变默认值必须这样写，每个实例得到新列表 |
| dataclass 中定义方法 | `def grid(self, p)`、`def seq(self, p)` | dataclass 仍是普通类，可以有方法 |
| 原地修改字段 | `img.h -= img.h % 14` | 默认 dataclass 可变（`frozen=True` 时不可改） |
| 整除与取余 | `self.h // p`、`img.h % 14` | `//` 向下取整除法，`%` 取余 |
| 返回元组并解包 | `gh, gw = self.grid(p)`、`_, grid_r, grid_c = best` | 多值返回与忽略不需要的值 |
| 生成器求和 | `sum(n * n for n in lens)` | 计算 `Σ n_i²` |
| 累积列表 | `offsets.append(offsets[-1] + n)` | 前缀和的手写版 |
| `range(lo, hi)` | `for i in range(lo, hi)` | 左闭右开区间，与 `cu_seqlens` 的语义一致 |
| `None` 哨兵 | `if best is None or score < best[0]` | 首次迭代时初始化最优值 |
| 返回字典 | `{"grid": (grid_r, grid_c), "total": ...}` | 用键名取值：`ar["total"]` |
| 数字下划线 | `1_000_000` | 提高大数可读性 |
| f-string 对齐 | `{img.name:<26}`、`{nat:>10}`、`{native_sum / square_sum:>6.2f}` | 左/右对齐、宽度、小数位 |
| f-string 中引号 | `{ar['total']:>14}` | 外层双引号时内层用单引号 |
| 条件表达式 + `join` | `"".join("1" if v else "." for v in row)` | 把 0/1 行渲染为字符串 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3，瞬间完成）：

```text
Toy batch: two images, patch 2
  A: 6x4 -> grid 3x2 = 6 tokens
  B: 4x8 -> grid 2x4 = 8 tokens
packed total length: 14
cu_seqlens (FlashAttn varlen): [0, 6, 14]
dense mask size: 196 cells, non-zero: 100 (51.0%)

block-diagonal mask (1=attend, .=mask):
  111111........
  ...（共 6 行）
  ......11111111
  ...（共 8 行）

image                         native    square        anyres      grid
receipt 600x1500 (1:2.5)        4494       576          1728   1x2
chart 1280x720 (16:9)           4641       576          1728   2x1
phone screen 1170x2532         14940       576          1728   1x2
photo 2048x1536 (4:3)          15914       576          1152   1x1
receipt 504x1260 (1:2.5)        3240       576          1728   1x2
TOTAL                          43229      2880          8064

native vs square :  15.01x tokens, preserves OCR + layout detail
native vs anyres :   5.36x tokens, no tile + thumbnail blow-up past ~2 tiles
anyres vs square :   2.80x tokens, the middle ground when encoder is locked at 336
```

逐项解读：

- **玩具示例**：`6² + 8² = 100` 个非零元素，占 `14² = 196` 的 51.0%。图越多、长度越均匀，这个比例越低（四张图 256/576/729/1024 时为 29.6%），稠密 mask 中被屏蔽的"无用计算"占比越高。
- **native 列**：例如收据裁剪后为 588 × 1498，`42 × 107 = 4494`；手机截图 `83 × 180 = 14940`；照片 `146 × 109 = 15914`。一张手机截图或照片就超过 1.4 万个 token，在 8k 或 16k 上下文中根本放不下。
- **square 列**：恒为 576，文字和图表细节被大幅缩小。
- **anyres 列**：大多为 2 块 + 缩略图 = 1728；照片因打分只看长宽比选了 1×1，只有 1152（且块与缩略图内容几乎重复）。grid 列的方向因宽高顺序错误而全部转置（3.6 节）。
- **汇总比值**：native 是 square 的 15 倍、AnyRes 的 5.4 倍。结论应当是：**原生分辨率保真度最高，但必须配合 `max_pixels` 上限**。若以 1024 token 为上限、保持长宽比缩放（测验 Q12），5 张图合计约 4,967 个 token，比不设上限少约 89%。
- "WHEN TO USE"中 native-pack 的"minimum tokens"与上表矛盾：打包的收益是消除 padding、让不同长宽比的图共享一个 batch，而不是"token 最少"。

---

## 7. 动手改一改

1. **修正方向**：把工作负载改为按 `(h, w) = (高, 宽)` 正确传参（或给 `Image` 增加一个 `from_wh(name, w, h)` 类方法），重新打印 grid 列，确认收据和截图得到"多行"网格。
2. **（讲义练习 2）**用 `pack_batch` 处理长度 256/576/729/1024 的四张图（边长 224/336/378/448），验证总长 2585、非零数 `Σ n_i² = 1,977,329`。
3. **（讲义练习 4）**实现 `pack_with_positions`：为每个 token 生成 `(row, col)` 和图像 id，支持按比例随机丢弃 patch，并比较丢弃前后 mask 的非零比例与非零数（参考测验 Q11）。
4. **加 `max_pixels` 上限**：给 `budget_table` 增加一列"native@1024"，按保持长宽比缩放到不超过 1024 token 计算，并再加一个 `min_pixels` 下限（如 64 token）处理小图。
5. **改进 AnyRes 打分**：把"缩放后保留的有效像素"和"填充浪费"纳入打分；小于等于一块的图不加缩略图；放开 3×3 并给总 token 设上限。
6. **（讲义练习 1、3）**分别计算 600×1500 收据和 1792×896 图像在 native / square / AnyRes 下的 token 数，并思考哪种对 OCR 最友好。

---

## 8. 常见坑

- **宽高顺序混淆**：图像库、张量、文件名的"宽×高"与"高×宽"约定各不相同；网格方向一旦反了，切块会严重拉伸文字。
- **打包后位置 id 没有按图重置**：模型会把多张图当成一张大图。
- **mask 与 `cu_seqlens` 不一致**：丢弃 patch 或重排样本后忘记更新，造成图像间信息泄露。
- **在大规模上构造稠密 mask**：`O(N²)` 内存，几万个 token 就要几 GB；应使用 varlen 注意力。
- **以为原生分辨率 = 省 token**：没有上限时恰恰相反；省掉的是 padding。
- **AnyRes 对小图也加缩略图**：内容重复，浪费 token。
- **只按长宽比选网格**：大图被压成一块，失去 AnyRes 的意义。
- **dataclass 可变默认值写成 `= []`**：会直接报错（必须用 `default_factory`）。
