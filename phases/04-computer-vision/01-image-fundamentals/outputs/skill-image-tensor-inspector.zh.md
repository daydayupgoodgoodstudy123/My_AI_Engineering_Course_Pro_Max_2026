---
name: skill-image-tensor-inspector
description: Inspect any image-shaped tensor or array and report dtype, layout, range, and whether it looks raw, normalized, or standardized
version: 1.0.0
phase: 4
lesson: 1
tags: [computer-vision, debugging, preprocessing, tensors]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="image-tensor-inspector"></a>

# 图像 Tensor 检查员

一种针对视觉管道中任何点的诊断技能，其中您持有图像形状的阵列，并且需要确切地知道它处于什么状态。

<a id="when-to-use"></a>

## 何时使用

- 预训练模型返回垃圾预测，您怀疑预处理。
- 在 OpenCV 和 torchvision 之间迁移管道以及通道顺序尚不清楚。
- 来自多个框架的堆叠层和批处理轴不断出现在错误的位置。
- 调试损失卡在 `log(num_classes)` 的训练循环。

<a id="inputs"></a>

## 输入

- `x`：任何 2-D、3-D 或 4-D 数组（NumPy、PyTorch、JAX）。
- 可选的 `expected`：要检查的不变量字典，例如`{"layout": "CHW", "range": "standardized"}`。

<a id="steps"></a>

## 步骤

1. **解析后端** — 检测`x`是否为NumPy、Torch或JAX。转换为NumPy进行检查，无需改变原件。

2. **分类排名**：
   - 等级 2 -> 单通道图像（H、W）。
   - 如果最后一个轴是 1、3 或 4 并且严格小于其他两个轴，则排名 3 -> `HWC`；否则为 `CHW`。
   - 排名 4 -> 如果轴 1 位于 {1, 3, 4} 中，则优先选择 `NCHW` ** 和 ** 轴 2 或轴 3 大于 16；否则更喜欢 `NHWC`。纯 axis-1 检查会错误分类小图像 NHWC 批次，例如 `(3, 4, 224, 3)`。
   - 始终将不明确的情况（例如 `(1, 3, 3, 3)`）标记为 `ambiguous` 而不是猜测；要求调用者提供`expected`。

3. **分类dtype和范围**:
   - `uint8` 在 [0、255] -> `raw`。
   - `float*`，最小值 >= 0 且最大值 <= 1.01 -> `normalized`。
   - `float*`，最小值 < 0 且 |意思是| < 0.5 且 0.5 <= std <= 1.5 -> `standardized`.
   - 其他 -> `unusual`，打印直方图。

4. **每通道统计数据** — 报告每个通道的平均值和标准差。如果数组看起来标准化并显示匹配置信度，则与 ImageNet 均值/标准差进行比较。

5. **Report** 在这个确切的块中：

```
[inspector]
  backend:   numpy | torch | jax
  rank:      2 | 3 | 4
  layout:    HW | HWC | CHW | NHWC | NCHW
  dtype:     <dtype>
  shape:     <shape>
  range:     raw | normalized | standardized | unusual
  min/max:   <min> / <max>
  per-channel mean: [ ... ]
  per-channel std:  [ ... ]
  likely source:    camera | PIL | OpenCV | torchvision | random init
  likely target:    display | training | inference
```

6. **基于`likely target`推荐下一步行动**：
   - 对于`display`：转置为HWC，剪辑，转换为uint8。
   - 对于 `training`：使用数据集统计数据进行标准化，转置为 CHW，添加批处理轴。
   - 对于 `inference`：匹配 model card 中的精确不变量。

<a id="rules"></a>

## 规则

- 切勿改变输入。仅打印诊断信息。
- 如果提供了 `expected`，则用 `[expected X got Y]` 标记每个不匹配。
- 当布局或通道顺序不明确时，指出无声故障风险。
- 一次推荐一项操作，而不是一系列选项。
