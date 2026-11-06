# 面试官手册：Handoffs（14/16）

候选人计时期间不要看。候选人手里只有 README、`handoffs/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 告诉候选人：每个 agent 的模型是测试里的普通函数（`Model`），不联网，也不要去改测试里的替身。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 工具返回 dict 时，模型读到什么？ | "JSON text, and the same for any other result that isn't a string. A string result goes through as it is." |
| 1 | 交接以后，目标 agent 能看到 session 里更早的消息吗？ | "Yes. It reads everything the previous agent read, plus the handoff." |
| 1 | 输出护栏用谁的？ | "The agent that gives the final answer. Not the first agent, and not every agent on the way." |
| 1 | 工具调用算不算 max_handoffs？ | "No. Only handoffs count. max_turns bounds the model calls." |
| 1 | 超限的那一次交接要不要记进 trace？ | "Your call. The tests only check that the run raises HandoffLimitExceeded." |
| 1 | agent 回答了空字符串，算不算 drift？ | "No. An empty answer is still an answer." |
| 1 | PII 规则能合成一个大正则吗？ | "Only if the reason still names the first rule, in rule order." |
| 2 | session id 是什么格式？ | "Any string. We key sessions by the customer's email, so expect quotes in them." |
| 2 | session id 能不能先把引号去掉再用？ | "No. o'brien@example.com and obrien@example.com are two customers." |
| 2 | 用户把同一句话说了两遍，要存两条吗？ | "Yes. Every item the runner adds is its own item, repeats included." |
| 2 | add_items 里混进一个不是 item 的东西呢？ | "Raise TypeError and store none of the batch." |
| 2 | limit=0 返回什么？ | "No items." |
| 2 | 空 session 上 pop_item 呢？ | "Return None." |
| 2 | 要支持多个进程同时写吗？ | "Not today. Tell me what you would do." |
| 2 | HistorySummary 要能存吗？ | "No. A session holds the four item types. The runner never stores a summary." |
| 3 | 最新用户消息之后的工具调用和交接要不要折叠？ | "No. The latest user message and everything after it stay as they are." |
| 3 | 前面已经有一个摘要了怎么办？ | "Carry its lines over as they are. Never summarize a summary." |
| 3 | 前面什么都没有时，要放一个空摘要吗？ | "No summary at all." |
| 3 | 参数写成什么样的 JSON？ | "Like the example in the docstring. The tests only use ASCII arguments." |
| 3 | 折叠会改 session 里存的东西吗？ | "No. Nesting only changes what the next agent reads." |
| 3 | max_handoffs 是每个 run 还是整段对话？ | "Per run." |
| 4 | processor 自己抛异常怎么办？ | "The tests don't cover it. What would you do?" |
| 4 | NDJSON 里要不要时间戳？ | "Not today. The six fields in the docstring." |
| 4 | 队列满了丢新的还是丢旧的？ | "The new one. Spans that are already waiting keep their place." |
| 4 | 正在交给慢 processor 的那个 span 算不算进 max_queue？ | "No. Only the ones waiting." |
| 4 | shutdown 要等吗？ | "Yes. It returns once every queued span has been handed over." |
| 4 | 能不能每个 trace 结束时再一起导出？ | "No. Each span goes out as it ends." |
| 5 | 不在 agents 列表里、但被 handoff 指到的 agent 算不算？ | "Yes. It's part of the graph." |
| 5 | 两个同名的 agent 呢？ | "ValueError, wherever the second one turns up." |
| 5 | 两条一样短的路径怎么比？ | "Compare the chains name by name from the entry, the way Python compares lists." |
| 5 | path_to_tool 算不算内置工具？ | "Yes. Any tool the agent has." |
| 5 | 入口 agent 自己没有输出护栏要报吗？ | "Yes. Any agent a run can reach may give the final answer." |

## 每关：要看什么、提示、追问

### Part 1 修 runner（目标 12 分钟）

一个测试里叠了 5 个缺陷和几个护栏：

1. `_call_tool` 把工具的原始结果直接返回。`lookup_customer` 返回 dict，错误不在 `_call_tool` 报，而是在 `tracing.preview` 里报 `AttributeError: 'dict' object has no attribute 'split'`。docstring 写的是：字符串原样，其他结果转成 JSON。只把 `preview` 改成能吃任何类型，报错没了，模型拿到的却还是 dict，下一条断言会抓住；`str()` 得到的是 Python 的 repr，不是 JSON；所有结果都 `json.dumps` 会给字符串结果加上引号；只给 dict（或 dict 和 list）做 `json.dumps`、其余用 `str()`，`open_tickets` 返回的元组 `(77,)` 会变成 `"(77,)"`，JSON 应该是 `"[77]"`。
2. 不折叠时，交接分支把 `state.view` 换成了 `[state.request]`，目标 agent 只看到用户这一句：看不到 session 里更早的消息，看不到 triage 的查询结果，也看不到交接本身。billing 于是回答 “Which customer is this about?”。课里说 handoff 要 copy the conversation context。改成 `list(state.new_items)` 会丢掉 session 里更早的消息，同样会被抓住。
3. 输出护栏取的是 `agent`（入口 agent），不是 `current`。triage 的 60 字上限拦下了 billing 69 个字的回答，报 `OutputGuardrailTripwireTriggered: length_cap_60`。课里说输出护栏只在最后一个 agent 上运行。把一路上所有 agent 的护栏都跑一遍，会被同一个上限拦下；干脆不跑输出护栏，卡号就漏出去了（DID NOT RAISE）。
4. agent 循环是 `for _ in range(self.max_handoffs + 1)`，最后一个 agent 还要交接时循环自然结束：final 还是空串，输出护栏对空串放行，run 返回 `""`。这就是测验 Q6 的现象。修法是 `for ... else: raise HandoffLimitExceeded`。护栏：
   - 恰好 max_handoffs 次交接要能成功（抓差一）。
   - 一条不回头、但超过上限的链要报错。只检查“交回之前的 agent”的写法能拦住乒乓，拦不住这一条。
   - agent 回答空串不是 drift。按 `final == ""` 判超限，正是测验 Q9 说的“分不清空回答和交接循环”。
   - 3 次工具调用加 1 次交接、max_handoffs=1 要能成功。照课里的循环把每次模型调用都算进 hop，会在这里挂掉。
5. 计时：`PiiGuard` 把规则存成字符串，每次检查都对每条规则调用 `re.search(pattern, text)`。re 模块只缓存 512 个编译好的模式，600 条规则轮着用，每次都不命中，每次检查都要编译 600 个模式。120 次 run 约 1.3 秒，在 `__init__` 里编译一次约 5 毫秒。用 `functools.lru_cache(maxsize=128)` 会同样地反复失效；在 `check` 里每次调用 `re.compile` 也一样慢，它查的是同一个缓存。换成编译好的对象时把 `search` 写成 `match` 也不对：`match` 只从文本开头匹配，ID 号不在开头，护栏就放行了（DID NOT RAISE）。把规则合成一个大的交替正则很快，但正则取的是文本里最靠左的匹配，reason 会写成 `de_national_id`，而按规则顺序第一条命中的是 `at_passport`。

看什么：是不是先读 traceback、顺着调用链往上游找；是不是打印模型实际收到的 `request.conversation`；有没有对照 Runner 的 docstring 一条条核对；计时那一层有没有先 profile 再动手。

提示：
- 第 1 层：H1 "Which function first got something it didn't expect?" H2 "What does lookup_customer return, and what should the model read?" H3 直接指出 `_call_tool` 的 docstring。
- 第 2 层：H1 "Print the conversation billing's model was given." H2 "What does the lesson say a handoff does with the conversation?"
- 第 3 层：H1 "Whose guardrail tripped?" H2 "Which agent gave the final answer?"
- 第 4 层：H1 "What does run return when the agents keep handing off?" H2 "Where would HandoffLimitExceeded come from?"
- 第 5 层：H1 "Profile one run. Where does the time go?"（cProfile 里是 `re._compile`）H2 "How many compiled patterns does the re module keep?"

追问：
- "Why is a handoff a tool and not a separate control-flow API?"（模型本来就擅长从工具列表里选一个；工具描述告诉模型什么时候转交；trace 里和工具调用一样有 span。课里说这是把 supervisor 模式产品化）
- "This guardrail runs before the first model call. When would you run it in parallel instead?"（课里的两种模式：并行尾延迟低，触发时主调用的 token 白花；阻塞先检查，不浪费 token）
- "Why does the starter only get slow past 512 rules?"（re 模块的缓存上限。开发时 50 条规则一切正常，上线后规则一多才掉下去）
- "One Runner serves two threads. What must not live on it?"（每次 run 的状态：trace、计数器。测验 Q12）

### Part 2 SQLite 会话库（目标 12 分钟）

坑：
- 重复的消息要保留。“Danke!” 出现了两次，就是两条 item。加 UNIQUE 再 `INSERT OR IGNORE` 会丢一条；`INSERT OR REPLACE` 会删掉前一条，只留下后面那条。`pop_item` 要按 seq 删最新的那一行：按内容删会把两条 “Danke!” 都删掉；按内容找到一行再删，找到的是旧的那条。
- limit 是最新的 N 条，按从旧到新排。`ORDER BY seq LIMIT ?` 取到的是最旧的；`ORDER BY seq DESC LIMIT ?` 不倒回来是从新到旧。按 session 过滤要和 LIMIT 写在同一层查询里：在子查询里先对全表取最新的 N 条、外面再过滤，别的会话的消息插在 jorg 的两批中间，jorg 就只剩 3 条。
- session id 是邮箱，里面有引号：`o'brien@example.com`，还有本地部分带双引号的 `"ann lee"@example.com`。拼进 SQL 文本会报语法错误；用反斜杠转义也一样，SQL 不认 `\'`；改用双引号包起来，o'brien 能过（SQLite 找不到同名的列，就把双引号里的内容当成字符串），`"ann lee"@example.com` 照样报错；把引号去掉的话，o'brien 就和另一位客户 `obrien@example.com` 共用一个会话。每条 SQL 都要用参数：测试对 o'brien 调用了 `add_items`、`get_items`（带和不带 limit）、`pop_item` 和 `clear_session`，哪一条用单引号拼了字符串都会报错。
- 顺带检查：工具参数的存法写在类的 docstring 里（`json.dumps` 按插入顺序写、不排序键，`json.loads` 读回）。`exact()` 照样比较未排序的嵌套键、`0.1 + 0.2`、`2**64 + 1`、结尾带换行的工具输出和读回的 item 类型：`sort_keys=True`、读回普通 dict 或者建错了类、存的时候 strip 文本，都会被抓住；把参数拆进列的话，`2**64 + 1` 放不进 INTEGER。
- 顺带检查：`limit=0` 返回空列表。`rows[-limit:]` 在 0 时返回全部，`if limit:` 把 0 当成没给 limit 也一样。
- `add_items` 要么全存要么都不存。在逐条循环里校验、每条一个事务的话，“One more thing.” 会留下来。先全部校验和序列化，再在一个事务里插入。
- `pop_item` 取的是本 session 最新的一条（不是全表最新的一条），要返回它，空 session 返回 None。
- `clear_session` 只清自己，而且清空要持久：测试关掉连接再重开，清掉的 session 必须还是空的。
- HistorySummary 不是 session item（docstring 只列了四种），`add_items` 收到它应当报 TypeError。测试不检查这一点，候选人问到时按澄清问题回答。
- 顺带的现象，不是这一关的重点：`add_items` 或 `pop_item` 写完不提交的话，另一个连接写同一个文件时要等 sqlite3 默认的 5 秒超时，才报 `database is locked`。候选人看到测试卡住几秒再报错时，可以提示去看事务。
- 测试抓不住的：自己把单引号写成两个、再拼进 SQL 文本也能过；只在 `pop_item`、带 limit 的查询或 `clear_session` 里用双引号拼接，测试也碰不到（`"ann lee"@example.com` 只走 `add_items` 和 `get_items`）。看到拼接就问为什么不用参数：每个值都得记着转义，漏一处就是注入。
- 最后一段接上 runner：runner 先读 `get_items()`，成功后再写回新的 item，关掉重开以后对话照样接得上。这一段用的 agent 不碰 Part 1 的缺陷，所以 Part 1 没修完也能做这一关。

提示：
- 重复：H1 "How many times did the customer say Danke!, and how many rows came back?" H2 "Which rows does your DELETE match?"
- limit：H1 "Which query gives you the latest four, and in what order?" H2 "Does the LIMIT see other sessions' rows?"
- 引号：H1 "Print the SQL text that runs for o'brien." H2 "How does sqlite3 take a value without putting it in the SQL text?"
- exact()：H1 "What does exact() compare that == doesn't?" H2 "What does the class docstring say about tool arguments?"
- 原子性：H1 "What happens to the first row when the second item raises?"

追问：
- "Why keep the arguments' key order at all?"（重放的是模型自己写的参数；提示词逐字节不变，provider 的提示缓存才命中；调试时看到的就是当时的样子）
- "The runner retries add_items after a timeout. How do you avoid storing a run twice without dropping a repeated Danke!?"（去重靠写入方给的幂等键，比如 run id 加序号，在这个键上加 UNIQUE；不能按内容去重，用户真的会把一句话说两遍）
- "Would you keep SQLite in production?"（课里的 scaffold：默认 SQLite，生产用 Redis。多台应用服务器要共享存储，同一个 session 的并发写要加锁或者按序号追加）
- "A session grows to 10,000 items. What does the next run cost?"（每次 run 都要全读一遍；用 `get_items(limit)`、`nest_handoff_history` 或者做摘要）

### Part 3 交接折叠（目标 10 分钟）

坑：
- 位置和条数：[摘要, 最新的用户消息, 它之后的全部]。摘要放到用户消息后面，把用户消息也折进摘要（于是出现两次），或者除了用户消息全都折叠（这一轮的查询结果就进了摘要），都不对。
- 要找的是最新的用户消息，不是第一条：`starts[0]` 会原样返回整段对话；`conversation.index(msg)` 找到的是第一条内容相同的 “Thanks!”。
- 前面什么都没有时不放摘要，空的 HistorySummary 也不行。
- 已有摘要的行原样带过来，放在最前面。把它再折成一行，`nest(nest(x)) == nest(x)` 就不成立了，同一个 run 里的第二次折叠交接也会对不上。
- 传进来的列表不能改（原地切片赋值会被抓住）。
- 每种 item 的写法在 docstring 里，参数写成 JSON（`str()` 得到的 `{'order': 9001}` 不对）。回答那一行开头是 agent 的名字（`support: ...`），不是 `assistant:`；工具那一行要带上 `-> 输出`。
- runner 那边：交接上限按 run 算。把整段对话（包括 session 里的历史）里的 HandoffItem 都算上，第二次 run 唯一的一次交接就会被拒；把计数器放在 Runner 上、每次 run 不清零也一样（测验 Q12：每次 run 的状态不能放在 Runner 上）。Part 1 抓不住这种写法：那里反复使用的 Runner 上限是 3，一共只交接了两次。
- runner 折叠的是当前 agent 读到的整段视图，不是这次 run 的新 item：只折 `new_items`，第二次 run 的摘要就没了。session 里存的是全部 item；把最后一个 agent 读到的视图写回 session，摘要就进了 session。

追问：
- "Copy or nest: what does billing lose with the summary?"（测验 Q17：订单号、用户的原话这类细节。所以工具那一行保留参数，最新的用户消息原样保留。课里把 `nest_handoff_history` 标成 beta）
- "Would you write the summary with an LLM instead of one line per item?"（更短，但要多一次调用，可能丢事实，结果也不确定）
- "Two specialists keep handing back and forth with nesting on. What do they see?"（摘要里多出它们自己的交接行；拦住它们的仍然是 hop 计数器）

### Part 4 trace processor（目标 14 分钟）

坑：
- 在 span 结束时分发，不是开始时（探针看到 1 到 5 而不是 2 和 4），也不是 run 结束时（探针什么都看不到）。探针在工具调用中途从磁盘读文件：不 flush 的话，几行都还在 8 KB 的缓冲区里。
- run 中途加进来的 processor 要收到之后结束的每个 span。每个 trace 开始时把 processor 列表拷一份，就收不到了；每个 span 开始时拷一份也不行：工具 span（5）、triage 的 agent span（3）和 run span（1）都是在它加入之前开始的，会被漏掉。
- 一个 span 一行 JSON。缩进输出会让读文件的代码在工具里报 JSONDecodeError，把换行写在记录前面也一样（第一行成了空行）；少了 trace_id，整份记录对不上。
- 顺序是结束的顺序：子 span 在父 span 前面，run 在最后。分发放在 `Trace.end` 里，这一点自然满足。
- 被护栏拦下的 run 也要导出它的 span。现成的 `Trace.span` 在 finally 里结束 span，并记下异常类名；改成只有块正常结束才分发，run 那个 span 就没了。
- 每个 span 按加入的顺序依次交给各个 processor（first、second、first、second……），倒过来就错。
- BackgroundProcessor 的 `on_span_end` 不能等：
  - 直接调用慢 processor，或者用 `queue.put()`，run 都会被卡住约 1 秒；`put(timeout=0.02)` 丢 6 个就是 120 毫秒，同样超过 0.1 秒的上限。超时再短一些（比如 10 毫秒，6 个共 60 毫秒）就能过计时断言，但 run 还是在等后端，看到 `put(timeout=...)` 就追问。
  - 不设上限就不会丢；只把 dropped 加一、span 照样排进队列，慢 processor 最后会收到全部 span。
  - 正在交出的那个 span 不算进 max_queue（`maxsize - 1` 会丢 7 个，多留一格的 `maxsize + 1` 只丢 5 个）。
  - 丢新来的，不丢已经在排队的。
  - 先进先出（LifoQueue 不对）。
  - shutdown 要等到排队的 span 全部交出：不 join 就返回，或者让 worker 在清空队列前就看到停止标志，都会被抓住。
  - 测试抓不住的两种 shutdown：`self._worker.join(timeout=...)` 不发停止信号也能过，因为闸门一开，剩下三个 span 一下子就交完了，后端真慢时它会提前返回，要追问；用 `queue.join()` 等、却忘了在 worker 里调用 `task_done()`，shutdown 永远不返回，pytest 会一直卡住，让候选人按 Ctrl-C 看 traceback 停在哪里。

提示：
- H1 "When does the guardrail span reach the file?" H2 "Where does a span end?"
- H1 "What does the run wait for when the backend hangs?" H2 "queue.Queue has a maxsize and put_nowait."

追问：
- "Over-tracing: what in these spans shouldn't go to a third-party backend?"（工具参数里的邮箱、回答原文。课里说内容存在外面，span 里只放 ID，第 23 课讲内容捕获规则）
- "Why drop spans instead of blocking?"（可观测性不能把产品拖垮；丢了要计数、要报警，队列大小按峰值定）
- "The process exits with spans still queued. What do you lose?"（daemon 线程直接死掉；退出前要 shutdown 或 flush，比如注册 atexit）
- "Many runs at once, in threads?"（on_span_end 从多个线程进来，计数要加锁；NDJSON 写文件也要加锁，否则行会交错）

### Part 5 交接图（目标 12 分钟）

坑：
- 只沿 handoff 从入口往下走：archive 会交给 triage，但没有人能到 archive；入口自己算可达（refunds 只能到自己）；自环和环要有 visited，否则递归报 RecursionError。
- 构图时要沿 handoff 把目标也收进来。测试会只传 triage 一个 agent 建图，reachable 仍然要走到同样的 9 个。只用传进来的列表建索引，遍历时会在第一个没收进来的目标上报 KeyError（参考实现的遍历顺序下是 `sales`）；只收一层目标，到第二层同样会断。
- 最短的链，一样短时整条链按名字逐个比：
  - 按 handoff 的列表顺序做 BFS，issue_refund 会选 support → escalations。
  - 每一层按名字排序、保留第一个父节点，export_ledger 会选 support → accounts → ledger。
  - 只比较链的最后一个名字，issue_refund 会选 escalations（e 排在 r 前面）。
  - 用先进先出队列、按名字顺序访问邻居的 BFS 是对的；每一层比较整条链也对。
- 任何工具都算，包括内置工具；要看 agent 的每个工具，不能只看 `tools[0]`；入口自己有这个工具时路径就是 `[entry]`。
- audit：
  - 只报可达的 agent，archive 不能出现。
  - 入口自己的输入护栏会运行，其他 agent 的永远不会（`audit("sales")` 要报 triage 的 pii）。
  - 没有输出护栏的要报，入口也不例外：任何可达的 agent 都可能给出最终回答（`audit("accounts")` 要报 accounts 自己）。只报没有 handoff 的叶子 agent 也不对，accounts 和 support 都有 handoff。
  - 内置工具要单独的策略；function tool 不报。
  - 结果要排序。
- 重名：第二个同名 agent 只作为 handoff 目标出现时也要报错。只检查传进来的列表会漏掉。
- 未知的入口名，`reachable` 和 `path_to_tool` 都报 KeyError；`path_to_tool` 不能因为“到不了”就返回 None。

提示：
- H1 "Write down both shortest chains to issue_refund. Which one comes first?" H2 "When two chains are the same length, what do you compare?"

追问：
- "How would you prevent drift at design time?"（这张图里的环就是 drift 的来源；只允许专家交回 triage，或者干脆没有回边。测验 Q17）
- "The lesson says built-in tools need a separate policy. What would it be?"（在 provider 那边配置白名单：web fetch 的域名、file reader 的路径；或者不给读不可信输入的 agent 这些工具）
- "What if the app had 500 agents?"（BFS 是 O(V+E)；按入口缓存结果；图在部署时算一次）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看模型实际收到的对话、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出护栏模式、hop 上限、提示缓存、重试的幂等键、span 里的敏感内容、背压和丢弃计数、内置工具的策略 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
