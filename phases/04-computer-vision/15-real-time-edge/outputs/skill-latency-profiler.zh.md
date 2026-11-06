---
name: skill-latency-profiler
description: Write a complete latency-benchmarking script with warmup, synchronisation, percentiles, and memory tracking
version: 1.0.0
phase: 4
lesson: 15
tags: [edge, deployment, profiling, benchmarking]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="latency-profiler"></a>

# 延迟分析器

为任何 PyTorch 模型生成严格的延迟基准。下游任何人都可以真正信任的报告。

<a id="when-to-use"></a>

## 何时使用

- 在选择一个进行部署之前比较多个候选骨干网。
- 量化或修剪之前和之后。
- 运行时更改后（eager vs ONNX vs TensorRT）。
- 生成部署就绪报告。

<a id="inputs"></a>

## 输入

- `model`: PyTorch `nn.Module`.
- `input_shape`：像`(1, 3, 224, 224)`这样的元组。
- `device`: `cpu` | `cuda` | `mps`.
- `warmup`：默认10。
- `iters`：默认100。

<a id="checks"></a>

## 支票

<a id="1-warmup"></a>

### 1. Warmup
运行模型 `warmup` 次，无需计时。捕获先行 JIT 编译和冷缓存效果。

<a id="2-synchronisation"></a>

### 2. 同步
对于`cuda`，在每次定时forward pass之前和之后调用`torch.cuda.synchronize()`。
对于`mps`，请致电`torch.mps.synchronize()`。

<a id="3-timer"></a>

### 3. 定时器
使用 `time.perf_counter()` 进行挂钟测量。转换为毫秒。

<a id="4-percentiles"></a>

### 4. 百分位数
对完整的时间列表进行排序。报告`p50, p90, p95, p99, mean, std`。

<a id="5-memory"></a>

### 5. 记忆
对于 `cuda`，运行后调用 `torch.cuda.max_memory_allocated()` 并减去任何基线。
对于`cpu`，前后使用`tracemalloc`或`psutil.Process().memory_info().rss`。

<a id="6-batch-size-sweep"></a>

### 6. 批量扫描
（可选）重复 `batch_size in [1, 4, 16, 32]` 的基准测试，以揭示吞吐量与延迟的权衡。

<a id="output-template"></a>

## 输出模板

```python
import time
import torch
import psutil, os

def profile(model, input_shape, device="cpu", warmup=10, iters=100):
    proc = psutil.Process(os.getpid())
    baseline_rss = proc.memory_info().rss / 1e6

    model = model.to(device).eval()
    x = torch.randn(input_shape, device=device)

    def sync():
        if device == "cuda":
            torch.cuda.synchronize()
        elif device == "mps":
            torch.mps.synchronize()

    with torch.no_grad():
        for _ in range(warmup):
            model(x)
        sync()
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()

        times = []
        for _ in range(iters):
            sync()
            t0 = time.perf_counter()
            model(x)
            sync()
            times.append((time.perf_counter() - t0) * 1000)

    times.sort()
    mean = sum(times) / len(times)
    std  = (sum((t - mean) ** 2 for t in times) / len(times)) ** 0.5

    def pct(p):
        idx = max(0, min(len(times) - 1, int(len(times) * p) - 1))
        return times[idx]

    report = {
        "p50_ms":  pct(0.50),
        "p90_ms":  pct(0.90),
        "p95_ms":  pct(0.95),
        "p99_ms":  pct(0.99),
        "mean_ms": mean,
        "std_ms":  std,
        "rss_mb":  proc.memory_info().rss / 1e6 - baseline_rss,
    }
    if device == "cuda":
        report["peak_cuda_mb"] = torch.cuda.max_memory_allocated() / 1e6

    return report
```

<a id="rules"></a>

## 规则

- 始终运行warmup；永远不要相信先行时机。
- 百分位数，而不是平均值——单个异常值可以使平均值翻倍，但几乎无法移动 p50。
- 使用与生产相同的输入_形状； 224x224 上的延迟不是 384x384 上的延迟。
- 对于CUDA，切勿省略`torch.cuda.synchronize()`；没有它，数字就没有意义。
- 将火炬版本、CUDA 版本和设备名称与数字一起记录 - 否则它们将不再具有可比性。
