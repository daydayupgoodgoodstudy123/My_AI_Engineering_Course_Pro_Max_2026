# 参考答案讲解：memgpt（14/07）

计时结束后再看。参考实现在同目录的 `memgpt/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修记忆工具

**现象**：解锁后的第一个失败是 archival 检索结果里的引用。期望 `a002 [s7#4]`，实际是 `a002 [s0#0]`。`archival_memory_search` 的格式化本身没有错。

**顺着往上找**：结果里的 session 和 turn 直接来自 `ArchivalRecord`，记录里存的就是默认值，说明写入时没有传进去。`MemoryTools.archival_memory_insert` 只把 `tags` 交给了 `ArchivalStore.insert`，`session_id` 和 `turn_id` 落到了默认的 `"s0"` 和 `0`。课里把这叫 citation loss：记得事实，却说不出是哪一轮说的。这一关想练的是：报错的位置（检索的输出）不是出 bug 的位置（写入）。

**依次修四处**：

1. 写入时转交 `session_id=self.session_id, turn_id=self.main.turn`。turn 用 `main.turn`，也就是最新一条消息的编号；不能用 `len(main.messages)`，第 4 轮时第 1 条已经被挤出，上下文里只剩 3 条。
2. `core_memory_replace` 先确认 old 恰好出现一次。参考实现用两次 `find`：第一次找到位置，第二次从下一个字符开始再找，找到了就是有歧义，返回错误，不改。这样连重叠的出现也算成两次；用 `count(old) > 1` 判断也能通过测试。按整词匹配不行：出现指的是子串，`java` 里的 `ava` 也算。
3. `tokens()` 改成每条消息单独估算再相加，再加上摘要的估算：`approx_tokens(summary) + sum(approx_tokens(m.text) ...)`。拼成一段估算时，三条两个词的消息被算成 ceil(7.8) = 8，而不是 3 + 3 + 3 = 9。
4. 检索加倒排索引。插入时把记录的 token 集合存下来，同时登记 `token → [记录位置]`；查询时只遍历查询词的倒排表，累加每条候选记录的重叠数：

```python
for term in query_terms:
    for position in self._postings.get(term, ()):
        shared[position] = shared.get(position, 0) + 1
scored = [(overlap / (len(query_terms) + len(self._terms[position]) - overlap), position)
          for position, overlap in shared.items()]
scored.sort(key=lambda item: (-item[0], item[1]))
```

150 次查询从 1.4 秒左右降到 4 毫秒左右。只预分词、查询时仍然逐条扫描，大约是 0.17 到 0.21 秒，还是太慢：每次查询仍然要碰 2 万条记录。

**护栏**：

- 分数要和原来一模一样。倒排表里每条记录每个 token 只登记一次（用集合，不用原始 token 列表）；查询也先去重；分词不能顺手去掉标点；公式还是 |q ∩ r| / |q ∪ r|。
- 并列按插入顺序。候选是按倒排表读到的顺序进字典的，不是插入顺序，所以排序键里必须带上位置。只按分数排、或者候选放进 set，大样本上很快就会排错；按 rid 字符串排也不行，a10000 会排在 a2000 前面；按 turn 排也不行，turn 是每个会话自己的编号。
- 两个会话里的同一条事实是两条记录，各有各的引用，不能按文本去重。
- 主上下文：恰好等于 max_tokens 时不挤；最新一条消息永远留下；挤出的消息进 recall，`conversation_search` 还找得到；core 段有自己的上限，不算进 max_tokens。

## Part 2 SQLite archival

参考实现只有一张表。模块 docstring 只规定了 turn_id 列声明成 INTEGER，主键怎么设、其余几列怎么存，是参考实现自己的选择：

```sql
CREATE TABLE IF NOT EXISTS archival (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    tags TEXT NOT NULL,          -- JSON 数组，保持顺序
    session_id TEXT NOT NULL,
    turn_id INTEGER NOT NULL
)
```

rid 由 seq 生成（`a{seq:03d}`）。`SqliteArchive` 继承 `ArchivalStore`：打开文件时按 seq 读出所有行，经过 `_keep` 放进内存，Part 1 的索引也就一起建好了，所以 `get`、`records`、`search` 都不用重写；`insert` 先写库、提交，再 `_keep`；`delete` 先用 `get` 确认 id 存在（不存在就是 KeyError），删行、提交，再把内存重新装一遍。

要点：

- **id 不重用**：`AUTOINCREMENT` 让 SQLite 在 `sqlite_sequence` 里记住用过的最大值，删掉最新的一行后也不会再发出同一个号。普通的 `INTEGER PRIMARY KEY` 会用当前最大值加 1，删掉 a003 以后又发出 a003。旧答案引用过 a003，重用就等于把引用指向了另一条事实。
- **往返一致**：tags 用 JSON 存、读回后转成 tuple；逗号拼接对 `lang:zh-Hans,en` 和空 tags 都会出错，转小写会把 `zh-Hans` 改掉。text 原样存，不 strip。turn_id 照 docstring 用 INTEGER 列，测试顺带按类型核对：声明成 TEXT 会读回字符串，声明成 REAL 会读回浮点数，而 `40.0 == 40`，只比相等看不出来。
- **提交**：每次 insert 和 delete 都用 `with self._db:` 提交。测试在第一个连接还开着时另开一个连接读，只在 close 时提交是看不到的；delete 不提交，关闭连接时就被回滚了。
- **顺序**：按 seq 排序。按 rid 字符串排序在 a1000 以后就乱了；按 turn_id 排也不对，turn 是每个会话自己的编号。

## Part 3 BM25 与 recall@k

构造时把每条记录分好词，记下 tf（`Counter`）、长度和每个词的文档频率 n(t)；N 是记录数，avgdl 是所有记录长度的平均值，空记录也算在内。打分时对查询里的每个 token（重复的也算）累加：

```
idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d) / avgdl))
idf(t) = ln(1 + (N - n(t) + 0.5) / (n(t) + 0.5))
```

只在 tf > 0 时才算长度归一化，所以空库和全是空记录的库都不会除零。结果只保留分数大于 0 的，按 (−分数, 位置) 排序，取前 top_k 条。位置是记录在传入列表里的位置，不是 rid：测试把 TINY 倒过来再建一次，并列时 a005 排在 a002 前面。

几个容易错的地方：

- 经典的 IDF `ln((N - n + 0.5) / (n + 0.5))` 对出现在一半以上记录里的词是负数。小样本里 `tool` 在 5 条里出现了 4 条，用经典公式它的分数是负的，会被当成没命中。
- tf 和 n 是两回事：`drift drift tool` 里 drift 的 tf 是 2，但它只让 n(drift) 加 1。
- 分词必须和 archival 一样。这样 recall 的差别只来自打分方式。

recall@k 对每个 case 算“前 k 条里找到的相关记录数 / 相关记录数”，再对所有 case 取平均，一条结果都没有的 case 记 0。分母是相关记录数，k 比它小也一样：两条相关记录、k=1 时找到一条，recall 是 1/2，不是 1。调用时用 `search(query, k)`，archival 的 search 默认只给 3 条。没有相关记录的 case 和空的 case 列表都报 ValueError，不悄悄跳过。这组事实上：

| | recall@1 | recall@3 | recall@5 |
|---|---|---|---|
| 词重叠（Jaccard） | 4/9 | 6.5/9 | 8/9 |
| BM25 | 7/9 | 8/9 | 8/9 |

差别主要来自 IDF：`what is the deploy target` 里的 is、the 在大多数记录里都有，Jaccard 把它们和 deploy、target 一样计数，于是又短、又和查询共享 what、is 两个词的 `it is what it is` 排了第一；BM25 给只出现在一条记录里的 deploy、target 高得多的权重。what 也只出现在一条记录里，但 `it is what it is` 只命中这一个稀有词，比不过同时命中 deploy 和 target 的 a004。到 k=5 词重叠也追上了：BM25 的好处在排在前面的几条，而主上下文每次只放得下几条。两种方法都找不到 `which cloud do we use`，因为相关记录里一个查询词都没有：BM25 还是字面匹配。

## Part 4 中断式分页

每来一条消息：

```python
before = ctx.tokens()
message = ctx.push(role, text)
if before < warn_tokens <= ctx.tokens():
    yield line(memory_pressure)          # 先报，agent 还来得及存
while ctx.tokens() > ctx.max_tokens and len(ctx.messages) > 1:
    paged = ctx.evict()                  # 只挤到放得下，原文进 recall
    yield line(page_out)                 # 挤出就报
    ctx.summary = await summarize(ctx.summary, paged)
    yield line(summary)                  # 新摘要也占预算，可能还要再挤
```

- **一次 yield 一个事件**，测试在每个事件之间都能做事。memory_pressure 是 agent 的中断：测试收到它时把最旧的消息存进 archival，这条事实的引用是触发它的那一轮（第 8 轮）。
- **只在跨线时报**。用挤出前后的 token 数比较，不需要额外的状态；恰好等于 warn_tokens 也算跨线。
- **摘要占预算**。第 6 轮先挤出第 2、3 轮，这时上下文是 32；摘要从 6 个 token 涨到 16 个，又变成 42，只好再挤出第 4 轮。
- **最新一条消息自己就超预算时**，挤完更早的消息就停，循环条件里的 `len(ctx.messages) > 1` 就是为这个写的。
- 格式由测试的 `"".join(...)`、`splitlines()` 和逐行 `json.loads` 决定：每个事件后面恰好一个 `\n`。

## Part 5 类型化 core memory

参考实现把 schema 建成一棵 `_Section` 树，每个节点记着完整路径、上限、父节点和子节点（文本段没有子节点）。三件事都是在这棵树上做的：

- **查路径**：按 `.` 切开，一层一层往下找，找不到就是 KeyError，包括空的一段和穿过文本段往下找；找到的是 group 时，写文字报 TypeError。
- **查上限**：算出新文本比旧文本长了多少，从这一段开始沿父节点往上走，第一个超限的就是最内层的那个，报 CoreLimitError；全部通过才真正写入，所以被拒绝的写入什么都不改。如果把段摊平成以路径为键的字典，group 的用量要按 `路径 + "."` 前缀求和，否则名字以它开头的兄弟段也会被算进来：测试最后的小 schema 里，`human_notes` 的文字不能算进 `human`。
- **渲染**：按 schema 的顺序递归，每层缩进两个空格，每一段都输出名字和用量；group 不带冒号，文本段有内容时带 `: 文本`。

上限按 `len(str)` 算字符，`Ava 林小雨` 是 7。append 的分隔空格是文本的一部分，也算进上限。replace 沿用 Part 1 的“恰好出现一次”。

## 这套题证明了什么，没证明什么

通过了说明你能在 MemGPT 式的记忆代码里顺着引用找到写入时的根因、在不改变检索结果的前提下加倒排索引、把带出处的记录无损地存进 SQLite 并保证 id 永不重用、实现 BM25 并用 recall@k 和基线比较、写出事件即时产出的流式分页器，以及处理带逐层上限的嵌套结构。它不涉及真正的模型调用（摘要器和 agent 都是测试里的脚本）、真实的 tokenizer、向量检索、多进程同时写入，也不涉及课里讲的 memory poisoning 防御和 Letta 的三层记忆，这些需要另外动手（见第 08、09、27 课）。
