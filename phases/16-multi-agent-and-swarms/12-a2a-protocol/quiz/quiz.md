# 测验 · A2A：Agent 与 Agent 之间的通信协议（A2A — The Agent-to-Agent Protocol）

> **阶段 16 · 多智能体与集群 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 提示：①中文讲义为机器翻译，把 Agent Card 译成"纸牌"、artifact 译成"人工制品"、"Lesson 13" 译成"教训13"，请对照英文版。②讲义中的 "MCP (Lesson 13)" 指的是**阶段 13**（工具与协议）的 MCP 系列，而不是本阶段第 13 节（共享记忆）。③本节讲义和代码采用的是"简化的 REST 风格"演示；阶段 13 · 19 对 A2A 有更贴近规范的讲解（JSON-RPC 绑定、Message/Part、`input-required` 状态等），两者可对照阅读。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | A2A 解决什么问题 | 跨系统的 agent 调用不再是"每一对 agent 一份定制集成"，而是统一的发现、任务模型、传输与 artifact 格式 |
| 2 | MCP 与 A2A 的分工 | MCP 是**纵向**的 agent ↔ 工具；A2A 是**横向**的 agent ↔ agent（双方都有自己的推理）；生产系统常常两者并用 |
| 3 | Agent Card | 放在 `/.well-known/agent.json` 的 JSON：名称、技能、端点、模态、鉴权要求、协议版本；发现 = 读这张卡 |
| 4 | Task | 异步、有状态的工作单元；讲义给出的生命周期是 `submitted → working → completed / failed / canceled`（阶段 13 · 19 还讲了 `input-required`、`rejected`） |
| 5 | Artifact | 任务的类型化结果：文本、结构化 JSON、图片、视频、音频，各种模态都是一等公民 |
| 6 | 不透明生命周期 | A2A 不规定远端 agent **怎么**解决任务；客户端只看到状态变化和 artifact，实现可用任意框架 |
| 7 | 发现—提交—轮询/订阅—取结果 | `GET` Agent Card → `POST /tasks` 得到 task_id → `GET /tasks/{id}` 轮询，或订阅 SSE 事件流 |
| 8 | 鉴权 | bearer token（OAuth2 或不透明令牌）、mTLS、签名请求（HMAC）；鉴权方式在 Agent Card 中声明 |
| 9 | 适用与不适用 | 适合跨组织、异构框架、类型化 artifact、长时任务；不适合亚毫秒级微调用、同进程紧耦合 agent、规模很小的内部团队 |
| 10 | 生产清单 | 固定协议版本、幂等的任务创建、声明 artifact schema、限流 + 鉴权、失败任务进死信队列 |

### 核心技能（能动手做到）

- [ ] 用 `http.server` + `urllib` 写出最小的 A2A 服务端与客户端：Agent Card、创建任务、后台执行、轮询取结果
- [ ] 读懂本节 `TaskStore` 的锁与后台线程，解释为什么客户端第一次轮询就看到 `working`
- [ ] 给任务创建加上幂等键，使网络重试不会产生重复任务
- [ ] 在提交阶段校验技能与 JSON，返回 400 而不是让任务异步失败或让连接直接断开
- [ ] 为服务端新增一个技能并更新 Agent Card，让客户端按任务类型选择技能
- [ ] 说出本节演示与正式 A2A 规范之间的主要差距，并设计 SSE 推送方案

---

## 二、基础自测（选择题）

**Q1.** 讲义如何区分 MCP 与 A2A？

- A. MCP 用于 agent 之间通信，A2A 用于 agent 调用工具
- B. 两者完全相同，只是由不同公司提出
- C. A2A 取代了 MCP，生产系统不再需要 MCP
- D. MCP 是纵向的 agent ↔ 工具协议；A2A 是横向的 agent ↔ agent 对等协议，双方都有自己的推理；生产系统常常两者并用

**Q2.** 关于 Agent Card，正确的是：

- A. 它是客户端发给服务端的身份证明
- B. 它是服务端发布在 `/.well-known/agent.json` 的 JSON 文档，描述名称、技能、端点、支持的模态与鉴权要求，客户端通过读取它完成发现
- C. 它只在任务完成后返回
- D. 它必须通过 gRPC 获取

**Q3.** 按本节讲义，A2A Task 的生命周期是：

- A. `submitted → working → completed / failed / canceled`
- B. `created → running → done`
- C. `pending → approved → shipped`
- D. 任务是同步的，没有状态

**Q4.** "Opaque lifecycle（不透明生命周期）"的含义是：

- A. 客户端无法看到任务的任何状态
- B. 任务结果会被加密，客户端无法读取
- C. 协议不规定远端 agent 如何完成任务；客户端只看到状态变化与 artifact，远端可以用任何框架、工具或子 agent 实现
- D. 任务没有 ID，只能一次性获取结果

**Q5.** 运行 `code/main.py`，客户端轮询的输出是 `attempt 1: state=working`、`attempt 2: state=working`、`attempt 3: state=completed`。为什么轮询时从来看不到 `submitted`？

- A. 因为 `TaskStore.create` 没有设置 `submitted` 状态
- B. 因为客户端跳过了第一个状态
- C. 因为 HTTP 服务器把 `submitted` 改写成了 `working`
- D. 因为 `create` 在返回前就启动了后台线程，`_run` 第一时间把状态改为 `working`；POST 响应里的 `submitted` 是创建那一刻的状态，等客户端第一次 GET 时任务早已进入 `working`

**Q6.** 客户端向本节服务端提交 `{"skill": "summarize", "payload": {}}`（Agent Card 里没有这个技能），会发生什么？

- A. 服务端立即返回 400 错误
- B. 服务端返回 `201` 和 task_id；任务随后在后台变为 `failed`，artifact 为 `{"type": "text", "data": "unknown skill 'summarize'"}`
- C. 服务端崩溃
- D. 服务端把它当成 `review-python` 处理

**Q7.** 下列关于"A2A 不适合的场景"的说法，与讲义一致的是：

- A. 如果两个 agent 运行在同一个 Python 进程里，A2A 的 HTTP 往返是过度设计，应直接函数调用
- B. 跨组织调用不适合 A2A
- C. 长时间运行（数小时）的任务不适合 A2A
- D. 输出是视频或结构化 JSON 时不适合 A2A

**Q8.** 讲义 Ship It 要求"Idempotent task creation"，指的是：

- A. 每个任务只能被查询一次
- B. 任务执行必须在 1 秒内完成
- C. 因网络重试而重复发送的 `POST /tasks` 应该只产生一个任务
- D. 所有任务必须返回相同的 artifact

---

## 三、动手 / 代码题

**Q9.** 阅读 `TaskStore` 的两个片段：

```python
    def _run(self, tid: str) -> None:
        ...
                t["artifact"] = {
                    "type": "structured",
                    "data": {"issues": issues, "lines": code.count("\n") + 1},
                }
                t["state"] = "completed"

    def get(self, tid: str) -> dict | None:
        with self._lock:
            return self.tasks.get(tid)
```

1. 客户端提交的代码是 `"x = 1\nprint(x)\n"`，artifact 中 `lines` 为 3。这个数对吗？应该怎么算？
2. `get` 在锁内返回的是字典本身的**引用**，随后 `_send_json` 在锁外执行 `json.dumps(task)`。这会带来什么问题？如何修复？

**Q10.** 讲义 Ship It 要求幂等的任务创建，但本节服务端连续两次提交相同的请求会创建两个不同的任务（已验证）。请：

1. 设计一个基于 `Idempotency-Key` 请求头的方案，写出修改后的 `TaskStore.create`；
2. 说明重复请求应返回什么状态码和内容；
3. 指出检查和插入为什么必须在同一把锁内完成。

**Q11.** 讲义练习 2：为服务端增加 `summarize` 技能。

1. 需要改哪些地方（Agent Card、任务执行、提交校验）？
2. 本节服务端收到非法 JSON（如 `b"not json"`）时，客户端得到的是什么？应该如何改？
3. 写一个客户端函数 `pick_skill(card, task_type)`：`"code"` 类任务选 `review-python`，`"text"` 类任务选 `summarize`；Agent Card 中没有对应技能时报错。

**Q12.** 讲义练习 3、4：

1. 如果要实现 SSE 端点 `/tasks/{id}/events` 推送状态变化，客户端需要做哪些不同的事？本节使用的 `HTTPServer`（单线程）会遇到什么问题？
2. 列出至少三项"正式 A2A 规范要求、而本节演示没有实现"的内容。

---

## 四、面试高频题

**Q13.**（基础必考）A2A 是什么？它的四个核心元素是什么？和 MCP 是什么关系？

**Q14.**（原理深挖）为什么 A2A 把任务设计成"异步、有状态、生命周期不透明"的对象，而不是一次同步 RPC？这种设计的代价是什么？

**Q15.**（工程实践）你要把公司内部的"合同审查 agent"通过 A2A 开放给合作伙伴调用。上线前要做哪些工程与安全工作？

**Q16.**（场景设计）公司 A 的旅行规划 agent 需要调用公司 B 的机票 agent 和公司 C 的酒店 agent，订票可能需要几分钟，期间可能需要用户补充信息（如护照号）。请设计 A2A 交互流程。

**Q17.**（追问型）既然 MCP 的 server 也能把一个"agent"包装成工具暴露出去，为什么还需要 A2A？什么时候用 MCP 包一层就够了？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："A2A is the horizontal complement to MCP: where MCP is vertical (agent ↔ tools), A2A is peer-to-peer (agent ↔ agent)." 以及 "Production multi-agent systems use both. An A2A peer calls MCP tools on its side." A 把两者弄反；B、C 与"互补"的定位矛盾。

### Q2 — 答案：B

讲义："Agent Card. A JSON document at `/.well-known/agent.json` describing the agent: name, skills, endpoints, supported modalities, auth requirements. Discovery happens by reading the card." 本节代码的 `AGENT_CARD` 还包含 `version` 和 `protocol_version`（对应 Ship It 的"固定协议版本"）。A 错，卡片是服务端自我描述而不是客户端凭证；C 错，发现发生在提交任务之前；D 错，演示用的是普通 HTTP GET。

### Q3 — 答案：A

讲义："An async, stateful object with a lifecycle: `submitted → working → completed / failed / canceled`." 补充：阶段 13 · 19 的 A2A 讲义还给出了 `input-required`（需要调用方补充信息时暂停）和 `rejected` 状态；本节代码只实现了 `submitted`、`working`、`completed`、`failed`，**没有 `canceled`**，客户端的终态判断 `("completed", "failed")` 也不包含 `canceled`。

### Q4 — 答案：C

讲义："A2A does not prescribe *how* the remote agent solves the task. The client sees state transitions and artifacts; the implementation is free to use any framework." 这让竞争对手之间也能协作而不暴露内部实现。A 错，状态是可见的；B 与加密无关；D 错，任务有 ID 并可轮询。

### Q5 — 答案：D

```python
    def create(self, skill: str, payload: dict) -> str:
        ...
                "state": "submitted",
        ...
        threading.Thread(target=self._run, args=(tid,), daemon=True).start()
        return tid

    def _run(self, tid: str) -> None:
        with self._lock:
            self.tasks[tid]["state"] = "working"
        time.sleep(0.2)
```

`submitted` 只存在于"字典刚创建、后台线程还没拿到锁"的一瞬间。POST 响应的 `{"state": "submitted"}` 是 handler 直接写死的字面量。客户端第一次 GET 时任务已在 `working`；0.2s 的工作 + 每次 0.1s 的轮询间隔，所以第 3 次看到 `completed`。A 错，代码确实设置了 `submitted`；B、C 无依据。

### Q6 — 答案：B

已用测试服务器实际验证：POST 返回 `(201, {'task_id': ..., 'state': 'submitted'})`，0.3s 后 GET 得到 `state: 'failed'`、`artifact: {'type': 'text', 'data': "unknown skill 'summarize'"}`。`do_POST` 不校验技能是否在 Agent Card 里，只在后台执行时才发现。更好的做法是在提交时就返回 400 并列出可用技能（见 Q11）——"能同步发现的错误就不要异步报告"。

### Q7 — 答案：A

讲义 "Where A2A struggles"："Tight-coupled in-process agents. If both agents run in the same Python process, A2A's HTTP round-trip is overkill." `skill-a2a-integrator` 也写明同进程时拒绝 A2A、推荐直接函数调用。B、C、D 恰恰是讲义列出的 A2A 优势场景（跨组织、长时任务、类型化 artifact）。

### Q8 — 答案：C

讲义："Idempotent task creation. Duplicate submissions (network retries) should produce one task." 客户端发出 POST 后若超时，它不知道服务端是否已创建任务，只能重试；没有幂等就会出现重复任务（重复审查、重复下单）。A、B、D 都不是幂等的含义。

### Q9 — 参考答案

1. 不对。`"x = 1\nprint(x)\n"` 只有 2 行，但字符串以换行结尾，`count("\n") + 1 = 3`（已验证）。应使用 `len(code.splitlines())`，它对结尾换行和 `\r\n` 都能正确处理（结果为 2）。讲义演示里这个"小错"恰好也说明：artifact 的字段语义需要在 schema 中写清楚，否则调用方无法判断 `lines` 是"行数"还是"换行数 + 1"。
2. `get` 在锁内取到字典引用就释放锁，`json.dumps` 在锁外遍历这个**仍可能被后台线程修改**的字典。由于 `_run` 只是给已有键赋值（不增删键），不会触发 "dictionary changed size during iteration"，但可能得到**不一致的快照**：例如 `json.dumps` 先读到 `state="working"`，接着后台线程写入 `artifact` 和 `state="completed"`，再读到已有内容的 `artifact`——客户端看到"working 但已有 artifact"。修复：在锁内复制一份再返回：

   ```python
   import copy

   def get(self, tid: str) -> dict | None:
       with self._lock:
           t = self.tasks.get(tid)
           return copy.deepcopy(t) if t is not None else None
   ```

   原则：**共享可变状态只在锁内读写，跨出锁的边界时交出副本**。

### Q10 — 参考答案

1. 修改后的 `create`（已在测试服务器上验证：同一个 `Idempotency-Key` 提交两次，只产生 1 个任务，第二次返回同一个 task_id）：

   ```python
   class TaskStore:
       def __init__(self) -> None:
           self.tasks: dict[str, dict] = {}
           self.by_key: dict[str, str] = {}          # 幂等键 → task_id
           self._lock = threading.Lock()

       def create(self, skill, payload, idem_key=None):
           with self._lock:
               if idem_key and idem_key in self.by_key:
                   return self.by_key[idem_key], False   # 已存在：不再创建
               tid = str(uuid4())[:8]
               self.tasks[tid] = {"id": tid, "skill": skill, "payload": payload,
                                  "state": "submitted", "artifact": None,
                                  "created_at": time.time()}
               if idem_key:
                   self.by_key[idem_key] = tid
           threading.Thread(target=self._run, args=(tid,), daemon=True).start()
           return tid, True
   ```

   handler 中读取 `self.headers.get("Idempotency-Key")` 传入。
2. 首次创建返回 `201 Created`；重复请求返回 `200 OK`，内容是**同一个 task_id** 和任务的**当前状态**（实测第二次返回 `state: working`），而不是再次返回 `submitted`。更严格的实现还会比较请求体：同一个键却带着不同的 payload，应返回 409/422 拒绝。幂等键需要设置过期时间，并持久化（内存字典重启即失）。
3. 若"检查键是否存在"与"插入新任务"分在两次加锁中，两个并发的重复请求可能都通过检查、各自创建一个任务——典型的 check-then-act 竞争。本节用的 `HTTPServer` 是单线程的，暂时不会并发处理请求，但一旦换成 `ThreadingHTTPServer` 或多进程部署，问题就会出现；多实例部署时还需要用数据库唯一约束或 Redis `SET NX` 实现。

   附：`str(uuid4())[:8]` 只保留 32 位随机性。按生日问题估算，生成约 65,536 个任务时出现重复 ID 的概率约为 `1 − e^{−0.5} ≈ 39%`，生产中应使用完整 UUID。

### Q11 — 参考答案

1. 需要改三处：
   - **Agent Card**：`"skills": ["review-python", "summarize"]`（规范中技能是带 id、名称、描述、输入/输出模态的对象，见阶段 13 · 19），并声明 summarize 的输入/输出 schema；
   - **任务执行**：`_run` 增加 `summarize` 分支，例如取 `payload["text"]` 的第一句作为 `{"type": "text", ...}` artifact（实测 `"A2A is a peer protocol. It has agent cards."` → `"A2A is a peer protocol."`）；
   - **提交校验**：`do_POST` 检查 `skill` 是否在支持列表中，不在就返回 `400 {"error": "unknown skill 'xxx'", "skills": [...]}`。
2. 本节 `do_POST` 直接 `json.loads`，非法 JSON 会在 handler 中抛出 `JSONDecodeError`，服务器打印异常栈并**关闭连接**，客户端得到 `RemoteDisconnected('Remote end closed connection without response')`（已验证）。应捕获异常并返回 `400 {"error": "invalid JSON"}`；同理，缺少 `Content-Length` 时 `json.loads("")` 也会失败。
3. 参考实现：

   ```python
   def pick_skill(card: dict, task_type: str) -> str:
       mapping = {"code": "review-python", "text": "summarize"}
       want = mapping.get(task_type)
       if want is None:
           raise ValueError(f"unsupported task type {task_type!r}")
       if want not in card["skills"]:
           raise ValueError(f"agent {card['name']} does not offer skill {want!r}")
       return want
   ```

   要点：客户端**根据 Agent Card 做能力判断**，而不是假设对方支持；这就是"自描述 agent"的意义。生产中还应检查 `protocol_version` 是否兼容。

### Q12 — 参考答案

1. **客户端的不同**：不再循环 `GET`，而是发起一个长连接请求（`Accept: text/event-stream`），逐行读取响应流，解析 `event:` / `data:` 行，收到终态事件后关闭；需要处理断线重连（带上 `Last-Event-ID` 从断点续传）、超时与心跳。好处是状态变化即时到达，不浪费轮询请求。
   **服务端的问题**：`HTTPServer` 一次只处理一个请求。一个 SSE 连接会长时间占住处理线程，期间其他客户端的 Agent Card 请求、任务提交都会被阻塞。至少要换成 `ThreadingHTTPServer`，生产中更常用 asyncio 框架；还要为每个任务维护订阅者列表，在 `_run` 改状态时推送事件。
2. 本节演示未实现的规范内容（参考阶段 13 · 19 的讲解与 A2A 规范，具体字段以官方规范为准）：
   - **传输绑定**：规范使用 JSON-RPC 2.0 over HTTP（另有 gRPC 绑定），方法如发送消息、获取任务、取消任务；本节是自定义 REST 路由；
   - **Message / Part 结构**：输入是带 `text` / `file` / `data` 多种 Part 的消息，而不是一个自定义 `payload`；
   - **完整的状态机**：`input-required`（任务暂停等待调用方补充信息）、`canceled`、`rejected` 等；本节没有取消接口；
   - **Agent Card 结构**：技能是带 id / 名称 / 描述 / 输入输出模态的对象，并声明 capabilities（是否支持 streaming、push notifications）与安全方案；本节技能只是字符串列表；
   - **流式与推送**：SSE 订阅与 webhook 推送通知；
   - **鉴权**：本节 `auth: none`，`skill-a2a-integrator` 明确把"公网部署 auth=none"列为 hard reject。

### Q13 — 参考回答要点

- **定义**：A2A 是 agent 与 agent 之间的对等通信协议，讲义称 Google 于 2025 年 4 月发布，到 2026 年 4 月有 150+ 组织支持。目标是让不同组织、不同框架的 agent 用统一的方式发现彼此、委派任务、取回结果。
- **四个元素**：
  1. Agent Card（`/.well-known/agent.json`，自描述：技能、端点、模态、鉴权、版本）；
  2. Task（异步、有状态、有生命周期的工作单元）；
  3. Artifact（类型化结果：文本、JSON、图片、音视频）；
  4. Opaque lifecycle（只暴露状态与结果，不规定实现）。
- **与 MCP 的关系**：MCP 是 agent ↔ 工具（纵向），A2A 是 agent ↔ agent（横向）；一个 A2A 对端内部可以通过 MCP 调用自己的工具，两者互补。
- 加分点：说出 ACP、ANP、NLIP 等相关协议（讲义：A2A 是截至 2026 年 4 月采用最广的对等协议）；指出 MCP 的工具调用对调用方是透明的，而 A2A 刻意保持对端内部不透明。

### Q14 — 参考回答要点

- **为什么异步、有状态**：
  - agent 任务耗时不可预测，可能是秒级也可能是数小时（讲义："Long-running tasks. Opaque lifecycle + polling makes hours-long tasks straightforward"）；同步 RPC 会遇到连接超时、网关超时；
  - 任务过程中可能需要补充信息（`input-required`）、可能被取消，需要显式状态；
  - 状态 + task_id 让客户端可以断线重连、重试查询，而不丢失进度。
- **为什么不透明**：跨组织协作时对方不愿也不应暴露内部推理、工具与子 agent；协议只约定"接口"而不约定"实现"，任何框架都能接入。
- **代价**：
  - 延迟与复杂度：发现 + 提交 + 轮询/订阅至少多次往返，不适合亚毫秒级调用（讲义）；
  - 可观测性下降：看不到对端内部，出错时只能依赖对端返回的错误 artifact 与状态，跨组织追踪需要额外约定（如传递 trace ID）；
  - 需要处理幂等、重试、取消、超时、死信等分布式系统问题；
  - 信任问题：对端是黑盒，必须验证其输出（结合第 08 节的 verifier 思想）。

### Q15 — 参考回答要点

- **协议层**：发布 Agent Card，声明协议版本、技能（每个技能的输入/输出 JSON schema）、模态、鉴权方式；artifact schema 让合作伙伴可以校验。
- **鉴权与授权**：公网不能 `auth: none`；按威胁模型选择 OAuth2 bearer token、mTLS（组织间互信）或请求签名；按合作伙伴区分权限与配额。
- **输入安全**：合同文本可能包含 prompt injection；对端 agent 内部要把输入当作不可信数据处理，限制其工具权限；对上传文件做类型和大小校验。
- **可靠性**：幂等的任务创建（幂等键）、任务超时、取消接口、失败任务进死信队列并定期分析（讲义 Ship It）。
- **限流与防滥用**：每客户端、每任务的速率与并发上限。
- **数据合规**：合同属于敏感数据——传输加密、存储加密、保留期限、日志脱敏；明确数据是否用于训练。
- **可观测性**：每个任务记录状态变化与耗时，支持合作伙伴传入关联 ID 便于跨组织排查。
- **传输模式**：审查耗时较长，提供 SSE 或 webhook 推送，同时保留轮询作为兜底。
- **版本管理**：卡片版本号与兼容策略，避免升级破坏合作伙伴集成。

### Q16 — 参考回答要点

- **发现**：旅行规划 agent（A）读取 B、C 的 Agent Card，确认技能（如"搜索航班""预订航班""预订酒店"）、输入 schema、鉴权方式与是否支持 streaming / 推送。
- **并行委派**：A 同时向 B、C 提交任务（各带幂等键），得到 task_id；用 SSE 订阅或 webhook 推送接收进度，避免长时间轮询。
- **需要补充信息**：B 在订票时发现缺护照号，把任务置为 `input-required` 并说明所需字段；A 向用户收集后，在**同一个任务**上补发消息，任务回到 `working`。A 不应把护照号预先发给不需要的一方（最小必要原则）。
- **结果**：B、C 返回结构化 artifact（订单号、价格、取消政策），A 用 schema 校验后整合成行程。
- **失败与补偿**：若机票成功、酒店失败，A 需要决定是否取消机票（调用 B 的取消能力）或换酒店——A2A 不提供跨任务事务，补偿逻辑在 A 这一侧（类似 saga 模式）。
- **安全**：与 B、C 之间用 OAuth2 / mTLS；支付相关操作需要用户确认；记录每个外部任务的 ID 与状态变化，便于对账和售后。

### Q17 — 参考回答要点

- **MCP 包一层够用的情况**：被调用方本质上是"一个能力"——输入明确、同步或短时返回、调用方需要对过程有透明的控制，例如"把这段文本翻译成英文"。这时把它当工具即可，MCP 的工具列表与调用更简单。
- **需要 A2A 的情况**：
  - 对方是**有自主推理的对等方**，任务长、可能需要中途沟通（`input-required`）、可能被取消；
  - 跨组织、跨信任边界，需要自描述的发现机制、声明式鉴权与不透明的内部实现；
  - 结果是多模态、类型化的 artifact，可能流式产出；
  - 讲义："A2A became the way enterprise agent systems cross trust boundaries."
- **讲义练习 5 的取舍**：Agent Card（自描述）让客户端在调用前就知道能力和要求，适合跨组织发现、可以被注册中心收录；MCP 的 `listTools` 是连接后探测能力，更灵活、可随会话动态变化，但需要先建立连接。自描述的代价是卡片可能与真实能力不同步（需要版本管理，阶段 13 · 19 提到可对卡片签名以防冒充）。
- 加分点：说明两者可以组合——一个 A2A agent 内部用 MCP 调用工具；也可以设计"把 MCP server 包装成 A2A agent"，但会失去部分透明性（阶段 13 · 19 练习 4）。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：消息、任务、路由等原语。
- [阶段 16 · 03 通信协议](../../03-communication-protocols/docs/zh.md)：agent 通信协议的总体图景。
- [阶段 16 · 02 FIPA-ACL 与言语行为理论的历史基础](../../02-fipa-acl-heritage/docs/zh.md)：agent 通信标准化的前身。
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../../13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md)：理解 A2A 的"纵向"对照物 MCP。

### 本节被哪些后续内容用到
- [阶段 13 · 19 A2A：Agent 与 Agent 之间的通信协议](../../../13-tools-and-protocols/19-a2a-protocol/docs/zh.md)：更贴近规范的 A2A 讲解（Message/Part、`input-required`、传输绑定）。
- [阶段 13 · 16 MCP 授权：CIMD、签发者绑定、PKCE 与升级认证](../../../13-tools-and-protocols/16-mcp-security-oauth-2-1/docs/zh.md)：跨系统调用的鉴权设计。
- [阶段 16 · 21 Agent 经济体系、Token 激励与声誉](../../21-agent-economies/docs/zh.md)：跨组织 agent 之间的信任与激励。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../22-production-scaling-queues-checkpoints/docs/zh.md)：长时任务的持久化与幂等。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：公开端点的安全运维。

### 延伸关键词
`Agent2Agent (A2A)` · `Agent Card` · `/.well-known/agent.json` · `task lifecycle` · `input-required` · `artifact` · `Message / Part` · `JSON-RPC 2.0` · `SSE` · `push notification / webhook` · `Idempotency-Key` · `mTLS` · `OAuth2 bearer` · `MCP vs A2A` · `ACP / ANP / NLIP`
