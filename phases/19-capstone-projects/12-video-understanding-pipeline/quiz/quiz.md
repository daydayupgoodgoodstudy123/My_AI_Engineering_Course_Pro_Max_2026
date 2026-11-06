# 测验 · 综合项目 12：视频理解流程——场景、问答与搜索（Capstone 12 — Video Understanding Pipeline (Scene, QA, Search)）

> **阶段 19 · 综合项目 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么还需要场景级索引 | 讲义："Gemini 2.5 Pro can read a 2-hour video natively, but ingesting 100 hours of video into a queryable corpus still requires a scene-level index"——单个视频能整段读，语料库级检索仍要索引 |
| 2 | 三条并行的 ingest 流水线 | 场景切分（TransNetV2 / PySceneDetect）、VLM 逐场景字幕 + 关键帧 embedding、ASR（Whisper-v3-turbo，词级时间戳），三者按 `(scene_id, 时间范围)` 拼接 |
| 3 | Multi-vector 索引 | 每个场景存三个命名向量：`caption_emb`、`keyframe_emb`（代码里叫 `frame_emb`）、`transcript_emb`；payload 带 `{video_id, scene_id, start_ms, end_ms, keyframe_url}`；23 个场景 → 69 个向量 |
| 4 | RRF 融合 | 三路稠密检索各出一个排名，`score = Σ 1/(k + rank)`（代码 k = 60，rank 从 1 起）；只看名次、不看原始分数，避免不同表示的分数尺度不可比 |
| 5 | Temporal grounding | 在 top 场景内部把 `(start, end)` 收窄到真正包含答案的子窗口；评分用时间 IoU（权重 25，最高） |
| 6 | 带引用的回答 | 答案必须附 `(video_id, start_ms, end_ms)` 引用 + 帧预览，让用户能跳转核实；无引用直接 hard reject |
| 7 | 计数 / 动作类幻觉 | "how many X" 与 "先倒还是先搅" 是 VLM 已知的高幻觉题型，必须与描述类题分开报告准确率 |
| 8 | 评测组合 | 公开基准 ActivityNet-QA、NeXT-GQA + 自建 100 题手工标注集；rubric：IoU 25、QA 准确率 20、吞吐（每美元视频小时数）20、UI 与引用体验 20、幻觉率 15 |
| 9 | 本节代码的简化 | `fake_embed` 用哈希词袋代替真实 embedding；`ground_window` 按 transcript 词位置**线性**映射到时间；没有 VLM 合成与评测 |
| 10 | 可复现性陷阱 | `fake_embed` 用 Python 内置 `hash()`，字符串哈希每个进程随机化，导致每次运行检索结果不同 |

### 核心技能（能动手做到）

- [ ] 画出"切场景 → 字幕/关键帧/ASR 三路 → multi-vector 索引 → 三路检索 + RRF → grounding → VLM 合成"的完整数据流，并说出每一步的产物格式
- [ ] 手算 RRF 分数，解释为什么代码里所有场景的分数都挤在 0.0455～0.0492 之间
- [ ] 手算 `ground_window` 对任意 query 给出的子窗口，并指出停用词驱动 grounding 的问题
- [ ] 写出时间 IoU 函数，并能按题型（计数 / 动作 / 描述）分别统计准确率
- [ ] 识别并修复 `hash()` 随机化导致的不可复现问题（`hashlib` 稳定哈希或固定 `PYTHONHASHSEED`）
- [ ] 为"计数严格模式"设计输出格式：逐个实例带时间戳、可点击核验

---

## 二、基础自测（选择题）

**Q1.** 在 `multi_vector_search` 中，某场景在 caption、frame、transcript 三路排名里**都排第 1**，它的融合分数是多少？

- A. `3/61 ≈ 0.0492`
- B. `3/60 = 0.05`
- C. `1.0`
- D. `3 × 1/1 = 3.0`

**Q2.** 连续运行三次 `python3 main.py`，第一个问题 "how many cars pass through the intersection" 的 top-1 场景分别是 scene 1、scene 2、vid_002 的海浪场景。最根本的原因是：

- A. `random` 模块没有设置种子
- B. RRF 中 `dict` 的遍历顺序是随机的
- C. `sorted` 不是稳定排序
- D. `fake_embed` 使用内置 `hash()`，而 Python 对 `str` 的哈希在每个进程启动时随机加盐（`PYTHONHASHSEED`）

**Q3.** 讲义要求把哪类问题的准确率与描述类问题**分开报告**？

- A. 翻译类与说话人识别类
- B. 计数类（how many）与动作顺序类（does the chef pour before stirring）
- C. 场景切分类与 ASR 类
- D. 所有问题合并报告一个总准确率即可

**Q4.** 本节代码中 `ground_window` 的工作方式是：

- A. 调用 TimeLens 模型逐帧打分
- B. 用关键帧 embedding 与 query 的相似度选帧
- C. 找出 transcript 中与 query 重合的词的位置，按"词序号 / 总词数"线性映射到场景时间轴，再左右各外扩 5%
- D. 直接返回 top 场景的 `(start_ms, end_ms)`，不做任何收窄

**Q5.** 讲义 "Use It" 示例中检测到 23 个场景、写入 69 个向量。那么本节代码 `SAMPLE` 里的 6 个场景按同样的 schema 对应多少个向量？

- A. 6
- B. 12
- C. 24
- D. 18

**Q6.** 为什么三路检索用 RRF 融合，而不是把三个 cosine 分数直接相加？

- A. 不同表示（字幕文本、关键帧视觉、口语 transcript）的相似度分布和尺度不同，直接相加会被某一路主导；RRF 只用名次，天然对尺度不敏感
- B. RRF 计算速度比加法快
- C. cosine 分数可能为负，无法相加
- D. RRF 可以让每路检索只返回 1 个结果

**Q7.** 讲义 rubric 中权重最高的一项是：

- A. QA 准确率（20）
- B. 幻觉率（15）
- C. Temporal grounding IoU（25）
- D. UI 与引用体验（20）

**Q8.** 以下哪一项**不属于**交付物 `skill-video-qa.md` 中列出的 hard reject？

- A. 每个场景只池化成一个向量（single pooled vector）
- B. 使用 PySceneDetect 而不是 TransNetV2 做场景切分
- C. 回答没有 `(start, end)` 引用
- D. 只报告一个总体准确率，不拆分计数 / 动作子集

---

## 三、动手 / 代码题

**Q9.** 阅读 `ground_window`：

```python
def ground_window(query: str, scene: Scene) -> tuple[int, int]:
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

1. query 为 `"ocean at sunset"`，top 场景是 `vid_002/0`（0～40,000 ms，transcript `"beautiful evening at the shore"`）。手算返回的窗口，并说明是哪个词决定了它。
2. 对 `"plating of the dish"`（场景 170,000～210,000 ms，transcript `"plated presentation of the dish"`）同样手算。
3. 指出这个 stub 的两个根本性问题，并说明生产里应如何做。

**Q10.** `fake_embed` 的实现如下：

```python
def fake_embed(text: str) -> list[float]:
    v = [0.0] * EMB_DIM
    for tok in tokenize(text):
        h = hash(tok)
        v[h % EMB_DIM] += 1.0
        v[(h >> 8) % EMB_DIM] += 0.5
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]
```

1. 用 `PYTHONHASHSEED=0..199` 跑 200 次，第一个问题（数车）的 top-1 只有 77 次是"红灯前排队的车"那个场景（vid_001/2）。为什么一个"假 embedding"会表现得这么不稳定？除了随机化，还有哪些因素？
2. 改写成跨进程稳定的版本。
3. 为什么 `cosine()` 可以直接写成点积？

**Q11.** RRF 部分：

```python
    for ranks, stream in ((scored_caption, "cap"),
                          (scored_frame, "frm"),
                          (scored_transcript, "trn")):
        for rank, sc in enumerate(ranks):
            key = (sc.video_id, sc.scene_id)
            fused[key] += 1.0 / (60 + rank + 1)
            index[key] = sc
```

1. 某场景在三路中分别排第 1、第 6、第 3 名，融合分数是多少？与"三路都第 2 名"的场景相比谁更高？
2. 实际运行中所有分数都在 0.0469～0.0492 之间，打印出来几乎看不出差别。为什么？对于真实的 7k 场景库，代码这样"对全部场景排名后融合"有什么问题？
3. 很多场景与 query 的 cosine 为 0（没有共享词），`sorted` 会怎样排它们？这对结果有什么系统性影响？

**Q12.** `main()` 里每个 query 都带了一个 `descriptive` 布尔值，但代码从未使用它。请：

1. 写一个 `temporal_iou(pred, gold)` 函数，并计算讲义 "Use It" 中两组区间的 IoU：refined window `[00:12-00:58]` 与 top scene `[01:32-01:54]`。这个结果说明讲义示例有什么不自洽之处？
2. 写一个 `report(results)`，输入 `[(qclass, correct: bool, pred_window, gold_window), ...]`，按 `counting / action / descriptive` 分别输出准确率和平均 IoU。

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述一个"长视频问答 + 检索"系统从 ingest 到回答的流程，每一步用什么模型/组件，产物是什么。

**Q14.**（原理深挖）为什么每个场景要存 caption、keyframe、transcript 三个向量，而不是池化成一个？RRF 中的常数 k（如 60）起什么作用？

**Q15.**（工程实践）要在预算内 ingest 100 小时视频（约 6k～8k 个场景），你会如何控制成本、提高吞吐，并衡量"每美元可处理的视频小时数"？

**Q16.**（场景设计）用户问"第一分钟内有几辆车经过路口？"，VLM 经常数错。你会如何设计系统来降低计数类幻觉，并证明它有效？

**Q17.**（追问型）既然 Gemini 这类长上下文模型能直接读两小时视频，为什么还要做场景切分和向量索引？什么情况下可以不建索引？

---

## 五、参考答案与解析

### Q1 — 答案：A

`enumerate` 的 `rank` 从 0 开始，代码用 `60 + rank + 1`，所以第 1 名贡献 `1/61 ≈ 0.016393`，三路相加 `3/61 ≈ 0.04918`，与运行输出中最高的 `score=0.0492` 一致（"plating of the dish"、"ocean at sunset" 的 top-1 都是这个值）。B 忽略了 `+1`；C、D 把 RRF 当成了 `1/rank` 且没有 k。

### Q2 — 答案：D

`hash("cars")` 对 `str`/`bytes` 默认带随机盐，每个解释器进程不同（可用 `PYTHONHASHSEED` 固定）。于是每个词落入的 24 维桶在每次运行都不同，词与词之间的"碰撞"也不同，检索排名随之改变。A 错：本文件虽然 `import random` 但根本没用到；B 错：Python 3.7+ 的 dict 保持插入顺序；C 错：`sorted` 是稳定排序（稳定性反而导致了 Q11-3 的偏差）。

### Q3 — 答案：B

讲义："Counting ('how many people enter the room?') and action-type ('does the chef pour before stirring?') questions are notoriously unreliable. Report accuracy separately from descriptive questions." 交付物的拒绝规则也写明"Refuse to hide the counting/action hallucination number inside an overall accuracy figure"。D 恰好是被明确禁止的做法。

### Q4 — 答案：C

代码把 transcript 当成"均匀分布在场景时间轴上的词序列"：命中词的最小序号 / 总词数作为起点比例，最大序号 + 1 作为终点比例，各外扩 0.05 并裁到 `[0, 1]`。A 是讲义描述的生产方案（TimeLens / VideoITG adapter），代码只是 stub；B 没有实现；D 是"没有命中词"时的退化分支。

### Q5 — 答案：D

每个场景三个命名向量：`6 × 3 = 18`。讲义示例 `23 × 3 = 69` 同理。A 是"每场景一个池化向量"的数量——这正是 hard reject 的方案；C 把 `EMB_DIM = 24`（向量维度）误当作向量个数。

### Q6 — 答案：A

字幕 embedding、关键帧视觉 embedding、口语 transcript embedding 来自不同模型或不同文本分布，cosine 的典型值域差别很大；直接相加时尺度大的一路会主导排序。RRF 只依赖每路的**名次**，这是混合检索（如 BM25 + dense）的经典做法，讲义 Key Terms 称之为 "a classic hybrid-retrieval trick"。B 不是动机；C 不成立（负数也能相加）；D 与 RRF 无关。

### Q7 — 答案：C

rubric：Temporal grounding IoU 25、QA accuracy 20、Ingest throughput 20、UI and citation UX 20、Hallucination rate 15。grounding 权重最高，说明"答在哪一段"与"答什么"同样重要——没有准确时间窗，引用就无法核验。

### Q8 — 答案：B

TransNetV2 和 PySceneDetect 在讲义中是并列的可选方案（"TransNetV2 or PySceneDetect"）。A、C、D 均是 `skill-video-qa.md` 的 hard reject；另一条 hard reject 是"VLM 合成时没有直接看到场景帧（只给文本会丢掉视觉 grounding）"。

### Q9 — 参考答案

1. query 词集合 `{ocean, at, sunset}`，transcript 词 `[beautiful, evening, at, the, shore]`（5 个），只有 **`at`**（序号 2）命中。`start_frac = 2/5 = 0.4`，`end_frac = 3/5 = 0.6`；外扩后 `0.35`、`0.65`；`start = 0 + 40000 × 0.35 = 14000`，`end = 40000 × 0.65 = 26000`，即 **`[00:14-00:26]`**，与实际运行输出一致。真正与"海洋、日落"相关的信息在 caption 和 frame_tags 里，transcript 里一个都没有——窗口完全是停用词 "at" 决定的。
2. transcript 5 个词，命中 `of`(2)、`the`(3)、`dish`(4)。`start_frac = 0.4 → 0.35`，`end_frac = 5/5 = 1.0 → min(1.0, 1.05) = 1.0`；`start = 170000 + 40000 × 0.35 = 184000`，`end = 210000`，即 **`[03:04-03:30]`**。同样主要由 `of`/`the` 拉宽。若去掉停用词，只剩 `dish`(4)，窗口变为 `[03:20-03:30]`；而 "ocean at sunset" 去掉停用词后完全没有命中，退化为整场景 `[00:00-00:40]`——这也说明只看 transcript 做 grounding 本身不够。
3. 两个根本性问题：
   - **把词序号线性映射为时间**：假设语速均匀、整个场景都在说话。真实视频有静音、音乐、语速变化。生产中应使用 Whisper（faster-whisper）的**词级时间戳**，命中词直接对应真实时间。
   - **只用文本匹配做 grounding**：视觉事件（海浪、车辆经过）往往没人说出来。讲义的方案是 TimeLens / VideoITG 这类时间 grounding 模型，在 top 场景内对帧序列和 query 做对齐，输出 `(start, end)`。
   - 附带问题：没有停用词过滤、没有词形还原（`pour` ≠ `pouring`，`plating` ≠ `plated`）。

### Q10 — 参考答案

1. 不稳定的来源：
   - **哈希随机化**：`hash(str)` 每进程加盐，词 → 桶的映射每次都变。
   - **维度太小导致碰撞**：只有 24 维，每个词占两个桶，一个 6～8 词的句子会占据大半维度，不相关的词很容易撞进同一个桶，产生"虚假相似"。哪些词相撞取决于当次的盐，所以排名大幅波动。
   - **没有语义**：`cars` 与 `vehicles`、`car` 之间毫无关联，只有字面完全相同的词才会贡献相似度。数车问题与 scene 2 共享的只有 `cars`（caption、frame_tags）和停用词 `the`，信号很弱，因此最容易被碰撞噪声淹没。实测 200 个种子：vid_001/2 有 77 次 top-1，vid_001/1（路口）35 次，其余 88 次落在厨房、海浪、日出等无关场景；而 "plating of the dish"（190/200）和 "ocean at sunset"（193/200）共享词多，就很稳定。
2. 稳定版本（已运行验证：多次运行输出完全一致）：

```python
import hashlib

def stable_hash(tok: str) -> int:
    return int.from_bytes(hashlib.md5(tok.encode("utf-8")).digest()[:8], "little")

def fake_embed(text: str) -> list[float]:
    v = [0.0] * EMB_DIM
    for tok in tokenize(text):
        h = stable_hash(tok)
        v[h % EMB_DIM] += 1.0
        v[(h >> 8) % EMB_DIM] += 0.5
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]
```

   替换后四个问题的 top-1 稳定为 vid_001/2、vid_001/3、vid_001/4、vid_002/0。另一种办法是在运行前 `export PYTHONHASHSEED=0`，但把可复现性寄托在环境变量上不可靠。
3. `fake_embed` 返回前已经做了 L2 归一化，单位向量的 cosine 等于点积。真实 embedding 模型输出未必归一化，直接用点积会把向量长度混进相似度；向量库里一般在建索引时显式选择 cosine 距离或先归一化。

### Q11 — 参考答案

1. 第 1、6、3 名：`1/61 + 1/66 + 1/63 = 0.016393 + 0.015152 + 0.015873 ≈ 0.04742`。三路都第 2 名：`3/62 ≈ 0.04839`。后者更高——RRF 奖励"各路都靠前"的一致性，惩罚在某一路明显落后的结果。
2. 分数挤在一起是因为：每一路都对**全部 6 个场景**排名，最差的第 6 名也能拿到 `1/66`，与第 1 名的 `1/61` 只差约 8%；三路相加后，理论范围只有 `3/66 ≈ 0.0455` 到 `3/61 ≈ 0.0492`。k = 60 本来就是为了让名次差异"平滑"，场景太少时就显得几乎没有区分度。打印 4 位小数时，0.0481 与 0.0484 这种差距其实对应的是一两个名次的变化。
   对真实库的问题：对 7k 场景每一路都做全量排序是 O(N log N) 且毫无必要；生产中每一路只取 top-N（例如 50～100）进入 RRF，其余视为未命中（贡献 0），这才是标准用法，也让"只在某一路命中"的结果与"三路都命中"的结果有明显差距。
3. `sorted` 是稳定排序，cosine 相同（例如都为 0）的场景保持 `SAMPLE` 中的原始顺序，于是靠前的场景（vid_001/0 日出、vid_001/1 路口）在"零分并列"时总能拿到更好的名次，在 RRF 中获得系统性加分。这就是运行结果里 `vid_001/0 sunrise` 经常莫名进入 top-3 的原因。修复：零相似度的结果不进入该路排名，或者并列时给相同名次。

### Q12 — 参考答案

```python
def temporal_iou(pred: tuple[float, float], gold: tuple[float, float]) -> float:
    inter = max(0.0, min(pred[1], gold[1]) - max(pred[0], gold[0]))
    union = max(pred[1], gold[1]) - min(pred[0], gold[0])
    return inter / union if union > 0 else 0.0

from collections import defaultdict

def report(results):
    by = defaultdict(lambda: {"n": 0, "ok": 0, "iou": 0.0})
    for qclass, correct, pred_w, gold_w in results:
        b = by[qclass]
        b["n"] += 1
        b["ok"] += int(correct)
        b["iou"] += temporal_iou(pred_w, gold_w)
    for qclass in ("counting", "action", "descriptive"):
        b = by.get(qclass)
        if not b:
            continue
        print(f"{qclass:<12} n={b['n']:3d}  acc={b['ok']/b['n']:.2%}  mIoU={b['iou']/b['n']:.3f}")
```

1. `[12, 58]` 与 `[92, 114]`（秒）没有交集，IoU = **0**（已用上面函数计算）。说明讲义示例不自洽：top 场景是 `01:32–01:54`，grounding 理应在场景**内部**收窄，结果却给出了 `00:12–00:58`，完全落在场景之外（更像是相对于场景起点的偏移，或者是问题里 "first minute" 的窗口）。实现 grounding 时要明确时间戳是"视频绝对时间"还是"场景内相对时间"，并断言 `scene.start ≤ start < end ≤ scene.end`。作为对照，`[12, 58]` 与 `[10, 50]` 的 IoU 为 `38/48 ≈ 0.79`。
2. `report` 按题型分桶输出准确率和平均 IoU，满足"计数 / 动作与描述类分开报告"的要求。本节 `main()` 中的 `descriptive` 布尔值只被打印出来，既不影响检索，也没有对应的标准答案，因此代码实际上没有任何评测——这是讲义 rubric（幻觉率 15 分）在代码中完全缺失的部分。

### Q13 — 参考回答要点

- **Ingest**：下载 / 读取 MP4 → 必要时降到 720p → 持久化 `{video_id, file_path}`（并带 license 标签，交付物要求拒绝来源不明的视频）。
- **场景切分**：TransNetV2 或 PySceneDetect → `[{scene_id, start_ms, end_ms, keyframe_path}]`；100 小时约 6k～8k 个场景。
- **三路并行**：
  - VLM（Gemini 2.5 Pro / Qwen3-VL-Max / Molmo 2）对关键帧生成 caption，并产出帧 embedding；
  - Whisper-v3-turbo（faster-whisper）产出词级时间戳，按场景切片；
  - 三者按 `(scene_id, 时间范围)` 拼接。
- **索引**：Qdrant 集合三个命名向量 + payload。
- **查询**：query 编码后对三个向量各做一次稠密检索 → RRF → top-5 场景 → TimeLens 类 grounding 收窄 top 场景的窗口 → VLM 合成（query + top-3 场景片段/帧 + transcript）→ 带 `(video_id, start_ms, end_ms)` 引用和帧预览的回答。
- **评测**：ActivityNet-QA、NeXT-GQA、自建 100 题；按题型拆分。
- 加分点：说明 query 侧需要与各路 embedding 空间匹配（文本 query 检索帧向量需要 CLIP 类图文对齐模型）；本节代码用同一个 `fake_embed` 编码所有内容，回避了这个问题。

### Q14 — 参考回答要点

- **三种表示各有盲区**：caption 是 VLM 的"概括"，会丢细节；关键帧 embedding 保留视觉相似性（颜色、物体、构图），适合"找出类似画面"；transcript 只覆盖被说出来的内容，但对"某人说了什么"类问题最精确。池化成一个向量会把三种信号平均掉，讲义练习 2 就是让你测量"pooled vs multi-vector"的检索退化。
- **题型差异**：交付物写道 "Multi-vector is required for the class distinctions to show"——不同题型依赖不同的表示。
- **RRF 的 k**：`1/(k + rank)` 中的 k 控制名次差距的影响力。k 小时第 1 名远大于第 2 名，融合结果近似"谁在某一路排第 1 谁赢"；k 大时曲线平缓，更看重"多路一致靠前"。k = 60 是 RRF 原论文的常用默认值，对各路分数尺度不敏感、无需训练。
- 加分点：可以给各路加权（如计数类 query 加大 frame 路权重），或在 RRF 之后接 cross-encoder / VLM reranker。
- 常见误区：以为 RRF 会考虑相似度大小——它只看名次，因此"第 1 名只比第 2 名好一点点"和"好很多"没有区别。

### Q15 — 参考回答要点

- **把贵的调用放在少的单位上**：VLM caption 按场景（而不是按帧）调用，一个场景只送 1～3 张关键帧；6k～8k 次调用即可覆盖 100 小时（平均每场景约 45～60 秒）。
- **廉价预处理先行**：降采样到 720p 甚至更低用于切分；用感知哈希或帧 embedding 去重近似场景（片头片尾、静态镜头）。
- **ASR 用本地 GPU**：faster-whisper 批处理，远便宜于按分钟计费的 API。
- **批处理与并发**：VLM 调用批量化、异步并发，受 rate limit 约束时用队列；结果缓存，重复 ingest 不重复计费。
- **模型分级**：讲义练习 4 要求比较三种 VLM 的"每美元视频小时数"，找到质量与成本的平衡点（例如 caption 用较便宜的模型，答题时再用 Gemini 2.5 Pro）。
- **度量**：吞吐 = 已索引视频小时数 / 总花费（API + GPU 时长），分阶段记录耗时与费用。交付物的拒绝规则："Refuse to claim 'real-time' response at ingest rates above the measured throughput"。
- 常见误区：逐帧调用 VLM——成本随帧数线性爆炸。

### Q16 — 参考回答要点

- **检索与 grounding 先把范围缩小**：先用时间约束（"第一分钟"）过滤到对应场景，再 grounding，避免让模型在整段视频里数。
- **"计数严格模式"（讲义练习 3）**：要求合成器**逐个列出**被计数的实例，每个附带时间戳和帧预览（讲义示例 "frame preview at 00:14, 00:27, 00:44, 00:51, 00:57" 正是这种形态），最终答案 = 实例个数；用户可以点击核验每一个。
- **多帧而不是单帧**：计数需要连续帧，按更高帧率采样场景片段，避免同一辆车在多帧中被重复计数（可配合跟踪/去重）。
- **工具辅助**：用检测 + 跟踪模型（目标检测 + 多目标跟踪）做客观计数，VLM 只负责理解问题和组织答案。
- **证明有效**：建立计数 / 动作子集的手工标注集，单独报告准确率；对比"普通模式 vs 严格模式 vs 严格模式 + 用户核验"，并报告不确定时的拒答率。
- 常见误区：只看总体准确率——描述类题目占多数时，计数类的高幻觉会被平均掉。

### Q17 — 参考回答要点

- **规模**：讲义的区分是"单个视频可以整段读"vs"100 小时语料库要可查询"。每次提问都把全部视频塞进上下文，成本和延迟都不可接受，而且超出上下文窗口。
- **成本结构**：索引是一次性的 ingest 成本，之后每次查询只处理 top-k 场景；长上下文方案是每次查询都付全量成本。
- **可引用性**：场景索引天然带 `(start_ms, end_ms)`，方便给出时间戳引用和帧预览；直接让长上下文模型"报时间"更容易出错。
- **增量更新**：新视频只需增量 ingest。
- **何时可以不建索引**：只针对单个较短视频的一次性问答（例如用户上传一段视频问几个问题），直接用长上下文 VLM 更简单；也可以两者结合——索引负责召回场景，长上下文模型负责在召回的较长片段上精读。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 12 视频理解——时间建模](../../../04-computer-vision/12-video-understanding/docs/zh.md)：视频的时间维度建模基础。
- [阶段 06 · 05 Whisper——架构与 Fine-Tuning](../../../06-speech-and-audio/05-whisper-architecture-finetuning/docs/zh.md)：ASR 与词级时间戳的来源。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：RRF 与混合检索。
- [阶段 12 · 17 视频语言模型：时间 Tokens 与 Grounding](../../../12-multimodal-ai/17-video-language-temporal-grounding/docs/zh.md)：temporal grounding 的模型侧原理。
- [阶段 12 · 18 百万 Token 上下文中的长视频理解](../../../12-multimodal-ai/18-long-video-million-token/docs/zh.md)：长上下文直接读视频的能力与代价。
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../../12-multimodal-ai/02-clip-contrastive-pretraining/docs/zh.md)：用文本 query 检索关键帧向量所需的图文对齐空间。

### 本节被哪些后续内容用到
- [阶段 12 · 24 多模态 RAG 与跨模态检索](../../../12-multimodal-ai/24-multimodal-rag-cross-modal/docs/zh.md)：跨模态检索的通用化。
- [阶段 19 · 04 多模态文档问答](../../04-multimodal-document-qa/docs/zh.md)：同样的"多表示索引 + 引用"思路用于 PDF。
- [阶段 19 · 63 多模态 Evaluation](../../63-multimodal-eval/docs/zh.md)：按题型拆分的多模态评测。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../65-hybrid-retrieval-bm25-dense/docs/zh.md)：RRF 在文本检索中的完整实现。
- [阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../68-rag-eval-precision-recall/docs/zh.md)：检索阶段的量化评估。

### 延伸关键词
`TransNetV2` · `PySceneDetect` · `faster-whisper word timestamps` · `Qdrant named vectors` · `reciprocal rank fusion` · `temporal IoU` · `TimeLens` · `VideoITG` · `NeXT-GQA` · `ActivityNet-QA` · `counting hallucination` · `PYTHONHASHSEED`
