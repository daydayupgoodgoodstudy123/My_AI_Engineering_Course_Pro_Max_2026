# 面试官手册：FeedLog（14/37）

候选人计时期间不要看。候选人手里只有 README、`feedlog/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 告诉候选人：`FakeShell` 和 `FakeProcess` 是命令和进程的替身，按脚本输出，不要去改测试里的替身。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 超时被杀掉的命令，要不要记它的退出码？ | "No. We killed it, so it has no exit code of its own. None, and error says it timed out." |
| 1 | 找不到程序时，照 shell 的习惯记 127？ | "No. 127 is a shell convention and there is no shell here. None, with the error." |
| 1 | 超时前打印的内容还要吗？ | "Yes. Decode it, redact it and truncate it like any other output." |
| 1 | 命令根本没启动，也要写记录吗？ | "Yes. Every command leaves exactly one record." |
| 1 | 输出不是 UTF-8 怎么办？ | "Keep the record. Bad bytes become U+FFFD." |
| 1 | 能不能把带 key 的行整行删掉？ | "No. Replace the secret and keep the line." |
| 1 | argv 里的秘密要不要脱敏？ | "Not today. The tests don't put secrets in argv. Tell me what you would do." |
| 1 | 退出码非零时，loop_can_advance 返回什么？ | "True. A failing exit code is feedback. The agent reads it and reacts." |
| 2 | max_bytes 按字符算还是按字节算？ | "Bytes on disk, in UTF-8." |
| 2 | 文件正好等于 max_bytes，算超吗？ | "No. Past max_bytes means more than max_bytes." |
| 2 | 换行符算进 max_bytes 吗？ | "Yes. It's the size of the file on disk, newlines and all." |
| 2 | 一条记录比 max_bytes 还大呢？ | "It gets a file to itself. Never split it, never drop it." |
| 2 | keep 指什么？ | "How many rotated files we keep: path.1 to path.keep. Anything older is deleted." |
| 2 | 目录里还有别的文件，比如 .bak？ | "Not ours. Don't read them, don't touch them." |
| 2 | 要支持多个进程同时写吗？ | "Not today. Tell me what you would do." |
| 2 | 进程崩溃，最后一行只写了一半？ | "The tests don't cover it. What would you do?" |
| 3 | 只按 \n 分行？\r\n 呢？ | "Only \n ends a line. A \r\n line keeps its \r." |
| 3 | head 和 tail 加起来超过总行数？ | "Then nothing is cut, and there is no marker." |
| 3 | 只截掉 1 行也写 lines 吗？ | "Yes. Always ...truncated N lines..., the format never changes." |
| 3 | 原文末尾没有换行呢？ | "Then the result has none either." |
| 3 | 一行 5 MB 的输出要不要切？ | "Not in this function. Lines are the unit here." |
| 3 | head 或 tail 是负数？ | "ValueError." |
| 4 | stdout 和 stderr 分开截吗？ | "Yes. Each pipe keeps its own first and last lines." |
| 4 | 进度输出要脱敏吗？ | "No. It's the agent's live view and it isn't written anywhere. Nothing in follow is redacted." |
| 4 | 一行被拆在两个 chunk 里？ | "It waits on its own pipe until its \n arrives." |
| 4 | 进度行要先解码吗？ | "No. The bytes exactly as written, behind the prefix." |
| 4 | 超时以后，还读剩下的输出吗？ | "No. Kill it and stop reading. A line that has started still goes out." |
| 4 | 两个管道都关了，进程还没退出？ | "The deadline covers waiting for the exit too." |
| 4 | 一个 chunk 里有好几行？ | "One yield for that chunk, with every line it completed." |
| 4 | 被杀的进程 exit_code 记什么？ | "None, and error is timeout after <timeout_s>s." |
| 5 | 父记录被轮转删掉了？ | "The chain starts at the first record we still have, and says which parent is missing." |
| 5 | 一个尝试被重试了两次？ | "Each retry leads its own chain. The chains share the attempts before the fork." |
| 5 | 超时（exit_code 是 None）算 failure 吗？ | "Not for last_failure. There is no exit code to look at. It can still end a chain." |
| 5 | 被信号杀掉的 -9 呢？ | "That's a non-zero exit code, so yes." |
| 5 | 链最长会有多长？ | "As long as the log. A polling script can retry a thousand times." |
| 5 | 链怎么排序？ | "As the docstring says: by where each chain's last attempt sits in records. Never by started_at." |
| 5 | 有环，或者 id 重复？ | "Malformed input. ValueError." |
| 5 | 重试写在了被重试的记录前面，但没有环？ | "Still malformed. An attempt is always written before its retries. ValueError." |

## 每关：要看什么、提示、追问

### Part 1 修 runner（目标 12 分钟）

一个测试里叠了 5 个缺陷和几个护栏：

1. 超时分支把 `exc.stdout` 原样放进记录。`TimeoutExpired.stdout` 是 bytes（POSIX 上即使 `text=True` 也是，课里的代码专门判断了一次），错误不在超时分支报，而在两层调用之外：`JsonlSink.append` 调 `FeedbackRecord.to_json`，`json.dumps` 报 `TypeError: Object of type bytes is not JSON serializable`。只解码不够：这段输出也要脱敏和截断，37 行里留最后 30 行，Bearer token 换掉。只解码 stdout 不管 stderr，stderr 的 bytes 会再报一次同样的错；stderr 里 dsn 那一行带着 password，只给 stdout 走 `_capture`、stderr 只解码，也会被抓住。
2. `_capture` 先截断再脱敏。bootstrap 脚本打印了一把 52 行的 PEM 私钥，测试里的 `keep_last(30)` 截掉了 BEGIN 那一行，多行规则再也匹配不上，27 行密钥原样进了记录。`redact` 本身没有错，错在 `_capture` 里两步的顺序，这正是测验 Q11。护栏：
   - 把含 key、token 的行整行删掉，会连 `keyboard: us-intl`、`tokenizer=fast`、`--- deploy_key ---` 一起删掉，精确比较会抓住。
   - 截断后再删“像 base64 的行”，END 那一行还留着。
   - 逐行脱敏永远匹配不上多行的私钥。
3. 找不到程序时记了 `exit_code=127`。`loop_can_advance` 本身是对的，于是把这条记录当成了反馈，报错的是 “a command that never started gave no feedback”。127 是 shell 的约定（测验 Q6），这里没有 shell。让 `loop_can_advance` 把 127 也当成没有反馈也不对：真实命令也可以自己以 127 退出，测试接着查 `exit_code is None`。
4. 只捕获了 `FileNotFoundError`，没有执行权限的脚本抛 `PermissionError`，直接冒出 runner，一条记录都不写（测验 Q12）。改成 `except OSError`，`NotADirectoryError` 也就一起盖住了。只多捕获一个 `PermissionError` 不够：`migrate.sh` 没有 `#!` 行，exec 报的是普通的 `OSError: [Errno 8] Exec format error`。error 的格式是“异常类名: 消息”。
5. `_decode` 是严格解码，`cat` 一个 PNG 就报 `UnicodeDecodeError`，这条命令的退出码丢了，记录也没了。用 `errors="replace"` 得到 U+FFFD；`ignore`、latin-1、`backslashreplace` 都会被抓住。

其余护栏：退出码为 1 的记录 `loop_can_advance` 必须是 True（测验 Q3：失败也是反馈）；每条命令恰好一条记录，超时和起不来的命令都算；cwd 和 timeout 原样交给执行器；重试要记下 parent；最后一段用真实的 `python -c` 跑一次默认执行器。

测试抓不到、可以接受的：用 `except Exception` 包住执行器也能过。追问它的代价：调用方自己的 bug（比如 argv 里混进了 None，subprocess 报 TypeError）也会被记成“命令起不来”。

看什么：是不是先读 traceback、顺着调用链往回找是谁把 bytes 放进了记录；是不是打印 `boot.stdout_tail` 看实际留下了哪几行；每改一处就重跑。

提示：
- 第 1 层：H1 "Which value could not be serialized, and where did it come from?" H2 "What type is TimeoutExpired.stdout?" H3 直接指出超时分支和正常分支的差别。
- 第 2 层：H1 "Print boot.stdout_tail. Which lines are left, and where did the BEGIN line go?" H2 "What does the private key pattern need to see?"
- 第 3 层：H1 "What exit code did the missing program get, and who decided it?"
- 第 4 层：H1 "Which exceptions can starting a process raise?"
- 第 5 层：H1 "What does decode do with a byte like 0x89?"

追问：
- "The command line itself carries a secret: curl -H 'Authorization: Bearer ...'. Where does it end up?"（测验 Q9：command、agent_note、error 原样写盘；`str(TimeoutExpired)` 还会把 argv 再抄一遍，所以 error 用 timeout_s 自己拼。根本办法是秘密走环境变量或文件，记录里只留变量名，其余字符串字段也过一遍 redact）
- "Why not redact when the agent reads the record?"（磁盘上的文件才是会泄漏的东西：备份、CI artifact、handoff 文件）
- "Redacting 50 MB with five regexes takes time. How would you bound it?"（测验 Q11：先按字节留一个很大的头尾上限，再脱敏，再按行截断）
- "Why is exit code 2 progress and a timeout not?"（refuse-on-null：非零退出码是事实，agent 可以读 stderr 再改；没有退出码就没有事实）
- "Which clock gives duration_ms, and which gives started_at?"（耗时用 monotonic，不受校时影响；started_at 用墙上时间，方便回放和对时）

### Part 2 轮转的 JSONL 日志（目标 12 分钟）

坑：
- 在写入之前判断：这条记录写进去会不会超过 max_bytes，会就先轮转。课里的 `maybe_rotate` 是事后判断（文件已经 ≥ 上限，下一次写之前才轮转），文件会多出一条记录（测验 Q8）。这里两条 700 字节的记录是 1400，第三条会到 2100，超过 1800。
- 按字节算，不按字符算。记录里填充了 📦，每个 4 字节，按字符数算会在一个文件里塞进四条。
- 正好填满 max_bytes 是允许的（`>=` 和 `>` 的区别）：那条 400 字节的记录让当前文件正好到 1800。另一头，记录的大小要算上结尾的换行：用 `len(record.to_json().encode())` 判断会少算 1 个字节，测试最后让 1400 字节的文件再来一条 401 字节的记录，写进去正好是 1801。
- 重新打开的日志要接着上次的大小，大小从文件取，不能从内存里的计数器从 0 开始。
- 轮转顺序：先删 `.keep`，再从大到小改名（`.11` 先变 `.12`）。从小到大改名会一路覆盖，最后只剩两三个文件。只保留 12 个。
- 按数字顺序读轮转文件。`sorted()` 会把 `.10` 到 `.12` 排在 `.1` 和 `.2` 中间，合并出来的顺序就错了。课里的 `load_all` 用日志文件名加 `*` 做 glob，放到这里就是 `feedback.jsonl*`，会把 `feedback.jsonl.bak` 也读进来。
- `current()` 只读当前文件，这是 agent 每一轮都要读的；`load_all()` 读全部，从旧到新，给 CI 和 reviewer。
- 比 max_bytes 还大的记录单独占一个文件，下一条记录来时把它轮转出去。新日志的第一条就是大记录时没有东西可轮转，硬要轮转会报 `FileNotFoundError`。
- `with_suffix` 会得到 `feedback.1`；用 `"wb"` 打开会把文件清空。
- 每行就是 `record.to_json()`，非 ASCII 原样写成 UTF-8。用 `json.dumps` 的默认参数会把 📦 转义成 `\ud83d\udce6`，字节数就全变了。
- 测试抓不到、可以接受的：大小记在内存里、打开日志时从文件取，测试能过，只有一个写者时也没错，追问另一个实例写过以后这个计数会怎样；用 glob 找轮转文件，只认数字后缀并按数字排序；轮转时先复制再清空当前文件（logrotate 的 copytruncate）。

提示：
- H1 "How big is each file on disk right now, and how big would it be after the next append?" H2 "List the directory after 30 appends. In what order does sorted() give you the rotated files?"

追问：
- "Ten agent workers append to the same file. What breaks?"（测验 Q16：写入交错、轮转和写入抢跑；把“检查、轮转、追加”放进同一把文件锁，或者每个 worker 一个文件，或者只留一个写进程）
- "A crash leaves half a line at the end of the file. What does load_all do?"（跳过不完整的最后一行；下一次追加要从新的一行开始，否则两条记录都坏）
- "A tail contains U+2028. What if load_all split the file with str.splitlines()?"（ensure_ascii=False 时 U+2028 原样写在行里，splitlines 会把一条记录切成两半；只能按 \n 切）
- "Defend the rotation policy."（练习 3：每一轮读取的成本有上界，磁盘占用有上界，CI 拿完整的一套；代价是父记录会被轮转掉，这就是 Part 5 的孤儿链）

### Part 3 确定性截断（目标 10 分钟）

坑：
- 结尾的 \n 是最后一行的结束，不是新的一行："a\nb\n" 是 2 行。把它后面的空串也算一行，N 会多 1；丢掉结尾的 \n，或者给没有 \n 结尾的原文加一个，都不对；`rstrip("\n")` 会把结尾的空行一起吃掉。
- `lines[-tail:]` 在 tail=0 时是整个列表。
- head + tail 不少于总行数时原样返回，不加标记（`<=` 和 `<` 的区别）。
- 空行也是行。
- 只有 \n 结束一行。`str.splitlines()` 还会在 \r、\x0b、\x0c、\x1c 到 \x1e、\x85、U+2028、U+2029 处断行，ODD 里每一种都有；\r\n 的行保留它的 \r。用 universal newlines（`open()` 和 `io.TextIOWrapper` 默认的 `newline=None`）、`re.split(r"\r?\n")`、先把 \r\n 换成 \n，也都不对。
- head、tail 为负数要报 ValueError，否则 `lines[:-1]` 会悄悄算出一个错的结果。
- 计时：6 万行、2.4 MB。从字符串前面一行一行地丢（`text = text[text.index("\n") + 1:]`）是平方级复制，约 1.2 秒；对列表反复 `pop(0)` 约 0.25 秒；`split` 加切片 2 到 3 毫秒，限值 0.1 秒。
- `io.StringIO(text).readlines()`（StringIO 默认 `newline="\n"`，只在 \n 处断行，也不转换）和 `str.find` 一行一行往后找，都是对的。逐字符扫描虽然也是线性的，但 240 万次 Python 循环在 3.12、3.14 上要 40 到 60 毫秒，3.10 上 90 到 160 毫秒，会撞上限值；遇到时提示改用 `split` 或 `find`。
- 最后一段用真正的截断跑 Part 1 的 runner：私钥的 BEGIN 落在保留的头部，END 落在被截掉的中间，正是课里讲的那种泄漏。Part 1 的顺序没修好，这里就过不去。

提示：
- H1 "How many lines does 'a\nb\n' have? How many does your code count?" H2 "What is lines[-0:]?"

追问：
- "A single 5 MB line of minified JSON. What does this function do with it?"（什么都不做，N 是 0。测验 Q11 的第 2 问：再加一层按字符的头尾上限，同样要确定性）
- "Why deterministic, and never sampled?"（测验 Q14：回放看到的就是 agent 当时看到的，提示词缓存能命中，回归测试能写）
- "Why 5 lines of head and 30 of tail?"（最后的错误和测试总结在尾部；头部是启动信息、配置和早期警告）

### Part 4 实时跟随（目标 15 分钟）

坑：
- 两个管道要同时读。假管道一次只装一次写入，进程要等它被读走才继续，和装满的系统管道一样。先把 stdout 读到底再读 stderr，或者根本不读 stderr，进程会卡在写 stderr 上，一直等到截止时间（subprocess 文档里专门警告过这种死锁）。`read()` 不给大小时会一直读到 EOF（`StreamReader` 的语义），就没有流式了，顺序也会错。
- 每个管道各自拼行。“Building wheels for coll” 要等后半截 “ected packages” 到了才是一行；两个管道共用一个缓冲区，stderr 的 gcc 那行会被粘到它后面。
- 进度行是原样的字节：不解码（caf\xe9 原样发出），不去掉 \r。
- 每个 chunk 一次 yield，带上它补全的所有行；没有补全任何行就不 yield，不发空的，不发半行。
- 每个管道一个头部列表加一个 `deque(maxlen=tail)` 的尾部；tail 的排版和 truncate_lines 一样，解码时坏字节换成 U+FFFD。
- 内存：5 万行、2.5 MB 的输出流过去时 tracemalloc 的峰值要低于 1 MB，参考实现约 60 KB；把每一行都留下、最后再切尾巴，峰值约 5 MB。
- 截止时间管整个运行，从 follow 开始算：每次读各给 timeout_s，持续有输出时永远不会触发；只在 chunk 到达时检查截止时间，会等下一个 chunk 到了才动手；从第一块输出才开始计时，一声不吭的 `git fetch` 就永远不会被 kill。等进程退出也算在里面：start-daemon 在 0.15 秒关掉管道、0.3 秒才退出，截止时间是 0.2 秒，等退出时不设上限，或者重新给满 timeout_s，都会等到它自己退出。
- 到截止时间：kill，不再读（不要把剩下的读完），正在写的那一行照样发出，exit_code 是 None，不是 -9。
- 记录放在最后，单独一次 yield，一行 JSON，不能缩进。
- 最后一段在真实的 asyncio 子进程上跑一次。
- 测试抓不到、可以接受的：轮流对每个管道 `wait_for` 一个几毫秒的超时也能过，但这是轮询，flood 那段每一块都要白等一次 stderr，这一关要多花 2 秒多，追问延迟和空转；到截止时间不取消还挂着的读任务也能过（kill 之后管道关了，读会拿到 b"" 结束），追问消费者中途走掉时这些任务归谁收拾。

提示：
- H1 "Which pipe is your code waiting on when the process writes to stderr?" H2 "What happens to a writer whose pipe nobody reads?"
- H1（截止时间）"What is your code awaiting when the process goes quiet?"

追问：
- "Can we write this record to the feedback log as it is?"（不行，这里什么都没脱敏；只对留下的头尾脱敏又成了先截后脱。要在每一行进入头尾之前脱敏，私钥这类多行块用一个小状态机。跨块脱敏是第 13 章 26 课的内容）
- "A 20 MB line with no newline?"（正在拼的那一行会无限长；要给它设上限）
- "The consumer goes away mid-stream. What still runs?"（生成器的 finally 会取消读任务；进程要不要杀，要定下来并写进文档）
- "Why kill and then wait()?"（回收子进程，否则留下僵尸进程）

### Part 5 重试链（目标 11 分钟）

坑：
- 分叉：d2 被 d3 和 d4 各重试了一次，得到两条链，共用 d1、d2。用 `child[parent] = child` 这种字典只能留下一个，留下先写的 d3 还是后写的 d4 都不对。为了不重复走共用的那一段，所有链共用一个“走过”集合，d4 那条链走到 d2 就停了，只剩 `("d4",)`。
- 孤儿链：c1 的父记录 gone-7 已经被轮转掉了，链从 c1 开始，orphaned_from 写原来的父 id "gone-7"。直接按 id 查会报 KeyError；当成普通的根，信息就丢了；整条链不输出也不对。f1 和 g1 都指向 gone-3，是两条孤儿链。
- last_failure 是最近一次非零退出码：超时的 None 不算（e2），信号杀掉的 -9 算（d3）。`exit_code > 0` 会漏掉 -9，`!= 0` 会把 None 算进去，取第一个而不是最后一个也不对。只看这条链自己的尝试：在整棵重试树上找，d4 那条链会拿到另一条分叉上的 d3。链最后成功了也要填：a 链最后是 a3 的 0，last_failure 仍是 a2。
- 1500 次的轮询链要用循环，不能递归：往上找父记录、从第一个尝试往下 DFS、带缓存的递归，都会 RecursionError。
- 链的 exit_code 是最后一个尝试的，可以是 None。
- id 重复、重试的是后面才写入的记录（环、自己指向自己）都报 ValueError。只查环不够：w2 重试的 w1 写在它后面，没有环，也要报错。
- Chain.attempts 是 tuple。
- 顺带检查（docstring 写明了先后一律看在 records 里的位置，不看 started_at）：a3 的时钟回拨到了 99.0。链要按最后一个尝试的位置排，按 started_at 排会让 a 链排到最前面，按第一个尝试排也不对；判断“重试了后面才写入的记录”时比 started_at，会在 a3 上误报。
- 测试抓不到、可以接受的：从根往下用显式栈走、最后按链尾的写入位置排序，结果一样；递归再调大 `sys.setrecursionlimit` 也能过 1500 次的链，但只是把上限往后推，追问链再长十倍怎么办。

提示：
- H1 "Draw the d chain. How many attempts did nobody retry?" H2 "Where does the c chain start, and what is its parent?"
- H1（last_failure）"Which attempts in the e and d chains have an exit code that says they failed?"

追问：
- "What does the TUI from exercise 5 show for each chain?"（练习 5 的八项：命令、尝试次数、最后的退出码、最近一次非零退出和它的 stderr 尾部、耗时、agent_note 和实际结果的对比、截断和脱敏计数、孤儿标记）
- "The final attempt is green. What should the verification gate still ask the chain?"（失败的历史；reviewer 要看修法是否合理。本章 38、39、40 课）
- "Parents rotate away. How would you keep chains whole?"（另存一份链的索引，按链而不是按大小轮转，或者把根的摘要抄进重试的记录）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、打印记录里实际留下的内容、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出 argv 里的秘密、读时脱敏的问题、并发追加和文件锁、管道死锁、超时和 refuse-on-null、轮转造成的孤儿链 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
