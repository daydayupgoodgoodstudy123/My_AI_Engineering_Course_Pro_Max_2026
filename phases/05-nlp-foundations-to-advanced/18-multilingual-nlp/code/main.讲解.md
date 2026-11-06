# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 18 节 多语言自然语言处理 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 内置功能（没有任何 `import`）；讲义中的 XLM-R 零样本分类、多语言句向量、少样本微调需要 `transformers` / `sentence-transformers` / `datasets` / `torch`，本文件没有用到

---

## 1. 这份代码在考察什么

讲义说多语言 NLP 里"最容易绊倒新团队的一个决定"是**选哪种语言作为微调的源语言**。这份代码只做这一件事，用最小的玩具把思路演示清楚：

1. **语言相似度**：用 3 个类型学特征（语序、文字、语系）的匹配比例，模拟 qWALS / lang2vec 这类基于 WALS 特征的相似度。
2. **源语言排序**：对给定目标语言，把所有候选按相似度降序排列——"语言相似度比语料规模更能预测迁移效果"。
3. **迁移效果示意**：用一个手写的线性函数把相似度映射成"模拟准确率"，让"越相似、迁移越好"这个**趋势**看得见。
4. **核心结论**：对马拉地语，印地语是比英语更好的源语言。

> 一句话：**不要默认英语**——先找类型学上最近的高资源亲属语言，再与英语对比。代码里的数字是示意，结论要靠真实实验验证。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `LANGUAGE_FEATURES` | 常量字典 | 11 种语言 × 3 个特征（`word_order`、`script`、`family`） | WALS 类型学特征（极简版） |
| `similarity(a, b)` | 函数 | 两种语言特征相同的个数 / 特征总数 | 语言相似度（qWALS 风格） |
| `rank_source_languages(target, candidates)` | 函数 | 去掉目标自身，按相似度降序排列候选 | 源语言选择（LANGRANK 思路） |
| `simulate_transfer_accuracy(target, source)` | 函数 | `min(0.95, 0.45 + sim × 0.45)` | 迁移效果示意（非预测） |
| `main()` | 函数 | 对 4 个目标语言各打印 top-4 源语言 | — |

调用关系：`main` → `rank_source_languages` → `similarity`；对每个排名结果再调用 `simulate_transfer_accuracy`（它内部又调用一次 `similarity`）。

---

## 3. 逐段精讲

### 3.1 特征表：一个嵌套字典

```python
LANGUAGE_FEATURES = {
    "english":  {"word_order": "SVO", "script": "Latin",   "family": "Germanic"},
    "german":   {"word_order": "SVO", "script": "Latin",   "family": "Germanic"},
    # ...
    "hindi":    {"word_order": "SOV", "script": "Devanagari", "family": "Indic"},
    "marathi":  {"word_order": "SOV", "script": "Devanagari", "family": "Indic"},
    "bengali":  {"word_order": "SOV", "script": "Bengali",    "family": "Indic"},
    "urdu":     {"word_order": "SOV", "script": "Arabic",     "family": "Indic"},
    "arabic":   {"word_order": "VSO", "script": "Arabic",     "family": "Semitic"},
    "japanese": {"word_order": "SOV", "script": "Kanji",      "family": "Japonic"},
}
```

- 外层键是语言名，内层是"特征名 → 取值"。这是**用数据表达知识**的典型写法：新增语言只需加一行，不用改函数。
- 三个特征各自对应迁移时的不同因素：
  - `word_order`（语序）：SVO / SOV / VSO，影响句法结构；
  - `script`（文字）：同文字的语言共享更多子词，直接影响共享词表的"锚点"数量；
  - `family`（语系 / 语支）：反映词汇、形态上的亲缘关系。
- 一些有意思的组合：乌尔都语与印地语口语上非常接近，但文字不同（阿拉伯字母 vs 天城文）；乌尔都语与阿拉伯语文字相同但语系不同。
- ⚠️ 极度简化：真实的 WALS 有上百个特征；日语实际上混用汉字和假名，这里只标 `Kanji`；英语和德语的语序在细节上也不完全相同。代码最后一行打印的 note 也承认这是"3 特征的玩具"。

### 3.2 `similarity`：匹配比例

```python
def similarity(a, b):
    fa = LANGUAGE_FEATURES[a]
    fb = LANGUAGE_FEATURES[b]
    matches = sum(1 for k in fa if fa[k] == fb[k])
    return matches / len(fa)
```

- `for k in fa` 遍历字典的**键**（三个特征名）；`sum(1 for ... if ...)` 是"数一数满足条件的有几个"的惯用写法。
- 结果只可能是 0、1/3、2/3、1。例如马拉地语 vs 印地语三项全同 → 1.0；马拉地语 vs 孟加拉语只差文字 → 0.67；马拉地语 vs 英语全不同 → 0.0。
- 它是对称的：`similarity(a, b) == similarity(b, a)`。
- ⚠️ **等权、精确匹配**：文字是否相同和语序是否相同同样只算 1 分；`SOV` 与 `SVO` 没有"部分相似"。
- ⚠️ 没有处理未知语言：`similarity("korean", "english")` 直接抛 `KeyError: 'korean'`。

### 3.3 `rank_source_languages`：过滤 + 排序

```python
def rank_source_languages(target, candidates):
    scored = [(cand, similarity(target, cand)) for cand in candidates if cand != target]
    scored.sort(key=lambda x: -x[1])
    return scored
```

- 列表推导式里的 `if cand != target` 把目标语言自己排除——拿马拉地语做马拉地语的源语言没有意义。
- `key=lambda x: -x[1]`：按元组第 2 项（相似度）取负，实现降序。
- **稳定排序**：Python 的 `sort` 是稳定的，相似度相同时保持原来的顺序，即 `LANGUAGE_FEATURES` 的插入顺序（Python 3.7+ 字典保证插入顺序）。所以同为 0.67 时，`bengali` 排在 `urdu` 前面，并不是因为它"更好"。
- 这就是 LANGRANK 思路的最小骨架：给候选打分 → 排序 → 取前几名去做真实实验。真实的 LANGRANK 还会综合语料规模、谱系关系等多个因素。

### 3.4 `simulate_transfer_accuracy`：示意函数

```python
def simulate_transfer_accuracy(target, source):
    sim = similarity(target, source)
    base_accuracy = 0.45
    max_boost = 0.45
    return min(0.95, base_accuracy + sim * max_boost)
```

- 线性映射：相似度 0 → 45%，相似度 1 → 90%。两个常数都是为了演示而设，**没有任何实验依据**。
- 可能的输出只有 45%、60%、75%、90% 四档。
- ⚠️ `min(0.95, ...)` 在当前参数下**永远不会生效**（最大值 0.90 < 0.95）；它只是在有人把 `max_boost` 调大时防止"准确率"超过 95% 的保护。
- 正确的理解：它只是把"相似度高 → 迁移效果好"的**方向**画出来。真实的迁移效果还受预训练语料中各语言的数据量、分词覆盖（"分词税"）、任务类型、领域等影响，必须实测（讲义练习 3）。

### 3.5 `main`：四个精心挑选的目标语言

```python
    candidates = list(LANGUAGE_FEATURES)
    targets = ["marathi", "urdu", "arabic", "japanese"]
    # ...
        ranking = rank_source_languages(target, candidates)[:4]
        # ...
            print(f"    source={source:10s}  sim={sim:.2f}  simulated_acc={expected:.0%}")
```

- `list(LANGUAGE_FEATURES)` 得到所有键（语言名）组成的列表。
- 四个目标各有看点：
  - **马拉地语**：有一个三项全同的"近亲"印地语 → 讲义的核心案例；
  - **乌尔都语**：印地语、马拉地语、孟加拉语并列 0.67——同语支但文字不同，说明 3 个特征分辨率不够；
  - **阿拉伯语**：唯一的部分匹配是同文字的乌尔都语（0.33），其他全是 0——在这个特征表里阿拉伯语没有"亲戚"；
  - **日语**：top-4 全是印度语言，只因为都是 SOV——**玩具相似度最容易误导的例子**。
- 格式符：`{source:10s}` 左对齐占 10 格；`{sim:.2f}` 两位小数；`{expected:.0%}` 把 0.9 格式化成 `90%`（乘 100、0 位小数、加百分号）。
- 最后两行 `print` 是写死的说明文字：真实相似度来自 qWALS / lang2vec；关键结论是"马拉地语用印地语做源语言优于英语"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 3 个人工特征 | 一眼能看懂"相似"指什么 | 分辨率太低、出现日语 → 印地语这类误导；生产用 lang2vec / WALS 的上百维特征向量 |
| 等权精确匹配 | 公式最简单 | 文字、语序、语系重要性不同；可以加权，权重从迁移实验中回归得到 |
| 数据与逻辑分离（特征放字典） | 加语言不用改代码 | 缺失语言直接 `KeyError`，需要校验 |
| 线性"模拟准确率" | 让趋势可视化 | 不能当预测；真实决策靠在候选源语言上实测 |
| 稳定排序决定并列顺序 | 结果可复现 | 并列名次带有偶然性，报告时应注明并列 |
| 零依赖 | 无需 GPU / 模型即可运行 | 讲义中真正的跨语言迁移（XLM-R、句向量）需要 transformers 等库 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 嵌套字典字面量 | `{"english": {"word_order": "SVO", ...}, ...}` | 字典的值也可以是字典，适合表达"实体 → 属性" |
| 字典按键访问 | `LANGUAGE_FEATURES[a]` | 键不存在时抛 `KeyError` |
| 遍历字典的键 | `for k in fa` | 直接遍历字典得到的是键 |
| `sum` + 带条件的生成器 | `sum(1 for k in fa if fa[k] == fb[k])` | 计数满足条件的元素个数 |
| `len` 用于字典 | `len(fa)` | 字典的键数量 |
| 列表推导式 + 过滤 | `[(cand, similarity(target, cand)) for cand in candidates if cand != target]` | 一行完成映射与过滤 |
| `list.sort(key=...)` | `scored.sort(key=lambda x: -x[1])` | 按自定义键原地排序；Python 排序是稳定的 |
| `lambda` | `lambda x: -x[1]` | 匿名函数，取元组第 2 项的相反数 |
| `min` | `min(0.95, base_accuracy + sim * max_boost)` | 取较小值，实现上限截断 |
| `list(dict)` | `list(LANGUAGE_FEATURES)` | 得到键的列表（保持插入顺序） |
| 切片 | `rank_source_languages(...)[:4]` | 取前 4 个 |
| 元组解包 | `for source, sim in ranking` | 每个元素是 `(语言, 相似度)` |
| f-string 格式符 | `{source:10s}`、`{sim:.2f}`、`{expected:.0%}`、`f"\n  target: {target}"` | 宽度对齐；两位小数；百分比格式；`\n` 换行 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13）输出：

```text
=== source language selection (qWALS-style similarity) ===

  target: marathi
    source=hindi       sim=1.00  simulated_acc=90%
    source=bengali     sim=0.67  simulated_acc=75%
    source=urdu        sim=0.67  simulated_acc=75%
    source=japanese    sim=0.33  simulated_acc=60%

  target: urdu
    source=hindi       sim=0.67  simulated_acc=75%
    source=marathi     sim=0.67  simulated_acc=75%
    source=bengali     sim=0.67  simulated_acc=75%
    source=arabic      sim=0.33  simulated_acc=60%

  target: arabic
    source=urdu        sim=0.33  simulated_acc=60%
    source=english     sim=0.00  simulated_acc=45%
    source=german      sim=0.00  simulated_acc=45%
    source=french      sim=0.00  simulated_acc=45%

  target: japanese
    source=hindi       sim=0.33  simulated_acc=60%
    source=marathi     sim=0.33  simulated_acc=60%
    source=bengali     sim=0.33  simulated_acc=60%
    source=urdu        sim=0.33  simulated_acc=60%

note: real similarity comes from qWALS / lang2vec, not a 3-feature toy.
key insight: for Marathi, Hindi is a better source than English.
```

- **marathi**：印地语三项全同（SOV、天城文、印度语支）→ 1.00，模拟 90%；英语相似度为 0，连前 4 都没进。这就是讲义的核心论点："对印度语目标，印地语常常胜过英语。"
- **urdu**：印地语、马拉地语、孟加拉语都是 0.67（同语序、同语支、不同文字），三者并列，排序只是字典插入顺序；阿拉伯语因为同文字得 0.33。现实中乌尔都语和印地语口语高度互通，3 个特征无法体现这种"非常近"。
- **arabic**：只有同文字的乌尔都语得分；第 2–4 名都是 0 分，只是按插入顺序列出的英语、德语、法语——**0 分的"推荐"没有任何信息量**。
- **japanese**：四个印度语言并列 0.33，仅因为都是 SOV。语言学上，用印地语作为日语的源语言没有依据；这正是"特征太少 + 等权"会产生的误导，代码的 note 也提醒了这一点。
- 所有 `simulated_acc` 都只是 `0.45 + sim × 0.45` 的直接换算，不含任何实验信息。

---

## 7. 动手改一改

1. **加权相似度**：给 `script` 和 `family` 更高权重（如 2:2:1），观察乌尔都语的排序如何变化。
2. **加特征**：加入 `morphology`（如 fusional / agglutinative），日语和韩语都是黏着语，看看能否让日语的推荐更合理（需要先在表里加入韩语）。
3. **健壮性**：对未知语言抛出带说明的 `ValueError`，而不是 `KeyError`；对并列名次在输出中标注 "(tie)"。
4. **过滤零分**：`rank_source_languages` 只返回相似度 > 0 的候选，没有合适源语言时提示"回退到英语 / 做少样本标注"。
5. **测生育率**：写 `byte_fertility(text)`（UTF-8 字节数 / 词数），比较英语、印地语、中文句子，体会讲义的"分词税"。
6. **真实实验**（需要 GPU 与 `transformers`）：按讲义练习 3，在 500 条印地语数据上比较英语源与印地语源的微调效果，再回来看这份玩具排序是否预测对了方向。

---

## 8. 常见坑

- **把 `simulated_acc` 当成预测**：它是手写的线性函数，只表达趋势。
- **把并列名次当成排序结论**：稳定排序下，并列项的先后只由字典插入顺序决定。
- **0 分的候选也被"推荐"**：前 4 名里出现相似度 0 的语言，说明特征表里根本没有合适的源语言。
- **特征过少导致荒谬结论**：日语 → 印地语就是例子；类型学相似度要用足够多的特征。
- **未知语言直接崩溃**：查字典前先校验，或用 `.get()` 给出明确错误。
- **只看相似度不看资源量**：一个极相似但几乎没有标注数据的语言，未必是好的源语言；LANGRANK 一类方法会把语料规模也纳入考虑。
