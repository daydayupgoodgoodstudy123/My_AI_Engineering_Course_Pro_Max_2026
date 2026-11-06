---
name: skill-advanced-rag
description: Build production-grade RAG with hybrid search, reranking, and evaluation
version: 1.0.0
phase: 11
lesson: 7
tags: [rag, hybrid-search, bm25, reranking, hyde, evaluation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="advanced-rag-pattern"></a>

# Advanced RAG Pattern

Basic RAG:嵌入查询 - > 矢量搜索 -> 顶部- k - > 生成 。
Advanced RAG:嵌入查询+ BM25 - > 引信排行 - > 重排 - > 顶部-k - > 生成。

```
query -> [vector search (top-50)] -+-> RRF fusion -> reranker (top-5) -> prompt -> LLM
                                   |
query -> [BM25 search (top-50)]  --+
```

<a id="when-to-upgrade-from-basic-rag"></a>

## 何时升级为基础 RAG

- 检索质量下降到70%以下
- 用户报告错误或不相关的答案
- 公司增长超过100K块
- 查询使用不同的 vocabulary 文档
- 多次访问问题总是失败

<a id="implementation-checklist"></a>

## 实施清单

1. Add BM25 与矢量指数并列的索引
2. 平行运行两个搜索( 每个顶部- 50)
3. 合并为 Reciprocal Rank Fusion (k=60) (单位:千美元)
4. 重新排名顶级候选人 与交叉 -encoder
5. 以前5为决赛 prompt
6. 添加忠诚 evaluation 在一个测试集

<a id="technique-selection-guide"></a>

## 技术选择指南

- **混合搜索**:总是用于生产。查询时间不增加任何费用。
- **Reranking**: 当回想@ 50 不错时使用, 但回想@ 5 不好。 添加 50- 200 ms latency 。
- **HyDE**:当查询模糊或使用不同时使用 vocabulary 增加一个 LLM 电话
- **父母-子女块**:当小块缺少上下文但大块淡化相关性时使用。
- **元数据过滤**:当文件有明确的类别(日期、来源类型、部门)时使用。
- **查询分解**:用于需要多个文档提供信息的多跳问题。

<a id="common-mistakes"></a>

## 常见错误

- Running BM25 和不同块组的矢量搜索( 他们必须搜索相同的元素)
- 使用过小的候选人人才库进行重新排队( 上至10人太少; 使用上至50人)
- 为每个查询添加 HYDE( 仅在以下时间帮助) vocabulary 错配是瓶颈)
- 不评价变化(措施) Recall@k (在每种技术前后)
- 在测量输油管失灵之前,先对管道进行工程改造

<a id="evaluation-workflow"></a>

## Evaluation workflow

1. 创建有已知答案块的 50+ 测试问题
2. 每种检索方法的度量回溯@ 5 和回溯@ 10
3. 对于成功检索的查询, 测量生成答案的忠实度
4. 每周跟踪量值,随着体积的增长
5. 在添加更多技术之前先调查个人的失败
