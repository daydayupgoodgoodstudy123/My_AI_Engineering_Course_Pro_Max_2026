# 面试官手册：RuleCheck（14/33）

候选人计时期间不要看。候选人手里只有 README、`rulecheck/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 规则没有 check 字段怎么办？ | "parse_rules already raises BrokenRule for that. Keep it." |
| 1 | 两行描述用换行还是空格连接？ | "A space. Markdown reads the lines of one paragraph as one line." |
| 1 | check 指向的方法不存在，记失败还是报错？ | "Raise BrokenRule, before any check runs. A pointer that doesn't resolve means the rule file is broken, not the agent." |
| 1 | 报告里的依赖名要不要也规范化？ | "No. Compare normalized names, report them the way the agent wrote them." |
| 1 | 依赖名会带版本号吗，比如 requests>=2？ | "Not in these turns. An install carries a bare package name." |
| 1 | TurnTrace 构造之后事件还会变吗？ | "No. It's frozen and holds a tuple." |
| 2 | 同一类别里的规则要不要排序？ | "No. Keep the order you're given. Newest first is the caller's job." |
| 2 | severity 是默认的 block 也要写出来吗？ | "Yes. Severity is tagged at write time, the default too." |
| 2 | 描述里有换行怎么办？ | "ValueError. A description is one line." |
| 2 | 描述中间连着的两个空格要保留吗？ | "Yes. A description reads back exactly as it was written." |
| 2 | add_rule 能不能解析整个文件，再整体重写？ | "No. People edit this file by hand. Change nothing but the new block." |
| 2 | 类别里还没有规则，新规则放哪？ | "Where that category would start: before the first rule of a later category, or at the end." |
| 2 | remove_rule 遇到不存在的 slug？ | "KeyError." |
| 3 | 读状态文件本身算不算 tool call？ | "It is a tool call, but the startup rule watches it, so it doesn't start work." |
| 3 | decide 和 approve 算 tool call 吗？ | "No. Only read, write, run, install and ask." |
| 3 | 有两条 startup 规则，读第二条要的文件算不算开始干活？ | "No. Work starts at the first tool call that no startup rule watches." |
| 3 | 装依赖有 approval 规则在看，还算开始干活吗？ | "Yes. Only what a startup rule watches holds work back." |
| 3 | 置信度正好等于阈值？ | "0.7 is not below 0.7. No note needed." |
| 3 | 一个问题记录能管两个没把握的决定吗？ | "No. Each unsure decision needs its own note, after the previous decision." |
| 3 | 批准在安装之后才来？ | "Too late. The approval has to come first." |
| 3 | 测试通过之后又装了依赖？ | "Then the proof is stale. Any write or install after the last acceptance run." |
| 3 | 整个回合都没跑验收命令？ | "Failed, with at=None. There's no event to point at." |
| 4 | 事件编号算不算被拒绝的事件？ | "Yes. It's the position in the stream the runtime received." |
| 4 | warn 级的规则也要拒绝事件吗？ | "No. Only block rules refuse. warn and info are reported." |
| 4 | 同一条规则被违反两次？ | "One line per rule. A block rule keeps refusing, without a second line." |
| 4 | 被拒绝的 tool call 算开始干活了吗？ | "No. A refused event never happened, so the runtime keeps refusing until the state file is read." |
| 4 | 一个事件同时违反两条规则？ | "Two lines, in rule order." |
| 4 | 计划行放哪？ | "Last, after the stream ends." |
| 5 | 锚点用 GitHub 的标题 slug 吗？ | "No. Our links put the rule's slug itself after the #." |
| 5 | 锚点不对的链接还算把 agent 带到了文件吗？ | "Yes. The agent can open the file. The link is still broken." |
| 5 | 只有 `#锚点` 的链接也要检查吗？ | "Yes. It points into its own file, and in a rule file the anchor has to be one of its rules." |
| 5 | 规则文件只在 docs/ 里找吗？ | "No. Anywhere under the repo root." |
| 5 | 行内代码里的链接算不算？ | "No. Inline code shows a link, it isn't one." |
| 5 | topic doc 能从别的文档走到，算不算 router 链接了它？ | "No. The router links every topic doc itself." |
| 5 | docs/ 子目录里的文档算 topic doc 吗？ | "No. Only files directly in docs/." |
| 5 | router 正好 50 行？ | "Over budget. Under 50 means 49 at most." |
| 5 | 围起来的代码块（```）里的链接要处理吗？ | "Our routers don't put links in fenced blocks. You don't need to handle them." |
| 5 | 链到仓库外面、文件确实存在？ | "Broken. The agent works inside the repo." |
| 5 | router 走不到的文件里有断链，要报吗？ | "No. Report what the walk from the router meets. That file already shows up as unreachable." |

## 每关：要看什么、提示、追问

### Part 1 修规则报告（目标 12 分钟）

一个测试里叠了 5 个缺陷和几道护栏：

1. `parse_rules` 用 `re.split(r"\n## ", text)[1:]` 切规则，靠的是"`## ` 前面有换行"，再把第一段当成序言丢掉。测试里的规则文件没有 `# Agent Rules` 标题，第一行就是 `## startup/state-file-fresh`，于是第一条规则被静默丢掉（测验 Q9(a)）。报错不在解析器里：`score` 照常返回，测试调 `report.verdict("startup/state-file-fresh")` 时在 `Report.verdict` 里报 `KeyError`，根因在两层调用之上。
2. 描述：每读到一行描述就覆盖一次 `description`，两行的描述只剩最后一行（测验 Q9(d)）。测试里 forbidden 规则的描述写在字段前面、分两行，uncertainty 规则的第二行是转义过的 `\- do not guess.`。修法是把描述行收集起来用空格连接，转义的处理原样保留。
3. `score` 照抄课里的 `getattr(checker, rule.check, None)`，方法不存在就记 `passed: False`（测验 Q4）。docstring 要求在任何检查运行之前报 `BrokenRule`，消息里要有规则名和 check 名。测试用一个会记录调用的检查器子类确认"之前"两个字。
4. `normalize` 的正则是 `[-_]+`，漏了 `.`。docstring 写的是 PEP 503：小写，`-`、`_`、`.` 连续出现的一段换成一个 `-`；docstring 自己举的 `zope.interface` 和 `zope__interface` 在这个正则下就对不上。好的那个回合里没有带点的名字，报告全对，挂在 `mixed` 那条：`zope__interface` 和 `ruamel.yaml` 被当成没批准。
5. `TurnTrace` 的几个摘要字段是普通的 `@property`，每读一次就把整个事件列表扫一遍。一年的规则（2,000 条）乘上 5 万个事件，`score` 要 1 到 2 秒（看 Python 版本），限值 0.1 秒。`TurnTrace` 是 frozen 的、事件是 tuple，所以换成 `functools.cached_property` 是安全的；在 `score` 里先算一次摘要也行。
6. 护栏，每种常见的改坏写法都有一条断言接着：
   - 为了好比较，把报告里的依赖名也规范化了：`unapproved_dependencies` 要返回 agent 写的原样名字，`Requests` 不能变成 `requests`。
   - 重写 `normalize` 时的捷径各漏一种情况。只把 `_` 换成 `-`：`zope__interface` 对不上 `zope.interface`，`ruamel.yaml` 对不上 `RUAMEL_YAML`。逐个字符替换不合并连续段：`zope__interface` 变成 `zope--interface`。把分隔符全删掉：`pythondateutil` 被当成 `python-dateutil` 的批准，这是另一个包。不转小写：`FastAPI` 对不上 `fastapi`。
   - `BrokenRule` 在循环走到那条规则时才抛：前面的检查已经跑过了，测试的记录器会看到调用。
   - 为了提速把摘要缓存在 `RuleChecker` 实例上：同一个检查器先评好回合、再评坏回合，第二次拿到的是第一次的数据。
   - 改写摘要字段时把语义改了：`tests_exit_code` 要取最后一次验收运行，`confidence` 要取最低的那次决定（坏回合里先 0.4 后 0.9）。

看什么：第一个失败是 `KeyError`，候选人是去 `Report.verdict` 里找，还是先打印 `parse_rules` 的结果；是否注意到 `#` 标题和 `##` 规则的差别；每改一处就重跑；计时失败时是靠猜还是先测（`cProfile` 或者在属性里计数）。

提示：
- H1："How many rules did parse_rules return?"
- H2："What does re.split leave in its first piece when the text starts with '## '?"
- H3：直接指出对应的那一处（`re.split` 那一行、覆盖 `description` 的两行、`score` 里的 `getattr`、`normalize` 的字符类、`TurnTrace` 的 `@property`）。

追问：
- "Why raise on a check that doesn't resolve instead of failing the rule?"（失败会让报告怪到 agent 头上，而真正坏的是规则文件。更好的做法是规则集加载时就校验所有 check，在 CI 里跑。）
- "Your cache sits on a frozen TurnTrace. The runtime appends events to a live trace. Now what?"（追加时让缓存失效，或者按事件增量维护摘要；不能再用一次性的 cached_property。）
- "Should normalize strip version specifiers and extras, like requests[socks]>=2?"（不该在 normalize 里做。先用 `packaging.requirements.Requirement` 解析出名字，PEP 503 只管名字。）
- "The lesson keeps agent-rules.md as the source and agent-rules.lock.json as a cache. Where does that fit here?"（pre-commit hook 解析一次写出 lock，热路径只读 lock；lock 里存源文件的哈希，对不上就重新生成。）
- 测试没有覆盖、但可以聊的：check 名以下划线开头时参考答案也报 `BrokenRule`；在属性上加 `@functools.cache` 会让每次读取都对 5 万个事件的 tuple 求一遍哈希，比原来还慢，而且缓存会把每个回合永远留在内存里；把摘要按 `id(trace)` 存进模块级的字典也能过测试，但回合对象回收以后 id 会被新对象复用，读到的是别的回合的摘要。

### Part 2 规则文件（目标 12 分钟）

坑：
- 版式由 `SEED_FILE` 定死：标题行、每块前一个空行、四行字段、一行描述、文件以换行结尾。severity 即使是默认的 block 也要写出来（课里说 severity 在写规则时就定下来）。没有描述的规则没有描述行，写一个空行会让下一块前面多出一个空行。
- 按 `CATEGORIES` 的顺序分组，组内保持传入的顺序。按 slug 排序会把 `startup/tool-versions` 排到 `startup/state-file-fresh` 后面；按类别名的字母序排，approval 会排到最前。
- 转义只给 `parse_rules` 读回来会变样的描述行：以 `## ` 开头（会变成新规则）、整行匹配 `FIELD`（会改掉规则自己的字段）、以反斜杠开头（解析器会吃掉一个）。不转义的话，`## approval/always-ok` 会让解析器报"approval/always-ok 没有 category"，`- check: always_ok` 会报 check 设了两次。转义多了也不对：`#1 cause of rework...` 不是标题，`- check: run the linter before you push.` 整行不匹配 `FIELD`（值里有空格），这两行原样写。用 `FIELD.match` 代替 `fullmatch` 就会多转义后一行。字段行要直接拿 `FIELD` 判断：`-check:always_ok` 没有空格，也整行匹配 `FIELD`，另写一个只认 `- name: value` 的正则会漏转义它，读回来 check 设了两次。`##__VA_ARGS__ ...` 的 `##` 后面没有空格，不是标题，原样写；按 `startswith("##")` 判断会多转义。
- 写不出来的规则报 `ValueError`：描述含换行。注意 `str.splitlines` 认的换行不只 `\n`，`\u2028` 和换页符 `\x0c` 也会把一行拆成两行，解析回来就变了；只查 `"\n"`，或者把 `\n`、`\r`、`\u2028` 一个个列出来，都会漏。直接用 `splitlines()` 判断，和解析器一致。首尾有空白（包括制表符）的描述读回来会被 strip。slug 为空或含空白、类别或严重度不认识、check 不是标识符、两条规则同名，都报 `ValueError`。
- 描述中间的空白原样读回：`Keep the macros portable.` 前面是两个空格。Part 1 修描述时如果顺手把空白压成一个（`" ".join(text.split())`），会挂在往返那条上。
- 没有规则的文件只有标题一行，`write_rules([])` 是 `"# Agent Rules\n"`。`add_rule` 和 `write_rules` 拒绝同样写不出来的规则。
- `add_rule` 只插入一块，别的一个字节都不动。测试里的手写文件有一段说明、两行的描述、写在字段前面的描述、没写 severity 的规则、两个连续空行，解析再整体重写会把这些全改掉。插入位置是这个类别第一条规则的标题前，块后面跟一个空行；类别还没有规则时，放在后面类别的第一条规则前，或者文件末尾。手写文件里 done 和 approval 之间有两个空行，新块插在 approval 标题前，或者插在 done 的正文后面、把两个空行留在新块之后，diff 都只多一块，两种都可以。插入的块要和 `write_rules` 写的一样，描述照样转义：自己拼块、忘了转义的话，把 `## approval/always-ok` 那条规则加进 `SEED_FILE` 就对不上。判断"已经有这个 slug"要按整条规则比：`done/tests` 是 `done/tests-pass` 的前缀，用 `"## " + slug in text` 会误报。
- `remove_rule` 删掉从标题到下一条规则之前的所有行，包括中间的空行；删最后一条时，把它前面的空行一起删掉，文件仍然以一个换行结尾。手写文件里 `done/tests-pass-fast` 在 `done/tests-pass` 前面，用 `str.find("## done/tests-pass")` 会删错那一条。

追问：
- "Two people each add a rule to the top of the same category in two branches. What happens at merge time?"（两边插在同一个位置，git 报冲突。这比悄悄交错要好：审查的人会看到两条新规则。）
- "Why are rules headings and not a YAML list?"（改名就是一行标题的 diff；一条规则一个块，增删都是连续的一块；Markdown 本身就是给人读的文档。）
- "Should remove_rule leave a comment saying the rule was removed?"（不该。课里说过期规则直接删，不注释掉；为什么删的记录在 git 历史和 PR 里。）
- "How does a rename look in your format?"（只改标题那一行。所以 slug 不能藏在描述或字段里。）
- 测试没有覆盖、但可以聊的：文件最后一行没有换行时，往末尾加规则会改到那一行；CRLF 的文件；规则文件超过 200 行时按类别拆成 `agent-rules.<类别>.md`，由一个索引文件串起来（Part 5 的仓库就是这样）。

### Part 3 按事件判定（目标 12 分钟）

先讲清楚分工：`Watch` 上的方法只说"这条规则关心哪些事件"，时间上的要求全由类别决定。候选人要实现的是五种类别的读法，不是五个检查函数。测试里的 `RepoWatch` 加了两个自己的 check，硬编码五个 check 名字的写法过不了。

坑：
- startup：开始干活的位置是"第一个没有任何 startup 规则关心的 tool call"，不是每条规则各算各的。主回合先读 `docs/agent-rules.md` 再读 `agent_state.json`，两条 startup 规则都关心各自的文件，干活从第 3 个事件读 `app.py` 开始，两条都通过。每条规则各算各的，`state-file-fresh` 会在第 1 个事件就失败。只有种子规则时，读 `docs/agent-rules.md` 就算开始干活，所以同一个回合里 `state-file-fresh` 在第 1 个事件失败。decide 和 approve 不是 tool call；写问题记录（ask）是。别的类别关心的 tool call 也算开始干活：先装依赖再读状态文件，装依赖虽然有 approval 规则在看，`state-file-fresh` 照样在第 0 个事件失败；拿"没有任何规则关心的第一个 tool call"当开工点，过不了这一条。一个 tool call 都没有的回合永远没开始干活，startup 规则全部通过。
- forbidden：在第一个它关心的事件处失败，不是最后一个。
- definition_of_done：最后一次验收运行才是证明。第一次失败、最后一次通过算通过；先过后挂算失败，位置是最后那次运行。只认验收命令，`ruff check .` 挂了不影响。证明之后又有 write 或 install，证明就过期了，失败位置是第一次改动，不是那次运行，也不是最后一次改动。问题记录、决定、批准和读文件都不是改动：把"不是 read、ask、decide、run 的事件"都当改动，证明之后的一个 approve 就会让它过期。没有任何验收运行：失败，`at=None`。
- uncertainty：低于阈值才需要问题记录，0.7 不低于 0.7。记录必须在上一个决定之后、这个决定之前，中间隔几个事件都可以；一个记录只管一个决定，上一个决定不管有没有把握都会用掉它。只在没把握的决定上清掉标记，`[ask, decide 0.9, decide 0.3]` 就会被放过。阈值是参数，写死 0.7 过不了 `threshold=0.5` 那条。
- approval：批准必须在安装之前，按 Part 1 的 `normalize` 比较名字：`Python_DateUtil` 的安装由 `python-dateutil` 的批准覆盖，只做 `lower()` 过不了。从整个回合收集批准，`uvicorn` 在安装之后才批准也会被放过；只记最后一个批准，`httpx` 的批准会被 `Requests` 的批准顶掉；有任何批准就放行所有安装也不对。
- check 解析不到、类别不认识，都在判定之前报 `BrokenRule`。

追问：
- "Part 1's checker and your judge disagree on the same turn. Which one do you trust?"（judge。摘要丢了顺序，`read_state_file` 说不出读状态文件是在第一个 tool call 之前还是之后。）
- "Why do categories decide the timing instead of each check?"（加一条规则只要加一个谓词；五种时间形状固定下来，就是规则集对外的契约。一条规则放不进五类，通常该拆成两条。）
- "Could a check ask an LLM whether a decision was a guess?"（不行。检查要确定、便宜，每个回合都跑；课里的 skill 把"需要调用 LLM 的检查"列为硬性拒绝。）
- "Does severity change the verdict?"（不改变判定，只改变运行时怎么处理，这是 Part 4 的事。）
- 测试没有覆盖、但可以聊的：用 PEP 503 去比较 prod write 这类路径会把 `prod.yaml` 和 `prod-yaml` 当成一个；没带 confidence 的 decide 事件参考答案直接报 TypeError。

### Part 4 运行时拦截（目标 12 分钟）

坑：
- 违反 block 规则的事件被拒绝，不进 `record`，之后的判定当它没发生过。主流里第 9 个事件（再写 release.sh）被拒绝，所以第 8 个事件的测试证明不过期，done 是 ok；把被拒的事件也记进去，done 会在第 9 个事件失败。违反 warn 规则的事件照样放行：第 4 个事件那个决定没有问题记录，报 not ok，但留在 record 里。
- 被拒绝的 tool call 不算开始干活，被拒的验收运行也不算证明。第二条流里 agent 先跑了一次验收命令，又连写两次 `notes.md`，三次都被拒，读了状态文件之后才放行，done 报 `# end of turn`。如果第一次被拒时就把"已开始干活"设上，后面的写就会被放过；把被拒的那次运行记成证明，done 会变成 `# event 4`。
- 一条规则只出一行。第二次违反同一条 block 规则照样拒绝，但不再输出。编号按输出的先后，不是规则在列表里的位置；事件序号按收到的顺序，被拒的也算，不是在 record 里的位置（主流里那个决定在 record 里是第 3 个，行里要写 event 4）。同一个事件出的几行按规则在列表里的顺序，不按类别：测试里有一组规则把 forbidden 放在 startup 前面，写 release.sh 时 forbidden 那行先出。
- 每到一个事件就判，判完立刻输出。测试记下每行出来时已经拉取了几个事件：主流里是 `[2, 2, 5, 6, 11, 11]`。先把事件全读完再判，结果一样但这一条挂。
- startup 规则在它关心的事件被放行时（还没开始干活）立刻报 ok，不要等到流结束。第三条流里 ok 是第一个事件之后就出来的。
- 流结束时，还没出过行的规则按规则顺序补上；definition_of_done 只能在这时判，写 `# event <i>`（不写 refused）或者 `# end of turn`。最后是计划行 `1..N`，每行都以换行结尾。
- 过期的证明报第一次改动：第三条流在通过的运行之后先写 `poetry.lock`（warn 规则，放行），再写 `app.py`，done 写 event 2。每次改动都把记下的位置覆盖一遍，会写成 event 3。
- 新的通过的证明会替换过期的或失败的证明：`[读状态, 跑测试失败, 改代码, 跑测试通过]` 是 ok。
- 流结束时报的行也按收到的顺序编号：`[读状态, 写 release.sh（被拒）, 跑测试失败]` 里 done 写 event 2，按 record 的位置算会写成 event 1。
- 批准照样用 `normalize` 比较：主流里批准的是 `fastapi`，被拒之后重试的安装写的是 `FastAPI`，要放行；按原样比较会把重试也拒掉，record 就对不上。
- 阈值是 `Runtime` 的参数，和 Part 3 一样：写死 0.7 的话，`threshold=0.5` 时 0.6 的决定也会被报成没把握。
- check 解析不到时，构造 `Runtime` 就要报 `BrokenRule`，不要等到回合开始。
- `run` 要写成 async generator。starter 里的 `async def run` 只有 `raise`，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要看出来缺的是 `yield`。

追问：
- "The runtime refused a write. What should the agent see, and what should it do next?"（拒绝的消息里引用那条规则；agent 照规则去做，比如先读状态文件、先去要批准。课里说 Claude Code、Codex、Cursor 拒绝动作时会引用规则。）
- "Where does this sit next to Agents SDK guardrails and LangGraph interrupts?"（block 规则相当于触发 tripwire 的护栏；approval 更像 interrupt：停下来问人，批准后接着跑。规则集是两边共同的契约。）
- "Why one TAP line per rule, not per violation?"（TAP 的测试点就是规则，CI 按失败的规则数判；每次违反的细节写日志。）
- "Someone needs to override a block rule for a release. How?"（第 38 课：签名后写进 `overrides.jsonl` 审计日志，不能悄悄放过。）
- 测试没有覆盖、但可以聊的：被拒的 ask 不算问题记录；一个事件同时违反 warn 和 block 规则时，warn 那一行不写 refused，但事件照样被拒。

### Part 5 router 可达性（目标 12 分钟）

坑：
- 指向规则文件的锚点必须是那个文件里某条规则的 slug。规则文件按类别拆开以后，router 里的 `docs/agent-rules.md#startup/state-file-fresh` 指向的索引里已经没有这条规则了，这是断链，也是 startup 违规。`deploy.md` 里的 `#approval/prod-writes` 多了一个 s，也是断链，但不在 router 里，不算 startup 违规。topic doc 的锚点不检查：`deploy.md#approvals` 没问题。
- 只有 `#锚点` 的链接指向本文件，锚点照样要查：startup 规则文件里的 `[state file](#startup/state-file-read)` 指向一条已经改名的规则，是断链，跳过这种链接就漏了它。approval 规则文件里的 `#approval/new-dependency` 是好的；把空路径当成路径去解析，它也会被报成断链。
- 锚点断了，路径还在，agent 照样能打开文件：approval 规则只有 `deploy.md` 那条断了锚点的链接能到，它们是 3 跳（太深），不是不可达。
- topic doc 是 `docs/` 下直接的 `.md` 文件，规则文件除外，必须由 router 直接链接：`docs/deploy.md` 只在正文里提了一句，`docs/architecture.md` 的链接拼错成了 `architecure.md`，两个都算没链接，虽然都能从别的文档走到。`docs/adr/` 下的不是 topic doc。
- 不可达的规则要在整个仓库里找规则文件：`legacy/agent-rules.old.md` 在 `docs/` 外面，没有任何链接指向，它的规则不可达。只在 `docs/` 里找，不管找一层还是递归，都会漏掉它。
- 跳数是按广度优先算的最少链接数。仓库里 router 先链 `testing.md`，`testing.md` 又链 `agent-rules.done.md`；深度优先、先到先得的话，done 规则会是 2 跳，forbidden 规则也会是 2 跳（先从索引走到），uncertainty 会是 3 跳。正确答案是 1、1、2。
- 链接相对于它所在的文件解析：索引里的 `agent-rules.startup.md` 在 `docs/` 下，`../AGENTS.md` 回到 router。相对仓库根解析，索引里的链接全断。
- 先在 `#` 处切开再规范化路径。规则的 slug 里有 `/`，不切开的话 `agent-rules.forbidden.md#forbidden/no-release-script-edits` 会被当成一个不存在的文件。
- 行内代码不是链接：router 里的 `` `[slug](docs/agent-rules.md#<slug>)` `` 是写法示例。`https:` 链接跳过，不算断链。链到仓库外面的文件，就算文件存在也算断链（测试在仓库外放了一个 `shared/glossary.md`）。
- 断链报原样的写法（`fixtures.md`），不是解析后的路径。只报 router 走得到的文件里的断链：旧规则文件里那条指向 runbook 的链接也断了，但没人走得到那个文件，它已经出现在不可达里。
- 行数用 `splitlines()`：最后的换行不算新的一行。`split("\n")` 会多数一行，数 `\n` 的个数在没有结尾换行时会少数一行。50 行算超预算，49 行不算。
- 规则文件用 Part 1 的 `parse_rules` 读。拆开后的规则文件第一行就是 `## `，Part 1 的第一个缺陷没修的话，每个文件的第一条规则都会丢。

追问：
- "How do you keep the router under 50 lines as the rule set grows?"（router 只放指针；规则按类别拆在索引后面；每个 PR 都重读 router，这是课里的 freshness test。）
- "A rule gets renamed and the router's anchor breaks. How do you stop that from merging?"（在 CI 里跑这个检查，router 的断链当成 startup 违规，直接让构建失败。）
- "Why count hops to the file and not to the anchor?"（agent 打开的是文件，锚点只是文件里的位置。）
- "Should a rule three hops away fail the build?"（可以先当 warn：router 断链是 block，深度超了提醒拆分或者补一条直达链接。）
- 测试没有覆盖、但可以聊的：围起来的代码块里的链接、指向目录的链接、图片链接、带标题的链接 `[x](y "title")`、大小写不同的锚点。

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、打印中间结果、一次只改一处、用 `-x -k`、计时失败先测再改 |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出加载时校验、缓存失效、合并冲突、拒绝后 agent 该看到什么、CI 里跑 router 检查 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
