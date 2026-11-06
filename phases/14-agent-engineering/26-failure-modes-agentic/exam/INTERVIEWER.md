# 面试官手册：FailTag（14/26）

候选人计时期间不要看。候选人手里只有 README、`failtag/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 题目里没有真的 agent 和 LLM。trace 是测试里手写的数据，`${N}` 表示“用了第 N 步的结果”；时钟是测试注入的函数。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | "updates"、"edited" 这类变形算写入动词吗？ | "No. Whole words from the list only. Say how you'd widen it." |
| 1 | 级联要不要算间接用到失败结果的调用？ | "Not here. Direct consumers only. The transitive version is Part 5." |
| 1 | message 步引用了失败结果，算下游调用吗？ | "No. Only tool calls count here. Part 5 counts messages in the radius." |
| 1 | "do not exceed 5 searches" 这种约束怎么办？ | "It isn't a tool rule. Ignore it." |
| 1 | 路径要不要规范化，比如 ./src/a.py？ | "No. Plain prefix match on the path argument." |
| 2 | trace id 里可能有什么字符？ | "Anything. They come from the runtime. And they're case-sensitive." |
| 2 | 临时文件放在哪？ | "Next to the file it replaces, so the rename stays on one filesystem." |
| 2 | 基线能引用还没存的 trace 吗？ | "No. ValueError, and keep the old baseline." |
| 2 | 同一个 tid 再存一次呢？ | "It replaces the old copy. We re-tag traces." |
| 3 | 还没有基线时 check 返回什么？ | "Raise LookupError. We can't say it's getting worse without a last-known-good." |
| 3 | 某个模式变少了要告警吗？ | "No. Only getting worse pages." |
| 3 | 被压下去的告警算不算一次告警？ | "No. The cooldown counts from the last page that went out." |
| 3 | 正好 5% 呢？ | "Fails the build. At least 5%." |
| 3 | check 之后基线要不要跟着更新？ | "Never. Only confirm moves it." |
| 4 | 时间戳用哪个时区？ | "UTC, with a Z and milliseconds." |
| 4 | 同一步同时触发两种模式，先报哪个？ | "DETECTORS order." |
| 4 | 结束后的 trace 状态要保留吗？ | "No. Drop it at End." |
| 4 | Start 之前就来了 Step？ | "Won't happen in the tests. Failing loudly is fine." |
| 5 | message 步算进半径吗？ | "Yes. It's an affected step. It just doesn't touch a system." |
| 5 | 引用了后面的步骤或者不存在的步骤？ | "Malformed trace. ValueError." |
| 5 | 根因自己的系统算不算？ | "No. Only the systems downstream of it." |
| 5 | 一个失败的结果没有任何步骤用到，还要报吗？ | "Yes. It's still a root cause: radius 0, depth 0, no systems." |

## 每关：要看什么、提示、追问

### Part 1 修检测器（目标 12 分钟）

一个测试里叠了 4 个缺陷和 3 个护栏：

1. `mentions` 用 `re.search(verb, ...)` 做子串匹配。"summarize the credit memo" 里的 credit 含有 edit，于是这次写文件被当成用户要求的，scope creep 漏报。课里 `detect_scope_creep` 的 `w in request` 是同一个问题。
2. `parse_constraint` 遇到 VERB_TOOLS 里没有的动词（"do not exceed 5 searches"），没有返回 None，而是返回 `Rule(tools=None)`。错误不在这里报出来，而是两层之后，`violates` 里的 `step.name not in rule.tools` 报 TypeError。
3. `detect_cascading_errors` 把失败之后所有带引用的调用都算成下游，哪怕它们引用的是别的步骤。docstring 要求只算引用了失败步骤本身的调用。课里的版本更宽，失败之后的任何调用都算。
4. 改对第 3 处以后，每个失败步都把后面所有步骤的 `references()` 重新算一遍，是 O(S²)。4000 步在本机要 1.2 到 1.6 秒。
5. 护栏：按词匹配必须忽略大小写和标点（"Edit the README."、"then SAVE."），而且两边都是词边界："list the saved searches" 里的 saved 不是 save。只用 `split()`、没转小写、只在前面加 `\b`、用 `startswith`，都会挂。
6. 护栏：第 2 处要修在 `parse_constraint`。只在 `violates` 或 `detect_context_loss` 里绕开 `Rule(tools=None)`，tag 也能通过，但测试接着直接检查 `parse_constraint` 对未知动词返回 None。
7. 护栏：提速时只看后面几十步的窗口会漏掉远处的消费者；按 `${N}` 出现次数计数会把“一次调用用了两次”算成两个消费者。改成一遍计数时，只数 tool call，并且按失败步分别计数："look up both invoices" 那条里两个失败步各被一个调用用到，message 也引用了它们，把 message 算进去或者把所有失败步的消费者加在一起，都会误报级联。

测试抓不到的：只把每一步的 `references()` 缓存起来、仍然对每个失败步扫一遍后面所有步骤，还是 O(S²)，但只剩集合查找，本机 40 到 130 毫秒，机器空闲时能过 0.12 秒的限值，忙的时候会挂。看到这种写法要追问复杂度，并让候选人改成一遍计数。

看什么：是不是先读 traceback、顺着 `rule.tools` 为什么是 None 往上找；是不是先 `print` 出被误判的 trace 看实际数据；每改一处就重跑。

提示：
- H1："Which detector disagrees with its docstring, and on what input?"
- H2："What does parse_constraint return for a verb it doesn't know?"
- H3：直接指出 `re.search(verb, request)` 会在 credit 里找到 edit。

追问：
- "Word matching still misses 'updated' and fires on 'don't edit'. What would you do in production?"（同义词表、否定识别，或者干脆用分类器；按词匹配只是便宜的第一道）
- "Why does the lesson say tagging only crashes is not enough?"（大多数失败的输出看起来是正常的，要看内容）

### Part 2 trace 存储与基线（目标 11 分钟）

坑：
- tid 直接当文件名，"run/7\n" 会变成子目录，写的时候报 FileNotFoundError。
- 用百分号编码当文件名，在 macOS 和 Windows 默认的大小写不敏感文件系统上，"T001" 和 "t001" 会写进同一个文件。用 tid 的 sha256 做文件名，tid 本身存在文件里。（在 Linux 上百分号编码能过，这个坑只在本机这类文件系统上暴露。）
- 读回时 steps 要还原成 TraceStep，留成 dict 比较不相等。标签列表保持原顺序，不能排序或转成 set。
- `tids()` 要按 tid 排序，不是按文件名排序。
- 没设过基线时 `baseline()` 返回 None，不能抛 FileNotFoundError。
- 基线要原子替换：同目录临时文件，写完 `os.replace`。直接写文件的话，测试把 `os.replace` 换成报错函数时不会报错。替换失败时要删掉临时文件。
- 基线里有没存过的 tid 要报 ValueError，而且要先检查再写。先写后查的话，被拒的基线已经落盘了。
- BASELINE 一行一个 tid 的话，结尾带换行的 tid "run/7\n" 读回来会少掉换行（`splitlines`）或者多出一个空串（`split("\n")`）。基线也存成 JSON 列表。
- 测试抓不到的：`tempfile.mkstemp()` 不带 `dir`，临时文件落在系统临时目录。本机 /tmp 和测试目录在同一个文件系统上，`os.replace` 照样成功；换到跨文件系统的部署就会失败。看到要追问。

追问：
- "Why does the temp file have to be in the same directory?"（跨文件系统的 rename 不是原子的，`os.replace` 会直接失败）
- "A crash between writing the temp file and the rename?"（旧基线还在，只留下一个临时文件；启动时清理以 .tmp- 开头的文件）
- "A million traces in one directory?"（按哈希前两位分子目录；或者换成数据库）

### Part 3 漂移与构建闸门（目标 13 分钟）

坑：
- 占比的分母是全部 trace，包括没有标签的。同一个 trace 里重复的标签只算一次。
- 闸门是“至少”：1/20 正好 5% 要失败。写成 `count >= threshold * n` 时，0.07 × 200 = 14.000000000000002，14 个就不算失败了。用 `count / n >= threshold`。
- 没有基线要报 LookupError。当成全 0 会让所有模式都告警。
- 基线冻结，只有 `confirm` 能改。每次 check 都把当前窗口当新基线的话，4% → 8% → 12% 每一步都在容差内，慢慢变坏永远不告警。
- 只有变坏才告警。用 `abs` 的话，context_loss 从 40% 降到 0 也会告警。
- 漂移是“比基线高出超过 tolerance”。1/20 = 0.05 对基线 0，正好等于 tolerance，不告警；写成 `>=` 会挂。
- 冷却按模式分开计时，从上一次真正发出的告警算起。被压下去的那次不能重新开始计时；每次真正发出都要更新时间，只在第一次记（`setdefault`）的话，1700 发完以后 2000 又会发；正好过了 cooldown_s 要能再发。
- 告警按模式排序。f 窗口里先出现 tool_misuse、后出现 context_loss，按首次出现的顺序输出会挂。
- 少于 min_traces 不下结论，正好 min_traces 要下结论。
- 最后一段是端到端：课里的 7 条 trace 经过 Part 1 打标、Part 2 存储，确认成基线；再来 7 条同时 scope creep 和 context loss 的 trace，必须告出这两种模式。

追问：
- "How would you pick tolerance and min_traces?"（按基线占比的二项分布算置信区间，样本少时容差要放宽）
- "The lesson says cluster and rate-limit. What would you cluster on besides the mode?"（工具名、出错的系统、用户请求的意图；课里说 Phoenix 在生产环境里做的就是这种 trace 聚类）
- "When is it safe to call confirm?"（人看过、或者一段时间内没有事故、并且和发布版本绑定）

### Part 4 在线 syslog（目标 13 分钟）

坑：
- 每个 trace 的状态要分开：已经报过的模式、失败步、消费者计数、步号都按 tid 存。测试里 a、odd、c 三个 trace 交错到达。共用一个已报集合，trace c 的 scope_creep 会被 trace a 吞掉；共用一个集合、每次 Start 时清空，a 在 c 开始之后的那次写入会把 scope_creep 和 context_loss 再报一遍；失败步和计数不分 trace，a 第 2 步里的 `${1}` 会被算成 odd 那个失败步的第二个消费者；步号不分 trace，odd 的 `${1}` 就对不上它自己失败的那一步，级联报不出来。
- 同一个 trace 同一种模式只报一次。a 的第 2 步写文件没带 content，要报 tool_misuse，同一步再次触发的 scope_creep 和 context_loss 不再报。已报集合要跨步保留，只在一步之内去重挡不住这两条。反过来，一步只报一条也不对：a 的第 1 步要按 DETECTORS 顺序报出 scope_creep 和 context_loss 两条。
- success_hallucination 只能在 End 判定，只带 tid，不带 step 和 tool。动词表是 SUCCESS_VERBS，比 WRITE_VERBS 多一个 make：odd 的请求是 "make a README"，用 WRITE_VERBS 会漏报。End 时只清掉状态、不做判定，也会漏报。
- PRI 是 FACILITY × 8 + SEVERITY[mode]，facility 16 是 local0，测试里的 PRI 是 130 到 132。写成两者相加、乘错一边（severity × 8 + facility），或者把两个数字拼成 163，都会挂。
- 输出格式由测试的解析代码决定：每条一行 RFC 5424，结尾一个换行。
- 时间戳是 UTC、带毫秒和 Z。用不带时区的 `datetime.fromtimestamp(t)` 得到的是本机时间：本机不在 UTC 时测试会抓住，在 UTC 的机器上抓不住。
- 级联和 Part 1 一样按失败步分别计数，只算 tool call。quiet 那条 trace 的两个失败步各被一个调用用到，message 也引用了它们，不能有任何输出。
- 能在某一步判定的模式要在那一步立刻输出。测试用探针数拉取了几个事件，先收集再统一输出会挂。
- 顺带检查：结构化数据参数值的转义顺序写在 docstring 里，先转义反斜杠，再转义 `"` 和 `]`。tid `b"]\` 和工具名 `magic"scan]` 用来确认照做了：只转义引号、先转义引号、漏掉 `]`，或者用 `json.dumps`（它不转义 `]`），整行都会解析失败。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要会看出来这里需要 async generator。
- 可以接受的写法：每来一步就把目前为止的步骤拼成 Trace，再跑一遍 tag()，只报新出现的模式。结果和逐步判定一样，只是每一步都是 O(S)，可以追问长 trace 上的代价。

追问：
- "Why RFC 5424 structured data instead of free text?"（下游可以按 tid、mode 过滤和聚合，不用解析自然语言）
- "Should the online tagger stop the agent?"（可以：hallucinated_action、context_loss 这类在执行前就能拦，就是课里说的 gates at every step；要区分告警和阻断）
- "A trace never sends End?"（按最后活动时间过期，清掉状态，报一条超时）

### Part 5 级联半径（目标 11 分钟）

坑：
- 根因是不受任何其他失败影响的失败。只看直接父节点是否失败不够：测试里 email.send 的失败是隔着一个成功步骤传下来的。
- depth 是最长链，不是 BFS 的最短跳数。shipping.create 同时用到第 1 步和第 2 步的结果，最短 2 跳，最长 3 跳。
- 一个下游被两个根因影响时，两个根因都要算上它。
- 影响要穿过下游的失败步继续传：relay 里 email.send 只能经过失败的 payments.refund 到达，遇到失败步就停，第 1 步的半径会少算一个。结果没人用到的失败也是根因，radius 和 depth 都是 0，systems 为空；只报有下游的根因会漏掉 relay 的第 0 步。
- message 步算进半径，但不算系统。
- 引用自己、后面的步骤或者不存在的步骤要报 ValueError，没有失败步的 trace 也要检查。
- 顺带覆盖的边界：菱形依赖里同一个下游只算一次，用已访问集合做遍历自然就对；按边数或路径条数计数会多算。3000 步的长链，递归 DFS 会 RecursionError；步骤下标本身就是拓扑序，按下标顺序做一遍就能算出最长路径。

追问：
- "How would you use the radius in alerting?"（半径或系统数大的先处理；课里说 cascading is the killer）
- "How do you stop a cascade at run time?"（失败结果不能被下游当成正常值使用；工具返回错误时要么重试，要么停下问人）
- "The same failure fans out across services in production. Where does the DAG come from?"（trace 的 span 父子关系加上参数里的结果引用；前提是各个服务共用同一个 trace id）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出误报、原子写入、基线管理、告警疲劳、阻断时机 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
