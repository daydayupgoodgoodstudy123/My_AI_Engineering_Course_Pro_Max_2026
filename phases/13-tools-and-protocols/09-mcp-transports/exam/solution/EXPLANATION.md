# 参考答案讲解：streamhttp（13/09）

计时结束后再看。参考实现在同目录的 `streamhttp/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修请求读取

**现象**：解锁后的第一个错误是 `read_body` 里的 `FramingError: Content-Length is required`，可请求里明明有 `content-length`。

**顺着往上找**：测试模拟的是 HTTP/2 那一跳，所有头名都是小写。`read_body` 用 `get_all("Content-Length")` 去查，`Headers.get_all` 用 `key == name` 比较，小写的 `content-length` 对不上。HTTP 的头名不分大小写，`Headers` 的 docstring 也是这么写的。报错的位置在 `read_body`，出错的位置在 `Headers`。

**依次修四处**：

1. `get_all` 两边都转小写再比：`key.lower() == name.lower()`。只在存入时转小写、查询时不转，或者反过来，都不够。
2. `_expect` 先确认 `len(values) == 1`，再读取这一个值。路由头不能 first-wins 或 last-wins，两个值相同也必须拒绝；混合大小写的头名仍是同一个字段。`code/main.py` 的 `reject_duplicate_routing_headers` 也在分发之前检查这一点。解码后原样比较已经给定：`Tools/Call` 不是 `tools/call`，`searchNotes` 的大小写和名字末尾空格都不能改写。
3. `body_name` 对 `resources/read` 取 `params.uri`，其余取 `params.name`。Base64 哨兵的解码本来就在 `_expect` 里，修好以后讲义练习 3 的场景就能通过：非 ASCII 的 URI 以 `=?base64?...?=` 发来，解码后和 `params.uri` 原样比较。
4. `read_body` 改用 `bytearray` 累加，最后返回 `bytes(body)`；list 加 `b"".join` 也可以。bytes 不可变，`+=` 每次都新建一个对象，把已读的全部内容复制一遍。12 MiB 按 4 KiB 读，一共要复制约 18 GiB，1 秒多；bytearray 的追加摊还是 O(1)，2 到 3 毫秒。

**护栏**：提速时最常见的改法是重写整个读取循环，顺手丢掉框定规则。参考实现保留原来的检查顺序：先看 Transfer-Encoding，再看 Content-Length 是否只有一个、是否纯 ASCII 数字、是否在 1 到 limit 之间，全部通过才开始读。`isascii()` 和 `isdigit()` 缺一不可：`"١٠".isdigit()` 为真，`int("+10")` 也能成功。每次最多读 `length - len(body)` 个字节，所以 body 后面的字节还留在流里；读到 `b""` 说明对方断开了，报 FramingError。

## Part 2 共享草稿库

参考实现只有一张表：`handle` 是主键，另有 subject、tenant、version、text，以及整数毫秒的 `expires_at_ms`。

- `create`：用 `secrets.token_urlsafe(32)` 生成 handle（256 位），`expires_at_ms = clock() + ttl_ms`，在 `with self._db:` 里插入并提交。
- `get`：一条 SELECT 同时按 handle、subject、tenant 和 `expires_at_ms > clock()` 过滤，查不到就抛同一个 `UnknownHandle("unknown or expired draft handle")`。从没发过、已经过期、属于别人，三种情况走的是同一条路，调用方分不出来。
- `save`：先调 `get` 做归属和过期检查，再执行 `UPDATE drafts SET text = ?, version = ? WHERE handle = ? AND version = ?`，rowcount 不是 1 就抛 VersionConflict，带上 `get` 读到的当前版本号。版本判断在 SQL 里，两个副本同时保存，只有一个能成功。过期时间不变。

容易漏的几点：

- **提交**：两个副本是两个连接，不提交，另一个连接就看不到。
- **不要把草稿存在副本内存里**：讲义说副本内存可以做缓存，但不能是正确性依赖的唯一副本。最简单的做法是每次都读库。
- **handle 跨副本唯一**：计数器和固定种子的随机数在每个副本里都从同一个值开始，第二个副本一插入就撞主键。
- **时间是整数毫秒，用注入的 clock**：`expires_at_ms - 1` 时还能读，到点就读不到；声明成 REAL 的列会把整数读回成 float。
- **先查归属，后查版本**：反过来的话，入侵者拿着 handle 和旧版本号，就能从 VersionConflict 知道这个草稿存在。

测试是单线程的，测不出“先读版本、再无条件 UPDATE”的竞态，这一点留给面试官追问。

## Part 3 HTTP 响应映射

`handle` 就是把 docstring 的九条规则按顺序写下来：

```python
headers = Headers(request.headers)
if request.path != ENDPOINT:
    return HttpResponse(404)
origins = headers.get_all("Origin")
if origins and (len(origins) > 1 or origins[0] not in self.allowed_origins):
    return HttpResponse(403)
if request.method != "POST":
    return HttpResponse(405, [("Allow", "POST")])
try:
    message = json.loads(read_body(headers, request.body))
except ValueError as exc:  # FramingError、JSONDecodeError、UnicodeDecodeError 都是 ValueError
    return json_response(400, rpc_error(None, PARSE_ERROR, "Parse error", {"detail": str(exc)}))
...
try:
    version = validate_structure(message)
    check_mirrored_headers(headers, message)
    if version not in SUPPORTED_VERSIONS:
        raise RpcFault(UNSUPPORTED_VERSION, "Unsupported protocol version",
                       {"supported": list(SUPPORTED_VERSIONS), "requested": version})
except RpcFault as fault:
    return json_response(400, rpc_error(request_id, fault.code, str(fault), fault.data))
if "id" not in message:
    return HttpResponse(202)
response = self.dispatch(message, request.principal)
status = 404 if response.get("error", {}).get("code") == METHOD_NOT_FOUND else 200
return json_response(status, response)
```

要点：

- 顺序本身就是答案的一半。Origin 在方法之前；镜像头在版本之前，所以头写 2027、body 写 2026 是 `-32020`，两边都是 2027 才是 `-32022`；通知要通过全部检查才被接受。
- 只有 `-32601` 变成 404，dispatch 返回的其他错误照常是 200。
- 两种 404 不一样：路径不对的 404 没有 JSON-RPC body，未知方法的 404 带着 `-32601`。讲义说双时代客户端靠这个 body 判断对面是不是现代服务器。
- Origin 是精确匹配，用的是构造时传入的允许列表。空字符串也算“有这个头”。
- 202 的 body 是空字节串。没有 id 的消息，不管方法是什么，都不回 JSON-RPC 响应。
- 响应头里从不出现 Mcp-Session-Id；请求带着它也照常处理。

端到端那一段说明讲义 Explicit application state 里的五步故障不会再发生：请求 A 落在副本 1，拿到 handle；请求 B 是一个新的 POST，落在副本 2，凭 handle 从共享库里取到同一条草稿；换一个调用者，同一个 handle 就不管用了。

## Part 4 请求级 SSE

```python
try:
    async for step in steps:
        if isinstance(step, ToolResult):
            result = complete({"content": step.content, "isError": step.is_error})
            yield _event({"jsonrpc": "2.0", "id": request_id, "result": result})
            return
        if isinstance(step, Heartbeat):
            yield KEEPALIVE  # b":\n\n"
        elif progress_token is not None:
            yield _event({"jsonrpc": "2.0", "method": "notifications/progress", "params": params})
finally:
    await steps.aclose()
```

- `_event` 写出 `b"data: "`、紧凑 JSON、`b"\n\n"`。`json.dumps` 会把字符串里的换行转义，所以一条消息一定只占一行。
- 不写 `id:`，也不写 `event:`。
- 拿到 ToolResult 就 return，不再向 steps 要下一个。
- finally 里的 `await steps.aclose()` 同时覆盖两种结束：正常写完最终响应，以及调用方提前 aclose。提前关闭时 GeneratorExit 在 yield 处抛出，finally 照样执行。async 生成器的 finally 里可以 await，只是不能再 yield。
- 进度的 params 用第 29 课代码里的形状：progressToken 和 progress，有 total 和 message 时才写。判断有没有 token 用 `is not None`，`0` 也是 token。

## Part 5 客户端分层解码

三层各管一件事：

- HTTP：`Headers(headers).get("Content-Type")`，取分号前的部分，strip 再转小写。`application/json` 就把字节攒到 finish 时一次解析；`text/event-stream` 走 SSE；别的报 ProtocolError。
- SSE：字节缓冲区按 `b"\n"` 切，最后一段不完整的留到下次；每个完整的行再按 UTF-8 解码，去掉行尾的 `\r`。空行结束事件，`:` 开头的是注释，其余的行按第一个冒号拆成字段和值，值去掉一个前导空格，只收集 `data`。
- JSON-RPC：有 method 没 id 的是通知，按顺序收着；有 method 又有 id 的是服务器发来的请求，报错；没有 method 的是响应，带 result 或 error 都行，id 的类型和值都要等于 request_id，否则报错；最终响应之后再来任何消息都报错。finish 时还没有最终响应，就是 StreamLost。

```python
def feed(self, chunk):
    self._buffer += chunk
    if not self._sse:
        return []
    *lines, rest = self._buffer.split(b"\n")
    self._buffer = bytearray(rest)
    ...
```

LF 是单字节 0x0A，而 UTF-8 多字节序列里的每个字节都不小于 0x80，所以在字节层按 LF 切行，永远不会切到一个字符中间。这也是测试可以在任意字节处切块的原因：一个 é 被切成两半，一个 CRLF 被切成 CR 和 LF，结果都和整块读一样。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的协议代码里顺着错误找到上一层的根因，知道一个路由头只能有一个值，保留 HTTP 头名和头值的大小写规则，也知道 Content-Length 为什么要这么严；能把跨副本的应用状态放进共享库并按调用者授权；能把讲义里 Streamable HTTP 的状态码规则按正确的先后写出来；能写出逐事件输出、关流即取消的 SSE 生成器，以及在任意字节边界上都正确的分层解码器。它不涉及真正的套接字和 HTTP 服务器（测试直接调用函数，`code/main.py` 的 `http.server` 版本要另外跑），也不涉及 stdio 传输、`subscriptions/listen` 的长连接订阅（第 10 课）、真实的认证（第 16、18 课）、背压和看门狗（第 29 课）、并发下的 compare-and-set 竞态，以及 legacy HTTP+SSE 的兼容桥。
