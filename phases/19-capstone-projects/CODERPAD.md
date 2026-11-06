# 19-capstone-projects：CoderPad 练习

本章 85 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [Capstone 01 — Terminal-Native Coding Agent](01-terminal-native-coding-agent/coderpad/README.md) | 精确命令策略 | 词法路径包含边界 |
| 02 | [Capstone 02 — RAG over Codebase (Cross-Repo Semantic Search)](02-rag-over-codebase/coderpad/README.md) | 重叠窗口切块 | 检索指标 |
| 03 | [Capstone 03 — Real-Time Voice Assistant (ASR to LLM to TTS)](03-realtime-voice-assistant/coderpad/README.md) | 能量 VAD 边界 | 合法状态转换 |
| 04 | [Capstone 04 — Multimodal Document QA (Vision-First PDF, Tables, Charts)](04-multimodal-document-qa/coderpad/README.md) | 图像 Patch 切分 | 问答 Token F1 |
| 05 | [Capstone 05 — Autonomous Research Agent (AI-Scientist Class)](05-autonomous-research-agent/coderpad/README.md) | 依赖计划拓扑排序 | 声明与证据绑定 |
| 06 | [Capstone 06 — DevOps Troubleshooting Agent for Kubernetes](06-devops-troubleshooting-agent/coderpad/README.md) | 开发环境探针汇总 | 依赖计划拓扑排序 |
| 07 | [Capstone 07 — End-to-End Fine-Tuning Pipeline (Data to SFT to DPO to Serve)](07-end-to-end-fine-tuning-pipeline/coderpad/README.md) | Warmup 与余弦学习率 | LoRA 增量与参数量 |
| 08 | [Capstone 08 — Production RAG Chatbot for a Regulated Vertical](08-production-rag-chatbot/coderpad/README.md) | 倒数排名融合 | 上下文预算装箱 |
| 09 | [Capstone 09 — Code Migration Agent (Repo-Level Language / Runtime Upgrade)](09-code-migration-agent/coderpad/README.md) | Git 变更分类 | 内容指纹与漂移 |
| 10 | [Capstone 10 — Multi-Agent Software Engineering Team](10-multi-agent-software-team/coderpad/README.md) | 依赖计划拓扑排序 | 可验证任务交接 |
| 11 | [Capstone 11 — LLM Observability & Eval Dashboard](11-llm-observability-dashboard/coderpad/README.md) | 耗时聚合 | 分位数与 Goodput |
| 12 | [Capstone 12 — Video Understanding Pipeline (Scene, QA, Search)](12-video-understanding-pipeline/coderpad/README.md) | 视频均匀采样 | 上下文预算装箱 |
| 13 | [Capstone 13: Stateless MCP Server with Registry and Governance](13-mcp-server-with-registry/coderpad/README.md) | JSON-RPC 请求包 | 内容指纹与漂移 |
| 14 | [Capstone 14 — Speculative-Decoding Inference Server](14-speculative-decoding-server/coderpad/README.md) | 推测解码前缀验收 | KV Cache 内存预算 |
| 15 | [Capstone 15 — Constitutional Safety Harness + Red-Team Range](15-constitutional-safety-harness/coderpad/README.md) | 分类信号合并 | 证据分层 Gate |
| 16 | [Capstone 16 — GitHub Issue-to-PR Autonomous Agent](16-github-issue-to-pr-agent/coderpad/README.md) | Git 变更分类 | 证据分层 Gate |
| 17 | [Capstone 17 — Personal AI Tutor (Adaptive, Multimodal, with Memory)](17-personal-ai-tutor/coderpad/README.md) | 上下文预算装箱 | 分类混淆矩阵指标 |
| 20 | [Agent Harness Loop Contract](20-agent-harness-loop-contract/coderpad/README.md) | 合法状态转换 | 成本预算治理 |
| 21 | [Tool Registry with Schema Validation](21-tool-registry-schema-validation/coderpad/README.md) | 工具参数校验 | 配置合同校验 |
| 22 | [JSON-RPC 2.0 Over Newline-Delimited Stdio](22-jsonrpc-stdio-transport/coderpad/README.md) | JSON-RPC 请求包 | 幂等请求账本 |
| 23 | [Function Call Dispatcher](23-function-call-dispatcher/coderpad/README.md) | 角色与工具选择 | 工具参数校验 |
| 24 | [Plan-Execute Control Flow](24-plan-execute-control-flow/coderpad/README.md) | 依赖计划拓扑排序 | 合法状态转换 |
| 25 | [Capstone Lesson 25: Verification Gates and the Observation Budget](25-verification-gates-observation-budget/coderpad/README.md) | 证据分层 Gate | 成本预算治理 |
| 26 | [Capstone Lesson 26: Sandbox Runner with Denylist and Path Jail](26-sandbox-runner-denylist/coderpad/README.md) | 精确命令策略 | 独立权限与批准 |
| 27 | [Capstone Lesson 27: Eval Harness with Fixture Tasks](27-eval-harness-fixture-tasks/coderpad/README.md) | 分类混淆矩阵指标 | 配置合同校验 |
| 28 | [Capstone Lesson 28: Observability with OTel GenAI Spans and Prometheus Metrics](28-observability-otel-traces/coderpad/README.md) | 耗时聚合 | 结构化日志脱敏 |
| 29 | [Capstone Lesson 29: End-to-End Coding Agent on the Harness](29-end-to-end-coding-task-demo/coderpad/README.md) | 依赖计划拓扑排序 | 证据分层 Gate |
| 30 | [BPE Tokenizer From Scratch](30-bpe-tokenizer-from-scratch/coderpad/README.md) | BPE 相邻 Pair 合并 | N-gram 计数 |
| 31 | [Tokenized Dataset with Sliding Window](31-tokenized-dataset-sliding-window/coderpad/README.md) | 重叠窗口切块 | 因果与窗口 Attention Mask |
| 32 | [Token and Positional Embeddings](32-token-positional-embeddings/coderpad/README.md) | Sinusoidal 位置编码 | 线性层前向 |
| 33 | [Multi-Head Self-Attention](33-multihead-self-attention/coderpad/README.md) | 单头注意力 | 矩阵乘法 |
| 34 | [Transformer Block from Scratch](34-transformer-block/coderpad/README.md) | LayerNorm 前向 | 激活函数前向 |
| 35 | [GPT Model Assembly](35-gpt-model-assembly/coderpad/README.md) | 模型参数与内存估算 | 因果与窗口 Attention Mask |
| 36 | [Training Loop and Evaluation](36-training-loop-eval/coderpad/README.md) | 分类交叉熵 | 梯度下降一步更新 |
| 37 | [Loading Pretrained Weights](37-loading-pretrained-weights/coderpad/README.md) | 内容指纹与漂移 | 模型参数与内存估算 |
| 38 | [Capstone Lesson 38: Classifier Fine-Tuning by Head Swap](38-classifier-finetuning/coderpad/README.md) | 线性层前向 | 分类混淆矩阵指标 |
| 39 | [Capstone Lesson 39: Instruction Tuning by Supervised Fine-Tuning](39-instruction-tuning-sft/coderpad/README.md) | 受限解码分布 | 分类交叉熵 |
| 40 | [Capstone Lesson 40: Direct Preference Optimization from Scratch](40-dpo-from-scratch/coderpad/README.md) | 偏好对的稳定 Loss | 稳定 Sigmoid |
| 41 | [Capstone Lesson 41: Full Evaluation Pipeline](41-eval-pipeline/coderpad/README.md) | 分类混淆矩阵指标 | Expected Calibration Error |
| 42 | [Large Corpus Downloader](42-large-corpus-downloader/coderpad/README.md) | 内容指纹与漂移 | 有限指数退避 |
| 43 | [HDF5 Tokenized Corpus](43-hdf5-tokenized-corpus/coderpad/README.md) | 重叠窗口切块 | 内容指纹与漂移 |
| 44 | [Cosine LR with Linear Warmup](44-cosine-lr-warmup/coderpad/README.md) | Warmup 与余弦学习率 | 梯度范数裁剪 |
| 45 | [Gradient Clipping and Mixed Precision](45-gradient-clipping-amp/coderpad/README.md) | 梯度范数裁剪 | 梯度下降一步更新 |
| 46 | [Gradient Accumulation](46-gradient-accumulation/coderpad/README.md) | 集体归约 | 梯度下降一步更新 |
| 47 | [Checkpoint Save and Resume](47-checkpoint-save-resume/coderpad/README.md) | 内容指纹与漂移 | 合法状态转换 |
| 48 | [Distributed Data Parallel and FSDP from Scratch](48-distributed-fsdp-ddp/coderpad/README.md) | 均衡参数分片 | 集体归约 |
| 49 | [Language Model Evaluation Harness](49-lm-eval-harness/coderpad/README.md) | Perplexity 与长度 | 检索指标 |
| 50 | [Hypothesis Generator](50-hypothesis-generator/coderpad/README.md) | 上下文预算装箱 | 多目标候选筛选 |
| 51 | [Literature Retrieval](51-literature-retrieval/coderpad/README.md) | 倒数排名融合 | 声明与证据绑定 |
| 52 | [Experiment Runner](52-experiment-runner/coderpad/README.md) | 优先级任务调度 | 成本预算治理 |
| 53 | [Result Evaluator](53-result-evaluator/coderpad/README.md) | 均值与总体方差 | Expected Calibration Error |
| 54 | [Paper Writer](54-paper-writer/coderpad/README.md) | 声明与证据绑定 | 配置合同校验 |
| 55 | [Critic Loop](55-critic-loop/coderpad/README.md) | 评估锚点漂移 | 证据分层 Gate |
| 56 | [Iteration Scheduler](56-iteration-scheduler/coderpad/README.md) | 探索与利用调度 | 成本预算治理 |
| 57 | [End-to-End Research Demo](57-end-to-end-research-demo/coderpad/README.md) | 依赖计划拓扑排序 | 声明与证据绑定 |
| 58 | [Vision Encoder Patches](58-vision-encoder-patches/coderpad/README.md) | 图像 Patch 切分 | Sinusoidal 位置编码 |
| 59 | [Vision Transformer Encoder](59-vit-transformer/coderpad/README.md) | 单头注意力 | 模型参数与内存估算 |
| 60 | [Projection Layer for Modality Alignment](60-projection-layer-modality-align/coderpad/README.md) | 线性层前向 | Embedding 余弦相似度 |
| 61 | [Cross-Attention Fusion](61-cross-attention-fusion/coderpad/README.md) | 单头注意力 | 因果与窗口 Attention Mask |
| 62 | [Vision-Language Pretraining](62-vision-language-pretraining/coderpad/README.md) | 分类交叉熵 | Embedding 余弦相似度 |
| 63 | [Multimodal Evaluation](63-multimodal-eval/coderpad/README.md) | 检索指标 | 问答 Token F1 |
| 64 | [Chunking Strategies, Compared](64-chunking-strategies-advanced/coderpad/README.md) | 重叠窗口切块 | 上下文预算装箱 |
| 65 | [Hybrid Retrieval with BM25 and Dense Embeddings](65-hybrid-retrieval-bm25-dense/coderpad/README.md) | 倒数排名融合 | Embedding 余弦相似度 |
| 66 | [Cross-Encoder Reranker](66-reranker-cross-encoder/coderpad/README.md) | 稀疏路由 Top-K | 检索指标 |
| 67 | [Query Rewriting: HyDE, Multi-Query, and Decomposition](67-query-rewriting-hyde/coderpad/README.md) | 词袋向量 | 倒数排名融合 |
| 68 | [RAG Evaluation: Precision, Recall, MRR, nDCG, Faithfulness, Answer Relevance](68-rag-eval-precision-recall/coderpad/README.md) | 检索指标 | 声明与证据绑定 |
| 69 | [End-to-End RAG System](69-end-to-end-rag-system/coderpad/README.md) | 依赖计划拓扑排序 | 检索指标 |
| 70 | [Task Spec Format](70-task-spec-format/coderpad/README.md) | 配置合同校验 | 工具参数校验 |
| 71 | [Classical Metrics](71-classical-metrics/coderpad/README.md) | 问答 Token F1 | N-gram 计数 |
| 72 | [Code Exec Metric](72-code-exec-metric/coderpad/README.md) | 独立权限与批准 | 精确命令策略 |
| 73 | [Perplexity and Calibration](73-perplexity-calibration/coderpad/README.md) | Perplexity 与长度 | Expected Calibration Error |
| 74 | [Leaderboard Aggregation](74-leaderboard-aggregation/coderpad/README.md) | 均值与总体方差 | 分类混淆矩阵指标 |
| 75 | [End-to-End Eval Runner](75-end-to-end-eval-runner/coderpad/README.md) | 证据分层 Gate | 声明与证据绑定 |
| 76 | [Collective Ops From Scratch](76-collective-ops-from-scratch/coderpad/README.md) | 集体归约 | 均衡参数分片 |
| 77 | [Data Parallel DDP From Scratch](77-data-parallel-ddp/coderpad/README.md) | 集体归约 | 数值梯度 |
| 78 | [ZeRO Optimizer State Sharding](78-zero-parameter-sharding/coderpad/README.md) | 均衡参数分片 | 模型参数与内存估算 |
| 79 | [Pipeline Parallel and Bubble Analysis](79-pipeline-parallel/coderpad/README.md) | 流水线气泡估算 | 优先级任务调度 |
| 80 | [Sharded Checkpoint and Atomic Resume](80-checkpoint-sharded-resume/coderpad/README.md) | 内容指纹与漂移 | 均衡参数分片 |
| 81 | [End-to-End Distributed Training](81-end-to-end-distributed-train/coderpad/README.md) | 均衡参数分片 | 流水线气泡估算 |
| 82 | [Capstone 82 — Jailbreak Taxonomy](82-jailbreak-taxonomy/coderpad/README.md) | 风险登记与排序 | 配置合同校验 |
| 83 | [Capstone 83 — Prompt Injection Detector](83-prompt-injection-detector/coderpad/README.md) | 文本归一化与分词 | 声明与证据绑定 |
| 84 | [Capstone 84 — Refusal Evaluation](84-refusal-evaluation/coderpad/README.md) | 分类混淆矩阵指标 | 分类信号合并 |
| 85 | [Capstone 85 — Content Classifier Integration](85-content-classifier-integration/coderpad/README.md) | 分类信号合并 | 风险登记与排序 |
| 86 | [Capstone 86 — Constitutional Rules Engine](86-constitutional-rules-engine/coderpad/README.md) | 配置合同校验 | 分类信号合并 |
| 87 | [Capstone 87 — End-to-End Safety Gate](87-end-to-end-safety-gate/coderpad/README.md) | 证据分层 Gate | 独立权限与批准 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
