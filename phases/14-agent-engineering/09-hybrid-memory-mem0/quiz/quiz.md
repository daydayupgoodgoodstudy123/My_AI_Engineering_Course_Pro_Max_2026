# 测验 · 混合记忆：向量、图与 KV（Hybrid Memory: Vector + Graph + KV）

> **阶段 14 · Agent 工程 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：本节中文讲义为机器翻译，读不通时请以 [English](../docs/en.md) 为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 单一存储为什么不够 | 三类查询各有赢家：语义相似（"上周聊过的 agent drift"）→ 向量；事实查找（"用户电话"）→ KV；关系推理（"哪些客户共享同一账单主体"）→ 图。只用一种存储，总有两类答错 |
| 2 | Mem0 的写路径 | `add(text, user_id, metadata)`：LLM 抽取候选事实 → 写向量库（embedding）→ 写 KV（键为 `(user_id, fact_type, entity)`）→ 写图（Mem0g，类型化边） |
| 3 | Mem0 的读路径 | 向量 top-k（余弦）+ KV 直接命中 + 图中从查询实体可达的子图 → 打分层融合 |
| 4 | 融合打分 | `score = w_relevance·relevance + w_importance·importance + w_recency·recency`，是加权和而不是层级优先 |
| 5 | 三个维度的来源 | Relevance：向量余弦 / KV 精确匹配 / 图路径权重；Importance：写入时标注或学习得到；Recency：距上次读写时间的指数衰减 |
| 6 | 按产品调权重 | 聊天 agent 提高 `w_recency`；合规 agent 提高 `w_importance`；检索 agent 提高 `w_relevance` |
| 7 | Mem0g 冲突检测与时间推理 | 新事实与已有边矛盾时，旧边标记 invalid 但不删除；"三月时用户住哪"沿"在该时刻有效"的子图遍历 |
| 8 | Scope 分类 | user（跨会话，按 `user_id`）、session（单个线程内）、agent（单个 agent 实例状态）；混用 scope 就会出现"把 Bob 的项目告诉了 Alice" |
| 9 | 三种故障 | Embedding drift（语料增长后向量检索变差 → 定期重嵌入高频记录）、KV schema creep（各团队乱加 `type` → 每季度审计）、Graph explosion（噪声抽取器每条消息加 50 条边 → 每次 `add` 限制边数、丢弃低置信度边） |
| 10 | 本节代码的落差 | 检索完全不使用图；KV 兜底给用户所有记录固定 relevance 0.4，无关查询也返回高分结果；session/agent scope 会跨用户泄漏；图的失效不传播到记录 |

### 核心技能（能动手做到）

- [ ] 给定一个查询，判断它属于语义 / 事实 / 关系哪一类，应由哪个存储回答
- [ ] 手算一条记录的融合分数（Jaccard relevance、importance、半衰期 recency）
- [ ] 解释为什么本节 `search("where does ava live")` 排第一的是"课程项目"而不是"搬到里斯本"
- [ ] 修复 scope 过滤，使任何 scope 的记录都不会泄漏给其他用户，session scope 还要校验 `session_id`
- [ ] 为图边加 `valid_from` / `valid_to`，实现 `as_of` 时间查询，并区分单值关系与多值关系
- [ ] 设计 `user_feedback` 维度并防止"自我强化"的刷分

---

## 二、基础自测（选择题）

**Q1.** 查询"哪些客户共享同一个账单主体（billing entity）？"最适合由哪种存储回答？

- A. 向量存储（语义相似度）
- B. KV 存储（按键直接查找）
- C. 图存储（实体关系推理）
- D. 三者都无法回答，只能用全上下文 LLM

**Q2.** Mem0 融合打分的三个维度是：

- A. Relevance（相关性）、Importance（重要性）、Recency（新近性）
- B. Precision、Recall、F1
- C. Latency、Cost、Accuracy
- D. Vector score、KV score、Graph score 三者取最大值

**Q3.** 按讲义，Mem0g 遇到新事实与已有边矛盾时会：

- A. 直接删除旧边，只保留最新事实
- B. 保留两条边并让 LLM 在检索时自行判断
- C. 拒绝写入新事实，要求人工确认
- D. 把旧边标记为 invalid 但不删除，以支持"某个时刻什么为真"的时间查询

**Q4.** 运行 `code/main.py`，查询 `"where does ava live"`（`user_id="ava"`）的融合结果第一名是：

- A. `m004  ava moved to Lisbon last month`
- B. `m002  ava is building a 30-lesson curriculum on agent engineering`
- C. `m003  ava lives in Berlin`
- D. `m005  bob requested a refund for invoice 4711`

**Q5.** 本节 `_recency_score` 为 `0.5 ** (elapsed / half)`，默认 `recency_halflife_s = 86400`。一条两天前写入的记录，recency 分数是：

- A. 0.5
- B. 0.125
- C. 0.25
- D. 0.0

**Q6.** 本节 `Mem0.search` 中的 scope 过滤为：

```python
            if scope is not None and record.scope != scope:
                continue
            if record.user_id != user_id and record.scope == "user":
                continue
```

如果 bob 写入一条 `scope="session"` 的记录"bob's acquisition plan for acme is confidential"，ava 搜索 `"bob acquisition plan"` 时会：

- A. 搜不到，因为 user_id 不同
- B. 抛出 `KeyError`
- C. 只有当 ava 和 bob 在同一个 session 时才能搜到
- D. 搜得到——过滤只拦截 `scope == "user"` 的他人记录，session / agent scope 的记录跨用户泄漏

**Q7.** 本节写入时用 `KVKey(user_id, fact_type, entity)`，示例中 `kv_triples=(("city", "Berlin"),)` 与后来的 `(("city", "Lisbon"),)`。执行完 `main()` 中的写入后，KV 中关于 ava 城市的状态是：

- A. 两条键 `(ava, city, Berlin)` 与 `(ava, city, Lisbon)` 同时存在，互不覆盖；想查"ava 住哪"必须事先知道答案才能拼出键
- B. 只有 `(ava, city, Lisbon)`，Berlin 被覆盖
- C. 只有 `(ava, city, Berlin)`，Lisbon 写入被拒绝
- D. `(ava, city, Berlin)` 被标记为 invalid

**Q8.** 运行 `main()` 的最后一段：ava 搜索 `"refund invoice"`，结果为 4 条 ava 的记录、分数 0.56–0.62，而这 4 条与"退款发票"毫无关系。原因是：

- A. 向量相似度把 `invoice` 和 `curriculum` 视为近义词
- B. `search` 把用户在 KV 中的**所有**记录以固定 relevance 0.4 加入候选，任何查询都会返回它们，且分数高于真正匹配的向量结果
- C. recency 权重过高
- D. bob 的记录被错误地标成了 ava 的 user_id

---

## 三、动手 / 代码题

**Q9.** 手算 `"where does ava live"` 的融合分数（默认权重 0.6 / 0.2 / 0.2，所有记录刚写入，recency ≈ 1.0）。向量相关度为 Jaccard：`overlap / |Q ∪ R|`。

| 记录 | 文本 | importance |
|------|------|-----------|
| m002 | `ava is building a 30-lesson curriculum on agent engineering` | 0.9 |
| m003 | `ava lives in Berlin` | 0.6 |
| m004 | `ava moved to Lisbon last month` | 0.8 |

1. 写出三条记录的 relevance 和融合分数。
2. 为什么"课程项目"排第一？为什么已经被图标记为过时的 Berlin 仍然出现在结果中？
3. 若把权重改为 relevance-only（1, 0, 0），排序会变成什么？这说明了什么？

**Q10.** 重写 `Mem0.search`，修复两个问题：

- scope 泄漏：任何 scope 的记录都不能返回给其他用户；session scope 还要求 `session_id` 一致；
- KV 兜底：只有当查询解析出具体的 `(fact_type, entity)` 键时才走 KV，命中时给满分 relevance；不要把用户全部记录塞进候选。

另外说明：为什么应该"先过滤 scope、再截断 top-k"，而不是像原代码那样先取 `top_k * 3` 再过滤？

**Q11.** 讲义练习 2、3：实现带时间的冲突检测与 `as_of` 查询。

```python
    def add_edge(self, subject: str, relation: str, obj: str) -> None:
        for edge in self._edges:
            if edge.valid and edge.subject == subject and edge.relation == relation:
                edge.valid = False
        self._edges.append(Edge(subject=subject, relation=relation, obj=obj))
```

1. 原实现对 `("ava", "owns_project", "curriculum")` 之后再写 `("ava", "owns_project", "newsletter")` 会怎样？重复写同一条 `("ava", "lives_in", "Berlin")` 又会怎样？
2. `Edge` 只有 `valid` 和创建时间 `ts`，为什么不足以回答"ava 在时间 t 住在哪"？
3. 写出带 `valid_from` / `valid_to` 的实现，并区分单值关系与多值关系。

**Q12.** 讲义练习 4：给融合打分加一个 `user_feedback` 维度（用户对检索结果点赞）。

1. 写出新的打分公式和一种 feedback 分数的计算方式；
2. "agent 只返回它已经被点赞过的记录"这种刷分（gaming）是怎么发生的？给出至少三种防御手段。

---

## 四、面试高频题

**Q13.**（基础必考）为什么 agent 记忆不能只用一个向量数据库？请用三类查询举例说明向量、KV、图各自的优势。

**Q14.**（原理深挖）解释 Mem0 的融合打分。为什么是加权和而不是"先看 KV、再看向量"的层级？三个权重怎么调？加权和有什么固有问题？

**Q15.**（工程实践）多租户场景下，你如何保证记忆不会跨用户泄漏？请从数据模型、检索路径和测试三个层面回答。

**Q16.**（场景设计）用户三月说"我住柏林"，五月说"我搬到里斯本"，七月问"我三月时住哪？"和"我现在住哪？"。请设计能正确回答两个问题的写入与检索流程。

**Q17.**（追问型）你说用 LLM 从对话中抽取事实写进三个存储。抽取器出错了怎么办？如果它每条消息抽出几十条边呢？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义原例："Relationship reasoning — 'which customers share the same billing entity?' Graph wins; vector and KV cannot answer." 这类问题需要沿"客户 → 账单主体 ← 客户"的边做多跳遍历。A 只能找到语义相似的文本片段；B 需要预先知道键；D 不符合讲义结论。

### Q2 — 答案：A

讲义公式：`score = w_relevance * relevance + w_importance * importance + w_recency * recency`。D 是一种常见误解：融合不是在三个存储的分数中取最大值，三个存储都只贡献 relevance 这一项（向量余弦、KV 精确匹配、图路径权重），另外两项来自记录本身的属性。B、C 是评估指标。

### Q3 — 答案：D

讲义："When a new fact contradicts an existing edge, the existing edge is marked invalid but not deleted. Temporal queries ('what was the user's city in March?') traverse the valid-at-time subgraph." A 会丢失历史、无法审计；B 把矛盾推给检索时的 LLM；C 不是 Mem0 的做法。

### Q4 — 答案：B

实际输出：

```text
fused top-3 for ava, query 'where does ava live'
  0.430  m002  ava is building a 30-lesson curriculum on agent engineering
  0.427  m004  ava moved to Lisbon last month
  0.406  m003  ava lives in Berlin
```

查询词 `live` 与记录中的 `lives` 不匹配，四条 ava 记录都只靠 `ava` 一个词重叠获得很低的 relevance（0.08–0.14），于是 importance（m002 为 0.9）主导了排序。详细计算见 Q9。D 被 user 过滤掉了；C 排第三。

### Q5 — 答案：C

`elapsed / half = 2 × 86400 / 86400 = 2`，`0.5² = 0.25`。A 是一天前；B 是三天前；D 只有 elapsed 趋于无穷时才成立（实测 30 天前约为 `9e-10`，已可忽略）。注意 `main()` 中所有记录都是刚写入的，recency 全都约等于 1.0，所以这一项在演示里只是一个对所有记录相同的常数 0.2，看不出效果。

### Q6 — 答案：D

已实际运行验证：ava 搜索 `"bob acquisition plan refund"` 时，结果中出现了 `('bob', 'session', "bob's acquisition plan for acme is confidential")`。第二个 `if` 只在 `record.scope == "user"` 时比较 user_id，对 session 和 agent scope 的记录完全不检查归属，也不检查 session_id。C 描述的是"正确实现"应有的行为（且还应要求是同一用户）。讲义："Mixing scopes without thought is how you get 'the assistant told Alice about Bob's project' incidents." 代码末尾打印的 "scope isolation: bob's refund does not leak" 只测了 user scope，恰好避开了这个漏洞。

### Q7 — 答案：A

实测 KV 中的键为 `('city', 'Berlin')` 和 `('city', 'Lisbon')`，两者并存；`kv.get(KVKey("ava", "city", "Berlin"))` 仍返回 "ava lives in Berlin"。代码把"值"放进了 `entity` 位置，导致：

- 同一属性的新旧值不会互相覆盖，KV 层没有冲突检测；
- 想 O(1) 查"ava 的城市"，需要先知道答案是 Berlin 还是 Lisbon 才能构造键——KV 失去了"事实查找"的意义。

合理的键应是 `(user_id="ava", fact_type="city", entity="ava")` → 值 `"Lisbon"`，或干脆 `(user_id, fact_type)` → 值。B、C、D 都不是代码行为。

### Q8 — 答案：B

`search` 的第二个循环：

```python
        for record in self.kv.by_user(user_id):
            if record.rid in fused:
                continue
            ...
            score = (self.config.w_relevance * 0.4 + ...)
```

`by_user` 返回该用户在 KV 中的**所有**记录，与查询毫无关系；每条都得到 `0.6 × 0.4 = 0.24` 的 relevance 分。而真正与查询匹配的向量结果 relevance 通常只有 0.08–0.3（乘以 0.6 后 0.05–0.18）。结果是：**不匹配的记录反而比匹配的记录分数更高**，任何查询（实测 `"quantum chromodynamics"` 也一样）都会返回这 4 条，分数 0.56–0.62。代码注释"expect 0 user-scoped hits from bob"只验证了没泄漏 bob 的记录，却没注意到返回了 4 条无关结果。

### Q9 — 参考答案

1. 查询 token `{where, does, ava, live}`（4 个）：

| 记录 | 记录 token 数 | 交集 | 并集 | relevance | 融合分数 = 0.6·rel + 0.2·imp + 0.2·1.0 |
|------|-------------|------|------|-----------|-----|
| m002 | 9 | 1（ava） | 12 | 0.0833 | 0.05 + 0.18 + 0.2 = **0.430** |
| m004 | 6 | 1 | 9 | 0.1111 | 0.0667 + 0.16 + 0.2 = **0.427** |
| m003 | 4 | 1 | 7 | 0.1429 | 0.0857 + 0.12 + 0.2 = **0.406** |

   与实际输出一致（m001 为 0.3945，排第四）。
2. **课程排第一**：查询里的 `live` 与 `lives` 不匹配，相关信号只剩"都提到了 ava"，relevance 之间的差距（最多 0.06 × 0.6 ≈ 0.04）小于 importance 的差距（0.9 vs 0.6，乘 0.2 后 0.06），于是 importance 主导。这说明：**当 relevance 信号弱时，加权和会让"重要但无关"的记录胜出**。
   **Berlin 仍出现**：冲突检测只发生在图上（`ava --lives_in--> Berlin` 被标为 INVALID），但 `search` 根本不查询图，向量库和 KV 里的 m003 记录也没有任何"失效"标记。三个存储之间**没有一致性**：图知道 Berlin 过时了，向量和 KV 不知道。
3. 实测 relevance-only 排序为 `m003 (0.1429) > m004 (0.1111) > m001 (0.0909) > m002 (0.0833)`——**过时的 Berlin 排第一**。若查询改为 `"where does ava lives"`，默认权重下 m003 也以 0.52 排第一。说明 importance 和 recency 不仅是"微调"，而是在 relevance 不可靠时防止陈旧结果的关键；同时也说明必须把失效状态传播到所有存储。

### Q10 — 参考答案

```python
class SafeMem0(Mem0):
    def _visible(self, r, user_id, session_id):
        if r.user_id != user_id:                       # 任何 scope 都先按用户隔离
            return False
        if r.scope == "session" and r.session_id != session_id:
            return False
        return True

    def search(self, query, *, user_id, session_id=None, scope=None, top_k=5, kv_keys=()):
        now, c = time.time(), self.config
        fused = {}
        cands = [(rel, r) for rel, r in self.vector.search(query, top_k=10**9)
                 if self._visible(r, user_id, session_id)
                 and (scope is None or r.scope == scope)]
        for rel, r in cands[: top_k * 3]:              # 先过滤、后截断
            fused[r.rid] = (c.w_relevance * rel + c.w_importance * r.importance
                            + c.w_recency * self._recency_score(r, now), r)
        for ft, ent in kv_keys:                        # 只有查询解析出的键才走 KV
            r = self.kv.get(KVKey(user_id, ft, ent))
            if r and self._visible(r, user_id, session_id):
                fused[r.rid] = (c.w_relevance * 1.0 + c.w_importance * r.importance
                                + c.w_recency * self._recency_score(r, now), r)
        return sorted(fused.values(), key=lambda x: -x[0])[:top_k]
```

实测：

- `search("refund invoice", user_id="ava")` → `[]`（原实现返回 4 条无关记录）；
- `search("quantum chromodynamics", user_id="ava")` → `[]`；
- `search("bob acquisition plan", user_id="ava")` → `[]`（不再泄漏 bob 的 session 记录）；
- bob 在 `s011` 中能搜到自己的 session 记录，在 `s012` 中搜不到；
- 传入 `kv_keys=(("city", "Lisbon"),)` 时，m004 以 0.96 排第一。

（`kv_keys` 在真实系统中由查询理解步骤——通常是 LLM 或规则——从 query 中解析；本例为演示直接传入。）

**为什么先过滤再截断**：原代码 `self.vector.search(query, top_k=top_k * 3)` 在**所有用户**的记录里取前 15 条，再丢掉不属于当前用户的。多租户下，其他用户的记录可能占满这 15 个名额，当前用户真正相关的记录被截掉，召回率随用户数增长而下降；而且这本身就意味着检索层"看到了"别人的数据。生产中应把 `user_id` 作为向量库的**预过滤条件**（metadata filter / 分区 / namespace），在检索阶段就隔离。

### Q11 — 参考答案

1. 实测：
   - `owns_project` 先写 curriculum、再写 newsletter → `[('curriculum', False), ('newsletter', True)]`。原实现把**所有**同 subject + relation 的边都视为互斥，但一个人可以同时拥有多个项目——多值关系被错误地失效了。
   - 重复写同一条 `lives_in Berlin` → `[('Berlin', False), ('Berlin', True)]`。相同事实也会"自我冲突"，产生一条无意义的失效记录和一条重复边（对应讲义 Graph explosion 的风险）。
   - 另外，图节点只用裸字符串 `"ava"`，没有 `user_id` 命名空间：两个不同用户都叫 ava 时会互相使对方的边失效。
2. `valid` 只是一个当前状态的布尔值，`ts` 是创建时间，但**失效时间没有记录**。要回答"时刻 t 什么为真"，需要知道每条边的有效区间 `[valid_from, valid_to)`；只有布尔值无法区分"三月有效、五月失效"和"四月才写入"。
3. 实现（已运行验证）：

```python
from dataclasses import dataclass

@dataclass
class TEdge:
    subject: str
    relation: str
    obj: str
    valid_from: float
    valid_to: float | None = None

class TemporalGraph:
    SINGLE = {"lives_in"}                         # 单值关系才互斥（可配置）

    def __init__(self):
        self.edges, self.log = [], []

    def add_edge(self, s, rel, o, at):
        for e in self.edges:
            if e.valid_to is None and e.subject == s and e.relation == rel:
                if e.obj == o:
                    return                         # 重复事实：不新建、不失效
                if rel in self.SINGLE:
                    e.valid_to = at                # 失效而非删除，记录失效时刻
                    self.log.append(f"invalidate {s}-{rel}->{e.obj} by {o} at {at}")
        self.edges.append(TEdge(s, rel, o, at))

    def as_of(self, s, rel, t):
        return [e.obj for e in self.edges
                if e.subject == s and e.relation == rel
                and e.valid_from <= t and (e.valid_to is None or t < e.valid_to)]
```

   测试：t=100 写 Berlin、t=200 写 Lisbon、t=300 再写一次 Lisbon；`as_of(150)` → `['Berlin']`，`as_of(250)` → `['Lisbon']`，`as_of(50)` → `[]`；多值的 `owns_project` 在 t=260 返回 `['curriculum', 'newsletter']`；边总数 4（重复的 Lisbon 未新建），日志记录了"Berlin 被 Lisbon 在 200 时刻失效"（练习 3 要求"log both"）。
   讲义练习 2 问"哪个存储改动最大"：向量库最难——embedding 本身没有时间语义，需要在每条记录上加有效区间元数据并在检索时过滤；KV 需要从"键 → 值"变成"键 → 带时间的版本列表"；图在加了区间之后最自然。

### Q12 — 参考答案

1. 公式：

```text
score = w_rel·relevance + w_imp·importance + w_rec·recency + w_fb·feedback
feedback = (up + 1) / (up + down + 2) − 0.5        # 拉普拉斯平滑，范围约 (−0.5, 0.5)
```

   平滑保证"被看过一次就点赞"的记录不会立刻得到满分；减去 0.5 使没有反馈的记录贡献为 0。
2. **刷分如何发生**：点过赞的记录分数更高 → 更常被检索出来 → 获得更多曝光和点赞 → 分数更高。这是推荐系统中经典的反馈循环（rich-get-richer），最终 agent 只返回少数"老熟人"记录，新写入的、或者更相关但还没被评价的记录永远排不上来。
   **防御**：
   - 给 `w_fb` 设上限（如不超过 relevance 权重的一部分），并且**只在 relevance 超过阈值的候选中**使用 feedback 重排，而不是让它决定候选集；
   - 平滑与衰减：feedback 也随时间衰减，旧的点赞逐渐失去作用；
   - 探索：保留少量名额给没有反馈的新记录（类似 ε-greedy / bandit）；
   - 按曝光归一化：用"点赞数 / 曝光数"而非点赞总数；
   - 反馈按查询上下文记录（这条记录对"住址"类查询有用，不代表对所有查询有用）；
   - 离线评估：在固定测试集上比较加入 feedback 前后的 recall，防止线上指标"变好"而实际质量下降。

### Q13 — 参考回答要点

- **语义相似**（"上周我们讨论 agent drift 时说了什么"）：查询与记忆的措辞不同，需要 embedding 相似度——向量库胜出；KV 需要精确键，图需要明确实体，都答不了。
- **事实查找**（"用户的电话号码是多少"）：答案是一个确定值，KV 以 `(user_id, fact_type, entity)` 为键 O(1) 命中；向量检索既慢又可能返回一堆"提到电话"的片段，讲义称之为"wasteful"，图则"overkill"。
- **关系推理**（"哪些客户共享同一账单主体"）：需要多跳遍历实体关系——图胜出；向量和 KV 都无法表达"共享"这种结构。
- **结论**：讲义："Production agents issue all three in one session. A single-store memory is always wrong for two of them." Mem0 的贡献是把三者藏在一个 `add`/`search` 接口后面，用打分层融合。
- 加分点：图还天然支持时间有效性（Mem0g 的失效边），向量库要额外加元数据才能做到；同时承认代价——三套存储的运维、写放大、一致性问题（见本节代码里图失效了但向量记录没失效）。

### Q14 — 参考回答要点

- **公式**：`w_rel·relevance + w_imp·importance + w_rec·recency`。relevance 来自三个存储（余弦 / 精确匹配 / 路径权重），importance 来自写入时标注或学习，recency 是指数衰减。
- **为什么不是层级**：层级（"KV 命中就直接返回"）在 KV 命中的是陈旧值时会出错；加权和允许"非常相关但旧"与"稍不相关但新且重要"相互权衡。讲义明确说"it is a weighted sum, not a hierarchy"。
- **怎么调**：讲义——聊天 agent 提高 recency；合规 agent 提高 importance；检索 agent 提高 relevance。实践中用一组带标注的查询做离线评估（recall@k、MRR），网格搜索权重；"Tune per product, not per call"（skill 文件）。
- **固有问题**：
  - 三个分量的**尺度**不一致（Jaccard 0–0.3、importance 0.5–0.9、recency 0–1），权重的含义被尺度扭曲，应先归一化；
  - relevance 弱时，importance 会让"重要但无关"的记录胜出（本节 Q9 的现象）；
  - 不同存储的 relevance 不可直接比较（KV 精确命中给多少分？本节代码给固定 0.4，结果比真实匹配还高）；
  - 可考虑 RRF（倒数排名融合）等基于排名而非分数的融合，或把 importance/recency 作为 relevance 过阈值后的重排因子。

### Q15 — 参考回答要点

- **数据模型**：每条记录、每个 KV 键、每条图边都带 `user_id`（以及 `org_id`）；session scope 还带 `session_id`，agent scope 带 `agent_id`。图节点也要按用户命名空间隔离（本节图节点只用 `"ava"` 这样的裸字符串）。
- **检索路径**：
  - 隔离条件在**存储层预过滤**（向量库 metadata filter / namespace / 分库），而不是取回后在应用层过滤（本节先取 `top_k*3` 再过滤，Q10）；
  - 所有 scope 都校验归属——本节代码只对 `scope == "user"` 检查 user_id，session/agent 记录跨用户泄漏（Q6）；
  - 跨 scope 检索必须显式传参并有每个 scope 的权重（skill 文件："Cross-scope retrieval without per-scope weights or an explicit `scope=` filter" 是 hard reject）。
- **测试**：为每种 scope 写"用户 A 写、用户 B 搜"的负向测试，并把它放进 CI；对随机生成的多用户数据做属性测试（返回结果的 user_id 必须全部等于查询者）；上线后对检索日志做抽样审计。
- 加分点：讲义称 scope leak 为合规与隐私事故；涉及 PII 时，抽取器本身也需要产品负责人审计（skill 文件的 refusal rule）。

### Q16 — 参考回答要点

- **写入（三月）**：抽取 `(ava, lives_in, Berlin)`；图中新建边 `valid_from=三月`；KV 写 `(ava, city) → [Berlin @三月]`；向量库写记录并带 `valid_from`。
- **写入（五月）**：抽取 `(ava, lives_in, Lisbon)`；冲突检测发现 `lives_in` 是单值关系，把 Berlin 边的 `valid_to` 设为五月（失效不删除）；KV 追加新版本；向量库中旧记录加 `valid_to=五月`。失效状态要**同步到所有存储**。
- **检索"我现在住哪"**：解析为事实查询，KV 取最新有效版本 → Lisbon；或图 `as_of(now)`。
- **检索"我三月时住哪"**：解析出时间约束，图 `as_of(三月)` → Berlin（Q11 的实现）；向量检索过滤 `valid_from ≤ 三月 < valid_to` 的记录。
- **对照本节代码**：图能标记 Berlin 失效，但没有失效时间、无法 `as_of`；KV 中 Berlin、Lisbon 两个键并存；向量记录不知道失效；`search` 不查图——所以本节实现两个问题都可能答错（Q9 中 relevance-only 时 Berlin 排第一）。

### Q17 — 参考回答要点

- **抽取器出错的影响**：抽错的事实会同时进入三个存储，并且通过冲突检测**使正确的旧事实失效**——错误会"传染"。
- **应对**：
  - 每条抽取结果带置信度和来源（哪个会话、哪一轮、原文片段），低置信度的不写图或只写向量；
  - 抽取器接口化，测试时用确定性的规则/正则替身（skill 文件："allow a deterministic regex fallback for tests"）；
  - 失效而非删除，保证可回滚；为冲突写日志，抽样人工复核；
  - 对涉及 PII 或合规的领域，抽取器上线前需要审计。
- **边爆炸**：讲义："One noisy extractor adds 50 edges per message. Cap graph writes per `add` call; drop low-confidence edges." 另外：去重（同一事实不重复建边，本节代码会重复建边，Q11）、合并同义关系、限制关系类型白名单（与"KV schema creep"一样定期审计 type/relation 集合）。
- 加分点：抽取发生在写路径上，可以像 [阶段 14 · 08](../../08-memory-blocks-sleep-time-compute/docs/zh.md) 的 sleep-time compute 一样异步执行，并用更强的模型。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../07-memory-virtual-context-memgpt/docs/zh.md)：archival memory 的来源，本节是它的多存储实现。
- [阶段 14 · 08 记忆块与休眠时计算](../../08-memory-blocks-sleep-time-compute/docs/zh.md)：作废而非删除、sleep-time 整理，是 Mem0g 冲突检测的近亲。
- [阶段 11 · 04 Embeddings 与向量表示](../../../11-llm-engineering/04-embeddings/docs/zh.md)：向量存储的基础（本节用词重叠代替 embedding）。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：混合检索与分数融合（如 RRF）。

### 本节被哪些后续内容用到
- [阶段 14 · 10 技能库与终身学习（Voyager）](../../10-skill-libraries-voyager/docs/zh.md)：把"技能"作为另一种可检索的记忆。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：为记忆读写打 span。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../27-prompt-injection-defense/docs/zh.md)：检索结果作为不可信输入的处理。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：用评测集调融合权重。

### 延伸关键词
`Mem0` · `Mem0g` · `hybrid memory` · `fusion scoring` · `RRF` · `fact extraction` · `temporal knowledge graph` · `valid_from / valid_to` · `scope isolation` · `metadata pre-filter` · `embedding drift` · `LoCoMo` · `LongMemEval`
