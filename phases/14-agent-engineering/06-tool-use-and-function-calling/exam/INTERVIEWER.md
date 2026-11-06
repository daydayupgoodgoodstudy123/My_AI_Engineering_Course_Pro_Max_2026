# 面试官手册：ToolCall（14/06）

候选人计时期间不要看。候选人手里只有 README、`toolcall/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | "5.0" 或 "1e3" 能转成 integer 吗？ | "No. Only a string JSON would write as an integer: an optional minus sign, ASCII digits, no leading zeros." |
| 1 | "07" 这种前导零呢？ | "Rejected. JSON doesn't allow it, and in some languages a leading zero means octal." |
| 1 | 没有 minimum 和 maximum 的参数，NaN 也要拒吗？ | "Yes. A non-finite number is never a valid argument." |
| 1 | 卡住的线程能杀掉吗？ | "No, Python can't kill a thread. Stop waiting, answer with the timeout observation, and keep serving other calls." |
| 1 | 日期只认 YYYY-MM-DD 吗，20260215 算不算？ | "Only YYYY-MM-DD, and it has to be a real calendar date." |
| 2 | 用例 id 能带 "/"、空格或者非 ASCII 字符吗？ | "Yes. Only '#' and line breaks are rejected, because ids go into TAP lines." |
| 2 | add 要不要存校验、强转之后的参数？ | "No. Validate them, but store exactly what you were given." |
| 2 | 用哪个 dbm 模块？ | "Whatever dbm.open picks. The test reads the file back with dbm.open too." |
| 2 | id 已经存在怎么办？ | "ValueError. A stored case is never replaced." |
| 3 | 21.0 和 21 算不算一样？ | "For a number parameter, yes. For an integer parameter, no." |
| 3 | 评分时要不要像 registry 那样把 "4" 强转成 4？ | "No. We're measuring what the model wrote, not what the runtime repaired." |
| 3 | Multi-Turn 的调用本身也要和可接受答案一致吗？ | "No. Only the final state counts." |
| 3 | 某一类一条用例都没有呢？ | "That category has no score, None. Leave its weight out and rescale the rest. No cases at all means no total." |
| 3 | 某条用例没有 attempt？ | "It's wrong, in every category. No answer isn't a refusal." |
| 4 | TAP 编号按用例顺序还是输出顺序？ | "Output order. The first line out is number 1." |
| 4 | 模型调用或者评分抛异常了？ | "Either way that case is not ok, with the error as its reason, and it counts as wrong. The other cases carry on." |
| 4 | 分数和计划行放哪？ | "At the end: the score comment, then the plan." |
| 5 | 引用能指向后面的调用吗？ | "No. Reject the whole chain before anything runs." |
| 5 | 支持 [-1] 这种负下标吗？ | "No. Only non-negative integers." |
| 5 | 引用夹在一段文字中间呢？ | "That's plain text. Only a string that is a reference as a whole gets resolved." |
| 5 | 结果里有一个长得像引用的字符串？ | "It's data. Never resolve it." |

## 每关：要看什么、提示、追问

### Part 1 修参数校验和超时（目标 10 分钟）

一个测试里叠了 4 个缺陷和几道护栏：

1. `_coerce` 的 number 分支放过 NaN 和无穷大。Python 的 json 模块会把模型输出里的 `NaN`、`Infinity` 读成 float，`"nan"` 这样的字符串 `float()` 也认，`1e999` 会溢出成 inf。NaN 和任何数比较都是 False，所以 `minimum` 和 `maximum` 都拦不住它（测验 Q9）。错误不在校验器里报出来，而是在工具里：测试里的 `set_thermostat` 调 `round(nan)`，观察是 `execution error: ValueError: cannot convert float NaN to integer`。根因在两层之上（dispatch → validate → _coerce）。
2. 字符串强转用的是 `int()` 和 `float()`。它们会接受 `" 7"`、`"+7"`、`"07"`、`"1_000"`、阿拉伯-印度数字 `"٣"`、`"7\n"`，以及 `" 2.5"`、`"2_5"`、`".5"`、`"2."`（测验 Q12）。docstring 规定只接受和 JSON 写法完全一样的数字字符串。
3. `format: date` 用的是 `re.match(r"\d{4}-\d{2}-\d{2}")`，2026-02-30 能通过。同样是工具先报错：测试里的 `book_room` 用 `date.fromisoformat` 算星期几，观察是 `execution error: ValueError: day is out of range for month`。课里要求格式用真正的解析器校验，不用正则。
4. `ToolDef.timeout_s` 从来没被读过（测验 Q8）。一个会卡 2.5 秒的工具，timeout_s=0.01，`dispatch` 等满了 2.5 秒才返回。
5. 护栏，每种常见的改坏写法都有一条断言接着：
   - 为了拒绝歧义，把所有字符串都拒掉：`"5"` 必须还能变成 5，`"-1"` 变成 -1，`"21.5"`、`"2.15e1"`、`"-0.2"` 都还是数。
   - `str.isdigit()` 或 `-?\d+`：Python 的 `isdigit` 和 `\d` 都认 Unicode 数字，`"٣"` 被放过；`-?\d+` 还放过 `"07"`。照 JSON 的语法写成 `-?(?:0|[1-9]\d*)` 也不够：首位限定了 ASCII，后面的 `\d` 还认 Unicode 数字，`"1٣"` 和 `"2.٥"` 被放过。`decimal.Decimal()` 和 `float()` 一样宽松，`" 2.5"` 被放过。
   - 只去掉首尾空白：`"+7"` 还在。`re.match` 加 `$`：`$` 能匹配末尾换行之前的位置，`"7\n"` 被放过。
   - 只用 `math.isnan`：`Infinity` 被放过。列一张 `"nan"`、`"inf"` 的写法表：`"1e999"` 不在表里。只在字符串分支检查有限性：json 读出来的 NaN 是 float，被放过。
   - `datetime.strptime(text, "%Y-%m-%d")`：会接受 `2026-2-5`。只用 `date.fromisoformat`：Python 3.11 起它还接受 `20260302` 和 `2026-W10-1`，参考答案用 `fromisoformat(text).isoformat() == text` 把这两种挡掉。正则全匹配加月份 1 到 12、日期 1 到 31 的范围检查：2026-02-30 还是能过。先查长度是 10 再交给 `fromisoformat`：`2026-W10-1` 也是 10 个字符。按 `-` 切开、转成整数交给 `date()`：`2026-2-5` 和末尾带空格的 `2026-03-02 ` 都能过。`2028-02-29` 必须通过，手写的天数表别忘了闰年。
   - 在 `with ThreadPoolExecutor() as pool:` 里等结果：超时后退出 with 块时 `shutdown(wait=True)` 会等那个卡住的调用，还是 2.5 秒。等工具返回后再看耗时，也是 2.5 秒。
   - 整个 registry 共用一个单线程的池：卡住的调用占着唯一的线程，`lookup` 排在后面，2 秒后也超时。
   - 用 `ToolDef.timeout_s`（类上的默认值 5.0）而不是这个工具自己的值：卡住的调用 2.5 秒后自己返回了，没到 5 秒，于是被当成正常结果。
   - 线程里不把异常交回来：`flaky` 抛的 ConnectionError 丢了，`dispatch` 在取结果时报 `KeyError: 'content'`。

看什么：是不是先读观察内容，意识到出错的是工具而值不该到工具手里；有没有在 REPL 里试 `float("nan") < 5`、`int(" 7")`；每改一处就重跑；改超时前是否先想清楚线程杀不掉这件事。

提示：
- H1："The observation says the tool failed. Should the tool ever have seen that value?"
- H2："What do `float('nan') < 5`, `float('nan') > 30` and `int(' 7')` return?"
- H3：直接指出对应的那一处（number 分支、两个字符串分支、`_DATE`、`dispatch` 里直接调用 executor 的那一行）。

追问：
- "The stuck call keeps running after we answered. What if it writes to a database a second later?"（副作用照样发生。真正的隔离要靠子进程或容器，超时后能杀掉；或者让工具幂等，或者带一个取消令牌让工具自己检查）
- "Every timed-out call leaves a thread behind. What happens after a thousand of them?"（线程越来越多。用有上限的池会在全部占满后让正常调用也排队超时；要给每个工具限流，或者把慢工具放进单独的进程）
- "Where does coercion start to hide real bugs?"（课里练习 2。每一次修复都让"模型输出类型错了"这个信号消失；修了也要计数，按工具统计）
- "Could you reject NaN when parsing the JSON instead?"（可以，`json.loads(text, parse_constant=...)` 在解码时就拒掉 NaN 和 Infinity；但 `1e999` 不走 parse_constant，校验器里的有限性检查还是要有）
- 测试没有覆盖、但可以聊的：number 参数收到 int 时参考答案按 docstring 返回 float，返回原来的 int 测试看不出来；`"-0"` 按 JSON 的写法是合法整数；`signal.setitimer` 也能做超时，但只在主线程里有效。

### Part 2 用例库（目标 12 分钟）

坑：
- 每条用例一个 dbm 键，值是 JSON。dbm 读回来的键是 bytes：`str(key)` 得到的是 `"b'book/ada 1'"`；要按 UTF-8 解码，按 Latin-1 解码的话 `zürich` 变成乱码。
- `dbm.open(path, "n")` 每次都新建一个空库，重开后什么都没有；要用 `"c"`。默认的 `"r"` 打不开还不存在的文件。
- 键要能还原出原样的 id。`"rename report"` 和 `"rename_report"` 是两条不同的用例，把空格换成下划线当键，第二条会撞上第一条。
- `ids()` 要排序。dbm 的 `keys()` 是哈希顺序（macOS 上是 ndbm），不是插入顺序。`cases()` 按 `ids()` 的顺序。
- add 要用 Part 1 的 `validate` 检查每一个可接受答案，但存的是原来的参数。只查第一个答案的话，第二个答案里的 `people: 40` 就进了库。`validate` 返回的是强转后的值，number 参数上的 200 会变成 200.0；把它写回调用方的 `call.args` 也一样，存进去的和调用方手里的用例都变了。Python 里 `200 == 200.0` 为真，普通的 `==` 看不出来，所以测试用 `typed()` 把每个值和它的类型一起比较。
- 读回来的调用是 `Call` 对象，不是 dict。
- 先查完所有问题再写入，被拒的用例不能留在库里。id 重复要报 ValueError，不能覆盖。未知 id 报 KeyError，不能返回 None。
- 工具名不在目录里时要先报 ValueError，直接 `schemas[call.name]` 会报 `KeyError: 'book_rooms'`。
- 其他拒收条件都在 docstring 里：id 带 `#` 或换行、未知类别、空答案、Hallucination 带答案、Live 和 Non-Live 没有答案、Multi-Turn 和 Agentic 缺状态。成对的条件两类都要查，测试里 Live 没有答案、Agentic 缺初始状态各有一条。
- 值必须是 JSON：用 pickle 或 shelve 能原样读回，但测试直接打开 dbm 文件检查每个值。
- `close()` 要真的关掉。本机 Python 3.12 的 ndbm 把写入留在缓冲里，不关就重开，`ids()` 是空的；gdbm 第二次打开时报锁错误；3.13 起默认的 dbm.sqlite3 写入立刻可见，这时测试看不出来。

追问：
- "Two CI jobs add cases at the same time?"（dbm 不保证多进程并发写。要么单写者排队，要么换 SQLite）
- "Which backend did dbm.open give you, and what if a teammate is on Python 3.13?"（`dbm.open` 选第一个能用的：3.13 起是 dbm.sqlite3，然后是 gdbm、ndbm、dumb；文件格式和文件名都不同，`dbm.whichdb` 能认出来。要跨机器共享，就固定一种后端）
- "The scorer treats 200 and 200.0 alike. Why keep them apart in the bank?"（库不是评分器。导出给别的工具、和上一版用例做 diff、复现一个已发布的分数，都需要原样的数据；评分规则以后也可能改）
- "A tool's schema changes after the case was written?"（目录跟着用例一起存，本题就是这样；也可以给目录算哈希，schema 变了就让用例失效）
- 测试没有覆盖、但可以聊的：id 只有空格算不算合法，docstring 没有规定；id 里单独的 `\r` 测试没有检查，参考答案和 `\n` 一样拒收。

### Part 3 BFCL 式评分（目标 14 分钟）

坑：
- AST 匹配。参考答案把每个调用变成一个可哈希的规范形式：两边都把有 default 的缺省参数补上，number 参数的值转成 float，再用 `json.dumps(sort_keys=True)`，最后用 Counter 比较两边的多重集合，有一个可接受答案对上就算对。
  - 参数顺序无关：不排序就比 JSON 文本，键的顺序一变就对不上。
  - 用 Python 的 `==` 比较值：`4.0 == 4` 为真，integer 参数会放过 4.0。比较 JSON 文本又不做数值规范化：number 参数上的 200 和 200.0 对不上。
  - 不做强转：integer 参数写成 `"4"`、number 参数写成 `"200"` 都是错答案，虽然 registry 运行时会把它们修好。评测量的是模型写了什么（测验 Q12：强转会让模型的错误从指标里消失）。
  - 缺省参数等于它的 default，不是通配符。没有 default 的参数，两边要么都给、要么都不给。
  - 工具名也要比：`get_forecast` 和 `get_weather` 的 schema 一模一样。
  - 并行调用顺序无关，但条数要对：按顺序 zip、用 set 比、"每个调用都能在答案里找到"，分别会放过顺序不同、重复、多一条的情况。
  - 目录里没有的工具：不先判断就去查 schema 会崩（AttributeError 或 KeyError）。
  - 字符串原样比较。`Zürich` 和 `Zurich` 两种写法都算对，是因为它们是两个可接受答案，不是因为做了规范化。
  - 规范化要在副本上做。直接在 `call.args` 上补 default、转 float，可接受答案也会经过同一个函数，用例就被改了（`book/ada 1` 的 200 变成 200.0）；对答案就地 `answer.sort()`，`rename_report` 里两个调用的顺序也被改了。测试在 AST 那一段结束时和整个测试结束时各比较一次 CASES。
- 状态式评估。从 `initial_state` 的深拷贝开始，通过 `FakeDrive.registry(case.tools)` 按顺序重放，比较整个状态。
  - 直接把 `case.initial_state` 交给 FakeDrive，或者只做浅拷贝：`files` 这个字典被改掉，用例本身变了。
  - 遇到失败的调用就停：模型看到错误后改正了，后面的调用也要重放。
  - 只用这条用例提供的工具：用 FakeDrive 的全部工具，或者绕过 registry 直接调 `drive.call`，没提供的 `copy_file` 也能跑，状态就对上了。按名字过滤之后再直接调 `drive.call` 也不行：参数校验是 registry 做的，`text` 写成数字的 `write_file` 应该被拒掉、什么都不改，直接调就把文件写进去了。
  - 按原来的顺序重放，比较时连文件内容一起比。
- 用哪种方法由类别决定：Multi-Turn 带着可接受答案也只看状态，Live 带着状态也只看调用。
- Hallucination：任何调用都算错，哪怕调的是目录里真有的工具。没有 attempt 和"什么都没调用"是两回事：前者在每一类都算错。`score_run` 里 attempts 缺的用例要按 `None` 交给 `grade`，写成 `attempts.get(id, [])` 的话，缺了回答的 Hallucination 用例就成了对的。
- 加权：先求每一类的正确率，再按 40/30/10/10/10 加权。没有用例的类别分数是 None，它的权重去掉，其余的重新归一化；一条都没有时 total 是 None。完整那组数据的 total 是 0.2667；按全部用例算一个正确率是 0.571，各类不加权平均是 0.533。只有三条用例的那组是 0.5，把空类别当 0 分是 0.1。attempt 里有不属于这次运行的用例，报 ValueError。

追问：
- "AST says wrong, state says right. Which do you trust?"（有副作用的任务看状态，这正是 V3 引入状态式评估的原因；单轮意图看调用。两者都看能分出"做对了但方式不对"）
- "Is rescaling the weights fair?"（只有类别相同的两次运行之间才可比；报告里要写明这次跑了哪些类别。和完整的五类总分放在一起比是不对的）
- "Some checkers list acceptable values per parameter instead of whole answers. What changes?"（可接受答案的组合数会乘起来；匹配不再是等价关系，并行调用要做二分图匹配，贪心可能配错）
- "The model omits an optional parameter that has no default, and the answer gives it. Always wrong?"（按本题规则是错的；也可以在用例里多列一个不带这个参数的答案）
- "The runtime would have coerced '4'. Should a call like that really count as wrong?"（评测是为了量模型，把修复算对就量不出模型多常出错；可以另报一个"运行时修复后正确"的指标）

### Part 4 TAP 流水线（目标 12 分钟）

坑：
- 要写成 async generator。写成普通的协程函数，测试报 `'async for' requires an object with __aiter__ method, got coroutine`。
- 参考答案：每条用例一个 task，用 `Semaphore(concurrency)` 限流，判完就放进一个队列，生成器从队列里取，按取出的先后编号。
  - 按用例在列表里的位置编号，行号就乱了。TAP 的编号是输出的先后。
  - 不限流、按 `concurrency` 一批一批跑、一次只跑一条，完成的顺序都和"空出一个位置就按顺序开始下一条"不同。按测试里的延迟，正确的顺序是 weather、rename report、no tool、clean up、rename_report、book。
  - 全部判完再输出，或者先把每条用例都启动了再开始输出：第一行出来得太晚。测试记下了第一行出来时已经完成了几条，必须是 1。
- 异常：模型调用和评分外面都要包 `try/except Exception`，原因写成 `error: <类型>: <消息>`，多行的消息用空格接成一行。异常直接冒出来，那个 task 不会往队列里放结果，生成器会一直等，测试 3 秒后报 TimeoutError。测试里两种异常都有：模型抛 RuntimeError；一条目录里没有 description 的 Multi-Turn 用例，评分时 `FakeDrive.registry` 报 `KeyError: 'description'`。只把 `await model(case)` 包进 try，后一种还是 3 秒后 TimeoutError。
- 出错的用例算错。把异常当成"没有调用"，Hallucination 那条就成了 ok；把出错的用例从分数里去掉，分数从 0.5500 变成 0.6111。
- 最后两行是 `# score 0.5500` 和计划行 `1..6`。分数保留四位小数，没有用例时写 `-`，计划行是 `1..0`。
- 读者提前停下（`aclose()`）时，要在 finally 里取消还在跑的 task，并且等它们真正结束。只调 `cancel()` 不等，`aclose()` 返回时取消还没生效。`gather` 不加 `return_exceptions=True`，被取消的 task 让它抛出 CancelledError，`aclose()` 也跟着抛。
- `concurrency` 小于 1 报 ValueError。`Semaphore(0)` 会让所有 task 永远等下去。
- 测试没有覆盖、但可以聊的：取消之后只 `await asyncio.sleep(0)` 一次也能通过，因为替身模型被取消时不再等别的东西，真实客户端的清理可能要好几轮；`except BaseException` 会把取消也吞成一条错误判定，测试看不出来，但 task 结束时不再是 cancelled 状态。

追问：
- "The model API returns 429 for one case. Retry or fail?"（在预算内退避重试，记下重试次数；不管怎样都不能算成正确的拒答）
- "Is the line order stable between runs?"（不稳定，取决于延迟；下游按 id 处理，TAP 的编号只是输出的位置）
- "How do you make a run reproducible?"（温度 0，记下模型的原始输出，事后离线重新评分。这就是要把用例和调用都存下来的原因）
- "1,000 cases and a rate limit of 50 requests a minute?"（固定并发数不够，要按时间限流，比如令牌桶）
- "Why does the bank reject '#' in ids?"（id 原样写进 TAP 行，`#` 后面是注释和类别，换行会把一行拆成两行）

### Part 5 调用链引用（目标 12 分钟）

坑：
- 先做一遍静态检查，再执行任何一步：call id 重复、引用自己、引用后面的调用、引用不存在的调用、格式不对的引用，都在任何调用执行之前报错。在执行到那一步时才检查，前面的调用已经执行了，副作用收不回来。存结果的时候才发现 call id 重复，也是同一个问题：前一个同名的步骤已经执行了。静态检查也要递归进嵌套的 dict 和 list。
- 语法：以 `$<call id>.result` 开头的字符串就是引用，后面跟 `.field` 或 `[index]`。字段名不能以数字开头，`.0` 这种 JavaScript 式的下标不合法（字段名写成 `\w+` 就会放过它，到执行时才报错，`lookup` 已经跑过了）；下标不能是负数，否则 Python 会悄悄取最后一个。格式不对的引用要报错，不能当普通文本传下去。
- 解析时要检查类型：`.field` 要求是对象而且有这个键，用 `.get()` 会把缺失的字段变成 None；`[index]` 要求是数组，Python 的字符串也能按下标取，`"closed"[0]` 是 `"c"`，所以 `try: value[key]` 接住 KeyError、IndexError、TypeError 的写法也不够；在 None 上用 `in` 会冒出 TypeError，要报 ChainError。
- `ChainError.at` 是从 `$` 到出错那一步（含）的那段文本，`call_id` 是参数里带着这个引用的那一步。
- 解析出来的值保持原来的类型：2 不能变成 `"2"`。只有整个字符串是引用时才解析，夹在文字里的保持原样。
- 结果是数据：工单标题里的 `"$c1.result.owner"` 不能再解析一次。工具返回的内容来自外部，这和提示词注入是同一个道理。
- 每一步只执行一次。按需求值、每次引用都重跑一遍的话，`search_files` 会在状态变了之后再跑，结果也跟着变。
- 不改动传进来的 steps。就地替换以后，同一条链第二次重放时已经没有引用了。

追问：
- "Why not allow forward references and sort the steps topologically?"（记录下来的链是一条轨迹，顺序本身就是记录的一部分；有副作用的调用不能随便换顺序，模型当时也是按这个顺序看到结果的）
- "A step fails halfway through. What does the caller need?"（哪些步已经执行、结果是什么，最好还有一个能接着跑的位置；工具幂等的话重跑才安全）
- "Should a resolved value be a copy?"（工具可能会改自己的参数，不拷贝的话，前面那一步的结果也被改掉了。参考答案做了深拷贝）
- "'$call_1' without '.result' passes through as text. Is that safe?"（拼写错误会被当成普通文本。更严格的做法是所有以 `$` 开头的字符串都必须能解析，字面量的 `$` 写成 `$$`）
- 测试没有覆盖、但可以聊的：dict 的键里出现引用不解析；执行器抛出的异常原样冒出，后面的步骤不执行（02 ReWOO 那课专门讲失败传播，这里不考）。

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读观察和 traceback、在 REPL 里试、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出线程杀不掉的副作用、并发写、可复现、限流、不可信的工具结果 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
