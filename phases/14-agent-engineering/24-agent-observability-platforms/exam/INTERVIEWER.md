# 面试官手册：TraceJudge（14/24）

候选人计时期间不要看。候选人手里只有 README、`tracejudge/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 告诉候选人：评审是课里那套脚本化规则（`scripted_llm_judge`），不调用真实的 LLM，也不联网。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 不同 trace 里 span_id 相同，算重复吗？ | "No. Span ids are only unique within a trace." |
| 1 | 重发的那份和第一份内容不一样，留哪份？ | "The first. A retry is the same span sent again." |
| 1 | tokens 会是 "800.0" 这种吗？ | "Not from our exporters. Whole numbers, sometimes written as strings." |
| 1 | eval_score_mean 要按 span 数加权吗？ | "No. Every trace counts once." |
| 1 | 修 tokens 的类型，在 judge 里修行不行？ | "Where else is the token count used?" |
| 2 | 同一个人能给同一个 trace 标两次吗？ | "Yes. Keep both. People change their minds." |
| 2 | 0.0 分和没有分是一回事吗？ | "No. 0.0 means completely wrong. None means they didn't give a score." |
| 2 | 标注按 created_ns 排序吗？ | "No. Annotators' laptop clocks drift. Keep the order we recorded them in." |
| 2 | 已经标过的 trace 再入队，会回到 pending 吗？ | "No. It already has an annotation." |
| 2 | 要支持多个进程同时写吗？ | "Not today. Tell me what you would do." |
| 3 | WARN 算通过吗？ | "No. Only PASS." |
| 3 | 版本号是什么格式？ | "A v, then numbers separated by dots. v1.9, v1.10, v2.0." |
| 3 | max_drop 是相对下降还是绝对下降？ | "Absolute percentage points. 90% to 80% is a drop of 10." |
| 3 | 比 known_good 更早的版本怎么处理？ | "Ignore them. We already know known_good was fine." |
| 3 | 没有版本回归时返回什么？ | "Whatever the docstring says: no culprit, no suspects, and the newest good version." |
| 3 | 浮点比较加个容差行不行？ | "Exactly max_drop points is not a regression, and a tenth of a point more is. Any way that gets both right is fine." |
| 4 | 有个 update 对应的 span 一直不来呢？ | "Drop it after orphan_ttl more batches and report how many you dropped." |
| 4 | create 也会重发吗？ | "Yes. The second create is ignored, even if its values differ." |
| 4 | update 的 ts 比它的 create 还早呢？ | "Same rule. The create's values carry the create's ts, so the older update loses." |
| 4 | 两个事件 ts 相同呢？ | "The one that arrived later wins. The tests don't hit that case." |
| 4 | 未知的 kind？ | "ValueError." |
| 4 | 浏览器断线重连怎么办？ | "Not today. That's what the ids are for. How would you use them?" |
| 5 | span 的父 span 不在这个 trace 里？ | "Treat it as a root. The exporter probably dropped the parent." |
| 5 | 连续三个 chat 要不要折叠成一个？ | "No. Three chats in a row is a different shape from one." |
| 5 | min_share 的分母是什么？ | "All the traces you were given." |
| 5 | 父子关系成环？ | "Corrupt data. Raise a ValueError." |

## 每关：要看什么、提示、追问

### Part 1 修会话看板（目标 12 分钟）

一个测试里叠了 5 个缺陷和几个护栏：

1. `load_spans` 没有把字符串形式的 `tokens` 转成 int，与 docstring 不一致。错误不在加载时报，而是在 `summarize` → `summarize_session` → `scripted_llm_judge` 里报 `TypeError: '>' not supported between instances of 'str' and 'int'`。只在 judge 里加 `int(...)` 的话，下一行 `tokens` 求和还会报 `unsupported operand type(s) for +`，要回到加载处修。在 judge 和求和两处都加 `int(...)`，看板上的数是对了，但测试随后直接检查 `load_spans` 的输出，会挂在 "load_spans returns tokens as ints"。
2. `TraceCollector.ingest` 不去重。导出器超时重发，同一个 span 进来两次，sess-c 的错误数、tokens、span 数都翻倍。docstring 写的是按 `(trace_id, span_id)` 去重，重复的返回 False。
3. `trace_count=len(spans)`，数的是 span 不是 trace。课里 `code/main.py` 就是这么写的。
4. `eval_score_mean` 把整个会话的 span 当成一条 trace 打一次分，这也是课里代码的写法。docstring 要的是每条 trace 单独打分，再对会话求均值。sess-a 里一条好 trace 和一条坏 trace 混在一起，整体打分是 0.5，逐条平均是 0.7。
5. `summarize` 对每个会话都调一次 `by_session()`，每次都把全部 span 重新分组，5000 个会话要 2 秒左右。分组一次就行。

护栏：
- 同一 trace 里有两个都叫 chat 的 span，按 `(trace_id, name)` 去重会把它们合并（"spans that share a name are still separate spans"）。
- sess-b 的导出器在每个 trace 里都把 span 编成 1、2、3，只按 `span_id` 去重会丢掉整条 b2（"span ids are unique within a trace"）。
- 去重要用集合。用 `any(...)` 扫一遍已存的 span，或者把 key 存进列表再用 `in`，都是 O(n²)。测试让导出器把 8000 个 span 整批重发一遍，限值 0.05 秒：参考实现 2 毫秒左右，扫描 1.2 秒左右，列表 0.45 秒左右。

看什么：是不是顺着 traceback 往上找到数据从哪来；是不是先 `print(repr(...))` 看实际的 tokens；每改一处就重跑。

提示：
- H1："What type is tokens when it reaches the judge, and where did it come from?"
- H2："What does an exporter do when it times out waiting for an ack?"
- H3：直接指出 `summarize_session` 里 judge 的输入是整个会话。

追问：
- "Why dedupe at ingest instead of at query time?"（重发是常态；在写入时去重，下游所有统计都不用再关心）
- "The collector restarts. What happens to the seen-set?"（内存里的集合会丢；需要持久化，或者让存储层用 `(trace_id, span_id)` 做唯一键）
- "The lesson says tracing without evaluation is just expensive logging. Where does this dashboard stop being enough?"（规则式的评审没有事实核验；课里说 judge 需要外部工具，即 CRITIC 模式）

### Part 2 标注队列（目标 10 分钟）

坑：
- `created_ns` 是 19 位的纳秒整数。列声明成 REAL（或 FLOAT、DOUBLE）时，SQLite 会把它转成浮点，末几位就没了。INTEGER 列能原样存 64 位整数。
- 0.0 分是一个真实的分数。`score or None` 会把它变成 None，`score or 0.0` 会把 None 变成 0.0。
- 标注按记录顺序返回，不按 `created_ns` 排：测试里 li 的笔记本时钟比 maya 慢。用自增列或 rowid 排序。
- 已经入队的 trace 再入队，位置不变。`INSERT OR REPLACE` 会先删再插，换一个新行号，排到队尾。`INSERT OR IGNORE` 或先查再插都可以。
- `pending()` 按入队顺序，不按 trace id 排（字符串排序时 tr-10 在 tr-9 前面）。
- 非法分数（包括 NaN）报 ValueError，而且不能留下半条记录；没入队的 trace 报 KeyError。
- 笔记要原样存，包括换行、`\r\n` 和前导空格。
- 测试抓不到的：score 列声明成 INTEGER 或 NUMERIC 时，0.0 读回来是 int 的 0，`==` 看不出来。这和第一条的 created_ns 是同一类类型亲和性，这里不另外考；看到了可以问候选人读回来是什么类型。

追问：
- "Two reviewers disagree. What do you show on the dashboard?"（保留每一条，另算一致率；或者按人取最新一条）
- "How would you turn these annotations into an eval dataset?"（只取有分数的；按 label 分层抽样；记录对应的 prompt 版本）
- "Ten reviewers pulling from the same queue at once?"（领取时加租约，`UPDATE ... WHERE claimed_by IS NULL`，超时释放）

### Part 3 按 prompt 版本二分（目标 12 分钟）

坑：
- 版本号按数字段比较。字符串排序时 v1.10 排在 v1.9 前面，从 known_good 往后就找不到它。
- 只有 PASS 算通过，WARN 不算。
- 每个版本都和 known_good 的通过率比，不和前一个版本比。v4.x 每版只掉 2.5 到 5 个点，逐版比较永远不报，和基线比在 v4.3 掉了 12.5 个点。
- 正好掉 max_drop 个点不算回归。用浮点数比较会出错：68% 和 58% 的差在浮点里是 0.10000000000000009。先算百分数（`100 * passed / n`）再相减，在 68% 和 58% 上碰巧是精确的 10.0，所以测试另有一组 9/14 对 19/35（64.29% 对 54.29%），常见的几种浮点写法在这组上都会算出比阈值多一点的差（比如 10.000000000000007）。要用整数交叉相乘或者 `Fraction` 比较。
- 反过来，为了躲开浮点把差值或通过率取整也不行：`int(...)`、`round(...)`、`100 * passed // n` 都会把 10/11 对 21/26 掉的 10.14 个点算成 10，漏掉这次回归。加一个很小的容差（比如 1e-9）能过测试，可以追问为什么整数比较更好。
- trace 数少于 min_traces 的版本不下结论，既不算好也不能当 culprit（v1.9 只有 5 条，通过率 60%）；正好 min_traces 条的版本是有结论的。
- 比 known_good 早的版本不参与（v1.2 很差，但和这次回归无关）。
- suspects 是 last_good 之后到 culprit 为止的所有版本，包括中间不下结论的那些：v1.12 只有 2 条 trace，改坏的可能就是它。v1.9 不在里面，因为它后面的 v1.10、v1.11 都正常。

追问：
- "Why compare against known-good instead of the previous version?"（逐版比较时，缓慢漂移每一步都在阈值以内；课里说回归要能二分到具体版本）
- "The inconclusive version is the real culprit. How do you confirm it?"（回放：把它重新部署到一小部分流量，或者在离线评测集上重跑）
- "Is a 10-point drop on 20 traces significant?"（不一定；可以用二项检验或置信区间代替固定的点数阈值）
- "The lesson says Phoenix has no prompt versioning. What does that mean for this code?"（版本号要从别处来：Langfuse 的 prompt 管理，或者自己在 span 上打版本属性）

### Part 4 批量摄取和 SSE（目标 14 分钟）

坑：
- 每个字段（status，以及每个 attribute 键）各自保留 ts 最新的值。按到达顺序覆盖的话，第 2 批里 ts=20 的旧 update 会把 ts=30 的 tokens 2600 改回 900。
- ts 要按字段记，不能整个 span 只记一个：第 4 批 t1 的 chat 先收到 ts=35 的 status，再收到 ts=32 的 tokens，tokens 仍要生效（2700）。update 的 attributes 要合并进去，整个替换的话，ts=35 那条会把 tokens 冲掉。
- update 可能先于 create 到达，要先存着，create 到了再合并（第 3 批 t2 的 error）。合并后同样按 ts 比较：create 的字段带着 create 的 ts，第 4 批 t4 等着的 update（ts=49）比 create（ts=50）早，tokens 仍是 10。
- 等待中的 update 在第 k 批到达，到第 k + orphan_ttl 批结束时还没等到 create 就丢掉（t9 在第 3 批结束时丢）。`>` 和 `>=` 差一批。从到达的那一批就开始计数会早丢一批：t2 的 update 第 1 批到，第 3 批才等到 create。测试先检查第 1、2 批没有 dropped 事件。
- 一批里的 session 事件按 session_id 排，不按碰到的先后：第 4 批先碰到 s-c，再碰到 s-a。
- 流结束时还在等的 update 也要报 dropped（t8）。
- 摘要没变的会话不发事件。第 2 批把 t3 的 status 设成它本来的值，s-b 被碰到但摘要没变。
- 重发的 create 不能把已经更新过的 span 改回去。第 2 批重发的 t1 chat 带着 tokens=100，改回去的话 s-a 的摘要和第 1 批发出的一样，这一批就没有事件了。
- 每批处理完就要 yield，不能先把所有批读完。测试数了被拉取了几批。
- id 在整条流里递增，不按批重来。
- 写成普通的 `async def` 加 `return` 时，测试报 `'coroutine' object has no attribute '__anext__'`，要会看出这里需要 async generator。

追问：
- "The browser reconnects with Last-Event-ID: 5. What do you need to keep?"（最近若干事件的环形缓冲，或者重放每个会话的最新摘要）
- "One slow browser tab. What happens to ingestion?"（生成器被拉取时才往前走；每个订阅者要有自己的有界队列，慢的丢旧事件或断开）
- "Why per-field timestamps instead of one per span?"（不同 update 改的是不同字段；按整个 span 比较时，旧的 tokens 更新会被整条丢掉，或者把新的 status 改回去）

### Part 5 trace 结构聚类（目标 12 分钟）

坑：
- 子节点按 `start_ns` 排，相同时按 `span_id` 排。按输入顺序会错（r1 是乱序给的）；只按 `span_id` 排也会在 r1 上错，工具调用的 id 最小，开始得却比第一个 chat 晚；只按 `start_ns` 稳定排序会在 r2 的平局上错。
- span_id 只在一个 trace 内唯一，所有 trace 都用 1、2、3、4。跨 trace 建一个全局索引会把父子关系连错。
- 父 span 不在本 trace 里的是根。r5 的签名是 `invoke_agent(chat),chat`。只把 `parent_id is None` 当根，这个 span 就成了谁也到不了的节点。多个根也按 `(start_ns, span_id)` 排：r5 的孤儿 span 在输入里排第一，按输入顺序会写成 `chat,invoke_agent(chat)`。
- 名字里的 `\`、`(`、`)`、`,` 要转义。不转义时，名为 `chat(retry)` 的叶子和 chat 下面挂一个 retry 的树签名相同，r6 会混进 r7、r8 那一簇。用 `str.replace` 逐个替换时要先换反斜杠，否则前面加进去的反斜杠会被再转义一次。
- 占比正好等于 min_share 的簇不算异常（2/8 = 0.25）。
- 占比的分母是 trace 总数，不是簇数，也不是 span 数。第一组 8 条 trace 有 5 个簇，按簇数算异常标记碰巧一样；第二组 r3、r4、r1、r2 里 web_fetch 占 1/4，低于 0.3，按簇数算成 1/2 就不异常了。
- 成环的 span 永远到不了根。只从根往下遍历会静默漏掉它们，要检查每个 span 都被访问到，否则报 ValueError。自己指向自己也是环。
- 排序：簇大的在前，同样大按签名字符串排。簇里的 trace_ids 按每条 trace 第一次出现的顺序，r8 排在 r7 前面，给 trace_ids 排序会挂。

追问：
- "Two runs call the same tools but one retries chat twice. Same cluster?"（这里不同；要不要折叠重复是产品决定，折叠后会漏掉重试风暴）
- "How would you cluster on more than shape?"（加上耗时、token 分桶，或者对 span 名和属性做向量化再聚类）
- "A new shape appears at 3% of traffic after a deploy. Anomaly or new feature?"（和 Part 3 一样，按 prompt 版本切开看）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出重发、时钟漂移、统计显著性、断线重连、慢订阅者 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
