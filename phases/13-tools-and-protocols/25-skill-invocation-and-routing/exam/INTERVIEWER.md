# 面试官手册：SkillRoute（13/25）

候选人计时期间不要看。候选人手里只有 README、`skillroute/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | SKILL.md 改了，路由器要不要重新读？ | "No. A router serves one catalog snapshot. Discovery builds a new router when the catalog changes." |
| 1 | 目录里会有重名的 skill 吗？ | "No. Discovery already resolved duplicates, so names are unique here." |
| 1 | disable-model-invocation 会不会也挡住应用或 harness？ | "Not in this host. It removes selection by the model and by agents. The application and harness channels have their own allowlists." |
| 1 | 字段值写成 yes 或 1 怎么算？ | "This host only understands true and false, as booleans or as text in any case. Anything else leaves the default. The tests don't cover it; tell me what you'd prefer." |
| 1 | 两个 skill 并列，但分数都没过阈值，要不要问用户？ | "No. If nothing clears the threshold, abstain." |
| 1 | eligible() 对 skill 这个 actor 返回什么？ | "Composition needs a caller and a depth, so with no request nothing is eligible. The tests don't use it." |
| 2 | resume() 要不要马上写文件？ | "Your call. The tests only look at the file after something changed." |
| 2 | 需要 fsync 吗？ | "Write the whole file and swap it in. fsync is a good habit; the tests don't measure it." |
| 2 | commit 可以传短 SHA 吗？ | "No. The host resolves the tag to the full 40-character id before it calls resume." |
| 2 | 两个进程同时写同一个文件？ | "Not in this session. Tell me what you would add." |
| 2 | 同一个幂等键换了 target 怎么办？ | "The key identifies the write. A recorded key answers with its recorded result." |
| 2 | 外部写入其实成功了，但记录之前进程崩了？ | "That's what the key is for: we pass it to the external system so it can drop the duplicate. Here, record the write once the call returns." |
| 3 | 能用 shlex 吗？ | "Yes. Check that it follows the rules in the docstring." |
| 3 | 选项的值是 -1 这种以减号开头的呢？ | "Only -- marks an option. -1 is a value." |
| 3 | --dry-run=false 能把开关关掉吗？ | "No. A flag takes no value, so that's an error." |
| 3 | 文本 "true" 要不要转成布尔值？ | "No. Booleans only come from flags and defaults." |
| 3 | 整数允许前导零、加号、空格吗？ | "Digits with an optional minus sign. The tests don't push further than that." |
| 4 | 用户批准了“本会话一直允许”呢？ | "This host doesn't have that. An approval lasts until the turn ends." |
| 4 | 什么时候重新加载正文：压缩时还是之后？ | "Right before the skill's next tool call. Reloading at the compaction would undo it." |
| 4 | 用户又一次调用已经激活的 skill？ | "Nothing happens. It stays active, with whatever body it has now." |
| 4 | 隐式路由什么都没选中，要不要输出一行？ | "No." |
| 4 | 第一个用户回合之前会有事件吗？ | "Not in this session." |
| 5 | 调用者和深度从哪里来？ | "From your own record of the chain. A request never says." |
| 5 | fallback 对哪些失败生效？ | "Every call that didn't complete: refused, wrong contract, or stopped. No fallback means stop." |
| 5 | fallback 可以是 None 吗？ | "None means stop. Any other value is a fallback." |
| 5 | fork 出来的 skill 能看到父 skill 的任务吗？ | "Only through its own request, in ctx.request." |
| 5 | 同一个 skill 先后被调两次（不是环）？ | "That's fine: once a call returns, that skill is off the chain. The tests don't cover it." |

## 每关：要看什么、提示、追问

### Part 1 修路由器（目标 11 分钟）

一个测试里叠了 4 个缺陷，外加几个护栏：

1. `Router.route` 的隐式分支先给所有 skill 打分，取最高分，再问策略。incident-triage 得 0.8 但不许模型调用，路由就整个弃权了，0.5 分、可以调用的 incident-review 根本没被考虑。这正是课里 Eligibility must precede ranking 批评的写法。
2. `ExtensionPolicyAdapter.allows` 把两个宿主字段对错了 actor：`disable-model-invocation: true` 挡住了所有人，`user-invocable: false` 挡住的是模型。这是课里 The confusing detail matters 那段说的两种误读。测试是在上一层 `Router.route` 和 `Router.eligible` 的结果里看到它的：人类按名字调 incident-triage 被拒，人类菜单和模型目录都不对。
3. 没有歧义规则。课里代码的 `max(key=(score, name))` 在并列时选字典序最大的名字，`InvocationPolicy.ambiguity_margin` 定义了但没人用。docstring 写的是：并列或差距在边际内就什么都不激活，把候选按名字列在 `candidates` 里让宿主去问。
4. `route` 和 `eligible` 每次调用都通过 `_catalog()` 把所有 frontmatter 重新解析一遍。3000 个 skill、50 次显式调用，本机约 0.27 到 0.32 秒；只解析一次、按名字查表以后约 0.07 毫秒，限值 0.02 秒。

护栏：
- 字段写成文本：`disable-model-invocation: "false"`（带引号）、`user-invocable: False`、`disable-model-invocation: TRUE`。给出的解析器只把不带引号的小写 true/false 变成布尔值，其余都是文本。为了提速预先算布尔值时写 `bool(value)`，`bool("false")` 是 True；只认 `is False`、大小写敏感地比较，也都会挂。课里的 `_extension_false` / `_extension_true` 已经是对的，留着用就行。
- core 适配器不认宿主字段；应用通道照样能预加载“两边都关掉”的 staged-rollout；按名字调用照样要过策略。
- 歧义只在可调用的 skill 之间判断：被挡住的 log-digest 和 deploy-digest 分数相同，也不算歧义。
- 并列但都没过阈值，是弃权，不是询问。
- 差距正好等于边际的情况测试没有压：浮点下 0.8 - 0.6 比 0.2 大一点点，这种边界本来就不稳。完全并列必须算歧义，所以边际 0 时要用 `<=`。

看什么：是不是先看断言里的实际值（`(False, 'incident-triage', ..., 0.8)`）就明白发生了什么；改策略代码前会不会先读 docstring 和讲义里那张矩阵；性能问题会不会先测量再改。

提示：
- H1："What does route() do with the best-scoring skill when the policy blocks it?"
- H2："Which actors does each host field block in ExtensionPolicyAdapter?"
- H3：直接指出隐式分支的顺序是打分、取最大、再问策略；然后指出 `_catalog()` 在每次请求里都被调用。

追问：
- "After the fix, 'draft release notes from merged pull requests' goes to release-readiness with 0.23 once release-notes is human-only. Good result?"（不好。先资格后排序只保证被挡住的 skill 不会被选中，不保证剩下的最高分就合适。可以记录被过滤掉的最佳候选，差距悬殊时弃权，并提示用户用 `/release-notes` 显式调用。quiz Q9 就是这个例子）
- "A host field says `yes`. What should happen?"（课里的写法是 fail-open：认不出的值等于没写。更安全的适配器对已识别字段的未知取值报错或按拒绝处理，quiz Q7）
- "What happens with model_threshold 0?"（零分的 skill 也会被激活，quiz Q10(b)。应该要求分数大于 0）
- "A million skills?"（显式调用按名字查表；隐式调用的资格集合可以按 actor 预先算好；词汇路由可以建倒排索引，只给和请求有共同 token 的 skill 打分。真实宿主用模型路由，成本在上下文预算上，见第 24 课）

### Part 2 可重入状态（目标 12 分钟）

坑：
- 文件放在 `artifacts/` 下，这个目录一开始不存在。
- 每次改动都要在方法返回前写进文件。测试用一个新的 `SkillRun.resume` 模拟中断后的下一个进程，只在最后保存的写法会挂。
- 读回来要完全一样：`Step` 和 `Write` 对象，不是 dict；步骤和写入保持发生的顺序（按名字排就不对了）；0、`[]`、`None` 都是正常的值，`or None` 之类的写法会把它们变没。
- 已记录的幂等键直接返回当时记下的结果，不再调用 action，结果是 `None` 也一样。用 `if write.result:` 判断“有没有记录”，204 No Content 那次状态写入就会重复。
- 写入只认幂等键：测试第二次用 `github:release-draft` 这个 target 名字发同一个键，也要直接返回记录。按键加 target 查，就会再写一次。
- 写入要在 action 返回之后才记：action 抛异常时什么都不记，下次同一个键会再执行一次。先占位再调用是“最多一次”，外部写入失败后就永远补不上了。
- 重新校验 commit 要比完整的 40 位 id。测试里换过的 commit 和原来的前 12 位相同，按前缀比较会把旧步骤当成有效的；短 SHA 直接报 ValueError。
- commit 变了、参数变了、候选版本变了，都是另一次运行：丢掉已完成的步骤，但保留外部写入的记录，因为那些写入已经真的发生了。把整个文件扔掉，下一次就会重复发同一条状态。
- 文件里是另一个 skill 的运行，报 ValueError，不能当成过期的同一次运行。
- 同一个步骤完成两次报 ValueError；JSON 存不准的输出（`{200: 14}` 读回来会变成 `{"200": 14}`）报 ValueError，而且什么都不记。先追加再检查的写法会在内存里留下这一步。
- 文件格式是固定的：skill 的指令也读写这个文件。测试先读一个“skill 自己写的”文件，再检查宿主写回去的内容和它对得上。

追问：
- "The process dies halfway through writing the file. What do you lose?"（直接覆盖写会留下半个文件。先写同目录的临时文件、fsync，再 `os.replace`，旧文件要么完整保留，要么整个换成新的。参考答案是这么写的；这一章别的题已经考过崩溃恢复，这里测试没有模拟）
- "The external call timed out. Did the write happen?"（不知道。所以幂等键要一起交给外部系统，由它去重；宿主这边是至少一次，加上对方去重，效果就是恰好一次）
- "Why keep the writes when the commit moved?"（它们记录的是外部世界已经发生的事。新 commit 如果用新的键，旧记录不碍事；扔掉记录，同一个键再出现时就会重复写）
- "Two hosts resume the same run?"（需要锁文件或租约，见第 13 课的 worker lease；每次重读文件也只能避免用过期副本）

### Part 3 参数绑定（目标 12 分钟）

坑：
- 第一种表示，命令文本：`str.split` 会切开引号里的空格；`shlex.split(posix=False)` 会把引号留在参数里；只认双引号、不处理转义的正则会弄坏 `"say \"ship it\" twice"`；`""` 是一个空参数，不能丢；没闭合的引号要报 `ArgumentError`，shlex 自己的 ValueError 要转换；没有开头的 `/` 也要报错。用 shlex 完全可以，它正好是 docstring 写的这套规则。`#412`、`~/notes`、`$HOME` 原样保留：`shlex.split` 默认不认注释，但自己建 `shlex.shlex` 时 `commenters` 默认是 `#`，后面的参数会被整个吃掉；`os.path.expandvars`、`expanduser` 也不能用。
- 第二种表示，绑定：`--` 之后全是位置参数，`-- --dry-run` 里的 `--dry-run` 是 notes 的内容；选项的值不能以 `--` 开头，但可以以单个减号开头：`--min-approvals -1` 的值是 `-1`，`-rc` 是位置参数，用 `startswith("-")` 判断会挂；`--min` 不是 `--min-approvals`（argparse 默认允许缩写）；缺必填参数放进 `missing` 让宿主去问，不能报错，也不能拿空串顶上；`publish` 是固定参数，调用方传了就报错，绑定结果里永远是默认值；未知选项、多余的位置参数、重复的选项、给开关传值，都报错；默认值也是绑定的一部分。
- 第三种表示，类型化：只有 schema 要求 integer 的地方才把文本转成整数，`"2.10"` 和 `"007"` 是字符串就保持字符串；`"3.0"`、`"three"` 不是整数，`"-1"` 是（`str.isdigit()` 不认负号）；boolean 属性收到文本 `"false"` 要报错，用 `bool()` 转就成了 True，固定为 False 的 publish 就被打开了；string 属性收到布尔值也要报错；不在 schema 里的名字、缺少的必填属性，工具这一侧要再检查一遍。
- 最后一段是端到端检查：`SkillHost.prepare` 先过 Part 1 的路由器，`"v2.4.0; rm -rf ~"` 和 `"$(whoami) | tee"` 从命令行一路到工具参数都只是数据；model-only 的 style-guide 在绑定参数之前就被拒绝。

追问：
- "How would you run scripts/inspect_release.py with these values?"（`subprocess.run([sys.executable, script, "--candidate", value, ...])`，参数向量，不用 `shell=True`，不拼字符串。课里那句 Do not interpolate raw arguments into shell commands）
- "Why not just call int()?"（`int()` 接受 `" 3"`、`"+3"`、`"3_000"` 和非 ASCII 数字，比 schema 文本的意思宽。这一章别的题已经考过这些，这里测试没有往下压）
- "Another host hands the skill the raw argument text instead of a vector. What changes?"（skill 只能自己再解析一遍，引号规则由宿主决定，换个宿主就可能不一样。所以绑定放在适配器里，不写进可移植的 SKILL.md）
- "Where would a schema minimum go?"（`tool_arguments`。工具这一侧拿到的是类型化的值，在这里再校验一次）

### Part 4 多轮生命周期（目标 13 分钟）

坑：
- 输出格式由测试的解析代码决定：所有块拼起来以换行结尾，按 `\n` 切开，每行一个 JSON。少了换行、多一个空行、`indent=2` 都会挂。字段名和取值看 docstring 的表。
- 回合从 1 开始，按 UserTurn 计数。
- `/name` 是人类显式调用；普通文本只有在没有激活的 skill 时才让模型隐式路由，有激活的 skill 时就是在接着干活，不路由（第 5 回合那句话和 style-guide 完全匹配，路由了就会多出三行）。
- 再次调用已激活的 skill 什么都不输出（第 2 回合）。
- 批准在同一回合内累加，下一个 UserTurn 清空，压缩不影响它（第 3 回合压缩后 timeline.read 照样能执行）。只是接着干活、不路由的回合也要清空：第 5 回合 incident-review 调 git.log 被拒，第 4 回合的批准在这里无效。新的 Approve 覆盖旧的、批准跨回合有效、压缩时清空批准，都会挂。
- 压缩丢掉所有激活 skill 的正文，但 skill 仍是激活的。每个 skill 在自己下一次工具调用之前各自重新加载：incident-review 在第 3 回合，release-readiness 在第 4 回合，而且这时 SKILL.md 已经改成了 r2。全会话共用一个“压缩过”标志、压缩时马上加载、每回合都加载、从缓存里拿旧正文，都会挂。
- 重新加载发生在这次工具调用被批准与否之前：第 4 回合 git.log 先被拒，但正文已经重新加载了。
- 检查失败不输出，skill 仍然激活，之后还能执行；检查通过输出 completed，skill 不再激活；对没激活的 skill 做检查什么都不输出。
- 没激活的 skill 发起工具调用，输出 denied，原因是 skill not active。
- 正文只在激活和压缩后重新加载时读取，测试数了 load_body 的调用次数。
- 每个阶段一发生就输出：探针在第一个回合之后跟着 200 个事件，第一行出来时最多只能多拉一个。先把整个流读完再处理，或者把一个回合的行攒到下一回合再发，都会挂。

追问：
- "Why not keep the body in the host and skip the reload?"（压缩以后模型的上下文里已经没有这些指令了，凭记忆继续就是照着模型看不见的指令干活；而且文件可能改过，测试里的 r2 就是这个情况）
- "Tool approvals that last the whole session?"（宿主可以这么设计，但课里说 Tool allowances may last one turn while instructions persist longer，持续的授权是一项要明说的策略，不能靠默认）
- "What does Part 2's file have to do with compaction?"（压缩后重新加载正文时，skill 按正文里的恢复规则重读 `artifacts/release-readiness.json`、重新校验 commit 再继续；trace 里的 reloaded 就是这一步发生的地方）
- "Where is argument binding in this trace?"（课里要求在 trace 里把 eligibility、selection、activation、argument binding、execution 分开。可以在 activated 和第一次 executing 之间加一个 bound 阶段，内容来自 Part 3）

### Part 5 skill 调用链（目标 12 分钟）

坑：
- 调用链是宿主自己记录的：从会话启动的 skill 开始，到当前正在运行的 skill。请求里没有调用者和深度。
- 目标已经在链上就是环，不管在哪一层：回到根的两段环、经过第三个 skill 的长环、不经过根的环（triage → collect → summarize → collect）。只查直接自调用，或者只查根，都会挂。拒绝原因里是完整路径：链加上目标。
- 检查顺序是环、深度、存在。长环那一跳正好也超了深度，先查深度就会报成 depth。
- 深度：根自己发出的调用是 1。限值取这次请求和链上每个请求的 max_depth 里最小的那个：license-scan 自己要了 5，但上面的请求只允许 2，所以 depth 3 被拒；summarize 那一跳被它自己请求里的 1 挡住。只看这次请求、只看前面的请求、深度从 0 数，都会挂。
- 不存在的 skill 被拒；有 fallback 时调用方拿着 fallback 继续。只有 None 表示停止：notes-writer 的 fallback 是空串，用 `if req.fallback:` 判断会把它当成停止。
- 回复的契约和 expected 不一样就算失败，notes.md 不是 release-notes.md。
- 没有 fallback 的失败让调用方停下：在调用方里抛 Stopped，调用方记为 failed "stopped"，再由它上一层请求的 fallback 决定。fallback 被忽略、失败时返回 None、只对 refused 用 fallback，都会挂。
- 停下以后链要恢复：smoke-test 停下之后，根接着调 summary-writer，深度必须还是 1。用可变栈又没在异常路径上弹出，summary-writer 就会被算成第 2 层而被拒。
- 调用树记录每一次调用，按发生顺序，带上 used_fallback 和完成时的结果。
- fork 出来的 skill 看不到调用方的上下文；shared 的 skill 看到的正好是调用方看到的东西，所以挂在 fork 下面的 shared skill 看到的也是空的。请求本身总在 ctx.request 里。
- 根自己停下时，根就是 failed。
- skill 自己的错误原样抛出：测试最后一段的 skill 读了不存在的 `inputs[0]`，`IndexError` 要从 `run` 里出来。`except Exception` 把它当成 stopped，就会挂。

追问：
- "Why not trust caller_name and depth from the request, as code/main.py does?"（那是请求方自报的，任何构造请求的代码都能说自己是 release-readiness、深度为 1。宿主自己记录调用链，quiz Q12）
- "Why not a visited set?"（visited 集合会把先后调用两次的同一个 skill 当成环。环只关心此刻正在运行的那条链。这一章别的题已经考过这个区别，这里测试没有覆盖）
- "Where does the host policy come in?"（在目标运行之前，用 `Actor.SKILL` 走 Part 1 的路由器：调用者取链的末端，深度取链长，再看 skill_caller_allowlist 和 max_skill_depth。这套题没有接这一步）
- "What does a real fork cost and buy?"（换来干净的上下文，不会把父会话的历史带进去；代价是要把任务和产物路径写清楚，结果再通过工具结果返回。课里 The host decides how to activate it）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback 和断言里的实际值、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出：资格和相关性分开、宿主字段不可移植、整文件替换、幂等键交给外部系统、参数不进 shell、压缩后重新加载、宿主记录调用链 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
