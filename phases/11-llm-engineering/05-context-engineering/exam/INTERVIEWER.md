# 面试官手册：ContextLoom（11/05）

候选人计时期间不要看。候选人手里只有 README、`contextloom/` 和 `tests/`。

## 开场（2 分钟）

- 总时长 60 分钟，含开场 2 分钟。请候选人边做边说明想法，可以提问、查官方文档。
- 五关参考时长为 12、12、10、12、12 分钟，合计 58 分钟。记录变绿时间、pytest 次数和提示次数。时间分配未经真人校准。
- 不代写；卡住约 5 分钟后，一次只给一级提示。

## 澄清问题的标准答案

只在候选人问到时回答，用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | score 要跟被过滤的 docs 一起吗？ | "Yes. The selected arrays must remain paired in source order." |
| 1 | 相同 key 的分配是新增吗？ | "No. It replaces one live slot without moving that slot's original position." |
| 1 | query 与 history 谁先得到空间？ | "System and query must remain complete before optional components compete. The final query still appears last." |
| 1 | 历史上限包括 summary 吗？ | "Yes. Count the complete rendered history, including role labels, headers and the rolling summary." |
| 1 | 摘要怎么产生？ | "Use the supplied bounded deterministic rollup. It preserves source ids separately and makes no semantic-quality claim." |
| 1 | 最近两对本身放不下呢？ | "The supplied finalizer raises ValueError. Do not silently remove compulsory recent exchanges." |
| 2 | 旧 revision 还能 append 吗？ | "No. New appends must strictly increase that component's revision, including when the payload is unchanged." |
| 2 | checkpoint 后重见旧 log 呢？ | "Covered older revisions are harmless. A conflicting revision equal to the current live revision is rejected; this is not a historical-integrity audit." |
| 2 | token 字段是什么？ | "An integer estimate of that component's exact stored text. Summary provenance is a separate ordered field." |
| 3 | 首尾指整个 prompt 吗？ | "Only the retrieved block. System and query retain their fixed outer layout." |
| 3 | 同分怎么处理？ | "Keep original input rank. Do not compare component keys or text as hidden tiebreakers." |
| 4 | id 是 component revision 吗？ | "No. It is the increasing session revision, one event per applied update." |
| 4 | 失败后要输出半份 budget 吗？ | "No. Each data record is one complete coherent applied-state snapshot." |
| 5 | parent 的输入是什么？ | "Join its completed child digests in order, then apply its own local budget." |
| 5 | 相同 title 的 section 呢？ | "Keep both. Source identity is the complete key path, not the title." |
| 5 | 短 paragraph 也必须 summarize 吗？ | "No. Keep fitting text exactly, including whitespace." |

## 每关：要看什么、提示、追问

### Part 1 修配对与预算流水线（目标 12 分钟）

四层缺陷：

1. filter 缩短 documents，却携带完整 scores。ContextService.preview 经 build_retrieved，把结果交给正确 emit_scored_components/pair consumer；下游长度合同报 ValueError。源码 zip 本来会静默截断/错配，不会自然报 IndexError，本题明确提供长度检查。
2. 替换 slot 时把旧 allocation 也当作其他占用，导致最终本来放得下的新内容被截断。used 要排除该 slot 的旧值，替换不改插入位置。
3. query 在 optional history 后分配，会被挤掉。先按优先级分配完整 system/query，再让 optional components 竞争，最后按固定布局渲染。
4. 每次移走最旧 exchange 后重新扫描 retained history 的全部字数。正确版预计算每个完整 exchange 的真实 rendered word contribution，再用 running total 扣除。deque、bounded rolling summary、完整计数公式和不可行预算处理已正确给定。

历史计量在完整 rendered words 上只用一次 source `int(words*1.3)`，不是各 turn 先取整再相加。role labels、两个 section headers 与 summary text 都计入。每次实际 summary/provenance 更新和最终渲染都在计时内。

1,200 对完整 exchanges 的三次功能已修慢版约 0.586–0.604 秒，参考版约 0.0028–0.0028 秒，限值 0.06 秒；双侧余量均超过 8 倍。测试同时保留最近两对、全部 summary 来源与最终文本计数，不能靠不生成摘要或不返回内容提速。

提示：H1 "Which arrays reached the pair consumer?"；H2 "What live contribution does a replacement represent?"；H3 指向过滤生产者与同一 slot 的旧 allocation。

追问："Why is allocation order different from display order?"（query 要保留空间，但在最终布局中仍在末尾）；"Can token estimates be added after separate rounding?"（完整 history 应先汇总 rendered words，再估一次）。

### Part 2 component revision log（目标 12 分钟）

坑：

- append 保留历史，replay 只留下每个 slot 的最新 revision，不重复计算旧版本；slot 第一次出现的位置不能变成按 key 排序。重复 append 相同 revision、相同 payload 也要拒绝，且不改变 log。
- checkpoint 是完整有序 live state。重开时先读 checkpoint，再折叠 log；covered older entries 不复活旧内容，与当前 live 值相同版本但不同内容时拒绝；忽略 covered older revisions，不承诺检查全部历史版本间的冲突。
- text、role、revision、integer token estimate、summary provenance 都属于记录。provenance 独立有序，不能从 summary 文本反推。Unicode、CRLF 和空内容原样保留。JSON 可以包含 literal U+2028/NEL；日志只按真实 LF 分 record，不能用 splitlines 把字符串内分隔符拆开。

codec 已正确给定。checkpoint 后清空已覆盖 log；这不是 fsync、原子事务或坏半行恢复练习。

提示：H1 "Are you returning revisions or live slots?"；H2 "Which file contains state after compaction?"；H3 提醒 checkpoint-before-log 与按 key 更新但保持原位置。

追问："What if a checkpoint is visible before log clearing?"（幂等折叠 covered revisions，不能复活旧版本）。

### Part 3 retrieved block zigzag（目标 10 分钟）

P1 没有实现 zigzag；它只提供正确的 budget 与 scored pairing。P3 实现独立 placement TODO。

坑：

- 稳定按 score 排 rank；不能让 tuple sort 顺带比较 Component、key 或 text。同分按输入 rank。
- ranks 1/3/5... 正序在前，2/4/6... 逆序在后。奇偶长度都恰好保留每一项，最高两项处于该 block 两端。
- 不能按重复 text 去重，也不能改 source score。placement 不再次筛选：已选中的零分 component 也必须保留。重排只作用于 retrieved block，system/query 固定布局与 reserve 由修好的 P1 依赖处理。

提示：H1 "Which two ranks belong at the block's ends?"；H2 "Where do the lowest ranks meet for odd and even lengths?"；H3 提醒稳定 rank 与交替方向。

追问："Does this test prove an attention or answer-quality gain?"（不；只验证 source heuristic 的确定性 placement）。

### Part 4 SSE context revisions（目标 12 分钟）

候选人实现同步 `encode_revision(component, session)`：使用当前 update 调用给定的 `session.apply`，投影完整 applied state，再构造一个 SSE event。`encode_revisions` 的完整逐条拉取、发布和 `stream_revisions` 的 source/encoder 关闭都已正确给定，不是待修任务。

坑：

- contents 和 allocations 必须覆盖同一完整 live slot 布局，不能只报告刚更新的 component，也不能按 text 真值丢掉已准入的空内容。selected ids 只列非空 slot，保持该 live 布局的相对次序。
- snapshot 的 reserve 必须保留 session 规定的生成预留；不能把它改成可用输入空间，即使总和仍然看起来一致。used、remaining 与 allocations 来自这次 apply 的同一状态。
- SSE id 是全 session revision，不是各 component 自己的 revision。JSON text newline 应转义，event block 用一个空行结束。

给定 driver 的节奏与 early-close 测试验证集成边界；提前读取和跨 revision 混用 allocations 的错误写法用于核对该 driver。候选人的职责是同步 snapshot 与 SSE 编码。

提示：H1 "Which complete state does this update produce?"；H2 "Do contents, allocations and selected describe the same live layout?"；H3 提醒区分 session revision、component revision 与窗口中的生成预留。

追问："Why not emit only the updated component?"（调用方需要完整 coherent budget，不能自行拼出可能混合 revision 的状态）。

### Part 5 bottom-up document digest（目标 12 分钟）

坑：

- children 先产生 digest，parent 再消费 child digests，不从原始 descendant paragraphs 重新汇总。
- source identity 用完整 key path；重复 section/paragraph title 不合并，leaf sources 按文档顺序保留，key 的字母顺序不改变来源次序。
- 每层用自己的 budget。能放下的 paragraph 字节原样保留；只有超限才调用注入 summarizer。正确 helper 负责拒绝超限 callback 输出。

source 只有 recursive summarization 概念，没有现成 tree algorithm。本题提供明确的 section/paragraph tree，是自然教学扩展；不调用真实摘要模型。

提示：H1 "What does the parent receive after its child is compressed?"；H2 "Are two equal titles the same source?"；H3 提醒 post-order、full path 和 local budget。

追问："Does a fitting digest preserve every fact?"（不证明；这里只验证结构、计量、来源与调用次序）。

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 追踪下游 pair contract，逐层核对 live budget |
| 代码质量 | 15 | 完整记账、稳定顺序、清楚状态与算法边界 |
| 沟通 | 15 | 主动澄清 estimate、priority/layout、revision 与 provenance |
| 生产意识 | 10 | 不可行预算、完整事件、持久化边界与模拟限制 |

每项写具体观察证据，没观察到就写“未观察”。
