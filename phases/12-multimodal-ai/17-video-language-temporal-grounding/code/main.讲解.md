# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 17 节 视频语言模型：时间 Tokens 与 Grounding ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`；`math`、`random` 被导入但未使用），无需 GPU、无需网络

---

## 1. 这份代码在考察什么

这份代码不涉及任何真实视频或模型，而是用三个小玩具把讲义里"视频 VLM 的工程决策"具体化：

1. **抽帧策略**：均匀抽帧 vs 按运动强度分配的动态 FPS 抽帧——对应讲义 "Frame sampling strategies"。
2. **时间 grounding 评测**：用时间区间 IoU 判断模型给出的事件起止时间是否"命中"，统计 recall——对应讲义 "Grounding output formats" 与学习目标中的"grounding accuracy"。
3. **架构对照表**：Video-LLaMA、Video-LLaVA、VILA-1.5、Qwen2.5-VL、LLaVA-OV-1.5 各用什么压缩器——对应讲义 "The Concept" 各小节。

> 一句话：**视频 VLM 的效果一半取决于"喂哪些帧、每帧给多少 token、怎么告诉模型时间"，另一半才是视觉编码器本身**；本代码让你能亲手算出抽帧位置和 grounding 分数。同时要注意，它的动态抽帧会超预算、评测只算 recall，这两处简化正好是练习和面试的切入点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `uniform_sample(duration, n)` | 函数 | 把时长等分成 n 段，取每段中点 | 均匀抽帧 |
| `dynamic_sample(motion, fps_cap, total_budget)` | 函数 | 按每秒运动强度比例分配帧数，每秒至少 1 帧、至多 `fps_cap` 帧 | 动态 FPS |
| `iou(a_start, a_end, b_start, b_end)` | 函数 | 两个时间区间的交并比 | 时间 IoU |
| `Event` | dataclass | 事件名 + 起止时间 | grounding 输出的结构化表示 |
| `evaluate_grounding(predictions, ground_truth, tol_iou)` | 函数 | 每个真值找同名、IoU 最大的预测，统计 recall | grounding 评测 |
| `demo_samplers` / `demo_grounding` / `arch_compare` | 函数 | 打印三个演示 | — |
| `main` | 函数 | 依次调用演示并打印 TAKEAWAY | — |

数据流：`main` → `demo_samplers`（`uniform_sample`、`dynamic_sample`）→ `demo_grounding`（构造 `Event` 列表 → `evaluate_grounding` → `iou`）→ `arch_compare`（静态表格）→ 打印结论。

---

## 3. 逐段精讲

### 3.1 均匀抽帧：取每段中点

```python
def uniform_sample(duration: float, n: int) -> list[float]:
    if n <= 1:
        return [duration / 2]
    step = duration / n
    return [round(step * (i + 0.5), 3) for i in range(n)]
```

- 把 `[0, duration)` 等分为 n 段，每段长度 `step`，取中点 `step × (i + 0.5)`。10 秒取 8 帧时 `step = 1.25`，结果是 `0.625, 1.875, …, 9.375`。
- 取中点而不是起点，可以让首尾两帧离视频边界同样远，避免第一帧总是黑屏或片头。
- `n <= 1` 时只取正中一帧；注意 `n = 0` 也会返回 1 帧（`[5.0]`），这是一个没有明确报错的边界情况。
- 讲义对均匀抽帧的评价："Simple, loses motion peaks"——如果一个 0.3 秒的跳跃恰好落在两个采样点之间，模型根本看不到。

### 3.2 动态 FPS 抽帧：按运动量分配预算

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
    times = []
    for sec_idx, count in enumerate(samples_per_sec):
        for j in range(count):
            t = sec_idx + (j + 0.5) / count
            times.append(round(t, 3))
    return times
```

- `motion` 是"每秒一个运动强度"的列表，长度就是视频秒数。真实系统里它来自光流或相邻帧差分（讲义："Optical flow or frame differencing picks high-motion segments"）。
- 第一步按比例分配：`raw = 预算 × 本秒运动 / 总运动`，再 `round`，并夹在 `[1, fps_cap]` 之间。
- 第二步在每秒内部均匀放 `count` 个点：`sec_idx + (j + 0.5) / count`。例如第 2 秒分到 2 帧，就是 2.25 和 2.75。
- 全静止（`total_motion == 0`）时退化为均匀抽帧，避免除以 0。
- ⚠️ **预算不守恒**：`max(1, ·)` 的保底帧没有从预算里扣除。本次运行预算 12，实际返回 **15** 帧；预算 32 时又因为 `fps_cap` 截断后没有重新分配而只返回 **27** 帧。打印标签 "dynamic (12 frames total)" 与实际不符（逐秒计算见测验 Q9）。
- ⚠️ `round` 是 Python 的"银行家舍入"（四舍六入五成双）：`round(2.5) == 2`、`round(3.5) == 4`。在这里影响不大，但做配额分配时要心中有数。
- ⚠️ 这里的"动态 FPS"只在**一秒的粒度**上变化，真实系统（讲义说 Qwen2.5-VL 在动态 FPS 上训练）还要配合时间戳位置编码，才能让模型知道两帧之间到底隔了多少秒。

### 3.3 时间 IoU

```python
def iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union if union > 0 else 0.0
```

- 交集 = 较早的结束 − 较晚的开始，负数截为 0。
- 这里的 `union` 其实是两个区间的"外包区间"长度；两区间有重叠时它恰好等于并集长度；没有重叠时交集已经是 0，IoU 仍为 0，所以结果正确。
- 例：预测 `[4.1, 4.7]` vs 真值 `[4.0, 4.5]`：交集 0.4，并集 0.7，IoU = 0.571。
- 时间 IoU 对**短事件**非常苛刻：真值 `turn` 只有 0.5 秒，预测整体提前 0.2 秒，IoU 就只剩 0.286。

### 3.4 `Event` 与 grounding 评测

```python
@dataclass
class Event:
    name: str
    start: float
    end: float


def evaluate_grounding(predictions: list[Event], ground_truth: list[Event],
                       tol_iou: float = 0.3) -> dict:
    hits = 0
    details = []
    for gt in ground_truth:
        best_iou = 0.0
        best_pred = None
        for p in predictions:
            if p.name == gt.name:
                val = iou(p.start, p.end, gt.start, gt.end)
                if val > best_iou:
                    best_iou = val
                    best_pred = p
        hit = best_iou >= tol_iou
        if hit:
            hits += 1
        details.append((gt.name, best_iou, hit))
    return {"recall": hits / max(1, len(ground_truth)), "details": details}
```

- `Event` 正好对应讲义推荐的结构化 JSON 输出 `{"event": "jump", "start": 4.1, "end": 4.3}`：真实系统里先把模型输出的 JSON 解析成 `Event`，再交给评测函数。
- 对每个真值，在**同名**预测里找 IoU 最大的一个，IoU ≥ 阈值就算命中；最终 `recall = 命中数 / 真值数`。`max(1, …)` 防止真值为空时除以 0。
- `best_pred` 被赋值但从未使用——原作者可能想把它放进 `details`。
- ⚠️ **只有 recall，没有 precision**：模型多输出 10 个乱猜的事件也不扣分。
- ⚠️ **不是一对一匹配**：同一个预测可以同时"命中"多个同名真值。
- ⚠️ 事件名必须**完全相同**（`"jump"` 与 `"Jump"`、`"jumps"` 都对不上），真实评测要做名称规范化。
- 修正版（一对一贪心匹配 + precision/recall/F1）见测验 Q10。

### 3.5 架构对照表与 TAKEAWAY

```python
    rows = [
        ("Video-LLaMA",  "Q-former / 16 frames", "fixed clip, audio branch"),
        ("Video-LLaVA",  "MLP / 8 frames",       "shared image+video encoder"),
        ("VILA-1.5",     "MLP / 8-16 frames",    "pretraining-heavy"),
        ("Qwen2.5-VL",   "TMRoPE / dynamic FPS", "absolute time, best open 2025"),
        ("LLaVA-OV-1.5", "pool / 32 frames",     "unified image+multi+video"),
    ]
```

- 这是一张**硬编码**的说明表，没有任何计算。讲义 "Use It" 说代码包含 "A comparison across Video-LLaMA (16 frames, Q-former), Video-LLaVA (8 frames, MLP), Qwen2.5-VL (dynamic FPS + TMRoPE)"，容易让人以为会对三种架构跑同一个评测，实际只是打印文字。
- 表中 "TMRoPE" 一列沿用讲义说法；第 20 节讲义则把 TMRoPE 归于 Qwen2.5-Omni，两节说法不一致（详见测验 Q14）。
- TAKEAWAY 第三条 "JSON grounded output beats free-text for downstream use"，与 skill 文件 "JSON is more robust" 一致，但与讲义正文 "Token-based is most accurate for downstream use" 相矛盾——学习时以"JSON 便于解析校验、特殊 time token 便于模型内部表达"来理解两者的分工即可。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用"每秒一个标量"模拟运动强度 | 不需要真实视频和光流库 | 真实系统用光流、帧差或镜头检测计算，粒度可以细到帧 |
| 动态抽帧按比例 + `round` + 保底 | 代码最短 | 预算不守恒（12 → 15、32 → 27）；应先扣保底再用最大余数法分配 |
| 每秒内均匀放点 | 简单 | 运动峰值可能集中在某一秒的前半段；可在帧差最大处取帧 |
| 时间 IoU + 固定阈值 0.3 | 业界最常见的 grounding 指标 | 应报多个阈值（0.3/0.5/0.7）和 mIoU |
| 只算 recall、非一对一 | 演示目的 | 生产评测必须一对一匹配并报 precision / F1，统计解析失败率 |
| 架构对比只打印表格 | 不依赖任何模型 | 真实对比需在 VideoMME、TempCompass 等基准上跑分 |
| `random.seed(4)` | 预留随机性 | 代码中没有任何随机调用，`random` 与 `math` 都是多余导入 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，在旧版本 Python 中也能写 `list[float]` |
| 类型注解 | `def iou(a_start: float, ...) -> float:` | 标明参数和返回值类型，不影响运行，方便阅读和 IDE 检查 |
| 内置泛型 | `list[float]`、`list[Event]` | Python 3.9+ 可直接用 `list[...]`，无需 `typing.List` |
| 默认参数 | `fps_cap: int = 4, total_budget: int = 32` | 调用时可省略 |
| `@dataclass` | `class Event: name: str; start: float; end: float` | 自动生成 `__init__`、`__repr__`、`__eq__`，适合"纯数据"对象 |
| 列表推导式 | `[round(step * (i + 0.5), 3) for i in range(n)]` | 一行生成列表 |
| `enumerate` | `for sec_idx, count in enumerate(samples_per_sec)` | 同时拿到下标和值 |
| 嵌套 `min` / `max` 夹取 | `min(fps_cap, max(1, round(raw)))` | 把值限制在 `[1, fps_cap]` 区间 |
| `round(x, 3)` 与银行家舍入 | `round(t, 3)`；`round(2.5) == 2` | 保留小数位；整数舍入时 .5 向偶数取整 |
| 条件表达式 | `inter / union if union > 0 else 0.0` | 一行 if-else，避免除零 |
| 元组解包 | `for name, val, hit in result["details"]` | 循环中直接拆开三元组 |
| f-string 格式符 | `{result['recall']:.2f}`、`{name:<6}`、`{r[0]:<14}` | 保留 2 位小数；左对齐并占 6 / 14 个字符宽 |
| 字符串乘法 | `"-" * 60` | 生成 60 个减号的分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 `import` 时不执行 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，Python 3，耗时不到 1 秒）：

```text
FRAME SAMPLING STRATEGIES
------------------------------------------------------------
  uniform   (8 frames / 10s) : [0.625, 1.875, 3.125, 4.375, 5.625, 6.875, 8.125, 9.375]
  motion    : [0.1, 0.1, 0.8, 0.9, 0.9, 0.2, 0.1, 0.5, 0.9, 0.9]
  dynamic (12 frames total): [0.5, 1.5, 2.25, 2.75, 3.25, 3.75, 4.25, 4.75, 5.5, 6.5, 7.5, 8.25, 8.75, 9.25, 9.75]
  dynamic places more frames in high-motion seconds 2-4 and 7-9

TEMPORAL GROUNDING EVAL (IoU >= 0.3)
------------------------------------------------------------
  recall@IoU0.3 : 0.33
    jump   IoU=0.57  HIT
    turn   IoU=0.29  miss
    sit    IoU=0.27  miss

VIDEO VLM ARCHITECTURES
  ...（静态表格，略）
```

逐项解读：

- **均匀抽帧**：`step = 1.25`，8 个中点均匀分布，与运动强度无关——第 2–4 秒的高运动段只分到 2–3 帧。
- **动态抽帧**：数一下列表共 **15** 个时刻，而不是标签上的 12。第 2、3、4、8、9 秒各 2 帧，其余 5 秒各 1 帧。第 7 秒（motion 0.5）只有 1 帧（7.5），所以"7-9 秒加密"的说法只对 8、9 秒成立。
- **grounding**：
  - `jump`：预测 `[4.1, 4.7]` vs 真值 `[4.0, 4.5]`，交集 0.4、并集 0.7 → 0.57，命中；
  - `turn`：预测 `[5.8, 6.2]` vs `[6.0, 6.5]`，0.2 / 0.7 = 0.286 → 打印 0.29，低于 0.3，miss；
  - `sit`：预测 `[9.2, 9.6]` vs `[8.5, 9.5]`，0.3 / 1.1 = 0.273 → miss；
  - recall = 1/3 = 0.33。这三个预测其实都"大致对"（中心偏差 0.15–0.4 秒），但短事件的 IoU 对小偏移极其敏感——这正是讲义说"Free text ... imprecise"、需要结构化时间输出的原因。若把阈值降到 0.25，recall 变为 1.0。
- **架构表**：纯文字，没有数值结果。

---

## 7. 动手改一改

1. **修预算**：把 `dynamic_sample` 改成严格遵守 `total_budget`（先扣每秒 1 帧保底，再按运动量分配剩余，最后用最大余数法补齐，参考测验 Q9）。验证预算 12/20/32 时返回帧数正好等于预算。
2. **多阈值评测**：让 `demo_grounding` 同时打印 IoU 0.3 / 0.5 / 0.7 下的 recall 和 mIoU（本例 mIoU = 0.377）。
3. **一对一匹配**：实现 `evaluate_grounding_v2`，输出 precision / recall / F1；往 `predictions` 里加 3 个乱猜的事件，观察新旧两个函数的差异。
4. **讲义练习 1**：构造一个 180 秒的 `motion` 列表（120 秒低运动、60 秒高运动），比较均匀 2 FPS 与动态 FPS 在高运动段的帧密度，按每帧 64 token 计算总 token 数。
5. **从 JSON 解析**：写一个 `parse_grounding(json_text, video_duration)`，把模型输出的 `{"events": [...]}` 解析成 `Event` 列表，并拒绝 `start >= end` 或超出视频时长的条目（讲义练习 3）。
6. **进阶**：用 OpenCV 读取一段真实视频，用相邻帧灰度差的均值作为每秒的 `motion`，把动态抽帧的结果和均匀抽帧的帧画面并排保存，直观感受差异。

---

## 8. 常见坑

- **以为动态抽帧一定省 token**：本实现的保底帧会让总帧数超过预算；动态 FPS 的意义是"同样预算下把帧放在该放的地方"，前提是分配算法守恒。
- **用帧序号当时间**：动态 FPS 下第 15 帧不等于第 15/FPS 秒，输出时间必须基于采样时刻表或时间戳位置编码换算。
- **短事件用高 IoU 阈值**：0.5 秒的事件偏移 0.2 秒就掉到 0.29；评测要按事件时长分桶，或者对瞬时事件改用"中心点误差 ≤ x 秒"。
- **评测只看 recall**：模型可以靠"多猜几个"刷高 recall，必须同时看 precision。
- **事件名精确匹配**：`jump` / `Jump` / `jumping` 会被当成不同事件，先做规范化或用标签集合约束输出。
- **把讲义里的命名当定论**：TMRoPE 在第 17 节被归于 Qwen2.5-VL，在第 20 节被归于 Qwen2.5-Omni；理解"按绝对时间戳分配时间位置"这一机制更重要。
