# 面试官手册：TaskScope（14/36）

候选人计时期间不要看。候选人手里只有 README、`taskscope/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 告诉候选人：没有真实的仓库和 agent，`RunSummary` 和 diff 字节串都是测试写好的。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 合并时 allowed_files 能不能直接对两张 glob 表求交集？ | "No. Keep both lists. A path is allowed when it matches one pattern from each." |
| 1 | violation budget 数 finding 还是数文件？ | "Files. Distinct off-scope files. Soft and forbidden files don't count." |
| 1 | 同一个文件被改了两次算几个？ | "One file." |
| 1 | 带端口的主机算同一个吗？ | "Yes. Compare lowercased, without the port. An IPv6 address keeps its brackets." |
| 1 | allowlist 里的主机也要规范化吗？ | "Yes. Both sides compare the same way." |
| 1 | allowed_files 是空列表呢？ | "Nothing is in scope. That's a read-only task." |
| 1 | 合并出来的合同还会再拿去合并吗？ | "It can be. Merging again must keep every list, the child's own allowed_within too." |
| 1 | 能把编译好的模式缓存起来吗？ | "Sure. The test builds a fresh contract, so the check itself still has to be fast." |
| 2 | 文件里写什么？ | "One JSON object. task_id, passed and closed_at at the top level. The rest is up to you, as long as load gives back the same ClosedTask." |
| 2 | 内容一样的话能覆盖吗？ | "No. A task closes once. Raise FileExistsError." |
| 2 | 目标位置已经有一个符号链接或者目录呢？ | "Same rule. Refuse, and leave it alone." |
| 2 | 记录里有 NaN 怎么办？ | "ValueError, and nothing on disk. Auditors read this with tools that reject NaN." |
| 2 | touched_files 里的重复要去掉吗？ | "No. The archive keeps the run as it was recorded." |
| 2 | 两个进程同时关同一个任务呢？ | "Exactly one may win. Tell me how yours makes sure of that." |
| 2 | 要 fsync 吗？ | "Not for the tests. What would you do in production?" |
| 3 | `**` 能匹配零层目录吗？ | "Yes. lib/**/*.py covers lib/x.py." |
| 3 | macOS 不区分大小写，匹配要不要也不区分？ | "Case-sensitive. The repository is the source of truth, not the laptop's filesystem." |
| 3 | 支持 `{a,b}` 或者用 `^` 取反吗？ | "No. Only what the translate docstring lists." |
| 3 | 模式本身要规范化吗？ | "No. Patterns are written from the repository root, the way normalized paths look." |
| 3 | checker 遇到 `../secrets.env` 怎么办？ | "It's outside the repository, so it's forbidden. Keep the path as the agent wrote it." |
| 4 | diff 是 UTF-8 吗？ | "The headers are ASCII; git quotes everything else. Hunk lines can be any bytes." |
| 4 | copy 是什么？ | "git diff -C. The source stays as it was. Only the destination is written." |
| 4 | 只改了权限位算不算？ | "Yes. chmod +x on a release script is a write." |
| 4 | 什么时候输出？ | "As soon as the file's header is complete: at its first @@, at the next diff --git, or at the end of the stream." |
| 4 | over-budget 报一次还是每个文件都报？ | "Once, right after the file that tips it." |
| 4 | 要输出完整的 SARIF 日志（runs、tool）吗？ | "No. One result object per line. The CI step wraps them." |
| 4 | 同一个文件在两个 commit 的 diff 里都出现了呢？ | "Report it once." |
| 5 | 好几层都不允许时，报哪一层？ | "The one nearest the project." |
| 5 | 一个路径既被禁止又不被允许？ | "Forbidden wins, whichever layers say what." |
| 5 | 子任务能放宽任务的范围吗？ | "No. Every layer has to allow the path." |
| 5 | task 直接挂在 project 下面？ | "ValueError. Every task belongs to a feature." |
| 5 | project 合同可以写 parent 吗？ | "No. The project is the top. A parent there is a ValueError." |
| 5 | network_egress 的 None 和 []？ | "None doesn't restrict. [] allows nothing, and that holds all the way down." |
| 5 | 有两个合同的 task_id 一样？ | "ValueError." |

## 每关：要看什么、提示、追问

### Part 1 修 checker（目标 12 分钟）

一个测试里叠了 4 个缺陷和一串护栏：

1. `merge_contracts` 把两张 allowed glob 表当字符串集合求交集。项目合同写 `lib/**/*.py`，任务合同写 `lib/upload/*.py`，交集是空的，合并后只剩两边字面相同的 `app.py`。错误不在 merge 报出来，而是在 `scope_check` 的结果里：`lib/upload/pdf.py` 被分到了 off-scope。docstring 写的是保留两张表：`allowed_files` 取子合同的，父合同的表进 `allowed_within`，`Classifier` 已经会逐张检查。子合同自己的 `allowed_within` 也要接在后面：测试把合并好的合同放到一个只写了 `**` 的合同下面再合并一次，丢了它，项目的表就没了，`tools/bump.py` 会变成 in scope。
2. `violation_budget` 数的是 warn 级 finding 的条数。所有越界文件只产生一条 finding，所以预算 ≥ 1 时越界多少个文件都通过（测验 Q5）。docstring 写的是数不同的越界文件。
3. 网络出口直接拿字符串比较，`API.Anthropic.com:443` 不等于 `api.anthropic.com`。docstring 写的是不区分大小写、去掉端口，IPv6 保留方括号。
4. 计时：`PatternSet` 对每个路径把每条 glob 都 `fnmatch` 一遍。1,700 个文件、3,000 条 glob，约 500 万次 `fnmatch`，本机 1 到 2.5 秒。按 glob 第一个通配符前面的字面目录建索引，每个路径只查自己的各级目录，5 到 12 毫秒。

护栏：
- 用并集合并、只留子合同、只留父合同，都会被第一条断言抓住；`child.allowed_files or parent.allowed_files` 会让只读任务（空 allow-list）什么都能写。
- soft 文件和同一文件的重复修改不进预算；forbidden 文件自己 block，也不进预算；`>=` 会在恰好等于预算时误判。
- 30 分钟正好等于 30 分钟预算，不算超时。
- 主机：只转小写不去端口会挂；只去掉 `:443` 也会挂（还有 `:8443`、`:5432`）；在第一个冒号处切会把 `[2001:db8::7]` 切成 `[2001`，两边一起切时所有 IPv6 地址都变成同一个，`[2001:db8::8]` 也被放行；在最后一个冒号处切，没有端口的 IPv6 会被切坏；allowlist 不规范化，`LocalHost` 就对不上。`[]` 拒绝全部，`None` 不检查。两边都用 `urlsplit("//" + host).hostname` 也能通过：方括号被去掉了，但两边一致，比较结果相同。
- 索引：没有字面目录的 glob（`**/secrets/**`、`*.lock`）必须对所有路径生效；按第一段目录分桶不够，3,000 条 `services/svc-NNNN/**` 全在 `services` 一个桶里，还是 0.4 到 0.9 秒；拿 `tests/test_` 这种截在段中间的前缀去查目录，会漏掉 `tests/test_*.py`；拿最后一个 `/` 前面的部分当目录，`lib/**/*.py` 会落进 `lib/**` 这个永远查不到的桶，第一条断言就挂。forbidden 必须先于 allowed 判断，允许范围内的文档路径（`services/svc-2484/README.md`）算 in scope，不算 soft。
- 有两种写法贴着 0.1 秒的上限，时过时不过：在 `PatternSet.__init__` 里把 3,000 条 glob 全部预编译（计时的那次检查第一次见到这些 glob，3,000 次编译都算在里面，本机 60 到 120 毫秒）；把 3,000 条 `fnmatch.translate` 用 `|` 拼成一条大正则（编译加匹配 60 到 180 毫秒）。两者都在为用不到的 glob 付钱。即使这一次过了，也要指出来，提示只编译候选桶里的那几十条：`fnmatch` 自带缓存，Part 3 以后用 `compile_glob` 的缓存。

看什么：是不是先读断言，再打印 `effective.allowed_files` 去找上游；有没有对照 docstring 一条条核对；计时那一层有没有先 profile（`fnmatch` 被调了约 500 万次）再动手。

提示：
- 第 1 层：H1 "Which contract allows lib/upload/pdf.py? What does the merged contract say?" H2 "Print effective.allowed_files." H3 直接指出 merge 里 allowed_files 那一行。
- 第 2 层：H1 "How many warn findings does a run with three off-scope files produce?" H2 "Read the violation_budget paragraph of scope_check."
- 第 3 层：H1 "Print the host the run reports and the allowlist side by side."
- 第 4 层：H1 "Profile it. How many fnmatch calls?" H2 "Which of the 3,000 globs could possibly match services/svc-2480/src/handler_0.py?" H3 "File each glob under the literal directory in front of its first wildcard."

追问：
- "Why not compute the intersection of two globs?"（glob 的包含关系一般很难判定；保留两张表、逐张匹配是精确的，代价只是多查一次）
- "merge_contracts unions docs_paths_soft. Is that least privilege?"（不是。soft 会把 warn 降成 info，取并集等于放宽；应该像 allowed_within 一样保留每个合同自己的表）
- "elapsed_minutes is NaN. What does the time check do?"（`nan > 30` 是 False，静默通过；输入要先校验）
- "Where would you cache the compiled contract?"（合同是不可变文件，按内容 hash 缓存）

### Part 2 归档（目标 12 分钟）

坑：
- 用 `"w"` 打开，第二次关闭会覆盖第一次的证据。
- 先 `exists()` 再写：`closed/T-001.json` 是一个指向外面的悬空符号链接时，`exists()` 返回 False，`write_bytes` 顺着链接把文件写到了仓库外面。先写临时文件再 `os.replace`，会把那个链接本身换掉。`os.open(..., O_CREAT | O_EXCL)`（也就是 `open(path, "x")`）在路径以任何形式存在时都失败，而且不跟随链接。
- 先建文件再 `json.dump`：遇到 NaN 时文件已经建了一半，这个任务再也关不上。要先序列化成字节（`allow_nan=False`），再独占创建。Python 的 json 默认允许 NaN，写出来的不是严格 JSON。
- 往返：`network_egress` 的 `[]` 和 `None` 不能互相变（`or []`、`or None` 都错）；`allowed_within` 是表的表；findings 要还原成 `Finding`；`touched_files` 保持原样，包括重复和顺序；`0.1 + 0.2` 和 `1767225600.1234567` 原样读回，round 到 6 位或者转成 ISO 时间都会丢精度。
- 顶层的 `passed` 必须是 JSON 布尔值，写成 0/1 或字符串都不对；值取 `report.passed()`：T-010 只有一条 info finding，照样是 true，写成“没有 finding 才算通过”会挂。
- `closed/` 已经存在时 `mkdir` 不能报错（`exist_ok=True`），否则第二个任务就关不上；遇到 `FileExistsError` 直接返回旧文件也不行，再次关闭必须报错。
- task_id 必须是普通文件名：`../T-004`、`T-004/x`、空串、`.hidden`、带空格的都要 ValueError，而且要在写盘之前检查；用 `re.match` 只查开头，`T-004/x` 会漏过去；`load` 也要检查，否则 `../closed/T-001` 能读到文件。
- `task_ids()` 要跳过临时文件和 macOS 的 `._T-001.json`；按 `.stem` 或按 `.json` 后缀取名都会把它们算进来。
- 重开以后要能读到，状态不能只放在内存里。

追问：
- "Two gates close the same task at the same moment?"（`O_EXCL` 保证只有一个成功；网络文件系统上不一定可靠，换成数据库的唯一键）
- "The machine dies halfway through the write. What's on disk?"（独占创建的文件只写了一半，任务再也关不上。先写临时文件、fsync，再用 `os.link` 放到最终位置：既是独占的，又是原子的；目录也要 fsync）
- "T-001 and t-001 on macOS?"（默认文件系统不区分大小写，两个任务会撞名；规范化 task_id，或者只允许一种大小写）
- "Why keep duplicate touches?"（归档是证据，按记录原样保存；去重是分析时的事）

### Part 3 glob 方言（目标 12 分钟）

坑：
- `**/` 要能匹配零层目录：`lib/**/*.py` 覆盖 `lib/x.py`，`**/*.md` 覆盖根目录的 `README.md`（测验 Q3 的现象正好反过来）。开头的 `**/` 也只吞整段目录：`**/.env` 不匹配 `deploy/prod.env`，翻译成 `.*` 会挂。
- `*` 和 `?` 不跨 `/`：`*.md` 不匹配 `docs/guide.md`；段内的 `**`（`lib/**.py`）等于 `*`。
- `dir/**` 只匹配 dir 下面的文件，不匹配 dir 本身，也不匹配 `docsite/`；结尾的 `/` 等于 `/**`。
- 字符类：`[!a]` 要写成 `[^a/]`，否则会匹配 `/`；范围 `[1-3]` 不能被转义成字面量。
- 反斜杠转义：`web/app/\[slug\]/page.tsx` 是 Next.js 的动态路由目录，`[slug]` 不转义就是字符类。其他字符都要 `re.escape`，`docs/v1.2/` 里的点、`lib/c++/` 里的加号都是字面量。
- 大小写敏感，`re.IGNORECASE` 会挂。
- 非法模式（空、绝对路径、末尾单独的反斜杠、没闭合的 `[`）报 ValueError，不能像 fnmatch 那样当字面量。
- `normalize_path`：`posixpath.normpath` 把 `lib/../../x` 变成 `../x`、把空串变成 `.`，都不报错；`startswith("..")` 会把 `..notes/todo.md` 误杀；`lib/..` 规范化后是空的，要报错；开头的 `/` 要拒绝，不能剥掉；结尾的 `/` 要去掉。`normpath` 之后再准确地检查（结果是 `.`、`..` 或者以 `../` 开头就拒绝）也是对的。
- 接进 checker：`PatternSet` 改用 `compile_glob`；`scope_check` 先规范化再去重（`./lib/pdf.py` 和 `lib/pdf.py` 是同一个文件）；越出仓库的路径归为 forbidden，保留原样。
- 索引和方言要一致：Part 1 的索引如果把没有通配符的模式直接当字面路径，`docs/`（目录简写）就会被当成文件名；带转义的模式要先解转义再算字面目录。

看什么：是不是先写一张小的用例表再写翻译器；有没有用 `re.fullmatch`；改完方言有没有回头跑 Part 1，确认计时还在。

提示：
- H1 "What should lib/**/*.py match that fnmatch misses?"
- H2 "Translate segment by segment. What does a whole-segment ** become, at the start, the middle and the end?"
- H3 "`(?:[^/]+/)*` for a leading or middle **, `.+` for a trailing one."

追问：
- "Python 3.13 has PurePath.full_match. Why not use it?"（还要支持 3.11 和 3.12；而且它的方言细节和合同作者的约定不一定一致，方言要写进合同 schema）
- "What does [+-0] match?"（`+` 到 `0` 的范围包含 `/`，类就跨过了目录；参考实现在肯定类前面加 `(?!/)`。测试不查这一条）
- "Should compile reject ./app.py or a//b in a contract?"（应该，在加载合同时 lint，模式永远匹配不到就是写错了）
- "How do you keep macOS developers and Linux CI in agreement?"（以 `git ls-files` 的大小写为准，匹配一律区分大小写）

### Part 4 流式 diff 检查（目标 14 分钟）

坑：
- 输出格式由测试的 `"".join(...)`、`splitlines()` 和逐行 `json.loads` 决定：每条 result 后面恰好一个换行。少了报 Extra data，多一个空行报 Expecting value。
- 输入是字节，按任意位置切块：要在字节层面按 `\n` 拼行。每块单独 `decode("utf-8")` 会在 Latin-1 的 hunk 行上报 UnicodeDecodeError；跨块的半行要留到下一块；最后一行可以没有换行。流结束时不管还剩没剩半行，当前文件都要判定：只在 `if buffer:` 里收尾的写法，会漏掉以换行结尾、没有 hunk 的最后一个文件（测试里有一个只改权限位的流）。
- 路径从哪来：`diff --git` 头。没有 `---`/`+++` 的情况很多（二进制文件、只改权限位、新建的空文件、100% 相似的重命名），只靠 `---`/`+++` 会漏。删除也算写。
- 带空格的路径 git 不加引号：`diff --git a/docs/release notes.md b/docs/release notes.md`，`split()` 会切坏。非重命名时两边路径相同，按长度对半分最稳；路径里还有 `notes/plan b/todo.md` 这种带 ` b/` 的，`split(" b/", 1)` 也会切错。
- 引号形式：带 `"`、`\`、控制字符或非 ASCII 字节的路径会被加上双引号，按 C 转义写，非 ASCII 是每个 UTF-8 字节一个 `\ooo`。要先还原成字节再按 UTF-8 解码，按 Latin-1 解码会得到 `cafÃ©.md`；拿 `ast.literal_eval` 当 str 字面量解析也是这个结果。`codecs.escape_decode`（官方文档里没有写）得到的是字节，再按 UTF-8 解码是对的。`rename from` 这一行也会被加引号。
- 重命名两边都检查（`lib/search/rank.py` 越界）；copy 只检查目标，源文件 `scripts/deploy.sh` 没有被写。
- hunk 里删掉的 SQL 注释 `-- a/b test cohort` 在 diff 里是 `--- a/b test cohort`，不是文件头。
- 同一个文件在后面的 commit 里又出现一次，只报一次。
- 预算：在不同越界文件第一次超过 `violation_budget` 时补一条 `scope/over-budget`，只报一次；soft 和 forbidden 文件不算。同一个越界文件出现两次只算一次：先计数再查重，`tools/a.sh` 第二次出现时多算了一个，over-budget 就报不出来了。
- `uri` 是 URI reference：`urllib.parse.quote` 默认保留 `/`，空格变 `%20`，`é` 变 `%C3%A9`。
- 越界即输出：文件头一完整（看到 `@@`）就 yield，不能等到下一个 `diff --git` 或流结束。探针在第一个文件后面跟了 400 块 hunk。

看什么：是不是先在纸上列出 diff 的几种文件头；状态机是不是只在 `@@` 之前认文件头；有没有拿 1 字节的切块自测。

提示：
- H1 "Which lines can tell you a path, and which of them always exist?"
- H2 "When is a file's header complete?"
- H3 "Keep a bytearray, cut complete lines off its front, and keep the header lines of the current file until @@."

追问：
- "Why bytes and not text?"（git 输出的是字节，内容可以是任何编码；只有文件头需要解码）
- "Why find b'\n' instead of splitlines()?"（`splitlines()` 还会在 `\r` 处切，CRLF 文件或带单独 `\r` 的 hunk 行会被切成几行；文件头里 git 不会写裸的 `\r`，所以测试照样通过，但按 `\n` 切才和 git 的格式一致）
- "core.quotePath=false?"（文件头里直接是 UTF-8 字节，不加引号；那时文件头要按 UTF-8 解码，并且要处理跨块切开的多字节字符）
- "What would you actually run in CI?"（`git diff --name-status -z`：NUL 分隔、不加引号、直接给出 R/C 两边，比解析补丁文本简单得多）
- "Upload to GitHub code scanning?"（外面包一层 SARIF log：`version`、`runs[].tool.driver.rules`，results 原样放进去）
- "A 2 GB diff?"（内存只放当前文件的头几行，hunk 行看一眼就丢；输出是流式的，背压由消费方决定）

### Part 5 合同链（目标 10 分钟）

坑：
- 解释取离项目最近的那一层：`lib/search/index.py` 被 feature 和 task 都排除，报 feature；从叶子往上找会报 task。
- forbidden 优先于 not allowed，不管是哪一层说的：`secrets/prod.env` 项目不允许、任务禁止，报的是任务的 forbidden。每层先问禁止再问允许的单趟遍历会报项目的 not allowed。
- 同一层里取第一条匹配的 forbidden glob（`scripts/**`，不是 `scripts/release.sh`）。拿合并后排好序的 forbidden 表去找第一条，会先撞上任务的 `**/release.sh`，报成 T-001。
- 子任务写了 `lib/**` 和 `tools/**`，也放宽不了上层：`lib/pdf/render.py` 被 task 排除，`tools/upload_cli.py` 被项目排除（三层以下项目的表照样生效，合并时丢掉父合同的 `allowed_within` 会在这里漏）。
- 主机：`None` 不限制，`[]` 拒绝全部，并且一路保持；`if not egress: continue` 会把 `[]` 当成不限制。比较方式和 `scope_check` 一样：测试里的 `API.Anthropic.com:443` 带端口，只转小写会挂。
- `effective()` 从项目往下用 `merge_contracts` 折叠。自己写一个跳过空列表的交集会丢掉 deny-all；从叶子往上折，审批的顺序会反过来。
- 链要完整：父合同不存在、task 直接挂在 project 下、subtask 挂在 feature 下、非项目合同没有 parent、project 合同反而有 parent，都报 ValueError；只要求 parent 在上面某一层（不是正好高一层）会放过跳层；未知 task_id 报 KeyError；task_id 重复报 ValueError（用 dict 收集会静默留下最后一个）。

追问：
- "Why the layer nearest the project?"（那是必须由人改的那份合同；下层改了也没用）
- "Five hundred tasks share one feature. Cost?"（按节点缓存 effective，树上的动态规划）
- "Where does the feature list's one-in_progress rule plug in?"（启动检查：只有 active feature 下面的链能被解析出来）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读断言和 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出并发、崩溃一致性、编码、规模、合同版本 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
