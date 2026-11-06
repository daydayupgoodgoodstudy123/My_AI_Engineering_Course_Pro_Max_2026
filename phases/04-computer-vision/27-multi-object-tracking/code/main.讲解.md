# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 27 节 多目标跟踪与视频记忆 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：`numpy`、`scipy`（`scipy.optimize.linear_sum_assignment`）；纯 CPU，不需要检测模型，无需联网

---

## 1. 这份代码在考察什么

讲义的开场白是"跟踪 = 检测 + 关联"。这份代码把"检测"换成合成的完美检测框，只练"关联"这一半，并刻意**不加 Kalman 运动预测**，让你看到最朴素的 IoU 关联在哪里开始失效：

1. **向量化 IoU**：用 NumPy 广播一次算出 M×N 的 IoU 矩阵——所有 tracking-by-detection 的代价矩阵都从这里来。
2. **匈牙利匹配 + 门限**：`linear_sum_assignment` 求一对一最优匹配，再用 IoU 门限拒绝坏配对。
3. **轨迹生命周期**：匹配上的更新、没匹配上的检测新生、长时间没更新的轨迹删除（`max_age`）。
4. **合成场景 + ID 切换计数**：3 / 10 / 30 个匀速运动物体、20% 随机漏检，统计 GT 物体"换了几次 ID"。
5. **观察失效模式**：目标变多 → 交叉增多 → ID 互换；漏检 → 没有运动预测 → 新 ID。

> 一句话：**这是一个"故意不完整"的 SORT**——去掉 Kalman 之后剩下的骨架，正好暴露出 Kalman、ByteTrack、ReID 各自要解决的问题。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `bbox_iou(a, b)` | 函数 | `(N_a, 4)` × `(N_b, 4)` → `(N_a, N_b)` IoU 矩阵 | 关联代价的基础 |
| `Track` | 类 | 一条轨迹：ID、当前框、最后更新帧、命中次数 | 轨迹状态 |
| `SimpleTracker` | 类 | `step(detections, frame)`：匹配 → 更新 → 新生 → 删除 | tracking-by-detection 循环（无 Kalman） |
| `synthetic_frames(...)` | 函数 | 生成匀速运动物体的逐帧检测与 GT，可随机漏检 | 合成测试数据 |
| `count_id_switches(...)` | 函数 | 统计每个 GT 物体被分配的轨迹 ID 变化了几次 | 简化的 ID 一致性指标（接近 IDF1 思想） |
| `main()` | 演示入口 | 3/10/30 个物体各跑一次；再跑 5 个物体 + 20% 漏检 | — |

数据流：`synthetic_frames` → 每帧 `dets` → `SimpleTracker.step` 返回 `[(track_id, bbox), ...]` → 收集成 `tracks_per_frame` → 与 `gt` 一起送入 `count_id_switches`。

---

## 3. 逐段精讲

### 3.1 `bbox_iou`：一次算完 M×N 个 IoU

```python
def bbox_iou(a, b):
    ax1, ay1, ax2, ay2 = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    bx1, by1, bx2, by2 = b[:, 0], b[:, 1], b[:, 2], b[:, 3]
    inter_x1 = np.maximum(ax1[:, None], bx1[None, :])
    inter_y1 = np.maximum(ay1[:, None], by1[None, :])
    inter_x2 = np.minimum(ax2[:, None], bx2[None, :])
    inter_y2 = np.minimum(ay2[:, None], by2[None, :])
    inter = np.clip(inter_x2 - inter_x1, 0, None) * np.clip(inter_y2 - inter_y1, 0, None)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a[:, None] + area_b[None, :] - inter
    return inter / np.clip(union, 1e-8, None)
```

- **广播技巧**：`ax1[:, None]` 形状 `(N_a, 1)`，`bx1[None, :]` 形状 `(1, N_b)`，两者做 `np.maximum` 会广播成 `(N_a, N_b)`——第 `(i, j)` 个元素就是第 i 个 a 框与第 j 个 b 框的交集左边界。没有任何 Python 循环。
- 交集矩形：左上角取两框左上角的**较大值**，右下角取右下角的**较小值**；宽或高为负说明不相交，用 `np.clip(..., 0, None)` 截为 0。
- `IoU = 交集 / (面积A + 面积B - 交集)`。分母用 `np.clip(union, 1e-8, None)` 防除零。
- 例：20×20 的框错开 (4, 4) 时 IoU ≈ 0.47，错开 (8, 8) 时 ≈ 0.22（测验 Q9）。
- ⚠️ 没有校验框是否合法（`x2 > x1`、`y2 > y1`）。退化框的交集恒为 0，IoU 恒为 0——这一点在 3.5 节会造成"幽灵轨迹"。

### 3.2 `Track`：轨迹的最小状态

```python
class Track:
    def __init__(self, tid, bbox, frame):
        self.id = tid
        self.bbox = bbox
        self.last_frame = frame
        self.hits = 1

    def update(self, bbox, frame):
        self.bbox = bbox
        self.last_frame = frame
        self.hits += 1
```

- 只存四样东西：ID、最新框、最后一次被更新的帧号、累计命中次数。
- `last_frame` 是生命周期管理的关键：`frame - last_frame` 就是"已经多少帧没见到它了"。
- `hits` 在本文件中没有被使用；在真实跟踪器里常用来做"轨迹确认"——连续命中 N 次才对外输出，过滤检测器的偶发误检。
- ⚠️ 与讲义中 Kalman 的状态 `(x, y, w, h, dx, dy, dw, dh)` 相比，这里**没有速度**，所以无法预测下一帧的位置——这是本代码最核心的刻意简化。

### 3.3 `SimpleTracker.step`：一帧的完整处理

```python
    def step(self, detections, frame):
        dets = np.array(detections, dtype=np.float32) if len(detections) else np.empty((0, 4), dtype=np.float32)
        if not self.tracks:
            for d in dets:
                self.tracks.append(Track(self.next_id, d, frame))
                self.next_id += 1
            return [(t.id, t.bbox.tolist()) for t in self.tracks]

        track_boxes = np.array([t.bbox for t in self.tracks])
        iou = bbox_iou(track_boxes, dets) if len(dets) else np.zeros((len(track_boxes), 0))
        cost = 1 - iou
        cost[iou < self.iou_threshold] = 1e6
```

- **冷启动**：没有任何轨迹时，所有检测直接成为新轨迹，ID 从 1 开始递增。
- `np.empty((0, 4))`：空检测时仍然构造一个"0 行 4 列"的数组，保证后续代码的形状处理统一，避免 `bbox_iou` 在空数组上出错。
- 代价矩阵 `cost = 1 - IoU`：重叠越大代价越小。
- **门限**：`iou < 0.3` 的配对代价设为 `1e6`，让匈牙利算法尽量避开它们。

```python
        matched_track, matched_det = set(), set()
        if cost.size > 0:
            row, col = linear_sum_assignment(cost)
            for r, c in zip(row, col):
                if cost[r, c] < 1.0:
                    self.tracks[r].update(dets[c], frame)
                    matched_track.add(r)
                    matched_det.add(c)
```

- `linear_sum_assignment(cost)` 返回两个等长数组 `row`、`col`，表示第 `row[k]` 条轨迹配给第 `col[k]` 个检测，总代价最小；它适用于非方阵，会给出 `min(M, N)` 对匹配。
- **为什么还要 `cost[r, c] < 1.0`**：匈牙利算法不会拒绝任何配对，即使代价是 `1e6` 也照样配上。所以必须事后检查，把"被迫配对"的坏配对过滤掉。合法配对的代价最多 `1 - 0.3 = 0.7`，用 1.0 做分界足够安全。
- `cost.size > 0`：轨迹或检测为空时跳过，避免在空矩阵上调用。
- `matched_track` 收集了但后面没用到；真实实现中会用它来给未匹配轨迹做"老化"计数或 Kalman 的纯预测。

```python
        for i, d in enumerate(dets):
            if i not in matched_det:
                self.tracks.append(Track(self.next_id, d, frame))
                self.next_id += 1

        self.tracks = [t for t in self.tracks if frame - t.last_frame <= self.max_age]
        return [(t.id, t.bbox.tolist()) for t in self.tracks]
```

- **新生**：没被匹配的检测都被当作新物体，分配新 ID。
- **死亡**：超过 `max_age` 帧没更新的轨迹被删除（列表推导式过滤）。`max_age=5` 意味着一条轨迹最多可以"失联"5 帧，期间如果物体重新出现且 IoU 够大，还能接上原 ID。
- 返回值包括**所有存活轨迹**，也包括本帧没匹配上、框停在旧位置的轨迹。
- ⚠️ 没有运动预测：失联期间轨迹框停在原地，而物体在继续移动。漏检 1 帧，物体位移翻倍，IoU 从 0.47 掉到 0.22，接不上了——于是"失联容忍期"（`max_age`）形同虚设。这正是讲义说"in production the Kalman predict is essential"的原因。
- ⚠️ 新生时机：讲义的流程图是"先新生、再删除"，本代码也是；新建的轨迹 `last_frame = frame`，不会被立刻删掉。

### 3.4 `synthetic_frames`：匀速物体 + 随机漏检

```python
def synthetic_frames(num_frames=25, num_objects=3, H=240, W=320, seed=0, drop_prob=0.0):
    rng = np.random.default_rng(seed)
    starts = rng.uniform(20, 200, size=(num_objects, 2))
    velocities = rng.uniform(-4, 4, size=(num_objects, 2))
    gt = []
    frames = []
    for f in range(num_frames):
        g = []
        dets = []
        for i in range(num_objects):
            cx, cy = starts[i] + f * velocities[i]
            x1 = max(0.0, cx - 10)
            y1 = max(0.0, cy - 10)
            x2 = min(float(W - 1), cx + 10)
            y2 = min(float(H - 1), cy + 10)
            box = [x1, y1, x2, y2]
            g.append((i, box))
            if rng.random() >= drop_prob:
                dets.append(box)
        gt.append(g)
        frames.append(dets)
    return frames, gt
```

- 每个物体：起点在 `[20, 200)²`，速度每轴 `[-4, 4)` 像素/帧，框大小 20×20，以中心 `(cx, cy)` 为准。
- GT 中每帧都有所有物体（带 GT ID `i`）；检测则以 `drop_prob` 的概率随机丢弃，模拟漏检 / 遮挡。
- 框坐标被裁剪到图像范围内（`max(0, ...)`、`min(W-1, ...)`），模拟物体部分出画。
- ⚠️ **出画后的退化框**：裁剪只处理了"部分出画"。当物体**完全出画**（比如 `cy - 10 > 239`）时，会得到 `y1 > y2` 的反向框，但它仍然被写进 GT 和检测里。这类框与任何框的 IoU 都是 0，永远匹配不上，于是每帧都会被新建为一条新轨迹。实测：30 个物体的场景中有 83 个这样的退化检测，累计新建了 120 个 ID；漏检场景（5 个物体）中也有 18 个退化检测、累计 24 个 ID。修复：`if x2 <= x1 or y2 <= y1: continue`（见测验 Q10）。
- 25 帧内物体最多移动约 `24 × 4 = 96` 像素，起点在 20–200 之间：x 方向大多仍在 320 宽的画面内，但 y 方向最高可到约 296，超过 240 的图像高度——所以物体多时，从下边出画的情况很常见。

### 3.5 `count_id_switches`：简化的 ID 一致性指标

```python
def count_id_switches(tracks_per_frame, gt_per_frame):
    prev_assignment = {}
    switches = 0
    for tracks, gts in zip(tracks_per_frame, gt_per_frame):
        if not tracks or not gts:
            continue
        t_boxes = np.array([b for _, b in tracks])
        g_boxes = np.array([b for _, b in gts])
        iou = bbox_iou(g_boxes, t_boxes)
        for g_idx, (gt_id, _) in enumerate(gts):
            j = int(iou[g_idx].argmax())
            if iou[g_idx, j] > 0.5:
                t_id = tracks[j][0]
                if gt_id in prev_assignment and prev_assignment[gt_id] != t_id:
                    switches += 1
                prev_assignment[gt_id] = t_id
    return switches
```

- 对每个 GT 物体，找本帧与它 IoU 最大的预测轨迹；IoU > 0.5 才认为"它被这条轨迹覆盖"。
- `prev_assignment` 字典记录"GT ID → 上次对应的轨迹 ID"；如果这次对应的轨迹 ID 变了，计一次切换。
- 讲义称之为"简化的、接近 IDF1 思想的指标"：真正的 MOTA / IDF1 / HOTA 要用 `py-motmetrics` 或 `TrackEval`。
- ⚠️ 简化之处：
  - 用 `argmax` 而不是一对一匹配，同一条轨迹可能同时"覆盖"两个重叠的 GT；
  - IoU ≤ 0.5（如漏检、退化框）的帧直接跳过，不计 FN；
  - 返回的轨迹列表里包含"框停在原地"的失联轨迹，它们也可能被选中。

### 3.6 `main()`：两组实验

- **实验 1**：3、10、30 个物体，无漏检，默认 `max_age=5`。每次都新建 `SimpleTracker`，逐帧 `step`，最后打印活跃轨迹数和 ID 切换数。
- **实验 2**：5 个物体，20% 漏检，`max_age=3`。
- `f"{n_obj:>3d}"`：右对齐占 3 位，让表格对齐。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不做 Kalman 预测 | 代码短，专注"关联"本身；让失效模式暴露出来 | 漏检、交叉时 ID 切换；生产必须加 Kalman（或至少匀速外推） |
| 合成的完美检测框 | 排除检测误差，只评估关联 | 真实检测有噪声、有置信度，需要 ByteTrack 式的分层匹配 |
| `1 - IoU` 代价 + 门限 `1e6` + 事后检查 | 匈牙利算法不会主动拒绝坏配对 | 可叠加外观距离（ReID 特征）与基于 Kalman 预测的运动门限（DeepSORT 的做法） |
| `max_age` 删除 | 防止轨迹无限增长 | 没有预测时失联期形同虚设；`hits` 未用于轨迹确认 |
| 向量化 IoU | 一次算出 M×N，速度快 | 未校验退化框 |
| 自写的 ID 切换计数 | 直观、零依赖 | 不是标准指标；正式评测用 `py-motmetrics` / `TrackEval` 报告 MOTA、IDF1、HOTA |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组解包 | `ax1, ay1, ax2, ay2 = a[:, 0], ...`、`cx, cy = starts[i] + f * velocities[i]` | 一次赋多个值；右边是长度为 2 的数组也能解包 |
| NumPy 列切片 | `a[:, 0]` | 取所有行的第 0 列 |
| `None` 增维与广播 | `ax1[:, None]`、`bx1[None, :]` | 插入长度为 1 的维度，使 `(N,1)` 与 `(1,M)` 广播成 `(N,M)` |
| `np.maximum` / `np.minimum` / `np.clip` | `np.clip(union, 1e-8, None)` | 逐元素取大/取小；`None` 表示该侧不设界 |
| 条件表达式 | `np.array(...) if len(detections) else np.empty((0, 4), ...)` | 一行 if-else |
| 布尔索引赋值 | `cost[iou < self.iou_threshold] = 1e6` | 把满足条件的元素统一改值 |
| 类与实例属性 | `self.next_id = 1`、`self.tracks = []` | 在 `__init__` 中初始化对象状态 |
| `set` | `matched_det = set()`、`if i not in matched_det` | 集合的成员判断是 O(1) |
| 多变量同时赋值 | `matched_track, matched_det = set(), set()` | 两个独立的空集合 |
| `zip` / `enumerate` | `for r, c in zip(row, col)`、`for i, d in enumerate(dets)` | 并行遍历 / 带下标遍历 |
| 列表推导式（过滤） | `[t for t in self.tracks if frame - t.last_frame <= self.max_age]` | 一行完成过滤并重建列表 |
| `ndarray.tolist()` | `t.bbox.tolist()` | NumPy 数组转回 Python 列表，便于打印和序列化 |
| 字典 `in` 判断 | `if gt_id in prev_assignment and prev_assignment[gt_id] != t_id` | 先判断键存在再取值，利用 `and` 短路 |
| `int(...)` 转换 | `j = int(iou[g_idx].argmax())` | 把 NumPy 整数转成 Python `int` |
| f-string 对齐 | `f"{n_obj:>3d}"`、`f"{len(tracker.tracks):3d}"` | `>3d` 右对齐占 3 位 |
| 新式随机数生成器 | `np.random.default_rng(seed)`、`rng.uniform(...)`、`rng.random()` | 固定种子可复现 |
| 默认参数 | `def synthetic_frames(num_frames=25, ..., drop_prob=0.0)` | 调用时可按名字覆盖 |

---

## 6. 运行结果解读

在临时副本中实际运行（Python 3.13 + NumPy 2.5 + SciPy 1.18，耗时不到 1 秒）：

```text
  3 objects:  active tracks=  3  ID switches=0
 10 objects:  active tracks= 10  ID switches=2
 30 objects:  active tracks= 70  ID switches=18

With frame dropouts (drop_prob=0.2):
  5 objects + 20% dropouts:  ID switches=1
```

逐行解读：

- **3 个物体**：物体稀疏、不交叉，每帧位移最多约 5.7 像素（相邻帧 IoU ≥ 0.47），纯 IoU 关联完全够用：0 次切换。
- **10 个物体**：轨迹数恰好是 10，没有新建任何多余 ID，却有 2 次切换——说明是**两条已有轨迹在两物体交叉时互换了身份**（一次互换会让两个 GT 各记一次切换）。没有运动方向和外观信息，重叠时匈牙利只看当前帧的 IoU，容易接错。
- **30 个物体**：70 条活跃轨迹远多于 30 个物体。主要原因是 3.4 节说的**出画退化框**：完全出画的物体仍然产生 `y1 > y2` 的反向框，永远匹配不上，每帧都新建一条轨迹（累计新建 120 个 ID）。我额外验证过：丢弃退化框后活跃轨迹降为 23、累计 ID 37，但 ID 切换仍为 18——剩下的是密集场景下真实的交叉 / 互换问题。
- **5 个物体 + 20% 漏检**：1 次切换。漏检时轨迹框停在原地，物体再出现时已经移动了两倍距离，IoU 掉到门限以下，于是被当成新物体。测验 Q11 中加入匀速外推后，这个场景（以及 10 个物体的交叉场景）的 ID 切换都降为 0。

这正好对应讲义练习 1 的问题"找出纯 IoU 关联从哪里开始失效"：**目标密度上升（交叉）和漏检（无预测）**是两个主要失效点；另外要警惕测试数据本身的问题（出画退化框）对结论的干扰。

---

## 7. 动手改一改

1. **修数据**：在 `synthetic_frames` 中跳过完全出画的物体（`x2 <= x1 or y2 <= y1`），重新运行，对比活跃轨迹数。
2. **防御性 IoU**：让 `bbox_iou` 对宽或高 ≤ 0 的框直接返回 0，并为它写一个单元测试。
3. **匀速外推**：实现测验 Q11 的 `CVTrack` / `CVTracker`，比较 3/10/30 个物体和漏检场景下的 ID 切换。
4. **轨迹确认**：利用 `hits`，只有命中 ≥ 3 次的轨迹才输出，观察对"幽灵轨迹"的抑制效果。
5. **ByteTrack 第二阶段**：给检测加上置信度（漏检改成"低置信度检测"而不是丢弃），实现"先匹配高置信度、再用剩余轨迹匹配低置信度（门限稍宽）"的两阶段关联。
6. **标准指标**：把 `tracks_per_frame` 和 `gt` 转成 `py-motmetrics` 需要的格式（如果你本地已安装），计算 MOTA、IDF1，与自写的切换计数对照。

---

## 8. 常见坑

- **相信匈牙利的全部输出**：`linear_sum_assignment` 不会拒绝坏配对，必须在匹配后按代价/IoU 门限过滤。
- **没有运动预测**：轨迹框停在旧位置，漏检一两帧就接不上；`max_age` 再大也没用。
- **退化框混入数据**：出画、裁剪后的反向框 IoU 恒为 0，会制造大量"幽灵轨迹"，让指标看起来比真实情况糟得多。
- **框格式不统一**：本文件统一用 `[x1, y1, x2, y2]`；如果检测器输出 `[cx, cy, w, h]` 或 `[x, y, w, h]`，不转换就算 IoU 会得到完全错误的结果。
- **只看 ID 切换数**：它不包含漏检、误检，也不是一对一匹配；正式评测请用 MOTA / IDF1 / HOTA。
- **`max_age` 与帧率脱钩**：`max_age=5` 在 30 fps 下约 0.17 秒，在 5 fps 下是 1 秒——参数要随帧率调整。
