# 面试官手册：EvalGate（14/30）

候选人计时期间不要看。候选人手里只有 README、`evalgate/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | refine=False 的用例第一轮就通过了呢？ | "Then it passes in one round. refine=False only caps the rounds at one." |
| 1 | 一个用例的运行次数还不到 window 次，怎么判 flaky？ | "Use the runs it has. One pass and one fail are already flaky." |
| 2 | 同一个提交 CI 重跑了一次？ | "The new run replaces the old snapshot. Nothing is merged." |
| 2 | 可以用短 sha 或分支名吗？ | "No. Full 40-character lowercase shas only. Anything else is a ValueError." |
| 2 | 主干历史里有的提交没有结果？ | "Skip them. CI doesn't run on docs-only commits." |
| 2 | last-known-good 是不是指最近一次全部通过的运行？ | "No. It's main's newest commit with results, failures included. An older green run would blame this pull request for failures main already has." |
| 2 | 快照文件里的 JSON 结构有要求吗？ | "Your call, as long as it's one JSON file per commit and it reads back exactly." |
| 3 | 主干上还没有任何快照？ | "Block. We don't merge blind. Someone runs the suite on main first." |
| 3 | 新加的用例失败了，要不要拦？ | "No. Report it as new. People add a failing case for a known bug before they fix it." |
| 3 | 回归比例正好等于上限，算不算超？ | "The lesson says no regression greater than the limit, so exactly at the limit passes. That's also why a 0% layer with no regressions merges." |
| 3 | 一个用例在两个快照里的类别不同？ | "Judge it under its category in this commit. The tests don't cover it." |
| 4 | 某一层一个用例都没有？ | "Then it gets no group." |
| 4 | 结果流在所有用例结束前断了？ | "The run is broken. Raise a ValueError naming the missing cases." |
| 4 | 组按什么顺序输出？ | "Always benchmark, custom, online, so two runs' logs diff cleanly." |
| 5 | 派生规则自己有通过的用例，父规则没有？ | "Still uncovered. Show the chain down to the parent no passing case backs." |
| 5 | 用例声明覆盖了一个不存在的护栏？ | "That's a typo in the case. Raise a ValueError." |

## 每关：要看什么、提示、追问

### Part 1 修评测框架（目标 10 分钟）

一个测试里叠了 4 个缺陷和几道护栏：

1. `evaluator_optimizer` 不看 `refine`，guardrail 用例也拿到 3 轮。错误不在它自己里面报，而是在下一层：`Replay` 只录了一轮，被要第二轮时报 `LookupError: session 'sess-0412' recorded 1 turn(s); the eval asked for turn 2`。
2. `evaluator_optimizer` 把被拒绝的 `candidate` 当作下一轮反馈，proposer 收不到 judge 的失败原因。依赖“missing sticks”或“citations”的用例一直重复错误输出。下一轮必须收到紧接着那次失败的 reason，保留空白和 Unicode；不能一直沿用第一条诊断。
3. 失败分支照抄课里的代码返回 `case.max_rounds`，只跑了一轮的用例也报 3 轮。
4. `FlakyTracker.record` 每记一次就把整段历史扫一遍，是 O(N²)，15000 次运行要 1 秒以上。
5. 护栏：
   - 可以修订的用例照样要靠反馈通过，把所有用例都改成一轮会挂。
   - 只跑一轮的依据是 `refine`，不是类别。`custom_c002`（发邮件）也是 refine=False，按 `category == "online"` 判断会在它的 Replay 上再报一次 LookupError。
   - 捕获 `LookupError` 来结束循环的写法，会被 `requests` 的断言抓住：agent 被多问了一次。
   - 用 `copy.deepcopy` 复制用例不行：函数按引用复制，闭包还是同一个。
   - 整个套件跑完一遍再跑下一遍。写成 `[... for make in factories for _ in range(repeats)]` 会让同一个用例连着跑三次，顺序断言会挂。
   - 窗口按用例各算各的，旧的运行要滑出窗口，运行次数不够 window 次时也要能判出 flaky。用通过计数实现时，最旧的一次滑出窗口要从计数里减掉。
   - 窗口正好是 window 次。bench_t007 是过、不过、过，再过一次时最近 3 次是不过、过、过，还在名单上；再过一次才离开。窗口少一次（比如 append 之后用 `len(recent) >= window` 判断要不要丢掉最旧的一次）、多一次，或者只看最近两次是否不同，都会在这两步挂掉。

看什么：是不是先读 traceback，看出 LookupError 是被谁调用出来的；是不是逐句对照 docstring 和代码；每改一处就重跑。

提示：
- H1："Who asked the replay for a second turn, and should it have?"
- H2："Read evaluator_optimizer's docstring against its loop, line by line."
- H3：直接指出 `range(case.max_rounds)` 和失败分支的 `case.max_rounds`。

追问：
- "After refinement three of five cases pass. What's the first-round pass rate, and which number goes on the dashboard?"（首轮是 0/5；两个都要报，课里的 4/4 PASS 全靠修订）
- "The judge's reason says 'missing sticks in recipe'. What does that do to the refined pass rate?"（反馈直接告诉了答案，修订后的通过率虚高）
- "Should pull-request runs feed the tracker?"（不应该。PR 把一个用例改坏了，窗口里就有过有不过，它会被当成 flaky 隔离掉，闸门就放过了这次回归。`EvalPipeline.run` 只用主干的运行喂 tracker）

### Part 2 每个提交一份快照（目标 12 分钟）

坑：
- 同一个提交重跑 CI，新快照整份替换旧的。合并新旧用例会留下已经删掉的用例。
- 基线按主干历史从新到旧找第一个有快照的提交。没有结果的提交跳过；PR 的快照即使更新也不能当基线；按文件修改时间找会挂，因为重跑会让旧提交的文件变成最新的。有失败用例的快照照样是基线：c3 有一个失败的用例，只认全部通过的快照会退到 c2。
- 用例顺序要原样保留。按层分组、按 id 排序保存都会挂；用例按 id 存成 JSON 对象时，`json.dumps(..., sort_keys=True)` 也会把它们排序。
- 用 id 作键的 dict 会把重复的 id 悄悄合成一个，必须报 ValueError。
- 未知类别（`"Online"`）要报 ValueError。讲解里说过，拼错的类别会在分类汇总里悄悄消失。
- sha 只认 40 位小写十六进制；`"HEAD"`、7 位短 sha 和大写的 sha 都要报错。只查长度，或者拿 `string.hexdigits`（里面有大写字母）去查，都会放过大写的 sha。大写和小写的同一个 sha 在 macOS 默认的文件系统上是同一个文件，在 Linux 上是两个文件。末尾带换行的 sha 也要报错，`git rev-parse` 的原始输出就是这样：`re.match(r"^[0-9a-f]{40}$", sha)` 会放过它，因为 `$` 能在末尾的换行前匹配，要用 `re.fullmatch`。没有快照的提交 `load` 报 KeyError。
- docstring 要求原子替换：同目录写临时文件再 `os.replace`。测试不检查这一点，用追问讨论。
- 测试不拦、可以接受的写法：`passed` 存成 0 和 1，读回来和 True、False 相等（`1 == True`），下游也只按真假用。

追问：
- "CI gets killed halfway through a save. What does the next reader see?"（原子替换，读者看到的要么是旧文件，要么是新文件；临时文件要和目标放在同一个目录，放到系统临时目录可能跨文件系统，`os.replace` 会直接报错）
- "Two jobs save the same commit at the same time?"（后一个 replace 赢；读者看到的总是某一份完整的快照）
- "Every CI run is a fresh process. Where does the flaky window come from?"（从这个库里主干最近 k 份快照重建）

### Part 3 合并闸门（目标 12 分钟）

坑：
- 按 id 一个一个比，不比总通过率。b03 坏了、b07 修好了，总数不变，但 b03 仍然是回归。
- 分母只算可比的用例：两边都有、两边都不是 flaky。把 10 个新用例算进分母，benchmark 的 1/12 会被稀释成 1/22，闸门就放行了。只算主干上通过的用例也不对：b07 在主干上失败、这次通过，照样可比，分母是 12 不是 11。
- flaky 不管是本次还是主干上标的，都只报告不计数。c12、c13 这次 flaky 且失败，b13、c11 在主干上 flaky，都不能算回归。b14 在主干上 flaky、两边都通过，同样列进 flaky、不进分母：只在“本来要算回归”的用例上查 flaky，会把它漏出 flaky 列表，或者把 benchmark 的分母算成 13。
- 新用例失败不算回归，只列进 new。主干有、这次没有的用例列进 removed，不能悄悄消失，也不能当成回归。
- 四个列表的顺序都写在 docstring 里：regressed、flaky、new 按这次快照的顺序，removed 按主干的顺序。用集合求差再排序会挂：这次的快照把 c20–c22 排在 b20–b29 前面、b14 排在最后，主干把 b99 排在最后。
- 每层各用各的上限。online 的上限是 0，一个 guardrail 回归就要拦，即使总体只是 1/44。按课里 `ci_gate` 那样全体合算会挂。
- 上限是容忍度。`drift` 里 benchmark 1/40 是 2.5%，没超过 5%，要放行，但 b17 照样列进 regressed。只要有回归就拦的写法会挂在这里。
- 某一层没有可比用例时不拦，也不能除以 0。比较用整数：`regressed * 100 > limit * comparable`。写成 `>=` 时，上限为 0 的层和没有可比用例的层会永远拦下（`0 >= 0`），`guard` 那组会多出一条 custom 的理由。
- 用除法（`regressed / comparable * 100 > limit`，再判断 comparable 为 0）也能通过：非 0 的上限在测试数据里都没有正好踩到边界。可以接受，用追问讨论浮点边界。
- `limits` 缺类别时 docstring 要求 ValueError，测试不检查。直接 `limits[category]` 报 KeyError 可以接受；`limits.get(category, 100)` 这种默认值会把配置里写错的类别悄悄变成不设防，值得追问。
- 没有基线要拦，空快照也要拦。
- 最后一段是端到端检查：课里的用例经过 Part 1 的框架、Part 2 的库和这一关的闸门，一个不再引用论文的 PR 必须被拦下。

追问：
- "Why not compare overall pass rates, like the lesson's ci_gate?"（一升一降会抵消；`0.95 - 0.90` 在浮点里是 `0.04999999999999993`；4 个用例时 5% 的阈值没有意义；见本课测验 Q11）
- "The guardrail fails on main too. Should every PR be blocked until it's fixed?"（这是另一条规则：guardrail 必须通过的清单。闸门管的是回归）
- "A case has been quarantined as flaky for two months."（隔离要有负责人和期限；报告里要能看到隔离区有多大）

### Part 4 GitHub Actions 日志（目标 14 分钟）

坑：
- 输出格式由测试里模仿 Actions runner 的解析代码决定：每行一条命令或一行普通日志。和 runner 一样，单独一个 CR、一个 LF 或者 CRLF 都算换行。
- 消息里的 `%`、`\r`、`\n` 要写成 `%25`、`%0D`、`%0A`，否则一条命令会断成两行。只转义 `\n` 不转义 `\r`，`online:pii-ssn` 的消息会在 CR 处断开。`%` 要最先替换，最后替换会把 `%0A` 变成 `%250A`。完全不转义 `%` 也会挂：`bench_t002` 的消息里有一个已经编码过的链接 `?min=90%25`，不转义的话 runner 会把它读成 `90%`。属性值（`title=`）还要把 `:`、`,` 写成 `%3A`、`%2C`：`custom_c001[en,de]` 不转义逗号会被拆成两个属性，`online:pii-ssn` 不转义冒号就解析不出来。
- 反过来，消息里的冒号不能转义。共用一套转义函数会让 `missing sticks: recipe` 变成 `missing sticks%3A recipe`。
- flaky 的用例不管这次过没过都写成 warning：`custom_c001[en,de]` 过了，`custom_c002` 没过，两个都是 warning。先判断失败会把 `custom_c002` 写成 error；只把失败的 flaky 当 warning，会把 `custom_c001[en,de]` 写成 ok。
- 组之间不能交错，组内按套件顺序，所以要按层缓冲。套件里 `custom_c002` 排在 `custom_c001[en,de]` 前面：组内按完成顺序会把 benchmark 组排反，按 id 排序会把 custom 组排反。组的顺序固定，后面的层先完成也要等前面的组输出。
- 一层的用例全部到齐、前面的组也都输出了，就立刻输出这一组。测试记录每个 `::endgroup::` 出来时拉取了几条结果，应该是 `[4, 4, 5]`。先读完整个流会得到 `[5, 5, 5]`；每来一条结果最多输出一组会得到 `[4, 5, 5]`。
- 最后一行是结论，`decide` 要拿到按套件顺序排好的全部结果。结果流缺了用例、或者同一个用例来了两次，要报 ValueError。
- 写成普通的 async 函数，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出来这里需要 async generator。
- 测试不拦、可以接受的写法：一次 yield 一整组（日志文本一样，docstring 要的是一次一行）；suite 里没有的用例、suite 自己重复或类别未知，docstring 要求 ValueError，测试不检查，直接查字典报 KeyError 也行。
- 测试数据里的 CR 都在 CRLF 里。把 `\r\n` 整个换成 `%0D%0A`、单独的 CR 原样留下的写法测试拦不住，但 runner 遇到单独的 CR 也会断行，看到了要指出来。

追问：
- "Why a fixed group order instead of the order the layers finish?"（两次运行的日志能直接 diff）
- "One case hangs forever."（每个用例有超时，超时记为失败结果；结果流必须能结束）
- "Why are passes plain lines and failures annotations?"（error 和 warning 会显示在 PR 上，通过的用例只需要留在日志里）

### Part 5 护栏和规则的覆盖图（目标 12 分钟）

坑：
- 只有通过且不 flaky 的用例才算支撑：`custom_c001` flaky，`custom_c003` 失败，`rule:cite` 因此没有覆盖。没跑的用例（`online_o004`）也不算。
- covered 里的支撑用例按快照顺序列出。COVERS 里 `online_o003` 写在 `online_o001` 前面，照 covers 的顺序收集会把 `guard:pii` 的两个用例排反；按 id 排序会把 `rule:scope` 的排反。
- 派生规则自己有通过的用例还不够，它派生自的每一条都要覆盖，一直往上。只看父规则自己有没有用例，`rule:small-diffs` 的链会少一环。
- 链只沿 derived_from 里第一个没覆盖的父规则走，一直走到没有用例支撑的那一条。`rule:tests-first` 的第一个父规则 `rule:scope` 是覆盖的，所以链走 `rule:cite`，不走后面的 `guard:dom`，也不走链更长的 `rule:verified-cites`。挑最短或最长的链都会挂。
- `rule:verified-cites` 写在它的两个父规则前面，不能假设父规则先出现。按给定顺序算一遍、把还没算到的父规则当成没覆盖，它的链会变成 `("rule:verified-cites", "rule:scope")`，可 `rule:scope` 其实是覆盖的；当成覆盖，它自己会被算成覆盖。
- 菱形不是环：`rule:small-diffs` 从两条路都能走到 `rule:cite`。用一个全局 visited 集合判环会误报。环要按当前路径判，而且没有用例的规则也要往上查，不然 `rule:a` 和 `rule:b` 互相派生的环查不出来。
- covers 里写错的名字要报 ValueError。写错名字的 `custom_c004` 不在快照里，只检查跑过的用例会放过它。结果按给定顺序列出，不排序。
- 未知的 kind 和重复的名字，docstring 要求 ValueError，测试不检查。

追问：
- "One passing case per guardrail. Is that enough?"（不够。要有对抗性的变体，还要轮换用例，课里说过对 eval 过拟合）
- "Ten thousand rules in one derivation chain?"（递归深度会超限，改成显式栈）
- "Where should this run: on every PR, or nightly?"（覆盖图很便宜，每个 PR 都跑；新加的护栏没有用例时直接在 PR 上报出来）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出首轮通过率、状态隔离、原子写、基线选择、隔离区管理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
