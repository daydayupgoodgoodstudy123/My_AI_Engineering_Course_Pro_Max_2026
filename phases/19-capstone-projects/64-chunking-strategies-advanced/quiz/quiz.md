# 测验 · Chunking 策略比较（Chunking Strategies, Compared）

> **阶段 19 · 综合项目 · 第 64 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Chunking 决定检索上限 | 讲义："The choice of where to cut is not a hyperparameter. It is the upper bound on what the retriever can ever return"——切错了，后面的 embedding、reranker、LLM 都补不回来 |
| 2 | Fixed-window | 每 `size` 个字符切一刀，相邻块重叠 `overlap`（步长 `size − overlap`）；快、确定，但会切断单词与标识符，只适合当对照组 |
| 3 | Sentence 打包 | 按句子边界切分，再把若干句子装进 `target` 字符预算；不会切断单词，但会跨段落、跨小节 |
| 4 | Recursive split | 按"段落 `\n\n` → 行 `\n` → 句子 `. ` → 空格"的顺序递归，块装得下就停，再把相邻小块打包到预算内；讲义称其为"最强的单一策略基线" |
| 5 | Semantic 聚类 | 逐句 embedding，与当前块的质心比较，相似度低于阈值或超过字符上限就切；边界反映语义，但依赖 embedding 模型 |
| 6 | Structural markdown | 在标题处切，每块是"标题 + 下面的内容"；只适用于结构良好的文档 |
| 7 | Recall@k（按 span 重叠） | 每个 query 带有金标准答案的字符区间；top-k 中任一块与之重叠记 1，否则 0，再取平均 |
| 8 | 五种失败模式 | orphan sentence（孤立句）、mid-symbol cut（切断标识符）、header-only chunk（只有标题）、semantic drift（语义漂移）、stale embeddings（换模型后块也变了） |
| 9 | 选默认策略的三个属性 | 文档类型、平均段落长度、是否有显式结构；拿不准时选 recursive |
| 10 | 评估本身的偏差 | "重叠即命中"天然偏爱大块（整篇文档当一块必然命中）；每篇文档单独建索引、块数 ≤ k 时 recall 恒为 1——数字要结合块数与块长一起看 |

### 核心技能（能动手做到）

- [ ] 手写 fixed-window、句子打包、递归切分、语义聚类、markdown 标题切分五个 chunker，并保证每个块都带正确的 `start/end` 字符偏移
- [ ] 用半开区间判断块与金标准 span 是否重叠，写出 recall@k 评估循环
- [ ] 读懂一张 recall 表：结合块数、块长分布判断"赢"是真实的还是评估偏差造成的
- [ ] 把"每篇文档单独建索引"改成"全语料一个索引"，并解释结果为什么会大幅变化
- [ ] 找出并修复 structural chunker 丢失前言、产生只有标题的块等问题
- [ ] 针对新语料，不跑 benchmark 也能根据文档类型与结构给出默认 chunker 与参数

---

## 二、基础自测（选择题）

**Q1.** `fixed_window(doc_id, text, size=400, overlap=80)` 作用于长度 880 的 `PROSE_DOC`，产生的块是：

- A. 2 块：`[0, 400)`、`[400, 800)`，最后 80 个字符被丢弃
- B. 3 块：`[0, 400)`、`[400, 800)`、`[800, 880)`
- C. 4 块：`[0, 400)`、`[320, 720)`、`[640, 880)`、`[800, 880)`
- D. 3 块：`[0, 400)`、`[320, 720)`、`[640, 880)`

**Q2.** `Chunk.overlaps` 的实现是 `not (self.end <= gold_start or self.start >= gold_end)`。下列哪一组返回 `True`？

- A. 块 `[100, 200)`，金标准 `[199, 250)`
- B. 块 `[100, 200)`，金标准 `[200, 250)`
- C. 块 `[100, 200)`，金标准 `[50, 100)`
- D. 块 `[100, 100)`（空块），金标准 `[90, 110)` 中的任何情况都返回 False

**Q3.** `DEFAULT_SEPARATORS = ("\n\n", "\n", ". ", " ")`。recursive split 先尝试 `\n\n` 的原因是：

- A. `\n\n` 在文本中出现的次数最多
- B. Python 的 `str.split` 只支持两个字符的分隔符
- C. 先用"最强"的边界（段落）切，只有段落仍然超出预算时才退到更弱的边界，尽量保留语义完整的单元
- D. 为了让每个块恰好等于 `target` 个字符

**Q4.** 本节运行结果中 `structural` 在三份文档上的 recall@1 都是 1.00。对 `prose` 文档（没有任何 `#` 标题），它实际做了什么？

- A. 自动按段落切成 3 块
- B. 整篇 880 个字符作为 1 块返回；只有一个块时任何 query 的 top-1 都必然与金标准重叠
- C. 抛出 `ValueError`
- D. 回退到 recursive split

**Q5.** 讲义定义的 recall@k（本节 `eval_recall`）是：

- A. top-k 个块中**至少一个**与金标准答案的字符区间重叠的 query 所占比例
- B. top-k 个块中与金标准重叠的块数 / k
- C. 金标准 span 被 top-k 块覆盖的字符比例
- D. 第一个命中块排名的倒数的平均值

**Q6.** 本节 `semantic` 策略在 `prose` 文档（12 个句子）上切出了 11 块。最主要的原因是：

- A. `max_chars = 900` 太小
- B. `split_sentences` 把每个单词都当成一个句子
- C. 代码有 bug，`flush()` 每次都会被调用两次
- D. `mock_embed` 是基于 token 哈希的词袋向量，相邻句子很少共享词，余弦相似度大多低于阈值 0.55（实测相邻句相似度为 0.07、0.40、0.43、0.23…），于是几乎每句都切

**Q7.** 根据讲义"Choosing a default without running the benchmark"的表格，一个 API 文档站点（markdown，层级标题完整）应默认选择：

- A. Fixed-window，size 400
- B. Structural markdown
- C. Semantic，threshold 0.6
- D. Sentence，target 500

**Q8.** 运行结果中，除 semantic 外所有策略的 recall@3 和 recall@5 都是 1.00。最合理的解释是：

- A. mock embedding 的质量非常高
- B. 三份文档都很短，query 很简单
- C. `eval_recall` 为每篇文档**单独**建索引，而这些策略在每篇文档上只切出 1–4 块；当块数 ≤ k 时，top-k 就是全部块，必然命中
- D. `DenseIndex.search` 忽略了 k

---

## 三、动手 / 代码题

**Q9.** 阅读 `structural_markdown`：

```python
_HEADER = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

def structural_markdown(doc_id, text):
    matches = list(_HEADER.finditer(text))
    if not matches:
        return [Chunk(doc_id, "structural", 0, len(text), text)]
    out = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            out.append(Chunk(doc_id, "structural", start, end, body))
    return out
```

输入 `"Preamble text here.\n\n# A\n\nbody a\n\n## A1\n\n### A1a\n\nbody"`：

1. 写出输出的每个块的文本。哪些内容丢了？哪一块属于讲义所说的 "header-only chunk"？
2. 讲义说每块是"the heading plus everything underneath it down to the next heading at the **same or higher level**"。代码的切法与之一致吗？
3. 写一个修正版：保留前言、把只有标题的块与下一块合并（或给每块加上"标题路径"前缀）。
4. 如果 markdown 中有代码块，其中一行是 `# install deps`，会发生什么？

**Q10.** 阅读 `semantic_chunks` 的质心更新：

```python
        else:
            cur_sents.append((s_start, s_end, s_text))
            cur_n += 1
            cur_vec = [(cur_vec[i] * cur_n + v[i]) / (cur_n + 1) for i in range(len(cur_vec))]
            norm = math.sqrt(sum(x * x for x in cur_vec)) or 1.0
            cur_vec = [x / norm for x in cur_vec]
```

1. 第一句向量为 `e1 = [1, 0]`，第二句为 `e2 = [0, 1]`。按这段代码，加入第二句后的（归一化）质心是多少？"两句的平均方向"应该是多少？
2. 指出 bug 并给出修正。
3. 除此之外，用"归一化后的质心 × 句子数"做加权平均，本身是不是精确的均值？更稳妥的做法是什么？

**Q11.** `eval_recall` 对每篇文档单独建 `DenseIndex`。

1. 这种设定对应真实 RAG 中的什么情形？为什么不现实？
2. 把三份文档的所有块放进**同一个**索引，query 只有命中"本文档且与金标准重叠"的块才算对。写出修改后的评估函数。
3. 我们实测的全局索引 recall@1：fixed 0.56、sentence 0.44、recursive 0.33、semantic 0.44、structural 0.33（原表分别为 0.89、0.78、1.00、0.67、1.00）。这说明讲义的结论能否成立？

**Q12.** 句子切分正则是 `(?<=[.!?])\s+(?=[A-Z0-9])`。

1. 对 `MARKDOWN_DOC`，`## Retry Budget` 这一行会落到哪个句子里？为什么？
2. `sentence_chunks` 用 `" ".join(cur_buf)` 生成块文本。在 `PROSE_DOC` 上，块文本与 `text[start:end]` 一致吗？会带来什么问题？
3. 列举两种这个正则会切错的英文句子，并说明生产中通常怎么做句子切分。

---

## 四、面试高频题

**Q13.**（基础必考）RAG 中常见的 chunking 策略有哪些？各自的优缺点和适用场景是什么？

**Q14.**（原理深挖）chunk 大小与重叠如何影响检索质量？为什么"按 span 重叠计算 recall"会偏爱大块？应该如何更全面地评估 chunker？

**Q15.**（工程实践）你要把公司的上万篇内部文档（Confluence 导出的 markdown、PDF 转文本、代码仓库 README）接入 RAG，chunking 这一层你会如何设计？需要在每个块上保存哪些元数据？

**Q16.**（场景设计）用户反馈："问'abort threshold 是多少'，系统总返回关于 retry budget 的段落。"你如何定位问题出在 chunking、embedding 还是排序？

**Q17.**（追问型）语义切分（semantic chunking）听起来最"聪明"，为什么讲义仍然推荐 recursive split 作为默认？什么时候值得用语义切分？

---

## 五、参考答案与解析

### Q1 — 答案：D

步长 = `400 − 80 = 320`，起点 0、320、640；终点 `min(i + 400, 880)` 分别为 400、720、880。第三块到达文本末尾后 `break`，所以只有 3 块，长度 400、400、240（实测一致）。A 没有考虑重叠、而且丢弃了尾部；B 是无重叠的切法；C 多出的 `[800, 880)` 正是 `if end == n: break` 要避免的冗余尾块。

### Q2 — 答案：A

区间是**半开**的 `[start, end)`。A：块结束 200 > 金标准开始 199，块开始 100 < 金标准结束 250，重叠 1 个字符 → True。B：`end <= gold_start`（200 ≤ 200）→ 不重叠；C：`start >= gold_end`（100 ≥ 100）→ 不重叠。D 说法本身是错的：空块 `[100, 100)` 对 `[90, 110)` 而言，`100 <= 90` 为假、`100 >= 110` 为假，返回 **True**——这是半开区间公式对空区间的一个边角情况（各 chunker 都会过滤空块，所以实际不会出现）。

### Q3 — 答案：C

讲义："Try to split on the strongest separator first (double newline, paragraph), fall back to the next... The recursion terminates when the chunk fits the budget." 段落通常是最完整的语义单元，只有段落装不下时才退到行、句子、空格。A 错，出现次数与优先级无关；B 错，`split` 支持任意长度字符串；D 错，目标是"不超过预算"，打包后的块长度不固定（实测 prose 上为 278、305、293）。

### Q4 — 答案：B

`if not matches: return [Chunk(doc_id, "structural", 0, len(text), text)]`——整篇 880 字符作为唯一的块。每篇文档单独建索引时，唯一的块就是 top-1，而它覆盖整篇文档，任何金标准 span 都与它重叠，所以 recall 必然是 1。这不说明 structural 在 prose 上"好"，而是暴露了评估方式的漏洞：一个 880 字符的块塞给 LLM，答案只占其中 62 个字符。A、D 是合理的改进方向（无标题时回退到其它策略），但代码没有这样做；C 错，代码不会报错。

### Q5 — 答案：A

讲义 Key Terms："Fraction of queries where any of the top-k chunks overlaps the gold answer span"。B 是 precision@k 的一种形式；C 是"覆盖率"；D 是 MRR。

### Q6 — 答案：D

`mock_embed` 把每个 `[a-z0-9]+` token 哈希到 96 维中的两个位置，本质是词袋。两句话共享的词少，余弦就低。我们实测 prose 的 11 对相邻句相似度为 `[0.07, 0.40, 0.43, 0.23, 0.05, 0.61, 0.33, 0.16, 0.03, 0.44, 0.39]`，只有一对超过 0.55，所以 12 句被切成 11 块（块长 24–212 字符）。A 错，没有一块接近 900；B 错，切分是按句子；C 错，`flush` 每次切换只调用一次。讲义也提醒："semantic clustering... dependent on the embedding model"——换成真正的语义 embedding，结果会完全不同。

### Q7 — 答案：B

讲义表格："Document type: Markdown / RFC / API docs → Structural markdown"。A 是对照基线；C 对应"短段落、混合主题"；D 对应"长段落、单一主题"。

### Q8 — 答案：C

`eval_recall` 在循环里对每篇文档 `idx = DenseIndex()` 单独建索引。实测每篇文档的块数：fixed 3/2/3、sentence 2/2/2、recursive 3/2/2、structural 1/4/4，只有 semantic 是 11/4/5。块数 ≤ 3 时 top-3 就是全部块，recall@3 必然为 1；structural 在 markdown/mixed 上有 4 块，但它的 recall@1 已经是 1。所以 recall@3/5 这两列几乎没有区分度。A、B 都不是根本原因；D 错，`search` 正确地取了 `scored[:k]`。

### Q9 — 参考答案

1. 实测输出三块：`'# A\n\nbody a'`、`'## A1'`、`'### A1a\n\nbody'`。
   - **前言丢失**：第一个标题之前的 `"Preamble text here."` 不属于任何块——代码只从 `matches[0].start()` 开始切。
   - **header-only chunk**：`'## A1'` 只有标题没有正文（它下面紧跟子标题）。`if body:` 只过滤空块，过滤不了只有标题的块。讲义 Failure modes 说 "Filter those out or attach the next chunk's first paragraph"，代码没做。
2. 不一致。代码在**任何级别**的下一个标题处切，`## B` 的块不包含它的子节 `### B sub`；讲义描述的是"直到同级或更高级标题"，那样父节块会包含子节。两种做法都有道理（前者块小、后者语境完整），但代码与讲义描述不符。
3. 修正思路（保留前言 + 标题路径 + 合并纯标题块）：

```python
def structural_markdown_v2(doc_id, text):
    matches = list(_HEADER.finditer(text))
    if not matches:
        return [Chunk(doc_id, "structural", 0, len(text), text)]
    out, path = [], []                                  # path: [(level, title), ...]
    if matches[0].start() > 0 and text[:matches[0].start()].strip():
        out.append(Chunk(doc_id, "structural", 0, matches[0].start(),
                         text[:matches[0].start()].strip()))
    pending_start = None
    for i, m in enumerate(matches):
        level, title = len(m.group(1)), m.group(2).strip()
        path = [p for p in path if p[0] < level] + [(level, title)]
        start = m.start() if pending_start is None else pending_start
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body_only = text[m.end():end].strip()
        if not body_only:                               # 纯标题：并入下一块
            pending_start = start
            continue
        pending_start = None
        prefix = " > ".join(t for _, t in path)
        out.append(Chunk(doc_id, "structural", start, end,
                         prefix + "\n" + text[start:end].strip()))
    return out
```

   "标题路径前缀"（例如 `Storage Service Configuration > Abort Threshold`）让每个块自带上下文，这也是讲义提到的 contextual chunk headers 思路。注意加前缀后 `chunk.text` 不再等于 `text[start:end]`，偏移仍用于评估。
4. `re.MULTILINE` 下 `^#` 会匹配代码块中的 `# install deps`，于是在代码块中间切出一个"标题"。正确做法是先识别 ``` 围起来的代码块并跳过其中的行，或使用真正的 markdown 解析器（如基于 AST 的解析）。

### Q10 — 参考答案

1. 第一句后 `cur_vec = e1`、`cur_n = 1`。加入第二句时先 `cur_n += 1` 得 2，再算 `(e1 × 2 + e2) / 3 = [0.667, 0.333]`，归一化后 `[0.894, 0.447]`（实测）。两句平均方向应为 `[0.707, 0.707]`。代码让旧质心的权重是新句子的 2 倍。
2. bug：`cur_n` 的自增放在了计算均值**之前**，权重差一。修正为先算再自增：

```python
            cur_vec = [(cur_vec[i] * cur_n + v[i]) / (cur_n + 1) for i in range(len(cur_vec))]
            cur_n += 1
```

   影响：质心偏向块的开头几句，越往后的句子对质心影响越小，"漂移"更难被检测到。
3. 也不精确：`cur_vec` 每次都被归一化成单位向量，再乘以 `cur_n` 当作"n 个向量之和"，这与真正的向量和（长度通常小于 n）不同。更稳妥的做法是维护**未归一化的累加和** `sum_vec += v`，比较时再归一化：`sim = cosine(normalize(sum_vec), v)`。这样既精确又简单。

### Q11 — 参考答案

1. 相当于"系统已经知道答案在哪篇文档里，只在这一篇里找段落"。真实 RAG 是在整个知识库上检索，其它文档的块会与正确块竞争（本节三份文档都讲 retry/abort/authorization，竞争非常激烈）。单文档索引还导致块数 ≤ k 时 recall 恒为 1（Q8）。
2. 参考实现：

```python
def eval_recall_global(chunker, fixture, ks=(1, 3, 5)):
    idx = DenseIndex()
    queries = []
    for doc in fixture:
        for c in chunker(doc["doc_id"], doc["text"]):
            idx.add(c)
        queries += [(doc["doc_id"], q, span) for q, span in doc["queries"]]
    out = {}
    for k in ks:
        hits = 0
        for doc_id, q, (gs, ge) in queries:
            top = idx.search(q, k)
            hits += any(c.doc_id == doc_id and c.overlaps(gs, ge) for c in top)
        out[k] = hits / len(queries)
    return out
```

3. 全局索引下排名完全改变：recursive 和 structural 从 1.00 掉到 0.33，fixed 反而以 0.56 领先。讲义 Build It 中的结论（"Structural-markdown wins on the markdown fixture... Semantic clustering wins on the prose fixture"）在实际运行中本来就不成立（原表 semantic 是最差的 0.67），换成全局索引后更站不住。只有 9 个 query，每个 query 就是 0.11，任何结论都需要更大的评估集。另一个因素是 mock embedding 不去停用词：例如 prose 查询 "what is the abort threshold per bucket" 在 fixed 策略下，不含答案的第 0 块得分 0.529，高于含答案的第 1 块 0.491——"the/is" 这类词主导了相似度。

### Q12 — 参考答案

1. 正则要求边界后面是大写字母或数字，`#` 不满足。所以 `"...describes the storage service knobs.\n\n## Retry Budget\n\nEach client carries a retry budget."` 被当成**一个**句子（实测 `split_sentences(MARKDOWN_DOC)` 的第一项以 `# Storage Service Configuration` 开头，并一直延续到 "Each client carries a retry budget."）。标题被粘到了上一节的最后一句上，这正是"orphan / 错位标题"问题：`## Abort Threshold` 也被粘在 retry budget 那一节的最后一句后面。
2. 不一致。`" ".join` 把原文中句子之间的 `\n\n` 统一换成了空格，实测 prose 上 2 个块 `text == text[start:end]` 的数量为 0/2。偏移仍然正确，所以 recall 评估不受影响；但如果下游用 `text[start:end]` 做高亮或引用，与送进 embedding 的文本不同，调试时会困惑；对 markdown 而言换行被抹掉还会破坏列表、代码格式。更好的做法是直接取 `text[cur_start:cur_end]`。
3. 切错的例子：
   - 缩写："Dr. Smith arrived." 中 `Dr.` 后跟空格和大写 S，被错切；`e.g. The` 同理；
   - 小写开头的句子或以引号、括号开头的句子："It failed. (See logs.)"、"Done. iOS is next." 不会被切开；
   - 小数和版本号不受影响（后面没有空白），但 "v2. Next" 会被切。
   生产中常用 NLTK Punkt、spaCy 的 sentencizer，或基于规则 + 缩写表的切分器；对中文按 `。！？` 切分；对 markdown 先按结构切再在块内切句。

### Q13 — 参考回答要点

| 策略 | 优点 | 缺点 | 适用 |
|------|------|------|------|
| Fixed-window（+overlap） | 实现最简单、确定、块长均匀 | 切断单词/标识符/句子 | 对照基线；无结构的日志类文本 |
| Sentence 打包 | 不切断句子 | 跨段落/小节，标题会粘到句子上 | 无结构的散文 |
| Recursive split | 按段落→行→句→词自适应，结构不一致也稳 | 仍按字符预算，不理解语义 | 默认首选 |
| Semantic 聚类 | 边界跟随话题变化 | 慢、依赖 embedding 模型、换模型块就变、均匀主题会欠切 | 段落短、话题频繁切换 |
| Structural（标题） | 块与文档结构一致、可附标题路径 | 只适用于格式良好的文档；纯标题块、前言丢失需处理 | markdown、RFC、API 文档 |

- 加分点：代码要用 AST 感知的切分（按函数/类）；表格要整体保留；讲义："When in doubt, pick recursive split."

### Q14 — 参考回答要点

- **块太大**：一个块里装了多个主题，embedding 被平均成"模糊"的向量（讲义 semantic drift："A 5000-character chunk packs many specific answers into one diffuse embedding"）；送进 LLM 的无关内容多、成本高，长上下文中间的信息还容易被忽略。
- **块太小**：缺少上下文（孤立句、代词指代不明），embedding 不稳定；同一个答案被拆到多个块里。
- **重叠**：降低"答案恰好被切在边界上"的风险，代价是索引变大、top-k 中出现重复内容。
- **为什么"重叠即命中"偏爱大块**：块越大越容易与金标准 span 重叠，极端情况下整篇文档一块必然命中（本节 structural 在 prose 上就是这样）。
- **更全面的评估**：
  - 同时报告块数、平均块长/分布、top-k 返回的总 token 数；
  - 用"金标准 span 被覆盖的比例 × 返回文本中金标准所占比例"之类的精确度指标；
  - 在全语料一个索引上评估；
  - 端到端评估：最终回答的正确率与忠实度（第 68 节）；
  - 固定 token 预算（例如 top-k 的总长度不超过 2000 token）下比较。

### Q15 — 参考回答要点

- **按文档类型路由**：markdown → 结构化切分（带标题路径）；PDF 转文本 → 先清洗页眉页脚、断行修复，再 recursive；代码 → AST 切分；表格 → 整表或按行组切分并保留表头。
- **硬上限**：任何策略之后再加 token 上限（按目标 embedding 模型的 tokenizer 计算，而不是字符数），超长块继续递归切。
- **上下文增强**：给块加标题路径、文档标题，或用 LLM 生成一句块摘要放在开头（讲义 Further Reading 提到 Anthropic 的 Contextual Retrieval；讲义练习 4 也让你加 summary 字段）。
- **元数据**：`doc_id`、来源 URL、文档版本/更新时间、`start/end` 偏移、标题路径、chunker 名称与参数、embedding 模型版本（讲义 Use It："Persist the strategy name in each chunk's metadata so you can attribute regressions later"）、权限/租户标签。
- **增量更新**：文档变更时只重切、重 embed 受影响的文档；换 embedding 模型时整体重建索引（semantic chunker 的边界也会变）。
- **评估**：上线前在带金标准 span 的评估集上跑 recall@k（全局索引），换模型或语料结构变化时重跑。

### Q16 — 参考回答要点

1. **先看 chunking**：找到包含答案的原文位置，确认它落在哪个块、这个块里还有什么。如果答案与 retry budget 段落被切在同一块，或答案被切断（例如 "three failed parts" 被分到下一块），就是 chunking 问题。
2. **看候选是否进入 top-k**：打印该 query 的 top-20 及分数。正确块排名很低，但它本身内容完整 → embedding/打分问题。
3. **看 embedding**：计算 query 与正确块、错误块的相似度，检查是否被高频词主导。本节的 mock embedding 就有此问题：不含答案的块因共享 "the/is" 而得分更高。可尝试 BM25 + dense 混合（第 65 节）。
4. **看排序**：正确块在 top-20 但不在 top-3 → 加 reranker（第 66 节）。
5. **看 query**：短 query 信息少，可以做 query 改写/HyDE（第 67 节）。
6. **建回归测试**：把这个 query 与金标准 span 加入评估集，修复后确认 recall 改善、其它 query 不退化。

### Q17 — 参考回答要点

- **语义切分的代价**：每个句子都要 embedding，构建索引慢、成本高；结果依赖 embedding 模型，换模型块就变（讲义 stale embeddings）；阈值难调——主题均匀时欠切成巨块，embedding 质量差时过切成碎片（本节 mock embedding 下 12 句切成 11 块）。
- **recursive 的优势**：快、确定、无外部依赖；利用文档自带的段落/换行结构，而作者写的段落边界本身就是很强的语义信号。
- **什么时候值得用语义切分**：段落很长且内部切换话题（会议记录、访谈转写、聊天记录），或者文本几乎没有结构（OCR 结果、一整段的转写）；并且一定要配合硬字符/token 上限。
- **证据**：讲义的运行表中 semantic 在三份 fixture 上的 recall@1 是最低的 0.67，讲义"semantic wins on prose"的说法并未被这次运行支持——是否值得要在自己的语料上评估。
- 加分点：可以把语义切分只用于"recursive 产生的超长块"的二次切分，兼顾两者。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 04 Embeddings 与向量表示](../../../11-llm-engineering/04-embeddings/docs/zh.md)：理解块的 embedding 与余弦相似度。
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：RAG 管线中 chunking 所处的位置。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：chunking 与后续阶段的配合。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../../05-nlp-foundations-to-advanced/23-chunking-strategies-rag/docs/zh.md)：同一主题的 NLP 视角介绍。
- [阶段 19 · 02 代码库 RAG——跨仓库 Semantic Search](../../02-rag-over-codebase/docs/zh.md)：讲义提到的代码 AST 感知切分。

### 本节被哪些后续内容用到
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../65-hybrid-retrieval-bm25-dense/docs/zh.md)：对本节切出的块做混合检索。
- [阶段 19 · 66 基于 Cross-Encoder 的 Reranker](../../66-reranker-cross-encoder/docs/zh.md)：对候选块重排序。
- [阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../68-rag-eval-precision-recall/docs/zh.md)：讲义："The eval harness in lesson 68 reads recall@k from the same shape"。
- [阶段 19 · 69 端到端 RAG 系统](../../69-end-to-end-rag-system/docs/zh.md)：把这里选出的 chunker 作为第一阶段。
- [阶段 14 · 09 混合记忆：向量、图与 KV](../../../14-agent-engineering/09-hybrid-memory-mem0/docs/zh.md)：Agent 记忆同样需要切分与索引。

### 延伸关键词
`fixed-window + overlap` · `recursive character splitter` · `semantic chunking` · `markdown header splitter` · `contextual chunk headers` · `parent-child chunks` · `late chunking` · `token-based chunking (tiktoken)` · `AST chunking` · `recall@k by span overlap` · `chunk length distribution`
