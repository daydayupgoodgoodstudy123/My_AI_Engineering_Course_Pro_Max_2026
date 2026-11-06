# 参考答案讲解：AgnoMastra（14/18）

计时结束后再看。参考实现在同目录的 `agnomastra/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修运行时

**现象**：解锁后第一个失败是会话隔离的断言。第二个请求属于 s2，它的 memory 里却有 s1 的 "my name is Ada"。

**依次修四处**：

1. `AgnoApp`：`__init__` 里只建了一个 agent，`handle` 每次都复用它，memory 在请求之间越积越多。改成在 `handle` 里为每个请求新建一个 `Agent`。课里说 "each request starts a fresh agent; session state lives in a DB"：agent 只活一个请求，会话状态在 session store 里。课里的 `main()` 也只建了一个 agent 传给每个请求，那里的 agent 没有 memory，所以看不出问题。
2. `MastraAgent.run`：记下 schema 错误以后少了 `continue`，工具照样执行。报错出现在测试的 `search` 里（`'int' object has no attribute 'lower'`），离根因隔了两层。课里 TypeScript 版的 `checkSchema` 发现问题后就跳过这次调用，Python 版要做到同样的事。
3. `check_input`：遍历的是调用方传来的 `args`，schema 里有、`args` 里没有的字段根本不会被看到。`("search", {})` 因此通过了检查，工具在没有参数的情况下被调用，报 `TypeError: ... missing 2 required positional arguments`。第 2 处修好以前，类型错的调用会先在工具里出错，所以这一处要等补上 `continue` 才露出来。改成遍历 schema，和课里的 `checkSchema` 一样：按 schema 的顺序，每个字段先看在不在，再看类型，遇到第一个问题就返回。
4. `Agent.__init__`：每次都深拷贝整个注册表。只有一个 agent 的时候这笔开销只付一次；每个请求都新建 agent 以后，1000 个工具、300 个请求要 0.8–1.6 秒。注册表是只读的，直接引用即可，创建 agent 的开销就和工具数量无关了。

**第 3 处容易修错的地方**：只在原来的循环前面或者后面补一段缺字段检查，报出来的会是另一个字段的问题。`{"limit": "ten"}` 按 schema 的顺序先缺 query，应该报 missing field query，补在后面会先报 limit 的类型；`{"query": 7}` 的第一个问题是 query 的类型，补在前面会报缺 limit。`sorted(set(schema) - set(args))` 按字母序找缺字段，`{}` 会报成缺 limit。缺字段要用 `key not in args` 判断：`args.get(key) is None` 会把显式传来的 None 当成缺字段，其实这个字段在，类型是 null，Zod 也把这两种情况分开报（一个收到 undefined，一个收到 null）；`not args.get(key)` 还会把 `limit: 0` 当成缺。类型要用 `type()` 查表：`isinstance(True, int)` 是 True，改用 `isinstance` 会把布尔值当成数字。

**护栏**：最省事的“修法”是继续复用一个 agent、每次 run 先清空 memory，或者修计时的时候再把 agent 缓存回去。单线程下结果看起来也对，但违背了“每个请求一个新 agent”，并发请求会互相覆盖 memory。测试检查 3 个请求用了 3 个不同的 agent 对象。另一个是把深拷贝换成 `dict(tools)`：300 个请求只要 1 毫秒左右，计时能过，但开销仍然随注册表增长，测试检查所有 agent 共用同一个注册表对象。

第三个护栏是 workflow 的 trace。起始代码里的 `Workflow.run` 已经把每一步的输出 `copy.deepcopy` 一份再存，后面的步骤原地修改 payload，前面的记录不会跟着变。课里的 `MastraWorkflow.run` 直接存引用，步骤返回新字符串时看不出问题，步骤改 dict 时就会改写前面的记录。修第 4 处时如果把这里的深拷贝一起删掉，或者改成浅拷贝（`tags` 列表和 `meta` 字典还是共享的），trace 的断言就会挂。同样是 `copy.deepcopy`，放在注册表上是多余的开销，放在 trace 上是必需的，区别在于这份数据之后会不会被改。

## Part 2 组合存储

三类记录各进一个后端，和课里 Mastra 的 composite storage 一样：

- **memory**：SQLite，一条消息一行，`seq` 自增列保证顺序，`with self._db:` 自动提交。
- **workflows**：每个 run 一个 JSON 文件，文件名是 run id 的 sha256，run id 本身存在文件里。这样斜杠、`..`、大小写、长度都不会影响路径，`runs()` 读出 run id 再排序。
- **observability**：每次 `record` 用 `"a"` 模式追加一行 JSON。

容易漏的几点：

- **精确往返**：`json.dumps` 加 `json.loads` 能保留键顺序、`True`、`2.0`、大整数和 `-0.0`。加了 `sort_keys` 就改了键顺序。pickle 也能原样往返，但文件就不是 JSON 了，测试会逐个解析快照文件。
- **文件名**：run id 直接当文件名会出错或写到目录外面；把 `/` 换成 `_` 会让两个不同的 run 撞成一个文件；URL 编码或 base64 遇到 349 个字符的 backfill run id 会超过文件名 255 字节的上限。哈希值长度固定，没有这些问题。
- **日志分行**：测试要求日志是可读的 UTF-8，所以写的时候用 `ensure_ascii=False`。这时 U+2028（LINE SEPARATOR）会原样写进文件，`str.splitlines()` 把它当成换行。读的时候要按 `"\n"` 切。
- **重开**：日志文件不能在打开时清空；SQLite 的插入要提交，否则 `close()` 时就丢了。
- **空 run id**：docstring 要求报 ValueError。

## Part 3 容量规划

每一段用 Little 定律：`in_flight = rate × 服务时间`，`utilization = in_flight / workers`。全部用 Fraction 算，时间先解析成整数纳秒。

- `parse_duration` 用 Decimal，`2.05s` 得到 2050000000。float 乘 10⁹ 再 `int()` 会得到 2049999999。`1.5ns` 不是整数纳秒，要报错；`+2ms`、`-2ms` 带符号，也要报错。
- `μs`（U+03BC）和 `µs`（U+00B5）都要认。课里写的是希腊字母，但不少工具输出的是微符号。
- 利用率 ≥ 1 就撑不住，所以 `workers_needed = floor(in_flight) + 1`。in_flight 正好是 54 时要 55 个，不是 54 个。
- 瓶颈按 (−利用率, −服务时间, 顺序) 取最小的那个。比的是利用率，不是服务时间：每秒 2000 个请求的 fan-in 里，1 毫秒、只有 1 个 worker 的实例化利用率是 2，50 毫秒、200 个 worker 的模型只有 1/2，瓶颈是实例化。
- `max_rate` 是各段 `workers / 服务时间` 的最小值，和当前的 rate 无关，rate 为 0 时也能算。
- `latency_saving` 的分母是原来的端到端时间。

这组数据算出来：模型调用 1.8 秒，占了 1.966 秒中的绝大部分。把 40 毫秒的实例化换成 2μs，只省下大约 2%。这就是课里说的 "Perf-for-perf's-sake"：一个请求只调一次慢模型时，实例化开销不是瓶颈。反过来，fan-in 那组数据里实例化本身就是瓶颈，这时 2μs 才值钱。

## Part 4 流式后端

```python
lock = self._locks.setdefault(session_id, asyncio.Lock())
async with lock:
    yield HEADERS
    messages = self.store.history(session_id) + [f"user: {prompt}"]
    async with aclosing(self.model(messages)) as tokens:
        async for token in tokens:
            data = token.encode("utf-8")
            if not data:
                continue
            yield b"%x\r\n" % len(data) + data + b"\r\n"
    # 回复完整以后、发最后一块之前写入两轮
    yield b"0\r\n\r\n"
```

- 每个会话一把 `asyncio.Lock`。它是先来先得的，第一次迭代就去排队，所以同一会话的请求按开始顺序执行，不同会话互不等待。
- 历史在拿到锁以后读，排在后面的请求能看到前一轮。
- 长度是 UTF-8 字节数，只写十六进制数字（`%x`，不是 `hex()` 的 `0x11`）。空 token 跳过，否则 `0\r\n\r\n` 会提前结束回复；只有空格的 token 照发。
- 每个 token 一到就 `yield`，测试里的模型停在第一个 token 之后，第一块必须已经发出去。
- 两轮对话在发出 `0\r\n\r\n` 之前写入。客户端拿到最后一块就认为回复完整，可能马上断开，也可能马上发下一个请求。
- 客户端 `aclose()` 时，生成器在 `yield` 处收到 GeneratorExit，`async with` 会释放锁，`aclosing` 会关掉模型的流。两轮对话只在回复完整后写入，中途断开的请求什么都不留下。

## Part 5 工作流 schema 检查

`first_mismatch(src, dst)` 回答的是“src 产出的每个值，dst 都能接受吗”。处理顺序很重要：

1. 先处理 optional：源可能缺失，目标就必须也是 optional。
2. 再拆源的 union：每个成员都要兼容。
3. 再拆目标的 union：有一个成员兼容就行。顺序反了，`string | integer` 交给 `integer | string` 会被判成不兼容。
4. 然后比较种类：`integer` 可以给 `number`；数组递归比较元素，路径加 `[]`；对象按目标的字段顺序检查，必填字段在源里必须存在而且不能是 optional，目标里 optional 的字段源里可以没有，strict 的目标不允许多余字段。

`check_flow` 先检查结构，再检查链接。结构检查走遍每一层：任何一层的空工作流都报错；“自己包含自己”只看当前这条嵌套路径，所以同一个子工作流用两次是允许的，全局的 visited 集合会把它误判成环。嵌套工作流的边界一直往里找到叶子步骤：输入取第一个叶子，输出取最后一个叶子。链接按数据经过的顺序检查：先查进入某一步的链接，再递归检查这一步里面的链接。名字带上所有外层工作流的名字，比如 `pipeline/outer/enrich/score`。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里找出共享实例、漏查的必填字段和多余的拷贝，同时分清哪一份拷贝必须留着，能设计按类型分后端的存储并保证精确往返，能用 Little 定律做精确的容量估算，能写出符合 HTTP/1.1 chunked 编码、按会话串行的异步流式处理，并能对嵌套结构做递归的类型兼容判断。它不涉及真实的 Agno 或 Mastra 代码，不涉及 FastAPI、Zod、Vercel AI SDK 的具体 API，也不涉及多进程部署和真实的模型调用。课里 Exercises 1、2、4、5 需要读两个框架的文档，另外动手做。
