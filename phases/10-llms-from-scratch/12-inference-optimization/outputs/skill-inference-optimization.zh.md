---
name: skill-inference-optimization
description: Diagnose and optimize LLM inference serving throughput, latency, and cost
version: 1.0.0
phase: 10
lesson: 12
tags: [inference, kv-cache, batching, speculative-decoding, vllm, optimization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="llm-inference-optimization-pattern"></a>

# LLM Inference 优化模式

两个阶段: prefill (计算受约束的、平行的)和解码(模拟受约束的、顺序的)。
每个优化都针对一个或两个目标。

```
Request -> Prefill (process prompt) -> Decode (generate tokens) -> Response
              |                            |
         Compute-bound               Memory-bound
         Optimize: fusion,           Optimize: batching,
         prefix caching              quantization, speculation
```

<a id="decision-framework"></a>

## 决策框架

<a id="step-1-identify-your-bottleneck"></a>

### 第一步: 识别你的瓶颈

计量任务: 工作量的字节比率 :

| 行动:字节 | Bound | 怎样才能优化 |
|----------|-------|-----------------|
| < 50 | 内存 | Quantize KV cache,增加 batch size |
| 50-200 | Transitional | 两个物质,从批量开始 |
| > 200 | 计算 | 核聚变 tensor parallelism, FP8 |

<a id="step-2-pick-your-engine"></a>

### 步骤2: 选取引擎

- **默认**: vLLM (最广泛的模型支持,PagedAtention, OpenAI- 兼容 API)
- **多方向 / structured output**: SGLang (目标) prefix caching,限制解码)
- **最大 NVIDIA 输送量**:天文台-LLM (内核聚变,H100上的FP8)

<a id="step-3-apply-optimizations-in-order"></a>

### 步骤3:按顺序优化

1. **KV cache** - 总是,没有负面
2. **Continuous batching** - 总是,没有负面(vLLM/SGLang 默认这样做)
3. **Prefix caching** - 启用,如果您共享 system prompts (大多数聊天的机器人做)
4. **Quantization** -- KV cache INT8/FP8 减少内存 2-4x 且质量损失最小
5. **Speculative decoding** - 添加,当潜伏比吞吐量更重要时
6. **Tensor parallelism** - 分开 GPUs 当模型不适合时

<a id="kv-cache-memory-formula"></a>

## KV cache 内存公式

```
per_token = 2 * num_layers * num_kv_heads * head_dim * bytes_per_param
total = per_token * sequence_length * num_concurrent_users
```

通用模型快速参考(BF16):

| 模型 | 每 token | 100个用户@ 4K |
|-------|-----------|----------------|
| Llama 3 8B 目标 | 32千卢比 | 12.5英镑 |
| Llama 3 70B 电话: | 320千卢比 | 125英镑 |
| Llama 3 405B (3 405B) | 504千亿卢比 | 197英镑 |

<a id="speculative-decoding-checklist"></a>

## Speculative decoding checklist

- 模型草案应小于目标5-10x(例如,70B的8B草案)
- 有效加速的接受率 > 70%
- 最能预测的文字(代码, structured output语言)
- 最差的创意/sampling- 繁重任务(低) temperature 帮助)
- 大多数工作量的EGLE > 目标草案 > n克

<a id="common-mistakes"></a>

## 常见错误

- 在批量=1时运行解码( 模拟连接, ) GPU 计算时闲置95%)
- 分配毗连 KV cache 区块( 使用 Paged 注意, 获取接近零的废物)
- Ignoring prefix caching 当80%的请求 共享相同 system prompt
- Over-provisioning GPU 模型的内存 weights,没有留下任何东西 KV cache
- 测量输送量而不测量延迟度(在10秒TTFT的高输送量是无用的)
- 使用 speculative decoding 高频 temperature (接受率低于50%)

<a id="monitoring-checklist"></a>

## 监测清单

- Time to first token (TTFT): prefill 延迟时间,目标 < 500米,用于互动
- Inter-token latency (ITL):解码速度,目标 < 50米 streaming
- 产出(tokens第二:所有同时使用的用户总数
- KV cache 使用:分配的缓存使用百分比
- 批量利用率:按迭代填充的批量槽百分比
- 队列深度: 请求等待批量槽
