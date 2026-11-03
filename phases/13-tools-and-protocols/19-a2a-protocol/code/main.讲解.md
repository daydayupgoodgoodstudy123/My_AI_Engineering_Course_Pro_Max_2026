# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 19 节 A2A：Agent 与 Agent 之间的通信协议 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下） ｜ **依赖**：纯标准库（`base64`、`json`、`uuid`、`dataclasses`）；同目录的 `main.ts` 是 TypeScript 移植版（`npx tsx code/main.ts`，不在本讲解范围内，差异见 3.6）

---

## 1. 这份代码在考察什么

这份约 150 行的代码用一个**进程内传输**模拟 A2A 的核心对象和一次完整委托：

1. **Agent Card**：writer agent 的卡片，含 `schemaVersion`、`name`、`url`、`version`、`skills[]`、`capabilities`。
2. **Message / Part**：调用方发送 `text` + `file`（base64）两种 Part，之后补发 `data` Part。
3. **Task 生命周期**：`working → input_required → working → completed`，包括"信息不足时暂停、等待调用方补充"这条分支。
4. **Artifact**：任务结果是带名字和 `mimeType` 的 Artifact，而不是裸字符串。
5. **不透明性**：调用方只通过 Task 的状态与 Artifact 了解结果。

> 一句话：**用最少的代码展示"一个 agent 把任务交给另一个 agent"时，两边交换的消息长什么样、任务状态怎么走**。它刻意省略了网络、认证、持久化和大部分错误处理——这些省略正是测验 Q9、Q10 的素材。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `WRITER_AGENT_CARD` | 字典常量 | writer agent 发布的卡片，一个 skill `draft_report` | Agent Card、Skill |
| `Part` | dataclass | `kind`（text/file/data）+ `payload` | Part |
| `Message` | dataclass | `role` + `parts` 列表 | Message |
| `Artifact` | dataclass | `name`、`mimeType`、`parts` | Artifact |
| `Task` | dataclass | `id`、`state`（默认 `submitted`）、`messages`、`artifact` | Task |
| `TASK_STORE` | 全局字典 | task id → Task，模拟被调方的任务存储 | 服务端状态 |
| `writer_tasks_send` | 函数 | 被调方处理 `tasks/send`：建任务、判断信息是否足够 | 发起任务 |
| `writer_tasks_reply` | 函数 | 被调方处理后续消息：补齐信息后完成 | 多轮交互 |
| `finish` | 函数 | 生成固定模板的 Artifact，状态置为 `completed` | 产出 |
| `research_agent_flow` | 函数 | 调用方（research agent）的完整流程 | 调用方视角 |

数据流：读取 `WRITER_AGENT_CARD` → 选 `skills[0]` → 构造 text + file 消息 → `writer_tasks_send`（缺 `targetLength` → `input_required`）→ 补发 data 消息 → `writer_tasks_reply` → `finish` → 读 Artifact 与最终状态。

---

## 3. 逐段精讲

### 3.1 Agent Card

```python
WRITER_AGENT_CARD = {
    "schemaVersion": "1.0",
    "name": "writer-agent",
    "description": "Drafts technical summaries and reports from source material.",
    "url": "https://writer.example.com/a2a",
    "version": "1.0.0",
    "skills": [
        {
            "id": "draft_report",
            "name": "Draft report",
            "description": "Given source material and a target length, produce a report.",
            "inputModes": ["text", "file", "data"],
            "outputModes": ["text", "artifact"],
        }
    ],
    "capabilities": {"streaming": True, "pushNotifications": False},
}
```

- 字段与讲义的 research-agent 示例一一对应。讲义说卡片发布在 `/.well-known/agent.json`；`url` 字段则是 A2A 端点（JSON-RPC 绑定下的 `/a2a`）。
- `schemaVersion` 是卡片格式的版本，`version` 是这个 agent 自己的版本，两者不要混淆。
- `skills[].inputModes` 声明本 skill 接受 text、file、data 三种输入——调用方据此判断"我能不能把一个 PDF 交给它"。
- `capabilities.streaming: True` 表示支持流式输出（讲义练习 3），`pushNotifications: False` 表示不支持推送回调，调用方只能轮询或订阅流。
- ⚠️ 代码里卡片是常量，调用方"抓取卡片"只是读字典；也没有签名（讲义练习 2，参考测验 Q11）。

### 3.2 四个数据类

```python
@dataclass
class Part:
    kind: str
    payload: dict

@dataclass
class Message:
    role: str
    parts: list[Part] = field(default_factory=list)

@dataclass
class Artifact:
    name: str
    mimeType: str
    parts: list[Part]

@dataclass
class Task:
    id: str
    state: str = "submitted"
    messages: list[Message] = field(default_factory=list)
    artifact: Artifact | None = None

    def append(self, m: Message) -> None:
        self.messages.append(m)
```

- 讲义 JSON 里 Part 用 `"type": "text", "text": ...` 的扁平形式；代码用 `kind` + `payload` 两层结构。逻辑等价，但序列化出来与讲义示例形状不同（实测 `dataclasses.asdict` 得到 `{"kind": "data", "payload": {...}}`）。
- `Artifact.mimeType` 用了驼峰命名，是为了与 JSON 字段名一致，不符合 Python 的 snake_case 习惯——这是"协议字段名优先"的常见取舍。
- `Task.state` 用普通字符串，没有枚举，也没有转换约束；任何代码都能把它改成任何值。
- `Message.role` 只有 `"user"`（调用方）和 `"agent"`（被调方）两种取值。
- `artifact` 只有一个——讲义说"Outputs are Artifacts"，真实任务可以产出多个 Artifact。

### 3.3 `writer_tasks_send`：建任务与 `input_required` 分支

```python
TASK_STORE: dict[str, Task] = {}

def writer_tasks_send(skill_id: str, message: Message) -> Task:
    task = Task(id=f"task_{uuid.uuid4().hex[:10]}")
    TASK_STORE[task.id] = task
    task.state = "working"
    task.append(message)
    print(f"    WRITER  : started task {task.id} skill={skill_id}")
    # needs target_length
    data_parts = [p for p in message.parts if p.kind == "data"]
    if not data_parts or "targetLength" not in data_parts[0].payload:
        task.state = "input_required"
        task.append(Message(role="agent", parts=[
            Part("text", {"text": "Please specify target_length as a data part."})
        ]))
        print(f"    WRITER  : paused input_required")
    else:
        finish(task, data_parts[0].payload["targetLength"])
    return task
```

- task id：`uuid4().hex` 是 32 个十六进制字符，取前 10 个（40 位随机）加 `task_` 前缀，如 `task_31a607a8f7`。
- 状态：dataclass 默认 `submitted`，紧接着改成 `working`——调用方拿到 Task 时已经不是 `submitted`。真正的服务端会先返回 `submitted`，由后台推进。
- 用列表推导式筛出所有 `data` Part，但只检查**第一个**是否含 `targetLength`。
- 信息不足时不失败，而是：状态置 `input_required`，并以 `role="agent"` 追加一条说明需要什么的消息——这就是讲义的"Input-required branch mid-task"。
- ⚠️ 提示语写 `target_length`，代码却检查 `targetLength`（TS 版提示语是 `targetLength`）。调用方照提示发 `target_length` 将得不到预期结果。
- ⚠️ `skill_id` 只被打印，不校验是否存在于卡片中（实测传 `"nonexistent_skill"` 照样 `completed`），也不检查 Part 类型是否属于 `inputModes`。规范行为应是拒绝（`rejected`）。

### 3.4 `writer_tasks_reply`：调用方补充信息

```python
def writer_tasks_reply(task_id: str, message: Message) -> Task:
    task = TASK_STORE[task_id]
    task.append(message)
    data_parts = [p for p in message.parts if p.kind == "data"]
    if task.state == "input_required" and data_parts:
        task.state = "working"
        finish(task, data_parts[0].payload.get("targetLength", "short"))
    return task
```

- 用 task id 从 `TASK_STORE` 取回任务——这就是 Task 有 id 的意义：多轮交互可以跨请求关联。
- 只有"任务在等输入"且"消息里有 data Part"时才推进：`input_required → working → completed`。
- ⚠️ 已实测的宽松行为：
  - 只发 text：消息被追加，状态仍 `input_required`，没有任何反馈；
  - data 里没有 `targetLength`：`.get(..., "short")` 默认值让任务直接完成——与 `send` 路径"缺了就要"的规则不一致；
  - 任务已 `completed` 后再发：消息仍被追加到已完成任务上，不报错；
  - 未知 id：抛 `KeyError`。
  测验 Q10 给出了用"允许转换表"改写的版本。

### 3.5 `finish` 与调用方流程

```python
def finish(task: Task, length: str) -> None:
    text = f"[writer agent] {length} summary of provided source: "\
           f"topic identified, key points extracted, conclusion drafted."
    task.artifact = Artifact(name="summary", mimeType="text/markdown",
                             parts=[Part("text", {"text": text})])
    task.state = "completed"
```

- 两个相邻的 f-string 字面量会被自动拼接，行尾 `\` 是续行符。
- Artifact 内容是固定模板，只把 `length` 填进去；`file` Part（PDF）从未被读取。
- `finish` 不追加消息，所以最终消息数是 3（见第 6 节）。

```python
    msg = Message(role="user", parts=[
        Part("text", {"text": "Summarize the attached paper."}),
        Part("file", {"file": {"name": "paper.pdf", "mimeType": "application/pdf",
                                "bytes": base64.b64encode(b"fake-pdf").decode()}}),
    ])
    task = writer_tasks_send(skill_id, msg)
    if task.state == "input_required":
        followup = Message(role="user", parts=[Part("data", {"targetLength": "3 paragraphs"})])
        task = writer_tasks_reply(task.id, followup)
```

- file Part 的 `bytes` 是 base64 字符串：`b"fake-pdf"` → `ZmFrZS1wZGY=`。JSON 只能携带文本，二进制必须编码。这里用的是**标准** base64（可能含 `+`、`/`、`=`），不是 URL-safe 变体。
- 调用方根据 `task.state` 分支：看到 `input_required` 就补发 data Part——调用方只依赖"状态 + agent 消息"，不了解 writer 内部如何判断，这就是不透明性。
- 打印卡片时用字典推导式 `{k: WRITER_AGENT_CARD[k] for k in ("name", "url", "skills")}` 只选三个字段，`json.dumps(..., indent=2)` 美化输出。

### 3.6 与讲义、TS 版的差异汇总

| 位置 | 本文件 | 讲义 / TS 版 |
|------|--------|-------------|
| banner | `PHASE 13 LESSON 18` | 本节是第 19 节；TS 版打印 `LESSON 19` |
| 提示语 | `target_length` | 代码与 TS 版都用 `targetLength` |
| Part 形状 | `kind` + `payload` | 讲义 JSON 为 `type` + 扁平字段 |
| 谁发布卡片 | writer agent | 讲义 Use It 说"a research agent publishes its card" |
| 终态 | 只用 `completed` | 讲义还有 `failed / canceled / rejected`；TS 的 `TaskState` 类型里没有 `rejected` |
| 未知 task id | `KeyError` | TS 版抛 `unknown task` 错误 |

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 进程内函数调用代替 JSON-RPC over HTTP | 聚焦消息形状 | 没有序列化、超时、重试；生产用 HTTP + JSON-RPC 2.0 或 gRPC |
| 全局 `TASK_STORE` 字典 | 最简单的状态存储 | 重启丢失、无并发控制、无租户隔离；生产用数据库/队列 |
| `state` 用字符串 | 代码短 | 无转换约束，可出现非法状态；用 `Enum` + 允许转换表 |
| 同步完成任务 | 演示线性 | 观察不到 `submitted`；生产异步推进、SSE/推送通知 |
| 只看第一个 data Part | 代码短 | 多个 data Part 时误判；应合并或遍历 |
| 不校验 skill 与 inputModes | 演示简单 | 任意 skill id 都能"成功"；应 `rejected` |
| Artifact 为固定模板 | 不依赖 LLM | 不能体现真实的生成；替换为实际 agent 调用 |
| 卡片无签名 | 简化 | 可被冒充；签名卡片（讲义练习 2） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许在注解里写 `Artifact \| None` 等新语法 |
| `@dataclass` | `class Task:` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=list)` | `messages: list[Message] = field(default_factory=list)` | 每个实例一个新列表，避免共享可变默认值 |
| 类型注解 `X \| None` | `artifact: Artifact \| None = None` | 可为空的类型 |
| 模块级类型注解 | `TASK_STORE: dict[str, Task] = {}` | 给全局变量标注类型 |
| 位置参数构造 dataclass | `Part("text", {"text": ...})` | 按字段定义顺序传参 |
| 列表推导式 + 条件 | `[p for p in message.parts if p.kind == "data"]` | 过滤 |
| 字典推导式 | `{k: WRITER_AGENT_CARD[k] for k in ("name", "url", "skills")}` | 挑选字段 |
| `dict.get(key, default)` | `payload.get("targetLength", "short")` | 缺键时返回默认值（也正是 Q10 的宽松根源） |
| `in` 判断键 | `"targetLength" not in data_parts[0].payload` | 字典成员测试 |
| 短路 `or` | `if not data_parts or "targetLength" not in data_parts[0].payload` | 列表为空时不会执行右侧索引，避免 `IndexError` |
| f-string 拼接与续行 | `f"..."\` 换行 `f"..."` | 相邻字符串字面量自动连接 |
| `uuid.uuid4().hex[:10]` | 生成 task id | 字符串切片 |
| `base64.b64encode(b"...").decode()` | file Part | bytes → base64 bytes → str |
| `json.dumps(obj, indent=2)` | 打印卡片 | 美化输出 |
| `"=" * 72` | banner | 字符串重复 |
| `if __name__ == "__main__":` | 文件末尾 | 被导入时不执行流程 |

---

## 6. 运行结果解读

实际运行 `python3 code/main.py`（task id 每次随机）：

```text
========================================================================
PHASE 13 LESSON 18 - A2A CALL FROM RESEARCH TO WRITER      ← 笔误，应为 19
========================================================================

--- research agent fetches writer Agent Card ---
{
  "name": "writer-agent",
  "url": "https://writer.example.com/a2a",
  "skills": [ { "id": "draft_report", ..., "inputModes": ["text","file","data"], ... } ]
}

  research agent will invoke skill: draft_report
    WRITER  : started task task_31a607a8f7 skill=draft_report
    WRITER  : paused input_required                       ← 第一条消息没有 data Part
  research : task state = input_required

--- research agent supplies the missing data ---
    WRITER  : completed task task_31a607a8f7              ← 同一个 task id，多轮关联
  research : task state = completed

--- research agent reads artifact ---
  name     : summary
  mimeType : text/markdown
  content  : [writer agent] 3 paragraphs summary of provided source: topic identified, key points extracted, conclusion drafted.

--- lifecycle observation ---
  final state : completed
  messages    : 3
```

逐项解读：

- 以 4 个空格 + `WRITER  :` 开头的行是**被调方**内部日志；以 `research :` 开头的是调用方看到的。真实部署中调用方看不到 WRITER 行——这就是不透明性在输出格式上的体现。
- 状态序列（调用方视角）：`input_required` → `completed`；中间的 `working` 在同步实现里一闪而过。
- Artifact 的 `content` 中 "3 paragraphs" 来自补发的 data Part，其余是模板。
- `messages : 3`：调用方首条消息、writer 的提示、调用方补充；Artifact 不计入消息。

---

## 7. 动手改一改

1. **（入门）** 修正 banner 为 `LESSON 19`、提示语为 `targetLength`；把第一条消息直接带上 `Part("data", {"targetLength": "1 paragraph"})`，确认任务一次完成、`messages` 为 1。
2. **（状态机）** 用 `enum.Enum` 定义 7 个状态，加"允许转换表"，让 `writer_tasks_reply` 在终态上抛错（参考测验 Q10）。
3. **（skill 校验）** 在 `writer_tasks_send` 中检查 `skill_id` 是否在卡片里、每个 Part 的 `kind` 是否属于 `inputModes`，不符合时置 `rejected` 并附一条 agent 消息说明原因。
4. **（练习 2）** 实现 `sign_card` / `verify_card`（测验 Q11），在 `research_agent_flow` 开头验证卡片，篡改 `url` 后流程应拒绝继续。
5. **（练习 3）** 把 `finish` 改为生成器，分 3 块产出 Artifact，调用方按 `append` / `lastChunk` 累积（测验 Q12）。
6. **（进阶）** 用 `http.server` 起一个本地 JSON-RPC 端点，把 `tasks/send` 与回复包装成 JSON-RPC 2.0 请求（`{"jsonrpc": "2.0", "id": ..., "method": ..., "params": ...}`），调用方用 `urllib.request` 发送；此时 Part / Artifact 需要能 JSON 序列化（`dataclasses.asdict`）。

---

## 8. 常见坑

- **把 A2A 当工具调用用**：如果需求只是调一个函数，用 MCP；技能文件也规定"single tool call → refuse to scaffold A2A"。
- **字段名不一致**：提示语、调用方、被调方对 `targetLength` / `target_length` 的写法要统一，否则会静默走默认值。
- **`.get` 的默认值掩盖缺失输入**：`get("targetLength", "short")` 让本该再次 `input_required` 的任务直接完成。
- **终态还能接收消息**：没有状态机约束时，已完成任务可以被继续追加消息。
- **只看第一个 Part**：多个同类 Part 时逻辑出错。
- **把 file 原始 bytes 塞进 JSON**：必须 base64；同时要限制大小与 mimeType。
- **把不透明性理解为"不可审计"**：任务 id、状态时间线、输入/输出 Artifact 仍应记录。
- **对方 Artifact 当指令执行**：另一个 agent 的输出是不可信数据，可能含 prompt injection。
