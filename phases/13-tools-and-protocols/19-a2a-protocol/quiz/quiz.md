# 测验 · A2A：Agent 与 Agent 之间的通信协议（A2A — Agent-to-Agent Protocol）

> **阶段 13 · 工具与协议 · 第 19 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | MCP 与 A2A 的分工 | MCP 是 agent-to-tool（调用一个具体工具，调用过程透明）；A2A 是 agent-to-agent（把整个任务委托给另一个不透明的 agent）；两者互补，生产系统常同时使用 |
| 2 | Agent Card | 讲义：每个 A2A agent 在 `/.well-known/agent.json` 发布卡片，含 `name`、`description`、`url`、`version`、`skills[]`、`capabilities`；发现就是"抓卡片 → 拿 endpoint → 枚举 skill" |
| 3 | Skill | agent 支持的一个具名操作（类比 MCP tool），声明 `inputModes` / `outputModes`，调用方据此判断能否对接 |
| 4 | Task 生命周期 | `submitted → working → completed / failed / canceled / rejected`；`working → input_required → working` 可经消息循环 |
| 5 | Message 与 Part | 一条消息带一个或多个 Part：`text`（纯文本）、`file`（base64 + mimeType）、`data`（结构化 JSON 输入） |
| 6 | Artifact | 任务输出是具名、带类型的 Artifact，而不是裸字符串；可以分块流式返回，由调用方累积 |
| 7 | 不透明性（opacity） | 调用方只看到任务状态与 Artifact，被调方的思维链、工具调用、子 agent 委托都不可见；这让竞争方也能协作 |
| 8 | 两种传输绑定 | JSON-RPC over HTTP（默认，`/a2a` 端点，POST + 可选 SSE 流）与 gRPC；两者承载相同的逻辑消息形状 |
| 9 | 发展时间线（讲义） | 2025-04 Google 发布 → 2025-06 捐给 Linux 基金会 → 2025-08 吸收 IBM 的 ACP → 2025-09 AP2 扩展 → 2026-04 v1.0，150+ 支持组织 |
| 10 | 信任 | 讲义把"签名的 Agent Card"归入 AP2：发布方用 JWT 签名自己的卡片，消费方验证，防止冒充 |

### 核心技能（能动手做到）

- [ ] 写出一个合法的 Agent Card JSON，并为一个 skill 写清 `inputModes` / `outputModes`
- [ ] 画出 Task 状态机，说出哪些状态是终态、`input_required` 如何回到 `working`
- [ ] 构造含 `text` + `file` + `data` 三种 Part 的 Message，知道 file Part 为什么要 base64
- [ ] 读懂 `writer_tasks_send` / `writer_tasks_reply`，预测任意输入下的任务状态与消息数
- [ ] 用 HMAC 对卡片的规范化 JSON 签名并验证，证明篡改后的卡片验证失败（讲义练习 2）
- [ ] 判断一个需求该用 MCP 还是 A2A，并说出把 MCP server 包装成 A2A agent 会失去什么

---

## 二、基础自测（选择题）

**Q1.** 一个客服 agent 要把"写一份完整的季度报告"交给另一家公司提供的写作 agent，而且对方不愿意暴露内部实现。最合适的协议是：

- A. MCP，把写作 agent 当作一个 tool 调用
- B. 自定义 REST API，每对 agent 单独约定
- C. A2A，以 Task 的形式委托，调用方只看到状态和 Artifact
- D. 让两个 agent 共享同一个代码库和框架

**Q2.** 按本节讲义，A2A agent 的 Agent Card 发布在哪里？

- A. `/.well-known/agent.json`
- B. `/.well-known/oauth-protected-resource`
- C. `/.well-known/mcp.json`
- D. `/a2a/card`

**Q3.** 关于 A2A Task 生命周期，下列哪个转换是讲义允许的？

- A. `completed → working`
- B. `canceled → input_required`
- C. `submitted → completed`，中间不需要任何状态
- D. `input_required → working`（调用方通过新消息补充信息后）

**Q4.** 关于 Message 的三种 Part，正确的是：

- A. `data` Part 用来传 PDF 等二进制文件
- B. `file` Part 携带 base64 编码的内容和 `mimeType`；`data` Part 携带结构化 JSON
- C. 一条消息只能包含一个 Part
- D. `text` Part 必须是 Markdown

**Q5.** A2A 的"不透明性"指的是：

- A. 调用方只能看到任务状态转换和最终产出，看不到被调 agent 的思维链、工具调用和子 agent 委托
- B. 消息内容全部加密，连调用方也看不到 Artifact
- C. Agent Card 不对外公开
- D. 与 MCP 一样，每个工具调用对调用方都可见

**Q6.** 本节 `research_agent_flow` 第一次调用 `writer_tasks_send` 时，消息只含 `text` 和 `file` 两个 Part。返回时任务的 `state` 和 `messages` 长度分别是：

- A. `completed`，1
- B. `working`，1
- C. `submitted`，2
- D. `input_required`，2

**Q7.** 本节代码跑完后，最后打印的 `messages` 是多少？

- A. 2
- B. 3
- C. 4
- D. 5

**Q8.** 讲义列出的 A2A 两种传输绑定是：

- A. stdio 与 Streamable HTTP
- B. WebSocket 与 MQTT
- C. JSON-RPC over HTTP（默认，可选 SSE 流）与 gRPC
- D. REST 与 GraphQL

---

## 三、动手 / 代码题

**Q9.** 阅读本节代码，找出至少 4 处"讲义 / 提示文本 / 实现"之间不一致或过于宽松的地方。提示：看 banner、`input_required` 时 agent 发出的提示文字、`skill_id` 的用法、`submitted` 状态、对多个 `data` Part 的处理。

```python
def writer_tasks_send(skill_id: str, message: Message) -> Task:
    task = Task(id=f"task_{uuid.uuid4().hex[:10]}")
    TASK_STORE[task.id] = task
    task.state = "working"
    task.append(message)
    print(f"    WRITER  : started task {task.id} skill={skill_id}")
    data_parts = [p for p in message.parts if p.kind == "data"]
    if not data_parts or "targetLength" not in data_parts[0].payload:
        task.state = "input_required"
        task.append(Message(role="agent", parts=[
            Part("text", {"text": "Please specify target_length as a data part."})
        ]))
```

**Q10.** 对 `writer_tasks_reply` 做"黑盒测试"。先建一个处于 `input_required` 的任务，然后依次发送下列回复，写出每次之后的 `state`、`messages` 长度和 Artifact 文本的长度描述：

1. 只含 `text` Part：`"2 paragraphs"`
2. 含 `data` Part 但键名是 `length`：`{"length": "long"}`
3. 任务已完成后再发 `data` Part：`{"targetLength": "X"}`
4. 用不存在的 `task_id` 调用

然后用一个"允许转换表"改写，使非法转换显式报错。

**Q11.** 完成讲义练习 2：给 Agent Card 加 HMAC 签名。要求：
- 对"去掉 `signature` 字段后的卡片"做规范化 JSON 再签名；
- 验证时按 `kid` 取 key、常数时间比较；
- 证明把 `url` 改成 `https://evil.example.com/a2a` 后验证失败，而仅仅改变 JSON 缩进不影响验证。

**Q12.** 完成讲义练习 3 的核心逻辑：写一个生成器 `writer_stream(length)`，产出 3 个增量 Artifact 块（每块带 `append` 与 `lastChunk` 标志），调用方把它们累积成完整文本。说明 `append=False` 的语义为什么重要。

---

## 四、面试高频题

**Q13.**（基础必考）MCP 和 A2A 有什么区别？为什么说它们是互补而不是竞争关系？举一个两者同时使用的架构例子。

**Q14.**（原理深挖）A2A 为什么要把交互建模成"带生命周期的 Task"，而不是一次同步 RPC？`input_required` 状态解决了什么问题？

**Q15.**（工程实践）如果把本节的内存 harness 变成生产级 A2A server，你要补哪些东西？

**Q16.**（场景设计）讲义练习 4：设计一个把现有 MCP server 包装成 A2A agent 的适配层。每个 MCP tool 映射为一个 A2A skill 合理吗？会失去什么、得到什么？

**Q17.**（追问型）A2A 强调被调方不透明。那调用方如何建立信任、如何防止被冒充、如何防御对方 Artifact 里夹带的 prompt injection？不透明性和可审计性如何平衡？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义的问题场景几乎就是这一题：客服 agent 委托写作 agent。A 不合适："MCP is for calling tools, not for two agents collaborating while preserving each agent's opaque internal reasoning"。B 能用，但"every pairing is a one-off"。D 要求双方跑同一个框架。A2A 把交互建模为 Task + 生命周期 + 消息 + Artifact，被调方内部状态保持不透明。

### Q2 — 答案：A

讲义："Every A2A-compliant agent publishes a card at `/.well-known/agent.json`"。B 是第 18 节 MCP 授权中 RFC 9728 protected-resource metadata 的路径；C、D 是虚构路径。卡片中的 `url`（如 `https://writer.example.com/a2a`）才是 A2A 端点本身。（规范在演进，部署时以 a2a-protocol.org 的当前版本为准。）

### Q3 — 答案：D

讲义状态图：`working -> input_required -> working (loop via message)`。`completed`、`failed`、`canceled`、`rejected` 是终态，A、B 都从终态往回走。C：讲义的路径是 `submitted -> working -> completed`，要经过 `working`。（本节代码中 `submitted` 是 dataclass 默认值，但 `writer_tasks_send` 立刻改成 `working`，调用方从来观察不到 `submitted`——见 Q9。）

### Q4 — 答案：B

讲义：`text` 是纯文本；`file` 是 "base64 blob with mimeType"；`data` 是 "typed JSON payload (structured input for the called agent)"。A 把 file 和 data 弄反了；C 错，讲义示例一条消息里就有三个 Part；D 没有这种要求（Artifact 的 `mimeType` 才可能是 `text/markdown`）。base64 的原因是 JSON 只能承载文本，二进制要先编码。

### Q5 — 答案：A

讲义："The caller sees task state and artifacts. The called agent's chain-of-thought, its tool calls, its sub-agent delegation — all invisible. This is different from MCP, where tool calls are transparent." B 混淆了"不透明"与"加密"——Artifact 本来就是交给调用方的；C 错，Agent Card 恰恰要公开以便发现；D 描述的是 MCP。

### Q6 — 答案：D

`data_parts` 为空 → `state = "input_required"`，并追加一条 `role="agent"` 的提示消息。于是 `messages` = [调用方原始消息, agent 的提示] = 2 条。实际运行输出 `WRITER  : paused input_required` 和 `research : task state = input_required`。A 需要消息里带 `targetLength`；B 是瞬时状态，函数返回前已被覆盖；C 的 `submitted` 根本观察不到。

### Q7 — 答案：B

三条消息：①调用方的 text + file；②writer 的 `input_required` 提示；③调用方补充的 `data` Part。`finish` 只设置 `task.artifact`，**不**追加消息，所以是 3。实际运行输出 `messages    : 3`。

### Q8 — 答案：C

讲义 "Two transport bindings"：JSON-RPC over HTTP（`/a2a` 端点，POST 请求，可选 SSE 流，默认绑定）和 gRPC（企业环境）。A 是 MCP 的传输；B、D 不在讲义中。

### Q9 — 参考答案

| # | 问题 | 后果 / 修法 |
|---|------|------------|
| 1 | banner 打印 `PHASE 13 LESSON 18`，本节是第 19 节（TS 版 `main.ts` 打印的是 19；`outputs/skill-a2a-agent-spec.md` 的 front matter 也写着 `lesson: 18`） | 纯笔误，改成 19 |
| 2 | 提示语要求 `target_length`，代码检查的却是 `targetLength`（TS 版提示语写的是 `targetLength`） | 调用方若照提示发 `{"target_length": ...}`，`writer_tasks_reply` 会走 `.get("targetLength", "short")` 默默得到 "short" 报告；统一为 `targetLength` |
| 3 | `skill_id` 只用于打印，不校验是否在 Agent Card 中，也不检查 Part 类型是否在 `inputModes` 中 | 实测传 `"nonexistent_skill"` 也能 `completed`；应返回 `rejected` 或协议错误 |
| 4 | `submitted` 状态被立即覆盖为 `working`，调用方永远看不到 | 真正的异步实现应先返回 `submitted`，由 worker 推进 |
| 5 | 只看**第一个** `data` Part | 实测消息为 `[data{x:1}, data{targetLength:"2"}]` 时进入 `input_required`；应合并或遍历所有 data Part |
| 6 | `file` Part 从不被读取，产出是固定模板 | 演示简化；讲义说 writer "returns a text artifact"，但内容与输入无关 |
| 7 | 讲义 Use It 说"a research agent publishes its card"，代码里发布卡片的是 **writer** agent | 讲义描述与代码不符 |
| 8 | 从不使用 `failed` / `canceled` / `rejected`，也没有 cancel 方法 | 生命周期只演示了一半 |

### Q10 — 参考答案

实际运行结果（任务初始为 `input_required`、2 条消息）：

| 操作 | state | messages | Artifact |
|------|-------|----------|----------|
| 1. 只含 text | `input_required` | 3 | 无（静默追加，没有任何提示或错误） |
| 2. data 但键为 `length` | `completed` | 4 | `"[writer agent] short summary ..."`——缺 `targetLength` 时默认 `"short"`，与 `send` 路径"缺了就要求补充"的规则不一致 |
| 3. 已完成后再发 data | `completed` | 5 | 不变；消息被追加到已完成任务上，没有报错 |
| 4. 不存在的 `task_id` | 抛 `KeyError: 'task_nope'` | — | 应返回协议级错误（如"task not found"） |

改写思路：

```python
ALLOWED = {
    "submitted": {"working", "rejected", "canceled"},
    "working": {"input_required", "completed", "failed", "canceled"},
    "input_required": {"working", "canceled", "failed"},
    "completed": set(), "failed": set(), "canceled": set(), "rejected": set(),
}

class TaskError(Exception):
    pass

def transition(task: Task, new_state: str) -> None:
    if new_state not in ALLOWED[task.state]:
        raise TaskError(f"illegal transition {task.state} -> {new_state}")
    task.state = new_state

def writer_tasks_reply(task_id: str, message: Message) -> Task:
    task = TASK_STORE.get(task_id)
    if task is None:
        raise TaskError("task not found")
    if task.state != "input_required":
        raise TaskError(f"task is {task.state}, not awaiting input")
    task.append(message)
    length = next((p.payload["targetLength"] for p in message.parts
                   if p.kind == "data" and "targetLength" in p.payload), None)
    if length is None:                       # 仍缺信息：保持 input_required，并明确再问一次
        task.append(Message("agent", [Part("text", {"text": "Still need targetLength as a data part."})]))
        return task
    transition(task, "working")
    finish(task, length)                     # finish 内部也应改用 transition(task, "completed")
    return task
```

要点：终态没有出边；"缺字段"有一致的处理；未知任务给出明确错误而不是 `KeyError`。

### Q11 — 参考答案

```python
import base64, hashlib, hmac, json

def canonical(card: dict) -> bytes:
    body = {k: v for k, v in card.items() if k != "signature"}     # 签名不能覆盖自己
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def sign_card(card: dict, key: bytes, kid: str) -> dict:
    sig = hmac.new(key, canonical(card), hashlib.sha256).digest()
    out = dict(card)
    out["signature"] = {"alg": "HS256", "kid": kid,
                        "value": base64.urlsafe_b64encode(sig).rstrip(b"=").decode()}
    return out

def verify_card(card: dict, keys: dict[str, bytes]) -> bool:
    s = card.get("signature")
    if not isinstance(s, dict) or s.get("alg") != "HS256" or s.get("kid") not in keys:
        return False
    expected = base64.urlsafe_b64encode(
        hmac.new(keys[s["kid"]], canonical(card), hashlib.sha256).digest()).rstrip(b"=").decode()
    return hmac.compare_digest(expected, s.get("value", ""))
```

已实际运行：对 `WRITER_AGENT_CARD` 签名后 `verify_card` 为 `True`；把 `url` 改成 `https://evil.example.com/a2a` 后为 `False`；用 `json.dumps(indent=4)` 重新排版再解析后仍为 `True`（因为签的是 `sort_keys=True` + 紧凑分隔符的规范化形式，不是原始字节）。

注意：HMAC 是对称密钥，验证方也能签名，只适合双方已共享密钥的场景；面向公众发布的卡片应使用非对称签名（讲义所说的 JWT 签名，配合公钥/JWKS），这样任何人都能验证却不能伪造。真实系统的规范化还需遵循一个明确标准（如 JSON 规范化方案），否则不同语言的序列化细节会导致验签失败。

### Q12 — 参考答案

```python
def writer_stream(length: str):
    chunks = [f"## Summary ({length})\n", "Key points extracted.\n", "Conclusion drafted.\n"]
    for i, c in enumerate(chunks):
        yield {"artifact": {"name": "summary", "parts": [{"kind": "text", "text": c}]},
               "append": i > 0,                      # 第一块是"新建"，之后是"追加"
               "lastChunk": i == len(chunks) - 1}

acc: list[str] = []
for ev in writer_stream("3 paragraphs"):
    if not ev["append"]:
        acc = []                                     # 新 Artifact 开始：丢弃旧累积
    acc.append(ev["artifact"]["parts"][0]["text"])
    if ev["lastChunk"]:
        break
print("".join(acc))
```

已运行，结果为 `'## Summary (3 paragraphs)\nKey points extracted.\nConclusion drafted.\n'`。

`append=False` 的意义：流可能断线重连、被调方可能决定重新生成，调用方必须知道"这一块是替换还是追加"，否则会把两次生成拼在一起。`lastChunk` 让调用方知道何时可以交给下游。线上用 SSE 时，每个 `yield` 对应一个 `data:` 事件。

### Q13 — 参考回答要点

- **调用对象不同**：MCP 是 agent 调用工具/数据源；A2A 是 agent 把任务委托给另一个 agent。
- **透明度不同**：MCP 的工具调用对宿主透明（参数、结果都可见）；A2A 被调方内部不透明，只暴露状态与 Artifact。
- **状态模型不同**：MCP 工具调用是"请求→结果"；A2A 是带生命周期的 Task（可暂停等待输入、可流式产出）。
- **讲义对比表**中的其他维度：典型调用方（agent runtime vs 另一个 agent）、授权（MCP 用 OAuth 2.1；讲义写 A2A 用 JWT 签名的 Agent Card）、传输（stdio / Streamable HTTP vs JSON-RPC over HTTP / gRPC）。
- **互补的例子**：一个"差旅 agent"用 MCP 连接日历、邮件、报销系统（工具层），再用 A2A 把"订机票"委托给航空公司提供的预订 agent（协作层）。讲义："an agent uses MCP for its tool layer and A2A for its collaboration layer"。
- 常见误区：把 A2A 当成"MCP 的替代品"。

### Q14 — 参考回答要点

- **委托的工作往往是长时间的**：写报告、研究、订票可能耗时数分钟到数小时；同步 RPC 会超时，也无法表达"进行中"。
- **生命周期让双方对进度有共同语言**：`submitted / working / input_required / completed / failed / canceled / rejected`，调用方可以轮询或通过 SSE 订阅状态。
- **`input_required` 解决"信息不足"**：被调方发现缺参数时不必失败，而是暂停并通过消息索要，调用方补充后回到 `working`——这是多轮协作，而不是一次函数调用。本节代码正是缺 `targetLength` 时进入该状态。
- **终态区分失败原因**：`rejected`（不接这个活，如 skill 不支持）、`failed`（执行出错）、`canceled`（调用方取消），便于重试与计费策略。
- **与不透明性配合**：生命周期是被调方愿意公开的唯一"过程信息"。
- 加分点：Task 有 id，天然支持断线后查询、幂等重试、推送通知（`capabilities.pushNotifications`）。

### Q15 — 参考回答要点

- **持久化**：`TASK_STORE` 是进程内全局字典，重启即丢；改为数据库/持久队列，Task 带创建时间、过期策略。
- **异步执行**：`tasks/send` 先返回 `submitted`/`working`，由 worker 推进；支持 SSE 推送与 push notification。
- **状态机约束**：非法转换报错（见 Q10），未知 task 返回规范的协议错误。
- **输入校验**：skill 存在性、Part 类型与 `inputModes` 匹配、file 大小与 mimeType 白名单、data Part 的 JSON Schema。
- **认证授权**：调用方身份、按 skill 的权限；Agent Card 签名（讲义 AP2/练习 2）。
- **幂等与重试**：客户端请求 id，防止重复创建任务；取消（`canceled`）与超时（`failed`）。
- **多租户隔离**：调用方只能查询自己的 task；task id 要不可猜（本代码用 uuid4 的前 10 个十六进制字符，40 位随机，仅供演示）。
- **可观测性**：为每个 Task 打 trace（下一节 OpenTelemetry GenAI），但只记录状态与元数据，不泄露被调方内部推理。

### Q16 — 参考回答要点

- **直接一对一映射的问题**：把每个 MCP tool 变成一个 A2A skill，得到的是"披着 A2A 外衣的工具调用"——调用方要自己编排多个 skill，A2A 的价值（委托一个完整任务、被调方自行规划）就没了。
- **更好的做法**：按"任务"而不是"工具"设计 skill（如 `prepare_quarterly_report`），适配层内部的 agent 自主决定调用哪些 MCP tool。
- **失去什么**：调用方看不到中间 tool calls 和参数（讲义练习 4 问的"what opacity is lost"反过来就是"调用方失去的透明度"）；细粒度控制与逐步审批变难；错误定位更难。
- **得到什么**：封装性、跨框架协作、长任务生命周期、`input_required` 多轮交互、Artifact 类型化输出。
- **映射细节**：MCP tool 的 `inputSchema` → skill 的 `data` Part schema；tool 结果 → Artifact；需要用户确认的 tool → `input_required`；MCP 的 OAuth scope → skill 级授权。
- 讲义 skill 文件也有对应的拒绝规则："If the agent's use case is a single tool call, refuse to scaffold A2A; recommend MCP."

### Q17 — 参考回答要点

- **防冒充**：通过固定、稳定的 URL 发现卡片（技能文件："Any Agent Card without a stable URL. Breaks discovery"）；验证卡片签名（讲义：发布方用 JWT 签名，消费方验证）；HTTPS + 调用时的身份认证。
- **信任建立**：注册表/白名单准入、版本固定、对 skill 的能力声明做契约测试；不只看卡片自述。
- **防 Artifact 注入**：对方 Artifact 是**不可信输入**——它可能夹带"忽略之前的指令…"之类的文本。处理方式：把 Artifact 作为数据而非指令放入上下文、做结构化校验、高风险动作需人工确认、用权限最小化限制注入后的影响面。
- **不透明 vs 可审计**：不透明保护的是被调方的实现（竞争信息），但调用方仍需要**结果层面**的可审计：任务 id、状态时间线、输入输出 Artifact、签名与版本都可记录；必要时通过合同/SLA 约定对方提供审计摘要，而不是原始思维链。
- 加分点：注意讲义内部对 AP2 的描述并不统一——正文把 AP2 写成"给 Agent Card 加签名"的扩展，关键术语表写成 "Agent Payments Protocol"，而 `outputs/skill-a2a-agent-spec.md` 又要求"flag that AP2 is separate from core A2A"。面试中谈"签名卡片"时说清楚它解决的是身份真实性，"支付"是另一回事，更稳妥。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：A2A 默认绑定同样是 JSON-RPC，对比 agent-to-tool 的消息形状。
- [阶段 13 · 08 构建 MCP 客户端：发现、路由与新旧协议兼容回退](../../08-building-an-mcp-client/docs/zh.md)：发现 → 枚举能力 → 调用的客户端思路与 Agent Card 发现一致。
- [阶段 13 · 13 MCP Tasks 扩展：在无状态核心上运行持久任务](../../13-mcp-async-tasks/docs/zh.md)：对比 MCP 的长任务模型与 A2A 的 Task 生命周期。
- [阶段 13 · 18 生产环境中的 MCP 认证](../../18-mcp-auth-production/docs/zh.md)：签名、JWKS、受众绑定等信任机制在 A2A 中同样需要。

### 本节被哪些后续内容用到
- [阶段 16 · 12 A2A：Agent 与 Agent 之间的通信协议](../../../16-multi-agent-and-swarms/12-a2a-protocol/docs/zh.md)：在多智能体系统视角下再次讨论 A2A。
- [阶段 16 · 03 通信协议](../../../16-multi-agent-and-swarms/03-communication-protocols/docs/zh.md)：多 agent 通信协议的整体对比。
- [阶段 16 · 11 Handoffs 与例程：无状态 Orchestration](../../../16-multi-agent-and-swarms/11-handoffs-and-routines/docs/zh.md)：任务委托与交接的编排模式。
- [阶段 13 · 20 OpenTelemetry GenAI：端到端追踪 Tool Calls](../../20-opentelemetry-genai/docs/zh.md)：跨 agent 的任务如何被追踪。
- [阶段 13 · 23 综合项目：无状态工具生态系统](../../23-capstone-tool-ecosystem/docs/zh.md)：把 MCP 与 A2A 组合进完整生态。

### 延伸关键词
`Agent Card` · `skills / inputModes / outputModes` · `Task lifecycle` · `input-required` · `Message Parts` · `Artifact streaming` · `JSON-RPC 2.0` · `SSE` · `gRPC` · `push notifications` · `signed Agent Card` · `AP2` · `opacity` · `ACP`
