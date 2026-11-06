---
name: skill-embedding-patterns
description: Production patterns for embeddings, vector search, and similarity
version: 1.0.0
phase: 11
lesson: 4
tags: [embeddings, vectors, similarity, search, chunking, quantization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="embedding-patterns"></a>

# Embedding Patterns

每个 embedding 工作流程遵循本合同:

```
text -> embed(text) -> vector (float array)
similarity(vector_a, vector_b) -> score (float)
```

该 embedding 模型和相似度测量是唯一两个重要决定,其他一切都是管道。

<a id="when-to-use-embeddings"></a>

## 何时使用 embeddings

- Semantic search 横跨文档(查找含义,而非关键词)
- 将类似项目(支持票、产品审查、错误报告)分组
- 按最近的邻里分类(按标签示例的相似性标记新项目)
- 建议系统(找到与用户喜欢的项目相似的项目)
- 调试(使用相似阈值查找近乎重复的内容)

<a id="when-not-to-use-embeddings"></a>

## 不使用时 embeddings

- 精确的关键字匹配( 使用全文搜索)
- 结构化查询(使用) SQL,过滤器)
- 手工标签更快的小型数据集( < 100项)
- 可解释性大于准确性的任务(embeddings (不透明)

<a id="model-selection"></a>

## 模式选择

根据您的限制选择 :

- **需要一个 API,最高值**: OpenAI text-embedding-3小(1536美元,0.02美元/1亿美元) tokens)
- **需要最大限度的准确性**(1024日,0.06/1亿美元) tokens最高值( MTEB)
- **需要当地/私营**BGE-M3 (1024d, 免费, 多语种, GPU 推荐)
- **需要快速的本地原型**:全 MiniLM-L6-v2 (384d, 免费, 运行中) CPU)
- **需要多种语文**:Cohere 嵌入- v3 (1024d) 或 BGE-M3(两种语言均强势)

规则:从不混合 embedding 索引和查询之间的模型。来自不同模型的矢量生活在不兼容的空间中。

<a id="chunking-rules"></a>

## Chunking rules

1. 目标256-512 tokens 每块50 -token overlap
2. 如果可以避免的话,不要分开中句
3. 包含每个块的元数据( 源文件、 区域标题、 位置)
4. 结构化文件(Markdown, HTML)),先按标题边界分割
5. 通过搜索已知答案和检查检索来测试块质量

<a id="similarity-metric-selection"></a>

## 相似度量选择

- **Cosine similarity**: 默认选择, 处理可变长的文字, 常规化
- **点数产品**:当矢量已经单位正常化时使用(OpenAI 模型),稍快
- **欧几里德距离**:当绝对位置重要时用于分组

当向量正常化时, 这三个区域给予相同的排序。 选择只对非正常化的向量很重要 。

<a id="storage-optimization"></a>

## 存储优化

压缩的三层, 可堆放 :

1. **马特约什卡短跑**:减少尺寸(1536 - > 256=6x节省,精确度损失3-5%)
2. **Float16 quantization**:将每个维度的存储量减半(2x 节省, < 1% 准确性损失)
3. **Binary quantization**:每个维度1位数(节省32位数,精确度损失5-10%,与重新校正一起使用)

生产模式:对全体进行二进制搜索,以浮点32矢量为顶层1000再芯。

<a id="retrieve-then-rerank"></a>

## 先检索，再重排（Retrieve-then-rerank）

两阶段输油管的准确性最好:

1. Bi-encoder 获取100名顶级候选人( 快速, 使用预编的) embeddings)
2. Cross-encoder 重新排到前十位( 慢一点 处理每对查询- doc )

精确度量比单级检索高出10-15%。 当精确度超过延迟度时使用 。

<a id="common-mistakes"></a>

## 常见错误

- 使用不同的 embedding 索引和查询模式
- Embedding 整个文档而不是块(embedding 成为一切的平均数)
- 之前没有将矢量正常化 cosine similarity (大多数模型都提前正规化,但经核实)
- 忽略块重叠( 在断线时分割的语句失去上下文)
- 只存储没有原始文字的矢量( 您需要同时检索)
- 不,不,不,不,不,不,不。embedding 当模型改变时(旧矢量不兼容)
- 仅根据准确度选择尺寸(与尺寸线性地选择储存和潜伏尺度)

<a id="debugging-embeddings"></a>

## Debugging embeddings

如果搜索结果差:

1. 校验查询 embedding 非零(空或空白输入产生零矢量)
2. 手动检查已知相关文档的相似性评分
3. 尝试修改查询以匹配文档 vocabulary
4. 检查块边界,以确保相关内容不会在块中分割
5. 比较所有度量( cosine, dot, ecclidean) 的最高公里结果 normalization issues
6. 测试一个微小匹配的查询( 从文档中复制一个句子) 以确认管道工程

<a id="production-parameters"></a>

## Production parameters

- 块大小: 256-512 tokens
- 块重叠: 50 tokens (块大小的10-20%)
- 顶级检索:5-10用于直接使用,50-100用于重新排序
- 相似性阈值: 0.7+ 余弦(在此以下,结果通常无关紧要)
- Batch embedding:每份100-500个文本的处理 API 请求输送量
- 索引重建: 当模型或文档发生重大修改或更新时重新组合
