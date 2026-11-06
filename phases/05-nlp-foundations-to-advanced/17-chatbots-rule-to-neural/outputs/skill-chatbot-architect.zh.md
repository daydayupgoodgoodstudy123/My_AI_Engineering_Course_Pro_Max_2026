---
name: chatbot-architect
description: Design a chatbot stack for a given use case.
version: 1.0.0
phase: 5
lesson: 17
tags: [nlp, agents, chatbot]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定产品上下文（用户需求、合规性约束、可用工具、数据量），输出：

1. 建筑学。基于规则、检索、神经、LLM agent 或混合（指定哪些路径去往何处）。
2. LLM 选择（如果适用）。命名模型系列（Claude、GPT-4、Llama-3.1、Mixtral）。与工具使用质量和成本相匹配。
3. Grounding 策略。 RAG来源，检索方法（第14课），tool contracts。
4. Evaluation计划。任务成功率、工具调用正确性、脱离任务率、保留对话框上的 hallucination 率。

拒绝推荐纯 LLM agent 进行任何没有结构化确认流程的破坏性操作（付款、账户删除、数据修改）。如果 agent 对任何内容具有写访问权限，则拒绝跳过 prompt 注入审核。
