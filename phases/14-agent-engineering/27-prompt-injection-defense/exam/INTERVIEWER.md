# 面试官手册：PVEGate（14/27）

候选人计时期间不要看。候选人手里只有 README、`pvegate/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 被拒绝时要不要告诉模型原因？ | "No. The model gets the refusal line and nothing else. The reason goes to the audit log." |
| 1 | 用户自己的消息里像指令的话要不要拦？ | "No. Only direct instructions from the user count as permission. We check arguments and tainted content." |
| 1 | 先问人还是先跑验证器？ | "Validator first, all of it. A call it refuses never reaches the human." |
| 1 | 规范化以后的参数能不能直接传给工具？ | "No. Normalization is only for detection. Tools get exactly what the model wrote." |
| 2 | 用户自己写的记忆也要过护栏吗？ | "Yes. Every write, whatever the source, as in the lesson's memory-write guard." |
| 2 | 存原文还是存规范化后的文本？ | "The original, byte for byte. We need it for incident review." |
| 2 | derived_from 里有不存在的 id？ | "KeyError, and nothing gets stored." |
| 2 | derived_from 的顺序要保留吗？ | "Yes. Give the parents back in the order they were written." |
| 3 | 窗口比较区分大小写吗？ | "No. Casefold both sides." |
| 3 | 同一段文字用户写过，网页里也有？ | "Then it's the user's. It's not tainted." |
| 3 | 非敏感工具的参数来自网页，要拒绝吗？ | "No. Searching for what a page says is normal. Only sensitive tools refuse tainted arguments." |
| 3 | intent 不在表里？ | "It serves no tool. Refuse." |
| 3 | 拒绝理由里参数名怎么写？ | "Quote each one with repr, the way the other reasons name things." |
| 4 | 通知也要验证吗？ | "Yes, exactly like any other call. It just never gets a reply, not even an error." |
| 4 | 批量请求（JSON 数组）？ | "Out of scope. The model never sends batches." |
| 4 | 工具自己抛异常，或者参数名对不上？ | "Out of scope, the tests never do that. In production that's -32603 Internal error, or -32602 for arguments the tool doesn't take." |
| 4 | 被拒绝的调用要写进 history 吗？ | "No. Only tool output goes into the history. The model hears about the refusal from the error reply." |
| 4 | method 不是字符串，或者整行不是对象？ | "Invalid Request, -32600, with id null. The tests don't send one." |
| 5 | 结果按什么顺序？ | "Document order: a node's own text, then its parts in order." |
| 5 | 同一个附件挂在两封邮件下面？ | "Report it at every path where it shows up." |
| 5 | 超过 max_depth 的节点怎么办？ | "Report it as too deep and don't look inside it." |

## 每关：要看什么、提示、追问

### Part 1 修 PVE 会话（目标 12 分钟）

一个测试里叠了 4 个缺陷和几道护栏：

1. 被拒绝时，`Session.step` 把拒绝理由拼进了给模型的观察。理由里引用了注入标记（'ignore all instructions'），这条观察作为 tool_output 进了 history，下一次干净的调用就因为“tool_output 里有注入标记”被拒。错误在下一步才报出来，根因在上一步留下的观察文本里。
2. `normalize` 只做了 `lower()`，没有做 NFKC，也没有 strip。全角字母 `ＩＧＮＯＲＥ`、全角冒号 `SYSTEM：`、前导空格的 `   do wire ...` 都能绕过。
3. `_drop_invisible` 每删一个不可见字符就把剩下的字符串复制一遍，是 O(n·k)。测试里的页面有 14000 段，每段之间夹 3 个零宽字符，约 15.7 万字符，其中 4.2 万个不可见。本机这一步要 1.1–2.5 秒，限值 0.1 秒；改成一遍过滤后是 3–10 毫秒。
4. `Validator.assess` 声明了 `sensitive_tools` 却从来没用，send_message 不经人确认就发出去了（doctrine 5：send-message 由人决定）。

护栏：
- 工具输出里带注入，后面的调用照样要拦。为了修第 1 个缺陷而把 tool_output 排除出扫描，会在这里挂掉。
- 用户消息以 "Do a quick search ..." 开头，形状像指令，但它是用户自己的话（课里引的 OpenAI 说法：只有用户的直接指令才算授权）。扫 history 时把用户消息也扫进去，第一步就会被拒。
- 理由不给模型看，但要留在 `audit` 里。为了不泄露而把理由里的标记删掉，事后就查不到是哪条规则拦的。
- 带全角字母、中文和零宽字符的正常参数必须原样交给工具。把规范化后的参数传下去会挂。
- 规范化的顺序照 docstring：NFKC、删不可见字符、casefold，最后 strip。先 strip 再删不可见字符，会放过 `"\u200b  execute ..."`：零宽字符挡在最前面，strip 碰不到它后面的空格。
- 长页面末尾的注入照样要拦。为了提速只扫前面一段会挂。
- 验证器拒绝的调用不能交给人。三项检查都过了才轮到人：在扫 history 之前就问人，注入页面之后的 send_message 会去打扰人；每个调用都问人同样会挂。
- confirm 要由 `Validator.assess` 自己返回。把敏感工具的判断挪进 `Session.step`，这一关的流程照样走得通，可直接拿 `assess` 当验证器用的调用方（比如 Part 4 的 `serve`）就不会再问人了。测试最后一条断言直接问验证器。

可以接受的写法：NFKC 之后用 `lower()` 代替 `casefold()`，对这张全是 ASCII 的标记表结果一样；一遍过滤用 `str.translate` 或 `re.sub` 也都在限值以内。

看什么：是不是先读断言里的实际观察文本，看出拒绝理由在里面；是不是去看 history 里第 3 条是什么；每改一处就重跑。

提示：
- H1："What is in the history when the third call is assessed?"
- H2："The reason says some tool_output contains a marker. Which tool produced that output?"
- H3：直接指出 `Session.step` 里拒绝时的 observation。

追问：
- "Why not tell the model why it was refused?"（理由会把攻击文本原样送回上下文，还等于告诉攻击者哪条规则拦住了它；理由留在审计日志里）
- "One poisoned page and every later call is refused. Is that acceptable in production?"（课里的验证器偏保守；可以把那段内容隔离出上下文、重新规划，代价是可用性；Exercise 5 要量正常流量上的拒绝率）
- "The marker list is a blocklist. What would you add?"（来源标签和污点追踪、工具和目的地白名单、用小模型当验证器、每步安全评估）
- "Unicode tag characters can spell out a whole instruction that renders as nothing. normalize drops them. Is that enough?"（删掉以后检测器看不到那段话，可原文里还有，会原样进上下文；更稳的做法是把 tag 字符还原成 ASCII 再检测，或者见到 tag 字符就直接判为可疑）

### Part 2 带污点的记忆（目标 11 分钟）

坑：
- 原文必须原样存：`\r\n`、首尾空白、全角字母、零宽字符都要保留。存 `normalize(text)` 或 `text.strip()` 都会挂。规范化只用于检测，事后审计要看原文。
- 污点要传递：summary 的来源是 user_message，但它从 retrieved 的页面派生，所以有污点；digest 从 summary 派生，也有污点。只看父节点的来源标签会把 digest 算成干净的。
- 任何一个父节点有污点都算。重开后的 `later` 写的是 `[5, 4]`，第一个父节点干净，第二个有污点；只看第一个父节点会把它算成干净的。
- 护栏对所有来源都生效，和课里的 `memory_write_guard` 一样。只拦非用户来源会挂。
- 父 id 不存在时什么都不能留下。先插入并提交、再检查父 id，会留下一条孤立的记录。写成 `tainted or any(self.get(p).tainted for p in parents)` 也会挂：`any` 碰到第一个有污点的父节点就停，`[3, 99]` 里的 99 根本没查，不报 KeyError。
- 失败时把刚插入的行删掉也能过（`INTEGER PRIMARY KEY` 会复用这个 id），可以接受；追问两步之间进程崩溃会留下什么。加了 `AUTOINCREMENT` 的话 id 会被用掉，`later` 变成 7，测试会挂。
- `recall()` 返回的 Content 要带上存下来的污点。用默认值（按来源推断）会把 summary 当成干净的。
- derived_from 按写入时给的顺序读回：digest 写的是 `(3, 1)`，读回来也必须是 `(3, 1)`。用一张父子关系表存的话要带位置列，按父 id 排序读回会挂。
- 文本里有单引号，SQL 必须用参数绑定。

追问：
- "Taint never wears off. Isn't everything tainted after a month?"（是的，这是代价；可以让人审过以后显式清除污点，并记录是谁清的）
- "Why keep derived_from at all, when the flag is already computed?"（事后追查：出事时要能顺着来源链找到最初那个页面，这就是课里 doctrine 6 说的可审计）

### Part 3 参数来源检查（目标 12 分钟）

坑：
- 同一段文字用户写过、网页也写过，算用户的。不减去可信内容里的窗口，会把 `Bob <bob@example.com>` 当成污点。减法要按窗口做，不能按整串：这个参数整串不在用户消息里，可它每个出现在网页上的窗口也都出现在用户消息里。只在整串出现在用户消息里时才豁免，第一条断言就会挂。
- 信任看 `tainted` 标志，不看来源标签。HISTORY 最后一条是用户来源但有污点的记忆，按 `source == "user_message"` 判断会放过它。
- 参数里的字符串要递归找，列表和字典里的都算。只看顶层字符串会漏掉 cc 里的地址。
- 窗口下标是 `range(len - n + 1)`。少一个会漏掉最后一个窗口，`https://evil.biz` 只有最后 8 个字符是从工具输出里抄的。
- 比较前两边都 casefold。页面写的是 `Mallory@Evil.Example`，测试里的参数一个全小写、一个全大写；只对 history 做 casefold 会漏掉全大写的那个。
- 返回的参数名按参数顺序排，不要排序。
- 只有敏感工具才因为污点被拒；search 用页面里的词是正常的。
- 未知 intent 要拒绝，不能抛 KeyError，也不能当成“什么工具都能用”。
- `assess` 要把自己的 `min_run` 传给 `tainted_args`。漏传会用上默认的 8，`min_run=24` 的检查就会拦下一个只有 20 个字符的地址，而它根本装不下一个 24 字符的窗口。
- 最后一段把 Part 2 接进来：从页面摘出来的记忆，重开会话后读进 history，照样拦住发往攻击者地址的消息。

追问：
- "Why character windows and not exact equality?"（模型会在抄来的地址前后加字，或者只抄一段 URL）
- "How do you pick min_run?"（太短误报多，比如常见词；太长漏掉短地址；可以按参数类型设不同的值）
- "Where does this sit relative to Part 1?"（同一个验证器的两半：Part 1 看指令的形状，Part 3 看数据的来源）

### Part 4 单请求 PVE 与 JSON-RPC（目标 13 分钟）

坑：
- `handle_line` 是同步的单请求处理函数。外层 `serve` 已正确逐行调用它、即时 yield 回复；候选人不用实现生成器、队列或任务取消。
- 每个调用都要拿当前的原 history 验证，再按裁决决定是否执行。不能只把初始用户消息交给验证器；工具返回的内容必须带 `tool_output` 来源，不能提升成用户授权。空字符串也是工具输出。
- 通知的“不回复”和“不执行”是两回事。fetch 通知照样经过验证、运行，并更新后续调用看到的证据历史；只有回复被省略。
- confirm 只为当前调用向人提问，人同意才真正执行；refuse 和人否决都不能先产生 effect，普通 allow 不额外问人。
- 输出格式由测试的解析代码决定：每条回复一行 JSON，以 `\n` 结尾。少了换行，`json.loads` 会报 Extra data。
- 没有 `id` 成员的是通知：要验证、要执行，但不回复，走到错误分支也不回。测试里还有一个被拒绝的通知和一个方法不存在的通知；在单请求函数的出错分支提前返回错误回复、绕过通知门，就会多出 id 为 null 的回复。`id` 为 0 也是有 id，用 `if request.get("id")` 判断会漏掉它。
- id 原样回传，整数还是整数，字符串还是字符串。
- 空行跳过，不能当成解析错误回复。
- params 可以省略（`list_files` 就没写），这时工具不带参数调用。直接取 `request["params"]` 会 KeyError。
- 每个调用都对照“到这一步为止”的 history 验证。工具输出要在读下一行之前追加进 history，否则第二个请求看不到第一个请求抓回来的注入页面。
- 只有工具输出进 history。照 Part 1 的 `Session` 把 REFUSAL 也追加进去，后面每次验证看到的 history 都会多出几条。这里模型是从错误回复里知道自己被拒的。
- 被拒绝或被人否决的调用不能执行。先执行再看裁决会挂。
- 人同意了就照常执行。主场景之后单独有一个人同意的 delete_file。写成 `if verdict.action == "confirm" and not confirm(call)`、之后只在 action 是 allow 时执行，人同意的调用也会被拒。
- 拒绝的错误里只有 code 和 message。把理由放进 `error.data` 会挂，而且等于把拒绝理由又交给了模型，Part 1 修的就是这个。
- 给定传输循环每次把一行交给 `handle_line`，拿到回复就发出再读下一行；预读全流、newline 和编码由边界断言检查。
- 解析错误的 id 是 null；未知方法和参数不是对象分别回 -32601 和 -32602，这两种不调用验证器。docstring 里还写了 -32600 Invalid Request（整行不是对象，或者 method 不是字符串），测试没有覆盖。

追问：
- "Why refuse with an error instead of a result that says refused?"（调用方能按错误码区分“工具没跑”和“工具跑了但结果是这样”；主模型看到的文字仍然只有那一句）
- "A refused notification: how does the model ever find out?"（它不会知道；所以敏感工具可以规定不接受通知）
- "A request arrives with an id of null. Is that a notification?"（不是。按规范它是请求，要回复，回复的 id 也是 null；规范不建议用 null 当 id。用 `request.get("id") is None` 判断通知会把它当成通知，测试没有发这种请求）
- "The validator is a model call. What happens to latency?"（每个工具调用多一次推理；课里说这对大多数产品是便宜的保险；可以和主模型的下一步并行准备，但执行必须等裁决）

### Part 5 嵌套内容扫描（目标 12 分钟）

坑：
- 有效来源取路径上最不可信的那个。邮件里一段自称 user_message 的文字，仍然是 retrieved。
- 没写 source 的部分继承父节点的有效来源。
- 有效来源是 user_message 的指令是用户自己的话，不报告。根节点的 "Do summarise ..." 不能出现在结果里。
- 反过来，来源不是 user_message 的根节点，它自己的 text 也要查。只在遍历 parts 时检查子节点的写法，会漏掉根上的 `SYSTEM:`。
- 结果按文档顺序：先看自己的 text，再按顺序进入 parts，也就是深度优先的先序遍历。为了不递归而改成队列（广度优先）或者栈，找到的东西对，顺序不对。FORWARD 第三个顶层部分里的 "Override:" 就是为这个放的。
- 同一个对象挂在两个父节点下，两个位置都要报告，各自带自己的有效来源。按 `id(node)` 记已访问会漏掉第二个。
- 深度从 0 开始，max_depth 这一层还要读，再往下一层报告 too deep，并且不往里看：它自己的 text（`rm -rf the backups`）不读，它的 parts 也不进。直接跳过会漏掉，`>=` 会多报一层，先查 text 再判深度会多出一条 rm -rf。
- 自己包含自己的节点不会无限递归，深度上限会把它截住。报了 too deep 还接着进 parts，会在这里 RecursionError。
- 根没有 source、出现未知来源都报 ValueError。
- 可以接受：直接对来源名取 `min()` 也能过，因为这三个名字的字母序恰好和信任顺序相反。值得问一句为什么能过、再加一个来源会怎样。

追问：
- "Why trust the least trusted ancestor instead of what the node says about itself?"（来源标签本身也是攻击者能写的内容）
- "Why report too-deep content instead of skipping it?"（深度是攻击者控制的；跳过等于给注入留了藏身处）
- "Real emails are MIME trees. What changes?"（解码、字符集、HTML 里的隐藏文字；每一层都要保留来源）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback 和断言里的实际值、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出误报率、审计、延迟、攻击者能控制什么 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
