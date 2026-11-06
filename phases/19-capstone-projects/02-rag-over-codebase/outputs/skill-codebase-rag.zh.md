---
name: codebase-rag
description: Build a cross-repo semantic search system with AST-aware chunking, hybrid retrieval, incremental re-index, and cited answers.
version: 1.0.0
phase: 19
lesson: 02
tags: [capstone, rag, code-search, tree-sitter, qdrant, bm25, hybrid-retrieval]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于10+储存库总共至少2M条代码,应建立一个吸收管道、混合指数和一个引用强制查询 agent 以可核查的文件: 线锚回答交叉解答问题。

构建计划 :

1. 分析每个树管理器的文件。 在函数和类节点边框处放整块。 存储 `{repo, path, start_line, end_line, symbol, body}`.
2. 以 Claude 海库4.5或 Gemini 2.5 使用闪光 prompt-cached system prompts。将单句摘要保存在块旁。
3. 分为三个结构的索引:Qdrant(音频、波形代码3或混凝土代码),Tantivy(音频)BM25 与字段 weights)和kuzu(进口、电话、继承的符号图形边緣)。
4. 构建 LangGraph query agent 有三个节点: 检索( 高度平行) BM25重排( Cohere 重排3 或 Bge-)reranker-v2-gemma-2b,合成( 合成) (Claude 索内特4.7与 prompt 备查和文件:线条引证要求)
5. 过滤后:在没有可核实的情况下驳回任何索赔要求 `(repo/path:start-end)` 锁定; 重新检查或下降 。
6. 电线a git 推 Webhook 计算符号级别 diff , 并只重新组合更改的块。 目标: 50 文件 commit 可在60年代以下的2MLOC舰队上搜索
7. 以100个问题进行评分。报告MRR@10, nDCG@10, 引用忠诚度和潜伏百分位数。
8. 运行每周一次的漂移任务, 重新执行 ERR 和提醒@ 10 下降 > 5% 。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | 检索质量 | 10和NDCG@10,关于100问题集 |
| 20 | 引用的忠诚 | 含有可核实文件的答题分数: 线锚 |
| 20 | 期限和规模 | p95 查询长度, 以10k QPS 的索引式体积 |
| 20 | 递增索引正确性 | 时间 git 在一个 50 文件上进行搜索 commit |
| 15 | UX 和回答格式 | 可点击引用、 片段预览、 后续提供 |

艰难的拒绝 :

- Fixed-size token chunking 而不是AST意识 chunking会产生毒药的编码重的子公司
- 仅余弦检索, 不包含 BM25 或重排。已知在精确符号名查询中失败 。
- 答案没有强制文件: 引用线条 。
- 整个体重...embedding 在每个 git 推; 必须递增 。

拒绝规则 :

- 拒绝在不阅读许可证的情况下使用索引。 embedding 第三方病媒仓库。
- 拒绝回答那些声称引用索引从未看到的文件的询问;在返回之前总是要核实锚。
- 拒绝在4s以上第95页上填写答复;返回部分结果,然后用后续处理。

输出:含有摄入管道的回收站, LangGraph query agent,100个问题标签 eval set,一个兰富斯仪表板链接,和一个写作标签 , 命名三种检索失败模式( 生成的代码中毒, 长尾符号回忆, 交叉反转符号分辨率) 以及每个模式的精确修改 。
