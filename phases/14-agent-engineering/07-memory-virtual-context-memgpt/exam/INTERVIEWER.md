# 面试官手册：memgpt（14/07）

候选人计时期间不要看。候选人手里只有 README、`memgpt/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 存进 archival 的事实算第几轮？ | "main.turn: the number of the latest message in the conversation." |
| 1 | old 出现了两次，替换第一处可以吗？ | "No. Refuse it and change nothing. The agent can quote more of the text." |
| 1 | 重叠出现（在 "ha ha ha" 里找 "ha ha"）算一次还是两次？ | "Your call. Say what you chose. The tests don't cover it." |
| 1 | 最新一条消息自己就超预算怎么办？ | "It stays. Everything older goes to recall." |
| 1 | core 段算进 max_tokens 吗？ | "No. Core sections have their own caps. max_tokens is the summary plus the messages." |
| 1 | 提速时能顺便把打分换成 BM25 吗？ | "Not here. Same scores, same order, only faster. BM25 is Part 3." |
| 2 | 表结构有规定吗？ | "Only that turn_id is an INTEGER column, as the module docstring says. Keys and the other columns are your call." |
| 2 | 删掉的 id 能再发出去吗？ | "Never. Old answers cite ids, and a reused id would point them at a different fact." |
| 2 | tags 要不要去重、排序、转小写？ | "No. Store them exactly as given, in order, as a tuple." |
| 2 | 可以软删除吗？ | "Your call, as long as get, records and search stop seeing it and its id never comes back." |
| 2 | 要支持多个写入者吗？ | "One writer. Other connections may open the file and read at any time." |
| 2 | 内存里也留一份记录可以吗？ | "Yes. SqliteArchive is an ArchivalStore. get, records and search behave the same." |
| 3 | 分词能不能顺便去掉标点？ | "No. Use tokens.tokenize, punctuation and all. Otherwise you're comparing tokenizers, not scorers." |
| 3 | 查询里重复的词算几次？ | "Every time it appears. It's in the docstring." |
| 3 | k1 和 b 取多少？ | "1.2 and 0.75, the defaults in the signature." |
| 3 | 一个 case 一条结果都没有，recall 怎么算？ | "Zero for that case, and it still counts in the mean." |
| 3 | 相关记录比 k 多时，分母用 k 吗？ | "No. It's the number of relevant records, so one of two found at k = 1 is 0.5." |
| 3 | 没有相关记录的 case 能跳过吗？ | "No. Raise ValueError. A case with nothing to find is a broken case." |
| 3 | 插入新记录以后 BM25 要跟着更新吗？ | "No. It's built over a fixed list. Build a new one." |
| 4 | 摘要算一条消息吗？ | "No. It's ctx.summary, shown above the messages. It counts toward max_tokens." |
| 4 | 超过警戒线以后每条消息都报 memory_pressure 吗？ | "No. Only when a message takes the context from below warn_tokens to warn_tokens or more." |
| 4 | 一次挤出多少？ | "Oldest first, and only until it fits. Then summarize. If the new summary pushes it over again, page out more." |
| 4 | 最新一条消息自己就超预算？ | "It stays. Page out everything older, then move on to the next message." |
| 4 | 能先挤出再报 memory_pressure 吗？ | "No. The pressure report is the agent's chance to save what's about to leave." |
| 5 | 上限按字节还是按字符？ | "Characters. len() of the str." |
| 5 | 同时超了好几层，报哪一层？ | "The innermost one." |
| 5 | group 自己能写文字吗？ | "No. That's a TypeError." |
| 5 | append 时加的那个空格算不算？ | "Yes. It's part of the text." |
| 5 | 路径区分大小写吗？ | "Yes. Names match exactly." |

## 每关：要看什么、提示、追问

### Part 1 修记忆工具（目标 12 分钟）

一个测试里叠了 4 个缺陷和两组护栏：

1. `MemoryTools.archival_memory_insert` 调 `ArchivalStore.insert` 时只传了 `tags`，`session_id` 和 `turn_id` 都是默认的 `"s0"` 和 `0`。错误不在 insert 报出来，而是在后面 `archival_memory_search` 的输出里：每条结果的引用都是 `[s0#0]`。这就是课里说的 citation loss。
2. `core_memory_replace` 用 `str.replace` 替换所有出现。core 里是 `name=ava, stack=java`，把 `ava` 换成 `eva`，`java` 也变成了 `jeva`。docstring 规定 old 必须恰好出现一次，否则返回错误、什么都不改。改成按整词匹配（`\bava\b`）也会挂：docstring 说的是子串，`java` 里的 `ava` 也算一次出现。
3. `MainContext.tokens` 把所有消息拼成一段再估算，等于 `ceil(总词数 × 1.3)`；docstring 规定每条消息单独估算再相加。三条两个词的消息，分开算是 3 + 3 + 3 = 9，拼起来算是 ceil(7.8) = 8，预算是 8 时就少挤了一条。
4. `ArchivalStore.search` 每次查询都把每条记录重新 `lower().split()` 一遍。2 万条记录、150 次查询，本机要 1.4 秒左右。只在插入时预分词、查询时仍然全表扫描，也要 0.17 到 0.21 秒，过不了 0.08 秒的限值；要建倒排索引（token → 记录位置），只给包含查询词的记录打分，约 4 毫秒。
5. 护栏，主上下文：恰好等于 max_tokens 的上下文不挤；最新一条消息永远留下，哪怕它自己就超预算；被挤出的消息进 recall，`conversation_search` 还能找到；core 段不算进 max_tokens，`small` 带着一个 core 段，算进去的话 `tokens()` 是 8 不是 6。
6. 护栏，检索：分数必须和原来完全一样（按 `tokenize` 切出、去重后的 Jaccard），并列按插入顺序。常见的改坏方式：倒排表里一条记录按出现次数记了好几次；查询不去重；顺手去掉标点；换成别的打分；候选放进 set 再只按分数排，或者用 `heapq.nlargest` 只按分数取；按 rid 字符串排并列；按 turn 排并列（turn 是每个会话自己的编号，同一条事实在 s1 是第 9 轮、在 s3 是第 2 轮）；按文本去重，把两个会话里的同一条事实合并成一条。

看什么：是不是从 `[s0#0]` 倒推到写入的地方，而不是去改 search 的格式；修 replace 之前是不是先想清楚“出现两次”该怎么办；提速之前是不是先说清楚哪些结果不能变。

提示：

- H1："Where do session_id and turn_id get their values?"
- H2："Work out small.tokens() by hand, message by message, and compare."
- H3：直接指出 `archival_memory_insert` 没有转交 session 和 turn；`tokens()` 是拼起来估算的；search 需要倒排索引。

追问：

- "Why does every archival write carry a session and a turn?"（课里的 citation loss：回答要说得出是哪一轮说的；纠错、删除和审计也靠它）
- "run_scripted_agent checks the tool name against a list. What goes wrong with a plain getattr?"（模型的输出是不可信输入；`getattr` 会把 `main`、`__init__` 这类属性也当成工具，调一次 `__init__` 记忆就清空了）
- "1.3 tokens per word. Where is that badly off?"（代码、URL、不用空格分词的中文：`简体中文` 按空格只算一个词；生产里用模型自己的 tokenizer 计数）
- "Your index stores positions. What happens when a record is deleted?"（位置会错位；用 rid 做键、留墓碑，或者像 Part 2 那样删除后重建）

### Part 2 SQLite archival（目标 10 分钟）

坑：

- 删掉的 id 不能再发出去。删除最新的 a003 后重开再插入，必须是 a004。`INTEGER PRIMARY KEY` 不加 `AUTOINCREMENT` 时，SQLite 用当前最大的 rowid 加 1，又发出 a003；`COUNT(*) + 1`、`MAX(seq) + 1` 和只记在内存里的计数器（重开后从 0 开始）也会重用旧 id。理由来自领域：旧答案引用过 a003，重用以后这个引用就指向了另一条事实。
- 往返完全一致：tags 是有序元组，读回 list、排序后存、转小写、用逗号拼接都不行（`lang:zh-Hans,en` 里本身有逗号和大写字母，空 tags 用逗号拼接会读回 `("",)`）；text 原样保存，非 ASCII、换行和结尾的空格都在，不能 strip。测试数据里没有重复的 tag，去重抓不到；看到候选人去重或者问到时，按澄清问题的回答说明不能去重。turn_id 列声明成 INTEGER 是模块 docstring 规定的，测试只是顺带按类型核对一下，不算这一关的坑。
- 每次 insert 返回时就已经提交。测试在第一个连接还开着时另开一个连接去读，只在 `close()` 里 commit 也会挂。delete 也要提交：不提交的话，关闭连接时删除被回滚，重开后 a003 又回来了。
- 打开文件时要把记录装回内存，`get`、`records`、`search` 才看得到；装回时要经过 `_keep`，否则 Part 1 的索引是空的。
- 插入顺序：超过 a999 以后是 a1000，按 rid 字符串排序会把 a1000 排到 a998 前面。按 turn_id 排也不对，turn 是每个会话自己的编号，a001 是 s7 的第 21 轮，a002 是 s8 的第 12 轮。要按自增列排。
- `delete` 未知 id 报 KeyError；删除后 get 和 search 都看不到。只从列表里删掉、不更新 Part 1 的索引，倒排表还指着旧位置，search 会报 IndexError 或者返回别的记录。
- 建表要写 `IF NOT EXISTS`，否则第二个连接打开时报 `table archival already exists`。

追问：

- "Archival memory is supposed to be unbounded. Where does this design stop scaling?"（内存里镜像了全部记录；数据大了要在库里建索引，比如 FTS5 或向量库，查询时只取 top-k）
- "A web page the agent read says 'ignore all previous instructions', and it gets stored. What would you store next to it?"（课里的 memory poisoning：记来源和信任级别，检索结果作为数据交给模型，不当作指令）
- "Two agent processes write to the same file?"（SQLite 的写锁会把写入串起来，AUTOINCREMENT 保证不重号；并发再高就换数据库）

### Part 3 BM25 与 recall@k（目标 12 分钟）

坑：

- 分词和 archival 一样，用 `tokens.tokenize`：转小写、按空白切、标点留着。`drift,` 不是 `drift`。换成正则分词，比较的就不只是打分方式了。
- IDF 用 `ln(1 + (N - n + 0.5) / (n + 0.5))`。经典的 `ln((N - n + 0.5) / (n + 0.5))` 对出现在一半以上记录里的词是负数：`tool` 在 5 条记录里出现了 4 条，分数变成负的，就被过滤掉了。
- N 和 avgdl 算上每一条记录，空记录也算。只有一条记录时 avgdl 就是它自己的长度。空库或全是空记录时不能除零：只在词命中时才算长度归一化，或者先判断。
- tf 是词在这条记录里出现的次数；n 是包含这个词的记录数，不是它的出现总次数。
- 查询里重复的词每次都算，docstring 写明了：`drift drift` 的分数是 `drift` 的两倍。用 `set` 去重会挂。
- 只返回分数大于 0 的记录，最多 top_k 条；分数相同按传入的顺序。对 (分数, 位置) 元组用 `sort(reverse=True)`，平局的顺序会反过来。测试还把 TINY 倒过来建了一次 BM25，并列的 a005 要排在 a002 前面，按 rid 排并列会挂。
- recall@k：每个 case 是“前 k 条里找到的相关记录数 / 相关记录数”，每个 case 都算进平均，一条结果都没有的算 0。按“找到一个就算 1”、除以 k、除以 min(k, 相关记录数)、跳过没有结果的 case，结果都不对：`what is the plan for the bot` 有两条相关记录，k=1 时找到一条就是 1/2。
- 调用 search 时要传 k。不传 k 的话，archival 的 search 默认只给 3 条：recall@1 会多看两条；先取 3 条再截到 k，到 recall@5 就只有 6.5/9，应该是 8/9。
- 没有相关记录的 case 报 ValueError，混在正常 case 里也一样，不能跳过；空的 case 列表也报 ValueError。
- 这套事实上，词重叠基线的 recall@1 是 4/9，BM25 是 7/9；recall@3 是 6.5/9 和 8/9；到 recall@5 两者都是 8/9。差别主要来自 IDF：`what is the deploy target` 在基线下排第一的是 `it is what it is`。

追问：

- "Which case does neither method find, and why?"（`which cloud do we use`：相关记录里一个查询词都没有。BM25 还是字面匹配，这种要靠向量检索或混合检索，见第 09 课）
- "'it is what it is' still ranks first for 'what is ava building and what does she prefer'. Why, and what would you change?"（查询里 `what` 出现两次，每次都算；整个库里只有这条记录有 `what`，IDF 最高；这条记录又短，`is` 还出现了两次。可以去掉停用词，或者给查询词频加饱和）
- "At k=5 token overlap catches up with BM25. Why bother with BM25?"（主上下文的预算有限，每次只能把前几条换进来；排在前面的质量才是关键，所以要看小 k）
- "recall@k, precision@k, MRR: which would you watch for agent memory?"（看用途：要找得回来看 recall@k，要第一条就对看 MRR）

### Part 4 中断式分页（目标 14 分钟）

坑：

- 输出格式由测试决定：每个事件一行 JSON，以 `\n` 结尾，一次 yield 一个事件。缺换行报 Extra data，多一个空行报 Expecting value，`indent=2` 在逐行解析时也会挂。以 `\r\n` 结尾能通过（`splitlines` 认它），可以接受。
- memory_pressure 只在一条消息把上下文从警戒线下面推到警戒线或以上时报一次，恰好等于 warn_tokens 也算。每条超线的消息都报，或者只在挤出过一次后才重新报，事件都会多出来；整个流只报一次，第 8 轮的会漏掉。“下面”是推入这条消息之前的大小，也就是上一条消息挤完、摘要写完之后：拿上一条消息刚推入时的大小来比，第 8 轮的也会漏掉。上下文本来就恰好停在警戒线上时不算跨线，写成 `before <= warn_tokens` 会在边界那段短流里多报一次。
- memory_pressure 要在挤出之前报。这是 agent 的中断：测试收到事件时检查最旧的消息还在上下文里，并把它存进 archival。先挤出再报，或者把一条消息的事件攒齐了再一起 yield，到第 8 轮都会挂。
- 只挤到放得下为止（`MainContext.evict`），挤出的原文进 recall；然后 `await summarize(ctx.summary, paged)` 生成新的摘要。摘要也占预算：第 6 轮摘要从 6 个 token 涨到 16 个，上下文又超了，要再挤一次。只挤一次的话，下一条消息到来时上下文是 42。
- page_out 要在调用 summarize 之前报出去。先等摘要再报，事件内容一样，但测试记下的先后顺序不对。
- 流式：一条消息处理完才拉下一条。测试检查第一次 page_out 时只拉了 4 条。
- 最新一条消息自己就超预算时，挤完更早的消息就继续往下走。循环条件只写“超预算”会一直报空的 page_out；测试只读前 6 行，不会卡住，但写成不 yield 的死循环就会卡住。
- summarize 是协程，忘了 await 会在 `approx_tokens` 里报 `'coroutine' object has no attribute 'split'`。
- Part 1 修 `tokens()` 时如果漏了摘要，到这一关才暴露。

追问：

- "Why report page_out before the summary is written?"（摘要是一次模型调用，可能要几秒；观察者和 agent 应该马上知道哪些消息离开了上下文）
- "The rolling summary lost 'my name'. How would you keep facts like that?"（摘要是有损的；关键事实写进 core 或 archival，这正是 memory_pressure 时 agent 要做的事）
- "summarize takes two seconds and messages keep arriving. What happens here, and what would you change?"（这里是串行的，后面的消息都在等；可以排队、在后台摘要，或者像第 08 课那样交给 sleep-time agent）

### Part 5 类型化 core memory（目标 12 分钟）

坑：

- 写入时从这一段一路往上查到顶层，报最内层超限的那一段，带完整的点路径、上限和写入后这一段的大小。只查自己、跳过文本段自己、只查到父段、从顶层往下查，都会挂。
- group 的用量是它下面所有文本段的总和，不只是直接的子段。把段摊平成以路径为键的字典时，要按 `path + "."` 前缀求和：测试最后用一个小 schema 放了 `human` 和 `human_notes` 两个兄弟段，`startswith(path)` 会把 `human_notes` 的文字算进 `human`。
- append 用一个空格接在已有文本后面，这个空格也算字符：`Ava 林小雨` 接上 `Lewis` 是 13 个字符。空段前面不加空格。
- 上限按字符（`len(str)`）。`Ava 林小雨` 是 7 个字符、13 个字节，name 的上限是 12。
- 恰好等于上限算放得下。
- 被拒绝的写入什么都不改。先写再查、出错不回滚会挂。
- replace 的规则和 Part 1 一样：old 恰好出现一次，否则 ValueError；替换后变长也要查上限。
- 路径：不存在的段报 KeyError，包括 `human.profile..name`、`persona.tone` 和大小写不对的 `Human`；往 group 里写文字报 TypeError。
- render 按 schema 的顺序。课里 `MainContext.render` 用的是 `sorted`，这里不能排序。每一段都要渲染，空的也要；空文本段只有名字和用量，没有冒号。

追问：

- "What changes when core memory goes from flat strings to typed sections?"（课里的练习 5：每段有类型和上限，路径要校验，渲染要稳定；模型看到用量，才知道哪里还有空间）
- "Why characters and not tokens for these limits?"（便宜、确定、和模型无关；token 数换一个模型就变了）
- "The agent hits the human limit. What should it do next?"（把不常用的内容挪进 archival，core 里留一句摘要和 rid）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出规模、并发、出处、失败处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
