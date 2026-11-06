# Phase 11 LLM 应用工程 — LLM Engineering

[返回总目录](README.md) · [前一章](10-从零构建大语言模型.md) · [后一章](12-多模态%20AI.md)

本章共 **17 节**。

**掌握目标**：能把模型调用组织成有上下文、检索、工具、评估与成本控制的应用。

**章节衔接**：承接模型原理，也可以在具备 Python 和 API 基础后作为应用入口；进一步通向 Phase 13、14。

**为什么有用**：处于基础模型之上的应用系统层。提示、上下文、检索、工具和评估共同决定用户可见行为，也是把模型能力转成稳定功能的主要工作面。

**章节练习**：做一个带依据的文档问答原型，加入结构校验、失败样例、费用记录与离线评估。

小节中的“衔接”说明知识如何复用，不代表必须按编号完成所有分支；原课的具体前置要求见教材。建议练习可配合原课代码完成，CoderPad 的实际题目范围以各自 `PROMPT.md` 为准。

## 模型输入输出与表示

### 11.01 [Prompt Engineering](../11-llm-engineering/01-prompt-engineering/docs/en.md) — Prompt Engineering: Techniques & Patterns

- **掌握**：明确角色、上下文、约束和输出格式。
- **衔接**：是后续检索、工具使用和评估的接口基础。
- **为什么有用**：位于用户需求到模型输入的表达层。明确上下文、约束与格式能减少歧义，并让后续结果有可比较的验收标准。
- **建议练习**：把模糊需求改成可评分提示，比较固定样本结果。

入口：[中文教材](../11-llm-engineering/01-prompt-engineering/docs/zh.md) · [原课代码](../11-llm-engineering/01-prompt-engineering/code/) · [CoderPad](../11-llm-engineering/01-prompt-engineering/coderpad/README.md) · [分关练习](../11-llm-engineering/01-prompt-engineering/exam/README.md) · [课后测验](../11-llm-engineering/01-prompt-engineering/quiz/quiz.md)

### 11.02 [Few-Shot 与推理组织](../11-llm-engineering/02-few-shot-cot/docs/en.md) — Few-Shot, Chain-of-Thought, Tree-of-Thought

- **掌握**：理解示例选择、多步分解和候选搜索。
- **衔接**：在基础提示之上改善任务说明与求解流程。
- **为什么有用**：位于输入组织与求解流程设计层。示例和任务分解能改变模型使用已有能力的方式，需要通过固定样本判断是否值得增加成本。
- **建议练习**：固定测试集比较零样本和少样本，排除示例泄漏。

入口：[中文教材](../11-llm-engineering/02-few-shot-cot/docs/zh.md) · [原课代码](../11-llm-engineering/02-few-shot-cot/code/) · [CoderPad](../11-llm-engineering/02-few-shot-cot/coderpad/README.md) · [分关练习](../11-llm-engineering/02-few-shot-cot/exam/README.md) · [课后测验](../11-llm-engineering/02-few-shot-cot/quiz/quiz.md)

### 11.03 [结构化输出](../11-llm-engineering/03-structured-outputs/docs/en.md) — Structured Outputs: JSON, Schema Validation, Constrained Decoding

- **掌握**：区分 JSON 语法、Schema 约束和业务校验。
- **衔接**：让模型输出成为后续程序可消费的数据。
- **为什么有用**：位于模型生成到业务程序的边界层。稳定结构让输出可解析，但字段约束与业务校验仍决定数据是否真的可用。
- **建议练习**：测试缺字段、错类型、非法枚举及校验后的重试。

入口：[中文教材](../11-llm-engineering/03-structured-outputs/docs/zh.md) · [原课代码](../11-llm-engineering/03-structured-outputs/code/) · [CoderPad](../11-llm-engineering/03-structured-outputs/coderpad/README.md) · [分关练习](../11-llm-engineering/03-structured-outputs/exam/README.md) · [课后测验](../11-llm-engineering/03-structured-outputs/quiz/quiz.md)

### 11.04 [Embedding 与向量表示](../11-llm-engineering/04-embeddings/docs/en.md) — Embeddings & Vector Representations

- **掌握**：掌握文本向量、归一化和相似度。
- **衔接**：为 RAG 语义检索和语义缓存提供表示。
- **为什么有用**：位于语义表示与相似度服务层。Embedding 将文本转换成可比较的向量，是检索、聚类和语义缓存的共同基础。
- **建议练习**：用相近与无关短句检查相似度排序。

入口：[中文教材](../11-llm-engineering/04-embeddings/docs/zh.md) · [原课代码](../11-llm-engineering/04-embeddings/code/) · [CoderPad](../11-llm-engineering/04-embeddings/coderpad/README.md) · [分关练习](../11-llm-engineering/04-embeddings/exam/README.md) · [课后测验](../11-llm-engineering/04-embeddings/quiz/quiz.md)

## 上下文、检索与适配

### 11.05 [Context Engineering](../11-llm-engineering/05-context-engineering/docs/en.md) — Context Engineering: Windows, Budgets, Memory, and Retrieval

- **掌握**：分配系统提示、工具、历史、证据和输出预算。
- **衔接**：把单次提示扩展成受窗口约束的应用上下文。
- **为什么有用**：位于模型可见信息的资源分配层。窗口有限时，保留什么会直接影响回答与行动，系统提示、历史和证据需要一起预算。
- **建议练习**：在预算紧张时选择保留内容，确保问题与关键证据完整。

入口：[中文教材](../11-llm-engineering/05-context-engineering/docs/zh.md) · [原课代码](../11-llm-engineering/05-context-engineering/code/) · [CoderPad](../11-llm-engineering/05-context-engineering/coderpad/README.md) · [分关练习](../11-llm-engineering/05-context-engineering/exam/README.md) · [课后测验](../11-llm-engineering/05-context-engineering/quiz/quiz.md)

### 11.06 [基础 RAG](../11-llm-engineering/06-rag/docs/en.md) — RAG (Retrieval-Augmented Generation)

- **掌握**：掌握加载、切分、向量化、检索与带依据生成。
- **衔接**：组合 embedding 和上下文管理，减少无依据回答。
- **为什么有用**：位于外部知识到模型回答的桥接层。RAG 让答案能够引用可更新文档，错误也可拆到召回、上下文与生成各环节。
- **建议练习**：为可回答和无答案问题分别检查召回与引用。

入口：[中文教材](../11-llm-engineering/06-rag/docs/zh.md) · [原课代码](../11-llm-engineering/06-rag/code/) · [CoderPad](../11-llm-engineering/06-rag/coderpad/README.md) · [分关练习](../11-llm-engineering/06-rag/exam/README.md) · [课后测验](../11-llm-engineering/06-rag/quiz/quiz.md)

### 11.07 [高级 RAG](../11-llm-engineering/07-advanced-rag/docs/en.md) — Advanced RAG (Chunking, Reranking, Hybrid Search)

- **掌握**：理解混合检索、重排、语义和父子切块。
- **衔接**：针对基础 RAG 的具体召回问题逐项优化。
- **为什么有用**：位于检索系统的针对性优化层。混合召回和重排解决不同失败类型，先诊断问题再改组件，才能避免复杂度上升却没有收益。
- **建议练习**：固定评估问题，只改变一个检索环节做对比。

入口：[中文教材](../11-llm-engineering/07-advanced-rag/docs/zh.md) · [原课代码](../11-llm-engineering/07-advanced-rag/code/) · [CoderPad](../11-llm-engineering/07-advanced-rag/coderpad/README.md) · [分关练习](../11-llm-engineering/07-advanced-rag/exam/README.md) · [课后测验](../11-llm-engineering/07-advanced-rag/quiz/quiz.md)

### 11.08 [LoRA 与 QLoRA 微调](../11-llm-engineering/08-fine-tuning-lora/docs/en.md) — Fine-Tuning with LoRA & QLoRA

- **掌握**：理解低秩适配、冻结权重和量化训练。
- **衔接**：为提示或检索无法解决的适应任务提供训练路线。
- **为什么有用**：位于预训练权重的高效适配层。低秩参数让任务训练集中在较小修改上，适合比较模型行为适应与外部知识检索的不同作用。
- **建议练习**：计算可训练参数量，比较微调与 RAG 所需数据。

入口：[中文教材](../11-llm-engineering/08-fine-tuning-lora/docs/zh.md) · [原课代码](../11-llm-engineering/08-fine-tuning-lora/code/) · [CoderPad](../11-llm-engineering/08-fine-tuning-lora/coderpad/README.md) · [分关练习](../11-llm-engineering/08-fine-tuning-lora/exam/README.md) · [课后测验](../11-llm-engineering/08-fine-tuning-lora/quiz/quiz.md)

## 工具、质量与服务整合

### 11.09 [Function Calling](../11-llm-engineering/09-function-calling/docs/en.md) — Function Calling & Tool Use

- **掌握**：掌握声明、模型提议、主程序执行和结果回传。
- **衔接**：让应用使用外部能力，Phase 13 会深入接口细节。
- **为什么有用**：位于模型决策与外部执行之间的接口层。工具循环让模型使用计算、查询和操作能力，主程序负责校验、执行与失败处理。
- **建议练习**：模拟未知工具、非法参数和执行失败，检查循环行为。

入口：[中文教材](../11-llm-engineering/09-function-calling/docs/zh.md) · [原课代码](../11-llm-engineering/09-function-calling/code/) · [CoderPad](../11-llm-engineering/09-function-calling/coderpad/README.md) · [分关练习](../11-llm-engineering/09-function-calling/exam/README.md) · [课后测验](../11-llm-engineering/09-function-calling/quiz/quiz.md)

### 11.10 [应用评估与测试](../11-llm-engineering/10-evaluation/docs/en.md) — Evaluation & Testing LLM Applications

- **掌握**：建立任务样本、评分规则、边界案例与回归集。
- **衔接**：为提示、检索、微调和工具方案提供共同验收。
- **为什么有用**：位于应用质量与迭代决策层。固定任务集把主观印象转成可复查结果，能判断提示、模型或检索修改是否引入回归。
- **建议练习**：保存逐例输入输出，区分确定性评分和 judge 评分。

入口：[中文教材](../11-llm-engineering/10-evaluation/docs/zh.md) · [原课代码](../11-llm-engineering/10-evaluation/code/) · [CoderPad](../11-llm-engineering/10-evaluation/coderpad/README.md) · [分关练习](../11-llm-engineering/10-evaluation/exam/README.md) · [课后测验](../11-llm-engineering/10-evaluation/quiz/quiz.md)

### 11.11 [缓存、限流与成本](../11-llm-engineering/11-caching-cost/docs/en.md) — Caching, Rate Limiting & Cost Optimization

- **掌握**：理解语义缓存、请求预算、token 成本和速率限制。
- **衔接**：在效果之外管理服务资源和重复请求。
- **为什么有用**：位于应用资源与请求治理层。缓存、限流和预算把单次调用扩展成可持续服务，同时需要保持结果正确和计费可追踪。
- **建议练习**：设计缓存失效与限流样例，估算单请求成本。

入口：[中文教材](../11-llm-engineering/11-caching-cost/docs/zh.md) · [原课代码](../11-llm-engineering/11-caching-cost/code/) · [CoderPad](../11-llm-engineering/11-caching-cost/coderpad/README.md) · [分关练习](../11-llm-engineering/11-caching-cost/exam/README.md) · [课后测验](../11-llm-engineering/11-caching-cost/quiz/quiz.md)

### 11.12 [Guardrails 与内容检查](../11-llm-engineering/12-guardrails/docs/en.md) — Guardrails, Safety & Content Filtering

- **掌握**：区分输入、输出及执行前的检查职责。
- **衔接**：为模型应用补充隐私、越权和内容边界。
- **为什么有用**：位于应用输入、输出和行动的检查层。不同风险需要在不同位置处理，测试误拒绝与漏检才能判断控制是否适合任务。
- **建议练习**：构造正常与攻击样例，检查误拒绝和漏检。

入口：[中文教材](../11-llm-engineering/12-guardrails/docs/zh.md) · [原课代码](../11-llm-engineering/12-guardrails/code/) · [CoderPad](../11-llm-engineering/12-guardrails/coderpad/README.md) · [分关练习](../11-llm-engineering/12-guardrails/exam/README.md) · [课后测验](../11-llm-engineering/12-guardrails/quiz/quiz.md)

### 11.13 [完整 LLM 应用](../11-llm-engineering/13-production-app/docs/en.md) — Building a Production LLM Application

- **掌握**：整合提示、RAG、工具、缓存、流式响应与错误处理。
- **衔接**：汇总本章组件，进入协议和 Agent 系统。
- **为什么有用**：位于模型应用的端到端交付层。组件各自可运行还需要稳定接口、超时和响应流程，集成验证决定系统是否真正可用。
- **建议练习**：画出请求链路，逐段设计超时与可观察输出。

入口：[中文教材](../11-llm-engineering/13-production-app/docs/zh.md) · [原课代码](../11-llm-engineering/13-production-app/code/) · [CoderPad](../11-llm-engineering/13-production-app/coderpad/README.md) · [分关练习](../11-llm-engineering/13-production-app/exam/README.md) · [课后测验](../11-llm-engineering/13-production-app/quiz/quiz.md)

## 协议、缓存与 Agent 执行结构

### 11.14 [MCP 入门](../11-llm-engineering/14-model-context-protocol/docs/en.md) — Model Context Protocol (MCP)

- **掌握**：区分 host、client、server、transport 和能力发现。
- **衔接**：把自定义工具接口连接到 Phase 13 协议体系。
- **为什么有用**：位于应用宿主与工具服务的互操作层。MCP 将能力发现与调用合同显式化，让外部服务能通过协议接入模型应用。
- **建议练习**：画出主程序到服务端的请求流，标明各方职责。

入口：[中文教材](../11-llm-engineering/14-model-context-protocol/docs/zh.md) · [原课代码](../11-llm-engineering/14-model-context-protocol/code/) · [CoderPad](../11-llm-engineering/14-model-context-protocol/coderpad/README.md) · [课后测验](../11-llm-engineering/14-model-context-protocol/quiz/quiz.md)

### 11.15 [Prompt 与 Context 缓存](../11-llm-engineering/15-prompt-caching/docs/en.md) — Prompt Caching and Context Caching

- **掌握**：区分供应商前缀缓存、语义缓存及命中条件。
- **衔接**：深化第 11 节，分析重复上下文的处理成本。
- **为什么有用**：位于重复上下文的推理成本管理层。前缀复用和直接返回缓存答案节省的是不同工作，命中条件与失效规则决定可靠收益。
- **建议练习**：比较固定与变化前缀，明确缓存粒度和失效条件。

入口：[中文教材](../11-llm-engineering/15-prompt-caching/docs/zh.md) · [原课代码](../11-llm-engineering/15-prompt-caching/code/) · [CoderPad](../11-llm-engineering/15-prompt-caching/coderpad/README.md) · [课后测验](../11-llm-engineering/15-prompt-caching/quiz/quiz.md)

### 11.16 [Agent 状态机](../11-llm-engineering/16-langgraph-state-machines/docs/en.md) — Agent State Machines — Graphs, Nodes, Checkpoints

- **掌握**：理解节点、条件边、状态和 checkpoint。
- **衔接**：在工具循环上加入可恢复的执行结构。
- **为什么有用**：位于 Agent 的显式执行与恢复层。状态图把循环中的分支和进度变成可保存对象，便于中断、重试和人工接续。
- **建议练习**：画出一次失败重试的状态图，标出持久化位置。

入口：[中文教材](../11-llm-engineering/16-langgraph-state-machines/docs/zh.md) · [原课代码](../11-llm-engineering/16-langgraph-state-machines/code/) · [CoderPad](../11-llm-engineering/16-langgraph-state-machines/coderpad/README.md) · [课后测验](../11-llm-engineering/16-langgraph-state-machines/quiz/quiz.md)

### 11.17 [Agent 框架取舍](../11-llm-engineering/17-agent-framework-tradeoffs/docs/en.md) — Agent Framework Tradeoffs — Graph, Role, and Actor Orchestration

- **掌握**：比较图、角色和 actor 编排对问题的适配。
- **衔接**：连接状态机与 Phase 14，避免只按演示选框架。
- **为什么有用**：位于编排框架与任务需求的匹配层。图、角色和 actor 管理状态的方式不同，选型应依据依赖、并发和恢复需求。
- **建议练习**：用同一任务列出状态、并发和恢复需求再选抽象。

入口：[中文教材](../11-llm-engineering/17-agent-framework-tradeoffs/docs/zh.md) · [原课代码](../11-llm-engineering/17-agent-framework-tradeoffs/code/) · [CoderPad](../11-llm-engineering/17-agent-framework-tradeoffs/coderpad/README.md) · [课后测验](../11-llm-engineering/17-agent-framework-tradeoffs/quiz/quiz.md)
