# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 13 节 MCP Tasks 扩展：在无状态核心上运行持久任务 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试 `python3 -m unittest discover tests -v` ｜ **依赖**：仅标准库（`json`、`tempfile`、`uuid`、`dataclasses`、`datetime`、`pathlib`、`typing`）；运行时在系统临时目录创建并自动删除任务文件

---

## 1. 这份代码在考察什么

这份代码实现了一个确定性的"任务服务"，用一个会暂停等待用户批准大纲的 `generate_report` 工具，把 Tasks 扩展的完整生命周期跑一遍：

1. **扩展协商**：客户端在每个请求的 `clientCapabilities.extensions` 中声明 `io.modelcontextprotocol/tasks`；未声明返回 `-32021`；`server/discover` 也在 `capabilities.extensions` 中广告它。
2. **服务端决定的任务创建**：`tools/call` 先把任务写进磁盘，再返回 `resultType: "task"`（durable-before-return）。
3. **重启恢复**：新建一个 `TaskService` 从磁盘重新加载，仍能 `tasks/get` 到同一个任务。
4. **任务内输入**：worker 把任务推进到 `input_required`，客户端通过 `tasks/get` 看到表单，用 `tasks/update` 回答。
5. **完成与内联结果**：任务完成后，`tasks/get` 在 `result` 中内联原 `CallToolResult`（带自己的 `resultType` 与 `serverInfo`）。
6. **协作取消、所有权、HTTP 头、订阅通知**：`tasks/cancel` 幂等；每个方法都检查所有者；`make_http_request` 让 `Mcp-Name` 镜像 `taskId`；通知辅助函数使用 `notifications/subscriptions/acknowledged` 与 `notifications/tasks`。

> 一句话：**协议保持无状态，但长任务的状态被显式地命名（task id）、持久化、授权和查询**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TASKS_EXTENSION` 等常量 | 字符串 | 扩展名与 `_meta` 键 | 扩展协商 |
| `TERMINAL_STATUSES` | 集合 | `completed`、`cancelled`、`failed` | 任务终态 |
| `TOOLS` | 列表 | `generate_report`，`size` 枚举，默认 `medium` | `tools/list` |
| `McpError` | dataclass 异常 | 结构化错误 | 错误码 |
| `request_meta` / `complete` / `validate_request_meta` | 函数 | 信封与校验 | 无状态核心 |
| `require_tasks_extension` | 函数 | 检查扩展声明，否则 `-32021` | 能力门 |
| `utc_now` | 函数 | 秒级 ISO 8601 UTC 时间，`Z` 结尾 | 时间戳 |
| `Task` | dataclass | 任务记录；`to_wire()` 按状态输出线格式 | 任务形状 |
| `TaskStore` | 类 | 目录中的 JSON 文件 + 内存字典；原子写入；重载 | 持久化 |
| `TaskService` | 类 | discover、tools/list、tools/call、tasks/get/update/cancel、worker、通知辅助、dispatch | 服务端 |
| `make_request` / `make_http_request` | 函数 | 构造 JSON-RPC 请求；构造 HTTP 头（`Mcp-Method`、`Mcp-Name`） | Streamable HTTP |
| `run_demo` / `main` | 函数 | 六步演示并打印摘要与一条任务通知 | 演示 |

数据流：`main()` 创建临时目录 → `run_demo`：discover(0) → `tools/call`(1) 创建并持久化 → **新建 TaskService（重载）** → `tasks/get`(2) working → `advance_worker` → `tasks/get`(3) input_required → `tasks/update`(4) 批准 → `advance_worker` → `tasks/get`(5) completed → 打印每步 `resultType`/`status` → 打印 `task_notification` → 退出时删除临时目录。

---

## 3. 逐段精讲

### 3.1 扩展能力检查

```python
def request_meta(*, tasks: bool = True) -> dict[str, Any]:
    extensions = {TASKS_EXTENSION: {}} if tasks else {}
    return {
        PROTOCOL_META: PROTOCOL_VERSION,
        CAPABILITIES_META: {"extensions": extensions},
        CLIENT_INFO_META: {"name": "lesson-client", "version": "1.0.0"},
    }

def require_tasks_extension(meta: dict[str, Any]) -> None:
    extensions = meta[CAPABILITIES_META].get("extensions")
    if not isinstance(extensions, dict) or TASKS_EXTENSION not in extensions:
        raise McpError(-32021, "missing required client capability",
                       {"requiredCapabilities": {"extensions": {TASKS_EXTENSION: {}}}})
```

- 扩展声明位于 `clientCapabilities.extensions`，键是完整的扩展名（带反向域名前缀，避免不同扩展重名）。
- `tools_call`、`tasks_get`、`tasks_update`、`tasks_cancel` 都会调用它——**每个请求**都要声明，讲义："A task response is unsolicited in the sense that the client does not request task mode. It is not unnegotiated: the current request still must advertise the extension."
- ⚠️ 本实现中，未声明扩展的客户端调用 `generate_report` 会直接得到 `-32021`（实测），没有同步执行的回退路径。讲义说"服务端决定是否创建任务"，因此另一种合法设计是：客户端不支持扩展时，服务端同步执行或返回一个说明性的工具错误。

### 3.2 时间戳

```python
def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
```

- `datetime.now(timezone.utc)` 得到带时区的当前时间；`.replace(microsecond=0)` 去掉微秒；`.isoformat()` 得到 `2026-10-12T17:06:14+00:00`，再把 `+00:00` 换成 `Z`。
- 秒级精度意味着同一秒内的多次更新 `lastUpdatedAt` 相同（实测演示中 `createdAt` 与 `lastUpdatedAt` 都是同一秒）。

### 3.3 `Task`：存储形状与线格式分离

```python
@dataclass
class Task:
    task_id: str
    owner: str
    operation: str
    status: str
    status_message: str
    created_at: str
    last_updated_at: str
    ttl_ms: int | None
    poll_interval_ms: int = 1_000
    stage: int = 0
    size: str = "medium"
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    input_requests: dict[str, Any] = field(default_factory=dict)
    issued_keys: list[str] = field(default_factory=list)
```

- 存储字段用 Python 风格的 `snake_case`，包含**不对外暴露**的内部字段：`owner`（所有者）、`operation`（原操作引用）、`stage`（worker 进度）、`size`（原参数）、`issued_keys`（所有发出过的输入键）。这与讲义"Persist at least the task id, status, timestamps, ttl, poll interval, original operation ownership, result or error, outstanding input requests, and all issued input keys"一一对应。
- `field(default_factory=dict)`：可变默认值必须用工厂函数，否则所有实例会共享同一个字典/列表。

```python
    def to_wire(self) -> dict[str, Any]:
        wire = {"taskId": ..., "status": ..., "statusMessage": ..., "createdAt": ...,
                "lastUpdatedAt": ..., "ttlMs": self.ttl_ms, "pollIntervalMs": ...}
        if self.status == "input_required":
            wire["inputRequests"] = self.input_requests
        elif self.status == "completed":
            wire["result"] = self.result
        elif self.status == "failed":
            wire["error"] = self.error
        return wire
```

- 线格式用协议的 `camelCase`，并且**只在对应状态下**才附带状态专属字段：`input_required` 带 `inputRequests`、`completed` 带 `result`、`failed` 带 `error`（讲义 "Status-specific fields appear only when relevant"）。
- 内部字段 `owner`、`stage`、`issued_keys` 不出现在线上——显式的 `to_wire` 比直接 `asdict` 安全。

### 3.4 `TaskStore`：原子写入的文件存储

```python
    def reload(self) -> None:
        self.tasks = {}
        for path in sorted(self.directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            task = Task(**data)
            self.tasks[task.task_id] = task

    def persist(self, task: Task) -> None:
        path = self.directory / f"{task.task_id}.json"
        temporary = self.directory / f"{task.task_id}.tmp"
        temporary.write_text(json.dumps(asdict(task), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
        self.tasks[task.task_id] = task
```

- **每个任务一个文件**，文件名就是服务端生成的 task id（不是用户输入，所以没有路径注入问题）。
- **原子写入**：先写 `.tmp`，再 `Path.replace`（同一文件系统上的 rename 是原子的）——读者要么看到旧版本，要么看到完整的新版本，不会读到半个 JSON。讲义："The lesson writes a temporary file and atomically renames it."
- `asdict(task)` 把 dataclass 递归转成字典；`Task(**data)` 反向重建——字段名必须一一对应（实测磁盘文件的键就是 15 个 snake_case 字段名）。
- `reload` 只读 `*.json`，残留的 `.tmp` 被忽略。
- ⚠️ 没有 `fsync`，断电时可能丢失最近的写入。
- ⚠️ **内存缓存问题**：`get` 只查 `self.tasks`，从不回读磁盘。两个实例共享目录时，后创建的任务对先构造的实例不可见；更严重的是陈旧实例写回会覆盖新状态（实测：陈旧实例 `advance_worker` 把已 `completed` 的任务改回 `input_required`）。详见测验 Q10。

```python
    def create(self, *, size: str, owner: str) -> Task:
        timestamp = utc_now()
        task = Task(task_id=f"tsk_{uuid.uuid4().hex[:12]}", owner=owner,
                    operation="tools/call:generate_report", status="working",
                    status_message="Preparing report outline.", created_at=timestamp,
                    last_updated_at=timestamp, ttl_ms=900_000, size=size)
        self.persist(task)
        return task
```

- task id：`tsk_` + UUID4 的前 12 个十六进制字符（48 位随机性）。id 不是权限凭证，安全性来自所有权检查。
- **先 `persist` 再返回**：这就是 durable-before-return。
- `ttl_ms=900_000`（15 分钟），但代码**从未检查过期**（讲义练习 5）。
- `save()` 在持久化前更新 `last_updated_at`。

### 3.5 `TaskService`：发现、列表与所有权

```python
    def _owned_task(self, task_id: Any, *, principal: str) -> Task:
        task = self.store.get(task_id)
        if task.owner != principal:
            raise McpError(-32602, "task not found")
        return task
```

- "不存在"和"不是你的"返回**同一个**错误消息，避免泄露别人任务的存在（测试 `test_task_owner_is_checked_on_every_lookup`）。讲义："Knowing a task id must not grant access."
- 只按 `principal` 检查，没有租户维度（讲义练习 2）。
- `server_discover` 广告 `{"tools": {}, "extensions": {TASKS_EXTENSION: {}}}`。
- ⚠️ `tools_list` 返回 `sorted(TOOLS, ...)` 但没有 `deepcopy`，调用方修改返回的描述符会污染全局 `TOOLS`（实测）——第 11 节对此做了防护，第 12、13 节没有。

### 3.6 `tools_call`：服务端决定创建任务

```python
        size = arguments.get("size", "medium")
        if size not in {"small", "medium", "large"}:
            raise McpError(-32602, "size must be small, medium, or large")

        task = self.store.create(size=size, owner=principal)
        return {"resultType": "task", **task.to_wire(), "_meta": _server_meta()}
```

- 参数校验在创建之前，非法参数是协议错误（`-32602`），不会产生任务。
- ⚠️ `size` 不先检查类型：传入列表时 `size not in {...}` 会因不可哈希抛 `TypeError`，`dispatch` 只捕获 `McpError`，异常冒出（实测 `TypeError: unhashable type: 'list'`）。
- 返回值不是用 `complete()` 包装，而是手工写 `resultType: "task"`——这就是 CreateTaskResult。
- 讲义提到"创建前需要输入就先走核心 MRTR，结束后再创建任务"，本工具没有创建前输入，所以直接创建。

### 3.7 `tasks_get`、`tasks_update`、`tasks_cancel`

```python
    def tasks_get(self, params, *, principal):
        meta = validate_request_meta(params)
        require_tasks_extension(meta)
        task = self._owned_task(params.get("taskId"), principal=principal)
        return complete(**task.to_wire())
```

- 用 `complete()` 包装：**外层 `resultType` 永远是 `complete`**，任务状态在 `status` 字段里。

`tasks_update` 的逻辑（节选见测验 Q11）：

- 只有任务处于 `input_required` 时才看 `approve_outline` 的回答；其他状态或未知键一律**静默忽略**并返回空确认（测试 `test_unknown_input_response_is_ignored`）。这符合讲义"servers ignore responses for unknown, superseded, or already fulfilled keys"。
- `decline` 或 `cancel` → 任务 `cancelled`（讲义允许，但要写进文档）。
- `accept` 且 `approved is True` → 状态回到 `working`、`stage = 2`、清空 `input_requests`，等待 worker 继续。
- ⚠️ `accept` + `approved: false` 什么也不做，任务一直停在 `input_required`（实测）。
- 返回 `complete()`：空确认。讲义："The state change may be eventually consistent, so the client continues polling or listening."

```python
    def tasks_cancel(self, params, *, principal):
        ...
        if task.status not in TERMINAL_STATUSES:
            task.status = "cancelled"
            task.status_message = "Cancellation was acknowledged by the worker."
            task.input_requests = {}
            self.store.save(task)
        return complete()
```

- 已是终态则不改，所以重复取消是**幂等**的（测试 `test_cancel_is_acknowledged_and_idempotent`）。
- 本实现"立刻生效"，但讲义强调生产中取消是协作式的，确认不代表 worker 已停止。

### 3.8 `advance_worker`：显式推进的状态机

```python
    def advance_worker(self, task_id: str) -> Task:
        task = self.store.get(task_id)
        if task.status != "working":
            return task
        if task.stage == 0:
            key = "approve_outline"
            if key in task.issued_keys:
                raise RuntimeError("task input request key cannot be reused")
            task.issued_keys.append(key)
            task.input_requests = {key: {"method": "elicitation/create", "params": {...form...}}}
            task.status = "input_required"
            task.status_message = "Waiting for outline approval."
            task.stage = 1
        elif task.stage == 2:
            task.status = "completed"
            task.status_message = "Report completed."
            task.stage = 3
            task.result = complete(content=[...], structuredContent={"size": task.size, "approved": True},
                                   isError=False)
        self.store.save(task)
        return task
```

阶段表：

| stage | status | 触发 | 下一步 |
|-------|--------|------|-------|
| 0 | working | `tools/call` 创建 | worker 发出表单 → stage 1 |
| 1 | input_required | worker | `tasks/update` 批准 → stage 2 |
| 2 | working | `tasks/update` | worker 生成结果 → stage 3 |
| 3 | completed | worker | 终态 |

- 只推进 `working` 状态的任务；`cancelled` 或 `input_required` 的任务调用它不会有变化（实测）。
- **输入键终身唯一**：发出前检查 `issued_keys`，复用就报错。
- 完成结果用 `complete(...)` 生成，因此嵌套的 CallToolResult 自带 `resultType: "complete"` 和 `serverInfo`——讲义："That nested discriminator is required."
- 讲义："The worker advances explicitly instead of sleeping in a background thread." 让每次状态转换都可预测、可测试，并把协议示例和队列机制分开。
- ⚠️ 没有任何路径会产生 `failed` 状态；worker 抛出的 `RuntimeError` 也不会被转换为任务失败。真实 worker 应把执行中的 JSON-RPC 错误写入 `task.error` 并置 `failed`。

### 3.9 订阅通知辅助函数

```python
    def subscription_acknowledgement(self, task_ids, *, subscription_id, principal="user-42"):
        accepted = [task_id for task_id in task_ids
                    if task_id in self.store.tasks and self.store.tasks[task_id].owner == principal]
        return {"jsonrpc": "2.0", "method": "notifications/subscriptions/acknowledged",
                "params": {"notifications": {"taskIds": accepted},
                           "_meta": {SUBSCRIPTION_ID_META: subscription_id}}}

    def task_notification(self, task_id, *, subscription_id, principal="user-42"):
        task = self._owned_task(task_id, principal=principal)
        return {"jsonrpc": "2.0", "method": "notifications/tasks",
                "params": {**task.to_wire(), "_meta": {SUBSCRIPTION_ID_META: subscription_id}}}
```

- 确认消息只包含调用者拥有的任务 id——不存在或属于别人的 id 被静默过滤，不泄露存在性。
- 任务通知的内容等价于此刻 `tasks/get` 的快照（讲义："Each task notification is otherwise equivalent to what `tasks/get` would return at that moment"），并带 subscription ID。
- 这两个函数只构造消息，不实现真正的 `subscriptions/listen` 方法与 SSE 流（讲义练习 4）。

### 3.10 `dispatch` 与 `make_http_request`

- `dispatch` 支持六个方法；`tasks/status`、`tasks/result`、`tasks/list` 落到 `else` 分支返回 `-32601`（测试 `test_removed_legacy_task_methods_are_not_found`）。通知（无 `id`）执行但不回响应。

```python
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
               "MCP-Protocol-Version": PROTOCOL_VERSION, "Mcp-Method": method}
    name: Any = None
    if method == "tools/call":
        name = body["params"].get("name")
    elif method in {"tasks/get", "tasks/update", "tasks/cancel"}:
        name = body["params"].get("taskId")
    if method == "tools/call" or method in {"tasks/get", "tasks/update", "tasks/cancel"}:
        if not isinstance(name, str) or not name:
            raise ValueError(f"{method} requires a name for Mcp-Name")
        headers["Mcp-Name"] = name
```

- `Accept` 同时接受 JSON 和 SSE：服务端可能直接回 JSON，也可能把响应升级为事件流。
- `Mcp-Method` 是方法名；`Mcp-Name` 对 `tools/call` 是工具名（实测 `generate_report`），对三个任务方法是 `taskId`。这些头让网关**不解析 JSON body** 就能路由（例如按 task id 找到所属后端）。
- 缺少名字时抛 `ValueError`——在客户端就拦住非法请求。

### 3.11 `run_demo` 与 `main`

- `run_demo` 里有一行 `service = TaskService(directory)`：用新实例替换旧实例，模拟重启。
- `main` 使用 `tempfile.TemporaryDirectory` 作为 `with` 上下文，演示结束自动删除任务文件，不在仓库里留下垃圾。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 每任务一个 JSON 文件 + 原子 rename | 零依赖、可直接查看、不会读到半个文件 | 无 `fsync`；不适合多副本；生产用事务数据库 |
| 先持久化再返回句柄 | durable-before-return | 最终一致存储还需等读可见 |
| 内存字典缓存任务 | 简单 | 多实例下读不到新任务、写回陈旧副本造成丢失更新；应每次读存储 + 版本号 |
| `to_wire` 显式映射 | 内部字段不外泄、状态专属字段按需出现 | 需手动维护映射 |
| worker 显式推进 | 确定性、可测试 | 不是真实队列；无租约、无失败路径 |
| 所有权失败与不存在同一错误 | 不泄露存在性 | 只有主体没有租户 |
| 未知/过时输入静默忽略 | 符合规范，容忍重复提交 | `approved: false` 也被"忽略"，任务卡住 |
| decline/cancel 都转 `cancelled` | 简单的终态 | 用户误关对话框也无法恢复，需在文档中说明 |
| 取消立即生效、幂等 | 演示清晰 | 生产中取消是协作式的 |
| `ttl_ms` 只存不查 | 代码短 | 任务永不过期（练习 5） |
| `tools_list` 不复制 | 省事 | 返回值可污染全局描述符 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 与默认值 | `class Task:`、`poll_interval_ms: int = 1_000` | 自动生成构造函数；有默认值的字段放在后面 |
| `field(default_factory=...)` | `input_requests: dict = field(default_factory=dict)` | 可变默认值的正确写法，每个实例一份 |
| `dataclasses.asdict` | `asdict(task)` | dataclass → 字典（递归） |
| `**` 解包构造对象 | `Task(**data)` | 字典的键作为关键字参数 |
| `pathlib.Path` | `self.directory / f"{task.task_id}.json"`、`.glob("*.json")`、`.read_text()`、`.write_text()`、`.replace()` | 面向对象的路径操作；`/` 拼接路径 |
| `mkdir(parents=True, exist_ok=True)` | `TaskStore.__init__` | 递归创建目录，已存在不报错 |
| `tempfile.TemporaryDirectory` + `with` | `main()` | 离开 `with` 时自动删除目录 |
| `uuid.uuid4().hex[:12]` | task id | 随机 UUID 的十六进制字符串取前 12 位 |
| `datetime` 时区 | `datetime.now(timezone.utc)` | 带时区的 UTC 时间 |
| 方法链 | `.replace(microsecond=0).isoformat().replace("+00:00", "Z")` | 前一个方法的返回值调用下一个方法 |
| `int \| None` 联合类型 | `ttl_ms: int \| None` | 可以为空 |
| 集合字面量与成员判断 | `TERMINAL_STATUSES = {...}`、`action in {"decline", "cancel"}` | O(1) 成员检查 |
| `elif` 分派链 | `dispatch` 中的方法分派 | 多分支选择 |
| 列表推导式带多条件 | `[task_id for task_id in task_ids if ... and ...]` | 过滤 |
| `enumerate(..., start=10)` | 测试中遍历旧方法名 | 从指定数字开始计数 |
| `setUp` / `tearDown` | 测试类中创建并清理临时目录 | 每个测试前后自动执行，保证测试互不影响 |
| 元组返回值 | `make_http_request` 返回 `(body, headers)` | 一次返回多个值 |
| `raise RuntimeError` | `advance_worker` 键复用 | 内部不变量被破坏时用普通异常 |
| f-string 带表达式 | `f"status={result.get('status', 'ack')}"` | 花括号里可以调用方法 |
| `if __name__ == "__main__":` | 文件末尾 | 被测试导入时不运行演示 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`：

```text
id=0 resultType=complete status=ack
id=1 resultType=task status=working
id=2 resultType=complete status=working
id=3 resultType=complete status=input_required
id=4 resultType=complete status=ack
id=5 resultType=complete status=completed
notification: {
  "jsonrpc": "2.0",
  "method": "notifications/tasks",
  "params": {
    "taskId": "tsk_c7de239cfc6e",              ← 每次运行随机
    "status": "completed",
    "statusMessage": "Report completed.",
    "createdAt": "2026-10-12T17:06:14Z",
    "lastUpdatedAt": "2026-10-12T17:06:14Z",   ← 同一秒内完成，秒级精度
    "ttlMs": 900000,
    "pollIntervalMs": 1000,
    "result": {
      "resultType": "complete",                 ← 嵌套 CallToolResult 的判别字段
      "content": [{"type": "text", "text": "Generated large report with approved outline."}],
      "structuredContent": {"size": "large", "approved": true},
      "isError": false,
      "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "tasks-demo", "version": "1.0.0"}}
    },
    "_meta": {"io.modelcontextprotocol/subscriptionId": "listen-demo"}
  }
}
```

逐项解读：

- 六行摘要与讲义 "Expected result sequence" **完全一致**。`status=ack` 是 `main()` 打印的占位词：discover 与 `tasks/update` 的结果里没有 `status` 字段。
- **id=1** 是唯一一个 `resultType=task` 的响应：只有 `tools/call` 返回 CreateTaskResult。
- **id=2** 来自新建的 `TaskService` 实例，证明重启后仍能查到任务。
- **id=3 → id=5**：worker 两次显式推进，中间由 `tasks/update` 批准。
- **通知**：内容就是任务快照加 subscription ID；`subscriptionId` 用字符串 `"listen-demo"`，说明 JSON-RPC id 可以是字符串。
- 通知的 `_meta` 只有 subscription ID，没有 `serverInfo`；而 `tasks/get` 的响应带 `serverInfo`——两者的 `_meta` 用途不同。

---

## 7. 动手改一改

1. **（入门）** 在 `tools_list` 中加 `copy.deepcopy`，在 `tools_call` 中先检查 `isinstance(size, str)`；各补一个测试。
2. **（讲义练习 2）** 给 `Task` 增加 `tenant` 字段，`dispatch` 增加 `tenant` 参数；`_owned_task` 同时比对租户与主体；写测试：另一个租户拿着合法 task id 得到 `task not found`。
3. **（讲义练习 1）** 增加第二个输入键 `choose_format`，实现"部分更新后仍为 `input_required`、两键都回答才继续"，并让已回答的键再次提交时被忽略（参考测验 Q11）。
4. **（讲义练习 5）** 在 `tasks_get` 中按 `created_at + ttl_ms` 判断过期：未终结的过期任务置为 `failed`（`error` 为 JSON-RPC 错误对象）；加一个清理函数删除过期文件；确认跨租户查询仍只看到 `task not found`。
5. **（讲义练习 3）** 修复多实例问题：`TaskStore.get` 每次从磁盘读；`Task` 增加 `version`，`persist` 前检查磁盘上的版本未变（不符则抛冲突）；再加 `lease_owner`/`lease_expires_at`，写测试证明两个实例不能同时完成同一个任务，并复现测验 Q10 中的丢失更新已被阻止。
6. **（讲义练习 4，进阶）** 用 `http.server` 写一个最小的 POST 端点：`subscriptions/listen` 的响应以 `text/event-stream` 返回，先发确认，再在任务状态变化时发 `notifications/tasks`；不要实现 GET 事件流、`Last-Event-ID` 或会话头。

---

## 8. 常见坑

- **把外层 `resultType` 当任务状态**：`tasks/get` 的 `resultType` 永远是 `complete`，任务进度看 `status`。
- **先返回句柄再写库**：客户端立即 `tasks/get` 会得到 not found。
- **任务只存在进程内存**：重启或换副本就丢；本节的内存缓存在多实例下会读到陈旧数据并覆盖新状态。
- **以为知道 task id 就能访问**：每个方法、每个订阅都要检查所有权，且不存在与无权返回同一错误。
- **用 `tasks/result`、`tasks/list`、`tasks/status`**：已移除；结果内联在 `tasks/get` 中。
- **任务内输入去重试原 `tools/call`**：创建后应使用 `tasks/update`。
- **复用 `inputRequests` 键**：迟到的回答会被误用到新问题上。
- **把 `tasks/cancel` 的确认当作已停止**：取消是协作式的，继续观察状态。
- **用 `notifications/cancelled` 取消任务**：它只取消进行中的请求。
- **把 `ttlMs` 当成完成后的保留时长**：它从创建起算。
- **把 `isError: true` 的工具结果标成 `failed`**：那是 `completed`；只有 JSON-RPC 错误才是 `failed`。
- **`Mcp-Name` 写成方法名**：任务方法上它镜像 `params.taskId`。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m unittest discover tests -v`。实际结果：**Ran 17 tests ... OK**。

测试按路径加载 `main.py`（模块名 `lesson13_main`）；`setUp` 为每个测试创建独立的临时目录与 `TaskService`，`tearDown` 清理目录。辅助方法 `create_task(tasks=...)` 发起一次 `generate_report(size=large)`。

| 测试 | 验证的性质 |
|------|-----------|
| `test_discovery_advertises_tasks_extension` | discover 为 `complete`、版本正确、`capabilities.extensions` 含 Tasks 扩展 |
| `test_tools_list_is_deterministic_cacheable_and_described` | `ttlMs=60000`、`public`、含 serverInfo、排序、`size` 枚举正确 |
| `test_server_directed_creation_returns_task_result` | 请求 `_meta` 中**没有** `task` 标志，响应仍为 `resultType: task`、`working` |
| `test_missing_extension_capability_is_rejected` | 未声明扩展 → `-32021` 与精确 `data` |
| `test_task_is_durable_before_handle_is_returned` | 创建后新建 `TaskService` 仍能 `tasks/get` 到 `working` 的任务 |
| `test_task_owner_is_checked_on_every_lookup` | 其他主体查询 → `-32602 task not found` |
| `test_tasks_get_uses_complete_discriminator` | `tasks/get` 的外层 `resultType` 为 `complete` |
| `test_input_required_is_fulfilled_through_tasks_update` | worker 推进后为 `input_required` 且含 `approve_outline`；`tasks/update` 返回**恰好** `{"resultType": "complete", "_meta": ...}`；任务回到 `working` |
| `test_completed_task_inlines_original_tool_result` | 完成后 `result.resultType == complete`、`isError` 为假、嵌套 `_meta` 为 serverInfo、`size == large` |
| `test_http_task_methods_mirror_task_id_as_mcp_name` | 三个任务方法的 `Mcp-Method` 为方法名、`Mcp-Name` 为 task id |
| `test_unknown_input_response_is_ignored` | 未知键的回答返回确认，任务仍为 `input_required` |
| `test_cancel_is_acknowledged_and_idempotent` | 连续两次取消都返回 `complete`，最终 `cancelled` |
| `test_removed_legacy_task_methods_are_not_found` | `tasks/status`、`tasks/result`、`tasks/list` → `-32601` |
| `test_notification_helpers_use_current_methods` | 确认与任务通知的方法名正确，都带同一个 subscription ID |
| `test_unsupported_protocol_version_is_rejected` | `2025-11-25` → `-32022` 与精确 `data` |
| `test_non_string_protocol_version_is_invalid_params` | 版本为 `None` → `-32602` |
| `test_notification_never_receives_a_json_rpc_response` | 无 `id` 的 `tasks/get` 返回 `None` |

测试盲区：

- 只测了"重启后新实例能读到"，**没有测两个并存实例**——这正是内存缓存出问题的地方（测验 Q10）。
- 没有测 `decline`/`cancel` 回答、`approved: false`、取消后再推进 worker、过期、`failed` 状态。
- 没有测 `subscription_acknowledgement` 过滤掉他人任务或不存在的 id。
- 没有测 `tools/call` 的 `Mcp-Name`（实测为工具名）以及缺少 `taskId` 时 `make_http_request` 抛 `ValueError`。
