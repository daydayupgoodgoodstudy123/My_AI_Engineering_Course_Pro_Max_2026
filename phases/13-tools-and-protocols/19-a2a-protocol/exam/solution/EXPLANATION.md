# 参考答案讲解：agentcard（13/19）

计时结束后再看。参考实现在同目录的 `agentcard/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 writer 和下载

**现象**：解锁后的第一个错误是 `artifact_chunks` 里的 `AttributeError: 'NoneType' object has no attribute 'parts'`，而 `artifact_chunks` 本身没有 bug。

**顺着往上找**：`artifact_chunks` 取的是任务的 artifact，可这个任务根本没有 artifact。没有 artifact，是因为任务没走到 completed，停在了 input_required，最后一条 agent 消息在要 targetLength。可第一条消息里明明有 targetLength，只是放在三个 data part 的中间那个；`target_length` 只看 `data[0]`。这一关想练的是：报错的位置（下载）离出错的位置（读输入）隔着两层调用，要先问“这个对象为什么是这个样子”。

**依次修四处**：

1. `target_length` 依次看每个 data part，返回第一个带 targetLength 的。改成 `data[-1]` 也会挂，因为测试里它在中间。
2. `tasks_send` 先查卡片上有没有这个 skill。没有就从 submitted 直接到 rejected，加一条点名这个 skill 的 agent 消息，然后返回，不进入 working。rejected 是“不接这个活”，failed 是“干了但失败”，两者不能混用。检查要读 `self.card["skills"]`，写死 `"draft_report"` 的话，换了卡片的 writer 就会挂。
3. `tasks_reply` 在改动任何东西之前检查终态：completed、failed、canceled、rejected 都抛 TaskError。先记下消息再检查，任务已经被改了；只检查 completed，rejected 的任务还能被复活。
4. `ArtifactAssembler.add` 只解码这一片新凑齐的 4 字符组，余数留到下一片：

```python
def add(self, chunk):
    text = self._pending + chunk
    whole = len(text) - len(text) % 4
    self._received += base64.b64decode(text[:whole], validate=True)
    self._pending = text[whole:]
```

原来的写法每来一片都把累积的整段文本拼接、切片、校验、解码一遍，2 万片是平方级，本机 1.2 到 1.5 秒；改完以后 4 毫秒左右。`_received` 用 bytearray，追加是均摊 O(1)。

**护栏**：最常见的提速写法是每片单独 `b64decode(chunk)`。base64 以 4 个字符为一组，分片的边界在组中间时，单独解码要么报 Incorrect padding，要么补了 `=` 以后解出错的字节。另一种是全部攒到 `finish()` 再解码：快是快，但 `received` 不再随分片增长，坏的组也要等到最后才发现，docstring 要求的两件事都丢了。重写时还要保留 `validate=True`：默认模式会悄悄丢掉字母表以外的字符，一组 base64url 的 `----` 会被当成空的组放过去。

## Part 2 SQLite 任务库

五张表：tasks（id、skill、当前 state）、history（task_id、seq、state）、messages（task_id、seq、role）、artifacts（task_id、name、mime_type）、parts（task_id、message_seq、seq、type，以及 text、name、mime_type、content、data 几列，message_seq 为 NULL 的是 artifact 的 part）。`save` 先把所有 part 转成行，未知类型在这一步就抛 ValueError；然后在一个 `with self._db:` 里删掉这个任务的旧行，再全部插入新行。

要点：

- **字节原样存**。file part 的 content 列是 BLOB，存的就是原始字节，含 NUL、CRLF、`\xff` 都没问题。latin-1 文本或 base64 文本也能往返，但不符合 docstring，测试会扫描整个数据库找原样的 BLOB。
- **顺序靠整数序号**。消息和 part 各自带 seq，读的时候 `ORDER BY`。part 不能按类型分开存再拼，文本列里的序号会把 10 排到 2 前面。
- **data part 用 JSON 文本**。`json.dumps` 和 `json.loads` 保住键序和每个值的类型，包括 bool 和超过 64 位的整数。不要 `sort_keys`，也不要让数字经过 SQLite 的 JSON 函数或者 REAL、NUMERIC 列。因为 `True == 1`、`1 == 1.0`，测试另外逐个比较了类型。
- **历史是序列**。working 和 input_required 会重复，按 seq 存，不能去重。
- **替换，而且要么全成，要么全不成**。删和插在同一个事务里，失败时 `with` 自动回滚；先删再另开事务插，或者手动 commit 而不回滚，失败后同一个连接上就看到半截任务。
- **读出来的是存进去的样子**。`load` 每次从库里重新构造 Task，不返回 save 时传进来的对象。

## Part 3 卡片、签名与选 skill

签名的核心是一个函数：

```python
def canonical_json(card):
    body = {k: v for k, v in card.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
```

`sign_card` 对它做 HMAC-SHA256，结果用 base64url 编码、去掉 `=`，放进 `{"alg": "HS256", "kid": ..., "value": ...}`，返回一张新卡片。`verify_card` 先看 alg 和 kid，kid 不在 keys 里就是 False，再重新算一遍，用 `hmac.compare_digest` 比较。签名不覆盖它自己，所以再签一次的结果不变；键序和缩进不同的同一张卡片，规范化以后字节相同，签名也相同；改了任何字段，包括嵌套在 skill 里的，签名就对不上。

`check_card` 把讲义里卡片的形状逐条写成检查：几个顶层字符串非空，url 是绝对的 https 地址，skills 非空、id 不重复，inputModes 只能是 text、file、data，outputModes 只能是 text、artifact，capabilities 里的两个开关必须是布尔值。缺字段一律报 CardError，不让 KeyError 漏出去。

`choose_skill` 先把消息里的 part 类型收成集合，空消息直接报错；再按卡片顺序找第一个 inputModes 包含这个集合、outputModes 包含 wants 的 skill，交付方式由 `capabilities.streaming` 决定。都不满足就返回 None，`delegate` 也就什么都不发。测试里的卡片故意让“字母序”“完全相等”“模式最少”“只要有交集”这几种写法各自选错一次。

## Part 4 长度前缀帧

写端：

```python
task.move("working")
try:
    yield encode_frame(working)
    async for piece in pieces:
        if piece:
            yield encode_frame(artifact_piece(seq=len(text)))
            text.append(piece)
except ModelError as error:
    task.move("failed")
    yield encode_frame(failed(str(error)))
    return
except GeneratorExit:
    task.move("canceled")
    await pieces.aclose()
    raise
task.artifact = ...
task.move("completed")
yield encode_frame(completed)
```

- 每一帧单独 yield，working 在向模型要第一片之前发出，所以测试的探针看到“发 working 时模型还没被拉过，发第一片时只拉了一片”。
- 调用方关闭流时，GeneratorExit 从 yield 那里抛进来。这时不能再 yield，只能收尾：任务改成 canceled，并且主动 `aclose()` 模型的流。不主动关闭，模型那边的 finally 要等对象被回收后由事件循环另外安排，测试检查的那一刻还没跑。发 working 的那个 yield 也在 try 里面，刚收到 working 就关闭也能取消任务。发 completed 的那个 yield 在 try 外面，而且在任务改成 completed、挂上 artifact 之后：调用方读到 final 帧就关闭流，GeneratorExit 从这里抛出来，任务已经是终态，不会被改成 canceled。
- 长度是 JSON 编码后的字节数，`struct.pack(">I", len(body))`，不含长度本身的 4 个字节。

读端用一个 bytearray 缓冲：凑够 4 个字节就读长度，超过 MAX_FRAME 立刻报错；凑够正文才解出一个事件，删掉这一帧，接着看下一帧。artifact 的 seq 按名字分别计数；看到 final 的 status 以后，同一块里剩下的字节和以后的任何字节都报错；close 时缓冲里还有东西、或者从没见过 final，也报错。

## Part 5 多跳委托视图

一个递归函数 `run(node, hop)` 返回这个任务给它的调用方看的视图：

1. `hop > max_hops`：rejected，没有 artifact，不往下走。
2. 否则先按顺序跑完所有下游，拿到它们的视图；有下游就记到 `views[node["task"]]`。
3. 自己的 `fails`，或者某个 required（默认 true）的下游没有 completed，就是 failed，返回空 artifact。
4. 否则 completed，返回自己的 artifact（只留 name、mimeType、parts），后面按委托顺序接上每个 forward 的下游返回的东西。

根节点从 hop 1 开始，结果最后加上 `views["client"]`。重复的 id 在运行之前用 `_check_ids` 查整棵树，包括那些因为超过 max_hops 而从来不运行的子树。

这样写，不透明原则是自然成立的：一个调用方拿到的只是下游的返回值，不是下游的 plan 节点，所以 steps、内部字段、更深的委托都碰不到；artifact 只有在每一跳都 forward 的时候才能一路传上去。失败也一样，每个任务按自己的规则决定自己的状态，下游失败不会越级影响更上游。同一个 agent 的两个任务各跑各的，结果按 task id 记。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的 A2A 代码里调试生命周期和分片解码、把任务连同字节和类型原样存进 SQLite、实现卡片校验和 HMAC 签名、按 inputModes 和 outputModes 选 skill、写有探针约束的流式帧编解码，以及在委托树上实现不透明的视图。它不涉及真正的 JSON-RPC 或 gRPC 传输、HTTP 和 SSE、JWT 与非对称签名、推送通知、认证授权和真实的 LLM 调用。讲义练习 4（把 MCP server 包成 A2A agent）也没有覆盖，需要另外动手。
