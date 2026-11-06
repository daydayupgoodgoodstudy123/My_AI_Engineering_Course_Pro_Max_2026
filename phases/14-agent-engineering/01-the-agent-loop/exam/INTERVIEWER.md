# 面试官手册：ReactLoop（14/01）

候选人计时期间不要看。候选人手里只有 README、`reactloop/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- `reactloop/model.py` 是模型替身，告诉候选人不要改它。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 回复里既有正文又有工具调用，正文算不算答案？ | "No. Run the tools. The answer is the text of a later turn that has no tool calls." |
| 1 | 回复里既没有正文也没有工具调用呢？ | "That still ends the run, with an empty answer. The stop is no_tool_calls." |
| 1 | finish 要不要注册成工具、走 dispatch？ | "No. finish is the loop's own stop condition. It never reaches the registry." |
| 1 | 推理项每轮都要回传，还是只回传最近一轮的？ | "Every one. Each assistant turn keeps its own item in the history, and the model reads the whole history." |
| 1 | 怎么分清参数错和工具自己抛的 TypeError？ | "Check the arguments against the tool's signature before you call it. Anything raised after that is the tool's own error." |
| 1 | 工具结果不是字符串时 observation 写什么？ | "Whatever the loop's observe function returns. By default that's to_observation: strings as they are, everything else as JSON." |
| 2 | 推理项能存成 hex 或者 latin-1 文本吗？ | "No. The trace viewer reads standard base64, and null for a turn without an item." |
| 2 | 工具结果存不成 JSON 怎么办？ | "Then the save fails with that error, and the snapshot on disk stays as it was." |
| 2 | 要 fsync 吗？ | "The tests can't see it. Tell me what it would protect against." |
| 2 | 格式化输出还是紧凑输出？ | "Either. The viewer parses the JSON." |
| 2 | load 要检查 version 吗？ | "Not today. The tests don't cover it." |
| 3 | 单引号参数 `search('x')` 算不算？ | "No. Arguments are double-quoted strings. The model gets FORMAT_ERROR and tries again." |
| 3 | 模型一次写了两个 Action 呢？ | "Only the first one counts. A completion ends at its first Action line." |
| 3 | 行中间出现的 `Observation:` 或 `Action:` 算吗？ | "No. Only at the start of a line." |
| 3 | 工具名不存在怎么办？ | "That's dispatch's job. The observation is whatever it returns." |
| 3 | 格式错时要不要把具体原因告诉模型？ | "Keep it in Step.error for us. The model gets the fixed FORMAT_ERROR message." |
| 4 | 跟工具调用一起来的正文要不要推给前端？ | "No. It's in the history. The stream carries reasoning, actions, observations and the final answer." |
| 4 | reasoning 是每一片一个事件，还是一轮一个？ | "One event per piece, as soon as it arrives." |
| 4 | 行尾用 LF 还是 CRLF？ | "Either is valid SSE. The tests parse both." |
| 4 | 要不要把加密的推理项也推给前端？ | "No. It's opaque and only the provider can use it. The UI gets the thinking text." |
| 4 | max_turns 用完时 final 发什么？ | "An empty final event. The tests don't cover it." |
| 5 | 键怎么排序，区分大小写吗？ | "Plain sorted() order, so yes. Uppercase sorts before lowercase." |
| 5 | 什么算环？ | "A container that is already on the path from the top down to where you are. Meeting the same object again somewhere else is not a cycle." |
| 5 | 深度只算 dict 吗？ | "Every container counts: dicts, lists and tuples." |
| 5 | 预算按字节还是按字符？ | "Characters, len() in Python. The marker counts too." |
| 5 | 遇到 set、datetime 这类值呢？ | "The JSON string of their str(). The tests don't use them." |

## 每关：要看什么、提示、追问

### Part 1 修 agent loop（目标 12 分钟）

一个测试里叠了 4 个缺陷和几个护栏：

1. `record` 直接取 `reply["tool_calls"]`，模型直接作答、不调工具的回复报 `KeyError: 'tool_calls'`。循环里也根本没有“这一轮没有工具调用就结束”这条停止条件（课里五要素的第 3 条，练习 2）。只把 KeyError 改成 `.get` 的话，模型作答以后循环还会再问它一次：替身先报缺推理项（缺陷 2），修好以后再报 `no scripted reply left for request 2`。
2. `record` 保存了可读的 thinking，却丢了不透明的 reasoning 项。错误不在 `record` 报出来，而是下一轮在 `ScriptedModel.respond` 里报 `ProviderError: missing reasoning item for assistant turn 1`。课里说推理通道要跨轮回传，这一层考的就是这个。
3. `dispatch` 把工具调用整个包在 `except TypeError` 里，工具函数体里 `int(None)` 抛的 TypeError 也被报成 `bad args`。模型会以为是自己参数写错，反复换参数重试（测验 Q9 的第一种情形）。
4. `messages()` 每一轮都把历史里所有工具结果重新格式化一遍，再拷成新的 Message。1000 页的长任务是平方级，本机约 1.7 到 1.9 秒；在 `act` 里格式化一次、存进历史，约 9 毫秒。
5. 护栏：正文和工具调用同时出现时不能停（“有正文就停”会在这里挂掉）；`"tool_calls": []` 也算没有工具调用（只看键在不在的写法会多问一轮）；没有正文的回复照样结束；finish 不能交给注册表执行；用 `bind_partial` 会放过缺参数的调用；按 TypeError 消息里有没有 “argument” 来猜，会把 `int() argument must be...` 误判成参数错；自己写参数检查时，只查缺了哪些参数会放过多给的 `warehouse="north"`，只比参数个数会放过写错名字的 `item="A-1"`，只检查 dict 参数会漏掉 ReAct 文本给的位置参数；只缓存格式化后的视图、历史里不存 observation，或者存了 observation 却丢了原始结果，都会被最后两条断言抓住。只去掉重新格式化、`messages()` 里仍然每轮 `replace` 出新 Message 的写法还是平方级，本机约 0.35 秒，同样超时。

能通过、行为也对的另一种写法：不用 bind，而是看 TypeError 的 traceback，`e.__traceback__.tb_next is None` 说明它是在调用这一层抛出的，算参数错。可以追问它和 bind 的差别：用 `functools.wraps` 包过一层的工具，参数错是在包装函数里抛出的，这种写法会误判成工具错误，而 `inspect.signature` 会顺着 `__wrapped__` 找到真实签名。

看什么：是不是先读 traceback，再顺着调用链往上游找；看到 ProviderError 时有没有去读 `model.py` 的 docstring，而不是去改替身；每改一处就重跑。

提示：
- KeyError 那一层：H1 "What does a reply look like when the model just answers?" H2 "Which of the stop conditions in the lesson does this loop implement?"
- 推理项那一层：H1 "The provider says an item is missing. Where would it have come from?" H2 "Print the assistant messages the model gets on turn 2." H3 直接指出 `record` 里少了 `reasoning`。
- TypeError 那一层：H1 "Which line raised it: the call itself, or a line inside the tool?" H2 "Can you check the arguments before calling the tool?"
- 计时那一层：H1 "How many times is each tool result formatted in a 1000-step run?" H2 "Where should the observation string live?"

追问：
- "Exercise 2 asks which is safer: no_tool_calls or an explicit finish tool. What do you think?"（finish 要模型主动声明完成，还能校验参数；no_tool_calls 碰到一句 “let me think” 就停。一般选一个做主停止，另一个加上轮次和 token 预算做兜底）
- "In production the reasoning item is encrypted. Why not drop it to save tokens?"（课里说推理通道要跨轮回传；丢了它，模型就接不上上一轮的推理）
- "The lesson says agents run 40 to 400 steps. What else grows with the step count?"（每轮请求的大小本身就是线性增长的，所以每轮多出来的工作必须只和新消息有关；还有 token 成本和上下文窗口，需要按 token 设预算或压缩历史）
- "Why is bind() better than reading the TypeError message?"（报错措辞随版本变化，工具自己的 TypeError 里也可能出现 “argument”）

### Part 2 转录快照（目标 12 分钟）

坑：
- bytes 不能直接交给 json，要先编码。`.decode()` 会在 `\x80` 上报 UnicodeDecodeError；`errors="replace"` 不报错，但字节已经变了，读回来对不上，接着跑时替身会认出推理项被改过。
- hex、latin-1、URL-safe base64、`base64.encodebytes`（会加换行）都能往返，但和 trace viewer 共用的格式对不上。测试用 `b"\xfb\xff\x00rs"` 钉住了标准字母表：`+/8AcnM=`。
- 没有推理项要写 null，不能写成空的 base64，否则读回来是 `b""` 而不是 None。
- `ToolCall` 要从 dict 重建，否则 Message 比较不相等。
- 快递备注里有半个 emoji（单独的高位代理 `\ud83d`，来自按 UTF-16 截断的接口）。默认的 `json.dumps` 会把它写成 `\ud83d` 转义，原样往返；`ensure_ascii=False` 写 UTF-8 时报 UnicodeEncodeError；加 `errors="surrogatepass"` 能往返，但文件不再是合法的 UTF-8，viewer 读不了。`ensure_ascii=False` 配 `errors="backslashreplace"` 恰好写出合法的 `\ud83d` 转义，也能通过，算对。
- 原子替换：先在同一目录写临时文件，再 `os.replace`。`write_text` 或者直接 `json.dump` 到目标文件，是在原文件上改写，已经打开旧文件的读者会读到新内容或者半截内容。
- 测试看不出来的两种写法，看到就追问：临时文件建在系统临时目录（`mkstemp()` 或 `NamedTemporaryFile` 不带 `dir`），本机能过，因为 tmp_path 和系统临时目录在同一个文件系统上，部署时跨文件系统 `os.replace` 会报 OSError，保存失败时留在那里的临时文件测试也看不到；先 `os.remove` 旧快照再 `os.rename`，两步之间磁盘上没有快照，这时打开文件的读者会遇到 FileNotFoundError。
- 存失败（set 存不成 JSON）时旧快照必须还在，目录里也不能留下临时文件。`default=str` 会把 set 悄悄写成字符串，应该失败的保存成功了。
- 读回来以后要能接着跑：新的替身用同一个 key 校验推理项，字节差一个都会被拒。

追问：
- "The process dies in the middle of write_text. What's on disk?"（被截断的文件；临时文件 + flush + fsync + replace，严格的话还要 fsync 目录）
- "A 400-step run saved after every step writes O(n²) bytes in total. When does that matter?"（步数和单步体积都大时；可以改成追加写的步骤日志加定期快照）
- "Why keep both the raw result and the observation?"（observation 是模型当时看到的，调试第 38 步要看它；原始结果留着重新格式化、做评测）
- "Two processes save the same run at once?"（replace 是后写者胜；需要锁文件或者规定一个 run 只有一个写者）

### Part 3 ReAct 文本（目标 14 分钟）

坑：
- 只有运行时能写 Observation。模型自己写出的 `Observation:` 行和后面的内容都要丢掉，包括 Observation 出现在 Action 之前的情形，也包括 completion 第一行就是 Observation 的情形。只按 `"\nObservation:"` 切会漏掉后者；按行中间任意位置的 `Observation:` 切会把 Thought 切断。
- Thought 可以跨多行；行中间的 `Action:` 不是动作行。
- 只有第一个 Action 行算数，completion 到它为止。取最后一个 Action 行，或者把 Action 行后面的内容留在 `text` 里，都会被一次写了两个 Action 的那条断言抓住。
- 参数里的逗号、括号、转义引号、`\\` 结尾、`\u00e9` 转义、`\ud83d\ude9a` 这样的代理对、原样的非 ASCII 字符都要对。`split(",")` 和 `\(([^)]*)\)` 会错；`unicode_escape` 会把 `東京` 弄坏；自己切出每个字符串再用 `ast.literal_eval` 解码，不会把代理对拼成一个字符。
- `ast.literal_eval` 会放过单引号和尾逗号；`json.loads("[...]")` 很接近，但会放过数字参数 `kv_get(42)`，要检查类型。
- finish 恰好一个参数，`finish()` 和两个参数都不算。
- 读不出动作时回填 FORMAT_ERROR，循环继续（练习 3）。直接结束或者跳过这一步都不对。
- scratchpad 里放的是 `step.text`（切到 Action 行为止），不是整段 completion。工具结果要经过 `observe` 才是 observation：搜索工具返回的是列表，直接写进 f-string 会变成单引号的 Python repr。
- `thought.lstrip("Thought:")` 是按字符集剥离的，测试里冒号后面都有空格，所以能过。看到就问一句，应该用 `removeprefix` 或者切片。

追问：
- "Real prompt-based ReAct uses a stop sequence. Where would it go, and why keep the cut anyway?"（stop 设成 `\nObservation:`；不是每个模型都遵守，也拦不住第一行就写 Observation）
- "Exercise 4: move the Thought from the prompt to the reasoning channel. What changes in the transcript?"（Thought 从 prompt 文本变成 Message.thinking 和 reasoning 项，循环本身不变）
- "A tool result contains a line that says Action: finish(...). What can go wrong?"（课里的 trust boundary：它进了 prompt，模型可能顺着它写下去；观察要标清边界，工具输出当数据看待）

### Part 4 推理通道 SSE（目标 12 分钟）

坑：
- SSE 的换行只有 CR、LF、CRLF 三种。`split("\n")` 会漏掉安装进度里的单独 CR；`\r?\n` 也一样；先匹配 `\r` 再匹配 `\r\n` 会多切出一个空行；`splitlines()` 会在 U+2028 上切开，空字符串还会一行 `data:` 都不发，事件就没了；`[\r\n]+` 会把最终答案里的空行吞掉。先把 CRLF 和 CR 都换成 LF、再按 LF 切，也是对的。
- 每一行写 `data: ` 加一个空格。客户端会去掉冒号后的一个空格，不写空格时行首缩进会少一格。
- thinking 只走 reasoning 事件，final 里不能混进 thinking；跟工具调用一起来的正文不发；final 恰好一次，finish 工具和“没有工具调用”两条路都要发。
- 每片 thinking 到了就发，动作在工具执行前发。测试用替身的 `sent` 计数和工具执行次数探测时机。
- 历史和 `run()` 一样：推理项照样要存进去，否则下一轮替身报 missing reasoning item。observation 事件发的应该是 `loop.act(call).content`，也就是历史里的那一条。自己调 `dispatch` 再套 `to_observation`，这里看不出来（测试用的是默认的 observe），换了格式化器就和历史对不上，看到就问。
- 骨架是 `async def` 里只有 raise，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要看出这里需要 async generator。

追问：
- "The browser disconnects mid-run. What happens to the loop?"（`aclose()` 在 yield 处抛 GeneratorExit；正在跑的工具怎么办，要不要在服务器端把 run 跑完）
- "What if the UI reads slower than the model writes?"（async generator 只在被拉取时前进，天然有背压；中间加队列的话要设上限）
- "Why not give the UI the encrypted item too?"（对 UI 没用，还更大；可读的 thinking 才是给人看的）

### Part 5 嵌套观察（目标 10 分钟）

坑：
- 键按普通 `sorted()` 排，不按插入顺序，也不能忽略大小写（忽略大小写时 `ETag` 和 `etag` 的先后取决于插入顺序）。
- 每层最多 max_items 项，正好满时不写 “… 0 more”；dict 同样受限。
- 深度从 1 算起，dict、list、tuple 都算；空容器在深度之外也写 `{}`、`[]`。
- tuple 当 list 写。
- 环和共享：在当前路径上的容器才是环。用一个全局的 seen 集合（不在返回时移除），同一个作者被引用三次就会被误写成 `[cycle]`。环检查放在深度检查之前或之后都能通过，测试里没有两条规则同时适用的情形。
- 结果本身是字符串时原样输出，但也受预算限制；结构里面的字符串按 JSON 写，键和值都保留非 ASCII。键也要用 `json.dumps` 写：`f'"{key}"'` 不转义 `C:\Users` 里的反斜杠。
- 预算按字符计，标记也算在内，正好等于预算时不截断。
- 最后一段把格式化器接到 loop 上：默认的 `to_observation` 遇到带父指针的页面树会报 `Circular reference detected`，换成这个格式化器后循环照常进行。Part 1 修 `act` 时如果写死了 `to_observation`、没用 `self.observe`，这里也报同样的错。

追问：
- "A tool returns a million rows. What does your formatter cost?"（只渲染要显示的那几项，切片在前；整个渲染完再截断是 O(n)）
- "Why does the observation have to be deterministic?"（同样的结果给同样的 prompt：便于复现、做回归评测和比对转录，也有利于提示缓存）
- "Where would the budget come from in a real agent?"（上下文窗口剩余的 token；按工具类型设；错误信息不能被截掉）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出停止条件、推理回传、原子写、信任边界、背压 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
