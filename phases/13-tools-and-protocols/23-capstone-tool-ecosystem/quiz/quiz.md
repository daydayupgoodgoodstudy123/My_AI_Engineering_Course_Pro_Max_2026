# 测验 · 综合项目：无状态工具生态系统（Capstone: Stateless Tool Ecosystem）

> **阶段 13 · 工具与协议 · 第 23 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 系统是一组边界 | 一个"研究并出报告"的请求背后至少有 8 份独立契约：工具 schema、无状态请求信封与发现、网关决策、长任务、委托、宿主到 App 的桥、追踪传播与导出、可复用流程 |
| 2 | 无状态 MCP（revision `2026-07-28`） | 去掉协议会话、`initialize` / `notifications/initialized` 握手和 `Mcp-Session-Id`；每个请求在 `params._meta` 里带协议版本、客户端能力与客户端身份 |
| 3 | 强制的 `server/discover` | 服务端必须实现；返回支持的版本、能力、服务端身份；本节还带 `ttlMs` 与 `cacheScope` 供缓存 |
| 4 | 结果类型 | 普通结果 `resultType: "complete"`；任务句柄 `resultType: "task"`；结果的 `_meta` 里标明 `io.modelcontextprotocol/serverInfo` |
| 5 | Tasks 扩展 | `io.modelcontextprotocol/tasks`，方法为 `tasks/get`、`tasks/update`、`tasks/cancel`；完成的 Task 自带最终结果，**没有** `tasks/result` 与 `tasks/list`；客户端必须在**同一请求**里声明该能力，否则返回 `-32021` + `requiredCapabilities` |
| 6 | 协议名称 | A2A v1 在 gRPC/JSON-RPC 中用 `SendMessage`，HTTP+JSON 用 `POST /message:send`；MCP App 调服务端工具用 `app.callServerTool({ name, arguments })` |
| 7 | 纵深防御 | OAuth（按需 PKCE）、令牌的资源/受众绑定、网关 RBAC、上游凭据不进模型上下文、固定（pinned）工具描述哈希、Rule of Two、宿主强制的执行沙箱；demo 只实现静态 token、scope 检查和描述哈希 |
| 8 | Skill 是流程不是传输 | Skill 能告诉运行时怎么做研究流程，但不能让 MCP server 存在、建立 A2A 兼容、授予 scope 或创建沙箱 |
| 9 | 课程元数据是本地适配器 | 平面文件 `skill-*.md` 的 `version`/`phase`/`lesson`/`tags` 是课程目录扩展，必须与 `name`/`description` 同层；嵌套进 `metadata` 会被课程的最小解析器跳过 |
| 10 | 模拟 vs 生产 | 一次本地"绿色运行"只验证模拟；每升级一层都需要跨越真实边界的集成证据（线上 transcript、接收端观测等） |

### 核心技能（能动手做到）

- [ ] 读懂 `request_meta` / `validate_request_meta`，说出 `-32602`、`-32022`、`-32021` 各在什么条件下返回
- [ ] 追踪 `generate_report` 从任务句柄到 `tasks/get` 完成结果的完整数据形状
- [ ] 解释网关 `gateway_call` 中各项检查的顺序，并指出哪些拒绝没有进审计日志
- [ ] 从 demo 打印的 span 列表重建两棵 trace 树，并和讲义"Target trace"对比找出缺失的 span
- [ ] 发现 `tasks_get` 不做身份校验、`orchestrator` 忽略用户请求等模拟中的缺口，并给出修复
- [ ] 把讲义"Simulation versus production"表格的每一行转化为一个具体的集成测试

---

## 二、基础自测（选择题）

**Q1.** MCP revision `2026-07-28` 相对旧版本**移除**的是：

- A. `tools/call` 方法
- B. `server/discover` 方法
- C. 协议会话：`initialize` / `notifications/initialized` 握手和 `Mcp-Session-Id`
- D. 请求中的 `params._meta`

**Q2.** Alice 用 `request_meta()`（**不带** tasks 扩展）调用 `gateway_call(..., "generate_report", ...)`，返回：

- A. `{"error": {"code": -32021, "message": "Missing required client capability", "data": {"requiredCapabilities": {"extensions": {"io.modelcontextprotocol/tasks": {}}}}}}`
- B. `{"error": {"code": -32022, ...}}`，提示协议版本不支持
- C. `{"error": "insufficient_scope", "scope": "research:write"}`
- D. 照常返回 `resultType: "task"` 的句柄，客户端以后再声明能力也可以

**Q3.** 在本节实现中，`tasks_get(task_id, request_meta(tasks=True))` 对一个已存在的任务返回的对象：

- A. `resultType: "task"`、`status: "working"`，需要再调 `tasks/result` 取结果
- B. 需要先调 `tasks/list` 才能找到该任务
- C. 只返回状态，最终结果要等服务器推送通知
- D. `resultType: "complete"`、`status: "completed"`，`result` 中含文本、`ui://report/current` 引用和 HTML

**Q4.** demo 两次运行 `orchestrator` 之后，审计日志 `AUDIT` 中关于 Bob 的记录是：

- A. 只有一条 `generate_report` 的 `403`
- B. `arxiv_search` 为 `allow`，`generate_report` 为 `403`
- C. 两条都是 `403`
- D. 没有 Bob 的记录，因为被拒绝的请求不审计

**Q5.** 一次 `python3 code/main.py` 的成功运行能证明什么？

- A. 进程内的策略与数据流按断言工作
- B. 一个真实的 MCP 传输完成了连接
- C. OAuth 授权服务器签发了有效 token
- D. collector 收到了全部 OpenTelemetry span

**Q6.** `gateway_call` 中各项检查的**实际执行顺序**是：

- A. token → scope → 协议元数据 → 工具是否存在 → 描述哈希
- B. 工具是否存在 → token → scope → 描述哈希 → 协议元数据
- C. 描述哈希 → 协议元数据 → token → scope → 工具是否存在
- D. 协议元数据 → token → scope → 工具是否存在 → 描述哈希

**Q7.** `pin_ok(tool_name, description)` 的作用最接近：

- A. 校验工具的参数 schema 没有变化
- B. 检测工具描述相对于固定清单（pinned manifest）是否被改动，防御描述被悄悄替换的元数据投毒
- C. 检查调用者 token 是否被篡改
- D. 校验工具返回内容的完整性

**Q8.** 讲义说课程的平面 skill 文件把 `version`、`tags` 等写在顶层。如果作者把它们嵌套到 `metadata:` 下面，会发生什么？

- A. 课程解析器自动把 `metadata` 当成 `tags` 使用
- B. 文件变成合法的便携目录 skill
- C. 课程的最小解析器只读顶层键，跳过缩进键：目录记录的 version 为空，`--tag capstone` 找不到它
- D. 安装器拒绝安装并给出明确错误

---

## 三、动手 / 代码题

**Q9.** 阅读下面两段代码，找出一个**授权缺陷**，给出攻击步骤与修复。

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

```python
    report = gateway_call(token, "generate_report",
                          {"format": "html"}, trace_id, root["spanId"],
                          request_meta(tasks=True))
    task = None
    if report.get("resultType") == "task":
        task = tasks_get(report["taskId"], request_meta(tasks=True))
```

**Q10.** `gateway_call` 的五种拒绝路径中，哪几种**没有写审计日志**？错误返回的形状有什么不一致？请重写网关，使每个决策都被审计、错误形状统一。

**Q11.** 下面是 demo 一次运行打印的 span（`parent` 是父 span id 的前 6 位）：

```text
  [a26e35] agent.invoke_agent   INTERNAL parent=ROOT
  [a26e35] llm.chat             CLIENT   parent=f3b654
  [a26e35] mcp.call             CLIENT   parent=f3b654
  [a26e35] mcp.call             CLIENT   parent=f3b654
  [a26e35] mcp.task.working     INTERNAL parent=8b2961
  [a26e35] a2a.SendMessage      CLIENT   parent=762321
  [a26e35] llm.chat             CLIENT   parent=f3b654
  [952918] agent.invoke_agent   INTERNAL parent=ROOT
  [952918] llm.chat             CLIENT   parent=8a62e4
  [952918] mcp.call             CLIENT   parent=8a62e4
  [952918] llm.chat             CLIENT   parent=8a62e4
```

1. 画出两棵 trace 树，说明 `8b2961`、`762321` 分别是谁的 span id。
2. 对照讲义的 Target trace，列出本实现**缺少**的 span。
3. Bob 的 trace 里为什么看不到被拒绝的 `generate_report`？这对排障有什么影响？

**Q12.** 用户问"summarize the three most-cited 2026 arXiv papers"，demo 输出：搜索结果只有 1 篇论文，报告却写着 "Report generated: 3 papers summarized." 并列出全部 3 篇。请定位造成这个数据流断裂的代码，并给出最小修改。

---

## 四、面试高频题

**Q13.**（基础必考）MCP 从"有会话"变成"无状态"后，客户端与服务端各要改什么？为什么每个请求都要带协议版本、能力与客户端身份？

**Q14.**（原理深挖）讲解 MCP Tasks 扩展的完整生命周期：谁决定返回任务句柄？客户端如何声明能力？结果怎么取？为什么能力要"每个请求都声明"而不是协商一次？

**Q15.**（工程实践）你接手这个模拟系统，要把它逐层升级到生产。请给出升级顺序，以及每一层"完成"的证据标准。

**Q16.**（场景设计）这个研究系统要读取外部论文（不可信输入）、访问公司内部知识库（敏感数据）、并能给外部合作方发邮件（有后果的动作）。按讲义的安全姿态，你会怎么设计？

**Q17.**（追问型）"本地所有 span 都共享同一个 trace id，所以我们的追踪是对的。"你会怎么反驳？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Revision `2026-07-28` removes protocol sessions and the `initialize` / `notifications/initialized` handshake. It also removes `Mcp-Session-Id`." A 错，`tools/call` 仍是调用工具的方法；B 恰恰相反，`server/discover` 变成**强制**实现；D 错，`_meta` 是新模型的核心——每个请求都靠它携带版本、能力与身份。

### Q2 — 答案：A

`gateway_call` 第一步就调用 `validate_request_meta(meta, require_tasks=tool_name == "generate_report")`。协议版本正确、能力对象存在，但 `extensions` 里没有 `io.modelcontextprotocol/tasks`，于是返回 `-32021`，`data.requiredCapabilities` 正是缺失的客户端能力对象（测试 `test_task_handle_requires_per_request_extension_capability` 断言了这个形状）。B 是协议版本不匹配时的错误；C 是 Bob（缺 write scope）才会得到的错误，而且元数据检查先于 scope 检查；D 违反讲义："A client must advertise `io.modelcontextprotocol/tasks` in the same request that may receive a task handle."

### Q3 — 答案：D

`research_generate_report` 先把一个**已完成**的任务记录存进 `TASKS`，再返回 `resultType: "task"`、`status: "working"` 的句柄；`tasks_get` 返回该记录的深拷贝：`resultType: "complete"`、`status: "completed"`，`result` 内含 `content`（文本 + `ui_resource`）、`ui`（`resourceUri`、`csp`、`permissions`）和 `html`。A、B 是讲义明确说"不属于当前扩展"的旧方法；C 不对，讲义："the completed `Task` contains the final result."

### Q4 — 答案：B

`orchestrator` 无条件先调 `arxiv_search`（需要 `research:read`，Bob 有）再调 `generate_report`（需要 `research:write`，Bob 没有）。实际 demo 输出的审计日志：

```text
{'user': 'alice', 'tool': 'arxiv_search', 'decision': 'allow'}
{'user': 'alice', 'tool': 'generate_report', 'decision': 'allow'}
{'user': 'bob', 'tool': 'arxiv_search', 'decision': 'allow'}
{'user': 'bob', 'tool': 'generate_report', 'decision': '403'}
```

D 错：scope 不足的拒绝**会**写审计（但其他拒绝路径不会，见 Q10）。

### Q5 — 答案：A

讲义："This table is the handoff boundary. A green local run validates the simulation only." demo 不打开传输、不做 OAuth、不导出遥测（文件 docstring 也明确写了"does not implement an MCP or A2A transport, OAuth exchange, MCP App bridge, telemetry exporter, or execution sandbox"）。B、C、D 都需要真实集成证据。

### Q6 — 答案：D

代码顺序：`validate_request_meta` → `USERS.get(token)`（未认证返回 `unauthenticated`）→ `REQUIRED_SCOPE` 检查（不足返回 `insufficient_scope` 并审计 403）→ 在 `TOOLS` 中查找工具（不存在返回 `unknown tool`）→ `pin_ok` 哈希比对 → 创建 span、分派、审计 allow。一个值得讨论的细节：scope 检查在"工具是否存在"之前，对于 `REQUIRED_SCOPE` 中没有的未知工具名，`required` 为 `None`，会直接跳过 scope 检查落到 `unknown tool`。

### Q7 — 答案：B

`PINNED` 在模块导入时对每个工具描述计算 SHA-256，`pin_ok` 把当前描述的哈希与之比较。实测：把 `arxiv_search` 的描述追加一句后，网关返回 `{'error': 'hash_mismatch'}`。这对应第 15 节的工具元数据投毒防御（描述在审核后被悄悄改写）。局限：本节的"清单"和"当前描述"来自同一个进程内的 `TOOLS`，真实部署中清单应来自审核过的独立来源，而被比对的描述来自服务端实时 `tools/list`。A 参数 schema 不在哈希范围内；C、D 与此无关。

### Q8 — 答案：C

讲义："If this flat file nests `version` or `tags` below `metadata`, the minimal parser skips those indented keys, the catalog records an empty version, and tag filtering cannot find the artifact." A 是臆测；B 错，平面文件不是目录包，不能携带 references/scripts/assets；D 错，问题恰恰是**静默**失效而不是明确报错。

### Q9 — 参考答案

**缺陷**：`tasks_get` 只校验协议元数据，**不经过网关、不校验调用者身份**，也没有把任务与创建者绑定。任何拿到 `taskId` 的人都能读到完整报告。

**攻击步骤**：Alice 生成报告得到 `tsk_xxxxxxxxxx`；该 id 出现在日志、URL 或被猜中（只有 10 个十六进制字符，约 40 bit）；Bob（甚至无 token 的调用者）直接调用 `tasks_get(task_id, request_meta(tasks=True))`。实测：不带任何 token 调用即可拿到 `status: completed` 和完整 `result`。

**修复要点**（已在临时脚本中运行验证）：

```python
TASK_OWNER: dict[str, str] = {}

# 网关创建任务成功后记录归属
if result.get("resultType") == "task":
    TASK_OWNER[result["taskId"]] = user["id"]

def tasks_get_v2(token, task_id, meta):
    user = USERS.get(token)
    if not user or TASK_OWNER.get(task_id) != user["id"]:
        return protocol_error(-32602, "Unknown taskId")   # 不区分"不存在"与"不是你的"
    return tasks_get(task_id, meta)
```

验证结果：Bob 读取 Alice 的任务得到 `Unknown taskId`，Alice 本人得到 `completed`。要点：

- 任务 id 不是授权凭证（它是"名字"不是"钥匙"），每次 `tasks/get`、`tasks/update`、`tasks/cancel` 都要重新做认证与授权；
- 对"不存在"和"无权访问"返回同样的错误，避免枚举；
- 生产中 task id 应使用足够长的随机值，并配合 `ttlMs` 过期清理（本节 `TASKS` 从不过期）。

### Q10 — 参考答案

五种拒绝路径与审计情况（已实测）：

| 拒绝原因 | 返回值 | 是否审计 |
|---|---|---|
| 协议元数据无效 | `{"error": {"code": ..., "message": ...}}` | 否 |
| 未认证 | `{"error": "unauthenticated"}` | 否 |
| scope 不足 | `{"error": "insufficient_scope", "scope": ...}` | **是**（`403`） |
| 未知工具 | `{"error": "unknown tool"}` | 否 |
| 描述哈希不匹配 | `{"error": "hash_mismatch"}` | 否 |

形状不一致：协议错误是 `{"error": {code, message, data}}` 的对象，网关错误是 `{"error": "<字符串>"}`；调用方必须写两套解析逻辑。且被拒的调用不产生任何 span（见 Q11）。

重写思路（已运行验证）：

```python
def audit(user, tool, decision, reason=""):
    AUDIT.append({"user": user, "tool": tool, "decision": decision, "reason": reason})

def gateway_call_v2(token, tool_name, args, trace_id, parent, meta):
    invalid = validate_request_meta(meta, require_tasks=tool_name == "generate_report")
    if invalid:
        audit(None, tool_name, "400", "invalid request meta"); return invalid
    user = USERS.get(token)
    if not user:
        audit(None, tool_name, "401", "unauthenticated")
        return protocol_error(-32001, "unauthenticated")
    tool = next((t for t in TOOLS if t["name"] == tool_name), None)
    if tool is None:
        audit(user["id"], tool_name, "404", "unknown tool")
        return protocol_error(-32602, "Unknown tool")
    required = REQUIRED_SCOPE[tool_name]
    if required not in user["scopes"]:
        audit(user["id"], tool_name, "403", f"missing {required}")
        return protocol_error(-32003, "insufficient_scope", {"scope": required})
    if not pin_ok(tool_name, tool["description"]):
        audit(user["id"], tool_name, "409", "description hash mismatch")
        return protocol_error(-32004, "hash_mismatch")
    ...  # 正常分派、span、audit allow
```

说明：`-32001/-32003/-32004` 只是示意用的应用自定义错误码；真实部署中认证/授权失败通常在 HTTP 层以 401/403 返回（第 16、18 节）。关键是：**每个决策都有审计记录、拒绝原因可机器读取、错误形状只有一种**；同时把"工具是否存在"挪到 scope 检查之前，使未知工具名不会绕过 scope 表。

### Q11 — 参考答案

1. 两棵树（由 `orchestrator` 两次调用产生）：

```text
trace a26e35 (Alice)
└─ agent.invoke_agent (f3b654)
   ├─ llm.chat
   ├─ mcp.call            ← arxiv_search
   ├─ mcp.call (8b2961)   ← generate_report
   │  └─ mcp.task.working (762321)
   │     └─ a2a.SendMessage
   └─ llm.chat

trace 952918 (Bob)
└─ agent.invoke_agent (8a62e4)
   ├─ llm.chat
   ├─ mcp.call            ← arxiv_search（generate_report 被拒，无 span）
   └─ llm.chat
```

   `8b2961` 是第二个 `mcp.call`（generate_report）的 span id——`research_generate_report(args, trace_id, sp["spanId"])` 把它作为父节点；`762321` 是 `mcp.task.working` 的 span id，`a2a.SendMessage` 以它为父。（span id 每次运行随机，前缀会变，结构不变。）
2. 对照讲义 Target trace，缺少：`server/discover`（demo 中 discover 在 orchestrator 之外调用，且根本不创建 span）、`tasks/get polling`、"completed Task with final result"、`ui://` 资源这几个节点；A2A 端的 "Opaque writer-agent execution" 当然也不存在（讲义要求的不透明边界只记录一个 span，这一点是符合的）。另外 LLM span 的模型名、token 数是硬编码的假数据。
3. 网关在 scope 检查失败时**先返回**，`span("mcp.call", ...)` 在所有检查通过之后才创建，所以拒绝只在 `AUDIT` 里留痕。排障时只看 trace 会以为 Bob 根本没尝试生成报告；生产中应为被拒绝的调用也创建 span，并设置错误状态和拒绝原因属性，同时与审计记录用同一个 trace id 关联。

### Q12 — 参考答案

断裂点有三处：

1. `orchestrator(token, user_query)` **完全没用 `user_query`**，搜索参数写死为 `{"query": "agent"}`；
2. `research_arxiv_search` 是对标题的大小写不敏感子串匹配，"agent" 只命中 `Agent-to-agent coordination benchmarks` 一篇（实测）；
3. `research_generate_report(args, ...)` **忽略 `args`**，HTML 遍历的是全局 `PAPERS` 全部 3 篇，文本 "3 papers summarized." 是硬编码字符串。

最小修改：

```python
# orchestrator
search = gateway_call(token, "arxiv_search", {"query": extract_keywords(user_query)}, ...)
hits = json.loads(search["content"][0]["text"]) if "content" in search else []
report = gateway_call(token, "generate_report", {"format": "html", "papers": hits}, ...)

# research_generate_report
papers = args.get("papers", [])
html = ... + "".join(f"<li>{p['arxiv_id']}: {p['title']}</li>" for p in papers) + ...
text = f"Report generated: {len(papers)} papers summarized."
```

其中 `extract_keywords` 在真实系统里由第一次 `llm.chat` 完成。这道题的教训：模拟可以简化每个边界，但**跨边界的数据要真的流过去**，否则 demo 会掩盖"检索结果没被用上"这种在生产中最常见的 bug。

### Q13 — 参考回答要点

- **改了什么**：没有 `initialize` 握手和会话 id；每个请求的 `params._meta` 都带 `io.modelcontextprotocol/protocolVersion`、`clientCapabilities`、`clientInfo`。服务端必须实现 `server/discover`，返回支持的版本、能力和 `serverInfo`；结果带 `resultType` 并在 `_meta` 中标明服务端身份。
- **客户端**：先 discover（可按 `ttlMs`/`cacheScope` 缓存），每个请求都组装完整的 `_meta`（本节的 `request_meta()`）。
- **服务端**：每个请求独立校验版本与能力（本节的 `validate_request_meta`），不依赖连接状态；版本不支持返回 `-32022` 并给出 `supported` 列表。
- **为什么**：请求自描述后，可以被任意实例处理、经过负载均衡与网关而不需要会话粘滞；网关也能在单个请求上做完整的策略判断；水平扩展、重试与故障转移更简单。
- 加分点：说出代价——每个请求的元数据开销更大；需要长期状态的场景（长任务）改由显式的 Tasks 扩展和持久化存储承担，而不是隐藏在连接里。

### Q14 — 参考回答要点

- **谁决定**：工具调用可以先返回 `resultType: "task"` 的句柄（含 `taskId`、`status`、`ttlMs`、`pollIntervalMs` 等）。
- **能力声明**：客户端必须在**可能收到任务句柄的那个请求里**声明 `extensions["io.modelcontextprotocol/tasks"]`；否则服务端返回 `-32021`，`requiredCapabilities` 精确指出缺什么。
- **取结果**：轮询 `tasks/get`（遵守 `pollIntervalMs`），它本身返回 `resultType: "complete"`；终态 Task 携带最终结果；`tasks/update` 用于补充输入，`tasks/cancel` 用于取消。没有 `tasks/result`、`tasks/list`。
- **为什么每请求声明**：无状态模型下不存在"一次协商、终身有效"的会话；每个请求可能落到不同实例、由不同版本的客户端发出，能力必须随请求携带才可判定。
- 加分点：持久化任务存储需要处理重启恢复、TTL 过期、取消的竞态；任务 id 必须与调用者授权绑定（Q9）。
- 常见误区：在新设计里继续使用 `tasks/result` / `tasks/list`，随包蓝图把它列为"硬拒绝"条件。

### Q15 — 参考回答要点

按讲义"Use It"逐层升级，**每一层都要有跨越新边界的集成测试，且不删除下层的策略测试**：

| 顺序 | 升级 | 完成证据 |
|---|---|---|
| 1 | 真实 `server/discover` + `tools/list`，每请求带版本/身份/能力 | 线上 transcript、确定性顺序、schema 校验 |
| 2 | 授权服务器 + 受保护资源校验 | issuer、audience、scope、过期与失败用例 |
| 3 | 网关策略绑定 actor、tool、target、tenant | allow 与 deny 的审计用例 |
| 4 | 持久化 Tasks 存储（get/update/cancel、TTL） | 状态迁移、输入、取消、重启恢复测试 |
| 5 | A2A 客户端解析 Agent Card 并发送消息 | 契约、超时、重试、不透明性测试 |
| 6 | 官方 SDK 构建 App，经 `app.callServerTool` 调工具 | CSP、权限、浏览器内工具调用测试 |
| 7 | OTel SDK 导出到测试 collector | 接收端断言 trace id 与父子关系 |
| 8 | 在第 26 节的沙箱契约内执行工具与脚本 | 逃逸、出网、密钥、资源上限测试 |
| 9 | 打包为完整目录 bundle，通过第 27 节发布门禁 | 评估与打包报告 |

- 加分点：每升级一层，就把本地 demo 中对应的"假数据"（硬编码 model、token 数、`3 papers`）替换为真实来源，并加回归测试。

### Q16 — 参考回答要点

- **Rule of Two**：讲义（及随包蓝图的"硬拒绝"）——不可信输入、敏感数据、有后果的动作，**不能在同一轮里三者同时出现**。设计上把流程拆开：
  - 读外部论文的环节不能访问内部知识库、不能发邮件，输出只作为数据；
  - 发邮件这一步需要人工审批，或由不接触不可信输入的独立组件执行。
- **授权**：OAuth + PKCE（视客户端类型）、令牌绑定资源与受众；网关 RBAC 精确到工具与 scope（本节 `REQUIRED_SCOPE` 的升级版）。
- **凭据**：上游 API 凭据只在网关/服务端，不进入模型可见上下文。
- **工具元数据**：固定描述哈希清单，变更需审核（本节 `PINNED`）。
- **执行隔离**：沙箱在 skill 之外强制文件系统、进程、网络、凭据、资源限制。
- **可观测**：每次 allow/deny 都审计并进入 trace（对比 Q10、Q11 的缺口）。
- 加分点：随包蓝图的拒绝规则——涉及支付必须有单独评审的授权协议与显式签字；若需求用一次直接的 LLM 调用就能满足，应拒绝搭建整套生态。

### Q17 — 参考回答要点

- 讲义："A shared trace identifier alone does not prove correct parentage, export, or backend ingestion."
- **父子关系**：同一 trace id 下，父 span id 必须正确；demo 里 Bob 被拒的调用根本没有 span，`server/discover`、`tasks/get` 也没有 span，树是不完整的。
- **跨进程传播**：真实系统要通过 propagator 把上下文带过 MCP、A2A 的网络跳；本地字典共享 id 不需要传播，因此证明不了传播逻辑。
- **导出与接收**：只有 collector/后端收到并能按父子关系重建，才算追踪成立；讲义要求"Export spans to a test collector and assert parentage at the receiver"。
- **语义约定**：span 名称与属性要遵循所选版本的 OpenTelemetry GenAI 语义约定，demo 中的 `mcp.call`、`a2a.peer` 等是示意名称。
- 加分点：还应检查错误状态（被拒或失败的调用要标记 error）与时间（demo 中 `finish` 强制 `end ≥ start + 1ns`，只保证正时长，不代表真实耗时）。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)、[阶段 13 · 08 构建 MCP 客户端：发现、路由与新旧协议兼容回退](../../08-building-an-mcp-client/docs/zh.md)：`server/discover` 与每请求 `_meta`。
- [阶段 13 · 13 MCP Tasks 扩展：在无状态核心上运行持久任务](../../13-mcp-async-tasks/docs/zh.md)：本节任务句柄与 `tasks/get` 的来源。
- [阶段 13 · 14 无状态协议上的 MCP Apps](../../14-mcp-apps/docs/zh.md)：`ui://` 资源与 `app.callServerTool`。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)、[阶段 13 · 16 MCP 授权：CIMD、签发者绑定、PKCE 与升级认证](../../16-mcp-security-oauth-2-1/docs/zh.md)、[阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：哈希固定、OAuth 与网关。
- [阶段 13 · 19 A2A：Agent 与 Agent 之间的通信协议](../../19-a2a-protocol/docs/zh.md)、[阶段 13 · 20 OpenTelemetry GenAI：端到端追踪 Tool Calls](../../20-opentelemetry-genai/docs/zh.md)：委托与追踪。
- [阶段 13 · 22 Agent Skills：可移植契约与运行时边界](../../22-skills-and-agent-sdks/docs/zh.md)：skill 是流程、不是传输。

### 本节被哪些后续内容用到
- [阶段 13 · 24 Skill Discovery 与 Progressive Disclosure](../../24-skill-discovery-and-progressive-disclosure/docs/zh.md)、[阶段 13 · 25 Skill Invocation 与路由](../../25-skill-invocation-and-routing/docs/zh.md)：把本节的平面蓝图升级为完整目录包的生命周期。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../26-skill-permissions-sandboxes-and-trust/docs/zh.md)：本节"Sandbox: None"一行的替代方案。
- [阶段 13 · 27 Skill 评估、打包与可移植性](../../27-skill-evals-packaging-and-portability/docs/zh.md)：发布门禁。
- [阶段 13 · 29 MCP 可靠性、取消与流量控制](../../29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)、[阶段 13 · 31 MCP 一致性工程：版本管理、证据与运维](../../31-mcp-conformance-versioning-and-operations/docs/zh.md)：超时、取消、版本与生产证据。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../../14-agent-engineering/23-otel-genai-conventions/docs/zh.md)、[阶段 14 · 27 Prompt Injection 与 PVE 防御](../../../14-agent-engineering/27-prompt-injection-defense/docs/zh.md)：追踪约定与 Rule of Two 背后的注入威胁。

### 延伸关键词
`stateless MCP` · `server/discover` · `params._meta` · `resultType` · `io.modelcontextprotocol/tasks` · `tasks/get / tasks/update / tasks/cancel` · `-32021 requiredCapabilities` · `A2A SendMessage` · `app.callServerTool` · `pinned description hash` · `Rule of Two` · `trace propagation` · `integration evidence`
