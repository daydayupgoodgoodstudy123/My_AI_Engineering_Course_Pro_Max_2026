# 面试官手册：TaskFrame（14/43）

候选人计时期间不要看。候选人手里只有 README、`taskframe/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 收据能指向一段行吗，比如 `18-25`？ | "No. One line per receipt. Cite each line you rely on." |
| 1 | 行号从 0 还是从 1 开始？ | "From 1, the way grep -n and your editor count." |
| 1 | validate 要不要检查那一行真的写着 claim 说的东西？ | "No. Here a line receipt resolves when the line exists. Keeping the line's content is the next part." |
| 1 | 命令收据要重新跑一遍吗？ | "No. We can't replay commands here. A well-formed one counts." |
| 1 | 路径里会有冒号吗？ | "Not in a line receipt. The line number is what follows the last colon." |
| 1 | 快照能缓存吗？ | "A snapshot never changes. What you cache is up to you." |
| 2 | 一行挪到了别的文件，算 moved 吗？ | "No. A receipt names a file. If the line left that file, the fact needs a new receipt." |
| 2 | 行尾空格要不要紧？ | "Yes. Compare bytes. A reformatted line is a changed line." |
| 2 | 这一行现在出现了两次呢？ | "Stale. Picking one of them would be a guess." |
| 2 | 换行符算这一行的一部分吗？ | "No. The line ends before the newline." |
| 2 | pin 列表存在哪里？ | "In the same store, under its own hash. The frame keeps that digest." |
| 3 | 证据和授权都覆盖同一个决定，算哪个？ | "Evidence. The order in the docstring is the rule." |
| 3 | unknown 指向计划里没有的决定？ | "That's a ValueError. The frame and the plan disagree." |
| 3 | open 的决定算阻塞吗？ | "It means reconnaissance isn't done. The status is INVESTIGATE." |
| 3 | 同一个 look_at 出现两次？ | "List it once, where it first comes up in the plan." |
| 4 | 搜索结果的路径里会有冒号吗？ | "Assume not. The path ends at the first colon." |
| 4 | 停下来的时候要不要把搜索关掉？ | "The tests don't check it. Tell me what you'd do in production." |
| 4 | 一条结果同时满足两个还没定的决定？ | "Settle both and send the line once." |
| 4 | 搜索结束了，还有决定没定？ | "End the stream with what you found. The open decisions go into the frame as unknowns." |
| 5 | 计划里还不存在的文件算吗？ | "Yes. The change creates them, and their directories may be new too." |
| 5 | 要支持 `*.py` 这样的 glob 吗？ | "No. Entries are files or dir/**." |
| 5 | 一个目录里只有一个文件、而且要改，写成 `dir/**` 行不行？ | "No. That's no shorter, and it would allow new files there." |

## 每关：要看什么、提示、追问

### Part 1 修任务框架的校验（目标 10 分钟）

一个测试里叠了 3 个缺陷和一处性能问题：

1. 解锁后第一个失败是 `validate(example())` 返回 `['unsupported fact: Only AccountStore.save raises DUPLICATE_EMAIL']`，而 `validate` 本身没有错。顺着往下：`validate → receipt_problem → parse_receipt`。`parse_receipt` 先试 `路径:行号`，用 `rpartition(":")` 切最后一个冒号；这条命令收据是 `$ git grep -c 'raise DUPLICATE_EMAIL' -> app/accounts.py:1`（`git grep -c` 打印的就是 `路径:次数`），于是被读成文件 `$ git grep -c ... -> app/accounts.py` 的第 1 行，`receipt_problem` 报“不在仓库里”。要先认 `$ ` 开头的命令形式。同一个 example 里的 curl 收据中间有 `localhost:8000`，只是因为最后一个冒号后面不是数字才碰巧没出事。
2. 行号从 1 开始，`parse_receipt` 只检查了是不是数字，`receipt_problem` 只查了上界，`app/accounts.py:0` 于是成了能解析的收据。grep -n 和编辑器都从 1 数；第 0 行通常说明收据是从 0 起数的工具（比如 LSP 的位置）抄来的，那样的收据每一条都差一行。
3. 命令收据只切了 ` -> `，没检查两边：`$ python3 -m unittest tests.test_accounts`（没有结果）和 `$ make test -> `（结果为空）都被接受。docstring 规定两部分都不能为空；讲义说命令结果更好，收据的分量就在结果上。
4. 性能：`Repo.lines` 每次调用都把整个文件重新切一遍，`receipt_problem` 每条收据都要调一次。500 个 frame、1,500 条收据指向两个 20,000 行的生成文件，本机三个独立进程各测一次为 0.689、0.706、0.692 秒，限值 0.05 秒。每个快照每个文件只切一次、存在实例上之后为 2.139、2.144、2.533 毫秒。两侧都至少留 8 倍余量。
5. 护栏：
   - 命令收据仍然是收据。把收据限定成 `路径:行号`，example 里的 curl 收据就不认了。
   - 缓存放在模块级、按路径做键，两个快照里的同名文件会共用一份行：“each snapshot answers for its own files” 抓住。
   - 行号和 grep -n 一致，只按 `\n` 切。测试的两个测试类之间有一个换页符（PEP 8 允许的分页），`splitlines()` 会在那里多切一行，`tests/test_accounts.py:45` 就成了能解析的收据。`split("\n")` 不去掉结尾换行后的空串，`app/accounts.py:34` 也能解析；只数 `\n` 的个数，`app/settings.py` 没有结尾换行，第 2 行就没了。
   - 每次调用都用 `str.count` 数行，不切文件但仍然整个扫一遍，约 0.22 秒，过不了限值。
6. 可以接受：在 `__init__` 里一次切好所有文件（计时只算 validate），或者用 `functools.lru_cache` 装饰 `lines`（键里带着 self）。
7. 五个破坏过的 frame（讲义的四种，加上没有事实）在起始代码里都是对的，修完第一处就通过。没有事实时报 `repository facts are empty`，起始代码已经这样做；讲义 Use It 第 2 条要记两三个带收据的事实。

看什么：是不是先看 `receipt_problem` 对那条收据说了什么，而不是去改 example；是不是先 `print(repr(parse_receipt(...)))` 看实际结果；提速时有没有先说清楚“快照不会变”这个前提。

提示：
- H1："Which receipt in the example does the validator turn down, and what does receipt_problem say about it?"
- H2："What does parse_receipt return for that evidence?"
- H3：直接指出 `parse_receipt` 里两种形式的判断顺序。

追问：
- "The receipt resolves, but the line now says something else. What catches that?"（收据只是地址；下一关把那一行的内容钉住，变了就是 stale）
- "The snapshot is two gigabytes. Do you still keep every line?"（按需切，只切被引用的文件；或者只存每行的起始偏移量，按偏移取行）
- "Why not re-run command receipts here?"（有副作用、依赖环境；收据记录的是当时的观察，验收那一步才重跑）
- "Where would a receipt with line 0 come from?"（从 0 起数的工具，比如 LSP；那样抄来的收据每一条都差一行，只有第 0 行能被看出来）

### Part 2 收据钉住（目标 12 分钟）

坑：
- recheck 先看原来那一行：还是原样就是 fresh，哪怕后面又出现了一次（`tests/test_accounts.py:44` 在新版里第 49 行又出现）。先数出现几次再判断，会把它判成 stale。
- 不在原处时，同一个文件里恰好出现一次才是 moved：新提交在 class 上面加了两行 import，`class AccountStore:` 从 18 行挪到 20 行，这条事实没有失效。出现两次是 stale（`return account`，新版的 rename 也以它结尾，选哪一个都是猜）。
- 不往别的文件里找：signup.py 删了，同样的 import 在 `tests/test_accounts.py:3` 还有，但那不是这条事实说的地方，仍然是 stale。
- 命令收据没有行可钉，跳过：11 条事实只出 9 个 pin，顺序和事实一致。
- 空白也算变化：新版 Makefile 只是去掉了行尾空格，这条收据是 stale。按 `rstrip()` 比较会把它判成 fresh。
- 钉住的是被引用那一行原样的 UTF-8 字节，不带换行。`Makefile` 第 2 行开头是制表符、结尾有两个空格，`app/api/messages.py` 第 4 行有 é、à 和破折号。`strip()`、带上 `\n`、`encode("ascii", "replace")` 都会被摘要那条断言抓住；测试自己从文件文本按 `\n` 切出期望的行，不用候选人的 `Repo`。
- 内容寻址的基本要求：对象文件名是内容的 sha256，放在 `objects/<前 2 位>/<后 62 位>`；pin 列表本身也是一个对象；相同的字节只存一份（`app/api/signup.py:3` 和 `tests/test_accounts.py:3` 是同一行，所以是 8 个行对象加 1 个列表，共 9 个）；列表里加时间戳，第二次 pin 就多出一个对象；只放在内存里的 pin 列表重开后读不到。
- 未知的摘要报 KeyError，不能漏出 FileNotFoundError；解析不了的收据报 ValueError。

追问：
- "Two agents pin at the same time?"（内容寻址的写是幂等的；先写临时文件再 `os.replace`，对象要么不在、要么完整；会变的只有 frame 指向哪个列表）
- "When do you delete line objects?"（从还在用的 pin 列表出发标记，没被引用的再清掉，和 git gc 一样）
- "Why store the line and not just its hash?"（stale 的时候要能告诉人“原来写的是什么”；只有哈希的话只知道变了）

### Part 3 决定覆盖（目标 12 分钟）

坑：
- decidable 的 unknown 只有在任务契约授权了这个决定时才能由 agent 自己定，否则是 ask：第一组里 `delegated` 只有 layer，改写提示语那一条要去问人（讲义：Decidable 是“契约给了 agent 选择的权力”，agent 不能给自己授权）。
- human 优先于证据：`error_shape` 有“今天返回 409”的事实，但“以后改成 422 吗”是 human 的问题，仍然是 ask。
- 证据要能解析：`tests/test_signup.py:12` 不存在，proof 这个决定就落到 discoverable 那一条，去读 `Makefile`。
- deferred 必须写进 non_goals，否则是 open；discoverable 必须写明去哪里看，look_at 是空白也是 open。
- 状态：有 ask 就是 ASK，否则有 investigate 或 open 就是 INVESTIGATE，都没有才是 READY。把 open 当成没事，会在“nowhere”那组得到 READY。
- questions 和 reads 按计划顺序、同一项只列一次：第一组按 frame 顺序会先列改写提示语那一条。同一个决定下的多个 human 问题都要保留；另一个决定重复提出同一个问题，不再列第二次。授权已经定下的决定，不因还有 discoverable 线索而回到 investigate。
- 未知的 kind、指向计划外决定的 unknown 都报 ValueError。

追问：
- "Who fills delegated?"（任务契约，也就是第 36 课的 scope contract；agent 自己不能往里加）
- "The evidence says 409 today, product wants 422. Where does that go?"（error_shape 上的 human unknown，在写进代码之前就停下来问）
- "INVESTIGATE with nothing to read. What should the agent do?"（这个决定还是 open：要么找出去哪里看，要么把它写成 unknown）

### Part 4 侦察流（目标 14 分钟）

坑：
- 输出格式由测试的解析代码决定：所有块拼起来以换行结尾，按 `\n` 切开，每行 `split(":", 2)` 得到路径、行号、文本。文本原样，前导空格保留。
- 只在前两个冒号处切：文本里的冒号要留着（`class AccountStore:`、case 测试那一行里的字典）。`split(":")` 会把文本截掉。
- 不是结果的行要跳过（`Binary file ... matches`、上下文分组之间的 `--`）。直接 `split(":", 2)` 解包会在第一行就报 `not enough values to unpack`。
- 正则只搜文本，不搜整行：`tests/http-409/test_conflict.py:3` 的路径里有 409，搜整行就把 error_shape 定在一行 `import unittest` 上。
- 只认探针接受的表面：`docs/adr/` 是 history，那里写的 409 不算 error_shape 的约束（只认 test 和 contract）。
- 一条结果可以同时定下两个决定（`tests/test_signup_case.py:12` 同时定了 case_rule 和 error_shape），只发一次；定过的决定不再响应（signup.py 里第二次出现的 AccountStore、openapi.yaml 里的 Conflict）。
- 全部定下就停：发出最后一条以后立刻结束，一共只拉 10 条。放在循环开头检查会多拉第 11 条；一直读到搜索结束会拉 12 条。讲义：More reading after that point is often avoidance。
- 一定下就发：拿到第一行时只拉了 5 条。
- 搜索提前结束就带着已有的结束；没有探针时一条都不拉。
- 写成普通的 async 函数时，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要看出这里需要 async generator。

追问：
- "What happens to the grep process when you stop?"（生成器 return 不会关掉被迭代的上游；生产里用 `contextlib.aclosing` 或显式 `aclose()`，上游的 finally 里杀掉子进程）
- "Why not let every search finish and then pick?"（讲义：停止条件满足以后再读多半是在回避；还有时间和 token 成本）
- "A hit comes from vendored or generated code?"（表面规则里排除 vendor 和生成目录；或者按路径给探针加白名单）

### Part 5 收窄允许路径（目标 12 分钟）

坑：
- 计划里还不存在的文件也算（`app/emails/` 两个新文件、`tests/conftest.py`），它们的目录可能也是新的。
- 空目录什么都不加，也不挡父目录收起来（`app/cache`）。
- 能收多高就收多高：app 下的文件全都要改时只剩 `app/**`。
- 不存在的禁止路径照样挡住它的目录：`app/.env` 还没有，可 `app/**` 会允许创建它。
- 深层的禁止项挡住它上面的每一层：`svc/core/keys/private/**` 让 keys、core、svc 都不能收。
- 只有替掉两项或以上才收：`lib/only.py` 不变成 `lib/**`；根目录永远不收。
- 结果排序；要改的文件本身被禁止时报 ValueError。同层一个目录未全部列入计划，后面的目录全部列入也不能覆盖这个事实。

追问：
- "Why not turn lib/only.py into lib/**?"（条目没有变少，范围却变宽了，以后在 lib 里新建的文件也被允许）
- "Narrowing still leaves forty entries. Now what?"（讲义：frame 应该放进一屏，放不下说明这里可能是好几个能分别验证的改动，拆开）
- "How does this feed lesson 36's scope contract?"（收窄的结果就是契约的 allowed_files；禁止项照样优先）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出规模、并发、清理、权限边界 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
