---
name: skill-quantization
description: Choose the right quantization strategy for deploying LLMs based on hardware, quality, and latency constraints
version: 1.0.0
phase: 10
lesson: 11
tags: [quantization, inference, deployment, optimization, fp8, int4, int8, gptq, awq, gguf]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="quantization-decision-framework"></a>

# Quantization 决定框架

在部署语言模型时,使用此框架选择正确的数字格式, quantization 方法,质量验证战略。

<a id="input-requirements"></a>

## 输入要求

提供：
- **模型** (名称, parameter 计数, 原精度)
- **目标硬件** (GPU 型号/VRAM, CPU,苹果硅,边缘设备)
- **延迟目标** (tokens/第二个, time to first token)
- **质量底层** (最多可接受) perplexity 增加量,基准三角洲)
- **服务模式** (batch size,最大上下文长度,同时使用)

<a id="quick-selection"></a>

## 快速选择

| 你的情况 | 格式 | 方法 | 预期质量损失 |
|---------------|--------|--------|----------------------|
| H100 GPU,最大输出量 | FP8 E4M3 级计算机 | 原生H100铸造 | < 0.1% |
| A100/A10,需要2x输送 | INT8 | LLM.int8() 或平滑量 | < 0.5% |
| 单发24GB GPU70B 型号 | INT4 | AWQ 或 GPTQ 组合键 | 1-3% |
| MacBook / 苹果硅 | INT4 GGUF 气压 | Q4_K_M 发 llama. cpp 组合键 | 1-2% |
| 移动/边缘设备 | INT4或INT3 号 | QAT + 设备专用 | 2-5% |
| 最大压缩,一些损失 | INT2 | QIP# 或 AQLM 组合键 | 5-15% |
| 培训mixed precision) | BF16 + FP32 累加 | 本地框架支持 | 0% |

<a id="precision-selection-by-component"></a>

## 按组件选择精度

并非全部 tensors 应该得到同样的待遇。

| 组件 | 安全最小值 | 推荐 | 避免 |
|-----------|-------------|-------------|-------|
| FFN weights | INT4 | INT4(阿拉伯新闻/全球新闻通讯网) | 无QAT的INT2 |
| Attention weights | INT4 | INT8或FP8 | INT2 |
| Embedding layer | INT8 | FP16(保持原样) | INT4 |
| 输出头 | INT8 | FP16(保持原样) | INT4 |
| KV cache | FP8 | FP8 或INT8 | 长期INT4 |
| Attention logits | FP16 | FP16或BF16 | INT8 |
| 启动(inference) | INT8 | FP8 或INT8 | INT4 |

<a id="method-comparison"></a>

## 方法比较

<a id="gptq"></a>

### GPTQ
- **当:** GPU inference,你想要一个与脸部相容的模型
- **Calibration 数据 :** 128例,2048年 tokens 每个
- **时间:** A100上70B的30-60分钟
- **工具 :** `gptqmodel`, `exllama`, `exllamav2`
- **强度 :** 大型动物园在抱起脸来
- **弱点 :** 在一些模型中应用比 AWQ 慢,质量略低于 AWQ

<a id="awq"></a>

### AWQ
- **当:** GPU inference,你想要最好的质量每位
- **Calibration 数据 :** 128个实例
- **时间:** A100上70B的15-30分钟
- **工具 :** `llmcompressor`, `vLLM` (本地支持)
- **强度 :** 最佳INT4质量, 快速应用, vLLM integration
- **弱点 :** 比GPTQ小得多的模型动物园

<a id="gguf"></a>

### GGUF
- **当:** CPU inference苹果硅树 llama.cpp 生态系统
- **备选案文:** Q2_K, 问题3_K_S/M/L, 问题4_K_S/M,问题5_K_S/M,问题6_K, 问题8_0, F16 号
- **建议的默认 :** Q4_K_M(最佳质量/大小平衡)
- **工具 :** `llama.cpp`, `ollama`, `LM Studio`
- **强度 :** 自成一体的文件, mixed precision、 大型生态系统
- **弱点 :** 不适合 GPU (设计用于 CPU/金属)

<a id="smoothquant"></a>

### SmoothQuant
- **当:** INT8 开 GPU,需要两个 weight 和激活 quantization
- **关键的想法 :** Migrate quantization 激活到 weights 通过每个频道的缩放
- **工具 :** `smoothquant`, `TensorRT-LLM`
- **强度 :** 启用 W8A8( 两个都 weights 和在INT8中启动),用于 2x 加速
- **弱点 :** 仅指INT8, 不延伸至INT4

<a id="quality-validation-protocol"></a>

## 质量验证协议

量化后,在部署前验证:

1. **Perplexity 测试。** 计算到 WikitText-2 或您的域名。 Delta < 0.5 是极好的, 0.5-1.0 是好的, > 2. 0是一个问题。

2. **基准扫描。** 运行 MMLU( 常规) , GSM8K( 数学) , HumanEval( 代码) 。 数学和代码对精确损失最为敏感 。

3. **产出比较。** 生成100个原始和量化模型的响应。 LLM目标:量化模型赢得或连接大于90% prompts.

4. **延迟度测量。** Measure tokens/ 第二次时间 batch size 1号目标 batch size。验证加速度说明质量成本。

5. **长发测试。** 如果服务于长环境( > 4K) tokens),测试您的最大上下文长度。 KV cache quantization 使用序列长度的错误复合。

<a id="memory-budget-calculator"></a>

## 内存预算计算器

```
Weight memory (GB) = parameters (B) * bits / 8 / 1.073741824
KV cache per token (MB) = 2 * num_layers * d_model * bits / 8 / 1048576
KV cache for context (GB) = kv_per_token * max_context_length / 1024
Activation memory (GB) ~ 1-4 GB (relatively constant, depends on batch size)
Total = weight_memory + kv_cache + activation_memory + overhead (10-20%)
```

实例 Llama 3 70B INT4, 32K 上下文:
- Weights: 70B * 4 / 8 / 1.07 = 32.6 GB
- KV cache (FP16): 2 * 80 * 8192 * 16 / 8 / 1e9 * 32768 = ~40 GB
- KV cache (FP8):~20GB
- 总计,FP8千伏:~55GB(合80GB A100)

<a id="common-mistakes"></a>

## 常见错误

| 错误 | 为何失败 | 修复 |
|---------|-------------|-----|
| 量化 embedding 平层改为INT4 | 第一层通过整个模型放大错误 | Keep embeddings 在FP16或INT8处 |
| 使用每 -tensor INT4的比额 | 一个外行会破坏所有行的精确度 | 使用每个频道或每组比例尺 |
| 未校准通用一般分类和标准/一般分类 | 没有具有代表性的数据,比例因素是错误的 | 使用您域的 128 个示例 |
| 所有层的比特宽相同 | 头层/最后一层比较敏感 | Mixed precision:第一个/最后一个比特高 |
| Quantizing KV cache 在非常长的背景下 | 带有序列长度的二次误差 | 使用 FP8 KV cache,而不是INT4 |
| 跳过质量验证 | 有些模型的量化差(特别是在边界方面) | 总是运行 perplexity +任务评估 |

<a id="deployment-recipes"></a>

## 部署津贴

<a id="recipe-1-vllm-with-awq-gpu-server"></a>

### 食谱 1 : vLLM 与 AWQ (GPU 服务器)
```
pip install vllm
vllm serve model-awq --quantization awq --dtype half --max-model-len 8192
```

<a id="recipe-2-llamacpp-with-gguf-macbook"></a>

### 食谱2: llama. 与 GGUF 连接的 cpp (MacBook)
```
./llama-server -m model.Q4_K_M.gguf -c 4096 -ngl 99
```

<a id="recipe-3-tensorrt-llm-with-fp8-h100"></a>

### 食谱3: 感应器-LLM 有FP8(H100)
```
trtllm-build --model_dir model --output_dir engine --dtype float16 --use_fp8
```
