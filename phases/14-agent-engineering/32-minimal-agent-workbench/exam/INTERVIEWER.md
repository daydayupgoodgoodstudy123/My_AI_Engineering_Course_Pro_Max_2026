# 面试官手册：Workbench（14/32）

候选人计时期间不要看。候选人手里只有 README、`workbench/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档和 RFC。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- Part 4 跑的是 Part 1 的回合。候选人跳过 Part 1 直接做 Part 4 时，提醒一句顺序。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 验收命令失败以后，任务是继续 in_progress 还是 blocked？ | "Blocked. The builder lets go of it, and a human reads the blockers." |
| 1 | 状态文件里的活动任务在看板上找不到怎么办？ | "Keep the lesson's behaviour: clear it, and the next turn picks new work." |
| 1 | 未知的键要不要做类型检查？ | "No. Keep them exactly as they were and write them back." |
| 1 | runner 抛异常怎么办？ | "Let it propagate. Nothing is written for that turn." |
| 1 | load_context要自动找所有规则文件吗？ | "No. Always load root AGENTS.md, then only the explicitly requested Markdown paths." |
| 1 | 同一路径重复请求或文件后来被人改了？ | "Keep first-request order and read fresh selected text on every call. The path helper already normalizes and deduplicates." |
| 2 | 某一行不是合法 JSON 怎么办？ | "Let the JSONDecodeError through. We don't repair files." |
| 2 | update 的 id 不在文件里，要不要追加？ | "No, that's a KeyError. Adding a task is a different operation." |
| 2 | 空行怎么处理？ | "Skip them when reading. When you rewrite one line, leave everything else where it is." |
| 3 | priority 是数字大的优先还是小的优先？ | "Higher runs first. A task without one counts as 0." |
| 3 | 两个任务互相依赖怎么办？ | "Neither is ever ready, so both show up in waiting. We don't look for cycles here." |
| 3 | 操作员可以提前确认吗？ | "No. confirm is the exact last_run the operator looked at." |
| 3 | 状态过期了，看板上也没有能开始的任务，返回 idle 还是 refuse？ | "Refuse. The age check comes first, whatever the board says." |
| 4 | 流开始时要不要先发一份完整的快照？ | "No. The watcher already has the files from before the stream started." |
| 4 | 能用 move、copy、test 吗？追加能写 "-" 吗？ | "Only add, replace and remove, and always the numeric index." |
| 4 | 已经没事可做了，能不能提前结束？ | "No. Run every turn you were asked for. An idle turn still sends []." |
| 5 | 一个任务能有两个 parent 吗？ | "No. parent is a single id." |
| 5 | epic 自己要不要验收命令？ | "Not for the roll-up. Its children decide its status." |

## 每关：要看什么、提示、追问

### Part 1 修回合循环（目标 12 分钟）

一个测试里叠了 4 个缺陷和 1 个计时问题：

1. `load_state` 照抄课里的 `AgentState(**raw)`。新版工具在状态文件里多写了 `last_run` 和 `lease` 两个键，第一个就让它报 `TypeError: ... unexpected keyword argument 'last_run'`，这正是课后测验 Q11 的情形。docstring 要求未知键放进 `extra`，由 `save_state` 原样写回。
2. 取任务只看 `todo`。测试模拟上一个会话写完看板就死了：T-006 在看板上是 `in_progress`，状态文件里却没有活动任务。starter 去领 T-007，看板上就有了两个 builder 任务在做。错误不在取任务的地方报出来，而是在 `take_turn -> save_board -> check_board` 里报 `ValueError: the builder has 2 tasks in progress: T-007, T-006`，`check_board` 本身没有错。
3. 完成定义：`all(exits.values())` 把退出码当成布尔值，0 是假。T-007 的命令全部退出 0，却走进 blocked 分支，blockers 为空，`state.blockers[0]` 报 IndexError。
4. 改成 `all(code == 0 ...)` 以后，没有验收命令的 T-008 因为 `all()` 对空序列返回 True 被标成 done。docstring 要求它 blocked，blocker 是 `T-008 has no acceptance command`；配套 skill 说没有 acceptance 的任务会变成橡皮图章。
5. 按需上下文：`load_context` 先rglob读取整个workspace的Markdown建catalog，最后才挑本回合requested。20个普通回合请求面对600份无关文档时，慢三次0.644/0.650/0.663秒，快1.282/1.192/1.315毫秒，限0.03秒，双侧至少21倍。正确做法直接读这次明确选中的文件；不建全catalog，也不跨回合缓存。正文强调短router只在相关时加载deeper docs。

护栏：
- 把未知键过滤掉也能消掉 TypeError，但 `last_run` 会从文件里消失，第一条断言就查这个。照测验 Q11 的参考答案把 `last_run` 加成 `AgentState` 的字段、再加进 `STATE_KEYS`，`last_run` 是保住了，`lease` 又报同样的 TypeError。
- 删掉 `check_board` 里“builder 最多一个 in_progress”的检查，报错是没了，可 T-007 照样被领走，第二条断言要的是接回 T-006。
- 接回进行中的任务时不看 owner，会把 reviewer 的 R-003 接过来；把 in_progress 和 todo 放在一起按看板顺序取，会先拿到排在前面的 T-007。
- 失败要按 `code != 0` 判断。T-006 的登录测试被信号杀掉，退出码是 -9；写成 `code > 0` 或 `code == 1`，它会被当成通过，T-006 变成 done。
- `check_board` 是起始正确的线性校验器；合并后的重复id仍要点名，8000条正常任务仍须快速通过，这些是给定实现的健康护栏。

上下文护栏：输出是AGENTS.md加本次显式请求、按首次请求顺序稳定去重；选中的文档被人修改后下一回合要看到新内容；未请求文档即使不是合法UTF-8也不能读。context_paths与read_document从起始给对，不另考路径安全或文本换行。

看什么：是否区分“只输出请求项”和“只读取请求项”；是不是从 `check_board` 的报错倒回去问“哪一回合把第二个任务设成了 in_progress，那之前看板是什么样”；是不是先打印 exits 看实际的退出码；每改一处就重跑。

提示：
- H1："Which turn put the second task in progress, and what did the board look like before it?"
- H2："What does all() return for [0]? And for an empty list?"
- H3：直接指出 `run_one_turn` 取任务只找 todo，或者指出 `all(exits.values())`。
- 上下文：H1 "Which files did this turn request, and which files did the loader read?" H2 "Does a router need a catalog of every document?"

追问：
- "take_turn writes the board before the state. What breaks if you swap them?"（换过来以后，崩溃会留下“状态说在做 T-006、看板上 T-006 还是 todo”，别的会话可能再领一次；现在的顺序留下的是看板上的 in_progress，下一回合接回。课后测验 Q14 讨论的就是两次写之间的一致性。）
- "Two builders share one board. What does the one-task-in-progress rule become?"（每个 builder 有自己的 owner id，领取时做 compare-and-set；并发写状态是第 34 课的内容。）
- "Why not cache selected document text across turns?"（repo里的规则会被人或工具改；短router减少读取范围，但每回合选中的文档仍要fresh。）
- "Why keep each command's exit code on the task instead of a passed flag?"（reviewer 和下一个会话能看到是哪条命令、退出码多少；反复失败的命令也有记录。）

### Part 2 JSON Lines 看板（目标 11 分钟）

坑：
- 一行一个任务，键的顺序由 `task_to_doc` 决定：课里的键在前，`extra` 在后。用 `dataclasses.asdict` 会多出一层 `"extra"`。
- 每一行以换行结束；`"\n".join(...)` 少了最后一个换行。
- 按 `"\n"` 切开后最后一项是空串，不跳过就报 `Expecting value`。手写的那行前面还有一个空行，改用 `splitlines()` 而不跳过空行，同样报这个错。
- `update` 只改那一行。整个文件重写一遍，手写的那行（紧凑格式、键顺序不同、没有 `checks`）和它前面的空行都会变。测试用 `difflib.unified_diff(..., n=0)` 比较，要求只有一块 `@@ -3 +3 @@`：删掉旧行、把新行追加到末尾，用 ndiff 看也是一删一加，但行的位置变了，看板顺序也跟着变了。
- 按任务在 `load()` 结果里的下标去改文件的第几行，会被空行错开：改 T-003 时改掉的是那个空行，手写的那行原样留着。
- 找行要解析 JSON 比较 `id`。用子串找会命中 R-001，它的 goal 和 depends_on 里都有 T-002；用 `'"id": "T-003"'` 这种规范写法去匹配，又找不到手写的 `"id":"T-003"`。
- 不能把看板缓存在内存里：测试在两次调用之间手工追加了一行。
- 先对替换后的整个看板跑 `check_board`，通过了再写；写完再检查，坏行已经落盘了。只检查传进来的那个任务也不够：T-003 已经在做，再把 T-002 改成 in_progress，单看 T-002 没问题，整个看板上 builder 就有两个任务在做。
- `load` 也要 `check_board`：合并冲突解决后留下两行 T-004，要报 ValueError。
- 不存在的 id 要报 KeyError，不能悄悄忽略。
- 测试不管 `ensure_ascii`：写成 `ensure_ascii=False`，中文会原样落盘，测试照样通过（规范行只断言了纯 ASCII 的 R-001）。docstring 说的是 json 的默认设置，看到了可以问一句为什么改。

追问：
- "Why does one task per line merge better than one JSON array?"（两个分支改不同任务时改的是不同的行，git 能自动合并；带缩进的数组在末尾加任务会改到上一行的逗号，两个分支同时追加就冲突。）
- "The process dies halfway through write_text. What is left on disk?"（半个文件；写临时文件再 `os.replace`，原子写是第 34 课的内容。）
- "Two tools rewrite the same line at once?"（后写的覆盖先写的；要么加锁，要么带版本号比较后再写。）

### Part 3 取任务（目标 11 分钟）

坑：
- 只取 owner 是 builder 的任务。课后测验 Q8 指出课里的取任务没有检查 owner，H-001 优先级 9 也不能拿。
- 只取 todo：T-002 优先级 7，但它是 blocked。
- 依赖要 done 才算满足，reviewer 正在做的 T-004 不算。
- 优先级相同按看板顺序。`>=` 或者 `sorted(...)[-1]` 会拿到后面的 T-006；测验 Q10 提到 `max` 返回第一个最大值。看板顺序也不是 id 顺序：T-010 排在 T-006 前面，按 `(-priority, id)` 排序，或者给堆加上 id 当平局键，也会拿到 T-006。
- 没有 priority 的任务按 0 算，直接 `extra["priority"]` 会在 T-007 上报 KeyError。
- 不在看板上的依赖整板检查。只检查最后挑中的那个任务，会放过 T-032。
- idle 时 `waiting` 只列还没 done 的依赖，T-022 已经 done，不列。也只列 builder 的 todo：H-020 同样在等 T-021，先算依赖、后看 owner，就会把它也列进去。
- 先看时间再看看板：过期的状态在看板上没事可做时也要 refuse。只在要开始任务时才拦，等待中的看板会返回 idle。
- 24 小时边界：正好 24 小时不算过期，多 1 秒才算。`>=` 和 `.days >= 1` 都会在边界上错。
- 时区：`fromisoformat` 读出 `+02:00` 后直接和 `now` 相减就会换算。`.replace(tzinfo=timezone.utc)` 是改标签不是换算，10:30+02:00 会被当成 10:30 UTC，年龄从 24.5 小时变成 22.5 小时。
- 没有偏移量的时间戳报 ValueError。不处理的话，它和带时区的 `now` 相减会报 TypeError；把它当成 UTC 也不对。
- 确认只对它点名的那个 `last_run` 有效。只要 `confirm` 不是 None 就放行，旧的确认会放过以后每一次过期。
- 从没运行过（没有 `last_run`）不算过期，测验 Q11 也这么说。

追问：
- "Why tie the confirmation to last_run instead of a --yes flag?"（一个开关很容易被写进脚本，以后每次过期都被放行；绑定 last_run 后，确认只对操作员看过的那个状态有效，运行结束写入新的 last_run，确认自然失效。）
- "Where does now come from in production, and what if the clock is wrong?"（注入时钟便于测试；生产用 UTC 和校时；last_run 在未来的情况要单独决定怎么处理。）
- "The board says T-003 waits for T-004, and T-004 never finishes. Who notices?"（waiting 会一直列着它；可以在 idle 超过一定回合数时提醒 human。）

### Part 4 回合 JSON Patch（目标 14 分钟）

坑：
- 输出格式由测试决定：每个补丁是一行 `json.dumps(patch)` 加 `"\n"`。用 `indent` 会让一个补丁占很多行，少了换行也不行。
- JSON Pointer 转义：先把 `~` 换成 `~0`，再把 `/` 换成 `~1`。验收命令做了 `checks` 的键，里面有 `tests/test_login.py` 和 `HEAD~1`。顺序反了，`/` 先变成 `~1`，接着又被换成 `~01`；完全不转义，路径就被切成了别的层级。
- null 是一个值：`active_task_id` 从 `"T-006"` 变成 null 是 replace，不是 remove。
- 列表从后往前删：先删 `/1` 再删 `/0`。从前往后删，第二个下标就不存在了。
- 不能整个列表或整个文档 replace：测试要求每个变了的值一个操作。
- 差分要对着 watcher 手里的版本，也就是上一行发出去之后的文档。每回合开始时重新读文件当 before，就丢了回合之间人改的内容：测试在第 4 行之后把 T-006 改回 todo，还加了 H-003。
- 回合一结束就 yield。先跑完 15 回合再一起发，第一行到达时文件已经是最后的样子。
- 什么都没变的回合也要发 `"[]\n"`，watcher 收到的行数才和回合数对得上。也不能因为没事可做就提前结束：最后两个回合都要发 `[]`。

追问：
- "Why not send both files after every turn?"（看板大了以后每回合几百 KB，补丁只有几十字节；但 watcher 断线重连时需要一份快照，再接着收补丁。）
- "The watcher misses line 7. How does it find out, and how does it recover?"（每行带序号或文档版本；发现跳号就重新要快照；也可以在补丁前面加 RFC 6902 的 test 操作做前置检查。）
- "A person inserts a task at the top of the board. What does the positional list diff send?"（之后每个位置都会变成一串 replace，补丁很大但仍然正确；按 id 对齐要用 move，或者把看板按 id 存成对象。）

### Part 5 Epic 汇总（目标 12 分钟）

坑：
- 子节点要用汇总后的状态：E-1 下面的 S-11 在看板上写的是 todo，汇总后是 blocked。
- 判断顺序：全部 done 为 done；否则有 blocked 为 blocked；否则有 in_progress 或 done 为 in_progress；否则 todo。先判 in_progress，S-11（done、blocked、todo 各一个）会变成 in_progress；只认 in_progress，E-4（一个 done、一个 todo）会变成 todo。
- `conflicts` 按看板顺序，不是后序遍历算完的顺序，否则 S-11 会排到 E-1 前面。
- `next_leaf` 是深度优先、每一层按优先级排：E-1 在根这一层优先级最高，所以它下面优先级 0 的 T-113 先于根上优先级 4 的 T-9。全板取最大会拿到 T-9，兄弟按看板顺序也会先看 T-9。同一层优先级相同时按看板顺序：S-11 下面的 T-113 排在 T-110 前面。改成显式栈时按优先级升序压栈，平局会倒过来先弹出 T-110；按 id 打破平局也会拿到 T-110。
- blocked 的 epic 里还可以有活：跳过 blocked 分支会拿到 T-23。
- 只返回叶子：先判断节点本身是不是 builder 的 todo，会把 epic S-11 返回出去。
- parent 不在看板上报 ValueError，报错里要有这个任务。parent 成环（T-71 和 T-72 互为 parent）也要报，报错里要有环上的任务：从根往下走时环上的任务根本访问不到，不检查就悄悄漏掉；从每个任务往上找根，则会无限递归。

追问：
- "Someone blocked E-2 on purpose, but its children are all todo. What should the roll-up say?"（这里只相信叶子，所以会报 conflict；要允许手动阻塞，就把原因表达成一个 blocked 的子任务，或者单独加一个字段。）
- "Part 3's depends_on and this parent: one graph or two?"（两种边：depends_on 决定能不能开始，parent 决定汇总；环检测要分别做。）
- "The board has 50,000 tasks. What changes?"（children 索引一遍建好，O(n)；递归改成显式栈，避开 Python 的递归深度限制，压栈时按优先级倒着压，平局才保持看板顺序。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出崩溃一致性、并发、原子写、时钟、断线恢复 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
