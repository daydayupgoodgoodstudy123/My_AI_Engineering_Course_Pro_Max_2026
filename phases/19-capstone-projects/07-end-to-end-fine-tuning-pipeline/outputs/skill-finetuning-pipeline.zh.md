---
name: finetuning-pipeline
description: Run a reproducible data-to-SFT-to-DPO-to-serve fine-tuning pipeline with ablations, quantization, and a 2026 Model Openness Framework model card.
version: 1.0.0
phase: 19
lesson: 07
tags: [capstone, fine-tuning, axolotl, trl, dpo, grpo, vllm, eagle-3, mof]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定基准模型(Llama 3.3 8B、Quen3 14B或Gemma 3 12B)和任务特定数据集,建立一个单一指令的管道,产生一个供货端点和可复制 model card.

构建计划 :

1. 数据阶段:数据仪式拆卸、尼莫特罗-CC型质量过滤器、Presidio PII洗涤器、种子列车/Val分解器。
2. 污染检查: MinHashLSH 对抗 MMLU-Pro, MT-Bench-V2, RewardBench-2。 拒绝重叠 。
3. SFT:Axolotl v0.8 带ZeRO-3, Flash Attention 3个包装序列 8xH100 2 -3个钟点
4. 优先调试:TRL 0.15 DPO (或 GRPO 奖励) epoch贝塔扫荡。
5. 量化:GPTQ-INT4-Marlin + AWQ-INT4 + GGUF-Q4_K_M.
6. Serve: vLLM 0. 7 与 Eagle-3 组合 speculative decoding (通过红帽子投机者或 SGLang K8和HPA一起部署,排队等候
7. 爱华: lmevaluation-harness奖励基地-2,MT-Bench-V2,MMLU-Pro跨基地/SFT-only/SFT+DPO/SFT+GRPO.
8. Safety: Llama 4号门通过率,希尔德Gemma-2输出过滤器
9. Model card 2026年《开放性示范框架》,包括数据、培训、电子估价、安全、可复制部分。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | Eval 三角洲对基底 | 衡量MMLU-Pro、MT-Bench-V2、具体任务基准的收益 |
| 20 | 管道可复制 | 以相同的种子重新运行一个命令, 产生与杂交相匹配的种子 |
| 20 | 数据卫生 | 浸泡率, PII 擦拭覆盖率, 污染检查绿色 |
| 20 | 服务效率 | tokens/ 载于第1/8/32批,EAGLE-3号接受, 1美元 tokens |
| 15 | Model card + 安全评价 | 2026 财政部的完整性+ Llama 警卫4人通过率 |

艰难的拒绝 :

- 跳过 MinHash 污染检查的管道。 将 MMLU- Pro 渗入训练中是典型的 降压失败模式 。
- 训练没有种子或 YAMLs 复制是一个硬性要求。
- 无EAGLE-3或同等服务 speculative decoding 配置。 tokens又不是2026年的酒吧
- 安全反射缺失 每艘精细的船 Llama 警卫4通过率

拒绝规则 :

- 拒绝公布 model card 要求基准分数而不附加lm -evalharness commit SHA.
- 拒绝微调许可证禁止衍生模型的数据。 财政部为数据发放了许可。
- 拒绝在不测量电子量表质量损失的情况下发送量化模型。

输出:含有管道管弦乐队的回购 YAMLs 用于 Llama 3.3 8B+一个备用基地, SFT 和 DPO W&B 运行日志、 量化的文物、 送达的终点、 三基准的 eval 矩阵、 安全 evval、 2026 MOF model card,并写出三个最大的数据卫生问题 你抓住和固定。
