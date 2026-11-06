# 面试官手册：Surfaces（14/31）

候选人计时期间不要看。候选人手里只有 README、`surfaces/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 告诉候选人：整套题不调用 LLM，也不联网。agent 是课里那个规则桩，运行事件和线束描述都是测试里写好的数据。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 禁止写的文件要不要也算进 off_scope_writes？ | "No. Forbidden writes are their own list. off_scope_writes is what the task neither allows nor forbids." |
| 1 | 一个文件既允许又禁止呢？ | "Forbidden wins. The tests don't have one." |
| 1 | 同一个文件写了两次呢？ | "List it once, where it was first written." |
| 1 | 有 feedback、没有 verification，算通过吗？ | "No. A captured run is evidence. Only the gate turns it into a pass." |
| 1 | label 有哪几种？ | "prompt-only, partial and workbench. The docstring has the rule." |
| 2 | 拒绝打分和 0 分有什么区别？ | "0 means the surface is missing. None means the auditor refused to score it, like verification in a repo with no test command. Keep them apart." |
| 2 | scores 里少了一个面，能当成拒绝打分吗？ | "No. A refusal is written down as None. A missing key is a broken audit: ValueError." |
| 2 | 第八个面（练习 3）能记吗？ | "Not in this card. The columns are the seven surfaces, so it's a ValueError." |
| 2 | 时间要统一成 UTC 再存吗？ | "No. Keep audited_at exactly as the auditor wrote it. Order by the instant it names." |
| 2 | 没有时区的时间呢？ | "Reject it. We can't order it against the others." |
| 2 | 同一时刻的两次体检怎么排？ | "In the order they were recorded." |
| 2 | scores 的键会按表头的顺序给吗？ | "Not always. It's a dict. Each score goes in its own surface's column." |
| 2 | 能为了保持顺序重写文件吗？ | "No. It's append-only. Earlier rows never change." |
| 2 | 要支持多个进程同时写吗？ | "Not today. Tell me what you would do." |
| 3 | instructions 在流程图的哪一站？ | "At the agent loop's startup: after state, before feedback. FLOW_ORDER has it." |
| 3 | catchers 的顺序有意义吗？ | "No. The flow decides the order." |
| 3 | 两个面杠杆一样呢？ | "The one earlier on the flow." |
| 3 | 一个面什么也拦不住，要列进 next_surfaces 吗？ | "No. Stop when nothing more can be stopped." |
| 3 | 服务里 1 分的面算存在吗？ | "No. Only healthy surfaces count. The service docstring says so." |
| 4 | 重复投递的事件内容会不同吗？ | "No. Same seq, same event. Check it once." |
| 4 | 流结束时还缺序号呢？ | "Raise ValueError and name the seqs that never arrived." |
| 4 | 之前一次 run 都没有就 claim 呢？ | "A feedback violation with exit_code null." |
| 4 | 同一次失败的 run 之后连着两次 claim？ | "Report both. Every claim is judged on its own." |
| 4 | 同一个越界文件写了两次？ | "Report it once, at the first write." |
| 4 | end 之后还会有事件吗？ | "Nothing with a higher seq. Late and redelivered events can still arrive after it." |
| 5 | ref 是相对路径吗？ | "No. Always the full path from the top runtime." |
| 5 | ref 断了，这个 trigger 还要报 no_function 吗？ | "Yes, both. They're different findings." |
| 5 | 函数的 ref 断了，报在 worker 上还是函数上？ | "On the function: the worker's path, a slash and the function's name." |
| 5 | 经过 chat 的环算闭合吗？ | "No. Only a durable store closes the loop." |
| 5 | policy 的内容要检查吗？ | "Not today. Only that every worker has one." |

## 每关：要看什么、提示、追问

### Part 1 修运行对照和失败报告（目标 12 分钟）

一个测试里叠了 5 个缺陷和几道护栏：

1. `RunResult.missing_surfaces` 返回的是集合（`set(...).difference(...)`），docstring 和返回注解写的是按 WORKBENCH_SURFACES 顺序排的列表。报错不在这里：`compare` 调 `write_report`，`json.dumps` 在编码器深处报 `TypeError: Object of type set is not JSON serializable`，traceback 里根本没有 `missing_surfaces`。要从 `default()` 那一帧的 `o = {'feedback', 'handoff', ...}` 认出这是七个面的名字，再回头找是谁造出了集合。只套一层 `sorted()` 会变成字母序，下一条断言 "missing surfaces keep the lesson's table order" 会抓住。
2. `failure_report` 的允许集写死成课里那个 `{"app.py", "test_app.py"}`（测验 Q9）。换成登录限流的任务后，三个允许的文件全被算成越界。修法是用 `task.allowed_files`。护栏：只把 stub 已知会乱写的 README.md 和 scripts/release.sh 当越界，或者“没禁止的都算允许”，都会漏掉幻觉写入的 CHANGELOG.md；照测验 Q9 的参考修法把禁止的文件也算进越界，同一条断言也会抓住。
3. `stub_agent` 的 label 还是课里的写法：有一个面就叫 workbench。docstring 要求七个面齐全才叫 workbench，否则是 partial。重写这一行时别把 prompt-only 丢掉：测试会读 failure_modes.json 里的 label，一个面都没有的运行仍然是 prompt-only。
4. `stub_agent` 的 verification 分支不看 `tests_run`，没有 feedback 也“证明”通过（测验 Q6）。课里说 verification “Fails closed”。修法：有 verification 并且有捕获的测试运行才算通过。护栏：改成“跑过测试就算通过”，只有 scope 和 feedback 的那次运行会被当成通过，"a captured test run is not a verdict; the gate is" 会抓住。只改 `failure_report` 里 `unverified_success` 的算式也不行：stub 仍把这次运行记成 `actually_passing`，测试同时查这两个字段。
5. 计时：越界列表和禁止列表都是先做集合运算，再用 `sorted(..., key=result.files_touched.index)` 恢复写入顺序。`list.index` 每次都从头扫，24,800 次写入的 codemod 要 1 秒多，一遍扫描约 1.5 毫秒。护栏：用 `sorted(set)` 或 `list(set)` 提速会丢掉写入顺序；去掉去重会让写了两次的 README.md 出现两次。允许清单和禁止清单各有 8,000 项（codemod 写了其中 800 个禁止文件），直接在 `task.allowed_files` 或 `task.forbidden_files` 这个列表里查，或者在输出列表里查重，也要 0.3 到 0.8 秒，同样超时。

看什么：是不是从 traceback 最底下那一帧的值往回推，而不是去 json 模块里找 bug；每改一处就重跑；修第 2 处时有没有对照 docstring 把禁止文件留在越界列表之外。

提示：
- H1："Which value in the report is not a list or a dict?"
- H2："What does missing_surfaces return, and what does its docstring promise?"
- H3：直接指出 `missing_surfaces` 的返回值。

计时卡住时可以问："How many times does sorted call its key, and what does one call cost?"

追问：
- "The report finds off-scope writes after the fact. Where should scope stop them instead?"（写入之前，在授权策略那一层拒绝；事后的 scope check 是 verification 的第二道防线，测验 Q11）
- "The stub decides passing with a flag. What would a real verification gate read?"（feedback 捕获的命令、退出码和输出；读不到就 fail closed）

### Part 2 体检记分卡（目标 12 分钟）

坑：
- 拒绝打分（None）和 0 分是两回事。写成空字段，读回来要变回 None。`int(v or 0)` 会把拒绝读成缺失，`int("")` 直接报错。
- scores 少一个面时，`scores.get(s)` 会悄悄写成空字段，看起来就像拒绝打分。要报 ValueError：拒绝必须明确写出来。
- 第八个面（`observability`）、超出 0 到 2 的分数、没有 UTC 偏移的时间都要报 ValueError，而且文件不能变。超范围的分数有 3 也有 -1，只查 `score > 2` 会放过 -1；先写入、后检查时间的话，被拒绝的那行已经进了文件。
- history 按时间点排，不按文本排：-08:00 的 3 月 13 日 17:30 晚于 +00:00 的 3 月 14 日 00:15。按文本排、按文件顺序读，都会把这两条弄反。同一时刻的两次体检保持记录顺序：`sorted` 是稳定排序，自然满足；拿文本当第二排序键会把 -08:00 的那条排到前面，用以时间点为键的 dict 收集会丢掉一条。
- 为了让文本能排序而把 audited_at 改写成 UTC，会破坏原样往返。
- 一行的分数要按 WORKBENCH_SURFACES 取，不能照 `audit.scores.values()` 的顺序写：acme/web 的 dict 把 handoff 写在最前面，按 dict 顺序写，它的 1 分会落进 instructions 那一列。
- 追加写：之前的字节必须原样保留（测试比较前缀），用 `"w"` 打开会把前面的体检冲掉；表头只在文件为空时写，靠实例上的标记判断的话，新开的 Scorecard 会再写一遍表头；只看文件存不存在也不够，测试先建了一个空文件，第一行仍然要是表头；备注里的逗号、引号和换行交给 csv 模块。

追问：
- "Two auditors append at the same moment from two machines?"（文件锁或单一写入者；或者每次体检一个文件；CSV 追加一行不保证原子）
- "You add an eighth surface next quarter. What happens to the old rows?"（表头就是 schema；加列需要版本或迁移，读旧行时补空）
- "Why keep the auditor's offset at all?"（审计记录要保持原样；时间点用来排序，原文用来追溯）

### Part 3 拦截矩阵和下一步（目标 12 分钟）

坑：
- 顺序看 FLOW_ORDER（流程图），不看 WORKBENCH_SURFACES（表格），也不看 failure 自己列出 catchers 的顺序。`forbidden write` 的 catchers 是 review、instructions、scope：按表格顺序会给 instructions，按列出的顺序会给 review，正确的是 scope。
- 只记第一个拦住它的面；counts 里七个面都要有，包括 0。
- 没有任何面为它而建的失败（wrong acceptance criteria）在七面齐全时也会逃逸。
- next_surfaces 是贪心：每一轮只数还在逃逸的失败，加上一个面后重算。静态地数“这个面能拦几种失败”，或者只算第一轮不重算，都会选出 review、verification、scope，正确的是 review、state。从全部失败里扣掉已选的面拦住的，却忘了在场的面已经拦住了一部分，会多选一个 verification。
- 平局按流程顺序：state 在 instructions 前面，按字母或按表格顺序都会反过来。照抄 `Counter.most_common` 会按 catchers 出现的先后破平局：七个面全缺时，第三个会选成 verification，正确的是 feedback。
- 拦不住任何失败的面不选；最多选 limit 个，`<=` 写错会多选一个。候选里忘了排除在场的面不算错：逃逸的失败没有在场的拦截面，在场的面收益总是 0，不会被选中。
- 最后一段是端到端：服务按最新一次体检判断哪些面存在，“最新”按时间点而不是文件最后一行，而且只算 2 分的面。

追问：
- "Is greedy optimal here?"（不一定。这是集合覆盖，贪心只是近似；只挑三个面时可以穷举）
- "Should every failure weigh the same?"（可以按出现频率或严重度加权，比如第 4 关监控到的违规次数）
- "Exercise 3 asks for an eighth surface. What changes here?"（在 FLOW_ORDER 里给它一个位置，并说明它为什么不能并进现有的七个面）

### Part 4 运行事件监控（目标 12 分钟）

坑：
- 事件经过至少一次投递的队列，会乱序，也会重复。要按 seq 顺序检查，每个 seq 只检查一次。按到达顺序检查时：第 9 步的 claim 比第 8 步的 run 先到，会拿第 6 步的通过来判，漏报；end 比 handoff 先到，会报一条假的 handoff 违规；再不去重的话，迟到的第 2 步（exit 1）会让第 7 步的 claim 变成假违规。
- 常见写法是一个按 seq 存的缓冲区加一个 next_seq 指针。迟到的重复事件 seq 小于 next_seq，要直接丢掉；放进缓冲区的话，流结束时会被当成缺口。
- 先把整个流读完再排序：结果对，但探针会抓住。探针先发 seq 2、再发 seq 1，后面还有 297 条；seq 2 的违规要在 seq 1 到达后立刻输出。
- 缺 handoff 的违规在检查 end 时就输出，不等流结束。第二个探针只有一条 end，队列随后一直重投它；把这条违规放到 `async for` 结束后再报，就得先读完 300 条重投。检查完 end 就停止读流也可以：end 是最后一个 seq，它之前的事件都已经查过了。
- 同一个越界路径只报一次，在第一次写入时。越界指 task.allowed_files 以外的所有写入，禁止的文件也算（seq 10 的 scripts/release.sh）；沿用第 1 关“既不允许也不禁止”的口径会漏掉它。
- claim 看它之前最近的一次 run；`exit_code` 为 None（没有捕获）不算通过。`if code:` 会把 None 当成通过。每个 claim 各判各的：quiet 里同一次 exit 1 之后连着两个 claim，两个都报。claim 之后把 last_run 清掉，或者同一次 run 只报一次，都会漏掉第二条。
- 流结束时还有空缺的 seq，要报 ValueError，只写出没到的 5 和 7（到了的是 6、8、9）。直接写 `range(next_seq, max(waiting))` 会把已经到了的 6 和 8 也算进去，写成“seqs 5 to 8”这样的区间也一样。测试的正则要求消息里 5 和 7 之间只隔着非数字字符：前一种写法中间夹着 6，后一种根本没有 7。
- 输出格式由测试决定：每个字符串是一个 JSON 对象，以一个换行结尾。以 `\r\n` 结尾也能通过，`json.loads` 会忽略行尾的 `\r`，可以接受。

追问：
- "The buffer waits forever for seq 5. What do you do in production?"（缓冲区设上限、加超时，把缺口作为违规报出去，或者从持久日志重放）
- "Why does the feedback check read the exit code and not the agent's claim?"（Agent declares success on a 400；证据来自运行时，不来自模型）
- "Where does this monitor run: inside the agent loop or beside it?"（作为单独的 worker 消费队列，不和 builder 共享权限）

### Part 5 线束原语检查（目标 12 分钟）

坑：
- 组件嵌套在 runtime 里，而且可以多层（sandbox 里还有 mcp）。只遍历顶层会把所有指向 sandbox/... 的 ref 报成 unresolved，也查不到 sandbox/runner 没有 policy。
- 函数的路径是 worker 的路径加函数名，比如 sandbox/builder/plan。
- trigger 要经过任意多个 queue 最终到达一个函数。指向 worker（cron）不算；queue 成环（retry 和 retry_later）不算，而且不能无限递归下去。
- 断掉的 ref 报 unresolved，同一个 trigger 也报 no_function。
- 每一种 ref 都要查：trigger 的 to 和 on、queue 的 to、函数的 to。lint_hook 的 on（sandbox/checkout）和 reviewer/review 写入的 review_report 都不存在，只查 trigger 的 to 会漏掉这两条。函数的 ref 报在函数的路径上。
- 闭环要求有一个 durable store 在环上。chat 那个环不 durable，不算；agent_state 被写入但不在环上，也不算。feedback_log 经 on_feedback 触发 act，能走进 chat 的环，但走不回它自己，也不算：“从 store 出发能遇到环”和“store 在环上”是两回事，三色 DFS 的标准写法查的是前者，会把 chat 的环当成闭环；不带 visited 的递归在这里会 RecursionError。trigger 的 on 边方向是 store 指向 trigger；只检查 on 能不能解析、不连这条边，补上 session_end 以后也闭不了环。
- 结果按 (path, code, detail) 排序。lint_hook 有两条 unresolved，sandbox/checkout 排在 sandbox/linter/run 前面；只按 (path, code) 排、又先处理 to 再处理 on，顺序就反了。

追问：
- "Which of the seven surfaces can you read off this description, and which can't you?"（state 看 durable store 是否在环上，scope 看 policy，review 看是否有独立的 worker，feedback 看运行结果是否写进日志、有没有 trigger 把它送回 agent loop；instructions 和完成定义看不出来）
- "The lesson quotes 'the harness belongs outside the sandbox'. How would you check that here?"（授权策略不能由 sandbox 里的组件执行；检查执行 policy 的组件在哪个 runtime）
- "A cycle with no store at all: trigger, function, trigger. Is that a problem?"（是。状态只在内存里，换一个会话就丢了）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出并发、版本、失败处理、证据和权限边界 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
