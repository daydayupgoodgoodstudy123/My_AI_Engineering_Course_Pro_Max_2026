# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 09 节 混合记忆：向量、图与 KV ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`time`、`dataclasses`、`typing`）；不调用 LLM、不需要 embedding 模型或数据库

---

## 1. 这份代码在考察什么

这份代码用标准库搭出 Mem0 形状的**混合记忆**：

1. **三个并行存储**：`VectorStore`（用词重叠代替 embedding 相似度）、`KVStore`（以 `(user_id, fact_type, entity)` 为键）、`GraphStore`（类型化的边，带 `valid` 标志）。
2. **统一写入**：`Mem0.add` 一次调用同时写三个存储（讲义中由 LLM 抽取事实，这里由调用者直接给出 `kv_triples` 和 `graph_triples`）。
3. **冲突检测**：图中同一 subject + relation 的新边会让旧边失效（invalid 而非删除），对应 Mem0g。
4. **融合打分**：`relevance + importance + recency` 的加权和，recency 用半衰期指数衰减。
5. **Scope 隔离**：检索时按 `user_id` / `scope` 过滤，防止跨用户泄漏。

> 一句话：**一次写三份、读时打分融合——用"一个 add/search 接口"同时服务语义、事实、关系三类查询。**

需要提前知道的落差（本讲解会逐一实测）：`search` **完全不查询图**，也没有用 KV 的键查找；KV 兜底把用户全部记录以固定 relevance 0.4 塞进结果；scope 过滤只拦截 user scope，session/agent scope 会跨用户泄漏；图的失效不会传播到向量和 KV 中的记录；讲义说"Flip the scoring weights at the top of `main()`"，但 `main()` 顶部并没有权重设置，用的是 `Mem0Config` 默认值。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Record` | dataclass | 一条记忆：`rid`、`text`、`scope`、`user_id`、`session_id`、`importance`、`ts`、`tags` | 记忆记录 |
| `VectorStore` | 类 | 存记录，`search` 用 Jaccard 词重叠打分 | 向量存储（替身） |
| `KVKey` | frozen dataclass | `(user_id, fact_type, entity)`，可哈希，可作字典键 | KV 键 |
| `KVStore` | 类 | `put` / `get` / `by_user` | KV 存储 |
| `Edge` | dataclass | `subject`、`relation`、`obj`、`valid`、`ts` | 图的边 |
| `GraphStore` | 类 | `add_edge`（带冲突失效）、`neighbors`、`all_edges` | 图存储 / Mem0g |
| `Mem0Config` | dataclass | 三个权重 + recency 半衰期 | 融合打分配置 |
| `Mem0` | 类 | `add` 写三个存储；`_recency_score`；`search` 融合打分 + scope 过滤 | Mem0 门面（facade） |
| `main` | 函数 | 写 5 条记忆（ava 4 条、bob 1 条）→ 分别演示向量 / 图 / KV / 融合 / scope 隔离 | 演示 trace |

数据流：`main` → `Mem0.add` × 5（每次：生成 `Record` → 写向量 → 写 KV → 写图边并触发冲突失效）→ 直接调用各存储打印三条召回路径 → `Mem0.search`（向量候选 + KV 兜底 → 加权打分 → 排序截断）。

---

## 3. 逐段精讲

### 3.1 `Record` 与 `VectorStore`

```python
@dataclass
class Record:
    rid: str
    text: str
    scope: str
    user_id: str
    session_id: str
    importance: float = 0.5
    ts: float = field(default_factory=time.time)
    tags: tuple[str, ...] = ()
```

- `scope` 取值 `"user"` / `"session"` / `"agent"`，对应讲义 Scope taxonomy。
- `importance` 由写入方给定（0–1），讲义说也可以"learned"，本代码没有学习机制。
- `ts: float = field(default_factory=time.time)`：每条记录在**创建时**自动取当前时间戳。注意不能写成 `ts: float = time.time()`——那样默认值只在类定义时计算一次，所有记录共享同一个时间。
- `tags` 被存储但检索时从不使用。

```python
    def search(self, query: str, top_k: int = 5) -> list[tuple[float, Record]]:
        q_tokens = set(query.lower().split())
        ...
            overlap = len(q_tokens & r_tokens)
            if overlap == 0:
                continue
            score = overlap / (len(q_tokens | r_tokens))
```

- 打分是 Jaccard 相似度 `|Q ∩ R| / |Q ∪ R|`（与第 07 节相同，这里直接写成集合并集）。讲义称其为"embedding stand-in"，但它与 embedding 的关键差别是**只认字面**：`live` 与 `lives`、`building` 与 `build` 都不匹配，这直接导致了 3.6 中的排序问题。
- 返回的是 `(分数, 记录)` 二元组列表，按分数降序取 `top_k`。
- 向量库对所有用户的记录一视同仁，没有任何按用户的分区或过滤。

### 3.2 `KVStore`：frozen dataclass 作为字典键

```python
@dataclass(frozen=True)
class KVKey:
    user_id: str
    fact_type: str
    entity: str


class KVStore:
    def put(self, key: KVKey, record: Record) -> None:
        self._map[key] = record

    def get(self, key: KVKey) -> Record | None:
        return self._map.get(key)

    def by_user(self, user_id: str) -> list[Record]:
        return [r for k, r in self._map.items() if k.user_id == user_id]
```

- `frozen=True` 让实例不可变，dataclass 会据此生成 `__hash__`，于是 `KVKey` 可以作为 `dict` 的键；两个字段完全相同的 `KVKey` 相等且哈希相同。
- `get` 才是讲义所说的 O(1) 事实查找，但 **`Mem0.search` 从不调用 `get`**，只调用 `by_user`——后者是 O(n) 的全表扫描，返回该用户所有记录。
- ⚠️ **键的设计问题**：`main` 里写的是 `kv_triples=(("city", "Berlin"),)`，即 `entity` 位置放的是**值**。实测 KV 中同时存在 `(ava, city, Berlin)` 和 `(ava, city, Lisbon)` 两个键，互不覆盖；要查"ava 住哪"必须先知道答案才能拼键。合理的建模是 `(ava, city, ava) → "Lisbon"` 或 `(ava, city) → 带时间的版本列表`。

### 3.3 `GraphStore`：冲突即失效

```python
    def add_edge(self, subject: str, relation: str, obj: str) -> None:
        for edge in self._edges:
            if edge.valid and edge.subject == subject and edge.relation == relation:
                edge.valid = False
        self._edges.append(Edge(subject=subject, relation=relation, obj=obj))

    def neighbors(self, subject: str, valid_only: bool = True) -> list[Edge]:
        return [e for e in self._edges
                if e.subject == subject and (e.valid or not valid_only)]
```

- 这是 Mem0g 冲突检测的最简版本：同一个 `(subject, relation)` 上有新边写入时，旧的有效边被标为 `valid=False`，**不删除**——讲义"marked invalid but not deleted"。
- `neighbors(..., valid_only=False)` 返回包括失效边在内的全部历史，`main` 用它展示 `[INVALID] ava --lives_in--> Berlin`。
- `(e.valid or not valid_only)`：`valid_only=True` 时只要有效边；为 `False` 时条件恒真，返回全部。
- ⚠️ 实测的三个问题：
  - **多值关系被误失效**：`owns_project` 先写 curriculum 再写 newsletter，curriculum 被标为失效——一个人可以拥有多个项目。
  - **重复事实自我冲突**：重复写 `lives_in Berlin` 得到一条失效的 Berlin 和一条有效的 Berlin。
  - **没有失效时间**：只有创建时间 `ts`，无法回答"三月时住哪"（讲义练习 2 的 `as_of`）。
- 节点是裸字符串（`"ava"`），没有 `user_id` 命名空间；两个同名用户会互相使对方的边失效。

### 3.4 `Mem0Config` 与 `add`

```python
@dataclass
class Mem0Config:
    w_relevance: float = 0.6
    w_importance: float = 0.2
    w_recency: float = 0.2
    recency_halflife_s: float = 86400.0
```

- 三个权重之和为 1；半衰期 86400 秒 = 1 天。

```python
    def add(self, text: str, *, user_id: str, session_id: str = "s0",
            scope: str = "user", importance: float = 0.5,
            tags: tuple[str, ...] = (),
            kv_triples: tuple[tuple[str, str], ...] = (),
            graph_triples: tuple[tuple[str, str, str], ...] = ()) -> str:
        self._counter += 1
        rid = f"m{self._counter:03d}"
        record = Record(...)
        self.vector.add(record)
        for fact_type, entity in kv_triples:
            self.kv.put(KVKey(user_id=user_id, fact_type=fact_type, entity=entity), record)
        for subject, relation, obj in graph_triples:
            self.graph.add_edge(subject, relation, obj)
        return rid
```

- `*` 之后全是仅限关键字参数，调用必须写 `user_id="ava"`，避免把用户 ID 传错位置。
- 讲义的写路径第 1 步是"Extract candidate facts from the text (an LLM-driven step)"，这里省略了——`kv_triples`、`graph_triples` 由调用者手写，相当于"完美抽取器"。
- 向量和 KV 存的是**同一个 `Record` 对象**（引用），而图里只存三元组字符串，**图边与记录之间没有链接**。所以图知道 Berlin 失效了，但向量和 KV 中的 m003 记录没有任何变化——三个存储之间没有一致性。

### 3.5 recency：半衰期指数衰减

```python
    def _recency_score(self, record: Record, now: float) -> float:
        elapsed = max(0.0, now - record.ts)
        half = self.config.recency_halflife_s
        return 0.5 ** (elapsed / half) if half > 0 else 1.0
```

- `0.5 ** (elapsed / half)`：每过一个半衰期分数减半。刚写入 → 1.0；1 天 → 0.5；2 天 → 0.25；30 天 → 约 `9e-10`（实测）。
- `max(0.0, ...)` 防止时钟回拨导致负的 elapsed、分数大于 1。
- `half > 0` 的保护避免除零；半衰期设为 0 时 recency 恒为 1.0（等于关闭）。
- 讲义说 recency 是"since last write or read"，代码只看写入时间，读取不会刷新。
- ⚠️ 演示中所有记录都在同一秒写入，recency 全部约等于 1.0，这一项变成对所有记录相同的常数 0.2，看不出效果。实测把 m003 的 `ts` 往前拨 30 天后，它从 top-3 中消失。

### 3.6 `search`：融合与过滤

```python
    def search(self, query: str, *, user_id: str,
               scope: str | None = None, top_k: int = 5) -> list[tuple[float, Record]]:
        now = time.time()
        vector_hits = self.vector.search(query, top_k=top_k * 3)
        fused: dict[str, tuple[float, Record]] = {}
        for rel, record in vector_hits:
            if scope is not None and record.scope != scope:
                continue
            if record.user_id != user_id and record.scope == "user":
                continue
            recency = self._recency_score(record, now)
            score = (self.config.w_relevance * rel
                     + self.config.w_importance * record.importance
                     + self.config.w_recency * recency)
            fused[record.rid] = (score, record)
        for record in self.kv.by_user(user_id):
            if record.rid in fused:
                continue
            recency = self._recency_score(record, now)
            score = (self.config.w_relevance * 0.4
                     + self.config.w_importance * record.importance
                     + self.config.w_recency * recency)
            fused[record.rid] = (score, record)
        ordered = sorted(fused.values(), key=lambda x: -x[0])
        return ordered[:top_k]
```

两个候选来源：

1. **向量候选**：先在所有用户的记录中取 `top_k * 3` 条，再按 scope 和 user 过滤，计算加权分。
2. **KV 兜底**：把该用户在 KV 中的**所有**记录加入候选（已在向量候选中的跳过），relevance 固定为 0.4。

`fused` 以 `rid` 为键去重，最后按分数降序截断。

逐一分析问题（全部已实测）：

- ⚠️ **图没有参与检索**。讲义的读路径第 3 步"Graph store returns subgraph reachable from query entities"在代码中不存在。
- ⚠️ **KV 兜底让无关记录胜出**：KV 兜底的 relevance 贡献是 `0.6 × 0.4 = 0.24`，而本演示中真实向量匹配的 relevance 只有 0.08–0.3（贡献 0.05–0.18）。于是**不匹配查询的记录反而比匹配的分数更高**；任何查询都会返回该用户的全部 KV 记录——实测 `"quantum chromodynamics"` 返回 4 条 ava 记录，分数 0.56–0.62。
- ⚠️ **scope 泄漏**：第二个 `if` 只在 `record.scope == "user"` 时检查归属。实测 bob 写入一条 `scope="session"` 的"bob's acquisition plan for acme is confidential"，ava 搜索时能看到。session scope 也不校验 `session_id`。
- ⚠️ **先截断后过滤**：`top_k * 3` 是在所有用户的记录中取的，用户多了以后，当前用户的相关记录可能被别人的记录挤出候选集。
- ⚠️ **失效不传播**：m003 "ava lives in Berlin" 在图中已失效，但仍以正常分数出现在结果中；若用 relevance-only 权重，它甚至排第一。
- 讲义的 `search(query, as_of=timestamp)`（练习 2、skill 文件第 4 条）没有实现。

### 3.7 `main`：五次写入与五段演示

```python
    mem.add(
        "ava moved to Lisbon last month",
        user_id="ava", session_id="s002",
        importance=0.8, tags=("profile", "update"),
        kv_triples=(("city", "Lisbon"),),
        graph_triples=(("ava", "lives_in", "Lisbon"),),
    )
```

- 第 3、4 条写入演示冲突：图中 Berlin 边失效，KV 中两个 city 键并存，向量库中两条记录并存。
- bob 的退款记录用于演示 scope 隔离。
- ⚠️ 第四段打印的标题是 `query 'what is she building'`，实际查询字符串是 `"what is ava building"`——标题与代码不一致（用 `she` 的话 Jaccard 少一个重叠词）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 词重叠代替 embedding | 零依赖、可手算 | 只认字面（`live` ≠ `lives`）；生产用 embedding 模型 + 向量库（讲义提到 Qdrant），并定期重嵌入应对 embedding drift |
| 调用者手写 KV/图三元组 | 跳过 LLM 抽取步骤 | 看不到抽取错误和边爆炸；生产需要可替换的抽取器接口、置信度与每次 `add` 的边数上限 |
| KV 键里放"值" | 示例写起来直观 | 新旧值并存、无法按属性 O(1) 查找；应以属性为键、值带版本 |
| 图冲突 = 同 subject+relation 全部失效 | 实现最简单 | 多值关系被误失效、重复事实自我冲突、无失效时间；应区分单值/多值关系并记录 `valid_from/valid_to` |
| 检索不查图 | 演示保持短小 | 关系推理这一类查询完全没被服务；应从查询中识别实体，取子图并转为候选 |
| KV 兜底固定 relevance 0.4 | 让 KV 记录"总能出现" | 无关记录压过真实匹配；应只对查询解析出的键做精确查找，命中给满分，未命中不加入 |
| 只对 user scope 检查归属 | 只考虑了演示场景 | session/agent 记录跨用户泄漏；所有 scope 都要校验归属，并在存储层预过滤 |
| 三个存储之间无一致性 | 各存储独立、简单 | 图失效了而向量/KV 不知道；生产中让记录、键、边互相引用，失效一起传播 |
| recency 只看写入时间 | 实现简单 | 读取不刷新热度；演示中全部为 1.0，看不出作用 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `field(default_factory=time.time)` | `ts: float = field(default_factory=time.time)` | 每次创建实例时调用 `time.time()`；直接写 `= time.time()` 只在类定义时求值一次 |
| `@dataclass(frozen=True)` | `class KVKey:` | 实例不可变并自动生成 `__hash__`，可以作为字典键或放进集合 |
| 自定义类型作字典键 | `dict[KVKey, Record]` | 键需要可哈希；frozen dataclass 按字段值比较相等 |
| 集合并集 `\|` / 交集 `&` | `q_tokens \| r_tokens`、`q_tokens & r_tokens` | Jaccard 的分母与分子 |
| `time.time()` | `now = time.time()` | 当前 Unix 时间戳（秒，浮点数） |
| 幂运算 `**` | `0.5 ** (elapsed / half)` | 指数衰减 |
| `max(0.0, x)` | `max(0.0, now - record.ts)` | 截断到非负 |
| `X or Y` 默认值 | `self.config = config or Mem0Config()` | `config` 为 None 时使用默认配置（注意：任何"假值"都会触发） |
| 仅限关键字参数 | `def add(self, text, *, user_id, ...)` | `*` 之后的参数必须写参数名 |
| 嵌套元组类型 | `tuple[tuple[str, str, str], ...]` | 任意个三元组 |
| 循环中解包三元组 | `for subject, relation, obj in graph_triples:` | 逐个取出三个字段 |
| `X \| None` 可选类型 | `scope: str \| None = None` | 参数可以不传 |
| `continue` | `if record.rid in fused: continue` | 跳过本次循环剩余部分 |
| `dict` 去重 | `fused[record.rid] = (score, record)` | 同一个 rid 只保留一份 |
| `sorted` + `lambda` | `sorted(fused.values(), key=lambda x: -x[0])` | 按分数降序 |
| 布尔表达式技巧 | `(e.valid or not valid_only)` | `valid_only=False` 时恒为真 |
| f-string 格式符 | `f"{score:.3f}"`、`f"m{self._counter:03d}"` | 三位小数；宽度 3 补零 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，瞬间完成）：

```text
vector-only recall for 'writing style preferences'
  0.222  m001  ava prefers citation-heavy, terse writing over tutorial style

graph recall for entities linked to 'ava'
  [VALID  ] ava --owns_project--> agent_curriculum
  [INVALID] ava --lives_in--> Berlin
  [VALID  ] ava --lives_in--> Lisbon

KV recall for ava all facts
  m001  ava prefers citation-heavy, terse writing over tutorial style
  m002  ava is building a 30-lesson curriculum on agent engineering
  m003  ava lives in Berlin
  m004  ava moved to Lisbon last month

fused top-3 for ava, query 'where does ava live'
  0.430  m002  ava is building a 30-lesson curriculum on agent engineering
  0.427  m004  ava moved to Lisbon last month
  0.406  m003  ava lives in Berlin

fused top-3 for ava, query 'what is she building'
  0.560  m002  ava is building a 30-lesson curriculum on agent engineering
  0.427  m004  ava moved to Lisbon last month
  0.406  m003  ava lives in Berlin

scope isolation: bob's refund does not leak to ava's search
  ava results: 4  (expect 0 user-scoped hits from bob)
    0.620  ava  ava is building a 30-lesson curriculum on agent engineering
    0.600  ava  ava moved to Lisbon last month
    0.580  ava  ava prefers citation-heavy, terse writing over tutorial style
    0.560  ava  ava lives in Berlin
```

逐项解读：

- **向量召回 0.222**：m001 按空白切分得到 8 个 token（`citation-heavy,` 连同逗号算一个），查询 `{writing, style, preferences}` 与它重叠 2 个（`writing`、`style`；`preferences` ≠ `prefers`），`2 / (3 + 8 − 2) = 2/9 = 0.222`。其余记录没有重叠词，所以只返回一条。
- **图召回**：冲突检测正确地把 Berlin 边标为 INVALID 并保留。
- **KV 召回**：4 条记录全部列出，其中 m003（Berlin）和 m004（Lisbon）作为两个不同的 city 键并存。
- **"where does ava live" 排第一的是课程项目**：四条记录都只靠 `ava` 一个词重叠，relevance 都很低（0.08–0.14），importance 0.9 的 m002 胜出；已在图中失效的 Berlin 记录照样排第三。手算见测验 Q9。
- **"what is ava building"**：查询 `{what, is, ava, building}` 与 m002 的 9 个 token 重叠 `is`、`ava`、`building` 3 个词，`3 / (4 + 9 − 3) = 0.3`，得分 `0.18 + 0.18 + 0.2 = 0.56`，这次是合理的第一名。后两名与 building 无关，是靠 `ava` 一词和 importance 混进来的。
- **scope isolation 段**：确实没有返回 bob 的记录（bob 的记录是 user scope，能被正确拦截），但返回了 ava 的 4 条与"refund invoice"毫无关系的记录，分数还高达 0.56–0.62——这些全部来自 KV 兜底（固定 relevance 0.4）。打印的 "expect 0 user-scoped hits from bob" 只验证了"没泄漏"，没验证"结果相关"。
- 讲义 Benchmark 一节引用的 LoCoMo 91.6、LongMemEval 93.4、BEAM 1M 64.1 等数字，代码中没有对应内容；这些数字与 Mem0 原论文（arXiv:2504.19413）摘要的表述方式不一致，引用前建议对照原文核实。

---

## 7. 动手改一改

1. **修复 KV 兜底与 scope 泄漏**：按测验 Q10 重写 `search`，验证 `"refund invoice"`、`"quantum chromodynamics"` 对 ava 返回空，bob 的 session 记录不再泄漏。
2. **让检索用上图**：从查询中识别实体（先用"出现在图节点集合中的词"这一简单规则），取其有效邻居边，把边对应的记录加入候选，relevance 可设为路径权重（直接邻居 1.0，两跳 0.5）。
3. **失效传播**：给 `Record` 加 `valid` 字段，图边记录来源 `rid`；某条边失效时，把对应记录也标为失效，`search` 跳过失效记录。验证"where does ava live"不再返回 Berlin。
4. **讲义练习 2、3**：给边加 `valid_from` / `valid_to`，区分单值与多值关系，实现 `as_of` 查询（测验 Q11 有参考实现）。
5. **体验 recency**：把某些记录的 `ts` 往前拨若干天，分别用 `Mem0Config(0.2, 0.2, 0.6)` 与 `Mem0Config(0.8, 0.1, 0.1)` 搜索，观察排序变化（这才是讲义说的"Flip the scoring weights"）。
6. **讲义练习 1**：若环境允许，用真实 embedding 模型替换 `VectorStore.search`，比较 `"where does ava live"` 的排序，体会"字面匹配 vs 语义匹配"的差别。

---

## 8. 常见坑

- **以为融合会自动用上三个存储**：本代码的 `search` 只用了向量和 KV 的 `by_user`，图只在 `add` 时被写入。
- **兜底候选给固定分数**：只要固定分数高于真实匹配的典型分数，无关结果就会排在前面，而且永远不会返回空。
- **只对一种 scope 做隔离**：隔离条件必须对所有 scope 生效；最好在存储层预过滤。
- **先截断后过滤**：多租户下会让当前用户的结果被别人的记录挤掉。
- **KV 键里放值**：同一属性的新旧值并存，失去"按属性直接查"的能力。
- **冲突检测不区分单值/多值关系**：会把"拥有第二个项目"误判为"不再拥有第一个项目"。
- **失效只发生在一个存储里**：图知道过时了，向量和 KV 不知道，检索照样返回旧事实。
- **`ts = time.time()` 写成类属性默认值**：所有实例共享同一时间戳；要用 `default_factory`。
- **加权和的尺度问题**：三个分量量纲不同，relevance 弱时 importance 会主导排序；权重要在带标注的评测集上调，并考虑先归一化。
