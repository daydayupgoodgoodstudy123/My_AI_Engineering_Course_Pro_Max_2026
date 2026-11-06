# 面试官手册：Debate（14/25）

候选人计时期间不要看。候选人手里只有 README、`debate/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 五关互相独立。Part 4 用到 `engine.py` 里已经写好的 `Ask`、`Reply` 和 `check_reads`，不依赖 Part 3 的 `debate()`。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 星形里 hub 要不要读 spoke？ | "No. In the lesson's star the spokes read only the hub. That's where the 12 ops come from." |
| 1 | 平票时选谁？ | "The alphabetically first answer. The seating order must never decide." |
| 1 | 先一致、后分歧、最后又一致，converged_round 记哪一轮？ | "The round where the final agreement started." |
| 1 | 可以改 drift 的参数吗？ | "Keep the signature. It already takes a Counter of the peers' answers." |
| 2 | 字节布局能自己定吗？ | "No. The module docstring fixes it byte for byte. Other tools read these files." |
| 2 | -0.0 算合法的置信度吗？ | "Yes, it's within [0, 1]. Store it bit for bit." |
| 2 | NaN 呢？ | "Refuse it with a ValueError, like any confidence outside [0, 1]." |
| 2 | 读文件时要不要再校验每个 turn？ | "Yes. A file can't hold a turn that add() would refuse." |
| 2 | 能用 pickle 或 JSON 吗？ | "No. Use the layout in the docstring." |
| 3 | 辩手无视 taken，还是给了重复的答案？ | "Keep it. Don't ask again: every call costs money." |
| 3 | 同一轮里，后面的辩手能看到前面的辩手这一轮的新答案吗？ | "No. Rounds are synchronous. Round r reads only round r - 1." |
| 3 | 开场那一轮大家一致，能直接结束吗？ | "No. Only a critique round at or after min_rounds can end the debate." |
| 3 | 加权用哪一轮的置信度？ | "The last round played." |
| 4 | 超时要重试吗？ | "No. The debater abstains for that round and is asked again next round." |
| 4 | 读弃权者的人看到什么？ | "Nothing from it. Skip it, and it costs no op." |
| 4 | 要不要限制并发数？ | "No. A whole round goes out at once." |
| 4 | agree_ratio 保留几位？ | "Three decimals, the way format(x, '.3f') writes it." |
| 4 | 开场大家就一致，能直接结束吗？ | "No. Only a critique round in which everyone answered can end it." |
| 5 | 自己读自己、重复的 peer 怎么算？ | "Ignore both. People write these configs by hand." |
| 5 | 只有一个辩手时 reach 是多少？ | "Zero. There's nobody left to reach." |
| 5 | reads 里出现不存在的名字？ | "ValueError, naming it." |
| 5 | deaf 和 camp 要排序吗？ | "No. Keep the roster order, the order of reads." |

## 每关：要看什么、提示、追问

### Part 1 修课里的 runner（目标 12 分钟）

一个测试里叠了 4 个缺陷和 1 道护栏：

1. `sparse_star_round` 让 hub 读所有 spoke，还把这些读也算进 ops。课里星形 N=5、R=3 是 12 次（spoke 只读 hub），这里算出来是 24。docstring 写的是 hub 谁也不读。只删掉 hub 那一行的 ops、hub 照样读 spoke，ops 对了也过不了：测试用会记录输入的假辩手在星形上跑一轮，hub 不能收到任何票，每个 spoke 只收到 hub 的一票。
2. `majority()` 用 `Counter.most_common`，平票时按出现顺序选。docstring 要求平票取字母序最前的答案。错误不在 `majority()` 报出来，而是两层之外：测试让同样四个辩手正着坐、倒着坐各辩一次，按 docstring 两次都应该得 Madrid，现在的代码得 Porto。`majority()` 同时被辩手的 drift 和最后的多数票用到，只在 `run_debate` 的最后一票上改平票规则不够：测试接着让三个各持一个答案的辩手辩一轮，每个人看到的两个 peer 正好一比一，辩手自己的平票也要取字母序最前的答案。
3. `converged_round` 照搬课里的代码，记下第一次全体一致的轮次，之后又分歧了也不清掉。测试里的辩手第 1 轮一致、第 2 轮分歧、第 3 轮重新一致，应该报 3。
4. `full_mesh_round` 给每个辩手单独数一遍其他 N − 1 个人的答案，是 O(N²)。5000 个辩手一轮要 1.1 到 1.6 秒，限值 0.1 秒。改法是全体只数一次，再给每个辩手减掉自己那一票，修好后 5 到 12 毫秒。

护栏：提速时最常见的写法是全体数一次就直接发给每个人，忘了减掉自己那一票；或者减了，但减在同一个 Counter 上，一个人减完下一个人接着减。测试在提速断言之前，用会记录输入的假辩手核对每个人收到的票数，这两种写法都会在这里挂。

测试抓不到的：重写星形时让 spoke 读 hub 这一轮的新答案，而不是上一轮的。课里的 drift 不看自己上一轮说了什么，hub 又谁也不读，它的答案永远不变，所以结果一样；但这已经不是同步轮次了（Part 3 会考），看到了要指出来。

看什么：是不是先读断言消息、对照 docstring 和课里的 12 次；座次断言失败时，是去 `run_debate` 里打补丁，还是顺着找到 `majority()`；提速时有没有先想清楚“不算自己”这一条。

提示：
- H1："The lesson says a 5-debater star over 3 rounds costs 12 ops. Who reads whom in that count?"
- H2："Two answers have the same count. Which function picks between them, and by what rule?"
- H3：直接指出 `most_common` 的平票顺序，以及 `converged_round` 没有在分歧时清零。

追问：
- "The lesson's star has the hub read no one. What does that mean for the spokes' answers?"（它们永远到不了别人那里，hub 一个人说了算；这就是课里说的 hub failure，Part 5 会算出来）
- "Why does the tie rule have to be independent of seating?"（换个座次结论就变，结果不可复现；而且提速改写会改变插入顺序）

### Part 2 二进制辩论记录（目标 12 分钟）

坑：
- 布局是固定的，测试逐字节比对一条小记录：LEB128 是低 7 位在前，300 写成 `ac 02`；double 是大端。用 `<d`、固定宽度整数，或者把 7 位组倒过来写，往返都对，但逐字节比对会挂。
- 置信度必须逐位还原：0.1 + 0.2、1/3、5e-324（最小的次正规数）、-0.0。存成 32 位 float 会挂；-0.0 和 0.0 比较相等，所以测试另外按 `struct.pack(">d")` 比对。
- 文本长度是 UTF-8 字节数，不是字符数。答案里有 `ã`、`東京`、emoji 和 `\x00`，按字符数写长度会在读的时候错位。用 `\x00` 结尾的字符串也不行。
- `read` 是 tuple，顺序就是阅读顺序。读回成 list 或排了序，往返都会挂。
- 校验：NaN 用 `x < 0 or x > 1` 拦不住，要写成 `not 0 <= x <= 1`。读自己、重复读同一个 peer、辩手或 peer 越界都要拦。越界包括负数：只写 `>= len(roster)` 会放过 -1（`roster[-1]` 在 Python 里不报错），测试里有辩手 -1 和 peer -1。
- 被拒绝的 turn 不能留在记录里。先 append 再校验，`turns` 里会多出几条。测试先比对 `turns` 再比对字节，因为 round 为 -1 的 turn 一旦进了 `to_bytes()`，常见的手写 varint 循环（`n >>= 7` 直到 n 为 0）在负数上停不下来。
- 损坏的数据都要报 ValueError：截断在任何一个字节（测试逐个字节截）、多出尾部字节、magic 不对、读出来的 turn 不合法。不处理的话，截断会变成 IndexError 或 struct.error。
- 测试没有覆盖的：答案的字节不是合法 UTF-8 时，`decode` 默认抛 UnicodeDecodeError，它本身就是 ValueError；写成 `errors="replace"` 会把坏文件悄悄读进来，看到了要追问。

追问：
- "Why varints instead of fixed 4-byte ints?"（大多数轮次和下标都小于 128，一个字节就够；代价是不能随机访问）
- "How would you append turns while the debate runs?"（turn 数写在前面就不能直接追加；可以改成按记录追加、带长度前缀或校验和，崩溃时丢掉残缺的尾巴）
- "Why keep confidences bit for bit?"（Part 3 的加权会精确比较总和，存储改了一位，平票的结果就可能变）

### Part 3 稀疏拓扑辩论（目标 13 分钟）

坑：
- 开场按名单顺序一个一个问，`taken` 是这一轮已经出现过的答案，去重、按第一次出现的顺序。两个固执的辩手都说 Lisbon，第三个人看到的是 `("Lisbon",)`。
- 辩手不听话照样重复时就接受，不能再问一遍。测试会数每个辩手每轮被问了几次。
- 互评轮次是同步的：第 r 轮只读第 r − 1 轮。在同一个 dict 里边算边更新，环形拓扑上后面的人会读到前面的人这一轮的新答案，三个人第 1 轮就“收敛”了。Ask 里的 `own` 也是自己上一轮的回答，测试核对了 a 在第 1 轮和第 2 轮收到的 Ask。
- peers 按 `reads[name]` 的顺序给，不排序。
- `min_rounds` 之前不能因为一致就停（课里 Convergence collapse 的缓解办法）：测试里三个人第 1 轮一致地错成 Madrid，第 3 轮才一致地改成 Lisbon。
- 开场一致也不能停，只有互评轮能结束辩论：三个人开场都说 Lisbon（无视 `taken`），要到第 1 轮才算收敛，history 有两轮。
- 聚合按最后一轮的总置信度，不是按人数：只辩 2 轮、min_rounds=2 的那一次，b 一个人以 1.0 说 Lisbon，a、c 各以 0.25 说 Madrid，答案是 Lisbon。先比人数、或者只把置信度当平票规则，都会选 Madrid。
- 0.75 对 0.5 + 0.25 是精确的平票，要按支持人数决胜；`max(weights, key=weights.get)` 会选先出现的那个。完全平票时按第一个支持者在名单里的位置，按字母序会错。
- 每读一个 peer 算一次 op，开场那一轮是 0。

追问：
- "Forced disagreement made the ring never converge. Is that a bug?"（不是。强制分歧本来就会让收敛变慢；要靠更多轮或 hub 来打破对称）
- "Debaters return their own confidence. What can go wrong?"（模型的自报置信度没有校准，一个过度自信的辩手能压过多数；可以截顶、归一化，或者按历史准确率加权）
- "How would you rotate the hub when it goes bad?"（把 reads 做成轮次的函数，每轮换一个 hub，或者同时用多个 hub）

### Part 4 并发轮次和 CSV（目标 13 分钟）

坑：
- 同一轮的辩手要同时问（`asyncio.gather` 加每个调用的 `wait_for`）。一个一个 await，结果完全一样，但测试记录了同时在途的调用数，顺序调用时是 1。
- 超时的调用要取消，并且要等取消完成，再报告这一轮。`asyncio.wait` 超时后不取消，调用还在后台跑（还在花钱），测试会在第 1 轮的记录出来时检查；调了 `cancel()` 但不等它结束，这时取消也还没生效。把整轮包进一个 `wait_for` 也不对：超时时整轮都被取消，已经回答的人也成了弃权。
- 弃权者：单元格为空；不进 agree_ratio 的分母（两个人都说 Lisbon，比例是 1.000）；但这一轮不算收敛，因为不是每个人都回答了；下一轮读它的人跳过它，不计 op；它自己下一轮的 `own` 还是它最后一次给出的回答。
- agree_ratio 是最常见答案的占比：第一段的第 1 轮 alpha 说 Lisbon，beta、gamma 都说 `Porto "Invicta"`，比例是 0.667；按“和第一个辩手一致”来算会得 0.333。
- 测试最后一段（quiet）：开场三个人都说 Lisbon，不能结束，只有互评轮能结束辩论；第 1 轮三个人全部超时，agree_ratio 为空（不能除以 0，也不能写 0.000），下一轮谁也读不到，ops 是 0；之后一直不一致，就跑满 `rounds` 轮，最后一条是第 3 轮。
- 每一行都要交给 `csv.writer`。答案里有逗号和双引号（`Madrid, Spain`、`Porto "Invicta"`），手工用逗号拼接会被 `csv.reader` 解析成别的单元格。每个字符串恰好是一条记录，带行尾。
- 每轮结束就 yield，不能等整场辩论跑完。测试拿到表头和第 0 轮后数调用次数，应该只有 3 次。
- elapsed_ms 是这一轮自己的耗时，整数毫秒。超时那一轮至少 90 毫秒，后面那一轮不到 90 毫秒。从辩论开始累计、或者写成秒，都会挂。

追问：
- "A round takes as long as its slowest debater. What would you do about a slow one?"（设超时让它弃权；对冲请求；或者不等最后一个，达到法定人数就进入下一轮）
- "Why does an abstention block convergence?"（沉默不等于同意；如果弃权者恰好是唯一的反对者，提前收敛就把它的意见丢了）
- "N x R calls per question. Where does the latency budget go?"（每轮的延迟取决于最慢的辩手，总延迟约等于 R 乘以它；稀疏拓扑省 token，不省轮数）

### Part 5 读取图分析（目标 10 分钟）

坑：
- 方向：a 读 b，信息从 b 流向 a。课里的星形（spoke 只读 hub）上，hub 的答案 1 轮传遍全场，每个 spoke 的答案永远到不了别人那里，所以 rounds_needed 是 None。边建反了，结论正好倒过来。
- 一轮只走一跳，和 Part 3 的同步轮次是一回事。按轮模拟传播时，这一轮只能用上一轮的状态；在同一个集合里边扫边加，环形上 a 的答案一轮就能绕完整圈，reach 会算成 1 而不是 4。
- reach 是最少轮数。测试里有一条捷径：沿着链走要 3 轮，直接读只要 1 轮。按层做 BFS 是对的；用递归 DFS 记第一次访问的深度，全连接上会算出 4 轮。
- 到不了某个人时 reach 是 None，不能只取能到达的那部分的最大值。
- 自己读自己、重复的 peer 要去掉，不算 op；只读自己的辩手算“聋”的。
- camp 要求双向可达。只看单向可达，星形会被算成一个 camp。
- deaf 和 camp 都按名单顺序（reads 的顺序），不按名字排序。前面几张图的名单碰巧都是字母序，`split` 后面那张（z、y、m、b）不是，排了序就会挂。

追问：
- "What does rounds_needed tell you about choosing R?"（R 小于它时，有的开场答案还没传到所有人，辩论就结束了）
- "Two camps that never hear each other. What happens to the debate?"（各自收敛到自己的答案，整体永远不收敛；需要至少一条跨 camp 的边）
- "How would you pick a sparse topology for N = 50?"（在 ops 预算内让 rounds_needed 小、没有聋的辩手、只有一个 camp；比如每人读两个邻居再加几个 hub）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读断言消息和 traceback、对照 docstring 和课里的数字、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出成本、延迟、取消、置信度校准、拓扑选择 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
