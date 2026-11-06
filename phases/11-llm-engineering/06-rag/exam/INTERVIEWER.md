# 面试官手册：SourceWeave（11/06）

候选人计时期间不要看。开场 2 分钟，五关 12、12、12、10、12 分钟，总计 60 分钟；尚无真人校准。候选人可以提问、查官方文档、解释取舍。卡住约 5 分钟后一次只给一级提示。

## 澄清合同

| 关 | 问题 | 只在问到时回答 |
|---|---|---|
| 1 | flat id 与 ordinal？ | "A flat chunk id identifies the original snapshot record. The ordinal is local to its source." |
| 1 | reindex 是追加吗？ | "No. It replaces documents, chunks, vocabulary, IDF and vectors as one new generation." |
| 1 | top_k=0？ | "It returns no hits. None uses the configured default; that helper is already correct." |
| 2 | 精度与重复内容？ | "Preserve binary64 coordinates, raw UTF8 text and source identities. Equal names or text do not merge records." |
| 2 | 写入一半失败？ | "The complete previous snapshot remains committed. No crash/fsync guarantee is requested." |
| 3 | query 从哪里取？ | "Use the explicit question, not the prompt suffix." |
| 3 | 什么叫支持？ | "Distinct whitespace-token keyword overlap after the supplied source stopwords. The first positive maximum wins." |
| 3 | 最短句子、标点？ | "At least ten stripped Python characters. Keep source punctuation and literal-period splitting." |
| 3 | citation label？ | "One-based retrieved-local position, plus original global chunk/source id and absolute byte span." |
| 4 | appendix 导出所有来源吗？ | "Only complete positive markers actually present in the replayed answer, unique in first-use order." |
| 4 | marker 分片？ | "A complete marker may span fragments. Preserve body fragments exactly." |
| 5 | 短 section？ | "Keep the largest fitting boundary intact. Never merge sibling units." |
| 5 | heading 与偏移？ | "Cover heading tokens once as original text; propagate the title separately as metadata. Offsets are UTF8 bytes." |

## Part 1：context 与 generation

坑：

三层缺陷：project_hit 错用 source-local ordinal 作为 flat id；正确的 render_context -> validate_hit 在生产者外 1–2 次调用报 provenance ValueError。它不天然产生 IndexError。修复后 reindex 仍把旧 vectors 拼入新 chunks，正确 snapshot consumer 拒绝不一致 generation。第三层每个 query 都重新完整 fit 不变 corpus；正确 TF-IDF 本身已给定，修复生命周期，让 query 使用当前 generation 的坐标。每次 query 仍计算 query vector、评分、投影和完整 prompt，不能缓存首个答案或清空 hits。

H1 "Which identity reached the provenance consumer?" H2 "Which fields belong to one replacement generation?" H3 指向 fit 所处的生命周期。追问：何时需要重建 IDF？（corpus replacement，而非每次相同 generation query。）性能数据见 SCOPE 与外部 timing evidence，所有必要输出都在计时范围内。

## Part 2：完整 SQLite snapshot

坑：

按插入顺序保存 documents、按坐标顺序保存 vocabulary/IDF/chunks/vectors；不以内容去重。保存元数据 generation、原文和 UTF8 spans、binary64 值（含 -0.0 sign bit）；IDF 与 vectors 均用给定 double codec 的 BLOB，不能依赖 SQLite REAL 保留符号零；正确 codec 给定。一次事务替换所有表，插入失败回滚之前的删除。新 store 无 snapshot；空 corpus 是有效 committed generation。load 不重新 fit。已保存的词表即便不是字母顺序，也须连同对应 IDF/vector 维度原样恢复。

H1 "Are these rows one coherent vector space?" H2 "What survives when the insert fails?" H3 指向事务覆盖删除与全部插入。追问：存精确 fitted vectors 与仅存原文有何区别？（后者需要重建，并不保留本合同中的精确坐标。）

## Part 3：抽取回答与真正引用

坑：

这是独立 TODO，不重复 P1 检索/fit。question 的 lower/split distinct set 去掉给定 stopwords；按 hits 顺序和 source literal-period 句子顺序遍历。strip 后长度至少 10 Python 字符；按 distinct intersection 计分，仅严格大于当前正分时更新。同分留最早，零支持使用原 source fallback 且无 citation。eligible 句子只含 stopwords 时也不能产生支持；恰好 10 字符仍须保留。引用保存实际赢家的 source、global chunk、原 UTF8 sentence interval 与 retrieved-local label。重复词不能堆高支持，global id 不能冒充 local label。

H1 "Are repeated words additional evidence?" H2 "Which sentence won the first positive maximum?" H3 指向 set、strict comparison 与给定 citation helper。追问：这能证明真实事实正确吗？（只能证明有限 toy extractive 合同。）

## Part 4：Markdown replay

坑：

在完整原始 fragments 上识别 complete positive markers，跨 fragment 的标记也有效；只选择实际使用的 source，去重并保持首次出现顺序。unknown label 拒绝，不能静默丢弃；没有标记时返回空附录。Markdown appendix 以两个 LF 开始，每条 footnote 使用给定 helper 保留原始 metadata，末尾恰好一个 LF。

原始 fragments 的逐片回放、空 fragment 位置、完整 body 收集、附录调用和 early-close ownership 都正确 GIVEN；这些是集成护栏。候选只实现同步 citation_appendix，不编写消费或发布循环。本题不是 NDJSON provider protocol。

H1 "Which sources did the answer actually cite?" H2 "Can a marker cross fragments?" H3 指向完整 marker 集合、首次引用顺序与 Markdown 附录边界。追问：为何需要等完整 body 后附 footnotes？（本题只承诺最终引用集合，而非有界缓冲或在线语法识别。）

## Part 5：boundary-first recursive chunks

坑：

给定 section→paragraph→sentence 边界。完整 unit 能放下就保留 raw interval，包括 oversized section 内本可放下的多句 paragraph；否则递归 children；只有超大 leaf 才用给定 token spans 做连续窗口，保留最后不足一窗的尾部。重复 paragraph 用自己的 offset，不用 text.find。metadata 向下继承，heading 文本不重复插入；原非空白 tokens 恰好一次，原空白间隙可排除。该有限 tree/parser 是 docs recursive chunking 的显式教学实现，非源代码中已有树算法。

H1 "What is the largest unit that already fits?" H2 "Which interval identifies this repeated paragraph?" H3 指向原始 byte spans 和 leaf-only fallback。追问：为何 whitespace gaps 不要求覆盖？（合同要求 token coverage 与每条 raw slice，不要求把分隔空白放进邻居 chunk。）

## 记录

填写各关解锁、变绿、提示、澄清与代码取舍；不要用本地 timing 声称真实服务 latency 或人类 60 分钟难度已验证。

最终完整三慢三快：slow 0.409298, 0.403860, 0.408013 秒；fast 0.003081, 0.003044, 0.002979 秒；限值 0.045 秒，双侧最小余量 8.97 与 14.61 倍。48 documents×384words、180terms、8 个完整 query；来源 fit 只在初始 replacement 外部准备，两侧计时均保留所有 query 输出。详见 SCOPE 的真实外部证据路径。


## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，原测试通过即得 |
| 调试方法 | 20 | 读 traceback、追踪原始 identity 和 generation、一次验证一个假设 |
| 代码质量 | 15 | 保留正确消费者与必要工作、命名清楚、无残留死代码 |
| 沟通 | 15 | 先澄清精度、证据和边界合同，再解释取舍 |
| 工程判断 | 10 | 说明 snapshot 事务、来源坐标、资源关闭和有限 toy 算法的限制 |

每项记录具体观察证据，没观察到的写“未观察”。提示次数和每关用时单独记录；60 分钟未经真人校准。
