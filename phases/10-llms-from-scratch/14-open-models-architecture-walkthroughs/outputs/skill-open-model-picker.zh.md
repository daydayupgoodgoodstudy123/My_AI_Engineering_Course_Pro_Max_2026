---
name: open-model-picker
description: Pick an open LLM family, quantization, and inference stack for a given deployment target.
version: 1.0.0
phase: 10
lesson: 14
tags: [open-models, llama, deepseek, mixtral, qwen, gemma, moe, gqa, mla, quantization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


考虑到部署目标(GPU 类型, VRAM / GPU数字 GPUs,目标上下文长度,目标 p50/p99 延迟,同时提出最高峰的要求)和任务简介(聊天、代码、推理、长文本检索、工具使用),建议采用开放模型,同时为第14课的6个建筑把手提供明确的推理。

显示 :

1. 3名候选人,每个候选人都有总参数、活性参数(A/CN.9/WG.III/WP.9)。MoE- 觉悟,建筑标志(规范/激活/位置/) attention / MoE 以及它之所以会排入最后名单的原因
2. 记忆预算检查。 对于顶级候选人 : weight BF16和选定 quantization; KV cache 目标范围 batch size; 激活主机。如果 weights + KV cache +激活超过可用的 VRAM。
3. Quantization 选项。 GPTQ-4bit、 AWQ-4bit、 FP8 或 BF16。 使用任务精确度来说明理由( 代码/ 数学/ 推理任务从攻击性中得益更大) quantization 或检索)。
4. Inference 堆叠。 vLLM特索瑞特, 特索瑞特... ...LLM, SGLang, 或 llama.cpp. 说明反对: continuous batching 需要时间 speculative decoding 支持, quantization 格式兼容性, 单节对多节表层学 。
5. 检查输液是否正常 Prefill tokens/秒数和解码 tokens/秒估计数 GPU 内存带宽(解码)和TFLOPs (prefill如果解码通过量低于目标同时使用层,则拒绝这项建议。
6. 后退。 如果顶级候选人超过 VRAM 或工作量预算, 则第二选 。 总是列出一个 。

艰难的拒绝 :
- 单一24GB消费者的浓度超过30B的模型 GPU 不卸载或攻击性 quantization.
- MoE 模型在服务堆叠上 没有专家平行支持。
- 关于没有GQA或MLA的架构的长文本(128k+)KV cache (b) 爆炸)。
- 任何未指明具体示范修订本的建议(例如, "Llama 3 8B 说明 v3.1, 不是“Llama 3").

产出:一页建议列出模式, quantization,堆叠,每个决定的编号证据。结尾是“如果.........”段落,其中指定具体能力或部署 parameter 那样会改变选择的
