---
name: skill-depth-to-pointcloud
description: Build point clouds from depth maps with correct intrinsics handling and export to .ply
version: 1.0.0
phase: 4
lesson: 26
tags: [depth, point-cloud, 3d, intrinsics]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="depth-to-point-cloud"></a>

# 深度到点云

将深度图和彩色图像转换为纹理点云，可导出用于可视化或进一步的 3D 工作。

<a id="when-to-use"></a>

## 何时使用

- 将深度预测可视化为实际的 3D 场景。
- 从单个图像引导稀疏 3D 重建。
- 当 SfM 失败时，为 3DGS 训练生成输入。
- 将预测深度与 LiDAR 地面实况进行比较。

<a id="inputs"></a>

## 输入

- `depth`：`(H, W)` numpy 深度数组，采用与输出中所需单位相同的单位（建议使用米）。
- `rgb`：`(H, W, 3)` numpy 颜色数组（uint8 或 float32 [0、1]）。
- `intrinsics`：`(fx, fy, cx, cy)`（以像素为单位）。
- 可选 `depth_scale`：将预测深度单位转换为米的乘数。

<a id="pipeline"></a>

## 管道

1. **Validate** — 在您计划包含的任何地方，深度都必须为正且有限。屏蔽无效像素。
2. **Lift** — `X = (u - cx) * d / fx`、`Y = (v - cy) * d / fy`、`Z = d` 每像素。
3. **Pair** 与 RGB — 每个 3D 点从匹配像素获得一个 `(r, g, b)` 三元组。
4. **Export** — PLY（便携式）、`.xyz`（轻量级）、`.pcd`（Open3D 原生）、`.las`/`.laz` （地理空间）。

<a id="implementation-template"></a>

## 实施模板

```python
import numpy as np

def depth_to_point_cloud(depth, intrinsics, depth_scale=1.0, min_depth=0.1, max_depth=100.0):
    H, W = depth.shape
    fx, fy, cx, cy = intrinsics
    v, u = np.meshgrid(np.arange(H), np.arange(W), indexing="ij")
    z = depth.astype(np.float32) * depth_scale
    valid = (z > min_depth) & (z < max_depth) & np.isfinite(z)
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    points = np.stack([x, y, z], axis=-1)
    return points, valid


def write_ply(path, points, colors=None, valid_mask=None):
    p = points.reshape(-1, 3)
    if valid_mask is not None:
        p = p[valid_mask.flatten()]
    lines = [
        "ply",
        "format ascii 1.0",
        f"element vertex {p.shape[0]}",
        "property float x", "property float y", "property float z",
    ]
    if colors is not None:
        c = colors.reshape(-1, 3).astype(np.uint8)
        if valid_mask is not None:
            c = c[valid_mask.flatten()]
        lines += ["property uchar red", "property uchar green", "property uchar blue"]
    lines.append("end_header")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
        if colors is not None:
            for pt, col in zip(p, c):
                f.write(f"{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f} {col[0]} {col[1]} {col[2]}\n")
        else:
            for pt in p:
                f.write(f"{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f}\n")
```

<a id="report"></a>

## 报告

```
[export]
  input depth shape:  (H, W)
  valid points:       <N> of <H*W>
  output format:      ply | xyz | pcd | las
  coordinate system:  camera (+X right, +Y down, +Z forward)
  scale:              metres | millimetres | normalised
```

<a id="rules"></a>

## 规则

- 始终屏蔽无效深度（零、NaN、inf、饱和）；包括它们会在原点产生一堆垃圾点。
- 对于相对深度模型的预测，请勿导出为指标；在输出文件名前加上 `relative_` 来表示约定。
- 保持相机坐标约定一致（OpenCV：+X 向右，+Y 向下，+Z 向前）。如果下游工具需要 OpenGL（+Y 向上），则交换符号。
- 对于密集场景（> 1M点），提供子样本parameter； PLY 文件 > 500 MB 很难在任何地方加载。
- 永远不要默默地剪辑深度以产生“合理”的输出；使用警告阈值明确剪辑，以便用户知道丢弃了什么。
