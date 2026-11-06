# 17-infrastructure-and-production：CoderPad 练习

本章 28 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [Managed LLM Platforms — Bedrock, Vertex AI, Azure OpenAI](01-managed-llm-platforms/coderpad/README.md) | 角色与工具选择 | Token 成本计费 |
| 02 | [Inference Platform Economics — Fireworks, Together, Baseten, Modal, Replicate, Anyscale](02-inference-platform-economics/coderpad/README.md) | Token 成本计费 | 并行加速上限 |
| 03 | [GPU Autoscaling on Kubernetes — Karpenter, KAI Scheduler, Gang Scheduling](03-gpu-autoscaling-kubernetes/coderpad/README.md) | 容量与副本数 | 优先级任务调度 |
| 04 | [Serving Engine Internals — PagedAttention, Continuous Batching, Chunked Prefill](04-vllm-serving-internals/coderpad/README.md) | KV Cache 内存预算 | 有界批处理装箱 |
| 05 | [EAGLE-3 Speculative Decoding in Production](05-eagle3-speculative-decoding/coderpad/README.md) | 推测解码前缀验收 | 分位数与 Goodput |
| 06 | [Prefix-Cache Serving — RadixAttention and KV Reuse](06-sglang-radixattention/coderpad/README.md) | LRU 缓存淘汰 | KV Cache 内存预算 |
| 07 | [Hardware-Specialized Inference Compilation — FP8 and NVFP4 on Blackwell](07-tensorrt-llm-blackwell/coderpad/README.md) | 对称整数化 | 模型参数与内存估算 |
| 08 | [Inference Metrics — TTFT, TPOT, ITL, Goodput, P99](08-inference-metrics-goodput/coderpad/README.md) | 分位数与 Goodput | 耗时聚合 |
| 09 | [Production Quantization — AWQ, GPTQ, GGUF K-quants, FP8, MXFP4/NVFP4](09-production-quantization/coderpad/README.md) | 对称整数化 | 回归误差与形状 |
| 10 | [Cold Start Mitigation for Serverless LLMs](10-cold-start-mitigation/coderpad/README.md) | 开发环境探针汇总 | 分位数与 Goodput |
| 11 | [Multi-Region LLM Serving and KV Cache Locality](11-multi-region-kv-locality/coderpad/README.md) | LRU 缓存淘汰 | TTL 缓存回放 |
| 12 | [Edge Inference — Apple Neural Engine, Qualcomm Hexagon, WebGPU/WebLLM, Jetson](12-edge-inference/coderpad/README.md) | 模型参数与内存估算 | 对称整数化 |
| 13 | [LLM Observability Stack Selection](13-llm-observability/coderpad/README.md) | 耗时聚合 | 结构化日志脱敏 |
| 14 | [Prompt Caching and Semantic Caching Economics](14-prompt-semantic-caching/coderpad/README.md) | Embedding 余弦相似度 | TTL 缓存回放 |
| 15 | [Batch APIs — the 50% Discount as Industry Standard](15-batch-apis/coderpad/README.md) | 有界批处理装箱 | 成本预算治理 |
| 16 | [Model Routing as a Cost-Reduction Primitive](16-model-routing/coderpad/README.md) | 角色与工具选择 | 分位数与 Goodput |
| 17 | [Disaggregated Prefill/Decode — NVIDIA Dynamo and llm-d](17-disaggregated-prefill-decode/coderpad/README.md) | 优先级任务调度 | KV Cache 内存预算 |
| 18 | [Production Serving Stack — KV Offloading and Cache-Aware Routing](18-vllm-production-stack-lmcache/coderpad/README.md) | LRU 缓存淘汰 | 有界批处理装箱 |
| 19 | [AI Gateways — LiteLLM, Portkey, Kong AI Gateway, Bifrost](19-ai-gateways/coderpad/README.md) | 独立权限与批准 | 滑动窗口限流 |
| 20 | [Shadow Traffic, Canary Rollout, and Progressive Deployment for LLMs](20-shadow-canary-progressive/coderpad/README.md) | 灰度发布判定 | 分位数与 Goodput |
| 21 | [A/B Testing LLM Features — GrowthBook, Statsig, and the Vibes Problem](21-ab-testing-llm-features/coderpad/README.md) | 分类混淆矩阵指标 | Expected Calibration Error |
| 22 | [Load Testing LLM APIs — Why k6 and Locust Lie](22-load-testing-llm-apis/coderpad/README.md) | 滑动窗口限流 | 分位数与 Goodput |
| 23 | [SRE for AI — Multi-Agent Incident Response, Runbooks, Predictive Detection](23-sre-for-ai/coderpad/README.md) | 证据分层 Gate | 分位数与 Goodput |
| 24 | [Chaos Engineering for LLM Production](24-chaos-engineering-llm/coderpad/README.md) | 有限指数退避 | 证据分层 Gate |
| 25 | [Security — Secrets, API Key Rotation, Audit Logs, Guardrails](25-security-secrets-audit/coderpad/README.md) | 结构化日志脱敏 | 独立权限与批准 |
| 26 | [Compliance — SOC 2, HIPAA, GDPR, PCI-DSS, EU AI Act, ISO 42001](26-compliance-frameworks/coderpad/README.md) | 声明与证据绑定 | 证据分层 Gate |
| 27 | [FinOps for LLMs — Unit Economics and Multi-Tenant Attribution](27-finops-llms/coderpad/README.md) | Token 成本计费 | 成本预算治理 |
| 28 | [Self-Hosted Serving Selection — Matching Engine to Hardware and Scale](28-self-hosted-serving-selection/coderpad/README.md) | 多目标候选筛选 | 模型参数与内存估算 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
