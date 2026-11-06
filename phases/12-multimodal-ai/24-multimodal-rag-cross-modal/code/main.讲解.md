# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 24 节 多模态 RAG 与跨模态检索 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），无需网络、GPU 或模型权重

---

## 1. 这份代码在考察什么

这份约 170 行的脚本把讲义里的"旅行规划"例子（"找一家安静、有自然光的素食早午餐"）做成一个可运行的玩具：

1. **按模态拆分检索**：文本（评论关键词）、图像（照片标签）、音频（环境分贝）三个检索器各自给 5 家餐厅打分。
2. **Score fusion**：三路分数按权重加权求和，得到每家餐厅的综合分。
3. **Grounded generation 的雏形**：输出 top-3 时附上评论 id、图像标签、分贝值作为"证据"。
4. **Agentic 改写**：首轮置信度低于阈值时改写查询、调整权重再检索一次。

> 一句话：**把"查询分解 → 分模态检索 → 融合 → 带证据回答 → 低置信时重试"这条多模态 RAG 流水线压缩成几个纯函数**。它的价值同样在于暴露陷阱：子串匹配误报、缺少模态内归一化、"只调权重就让置信度上升"的伪 agentic 循环。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Restaurant` | dataclass | id、名称、评论文本、图像标签、环境分贝 | 多模态知识库中的一条记录 |
| `CORPUS` | 模块级常量 | 5 家餐厅 | 多模态知识库 |
| `text_retrieve` | 函数 | 查询关键词在评论中的子串计数 / 关键词数 | 文本检索头 |
| `image_retrieve` | 函数 | 查询词 → 标签提示 → 命中比例 | 图像检索头（用标签模拟 CLIP） |
| `audio_retrieve` | 函数 | 含 quiet/calm 时 `1 − dB/80`，否则全给 0.5 | 音频检索头（用分贝模拟 CLAP） |
| `fuse` | 函数 | 按权重对三路分数求和 | Score fusion |
| `top_k` | 函数 | 按分数降序取前 k | 排序 |
| `grounded_generate` | 函数 | 拼接 top-k 的名称、分数和证据 | Grounded generation（模板） |
| `agentic_loop` | 函数 | 首轮检索 + 融合；低于阈值时改写再来一轮 | Agentic multi-hop |
| `surveys_table` | 函数 | 打印 2025 年三篇综述 | 文献 |
| `main` | 函数 | 运行示例查询，打印综述与融合策略说明 | 演示入口 |

数据流：`main` → `agentic_loop(query, 0.7)` → [`text_retrieve`、`image_retrieve`、`audio_retrieve`] → `fuse` → `top_k` →（若低置信：`image_retrieve(query2)`、`audio_retrieve(query2)` → `fuse`(新权重) → `top_k`）→ `grounded_generate` → 打印。

---

## 3. 逐段精讲

### 3.1 知识库：一条记录 = 多个模态的特征

```python
@dataclass
class Restaurant:
    id: str
    name: str
    review_text: str
    image_tags: list[str]
    ambient_db: float


CORPUS = [
    Restaurant("r1", "Sunday Plant Bistro",
               "best vegan brunch, quiet mornings, lots of windows", ["natural_light", "minimal"], 38),
    Restaurant("r2", "Orange Grove Cafe",
               "all-day vegan brunch, noisy music, industrial style", ["industrial"], 68),
    Restaurant("r3", "Vine & Leaf",
               "vegan lunch, dim lighting", ["warm_lighting"], 55),
    Restaurant("r4", "Morning Glow",
               "vegan brunch, airy space, lots of sun", ["natural_light", "airy"], 42),
    Restaurant("r5", "Steak Central",
               "steakhouse, loud atmosphere", ["dark"], 72),
]
```

- 三个字段分别代表三种模态的**已提取特征**：`review_text`（文本）、`image_tags`（图像经分类器/VLM 打的标签）、`ambient_db`（音频片段测得的分贝）。真实系统存的是 embedding（CLIP 图像向量、CLAP 音频向量），这里用可读的符号代替。
- 数据是精心设计的：r1 与 r4 都是"素食早午餐 + 自然光"，只在分贝（38 vs 42）上有差别；r3 的 "dim lighting" 是语义相反的干扰项；r5 是完全不相关的牛排馆。
- `ambient_db` 注解为 `float`，但传入的是整数 38、68……Python 不做运行时检查，这完全合法。

### 3.2 `text_retrieve`：关键词子串计数

```python
def text_retrieve(query: str) -> dict[str, float]:
    keywords = [w.lower() for w in query.split() if len(w) > 2]
    scores = {}
    for r in CORPUS:
        text = r.review_text.lower()
        s = sum(text.count(k) for k in keywords)
        scores[r.id] = s / len(keywords) if keywords else 0
    return scores
```

- 示例查询的 `keywords` 是 `['find', 'quiet', 'vegan', 'brunch', 'with', 'natural', 'light']`，共 7 个。
- 每家餐厅的分数 = 关键词在评论中出现的总次数 / 7。结果：r1 `3/7 = 0.4286`（quiet、vegan、brunch），r2/r3/r4 都是 `2/7 = 0.2857`，r5 为 0。
- ⚠️ `str.count` 是**子串**计数：r3 的 "dim lighting" 命中了 "light"，与 r4 同分。用户要自然光，昏暗灯光反而加分。
- ⚠️ "find"、"with" 是停用词，"natural" 在所有评论里都不存在，它们只增大分母；标点也没处理。
- 改进版（按词匹配 + 停用词表）见测验 Q9：r1 0.6、r2 0.4、r3 0.2、r4 0.4、r5 0。

### 3.3 `image_retrieve`：查询词 → 标签

```python
def image_retrieve(query: str) -> dict[str, float]:
    q = query.lower()
    tag_hints = []
    if "light" in q or "sun" in q:
        tag_hints.append("natural_light")
    if "airy" in q or "spacious" in q:
        tag_hints.append("airy")
    if "minimal" in q:
        tag_hints.append("minimal")
    scores = {}
    for r in CORPUS:
        s = sum(1.0 for t in tag_hints if t in r.image_tags)
        scores[r.id] = s / max(1, len(tag_hints))
    return scores
```

- 用硬编码规则把查询映射到视觉标签，模拟"文本查询 → 共享空间 → 图像"的跨模态检索。示例查询只触发 `natural_light`，于是 r1、r4 得 1.0，其余 0.0。
- `max(1, len(tag_hints))` 防止没有提示词时除以 0。
- 只有 0 和 1 两个取值（一个提示时），分布极不连续——在融合时它会主导结果（见 3.5）。
- 规则只认识 light/sun/airy/spacious/minimal，所以第二轮追加的 "bright windows" 对它没有任何作用。
- 真实做法：用 CLIP/SigLIP 2 把查询文本和餐厅照片编码到同一空间，算余弦（讲义"Shared embedding space"）。

### 3.4 `audio_retrieve`：分贝 → 安静度

```python
def audio_retrieve(query: str) -> dict[str, float]:
    q = query.lower()
    scores = {}
    if "quiet" in q or "calm" in q:
        for r in CORPUS:
            scores[r.id] = max(0.0, 1.0 - r.ambient_db / 80.0)
    else:
        for r in CORPUS:
            scores[r.id] = 0.5
    return scores
```

- 查询要求安静时，把分贝线性映射为 `1 − dB/80`：38 dB → 0.525，42 → 0.475，55 → 0.3125，68 → 0.15，72 → 0.1。`max(0.0, ...)` 让 80 dB 以上截断为 0。
- 注意 38 dB 也只有 0.525，所以音频通道的上限远低于图像通道的 1.0。
- ⚠️ 没有安静需求时，所有餐厅都给常数 0.5。常数不影响排序，但会把融合分整体抬高 `0.3 × 0.5 = 0.15`，而代码恰恰用融合分的绝对值当"置信度"（测验 Q7）。更合理的是让这一路不参与融合（权重 0）。
- 同样只认 quiet/calm，"low noise" 不起作用。

### 3.5 `fuse` 与 `top_k`：加权求和与排序

```python
def fuse(scores_list: list[dict[str, float]], weights: list[float]) -> dict[str, float]:
    fused = {}
    for r in CORPUS:
        s = 0.0
        for w, scores in zip(weights, scores_list):
            s += w * scores.get(r.id, 0)
        fused[r.id] = s
    return fused


def top_k(scored: dict[str, float], k: int = 3) -> list[tuple[str, float]]:
    return sorted(scored.items(), key=lambda x: -x[1])[:k]
```

- `zip(weights, scores_list)` 把权重和对应模态的分数字典配对；`scores.get(r.id, 0)` 让缺失的条目按 0 处理（一个检索器没返回某餐厅时不至于报错）。
- 第一轮权重 `[0.3, 0.4, 0.3]` 的结果：

| 餐厅 | 文本 | 图像 | 音频 | 融合 |
|------|------|------|------|------|
| r1 | 0.4286 | 1.0 | 0.525 | **0.6861** |
| r4 | 0.2857 | 1.0 | 0.475 | 0.6282 |
| r3 | 0.2857 | 0.0 | 0.3125 | 0.1795 |
| r2 | 0.2857 | 0.0 | 0.15 | 0.1307 |
| r5 | 0.0 | 0.0 | 0.1 | 0.0300 |

- ⚠️ **没有模态内归一化**。讲义原话是 "Normalize scores within-modality then sum"，代码省略了这一步。三路取值范围不同（文本 0–0.43、图像 0/1、音频 0.1–0.525），图像通道的 0/1 跳变贡献 0.4，远大于其它通道能产生的差距，名义权重并不代表真实影响力。min-max 归一化后排序为 r1 1.000 > r4 0.865 > r3 0.350 > r2 0.235 > r5 0（测验 Q10）。
- `top_k` 对字典的 `(id, 分数)` 对按分数降序排序后切片；`sorted` 是稳定排序，分数并列时保持 `CORPUS` 中的顺序——这决定了并列时谁排前面。

### 3.6 `grounded_generate`：带证据的输出（模板）

```python
def grounded_generate(query: str, ranked: list[tuple[str, float]]) -> str:
    lines = [f"Answer for: '{query}'"]
    for i, (rid, score) in enumerate(ranked, 1):
        r = next(x for x in CORPUS if x.id == rid)
        lines.append(
            f"  {i}. {r.name} (score {score:.2f})"
            f" [review {rid}] [img tags {r.image_tags}] [ambient {r.ambient_db}dB]")
    return "\n".join(lines)
```

- `enumerate(ranked, 1)` 从 1 开始编号；`next(生成器)` 取第一个满足条件的餐厅（线性查找，5 条无所谓，大规模应建 `id → Restaurant` 字典）。
- 每一行附带三类"来源"：评论 id、图像标签、分贝，对应讲义的跨模态引用格式（`[1]`、`[img 3]`、`[audio 2 at 0:34]`）。
- ⚠️ 这不是生成，也不是**结论级**引用：没有任何一句"这家很安静 [audio r1]"式的断言与来源绑定；它甚至给 r3 也附上 `[review r3]`，尽管那条评论与用户需求相悖。讲义说真正的 grounding 需要用"每个结论都带来源标签"的数据训练生成器。

### 3.7 `agentic_loop`：低置信时"改写"

```python
def agentic_loop(query: str, confidence_floor: float = 0.8) -> str:
    t = text_retrieve(query)
    i = image_retrieve(query)
    a = audio_retrieve(query)
    fused = fuse([t, i, a], [0.3, 0.4, 0.3])
    top = top_k(fused, k=3)
    confidence = top[0][1] if top else 0

    trace = [f"round 1: top={top[0]}  confidence={confidence:.2f}"]
    if confidence < confidence_floor:
        trace.append("  confidence low; reformulating query")
        query2 = query + " bright windows low noise"
        i2 = image_retrieve(query2)
        a2 = audio_retrieve(query2)
        fused = fuse([t, i2, a2], [0.3, 0.5, 0.2])
        top = top_k(fused, k=3)
        trace.append(f"round 2: top={top[0]}  confidence={top[0][1]:.2f}")
    return "\n".join(trace) + "\n\n" + grounded_generate(query, top)
```

讲义描述的 agentic multi-hop 是"首轮置信度低 → LLM 改写查询 → 再检索"。这段代码在形式上做到了，但实质上：

- ⚠️ **新查询没有带来任何新证据**：`i2` 与 `i` 完全相同（"bright windows" 不触发任何标签规则），`a2` 与 `a` 完全相同（"low noise" 不触发 quiet/calm），文本检索干脆没有用 `query2` 重跑，仍用第一轮的 `t`。
- ⚠️ **置信度上升完全来自换权重**：`[0.3, 0.5, 0.2]` 把权重挪给 r1 拿满分的图像通道，于是 `0.3 × 0.4286 + 0.5 × 1.0 + 0.2 × 0.525 = 0.7336`，越过了 0.7 的阈值。这是"调阈值让自己通过"，而不是"找到了更多证据"。
- ⚠️ **置信度定义**：用融合分绝对值，受权重、常数通道（3.4）影响，不可比较；更合理的是 top-1 与 top-2 的差距（r1 vs r4 只差 0.058）或校准后的概率。
- ⚠️ **没有兜底**：第二轮仍不够时也照常输出；`top` 为空时 `top[0]` 会 `IndexError`（`if top else 0` 只保护了 `confidence`）。
- `confidence_floor` 默认 0.8，但 `main` 传入 0.7；`round 1: top=('r1', 0.6860714285714286)` 直接打印了元组，浮点数没有格式化。
- 改进版（每轮重跑三路检索 + 归一化 + margin 置信度 + 最多 3 轮 + 低置信标记）见测验 Q11。改进后两个示例查询都被如实标记为低置信，因为 r1 和 r4 本来就难分高下；还暴露了"追加 sun 让 top-1 变成 r4"的查询漂移。

### 3.8 `surveys_table` 与 `main`

```python
    rows = [
        ("Abootorabi et al.", "Feb 2025", "comprehensive taxonomy"),
        ("Mei et al.",        "Apr 2025", "sub-task benchmarks + failure modes"),
        ("Zhao et al.",       "Mar 2025", "vision-focused, strong on ColPali"),
    ]
```

- 日期与 arXiv 编号一致：2502.08826（2025 年 2 月）、2504.08748（4 月）、2503.18016（3 月）。
- `main` 最后打印的四行融合策略说明与讲义一致，"default: score fusion + slight bias toward dominant modality"——但代码的融合本身并没有实现"按查询主导模态倾斜"，权重是写死的。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用符号特征（标签、分贝）代替 embedding | 无需模型，人眼可读 | 只能命中规则覆盖的词；生产用 CLIP/SigLIP 2、CLAP 或 VLM 表示 |
| 文本检索用子串计数 | 一行实现 | "lighting" 误配 "light"、停用词稀释；应改为 BM25 或文本 embedding |
| 无安静需求时音频返回 0.5 | 避免空字典 | 常数抬高"置信度"；应让该通道不参与融合 |
| 直接加权求和、不归一化 | 简单 | 违背讲义"先模态内归一化"；取值范围大的通道主导 |
| 权重写死 | 便于演示 | 不随查询变化；skill 文件指出权重不能跨领域迁移，需按领域调参或训练 MoE |
| 融合分绝对值当置信度 | 直观 | 受权重和常数影响，不可校准；用 margin 或校准分数 |
| 第二轮只改权重、不重跑文本检索 | 代码短 | 置信度"自我说服"；应每轮重跑全部检索并验证结果确实变化 |
| 模板拼接代替生成 | 无需 LLM | 没有结论级引用；生产用 VLM 生成并强制每个结论带来源 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 位置参数构造 | `Restaurant("r1", "Sunday Plant Bistro", ...)` | 按字段定义顺序传参 |
| 类型注解 | `dict[str, float]`、`list[tuple[str, float]]` | 描述返回的"id → 分数"字典、"(id, 分数) 列表" |
| 带条件的列表推导式 | `[w.lower() for w in query.split() if len(w) > 2]` | 过滤 + 变换一步完成 |
| `str.split()` | `query.split()` | 按任意空白切分，不处理标点 |
| `str.count` | `text.count(k)` | 统计**子串**出现次数（不是按词） |
| `in` 用于字符串和列表 | `"light" in q`、`t in r.image_tags` | 前者是子串判断，后者是成员判断 |
| 条件表达式 | `s / len(keywords) if keywords else 0` | 三元表达式，避免除以 0 |
| `max(1, n)` / `max(0.0, x)` | `s / max(1, len(tag_hints))` | 下限保护 |
| `sum` + 生成器 | `sum(1.0 for t in tag_hints if t in r.image_tags)` | 计数命中的标签 |
| `dict.get(key, default)` | `scores.get(r.id, 0)` | 缺失键返回默认值 |
| `zip` | `zip(weights, scores_list)` | 权重和分数配对 |
| `dict.items()` + `sorted` + 切片 | `sorted(scored.items(), key=lambda x: -x[1])[:k]` | 字典转成键值对列表后按值降序排序取前 k |
| `enumerate(seq, 1)` | `for i, (rid, score) in enumerate(ranked, 1)` | 从 1 开始编号；嵌套元组解包 |
| `next(生成器)` | `next(x for x in CORPUS if x.id == rid)` | 取第一个匹配项；找不到会抛 `StopIteration` |
| 相邻字符串字面量拼接 | `f"  {i}. ..." f" [review {rid}] ..."` | 括号内相邻的字符串自动拼成一个 |
| `"\n".join(list)` | `"\n".join(lines)` | 用换行连接多行文本 |
| f-string 中直接放列表/元组 | `{r.image_tags}`、`top={top[0]}` | 调用 `str()`，打印出 `['natural_light', 'minimal']`、`('r1', 0.686...)` |
| 默认参数 | `def agentic_loop(query, confidence_floor: float = 0.8)` | 调用方可覆盖（`main` 传 0.7） |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，瞬时完成）：

```text
QUERY: find me a quiet vegan brunch with natural light
------------------------------------------------------------
round 1: top=('r1', 0.6860714285714286)  confidence=0.69    ← 0.3×0.4286 + 0.4×1.0 + 0.3×0.525
  confidence low; reformulating query                        ← 0.686 < 0.7
round 2: top=('r1', 0.7335714285714285)  confidence=0.73    ← 三路分数都没变，只是权重改成 0.3/0.5/0.2

Answer for: 'find me a quiet vegan brunch with natural light'
  1. Sunday Plant Bistro (score 0.73) [review r1] [img tags ['natural_light', 'minimal']] [ambient 38dB]
  2. Morning Glow (score 0.68) [review r4] [img tags ['natural_light', 'airy']] [ambient 42dB]
  3. Vine & Leaf (score 0.15) [review r3] [img tags ['warm_lighting']] [ambient 55dB]   ← 靠 "lighting" 误配拿到文本分

2025 MULTIMODAL RAG SURVEYS
------------------------------------------------------------
  Abootorabi et al.     Feb 2025  comprehensive taxonomy
  Mei et al.            Apr 2025  sub-task benchmarks + failure modes
  Zhao et al.           Mar 2025  vision-focused, strong on ColPali

FUSION STRATEGIES
------------------------------------------------------------
  score fusion : weighted sum, simple, fast
  MoE fusion   : gating routes to experts, learnable, trains
  attention    : small network weights retrieved items
  default: score fusion + slight bias toward dominant modality
```

逐项解读：

- **最终排序 r1 > r4 > r3** 本身是合理的：r1 最安静（38 dB）、评论里有 "quiet"、有自然光。但 r1 与 r4 的差距（0.733 vs 0.681）主要来自文本里一个 "quiet" 和 4 dB 的分贝差。
- **第二轮的 0.73** 不代表系统"更确定了"：已逐一验证 `image_retrieve(query2) == image_retrieve(query)`、`audio_retrieve(query2) == audio_retrieve(query)`，文本检索未重跑。若真用 `query2` 重跑文本检索，r1 的文本分反而会从 0.4286 降到 0.3636（关键词从 7 个变成 11 个，只多命中一个 "windows"）。
- **第 3 名 Vine & Leaf**：第二轮融合分 `0.3 × 0.2857 + 0 + 0.2 × 0.3125 = 0.148`。它的文本分有一半来自 "lighting" 对 "light" 的误配；它排在 r2 前面主要是因为 55 dB 比 68 dB 安静。
- **对照实验**：把查询换成 `"vegan brunch with natural light"`（无 "quiet"），音频通道变成常数 0.5，第二轮 r1 与 r4 并列 0.72——唯一能区分两家的安静信号消失了，排序由 `CORPUS` 顺序决定（测验 Q7）。

---

## 7. 动手改一改

1. **修文本检索**：用正则分词 + 停用词表实现按词匹配（测验 Q9），确认 r3 不再因为 "lighting" 得分；再进一步换成简化版 BM25。
2. **模态内归一化**：实现 `minmax` 并在 `fuse` 之前调用，对比归一化前后的排序（参考：r1 1.000 > r4 0.865 > r3 0.350 > r2 0.235 > r5 0）；再实现 RRF，观察并列对名次的影响。
3. **按查询选择模态**：写 `route_weights(query)`：查询没有安静需求时音频权重为 0，没有视觉需求时图像权重为 0，其余权重重新归一化——这是 MoE 门控的"规则版"。
4. **诚实的 agentic 循环**：实现测验 Q11 的 `agentic_loop_v2`（每轮重跑三路检索、margin 置信度、最多 3 轮、低置信标记），并在 trace 中记录每轮查询与 top-1，观察查询漂移。
5. **结论级引用**：把 `grounded_generate` 改成对每个约束输出一句断言并绑定来源，例如 `"环境安静（38 dB）[audio r1]"`、`"有自然光 [img r1: natural_light]"`、`"提供素食早午餐 [review r1]"`；某个约束没有证据时明确写"无证据"。
6. **评估脚本**：为 5 个查询人工标注"满足全部约束的餐厅集合"，计算各模态 Recall@k、融合后 Precision@1 和约束满足率（讲义练习 4）。

---

## 8. 常见坑

- **子串匹配当关键词匹配**：`"light" in "lighting"`、`"sun" in "sunday"` 都为真，误报会悄悄进入排序。
- **不归一化就加权**：名义权重 0.3/0.4/0.3 并不代表各模态的真实影响力；取值范围最大的通道说了算。
- **常数通道**：给"无关模态"填常数看似无害，却会抬高所有分数，污染任何基于绝对分数的阈值。
- **调权重冒充重新检索**：agentic 循环必须真的拿到新证据；改写后应检查检索结果是否变化。
- **用融合分绝对值当置信度**：不同权重、不同查询下不可比；用 top-1/top-2 差距或校准分数。
- **查询改写引入新约束**：追加用户没说过的词（如 "sun"、"airy"）会改变 top-1，属于查询漂移。
- **把附带 id 当作 grounding**：真正的 grounding 是"每个结论 ↔ 支持它的来源"，而不是在每一行后面贴一串元数据。
- **`next()` 找不到时抛 `StopIteration`**：生产代码应给默认值 `next(gen, None)` 或使用字典索引。
