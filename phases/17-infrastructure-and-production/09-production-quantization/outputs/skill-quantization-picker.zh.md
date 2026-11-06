---
name: quantization-picker
description: Pick a 2026 quantization format given hardware, engine, workload, and quality tolerance, and produce a calibration + validation plan.
version: 1.0.0
phase: 17
lesson: 09
tags: [quantization, awq, gptq, gguf, fp8, nvfp4, calibration]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定硬件(CPU / H100 / H200 / B200 / GB200, 计数) 引擎(llama. cpp / 电子格式 vLLM 转基因 -LLM / SGLang),模型(大小+任务类型——常规聊天/推理/代码/多LoRA),以及质量容忍度(能够吸收人类生命val/MATH/MMLU的N点下降),选择 quantization 格式化和制定审定计划。

显示 :

1. 建议格式。 其中之一:GGUF Q4_K_男、女、女、女5岁_K_M, GPTQ-Int4 + Marlin, AWQ-Int4 + Marlin, FP8, NVFP4 + FP8 KV, 或堆叠的组合。 由决定树说明 : CPU GGUF; 推理  FP8; 多个-LoRA 在 vLLM GPTQ; 常规 GPU 聊天 + Q; Blackwell 验证 + NVFP4。
2. 记忆预算。 weights + KV cache (在报告的同值x上下文)+激活。确认它符合目标 GPU 或喊出多个-GPU requirement.
3. Calibration 计划。 数据集源( AWQ/ GPTQ 的域匹配; 通用 C4/ WikiText 作为最后手段) 。 样本数 (500-2000 域名) 。 校验设置 (10% 由 calibration pool).
4. 验证计划 Eval set 与任务匹配: 代码为人类值, 逻辑为MATH/ MMLU, 聊天为MT- Bench。 BF16 基线对量化。 如果降低 Q 质量耐受度, 则船舶 。
5. KV cache 另选决定。 weight quantization建议采用FP8 KV作为推理依据;如果 attention 准确度是边缘的; INT8 KV 仅在验证后才能进行。
6. Rollback 路径。保留 BF16/FP8 weights 。 如果生产质量下降, 将换回标记 。

艰难的拒绝 :
- 建议NVFP4 weights 未经电子估价验证的推理重工作量。
- 校准域模型的通用网络数据。 总是使用域内数据 。
- 忘记 KV cache 总是逐项列出。
- 要求输送量号码而不点名(Marlin-AWQ对平原AWQ为10x)。

拒绝规则 :
- 如果工作量本身就质量边缘(无限制的创造性生成、边际推理),则拒绝积极使用INT4。 保持 FP8 或 BF16 。
- 如果引擎是的话 llama.cpp,拒绝 GGUF 以外的任何格式。匹配引擎的格式是表格的基本要求。
- 如果用户无法运行1,000个样本的模拟, 请拒绝。 没有盲点 quantization 正在生产。

产出:一页 quantization 选择所选格式, HBM 预算, calibration 计划,验证计划, KV cache 决定, rollback 路径。结尾处有一个“测量下一步什么”段落,其中命名了电子方位三角形中的某一个, KV cache 最高货币下的压力,或实际吞吐量 batch size 取决于关键的风险。
