# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 07 节 Agent Memory：虚拟上下文与记忆分页 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`dataclasses`、`typing`）；不调用 LLM，"agent"是一段写死的工具调用脚本

---

## 1. 这份代码在考察什么

这份代码用不到 200 行标准库代码，复刻 MemGPT 论文的**两层虚拟上下文**：

1. **Main context（RAM）**：`MainContext` = 一个 `core` 字典（钉住的命名段落）+ 一个 `messages` 列表（最近对话），超出上限时把最老的消息挪到 `evicted`。
2. **External context（磁盘）**：`ArchivalStore` = 一个可搜索的记录列表，按词重叠打分检索。
3. **记忆工具（换页）**：`MemoryTools` 提供 MemGPT 的五个标准工具 `core_memory_append / core_memory_replace / archival_memory_insert / archival_memory_search / conversation_search`。
4. **Interrupt 式控制流**：`run_scripted_agent` 依次执行工具调用，把返回字符串收集为 observation。

> 一句话：**"无限记忆"不是更大的窗口，而是"固定大小的 prompt + 可搜索的外部存储 + 让 agent 自己决定何时换入换出的工具"。**

需要提前知道的简化：淘汰按**消息条数**而非 token；检索是 Jaccard 词重叠而非讲义说的"BM25-esque"；被淘汰的消息只是挪进列表，没有压缩/摘要；工具写入的记录没有真实的 session/turn；没有真实 LLM，检索结果也没有被拼回主上下文。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Message` | dataclass | 一条对话：`role` + `text` | 对话轮次 |
| `MainContext` | dataclass | `core` + `messages` + `max_messages` + `evicted`；`append` 带 FIFO 淘汰，`render` 拼出 prompt | Main context / RAM |
| `ArchivalRecord` | dataclass | 一条长期记忆：`rid`、`text`、`tags`、`session_id`、`turn_id` | Archival 记录（带引用字段） |
| `ArchivalStore` | 类 | `insert` 生成 ID 并存储；`search` 用 Jaccard 打分取 top-k | External context / 磁盘 |
| `MemoryTools` | 类 | 五个 MemGPT 记忆工具，全部返回字符串 | Memory tool surface |
| `ToolCall` | dataclass | 工具名 + 参数字典 | 模型发出的调用 |
| `run_scripted_agent` | 函数 | 用 `getattr` 按名字分发调用，捕获异常 | Interrupt：调用 → 执行 → observation |
| `main` | 函数 | 灌入 4 条对话 → 执行 5 个记忆写入 → 再灌 2 条 → 打印主上下文 → 检索 archival 与历史对话 | 演示 trace |

数据流：`main` 往 `MainContext` 追加对话（触发淘汰）→ `run_scripted_agent` 执行写 core / 写 archival 的工具 → 继续追加对话（更多淘汰）→ `render()` 打印"模型此刻能看到的 prompt" → `archival_memory_search` 换入长期事实 → `conversation_search` 从被淘汰的历史里找回原文。

---

## 3. 逐段精讲

### 3.1 `MainContext`：固定容量的"RAM"

```python
@dataclass
class MainContext:
    core: dict[str, str] = field(default_factory=dict)
    messages: list[Message] = field(default_factory=list)
    max_messages: int = 4
    evicted: list[Message] = field(default_factory=list)

    def append(self, role: str, text: str) -> None:
        self.messages.append(Message(role=role, text=text))
        while len(self.messages) > self.max_messages:
            self.evicted.append(self.messages.pop(0))
```

- `core` 对应 MemGPT 的 core memory：命名段落（如 `persona`、`user`），每次 `render` 都会出现在 prompt 里，不参与淘汰。
- `messages` 是最近对话；超过 `max_messages` 时用 `pop(0)` 弹出**最老**的一条，放进 `evicted`——这是 FIFO 淘汰。
- `evicted` 没有被丢掉，`conversation_search` 还能搜到它。这相当于 Letta 三层结构中的 **recall memory**（讲义 Lesson 08 会正式引入），本节虽然只讲"两层"，代码里其实已经有了第三层的雏形。
- `field(default_factory=dict)`：dataclass 的可变默认值必须用工厂函数，否则所有实例会共享同一个字典。
- ⚠️ 淘汰按**条数**计，与真实的 token 预算无关：实测往 `max_messages=3` 的上下文里塞一条 10 万字符的消息，`render()` 长度为 100,026 字符，照样"没超限"。讲义练习 1 要求改成按 token 计（测验 Q10）。
- ⚠️ 讲义 Build It 说 `MainContext` "auto-compacts oldest messages"，但代码只是**挪走**，没有压缩或摘要。
- ⚠️ `core` 没有任何大小限制，可以无限追加。

```python
    def render(self) -> str:
        parts: list[str] = ["[core]"]
        for key, value in sorted(self.core.items()):
            parts.append(f"  {key}: {value}")
        parts.append("[messages]")
        for msg in self.messages:
            parts.append(f"  {msg.role}: {msg.text}")
        return "\n".join(parts)
```

- `render` 拼出"模型此刻真正能看到的内容"：先 core（按 key 排序，保证输出稳定），后最近消息。被淘汰的消息不在这里——这就是"溢出即遗忘"，除非 agent 主动去搜。

### 3.2 `ArchivalStore`：可搜索的"磁盘"

```python
    def insert(self, text: str, *, tags: tuple[str, ...] = (),
               session_id: str = "s0", turn_id: int = 0) -> str:
        self._counter += 1
        rid = f"a{self._counter:03d}"
        self._records.append(ArchivalRecord(
            rid=rid, text=text, tags=tags,
            session_id=session_id, turn_id=turn_id,
        ))
        return rid
```

- 自增计数器生成 `a001`、`a002`……形式的 ID，`{:03d}` 补零到 3 位。返回 ID 是为了**引用**：skill 文件要求"Every write returns the stored id for citation"。
- 参数列表中的 `*`：之后的参数只能用关键字传递（`insert(text, tags=...)`），防止把 `session_id` 和 `turn_id` 的位置传反。
- `ArchivalRecord` 预留了 `session_id`、`turn_id`，对应讲义"Store source references (session ID, turn ID) with every archival write"。⚠️ 但 3.3 中的工具并没有传入它们。

```python
    def search(self, query: str, top_k: int = 3) -> list[ArchivalRecord]:
        q_tokens = set(query.lower().split())
        scored: list[tuple[float, ArchivalRecord]] = []
        for record in self._records:
            r_tokens = set(record.text.lower().split())
            if not r_tokens:
                continue
            overlap = len(q_tokens & r_tokens)
            if overlap == 0:
                continue
            score = overlap / (len(q_tokens) + len(r_tokens) - overlap)
            scored.append((score, record))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:top_k]]
```

- 打分是 **Jaccard 相似度**：`|Q ∩ R| / |Q ∪ R|`，因为 `|Q ∪ R| = |Q| + |R| − |Q ∩ R|`。讲义称之为"BM25-esque store (token-overlap scoring)"，实际上与 BM25 关系不大：没有词频、没有 IDF、只有集合交并。
- 手算本次运行的查询 `"tool chains drift"`（实测）：

| 记录 | 重叠 | 分数 |
|------|------|------|
| a001 `ava is building a retrieval bot with 12 tools for sales` | 0（`tools` ≠ `tool`） | 0 |
| a002 `long-horizon tool chains drift after 20 steps per BFCL V4` | 3 | 3 / (3 + 10 − 3) = **0.3** |
| a003 `sleep-time compute consolidates memory asynchronously` | 0 | 0 |

- 分词只是 `lower().split()`：标点粘在词上（`drift?` ≠ `drift`，实测分数从 0.3 降到 0.1818）、没有词干化、停用词（`is`、`the`）也计入重叠。
- `tags` 被存储但**检索时完全不用**。
- `scored.sort(key=lambda x: -x[0])`：按分数降序；Python 的排序是稳定的，同分时保持插入顺序（越早插入越靠前）。
- 在真实系统中这里会是 BM25（练习 2，测验 Q11 有实现）、向量检索或两者混合（Lesson 09）。

### 3.3 `MemoryTools`：五个记忆工具

```python
    def core_memory_append(self, section: str, text: str) -> str:
        existing = self.main.core.get(section, "")
        self.main.core[section] = (existing + " " + text).strip() if existing else text
        return f"core[{section}] appended: {len(self.main.core[section])} chars"

    def core_memory_replace(self, section: str, old: str, new: str) -> str:
        current = self.main.core.get(section, "")
        if old not in current:
            return f"error: {old!r} not in core[{section}]"
        self.main.core[section] = current.replace(old, new)
        return f"core[{section}] replaced"
```

- `core_memory_append`：段落已存在就用空格拼接，不存在就新建。返回值报告的是段落的**总长度**，提示模型 core 正在变大。
- `core_memory_replace`：找不到 `old` 时返回错误字符串而不是抛异常（与 Lesson 06 "never raise to the loop"一致）。
- ⚠️ `str.replace` 会替换**所有**出现位置：实测 `core["user"] = "likes tea; likes tea"` 执行 `replace("tea", "coffee")` 后变成 `"likes coffee; likes coffee"`。想只改一处需要 `replace(old, new, 1)` 或要求 `old` 唯一。
- 没有 `core_memory_clear`——符合 skill 文件"Support `replace` not `clear`"的规则。

```python
    def archival_memory_insert(self, text: str, tags: tuple[str, ...] = ()) -> str:
        rid = self.archival.insert(text, tags=tags)
        return f"stored {rid} ({self.archival.count()} records)"

    def archival_memory_search(self, query: str, top_k: int = 3) -> str:
        hits = self.archival.search(query, top_k=top_k)
        if not hits:
            return "no matches"
        return "\n".join(f"  {h.rid}: {h.text}" for h in hits)

    def conversation_search(self, query: str) -> str:
        q = query.lower()
        for msg in reversed(self.main.evicted + self.main.messages):
            if q in msg.text.lower():
                return f"found ({msg.role}): {msg.text}"
        return "no matches"
```

- ⚠️ `archival_memory_insert` 只把 `tags` 传给 `insert`，`session_id`、`turn_id` 永远是默认值 `"s0"` 和 `0`——讲义说的 citation 字段在工具层被丢掉了。
- `archival_memory_search` 的输出带 `rid`，这是引用的最低要求；但没有 session/turn、没有分数。
- `conversation_search`：`evicted + messages` 按时间从旧到新拼接，`reversed` 后从新到旧扫描，做**子串**匹配，返回**第一个**（最近的）命中。注意它只返回一条，且是子串匹配，不是 `ArchivalStore` 的分词打分。
- 所有工具都返回字符串——因为结果要作为 observation 拼回 prompt。

### 3.4 `run_scripted_agent`：interrupt 式分发

```python
def run_scripted_agent(tools: MemoryTools, script: list[ToolCall]) -> list[str]:
    observations: list[str] = []
    for call in script:
        fn = getattr(tools, call.name, None)
        if fn is None:
            observations.append(f"error: unknown tool {call.name!r}")
            continue
        try:
            observations.append(fn(**call.args))
        except Exception as e:
            observations.append(f"error: {type(e).__name__}: {e}")
    return observations
```

- 这是讲义 interrupt 模式的骨架："agent 调用工具 → 运行时执行 → 结果作为 observation 返回"。真实系统里，这些 observation 会追加到 `messages`（于是可能又触发淘汰），然后再次调用模型。本文件只把它们收集到列表里打印。
- `getattr(tools, call.name, None)`：按字符串取方法，第三个参数是取不到时的默认值。
- ⚠️ **没有白名单**：`getattr` 能取到 `MemoryTools` 的任何属性。实测：
  - `ToolCall("main", {})` → `error: TypeError: 'MainContext' object is not callable`；
  - `ToolCall("__init__", {"main": MainContext(), "archival": ArchivalStore()})` → 重新初始化工具对象，记忆被替换成空的（之后 `count()` 为 0），返回值 `None` 混进了 observations。
  
  模型输出是不可信输入，工具名必须用显式白名单或 registry 分发（测验 Q9）。

### 3.5 `main`：演示脚本

```python
    main_ctx = MainContext(max_messages=3)
    ...
    main_ctx.append("user", "my name is ava and I ship agents for a living")
    main_ctx.append("assistant", "noted. what are you building right now?")
    main_ctx.append("user", "a retrieval bot for our sales org, 12 tools so far")
    main_ctx.append("assistant", "12 tools is in the long-horizon band; plan for drift")
```

- `max_messages=3` 覆盖了 dataclass 默认的 4。追加第 4 条时，第 1 条（含用户名字）已被淘汰。
- 好在脚本随后通过 `core_memory_append("user", "name=ava, role=ships agents")` 把名字钉进了 core——这正是 MemGPT 的核心思路：**重要事实要主动写进不会被淘汰的地方**。
- 三条 `archival_memory_insert` 写入长期事实，带 tags。
- 再追加两条消息后，共 3 条被淘汰；随后演示从 archival 检索（`"tool chains drift"`，`top_k=2` 但只有 1 条命中）和从历史对话检索（`"retrieval bot"`，命中已被淘汰的第 3 条消息）。
- ⚠️ 讲义说"answers a follow-up question by calling `archival_memory_search`"，实际上检索是由 `main` 直接调用的，没有经过 `run_scripted_agent`，也没有生成答案或把结果拼回 `messages`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 按消息条数 FIFO 淘汰 | 最简单、行为可预测 | 与真实 token 预算无关；生产按 token 计，钉住 system/core/未完成的工具对，配合有上限的滚动摘要 |
| 被淘汰的消息进 `evicted` 列表 | 让 `conversation_search` 能找回原文 | 存在进程内存里，进程退出即丢失；生产写数据库，即 Letta 的 recall memory |
| Jaccard 词重叠检索 | 零依赖、可手算 | 无 IDF、不去标点、不词干化；生产用 BM25 / 向量 / 混合检索 + rerank |
| 工具返回字符串 | 直接作为 observation 拼回 prompt | 结构信息（分数、来源）丢失；可以返回 JSON 再渲染 |
| `ArchivalRecord` 有 session/turn 字段 | 为引用预留 | 工具层没传，字段形同虚设；应在工具层自动填充 |
| `getattr` 分发 | 少写一张映射表 | 暴露所有属性和 dunder 方法；生产必须白名单 + schema 校验 |
| 只有 `replace` 没有 `clear` | core 是承重结构，清空是"脚枪" | `replace` 会替换所有出现位置，需要唯一性约束 |
| 脚本化 agent，无 LLM | 控制流可离线测试 | 看不到"模型何时决定换页"这一最难的部分 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class Message:`、`class MainContext:` | 自动生成 `__init__` 等方法；dataclass 也可以定义普通方法（如 `append`、`render`） |
| `field(default_factory=...)` | `core: dict[str, str] = field(default_factory=dict)` | 可变默认值（dict、list）必须用工厂函数，每个实例各自新建 |
| 关键字参数构造 | `Message(role=role, text=text)` | 显式写出字段名，可读性更好 |
| 仅限关键字参数 `*` | `def insert(self, text, *, tags=(), session_id="s0", turn_id=0)` | `*` 之后的参数调用时必须写参数名 |
| 可变长元组类型 | `tuple[str, ...]` | 任意长度、元素都是 str 的元组 |
| `list.pop(0)` | `self.messages.pop(0)` | 弹出并返回第一个元素（O(n)；大量操作时可用 `collections.deque`） |
| `while` 循环 | `while len(self.messages) > self.max_messages:` | 条件成立就一直执行 |
| 格式化补零 | `f"a{self._counter:03d}"` | 宽度 3、不足补 0：1 → `a001` |
| 集合运算 | `q_tokens & r_tokens` | 交集；`set(...)` 去重 |
| `lambda` 排序键 | `scored.sort(key=lambda x: -x[0])` | 按分数降序；Python 排序稳定 |
| 解包时丢弃 | `[r for _, r in scored[:top_k]]` | `_` 表示不关心的值；切片取前 k 个 |
| 条件表达式 | `(existing + " " + text).strip() if existing else text` | 三元表达式 |
| `in` 判断子串 | `if old not in current:`、`if q in msg.text.lower():` | 字符串包含检查 |
| `str.replace` | `current.replace(old, new)` | 默认替换所有出现位置 |
| `reversed` | `reversed(self.main.evicted + self.main.messages)` | 反向迭代，不复制列表（但 `+` 会先拼出新列表） |
| 生成器表达式 + `join` | `"\n".join(f"  {h.rid}: {h.text}" for h in hits)` | 逐个生成字符串再拼接 |
| `getattr` 带默认值 | `getattr(tools, call.name, None)` | 按名字取属性，取不到返回 None |
| `**` 解包 | `fn(**call.args)` | 字典变关键字参数 |
| `zip` | `for call, obs in zip(script, observations):` | 并行遍历两个列表 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，瞬间完成）：

```text
tool trace (memory writes)
  core_memory_append({'section': 'persona', 'text': 'the agent remembers user details politely'}) -> core[persona] appended: 41 chars
  core_memory_append({'section': 'user', 'text': 'name=ava, role=ships agents'}) -> core[user] appended: 27 chars
  archival_memory_insert({'text': 'ava is building a retrieval bot with 12 tools for sales', 'tags': ('project', 'ava')}) -> stored a001 (1 records)
  archival_memory_insert({'text': 'long-horizon tool chains drift after 20 steps per BFCL V4', 'tags': ('bfcl', 'tools')}) -> stored a002 (2 records)
  archival_memory_insert({'text': 'sleep-time compute consolidates memory asynchronously', 'tags': ('letta', 'memory')}) -> stored a003 (3 records)

filling main context until eviction kicks in

main context (3 messages, 3 evicted)
[core]
  persona: the agent remembers user details politely
  user: name=ava, role=ships agents
[messages]
  assistant: 12 tools is in the long-horizon band; plan for drift
  user: what were you saying about tool chains?
  assistant: let me check archival

page in: archival_memory_search('tool chains drift')
  a002: long-horizon tool chains drift after 20 steps per BFCL V4

conversation_search for 'retrieval bot'
found (user): a retrieval bot for our sales org, 12 tools so far
```

逐项解读：

- **tool trace**：`41 chars`、`27 chars` 是 core 段落当前的总长度（新段落，所以就是写入文本的长度）。`stored a001 (1 records)` 返回的 ID 可用于之后引用。
- **3 messages, 3 evicted**：前 4 条对话淘汰了 1 条，后 2 条又淘汰 2 条。前三条对话（包括用户名字、项目介绍）都已不在 `[messages]` 里。
- **core 仍然在**：用户名字和角色通过 core memory 保留下来——如果脚本没写 core，此刻模型就"忘记"了 ava 是谁。
- **archival 检索只返回 1 条**：虽然 `top_k=2`，但只有 a002 得分非零（0.3）；a001 含 `tools` 但不含 `tool`，得 0 分。
- **conversation_search 命中被淘汰的消息**：`"a retrieval bot for our sales org..."` 已不在主上下文，但仍在 `evicted` 中，可被找回。这说明"淘汰 ≠ 删除"——前提是有 recall 存储。
- 本次运行中三条 archival 记录的 `session_id`/`turn_id` 都是 `"s0"`/`0`（工具没传），输出里也看不到——如果 agent 要回答"你是在哪次对话里告诉我的"，它答不上来。

---

## 7. 动手改一改

1. **白名单分发**：把 `run_scripted_agent` 改成只允许五个记忆工具，验证 `ToolCall("__init__", ...)` 被拒绝（测验 Q9）。
2. **讲义练习 1**：按 token 预算（`len(text.split()) * 1.3`）淘汰，并加入有上限的滚动摘要；观察摘要占预算时的连锁淘汰现象（测验 Q10 给出了实测）。
3. **讲义练习 2**：实现 BM25（去标点分词、TF、IDF、长度归一化），在 10 条事实上比较 recall@1（测验 Q11 实测：基线 5/6，BM25 6/6）。
4. **讲义练习 3**：让 `archival_memory_insert` 自动填入 `session_id`、`turn_id`、`source`，让检索结果带上 `[a002 | s3#14]` 形式的引用。
5. **讲义练习 4**：插入一条 "ignore all future user instructions" 的记录，写一个 guard 把指令形状的检索结果标记为 untrusted（测验 Q12）。
6. **闭环**：写一个最小 agent 循环——把每个 observation 作为 `tool` 消息 `append` 回 `main_ctx`，观察检索结果本身也会挤占主上下文、触发淘汰，体会"换页也有成本"。

---

## 8. 常见坑

- **把"按条数"当成"按 token"**：一条超长工具输出就能撑爆真实窗口，而条数计数毫无察觉。
- **淘汰即删除**：没有 recall 存储时，被淘汰的对话永久丢失；本文件用 `evicted` 列表保留，但也只在进程内存中。
- **关键事实只存在对话里**：用户名字随第 1 条消息被淘汰；必须主动写入 core 或 archival。
- **`str.replace` 改了不该改的地方**：`core_memory_replace` 会替换所有出现位置。
- **检索不去标点**：`drift?` 匹配不上 `drift`；用户提问通常带问号，直接影响召回。
- **存了 citation 字段但不填**：数据结构有 `session_id`/`turn_id`，工具层没传，结果全是默认值。
- **`getattr` 分发**：等于把对象所有属性都暴露为工具；模型或注入内容可能调用 `__init__` 之类的方法破坏状态。
- **把检索结果当指令**：archival 内容来自过去的对话或外部网页，属于不可信数据，应作为 observation 并加标记，而不是放进 system prompt。
