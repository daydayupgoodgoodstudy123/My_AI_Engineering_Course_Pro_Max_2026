# 面试官手册：Critic（14/05）

候选人计时期间不要看。候选人手里只有 README、`critic/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 事实检查是在全文里找子串，还是整条 bullet 比？ | "Whole bullets. A bullet is wrong when its claim, normalized, is one of the known wrong facts." |
| 1 | 要列出全部问题，还是只报第一条？ | "Only the first, in the order the docstring gives. The lesson's verifier works that way." |
| 1 | 有验证器的时候，还要让模型自评吗？ | "No. CRITIC replaces the feedback step." |
| 2 | 文件格式可以自己定吗？ | "Yes, as long as it's UTF-8 text a person can read, round 0 is stored whole, and later rounds store only the lines that changed." |
| 2 | 文件坏了怎么办？ | "Rounds before the damage still read back. Anything that depends on the damaged record raises CorruptChain." |
| 2 | 会有两个进程同时 append 吗？ | "No. One writer at a time. Other instances read, or take over later." |
| 3 | 工具抛的不是 ToolUnavailable，而是别的异常？ | "That's a bug in the tool. Let it propagate. The tests don't cover it." |
| 3 | 草稿里一条 bullet 都没有？ | "It doesn't pass. Treat it like any failing draft. The tests don't cover it." |
| 3 | 事实库里查不到的 claim 算通过吗？ | "No. Not found means unverified." |
| 3 | "no progress" 里的两个轮次号分别指哪一轮？ | "The first is the round the repeated output would have been, the next one. The second is the earlier round that had it." |
| 4 | 客户端是按 token 收，还是按行收？ | "By line, and only after the guardrail has passed that line." |
| 4 | 单独一个 \r 算换行吗？ | "No. Lines end at \n. A \r right before it is part of the line break." |
| 4 | 空行也要过护栏吗？ | "Every line goes through the guardrail. The guardrail decides." |
| 5 | 每层缩进是四个空格吗？ | "Two spaces or one tab per level, and one outline uses one or the other." |
| 5 | 大纲比 limits 还深怎么办？ | "That's malformed: a ValueError naming the line. The tests don't cover it." |
| 5 | 空子列表会让父项失败吗？ | "Yes. That bullet fails, so every bullet above it fails too." |

## 每关：要看什么、提示、追问

### Part 1 修精修循环（目标 10 分钟）

一个测试里叠了 4 个缺陷和 1 个护栏，都来自课里的 `code/main.py` 和 Pitfalls：

1. `verify_external` 的 for 循环没用循环变量：循环体是课里写死的两条检查（paris 和 germany、everest 和 europe 同时出现），参考数据里的第三条 "the sun orbits the earth" 永远查不出。错误不在 `verify_external` 里报出来，而是在 `run_loop` 的结果里：CRITIC 在第 2 轮把一份带着错误事实的稿子判成了通过。
2. 长度检查把 "- " 算进去，又用了 `> 60`。课里写的是 "under 60 chars"，严格小于，而且只算正文。两处叠在一起：59 个字的正文被判超长；只修掉前缀，60 个字的正文又会被放过。那条 60 个字的正文最后一个字是句号，借 `normalize_claim` 量长度会把句号去掉，同样把它放过去。
3. `run_loop` 里是 `if ok: break`：模型第一轮自评说 "No issues." 就停，这就是课里的 rubber-stamp。课里的 2026 默认是：验证器通过，或者模型说没问题且已经跑了至少 2 轮，或者到了上限。同一处还有第二个问题：最后一轮失败后仍然调用 refine，这次 refine 的结果既不验证也不返回。照课里的规则写完整，两个问题一起消失。
4. 性能：`verify_external` 在每条参考事实的循环里都对整段输出重新 `lower()` 再找子串。2 万条事实、2000 条 bullet 时要 0.55 秒左右，限值 0.04 秒。每条 bullet 规范化一次，再到集合里查。
5. 护栏：为了"更鲁棒"改成比较词的集合（`frozenset(words)`），会把 "The earth orbits the sun" 当成 "the sun orbits the earth"。测试要求它通过。

另外两处要求不是预埋的缺陷，是常见改法会踩到的：critique 要按 bullet 顺序报第一条错误事实（先遍历参考事实、再看它在不在 bullet 里，速度够快，但报的是参考表里靠前的那条）；事实检查排在格式检查前面（逐条 bullet 同时查事实和长度，会先报出长度问题）。

看什么：是不是先看 pytest 打出来的 history 差异，找出是哪一轮、哪个函数给出了错误的判断；是不是注意到循环变量没用上；每改一处就重跑。

提示：
- H1："Which round got the wrong verdict, and which function gave it?"
- H2："What does the body of the for loop in verify_external actually use?"
- H3：直接指出 `fact` 没被用，请候选人说出规范化之后怎么和参考数据比。

追问：
- "This verifier only knows a list of wrong facts. What can it never catch?"（清单之外的一切错误。有依据的验证要找到正面的支持，这就是 Part 3）
- "Why does the model's own 'no issues' need two rounds, while the verifier can stop the loop at once?"（验证器有外部依据；同一个模型自评容易收敛到 "looks good"）
- "Lesson exercise 2: the verifier lets 30% of wrong drafts through. What does the loop do?"（它会在错的稿子上停下。课里的例子要两轮才修完，带着错误"通过"的概率约 0.3 + 0.7 × 0.3 = 0.51。办法是再加一个独立的验证器，或者抽样给人看）

### Part 2 修订差分链（目标 12 分钟）

坑：
- 按行切要保留换行符。`splitlines()` 不带 keepends、再用 `"\n".join` 拼回去，会丢掉末尾换行，把 CRLF 变成 LF，把单独的 `\r` 和 U+2028 都变成 `\n`。`splitlines(keepends=True)` 配 `"".join` 能精确往返，`split("\n")` 配 `"\n".join` 也能。
- 第 0 轮可以是空字符串。`if record.get("text")` 这类写法会把它当成差分轮。
- difflib 的 opcodes 要从后往前应用，或者边走边拼一个新列表。从前往后原地改列表，前面的插入和删除会让后面的下标错位。测试里有一轮同时在开头插入、在中间删除、在末尾修改。
- 只存变化的行。每轮存全文，或者把 equal 块的行也存下来，都会超出文件大小的上限。unified diff 带上下文行，"Asia" 那一行会在下一轮的上下文里再出现一次，`raw.count(b"Asia") == 1` 会挂。
- 校验：每条记录存一个摘要（比如重建出的输出连同 critique 的 sha256），读的时候核对。没有摘要，文件里改一个字母，读出来就是另一段文本。第 0 轮也要核对，测试会改坏第 0 轮；critique 也要算进摘要，测试会只改坏最后一轮的 critique。
- 只核对要读的那一轮也可以，前提是摘要算的是重建结果：摘要对得上，返回的文本就一定是写进去的那段。参考实现每一轮都核对，能指出坏的是哪一条。
- 损坏之前的轮次还要能读。一打开就校验整条链、发现问题就整体报错的写法会挂。
- 用 JSON 存时，`ensure_ascii=False` 会把非 ASCII 原样写出，这时如果用 `str.splitlines()` 切记录，会在 U+2028 处把一条 JSON 切成两半。用 `split("\n")` 或者逐行读文件就没问题。
- 每次 append 都要真正写进文件。测试在第一个实例还在用的时候，就开了第二个实例去读。

追问：
- "Why a digest per record instead of one for the whole file?"（能定位到坏的那一条，之前的轮次照样能读；append 之前也能先确认基准版本没坏）
- "Why no context lines?"（每个差分都应用在一个已知、已校验的基准上；上下文行是给基准可能变化的模糊打补丁用的）
- "What does autojunk do?"（序列有 200 项以上时，出现超过 1% 的项被当成垃圾项。opcodes 仍然正确，但差分可能变大；`autojunk=False` 让差分最小，代价是慢一些）
- "Two writers at once?"（落后的写者会对着错误的基准算差分；要加锁或者只留一个写者。有摘要的话，读的时候能发现）
- "The process dies halfway through an append. What does the next reader see?"（文件末尾是半截记录。逐条解析的话，之前的轮次照样能读，读这一轮报 CorruptChain；写者要先截掉半截行或者拒绝追加，否则新记录会接在半行后面。参考实现把解析不了的行当作坏记录，append 前重建上一轮时就会报错。测试只改坏记录的内容，不覆盖这种情况）
- "Reading round 10,000 of one loop?"（每隔 N 轮存一次全文，像视频的关键帧）

### Part 3 工具化核验（目标 12 分钟）

坑：
- 按工具分组调用之后，findings 要放回 bullet 的顺序。最顺手的写法是先处理完所有事实、再处理所有算式，结果的顺序就成了 1、3、5、2、4。
- 每个工具每次核验只调用一次，带上它的全部 claim。一条 claim 调一次，调用次数的断言会挂。没有 claim 的工具不调用，也就是课里说的 "do not pay the latency for a stub verifier"。
- 工具抛 ToolUnavailable 时，它的 claim 记 unverified，证据是异常消息。直接跳过等于通过，记成 supported 也不行。
- 事实库没见过的 claim（unknown）也是 unverified。Part 1 的验证器是一张错误清单，查不到就算对；这里要的是有依据的支持。
- 循环里的检查顺序：先看是否通过；再看是不是只剩 unverified，这时 refine 帮不上忙，直接升级，不调用 refine；再看预算；最后，refine 之后看新输出是不是之前验证过的。
- 既有矛盾又有 unverified 时，仍然要 refine 一次，矛盾是 optimizer 能修的。
- "没有进展"要和之前所有轮次比，不能只比上一轮。A → B → A 时，只比上一轮会把 A 再验证一次，最后报成预算用完。
- 原因字符串是给人看的，测试按 docstring 里的格式逐字比较。

追问：
- "Why batch the claims per tool?"（延迟和限流：每轮每个工具只有一次往返）
- "The calculator is down. Retry, or hand it to a person?"（短暂的故障在工具内部退避重试；一直不可用就升级。不要让 optimizer 去改它根本没法核验的 claim）
- "Why is a repeated output 'no progress' instead of one more round?"（evaluator 是确定的：同样的输出得到同样的 critique。这是课里的 Over-refinement）
- "The lesson says the evaluator and optimizer prompts should be substantially different. Where is that here?"（这里的 evaluator 根本不是模型，而是工具；如果改用模型做 evaluator，就要用结构上不同的 prompt，或者换一个小模型）

### Part 4 流式护栏（目标 14 分钟）

坑：
- 输出格式由测试的解析代码决定：每个事件一帧，`event: <name>\ndata: <JSON>\n\n`。data 一定要用 `json.dumps`。行里带着 `\r\n`，手拼字符串会在 data 行里留下原始的回车换行，SSE 客户端会把它们当成行尾。
- 每一行先过护栏再发。先发 delta 再检查，被拒的那一行已经到了客户端手里。
- 触发 tripwire 后马上停：后面不再有 delta，也没有 done，不再拉 token，并且关闭 token 流。测试会数拉了几块，还会在流结束的那一刻检查源头的 finally 有没有执行。`async for` 里提前 return 不会关闭被迭代的生成器，要在 finally 里显式 `await tokens.aclose()`，这样客户端断开时也会关。
- 结尾没有换行的最后一行也要检查；结尾有换行时，后面剩下的空串不是一行。
- token 可以在任何位置切开，包括 `\r` 和 `\n` 之间，一块里也可以有好几行。以 `\n` 作为行尾，`\r\n` 整个算换行符。用 `splitlines` 切会把单独的 `\r` 当成行尾；把 buffer 末尾的半截行留到下一块，能过 token 切在 `\r` 和 `\n` 之间的那一组，可行中间的 `\r` 还是会把一行切成两行，测试里有一行 `- Water boils\rat 100C`。
- 护栏看到的文本只去掉换行符，delta 里带着换行符。用 `rstrip()` 会连行尾的空格一起去掉，测试里 `- Mt Everest is in Asia ` 末尾有一个空格。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要能看出这里需要 async generator。
- 护栏自己抛出的其他异常要往外抛，不能当成 tripwire，否则护栏的 bug 会变成"内容违规"。

追问：
- "The Agents SDK runs output guardrails on the final output. What does checking line by line buy, and what does it cost?"（停得早，少花 token，错的内容一个字也不给客户端看；但要看全文才能判断的检查，比如几条 bullet 之间是否矛盾，还是得在最后做）
- "One line never ends: 50,000 tokens without a newline?"（缓冲区要有上限，超过最大行长就触发 tripwire）
- "After a tripwire the SDK lets the agent retry. Where does the retry go here?"（在流的外面：服务端把 tripwire 的原因当作 critique 重新生成，客户端丢掉这次的部分输出）

### Part 5 嵌套要点（目标 12 分钟）

坑：
- 先建树再检查。建树用一个栈，`stack[d]` 是深度 d 上最近的一条 bullet。缩进一次回退两级时要一次弹掉两层，测试里有从第 3 层直接回到第 1 层的情况。
- 缩进单位是两个空格或一个 tab，同一份大纲只能用一种：由第一条缩进的行定下来，之后不一致就报错，同一行里混用也报错。只做 `expandtabs` 会让混用悄悄通过。空格数不是 2 的倍数也要报错：只做整除的话，缩进一个空格的那行会被当成上一行的兄弟，悄悄通过。
- 跳级（比上一行深两级或更多）和第一行就缩进都要报错。错误消息里要有行号，行号按原文计，空行也算。
- 路径在兄弟节点之间从 1 编号。输出按文档顺序，先父后子。自下而上递归时，最顺手的写法是后序，要先给父节点占住位置。
- 父节点因为子节点失败时，只列直接子节点：`sub-bullets failed: 2.1, 2.2`，不列孙节点。
- 自己的问题在前（长度、事实、空子列表，照这个顺序），子节点失败在后，用 "; " 连接。1.3 既超长又是空子列表，要写成 `not under 50 chars; empty sub-list`。
- 长度只算正文，不算缩进和 "- "。第 3 层有一条 39 个字的 bullet，算上标记就超了。"not under" 是严格小于：1.3 的正文恰好 50 个字，用 `>` 比会放过它。
- 以冒号结尾、但没有子项的 bullet 是"空子列表"。

追问：
- "Why reserve the parent's line before visiting its children?"（输出是先序的，信息却要等子节点算完才有）
- "A 500-level outline?"（递归深度上限；改成显式栈）
- "Markdown accepts four-space indentation and mixed lists. Why be strict here?"（结构有歧义，本身就是稿子的问题；带行号报错，optimizer 才知道改哪里）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback 和断言差异、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出成本、延迟、失败处理、并发写和升级给人的时机 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
