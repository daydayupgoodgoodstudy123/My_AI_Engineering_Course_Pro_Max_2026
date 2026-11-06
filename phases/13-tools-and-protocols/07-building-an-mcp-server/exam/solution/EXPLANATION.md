# 参考答案讲解：notesrv（13/07）

计时结束后再看。参考实现在同目录的 `notesrv/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修请求校验和结果字段

**现象**：解锁后的第一个错误是 resources/read 返回 -32602 Resource not found，可那条笔记刚刚建好，id 是 note-4。

**顺着往下找**：Resource not found 是 `handle_resources_read` 在 `self.notes.get(...)` 抛 KeyError 时报的。它查的 id 来自 `note_id_from_uri`，那里写的是 `uri.lstrip("notes://")`。lstrip 的参数是一组字符，n、o、t、e、s、冒号、斜杠都会从左边去掉，直到遇到第一个不在这组里的字符，所以 `notes://note-4` 变成了 `-4`。改成 `uri.removeprefix(NOTE_SCHEME)`。这一关想练的是：报错的位置往往不是出 bug 的位置。

**再依次修四处**：

1. `complete()` 的 `cache_scope` 默认值改回 "private"，和 docstring 一致。resources/read 只传了 ttl_ms，靠的就是这个默认值；用户的笔记不能让共享缓存跨授权上下文复用。
2. `handle_prompts_get` 去掉 `ttl_ms` 和 `cache_scope`。课里说只有 discovery、list 和 read 是可缓存结果，prompts/get 的结果是 complete，但不带缓存提示。
3. `handle` 先用 `"id" not in message` 判断通知并返回 None，再读取 id、校验和分派请求。已知方法、未知方法或不合法参数都不让通知获得响应。不要用 `not message.get("id")`：0 和空字符串是真实请求。`valid_request_id` 已给定并严格排除 bool、限制安全整数范围，错误响应继续使用同一 helper 决定回显 id。
4. `MemoryNotes.create` 用一个计数器 `self._next`，不再每次扫描所有 id 求最大值。扫描是每次 O(n)，7000 次创建要 1.5 秒左右；它还会在删掉最新一条以后把那个 id 再发一次，和 docstring 不一致。

**护栏**：提速最省事的写法是 `len(notes) + 1`。删掉一条以后，它算出的 id 是一条还在的笔记的 id，新笔记会把那条覆盖掉。删除时重新算一遍最大值也不行，删掉最新的一条就会复用它的 id。测试删掉中间一条和最新一条再建两条，两种写法都过不了。另一个护栏是 tools/list 的 cacheScope 仍然是 public：把所有可缓存结果一律改成 private 能让 resources/read 过关，但工具定义本来就该公开缓存。第三个护栏读一条不存在的笔记，-32602 的响应必须带着请求自己的 id。把 `handle` 里所有错误的 id 都改成 null，也能让 True 那条断言通过，但 JSON-RPC 要求错误响应带回请求的 id，只有 id 本身不合法时才用 null。

## Part 2 笔记目录

参考实现的布局就是 docstring 里写的：`note-<n>.body` 是正文的 UTF-8 字节，`note-<n>.json` 是标题、标签和 owner，`next_id` 是计数器。

- **正文按字节读写**：`write_bytes(body.encode("utf-8"))` 和 `read_bytes().decode("utf-8")`。`read_text()` 默认按 universal newlines 读，会把 `\r\n` 和单独的 `\r` 都变成 `\n`；Python 3.12 的 `Path.read_text` 还没有 newline 参数，要文本模式就得 `open(..., newline="")`。macOS 和 Linux 上文本模式写入不改换行，所以这里挂在读的一侧。
- **什么都不加、什么都不减**：不要 strip，不要用 print 多写一个换行，不要用 `utf-8-sig` 写 BOM，空正文也要写一个空文件。
- **元数据用 JSON**：字符串原样往返，owner 的 None 存成 null 再读回 None。存成 "" 或 `str(owner)` 都会变样。
- **计数器先写**：`_take_number` 先把计数器加一写回磁盘，再写笔记。中途崩溃最多丢一个编号，不会把同一个编号发两次。打开时不能用“磁盘上最大的编号 + 1”重建计数器：删掉最新的一条再重开，就会把它的编号再发一次。
- **按编号排序**：`all()` 从 `note-*.json` 里解析出编号，按整数排序。按文件名排序会把 note-10 排在 note-2 前面。
- **KeyError**：`get` 和 `delete` 把 FileNotFoundError 转成 KeyError，参考实现还先校验 id 的格式，格式不对的 id 不会拿去拼路径。delete 先删 .json（它在不在决定笔记在不在），再删 .body，两个文件都不留。

最后的端到端检查把 NoteDir 交给 NotesServer：resources/read 读出的正文和写进去的一模一样。

## Part 3 tools/call 的两层错误和删除授权

`call_tool` 按这个顺序判断：

1. name 不是字符串，或者 arguments 存在但不是对象：这是 tools/call 自己的参数错了，抛 `RpcProblem(-32602)`。省略 arguments 按空对象处理。
2. 工具名不存在：返回 `isError: true` 的文本内容。这是本课代码的约定，模型能看到消息并换一个真实的工具。
3. `check_arguments` 按 inputSchema 查 required、类型和闭区间的 minimum/maximum，第一个问题抛 ToolError，消息里写出参数名；schema 没列出的参数忽略。
4. 执行器抛 ToolError：同样返回 isError。
5. 其他异常不在这里捕获。它们一路传到 `NotesServer.handle`，那里把 traceback 写进 `self.log`，给客户端的只有 -32603 Internal error。

这样一个带内部路径的 OSError 不会进入模型的上下文，运维仍然能在日志里看到它。除了 ToolError，再像课里的代码那样把 (KeyError, TypeError, ValueError) 也转成 isError，在这套测试里也能通过；`except Exception` 不行，它会把故障当成工具结果，把路径交给模型。

`exec_notes_delete` 先查笔记，找不到就抛 ToolError；再查权限：principal 为 None，或者和 owner 不同，都拒绝；最后才删除。三点要注意：

- principal 是传输层传进 `handle()` 的，不是 clientInfo。clientInfo 是客户端自报的，测试里 bob 自称 alice。
- 示例笔记没有 owner。只写 `note.owner != principal`，匿名调用者（None）对没有 owner 的笔记（None）就能通过。反过来只拦匿名调用者也不够，登录的 alice 同样不能删 note-2。`principal is None or note.owner != principal` 两种情况都拦住了。
- destructiveHint 只用来让 host 弹确认框，决定不了能不能删。授权写在执行器里，不依赖任何 annotation。

## Part 4 stdio 服务循环

```python
pending = bytearray()
async for chunk in reader:
    pending += chunk
    start = 0
    while (end := pending.find(b"\n", start)) != -1:
        _answer(server, bytes(pending[start:end]), stdout, stderr, principal)
        start = end + 1
    del pending[:start]
if pending:
    _answer(server, bytes(pending), stdout, stderr, principal)
```

- 在字节上按 `\n` 切行，整行到齐才解码。逐块解码会在多字节字符被切开时出错；`str.splitlines()` 还会在 U+2028 这类字符上断开，而 stdio 的分隔符只有 `\n`。
- 一块里的每一行都处理掉；空块只是没有新数据，`async for` 结束才是输入结束；最后一行没有换行，也在结束时处理。
- `_answer` 里：只有空白的行跳过；`json.loads(line.decode("utf-8"))` 失败时捕获 ValueError，因为 UnicodeDecodeError 和 JSONDecodeError 都是它的子类，回 -32700；不是对象的 JSON 回 -32600；对象交给 `server.handle(message, principal)`。
- 每个响应写成一行 `json.dumps(response, separators=(",", ":"))` 加 `\n`，马上 flush。测试的客户端每发一行，就检查上一行的响应有没有 flush；测试的 StdioServer 还记下每个请求到达时已经 flush 了几行，所以同一块里的几行也要一行一行地处理、写出、flush，不能先全部处理再统一写出。
- 解析失败和非对象都在 stderr 记一行。stdout 上除了响应什么都没有。

测试的期望值来自另一个同样状态的服务端直接调用 `handle()` 的结果，所以这一关只考循环本身：无论怎么切块，输出都必须和逐条调用 handle 一样。

## Part 5 双时代连接

`handle` 只做选择：

```python
if _is_modern(message):                      # 带任意一个现代 key
    return self.core.handle(message, principal)
if message.get("method") == "initialize":
    return self._initialize(connection, message)
if connection in self._handshakes:
    return self._legacy_request(message, principal)
return self.core.handle(message, principal)  # 没有元数据，现代核心报 -32602
```

- 顺序就是要点。现代判断放在最前面，做过握手的连接上的现代请求照样走现代核心，带现代 `_meta` 的 initialize 也是现代请求（-32601）。只带版本或者只带 capabilities 的请求同样算现代，由现代核心按缺的字段报 -32602，握手时声明的 capabilities 不会被拿来补。反过来，`_meta` 里只有 progressToken 这类键的请求不是现代请求，在握过手的连接上照样走 legacy。
- `_initialize` 先校验 protocolVersion、capabilities、clientInfo，通过了才记下这条连接的握手，结果的 protocolVersion 固定是 2025-11-25。
- `_legacy_request` 只接受 LEGACY_METHODS，用 `self.core.run` 执行同一套 handler，再用 `_legacy_shape` 去掉 resultType、ttlMs、cacheScope 和 `_meta` 里的 serverInfo。notifications/initialized 这类通知不回复。
- 握手存在 `self._handshakes[connection]` 里，`close()` 用 `pop(connection, None)` 只删这一条。没握过手的连接（所有现代连接都是）关闭时什么也不做，不报错。

另一种做法是把 legacy 请求翻译成现代请求（用握手里的 capabilities 和 clientInfo 拼出 `_meta`），交给 `core.handle`，再把结果剥成 legacy 形状。它也能通过测试，好处是校验和错误处理只写一份；注意仍然要先挡掉 server/discover。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的协议代码里顺着错误响应找到两层之外的根因，能把笔记一个字节不差地落盘，能分清 tools/call 的协议错误和工具错误并在执行器里做授权，能写出按字节分帧、逐行 flush 的 stdio 循环，也能让 legacy 握手只存在于一条连接里。它不涉及课里的 TypeScript 版本（`main.ts` 要另外跑），也不涉及真实进程之间的 stdio（测试用的是内存里的字节流）、HTTP 传输、OAuth 和真正的 MCP 客户端。资源模板、订阅和 input_required 分别在第 10、11 课。
