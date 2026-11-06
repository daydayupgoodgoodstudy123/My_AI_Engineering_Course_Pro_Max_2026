<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-02--rag-over-codebase-cross-repo-semantic-search"></a>

# 综合项目 02：代码库 RAG——跨仓库 Semantic Search

> 2026年的每个严肃工程大猩猩 都进行内部代码搜索, 不仅理解字符串的含义。 源码 Amp, Cursor 的代码库回答, Augment 的企业图, Aider 的代号, Pinterest 的内部 MCP 相同的形状。 最多很多的回复, 以树质保存器进行分析, 嵌入函数和类层块, 混合搜索, 重新排序, 回答引用。 此综合项目要求您在 10 个回复器上建立 2M 代码行, 并生存下来 。 git push.

**类型:** Capstone
**语言:** Python (ingestion), TypeScript (API + 用户界面)
**先修要求:** 第五阶段(无酬工基金会),第七阶段(transformers阶段11(LLM 工程,第13阶段(工具),第17阶段(基础设施)
**实施阶段:** P5 ; P7 ; P11 ; P13 ; P17
**时间:** 30小时

<a id="problem"></a>

## 问题

到2026年,每个边境 coding agent 具有代码数据库回收层的船舶 context windows 单靠自己解决不了交叉问题 Claude1米 - 7米 - 5米 - 3米token 上下文帮助; 它不能消除排序检索的需要。 原始块的自然余弦搜索会生成代码、 单雷波重复和极少输入符号的长尾的毒效结果。 生产答案是混合的( 强烈+ ) BM25)搜索 AST 识别块,并重新排序,并配有符号引用图。

使用一个真正的舰队(不是一次辅导性回购)来进行索引,并测量MRR@ 10, 引用忠诚度和增生性。 失败模式是基础设施: 100k 文件单列波, 将一半文件重新调试, 需要通过四个回复方来正确回答这个问题 。

<a id="concept"></a>

## 概念

AST 感知的输油管吸附法将每个文件都配有树喷雾器,提取函数和类节点,并按节点边界而不是固定块 token 窗口。 每个块有三个表示式: embedding (Voyage-code-3或Nomemic-emid-code),稀有 BM25 和简短的自然语言摘要。 modality 用户问“X授权如何” 概要提到“authz”,即使代码仅包含 `check_permission`.

回收是混合的, 查询会燃烧密度和 BM25 搜索,合并上K, 并把联盟交给一个十字架 --encoder 重新排序( Cohere 重排三或三)reranker-v2-gemma-2b. 重新排序列表将使用长文本合成器( ưμ㼯A)Claude 索内特4.7与 prompt 缓冲,或 Llama 3.3 70B自办),指示按档案和行距列出每项索赔,未经引证的答复被过滤后者拒绝。

增加新鲜度是基础设施问题。 Git 点击触发 diff: 文件被更改, 符号被更改。 只有受影响的块重新组合。 受影响的跨文件符号边缘( 导入、 方法调用) 会被重新编号。 索引保持一致, 没有再处理 2M 行 commit.

<a id="architecture"></a>

## 建筑

```
git push --> webhook --> ingest worker (LlamaIndex Workflow)
                           |
                           v
             tree-sitter parse + AST chunk
                           |
            +--------------+----------------+
            v              v                v
          dense        BM25 index       summary (LLM)
        (Voyage / bge)  (Tantivy)        (Haiku 4.5)
            |              |                |
            +------> Qdrant / pgvector <----+
                            |
                            v
                      symbol graph (Neo4j / kuzu)
                            |
  query --> LangGraph agent (retrieve -> rerank -> synth)
                            |
                            v
                 Claude Sonnet 4.7 1M context
                            |
                            v
                 answer + file:line citations
```

<a id="stack"></a>

## 堆栈

- 剖析:树质报告,17种语言语法(Python,TS,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,, Rust, Go, Java, C++, 等)
- Dense embeddings:Voyage-code-3(托管)或Nomec-编织编码-v1.5(自东道),bge-code-v1 后退
- 粗略指数: antivy (Rust),使用 BM25F,在符号名称与身体上进行字段加权
- 矢量 DB: 具有混合搜索的 Qdrant 1.12, 或为50M 下向量组提供的 pgvictor + pgvictor 标度
- 块摘要模型 : Claude 海库4.5或 Gemini 2.5 Flash灯, prompt-cached
- 重新排序: Cohere 重新排序3或bge-reranker-V2-Gemma-2b 自行托管
- Orchestration: LlamaIndex 供摄入的工作流程, LangGraph 查询 agent
- Synthesizer: Claude 索内特 4.7 (1M 上下文) prompt caching
- 符号图: Neo4j(管理)或kuzu(编织)用于导入和调用边
- Observability:每回收一次朗弗斯横跨+合成步骤

```figure
ce-hybrid-retrieval
```

<a id="build-it"></a>

## 动手实现

1. **摄取活体** Iterate git 每个推钩的历史。 收集已更改的文件。 对于每个文件, 使用树管理器分析, 提取函数和带完整源的类节点。 Emit 块记录 `{repo, path, start_line, end_line, symbol, body}`.

2. **块状摘要。** 批量块进入海库4.5电话 prompt 系统前言中刻着 Prompt: “ 将此函数合并为一句话, 命名为公共合同和副作用 。 ” 。 将摘要保存在块边 。

3. **Embedding pool.** 两个平行队列:密度(Voyage-code-3 批次128)和摘要(相同模式,但以摘要字符串为主)。 `{repo, path, start_line, end_line, symbol, kind}`.

4. **BM25 index.** 实地加权的 antivy 指数: 符号名称 weight 4个符号体 weight 1. 总结 weight 2. 启用“查找名为 X 的函数”查询,同时“查找用于 X 的函数”。

5. **符号图。** 对于每个块,记录边缘: 导入( 此文件使用 repo Z 的 Y 符号) , 调用( 此函数调用 C 类的 M 方法) , 继承。 保存在 kuzu 中 。 查询时用于扩大跨 repo 边界的检索 。

6. **Query agent.** LangGraph 有三个节点 `retrieve` 密集火 + BM25 平行的,重复的,由(repo, 路径, 符号) 来显示。 `rerank` 运行十字架...encoder 上50,保持前10。 `synth` calls Claude 索内特4.7,加上上下文的重新排列块,隐藏 system prompt,需要文件:线条引用。

7. **引用执行。** 分析模型输出;任何没有 `(repo/path:start-end)` 锁定会被标记为要重新询问或丢弃。 返回只引用的回答给用户 。

8. **递增重指数。** 在每次 Webhook 上, 计算符号级别 diff 。 只有文本被修改的块重新组合。 重新配置进口改变的块的符号边。 测量: 50 文件在60秒内将 2M- LOC 船队重新索引。

9. **Eval.** 标注100个交叉折叠问题, 并附有金文件: 线条答案 。 度量 MRR@ 10, nDCG@ 10, 引用忠诚度( 违反要求, 使用可核实的锚) 和 p50/ p99 latency 。

<a id="use-it"></a>

## 实际应用

```
$ code-rag ask "how is S3 multipart abort wired into our retry budget?"
[retrieve]  12 chunks dense + 7 chunks bm25, 16 unique after dedup
[rerank]    top-5 kept (cohere rerank-3)
[synth]     claude-sonnet-4.7, cache hit rate 68%, 2.1s
answer:
  Multipart aborts are triggered by `AbortMultipartOnFail` in
  services/uploader/retry.go:122-148, which decrements the per-bucket
  retry budget defined in config/budgets.yaml:34-51 ...
  citations: [services/uploader/retry.go:122-148, config/budgets.yaml:34-51,
              libs/s3client/multipart.ts:44-61]
```

<a id="ship-it"></a>

## 交付成果

可交付技能 `outputs/skill-codebase-rag.md`。如果有一系列的回复,它会支撑输入管道、混合指数和查询 agent,并返回任何交叉问题引用的答案。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | 检索质量 | 10和NDCG@10,关于100问题集 |
| 20 | 引用的忠诚 | 含有可核实文件的答题分数: 线锚 |
| 20 | 期限和规模 | p95 查询长度, 以10k QPS 的索引式体积 |
| 20 | 递增索引正确性 | 时间 git 在一个 50 文件上进行搜索 commit |
| 15 | UX 和回答格式 | 可点击引用、 片段预览、 后续提供 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 交换自托管的节点编织码3。 测量 MRR@ 10 delta 。 报告是否通过启用重新排行来弥补差距 。

2. 输入 20% 生成的代码 (%)LLM将“生成”的旗帜添加到有效载荷和下方weight 被击中了

3. 基准 Qdrant 混合搜索相对于 pgvictor + pgvictor 比例尺,以您体积大小。 batch size 1.

4. 添加a sampling- 基于漂移检查:每周重开100个问题模拟。 提醒注意: 10 个降幅 > 5%

5. 扩展至跨语言符号分辨率: a Python 函数,在 GRPC 上调用 Go 服务。使用符号图形将其链接。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| AST-aware chunking | "功能级分裂" | 切除树喷射节点的代码, 而不是固定 token windows |
| 混合搜索 | "密集+稀少" | Run BM25 和平行的矢量搜索, 合并上K, 重新排序 |
| Cross-encoder rerank | 第二阶段 | 每一对(尖叫、候选)的模型比余弦更准确 |
| Prompt caching | "Cached system prompt" | 2026 Claude / OpenAI feature 重复前缀 tokens 最高为90% |
| 符号图 | “代码图” | 进口、调用、文件继承和回收的边距 |
| 引用的忠诚 | 答案率四舍五入 | 用户可以通过单击锚和读取引用的间隔来校验索赔的分数 |
| 递增再索引 | "搜索时间" | 墙上时钟 git 键到更改后的符号可查询 |

<a id="further-reading"></a>

## 进一步阅读

- [源码 Amp](https://ampcode.com) - 生产跨转码情报
- [源码库迪 RAG architecture](https://sourcegraph.com/blog/how-cody-understands-your-codebase) ——这个综合项目的参考深度
- [辅助回波图](https://aider.chat/docs/repomap.html) - 树管理器排序为回po 视图
- [增强代码企业图](https://www.augmentcode.com) 商业符号图 RAG
- [解密混合搜索文档](https://qdrant.tech/documentation/concepts/hybrid-queries/) 参考执行
- [旅行AI 代码 embeddings](https://docs.voyageai.com/docs/embeddings) - 旅行代码3细节
- [重排三号](https://docs.cohere.com/reference/rerank) 交叉 - 交叉 -encoder reference
- [Pinterest MCP 内部搜索](https://medium.com/pinterest-engineering) 内部平台参考
