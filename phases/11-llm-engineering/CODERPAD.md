# 11-llm-engineering：CoderPad 练习

本章 17 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [Prompt Engineering: Techniques & Patterns](01-prompt-engineering/coderpad/README.md) | 上下文预算装箱 | 配置合同校验 |
| 02 | [Few-Shot, Chain-of-Thought, Tree-of-Thought](02-few-shot-cot/coderpad/README.md) | 上下文预算装箱 | 问答 Token F1 |
| 03 | [Structured Outputs: JSON, Schema Validation, Constrained Decoding](03-structured-outputs/coderpad/README.md) | 配置合同校验 | 工具参数校验 |
| 04 | [Embeddings & Vector Representations](04-embeddings/coderpad/README.md) | Embedding 余弦相似度 | 检索指标 |
| 05 | [Context Engineering: Windows, Budgets, Memory, and Retrieval](05-context-engineering/coderpad/README.md) | 上下文预算装箱 | 有界记忆保留 |
| 06 | [RAG (Retrieval-Augmented Generation)](06-rag/coderpad/README.md) | 重叠窗口切块 | 检索指标 |
| 07 | [Advanced RAG (Chunking, Reranking, Hybrid Search)](07-advanced-rag/coderpad/README.md) | 倒数排名融合 | 检索指标 |
| 08 | [Fine-Tuning with LoRA & QLoRA](08-fine-tuning-lora/coderpad/README.md) | LoRA 增量与参数量 | 模型参数与内存估算 |
| 09 | [Function Calling & Tool Use](09-function-calling/coderpad/README.md) | 工具参数校验 | JSON-RPC 请求包 |
| 10 | [Evaluation & Testing LLM Applications](10-evaluation/coderpad/README.md) | 分类混淆矩阵指标 | Expected Calibration Error |
| 11 | [Caching, Rate Limiting & Cost Optimization](11-caching-cost/coderpad/README.md) | TTL 缓存回放 | Token 成本计费 |
| 12 | [Guardrails, Safety & Content Filtering](12-guardrails/coderpad/README.md) | 分类信号合并 | 独立权限与批准 |
| 13 | [Building a Production LLM Application](13-production-app/coderpad/README.md) | 合法状态转换 | 成本预算治理 |
| 14 | [Model Context Protocol (MCP)](14-model-context-protocol/coderpad/README.md) | JSON-RPC 请求包 | 配置合同校验 |
| 15 | [Prompt Caching and Context Caching](15-prompt-caching/coderpad/README.md) | LRU 缓存淘汰 | TTL 缓存回放 |
| 16 | [Agent State Machines — Graphs, Nodes, Checkpoints](16-langgraph-state-machines/coderpad/README.md) | 合法状态转换 | 依赖计划拓扑排序 |
| 17 | [Agent Framework Tradeoffs — Graph, Role, and Actor Orchestration](17-agent-framework-tradeoffs/coderpad/README.md) | 角色与工具选择 | 证据分层 Gate |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
