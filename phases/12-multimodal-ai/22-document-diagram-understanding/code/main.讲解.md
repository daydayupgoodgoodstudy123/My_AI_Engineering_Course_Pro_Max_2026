# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 22 节 文档与图解理解 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`json`、`dataclasses`），无需网络、GPU 或模型权重

---

## 1. 这份代码在考察什么

这是一个只有 127 行的"示意型"脚本，不加载任何模型，用写死的数据把讲义的三个关键概念具体化：

1. **LayoutLMv3 的三路输入**：一页文档在 OCR 之后被表示成"文本 id 流 + 逐 token bbox 流 + 图像 patch 流"。
2. **Donut 风格的输出 schema**：OCR-free 模型直接输出 JSON，因此任务首先要定义 schema（发票、表单）。
3. **各技术栈的 token 预算**：同一页 A4 在不同技术栈下要消耗多少输入 token，这直接决定成本和延迟。
4. **三个时代与选型配方**：用两张打印表格复述讲义的分类和 2026 recipe。

> 一句话：**把"文档 AI 选型 = 版面信息怎么进模型 + 输出长什么样 + 每页花多少 token"这三个问题落到几行数据上**。代码本身很简单，价值在于看清它哪些地方是简化、哪些数字经不起推敲。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Token` | dataclass | 一个 OCR 结果：文字 + `(x0, y0, x1, y1)` bbox | OCR 输出（逐词 bbox） |
| `mock_page()` | 函数 | 返回 8 个写死的发票 token | 合成的 OCR 页面 |
| `layoutlm_input()` | 函数 | 生成 `text_ids`、`bbox_stream`、`patch_ids` 三路输入 | LayoutLMv3 三路流 |
| `donut_schema()` | 函数 | 返回 invoice / form 的 JSON 模板 | Donut 结构化输出 |
| `token_budget()` | 函数 | 打印 6 种技术栈每页 token 数 | 成本 / 分辨率取舍 |
| `demo_pipeline_output()` | 函数 | 打印三路输入的片段和 invoice schema | 演示 |
| `eras_table()` | 函数 | 打印三个时代与代表模型 | 三时代划分 |
| `main()` | 函数 | 依次调用以上演示，最后打印选型配方 | 2026 recipe |

数据流：`main` → `demo_pipeline_output`（`mock_page` → `layoutlm_input`；`donut_schema` → `json.dumps`）→ `token_budget` → `eras_table` → 打印 recipe。各部分之间没有数据依赖，都是独立的打印演示。

---

## 3. 逐段精讲

### 3.1 `Token` 与 `mock_page`：OCR 的产物长什么样

```python
@dataclass
class Token:
    text: str
    bbox: tuple[int, int, int, int]


def mock_page() -> list[Token]:
    """A synthetic invoice page."""
    return [
        Token("INVOICE",      (100, 50,  300, 80)),
        Token("ACME Co.",     (100, 100, 250, 130)),
        ...
        Token("Total",        (400, 400, 500, 430)),
        Token("$1,245.00",    (400, 440, 550, 470)),
    ]
```

- 这就是 Era 1 里 "Tesseract extracts text with per-word bounding boxes" 的输出格式：每个文字片段带一个轴对齐矩形 `(左, 上, 右, 下)`，单位是像素。
- 讲义问题部分的例子"Total: $1,245 来自右下角而不是脚注"在这里具体化了：`"Total"` 和 `"$1,245.00"` 的 x 都从 400 开始、y 在 400 以上，位置本身就是语义。
- ⚠️ 简化：真实 OCR 是"逐词"的，这里 `"ACME Co."`、`"Widget A"` 是多词片段；页面上也没有数量字段，`$120.00` 与总额 `$1,245.00` 对不上——作为演示无妨，但用它去填下面的 invoice schema 是填不满的。

### 3.2 `layoutlm_input`：三路输入

```python
def layoutlm_input(tokens: list[Token], patch_grid: tuple[int, int] = (16, 16)) -> dict:
    """Produce the three-stream input: text, bbox, patch-ids."""
    text_ids = [hash(t.text) % 10000 for t in tokens]
    bbox_stream = [t.bbox for t in tokens]
    n_patches = patch_grid[0] * patch_grid[1]
    patch_ids = list(range(n_patches))
    return {"text_ids": text_ids, "bbox_stream": bbox_stream,
            "patch_ids": patch_ids}
```

三行分别对应讲义的三路流：

| 流 | 代码 | 本例结果 | 真实 LayoutLMv3 |
|----|------|---------|----------------|
| 文本 | `hash(t.text) % 10000` | 8 个 0–9999 的整数，**每次运行不同** | BPE tokenizer 切子词，id 来自固定词表 |
| 版面 | `t.bbox` 原样 | 像素坐标，如 `(100, 50, 300, 80)` | 按页面宽高归一化到 0–1000，查 2D 位置 embedding；子词共享所属词的 bbox |
| 图像 | `range(16*16)` | 256 个 id，与图像内容无关 | 页面缩放到 224×224，16×16 patch → 14×14 = 196 个 patch |

- ⚠️ **`hash()` 不确定**：Python 对字符串的 `hash` 每个进程加随机盐。实测两次运行得到 `[6203, 8820, 2219, 3872]` 和 `[7517, 1811, 1083, 5266]`，设置 `PYTHONHASHSEED=0` 才固定。真实模型里 id 必须稳定地指向 embedding 表中的同一行。
- ⚠️ **碰撞**：只有 1 万个桶，约 118 个不同的词就有 50% 概率出现碰撞（生日问题，已计算）。
- ⚠️ **参数名误导**：`patch_grid=(16, 16)` 实际被当作"网格行列数"，而 LayoutLMv3 里的 16 是 patch 的**像素尺寸**。
- 代码没有体现的部分：三路流如何拼成一个序列（文本 token 和图像 patch 拼接后进同一个 Transformer）、统一 masking 预训练目标。讲义说它是"OCR 路线的巅峰"，靠的正是这一点，而代码只展示了数据形状。
- 改进版实现见测验 Q9。

### 3.3 `donut_schema`：OCR-free 的输出契约

```python
def donut_schema(task: str = "invoice") -> dict:
    schemas = {
        "invoice": {
            "vendor": "<string>",
            "invoice_number": "<string>",
            "line_items": [
                {"description": "<string>", "quantity": "<int>", "price": "<float>"}
            ],
            "total": "<float>",
            "currency": "<string>",
        },
        "form": { ... },
    }
    return schemas.get(task, {})
```

- Donut 的卖点是"图像进、JSON 出"，所以下游系统和模型之间的契约就是这个 schema：字段名、嵌套结构（`line_items` 是对象数组）、每个字段的类型占位符。
- 列表里只放一个元素作为"每一项的模板"，这是描述数组 schema 的常见写法（JSON Schema 里对应 `items`）。
- ⚠️ `schemas.get(task, {})`：未知任务静默返回空字典。若下游用它做校验，空 schema 会让任何输出都"合格"（测验 Q11 实测 `validate(pred, donut_schema("receipt")) == []`）。生产代码应对未知任务直接报错。
- 真实 Donut 并不输出 JSON 字符串本身，而是输出一串带特殊标签的 token 序列（类似 XML 的开闭标签），再转换成 JSON；这里只展示目标结构。

### 3.4 `token_budget`：每页要花多少 token

```python
    rows = [
        ("OCR pipeline + LayoutLMv3", 512, "text + bbox + small image"),
        ("Donut (OCR-free)",          4096, "swin encoder, ~4k patches"),
        ("Nougat (paper pages)",      4096, "896x896, 4-tile AnyRes"),
        ("VLM AnyRes 4-tile (LLaVA)", 2916, "336 tiles + thumbnail"),
        ("VLM native 2048 (Qwen2.5-VL)", 8192, "native resolution"),
        ("VLM native 2576 (Claude 4.7)", 12000, "frontier, best accuracy"),
    ]
    print(f"  {'stack':<28}{'tokens':<10}  note")
    for name, toks, note in rows:
        print(f"  {name:<28}{toks:<10}  {note}")
```

- 这张表的意图是建立"分辨率越高、token 越多、成本越高"的直觉：OCR 路线 512 是 LayoutLM 类模型常见的最大序列长度，前沿 VLM 一页上万 token。
- 所有数字都是**手写常量**，不是算出来的，其中有几处经不起推敲：
  - **LLaVA 行**：按阶段 12 · 06 讲义，2×2 个 336 tile + 缩略图 = `4 × 576 + 576 = 2880`；`2916 = 4 × 729` 是 384 分辨率 SigLIP tile（阶段 12 · 08 的 OneVision）且不含缩略图，与注释不符。
  - **Nougat 行**："4-tile AnyRes" 是 LLaVA 系的切 tile 概念；讲义说 Nougat 是与 Donut 同类的 OCR-free 编码器-解码器，并不使用 AnyRes 切 tile（Nougat 论文报告的输入分辨率是 896×672，而不是 896×896）。
  - **Qwen2.5-VL 行**：按阶段 12 · 09 讲义"每 28×28 像素一个 token"，长边 2048 的 A4 约 `52 × 73 = 3,796` 个 token，2048×2048 正方形约 5,350 个，都不是 8192（测验 Q10）。
- ⚠️ **格式 bug**：`:<28` 是"最少 28 宽"，`"VLM native 2048 (Qwen2.5-VL)"` 正好 28 个字符，输出里名字和数字粘在一起（见第 6 节）。

### 3.5 `demo_pipeline_output` 与 `eras_table`

```python
    print(f"  text_ids[0:4]    : {data['text_ids'][:4]}...")
    print(f"  bbox_stream[0:2] : {data['bbox_stream'][:2]}")
    print(f"  patch_ids count  : {len(data['patch_ids'])}")
    ...
    print(json.dumps(schema, indent=2))
```

- 切片 `[:4]`、`[:2]` 只打印前几项；`json.dumps(..., indent=2)` 把嵌套字典漂亮地打印出来。
- f-string 里用了单引号 `data['text_ids']`，因为外层是双引号（Python 3.12 之前 f-string 内外不能用同一种引号）。

```python
    rows = [
        ("Era 1 OCR pipeline",    "Tesseract, TrOCR, LayoutLMv3", "deterministic"),
        ("Era 2 OCR-free",        "Donut, Nougat, DocLLM",         "generalist less"),
        ("Era 3 VLM-native",      "Qwen2.5-VL, PaliGemma 2, Claude 4.7", "frontier 2026"),
    ]
```

- ⚠️ DocLLM 被放进 "Era 2 OCR-free"，但讲义 DocLLM 小节明确说它 "still depends on OCR input"。这个错误源自讲义开头把 DocLLM 与 Donut、Nougat 并列为 OCR-free 模型——讲义自身前后矛盾。更准确的归类是与 LayoutLMv3 同属"OCR + 版面感知"路线（生成式 vs 判别式）。
- "generalist less" 想表达的是"专才、通用性差"（讲义："specialists, not generalists"）。

### 3.6 `main` 与选型配方

```python
    print("  10M invoices/day     : OCR pipeline + LayoutLMv3, cheap")
    print("  scientific papers    : Nougat for math, VLM for figures")
    print("  mixed + handwriting  : VLM-native (PaliGemma 2 or Qwen2.5-VL)")
    print("  regulated            : OCR + VLM cross-check, auditable")
```

- 四行与讲义 "2026 recipe" 一一对应，也与 `outputs/skill-document-ai-stack-picker.md` 的规则一致（例如 >1,000 万页/天拒绝 Era 3）。
- 这里只是打印字符串，没有实现任何选择逻辑；"动手改一改"第 5 题把它改成真正的函数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用标准库、不加载模型 | 秒级运行、零依赖，专注概念 | 看不到真实模型行为；生产用 `transformers` 加载 LayoutLMv3 / Donut / Nougat 或调用 VLM API |
| `hash() % 10000` 当 token id | 一行代码表示"文本变成整数" | 不确定、会碰撞；应使用模型自带 tokenizer |
| bbox 用原始像素 | 直观 | 与分辨率耦合；应归一化到 0–1000 |
| patch 数写死 256 | 只为展示"有一路图像流" | 与图像无关；应由 `img_size // patch` 计算（LayoutLMv3 为 196） |
| schema 用字典 + 类型占位符 | 一眼看懂结构 | 不是标准 JSON Schema，无法直接用于约束解码；未知任务静默返回空 |
| token 预算手写常量 | 快速给出量级直觉 | 部分数字与注释/其它小节矛盾；应按模型的分辨率规则计算或读 API usage |
| 配方用 print | 便于阅读 | 没有可测试的决策逻辑 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，旧版本 Python 也能写 `list[Token]`、`tuple[int, ...]` |
| `@dataclass` | `class Token: text: str; bbox: tuple[...]` | 自动生成 `__init__`、`__repr__`、`__eq__`，适合"纯数据"类 |
| 类型注解 | `def layoutlm_input(tokens: list[Token], ...) -> dict` | 标注参数和返回类型；运行时不检查，供阅读和类型检查器使用 |
| 默认参数为元组 | `patch_grid: tuple[int, int] = (16, 16)` | 元组不可变，作为默认值是安全的（不要用可变的 list/dict 作默认值） |
| 列表推导式 | `[hash(t.text) % 10000 for t in tokens]` | 一行内对每个元素做变换生成新列表 |
| 内置 `hash()` | `hash(t.text)` | 字符串哈希每个进程随机，不能用于持久化 id；需要稳定值时用 `hashlib` |
| `range` 转列表 | `list(range(n_patches))` | 得到 `[0, 1, ..., n-1]` |
| 嵌套字典/列表字面量 | `donut_schema` 中的 `schemas` | Python 原生数据结构可以直接映射成 JSON |
| `dict.get(key, default)` | `schemas.get(task, {})` | 键不存在时返回默认值而不是抛 `KeyError` |
| `json.dumps(obj, indent=2)` | `print(json.dumps(schema, indent=2))` | 把字典序列化为带缩进的 JSON 字符串 |
| 元组解包的 for 循环 | `for name, toks, note in rows:` | 每行元组拆成三个变量 |
| f-string 对齐 | `{name:<28}`、`{toks:<10}`、`{era:<20}` | `<` 左对齐并补空格到**至少** N 宽；内容超长不会截断 |
| 字符串乘法 | `"-" * 60` | 重复字符串，画分隔线 |
| 切片 | `data['text_ids'][:4]` | 取前 4 个元素 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`；被 `import` 时不执行（测验里就是 `import main` 复用函数） |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，瞬时完成）：

```text
LAYOUTLMv3-STYLE INPUT (invoice page)
------------------------------------------------------------
  text_ids[0:4]    : [5235, 6523, 1481, 1060]...       ← 每次运行都不同（hash 随机化）
  bbox_stream[0:2] : [(100, 50, 300, 80), (100, 100, 250, 130)]   ← 原始像素，未归一化
  patch_ids count  : 256                                ← 16×16；LayoutLMv3 实际是 14×14 = 196

DONUT SCHEMA (invoice)
------------------------------------------------------------
{
  "vendor": "<string>",
  "invoice_number": "<string>",
  "line_items": [
    {
      "description": "<string>",
      "quantity": "<int>",
      "price": "<float>"
    }
  ],
  "total": "<float>",
  "currency": "<string>"
}

INPUT TOKEN BUDGET PER PAGE (A4 at 300 DPI, ~2500x3500 px)
------------------------------------------------------------
  stack                       tokens      note
  OCR pipeline + LayoutLMv3   512         text + bbox + small image
  Donut (OCR-free)            4096        swin encoder, ~4k patches
  Nougat (paper pages)        4096        896x896, 4-tile AnyRes
  VLM AnyRes 4-tile (LLaVA)   2916        336 tiles + thumbnail      ← 应为 2880（5 × 576）
  VLM native 2048 (Qwen2.5-VL)8192        native resolution          ← 名字与数字粘连
  VLM native 2576 (Claude 4.7)12000       frontier, best accuracy

THREE ERAS OF DOCUMENT AI
------------------------------------------------------------
  Era 1 OCR pipeline  Tesseract, TrOCR, LayoutLMv3        deterministic
  Era 2 OCR-free      Donut, Nougat, DocLLM               generalist less   ← DocLLM 依赖 OCR
  Era 3 VLM-native    Qwen2.5-VL, PaliGemma 2, Claude 4.7 frontier 2026

RECIPE PICKER
------------------------------------------------------------
  10M invoices/day     : OCR pipeline + LayoutLMv3, cheap
  ...
```

逐项解读：

- **text_ids**：本次是 `[5235, 6523, 1481, 1060]`，另外两次运行分别得到 `[6203, 8820, 2219, 3872]` 与 `[7517, 1811, 1083, 5266]`。这不是 bug 的"症状不明显"，而是非常直接地说明内置 `hash` 不能做 token id。
- **bbox_stream**：前两个 token 是 "INVOICE" 和 "ACME Co."，都在页面左上方（x=100），y 从 50 到 130——标题区。版面坐标让模型知道它们是"页眉"而不是"金额"。
- **patch_ids count 256**：只是 `16 × 16`；如果换成 LayoutLMv3 的 224 输入 + 16 像素 patch，应为 196。
- **Donut schema**：`line_items` 是对象数组，这正是 OCR pipeline 最难处理的"表格行"结构，Donut 直接把它作为输出格式。
- **token 预算**：最便宜与最贵差 `12000 / 512 ≈ 23.4` 倍。每天 1,000 万页时是 51.2 亿 vs 1,200 亿 token（测验 Q6）。这就是讲义"大规模纯印刷发票用 LayoutLMv3 + 规则"的经济原因。
- **粘连的两行**：两个名字长度恰好都是 28（已用 `len` 验证），等于列宽，于是没有补空格。

---

## 7. 动手改一改

1. **修复格式**：把 `token_budget` 的列宽改为 30，数字右对齐并加千分位（`{toks:>8,}`），确认六行都对齐。
2. **确定性的三路输入**：实现测验 Q9 的 `layoutlm_input_v2`：用一个递增词表替换 `hash`，bbox 按页面宽高归一化到 0–1000，patch 数由 `img_size // patch` 计算。再进一步：把 `"ACME Co."` 按空格拆成两个词，两个词共享原 bbox（模拟子词共享 bbox）。
3. **算出而不是写死 token 数**：写 `qwen_tokens(w, h)`（每 28×28 像素一个 token）和 `anyres_tokens(grid, tile_tokens=576, thumbnail=True)`，用它们重算表中 LLaVA 与 Qwen2.5-VL 两行，并加一列"每天 1,000 万页的 token 量（十亿）"。
4. **schema 校验器**：实现测验 Q11 的 `validate(out, schema)`，并让 `donut_schema` 对未知任务抛 `ValueError`；再加一条业务规则：`sum(quantity × price)` 与 `total` 的差不超过 0.01。
5. **把配方变成函数**：写 `pick_stack(domain, pages_per_day, handwriting_heavy, needs_latex, regulated)`，实现 skill 文件中的规则（>1,000 万页/天拒绝 Era 3、手写为主拒绝纯 OCR、需要 LaTeX 时必须有 Nougat、受监管必须有审计路径），并为每条规则写一个 `assert` 测试。
6. **进阶（需安装依赖与下载权重，非本课必需）**：用 Hugging Face `transformers` 加载 LayoutLMv3 的 processor，对同一页的 OCR 结果打印真实的 `input_ids`、`bbox`、`pixel_values` 形状，与本脚本的三路输入逐项对照。

---

## 8. 常见坑

- **用内置 `hash()` 做持久 id**：跨进程不一致；需要稳定哈希用 `hashlib`，需要语义 id 用 tokenizer 词表。
- **bbox 不归一化**：同一张发票 150 DPI 和 300 DPI 扫描得到的坐标差一倍，模型学到的位置分布就对不上。
- **把 patch 尺寸和网格数搞混**：224 输入、16 像素 patch → 14×14 网格；"16×16" 两种理解会差出 60 个 patch。
- **f-string 宽度当分隔符用**：`:<N` 只是最小宽度，超长内容会贴住下一列；列之间要显式留空格。
- **`dict.get(..., {})` 吞掉错误**：配置/schema 查找失败时应报错，静默返回空对象会让下游校验形同虚设。
- **把 DocLLM 当 OCR-free**：它和 LayoutLMv3 一样需要 OCR 输入；选型时会直接影响是否需要部署 OCR 引擎。
- **抄表做成本估算**：本表数字有与注释矛盾之处；估算成本要按目标模型的分辨率规则实算，或以 API 返回的 usage 为准。
