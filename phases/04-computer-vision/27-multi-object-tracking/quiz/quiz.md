# 测验 · 多目标跟踪与视频记忆（Multi-Object Tracking & Video Memory）

> **阶段 04 · 计算机视觉 · 第 27 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 跟踪 = 检测 + 关联 | 检测器只回答"这一帧哪里有物体"；跟踪器回答"第 t 帧的这个检测和第 t-1 帧的哪个是同一个物体"，并给出稳定的 ID |
| 2 | tracking-by-detection 循环 | 逐帧检测 → 运动预测（Kalman）→ 匈牙利匹配（IoU / 余弦 / 运动）→ 更新已匹配轨迹、为未匹配检测新建轨迹、未匹配轨迹老化并在 N 帧后删除 |
| 3 | 算法家族 | SORT（Kalman + IoU 匈牙利）→ DeepSORT（加 ReID 外观特征）→ ByteTrack（低置信度检测做第二阶段匹配）→ BoT-SORT（加相机运动补偿 + ReID）→ StrongSORT / OC-SORT |
| 4 | Kalman 滤波 | 每条轨迹维护状态 `(x, y, w, h, dx, dy, dw, dh)` 及协方差；匀速模型预测、用匹配检测更新；预测不确定性越大越信任检测；可穿越 1–5 帧的短遮挡 |
| 5 | 匈牙利算法 | 在 M×N 代价矩阵上求总代价最小的一对一匹配；代价常用 `1 - IoU` 或负余弦相似度；复杂度 O((M+N)³)；`scipy.optimize.linear_sum_assignment` |
| 6 | SAM 2 记忆跟踪 | 维护每实例的时空特征记忆库，新帧特征与记忆做 cross-attention，解码器直接输出同一实例的 mask；没有 Kalman、没有匈牙利，关联隐含在注意力中 |
| 7 | SAM 3.1 Object Multiplex | 把"每实例一个记忆库"合并为一个共享记忆 + 每实例 query token，成本随实例数亚线性增长，成为 2026 年人群跟踪的默认方案 |
| 8 | 三个指标 | MOTA = `1 - (FN + FP + IDSW) / GT`，把检测与关联错误混在一起；IDF1 = ID 精确率与召回率的调和平均，关注 ID 保持；HOTA 分解为 DetA 与 AssA，是 2020 年以来的社区标准 |
| 9 | 选型 | 行人 / 车辆 30+ fps → ultralytics + ByteTrack；同类大量实例的人群 → SAM 3.1 Multiplex；遮挡严重但外观可辨 → DeepSORT / StrongSORT；体育等复杂交互 → BoT-SORT 或学习型跟踪器 |

### 核心技能（能动手做到）

- [ ] 能用 NumPy 广播写出向量化的 `bbox_iou(a, b)`，返回 `(N_a, N_b)` 矩阵，并能手算两个框的 IoU
- [ ] 能用 `linear_sum_assignment` + IoU 门限实现一个 SORT 风格的最小跟踪器（匹配、新生、老化删除）
- [ ] 能解释为什么需要"门限设大代价 + 匹配后再检查"两步，而不能直接相信匈牙利的输出
- [ ] 能给跟踪器加上匀速运动预测，并用"20% 漏检"的合成数据验证 ID 切换减少
- [ ] 能写出简化的 ID 切换计数函数，并说明它与 MOTA / IDF1 / HOTA 的关系
- [ ] 能根据场景（帧率、遮挡、外观可区分度、实例数量）在 ByteTrack、DeepSORT、BoT-SORT、SAM 2、SAM 3.1 之间做选型

---

## 二、基础自测（选择题）

**Q1.** 在 tracking-by-detection 中，匈牙利算法的作用是：

- A. 训练检测器
- B. 预测下一帧的位置
- C. 过滤低置信度检测
- D. 在轨迹与检测之间求总代价最小的一对一匹配

**Q2.** ByteTrack 最核心的贡献是：

- A. 一个新的骨干网络
- B. 一个外观 embedding（ReID）
- C. 保留低置信度检测，在高置信度匹配之后，让未匹配的轨迹用稍宽松的 IoU 门限再和低置信度检测匹配一次
- D. 一个新的 Kalman 滤波器

**Q3.** SAM 2 的记忆跟踪器为什么不需要显式的匈牙利匹配？

- A. 它内部运行了 SORT
- B. 它把每个实例的时空特征存进记忆库，新帧特征与记忆做 cross-attention，解码器直接输出同一实例的 mask，关联隐含在注意力里
- C. 它使用 Kalman 滤波器
- D. 它要求每帧都人工标注 ID

**Q4.** 监控场景的首要需求是"每个人的 ID 在整段视频中保持一致"，应该重点报告哪个指标？

- A. Top-1 准确率
- B. MOTA
- C. IDF1
- D. FID

**Q5.** 某段视频共有 GT 目标实例 1000 个（逐帧累计），跟踪器产生 FN = 100、FP = 50、ID 切换 = 10，MOTA 是：

- A. 0.84
- B. 0.85
- C. 0.90
- D. 0.99

**Q6.** 关于 Kalman 滤波在跟踪中的作用，哪项说法**错误**？

- A. 用匀速模型预测每条轨迹在下一帧的状态
- B. 预测的不确定性越大，更新时越信任检测
- C. 能让轨迹穿过 1–5 帧的短暂遮挡
- D. 它通过比较外观特征来区分两个相互交叉的行人

**Q7.** 讲义的选型建议中，"仓库里大量穿同样工服的工人（同一类的大量实例）"最适合：

- A. SORT
- B. SAM 3.1 Object Multiplex
- C. 只用检测器，不做跟踪
- D. MiDaS

**Q8.** 关于 HOTA，下列说法正确的是：

- A. 它只衡量检测精度
- B. 它可以分解为检测精度（DetA）与关联精度（AssA），是 2020 年以来社区的标准指标
- C. 它就是 IDF1 的别名
- D. 它要求跟踪器输出 mask 才能计算

---

## 三、动手 / 代码题

**Q9.**（手算 + 解释）`main.py` 的匹配部分：

```python
        iou = bbox_iou(track_boxes, dets) if len(dets) else np.zeros((len(track_boxes), 0))
        cost = 1 - iou
        cost[iou < self.iou_threshold] = 1e6

        matched_track, matched_det = set(), set()
        if cost.size > 0:
            row, col = linear_sum_assignment(cost)
            for r, c in zip(row, col):
                if cost[r, c] < 1.0:
                    self.tracks[r].update(dets[c], frame)
```

1. 合成数据中的框都是 20×20。若物体每帧在 x、y 方向各移动 4 像素，相邻两帧的 IoU 是多少？能否通过 `iou_threshold=0.3`？
2. 若中间漏检了 1 帧（轨迹没有被更新，框停在原地），物体再出现时已移动了 8 像素（x、y 各 8），IoU 是多少？会发生什么？
3. 既然 `iou < 0.3` 的代价已经设成 `1e6`，为什么还要写 `if cost[r, c] < 1.0`？

**Q10.**（诊断）运行 `main.py` 得到：

```text
  3 objects:  active tracks=  3  ID switches=0
 10 objects:  active tracks= 10  ID switches=2
 30 objects:  active tracks= 70  ID switches=18
```

30 个物体却有 70 条活跃轨迹。请结合下面的合成数据代码分析原因，并给出修复：

```python
            cx, cy = starts[i] + f * velocities[i]
            x1 = max(0.0, cx - 10)
            y1 = max(0.0, cy - 10)
            x2 = min(float(W - 1), cx + 10)
            y2 = min(float(H - 1), cy + 10)
            box = [x1, y1, x2, y2]
            g.append((i, box))
            if rng.random() >= drop_prob:
                dets.append(box)
```

另外：10 个物体时没有新建任何多余的 ID（ID 总数恰好是 10），却仍有 2 次 ID 切换，这说明发生了什么？

**Q11.**（扩展）给跟踪器加上**匀速运动预测**（Kalman 的极简替代）：每条轨迹记住上一次更新时的速度（框坐标的逐帧差），关联前先把轨迹框外推到当前帧，用外推框和检测算 IoU。请写出 `CVTrack` 和 `CVTracker`（可继承 `main.py` 中的 `Track` 和 `SimpleTracker`），并在"5 个物体 + 20% 漏检"的场景下与 `SimpleTracker` 对比 ID 切换次数。

---

## 四、面试高频题

**Q12.**（基础必考）请讲一下 tracking-by-detection 的完整流程，以及 SORT、DeepSORT、ByteTrack 分别在前一代的基础上改进了什么。

**Q13.**（原理深挖）Kalman 滤波在 MOT 里具体做了什么？状态向量是什么？为什么用匀速模型？它在什么情况下会失效，业界怎么补救？

**Q14.**（原理深挖）SAM 2 的记忆跟踪和基于 IoU 的匈牙利关联相比，有什么本质区别和优缺点？SAM 3.1 Object Multiplex 又解决了什么问题？

**Q15.**（工程实践）MOTA、IDF1、HOTA 有什么区别？为什么一个跟踪器可能 MOTA 很高但 IDF1 很低？不同业务你会报告哪个？

**Q16.**（场景设计）设计一个路口车辆"过线计数"系统（统计每个方向每分钟通过的车辆数），要求实时。请给出模块选型、计数逻辑、如何避免重复计数和漏计，以及如何评估。

---

## 五、参考答案与解析

### Q1 — 答案：D

每一帧都要解一个指派问题：M 条轨迹、N 个检测，求一对一的最优匹配。匈牙利算法是这个问题的多项式时间最优解法，代价通常是 `1 - IoU`（重叠越大代价越低）。SORT、DeepSORT、ByteTrack、BoT-SORT 都用它。B 是运动模型（Kalman）的工作，C 是检测后处理。

### Q2 — 答案：C

大多数跟踪器直接丢弃置信度低于约 0.5 的检测。ByteTrack 把它们保留为**第二阶段候选**：先用高置信度检测和轨迹匹配，剩下没匹配上的轨迹再用稍宽松的 IoU 门限去匹配低置信度检测。被遮挡的物体置信度往往会掉下来，这一步正好把它们"捞回来"，减少短遮挡和人群附近的 ID 切换——而且不需要外观特征。

### Q3 — 答案：B

SAM 2 用"带记忆的分割器"取代了"先检测再关联"：记忆库保存实例在之前帧的特征，新帧特征与记忆做 cross-attention，解码器输出的就是同一个实例的 mask，不需要外部匹配步骤。因为记忆在实例消失多帧后依然保留，它对长时间遮挡更鲁棒。

### Q4 — 答案：C

IDF1 是 ID 精确率与 ID 召回率的调和平均，专门衡量"每个 GT 轨迹能否长期保持同一个 ID"。MOTA 把检测错误和关联错误混在一个数里，大量的 FN/FP 会掩盖 ID 问题。讲义建议：监控（谁是谁）报 IDF1；体育分析和学术对比报 HOTA。

### Q5 — 答案：A

`MOTA = 1 - (FN + FP + IDSW) / GT = 1 - (100 + 50 + 10) / 1000 = 1 - 0.16 = 0.84`。注意 10 次 ID 切换只贡献了 1% 的扣分，而 FN 贡献了 10%——这正是 MOTA 被批评"对 ID 问题不敏感"的原因。

### Q6 — 答案：D

Kalman 滤波只处理**运动**：用匀速模型预测，再用匹配到的检测更新，预测不确定性高时更信任观测，从而得到平滑轨迹，并能在 1–5 帧的短遮挡中"滑行"过去。比较外观特征是 DeepSORT 的 ReID 分支做的事，不是 Kalman 的职责。

### Q7 — 答案：B

讲义的选型建议："同一类大量实例的人群 → SAM 3.1 Object Multiplex"，并举例演唱会人群、仓库工人、交通路口。SORT 没有外观模型，在大量相似目标交叉时 ID 切换严重；C 无法给出 ID；D 是深度估计模型。

### Q8 — 答案：B

HOTA（Higher Order Tracking Accuracy）分解为 DetA（检测精度）和 AssA（关联精度），能同时、且分别地反映两类能力，是 2020 年以来社区的标准。它与 IDF1 不同（C 错），用框也能计算（D 错）。

### Q9 — 参考答案

1. 两个 20×20 的框错开 (4, 4)：交集 `(20-4) × (20-4) = 256`，并集 `400 + 400 - 256 = 544`，IoU = 256 / 544 ≈ **0.47** > 0.3，能匹配上。
2. 错开 (8, 8)：交集 `12 × 12 = 144`，并集 `800 - 144 = 656`，IoU ≈ **0.22** < 0.3。代价被设为 `1e6`，匹配失败；旧轨迹没被更新，检测被当作新物体，**分配新 ID**——对 GT 来说就是一次 ID 切换。这就是"没有运动预测"的代价：轨迹框停在原地，而物体在继续移动。（以上 IoU 已用 `bbox_iou` 验证。）
3. `linear_sum_assignment` 总会返回 `min(M, N)` 对匹配，**哪怕某些配对的代价是 `1e6`**——它只保证总代价最小，不会主动拒绝坏配对。所以要分两步：
   - 先把低于门限的配对代价设为一个极大值，让算法尽量避开它们；
   - 匹配后再检查 `cost[r, c] < 1.0`（任何合法配对的代价 `1 - IoU` ≤ 0.7 < 1），把被迫配上的坏配对剔除掉。

   只做第一步，坏配对会被错误地"更新"；只做第二步，大代价不参与优化，可能挤掉本该匹配的好配对。

### Q10 — 参考答案

**原因：离开画面的物体仍然输出"反向"的框。** 代码把框坐标裁剪到图像范围内，但没有判断物体是否已经完全出画。例如物体从下边出画，`cy - 10 > 239` 时 `y1 = cy - 10` 而 `y2 = 239`，得到 `y2 < y1` 的**退化框**（高度为负）。这些框仍然被当作"检测"送进跟踪器：

- 退化框在负的那个方向上与任何框的重叠长度都 ≤ 0，被 `np.clip(..., 0, None)` 截为 0，所以交集恒为 0、IoU 恒为 0（两个退化框之间，并集甚至可能是负数，被 `np.clip(union, 1e-8, None)` 截成 1e-8，结果仍是 0）；
- 所以它们**永远匹配不上任何轨迹**，每一帧都会被新建为一条新轨迹；
- 实际运行验证：30 个物体的场景中共有 83 个退化检测，累计创建了 120 个 ID，最后剩 70 条活跃轨迹。

**修复**：出画的物体不应产生检测（GT 中也应去掉或标记为不可见）：

```python
            box = [x1, y1, x2, y2]
            if x2 <= x1 or y2 <= y1:      # 完全出画：不可见
                continue
            g.append((i, box))
            if rng.random() >= drop_prob:
                dets.append(box)
```

验证：丢弃退化框后，活跃轨迹降到 23，ID 总数降到 37，但 ID 切换仍为 18——说明剩下的问题是**真实的关联失败**（物体密集、相互交叉），不再是数据假象。另外 `bbox_iou` 本身也可以对宽或高 ≤ 0 的框直接返回 0，作为防御。

**10 个物体、0 个多余 ID、2 次切换**：没有新建任何 ID，却有 GT 物体换了轨迹 ID，说明是**两条已有轨迹在两个物体交叉时互换了身份**（一次互换会让两个 GT 各记一次切换）。纯 IoU 关联没有运动方向和外观信息，两个框重叠时匈牙利算法只看当前帧的重叠量，很容易"接错"。这正是 Kalman（运动）和 ReID（外观）要解决的问题。

### Q11 — 参考答案

```python
import numpy as np
from scipy.optimize import linear_sum_assignment
from main import bbox_iou, Track, SimpleTracker, synthetic_frames, count_id_switches


class CVTrack(Track):
    def __init__(self, tid, bbox, frame):
        super().__init__(tid, bbox, frame)
        self.vel = np.zeros(4, dtype=np.float32)

    def predict(self, frame):
        # 按"距上次更新过去了几帧"外推
        return self.bbox + self.vel * (frame - self.last_frame)

    def update(self, bbox, frame):
        dt = frame - self.last_frame
        self.vel = (bbox - self.bbox) / max(dt, 1)
        super().update(bbox, frame)


class CVTracker(SimpleTracker):
    def step(self, detections, frame):
        dets = np.array(detections, dtype=np.float32) if len(detections) else np.empty((0, 4), dtype=np.float32)
        if not self.tracks:
            for d in dets:
                self.tracks.append(CVTrack(self.next_id, d, frame))
                self.next_id += 1
            return [(t.id, t.bbox.tolist()) for t in self.tracks]

        pred_boxes = np.array([t.predict(frame) for t in self.tracks])
        iou = bbox_iou(pred_boxes, dets) if len(dets) else np.zeros((len(pred_boxes), 0))
        cost = 1 - iou
        cost[iou < self.iou_threshold] = 1e6

        matched_det = set()
        if cost.size > 0:
            row, col = linear_sum_assignment(cost)
            for r, c in zip(row, col):
                if cost[r, c] < 1.0:
                    self.tracks[r].update(dets[c], frame)
                    matched_det.add(c)

        for i, d in enumerate(dets):
            if i not in matched_det:
                self.tracks.append(CVTrack(self.next_id, d, frame))
                self.next_id += 1

        self.tracks = [t for t in self.tracks if frame - t.last_frame <= self.max_age]
        return [(t.id, t.bbox.tolist()) for t in self.tracks]
```

实测（`max_age=3`，5 个物体，20% 漏检，5 个随机种子；格式为"(ID 切换, 累计 ID 数)"）：

| seed | SimpleTracker | CVTracker |
|------|---------------|-----------|
| 0 | (1, 24) | (0, 23) |
| 1 | (1, 12) | (0, 11) |
| 2 | (1, 6) | (0, 5) |
| 3 | (0, 5) | (0, 5) |
| 4 | (3, 8) | (0, 5) |

10 个物体无漏检的场景：SimpleTracker 2 次切换，CVTracker 0 次——运动预测同时缓解了漏检和交叉两类问题。

要点：
- 关键是**按时间间隔外推**：`self.vel * (frame - self.last_frame)`，漏检 1 帧就外推 2 步；
- 速度用 `(新框 - 旧框) / dt` 估计，`dt` 来自 `last_frame`，所以必须在调用 `super().update` **之前**计算；
- 这是"只有预测、没有协方差"的极简版本：真正的 Kalman 还会根据不确定性调节"信预测还是信检测"，对噪声检测更稳。

### Q12 — 参考回答要点

- **流程**：逐帧检测 → 对已有轨迹做运动预测 → 构建代价矩阵（`1 - IoU`、外观距离、运动距离）→ 匈牙利匹配 + 门限过滤 → 匹配的轨迹用检测更新；未匹配的检测新建轨迹；未匹配的轨迹老化，超过 `max_age` 帧删除。
- **演进**：
  - SORT（2016）：Kalman + IoU 匈牙利。简单、快，没有外观模型，交叉和遮挡时容易换 ID；
  - DeepSORT（2017）：为每条轨迹加一个 CNN 外观特征（ReID embedding），交叉时靠"长得像不像"区分；
  - ByteTrack（2021）：不靠外观，而是把低置信度检测作为第二阶段候选，捞回被遮挡、置信度下降的目标；在 MOT17 上表现顶尖；
  - BoT-SORT（2022）：Byte + 相机运动补偿 + ReID。
- 加分点：说明 "Every tracker you will encounter in 2026 is a variation on this loop"；生产上 ultralytics 内置 ByteTrack / BoT-SORT，一行 `model.track(source, tracker="bytetrack.yaml")`。

### Q13 — 参考回答要点

- **状态**：讲义给出的形式是 `(x, y, w, h, dx, dy, dw, dh)`——位置、尺寸及其各自的速度，外加协方差矩阵表示不确定性。
- **两步**：
  - 预测：用匀速模型把状态推到下一帧，协方差随之增大（不确定性增加）；
  - 更新：拿匹配到的检测作为观测，按"预测不确定性 vs 观测不确定性"加权融合——预测越不确定，越信任检测。
- **为什么匀速**：帧间隔很短（30 fps 时约 33 ms），大多数物体在这么短时间内近似匀速；模型线性，计算极便宜。
- **收益**：轨迹平滑；关联时用预测框而不是上一帧的旧框，提升 IoU；短遮挡（1–5 帧）时可以靠预测"滑行"。
- **失效场景与补救**：
  - 剧烈机动、非线性运动（球类、急转）→ 更强的运动模型或学习型跟踪器；
  - 相机自身运动（车载、手持）会让所有目标"一起动" → BoT-SORT 的相机运动补偿；
  - 长时间遮挡后预测发散 → 外观 ReID（DeepSORT / StrongSORT）或记忆型跟踪（SAM 2）；
  - OC-SORT 等后继工作专门改进了运动建模。

### Q14 — 参考回答要点

| 维度 | IoU + 匈牙利（SORT / ByteTrack） | SAM 2 记忆跟踪 |
|------|------------------------------|---------------|
| 关联方式 | 显式：代价矩阵 + 指派 | 隐式：记忆库与新帧 cross-attention |
| 运动模型 | 需要（Kalman） | 不需要 |
| 输出 | 框 + ID | mask + ID |
| 长遮挡 | 弱（预测发散、轨迹被删） | 强（记忆在实例消失多帧后仍保留） |
| 开放词表 | 取决于检测器 | 与 SAM 3 文本提示结合即可 |
| 速度 | 快，适合大量目标 | 多目标时比 ByteTrack 慢 |
| 其他代价 | 需要调门限、max_age | 记忆库会增长，限制上下文窗口 |

- **Object Multiplex**：之前 SAM 2 / SAM 3 每个实例一个记忆库，50 个目标就要 50 个；SAM 3.1 合并为一个共享记忆 + 每实例 query token，成本随实例数亚线性增长，让记忆型跟踪也能用于演唱会人群、仓库、路口这类密集场景。
- 常见误区：认为记忆型跟踪全面取代了经典跟踪——讲义的选型中，普通行人 / 车辆 30+ fps 仍然首选 ByteTrack。

### Q15 — 参考回答要点

- **MOTA** = `1 - (FN + FP + IDSW) / GT`：一个数同时包含检测错误和关联错误。由于 FN、FP 的数量通常远大于 ID 切换数，MOTA 主要反映检测质量。
- **IDF1**：在整段视频上把预测轨迹与 GT 轨迹做全局匹配，计算 ID 级别的精确率和召回率的调和平均，关注"谁是谁"。
- **HOTA**：分解为 DetA 与 AssA，两种能力分别可见，是 2020 年以来的社区标准。
- **为什么 MOTA 高而 IDF1 低**：检测器很强（FN、FP 很少），但轨迹频繁断开、换 ID。比如一个人被切成 5 段轨迹，每段都"检测正确"，MOTA 只扣了 4 次 IDSW，IDF1 却会因为 ID 不连续大幅下降（见 Q5：10 次切换只扣 1% MOTA）。
- **报告选择**（讲义）：监控（谁是谁）→ IDF1；体育分析（数传球）→ HOTA；学术对比 → HOTA。
- 工具：`py-motmetrics`、`TrackEval`；本节的 `count_id_switches` 只是一个简化的、接近 IDF1 思想的计数。

### Q16 — 参考回答要点

- **模块选型**：实时检测器（YOLO 系 / RT-DETR）+ ByteTrack（讲义："行人 / 车辆 30+ fps → ultralytics + ByteTrack"）；夜间、大车遮挡严重时考虑 BoT-SORT（ReID + 相机抖动补偿）。
- **计数逻辑**：
  - 在画面中定义有方向的计数线；对每条轨迹记录历史中心点；
  - 当轨迹中心在相邻两帧之间**从线的一侧跨到另一侧**时计数一次，并根据跨越方向区分车流方向；
  - 每个轨迹 ID 只计一次（维护"已计数 ID 集合"）。
- **避免重复与漏计**：
  - ID 切换会导致同一辆车被计两次 → 只对"已存在若干帧（`hits` 足够）"的稳定轨迹计数；在计数线附近加一个缓冲带，要求跨越后持续若干帧；
  - 遮挡导致漏检 → ByteTrack 的低置信度二次匹配 + Kalman 滑行；
  - 出画的目标及时结束轨迹，避免本节 Q10 中的"幽灵轨迹"。
- **评估**：人工标注若干段视频的真实过线数和轨迹 GT；业务指标看计数误差（按方向、按时段）；跟踪指标看 IDF1 和 ID 切换数（计数对 ID 切换最敏感）；压测端到端延迟和吞吐。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 06 物体检测——YOLO](../../06-object-detection-yolo/docs/zh.md)：逐帧检测器与 IoU 的定义。
- [阶段 04 · 08 实例分割——Mask R-CNN](../../08-instance-segmentation-mask-rcnn/docs/zh.md)：实例级输出与 mask。
- [阶段 04 · 24 SAM 3 与开放词表分割](../../24-sam3-open-vocab-segmentation/docs/zh.md)：SAM 3 的记忆跟踪器与 Object Multiplex 的来源。

### 本节被哪些后续内容用到
- [阶段 04 · 12 视频理解——时间建模](../../12-video-understanding/docs/zh.md)：视频中的时间维度建模。
- [阶段 04 · 20 图像检索和度量学习](../../20-image-retrieval-metric/docs/zh.md)：DeepSORT / StrongSORT 的 ReID 外观特征就是度量学习。
- [阶段 04 · 16 视觉流程 Capstone](../../16-vision-pipeline-capstone/docs/zh.md)：把检测 + 跟踪接入完整流水线。
- [阶段 04 · 28 世界模型与视频扩散](../../28-world-models-video-diffusion/docs/zh.md)：对象持久性（object permanence）在生成视频中的对应问题。
- [阶段 12 · 17 视频-语言时间定位](../../../12-multimodal-ai/17-video-language-temporal-grounding/docs/zh.md)：在视频中定位"何时、何物"。
- [阶段 19 · 12 视频理解流水线](../../../19-capstone-projects/12-video-understanding-pipeline/docs/zh.md)：工程化的视频分析项目。
- [阶段 01 · 22 随机过程](../../../01-math-foundations/22-stochastic-processes/docs/zh.md)：理解 Kalman 滤波背后的状态空间模型。

### 延伸关键词
`SORT` · `DeepSORT` · `ByteTrack` · `BoT-SORT` · `OC-SORT` · `StrongSORT` · `MOTRv3` · `ReID` · `相机运动补偿` · `MOT17` · `py-motmetrics` · `TrackEval` · `MOTA / IDF1 / HOTA`
