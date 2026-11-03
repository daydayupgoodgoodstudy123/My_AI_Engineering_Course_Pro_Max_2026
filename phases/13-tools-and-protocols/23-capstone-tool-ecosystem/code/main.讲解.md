# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 23 节 综合项目：无状态工具生态系统 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下） ｜ **依赖**：仅标准库（`hashlib`、`json`、`time`、`uuid`、`copy`、`datetime`）；不联网、不需要 API key。测试另依赖仓库根目录的 `scripts/build_catalog.py` 与 `scripts/install_skills.py`（本副本中不存在，见第 9 节）

---

## 1. 这份代码在考察什么

这是阶段 13 的综合项目：一个"研究并出报告"系统的**进程内模拟**。它用普通 Python 函数和字典，把讲义列出的几条独立契约放进同一个流程里，同时让每条边界都保持可见：

1. **无状态 MCP 请求信封**：每个请求带协议版本、客户端能力、客户端身份（`request_meta`），服务端逐请求校验（`validate_request_meta`）；强制的 `server/discover`。
2. **网关**：静态 token → 用户 → scope 的 RBAC；工具描述的固定哈希（pinned hash）检查；审计日志。
3. **Tasks 扩展**：`generate_report` 先返回 `resultType: "task"` 的句柄，再用 `tasks/get` 取到完成的任务和最终结果。
4. **A2A 形状的委托**：写作 agent 被表示为一个嵌套的 `a2a.SendMessage` span，内部不透明。
5. **MCP App 形状的 UI 资源**：`ui://report/current` 引用 + 一段 HTML 字符串 + CSP。
6. **OTel GenAI 形状的追踪**：内存中的 span 字典，同一次运行共享 trace id，记录父 span id。

文件 docstring 明确声明：不实现 MCP/A2A 传输、OAuth、App 桥、遥测导出器、执行沙箱。

> 一句话：**用一个可读的模拟把"系统是一组边界"演示出来，同时诚实地标出每条边界在生产中必须替换成什么。** 读这份代码时要特别留意"模拟在哪里偷懒了"——授权、审计、追踪和数据流各有一个值得修的缺口。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SPANS` / `TASKS` / `AUDIT` | 模块级全局容器 | 内存中的 span 列表、任务存储、审计日志 | 遥测、任务存储、审计 |
| `PROTOCOL_VERSION` / `TASK_EXTENSION` / `SERVER_INFO` | 常量 | `2026-07-28`、`io.modelcontextprotocol/tasks`、服务端身份 | 无状态 MCP |
| `request_meta` | 函数 | 构造每请求的 `_meta`（可选声明 tasks 扩展） | 请求信封 |
| `_server_meta` / `complete_result` / `protocol_error` | 函数 | 结果的 `_meta.serverInfo`、`resultType: complete` 结果、JSON-RPC 风格错误 | 结果形状 |
| `validate_request_meta` | 函数 | 校验版本（`-32022`）、形状（`-32602`）、tasks 能力（`-32021`） | 逐请求校验 |
| `server_discover` | 函数 | 返回支持版本、能力、`ttlMs`、`cacheScope` | 强制发现 |
| `_hex` / `span` / `finish` | 函数 | 生成随机 id、创建 span、结束 span | 追踪 |
| `TOOLS` / `PAPERS` / `PINNED` | 常量 | 工具清单、论文夹具、描述哈希清单 | 工具元数据、固定哈希 |
| `research_arxiv_search` | 函数 | 标题子串搜索，返回 `content` | 工具实现 |
| `research_generate_report` | 函数 | 创建任务 span 与 A2A span，写入完成任务，返回任务句柄 | Tasks、A2A、MCP App |
| `tasks_get` | 函数 | 按 id 返回任务深拷贝 | `tasks/get` |
| `USERS` / `REQUIRED_SCOPE` / `pin_ok` | 常量/函数 | token→用户与 scope；工具→所需 scope；哈希比对 | 认证、授权、投毒防御 |
| `gateway_call` | 函数 | 元数据 → token → scope → 工具存在 → 哈希 → span + 分派 + 审计 | 网关 |
| `orchestrator` | 函数 | 根 span → LLM span → 搜索 → 报告 → 轮询任务 → LLM span | 编排 |
| `demo` | 函数 | discover、Alice 运行、Bob 运行、打印审计、span、覆盖清单 | 演示 |

数据流：`demo` → `server_discover(request_meta())` → `orchestrator("tok_alice", ...)` → `gateway_call(arxiv_search)` → `research_arxiv_search` → `gateway_call(generate_report)` → `research_generate_report`（写 `TASKS`、产生子 span）→ `tasks_get` → 返回汇总字典；再以 Bob 运行一次 → 打印 `AUDIT` 与 `SPANS`。

---

## 3. 逐段精讲

### 3.1 每请求元数据与校验

```python
def request_meta(*, tasks: bool = False) -> dict:
    extensions = {TASK_EXTENSION: {}} if tasks else {}
    return {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {"extensions": extensions},
        "io.modelcontextprotocol/clientInfo": {
            "name": "capstone-client",
            "version": "1.0.0",
        },
    }
```

- 这正是讲义给出的三个命名空间字段。`*` 让 `tasks` 只能以关键字传入（`request_meta(tasks=True)`），可读性更好。
- 每次调用返回**新字典**，没有共享的"会话"对象——无状态的直接体现。

```python
def validate_request_meta(meta: dict, *, require_tasks: bool = False) -> dict | None:
    if not isinstance(meta, dict):
        return protocol_error(-32602, "params._meta must be an object")
    requested = meta.get("io.modelcontextprotocol/protocolVersion")
    if not isinstance(requested, str):
        return protocol_error(-32602, "protocolVersion must be a string")
    if requested != PROTOCOL_VERSION:
        return protocol_error(
            -32022,
            "Unsupported protocol version",
            {"supported": [PROTOCOL_VERSION], "requested": requested},
        )
    ...
    if require_tasks and (
        not isinstance(extensions, dict) or TASK_EXTENSION not in extensions
    ):
        return protocol_error(
            -32021,
            "Missing required client capability",
            {"requiredCapabilities": {"extensions": {TASK_EXTENSION: {}}}},
        )
    return None
```

| 条件 | 错误码 | 说明 |
|---|---|---|
| `_meta` 不是对象、版本不是字符串、能力不是对象 | `-32602` | JSON-RPC 标准的 Invalid params |
| 版本不等于 `2026-07-28` | `-32022` | data 里给出 `supported` 与 `requested`，便于客户端降级 |
| 需要 tasks 但未声明 | `-32021` | `requiredCapabilities` 的形状就是"缺失的客户端能力对象" |

- 返回 `dict | None`：`None` 表示通过，调用方写 `if invalid: return invalid`——"返回错误而不是抛异常"的风格，与协议错误最终要序列化给客户端一致。
- 简化：只支持一个版本；`clientInfo` 不校验；`extensions` 缺失时默认 `{}`。

### 3.2 `server_discover`

```python
def server_discover(meta: dict) -> dict:
    invalid = validate_request_meta(meta)
    if invalid:
        return invalid
    return complete_result(
        supportedVersions=[PROTOCOL_VERSION],
        capabilities={
            "tools": {"listChanged": False},
            "extensions": {TASK_EXTENSION: {}},
        },
        ttlMs=3_600_000,
        cacheScope="public",
    )
```

- discover 本身也是普通请求，同样要带 `_meta` 并被校验。实测只给版本、不给能力对象时返回 `-32602 clientCapabilities must be an object`。
- `ttlMs=3_600_000`（1 小时）+ `cacheScope="public"`：告诉客户端这份发现结果可以缓存多久、能否跨用户共享——对应讲义"cache-aware `tools/list`"。
- `complete_result(**fields)` 用 `{"resultType": "complete", **fields, "_meta": _server_meta()}` 拼装：字典解包让任意字段都能透传，`_meta` 放最后保证不会被调用方覆盖。
- `_server_meta()` 每次 `deepcopy(SERVER_INFO)`，避免调用方修改返回值时污染全局常量。

### 3.3 追踪：`_hex`、`span`、`finish`

```python
def _hex(n: int) -> str:
    return uuid.uuid4().hex[: n * 2]


def span(name: str, kind: str, trace_id: str | None, parent: str | None,
         attrs: dict) -> dict:
    tid = trace_id or _hex(16)
    sp = {"name": name, "kind": kind, "traceId": tid, "spanId": _hex(8),
          "parentSpanId": parent, "start": time.time_ns(), "attrs": attrs, "end": 0}
    SPANS.append(sp)
    return sp


def finish(sp: dict) -> None:
    sp["end"] = max(time.time_ns(), sp["start"] + 1)
```

- trace id 16 字节（32 个十六进制字符），span id 8 字节（16 个十六进制字符），与 W3C Trace Context 的长度一致。
- ⚠️ `uuid4().hex` 不是 128 位全随机：第 13 个字符固定是版本号 `4`（实测连续三次都是 `4`），还有 2 位 variant。教学足够，生产应由 OTel SDK 生成 id。
- `finish` 用 `max(..., start + 1)` 保证结束时间严格大于开始时间：时钟分辨率不够时两次 `time_ns()` 可能相等，测试 `test_finish_guarantees_positive_duration_at_clock_resolution_boundary` 专门用 mock 验证了这一点。代价是这个 1ns 不是真实耗时。
- span 是普通字典，`SPANS.append` 在**创建时**就入列——所以打印顺序是"开始顺序"，不是"结束顺序"。

### 3.4 工具清单、论文夹具与固定哈希

```python
TOOLS = [
    {"name": "arxiv_search", "description": "Use when the user searches arXiv by keyword."},
    {"name": "generate_report", "description": "Use when the user wants a full report."},
]
...
PINNED = {f"research::{t['name']}": hashlib.sha256(t["description"].encode()).hexdigest()
          for t in TOOLS}
```

- `PINNED` 用字典推导式在**导入时**计算每个描述的 SHA-256，键带 `research::` 前缀（服务器命名空间），为"多个后端同名工具"预留了区分方式（讲义练习 2）。
- 工具清单只有名字和描述，没有 `inputSchema`；`research_arxiv_search` 直接 `args["query"]`，缺参数时抛 `KeyError`（实测），而不是返回结构化的参数错误。
- 论文是 3 条静态夹具，标题里的 arXiv 编号只是示例数据。

### 3.5 两个工具实现

```python
def research_arxiv_search(args: dict) -> dict:
    q = args["query"].lower()
    hits = [p for p in PAPERS if q in p["title"].lower()]
    return complete_result(
        content=[{"type": "text", "text": json.dumps(hits)}],
        isError=False,
    )
```

- 标题子串匹配；"agent" 只命中 `Agent-to-agent coordination benchmarks`；空查询会命中全部（空串是任何字符串的子串）。
- 结果用 MCP 的 `content` 数组 + `isError`，命中列表被序列化成 JSON 文本放进 `text` 块。

```python
def research_generate_report(args: dict, trace_id: str, parent: str) -> dict:
    task_id = f"tsk_{uuid.uuid4().hex[:10]}"
    sp = span("mcp.task.working", "INTERNAL", trace_id, parent,
              {"gen_ai.operation.name": "execute_tool", "mcp.task.id": task_id})
    a2a = span("a2a.SendMessage", "CLIENT", trace_id, sp["spanId"],
               {"a2a.peer": "writer-agent", "a2a.skill": "summarize_papers"})
    finish(a2a)
    finish(sp)
    html = (... "".join(f"<li>{p['arxiv_id']}: {p['title']}</li>" for p in PAPERS) ...)
    now = datetime.now(timezone.utc).isoformat()
    TASKS[task_id] = {
        "resultType": "complete",
        "taskId": task_id,
        "status": "completed",
        ...
        "result": complete_result(
            content=[
                {"type": "text", "text": "Report generated: 3 papers summarized."},
                {"type": "ui_resource", "uri": "ui://report/current"},
            ],
            ui={"resourceUri": "ui://report/current",
                "csp": {"default-src": "'self'"}, "permissions": []},
            html=html,
        ),
        "_meta": _server_meta(),
    }
    return {
        "resultType": "task",
        "taskId": task_id,
        "status": "working",
        ...
        "ttlMs": 900_000,
        "pollIntervalMs": 1_000,
        "_meta": _server_meta(),
    }
```

- **任务 span 与委托 span**：`mcp.task.working` 以网关的 `mcp.call` span 为父；`a2a.SendMessage`（kind 为 CLIENT）以任务 span 为父。写作 agent 内部没有任何 span——讲义的"opacity boundary"：调用方只看见边界。
- **"立即完成"的任务**：存进 `TASKS` 的已经是 `completed`，但返回给调用方的句柄写着 `working`。这是模拟的简化：真实任务存储会经历 `working → completed`（或失败、取消、需要输入）的状态迁移，客户端按 `pollIntervalMs` 轮询。
- **句柄与终态的形状差异**：句柄 `resultType: "task"`；`tasks/get` 返回的终态 `resultType: "complete"` 且带 `result`——与讲义"`tasks/get` itself returns `resultType: "complete"`"一致。
- **UI 资源**：`ui://` URI + 限制性 CSP（`default-src 'self'`）+ 空权限列表；HTML 里的 `<script>` 注释说明"真实 App 桥刻意缺席"。实测 HTML 长度 330 字符。
- ⚠️ `args` 完全没被使用；HTML 遍历全局 `PAPERS`（3 篇），文本"3 papers summarized."是硬编码——与搜索结果无关（测验 Q12）。
- ⚠️ 讲义"Simulation versus production"表中 Delegation 一行写"Sleep plus nested span"，但代码里没有任何 `sleep`，讲义另一张表"Current protocol surfaces"也说"One nested span with no remote call or artificial delay"——两处讲义互相矛盾，以代码为准：没有人为延迟。

### 3.6 `tasks_get`

```python
def tasks_get(task_id: str, meta: dict) -> dict:
    invalid = validate_request_meta(meta, require_tasks=True)
    if invalid:
        return invalid
    if not isinstance(task_id, str):
        return protocol_error(-32602, "Unknown taskId")
    task = TASKS.get(task_id)
    if task is None:
        return protocol_error(-32602, "Unknown taskId")
    return deepcopy(task)
```

- 先校验 `_meta` 且要求 tasks 能力——`tasks/get` 属于扩展方法，不声明能力就不该调用。
- `isinstance(task_id, str)` 先于字典查找：列表、字典不可哈希，直接 `TASKS.get([])` 会抛 `TypeError`；这里统一返回 `Unknown taskId`（测试 `test_tasks_get_rejects_non_string_ids_without_hashing_them`）。
- `deepcopy` 防止调用方修改返回值进而篡改存储。
- ⚠️ **没有任何身份校验**：不经过网关、不看 token、任务也没记录创建者。实测：不带 token 直接调用即可拿到 Alice 的完整报告（测验 Q9 给出修复）。
- ⚠️ `ttlMs` 只是写在记录里的字段，`TASKS` 永不过期。

### 3.7 网关 `gateway_call`

```python
def gateway_call(token: str, tool_name: str, args: dict,
                 trace_id: str, parent: str, meta: dict) -> dict:
    invalid = validate_request_meta(
        meta, require_tasks=tool_name == "generate_report"
    )
    if invalid:
        return invalid
    u = USERS.get(token)
    if not u:
        return {"error": "unauthenticated"}
    required = REQUIRED_SCOPE.get(tool_name)
    if required and required not in u["scopes"]:
        AUDIT.append({"user": u["id"], "tool": tool_name, "decision": "403"})
        return {"error": "insufficient_scope", "scope": required}
    tool = next((t for t in TOOLS if t["name"] == tool_name), None)
    if tool is None:
        return {"error": "unknown tool"}
    if not pin_ok(tool_name, tool["description"]):
        return {"error": "hash_mismatch"}
    sp = span("mcp.call", "CLIENT", trace_id, parent, {...})
    if tool_name == "arxiv_search":
        result = research_arxiv_search(args)
    else:
        result = research_generate_report(args, trace_id, sp["spanId"])
    finish(sp)
    AUDIT.append({"user": u["id"], "tool": tool_name, "decision": "allow"})
    return result
```

- `require_tasks=tool_name == "generate_report"`：网关知道哪个工具会返回任务句柄，于是只对它要求 tasks 能力。比较表达式的结果直接作为布尔实参。
- `next((... for ...), None)`：在列表里找第一个匹配项，找不到返回默认值 `None`。
- 检查顺序：元数据 → 认证 → scope → 工具存在 → 哈希 → 分派。
- ⚠️ **审计缺口**：只有"scope 不足"和"允许"写审计；元数据无效、未认证、未知工具、哈希不匹配四种拒绝都**不留痕**（实测）。
- ⚠️ **错误形状不一致**：协议错误是 `{"error": {"code", "message", "data"}}`，网关错误是 `{"error": "<字符串>"}`。
- ⚠️ **追踪缺口**：`mcp.call` span 在所有检查通过后才创建，被拒绝的调用在 trace 中不可见。
- ⚠️ scope 检查在"工具是否存在"之前：`REQUIRED_SCOPE.get` 对未知工具返回 `None`，`if required and ...` 直接跳过——更稳妥的顺序是先确认工具存在，再强制查表（缺表项即拒绝）。
- `pin_ok` 的比较对象来自同一进程的 `TOOLS`，正常运行时永远相等；只有在运行中修改 `TOOLS`（测试与测验 Q7 的做法）才会触发 `hash_mismatch`。

### 3.8 `orchestrator`：一次完整的 agent 调用

```python
def orchestrator(token: str, user_query: str) -> dict:
    trace_id = _hex(16)
    root = span("agent.invoke_agent", "INTERNAL", trace_id, None, {...})
    llm1 = span("llm.chat", "CLIENT", trace_id, root["spanId"], {... "gen_ai.request.model": "gpt-4o", "gen_ai.usage.input_tokens": 24})
    finish(llm1)

    search = gateway_call(token, "arxiv_search",
                          {"query": "agent"}, trace_id, root["spanId"],
                          request_meta())
    report = gateway_call(token, "generate_report",
                          {"format": "html"}, trace_id, root["spanId"],
                          request_meta(tasks=True))
    task = None
    if report.get("resultType") == "task":
        task = tasks_get(report["taskId"], request_meta(tasks=True))
    llm2 = span("llm.chat", ...)
    finish(llm2)
    finish(root)
    return {"trace_id": trace_id, "search": search, "report": report, "task": task}
```

- 每次调用生成一个新 trace，根 span 的 `parentSpanId` 为 `None`；所有子调用都把 `root["spanId"]` 传为父节点。
- 每个请求都**重新**调用 `request_meta(...)`——搜索不需要 tasks 能力，报告与轮询需要。
- `report.get("resultType") == "task"` 守卫：Bob 被拒时 `report` 是错误字典，没有 `resultType`，`task` 保持 `None`。
- 只轮询一次：因为任务"立即完成"，所以一次 `tasks_get` 就拿到终态；真实实现应循环、遵守 `pollIntervalMs` 并处理超时。
- ⚠️ `user_query` 参数**从未使用**，搜索词写死为 `"agent"`；LLM span 的模型名与 token 数是硬编码的示意值，没有真实模型调用。

### 3.9 `demo`

依次打印：discover 结果 → Alice 的运行摘要 → Bob 的报告结果 → 审计日志 → 全部 span（traceId 前 6 位、名称、kind、父 id 前 6 位、耗时）→ 十条"原语覆盖"清单。span 耗时用 `round((end - start) / 1_000_000, 2)` 换算成毫秒。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 进程内函数代替传输 | 控制流一眼可读，不把模拟包装成合规服务 | 证明不了序列化、超时、重试；需要线上 transcript |
| 每请求重建 `_meta` 并逐请求校验 | 体现无状态 MCP 的核心变化 | 无 |
| 错误以返回值而非异常传递 | 与协议错误最终序列化给客户端的形态一致 | 网关错误与协议错误形状不统一，应统一为一种 |
| 任务创建即完成 | 一次 `tasks/get` 就能演示终态形状 | 看不到状态迁移、取消、恢复；需持久化任务存储 + TTL |
| `tasks_get` 不经网关 | 代码短 | 任何人凭 task id 可读结果；必须绑定所有者并重新授权 |
| 静态 token 字典 + scope 集合 | 演示策略流 | 无签发者、受众、过期；生产用 OAuth 授权服务器与资源服务器校验 |
| 描述哈希在导入时计算 | 演示"描述被改即拒绝" | 清单与被比对对象同源；真实清单来自审核流程，比对对象来自实时 `tools/list` |
| 只审计 scope 拒绝与允许 | 代码简短 | 大部分拒绝无痕；应审计每个决策 |
| span 在授权通过后才创建 | 只追踪真实执行的工作 | 被拒绝的请求在 trace 中不可见；应建 span 并标错误状态 |
| 全局可变容器 `SPANS/TASKS/AUDIT` | 便于打印与测试检查 | 跨测试污染（测试在 `setUp` 中手动清空）；不支持并发 |
| A2A 只是一个 span | 体现不透明边界 | 无 Agent Card、无消息、无超时；需 A2A 客户端与测试服务器 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring | 文件开头三引号说明 | 说明用途与"不做什么" |
| 仅关键字参数 | `def request_meta(*, tasks: bool = False)` | `*` 之后的参数必须用 `tasks=True` 形式传 |
| 条件表达式 | `{TASK_EXTENSION: {}} if tasks else {}` | 一行内的 if/else |
| 联合类型返回 | `-> dict \| None` | 返回字典或 None |
| `**kwargs` 收集与字典解包 | `def complete_result(**fields)`、`{"resultType": "complete", **fields, "_meta": ...}` | 把任意关键字参数收成字典，再展开进新字典；后出现的键覆盖先出现的 |
| `deepcopy` | `deepcopy(SERVER_INFO)`、`deepcopy(task)` | 递归复制，防止共享可变对象被改 |
| 数字下划线 | `3_600_000`、`900_000`、`1_000_000` | 仅为可读性，等价于 `3600000` |
| 字典推导式 | `{f"research::{t['name']}": hashlib.sha256(...).hexdigest() for t in TOOLS}` | 一行构造字典 |
| `hashlib` | `hashlib.sha256(s.encode()).hexdigest()` | 先把字符串编码为字节，再求十六进制摘要 |
| `uuid` | `uuid.uuid4().hex[:10]` | 随机 UUID 的 32 位十六进制表示再切片 |
| `time.time_ns()` | `"start": time.time_ns()` | 纳秒级整数时间戳，避免浮点误差 |
| 时区感知时间 | `datetime.now(timezone.utc).isoformat()` | 带 `+00:00` 的 ISO 8601 字符串 |
| 列表推导式 + 过滤 | `[p for p in PAPERS if q in p["title"].lower()]` | 筛选 |
| `in` 子串判断 | `q in p["title"].lower()` | 字符串包含 |
| `next(生成器, 默认值)` | `next((t for t in TOOLS if t["name"] == tool_name), None)` | 取第一个匹配项 |
| 生成器表达式 + `join` | `"".join(f"<li>...</li>" for p in PAPERS)` | 拼接 HTML 片段 |
| 布尔表达式作实参 | `require_tasks=tool_name == "generate_report"` | 比较结果直接是 bool |
| `dict.get` | `USERS.get(token)`、`report.get("resultType")` | 键不存在时返回 None 而非抛异常 |
| 集合成员判断 | `required not in u["scopes"]` | scope 用 `set` 存，判断为 O(1) |
| f-string 格式符 | `f"{sp['name']:20s} {sp['kind']:8s}"` | 左对齐填充到指定宽度 |
| `round` | `round((sp['end'] - sp['start']) / 1_000_000, 2)` | 保留两位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 被导入（如测试）时不运行 demo |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 code/main.py`，退出码 0；trace/span id 与 task id 每次随机）：

```text
--- stateless server discovery ---
  protocol       : 2026-07-28
  task extension : True

--- orchestrator run as alice (read+write) ---
  trace id      : a26e359d7aa845b8b1d3d76489923302
  search result : [{"arxiv_id": "2604.01055", "title": "Agent-to-agent coordination benchmarks"}]
  report handle : tsk_14567efe42 (working)
  task status   : completed via tasks/get
  ui bytes      : 330

--- orchestrator run as bob (read only) ---
  generate_report -> {'error': 'insufficient_scope', 'scope': 'research:write'}

--- audit log ---
  {'user': 'alice', 'tool': 'arxiv_search', 'decision': 'allow'}
  {'user': 'alice', 'tool': 'generate_report', 'decision': 'allow'}
  {'user': 'bob', 'tool': 'arxiv_search', 'decision': 'allow'}
  {'user': 'bob', 'tool': 'generate_report', 'decision': '403'}

--- OTel GenAI spans ---
  [a26e35] agent.invoke_agent   INTERNAL parent=ROOT  dur=0.15ms
  [a26e35] llm.chat             CLIENT   parent=f3b654  dur=0.0ms
  [a26e35] mcp.call             CLIENT   parent=f3b654  dur=0.03ms
  [a26e35] mcp.call             CLIENT   parent=f3b654  dur=0.05ms
  [a26e35] mcp.task.working     INTERNAL parent=8b2961  dur=0.01ms
  [a26e35] a2a.SendMessage      CLIENT   parent=762321  dur=0.0ms
  [a26e35] llm.chat             CLIENT   parent=f3b654  dur=0.0ms
  [952918] agent.invoke_agent   INTERNAL parent=ROOT  dur=0.03ms
  [952918] llm.chat             CLIENT   parent=8a62e4  dur=0.0ms
  [952918] mcp.call             CLIENT   parent=8a62e4  dur=0.02ms
  [952918] llm.chat             CLIENT   parent=8a62e4  dur=0.0ms

--- primitive coverage ---
  + tool interface and direct function dispatch
  ...（共 10 条）
```

逐项解读（对照讲义"Build It"要求检查的项目——讲义写"Inspect five things"却列了 6 条，也是一个小笔误）：

1. **discover**：版本 `2026-07-28`，能力里含 tasks 扩展。
2. **授权**：Alice 读写都成功；Bob 的搜索成功、报告被拒，`scope` 字段指明缺少 `research:write`。
3. **追踪**：每次运行一个 trace id；Alice 的树有 7 个 span，Bob 的只有 4 个——被拒的报告调用没有 span。`8b2961` 是 Alice 第二个 `mcp.call`（generate_report），`762321` 是 `mcp.task.working`。`dur=0.0ms` 是因为进程内调用极快、四舍五入到两位小数。
4. **任务**：句柄 `working`，`tasks/get` 后 `completed`；UI HTML 330 字符。
5. **委托不透明**：`a2a.SendMessage` 之下没有任何写作 agent 内部 span。
6. **无越界宣称**：覆盖清单只说"shaped / simulation / in-memory"，没有声称发生了网络连接、OAuth、导出、渲染或沙箱执行。

值得注意的不一致：搜索只返回 1 篇（标题含 "agent"），报告却说 "3 papers summarized" 并列出全部 3 篇——`orchestrator` 没用用户问题、`generate_report` 没用搜索结果（测验 Q12）。

---

## 7. 动手改一改

1. **（讲义练习 1）** 把输出逐行分成"本地输出可证明的事实"和"仍需集成证据的生产声明"两列，对照讲义"Simulation versus production"表。
2. **修数据流**：让 `orchestrator` 用 `user_query`（先简单取关键词），把搜索命中通过 `args["papers"]` 传给 `generate_report`，报告文本中的篇数改为 `len(papers)`。
3. **补审计与错误形状**：每个拒绝都写 `AUDIT`（带 reason），所有错误统一为 `{"error": {"code", "message", "data"}}`；为被拒的调用也创建 `mcp.call` span 并在 attrs 中记录拒绝原因（测验 Q10、Q11）。
4. **任务归属**：在网关里记录 `task_id → user_id`，新增经网关的 `tasks_get(token, task_id, meta)`，跨用户读取返回 `Unknown taskId`；再实现 `tasks_cancel` 与 TTL 过期清理（讲义练习 4 的本地版）。
5. **（讲义练习 2）** 增加第二个静态后端 `catalog::arxiv_search`，定义同名工具的冲突规则（例如必须用 `server::tool` 限定名调用），并相应调整 `PINNED` 的键。
6. **进阶（讲义练习 6）**：安装 `opentelemetry-sdk`，用 `InMemorySpanExporter` 或本地 collector 替换 `SPANS`，断言接收端的父子关系与错误状态；对比"同一 trace id"与"正确父子关系"两种断言的强弱。

---

## 8. 常见坑

- **以为 demo 跑通就"接上了 MCP"**：这里没有任何传输层；讲义的关键词是 "protocol-shaped simulation"。
- **能力只声明一次**：在无状态模型里，每个可能收到任务句柄的请求都要声明 tasks 扩展，否则 `-32021`。
- **用旧方法名**：`tasks/result`、`tasks/list`、`initialize`、`Mcp-Session-Id` 都不属于当前设计，随包蓝图把它们列为硬拒绝。
- **把 task id 当授权凭证**：本实现中 `tasks_get` 不校验身份，照抄到生产就是越权读取漏洞。
- **只看 trace 排障**：被拒的调用没有 span，审计也只覆盖一种拒绝；两者都不完整。
- **测试间状态泄漏**：`SPANS`、`TASKS`、`AUDIT` 是模块级全局变量，测试必须在 `setUp` 里清空（现有测试已这样做）；多次调用 `demo()` 会累积。
- **哈希检查"永远通过"**：清单与当前描述同源，只有在运行中修改 `TOOLS` 才会触发；不要据此认为已经防住了服务端的描述篡改。
- **平面 skill 文件的元数据嵌套**：课程的 `version`/`tags` 必须在顶层，嵌套进 `metadata` 会被静默跳过。

---

## 9. 测试在验证什么

测试文件：`code/tests/test_main.py`，共 14 个用例，`setUp` 中清空 `SPANS`、`AUDIT`、`TASKS`。

**运行情况**：

- 按讲义命令 `python3 -m unittest discover -s code/tests -v` 运行时，**整个测试模块导入失败**：`ModuleNotFoundError: No module named 'build_catalog'`。原因是测试顶部从仓库根目录 `scripts/` 导入 `build_catalog.parse_artifact` 与 `install_skills.artifact_from_markdown`（`REPO_ROOT = Path(__file__).resolve().parents[5]`），而本课程副本不包含仓库根的 `scripts/` 目录。结果是 1 个导入错误、0 个用例实际执行。
- 为了验证其余用例，我在临时目录用一个运行脚本向 `sys.modules` 注入这两个模块的桩（调用时抛 `SkipTest`），再加载 `test_main`：**Ran 14 tests，OK (skipped=1)**——13 个用例全部通过，依赖仓库脚本的 `test_shipped_blueprint_metadata_matches_course_parsers` 被跳过、**未实际验证**。

| 用例 | 验证的性质 |
|---|---|
| `test_pinned_description_detects_mutation` | 原描述 `pin_ok` 为 True，追加 " changed" 后为 False |
| `test_finish_guarantees_positive_duration_at_clock_resolution_boundary` | 用 `patch.object(main.time, "time_ns", side_effect=[123, 123])` 模拟时钟不前进，`end - start == 1` |
| `test_search_uses_local_fixtures` | 搜索 "agent" 至少一条命中，`isError=False`，`resultType=complete` |
| `test_server_discovery_advertises_stateless_revision_and_task_extension` | discover 的版本、`ttlMs`、`cacheScope`、tasks 扩展、`resultType` |
| `test_unsupported_protocol_version_uses_reserved_error` | 请求 `2025-11-25` → `-32022`，data 为 `{"supported": ["2026-07-28"], "requested": "2025-11-25"}` |
| `test_missing_protocol_version_is_invalid_params` | 删除版本字段 → `-32602` |
| `test_unknown_token_is_rejected` | 未知 token → `{"error": "unauthenticated"}`，且**没有产生 span** |
| `test_read_only_actor_cannot_generate_report` | Bob 生成报告 → `insufficient_scope`，最后一条审计为 `403` |
| `test_report_uses_task_extension_and_tasks_get_returns_final_result` | 句柄 `task/working`，`tasks_get` 后 `complete/completed`，含 `ui://report/current` 与 `<!doctype html>` |
| `test_task_handle_requires_per_request_extension_capability` | 不声明 tasks → `-32021`，`requiredCapabilities` 形状精确匹配 |
| `test_tasks_get_rejects_non_string_ids_without_hashing_them` | `[]`、`{}` 作 id → `-32602 Unknown taskId`，不抛 `TypeError` |
| `test_delegation_span_uses_current_a2a_operation_name` | span 名为 `a2a.SendMessage`（A2A v1 的当前方法名） |
| `test_one_orchestrator_run_preserves_trace_parentage` | 一次运行中只有一个根 span 且名为 `agent.invoke_agent`，所有 span 时长为正 |
| `test_shipped_blueprint_metadata_matches_course_parsers` | 用仓库真实的目录/安装解析器读取 `outputs/skill-ecosystem-blueprint.md`，断言 version、tags、phase、lesson（本副本中未能运行） |

测试没有覆盖、值得补的地方：跨用户 `tasks_get`（当前会成功，应当失败）；未认证/未知工具/哈希不匹配是否写审计；被拒调用是否出现在 trace 中；报告内容是否与搜索结果一致。另外建议把测试对仓库 `scripts/` 的依赖改为 `try/except ImportError` + `skipUnless`，避免一个可选依赖让整个测试模块失效。
