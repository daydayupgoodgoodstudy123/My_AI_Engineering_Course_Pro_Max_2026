---
name: skill-mot-evaluator
description: Write a complete evaluation harness for MOTA / IDF1 / HOTA against ground-truth tracks
version: 1.0.0
phase: 4
lesson: 27
tags: [mot, evaluation, tracking, metrics]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="mot-evaluator"></a>

# MOT评估器

将跟踪器的输出包装到标准 MOTA/IDF1/HOTA 管道中，以便您可以与文献进行公平比较。

<a id="when-to-use"></a>

## 何时使用

- 在 MOT17 / MOT20 / DanceTrack / SportsMOT 上对新跟踪器进行基准测试。
- 在您自己的镜头上将 ByteTrack 与 BoT-SORT 和 SAM 2 进行比较。
- 为论文或 PR 描述生成可重复的数字。

<a id="inputs"></a>

## 输入

- `predictions`：`(track_id, x, y, w, h, confidence)` 元组的每帧列表。
- `ground_truth`：`(gt_id, x, y, w, h)` 元组的每帧列表。
- `iou_threshold`：MOTA 典型值为 0.5； HOTA 使用扫描。
- `evaluator`：`py-motmetrics`（MOTA、IDF1）或`TrackEval`（HOTA）。

<a id="output-format-contract"></a>

## 输出格式约定

`py-motmetrics` 和 `TrackEval` 都期望特定的磁盘格式：

```
# predictions.txt
<frame>,<track_id>,<x>,<y>,<w>,<h>,<confidence>,-1,-1,-1

# ground_truth.txt
<frame>,<gt_id>,<x>,<y>,<w>,<h>,1,-1,-1,-1
```

框架是 1 索引的，盒子是 (x, y, w, h)，而不是 (x1, y1, x2, y2)。转换是大多数集成错误存在的地方。

<a id="steps"></a>

## 步骤

1. 将跟踪器的输出转换为 MOT Challenge 文本格式。
2. 对这两个文件运行 `py-motmetrics.io.loadtxt`。
3. 使用 `mm.metrics.create().compute()` 计算 MOTA + IDF1。
4. 对于 HOTA，使用相同的文件和 `Metrics: HOTA` 调用 `TrackEval`。
5. 将仪表板结果保存为 JSON。

<a id="implementation-sketch"></a>

## 实施草图

```python
import motmetrics as mm

def evaluate_mota_idf1(pred_path, gt_path):
    gt = mm.io.loadtxt(gt_path, fmt="mot15-2D")
    pred = mm.io.loadtxt(pred_path, fmt="mot15-2D")
    acc = mm.utils.compare_to_groundtruth(gt, pred, dist="iou", distth=0.5)
    metrics = mm.metrics.create().compute(
        acc, metrics=["num_frames", "mota", "motp", "idf1", "idp", "idr", "num_switches"]
    )
    return metrics


def write_mot_txt(predictions, path):
    with open(path, "w") as f:
        for frame_idx, detections in enumerate(predictions, start=1):
            for tid, x, y, w, h, conf in detections:
                f.write(f"{frame_idx},{tid},{x:.2f},{y:.2f},{w:.2f},{h:.2f},{conf:.3f},-1,-1,-1\n")
```

<a id="report"></a>

## 报告

```
[mot evaluation]
  frames:     <int>
  gt tracks:  <int>
  pred tracks: <int>

[metrics]
  MOTA:       <float>
  MOTP:       <float>
  IDF1:       <float>
  IDP/IDR:    <float/float>
  ID switches: <int>
  HOTA:       <float>  (from TrackEval)
```

<a id="rules"></a>

## 规则

- 在输出文本文件中始终使用 1 索引帧； MOT 工具期望如此。
- 在写入之前将 (x1, y1, x2, y2) 转换为 (x, y, w, h)。
- 不要单独报告 MOTA 以进行现代比较；包括 IDF1 和 HOTA。
- 留意 MOT17 上的私人检测和公共检测——它们是单独评估的，混合在一起会增加分数。
- 记录每个序列的分数；聚合隐藏了单个困难序列的失败。
