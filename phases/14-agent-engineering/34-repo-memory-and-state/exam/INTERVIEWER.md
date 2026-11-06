# 面试官手册：Statefile（14/34）

候选人计时期间不要看。候选人手里只有 README、`statefile/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 测试里的 `Crash`、包住 `os.fsync` 和 `os.replace` 的 monkeypatch、脚本化的 turn 和“人工编辑”都是外部世界的替身，不要改它们。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | validate 要报出所有错误，还是第一个就停？ | "The first one, with its JSON path, as it does now." |
| 1 | 1.0 算 integer 吗？ | "No. It's a number. An integer is an int that isn't a bool." |
| 1 | 任务里能带 schema 没列出的字段吗？ | "Yes, unless the schema says additionalProperties: false. The state schema says it, tasks don't." |
| 1 | NaN 或 Infinity 能当时间戳吗？ | "No. JSON has no NaN or Infinity, so they aren't numbers." |
| 1 | enum 的键和缓存需要自己实现吗？ | "No. The typed key and per-call index are supplied correctly. The schema may change between calls." |
| 1 | 多个 changes 中最后一个不合法，前面的能保存吗？ | "No. One request is one state transition. Refuse all of it." |
| 1 | update() 什么都不改时呢？ | "Load and validate the current state, return it, and do not replace the file." |
| 2 | 要支持 Windows 吗？ | "No. macOS and Linux only." |
| 2 | 每次保存都 fsync？很慢。 | "Yes. This file is the system of record. The directory too, after the rename." |
| 2 | 崩溃的那次保存能不能自己删掉临时文件？ | "If it gets the chance, sure. kill -9 gives it none, so opening the snapshot cleans up." |
| 2 | 同一目录里别的文件的临时文件呢？ | "Leave them. A save of that file may still be running." |
| 2 | 什么叫“没有变”？ | "Byte for byte the text save would write. Not Python equality." |
| 2 | 文件坏了，修复还是从空状态开始？ | "Neither. Raise CorruptSnapshot and leave the file for a human." |
| 2 | 新文件用什么权限？ | "NEW_FILE_MODE, 0o644. An existing file keeps its own bits." |
| 3 | 没有 schema_version 的文件算 v1 吗？ | "No. No version, no load: VersionError." |
| 3 | migrate 要不要在每一步之后自己设 schema_version？ | "No. Each step returns the next version's document, and the schema check catches one that doesn't." |
| 3 | 支持降级吗？ | "No. VersionError." |
| 3 | 已经是最新版本，还要验证吗？ | "Yes. A current file that breaks its schema is still refused." |
| 3 | 升级前要不要留一份备份？ | "Not in this session. Tell me how you'd do it." |
| 4 | 会话是真的进程吗？ | "Tasks in one event loop. Tell me what changes with processes." |
| 4 | turn 拿到的是什么？ | "A fresh copy of the state that attempt read. It returns the new state." |
| 4 | 冲突那一行的 revision 写哪个？ | "The one found on disk." |
| 4 | 会话按什么顺序开始？ | "In the order given." |
| 4 | turn 抛异常怎么办？ | "The stream ends with that error. The tests don't cover it." |
| 5 | 迁移图会有环吗？ | "Never. Every migration goes to a higher version." |
| 5 | “最短”怎么算？ | "Fewest migrations. Not the smallest jump in version numbers." |
| 5 | 一样短怎么选？ | "Read the versions along each path in order and compare them as integers. The smaller one wins." |
| 5 | disagreements 里结果怎么比较？ | "With ==." |
| 5 | 某条路径中途验证失败呢？ | "Let the error propagate." |

## 每关：要看什么、提示、追问

### Part 1 修状态管理器（目标 12 分钟）

一个测试里叠了 4 个缺陷和一组护栏：

1. JSON Schema 有 7 个类型名，`_check_type` 只认识其中 5 个，没有 number 和 boolean，讲义的代码讲解把这叫“静默的子集”。错误不在 `_check_type` 报出来，而是两层调用之外：测试调 `update`，`update` 先 `load` 人手改过、带浮点时间戳的文件，`validate` 报 `$.last_human_touch: expected ['number', 'null'], got float`。看起来像是人把文件改坏了，其实文件是对的。
2. pattern 用 `re.match`：只锚定开头，`$` 还能匹配结尾换行之前的位置，`"T-001\n"` 能过 `^T-\d{3,}$`（测验 Q8）。不带 `^ $` 的 pattern 更糟，`"T-001-old"` 也能过。docstring 要求整个字符串匹配。
3. 对象里多出来的键一律拒绝，相当于处处写了 `additionalProperties: false`（测验 Q5）。docstring 规定只有 schema 写了才拒绝；状态 schema 写了，任务没写，所以带 `estimate_h` 的任务被拒。
4. `update` 把一个 changes 请求拆成逐字段 commit。前面字段已验证并写入，后面字段非法时虽报拒绝，文件却留下了前缀；每个字段又重复编码、fsync、替换整份状态。先合并所有字段，再调用一次 commit，才符合“bad write is a refused write”。256 个组件检查结果、既有 2000 条 touched_files 的有限状态共 80,369 字节，逐字段真实提交三次为 0.255894 / 0.471284 / 0.256397 秒，整批为 0.002064 / 0.003418 / 0.001899 秒，限值 0.03 秒；两侧最差余量 8.53 / 8.78 倍。
5. 护栏：
   - number 不能收 bool（`isinstance(True, int)` 为真），也不能收 NaN 和 Infinity；整数时间戳要收。只认 float 的话，`last_human_touch=1762002000` 被拒；只用 `math.isnan` 排除 NaN 会放过 `float("inf")`，docstring 写的是有限的 float。对 int 也直接调 `math.isfinite` 能过测试，只有超过 1e308 的整数会让它抛 OverflowError，可以顺口问。
   - boolean 写成 `value in (True, False)` 会收下 1。
   - 照 JSON Schema 规范让 integer 收 1.0：docstring 说 1.0 是 number 不是 integer，`schema_version: 3.0` 要拒。
   - pattern 换成 `re.search`、先对值做 `strip()`、在 pattern 后面拼 `\Z`（顶层的 `|` 让它失效）都会被抓住。
   - 干脆删掉多余字段检查：状态里多出 `last_run` 也写进去了。
   - 不改 validate，把 `estimate_h` 和 `labels` 补进 BOARD_SCHEMA：任务板能过，但测试另有一个没写 additionalProperties 的小 schema，多出来的 `sprint` 照样被拒。
   - 类型化 enum 与每顶层调用缓存已经正确给定。给定实现的语义护栏包括：`set(options)` 会混同 True 与 1，Python 类型名会拆开 2 与 2.0，对象键顺序不能影响相等。候选人无需重新实现这些 helper。
   - 给定 enum 缓存只活在一次顶层调用。给定实现的护栏包括大仓库性能断言和同一列表内重命名的动态 schema 检查；跨调用按 id 或 id 加长度缓存，仍会被边界断言抓住。
   - 多字段更新不允许先写合法前缀、等发现非法字段后再报错；预先验证全部、却反复写同一最终状态，也违反一次 replace 的合同。空 changes 仍需 load 验证，但不创建新的快照。

看什么：是不是顺着 `update` / `load` 的 traceback 找到类型检查；是不是一次修一层；是否把一次请求视为一个完整状态转换；遇到慢更新时是否先数真实编码、fsync 和 replace 的次数。

提示：
- 类型层：H1 "A human edited that file. Is it really wrong?" H2 "What does _check_type do with 'number'?" H3 直接指出 `_check_type` 少了 number 和 boolean 两个分支。
- pattern 层：H1 "What can $ match in Python?" H2 "Which re function makes the whole string match?"
- 多余字段层：H1 "Which schema says extra keys are refused?" H2 "Read the additionalProperties line in validate's docstring."
- 批量更新层：H1 "The last field is invalid. What is already on disk?" H2 "How many complete snapshots does one changes request write?" H3 "Merge the request in memory, then validate and commit its complete result once."

追问：
- "Why not just use the jsonschema library?"（可以，课里说它是可选的。要先弄清本课验证器和标准语义不同的地方：多余字段、integer 收不收 1.0、`$` 的含义。换库之前，拿同一批例子对比两边的结论，测验 Q5 就是这么做的）
- "The repo tracks 200,000 files. Is an enum still the right tool?"（schema 会变得很大，每次写都要带着；更好的是 schema 只管形状，“是不是被跟踪的文件”交给单独的检查，读 `git ls-files` 得到的集合）
- "Should validate report every error at once?"（对 reviewer 更友好，像 jsonschema 的 iter_errors；代价是代码更复杂，第一个错误之后的错误常常是连带出来的）
- "Where else does True == 1 bite in this code base?"（dict 的键、set、`in`、`==`。Part 2 判断“没变就不写”时也会遇到）

### Part 2 崩溃安全的快照（目标 14 分钟）

坑：
- 格式由测试固定：UTF-8、缩进 2、键按文档里的顺序、非 ASCII 原样写、结尾一个换行。`sort_keys=True` 看起来对 diff 友好，其实人手调过的键顺序每次保存都被打乱；`json.dumps` 默认把非 ASCII 转成 `\u` 转义，reviewer 在 diff 里看不懂。
- NaN 不是 JSON：要 `allow_nan=False`，否则文件里写进 `NaN`，jq 和 JS 都读不了。读的时候也要拒绝，Python 的 `json.loads` 默认会收下 `NaN`。
- “没变就不写”要比字节。`==` 认为 1 和 True、-0.0 和 0.0、键顺序不同的 dict 都相等，会漏掉真实的修改；在内存里记住上次写的内容也不行，人可能在中间改过文件。
- 临时文件必须和目标在同一目录（rename 只在同一文件系统内是原子的），名字是 `<文件名>.<随机>.tmp`，打开时才能认出来清理。换名字用 `os.replace`，docstring 和讲义都这么写：`os.rename` 在 POSIX 上一样是原子的，但在 Windows 上目标已经存在时会失败；测试只看 `os.replace`。
- 顺序是写入、flush、chmod、fsync 文件、rename、fsync 目录。不 flush 就 fsync，字节还在 Python 的缓冲区里，fsync 的是一个空文件，关文件时才真正写进去；先 rename 再 fsync，断电后可能得到一个空文件；不 fsync 目录，rename 本身可能丢（测验 Q12）。测试包住 `os.fsync` 和 `os.replace`，记下 fsync 那一刻文件的 inode 和大小来检查顺序，还会在 fsync、rename、目录 fsync 三处模拟崩溃。
- 权限：`mkstemp` 总是 0600，替换以后别人读不了状态文件（测验 Q12）。新文件给 0o644，已有文件保留原来的权限位。权限要在 rename 之前设在临时文件上：rename 以后再 chmod，中间那段时间文件是 0600，进程死在这里就一直是 0600。测试在 rename 那一刻读临时文件的权限。
- 打开时清理，只删 `<文件名>.*.tmp`：按前缀删会删掉人留的备份 `agent_state.json.orig`；按 `.tmp` 后缀删会删掉别的文件正在写的临时文件；按子串匹配会删掉 `old.agent_state.json.*.tmp`。只在 `except Exception` 里清理、打开时不清理的话，`kill -9`（测试里的 `Crash`）留下的临时文件就一直在。
- 编码失败（set、NaN）要发生在创建临时文件之前，或者失败时删掉临时文件。先 mkstemp 再编码会留下垃圾。
- 坏文件：截断的 JSON、空文件、非法 UTF-8、`NaN`、`-Infinity` 都报 CorruptSnapshot。`UnicodeDecodeError` 也是 ValueError，可它不是 CorruptSnapshot，要包一层；`errors="replace"` 会把坏字节悄悄换掉。不能返回空状态（讲义里 Hive 的 bug），也不能把坏文件挪走。
- 测试抓不到的：新文件的权限按 umask 算（`0o666 & ~umask`），本机 umask 是 022，正好是 0o644，可 docstring 要的是 NEW_FILE_MODE，可以问 umask 是 077 时会怎样；按文本判断没变（`read_text() == text`），合法的文件上和按字节比一样，但文件里有非法 UTF-8 时 save 会抛 UnicodeDecodeError，坏文件就再也存不过去了。

追问：
- "Two writers save at the same moment?"（rename 保证文件完整，但后写的覆盖先写的，也就是 Part 4 的丢失更新）
- "How would you test a real power cut?"（在虚拟机里断电，或者用会丢写入的故障注入文件系统；进程内只能模拟“死在这一行”）
- "What breaks on Windows?"（目标被别的进程打开时 os.replace 会失败，要重试；目录不能 fsync；权限位的含义不同）
- "Why not start from an empty state when the file is corrupt?"（状态文件是 system of record。自动“修复”正是讲义里 Hive 的 bug：会话在空状态上继续跑，没有任何信号，已经完成的工作会被重做）

### Part 3 迁移链（目标 10 分钟）

坑：
- 一步一步走：v1 到 v3 必须经过 v2。直接调 `migrations[target - 1]` 的话，v2_to_v3 拿到的是 v1 文档，报 `missing required field 'risks'`。
- 先用文档自己版本的 schema 验证输入，再跑任何一步。测试里的 spy 会记下跑了几步。已经是目标版本的文档也要验证：直接交回一份拷贝的话，坏的 v3 文件照样被加载。
- 每一步的结果都用下一个版本的 schema 验证，schema_version 也在内。只在最后验证一次的话，lossy 那一步丢掉的 next_action 被下一步补回来，看不出来；migrate 自己改 schema_version 的话，jumps 那一步自称 v3 也看不出来；照测验 Q10 的写法跟着步骤自报的 schema_version 往下走、用自报版本的 schema 验证，leaps 一步做完两次升级也能过，v2→v3 那一步被跳过了。
- 不能改调用方的文档。迁移脚本会改传进来的对象，测试里的 annotate 还会往嵌套列表里追加，所以浅拷贝不够，要 deepcopy。已经是目标版本时也要交出一份拷贝。
- 版本拒绝：没有 schema_version、字符串 "1"、0、比代码新的 4、降级、缺一步，都是 VersionError。把缺失的版本当成 1 正是课里 skill 文件拒绝的做法（没有 schema_version 的 schema 不该存在）。缺一步不能让它变成 KeyError。
- upgrade_file 只写一次、原子地写、版本变了才写；任何一步失败，文件一个字节都不变，异常照样抛出去。每一步写一次的话，第二步失败时文件停在了 v2；返回值是（找到的版本，现在的版本），顺序不能反。
- 测试抓不到的：upgrade_file 写成紧凑的 JSON（`json.dumps(out)`），文件照样读得回来，但和 StateManager 写的格式（`dump_state`，缩进 2、结尾换行）不一样，第一次升级的 diff 会是整个文件。可以问。

追问：
- "The lesson's tools/migrate_state.py runs on every startup. What makes that safe?"（幂等：已是最新版本就什么都不做；原子写；失败不留半成品）
- "A migration with a bug has already run on 50 machines. Now what?"（再发一个修正迁移，不改已经发布的那一个；迁移前留备份；把历史版本的样例文件加进回归测试）
- "How do you rename a field while old and new code run side by side?"（扩展再收缩：先加新字段、同时兼容旧字段，下一个版本再删旧字段，测验 Q17）

### Part 4 多会话 CAS 提交（目标 12 分钟）

坑：
- CAS 要在提交时重新读磁盘上的修订号。在 RevisionFile 实例里记住修订号的话，另一个实例的提交它看不见，两个句柄的那段测试就会丢失更新。
- 冲突以后要重读，并且在新状态上重跑 turn。把第一次 turn 的结果用新修订号再提交一次，修订号对了，另一个会话的修改却丢了；只在会话开头读一次也一样。
- 每个会话最多 max_attempts 次尝试，最后一次冲突报 gave_up，而且什么都不写。第二段测试传的是 `max_attempts=2`：少一次、多一次、写死 3 次、最后一次仍写 conflict，都会被抓住。planner 被调用第三次时直接报错，只要 turn 的异常能传到流上，一直重试下去的写法也不会卡住。
- 冲突行里的 revision 是在磁盘上看到的那个，不是自己期望的那个，也不是 base + 1：第二段测试里人每次存两遍，磁盘上的修订号比 base 大 2。
- 每次尝试一有结果就要输出：builder 的每次 turn 都要等测试拿到上一行才放行。攒到最后再输出、一个会话跑完再跑下一个、每个会话结束时才交出自己的几行，都会超时（`each attempt is reported as soon as it is decided`）。
- commit 要用 atomic_write 写，docstring 写了这一点。直接 `write_text` 的话测试看不到 `os.replace`，报 `a commit replaces the file atomically`。
- 格式由测试的解析代码决定：每次尝试恰好一行 JSON，以一个 `\n` 结尾。少换行、多空行、`indent=2` 都不行。
- 骨架里的 run_sessions 是只有 raise 的 `async def`，测试会报 `'coroutine' object has no attribute '__anext__'`，要看出这里需要 async generator。

追问：
- "These are tasks in one process. What changes with real processes?"（读、比较、写之间可能被别的进程插进来：要么用锁文件（`O_CREAT | O_EXCL`）或 `fcntl.flock` 包住这三步，要么换成自带事务的存储，比如课里练习 4 的 SQLite）
- "Why isn't the atomic rename enough here?"（rename 只保证文件不会写坏，不保证不丢更新。skill 文件的原话是 atomic rename is necessary but not sufficient）
- "A session gave up. What should the agent do next?"（不能悄悄丢掉：把冲突交给人，或者稍后重试；可以把它想做的修改写进事件日志，事后再合并）
- "Why rerun the turn instead of merging the two states?"（通用合并要懂语义：两个会话都改了 next_action 时谁赢？重跑 turn 让 agent 在最新状态上重新决定；只有可交换的修改，比如往集合里加元素，才适合自动合并）

### Part 5 迁移图寻路（目标 12 分钟）

坑：
- 最短按步数，用 BFS。DFS 找到的第一条路径不一定最短；只取字典序最小、不管长度的话，会选 [1,2,4,5]，而不是走捷径 [1,4,5]。
- 一样短时按版本序列比较：邻居要排好序再展开，父节点取第一次发现它的那个。按注册顺序展开时 1→3 先注册，会选 [1,3,4]；把队列换成栈也会选错。
- 起点等于终点时返回 []，不是报错。
- 不可达（兄弟分支、降级、没有 schema 的版本）报 VersionError。
- upgrade 先用文档自己版本的 schema 验证，再跑任何一步。测试给了一个 touched_files 为 null 的 v1 文档，不验证、或者只验证最后的结果，都会被抓住。
- disagreements 要跑所有路径，每条路径从自己的 deepcopy 开始。迁移脚本会 pop 键，tidy 那条捷径还会原地 sort 列表：所有路径共用一份文档，第二条路径就 KeyError；每条路径只做浅拷贝，捷径的 sort 会改到调用方的列表，所有路径看起来都一致了。
- 不能按版本缓存中间结果。同一个版本从不同路径到达，内容可能不同，这正是要查的东西。lossy_merge 只在 3→4 这条边上出错，按版本 4 缓存时它被 2→4 的结果盖住了。
- 结果里不放计划路径本身，并按版本序列排序；剪枝用 `<=`，否则没有一条路径能到 target。
- target 不可达时 disagreements 也要报错。返回 [] 会让 CI 以为一切正常。
- 测试抓不到的：用 BFS 一层层枚举路径，disagreements 的结果就成了先按长度、再按版本排。这组数据里不一致的路径一样长，看不出来；docstring 要求只按版本序列排，可以追问。

追问：
- "Alembic and Django have migration graphs too. How are theirs different?"（数据库处在某个版本，意味着所有祖先迁移都执行过，升级要按拓扑序跑完每条分支上的迁移，合并节点有两个父节点；这里的文档一次只处在一个版本，所以是找一条路径）
- "The history grows to 300 versions with many shortcuts and disagreements gets slow. What do you do?"（路径数是指数级的。只拿每条捷径和它跳过的那段链比较，或者对每个历史样例只比较计划路径和逐步路径）
- "Why compare against the planned path rather than every pair?"（计划路径是生产上真正会走的，它的结果就是用户会拿到的文件）
- "Where does this check run?"（CI 里，对每个历史版本的样例文件跑一遍，测验 Q17）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出 fsync 与断电、权限、跨进程的锁、迁移的幂等和回滚、捷径的验证 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
