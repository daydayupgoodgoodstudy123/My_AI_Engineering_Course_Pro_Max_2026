# 面试官手册：FCBridge（13/02）

候选人计时期间不要看。候选人手里只有 README、`fcbridge/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 测试文件里的 `FakeProvider` 代表三家的真实 API：它按脚本回复，并像真实 API 那样检查请求。候选人要改的是我们这一侧的代码。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 能不能改测试里的假 provider，让它接受我们的请求？ | "No. They stand in for the real APIs. Fix our side." |
| 1 | `["string", "integer"]` 这种联合类型，Gemini 那边怎么办？ | "Gemini's subset can't say it. Raise ValueError, as the docstring says." |
| 1 | arguments 不是合法 JSON 时返回空参数行不行？ | "No. Raise. The caller sends the error back to the model and asks again." |
| 1 | 深度上限是含还是不含？ | "Inclusive. Five deep is fine on OpenAI, six is not." |
| 2 | OpenAI 的调用能不能只存解析后的 args，读回时再生成 arguments 文本？ | "No. Keep OpenAI's text exactly as it came. It goes back to OpenAI byte for byte." |
| 2 | 位置是每个会话单独计数，还是整个库一起？ | "Per conversation, from 0." |
| 2 | replace 能改什么？ | "Anything in the turn. Not its place." |
| 2 | 会有两个进程同时写吗？ | "Not today. One process writes." |
| 3 | OpenAI 的多个结果能不能合成一条 tool 消息？ | "No. One role tool message per result. Anthropic and Gemini take all the results of a turn in one user message." |
| 3 | 一个会话里会混着几家 provider 的回合吗？ | "Yes. The gateway can switch providers between turns. That's why a call remembers where it came from." |
| 3 | 换到别家时要不要改写调用 id？ | "No. Ids pass through unchanged. A result just names the id of its call." |
| 3 | 8192 数的是哪段文本？ | "The arguments text you actually send, in UTF-8 bytes." |
| 3 | 8192 是每个调用的上限，还是整个请求的？ | "Per call. Each arguments text on its own." |
| 3 | Gemini 的深度上限是多少？ | "None in our table. None means no limit." |
| 4 | 模型拒答、没有调用，算什么？ | "An error record. A reply needs exactly one call." |
| 4 | 超时是每家单独算，还是整个探针一个总时限？ | "Per provider. They all start together." |
| 4 | 一家失败、另外两家一致，汇总写什么？ | "incomplete. But if any two answers disagree, it's different." |
| 4 | OpenAI 那一行的 arguments_json 能直接用原始文本吗？ | "Sure. Any JSON text that parses to the arguments." |
| 4 | error 记录里要不要写出错原因？ | "No. Leave the call fields empty. The reason goes to the logs." |
| 5 | `$defs` 会互相循环引用吗？ | "No. The definitions are acyclic." |
| 5 | 本来就是必填、类型里已经有 null 的属性要改吗？ | "Its type stays. But an enum next to a nullable type has to list None." |
| 5 | `$ref` 旁边还有 description 之类的键怎么办？ | "Keep them. They win over the definition's. The tests don't cover it." |
| 5 | 编译后太深怎么办？ | "LimitError naming openai. Measure after inlining." |
| 5 | 输入的工具不是 strict 的，编译后要标成 strict 吗？ | "Yes. That's why we compile it." |

## 每关：要看什么、提示、追问

### Part 1 修三家翻译（目标 10 分钟）

一个测试里叠了 4 个缺陷和 3 个护栏：

1. `tool_choice_anthropic` 把三种简单模式合成了一句 `if tc.mode in ("auto", "none", "required")`，照抄了 OpenAI 那一版，required 变成了 `{"type": "required"}`。docstring 写的是 any。错误不在这里报：测试里的假 Anthropic 拒收整个请求，`ProviderError: anthropic rejected the request: 400 tool_choice.type: 'required' is not one of ...`，离根因两层（`Bridge.ask` → `tool_fields` → `tool_choice_anthropic`）。
2. `_gemini_schema` 只在 type 是字符串时才转大写（课里代码的原样，测验 Q4、Q9），WEATHER 的 `["string", "null"]` 原样发出去。假 Gemini 报 `functionDeclarations[0].parameters.properties.units.type: expected one of STRING, ...`，离根因三层。要改成一个大写类型加 `nullable: true`；两个真实类型的联合没有这种写法，要报 ValueError（测验 Q9.3）。
3. `parse_openai` 把空字符串交给 `json.loads`。无参数工具 get_time 的回复报 `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`。空串表示没有参数，`raw_arguments` 仍然保留 `""`。
4. `schema_depth` 在比较和赋值里各递归一次，每多一层嵌套（属性、数组 items、anyOf）工作量就翻倍。对象和数组交替的 10 层文件夹树在本机要 0.3 到 0.6 秒，限值是 0.03 秒。改成每个子 schema 只算一次。
5. 护栏：FLEET 有一个名叫 type 的属性。顺手把所有 type 键都当关键字处理的改法，会在 `{"type": "string", "enum": [...]}` 上报 `'dict' object has no attribute 'upper'`。properties 下面的键是属性名，不是关键字（测验 Q9）。FLEET 的 plate 写成 `["null", "string"]`，取列表第一个元素当类型会得到 NULL。
6. 护栏：非法 JSON 仍然要报错。为了让空串过而把 JSONDecodeError 吞成 `{}`，工具会在没有参数的情况下被调用；课里 Errors and repair 要的是解析失败后把错误交回模型重试。
7. 护栏：深度要准确。8 层只有 OpenAI（5）拒收，12 层 OpenAI 和 Anthropic（实践上限 10）都拒收，Gemini 没有深度上限。为了提速把递归截在 OpenAI 的上限，两者都报 6，Anthropic 永远不会拒收；截在 11 也会把 12 报成 11。

看什么：是不是先读 traceback、看出报错的是 provider 不是我们；有没有打印出实际发出去的请求（`bridge.providers["anthropic"].requests`）再对照课里的对比表；每改一处就重跑。

提示：
- H1："Print the request the fake rejected. Which function built that field?"
- H2："Compare tool_choice_anthropic with its docstring. What does _gemini_schema do with a type that is a list?"
- H3：直接指出 `tool_choice_anthropic` 的 required 分支和 `_gemini_schema` 的 `isinstance(v, str)`。

追问：
- "Why raise on a type union instead of picking the first type?"（在构建期报错，比线上被 provider 拒收或者悄悄收窄类型好）
- "_gemini_schema drops a property called additionalProperties. Why, and how would you fix it?"（测验 Q9.2：同样是把属性名当成了关键字；按关键字逐个翻译，properties 下只递归值）
- "Gemini 2 sends parallel calls without ids. What does parse_gemini return, and what breaks?"（两个 id 都是空串，结果对不上调用；课里说 Gemini 3 起才有唯一 id）
- "strict: true is silently dropped for Anthropic and Gemini. What does that mean for the host?"（校验强度变了，要在服务端自己校验；课里说 Anthropic 的 schema 只是 advisory）

### Part 2 规范会话库（目标 12 分钟）

坑：
- OpenAI 的 arguments 原文要逐字节读回。测试里的原文有 `" ,"` 这样的空格、大写的 `\u00E3` 转义，还有无参数工具的空串 `""`。存解析后的 args 再 `json.dumps`、压缩成紧凑 JSON，或者交给 SQLite 的 `json()` 去校验（它会去掉空格），都会改写原文。这段文本下一轮要原样发回 OpenAI。
- 空串 `""` 是合法的原文。`raw or None` 会把它变成 None。
- Anthropic 和 Gemini 的调用存的是对象，`raw_arguments` 读回来仍是 None。所有 provider 共用一个“参数文本”列，读回时会把它们也变成文本。
- `exact()` 比较的是 JSON 文本，不是 `==`。SQLite 没有布尔类型，`is_error` 存进 INTEGER 列读回来是 1；Python 里 `1 == True`，dataclass 比较照样相等，但发给 Anthropic 时是 `1` 不是 `true`。`json.dumps(..., sort_keys=True)` 存进去会改掉参数对象的键序，`exact()` 也会抓到。
- 位置按会话从 0 计。测试把两个会话交错写入，用全局自增 id 或者不带 `WHERE conversation_id` 的 `MAX(position)` 都会挂。
- 并行调用的先后要保住。把调用拆到另一张表、主键写成 `(conversation_id, position, call_id)` 的话，按主键查出来是按 id 排序的；测试里两个并行调用的 id（`call_Ww9mQ4`、`call_Hk2pR7`）不是字母序，顺序一换就会挂。要另存一个序号列，按它排序。
- replace 要保住位置。用 DELETE 加 INSERT 或者 `INSERT OR REPLACE` 实现，被替换的行会拿到新的 rowid；再按 rowid 排序，脱敏后的那条结果就跑到了最后。按显式的 position 排序。
- replace 只改自己会话里的那一条。UPDATE 的 WHERE 漏了 `conversation_id`，会把 standup 里同样在位置 5 的回合也换掉，测试最后会重读 standup。
- 常规的：commit；建表写 `IF NOT EXISTS`；未知 provider 报 ValueError；不存在的位置报 KeyError；不存在的会话返回 `[]`。
- 数据里有 2^64 + 1 的预订号和 140.0 这样的浮点数。JSON 文本能原样保住；放进 SQLite 的 INTEGER 列，超过 2^63 的整数会报 OverflowError，SQLite 的 JSON 函数会把它变成 REAL。

追问：
- "Why not pickle the dataclasses into a BLOB?"（反序列化会执行代码，只有 Python 能读，dataclass 一改字段旧数据就读不出来）
- "Why does it matter that OpenAI's text comes back byte for byte?"（这段文本下一轮原样发回；provider 如果按前缀做缓存，改了字节就命中不了；排查问题时要看到模型真正说了什么）
- "The redacted email: is it gone from the database file?"（不一定：SQLite 删除或覆盖的数据可能还留在空闲页里，要 `secure_delete` 或 VACUUM）
- "A provider changes its id prefix tomorrow. What breaks?"（我们这边什么都不该坏：id 是不透明的字符串，不按前缀判断来源，来源记在 AssistantTurn.provider 上）

### Part 3 三家请求（目标 14 分钟）

坑：
- 结果的归组：OpenAI 每个结果一条 role=tool 消息；Anthropic 把一个回合的所有 tool_result 块放进同一条 user 消息；Gemini 把所有 functionResponse 放进同一条 user content。课文说 OpenAI 是 "a batched tool-role message containing one entry per tool_call_id"，照字面合成一条消息是错的，测试要的是每个 tool_call_id 一条（测验 Q11 的写法）。
- OpenAI 的 arguments 是文本：来自 OpenAI 的调用发回 `raw_arguments` 原文，别家的调用发 `json_text(args)`。发对象不行；用 `json.dumps` 的默认参数会把 São 写成 `S\u00e3o`。来自 OpenAI 的空串 `""` 也要原样发回：`raw_arguments or json_text(args)` 会把它换成 `"{}"`，测试会单独渲染 STANDUP 检查这一点。
- Anthropic 的 input 和 Gemini 的 args 是对象，来自 OpenAI 的调用也一样，不能塞原文字符串。
- Anthropic：有文字时 text 块在 tool_use 块前面；只有失败的结果带 `"is_error": true`；tool_result 的 content 是 JSON 文本。Gemini：模型回合的 role 是 model，functionCall 和 functionResponse 都带调用的 id（课里说 Gemini 3 起用 id 对应并行调用）。OpenAI：没有调用的回合不带 tool_calls 键，有调用时 content 是 None。
- 工具数上限 128 / 64 / 64，正好等于上限时可以；Gemini 的 tools 只有一个对象，64 数的是里面的函数声明，数 `len(body["tools"])` 永远是 1。LimitError 的消息要带 provider 名。深度也要查，按各家自己的上限，含上限：OpenAI 5 层可以、6 层不行，Anthropic 10 层可以、11 层不行。直接调 Part 1 的 check_depth 最省事；只给 OpenAI 查，或者自己写成 `>=`，都会挂。
- 8192 字节数的是实际发出去的文本的 UTF-8 字节，含上限。测试里那条笔记的参数文本（2725 个“大”加 "ab"，外面是 `{"summary": ...}`）正好 8192 字节、2742 个字符：用 `len(str)` 数字符会放过 8193 字节的那一条，用带 `\u` 转义的 JSON 去量会量出 16367 字节、把正好 8192 的那一条也拒掉。只有 OpenAI 有这个上限。
- 上限是每个调用各自的。同一回合里还有一条短笔记，把一个回合或者整个请求的参数加在一起量，正好 8192 字节的那一条也会被拒掉。
- 最后一段把 Part 2 串起来：存进库、重开、再渲染，三家的请求要和原来的逐字节相同。

追问：
- "100 tools: fine on OpenAI, too many for the other two. What would you build?"（工具路由或检索，只把相关的十几个发给模型；课里的移植审查 skill 把这叫 needs-router，测验 Q16）
- "The conversation moves from Anthropic to OpenAI mid-way. What else would you check before switching?"（两边都声明了历史里出现过的工具；strict 与否不同带来的校验差异；上限）
- "Why bytes and not characters?"（上限是字节数；中文 3 字节、emoji 4 字节；`\u` 转义的中文是 6 字节）
- "Tool results go out as json_text. What if they went out with json.dumps defaults?"（测试抓不到，夹具里的结果都是 ASCII；内容等价，模型看到的是 `\u` 转义，中文结果会多花不少 token。arguments 不一样：OpenAI 的原文要逐字节发回，还要量 8192 字节）

### Part 4 一致性探针（目标 12 分钟）

坑：
- 要并发问三家，并按回复到达的顺序输出：`asyncio.as_completed`，或者每家一个 task、结果放进队列。依次 await 是 bridge 的顺序；`gather` 是输入顺序，而且要等所有人。
- 要边到边输出：测试在前两条记录到达时检查最慢的那家还没有回复。先收齐再输出会挂。
- CSV 用 csv 模块写。JSON 文本里本来就有引号和逗号，城市名还是 "Washington, D.C."：用逗号直接拼字段，或者只在两边加引号、不把里面的引号写成两个，测试的 `csv.DictReader` 都会解析出多余的字段。第一条是表头，每次 yield 一条完整的记录，带换行。
- 失败各自成行，不影响别家：拒答（没有调用）、一次回复两个调用、坏 JSON、429 都是 error，超时是 timeout。只接 TimeoutError 的话，429 会把整个流打断。
- error、timeout 和汇总这三种记录，call_id、name、arguments_json 都留空。测试解析每一份报告时都会检查：把报错信息写进去，或者一次两个调用时填上第一个调用，都会挂。
- 超时按每家算，从发出请求算起，用 `asyncio.wait_for`；超时的请求要取消，测试在报告结束后让出一次事件循环，再看那家有没有收到取消。`as_completed(..., timeout=)` 是整个探针一个总时限，到点会直接抛 TimeoutError。用 `asyncio.wait(..., timeout=timeout_s, return_when=FIRST_COMPLETED)` 循环的话，每来一个回复就重新计时：最后一段测试里 Gemini 0.2 秒回复，Anthropic 0.4 秒才回复，限时 0.3 秒，Anthropic 会被错当成 ok。
- 汇总比较的是工具名和解析后的参数：不比 id（`call_`、`toolu_`、UUID 本来就不同），不比文本（OpenAI 的原文键序不同、没有空格），也不能只比名字或只比参数。有两家不一致就是 different，即使另一家失败了；三家都回答且一致才是 same；其余是 incomplete。最后一段测试里两家一致、第三家超时，是 incomplete，“回来的答案都一致就是 same”会挂。
- starter 里是 `async def ... raise NotImplementedError`，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要看出这里需要 async generator。

追问：
- "Two providers agree, and both are wrong. What would you add?"（每个探针问题配一个期望的调用，或者按 schema 校验参数，即课后练习 5）
- "Is 1 the same argument as 1.0? Is true the same as 1?"（JSON 里 1 和 1.0 是同一个数，true 不是 1；Python 的 `==` 两种情况都说相等，要按 JSON 的规则比）
- "The probe runs every hour on production prompts. What does it cost, and what would you log?"（每个问题三次付费调用；抽样；记下每家的延迟和失败原因）
- "After a timeout, is the provider still generating?"（取消 task 会关掉我们这边的请求；对方停不停、计不计费要看各家，上线前要查清楚）

### Part 5 strict 编译器（目标 12 分钟）

坑：
- 每个 `$ref` 要有自己的一份拷贝。billing 是必填的，保持 `"object"`；shipping 是可选的，要变成 `["object", "null"]`。几处引用共享同一个 dict 时，给 shipping 加 null 会把 billing 也改了。只复制最外层也不够：测试会改一份拷贝里的 street，看另一份有没有跟着变。
- 输入不能动。叶子值也要复制：浅拷贝的 enum 列表和输入共用，加 None 时会加到输入里。
- 每个对象都要处理，包括数组 items 里的和 anyOf 分支里的：`additionalProperties: false`，required 按 properties 的顺序列出全部属性。
- 可选属性改成可空：type 加一个 "null"（postcode 本来就有，不能加成两个）；有 enum 的，enum 加 None（speed）；没有 type 的 anyOf 加一个 `{"type": "null"}` 分支（payment）。要在内联之后做：`{"$ref": ...}` 本身没有 type，先处理再内联，shipping 就不会变成可空。
- WEATHER 的 units 本来就是必填、可空，但 enum 里没有 None（测验 Q7），null 会被 enum 拒掉。所有“类型允许 null 又有 enum”的地方都要加 None。
- 深度在内联之后算：org_chart 内联前只有 1 层，内联后 6 层，要报带 openai 的 LimitError；5 层可以。用 OpenAI 的上限，含上限。
- 结果里不能有 `$defs`，也不能剩下 `$ref`，包括定义里嵌套的引用（line 里的 ship_to）。
- 编译出来的工具要标成 strict。ORDER 本身是 `strict=False`（带着 `$ref` 和可选属性，strict 模式会拒收）；用 `dataclasses.replace(tool, input_schema=...)` 会把 False 原样带过来。
- 新加的 null 放在最后：type 写成 `["string", "null"]`，anyOf 的 `{"type": "null"}` 分支排在最后，docstring 写明了。放在前面语义一样，但和测试的期望不符。

追问：
- "What if a $def refers to itself, like a tree of categories?"（内联会无限展开；strict 模式不允许 $ref，只能限定层数展开，或者换成不要求内联的模式）
- "Why does strict mode want every property in required?"（测验 Q14：受约束解码要有确定的生成路径，“可选”只能写成“必填但可为 null”）
- "Feed the compiled schema to _gemini_schema. What comes out?"（`["object", "null"]` 变成 OBJECT 加 nullable，additionalProperties 被删掉；enum 里的 None 原样留着，要不要保留看 Gemini 的子集是否接受）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、打印实际发出的请求、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出原文保真、类型与键序、字节上限、超时与取消、共享与复制 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
