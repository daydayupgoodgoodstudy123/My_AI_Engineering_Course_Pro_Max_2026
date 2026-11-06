# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 07 节 开放 Weight VLM 的构建方案：真正重要的因素 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`__future__`），无需 NumPy、GPU 或网络

---

## 1. 这份代码在考察什么

这份代码不训练任何模型，而是把 2024–2025 年几篇开放 VLM 论文（MM1、Idefics2、Cambrian-1、Molmo、Prismatic VLMs）的消融结论"压缩"成几张硬编码的表，然后：

1. **打印典型开放 VLM 的成绩表**（MMMU、CV-Bench、DocVQA），让你看到"同样是 7B，Molmo 为什么能高出一截"；
2. **打印各设计轴对方差的贡献**（对应讲义的 Prismatic 分解）；
3. **打印 encoder 替换和数据组合替换的对比表**（对应讲义的"轴 1"和"轴 4"）；
4. **按预算和任务类型给现成模型加权打分、排序**，演示"任务不同，权重不同"。

对应讲义的核心概念：五轴设计空间、encoder > connector、详细人类字幕 > 蒸馏、visual-token 数是最大的旋钮、LLM 规模决定上限。

> 一句话：**把消融表变成可查询的数据结构，训练"读表、按任务加权、挑配方"的直觉**。代码 docstring 自己也说："The point is the structure of the evidence, not the numeric precision." 表中数字是"浓缩"的示意值，不宜当作论文原始数据引用。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Recipe` | `@dataclass` | 一条模型记录：名字、encoder、connector、LLM 大小、数据、分辨率、三项分数 | 五轴设计空间 |
| `RECIPES` | 模块级列表 | 9 个典型开放 VLM（LLaVA-1.5 到 Molmo-72B） | 消融表 / 排行榜 |
| `axis_impact()` | 函数 | 打印各轴的方差占比和文字说明 | Prismatic 方差分解 |
| `compare_encoders()` | 函数 | 固定 7B LLM 时 5 种 encoder 的三项分数 | 轴 1：encoder |
| `compare_data()` | 函数 | 固定 SigLIP + 7B + AnyRes 时 5 种数据组合的 MMMU | 轴 4：数据 |
| `print_recipes()` | 函数 | 打印 `RECIPES` 表格 | 典型配方对比 |
| `pick_recipe(budget_b, task)` | 函数 | 过滤 LLM ≤ 预算的模型，按任务权重加权打分取前 3 | 按任务选配方 |
| `main()` | 函数 | 依次调用以上函数，演示三次 picker | 入口 |

数据流：`main()` → `print_recipes()`（读 `RECIPES`）→ `axis_impact()` → `compare_encoders()` → `compare_data()` → `pick_recipe(10,"ocr")` / `pick_recipe(80,"reasoning")` / `pick_recipe(10,"agent")`（都读 `RECIPES`）。四张表之间**没有数据依赖**，encoder 表和数据表并不参与 picker 的打分。

---

## 3. 逐段精讲

### 3.1 `Recipe` 数据类与 `RECIPES` 表

```python
@dataclass
class Recipe:
    name: str
    encoder: str
    connector: str
    llm_b: int
    data: str
    resolution: str
    mmmu: float
    cv_bench: float
    docvqa: float


RECIPES = [
    Recipe("LLaVA-1.5", "CLIP L/14 @336", "MLP-2", 13, "LLaVA-Inst-150k", "336", 35.3, 56.0, 55.0),
    ...
    Recipe("Molmo-7B-D", "SigLIP SO400m/14", "MLP-2", 7, "PixMo (712K human caps)", "AnyRes 672", 45.3, 65.0, 92.4),
    Recipe("Molmo-72B", "SigLIP SO400m/14", "MLP-2", 72, "PixMo (712K human caps)", "AnyRes 672", 54.1, 73.0, 93.5),
    ...
]
```

- 一个 `Recipe` 恰好覆盖讲义五轴中的四个：`encoder`（轴 1）、`connector`（轴 2）、`llm_b`（轴 3）、`data`（轴 4）、`resolution`（轴 5 的一部分，没有"schedule"信息），再加三项 benchmark。
- `@dataclass` 自动生成 `__init__`，所以可以按位置参数构造：`Recipe("LLaVA-1.5", "CLIP L/14 @336", ...)`。
- 三个 benchmark 各有侧重：**MMMU** 偏大学水平多学科推理（主要受 LLM 影响）；**CV-Bench** 偏细粒度视觉感知（主要受 encoder 影响）；**DocVQA** 偏文档 OCR（主要受分辨率和 token 数影响）。
- 值得注意的几行对比：
  - LLaVA-1.5 → LLaVA-NeXT：encoder、connector、LLM 都不变，只把分辨率换成 AnyRes 672 并加数据，DocVQA 从 55.0 跳到 77.4（+22.4），MMMU 只 +0.9——**分辨率主要动 OCR**。
  - Molmo-7B-D vs Prismatic-7B default：encoder（SigLIP）、connector（MLP-2）、LLM 规模（7B）相同，差别在数据（PixMo vs LLaVA-Inst + ShareGPT4V）和分辨率（AnyRes 672 vs 336），MMMU 45.3 vs 40.0。
  - Molmo-7B-D → Molmo-72B：只换 LLM 规模，MMMU +8.8，DocVQA 只 +1.1——**LLM 规模主要动推理**。
- ⚠️ 讲义说 Prismatic 的受控比较用 "Same 13B LLM"，代码里却是 "Prismatic-7B default"（7B）。两者描述的不是同一个配置。

### 3.2 `axis_impact()`：方差分解

```python
    axes = [
        ("visual-token count", 60, "64 -> 576 -> 1024 tokens; diminishing past 1024"),
        ("image encoder",      20, "CLIP vs SigLIP vs DINOv2; concatenation helps"),
        ("connector arch",      5, "MLP ~= Q-Former ~= Perceiver at same token count"),
        ("data mix",           10, "detailed human caps > distilled GPT-4V data"),
        ("LLM size",           15, "7B -> 70B plateau around MMMU 55"),
        ("resolution sched",    5, "ramp 224 -> 448 > flat 448; native wins OCR"),
    ]
    total_weight = sum(a[1] for a in axes)
    print(f"{'axis':<22}{'%var':>8}  note")
    for name, pct, note in axes:
        bar = "#" * (pct // 2)
        print(f"{name:<22}{pct:>6}% {bar}")
        print(f"{'':<22}       {note}")
    print(f"note: weights rebased from ~{total_weight}% to ~100% after rounding.")
```

- 每个轴是一个三元组 `(名字, 百分比, 说明)`；`sum(a[1] for a in axes)` 用生成器表达式取出第 2 个元素求和。
- `"#" * (pct // 2)`：字符串乘整数得到重复字符串，每 2 个百分点一个 `#`，是终端里最简单的"条形图"。
- ⚠️ **声明了 rebase 却没做**：`total_weight = 115`，最后一行说 "rebased from ~115% to ~100%"，但打印的仍是原始数字。
- ⚠️ **与讲义不一致**：讲义的 Prismatic 分解是 token 数 60%、encoder 20%、connector 5%、"Everything else (data mix, scheduler, LR) the remaining ~15%"。代码把"其余"拆成 data mix 10% + LLM size 15% + resolution 5%，凭空多出 15 个点。更重要的是，Prismatic 实验固定了 LLM，"LLM size"不可能出现在这次受控比较的分解里——这是把讲义"轴 3"的结论混了进来。修正方案见测验 Q9。

### 3.3 `compare_encoders()` 与 `compare_data()`：单轴对比表

```python
    rows = [
        ("CLIP ViT-L/14 @ 336",        38.5, 56.0, 70.0),
        ("SigLIP SO400m/14 @ 384",     41.0, 60.0, 75.0),
        ("DINOv2 ViT-g/14 @ 224",      37.0, 65.0, 52.0),
        ("SigLIP + DINOv2 concat",     42.0, 67.0, 74.0),
        ("InternViT-6B @ 448",         43.0, 66.0, 78.0),
    ]
    print(f"{'encoder':<32}{'MMMU':>8}{'CV-B':>8}{'DocVQA':>10}")
    for name, mmmu, cv, doc in rows:
        print(f"{name:<32}{mmmu:>8.1f}{cv:>8.1f}{doc:>10.1f}")
```

- 这张表体现了"不同 encoder 擅长不同 benchmark"：DINOv2（自监督、无文本对齐）CV-Bench 65.0 很高，但 DocVQA 只有 52.0、MMMU 37.0 最低；SigLIP 语义对齐好，MMMU 和 DocVQA 都优于 CLIP；拼接 SigLIP + DINOv2 在 CV-Bench 上 67.0，超过任何单个。
- `for name, mmmu, cv, doc in rows`：在 for 循环里直接**元组解包**。
- ⚠️ 与讲义的小出入：
  - 讲义说 MM1 中 CLIP → SigLIP "added 3+ points MMMU"，这张表只给了 +2.5（38.5 → 41.0），总结行也写 "+2.5"。
  - 讲义练习 2 说 Cambrian-1 发现拼接 "adds no signal on MMMU"，表中拼接却比 SigLIP 单独高 1.0 MMMU；拼接的 DocVQA（74.0）还略低于 SigLIP 单独（75.0）。
  - 表头说 "7B LLM"，但 encoder 分辨率各不相同（224 / 336 / 384 / 448），视觉 token 数也不相同。按讲义自己的观点，token 数才是影响最大的因素，所以这张表并不是严格的"单轴"消融。

```python
    rows = [
        ("LLaVA-Inst-150k",         40.0, "web caps + GPT-4 dialogues"),
        ("+ ShareGPT4V",            42.0, "+ GPT-4V detailed captions"),
        ("+ Cauldron",              43.0, "+ OCR + charts + multimodal instructions"),
        ("PixMo (human caps only)", 45.3, "712K dense human captions"),
        ("PixMo + Cauldron + more", 47.0, "best data mix as of Jul 2025"),
    ]
```

- 前三行是**累加**（`+` 号表示在上一行基础上加数据），第四行是**替换**（只用 PixMo）。PixMo 45.3 比 "+ShareGPT4V" 高 3.3、比 "+Cauldron" 高 2.3，与总结行的 "+2-3 MMMU" 一致。
- "at the same training token count" 这个前提在表里没有体现（没有 token 数一列），只能当作结论转述。

### 3.4 `print_recipes()`：格式化表格

```python
    print(f"{'recipe':<22}{'LLM':>6}{'MMMU':>8}{'CV-B':>8}{'DocVQA':>10}")
    for r in RECIPES:
        print(f"{r.name:<22}{r.llm_b:>5}B{r.mmmu:>8.1f}{r.cv_bench:>8.1f}{r.docvqa:>10.1f}")
```

- `:<22` 左对齐占 22 列，`:>5` 右对齐占 5 列，`:>8.1f` 右对齐 8 列、保留 1 位小数。表头的 `'LLM':>6` 与数据行的 `{r.llm_b:>5}B`（5 列 + 字母 B）正好对齐。

### 3.5 `pick_recipe()`：按任务加权的 picker

```python
def pick_recipe(budget_b: int, task: str) -> None:
    weights = {"mmmu": 1.0, "cv": 1.0, "doc": 1.0}
    if task == "ocr":
        weights = {"mmmu": 0.4, "cv": 0.3, "doc": 1.2}
    elif task == "agent":
        weights = {"mmmu": 1.0, "cv": 1.2, "doc": 0.8}
    elif task == "reasoning":
        weights = {"mmmu": 1.5, "cv": 0.5, "doc": 0.8}

    def score(r: Recipe) -> float:
        return r.mmmu * weights["mmmu"] + r.cv_bench * weights["cv"] + r.docvqa * weights["doc"]

    candidates = [r for r in RECIPES if r.llm_b <= budget_b]
    candidates.sort(key=score, reverse=True)
    for r in candidates[:3]:
        ...
```

- **任务 → 权重**：OCR 重 DocVQA（1.2），agent 重 CV-Bench（1.2，需要看清 UI 元素位置），reasoning 重 MMMU（1.5）。
- `score` 是**嵌套函数**，它读取外层的 `weights`（闭包）。`candidates.sort(key=score, reverse=True)` 把函数本身作为排序键，按分数从高到低原地排序。
- 预算过滤只看 `llm_b`：`budget_b=10` 时保留 3B、7B、8B 的 5 个模型，排除 13B 的 LLaVA 系列。
- 手算示例：OCR 下 Molmo-7B-D = `0.4 × 45.3 + 0.3 × 65.0 + 1.2 × 92.4 = 18.12 + 19.5 + 110.88 = 148.5`，与输出一致。
- ⚠️ **量纲问题**：本表 DocVQA 的标准差约 11.8，MMMU 约 5.4，CV-Bench 约 5.2。直接加权求和时，DocVQA 的差异主导排名。实测 `budget=10` 时四种权重（含默认等权重）第一名都是 Molmo-7B-D；要让 Cambrian-1-8B 在 agent 任务下胜出，`cv` 权重需大于约 5.1（测验 Q10）。
- ⚠️ **不是"组合配方"**：它只在 9 个现成模型里挑，不会回答讲义 "Use It" 里"把 SigLIP 换成 CLIP 的预期 delta"或"先消融哪个轴"这类问题。
- ⚠️ **未知任务静默回退**：`if/elif` 链没有 `else`，`task="OCR"`（大写）或拼错时悄悄使用等权重。
- ⚠️ **没有实现 skill 文件的拒绝规则**：`outputs/skill-vlm-recipe-picker.md` 要求"1–3B 做推理任务时拒绝"，但 `pick_recipe(5, "reasoning")` 会照常推荐 MM1-3B。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 硬编码"浓缩"的论文数字 | 无需下载模型、几毫秒跑完，聚焦证据结构 | 数字不精确，且来自不同评测协议，不可横向精确比较；生产中应引用原论文表格或自己复现 |
| 用 `@dataclass` 表示一条配方 | 字段清晰，可按属性访问 | 若要做筛选和统计，可换成 pandas DataFrame |
| 终端里用 `#` 画条形图 | 零依赖 | 无法展示误差条；正式报告用 matplotlib |
| 线性加权打分 | 简单易懂，体现"任务决定权重" | benchmark 量纲不同，应先标准化（z-score / min-max） |
| 只按 LLM 参数过滤预算 | LLM 是参数大头（讲义："LLM size is the dominant param cost"） | 忽略 encoder 参数（InternViT-6B 本身 6B）、视觉 token 数带来的推理成本和延迟 |
| 在现成模型中挑选 | 实现量小 | 不能组合各轴、不能预测 delta；真正的 picker 应基于各轴的效应估计做组合 |
| 方差分解写死为常数 | 展示"先消融什么" | 与讲义不一致、总和 115%；应改成讲义的 60/20/5/15 或真正归一化 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 让类型注解延迟求值（存成字符串），可以在注解里引用尚未定义的名字，也减少运行时开销 |
| `@dataclass` | `@dataclass class Recipe:` | 根据带类型注解的类属性自动生成 `__init__`、`__repr__`、`__eq__` |
| 类型注解 | `llm_b: int`、`def pick_recipe(budget_b: int, task: str) -> None` | 说明变量/参数/返回值类型，Python 运行时不强制检查 |
| 模块级常量 | `RECIPES = [...]` | 全大写命名表示"约定不修改"的全局数据 |
| 元组列表 + 解包 | `for name, pct, note in axes:` | 循环时把三元组直接拆成三个变量 |
| 生成器表达式 | `sum(a[1] for a in axes)` | 不建中间列表，边生成边求和 |
| 字符串乘法 | `"#" * (pct // 2)`、`"-" * 60`、`"=" * 60` | 重复字符串，常用于分隔线和简易条形图 |
| 整除 `//` | `pct // 2` | 向下取整的除法，`15 // 2 == 7` |
| f-string 对齐与格式 | `{name:<22}`、`{pct:>6}`、`{mmmu:>8.1f}`、`{'':<22}` | `<` 左对齐、`>` 右对齐、数字为宽度、`.1f` 保留 1 位小数；`{'':<22}` 输出 22 个空格做缩进 |
| 相邻字符串字面量拼接 | `print("deltas: SigLIP adds ... " "concat beats ...")` | 括号内相邻的两个字符串会在编译时自动拼成一个 |
| 字典 | `weights = {"mmmu": 1.0, "cv": 1.0, "doc": 1.0}`、`weights["mmmu"]` | 按键查值 |
| `if / elif` 链 | `if task == "ocr": ... elif task == "agent": ...` | 多分支选择；没有 `else` 时不匹配的输入走默认值 |
| 嵌套函数与闭包 | `def score(r)` 定义在 `pick_recipe` 内部，读取外层 `weights` | 内部函数可以访问外层函数的局部变量 |
| 列表推导式（带过滤） | `[r for r in RECIPES if r.llm_b <= budget_b]` | 一行完成"遍历 + 筛选" |
| `list.sort(key=..., reverse=True)` | `candidates.sort(key=score, reverse=True)` | 原地排序，`key` 接收一个函数，`reverse=True` 表示降序 |
| 切片 | `candidates[:3]` | 取前 3 个，不足 3 个时取全部，不会报错 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 `import` 时不执行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3，几毫秒完成，输出完全确定，没有随机性），节选：

```text
CANONICAL OPEN VLMS (ablation-reported MMMU, CV-Bench, DocVQA)
recipe                   LLM    MMMU    CV-B    DocVQA
LLaVA-1.5                13B    35.3    56.0      55.0
LLaVA-NeXT               13B    36.2    58.5      77.4   ← 只加 AnyRes + 数据，DocVQA +22.4
Idefics2-8B               7B    43.0    60.0      74.0
...
Molmo-7B-D                7B    45.3    65.0      92.4   ← 7B 档三项里两项第一
Molmo-72B                72B    54.1    73.0      93.5   ← 只放大 LLM：MMMU +8.8，DocVQA +1.1
Cambrian-1-8B             8B    42.7    67.8      77.8   ← ≤10B 中 CV-Bench 最高（多 encoder 拼接）

AXIS-IMPACT DECOMPOSITION (Prismatic VLMs controlled comparison)
visual-token count        60% ##############################
image encoder             20% ##########
connector arch             5% ##
data mix                  10% #####
LLM size                  15% #######          ← 15 // 2 = 7 个 #
resolution sched           5% ##
note: weights rebased from ~115% to ~100% after rounding.   ← 实际并未 rebase

ENCODER SWAP DELTAS (fixed 7B LLM, LLaVA-Inst + shareGPT4V data)
DINOv2 ViT-g/14 @ 224               37.0    65.0      52.0   ← 感知强、OCR 弱
SigLIP + DINOv2 concat              42.0    67.0      74.0   ← CV-Bench 最高

PICKER: budget 10B params, task profile: ocr
  Molmo-7B-D             LLM 7B  score=148.5
  Cambrian-1-8B          LLM 8B  score=130.8
  Idefics2-8B            LLM 7B  score=124.0

PICKER: budget 80B params, task profile: reasoning
  Molmo-72B              LLM 72B  score=192.4
  Molmo-7B-D             LLM 7B  score=174.4
  Cambrian-1-8B          LLM 8B  score=160.2

PICKER: budget 10B params, task profile: agent
  Molmo-7B-D             LLM 7B  score=197.2
  Cambrian-1-8B          LLM 8B  score=186.3
  Idefics2-8B            LLM 7B  score=174.2
```

逐项解读：

- **成绩表**的价值在于"成对比较"：LLaVA-1.5 → NeXT 说明分辨率主要拉 DocVQA；Molmo-7B → 72B 说明 LLM 规模主要拉 MMMU；Molmo-7B-D 与 Prismatic-7B（同 encoder、同 connector、同 LLM 规模）的差距主要来自数据和分辨率。
- **方差分解**的六个数字加起来是 115%，说明 note 行的 "rebased" 没有实现；按讲义应为 60/20/5/15。
- **encoder 表**说明没有"全能"的 encoder：DINOv2 适合感知、SigLIP 适合语义和 OCR，拼接在视觉中心基准上最好。
- **三次 picker** 的第一名分别是 Molmo-7B-D、Molmo-72B、Molmo-7B-D。agent 权重下 Cambrian-1-8B 虽然 CV-Bench 更高（67.8 vs 65.0），但 DocVQA 落后 14.6 分，0.8 的 DocVQA 权重就足以把它压下去。这正是"未标准化的加权求和"的典型表现。
- `reasoning` 用的是 80B 预算，所以 Molmo-72B 入选；若预算为 10B，额外测试的结果是 Molmo-7B-D（174.4）> Cambrian-1-8B（160.2）> Idefics2-8B（153.7）。

---

## 7. 动手改一改

1. **修正方差分解**：按讲义改成 token 数 60、encoder 20、connector 5、其余 15，或保留六项但真正归一化到 100%（参考测验 Q9），并把 "LLM size" 单独列为"不在 Prismatic 受控实验内"的注释。
2. **标准化打分**：在 `pick_recipe` 中先对三列做 z-score，再加权；对比 agent 任务下 Cambrian-1-8B 与 Molmo-7B-D 的分差变化。
3. **任务表与拒绝规则**：把权重写成 `TASK_WEIGHTS` 字典，未知任务抛 `ValueError`；当 `task == "reasoning"` 且 `budget_b <= 3` 时打印拒绝理由（对应 skill 文件的 refusal rule）。
4. **加入"预期 delta"查询**：写 `encoder_delta(from_enc, to_enc, metric)`，从 `compare_encoders()` 的行数据中返回差值，回答讲义中"在 7B 上把 SigLIP 换成 CLIP，MMMU 预期变化多少"的问题（需要先把 `rows` 提到模块级）。
5. **按轴组合配方**：把每个轴的选项和"相对基线的增益"建成字典（encoder 增益、数据增益、分辨率增益），给定任务和预算，用加法模型组合出一个新配方并输出预期分数。思考这个加法模型忽略了哪些交互效应。
6. **讲义练习 5**：用代码生成一个 2×2 因子实验计划（encoder × 数据），并写一个函数从 4 次运行的分数中计算主效应和交互效应（参考测验 Q12）。

---

## 8. 常见坑

- **把"浓缩数字"当论文原始数据引用**：表中数字是示意值，跨论文的分数来自不同评测协议，不能直接相减得出精确结论。
- **只看一个 benchmark 就下结论**：同一个改动在 MMMU、CV-Bench、DocVQA 上效果完全不同（例如 DINOv2 感知强、OCR 弱）。
- **未标准化就加权**：取值范围大的指标（本表的 DocVQA）会主导排名，权重失去原本的含义。
- **把 token 数差异误认为 connector 差异**：比较 MLP 和 Q-Former 时如果 token 数不同，结论无效。
- **`if/elif` 没有 `else`**：拼错的任务名会静默走默认分支，输出看起来正常但其实是错的。
- **声明与实现不一致**：如 "rebased to ~100%" 的提示与实际打印值不符。读别人代码时要核对输出是否真的满足注释和提示里的说法。
- **预算只算 LLM**：InternViT-6B 这类大 encoder 和高分辨率带来的上千视觉 token，都会显著增加推理成本。
