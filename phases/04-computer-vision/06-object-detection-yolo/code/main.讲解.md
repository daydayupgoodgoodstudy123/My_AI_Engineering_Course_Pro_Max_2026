# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 06 节 物体检测——从头开始的 YOLO ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：`numpy`、`torch`（`torch.nn`、`torch.nn.functional`）；CPU 即可，无需联网、无需预训练权重

---

## 1. 这份代码在考察什么

这份代码把一个 YOLO 式检测器拆成**可以单独验证的零件**，不训练、不加载数据集，只用合成框和随机特征图把每个环节跑通：

1. **几何基本功**：用 NumPy 广播一次性算出 N×M 个框对的 IoU；用 IoU 写出贪心 NMS。
2. **回归目标的编码/解码**：网络回归的不是像素坐标，而是 `(tx, ty, tw, th)`；encode 和 decode 必须**严格互逆**（代码特意修正了讲义里的不一致）。
3. **检测头的张量形状**：一个 1×1 卷积 + `view` + `permute`，把通道维拆成 `(anchor, 5+C)`。
4. **标签分配**：每个 GT 框由"中心所在格子 + 形状最像的 anchor"负责。
5. **三部分损失**：box 回归、objectness（正负分开）、分类，以及 `λ` 权重的作用。
6. **推理后处理**：解码 → 置信度过滤 → NMS，这就是完整的 eval 路径。

> 一句话：**检测 = 每个位置做一次分类 + 回归，再用 NMS 去重**；这份代码让你亲手把这句话的每个字落成张量运算。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sigmoid(x)` | 函数 | NumPy 版 sigmoid | 把 logit 压到 (0,1) |
| `box_iou(boxes_a, boxes_b)` | 函数 | 两组框的两两 IoU，返回 `(N_a, N_b)` | IoU |
| `nms(boxes, scores, iou_threshold)` | 函数 | 贪心非极大值抑制，返回保留下标 | NMS |
| `encode(...)` / `decode(...)` | 函数 | 像素框 ↔ `(tx,ty,tw,th)` | 网格 + anchor 参数化 |
| `YOLOHead` | `nn.Module` | 1×1 卷积 + reshape 成 `(N,H,W,A,5+C)` | 检测头 |
| `assign_targets(...)` | 函数 | 为每个 GT 选 (格子, anchor)，构造目标张量和正样本掩码 | 标签分配 |
| `yolo_loss(...)` | 函数 | box MSE + obj BCE（正/负）+ cls BCE，加权求和 | YOLO 损失 |
| `postprocess(...)` | 函数 | 解码、阈值过滤、NMS | 推理后处理 |
| `main()` | 演示入口 | 依次验证 IoU、NMS、编解码、分配+损失、后处理 | — |

数据流：`特征图 → YOLOHead → pred`；训练分支 `GT 框 → assign_targets → (target, has_obj) → yolo_loss(pred, ...)`；推理分支 `pred → postprocess（内部调用 sigmoid、nms → box_iou）→ 最终框`。

---

## 3. 逐段精讲

### 3.1 `box_iou`：用广播一次算完所有框对

```python
def box_iou(boxes_a, boxes_b):
    ax1, ay1, ax2, ay2 = boxes_a[:, 0], boxes_a[:, 1], boxes_a[:, 2], boxes_a[:, 3]
    bx1, by1, bx2, by2 = boxes_b[:, 0], boxes_b[:, 1], boxes_b[:, 2], boxes_b[:, 3]

    inter_x1 = np.maximum(ax1[:, None], bx1[None, :])
    inter_y1 = np.maximum(ay1[:, None], by1[None, :])
    inter_x2 = np.minimum(ax2[:, None], bx2[None, :])
    inter_y2 = np.minimum(ay2[:, None], by2[None, :])

    inter_w = np.clip(inter_x2 - inter_x1, 0, None)
    inter_h = np.clip(inter_y2 - inter_y1, 0, None)
    inter = inter_w * inter_h

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a[:, None] + area_b[None, :] - inter
    return inter / np.clip(union, 1e-8, None)
```

- 框格式是 `(x1, y1, x2, y2)`（左上 + 右下）。交集矩形的左上角取两者左上角的**较大值**，右下角取右下角的**较小值**。
- **广播是核心**：`ax1[:, None]` 形状 `(N,1)`，`bx1[None, :]` 形状 `(1,M)`，两者做 `np.maximum` 自动扩展成 `(N,M)`——不写一个循环就得到所有框对的结果。这与 `torchvision.ops.box_iou` 的写法完全一致。
- `np.clip(..., 0, None)`：两框不相交时 `x2 - x1` 为负，必须截到 0，否则"负宽 × 负高"会得到一个**正的**假交集。
- `union` 用"面积和减交集"（容斥原理）；`np.clip(union, 1e-8, None)` 防止退化框（面积 0）导致除零。
- ⚠️ 简化：默认输入合法（`x2 ≥ x1, y2 ≥ y1`）。如果传进来的是 `(cx, cy, w, h)` 格式，结果会静默出错——检测代码里最常见的 bug 就是框格式混用。

### 3.2 `nms`：贪心去重

```python
def nms(boxes, scores, iou_threshold=0.45):
    order = np.argsort(-scores)
    keep = []
    while len(order) > 0:
        i = order[0]
        keep.append(int(i))
        if len(order) == 1:
            break
        rest = order[1:]
        ious = box_iou(boxes[[i]], boxes[rest])[0]
        order = rest[ious <= iou_threshold]
    return np.array(keep, dtype=np.int64)
```

- `np.argsort(-scores)`：对负分数升序排序 = 对分数降序排序，得到下标顺序。
- 每轮取当前最高分的 `i` 放入 `keep`，再用它和剩余框算 IoU，**只保留 IoU ≤ 阈值的框**进入下一轮。
- `boxes[[i]]`（双层方括号）是**花式索引**，取出的形状是 `(1,4)` 而不是 `(4,)`，这样才能喂给要求二维输入的 `box_iou`；结果 `(1, len(rest))` 再用 `[0]` 取出第一行。
- `rest[ious <= iou_threshold]` 是**布尔掩码索引**，一行完成"过滤"。
- 返回的下标按**分数从高到低**排列，而非原始顺序。
- ⚠️ 复杂度：排序 `O(N log N)`，但循环最坏 `O(N²)`（每个框都留下时每轮都要算一遍 IoU）。讲义说 "O(N log N) from the sort" 只描述了排序部分。
- ⚠️ 类别无关：不同类别的框也会互相抑制。生产中用逐类 NMS 或 `torchvision.ops.batched_nms`（测验 Q12 给出了坐标偏移写法）。

### 3.3 `encode` / `decode`：必须互逆

```python
def encode(box_xyxy, cell_x, cell_y, stride, anchor_wh):
    x1, y1, x2, y2 = box_xyxy
    cx = 0.5 * (x1 + x2)
    cy = 0.5 * (y1 + y2)
    w = x2 - x1
    h = y2 - y1
    # Offset within the cell in [0, 1], converted to logit so decode(sigmoid(tx)) round-trips.
    off_x = np.clip(cx / stride - cell_x, 1e-6, 1 - 1e-6)
    off_y = np.clip(cy / stride - cell_y, 1e-6, 1 - 1e-6)
    tx = float(np.log(off_x / (1 - off_x)))
    ty = float(np.log(off_y / (1 - off_y)))
    tw = np.log(w / anchor_wh[0] + 1e-8)
    th = np.log(h / anchor_wh[1] + 1e-8)
    return np.array([tx, ty, tw, th])


def decode(tx_ty_tw_th, cell_x, cell_y, stride, anchor_wh):
    tx, ty, tw, th = tx_ty_tw_th
    cx = (sigmoid(tx) + cell_x) * stride
    cy = (sigmoid(ty) + cell_y) * stride
    w = anchor_wh[0] * np.exp(np.clip(tw, -10.0, 10.0))
    h = anchor_wh[1] * np.exp(np.clip(th, -10.0, 10.0))
    return np.array([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])
```

decode 就是讲义的四行公式：

| 量 | 解码 | 编码（反函数） |
|----|------|---------------|
| 中心 x | `(sigmoid(tx) + cell_x) · stride` | `tx = logit(cx/stride − cell_x)` |
| 宽 w | `anchor_w · exp(tw)` | `tw = log(w / anchor_w)` |

- **为什么 encode 要取 logit**：decode 里有 sigmoid，encode 就必须用它的反函数 `logit(p) = ln(p / (1−p))`。讲义 Step 3 的 encode 直接存 `cx/stride − cell_x`，与 decode 不互逆——偏移 0.05、stride 32 时会偏约 14.8 像素。代码注释 "so decode(sigmoid(tx)) round-trips" 说的就是这个修正。
- `np.clip(..., 1e-6, 1 - 1e-6)`：GT 中心正好落在格线上时偏移为 0，`logit(0) = −∞`；夹紧后最多是约 ±13.8。
- `+ 1e-8`：防止 `w = 0` 时 `log(0)`。代价是往返有约 `1e-6` 像素的误差，可以忽略。
- decode 里 `np.clip(tw, -10, 10)`：未训练或发散的网络可能输出很大的 `tw`，`exp(100)` 直接溢出成 `inf`，夹紧后宽度最多放大 `e^10 ≈ 2.2 万` 倍，至少是有限数。
- `x1, y1, x2, y2 = box_xyxy`：元组解包，要求正好 4 个元素。

### 3.4 `YOLOHead`：1×1 卷积 + 形状重排

```python
class YOLOHead(nn.Module):
    def __init__(self, in_c, num_anchors, num_classes):
        super().__init__()
        self.num_anchors = num_anchors
        self.num_classes = num_classes
        self.conv = nn.Conv2d(in_c, num_anchors * (5 + num_classes), kernel_size=1)

    def forward(self, x):
        n, _, h, w = x.shape
        y = self.conv(x)
        y = y.view(n, self.num_anchors, 5 + self.num_classes, h, w)
        y = y.permute(0, 3, 4, 1, 2).contiguous()
        return y
```

- **1×1 卷积 = 在每个空间位置上做同一个全连接层**：输入通道 `in_c` → 输出 `A·(5+C)` 个数，参数在所有格子间共享，这正是"稠密预测"的实现方式。
- 张量形状变化（`main()` 中 `in_c=128, A=3, C=5`）：

| 步骤 | 形状 |
|------|------|
| 输入 `x` | `(1, 128, 13, 13)` |
| `self.conv(x)` | `(1, 30, 13, 13)` |
| `view(n, A, 5+C, h, w)` | `(1, 3, 10, 13, 13)` |
| `permute(0, 3, 4, 1, 2)` | `(1, 13, 13, 3, 10)` |

- 为什么先 `view` 再 `permute`：卷积输出的通道维在第 1 维，`view` 只能按内存顺序拆分，所以先把 30 个通道拆成 `(3, 10)`；然后用 `permute` 把空间维挪到前面。直接 `view(n, h, w, A, 5+C)` 不会报错，但语义全错（测验 Q11）。
- `.contiguous()`：`permute` 只改步长不搬数据，后续某些操作（如 `view`）要求内存连续，这里提前拷贝一次。
- `super().__init__()` 必须调用，否则 `nn.Module` 的参数注册机制没初始化，`self.conv = ...` 会报错。
- `n, _, h, w = x.shape`：用 `_` 丢弃不需要的通道数。

### 3.5 `assign_targets`：谁负责哪个 GT

```python
    for box, cls in zip(boxes_xyxy, classes):
        x1, y1, x2, y2 = box
        cx, cy = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
        gx_raw, gy_raw = int(cx / stride), int(cy / stride)
        if not (0 <= gx_raw < grid_size and 0 <= gy_raw < grid_size):
            continue
        gx = min(gx_raw, grid_size - 1)
        gy = min(gy_raw, grid_size - 1)
        bw, bh = x2 - x1, y2 - y1

        ious = []
        for aw, ah in anchors:
            inter = min(bw, aw) * min(bh, ah)
            union = bw * bh + aw * ah - inter
            ious.append(inter / max(union, 1e-8))
        best = int(np.argmax(ious))
        aw, ah = anchors[best]

        off_x = np.clip(cx / stride - gx, 1e-6, 1 - 1e-6)
        off_y = np.clip(cy / stride - gy, 1e-6, 1 - 1e-6)
        target[gy, gx, best, 0] = np.log(off_x / (1 - off_x))
        target[gy, gx, best, 1] = np.log(off_y / (1 - off_y))
        target[gy, gx, best, 2] = np.log(bw / aw + 1e-8)
        target[gy, gx, best, 3] = np.log(bh / ah + 1e-8)
        target[gy, gx, best, 4] = 1.0
        target[gy, gx, best, 5 + cls] = 1.0
        has_obj[gy, gx, best] = True
    return target, has_obj
```

- **选格子**：`int(cx / stride)` 把中心坐标映射到格子下标（正数时 `int` 等价于向下取整）。中心在图外的 GT 直接 `continue` 跳过。
- **选 anchor**：`min(bw,aw) * min(bh,ah)` 是"中心对齐时的交集"，即**形状 IoU**——位置已经由格子决定，anchor 只比形状。这是 YOLOv2/v3 的分配方式。
- **写目标**：前 4 个是回归目标（中心偏移存 logit，与 `encode` 保持一致）；第 5 个 objectness = 1；`5 + cls` 处的 one-hot = 1；`has_obj` 掩码标记正样本位置。
- `main()` 中 GT `(100, 80, 200, 220)`：中心 `(150,150)` → 格子 `(4,4)`；宽高 `100×140` 与三个 anchor 的形状 IoU 约为 `0.129 / 0.646 / 0.184`，选中 anchor 1 `(75,170)`；目标向量为 `[0.788, 0.788, 0.288, −0.194, 1, 0, 0, 1, 0, 0]`（已用 NumPy 验证）。
- ⚠️ 冗余：前面的 `if not (0 <= gx_raw < grid_size ...)` 已保证下标合法，后面的 `min(gx_raw, grid_size - 1)` 永远不会生效。
- ⚠️ 简化：①两个 GT 落在同一 (格子, anchor) 时后者**覆盖**前者；②每个 GT 只分配一个正样本，正样本极少；YOLOv5 之后的分配器会让多个格子/anchor 同时负责一个 GT。

### 3.6 `yolo_loss`：三部分损失

```python
    has_obj_t = torch.from_numpy(has_obj).bool().to(pred.device)
    target_t = torch.from_numpy(target).float().to(pred.device)
    if pred.dim() == 5 and pred.shape[0] == 1:
        pred = pred[0]

    box_pred = pred[..., :4][has_obj_t]
    box_true = target_t[..., :4][has_obj_t]
    loss_box = F.mse_loss(box_pred, box_true, reduction="sum") if box_pred.numel() else torch.tensor(0.0)

    obj_pred = pred[..., 4]
    obj_true = target_t[..., 4]
    loss_obj_pos = F.binary_cross_entropy_with_logits(
        obj_pred[has_obj_t], obj_true[has_obj_t], reduction="sum"
    ) if has_obj_t.any() else torch.tensor(0.0)
    loss_obj_neg = F.binary_cross_entropy_with_logits(
        obj_pred[~has_obj_t], obj_true[~has_obj_t], reduction="sum"
    ) if (~has_obj_t).any() else torch.tensor(0.0)
    # ...
    total = (lambda_coord * loss_box
             + lambda_obj * loss_obj_pos
             + lambda_noobj * loss_obj_neg
             + lambda_cls * loss_cls)
```

| 分量 | 计算位置 | 损失函数 | 权重 |
|------|---------|---------|------|
| `loss_box` | 只在正样本 | MSE（在 `tx,ty,tw,th` 空间） | `λ_coord = 5` |
| `loss_obj_pos` | 只在正样本 | BCE-with-logits，目标 1 | `λ_obj = 1` |
| `loss_obj_neg` | 只在负样本 | BCE-with-logits，目标 0 | `λ_noobj = 0.5` |
| `loss_cls` | 只在正样本 | BCE-with-logits（多标签式） | `λ_cls = 1` |

- `pred[..., :4]`：`...`（Ellipsis）表示"前面所有维度都保留"，只在最后一维切片；`[has_obj_t]` 是布尔掩码，结果被展平成 `(正样本数, 4)`。
- `~has_obj_t` 对布尔张量取反，得到负样本掩码。
- **为什么用 `binary_cross_entropy_with_logits` 而不是先 sigmoid 再 BCE**：它内部用 log-sum-exp 技巧，数值稳定，不会出现 `log(0)`。
- 分类用 BCE 而非 softmax CE：每个类别独立判断，允许多标签（YOLOv3 起的做法）。
- `... if cond else torch.tensor(0.0)`：一张图没有 GT 时掩码全 False，选出来的是空张量。`reduction="sum"` 时对空张量求和本来就是 0，但一旦有人把它改成 `"mean"` 就会得到 `nan`；显式兜底是一种防御式写法，同时让"没有正样本"这一情况在代码里一目了然。
- ⚠️ 简化：①只支持 batch=1（`pred = pred[0]`，`target` 也没有 batch 维）；②`reduction="sum"` 没有按正样本数或 batch 归一化，换数据规模时 λ 需重调；③box 损失在 logit 空间做 MSE，靠近格子边缘的 GT 目标值可达 ±13.8（测验 Q10c），现代实现改用 CIoU 等 IoU 损失；④兜底的 `torch.tensor(0.0)` 在 CPU 上，0 维张量能和 GPU 张量相加，但不带梯度。

### 3.7 `postprocess`：解码 → 过滤 → NMS

```python
    for gy in range(grid_h):
        for gx in range(grid_w):
            for a in range(num_anchors):
                row = pred[0, gy, gx, a]
                tx, ty, tw, th, obj = row[:5]
                cls_logits = row[5:]
                cls_probs = sigmoid(cls_logits)
                score = float(sigmoid(obj) * cls_probs.max())
                if score < conf_threshold:
                    continue
                cls_idx = int(np.argmax(cls_probs))
                cx = (sigmoid(tx) + gx) * stride
                cy = (sigmoid(ty) + gy) * stride
                # Clamp tw/th to keep exp() finite on wild predictions.
                w = anchors[a][0] * np.exp(np.clip(tw, -10.0, 10.0))
                h = anchors[a][1] * np.exp(np.clip(th, -10.0, 10.0))
                boxes.append([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])
                # ...
    keep = nms(boxes, scores, iou_threshold)
    return boxes[keep], scores[keep], classes[keep]
```

- `pred_tensor.detach().cpu().numpy()`：先断开计算图、搬到 CPU，才能转 NumPy。
- **最终置信度 = objectness × 最大类别概率**：既要"这里有东西"，又要"确定是哪一类"。
- 解码与 `decode()` 公式完全一致，`gx, gy` 就是格子坐标。
- 没有任何框过阈值时返回三个空数组，保证调用方拿到的形状永远一致。
- ⚠️ 简化：①只处理 batch 里的第 0 张图；②三重 Python 循环在 13×13×3 = 507 个位置上还行，换成 80×80 的特征图就很慢，生产代码用张量一次性解码（构造网格坐标后广播）；③NMS 类别无关。

### 3.8 `main()`：逐个零件验证

- IoU：相同框 = 1；`[0,0,10,10]` 与 `[5,0,15,10]` 交集 50、并集 150，IoU = 1/3。
- NMS：两簇各 2–3 个重叠框，阈值 0.4 下每簇只留最高分，结果 `[0, 3]`。
- 编解码：GT `(120, 80, 240, 220)` 中心 `(180,150)` → 格子 `(5,4)`，用 anchor `(75,170)` 编码再解码，误差约 `8.5e-7`。
- 分配 + 损失：随机特征图 `torch.randn(1, 128, 13, 13)` 喂给未训练的 head，只为验证形状对齐和损失能算。
- 后处理：故意用很低的阈值 `0.1`，看随机网络会输出多少框。
- 小瑕疵：第一行 `rng = np.random.default_rng(0)` 创建后从未使用，可以删除。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| IoU/NMS 用 NumPy 广播实现 | 每一步看得见，且与 torchvision 语义一致 | 生产用 `torchvision.ops.box_iou / nms`（C++/CUDA 实现） |
| encode 用 logit，与 decode 严格互逆 | 训练目标与推理解码处在同一空间 | 很多实现在 sigmoid 后的空间算损失，或直接用 IoU 损失 |
| `tw` 夹到 [-10, 10] | 防止 `exp` 溢出成 inf | 训练良好时几乎不触发 |
| 形状 IoU 选单个 anchor | 简单、对应 YOLOv2/v3 | 现代用 SimOTA / Task-Aligned 等多正样本分配 |
| 正负 objectness 分开计算、分别加权 | 负样本远多于正样本，需要单独降权 | 也可用 focal loss / quality focal loss |
| 损失 `reduction="sum"` | 与 YOLOv1 原论文一致，便于理解 | 生产中按正样本数或 batch 归一化 |
| batch=1、Python 三重循环后处理 | 代码短、每一步可调试 | 生产中全部向量化、支持 batch |
| 类别无关 NMS | 实现最简单 | 用 batched NMS（逐类） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组解包 | `x1, y1, x2, y2 = box_xyxy`；`n, _, h, w = x.shape` | 一次给多个变量赋值；`_` 表示丢弃不用的值 |
| 多重赋值 | `cx, cy = 0.5 * (x1 + x2), 0.5 * (y1 + y2)` | 右侧先组成元组再解包 |
| `zip` | `for box, cls in zip(boxes_xyxy, classes)` | 两个序列按位置配对遍历 |
| 链式比较 | `0 <= gx_raw < grid_size` | 等价于 `0 <= gx_raw and gx_raw < grid_size` |
| 条件表达式 | `F.mse_loss(...) if box_pred.numel() else torch.tensor(0.0)` | `a if 条件 else b`，一行完成分支 |
| 解包到列表 | `np.array([*enc[:2], enc[2], enc[3]])` | `*` 把序列展开成多个元素 |
| f-string 格式符 | `f"{box_iou(a, b)[0, 0]:.3f}"` | `:.3f` 保留 3 位小数 |
| 字典字面量 | `{"box": float(loss_box), "obj_pos": ...}` | 返回多个具名数值，方便打印 |
| 类继承 + `super()` | `class YOLOHead(nn.Module)`、`super().__init__()` | 继承 PyTorch 模块，必须先初始化父类 |
| NumPy 广播 | `ax1[:, None]` 与 `bx1[None, :]` | `None` 插入长度为 1 的新轴，自动扩展成 `(N,M)` |
| 花式索引 | `boxes[[i]]` | 用列表索引，保留二维形状 `(1,4)` |
| 布尔掩码索引 | `rest[ious <= iou_threshold]`、`pred[..., :4][has_obj_t]` | 按条件筛选元素 |
| Ellipsis `...` | `pred[..., 4]` | 代表"前面所有维度"，只在最后一维取值 |
| 张量方法 | `.view` / `.permute` / `.contiguous()` / `.detach().cpu().numpy()` | 改形状、重排维度、整理内存、转 NumPy |
| `if __name__ == "__main__":` | 文件末尾 | 只有直接运行时才执行 `main()` |

---

## 6. 运行结果解读

**未实际运行完整脚本（当前环境缺少 `torch`）。** 不过前四段只依赖 NumPy：我用 `ast` 只抽取 `sigmoid / box_iou / nms / encode / decode / assign_targets` 在临时目录单独执行，得到的数值与下面一致；后两段依赖 PyTorch 随机权重，只能给出形状和量级预期。

```text
[iou] identical boxes should have iou=1
  iou=1.000

[iou] half-overlap boxes
  iou=0.333  (expected 1/3 = 0.333)

[nms] 5 overlapping boxes -> NMS keeps highest-score non-overlapping set
  kept indices: [0, 3]  (expected [0, 3])

[encode/decode] round-trip error
  enc  =[ 0.511  0.788  0.47  -0.194]
  decoded=[120.  80. 240. 220.]  (original (120, 80, 240, 220))
  max|diff|=0.000  (should round-trip to ~0 once encode applies logit)

[assign + loss] one synthetic image
  pred shape: (1, 13, 13, 3, 10)   target shape: (13, 13, 3, 10)
  loss=…  parts={'box': …, 'obj_pos': …, 'obj_neg': …, 'cls': …}

[postprocess] decode + NMS
  predictions after NMS: …  scores range [… , …]
```

逐行解读：

- `iou=1.000` / `0.333`：广播 IoU 正确，容斥原理的并集没有算错。
- `kept indices: [0, 3]`：box0 与 box1、box2 的 IoU 分别是 0.681、0.471，都超过 0.4 被删；box3 删掉 box4。
- `enc = [0.511, 0.788, 0.47, -0.194]`：格内偏移 `0.625, 0.6875` 的 logit，以及 `ln(120/75)`、`ln(140/170)`。`tw > 0` 表示比 anchor 宽，`th < 0` 表示比 anchor 矮。
- `max|diff|=0.000`：真实误差约 `8.5e-7` 像素，来自 `+1e-8`，证明 encode/decode 互逆。
- `pred shape (1,13,13,3,10)` 与 `target shape (13,13,3,10)`：`yolo_loss` 会去掉 batch 维后用同一个掩码索引两者。
- **损失量级（估计）**：507 个位置里只有 1 个正样本，506 个负样本的 objectness BCE 会主导——按 PyTorch 默认初始化估算，随机 head 的输出标准差约 0.58，每个负样本 BCE 约 0.7，`obj_neg` 约在 350–400 之间，乘 `λ_noobj=0.5` 后仍是总损失的大头；`box`、`obj_pos`、`cls` 都只是个位数。这正是 `λ_noobj` 存在的原因。
- **后处理（估计）**：未训练网络的 `sigmoid(obj) × max(sigmoid(cls))` 普遍在 0.1–0.7，阈值 0.1 几乎挡不住任何框；类别无关 NMS 后仍会剩下上百个框（用同分布的 NumPy 模拟约 300 个）。这说明"会解码"不等于"能检测"：objectness 必须经过训练学会在空格子上"闭嘴"。

---

## 7. 动手改一改

1. 把讲义版 encode（不取 logit）粘进来，打印 `max|diff|`，再把 GT 改成中心靠近格线的框，观察误差如何变大。
2. 给 `nms` 加一个 `classes` 参数，实现类别感知 NMS（提示：坐标偏移技巧，见测验 Q12）。
3. 把 `postprocess` 的三重循环改成向量化：用 `np.meshgrid` 构造 `gx, gy` 网格，一次性算出所有框和分数，再与原实现比对结果。
4. 让 `yolo_loss` 支持 batch：`target`/`has_obj` 增加 batch 维，并把各项损失除以正样本总数。
5. 实现 `ciou_loss(pred_boxes, true_boxes)`，在解码后的 `xyxy` 框上替换 MSE（讲义练习 2）。
6. 写一个训练循环：固定一个合成 GT，用 Adam 训练 `YOLOHead` 200 步，看 `obj_neg` 是否下降、`postprocess` 是否只剩 1 个框。

---

## 8. 常见坑

- **框格式混用**：`xyxy` 与 `cxcywh` 混着传，IoU 不报错但结果全错。每个函数入口都应该明确格式。
- **encode/decode 不互逆**：讲义版本就是例子；训练时目标空间与推理解码空间不一致，模型怎么训都"差一点"。
- **`view` 代替 `permute`**：形状对得上就不报错，但通道和空间被搅乱，是最难查的静默 bug。
- **忘了 clip**：`log(0)`、`exp(100)`、`logit(0)` 都会产生 `inf/nan`，一个 nan 就能污染整个 batch 的梯度。
- **负样本主导损失**：不降权或不归一化时，模型学会"处处预测没有目标"，recall 接近 0。
- **评估时置信度阈值设太高**：AP 需要整条 P-R 曲线，评估 mAP 时阈值应很低，部署时再单独选阈值。
