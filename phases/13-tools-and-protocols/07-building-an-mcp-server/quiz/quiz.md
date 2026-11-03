# 测验 · 构建 MCP 服务端：无状态 Python 与 TypeScript（Building an MCP Server: Stateless Python and TypeScript）

> **阶段 13 · 工具与协议 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（TypeScript 移植版：[code/main.ts](../code/main.ts)） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：中文讲义为机器翻译（如"现代发送环""无国籍合同""电线合同"分别对应 dispatch loop、stateless contract、wire contract），有疑义以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 现代 dispatch loop | 读一行 JSON-RPC → 解析信封 → 通知不回复 → 校验本请求的 `params._meta` → 按 method 路由 → 用 `resultType` + `serverInfo` 包装成功结果 → 写一行响应 → 忘掉请求级元数据 |
| 2 | stdio 三条规则 | stdout 只写 JSON-RPC 消息，诊断写 stderr；每条消息以换行分隔并 flush；stdin 到 EOF 时及时退出。进程寿命是**传输**寿命，不是 MCP 会话 |
| 3 | 每请求校验 | 缺元数据 → `-32602`；版本不支持 → `-32022`（带 requested/supported）；`clientInfo` 存在时校验形状，但不当作认证；**绝不**用上一次调用的值补齐 |
| 4 | 强制的 `server/discover` | 返回 supportedVersions、capabilities（tools/resources/prompts）、instructions、缓存提示和 server 身份；它不"解锁" server，客户端可以直接调 `tools/list` |
| 5 | Tools | `tools/list` 确定顺序 + 缓存提示；`tools/call` 返回 content + `isError`。协议信封或方法参数非法 → JSON-RPC error；合法调用但工具失败 → `isError: true` |
| 6 | Tool annotations | `readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` 只是给 host 做确认与展示的提示，**不是**授权；server 必须自己做真正的授权 |
| 7 | Resources | `resources/list` 给稳定的 URI 描述，`resources/read` 返回带类型的内容；二者都可缓存，用户相关数据用 `cacheScope: "private"`；变更推送走 `subscriptions/listen` 而不是 `resources/subscribe` |
| 8 | Prompts | `prompts/list` 可缓存且有序；`prompts/get` 按参数渲染模板，结果是 complete 但**不需要**缓存提示 |
| 9 | 集中的结果包装器 | 一个 `complete()` 负责 `resultType` 与 `serverInfo`，list/read/discover 额外加 `ttlMs` + `cacheScope`，防止某个 handler 漏字段 |
| 10 | 不主动发请求 + 显式 legacy | server 只能发与请求相关的通知；需要 sampling/elicitation/roots 时返回 `input_required`，客户端满足后用新 id 重试；legacy `2025-11-25` 握手只能放在隔离的适配器中 |

### 核心技能（能动手做到）

- [ ] 用标准库写一个 stdio MCP server：逐行读 stdin、`-32700`/`-32600`/`-32601`/`-32602`/`-32022`/`-32603` 各在何处产生
- [ ] 为 tools / resources / prompts 写出 list 与 call/read/get handler，并为每个 list 定义稳定排序键
- [ ] 判断一个结果该不该带 `ttlMs` / `cacheScope`，以及该用 `public` 还是 `private`
- [ ] 区分"协议错误"与"工具执行错误"，并指出本节代码与讲义在"未知工具"上的分歧
- [ ] 给 server 增加一个破坏性工具（`notes_delete`），在 executor 内做授权，`destructiveHint` 只做 UX 提示
- [ ] 用同一组输入对比 Python 与 TypeScript 两个实现，找出 wire contract 不一致的地方

---

## 二、基础自测（选择题）

**Q1.** 按讲义，下列哪个成功结果**不需要**带 `ttlMs` 和 `cacheScope`？

- A. `tools/list`
- B. `resources/read`
- C. `server/discover`
- D. `prompts/get`

**Q2.** 本节代码中 `tools/list`、`prompts/list` 用 `cacheScope: "public"`，而 `resources/list`、`resources/read` 用 `"private"`。最主要的原因是：

- A. 笔记内容可能是用户相关的数据，共享缓存不能在不同授权上下文之间复用
- B. `private` 缓存的读取速度更快
- C. 资源每次请求都会变化，所以不能缓存
- D. 规范禁止资源类结果使用 `public`

**Q3.** 关于 stdio 传输，下列说法正确的是：

- A. 调试信息可以写到 stdout，只要每行以 `#` 开头
- B. 多个响应可以写在同一行，用逗号分隔
- C. stdout 只写 JSON-RPC 消息、每条以换行结尾并 flush；诊断信息写 stderr；stdin 到 EOF 时及时退出
- D. stdin 到 EOF 后 server 应继续运行，等待客户端重连并恢复会话

**Q4.** 向本节 Python server 发送 `tools/call`，`name` 为 `notes_search`，`arguments` 为 `{"query": ""}`。返回的是：

- A. JSON-RPC 错误 `-32602`
- B. 成功结果，`isError: true`，文本为 `query must be a non-empty string`
- C. JSON-RPC 错误 `-32603 Internal error`
- D. 成功结果，`isError: false`，命中列表为空

**Q5.** 一个请求的 `id` 是布尔值 `true`。本节 `dispatch` 的处理是：

- A. 当作 `1` 处理，正常返回结果
- B. 返回 `-32600`，响应的 `id` 为 `null`
- C. 返回 `-32602`，响应的 `id` 为 `true`
- D. 当作通知，不返回任何响应

**Q6.** 关于 tool annotations（如 `destructiveHint`、`readOnlyHint`），正确的是：

- A. server 根据它们决定是否放行调用
- B. host 必须拒绝所有 `destructiveHint: true` 的调用
- C. 它们决定 `tools/list` 的缓存时间
- D. 它们是给 host 做确认与展示的提示，server 仍需自己执行真正的授权

**Q7.** 某个 handler 在执行中需要向用户确认一项信息（elicitation）。现代 MCP server 应该：

- A. 返回 `input_required` 结果，客户端满足其中的输入请求后，用新的 request id 重试原方法
- B. 立即向客户端发送一个 `elicitation/create` JSON-RPC 请求并等待响应
- C. 打开一个协议会话，把中间状态保存在会话里
- D. 阻塞读取 stdin，直到用户输入

**Q8.** 用本节 `make_request(13, "initialize")`（带完整的现代 `_meta`）调用 `dispatch`，结果是：

- A. 返回 legacy 握手结果（含 `protocolVersion` 与 `serverInfo`）
- B. `-32022`
- C. `-32601 Method not found`
- D. `-32602`

---

## 三、动手 / 代码题

**Q9.** 讲义："Use a JSON-RPC error when the protocol envelope or method parameters are invalid. Use `isError: true` when a valid tool invocation runs but the tool itself fails." 本节代码与测试却是：

```python
    executor = TOOL_EXECUTORS.get(name)
    if executor is None:
        return complete(
            {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
        )
    try:
        return complete({"content": executor(arguments), "isError": False})
    except (KeyError, TypeError, ValueError) as exc:
        return complete(
            {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        )
```

```python
    def test_unknown_tool_is_tool_level_error(self) -> None:
        ...
        self.assertTrue(result["isError"])
```

1. "未知工具"按讲义应归入哪一类？代码和测试的选择有什么理由、又有什么代价？
2. 如果某个 executor 抛出 `RuntimeError("db password=hunter2 at 10.0.0.5")`，客户端会收到什么？这有什么问题？
3. 写出你会如何修改（含测试）。

**Q10.** 用同一组 stdio 输入分别驱动 `main.py` 和 `main.ts`（`node --experimental-strip-types main.ts`）。对下列 5 个请求，写出两边的结果是否一致；不一致的，说明谁更符合讲义。

| # | 请求 |
|---|------|
| a | `tools/call`，`{"name": "notes_list"}`（不带 `arguments`） |
| b | `tools/call`，`{"name": "notes_search", "arguments": []}` |
| c | `tools/call`，`{"name": "notes_search", "arguments": {"query": "o", "limit": true}}` |
| d | `tools/list`，`id` 为 `9007199254740992`（2⁵³） |
| e | `tools/call`，`{"name": "notes_search", "arguments": {"query": "MCP"}}`，比较 `content[0].text` |

讲义称两个版本"enforce the same wire contract"。你会怎样在工程上保证这一点？

**Q11.** 本节在 `handle_discover` 中用了 `deepcopy(SERVER_CAPABILITIES)`，但 `handle_tools_list` 是：

```python
def handle_tools_list(params):
    return complete(
        {"tools": sorted(TOOLS, key=lambda tool: tool["name"])},
        ttl_ms=60_000,
        cache_scope="public",
    )
```

1. 执行 `r = dispatch(make_request(1, "tools/list"))["result"]; r["tools"][0]["description"] = "HACKED"` 后，`TOOLS[1]["description"]` 是什么？为什么是下标 1？
2. 这个问题与 stdio 下"同一进程服务多个先后到来的客户端"结合起来，会造成什么后果？
3. `exec_notes_create` 中 `"tag": str(arguments.get("tag", ""))` 在 `tag` 为 `None` 时会存入什么？与 TS 版有何不同？给出修正。

**Q12.** （讲义练习 3）为 server 增加一个破坏性工具 `notes_delete(note_id)`：

1. 写出它在 `TOOLS` 中的描述符（含 `annotations`）。
2. 写出 executor，要求授权检查在 executor 内部完成。授权主体从哪里来？为什么**不能**从 `params._meta` 的 `clientInfo` 来？
3. 加入删除工具后，`tools/list` 还能保持 `cacheScope: "public"` 吗？`resources/list` 的 10 秒 TTL 会带来什么现象？

---

## 四、面试高频题

**Q13.**（基础必考）描述一个 stdio MCP server 处理一行输入的完整流程。哪些情况不回复？哪些情况回复 `id: null` 的错误？

**Q14.**（原理深挖）为什么 MCP 要区分"协议错误"和"工具执行错误（`isError`）"？从 host、模型和运维三个角度分别说明。

**Q15.**（工程实践）你要把一个 `2025-11-25` 的老 server 升级成同时支持新旧两代协议的 server。怎么组织代码？怎么写测试证明"现代请求永远不会进入 legacy 分支"？

**Q16.**（场景设计）把本节 notes server 改造成多租户的远程服务（每个用户只能看到自己的笔记）。tools、resources、prompts 三类结果的缓存提示和排序要怎么调整？应用状态和协议状态的边界在哪里？

**Q17.**（追问型）本节为什么要用一个集中的 `complete()` 包装所有成功结果？如果有人新写了一个 handler 直接 `return {"tools": [...]}`，会出什么问题，怎么在 CI 中防住？再说说代码中 3600000 / 60000 / 10000 / 5000 这几个 TTL 的取值逻辑。

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："The rendered prompt result is complete, but it is not one of the cacheable list or read results that requires cache hints." 代码中 `handle_prompts_get` 调用 `complete({...})` 时没有传 `ttl_ms`，实际输出中也没有 `ttlMs`。

- A、C：讲义列出 discovery、list 都必须带缓存提示；实际输出 `tools/list` 为 `ttlMs: 60000, public`，discover 为 `3600000, public`。
- B：`resources/read` 也是可缓存结果，代码给的是 `5000, private`。

### Q2 — 答案：A

讲义："Use `cacheScope: "private"` for user-specific note data. A shared cache must not reuse a private response across authorization contexts." 工具和 prompt 模板的定义对所有人相同，可以 public；笔记内容属于数据，可能因人而异。

- B 错：作用域决定的是"谁能复用"，与速度无关。
- C 错：`private` 仍然是可缓存的（有 10 秒 / 5 秒 TTL），只是不能跨授权上下文共享。
- D 错：讲义没有这种规定；对所有人都相同的公共资源也可以 public。

### Q3 — 答案：C

讲义三条 stdio 规则："Write only JSON-RPC messages to stdout. Send diagnostics to stderr." "Delimit messages with a newline and flush each response." "Exit promptly when stdin reaches EOF." 代码 `serve_stdio` 每次 `sys.stdout.write(... + "\n")` 后 `flush()`，`for raw_line in sys.stdin` 在 EOF 时自然结束。

- A 错：任何非 JSON-RPC 的字节写进 stdout 都会破坏客户端的解析。
- B 错：一行一条消息。
- D 错：进程寿命是传输寿命，没有可"恢复"的会话。

### Q4 — 答案：B

实测：`{"resultType": "complete", "content": [{"type": "text", "text": "query must be a non-empty string"}], "isError": true, ...}`。`exec_notes_search` 对空字符串抛 `ValueError`，`handle_tools_call` 捕获 `(KeyError, TypeError, ValueError)` 后转为 `isError` 结果——模型能读到原因并重试。

- A 错：`-32602` 用于 `name` 不是字符串或 `arguments` 不是对象（例如 `arguments: []`）。
- C 错：只有不在上述三类中的异常才会落到 `dispatch` 的 `-32603`。
- D 错：空查询被显式拒绝了。

### Q5 — 答案：B

```python
    if "id" in message and type(message["id"]) not in (int, str):
        raise RpcProblem(-32600, "id must be a string or integer")
```

`type(True)` 是 `bool`，不在 `(int, str)` 中（这里特意用 `type(...)` 而不是 `isinstance`，因为 `isinstance(True, int)` 为 `True`）。`dispatch` 中 `error_id = request_id if type(request_id) in (int, str) else None`，所以响应 `id` 为 `null`。测试 `test_invalid_request_ids_are_rejected_at_the_boundary` 对 `None, True, 1.5, {"nested": "id"}` 逐一验证了这一点。

- A 错：Python 中 `True == 1`，但代码刻意拒绝了。
- C 错：错误码是 `-32600`（信封问题），且非法 id 不能原样回显。
- D 错：只有**没有** `id` 键才是通知；`id: true` 是带非法 id 的请求。

### Q6 — 答案：D

讲义："Tool annotations remain hints, not enforcement ... The host should use them for confirmation and presentation. The server must still enforce real authorization." skill 中的硬性拒绝项也包括 "Treating annotations as authorization controls."

- A 错：annotation 是 server 自己声明的，不可能约束 server 自己，更不能代替授权。
- B 错：host 可以据此弹出确认，而不是一律拒绝。
- C 错：缓存提示由结果的 `ttlMs` / `cacheScope` 决定。

### Q7 — 答案：A

讲义："When a handler needs sampling, elicitation, or roots input, it returns an `input_required` result. The client fulfills the embedded input requests and retries the original method with a new request id." 这就是 Multi Round-Trip Request（MRTR），第 11、12 节展开。

- B 错："It must not send its own JSON-RPC request."
- C 错：现代协议没有会话。
- D 错：stdin 是客户端发消息的通道，不是用户输入通道。

### Q8 — 答案：C

实测：`{"code": -32601, "message": "Method not found: initialize"}`，即测试 `test_initialize_is_not_a_modern_handler`。本节 server 是"deliberately modern-only"，`HANDLERS` 里没有 `initialize`。

- A 错：本节没有 legacy 适配器。
- B 错：`make_request` 带的是 `2026-07-28`，版本受支持。
- D：如果是一个真正的 legacy 客户端发来的 `initialize`（`params` 里没有 `_meta`），会在校验阶段得到 `-32602 params._meta is required`——这也是第 08 节客户端判断"对方是老 server"的线索之一。题目中的请求带了完整 `_meta`，所以走到了路由阶段。

### Q9 — 参考答案

1. **归类**：未知工具意味着"这不是一次合法的工具调用"，按讲义原文更接近"method parameters are invalid"，应返回 JSON-RPC 错误（如 `-32602`）。
   - 代码这样做的**理由**：`isError` 内容会进入模型上下文，模型看到 `Unknown tool: missing` 可能自行改用正确的名字；而 JSON-RPC 错误通常被 host 拦截。
   - **代价**：与讲义规则冲突；host 无法从协议层区分"工具名拼错 / 模型幻觉出不存在的工具"与"工具执行失败"，监控指标会混在一起；测试 `test_unknown_tool_is_tool_level_error` 把这个分歧固化了。
2. **实测**：`{"code": -32603, "message": "Internal error", "data": {"detail": "db password=hunter2 at 10.0.0.5"}}`。`dispatch` 的兜底把 `str(exc)` 原样放进 `data.detail` 返回给客户端，可能泄露内部地址、凭证片段、SQL 等敏感信息。正确做法是只返回通用信息加一个关联 ID，把完整异常写到 **stderr** / 日志。
3. 修改要点：

```python
    executor = TOOL_EXECUTORS.get(name)
    if executor is None:
        raise RpcProblem(-32602, f"Unknown tool: {name}")      # 协议错误

# dispatch 兜底
    except Exception as exc:
        incident = uuid.uuid4().hex[:8]
        print(f"[{incident}] {exc!r}", file=sys.stderr)        # 诊断写 stderr
        return rpc_error(error_id, -32603, "Internal error", {"incident": incident})
```

   测试相应改为 `assertEqual(response["error"]["code"], -32602)`，并新增"executor 抛 RuntimeError 时响应中不包含异常文本"的测试。参数层面的业务错误（如空 query、limit 越界）仍保留为 `isError`，因为工具确实被合法调用了、只是输入不满足业务约束，模型可据此修正。

### Q10 — 参考答案

实测结果（同一份输入文件分别喂给两个进程）：

| # | Python `main.py` | TypeScript `main.ts` | 是否一致 |
|---|------------------|----------------------|---------|
| a | 正常返回 3 条笔记（`arguments` 默认 `{}`） | `-32602 tools/call requires string name and object arguments` | 不一致 |
| b | `-32602`（`[]` 不是 dict） | `isError: true`，`Error: query must be a non-empty string`（`typeof [] === "object"`，数组被当成对象放行） | 不一致 |
| c | 成功，只返回 1 条（`isinstance(True, int)` 为真，`True` 当作 1） | `isError: true`，`limit must be an integer from 1 through 50`（`Number.isInteger(true)` 为假） | 不一致 |
| d | 成功，`id` 原样回显 9007199254740992 | `-32600 id must be a string or integer`，`id: null`（超出 `Number.isSafeInteger`） | 不一致 |
| e | `[{"id": "note-1", "title": "MCP overview"}]`（`json.dumps` 默认带空格、`sort_keys=True`） | `[{"id":"note-1","title":"MCP overview"}]`（无空格，按插入顺序） | 文本不同 |

谁更符合讲义：
- a：Python 更合理。`arguments` 在 MCP 中通常是可选的，`notes_list` 本来就没有必填参数。
- b：Python 正确，数组不是 JSON 对象。
- c：TS 正确，`limit` 的 schema 是 `integer`，布尔值不应被接受。
- d：TS 更稳妥——JSON 数字在 JavaScript 客户端中超过 2⁵³ 会丢精度，id 可能无法配对；测试 `test_typescript_ids_are_limited_to_safe_integer_bounds` 只约束了 TS 一侧。
- e：wire contract 没被破坏（都是合法 JSON 文本），但对"确定性输出 / 缓存键稳定"的追求来说，两个端口的内容字节不同。

保证一致的工程做法：维护一份**语言无关的一致性测试语料**（JSONL：输入请求 + 期望响应的关键字段），用同一个测试驱动对两个进程分别跑 stdio 黑盒测试（本节的 TS id 测试就是这种做法的雏形）；参数校验从手写 `isinstance` 改为基于 `inputSchema` 的 JSON Schema 校验，两边共用同一份 schema。

### Q11 — 参考答案

1. 结果是 `"HACKED"`（已实测）。`sorted` 返回的新列表只是重新排列了**同一批** dict 对象的引用。排序后第 0 个是 `notes_create`，而它在 `TOOLS` 中的下标是 1（定义顺序为 `notes_search`、`notes_create`、`notes_list`）。
2. stdio server 是长生命周期进程，可能先后服务多个客户端（讲义 The Problem："The same process may serve sequential clients"）。任何中间层（日志脱敏、缓存、测试辅助代码）就地修改了响应对象，修改会写回全局 `TOOLS`，之后**所有**客户端看到的工具描述都变了——这是一种隐蔽的跨请求、跨客户端状态，正是本节要消除的东西。修复：`deepcopy(sorted(TOOLS, key=...))`，`PROMPTS` 同理。
3. `str(None)` 得到字符串 `"None"`，实测创建后 `notes_list` 输出 `"tag": "None"`；`tag: 123` 会变成 `"123"`，而 schema 声明的是 `string`。TS 版写的是 `typeof arguments_.tag === "string" ? arguments_.tag : ""`，非字符串一律存空串。更好的修正是显式校验：

```python
    tag = arguments.get("tag", "")
    if not isinstance(tag, str):
        raise ValueError("tag must be a string when provided")
```

### Q12 — 参考答案

1. 描述符：

```python
{
    "name": "notes_delete",
    "description": "Permanently delete one note by id.",
    "inputSchema": {
        "type": "object",
        "properties": {"note_id": {"type": "string"}},
        "required": ["note_id"],
    },
    "annotations": {"destructiveHint": True, "idempotentHint": True, "readOnlyHint": False},
}
```

   `idempotentHint: True`：删除同一个 id 两次，最终状态相同（第二次会报"不存在"，但不会多删别的东西）。

2. executor（已实际运行验证：只有 `notes:read` 权限的 alice 删除失败、笔记仍在；有 `notes:delete` 的 admin 删除成功）：

```python
class Forbidden(Exception):
    pass

def exec_notes_delete(arguments, principal):
    note_id = arguments.get("note_id")
    if not isinstance(note_id, str) or note_id not in NOTES:
        raise ValueError("note_id must name an existing note")
    if "notes:delete" not in principal.get("scopes", ()):
        raise Forbidden(f"principal {principal.get('sub')} may not delete {note_id}")
    del NOTES[note_id]
    return [{"type": "text", "text": f"Deleted {note_id}"}]
```

   - **主体从哪里来**：由传输层的真实认证得出，并在**每个请求**上重新计算——远程 HTTP 场景是经过校验的 OAuth access token（第 16、18 节）；stdio 场景是启动该进程的本地用户 / 注入的环境凭证。`dispatch` 需要把这个 `principal` 传给 handler（本节的 executor 签名只有 `arguments`，需要扩展）。
   - **为什么不能用 `clientInfo`**：讲义明确它是"self-reported display and debugging data, not a security credential"，任何客户端都能自称 `admin-console`。
   - 讲义要求"Keep `destructiveHint` as a UX hint only"：host 看到它可以弹确认框，但即使 host 不弹，server 的授权检查也必须拦住。

3. 若所有用户看到的工具列表都一样（删除权限在执行时检查），`tools/list` 仍可 `public`；但如果改成"按权限过滤工具列表"（没有删除权限的人看不到 `notes_delete`），就必须改为 `private`，否则共享缓存会把管理员的列表发给普通用户。`resources/list` 的 10 秒 TTL 意味着删除后最多 10 秒内，客户端缓存里仍可能出现已删除的 `notes://note-x`，随后 `resources/read` 会得到 `Resource not found`——客户端要能处理这种"列表与读取之间的竞态"；需要更及时时可通过 `subscriptions/listen` 接收变更（第 10 节）。

### Q13 — 参考回答要点

- **流程**（对应 `serve_stdio` + `dispatch`）：
  1. 从 stdin 读一行，空行跳过；
  2. `json.loads` 失败 → `-32700 Parse error`，`id: null`；
  3. 解析结果不是对象（例如数组 batch）→ `-32600`，`id: null`；
  4. 没有 `id` → 通知，**不回复**；
  5. 校验信封与 `_meta`：非法 id → `-32600`（`id: null`）；`jsonrpc`/`method` 错 → `-32600`；`params` / `_meta` / 版本 / capabilities / clientInfo 问题 → `-32602`；版本不支持 → `-32022`；
  6. 按 method 查 handler，没有 → `-32601`；
  7. handler 抛 `RpcProblem` → 对应错误码；其它异常 → `-32603`；
  8. 成功 → `{"jsonrpc": "2.0", "id": ..., "result": complete(...)}`；
  9. 紧凑 JSON + `"\n"` 写 stdout 并 flush；
  10. EOF 时循环结束、进程退出。
- **回复 `id: null` 的情况**：无法解析、不是对象、id 本身非法——因为此时无法（或不应）回显一个可信的 id。
- 加分点：诊断写 stderr；不支持 batch（数组）；每行独立处理，前一行的错误不影响后一行。

### Q14 — 参考回答要点

- **host 角度**：协议错误说明"请求构造有问题 / 对方不支持"，host 应修正自身代码、重试或降级，通常不打扰模型；`isError` 结果是工具运行后的业务结果，需要原样交给模型。
- **模型角度**：`isError` 的文本进入上下文，模型能据此自我纠正（补参数、换查询词、换工具），因此错误信息应该具体、可执行（第 05 节）；协议错误的细节对模型通常没有意义。
- **运维角度**：两类错误分开计数，才能区分"客户端 bug / 版本不兼容"与"下游依赖故障 / 业务输入问题"，告警阈值和责任人也不同。
- 边界讨论：未知工具应归哪类有争议（本节代码选 `isError`，讲义规则更倾向协议错误）；关键是团队统一约定并写进一致性测试。
- 常见误区：把所有异常都包成 `isError`（模型被内部堆栈污染、还可能泄露敏感信息）；或把所有失败都做成协议错误（模型失去自我纠正机会）。

### Q15 — 参考回答要点

- **结构**：一个"时代选择器" + 两个互相隔离的处理器。
  - 选择器在任何 parser 之前运行：请求带完整的现代 `_meta`（版本 + capabilities）→ 现代核心；收到 `initialize`（且没有现代元数据）→ legacy 适配器。讲义："It chooses modern behavior when required modern `_meta` fields are present and legacy behavior when it receives `initialize`."
  - 现代核心保持无状态；legacy 适配器可以持有**连接级**状态（协商结果、`notifications/initialized` 之后才可用的操作），但这些状态不能泄漏给现代核心。
  - 不要给 legacy 的 initialize 结果加 `resultType`；不要让 `2026-07-28` 请求走握手路径。
  - 共享的是**业务逻辑**（笔记的增删查），不共享协议层状态。
- **测试**（讲义练习 5）：
  - 对 legacy 适配器打桩 / 计数，发送各种现代请求，断言计数为 0；
  - 先在同一连接上走一遍 legacy 握手，再发现代请求，断言现代请求的结果不受握手中声明的能力影响；
  - 现代请求缺 capabilities 时得到 `-32602`，而不是被当作 legacy 处理；
  - legacy 流程的端到端测试独立存在。
- 加分点：说出 skill 中的硬性拒绝项——"A modern server whose first valid method must be `initialize`"。

### Q16 — 参考回答要点

- **身份与授权**：每个请求由传输层认证得到主体（不是 `clientInfo`），handler 和 executor 内按主体过滤 / 授权。
- **缓存提示**：
  - `tools/list`、`prompts/list`：若对所有租户相同仍可 `public`；一旦按权限 / 租户过滤，改为 `private`；
  - `resources/list`、`resources/read`：必然 `private`，TTL 视一致性要求调小或为 0；
  - `server/discover`：通常 `public`。
- **排序**：所有列表按稳定键排序（本节按 note id / name / uri）；分页时用基于排序键的游标，保证翻页稳定。
- **应用状态与协议状态的边界**：笔记存数据库（应用状态，允许且必要），每个副本都能处理任何请求；不在任何地方保存"这个连接声明过的能力 / 版本 / clientInfo"。跨调用的工作流用不透明 handle 作普通参数传递（第 06 节）。
- 加分点：资源 URI 不要编码可猜测的用户信息，读取时仍要按主体校验（URI 不是凭证）；`notes_create` 生成的 ID 用随机值而非自增，避免枚举。

### Q17 — 参考回答要点

- **集中包装的目的**：讲义"Centralizing this wrapper prevents one handler from silently omitting modern result fields." `resultType` 是现代结果的判别字段，缺了它客户端会把结果当作 legacy 或非法（第 06 节的追踪器就会把它标为 legacy）。
- **漏掉的后果**：新 handler 返回裸 dict → 没有 `resultType`、没有 `serverInfo`、没有缓存提示 → 现代客户端拒收或误判，缓存层按默认值处理。
- **CI 防线**：
  - 参数化测试遍历 `HANDLERS` 中所有方法（本节 `test_every_success_has_server_identity` 只覆盖了 3 个 list 方法，可以扩展到全部）；
  - 对 list / read / discover 方法断言存在 `ttlMs` 与合法的 `cacheScope`；
  - TS 中把 handler 的返回类型声明为 `CompleteResult`，只能由 `complete()` 构造（品牌类型 / 私有构造）。
- **TTL 取值逻辑**（代码中的值，讲义未规定具体数字）：
  - `server/discover` 1 小时：版本和能力只随部署变化；
  - `tools/list`、`prompts/list` 60 秒：定义稳定，但部署新版本后希望较快生效；
  - `resources/list` 10 秒、`resources/read` 5 秒：数据会被 `notes_create` 修改，需要更新鲜；
  - `prompts/get`、`tools/call` 不缓存。
  - 原则：变化越频繁、越个性化，TTL 越短、作用域越窄；拿不准就用讲义的安全默认 `0` + `private`。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：本节所有校验规则和结果形状的来源。
- [阶段 13 · 05 工具 Schema 设计：命名、描述与 Parameter 约束](../../05-tool-schema-design/docs/zh.md)：工具拆分粒度、`inputSchema` 与可执行的错误信息。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../04-structured-output/docs/zh.md)：用 schema 校验替代手写 `isinstance`（Q10）。
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../01-the-tool-interface/docs/zh.md)：工具作为结构化契约的基本思想。

### 本节被哪些后续内容用到
- [阶段 13 · 08 构建 MCP 客户端：发现、路由与新旧协议兼容回退](../../08-building-an-mcp-client/docs/zh.md)：与本节 server 对接的客户端。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：同一套 dispatch 放到 HTTP 上。
- [阶段 13 · 10 MCP Resources 与 Prompts：无状态服务端的可寻址上下文](../../10-mcp-resources-and-prompts/docs/zh.md)：资源模板与 `subscriptions/listen`（讲义练习 4 的延伸）。
- [阶段 13 · 11 MCP 模型输入：Sampling 迁移与无状态 MRTR](../../11-mcp-sampling/docs/zh.md)：`input_required` 结果的完整流程。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：工具描述被篡改的风险（对照 Q11 的共享引用问题）。
- [阶段 13 · 18 生产环境中的 MCP 认证：绑定签发者的注册与 Tokens](../../18-mcp-auth-production/docs/zh.md)：Q12 中授权主体的真实来源。
- [阶段 13 · 28 MCP Tool Contracts 与内容](../../28-mcp-tool-contracts-and-content/docs/zh.md)、[阶段 13 · 31 MCP 一致性工程：版本管理、证据与运维](../../31-mcp-conformance-versioning-and-operations/docs/zh.md)：工具契约与跨实现一致性测试（Q10）。

### 延伸关键词
`stdio transport` · `newline-delimited JSON` · `server/discover` · `tools/list` · `tools/call` · `isError` · `resources/read` · `prompts/get` · `tool annotations` · `cacheScope` · `deterministic ordering` · `input_required` · `MRTR` · `legacy adapter` · `conformance test`
