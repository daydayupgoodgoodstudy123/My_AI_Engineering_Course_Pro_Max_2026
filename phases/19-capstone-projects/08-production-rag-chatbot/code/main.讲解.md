# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 08 节 面向受监管行业的生产级 RAG 聊天机器人 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`hashlib`、`re`、`dataclasses`）；不调用任何 LLM、embedding 模型或数据库

---

## 1. 这份代码在考察什么

讲义描述的是一个完整的受监管行业 RAG 系统：docling/ColPali 入库、pgvector + Tantivy 混合检索、bge-reranker 重排、Claude Sonnet 4.7 合成、Llama Guard 4 + NeMo Guardrails + Presidio 护栏、RAGAS + Phoenix 评估。

`main.py` 的 docstring 说明它只抓住一个"最难的架构原语"：**缓存感知的 prompt 组装（cache-aware prompt assembly）**——既要保持稳定前缀以获得 prompt caching 折扣，又要按 role 和 jurisdiction 过滤检索结果。围绕它，脚本用极简的替身实现了：

1. **带合规标签的 chunk**：每个 chunk 有 `role` 和 `jurisdiction`；
2. **先过滤再检索**：访问控制在检索之前强制执行；
3. **混合检索 + RRF**：一个 Jaccard 版"dense"、一个简化版"BM25"，用 reciprocal rank fusion 融合；
4. **cache key 构造与缓存模拟器**：system + policy + context 求哈希，问题不参与；
5. **护栏桩**：正则版"Llama Guard"输入检查、正则版"Presidio"输出清洗；
6. **端到端一轮对话**：护栏 → 检索 → 组装 → 查缓存 → "合成" → 清洗 → 返回引用。

> 一句话：**这份代码展示 prompt 前缀如何对齐、访问控制放在哪一层**。它的检索打分、护栏和"合成"都是玩具，其中几处简化（无相关性阈值、无停用词、context 顺序敏感）恰好能引出讲义的练习 2 和练习 5。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Chunk` | dataclass | 文档片段：`doc_id`、`section`、`text`、`role`、`jurisdiction`；`anchor()` 生成引用锚点 | 带合规标签的 chunk |
| `CORPUS` | 列表 | 5 个 chunk：2 个 GDPR/analyst、1 个 HIPAA/counsel、1 个 SOC2/counsel、1 个 public/any | 演示语料 |
| `tokenize` | 函数 | `\w+` 正则 + 小写 | 分词 |
| `bm25_score` | 函数 | 命中词计数 / 长度归一（不是真 BM25） | 稀疏检索替身 |
| `dense_score` | 函数 | 词集合 Jaccard（不是 embedding） | 稠密检索替身 |
| `retrieve` | 函数 | role + jurisdiction 过滤 → 两路排序 → RRF 融合 → top-k | 混合检索 |
| `SYSTEM_PROMPT` | 常量 | 要求逐条引用、不越出上下文、不确定就说明 | 稳定前缀 |
| `PromptLayout` | dataclass | system / policy / context / question 四段；`cache_key()` 哈希前三段 | 缓存友好结构 |
| `PromptCache` | 类 | 记录见过的 key，统计 hits/misses | prompt caching 模拟器 |
| `BLOCKED_PATTERNS` / `llama_guard_input` | 常量 + 函数 | 3 条正则黑名单 | 输入护栏替身 |
| `presidio_scrub` | 函数 | 正则替换邮箱、SSN | 输出 PII 清洗替身 |
| `chat_turn` | 函数 | 串起完整一轮对话，返回 dict | Conversation 侧流水线 |
| `main` | 函数 | 4 个演示请求 + 打印命中率 | 入口 |

数据流：`query, role, jurisdiction` → `llama_guard_input`（拦截则直接返回）→ `retrieve`（过滤 + RRF）→ 拼 `context` → `PromptLayout` → `cache.check(cache_key)` → 拼"答案"→ `presidio_scrub` → 返回 `{answer, citations, cache_hit, cache_key}`。

---

## 3. 逐段精讲

### 3.1 `Chunk` 与语料：合规标签是一等字段

```python
@dataclass
class Chunk:
    doc_id: str
    section: str
    text: str
    role: str           # "analyst" | "counsel" | "public"
    jurisdiction: str   # "GDPR" | "HIPAA" | "SOC2" | "any"

    def anchor(self) -> str:
        return f"{self.doc_id} {self.section}"
```

- 讲义 Concept："chunks get summaries, tags, and role-based access labels"。这里把 `role` 和 `jurisdiction` 直接做成字段，而不是藏在文本里——过滤必须基于结构化元数据。
- `anchor()` 生成 `"MSA-2024-03-11 s12.4"` 这样的引用锚点，与 `SYSTEM_PROMPT` 要求的 "(doc_id section)" 格式一致，也是 RRF 字典的键。
- 语料里的条款与讲义 Use It 示例对应：MSA s12.4（30 天删除）、DPA-v2.1 s5（受限数据 14 天）。
- ⚠️ 每个 chunk 只有一个 role：没有"counsel 也能看 analyst 文档"这类层级关系；真实系统常用 ABAC（基于属性）或权限集合。

### 3.2 两个检索打分替身

```python
def tokenize(s: str) -> list[str]:
    return re.findall(r"\w+", s.lower())


def bm25_score(query: str, chunk: Chunk) -> float:
    q = set(tokenize(query))
    c = tokenize(chunk.text + " " + chunk.section + " " + chunk.doc_id)
    if not q or not c:
        return 0.0
    return sum(1.0 for w in c if w in q) / (1 + len(c) / 20)


def dense_score(query: str, chunk: Chunk) -> float:
    """Stand-in for a real Voyage-3 or Nomic embedding cosine."""
    q = set(tokenize(query))
    c = set(tokenize(chunk.text))
    if not q or not c:
        return 0.0
    return len(q & c) / max(1, len(q | c))  # Jaccard stand-in
```

- `bm25_score`：数 chunk 里有多少个词出现在问题中（重复出现会重复计数），再除以 `1 + 长度/20` 做长度惩罚。和真正的 BM25 相比：**没有 IDF**（`the` 和 `retention` 同权）、**没有 tf 饱和**（无 k1）、长度归一用固定常数 20 而非平均文档长度；还把 `section`、`doc_id` 拼进来，相当于粗糙的"字段"。
- `dense_score`：词集合的 Jaccard 相似度 `|A∩B| / |A∪B|`，只是"重叠比例"，没有任何语义能力。`max(1, ...)` 防止分母为 0。
- ⚠️ 没有停用词表：实测主查询里，与问题无关的 FAQ 因为共享 `the` 和 `data`（Jaccard 2/18 ≈ 0.111）压过了讲删除期限的 DPA（只共享 `data`，1/19 ≈ 0.053）。
- ⚠️ 没有词形归一：`user` 与 `users`、`retention` 与 `deletion` 都不匹配。

### 3.3 `retrieve`：先过滤，再 RRF

```python
def retrieve(query: str, role: str, jurisdiction: str,
             corpus: list[Chunk], k: int = 5) -> list[tuple[Chunk, float]]:
    # enforce access policy up front  (critical in regulated domains)
    eligible = [c for c in corpus
                if (c.role == role or c.role == "public") and
                (c.jurisdiction == jurisdiction or c.jurisdiction == "any")]
    hits: dict[str, float] = {}
    anchors: dict[str, Chunk] = {}
    for rank, c in enumerate(sorted(eligible, key=lambda x: -dense_score(query, x))):
        hits[c.anchor()] = hits.get(c.anchor(), 0.0) + 1 / (60 + rank + 1)
        anchors[c.anchor()] = c
    for rank, c in enumerate(sorted(eligible, key=lambda x: -bm25_score(query, x))):
        hits[c.anchor()] = hits.get(c.anchor(), 0.0) + 1 / (60 + rank + 1)
        anchors[c.anchor()] = c
    ranked = sorted(hits.items(), key=lambda x: -x[1])
    return [(anchors[a], s) for a, s in ranked[:k]]
```

- **过滤在最前面**：列表推导式一次筛掉无权限的 chunk。这正是讲义 Build It 第 3 步"Filter by role+jurisdiction first"。访问控制是确定性代码，不依赖 LLM"自觉不说"。
- **RRF**：每路排序后，第 `rank`（从 0 开始）名得 `1/(60 + rank + 1)`，两路相加。只用名次、不用原始分数，所以 Jaccard（0～1）与"BM25"（无上界）的量纲差异不成问题。
- `key=lambda x: -score` 实现降序；`sorted` 是稳定排序，分数相同时保持语料原顺序。
- 实测主查询（analyst / GDPR）：

| chunk | dense 名次 | bm25 名次 | RRF |
|---|---|---|---|
| MSA s12.4 | 1 | 1 | 1/61 + 1/61 = 0.03279 |
| FAQ Q1 | 2 | 2 | 1/62 + 1/62 = 0.03226 |
| DPA s5 | 3 | 3 | 1/63 + 1/63 = 0.03175 |

- ⚠️ **没有相关性门槛**：所有合格 chunk 都会拿到 RRF 分数，哪怕两路原始分都是 0。实测 `"zzz unrelated"` 照样返回 3 个 chunk。由于 public 的 FAQ 对任何 role、任何 jurisdiction 都合格，`retrieve` 永远不会返回空列表，`chat_turn` 的"不确定"分支对本语料不可达。修复见测验 Q10。
- ⚠️ 没有 reranker：讲义是 top-20 → reranker → top-5，这里直接 RRF 取 top-k。
- 两个循环几乎一样，可以抽成 `for score_fn in (dense_score, bm25_score):`；而且每次 `sorted` 的 key 都会重新计算分数，生产中应先算好再排序。

### 3.4 `PromptLayout`：缓存前缀的结构

```python
@dataclass
class PromptLayout:
    system: str
    policy: str
    context: list[str]
    question: str

    def cache_key(self) -> str:
        prefix = self.system + "\n" + self.policy + "\n" + "\n".join(self.context)
        return hashlib.sha256(prefix.encode()).hexdigest()[:16]
```

- 四段从稳定到易变：system（几乎不变）→ policy（随 role/jurisdiction 变）→ context（随检索结果变）→ question（每次都变）。对应讲义 Build It 第 4 步："System prompt + static policies in cache header; reranked context as cache extension; user question as uncached suffix"。
- `cache_key` **不含 question**：同一上下文、不同问法也能命中——这是"用户问变体"时的收益来源。
- `policy` 含 role 和 jurisdiction：不同权限的请求永远不会共享缓存。这在成本上是损失，在安全上是正确的隔离。
- ⚠️ `"\n".join(self.context)` 对**顺序敏感**。实测把问题从 "what is the data retention obligation for EU user profiles" 改成 "data retention obligation EU user profiles"，检索到的 3 个 chunk 完全相同，但顺序从 MSA、FAQ、DPA 变成 MSA、DPA、FAQ，cache key 改变 → 未命中。按稳定键（如 anchor）排序 context 能避免这种抖动。
- docstring 写"Prompt caching buys 60-80% discount"，把讲义里的"命中率 60–80%"和"折扣 60–90%"混在了一起（讲义 Key Terms："cached prefix tokens discounted 60-90% on hit"）。

### 3.5 `PromptCache`：全有或全无的模拟器

```python
class PromptCache:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}
        self.hits = 0
        self.misses = 0

    def check(self, key: str) -> bool:
        if key in self.store:
            self.store[key] += 1
            self.hits += 1
            return True
        self.store[key] = 1
        self.misses += 1
        return False
```

- 第一次见到 key 记为未命中并"写入缓存"，之后见到记为命中；`store[key]` 记录被使用次数。
- `hit_rate()` 用条件表达式防止除零：`self.hits / total if total else 0.0`。
- ⚠️ 与真实 prompt caching 的差异：
  - 真实缓存是**前缀匹配**，可以在 system 段末尾命中、在 context 段未命中（部分命中）；模拟器只有整段完全相同才算命中；
  - 没有 TTL（真实缓存几分钟不用就过期）、没有容量上限；
  - 不区分"缓存写入"和"缓存读取"的价格。

### 3.6 护栏桩：正则版 Llama Guard 与 Presidio

```python
BLOCKED_PATTERNS = [
    r"ignore previous instructions",
    r"reveal the system prompt",
    r"show me (?:social security|credit card)",
]


def llama_guard_input(query: str) -> tuple[bool, str]:
    for pat in BLOCKED_PATTERNS:
        if re.search(pat, query, re.IGNORECASE):
            return False, f"blocked by Llama Guard 4: {pat}"
    return True, "ok"


def presidio_scrub(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[ssn]", text)
    return text
```

- 返回 `(bool, str)` 元组：是否放行 + 原因，调用方用元组解包 `ok, reason = ...`。
- `(?:...)` 是非捕获分组；`re.IGNORECASE` 让大小写无关。
- 实测可以绕过的输入：`Ignore all previous instructions`、`please reveal your system prompt`、`ignore  previous instructions`（两个空格）。正则黑名单只能当桩，真实系统要用 Llama Guard 4 分类器 + NeMo Guardrails 策略，并用红队套件持续测试。
- `presidio_scrub` 实测：`a.b+c@x.co.uk` → `[email]`、`123-45-6789` → `[ssn]`；但 `555-123-4567`（电话）和 `123456789`（不带横线的 SSN）都原样保留。
- ⚠️ 输出护栏只有 PII 清洗，没有讲义说的"citation enforcement post-filter"（校验答案中的引用都来自本次检索），docstring 虽然列了"citation enforcement"，代码里并没有单独的校验步骤——"答案"本身就是由检索结果拼出来的，所以引用天然一致。

### 3.7 `chat_turn`：一轮对话的完整编排

```python
def chat_turn(query: str, role: str, jurisdiction: str,
              corpus: list[Chunk], cache: PromptCache) -> dict:
    ok, reason = llama_guard_input(query)
    if not ok:
        return {"blocked": True, "reason": reason}

    hits = retrieve(query, role, jurisdiction, corpus, k=3)
    context = [f"[{c.anchor()}] {c.text}" for c, _ in hits]

    layout = PromptLayout(
        system=SYSTEM_PROMPT,
        policy=f"role={role} jurisdiction={jurisdiction}",
        context=context,
        question=query,
    )
    cache_hit = cache.check(layout.cache_key())

    if hits:
        answer = f"Based on the cited sections: " + "; ".join(
            f"{c.anchor()} -> {c.text[:60]}" for c, _ in hits
        )
    else:
        answer = "I do not have confident citations for this question."

    answer = presidio_scrub(answer)
    return {...}
```

- 顺序：输入护栏 → 检索 → 组装 → 查缓存 → 合成 → 输出清洗。被拦截的请求**不会**走到 `cache.check`，所以不计入命中率统计。
- `for c, _ in hits`：`_` 丢弃 RRF 分数。
- "合成"只是把每个 chunk 的前 60 个字符拼起来（`c.text[:60]`），所以打印的答案会在单词中间截断，如 `...deleted within 30`。真正的合成需要调用 LLM，并要求逐条引用。
- `f"Based on the cited sections: "` 是没有占位符的 f-string，`f` 前缀多余但无害。
- 返回 dict 里同时有 `cache_hit` 和 `cache_key`，方便在 Langfuse 一类工具里统计命中率和定位"打破前缀"的请求（讲义练习 2）。
- ⚠️ `layout.cache_key()` 被调用了两次（查缓存一次、返回一次），重复计算哈希。
- ⚠️ 没有多轮记忆：讲义的 LangGraph 会话、10k token 摘要缓冲（练习 3）都未实现；TS 版本用 `SessionStore` 实现了会话存储。

### 3.8 `main`：四个演示请求

- 请求 1、2 完全相同 → 第 2 次命中；请求 3 换了 role 和 jurisdiction → 未命中；请求 4 被正则拦截。
- 最后 `f"{cache.hit_rate():.2%}"`：`.2%` 格式符把 0.3333 显示成 `33.33%`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 检索前硬过滤 role + jurisdiction | 访问控制必须确定性执行 | 生产在向量库层做 payload filter（pgvector WHERE / Qdrant filter），并记审计日志 |
| RRF 融合名次 | 两路分数量纲不同，RRF 无需归一化 | 丢掉绝对分数，无法判断"都不相关"；需 reranker 分数 + 阈值 |
| Jaccard / 简化 BM25 替身 | 不依赖模型和索引，能跑 | 无语义、无 IDF、被停用词左右；生产用 Voyage-3/Nomic + Tantivy BM25 |
| cache key 不含问题 | 问题是不缓存的后缀 | 正确；但 context 顺序敏感，应按稳定键排序 |
| policy（role/jurisdiction）进入 cache key | 不同权限不共享缓存 | 命中率被权限组合数稀释；可把 policy 放在 context 之后、或按租户分组 |
| 全有或全无的缓存模拟 | 实现最简单 | 低估真实的部分前缀命中；无 TTL、无写入成本 |
| 正则护栏 | 演示护栏位置 | 极易绕过；生产用 Llama Guard 4、NeMo Guardrails、Presidio，配红队测试 |
| 用检索文本拼答案 | 无需 LLM | 不能测 faithfulness；生产要 LLM 合成 + 引用强制校验 + RAGAS |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可直接写 `list[tuple[Chunk, float]]` |
| `@dataclass` | `class Chunk`、`class PromptLayout` | 自动生成构造函数等；按字段顺序位置传参：`Chunk("MSA-...", "s12.4", ...)` |
| 方法 | `def anchor(self) -> str` | dataclass 也可以有普通方法 |
| 正则 `re.findall` | `re.findall(r"\w+", s.lower())` | 返回所有匹配的列表；`\w` 匹配字母、数字、下划线（含 Unicode 字母） |
| 原始字符串 | `r"\b\d{3}-\d{2}-\d{4}\b"` | `r` 前缀让反斜杠不被转义；`\b` 是单词边界 |
| 非捕获分组 | `(?:social security|credit card)` | 只分组不捕获 |
| `re.sub` | `re.sub(pattern, "[email]", text)` | 替换所有匹配 |
| `re.search` + flag | `re.search(pat, query, re.IGNORECASE)` | 在任意位置查找，忽略大小写 |
| 集合运算 | `q & c`、`q | c` | 交集、并集 |
| 生成器表达式 | `sum(1.0 for w in c if w in q)` | 不建列表直接求和 |
| 列表推导式 + 复合条件 | `[c for c in corpus if (...) and (...)]` | 过滤列表 |
| `lambda` 作排序键 | `sorted(eligible, key=lambda x: -dense_score(query, x))` | 取负号实现降序 |
| `enumerate` | `for rank, c in enumerate(sorted(...))` | 同时得到下标和元素 |
| `dict.get` 累加 | `hits.get(c.anchor(), 0.0) + ...` | 键不存在时用默认值 |
| `dict.items()` 排序 | `sorted(hits.items(), key=lambda x: -x[1])` | 按值降序排 (键, 值) 对 |
| 切片 | `ranked[:k]`、`c.text[:60]`、`hexdigest()[:16]` | 取前 N 个 |
| 元组返回与解包 | `return False, f"..."`；`ok, reason = llama_guard_input(query)` | 一次返回多个值 |
| `_` 占位 | `for c, _ in hits` | 忽略不需要的值 |
| `str.join` | `"\n".join(self.context)`、`"; ".join(...)` | 用分隔符拼接字符串列表 |
| 条件表达式 | `self.hits / total if total else 0.0` | 防止除零 |
| `dict.get` 安全取值 | `r.get('blocked')` | 被拦截的结果没有 `cache_hit` 等键，用 `.get` 避免 `KeyError` |
| f-string 格式符 | `{cache.hit_rate():.2%}`、`{r['answer'][:140]}` | 百分比两位小数；f-string 内可以写表达式 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`）：

```text
=== analyst / GDPR ===
  cache_hit=False citations=['MSA-2024-03-11 s12.4', 'general-privacy-faq Q1', 'DPA-v2.1 s5']
  answer: Based on the cited sections: MSA-2024-03-11 s12.4 -> Upon termination, EU user profiles must be deleted within 30; general-privacy-faq Q1 ->...

=== same query repeated (same cache prefix) ===
  cache_hit=True

=== counsel / HIPAA ===
  cache_hit=False citations=['HIPAA-BAA-2024 s7', 'general-privacy-faq Q1']

=== blocked prompt (jailbreak attempt) ===
  blocked=True  reason=blocked by Llama Guard 4: ignore previous instructions

cache hit rate: 33.33% (hits=1 misses=2)
```

逐项解读：

- **analyst / GDPR**：可见的 chunk 是 2 个 GDPR/analyst + 1 个 public FAQ，过滤掉了 HIPAA 和 SOC2（它们属于 counsel）。三者全部返回（k=3）。无关的 FAQ 排在第 2，原因是停用词 `the` 和 `data`（见 3.2）。答案在 60 个字符处截断，所以出现 "deleted within 30" 而不是 "30 days"。
- **重复请求命中**：同一 role、同一 context 顺序 → 相同 cache key（实测为 `8a4a2f0b11d90449`）。
- **counsel / HIPAA**：可见的是 HIPAA chunk 和 FAQ（SOC2 是 counsel 的但 jurisdiction 不符），返回 2 个。policy 不同，未命中。
- **越狱被拦**：命中第一条正则；只报告第一个匹配的模式（`reveal the system prompt` 也匹配，但循环已经返回）。
- **命中率 33.33%**：被拦截的请求没有走到缓存，分母是 3 而不是 4。

补充实验（测验中引用的数据都来自这些实测）：

| 实验 | 结果 |
|---|---|
| `retrieve("zzz unrelated", "analyst", "GDPR")` | 仍返回 MSA、DPA、FAQ（全零分，按语料顺序） |
| `retrieve("zzz", "counsel", "GDPR")` | 只返回 FAQ（counsel 没有 GDPR 文档） |
| 去掉 what/is/the/for 的问题 | 相同 3 个 chunk、顺序变为 MSA、DPA、FAQ，cache 未命中 |
| `llama_guard_input("Ignore all previous instructions")` | `(True, 'ok')`，绕过 |
| `presidio_scrub("... phone 555-123-4567 ssn2 123456789")` | 电话与无横线 SSN 未被清洗 |

---

## 7. 动手改一改

1. **加停用词表**：在 `tokenize` 后过滤 `{"the", "is", "what", "for", "a", "of", ...}`，重跑主查询，观察 DPA 是否排到 FAQ 前面。
2. **unsure 模式**（讲义练习 5）：在 `retrieve` 中丢弃两路原始分数都为 0 的 chunk（参考测验 Q10），验证 `"zzz unrelated"` 得到"I do not have confident citations"。
3. **稳定 context 顺序**（讲义练习 2）：在 `chat_turn` 里把 `hits` 按 `anchor()` 排序后再组装 context，验证换问法（检索集合相同）时能命中缓存。再写一个 50 条变体问题的小脚本统计命中率变化。
4. **前缀匹配缓存**：把 `PromptCache` 改成按段累进的前缀哈希（`h1 = H(system)`、`h2 = H(system+policy)`、`h3 = H(system+policy+context)`），统计"命中到第几段"，并按"每段 token 数 × 折扣"估算成本。
5. **跨辖区探针**（讲义练习 1）：给语料增加 HIPAA/analyst 的 chunk，写 20 个带 HIPAA 关键词的问题，以 analyst/GDPR 身份查询，断言所有返回 chunk 的 jurisdiction ∈ {GDPR, any}。
6. **进阶**：接入真实的 embedding（如 sentence-transformers 小模型）替换 `dense_score`，接入 `rank_bm25` 替换 `bm25_score`，再加一个 cross-encoder reranker，比较 top-3 的变化。

---

## 8. 常见坑

- **把访问控制交给 prompt**：在 system prompt 里写"不要告诉 analyst HIPAA 内容"是不够的；必须在检索阶段过滤，模型根本看不到无权限的文本。
- **用 RRF 分数做相关性阈值**：RRF 只反映名次，最差的 chunk 也有约 1/(60+n) 的分数；阈值要用原始分数或 reranker 分数。
- **context 顺序不稳定**：同样的 chunk 集合因排序抖动产生不同前缀，缓存白白失效。
- **在前缀里放易变内容**：时间戳、请求 ID、用户名一旦出现在 system prompt 里，命中率就会归零。
- **正则护栏当真**：`Ignore all previous instructions` 就能绕过；护栏要用分类器 + 红队回归测试。
- **PII 正则覆盖不全**：只匹配 `ddd-dd-dddd` 的 SSN 会漏掉其它格式和电话号码；Presidio 用 NER + 规则组合。
- **把 public 文档当"永远安全的兜底"**：它让检索永远非空，掩盖了"其实没有相关文档"的情况。
- **Python 与 TS 实现不一致**：TS 版 `retrieve` 只把 jurisdiction 当加分项、完全不看 role（实测 GDPR 用户能拿到 HIPAA 文档）；两端的合规逻辑必须共用同一套测试。
