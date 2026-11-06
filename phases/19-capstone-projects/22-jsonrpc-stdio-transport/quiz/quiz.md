# 测验 · 通过换行分隔的 stdio 传输 JSON-RPC 2.0（JSON-RPC 2.0 Over Newline-Delimited Stdio）

> **阶段 19 · 综合项目 · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么是 JSON-RPC | 讲义：规范只有两页，在 stdio、socket、websocket、HTTP 上形状一致；客户端可以驱动一个从未见过的服务端 |
| 2 | 四种信封 | 客户端发：request（有 `id`）、notification（无 `id`）；服务端发：success（`result`）、error（`error: {code, message, data?}`）；每条都带 `"jsonrpc": "2.0"` |
| 3 | 换行分帧 | 一行一个 JSON 对象，边界是 `\n`；`json.dumps` 会把字符串中的换行转义成 `\\n`，所以序列化结果本身不含裸换行 |
| 4 | notification 规则 | 没有 `id` 的消息不得响应，即使处理出错也保持沉默；否则客户端无法把响应对应到调用点 |
| 5 | batch | 一行是 JSON 数组；返回数组，只包含非 notification 的响应；全是 notification 时什么都不写；空数组 `[]` 返回单个 `-32600` 错误 |
| 6 | 五个标准错误码 | `-32700` Parse error、`-32600` Invalid Request、`-32601` Method not found、`-32602` Invalid params、`-32603` Internal error；`-32000～-32099` 留给服务端自定义 |
| 7 | parse error 的 id | 无法解析就拿不到 id，响应中 `id` 必须为 `null` |
| 8 | 流不被污染 | 一行坏 JSON、缺 `method`、handler 抛异常，都只影响这一行，循环继续读到 EOF |
| 9 | 分层 | 传输层只认 JSON-RPC，不知道有哪些方法；`handler(method, params)` 背后才是注册表，第 23 节的分派器把两者缝起来 |
| 10 | 用 BytesIO 演示 | `io.BytesIO` 提供与真实管道相同的 `.readline()` / `.write()`，演示与测试无需起子进程 |

### 核心技能（能动手做到）

- [ ] 手写合法与非法的 JSON-RPC 消息，并预测服务端每一行的输出（包括 batch 与 notification）
- [ ] 把 handler 抛出的异常映射到正确的错误码，并能自定义 `-32000` 段的服务端错误
- [ ] 用 `io.BytesIO` 驱动 `serve`，写出端到端测试
- [ ] 找出会让整个 `serve` 循环崩溃的输入（非法 UTF-8、不可序列化的结果）并修复
- [ ] 为 handler 设计"调用过程中发送进度 notification"的接口
- [ ] 说清 newline 分帧与 `Content-Length` 头分帧的取舍，以及 stdio 服务端为什么不能往 stdout 打日志

---

## 二、基础自测（选择题）

**Q1.** 在线上（wire）区分 JSON-RPC notification 与 request 的依据是：

- A. notification 的 `method` 以 `$/` 开头
- B. notification 的 `params` 必须是数组
- C. notification 没有 `id` 字段；服务端不得对它作出响应
- D. notification 的 `jsonrpc` 字段是 `"2.0-notify"`

**Q2.** 为什么"换行分隔的 JSON"足以作为 stdio 上的分帧方式？

- A. 合法 JSON 的字符串内部不能出现未转义的换行，序列化时换行会被写成 `\n` 转义序列，因此一个对象可以完整地放在一行里
- B. 因为 stdio 管道每次 `write` 都恰好是一条消息
- C. 因为操作系统会自动在每个 JSON 对象后加换行
- D. 因为 JSON-RPC 规范规定了必须使用换行分帧

**Q3.** 服务端读到一行无法解析的 JSON，会返回：

- A. `-32600`，`id` 为该行中出现的 id
- B. 不返回任何内容并关闭连接
- C. `-32603`，`data.exception` 为 `JSONDecodeError`
- D. `-32700`，`id` 为 `null`，然后继续读下一行

**Q4.** handler 抛出普通的 `ValueError("kaboom")`，本节传输层返回：

- A. `-32602 Invalid params`
- B. `-32603`，`message` 为 `"internal error"`，`data` 为 `{"exception": "ValueError", "detail": "kaboom"}`
- C. `-32601 Method not found`
- D. 异常向上抛出，`serve` 结束

**Q5.** 一行 batch 中的三个元素全部是 notification，服务端会：

- A. 返回空数组 `[]`
- B. 返回 `-32600` 错误
- C. 返回三个 `null`
- D. 什么都不写

**Q6.** 服务端收到一行 `[]`（空 batch），会返回：

- A. 一个**单独的**错误对象（不是数组）：`{"jsonrpc": "2.0", "id": null, "error": {"code": -32600, "message": "empty batch"}}`
- B. 空数组 `[]`
- C. 什么都不写
- D. `-32700` 解析错误

**Q7.** 收到 `{"jsonrpc": "2.0", "id": true, "method": "echo"}`，本节代码的响应是：

- A. 正常执行 `echo`，`id` 为 `true`
- B. 当作 notification 处理，不响应
- C. `-32600` 错误，但响应里的 `id` 被原样回显为 `true`
- D. `-32700` 错误，`id` 为 `null`

**Q8.** 运行 `python main.py`，演示向服务端写入 6 条 JSON 行（4 个 request、1 个 notification、1 个含 3 个元素的 batch）和 1 行坏 JSON。服务端 stdout 一共输出多少行？

- A. 5 行
- B. 6 行
- C. 7 行
- D. 9 行

---

## 三、动手 / 代码题

**Q9.** 阅读 `serve` 的主循环：

```python
    while True:
        line = transport.read_line()
        if line is None:
            return
        text = line.decode("utf-8").rstrip("\n").strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            transport.write_error(None, ERR_PARSE, f"parse error: {exc}")
            continue
        ...
        resp = _handle_one(handler, transport, req)
        if resp is not None:
            _write_raw(transport, resp)
```

讲义承诺"Handle one parse error per line without poisoning the rest of the stream"。请找出**至少两种**能让整个 `serve` 抛异常退出、后续合法请求都得不到处理的输入，并给出修复代码。另外，handler 返回 `float("nan")` 时会发生什么？

**Q10.** 讲义写道："The demo shows the pattern: a request comes in, the handler emits two progress notifications, then writes the final response."

1. 本节的 `_demo` 和测试真的演示了这个模式吗？`Handler` 的签名允许 handler 发 notification 吗？
2. 在**不修改** `serve` 的前提下，设计一个包装函数，让 handler 可以在处理 `slow.job` 时发两次 `progress` notification 后返回 `{"done": true}`，写出代码并给出 stdout 上的三行输出。

**Q11.** 手工推演：服务端依次读到下面 4 行，写出每一行对应的输出（没有输出的写"无"）：

```text
[1, {"jsonrpc": "2.0", "id": 2, "method": "nope"}, {"foo": 1}]
{"jsonrpc": "2.0", "id": null, "method": "echo", "params": {"x": 1}}
{"jsonrpc": "1.0", "method": "echo"}
42
```

（handler：`echo` 返回 `params`，其他方法抛 `MethodNotFound`。）

**Q12.** Q7 中 `id: true` 被原样回显。同样，`{"id": {"a": 1}}` 会回显对象、`{"id": 1.5}` 会回显 `1.5`。

1. 这些回显有什么问题？JSON-RPC 2.0 规范对"检测 id 出错时"的响应 id 怎么规定？
2. 写一个 `_safe_id(msg)`，并说明应替换代码中哪些位置。

---

## 四、面试高频题

**Q13.**（基础必考）介绍 JSON-RPC 2.0：消息有哪几种？五个标准错误码分别在什么时候使用？request 和 notification 的处理有什么区别？

**Q14.**（原理深挖）stdio 传输有两种常见分帧：本节的"换行分隔 JSON"和 LSP 式的 `Content-Length` 头。比较两者。为什么 stdio 服务端绝对不能把日志 `print` 到 stdout？

**Q15.**（工程实践）讲义"Going further"说生产传输还要加 trace id、取消通道、内容协商。如果让你把本节传输层升级到生产可用，你还会补哪些能力？

**Q16.**（场景设计）一个 agent harness 同时通过 stdio 连接 12 个本地工具服务端子进程。描述进程生命周期、消息关联、错误隔离与可观测性的设计。

**Q17.**（追问型）规范要求服务端不响应 notification，即使处理失败也保持沉默。这样做的代价是什么？如果客户端确实需要知道某个"取消"或"日志"消息是否送达，应该怎么办？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："A notification has no `id`. The server must not respond to it. If a server returns a response to a notification, the client has no way to attach it to a call site." 代码中 `is_notif = "id" not in msg`——判断依据是**键是否存在**，因此 `"id": null` 的消息仍是 request。A 是 LSP 中某些协议级方法的命名约定（如 `$/cancelRequest`），与是否为 notification 无关；B、D 不存在。

### Q2 — 答案：A

RFC 8259 要求字符串中的控制字符（包括换行）必须转义，`json.dumps` 输出 `\n` 两个字符而非真正的换行；配合 `separators=(",", ":")` 也不会产生缩进换行。官方 `quiz.json` 的答案即"JSON does not allow literal newlines inside strings without escaping, so each object can be one line"。实测 handler 返回 `"中文\n换行"`，输出为一行 `"中文\n换行"`（`ensure_ascii` 默认开启，非 ASCII 也被转义）。B 错，管道没有消息边界，一次 `read` 可能拿到半条或多条；C 错；D 错，JSON-RPC 规范本身与传输无关，不规定分帧。

### Q3 — 答案：D

讲义："A parse error has a special rule. The `id` in the response is `null`, because the request never parsed enough to extract an id." 以及 "If a line cannot be parsed, the transport writes a -32700 response with `id: null` and continues." 测试 `test_parse_error` 与 `test_parse_error_then_continue` 钉住了这两点。A 是信封错误的码；B、C 都不是本节行为。

### Q4 — 答案：B

```python
    except Exception as exc:
        return None if req.is_notification else _err_envelope(
            req.id, ERR_INTERNAL, "internal error",
            {"exception": type(exc).__name__, "detail": str(exc)},
        )
```

只有 `MethodNotFound`、`InvalidParams`（以及 `JsonRpcError` 子类）会映射为各自的码，其他异常一律 `-32603`。讲义说 data 中带 `exception` 类名，代码还额外带了 `detail`（异常消息）。注意 `detail` 可能泄露内部信息（实测 `"secret path /etc/x"` 被原样返回），生产中应只在调试模式返回。A、C 需要 handler 抛对应的异常类；D 错，handler 异常被捕获，不影响循环。

### Q5 — 答案：D

`_process_batch` 收集到的 `out` 为空时返回 `None`，`serve` 不写任何字节。讲义："If every entry in the batch is a notification, the server sends nothing back."（`test_batch_all_notifications_silent`）。A 是常见误解——规范明确要求此时不返回空数组。

### Q6 — 答案：A

```python
        if isinstance(parsed, list):
            if not parsed:
                transport.write_error(None, ERR_INVALID_REQUEST, "empty batch")
                continue
```

JSON-RPC 2.0 规范规定空数组是无效请求，响应是**单个**错误对象而不是数组（`test_empty_batch_invalid_request`）。B 是很多实现的错误做法；C 混淆了"全是 notification"的情形；D 错，`[]` 是合法 JSON。

### Q7 — 答案：C

`_is_valid_envelope` 对 `bool` 类型的 id 返回 `False`（`test_boolean_id_rejected`），所以是 `-32600`。但 `parse_request` 构造错误时取 `rid = msg.get("id")`，把非法的 `true` 原样放进了响应（实测输出 `{"jsonrpc":"2.0","id":true,"error":{...}}`）。测试只检查了错误码，没检查 id。A 错，`true` 不是合法 id；B 错，有 `id` 键就不是 notification；D 错，JSON 本身可以解析。

### Q8 — 答案：B

实际运行输出 6 行：

| 输入 | 输出 |
|------|------|
| id 1 `math.add {a:2,b:3}` | `result: 5` |
| id 2 `math.add {a:5}` | `-32602 a and b required` |
| id 3 `missing` | `-32601 method 'missing'` |
| id 4 `boom` | `-32603`，`data.exception = RuntimeError` |
| notification `log` | 无 |
| batch [10 echo, 通知 log, 11 math.add] | 一行数组：id 10 与 id 11 两个结果 |
| `{not json` | `-32700`，`id: null` |

A 漏了 parse error；C 把 notification 也算了一行；D 把 batch 的每个元素当成独立的行。

### Q9 — 参考答案

能让 `serve` 崩溃的输入（均已实测）：

1. **非法 UTF-8 字节**：`b"\xff\xfe\n"` → `line.decode("utf-8")` 抛 `UnicodeDecodeError`，不在 `try` 内，`serve` 直接退出，后面的合法请求没有任何输出。
2. **handler 返回不可 JSON 序列化的值**：如 `{1, 2}`（set）、`datetime`、自定义对象 → `_write_raw` 中 `json.dumps` 抛 `TypeError`，同样在 `try` 之外，`serve` 退出。
3. `float("nan")`：不会崩溃，但输出 `{"jsonrpc":"2.0","id":1,"result":NaN}`——`NaN` 不是合法 JSON，严格的客户端会解析失败。反过来，`json.loads` 默认也**接受**输入中的 `NaN`。

修复（已在副本上实测，原 15 个测试仍通过）：

```python
        try:
            text = line.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            transport.write_error(None, ERR_PARSE, f"invalid utf-8: {exc.reason}")
            continue
```

```python
def _write_raw(transport: StdioTransport, obj: Any) -> None:
    try:
        encoded = json.dumps(obj, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        rid = obj.get("id") if isinstance(obj, dict) else None
        encoded = json.dumps(_err_envelope(rid, ERR_INTERNAL, "result not serializable",
                                           {"exception": type(exc).__name__}),
                             separators=(",", ":"))
    transport._out.write((encoded + "\n").encode("utf-8"))
    transport._out.flush()
```

修复后对"坏 UTF-8 行 → 返回 set 的请求 → 合法请求"三行输入，依次得到 `-32700`、`-32603 result not serializable`、正常结果。注意 batch 中某个结果不可序列化时，`obj` 是列表，会整体被替换为一个 `id: null` 的错误；更精细的做法是在 `_handle_one` 里就预先检查结果能否序列化。另外 `allow_nan=False` 让 NaN 变成 `ValueError` 被同一分支处理；输入端可以用 `json.loads(text, parse_constant=...)` 拒绝 `NaN`/`Infinity`。

### Q10 — 参考答案

1. **没有**。`_demo` 的 handler 只返回值或抛异常，没有发送任何 notification；测试 `TestNotificationHelper` 只是单独调用 `transport.write_notification("progress", {"pct": 50})`，并不是"在请求处理中途"。`Handler = Callable[[str, Any], Any]` 只接收 `(method, params)`，拿不到 transport。`_handle_one` 与 `_process_batch` 虽然接收了 `transport` 参数，却从未使用。讲义与代码在这一点上不一致。
2. 用闭包把 `notify` 注入 handler（已实测）：

```python
def serve_with_notify(handler, transport):
    def notify(method, params=None):
        transport.write_notification(method, params)
    return serve(lambda m, p: handler(m, p, notify), transport)

def handler(method, params, notify):
    if method == "slow.job":
        notify("progress", {"pct": 50})
        notify("progress", {"pct": 100})
        return {"done": True}
    raise MethodNotFound(method)
```

输出：

```text
{"jsonrpc":"2.0","method":"progress","params":{"pct":50}}
{"jsonrpc":"2.0","method":"progress","params":{"pct":100}}
{"jsonrpc":"2.0","id":1,"result":{"done":true}}
```

要点：notification 先于最终响应写出，因为 `write_notification` 立即 `flush`。进度消息里通常应带上关联的请求 id 或 progress token（如 `{"id": 1, "pct": 50}`），否则并发请求时客户端分不清是谁的进度。

### Q11 — 参考答案

实测输出：

1. `[{"jsonrpc":"2.0","id":null,"error":{"code":-32600,...}}, {"jsonrpc":"2.0","id":2,"error":{"code":-32601,"message":"method 'nope'"}}, {"jsonrpc":"2.0","id":null,"error":{"code":-32600,...}}]`——一行数组。`1` 不是对象，`{"foo": 1}` 缺 `jsonrpc`/`method`，都是 Invalid Request；中间合法请求得到 Method not found。顺序与输入一致。
2. `{"jsonrpc":"2.0","id":null,"result":{"x":1}}`——有 `id` 键（值为 null）就是 request，会得到响应。规范不推荐用 null 作 id，正因为这样的响应与 parse error 的 `id: null` 难以区分。
3. `{"jsonrpc":"2.0","id":null,"error":{"code":-32600,...}}`——发送者本意是 notification，但信封非法，服务端无法确认它是 notification，按 Invalid Request 返回错误。
4. `{"jsonrpc":"2.0","id":null,"error":{"code":-32600,...}}`——`42` 是合法 JSON 但不是对象。

### Q12 — 参考答案

1. 规范："If there was an error in detecting the id in the Request object (e.g. Parse error/Invalid Request), it MUST be Null." 当 id 本身就是非法类型（bool、对象、数组）时，回显它等于在响应里放一个违反规范的 id，客户端的"按 id 匹配挂起请求"逻辑可能出错（例如把 `true` 当成 `1`）。`1.5` 的情况略有不同：规范允许数字 id 但"SHOULD NOT contain fractional parts"，代码选择拒绝浮点 id 是更严格的做法，回显 `1.5` 至少不会造成歧义。
2. 参考实现：

```python
def _safe_id(msg: Any) -> int | str | None:
    if not isinstance(msg, dict):
        return None
    rid = msg.get("id")
    if isinstance(rid, bool):
        return None
    if isinstance(rid, (int, str)):
        return rid
    return None
```

   替换 `parse_request` 中的 `rid = msg.get("id") if isinstance(msg, dict) else None`，以及 `_process_batch` 中相同的那一行。再给 `test_boolean_id_rejected` 增加断言 `self.assertIsNone(out_true[0]["id"])`。

### Q13 — 参考回答要点

- **消息种类**：request（`jsonrpc`、`method`、可选 `params`、`id`）、notification（无 `id`）、success response（`id` + `result`）、error response（`id` + `error{code, message, data?}`）；`result` 与 `error` 互斥。batch 是这些对象的数组。
- **错误码**：
  - `-32700`：收到的不是合法 JSON（id 为 null）；
  - `-32600`：是 JSON 但不是合法请求对象（缺 `method`、`jsonrpc` 不是 `"2.0"`、id 类型非法、空 batch）；
  - `-32601`：方法不存在；
  - `-32602`：参数不合法（本节由 handler 抛 `InvalidParams` 表示）；
  - `-32603`：服务端内部错误（handler 抛其他异常）；
  - `-32000～-32099`：实现自定义的服务端错误（实测自定义 `code = -32001` 的子类能正确返回）。
- **request vs notification**：request 必须且只能得到一个响应；notification 不得响应，失败也沉默（`test_notification_handler_exception_silent`）。
- 加分点：params 只能是对象或数组（按名或按位置传参）；id 应为字符串或整数，避免 null 和小数。

### Q14 — 参考回答要点

- **换行分隔**：实现最简单，可以用 `readline` 逐条读，便于 `cat`/`jq` 调试；前提是发送方保证消息内无裸换行（JSON 序列化天然满足，但手写的漂亮打印 JSON 会破坏分帧）。缺点：读者必须扫描到换行才知道消息结束，单条超长消息需要额外的长度上限防护。
- **`Content-Length` 头**（LSP 风格）：先读头部得到字节数，再精确读取消息体；可以承载任意内容（包括含换行的漂亮 JSON），可以预先检查长度并拒绝超大消息；缺点是实现稍复杂，头部与体之间的 `\r\n\r\n` 等细节容易出错，人工调试不方便。
- **为什么不能 print 到 stdout**：stdout 就是协议通道，任何非协议输出都会混进消息流，客户端会把它当成一条坏 JSON（触发解析错误）甚至错位地匹配响应。日志必须写到 stderr 或文件；本节 `_write` 每次都 `flush`，也是为了让消息及时出现在管道里。
- 加分点：注意 Python 的 stdout 默认缓冲，真实子进程中要用 `sys.stdout.buffer` 并及时 flush；Windows 上换行符转换（`\r\n`）也要注意，本节用 `strip()` 兼容了 CRLF 输入（实测）。

### Q15 — 参考回答要点

- 讲义列出的三项：外层 trace id（在多跳转发中关联调用链）；取消通道（如 LSP 的 `$/cancelRequest`，带上进行中请求的 id）；内容类型协商（同一连接支持 JSON-RPC 与 Streamable HTTP）。
- 其他常见能力：
  - **健壮性**：非法 UTF-8、不可序列化结果、单行长度上限、NaN（Q9）；
  - **并发**：多个请求并发处理、响应乱序返回（靠 id 关联），需要写锁保证每条消息原子写出；
  - **超时与背压**：请求级超时、未完成请求数上限、慢消费者处理；
  - **生命周期**：初始化握手与能力协商、优雅关闭（收到 EOF 时等待进行中请求完成）；
  - **安全**：错误中的 `detail` 只在调试模式返回；限制 batch 大小；
  - **可观测性**：每条消息记录方法、耗时、错误码到 stderr 或 tracing 系统；
  - **双向**：服务端也能向客户端发 request（如 MCP 的 sampling），需要客户端同样实现分派。
- 加分点：这些都只增加元数据或外围逻辑，讲义强调"None of those change the wire"。

### Q16 — 参考回答要点

- **生命周期**：harness 为每个服务端启动子进程，把子进程的 stdin/stdout 作为通道、stderr 单独收集为日志；启动后先做初始化握手确认协议版本与能力；会话结束时关闭 stdin（服务端读到 EOF 后退出，本节 `serve` 正是 EOF 即返回），超时未退出再发信号终止。
- **消息关联**：每个连接维护自增 id → 挂起请求（future）的映射；收到响应按 id 唤醒；notification 按方法名分发给订阅者（进度、日志）。不同连接的 id 空间互相独立，跨连接追踪需要外层 trace id。
- **错误隔离**：单个服务端崩溃（管道 EOF、退出码非零）只让该连接上的挂起请求以错误结束，并按策略重启；一行坏消息只影响一条请求（本节"不污染流"的性质）；对每个服务端设置请求超时与最大并发。
- **可观测性**：为每次调用记录服务端名、方法、id、耗时、错误码；收集 stderr 日志并带上服务端名；把 `-32603` 的比例作为健康指标。
- 加分点：讲义开头提到"A coding agent in 2026 talks to maybe twelve tool servers in a single session"；子进程的环境变量、工作目录、权限要最小化（与第 26 节沙箱衔接）。

### Q17 — 参考回答要点

- **代价**：服务端处理 notification 失败时，客户端完全不知道；方法名拼错的 notification 会被静默丢弃（`test_notification_handler_exception_silent` 就是这种情况）。调试困难，只能依赖服务端日志。
- **为什么仍然这样规定**：notification 没有 id，任何响应都无法关联到调用点；允许响应会破坏"一个 id 一个响应"的简单计数规则（讲义："That single rule keeps the framing math simple"）。
- **需要确认时**：
  - 把它改成 request（带 id），拿到一个哪怕是 `null` 的 result 作为 ack；
  - 取消类操作：取消本身用 notification，但被取消的那个 request 仍会得到一个响应（结果或"已取消"错误），客户端通过它确认；
  - 服务端把 notification 处理错误写到 stderr / 日志，并暴露计数指标。
- 常见误区：给 notification 返回 `{"id": null, ...}` 的响应——这违反规范，而且会与 parse error 响应混淆。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../../13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md)：MCP 正是建立在 JSON-RPC 之上。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../../13-tools-and-protocols/09-mcp-transports/docs/zh.md)：stdio 与 HTTP 两种传输的对比。
- [阶段 13 · 07 构建 MCP 服务端：无状态 Python 与 TypeScript](../../../13-tools-and-protocols/07-building-an-mcp-server/docs/zh.md)：服务端如何组织方法。
- [阶段 19 · 20 Agent Harness 的循环契约](../../20-agent-harness-loop-contract/docs/zh.md)：讲义提到 pull point 在 MCP 上对应 `tools/call`。
- [阶段 19 · 21 带 Schema 校验的工具注册表](../../21-tool-registry-schema-validation/docs/zh.md)：位于 handler 背后的注册表。

### 本节被哪些后续内容用到
- [阶段 19 · 23 函数调用分派器](../../23-function-call-dispatcher/docs/zh.md)：把传输层与注册表缝在一起，加入超时与重试。
- [阶段 19 · 29 基于 Harness 的端到端 Coding Agent](../../29-end-to-end-coding-task-demo/docs/zh.md)：完整系统中的传输层。
- [阶段 13 · 08 构建 MCP 客户端：发现、路由与新旧协议兼容回退](../../../13-tools-and-protocols/08-building-an-mcp-client/docs/zh.md)：客户端侧的连接管理。
- [阶段 13 · 29 MCP 可靠性、取消与流量控制](../../../13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)：讲义"Going further"中取消与流控的展开。

### 延伸关键词
`JSON-RPC 2.0` · `NDJSON / JSON Lines` · `Content-Length framing` · `notification` · `batch` · `-32700 / -32600 / -32601 / -32602 / -32603` · `io.BytesIO` · `stderr logging` · `$/cancelRequest` · `backpressure` · `allow_nan` · `UnicodeDecodeError`
