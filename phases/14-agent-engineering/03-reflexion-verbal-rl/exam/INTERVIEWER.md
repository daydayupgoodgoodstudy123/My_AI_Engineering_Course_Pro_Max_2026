# 面试官手册：Reflexion（14/03）

候选人计时期间不要看。候选人手里只有 README、`reflexion/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 能改 Actor 吗？ | "No. It stands in for the model. Fix the code around it." |
| 1 | 工具宕机的那个试次算不算一次试次？ | "Yes. It uses up a trial. It just teaches nothing, so nothing goes into memory." |
| 1 | 同一条反思又学到一次，试次号用哪个？ | "The latest. Its ttl counts from there, and the failures add up." |
| 1 | 什么算同一条反思？ | "Equal after normalize. Case and spacing don't matter." |
| 1 | 记忆满了，又学到一条已有的反思，要淘汰最旧的吗？ | "No. It replaces its old copy, so nothing has to go." |
| 1 | 近似重复（相似度 0.9）也要合并吗？ | "Not here. Only what normalize makes equal." |
| 2 | 能改成存 JSON 吗？ | "No. People read and edit this file, like CLAUDE.md." |
| 2 | 反思里有三个反引号怎么办？ | "It still has to come back exactly. Pick a fence that can hold it." |
| 2 | 条目之间有人加了一行备注？ | "Reading skips it. Writing writes a fresh file." |
| 2 | 标题行有拼写错误？ | "That's an error. Don't drop the entry silently." |
| 2 | 文件还不存在？ | "No learnings yet. Return an empty list." |
| 2 | 要不要原子写（临时文件加 rename）？ | "Not needed here. Just don't touch the file until every entry checks out." |
| 3 | scalar 说通过，但同一个动作连做了两次？ | "Scalar wins. The rails never overrule ground truth." |
| 3 | 自评本来就没通过（或者没有自评），又连着两次同一个动作，来源算什么？ | "Stuck. Below the scalar, the first rule that applies decides." |
| 3 | self_score 正好等于 0.5？ | "That's a pass." |
| 3 | 外部故障算不算用掉一次试次？ | "Yes." |
| 3 | 既没有 scalar 也没有 self_score？ | "Not a success. Source none, and no reflection." |
| 3 | 过期的反思要从记忆里删掉吗？ | "No. visible() only filters. The memory keeps them, so replaying an earlier trial still sees what it saw." |
| 4 | 任务要并行跑吗？ | "Concurrently, on one event loop. A task's next trial starts as soon as its last one is judged." |
| 4 | 成功率的分母是什么？ | "All the tasks, solved or not." |
| 4 | 一个任务成功以后还继续吗？ | "No. It's done." |
| 4 | 行尾用 \r\n 还是 \n？ | "Whatever csv.writer writes." |
| 4 | 读的人提前停了怎么办？ | "Stop the trials that are still running." |
| 4 | attempt 抛异常呢？ | "Not in the tests. Tell me what you would do." |
| 5 | code/test 算 code/tests 的上级吗？ | "No. Ancestors are whole path segments." |
| 5 | 父类能看到子类的反思吗？ | "No. Lessons flow down, never up." |
| 5 | 某一层不够 per_level 条，空出来的名额给别的层吗？ | "No. per_level caps each level on its own." |
| 5 | 根是什么？ | "A top-level class, one with no parent." |
| 5 | 同一句话挂在子类和父类上，要去重吗？ | "Not in the tests. What would you do?" |

## 每关：要看什么、提示、追问

### Part 1 修反思循环（目标 12 分钟）

一个测试里叠了 4 个缺陷和几道护栏。这一课原来的 Actor 只数反思条数、不读内容（本课测验第 5 题）；这里的 Actor 读最新一条反思，从里面拿到上次试了什么、差多少，然后每次最多挪 4。所以反思写错、记忆存错，都会在两三个试次以后表现成不收敛。

1. `SelfReflector.reflect` 把方向写反了：`delta > 0` 时写 “is short”，否则写 “overshoots”。docstring 说 delta 是 `sum(attempt) - target`，小于零才是不够。第一次试 `[1, 2, 3]`，差 14，反思却写成 “sum 6 overshoots by 14; pick smaller values”，Actor 往下调成 `[1, 1, 1]`，然后一直停在那里。报错在 `run_reflexion` 的结果上，离根因隔着 Actor 读反思这一层。
2. `EpisodicMemory.add` 满了以后用 `kept.pop()` 丢掉的是刚加进来的那一条，也就是最新的。默认 `max_len=6` 的那次运行碰不到上限，所以修完第 1 处才露出来：`max_len=2` 时记忆停在第 1、2 次的反思上，Actor 每次都读第 2 次的反思，反复给出 `[9, 2, 3]`。
3. `run_reflexion` 遇到 `ToolDown` 时写了一条 “the check failed ... wait for the checker next time” 存进记忆。讲义说外部故障（network down, tool broken）的反思对以后的运行没有帮助，把一次偶然的故障写成反思就成了 superstition。这里还更糟：这条反思成了最新的一条，Actor 读不懂，退回 `[1, 2, 3]`，前面学到的全丢了。
4. `add` 每加一条都把整个记忆重新规范化一遍、重建一次列表，每次 O(n)，回放一段长记录就是 O(n²)。讲义的 Memory rot：缓冲越大重跑越慢。3,700 次写入（3,600 条不同的反思，其中 100 条又学到一次）本机实测 1.4 到 1.7 秒（负载约 4.5），限值 0.1 秒；改成按规范化文本做键的 dict 以后约 1.2 毫秒。

护栏：

- 方向要在 `reflect` 里修。改 Actor 让它把 “overshoots” 读成往上调，运行能收敛，但反思原文那条断言会挂；把 `scalar_check` 改成 `target - sum`，delta 的符号那条断言会挂。只翻条件不翻符号，会写出 “is -14 short”，Actor 读不懂，仍然不收敛。
- 去重的语义不能在提速时丢掉：重复的反思要挪到最新的位置，带上最新的试次号、措辞和 ttl，两边的 failures 要相加（测试里是 1 加 2，只加 1 也会挂）。直接丢弃新条目（`if key in seen: return`）、原地覆盖 dict 的值（位置不动）、不加 failures、只刷新试次号不换措辞，都会挂在 “a lesson learned again moves to the newest slot” 这条上。
- 被淘汰的反思再学到时要从头算（failures 是 1）。normalize 不能为了快而简化：只 casefold 不合并空白、只合并空白不 casefold，都会让 “Pick larger values ...” 和 “pick larger values  when the SUM ...” 变成两条。
- 记忆满了以后又学到一条已有的反思，什么都不用淘汰：先拿掉旧的那条、放进新的，再看有没有超过 max_len。先腾位置再去重，或者先 append 进 `deque(maxlen=...)` 再删旧的那条（append 时 deque 已经自动挤掉了最旧的），都会白白挤掉一条还有用的反思，挂在 “a lesson learned again on a full buffer pushes nothing out”。
- 改成 dict 以后，`dict.popitem()` 弹出的是最后插入的那一条，等于把第 2 处缺陷又写回去了；要用第一个键，或者 `OrderedDict.popitem(last=False)`。用列表加“键到下标”的 dict 也不行：删掉一条以后后面的下标全错了，下一次按下标取就会 `IndexError`，或者取错条目。
- 计时那条抓的是每次 add 都在 Python 里把全部记忆走一遍的写法。只把规范化文本缓存在每一条旁边、每次 add 还是重建列表，仍然是这种写法，本机约 0.24 到 0.29 秒，会挂。用 set 判断重复、只在重复时重建列表（本机 15 到 27 毫秒），或者用一个键列表在 C 层面做 `in`/`index`（约 22 毫秒），都能过；这两种其实还是线性的，可以追问重复的反思很多时怎么办。
- 外部故障要占一次试次，但不能在同一个试次里重试到工具恢复（一直宕机时测试会数 check 调用了几次），也不能不记录这个试次。只有 `ToolDown` 算外部故障：把 `except ToolDown` 放宽成 `except Exception`，检查器自己的 bug 就被当成宕机悄悄吞掉了。

看什么：是不是先把每个试次的 attempt、delta、反思打印出来对着看，而不是直接改 Actor；修第 2 处时有没有去看记忆里到底存了什么；提速前有没有先确认慢在哪一行。

提示：

- H1："What does the Actor read before trial 2, and what does it do with it?"
- H2："Print each trial's reflection next to its attempt and the target."
- H3：直接指出 `reflect` 的条件和 docstring 说的 delta 方向相反。

后面几处卡住时：“Print `small.reflections()` after each trial.”；“What does memory hold after trial 3 of the flaky run?”；“What does one add() do for every entry already stored?”

追问：

- "The lesson's Actor only counts reflections. Why does this one read them?"（只数条数的 Actor 对反思写对写错毫无反应，本课测验第 5 题就指出了这一点。读内容以后，方向写反、读到旧的反思、读到一条垃圾反思，都会改变行为，这才是 verbal reinforcement 真正起作用的地方）
- "Your fix stores nothing for the outage. Where should that fact go instead?"（日志、trace、告警，而不是会拼进下一次 prompt 的记忆。讲义：reflection on "the network was down" does not help future runs）
- "Why should a repeated lesson take the latest trial instead of keeping its first?"（ttl 要从最近一次学到算起，否则一条反复被验证的反思会在仍然有用时过期；failures 记录证据有多少）
- "The skill also collapses near-duplicates (over 0.9 cosine, or 80% shared substring). How, without going back to O(n²)?"（向量索引或 MinHash/LSH 先找候选；或者放到 sleep-time 压缩里离线做，不挡主路径，讲义提到 Letta）

### Part 2 学习记录文件（目标 12 分钟）

坑：

- 版式由精确文本那条断言钉死：HEADER、空行、标题行、空行、围栏、正文、围栏，条目之间一个空行，文件以换行结尾。
- 围栏长度：比正文里最长的一串反引号多一个，至少三个。FENCED 的正文中间有 ```` ``` ````，要用四个。只数行首的反引号、长度等于最长串、没有“至少三个”，精确文本都会挂；永远用三个的话，正文里有 ```` ``` ```` 行的反思读回来会被截断。
- 读的时候从第一行起就要认围栏：HEADER 本身就在围栏里放了一个示例标题行。只找 `## ` 开头的行、把标题和围栏块按顺序配对、按 `"\n## "` 切文件，都会把这个示例当成一条记录。这就是“文件头说明段不能被当成记录”。
- 关闭围栏的必须是和开头一模一样的那一行。用 `startswith("```")` 会在 ```` ```python ```` 那行提前关闭；任何一行反引号都算关闭的话，四个反引号里的 ```` ``` ```` 会提前关闭。按 CommonMark 的规则关闭（只有反引号、不比开头短）也能过：写出来的文件里，正文不会有这么长的反引号行。
- 正文原样：行尾两个空格（Markdown 的硬换行，编辑器常常顺手删掉）、行首四个空格（Markdown 的缩进代码块）、开头和结尾的空行、制表符、以 `- `、`#`、`## ` 开头的行。读的时候不能 strip、rstrip 或者去缩进。
- 人手改过的文件也要读对：标题换了措辞、标题和围栏之间有两个空行或者没有空行、围栏后面跟一行备注、文件最后没有换行。用一个正则匹配整条记录、要求恰好一个空行，会漏掉条目。
- 围栏外以 `## ` 开头的每一行都是条目标题，必须合法。把不合法的标题当备注跳过，后面的围栏也就成了备注，这条反思就悄悄丢了：`failure 3` 这样的笔误必须报错。标题要整行匹配：`(trial 12, ttl 5, failures 3) checked` 后面多出的字，用 `re.match` 会悄悄放过，下次写回时就没了。标题后面没有正文、围栏没关、两个标题挨着、读回 trial 0、ttl 0 或者不合法的 task class，都报 ValueError；读和写用同一套检查。
- 写之前先把每一条都检查完，再打开文件：`open(path, "w")` 一打开就清空了，边写边查的话，一条坏数据会把整个文件毁掉。task class 要用 `fullmatch`，`match` 会放过 `math/arith/` 和 `math//arith`。只有空白的正文、trial/ttl/failures 小于 1，都要拒绝。
- 数字要读回成 int。文件不存在时返回空列表。

追问：

- "Your editor strips trailing whitespace on save. What happens to the entry that ends in two spaces?"（正文被悄悄改了。给这个文件配 .editorconfig 例外；或者给每条记录存一个摘要，读的时候发现被手改过就提示）
- "A reflection contains \r\n. Does it survive your reader?"（文本模式读会把 `\r\n` 和单独的 `\r` 都变成 `\n`；要用 `newline=""` 打开或者按字节读。`read_text().splitlines()` 能过测试，但它还会在 U+2028、`\x0c` 这些字符处断行。测试没有发这种文本）
- "Two agents write learnings at the same time?"（文件锁，或者写临时文件再 `os.replace`；否则后写的覆盖先写的）
- "JSON round-trips for free. Why Markdown?"（人要审、要改，像 CLAUDE.md 一样进代码评审；代价就是要有这样一套严格的格式。讲义 Use It：Claude Code 的 `/memory` 和 pro-workflow 的 `/learn-rule` 都把缓冲区外置成 Markdown 文件）

### Part 3 评估器裁决与试次循环（目标 12 分钟）

坑：

- 规则顺序：external、scalar、stuck、inefficient、self、none，第一条成立的说了算。讲义：scalar when available, self-eval when not, heuristics as safety rails。
- `if trial.scalar:` 把 `False` 当成没有 scalar，于是 scalar 失败、自评 0.9 的试次被判成功。`if trial.self_score:` 把 `0.0` 当成没有自评，判成 none。都要用 `is not None`。
- 护栏不推翻 scalar：scalar 通过时，连跑两次 test、走了 51 步，都算成功。护栏推翻的是自评。
- stuck 是同一个动作连续出现两次，不是“出现过两次”：`test, edit, test` 不算。连续的两次出现在哪里都算：只比较前两个动作、按 (0, 1)、(2, 3) 两两比较，都会漏掉 `search, read, read, answer` 和 `read, edit, edit`。inefficient 是动作总数超过 max_steps，讲义说 exceeds 50 steps，正好 50 步不算；`search, read` 交替 52 步不算 stuck，但算 inefficient，按不同动作的个数数就漏了。自评达到 pass_score 就算通过，0.5 算过。
- 护栏只要成立就说了算，不管自评通过、没通过还是根本没有：`search, read, read, answer` 自评 0.2 是 stuck，`read, edit, edit` 没有自评也是 stuck，都会写反思。只在自评通过时才看护栏（来源成了 self），或者只在有自评时才看护栏（来源成了 none，反思也没了），都不对：护栏本身就是讲义的 heuristic evaluator。
- external 排在最前面：报了 error 的试次，就算带着 scalar False 或者连着两个相同动作，也是 external。
- 没有任何信号时不算成功，来源是 none，也不写反思（配套 skill：reflection requires a signal, not a gut feeling）。
- `visible(now)`：第 t 次的反思、ttl 为 n，给第 t+1 到 t+n 次看。本课测验第 11 题的写法 `now - trial < ttl` 少看一次；`trial <= now` 让一个试次看到自己的反思；不设下界的话，从文件读回的记忆里，后面试次的反思会给前面的试次看到。按记忆里的顺序，旧的在前。`visible` 只过滤，不删：在里面顺手删掉过期的反思，最后那条 `memory.reflections()` 的断言会挂。
- 循环：第 n 次调用 `act(n, memory.visible(n))`；编号从 start 开始；存 `Reflection(n, task_class, text, ttl)`；external 和 none 不写反思；成功不写反思并且停下；每个试次都算数，外部故障也算；`max_steps` 和 `pass_score` 要传给 `judge`。
- 和 Part 1 连起来：第 12 次和第 15 次写出同一句反思，记忆里合成一条，试次号变成 15，failures 是 2，所以第 16 次还看得到它。ttl 从最近一次学到算起。

追问：

- "Why don't the rails override a scalar pass?"（scalar 是 ground truth；重复的动作也可能是正常的重试；护栏防的是最弱的那种信号，也就是自评）
- "The self-evaluation passed but the trajectory is stuck. What should the reflection say?"（说过程，不说结果：我重复了 X，下次换 Y。讲义练习 3 问的就是 stuck 和 Self-Reflector 怎么配合）
- "Why count ttl in trials, not hours?"（配套 skill：TTL should be trial-scoped, not time-scoped, for offline-replayable runs。重放同一段运行，看到的反思和原来一模一样）
- "No signal at all. Should the loop keep trying?"（skill 的拒绝规则：没有 evaluator 就不做反思，建议去看第 05 课；这里只是由 max_trials 截住）

### Part 4 学习曲线 CSV（目标 14 分钟）

坑：

- 输出格式由测试的解析决定：先是表头，之后每完成一个试次一行。Q1 里有逗号，Q3 里有双引号，所以要用 `csv.writer`；手写 `",".join` 或者自己加引号都会解析错。每个字符串恰好是一条记录，带行尾；去掉行尾的话，拼起来就成了一行。
- success 写 1 或 0；evaluator 是判定来源；成功率是已解决的任务数除以全部任务数，四位小数（`0.2500`），不是按行算的通过率。
- 行按完成的顺序，而且完成一个就输出一个：测试记下每一行到达时已经完成了几个试次，必须依次是 1 到 8。先 gather 全部再输出、轮询队列，都过不了这条；任务一个接一个跑、用一把锁把任务串起来，顺序那条会挂。像论文那样按轮次跑（所有任务的第 n 次都完成再开始第 n+1 次）也不行：Q4 的第二次应该在 Q1 的第一次之前完成。
- 每个任务一个记忆：共用一个记忆，别的任务的反思会漏进来；每个试次新建一个记忆，就什么都学不到。ttl=1 时 Q3 的第三次什么都看不到：第一次的反思过期了，第二次是外部故障，没写反思。Q4 的第一次没有任何信号（来源 none），也不写反思，所以 Q4 的第二次什么都看不到；在曲线里另写一个 `not verdict.success and source != "external"` 的条件，会把 none 也拿去反思。直接用 Part 3 的规则。
- 一直没成功的任务也有三行；外部故障那次也有一行。
- 读的人提前关掉流（`aclose`）时，要把还在跑的任务取消：测试在拿到第一行后关闭，再等 200 轮事件循环，不能有新的试次开始。
- 任务名重复报 ValueError（第一次取值时抛出）。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要看出来这里需要 async generator。`asyncio.TaskGroup` 是 3.11 才有的，要兼容 3.10 就用 `create_task`。

追问：

- "The paper plots success rate per trial number. Why not run the tasks in lockstep rounds?"（按轮次跑，每一轮都要等最慢的任务；各任务各自往下跑，整体更早结束。按试次号的曲线可以事后从这些行算出来）
- "One trial hangs forever."（给每次 attempt 加 `asyncio.wait_for`，超时按外部故障处理）
- "The model API allows two calls at a time."（在 attempt 外面套一个 `asyncio.Semaphore`）
- "attempt raises."（像参考实现那样把异常交给读的那一边抛出，或者记成外部故障；不能让后台任务悄悄死掉，否则读的那一边会一直等下去）

### Part 5 任务类作用域（目标 10 分钟）

坑：

- 上级按完整的路径段算：`code/tests/flaky` 的上级是 `code/tests` 和 `code`。用字符串前缀判断，会把 `code/test` 的反思也拿进来；`support/billing` 和 `support/billing-disputes` 是兄弟，互相看不到。
- 近的层在前；同一层里试次号新的在前，试次号相同的按挂上去的顺序。`sorted(...)[::-1]` 会把并列的顺序也反过来；直接把挂上去的顺序倒过来，是假设挂上去的顺序就是时间顺序。
- 两个上限同时生效：每层最多 per_level 条，总共最多 total 条，一层之内也受 total 限制（per_level=5、total=2 时只给 2 条）。只在每层开始前检查 total，会多给。
- 可疑的条件是两个同时成立：挂在根类（没有父类的那一层）上，而且只来自一次失败。所有只来自一次失败的都标、所有根上的都标、按被查询的那一类判断，都不对。
- 父类看不到子类：`recall("math")` 只有 math 自己的。
- 声明过的类和它的每一个前缀都是已知的；其余的（`math/arith/division`、`physics`）在 recall 和 attach 时都报 KeyError。声明的类要用 `fullmatch` 检查，不合法报 ValueError。

追问：

- "What should happen to a suspicious reflection?"（先让人审，再让它覆盖整个领域；或者降回它出生的那个类；要求来自几个不同子类的多次失败才挂到根上。配套 skill：never escalate to agent scope automatically）
- "Who attaches a reflection to a parent class in the first place?"（sleep-time 的压缩任务：同一条教训在几个子类里都出现了，再提上去，而且不在主路径上做）
- "The same sentence sits on a class and on its parent."（近的那条遮住远的那条：先按规范化文本去重，再算名额，不然重复的那条白占一个位置）
- "How would you know a recalled reflection actually helps?"（带它和不带它各跑一组做对比，看成功率、步数和 token；本课测验第 17 题）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读报错、打印每个试次实际看到的东西、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出外部故障该去哪、ttl 为什么按试次算、人工编辑的风险、并发和取消、反思作用域怎么升级 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
