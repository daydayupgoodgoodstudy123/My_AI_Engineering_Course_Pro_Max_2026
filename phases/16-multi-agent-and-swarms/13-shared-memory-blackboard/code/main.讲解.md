# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 13 节 共享记忆与黑板模式 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`hashlib`、`threading`、`time`、`dataclasses`、`typing`），无需 API key、无需网络

---

## 1. 这份代码在考察什么

这份代码用不到 230 行标准库 Python，把讲义的三件事落成了可运行的玩具：

1. **两种共享状态拓扑**：`MessagePool`（完整消息池，所有人读全部）与 `Blackboard`（按 topic 发布/订阅，只推给订阅者）。
2. **Provenance（来源记录）**：每次写入都生成一个 `ProvenanceEntry`，记录写入者、时间戳、prompt 哈希、来源 URI，并预留了 `supersedes`（被取代条目）与 `flags`（标记）字段。
3. **Memory poisoning（记忆投毒）与只读 verifier**：retriever 把来源中的 "4.2%" 幻觉成 "42%"，summarizer、analyst 依次读池子并把错误数字带进结论；第二轮加入一个重新"取源"比对的 verifier，把不一致的条目标记出来。

> 一句话：**用一个"小数点丢失"的故事，演示共享状态如何把一个 agent 的幻觉洗白成全队的事实，以及独立核查为什么必要**。同时要注意：代码只演示了"发现"，没有演示"阻断"——RUN 2 的最终结论仍然是错的，这一点与讲义描述不一致，是本节最值得讨论的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ProvenanceEntry` | `@dataclass` | 一条共享状态记录 + 元数据 | Provenance、supersession、flag |
| `MessagePool` | 类 | 加锁的 append-only 列表，`write / read_all / flag` | 完整消息池 |
| `Blackboard` | 类 | `topic → 条目列表` + `topic → 回调列表`，`publish / subscribe / read_topic` | 黑板 + 订阅 |
| `FAKE_SOURCES` | 字典常量 | 模拟"互联网上的原文"，是 verifier 的独立事实来源 | Ground truth |
| `retrieval_agent` | 函数 | 读来源写池子；`hallucinate=True` 时把 4.2% 改成 42% | 投毒源头 |
| `summarizer_agent` | 函数 | 读最近一条 retriever 记录，写摘要 | 第一跳传播 |
| `analyst_agent` | 函数 | 读最近一条摘要，含 "42%" 就建议采用 | 第二跳传播 |
| `verifier_agent` | 函数 | 遍历带 `source_uri` 的条目，与原文全等比较，返回 `(id, 原因)` 列表 | 只读 verifier |
| `run_without_verifier` / `run_with_verifier` | 函数 | 两轮对照实验 | 投毒 vs 缓解 |
| `demo_blackboard` | 函数 | prices / alerts 两个 topic 的订阅演示 | 选择性路由 |

数据流：`main()` → RUN 1（retriever → summarizer → analyst → 打印池）→ RUN 2（retriever → summarizer → **verifier → 调用方 flag** → analyst → 打印池）→ 黑板演示 → 打印三条 takeaway。

注意：讲义 Build It 部分写的是 `PoisoningScenario`、`Verifier` 两个"类"，实际代码里是 `run_without_verifier / run_with_verifier` 与 `verifier_agent` 函数；讲义标注"Python (stdlib, `threading`)"，但代码只用了 `threading.Lock`，全程单线程顺序执行，没有真正的并发写入。

---

## 3. 逐段精讲

### 3.1 `ProvenanceEntry`：一条带来源的记录

```python
@dataclass
class ProvenanceEntry:
    id: int
    writer: str
    topic: str
    content: str
    timestamp: float
    prompt_hash: str
    source_uri: str | None = None
    supersedes: int | None = None
    flags: list[str] = field(default_factory=list)
```

- 讲义 Ship It 列出的 provenance 五元组是 `(writer, timestamp, prompt_hash, tool_calls_cited, source_uri)`；代码实现了其中四个，**没有 `tool_calls_cited`**。
- `supersedes` 用于"更正是新条目，指向被取代的旧条目"的 append-only 版本化——但整个文件里**没有任何地方传入非 None 的 `supersedes`**，supersession 只停留在字段层面。
- `flags` 用 `field(default_factory=list)`：可变默认值必须这样写，否则所有实例会共享同一个列表。
- 缺少的关键字段：`derived_from`（我是读了哪些条目推出来的）。没有它，summarizer 和 analyst 的输出与源头条目之间没有可追踪的边，这直接导致 verifier 查不到派生条目（见 3.5 与测验 Q10）。

### 3.2 `MessagePool`：加锁的 append-only 列表

```python
    def write(self, writer, content, prompt, source_uri=None, topic="default", supersedes=None) -> int:
        with self._lock:
            eid = self._next_id
            self._next_id += 1
            e = ProvenanceEntry(
                id=eid, writer=writer, topic=topic, content=content,
                timestamp=time.time(),
                prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()[:10],
                source_uri=source_uri, supersedes=supersedes,
            )
            self.entries.append(e)
            return eid
```

- **id 分配和追加在同一把锁里**：保证并发写入时 id 单调递增、不重复，且列表顺序与 id 顺序一致。
- `prompt_hash` 取 SHA-256 前 10 个十六进制字符（40 bit）。例如 `"Fetch and summarize https://arxiv.org/paper-1"` 的哈希是 `154751ffa7`，与运行输出一致。存哈希而不存原文：节省空间、可以和外部存储的 prompt 原文对账；但 skill 文件也强调，只有内容哈希不足以构成 provenance——哈希说明"写了什么"，不说明"谁、从哪来"。
- `read_all` 返回 `list(self.entries)`——**浅拷贝**。列表是新的，里面的 `ProvenanceEntry` 对象还是同一批。实测 `p.read_all()[0].content = "hacked"` 会直接改掉池中条目。所以"只读 verifier"在本代码里只是约定。
- `flag` 在锁内线性查找并 `e.flags.append(flag)`：这是对已有条目的**原地修改**，与讲义"append-only、更正作为新条目"的原则相冲突（见第 4 节）。

### 3.3 `Blackboard`：topic 订阅与"锁外回调"

```python
    def publish(self, writer, topic, content, prompt, source_uri=None) -> int:
        with self._lock:
            eid = self._next_id
            self._next_id += 1
            e = ProvenanceEntry(...)
            self.topics.setdefault(topic, []).append(e)
            subs = list(self.subscribers.get(topic, []))
        for cb in subs:
            cb(e)
        return eid
```

- `setdefault(topic, [])`：topic 不存在时先放一个空列表再追加，一行完成"创建或取出"。
- **在锁内复制订阅者列表，在锁外调用回调**——这是并发编程的经典写法：
  - 如果在锁内调用回调，而回调里又调用 `bb.publish(...)`（例如风控引擎收到价格后立即发布告警），`threading.Lock` 不可重入，会**死锁**；
  - 复制一份 `subs` 再遍历，避免回调执行期间别的线程 `subscribe` 修改列表。
- 代价：回调执行时条目已经入库；回调抛异常会直接冒泡给发布者，后续订阅者收不到。生产中通常把回调放进队列异步执行，并单独捕获异常。
- `subscribe` 只登记回调，**不回放历史**。先发布后订阅的 agent 收不到旧消息，只能 `read_topic` 主动拉取（已实测：回调收到 `[]`，`read_topic` 返回 `[0]`）。
- `Blackboard` 的 `publish` 不接受 `supersedes`，也没有 `flag` 方法：版本化和核查只在消息池一侧演示。

### 3.4 三个"agent"与投毒链

```python
FAKE_SOURCES = {
    "https://arxiv.org/paper-1": "The study reports a 4.2% accuracy improvement over the baseline.",
    "https://arxiv.org/paper-2": "Dataset size was 12,500 examples.",
}

def retrieval_agent(pool, uri, hallucinate):
    content = FAKE_SOURCES[uri]
    if hallucinate and "4.2%" in content:
        content = content.replace("4.2%", "42%")
    return pool.write(writer="retriever", content=content,
                      prompt=f"Fetch and summarize {uri}", source_uri=uri)
```

- "幻觉"用一次确定性的字符串替换模拟，让实验可复现。`paper-2` 在主流程里从未被用到，是给讲义练习 2 预留的。
- retriever 是唯一带 `source_uri` 的写入者。

```python
def summarizer_agent(pool):
    retrieved = [e for e in pool.read_all() if e.writer == "retriever"]
    ...
    latest = retrieved[-1].content
    summary = f"Summary: study reports a significant result -- {latest.split('.')[0]}."
    return pool.write("summarizer", summary, "Summarize retrieval", None)
```

- 按 `writer` 字段过滤——这就是"按 provenance 读"的最朴素形式。
- `retrieved[-1]` 取最近一条：如果以后有 supersession 更正条目，它也会被当作"最新"读到，这是本代码中唯一隐含"后写覆盖先写"语义的地方。
- **bug**：`latest.split('.')[0]` 想取第一句，但会在任何句点处切开。正确原文 `"...a 4.2% accuracy..."` 中的小数点被当成句号，摘要变成 `"...The study reports a 4."`；而幻觉版本 "42%" 没有小数点，反而完整保留。实测 `hallucinate=False` 时输出：

```text
1 summarizer | Summary: study reports a significant result -- The study reports a 4.
2 analyst    | Analyst verdict: Recommend further review (based on: ... The study reports a 4.)
```

  也就是说，主流程恰好只走了 `hallucinate=True` 的分支，才没暴露这个问题。这个 bug 本身就是一次"确定性代码造成的记忆投毒"：派生条目与来源不一致，verifier 却查不到。
- summarizer 写入时 `source_uri=None`，也没有记录它读的是哪条（讲义场景里写的是 "(source: A)"，代码没实现）。

```python
def analyst_agent(pool):
    summaries = [e for e in pool.read_all() if e.writer == "summarizer"]
    ...
    verdict = "Recommend adoption" if "42%" in latest else "Recommend further review"
```

- analyst 的"推理"是一个关键字判断，硬编码了 "42%"。它**不看任何 `flags`**，既不看自己读的摘要条目，也不看上游 retriever 条目。

### 3.5 只读 verifier

```python
def verifier_agent(pool: MessagePool) -> list[tuple[int, str]]:
    findings = []
    for e in pool.read_all():
        if e.source_uri and e.source_uri in FAKE_SOURCES:
            truth = FAKE_SOURCES[e.source_uri]
            if e.content != truth:
                findings.append((e.id, f"mismatch with {e.source_uri}: fetched text was {truth!r}"))
    return findings
```

- 做对了的地方：
  - **独立事实来源**：比对对象是 `FAKE_SOURCES`（模拟重新抓取原文），而不是池中别的条目——不会被池子"带偏"。
  - **不直接写池子**：只返回 `(entry_id, reason)` 列表，由调用方决定怎么处理，对应讲义"Verifier has no write handle to shared state"。
- 局限：
  1. 只核查带 `source_uri` 的条目。summarizer [1] 和 analyst [2] 同样含有 42%，但都被跳过。
  2. `e.content != truth` 是**整句全等**比较。retriever 只要换个说法（例如 `"Study: 4.2% accuracy improvement over baseline."`），即便数字正确也会被误报（已实测会被标记）。真实系统要做"断言级"核查：抽取数字/实体，检查能否在原文中找到支撑。
  3. `{truth!r}` 用 `repr` 打印原文，所以输出里带单引号。
- 它拿到的是完整 `MessagePool` 对象，Python 层面完全可以调用 `write` 或改条目——"只读"是靠自觉，不是靠能力隔离。

### 3.6 两轮对照实验

```python
def run_with_verifier() -> None:
    pool = MessagePool()
    retrieval_agent(pool, "https://arxiv.org/paper-1", hallucinate=True)
    summarizer_agent(pool)
    findings = verifier_agent(pool)
    for eid, reason in findings:
        pool.flag(eid, reason)
    analyst_agent(pool)
```

- verifier 插在 summarizer 之后、analyst 之前运行，标记结果通过 `pool.flag` 写回了池中条目。
- 这里有两处与讲义原则相冲突：
  - 讲义要求 verifier 的输出 "routed to a human or a separate decision agent, never fed back into the pool"，而这里调用方把结论直接塞进了池中条目的 `flags`——下游 agent 读池子就能读到；
  - `flag` 是原地修改，不是 append-only 的新条目。
- 由于 analyst 不看 flags，RUN 2 的最终结论仍是 `Recommend adoption`，代码末尾打印的是"downstream agents **can** suppress the verdict"。讲义 Build It 里写的预期是"the pool is labeled 'flagged', the final report includes a retraction"——**代码中并不存在 retraction**。

### 3.7 黑板演示

```python
    bb.subscribe("prices", on_prices)
    bb.subscribe("alerts", on_alerts)
    bb.publish("scraper-1", "prices", "AAPL=192.4", "poll market")
    bb.publish("scraper-2", "prices", "MSFT=401.2", "poll market")
    bb.publish("risk-engine", "alerts", "ALERT: AAPL moved >2% in 60s", "watch prices")
```

- `on_prices` / `on_alerts` 是**闭包**：它们引用外层函数的 `received` 字典并修改其中的列表（修改可变对象不需要 `nonlocal`）。
- id 由黑板全局分配（0、1、2），而不是每个 topic 各自从 0 开始，所以 alerts 订阅者收到的是 `[2]`。
- 演示的要点是"价格订阅者从未看到告警"——选择性路由让每个 agent 的上下文只装与自己相关的内容，这是黑板能比消息池扩展得更远的原因。
- 这个演示没有展示投毒相关的内容；讲义练习 3 要求把投毒场景迁到带 topic 分区的黑板上做对比。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用字符串替换模拟幻觉 | 结果确定、可复现 | 真实幻觉形态多样，需要断言级核查 |
| `FAKE_SOURCES` 字典充当"互联网" | 无需网络即可演示独立取源 | 生产中 verifier 要真的重新抓取 URL / 调用工具，并处理来源本身变化 |
| prompt 只存 SHA-256 前 10 位 | 简短、可对账 | 40 bit 足够演示；生产中存完整哈希并把 prompt 原文放对象存储 |
| `threading.Lock` 保护写入 | 演示"共享状态需要并发控制" | 本代码实际单线程；生产中用数据库事务或单写者队列 |
| 黑板回调在锁外执行 | 避免回调内再发布导致死锁 | 回调异常会打断后续订阅者；生产中放进异步队列并隔离异常 |
| 订阅不回放历史 | 实现最简单 | 迟到的订阅者丢消息；生产用持久化日志 + 消费位点（offset） |
| verifier 返回结果而不写池子 | 体现"不可写 verifier" | 但调用方又把结果 `flag` 进池子，并且是原地修改；应写到独立核查通道，更正以 `supersedes` 新条目表达 |
| verifier 整句全等比较 | 代码最短 | 改写即误报；只能查带 `source_uri` 的条目，派生条目漏检 |
| analyst 用关键字 "42%" 下结论 | 让投毒后果直观 | 不看 flags，所以 RUN 2 仍"采纳"错误结论 |
| `read_all` 浅拷贝 | 简单 | 读者能改池中对象；应 `frozen=True` 或深拷贝 / 只读视图 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值；配合 `str \| None` 等新式写法在旧版本也不报错 |
| `@dataclass` | `class ProvenanceEntry` | 自动生成 `__init__`、`__repr__`、`__eq__`，按字段顺序传参 |
| `field(default_factory=list)` | `flags: list[str] = field(default_factory=list)` | 可变默认值必须用工厂函数，否则所有实例共享同一个列表 |
| 联合类型 `X \| None` | `source_uri: str \| None = None` | 表示"字符串或 None"，等价于 `Optional[str]` |
| 泛型注解 | `dict[str, list[ProvenanceEntry]]`、`list[tuple[int, str]]` | 内置容器直接下标标注元素类型（Python 3.9+） |
| `Callable[[A], R]` | `Callable[[ProvenanceEntry], None]` | 注解"接收一个 ProvenanceEntry、返回 None 的函数" |
| 返回值注解 | `def write(...) -> int:` | 声明返回类型，仅供阅读与静态检查 |
| `with` + 锁 | `with self._lock:` | 进入时 `acquire`、离开时自动 `release`，即使抛异常也会释放 |
| 私有约定 `_name` | `self._lock`、`self._next_id` | 单下划线表示"内部使用"，Python 不强制 |
| `hashlib` 链式调用 | `hashlib.sha256(prompt.encode()).hexdigest()[:10]` | 字符串先编码成 bytes，再求哈希、转十六进制、切片 |
| `dict.setdefault` | `self.topics.setdefault(topic, []).append(e)` | 键不存在则插入默认值并返回它 |
| `dict.get` 带默认值 | `self.subscribers.get(topic, [])` | 键不存在时返回 `[]` 而不是抛 `KeyError` |
| 列表推导式 + 条件 | `[e for e in pool.read_all() if e.writer == "retriever"]` | 过滤出符合条件的元素 |
| 负索引 | `retrieved[-1]` | 取最后一个元素 |
| 条件表达式 | `"Recommend adoption" if "42%" in latest else "Recommend further review"` | 一行 if/else 取值 |
| `in` 判断子串 | `"4.2%" in content` | 字符串包含关系 |
| 元组解包循环 | `for eid, reason in findings:` | 每个元素是二元组，直接拆成两个变量 |
| 嵌套函数 / 闭包 | `def on_prices(e): received["prices"].append(e.id)` | 内部函数引用并修改外层的可变对象 |
| f-string 格式符 | `{e.writer:11s}`、`{truth!r}` | `:11s` 左对齐宽度 11；`!r` 用 `repr()` 显示（带引号） |
| 字符串乘法 | `"=" * 72` | 生成 72 个等号的分隔线 |
| `str.join` | `'; '.join(e.flags)` | 用分隔符拼接列表 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`cd code && python3 main.py`，耗时不到 1 秒，结果完全确定）：

```text
========================================================================
RUN 1 — no verifier; hallucination propagates
========================================================================
  [0] retriever   (154751ffa7) :: The study reports a 42% accuracy improvement over the baseline.
  [1] summarizer  (9cbcb95e85) :: Summary: study reports a significant result -- The study reports a 42% accuracy improvement over the baseline.
  [2] analyst     (eb19da3531) :: Analyst verdict: Recommend adoption (based on: Summary: ... 42% accuracy improvement over the baseline.)

final report uses hallucinated 42% figure; no alarm raised.

========================================================================
RUN 2 — read-only verifier re-fetches sources and flags
========================================================================
  [0] retriever   (154751ffa7) :: The study reports a 42% accuracy improvement over the baseline. [FLAGGED: mismatch with https://arxiv.org/paper-1: fetched text was 'The study reports a 4.2% accuracy improvement over the baseline.']
  [1] summarizer  (9cbcb95e85) :: Summary: study reports a significant result -- The study reports a 42% accuracy improvement over the baseline.
  [2] analyst     (eb19da3531) :: Analyst verdict: Recommend adoption (based on: Summary: ... 42% ...)

verifier surfaced 1 inconsistency. downstream agents can suppress the verdict.

========================================================================
BLACKBOARD DEMO — topic-keyed pub/sub, not every agent reads everything
========================================================================
  price subscribers got ids: [0, 1]
  alert subscribers got ids: [2]
  (note: price subscribers never saw the alert; that is the point)
```

（analyst 行的长内容做了截取。）

逐项解读：

- **括号里的十位十六进制**是 prompt 哈希。三类 agent 的 prompt 固定，所以两轮的哈希完全相同（`154751ffa7`、`9cbcb95e85`、`eb19da3531`）——相同哈希说明"同一个提示模板写出了不同内容"时，问题就出在输入数据而不是提示上，这正是 provenance 的排障价值。
- **RUN 1**：错误从 [0] 传到 [1]、再到 [2]，每一跳都把上一跳的内容原样嵌进来，最终给出 `Recommend adoption`，没有任何告警。这就是讲义的 "laundered into fact"。
- **RUN 2**：verifier 只标记了 [0]。[1]、[2] 同样含 42%，但没有 `source_uri`，不在核查范围内。最终 analyst 仍然 `Recommend adoption`——**verifier 发现了问题，但系统没有对它做出反应**。讲义预期"final report includes a retraction"，实际输出里并没有撤回。
- **黑板**：id 是全局计数，价格订阅者收到 `[0, 1]`，告警订阅者收到 `[2]`，两者互不可见。
- **未在主流程中出现但值得自己试的结果**（已实测）：把 `hallucinate` 改成 `False`，摘要会被 `split('.')` 截成 "...a 4."，analyst 给出 `Recommend further review`——也就是说，诚实路径下系统同样拿不到正确数字。

---

## 7. 动手改一改

1. **修掉分句 bug**：把 `latest.split('.')[0]` 改为 `re.split(r'(?<=[.!?])\s+', latest)[0].rstrip('.')`，分别用 `hallucinate=True/False` 运行，确认诚实路径下 "4.2%" 被完整保留。
2. **让 analyst 尊重核查结果**：给 `analyst_agent` 增加 `blocked_ids` 参数（由调用方从 `findings` 构造，不写回池子）；若读到的数据链上有被拦截条目，输出 `Withheld: upstream source failed verification`。再让一个"决策 agent"写一条 `supersedes=0`、内容为来源原文的更正条目，实现讲义所说的 retraction。
3. **派生链 provenance（讲义练习 2）**：给 `ProvenanceEntry` 加 `derived_from: list[int]`，summarizer/analyst 写入时填上所读条目 id；让 summarizer 把 12,500 编造成 125,000；把 verifier 改成"抽取数字 → 在祖先条目引用的原文中查找"，确认两个幻觉都能被抓到，且正确改写不会误报。
4. **独立核查通道**：新建 `VerificationChannel` 类（只有 verifier 能写、只有决策者能读），删除 `MessagePool.flag` 的使用，比较两种设计下"被投毒的池子"能否影响 verifier。
5. **黑板版本的投毒实验（讲义练习 3）**：用 `Blackboard` 的 `prices / summaries / analyses` 三个 topic 重写三 agent 流水线，思考：topic 分区能否阻止"沿依赖链"的投毒？（提示：analyst 必须订阅 summaries，链条不变；分区只能限制"无关 agent 被波及"的范围。）
6. **真正的并发**：用 `threading.Thread` 启动 20 个线程同时 `write`，检查 id 是否连续、无重复；再去掉锁观察会发生什么。然后给黑板加一个在回调里再次 `publish` 的订阅者，验证"锁外回调"避免了死锁（把回调挪进 `with` 块再试一次）。

---

## 8. 常见坑

- **以为"标记了"就等于"阻断了"**：本代码 RUN 2 的最终结论仍是错的。核查结果必须有消费者，并且下游要依据它改变行为。
- **只核查一手条目**：派生条目没有 `source_uri`，污染会在"二手、三手"条目里继续传播。必须记录 `derived_from`，按依赖图传播 taint。
- **整句全等比较**：任何正当改写都会被误报，误报多了团队会忽略 verifier。应做断言级核查。
- **verifier 结论回写池子**：被投毒的池子会反过来污染 verifier 的输入；讲义要求核查输出走独立通道。
- **原地修改条目**：`flag` 这类原地修改破坏了 append-only 的审计轨迹，也让"谁在什么时候改了什么"无从查起。
- **浅拷贝当只读**：`list(self.entries)` 不会复制条目对象；要么 `frozen` dataclass，要么只读视图或深拷贝。
- **在锁内调用回调**：回调里再发布会因 `Lock` 不可重入而死锁；回调慢还会阻塞所有写入者。
- **用 `str.split('.')` 分句**：小数、缩写（如 "e.g."）、URL 都含句点，数字恰恰是最容易出错、也最需要核对的内容。
- **迟到的订阅者**：不做回放就会丢消息；新加入的 agent 需要先 `read_topic` 补齐历史再订阅。
