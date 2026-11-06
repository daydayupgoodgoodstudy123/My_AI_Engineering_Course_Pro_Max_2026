# 面试官手册：RerankDesk（11/07）

计时期间不向候选人展示。开场 2 分钟，五关 12、12、12、10、12 分钟，总计 60；未经真人校准。让候选人边做边解释，允许查官方文档与提问。卡住约 5 分钟后一次只给一级提示。

## 澄清问题标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | HyDE 返回什么、用哪个问题打分？ | "The source returns candidate rows, then hypothesis text. Retain that text and pair-score with the original question." |
| 1 | 输入已经被 top-k 截了吗？ | "No. The fixture supplies the complete ordered retrieval list. Apply metadata admission before its pool boundary." |
| 1 | pool 和 final count 一样吗？ | "No. Every admitted pool candidate competes under the injected scorer before the final cut." |
| 1 | scorer 可以换成 initial score 吗？ | "No. It is a required caller dependency with meaningful nonconstant pair scores." |
| 2 | dbm keys 的顺序？ | "Source insertion order, then numeric parent and child ordinal defines catalog order." |
| 2 | 时间单位？ | "Exact integer microseconds. Equal names or text do not merge identities." |
| 2 | 事务保证？ | "None requested for this local dbm replacement format; persist the complete valid catalog." |
| 3 | term 和 position 都是整词吗？ | "No. Term overlap is whole-token set overlap; the source position feature uses the first substring location." |
| 3 | bigram 何时去 stopwords？ | "Filter the ordered query token list first, then build unique adjacent pairs." |
| 3 | 前三分之一含边界吗？ | "Strictly before len(lower_text)//3 Python characters." |
| 4 | initial_rank 是新排名吗？ | "No. Preserve each hit's original retrieval rank, query ownership and round-trippable score text." |
| 4 | 空第一批？ | "Emit the one header and let later nonempty batches produce their own rows." |
| 5 | parent 以 ordinal 去重？ | "Use source identity plus parent ordinal, retaining every nested selected child in hit order." |
| 5 | 返回 child 还是 parent？ | "One complete original parent block per identity, with original child spans and evidence metadata." |

## Part 1 候选调度（目标 12 分钟）

坑：
- query_hyde 把 source 的 `(results, hypothesis)` 两个返回角色接反；真实 hypothesis 字符串进入 query，再由正确 project_candidates 解包候选对，产生自然 ValueError。错误发生在 adapter 外两次调用，不能在 consumer 吞错或从字符串猜候选。hypothesis 原文要返回，pair scorer 必须接收完整原问题。
- metadata admission 在 pool boundary 后执行，allowed candidates 已被不相关来源挤掉。
- pool 在 rerank 前截成 final count，低 initial/high pair-score 的合法候选永远看不见。
- BM25 score 忽略 index 时已正确拟合的 avg_dl，每 doc 都重扫全部 doc_lengths。修复 provider 去消费本 index generation 的 scalar；不能用常数、跨 index 的全局值或重建后未失效的旧值。不同 query 仍真正重新评分。

source-template HyDE generator、完整本地 retrieval callback、original-id projection、TF/DF/counts/query weights/BM25公式、稳定完整 keyword source 与 once-per-batch rerank 均正确 GIVEN。原检索 id/rank 断言与 rank-substitution 错修验证给定 identity projector 的集成边界。source 原码本来预存 avg_dl，本题明确植入读取生命周期回归。完整 source 输出 N 条候选，不把必要评分或结果移出 timer；metadata 为空时仅省不会进 pool 的临时 Candidate 包装，非空 metadata 仍完整预筛，original ranks 不变。

26,000 个不同长度文档、完整 keyword source→BM25逐 doc 评分/全部稳定排序→SearchDesk mandatory scorer/final result。完整连续三慢 1.183464/1.145908/1.336547 秒，三快 0.006304/0.006838/0.006301 秒，限值 0.11 秒；双侧 10.42/16.09 倍，最慢 1.337 秒。fit 和本地 pair-score fixture 两侧同样在计时外；query weights、实际评分、全部 candidates 与最终消费均在计时内。外部完整证据见 SCOPE。

1,600 条 supplied-candidate 的响应断言用于防止破坏 batch orchestration；本关性能缺陷在 BM25 的 avg_dl provider。完整检索仍包含稳定排序，不声称整体 O(N)。

H1 "What are the two outputs of this source retrieval call?" H2 "Who remains eligible before each boundary?" H3 指向 HyDE adapter、pool/final 职责与该 index generation 的统计字段。追问：为何 metadata 必须作用于完整 caller list？（已丢失的候选无法靠事后过滤恢复。）

HyDE 的 retrieval/generator 都是正确本地依赖，不运行 LLM。源码只返回 results 与 hypothesis；组合到这个 service 是明确教学适配。不同问题各有自己的 hypothesis/results，metadata、initial scores 与 original ranks 沿用同一个已声明的 query 合同；hypothesis 不充当原问题或最终回答。

## Part 2 dbm catalog（目标 12 分钟）

坑：
- DBM key iteration 与字符串中的数字都不能充当 numeric child ordinal 顺序。
- source insertion order 与 source-scoped parent/child identities 要原样恢复；相同 source label/text 不去重。
- 微秒 timestamp 不能降成秒；raw source/child UTF8 byte intervals 也不能重新按字符长度猜测。
- replacement 必须清旧 namespaced records，不能把旧 parent/child 混进新 source set。
- source raw text 不等于 parent text 的拼接；非索引尾部空白和无 child 的来源仍是应保存的 payload/provenance。

正确 JSON/key codec 已给定。H1 "What orders a child within its source parent?" H2 "Which raw source fields exist even without an indexed child?" H3 指向 source order 与 numeric ordinals。追问：dbm replacement 是否是原子事务？（本合同不提供；不要声称 crash-safe。）

## Part 3 source lexical scorer（目标 12 分钟）

坑：
- term_overlap 按 whole-token sets；重复词只算一次，标点不额外清洗。query/text 都沿 source lower 语义，mixed-case 不改变 feature。
- bigrams 来自先去 stopword 的保序 query list，再去重；在 text 中按 substring presence 每对最多一次，不按出现次数累加。
- position 用每个 unique term 的首次 substring find，严格小于 lower text 的字符长度整除三；不能把它改成整词/token/UTF8 byte 位置。
- total 严格是 term+2*bigram+position+5*initial。P1 稳定排序、admission 和 pool policy 已修好；本关不重复实现它们。

H1 "Which two features intentionally use different match semantics?" H2 "What remains ordered before the bigram set?" H3 指向四个真实 feature 而非 model wrapper。追问：这能说明 neural reranker 收益吗？（不能；source 本身没有 attention model。）

## Part 4 query evidence CSV projection（目标 10 分钟）

坑：
- initial_rank 来自原检索记录，输出顺序沿用 supplied hits；不能用 rerank position 替换 rank，也不按旧 rank 重排完成的 hits。
- 使用这次 hit 的 rerank score，不用 initial score；文本须回到同一个 binary64 值，不能提前格式化成展示精度。
- 逐 child 从 catalog 取真实 parent ordinal 和完整 source label，不能混用 child ordinal、source key 或当前 query 的总量。每次 hit occurrence 都保留。

候选只写同步 report_rows，一次只接收当前 query_id/hits。完整 async callback 绑定、逐 batch 拉取/发布、唯一 header、empty completed report 和关闭都正确 GIVEN；first-query cache 与 collect-all wrong 在该 driver 内作为集成验证，候选不修跨批所有者缓存或通用 cadence。CSV quoting/newline codec 也 GIVEN。H1 "Does this field come from the original retrieval, rerank result or catalog?" H2 "Which ordinal belongs in parent_id?" H3 对照 hit 与 child/source 的不同字段职责。追问：为什么报告不重新排名？（输入是已经完成的 ordered rerank batch，应保留原 evidence 顺序）。

## Part 5 parent context tree（目标 12 分钟）

坑：
- 每个 source+parent identity 只出一个完整 context，但所有选中 child matches 都嵌入，不丢 evidence。同一 child 再次出现在 selected hits 中也保留该次原 score/rank；nested score 不替换成 initial score。
- parent blocks 按首次最佳 child 的 hit 顺序，内部 matches 也保持 hit 顺序，而非 catalog offset 顺序。
- 相同 parent ordinal 或文本在不同 source 中不共用 identity；末尾短 child 保留真实 byte extent。

正确 per-source chunk builder/lookup 已给定。H1 "What parent identity does this child belong to?" H2 "Which order carries retrieval evidence?" H3 指向 source-scoped grouping 和 nested original spans。追问：能跨文档拼 parent 吗？（不能；source demo 拼全文的限制在本题由正确 builder 避免。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，原测试通过即得 |
| 调试方法 | 20 | 读 traceback、核对候选身份与各截断边界、用数据验证假设 |
| 代码质量 | 15 | 保留 scorer 依赖与必要输出、清楚命名、没有死代码 |
| 沟通 | 15 | 主动澄清匹配语义、精度、顺序与来源合同 |
| 工程判断 | 10 | 解释 catalog 生命周期、资源边界和 toy lexical scorer 限制 |

每项都写具体证据，没观察到的写“未观察”。提示次数、变绿时间和原 60 分钟成绩单独记录。
