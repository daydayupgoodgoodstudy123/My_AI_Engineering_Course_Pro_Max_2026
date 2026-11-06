# 测验 · 视频语言模型：时间 Tokens 与 Grounding（Video-Language Models: Temporal Tokens and Grounding）

> **阶段 12 · 多模态 AI · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：本节中文讲义是机器翻译，质量较差（如把 frame 译成"框架"、Q-Former 译成"Q-前"），有疑义请以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 视频 token 爆炸 | 1 分钟 30 FPS = 1,800 帧，每帧 196 个 patch token（ViT-B/224）就是 352,800 个 token，远超 2024 年代的 LLM 上下文 |
| 2 | 三种压缩手段 | 抽帧（丢时间细节）、逐帧池化（丢空间细节）、Q-Former 按片段压缩（两者都丢一点，但最省 token） |
| 3 | 时间位置编码是独立的一根轴 | 模型怎么知道第 5 帧在第 6 帧之前：1D 时间编码、可学习时间嵌入、按真实时间戳旋转的 TMRoPE / M-RoPE |
| 4 | Video-LLaMA（2023） | 16 帧 × 2 FPS = 8 秒片段 → Video Q-Former → 32 个可学习 query → LLM；并行一条 ImageBind 音频分支。固定片段长度、无法定位任意时刻 |
| 5 | VideoChat / Video-LLaVA | 冻结 CLIP 类编码器 + MLP + LLM；Video-LLaVA 用"alignment before projection"让图像与视频共享一个视觉表示；都是 8–16 帧的短视频系统 |
| 6 | TMRoPE（讲义说法） | 每个 patch token 带 `(t, h, w)` 位置，`t` 是真实时间戳而不是帧序号；逐 token 旋转；天然兼容不均匀的动态 FPS，能回答"第 4.2 秒" |
| 7 | 四种抽帧策略 | 均匀（简单，丢运动峰值）、动态 FPS（按运动强度加密）、事件驱动（轻量检测器指路，VideoAgent）、关键帧 + 上下文（镜头边界，电影内容） |
| 8 | 逐帧池化 | 576 token/帧 → 3×3 双线性池化 → 64 token/帧（5 分钟 1 FPS 从 172,800 降到 19,200）；6×6 → 16 token/帧，适合 agent 工作流 |
| 9 | 四个视频基准 | VideoMME（短中长综合）、TempCompass（before/after 时序）、EgoSchema（3 分钟以上第一人称长程）、Video-MMMU（多学科） |
| 10 | Grounding 输出与评测 | 自由文本 / 结构化 JSON `{"event","start","end"}` / `<time>` 特殊 token；评测用时间区间 IoU，常报 recall@IoU 阈值 |

### 核心技能（能动手做到）

- [ ] 给定时长、FPS、每帧 token 数和池化系数，30 秒内估算出视频的 token 预算，并判断能否放进某个上下文窗口
- [ ] 读懂并改写 `uniform_sample` / `dynamic_sample`，指出原实现会**超出帧预算**并能修正（最大余数法）
- [ ] 手算两个时间区间的 IoU，解释为什么 IoU 0.29 在 0.3 阈值下算 miss
- [ ] 把 `evaluate_grounding` 改成一对一匹配，并同时报告 precision / recall / F1
- [ ] 为时间 grounding 设计一个 VLM 可学习输出的 JSON schema，包括"事件不存在""多次发生"等错误情形
- [ ] 能说清 Q-Former-per-clip、pooled-per-frame、M-RoPE-per-token 三种设计各自丢掉了什么

---

## 二、基础自测（选择题）

**Q1.** 一段 1 分钟、30 FPS 的视频，逐帧送入 ViT-B/224（每帧 196 个 patch token），不做任何压缩，总共多少视觉 token？

- A. 352,800
- B. 11,760
- C. 58,800
- D. 1,800

**Q2.** 5 分钟视频按 1 FPS 抽帧、每帧 576 个 token，再做 3×3 双线性池化，送进 LLM 的视觉 token 数约为：

- A. 172,800
- B. 57,600
- C. 4,800
- D. 19,200

**Q3.** 与"可学习的时间位置嵌入表"（按帧序号查表）相比，讲义所说 TMRoPE 的关键增益是：

- A. 把每帧的 token 数从 576 降到 64
- B. 用真实时间戳作为位置，逐 token 旋转，因此能处理不均匀抽帧（动态 FPS），并能输出"第 4.2 秒"这类绝对时刻
- C. 增加了一条 ImageBind 音频分支，实现视听联合推理
- D. 用一个更大的视觉编码器替换 CLIP

**Q4.** 真实事件区间为 `[6.0, 6.5]` 秒，模型预测为 `[5.8, 6.2]` 秒。按本节代码的 `iou()`，两者的时间 IoU 是：

- A. 0.40
- B. 0.50
- C. 0.29
- D. 0.20

**Q5.** 本节运行 `dynamic_sample(motion, fps_cap=4, total_budget=12)`（`motion` 为 10 秒的运动强度），实际返回了多少个采样时刻？

- A. 12，正好等于预算
- B. 10，每秒 1 帧
- C. 40，每秒都打满上限 4 帧
- D. 15，超出了预算

**Q6.** 下列哪个基准专门考察"before / after"这类细粒度时序推理？

- A. TempCompass
- B. EgoSchema
- C. Video-MMMU
- D. VideoMME

**Q7.** 关于 Video-LLaMA 的架构，描述正确的是：

- A. 用同一个视觉编码器同时处理图像和视频帧，再经 MLP 投影进 LLM
- B. 每个 patch token 携带 `(t, h, w)` 位置，`t` 为真实时间戳
- C. 16 帧片段经 Video Q-Former 压成 32 个可学习 query；另有 ImageBind 音频编码器 + Audio Q-Former 的并行音频分支
- D. 每帧 3×3 池化，一次输入 32 帧，统一处理单图、多图和视频

**Q8.** 关于本节 `evaluate_grounding()` 的行为，说法正确的是：

- A. 它用匈牙利算法做一对一匹配，同一个预测不会被重复计分
- B. 它只计算 recall：额外的错误预测不会让分数下降，一个预测还可以同时"命中"多个同名真值事件
- C. 只要 IoU 足够高，事件名不同也会被算作命中
- D. IoU 恰好等于 0.3 时会被判为 miss

---

## 三、动手 / 代码题

**Q9.** 阅读 `dynamic_sample`：

```python
def dynamic_sample(motion: list[float], fps_cap: int = 4,
                   total_budget: int = 32) -> list[float]:
    total_motion = sum(motion)
    if total_motion == 0:
        return uniform_sample(len(motion), total_budget)
    samples_per_sec = []
    for m in motion:
        raw = total_budget * m / total_motion
        samples_per_sec.append(min(fps_cap, max(1, round(raw))))
    ...
```

`motion = [0.1, 0.1, 0.8, 0.9, 0.9, 0.2, 0.1, 0.5, 0.9, 0.9]`，`total_budget = 12`。

1. 逐秒写出 `raw` 和最终的 `samples_per_sec`，说明为什么返回 15 帧。
2. 程序打印 "dynamic places more frames in high-motion seconds 2-4 and 7-9"，这句话准确吗？
3. 若改成 `total_budget = 32`，会返回多少帧？为什么这次又"不够"？
4. 写一个严格遵守预算的版本。

**Q10.** `evaluate_grounding` 对每个真值事件找"同名且 IoU 最大"的预测，只报 recall。

1. 构造一个例子，说明一个预测可以同时命中两个真值事件。
2. 改写为一对一匹配，并同时输出 precision / recall / F1。用本节 demo 数据，在阈值 0.3、0.5、0.7 下结果分别是多少？

**Q11.**（手算，对应讲义练习 1）一段 3 分钟的烹饪演示：前后共 120 秒是主持人站着讲解（几乎静止），中间 60 秒是快速切菜和翻炒。每帧 576 token，统一做 3×3 池化。分别计算：

1. 均匀 1 FPS、均匀 2 FPS、均匀 4 FPS 的 token 数；
2. 动态 FPS（静止段 1 FPS、动作段 4 FPS）的 token 数；
3. 你会选哪种？为什么？

**Q12.**（设计题，对应讲义练习 3）为时间 grounding 设计一个 VLM 可以学会输出的 JSON schema。要求覆盖：单次事件、多次发生、事件不存在、模型不确定、时间超出视频长度等情形，并说明下游解析时要做哪些校验。

---

## 四、面试高频题

**Q13.**（基础必考）为什么说"视频不是一叠照片"？把视频喂给 LLM 时 token 会爆炸到什么量级，常见的三种压缩手段各自牺牲了什么？

**Q14.**（原理深挖）比较三种时间建模方式：Video-LLaMA 的 Q-Former-per-clip、Video-LLaVA 的 pooled-per-frame、Qwen2.5-VL 的 per-token 绝对时间位置编码。为什么"用真实时间戳当位置"能让模型回答"第几秒"，而帧序号嵌入不行？

**Q15.**（工程实践）你要评测一个视频 VLM 的时间 grounding 能力，会设计哪些指标与流程？本节的 `evaluate_grounding` 离一个可用的评测还差什么？

**Q16.**（场景设计）为一个"体育比赛精彩片段自动打点"产品设计视频 VLM 方案：比赛 90 分钟，需要输出进球、犯规等事件的起止时间。请给出抽帧、池化、时间编码、输出格式和上下文预算。

**Q17.**（追问型）既然 Q-Former 能把 16 帧压成 32 个 token，最省 token，为什么 2025 年后的主流开源视频 VLM 反而回到"逐帧池化 + 时间位置编码"？

---

## 五、参考答案与解析

### Q1 — 答案：A

`60 秒 × 30 FPS = 1,800 帧`，`1,800 × 196 = 352,800`。讲义原文："that is 352k tokens — larger than any 2024-era LLM context"。B 是 `60 × 196`（每秒只取 1 帧）；C 是 `300 × 196`（误按 5 FPS）；D 只是帧数。

### Q2 — 答案：D

3×3 池化把 24×24 = 576 的 patch 网格降到 8×8 = 64，`300 帧 × 64 = 19,200`，与讲义 "19,200 tokens for 5 minutes" 一致。A 是未池化的 `300 × 576`；B 是误把 3×3 池化当成只除以 3；C 是 6×6 池化（16 token/帧）的结果 `300 × 16 = 4,800`。

### Q3 — 答案：B

讲义列出三点区别："Absolute time, not index"、"Per-token rotation, not per-clip"、"Compatible with dynamic FPS"。帧序号嵌入在 2 FPS 和 4 FPS 混合抽帧时，相邻帧的序号差都是 1，但真实间隔一个是 0.5 秒一个是 0.25 秒，模型无从得知；用时间戳就没有这个问题。A 是池化的作用；C 是 Video-LLaMA 的音频分支；D 与位置编码无关。

### Q4 — 答案：C

交集 = `min(6.2, 6.5) − max(5.8, 6.0) = 0.2`；代码中的 union = `max(6.2, 6.5) − min(5.8, 6.0) = 0.7`；IoU = 0.2 / 0.7 ≈ **0.286**，打印为 0.29，低于 0.3 阈值，所以 `turn` 被判为 miss。A 是 0.2/0.5（误用真值长度做分母）；B 是 0.2/0.4（误用预测长度）；D 只是交集长度。

### Q5 — 答案：D

实际运行输出 15 个时刻（见 Q9 的逐秒表）。原因是每秒保底 `max(1, ...)`，再加上 `round` 向上取整，10 秒保底就占了 10 帧，剩下高运动秒还各拿 2 帧。代码打印的标签 "dynamic (12 frames total)" 与实际不符。C 错在 `fps_cap` 在这里从未生效（最大的 raw 只有 2.0）。

### Q6 — 答案：A

讲义："TempCompass: fine-grained temporal reasoning, 'before' / 'after' questions"。EgoSchema 考 3 分钟以上的第一人称长程推理；Video-MMMU 是多学科视频问答；VideoMME 覆盖短、中、长时长的综合理解。

### Q7 — 答案：C

讲义："16-frame clips at 2 FPS ... Video Q-former that cross-attends over all 16 frames -> 32 learned queries -> LLM"，并行 "waveform -> ImageBind audio encoder -> Audio Q-former -> 32 queries"。A 描述的是 Video-LLaVA；B 是讲义中 Qwen2.5-VL 的 TMRoPE；D 接近代码表格中 LLaVA-OV-1.5 的"pool / 32 frames"。注意讲义开头"The Problem"一节又说 Q-Former "takes a 16-frame clip and outputs 64 tokens"，与这里的 32 个 query 前后不一致。

### Q8 — 答案：B

代码只统计 `hits / len(ground_truth)`，即 recall；预测列表里多出来的错误事件完全不扣分；而且内层循环没有记录"这个预测已经被用过"，同一个预测可以被多个同名真值重复使用（实测：一个预测 `jump [4.1, 4.6]` 同时命中真值 `[4.0, 4.5]` 和 `[4.2, 4.6]`，recall = 1.0）。A 错，没有任何一对一匹配；C 错，`if p.name == gt.name` 要求事件名完全相同；D 错，判定是 `best_iou >= tol_iou`，等于 0.3 算命中。

### Q9 — 参考答案

1. `total_motion = 5.4`，`raw = 12 × m / 5.4`（已实际运行验证）：

| 秒 | motion | raw | round(raw) | 最终帧数 |
|----|--------|-----|-----------|---------|
| 0 | 0.1 | 0.222 | 0 | 1（保底） |
| 1 | 0.1 | 0.222 | 0 | 1（保底） |
| 2 | 0.8 | 1.778 | 2 | 2 |
| 3 | 0.9 | 2.000 | 2 | 2 |
| 4 | 0.9 | 2.000 | 2 | 2 |
| 5 | 0.2 | 0.444 | 0 | 1（保底） |
| 6 | 0.1 | 0.222 | 0 | 1（保底） |
| 7 | 0.5 | 1.111 | 1 | 1 |
| 8 | 0.9 | 2.000 | 2 | 2 |
| 9 | 0.9 | 2.000 | 2 | 2 |

合计 `1+1+2+2+2+1+1+1+2+2 = 15`。超预算的根源：`max(1, ·)` 的保底帧没有从预算里扣除；`round` 也可能把多个 0.5 以上的值同时向上取整。

2. 不完全准确。第 2–4 秒确实是 2 帧，但第 7 秒（motion 0.5）只分到 1 帧，与静止秒一样；只有 8–9 秒是 2 帧。而且高运动秒只比静止秒多 1 帧，"加密"效果很弱——因为 12 帧预算本来就只比 10 秒多 2 帧。

3. 返回 **27 帧**（实测）。此时高运动秒的 raw ≈ 4.4–5.3，被 `fps_cap = 4` 截断，多出来的预算没有重新分配给其它秒，于是少于 32。原实现既不保证"不超"，也不保证"用满"。

4. 参考实现（已运行验证：预算 12/20/32 时分别正好返回 12/20/32 帧，预算 50 时受上限约束返回 40 帧）：

```python
def dynamic_sample_budgeted(motion, fps_cap=4, total_budget=32):
    n = len(motion)
    total = sum(motion)
    budget = min(total_budget, n * fps_cap)        # 预算不能超过上限能容纳的帧数
    if total == 0 or budget <= n:
        return uniform_sample(n, budget)
    counts = [1] * n                               # 保底：每秒 1 帧，先从预算里扣掉
    extra = budget - n
    raw = [extra * m / total for m in motion]      # 剩余预算按运动量分
    for i in range(n):
        counts[i] += min(fps_cap - 1, int(raw[i]))
    left = budget - sum(counts)
    order = sorted(range(n), key=lambda i: raw[i] - int(raw[i]), reverse=True)
    while left > 0:                                # 最大余数法补齐，跳过已满的秒
        for i in order:
            if left > 0 and counts[i] < fps_cap:
                counts[i] += 1
                left -= 1
    return [round(s + (j + 0.5) / c, 3) for s, c in enumerate(counts) for j in range(c)]
```

预算 12 时得到每秒帧数 `[1,1,1,2,2,1,1,1,1,1]`：保底用掉 10 帧，剩下 2 帧给余数最大的秒。要点：**先扣保底，再按比例分配剩余，最后用最大余数法补齐并尊重上限**。

### Q10 — 参考答案

1. 真值 `jump [4.0, 4.5]`、`jump [4.2, 4.6]`，只有一个预测 `jump [4.1, 4.6]`。原函数对两个真值分别算出 IoU 0.67、0.80，都命中，recall = 1.0——一个预测"领了两份功劳"。

2. 一对一贪心匹配（按 IoU 从高到低配对，每个预测、每个真值最多用一次）：

```python
def evaluate_grounding_v2(predictions, ground_truth, tol_iou=0.3):
    cands = []
    for gi, gt in enumerate(ground_truth):
        for pi, p in enumerate(predictions):
            if p.name == gt.name:
                v = iou(p.start, p.end, gt.start, gt.end)
                if v >= tol_iou:
                    cands.append((v, gi, pi))
    cands.sort(reverse=True)
    used_g, used_p, tp = set(), set(), 0
    for v, gi, pi in cands:
        if gi not in used_g and pi not in used_p:
            used_g.add(gi); used_p.add(pi); tp += 1
    recall = tp / max(1, len(ground_truth))
    precision = tp / max(1, len(predictions))
    f1 = 2 * precision * recall / (precision + recall) if tp else 0.0
    return {"recall": recall, "precision": precision, "f1": f1}
```

实测结果：

| 场景 | recall | precision | F1 |
|------|--------|-----------|----|
| 上面的重复命中例子 | 0.50 | 1.00 | 0.67 |
| demo 数据，阈值 0.3 | 0.33 | 0.33 | 0.33 |
| demo 数据，阈值 0.5 | 0.33 | 0.33 | 0.33 |
| demo 数据，阈值 0.7 | 0.00 | 0.00 | 0.00 |
| demo 数据 + 3 个垃圾预测，阈值 0.3 | 0.33 | 0.17 | 0.22 |

最后一行说明：原函数对垃圾预测"免疫"（recall 仍是 0.33），新函数的 precision 会下降。三个事件的平均 IoU（mIoU）为 0.377，也常与 recall@IoU 一起报告。严格的最优一对一匹配可用匈牙利算法（`scipy.optimize.linear_sum_assignment`），贪心在大多数评测脚本中已经够用。

### Q11 — 参考答案

每帧池化后 `576 / 9 = 64` token（已用 Python 计算）。

1. 均匀 1 FPS：`180 × 64 = 11,520`；均匀 2 FPS：`360 × 64 = 23,040`；均匀 4 FPS：`720 × 64 = 46,080`。
2. 动态 FPS：`120 × 1 × 64 + 60 × 4 × 64 = 7,680 + 15,360 = 23,040`。
3. 选**动态 FPS**：它和均匀 2 FPS 花的 token 一样多（23,040），但动作段的时间分辨率是均匀 2 FPS 的两倍，与均匀 4 FPS 相同，而 token 只有后者的一半。烹饪演示的关键信息（下刀、翻炒、加料的时机）集中在高运动段，均匀抽帧会把预算浪费在静止的讲解段上。如果目标只是"总结菜谱"，均匀 1 FPS 的 11,520 token 也够用；如果要回答"第几秒加的盐"，就需要动态 FPS + 时间戳位置编码。

### Q12 — 参考答案

```json
{
  "video_duration": 182.4,
  "query": "厨师什么时候加盐？",
  "status": "found",
  "events": [
    {"event": "add_salt", "start": 64.2, "end": 65.0, "confidence": 0.82},
    {"event": "add_salt", "start": 131.5, "end": 132.1, "confidence": 0.61}
  ],
  "reason": null
}
```

- `status` 取值：`found`（一次或多次，`events` 非空）/ `not_found`（视频中没有该事件，`events` 为空，`reason` 写明"未观察到"）/ `uncertain`（画面遮挡、帧率不足等，给出低置信度候选并说明原因）。
- 多次发生：`events` 是数组，按 `start` 升序。
- 下游校验：JSON 能否解析；`0 ≤ start < end ≤ video_duration`（超出视频长度直接判为错误或裁剪）；`confidence ∈ [0, 1]`；事件名在允许的标签集合内；数组内区间是否重叠（重叠的同名事件应合并）。
- 训练技巧：数据中一定要包含 `not_found` 样本，否则模型会"必答"，凭空编一个时间；数值保留 1 位小数，与时间位置编码的分辨率一致。
- 与讲义一致：讲义建议 "structured JSON with time + event fields"，skill 文件进一步要求 `{event, start, end, confidence}`。

### Q13 — 参考回答要点

- **视频 ≠ 图片堆**：视频含有因果顺序、动作动词（"拿起"和"放下"画面可能相同，只是顺序相反）和事件时刻；把帧当作无序图片集合，模型无法回答 before/after、"第几秒"之类的问题。
- **token 量级**：1 分钟 30 FPS × 196 token/帧 = 352,800；5 分钟 1 FPS × 576 = 172,800。
- **三种压缩及代价**：
  - 抽帧（1–8 FPS）：丢**时间**细节，可能漏掉短促动作；
  - 逐帧池化（3×3、4×4）：丢**空间**细节，小物体、文字可能看不清；
  - Q-Former 按片段压缩（16 帧 → 32/64 个 query）：时间和空间都丢一点，但 token 最省；代价是片段长度固定，片段内的时间顺序被揉进 query，难以精确定位。
- 加分点：说明这三者可以组合（如动态 FPS + 3×3 池化），并且时间位置编码是与压缩正交的另一根轴。

### Q14 — 参考回答要点

- **Q-Former-per-clip（Video-LLaMA）**：一个 8 秒片段输出固定数量的 query，LLM 看到的是"这一段的摘要"，只能说"片段前部"，无法给出秒级时刻；片段长度固定。
- **pooled-per-frame（Video-LLaVA）**：每帧保留一组 token，帧的顺序靠序列位置（或时间嵌入）表达；8 帧系统覆盖的时长有限。
- **per-token 绝对时间位置（Qwen2.5-VL）**：每个视觉 token 的位置包含 `(t, h, w)`，`t` 对齐真实时间。抽帧密度变化时，位置差仍然等于真实时间差，模型在训练中学到"位置差 ↔ 秒数"的对应，于是能输出"4.2 秒"。帧序号嵌入只知道"第 15 帧"，换一个 FPS 同一序号就对应不同秒数，推理时无法换算。
- 补充：讲义第 17 节把这种编码称为 Qwen2.5-VL 的 TMRoPE；第 20 节则把 TMRoPE 归于 Qwen2.5-Omni（跨视觉、音频、文本的时间对齐）。据两篇论文，Qwen2.5-VL 的提法是"把 M-RoPE 的时间维与绝对时间对齐"，TMRoPE（Time-aligned Multimodal RoPE）这一名称出自 Qwen2.5-Omni。面试中说清"按绝对时间戳分配时间位置 ID"这一机制即可，不必纠结命名。
- 常见误区：认为时间编码只是锦上添花。讲义强调它"independently of the vision encoder"地影响视频 VLM 性能。

### Q15 — 参考回答要点

- **指标**：recall@1 在 IoU = 0.3 / 0.5 / 0.7 三个阈值下的数值；mIoU；如果允许多个预测，再报 precision / F1；对"事件不存在"的样本单独统计拒答准确率。
- **匹配规则**：一对一匹配（贪心或匈牙利），事件名要做规范化（同义词、大小写）。
- **解析失败**：JSON 解析失败、时间越界、`start ≥ end` 都应计为错误并单独统计比例，否则会高估模型。
- **分层报告**：按视频时长（短/中/长）、事件时长（瞬时动作 vs 长事件）分桶——短事件的 IoU 对 0.1 秒误差极其敏感（本节 `turn` 事件只有 0.5 秒，偏移 0.2 秒 IoU 就掉到 0.29）。
- **本节代码缺什么**：一对一匹配、precision、多阈值、解析校验、分桶统计；事件名必须完全一致这一点也过于严格。
- 加分点：说明公开基准（如讲义提到的 TempCompass 偏时序判断）与 grounding 任务的指标不同，需要按任务选择。

### Q16 — 参考回答要点

- **预算估算**：90 分钟 = 5,400 秒。均匀 1 FPS × 64 token = 345,600 token，超过多数开源模型上下文；skill 文件要求"总 token 超过上下文 40% 要报警"。
- **分层方案**：
  1. 第一遍：低帧率（如 0.5 FPS）+ 6×6 池化（16 token/帧），全场 `2,700 × 16 = 43,200` token，粗定位候选时间段；或者用比分牌 OCR、音频能量（观众欢呼）做事件驱动触发。
  2. 第二遍：只对候选段（如每段 30 秒）用动态 FPS（1–4 FPS）+ 3×3 池化精细定位。
- **时间编码**：选用支持绝对时间位置编码的模型（讲义推荐 Qwen2.5-VL 系），分段送入时要把真实起始时间偏移带上，否则输出的秒数是相对片段的。
- **输出**：JSON `{event, start, end, confidence}`，下游做越界和重叠校验。
- **评测**：用历史比赛的人工打点做 recall@IoU 0.5，并统计漏报（进球漏报代价最高）。
- 与第 18 节衔接：超长视频可走 agentic retrieval 路线。

### Q17 — 参考回答要点

- Q-Former 的问题：片段长度固定、query 数固定，**时间信息在 cross-attention 里被混合**，无法输出精确时刻；对长视频要串很多片段，片段之间的顺序还要另外编码。
- 逐帧池化 + 时间位置编码：每帧仍保留空间结构，时间维由位置编码显式表达，可直接回答"第几秒"；配合动态 FPS 能把 token 花在高运动段上。
- 上下文变长（讲义提到 Qwen2.5-VL-72B 的 128k）以后，"最省 token"不再是首要目标，"保留可定位的信息"更重要。
- 训练层面：逐帧池化与图像路径一致，便于图像/多图/视频统一训练（参见 LLaVA-OneVision）。
- 加分点：Q-Former 思路并未消失，在第 18 节的 token compression（如 Video-XL 的视觉摘要 token）里以另一种形式存在——当时长真的到小时级时，压缩仍然必要。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 08 LLaVA-OneVision：统一处理单图、多图与视频](../../08-llava-onevision-single-multi-video/docs/zh.md)：本节的先修课，逐帧池化 + 统一训练的基础。
- [阶段 12 · 03 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former](../../03-blip2-qformer-bridge/docs/zh.md)：Video-LLaMA 的 Video Q-Former 直接沿用这一结构。
- [阶段 12 · 09 Qwen-VL 系列与动态帧率视频](../../09-qwen-vl-family-dynamic-fps/docs/zh.md)：动态 FPS 与 M-RoPE 的详细介绍。
- [阶段 07 · 04 位置编码 — 正弦、RoPE、ALiBi](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：理解 RoPE 才能理解按时间戳旋转。
- [阶段 12 · 01 Vision Transformers 与 Patch-Token 基本单元](../../01-vision-transformer-patch-tokens/docs/zh.md)：每帧 196 / 576 个 patch token 从何而来。

### 本节被哪些后续内容用到
- [阶段 12 · 18 百万 Token 上下文中的长视频理解](../../18-long-video-million-token/docs/zh.md)：把本节的 token 预算推到小时级视频。
- [阶段 12 · 20 全模态模型：Qwen2.5-Omni 与 Thinker-Talker 分工](../../20-omni-models-thinker-talker/docs/zh.md)：TMRoPE 扩展到视觉、音频、文本的时间对齐。
- [阶段 11 · 03 Structured Outputs：JSON、Schema 校验与约束解码](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：让 VLM 稳定输出 grounding JSON。
- [阶段 19 · 12 综合项目 12：视频理解流程——场景、问答与搜索](../../../19-capstone-projects/12-video-understanding-pipeline/docs/zh.md)：在综合项目中落地抽帧与 grounding。

### 延伸关键词
`temporal grounding` · `M-RoPE / TMRoPE` · `dynamic FPS` · `Video Q-Former` · `alignment before projection` · `bilinear pooling` · `temporal IoU` · `recall@IoU` · `mIoU` · `VideoMME` · `TempCompass` · `EgoSchema`
