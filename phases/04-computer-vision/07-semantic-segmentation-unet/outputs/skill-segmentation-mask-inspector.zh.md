---
name: skill-segmentation-mask-inspector
description: Report class distribution, predicted-mask statistics, and the classes most likely to be under-predicted or boundary-blurred
version: 1.0.0
phase: 4
lesson: 7
tags: [computer-vision, segmentation, debugging, evaluation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="segmentation-mask-inspector"></a>

# 分割掩模检查器

对“损失下降”和“面具实际上看起来不错”之间差距的诊断。

<a id="when-to-use"></a>

## 何时使用

- 训练结束后，mIoU 看起来不错，但目视检查却显示不然。
- 部署之前：检查预测与真实情况的类平衡。
- 当每类 IoU 对于大对象较高但对于小对象较低时。
- 调试未在 IoU 中显示的边界伪影，因为它们的像素数很小。

<a id="inputs"></a>

## 输入

- `preds`：（N、H、W）tensor 预测的类别 ID。
- `targets`：（N、H、W）tensor 真实类别 ID。
- `num_classes`：整数。
- 可选 `class_names`：C 字符串列表。

<a id="steps"></a>

## 步骤

1. **类像素直方图。** 计算 `preds` 和 `targets` 的每个类的像素百分比。标记 `|pred% - gt%| / max(gt%, 1e-6) > 0.30`（相对偏差高于 30%）的任何类别。对于地面实况中缺少的类 (`gt% == 0`)，直接标记高于 `0.3` 的任何预测份额。

2. **IoU 每类 ** 和 ** 每类边界 F1**。边界 F1 是通过将每个掩模扩大 3 个像素、相交和评分来计算的。 IoU > 0.7 但边界 F1 < 0.5 的类是模糊边缘。

3. **小对象召回。** 将每个真实连接组件分成大小桶（微小 < 100 px，小 < 1000 px，中 < 10000 px，大 >= 10000 px）。报告每个类别每个存储桶的召回率。小目标召回率低于 0.3 而大目标召回率高于 0.9 表明存在分辨率/感受野问题。

4. **混淆对。** 对于每个类，找到最常混淆的类（其真实掩码中最常见的错误预测类）。报告前 3 对。

5. **Saturation 检查（需要 `probs` 或 `logits`，而不仅仅是 `preds`）。** 如果调用者传递原始每像素概率分布`probs: (N, C, H, W)`，计算每个类中 `probs.max(dim=1) > 0.99` 的像素分数。高 saturation（> 类像素的 0.9）表明过度自信 - 标签平滑或 calibration 的候选者。当只有 argmaxed `preds` 可用时，请跳过此步骤并在报告中注明。

<a id="report-format"></a>

## 报告格式

```
[mask-inspector]
  classes: C

[class distribution]
  name       gt %    pred %   delta
  ...

[metrics]
  class       IoU     bF1    recall_tiny  recall_small  recall_medium  recall_large
  ...

[confusion pairs]
  class A confused with class B: <N> pixels (most common)
  class B confused with class A: <N> pixels
  ...

[verdict]
  most impactful issue: <one sentence>
```

<a id="rules"></a>

## 规则

- 按 gt 像素份额降序对类行进行排序，以便最常见的类排在第一位。
- 将 IoU < 0.4 或边界 F1 < 0.3 的类标记为 `critical`。
- 当小目标召回是主要失败时，建议：更高分辨率的训练，最后 encoder 阶段更小的步幅，或 feature 金字塔 decoder。
- 当边界 F1 是主要故障时，推荐：边界感知损失（Lovasz 或 BoundaryLoss）、水平翻转的 TTA 和无步幅 decoder。
- 切勿将类索引输出为唯一标识符；如果提供了 `class_names`，则在每一行中使用它。
