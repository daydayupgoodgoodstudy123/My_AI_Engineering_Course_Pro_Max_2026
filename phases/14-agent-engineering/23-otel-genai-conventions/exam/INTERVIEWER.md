# 面试官手册：SemConv（14/23）

候选人计时期间不要看。候选人手里只有 README、`semconv/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 题里没有真的 LLM：`ModelReply` 由测试脚本化给出，工具是 async 函数，用 `asyncio.sleep(0)` 控制交错的顺序。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 未命名的 agent 还要带 `gen_ai.agent.name` 吗？ | "No. Leave the attribute out. The span is just `invoke_agent`." |
| 1 | 能改 agent.py，还是只能改 tracer？ | "Anything under semconv/ is yours." |
| 1 | 去重能不能去掉？ | "No. A prompt repeated on every turn is stored once." |
| 1 | 每次运行都要记一个 create_agent 吗？ | "No. Once, when the agent is built. A run is invoke_agent." |
| 1 | 同一个 agent 换一个 tracer 跑，要再记 create_agent 吗？ | "No. It was created once, in the trace where it was built." |
| 2 | 引用是什么格式？ | "The row id as a decimal string, like '7'." |
| 2 | 删掉的内容又被 put 进来，用原来的引用吗？ | "No, a new one. The old reference stays dead." |
| 2 | 1 和 1.0 算同一份内容吗？ | "No. Only the same JSON text is the same content." |
| 2 | 会有多个进程同时写吗？ | "Not today. One process." |
| 3 | 没有 `gen_ai.response.model` 怎么办？ | "Use the request model, as the docstring says." |
| 3 | 工具 span 的父节点是另一个工具 span？ | "Orphaned. Count it, don't guess." |
| 3 | 开始时间一样的两个 chat span？ | "Smaller span id. It's in the docstring." |
| 4 | 消费方很慢怎么办？ | "An unbounded queue is fine here. Tell me what you'd do in production." |
| 4 | 流停了以后才结束的 span？ | "Not streamed. The tracer still records them." |
| 4 | run 失败了，错误要吞掉吗？ | "No. Stream every line first, then raise it." |
| 5 | 没有 token 属性的 chat span 算 0 还是未知？ | "Zero." |
| 5 | 同名的两个 agent run？ | "Two runs." |
| 5 | 父 span 没有收到的子 agent？ | "It's a root of its own." |

## 每关：要看什么、提示、追问

### Part 1 修 agent 的 span（目标 12 分钟）

一个测试里叠了 4 个缺陷、1 个性能问题和几道护栏：

1. 未命名 agent：`agent_attributes` 无条件把 `gen_ai.agent.name: None` 放进属性，`agent_span_name` 拼成 `invoke_agent None`，create_agent 和 invoke_agent 两种 span 都用这两个函数。报错不在 agent.py，而是在 `Span.set_attribute` 里报 TypeError（调用链：`run_agent` → `Tracer.span` → `start_span` → `set_attribute`）。课里的规则是有名字时用 `invoke_agent {gen_ai.agent.name}`，否则回退成 `invoke_agent`。
2. 当前 span 用一个共享的栈跟踪，`end_span` 还忽略传进来的参数，直接弹栈顶。两个工具调用用 `asyncio.gather` 并发时，后开始的工具被挂在先开始的工具下面，先返回的工具结束的是别人的 span。docstring 要求当前 span 放在 contextvars 里。
3. agent 的两种 span 记的时机不对：`create_agent()` 什么都不记，`run_agent` 每次一开头在 invoke_agent 下面记一个 create_agent。课里 Span categories 讲的是 create_agent 在构造 agent 时记一次，invoke_agent 每次运行记一次；课里的代码也是先记一个立刻结束的 create_agent，再开始 invoke_agent。测试按 `gen_ai.operation.name` 计数：构造完恰好一个 create_agent，在原来的 tracer 和另一个 tracer 上各跑一次，都不再多出来。父节点只顺带看一眼（在任何 run 之外构造的 agent，create_agent 是根 span），所以这里的失败信息说的是个数，不是父节点。
4. 默认时钟是 `time.perf_counter_ns`（单调时钟，起点任意），docstring 要的是 Unix 纪元纳秒 `time.time_ns`。
5. `ExternalContentStore.put` 为了去重线性扫描已有内容，18000 条要 1.6–3.6 秒。按 JSON 文本建一个反向字典即可。

护栏：

- 为了提速把去重删掉：同一个 prompt 在两个 tracer 里拿到不同的引用，挂在 “identical content shares one reference”。
- 用 contextvars 但 `end_span` 不把父 span 设回当前：invoke_agent 会挂在已经结束的 create_agent 下面，后面的工具和 chat 会挂在已经结束的 chat 下面。
- 时钟写成 `time.time() * 1e9`：是 float，挂在 “integer nanoseconds”。
- 把 `is None` 判断改成直接赋值 `content_store`：默认构造的 `Tracer(capture_content=True)` 会 AttributeError。改成课里代码的 `content_store or ExternalContentStore()` 也不行：store 定义了 `__len__`，空 store 是假值，内容写进 tracer 自己的 store，测试读内容时报 KeyError。
- 在 `set_attribute` 里静默丢掉 None：不报错了，但 span 名还是错的。
- 把 create_agent 挪到 invoke_agent 前面，但仍然每次运行都记（照课里脚本的顺序）：父节点对了，可构造完一个都没有，挂在 “constructing an agent records one create_agent span”。等第一次运行时才补记，或者构造时只 start 不 end，也挂在这里。
- 构造时记了，`run_agent` 里那两行却没删：跑一次就有两个，挂在 “a run records invoke_agent, never create_agent”。每换一个 tracer 补记一次，挂在 “a run on another tracer records no create_agent either”。
- 自己拼 span 名 `f"create_agent {name}"`：未命名 agent 得到 `create_agent None`，挂在 “an unnamed agent's create_agent span is named create_agent”。create_agent 上只写 `gen_ai.operation.name`、不带 `gen_ai.provider.name`，挂在紧接着的 “root create_agent span with its provider”。

测试抓不到、要靠面试官看的写法：

- `run_agent` 里那两行注释掉留着，或者留一个永远不成立的开关：测试能过，记成死代码。
- create_agent 的属性自己手写，不复用 `agent_attributes`：带上 provider、未命名时不写 `gen_ai.agent.name` 就能过。课里代码的 create_agent 也不带 request model，可以接受；问一句为什么不复用。
- 用 `ContextVar.set` 返回的 token，在 `end_span` 里 `reset`：可以接受。前提是 span 在开始它的那个任务里结束，本题里都是这样。

看什么：是不是先读 traceback 找到是谁传了 None；能不能说出单个栈为什么在 asyncio 下串台；看到 create_agent 的计数断言时，能不能先说清课里 create_agent 和 invoke_agent 各对应 agent 的哪个阶段，再动手，而不是把那两行挪到 invoke_agent 外面就算完。

提示：
- H1："Which code put None there? The span only complains about it."
- H2："Print each tool span's parent_span_id. Two tasks share one list. What does each task think is current?"
- H3：直接指出 `create_agent()` 什么都没记，而 `run_agent` 每次一开头都在 invoke_agent 下面记一个 create_agent。

追问：
- "A dashboard counts create_agent spans to show how many agents a service builds. What did it show before your fix?"（每运行一次就多一个“创建”，数出来的是运行次数，不是 agent 的个数。agent 在启动时构造、一跑好几天的话，run 的 trace 里本来就没有 create_agent，要靠 `gen_ai.agent.name` 关联，或者像课后测验 Q12 说的，用 span link 把运行连到创建）
- "Why contextvars rather than threading.local?"（asyncio 的任务在同一个线程里；contextvars 在创建任务时复制上下文，每个任务改自己的副本）
- "Monotonic clocks are better for durations. Why epoch here?"（跨进程、跨主机要对齐到同一条时间线；OTel 的 span 时间戳是纪元纳秒）
- "Content dedupe across tenants: any risk?"（共用一个 store 时，相同引用会暴露“别人也发过同样的内容”；按租户分 store）

### Part 2 SQLite 内容库（目标 10 分钟）

坑：
- 引用是行 id 的十进制字符串，docstring 写明了。返回 int 会挂。
- 字符串内容也要按 JSON 存。字符串原样存、其他按 JSON 存的话，读回时分不清 `'["not", "a", "list"]'` 是字符串还是列表。
- 去重按 JSON 文本，不按 Python 相等：`[1] == [1.0] == [True]` 在 Python 里都成立，但它们是三份不同的内容。
- 去重要落在数据库里（`UNIQUE` 加 `INSERT OR IGNORE`），只放在内存字典里的话，重开后同一内容会拿到新行。
- 删除后行 id 不能复用。没有 `AUTOINCREMENT` 时，删掉最大的那一行，下一次 insert 会拿回同一个 id，旧 span 上的引用就指向了别人的内容。
- 删除也要提交。只在 `put` 里提交、`delete` 不提交的话，同一个连接里看着删掉了，关掉重开后内容又回来了。测试在最后一次重开后会再 `get` 一次被删的引用。
- 软删除（行留着，加一个 deleted 标记）不算擦除：正文还在库里，而且同样的内容再 `put` 进来时 `INSERT OR IGNORE` 命中那一行，交出的是已经作废的引用。测试最后会把那条 SSN 再 `put` 一次。
- 非数字的引用要报 KeyError，`int(ref)` 会报 ValueError；删除不存在的引用也报 KeyError。
- 最后一段是集成检查：Part 1 修好的 tracer 加上这个 store，工具 span 上只有行 id。

追问：
- "A user asks you to erase their prompts. What else holds them?"（备份、WAL、下游复制；span 上留下的是失效引用，正因为 id 不复用才安全）
- "Why not put the content in a span event?"（span 会被运维看到，也会被复制到各个后端；课里的建议就是存外部、span 只带指针）
- "Two writer processes?"（SQLite 的写锁；`INSERT OR IGNORE` 加 `SELECT` 在一个事务里仍然是对的）

### Part 3 工具错误按模型归因（目标 12 分钟）

坑：
- 工具 span 要在自己的 invoke_agent 下面找 chat span。两个 agent 并发时，按时间在全局找“最近的 chat”会把 tool 15 算到 openai 头上。
- 模型用 `gen_ai.response.model`（真正回答的模型，路由后可能不同），没有时才用 request model。集成段里第二个 chat 没有 response model，专门测这个回退。
- chat span 缺 `gen_ai.provider.name` 时，取最近的 invoke_agent 祖先的 provider（课里的 “No `gen_ai.provider.name`”）。
- 反过来，chat 自己带 `gen_ai.provider.name` 时用它自己的。合成数据后面单独有一个默认用 openai 的 agent，它这一次模型调用走了 Bedrock，要记在 aws.bedrock 下面；先取 agent 的 provider 会挂。
- 有的框架把工具 span 挂在 chat span 下面，这时父节点就是发起它的 chat。
- 孤儿：没有父节点、父节点不在数据里、父节点是别的工具、或者之前没有 chat 的工具 span，都单独计数，不进任何行（课里的 “Spans without parent links”）。
- `<=` 和平票：chat 和工具同一纳秒开始也算；平票取较小的 span_id。输入顺序是打乱的，测试还会把同一批 span 倒过来再算一遍，结果必须一样，所以按输入里先见到或后见到的那个定平票都会挂。
- 行按 (provider, model, tool) 排序。

追问：
- "Error rate 1/1 vs 40/1000: which one do you page on?"（样本量；给比例加置信区间，或者设最小调用数）
- "Correlation or cause?"（同一个工具在某个模型下错误多，可能是那个模型生成的参数差，也可能是那个 agent 用的数据源不同；要按 `gen_ai.data_source.id` 再切一刀）
- "Spans arrive from several services. What breaks?"（父 span 可能晚到或丢失；孤儿计数就是数据质量指标）

### Part 4 实时 span 流（目标 14 分钟）

坑：
- 格式由测试的解析代码决定：每个 span 一行 JSON，以 `\n` 结尾。id 是补零的小写十六进制（trace 32 位，span 16 位），根的 `parent_span_id` 是 null，纳秒时间戳原样写整数。种子 0 下有一个 span id 小于 2⁶⁰，`:x` 不补零会被抓到。失败那一段的 tracer 用种子 34，trace id 最高的一位十六进制是 0，`:x` 或照抄 span id 的 `:016x` 都只写出 31 位。
- 每个 span 一结束就要产出一行。测试里的工具在等一个 Event，只有消费方拿到第一行后才放行；先等 run 结束再输出会卡住，测试 2 秒后报 “as soon as its span ends”。
- 写成普通的 `async def` 时，测试报 `'async for' requires an object with __aiter__`，要看出这里需要 async generator。
- `asyncio.create_task(run)` 只收协程。第一段传进来的是 `asyncio.gather` 返回的 future，会报 `TypeError: a coroutine was expected`；用 `asyncio.ensure_future`，或者包一层 `async def`。
- run 结束后要把队列里剩下的行都发完再停。用 `task.done()` 判断提前退出，会丢掉最后结束的根 span（失败的 run 里最明显）。反过来，在 `queue.get()` 外面套 `while not task.done()` 也不行：第一段的 run 是 `gather` 返回的 future，最后一个 span 出队时它还没标记完成，循环会卡在下一次 `queue.get()` 上，2 秒后报同一个超时。
- run 抛出的异常要在最后一行之后再抛给消费方，不能吞掉。
- 消费方提前 `aclose()` 时，要取消 run 并等它真的结束：`aclose()` 一返回，测试就检查工具已经收到 CancelledError、run 的三个 span 都已结束。只 `cancel()` 不 await，或者 `cancel()` 之后 `sleep(0)` 一下，都会挂；await 时不吞掉 CancelledError，`aclose()` 会把它抛给消费方。
- feed 只在生成器运行期间挂在 tracer 上：正常结束、run 失败、提前关闭，三种情况都要从 `tracer.processors` 移除。
- 两个 agent 用 `gather` 并发，工具 span 的父节点必须是各自的 agent，这一段依赖 Part 1 的 contextvars。

测试抓不到、可以接受但要追问的写法：不挂 processor，在循环里轮询 `tracer.finished` 再 `await asyncio.sleep(0)`。行为上没错，但 run 等模型的那几秒里它一直空转占着 CPU，`finished` 也只增不减；问候选人换成 processor 加队列会怎样。

追问：
- "The collector is remote and slow. What changes?"（有界队列加丢弃策略和计数；批量导出；不能让 agent 等导出）
- "Why a done callback rather than polling task.done()?"（回调排在任务最后一个 span 之后入队，顺序天然正确）
- "A tool span is still open when the feed stops. Where does it go?"（tracer 照常记录；可以在 shutdown 时补导出或明确丢弃）

### Part 5 嵌套 agent 的用量汇总（目标 12 分钟）

坑：
- 每个 invoke_agent span 是一个 run，同名的两个 researcher 是两个 run。按名字做键会合并。
- chat 的 token 只归最近的 invoke_agent 祖先（own），不往上重复记；total 再把子 run 的 total 加上去。
- 子 agent 挂在 tool_call span 下面，不是 agent span 的直接子节点。只按 `parent_span_id == agent.span_id` 找子 run 会漏掉。
- chat 也会挂在 tool_call 下面（chat 13 在 planner 的 tool 9 下面），token 照样算进最近的 invoke_agent。只看直接父节点是不是 agent，会把它算进 unattributed，planner 的 own 变成 (100, 10)。
- depth 数的是上面有几个 agent run，不是几层 span。
- 父 span 没收到的 auditor 是独立的根；没有 agent 祖先的 chat（包括父节点不在数据里的）进 unattributed。
- 没有 token 属性的 chat 记 0。
- 输出按先序，根和兄弟按 start_ns 再按 span_id 排。输入是打乱的。
- 最后是集成检查：`agent_tool` 把 researcher 当成 lead 的工具，真实跑一遍再汇总。

追问：
- "Cost per run?"（按 provider 和 response model 的单价乘 token；同一个 run 里可能用了多个模型）
- "Parent ids form a cycle in corrupt data. What happens to your code?"（参考答案向上走时记录已访问的 span，不会死循环）
- "A sub-agent runs in another process?"（靠 trace context 传播把父 span id 带过去；没带过去就成了这里的孤儿根）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出隐私、删除、背压、跨进程、成本 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
