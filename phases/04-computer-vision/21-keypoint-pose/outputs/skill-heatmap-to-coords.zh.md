---
name: skill-heatmap-to-coords
description: Write the sub-pixel heatmap-to-coordinate routine used by every production pose model
version: 1.0.0
phase: 4
lesson: 21
tags: [keypoint, pose, subpixel, inference]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="heatmap-to-coords"></a>

# 热图到坐标

将原始关键点热图转换为亚像素精确坐标。每个姿势管道中最便宜的精度升级。

<a id="when-to-use"></a>

## 何时使用

- 部署基于热图的关键点模型。
- 姿势指标基准测试 - OKS 对子像素精度极其敏感。
- 将姿势代码从一个框架移植到另一个框架。

<a id="inputs"></a>

## 输入

- `heatmaps`：`(N, K, H, W)` tensor，模型中的每个关键点热图。
- `confidence_threshold`：丢弃峰值低于该值的关键点。

<a id="steps"></a>

## 步骤

1. **Argmax** 每个热图查找整数峰值位置。
2. **一阶差分偏移** — 估计与相邻像素的子像素偏移。 `0.25` 系数是使用 `sigma >= 1` 为高斯热图校准的启发式系数；对于有原则的子像素恢复，请使用完全二次拟合 (DARK) 或高斯拟合。

```
dx = 0.25 * sign(heatmap[y, x+1] - heatmap[y, x-1])
dy = 0.25 * sign(heatmap[y+1, x] - heatmap[y-1, x])
```

对于 DARK/二次变体，使用局部二次进行近似：

```
dx = -0.5 * (heatmap[y, x+1] - heatmap[y, x-1])
        / (heatmap[y, x+1] - 2 * heatmap[y, x] + heatmap[y, x-1] + eps)
```

二次拟合在峰值热图上更准确；当热图有噪声时，基于符号的偏移是更安全的默认值。

3. **将偏移量**添加到整数峰值。
4. **Confidence** — 返回每个关键点的峰值；客户用它来掩盖低可信度的预测。
5. **边界情况** — 当峰值落在沿轴的第一个或最后一个像素上时，其中一个邻居被钳位；偏移量降至零，这是最安全的后备方案。

<a id="output-template"></a>

## 输出模板

```python
import torch

def heatmap_to_coords_subpixel(heatmaps, threshold=0.2):
    N, K, H, W = heatmaps.shape
    flat = heatmaps.reshape(N, K, -1)
    conf, idx = flat.max(dim=-1)
    ys = (idx // W).float()
    xs = (idx % W).float()

    ys_int = ys.long()
    xs_int = xs.long()

    x_minus = (xs_int - 1).clamp(min=0)
    x_plus = (xs_int + 1).clamp(max=W - 1)
    y_minus = (ys_int - 1).clamp(min=0)
    y_plus = (ys_int + 1).clamp(max=H - 1)

    batch_idx = torch.arange(N).view(-1, 1).expand(-1, K)
    kp_idx = torch.arange(K).view(1, -1).expand(N, -1)

    dx_raw = (heatmaps[batch_idx, kp_idx, ys_int, x_plus]
              - heatmaps[batch_idx, kp_idx, ys_int, x_minus])
    dy_raw = (heatmaps[batch_idx, kp_idx, y_plus, xs_int]
              - heatmaps[batch_idx, kp_idx, y_minus, xs_int])
    dx = 0.25 * torch.sign(dx_raw)
    dy = 0.25 * torch.sign(dy_raw)

    at_left = xs_int == 0
    at_right = xs_int == (W - 1)
    at_top = ys_int == 0
    at_bottom = ys_int == (H - 1)
    dx = torch.where(at_left | at_right, torch.zeros_like(dx), dx)
    dy = torch.where(at_top | at_bottom, torch.zeros_like(dy), dy)

    refined_x = xs + dx
    refined_y = ys + dy
    coords = torch.stack([refined_x, refined_y], dim=-1)
    mask = conf >= threshold
    return coords, conf, mask
```

<a id="report"></a>

## 报告

```
[subpixel decode]
  keypoints:   K
  threshold:   <float>
  valid_rate:  fraction of keypoints above threshold
```

<a id="rules"></a>

## 规则

- 始终将邻居索引限制在有效范围内；边缘关键点具有零差异偏移，但不会崩溃。
- 返回置信度和坐标，以便客户可以掩盖低置信度点。
- 子像素细化仅在热图在峰值附近平滑时才有帮助 - 检查训练是否使用 sigma >= 1 的高斯目标。
- 对于非常小的热图分辨率（< 48x48），请考虑在提取坐标之前将热图上采样到完整图像大小；子像素偏移量随步幅缩放。
