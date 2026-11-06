---
name: inference-optimizer
description: Pick attention implementation, KV cache strategy, quantization, and speculative decoding for a new inference deployment.
version: 1.0.0
phase: 7
lesson: 12
tags: [transformers, inference, flash-attention, kv-cache]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 inference 部署（模型名称 + 参数、目标硬件、并发性、最大上下文长度、延迟 SLO、吞吐量目标），输出：

1. 服务堆栈。 vLLM（默认生产）、SGLang（每个 token 的最低延迟）、TensorRT-LLM（NVIDIA 最佳）、llama.cpp （边缘/CPU），MLX（苹果芯片）。一句话理由。
2. Attention 实施。闪存 Attention 2（Ampere/Ada 默认）、闪存 Attention 3（Hopper）、闪存 Attention 4（Blackwell，仅前向）。指定后备。
3. KV cache。 Dtype（默认为 fp16，如果支持则为 fp8）、分页与连续、prefix caching 开/关、并行 sampling 的共享 KV。
4. Quantization。 fp16 / bf16（默认）、int8（仅限 weight）、AWQ / GPTQ / GGUF 用于 weights。仅在进行基准测试时激活 quantization。
5. 额外的加速。 Speculative decoding（EAGLE 2 / Medusa /草稿模型）、continuous batching（始终开启）、chunked prefill（长prompt工作负载）、prefix caching（如果重复） prompts。

拒绝部署 Flash Attention 4 进行训练 - 它在启动时仅向前。在没有对目标任务进行质量影响基准测试的情况下，拒绝推荐 fp8 KV cache。将任何没有 GQA 的 70B+ 模型标记为在 32K+ 上下文中具有无法管理的 KV cache。对于具有重复 system prompts 的任何 agent/工具调用部署，需要启用 prefix caching。
