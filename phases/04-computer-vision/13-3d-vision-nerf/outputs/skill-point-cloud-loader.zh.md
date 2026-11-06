---
name: skill-point-cloud-loader
description: Write a PyTorch Dataset for .ply / .pcd / .xyz files with correct normalisation, centring, and point sampling
version: 1.0.0
phase: 4
lesson: 13
tags: [3d-vision, point-cloud, data-loading, pytorch]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="point-cloud-loader"></a>

# 点云加载器

将 3D 扫描文件的文件夹转换为准备训练的 PyTorch `Dataset`。

<a id="when-to-use"></a>

## 何时使用

- 开始一个新的点云分类/分割项目。
- 在 `.ply`、`.pcd` 和 `.xyz` 格式之间切换。
- 调试一个训练没有错误但收敛性很差的模型；数据加载器规范化通常是错误的。

<a id="inputs"></a>

## 输入

- `data_root`：点云文件和带有标签的可选 CSV 的文件夹。
- `file_format`：层数 | 多晶硅 | XYZ | npy。
- `num_points`：固定sampling大小，通常为1024或2048。
- `augmentation`：无 | 旋转 | 抖动 | 混合。

<a id="normalisation-policy"></a>

## 正常化政策

每个生产点云管道按顺序应用：

1. **Centre** 云：减去质心。
2. **Scale** 到单位球体：除以距中心的最大距离。
3. **样本** `num_points` 积分。如果云有更多，请使用 ** 最远点 sampling** (FPS) 来实现忠实的形状表示，或使用随机 sampling 来提高速度。如果较少，则重复点。
4. **Shuffle** 点顺序（无论如何，顺序对于模型来说并不重要，但洗牌会破坏意外的顺序依赖性）。

<a id="output-template"></a>

## 输出模板

```python
import numpy as np
import torch
from torch.utils.data import Dataset

try:
    import open3d as o3d
    HAS_O3D = True
except ImportError:
    HAS_O3D = False

def _read_ply(path):
    if HAS_O3D:
        pc = o3d.io.read_point_cloud(path)
        return np.asarray(pc.points, dtype=np.float32)
    # Fallback: minimal ascii-ply reader
    ...

def _fps(points, k):
    idx = np.zeros(k, dtype=np.int64)
    dist = np.full(len(points), np.inf)
    seed = np.random.randint(len(points))
    idx[0] = seed
    for i in range(1, k):
        dist = np.minimum(dist, ((points - points[idx[i-1]]) ** 2).sum(axis=1))
        idx[i] = int(np.argmax(dist))
    return idx

def normalise(points):
    centre = points.mean(axis=0)
    points = points - centre
    scale = np.max(np.linalg.norm(points, axis=1))
    return points / max(scale, 1e-8)

class PointCloudDataset(Dataset):
    def __init__(self, files, labels, num_points=1024, augment=False):
        self.files = files
        self.labels = labels
        self.num_points = num_points
        self.augment = augment

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        pts = _read_ply(self.files[i])
        pts = normalise(pts)
        if len(pts) >= self.num_points:
            idx = _fps(pts, self.num_points)
            pts = pts[idx]
        else:
            reps = int(np.ceil(self.num_points / len(pts)))
            pts = np.tile(pts, (reps, 1))[:self.num_points]
        # Shuffle point order to break any accidental dependencies (especially
        # important when tiling repeats points in deterministic order).
        np.random.shuffle(pts)
        if self.augment:
            theta = np.random.uniform(0, 2 * np.pi)
            R = np.array([[np.cos(theta), 0, np.sin(theta)],
                          [0, 1, 0],
                          [-np.sin(theta), 0, np.cos(theta)]], dtype=np.float32)
            pts = pts @ R
            pts = pts + np.random.normal(0, 0.02, pts.shape).astype(np.float32)
        pts = np.ascontiguousarray(pts, dtype=np.float32)
        return torch.from_numpy(pts).transpose(0, 1), int(self.labels[i])
```

<a id="report"></a>

## 报告

```
[dataset]
  files:          <N>
  format:         <ply|pcd|xyz|npy>
  points_per_sample: <int>
  normalise:      centre + unit sphere
  sampling:       FPS | random
  augmentation:   <list>
```

<a id="rules"></a>

## 规则

- 缩放之前始终居中；交换顺序会改变“单位球体”的含义。
- 对于形状任务，优先选择 FPS 而不是随机 sampling；随机对于分割来说是很好的，无论如何，每个点都很重要。
- evaluation期间切勿增持；仅在训练期间。
- 如果点云文件包含颜色或法线作为额外通道，请扩展数据集以返回 `(3 + C, num_points)` tensor，而不仅仅是 xyz。
