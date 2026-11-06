# 测验 · 物体检测——从头开始的 YOLO（Object Detection — YOLO from Scratch）

> **阶段 04 · 计算机视觉 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 检测 = 稠密预测 | 分类每张图输出 C 个数；YOLO 式检测器每张图输出 `S×S×B×(5+C)` 个数，每个网格、每个 anchor 都做一次"分类 + 回归" |
| 2 | 网格负责制 | 每个 ground-truth（GT）框只由其**中心点所在的格子**负责，避免"整图平移导致所有预测一起平移"的回归难题 |
| 3 | Anchor（先验框） | 每个格子预定义 B 个形状先验，网络只回归相对 anchor 的小偏移 `tw, th`，而不是从零回归绝对宽高 |
| 4 | 解码公式 | `cx = (sigmoid(tx)+cell_x)·stride`，`w = anchor_w·exp(tw)`；sigmoid 把中心锁在格子内，exp 保证宽高为正并做乘性缩放 |
| 5 | IoU | `IoU = 交集面积 / 并集面积`，既用来判 TP/FP（通常 ≥0.5），也用来给 NMS 去重 |
| 6 | NMS | 贪心：按分数排序 → 保留最高分 → 删除与它 IoU 超过阈值的框 → 重复；它只删不合并 |
| 7 | 三部分损失 | box 回归 + objectness（正/负）+ 分类；只有正样本贡献 box/cls 损失，`λ_coord=5、λ_noobj=0.5` 用来平衡梯度量级 |
| 8 | 检测指标 | Precision/Recall@0.5、AP@0.5（VOC）、mAP@0.5:0.95（COCO）；两个 mAP 差距大 ⇒ 定位不够紧 |

### 核心技能（能动手做到）

- [ ] 用 NumPy 广播写出向量化 `box_iou`，输入 `(N,4)` 与 `(M,4)`，输出 `(N,M)` 矩阵，并手算验证"半重叠 = 1/3"
- [ ] 从零实现贪心 NMS，能在纸上推出 5 个框在阈值 0.4 / 0.7 下各保留哪些
- [ ] 实现 `encode / decode` 一对函数，让 GT 框编码再解码的最大误差小于 `1e-3` 像素（理解为什么 encode 要取 logit）
- [ ] 写出 `YOLOHead`，说清 `view(n, A, 5+C, h, w)` → `permute(0,3,4,1,2)` 每一步张量形状
- [ ] 实现 `assign_targets`：用"形状 IoU"为每个 GT 选最佳 anchor，并写出它在目标张量里的 10 个数
- [ ] 实现 `yolo_loss` 的四项（box / obj_pos / obj_neg / cls），解释每一项只在哪些位置计算
- [ ] 拿到一行 `precision, recall, mAP@0.5, mAP@0.5:0.95` 指标，能说出最该调的一个旋钮

---

## 二、基础自测（选择题）

**Q1.** 输入 640×640，检测头所在特征图 stride=32，每格 3 个 anchor，COCO 80 类。检测头 1×1 卷积输出的空间尺寸和通道数分别是：

- A. 20×20，255
- B. 20×20，85
- C. 32×32，255
- D. 13×13，255

**Q2.** 解码时宽度写成 `w = anchor_w · exp(tw)`，而不是 `w = anchor_w + tw`。最主要的原因是：

- A. `exp` 的梯度更大，训练更快
- B. 保证宽度恒为正；`tw=0` 恰好等于 anchor 尺寸；在对数空间回归让"放大 2 倍"对大框小框是同样难度
- C. 因为 sigmoid 不能处理宽度
- D. 为了把框限制在当前格子内

**Q3.** 框 `[0,0,10,10]` 与 `[5,5,15,15]`（`x1,y1,x2,y2` 格式）的 IoU 是：

- A. 0.25
- B. 约 0.143
- C. 0.5
- D. 约 0.333

**Q4.** 把 NMS 的 `iou_threshold` 从 0.45 提高到 0.7，最可能的结果是：

- A. 保留的框变少，因为阈值更严格
- B. 保留的框变多：只有与胜出框 IoU > 0.7 的框才会被删，密集重叠目标更容易保住，但重复框也会变多
- C. 框的数量不变，只是分数变了
- D. NMS 会开始把重叠框合并成一个平均框

**Q5.** YOLOv1 风格的 `λ_noobj = 0.5`（小于 1）主要是为了：

- A. 负样本比正样本更重要，需要单独强调
- B. 绝大多数 (格子, anchor) 位置是空的，负样本 objectness 损失的总量会压倒正样本信号，必须降权
- C. 节省显存
- D. BCE 对负样本的梯度在定义上就更大

**Q6.** 某检测器在验证集上 Precision@0.5 = 0.92、Recall@0.5 = 0.41。按讲义的诊断思路，下一步最该先试的是：

- A. 提高置信度阈值，让输出更"干净"
- B. 降低置信度阈值，或提高 objectness 的权重
- C. 把 NMS 阈值降到 0.2
- D. 降低 `λ_coord`

**Q7.** `assign_targets` 里计算 GT 与 anchor 的 IoU 时只用了 `inter = min(bw, aw) * min(bh, ah)`，完全没用到坐标。这意味着：

- A. 代码有 bug，应该用完整的 `box_iou`
- B. 这是"形状 IoU"：假设两个框中心（对齐）重合，只比较宽高形状；位置问题已经由"中心所在格子"解决了
- C. 这是 GIoU
- D. 这是在比较中心点距离

**Q8.** 关于 mAP@0.5:0.95，下列说法**错误**的是：

- A. 它是 IoU 阈值取 0.50, 0.55, …, 0.95 共 10 个值时 AP 的平均
- B. 同一个模型，它一般不会高于 AP@0.5
- C. mAP@0.5 很高而 mAP@0.5:0.95 很低，说明框找到了但不够贴合
- D. 当每张图只有一个目标时，它就等于分类准确率

---

## 三、动手 / 代码题

**Q9.** 不运行代码，写出下面两次 `nms` 调用的输出，并给出关键 IoU 的计算过程。

```python
boxes = np.array([
    [0, 0, 10, 10],
    [1, 1, 11, 11],
    [2, 2, 12, 12],
    [20, 20, 30, 30],
    [21, 21, 31, 31],
], dtype=float)
scores = np.array([0.9, 0.8, 0.7, 0.85, 0.6])
print(nms(boxes, scores, iou_threshold=0.4).tolist())
print(nms(boxes, scores, iou_threshold=0.7).tolist())
```

**Q10.** 讲义 Step 3 的 `encode` 写的是 `tx = cx / stride - cell_x`（直接存格内偏移），而 `code/main.py` 改成了：

```python
    off_x = np.clip(cx / stride - cell_x, 1e-6, 1 - 1e-6)
    off_y = np.clip(cy / stride - cell_y, 1e-6, 1 - 1e-6)
    tx = float(np.log(off_x / (1 - off_x)))
    ty = float(np.log(off_y / (1 - off_y)))
```

(a) 如果沿用讲义版 encode，而 decode 依旧是 `(sigmoid(tx) + cell_x) * stride`，stride=32、格内偏移为 0.05 时，解码后的中心会偏多少像素？
(b) 为什么要 `np.clip(..., 1e-6, 1 - 1e-6)`？
(c) 即使用了 logit 版本，这种"在 logit 空间里做 MSE"还有什么隐患？

**Q11.** 解释 `YOLOHead.forward` 中下面两行为什么不能合并成一句 `y.view(n, h, w, self.num_anchors, 5 + self.num_classes)`，`.contiguous()` 又起什么作用？在 `main()` 的设置下（`in_c=128, num_anchors=3, num_classes=5`，输入 `(1,128,13,13)`），输出形状是什么？

```python
        y = y.view(n, self.num_anchors, 5 + self.num_classes, h, w)
        y = y.permute(0, 3, 4, 1, 2).contiguous()
```

**Q12.** `postprocess` 里的 NMS 是**类别无关**的：一只猫和一只狗的框若高度重叠，分数低的那个会被误删。请复用本文件的 `nms`，写一个类别感知的 `batched_nms(boxes, scores, classes, iou_threshold)`，要求只调用一次 `nms`。

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述一个 YOLO 式单阶段检测器从输入图像到最终框的流程；它和 Faster R-CNN 这类两阶段检测器的核心区别是什么？

**Q14.**（原理深挖）Anchor 解决了什么问题？anchor 尺寸一般怎么定？现在的 anchor-free 检测器（如 FCOS、YOLOv8）是怎么去掉 anchor 的，代价是什么？

**Q15.**（原理深挖）手写 NMS 的复杂度是多少？NMS 有哪些固有缺陷？有哪些改进方案？

**Q16.**（工程实践）请讲清楚某一类的 AP 是怎么算出来的，以及 COCO 的 mAP@0.5:0.95 在此基础上多做了什么。评估时置信度阈值应该怎么设？

**Q17.**（场景设计）你要在 4K 无人机航拍图上检测行人和车辆，目标普遍只有 10–30 像素，现成 YOLO 模型召回很低。你会怎么改？

**Q18.**（追问型）为什么现代 YOLO 把 box 回归从 MSE 换成 IoU 系列损失（GIoU / DIoU / CIoU）？它们分别补上了什么缺口？

---

## 五、参考答案与解析

### Q1 — 答案：A

网格边长 `640 / 32 = 20`；每格通道数 `B × (5 + C) = 3 × (5 + 80) = 255`。B 是单个 anchor 的维度（5+C=85），忘了乘 anchor 数；C 把 stride 当成了网格数；D 是 416 输入时的网格大小（416/32=13）。

### Q2 — 答案：B

`exp(tw) > 0` 天然保证宽度为正，不会出现"负宽度"导致的符号翻转；`tw = 0` 时 `w = anchor_w`，网络初始化附近的输出就对应"原样使用 anchor"；而且 `log(w / anchor_w)` 是**相对尺度**，把 30 像素放大成 60 和把 300 放大成 600 对应同一个 `tw = ln2`，回归难度与绝对尺寸无关。D 是 sigmoid 对 `tx, ty` 的作用，不是 exp 的。

### Q3 — 答案：B

交集是 `[5,5,10,10]`，面积 25；两框面积各 100，并集 `100 + 100 − 25 = 175`；IoU = `25/175 = 1/7 ≈ 0.143`。最常见的错误是把并集算成 200（忘了减交集），得到 0.125；或者以为"各重叠一半"就是 0.25 / 0.5。

### Q4 — 答案：B

阈值是"删除条件"的门槛：IoU **大于**阈值才删。门槛从 0.45 提到 0.7，被删的框更少，保留的更多。好处是两个真实重叠的目标（如拥挤人群）更不容易互相误删；坏处是同一目标的重复框也更容易留下来，precision 下降。D 错在 NMS 只删除、不合并——合并是 Weighted Box Fusion 之类的另一种算法。

### Q5 — 答案：B

13×13 网格、3 个 anchor 就有 507 个位置，一张图通常只有 1–5 个正样本，其余 500 多个都在贡献"预测为 0"的 objectness 损失。不降权的话，这一项的总量远大于正样本项，模型最省事的解是"处处预测无目标"。反过来 `λ_coord = 5` 把数值偏小的 box 回归损失放大：两个系数本质上都是在让各分量的梯度量级可比。

### Q6 — 答案：B

高 precision、低 recall = 模型"太保守"：报出来的基本都对，但大量真实目标没报。讲义给出的处方就是降低置信度阈值或提高 objectness 权重。A 会让 recall 更低；C 会让 NMS 删得更狠，recall 也更低；D 影响的是框的定位精度，不是"报不报"。

### Q7 — 答案：B

`min(bw,aw)·min(bh,ah)` 就是两个框**中心对齐**（或左上角对齐）时的交集面积，所以这是只比较形状的 IoU。它是 YOLOv2/v3 的 anchor 分配方式：位置由"中心所在格子"决定，anchor 只负责形状，因此无需坐标。用完整 `box_iou` 反而会让 anchor 的位置（格子中心）干扰形状选择。

### Q8 — 答案：D

A、B、C 都对：IoU 阈值越高，同一检测被判为 TP 的条件越苛刻，AP 单调不增，所以 10 个阈值的平均 ≤ AP@0.5。D 错：mAP 是 precision-recall 曲线下的面积，同时惩罚误报（FP）、漏报（FN）和定位不准（IoU 不够）；分类准确率完全不考虑框的位置与误报数量，讲义原话是"Accuracy does not transfer to detection"。

### Q9 — 参考答案

输出：

```text
[0, 3]
[0, 3, 1, 2, 4]
```

关键 IoU：
- box0 vs box1：交集 `[1,1,10,10]` = 9×9 = 81；并集 = 100+100−81 = 119；IoU = **0.681**。
- box0 vs box2：交集 `[2,2,10,10]` = 8×8 = 64；并集 = 136；IoU = **0.471**。
- box1 vs box2、box3 vs box4：同理都是 0.681；两组框之间 IoU = 0。

按分数排序：`0(0.9), 3(0.85), 1(0.8), 2(0.7), 4(0.6)`。

- 阈值 0.4：选 0 → 删掉 1（0.681>0.4）和 2（0.471>0.4）；剩 `[3, 4]`，选 3 → 删 4。结果 `[0, 3]`（与 `main()` 中注释的 expected 一致）。
- 阈值 0.7：所有 IoU 都 ≤ 0.7，一个都不删，按分数顺序全部保留：`[0, 3, 1, 2, 4]`。注意返回的是**按分数排序后的下标**，而不是原始顺序。

（已用 NumPy 抽取 `nms`/`box_iou` 实际运行验证。）

### Q10 — 参考答案

(a) 讲义版把偏移 0.05 直接当 `tx` 存起来，解码时却算 `sigmoid(0.05) ≈ 0.5125`，中心偏差 `(0.5125 − 0.05) × 32 ≈ 14.8` 像素——几乎半个格子。偏移越靠近 0 或 1，误差越大（偏移 0.95 时约 −7.3 像素）；偏移在 0.5 附近时误差也有约 3.9 像素。根本原因是 encode 与 decode 不是互逆函数：decode 里有 sigmoid，encode 就必须用它的反函数 `logit(p) = ln(p/(1−p))`。`main.py` 的 encode/decode 往返误差约 `8.5e-7` 像素（来自 `log(w/aw + 1e-8)` 里那个 `1e-8`）。

(b) `logit` 在 `p = 0` 时是 `ln 0 = −∞`，在 `p = 1` 时分母为 0 → `+∞`。GT 中心恰好落在格子边界（如 `cx/stride` 是整数）时偏移正好是 0，必须夹到 `[1e-6, 1−1e-6]`，最坏得到约 ±13.8 的有限值。

(c) 回归目标在 logit 空间里是无界的：偏移 0.5 对应 0，偏移 0.999 对应约 6.9，偏移 1e-6 对应约 −13.8。中心靠近格子边缘的 GT 会产生巨大的 MSE，把 box 损失拉偏，而它在像素空间里其实只差一点点。因此很多实现选择在 sigmoid **之后**的空间里与偏移比较（例如 `MSE(sigmoid(tx), offset)`），或者干脆改用 IoU 类损失在解码后的框上直接优化（见 Q18）。

### Q11 — 参考答案

1×1 卷积的输出布局是 `(n, A·(5+C), h, w)`：通道维在第 1 维，且通道按"anchor 优先"排列——前 `5+C` 个通道属于 anchor 0，接下来 `5+C` 个属于 anchor 1……

- `view` 只是按内存顺序**重新解释形状**，不会搬动数据。内存里最内层是 `w`、其次 `h`、最外层是通道，所以只能先把通道维拆成 `(A, 5+C)`，得到 `(n, A, 5+C, h, w)`——这一步语义正确。
- 若直接 `view(n, h, w, A, 5+C)`，元素个数相同不会报错，但会把"某个通道的一整行像素"误当成"某个格子的 5+C 个属性"，语义全乱，是**静默错误**。
- 正确做法是 `permute(0, 3, 4, 1, 2)` 把维度重排成 `(n, h, w, A, 5+C)`。`permute` 只改步长（stride）不搬数据，得到的张量**不连续**；`.contiguous()` 真正按新顺序拷贝一份内存，之后再 `view` 或做高效切片才不会报错。

`main()` 中输出形状为 `(1, 13, 13, 3, 10)`（`5 + 5 = 10`），对应 `target` 的形状 `(13, 13, 3, 10)`。

### Q12 — 参考答案

经典的"坐标偏移"技巧：给每个类别的框加一个足够大的平移量，让不同类别的框在坐标上永不相交，于是一次 NMS 就等价于逐类 NMS。

```python
import numpy as np

def batched_nms(boxes, scores, classes, iou_threshold=0.45):
    if len(boxes) == 0:
        return np.zeros((0,), dtype=np.int64)
    max_coord = boxes.max()
    offsets = classes.astype(boxes.dtype) * (max_coord + 1)  # 每个类别平移到互不重叠的区域
    shifted = boxes + offsets[:, None]                       # 4 个坐标同时平移，框形状不变
    return nms(shifted, scores, iou_threshold)               # 返回的下标可直接索引原 boxes


boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [20, 20, 30, 30]], dtype=float)
scores = np.array([0.9, 0.8, 0.7])
classes = np.array([0, 1, 0])
print(nms(boxes, scores, 0.45).tolist())                   # [0, 2]  —— 类别无关，box1 被误删
print(batched_nms(boxes, scores, classes, 0.45).tolist())  # [0, 1, 2] —— box1 属于另一类，保留
```

要点：①平移不改变同类框之间的 IoU；②偏移量必须大于所有坐标的最大值，否则不同类可能"撞上"；③`torchvision.ops.batched_nms` 用的正是这种思路。在 `postprocess` 中把最后的 `nms(boxes, scores, iou_threshold)` 换成 `batched_nms(boxes, scores, classes, iou_threshold)` 即可。（已用 NumPy 实际运行验证上面两行输出。）

### Q13 — 参考回答要点

- **单阶段（YOLO）流程**：图像缩放到固定尺寸 → backbone 提特征（如 416 输入得到 13×13 特征图，stride 32）→ 检测头（1×1 卷积）在每个格子、每个 anchor 输出 `tx,ty,tw,th,obj,cls×C` → 解码（sigmoid + 网格偏移 + stride，anchor × exp）→ 置信度 `sigmoid(obj) × max(sigmoid(cls))` 过阈值 → NMS → 最终 `boxes / scores / labels`。一次前向就完成，这正是"You Only Look Once"。
- **两阶段（Faster R-CNN）**：第一阶段 RPN 在特征图上生成候选区域（proposal）；第二阶段对每个 proposal 做 RoI Pooling/RoIAlign 抽取固定尺寸特征，再做分类和框精修。
- **取舍**：两阶段多一次"候选 → 精修"，历史上定位更准、小目标更好，但更慢；单阶段结构简单、延迟低，适合实时。随着 FPN、更好的标签分配和 IoU 损失，现代 YOLO 已基本追平。
- **加分点**：提到 DETR / RT-DETR 用集合预测 + 匈牙利匹配，训练时一一对应，推理不再需要 NMS；指出无论哪种结构，"分类 + 回归 + 去重"三件事都在。
- **常见误区**：笼统地说"YOLO 都用 anchor"或"YOLO 没有 anchor"——v1 直接回归框，v2/v3 引入 anchor（本节实现的就是这一代），YOLOX、v8 又转向 anchor-free。

### Q14 — 参考回答要点

- **解决的问题**：一个格子的特征感受野有限，直接回归几百像素的绝对宽高很难；给出几个形状先验后，网络只需"挑一个最像的 anchor + 小幅微调"，回归目标变成 `log(w/anchor_w)` 这种零附近的小数，训练稳定得多。多个 anchor 还允许同一格子同时负责形状不同的目标（如站立的人和横着的车）。
- **怎么定尺寸**：在训练集 GT 的 `(w, h)` 上做 k-means，距离用 `1 − 形状IoU` 而不是欧氏距离（大框不会主导聚类），YOLOv2 起就是这样做；配合 FPN 时按尺寸把 anchor 分到不同层：小 anchor 放高分辨率浅层，大 anchor 放低分辨率深层。本节 `outputs/skill-anchor-designer.md` 就是这个流程。
- **anchor-free**：FCOS 在每个位置直接回归到框四条边的距离；YOLOX、YOLOv8 也是 anchor-free 头。去掉 anchor 后少了一组和数据集强相关的超参数，输出也更少。
- **代价**：正负样本分配变成关键——需要中心采样、SimOTA（动态 k）、Task-Aligned Assigner 这类策略来决定"哪些位置负责哪个 GT"。讲义也提到 v5 之后的分配器（task-aligned matching、dynamic k）是同一思想的细化。
- **常见误区**：以为 anchor 越多越好——anchor 越多负样本越多、计算越重，分配也更难。

### Q15 — 参考回答要点

- **复杂度**：排序 `O(N log N)`；while 循环每次拿出一个框与剩余框算 IoU，最坏情况（框彼此都不重叠、一个也删不掉）是 `O(N²)`。所以讲义里"O(N log N) from the sort"只是排序部分，整体最坏是 `O(N²)`；实际中先用置信度阈值把 N 砍小，再做 NMS。
- **缺陷**：①拥挤场景（人群、密集货架）两个真实目标 IoU 大于阈值时会误删一个；②阈值敏感，全局一个数很难同时适配稀疏和密集场景；③不可微，无法端到端训练；④是串行的贪心过程，在边缘设备上会成为延迟瓶颈，讲义也提到延迟基准要把 NMS 算进去；⑤类别无关的 NMS 会跨类误删（见 Q12）。
- **改进**：Soft-NMS（不删除，而是按 IoU 衰减分数）；DIoU-NMS（同时考虑中心点距离，中心离得远的高 IoU 框更可能是两个目标）；Weighted NMS / WBF（加权融合而非删除，常用于集成）；DETR / RT-DETR 用一对一匹配训练，直接学会不输出重复框。
- **加分点**：能写出 batched NMS 的坐标偏移技巧；知道 `torchvision.ops.nms` 与本节实现的贪心语义一致。

### Q16 — 参考回答要点

- **单类 AP**：①把该类所有图像上的检测结果按置信度从高到低排序；②依次处理每个检测：在同一张图里找该类**尚未被匹配**、且 IoU 最大的 GT，若 IoU ≥ 阈值（如 0.5）则记 TP 并标记该 GT 已匹配，否则记 FP（包括对同一 GT 的重复检测）；③累积得到每个位置的 precision = TP/(TP+FP) 和 recall = TP/GT 总数，画出 P-R 曲线；④把 precision 做成单调不增的包络后求曲线下面积。VOC2007 用 11 点插值，后来改为全部点；COCO 用 101 点插值。
- **mAP**：对所有类别的 AP 取平均。COCO 的 mAP@0.5:0.95 再对 10 个 IoU 阈值（0.50:0.05:0.95）取平均，同时报告小/中/大目标的 AP_S / AP_M / AP_L。
- **置信度阈值**：评估 mAP 时要用很低的阈值（如 0.001）让检测尽量多，因为 AP 积分的是整条 P-R 曲线，高阈值会把曲线截断、人为压低 recall 端；部署时再根据业务对 precision/recall 的偏好单独选阈值（如 0.25）。
- **常见误区**：把"部署阈值下的 precision/recall"和"AP"混为一谈；忘了一个 GT 只能被匹配一次。

### Q17 — 参考回答要点

- **先诊断**：看 AP_S 与 recall 曲线，确认问题是"小目标根本没被检出"（分辨率/stride 问题）还是"检出了但定位差"。
- **分辨率与 stride**：10 像素的目标在 stride 32 的特征图上不到一个格子，信息基本被下采样抹掉。做法：①增加 stride 8 甚至 stride 4（P2）检测层；②用 FPN/PAN 把深层语义融合回高分辨率层；③提高输入分辨率。
- **切片推理**：4K 图直接缩放到 640 会让目标再缩小 6 倍。改为把原图切成有重叠的小块（tiling，如 SAHI 思路），分别推理，坐标映射回原图后统一做一次（类别感知）NMS，与讲义练习 3 的"多尺度预测后统一 NMS"同理。训练时也要对应地切块。
- **anchor 与分配**：用 k-means 在本数据集上重新聚类 anchor（或用 anchor-free 头），确保小目标能被分配到足够多的正样本。
- **数据**：copy-paste / mosaic 增强增加小目标数量；检查标注质量（小目标常漏标，会被当成负样本惩罚）。
- **取舍**：分辨率与切片数直接推高延迟和显存，需要和吞吐目标一起权衡；边缘部署见第 15 节。

### Q18 — 参考回答要点

- **MSE 的问题**：①优化的是 `(tx,ty,tw,th)` 四个独立数，而评估用的是 IoU，两者并不单调对应——相同的 MSE 可能对应差别很大的 IoU；②对尺度敏感，同样的像素误差对大框无所谓、对小框是灾难；③四个坐标被当成相互独立，忽略了框是一个整体。
- **IoU Loss（1 − IoU）**：直接优化评估指标，尺度不变；但两框不相交时 IoU 恒为 0，梯度为 0，学不动。
- **GIoU**：加入最小外接框 C 的惩罚项 `|C − A∪B| / |C|`，不相交时也有梯度，把预测框往 GT 拉。
- **DIoU**：惩罚项改为中心点距离² / 外接框对角线²，直接缩小中心距离，收敛更快。
- **CIoU**：在 DIoU 基础上再加长宽比一致性项，同时考虑重叠、中心距离、长宽比三要素。讲义提到现代变体把 MSE 换成 CIoU/DIoU 来直接优化 IoU，练习 2 就是让你对比 CIoU 与 MSE 在 mAP@0.5:0.95 上的差异。
- **加分点**：IoU 类损失作用在**解码后的框**上，所以天然避开了 Q10(c) 中 logit 空间回归的尺度问题；mAP@0.5 高但 mAP@0.5:0.95 低时，换 CIoU 往往是首选实验。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：backbone 的结构、stride 与感受野。
- [阶段 04 · 04 图像分类](../../04-image-classification/docs/zh.md)：检测 = 在每个位置做一次分类，再加回归。
- [阶段 04 · 05 Transfer Learning & Fine-Tuning](../../05-transfer-learning/docs/zh.md)：检测头通常挂在预训练 backbone 上。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：BCE、MSE，以及为检测而生的 focal loss。

### 本节被哪些后续内容用到
- [阶段 04 · 08 实例分割——Mask R-CNN](../../08-instance-segmentation-mask-rcnn/docs/zh.md)：两阶段检测器，RPN 同样用 anchor、IoU 和 NMS，再加 mask 分支。
- [阶段 04 · 14 Vision Transformers](../../14-vision-transformers/docs/zh.md)：DETR / RT-DETR 等 transformer 检测器的基础。
- [阶段 04 · 15 实时视觉——边缘部署](../../15-real-time-edge/docs/zh.md)：把 YOLO 类检测器压到边缘设备上跑实时，NMS 延迟是重点之一。
- [阶段 04 · 16 构建完整的视觉流程](../../16-vision-pipeline-capstone/docs/zh.md)：把检测器（YOLO 或 Mask R-CNN）接入端到端服务。
- [阶段 04 · 21 关键点检测和姿势估计](../../21-keypoint-pose/docs/zh.md)：自顶向下姿态估计先检测人框再找关键点，以本节为前置。
- [阶段 04 · 24 SAM 3 与开放词表分割](../../24-sam3-open-vocab-segmentation/docs/zh.md)：与 YOLO-World 等开放词表检测器的选型对比。
- [阶段 04 · 27 多目标跟踪与视频记忆](../../27-multi-object-tracking/docs/zh.md)：tracking-by-detection，复用 IoU + 匈牙利匹配。

### 延伸关键词
`FPN / PAN` · `Soft-NMS / DIoU-NMS / WBF` · `GIoU / DIoU / CIoU` · `Focal Loss` · `SimOTA / Task-Aligned Assigner` · `Anchor-free (FCOS)` · `DETR / RT-DETR` · `COCO mAP / AP_S` · `SAHI 切片推理`
