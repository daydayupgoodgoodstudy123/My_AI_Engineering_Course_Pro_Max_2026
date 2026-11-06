# 面试官手册：HybridMem（14/09）

候选人计时期间不要看。候选人手里只有 README、`hybridmem/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 抽取器和 embedding 模型都是测试里的替身（按脚本返回），不联网。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 用户自己在别的 session 里的 session 记忆能看到吗？ | "No. A session memory stays in its session. User memories go across sessions." |
| 1 | agent 记忆是不是用同一个 agent 的人都能看到？ | "No. Every memory belongs to one user. An agent memory also needs the same agent_id." |
| 1 | search 要不要也查 KV？ | "No. search is the vector path. recall in fusion.py is the one that reads all three stores." |
| 1 | 重复声明当前事实时，要不要更新时间或者 rid？ | "No. The edge keeps its valid_from and its rid. Nothing changes." |
| 1 | 被作废的边能删掉吗？ | "No. Close it and keep it. We answer questions about the past from it." |
| 1 | 有没有多值关系？比如一个人有好几个项目。 | "Not in this service. One current object per subject and relation." |
| 2 | 第二次 save 是追加还是覆盖？ | "Replace. The file holds what the memory held at the moment you saved." |
| 2 | last_read 也要存吗？ | "Yes. Every field of a record reads back exactly." |
| 2 | 表结构有规定吗？ | "The columns the export job reads, and their types, are in the module docstring. Keys are your call." |
| 2 | 要考虑并发写或者保存到一半崩溃吗？ | "One writer. The tests don't cover a crash mid-save. Tell me what you would do." |
| 3 | 查询文本是空的怎么办？ | "Then the vector store finds nothing. KV and graph can still hit." |
| 3 | 同一条记录被两个存储找到？ | "Take the larger relevance. Don't add them up." |
| 3 | 权重加起来不是 1？ | "Use them as they are." |
| 3 | halflife_s 是 0？ | "Recency is off: 1.0 for every record, as in Mem0Config." |
| 3 | 哪些记录算被读过？什么时候标记？ | "The ones you return. Mark them after every score is in." |
| 3 | scope_weights 里没有的作用域？ | "Not searched." |
| 4 | 要表头吗？ | "No header. The audit file is appended to." |
| 4 | 置信度正好等于阈值？ | "It passes. Below means strictly less." |
| 4 | 已经成立的事实也占上限的名额吗？ | "Yes. Keep the max_edges most confident first, then skip the kept ones that already hold." |
| 4 | 边全被丢掉的消息，本身还存不存？ | "Yes. Every message becomes a record. Only the edges are gated." |
| 4 | 消息也算进重嵌入的计数吗？ | "No. Lookups only." |
| 4 | 重嵌入以后使用次数怎么办？ | "It starts again from zero for the records you re-embedded." |
| 5 | valid_to 那一刻边还算成立吗？ | "No. Half-open: from valid_from up to, but not including, valid_to." |
| 5 | 路径能重复经过一个节点吗？ | "No." |
| 5 | 能反着走边吗？ | "No. Subject to object only." |
| 5 | source 和 target 是同一个节点？ | "Not covered. Tell me what you would return." |

## 每关：要看什么、提示、追问

### Part 1 修作用域检索和图存储（目标 12 分钟）

一个测试里叠了 5 个缺陷和几个护栏：

1. `Mem0.search` 交给向量库的可见性谓词（`where=visible`）只挡住“别人的 user 记忆”：bob 的 session 和 agent 记忆、ava 自己在别的 session 和别的 agent 下的记忆，都会混进来。错误不在 `search` 里报出来，而是一层之外，在 `memory_block` 的护栏里报 `ScopeLeak: m004 (agent memory of bob) reached ava's prompt`。课里说的 “the assistant told Alice about Bob's project” 就是这个。完整的规则已经写在 `Viewer.can_see` 里，把它交给 `where` 就行。
2. 谓词修好以后，报错换成 `ScopeLeak: m002 (session memory of ava) reached ava's prompt`。m002 是 ava 在 s1 的登录码，和 “acme plan” 一个词都不沾，不是向量库找到的：`search` 在向量命中之后，又把 `kv.by_user(viewer.user_id)` 的每条记录以固定的 relevance 0.4 加进候选，这是课里 `code/main.py` 的 KV 兜底（测验 Q8）。docstring 写明 search 只走向量路径，和查询没有共同词的记忆不会出现。只给兜底补上 `can_see` 不够：“refund invoice” 和谁都不沾边，兜底照样把 ava 的 m001 带回来，分数 0.56，报 `a query that matches no memory finds nothing`。这段循环要整个删掉。
3. `add_edge` 对“重复声明当前事实”也照样作废旧边、再追加一条：历史里多出一段 [3000, 4000) 和一条重复的 lisbon 边。应该只在 object 不同时作废；相同时什么都不改，返回已有的边。
4. `current()` 每次都从头扫所有边，`add_edge` 每次写入都要调它。2.4 万条边的快照上做 4000 次冲突写入，本机约 1.3 秒（负载高时 2 秒多）；按 (subject, relation) 建索引后约 1.5 毫秒。
5. 建了索引以后，`restore()` 也要维护它。快照里加载的边不在索引里，`current()` 查不到，冲突写入就不会关闭旧边，报 `every write closes the edge it contradicts, restored ones too`（28000 条有效边，应该是 24000）。
6. 护栏：30 个别人的“退款已批准”比 ava 自己那条更像查询，而且都是 session 记忆，起始代码那个谓词也放得过去。过滤要留在截断之前（`where` 是存储层的预过滤），这一条看修的时候有没有把它挪走：取回以后再过滤、把候选池放大，或者留着 `where=visible`、在循环里再补一道 `can_see`，ava 自己那条都会被挤掉，过不了 `a caller's own memories are found however many others match better`。只在 `memory_block` 里把泄漏的记录跳过也不行，`search` 自己的结果里照样有别人的记忆。
7. 护栏：被作废的边只关闭、不删除。为了提速直接删旧边，或者只留一个“当前边”的 dict，都过不了 `a contradicted edge is closed, not deleted`；“同一事实见过就不再写”过不了 `an old fact can come back`（ava 搬回 berlin）；只按 subject 建索引过不了 `each relation has its own current edge`；重复声明时改 `valid_from`、改 `rid`、换成新的权重或返回 None，都有对应的断言。

看什么：读到 ScopeLeak 时，是去找“谁把这条记录交给了 memory_block”，还是把护栏改成跳过；有没有先打印 `search` 的结果，看每条的 user、scope 和分数；修可见性时是用已有的 `Viewer.can_see`，还是又手写一套只管一部分的条件；第二次 ScopeLeak 时，是看出 m002 根本不是向量库找到的，还是给兜底再补一个条件。

提示：
- 作用域那一层：H1 "Which records does search hand to memory_block, and which of them may ava see?" H2 "Read Viewer.can_see, then the predicate search gives the vector store." H3 直接指出 `visible` 那个内部函数。
- 兜底那一层：H1 "Does m002 share a word with 'acme plan'? Then which store found it?" H2 "Read the docstring of search: which records can be candidates?" H3 直接指出 `kv.by_user` 那段循环。
- 30 条退款那条护栏：H1 "How many candidates does the vector store give search, and whose are they?" H2 "Look at the parameters of VectorStore.search."
- 重复声明那一层：H1 "What should happen when the object that already holds is asserted again?"
- 计时那一层：H1 "How many edges does one add_edge look at?" H2 "What would let current() answer without a scan?"
- restore 那一层：H1 "Which methods put edges into the store?"

追问：
- "Why not just filter in memory_block?"（那是最后一道防线；search 的结果还给 Part 4 的使用计数用；而且先截断再过滤，用户自己的记忆照样会丢。过滤要在存储层做，生产上就是向量库的 metadata 预过滤或按用户分 namespace）
- "The fallback was there so that KV facts always show up. How should KV hits get into a search?"（只查查询理解解析出来的 (fact_type, entity) 键，命中给满分，没命中就不加，测验 Q10 就是这么写的，也就是 Part 3 的 recall。固定分数的兜底让和查询无关的记录压过真正的匹配，而且查什么都不会返回空）
- "A user has two million memories. What does where= cost?"（谓词要能下推到索引；按用户分片；ANN 的带过滤检索）
- "Relations here are single-valued. owns_project is not. What changes?"（关系要有基数：多值关系不做冲突检测，只去重。课里说的是 “contradicts”，第二个项目并不和第一个矛盾）
- "Graph nodes are bare strings. Two users are both called ava?"（节点要带命名空间，比如加 user_id 前缀，否则一个人的写入会作废另一个人的边）

### Part 2 SQLite 三存储（目标 12 分钟）

坑：
- 边没有自然键，不能以 (subject, relation, obj) 做主键或唯一键：ava 搬回 lisbon 以后，历史里有两条 (ava, lives_in, lisbon)，一条已经关闭、一条还成立。唯一键在第二次 save 时直接报 IntegrityError；INSERT OR REPLACE 不报错，但已经关闭的那条被删掉了，读回来的历史少了一段。
- 记录和边都按写入顺序读回：bob 的那条记录来自时钟慢的节点，ts 比 m001 还早；还有一条倒填日期的边。按 ts 或 valid_from 排序都会挂，要靠自增列或 rowid。
- 时间戳不能转成 ISO 8601，也不能取整到微秒：第二条记录的 ts 是 1.7e9 再加 2⁻²² 秒，比一微秒还细。
- KV 表只存 rid，读回时要指向 vector store 里的同一个 Record 对象，不能各拷一份（Part 3 刷新 last_read 时两边要一致）。
- 第二次 save 要替换文件里的内容：不清表的话 seq 主键冲突；INSERT OR IGNORE 不报错，但留下了旧的 valid_to 和 last_read。
- rid 计数要恢复，否则重开后的第一条新记录又叫 m001。用 `MAX(rid)` 做字符串比较，过了 m999 会得到 999，下一条撞上已有的 m1000；`ORDER BY rid` 也会在 m1000 处把顺序打乱。
- 导出任务直接读表：kv 每个键一行；还成立的边 valid_to 是 NULL（写成 0 会让导出以为它已经关闭）；列名照模块 docstring。
- 读回来的图要能接着用：`restore()` 要维护 Part 1 加的索引，否则重开后搬回 lisbon 不会关闭 porto。
- `load` 要把传进来的 clock 交给新的 Mem0。漏掉的话，重开以后写的记录用的是真实时间，报 `a loaded memory runs on the clock it was given`。
- tags 是有序元组。用逗号拼接会把空元组读回成 `("",)`，还会把 `"refund, approved"` 拆成两个；JSON 读回来是 list；排序会改掉顺序。
- 列类型照模块 docstring 写，浮点列都是 REAL。测试的 `exact()` 区分 1 和 1.0，整秒的 ts（1700000000.0）和权重 1.0 是顺带的检查：不照 docstring、声明成 INTEGER 或 NUMERIC 的话读回来是 int，声明成 TEXT 读回来是字符串。
- Python 的 sqlite3 在 INSERT 时自动开事务，不 commit 的话关闭连接就丢数据。建表不写 `IF NOT EXISTS`，第二次 save 会报 `table records already exists`。

追问：
- "The process dies halfway through save. What's on disk?"（参考实现的 DELETE 和 INSERT 在同一个事务里，SQLite 的回滚日志保证要么是旧的、要么是新的；也可以写临时文件再 `os.replace`）
- "Saving everything every time is O(n). When does that matter?"（记录多了以后改成增量写：新记录 INSERT，关闭的边 UPDATE valid_to，last_read 批量 UPDATE。到那时 INSERT OR IGNORE 这类陷阱就是真问题了）
- "Why derive the rid counter from the data instead of storing it?"（没有删除时两者等价；一旦允许遗忘，从数据推算会复用 rid，要单独存计数器）
- "A user asks to be forgotten. Mem0g says never delete. Now what?"（作废是为了冲突检测和审计；用户的删除请求是另一回事，要真删，三个存储、快照和备份都要删）

### Part 3 融合打分（目标 14 分钟）

坑：
- 向量相关度是词频向量的余弦。照抄课里 `VectorStore.search` 的 Jaccard，或者按集合算余弦，排序都会变。分词用 `memory.tokens`。
- 一条记录被几个存储同时找到时取最大，不是相加，也不是谁先到或谁后到算谁的。lease 同时被向量（0.27）、KV（1.0）和两条图边（0.75 和 0.5）找到，相关度是 1.0。
- 图：只用现在成立的边，subject 或 object 是查询实体都算，相关度是边的权重，同一条记录的几条边取最大。图节点不分用户，bob 的 `works_on acme` 也连着 acme，必须过 `can_see`。
- KV 用 viewer 的 user_id 拼键；session 记忆也要过 `can_see`：s1 里的 wifi 密码不能出现在 s2 的结果里。bob 也有一个 `("landlord", "flat")` 键：按 (fact_type, entity) 扫所有用户的 KV、又不过 `can_see`，就会把 bob 的租约带出来。
- `scope_weights` 里没有的作用域不搜（这次没有 agent），作用域权重乘整个分数，不只乘 relevance。
- 权重原样用：0.5 + 0.25 + 0.5 加起来是 1.25，不归一化。
- recency 是半衰期 `0.5 ** (age / halflife_s)`，不是 `exp(-age / halflife_s)`；age 从最后一次读或写（`Record.touched`）算起，不能只看 ts，也不能有 last_read 就只看 last_read；时钟走在前面的节点写的记录 age 记 0；halflife 为 0 时 recency 是 1.0（和 `Mem0Config` 一样）。
- 返回的记录要标记为已读，但要等所有分数算完。先刷新再打分，所有候选的 recency 都成了 1.0。只刷新返回的那几条，不改 ts。第二次查询（top_k=4）专门看刷新有没有生效、是不是只刷新了返回的。
- 空文本照样能查 KV：余弦要先看点积是不是 0，否则 `|q| = 0` 会除零。
- 并列按 rid 升序：lease 和 carol 恰好都是 0.8125；两条一样的 “call the landlord” 被 KV 键按相反的顺序找到，只按分数的稳定排序会选错。
- 顺带检查（Part 1 删 KV 兜底时已经考过）：只有被某个存储找到的记录才是候选，牙医预约、“住过柏林”这种和查询无关的记录不能进来。

追问：
- "How would you tune the three weights?"（带标注的查询集，离线算 recall@k 或 MRR，网格搜索。课里说按产品调：聊天加 recency，合规加 importance，检索加 relevance）
- "A record with importance 0.9 and nothing to do with the query beats real matches. Fix?"（relevance 低于阈值的不进候选；或者先按 relevance 召回，再用 importance 和 recency 重排；或者用 RRF 这类按名次的融合）
- "Why must the graph path check visibility when the KV keys already carry user_id?"（图节点是全局字符串，可达子图会穿过别人的边；“把 Bob 的项目告诉了 Alice”在图上最容易发生）
- "recall writes last_read on every query. What does that cost in a real store?"（读变成了写；批量、异步写回，或者只在 recency 有明显变化时写）

### Part 4 写入审计（目标 12 分钟）

坑：
- 输出格式由测试里的 `csv.reader` 决定。object 里有逗号（`Lisbon, Portugal`、`1,70 m`）、双引号（`pastel de "nata"`）和换行（两行的地址），要用 csv 模块写；手拼字符串会多出列或者多出行。每个 yield 恰好一行，带换行符，没有表头。
- 阈值：正好等于 min_confidence 的（`owns dog`，0.5）算通过，参与上限的竞争，这里记的是 `over_cap`。低于阈值的不管排第几，原因都是 `low_confidence`：`height` 0.3 排在第二个，按“先截上限”写会记成 `over_cap`。
- 上限：按置信度降序保留 max_edges 条，并列取抽取器先列出的。三条 0.7 里保留 role 和 based_in，丢 likes。`owns dog` 列在 role 前面，只取前 max_edges 个通过阈值的候选（`passing[:max_edges]`）会留下 owns、丢掉 based_in。`sorted(...)[-N:]` 取升序的尾巴、`key=(conf, i), reverse=True` 都会选错。
- 已经成立的事实也占上限的名额：seq 6 的四个候选里按置信度留下 lives_in、country、city，lives_in 已经成立，记 `skip, restated`；likes 排第四，记 `over_cap`。先把已经成立的剔出去再截上限，likes 就会被写进图。
- 行按抽取器给的顺序输出，不是先写保留的、再写丢掉的。
- 冲突是 `write, conflict`，紧接着一行 `invalidate, superseded`，写的是被关闭的那条旧边。
- 没有候选的消息（“thanks!”）也要存成记录，否则后面的 rid 全部错位，重嵌入那几行对不上。
- 重嵌入只数 lookup，不数 message；每 3 次一轮；按使用次数降序、并列按 rid，至少用过一次；重嵌入以后计数清零，清零在写完这一行之后。`Counter.most_common` 并列时按第一次出现的顺序，会把 m004 排在 m001 前面；第二轮只有两条记录被用过，`most_common(3)` 还会带出一条计数为 0 的。
- 使用次数来自 `mem.search` 返回的记录（viewer 能看到的、top_k 以内的）；直接用 `vector.search` 会把 ava 的记录算进 bob 的查询。
- 边要真的写进图：权重是置信度，rid 是这条消息的记录；被丢掉的候选不能写进去。
- 每一行决定了就 yield：探针在只拉了一个事件时就要拿到第一行。先把整个流读完再处理，测试会数出拉了 13 个事件。
- 骨架是 `async def` 里只有 raise，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要看出这里需要 async generator。

追问：
- "The extractor proposes 50 edges per message. Is a cap of 5 enough?"（上限只防爆炸，不防错误；还要关系白名单、去重，低置信度的事实可以只写向量、不写图。课里的 KV schema creep 也一样，要定期审计 type 集合）
- "Re-embedding is an API call that can fail or be slow. Where does it go?"（不放在请求路径上：排队、批量、限速，失败的下一轮再试；每条记录记下是哪个模型版本嵌入的）
- "Why an append-only CSV for the audit, not just a table?"（审计要只追加、能交给外部核对；CSV 方便合规导出。放进表里也行，再加哈希链防篡改）
- "Two workers write messages for the same user at the same time."（冲突检测要串行：按用户分区的队列，或者数据库层的条件更新）

### Part 5 时点图查询（目标 10 分钟）

坑：
- 半开区间 `[valid_from, valid_to)`：搬家那一刻（MAY）住的是 lisbon，不是 berlin；`valid_from` 那一刻已经成立。写成 `<=` 或者 `<` 都会在边界上错。
- 回答过去的问题不能看 `edge.valid`（现在是否成立）：berlin 现在已经关闭，但三月时成立。忽略 `valid_from` 会让后来才有的边漏进过去（一月以前也说住在 berlin）。
- 每一跳都要在那一刻成立：四月 globex 的客户经理已经换成 dave，经过 carol 的那条路就断了。只在第一跳检查时间，四月的答案会多出路径。
- 简单路径：不重复经过节点（ava → bob → ava 是环）。不能用一个全局的 visited：先走过 globex 以后，`ava -partner_of-> globex` 那条路就丢了。也不能按节点序列去重：同样经过 ava、globex、carol，`customer_of` 和 `partner_of` 是两条路。
- 要全部路径，不是最短的或者最好的一条；找到一条进入目标的路以后还要接着搜。
- max_hops 数的是边：默认 3 跳，4 跳的 `ava -manages-> bob -knows-> dave -knows-> erin -knows-> carol` 不算。
- 排序：权重乘积降序；权重相同时跳数少的在前（1 跳的 mentors 排在 3 跳的前面）；再按每一跳的 (relation, object) 字母序（customer_of 排在 manages 前面）。只按权重的稳定排序，结果是搜索的顺序。
- 有向：边只从 subject 走到 object，carol 到 ava 没有路。
- 测试分不出、可以接受的写法：排序只比 relation、不比 object（关系是单值的，同一时刻从一个节点出去的边 relation 各不相同，两条路分叉的那一跳 relation 一定不同）；到了目标还接着往下搜（简单路径回不到目标，只是白做）；`value_at` 取 valid_from 不晚于那一刻的最后一条边（同一个 (subject, relation) 的区间首尾相接，结果一样，遇到倒填日期的写入才会不同）。

追问：
- "The graph has a million edges. paths() looks at all of them for every query."（按时间建索引：每条边一个区间，用区间树，或者按 valid_from 排好后二分；邻接表按 subject 建）
- "The number of paths explodes. What bounds it?"（max_hops、每个节点的扇出上限、按权重剪枝（乘积低于阈值不再展开）；只要前 k 条时用最佳优先搜索）
- "Exercise 2 asks for search(query, as_of=t). Which store needs the most work?"（向量库最难：embedding 没有时间语义，要给每条记录加有效区间并在检索时过滤；KV 要从“键对值”变成“键对带时间的版本”；图有了区间以后最自然）
- "What does a path weight mean when the weights are extractor confidences?"（把它们当作独立事件的概率相乘只是近似；同一个抽取器的错误往往是相关的）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出存储层预过滤、作废与删除、增量持久化、读放大、审计、时间索引 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
