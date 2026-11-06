# 面试官手册：VerifyGate（14/38）

候选人计时期间不要看。候选人手里只有 README、`verifygate/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 告诉候选人：整套题不调用 LLM，也不联网。签名用测试里的固定密钥；Part 4 的闸门是测试里写好的替身，按最新一次运行给出结论。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 记录里是 argv 列表，合同里是字符串，怎么比？ | "As shell text. shlex.join of the argv; a string is split with shlex.split first." |
| 1 | 同一条命令跑了几次，看哪次？ | "The latest one, the last record in the log. Earlier runs are history." |
| 1 | 不是验收命令的记录要管吗？ | "Not for these findings. Only the acceptance commands decide." |
| 1 | warn 能覆盖吗？ | "No. Only block findings, and never a null exit." |
| 1 | 同一个 finding 有两条有效覆盖呢？ | "The last one counts. Its user and reason go in the report." |
| 1 | 两条 finding 的 code 一样，一条覆盖能清掉两条吗？ | "Yes. Overrides are keyed by finding code, as in the lesson. Tell me what you'd change." |
| 1 | ts 要不要签进去？ | "Yes. Every field but the signature." |
| 2 | append 要自己签名吗？ | "No. The override CLI signs. append checks the entry and refuses one that doesn't verify." |
| 2 | 坏行跳过还是报错？ | "Raise LogTampered with its line number. It's an audit log, so a bad line is a finding, not noise." |
| 2 | 行号从 0 还是从 1 开始？ | "From 1, like an editor." |
| 2 | 文件里能有空行吗？ | "No. append never writes one, so a blank line means someone edited the file." |
| 2 | 能把 ts 统一写成 float 吗？ | "No. Write the entry as it is. The signature covers the exact value." |
| 2 | 要支持多个进程同时写吗？ | "Not today. Tell me what you would do." |
| 3 | 产物是空的和不存在有区别吗？ | "Yes. None is missing and blocks. An empty list or dict is there and clean." |
| 3 | 规则没写 severity，或者写成 "Warn" 呢？ | "Block. Severity is fixed when the rule is written; the gate doesn't guess." |
| 3 | strict 对 info 做什么？ | "Nothing. Only warn becomes block." |
| 3 | 覆盖在 strict 之前还是之后？ | "After. A human can sign off on a block that strict made." |
| 3 | 覆盖率正好低一个百分点呢？ | "A warn. More than one point is a block." |
| 3 | 报告里放生成时间吗？ | "No. Same artifacts, same bytes." |
| 3 | task id 里有斜杠呢？ | "Refuse it. One task, one path, inside outputs/verification." |
| 4 | 第一条记录到之前要发摘要吗？ | "Yes. The verdict before anything ran." |
| 4 | 一条记录都没来呢？ | "Then that first summary is the only one." |
| 4 | 什么算变化？ | "Anything that changes the summary text." |
| 4 | 最后要不要再发一个分隔符？ | "No. Breaks go between summaries only." |
| 4 | 要转义哪些字符？ | "The five in the docstring, the backslash first. Nothing else." |
| 5 | 父提交不在列表里呢？ | "ValueError, unless it's the base." |
| 5 | 父提交失败了，子提交还验吗？ | "Yes, against the parent's coverage. blocked_by says it can't land yet." |
| 5 | 父提交没有覆盖率报告呢？ | "Use what the parent was compared against, down to the base." |
| 5 | artifacts 的 head_commit 和 sha 对不上呢？ | "They're from an older push. The commit is waiting." |
| 5 | 兄弟提交按什么顺序？ | "The order they were given." |

## 每关：要看什么、提示、追问

### Part 1 修验收检查和覆盖（目标 12 分钟）

一个测试里叠了 5 个缺陷和一串护栏：

1. `command_text` 对 argv 列表用了 `str()`，得到 `"['pytest', '-x', ...]"`，和合同里的字符串永远对不上，三条验收命令全报 `acceptance.missing`。现象出在 `acceptance_findings` 的结果里，根因在两层调用之下的 `commands.py`。这正是测验 Q9：第 37 课按讲义记录 exact argv，第 38 课却按字符串比较。只把列表用空格拼起来不行，合同里 `pytest -k "card and not slow" ...` 的引号对不上；两边都用空格拼接，又会把 `["pytest", "-k", "card", "and", "not", "slow", ...]` 这个不同的命令当成同一个。
2. `latest_run` 找到第一条匹配就返回，先失败、重试后成功的验收命令仍报 `acceptance.failed`。docstring 写的是最后一条。这是测验 Q6 和 Q10：所有失败都 block 的话，正常的“失败、修复、重跑”永远过不了闸门，反而逼 agent 去删记录。
3. `make_override` 先签名再加 `ts`，签名只覆盖了五个字段，`verify_signature` 却按除签名外的全部字段验，于是刚签好的覆盖验不过，`apply_overrides` 把它当伪造的丢掉。现象出在 `apply_overrides` 的结果里，根因在 `signing.py`，候选人往往先怀疑自己刚看的 `apply_overrides`。只改 `verify_signature` 让它也跳过 `ts`，两边对上了，可时间戳就不在签名里了，后面 “the timestamp is signed too” 会抓住。
4. `apply_overrides` 没比较 `head_commit`，HEAD 变了以后旧的覆盖照样生效。课里要求覆盖记下当时的 HEAD：代码变了，人看过的就不是这份代码了。
5. 计时：`acceptance_findings` 对每条验收命令调一次 `latest_run`，每次都把整份日志重新规范化（每条记录一次 `shlex.join`）。400 条命令、8400 条记录约 2 秒，先建一次索引约 8 毫秒。改成倒序扫描、找到就返回也不够：这份日志里验收记录都在前面，照样要 2 秒左右。把每条记录规范化一次存成列表、再逐条命令扫描，本机 25–70 毫秒，机器很忙时到过 160 毫秒：这仍是命令数乘记录数的比较，测试不保证放过它；过了也要请候选人说出它为什么还是平方级。建字典才是要的写法。

护栏：一条覆盖只清掉它自己那个 code，其他 block 不动；传进来的列表不能改；别的任务的、改过字段的、改过 ts 的、别的密钥签的、没签名的条目都不算；null exit 不能覆盖；warn 不需要也不能覆盖；同一个 code 有两条有效覆盖时用最后一条，但只在算数的条目里取：先按 code 留下最后一条、再去验它，同一份日志里 T-43 对同一个 code 的覆盖就会把 T-42 的挤掉；空白的 reason、空密钥都要拒绝。

看什么：是不是先打印 `command_text` 的实际输出，而不是猜；第 3 层是不是直接调 `verify_signature(entry, SECRET)` 看结果；有没有对着 docstring 一条条核对；计时那一层是先 profile 还是直接动手。

提示：
- 第 1 层：H1 "What does acceptance_findings compare the contract's command with?" H2 "Print command_text of one record." H3 直接指出 `command_text` 的列表分支。
- 第 2 层：H1 "Which of the two signup runs did it look at?"
- 第 3 层：H1 "Does the entry make_override just returned verify?" H2 "What did sign() cover, and what does verify_signature check?"
- 第 4 层：H1 "What is different between the two calls?"
- 第 5 层：H1 "Profile it. How many times does shlex.join run?"

追问：
- "Normalising argv fixes quoting. What does it not fix?"（`python -m pytest` 和 `pytest`、参数顺序不同、`cd sub && pytest`；更稳的是合同给每条验收命令一个 id，runner 在记录里带上，测验 Q9）
- "The latest run passed, but the agent edited a file after it. Is the task done?"（不算，验收记录要晚于最后一次写入，或者记录运行时的 tree hash，测验 Q10）
- "What does this HMAC prove?"（只证明签名的人持有共享密钥，`user_id` 是自己填的；agent 的环境里不能有这个密钥；要证明是哪个人，得用个人密钥签名或者经过身份认证的审批服务，测验 Q12、Q16）
- "Why hmac.compare_digest instead of ==?"（常数时间比较，不从耗时泄露签名前缀）
- "Why can't a null exit be overridden?"（没有结果，人无从签字；出路是重跑，第 37 课的 No exit, no progress）

### Part 2 签名的覆盖日志（目标 12 分钟）

坑：
- 空密钥要拒绝（fail closed，对应课里的 `_load_override_secret`）。文件还不存在时 `entries()` 返回空列表；第一次 append 要把 `outputs/verification/` 建出来。
- 只追加，不重写。用 `"w"` 打开只会留下最后一条。整份重写即使内容一样，也会把另一个工具写的那一行重新序列化，前缀断言会抓住：审计日志里已经写下的字节不能动。
- 每条一行：`json.dumps(entry)` 加换行。`indent=2` 会写成多行，行号就乱了。
- append 返回的行号按文件里实际有几行来算。两个实例交替写同一个文件时，各自在内存里计数会得到 (5, 5, 6)。
- append 先校验再写：字段必须正好是六个加签名，签名必须验得过，被拒的条目一个字节也不能写进去。只验签名、不验字段的话，用密钥签过但多带一个字段的条目会混进去。
- 读的时候也要查字段，不能只验签名：另一个工具把 `ts` 改名成 `timestamp` 再签名，签名验得过，字段却不是那六个，要在那一行报 `LogTampered`。append 和 entries 共用一个校验函数最省事。
- 按字段验签名，不按行的写法验。另一个工具写的行键顺序不同、分隔符带空格、UTF-8 原样写，照样要验得过。要求每一行必须和 `json.dumps(entry)` 一模一样会在第 4 行误报。
- 按 `"\n"` 切分后最后一段是空串，要丢掉，否则一份干净的日志在第 4 行报错。
- 坏行抛 `LogTampered`，带从 1 开始的行号，报第一处：改过的字段、改过的 ts、多出来的字段、被截断的行、空行、`null`、重复字段、乱码签名。`JSONDecodeError` 不能漏出去，空行不能跳过。
- 重复字段：Python 的 json 取最后一个值，签名按最后一个值验得过，但别的读取方可能取第一个，两边就读出了不同的 finding_code。要用 `object_pairs_hook` 拒掉。
- 签名里有非 ASCII 字符时，`hmac.compare_digest` 会抛 TypeError。`signing.verify_signature` 已经处理了，自己另写比较的人会在这里崩。
- 精度：ts 有 float 也有 int（覆盖工具记整秒）。读回来以后规范 JSON 的字节必须和签名时一样，`1767225660` 变成 `1767225660.0` 签名就对不上了。
- 测试分不出、也都可以接受的写法：append 用 `ensure_ascii=False` 或 `sort_keys=True` 写行，签名照样验得过；行号用 `len(self.entries()) + 1` 算也对，代价是每次追加都把整份日志读一遍，日志里有坏行时干脆拒绝追加，可以和候选人讨论这样好不好。

追问：
- "Two CI jobs append at the same moment. What can go wrong, and what would you do?"（单次 `write` 在 `O_APPEND` 下对小记录基本是原子的，但行号的计算有竞态；要么加文件锁，要么不返回行号、读的时候再数）
- "The log is git-tracked. What does that buy you, and what doesn't it?"（谁在什么时候加了覆盖都在历史里，review 能看到；但能改文件的人也能改历史，签名防的是伪造和篡改内容，防不了删掉一整行，删行要靠 git 历史，或者第 13 章 30 课那种把链头存到别处的哈希链）
- "Why sign the canonical JSON and not the line itself?"（行的写法会随工具变：键顺序、空格、转义；签名要的是内容不变，写法可以不同）
- "The disk filled up and a line was cut in the middle of the Ü. What does your entries() do?"（先 `read_text` 整份解码再切行，会直接抛 UnicodeDecodeError，报不出是第几行；按字节切行、逐行解码才报得出。测试里截断的是 ASCII 行，两种写法都能过）

### Part 3 结论和唯一的报告（目标 14 分钟）

坑：
- `rule_findings` 还是课里的写法，所有失败的规则都当 block。第 33 课规定规则写入时就带 severity，gate 读的时候不能改。没有 severity、或者写的不是正好 `block`、`warn`、`info` 三个之一（`"Warn"`、`"critical"`）的，一律按 block。原样透传会把 `"Warn"` 写进报告、还让任务通过；先转小写会把 `"Warn"` 当成 warn，也是 fail open。
- 缺失的产物（None）是 block，不能当成空的；空的产物（`[]`、`{}`）存在而且干净。用 `not art.rule_report` 判断会把两者混在一起。缺失产物的 finding 占它那个来源的位置，不能统一放到最前面。
- 合同里一条验收命令都没有，是 `gate.no_acceptance`：什么都没证明的闸门只是摆设（skill 的拒绝规则）。
- strict 只把 warn 升成 block，info 不动。
- 覆盖在 strict 之后应用，strict 升出来的 block 可以用签名清掉。先覆盖再 strict 的话，覆盖时它还是 warn，不能覆盖，升级以后就成了清不掉的 block。overridden 不算 block，只剩 warn 也算通过。
- 覆盖率：`coverage_findings` 已经写好，边界写在它的 docstring 里，重写时最容易改坏。`delta > 0.01` 把 0.85→0.84 判成 block（浮点里是 0.010000000000000009）；`delta >= 0.01` 一样；`round(delta, 2)` 放过 0.85→0.839；`int(x * 100)` 截断放过 0.8599→0.849；`abs_tol=0.01` 宽到放过 1.1 个点；和 0 比较只能用 `abs_tol`，`rel_tol` 对 0 不起作用。
- 下限用传进来的值；不在 (0, 1] 里要报错，80 正是代码讲解里提到的单位错误，会让每个任务都低于下限。只写 `if coverage_floor > 1` 会放过 0，下限检查就悄悄关掉了；写成 `0 < floor < 1` 又会拒绝 1.0，要求百分之百覆盖的团队就用不了。
- 测试分不出的写法：合同里没有验收命令、feedback 也缺失时，先报 `gate.missing_artifact` 还是先报 `gate.no_acceptance`，结论都是 block。docstring 写的是先报 no_acceptance：补上 feedback 之后任务照样过不了，先说出这个更有用，可以问候选人为什么这样排。
- `write_report`：路径是 `outputs/verification/<task_id>.json`，不是课里代码写的 `verification_report_<id>.json`；内容是 `json.dumps(to_dict(), indent=2, sort_keys=True)` 加换行，不放时间戳；再写一次要替换，不能追加；task id 不是纯文件名就报错。用 `Path(task_id).name` 清洗不行，`../T-42` 会被写成 `T-42.json`，盖掉真正的报告。

追问：
- "What else must the report carry to be auditable?"（它读了哪些产物：路径和内容哈希，skill 里明确要求；以及 HEAD）
- "CI reads the report while the gate is rewriting it. What does CI see?"（可能读到半份文件；先写临时文件再 `os.replace`，参考实现就是这样做的）
- "Where would you make strict the default?"（发布分支、阻塞发布的 PR、事故后的排查，课里说按分支开启，日常分支全开会让团队绕开闸门）
- "A team wants the reviewer LLM's score in this verdict. What do you say?"（不行。闸门回答任务是否完成，必须确定；LLM 的打分放在第 39 课的 reviewer 一侧，混在一起信号会坍缩）

### Part 4 Markdown 摘要流（目标 10 分钟）

坑：
- 版式由 docstring 和测试里的完整样例决定：第一行是任务和 PASSED/FAILED，照报告里的 passed 写；第二行是 head，strict 时加 `, strict`；每个有 finding 的严重级别一节（空行、带个数的标题、空行、表格），顺序固定为 block、warn、info、overridden，节内保持报告顺序；overridden 的表多 by 和 reason 两列。按 finding 第一次出现的顺序排节、节内再排序、没有 finding 的级别也写一节，都会挂。只有 warn 和 info 的报告是 PASSED：warn 只给结论加批注，block 才挡住 `passed: true`，按“没有 finding 才算通过”来写会把它写成 FAILED。
- 第一份摘要在读第一条记录之前发出，那时两条验收命令都还没跑。把它放进循环里、等第一条记录到了再补发，测试数得出来：发出第一份时已经拉取了一条；流里一条记录都没有时，这样写什么都不发。
- 只有摘要变了才发。c3、c6 是无关的命令，c4 是重复的失败，都不发；c1 之后结论没翻转，还是 FAILED，但 lint 不再是 missing，finding 变了，要发。只在 PASSED 和 FAILED 之间翻转时才发，会漏掉这一次；只比每节的个数也会漏，c2 把 signup 从 missing 变成 failed，个数没变。忘了更新上一份、每份都和第一份比，又会多发。
- 分隔是空行、`---`、空行，只放在两份摘要之间，放在后一份的开头。通过的那份摘要最后一行是 `head 4be7a1c` 这段文字，紧跟一行 `---` 的话，Markdown 会把它读成 setext 二级标题。每次 yield 一份完整的摘要：分隔符单独 yield、放在每份后面、第一份前面也加，都不对。
- 和上一份摘要比，不是和发过的所有摘要比：c8 重跑 lint 通过，摘要回到 c5 之后那份 PASSED。用集合记下发过的摘要，这一份就不会再发，PR 评论最后停在 FAILED。比较 gate 返回的报告而不是摘要文本，这里结果一样：摘要不显示的只有 coverage，它不随反馈记录变化，这种写法可以接受。
- 写成普通的 `async def` 加 `return` 时，测试报的是 `'async for' requires an object with __aiter__`，要看出这里要的是 async generator。
- 记录一到就重算，摘要一变就发，不能先把流读完。闸门每条记录跑一次，拿到的是到目前为止的全部记录。
- 顺带检查转义：docstring 写明了顺序，先把反斜杠写成 `\\`，再给 `` ` * _ | `` 前面加反斜杠，别的字符不动。样例里的 `tests/test_signup.py`、`'|'`、`app/**/*.py`、`deploy\prod.ps1`、`` `#release` `` 只用来确认照做了。code、by、reason 列也要转义，`coverage.minor_regression` 的下划线就在 code 列里。

追问：
- "Which fields belong in the summary, and which only in the JSON?"（课后练习 3：摘要给人看，放结论、block、覆盖了谁签的为什么；完整的 detail、覆盖率数字、产物路径留在 JSON 里，摘要从 JSON 生成，两边不会说法不一）
- "The PR comment is edited in place. What changes?"（不再是追加的流，而是每次变化重写同一条评论；去重的道理一样）
- "A thousand records arrive in a burst. Re-running the whole gate per record is quadratic. How would you make it incremental?"（按命令维护最新一次运行的索引，每条记录只更新它那一条命令的结论）

### Part 5 堆叠提交（目标 12 分钟）

坑：
- 覆盖率比的是它所在的父提交，不是 main。b1 比 a1 低 0.5 个点只是 warn，和 main 比就是 2.5 个点，block。
- 父提交没有覆盖率报告时，用父提交自己比的那个数，一路往下直到 base_coverage：d1 比的是 b1 的 0.825。不能回到 main，也不能沿用 CI 自己算的 previous，CI 比的是任务运行时的 main（0.86）。
- 不改 CI 给的 artifacts，用 `replace` 和新的 dict。直接改 `coverage_report["previous"]` 会把调用方的数据改掉。
- 覆盖绑定 HEAD，a1 上签的豁免到不了 d1，d1 的回归照样 block。
- 等待有三种情况：没有 artifacts（f1）、artifacts 是旧提交的（h1 的 head_commit 是 h0，作者又推了一次）、父提交在等（g1）。等待的提交没有 verdict。
- blocked_by 是从栈底到它自己第一个没通过的提交。e1 自己通过了，但 d1 挡着；只看自己的结论，或者取离自己最近的那个失败，都不对。
- 输出顺序是父在前、深度优先、同一个父提交的子提交按给定顺序。按输入顺序、按层（BFS）、按 sha 排序都不对。
- 报错：父提交既不是 base 也不在栈里；连不到 base 的环；同一个 sha 给了两次。把未知的父提交当成 base，会把断掉的链悄悄接到 main 上。
- strict 和 coverage_floor 都要传给每个提交：下限改成 0.81 时，e1 的 0.80 就该挡住。

追问：
- "The bottom PR lands and main moves. What happens to the rest of the stack?"（b1 现在直接在 main 上，基准变成新 main 的覆盖率；它的 artifacts 是在 rebase 之前做的，head 变了，就是 waiting，等 CI 重跑）
- "Why can't an override on a1 cover the same finding on b1?"（b1 的代码不一样，人看的是 a1 的 diff；一条覆盖想罩住整个栈，就等于预先批准了还没写出来的代码）
- "A stack of 200 commits, gated on every push. What do you cache?"（每个提交的 verdict 按 sha 和 artifacts 的哈希缓存；只有改过的提交和它上面的提交需要重算）
- "What if overrides arrives as a generator?"（每个提交都要调一次 verify，生成器在第一个提交那里就读完了，后面的提交看不到任何覆盖；先 `list()` 一次。测试传的是列表，测不出来）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、打印实际值、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出命令 id、验收记录的新旧、HMAC 能证明什么、fail closed、报告的原子写入、栈的基准和重算 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
