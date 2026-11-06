# 10-llms-from-scratch：CoderPad 练习

本章 24 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
核心 6 cases、加分 2 cases。题目是原课程中的一个编码切面，不要求运行完整训练、云服务或 GPU。
相同基础 kernel 会在相关课程复用；请在复盘中区分“未见题”与“重复练习”。
运行方法：进入任一项目的 `coderpad/`，阅读 README/PROMPT，再执行：

```bash
python3 run_tests.py --list
python3 run_tests.py --core
```

初始失败是 TODO 的正常起点；计时结束后才打开 solution 或使用 `--solution`。
面试官材料、评分与复盘模板均在每套目录；计时器自行设置。

| 课号 | 主题与题目入口 | 核心 | 加分 |
| --- | --- | --- | --- |
| 01 | [Tokenizers: BPE, WordPiece, SentencePiece](01-tokenizers/coderpad/README.md) | 文本归一化与分词 | BPE 相邻 Pair 合并 |
| 02 | [Building a Tokenizer from Scratch](02-building-a-tokenizer/coderpad/README.md) | BPE 相邻 Pair 合并 | N-gram 计数 |
| 03 | [Data Pipelines for Pre-Training](03-data-pipelines/coderpad/README.md) | 重叠窗口切块 | 可复现数据划分 |
| 04 | [Pre-Training a Mini GPT (124M Parameters)](04-pre-training-mini-gpt/coderpad/README.md) | 因果与窗口 Attention Mask | 分类交叉熵 |
| 05 | [Scaling: Distributed Training, FSDP, DeepSpeed](05-scaling-distributed/coderpad/README.md) | 均衡参数分片 | 集体归约 |
| 06 | [Instruction Tuning (SFT)](06-instruction-tuning-sft/coderpad/README.md) | 受限解码分布 | 分类交叉熵 |
| 07 | [RLHF: Reward Model + PPO](07-rlhf/coderpad/README.md) | Actor-Critic Advantage | 折扣回报 |
| 08 | [DPO: Direct Preference Optimization](08-dpo/coderpad/README.md) | 偏好对的稳定 Loss | 稳定 Sigmoid |
| 09 | [Constitutional AI and Self-Improvement](09-constitutional-ai-self-improvement/coderpad/README.md) | 分类信号合并 | 证据分层 Gate |
| 10 | [Evaluation: Benchmarks, Evals, LM Harness](10-evaluation/coderpad/README.md) | Perplexity 与长度 | Expected Calibration Error |
| 11 | [Quantization: Making Models Fit](11-quantization/coderpad/README.md) | 对称整数化 | 回归误差与形状 |
| 12 | [Inference Optimization](12-inference-optimization/coderpad/README.md) | KV Cache 内存预算 | 分位数与 Goodput |
| 13 | [Building a Complete LLM Pipeline](13-building-complete-llm-pipeline/coderpad/README.md) | 依赖计划拓扑排序 | 内容指纹与漂移 |
| 14 | [Open Models: Architecture Walkthroughs](14-open-models-architecture-walkthroughs/coderpad/README.md) | 模型参数与内存估算 | KV Cache 内存预算 |
| 15 | [Speculative Decoding and EAGLE-3](15-speculative-decoding-eagle3/coderpad/README.md) | 推测解码前缀验收 | 分位数与 Goodput |
| 16 | [Differential Attention (V2)](16-differential-attention-v2/coderpad/README.md) | 单头注意力 | LayerNorm 前向 |
| 17 | [Native Sparse Attention (DeepSeek NSA)](17-native-sparse-attention/coderpad/README.md) | 因果与窗口 Attention Mask | 稀疏路由 Top-K |
| 18 | [Multi-Token Prediction (MTP)](18-multi-token-prediction/coderpad/README.md) | 时间序列滞后特征 | 因果与窗口 Attention Mask |
| 19 | [DualPipe Parallelism](19-dualpipe-parallelism/coderpad/README.md) | 流水线气泡估算 | 均衡参数分片 |
| 20 | [DeepSeek-V3 Architecture Walkthrough](20-deepseek-v3-walkthrough/coderpad/README.md) | 稀疏路由 Top-K | 模型参数与内存估算 |
| 21 | [Jamba — Hybrid SSM-Transformer](21-jamba-hybrid-ssm-transformer/coderpad/README.md) | 马尔可夫状态分布 | 单头注意力 |
| 22 | [Async and Hogwild! Inference](22-async-hogwild-inference/coderpad/README.md) | 幂等请求账本 | 滑动窗口限流 |
| 25 | [Speculative Decoding and EAGLE](25-speculative-decoding/coderpad/README.md) | 推测解码前缀验收 | 因果与窗口 Attention Mask |
| 34 | [Gradient Checkpointing and Activation Recomputation](34-gradient-checkpointing/coderpad/README.md) | 模型参数与内存估算 | 并行加速上限 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
