# 面试官手册：VoiceBot（06/12）

候选人计时期间不要看。候选人手里只有 README、`voicebot/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 未知工具、坏参数要不要抛异常？ | "No. Everything goes back to the LLM as an error result. The turn goes on." |
| 1 | "300" 这种字符串数字要不要转成整数？ | "No. Reject it and name the parameter. The model will resend a number." |
| 1 | dispatch 要不要自己重试失败的工具？ | "No. The LLM decides whether to retry. Part 3 caps it." |
| 2 | 过期从第一条消息算还是最后一条？ | "From the last message. A conversation that is in use never expires." |
| 2 | 过期的会话又来了新消息，旧消息怎么办？ | "Delete them. The new message starts a fresh conversation." |
| 2 | 参数要不要统一成 dict 再存？ | "No. Store every message exactly as the provider sent it." |
| 2 | 要不要加密存储？ | "Out of scope today. But deleted text has to be really gone from the file." |
| 2 | 能用 WAL 模式吗？ | "Sure. Deleted text still has to be gone from the database file as soon as it's deleted." |
| 3 | 和工具调用一起来的 content 要不要念？ | "Not in this version. Only the final answer is spoken." |
| 3 | “同一个工具失败两次”怎么算？ | "Same tool name, two error results in one turn." |
| 3 | 最后一次 LLM 调用还要工具，执行吗？ | "No. Answer each of those calls with an error result, then say the fallback." |
| 4 | 有事件比 max_delay_ms 还晚到怎么办？ | "The collector guarantees that doesn't happen. Your call. The tests don't cover it." |
| 4 | 首音延迟从哪个事件算起？ | "From vad.end, when the user stopped talking." |
| 4 | 一轮里没有音频或者没有 vad.end？ | "Then that number is null." |
| 5 | 60.0 算不算整数？ | "Your call. Say what you chose. The tests don't cover it." |
| 5 | 没写 additionalProperties 的对象，多出来的属性算问题吗？ | "No. Only additionalProperties: false forbids them." |
| 5 | 问题按什么顺序返回？ | "Any order. The tests sort them." |

## 每关：要看什么、提示、追问

### Part 1 修工具调度（目标 10 分钟）

一个测试里叠了 4 个缺陷和 2 个护栏：

1. `parse_arguments` 把 OpenAI 风格的 JSON 文本解析成了 `decoded`，返回的却还是原来的字符串。错误不在这里报：下一层 `check_arguments` 先用 `"seconds" in '{"seconds": 60}'` 做了一次子串匹配，必填检查被静默骗过，然后在 `args.items()` 报 AttributeError。
2. `_lookup` 和 `parse_arguments` 抛的 ToolError 没有被 dispatch 接住，未知工具和坏 JSON 直接中断这一轮。docstring 写的是 dispatch never raises。
3. `JSON_TYPES` 的键写成了 `"int"`，schema 里是 `"integer"`，`.get(kind, object)` 让整数参数一律不检查。`"300"` 一路传进 `Timers.set_timer`，在 `self._clock() + seconds` 报 TypeError，又被 catch-all 变成错误结果，错误里没有参数名。报错的地方离根因两层。
4. 同步工具直接在事件循环上调用。2 秒的天气查询让同一个循环上的“麦克风”停了 2 秒，测试要求最长停顿小于 0.2 秒。改成 `await asyncio.to_thread(tool.fn, **args)`。把工具包成 `async def`，或者调用前先 `await asyncio.sleep(0)`，阻塞调用还是跑在事件循环上，停顿照样是 2 秒。
5. 护栏：异步工具（next_event）还得 await。为了不阻塞把所有工具都扔进 `to_thread`，拿到的是一个没 await 的协程，`json.dumps` 报 `Object of type coroutine is not JSON serializable`。
6. 护栏：catch-all 要留着。第 3 处的 TypeError 被包成了错误结果，有人会为了看 traceback 把 `except Exception` 改窄，最后一条断言（天气服务挂了）就会挂。

看什么：是不是先读 traceback、发现报错的位置不是根因；看到错误结果里的 TypeError，是去问“为什么类型检查没拦住”，还是在 `set_timer` 里加 `int()`；每改一处就重跑。

提示：
- H1："Print args right before check_arguments. What type is it?"
- H2："Why did '300' get past check_arguments? What does JSON_TYPES.get('integer', object) return?"
- H3：直接指出 `parse_arguments` 的返回值、`JSON_TYPES` 的键和 `asyncio.to_thread`。

追问：
- "Two tool calls in one LLM step take a second each. How long does the turn wait, and how do you cut it?"（`asyncio.gather` 并行跑；结果仍按调用顺序回给 LLM，失败的那个也要有结果）
- "set_timer now runs in a worker thread. Is Timers thread-safe?"（不是：`len` 加 `append` 有竞态，并行 dispatch 时会出重复 id；加锁，或者让快的本地工具留在事件循环上）
- "The weather API hangs for 30 seconds. What does the user hear?"（一片安静。工具要有超时（`asyncio.wait_for`），超时也作为错误结果交回 LLM；慢工具前先说一句过渡语）

### Part 2 会话库（目标 12 分钟）

坑：
- 消息要原样读回：tool_calls 旁边的 `content: None`、JSON 文本形式的参数（一个字节都不能变）、dict 形式的参数、额外的 `is_error` 键、非 ASCII 字符和 emoji。只存几个固定列再拼回 dict，或者把参数“统一”成 dict，都会挂。整条消息存成 JSON 最稳。
- Python 的 sqlite3 默认开着隐式事务，不 commit 的话关闭连接就丢数据；建表没写 `IF NOT EXISTS`，重开会报 `table messages already exists`。
- 非法 role 要报 ValueError。只靠 CHECK 约束拦，报的是 IntegrityError。
- 过期从最后一条消息算，会话在用就不过期；刚好 ttl_s 时已经过期（`>=`）。按单条消息的时间过滤也不对，正在进行的对话会被截掉前半段。
- 过期的会话再来消息，要先删掉旧对话，否则会把上一段对话带回来。purge 返回的是删掉的消息条数，不是会话数。
- 删除要真的删掉：SQLite 默认把删掉的行留在页里的空闲区，`b"Okafor" in path.read_bytes()` 仍然成立。要 `PRAGMA secure_delete = ON`，或者删除后 VACUUM。这对应课里 Pitfalls 的 "Logging PII forever"。
- 两条删除路径都要真删。会话重新开始时删掉的旧对话，测试当场就读文件找 "Baker"，只在 purge 或 close 里 VACUUM 过不了。secure_delete 是连接级的设置，不存进文件，每次打开都要设。用了 WAL 的话，旧页会留在主文件里直到 checkpoint，这条断言也会挂。

追问：
- "The purge runs every night. Where else does this transcript still live?"（WAL 或回滚日志、备份、应用日志、LLM 提供方的留存；secure_delete 只管这一个文件）
- "The lesson says encrypted at rest. How?"（SQLCipher 或磁盘加密；密钥管理；每个用户一把密钥，删钥匙就等于删数据）
- "Why keep the provider's raw format instead of normalizing it?"（换提供方或排查问题时信息不丢；格式转换放在发请求的时候做）

### Part 3 语音工具循环（目标 12 分钟）

坑：
- 工具结果要回给 LLM，再调一次（课里代码一次就拿到了回复，省掉了第二次 LLM 往返）。带 tool_calls 的 assistant 消息要先进历史，后面紧跟每个调用的结果，id 和顺序对上。历史里存的是 LLM 的原始回复（带 markdown），念出来的才是 speakable 之后的文字。
- 每次调用 LLM 都要带上 `box.specs()`。测试里的假 LLM 会检查，写成 `box.specs`（少了括号）会报 "every LLM request offers the tool specs"。
- max_steps 数的是 LLM 调用次数。`range(max_steps + 1)` 会多调一次。第 max_steps 次回复如果已经是回答，就照常念出来：端到端那段用 `max_steps=3`，回答正好在第 3 次回复里，先查步数上限、后查有没有工具调用的写法会把它念成 FALLBACK。
- 最后一次调用还要工具：不执行，但每个调用都要有一条错误结果，否则历史里留着没有回答的 tool_call，下一轮请求不合法（OpenAI 会直接报 400）。把这条回复直接丢掉也不行，测试要看到 s3 的错误结果。
- 同一个工具第二次失败才降级（课里 "retry once, then gracefully degrade"）。第一次失败就降级的话，最后那段 `minutes` 写错、改成 `seconds` 重试的流程走不通。失败按工具名分别计数：测试里第一次回复的天气和计时器各失败一次，合起来算成两次就会提前降级。
- 降级时 FALLBACK 要作为 assistant 消息写进历史：这一轮助手说的就是这句话，下一轮模型才知道上一轮没办成。
- `speakable`：`-3°C`、`2.5 m/s` 开头的行不是列表，列表标记后面必须有空格；链接只念文字；标题和列表项各自成句。
- 最后一段端到端：参数名写错一次、重试一次、念出确认，整轮存进 Part 2 的库，Part 1 的计时器真的启动了。这就是课后练习 3。

追问：
- "The weather tool takes 1.5 s. What does the user hear meanwhile?"（先念一句过渡语或放提示音；预算里要算上第二次 LLM 调用）
- "The user barges in while a tool is running. What happens to the tool and the history?"（取消 LLM 和 TTS；有副作用的工具要么做完要么回滚；历史里只记实际念出口的部分）
- "Destructive tools like send_email or pay?"（语音没有确认按钮：先复述关键参数，要求口头确认，再执行）

### Part 4 延迟报告（目标 14 分钟）

坑：
- 按事件时间算，不按到达顺序：第一段音频取最小的 ms，不是第一个收到的那条。首音从 vad.end 算，从 stt.final 算会每轮少 80–100 ms。
- turn.end 到了还不能马上出报告，晚到的音频或 barge_in 可能还在路上。要等收到一个比 turn.end 新至少 max_delay_ms 的事件（水位线），或者流结束。测试里有一种到达顺序专门让 barge_in 和最后一段音频比 turn.end 晚到。
- 一轮完成就要输出，不能先把整条流读完。测试会数拉取了多少个事件。
- 静音幻觉要用 VAD 判断：没有 vad.start 的轮，就是 STT 在静音上出了字。按文字黑名单过滤会把用户真说的 "Thank you." 也当成幻觉（课里的 "Overzealous hallucination filters"）；有 stt.partial 也不代表有人说话。
- barge_in_ms 是用户打断之后助手还在播的时长：打断时或之后最后一段音频的时间减去打断时间，之后没有新的音频就是 0。第 3 轮打断后没再开始新的一段，是 0；直接拿这一轮最后一段音频去减，会得到 -150。第 4 轮 LLM 没被取消，抢话 900 ms，正是课里的第 2 种故障。
- 一轮完成的判断要在加进当前事件之后做。先检查再加进来，报告会晚一个事件，第一份报告要拉 11 个事件才出来。
- 格式由测试的 SSE 解析决定：每个事件一行 `event:`、一行 `data:`，后面空一行。少了空行会报 "every server-sent event ends with a blank line"。
- 写成普通的 async 函数（只有 return、没有 yield）时，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出来这里需要 async generator。

追问：
- "Why measure from vad.end and not from stt.final?"（用户感知的是自己停嘴以后；但 VAD 要等满静音挂起时间才能判定说完，课里代码把这 400 ms 也算进了预算，所以要分清“说完的时刻”和“判定说完的时刻”）
- "Users say the bot misses their first word. What would you look at, and what would you change?"（第 1 种故障：VAD 起得晚。这份 trace 看不出来，要看音频，比如 vad.start 之前的那一段；起始阈值用 0.3 而不是 0.5，保留 200–400 ms 的 pre-roll）
- "P95 of first_audio_ms over a day of traces?"（流式分位数：t-digest 或固定分桶直方图；只看平均会把尾部藏起来）
- "How do you pick max_delay_ms?"（越大越不容易漏掉晚到的事件，报告也出来得越晚；按各组件上报延迟的实测分布定）
- "tts.audio marks when a chunk starts playing. How would you know when the assistant actually went quiet?"（要有播放停止的事件，或者知道每段的时长；按段的起点算，会漏掉打断时正在播的那一段）

### Part 5 参数校验（目标 12 分钟）

坑：
- 要一次返回全部问题。模型每改一次就多一次 LLM 往返，在语音里就是用户多等几百毫秒。
- 布尔值不是整数：Python 里 `isinstance(True, int)` 为真。
- `type` 可以是列表，`["string", "null"]` 是 OpenAI strict 模式里可选参数的写法。
- 类型错了就不再往下查：字符串 "at 10pm" 不能再报 `/trigger/kind` missing，"lights off" 也不能当数组逐字检查。
- missing 的指针指向缺的那个属性，不是父对象。
- 只有 `additionalProperties: false` 的对象才报 unexpected。没写这个键的对象允许别的属性，测试最后一条专门查这个。
- JSON 指针要转义：键 `on/off` 写成 `/trigger/on~1off`，`~` 写成 `~0`。测试最后用 RFC 6901 自己的例子 `a/b`、`m~n` 再查一次。先换 `/` 再换 `~`，`~1` 会变成 `~01`。
- `$ref` 是递归的（group 步骤里还有 steps），要按需解析。先把引用全部展开会无限递归；用“见过的引用就跳过”来防递归也不对，第二个 step 起就都不查了。

追问：
- "Where would validate go in the dispatcher, and what would the LLM see?"（替换 `check_arguments`；把指针和问题拼进错误结果，比如 "/steps/1/action: not one of say, set_timer, play, group"）
- "Strict mode or constrained decoding already guarantees the schema. Do you still validate?"（还要：不是每个模型和提供方都支持；schema 只能表达结构，“时间必须在将来”这类业务规则还得自己查）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出并发、超时、PII、延迟尾部、失败处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
