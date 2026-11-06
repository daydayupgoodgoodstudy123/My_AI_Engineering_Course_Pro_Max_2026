<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="chunking-strategies-compared"></a>

# Chunking 策略比较

> Chunking 确定你的检索器能浮出什么。 embedding 型号, 无 reranker, 否 LLM 能够修复下游的损坏。

**类型:** Build
**语言:** Python
**先修要求:** 阶段11 课程04(embeddings), 06 (RAG, 07(高级) RAG; 阶段19轨道B基金会(指标20-29)
**时间:** ~90分钟

<a id="learning-objectives"></a>

## 学习目标
- 执行5项 chunking 零下战略:固定窗口、句子、递归式组合、语义组合和结构 markdown headers.
- Measure recall@k 解释为什么一个策略在文章上获胜,
- 读取块长分布并识别每个策略输入的失败模式:无主句、中符号切除、仅页码块、语义漂移。
- 为新元素选择默认值, 不运行基准, 检查三个属性: 文档类型、 平均段落长度, 以及格式是否带有明确的结构 。

<a id="the-problem"></a>

## 问题

每个 RAG 管道开始将源文档切成小到 embedding 模型适合它们,而且足够大 每个碎片都带有一个自成一体的想法。 hyperparameter。它是上圈 检索器可以返回。

询问“ 预算中止阈值看起来像什么” 的查询只有在持有中止阈值的块可以达到时才能成功。 如果固定窗口分割器从周围环境切除阈值, 则 embedding 移动到不同的组, BM25 得分下降, rerankers 看见噪音,答案是 LLM 生成是错误的。 2024年的论文“ LongRAG: 用长字符来增强回收- 推荐一代” LLMs测量到35%的绝对回溯率 chunking 2025年关于背景块页眉的后续工作缩小了差距,但没有予以弥补。

这个课程可以建立五个战略 并肩作战 与一个标有金标签的回答线的固定体对齐 让你自己读取回想数字

<a id="the-concept"></a>

## 概念

```mermaid
flowchart LR
  Doc[Source Document] --> S1[Fixed Window]
  Doc --> S2[Sentence]
  Doc --> S3[Recursive Split]
  Doc --> S4[Semantic Cluster]
  Doc --> S5[Structural Markdown]
  S1 --> Chunks1[Chunks]
  S2 --> Chunks2[Chunks]
  S3 --> Chunks3[Chunks]
  S4 --> Chunks4[Chunks]
  S5 --> Chunks5[Chunks]
  Chunks1 --> Index[Embedding Index]
  Chunks2 --> Index
  Chunks3 --> Index
  Chunks4 --> Index
  Chunks5 --> Index
  Index --> Eval[Recall@k vs Gold Spans]
```

<a id="fixed-window"></a>

### Fixed-window

粗力基线。 切除每个 N 字符。 可以选择重叠, 所以从位置 N 切除的句子会显示整个块内, 位置 N - 重叠 。 快速、 确定性、 边界很可怕 。 使用它作为控制, 而不是默认 。

<a id="sentence"></a>

### Sentence

使用正则或简单状态机器分割句号边框。 将一个或多个句子打包成块, 最多到目标字符预算。 停止切换中字。 仍然切换中和中区 。 许多早期的默认值 RAG 管道和没有其他结构的流言的合理选择。

<a id="recursive-split"></a>

### 递归分割

由 2023 年代的图书馆推广的等级战略。 尝试先分割最强的分隔符( 双新线, 段落) , 后再返回下一个分隔符( 单新线) , 然后返回字符 。 当块与预算匹配时, 递归会终止 。 文档结构不一致, 因为它会按区域进行调整 。

<a id="semantic-clustering"></a>

### 语义组合

嵌入每句话。 组合相连的句子, 共一个主题的圆形。 当运行与圆形相似时, 切换到一个阈值以下时, 边界代表的是意义, 而不是字符 。 越慢构建和依赖 embedding 模式,但有弹性 的文件,转换主题 在段落内。

<a id="structural-markdown-headers"></a>

### Structural markdown headers

具有明确结构的文件(markdown,结构化图文集,RFC式的编号区块,按方向边界切除。每个块都变成标题,加上下到下到同一或更高层次的下一个标题。每个主题最小块,但只有在材料完善时才能使用。

<a id="how-recallk-measures-the-boundary-choice"></a>

### How recall@k 测量边界选择

标有金标签的查询在源文档中带有答案宽度的精确字符偏移。 之后 chunking,您会问:检索器返回的顶部块中是否有任何一块与金盘重叠?如果是, recall@k 。如果是,则该查询为 1。在查询集中平均为 0。运行相同 evaluation 每一个策略和扩散 都显示你所拥有体积的边界政策

```figure
ci-chunk-boundaries
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `fixed_window(text, size, overlap)` - 基线。
- `sentence_chunks(text, target)` - 简单的句子包装器。
- `recursive_split(text, separators, target)` - 等级递归
- `semantic_chunks(text, similarity_threshold)` - 以机器人为主的集群,在确定模型之上 embedding.
- `structural_markdown(text)` - 头 - 意识分裂。
- `mock_embed(text, dim)` - 大麻类 embedding 所以循环就断线了
- `DenseIndex` - B轨道19号阶段使用的形状 hybrid retrieval lesson.
- `eval_recall(strategy, corpus, queries, k)` - 比较圈
- 一个 `main()` 运行每个策略的固定体 并打印 recall@k table.

运行：

```bash
python3 code/main.py
```

输出为小表格, 每条策略一行, 每 k 列一列。 句子在结构固定上会丢失 。markdown 赢 markdown 固定。 递归性在混合固定上保持自身, 因为循环会适应。 语义组合在没有有用的结构提示的情况下, 赢得了传导性固定 。

<a id="failure-modes-the-table-will-not-hide"></a>

## 失败模式

**孤儿判决** 句子包装产生块 错过主题句。 embedding 然后指向错误的组。

**中标切口** 代码内有固定窗口,或 YAML 将一个标识符分成一半,两半嵌入噪音中

**仅页眉块。** Structural markdown 散发出一块内含一切的 `## Title`。过滤这些内容或附加下块的第一段。

**语义流逝** 当元素在主题上一致时语义组合 。 5000个字符块将许多特定答案包成一个扩散的 embedding。将语义和硬字符盖结合起来。

**Stale embeddings.** 语义组合使用 embedding 模型。如果您更改了模型,您也会更改块。将块模型与检索模型分开,或者一起重建索引。

<a id="choosing-a-default-without-running-the-benchmark"></a>

## 选择默认而不运行基准

三个属性决定新体的默认块块 。

| 财产 | 价值 | 默认 |
|----------|-------|---------|
| 文档类型 | 无结构的证明 | 递归分割,目标800 |
| 文档类型 | Markdown /RFC / 转基因生物 API docs | Structural markdown |
| 文档类型 | 代码 | AST-意识(范围已超出;见第19阶段,02课) |
| 段落长度 | 长篇,单篇 | 判决,目标500 |
| 段落长度 | 简短、混合专题 | 语义,门槛0.6 |

当怀疑时, 选择递归性分割。 这是最强的单一战略基线 。

<a id="use-it"></a>

## 实际应用

生产模式:

- 在您发新管道之前运行 eva; 不要信任您的库默认的战略 。
- 每当您更改时, 重试 : embedding 模型或体积组合;胜者取决于体积。
- 将策略名称保留在每个块的元数据中, 这样您就可以稍后属性回归 。

<a id="ship-it"></a>

## 交付成果

F轨道的终点到终点 RAG 系统在课程69中使用在此选择的块块作为第一阶段。 harness 载于第68课中 recall@k 与 `eval_recall` 返回到此课中。选择在您的运动中赢得的策略,然后将其输入到前面。

<a id="exercises"></a>

## 练习

1. 增加第六项战略: token- 窗户用 `tiktoken` 而不是字符数。 比较同一固定窗口的大小 。
2. 将30%的代码块部分输入正文固定。 重新运行表格。 解释为什么每个策略都包含结构 markdown 失去记忆
3. 替换确定论 embedding 与您项目的真正提供者的连接。 测量语义集合回溯三角形。 报告战略之间的扩展范围是扩大还是缩小 。
4. 添加a `summary` 字段中每个块:一个单项子机器人描述。用块体的外附摘要重新运行反转。测量回调升。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Recall@k | "我们得到的那一块是对的吗?" | 任何上方K块重叠的查询分数 |
| 块重叠 | "滑动窗口" | 重新包含下块中上块的最后 N 字符 |
| 结构分裂器 | "头人意识的块" | 在 H1/H2/H3 边框中切除;标题文字是块的一部分 |
| 语义块 | "有广度意识的块" | 嵌入句子,按近似机器人分组,流出 |
| 中流体漂移 | 托比特轮班 | Cosine similarity 运行中平均值和下一句之间,会过一个阈值 |

<a id="further-reading"></a>

## 进一步阅读

- [长方形搜索组:用长方形增强回收型 LLMs (arXiv 2406.15319)](https://arxiv.org/abs/2406.15319)
- [Anthropic,上下文检索](https://www.anthropic.com/news/contextual-retrieval)
- [LlamaIndex, Chunking 生产战略 RAG](https://docs.llamaindex.ai/en/stable/optimizing/production_rag/)
- 阶段11 课程06 - RAG fundamentals
- 第11阶段课程07-高级 RAG
- 第19阶段课程 65 - hybrid retrieval 将这里的产物排成一行
- 第19阶段课程68 -- -- 评估 harness 并且可以分辨出生产中的策略选择
