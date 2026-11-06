# 面试官手册：Workflows（14/12）

候选人计时期间不要看。候选人手里只有 README、`workflows/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 模型、工人和路由处理器都是测试里的替身（`Model`、`Voters`、`Planner`、`Crew`、`Desk`），按脚本回答。`Model` 收到没有写进脚本的 prompt 会抛 `Unscripted`，这是在报告“工作流发出了一个没人预料的 prompt”。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | “refund.” 或 “Refund request” 这种标签算 refund 吗？ | "No. Only surrounding whitespace and case are normalized. Anything else is an unknown label: it goes to the default handler, or raises UnknownRoute." |
| 1 | 走了 default 的工单，route 返回什么标签？ | "The normalized label the classifier gave, with the default handler's output." |
| 1 | 模板里的 `{{` 和 `}}` 要变成单个花括号吗？ | "No. Only {text} is replaced. Everything else goes to the model exactly as written." |
| 1 | 过半按 n 算，还是按已经回来的票算？ | "Against n, the votes asked for. An answer needs more than half of n. Exactly half is not a majority." |
| 1 | 提前结束时，counts 里放什么？ | "Every vote that had come back when the answer got its majority. A cancelled call has no vote." |
| 1 | 卡住的调用要不要加超时，超时的票就不算了？ | "No timeout. Once an answer has more than half, the other votes can't change the result, so stop waiting for them. Without a majority, every vote counts, however slow." |
| 1 | 取消了以后，还要等它们结束吗？ | "Yes. When parallel_vote returns, none of its calls may still be running." |
| 1 | 一个投票的调用抛了异常怎么办？ | "Today the error propagates. The tests don't cover it. What would you want instead?" |
| 1 | n 是 0 呢？ | "The tests don't cover it. Tell me what you'd choose." |
| 1 | 轮数用完时，能不能返回被拒的稿子里最好的那份？ | "No. output is None when no round passed. The rounds are kept for whoever takes over." |
| 2 | XML 的结构能自己定吗？ | "Yes. The root element is run. The rest is yours, as long as an auditor sees plain text as plain text." |
| 2 | 哪些值需要编码？ | "Only what XML can't hold exactly: control characters other than tab and line feed, and carriage returns in element text. Everything else stays plain." |
| 2 | 用什么编码？ | "Your call. Base64 is fine. Mark the value so read() knows to decode it." |
| 2 | 同一个 run id 写两次？ | "Overwrite it. The tests don't cover it." |
| 2 | 要不要缩进排版？ | "Either. It helps auditors, but it must not change any value." |
| 2 | 步骤名有什么限制？ | "It's free text: slashes are fine, and names repeat, since an evaluator-optimizer run alternates propose and evaluate. The tests don't put control characters in names." |
| 3 | 编排者写了一个不存在的 worker，跳过就行吗？ | "No. The plan is bad. Raise PlanError before anything runs." |
| 3 | 同样的任务文本发给两个 worker，算重复吗？ | "No. A subtask is the worker and the task together." |
| 3 | max_subtasks 是整个 run 的上限吗？ | "Per round. Only subtasks that haven't run yet count against it." |
| 3 | 被截掉的子任务后来又跑了，dropped 里还留着吗？ | "Yes. dropped records what each round cut, in order. results shows what ran." |
| 3 | 说 done 的计划里还有子任务呢？ | "Run them. That plan is the last one." |
| 3 | worker 抛异常怎么办？ | "It propagates for now. The tests don't cover it." |
| 3 | 一轮里全是做过的子任务，要不要提前停？ | "No. The run stops on done or after max_rounds. The next plan may still ask for something new." |
| 3 | 计划里少了 done 字段？ | "That's not the plan shape, so it's a PlanError." |
| 4 | 并发上限是每条路由一个，还是全局一个？ | "Per route. A full refund route never slows down bugs or sales." |
| 4 | 分类器本身失败了呢？ | "Same as a handler failure: an error line, with route null. The tests don't cover it." |
| 4 | ms 从什么时候算？ | "From the moment the ticket arrived until its line is ready, including its classification and any wait for its route. Any number type is fine." |
| 4 | 输出按什么顺序？ | "The order the tickets finish, not the order they arrived." |
| 4 | 客户端中途不读了怎么办？ | "Stop pulling tickets and cancel whatever is still in flight. Nobody will read those lines, and a ticket pulled after that would be lost." |
| 4 | 要不要限制同时拉进来的工单数量？ | "Not today. The tests don't cover intake backpressure. Good thing to bring up later." |
| 5 | 工具调用算 LLM 调用吗？ | "No. A tool costs time, not LLM calls." |
| 5 | route 的分类器要算吗？ | "Yes. It's a node like any other, usually an llm node." |
| 5 | orchestrator 能一个 worker 都不跑吗？ | "Yes. Round 1 can say done with no subtasks." |
| 5 | 同一轮的 worker 延迟怎么算？ | "They run at the same time, so the round waits for the slowest one." |
| 5 | 遇到 type 是 agent 的节点？ | "That's not a workflow node. ValueError. An agent has no fixed step count, which is the lesson's point." |
| 5 | 最少、最多和最坏延迟要来自同一个分支吗？ | "No. Each bound is its own extreme." |

## 每关：要看什么、提示、追问

### Part 1 修四种模式（目标 14 分钟）

一个测试里叠了 6 处缺陷，分布在 4 个函数里，还有几个护栏：

1. `route` 没有规范化标签。分类器回的是 `"Refund\n"`，`handlers.get` 找不到，落到 default 的 triage 链上。错误不在 `route` 里报，而是在下面两层：triage 链经 `prompt_chain` 把一个没人预料的 prompt 发给了模型，测试替身报 `Unscripted: no reply scripted for 'Summarize this ticket for a person to pick up: ...'`。
2. `prompt_chain` 用 `template.format(text=current)`，提取模板里的 JSON 示例 `{"order": "A-123", ...}` 被当成格式字段，报 `KeyError: '"order"'`。
3. 没有 default 时，`route` 返回 `(label, "no handler for ...")`，把一句错误信息当成了处理结果。docstring 要求抛 `UnknownRoute`，并在消息里写出标签。
4. `evaluator_optimizer` 轮数用完时返回最后一份被拒的稿子（课里 `code/main.py` 就是这么写的，测验 Q9 问的也是它），调用方分不出通过和没通过。docstring 要求这时 output 是 None。
5. `max_iter=0` 时报 `UnboundLocalError`；修好第 4 处以后，常见写法会悄悄返回 `Refined(None, [])`。docstring 要求 `ValueError`，测试查 0 和 -1，写成 `if not max_iter` 会放过 -1。
6. `parallel_vote` 已经用 `asyncio.gather` 并发，但要等齐全部 n 票才计数。docstring 要求某个答案一超过 n 的一半就收场：取消还在跑的调用，等它们真正结束再返回。测试里 7 票的那次投票，10 毫秒时 yes 已经有 4 票，另有两个调用卡了 2 秒，整次投票跟着等了 2 秒，限值 0.2 秒；过半就收场约 10 毫秒。这就是课后练习 2 问的：一个调用卡住了怎么办，缺票时怎么聚合。

护栏：
- 过半就返回以后，还在跑的调用要取消，并且等它们结束。测试替身被取消以后要三轮事件循环才关掉连接，测试在返回那一刻和 50 毫秒以后各看一次。完全不取消，报 "the calls still running when the vote is decided are cancelled"；只 `cancel()` 不等，或者 cancel 以后 `await asyncio.sleep(0)`，返回时它们还在跑，报 "no call outlives the vote"；`gather` 不加 `return_exceptions=True`，`CancelledError` 会从 `parallel_vote` 里冒出来。
- 过半是超过 n 的一半。按已经回来的票算，第一票回来就“过半”了；`>= n / 2` 会把 2 比 2 当成多数；`>= n // 2` 在 7 票里 3 票就收场。测试里 2 比 2 的那次投票没有多数，要等齐 4 票，平票给最先提交的 no。
- 不能加超时丢票。有了多数，剩下的票改变不了结果，所以不用等；没有多数，每一票都要等。只靠截止时间收场的写法两头都过不去：2 比 2 那次有一票 0.25 秒才回来，短于 0.25 秒的截止时间会丢掉它；不短于 0.2 秒的截止时间又会让卡住的那次投票超过限值。
- counts 是过半那一刻已经回来的全部票，测试里包括最先回来的那张 no，只留赢家的票数不对。用 `asyncio.wait(..., return_when=FIRST_COMPLETED)` 的写法，要把这一批 done 全部计完再判断；数一张判一次、中途就返回，会漏掉同一批里已经回来的票。测试里那张 no 比决定胜负的 yes 早 9 毫秒回来，只有机器卡顿时才会撞进同一批，看到这种写法要指出来。
- 平票取最先提交的那一票。测试是三方平票：最先提交的是 yes，最先回来的是 unsure，字母序最前的是 no。`as_completed` 边回来边计的那份 Counter 是按回来的顺序插入的，没有过半时直接拿它 `most_common`，会选 unsure；按字母序会选 no。没有过半时要按 tasks 列表的顺序重新计票，`Counter.most_common` 平票时保留先插入的那个，课里原来的平票规则就照样成立。
- 遍历 `asyncio.wait` 返回的 done 集合收票，也不是提交顺序：集合按对象地址排，既不是提交顺序也不是完成顺序。平票测试抓不住这种写法（本机上它恰好每次都选 yes），看到了要指出来，改成按 tasks 列表的顺序取结果。
- 300 个调用要同时在飞。这次投票分成 140、120、40，没有答案过半，要等齐全部票；一个接一个 await 约 2 秒，限值 0.12 秒。替身数了同时在飞的调用数，加 Semaphore 限流的写法过不了：上限 50 时照样能在 0.12 秒内跑完，但 docstring 写的是 n 个调用同时在飞。
- 只有完全相等的标签才选路由。用子串、`startswith` 或第一个词匹配，"refund request" 会被送进退款链，替身报 `Unscripted`。
- 只替换 `{text}`：先试 `str.format`、失败了再用 replace 的写法，会把回复模板里的 `{{agent_name}}` 变成 `{agent_name}`；`re.sub` 会在 `C:\Users` 的 `\U` 上报 bad escape；`replace(..., 1)` 漏掉标题模板里的第二个 `{text}`。
- 配了 default 时，未知标签走 default。一律抛 `UnknownRoute` 的改法会挂在 "pricing" 上。
- 去空白要用 `strip()`。`strip(" \n")` 去不掉 `"\tBUG \n"` 前面的 tab。
- 评估器的反馈要传回提议者，测试核对提议者收到的是 `[None, "name the order"]`。

看什么：是不是先读 traceback，注意到 `Unscripted` 是从 triage 链里报出来的，再回头问“为什么走了 triage”；有没有用 `print(repr(label))` 看分类器的原始输出；改 `parallel_vote` 时有没有想到提前返回以后还在跑的调用怎么办，以及没有过半时平票规则还成不成立。

提示：
- `Unscripted` 那一层：H1 "Which handler sent that prompt?" H2 "What exactly did the classifier return? Print its repr." H3 直接指出 `route` 没有按 docstring 规范化标签。
- `KeyError` 那一层：H1 "Where does a key named '\"order\"' come from?" H2 "What does str.format do with the braces in a JSON example?"
- 计时那一层：H1 "How many votes does an answer need before the others can't change the result?" H2 "When parallel_vote returns, which of its calls are still running?" H3 直接指出用 `asyncio.as_completed` 边回来边计票，过半后 cancel 剩下的任务，再 `await asyncio.gather(..., return_exceptions=True)`。

追问：
- "Exercise 1: add a confidence threshold to routing. Where does the threshold come from?"（用带标签的历史工单离线标定：画阈值和自动处理率、误路由率的曲线；不同类别阈值不同，退款这种涉及钱的要更严；低于阈值转人工）
- "No answer has a majority and one call never comes back. What now?"（现在的写法会一直等下去；给整次投票一个截止时间，到点后按已经回来的票裁决，或者明确返回“没有结论”，并记下缺了几票；到点时同样要取消并等待剩下的调用）
- "Why wait for the cancelled calls instead of returning right after cancel()?"（`cancel()` 只是请求，CancelledError 要等任务下次运行时才送进去，关连接、写日志、释放并发名额都在那之后；不等的话，调用方以为投票结束了，后台还有请求在跑，事件循环关闭时还会报 Task was destroyed but it is pending）
- "What does cancelling actually save with a real API?"（流式接口断开以后模型不再生成，后面的 token 不用付；非流式请求已经发出去，服务端可能照样计费；省下的主要是等待时间和并发名额）
- "Why None instead of the best rejected draft?"（被拒的稿子不能当答案发出去；rounds 留给接手的人；练习 3 的 top-2 需要评估器能打分，是另一个问题）
- "When does voting on the same prompt even make sense?"（要有采样随机性；temperature 为 0 时 n 票几乎一样，白花钱）

### Part 2 XML 审计记录（目标 12 分钟）

坑：
- 控制字符（工具输出里的 ANSI 颜色码 `\x1b`、NUL、从 PDF 抽出来的换页符 `\x0c`）在 XML 1.0 里根本不允许出现。ElementTree 写的时候不检查，照样写进文件，读的时候 expat 报 `not well-formed (invalid token)`。报错在 read，根因在 write。
- 元素文本里的回车会被解析器换成换行：`\r\n` 读回来是 `\n`，命令行进度条里单独的 `\r` 也变成 `\n`。不报错，值悄悄变了。属性值里的回车 ElementTree 会写成 `&#13;`，能原样读回，所以把值放在属性里的写法只需要处理控制字符。
- 空字符串写成 `<output />`，读回来 `.text` 是 None。None 和空串要分开：没有这个元素表示 None，有元素没文本表示 ""。
- 读的时候 `.strip()`，首尾空白和换行全没了，`"Refund\n"` 变成 `"Refund"`。
- 步骤名会重复（evaluator-optimizer 的 propose、evaluate 来回交替），按名字存进 dict 会丢步骤。步骤名里有 `/`，拿来当标签名会写出非法的 XML。
- 全部 base64 或者全部存成 JSON 字符串，往返没问题，可审计员读不了。测试用独立的 ElementTree 解析器检查：XML 能装下的文本，必须原样出现在某个元素的文本或某个属性值里，包括首尾的空格和换行、`&` 和 `<`、代码里的 `]]>`、非 ASCII 字符。
- 自己发明转义（比如把 ESC 写成 `\u001b`）也可以，但只能用在带标记的值上。不分青红皂白地解码，一段本来就写着 `"\x1b[0m"` 字样的普通文本会被错误地还原。
- 带标记的值里，转义符本身也要转义。测试里有一步 grep 的彩色输出，同一个值里既有真的 ESC，也有源码里字面的 `\x1b`。只把控制字符写成 `\xNN`、不管反斜杠，读回来字面的那个也成了 ESC。
- run id 要校验：`re.match` 只匹配开头，"run 7" 会混过去；`^...$` 的 `$` 会放过结尾的换行，"run-0007\n" 会混过去；`\w` 和 `isalnum()` 会放过非 ASCII 字母（"rün-7"），docstring 只允许 ASCII；只查 `/` 和 `..` 会放过空格和空串；允许 `.` 会让 "run-0007.xml" 写成 `run-0007.xml.xml`。
- 不存在的 run id 要报 KeyError，不能把 FileNotFoundError 漏出去。

追问：
- "An auditor asks which branch run 7 took, and why. Can they tell?"（branch 加上 classify 那一步的原始输出；有置信度的话也要存）
- "Why XML here, and would JSON do?"（很多审计和合规工具吃 XML，有成熟的 schema 校验；真正要紧的是图能读懂、格式稳定、有 schema，JSON 加 schema 也可以）
- "How would you stop a record being edited afterwards?"（只追加写，哈希链或签名，写完改成只读权限）
- "A run has 50,000 steps. What changes?"（ElementTree 把整棵树放在内存里；改成边写边落盘，读的时候用 iterparse 流式解析，或者按步骤分文件）

### Part 3 编排者-工作者（目标 12 分钟）

坑：
- 子任务是 (worker, task) 这一对。只按任务文本去重，会把发给 security 的 "review error handling" 当成 python 那条的重复；只按 worker 去重，同一个 worker 的第二个任务就没了。
- 先去重，再截到 max_subtasks 个。先截后去重，第一轮只剩 3 个子任务。
- 第二轮先去掉已经跑过的，再截。先截后去掉，第二轮的 style 子任务被已经跑过的挤掉了。
- 被截掉的子任务记在 dropped 里，下一轮编排者还可以再要，它不算跑过。
- 结果按编排者要的顺序排，不按完成顺序。测试里 python 的 "review error handling" 最快，`as_completed` 会把它排到第一。
- 同一轮的子任务要同时跑，测试数了同时在跑的最大个数。
- 说 done 的那份计划，它列的子任务照样要跑，跑完才停。到 max_rounds 就停，不再向编排者要计划（替身会报错）。最后一轮说了 done，stopped 是 "done" 而不是 "max_rounds"。
- 一轮里全是做过的子任务，也不能提前结束：下一份计划可能还会要新的。测试里第二轮只重复了第一轮的子任务，第三轮才要 docs。
- 每一轮编排者看到的是到目前为止的全部结果，不是上一轮的结果。测试里跑满三轮的那个 run，核对了第三轮的编排者看到前两轮的全部结果。
- 未知 worker 抛 PlanError，不能跳过。整份计划先检查完再开始，超出本轮上限的部分也要检查。边跑边查的写法，python 那条已经跑起来了才报错。
- `"done": "false"` 是字符串，`bool("false")` 是 True；没有 done 字段也不是计划的样子，不能当成 false。
- 回复不是 JSON、不是对象、字段缺了，都要包成 PlanError，不能把 JSONDecodeError、AttributeError、KeyError 漏出去。
- 编排者一个 worker 都不派的时候，也要综合一次。

追问：
- "How is this different from routing, and from parallel sectioning?"（routing 只选一个处理者；sectioning 的切分是工程师写死的；这里由 LLM 按具体输入决定派给谁、派几个）
- "Why throw away the whole plan for one unknown worker?"（执行一半会留下半截副作用；让编排者重试或者转人工；更稳的是用 JSON schema 把 worker 名限定成枚举）
- "Workers fail or time out. What would you do?"（`gather(return_exceptions=True)` 把失败记成结果交给下一轮的编排者看；或者重试；不让一个 worker 拖住整轮）
- "At what point does this stop being a workflow?"（编排者能无限追加任务、自己决定什么时候停的时候；R 和 K 两个上限让它仍然有界，这正是 Part 5 算得出上界的原因）

### Part 4 路由流（目标 12 分钟）

坑：
- 输出格式由测试的解析代码决定：一行一个 JSON 对象，用换行分隔。手拼 JSON 会坏在带引号和换行的工单上；`indent=2` 会把一条记录拆成好几行。
- 每条路由一个 Semaphore。所有路由共用一个，bug 路由的并发就上不去；在 handle 里每次新建一个 Semaphore，等于没有限制。
- 不能在拉工单的循环里等路由的闸门：退款路由满了，后面的销售工单就进不来（head-of-line blocking）。测试里 10 张退款单排在一张销售单前面，销售单那一行必须在 50 毫秒内出来；堵住的几种写法都要 0.55 秒以上。
- 也不能在拉工单的循环里一张一张 await 分类器。分类器本身是一次 LLM 调用，这样写会让分类排成一队，拉取跟着变慢，而 ms 从拉进来才开始算，看不出这段等待。测试主流程用的分类器每次要 1 毫秒，并且数了同时在分类的工单数。
- 按完成顺序输出。按到达顺序 await 各个任务，或者全部做完再一起输出，都会让快的工单等慢的。
- 来一张处理一张。先把整个流读完再开始，第一行要等所有工单到齐，测试数了拿到第一行时拉了几张。
- 未知路由和 handler 抛的异常都变成 error 行，流继续往下走。异常没接住的话，那张工单就没有输出，`asyncio.wait` 也不报错，测试只看到少了一行。
- ms 从到达算起，包括分类和排队等路由的时间。从 handler 开始时算会少掉排队，从流开始时算会把后到的工单算得很慢；单位是毫秒，不是秒。从分类完才开始算也不对，只是测试的分类器只要 1 毫秒，测不出来，看到了要指出来。
- 消费方提前关掉流时，要停止拉取工单，并取消还在跑的工单。关闭以后还在拉的话，拉进来的工单没人处理，等于丢了；只取消拉取任务、不取消 handler 任务，或者在 finally 里等它们跑完，也都不对。
- 骨架是 `async def` 里只有 raise，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要看出这里需要的是 async generator。

追问：
- "The refund backend is down for an hour. What happens to its queue?"（排队的任务越来越多；给每条路由的排队长度设上限，满了就拒绝或者转人工）
- "Why a limit per route instead of one global limit?"（bulkhead：一条路由拥堵或故障不拖垮别的路由；各路由下游的容量本来就不一样）
- "Should intake stop pulling when every route is busy?"（这是背压：给在途工单总数设上限；现在的写法会无限地拉进来）
- "The classifier is an LLM call too. Where does its rate limit go?"（单独给分类器一个上限；分类慢了，所有路由都会跟着慢）

### Part 5 成本上界（目标 10 分钟）

坑：
- 工具调用不算 LLM 调用，但算延迟。
- route：先是分类器，再加一个分支。最少取最便宜的分支，最多取最贵的分支，最坏延迟取最慢的分支，这三个可以来自不同分支。测试里分别是 spam（不调 LLM）、sales（最多 35 次调用）和 refund（最慢，6150 毫秒）。
- parallel：调用数相加，延迟只等最慢的那个。投票是 n 份同一个子树：调用数乘 n，延迟不乘。
- evaluator-optimizer：最少 1 轮（第一轮就通过），最多 max_iter 轮，最坏延迟也按 max_iter 轮算。
- orchestrator：最少是一次规划加一次综合（第一轮就说 done，不派任务）；最多是每轮一次规划，每轮的 K 个槽位都给调用最多的 worker，再加一次综合；最坏延迟是每轮“规划加最慢的 worker”（同一轮并发），再加综合。调用最多的 worker（pricing，4 次）和最慢的 worker（legal，1800 毫秒）不是同一个。槽位数可以比 worker 多（测试里 4 个槽位、3 个 worker）：子任务是 (worker, task) 这一对，同一个 worker 一轮可以领几个不同的任务，按 worker 个数封顶会把 35 算成 27。
- 未知节点类型（测试里是 agent）报 ValueError 并写出类型名；n、max_rounds、max_subtasks、max_iter 小于 1 也报 ValueError。测试四个计数都查了，还有一个是负数，`if not value` 只拦得住 0。

追问：
- "The lesson says workflows have bounded step counts. Why can't you bound an agent the same way?"（下一步取决于上一步的结果，没有预先固定的步数；只能靠预算从外面截断）
- "Turn worst_ms into a p95. What would you need?"（每个节点的延迟分布，而不是一个数；串联要做卷积，并行要取最大值的分布；最简单的是蒙特卡洛模拟）
- "Exercise 4 asks about token cost. How would you add it?"（每个节点加 token 数，像调用数一样累加，route 取分支的极值；注意链往后走 prompt 会变长）
- "Where would you enforce these bounds while the workflow runs?"（在 orchestrator 和 evaluator-optimizer 的循环里设硬上限，超出预算就停下转人工；上线前用这里的上界做预算审查）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出置信阈值、缺票和取消后的收尾、审计可读性、bulkhead、背压、运行时的预算上限 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
