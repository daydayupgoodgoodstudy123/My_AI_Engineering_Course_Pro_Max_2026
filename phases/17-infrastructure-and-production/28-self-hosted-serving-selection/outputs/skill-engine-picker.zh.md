---
name: engine-picker
description: Pick a self-hosted LLM engine (llama.cpp, Ollama, TGI, vLLM, SGLang) given hardware, scale, and workload. Name 2026 TGI maintenance mode as a migration trigger.
version: 1.0.0
phase: 17
lesson: 28
tags: [self-hosted, vllm, sglang, llama-cpp, ollama, tgi, trt-llm, engine-selection]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定硬件(CPU 苹果硅/AMD/NVIDIA Hopper/NVIDIA Blackwell,规模(单一用户/小团队/生产/企业)和工作量(一般聊天/一般谈话/一般对话) agentic / RAG / 长文本/ 代码), 生成引擎建议 。

显示 :

1. 引擎,指定引擎名称,打开硬件第一, 缩放第二, 工作量第三树。
2. 为什么不选择其他的。对于每个替代引擎,请说明为什么它不是选手(TGI维护模式,AMD排除 TRT-)LLM奥拉玛是只爱听话的人
3. 管道。 如果生产,请说明管道模式(dev Ollama  中转) llama. cpp vLLM/SGLang)和确认 weight 格式(GGUF或HF)流动。
4. 生产堆放:在生产规模上,指向第17阶段 18(生产堆放)、17(分类)、11(了解剖析路由器)的构成。
5. 跨国移徙:如果现任者是跨国移徙,请具体说明移徙计划和时间表——不是紧急的,而是应在6个月内开始。
6. 硬件注意事项。指出两项硬性约束：仅有 CPU → llama.cpp；AMD → 不能使用 TRT-LLM。

艰难的拒绝 :
- 2026年向TGI默认新工程。拒绝-维护模式。
- Ollama 用于共享的 共享生产, 位于 > 1 同步用户。 拒绝 - 输送缺口 。
- 建议 TRT --LLM 拒绝 - AMD/ 非 NVIDIA 是一个硬块 。

拒绝规则 :
- 如果硬件混合(有些AMD,有些NVIDIA),则需要每个组群引擎的决定;不强制使用一个发动机。
- 如果生产规模的工作量“未知/一般”,默认为 vLLM 并计划一个重新 -evaluation 3个月后,交通数据。
- 如果团队想要"最快的每 GPU 没有 Blackwell 的功能 availability"坚持只用霍伯,确认 - TRTLLM 或 vLLM 两者都可接受。

产出:一页建议,包括引擎、替代品被排除、管道、生产堆叠、TGI迁移态势。 结束于单一季度审查:当工作量发生重大变化时重新评估引擎选择。
