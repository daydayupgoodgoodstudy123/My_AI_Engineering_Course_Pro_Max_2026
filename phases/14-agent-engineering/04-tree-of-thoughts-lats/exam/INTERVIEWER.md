# 面试官手册：ThoughTree（14/04）

候选人计时期间不要看。候选人手里只有 README、`thoughtree/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- Part 3 和 Part 4 依赖 Part 1 修好的 `game.py`。Part 1 超过 20 分钟还没修完，就把剩下的修法直接告诉候选人，记成 H3，让他接着做后面的关。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | children() 要不要自己去掉重复的状态？ | "No. It lists every step. The search deduplicates, level by level." |
| 1 | beam=None 是什么意思？ | "Keep every state: plain BFS. That's how we show a deal has no solution." |
| 1 | 评判员说 sure 的状态能不能直接当答案？ | "No. Sure means it can still make 24. Only 24 alone is an answer." |
| 2 | 字节布局怎么定？ | "Your call, within the module docstring: MAGIC, then VERSION as a little-endian u16, signed 64-bit numerators and denominators, floats bit for bit." |
| 2 | trace 要整条存吗？ | "Store whatever rebuilds it exactly. The last step of each node is enough." |
| 2 | 能用 pickle 或 JSON 吗？ | "No pickle: we load checkpoints from disk we don't fully trust. Pack the records with struct." |
| 2 | 放不下 64 位的数怎么办？ | "ValueError when saving. Never truncate a number." |
| 3 | 叶子第一次被选中就扩展吗？ | "No, on the second visit, as in the docstring. The first visit rolls out from the leaf itself." |
| 3 | uct() 里父节点 visits 为 0 怎么办？ | "It can't be zero here: a node only gets children after it has been visited. Make sure backpropagation counts the root." |
| 3 | 用哪个随机数生成器？ | "A fresh random.Random(f\"{seed}:{i}\") per iteration, with i counted over the whole search, so a resumed search replays the same rollouts." |
| 3 | 找到解以后还继续跑吗？ | "No. We can check an answer exactly, so the first one ends the search." |
| 4 | 解出来的状态也要送去评判吗？ | "Yes. The judge's reply is what confirms an answer." |
| 4 | 两个评估同时回来怎么办？ | "They won't in the tests. Report them in the order they come back." |
| 4 | 被取消的评估算进预算吗？ | "No. Only judgements that came back count." |
| 4 | 要不要限制并发数？ | "Not here. A whole level goes out at once." |
| 4 | 选 beam 用评判员回来的分数，还是自己调 game.value？ | "The judge's. In production it's an LLM, and the tests also run a judge that disagrees with game.value." |
| 5 | deal 里有两个 4，一步用的是哪一个？ | "The earliest one still in the pool, as the docstring says." |
| 5 | build 要检查结果是不是 24 吗？ | "No. It checks that the steps are valid and use every number once. evaluate gives you the value." |

## 每关：要看什么、提示、追问

### Part 1 修 ToT 搜索（目标 12 分钟）

一个测试里叠了 4 个缺陷和几道护栏：

1. tot_bfs 的停止条件照搬了课里的 `value(child) > 0.99`。课里的价值函数只给解出来的终局 1.0，这里的评判员给 sure 的状态也打 1.0，于是还剩三个数的 (100, 4, 4) 被当成了解，[4, 4, 10, 10] 只返回一步。docstring 写的是：解出来的子节点不问评判员，直接结束搜索。
2. start() 没有把数换成 Fraction，整数相除得到 float。错误不在 start() 报出来，而是在四五层调用之外：[3, 3, 8, 8] 返回 None。原因是评判员穷举 (8, 3, 8/3) 时，8 / (3 − 2.6666666666666665) 得到 23.99999999999999，判成 impossible，beam 把这一支丢了。第一条断言里的 96 / 4 = 24.0 恰好等于 24，所以问题要到第二条断言才露出来。
3. children() 照课里的代码只生成 a op b。状态按降序排，a ≥ b，b − a 和 b / a 永远生成不了，[1, 5, 5, 5] 需要的 1 / 5 没有，返回 None。
4. tot_bfs 每层不按状态去重。同一个状态可以从多条路径到达：两个相同的数、5 * 1 和 5 / 1、先合并哪一对。plain BFS（beam=None）在五个 7、五个 9、五个 10 上要 1.5 秒以上，每个 deal 要生成 24.3 万个孩子；去重后 8 毫秒左右（Python 3.10 上 18 毫秒左右），限值 0.15 秒。

护栏：

- 补 b − a 和 b / a 时，有人会把四种运算都按两个顺序各算一遍，+ 和 * 每对数就多出一个孩子。测试精确断言 (5, 1) 的孩子列表和 (6, 4, 4, 1) 的孩子数 36；在 children() 里自己去重、a == b 时跳过 b − a，个数也会变。Part 3 的访问次数依赖孩子的个数和顺序。
- 去重要在截 beam 之前做。截完再去重，beam 里不到 5 个状态，[1, 5, 5, 5, 13] 会失败。按走过的步骤序列去重，只能合并步骤完全相同的路径，5 * 1 和 5 / 1 到达同一状态这种合并不了，这个 deal 也会失败。
- 一层只用一个 set。把 set 建在 frontier 的循环里面，就成了每个父节点各去各的重，不同父节点到达的同一状态还是重复。[1, 5, 5, 5, 13] 的挤占出在第一层，那一层只有根一个父节点，抓不住这种写法；[5, 6, 6, 6, 7, 10] 的重复出在第二层，beam 被挤满，找不到 (10 + 7 + 5) + (6 + 6) / 6。计时那一块也分不出来，这种写法只要 0.016 秒左右。
- 平分时保持发现的顺序。按 (score, state) 元组排序，平分时比的是状态，[1, 2, 3, 8] 会找到另一条也对、但不是 docstring 规定的解。
- [1, 2, 3, 4, 6, 11] 有解，但六个数时评判员只能估计，每层留 5 个的 ToT 找不到。每个父节点各留 5 个（第二层就是 25 个）会找到它，所以这一条钉死了“每层留 beam 个”。把评判员改成对任何大小都精确穷举，也会在这里挂。

也能过、结果和参考答案一样的写法，可以顺着追问：

- 从 frontier 取出状态时才判断 solved，或者写成 `value(child) > 0.99 and len(child) == 1`。这两种都会把解出来的子节点也送去评判，docstring 说的是不问评判员；评判员换成 LLM 以后，每次调用都要花 token。
- 循环里不去重，排好序以后按状态挑前 beam 个不同的状态。重复的状态分数相同、排序稳定，留下的还是第一条路径，只是重复的状态都评了一遍。
- start() 不动，在 combine() 里把操作数转成 Fraction。所有运算照样精确，但 start() 的 docstring 写的就是 Fraction，问候选人根因在哪。
- 用 list 记见过的状态。每次查找要从头比，计时那一块约 0.04 秒（Python 3.10 上约 0.06 秒），比用 set 慢五倍左右，但能过，可以追问为什么该用 set。

看什么：是不是先读断言消息和 traceback；是不是用 `print(repr(...))` 看状态里每个数的类型；找到 float 以后，是追到 start()，还是在显示和比较的地方打补丁（容差比较会被后面的精确步骤断言抓住）。

提示：
- H1："[3, 3, 8, 8] does have a solution. Which state on its path did the search drop, and why?"
- H2："Print the children of start([3, 3, 8, 8]) with repr. What type are the numbers?"
- H3：直接指出 start() 没有转成 Fraction，以及 `value(child) > 0.99` 把 sure 当成了解。

追问：
- "The judge works three numbers out exactly. If it were exact for every size, what beam width would you need?"（宽度 1 就够。搜索能做到多好，取决于评判员；课里说 self-evaluation is the load-bearing piece）
- "Beam 5 misses [1, 2, 3, 4, 6, 11]. Wider beam, better judge, or another search?"（加宽 beam 成本线性增长；更准的评判员每次调用更贵；MCTS 用访问统计在探索和利用之间分配预算。课里说 ToT 在 Game of 24 上要花 CoT 的 100 到 1000 倍 token）
- "Why does the lesson's own heuristic walk into (24, 4, 1)?"（它只看离 24 最近的那个数，不看剩下的 4 和 1 还能不能用完）
- "Deduplication turns the tree into a DAG. Which path's trace do you keep, and does it matter?"（保留第一条，结果才可复现；哪一条都是对的解）

### Part 2 搜索检查点（目标 12 分钟）

坑：
- 数存成分子和分母，有符号 64 位。经过 float 的话 2/3、−1/3 读回来不相等；分子用 'Q' 遇到 −10/3 报 struct.error；用 32 位的 'i'，1000033 × 1000003 = 1000036000099 放不下。
- 放不下 64 位的数要报 ValueError。2^40 × 2^40 = 2^80，struct.pack 抛的是 struct.error，测试不认。
- value_sum 和 c 要逐位不变：0.1 + 0.2、1/3、2.5e-310（次正规数）、√2。用 'f' 存就挂。
- 孩子的顺序原样保留。两个相同的 6 * 4 = 24 孩子是两个节点，不能按状态合并成一个。
- trace：每个节点存最后一步就够，读回时用 `parent.trace + [step]` 建新列表。直接往父节点的列表里 append，所有节点会共用一个列表。
- 这一步不能从状态反推。4 * 1 和 4 / 1 到达同一个状态，测试里有一个节点就是经 4 / 1 到达的；读回时到父节点的 children() 里找第一个状态相同的孩子，拿到的是 4 * 1，round-trip 那一条就挂了。
- 读回的数必须是 Fraction，visits 必须是 int。整数读成 int 的话 `==` 照样相等，但后面一做除法又变成 float；visits 用 'd' 存，读回来是 1000003.0，`==` 也照样相等。所以测试单独查了这两样的类型。
- seed 和 iterations 读回来也必须是 int。rollout 的种子是 f"{seed}:{i}"，9.0 和 9 拼出来的字符串不同，续跑就换了一串随机数。测试在这一关就查它们的类型，不用等到 Part 3 末尾的续跑断言才发现。
- solution 的 None 和 [] 不同：已经是 24 的 deal，解是空列表。用 0 步表示“还没有解”，两者就混在一起了。
- load 要拒绝一切不是完整检查点的数据：magic 不对、版本不对、少字节、多字节。测试把 blob 的每一个前缀都喂进去，必须都是 ValueError，不能是 struct.error 或 IndexError。
- 开头 6 个字节是固定的：MAGIC 加小端 16 位的 VERSION。其余布局候选人自己定。
- 读回再存，字节要完全一样。Part 3 末尾的续跑断言靠的就是这一点。
- 用 pickle 会在截断和多字节的检查上挂（pickle 不管结尾多出来的字节，截断时抛的也不是 ValueError）。候选人如果用 JSON 再自己补上范围检查，测试能过，但不符合 struct 打包的要求，用澄清问题里的回答拉回来。
- 也能过的写法：分母用无符号 64 位（Fraction 的分母总是正的）；visits 或 iterations 用 32 位。可以追问每个字段的上限。

追问：
- "A million nodes, saved every 100 iterations?"（不必每次存整棵树：追加写每次迭代改过的节点，或者定期快照加增量日志）
- "Why seed every iteration with f\"{seed}:{i}\" instead of saving the generator's state?"（续跑只需要 seed 和迭代数，前面 rollout 的长短不影响后面的随机数；也可以存 getstate() 的 625 个 32 位整数）
- "The machine dies halfway through a save."（先写临时文件再 rename；加校验和）
- "Version 2 adds a field. How do version 1 files load?"

### Part 3 MCTS（目标 12 分钟）

坑：
- UCT 是 Q + c·sqrt(ln N / n)，没访问过的孩子是 +inf，要在除以 visits 之前判断。用 max(visits, 1) 凑出来的分数是有限值，访问顺序就变了。
- 平分给前面的孩子。`max()` 本来就返回第一个最大值，手写循环用 `>=` 就变成最后一个。[5, 4] 跑 4 次以后孩子的访问次数是 [1, 1, 1, 0, 0, 0]，专门查这一点。
- 延迟扩展：叶子第一次被选中时直接从它 rollout，第二次才展开并走到第一个孩子，和课里代码的 `cur.visits > 0` 一样。第一次就展开，前 4 次迭代就对不上。
- 只剩一个数的节点不展开。它的 children() 是空列表，展开以后取 children[0] 会 IndexError。
- 回传要覆盖路径上从根到 rollout 起点的每个节点，包括刚展开的孩子。漏掉根，根的 visits 一直是 0，永远不会被展开；漏掉新孩子，它下一轮又被当成没访问过。
- visits 在回传时才加。往下走的时候就给经过的节点加 visits、回传时只加奖励，UCT 里的 N(s) 就把这一次也算了进去。多数时候选出来的孩子不变，测试里 [2, 3] 在 c = 0.1 下跑 70 次，访问次数就成了 [13, 10, 10, 15, 11, 10]，应该是 [14, 10, 9, 15, 11, 10]。
- 随机数：每次迭代新建 `random.Random(f"{seed}:{i}")`，i 是整个搜索累计跑过的迭代数。整个 run() 共用一个生成器，访问次数就对不上；i 只在这次 run() 里从 0 数，单跑能过，续跑对不上。
- rollout 每一步是 `rng.choice(children(state))`，从完整的孩子列表里选，重复的也算。先去重再选，抽样的分布就变了。
- rollout 走到 24 也是解：rollout 起点的 trace 加上 rollout 的步骤。课里的代码把这样的解丢了（测验 Q11）。[4, 6, 4, 1] 用 seed 9 在第 150 次迭代由 rollout 找到解；只认树里的节点，要到第 640 次。
- 找到解就停，而且 [] 也是解。用 `if search.solution:` 判断，[24] 会一直跑下去。
- c 要从 search.c 传进 uct()。课里的 mcts 改不了 c（测验 Q12）。c = 0.1 时访问集中到 2 + 1 = 3（剩下 7 和 3，7 * 3 = 21 离 24 最近，奖励 1/4）；c = 2.0 时几乎平均。这就是课里的练习 1。
- 续跑：存检查点、读回、接着跑，结果要和一口气跑完逐字节相同。
- 也能过的写法：rollout 用 `options[rng.randrange(len(options))]` 或 `rng.sample(options, 1)[0]`，消耗的随机数和 `rng.choice` 一样；用 `random.seed(...)` 设模块级的生成器也能过，但那是整个进程共用的状态，可以追问几个搜索并发跑时会怎样。

追问：
- "c = 0.1 or c = 2.0, if the judge were noisy?"（噪声大要多探索；课里说 tune c per task）
- "Where would LATS's LLM value and its reflections go in iterate()?"（展开时给新孩子打分，作为初始值；失败的 rollout 生成反思，放进后面 policy 的 prompt）
- "Why is stopping at the first solution right here?"（终局可以精确验证。课里说值得搜索的任务要有便宜、可靠的价值函数，比如单元测试、明确的目标值）
- "Most rewards here are close to 0. What does that do to UCT with c = 1.4?"（Q 之间的差远小于探索项，搜索接近按访问次数轮流，c = 2.0 的那组数就是这样）

### Part 4 流式评估（目标 14 分钟）

坑：
- 一层的所有状态同时送去评判（测试查 peak 等于这一层的状态数），回来一个输出一行，顺序是回来的顺序。这个假评判员先回答最后一个问题，按发出的顺序 await，顺序就反了。先 gather 整层再输出，测试记下的“每一行到达时已经回来几个”会对不上。
- 解出来的状态也要送去评判，它那一行后面紧跟 stop 行，之后什么都不能有。
- tokens_used 只加已经回来的评估。发出时就记账，或者先 yield 再加，数字都错。
- 预算：tokens_used 达到或超过预算就停。用 `>` 会多跑一行；只在两层之间检查，也会多跑。解和预算同时到时，解优先。
- stop 行的 tokens_used 是实际花掉的总数，可以超过预算：预算 50 时，第二个评估回来是 60，stop 行写 60，不是 50。
- 停下时取消还在跑的评估，而且要等它们取消完。只 cancel 不等，流结束时任务还没结束；这个假评判员挂断要花几轮事件循环，只等一轮也不够。
- 下一层取 beam 个最好的，平分时按发现的顺序，不是回来的顺序。[2, 3, 4] 第一层有三个 sure，按回来的顺序会选错。
- “最好”按评判员回来的分数算，不能自己再调 game.value。默认的假评判员就是用 game.value 打分的，分不出这两种写法，所以测试另有一个把每个判断都说反的评判员：[2, 3, 4] 在 beam 1 下跟着它走到 (7, 2)，最后是 exhausted，找不到解。课里说评判员不可靠时搜索往往适得其反，这是最极端的情况。
- 已经是 24 的 deal 不调评判员，整个流只有一行 solved，tokens_used 是 0，trace 是空列表。
- 一层里同一个状态只评一次，(3, 2) 有两条路径。
- 每行一个 JSON 对象加换行。数写成字符串（"1/5"）：Fraction 不能直接 json.dumps，换成 float 又不精确。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要看出这里需要 async generator。
- 也能过的写法：取消以后用 `asyncio.wait(tasks)` 等它们结束，和 gather 一样。

追问：
- "A real provider bills a cancelled call anyway. How do you account for it?"（发出时按单次调用的上限预留；用 provider 返回的 usage 对账）
- "Cap the concurrency at 4 calls."（Semaphore，或者一个固定大小的工作队列）
- "The same state comes up again in another search. Do you pay again?"（按状态缓存评估结果，就是 Part 1 的转置表；缓存要带上评判员的版本）
- "How far past the budget can you go, and how would you bound it?"（最多超出在途调用的总和；剩余预算不够一次调用的上限时就不再发）

### Part 5 表达式树（目标 10 分钟）

坑：
- 池子：deal 的每个数是一个 Leaf，带它在 deal 里的位置，按 deal 的顺序；每一步的结果追加到末尾。一步先取 a，再从剩下的里取 b，取到就从池子里删掉。不删，或者两个都找到了再删，10 * 10 会用两次同一片叶子。
- 取池子里最早的那个：结果可能和 deal 里的数相等（6 / 3 = 2，deal 里也有 2），取最后一个，树的结构就变了。
- 减法和除法的左右不能换：1 − 6 就是 Op("-", 1, 6)。
- 最少括号：子表达式的运算比父节点松（+ 和 − 比 * 和 / 松）才加；右操作数在父节点是 − 或 / 且一样紧时也加。a + (b − c) 写成 a + b − c，a * (b / c) 写成 a * b / c。
- 只有一个数的 deal 没有步骤，表达式就是那片叶子。
- 用了池子里没有的数、结果算错、步骤用完后剩下不止一个表达式，都报 ValueError。测试里那个算错的例子只有一步，所以只能靠结果检查抓住。
- evaluate 用 Fraction，返回的也是 Fraction。用 float 或 `eval(render(...))`，8 / (3 − 8 / 3) 会算成 23.99999999999999；精确算完最后才转成 float，24 看不出来，1 / 3 就露馅了。
- 也能过的写法：先在 deal 的叶子里找、找不到再到结果里找。池子里叶子总排在结果前面，这和取最早的那个是一回事。检查结果时转成 float 再比，测试里的例子也都能抓住，但 Fraction 本来就能精确比较，可以追问为什么要绕一道 float。

追问：
- "a + b and b + a are the same answer. How would you count distinct solutions?"（规范形：交换律下给子表达式排序，结合律下展平）
- "render never prints Leaf.index. Why keep it?"（区分两个相同的数；审计时能说出 deal 里每个数用在了哪里）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出评判员的可信度、token 成本、转置表、确定性续跑、取消的代价 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
