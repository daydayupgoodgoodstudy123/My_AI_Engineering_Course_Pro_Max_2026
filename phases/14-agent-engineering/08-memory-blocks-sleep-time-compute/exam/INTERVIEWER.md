# 面试官手册：MemBlocks（14/08）

候选人计时期间不要看。候选人手里只有 README、`memblocks/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 超限的写入要截断，还是当场摘要？ | "Neither. Refuse it with an error observation. The sleep-time agent condenses the block later." |
| 1 | limit 算不算换行？ | "Yes. It's the length of the value, newlines included." |
| 1 | `block_replace` 的 new 可以是空串吗？ | "Yes. That's how the model deletes a stale line." |
| 2 | 日志中间有一行坏了怎么办？ | "That's not a crash. Raise. Only a torn last line is expected." |
| 2 | 每次写都要 fsync 吗？ | "Flushing is enough for the tests. Tell me what you'd do in production." |
| 2 | label 可以有大写字母吗？ | "No. Lowercase names only, as the docstring says." |
| 3 | key 区分大小写吗？ | "Yes, exactly as written. The primary agent writes them in lowercase." |
| 3 | fact 和自由文本之间也要去重吗？ | "No. Facts are settled by key only." |
| 3 | 两条重复的自由文本留哪条？ | "The first one. Something may already cite it." |
| 4 | sleep agent 正在整理的块又被主 agent 写了，要再排一次队吗？ | "No. Your compare-and-swap retry picks the new write up." |
| 4 | 模型返回的结果超过上限怎么办？ | "Drop it. The next write to that block queues it again." |
| 4 | 可以同时开几个 worker 吗？ | "No, one block at a time. The model is the expensive part." |
| 5 | 来源图里会有环吗？ | "No. Sources have to exist before the record made from them." |
| 5 | 我作废的那条记录本身要放进结果吗？ | "No, only the records made from it." |
| 5 | 已经作废的记录，往下还要找吗？ | "Yes. It may have been invalidated for another reason, and records made from it can still be valid." |
| 5 | 两条一样短的链选哪条？ | "The one through the earlier-created source. It's in the docstring." |

## 每关：要看什么、提示、追问

### Part 1 修块工具和 sleep pass（目标 10 分钟）

一个测试里叠了 4 个缺陷和几道护栏：

1. `Block._commit` 不检查 `limit`，超限的写入照样成功（讲义的 Block bloat）。docstring 要求拒绝：返回以 `error:` 开头的 observation，值、版本、history 都不变。
2. `Block.replace("", new)`：`"" in value` 永远为真，`str.replace("", "-")` 会在每个字符之间插入 `-`。插入后仍在上限内，所以修好第 1 处才看得到。
3. `summarize` 记账漏了行与行之间的换行（`used += len(line)`），保留 k 行时结果最多超出 k−1 个字符。错误不在 summarize 里报出来：sleep pass 把 86 字符的 task 块压成 52 字符（应不超过 50），之后主 agent 写一行 49 字符的事实，被第 1 处修好的上限检查拒绝。报错的地方离根因两层调用。
4. `Archival.get` 线性扫描。`SleepTimeAgent.run` 每作废一条都要 `invalidate → get` 从头扫一遍：3.2 万条记录里作废 8000 条，本机约 1 秒（负载高时 1.6 秒），按 rid 建索引后约 2.4 毫秒。限值 0.08 秒。

护栏：

- 拒绝不是截断：把写入截到上限（悄悄丢事实，Silent drift 的一种），或者先 push history 再检查，都会被 "a refused write changes nothing" 抓住。
- 恰好落在上限上的写入要接受，`>=` 会挂；上限按整个值算，含换行，只比 text 长度或不计换行都会挂。
- `block_replace` 和 rewrite 同样受上限约束，只在 append 里检查会挂。
- 要拒绝的是空的 old，不是空的 new。`block_replace(", at home", "")` 是删除，必须成功；修第 2 处时写成 `if not old or not new` 会被 "block_replace can delete text" 抓住。
- summarize 保留的是最新的若干整行：用 `text[-target_len:]` 凑长度会切断一行；放不下就 `continue` 去取更旧的短行，会把旧事实拼到新事实前面。
- 作废的记录要留在 `all_records()` 里、每条都要作废、要带原因。直接在 run 里改 `record.valid` 也可以，但别忘了原因。

看什么：是不是先读断言消息和 observation（措辞由候选人自己定，例如 `error: append would make task 102/100 characters`）；会不会回头看 sleep pass 之后块有多长；每改一处就重跑。

提示：
- H1："What did the sleep pass leave in the task block? How long is it?"
- H2："summarize promises at most target_len characters. Count what it returns."
- H3：直接指出 `used += len(line)` 没有算换行。

追问：
- "Refuse, truncate, or summarize inline. Why refuse?"（关键路径上不做摘要；截断会悄悄丢事实；拒绝让模型改用 replace 或写进 archival，sleep pass 稍后压缩）
- "Where would you set the near_limit threshold?"（讲义练习 1：要给两次 sleep pass 之间的写入量留出余量，太高会撞上限，太低会频繁摘要）
- "The lesson's _summarize kept sentences from the front. What goes wrong?"（保留最旧的、丢掉最新的：住在柏林留下，搬到里斯本丢了，摘要反而制造了陈旧事实）

### Part 2 块版本日志（目标 12 分钟）

坑：
- 用 `"w"` 打开，每次写都覆盖；或者只存在内存里。
- 自己拼分隔符（制表符、`|`）而不用 JSON：值里的 `\n`、`\r\n` 会把一个版本拆成几行。
- 撕裂的尾行要从文件里截掉，下一个版本从半行开始的位置写（`truncate`，或者把完整的部分重写回去）。只在读的时候跳过、不截：新的一行接在半行后面，重开时整行读不出来；再加上读到坏行就跳过，v4 就悄悄没了。先补一个换行把半行封起来、读的时候跳过坏行，v4 读得出来，但半行永远留在日志中间，测试数文件里的换行会挂。
- 截断位置按字节算。用了 `ensure_ascii=False` 时 emoji 是 4 个字节、1 个字符，按字符数截会切进前一行。
- 版本号要连续，重开以后要从文件里接上。重开后的第一个调用可能就是 `record`：只信这个实例已经读过的版本（没读过就当成 0），`reopened.record("persona", 1, ...)` 会被接受。
- op 只能是三种之一。label 要整串校验，`../human` 不能变成路径；`re.match` 不加结尾锚点只校验了开头，`human/../persona` 会混过去，测试里报的是 FileNotFoundError。
- `value_at` 的 0 是空块，4 和 -1 都要报 KeyError。直接按下标取，4 报 IndexError，-1 会取到倒数第二个版本。
- `restore` 的 history 是每次写之前的值，第一项是空串，和 Part 1 的 `Block` 一致。
- 值里还有 U+2028 和 U+0085，这是顺带的边界：`json.dumps(..., ensure_ascii=False)` 写、`str.splitlines()` 读，会在它们那里把一行 JSON 切开，报 JSONDecodeError。默认的 `ensure_ascii=True` 会转义它们；或者读的时候只按 `\n` 切。

追问：
- "fsync on every write?"（崩溃一致性和吞吐的取舍；可以按批 fsync，或者 group commit）
- "The log grows forever. What would you do?"（定期做快照、截掉旧日志，或只保留最近 N 版）
- "Why store full values instead of diffs?"（重建任意版本只要一次查找，一行坏了不影响别的版本；diff 省空间但要从头重放）
- "Two processes writing the same block?"（文件锁或单写者；O_APPEND 只保证单次 write 不交错，版本号检查仍会竞争）

### Part 3 sleep-time 整理（目标 12 分钟）

坑：
- 用子串匹配找矛盾（课里 `run` 的做法）：`city=Lisbon (updated from Berlin)` 提到了 Berlin，会被当成旧事实作废。要按 key 解析。
- 括号里的注释不属于值：`facts` 里 city 是 `Lisbon`。
- 按插入顺序取最新：晚入库的旧对话 `city=Porto`（at=200）会盖过 Lisbon（at=300）。要先按 at，再按插入顺序。
- 同一秒的 `pet=cat` 和 `pet=dog`：后写的赢。`record.at > best.at` 会让先写的留下。
- 已经作废的记录不参与：被投毒的 `city=Pyongyang` 不能拿去作废别人，也不能再报一次。这是讲义 Poisoned consolidation 在这一关的落点。
- 先按全文去重、再按 key 解析：role 改回 staff engineer 时，新记录会被当成旧记录的重复作废，最后的值变成 manager。
- 去重按小写字母数字词集合的 Jaccard，大小写和标点不算：`citation-heavy` 和 `citation heavy` 都是两个词，只去掉逗号句号再按空格切会挂。阈值严格大于 0.9，9/10 正好 0.9 不算重复；留先出现的那条。
- 重叠要除以两条记录合起来的词数。只除以旧记录的词数，多了 `every friday` 的那条（10/12）会被当成重复，新信息就丢了；只除以新记录的词数，少了 `short` 的那条（9/9）会被当成重复。
- 结果按插入顺序返回，每条一次；第二遍返回空。
- 测试抓不到、但值得指出的：按 `(at, rid)` 排序在这十几条记录上和按插入顺序一样，可 rid 是字符串，到 a1000 就排到 a999 前面了（Part 5 的滚动摘要会碰上）；自由文本按插入顺序去重，在这组数据上和按时间顺序结果相同，docstring 写的是先按 at；key 放进了大写字母（`[A-Za-z0-9_]+`），测试里没有大写的 key，也看不出来。

追问：
- "Exercise 2 says more than 90% token overlap. Is Jaccard the right measure?"（短记录上 Jaccard 很敏感；也可以用 containment、MinHash；语义上的重复要 embedding，成本高，放在 sleep pass 里正合适）
- "Who decides that a free-text record is contradicted?"（这里只处理 key=value；自由文本要模型判断，sleep-time 可以用更强的模型，但要把依据写进原因）
- "Why never delete?"（审计和排查“agent 为什么以为 X”；合规、医疗、法律这类领域需要历史主张）
- "A million records?"（按 key 建索引；增量整理，只看上一次 pass 之后写入过的 key）

### Part 4 主 agent 和 sleep-time agent 并发（目标 14 分钟）

坑：
- `turn` 里 `await` 了 sleep pass：测试把模型卡住，回合永远回不来，这正是 No latency cost 的反面。
- 只在 `idle()` 里启动 sleep-time agent：测试要在第二个回合之前看到模型已经被调用。
- 不做 compare-and-swap：模型读的是 v3，写回时块已经是 v4，`pet=cat` 丢了（测验 Q12 的 lost update）。
- 被拒以后不重试：human 一直没整理。重试的同时又把 human 排一次队：贵的模型多调一次，调用列表会多一项。
- 被拒的重写写进了 trace，或者版本号先加再检查：trace 里的版本号接不上。
- 模型返回原值时不提交。写成“rewrite 没提交就重试”，会在 persona 上无限循环。
- 起了多个 worker：两个块同时在整理，违背“一次一个”。
- 按回合改动的先后整理：先是 human、persona、task，`idle()` 之后是 task、persona。用栈或者按 label 排序，调用列表的顺序会错。
- `idle()` 只等一个 tick 就返回：task 还没整理完。先出队再整理、`idle()` 等队列变空，也会在 task 整理到一半时返回：task 排在最后。参考实现整理完才出队，“正在整理”也算在队里，去重和 `idle()` 都靠这一点。
- worker 只在第一次写入时启动（`if self._worker is None`），跑完就再也起不来：`idle()` 之后 task 和 persona 又各写了一次，没有人整理它们。
- diff 格式由测试的 `replay` 决定：每段以 `--- label@vN` 和 `+++ label@vN+1 (writer)` 开头，每一行包括最后一行都以换行结尾。用 `splitlines(keepends=True)` 加默认 lineterm，最后一行没有换行，下一段的头会粘上去。空值没有行，persona 的第一段是 `@@ -0,0 +1 @@`；`"".split("\n")` 是 `[""]`，拿它做 diff 会多出一行 `-`，replay 报 "a diff applies to the version before it"。
- 写到不存在的块要返回 `error:`，不能静默跳过（课里的 PrimaryAgent 就是静默跳过）。
- 测试抓不到、可以接受的：diff 用 `n=0` 不带上下文，replay 照样能重建；被拒的写入也把块排进队列，测试里 human 本来就在队里看不出来，代价是多一次模型调用。用 `splitlines()` 切值在这组数据上和按 `\n` 切一样，值里有 `\r` 时 diff 就和块对不上了，可以顺口问一句。

追问：
- "Threads or processes instead of asyncio?"（读版本和写入之间不再原子，要用锁，或者数据库的条件更新 `UPDATE ... WHERE version = ?`）
- "The sleep agent keeps losing the race on a hot block. What then?"（重试上限加退避；只在空闲时跑；或者把整理结果写成提案，下一回合由主 agent 合并）
- "How does the primary agent notice a sleep-time rewrite?"（讲义的 Silent drift：trace 里的 diff；下一回合的 prompt 标出块的版本变化）
- "What about the Persona or Safety block?"（讲义练习 4：sleep-time 的改写先进待审区，第二个 agent 审 diff 后再提交）

### Part 5 派生记录的传递失效（目标 12 分钟）

坑：
- 宽度优先的发现顺序不是创建顺序：brief 直接派生自 city，会排到它的另一个来源 voice 前面。
- 深度优先的先序也不是：weekly 会排到它的来源 commute 前面。按 at 排序也不行，brief 的 at 是它覆盖的时间，比它的来源早。
- 菱形：weekly 从 profile 和 commute 都能到，brief 从 city 和 voice 都能到，各列一次。
- 链取最短的：brief 是 `(city, brief)`，不是 DFS 走出来的 `(city, profile, voice, brief)`；一样短时走先创建的来源，所以 weekly 走 profile。
- 宽度优先、记下第一个找到的父节点：第二层的平局（weekly）碰巧也对，第三层的不对。budget 的两个来源 food 和 vet 链一样长，宽度优先先找到 food，可 vet 先创建，链要走 vet。按 at 断平局也不对，food 的 at 比 vet 早。
- 派生记录的作废原因是 `derived from <链上的前一条>`，不是根的原因，也不是 sources 列表里的第一项。
- 根已经被 `consolidate` 作废过（`pet=cat`）：仍要顺着它往下找；Rederive 里的 reason 是档案里存的第一个原因。
- 中间的记录也可能早就作废了：owner_copy 被 `consolidate` 当成 owner 的重复作废，由它派生的 vet 和 budget 还是有效的，也要作废。遍历时遇到已作废的记录就不往下走，会漏掉它们。
- `derive` 要先检查来源再插入。先插入的话，报了 KeyError，档案里却多了一条没有来源的记录。
- 再作废一次返回空，已作废的不再列。
- 1500 层的滚动摘要：递归会 RecursionError；按 rid 字符串排序会把 a1000 排在 a998 前面，建链时找不到来源。
- `pet=cat` 那一段要先跑 Part 3 的 `consolidate`。Part 3 没做完的话会挂在这一句上，记录时要分开看。
- 测试抓不到的：遍历不记已访问的节点，结果仍然对（第二次作废返回 False），但菱形多的图会按路径条数重复遍历，最坏是指数级。可以追问。

追问：
- "Would you re-derive in this order? What if a rebuilt summary comes out the same?"（按这个顺序重建；结果没变就不再往下传，类似增量构建的 early cutoff）
- "A summary with ten sources, and one went stale?"（可以只重算受影响的部分，或者记录每个来源贡献了什么）
- "Could there be cycles?"（来源必须先存在，所以没有；如果允许原地更新记录，就要检测环）
- "How is this different from cache invalidation?"（这里是记录级的来源图，要给出重建顺序和原因链，让运维回答“agent 为什么忘了 X”）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback 和 observation、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出崩溃一致性、并发写、成本、审计 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
