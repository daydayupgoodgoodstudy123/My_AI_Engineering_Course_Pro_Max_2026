---
name: skill-mask-rcnn-head-swapper
description: Generate the exact code for swapping box and mask heads on a torchvision Mask R-CNN for a custom num_classes
version: 1.0.0
phase: 4
lesson: 8
tags: [computer-vision, mask-rcnn, fine-tuning, torchvision]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="mask-r-cnn-head-swapper"></a>

# 面罩 R-CNN 换头器

专门为 Mask R-CNN 生产换头样板。下面的模板假设 `model.roi_heads.box_predictor` 和 `model.roi_heads.mask_predictor`，仅存在于 `maskrcnn_resnet50_fpn` 和 `maskrcnn_resnet50_fpn_v2` 上。 Faster R-CNN 有框预测器但没有掩模预测器； RetinaNet 使用 `RetinaNetHead` 且根本没有 `roi_heads` — 两者都需要不同的技能。

<a id="when-to-use"></a>

## 何时使用

- 自定义类集上的 Fine-tuning `maskrcnn_resnet50_fpn` 或 `maskrcnn_resnet50_fpn_v2`。
- 将在 COCO 上训练的 Mask R-CNN checkpoint 移植到非 COCO 类计数。
- 调试因 `cls_score.out_features` 或 `mask_predictor` 不匹配而崩溃的 Mask R-CNN 训练运行。

<a id="out-of-scope"></a>

## 超出范围

- `fasterrcnn_*` — 无掩码_预测器。仅交换`box_predictor`；使用单独的 Faster R-CNN 换头配方。
- `retinanet_*` — 无 `roi_heads`；分类器+回归头位于 `model.head.classification_head` 和 `model.head.regression_head` 下。使用 RetinaNet 特定的技能。
- `keypointrcnn_*` — 使用 `keypoint_predictor` 而不是 `mask_predictor`。

<a id="inputs"></a>

## 输入

- `model_name`：torchvision检测模型构造函数，例如`maskrcnn_resnet50_fpn_v2`。
- `num_classes`：包括背景。 4 对象类数据集表示 `num_classes=5`。
- `freeze`：`backbone`、`backbone_fpn`、`none` 之一。

<a id="steps"></a>

## 步骤

1. 导入模型构造函数和两个预测器类（`FastRCNNPredictor`、`MaskRCNNPredictor`）。
2. 加载默认的-weights 预训练模型。
3. 将 `model.roi_heads.box_predictor` 替换为新的 `FastRCNNPredictor(in_features, num_classes)`。
4. 将 `model.roi_heads.mask_predictor` 替换为新的 `MaskRCNNPredictor(in_features_mask, hidden_layer=256, num_classes)`。
5. 应用请求的冻结策略。
6. 打印确认块，列出每个模块的可训练参数。

<a id="output-code-template"></a>

## 输出代码模板

```python
from torchvision.models.detection import {MODEL_NAME}, {MODEL_WEIGHTS}
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.models.detection.mask_rcnn import MaskRCNNPredictor

def build_model(num_classes={NUM_CLASSES}):
    model = {MODEL_NAME}(weights={MODEL_WEIGHTS}.DEFAULT)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    in_features_mask = model.roi_heads.mask_predictor.conv5_mask.in_channels
    model.roi_heads.mask_predictor = MaskRCNNPredictor(in_features_mask, 256, num_classes)

    {FREEZE_BLOCK}

    return model
```

其中 `{FREEZE_BLOCK}` 是：

- `none` -> 空
- `backbone` ->
  ```python
  for p in model.backbone.parameters():
      p.requires_grad = False
  ```
- `backbone_fpn` ->
  ```python
  for p in model.backbone.parameters():
      p.requires_grad = False
  # FPN parameters live inside backbone.fpn
  ```

<a id="report"></a>

## 报告

```
[head-swap]
  model:         <MODEL_NAME>
  num_classes:   <N>  (includes background)
  freeze policy: <choice>
  trainable:     <N>
  total:         <N>
```

<a id="rules"></a>

## 规则

- 切勿在不包含背景的情况下推荐`num_classes`；时刻提醒用户。
- 如果可用，请始终使用 TorchVision 检测模型的 `_v2` 变体；他们比传统的 weights 有更好的预训练。
- 不要在该技能中实例化模型 - 生成代码块并让用户运行它。
- 如果用户在超过 10,000 张图像的数据集上请求 `freeze backbone`，建议他们也将 fine-tuning 视为主干。
