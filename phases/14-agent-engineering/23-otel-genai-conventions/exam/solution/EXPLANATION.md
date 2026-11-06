# 参考答案讲解：SemConv（14/23）

计时结束后再看。参考实现在同目录的 `semconv/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 agent 的 span

**现象**：解锁后的第一个错误是 `Span.set_attribute` 里的 TypeError：`attribute 'gen_ai.agent.name' must be str, bool, int or float, got NoneType`。`set_attribute` 本身没错，它只是照 docstring 拒绝 None。

**顺着往上找**：`set_attribute` 由 `start_span` 调用，`start_span` 由 `Tracer.span` 调用，属性字典来自 `run_agent` 调用的 `agent_attributes`。测试里的 agent 没有名字，`agent_attributes` 却无条件写了 `"gen_ai.agent.name": agent.name`，`agent_span_name` 也拼出了 `invoke_agent None`。课里的规则是：有名字用 `invoke_agent {gen_ai.agent.name}`，没有名字就回退成 `invoke_agent`，属性也不写。

**依次修四处**：

1. agent.py：`agent_attributes` 只在 agent 有名字时写 `gen_ai.agent.name`；`agent_span_name` 在没有名字时只返回操作名。create_agent 和 invoke_agent 两种 span 都用这两个函数，改这一处两种都对了。
2. tracer.py：当前 span 放进 `contextvars.ContextVar`。原来的共享栈在 `asyncio.gather` 下串台：search 先开始，fetch 后开始时栈顶是 search，于是 fetch 成了 search 的子 span；search 先返回，`end_span` 又忽略参数直接弹栈顶，结束的是 fetch。改成 contextvars 以后，每个任务在创建时复制一份上下文，各自的“当前 span”互不影响。`end_span` 只结束传进来的那个 span，并且在它是当前 span 时把父 span 设回当前，否则后面的 chat 会挂在已经结束的 chat 下面。
3. agent.py：create_agent 在构造时记，invoke_agent 在运行时记。原来 `create_agent()` 什么都不记，`run_agent` 每次一开头在 invoke_agent 下面记一个 create_agent：一个 agent 跑几次就“被创建”几次，而且每次都挂在运行里面。课里 Span categories 的说法是 create_agent 对应构造，invoke_agent 对应运行；课里的代码也是先记一个立刻结束的 create_agent，再开始 invoke_agent。改法是把那两行从 `run_agent` 挪进 `create_agent()`：建好 `Agent` 之后开始一个 create_agent span，马上结束。测试按 `gen_ai.operation.name` 计数：构造完恰好一个，在原来的 tracer 和另一个 tracer 上各跑一次，都不再增加。在任何 run 之外构造的 agent，create_agent 是一个根 span，和课里代码一样。
4. tracer.py：默认时钟用 `time.time_ns`。`perf_counter_ns` 是单调时钟，起点不确定，两个进程的 span 对不到一条时间线上。

**性能**：`put` 为了去重逐条比较已有内容，n 条内容是 O(n²)，18000 条在本机要 1.6–3.6 秒。加一个“JSON 文本 → 引用”的反向字典后是 7–15 毫秒。

**护栏**：

- 提速时不能把去重删掉。
- 时间戳必须是整数纳秒，`time.time() * 1e9` 是 float。
- 默认构造的 tracer 仍要自己建 store，给了 store 就用给的那个。写成课里代码的 `content_store or ExternalContentStore()` 不行：store 有 `__len__`，空 store 是假值，会被悄悄换掉，测试读内容时报 KeyError。起始代码用的是 `is None` 判断。
- 在 `set_attribute` 里吞掉 None 只是把报错藏起来，span 名照样错。
- create_agent 只挪到 invoke_agent 外面、却还是每次运行都记，或者等到第一次运行才补记，构造完都是零个。构造时只 start 不 end 也是零个：span 没结束，不算记过，而且它一直是当前 span，后面的 invoke_agent 会挂到它下面。
- 构造时记了，却没删 `run_agent` 里那两行，跑一次就有两个。每换一个 tracer 补记一次也不对：agent 只创建一次。
- 未命名 agent 的 create_agent 也叫 `create_agent`，自己拼 `f"create_agent {name}"` 会得到 `create_agent None`；它和 invoke_agent 一样要带 `gen_ai.provider.name`。

## Part 2 SQLite 内容库

一张表：`id INTEGER PRIMARY KEY AUTOINCREMENT`、`body TEXT NOT NULL UNIQUE`。任何内容都先 `json.dumps` 再存，读回时 `json.loads`：

- 字符串也按 JSON 存，读回时才能分清 `'["not", "a", "list"]'` 是字符串，不是列表。
- 去重按 JSON 文本：`INSERT OR IGNORE` 之后 `SELECT id WHERE body = ?`。JSON 文本区分 `1`、`1.0` 和 `true`，Python 的 `==` 不区分，所以不能读出来再比较。去重落在数据库里，重开后依然有效。
- 引用是行 id 的十进制字符串。`get` 和 `delete` 先检查引用是不是纯数字，不是就报 KeyError，而不是让 `int()` 报 ValueError。
- `AUTOINCREMENT` 保证删掉的 id 不会再发出去。没有它，SQLite 用当前最大 rowid 加一，删掉最大的那一行后，下一条内容会拿到同一个 id，旧 span 上的引用就指向了别人的 prompt。这正是内容外存要防的事。
- 删除和写入一样在事务里提交（同样用 `with self._db:`），否则关掉重开后被删的内容又回来了。删除就是真的 `DELETE`：打标记的软删除只是把正文藏起来，同样的内容再 put 进来时还会拿回那个作废的 id。

最后的集成段把 Part 1 的 tracer 接到这个 store 上：工具 span 上只剩 `gen_ai.tool.result.reference_id`，值是行 id，正文只在数据库里。

## Part 3 工具错误按模型归因

先建 `span_id → span` 的索引，再把 chat span 按父节点分组。对每个 `gen_ai.operation.name == "tool_call"` 的 span：

1. 父节点是 chat span：就是它发起的。
2. 父节点是 invoke_agent span：在同一个 invoke_agent 下面，取开始时间不晚于工具的 chat span 里最晚的一个，平票取较小的 span_id。
3. 其他情况（没有父节点、父节点不在数据里、父节点是别的工具、之前没有 chat）：记为孤儿，不进任何行。

模型取 chat 的 `gen_ai.response.model`，没有就取 request model。provider 取 chat 自己的 `gen_ai.provider.name`，没有就沿父链找最近的 invoke_agent。错误看有没有 `error.type`。

测试数据里两个 agent 在时间上交错：tool 15 开始前，全局最近的 chat 是 openai 那边的 chat 21，只有限定在同一个 invoke_agent 下才能找到 anthropic 的 chat 14。tool 15 也正是路由到 `claude-sonnet-4-5` 的那一轮，按 request model 统计会把它算到 opus 头上。

平票按 span_id 定，结果和输入顺序无关，测试把输入倒过来再算一遍来检查这一点。provider 先看 chat 自己的：同一个 agent 的某次调用可能被路由到别家，合成数据后面单独的那个 agent 默认用 openai，这次调用走了 Bedrock，就记在 aws.bedrock 下。

## Part 4 实时 span 流

用一个 `asyncio.Queue` 做 processor：`on_end` 把 span 放进队列。run 包成 task，再给 task 加一个完成回调，往队列里放结束标记：

```python
task = asyncio.ensure_future(run)
task.add_done_callback(lambda _: queue.put_nowait(_DONE))
while True:
    item = await queue.get()
    if item is _DONE:
        break
    yield json.dumps(span_record(item)) + "\n"
task.result()
```

- 所有 span 都在 task 内部结束，完成回调一定排在最后一个 span 之后，所以不会丢行，也不需要轮询 `task.done()`。
- 每个 span 一入队就被 `yield` 出去，所以工具还在等 Event 时，消费方已经拿到第一行 chat。
- `task.result()` 在最后一行之后把 run 的异常重新抛出。
- `finally` 里：run 还没结束就取消它并 await，所以 `aclose()` 返回时工具已经收到 CancelledError，run 的 span 也都结束了；然后把 processor 从 tracer 上摘掉。run 正常结束、失败、被提前关闭都会走到这里。
- `span_record` 用 `:032x` 和 `:016x` 补零，根的父 id 写 null，纳秒时间戳原样写整数。失败那一段的 trace id 最高一位是 0，不补零只有 31 位。

## Part 5 嵌套 agent 的用量汇总

1. 每个 invoke_agent span 是一个 run，用 span_id 做键。
2. 每个 chat 沿父链向上找最近的 invoke_agent（中间可以隔着 tool_call，测试里 chat 13 就挂在 tool 9 下面），token 加到这个 run 的 own；找不到就加到 unattributed。缺失的 token 属性记 0。
3. 每个 run 的父 run 也是“最近的 invoke_agent 祖先”，没有就是根。这样挂在工具 span 下的子 agent 也能找到父 run，父 span 没收到的 auditor 自成一根。
4. 先序遍历，根和兄弟按 (start_ns, span_id) 排，同时记录 depth。再按逆先序算 total：每个 run 的 total 是 own 加上各子 run 的 total。

向上找祖先时记录已访问的 span，脏数据里出现环也不会死循环。

## 这套题证明了什么，没证明什么

通过了说明你能在 asyncio 代码里排查 span 的父子关系和上下文传递，能按课里的 span 类别分清 agent 的创建和运行各记什么，能把内容按引用存进 SQLite 并保证读回完全一致、删除后引用不复用，能只凭 GenAI 属性做工具错误和模型的关联，能写一个边跑边输出、能正确收尾和取消的 async generator，也能处理 agent 调 agent 的嵌套树。它不涉及真实的 OpenTelemetry SDK、OTLP 导出和 Collector，不涉及跨进程的 trace context 传播，也不验证 `OTEL_SEMCONV_STABILITY_OPT_IN` 下属性名的变化；这些要照课里的练习 1 和练习 4 另外动手。
