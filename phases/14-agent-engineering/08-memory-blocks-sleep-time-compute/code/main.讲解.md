# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 08 节 记忆块与休眠时计算 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`dataclasses`、`typing`）；不调用 LLM，两个 agent 都是脚本化的

---

## 1. 这份代码在考察什么

这份代码把 Letta 的两个核心想法做成了可离线运行的最小模型：

1. **Memory block**：`Block` 是 core 记忆中一个有标签、有字符上限、可编辑、带版本历史的段落；`BlockStore` 管理多个块（human / persona / task）并渲染成 prompt 片段。
2. **主 agent 与 sleep-time agent 分工**：`PrimaryAgent` 在每一轮里只做"快而粗"的写入（append 到块、插入 archival）；`SleepTimeAgent` 在关键路径之外做"慢而细"的整理（压缩接近上限的块、作废被推翻的 archival 记录）。
3. **作废而非删除**：`Archival` 记录带 `valid` 标志，矛盾时 `invalidate`，历史仍可审计。

> 一句话：**把"记忆整理"从用户等待的那条路径上搬走——主 agent 只负责记下来，sleep-time agent 负责睡一觉后把它理清楚。**

需要提前知道的落差：本次演示中 sleep pass **一个块都没有压缩**（都没到 80% 阈值）；`_summarize` 在边界情况下会把块抹成 `"."`；human 块里的 `city=Berlin` / `city=Lisbon` 矛盾没有被处理；矛盾由调用者手写传入；代码没有 Recall 层；两个 agent 是串行调用而非并发。下文逐一标出。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Block` | dataclass | `label`、`value`、`limit`、`description`、`version`、`history`；`append` / `replace` / `rewrite` / `near_limit` | Memory block |
| `BlockStore` | 类 | 创建、读取块，按标签排序渲染 | Core 层 |
| `ArchivalRecord` | dataclass | `rid`、`text`、`valid` | Archival 记录 |
| `Archival` | 类 | `insert`、`invalidate`、`valid_records`、`all_records` | Archival 层（作废而非删除） |
| `PrimaryAgent` | 类 | `turn(user_text, writes)`：执行原始写入并生成占位回复 | 关键路径上的主 agent |
| `SleepTimeAgent` | 类 | `run(contradictions)`：压缩近上限的块、作废矛盾记录 | Sleep-time compute |
| `_summarize` | 函数 | 按句号切分，从前往后取句子直到达到目标长度 | 块压缩（规则版"摘要"） |
| `main` | 函数 | 建 3 个块 → 主 agent 跑 4 轮 → 打印块 → sleep pass → 打印块与 archival | 演示 trace |

数据流：`main` 创建 `BlockStore`（human / persona / task）和 `Archival` → `PrimaryAgent.turn` × 4（块 append、archival insert）→ 打印"整理前"的块 → `SleepTimeAgent.run`（`near_limit` → `_summarize` → `rewrite`；按 claim 作废记录）→ 打印"整理后"的块和 archival 状态。

---

## 3. 逐段精讲

### 3.1 `Block`：带版本的可编辑段落

```python
@dataclass
class Block:
    label: str
    value: str = ""
    limit: int = 300
    description: str = ""
    version: int = 0
    history: list[str] = field(default_factory=list)

    def append(self, text: str) -> str:
        old = self.value
        self.value = (self.value + " " + text).strip() if self.value else text
        self.version += 1
        self.history.append(old)
        return f"{self.label} v{self.version} ({len(self.value)}/{self.limit})"
```

- 字段对应讲义"Each block has an `id`, `label`, `value`, `limit` (character cap), `description`"。代码用 `label` 兼作唯一标识，**没有单独的 `id`**；另外多了讲义练习 3 要求的 `version` 和 `history`。
- 每次写入（`append` / `replace` / `rewrite`）都 `version += 1` 并把**旧值**压入 `history`——可以回滚，但存的是全文快照而不是 diff。
- 返回值形如 `human v2 (72/180)`：版本号 + 当前长度 / 上限，作为 observation 让模型感知"块快满了"。
- ⚠️ `append` **不检查** `limit`：实测 `Block("t", limit=20).append("x" * 50)` 返回 `t v1 (50/20)`。上限是"软"的，只用于 `near_limit` 判断和显示。
- ⚠️ `description` 被存储，但 `BlockStore.render` 不输出它，模型在 prompt 里看不到"这个块该放什么、何时编辑"。

```python
    def replace(self, old: str, new: str) -> str:
        if old not in self.value:
            return f"error: {old!r} not in {self.label}"
        prev = self.value
        self.value = self.value.replace(old, new)
        ...

    def rewrite(self, new: str) -> str:
        prev = self.value
        self.value = new
        ...

    def near_limit(self, threshold: float = 0.8) -> bool:
        return len(self.value) >= int(self.limit * threshold)
```

- `replace` 找不到旧串时返回错误字符串，不抛异常；`str.replace` 会替换**所有**出现位置。
- `rewrite` 整体替换，是 sleep-time agent 用的"重写"操作。
- `near_limit`：长度达到上限的 80% 即为真。本次演示的阈值为 human `int(180×0.8)=144`、persona `128`、task `176`。

### 3.2 `BlockStore` 与 `Archival`

```python
class BlockStore:
    def create(self, label: str, description: str, limit: int = 300) -> Block:
        block = Block(label=label, description=description, limit=limit)
        self._blocks[label] = block
        return block
    ...
    def render(self) -> str:
        lines: list[str] = []
        for label in self.labels():
            block = self._blocks[label]
            lines.append(f"[{block.label} v{block.version} "
                         f"{len(block.value)}/{block.limit}]")
            lines.append(f"  {block.value}")
        return "\n".join(lines)
```

- `render` 就是 core 层进入 prompt 的样子：按标签字母序（human、persona、task）输出，每个块带版本和容量。
- `create` 对同名标签**静默覆盖**。
- `get` 返回 `Block | None`，调用方需要判空。

```python
class Archival:
    def invalidate(self, rid: str) -> bool:
        for record in self._records:
            if record.rid == rid:
                record.valid = False
                return True
        return False

    def valid_records(self) -> list[ArchivalRecord]:
        return [r for r in self._records if r.valid]
```

- **作废而非删除**：只把 `valid` 置为 `False`，记录本身保留。`valid_records()` 给检索用，`all_records()` 给审计用。这与 skill 文件的 hard reject "Deleting archival records on contradiction. Invalidate so history remains auditable" 一致。
- `invalidate` 线性查找；配合 `SleepTimeAgent.run` 的外层循环，整体是 O(n²)。生产中用以 `rid` 为键的字典或数据库索引。
- 这里的 `ArchivalRecord` 比上一节少了 `tags`、`session_id`、`turn_id`——引用字段反而退化了。

### 3.3 `PrimaryAgent`：关键路径上只做原始写入

```python
    def turn(self, user_text: str, writes: list[tuple[str, str, str]]) -> str:
        self.trace.append(f"user: {user_text}")
        for kind, label_or_text, payload in writes:
            if kind == "block_append":
                block = self.blocks.get(label_or_text)
                if block is not None:
                    self.trace.append(f"  block_append -> {block.append(payload)}")
            elif kind == "archival_insert":
                rid = self.archival.insert(payload)
                self.trace.append(f"  archival_insert -> {rid}")
        response = f"response to: {user_text}"
        self.trace.append(f"assistant: {response}")
        return response
```

- 每个写入是一个三元组 `(kind, label_or_text, payload)`：`block_append` 时第二项是块标签；`archival_insert` 时第二项不用（传空串），内容在第三项。这种"一个字段两种含义"的设计可读性差，真实工具调用应使用带名字的参数。
- 主 agent **从不摘要、从不整理**，与讲义"primary turns are fast and produce raw writes"一致。
- ⚠️ 写入不存在的块（`get` 返回 `None`）或未知的 `kind` 会被**静默忽略**，trace 里没有任何错误——与前两节"每个失败都要变成 observation"的原则相违。
- ⚠️ `self.trace` 只是打印用的列表，不是讲义三层中的 **Recall** 层（没有分页、没有检索、没有 session）。

### 3.4 `SleepTimeAgent`：关键路径之外的整理

```python
    def run(self, contradictions: list[tuple[str, str]]) -> None:
        self.trace.append("sleep-time pass start")
        for label in self.blocks.labels():
            block = self.blocks.get(label)
            if block is None:
                continue
            if block.near_limit():
                summary = _summarize(block.value, block.limit // 2)
                result = block.rewrite(summary)
                self.trace.append(f"  consolidate {label}: {result}")
        for claim, reason in contradictions:
            for record in self.archival.all_records():
                if record.valid and claim.lower() in record.text.lower():
                    self.archival.invalidate(record.rid)
                    self.trace.append(
                        f"  invalidate {record.rid} ({reason}): {record.text[:50]}..."
                    )
        self.trace.append("sleep-time pass end")
```

两项工作：

1. **块压缩**：近上限的块被压缩到 `limit // 2`。
2. **作废矛盾**：对每个 `(claim, reason)`，把包含该 claim 的有效记录作废。

需要注意的问题：

- ⚠️ **本次演示没有触发块压缩**：human 72/180、task 119/220 都没达到阈值，persona 是空的。讲义 Build It 说 trace 会展示"a sleep-time pass that summarizes a block"，实际看不到。
- ⚠️ **矛盾是调用者给的**：`main` 手写了 `("ava lives in Berlin", "...")`。"发现哪些事实被推翻"本应是 sleep-time agent（往往是更强模型）最有价值的工作。
- ⚠️ **子串匹配没有词边界**：实测 claim `"ava lives in Berlin"` 会误作废 `"Java lives in Berlin servers"`（`ava` 是 `Java` 的后缀）和 `"ava lives in Berlingen"`（`Berlin` 是 `Berlingen` 的前缀）。
- ⚠️ **只处理 archival，不处理块**：human 块中的 `city=Berlin ... city=Lisbon` 这对矛盾原封不动。
- ⚠️ **没有并发**：`main` 在所有对话结束后才调用一次 `run`，而讲义说"consolidates blocks between turns"并在后台运行。真实并发时，sleep agent 基于旧快照的 `rewrite` 会覆盖主 agent 的新写入（lost update，测验 Q12 实测会丢掉 `pet=cat`）。`version` 字段可以用来做乐观并发控制，但代码没有用。
- `sleep-time pass start/end` 的 trace 是正确的做法：skill 文件要求"If the sleep-time agent has no trace output, refuse"。

### 3.5 `_summarize`：规则版"摘要"及其缺陷

```python
def _summarize(text: str, target_len: int) -> str:
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    if not sentences:
        return text[:target_len]
    picked: list[str] = []
    total = 0
    for sentence in sentences:
        if total + len(sentence) + 1 > target_len:
            break
        picked.append(sentence)
        total += len(sentence) + 2
    return ". ".join(picked) + "."
```

- 思路：按句号切句，从第一句开始累加，直到再加一句就超过 `target_len`。`total` 每句加 `len + 2` 是为 `". "` 分隔符预留空间，判断时的 `+ 1` 是给结尾的 `"."` 留位置——可以验证输出长度 ≤ `target_len`。
- 它其实是**截断**而不是摘要；讲义设想的是让（更强的）模型生成摘要（练习 1 的 `block_summarize`）。
- 实测的三个缺陷：

| 输入 | 输出 | 问题 |
|------|------|------|
| `"Ava ships agents. She lives in Berlin. She moved to Lisbon in May. She prefers concise writing with citations."`，目标 60 | `'Ava ships agents. She lives in Berlin.'` | **保留最旧、丢弃最新**：块是 append 增长的，最新事实在末尾，"搬到里斯本"被丢掉，"住在柏林"被保留 |
| `"uses v1.2 of the SDK. e.g. letta"`，目标 100 | `'uses v1. 2 of the SDK. e. g. letta.'` | 按 `.` 切分破坏版本号、缩写、小数、URL |
| 183 字符、无句号的 `key=value` 串，目标 90 | `'.'` | 第一句就超长时 `picked` 为空，**整块被抹成一个句号** |

- 第三种情况对 human 块是必然发生的（它的格式正是 `name=ava role=... city=...`，没有句号）：只要再多写几个事实使其越过 144 字符，下一次 sleep pass 就会把它改写为 `"."`，trace 显示 `consolidate human: human v5 rewritten (1/180)`。修复见测验 Q9。

### 3.6 `main`：四轮对话 + 一次 sleep pass

```python
    primary.turn(
        "I moved to Lisbon last month; update your notes",
        [
            ("block_append", "human", "city=Lisbon (updated from Berlin)"),
            ("archival_insert", "",
             "ava lives in Berlin - old address, outdated"),
        ],
    )
    ...
    sleep.run(contradictions=[
        ("ava lives in Berlin",
         "human block updated city to Lisbon; Berlin archival claim is stale"),
    ])
```

- 第 3 轮用户搬家：主 agent 用 `block_append` 而不是 `block_replace`，于是 human 块出现两个 `city`；同时它往 archival 插入了一条**自己都标注为 outdated** 的记录，只为了让 sleep pass 有东西可以作废。这是为了演示机制而人为构造的场景。
- persona 块创建后从未写入，渲染为空行。
- `limit // 2`：整除，180 → 90、220 → 110。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 主 agent 只做原始写入 | 关键路径零整理开销 | 块中会累积矛盾与重复；需要 sleep pass 可靠地跟上 |
| `limit` 只做软阈值 | 不在用户路径上做摘要 | 块可无限超限；生产用"软阈值触发异步整理 + 硬上限拒写/溢出到 archival"（测验 Q10） |
| `version` + `history` 全文快照 | 实现简单、可回滚 | 没有 diff、没有写入者和原因；生产记录 diff、writer、依据，并在 trace 中展示 |
| 作废而非删除 | 历史可审计 | 存储增长；需要定期归档 |
| 规则截断代替摘要 | 离线、确定性 | 丢新留旧、切坏版本号、可能抹空整块；生产用 LLM 摘要 + 结构化合并（key=value 后写覆盖） |
| 矛盾由调用者传入 | 演示简单 | 真正难的"发现矛盾"被跳过；生产由 sleep agent 比对块与 archival |
| 子串匹配作废 | 零依赖 | 无词边界、无语义；生产用结构化事实（主体-属性-值）或语义匹配 + 人工复核 |
| 串行调用两个 agent | 可复现的 trace | 掩盖了并发冲突；生产用队列/后台任务，并以版本号做 compare-and-swap |
| 无 Recall 层 | 聚焦 block 与 sleep-time | 讲义的"三层"只实现了两层 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 方法 | `class Block:` 中的 `append`、`near_limit` | dataclass 既存数据也能定义行为 |
| `field(default_factory=list)` | `history: list[str] = field(default_factory=list)` | 可变默认值必须用工厂函数，否则所有块共享同一个列表 |
| 原地自增 | `self.version += 1` | 等价于 `self.version = self.version + 1` |
| 带默认值的参数 | `def near_limit(self, threshold: float = 0.8)` | 调用时可省略 |
| `int()` 截断 | `int(self.limit * threshold)` | 向零取整：`int(176.0) = 176` |
| 整除 `//` | `block.limit // 2` | 180 // 2 = 90 |
| 联合类型返回 | `def get(self, label) -> Block \| None` | 可能返回 None，调用方需判空 |
| `sorted(dict)` | `sorted(self._blocks)` | 对字典排序得到排好序的**键**列表 |
| 元组解包遍历 | `for kind, label_or_text, payload in writes:` | 每个元素是三元组 |
| `list[tuple[str, str, str]]` | `writes` 参数注解 | 嵌套泛型注解 |
| `if / elif` | `if kind == "block_append": ... elif kind == "archival_insert":` | 多分支；没有 `else` 时未知值被静默忽略 |
| 字符串切片 | `record.text[:50]` | 取前 50 个字符 |
| 列表推导式带过滤 | `[s.strip() for s in text.split(".") if s.strip()]` | 切分、去空白、丢弃空串 |
| `str.join` 空列表 | `". ".join([])` | 返回空串 `""`——这正是 `_summarize` 返回 `"."` 的原因 |
| `list(...)` 复制 | `return list(self._records)` | 返回浅拷贝，调用方修改列表不影响内部（但记录对象仍共享） |
| 前导下划线 | `_summarize` | 模块内部函数；`from main import *` 不会导入它 |
| 文档字符串 | `"""Handles turns. ..."""` | 类和模块说明 |
| 条件表达式 | `"VALID  " if record.valid else "INVALID"` | 三元表达式 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，瞬间完成），截取关键部分：

```text
primary turns (writes are fast and raw)
  user: my name is ava, I ship agents for a living, I live in Berlin
    block_append -> human v1 (38/180)
  ...
  user: I moved to Lisbon last month; update your notes
    block_append -> human v2 (72/180)
    archival_insert -> a002
  ...
  user: also the curriculum target is senior and staff engineers, not junior
    block_append -> task v2 (119/220)

blocks after primary phase (pre-consolidation)
[human v2 72/180]
  name=ava role=ships_agents city=Berlin city=Lisbon (updated from Berlin)
[persona v0 0/160]
  
[task v2 119/220]
  plan 30-lesson agent curriculum, target senior eng audience=senior+staff eng, cite arXiv and first-party framework docs

sleep-time trace
  sleep-time pass start
    invalidate a002 (human block updated city to Lisbon; Berlin archival claim is stale): ava lives in Berlin - old address, outdated...
  sleep-time pass end

blocks after sleep-time (consolidated)
[human v2 72/180]
  name=ava role=ships_agents city=Berlin city=Lisbon (updated from Berlin)
[persona v0 0/160]
  
[task v2 119/220]
  plan 30-lesson agent curriculum, target senior eng audience=senior+staff eng, cite arXiv and first-party framework docs

archival state
  a001 [VALID  ] ava prefers concise, citation-heavy writing over tutorial-style
  a002 [INVALID] ava lives in Berlin - old address, outdated
```

逐项解读：

- **primary turns**：每次 `block_append` 都返回新版本号和容量，human 从 38 涨到 72，task 从 50 涨到 119。
- **整理前的块**：human 块同时包含 `city=Berlin` 和 `city=Lisbon`；task 块同时包含 `target senior eng` 和 `audience=senior+staff eng`——典型的"只追加不整理"。
- **sleep-time trace**：只有一次 `invalidate`，没有 `consolidate`。原因是两个块都没到 80% 阈值（144 和 176）。
- **"consolidated" 标题名不副实**：整理后的块与整理前逐字相同，版本号仍是 v2。
- **archival**：a002 被标为 `INVALID` 但仍然保留在列表里（作废而非删除）；a001 不受影响。
- 末尾两行"primary-turn latency is unchanged by consolidation"是**声明**而非测量：本程序里两个 agent 串行执行，没有任何计时。

---

## 7. 动手改一改

1. **触发压缩**：给 human 块多 append 几个 `key=value` 事实使其超过 144 字符，再跑 sleep pass，亲眼看到它被改写成 `"."`；然后用测验 Q9 的 `consolidate_kv` 替换 `_summarize`，得到 `name=ava role=ships_agents city=Lisbon ...`。
2. **讲义练习 1**：实现 `block_summarize`（可先用"从最新句子往回取"的规则版），比较阈值 0.6 / 0.8 / 0.9 时摘要调用次数与超限次数。
3. **硬上限**：让 `append` 在超过 `limit` 时返回结构化错误并建议改用 `replace` 或 archival，同时把近上限的块登记到待整理队列（测验 Q10）。
4. **讲义练习 2**：在 sleep pass 中做 archival 去重（Jaccard > 0.9 的记录作废后者），并把作废改为带词边界的匹配（测验 Q11）。
5. **讲义练习 3**：给 `Block` 增加 `rewrite_if(new, expected_version)` 和 diff 记录，重放测验 Q12 的并发时序，验证 lost update 被阻止。
6. **讲义练习 4**：给 persona / safety 块加审核门——sleep agent 的改写先进入 `pending` 字典，由第二个函数检查 diff 中是否删除了约束，通过后才提交。

---

## 8. 常见坑

- **以为 sleep pass 一定做了事**：本次演示的"consolidated"块与整理前完全一样；要看 trace 里有没有 `consolidate` 行。
- **截断当摘要**：从前往后截断会保留旧事实、丢掉新事实，反而制造 memory rot。
- **空列表 `join`**：`". ".join([]) + "."` 得到 `"."`；任何"选出若干项再拼接"的逻辑都要处理"一项都没选中"的情况。
- **用 append 记录更新**：`city=Berlin city=Lisbon` 让模型自己猜哪个是新的；更新应使用 `replace`，或者由 sleep pass 按键合并。
- **子串匹配作废**：没有词边界会误伤无关记录（`Java`、`Berlingen`），换个说法又匹配不到。
- **忽略并发**：sleep agent 基于旧快照改写会覆盖主 agent 的新写入；必须比较版本号。
- **静默忽略写入失败**：块不存在、类型未知时什么都不报，排查"为什么没记住"时无从下手。
- **`description` 不进 prompt**：模型不知道每个块的用途，就不知道该把事实写进哪个块。
