<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-07--end-to-end-fine-tuning-pipeline-data-to-sft-to-dpo-to-serve"></a>

# 综合项目 07：端到端 Fine-Tuning 流程——从数据、SFT、DPO 到模型服务

> 一种8B模型 以自己的数据训练, DPO- 以自己的偏好,量化,投机破解, 并用可计量的1美元 tokens。2026年的开放堆叠是Axolotl v.8.,TRL 0.15, 循环脱落, GPTQ/AWQ/GGUF, quantization, vLLM 0.7和EAGLE-3供使用。 YAML 并发表 model card 2026年的开放性示范框架。

**类型:** Capstone
**语言:** Python (pipeline), YAML (配置), Bash( 脚本)
**先修要求:** 第二阶段(ML),第三阶段(DL),第7阶段(A/C.5/49/70,附件)。transformers第十阶段(LLMs 11阶段(从零开始)LLM 工程,第17阶段(基础设施),第18阶段(安全)
**实施阶段:** P2 ; P3 ; P7 ; P10 ; P11 ; P17 ; P18
**时间:** 35小时

<a id="problem"></a>

## 问题

2026年所有认真的人工智能团队都有一个 fine-tuning 并非因为它们运输了前沿基地模型,而是因为下游适应——领域 SFT, DPO 与标签优惠对照, speculative decoding与EAGLE-3一起服务——这是可以衡量的赢家生存的地方。Axolotl v0.8处理多个-GPU SFT 配置 TRL 0.15 把手 DPO 和 GRPO阴沉让你快速单身GPU iteration. vLLM 0. 7 与 EAGLE-3 推进解码2-3x, 且不发生质量损失。 工具工作; 手工艺在 YAMLs数据卫生,以及评估纪律

您将运行 8B 基础( Y)Llama 3.3, Quen3, 或Gemma 3, 至 SFT 然后 DPO 计算服务量,衡量收益evaluation-harness奖励Bench-2,MT-Bench-V2和MMLU-Pro。 model card 点是复制——一个命令将整个管道重新运行到结束。

<a id="concept"></a>

## 概念

输油管有五个阶段。 **Data**: 卸载( MinHash / Datatrove), 质量过滤器( Nemotron- CC 样式分类器), PII 擦拭, 与公众对比的分解卫生检查 benchmark contamination. **SFT**:阿克斯罗特 YAML3号ZeRO -3号,8xH100, 接弦计划,包装序列,2 -3个时代。 **DPO 或 GRPO**:TRL 配置, 1 epoch,优选对,或是标有人类标签的,或是模型判断的,是贝塔调试。 **Quantize**部署灵活性:通用通用标准+ AWQ+ GGUF。 **Serve**: vLLM 0.7 带有EAGLE-3号投机头(或) SGLang 和斯佩克福格, K8s部署, HPA 排队等候。

减法是交付品: SFT- 仅对Vs SFT+DPO 与 SFT+GRPO 三个具体任务基准。 tokens/ 按照第1批/ 8批/ 32批,EAGLE-3号接收率, 1美元 tokens安全反射: Llama 警卫4通过率 Model card:偏差 evaluations,可复制种子,数据许可。

<a id="architecture"></a>

## 建筑

```
raw data (HF datasets + internal)
    |
    v
Datatrove dedup + Nemotron-CC quality filter + PII scrub
    |
    v
split hygiene (MMLU-Pro contamination check)
    |
    v
Axolotl SFT config (YAML)  ---> 8xH100, ZeRO-3
    |
    v
TRL DPO / GRPO config       ---> 4xH100, 1 epoch
    |
    v
GPTQ + AWQ + GGUF quantize
    |
    v
vLLM 0.7 + EAGLE-3 speculative decoding
    |
    v
K8s deployment, HPA on queue-wait
    |
    v
lm-eval-harness + RewardBench-2 + MT-Bench-v2 + MMLU-Pro
    |
    v
model card (2026 MOF) + safety eval (Llama Guard 4)
```

<a id="stack"></a>

## 堆栈

- 数据: 用于拆卸的数据仪, 用于质量的 Neprotron- CC 分类器, PII 的 Presidio
- Base: Llama 3.3 8B, Quen3 14B, 或 Gemma 3 12B
- SFT:Axolotl v0.8 带ZeRO-3, Flash Attention 3个包装序列
- 优先调试:TRL 0.15至 DPO 或 GRPO; 单词不通 --GPU iteration
- Quantization电话:GPTQ(马尔林),AWQ,GGUF 传真:1(212)963-5047 llama.cpp
- Serving: vLLM 0. 7 与 Eagle-3 组合 speculative decoding (或 SGLang 0.4+斑点)
- 爱华: lmevaluation-harness奖励区-2号,MT-Bench-V2号,MMLU-Pro
- 安全反射 : Llama 卫兵4号,盾牌Gemma-2号
- Infrastructure: Kubernetes + NVIDIA 设备插件,列等候度
- Observability:W&B用于培训,Langfuse用于 inference

```figure
ce-finetune-stages
```

<a id="build-it"></a>

## 动手实现

1. **数据管道。** 运行生体数据仪解析。 应用 Nemostron- CC 式的质量分类器。 预设式擦除 PII 。 写入列车/ val 和清晰种子分割 。

2. **污染检查。** 对于每一个验证分割, 都根据 MMLU- Pro、 MT- Bench- v2 测试组计算 MinHash。 拒绝任何重叠 。

3. **Axolotl SFT.** YAML 3级,FA3级,序列包装 2-3级,8xH100级,日志到W&B

4. **TRL DPO / GRPO.** 拿着 SFT checkpoint运行一个 epoch 的 DPO 或 GRPO 具有数学/代码的可核实奖赏。

5. **Quantize.** 生产三个量子:GPTQ-INT4-Marlin,AWQ-INT4, GGUF-Q4_K_M 表示 llama. cpp. 记录大小和名义输送量。

6. **服务 speculative decoding.** vLLM 0.7 配置EAGLE-3 高级主管,通过红帽子投机者培训。 tail latency / 8/32. 报告 1万美元 tokens 与 Anthropic / OpenAI 在同一一次的反射。

7. **爱瓦尔矩阵** 运行 lm -eval --harness奖励Bench-2,MT-Bench-V2,MMLU-Pro基地, SFT-仅, SFT+DPO, SFT+GRPO来张桌子

8. **安全反射仪** Llama 4号警戒通过率在Dev设置,希尔德Gemma-2输出过滤器。

9. **Model card.** 2026年财政部模板:数据、培训、评价、安全、许可证、复制部分 YAMLs 和 commit SHAs.

<a id="use-it"></a>

## 实际应用

```
$ ./pipeline.sh config/llama3.3-8b-domainX.yaml
[data]    300k deduped, 12k filtered, 280k accepted (seed=7)
[SFT]     3 epochs, 8xH100, 6h12m, val loss 1.42 -> 1.03
[DPO]     1 epoch, beta=0.08, 4xH100, 1h40m
[quant]   GPTQ-INT4 4.6 GB, AWQ-INT4 4.8 GB, GGUF-Q4_K_M 5.1 GB
[serve]   vLLM 0.7, EAGLE-3 acceptance 0.74, p99 126ms @ bs=8
[eval]    MMLU-Pro +3.2, MT-Bench-v2 +0.41, RewardBench-2 +0.08
[card]    model-card.md generated under 2026 MOF
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-finetuning-pipeline.md` 描述可交付文件。一个单命令通过 SFT through DPO 通过量子通过服务 通过Eval,并发布 model card + 服务端点。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | Eval 三角洲对基底 | 目标任务(MMLU-Pro、MT-Bench-V2、具体任务)的衡量收益 |
| 20 | 管道可复制 | 以相同的种子重播一个命令结束 |
| 20 | 数据卫生 | 浸泡率, PII 擦拭覆盖率, 污染检查绿色 |
| 20 | 服务效率 | tokens/ 以 bs=1/8/32, EGOLE-3 接受率, 1美元 tokens |
| 15 | Model card + 安全评价 | 2026 财政部的完整性+ Llama 警卫4人通过率 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. Run SFT- 仅对Vs SFT+DPO 与 SFT+GRPO 汇报哪一种优先方法胜出,以及有多少。

2. Swap Llama 3.3 8B为Quen3 14B。 tokens 质量相当

3. 测量域数据与通用 ShareGPT 的 EAGLE-3 接受率。 报告三角洲及其对于延迟预算的意义 。

4. 输入1%的污染( 将 MMLU- Pro 解密到训练数据中) , 并重新运行 eval 。 观察 MMLU- Pro 精确度不切实际地跳跃 。 建立一个能捕捉到这个的污染检查 CI 门 。

5. Add LoRA SFT 以替代完全微调。测量质量差为低存储量 10x 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Axolotl | "SFT trainer" | Unified YAML- 驾驶教练 SFT, DPO,以及蒸馏 |
| TRL | "首选调音器" | 将脸书库 DPO, GRPO, PPO 在 LLMs |
| GRPO | "集体政策优化" | DeepSeek R1 的 RL 配方, 可核实的回报 |
| EAGLE-3 | "Speculative decoding draft" | 预测N的草稿 tokens ahead; vLLM 与目标模型进行核查 |
| MOF | "模式开放框架" | 2026年数据、代码、许可证的分级模型发布标准 |
| 污染检查 | 卫生间 | 以 MinHash 为基础检测测试集渗漏到训练中 |
| 录取率 | “EAGLE/MTP衡量标准” | 起草的分数 tokens 目标模式接受 |

<a id="further-reading"></a>

## 进一步阅读

- [Axolotl 文档](https://axolotl-ai-cloud.github.io/axolotl/) 参考文献 SFT / DPO trainer
- [TRL 文档](https://huggingface.co/docs/trl) — DPO 和 GRPO 参考执行情况
- [Unsloth](https://github.com/unslothai/unsloth) - 单GPU 迭代参考
- [DeepSeek R1 纸(arXiv:2501.12948)](https://arxiv.org/abs/2501.12948) — GRPO methodology
- [vLLM + EAGLE-3 文档](https://docs.vllm.ai) - 参考服务堆栈
- [SGLang SpecForge](https://github.com/sgl-project/SpecForge) 备选的投机解码培训
- [2026年示范开放框架](https://isocpp.org/) - 开放式释放分级标准
- [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) 运算员
