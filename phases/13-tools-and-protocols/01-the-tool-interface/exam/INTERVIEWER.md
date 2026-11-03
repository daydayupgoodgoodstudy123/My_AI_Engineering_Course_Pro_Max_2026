# 面试官手册：ToolLoop（13/01）

候选人计时期间不要看。候选人手里只有 README、`toolloop/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 参数不合法时，要不要像课里的代码那样直接结束？ | "No. Send the error back as that call's result and keep going. The model may fix its call." |
| 1 | 一个 turn 指什么？ | "One model call. max_turns caps how many times we ask the model." |
| 1 | 最后一轮模型还要调工具，要不要执行？ | "Yes. Run and observe them, then stop. That's what the lesson's loop does." |
| 1 | 工具名能重复吗？ | "No. A second tool with a taken name is a ValueError." |
| 2 | 一个文件存几段对话？ | "One log, one conversation." |
| 2 | 最后一行 JSON 是完整的，只是没有换行，算不算？ | "No. A line counts once its newline is on disk. Drop it." |
| 2 | 中间某一行坏了，能跳过吗？ | "No. A crash only tears the last line. Anything else is corruption: raise ValueError." |
| 2 | 最后一行有换行，但读不出来呢？ | "That's corruption too. Only a last line without its newline is torn." |
| 2 | 结果里有 NaN 怎么办？ | "Reject the message with ValueError. Our logs are standard JSON." |
| 2 | 键的顺序要保留吗？可以 sort_keys 吗？ | "Either is fine. Messages are compared by value." |
| 2 | 要 fsync 吗？ | "Flush is enough for us. Tell me what fsync would add." |
| 3 | Rule of Two 按轮算还是按请求算？ | "Per user request: from the user's message to the final answer, across every model turn." |
| 3 | 用户同意过一次，后面的调用还要问吗？ | "Yes. Every call that would bring all three together is confirmed on its own." |
| 3 | 参数不合法的调用要先问用户吗？ | "No. It can't run anyway, so it just gets the validation error." |
| 3 | 用户同意之后，这个调用自己的标志还算不算？ | "Yes. It ran, so what it read is in the request now." |
| 3 | 工具运行时抛了异常，它的标志算不算进请求？ | "Yes, it ran. The tests don't cover it." |
| 4 | trace 里要不要像课里那样带耗时？ | "No. A trace must be reproducible. Timings go to metrics." |
| 4 | 同一轮的多个调用能并发跑吗？ | "No. One at a time, in order, like run_loop." |
| 4 | 答案里有换行怎么办？ | "Every step is one line. That's why the values are JSON." |
| 4 | 不存在的工具在 trace 里怎么写？ | "An ERROR line, like a validation error, with the error result as JSON." |
| 5 | 调用图会有环吗？ | "No. It's guaranteed acyclic." |
| 5 | 目录是按调用顺序排好的吗？ | "No. A tool can come before the tools it calls." |
| 5 | 有好几条路径时报哪一条？ | "The alphabetically first, comparing name by name. It's in the docstring." |
| 5 | 调用了不在列表里的工具怎么办？ | "ValueError, and name the missing tool." |

## 每关：要看什么、提示、追问

### Part 1 修 tool loop（目标 12 分钟）

一个测试里叠了 4 个缺陷和几个护栏：

1. `tool_message` 给 tool 消息另造了一个 uuid 当 id。错误不在 observe 报出来，而是在下一轮：模型替身按 call id 回查自己上一轮调用的结果，在 `model.py` 里报 `KeyError: 'call_1'`。
2. `validate` 把 `True` 当成 number。bool 是 int 的子类，`isinstance(True, (int, float))` 为真，`add(a=True, b=2)` 通过校验，执行器算出 3。
3. `range(1, max_turns)` 少跑一轮。正好在第 5 轮作答的请求被报成触发了断路器。
4. `Registry` 用列表存工具，重名检查、`get` 和 `in` 都线性扫描。装 7000 个工具是 O(n²)，本机 0.7 到 1 秒。
5. 护栏：一直要调工具的替身必须恰好在第 5 轮停下并给出 `max_turns`，删掉断路器的话，替身在第 101 次被问时报错；在第 5 轮作答时 `turns` 必须是 5，把 range 改成 `range(max_turns)`、从 0 数轮次，会少报一轮；最后一轮要的调用必须真的执行，只回一条错误结果不算；参数非法时执行器一次都不能跑；只接受 float 会把 35 这样的合法整数挡掉；重名仍要报 ValueError；注册顺序要保留。

看什么：是不是先读 traceback，再顺着调用链往上游找；有没有打印 history 看 tool 消息的 id；每改一处就重跑。

提示：
- H1："Which message is the model looking for, and which one did it get?"
- H2："Print the history at the start of turn 2. What id does the tool message carry?"
- H3：直接指出 `tool_message` 里的 id。

bool 那一层：H1 "What did validate return for a=True?"，H2 "What is isinstance(True, int)?"

追问：
- "Where else does bool-is-int bite?"（enum：`True in [1, 2]` 为真；`0 == False`；以后加 integer 类型时同样要先排除 bool）
- "Calls on the last turn run, but the model never sees their results. Is that right?"（取舍：执行了却不回填；也可以最后一轮不执行，但要告诉模型为什么停）
- "The model sends the same invalid call five times. What should the host do?"（按“同一个错误”计数熔断，而不只靠总轮数）
- "After your fix, is get() still a scan? And `in`?"（只把重名检查换成 set、`get` 还在扫的修法，会被 3500 次 `get` 抓住；`get` 改成字典、`__contains__` 还在扫的修法测试抓不住，但 `rejection` 每个调用都要查一次 `in`，工具一多，每次校验都是 O(n)）

### Part 2 会话日志（目标 13 分钟）

坑：
- NaN 和 Infinity：`json.dumps` 默认会写出 `NaN`、`Infinity`。Python 自己读得回来，但这不是标准 JSON，别的读者会报错。要 `allow_nan=False`，而且拒绝时什么都不能写。
- `json.dump(obj, f)` 是边编码边写文件的：遇到 NaN 时前半行已经进了缓冲区，下一次 append 接在这半行后面，整行就坏了。测试在拒绝之后又 append 了一条，再重开检查。
- 不 flush：句柄一直开着时，几 KB 的写入都停在 Python 的缓冲区里，进程一死，另一个进程什么也读不到。
- 非 ASCII 要原样写（`ensure_ascii=False`）。默认的 `\u00fc` 这种转义，测试在文件里找 `Zürich` 和 `☔` 时会挂。
- 崩溃留下的半行，判断标准是“最后一行没有换行”，不是“解析失败”。测试里有两种：切在一个 emoji 中间（整个文件按 UTF-8 解码会先报 UnicodeDecodeError），以及整行 JSON 完整、只差换行（靠解析失败来判断的写法会把它留下）。
- 丢掉半行之后要把文件截到最后一个换行。只在读的时候跳过，下一次 append 会接在半行后面。截断位置按字节算，按字符算会切进前一行。
- 中间的坏行不是崩溃造成的，要报 ValueError，不能跳过。最后一行如果换行还在、内容却读不出来，同样是损坏。测试先坏中间一行，再坏最后一行，只对最后一行网开一面的写法会在第二个文件上挂。

追问：
- "The caller edits a message dict after append, or the list messages() gave back. What does the log hold now?"（只存引用、或者把内部列表直接交出去的话，内存里的历史会跟着变，和文件对不上；参考实现把写出去的那一行再解析一次，messages() 返回副本。测试没有覆盖）
- "Why split on LF only? bytes.splitlines() passes the tests."（这里能过，因为 json.dumps 会把字符串里的 CR 转义，日志自己写不出裸的 CR；但 splitlines 把单独的 CR 也当行尾，而这份日志约定的行尾只有 LF）
- "Two processes append to the same log at once?"（追加模式保证每次 write 落在末尾，但一行要一次写完；多个写者还是要加锁或者排队）
- "flush vs fsync?"（flush 只交给操作系统；断电不丢要 fsync，代价是每次几毫秒）
- "The log grows forever. Then what?"（按会话分文件、轮转、压缩旧会话，或者换成数据库）
- "post_id 1853205730212356097 in a JavaScript client?"（超过 2^53，JS 的 Number 会丢精度；这种 id 应该存成字符串）

### Part 3 Rule of Two（目标 12 分钟）

坑：
- 范围是一次用户请求，不是一轮：第 1 轮 fetch_page 带进不可信内容，第 2 轮 read_contacts 带进敏感数据，第 3 轮的 send_email 才凑齐三项。每轮清零的写法一次都不会问。
- 同一轮里的调用按顺序算，前一个调用带进来的污点，后一个就要算上。
- 只有两项时不问，凑齐三项才问。
- 只有 consequential 的调用会被拦。先发邮件、再读网页和通讯录，不需要确认；把“做过有后果的动作”也当成一项累计，会去问 read_contacts 这种纯工具。
- 调用自己的标志也算：forward_inbox 一个工具就占齐了三项。
- 被拦的调用没有运行，它的标志不能算进请求。先更新污点再判断的写法会在这里挂。参数不合法的调用同样没有运行：参数不对的 fetch_page 什么也没读到，后面只剩敏感数据加发信，不用问。
- 反过来，用户同意后运行的调用，它自己的标志照样算进请求。forward_inbox 一个调用就带进了不可信内容和敏感数据，用户同意之后，后面再发邮件还要问。把确认单独写成一个分支、只在不需要确认的分支里更新污点，会漏掉这一条，而且漏的方向是放行。
- 每个调用单独确认：同意过一次，不代表后面的调用也同意，也不代表请求被“洗干净”了。测试里三封邮件依次是同意、拒绝、同意。
- 被拦的调用也要有一条带自己 id 的 tool 消息，否则下一轮替身报 KeyError；拦下一个调用后，这一轮剩下的调用照常处理。
- 先校验再问：参数不合法、工具不存在的调用不应该打扰用户。
- 污点不能放在模块级变量或 registry 上，否则会带进下一个请求。

追问：
- "Untrusted input plus sensitive data, no consequential tool. Any risk left?"（模型的回复本身也可能把数据带出去，所以有些宿主把“渲染回复”也算作有后果的动作）
- "Can you scope the taint more finely?"（按数据流追踪：只有真正流进参数的不可信内容才算；代价是实现复杂）
- "The lesson says 'a single turn'. What scope fits a chat that keeps its history across requests?"（范围跟着模型的上下文走：下一个请求如果带着上一次读到的网页，污点也要跟过去；本题每个请求都从空历史开始，所以按请求算）
- "What if confirm raises or times out?"（fail closed，当作拒绝）
- "Who enforces this, the host or the tool server?"（宿主。工具自己声明的标志只是提示，可能被投毒，课里把这部分留到第 13 章 15 课）

### Part 4 trace 流（目标 13 分钟）

坑：
- 格式由测试的解析代码决定：每一项是一行，以 `\n` 结尾；USER、args、EXECUTE、ERROR、MODEL 后面都是 JSON。
- 照抄课里的 EXECUTE 行会带上 `[0.01 ms]`，JSON 解析报 Extra data。
- `json.dumps` 默认带空格，默认转义非 ASCII，两样都过不了。
- 答案里有换行，原样输出会让一项里有两行。
- 每一步发生就 yield。把一轮的行攒起来一起发，测试的探针会发现第一条 DECIDE 到达时三个执行器都已经跑过了。args 行也属于 decide 这一步，要在执行前发出，探针同样检查第一条 args 行。
- 不存在的工具和参数不合法一样，写 ERROR 行，后面是 JSON 的错误结果。照抄课里的 `ERROR : unknown tool X` 是纯文本，解析报 Expecting value。
- tool 消息的 content 是结果本身。照抄课里的 `"content": json.dumps(result)`，或者直接复用 trace 行里那段 JSON 文本，模型读到的就成了字符串。测试会检查替身读到的结果。
- 模型是 async 的，要 await。执行器有同步也有异步的：异步的结果要 await，而且 await 里抛出的异常也要变成错误结果，`execute()` 里的 try 包不住后来的 await。
- 执行器抛异常也算跑过，写 EXECUTE 行；ERROR 行只给没有运行的调用。
- 断路器那一行只出现一次。最终答案后面用 `break` 而不是 `return`，会多出一行 LOOP TERMINATED。

追问：
- "The client goes away after three lines. What still runs?"（`aclose()` 在挂起的 yield 处抛 GeneratorExit；已经开始的工具会跑完；需要清理的资源放进 try/finally）
- "Why JSON for the user message and the answer?"（一步一行，能 grep，能重放，能比对两次运行）
- "When does the USER line go out?"（立刻，在第一次问模型之前。模型一次可能要好几秒；探针只看执行器，USER 行晚发测试也能过）
- "How would you send this to a browser?"（SSE 或 NDJSON 都行，每一行就是一个事件）

### Part 5 组合工具（目标 10 分钟）

坑：
- 传播要递归：plan_trip 经过 notify 才碰到 send_email。只看直接调用会把它判成 pure。
- 菱形：book_hotel 和 book_flight 都调 charge_card，actions 里 charge_card 只出现一次。
- 解释路径取字典序最小：按名字顺序，找第一个能到达有后果工具的被调用者。不是声明顺序；不是最短路径（wrap_up 最短的是经过 send_email 的那条，字典序最小的是经过 archive_receipts 的那条）；也不能只看排第一的被调用者（plan_trip 排第一的 ask_preferences 是 pure）。
- 本身声明为 consequential 的工具，路径就是它自己，即使它还调用别的工具（cancel_trip）。
- actions 是能到达的全部有后果工具，不在第一个有后果的工具那里停：handle_strike 经过 cancel_trip，还能碰到 charge_card 和 send_email。在第一个有后果的工具那里停下的只有 path。
- 叶子保留自己的分类：只看被调用者的写法会把 charge_card 判成 pure。
- 目录里的顺序是任意的：handle_strike 排在它调用的 cancel_trip 前面。按列表顺序一遍算完、默认被调用者已经算过的写法，会在 cancel_trip 上报 KeyError，或者把它当成未知工具。
- 用 visited 集合代替备忘：第二次走到同一个工具时什么也拿不到。先算的 handle_strike 已经走过 charge_card，轮到 charge_card 自己时就被判成了 pure。
- 未知的被调用者报 ValueError，并且写出它的名字。只在递归里用 `by_name[callee]`，抛出来的是 KeyError。

追问：
- "A ladder of 30 diamonds. How long without the memo?"（2^30 条路径；有备忘是线性的）
- "Should reads_untrusted and touches_sensitive propagate the same way?"（应该，组合工具的标志是它能到达的所有工具的并集，Part 3 的闸门才不会被组合工具绕过）
- "A chain 5000 tools deep?"（Python 默认递归上限是 1000，要改成迭代）
- "The lesson says pure tools are safe to call speculatively. Is every pure composite tool safe?"（前提是 calls 声明属实；声明可能是错的）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出规模、并发、持久化、失败处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
