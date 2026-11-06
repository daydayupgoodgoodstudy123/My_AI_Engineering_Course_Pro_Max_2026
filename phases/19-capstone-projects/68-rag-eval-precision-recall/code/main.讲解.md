# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 68 节 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（测试：`python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`） ｜ **依赖**：纯标准库（`math`、`re`、`collections`、`dataclasses`、`typing`），无需网络、无需 LLM。

---

## 1. 这份代码在考察什么

这份代码实现了一个最小但完整的 **RAG 离线评估框架**：

1. **四个检索指标**：precision@k、recall@k、MRR、nDCG@k（支持分级相关度）。
2. **两个答案指标**：faithfulness（答案的每个 claim 是否被检索上下文支持）和 answer relevance（答案是否回应问题），用一个基于 token 重叠的 `MockJudge` 代替 LLM-as-judge。
3. **qrels 数据结构**：每条包含 query、gold 文档 id、参考答案片段、分级相关度。
4. **统一的 pipeline 接口**：`(query, k) -> (doc_ids, answer)`，任何检索 + 生成方案都能接入。
5. **三个对比变体**：词袋 baseline、同义词扩展的 "hybrid"、再加标题加权的 "hybrid+rerank"，输出一张指标表。

> 一句话：**把"一个 RAG 系统好不好"拆成可计算、可对比、可回归测试的数字**。同时要看清这张表在本 fixture 上的局限：faithfulness 结构性饱和、rerank 与 hybrid 完全相同、qrels 二值与分级标注不一致——评估本身也需要被评估。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Qrel` | dataclass | qid、query、gold_doc_ids、gold_answer_substring、graded_relevance | 标注集 |
| `precision_at_k` / `recall_at_k` | 函数 | 集合型检索指标 | P@k、R@k |
| `reciprocal_rank` / `mean_reciprocal_rank` | 函数 | 第一个命中名次的倒数及其均值 | MRR |
| `dcg_at_k` / `ndcg_at_k` | 函数 | 指数增益 + 对数折扣，除以理想 DCG | nDCG |
| `extract_claims` | 函数 | 按句末标点切句，每句当作一个 claim | claim 抽取 |
| `_content_tokens` | 函数 | 小写分词、去停用词、去单字符 | 内容词 |
| `MockJudge` | dataclass | `supported(claim, context)`、`relevant(question, answer)`，阈值 0.4 | LLM-as-judge 替身 |
| `faithfulness` / `answer_relevance` | 函数 | 支持比例；0/1 相关性 | 答案指标 |
| `Doc` / `CORPUS` | dataclass / 常量 | 12 篇文档（含 4 篇"干扰文档" d9–d12） | fixture 语料 |
| `QRELS` | 常量 | 4 条 qrels | fixture 标注 |
| `PipelineFn` | 类型别名 | `Callable[[str, int], tuple[list[str], str]]` | pipeline 接口 |
| `_bow` / `_score_doc` | 函数 | 词袋点积打分（**未被使用**） | — |
| `_BASELINE_STOP` / `_baseline_tokens` | 常量 / 函数 | baseline 与 hybrid 共用的停用词过滤 | 预处理 |
| `baseline_pipeline` | 函数 | 内容词计数重叠，答案 = top-1 正文 | 词法基线 |
| `_SYN` / `hybrid_pipeline` | 常量 / 函数 | 同义词扩展 + 截断计数重叠 + 标题奖励，答案 = top-2 正文拼接 | "hybrid"替身 |
| `hybrid_plus_rerank_pipeline` | 函数 | 取 hybrid 的 2k 个结果，按标题命中 ×5 重排 | "rerank"替身 |
| `evaluate_pipeline` | 函数 | 对每条 qrel 运行 pipeline，计算全部指标并取平均 | 评估编排 |
| `_fmt` / `main` | 函数 | 打印三列指标表 | demo |

数据流：`main` → 对每个 pipeline 调 `evaluate_pipeline(fn, QRELS, ks=(1,3,5))` → 每条 qrel：`fn(query, 5)` 得到 `(retrieved, answer)` → 逐个 k 算 P/R/nDCG → 全部 qrel 跑完后算 MRR → 用检索到的文档正文作上下文算 faithfulness 与 relevance → 返回平均值字典 → 打印表格。

---

## 3. 逐段精讲

### 3.1 `Qrel`：标注记录

```python
@dataclass
class Qrel:
    qid: str
    query: str
    gold_doc_ids: list[str]
    gold_answer_substring: str
    graded_relevance: dict[str, int] = field(default_factory=dict)
```

- `gold_doc_ids` 给 precision/recall/MRR 用（二值），`graded_relevance` 给 nDCG 用（分级）。
- `gold_answer_substring` 只是参考元数据：讲义说明 faithfulness "is computed by judging extracted claims against the retrieved context, not against this substring"。代码中确实没有任何地方用到它。
- ⚠️ 本节 4 条 qrels 中，每条的 `graded_relevance` 都包含一个**不在** `gold_doc_ids` 里的文档（q1:d2、q2:d5、q3:d8、q4:d2），二值指标和 nDCG 的"相关"口径不一致（测验 Q12）。

### 3.2 precision@k 与 recall@k

```python
def precision_at_k(retrieved: list[str], gold: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = retrieved[:k]
    if not top:
        return 0.0
    return sum(1 for r in top if r in gold) / k


def recall_at_k(retrieved: list[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    top = set(retrieved[:k])
    return len(top & gold) / len(gold)
```

- precision 的分母是 **k**，不是实际返回的个数：返回 1 个且命中时 precision@5 = 0.2。这是 IR 的标准定义，惩罚"返回太少"。（第 69 节的 `doc_level_precision` 改成了除以实际个数，两节口径不同。）
- `sum(1 for r in top if r in gold)` 是生成器表达式计数；`r in gold` 对 set 是 O(1)。
- recall 用集合交集，`retrieved` 中的重复 id 不会被重复计数。
- 边界：k ≤ 0 或没有返回结果时 precision 为 0；gold 为空时 recall 定义为 0（也有实现定义为 1 或跳过该 query，需要在报告中写明）。

### 3.3 MRR

```python
def reciprocal_rank(retrieved: list[str], gold: set[str]) -> float:
    for i, doc_id in enumerate(retrieved):
        if doc_id in gold:
            return 1.0 / (i + 1)
    return 0.0


def mean_reciprocal_rank(retrieved_per_query, gold_per_query) -> float:
    if len(retrieved_per_query) != len(gold_per_query):
        raise ValueError(...)
    if not retrieved_per_query:
        return 0.0
    return sum(reciprocal_rank(r, g) for r, g in zip(retrieved_per_query, gold_per_query)) / len(retrieved_per_query)
```

- 找到第一个命中就立即返回 `1/名次`；都没命中返回 0，但这个 query **仍计入分母**。
- 长度不一致时主动抛 `ValueError`，防止 `zip` 静默截断导致的错误平均——这是一个很好的防御式写法。
- MRR 不看 k：它扫描整个返回列表。本节 pipeline 最多返回 5 个，所以实际上是 MRR@5。

### 3.4 nDCG

```python
def dcg_at_k(retrieved: list[str], graded: dict[str, int], k: int) -> float:
    s = 0.0
    for i, doc_id in enumerate(retrieved[:k]):
        rel = graded.get(doc_id, 0)
        if rel <= 0:
            continue
        s += ((2 ** rel) - 1) / math.log2(i + 2)
    return s


def ndcg_at_k(retrieved: list[str], graded: dict[str, int], k: int) -> float:
    dcg = dcg_at_k(retrieved, graded, k)
    ideal_order = sorted(graded.items(), key=lambda x: -x[1])
    ideal = [doc_id for doc_id, _ in ideal_order]
    idcg = dcg_at_k(ideal, graded, k)
    if idcg == 0:
        return 0.0
    return dcg / idcg
```

- **增益** `2^rel − 1`：rel = 3 → 7，rel = 2 → 3，rel = 1 → 1。指数增益让高度相关的文档在分数中占主导。
- **折扣** `log2(i + 2)`：第 1 位（i = 0）为 1，第 2 位 1.585，第 3 位 2。
- **IDCG** 用 qrels 中**全部**分级文档按相关度降序排出的"理想列表"计算，并同样截断到 k。这是正确做法：没被检索到的相关文档会拉低 nDCG。
- 例：q1 的 baseline 结果 `[d3, d9, d1]`，DCG@3 = `7 + 0 + 3/2 = 8.5`；理想 `[d3, d1, d2]`，IDCG@3 = `7 + 3/1.585 + 1/2 = 9.393`；nDCG@3 ≈ 0.905。
- 未标注的文档默认相关度 0（`graded.get(doc_id, 0)`）。

### 3.5 claim 抽取与 Mock 评审

```python
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def extract_claims(answer: str) -> list[str]:
    parts = _SENTENCE_BOUNDARY.split(answer.strip())
    return [p.strip() for p in parts if p.strip()]
```

- `(?<=[.!?])\s+` 是**后行断言**：只在"句号/感叹号/问号之后的空白"处切分，标点本身保留在前一句里。`"k = 60."` 和 `"Version 2.5 is used."` 这样的小数不会被错切（实测），因为小数点后没有空白。
- 一句话当一个 claim，是对"原子 claim 抽取"的粗略近似；真实系统常用 LLM 把复合句拆成多个原子事实。

```python
def _content_tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "is", ... "who", "why", "how"}
    return {t for t in _TOK.findall(text.lower()) if t not in stop and len(t) > 1}


@dataclass
class MockJudge:
    overlap_threshold: float = 0.4

    def supported(self, claim: str, context: str) -> bool:
        c_tokens = _content_tokens(claim)
        if not c_tokens:
            return False
        ctx_tokens = _content_tokens(context)
        if not ctx_tokens:
            return False
        overlap = len(c_tokens & ctx_tokens) / len(c_tokens)
        return overlap >= self.overlap_threshold

    def relevant(self, question: str, answer: str) -> bool:
        q_tokens = _content_tokens(question)
        a_tokens = _content_tokens(answer)
        if not q_tokens:
            return False
        overlap = len(q_tokens & a_tokens) / len(q_tokens)
        return overlap >= self.overlap_threshold
```

- `supported`：claim 的内容词中有多少比例出现在上下文里（分母是 **claim**）。
- `relevant`：问题的内容词中有多少比例出现在答案里（分母是 **问题**）。
- 停用词集合在函数内部定义，每次调用都重建一次 set（小开销，可以提到模块级）。
- ⚠️ token 重叠评审器的盲区：
  - 数字/实体替换："The abort threshold is five failed parts." 对 d3 的重叠是 4/5，判为支持（实测）；
  - 否定："Past that threshold the upload is not aborted." 判为支持（实测 1.0）；
  - 同义改写：真正忠实但换了说法的 claim 可能被判为不支持。

```python
def faithfulness(claims: list[str], context_texts: list[str], judge: MockJudge) -> float:
    if not claims:
        return 0.0
    context_blob = " ".join(context_texts)
    supported = sum(1 for c in claims if judge.supported(c, context_blob))
    return supported / len(claims)


def answer_relevance(question: str, answer: str, judge: MockJudge) -> float:
    return 1.0 if judge.relevant(question, answer) else 0.0
```

- 所有检索到的文档拼成一个大上下文；空答案的 faithfulness 定义为 0（也可以定义为"无可证伪的内容 = 1"，第 69 节对拒答就是这样处理的）。
- answer relevance 是 0/1 二值，再对 query 求平均。

### 3.6 fixture：语料与 qrels

- 12 篇文档中，d1–d8 是"真实"文档，**d9–d12 是刻意设计的干扰文档**：
  - d9 "Drop policy for stale records"：含 dropped、upload、abort、threshold，专门干扰 q1；
  - d10 "Worker pool sizing"：含 worker、long-running，干扰 q4；
  - d11 "Permission inheritance"：含 "central permission gate"，与 q2 的措辞完全一样，干扰 q2；
  - d12 "Combining query results"：含 production、engines、rank fusion，干扰 q3。
- 这种"词汇高度重叠但不回答问题"的困难负例，正是检验排序质量的好设计。

### 3.7 三个 pipeline 变体

```python
def baseline_pipeline(query: str, k: int) -> tuple[list[str], str]:
    q_tokens = _baseline_tokens(query)
    scored = []
    for d in CORPUS:
        d_tokens = _baseline_tokens(d.text())
        d_counter = Counter(d_tokens)
        score = sum(d_counter[t] for t in q_tokens)
        scored.append((d, score))
    scored.sort(key=lambda x: -x[1])
    top = [d for d, s in scored if s > 0][:k]
    answer = top[0].body if top else "I do not know."
    return [d.doc_id for d in top], answer
```

- 分数 = 每个查询内容词在文档中出现的次数之和（标题 + 正文）。q1 的内容词是 `threshold, multipart, upload, dropped`：d3 得 4 分，d9 得 3 分，d1 得 2 分，其余 0 分。
- 只保留分数 > 0 的文档，所以返回数可能少于 k。
- **答案 = top-1 文档的正文**：一个纯抽取式"生成器"。

```python
def hybrid_pipeline(query: str, k: int) -> tuple[list[str], str]:
    q_tokens = _baseline_tokens(query)
    expanded = list(q_tokens)
    for t in list(q_tokens):
        expanded.extend(_SYN.get(t, []))
    expanded_counter = Counter(expanded)
    scored = []
    for d in CORPUS:
        d_counter = Counter(_baseline_tokens(d.text()))
        score = sum(min(expanded_counter[t], d_counter[t]) for t in set(expanded_counter) | set(d_counter))
        title_tokens = set(_baseline_tokens(d.title))
        score += 2 * len(set(expanded) & title_tokens)
        scored.append((d, score))
    ...
    answer_parts = [d.body for d in top[:2]]
    return [d.doc_id for d in top], " ".join(answer_parts) if answer_parts else "I do not know."
```

- **同义词扩展**：`dropped → aborted`、`central → centralized`、`gate → check`、`stop → cancel, cancellation`、`fuse → combine, fusion` 等，弥补 query 与语料的用词差异（第 67 节的思路）。
- **`min` 计数重叠**：`Σ min(q_count, d_count)` 相当于两个多重集的交集大小，同一个词在文档里重复多次不会无限加分。遍历 `set(expanded_counter) | set(d_counter)` 时，只在一侧出现的词 min 为 0，等价于只遍历交集。
- **标题奖励** `+2 × 命中数`。
- 名字叫 "hybrid"，但其实**没有稠密检索**，只是"词法 + 同义词 + 标题加权"；docstring 说它是第 65 节检索器的 "stand-in"。
- 答案 = top-2 正文拼接。

```python
def hybrid_plus_rerank_pipeline(query: str, k: int) -> tuple[list[str], str]:
    ids, _ = hybrid_pipeline(query, k * 2)
    by_id = {d.doc_id: d for d in CORPUS}
    q_tokens = set(_baseline_tokens(query))
    for syn_list in _SYN.values():
        for s in syn_list:
            if s in {t for t in _SYN if any(s in v for v in _SYN.values())}:
                continue

    def title_boost(doc_id: str) -> int:
        ...
        return len(expanded & title_tokens) * 5

    ranked = sorted(ids, key=lambda did: -title_boost(did))
    top = ranked[:k]
```

- 先从 hybrid 取 2k 个候选，再按"标题命中扩展词的个数 × 5"重排。`sorted` 是稳定排序，title_boost 相同的保留 hybrid 原顺序。
- ⚠️ 中间的双层 `for` 循环**什么也不做**：循环体只有 `if ...: continue`，没有任何副作用，是遗留的死代码。
- ⚠️ title_boost 使用的信号与 hybrid 里的标题奖励**完全相同**（同样的扩展词、同样的标题），只是系数从 2 变成 5，所以不会改变任何文档的相对顺序。实测 4 个 query 的结果与 hybrid 完全一致，12 项指标逐项相等。讲义说 "the rerank row beats hybrid on MRR"，在本代码中不成立。
- 嵌套函数 `title_boost` 通过闭包读取外层的 `q_tokens` 与 `by_id`。

### 3.8 评估编排

```python
def evaluate_pipeline(pipeline, qrels, ks=(1, 3, 5), judge=None):
    judge = judge or MockJudge()
    ...
    for qrel in qrels:
        retrieved, answer = pipeline(qrel.query, max(ks))
        ...
        for k in ks:
            metrics[f"precision@{k}"].append(precision_at_k(retrieved, set(qrel.gold_doc_ids), k))
            metrics[f"recall@{k}"].append(recall_at_k(retrieved, set(qrel.gold_doc_ids), k))
            metrics[f"ndcg@{k}"].append(ndcg_at_k(retrieved, qrel.graded_relevance, k))

    mrr = mean_reciprocal_rank(per_q_retrieved, per_q_gold)

    by_id = {d.doc_id: d for d in CORPUS}
    for question, answer, retrieved in per_q_answers:
        context_texts = [by_id[did].text() for did in retrieved if did in by_id]
        claims = extract_claims(answer)
        faith_scores.append(faithfulness(claims, context_texts, judge))
        rel_scores.append(answer_relevance(question, answer, judge))

    return {
        "per_query_retrieved": per_q_retrieved,
        **{m: sum(v) / len(v) if v else 0.0 for m, v in metrics.items()},
        "mrr": mrr,
        ...
    }
```

- pipeline 只调用一次，取 `max(ks)` 个结果，所有 k 的指标都从同一个列表截取——保证不同 k 之间可比。
- `judge = judge or MockJudge()`：允许注入自定义评审器（例如测验 Q11 的 `StrictJudge`）。
- `defaultdict(list)` 按指标名收集每个 query 的值，最后用字典推导式求**宏平均**（每个 query 权重相同）。
- `**{...}` 把推导出的字典展开合并进返回字典。
- 返回值里保留了 `per_query_retrieved`，便于逐 query 排查（讲义："Persist the metric trace per query"）。
- ⚠️ faithfulness 的上下文是**全部检索到的文档**，而三个 pipeline 的答案都是检索文档正文的原句，因此 faithfulness 必然为 1.0（测验 Q11）。
- ⚠️ 上下文依赖模块级的 `CORPUS`：如果要评估使用其它语料的 pipeline，需要改造为由 pipeline 返回上下文文本。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 实现所有指标 | 每个公式都可见、可测 | 生产可用 `pytrec_eval`、`ranx` 或 Ragas 等库，但要确认其定义一致 |
| precision 分母固定为 k | IR 标准定义，惩罚返回过少 | 与第 69 节不一致；报告中要写明口径 |
| nDCG 指数增益 `2^rel − 1` | 突出高度相关文档 | 与线性增益的结果不同；报告中要写明 |
| IDCG 用 qrels 全部分级文档 | 漏检相关文档会被惩罚 | 需要 qrels 标注完整且一致 |
| 句子 = claim | 实现简单 | 复合句含多个事实时粒度太粗；生产用 LLM 拆原子 claim |
| token 重叠 `MockJudge` | 离线、确定、无成本 | 对数字、否定、实体替换无感；生产用 NLI 或 LLM 评审并人工校准 |
| 抽取式答案（拼接正文） | 不需要 LLM | faithfulness 结构性饱和，无法评估生成器 |
| 宏平均 | 每个 query 同等重要 | 掩盖某类 query 的失败；应按类别切片报告（讲义练习 4） |
| 干扰文档 d9–d12 | 制造困难负例，考察排序 | 只有 4 个 query，统计意义有限 |
| "rerank" 复用标题信号 | 简单示意 | 与 hybrid 结果完全相同，无法展示 rerank 的价值；应接入真正不同的信号（第 66 节） |
| 统一 `PipelineFn` 接口 | 任何变体都能接入同一评估 | 上下文从全局 `CORPUS` 取，接口不够自包含 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + `field(default_factory=dict)` | `graded_relevance: dict[str, int] = field(default_factory=dict)` | 可变默认值必须用工厂函数 |
| 类型别名 | `PipelineFn = Callable[[str, int], tuple[list[str], str]]` | 给复杂函数类型起名字；`Callable[[参数类型...], 返回类型]` |
| 元组默认参数 | `ks: tuple[int, ...] = (1, 3, 5)` | `tuple[int, ...]` 表示任意长度的整数元组；元组不可变，适合作默认值 |
| `X \| None` 可选参数 | `judge: MockJudge \| None = None` | 配合 `judge = judge or MockJudge()` 提供默认实例 |
| 生成器表达式计数 | `sum(1 for r in top if r in gold)` | 不建中间列表直接求和 |
| 集合运算 | `set(retrieved[:k]) & gold`、`set(expanded_counter) \| set(d_counter)` | 交集、并集 |
| 集合推导式 | `{t for t in _TOK.findall(text.lower()) if t not in stop and len(t) > 1}` | 一行构建去重集合 |
| `enumerate` + 提前 `return` | `reciprocal_rank` | 找到第一个命中立即返回 |
| `raise ValueError(f"...")` | `mean_reciprocal_rank` | 参数不合法时主动抛异常，附带说明 |
| 相邻 f-string 拼接 | `f"retrieved_per_query ... " f"({len(a)} vs {len(b)})"` | 括号内相邻字符串自动拼接 |
| `**` 幂运算 | `(2 ** rel) - 1` | 整数幂 |
| `math.log2` | `math.log2(i + 2)` | 以 2 为底的对数 |
| `sorted(dict.items(), key=...)` | `sorted(graded.items(), key=lambda x: -x[1])` | 按值降序排列键值对 |
| 后行断言正则 | `re.compile(r"(?<=[.!?])\s+")` | `(?<=...)` 匹配位置但不消耗字符，标点留在前一句 |
| `Counter` 的缺省 0 | `d_counter[t]`、`min(expanded_counter[t], d_counter[t])` | 访问不存在的键返回 0 |
| `list(q_tokens)` 复制后遍历 | `for t in list(q_tokens): expanded.extend(...)` | 遍历副本，避免一边遍历一边修改同一列表 |
| 条件表达式 | `top[0].body if top else "I do not know."` | 三元表达式 |
| 嵌套函数 / 闭包 | `hybrid_plus_rerank_pipeline` 内的 `def title_boost(doc_id)` | 内部函数读取外层变量 |
| 字典推导式 + 解包 | `**{m: sum(v) / len(v) if v else 0.0 for m, v in metrics.items()}` | 构造字典并合并到外层字典字面量中 |
| 函数作为字典值 | `pipelines = {"baseline": baseline_pipeline, ...}` | 函数是一等公民，可以存入字典再调用 |
| f-string 格式符 | `f"{v:.3f}"`、`f"{n:<14}"`、`f"{m:<15} \| {cells}"` | 3 位小数、左对齐定宽 |
| `" \| ".join(...)` | 表格单元拼接 | 用分隔符连接字符串 |
| 死代码 | `_bow`、`_score_doc` 定义了但从未被调用；rerank 函数中的空循环 | 阅读时注意区分"真正参与计算"的代码 |

---

## 6. 运行结果解读

实际运行（Python 3.13，纯标准库，瞬间完成）：

```text
metric          | baseline       | hybrid         | hybrid+rerank 
------------------------------------------------------------------
precision@1     | 0.500          | 1.000          | 1.000         
precision@3     | 0.417          | 0.417          | 0.417         
precision@5     | 0.250          | 0.250          | 0.250         
recall@1        | 0.375          | 0.875          | 0.875         
recall@3        | 1.000          | 1.000          | 1.000         
recall@5        | 1.000          | 1.000          | 1.000         
ndcg@1          | 0.500          | 1.000          | 1.000         
ndcg@3          | 0.724          | 0.882          | 0.882         
ndcg@5          | 0.724          | 0.882          | 0.882         
mrr             | 0.750          | 1.000          | 1.000         
faithfulness    | 1.000          | 1.000          | 1.000         
answer_relevance | 0.750          | 1.000          | 1.000         
```

我们额外打印了每个 query 的检索结果：

| qid | baseline | hybrid（= hybrid+rerank） |
|-----|----------|-------------------------|
| q1 | d3, d9, d1 | d3, d9, d1 |
| q2 | **d11**, d4 | d4, d11 |
| q3 | d6, d12 | d6, d12 |
| q4 | **d10**, d7 | d7, d10 |

逐项解读：

- **baseline 输在哪里**：q2 被干扰文档 d11（"A central permission gate..."，与 query 措辞完全一样）抢了第一；q4 被 d10（"Long-running workers..."）抢了第一。所以 baseline 的 MRR = `(1 + 0.5 + 1 + 0.5)/4 = 0.75`，precision@1 = 0.5，nDCG@1 = 0.5。
- **hybrid 赢在哪里**：同义词把 `central → centralized`、`gate → check`、`stop → cancel/cancellation` 连起来，并且标题奖励让 d4（标题 check_permission）、d7（标题 Cancellation）上升。MRR 达到 1.0。
- **precision@3/@5 三列相同**：每个 pipeline 返回的文档集合相同（只是顺序不同），集合型指标自然相同。q2–q4 只返回 2 个文档，precision@3 = 1/3、precision@5 = 1/5。
- **recall@1 = 0.875 而不是 1.0**：q1 有两个 gold（d3、d1），top-1 只能覆盖一半。
- **nDCG@3 = 0.882 而不是 1.0**：hybrid 在 q1 中 d9（不相关）仍排在 d1 前面（0.905）；q2 的 IDCG 包含了未被检索到的 d5（相关度 2），nDCG@5 = 0.787；q3、q4 的 IDCG 分别包含 d8、d2。可见 nDCG 受 qrels 中"二值 gold 之外的分级文档"影响很大。
- **hybrid+rerank 与 hybrid 完全相同**：rerank 使用的标题信号 hybrid 已经用过了，没有新信息（见 3.7）。讲义 "the rerank row beats hybrid on MRR" 在此不成立；讲义 "hybrid beats baseline on recall" 只在 recall@1 上成立。
- **faithfulness 全是 1.000**：答案就是检索文档的原句，结构性饱和。
- **answer_relevance baseline 0.75**：q3 的 baseline 答案只有 d6 的正文，问题内容词 `{production, search, engines, fuse, two, retrievers}` 中只命中 production、search（2/6 = 0.33 < 0.4）；hybrid 拼接了 d12 的正文，多命中了 engines（3/6 = 0.5），于是变成 1。也就是说，**拼接一篇干扰文档反而让"相关性"变好了**——这是 token 重叠评审的又一个盲区。
- **表头错位**：`answer_relevance` 有 16 个字符，超出 `{m:<15}` 的宽度，所以最后一行比其它行多出一个字符，竖线没有对齐。

---

## 7. 动手改一改

1. **讲义练习 1（hit-rate@k）**：实现 `hit_rate_at_k(retrieved, gold, k)`，加入 `evaluate_pipeline`。验证 baseline 的 hit-rate@1 = 0.5、recall@1 = 0.375，解释二者只在多 gold 的 q1 上不同。
2. **讲义练习 2（分级忠实度）**：把 `MockJudge.supported` 改成返回 0/1/2（重叠 < 0.4 为 0，0.4–0.8 为 1，≥ 0.8 为 2），faithfulness 改为 `Σ 分数 / (2 × claim 数)`。
3. **更严格的评审**：实现测验 Q11 的 `StrictJudge`（数字必须出现在上下文中），再把否定词（not、never、no）也纳入"关键 token"。构造 5 条故意出错的答案，比较新旧评审器的检出率。
4. **讲义练习 4（按类别切片）**：给 `Qrel` 加 `query_class` 字段（literal / paraphrased / multi-topic），让 `evaluate_pipeline` 同时输出每个类别的平均指标。
5. **修复 qrels 与 rerank**：用测验 Q12 的一致性检查找出问题并修正 qrels；把 `hybrid_plus_rerank_pipeline` 换成第 66 节的 cross-encoder 打分，再加 2–3 条更难的 query，看 rerank 一列能否与 hybrid 拉开差距。
6. **进阶**：把答案生成换成"模板化改写"（例如把正文中的数字随机替换），制造可控的幻觉，检验 faithfulness 指标能否随幻觉比例单调下降。

---

## 8. 常见坑

- **MRR 分母漏掉没命中的 query**：没命中贡献 0，但必须计入分母。
- **precision 分母用实际返回个数**：会让"只返回 1 个"的系统 precision 虚高；本节用 k，第 69 节用实际个数，混用会出错。
- **IDCG 只用检索到的文档计算**：会把漏检的相关文档"藏起来"，nDCG 虚高。
- **二值 gold 与分级 qrels 不一致**：同一结果在不同指标中口径不同（本节 4 条 qrels 全部存在此问题）。
- **用抽取式答案评估 faithfulness**：指标恒为 1，什么也没测到。
- **相信 token 重叠评审**：数字、否定、实体替换类幻觉都会被判为"支持"。
- **指标饱和还继续比较**：MRR 已是 1.0 时，任何"改进"都无法体现；需要更难的 query 或更细的指标。
- **把宏平均当全部真相**：4 个 query 的平均掩盖了 q2、q4 这类"措辞陷阱"的失败模式，应逐 query 查看并按类别切片。
- **评估依赖全局语料**：`evaluate_pipeline` 用模块级 `CORPUS` 取上下文，换语料时容易忘记同步。

---

## 9. 测试在验证什么

测试文件：`tests/test_eval.py`（`unittest` 风格）。在 `code/` 目录下运行 `python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`。

| 测试类 | 测试方法 | 验证的性质 |
|-------|---------|-----------|
| `TestPrecision` | `test_perfect` / `test_partial` | 全中为 1.0；3 个中 1 个为 1/3 |
| | `test_k_larger_than_retrieved` | 只返回 1 个且命中时 precision@5 = 0.2（分母为 k） |
| | `test_zero_k_returns_zero` | k = 0 返回 0 |
| `TestRecall` | `test_perfect` / `test_partial` / `test_empty_gold` | 全覆盖 1.0；两个 gold 中 1 个为 0.5；gold 为空返回 0 |
| `TestMRR` | `test_first_position` / `test_second_position` / `test_not_found` | 名次 1 → 1.0，名次 2 → 0.5，未命中 → 0 |
| | `test_mean` | 三个 query 的平均为 `(1 + 0.5 + 0) / 3`，未命中的 query 计入分母 |
| `TestNDCG` | `test_perfect_ranking` | 理想排序 nDCG = 1.0 |
| | `test_inverted_ranking` | 倒序时 0 < nDCG < 1 |
| | `test_dcg_zero_when_no_relevant` | 没有相关文档时 DCG = 0 |
| `TestClaims` | `test_extract_claims_split_on_sentences` | 按 `.!?` 切成 4 段（最后一段无标点也算） |
| | `test_extract_claims_empty` | 空字符串返回空列表 |
| `TestFaithfulness` | `test_all_supported` / `test_none_supported` / `test_empty_claims` | 低阈值下完全支持为 1.0；高阈值且无关上下文为 0.0；无 claim 为 0.0 |
| `TestAnswerRelevance` | `test_relevant` / `test_irrelevant` | 词汇重叠的答案判相关；天气答案判不相关 |
| `TestEvaluatePipeline` | `test_returns_all_metrics` | 返回字典包含 6 类指标键 |
| | `test_hybrid_beats_baseline_on_recall_at_1` | hybrid 的 recall@1 与 MRR **不低于** baseline |
| | `test_hybrid_plus_rerank_at_least_as_good_as_hybrid` | rerank 的 MRR **不低于** hybrid（允许 1e-9 误差） |

实际运行结果：

```text
........................                                                 [100%]
24 passed in 0.03s
```

几点评价：

- 指标函数的单元测试覆盖较完整，包括多个边界情况，是本文件最扎实的部分。
- `test_hybrid_beats_baseline_on_recall_at_1` 名字说 "beats"，断言用的是 `assertGreaterEqual`——即使 hybrid 与 baseline 完全相同也会通过。
- `test_hybrid_plus_rerank_at_least_as_good_as_hybrid` 同样只要求"不差于"；而实际 rerank 与 hybrid 完全相同，这个测试无法发现"rerank 没有任何作用"。
- 没有测试覆盖 qrels 的一致性（二值 gold 与分级相关度），也没有测试 faithfulness 能否检出幻觉（例如数字被篡改的答案）。
- `test_none_supported` 把阈值调到 0.8 才得到 0.0：用默认阈值 0.4 时，"the abort threshold is three failed parts" 与无关上下文没有交集，同样是 0.0；但这个测试没有覆盖"部分重叠但事实错误"的情况，而那恰恰是 mock 评审最大的盲区。
