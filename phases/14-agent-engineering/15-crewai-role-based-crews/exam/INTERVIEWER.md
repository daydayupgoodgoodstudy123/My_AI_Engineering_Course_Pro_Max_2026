# 面试官手册：CrewFlow（14/15）

候选人计时期间不要看。候选人手里只有 README、`crewflow/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- `crewflow/llm.py` 是模型替身，告诉候选人不要改它。`ScriptedLLM` 按顺序作答，报 `no scripted reply left for call N`，意思是代码调用模型的次数比剧本多；`KeyedLLM` 按收到的输入作答，报 `Unscripted: no reply scripted for ...`，意思是模型收到了剧本里没有的输入。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 没有 context 的任务读什么？ | "The previous task's output. Only the first task reads the topic." |
| 1 | 有 context 的任务还要读上一个任务的输出吗？ | "No. A task with context reads only the tasks it lists." |
| 1 | context 里几个任务的输出按什么顺序拼？ | "The order the context lists them in, not the order the tasks ran." |
| 1 | context 里的任务输出了空字符串呢？ | "Then that's the context. An empty answer is still an answer." |
| 1 | editor 的结构化结果要进长期记忆吗？ | "Only persistent tasks go to long-term memory. The edit task isn't one." |
| 1 | context 引用了后面的任务，什么时候报错？ | "Before any agent runs. A crew that can't run shouldn't spend tokens first." |
| 1 | 可以第一次 recall 时再嵌入吗？ | "Fine, as long as each record is embedded once. The first recall isn't timed." |
| 1 | 一个 topic 有两个监听者，和它们再 emit 的事件谁先跑？ | "First in, first out. Both listeners of the topic run before anything they emit." |
| 2 | 实体名区分大小写吗？要不要去掉首尾空格？ | "Exact names. No case folding, no trimming." |
| 2 | 可以用 shelve 或 pickle 吗？ | "No. Other tools read this file: one key per entity, the value is a JSON object." |
| 2 | 用哪个 dbm 模块？ | "Whatever dbm.open picks on your machine. The tests open the file the same way." |
| 2 | 查一个没记过的实体，报 KeyError 吗？ | "No, it has no facts: an empty dict." |
| 2 | 记一个空的 facts 字典呢？ | "Nothing to store, so don't create the entity. The tests don't cover it." |
| 2 | 事实的值只能是字符串吗？ | "Facts are text. The tests only pass strings." |
| 3 | 三段的规则由 manager 判断，还是 crew 判断？ | "The crew. The manager proposes, the code enforces." |
| 3 | editor 被拒以后谁重做，读什么？ | "The writer, from the researcher's output. Not from its own rejected draft." |
| 3 | 说 done 的那一轮算不算进 max_steps？ | "Yes. max_steps counts rounds, and every round is one manager call." |
| 3 | 被拒的草稿要不要发给 manager？ | "Yes. The manager is sent every output so far, plus the refusal reasons." |
| 3 | carried 按 token 算还是按字符算？ | "Characters. There's no tokenizer here; the growth is what matters." |
| 3 | manager 又挑了一个已经跑过的专家？ | "It runs again. Routing is the manager's call." |
| 3 | Windows 换行的文本怎么数段落？ | "Same rule. A line with only spaces or a carriage return is blank." |
| 4 | 两个步骤几乎同时完成，先输出哪一行？ | "The one that completed first. The tests never make two steps finish together." |
| 4 | 非 ASCII 的值要不要加引号？ | "Either. The parser accepts both. The rules for when you must quote are in the docstring." |
| 4 | 消费者读得慢，Flow 要不要等它？ | "Your call. Say what you chose. The tests don't cover it." |
| 4 | 一个步骤抛异常，其他步骤怎么办？ | "Log the failing step, cancel the ones still running, then raise the step's own exception." |
| 4 | 可以用 TaskGroup 吗？ | "Yes, but the caller must get the step's exception itself, not an ExceptionGroup." |
| 4 | duration_ms 从什么时候算？ | "From when the step starts running. Not from the start of the flow." |
| 5 | 路径里包括根节点吗？ | "No. Paths start at the top-level steps." |
| 5 | 中间节点也有 output，要比吗？ | "Yes. Every node both runs have is compared on its output." |
| 5 | 空字符串和 None 算不算一样？ | "No. A step that returned an empty string is not a step that returned nothing." |
| 5 | 只有坏的那次才有的节点，排在哪？ | "After the good run's nodes at the same level, in the bad run's order. It's in the docstring." |

## 每关：要看什么、提示、追问

### Part 1 修 crew 和 Flow（目标 12 分钟）

一个测试里叠了 4 个缺陷和一个计时问题：

1. `SequentialCrew.kickoff` 把每个任务的输出都写进长期记忆。editor 的输出是 dict（课里练习 5 的 `output_pydantic=Brief`），写进去的时候没事，错误要到两层调用之外才报出来：`recall_long_term` 调 `embed`，在 `text.lower()` 上报 `AttributeError: 'dict' object has no attribute 'lower'`。根因不在 memory.py，是 Pitfalls 里的 “Memory always-on”：只有标了 persistent 的任务才该写。
2. 上游输出按任务在 crew 里声明的顺序拼，不按 context 列出的顺序。`reads` 本身是按 context 的顺序排的，拼的时候却遍历 `outputs.items()`，挑出名字在 `reads` 里的输出，顺序就成了任务跑的顺序。outline、research、draft 这个 crew 里，draft 的 context 是 `[research, outline]`，拿到的却是 outline 在前。draft 的模型是 `KeyedLLM`，报 `Unscripted: no reply scripted for 'Outline: ...'`：错误在 llm.py 的替身里报出来，根因在 crew.py 拼输入的那一行。
3. 每个任务都先接上一个任务的输出，再接 context（context 已经列了上一个任务时不重复）。课里 Sequential 那句 “Output of task N is available as context to task N+1” 被当成了总要带上；docstring 写的是只有没写 context 的任务才读上一个任务的输出。第一个 crew 的 edit 自己就把 draft 列进了 context，那里看不出来。corrections 的 context 是 `[fact_check]`，fact_check 输出空串表示没发现问题，corrections 却读到了 draft 加空串，替身报 `Unscripted: no reply scripted for 'Agents forget ...\n\n'`。
4. `Flow.listen` 写成 `self._listeners[topic] = [fn]`，同一个 topic 的第二个监听者覆盖了第一个。`kickoff` 本身已经是先进先出的队列，没有问题（测验 Q11 说的正是这个覆盖）。
5. 计时：`recall_long_term` 每次查询都把全部长期记录重新嵌入。60 条约 3,000 词的笔记、30 次查询，本机约 2.1 秒；写入时嵌入一次以后约 3 毫秒。限值 0.1 秒。

起始代码里已经做对、修的时候不能改坏的两点：上游输出是空串时原样传下去；context 引用了声明在后面的任务，或者根本不在这个 crew 里的任务，在任何 agent 运行之前报 ValueError，写出那个任务的名字。

护栏：

- 修第 3 处时不能去掉回退：没有 context 的任务仍然读上一个任务的输出，第一个任务读 topic。改成“每个任务都只读 context”会让 researcher 读到空串，改成“回退到 topic”会让 writer 读到 topic。
- 照课里的代码写成 `joined or prior`，或者 context 的输出全是空串时改读上一个任务，fact_check 的空串都会换成 draft，corrections 的替身照样报 Unscripted。
- 修第 2 处时要沿着 context 取：把顺序倒过来、按任务名排序，第一个 crew 的 edit 会读反；按任务跑的顺序、沿着 crew 的任务列表去挑，或者让有 context 的任务读此前全部输出，outline 那个 crew 还是反的。
- 修第 1 处时只修表面不行：让 `embed` 接受 `str(text)`，或者只把文本输出写进长期记忆，报错没了，但 draft 还在长期记忆里，下一条断言抓住。
- 重写 `kickoff` 时把 context 检查挪进循环（轮到那个任务时才发现），researcher 会先花掉一次调用，测试检查替身有没有被调用过；只查 context 里的任务在不在这个 crew 里，声明在后面的任务会在取输出时报 KeyError。
- 把向量按角色缓存会让两次 kickoff 的 research 共用一个向量，第二次的召回顺序就错了。
- 可以接受：按任务名取上游输出（起始代码就是这样），测试也能过。kickoff 的结果本来就按任务名索引。

看什么：是不是先读 traceback，再顺着 dict 是从哪来的往上游找；看到 Unscripted 时，是不是先把替身收到的输入和测试里的剧本逐段对一遍，再回 docstring 核对 context 的规则；有没有回到 docstring 里核对“谁该写长期记忆”；每改一处就重跑。

提示：
- AttributeError 那一层：H1 "Which task produced a dict, and why is it in long-term memory at all?" H2 "Read Task.persistent's docstring." H3 直接指出 `kickoff` 里无条件的 `write_long_term`。
- outline 那一层：H1 "What did the draft's model receive, and what does its script expect?" H2 "Which collection does kickoff walk when it joins the outputs?" H3 直接指出遍历 `outputs.items()` 的那一行。
- corrections 那一层：H1 "Where does the draft in the corrections prompt come from?" H2 "Read the docstring again: which tasks read the previous task's output?" H3 直接指出 `reads.insert(0, ...)` 前面的条件。
- Flow 那一层：H1 "How many listeners does 'researched' have after the decorators run?" H2 直接让候选人读 `listen`。
- 计时那一层：H1 "How many times is each record embedded across 30 recalls?" H2 "When could the vector be computed instead?"

追问：
- "Why not just teach embed to accept dicts?"（那是在症状上修。课里的 Pitfall：长期记忆每次运行都写，向量库越来越大，检索越来越吵。该修的是谁能写）
- "With a real embeddings provider, what does write-time embedding cost?"（每条记录一次 API 调用，可以批量、按内容 hash 缓存；每次查询都重新嵌入，花的是钱和延迟）
- "Context reaches the agent as joined text. How would you make the order and the boundaries between tasks impossible to get wrong?"（每段标上来源任务；更好的是课里 Brittle handoffs 的修法：上游用 `output_pydantic` 产出类型化对象，下游按字段读，不靠拼接的位置）
- "Could the crew catch the forward reference even earlier?"（构造 crew 时就校验，或者在 CI 里对 crew 定义做静态检查）
- "The lesson's Flow kept one listener per topic. What else can go wrong in an event loop like this?"（A 发出的 topic 又被 A 监听，会死循环；可以在注册时检查环，或者给步数设上限）

### Part 2 实体记忆（目标 10 分钟）

坑：
- dbm 的键读回来是 bytes。`str(key)` 得到 `"b'Acme'"`，按 Latin-1 解码会把 `株式会社ネコ` 变成乱码，要按 UTF-8 解码。
- `dbm.open(path, "n")` 每次打开都清空文件，第二次 kickoff 什么都看不到。要用 `"c"`。
- 记一个新事实不能丢掉旧事实：先读出这个实体的 JSON，合并，再整体写回。`Acme Labs` 先记了 plan 和 seats，再改 seats、加 renewal，三项都要在。
- 值要原样读回：`Halle 4\nTor B\n` 结尾的换行、`PO-77\r\nref 3` 里的 CRLF、`"  formal, no emoji  "` 两头的空格、引号、等号、反斜杠。存成 `key=value` 行或者 strip 一下都会坏。JSON 能存准。
- 按名字精确查：`Acme` 和 `Acme Labs` 是两个客户。按前缀扫描或者统一小写都会把它们搅在一起。测试还查 `acme` 和末尾带空格的 `Acme `，都应该没有事实，所以查找时忽略大小写、去掉首尾空格也不行。
- `entities()` 要排序。键的顺序由 dbm 后端决定：gdbm 和 ndbm 是哈希顺序，dbm.dumb 是插入顺序。Python 3.13 起新文件默认用 dbm.sqlite3，它按字节序返回键，而 UTF-8 的字节序和 `sorted()` 的结果一样，所以在 3.13 及以上忘了排序测试抓不住，要看代码。
- 没记过的实体返回 `{}`，不报 KeyError；空的实体名要报 ValueError，否则缺了客户名的调用会把事实记到一个大家共用的 `""` 下面。
- 在内存里缓存读结果、把缓存里的 dict 直接交出去，调用方一改就改到了存储。
- 最后直接打开 dbm 文件检查：每个实体一个键，值是一个 JSON 对象。一事实一个键、另加一个索引键、pickle、JSON 列表、Python 的 `repr`，都会在这里挂掉。

追问：
- "Two kickoffs remember facts about the same customer at the same time?"（读、合并、写回之间有竞争，dbm 没有事务；加文件锁，或者换成带事务的存储）
- "A customer asks to be forgotten. What do you delete?"（实体记忆删一个键就够了；长期记忆里的向量和短期缓冲也可能提到这个客户，更难清理）
- "Why not keep these facts in long-term memory?"（课里说 entity 记忆按实体取，不按相似度取。相似度检索会把 Acme Labs 的事实拿给 Acme）

### Part 3 经理路由（目标 14 分钟）

坑：
- 段落按空行分。只按 `"\n\n"` 切，碰到 `"\n   \n"` 这种只有空白的行、CRLF 换行、连续的空行、开头结尾的空行都会数错；按非空行计数会把一段里折行的两行算成两段。测验里 Q9 的参考写法 `split("\n\n")` 加过滤，在空白行和 CRLF 上就数错了。用 `re.split(r"\n\s*\n", text)` 再去掉空块是对的。
- 被拒的那一轮也要有人干活：editor 被拒，writer 重做，这一轮仍然只调一次 manager。什么都不跑、直接进入下一轮，manager 会一直挑 editor。
- writer 重做读的是 researcher 的输出，不是自己被拒的草稿。课里的代码用 `current = out` 串起来，照抄就会读到自己的草稿（测验 Q9.3）。把拒绝理由拼进 writer 的输入当反馈（Q9.3 的答案说可以附上）在这里也不行：docstring 规定每个专家只读上一个专家的最新输出，测试查 `writer.inputs`。
- editor 读的是最新的草稿。
- 规则写在每个 Specialist 的 `min_paragraphs` 上，测试另有一个 analyst / reviewer 的 crew，门槛是 2 段，把 editor、writer、3 写死会挂。
- 被拒也算一轮。没有把它算进 max_steps，写作替身会先用完剧本，报 `no scripted reply left for call 7`。
- 说 done 的那一轮也算进 max_steps：max_steps=4 正好够 3 个专家加一次 done；`range(1, max_steps)` 少一轮。
- manager 每次拿到的是那一刻为止的全部输出。把活的 list 直接放进 ManagerView，测试记下的 5 个视图会全是最后的样子；只发每个专家的最新输出，也不对。测试还核对最后一个视图的内容：按调用先后排列，被拒的两段草稿也在，改派那一轮记在实际跑的 writer 名下。
- `refusals` 只记被挑中的专家为什么被拒。改派时往上游找，路上发现 writer 也还不能跑，这不算一次被拒的 pick；把它也记进去，manager 一上来就挑 editor 的那个用例会多出一条。
- 记账：每次 manager 调用记下任务数和此前所有输出的字符数，被拒的草稿也算。这组数据是 0、61、113、212、224，加起来 610 个字符，而几个专家自己读的输入一共只有 233 个字符。
- manager 回了不认识的名字要报 ValueError；`"done"` 要在检查名字之前判断。
- 还没轮到的专家被挑中时，往上游找最近一个输入已经齐了的专家来跑：manager 一上来就挑 editor，先跑的是 researcher。只往上退一级会在 `latest["researcher"]` 上报 KeyError。

追问：
- "The lesson says a five-task hierarchical crew makes six LLM calls instead of five. What does this crew make?"（每个专家前一次 manager，再加一次说 done：2n+1，五个任务是 11 次。“六次”只在 manager 一次排好全部顺序时成立，测验 Q14 讨论过）
- "Why does the tax grow faster than the number of calls?"（每次 manager 调用都带着此前全部输出，总量是平方级的。课里说 token 成本在五步的运行上可能翻三倍）
- "When would you drop the manager?"（课里：路由不依赖输出就用 Sequential；四个以上专家、顺序确实取决于前面的结果才值得）
- "Exercise 3 says trace the retry. What would you put in the trace?"（每一轮挑了谁、谁实际跑了、为什么拒绝、manager 带了多少内容）

### Part 4 Flow 事件日志（目标 14 分钟）

坑：
- 一个 topic 的监听者要同时开始。一个一个 await、按层 gather、按层 `as_completed`，都会在测试里等不到下一行，1 秒后报 “every step is logged the moment it completes”。测试的消费者每读到一行才放行下一个步骤，所以先把整个流程跑完再一起输出也会卡住。
- 下一个 topic 的监听者在上一个步骤完成时就开始，不等同一层的其他步骤：cite_check 完成后，file_citations 比 draft 先完成。
- 返回 None 只结束自己这条分支。照课里的代码 `break` 会让 Flow 在 file_citations 之后就停了。
- 没人监听的 topic（edited）直接结束这条分支，`self._listeners[topic]` 会报 KeyError。
- 什么时候结束：没有正在跑的步骤时结束。`while True` 等队列会一直等下去。
- logfmt：值为空、含空格、引号、等号、反斜杠、换行、回车、制表符时，要加双引号并转义。`x=1` 和 `say"hi"` 没有空格也要加引号；空值写 `out=""`；`json.dumps` 会把 `ü` 写成 `\u00fc`，测试的解析器不认。多加引号不算错，解析器两种都接受，只有两条直接检查要求 `step=draft` 写成裸值。
- 每行以 `\n` 结尾，值里的换行要转义，否则一个步骤变成两行。edit 的输出里有 `\r\n` 和制表符，回车或制表符原样写进去，解析器报 not a logfmt line。
- 结束分支的步骤只写 step 和 duration_ms，不写空的 topic 和 out。
- duration_ms 是整数毫秒，从这个步骤开始运行算起。从 Flow 开始算，快的那一步会报出 60 多毫秒。
- 出错：抛异常的步骤要先记一行 `error="RuntimeError: search API is down"`，再取消还在跑的步骤，最后把原来的异常抛给调用方。异常在任务里丢了，消费者会一直等；没有取消，被阻塞的 draft 会一直挂着（测试在 asyncio.run 收尾之前就看结果）。
- 骨架是 `async def` 里只有 raise，测试报 `'coroutine' object has no attribute '__anext__'`，要看出这里需要 async generator。
- 可以接受的写法：先 yield 这一行，等消费者来取下一行时才启动监听者，测试也能过，这就是澄清问题里“消费者读得慢”时的取舍，请候选人说出来。出错时只 `cancel()`、不等被取消的任务结束，测试也能过（测试拿到异常后先 `await asyncio.sleep(0)` 再看结果）；等它们结束再抛出更稳妥。

追问：
- "Why log on completion and not on start?"（两个都记更好。课里说值班的人要知道凌晨 3 点是哪个 agent 卡住了，开始了却一直没完成的步骤正是那种情况）
- "A step never returns. What should the flow do?"（给每个步骤设超时，`asyncio.wait_for`；超时也记一行，然后按失败处理）
- "Where would Crew.kickoff() go in this flow, and what about a step that posts to a CMS?"（Crew 放在某个步骤里面调用；有副作用的调用放在 Flow 步骤里，不交给 Crew 当工具，这是课里的 Pitfall。再给它加上幂等键，重放时就不会重复发布）
- "The consumer reads slowly. What grows?"（这个实现里结果在队列里排队；要限流就给队列设上限，或者等消费者读了再启动后面的步骤）

### Part 5 运行比对（目标 10 分钟）

坑：
- 兄弟节点按名字和出现序号对齐。按位置对齐，第二个 intake 一插进来，后面全错；只按名字对齐，几个 review 会合并成一个。
- 序号在每一组兄弟节点里单独数。全局计数（比如用可变默认参数在调用之间共享一个 dict）连两次一样的运行都会报出差异。
- 路径段是 `name[k]`，k 从 0 开始，第一次出现也要写 `[0]`。
- 只有一边有的子树只报一次：cite 下面的 crew 和 lookup 不再单独列出。
- 嵌套 crew：verify 在第 5 层，递归要一直走到底；被拒、重做出来的 review 和 revise 都是同名步骤多次出现。
- 每个两边都有的节点都比 output，中间节点也比（revise 的 output 从 revised 变成 revised twice）；`""` 和 `"3 notes"` 是不同的，按真假值比较会漏掉；`""` 和 None 也不同，用 `output or ""` 把 None 当成空串会漏掉 cite_check 那一条。output 不同还要接着往下比子节点。
- 顺序：沿着好的那次深度优先读，只在坏的那次出现的节点排在同一层好的节点之后。first 是所有差异里最早的一个。从 changed 里取、按 missing、extra、changed 的顺序拼起来取、把 extra 放到全部最后、沿着坏的那次走、先比子节点再记自己（后序）、按路径排序，都会在某个用例上排错。triage 那个用例查的是 extra 的位置：triage 只在坏的那次出现，排在 review 前面，但要等这一层好的节点都读完才轮到它，所以 first 是 `review[0]`；按它在坏的那次里的位置插进去（合并两边的顺序）会在这里挂。

追问：
- "The LLM rewords a draft but means the same thing. How do you keep the diff useful?"（比结构化输出而不是自由文本，课里的 `output_pydantic`；或者先归一化再比）
- "Why can't on-call diff two runs of a free-form crew?"（路径由 LLM 在运行时决定，没有稳定的步骤名可以对齐；用 Flow 包起来，步骤名和 topic 由代码决定）
- "Two traces with a thousand steps each?"（按层用字典对齐是线性的；可以先比子树的 hash，相同的整棵跳过）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出记忆的写入范围、嵌入成本、并发写、manager 税、超时和取消、Flow 与 Crew 的分工 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
