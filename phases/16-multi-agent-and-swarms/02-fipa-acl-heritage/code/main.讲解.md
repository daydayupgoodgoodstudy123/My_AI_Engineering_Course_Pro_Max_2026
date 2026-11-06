# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 02 节 FIPA-ACL 与言语行为理论的历史基础 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`typing`），无需网络

---

## 1. 这份代码在考察什么

这份约 250 行的脚本用纯标准库实现了两件事：

1. **翻译器**：把 2026 年的 agent 协议消息（MCP `tools/call`、MCP `resources/read`、A2A 建任务、A2A SSE 订阅）翻译成 FIPA-ACL 信封并打印，直观展示讲义的核心论点——"Same envelope, different syntax"。
2. **Contract Net 演示**：一个 manager 向三个 bidder 发 `cfp`，收集 `propose`，按评分选出中标者，发 `accept-proposal` / `reject-proposal`。

对应讲义的概念：performative（意图类别）、ACL 信封字段、现代规范到 FIPA 的映射表、值得移植的交互协议（Contract Net）。

> 一句话：**协议的骨架（谁、发给谁、什么意图、载荷、关联 id）二十多年没变，变的是语法和语义的严格程度。** 同时也要看到，这份代码本身就是"松散语义"的样本：它声明的 language、ontology 与实际内容并不相符。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PERFORMATIVES` | 模块级集合 | 允许的 16 个 performative | FIPA performative 目录（部分） |
| `ACLMessage` | dataclass | ACL 信封：performative + 8 个字段；`__post_init__` 校验 performative；`render()` 输出 FIPA 文本格式 | ACL 消息结构 |
| `mcp_tools_call_to_acl` | 函数 | `tools/call` → `request` | MCP ↔ FIPA |
| `mcp_resources_read_to_acl` | 函数 | `resources/read` → `query-ref` | MCP ↔ FIPA |
| `a2a_task_create_to_acl` | 函数 | A2A `POST /tasks` → `request`（protocol=`a2a-task`） | A2A ↔ FIPA |
| `a2a_subscribe_to_acl` | 函数 | A2A SSE 订阅 → `subscribe` | subscribe/notify |
| `Bid` | dataclass | 出价：bidder、price、eta_minutes | 投标内容 |
| `ContractNet` | dataclass | manager、bidders、消息日志；方法 `cfp` / `propose` / `award` | Contract Net Protocol |
| `demo_round_trip` | 函数 | 打印四条现代消息及其 ACL 形式 | 映射演示 |
| `demo_contract_net` | 函数 | 跑一轮招标并打印全部消息 | 交互协议演示 |
| `main` | 函数 | 依次调用两个 demo，打印结论 | 驱动 |

数据流：`main` → `demo_round_trip`（dict → `*_to_acl` → `ACLMessage.render()` → 打印）→ `demo_contract_net`（`ContractNet.cfp` → 3 × `propose` → 选 winner → `award` → 遍历 `log` 打印）。

---

## 3. 逐段精讲

### 3.1 performative 白名单

```python
PERFORMATIVES = {
    "inform", "request", "query-if", "query-ref", "propose",
    "accept-proposal", "reject-proposal", "agree", "refuse",
    "confirm", "disconfirm", "not-understood", "cfp",
    "subscribe", "cancel", "failure",
}
```

- 用**集合**存储，`in` 判断是 O(1)。
- 共 16 个，正好是讲义 "The twenty FIPA performatives (partial list)" 表格里的 16 行。
- ⚠️ 讲义推荐移植的 Request-When 协议对应的 `request-when` performative 不在集合里，`ACLMessage("request-when", ...)` 会抛 `ValueError`（已实测）。FIPA 通信行为库还有 `inform-if`、`inform-ref`、`propagate`、`proxy`、`request-whenever` 等。

### 3.2 `ACLMessage`：信封与校验

```python
@dataclass
class ACLMessage:
    performative: str
    sender: str
    receiver: str
    content: Any
    language: str = "SL0"
    ontology: str = "default"
    protocol: Optional[str] = None
    conversation_id: Optional[str] = None
    reply_with: Optional[str] = None

    def __post_init__(self) -> None:
        if self.performative not in PERFORMATIVES:
            raise ValueError(f"unknown performative: {self.performative}")
```

- 字段与讲义的"规范 FIPA-ACL 消息"一一对应：performative 是"动词"；sender/receiver 是"谁发给谁"；content 是载荷；language/ontology 说明"载荷怎么读"；protocol 说明属于哪个交互协议；conversation_id/reply_with 用于关联。
- `__post_init__` 是 dataclass 在自动生成的 `__init__` 末尾调用的钩子，适合做校验。这就是讲义说的"explicit performative in the envelope"——意图在**信封**里是显式且受约束的，即使 content 是自然语言。
- `content: Any`：载荷可以是任何对象（字典、字符串）。
- ⚠️ 与 FIPA 相比缺少的字段：`in-reply-to`（回复指向哪条消息）、`reply-by`（截止时间）、`reply-to`、`encoding`；receiver 只能是一个（FIPA 允许接收者集合，所以代码的 `cfp` 要发 N 条）。缺 `in-reply-to` 意味着 `propose` 无法声明它回复的是哪条 `cfp`。
- ⚠️ 只校验 performative，不校验 content 是否符合 language 和 ontology。

```python
    def render(self) -> str:
        fields = [
            f":sender       {self.sender}",
            f":receiver     {self.receiver}",
            f":content      {self.content!r}",
            f":language     {self.language}",
            f":ontology     {self.ontology}",
        ]
        if self.protocol:
            fields.append(f":protocol     {self.protocol}")
        ...
        inner = "\n  ".join(fields)
        return f"({self.performative}\n  {inner}\n)"
```

- 输出 FIPA 的 S 表达式风格：`(performative :key value ...)`。
- 可选字段为空（`None`）时不输出，所以 `subscribe` 消息没有 `:reply-with` 行、contract-net 的 `accept-proposal` 也没有。
- `{self.content!r}` 用 `repr()` 打印：字典显示为 `{'symbol': 'IBM'}`，字符串带引号 `'file:///etc/hosts'`。⚠️ 这是 Python 字面量，不是 JSON，也不是 SL0。
- 局部变量名 `fields` 与 `dataclasses.field` 无关（模块导入的是 `field`，没有冲突），但读代码时容易混淆。

### 3.3 四个翻译函数

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

| 现代消息 | performative | content | ontology | protocol | 关联 id |
|---------|-------------|---------|---------|---------|--------|
| MCP `tools/call` | `request` | `arguments` 字典 | **工具名** | `fipa-request` | `jsonrpc-<id>` / `msg-<id>` |
| MCP `resources/read` | `query-ref` | URI 字符串 | `mcp-resource` | `fipa-query` | `jsonrpc-<id>` / `msg-<id>` |
| A2A `POST /tasks` | `request` | `input`（这里是一段 Python 代码） | skill 名 | `a2a-task` | `task_id` |
| A2A SSE 订阅 | `subscribe` | `{task_id, event_types}` | `a2a-events` | `fipa-subscribe` | `task_id`（无 reply_with） |

要点与问题：

- **JSON-RPC 的 `id` 被映射成 conversation-id 和 reply-with**：这正是讲义说的"correlation id"在两边的对应。
- ⚠️ **ontology 被挪作他用**：FIPA 中 ontology 是概念词汇表（讲义示例为 `finance`），代码却把工具名、skill 名放进去，动作与词汇混在一个字段里；MCP 方法名 `tools/call` 本身则没有被保留。
- ⚠️ **歧义**：`tools/call` 与 A2A 建任务都映射为 `request`，只能靠 `protocol` 字段区分——如果要写解码器，`protocol` 是唯一的消歧依据（测验 Q9）。
- ⚠️ **硬编码的 sender/receiver**：MCP 消息本身没有发送方/接收方字段（由连接隐含），代码填了常量 `host`、`tool-server`。
- ⚠️ **常量默认值**：`a2a_task_create_to_acl` 在缺 `task_id` 时用 `"t-0"`，所有缺 id 的任务会共享同一个关联 id。
- `req["params"].get("arguments", {})`：`.get` 带默认值，缺参数时返回空字典；而 `req["params"]["name"]` 用方括号，缺工具名会直接 `KeyError`——必需字段与可选字段的区别。

### 3.4 `Bid` 与 `ContractNet`

```python
@dataclass
class ContractNet:
    manager: str
    bidders: list[str]
    log: list[ACLMessage] = field(default_factory=list)

    def cfp(self, task: str, conv: str) -> None:
        for b in self.bidders:
            self.log.append(ACLMessage(
                performative="cfp",
                sender=self.manager,
                receiver=b,
                content=task,
                ontology="contract-net",
                protocol="fipa-contract-net",
                conversation_id=conv,
                reply_with=f"cfp-{b}",
            ))
```

- `field(default_factory=list)`：可变默认值必须用工厂函数，每个实例得到**自己的**空列表。若写成 `log: list = []`，dataclass 会直接报错（防止所有实例共享同一个列表）。我们实测两个 `ContractNet` 实例的 `log` 不是同一个对象。
- `cfp` 对每个 bidder 发一条消息（广播 = N 条单播），共享 conversation-id `cn-1`。
- `propose` 把 `Bid` 的 price 和 eta 放进 content 字典；`Bid.bidder` 字段与 `propose` 的第一个参数重复，实际没有被用到。
- `award` 给中标者发 `accept-proposal`，给其余每人发 `reject-proposal`。
- ⚠️ 所有 contract-net 消息的 `language` 都是默认的 `SL0`，content 却是 Python 字典或英文短语。
- ⚠️ 这里的"agent"只是字符串名，所有消息都由同一段代码写进同一个 `log`，没有真正的异步收发；也没有 `refuse`（bidder 拒绝出价）、截止时间、`inform`/`failure`（执行完成或失败的通知）——FIPA 的 Contract Net 在授标之后还要求中标者报告结果。

### 3.5 选出中标者

```python
    proposes = [m for m in cn.log if m.performative == "propose"]
    winner = min(proposes, key=lambda m: m.content["price"] + m.content["eta_minutes"] / 10)
    losers = [m.sender for m in proposes if m.sender != winner.sender]
    cn.award(winner.sender, losers, conv)
```

- 列表推导式从日志中筛出全部 `propose`——manager 是"读消息"而不是"读 Bid 对象"来决策的，这符合消息驱动的思路。
- 评分 `price + eta/10`：a = 3 + 1.8 = 4.8，b = 2 + 2.5 = 4.5，c = 4 + 1.0 = 5.0，b 中标。
- 敏感性：把 1/10 换成权重 w，`w < 2/15 ≈ 0.133` 时 b 中标，`w > 2/15` 时 c 中标；a 在任何 w ≥ 0 下都不会中标（测验 Q11）。
- `min` 遇到平局返回第一个出现的元素，即平局时由消息到达顺序决定。
- ⚠️ 评分规则写死在 manager 里，且没有随 `cfp` 告知 bidder。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| dataclass 表示 ACL 信封 | 字段清晰，自动生成构造函数 | 生产会用 Pydantic / JSON Schema 做完整校验与序列化 |
| 只校验 performative | 体现"信封中显式意图"这一核心 | content、language、ontology 都不受约束；应按 performative 绑定 content schema |
| 白名单只有 16 个 | 与讲义表格一致 | 缺 `request-when` 等，讲义推荐的协议无法表达 |
| `render()` 用 `repr` | 简单 | 输出既不是 JSON 也不是 SL0；应用 `json.dumps` 或真正的 SL 编码 |
| 工具名放进 ontology | 让 round-trip 时工具名有处可放 | 混淆 ontology 的本义；应放进 content（`{"tool": ..., "arguments": ...}`） |
| 只有编码、没有解码 | 演示单向映射即可说明观点 | 讲义声称的 round-trip 并未实现；测验 Q9 补上 |
| 同步、单进程的 Contract Net | 便于打印完整消息轨迹 | 真实系统需要异步传输、超时、`refuse`/`failure`/`cancel`、幂等 |
| 固定评分 `price + eta/10` | 一行代码说明"manager 做决策" | 权重是业务决策，应配置化、归一化，并随 cfp 公开 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可写 `list[str]` 等新语法 |
| 集合字面量 | `PERFORMATIVES = {"inform", "request", ...}` | 无序、去重，成员判断快 |
| `@dataclass` | `class ACLMessage`、`class Bid`、`class ContractNet` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| 字段默认值 | `language: str = "SL0"` | 有默认值的字段必须排在无默认值字段之后 |
| `field(default_factory=list)` | `log: list[ACLMessage] = field(default_factory=list)` | 可变默认值要用工厂函数，避免实例间共享 |
| `__post_init__` | `def __post_init__(self) -> None:` | dataclass 构造完成后自动调用，常用于校验 |
| `typing.Any` / `Optional` | `content: Any`、`protocol: Optional[str] = None` | 任意类型；"该类型或 None" |
| 抛出异常 | `raise ValueError(f"unknown performative: ...")` | 非法输入立即失败 |
| f-string 的 `!r` | `f":content      {self.content!r}"` | 用 `repr()` 而不是 `str()` 格式化，字符串会带引号 |
| `str.join` | `"\n  ".join(fields)` | 用指定分隔符拼接列表 |
| 字典取值 | `req["params"]["name"]` vs `req["params"].get("arguments", {})` | 方括号缺键报 `KeyError`；`.get` 可给默认值 |
| 列表推导式 + 条件 | `[m for m in cn.log if m.performative == "propose"]` | 过滤 |
| `min` + `key` + `lambda` | `min(proposes, key=lambda m: ...)` | 按自定义评分取最小元素 |
| 关键字参数 | `ACLMessage(performative="cfp", sender=self.manager, ...)` | 字段多时按名传参更清晰 |
| 字符串乘法 | `"=" * 72` | 分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行输出（节选）：

```text
-- MCP tools/call --
{'jsonrpc': '2.0', 'method': 'tools/call', 'params': {'name': 'lookup_stock', 'arguments': {'symbol': 'IBM'}}, 'id': 42}
as ACL:
(request
  :sender       host
  :receiver     tool-server
  :content      {'symbol': 'IBM'}
  :language     JSON
  :ontology     lookup_stock
  :protocol     fipa-request
  :conversation-id jsonrpc-42
  :reply-with   msg-42
)

-- A2A SSE subscribe --
(subscribe
  :sender       research-host
  :receiver     code-review-agent
  :content      {'task_id': 't-12', 'event_types': ['state', 'artifact']}
  :language     JSON
  :ontology     a2a-events
  :protocol     fipa-subscribe
  :conversation-id t-12
)

... （3 条 cfp、3 条 propose）

(accept-proposal
  :sender       scheduler
  :receiver     worker-b
  :content      'awarded'
  :language     SL0
  ...
)

Winner: worker-b (price 2, eta 25m)
```

逐项解读：

- **tools/call → request**：JSON-RPC `id: 42` 变成 `jsonrpc-42`（conversation-id）和 `msg-42`（reply-with）；工具名出现在 `:ontology` 行，参数出现在 `:content` 行。
- **resources/read → query-ref**：`:language URI`，content 为 `'file:///etc/hosts'`（带引号，因为是 `repr`）。
- **A2A 建任务 → request**：与 tools/call 同为 `request`，区别只在 `:protocol a2a-task`。content `'def f(x): return x'` 是 Python 源码，`:language JSON` 与之不符。
- **A2A 订阅 → subscribe**：没有 `:reply-with` 行（字段为 None 时不输出）。
- **Contract Net**：一共 9 条消息——3 条 `cfp`（同一 conversation-id `cn-1`、不同 reply-with）、3 条 `propose`、1 条 `accept-proposal`（给 worker-b）、2 条 `reject-proposal`（给 a、c）。worker-b 分数 4.5 最低。
- **标题与实际不符**：输出标题是 "Round-trip ... <->"，但只有单向的 JSON → ACL，并且只有四条消息（讲义说五条）。
- **结论行**："MCP/A2A messages are FIPA-ACL envelopes with JSON syntax. The structural primitives survive; the ontology and formal semantics do not." ——输出本身就印证了后半句：ontology 和 language 字段已经沦为标签。

---

## 7. 动手改一改

1. **补上解码**（讲义练习 1 的前提）：写 `acl_to_modern()`，让三种消息 `decode(encode(x)) == x`；体会 `request` 的歧义只能靠 `protocol` 解决（参考测验 Q9）。
2. **修正字段语义**：把工具名移进 content（`{"tool": "lookup_stock", "arguments": {...}}`），ontology 改为领域词汇（如 `finance`）；`render()` 改用 `json.dumps` 输出 content，让 `:language JSON` 名副其实。
3. **加 `in_reply_to` 与 `cancel`**（讲义练习 2）：`propose` 引用对应 `cfp` 的 `reply_with`；实现 `ContractNet.cancel(conv, reason)`，并让会话进入 cancelled 状态后拒绝新的出价。
4. **补全 Contract Net**：加入 `refuse`（bidder 拒绝）、出价截止时间、授标后中标者的 `inform`（完成）或 `failure`（失败），失败时自动给次优出价者授标。
5. **评分配置化**：把权重作为 cfp content 的一部分发出，对价格和时间归一化，并定义平局规则；验证 w 跨过 2/15 时中标者从 b 变成 c。
6. **进阶**（讲义练习 5）：按 performative 绑定 content 的 JSON Schema，在 `__post_init__` 中校验；把 `PERFORMATIVES` 补齐 `request-when`，实现"条件满足时执行"的延迟请求。

---

## 8. 常见坑

- **把 ontology 当成"随便放个名字"的字段**：它表示 content 使用的概念词汇；动作和参数应放在 content。字段语义一旦混用，解码和跨系统互通都会出问题。
- **声明的 content language 与实际不符**：`:language JSON` 配 Python repr、`SL0` 配 Python 字典——接收方若真的按声明去解析就会失败。
- **以为 performative 能唯一确定消息类型**：`request` 同时对应 tools/call 和 A2A 建任务，必须结合 protocol。
- **用常量作为关联 id 的默认值**：`"t-0"` 会让不同任务的回复互相串线。
- **缺少 in-reply-to**：只有 conversation-id 时，同一会话多轮交互（重新招标、取消）无法精确对应。
- **可变默认值**：dataclass 中 `log: list = []` 会报错，必须用 `field(default_factory=list)`。
- **以为 schema 能解决语义漂移**：schema 只挡结构错误，"字段对、含义错"仍需共享词汇表和确认步骤（讲义 What breaks when you drop the ontology）。
