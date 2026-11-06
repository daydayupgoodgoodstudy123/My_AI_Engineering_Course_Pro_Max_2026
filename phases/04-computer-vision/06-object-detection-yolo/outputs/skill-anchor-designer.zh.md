---
name: skill-anchor-designer
description: Given a dataset of ground-truth boxes, run k-means on (w, h) and return anchor sets per FPN level plus coverage statistics
version: 1.0.0
phase: 4
lesson: 6
tags: [computer-vision, detection, anchors, kmeans]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="anchor-designer"></a>

# 主播设计师

锚点是基于锚点的检测器中最特定于数据集的 hyperparameter。默认 COCO 锚点在细胞培养图像、卫星图块或小物体监视方面表现不佳。该技能派生出与目标数据实际匹配的锚点。

<a id="when-to-use"></a>

## 何时使用

- 在新数据集上运行第一次训练之前。
- 当对非常小或非常大的物体的回忆在其他方面健康的模型上很弱时。
- 在主要数据集扩展之后，框大小分布可能会发生变化。

<a id="inputs"></a>

## 输入

- `boxes`：numpy 形状（N，4）数组，采用 `(cx, cy, w, h)` 或 `(x1, y1, x2, y2)` 格式；推荐至少 1000 个阳性框。
- `num_anchors_per_level`：通常为3。
- `num_fpn_levels`：通常为3（P3、P4、P5）或4。
- `input_size`：训练分辨率 HxW。
- 可选 `strides`：每级步幅；省略时，取 `[8, 16, 32, 64]` 的第一个 `num_fpn_levels` 条目。如果检测器的 FPN 具有不同的步幅，则明确传递更长或更短的数组。

<a id="steps"></a>

## 步骤

1. **将盒子**标准化为`(w, h)`对，以`input_size`的像素为单位。删除任何 w 或 h < 2 像素的内容。

2. ** 在 `(w, h)` 对上运行 k-means**，使用 `k = num_anchors_per_level * num_fpn_levels`。使用 `1 - IoU(box, cluster)` 作为距离函数，而不是欧几里德距离 - `(w, h)` 上的欧几里德距离将薄的高盒子和方形盒子折叠在一起。所有盒子的贡献均等（未加权）；如果您有一个类不平衡的数据集并且想要更大的框召回，请在输入数组中重复稀有类框，而不是传递 weight 向量。

3. ** 按区域 ** 升序对集群进行排序。分成 `num_fpn_levels` 组 `num_anchors_per_level`。最小的区域达到最高分辨率级别（最小步幅）。

4. ** 计算覆盖率统计** 每级：
   - 每个地面实况框的 `median IoU` 到该级别的最佳锚点。
   - `recall@IoU=0.5` — 最佳锚点 IoU >= 0.5 的框的百分比。
   - `area coverage` — 面积落在关卡 `[anchor_min_area / 4, anchor_max_area * 4]` 范围内的盒子的分数。

5. **报告每级锚点**和标志级别，其中`recall@IoU=0.5 < 0.9`;该级别的锚点与数据不太匹配，应重新调整或增加每个级别的锚点数量。

<a id="report-format"></a>

## 报告格式

```
[anchor-designer]
  total boxes:         <N>
  clusters:            <k>
  distance metric:     1 - IoU

[level P3  stride=8]
  anchors (w, h):      [(A, B), (C, D), (E, F)]
  median IoU:          <X>
  recall@IoU=0.5:      <X>
  coverage:            <X>
  flag:                ok | retune

[level P4  stride=16]
  ...

[summary]
  overall recall@IoU=0.5: <X>
  smallest anchor:        <w x h>
  largest anchor:         <w x h>
  recommendation:         <one sentence if any level flagged>
```

<a id="rules"></a>

## 规则

- 始终使用基于 IoU 的距离；欧几里得 k 均值产生视觉上合理但经验上较差的锚点。
- 按区域对集群进行排序，然后按升序分配到级别。
- 当 `num_anchors_per_level = 1` 时，完全跳过 k 均值：按面积分位数将框拆分为 `num_fpn_levels` 箱（例如 3 个级别的三分位数），并将每个级别的锚点设置为每个箱的中位数（w，h）。这比在小数据集上使用 `k = num_fpn_levels` 运行 k 均值更稳健。
- 切勿输出负锚尺寸；夹在 1 处。
- 如果数据集的框数小于 200 个，则警告用户锚点搜索不可靠，并建议使用默认的 COCO 锚点加上更多训练数据。
