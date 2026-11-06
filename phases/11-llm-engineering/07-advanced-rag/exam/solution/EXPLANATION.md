# 参考答案讲解：RerankDesk（11/07）

计时结束后再看。参考实现在同目录 `rerankdesk/`，全部是确定性本地数据。

## Part 1

source 的 hyde_search 返回 `(results, hypothesis)`。query_hyde 将真正的候选序列交给 query，给 mandatory scorer 的仍是完整原问题，并将 hypothesis 原文随结果返回。反接两种返回值会让真实文本流入候选对解包，在 adapter 外自然报错；不能改消费者掩盖类型与角色错误。source-template generator 和 replay retrieval 都正确给定，没有真实 LLM。这个组合入口是教学 adapter，源码并没有相同的集成 service。

候选保留原 id、initial score 和 original one-based rank；正确 id projection 与 lookup 已给定，不能为非法 rank 兜底；对应验证仍保留。先在完整 caller retrieval list 上做 metadata admission，再截 retrieval pool，让完整 pool 参加注入的非恒定 scorer，最后取 final count。同分稳定，零 count 是有效空结果。P1 没有给出 P3 完整词法 scorer。

source BM25 在 index 时已正确拟合 avg_dl。average_length 必须读该 generation 的值，不在每个 doc score 中重复 sum 全部长度。重 index 时正确 GIVEN 统计更新，不能把第一次均值另存成永久值或跨 index 共用。分词、counts/DF、query weights、真实 BM25 公式、稳定 source 排名和一次 batch rerank 均正确 GIVEN；P3 四 feature 仍是独立 TODO。

26,000 个不同长度文档、完整 keyword source→BM25逐 doc 评分/全部稳定排序→SearchDesk mandatory scorer/final result。完整连续三慢 1.183464/1.145908/1.336547 秒，三快 0.006304/0.006838/0.006301 秒，限值 0.11 秒；双侧 10.42/16.09 倍，最慢 1.337 秒。fit 和本地 pair-score fixture 两侧同样在计时外；query weights、实际评分、全部 candidates 与最终消费均在计时内。外部完整证据见 SCOPE。

1,600 条 supplied-candidate 的响应断言检查 batch orchestration 行为；本关性能职责是 BM25 的 avg_dl provider。

## Part 2

DBM 保存 source order 与 namespaced source/parent/child records，JSON/key codec 正确给定。load 按 source 插入顺序、numeric parent ordinal、numeric child ordinal 还原，不用 DBM 任意 key 顺序。source timestamps 是 exact integer microseconds，UTF8 raw text 与 byte interval 不重算；相同文本不等于同一个 source record。replacement 清旧键；raw source 不能从 parent payload 重建，非索引空白和无 child 的来源也原样保存。本格式不承诺事务或崩溃恢复。

## Part 3

query/text 的 mixed-case 输入都沿 source lowercase 语义。先对有序 query lower/split tokens 去给定 stopwords，再保留 terms set 与 adjacent bigrams set。term 用 whole-token set intersection，bigram 在 lower text 中按 substring presence 算一次；position 则对每个 unique term 找首次 substring，只有落在 strict first-third Python-character 范围才加 0.5。total=term+2*bigram+position+5*initial。将该独立 scorer 注入修好的 P1，不复制另一条绕过 admission/pool 的流水线。

## Part 4

同步 report_rows 接收一个完成 query 的 id/hits，按 supplied hit 顺序构造完整行。initial_rank 保留原检索位置，rerank_score 使用本次 hit.score 的 repr，不换成 initial_score 或展示舍入值。每个 child 的 parent ordinal 和原始 source label 通过正确 catalog 查询，不能将 child ordinal、source key 当作这些字段；重复选择仍保留每次原 evidence。

正确 GIVEN encode_batches 绑定当前 query，调用同步 callback，交给正确 CSV codec，再发布整个当前报告后拉下一批；它负责唯一 header 和 empty completed report。source/encoder close wrapper 也正确给定。候选不写 async loop、跨批缓存或 header 状态；no-read-ahead、first-query identity、空报告和关闭断言验证实际 driver。每批行会缓存在内存，没有固定内存上界的承诺。

## Part 5

用 (source_key,parent_ordinal) 保持 first-child encounter 的 block 顺序，输出完整 parent raw interval，每个选择的 child evidence 追加其 original span、score 和 initial rank。同一 child 的每次 selected hit 都保留各自 score/rank，score 字段使用该次 rerank score。不要按文字合并不同 source，不把 parent 对每个 child 重复输出，也不按 offset 重排本来的 hit evidence。给定 builder 已按 source 分开构造 parent/children，末尾 child 的真实 extent 直接保留。

## 这套题证明了什么，没证明什么

验证本地 candidate orchestration、目录存取、源启发式 feature 算法、逐 query 报告和 parent evidence 结构；不证明 neural cross-encoder、真实语义相关性提升、百万文档规模性能、production protocol 或 crash durability。来源里的模型、价格和收益文字不作为本题已核实事实；60 分钟未经真人校准。
