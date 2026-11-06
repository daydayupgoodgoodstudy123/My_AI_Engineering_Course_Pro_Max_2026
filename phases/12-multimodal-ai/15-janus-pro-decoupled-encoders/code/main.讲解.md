# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 15 节 Janus-Pro：用于统一 Multimodal Models 的解耦 Encoders ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

Janus-Pro 的核心是一张"路由图"：理解任务走 SigLIP，生成任务走 VQ，两条路在共享 Transformer 主干处汇合，再分别从文本头或 VQ 头出去。这份 150 行的脚本用三个桩对象（stub）和一个关键词路由器把这张图"跑"一遍：

1. **两个编码器桩**：`SiglipStub` 输出连续向量（语义特征），`VQStub` 输出整数码（可重建编码），并能"解码"。
2. **共享主干桩**：`SharedBody.process` 不管输入从哪个编码器来，按 `kind` 产出文本或 image token。
3. **路由器**：`route` 用关键词计数把 prompt 分成 understand / generate / ambiguous。
4. **数据扩展表**：Janus vs Janus-Pro 在参数、三个训练阶段数据量、MMMU、GenEval 上的对比。

> 一句话：**这份代码展示的是"数据流向"而不是"计算"**——读的时候重点是路径对不对、哪些信息该进主干却没进，以及关键词路由为什么不可靠。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SiglipStub` | `@dataclass` | `encode(seed)` → 32 维高斯向量 | 理解侧语义编码器 |
| `VQStub` | `@dataclass` | `encode(seed)` → 16 个 0–255 的码；`decode` → 描述字符串 | 生成侧 VQ tokenizer / 解码器 |
| `SharedBody` | `@dataclass` | `process(stream, kind)` → 4 个词或 16 个随机码 | 共享 Transformer 主干 |
| `route` | 函数 | 关键词计数分类 prompt | 任务路由 |
| `run_pipeline` | 函数 | 按路由结果走 SigLIP / VQ / 两者，返回 trace 字典 | 解耦编码 + 共享主干 |
| `demo_routing` | 函数 | 5 个 prompt 跑一遍并打印 | 路由演示 |
| `data_scale_table` | 函数 | 打印 Janus → Janus-Pro 扩展表 | 数据/模型扩展 |
| `main` | 函数 | 依次调用并打印架构一句话总结 | — |

数据流：`prompt` → `route` → {`understand`: `SiglipStub.encode` → `SharedBody.process(kind="text_out")`；`generate`: `VQStub.encode`（可选）→ `SharedBody.process(kind="image_out")` → `VQStub.decode`；`ambiguous`: 两路都跑} → `trace` 字典 → 打印。

---

## 3. 逐段精讲

### 3.1 两个编码器桩：语义 vs 重建

```python
@dataclass
class SiglipStub:
    dim: int = 32

    def encode(self, image_seed: int) -> list[float]:
        random.seed(image_seed)
        return [random.gauss(0, 0.5) for _ in range(self.dim)]


@dataclass
class VQStub:
    vocab: int = 256
    n_tokens: int = 16

    def encode(self, image_seed: int) -> list[int]:
        random.seed(image_seed * 7 + 1)
        return [random.randint(0, self.vocab - 1) for _ in range(self.n_tokens)]

    def decode(self, tokens: list[int]) -> str:
        return f"VQ-decoded image from tokens {tokens[:4]}..."
```

- **类型差异就是概念差异**：SigLIP 输出 `list[float]`（连续语义向量，只能"读"，不能还原像素）；VQ 输出 `list[int]`（码本下标，有 `decode`，能还原图像）。这正是讲义"semantic features vs reconstruction codes"的对比，也是为什么 `VQStub` 有 `decode` 而 `SiglipStub` 没有。
- 用 `image_seed` 代表"一张图"：同一个种子 → 同一组特征/码，模拟"同一张图编码结果确定"。
- `@dataclass` 让 `dim`、`vocab`、`n_tokens` 成为可配置字段，例如 `SiglipStub(dim=1152)`。
- ⚠️ 讲义 "Use It" 说 SigLIP-like 产生 **256 维**向量，代码默认是 32 维。
- ⚠️ **副作用**：`random.seed(...)` 重置的是**全局**随机数生成器。文件开头的 `random.seed(3)` 因此被覆盖，`SharedBody.process` 后续的随机输出变成"最后一次 encode 种子"的函数，组件之间产生隐式耦合。正确做法是每个桩持有 `random.Random(seed)` 实例。

### 3.2 `SharedBody`：不看输入的主干

```python
@dataclass
class SharedBody:
    name: str = "DeepSeek-7B-init"

    def process(self, input_stream: list, kind: str) -> list:
        if kind == "text_out":
            return [f"word_{i}" for i in range(4)]
        if kind == "image_out":
            return [random.randint(0, 255) for _ in range(16)]
        return []
```

- `name` 暗示主干从 DeepSeek 7B LLM 初始化（讲义："Janus-Pro does initialize from DeepSeek-MoE-7B"；代码写的是 "DeepSeek-7B-init"，两处说法不同，以原论文为准）。
- 主干**只有一个**，理解和生成都调用同一个 `process`——这是"shared body"的核心意思；输出类型由 `kind` 决定，对应两个输出头（文本 NTP 头、VQ 头）。
- ⚠️ `input_stream` **完全没被使用**；而且调用方也从未把 prompt 文本传进来。真实 Janus-Pro 中主干处理的是"文本 token + 视觉特征/token"的统一序列，没有文本条件就不可能做文生图或 VQA。
- ⚠️ 未知 `kind` 静默返回 `[]`，容易掩盖调用错误；更好的做法是 `raise ValueError`。

### 3.3 `route`：关键词计数路由

```python
def route(prompt: str) -> str:
    u_keywords = ["describe", "what", "why", "caption", "explain", "how many"]
    g_keywords = ["draw", "generate", "sketch", "render", "create", "paint"]
    p = prompt.lower()
    u_score = sum(1 for k in u_keywords if k in p)
    g_score = sum(1 for k in g_keywords if k in p)
    if g_score > u_score:
        return "generate"
    if u_score > g_score:
        return "understand"
    return "ambiguous"
```

- 先 `lower()` 统一大小写，再数两类关键词各命中几个，多者胜，平局为 ambiguous。这是讲义练习 2 的最简实现。
- `k in p` 是**子串**判断，不看词边界。实测误判：
  - `"What's in this painting?"` → ambiguous（`paint` ⊂ `painting`）；
  - `"Draw me a diagram that explains how a transformer works"` → ambiguous（`explain` ⊂ `explains`）；
  - `"Explain how to draw a cat"` → ambiguous（用户要文字教程）；
  - `"Make this photo look like night time"` → ambiguous（编辑请求，两表都没有 `make`）；
  - `"Withdraw cash icon"` → generate（`draw` ⊂ `withdraw`，碰巧"对"）。
- 讲义说路由可以由 `<understand>` / `<generate>` 标签显式决定——生产中这比猜意图可靠得多（测验 Q9 给出完整方案）。

### 3.4 `run_pipeline`：三条分支

```python
    task = route(prompt)
    trace = {"prompt": prompt, "task": task}

    if task == "understand":
        feats = siglip.encode(image_seed)
        trace["route"] = "SigLIP -> shared body -> text"
        trace["input_len"] = len(feats)
        out = body.process(feats, kind="text_out")
        trace["output"] = out
    elif task == "generate":
        tokens = vq.encode(image_seed) if image_seed else []
        trace["route"] = "(optional VQ) -> shared body -> image VQ -> decoder"
        out_tokens = body.process(tokens, kind="image_out")
        trace["output"] = vq.decode(out_tokens)
    else:
        trace["route"] = "ambiguous: run both and merge"
        feats = siglip.encode(image_seed)
        tokens = vq.encode(image_seed)
        trace["input_len"] = f"SigLIP:{len(feats)} + VQ:{len(tokens)}"
        trace["output"] = (body.process(feats, "text_out"),
                           vq.decode(body.process(tokens, "image_out")))
```

- **理解分支**：图像 → SigLIP → 主干 → 文本，正好对应讲义的 understanding path（省略了 2 层 MLP adaptor）。
- **生成分支**：可选的输入图经 VQ 编码 → 主干 → image token → VQ 解码。`if image_seed else []` 用 0 表示"没有输入图"。
  - ⚠️ `demo_routing` 传入的 `image_seed = hash(p) % 1000` 几乎总是非零，于是纯文生图请求也会去编码一张不存在的图（而且编码结果随后被主干忽略）。
- **ambiguous 分支**：两路并行，结果打包成元组。
  - ⚠️ 语义错误：对"先画一只猫再描述它的品种"，应先生成、再把**生成出的像素**送进 SigLIP 理解；代码描述的却是同一个输入种子的图。
- `trace` 用字典累积各个字段，`input_len` 在不同分支里一会儿是 `int`、一会儿是 `str`——字典不做类型约束，读取方需要小心。
- ⚠️ 讲义 "Use It" 承诺的"image editing"示例和"stage 1 → stage 3 加权采样日程"在代码中都没有实现。

### 3.5 `demo_routing` 与不可复现的 `hash`

```python
    for p in prompts:
        trace = run_pipeline(p, image_seed=hash(p) % 1000)
```

- 5 个 prompt：2 个理解、2 个生成、1 个复合（"Sketch a cat and then describe its breed"，`sketch` 与 `describe` 各 1 分 → ambiguous）。
- ⚠️ Python 对字符串的 `hash()` 每个进程随机化（`PYTHONHASHSEED`），所以每次运行 VQ token 都不同——实测三次运行 sunset 的输出分别以 `[36, 204, ...]`、`[32, 153, ...]`、`[131, 15, ...]` 开头。需要稳定种子时用 `zlib.crc32(p.encode())` 或 `hashlib`。

### 3.6 `data_scale_table`：扩展的账本

```python
    rows = [
        ("stage 1 (alignment)",   "72M pairs",  "90M pairs",  "+25%"),
        ("stage 2 (unified)",     "26M pairs",  "72M pairs",  "+176%"),
        ("stage 3 (instruction)", "1.2M inst",  "1.4M inst",  "+17%"),
        ("model params",          "1.3B",       "7B",         "5.4x"),
        ("MMMU",                  "30.5",       "60.3",       "+29.8"),
        ("GenEval",               "0.61",       "0.80",       "+0.19"),
    ]
    print(f"  {'axis':<20}{'Janus':<14}{'Janus-Pro':<14}{'delta'}")
    for r in rows:
        print(f"  {r[0]:<20}{r[1]:<14}{r[2]:<14}{r[3]}")
```

- 增量都可以手算核对：`90/72 = 1.25`、`72/26 ≈ 2.77`、`1.4/1.2 ≈ 1.17`、`7/1.3 ≈ 5.38`，与表中的 `+25%`、`+176%`、`+17%`、`5.4x` 一致；阶段 3 的 +0.2M 对应讲义"Added 200k image-gen instruction samples"。
- 规律：**阶段 2（统一预训练）数据扩得最多**，配合 5.4 倍参数，是 Janus-Pro 成立的关键（讲义练习 5 要你读原文确认哪个阶段贡献最大）。
- ⚠️ `"stage 3 (instruction)"` 有 21 个字符，超过 `:<20` 的宽度，输出中这一行和下一列粘在一起（`stage 3 (instruction)1.2M inst`）。把宽度改成 24 即可。
- ⚠️ 表中 MMMU 60.3（以及讲义"LLaVA ~58"）与公开报告的量级差距较大，建议核对 Janus-Pro 原论文的理解基准表。

### 3.7 `main` 的架构一句话

```text
  input tower A (SigLIP)  ->
  input tower B (VQ)       -> shared transformer body ->
  output head 1 (text NTP) or output head 2 (VQ tokens)
  3 stages: alignment -> unified -> instruction tune
```

这四行是本节最值得背下的总结：**两个输入塔、一个共享主干、两个输出头、三阶段训练**。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 编码器/主干都用桩对象 | 只展示数据流，不涉及模型细节 | 看不到 MLP adaptor、生成 adaptor/head；真实实现是 SigLIP-SO400m + VQ + LLM |
| SigLIP 输出 float、VQ 输出 int | 用类型直观区分"语义特征"与"可重建码" | 维度与讲义（256）不一致 |
| 关键词子串路由 | 实现极简，对应练习 2 | 误判多；生产用显式标签/API 参数或学习式意图分类 |
| ambiguous 时两路并行 | 演示"两条路都能走" | 复合指令应按依赖顺序执行，而非并行 |
| `hash(p) % 1000` 作种子 | 每个 prompt 对应一张"图" | 跨进程不可复现；应用稳定哈希 |
| 编码器内 `random.seed` | 让同一图编码结果确定 | 污染全局随机状态；应使用独立 `random.Random` |
| 主干忽略输入 | 只关心输出类型 | prompt 文本没进主干，"统一序列"缺失 |
| 数据表硬编码 | 一眼看出扩展倍数 | 个别数字需核对原文；列宽不足导致错位 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 方法 | `class VQStub: vocab: int = 256 ... def encode(self, ...)` | dataclass 也可以定义普通方法 |
| 字段默认值 | `dim: int = 32`、`name: str = "DeepSeek-7B-init"` | 不传参数就用默认值，`SiglipStub()` 即可构造 |
| 返回类型注解 | `-> list[float]`、`-> list[int]`、`-> dict` | 用类型表达"连续特征 vs 离散码" |
| `random.seed` / `gauss` / `randint` | `random.seed(image_seed)` | 设定全局种子 / 正态 / 闭区间整数；注意全局副作用 |
| 列表推导式 | `[f"word_{i}" for i in range(4)]` | 生成 `['word_0', ..., 'word_3']` |
| 切片 | `tokens[:4]` | 只取前 4 个用于打印 |
| `str.lower` + `in` | `p = prompt.lower()`、`k in p` | 大小写归一 + 子串判断（不看词边界） |
| 生成器计数 | `sum(1 for k in u_keywords if k in p)` | 统计命中数 |
| 条件表达式 | `vq.encode(image_seed) if image_seed else []` | 0、空值为假；用 0 表示"无图"是脆弱约定 |
| 字典累积字段 | `trace["route"] = ...`、`trace["output"] = ...` | 动态添加键 |
| 元组作为值 | `trace["output"] = (text, image_desc)` | 一次返回两种结果 |
| 内置 `hash` | `hash(p) % 1000` | 字符串哈希每个进程随机化，不可用于可复现种子 |
| 多行列表字面量 | `rows = [("stage 1 ...", "72M pairs", ...), ...]` | 元组列表做表格数据 |
| f-string 对齐 | `{r[0]:<20}`、`{'axis':<20}` | 左对齐固定宽度；内容超宽时不会截断，会挤到下一列 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16）。注意 VQ token 每次运行都不同（`hash` 随机化），以下是其中一次：

```text
  prompt  : Describe what's in this image
  task    : understand                      ← describe + what = 2 : 0
  route   : SigLIP -> shared body -> text
  output  : ['word_0', 'word_1', 'word_2', 'word_3']

  prompt  : Generate a picture of a sunset over the ocean
  task    : generate
  route   : (optional VQ) -> shared body -> image VQ -> decoder
  output  : VQ-decoded image from tokens [208, 209, 137, 120]...   ← 每次运行不同

  prompt  : Sketch a cat and then describe its breed
  task    : ambiguous                       ← sketch 1 : describe 1
  route   : ambiguous: run both and merge
  output  : (['word_0', ...], 'VQ-decoded image from tokens [242, 22, 226, 46]...')

  prompt  : What is the pose of the person in the image?
  task    : understand
  ...
  prompt  : Render a cyberpunk cityscape at night
  task    : generate

DATA SCALING: Janus vs Janus-Pro
  axis                Janus         Janus-Pro     delta
  stage 1 (alignment) 72M pairs     90M pairs     +25%
  stage 2 (unified)   26M pairs     72M pairs     +176%
  stage 3 (instruction)1.2M inst     1.4M inst     +17%     ← 列宽不足导致错位
  model params        1.3B          7B            5.4x
  MMMU                30.5          60.3          +29.8
  GenEval             0.61          0.80          +0.19
```

逐项解读：

- **5 个 prompt 的路由都"判对了"**，但这是因为 demo 的措辞刚好避开了子串陷阱；换一种说法（见 3.3）就会出错。
- **理解输出永远是 `word_0..3`**：主干桩不看输入，所以不同图片、不同问题得到同样的"回答"——这里只演示路径。
- **生成输出的 token** 由 `hash` 决定的种子驱动，跨运行不可复现。
- **ambiguous** 返回 (文本, 图像) 元组，体现了"并行两路"的设计，但语义上应是"先生成后理解"的串行流程。
- **数据表**：阶段 2 数据 +176%、参数 5.4 倍是两项最大的扩展；GenEval 0.61 → 0.80。

---

## 7. 动手改一改

1. **修复可复现性**：把 `hash(p) % 1000` 换成 `zlib.crc32(p.encode()) % 1000`；把两个 `encode` 改为 `rng = random.Random(seed)`，`SharedBody` 也持有自己的 `rng`。连续运行两次确认输出完全一致。
2. **（练习 2）更稳健的路由**：用 `re.search(r"\bdraw\b", p)` 做词边界匹配，并加入 `edit` 类（`make|change|remove|add` + 有输入图）；用测验 Q9 的 5 个句子做回归测试。
3. **让 prompt 进入主干**：给 `SharedBody.process` 增加 `text_tokens` 参数，让文本输出至少依赖 prompt（例如回显 prompt 中的名词），体会"统一序列"。
4. **实现 edit 分支（对应讲义承诺的第 3 个示例）**：SigLIP(源图) + 指令文本 + VQ(源图) → 主干 → 新 VQ token → 解码（参考测验 Q12）。
5. **复合指令串行化**：把 ambiguous 分支改成"先生成 → 用生成结果的种子做 SigLIP 编码 → 再理解"，并在 trace 中记录两步。
6. **（练习 4）加第三个编码器**：新增 `DepthStub`（输出 `list[float]` 深度图），并为"估计这张图的深度"设计路由与输出头，思考共享主干要承担什么。

---

## 8. 常见坑

- **子串匹配当意图识别**：`paint` ⊂ `painting`、`draw` ⊂ `withdraw`，关键词路由在真实流量下很快失效。
- **用内置 `hash()` 生成种子**：字符串哈希每次启动都不同，结果不可复现。
- **在组件内部调用 `random.seed`**：重置全局随机状态，悄悄改变其他组件的行为。
- **忘记把文本条件送进主干**：没有 prompt 的"文生图"没有意义。
- **把复合指令并行化**：有数据依赖的步骤（先画后描述）必须串行。
- **用 VQ token 直接做理解**：VQ 语义弱，这正是解耦的理由；理解应走 SigLIP（必要时先把生成结果解码成像素）。
- **f-string 宽度不够**：`:<20` 不会截断超长内容，会导致列错位。
- **把 GenEval 当成"画质全面超越"**：它主要测组合正确性，不衡量美学与细节。
