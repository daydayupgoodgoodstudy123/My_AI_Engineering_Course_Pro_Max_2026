# 测验 · MCP 传输：stdio 与无状态 Streamable HTTP（MCP Transports: stdio and Stateless Streamable HTTP）

> **阶段 13 · 工具与协议 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：中文讲义为机器翻译，部分术语译法不统一，有疑义以英文版为准。本节所有协议细节以讲义描述的 MCP `2026-07-28` 为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 传输只是搬运工 | 传输承载 MCP 消息，但**不**补充缺失的协议状态；stdio 与 Streamable HTTP 承载的都是自描述请求 |
| 2 | stdio 绑定 | 客户端拉起子进程；stdin/stdout 一行一条 UTF-8 JSON-RPC；诊断写 stderr；stdin EOF 时及时退出；进程意外退出时在途请求丢失，需重启、重新 discover / list、重开订阅、用新 id 重试安全操作 |
| 3 | 单端点、只用 POST | 一个端点（如 `/mcp`），每条 JSON-RPC 请求或通知都是一次新的 POST；请求的响应是 `application/json`（一条响应）或 `text/event-stream`（相关通知 + 最终响应）；通知被接受时返回 `202` 且无 body；客户端 `Accept: application/json, text/event-stream` |
| 4 | 被移除的旧机制 | `GET /mcp`、`DELETE /mcp` → `405`；`Mcp-Session-Id` 被忽略，从不签发或回显；`Last-Event-ID` 被忽略，现代流不可续传 |
| 5 | Origin 校验 | 防 DNS rebinding：存在且不在允许列表 → `403`；不存在（非浏览器客户端）允许；本地 server 绑定 `127.0.0.1`；必须**精确匹配**，`startswith` 不安全；Origin 校验**不是**认证 |
| 6 | 镜像 HTTP 头 | `MCP-Protocol-Version` = body 中的版本；`Mcp-Method` = JSON-RPC method；`Mcp-Name` 对 `tools/call`、`prompts/get` 等于 `params.name`，对 `resources/read` 等于 `params.uri`；头名大小写不敏感，头值大小写敏感 |
| 7 | Base64 哨兵与错误码 | 不安全或非 ASCII 的 `Mcp-Name` 用 `=?base64?{...}?=` 编码，server 解码后再比较；头缺失 / 畸形 / 不一致 → HTTP `400` + `-32020`（即使其中一个版本也不受支持）；头与 body 一致但版本不支持 → `400` + `-32022`；未知方法 → `404` + `-32601` |
| 8 | 请求级 SSE | 长请求可以用 SSE 返回进度通知再给最终响应；流上不能有 server 发起的请求；关闭流即取消该请求；不加 SSE event id，不支持重放 |
| 9 | `subscriptions/listen` | 长期变更通知由客户端发起的 POST 承载；首条消息为 `notifications/subscriptions/acknowledged`；确认、每条通知、最终结果的 `_meta` 都带 `io.modelcontextprotocol/subscriptionId` = listen 请求 id；断开后用新 id 重新 listen 并重新拉取；`resources/subscribe` 属于 legacy |
| 10 | 显式应用状态与双时代 | 草稿等状态用 server 签发、不可猜测、有过期、绑定主体的 handle，存在共享存储里，每次使用都授权；sticky routing 只是掩盖症状。HTTP 双时代客户端先发现代 POST，遇到 `400/404/405` 先看 body：可识别现代错误不降级，空 body 或无法识别才尝试旧的 GET 端点 |

### 核心技能（能动手做到）

- [ ] 根据部署形态在 stdio 与 Streamable HTTP 之间做选择，并说出各自的失败模式
- [ ] 用标准库实现一个 POST-only 的 MCP HTTP 端点：Origin、Content-Type、Accept、Content-Length、镜像头、版本校验各在哪一步、返回什么状态码
- [ ] 为任意 `Mcp-Name` 生成正确的头值（含 Base64 哨兵），并在 server 端解码比较
- [ ] 写出 `subscriptions/listen` 的 SSE 流，并说清 `subscriptionId` 的打标规则
- [ ] 指出本节代码在订阅过滤、无 id 请求、头部读取超时上的问题并修复
- [ ] 设计一个跨副本可用的显式草稿 handle（讲义练习 5），说明为什么 sticky routing 不是解决方案

---

## 二、基础自测（选择题）

**Q1.** 在 MCP `2026-07-28` 的 Streamable HTTP 中，客户端对 `/mcp` 发 `GET`，server 应返回：

- A. `200`，打开一个独立的 SSE 流
- B. `404 Not Found`
- C. `405 Method Not Allowed`（`Allow: POST`）
- D. `400` + `-32020`

**Q2.** 请求头 `MCP-Protocol-Version: 2027-01-01`，而 body 中 `_meta` 的版本是 `2026-07-28`。server 应返回：

- A. HTTP `400` + `-32020`（头与 body 不一致）
- B. HTTP `400` + `-32022`（版本不受支持）
- C. HTTP `200`，以 body 中的版本为准
- D. HTTP `404` + `-32601`

**Q3.** 对一个现代 `tools/list` POST，下列哪个头**不是**必需的？

- A. `MCP-Protocol-Version`
- B. `Mcp-Method`
- C. `Accept: application/json, text/event-stream`
- D. `Mcp-Name`

**Q4.** 一个请求级 SSE 流在最终响应到达前断开了。客户端应该：

- A. 带 `Last-Event-ID` 重连，从断点继续接收
- B. 视为该在途请求丢失；若重试是安全的，用新的 JSON-RPC id 发一个新请求
- C. 发 `GET /mcp` 重新打开流
- D. 等待 server 在下一个 POST 的响应中补发

**Q5.** 关于 `Origin` 校验，正确的是：

- A. 它是一种认证机制，通过后即可执行任何工具
- B. 可以用 `origin.startswith("https://trusted.example")` 判断
- C. 请求没有 `Origin` 头时必须返回 `403`
- D. `Origin` 存在且不在允许列表中时返回 `403`；需要精确匹配；没有 `Origin` 的非浏览器客户端可以放行；它不能代替认证

**Q6.** `resources/read` 的 `params.uri` 为 `notes://笔记-1`，客户端应发送的 `Mcp-Name` 头是：

- A. `=?base64?` + UTF-8 字节的 Base64 + `?=`，server 解码后与 `params.uri` 比较
- B. `notes%3A%2F%2F%E7%AC%94...`（百分号编码）
- C. 不发送，非 ASCII 的名字不需要镜像
- D. 直接发送原始 UTF-8 字节

**Q7.** 关于 `subscriptions/listen`，正确的是：

- A. 流中的第一条消息是最终结果
- B. 首条协议消息是 `notifications/subscriptions/acknowledged`；确认、每条变更通知和最终结果的 `_meta` 都带 `subscriptionId`，其值等于 listen 请求的 id
- C. 它通过 `GET /mcp` 建立
- D. 订阅资源变更应先调用 `resources/subscribe`

**Q8.** 客户端 POST 了一条 server 接受的 JSON-RPC 通知（没有 `id`），server 应返回：

- A. `200` + 一条 JSON-RPC 响应
- B. `204 No Content`
- C. `202 Accepted`，没有 body
- D. `405`

---

## 三、动手 / 代码题

**Q9.** 本节 `do_POST` 的校验顺序是：

```python
        request_id = message.get("id")
        try:
            body_version = validate_request_structure(message)
            reject_duplicate_routing_headers(self.headers)
            validate_http_headers(self.headers, message, body_version)
            validate_supported_version(body_version)
        except RpcFault as fault:
            self._write_fault(400, request_id, fault)
            return
        ...
        response = dispatch(message)
        status = 404 if response and response.get("error", {}).get("code") == -32601 else 200
```

1. 写出下列 4 个请求的 HTTP 状态码与 JSON-RPC 错误码：
   - (a) 头 `MCP-Protocol-Version: 2027-01-01`，body 版本 `2026-07-28`；
   - (b) 头与 body 版本都是 `2027-01-01`，body 缺 `clientCapabilities`；
   - (c) 头与 body 版本都是 `2027-01-01`，其余正常；
   - (d) `prompts/list`（本 server 未实现），其余正常。
2. 对比第 06、07 节的 `validate_request`，本节的顺序有什么不同？哪一个与第 06 节讲义的生命周期一致？
3. 为什么讲义坚持"头不一致返回 `-32020`，**即使**其中一个版本值本身不受支持"？请从网关的角度解释。

**Q10.** 阅读 `accepted_filter`：

```python
def accepted_filter(requested):
    accepted = {}
    for key in ("toolsListChanged", "promptsListChanged", "resourcesListChanged"):
        if requested.get(key) is True:
            accepted[key] = True
    resources = requested.get("resourceSubscriptions")
    if isinstance(resources, list) and all(isinstance(uri, str) for uri in resources):
        accepted["resourceSubscriptions"] = resources.copy()
    return accepted
```

已知本 server 的 `SERVER_CAPABILITIES = {"tools": {"listChanged": True}}`。

1. 客户端请求 `{"promptsListChanged": true, "resourceSubscriptions": ["file:///etc/passwd"]}`，确认消息中"已接受"的过滤器是什么？随后流中还会出现什么通知？
2. 这有哪些问题（至少两条）？
3. 改写 `accepted_filter`，让它与 server 能力和调用者的授权范围取交集。

**Q11.** 下列两个现象都可以用本节代码复现：

- 现象 A：发送一个没有 `id` 的 `tools/call`（`name: "ping"`），server 返回 `202`，工具没有执行，客户端也收不到任何错误。
- 现象 B：`Handler.timeout` 为 `None`，`READ_TIMEOUT_SECONDS` 只在读取 body 前通过 `self.connection.settimeout(...)` 设置。

1. 现象 A 中，server 的行为在协议上"错"了吗？客户端的问题是什么？你会如何让这类错误更早暴露？
2. 现象 B 意味着什么攻击面？如何修复？
3. 本节对 `Content-Length` 做了大量严格检查（必须存在、只能是 ASCII 数字、1～1 MiB、不允许重复、不允许 `Transfer-Encoding`）。这些检查分别防的是什么？

**Q12.**（讲义练习 5）为 `ping` 服务增加一个"草稿"工作流：`draft_start` 返回 handle，`draft_append(handle, text)` 追加内容。要求 server 部署为多个副本、请求可能落在任意副本上、不使用连接亲和（sticky routing）。

1. 写出核心实现（可用两个共享同一存储的 `Replica` 对象模拟两个副本）。
2. 说明 handle 应满足的 4 个性质，以及另一个用户拿到 handle 时会发生什么。
3. 讲义列出了三种状态机制（请求局部变量、带完整性保护的 `requestState`、显式 handle + 共享持久化），分别适用于什么生命周期？

---

## 四、面试高频题

**Q13.**（基础必考）MCP 的 stdio 与 Streamable HTTP 传输各适合什么场景？它们各自的"连接"与 MCP 协议会话是什么关系？

**Q14.**（原理深挖）`2026-07-28` 为什么要移除 `Mcp-Session-Id`、独立的 GET 流、DELETE 会话终止和 `Last-Event-ID` 续传？这些移除换来了什么，又付出了什么？

**Q15.**（工程实践）既然 body 里已经有版本、方法和名称，为什么还要在 HTTP 头里再镜像一份？server 为什么必须校验两者一致？Base64 哨兵解决了什么问题？

**Q16.**（场景设计）你负责把一个基于会话（`Mcp-Session-Id` + GET SSE）的 `2025` 版 MCP HTTP server 迁移到 `2026-07-28`，并且迁移期间老客户端不能断。给出迁移方案。

**Q17.**（追问型）有同事说："草稿丢失的问题，开启负载均衡的 sticky session 就解决了。"你怎么回应？正确的设计是什么？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："`GET /mcp` returns `405 Method Not Allowed`." 代码 `do_GET` 在通过路径与 Origin 校验后调用 `_method_not_allowed()`，发送 `405` 和 `Allow: POST`（测试 `test_get_and_delete_return_405` 同时断言了 `Allow` 头）。

- A 是旧版 Streamable HTTP 的独立 GET 流，现代协议已移除；长期变更改用 POST `subscriptions/listen`。
- B 错：端点存在，只是不支持该方法。
- D 错：`-32020` 是 POST 请求中头与 body 不一致的错误。

### Q2 — 答案：A

讲义："At an HTTP boundary, compare the version... A mismatch is `-32020` even when one of the two version values is unsupported."（第 06 节）以及本节 "Missing, malformed, or mismatched mirrored headers return HTTP `400` with JSON-RPC code `-32020`." 实测本节 server 返回 `400` + `-32020`。

- B 错：`-32022` 只在头与 body **一致**且版本不受支持时返回。
- C 错：不一致时不能"以某一方为准"，否则网关和源站可能在解释不同的东西。
- D 错：这不是方法未找到。

### Q3 — 答案：D

讲义："`Mcp-Name` is required for `tools/call`, `resources/read`, and `prompts/get`."，`tools/list` 没有"名称"，不需要。`MCP-Protocol-Version` 与 `Mcp-Method` 每个现代 POST 都必需；`Accept` 必须同时包含两种类型（本节代码缺任一类型返回 `406`，实测 `Accept: */*` 也会被拒绝）。

### Q4 — 答案：B

讲义："If a request-scoped stream breaks before its final response, the client has lost that in-flight request. It may issue a new request with a new JSON-RPC id when retry is safe. It must not attempt stream resumption."

- A 错：`Last-Event-ID` 续传不属于现代协议，server 也不会在 SSE 中写 event id（测试断言流中没有 `\nid:`）。
- C 错：GET 返回 `405`。
- D 错：没有会话，server 不会"记得"要补发。

### Q5 — 答案：D

讲义："If the header is present and not explicitly allowed, return `403 Forbidden`. A non-browser client may omit `Origin`"；"Use exact origin matching... Prefix checks such as `origin.startswith(...)` are unsafe"；"Origin validation is not authentication."

- B 错：`https://trusted.example.attacker.com` 也满足这个前缀。
- C 错：代码 `origin_allowed(None)` 返回 `True`。
- 补充：本节允许列表是 `http://localhost`、`http://127.0.0.1`、`https://client.example`，精确匹配意味着 `http://localhost:5173`（带端口）会被拒绝（实测 `403`）——配置允许列表时要写全端口。

### Q6 — 答案：A

讲义："Unsafe or non-ASCII `Mcp-Name` values use the exact UTF-8 Base64 sentinel: `=?base64?{Base64EncodedValue}?=`. The server decodes that value before comparing it with the body." 实测 `encode_header_value("notes://笔记-1")` 得到 `=?base64?bm90ZXM6Ly/nrJTorrAtMQ==?=`。

- B 错：讲义规定的是 Base64 哨兵，不是百分号编码。
- C 错：`resources/read` 必须带 `Mcp-Name`。
- D 错：HTTP 头值不能可靠地承载任意 UTF-8；本节 `decode_header_value` 会拒绝 0x20–0x7E 之外的字符（`-32020`）。

### Q7 — 答案：B

讲义："Its first protocol message is `notifications/subscriptions/acknowledged`. The acknowledgement, every change notification, and the final result carry `io.modelcontextprotocol/subscriptionId` in `_meta`, equal to the listen request id." 测试 `test_subscriptions_listen_is_post_scoped_sse` 断言最后一条 payload 的 `_meta.subscriptionId == "listen-8"`。

- C 错：listen 是 POST 请求，其响应是长期 SSE 流。
- D 错：讲义 "`resources/subscribe` and `resources/unsubscribe` belong to the legacy era."

### Q8 — 答案：C

讲义："For an accepted notification, the server returns `202 Accepted` with no body." 代码：`if "id" not in message: self.send_response(202); self.end_headers()`；探针输出 `accepted notification: HTTP 202, empty-body=True`。

### Q9 — 参考答案

1. 实测结果：

| 请求 | HTTP | JSON-RPC | 在哪一步失败 |
|------|------|----------|------------|
| (a) 头 2027 / body 2026 | 400 | `-32020` | `validate_http_headers` |
| (b) 都是 2027，缺 capabilities | 400 | `-32602` | `validate_request_structure` |
| (c) 都是 2027 | 400 | `-32022` | `validate_supported_version` |
| (d) `prompts/list` | 404 | `-32601` | `dispatch` |

2. 本节的顺序是：**结构校验（含 capabilities）→ 重复头 → 头 / body 一致性 → 版本支持性**，与第 06 节讲义的生命周期第 3、4、5 步完全一致。第 06、07 节的 `validate_request` 把"版本支持性"放在了"capabilities 是否存在"之前，所以 (b) 在那两节会得到 `-32022`。本节是三节中唯一与讲义顺序一致的实现。
3. 网关视角：网关通常只看头做路由、限流、授权（例如按 `Mcp-Method` / `Mcp-Name` 判断能否调用某个工具），源站执行的是 body。如果头和 body 不一致，"被授权的"和"被执行的"可能不是同一个东西（第 06 节讲义："A gateway must not authorize `Mcp-Name: notes.read` while the origin executes `params.name: notes.delete`"）。所以"不一致"本身就是最先要报告的错误，跟其中某个值是否受支持无关；若先报 `-32022`，客户端会去换版本重试，而真正的问题（头构造错误或被篡改）被掩盖了。

### Q10 — 参考答案

1. 实测：确认消息中的过滤器为 `{"promptsListChanged": true, "resourceSubscriptions": ["file:///etc/passwd"]}`，随后流中还出现了一条 `notifications/resources/updated`，`uri` 为 `file:///etc/passwd`，最后是最终结果。
2. 问题：
   - **接受了 server 并不支持的类别**：server 只声明了 `tools.listChanged`，却"确认"了 prompts 列表变更订阅，客户端会以为自己能收到永远不会来的通知；
   - **对资源订阅不做任何授权或存在性检查**：任何 URI（包括本 server 根本不提供的 `file://` 资源）都被接受，在真实系统中这可能让调用者探知、订阅他无权访问的资源的变更；
   - **伪造通知**：演示代码立即为第一个 URI 推送一条 "updated"，在真实实现中通知必须来自真实的变更事件；
   - server 能力中没有 `resources.subscribe`，资源订阅本不应被接受。
3. 改写（已实际运行：同样的请求得到 `{'toolsListChanged': True}`）：

```python
def accepted_filter(requested, capabilities, authorized_uris):
    accepted = {}
    for key, cap in (("toolsListChanged", "tools"),
                     ("promptsListChanged", "prompts"),
                     ("resourcesListChanged", "resources")):
        if requested.get(key) is True and capabilities.get(cap, {}).get("listChanged"):
            accepted[key] = True
    uris = requested.get("resourceSubscriptions")
    if (isinstance(uris, list) and all(isinstance(u, str) for u in uris)
            and capabilities.get("resources", {}).get("subscribe")):
        allowed = sorted(set(uris) & authorized_uris)     # 排序，保证确定输出
        if allowed:
            accepted["resourceSubscriptions"] = allowed
    return accepted
```

   `authorized_uris` 应由当前请求认证得到的主体计算（每个 listen 请求重新计算，不能缓存在连接上）。确认消息返回"实际接受的过滤器"，客户端据此知道哪些订阅被拒绝了。

### Q11 — 参考答案

1. **现象 A**：从 JSON-RPC 角度，没有 `id` 的消息就是通知，server 接受后返回 `202`、不回复，这是规定行为；server 也没有义务执行一个"以通知形式发来的 `tools/call`"。真正的错误在客户端：它把一个**请求**方法当作通知发送，永远拿不到结果，而且这个错误是静默的。让错误更早暴露的办法：
   - 客户端侧：请求构造函数强制带 id；对 `tools/*`、`resources/*` 等请求方法不允许省略 id；
   - server 侧（可选的防御性设计）：只接受 `notifications/` 前缀的已知通知方法；对已知的**请求**方法缺 `id` 的消息返回 `400` + `-32600` 并记录日志。本节代码对任何通过校验的无 id 消息都返回 `202`（实测 `tools/call` 也是），这对调试不友好。
2. **现象 B**：`BaseHTTPRequestHandler.timeout = None` 意味着在读取请求行和请求头阶段没有超时。攻击者可以打开大量连接、极慢地发送请求头（slowloris），在 `ThreadingHTTPServer` 下每个连接占用一个线程，最终耗尽资源。`READ_TIMEOUT_SECONDS` 只保护了 body 读取阶段。修复：设置类属性 `Handler.timeout = READ_TIMEOUT_SECONDS`（`StreamRequestHandler` 会在 `setup()` 中对套接字调用 `settimeout`），同时限制并发连接数；生产环境放在有超时与连接限制的反向代理之后。
3. Content-Length 检查：
   - **必须存在**：没有长度就不知道读多少，可能一直阻塞；
   - **只能是 ASCII 十进制数字**：Python 的 `str.isdigit()` 对 `"²"`（上标二）返回 `True`，`int("+1")` 也能成功，所以先 `isascii()` 再 `isdigit()`，防止不同组件对长度的解释不一致（测试 `test_content_length_accepts_only_ascii_decimal_digits`）；
   - **1～1 MiB 上限**：防止超大 body 耗尽内存；
   - **不允许重复 Content-Length、不允许 Transfer-Encoding**：多个长度声明或长度与分块编码并存时，前置代理和后端可能按不同规则切分请求边界，这正是 **HTTP 请求走私（request smuggling）** 的典型条件。本节宁可拒绝也不去猜。
   - 另外 `len(body) != length` 检查防止客户端提前断开导致读到半截 body 仍被当作完整消息解析。

### Q12 — 参考答案

1. 核心实现（已实际运行：replica-1 创建、replica-2 追加第 1 段、replica-1 追加第 2 段都成功；mallory 用同一 handle 得到 `isError`）：

```python
import secrets, time

SHARED = {}                                  # 代表共享数据库 / Redis

class Replica:
    def __init__(self, name, store):
        self.name, self.store = name, store

    def draft_start(self, principal):
        handle = "drf_" + secrets.token_urlsafe(16)          # 不可猜测
        self.store[handle] = {"owner": principal, "parts": [],
                              "expires": time.time() + 900}  # 15 分钟过期
        return {"content": [{"type": "text", "text": handle}], "isError": False}

    def draft_append(self, principal, handle, text):
        rec = self.store.get(handle)
        if rec is None or rec["expires"] < time.time() or rec["owner"] != principal:
            return {"content": [{"type": "text", "text": "unknown or expired draft handle"}],
                    "isError": True}
        rec["parts"].append(text)
        return {"content": [{"type": "text", "text": f"{self.name}: {len(rec['parts'])} parts"}],
                "isError": False}
```

2. handle 的性质（讲义："Bind handles to the authenticated principal, make them unguessable, expire them, and authorize every use."）：
   - **不可猜测**：`secrets.token_urlsafe` 而不是自增 ID 或时间戳；
   - **绑定主体（和租户）**：记录 owner，每次使用比对当前请求认证得到的主体；
   - **有过期时间**：避免无限期有效的"能力令牌"；
   - **每次使用都授权**：handle 只是"指针"，不是凭证。
   - 另一个用户拿到 handle：授权检查失败，返回与"不存在"相同的错误信息，避免泄露"这个 handle 存在但属于别人"。生产中还要加并发控制（版本号）和幂等键。
3. 三种机制（讲义 "Choose the state mechanism by lifetime"）：
   - **请求局部变量**：只服务于一次调用；
   - **带完整性保护的 `requestState`**：短暂的 MRTR 续接（server 返回 `input_required`、客户端补充输入后重试），状态随请求往返，server 不必存储，但必须防篡改（第 11 节）；
   - **显式 handle + 共享持久化**：草稿、持久任务等跨多次调用、可能跨副本的状态，还需要过期、并发控制、幂等。
   - 三者都**不是** MCP 协议会话。

### Q13 — 参考回答要点

- **stdio**：客户端在本机拉起子进程，一行一条 JSON-RPC，诊断写 stderr，EOF 退出。适合本地工具（读本地文件、调用本地 CLI），不需要网络端口，凭证天然是"启动进程的那个本地用户"。
- **Streamable HTTP**：单个 POST 端点，适合远程 / 共享 / 多租户服务，可以水平扩展，需要 Origin 校验、认证与授权。
- **与协议会话的关系**：stdio 进程可以活很久、服务很多次调用，HTTP 也可能复用 TCP 连接，但这些都只是**传输寿命**；现代协议中每个请求自带版本与能力，没有协议会话。讲义："The process may live for many calls, but it is not a modern protocol session."
- **失败模式**：stdio 进程意外退出 → 在途请求丢失 → 重启、rediscover、relist、重开订阅、用新 id 重试安全操作；HTTP 请求级流断开 → 该请求丢失 → 安全时用新 id 重发，不续传。
- 加分点：本地 HTTP server 要绑定 `127.0.0.1` 并校验 Origin，否则浏览器中的恶意网页可能通过 DNS rebinding 访问它。

### Q14 — 参考回答要点

- **为什么移除**：
  - `Mcp-Session-Id` 让请求依赖于某个副本的内存状态，要求 sticky routing，扩缩容、滚动发布、故障转移时会话丢失；
  - 独立 GET 流和 `Last-Event-ID` 续传要求 server 为每个会话缓存事件、维护长连接，跨副本续传需要共享事件存储；
  - DELETE 会话终止是会话模型的附属物；
  - 会话把"协议状态"藏在传输层，安全上更难推理（能力、版本在会话建立时协商，之后的请求"继承"它们）。
- **换来了什么**：讲义 "Every request can land on any healthy worker because its protocol version and client capabilities travel in the request body." 任意副本可处理任意请求；故障语义简单（流断即请求丢失）；网关可以对每个请求独立做策略判断。
- **付出了什么**：
  - 每个请求多带一些元数据和镜像头；
  - 长期通知改为客户端维护 `subscriptions/listen`，断开后要重新 listen 并重新拉取数据（可能有重复拉取的开销）；
  - 流不可续传，长请求中断后只能重做，所以非幂等操作需要应用层幂等控制；
  - 真正需要的工作流状态必须显式化（handle + 共享存储）。
- 加分点：讲义提醒"a server teaching the 2025 transport as current is teaching the wrong failure and security model"。

### Q15 — 参考回答要点

- **为什么镜像**：网关、负载均衡、WAF 通常不解析（或不应解析）JSON body 就做路由、限流、按方法 / 工具名授权和观测；把版本、方法、名称放进头里，基础设施可以低成本地读取。
- **为什么必须校验一致**：头是给基础设施看的，body 是给源站执行的；不一致时两者在处理"不同的请求"，攻击者可以构造"头写 `notes.read`、body 写 `notes.delete`"绕过网关授权。所以源站必须在执行前比较，不一致返回 `400` + `-32020`。
- **Base64 哨兵**：HTTP 头值只能安全承载可见 ASCII，工具名或资源 URI 可能包含非 ASCII 字符、首尾空格、控制字符；`=?base64?...?=` 让任意 UTF-8 值都能无损镜像。本节 `encode_header_value` 还会把"恰好长得像哨兵"的原始值也编码，避免歧义。
- **大小写**：头名大小写不敏感（实测全小写头名也能通过），头值大小写敏感（实测 `Mcp-Method: TOOLS/LIST` 被拒绝）。
- 加分点：重复的路由头也要拒绝（本节 `reject_duplicate_routing_headers`），否则网关取第一个、源站取最后一个，又会出现解释分歧。

### Q16 — 参考回答要点

（对应 `outputs/skill-mcp-transport-migrator.md`）
- **端点规划**：新增现代 POST-only 端点；旧的会话端点（GET SSE、DELETE、带 `Mcp-Session-Id` 的 POST）保留在**独立、明确标注的** legacy 路由上。
- **请求分流**：带现代 `_meta` 与镜像头的 POST → 现代实现；legacy 流量只走 legacy 路由。现代端点对 GET / DELETE 返回 `405`，忽略 `Mcp-Session-Id` 与 `Last-Event-ID`，从不签发或回显。
- **订阅迁移**：独立 GET 流、`resources/subscribe` / `unsubscribe` → `subscriptions/listen`，按 `subscriptionId` 打标。
- **状态迁移**：把依赖会话 / 连接亲和的状态改成显式 handle + 共享存储，绑定认证主体。
- **客户端侧**：先发现代 POST，遇到 `400/404/405` 先检查 body，可识别的现代错误绝不降级，只有空 body 或无法识别才尝试旧 GET 端点。
- **不要用重定向**：skill 明确"Do not redirect POST with `301` or `302` because method and body preservation are unsafe."（部分客户端会把重定向后的 POST 改成 GET 并丢掉 body。）
- **验证与回滚**：一致性清单（Origin、媒体协商、`_meta`、镜像头、`202`、SSE 打标、`405`、忽略旧头、断流用新 id 重试）；分阶段放量，监控 legacy 路由流量；定好回滚边界和 legacy 路由的下线日期。

### Q17 — 参考回答要点

- **sticky session 为什么不够**：讲义 "Sticky routing appears to fix the symptom until a restart, rollout, reschedule, or failover moves the next request." 副本重启、滚动发布、扩缩容、节点故障都会让下一个请求落到另一个副本，内存中的草稿要么找不到，要么读到错误的本地对象；而且粘性让负载不均，也把一个协议上不存在的"会话"偷偷带了回来。
- **故障机制**（讲义的 5 步）：请求 A 在副本 1 内存中创建草稿 → 响应中没有 handle（实现假设连接即身份）→ 请求 B 是新的 POST，落到副本 2 → 副本 2 协议元数据合法但无法定位草稿 → 工作流失败或读错对象。
- **正确设计**：协议上下文留在每个请求里；草稿存共享存储，server 签发不透明 handle 作为工具结果返回；客户端在后续调用中把 handle 作为显式参数传回；任意副本加载同一条记录，并按认证主体和租户授权。副本内存可以做缓存，但不能是正确性所依赖的唯一副本。
- 加分点：还要处理过期、并发写（乐观锁）和幂等（重试同一次追加不应重复）。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：请求生命周期，其中第 4 步就是本节的头 / body 一致性检查。
- [阶段 13 · 07 构建 MCP 服务端：无状态 Python 与 TypeScript](../../07-building-an-mcp-server/docs/zh.md)：stdio server 的实现与三条 stdio 规则。
- [阶段 13 · 08 构建 MCP 客户端：发现、路由与新旧协议兼容回退](../../08-building-an-mcp-client/docs/zh.md)：客户端的 era 协商；本节补充了 HTTP 下"先看 body 再决定是否降级"的规则。
- [阶段 13 · 03 并行 Tool Calls 与工具调用中的 Streaming](../../03-parallel-and-streaming-tool-calls/docs/zh.md)：SSE 流式传输的基础。

### 本节被哪些后续内容用到
- [阶段 13 · 10 MCP Resources 与 Prompts：无状态服务端的可寻址上下文](../../10-mcp-resources-and-prompts/docs/zh.md)：资源订阅通过 `subscriptions/listen` 实现。
- [阶段 13 · 11 MCP 模型输入：Sampling 迁移与无状态 MRTR](../../11-mcp-sampling/docs/zh.md)：`requestState` 与 `input_required`（Q12 第 3 问）。
- [阶段 13 · 13 MCP Tasks 扩展：在无状态核心上运行持久任务](../../13-mcp-async-tasks/docs/zh.md)：显式 handle + 共享存储的标准化形态。
- [阶段 13 · 16 MCP 授权：CIMD、签发者绑定、PKCE 与升级认证](../../16-mcp-security-oauth-2-1/docs/zh.md)：Origin 校验之外真正的认证与授权。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：网关如何利用镜像头做路由与策略。
- [阶段 13 · 29 MCP 可靠性、取消与流量控制](../../29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)：断流、取消、重试与背压。
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../../17-infrastructure-and-production/19-ai-gateways/docs/zh.md)：生产中放在 MCP 端点之前的网关层，负责超时、连接限制与按头路由（Q11、Q15）。

### 延伸关键词
`stdio` · `Streamable HTTP` · `POST-only` · `405 Method Not Allowed` · `Mcp-Session-Id（已移除）` · `Last-Event-ID（已移除）` · `Origin / DNS rebinding` · `MCP-Protocol-Version` · `Mcp-Method` · `Mcp-Name` · `Base64 sentinel` · `-32020 HeaderMismatch` · `request-scoped SSE` · `subscriptions/listen` · `subscriptionId` · `request smuggling` · `slowloris` · `opaque state handle` · `sticky session`
