# 面试官手册：InitProbe（14/35）

候选人计时期间不要看。候选人手里只有 README、`initprobe/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 测试里的 `workbench()`、`Bench` 和它们造出来的探针是工作台的替身：不联网、不起子进程，结果和耗时都由测试决定（`workbench()` 的 dependencies 探针读的是测试在临时目录里建的仓库）。不要改它们。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 仓库根要我自己往上找 `.git` 吗？ | "No. The hook passes the root in, absolute or the way git rev-parse --show-cdup prints it." |
| 1 | 可以先 cd 到仓库根吗？ | "No. Init shares the agent's process. Leave the working directory where it is." |
| 1 | pin_paths 要检查文件存不存在吗？ | "No. It only resolves. The probes that read the files say what's missing." |
| 1 | 探针抛 KeyboardInterrupt 也算 fail 吗？ | "No. Only exceptions from the probe's own code. Ctrl-C and cancellation still stop init." |
| 1 | 慢的 fail 也要加上 slow 的说明吗？ | "No. Only a pass turns into a warn. A fail stays exactly as the probe reported it." |
| 1 | 锁的时间戳比现在晚一点点，能容忍吗？ | "No. A lock stamped in the future is stale, even by half a second." |
| 1 | 指纹要不要把 severity、budget 也算进去？ | "No. Just the manifest text and the set of probe names, as the docstring says. Tell me what else you'd put in a real one, and why." |
| 1 | 指纹能缓存吗？ | "Init is a new process at every start, so a cache is always cold. Make one fingerprint cheap." |
| 1 | 同时最多跑几个探针？ | "No limit here. Every probe runs at once." |
| 2 | 每次运行一个文件，还是一个文件里一行一次？ | "One file, one line per run, appended." |
| 2 | 时间戳能写成人看得懂的格式吗？ | "Your call, as long as the float comes back exactly." |
| 2 | 锁命中、一个探针都没跑的那次要记吗？ | "No. Only runs that probed. InitService already skips the others." |
| 2 | 读到坏行怎么办？ | "Raise ValueError and say which line. Don't skip it." |
| 2 | ready 指什么？ | "exit_code 0." |
| 3 | 结果是 warn 的探针，算不算通过？ | "For the probes that need it, yes. Only fail and skip stop them." |
| 3 | warn 级别的探针失败了，依赖它的探针还跑吗？ | "No. Severity decides the launch, not whether the dependents can run." |
| 3 | 被跳过的 block 探针算不算阻断？ | "Yes. Init can't vouch for a check it didn't run." |
| 3 | info 级别的失败呢？ | "It shows in the results. Never in warnings, never blocking." |
| 3 | 探针配置写错了，退出码是多少？ | "There's no report then. run_init raises ProbeConfigError before anything runs, and the hook exits 2." |
| 3 | 可以按依赖层级一层一层地跑吗？ | "No. A probe starts as soon as its own needs are done." |
| 3 | 跳过原因里列谁？ | "The probes that actually failed, even through a chain of skipped ones. Each once, in list order." |
| 4 | 编号可以乱序出现吗？ | "Yes. Lines come as probes finish. The number stays the probe's place in the list." |
| 4 | info 级别的探针失败了，写 ok 还是 not ok？ | "not ok. A line says what the probe found. Whether that stops the launch is the verdict's job." |
| 4 | 计划行放在哪？ | "After the last probe, then the verdict." |
| 4 | 要不要输出 TAP version 行？ | "No. Plain TAP, no version line." |
| 4 | 探针配置坏了怎么办？ | "One Bail out! line with the error. Nothing runs." |
| 4 | detail 里的 # 要不要转义？ | "No. Only backslash, line feed and carriage return." |
| 4 | 跳过的探针，第一个 need 失败时就发吗？ | "No. Its reason names every failed probe behind it, so it goes out once all its needs have settled." |
| 5 | 要不要识别改名？ | "No. A move is a delete and an add, like git diff --no-renames." |
| 5 | 空目录算不算改动？ | "No. Git doesn't track directories, only files." |
| 5 | 只改了可执行位算吗？ | "Yes, that's a modification. run.sh without its x bit breaks the hook." |
| 5 | LKG 文件自己算不算？ | "No. Nothing under .init/ counts toward the budget." |
| 5 | 刚好 50 个文件呢？ | "That passes. More than the budget fails." |

## 每关：要看什么、提示、追问

### Part 1 修探针运行器（目标 12 分钟）

一个测试里叠了 5 个缺陷：

1. `pin_paths` 用 `Path(rel).resolve()` 按进程的当前目录解析相对路径，`root` 参数根本没用上。测试照 pre-task hook 的样子，从仓库子目录 `src/app` 启动 init。`pin_paths` 不报错，只是把 manifest 钉在了 `repo/src/app/requirements.txt`；错误在读它的 dependencies 探针里露出来，成了这个探针的 fail，detail 是 `FileNotFoundError: [Errno 2] No such file or directory: '…/repo/src/app/requirements.txt'`。探针本身没错，根因在测试一开始调用的 `pin_paths` 里。课里探针表的 Repo paths 一行就是 "resolve them once and pin"。修法是相对 root 解析：`(Path(root) / rel).resolve()`。
2. `_timed` 把所有超过预算的结果都改成 warn，docstring 只让慢的 pass 变成 warn。又慢又失败的 test_command（30ms，预算 10ms）回来是 `warn`，detail 后面还多了 slow 说明。block 探针的 warn 不阻止启动，等于把一个 fail 吞掉了，违反课里的 Fail loud；课里说超过三秒的探针只是 workbench smell，测验 Q6 和代码讲解 3.2 也都说慢的 fail 原样保留。
3. `_timed` 用 `time.time()` 计时。测试在探针运行时把墙钟往前拨 1 小时、再往回拨 2 小时：旧代码算出 3600000ms，把一个瞬间完成的 pass 降成 warn；另一个算出负数。docstring 要求单调时钟，`time.monotonic()` 或 `time.perf_counter()` 都可以。保留 `time.time()`、只把负数截成 0 不够，往前拨的那一小时照样算出 3600000ms。
4. `lock_is_fresh` 只判断 `age < LOCK_TTL_S`。锁的时间戳在未来时（时钟被拨回过，或者有人手改了文件），age 是负数，锁永远新鲜。docstring 写明 age 要在 [0, LOCK_TTL_S) 里。
5. `fingerprint` 每处理一个探针名，就把 manifest 和到目前为止的全部名字重新序列化、哈希一遍，是 O(探针数²)；docstring 规定 manifest 和排好序的名字各哈希一次。monorepo 里每个锁定的包一个探针，5000 个探针写一次锁再查一次，本机约 0.76–0.81 秒，限值 0.05 秒；各哈希一次以后中位数约 0.7ms。指纹的值不变，已经写下的锁照样有效。断言挂在 `write_lock` 和 `lock_is_fresh` 上，根因在它们调用的 `fingerprint` 里，离一层。测试计时前先 `gc.collect()`。

起始代码里有三件事已经做对，相关断言都是护栏：探针抛异常变成它自己的 fail（测试里的 env 探针有自己的 bug，`env["OPENAI_API_KEY"]` 抛 KeyError，detail 是 `KeyError: 'OPENAI_API_KEY'`，照常计时，其他探针照跑）；`run_probes` 用 `asyncio.gather` 一起跑，结果按探针列出的顺序返回；指纹覆盖探针名的集合。

护栏：
- 路径：在 `pin_paths` 里先 `os.chdir(root)` 再按当前目录解析，路径是对了，可 init 和 agent 共用一个进程，工作目录被挪走了，测试会检查它还在 `src/app`。只把 root 和相对路径拼起来、不 resolve，root 是相对路径时（`git rev-parse --show-cdup` 打印的就是 `../../`）钉住的还是相对路径；用 `absolute()` 不去掉 `..`，和从别处钉住的同一个文件比较不相等。照课里代码的 `HERE` 按包自己的位置解析，测试的仓库不在那里。
- 慢的 fail：把 slow 说明加到所有慢的结果上；只把状态降成 warn、detail 不动；在 except 里提前 return（抛异常的 env 保住了 fail，自己返回 fail 的 test_command 照样被降级）；写成 `status != "fail"`（慢的 warn 也加上了 slow 说明，state_freshness 会挂）；用 `asyncio.wait_for` 按预算取消探针（慢的 test_command 变成 TimeoutError 的 fail）。这些都会挂。
- 时钟：换成 `time.process_time()`，sleep 的时间不算 CPU 时间，耗时变成 0，慢探针判不出来。换成 `time.time_ns()` 仍是墙钟，测试一起打了补丁。
- 锁：`abs(age)`、容忍 60 秒偏差、`0 < age`（刚写下的锁不算新鲜）、`age <= LOCK_TTL_S`，都会被边界断言抓住。按整秒算 age（`int(now - written_at)` 或 `round(...)`）会把半秒之后的时间戳算成 0，测试用半秒的偏差抓它。
- 指纹的速度：给慢版本加 `functools.lru_cache` 没用。init 每次启动都是新进程，缓存永远是冷的，测试计的正是一个新探针集合的第一次。只把 manifest 提到循环外面，或者只用一个 hasher、每一步喂进到目前为止的全部名字，仍是 O(n²)。
- 指纹的内容（起始代码已经做对）：名字不排序（列出顺序一变锁就失效）；哈希每个探针的 repr（里面有函数地址，新进程永远对不上）；只哈希探针个数（改名对不上）；用 Python 的 `hash()`（每个进程的哈希种子不同，测试会另起一个进程算指纹来比）；去掉 manifest；把 severity、budget_s 也哈希进去（另起的进程用默认值建探针，指纹对不上，docstring 只要 manifest 和探针名的集合）。
- 异常（起始代码已经做对）：抛异常的探针也要有耗时，在 except 里直接返回耗时 0，或者在 `run_probes` 里用 `gather(return_exceptions=True)` 再补结果，都会挂；detail 用 `repr(exc)`（`KeyError('OPENAI_API_KEY')`）或只用 `str(exc)`（`'OPENAI_API_KEY'`）都不对；`time.process_time()` 也会让抛异常的 env 耗时变成 0。
- 并发（起始代码已经做对）：每个探针单独计时，把整批的耗时发给每个探针，瞬间完成的 runtime 也成了 50ms；换成 `asyncio.as_completed` 按完成顺序收集，会被顺序断言抓住；`asyncio.Semaphore(4)` 限流，200 个 10ms 的探针约 0.6 秒，过不了 0.2 秒的计时。

测试抓不到的：探针名直接拼起来、中间不加分隔符（`"".join(sorted(names))`，或者逐个 `h.update(name.encode())`）也能通过，可 `{"a", "bc"}` 和 `{"ab", "c"}` 会得到同一个指纹。可以问一句怎么让编码没有歧义（JSON 列表，或者每个名字后面加 `\0`）。在 `pin_paths` 里 chdir 到仓库根、解析完再切回去，测试也抓不到；可工作目录是整个进程共享的，这段时间里别的线程按相对路径做的事都会落到别处。

看什么：是不是先看 detail 里的路径，发现多了 `src/app`，再顺着找到 `pin_paths`，而不是去改 dependencies 探针；有没有读 `_timed` 和 `fingerprint` 的 docstring；改完时钟以后有没有再看一眼每个探针的耗时。

提示：
- 路径层：H1 "Which directory does that path point into, and where did the test start init?" H2 "Read pin_paths' docstring: what is a path in the layout relative to?" H3 直接指出 `Path(rel).resolve()` 没用到 root。
- 慢 fail 层：H1 "test_command reported a fail. Who turned it into a warn?" H2 "Read _timed's docstring: which statuses does the budget touch?"
- 时钟层：H1 "What does the duration become if the wall clock moves while a probe runs?" H2 "Which clock in the time module never jumps?"
- 锁层：H1 "How old is a lock written one second from now?" H2 "Read lock_is_fresh's docstring again: which ages are fresh?"
- 指纹层：H1 "Which call inside write_lock and lock_is_fresh grows with the number of probes?" H2 "How many times does fingerprint hash each name?"

追问：
- "Why except Exception and not BaseException?"（Ctrl-C 和任务取消必须还能停下 init。Python 3.8 起 `asyncio.CancelledError` 继承 BaseException，`except BaseException` 会把它吞掉。测试没有覆盖这一点）
- "Why not cd to the repo root at the top of init?"（工作目录是整个进程共享的状态。init 和 agent、hook 共用进程时，挪走它会让后面按相对路径做的事落到别处，asyncio 里并发的探针也会互相影响。钉住绝对路径就不依赖工作目录）
- "Lesson 36 reads the repo paths from the init report. What goes wrong if they are relative, or still carry '..'?"（相对路径换个进程、换个工作目录就指向别处；带 `..` 的路径和 scope contract 里的路径按字符串比不相等，在不在某个目录下的判断也会出错）
- "Each of the 200 probes forks a subprocess. Still gather them all?"（不行，要限流，比如 Semaphore；但计时要从拿到许可之后开始，否则排队时间也算进探针耗时，探针会被误判为慢）
- "The lock trusts a passing run for 24 hours. What else should make it stale?"（课里测验 Q9：失败的运行要删锁，`InitService` 已经这样做；必需环境变量是否存在、解释器路径和版本、探针代码自身的版本也应该进指纹。只哈希“存在与否”，不哈希 secret 的值）
- "The lesson's Exercise 2 refuses to start when the lock is older than seven days. How is that different from the 24-hour TTL?"（TTL 过期只是重新探测；七天是拒绝启动、交给人确认，是两道不同的闸门）
- "Someone times probes with datetime.now(). Does the test catch it?"（抓不住，那也是墙钟。说明测试只是证据，不是证明）

### Part 2 运行历史（目标 10 分钟）

格式本身的要求，测试会检查，但不算这一关设计的陷阱（本章别的课已经考过）：一次运行一行 JSON（不能照抄 `to_json()` 的 `indent=2`）；append 返回时这一行已经在磁盘上，另一个对象马上能读到（文件句柄一直开着又不 flush，读者看不到）；`runs()` 每次都读磁盘上的现状，第一次读完就缓存起来的话，后来追加的运行看不到；用 `"w"` 打开会把之前的运行冲掉；重新打开后之前的运行都在；结果按探针列出的顺序。

坑：
- 时间戳要原样回来。写成 ISO 8601 或者 `round(ts, 6)`，`1761955200.1234567` 读回来是 `1761955200.123457`。JSON 的 float 本来就能精确往返。
- 耗时是整数毫秒。存成秒再乘回 1000，读回来是 float；用 `int()` 截断时，1003ms 会变成 1002ms。测试用 `typed()` 连类型一起比。
- 读回来的要是 `Result` 和 list，不能是 dict 或 tuple。
- 用 `read_text().split("\n")` 读，文件末尾的换行会多出一个空行，被当成坏行。
- 文件还不存在时 `runs()` 返回空列表，不能抛 FileNotFoundError。
- `last_ready()` 要最后追加的那一次 ready，不是第一次，也不是最后一次运行（可能没 ready），也不是时间戳最大的那一次：测试最后追加的 ready 运行发生在时钟被拨回之后，时间戳反而更早。`runs()` 同样按追加顺序，不能按时间戳排序。
- 先检查再写。先写后检查，被拒绝的那次已经留在文件里了。
- 校验：负的耗时（Part 1 那个时钟 bug 的产物）、非整数的耗时（包括秒）、未知状态都要拒绝。只检查是不是数字，或者先 `round` 再检查，都会放过 2.5。合法状态有四个，包括 skip：照 `Probe` 的 docstring 只认 pass、warn、fail 的话，追加带 skip 的 BLOCKED 时就报 ValueError。
- 坏行要报 ValueError 并带上文件里的行号（`line 6`）。跳过坏行会挂；把 KeyError 原样抛出会挂；JSON 自己的错误信息里那个 “line 1” 是字符串内的行号，不是文件的行号；行号从 0 数也会挂。

测试抓不到的：跳过空行也能通过，空行里没有运行，可以接受。耗时存成秒、读回来用 `round()` 能精确还原，测试也抓不到，但字段叫 `duration_ms`、存的却是秒，读文件的人会被坑，值得问一句。

追问：
- "Two init processes append at the same time?"（本地文件系统上，用 `O_APPEND` 打开、一行只用一次 write 写完，各进程的行不会互相覆盖；Python 的缓冲写入要保证一行只落一次 write，要更稳就加 `fcntl.flock`。NFS 上不能指望 `O_APPEND`）
- "init is killed halfway through an append. What happens next time?"（最后一行不完整，这里的实现会报错。可以在打开时截掉不带换行的尾巴，或者只容忍最后一行；这是在“fail loud”和“历史还能用”之间的取舍）
- "The history grows forever. Then what?"（按大小或日期轮转，保留最近 N 份；`last_ready` 要能跨文件找）
- "Why JSON lines and not SQLite?"（追加写不改旧数据，grep、tail -f、人眼都能读；坏一行只影响一行。要按条件查询、要并发写，再换数据库）

### Part 3 探针编排（目标 14 分钟）

坑：
- 跳过要沿依赖链传递。只看 `status == "fail"` 的话，smoke 需要的三个探针都是 skip、没有一个是 fail，smoke 会照跑。
- 跳过原因要写失败的那个探针，不是中间被跳过的那个：smoke 是 `needs git, dependencies`，不是 `needs test_command, lkg_diff, lint`。这就是 fail in one place，人只需要看一个地方。
- 名字按探针列出的顺序排。字母序（`dependencies, git`）、needs 的顺序（`dependencies, git`）、失败发生的先后（两次运行不一样）都不对。同一个失败经两条路径传过来只写一次。
- 被跳过的探针不能执行，耗时是 0。先执行再把结果改成 skip 会挂；从开始等待算起的耗时也会挂。
- 结果、blocking、warnings 都按探针列出的顺序，不按完成顺序。测试用两张不同的延迟表各跑一次，要求 `to_json()` 除时间戳外逐字相同，这就是课里说的幂等。
- severity 的含义：block 级别的探针失败或被跳过都算 blocking；被跳过也算，因为 init 没法为没跑过的检查担保。git 是 warn 级别，它失败了，lkg_diff（block）被跳过，照样拒绝启动。
- 其余不是 pass 的都进 warnings，包括 block 探针的 warn（慢的 test_command）、warn 级别探针的 fail 和 skip（smoke）；info 级别的探针只出现在 results 里。只看 warn 级别的探针，或者漏掉 skip，都会挂。blocking 和 warnings 不重叠：两个 if 分开写，阻断的探针也会进 warnings。
- exit_code 只看 blocking：有就是 1，没有就是 0。warn 不阻止启动；不能用 blocking 的个数当退出码。
- 结果是 warn 的探针，对依赖它的探针来说算完成：慢的 test_command 之后 smoke 照跑。
- 依赖失败就跳过，不管失败的是什么级别：lint 是 info，它失败了，smoke 也要跳过。
- 调度：一个探针在它自己的 needs 都完成后立刻开始，不等同一层的其他探针；没有依赖的探针一起跑。测试把 env 卡住，要求 test_command 和 coverage 在 env 还没完成时就已经开始。按层跑、或者按拓扑序一个个跑都会挂。
- 校验必须在任何探针开始之前做完：未知依赖如果拖到运行时才发现，通常报 KeyError；依赖成环不检查会永远互相等待，测试一秒后超时；重名不拒绝的话，按名字索引的结构会互相覆盖，结果要么少一个、要么卡住；severity 写错（`critical`）要拒绝，不能悄悄当成 warn。这些都要报 ProbeConfigError，而且一个探针都没跑；抛普通的 ValueError，测试和 hook 都接不住。
- 查环要分清“在当前路径上”和“已经查过”。只查自己依赖自己，三个探针绕一圈照样互相等待；只用一个 visited 集合、碰到见过的就报环，又会把共享的依赖当成环：git 已经作为顶层探针查过，lkg_diff 再走到它就报错；smoke 经 test_command 和 lint 两条路也都会走到 dependencies。课里这套正常的探针会被整套拒掉。
- 报告的 timestamp 是传进来的 now，不是现在的墙钟；fingerprint 是 `fingerprint(manifest, probes)`。
- 最后一段是端到端检查：`InitService` 把 Part 1 的锁、Part 2 的历史和这一关的 `run_init` 串起来。被拒绝的运行要删掉锁，所以下一次普通运行会重新探测（测验 Q9 的那个洞）。

测试抓不到的：在 `run_init` 里加一个 Semaphore 限并发，上限不低于 2 时这一关能通过（Part 4 同时卡住两个探针，和 TAP 共用调度时上限 2 会在那里挂）。docstring 要求没有依赖的探针一起跑，可以问为什么要加，计时又从哪一刻算起。

追问：
- "Why does a skipped block probe block, when nothing it checks has failed?"（课里：init 的意义就是工作台坏了时拒绝启动。没跑的检查就是没验证过；代码里的 git 不可用只给 warn，在没有 git 的机器上漂移预算形同虚设）
- "A probe hangs forever. What does this design do?"（预算只计时、不打断，会一直等。需要另加一个硬超时，超时记为 fail，和“慢”的预算分开）
- "Lesson 33's rule checker runs after this. What does it read?"（读 init_report.json。规则说什么必须为真，init 让这些规则能被检查：Init without rules becomes a polished failure）
- "Why keep durations out of init_report.json?"（报告要幂等，agent 和 hook 会比较它；耗时在每次运行都不同，放进历史里）

### Part 4 TAP 流（目标 12 分钟）

坑：
- 编号是探针在列表里的位置，开跑前就定好，不按输出先后编号。测试里第一行是 `ok 2 - runtime`，不是 `ok 1`。编号从 1 开始，直接用下标（从 0 数）也会挂。
- `ok` 和 `not ok` 只看状态，不看 severity，也不看挡不挡启动：fail 是 not ok，pass 和 warn 是 ok。warn 级别的 git、info 级别的 coverage 失败了，照样是 not ok；最后一段里慢了的 test_command 是 block 探针的 warn，照样是 ok。挡不挡启动是结论行的事，测验 Q10 讲的就是这两个维度：status 是探针看到了什么，severity 是失败了该不该拦。跳过写成 `ok N - name # SKIP 原因`，被跳过的 block 探针也是 ok；SKIP 大写，后面直接是原因，不带冒号、不带耗时，也不能当成第四种状态写成 `# skip 0ms …`。warn 写成 not ok、跳过写成 not ok、只给挡住启动的失败写 not ok、block 探针的 warn 或跳过写成 not ok、`SKIP:` 带冒号、小写 skip、跳过行带耗时、写成 skip 状态，都会挂。
- 探针配置坏了（Part 3 的 ProbeConfigError）：整个流只有一行 `Bail out! 原因`，以换行结尾，一个探针都不跑，异常也不从流里抛出去。TAP 的 Bail out! 就是为这种情况准备的：解析器读到它就停下，后面的文字就是原因，读 CI 日志的人只看这一行，这是 fail fast、fail in one place。让异常抛出去，日志里是半截流加一段堆栈；测验 Q11 第 2 问说过，这不是结构化的失败。直接让 ProbeConfigError 抛出去会挂；yield 完 Bail out! 忘了 `return`，生成器接着去跑这套坏配置，异常照样抛出来；只写 `Bail out!` 不带原因、少了换行、换成 TAP 跳过整个文件的 `1..0 # SKIP 原因`、只打印到 stderr 而流里什么都没有，也都会挂。
- 一个探针一结束就输出它的那一行，跳过的也一样，它的 needs 都结束了就输出。测试把 env 和 coverage 卡住，要求在它们结束前已经收到 8 行。全部跑完再输出、只把跳过的攒到最后、按编号顺序等前面的行，都会挂。也不能更早：smoke 的原因是 `needs git, dependencies`，第一个 need 一失败就发，只写得出 `needs dependencies`。
- 计划行 `1..10` 和结论放在最后。计划行放在开头在 TAP 里是合法的，但 docstring 规定放在最后。多一行 `TAP version 13` 也会挂。计划行数的是全部探针，跳过的也算，只数跑过的会写成 `1..6`。
- 结论里的 blocking 按列表顺序，不按完成顺序，规则和 `run_init` 一样（info 不阻断，skip 的 block 阻断）。漏掉被跳过的 block 探针，结论就只剩 `dependencies`。
- 每一项都以换行结尾，一项只有一行。
- docstring 写明了 detail 怎么转义：先把反斜杠写成 `\\`，再把换行写成 `\n`、回车写成 `\r`，别的字符（包括制表符和 `#`）不动。照着 docstring 做就行，测试只是顺带检查：git 那条 detail 里有回车、制表符和 `C:\new`，state_freshness 里有 em dash，测试的 unescape 很严格。只转义换行，回车会把一行拆开；不转义反斜杠，`C:\new` 读回来是 `C:` 加换行加 `ew`；先换行后反斜杠会转义两次；用 `json.dumps` 或 `repr` 会多出 `\"`、`\t`、`\u2014`；把换行换成空格、把 `#` 或制表符也转义、先把 `\r\n` 合并成一个 `\n` 再转义，也都会挂。
- 骨架是只有 raise 的 `async def`，测试报 `'coroutine' object has no attribute '__anext__'`，要看出这里需要 async generator。

测试抓不到的：Bail out! 的原因前面多一个异常类型名（`Bail out! ProbeConfigError: lkg_diff needs git, …`）也能通过。docstring 只要求说出哪里坏了，可以接受。

追问：
- "Why number by list position instead of finish order?"（编号成了探针的稳定 id，两次运行的 TAP 可以按编号对比；代价是有些 TAP 解析器会对乱序编号发警告）
- "coverage is info and never stops the launch. Why is its line not ok?"（每一行说的是这个探针看到了什么，挡不挡启动是结论行的事。把 severity 混进 ok/not ok，CI 里数 not ok 的人就看不见 info 级别的失败，等于悄悄吞掉了，违反 Fail loud）
- "Why Bail out! instead of letting ProbeConfigError propagate?"（流的读者是 CI 日志和 TAP 解析器。异常让流断在半截，原因埋在堆栈里；Bail out! 让解析器停下，原因就在这一行上。pre-task hook 那边用退出码 2 说同一件事）
- "Lines can arrive out of order. How does a CI log reader rebuild the table?"（按编号放回去；计划行告诉它一共有多少个）
- "The reader goes away halfway. What should happen to the probes still running?"（生成器关闭时取消剩下的任务，不要让它们在后台继续跑；这套题没有测）
- "TAP 13 has YAML diagnostics. Would you use them for details?"（可以把多行 detail 放进缩进的 YAML 块，不用转义；代价是解析更复杂，一行一条的 grep 也没了）

### Part 5 LKG 差异（目标 12 分钟）

坑：
- oid 相同的子树里文件完全一样，整个跳过，不读。先把两棵树全部展开再比较，读 124 棵树；读 blob 内容来比较也会多读；连根都要先比 oid，两棵相同的树一棵都不读。
- 同一个名字一边是目录、一边是文件：目录下的每个文件都算增或删，文件本身也算一次。当成一次修改会挂，目录照样走下去、只把文件那一侧记成 M 也会挂；把那个文件当成树去读，报 `is a blob, not a tree`。
- 只列文件，目录本身从不出现。新增、删除的目录，以及空目录（`cache`、`build/tmp`、`tools/empty`），都不是改动。
- 只改了可执行位（run.sh 从 100644 变成 100755）是 M。只比 oid 会漏掉；当成删加也不对。
- 移动按删加计：`src/lib/mod07.py` 是 D，`src/core/mod07.py` 是 A。util.py 和 helpers.py 内容一样，也是一删一加。做改名检测会挂。
- 结果按完整路径排序。按 (状态, 路径) 元组排序不对；按目录里的名字顺序递归、最后不排序也不对，因为 `a/x.py` 要排在 `a-b.txt` 和 `a.txt` 之后（`/` 比 `-` 和 `.` 大）；按路径分段排序（`split("/")`）同样会把 `a/x.py` 排到前面。照 git 的树顺序（目录名后面加 `/`）递归、最后不排序，平常是对的，但在 `notes` 上会错：路径顺序是 `notes`、`notes.md`、`notes/a.md`，一个名字一边是文件、一边是目录时，按 git 顺序走不出这个位置。
- 预算：刚好等于预算是 pass，超过才 fail。
- init 自己的文件在 `.init/` 下，不计入预算（测验 Q11：LKG 文件被自己提交进去，51 个文件报成 52 个）。用 `startswith(".init")` 会把 `.initrc` 也排除掉；用 `"/.init/" in path` 又匹配不到根目录下的 `.init/`。排除只在 `lkg_drift` 里做，`diff_trees` 照样列出 `.init/` 下的文件。
- detail 里是 LKG 提交的前 7 位，不是 HEAD 的；默认预算是 50。
- 还没有 LKG 是 warn；LKG 提交在仓库里找不到是 fail，要人重新指定基线。代码里对无效提交只给 warn，测试要求 fail。直接抛 KeyError 也不对。

追问：
- "Why walk trees instead of shelling out to git diff --name-only?"（git 做的就是同样的树比较；在内存里做，测试不依赖 git 和真实仓库。真实场景用 `git diff --name-only --no-renames <lkg> HEAD`）
- "git diff renames by default. What changes for the budget?"（开着改名检测时，`--name-only` 只列新路径，一次移动算一个文件）
- "Uncommitted changes and untracked files?"（测验 Q11：只比两个提交会漏掉工作区。和工作区比，再加上 `git ls-files --others --exclude-standard`）
- "A legitimate refactor touches 300 files. Init refuses. Now what?"（人审查、合并、测试通过以后，重新指定 LKG 基线。不要把预算调大或者删掉 LKG 文件；可以按目录分别设预算）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出路径钉住、时钟、缓存失效、并发与取消、追加写的原子性、基线审批 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
