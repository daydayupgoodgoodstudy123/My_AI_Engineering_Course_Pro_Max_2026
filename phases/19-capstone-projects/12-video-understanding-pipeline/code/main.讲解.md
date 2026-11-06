# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 12 节 综合项目 12：视频理解流程——场景、问答与搜索 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`re`、`collections`、`dataclasses`），无需 GPU、无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义描述的是一个完整的生产系统：TransNetV2 切场景、Gemini/Qwen-VL 写字幕、Whisper 出词级时间戳、Qdrant 存三种向量、TimeLens 做时间 grounding、Gemini 合成带引用的答案。这份 `main.py` 只是一个**骨架（scaffold）**，它的 docstring 说得很清楚：

> "The hard architectural primitive is a multi-vector-per-scene index with three representations (caption, frame, transcript), queried in parallel and merged with reciprocal rank fusion, then refined by a temporal-grounding step..."

它考察三件事：

1. **Multi-vector 场景记录**：一个场景同时持有 caption、frame、transcript 三种表示及其 embedding（讲义"Multi-vector index"）。
2. **三路检索 + RRF 融合**：同一个 query 分别对三种向量排名，再用 reciprocal rank fusion 合并（讲义"RRF fusion"）。
3. **场景内时间 grounding**：在 top 场景内部收窄 `(start, end)` 子窗口（讲义"Temporal grounding"）。

没有实现的部分：真正的 embedding 模型、场景切分、ASR、VLM 合成、评测（IoU、按题型准确率）。

> 一句话：**用 150 行标准库代码把"一个场景三个向量 → 三路排名 → RRF → 场景内收窄窗口"这条检索主干跑通**；但它的假 embedding 不稳定、grounding 被停用词驱动，读代码时要分清哪些是结构、哪些只是占位。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `EMB_DIM = 24` | 常量 | 假 embedding 的维度 | 向量维度 |
| `tokenize` | 函数 | 正则 `\w+` 小写切词 | 文本预处理 |
| `fake_embed` | 函数 | 哈希词袋 + L2 归一化，代替真实 embedding 模型 | Embedding（占位） |
| `cosine` | 函数 | 点积（输入已归一化） | 相似度 |
| `Scene` | dataclass | 一个场景：时间范围 + 三种文本 + 三个向量 | Multi-vector 场景记录 |
| `Scene.embed` | 方法 | 为三种表示各算一个向量 | 写入 multi-vector 索引 |
| `SAMPLE` | 列表常量 | 2 个视频共 6 个场景（东京日出、路口、红灯、厨房、摆盘、海边） | 测试语料 |
| `multi_vector_search` | 函数 | 三路排序 → RRF 融合 → 返回 top-k | 三路检索 + RRF |
| `ground_window` | 函数 | 按 transcript 命中词位置线性映射出子窗口 | Temporal grounding（stub） |
| `fmt_ms` | 函数 | 毫秒 → `MM:SS` | 时间戳展示 |
| `main` | 函数 | 嵌入全部场景，跑 4 个 query，打印 top-3 与 grounding 窗口 | 演示 |

数据流：`SAMPLE` → `Scene.embed()`（每场景 3 个向量）→ `multi_vector_search(query)`（3 个排名 → RRF → top-3）→ `ground_window(query, top1)` → 打印 `[MM:SS-MM:SS]`。

---

## 3. 逐段精讲

### 3.1 切词与假 embedding

```python
def tokenize(s: str) -> list[str]:
    return re.findall(r"\w+", s.lower())


def fake_embed(text: str) -> list[float]:
    v = [0.0] * EMB_DIM
    for tok in tokenize(text):
        h = hash(tok)
        v[h % EMB_DIM] += 1.0
        v[(h >> 8) % EMB_DIM] += 0.5
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]
```

- `re.findall(r"\w+", ...)`：取出所有"字母/数字/下划线"连续片段，`"sunrise over skyline, drone footage"` → `['sunrise', 'over', 'skyline', 'drone', 'footage']`。
- **哈希词袋（feature hashing）**：每个词用 `hash()` 映射到两个桶，主桶 +1.0、副桶（`h >> 8` 右移 8 位后取模）+0.5，最后 L2 归一化成单位向量。两个桶是为了减少"两个词完全撞在一起"的概率。
- `or 1.0`：空文本时范数为 0，用 1.0 避免除零。
- 它**没有任何语义**：只有字面完全相同的词才会产生相似度，`cars` 与 `vehicles`、`pour` 与 `pouring` 互不相关。
- ⚠️ **不可复现**：Python 对 `str` 的 `hash()` 在每个进程启动时随机加盐（`PYTHONHASHSEED`），所以每次运行时词 → 桶的映射都不同。24 维又很小，不相关的词经常撞进同一个桶。实测 `PYTHONHASHSEED=0..199` 共 200 次：数车问题的 top-1 只有 77 次是"红灯前的车"（vid_001/2），35 次是路口场景，其余 88 次落在厨房、海浪、日出等无关场景。修复见测验 Q10（改用 `hashlib`）。
- ⚠️ 文件 `import random` 但从未使用。

```python
def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
```

- 因为 `fake_embed` 输出已经归一化，cosine = 点积。若换成未归一化的真实 embedding，这里必须除以两个向量的范数。

### 3.2 `Scene`：一个场景三个向量

```python
@dataclass
class Scene:
    video_id: str
    scene_id: int
    start_ms: int
    end_ms: int
    caption: str
    transcript: str
    frame_tags: str              # stand-in for frame embedding features
    caption_emb: list[float] = field(default_factory=list)
    frame_emb: list[float] = field(default_factory=list)
    transcript_emb: list[float] = field(default_factory=list)

    def embed(self) -> None:
        self.caption_emb = fake_embed(self.caption)
        self.frame_emb = fake_embed(self.frame_tags)
        self.transcript_emb = fake_embed(self.transcript)
```

- 前 4 个字段对应讲义的 payload `{video_id, scene_id, start_ms, end_ms}`（少了 `keyframe_url`）。
- `caption` = VLM 字幕，`transcript` = 该场景的 ASR 切片，`frame_tags` 用一串标签词**模拟**关键帧的视觉特征——真实系统里这里是图像 embedding（如 CLIP 类模型对关键帧编码），不经过文本。
- 三个 `*_emb` 字段对应 Qdrant 的三个 named vectors。讲义示例 "69 vectors written (23 scenes x 3)"；本文件 6 个场景对应 18 个向量。
- `field(default_factory=list)`：可变默认值必须用工厂函数，否则所有实例会共享同一个列表（见第 5 节）。

`SAMPLE` 有 6 个场景，时间用 `32_000` 这样的下划线数字字面量（= 32000 ms）。注意设计意图：scene 2 的 transcript 是 "let me count the vehicles approaching"、scene 3 是 "first we pour then we stir it slowly"——对应讲义的两类难题：**计数**与**动作顺序**。

### 3.3 三路检索 + RRF

```python
def multi_vector_search(query: str, scenes: list[Scene], k: int = 5) -> list[tuple[Scene, float]]:
    qv = fake_embed(query)
    scored_caption = sorted(scenes, key=lambda s: -cosine(qv, s.caption_emb))
    scored_frame = sorted(scenes, key=lambda s: -cosine(qv, s.frame_emb))
    scored_transcript = sorted(scenes, key=lambda s: -cosine(qv, s.transcript_emb))

    fused: dict[tuple[str, int], float] = defaultdict(float)
    index: dict[tuple[str, int], Scene] = {}
    for ranks, stream in ((scored_caption, "cap"),
                          (scored_frame, "frm"),
                          (scored_transcript, "trn")):
        for rank, sc in enumerate(ranks):
            key = (sc.video_id, sc.scene_id)
            fused[key] += 1.0 / (60 + rank + 1)
            index[key] = sc

    ranked = sorted(fused.items(), key=lambda x: -x[1])
    return [(index[k_], s) for k_, s in ranked[:k]]
```

- **三路排名**：同一个 query 向量分别与三种场景向量比较，`key=lambda s: -cosine(...)` 用取负实现降序。
- **RRF 公式**：`score(d) = Σ_路 1 / (k + rank_路(d))`，这里 k = 60，`rank` 从 0 开始所以写 `60 + rank + 1`。第 1 名贡献 `1/61 ≈ 0.01639`，第 6 名 `1/66 ≈ 0.01515`。
- **为什么用 RRF**：三种表示的 cosine 分布不同，直接相加会被某一路主导；RRF 只看名次，与分数尺度无关。
- 场景主键用元组 `(video_id, scene_id)`，因为 `scene_id` 只在同一视频内唯一（vid_001/0 与 vid_002/0 都是 0）。
- `index` 保存 key → `Scene` 对象，每路都会重复赋值，无害。
- `stream` 变量（"cap"/"frm"/"trn"）从未使用，只起注释作用。
- ⚠️ **分数挤压**：每路都对**全部**场景排名，最差也有 `1/66`，因此融合分数只能在 `3/66 ≈ 0.0455` ～ `3/61 ≈ 0.0492` 之间，打印出来区分度很低。生产中每路只取 top-N（如 50～100）参与融合，其余记 0。
- ⚠️ **并列偏差**：很多场景与 query 的 cosine 为 0（无共享词），`sorted` 是稳定排序，并列者保持 `SAMPLE` 原序，排在前面的 vid_001/0（日出）在每一路都"白拿"较好名次。这解释了运行结果中日出场景频繁出现在 top-3。
- 参数 `k` 与 RRF 常数 60 同名不同义；返回时用 `k_` 作循环变量就是为了避免遮蔽参数 `k`。

### 3.4 时间 grounding stub

```python
def ground_window(query: str, scene: Scene) -> tuple[int, int]:
    """Stand-in: pick a sub-window of the scene based on query keyword position."""
    q = set(tokenize(query))
    t_tokens = tokenize(scene.transcript)
    if not q or not t_tokens:
        return scene.start_ms, scene.end_ms
    positions = [i for i, w in enumerate(t_tokens) if w in q]
    if not positions:
        return scene.start_ms, scene.end_ms
    span = scene.end_ms - scene.start_ms
    start_frac = min(positions) / max(1, len(t_tokens))
    end_frac = (max(positions) + 1) / max(1, len(t_tokens))
    start = int(scene.start_ms + span * max(0.0, start_frac - 0.05))
    end = int(scene.start_ms + span * min(1.0, end_frac + 0.05))
    return start, end
```

- 思路：把 transcript 的第 i 个词视为发生在场景的 `i / N` 处，取所有命中词的最小、最大位置作为窗口，两侧各外扩 5% 并裁到场景边界。
- 两个提前返回分支：query 或 transcript 为空、没有命中词 → 返回整个场景（不收窄）。
- `max(1, len(t_tokens))` 是防御式除零，其实前面已排除空列表，属于冗余保护。
- 手算 "what happened first pour or stir"：transcript 8 个词，命中 `first`(0)、`pour`(2)、`stir`(5)。`start_frac = 0 → max(0, -0.05) = 0`，`end_frac = 6/8 = 0.75 → 0.80`；场景 132,000～170,000 ms，`end = 132000 + 38000 × 0.8 = 162400`，输出 `[02:12-02:42]`。这是四个例子中唯一"收窄得有道理"的。
- ⚠️ **停用词驱动**："ocean at sunset" 只命中 transcript 里的 `at`，得到 `[00:14-00:26]`；"plating of the dish" 命中 `of`/`the`/`dish`，得到 `[03:04-03:30]`；数车问题如果 top-1 是 scene 2，只命中 `the`，得到 `[01:36-01:53]`。
- ⚠️ **线性时间假设**：真实视频语速不均、有静音和音乐。讲义的生产方案是 Whisper 词级时间戳 + TimeLens / VideoITG 这类 grounding 模型，而且视觉事件（车辆经过）未必有人说出来。

### 3.5 `fmt_ms` 与 `main`

```python
def fmt_ms(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"
```

- 整除取秒（截断，不四舍五入），再拆成分、秒；`:02d` 补零到两位。超过 99 分钟时分钟位会变成三位，长视频应改为 `HH:MM:SS`。

```python
    queries = [
        ("how many cars pass through the intersection", False),
        ("what happened first pour or stir", False),
        ("plating of the dish", True),
        ("ocean at sunset", True),
    ]
```

- 两个计数/动作题（`descriptive=False`）、两个描述题（`True`），正好对应讲义"计数与动作类单独报告"。
- ⚠️ 但 `descriptive` 只被打印，代码里没有标准答案、没有准确率、没有 IoU，讲义 rubric 中的评测部分完全没有实现。
- `hits[0][0]`：取 top-1 的 `Scene`，只对它做 grounding（讲义："refines the (start, end) window within the top scene"）。
- `sc.caption[:40]`：切片截断显示，防止行太长。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 哈希词袋假 embedding | 零依赖、几十行代码 | 无语义、24 维碰撞严重、`hash()` 随机化导致不可复现；生产用文本 embedding 模型 + CLIP 类图像 embedding |
| `frame_tags` 文本代替图像向量 | 不需要读图片 | 真实帧向量来自图像编码器，query 需要投到同一图文空间 |
| 三路各自全量排序 | 小数据集上最直观 | 7k 场景时浪费且分数挤压；生产中每路取 top-N，由 Qdrant 完成 ANN 检索 |
| RRF k = 60 | 经典默认值，对分数尺度不敏感 | 场景少时区分度低；可给各路加权或接 reranker |
| 只对 top-1 场景 grounding | 讲义流程就是如此 | top-1 错了 grounding 也跟着错；可以对 top-3 都 grounding 再比较置信度 |
| transcript 线性映射做 grounding | 无需时间戳数据 | 停用词驱动、时间不准；生产用 Whisper 词级时间戳 + TimeLens / VideoITG |
| 无 VLM 合成、无评测 | 聚焦检索主干 | 拿不到讲义 rubric 中的任何指标；需补 IoU、按题型准确率、幻觉率 |
| 场景主键 `(video_id, scene_id)` | `scene_id` 只在视频内唯一 | 正确做法；Qdrant 中可用 UUID 作 point id，把两者放 payload |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 类型注解延迟求值，可以在旧版本 Python 中写 `list[float]` 等新语法 |
| 类型注解 | `def tokenize(s: str) -> list[str]` | 标注参数和返回值类型，不影响运行 |
| 复杂类型注解 | `dict[tuple[str, int], float]`、`list[tuple[Scene, float]]` | 键是 `(str, int)` 元组的字典；元素是 `(Scene, float)` 的列表 |
| `@dataclass` | `class Scene:` | 自动生成 `__init__`、`__repr__` 等，按字段顺序接收位置参数 |
| `field(default_factory=list)` | `caption_emb: list[float] = field(default_factory=list)` | 可变默认值必须用工厂函数，否则所有实例共享同一个列表 |
| 正则 | `re.findall(r"\w+", s.lower())` | `r"..."` 原始字符串，`\w+` 匹配连续单词字符 |
| 内置 `hash()` | `h = hash(tok)` | 对 `str` 每进程随机加盐，不能用于需要跨进程稳定的场景 |
| 位运算 | `h >> 8` | 右移 8 位，等价于整除 256，用来取哈希的另一段比特 |
| `or` 默认值 | `math.sqrt(...) or 1.0` | 左边为 0（假值）时取右边 |
| 列表乘法 | `[0.0] * EMB_DIM` | 生成 24 个 0.0 的列表（元素是不可变的 float，安全） |
| 生成器表达式 | `sum(x * y for x, y in zip(a, b))` | 不建中间列表，边算边求和 |
| `zip` | `zip(a, b)` | 把两个序列按位置配对 |
| 数字下划线 | `132_000` | 仅为可读性，等于 132000 |
| `lambda` + `sorted` | `sorted(scenes, key=lambda s: -cosine(qv, s.caption_emb))` | 取负实现降序；`sorted` 是稳定排序 |
| `defaultdict` | `defaultdict(float)` | 访问不存在的键时自动初始化为 0.0，可直接 `+=` |
| 元组作字典键 | `key = (sc.video_id, sc.scene_id)` | 元组不可变、可哈希，适合作复合主键 |
| 嵌套元组循环 | `for ranks, stream in ((scored_caption, "cap"), ...)` | 循环时直接解包 |
| `enumerate` | `for rank, sc in enumerate(ranks)` | 同时拿到下标（从 0 开始）和元素 |
| 列表推导式 + 条件 | `[i for i, w in enumerate(t_tokens) if w in q]` | 收集命中词的位置 |
| 集合成员判断 | `w in q`（`q` 是 `set`） | 平均 O(1) 查找 |
| 整除与取余 | `ms // 1000`、`s % 60` | 时间换算 |
| f-string 格式符 | `{s // 60:02d}`、`{score:.4f}`、`{sc.caption[:40]}` | 补零两位、4 位小数、表达式内切片 |
| 字符串切片 | `sc.caption[:40]` | 取前 40 个字符 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3，`cd code && python3 main.py`，耗时不到 1 秒）。**每次运行结果都可能不同**（原因见 3.1），下面是一次实际输出：

```text
Q: how many cars pass through the intersection  (descriptive=False)
  scene vid_001/1 @ [00:32-01:08] score=0.0484  cap='busy intersection with pedestrians'
  scene vid_001/0 @ [00:00-00:32] score=0.0481  cap='sunrise over skyline, drone footage'
  scene vid_001/4 @ [02:50-03:30] score=0.0479  cap='chef plating the finished dish'
  grounded window: [00:32-01:08] (narrowed from 00:32-01:08)

Q: what happened first pour or stir  (descriptive=False)
  scene vid_001/3 @ [02:12-02:50] score=0.0487  cap='kitchen scene chef pouring then stirring'
  scene vid_001/0 @ [00:00-00:32] score=0.0481  cap='sunrise over skyline, drone footage'
  scene vid_002/0 @ [00:00-00:40] score=0.0471  cap='ocean waves at sunset'
  grounded window: [02:12-02:42] (narrowed from 02:12-02:50)

Q: plating of the dish  (descriptive=True)
  scene vid_001/4 @ [02:50-03:30] score=0.0492  cap='chef plating the finished dish'
  scene vid_001/2 @ [01:08-02:12] score=0.0474  cap='cars stopped at a red light'
  scene vid_001/1 @ [00:32-01:08] score=0.0472  cap='busy intersection with pedestrians'
  grounded window: [03:04-03:30] (narrowed from 02:50-03:30)

Q: ocean at sunset  (descriptive=True)
  scene vid_002/0 @ [00:00-00:40] score=0.0492  cap='ocean waves at sunset'
  scene vid_001/0 @ [00:00-00:32] score=0.0474  cap='sunrise over skyline, drone footage'
  scene vid_001/3 @ [02:12-02:50] score=0.0472  cap='kitchen scene chef pouring then stirring'
  grounded window: [00:14-00:26] (narrowed from 00:00-00:40)
```

逐项解读：

- **分数范围**：所有分数在 0.0469～0.0492 之间。0.0492 = `3/61`，表示三路都排第 1；"plating" 与 "ocean" 两个描述题都达到了满分，说明 caption、frame_tags、transcript 三路都与 query 有共享词。
- **数车问题**：这次 top-1 是路口场景（vid_001/1），它的 transcript "shibuya crossing after sunrise" 与 query 没有共享词，所以 grounding 直接返回整个场景，"narrowed from 00:32-01:08" 实际上没有收窄。另一次运行 top-1 变成了 vid_001/2，窗口 `[01:36-01:53]`（由停用词 `the` 决定）；还有一次 top-1 是**海浪场景** vid_002/0——纯粹是哈希碰撞造成的。
- **pour or stir**：四个问题中唯一真正有意义的 grounding，`first`、`pour`、`stir` 命中 transcript 前 6 个词，窗口 `[02:12-02:42]`。
- **ocean at sunset**：窗口 `[00:14-00:26]` 只由 transcript 中的 `at` 决定，与"海浪、日落"内容无关。
- **日出场景 vid_001/0 频繁进入 top-3**：它与这些 query 几乎没有共享词，是稳定排序 + 零分并列让它"白拿"名次。

可复现性实验（`PYTHONHASHSEED=0..199`，每个种子跑一次，统计 top-1）：

| query | 期望场景 | 命中次数 / 200 |
|-------|---------|---------------|
| how many cars pass through the intersection | vid_001/2（或 vid_001/1） | 77（+35） |
| what happened first pour or stir | vid_001/3 | 139 |
| plating of the dish | vid_001/4 | 190 |
| ocean at sunset | vid_002/0 | 193 |

共享词越少的 query 越不稳定——这恰好也映射了讲义的结论：计数/动作类问题更难。不过这里的原因是假 embedding 的碰撞噪声，而不是 VLM 的幻觉，不要混为一谈。

---

## 7. 动手改一改

1. **修复可复现性**：用 `hashlib.md5(tok.encode()).digest()` 构造稳定哈希替换 `hash()`（参考测验 Q10），确认连续运行三次输出完全相同。再把 `EMB_DIM` 改成 256，观察分数和排名的变化。
2. **加停用词与词形归一**：在 `tokenize` 后过滤 `{"the", "at", "of", "or", "what", "how", "many"}`，并把 `pouring → pour`、`plated → plate` 做简单词干化；比较 `ground_window` 的输出（"ocean at sunset" 会退化为整个场景——想想这说明了什么）。
3. **RRF 只取每路 top-N**：给 `multi_vector_search` 加参数 `per_stream_n=3` 与 `weights={"cap": 1.0, "frm": 1.0, "trn": 1.0}`，只有每路前 N 名参与融合并乘以权重；观察分数的区分度。
4. **对应讲义练习 2**：实现"单池化向量"版本——把三段文本拼起来只算一个 embedding，用固定种子对比两种方案的 top-1 命中率。
5. **补评测**：为每个 query 写标准答案 `(scene, gold_window)` 与题型，实现 `temporal_iou` 和按 `counting / action / descriptive` 分组的准确率报告（参考测验 Q12）。
6. **进阶**：把 transcript 改成带时间戳的词列表 `[(word, t_ms), ...]`，让 `ground_window` 直接使用真实时间，而不是词序号比例——这就是接入 Whisper 词级时间戳后的形态。

---

## 8. 常见坑

- **用内置 `hash()` 做持久化或跨进程的特征**：每个进程结果不同，检索、缓存、分片都会出问题；要用 `hashlib` 或固定 `PYTHONHASHSEED`。
- **以为 RRF 分数差很小就说明"差不多"**：RRF 分数只反映名次组合，0.0481 与 0.0484 可能是 "第 2 名" 与 "第 1 名" 的区别。
- **全量排名后再融合**：场景多时既慢又会压缩分数；每路取 top-N 再融合。
- **零分并列的隐性偏差**：稳定排序让列表靠前的元素在并列时占便宜；零相似度的结果不应进入排名。
- **grounding 用停用词**：不过滤停用词，"at"、"the" 会决定时间窗口。
- **时间戳的参照系混乱**：区分"视频绝对时间"与"场景内相对时间"。讲义 "Use It" 示例中 top 场景是 `01:32–01:54`，refined window 却是 `00:12–00:58`，完全落在场景之外，就是这个问题。
- **cosine 写成点积但输入未归一化**：换用真实 embedding 时要先归一化或改成真正的 cosine。
- **只报告总体准确率**：讲义与交付物都要求计数 / 动作类单独报告；代码里的 `descriptive` 标志至今没被用于任何统计。
