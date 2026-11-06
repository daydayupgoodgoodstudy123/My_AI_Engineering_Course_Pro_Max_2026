# 面试官手册：Reviewer（14/39）

候选人计时期间不要看。候选人手里只有 README、`reviewer/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 目标里的标点要去掉吗？ | "No. Split on whitespace only, as the lesson does. The tests don't use punctuation." |
| 1 | 有一维 0 分时，总分要跟着记 0 吗？ | "No. The total is the sum of the scores. The verdict is what says hard_fail." |
| 1 | 构建者后来又改了状态，队列里的报告要跟着变吗？ | "No. A report records one review. The builder submits again when it wants a new one." |
| 1 | gate 说 passed: false 时还评审吗？ | "review() scores whatever it's given. That's how a forbidden write gets its 0. Whether to call the reviewer at all before the gate passes is the caller's decision, and the tests don't cover it." |
| 1 | 五个打分器可以并行调用吗？ | "Sure, as long as each runs once per submit and the report keeps rubric order. The tests don't need it." |
| 1 | `approved_scope` 里能写目录或 glob 吗？ | "No. Each entry is one path, exactly as the gate reported it, compared whole. Opening up a whole directory is a change to the contract itself. The tests don't use globs." |
| 2 | 正文用什么格式？ | "Your call, as long as the object's name is the SHA-256 of its bytes and the report reads back exactly. JSON is fine." |
| 2 | 同一个 attempt 又记了一次？ | "Same report: that's a retry. Return the same digest and write nothing. Different report: ReportConflict." |
| 2 | 两个任务的报告能共用一个对象吗？ | "The body includes the task id, so they never match. Attempts of one task can share." |
| 2 | 要校验 total 等于各维之和吗？ | "Not required. The tests don't cover it." |
| 3 | 0 分的意见也要引用证据吗？ | "Yes, every opinion should. An unsupported 0 still counts as 0, and it's listed as unsupported." |
| 3 | 引用的前缀区分大小写吗？ | "Everything is matched exactly, prefix and path." |
| 3 | state 里值为空的项能当证据吗？ | "Yes. The entry exists, and an empty value is evidence too." |
| 3 | escalate 了还要给结论吗？ | "Yes. Escalation flags the dimension for the human. Scores and verdict stay as computed." |
| 4 | 构建者回合结束后才落下的写入算哪一轮？ | "The next one. The reviewer sees the workspace as it was when the turn returned." |
| 4 | hard fail 之后还给构建者一轮吗？ | "No. A hard fail halts the loop and goes to a human." |
| 4 | 这一轮什么都没改，changed 写什么？ | "An empty field." |
| 4 | 最后一轮 pass 了，next 写什么？ | "done. A pass is done, even in the last round." |
| 5 | 同一秒里既有回复又有 resolve？ | "At or after the resolve counts as later, so the reply reopens the thread. The tests don't cover it." |
| 5 | 构建者能 resolve 吗？ | "It can mark a thread, but that resolves nothing. Report those threads in self_resolved." |
| 5 | 输入是按时间排好的吗？ | "No. A reply can come before the comment it answers." |

## 每关：要看什么、提示、追问

### Part 1 修 rubric 和签收队列（目标 10 分钟）

一个测试里叠了 4 个缺陷：前三个在课里 `code/main.py` 也有的两个打分函数和 `review()` 里，第四个在签收队列里，也就是讲义流程图最后一步的 Human Sign-Off：

1. `score_problem_fit` 数的是（关键词，文件）对，而不是不同的关键词。T-001 的 `signup` 同时出现在 `app/signup.py` 和 `tests/test_signup.py` 里，被算成 2 分，总分成了 10。docstring 写的是按不同关键词计数。照抄课里的 `sum(any(...) for k in keywords)` 只修好一半：目标里写了两遍的 `signup` 仍然算两次。
2. `review()` 的结论只看总分：低于 5 是 hard fail，低于 7 是 soft fail，其余是 pass，和讲义 rubric 一节的说法一样。docstring 和讲义 Key Terms 里的 hard fail 还有一条：任一维 0 分。测试里的构建者顺手改了 `scripts/release.sh`，gate 报了 `scope.forbidden`，scope_discipline 是 0 分，其余四维满分，总分 8，起始代码给了 pass。五个分数都对，错的是结论。
3. `score_scope_discipline` 和课里的 `code/main.py` 一样只看 gate 的 findings，从不读 state 里的 `approved_scope`。讲义 rubric 表里 Scope discipline 问的是改动有没有留在合同里，后半句是 "or was the contract grown deliberately?"；第 36 课的做法是越界时问人，要么扩大合同，要么退回。docstring 据此规定：每条越界路径都在人批准的清单里是 2 分，否则 1 分；forbidden 写入是 0 分，任何批准都抵消不了。测试里的任务改了 `docs/api.md`，gate 报了越界，人随后把这条路径加进了合同。错误不在打分器里报出来，而是在 `review()` 的总分和结论里：本该 7 分 pass，起始代码给了 6 分 soft fail。gate 的越界判断本身是对的，评审漏看的是人后来批准的那份清单。
4. 计时：`SignOffQueue` 只存输入，`report()` 每次都重新评审，`board()` 为了取 total、verdict 和零分维度，又对每个任务调了三次 `report()`。生产里每个打分器是一次模型调用（测试里每次 2 毫秒），读一遍看板再打开 20 份报告要 400 次调用，本机 1.0 到 1.2 秒，限值 0.05 秒。修法是 `submit()` 时评审一次，把报告存下来，读的时候直接返回。

护栏，针对常见的改法：

- 有一维 0 分，结论就是 hard fail，总分照实写：为了 hard fail 把总分清零，forbidden 那一条的总分就不是 8 了。零分也不是 soft fail；把零分的检查加在 pass 那一支后面，总分 7 以上的零分照样 pass。
- 结论来自评审自己的分数，不来自 gate。forbidden 那一条的 gate 正好是 passed: False，按 gate 的 `passed` 或 block 级的 finding 判 hard fail 能让它过，紧接着的一条就挂：没有任何反馈的任务，gate 是 passed: True，总分 7，只有 verification_quality 的 0 分能让它 hard fail。只给 scope_discipline 的 0 分开特例，也挂在这一条。
- 有失败也有成功的反馈仍是 1 分：把“有命令失败”也改成 0 分会挂。
- `score_handoff` 在起始代码里是对的，两条断言是它的护栏。任务没关又没写 next_action 是 0 分：用 `is None` 判断，空字符串会被当成写了下一步；换回课里的顺序、先看任务关没关，会给 1 分。任务没关但写了 next_action 仍是 1 分：把“任务未关”一律改成 0 分会挂。
- 批准只抵消它点名的那条路径。测试里 `docs/api.md` 和 `README.md` 都越界，批准的是 `docs/api.md` 和 `CHANGELOG.md`，仍是 1 分：“有批准就给 2 分”、只要有一条越界被批准就给 2 分（any 代替 every）、拿批准的条数和越界的条数比，都挂在这一条。
- forbidden 写入是 0 分，人批准过也一样。先用批准把全部 findings 过滤一遍再查 forbidden，或者先查“所有 scope finding 都批准了”再查 forbidden，人点过头的 `scripts/release.sh` 就成了 2 分、总分 10 pass。
- state 里可能没有 `approved_scope`，那就是没有批准：课里的 T-002 就没有这一项，用 `state["approved_scope"]` 读会报 KeyError。
- 每个打分器每次 submit 只跑一次：在 submit 里评审两次（一份存、一份返回）会挂。
- 存下的报告是那一次评审的记录：构建者之后改了状态，报告不变（“输入变了就重新评审”会挂）；同一个任务再 submit，要重新评审并替换（按 task_id 缓存会挂）。在第一次读取时才评审并缓存，第一次读看板就要 100 次调用，计时会挂。
- 看板每个任务一行，按首次提交的顺序列（按 id 排序会挂）。同一个任务再 submit，报告换成新的，行还在原来的位置：把报告存进列表、每次 submit 追加一份，看板会多出一行；先删再插，任务会挪到最后。报告里维度的顺序和备注与 SCORERS 一致。
- 路径转成小写再比：`app/InputValidation.py` 也要找到 input 和 validation。
- 测试抓不到的：去掉 `total < 5`、只留零分检查也能过。五个维度都至少 1 分时总分至少是 5，所以总分低于 5 一定有一维是 0。docstring 两条都写了，可以接受，追问里可以接着问维度数变了怎么办。
- 测试抓不到的：批准用 `startswith`、`fnmatch` 或转成小写再比也能过。测试里的批准都是完整路径，没有目录、glob 或只差大小写的写法。docstring 写的是按完整路径比较，可以追问为什么不接受 glob。

看什么：是不是先读断言消息，顺着 `review()` 的结论分清是哪一维给错了分，还是分数都对、结论错了；是不是打印 `[(d.name, d.score, d.note) for d in report.dimensions]` 看实际数据；7 分变 6 分时，是不是去对照 gate 报的越界路径和 state 里的批准清单，而不是动阈值或给 scope 开特例；计时失败时是不是先数一数一次 `board()` 调了多少次打分器，而不是直接加缓存。

提示：
- H1："Is one of the scores off, or the verdict? What does that docstring say?"
- H2：分数问题问 "Which return does this input reach, and is that the case the docstring describes?"；少了一分时问 "Which part of the inputs does that scorer never read?"；结论问题问 "Where does review() look at a single dimension?"；计时问题问 "How many times does one board() call run each scorer?"
- H3：直接指出 `review()` 只比较了总分，`score_scope_discipline` 从没读过 `approved_scope`，或者 `report()` 每次都调用 `review()`。

追问：
- "The keyword match can be gamed. How?"（文件名里塞进目标词就能拿满分：课后测验 Q9 里只写一份 `docs/input_validation_signup_notes.md` 就是 10 分 pass，改对了同义词文件 `app/auth/register.py` 反而 hard fail。真实实现要读 diff 内容、交给模型，并要求证据，也就是 Part 3）
- "Why should a single 0 fail a run that totals 8?"（总分是加起来的，一维的 0 会被其他维的满分盖住；而 0 分往往是一票否决的事：改了不许改的文件，做的不是这个任务，下一次会话接不上。讲义 Key Terms：hard fail 是停下来交给人）
- "Lesson exercise 1 adds a sixth dimension. Do the 5 and 7 thresholds still hold?"（满分变成 12，阈值要按比例换算或者重新定，Part 2 里那份六维报告就是 12 分里的 8 分 soft fail；任一维 0 分的规则不受维度数影响）
- "Why can't a human's approval cover a forbidden write?"（forbidden_files 是合同的负空间，即使无意也不能碰；真要改发布脚本，应该先改合同本身、重跑 scope check 和 gate，而不是事后批准一次写入。第 36 课：A contract without forbidden_files is incomplete）
- "The contract is written in globs. Why are approvals whole paths?"（人批准的是 gate 报出来、自己看过的那一条写入；想放开一整类文件，就改合同的 allowed_files，由 scope check 按 glob 重新判断，评审不用再实现一遍 glob）
- "Should the reviewer run at all when the gate says passed: false?"（skill 的拒绝规则：没有验证报告就不评审。先让便宜的确定性检查把关，讲义里叫 hybrid norm）
- "Every scorer is a model call. What else would you do about cost and latency?"（五个维度并行调用；Cloudflare 的做法是便宜的专家模型并行，顶级模型只给协调者）

### Part 2 评审报告历史（目标 12 分钟）

坑：
- 对象的文件名必须是它字节的 SHA-256。先 hash 一份缩进过的 JSON、再写一份紧凑的，名字就对不上。
- 往返要完全一致：第六个维度 money_safety 夹在第二位，按模块里的 RUBRIC 重建维度会把它丢掉；verdict 是评审写的 soft_fail，读回时按阈值重算会变成 pass；note 里有引号、箭头、换行、制表符和行尾空格；维度要读回成 list，tuple 不相等。
- attempt 按任务从 1 开始连续编号：跳号报 ValueError；T-002 的第一次是 1，用一个全局计数器会挂。用 `recorded[attempt - 1]` 取已记录的 attempt 时要查下界：attempt 0 会变成 `recorded[-1]`，record 把它当成对最新一次的重试，load 读出最新的一份，测试要求分别报 ValueError 和 KeyError。
- 已记录的 attempt 不能改：同一份报告再记一次，返回同一个 digest，不加索引行；不同的报告报 ReportConflict。把“同一份报告”也当成冲突，重试就会失败。
- attempt 号不写进正文：两次评审结论相同，就共用一个对象。
- 被拒绝的 record 什么都不写：先写对象、再检查 attempt，会留下没人引用的对象。
- 重开时要读索引，接着往下编号；`load` 要按 attempt 取，不能总是取最新的。
- 分数必须是 0 到 2 的 int：`score in (0, 1, 2)` 会放过 2.0 和 True（`2.0 == 2`，`True == 1`），`isinstance(score, int)` 会放过 True，只查类型不查范围会放过 3。

追问：
- "Why content-address the bodies at all?"（相同的结论只存一份；对象的名字就能证明内容没被改过；索引只追加，整个历史可以审计）
- "The index is appended, not rewritten. Why does that matter?"（重写时进程崩溃可能丢掉整份历史，追加最多坏掉最后一行。再严格一点：对象写完先 fsync，再追加索引）
- "Two reviewer processes record attempt 3 of the same task at once?"（文件锁，或者把 attempt 编号交给唯一的写入者）
- "Where does this sit in the workbench?"（skill 规定的报告路径是 `outputs/review/<task_id>.json`，这里是它的历史版本；第 40 课的 handoff packet 会引用这些报告）

### Part 3 带证据的评分与双评审对账（目标 12 分钟）

坑：
- 两份草稿按维度名配对，不能按位置：judge-b 的意见是乱序的，第二组里 judge-a 的也是。
- 引用逐字匹配：`file:App/signup.py` 不是 `file:app/signup.py`；`state:active_task_id` 的值是 None，但它是 state 里的一项，算证据；`feedback:pytest -q` 是命令，不是记录 id（这条命令跑了两次，一次失败一次成功）；`finding:scope.forbidden` 不在 gate 的 findings 里。
- 每条引用都要在输入里，而且至少要有一条：用 `any` 会放过半真半假的引用；`all([])` 是 True，不检查非空，什么都没引用的意见就算有证据了。
- 封顶是“最多 1 分”：没证据的 2 记 1，没证据的 1 和 0 不变。记成 0 或者减 1 分都会错。
- 没有证据的意见都要列出来，不只是被封顶降了分的那些（judge-b 无证据的 1 分也要列），先列第一个评审的，各自按 rubric 顺序，不按草稿里的顺序。
- 两个计入分数取平均后向下取整。Python 的 `round(1.5)` 是 2、`round(0.5)` 是 0（银行家舍入），会在 1 对 2 时给出 2。取较高的不对；取较低的在 1 分差时碰巧一样，到 2 对 0 时给 0。
- escalate 比较的是封顶之后的分数：无证据的 2 对有证据的 0，封顶后是 1 对 0，不 escalate；有证据的 2 对无证据的 0，仍是 2 对 0，要 escalate。相差 1 不算。
- escalate 不改分数也不改结论：被 escalate 的维度仍是向下取整的平均值，总分 9 照样 pass。
- 边界：总分恰好 7 是 pass，恰好 5 是 soft fail；任一维 0 就是 hard fail，哪怕总分是 7。最后这条和 Part 1 修好的 `review()` 是同一条规则，候选人照搬过来是对的。
- 维度集合不对要报 ValueError：少一维、多一维、同一维两次，还有“同一维两次再少一维”（只比较长度会放过，后面取不到那一维会报 KeyError）。

追问：
- "Why cap an unsupported score at 1 instead of ignoring the opinion?"（没有证据的高分最不可信，封顶保留了“这个评审觉得还行”的信号，又不让它拉高结论；0 分不受影响，宁可保守）
- "Rounding down is conservative. What does it cost?"（两个评审一个 1 一个 2 时取 1，误判 soft fail 会多一轮构建；反过来误放一个坏改动的代价更高）
- "How would you check these two judges are any good?"（课里的校准集：10 到 20 个已知结论的历史任务，每次改 prompt 都重跑，一致率低于 80% 先改 rubric）
- "Lesson: LLM judges have position bias. Where does it bite here?"（这里两个评审各自独立打分，没有让模型比较先后；如果让一个模型比较两份方案，要两种顺序都评，只算一致的胜出。另外两条缓解也用得上：评审来自不同的模型家族，打分前去掉作者名）

### Part 4 构建与评审交替的回合（目标 14 分钟）

坑：
- 评审拿到的必须是构建者这一轮返回那一刻的冻结副本。直接把 workspace 给评审，或者给 `MappingProxyType(workspace)`（只读，但仍是实时视图），格式化钩子在评审等待期间写进来的内容都会被看到。
- 快照要只读：给一份普通的 dict 副本，评审写进去不报错，测试要求 TypeError，而且构建者的工作区不能被评审改动。
- changed 是这一轮快照和上一轮快照的差别：钩子在第一轮评审期间写下的内容算第二轮的变化；删掉的文件也算；内容没变的重写不算；排序后用 `;` 连接，按工作区顺序会错；第一轮和循环开始前的工作区比，每轮都和第一轮前比也会错。
- changed 两边都要用快照。评审结束后再拿实时的 workspace 去比，钩子的写入会提前一轮算进来。主场景里钩子改的正好是构建者这一轮也改过的文件，看不出来；测试最后一段里构建者只写了测试文件，钩子在评审期间改了 `app/signup.py`，第一轮的 changed 只能是 `tests/test_signup.py`。
- 结论：soft_fail 进入下一轮，下一轮的构建者拿到这份报告；pass 结束循环（next 是 done，在最后一轮也是 done）；hard_fail 立刻停下交给人（next 是 human）；到上限还没 pass，最后一行 next 是 human。
- 每轮的记录要在下一轮构建开始之前发出：攒到最后一起发会挂，测试的构建者会数自己开始时已经收到几行数据。
- 格式由测试的解析代码决定：每个字符串是一条 csv.writer 写出的记录，以换行结尾，最前面是表头。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要会看出这里需要 async generator。
- 测试抓不到的：手写 `",".join(...) + "\n"` 也能过。这里的字段没有逗号、引号和换行，csv.reader 对 `\n` 和 `\r\n` 一样处理。可以接着问：路径里带逗号时会怎样（要按 CSV 规则加引号，这正是用 csv.writer 的理由）。

追问：
- "In a real harness, how would you hand the reviewer a frozen snapshot of a repo?"（提交一个 commit 或建一个 worktree，只读挂载给评审；讲义的原则：the reviewer cannot edit the diff）
- "Reviews are slow. Could the next builder turn start before the review is in?"（可以投机地开始，但下一轮要用报告里的意见，评审结果出来后可能要作废重来）
- "Lesson exercise 5: the reviewer may ask for more evidence before scoring. How do you stop that from looping?"（请求次数设上限；每次请求必须带来新的证据；超过上限交给人）

### Part 5 意见线程（目标 12 分钟）

坑：
- 回复可以回复回复，任意深度都属于它那条 finding 的线程。只看 finding 的直接回复，会漏掉 fit-a 第四层的 resolve 和 scope-a 第二层的新回复。
- 输入没有顺序，回复可能排在它回复的评论前面。一遍扫描、要求父评论先出现，会在合法的输入上报错。
- 只有评审能 resolve，构建者的 resolve 不算数（verify-a）。
- 评审 resolve 之后，线程里任何更晚的评论，不论深度、不论是谁，都会重新打开它（scope-a、handoff-a）。“resolve 过就一直是 resolved”会挂。评审自己在 resolve 之后的追问也算：测试第二组里的 assume-b 只有评审的评论，仍然是 open，“只有构建者的回复才重新打开”会挂。
- 看的是评审最后一次 resolve，按时间算，不按输入顺序：verify-b 先被 resolve，构建者回复后又被 resolve 一次，两次 resolve 在输入里是倒着排的。取第一次，或者取输入里最后出现的那次，都会把它判成 open。
- self_resolved 是仍然 open、并且构建者在评审最后一次 resolve 之后（或者评审从没 resolve 过）标了 resolve 的线程。fit-b 里构建者先标、评审后来认可，已经 resolved，不算；scope-a 里构建者的标记早于评审的 resolve，后来被新回复重新打开，也不算；handoff-a 的最后一条是评审的回复，但构建者的标记晚于评审的 resolve，算。
- threads 按 finding 的时间排，不是输入顺序，也不是最后活动的时间；self_resolved 跟着线程顺序（输入里 handoff-a 排在 verify-a 前面，按输入顺序列会挂）；open_by_dimension 列出 rubric 的每一维，没有 open 线程的写 0。
- finding 的维度不在 rubric 里，或回复指向不存在的评论，都报 ValueError，消息里要有那条 finding 或回复自己的 id：c12 回复的 c404 不存在，消息里要有 c12，只写 c404 会挂。

追问：
- "A reply loop: c1 answers c2 and c2 answers c1?"（参考实现报 ValueError；向上找根时不记录走过的节点会死循环）
- "Builder and reviewer bots keep replying to each other. What stops them?"（每条线程设回合上限，超过就交给人；和课里练习 5 的回退是同一个问题）
- "Where do these threads come from in production?"（PR 的 review comments；讲义：Claude Code 的 reviewer subagent 把 rubric 分数作为评论贴到 PR 上）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback 和断言消息、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出调用成本、记录不可改、快照隔离、交给人的时机 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
