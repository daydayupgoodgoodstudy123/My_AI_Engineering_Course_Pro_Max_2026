# 面试官手册：SkillCat（13/24）

候选人计时期间不要看。候选人手里只有 README、`skillcat/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | rank 是越小越优先吗？ | "Yes. The lower rank wins. Rank 0 is the strongest scope." |
| 1 | 两个 scope 的 rank 一样，里面有同名的包，选哪个？ | "Neither. That's a CollisionError, whatever their paths are." |
| 1 | 被遮蔽的两个候选 rank 一样呢？ | "Only a tie at the winning rank is an error. Shadowed ties are fine." |
| 1 | `examples/` 里的 `SKILL.md` 要不要发布？ | "No. Only the immediate children of a scope root are packages." |
| 1 | 包里的符号链接允许吗？ | "Yes, as long as its resolved target stays inside the package." |
| 1 | 目录超出 max_catalog_chars 时从哪里砍？ | "From the end of the priority order. Keep the longest prefix that fits." |
| 2 | 快照放哪、什么格式？ | "One JSON file at the path you're given. It records each SKILL.md's SHA-256 as hex; the rest of the layout is yours." |
| 2 | 能用 mtime 判断改没改吗？ | "No. An edit can keep both the size and the mtime. Go by the content." |
| 2 | 同一个包装在两个 scope 里？ | "Those are two packages. A package is its directory, not its name or its bytes." |
| 2 | scope 的名字或 rank 变了？ | "Results carry the scope you were called with." |
| 2 | 被拒的包也要缓存吗？ | "Yes. An unchanged rejection comes from the snapshot too." |
| 2 | 要原子写吗？ | "Yes, a temp file and a rename. The tests don't simulate a crash." |
| 2 | 快照文件坏了怎么办？ | "Not tested. It's a cache, so rebuilding is fine. Say what you'd do." |
| 3 | 2% 要取整吗？ | "Round down to a whole token." |
| 3 | 窗口已知时，还要再限制 8,000 字符吗？ | "No. The 8,000 characters are only for an unknown window." |
| 3 | token 怎么数？ | "With the count_tokens you're given. It stands in for the host's tokenizer." |
| 3 | 描述缩短到多长、怎么缩短？ | "SHORT_DESCRIPTION_CHARS, with shorten() from catalog.py." |
| 3 | 省略条目之后，要把缩短的描述恢复吗？ | "No. Shortening comes first; omission only removes entries." |
| 3 | 空目录都放不下呢？ | "ValueError." |
| 4 | 同一个引用读两次？ | "Load it again and log it again." |
| 4 | 拒绝事件要不要带请求里的 reason？ | "No. On a refusal, reason holds the refusal code." |
| 4 | 文件刚好等于 max_read_bytes？ | "That's allowed. The limit is at most max_read_bytes." |
| 4 | 所有值都加引号行不行？ | "Yes. Quotes are required where the docstring says; extra quotes still parse." |
| 4 | 非 ASCII 字符要转义吗？ | "No. Only quotes, backslashes and control characters." |
| 4 | 已经激活的 skill 再激活一次？ | "Load the body again and log the activation again." |
| 5 | 图片链接算不算？ | "There are none here. Treat any [text](target) the same way." |
| 5 | 目录路径要不要带结尾的斜杠？ | "No. Package-relative POSIX paths, no trailing slash." |
| 5 | 行内代码里的链接算不算？ | "Only fenced blocks are tested. Say what you'd do." |
| 5 | 链接指向包外一个确实存在的文件？ | "Broken. A skill reads only its own package." |
| 5 | 脚本文件里像链接的东西要不要解析？ | "No. Only Markdown files are read for links." |

## 每关：要看什么、提示、追问

### Part 1 修发现流水线（目标 12 分钟）

一个测试里叠了 4 个缺陷和几个护栏：

1. `package_dirs` 用 `root.rglob("SKILL.md")`，把 `skill-author/examples/release-readiness/SKILL.md` 也当成一个包。错误不在发现时报出来，而是在 `SkillHost.catalog` → `build_catalog` → `resolve_collisions` 里报 `CollisionError: ambiguous 'release-readiness' at rank 0`，消息里的第二条路径指向 examples/。根因在另一条调用链上（`SkillHost.discover` → `discover_scope` → `package_dirs`），traceback 里看不到它，要从消息里的路径倒推。
2. `resolve_collisions` 的排序键是 `(str(c.source), c.rank)`，路径排在前面，结果按目录名字母序选赢家：`agent-runtime` 排在 `home` 和 `repo` 前面，builtin 版本赢了 workspace 版本。平票检查用的是 `min(rank)`，所以同 rank 重名照样能查出来，这也是第 1 处缺陷能报出来的原因。
3. `validate_reference` 在 resolve 之前做包含判断：`root.joinpath(...)` 在字面上永远在 root 下面，`references/team-notes.md -> <tmp>/private/sign-off.md` 就这样放过去了。docstring 写的是“resolved target must stay inside the resolved package root”。
4. `build_catalog` 每弹出一个条目就把整个目录重新序列化一遍，是讲义代码里的 while 循环：1800 个条目要 1.8 到 2.8 秒，限值 0.15 秒，修好后约 4 毫秒。

护栏：
- 为了让 CollisionError 消失，把平票检查删掉，会挂在 "two packages with one name at one rank are an error, whatever their paths"：两个 rank 3 的插件都带 `pdf-tools`。
- 只跳过 `examples/` 目录，会挂在 "a SKILL.md deeper inside a package is not a package of its own"：`tests/fixtures/minimal-skill` 还在。
- 按 scope 名字排序，或者 rank 大的赢，都挂在 "the lower rank wins a collision"。被遮蔽的候选要按 rank 排，三方冲突的 release-readiness 专门查这一点。
- 修第 3 处时干脆拒绝所有符号链接，会挂在 "a symlink that stays inside the package is fine"：`references/latest.md -> python-release.md` 必须能用。
- 只检查最后一段是不是符号链接，挂在 "a symlinked directory that leaves the package is refused"：`references/vendor` 本身是指向包外的目录链接，`vendor/guide.md` 不是链接。
- 只 resolve 目标、不 resolve 包根：测试通过一个符号链接的根目录（`linked-skills`）访问同一个包，包内文件也会被误拒。`resolve(strict=True)` 会让不存在的引用抛 FileNotFoundError，测试要的是 ReferencePathError。
- 修第 4 处时改成累计长度：漏掉条目之间的逗号，或者用 `json.dumps` 默认的分隔符量单个条目，`catalog_chars` 都会和实际序列化长度对不上；放不下就跳过、继续试后面更短的条目，会挂在 "entries are cut from the end"；`>=` 会丢掉刚好放得下的条目；被预算砍掉的名字要排在被 max_entries 砍掉的名字前面。

看什么：是不是先读 CollisionError 消息里的两条路径；是不是先 `print` 出 `discover_scope` 的结果再动手；每改一处就重跑。

提示：
- H1："Which candidates reached resolve_collisions? Look at the two paths in the error."
- H2："What does package_dirs promise about a SKILL.md deeper inside a package?"
- H3：直接指出 `rglob`。后面三处各给一句："What decides options[0]?"、"Which path does the containment check look at, before or after resolve()?"、"How many times does build_catalog serialize the catalog?"

追问：
- "Why not `str(target).startswith(str(root))`?"（兄弟包 `release-readiness-old` 的路径以同一个字符串开头；讲义说 "Literal string-prefix checks are not enough"；用 `Path.parents`、`is_relative_to` 或 `os.path.commonpath`。测试没有覆盖这一条，口头确认。）
- "The symlink is retargeted between validate_reference and the read. What then?"（检查和使用之间的竞态；讲义要求 "check the resolved target every time"；可以逐段用 O_NOFOLLOW 打开，或者打开后再核对。）
- "Workspace beats user here. When is that dangerous?"（讲义的策略表：最高优先级胜出时，一个本地包可以遮蔽可信的包，刚 clone 下来的仓库就能覆盖用户或管理员装的 skill。可以同时展示、要求确认，或者对可信名字拒绝重名。）
- "Codex may show both duplicates. What would that change?"（讲义里的 "keep every candidate" 策略：模型看到含糊的名字，需要按来源限定名字。）

### Part 2 发现结果的 JSON 快照（目标 12 分钟）

坑：
- 用大小加 mtime 判断是否过期：测试把 `Python` 改成 `Pyth0n`，长度不变，再用 `os.utime` 把纳秒级 mtime 改回去，缓存会返回旧描述。
- 用内置的 `hash()` 当摘要：同一个进程里前后一致，测试的几次重开都看不出来；但 str 和 bytes 的 `hash()` 每个进程加的盐不同，下一个会话所有包都会被当成改过。测试检查快照文本里有 `SKILL.md` 的 SHA-256 十六进制摘要，挂在 "the snapshot records the SHA-256 of each SKILL.md"。
- 用 `SKILL.md` 的摘要当键（内容寻址）：同一份字节装在 `incident-review` 和 `incident-review-old` 两个目录里，后者名字和目录不符，重新发现会拒绝它，按摘要查到的却是一个合格候选。身份是目录。
- 把候选的 scope 和 rank 一起存进快照、原样取回：scope 改名为 project、rank 改成 2 之后，结果还是旧的。
- JSON 读回来是 list 和 str：metadata 要还原成二元组的 tuple，source 要还原成 Path。第一次发现走的是新检查，看不出来，重开以后的比较会挂。
- 被拒的包没进快照：重开时 `parsed` 不为空。
- 保存时把别的 scope 的记录丢了：先发现 user，再发现 workspace，workspace 全部重新检查。
- 结果从快照里列，不从磁盘列：删掉的包还在，改名的包找不到。
- 只放在内存里、没写文件：挂在 "the snapshot is saved at the path the cache was given"。
- 根目录里有空格和非 ASCII 字符，描述里有换行，这些用 JSON 存不会出错，只是要原样往返。
- 不测的：写文件的原子性（参考答案先写临时文件再 `os.replace`），快照损坏时的行为（参考答案当作没有缓存，重新检查）。
- 可以接受的：卸载了的包的记录留在快照里不删。结果是从磁盘列出来的，测试不会挂，只是快照越来越大；可以问候选人什么时候清理。

追问：
- "Why SHA-256 and not `hash()`?"（`hash()` 对 str 和 bytes 按进程加盐（PYTHONHASHSEED），下一个会话算出来的值不同，所有包都会被当成改过。）
- "Two hosts write the snapshot at the same time?"（`os.replace` 能保证文件是完整的，但后写的覆盖先写的，另一方的记录就丢了；加锁，或者每个 scope 一个文件，或者写之前重新读一遍再合并。）
- "The snapshot is corrupt. Raise or rebuild?"（它是从磁盘推出来的缓存，重建是安全的；第 15 课的 pin 清单是事实来源，那里必须报错。）
- "What else should invalidate it?"（校验规则或解析器的版本变了，快照里要存版本号；宿主策略变了，就按当前 scope 重新盖章，参考答案已经这样做。）

### Part 3 目录预算（目标 12 分钟）

坑：
- `catalog_budget` 里写 `min(2%, 8000)`：100 万 token 的窗口变成 8000。
- 窗口已知时又加一道 8,000 字符的限制：8,415 字符的目录被缩短。讲义原话："it is not a second cap combined with the 2 percent rule"。
- 取整用 `round`：199,999 的 2% 是 3,999.98，要向下取整成 3,999。
- `if not context_window` 把 0 当成未知窗口，应该报 ValueError。
- 用字符数去比 token 预算：120,000 窗口的预算是 2,400 token，目录有 8,415 个字符。
- 兜底预算按 UTF-8 字节算：weekly-report 的中文描述让最终目录是 7,983 个字符、8,063 个字节。
- 只加 name 和 description 的长度：漏了键名、引号、转义和 source 路径。预算按 `model_json` 的精确文本计。
- 缩短的顺序：要从优先级最低的条目开始，一个一个缩，放得下就停。从最高优先级开始、一次全部缩短、先省略再缩短，都会挂在同一条断言上。
- 被省略的条目还列在 shortened 里：挂在 "an omitted entry is listed as omitted only"。
- “放得下”写成 `used < limit`：测试给一个窗口，它的 2% 刚好等于完整目录的成本（2,511 token），目录要原样发布，一条都不缩短，挂在 "a catalog that fits its budget exactly is published whole"。
- 直接用输入顺序当优先级：测试传进来的是打乱的列表。
- 不测的：只有长于 `SHORT_DESCRIPTION_CHARS` 的描述才算缩短。这组夹具里每条描述都超过 72 个字符，把没变的名字也记进 shortened 的写法看不出来，读代码时留意。

追问：
- "Why lowest priority first?"（workspace 的 skill 是这个仓库自己配的，先牺牲 builtin 描述的细节；也可以统一缩短，各有取舍。）
- "The cut drops the 'Use when…' clause. What does that cost?"（讲义说描述的第二句是触发边界；把它切掉，路由会出错，第 25 课专门评估这一点。更好的规则是保留触发句、缩短能力句。）
- "count_tokens here adds up entry by entry. A real tokenizer doesn't. What changes?"（不能把每条的 token 数相加，只能量最终文本；成本随缩短数和省略数单调变化，可以二分。）
- "You shortened the catalog. Did the activated body get any cheaper?"（没有。讲义的 catalog_cost 和 active_cost 是两本账，缩短描述对一个 900 行的 body 毫无作用。）

### Part 4 logfmt 披露事件（目标 12 分钟）

坑：
- 输出格式由测试的解析器决定：每个事件一行，`key=value` 之间一个空格，以换行结尾。值里有空格、`=`、`"`、反斜杠、换行，或者值是空的，都要加引号并转义。不加引号会挂在 "not a logfmt line"，消息里有原始行。
- 只转义引号，不转义反斜杠和换行，也挂在同一处。多加引号没关系，解析器两种都接受。
- 存根是没有 `yield` 的 `async def`，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要看出这里需要 async generator。
- 未激活就读：拒绝，原因是 not_active；另一个没激活的 skill 也一样。
- 文件存在但 `SKILL.md` 的决策图里没写：not_declared。决策图里写了、但是一个指向包外的符号链接：invalid_path，要复用 Part 1 修好的 `validate_reference`。
- 拒绝原因按 docstring 的顺序取第一条：最后一个请求 `../incident-review/SKILL.md` 既没有声明、路径也不合法，应该是 not_declared。先调 `validate_reference` 再查决策图会得到 invalid_path，挂在 "a read is refused with the first reason that applies, in the documented order"。
- 字节：container-release.md 是 1,000 个字符、1,088 个字节，超限；docs-release.md 刚好 1,024 个字节，可以读；激活事件的 bytes 是 body 的 UTF-8 字节数，body 里有一个破折号，按字符数算会少 2，算上 frontmatter 会多。
- 事件要立刻输出：测试会数第二个事件出来时多拉取了几个请求，先把请求读完再处理会拉 500 个。
- 内容不能进日志：测试检查文件里的内容（包括包外文件里的假密钥）没有出现在输出里。
- 可以接受的：用 `json.dumps` 给要加引号的值加引号。非 ASCII 字符会写成 `\uXXXX`，和 docstring 不一致，但解析器会把它还原，测试不挂；可以问候选人别的 logfmt 读取方会不会还原。

追问：
- "Why log the reason at all?"（讲义："The reason turns a context choice into reviewable evidence. It also helps identify instructions that cause the agent to load every file 'just in case.'"）
- "The reason is written by the model. Can it leak a secret?"（可以；讲义要求 "Record disclosure events without logging secrets"，要截断或脱敏，内容永远不记。）
- "A 2 GB reference?"（只读 max_read_bytes + 1 个字节就能判断超限，参考答案就是这样做的。）
- "Does a refused read count against active context?"（不算，没有任何东西进上下文；active_cost 只算激活的 body 和真正加载的资源。）

### Part 5 引用图一跳可达（目标 12 分钟）

坑：
- 链接相对于所在文件的目录解析：`references/python-release.md` 里的 `checklists/pypi.md` 是 `references/checklists/pypi.md`，`../assets/changelog-template.md` 是 `assets/changelog-template.md`，`./references/docs-release.md` 要规范化。
- 去掉 `#fragment` 和 `?query`；`#choose-the-path` 这种只有片段的链接不是引用。
- 深度取最少跳数：container-release.md 既被 `SKILL.md` 直接链接，也被 python-release.md 链接，深度是 1。递归 DFS 先走 python-release.md，会把它算成 2，后面的 signing.md 和 key-rotation.md 跟着错。
- 围栏代码块里的链接不算，``` 和 ~~~ 两种都有：archive.md 只出现在代码块里，是死文件。
- 整目录链接（`[the references](references/)`）只报告，不展开：legacy.md 只能从这里“到达”，所以是死文件。
- 只读 Markdown 文件：`scripts/check_version.py` 里的 `CHECKS[name](version)` 长得像链接。
- 带 scheme 的链接（https、mailto）不是引用。坏链接按写法报告目标，去掉片段：`checklists/old-pypi.md#upload` 报成 `checklists/old-pypi.md`。包外的路径也算坏链接：`../../incident-review/references/policy.md` 在磁盘上确实存在，只看文件存不存在的写法会把它记进 depth，挂在 "every file that takes two or more links is deep"。
- 死文件只看 `references/` 下面：`assets/logo.txt` 没人引用，但不算。
- deep 是两跳及以上，不是严格大于两跳。

追问：
- "Why one hop?"（讲义："One hop makes reachability testable and reduces the chance that a needed constraint never enters context."）
- "How would you fix the deep files in this package?"（从 `SKILL.md` 直接链接，并写明加载条件；或者把 key-rotation.md 并进 signing.md。）
- "Dead files: delete them or link them?"（逐个决定；死文件照样随包发布，一句 "read references/ for more" 就可能把它们全读进来。）
- "What would a full CommonMark parser add?"（引用式链接 `[x][id]`、图片、尖括号目标和带标题的链接。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback 和错误消息里的路径、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出信任边界、并发写、预算单位、日志脱敏 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
