# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 13 节 问答系统 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`re`、`collections.Counter`），无需 transformers / 网络

---

## 1. 这份代码在考察什么

讲义里的抽取式 reader（RoBERTa-SQuAD）和 dense retriever 都需要下载模型，这份代码则把 QA 系统里**不依赖模型、但每个工程师都必须亲手写对的部分**单独拿出来：

1. **SQuAD 评测指标**：`normalize` → `exact_match` → `token_f1`，理解"归一化后完全相等"和"按 token 重叠给部分分"的区别。
2. **指标的盲区**：用 5 个精心挑选的预测（同义改写、词序变化、只答年份、答错年份）展示 EM 与 F1 都**不理解语义**。
3. **检索 → 拒答的骨架**：一个极简的词面检索 `toy_retrieve`，加上"最高检索分低于阈值就拒答"的 `refusal_from_score`，对应讲义"生产评估"里的检索召回和拒答校准。
4. **（意外收获）检索失败案例**：demo 问题的 top-1 竟然是 iPod 段落——这恰好说明没有 IDF / 停用词的词面打分有多脆弱，为第 14 节的 BM25 做铺垫。

> 一句话：**先学会怎么给 QA 打分、怎么判断该不该回答，再去接模型**——评估和拒答写错了，换再好的模型也看不出效果。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tokenize(text)` | 函数 | 小写后用正则抽出 `[a-z0-9]+` 片段 | 分词 |
| `normalize(text)` | 函数 | 小写、去冠词、去标点、合并空白 | SQuAD 答案归一化 |
| `exact_match(pred, gold)` | 函数 | 归一化后完全相等得 1，否则 0 | EM 指标 |
| `token_f1(pred, gold)` | 函数 | 基于多重集合 token 重叠的 F1 | token-level F1 |
| `refusal_from_score(score, threshold)` | 函数 | 最高检索分 < 阈值则拒答 | 拒答校准（refusal calibration） |
| `CORPUS` | 常量 | 4 句与 iPhone / iPod / Android 有关的"文档" | 检索语料 |
| `toy_bm25_score(query, doc)` | 函数 | 词频 / 长度惩罚的简化词面打分 | 稀疏检索（简化版 BM25） |
| `toy_retrieve(question, top_k)` | 函数 | 给所有文档打分并取 top-k | retriever |
| `main()` | 函数 | 两段演示：指标对比、检索 + 拒答 | — |

数据流：`main` 第一段只用 `exact_match`/`token_f1`（二者都先经过 `normalize`，F1 再经过 `tokenize`）；第二段 `toy_retrieve → toy_bm25_score → tokenize`，拿到 top-1 分数后交给 `refusal_from_score`。

---

## 3. 逐段精讲

### 3.1 `tokenize`：最朴素的英文分词

```python
def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())
```

- 先 `lower()` 再找所有"连续的小写字母或数字"。标点、空格、撇号都被当作分隔符：`"Google's"` → `["google", "s"]`。
- `re.findall` 返回**所有**匹配子串组成的列表，是一行写分词的常用技巧。
- ⚠️ 只认 ASCII：`"café"` 会被切成 `["caf"]`，中文会被整个丢掉。这对英文 SQuAD 够用，多语言场景必须换（见第 18 节）。

### 3.2 `normalize`：SQuAD 风格的答案归一化

```python
def normalize(text):
    text = text.lower()
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())
```

四步对应讲义里 EM 的定义"lowercase, strip punctuation, remove articles"：

| 步骤 | 代码 | 例子 `"The iPhone's launch!"` |
|------|------|------------------------------|
| 小写 | `text.lower()` | `the iphone's launch!` |
| 去冠词 | `\b(a\|an\|the)\b` → 空格 | ` iphone's launch!` |
| 去标点 | `[^\w\s]` → 空格 | ` iphone s launch ` |
| 合并空白 | `" ".join(text.split())` | `iphone s launch` |

- `\b` 是**单词边界**，保证只删独立的 `a/an/the`，不会把 `there` 里的 `the` 删掉。
- `[^\w\s]` 表示"既不是单词字符也不是空白"的字符，即标点。
- `" ".join(text.split())`：`split()` 不带参数会按任意空白切分并丢弃空串，再用单个空格拼回——这是合并多余空白的惯用法。
- ⚠️ 与 SQuAD 官方脚本的细微差别：官方是**先去标点（直接删除）再去冠词**，这里是先去冠词、再把标点**替换成空格**。因此 `"a.m."` 在这里会变成 `"m"`（`a` 被当冠词删了），官方脚本会得到 `"am"`。教学足够，但要和官方榜单对齐时必须用官方实现。

### 3.3 `exact_match` 与 `token_f1`

```python
def exact_match(pred, gold):
    return 1.0 if normalize(pred) == normalize(gold) else 0.0


def token_f1(pred, gold):
    p_tokens = tokenize(normalize(pred))
    g_tokens = tokenize(normalize(gold))
    if not p_tokens or not g_tokens:
        return 0.0 if (p_tokens or g_tokens) else 1.0
    common = Counter(p_tokens) & Counter(g_tokens)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(p_tokens)
    recall = overlap / len(g_tokens)
    return 2 * precision * recall / (precision + recall)
```

- **EM** 只有 0 和 1 两个值，返回 `float` 是为了方便后面求平均。
- **F1** 的核心是 `Counter(p) & Counter(g)`：两个计数器做 `&`，结果是每个 key 取**较小计数**的多重集合交集。例如预测 `[june, june, 2007]`、参考 `[june, 29, 2007]`，交集是 `{june:1, 2007:1}`，重叠为 2。这保证重复词不会被重复计分。
- 空串处理：`0.0 if (p_tokens or g_tokens) else 1.0` 的意思是"一边空一边不空 → 0；两边都空 → 1"。两边都空对应 SQuAD 2.0 里"无答案问题预测了无答案"，应当算对。
- `if overlap == 0: return 0.0` 不只是提前返回，也**避免了 `precision + recall = 0` 时的除零**。
- F1 = `2PR/(P+R)` 是精确率和召回率的调和平均：预测太长（多余词多）会拉低 P，预测太短（漏词）会拉低 R。
- ⚠️ 两者都是**纯字面**指标：同义词、日期格式、数字写法（"two" vs "2"）都无法识别。

### 3.4 `refusal_from_score`：最简单的拒答闸门

```python
def refusal_from_score(top_retrieval_score, threshold=0.3):
    return top_retrieval_score < threshold
```

- 思路来自讲义练习 2："top 检索分数低于阈值（比如余弦 0.3）就返回 I don't know，不调用 reader"。好处是**省一次 reader 调用**，并且从源头上避免"在无关段落上硬答"。
- ⚠️ 0.3 是为**余弦相似度**（范围 [-1, 1]）设计的阈值，而这里喂给它的是 `toy_bm25_score` 的分数（没有上界、随长度变化），量纲不匹配。demo 里 top score 是 2.353，远超 0.3，所以永远不会拒答。实际系统中阈值必须在**同一种分数**上、用留出集来调。

### 3.5 `toy_bm25_score`：一个"像 BM25 但缺了关键部件"的打分函数

```python
def toy_bm25_score(query, doc):
    q_tokens = set(tokenize(query))
    d_tokens = tokenize(doc)
    d_counts = Counter(d_tokens)
    score = 0.0
    for qt in q_tokens:
        if qt in d_counts:
            score += d_counts[qt] / (1 + len(d_tokens) / 10)
    return score
```

- 查询词用 `set` 去重，每个查询词只算一次；文档词用 `Counter` 统计词频 tf。
- 每命中一个查询词，加 `tf / (1 + 文档长度/10)`：分母是一个粗糙的**长度惩罚**，越长的文档每个命中越不值钱。
- 和真正的 BM25（第 14 节）相比，缺了三样东西：
  - ⚠️ **没有 IDF**：`the`、`was` 和 `iphone` 的权重一样；
  - ⚠️ **没有 tf 饱和**（`k1`）：词频线性增长，一个词重复 10 次就加 10 倍；
  - ⚠️ **长度惩罚没有相对于平均文档长度**（`b`、`avgdl`），而是写死的 `/10`。
- 名字里的 "toy" 是认真的：它只用来演示"检索 → 取 top 分数 → 拒答"的流程。

### 3.6 `toy_retrieve`：打分、排序、截断

```python
def toy_retrieve(question, top_k=2):
    scored = [(toy_bm25_score(question, d), d) for d in CORPUS]
    scored.sort(reverse=True)
    return scored[:top_k]
```

- 把 `(分数, 文档)` 做成元组列表，`sort(reverse=True)` 会**先按分数降序**，分数相同时再按文档字符串降序比较——这是元组的字典序比较规则。
- 对 4 篇文档全量打分是 O(N) 的暴力检索；真实系统用倒排索引（BM25）或 ANN 索引（dense）避免全量扫描。
- 返回的仍是 `(score, doc)` 元组，`main` 里用 `results[0][0]` 取 top-1 的分数。

### 3.7 `main`：两段演示

```python
    cases = [
        ("June 29, 2007", "June 29, 2007"),
        ("June 29th, 2007", "June 29, 2007"),
        ("29 June 2007", "June 29, 2007"),
        ("2007", "June 29, 2007"),
        ("2008", "June 29, 2007"),
    ]
    for pred, gold in cases:
        em = exact_match(pred, gold)
        f1 = token_f1(pred, gold)
        print(f"  pred={pred!r:20s} gold={gold!r:20s} EM={em:.0f}  F1={f1:.2f}")
```

五个用例分别覆盖：完全正确、序数词改写、词序改写、答案不完整、答错。打印格式里 `{pred!r:20s}` 先用 `repr()` 给字符串加引号，再左对齐填充到 20 个字符宽，便于对齐成表格。

第二段对 demo 问题检索 top-2，并把 top-1 分数交给 `refusal_from_score`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不加载任何模型 | 秒级运行、零依赖，专注于指标和流程 | 生产中 reader 用 `deepset/roberta-base-squad2` 或 LLM，retriever 用 BM25 / dense / 混合 |
| 手写 `normalize` | 让你看清 EM 的"严格"来自哪几步 | 对齐官方榜单要用 SQuAD 官方脚本（顺序和标点处理略有不同） |
| `Counter &` 计算重叠 | 正确处理重复 token | — |
| 词面玩具检索 | 无需 embedding 即可演示检索 + 拒答 | 没有 IDF / 饱和 / 平均长度，排序不可靠；生产用 BM25（第 14 节） |
| 固定阈值 0.3 拒答 | 演示"检索分低就别答"的思路 | 阈值要与分数量纲匹配、在留出集上调，常与 reranker 分数或 reader 置信度组合使用 |
| 单参考答案 | 代码简洁 | SQuAD 有多个参考答案，应对每个参考打分取 max |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 函数默认参数 | `def refusal_from_score(top_retrieval_score, threshold=0.3)` | 调用时不传就用默认值 |
| 条件表达式 | `1.0 if ... else 0.0` | 一行版 if/else，返回其中一个值 |
| 真值判断 | `if not p_tokens or not g_tokens` | 空列表在布尔上下文中为 `False` |
| `re.findall` | `re.findall(r"[a-z0-9]+", text.lower())` | 返回所有匹配的子串列表；`r"..."` 是原始字符串，反斜杠不转义 |
| `re.sub` 与 `\b` | `re.sub(r"\b(a\|an\|the)\b", " ", text)` | 正则替换；`\b` 匹配单词边界，`(a\|an\|the)` 是分组 + 或 |
| 字符类取反 | `[^\w\s]` | 匹配"非单词字符且非空白"，即标点 |
| `str.split` + `join` | `" ".join(text.split())` | 合并连续空白的惯用法 |
| `collections.Counter` | `Counter(p_tokens) & Counter(g_tokens)` | 计数器；`&` 取每个 key 的最小计数（多重集合交集） |
| `dict.values()` + `sum` | `sum(common.values())` | 对所有计数求和 |
| `in` 判断字典键 | `if qt in d_counts` | O(1) 查询键是否存在 |
| 列表推导式 + 元组 | `[(toy_bm25_score(question, d), d) for d in CORPUS]` | 生成 `(分数, 文档)` 列表 |
| 元组排序 | `scored.sort(reverse=True)` | 元组按字典序比较：先比第 0 项，相同再比第 1 项 |
| 元组解包 | `for pred, gold in cases`、`for s, d in results` | 一次取出元组的多个元素 |
| 切片 | `scored[:top_k]` | 取前 k 个 |
| f-string 格式符 | `{pred!r:20s}`、`{em:.0f}`、`{f1:.2f}` | `!r` 用 `repr()`；`:20s` 宽度 20 左对齐；`.2f` 两位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13）输出：

```text
=== extractive metrics ===
  pred='June 29, 2007'      gold='June 29, 2007'      EM=1  F1=1.00
  pred='June 29th, 2007'    gold='June 29, 2007'      EM=0  F1=0.67
  pred='29 June 2007'       gold='June 29, 2007'      EM=0  F1=1.00
  pred='2007'               gold='June 29, 2007'      EM=0  F1=0.50
  pred='2008'               gold='June 29, 2007'      EM=0  F1=0.00

note: EM punishes paraphrase. F1 is partial credit. neither captures semantics.

=== toy retrieval ===
  query: When was the first iPhone released?
  top score: 2.353  refuse: False
    2.353  The first iPod was released in 2001.
    2.000  Apple Inc. released the first iPhone on June 29, 2007.
```

逐行解读：

- **第 1 行**：完全一致，EM=1、F1=1。
- **第 2 行** `June 29th`：`29th ≠ 29`，EM=0；token 为 `[june, 29th, 2007]` vs `[june, 29, 2007]`，重叠 2，P=R=2/3，F1=0.67。正是讲义说的"序数词破坏归一化，但 F1 仍给可观的部分分"。
- **第 3 行** `29 June 2007`：EM=0，但 F1=**1.00**——三个 token 完全重叠，F1 不看词序。说明 F1 对"词序不同但含义可能不同"的情况也会给满分。
- **第 4 行** `2007`：P=1/1、R=1/3，F1=0.5。只答对一部分。
- **第 5 行** `2008`：零重叠，F1=0。
- **检索部分**：⚠️ top-1 是 **iPod** 段落（2.353），正确的 iPhone 段落（2.000）排第二。原因：两段都命中 4 个查询词，但 iPod 段落命中的是 `the / first / was / released`，iPhone 段落命中 `released / the / first / iphone`；没有 IDF 时 `was` 和 `iphone` 等价，而 iPod 段落更短（7 个 token，惩罚 1.7；iPhone 段落 10 个 token，惩罚 2.0），于是错误段落胜出。
- `refuse: False`：2.353 ≥ 0.3，不拒答——系统会**自信地拿错误段落去回答**。如果 top_k=1，reader 只能看到 iPod 段落，抽取式模型很可能抽出 "2001" 这样的错误答案。这正是讲义强调"先测检索召回"的原因。好在 top_k=2 时正确段落仍在上下文中。

---

## 7. 动手改一改

1. **多参考答案**：写 `squad_score(pred, golds)`，对每个参考答案分别算 EM / F1 并取 max。
2. **修复检索**：给 `toy_bm25_score` 加停用词过滤（`when / was / the ...`），让 iPhone 段落排第一。再试试"只加 IDF、不去停用词"——你会发现在 4 篇文档的小语料上 `was` 的 IDF 反而最高，排序仍然是错的。
3. **对齐官方归一化**：把 `normalize` 改成"先删除标点（不替换为空格）、再去冠词"，对比 `"a.m."`、`"U.S."` 的结果。
4. **改进拒答**：把分数除以"查询所有词都命中时的满分"做归一化，再加一个"top-1 与 top-2 的分差太小就拒答"的条件；构造一个语料里根本没有答案的问题（如 "Who founded Microsoft?"）测试。
5. **接上真 reader**：如果本地有 `transformers` 和模型缓存，把 `toy_retrieve` 的 top-2 段落拼起来交给 `pipeline("question-answering", model="deepset/roberta-base-squad2")`，再用本文件的 `exact_match/token_f1` 打分。
6. **语义评估**：为 `"June 29th, 2007"` 这类改写写一个日期归一化器（解析成 `YYYY-MM-DD` 再比较），体会"指标领域定制"的思路。

---

## 8. 常见坑

- **忘了归一化就比较**：`"The iPhone"` 与 `"iphone"` 直接比较必然不等；EM 必须在归一化之后算。
- **用 set 或 `in` 计算重叠**：`set` 在两边都有重复词时少算，`sum(t in gold for t in pred)` 会把预测里的重复词重复计分，都会让 F1 失真；用 `Counter &`。
- **阈值量纲不匹配**：余弦阈值不能直接套在 BM25 类分数上；分数换了，阈值就要重新调。
- **把 top-1 当成一定正确**：本 demo 就是反例。评估 reader 之前先测检索召回。
- **ASCII 正则吃掉非英文字符**：`[a-z0-9]+` 会把 `é`、中文全部丢掉，多语言 QA 要换成 Unicode 感知的分词。
- **F1 不看词序**：`"29 June 2007"` 得满分，但 `"dog bites man"` 和 `"man bites dog"` 也会得满分——字面指标永远需要语义评估兜底。
