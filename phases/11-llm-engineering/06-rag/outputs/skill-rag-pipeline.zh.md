---
name: skill-rag-pipeline
description: Build and debug RAG pipelines from first principles
version: 1.0.0
phase: 11
lesson: 6
tags: [rag, retrieval, embeddings, vector-search, llm-engineering]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="rag-pipeline-pattern"></a>

# RAG 管道图案

每个 RAG 系统遵循此模式 :

```
documents -> chunk -> embed -> store
query -> embed -> search(top_k) -> build_prompt -> generate
```

每个文档都出现过一次索引。 每个用户都会要求查询 。

<a id="when-to-use-rag"></a>

## 何时使用 RAG

- 该 LLM 需要查阅私人或最近文件
- Fine-tuning 价格太贵或太慢无法更新
- 你需要引用源解答
- 知识基础经常变化

<a id="when-not-to-use-rag"></a>

## 不使用时 RAG

- 答案是一般都知道 LLM 已经
- 任务在于创造(写作、集思广益)而非事实
- 您需要模型来采用特定的推理样式( 使用) fine-tuning)

<a id="implementation-checklist"></a>

## 实施清单

1. 将文档排入 256-512 token 含有50-token overlap
2. 使用一个一致的嵌入每个块 embedding 模型
3. Store embeddings 在 a 中 vector database 与原始文本
4. 在查询时,将用户的问题嵌入同一模式
5. 获取上K( 5- 10) 最相似的块 cosine similarity
6. 构建一个 prompt:系统指令+检索到的上下文+用户问题
7. 产生答案, grounding 在检索的上下文中
8. 以源引用返回答案

<a id="common-mistakes"></a>

## 常见错误

- 使用不同的 embedding 索引和查询模式(矢量不兼容)
- 块太小( 接近上下文) 或太大( 模糊关联性)
- 不包括块的重叠( 边界上的句子)
- 文档更改时忘记重新索引
- 将回收的块返回用户, 而不生成一致的答案
- 不设置 temperature=0(事实) RAG 查询( 更高 temperature = 更远 hallucination)

<a id="debugging-retrieval"></a>

## 调试检索

如果右侧块未被检索 :
1. 打印查询 embedding 并且确认它不是零
2. Check cosine similarities 手动为已知相关块
3. 尝试修改查询以匹配文档 vocabulary
4. 校验 embedding 模式匹配索引和查询时间
5. 检查相关内容是否在 chunking

<a id="production-parameters"></a>

## Production parameters

- 块大小: 256-512 tokens
- 重叠: 50 tokens (块大小的10-20%)
- 最大剂量:5-10(多数使用)
- Temperature:对事实答案为0
- Embedding 型号: 文本-embedding-3-小(成本效益高)或文字-embedding-3大(更精确)
