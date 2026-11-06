# 测验 · 面向 RAG 的 Chunking 策略（Chunking Strategies for RAG）

> **阶段 05 · NLP 从基础到进阶 · 第 23 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过 `main.py` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Chunking 的分量 | 讲义引用 Vectara（NAACL 2025）：chunking 配置对检索质量的影响与 embedding 模型选择相当；切错了，重排序也救不回来 |
| 2 | Fixed | 每 N 个字符/token 切一刀；最简单的 baseline，会切断句子甚至单词 |
| 3 | Recursive | 依次尝试 `\n\n` → `\n` → `. ` → 空格，优先在大结构边界切；2026 年的默认选择 |
| 4 | Sentence / Semantic | 按句切或按相邻句 embedding 相似度骤降处切；semantic 更慢，没有最小长度约束时会产生 40 token 级碎片 |
| 5 | Parent-document | 用小的 child chunk 检索、返回大的 parent chunk 作上下文；多个 child 指向同一 parent 时要去重 |
| 6 | Late chunking | 先对整篇文档做 token 级编码，再把 token 向量池化成 chunk 向量，保留跨 chunk 上下文；需要长上下文 embedder，算力更高 |
| 7 | Contextual retrieval | Anthropic 2024：用 LLM 为每个 chunk 生成"它在全文中的位置/背景"并拼在前面再索引；其基准中检索提升 35–50%，索引成本高 |
| 8 | 按查询类型定大小 | 事实型 256–512 token；分析/多跳 512–1024；整节理解 1024–2048 |
| 9 | 反直觉发现 | 2026 年的研究：overlap 常常没有可测收益却让索引变大；recursive 512 在某研究中胜过 semantic；上下文约 2,500 token 处出现质量"悬崖" |
| 10 | 护栏 | 必须有 min/max chunk 大小约束；不能让一个 chunk 跨两篇文档；评测要按查询类型分层 |

### 核心技能（能动手做到）

- [ ] 从零实现 fixed（含 overlap 校验）、recursive、sentence、semantic、parent-child 五种切分函数
- [ ] 能手算 `chunk_fixed` 在给定 size/overlap 下产生的 chunk 数量与边界，并指出尾部冗余 chunk
- [ ] 能发现并修复"recursive 切分没有对超长片段继续递归"导致 chunk 超过上限的 bug
- [ ] 能识别评测中的"指标饱和"（chunk 数 ≤ top-k 时 recall 必然 100%），并设计更有区分度的评测（recall@1、MRR、更多文档、分层查询）
- [ ] 能解释 semantic chunking 中标题被"粘"到上一个 chunk 的原因，并用"先按段落切、再在段落内语义切"修复
- [ ] 能为一个具体语料（合同、论文、对话、短评）选出切分策略、大小、overlap 与 min/max 护栏，并给出 50 条分层查询的 recall@5 评估方案

---

## 二、基础自测（选择题）

**Q1.** LangChain 的 `RecursiveCharacterTextSplitter`（以及讲义的 `chunk_recursive`）尝试分隔符的顺序是：

- A. 空格 → `. ` → `\n` → `\n\n`
- B. `\n\n` → `\n` → `. ` → 空格，都不行再按固定长度切
- C. 只按 token 数切
- D. 先算句子 embedding，再按相似度切

**Q2.** 关于 parent-document 模式，正确的是：

- A. 用 parent 检索、返回 child，以节省上下文
- B. 用小 child 检索以提高精度，返回其所属的大 parent 以提供上下文；多个 child 命中同一 parent 时要去重
- C. parent 和 child 必须用不同的 embedding 模型
- D. 它要求 child 之间有 50% overlap

**Q3.** Late chunking 与传统"先切再编码"的根本区别是：

- A. 在检索之后才切分
- B. 先对整篇文档做 token 级编码，再把 token 向量按 chunk 池化，每个 chunk 向量都"看过"全文上下文
- C. 完全不切分，整篇文档一个向量
- D. 用 BM25 代替 embedding

**Q4.** 关于 Anthropic 的 contextual retrieval，下列说法**错误**的是：

- A. 为每个 chunk 生成一段说明它在全文中位置与背景的文字，拼在 chunk 前面再索引
- B. Anthropic 自己的基准中检索提升约 35–50%
- C. 它在查询时为每个 chunk 调用 LLM，因此在线延迟很高
- D. 主要成本在建索引阶段

**Q5.** 关于 chunk overlap，讲义的立场是：

- A. 至少 20% overlap 是行业标准，必须使用
- B. 2026 年的研究发现 overlap 常常没有可测收益却增加索引成本；默认 0，大于 20% 需要消融实验证明有用
- C. overlap 只对 BM25 有用
- D. overlap 越大召回越高

**Q6.** 你的 RAG 主要回答"公司 CEO 叫什么""合同金额是多少"这类问题，讲义建议的 chunk 大小是：

- A. 64 token
- B. 256–512 token
- C. 1024–2048 token
- D. 整篇文档一个 chunk

**Q7.** 下列做法中，哪一项违反了讲义的 Pitfalls？

- A. 对每篇文档分别切分，再把所有 chunk 合并建索引
- B. 给 semantic chunking 设置最小 token 数
- C. 把多篇短文档首尾拼接成一个长字符串后统一按 512 token 切分
- D. 评测集按事实型、分析型、多跳型分层

---

## 三、动手 / 代码题

**Q8.** 阅读 `main.py` 的 `chunk_fixed`：

```python
def chunk_fixed(text, size, overlap=0):
    if size <= 0:
        raise ValueError("size must be positive")
    step = size - overlap
    if step <= 0:
        raise ValueError("overlap must be less than size")
    return [text[i:i + size] for i in range(0, len(text), step) if text[i:i + size].strip()]
```

1. `chunk_fixed("abcdefghij", size=4, overlap=2)` 返回什么？最后一个 chunk 有什么问题？
2. 如果删掉 `if step <= 0` 这个检查，调用 `chunk_fixed(text, size=100, overlap=100)` 会发生什么？
3. 用 `main.py` 中 716 个字符的合同、`size=300, overlap=50` 切分，第二个 chunk 的开头是 `"hapter 3. Termination. ..."`。为什么会这样？这说明 fixed 切分的什么缺点？

**Q9.** 找 bug：`main.py` 的 `chunk_recursive` 与讲义 Step 1 的版本相比少了一段逻辑。

```python
def chunk_recursive(text, size, seps=("\n\n", "\n", ". ", " ")):
    if len(text) <= size:
        return [text.strip()] if text.strip() else []
    for sep in seps:
        if sep not in text:
            continue
        parts = text.split(sep)
        chunks = []
        buf = ""
        for p in parts:
            candidate = buf + sep + p if buf else p
            if len(candidate) <= size:
                buf = candidate
            else:
                if buf:
                    chunks.append(buf.strip())
                buf = p
        if buf:
            chunks.append(buf.strip())
        return [c for c in chunks if c]
    return chunk_fixed(text, size)
```

已知：

```python
long_para = "This is sentence number one. " * 20      # 约 580 字符，没有换行
t = "Short intro.\n\n" + long_para
print([len(c) for c in chunk_recursive(t, 300)])   # 输出 [12, 579]
```

1. 为什么会得到一个 579 字符、超过 `size=300` 的 chunk？
2. 请修复，使所有 chunk 都不超过 `size`。

**Q10.** `main.py` 的评测输出：

```text
fixed (300 chars, 50 overlap):    3 chunks
recursive (300 chars):            3 chunks
semantic (hash-trick):            11 chunks
sentence (3 per chunk):           7 chunks
parent-child (800 / 200):         5 children, 1 parents

=== recall@3 on 3 queries ===
  fixed       : 3 / 3
  recursive   : 3 / 3
  semantic    : 3 / 3
  sentence    : 3 / 3
  parent      : 3 / 3
```

1. 为什么说 fixed、recursive、parent 三行的 3/3 是"必然的"，与 embedding 好坏无关？（提示：看 chunk 数和 `top_k`；`parent` 那一行传入的是 `[m["parent"] for m in pc]`。）
2. 程序最后打印 "production embedders (BGE, text-3) give 20-40 pp higher recall on the same chunks."，在这个输出下这句话有什么问题？
3. 提出至少三条改进，让这个评测能真正区分不同切分策略。

**Q11.** semantic 切分的 11 个 chunk 中有这样两个：

```text
'Late payments incur a five percent fee. Chapter 3.'
'Termination. Either party may terminate this agreement with ninety days written notice.'
```

`chunk_semantic` 的核心逻辑如下（`threshold=0.3, min_chars=40`）：

```python
    for i in range(1, len(sentences)):
        sim = cosine(embs[i], embs[i - 1])
        if sim < threshold and len(" ".join(chunks[-1])) >= min_chars:
            chunks.append([sentences[i]])
        else:
            chunks[-1].append(sentences[i])
```

1. 标题 `Chapter 3.` 为什么被粘到了第 2 章内容的末尾，又和 `Termination.` 分开了？（已知 `len("Late payments incur a five percent fee.") == 39`，且这几句之间的哈希余弦都是 0。）
2. 给出一个修复思路并写出代码。

---

## 四、面试高频题

**Q12.**（基础必考）RAG 中常见的 chunking 策略有哪些？各自的优缺点和适用场景是什么？

**Q13.**（场景设计）用户把一份 50 页合同放进 RAG，问"终止条款是什么？"，系统却返回了封面页。请分析可能原因，并给出你的 chunking 方案。

**Q14.**（原理深挖）Late chunking 和 contextual retrieval 都想解决"chunk 丢失全文上下文"的问题，它们的机制、成本和前提条件有什么不同？

**Q15.**（工程实践）你要在三种切分策略中选一种上线，评测方案怎么设计？哪些"看起来很好"的评测结果其实不可信？

**Q16.**（追问型）很多教程默认 chunk overlap 10%–20%。讲义说 overlap 常常没用。你怎么看？什么情况下 overlap 可能有用？如何决定要不要加？

---

## 五、参考答案与解析

### Q1 — 答案：B

递归切分优先在最大的结构边界（段落）切，放不下再降级到换行、句子、空格，最后才按固定长度硬切。这样尽量保持语义完整。D 描述的是 semantic chunking。

### Q2 — 答案：B

小 child 让 embedding 更聚焦，检索更精确；大 parent 给生成模型足够上下文。讲义强调"dedupe parents"：多个 child 可能属于同一个 parent，全部返回会浪费上下文窗口。讲义还指出它"退化得很优雅"：child 切得不好时，返回的 parent 依然合理。

### Q3 — 答案：B

传统做法每个 chunk 单独编码，chunk 里的 "it"、"该条款" 不知道指什么。Late chunking 先让长上下文 embedder 看完整篇文档，再对每个 chunk 范围内的 token 向量做池化，chunk 向量因此携带了全文信息。讲义提到它适用于 BGE-M3、Jina v3 等长上下文模型，计算量更高。

### Q4 — 答案：C

contextual retrieval 的 LLM 调用发生在**建索引时**（讲义："Expensive to index"），查询时检索的是已经加好前缀的 chunk，不需要额外 LLM 调用。A、B、D 都与讲义一致。

### Q5 — 答案：B

讲义：SPLADE + Mistral-8B 在 Natural Questions 上 overlap 没有可测收益；"Overlap as cargo cult… Measure, do not assume." skill 规则："Overlap. Default 0; justify if >0"，"Refuse overlap above 20% without an ablation showing it helps."

### Q6 — 答案：B

按讲义的"按查询类型定大小"表，事实型查询用 256–512 token：chunk 要大到能装下答案和少量局部上下文，又要小到让 top-K 聚焦在答案上而不是被上下文噪声稀释。

### Q7 — 答案：C

讲义 Pitfalls："Cross-doc chunking. Never let a chunk span two documents. Always chunk per-doc, then merge." 拼接后统一切分会产生前半段属于文档 A、后半段属于文档 B 的 chunk，既污染 embedding，也让引用来源无法追溯。A 正是推荐做法。

### Q8 — 参考答案

1. `step = 4 - 2 = 2`，起点为 0、2、4、6、8：

   ```python
   ['abcd', 'cdef', 'efgh', 'ghij', 'ij']
   ```

   最后的 `'ij'` 完全包含在前一个 chunk `'ghij'` 里，是冗余的尾部碎片：它很短、信息量低，却占一个索引条目，还可能在检索时"抢位"。改进：当剩余长度不超过 overlap 时停止，或把过短的尾巴并入前一个 chunk。

2. `step = 0`，`range(0, len(text), 0)` 会直接抛 `ValueError: range() arg 3 must not be zero`；如果 overlap 大于 size，step 为负数，`range` 得到空序列，函数静默返回 `[]`——整篇文档凭空消失，这比报错更危险。显式检查把两种情况都变成清晰的错误信息。

3. 起点是 0、250、500。第二个 chunk 从第 250 个字符开始，恰好落在 "Chapter 3" 的 "C" 之后，于是以 `hapter 3.` 开头；第一个 chunk 也在 "Either party may terminate " 处被截断。fixed 切分只看字符数、不看任何边界，会把单词、句子、章节切断，"好压缩、坏连贯"（讲义原话："Good compression, bad coherence"）。

### Q9 — 参考答案

1. 第一个分隔符 `\n\n` 在文本中存在，于是按段落切成 `["Short intro.", long_para]`。处理 `long_para` 时 `candidate` 超长，代码只是把 `buf` 设为 `p`，**没有对这个超长片段继续用更细的分隔符切分**；循环结束后它被原样追加。更糟的是，函数在第一个命中的分隔符处就 `return` 了，后面的 `". "`、`" "` 永远没有机会作用于这个片段。所以 chunk 可以任意超长，`size` 只是"软上限"。

2. 参考讲义 Step 1 的写法，对超长片段递归调用，并降级到更细的分隔符：

```python
def chunk_recursive(text, size, seps=("\n\n", "\n", ". ", " ")):
    if len(text) <= size:
        return [text.strip()] if text.strip() else []
    for sep in seps:
        if sep not in text:
            continue
        parts = text.split(sep)
        chunks = []
        buf = ""
        for p in parts:
            if len(p) > size:                       # 新增：超长片段继续递归
                if buf:
                    chunks.append(buf.strip())
                    buf = ""
                chunks.extend(chunk_recursive(p, size, seps[seps.index(sep) + 1:] or (" ",)))
                continue
            candidate = buf + sep + p if buf else p
            if len(candidate) <= size:
                buf = candidate
            else:
                if buf:
                    chunks.append(buf.strip())
                buf = p
        if buf:
            chunks.append(buf.strip())
        return [c for c in chunks if c]
    return chunk_fixed(text, size)
```

修复后上例实测输出 `[12, 288, 289]`，全部不超过 300。注意子调用要传入**当前分隔符之后**的分隔符列表；当已经是最后一个分隔符（空格）时用 `(" ",)`，若片段中连空格都没有，就会落到 `chunk_fixed` 硬切（例如 `"x" * 700` 切成 `[300, 300, 100]`）。另外，`split(". ")` 会把分隔符本身吃掉，chunk 边界处的句号会丢失（上例第二个 chunk 以 `"...number one"` 结尾，没有句号），这是 `str.split` 写法的固有简化；生产实现（如 LangChain）可以选择把分隔符保留在片段中。

### Q10 — 参考答案

1. `retrieve_recall` 取 top-3。fixed 和 recursive 都恰好只有 3 个 chunk，top-3 就是**全部** chunk，只要答案在文档里，命中率必然 100%。`parent` 那一行：716 字符的合同小于 `parent_size=800`，只有 1 个 parent（整篇文档），而 `[m["parent"] for m in pc]` 是同一个 parent 字符串重复 5 次（每个 child 一份），不管怎么排都返回整篇文档——同时这也违反了讲义"parent 要去重"的要点。只有 semantic（11 个）和 sentence（7 个）两行有一定区分度。

2. 所有策略已经是 3/3 = 100%，不可能再"高 20–40 个百分点"。这句话可能来自更大规模的实验，但在本程序的输出下无法被验证，容易误导读者。

3. 改进建议（任选三条以上）：
   - **让 chunk 数远大于 k**：用多篇、更长的文档，或者把 k 调成 1（实测 recall@1：sentence 降到 2/3，其余仍为 3/3）。
   - **用 MRR / nDCG 代替二值 recall**：考察答案排第几，而不是"在不在前 k"。
   - **parent 去重**：评测 parent 策略时应先按 child 检索，再去重返回 parent，并控制返回的总 token 数，和其他策略在相同上下文预算下比较。
   - **扩大并分层查询集**：讲义建议 50 条，覆盖事实型、分析型、多跳型。
   - **记录 chunk 长度分布与索引条数**：评价策略时把成本一起报告。

### Q11 — 参考答案

1. `split_sentences` 按 `.!?` 后的空白切句，`"Chapter 3."` 和 `"Termination."` 都被当成独立的"句子"。
   - 处理 `Chapter 3.` 时：与上一句的余弦是 0（< 0.3），满足"话题变了"，但当前 chunk `"Late payments incur a five percent fee."` 只有 39 个字符，**小于 `min_chars=40`**，不允许切，于是 `Chapter 3.` 被追加到第 2 章的末尾。
   - 处理 `Termination.` 时：当前 chunk 已有 50 个字符，余弦仍为 0，满足切分条件，于是新开一个 chunk——章节标题和它的标题名被拆散了。
   
   根因：只比较**相邻两句**的相似度，且完全忽略了文档原有的段落结构；最小长度护栏在这里反而把标题推向了错误的一侧。在检索中，带着 `Chapter 3.` 的第 2 章 chunk 会被"终止"相关查询误命中的概率增加，而真正的第 3 章 chunk 却丢了章节号。

2. 思路：**结构优先**——先按段落（`\n\n`）切，再在每个段落内部做 semantic 切分，这样 chunk 永远不会跨越段落/章节边界。

```python
def chunk_semantic_by_para(text, threshold=0.3, min_chars=40):
    out = []
    for para in text.split("\n\n"):
        out.extend(chunk_semantic(para, threshold=threshold, min_chars=min_chars))
    return out
```

实测结果中第 3 章变成 `'Chapter 3. Termination. Either party may terminate this agreement with ninety days written notice.'`，标题回到了正确的位置，第 2 章 chunk 也不再带 `Chapter 3.`。其他可选方案：把形如 `Chapter N.` 的标题行与下一句预先合并；或者在 chunk 元数据中记录所属章节标题。

### Q12 — 参考回答要点

| 策略 | 做法 | 优点 | 缺点 | 适用 |
|---|---|---|---|---|
| Fixed | 每 N 字符/token 切 | 最简单、长度可控 | 切断句子/单词 | baseline |
| Recursive | `\n\n`→`\n`→`. `→空格逐级降级 | 尊重结构、实现简单 | 依赖文本格式 | 讲义的 2026 默认值 |
| Sentence | 按句或 N 句窗口 | 便宜，讲义称在约 5k token 内可与 semantic 相当 | 不感知话题 | 短文、FAQ |
| Semantic | 相邻句相似度骤降处切 | 话题连贯 | 慢；无最小长度会产生碎片 | 话题跳跃明显的长文 |
| Parent-document | child 检索、parent 返回 | 精度 + 上下文兼得 | 两层索引，需去重 | 分析型/多跳 |
| Late chunking | 全文 token 级编码后按 chunk 池化 | 保留跨 chunk 上下文 | 需长上下文 embedder，计算量大 | 交叉引用多的文档 |
| Contextual retrieval | LLM 为每个 chunk 写上下文前缀 | 讲义：检索提升 35–50% | 建索引成本高 | 合同、论文 |

- 加分点：说出讲义的"按查询类型定大小"规则和 Use It 表；强调"先用 recursive 512、无 overlap 起步，再测 recall@5"。

### Q13 — 参考回答要点

- **诊断**：
  1. chunk 过大或按页切，终止条款被分页符拆开，单个 chunk 中缺少"termination"等关键词；
  2. 条款正文里多是"本协议""任一方"这类指代，单独看一个 chunk 不知道它属于"终止"章节；
  3. 封面页包含合同名称、双方名称等高频词，在 embedding 空间中与很多查询都"有点像"；
  4. 文档可能超过 embedder 的最大输入长度被静默截断（第 22 节）。
- **方案**：
  - 解析结构：按章节/条款标题切（recursive，以标题和段落为一级分隔），每个 chunk 带上"章节路径"元数据；
  - 大小：条款型事实查询用 256–512 token；
  - 上下文：合同属于"交叉引用多"的文档，讲义推荐 late chunking 或 contextual retrieval；最简单的做法是把"第 X 章 终止"这样的标题拼进每个 chunk；
  - parent-document：child 是条款段落，parent 是整章；
  - 混合检索：加 sparse/BM25，抓住 "termination"、条款编号等关键词；
  - 评测：构造覆盖各章节的 50 条查询，看 recall@5。

### Q14 — 参考回答要点

| | Late chunking | Contextual retrieval |
|---|---|---|
| 机制 | 长上下文 embedder 对全文做 token 级编码，再按 chunk 边界池化 | LLM 为每个 chunk 写 50–100 词的上下文说明，拼在 chunk 前面再按普通方式编码 |
| 上下文来源 | 模型的注意力（隐式） | LLM 生成的文字（显式、可读、可调试） |
| 成本 | 一次长序列编码（算力高，但不需要 LLM） | 每个 chunk 一次 LLM 调用，且每次都要带上整篇文档（建索引贵） |
| 前提 | embedder 支持长上下文，文档不超过其窗口 | 有 LLM 预算；可配合 prompt caching 降低重复输入整篇文档的成本 |
| 收益 | 保留跨 chunk 的指代与主题信息 | 讲义：Anthropic 基准中检索提升 35–50% |

- 共同点：都只影响**建索引**阶段，查询时没有额外开销。
- 加分点：能指出 contextual retrieval 的产出是文本，所以它也能同时增强 BM25 等 sparse 检索；late chunking 只改善 dense 向量。

### Q15 — 参考回答要点

- **评测集**：至少 50 条真实或模拟查询，按事实型/分析型/多跳型分层（讲义：只用事实型评测会选错策略），每条标注金标准答案位置。
- **指标**：recall@5（讲义建议的主指标）、MRR/nDCG（关注排名）、端到端答案正确率；同时报告 chunk 数、平均/最大 chunk 长度、索引大小、建索引成本。
- **公平比较**：相同 embedder、相同 top-k、相同上下文 token 预算（parent 策略返回的上下文更长，不能直接比 recall）。
- **不可信的结果**：
  - chunk 总数 ≤ k 时 recall 必然 100%（`main.py` 就是例子）；
  - parent 没去重，或返回的上下文远大于其他策略；
  - 查询是根据 chunk 内容反向生成的，天然偏向该切分方式；
  - 只在一两篇文档、几条查询上测，方差极大。
- 结论原则（讲义）："Always benchmark. The 'best' strategy for your corpus may not match any blog post."

### Q16 — 参考回答要点

- **为什么流行**：直觉上 overlap 是"安全边际"，防止答案恰好被切在两个 chunk 的边界上。
- **为什么常常无用**：讲义引用的 2026 研究（SPLADE + Mistral-8B，Natural Questions）中 overlap 没有可测收益；而它的成本是确定的——overlap 比例为 r 时，chunk 数约为无 overlap 时的 `1/(1−r)` 倍（50% overlap 即翻倍），索引、embedding 计算和存储都随之增加，重复内容还可能让 top-k 被同一段文字的多个副本占满。
- **可能有用的情况**：使用 fixed 切分（经常切断句子）；答案天然跨越段落边界的长推理文本；没有 parent-document 等其他补救上下文的手段时。
- **怎么决定**：默认 0；在分层评测集上做消融（0% / 10% / 20%），只有在 recall@5 或端到端正确率上有显著收益时才加；讲义 skill 规则："Refuse overlap above 20% without an ablation showing it helps."
- 加分点：指出 parent-document、late chunking、contextual retrieval 都是比 overlap 更"有针对性"的补充上下文手段。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 14 信息检索与搜索](../../14-information-retrieval-search/docs/zh.md)：召回、排序与 recall@k 等评估指标。
- [阶段 05 · 22 Embedding 模型深度剖析](../../22-embedding-models-deep-dive/docs/zh.md)：模型最大输入长度、dense/sparse 检索与 RRF。

### 本节被哪些后续内容用到
- [阶段 05 · 24 共指消解](../../24-coreference-resolution/docs/zh.md)：chunk 中的代词在切分后失去先行词，是 contextual retrieval 要解决的问题之一。
- [阶段 05 · 28 长上下文评测](../../28-long-context-evaluation/docs/zh.md)：与讲义中的"上下文悬崖"现象相关。
- [阶段 11 · 06 RAG](../../../11-llm-engineering/06-rag/docs/zh.md) 与 [阶段 11 · 07 高级 RAG](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：chunking 在完整 RAG 流水线中的位置。
- [阶段 11 · 05 上下文工程](../../../11-llm-engineering/05-context-engineering/docs/zh.md)：如何在有限上下文预算中组织检索结果。
- [阶段 19 · 64 高级 Chunking 策略](../../../19-capstone-projects/64-chunking-strategies-advanced/docs/zh.md)：本节内容的项目级实现。
- [阶段 19 · 68 RAG 评估](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md) 与 [阶段 19 · 69 端到端 RAG 系统](../../../19-capstone-projects/69-end-to-end-rag-system/docs/zh.md)：评测与整体集成。

### 延伸关键词
`RecursiveCharacterTextSplitter` · `semantic chunking` · `parent-document retriever` · `late chunking` · `contextual retrieval` · `chunk overlap` · `min/max tokens` · `recall@5 / MRR` · `context cliff` · `structure-aware chunking` · `metadata (section path)`
