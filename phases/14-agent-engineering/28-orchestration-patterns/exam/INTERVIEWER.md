# 面试官手册：Orchestra（14/28）

候选人计时期间不要看。候选人手里只有 README、`orchestra/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 路由器的回复要不要忽略大小写？ | "No. It names the member exactly, maybe with whitespace around it." |
| 1 | 成员能删除吗？ | "Not in this version. Members are only ever registered." |
| 1 | 一个成员都没有的监督者收到任务怎么办？ | "Nothing fits, so it escalates. The tests don't cover it." |
| 2 | JSON 要缩进吗？ | "Either way. People do edit it by hand, so indentation is nice." |
| 2 | 要不要 fsync？ | "Yes, before the replace. The tests can't check it, so tell me what you did." |
| 2 | 读到不认识的 format 版本怎么办？ | "Not covered. Say what you would do." |
| 3 | 贪心分组不是最优的，要不要找最优？ | "No. We want a plan people can predict. Greedy, in order." |
| 3 | 根监督者也受预算限制吗？ | "Yes, the same budget, the same overhead." |
| 3 | 根下面能不能挂只有一个成员的监督者？ | "No supervisor below the root ever has a single member." |
| 4 | 一个专家报错，要不要取消其他调用？ | "No. Report it as a failed result and keep going." |
| 4 | 收到一个我们没发过的 id？ | "Not covered. Say what you would do in production." |
| 4 | progress 通知要不要转发给上层？ | "Not in this version. Skip them." |
| 5 | 根团队自己要不要匹配关键词？ | "No. Every task starts at the root." |
| 5 | 选中的 worker 会不会拒绝？ | "No. A picked worker always takes the task." |
| 5 | 根团队走不通算不算一次回溯？ | "No. A backtrack is a return to the team above, and the root has none." |
| 5 | 接手的 worker 要不要也写一行 trace？ | "No. A trace line is a pick. The worker taking the task costs an op, but it isn't a pick." |
| 5 | 回溯超过上限、放弃的时候要不要写一行？ | "No. Nobody is asked for a pick, so there's no line. The route already says the task is unresolved." |

## 每关：要看什么、提示、追问

### Part 1 修监督者路由（目标 10 分钟）

一个测试里叠了 4 个缺陷和 2 个护栏：

1. `prompt()` 只对描述做了 `strip()`，多行描述把换行带进了提示词。错误不在 `prompt()` 报出来，而是在 `run → route` 调用的路由器假对象里，报 `prompt line is not a member`。
2. 选中的成员是子监督者时，`run()` 直接 `return member.run(task)`，把子监督者的结果原样交回：path 从 customer_ops 开始，少了 desk；ops 是 2，少了 desk 自己那一次路由决策。docstring 要求 path 从拿到任务的监督者开始，每次路由决策和每次 worker 调用各算 1 次。课里的 `hierarchical` 每一层都记一次 op、一行 trace，所以层级是最“深”的；少记一层，层级看起来就和单层一样便宜。worker 选对了，只有 path 和 ops 不对，要看候选人能不能读出 Outcome 的差别。
3. 回复对不上任何成员时退回第一个成员，和课里 `classify` 最后的 `return "sales"` 是同一个毛病；docstring 要求交给人（ESCALATE）。只在回复是字面上的 `none` 时交给人也不够：测试里 commercial 的路由器回了别的团队的 worker（refund），也要交给人，既不能塞给 sales，也不能越过团队派给 refund。
4. 每次路由都把所有成员的描述重新拼成提示词。3000 个成员、800 个任务要 0.5 秒左右，限值 0.04 秒。
5. 护栏一：提示词缓存后，注册新成员必须让缓存失效，测试在两批之间注册了 `late`。
6. 护栏二：注册 3000 个成员要在 0.05 秒内完成。在 `register` 里立刻重建提示词是 O(N²)，要 0.7 秒以上。

看什么：是不是先读 traceback，看出断言出在路由器里、但坏数据来自 `prompt()`；是不是先 `print(repr(...))` 看实际的提示词和 Outcome；每改一处就重跑。

提示：
- H1："The router is complaining about a line. Who wrote that line?"
- H2："Which supervisors does the outcome say the task went through? Read the Outcome docstring again."
- H3：直接指出 `next(iter(self.members))` 和 docstring 不一致。

追问：
- "Why not give one supervisor all 3000 workers?"（提示词装不下，路由质量也会下降；这就是 Part 3 的层级）
- "The router names a member that doesn't exist. What is that, and why escalate instead of retrying?"（幻觉出来的名字；兜底到某个专家会悄悄做错事，交给人至少可见）
- "How would you see why a task went where it did?"（每次路由决策记一条 trace，包括提示词版本和回复）

### Part 2 拓扑快照（目标 12 分钟）

坑：
- 继承（INHERIT）和显式 `null`（不用 LLM、按关键词路由，即课里 CrewAI 的 Flow）是两种不同的配置。两者都写成 `null`，读回来就分不清了。读的时候用 `t.get("router")`，缺这个键会读成 None，手写的那份快照会挂。
- `keywords` 和 `members` 是 tuple，JSON 读回来是 list，要转回去，否则 dataclass 比较不相等。
- 描述原样保存，不能套用 Part 1 的折叠；团队顺序就是配置的一部分，不能排序。
- 校验要在写任何文件之前做：重名（worker 和团队共用一个命名空间，只在各自内部查重会漏掉 worker 和团队同名）、引用不存在的成员、root 不是团队（只查 root 存在会放过一个 worker 当 root）。先写后校验，坏配置已经覆盖了好快照；在写临时文件的过程中校验、又只在 OSError 时清理，会留下临时文件，测试最后会看目录。
- 原子替换：直接 `open(path, "w")` 写快照，写到一半崩溃就只剩半个文件。测试把 `os.replace` 和 `os.rename` 换成会失败的函数，直接写的实现会报 DID NOT RAISE。
- 临时文件要和快照在同一个目录。`tempfile.mkstemp()` 不带 `dir` 会写到系统临时目录，真实环境里跨文件系统时 `os.replace` 会失败。替换失败后要删掉临时文件。
- 测试不拦、可以接受的写法：用 `os.rename` 代替 `os.replace`（POSIX 上一样是原子的，Windows 上目标已经存在时会失败，可以追问）；`ensure_ascii` 用默认值，非 ASCII 写成 `\u` 转义，读回来一样。

追问：
- "Two deploys save the topology at the same moment?"（后写的覆盖先写的；需要锁文件或者带版本号的比较后替换）
- "Why keep 'inherit' separate from null at all?"（继承让改一处就改整棵子树；null 是有意关掉 LLM，两者语义不同）
- "Someone edits the JSON by hand and makes a cycle. Where do you catch it?"（加载时校验，或者至少在 Part 5 路由时报错）

### Part 3 按上下文预算建层级（目标 12 分钟）

坑：
- 每个提示词都有固定开销，组能装多少要从 `overhead` 开始算。判断“这一层放不放得下一个监督者”时也要加开销，根的提示词一样付开销：e、b、f 的 token 合计正好 120，不加开销会以为放得下，三个直接挂在根下面，根的提示词实际是 140。
- 正好等于预算算放得下。第一组 a、b、c 的 100 加上 20 的开销正好是 120，用 `<` 会切错。
- 子监督者在父级里的描述占 `team_tokens`，不是它所有成员的 token 之和。
- 只有一个元素的组不包监督者，原样带到上一层（课里的 Fake hierarchy；`outputs/skill-orchestration-picker.md` 也说一个分支只剩一个专家就要压平）。带上去的元素留在原来的位置：测试里 j 一直被带到根下面，e、b、f 那组里 e 排在新监督者 L1-0 前面。
- 编号只数新建的监督者：e 单独一组时，b、f 那组是 L1-0，不是按组的位置算出来的 L1-1。
- 一层切完没有变少就报 ValueError，不然会死循环。测试用后台线程等 2 秒。
- 单个 worker 比预算还大要报 ValueError，并且消息里写出它的名字。
- 所有 worker 一个提示词就放得下时，只有 root 一层。
- 测试抓不到的：单个 worker 的检查漏了开销（写成 `worker.tokens > budget`）时，101 的 huge 会一路走到“这一层切不动”那条错误。参考答案那条消息不带名字，测试会挂；如果候选人的那条消息列出了这一层所有成员的名字，测试也能过。看到要追问开销算在哪里。

追问：
- "Greedy in order versus balanced groups?"（贪心可预测、稳定，加一个专家只影响后面的组；平衡分组更省层数，但一改就全变）
- "A team's description grows as it gets members. What changes?"（team_tokens 不再是常数，要先定成员再算父级成本，可能要迭代）
- "When would you refuse to build a hierarchy at all?"（课里 Anthropic 的顺序：单 agent 加 workflow 先行；2–4 个专家用 supervisor；只有监督者的上下文预算真的放不下才上层级）

### Part 4 工具调用式监督（目标 13 分钟）

坑：
- 输出格式由测试决定：每个请求是 JSON-RPC 2.0 对象，`"jsonrpc"` 是字符串 `"2.0"`，id 从 1 开始，`params` 里只有 `instruction` 和 `context`。
- `context` 不多不少：只给 views 里列出的字段；case 里没有的字段不出现，不能写成 null；sales 看不到卡号。
- 回复乱序，要按 id 对回调用，不能按发送顺序配对；`call_id` 也要用回复里的 id，不能按到达顺序编号。
- 没有 id 的帧是通知，跳过。直接取 `message["id"]` 会 KeyError。
- 带 `error` 的回复变成 ok=False 的结果，内容是 `error["message"]`，不抛异常。
- 所有请求先发完，再等回复。发一个等一个会被假专家池拦下来：`send every tool call before waiting for a reply`。
- 回复到一个就 yield 一个。测试拿第一个结果时数 `receive()` 被调用了几次。
- 每个调用都收到回复后就不再读了，多读一次会被假专家池拦下。
- views 里没有的专家，要在发出任何请求之前报 ValueError。
- 测试不拦、可以接受的写法：用 `asyncio.gather` 一起发请求；按 `"method" in message` 认通知；context 按 case 的顺序取字段（JSON 对象不讲顺序，测试比较的是解析后的 dict）；开一个后台任务读回复、放进队列，只要生成器关闭时把它取消。不取消的话，调用方 `aclose()` 以后它还在读，测试数到的 `receive()` 就不止 2 次。

追问：
- "Why do supervision through tool calls instead of a supervisor library?"（课里 2026 年 LangChain 的建议：自己控制每个专家看到的上下文）
- "A specialist never answers. What happens to supervise?"（会一直等；需要每个调用的超时、取消，超时也变成一个失败结果）
- "Where would you enforce the views: in the supervisor or in the specialist?"（两边都要；监督者这边是允许清单，专家那边还要校验，审计里记下发出去的字段）

### Part 5 层级路由回溯（目标 13 分钟）

坑：
- 回溯：走进死路要退回上一层，换下一个匹配的成员，每退一次记一次 backtrack。根走不通时没有上一层，不算 backtrack。只试第一个匹配的成员、走不通就结束，发票那个任务会直接 unresolved。
- trace 每次向团队要选择都写一行，什么都没选出的那次也写（`  billing -> none`）。只在选中成员时才写，发票任务只剩 5 行。测试先数行数：应该等于 ops 减去 worker 接手的那一次，8 行；接手的 worker 不写，退回也不单独写一行。选中和没选中共用一个 `f"{team} -> {pick}"`，空选择会写成 `-> None`。
- 退回之后的那次选择要在行末写明从哪个团队退回，什么都没选出也一样：`desk -> support, back from billing`、`  support -> none, back from accounts`。漏写，只写在选中成员的行上，或者写到死路那一行（`billing -> none, back to desk`），都对不上。写在死路那一行还有一个问题：那一刻还不知道上一层会不会因为回溯上限而放弃。
- 缩进按路径上它上面有几个团队算，每个两个空格，根不缩进。死路的团队弹出以后，下一行要回到上一层的缩进。用一个进团队就加一、走空了不减的深度计数，billing 走空以后 desk 的下一行会多缩进两格，死路那一层还留在 trace 里。死路已经从 path 里弹出时，直接用 `len(path) - 1` 算缩进最省事。
- 没走通的任务也带着 trace：上限 2 时是发票任务 trace 的前 6 行，根走不通时只有 `desk -> none`。照着 path 把它写成空的，测试会挂。Route 比较时不看 trace，测试单独逐行比 trace。
- 已经走空的团队不再提供、也不再进入，即使它还挂在另一个团队下面。测试里 accounts 同时在 support 和 commercial 下面，commercial 直接跳过它去选 quotes，跳过不花 op，也不写 trace。先把它选出来、再发现走空过而跳过，会多算 1 次 op（10 次）。
- ops 要精确：每次向团队要一个选择都算 1 次，包括什么都选不出的那次，worker 接手再加 1 次。发票那个任务是 9 次。
- 回溯上限：需要第 max_backtracks + 1 次回溯时放弃，backtracks 报已经做过的次数。上限 3 时发票任务正好成功，上限 2 时失败并报 2 次；`>=` 写错会让上限 3 也失败，先加一再比较会在上限 2 时报成 3 次。
- 走空的记录只管这一个任务。放在模块级或者默认参数里跨任务共用，第二次问发票任务时 billing 和 support 已经被当成走空，结果不对。trace 也一样：共用一个列表，后一个任务会带着前一个任务的行。
- 死路的团队要从 path 里弹出去。
- 一个团队在自己的路径上再次出现要报 ValueError，不处理会 RecursionError。
- 多个成员都匹配时按声明顺序选。
- 分词已经给了：`tokenize` 按字母、数字、下划线切词并转小写，整词匹配只是顺带检查。不用它、自己写子串匹配，“debugger” 会命中 bug（课里 `classify` 的 `"bug" in t` 就是子串匹配）；用 `split()` 按空白切，“Quote,” 带着逗号，匹配不上 quote。

追问：
- "This is CrewAI's Flow side. When would you put an LLM router back in?"（规则覆盖不了的长尾；可以规则先走，走不通再让 LLM 选，或者交给人）
- "Is skipping a failed team always right?"（只有团队的结果不依赖从哪条路径进来时才对；如果父级会给子团队不同的上下文，就不能这样记忆）
- "How is the backtrack cap different from the hop counter on a swarm?"（swarm 的 hop 计数防的是 A→B→A 来回弹；这里防的是一棵大树上的穷举）
- "A capped route and a route nothing fits both come back unresolved. How does the caller tell them apart?"（看 trace 的最后一行：不缩进、是根自己的 `-> none`，说明没有成员合适；缩进在下面某一层，说明回溯用完了。只看 backtracks 不够，正好用完上限以后根也可能走空。生产里可以给 Route 加一个原因字段，课里测验 Q9 的改写也是把放弃明确写进 trace，不让任务被悄悄丢掉）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出并发写、超时、上下文控制、何时不用多 agent |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
