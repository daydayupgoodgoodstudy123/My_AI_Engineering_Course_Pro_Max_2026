# 参考答案讲解：HybridMem（14/09）

计时结束后再看。参考实现在同目录的 `hybridmem/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修作用域检索和图存储

**现象**：解锁后的第一个错误是 `memory_block` 里的 `ScopeLeak: m004 (agent memory of bob) reached ava's prompt`，而 `memory_block` 本身没有 bug。

**顺着往上找**：`memory_block` 只是把 `search` 的结果逐条检查后写进 prompt，bob 的那条 agent 记忆是 `search` 给它的。`search` 交给向量库的谓词是 `record.scope != "user" or record.user_id == viewer.user_id`，只挡住别人的 user 记忆：bob 的 session 和 agent 记忆，ava 自己在 s1 的 session 记忆和 writer agent 的记忆，全都放了过去。完整的规则写在 `Viewer.can_see` 里：先看是不是同一个用户，session 记忆再看 session，agent 记忆再看 agent。课里说的 “the assistant told Alice about Bob's project” 就是这么来的。

**依次修五处**：

1. **可见性**：`self.vector.search(query, top_k=top_k * 3, where=viewer.can_see)`，手写的 `visible` 删掉。
2. **删掉 KV 兜底**。谓词修好以后，ScopeLeak 换成了 m002，ava 在 s1 的登录码。它和 “acme plan” 没有一个共同的词，是 `search` 末尾那段循环加进来的：`kv.by_user(viewer.user_id)` 的每条记录都以固定的 relevance 0.4 进了候选，这就是课里 `code/main.py` 的写法。docstring 写明 search 只走向量路径，和查询没有共同词的记忆不会出现。只给这段循环补上 `can_see` 不够：“refund invoice” 和谁都不沾边，兜底照样把 ava 的 m001 带回来，分数 0.56，比 m001 真正匹配上 “acme plan” 时的 0.39 还高，测验 Q8 说的就是这个。KV 命中要来自查询解析出来的键，那是 Part 3 `recall` 的事。
3. **重复声明什么都不改**：`if old.obj == obj: return old`。只有 object 不同才算矛盾。原来的写法会把 lisbon 那条边在 4000 关掉，再开一条一样的，历史里多出一段假的区间，事实开始的时间也变了。
4. **按 (subject, relation) 建索引**：`self._current[(subject, relation)]` 指向现在成立的那条边，`current()` 直接查字典，`add_edge` 写入时更新。2.4 万条边的快照上做 4000 次冲突写入，从 1.3 秒左右降到 1.5 毫秒左右。
5. **`restore()` 也要维护索引**。快照里的边不经过 `add_edge`，不放进索引的话 `current()` 查不到它们，冲突写入就不会关闭旧边，有效边多出 4000 条。索引是派生状态，每一条往存储里放边的路径都要维护它。

**护栏**：

- 30 个别人的“退款已批准”比 ava 自己那条更像查询，而且是 session 记忆，起始代码的谓词拦不住它们。起始代码的过滤本来就在截断之前，`where` 是存储层的预过滤，修的时候要把正确的谓词留在那里。改成取回以后再过滤、把候选池放大，或者留着 `visible` 再在循环里补一道 `can_see`，ava 自己那条都会被挤掉；取回来以后在应用层过滤，检索层也已经“看见”了别人的数据。只在 `memory_block` 里跳过泄漏的记录也不对，`search` 自己的结果里照样有别人的记忆。
- 被作废的边只关闭、不删除。为了提速直接删旧边，或者干脆只留一个“当前边”的字典，历史就没了，Part 5 的时点查询也无从谈起。
- “同一个事实见过就不再写”也不对：ava 搬回 berlin 时，旧的 berlin 边已经关闭，要新开一条。判断重复只看现在成立的那条边。
- 索引要以 (subject, relation) 为键。只按 subject 建，ava 的 works_at 会把 lives_in 关掉。
- 重复声明时不能改 `valid_from`、不能把边的 rid 换成新记录、也不能换成新的权重，要按 docstring 原样返回已有的边。

## Part 2 SQLite 三存储

参考实现每个存储一张表：

```sql
CREATE TABLE IF NOT EXISTS records (seq INTEGER PRIMARY KEY, rid TEXT NOT NULL UNIQUE, text TEXT NOT NULL,
    scope TEXT NOT NULL, user_id TEXT NOT NULL, session_id TEXT NOT NULL, agent_id TEXT NOT NULL,
    importance REAL NOT NULL, ts REAL NOT NULL, tags TEXT NOT NULL, last_read REAL);
CREATE TABLE IF NOT EXISTS kv (user_id TEXT NOT NULL, fact_type TEXT NOT NULL, entity TEXT NOT NULL,
    rid TEXT NOT NULL, PRIMARY KEY (user_id, fact_type, entity));
CREATE TABLE IF NOT EXISTS edges (seq INTEGER PRIMARY KEY, subject TEXT NOT NULL, relation TEXT NOT NULL,
    obj TEXT NOT NULL, rid TEXT NOT NULL, weight REAL NOT NULL, valid_from REAL NOT NULL, valid_to REAL);
```

列名和列类型照模块 docstring，主键和约束是自己定的：records 和 edges 各加一个 seq 主键记下写入顺序，kv 以 (user_id, fact_type, entity) 为主键。`save` 建表以后，在一个事务里先 DELETE 三张表，再整批 INSERT，`with db:` 负责提交或回滚。`load` 先读 records 放进 vector store，再按 rid 取出同一个 Record 对象放进 KV，边逐条 `restore()`，最后把计数器设成最大的 rid 数字。

容易漏的几点：

- **边没有自然键**。ava 搬回 lisbon 以后，历史里有两条 (ava, lives_in, lisbon)，一条已关闭、一条还成立，所以不能拿三元组做主键或唯一键。唯一键在第二次 save 时报 IntegrityError；`INSERT OR REPLACE` 不报错，却把已经关闭的那条删了，历史少了一段。
- **顺序靠 seq**。记录不按 ts 排，边不按 valid_from 排：bob 那条记录来自时钟慢的节点，ts 比 m001 还早；测试里还有一条倒填日期的边。
- **时间戳的精度**。第二条记录的 ts 是 1.7e9 再加 2⁻²² 秒。float 在 1.7e9 附近的间距约是 2.4e-7 秒，比一微秒还细，转成 ISO 8601 或者取整到微秒都会丢。
- **tags 是有序元组**。JSON 能原样保存顺序，读回来要转回 tuple。用逗号拼接会把空元组读回成 `("",)`，还会把 `"refund, approved"` 拆成两个。
- **KV 存 rid，不存记录**。读回时 KV 指向 vector store 里的同一个对象。各拷一份的话，Part 3 刷新 last_read 只会改到其中一份。
- **第二次保存是替换**。不清表直接插入会撞主键；`INSERT OR IGNORE` 看起来没问题，可已经关闭的 porto 边和刷新过的 last_read 都没写进去。
- **rid 计数**。重开以后要从最大的 rid 接着数，否则下一条又叫 m001，在 dict 里悄悄覆盖掉第一条记忆。按字符串取 `MAX(rid)` 在 m999 之后会出错（"m999" > "m1005"），`ORDER BY rid` 也一样。
- **导出任务直接读表**。kv 每个键一行；还成立的边 valid_to 是 NULL，写成 0 的话，导出会以为它已经关闭。
- **`restore()` 维护索引**。这是 Part 1 的修复延伸过来的：重开以后的图要能接着检测冲突。
- **时钟要传下去**。`load` 用传进来的 clock 建 Mem0，重开以后写的记录和关闭的边才用注入的时钟，不会混进真实时间。
- **列类型照 docstring**。浮点列都是 REAL，能逐位存准。测试的 `exact()` 区分 1 和 1.0，顺带检查了整秒的 ts（1700000000.0）和权重 1.0：声明成 INTEGER 或 NUMERIC 时，SQLite 会把能无损转成整数的值存成整数，读回来是 int。`1 == 1.0` 在 Python 里成立，普通的相等比较看不出来。

## Part 3 融合打分

`recall` 先让三个存储各自报候选，统一经过一个 `offer`：

```python
def offer(record, value):
    if value > 0 and viewer.can_see(record) and record.scope in config.scope_weights:
        relevance[record.rid] = max(value, relevance.get(record.rid, 0.0))
```

- 向量：查询和记录的词频向量（`Counter(tokens(...))`）算余弦。点积为 0 时直接返回 0，空查询就不会除零。
- KV：对 `query.kv_keys` 里的每个 (fact_type, entity)，用 `KVKey(viewer.user_id, fact_type, entity)` 精确查找，命中给 `KV_HIT`。
- 图：现在成立的边，subject 或 object 在 `query.entities` 里，就把这条边的权重给断言它的那条记录。

然后对每个候选算 `scope_weights[scope] * (w_relevance * relevance + w_importance * importance + w_recency * recency)`，recency 是 `0.5 ** (max(0, now - touched) / halflife_s)`，halflife 为 0 时取 1.0。按 (-score, rid) 排序，截到 top_k，最后把返回的记录的 last_read 设成 now。

几个要点：

- **和课里代码的区别**。课里的 `VectorStore` 用 Jaccard，这里是词频向量的余弦。KV 只查查询解析出的键，这是测验 Q10 的写法：Part 1 从 `search` 里删掉的那个 KV 兜底，在 `recall` 里同样不能有，只有被某个存储真正找到的记录才是候选。
- **多个存储找到同一条记录时取最大**。lease 被向量（1/√14 ≈ 0.27）、KV（1.0）和两条图边（0.75、0.5）同时找到，相关度是 1.0。相加会超过 1，先到为准是 0.27，后到为准是 0.5。
- **每条路径都要过 `can_see`**。KV 的键里有 user_id，看起来天然隔离，但 session 记忆照样要看 session；图的节点是全局字符串，bob 的 `works_on acme` 和 ava 的查询实体连在一起，最容易出“把 Bob 的项目告诉 Alice”的事故。
- **recency 用最后一次读或写**（`Record.touched`）。只看 ts 的话，读过也不算；有 last_read 就只看 last_read 也不对，那条“未来”写入的记录 ts 比 last_read 还晚。
- **先打分、后刷新，只刷新返回的**。先刷新的话，所有候选的 recency 都是 1.0；刷新所有候选，第二次查询时被截掉的记录也成了“刚读过”。
- **权重原样用**。三个权重加起来是 1.25，归一化会把所有分数缩小。
- **并列按 rid**。lease 和 carol 都是 0.8125（这些数在二进制里都能精确表示，并列不受计算顺序影响）；两条一样的 “call the landlord” 被 KV 键按相反的顺序找到，只按分数的稳定排序会把 m002 排在前面。

## Part 4 写入审计

`ingest` 是一个 async generator，逐个处理事件：

- **Message**：`await extract(text)` 拿到候选，`mem.add` 存成记录（没有候选也存）。低于阈值的记 `drop, low_confidence`；其余的按置信度降序取前 `max_edges` 个（`sorted(..., key=lambda i: -confidence)` 是稳定排序，并列时保留先列出的），剩下的记 `drop, over_cap`。保留的候选如果和现在成立的边相同，记 `skip, restated`；否则写进图（rid 是这条消息的记录，权重是置信度），记 `write, new` 或 `write, conflict`，冲突时紧接着给被关闭的旧边一行 `invalidate, superseded`。所有行按抽取器给的顺序输出。
- **Lookup**：`mem.search` 返回的每条记录使用次数加一。每第 `reembed_every` 次 lookup，取使用次数最多的 `reembed_top` 条（至少用过一次，并列按 rid），依次 `await reembed(record)`，写一行 `record, <rid>, , , reembed, uses=<n>`，再把计数清零。

每一行用 `csv.writer` 写进一个 `StringIO` 再 yield，引号、逗号、换行都由 csv 模块处理；决定一行就 yield 一行，探针拉第一个事件时第一行就出来了。

容易错的几处：

- 上限按置信度取，不是取抽取器列出的前 `max_edges` 个：seq 3 里 `owns dog`（0.5）列在 role 前面，`passing[:max_edges]` 会留下它、丢掉 based_in。
- 已经成立的事实也占名额：seq 6 先按置信度留下 lives_in、country、city，再把已经成立的 lives_in 记成 skip，排第四的 likes 是 over_cap。先剔掉已经成立的再截上限，likes 就会写进图。
- `Counter.most_common` 并列时按第一次出现的顺序：bob 先查了 lisbon，m004 第一个被用到，于是排在 m001 前面。要自己按 (-uses, rid) 排序，并且排除计数为 0 的记录。
- 只数 lookup：把消息也算进去，第一次重嵌入会落在第 12 个事件（bob 的那次 lookup）上，而不是第 10 个。
- 使用次数要从 `mem.search` 来，它带着 Part 1 修好的可见性；`vector.search` 会把 ava 的记录算进 bob 的查询。
- 课里练习 3 说冲突时 “invalidate the old edge and log both”，这里就是 write 和 invalidate 两行。

## Part 5 时点图查询

一条边在 `[valid_from, valid_to)` 上成立。`value_at` 在 `history(subject, relation)` 里找那个时刻成立的边。`paths` 先把那个时刻成立的边按 subject 分组，再做深度优先搜索：

```python
def walk(node, trail, seen, weight):
    for edge in out.get(node, ()):
        if edge.obj in seen:
            continue
        step, w = trail + (edge,), weight * edge.weight
        if edge.obj == target:
            found.append(Path(w, step))
        elif len(step) < max_hops:
            walk(edge.obj, step, seen | {edge.obj}, w)
```

`seen` 是这一条路径上的节点，每一层传一个新集合，回溯时自然就恢复了。最后按 (-weight, 跳数, 每一跳的 (relation, object)) 排序。

- **半开区间**：MAY 那一刻 berlin 已经关闭，lisbon 已经成立。
- **用区间，不用 `valid`**：`valid` 说的是现在。三月时 globex 的客户经理是 carol，这条边现在已经关闭，但回答三月的问题时要用它。
- **每一跳都切时间**：四月起 globex 的客户经理换成了 dave，所以四月经过 globex 的路都改走 dave。
- **共享节点不是环**：从 ava 出发经过 globex 的路有两条（customer_of 和 partner_of），全局的 visited 会丢掉第二条；按节点序列去重也会丢掉它，因为两条路经过的节点完全一样，只是关系不同。
- **全部路径**：找到一条进入 carol 的路以后还要接着搜，3 跳的 `ava -manages-> bob -knows-> dave -refers-> carol` 和 1 跳的 mentors 权重一样，按跳数排在后面。

## 这套题证明了什么，没证明什么

通过了说明你能在一个多存储的记忆服务里，从 prompt 层的报错追到检索层，把跨用户、跨会话的泄漏修在根上，也认得出课里那种把用户全部 KV 记录塞进结果的兜底；能让冲突检测只作废真正矛盾的边，并让索引覆盖每一条写入路径；能把三个存储存进 SQLite 并逐位读回；能实现 Mem0 式的融合打分（多存储取最大、作用域权重、读写都算的半衰期 recency）；能写一个按置信度限流、带审计的流式写入管道；也能在带时间区间的图上回答时点的多跳问题。

它没有涉及真实的 embedding 模型和向量索引（ANN、预过滤怎样下推到索引）、LLM 抽取器本身的质量、Postgres、Qdrant、Neo4j 这类真实后端、多写者并发、用户的删除请求，以及 LoCoMo、LongMemEval 这些评测。课里的练习 1 和练习 5 需要另外动手。MemGPT 式的分页和 Letta 的记忆块在本章 07、08 课。
