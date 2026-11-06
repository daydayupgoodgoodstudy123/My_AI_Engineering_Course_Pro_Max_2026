---
name: skill-frame-sampler-auditor
description: Audit a video pipeline's frame sampler for off-by-one, short-clip handling, and crop consistency
version: 1.0.0
phase: 4
lesson: 12
tags: [computer-vision, video, sampling, debugging]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="frame-sampler-auditor"></a>

# 帧采样器审核器

帧 sampling 是视频管道中断的地方。这里的错误会传播到每个下游指标。

<a id="when-to-use"></a>

## 何时使用

- 编写一个新的视频数据加载器。
- 复制论文中的数字和训练准确性低于报告的水平。
- 调试其评估精度在运行过程中不稳定的视频模型。

<a id="inputs"></a>

## 输入

- `sampler_code`：Python 函数，采用 (num_frames_total, T) 并返回 T 索引。
- `T`：目标剪辑长度。
- 可选测试用例：要执行的 `num_frames_total` 值（例如 `[3, T-1, T, T+1, 30, 300, 3000]`）。

<a id="checks"></a>

## 支票

<a id="1-short-clip-handling"></a>

### 1. 短夹处理
饲料 `num_frames_total < T`。每个返回的索引必须位于 `[0, num_frames_total - 1]` 中。标准填充策略是对剩余位置重复最后一帧。

<a id="2-boundary-indices"></a>

### 2. 边界指标
饲料 `num_frames_total == T`。返回的索引应准确为 `[0, 1, ..., T-1]`。

<a id="3-uniform-distribution"></a>

### 3. 均匀分布
饲料 `num_frames_total == 10 * T`。返回的索引应该单调递增并且大致均匀分布。

<a id="4-dense-window-bounds"></a>

### 4. 密集窗口边界
对于稠密的 sampling，喂入 `num_frames_total == 3 * T`。返回的索引应形成一个连续的窗口，切勿跨越剪辑的末尾。

<a id="5-determinism"></a>

### 5.决定论
使用相同的输入和（对于确定性采样器）相同的 RNG 调用采样器两次。索引应该匹配。

<a id="6-crop-consistency"></a>

### 6. 作物一致性
如果管道还返回每帧的空间裁剪，请对具有相同种子的同一剪辑运行采样器两次，并确认每个帧使用相同的裁剪框（相同的 `(x, y, w, h)`）。一个剪辑中每帧的不同裁剪会破坏时间连贯性，是一个典型的无声错误。可接受的变化：每个剪辑应用增强 **，在剪辑内一致。

<a id="report"></a>

## 报告

```
[sampler audit]
  name: <function name>
  T:    <int>

[short-clip handling]
  passed | failed (<details>)

[boundary]
  passed | failed

[uniform spacing]
  passed | failed (<stddev of gaps>)

[dense window]
  passed | failed (<details>)

[determinism]
  passed | failed

[crop consistency]
  passed | failed (<per-frame crop varies: yes/no>)

[verdict]
  ok | fix required
```

<a id="rules"></a>

## 规则

- 如果短剪辑处理返回超出范围的索引，切勿将采样器标记为“正常”。
- 密集采样器不应返回穿过 `num_frames_total - 1` 的窗口。
- 如果采样器是随机的（密集的），则仅使用显式种子 RNG 来测试确定性。
- 建议但不要默默地修复规范策略：用最后一帧填充、将窗口夹到末端、将半开间隔舍入。
