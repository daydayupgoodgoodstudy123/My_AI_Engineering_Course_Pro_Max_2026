---
name: skill-pipeline-budget-planner
description: Given target latency and throughput, assign a time budget to every pipeline stage and flag which stage will miss its budget first
version: 1.0.0
phase: 4
lesson: 16
tags: [vision, pipeline, performance, deployment]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="pipeline-budget-planner"></a>

# 管道预算规划师

将延迟/吞吐量目标转化为逐步预算，以便每个团队成员都知道他们的设计目标是多少。

<a id="when-to-use"></a>

## 何时使用

- 在构建新的愿景服务之前，要为每个阶段设定期望。
- 在第一个基准之后，看看哪个阶段离预算最远。
- 当 SLA 发生变化并且需要重新协商预算时。

<a id="inputs"></a>

## 输入

- `p95_latency_target_ms`：每个请求的预算。
- `target_qps`：每个副本的吞吐量。
- `stages`：`{ name: str, current_ms: float }`的列表。

<a id="allocation-rules"></a>

## 分配规则

如果没有提供当前测量值，则七个标准阶段的默认分配：

| 舞台 | 分享 |
|-------|-------|
| 解码+预处理 | 15% |
| 探测器向前 | 55% |
| 后处理检测（NMS、钳位） | 5% |
| 裁剪 + 调整分类器大小 | 5% |
| 分类器前向 | 15% |
| 模式验证 | <1% |
| 响应序列化 | 4% |

在 GPU 绑定的管道（云）上，检测器份额通常会上升到 70%。在CPU上，预处理和分类器批处理吃的比较多。

<a id="report"></a>

## 报告

```
[budget plan]
  p95 target:  <ms>
  throughput:  <qps per replica>

| stage               | target_ms | current_ms | headroom | gate |
|---------------------|-----------|------------|----------|------|
| decode+preprocess   | ...       | ...        | ...      | ok|X |
| detector            | ...       | ...        | ...      | ok|X |
| ...                 | ...       | ...        | ...      |      |

[bottleneck]
  stage:  <name>
  miss:   <ms over budget>
  lever:  <specific action>

[levers]
  decode+preprocess:   Pillow-SIMD, libjpeg-turbo, decode on GPU via NVJPEG
  detector:            smaller backbone, lower input resolution, INT8, TensorRT
  postprocess:         GPU-side NMS (torchvision.ops), fused masks
  crop+resize:         GPU crop with grid_sample, batched interpolate
  classifier:          smaller backbone, INT8, warm cache, batch
  schema:              skip validation in hot path, validate at boundaries only
  response:            orjson, stream protobuf
```

<a id="rules"></a>

## 规则

- 切勿建议从生产路径中删除模式验证；建议将其移至边界。
- 如果预处理未达到预算，请务必在更改模型之前尝试 Pillow-SIMD 或 NVJPEG。
- 如果检测器未命中目标值超过 30%，则切换模型而不是优化当前模型。
- 当 current_ms > 1.1 * target_ms 时，将门标记为 `X`；如果在预算的 10% 以内，请标记 `ok`。
