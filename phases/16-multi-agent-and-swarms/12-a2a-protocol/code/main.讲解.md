# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 12 节 A2A：Agent 与 Agent 之间的通信协议 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数；会在本机 `localhost:8765` 启动一个临时 HTTP 服务，约 0.5 秒结束） ｜ **依赖**：仅标准库（`http.server`、`urllib.request`、`json`、`threading`、`uuid`），无需外网

---

## 1. 这份代码在考察什么

脚本在同一个进程里起了一个"A2A 风格"的 HTTP 服务端（后台线程），再用客户端走完整个流程：

1. **发现（discovery）**：`GET /.well-known/agent.json` 读取 Agent Card，得到技能列表和任务端点。
2. **提交（submit）**：`POST /tasks` 提交一个 `review-python` 任务，立即得到 `task_id`（异步任务模型）。
3. **轮询（poll）**：`GET /tasks/{id}` 观察状态从 `working` 变到 `completed`。
4. **取结果（artifact）**：读取类型化的 artifact `{"type": "structured", "data": {...}}`。

对应讲义的四要素：Agent Card、Task、Artifact、不透明生命周期（客户端看不到服务端怎么"审查代码"，只看到状态和结果）。

> 一句话：**用标准库的 HTTP 服务器把"发现 → 提交 → 轮询 → 取 artifact"这条 A2A 主线跑通**。需要注意它是讲义所说的"A2A-minimal"：用自定义 REST 路由代替规范的 JSON-RPC 绑定，没有鉴权、幂等、取消、`input-required`、SSE，也不校验输入。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `AGENT_CARD` | 模块级字典 | 名称、版本、技能、端点、鉴权、模态、协议版本 | Agent Card |
| `TaskStore` | 类 | 内存任务表 + 锁；`create` 建任务并起后台线程；`_run` 执行；`get` 查询 | Task 与生命周期 |
| `STORE` | 全局实例 | 服务端唯一的任务存储 | — |
| `A2AHandler` | `BaseHTTPRequestHandler` 子类 | `do_GET` 返回卡片/任务，`do_POST` 创建任务，`_send_json` 统一输出 | 传输层 |
| `run_server` | 函数 | 在 `localhost:8765` 启动 `HTTPServer`，后台线程 `serve_forever` | 服务端 |
| `http_json` | 函数 | 用 `urllib.request` 发送 JSON 请求并解析响应 | 客户端传输 |
| `run_client` | 函数 | 发现 → 提交 → 最多 10 次轮询 → 打印 artifact | A2A 客户端 |
| `main` | 函数 | 启动服务、运行客户端、`finally` 中关闭服务 | 演示入口 |

数据流：客户端 `GET` 卡片 → 从 `card["endpoints"]["tasks"]` 取到提交地址 → `POST` → `STORE.create` 写入 `submitted` 并启动 `_run` 线程 → `_run` 改为 `working`，`sleep(0.2)` 后写入 artifact 与 `completed` → 客户端每 0.1s `GET` 一次直到终态。

---

## 3. 逐段精讲

### 3.1 Agent Card

```python
AGENT_CARD = {
    "name": "code-review-agent",
    "version": "0.1.0",
    "skills": ["review-python"],
    "endpoints": {
        "tasks": "http://localhost:8765/tasks",
    },
    "auth": {"type": "none"},
    "modalities": ["text", "structured"],
    "protocol_version": "a2a-0.3",
}
```

- 与讲义示例字段一致，并多了 `version`（agent 自身版本）和 `protocol_version`（对应 Ship It 的 "Pin the spec version"）。
- `endpoints.tasks` 让客户端**从卡片里**得知提交地址，而不是硬编码——这就是"自描述"。
- `auth: none` 只适合本机演示；`skill-a2a-integrator` 把"公网部署 auth=none"列为 hard reject。
- 与规范的差距：规范中的技能是带 id、名称、描述、输入/输出模态的**对象**，卡片还会声明 capabilities（如是否支持 streaming、push notifications）与安全方案（参见阶段 13 · 19）。

### 3.2 `TaskStore`：任务与生命周期

```python
    def create(self, skill: str, payload: dict) -> str:
        tid = str(uuid4())[:8]
        with self._lock:
            self.tasks[tid] = {
                "id": tid,
                "skill": skill,
                "payload": payload,
                "state": "submitted",
                "artifact": None,
                "created_at": time.time(),
            }
        threading.Thread(target=self._run, args=(tid,), daemon=True).start()
        return tid
```

- 每个任务是一个字典，初始状态 `submitted`、artifact 为空。
- 创建后**立即**起一个守护线程执行任务，`create` 不等待结果直接返回——这就是 A2A "异步任务"的核心：提交和完成解耦。
- `str(uuid4())[:8]`：截取 UUID 前 8 个十六进制字符（32 位随机性），演示时可读性好；生产应使用完整 UUID（约 6.5 万个任务时碰撞概率就接近 39%）。
- ⚠️ 没有幂等：同一请求提交两次会产生两个任务（已验证）。测验 Q10 给出了基于 `Idempotency-Key` 的改法。

```python
    def _run(self, tid: str) -> None:
        with self._lock:
            self.tasks[tid]["state"] = "working"
        time.sleep(0.2)
        with self._lock:
            t = self.tasks[tid]
            if t["skill"] == "review-python":
                code = t["payload"].get("code", "")
                issues = []
                if "return" not in code:
                    issues.append("no return statement")
                if "def " not in code:
                    issues.append("no function definition")
                t["artifact"] = {
                    "type": "structured",
                    "data": {"issues": issues, "lines": code.count("\n") + 1},
                }
                t["state"] = "completed"
            else:
                t["state"] = "failed"
                t["artifact"] = {"type": "text", "data": f"unknown skill '{t['skill']}'"}
```

- 状态机：`submitted → working → completed | failed`。讲义还列了 `canceled`，代码没有取消接口。
- `time.sleep(0.2)` 放在锁外：模拟耗时工作时不占锁，查询请求可以同时读取状态。
- "审查"逻辑与第 08 节的 critic 一样只是关键字检查——这正是"不透明"的体现：客户端不关心、也看不到它内部如何实现。
- artifact 带 `type` 字段区分模态（`structured` / `text`）。失败时也返回一个 text artifact 说明原因，相当于"错误 artifact"。
- ⚠️ `lines` 计算有差一错误：`"x = 1\nprint(x)\n"` 只有 2 行，`count("\n") + 1` 得 3；应使用 `len(code.splitlines())`。
- ⚠️ 未知技能在提交时不校验，而是到后台才 `failed`。

```python
    def get(self, tid: str) -> dict | None:
        with self._lock:
            return self.tasks.get(tid)
```

- ⚠️ 返回的是字典**引用**。handler 在锁外 `json.dumps` 它，而后台线程可能同时在改它，可能序列化出"state=working 但 artifact 已有值"这类不一致快照。应在锁内 `copy.deepcopy` 后返回（测验 Q9）。

### 3.3 `A2AHandler`：HTTP 路由

```python
class A2AHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: int, body: Any) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
```

- `BaseHTTPRequestHandler` 的约定：对每个请求实例化一次 handler，按方法名调用 `do_GET` / `do_POST`。
- 覆盖 `log_message` 并直接 `return`：关闭默认的每请求访问日志，让演示输出干净。生产中恰恰需要这些日志（以及 trace ID）。
- `_send_json` 先 `send_response` → `send_header` → `end_headers` → 写 body，顺序不能乱；`Content-Length` 用**字节数** `len(data)` 而不是字符数。

```python
    def do_GET(self) -> None:
        if self.path == "/.well-known/agent.json":
            self._send_json(200, AGENT_CARD)
            return
        if self.path.startswith("/tasks/"):
            tid = self.path.split("/tasks/", 1)[1]
            task = STORE.get(tid)
            if task is None:
                self._send_json(404, {"error": "not found"})
                return
            self._send_json(200, task)
            return
        self._send_json(404, {"error": "route not found"})

    def do_POST(self) -> None:
        if self.path == "/tasks":
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            tid = STORE.create(body.get("skill", ""), body.get("payload", {}))
            self._send_json(201, {"task_id": tid, "state": "submitted"})
            return
        self._send_json(404, {"error": "route not found"})
```

- 手写路由：精确匹配卡片路径、前缀匹配 `/tasks/`。`split("/tasks/", 1)[1]` 取出 ID；若路径带查询串（`?x=1`）会被当成 ID 的一部分。
- `GET /tasks/{id}` 返回整个任务字典，包括调用方的 `payload`——没有鉴权时，任何知道 ID 的人都能读到别人的输入。
- `POST` 成功返回 **201 Created**，响应里的 `"submitted"` 是写死的字面量。
- ⚠️ 没有输入校验：非法 JSON 会让 handler 抛 `JSONDecodeError`，服务器打印异常并关闭连接，客户端得到 `RemoteDisconnected`（已验证）；应返回 400。
- ⚠️ 没有鉴权、限流、幂等键处理。

### 3.4 服务端启动与客户端

```python
def run_server() -> HTTPServer:
    server = HTTPServer(("localhost", 8765), A2AHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
```

- `HTTPServer` 是**单线程**的：一次处理一个请求。本例请求都很短，没问题；但如果加 SSE 长连接，一个订阅者就会阻塞其他所有请求，需要 `ThreadingHTTPServer` 或异步框架。
- 端口写死 8765：若被占用会抛 `OSError: [Errno 98] Address already in use`。
- `daemon=True`：主线程结束时后台线程不会阻止进程退出。

```python
def http_json(method: str, url: str, body: Any = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))
```

- 只用标准库的 HTTP 客户端。注意 `urlopen` 遇到 4xx/5xx 会抛 `HTTPError`，本函数没有处理——查询不存在的任务时客户端会直接异常。

```python
    resp = http_json("POST", card["endpoints"]["tasks"], submission)
    tid = resp["task_id"]
    ...
    for i in range(10):
        task = http_json("GET", f"http://localhost:8765/tasks/{tid}")
        print(f"    attempt {i + 1}: state={task['state']}")
        if task["state"] in ("completed", "failed"):
            print(f"    artifact: {task['artifact']}")
            break
        time.sleep(0.1)
```

- 提交地址取自 Agent Card，但轮询地址却是**硬编码**的 `http://localhost:8765/tasks/{tid}`——前后不一致；应从卡片的端点拼出来。
- 固定 0.1s 间隔、最多 10 次（约 1 秒预算）；超时后既不报错也不取消，循环静默结束。生产中应使用指数退避、总超时，并在超时后调用取消接口。
- 终态只判断 `completed` 和 `failed`，没有 `canceled`。

### 3.5 `main`

```python
    server = run_server()
    time.sleep(0.1)
    try:
        run_client()
    finally:
        server.shutdown()
```

- `time.sleep(0.1)` 粗略等待服务器就绪（更稳妥的做法是重试连接）。
- `try/finally` 保证即使客户端出错也会关闭服务器。`shutdown()` 停止 `serve_forever` 循环，但没有调用 `server_close()` 释放监听套接字；进程随即退出，所以无碍。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 自定义 REST 路由 | 直观展示"发现—提交—轮询"四步 | 规范使用 JSON-RPC 2.0 绑定（另有 gRPC），消息由 text/file/data Part 组成 |
| 服务端与客户端同进程 | 一条命令跑完整流程 | 讲义自己也说同进程用 A2A 是过度设计；这里只为演示 |
| 内存字典 + 锁存任务 | 零依赖 | 重启即丢；生产用数据库或持久化队列，配合死信队列 |
| 每任务一个后台线程 | 体现异步提交 | 无并发上限；生产用工作队列 / worker 池并限流 |
| 轮询而不是 SSE | 实现最简单 | 延迟与请求开销高；长任务应提供 SSE 或 webhook 推送 |
| `auth: none` | 本机演示 | 公网必须 bearer / mTLS / 签名请求 |
| 不校验 JSON 与技能 | 代码短 | 非法输入导致连接中断、未知技能异步失败；应同步返回 400 |
| 无幂等、无取消 | 聚焦主线 | 网络重试产生重复任务；无法止损长任务 |
| 截断的 8 位任务 ID | 输出可读 | 碰撞概率高、易被枚举；用完整 UUID 并加鉴权 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许在注解里写 `dict | None`（3.10 前的版本也能用） |
| `X | None` 联合类型 | `def get(self, tid: str) -> dict | None:` | 返回字典或 `None` |
| `typing.Any` | `body: Any` | 任意类型 |
| 类与 `__init__` | `class TaskStore:` | 封装状态（任务表）和行为（create/get） |
| 单下划线私有约定 | `self._lock`、`def _run` | 表示"内部使用"，不是强制私有 |
| `threading.Lock` + `with` | `with self._lock:` | 进入加锁，离开自动释放 |
| `threading.Thread(daemon=True)` | 后台执行任务、运行服务器 | 守护线程不会阻止进程退出 |
| `uuid4()` | `str(uuid4())[:8]` | 生成随机 UUID 并截取前 8 位 |
| 继承与方法覆盖 | `class A2AHandler(BaseHTTPRequestHandler)`、`def log_message(...)` | 通过覆盖 `do_GET`/`do_POST` 处理请求 |
| `*args` | `def log_message(self, format: str, *args: Any)` | 接收任意数量的位置参数（这里直接忽略） |
| `json.dumps` / `json.loads` | `json.dumps(body).encode("utf-8")` | Python 对象 ↔ JSON 字符串；再 encode 成字节 |
| `str.encode` / `bytes.decode` | `.encode("utf-8")`、`.decode("utf-8")` | 字符串与字节互转，网络传输用字节 |
| `str.startswith` / `split(sep, 1)` | `self.path.split("/tasks/", 1)[1]` | 前缀判断；最多切一次取后半部分 |
| `dict.get(key, default)` | `body.get("payload", {})`、`self.headers.get("Content-Length", "0")` | 缺键时给默认值 |
| `urllib.request.Request` + `urlopen` | `http_json` | 标准库 HTTP 客户端；`with` 自动关闭响应 |
| 条件表达式 | `json.dumps(body).encode(...) if body is not None else None` | GET 请求不带 body |
| `in` 元组判断 | `task["state"] in ("completed", "failed")` | 是否为终态 |
| `try / finally` | `main` 中关闭服务器 | 无论成败都执行清理 |
| f-string 嵌套引号 | `f"unknown skill '{t['skill']}'"` | 外层双引号、内层单引号 |
| `"-" * 30` | 打印分隔线 | 字符串重复 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`；task_id 每次随机）：

```text
A2A minimal protocol demo
------------------------------

[1] discovery: GET /.well-known/agent.json
    name=code-review-agent, skills=['review-python']

[2] submit task: POST /tasks
    task_id=a2ff7676, state=submitted

[3] poll until completed
    attempt 1: state=working
    attempt 2: state=working
    attempt 3: state=completed
    artifact: {'type': 'structured', 'data': {'issues': ['no return statement', 'no function definition'], 'lines': 3}}

Key insight: discovery + task lifecycle + typed artifact + auth is the A2A surface.
MCP is agent <-> tool (vertical); A2A is agent <-> agent (horizontal). Production uses both.
```

逐项解读：

- **[1] 发现**：客户端只知道服务器地址，通过卡片得知名字、技能，以及任务端点。
- **[2] 提交**：立刻拿到 `task_id`，`state=submitted` 是 POST 响应写死的值。
- **[3] 轮询**：第 1 次 GET 已是 `working`（后台线程在 `create` 返回前就开始运行了）；任务耗时 0.2s、轮询间隔 0.1s，所以第 3 次看到 `completed`。偶尔因线程调度差异，也可能在第 2 或第 4 次看到。
- **artifact**：被审查的代码是 `x = 1\nprint(x)\n`，既没有 `return` 也没有 `def `，所以两条 issue；`lines: 3` 是差一错误，实际 2 行。
- **结尾两行**：讲义的核心总结。注意本演示其实没有实现 "auth" 这一项（`auth: none`）。

额外验证（在另一个端口上运行同一个 handler）：

| 请求 | 结果 |
|------|------|
| 提交未知技能 `summarize` | `201`，随后任务 `failed`，artifact 为 `unknown skill 'summarize'` |
| 相同请求提交两次 | 产生两个不同的 task_id |
| `GET /tasks/nope` | `404 {"error": "not found"}` |
| `POST` 非法 JSON | 服务端抛异常，客户端 `RemoteDisconnected` |

---

## 7. 动手改一改

1. **讲义练习 1**：运行脚本，再把轮询间隔改为 0.05s、任务耗时改为 0.5s，观察轮询次数变化；把轮询 URL 改成从 Agent Card 推导。
2. **讲义练习 2**：新增 `summarize` 技能——更新 `AGENT_CARD["skills"]`、在 `_run` 中加分支、在 `do_POST` 中校验技能并对未知技能返回 400；客户端写 `pick_skill(card, task_type)` 按任务类型选技能（参考测验 Q11）。
3. **健壮性**：`do_POST` 捕获 `JSONDecodeError` 返回 400；`get` 在锁内返回 `copy.deepcopy`；`lines` 改用 `splitlines()`。
4. **幂等与取消**：支持 `Idempotency-Key` 请求头（重复请求返回同一 task_id，状态码 200）；增加 `POST /tasks/{id}/cancel`，`_run` 在工作中检查取消标志并转为 `canceled`（参考测验 Q10）。
5. **讲义练习 3**：把服务器换成 `ThreadingHTTPServer`，实现 `GET /tasks/{id}/events` 的 SSE 推送（`Content-Type: text/event-stream`，每次状态变化写一行 `data: {...}\n\n`），客户端逐行读取直到终态。
6. **进阶（讲义练习 4）**：对照 A2A 规范或阶段 13 · 19，把接口改成 JSON-RPC 风格（单一 `/a2a` 端点，按 `method` 分发），任务输入改为带 text/data Part 的消息，并加入 `input-required` 状态：当 `payload` 缺少 `code` 时暂停，等待客户端补发消息后继续。

---

## 8. 常见坑

- **把 POST 响应里的状态当成真实状态**：任务是异步的，状态要以 GET（或事件流）为准。
- **锁内取引用、锁外序列化**：可能读到不一致的快照；跨出锁边界时返回副本。
- **不校验输入**：非法 JSON 让连接直接断开，未知技能变成异步失败；能同步发现的错误就同步返回 4xx。
- **没有幂等键**：客户端超时重试会产生重复任务，在有副作用的技能上尤其危险。
- **单线程 HTTPServer 上做长连接**：SSE 会阻塞所有其他请求。
- **硬编码地址**：既然有 Agent Card，就应从卡片中读取端点，否则对方迁移地址时集成会断。
- **轮询无退避、无总超时、无取消**：浪费请求，超时后任务仍在对端运行。
- **把演示当规范**：真实 A2A 使用 JSON-RPC/gRPC 绑定、Message/Part 结构、更完整的状态机与安全方案；接入前以官方规范为准。
- **公网使用 `auth: none`**：任何人都能提交任务、读取他人的 payload。
