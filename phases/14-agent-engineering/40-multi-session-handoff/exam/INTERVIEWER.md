# 面试官手册：HandoffPkt（14/40）

候选人计时期间不要看。候选人手里只有 README、`handoffpkt/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 告诉候选人：没有模型，也不联网，工作台产物和仓库快照都是测试里写好的数据。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | review 报告不存在时，要拒绝生成吗？ | "No. Build the packet, and carry the missing review as a warn risk." |
| 1 | 超时的命令（exit_code 是 None）算失败吗？ | "Yes. No exit code means no answer. That is a failed attempt." |
| 1 | max_bytes 按字符还是按字节？ | "Bytes of handoff.json as written, UTF-8." |
| 1 | 超预算时先丢哪些命令？ | "The oldest. The next session cares about the latest ones, and the full log has the rest." |
| 1 | 能不能丢 failed_attempts 或 feedback_tail 来腾地方？ | "Never. If the packet doesn't fit without any commands, raise PacketTooLarge." |
| 1 | 能改 handoff.json 的格式让它变小吗？ | "No. Keep packet_json as it is. How you find the cut is up to you." |
| 1 | 状态里没有 next_action 时用一句占位文字行吗？ | "No. Raise NoNextAction. A packet without one is a status report." |
| 2 | 目录里那些不是会话的文件（.md、笔记）要清理掉吗？ | "No. Leave files you didn't write alone." |
| 2 | 包里已经带了 session 和 previous 怎么办？ | "Replace them. The history assigns both." |
| 2 | 同一个包保存两次？ | "One session. Only a repeat of the latest one counts as a repeat." |
| 2 | 两个进程同时保存怎么办？ | "Not today. Tell me what you would do." |
| 2 | 要校验包里的字段吗？ | "No. Store what you are given." |
| 3 | 未跟踪的 *.tmp 文件该报在工作区还是临时文件下？ | "Both. Each check reads its own input." |
| 3 | 暂存了还没提交的改动也算吗？ | "Yes. Staged is not committed." |
| 3 | scratch 目录里的 *.tmp 要单独报吗？ | "No. The scratch directory covers what's inside it." |
| 3 | 会话之前就有的 print 要报吗？ | "No. Only lines this session added." |
| 3 | Markdown 或 shell 脚本里的 print 呢？ | "Only .py files." |
| 3 | 什么算红？skipped 算吗？ | "failed or error. skipped is not red." |
| 3 | 已经合并的旧分支要报吗？ | "No. Only branches that aren't merged." |
| 3 | 分离 HEAD 时还要再报一条 wrong branch 吗？ | "No. Just 'detached HEAD'." |
| 3 | 注释掉的代码块要查吗？ | "Not today." |
| 4 | 最多能占多少内存？ | "The last k records, plus a constant." |
| 4 | 失败记录什么时候写出去？ | "As soon as nothing before it can still be kept. That is when it leaves the last k." |
| 4 | k=0 呢？ | "Only the failures." |
| 4 | 输出格式？ | "One JSON object per line, a newline after each, as strings." |
| 5 | 一条分支的头是哪一份？ | "Its highest session number. Older packets on that branch are superseded." |
| 5 | 换了措辞的风险还是同一个吗？ | "Same id, same risk." |
| 5 | 同一次会话里既打开又关闭同一个 id？ | "Closes apply after opens. The tests don't have one." |
| 5 | 缺的那一份在没人继续的分支上，也要报错吗？ | "Yes. A missing packet means the history is incomplete." |
| 5 | 工作都移到别的分支了，main 还算有头吗？ | "Yes. Every branch that has a packet has a head." |

## 每关：要看什么、提示、追问

### Part 1 修交接包生成器（目标 14 分钟）

一个测试里叠了 5 个缺陷和几个护栏：

1. **缺 review 报告**。错误不在 `derive_risks` 报，而是在它调用的 `review_total` 里报 `AttributeError: 'NoneType' object has no attribute 'get'`。这个辅助函数照抄课里的代码：`review.get("total", 10)`，转不成整数也当 10 分。改成 `review or {}` 能消掉报错，但缺报告又被读成了满分，下一条断言抓住：docstring 写的是缺报告本身就是一条 warn 风险，total 不是整数也是风险，7 分不算风险。
2. **None 退出码**。`failed()` 是课里的 `not in (0, None)`，超时的那条命令既不进 `failed_attempts`，也不进 `feedback_tail`。docstring 写的是没有退出码也算失败（第 37 课拒绝在 None 上推进，第 38 课的 `feedback.null_exit` 是 block）。写成 `bool(exit_code)` 也会把 None 当成成功。被信号杀掉的命令退出码是负数（第 7 条记录是 -9），也是失败：改写成 `exit_code is None or exit_code > 0` 会漏掉它，同一条断言会抓住。
3. **裁剪顺序**。`trim_feedback` 是课里的写法：先放最后 k 条，再放所有失败记录，读到的是“最新 5 条 + 从头开始的失败”（测验 Q9）。另外 `records[-k:]` 在 k=0 时是整个日志。常见的错误修法：
   - `[r for r in records if r in keep]` 按相等判断，课里 demo 那种不带 id 的记录会把相等的旧记录也带回来；
   - `sorted(keep, key=records.index)` 找到的是第一条相等的记录，位置错；
   - 用下标判断最稳，也能处理 k=0。
4. **Markdown 和 JSON 不一致**。`render_markdown(payload, state)` 的 next action 取自状态原文，状态里那句带换行和缩进，payload 里已经压成一行。测试把 handoff.md 解析回来和 payload 比，再用 handoff.json 单独重渲染一遍，要求逐字相同。课里说 “If they diverge, the JSON wins”，skill 里说 markdown is a render of JSON。改成只读 payload，并去掉 state 参数。
5. **计时**。`fit_budget` 为了不超过 max_bytes，每丢一条最旧的命令就把整个包重新序列化一次，3500 条命令是平方级：Python 3.12 上约 1.1 秒（机器忙时 2 秒以上），限值 0.1 秒。二分查找保留条数约 4 毫秒；从最新的命令往回累加每条的字节数、最后再实测一两次也可以，约 3 毫秒。从零条开始、每次多放一条最新的命令再整体序列化一次，也能过（约 17 毫秒），但它对留下的条数是平方级：换成默认的 64 KiB 预算要 250 毫秒左右，二分只要 7 毫秒。可以接受，追问它的代价随什么增长；在 Python 3.10 或很忙的机器上它离限值也最近。护栏：
   - 必须真的放得下：二分停在第一个放不下的位置，或者只拿 commands_run 的大小去比 max_bytes，文件都会超出预算。
   - 必须尽量多留：再多一条就放不下。“只留最近 100 条”、每次丢 50 条，都会在这里挂掉。
   - 留下的是最新的、按原顺序；`commands_omitted` 要计数；handoff.md 要在预算之后渲染，列出同样的命令和省略了多少条。
   - 失败记录永远不丢：`failed_attempts` 和 `feedback_tail` 原样保留。预算恰好等于零条命令的大小时要成功，再少 1 字节就报 `PacketTooLarge`。为了凑预算把失败记录也删掉，会在这里挂掉（DID NOT RAISE）。
   - 只去掉 `indent=2` 不改算法，还是要 0.7 秒左右，而且改了 handoff.json 的格式。

起始代码里已经正确、测试也在守的：没有或只有空白的 next_action 报 `NoNextAction`（课里的代码用一句占位文字填上，测验 Q10 说这是形式上满足）；`changed_files` 用 `sorted(set(...))`（测验 Q11：set 的顺序随进程变化，破坏幂等）；命令用 `shlex.join` 渲染（测验 Q10：`str(list)` 不是 shell 命令）。

看什么：是不是先读 traceback、顺着调用链往上找；是不是先打印 payload 和 handoff.md 对比；每改一处就重跑；计时那一层有没有先 profile。

提示：
- 第 1 层：H1 "Which call got a None it didn't expect?" H2 "What should a packet say when no reviewer ran?" H3 直接指出 `review_total` 的默认值。
- 第 2 层：H1 "Which record is missing from failed_attempts?" H2 "What does exit_code None mean?"
- 第 3 层：H1 "Print the command ids in feedback_tail. What order are they in?" H2 "What does records[-0:] return?"
- 第 4 层：H1 "Where does the Markdown's next action come from?" H2 "Could you render handoff.md from handoff.json alone?"
- 第 5 层：H1 "Profile one call. Where does the time go?" H2 "Packet size only grows with the number of commands kept. What does that let you do?"

追问：
- "Why is next_action the load-bearing field?"（课里的原话：没有它就是一份状态报告。其余字段描述过去，只有它规定下一个会话的第一步）
- "Why trim commands_run and not the failures?"（失败是下一个会话最需要知道的；老的成功命令在完整日志里都有。课里：The next session loads the full log if it needs to, but the packet stays small）
- "Run the generator twice on the same artifacts. What has to be stable?"（练习 4：没有时间戳和随机数，set 要排序，路径用仓库相对路径，dict 按固定顺序）
- "Codex compacts, Claude Code compacts. Why a packet on top?"（课里：compaction 的机制各不相同，packet 的 schema 不变；handoff 结束一个会话，compaction 延长一个会话）

### Part 2 交接包历史（目标 10 分钟）

坑：
- 编号从 `session-<nnnn>.json` 的文件名里解析成整数。目录里还有别的文件：每份包旁边的 Markdown（session-0001.md），编辑器留下的备份 session-0001.json~，人留下的 notes.txt。`glob("session-*")` 会把 session-0001.md 和备份也数进去，得到三个 1；正则用 `re.match` 又不锚定结尾，会把备份当成第 1 次会话；用目录里的文件个数算编号会跳号。
- 文件名补零到四位，docstring 里写了。写成 session-7.json，测试最后直接读 session-0015.json 时会报 FileNotFoundError。
- 第一份的 previous 是 null，不是 0，也不能不写这个键。Part 5 会把 0 当成一份缺失的会话。
- 幂等：会话结束的 hook 触发两次，只记一次。
  - 比较时去掉 session 和 previous：新包里没有这两个键，读回来的包里有。
  - 只和最新的一份比。内容和更早某一份相同，是新的会话：任务回到了以前的状态，历史要留下这一步。
  - 任何字段变化都是新会话。只比较 next_action，会把一次关掉了一个风险的会话吞掉。
- save 自己分配 session 和 previous，包里带来的要替换掉。
- root 不存在时 `sessions()` 返回 `[]`，第一次 save 才创建目录；读不存在的会话报 KeyError，不是 FileNotFoundError。
- latest 要从磁盘读：测试用一个新建的实例取 latest，只在内存里记最后一次保存的写法会拿到 None。
- 测试抓不到、可以接受的两种写法，看到了就追问：幂等比较时比 JSON 文本而不是比 dict，键的顺序一变就会多出一份（测试里的包键序都相同）；save 把 session 和 previous 直接写进调用方传进来的 dict。

追问：
- "Two agents end their sessions on this task at the same moment. What happens?"（两边算出同一个编号，os.replace 后写的覆盖先写的，一份交接包丢了。用 `open(path, "x")` 独占创建，失败就换下一个编号；或者加锁）
- "Why one JSON file per session instead of one JSONL log?"（每份包自成一体，下一个 agent 只读一个文件；旧的按编号归档。课里：Stale handoffs are archived; only the active one drives the next session）
- "This directory keeps growing. When do you archive?"（只保留每条分支的 active 那份在主目录，superseded 的移到 archive/）
- "Session 10000 gets a five-digit name. What breaks?"（按文件名排序的代码会把 session-10000 排到 session-9999 前面；排序和找最新的一份都要按解析出来的整数，补零只是让 `ls` 的顺序和编号一致）

### Part 3 清理检查（目标 14 分钟）

五项检查各有自己的输入，输出是 clean_state.json 的内容，顺序照 docstring 里的表。每一行怎么匹配，docstring 都写明了：stash 消息的开头、文件名的后缀、路径里名为 scratch 的那一段、去掉缩进以后的语句开头、完整的 node id。这一关看的是能不能把课里 Leave a clean state 那张表落成规则，重点是下面前四条。

坑：
- 工作区要数全：每一行 `git status --porcelain` 都是阻塞项，未跟踪的 `??` 也是。课里的标准是 Every change committed or explicitly stashed with a note，未跟踪的文件两样都没做。常见的漏法：
  - 觉得未跟踪的文件不算改动，跳过 `??`；
  - 觉得 `?? notes/window.tmp` 和 `?? scratch/` 已经由临时产物那一项报了，这里不再报（澄清问题的回答是两边都报）；
  - 只看状态码的第二列（工作区那一列）：暂存了还没提交的改名 `R  app/limit.py -> app/limits/window.py` 第二列是空格，被当成已经提交；
  - 先 `strip()` 再切掉两列状态码：` M app/signup.py` 第一列的空格没了，报成 `pp/signup.py`。
- debug print 的行号和路径从 diff 里读：
  - 行号是新文件里的行号：从 hunk 头的 `+c` 开始，上下文行和新增行加一，删除行不加。第二个 hunk 的旧起点是 40，新起点是 41，正确的是 `app/signup.py:44`。用旧起点报成 43，删除行也加一报成 45，上下文行不加报成 42，先加一再判断也是 45（`app/limits/probe.py` 跟着变成 5）。
  - 路径从 `+++ b/` 取，新文件的 `--- ` 行是 `/dev/null`。从 `---` 取的话，`app/limits/probe.py` 里的 `pprint(` 就报不出来。删掉的文件 `+++ ` 是 `/dev/null`，它的行全是删除行，本来也不报。
- feature board（课里：A stale board sends the next session to work that is already done）：
  - 多于一个 in_progress 时报一条，按看板顺序列出：`rate-limit, captcha`。只有一个 in_progress 是正常状态，不报，干净的那份看板上 captcha 正在做。每个 in_progress 各报一条，或者排序以后再列，都对不上。
  - 这次会话完成的 feature 必须标成 done。rate-limit 还是 in_progress，audit-log 还是 todo，两个都要报；只查还标着 in_progress 的，会漏掉 audit-log。
  - active 指向一个已经 done 的 feature 要报。要看看板上它的状态：signup-form 是以前的会话做完的，拿 finished 去比会漏掉它。
- 分支：分离 HEAD 只报一条 `detached HEAD`，不再报 wrong branch，也不能报成 `wrong branch: None`。预期的分支本来就没合并，不算孤儿：要按预期分支排除，拿当前分支代替的话，分离 HEAD 时会把 feat/signup-rate-limit 报成孤儿。已经合并的分支（fix/readme-typo）也不算。
- 改名的那一行报新路径，按空白切开会报成旧路径。
- 测试：failed 和 error 是红，skipped 不是。
- scratch 目录一个只报一次，报在它第一个文件的位置，里面的文件（包括 `scratch/out.tmp`）不再单独报。`tools/scratch/` 也是 scratch 目录，只认顶层的 `scratch/` 会漏掉它。
- scratch dir 和 temp file 读的都是 files，按 files 的顺序交错出现（docstring 表格上面那句写了：interleaved, in the order of files）。先列完所有 scratch 再列 temp file，或者反过来，都会挂。只在 status 的 `??` 行里找也不行，`tools/scratch/bench.py` 和 `build/out.tmp` 不在 status 里。
- 调试 print 只看这次会话新增的行：上下文行里原有的 print、删掉的 print 都不算。只看 .py 文件，README 里示例代码的 print 不算。
- 最后，`generate_handoff` 拿到非空的 clean_state 要报 DirtyWorkbench。这一行起始代码里已经有了，测试守着它。
- 顺带检查：数据里放了几处名字相近的东西，照 docstring 写明的匹配方式做自然不会报，测试顺带守着，不是这一关的重点。
  - stash 看消息的开头：以 “WIP on <branch>:” 开头才是没写说明。stash@{1} 的说明里也写了 “WIP on”，在整行里找这几个字会误报它。
  - 临时文件看文件名的后缀：在路径里找 “tmp” 会误报 `app/tmpl/signup.html`。
  - scratch 看路径里名为 scratch 的那一段：按子串找会误报 `app/scratchcard.py`。
  - 调试 print 看去掉缩进以后的开头：`app.register_blueprint(` 里也有 `print(`；`print_table(rows)` 是正常调用，比较时漏了括号就会误报它。用 `\bprint\(` 这类带词边界的正则在整行里找也能通过，它会多报 `if DEBUG: print(x)` 这种不以 print 开头的语句，和 docstring 的规则不一样；可以接受，问候选人为什么这样选。
  - risk 按完整的 node id 对应测试：按前缀或按文件匹配都会放过 `test_burst_window`。在 risk 的 detail 文字里找测试函数名，碰巧能过这组数据，但它不看 `"test"` 字段，两个文件里同名的测试会混在一起，看到了要追问。

提示：
- 工作区：H1 "Is an untracked file committed? Is it stashed?" H2 "What do the two letters at the start of a status line mean?"
- 行号：H1 "Which of these lines did this session add?" H2 "What does the @@ header tell you about line numbers?"
- 看板：H1 "Read the board as the next session would. Where does it send them?"
- 分支：H1 "With HEAD detached, what is there to compare with the expected branch?"
- stash：H1 "What does git write when you stash without -m?"

追问：
- "Why is cleanup a check and not a habit?"（课里：a habit is the thing that gets skipped on a hard day。写成前置条件，生成器自己断言）
- "Should the generator just commit and delete these files for the agent?"（不该：自动提交会把半成品当成意图提交；生成器只拒绝，由 agent 处理）
- "Where would these inputs come from in a real repo?"（`git status --porcelain`、`git stash list`、`git ls-files --cached --others --exclude-standard`、`git diff <start>..HEAD`、pytest 的结果文件、`git branch --merged`）
- "The lesson lists commented-out blocks too. Why aren't they here?"（没有不靠启发式的精确规则；可以做成提醒而不是阻塞）

### Part 4 单遍裁剪（目标 10 分钟）

坑：
- 失败记录不能一到就写：它前面可能还有会留在最后 k 条里的成功记录（`[ok, ok, fail]`、k=3 时原顺序输出）。
- 也不能攒到最后再写：探针的第一条记录就是失败，最多读到第 6 条就要写出来。`list(records)` 先读完整个日志也会挂在这里。
- 内存里只放最后 k 条：失败记录离开窗口时直接写出，不另存。测试用 dict 子类数活着的记录，峰值超过 k+3 就挂；把写过的失败记录存进一个列表，也会挂在这里。
- k=0 时只输出失败记录。`deque(maxlen=0)` 会把新来的记录直接扔掉；用 `window[-k:]` 截窗口，k=0 时截出来的是整个列表。
- None 和负的退出码（被信号杀掉，测试里 c7 是 -9）都是失败。直接用 Part 1 修好的 `failed()` 最省事。
- 每条记录一行 JSON 字符串。返回列表而不是生成器、yield dict、用 `str()` 都不行。

追问：
- "Lesson 37 rotates the log into .1 to .5 files. How do you stream across them?"（从最老的轮转文件开始依次串起来，单遍不变）
- "Would you keep the first few records too?"（第 37 课对单条输出是头尾都留；这里是跨记录，课里的规则只要最后 K 条和全部失败）
- "A flaky test fails 50,000 times. What does the trimmed log look like?"（按规则全部保留，输出很大；交给 Part 1 的预算去拒绝，或者按命令聚合失败）

### Part 5 分支交接链（目标 12 分钟）

坑：
- 一条分支的头是这条分支上编号最大的一份。feat/signup-ui 上 7 是叶子，但 8 从 3 重新开始，5 和 7 都被取代。只取叶子会少了 main、多出一个 ui；按输入里最后出现的那份取也不对，输入是打乱的。
- lineage 沿 previous 一直走到根，可以跨分支：api 和 ui 都继承 main 的 1 到 3。只看同名分支的包，或者走到分支名变化就停，都会丢掉主干上的风险。
- 风险按 id 匹配：R-2 在第 3 次会话换了措辞，要原位替换。按措辞做键会留下两个 R-2，关闭也关不掉。原位指位置不变，不是去改原来那个 dict：用 `.update()` 把新措辞写进第 1 次会话的那份风险，结果看起来对，却改掉了调用方手里的包，测试最后拿调用前的深拷贝来比。
- 关闭只对自己这条链生效：s6 在 api 上关了 R-2，ui 上的 R-2 还开着。把所有包按会话号统一处理一遍会把它关掉。
- 关掉又重开的风险排到最后（R-1 在 s3 关闭、s6 重开）。按首次出现的位置排、按 id 排都不对。
- 断链：任何一份的 previous 不在包里都报 BrokenChain，并写出缺的编号，那一份在没人继续的分支上也一样（去掉 5，7 就指向缺失的 5）。只在走各个头的链时才检查，会漏掉这种。previous 是 0 也算缺失。
- 两份包同一个编号、previous 指向更晚的会话或者指向自己，都报 ValueError。写成 `previous > session` 会放过指向自己的那份（测试里是被取代的第 2 份）；候选人的写法如果从每一份包都往回走，会在这里死循环，测试卡住时先看这一条。
- 结果按头的会话号排序。

追问：
- "The lesson wants a status of active, superseded or archived. Which packets here are superseded?"（三个头是 active，其余 1、2、4、5、7 都是 superseded；超过一段时间没用的归档）
- "What does the next session on feat/signup-ui do first?"（读这条分支的头，核对 last_known_good_commit 和当前 HEAD，从 next_action 开始，带着它的 open risks）
- "Risks without ids?"（从 finding 的 code 和对象生成稳定的 id；用措辞做哈希，一改措辞就对不上）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、打印 payload 和 handoff.md 对比、一次只改一处、用 `-x -k`、计时前先 profile |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码（比如修完以后不再用的 `review_total`）；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出幂等、并发写、归档、清理检查的来源、跨分支的风险 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
