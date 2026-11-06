# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 27 节 LLM Evaluation — RAGAS、DeepEval、G-Eval ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`re`；`collections.Counter` 被导入但没有使用），无需 API key

---

## 1. 这份代码在考察什么

讲义的 Step 5 说得很直白：这是一个"只用标准库、近似 RAGAS 四指标和 G-Eval 的玩具评测"，**不是生产代码，只展示评测循环的形状**。它要你搞清楚：

1. **四个 RAG 指标各自测什么**：faithfulness 和 answer relevance 测生成，context precision 和 context recall 测检索。
2. **每个指标需要什么输入**：问题、检索上下文、答案、gold 相关 chunk、期望答案，各自参与哪个指标。
3. **G-Eval 的"步骤化"思想**：把"正确性"拆成"列 claim → 逐条核对 → 求比例"，这与讲义 Step 3 的 evaluation steps 一一对应。
4. **词面近似的天花板**：用 token 重叠代替 NLI 和 LLM judge，会漏掉数字幻觉、惩罚简洁的正确答案。看清这些失败，才能理解为什么生产中要用 NLI + LLM-as-judge，以及为什么 judge 还要校准。
5. **多指标联合诊断**：同一个 case 在不同指标上的高低组合，才能定位问题出在检索还是生成。

> 一句话：**评测循环的骨架是"case → 多个指标 → 汇总 → 解读"**，把每个指标的打分函数从词重叠换成 NLI / judge，骨架不变。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念（生产中的做法） |
|---------|------|------|------------------------|
| `STOP` | 模块级集合 | 21 个英文停用词 | 文本预处理 |
| `tokenize(text)` | 函数 | 小写 → 抽字母数字串 → 去停用词，返回**列表** | 词袋表示 |
| `split_sentences(text)` | 函数 | 按句末标点切句 | 原子 claim 拆分（生产中由 LLM 完成） |
| `faithfulness(answer, context)` | 函数 | 答案中"重叠比例 ≥ 0.5"的句子占比 | RAGAS faithfulness（生产中用 NLI 蕴含） |
| `answer_relevance(question, answer)` | 函数 | 问题与答案词集合的 Jaccard | RAGAS answer relevance（生产中用反推问题 + embedding） |
| `context_precision(retrieved, relevant)` | 函数 | 检索结果中属于 gold 相关集合的比例 | RAGAS context precision（生产中由 judge 判断相关性） |
| `context_recall(retrieved, gold_tokens)` | 函数 | gold 答案 token 被检索文本覆盖的比例 | RAGAS context recall（生产中由 judge 对照 gold 答案） |
| `g_eval_correctness(actual, expected, threshold)` | 函数 | 实际答案中能被期望答案支持的句子占比 | G-Eval 的 Correctness 指标 |
| `main()` | 函数 | 3 个 case × 5 个指标，打印并给出解读 | 评测运行器 |

数据流：每个 case 是一个字典，`main` 从中取出不同字段喂给不同指标，所有指标都依赖 `tokenize`，faithfulness 和 G-Eval 还依赖 `split_sentences`。

---

## 3. 逐段精讲

### 3.1 预处理：`STOP`、`tokenize`、`split_sentences`

```python
STOP = {"a", "an", "the", "is", "are", "was", "were", "of", "in", "on", "at",
        "to", "for", "with", "and", "or", "but", "this", "that", "by", "as"}


def tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
```

- **去停用词**是词重叠指标的必需品：不去掉的话，"the"、"was" 这类词会让任何两句话都有一定重叠。`STOP` 用集合存储，`t not in STOP` 是 O(1) 查找。
- `tokenize` 返回**列表**而不是集合，保留了重复词和顺序。faithfulness 用列表长度做分母（重复词会重复计数），answer relevance 自己再转成集合。
- `split_sentences` 的正则 `(?<=[.!?])\s+` 是**后行断言（lookbehind）**：匹配"前面紧挨着 `.`、`!` 或 `?` 的空白"，并在这里切分，标点留在句子里。"June 29, 2007." 里的逗号不会触发切分。
- ⚠️ 把"一句话"当作"一个 claim"是很粗的近似：讲义 Step 1 是让 LLM 把答案拆成**原子事实**，一句话里可能有好几个 claim（比如 "launched on June 29, 2006, shortly after the moon landing" 至少有两个）。另外 "Dr. Smith said…" 会在 "Dr." 后面被错误切开。

### 3.2 `faithfulness`：答案有没有"据"

```python
def faithfulness(answer, context):
    context_set = set(tokenize(context))
    claims = split_sentences(answer)
    if not claims:
        return 0.0
    supported = 0
    for claim in claims:
        claim_tokens = tokenize(claim)
        if not claim_tokens:
            continue
        overlap = sum(1 for t in claim_tokens if t in context_set)
        if overlap / len(claim_tokens) >= 0.5:
            supported += 1
    return supported / len(claims)
```

- 结构与讲义 Step 1 的生产版完全一致：**拆 claim → 逐条判断是否被上下文支持 → 支持比例**。唯一的区别是"是否支持"的判断：生产版用 NLI 模型的 entailment 概率 > 0.5，这里用"claim 中出现在上下文里的 token 比例 ≥ 0.5"。
- 上下文先转成集合，后面每次 `t in context_set` 都是 O(1)。
- 空答案返回 0.0（保守处理：没有内容就不算忠实）。
- ⚠️ 全是停用词的 claim 会被 `continue` 跳过，但**仍然计入分母** `len(claims)`，相当于被当作"不受支持"。比如答案开头多一句 "That is."（that、is 都是停用词），faithfulness 就从 1.0 掉到 0.5（已实际验证）。
- ⚠️ 最大的缺陷：**对关键事实不敏感**。case 1 把年份写成 2006，但这只是 10 个 token 里的 1 个，重叠比例 0.6 照样过线，faithfulness = 1.00。NLI 会直接判"矛盾"。

### 3.3 `answer_relevance`：答案是否切题

```python
def answer_relevance(question, answer):
    q_tokens = set(tokenize(question))
    a_tokens = set(tokenize(answer))
    if not q_tokens or not a_tokens:
        return 0.0
    return len(q_tokens & a_tokens) / len(q_tokens | a_tokens)
```

- 问题和答案的词集合 Jaccard。讲义 Step 2 的生产版是：让 LLM 根据答案反推 n 个问题，与真实问题做 embedding 余弦后取平均。
- ⚠️ Jaccard 的分母包含答案里所有**新词**，而一个好答案的价值恰恰在于提供问题里没有的信息（日期）。所以 case 0 的正确答案只有 0.43；只回答 "June 29, 2007." 会得 0 分；只复述问题的 "The first iPhone was released." 反而得 0.75。这是词面相关性最典型的反例。

### 3.4 `context_precision` 与 `context_recall`：检索的"准"与"全"

```python
def context_precision(retrieved_chunks, relevant_chunks):
    if not retrieved_chunks:
        return 0.0
    hits = sum(1 for c in retrieved_chunks if c in relevant_chunks)
    return hits / len(retrieved_chunks)


def context_recall(retrieved_chunks, gold_answer_tokens):
    retrieved_text = " ".join(retrieved_chunks)
    retrieved_set = set(tokenize(retrieved_text))
    if not gold_answer_tokens:
        return 0.0
    covered = sum(1 for t in gold_answer_tokens if t in retrieved_set)
    return covered / len(gold_answer_tokens)
```

- **precision** = 检索到的 chunk 中，有多少在人工标注的 `gold_relevant` 列表里。判断方式是字符串**完全相等**（`c in relevant_chunks` 是列表成员判断）。生产中没有现成的 gold 列表，由 judge 逐个判断 chunk 是否相关，RAGAS 的实现还会考虑相关 chunk 的排名位置。
- **recall** = 期望答案的 token 有多少能在检索文本中找到，近似"检索是否覆盖了回答所需的信息"。讲义的定义是"gold 答案的 claim 有多少被检索内容支持"，所以它**需要 gold 答案**。
- 两个函数都**只看检索，不看生成的答案**。这就是为什么 3 个 case 的 precision 都是 0.50、recall 都是 1.00：三者的检索质量一样（2 个 chunk 中 1 个相关，且都包含 june、29、2007），出问题的是生成器。
- ⚠️ `gold_answer_tokens` 是列表，重复 token 会重复计数；chunk 内容只要改一个空格就会被 precision 判成不相关。

### 3.5 `g_eval_correctness`：步骤化的正确性评估

```python
def g_eval_correctness(actual, expected, threshold=0.5):
    a_claims = split_sentences(actual)
    e_set = set(tokenize(expected))
    if not a_claims:
        return 0.0
    supported = 0
    for c in a_claims:
        c_tokens = tokenize(c)
        if not c_tokens:
            continue
        overlap = sum(1 for t in c_tokens if t in e_set) / len(c_tokens)
        if overlap >= threshold:
            supported += 1
    return supported / len(a_claims)
```

- 与 faithfulness 几乎一样，只是"参照物"从**检索上下文**换成了**期望答案**。这正对应讲义 Step 3 中 G-Eval 的 evaluation steps：读期望输出 → 读实际输出 → 列出 claim → 逐条标注是否被期望输出支持 → 分数 = 支持比例。
- `threshold` 做成参数（faithfulness 里写死了 0.5），体现了 G-Eval "评价标准可定制"的特点。
- ⚠️ 结果对措辞很脆弱：case 0 的答案有 6 个有效 token，命中 `june, 29, 2007` 正好 3 个，比例 0.5，**恰好踩线**通过；如果答案多一个词，比如 "The first Apple iPhone was released on June 29, 2007."，比例变成 3/7，correctness 直接变成 0。真正的 G-Eval 由 LLM 按步骤判断语义，不会因为多一个词就翻转。

### 3.6 `main`：3 个精心设计的 case

```python
    for i, case in enumerate(cases):
        ctx_joined = " ".join(case["context"])
        f = faithfulness(case["answer"], ctx_joined)
        r = answer_relevance(case["question"], case["answer"])
        cp = context_precision(case["context"], case["gold_relevant"])
        cr = context_recall(case["context"], tokenize(case["expected"]))
        ge = g_eval_correctness(case["answer"], case["expected"])
```

三个 case 的问题相同，各自代表一种典型情况：

| case | 设计意图 | 答案 |
|------|---------|------|
| 0 | 忠实且正确 | "The first iPhone was released on June 29, 2007." |
| 1 | 日期幻觉 + 混入无关上下文（登月） | "...launched on June 29, 2006, shortly after the moon landing." |
| 2 | 答非所问 | "Apple is a technology company based in Cupertino." |

- 每个 case 用字典存放 question / context / answer / expected / gold_relevant 五个字段，这与 DeepEval 的 `LLMTestCase(input, actual_output, expected_output, ...)` 和 RAGAS 的数据格式是同一个思路：**评测样本 = 结构化记录**。
- faithfulness 用拼接后的上下文；context_precision 用 chunk 列表，因为要逐个判断相关性。
- 末尾打印的"interpretation"是作者对预期结果的描述，但**与实际输出有出入**，见第 6 节。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库、词重叠 | 零依赖、无需 API key，几秒跑完，便于看清指标形状 | 抓不到数字幻觉，惩罚简洁的正确答案；生产中用 NLI 模型 + LLM judge |
| 一句话 = 一个 claim | 用正则即可实现 | 漏掉句内的多个事实；生产中用 LLM 拆原子 claim |
| faithfulness 阈值写死 0.5 | 对应 NLI "entailment 概率 > 0.5" 的直觉 | 阈值应在人工标注集上校准 |
| answer relevance 用 Jaccard | 最简单的"切题"度量 | 分母惩罚新信息；生产中用"反推问题 + embedding 余弦" |
| precision 用字符串精确匹配 gold 列表 | 离线回归集可以人工标注相关 chunk | 线上没有 gold 列表；生产中由 judge 判断相关性，并考虑排名 |
| G-Eval 用"claim 比对期望答案" | 直接对应讲义的 evaluation steps | 对措辞极敏感（3/6 过线、3/7 失败）；生产中由 LLM 按步骤判断语义 |
| 每个 case 打印全部 5 个指标 | 多指标对照，才能区分检索问题和生成问题 | 生产中还要汇总均值、最低 10%、按分层统计 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 集合字面量 | `STOP = {"a", "an", "the", ...}` | 花括号 + 元素；成员判断 O(1) |
| 带条件的列表推导式 | `[t for t in re.findall(...) if t not in STOP]` | 边遍历边过滤 |
| `re.findall` | `re.findall(r"[a-z0-9]+", text.lower())` | 返回所有匹配子串组成的列表 |
| `re.split` + 后行断言 | `re.split(r"(?<=[.!?])\s+", text)` | `(?<=...)` 只检查"前面是什么"，不消耗字符，所以标点保留在前一句 |
| `str.strip` / `str.join` | `s.strip()`；`" ".join(case["context"])` | 去首尾空白；用空格把列表拼成一个字符串 |
| `set()` 与集合运算 | `set(tokenize(question))`；`q_tokens & a_tokens`、`q_tokens | a_tokens` | 列表转集合去重；交集、并集 |
| 生成器表达式 + `sum` | `sum(1 for t in claim_tokens if t in context_set)` | 计数满足条件的元素，不建中间列表 |
| 卫语句（提前 return） | `if not claims: return 0.0` | 先处理边界情况，避免除零 |
| `continue` | `if not claim_tokens: continue` | 跳过本轮循环 |
| 列表成员判断 | `c in relevant_chunks` | 对列表是 O(n) 线性查找，按值相等比较 |
| 默认参数 | `def g_eval_correctness(actual, expected, threshold=0.5)` | 可选参数 |
| 列表里套字典 | `cases = [{"question": ..., "context": [...], ...}, ...]` | 结构化测试样本 |
| `enumerate` | `for i, case in enumerate(cases)` | 同时取下标和元素 |
| f-string 中的字典取值 | `f"case {i}: {case['question']}"` | 外层双引号、内层单引号，避免引号冲突 |
| f-string 格式说明符 | `{f:.2f}` | 保留 2 位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py`，输出如下（三个 case 的问题相同，下面省略了重复行）：

```text
=== toy RAG eval: faithfulness / relevance / context precision & recall / G-Eval ===

case 0: When was the first iPhone released?
  answer:   The first iPhone was released on June 29, 2007.
  expected: June 29, 2007
  faithfulness        = 1.00
  answer-relevance    = 0.43
  context-precision   = 0.50
  context-recall      = 1.00
  g-eval correctness  = 1.00

case 1: ...
  answer:   The first iPhone launched on June 29, 2006, shortly after the moon landing.
  faithfulness        = 1.00
  answer-relevance    = 0.17
  context-precision   = 0.50
  context-recall      = 1.00
  g-eval correctness  = 0.00

case 2: ...
  answer:   Apple is a technology company based in Cupertino.
  faithfulness        = 0.00
  answer-relevance    = 0.00
  context-precision   = 0.50
  context-recall      = 1.00
  g-eval correctness  = 0.00

interpretation:
  case 0 = faithful + correct      -> all metrics high
  case 1 = hallucinated date        -> g-eval drops, faithfulness partial
  case 2 = off-topic answer         -> relevance + g-eval collapse
```

逐项解读：

| case | 指标 | 数值 | 怎么来的 |
|------|------|------|---------|
| 0 | faithfulness | 1.00 | 6 个 token 全在上下文中 |
| 0 | answer-relevance | 0.43 | 交集 {first, iphone, released} = 3，并集 7 |
| 0 | g-eval | 1.00 | 命中 {june, 29, 2007}，3/6 = 0.5，**恰好踩线** |
| 1 | faithfulness | **1.00** | 10 个 token 中 6 个在上下文中（含 moon、landing），0.6 ≥ 0.5；错误年份没被发现 |
| 1 | answer-relevance | 0.17 | 交集 {first, iphone} = 2，并集 12 |
| 1 | g-eval | 0.00 | 只命中 june、29，2/10 = 0.2 |
| 2 | faithfulness | 0.00 | 5 个 token 只有 apple 在上下文中，1/5 |
| 2 | answer-relevance / g-eval | 0.00 | 与问题、期望答案都没有共同词 |
| 全部 | precision / recall | 0.50 / 1.00 | 检索都是"2 个 chunk 中 1 个相关，且覆盖了 june、29、2007"，与答案无关 |

关键观察：

1. **脚本自带的解读与实际输出不一致**：case 0 并非 "all metrics high"（relevance 0.43、precision 0.50）；case 1 的 faithfulness 是 1.00，不是 "partial"。这恰好证明了讲义的观点：词面近似抓不到数字幻觉，生产中必须用 NLI 或 judge。
2. **检索指标与生成指标解耦**：三个 case 的检索指标完全相同，生成指标差别很大，说明问题出在生成器。这就是多指标联合诊断的价值。
3. **case 1 中真正报警的只有 G-Eval**：因为它和期望答案比对。faithfulness 高、correctness 低，典型原因是生成器"编了一个和上下文表面相似的答案"。
4. **case 2 的 faithfulness = 0** 并不说明答案"错"（Apple 确实在 Cupertino），而是说明它没有依据检索内容作答。faithfulness 衡量的是 grounding，不是事实正确性。

---

## 7. 动手改一改

1. **修正解读文字**：根据实际输出重写 `interpretation` 的三行，或者让程序根据分数自动生成解读（如 `faithfulness >= 0.8` 才算 "high"）。
2. **数字一票否决**：给 `faithfulness` 加规则："claim 中含数字的 token 必须出现在上下文中"，验证 case 1 降到 0。
3. **汇总与尾部**：在 `main` 末尾计算每个指标的均值和最低分 case，模拟讲义要求的 "bottom quantile" 报告。
4. **校准练习**：自己给 10 个答案打 0/1 标签，计算 `g_eval_correctness` 与人工标签的 Spearman ρ（可以用 `scipy.stats.spearmanr`，也可以手写平均秩），看它是否达到 0.7。
5. **换成真 NLI**（需要自行安装 transformers 并下载模型）：按讲义 Step 1，用 DeBERTa MNLI 模型替换 `overlap / len(claim_tokens) >= 0.5` 这一行，对比 case 1 的 faithfulness。
6. **写成 CI 闸门**（需要 pytest）：把 3 个 case 改成 `test_` 函数，`assert faithfulness(...) >= 0.85`，故意改坏答案，观察测试失败。

---

## 8. 常见坑

- **把 faithfulness 当正确性**：faithfulness 只说明"有据可依"，上下文本身错了，或者答案与上下文表面相似但事实不同（case 1），它都可能给高分。必须搭配 correctness 或 context 指标一起看。
- **词面相关性惩罚好答案**：Jaccard 的分母会因新信息变大；简洁、正确、只给日期的答案可能得 0 分。
- **阈值踩线导致结果翻转**：3/6 = 0.5 刚好通过，多一个词就失败。任何"比例 ≥ 阈值"的离散判断都要检查边界附近的稳定性。
- **分母里混入被跳过的 claim**：`continue` 跳过的 claim 仍然计入 `len(claims)`，空句或纯停用词句会拉低分数。
- **只看均值**：3 个 case 的 faithfulness 均值是 0.67，看不出 case 1 是一个"高分幻觉"。一定要逐条看，尤其是看最差的那些。
- **相信脚本自带的解读**：输出的解释文字是作者写死的，应该以实际数字为准。评测报告也一样，不要让预期代替结果。
