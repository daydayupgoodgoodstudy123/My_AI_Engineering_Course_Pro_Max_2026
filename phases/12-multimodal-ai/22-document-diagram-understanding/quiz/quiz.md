# 测验 · 文档与图解理解（Document and Diagram Understanding）

> **阶段 12 · 多模态 AI · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 文档不是照片 | 信息不只在文字里，还在版面（页眉/脚注/双栏）、表格（合并单元格）、图表、手写批注、字体层级里；纯 OCR 只留下文字，丢掉了"$1,245 来自右下角而不是脚注"这类信息 |
| 2 | Era 1：OCR pipeline（2021 年前） | PDF → 逐页图像 → Tesseract 等 OCR（带逐词 bbox）→ 版面分析 → 表格结构识别 → 规则/正则抽字段；确定性强但脆弱，每种失败都要写专门的例外分支 |
| 3 | TrOCR（2021） | 用 Transformer encoder-decoder 替换传统 CNN-CTC 识别器，手写和多语言识别明显提升，但仍是"检测 → 识别 → 版面"的流水线 |
| 4 | LayoutLMv3（2022） | 保留 OCR，输入三路流：OCR 文本 token、每个 token 的 2D bbox、图像 patch；对三种模态做统一 masking 预训练；是 OCR 路线的巅峰，表单/发票很强 |
| 5 | Era 2：OCR-free（2022–2023） | Donut（Swin-B 编码器 + 解码器，直接输出 JSON/markdown）、Nougat（专攻科学论文，输出 LaTeX/markdown）；都是"专才"，Donut 读论文会失败，Nougat 读发票会失败 |
| 6 | DocLLM（2023） | LayoutLM 的"生成式兄弟"：以版面 token 为条件生成自由文本答案，更适合文档 QA，但**仍依赖 OCR 输入** |
| 7 | Era 3：VLM-native（2024+） | 直接把高分辨率整页图像喂给 VLM 提问；讲义列举 LLaVA-NeXT AnyRes、Qwen2.5-VL 动态分辨率、Claude Opus 4.7 的 2576px、PaliGemma 2 |
| 8 | 各自的胜场 | VLM-native 赢在场景文字、合并单元格表格、行内公式、带文字标注的图；OCR pipeline 赢在超大规模低延迟、确定性失败（相对 VLM 幻觉）、需要可审计 OCR 输出的受监管环境 |
| 9 | 2026 配方 | 大规模纯印刷发票 → LayoutLMv3 + 规则；混合文档 → VLM-native；arXiv 全量 → Nougat 管公式、VLM 管图；受监管 → OCR 为主 + VLM 交叉校验 |
| 10 | token 预算决定成本 | 同一页 A4，在本节代码的估算表里从 512（OCR + LayoutLMv3）到 12,000（2576px 前沿 VLM）相差约 23 倍，乘以每天的页数就是成本差 |

### 核心技能（能动手做到）

- [ ] 说清三个时代各自的代表模型、输入/输出形式、优缺点，并把一个新模型正确归类
- [ ] 为一页 OCR 结果构造 LayoutLMv3 风格的三路输入：确定性的 text id、归一化到 0–1000 的 bbox、由图像尺寸和 patch 大小算出的 patch 数
- [ ] 为一个抽取任务写出 Donut 风格的 JSON schema，并写一个校验器检查模型输出的缺字段/类型错误
- [ ] 按"每页 token × 每天页数"估算不同技术栈的日 token 量和相对成本
- [ ] 用 Qwen2.5-VL 的"每 28×28 像素一个 token"规则估算一页文档的视觉 token 数
- [ ] 针对发票、科学论文、手写表单、受监管场景，各给出一个有理由的技术栈选择，并设计 OCR 与 VLM 不一致时的裁决规则

---

## 二、基础自测（选择题）

**Q1.** 讲义把文档 AI 分为三个时代。下列归类**完全正确**的是：

- A. Era 1：Tesseract OCR + 版面分析 + 规则；Era 2：Donut、Nougat 这类直接从像素输出结构化标记的模型；Era 3：把高分辨率整页图像直接交给 Qwen2.5-VL、Claude 等 VLM
- B. Era 1：Donut；Era 2：LayoutLMv3；Era 3：Nougat
- C. Era 1：TrOCR，它首次去掉了文字检测步骤；Era 2：Tesseract；Era 3：LayoutLMv3
- D. Era 2 的模型都需要上游 OCR 提供文字和 bbox，Era 3 才第一次做到 OCR-free

**Q2.** 下列哪一项**不是** LayoutLMv3 的输入流？

- A. OCR 得到的文本 token
- B. 每个 token 的 2D 边界框（bbox）坐标
- C. 页面图像切成的 patch
- D. 由 Swin 编码器直接从像素解码出的 JSON 字段序列

**Q3.** 关于 Donut 与 Nougat，讲义的说法是：

- A. 二者都是通用文档模型，发票和论文都能处理好
- B. Nougat 专门在科学论文上训练、输出 LaTeX/markdown，用它解析扫描发票会失败；Donut 用在科学论文上同样会失败
- C. Nougat 依赖 Tesseract 提供文字，只负责把文字排版成 LaTeX
- D. Donut 的编码器是 CNN，解码器输出纯文本，无法输出 JSON

**Q4.** 在本节代码目录下连续运行两次 `python3 main.py`，第一次 `text_ids[0:4]` 输出 `[6203, 8820, 2219, 3872]`，第二次输出 `[7517, 1811, 1083, 5266]`。最直接的原因是：

- A. `mock_page()` 每次随机生成不同的发票内容
- B. `% 10000` 会随机截断哈希值
- C. Python 对 `str` 的 `hash()` 默认按进程加随机盐（hash randomization，受 `PYTHONHASHSEED` 控制），不同进程结果不同
- D. `dataclass` 的字段顺序每次运行不同

**Q5.** 讲义认为到 2026 年，下列哪种场景 **OCR pipeline 仍然占优**？

- A. 带合并单元格的复杂表格
- B. 手写与印刷混排、多种文字脚本混排的场景文字
- C. 正文中嵌入的数学公式
- D. 要求输出可审计 OCR 结果的受监管环境

**Q6.** 用本节代码 `token_budget()` 表中的数字估算：每天处理 1,000 万页，分别使用"OCR pipeline + LayoutLMv3"（512 token/页）和"VLM native 2576 (Claude 4.7)"（12,000 token/页），每天的输入 token 量和倍数约为：

- A. 约 51.2 亿 vs 1,200 亿，相差约 23 倍
- B. 约 5.12 亿 vs 120 亿，相差约 2.3 倍
- C. 约 51.2 亿 vs 1,200 亿，相差约 12 倍
- D. 约 512 亿 vs 12,000 亿，相差约 23 倍

**Q7.** 代码表格里写着 `("VLM AnyRes 4-tile (LLaVA)", 2916, "336 tiles + thumbnail")`。按阶段 12 · 05/06 的讲义，"2×2 个 336×336 tile + 1 张缩略图"的视觉 token 数应为多少？2916 又对应什么？

- A. 2916，正好是 4 × 729
- B. 2304，即 4 × 576，缩略图不占 token
- C. 2880（5 × 576）；2916 = 4 × 729，对应 384 分辨率 SigLIP tile（每块 729 个 patch）且没算缩略图，与注释"336 tiles + thumbnail"不符
- D. 576，因为 AnyRes 会把所有 tile 池化成一张图

**Q8.** 关于 DocLLM，下列说法正确的是：

- A. DocLLM 是 OCR-free 模型，直接从像素生成答案
- B. DocLLM 以版面 token 为条件生成自由形式答案，适合文档 QA，但仍依赖 OCR 输入；因此讲义开头把它与 Donut、Nougat 并列为"OCR-free 模型"、代码 `eras_table()` 把它放进"Era 2 OCR-free"都不严谨
- C. DocLLM 是判别式模型，只能做分类
- D. DocLLM 是 Nougat 的升级版，专门输出 LaTeX

---

## 三、动手 / 代码题

**Q9.** 阅读本节 `layoutlm_input`：

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

1. 指出它与真实 LayoutLMv3 输入相比至少三处简化或问题（text id、bbox、patch 各一处）。
2. 改写成 `layoutlm_input_v2(tokens, page_w, page_h, img_size=224, patch=16)`：text id 确定且无碰撞、bbox 归一化到 0–1000、patch 数由 `img_size` 和 `patch` 算出。在 `mock_page()` 上假设页面为 600×500 像素，写出前三个归一化 bbox 和 patch 数。

**Q10.** 运行输出里有两行"粘"在一起：

```text
  VLM native 2048 (Qwen2.5-VL)8192        native resolution
  VLM native 2576 (Claude 4.7)12000       frontier, best accuracy
```

1. 解释 `f"  {name:<28}{toks:<10}  {note}"` 为什么会产生这个现象，并给出修复。
2. 表中的 token 数是手写常量。阶段 12 · 09 讲义给出 Qwen2.5-VL 的规则："ViT 接受能被 28 整除的任意 H×W（patch 14 + 2×2 合并）"，即每 28×28 像素一个视觉 token。请估算：(a) A4 300 DPI 原图 2480×3508 不缩放；(b) 长边缩放到 2048、保持 A4 比例。与表中 "VLM native 2048 → 8192" 比较。

**Q11.** Donut 的价值在于"直接输出符合 schema 的 JSON"，但生产里必须校验输出。

1. 写一个递归函数 `validate(out, schema)`，用 `donut_schema("invoice")` 做模板，报告缺失字段和类型错误（`"<string>"`→str，`"<int>"`→int，`"<float>"`→int 或 float）。
2. 用下面的"模型输出"测试，写出应报告的错误：

```python
pred = {"vendor": "ACME Co.",
        "line_items": [{"description": "Widget A", "price": "120.00"}],
        "total": 1245.0, "currency": "USD"}
```

3. 如果有人调用 `donut_schema("receipt")`，会发生什么？这对校验器意味着什么风险？

---

## 四、面试高频题

**Q12.**（基础必考）请概述文档 AI 的三个时代：每个时代的代表方法、输入输出形式、主要优点和主要失败模式。

**Q13.**（原理深挖）LayoutLMv3 的三路输入和统一 masking 预训练分别解决什么问题？为什么它在表单 QA 上能胜过纯 CLIP 类 VLM，却在场景文字上表现不佳？bbox 流"放弃"了什么？（讲义练习 2）

**Q14.**（工程实践）你的业务每天要处理 1,000 万张印刷体发票。你会选什么技术栈？如何在不明显损失准确率的前提下把每页成本压到最低？（讲义练习 1）

**Q15.**（场景设计）为一个受监管的金融文档系统设计"OCR pipeline 为主、VLM 交叉校验"的混合方案。两者结果不一致时怎么裁决？审计日志里要记录什么？（讲义练习 5）

**Q16.**（追问型）有人说"直接把 PDF 截图丢给最强的 VLM 就行了，OCR 已经过时"。你怎么回应？VLM 处理文档时的幻觉有哪些典型表现，如何检测和约束？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义的三段式：Era 1 OCR pipeline（检测 → OCR → 版面 → 规则），Era 2 OCR-free（Donut、Nougat 从像素直接输出结构化标记），Era 3 VLM-native（高分辨率整页图像直接给 VLM）。

- B 把 Donut 放进 Era 1、Nougat 放进 Era 3，都错。
- C 错在 TrOCR 仍是流水线中的一个识别步骤（"detector then TrOCR then layout"），并没有去掉检测；LayoutLMv3 也仍需上游 OCR。
- D 说反了：Era 2 的标志恰恰是不需要 OCR。

### Q2 — 答案：D

LayoutLMv3 的三路输入是 OCR 文本 token、逐 token 的 2D bbox、图像 patch（讲义："Three input streams: OCR text tokens, per-token 2D bounding boxes, image patches"）。D 描述的是 Donut 的工作方式（Swin-B 编码器 + 解码器直接输出 JSON），LayoutLMv3 是编码器式的理解模型，靠下游头做分类、实体抽取、表格 QA。

### Q3 — 答案：B

讲义："These are specialists, not generalists. Donut on a scientific paper fails; Nougat on an invoice fails." 本节的 skill 文件也把"声称 Nougat 能处理扫描发票"列为硬性拒绝项。A 与原文相反；C 错，Nougat 是 OCR-free 的；D 错，Donut 编码器是 Swin-B（Transformer），输出可以是 JSON、markdown 或任意任务 schema。

### Q4 — 答案：C

Python 3.3 起对 `str`/`bytes` 的 `hash()` 默认启用随机化，每个进程一个随机种子。实际验证：同一份代码两次运行得到 `[6203, 8820, 2219, 3872]` 和 `[7517, 1811, 1083, 5266]`，设置 `PYTHONHASHSEED=0` 后才固定。A 错，`mock_page()` 是写死的 8 个 token；B 错，取模是确定运算；D 错，dataclass 字段顺序由定义顺序决定。

后果：真实模型里 text id 必须稳定地对应词表中的行，否则同一个词每次进入不同的 embedding。另外 `% 10000` 只有 1 万个桶，按生日问题计算，约 118 个不同的词就有 50% 的概率出现碰撞（已用 Python 计算）。

### Q5 — 答案：D

讲义列出 OCR pipeline 的三项剩余优势：大规模纯扫描且每页延迟敏感；可靠性（确定性的失败 vs VLM 幻觉）；需要可审计 OCR 输出的受监管环境。A、B、C 都在讲义"VLM-native wins on"的清单里（合并单元格表格、混合脚本场景文字、行内公式）。

### Q6 — 答案：A

`512 × 10,000,000 = 5.12 × 10⁹`（约 51.2 亿）；`12,000 × 10,000,000 = 1.2 × 10¹¹`（约 1,200 亿）；`12,000 / 512 ≈ 23.4`（已用 Python 计算）。B 少了一个数量级；C 倍数算错；D 多了一个数量级。这也是 skill 文件规定"超过 1,000 万页/天时拒绝 Era 3、改用 Era 1 并以 Era 3 抽样校验"的原因。

### Q7 — 答案：C

阶段 12 · 06 讲义："For a 672x672 image at 2x2 grid plus thumbnail: 4 * 576 + 576 = 2880 visual tokens."（每个 336 tile 经 patch 14 得 24×24 = 576 个 token。）`2916 = 4 × 729 = 54²`，729 = 27×27 是 384 分辨率 SigLIP tile 的 patch 数；阶段 12 · 08 讲义中 "AnyRes-4 at 729-per-tile = 2916 + 729" 也说明 2916 是**不含缩略图**的 4 个 384 tile。所以代码这一行的数字和注释对不上。A 只说对了一半（2916 = 4×729），但它不是 336 tile + 缩略图；B 漏了缩略图；D 混淆了 OneVision 的池化。

### Q8 — 答案：B

讲义 DocLLM 小节："Generates free-form answers conditioned on layout tokens. Better for QA on documents; still depends on OCR input." 但讲义开头写 "OCR-free models — Donut (2022), Nougat (2023), DocLLM (2023)"，代码 `eras_table()` 也写 `("Era 2 OCR-free", "Donut, Nougat, DocLLM", ...)`，二者都与 DocLLM 小节矛盾。更准确的归类是：DocLLM 和 LayoutLMv3 同属"OCR + 版面感知"路线，只是一个判别式、一个生成式。A 与原文矛盾；C 把它和 LayoutLMv3 混了；D 是 Nougat 的特点。

### Q9 — 参考答案

1. 问题与简化：
   - **text id**：`hash(t.text) % 10000` 每次进程运行结果不同（见 Q4），而且有碰撞；真实 LayoutLMv3 用 BPE tokenizer（与 RoBERTa 同类）把 OCR 文本切成子词，一个词可能对应多个 token，**这些子词共享同一个 bbox**。代码把 "Widget A"、"$1,245.00" 当作单个 token。
   - **bbox**：直接用像素坐标。LayoutLM 系列的惯例是按页面宽高把坐标归一化到 0–1000 的整数区间，再查 2D 位置 embedding；不归一化的话，不同分辨率的扫描件会得到不同的坐标分布。
   - **patch**：`patch_grid=(16, 16)` 直接得到 256 个 patch，且与任何真实图像无关。LayoutLMv3 把页面缩放到 224×224、用 16×16 的 patch，得到 `14 × 14 = 196` 个 patch（另有一个特殊位置）；参数名 "patch_grid" 容易让人误以为 16 是 patch 尺寸。
   - 另外，代码没有体现三路流如何对齐（每个 text token 有自己的 1D 位置 + 2D 位置，图像 patch 也有自己的 2D 位置），也没有统一 masking。

2. 参考实现（已实际运行）：

```python
def layoutlm_input_v2(tokens, page_w, page_h, img_size=224, patch=16, vocab=None):
    vocab = {} if vocab is None else vocab
    text_ids = []
    for t in tokens:                       # 确定性词表：第一次见到就分配新 id
        if t.text not in vocab:
            vocab[t.text] = len(vocab)
        text_ids.append(vocab[t.text])

    def norm(b):                           # 像素 → 0..1000
        x0, y0, x1, y1 = b
        return (int(1000 * x0 / page_w), int(1000 * y0 / page_h),
                int(1000 * x1 / page_w), int(1000 * y1 / page_h))

    bbox_stream = [norm(t.bbox) for t in tokens]
    n_side = img_size // patch             # 224 // 16 = 14
    patch_ids = list(range(n_side * n_side))
    return {"text_ids": text_ids, "bbox_stream": bbox_stream, "patch_ids": patch_ids}
```

   在 600×500 页面上：`text_ids = [0, 1, 2, 3, 4, 5, 6, 7]`；前三个 bbox 为 `(166, 100, 500, 160)`、`(166, 200, 416, 260)`、`(166, 400, 333, 460)`；patch 数 196。若希望"同一个字符串在任何进程里都得到同一个 id"而又不想维护词表，可用 `hashlib.md5(s.encode()).hexdigest()` 代替内置 `hash`，但碰撞问题依旧——真正的答案是使用 tokenizer 的词表。

### Q10 — 参考答案

1. `:<28` 的含义是"**最少**占 28 个字符、左对齐、不足补空格"，它不会截断，也不会自动加分隔符。`"VLM native 2048 (Qwen2.5-VL)"` 和 `"VLM native 2576 (Claude 4.7)"` 恰好都是 28 个字符（已用 `len` 验证），补 0 个空格，于是紧贴数字。修复：加宽并在列之间留固定空格，数字右对齐加千分位：

```python
print(f"  {'stack':<30}{'tokens':>8}  note")
for name, toks, note in rows:
    print(f"  {name:<30}{toks:>8,}  {note}")
# 输出示例：  VLM native 2048 (Qwen2.5-VL)     8,192  native resolution
```

2. 按"每 28×28 像素一个 token"（已用 Python 计算）：
   - (a) 2480×3508：`round(2480/28) × round(3508/28) = 89 × 125 = 11,125` 个 token（实际会被调整到 28 的倍数，并受 `max_pixels` 上限约束）。
   - (b) 长边 2048、A4 比例：短边约 1448，`52 × 73 = 3,796` 个 token。即使是 2048×2048 的正方形也只有 `2048² / 784 ≈ 5,350` 个。
   - 结论：表中"2048 → 8192"不是由公式推出的，是一个粗略的手写预算；它高于按 Qwen2.5-VL 规则得到的值。做成本估算时应该用目标模型的实际规则（或直接读 API 返回的 usage）计算，而不是抄表。

### Q11 — 参考答案

1. 参考实现（已实际运行）：

```python
TYPE = {"<string>": str, "<int>": int, "<float>": (int, float)}

def validate(out, schema, path="$"):
    errs = []
    if isinstance(schema, dict):
        if not isinstance(out, dict):
            return [f"{path}: expected object"]
        for k, sub in schema.items():
            if k not in out:
                errs.append(f"{path}.{k}: missing")
            else:
                errs += validate(out[k], sub, f"{path}.{k}")
    elif isinstance(schema, list):            # 列表模板只有一个元素，作为每项的 schema
        if not isinstance(out, list):
            return [f"{path}: expected array"]
        for i, item in enumerate(out):
            errs += validate(item, schema[0], f"{path}[{i}]")
    else:
        t = TYPE[schema]
        if isinstance(out, bool) or not isinstance(out, t):   # bool 是 int 的子类，要单独排除
            errs.append(f"{path}: expected {schema}, got {type(out).__name__}")
    return errs
```

2. 输出：

```text
['$.invoice_number: missing',
 '$.line_items[0].quantity: missing',
 '$.line_items[0].price: expected <float>, got str']
```

   `price` 是字符串 `"120.00"`，这是 OCR-free 模型很常见的错误——它"抄写"了页面上的文字而不是转换类型。生产中通常再加一层业务校验，例如 `sum(quantity × price) == total`。注意本节 `mock_page()` 本身也没有数量字段，`$120.00` 与 `$1,245.00` 也对不上，单凭这一页无法填满 schema。

3. `donut_schema` 用 `schemas.get(task, {})`，未知任务**静默返回空字典**。空 schema 意味着 `validate` 永远返回 `[]`（实测 `validate(pred, donut_schema("receipt")) == []`），任何输出都会被判为合格。更安全的做法是对未知任务直接 `raise KeyError` / `ValueError`。

### Q12 — 参考回答要点

- **Era 1 OCR pipeline（2021 前）**：PDF → 图像 → OCR（逐词 bbox）→ 版面分析 → 表格结构识别 → 规则/正则。优点：确定性、可审计、便宜、可逐模块替换（如 TrOCR 换掉识别器）。失败：手写、倾斜扫描、复杂表格、非英文脚本，每种失败都要写例外路径；错误逐级累积。LayoutLMv3 把它推到顶峰（文本 + bbox + 图像三路）。
- **Era 2 OCR-free（2022–2023）**：Donut（Swin-B + 解码器 → JSON）、Nougat（科学论文 → LaTeX/markdown）。优点：单模型、端到端、输出即结构化；失败：专才，跨领域失效；生成式会出错字/漏行。
- **Era 3 VLM-native（2024+）**：高分辨率整页图像直接问 VLM。优点：通用，场景文字、合并单元格、公式、带标注的图都强（讲义：DocVQA 上 Claude 4.7 约 95.1、PaliGemma 2 约 88.4、LayoutLMv3 流水线约 83）；失败：每页 token 多、成本高、延迟高、会幻觉、不可审计。
- 加分点：指出三个时代不是简单替代关系，2026 年的最佳实践常常是混合（讲义的 2026 recipe）。
- 常见误区：把 DocLLM 当作 OCR-free（它仍依赖 OCR 输入）。

### Q13 — 参考回答要点

- **三路输入**：文本 token 提供语义；2D bbox 提供"在页面哪里"（同一个 "Total" 在右下角和在脚注里含义不同）；图像 patch 提供字体、线框、印章、勾选框等视觉线索。
- **统一 masking**：分别遮住文本、图像 patch（以及讲义提到的版面信息）让模型重建，迫使模型学习三种模态之间的对齐，而不是只依赖其中一种。
- **为什么表单 QA 强**：表单的关键是"键—值"的空间关系（标签在左、值在右，或上下对齐）。bbox 是显式坐标，模型无需从像素里自己找；OCR 文字是精确字符串，不会被 VLM 的分辨率限制。
- **为什么场景文字弱**：它完全依赖上游 OCR——OCR 漏检的弯曲文字、艺术字、手写，在 LayoutLMv3 的文本流里根本不存在；bbox 是轴对齐矩形，表达不了倾斜/弯曲文字；图像流分辨率低（224×224），不足以单独读字。bbox 流放弃的是"OCR 没看到的一切"以及形状、方向等细粒度几何信息。
- 加分点：LayoutLM 系列把坐标归一化到 0–1000，并用 2D 位置 embedding；一个词被 BPE 切成多个子词时共享同一个 bbox。

### Q14 — 参考回答要点

- **选型**：Era 1（OCR + LayoutLMv3 + 规则）作为主路径，讲义与 skill 文件都这么建议（"Pure-printed invoices at scale: LayoutLMv3 + rules, cost-efficient"；">10M pages/day 拒绝 Era 3"）。
- **成本量级**：按本节表格，512 vs 12,000 token/页，每天 51.2 亿 vs 1,200 亿 token，差约 23 倍（Q6）。
- **压成本手段**：
  - 先做文档分类/版式聚类，已知模板走规则抽取，未知模板才走模型；
  - OCR 在 CPU/小 GPU 上批量跑，LayoutLMv3 用小尺寸并量化；
  - 对低置信度字段（OCR 置信度低、规则校验失败如金额不平）才升级到 VLM，形成"级联"；
  - VLM 只做抽样校验，用来监控 Era 1 的漂移。
- **准确率保障**：业务规则校验（行项目合计 = 总额、日期格式、税号校验位）；人工抽检；按供应商/模板维度统计错误率。
- 常见误区：直接上最强 VLM 不做成本测算——skill 文件把"对 >1M 页/天提议 VLM-native 却不做成本分析"列为硬性拒绝。

### Q15 — 参考回答要点

- **架构**：OCR pipeline 产出主结果（每个字段带 bbox、OCR 置信度、来源页码）；VLM 在同一页图像上独立抽取同一 schema；两者都写入审计日志。
- **一致性比较**：字段级比较，做规范化后再比（去千分位、统一日期格式、大小写）；数值字段允许极小容差。
- **裁决规则**：
  - 一致 → 自动通过；
  - 不一致但 OCR 高置信且通过业务规则 → 以 OCR 为准（可审计、可复现），记录 VLM 意见；
  - 不一致且 OCR 低置信或业务规则失败 → 进入人工复核队列，不能让 VLM 直接覆盖；
  - 关键字段（金额、账号）任何不一致都转人工。
- **审计日志**：原始页图像哈希、OCR 引擎与版本、VLM 模型与版本、prompt、两份原始输出、字段级 diff、裁决规则 ID、复核人和时间。
- 加分点：定期用人工复核结果统计"OCR 对 / VLM 对"的比例，用来调整阈值；VLM 输出应要求附带它读到的位置（bbox 或页码引用），便于核对。

### Q16 — 参考回答要点

- **回应**：VLM-native 在质量上确实追上甚至超过了 OCR 流水线（讲义 DocVQA 数字），但"过时"不成立：
  - 成本与延迟：每页上万 token，在千万页/天规模下差一个数量级以上；
  - 可审计与确定性：受监管行业需要可复现的 OCR 输出；
  - 失败模式不同：OCR 的失败是可定位的（某个框没识别出来），VLM 的失败是"看起来很合理的错误"。
- **典型幻觉**：数字错位或改写（把 1,245 读成 1,254）；合并单元格对错行列；把表头当数据；跨页表格丢行；编造不存在的字段值来"填满" schema；对模糊手写给出确定答案；公式转 LaTeX 时漏下标。
- **检测与约束**：
  - 结构化输出（JSON schema、约束解码）+ 校验器（Q11）；
  - 业务一致性规则（合计、校验位）；
  - 要求输出附带引用位置（bbox/页码），再用 OCR 或裁剪图回查；
  - 多次采样或双模型一致性检查；
  - 分辨率要够（讲义强调前沿差距主要来自分辨率和底座规模）。
- 加分点：给出混合架构（Q14/Q15），而不是二选一。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：本节的先修课；VLM 如何把图像 patch 变成 LLM 的 token，576 / 2880 个视觉 token 的来源。
- [阶段 12 · 06 任意分辨率视觉：Patch-n'-Pack 与 NaFlex](../../06-any-resolution-patch-n-pack/docs/zh.md)：AnyRes 切 tile 与 token 预算，是文档这种高分辨率输入的关键。
- [阶段 12 · 09 Qwen-VL 系列与动态帧率视频](../../09-qwen-vl-family-dynamic-fps/docs/zh.md)：Qwen2.5-VL 的原生动态分辨率（每 28×28 像素一个 token）。
- [阶段 04 · 19 OCR 和文档理解](../../../04-computer-vision/19-ocr-document-understanding/docs/zh.md)：传统 OCR 与文档理解的视觉基础。
- [阶段 11 · 03 Structured Outputs：JSON、Schema 校验与约束解码](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：Donut 风格 schema 输出的校验与约束。

### 本节被哪些后续内容用到
- [阶段 12 · 23 ColPali 与视觉原生文档 RAG](../../23-colpali-vision-native-rag/docs/zh.md)：不做 OCR、直接用页面图像做检索。
- [阶段 12 · 24 多模态 RAG 与跨模态检索](../../24-multimodal-rag-cross-modal/docs/zh.md)：把文档、图表、图片统一进检索系统。
- [阶段 12 · 25 多模态 Agents 与计算机操作](../../25-multimodal-agents-computer-use/docs/zh.md)：读懂屏幕截图与读懂文档页是同一类能力。
- [阶段 19 · 04 多模态文档问答](../../../19-capstone-projects/04-multimodal-document-qa/docs/zh.md)：综合项目中以视觉方式处理 PDF、表格与图表。

### 延伸关键词
`Tesseract` · `TrOCR` · `LayoutLMv3` · `bbox 0–1000 归一化` · `Donut` · `Nougat` · `DocLLM` · `PaliGemma 2` · `DocVQA` · `ChartQA` · `AnyRes` · `dynamic resolution` · `schema validation` · `human-in-the-loop review`
