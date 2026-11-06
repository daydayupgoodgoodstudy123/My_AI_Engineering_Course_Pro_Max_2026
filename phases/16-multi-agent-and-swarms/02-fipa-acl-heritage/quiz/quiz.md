# 测验 · FIPA-ACL 与言语行为理论的历史基础（Heritage of FIPA-ACL and Speech Acts）

> **阶段 16 · 多智能体与集群 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 注：中文讲义为机器翻译，若干术语错译（如把 performatives 译成"表现"、ontology 译成"本体学"、"FIPA performatives" 译成"联邦投资促进机构业绩"），请以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 言语行为理论 | Austin（1962）：有些话语不是描述世界而是改变世界（"我承诺""我请求"）；Searle（1969）归纳为五类：assertive、directive、commissive、expressive、declarative |
| 2 | 从理论到线协议 | KQML（1993）把"消息 = performative（动作）+ content（内容）"做成软件协议；FIPA-ACL（2000 年批准）补齐 KQML 的缺口并标准化 |
| 3 | Performative | 消息的意图类别：`inform`、`request`、`query-if`、`query-ref`、`propose`、`accept-proposal`、`reject-proposal`、`agree`、`refuse`、`cfp`、`subscribe`、`cancel`、`failure`、`not-understood` 等 |
| 4 | ACL 消息结构 | 讲义："Seven fields carry the protocol envelope; one field (`content`) carries the payload"：sender、receiver、language、ontology、protocol、conversation-id、reply-with + content |
| 5 | 为什么 FIPA 衰落 | 本体（ontology）开销太重、形式语义（SL）没人用、工具锁定（JADE 只支持 Java、JACK 是商业产品）、Web 技术栈胜出 |
| 6 | LLM 时代是"FIPA-lite" | MCP `tools/call` ≈ `request`；`resources/read` ≈ `query-ref`；A2A Task 生命周期 ≈ contract-net + request-when；A2A 流式事件 ≈ subscribe/notify |
| 7 | 取舍 | 现代规范保留结构原语（意图、关联 id），丢掉形式语义和强制本体，用 JSON 原生载荷、自然语言内容、Web 传输、能力发现换取易实现性 |
| 8 | 值得移植的三个交互协议 | Contract Net（cfp → propose → accept/reject）、Subscribe/Notify、Request-When（满足条件 Y 时做 X） |
| 9 | 语义漂移 | 丢掉本体后，两个 agent 对同一个词（如 "customer"）理解不同，没有校验器能发现；缓解：content 上的 JSON Schema、类型化 artifact、信封中显式的 performative |
| 10 | 上线前的五个问题 | 每条消息的意图原语是什么？有没有关联 id（请求-响应、取消）？content language 是否明确？交互协议是否一等公民？语义分歧时怎么办？ |

### 核心技能（能动手做到）

- [ ] 写出一条完整的 FIPA-ACL 消息，并说出每个字段在 MCP/A2A 中的对应物
- [ ] 把任意 MCP / A2A 消息映射到最接近的 performative（讲义练习 1）
- [ ] 用 dataclass 实现 ACL 信封，并在 `__post_init__` 中做 performative 白名单校验
- [ ] 实现一个 manager + 多个 bidder 的 Contract Net，能计算评分并说出不同权重下谁中标
- [ ] 给 contract-net 加上 `cancel`，解释它解决了重试解决不了的什么问题（讲义练习 2）
- [ ] 为 `request` 的 content 设计一个最小 JSON Schema，并说出它的收益与代价（讲义练习 5）
- [ ] 用 `outputs/skill-fipa-mapper.md` 的六个维度评估一个新协议是"重新发明"还是"新结构"

---

## 二、基础自测（选择题）

**Q1.** 下列时间线与贡献的对应，正确的是：

- A. Austin（1962）提出 performative utterance；Searle（1969）形式化为五类；KQML（1993）做成软件 agent 的线协议；FIPA-ACL（2000）完成参考标准化
- B. Searle（1962）提出 performative；Austin（1969）分类；FIPA-ACL（1993）；KQML（2000）
- C. KQML 是 FIPA-ACL 的继任者，用于修补 FIPA 的缺陷
- D. FIPA-ACL 与 MCP 同年发布，二者互为竞争标准

**Q2.** 下列哪一项**不是**讲义列出的 FIPA 衰落原因？

- A. 解析 `content` 需要共享本体，而约定本体是长达数年的标准化过程
- B. SL 提供了严格的真值条件，但大多数生产系统用自由格式内容、忽略了形式化
- C. performative 数量太少，无法表达工具调用
- D. JADE 只支持 Java、JACK 是商业产品；以及 REST、JSON-RPC、gRPC 取代了 ACL 的传输

**Q3.** MCP 的 `resources/read` 在讲义映射表中对应哪个 FIPA performative？

- A. `inform`
- B. `request`
- C. `subscribe`
- D. `query-ref`

**Q4.** 讲义所说的"语义漂移（semantic drift）"指的是：

- A. 模型权重随时间变化导致输出变化
- B. 没有共享本体时，两个 agent 用同一个词（如 "customer"）指代略有不同的概念，接收方按错误理解行动，而没有任何 schema 校验器能发现
- C. JSON 字段名在版本升级中被重命名
- D. performative 的含义在不同 FIPA 版本中发生变化

**Q5.** 本节 contract-net 演示中，三个出价为 worker-a（price 3, eta 18）、worker-b（price 2, eta 25）、worker-c（price 4, eta 10），评分为 `price + eta_minutes / 10`，取最小。中标者及其分数是：

- A. worker-c，5.0
- B. worker-a，4.8
- C. worker-b，4.5
- D. worker-b，2.0

**Q6.** 讲义把 Request-When 列为值得移植的交互协议。在本节代码里执行 `ACLMessage("request-when", "a", "b", "x")` 会：

- A. 抛出 `ValueError: unknown performative: request-when`，因为代码的 `PERFORMATIVES` 集合只有 16 个，不含 `request-when`
- B. 正常构造，因为 `__post_init__` 只检查 sender
- C. 自动降级为 `request`
- D. 抛出 `KeyError`

**Q7.** 讲义 Build It 说代码"Encodes five MCP-style and A2A-style messages as FIPA-ACL"并"Decodes FIPA-ACL back to the modern equivalent"，输出是"round-trip"。实际代码是：

- A. 与讲义完全一致
- B. 编码了五条消息，但解码只实现了 MCP 部分
- C. 只有解码，没有编码
- D. 只编码了四条（tools/call、resources/read、A2A 建任务、A2A 订阅），而且只有"现代 → ACL"单向转换，没有任何解码函数

**Q8.** 讲义映射表中，"A2A streaming events"对应的 FIPA 概念及它丢掉的东西是：

- A. `cfp`；丢掉了出价机制
- B. subscribe/notify；丢掉了"类型化谓词订阅"（typed-predicate subscription）
- C. `inform`；丢掉了关联 id
- D. blackboard；丢掉了逻辑一致性模型

---

## 三、动手 / 代码题

**Q9.** 阅读 `mcp_tools_call_to_acl` 及其输出：

```python
def mcp_tools_call_to_acl(req: dict) -> ACLMessage:
    return ACLMessage(
        performative="request",
        sender="host",
        receiver="tool-server",
        content=req["params"].get("arguments", {}),
        language="JSON",
        ontology=req["params"]["name"],
        protocol="fipa-request",
        conversation_id=f"jsonrpc-{req['id']}",
        reply_with=f"msg-{req['id']}",
    )
```

```text
(request
  :sender       host
  :receiver     tool-server
  :content      {'symbol': 'IBM'}
  :language     JSON
  :ontology     lookup_stock
  ...
```

1. 对照讲义里 FIPA 的规范示例（`:content "(lookup stock IBM)"`、`:ontology finance`），`:ontology lookup_stock` 有什么问题？`:language JSON` 与实际打印的 content 一致吗？
2. 写一个 `acl_to_modern(m)` 解码函数，让 tools/call、resources/read、A2A 建任务三种消息都能 round-trip（`decode(encode(x)) == x`）。解码时 `request` 有歧义，你靠哪个字段消歧？
3. `a2a_task_create_to_acl` 对缺失字段使用默认值（如 `task.get("task_id", "t-0")`）。这对关联 id 会造成什么问题？

**Q10.** 讲义练习 2：给 contract-net 加一个 `cancel`，让 manager 能在竞标中途撤回任务。

1. 写出 `cancel` 方法。
2. 当前 `ACLMessage` 缺少 FIPA 的 `in-reply-to` 字段。这对 `propose` 回复 `cfp`、`cancel` 指向原请求有什么影响？
3. `cancel` 解决了什么单靠重试（retry）解决不了的失败场景？

**Q11.** 评分函数敏感性（手算 + 推导）。把评分改成 `price + w · eta_minutes`（w ≥ 0）：

1. 求 worker-b 与 worker-c 分数相等时的 w，以及 worker-a 分别与 b、c 相等时的 w。
2. 由此说明在所有 w ≥ 0 下谁可能中标、谁永远不会中标。
3. 这对"把评分逻辑写死在 manager 里"意味着什么？

**Q12.** 讲义练习 5：为你系统中 `request` performative 的 `content` 设计一个最小 JSON Schema，并在 `ACLMessage` 中做校验。说明它相比纯自然语言给你带来了什么、代价是什么。

---

## 四、面试高频题

**Q13.**（基础必考）什么是言语行为理论和 performative？一条 FIPA-ACL 消息由哪些字段组成？请把它和一条 MCP `tools/call` 请求逐字段对照。

**Q14.**（原理深挖）FIPA-ACL 为什么在工业界衰落？现代 agent 协议（MCP、A2A 等）相对 FIPA 做了什么取舍？讲义说"keep the structural primitive, drop the formalism, let LLMs paper over the ambiguity"，你怎么评价？

**Q15.**（工程实践）你们的多 agent 系统里，订单 agent 和客服 agent 对 "customer" 的理解不一致，导致退款发错了对象。请分析根因并给出不走"完整本体"路线的修复方案。

**Q16.**（场景设计）用 LLM agent 实现一个任务市场：一个调度 agent 把"压缩 10GB 日志"之类的任务分给若干 worker agent。请用 Contract Net 设计完整的消息流，包括超时、拒绝、失败、取消和完成通知。

**Q17.**（追问型）有人说"A2A、MCP 不过是换了 JSON 语法的 FIPA，没有任何新东西"。你同意吗？哪些是重新发明，哪些是真正的新结构？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Speech-act theory from Austin (1962) and Searle (1969) gave us 'utterances are actions.' KQML (1993) turned that into a wire protocol. FIPA-ACL (ratified 2000) produced the reference standardization." B 把人名和年份都弄乱了；C 说反了，KQML 是前身（Key Terms："FIPA's predecessor"）；D 错，MCP 是 2020 年代的协议。

### Q2 — 答案：C

讲义 "Why FIPA faded" 四条：Ontology overhead（A）、Formal semantics nobody used（B）、Tooling lock-in 与 The internet won the stack（D）。C 恰好相反：讲义的观点是 performative 足够丰富，"every one of these corresponds to a primitive an LLM protocol eventually re-adds"，`request` 就能表达工具调用。

### Q3 — 答案：D

讲义映射表：`MCP resources/read` ↔ `query-ref`（"What is the value of X?"），保留显式意图与关联 id，丢掉形式语义。代码中 `mcp_resources_read_to_acl` 也是 `performative="query-ref"`。`request` 对应的是 `tools/call`；`subscribe` 对应 A2A 流式事件；`inform` 是陈述"P 为真"。

### Q4 — 答案：B

讲义："two agents use the same word ('customer') for subtly different concepts, the receiver's agent acts on the wrong interpretation, no schema validator catches it. FIPA's ontology requirement would have rejected the message at parse time." A、C、D 都是别的问题。

### Q5 — 答案：C

worker-a：`3 + 18/10 = 4.8`；worker-b：`2 + 25/10 = 4.5`；worker-c：`4 + 10/10 = 5.0`。最小的是 worker-b，4.5。程序输出 `Winner: worker-b (price 2, eta 25m)`，随后给 worker-b 发 `accept-proposal`，给 a、c 发 `reject-proposal`。D 只比较了价格；A、B 是另外两人的分数。

### Q6 — 答案：A

已实际运行：`ValueError: unknown performative: request-when`。`PERFORMATIVES` 只收录了讲义"partial list"表中的 16 个；讲义称 FIPA 有约 20 个 performative（FIPA 通信行为库实际还包括 `inform-if`、`inform-ref`、`propagate`、`proxy`、`request-when`、`request-whenever` 等），所以讲义推荐移植的 Request-When 恰恰无法用这份代码表达。B 错，校验的正是 performative；C 代码没有降级逻辑；D 错，抛的是 `ValueError`。

### Q7 — 答案：D

`demo_round_trip()` 依次处理 `tools/call`、`resources/read`、A2A `POST /tasks`、A2A SSE subscribe——共四条，且每条只调用 `*_to_acl` 后 `render()`，文件中没有任何 ACL → JSON 的函数。标题 "Round-trip: 2026 JSON-RPC / REST <-> FIPA-ACL envelope" 的双向箭头名不副实。练习 1 要你"Observe the round-trip encoding"也就无从观察。Q9 第 2 问让你补上解码。

### Q8 — 答案：B

讲义表格："A2A streaming events | subscribe/notify | async push | typed-predicate subscription"。FIPA 的 `subscribe` 内容是一个带类型的谓词（"当这个条件变化时通知我"），A2A 只是按任务推送事件。A 的 `cfp` 对应任务招标；D 的 blackboard 对应 CA-MCP 共享上下文。

### Q9 — 参考答案

1. **ontology 被挪作他用**：FIPA 中 ontology 是"content 所用的概念词汇"（如 `finance`），动作与参数应该在 content 里（`(lookup stock IBM)`）。代码把**工具名** `lookup_stock` 塞进 `:ontology`，于是 content 只剩参数 `{'symbol': 'IBM'}`，"要做什么"和"用什么词汇"被混在一个字段里；MCP 的方法名 `tools/call` 本身则完全丢失。**language 与 content 不一致**：`render()` 用 `{self.content!r}` 打印，得到的是 Python repr `{'symbol': 'IBM'}`（单引号），并不是合法 JSON；A2A 那条 `:language JSON` 的 content 是一段 Python 源码字符串；contract-net 消息 `:language SL0`（默认值），content 却是 Python 字典或英文短语。声明的 content language 名存实亡——这正是讲义说的"looser semantics"。
2. 参考实现（已实际运行，三种消息 `decode(encode(x)) == x` 均为 True）：

```python
def acl_to_modern(m: ACLMessage) -> dict:
    if m.performative == "request" and m.protocol == "fipa-request":
        rid = int(m.conversation_id.removeprefix("jsonrpc-"))
        return {"jsonrpc": "2.0", "method": "tools/call",
                "params": {"name": m.ontology, "arguments": m.content}, "id": rid}
    if m.performative == "query-ref":
        rid = int(m.conversation_id.removeprefix("jsonrpc-"))
        return {"jsonrpc": "2.0", "method": "resources/read",
                "params": {"uri": m.content}, "id": rid}
    if m.performative == "request" and m.protocol == "a2a-task":
        return {"client": m.sender, "agent": m.receiver, "skill": m.ontology,
                "input": m.content, "task_id": m.conversation_id}
    raise ValueError(f"no modern mapping for {m.performative}/{m.protocol}")
```

   `tools/call` 与 A2A 建任务都是 `request`，只能靠 `:protocol`（`fipa-request` vs `a2a-task`）消歧。这说明 performative 只表达意图类别，**具体用哪个交互协议**必须另有字段说明——FIPA 把 protocol 设为独立字段是有道理的。另外 round-trip 能成功，部分是因为解码器"知道"编码器把工具名放进了 ontology；换一个编码器就不成立。`removeprefix` 需要 Python 3.9+。
3. 缺 `task_id` 的任务全部得到 `conversation_id = "t-0"`、`reply_with = "t-0"`（实测 `{"input": "x"}` 解码出 `task_id: 't-0'`）。多个任务共享同一个关联 id，回复、事件、取消会被错配到别的任务上。关联 id 应由发送方生成唯一值（如 UUID），缺失时宁可报错也不要用常量默认值。

### Q10 — 参考答案

1. 实现（已实际运行，三个 bidder 各收到一条 `cancel`）：

```python
    def cancel(self, conv: str, reason: str) -> None:
        for b in self.bidders:
            self.log.append(ACLMessage(
                performative="cancel",
                sender=self.manager,
                receiver=b,
                content={"reason": reason},
                ontology="contract-net",
                protocol="fipa-contract-net",
                conversation_id=conv,
            ))
```

   若已经发过 `accept-proposal`，`cancel` 只需发给中标者；还应记录会话状态（`open / awarded / cancelled`），状态为 cancelled 后再收到的 `propose` 直接回 `reject-proposal` 或忽略。
2. 没有 `in-reply-to`，`propose` 无法声明"我回复的是 `cfp-worker-a` 这条"，只能靠 `conversation_id` 粗粒度关联；同一会话里有多轮 cfp（重新招标）时就分不清某个出价回应的是哪一轮。代码给 cfp 设了 `reply_with=f"cfp-{b}"`，却没有任何消息引用它，等于白设。`cancel` 同理：FIPA 中 cancel 应指向被取消的那条请求。修复：给 `ACLMessage` 加 `in_reply_to: Optional[str] = None`，`propose` 填入对应 cfp 的 `reply_with`。
3. 重试解决的是**消息丢失或暂时失败**（同一个意图再发一次）；`cancel` 解决的是**意图本身变了**：任务被撤销、需求变化、已由别人完成、预算被砍。没有 cancel，bidder 会继续为一个已经不需要的任务预留资源甚至开始执行；对长任务（压缩 10GB 日志）而言，这既浪费资源，又可能产生重复的副作用。现代对应物：A2A 的任务取消、MCP 的取消通知（讲义配图）。

### Q11 — 参考答案

1. 分数：a = 3 + 18w，b = 2 + 25w，c = 4 + 10w。
   - b = c：2 + 25w = 4 + 10w → w = 2/15 ≈ 0.133；
   - a = b：3 + 18w = 2 + 25w → w = 1/7 ≈ 0.143；
   - a = c：3 + 18w = 4 + 10w → w = 1/8 = 0.125。
2. w < 2/15 时 b 最低（w = 0.1 就是演示用的 1/10，b = 4.5）；w > 2/15 时 c 最低（实测 w = 0.14：a 5.52、b 5.50、c 5.40）。a 要中标需同时 a < b（w > 1/7）且 a < c（w < 1/8），而 1/7 > 1/8，不可能同时成立——**worker-a 在任何 w ≥ 0 下都不会中标**。它在价格和时间上都不是最优，只是"折中"，而线性加权评分永远不会选中这种被两端"夹住"的方案。
3. 评分权重是业务决策（重价格还是重时效），却被写死成 `/ 10`，单位还不统一（价格无量纲、时间按分钟）。生产中应把评分函数作为 cfp 的一部分公开（让 bidder 知道规则），或允许 manager 配置；价格和时间应先归一化；还应定义平局规则（`min` 遇到平局返回先出现的那个，结果依赖消息到达顺序）。

### Q12 — 参考答案

最小 schema（JSON Schema 写法）：

```json
{
  "type": "object",
  "required": ["tool", "arguments"],
  "additionalProperties": false,
  "properties": {
    "tool": {"type": "string", "pattern": "^[a-z_]+$"},
    "arguments": {"type": "object"}
  }
}
```

标准库下的简化校验（已实际运行）：

```python
SCHEMA = {"tool": str, "arguments": dict}

def validate(content, schema):
    if not isinstance(content, dict):
        return ["content must be an object"]
    errs = [f"missing {k}" for k in schema if k not in content]
    errs += [f"{k} must be {t.__name__}" for k, t in schema.items()
             if k in content and not isinstance(content[k], t)]
    errs += [f"unexpected {k}" for k in content if k not in schema]
    return errs

# 在 ACLMessage.__post_init__ 里：
#   if self.performative == "request":
#       errs = validate(self.content, SCHEMA)
#       if errs: raise ValueError(errs)
```

`{"tool": "lookup_stock", "args": {...}}` 会得到 `['missing arguments', 'unexpected args']`。

- **收益**：结构性错误在线上被拒绝（讲义 "rejects structural errors at the wire"），而不是等到下游 agent 误解后才暴露；接口有了可读的契约；可以自动生成文档和测试；工具名与参数分离后，ontology 字段可以回归"词汇表"的本义。
- **代价**：schema 需要版本管理与协调（这正是 FIPA 本体的老问题，只是规模小得多）；灵活性下降，LLM 生成的内容必须严格满足格式（可配合 structured output）；**schema 只能防结构错误，防不了语义漂移**——`customer_id` 字段类型正确但指代错了，schema 照样放行。

### Q13 — 参考回答要点

- **言语行为**：Austin 指出有些话语本身就是行动（承诺、请求、宣告），称为 performative utterance；Searle 分为 assertive、directive、commissive、expressive、declarative 五类。
- **Performative**：消息的"动词"，表达发送者的意图类别，与内容分离。
- **FIPA-ACL 字段**：performative + sender、receiver、content、language、ontology、protocol、conversation-id、reply-with（FIPA 还定义了 in-reply-to、reply-by 等）。
- **与 MCP `tools/call` 对照**：

| FIPA-ACL | MCP JSON-RPC |
|---------|-------------|
| `request`（performative） | `"method": "tools/call"` |
| `:sender` / `:receiver` | 由传输连接隐含（host ↔ server） |
| `:content` | `params.arguments`（+ `params.name`） |
| `:language` | 隐含为 JSON |
| `:ontology` | 无（工具的 input schema 部分承担此角色） |
| `:conversation-id` / `:reply-with` | `"id": 42` |

- 讲义结论："Same envelope, different syntax. Both carry: who, whom, intent, payload, correlation id."

### Q14 — 参考回答要点

- **衰落原因**：本体开销（共享本体需要多年标准化）；形式语义 SL 很严谨但生产中没人用；JADE（Java）与 JACK（商业）造成工具锁定；Web 技术栈（REST → JSON-RPC → gRPC）赢得了传输层。
- **现代规范的取舍**：
  - 丢掉：形式语义（无法证明 `inform` 意味着发送者相信内容）、标准 performative 目录（每个新协议都要重新争论"要不要 cancel"）、有已知正确性性质的交互协议库；
  - 得到：JSON 原生载荷、LLM 可直接理解的自然语言内容、HTTP/SSE/WebSocket 传输、能力发现（MCP 工具列表、A2A Agent Card）。
- **评价**：
  - 合理的一面：本体是 FIPA 失败的主因，LLM 能在一定程度上理解非形式化内容，降低了集成门槛；
  - 风险：歧义被"糊过去"而不是被消除，语义漂移在运行时才暴露，且很难被测试发现；
  - 折中：保留显式 performative 和关联 id，对关键 content 用 schema 和类型化 artifact，只在边缘场景用自然语言。
- 加分点：引用讲义的 Ship It 五问；指出 Liu et al.（arXiv:2505.02279）把 MCP、A2A、ACP、ANP 分别对应到工具调用、agent 对等、审计追踪、去中心化身份四类言语行为。

### Q15 — 参考回答要点

- **根因**：两个 agent 之间用自然语言或松散 JSON 传递 "customer"，订单域的 customer 可能是"下单账户"，客服域的 customer 可能是"来电联系人"。没有共享词汇定义，也没有校验能发现"字段对、含义错"。这就是讲义的 semantic drift。
- **修复（不走完整本体）**：
  1. 用带域前缀的明确 ID 类型替代模糊名词（`order_account_id`、`contact_person_id`），并在 JSON Schema 中约束格式；
  2. 维护一个小型共享词汇表（几十个核心实体的定义），作为 agent system prompt 和 schema 描述的共同来源——相当于"轻量本体"；
  3. 关键操作（退款）使用类型化 artifact 和显式 performative（如 `request` + `refund` schema），接收方在执行前回显理解结果（`confirm`），发送方确认后再执行；
  4. 写跨 agent 的契约测试，覆盖易混淆实体；
  5. 对不可逆操作加 human-in-the-loop 或二次校验。
- 加分点：说明 schema 只能挡结构错误，挡不住语义错误，所以第 2、3 条才是关键。

### Q16 — 参考回答要点

消息流（FIPA Contract Net 的完整形态）：

1. manager → 所有 worker：`cfp`（任务描述、评分规则、截止时间 reply-by、唯一 conversation-id）；
2. worker → manager：`propose`（价格、预计耗时、in-reply-to 指向 cfp）或 `refuse`（没能力/没空）；截止时间到仍未回复的视为放弃；
3. manager 评估 → 中标者 `accept-proposal`，其余 `reject-proposal`；
4. 中标者执行 → 完成后 `inform`（附结果 artifact），失败则 `failure`（附原因）；
5. manager 可在任意阶段 `cancel`（任务撤回），worker 收到后停止并确认；
6. manager 收到 `failure` 或执行超时 → 在剩余出价者中重新授标或重新发 cfp。

工程要点：

- 传输：消息队列或 A2A；所有消息带 conversation-id / in-reply-to，落日志可回放；
- 超时：每个阶段都有 deadline；
- 幂等：worker 按 conversation-id 去重，避免重复执行；
- 出价可信度：LLM worker 可能"乐观报价"，用历史完成率做声誉加权（阶段 16 · 21 Agent 经济）；
- 评分规则随 cfp 公开，并定义平局规则（见 Q11）。

### Q17 — 参考回答要点

- **大部分同意，但不完全**。按 `skill-fipa-mapper.md` 的标准，只有引入了 FIPA 没有的原语，才算 "novel-structure"。
- **重新发明（reinvention）**：
  - `tools/call` ≈ `request`，`resources/read` ≈ `query-ref`，流式事件 ≈ subscribe/notify，任务生命周期 ≈ contract-net + request-when，取消 ≈ `cancel`；
  - JSON-RPC 的 `id` ≈ `conversation-id`/`reply-with`；
  - 能力发现：FIPA 也有 directory facilitator（黄页服务），A2A Agent Card、MCP 工具列表是它的 Web 化版本。
- **真正的新结构（novel-structure）**——skill 文件列出的常见候选：
  - LLM 可解释的自然语言 content（不需要手写本体）；
  - 类型化的多模态 artifact；
  - 去中心化身份（ANP 的 DID）。
- **会被重新发现的老问题**：语义漂移（没有本体）、交互协议的正确性（死锁、遗漏的 cancel/failure 分支）、关联 id 管理。
- 常见误区：宣称某协议"革命性"却说不出它有哪个 FIPA 没有的原语——skill 文件把这列为 hard reject。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 01 为什么需要多 Agent？](../../01-why-multi-agent/docs/zh.md)：agent 之间为什么需要消息传递，本节讨论消息"应该长什么样"。
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../../13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md)：`tools/call`、`resources/read` 的 JSON-RPC 形态。
- [阶段 13 · 19 A2A：Agent 与 Agent 之间的通信协议](../../../13-tools-and-protocols/19-a2a-protocol/docs/zh.md)：A2A 任务生命周期与流式事件。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../../13-tools-and-protocols/04-structured-output/docs/zh.md)：给 content 加 schema 的工具。

### 本节被哪些后续内容用到
- [阶段 16 · 03 通信协议](../../03-communication-protocols/docs/zh.md)：MCP、A2A、ACP、ANP 等现代协议的详细对比。
- [阶段 16 · 12 A2A：Agent 与 Agent 之间的通信协议](../../12-a2a-protocol/docs/zh.md)：contract-net 与 subscribe/notify 的现代实现。
- [阶段 16 · 13 共享记忆与黑板模式](../../13-shared-memory-blackboard/docs/zh.md)：讲义映射表中 CA-MCP 共享上下文 ↔ blackboard。
- [阶段 16 · 16 协商与议价](../../16-negotiation-bargaining/docs/zh.md)：Contract Net 作为任务市场的展开。
- [阶段 16 · 21 Agent 经济体系、Token 激励与声誉](../../21-agent-economies/docs/zh.md)：出价可信度与声誉机制。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../22-production-scaling-queues-checkpoints/docs/zh.md)：Request-When 在 durable workflow 中的对应物。

### 延伸关键词
`speech act` · `performative` · `KQML` · `FIPA-ACL` · `SL0 / SL1` · `ontology` · `JADE` · `BDI` · `Contract Net Protocol` · `subscribe / notify` · `request-when` · `conversation-id / in-reply-to` · `semantic drift` · `directory facilitator` · `Agent Card`
