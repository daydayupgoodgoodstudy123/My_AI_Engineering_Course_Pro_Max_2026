# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到高级 · 第 05 节 情绪分析 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，瞬间完成） ｜ **依赖**：仅 Python 标准库（`math`、`re`、`collections.Counter`），不需要 NumPy / scikit-learn

---

## 1. 这份代码在考察什么

这份脚本实现了一个最小但完整的情感分类流水线：**分词 → 否定作用域 → 多项式朴素贝叶斯 → 评估**。它想让你看清：

1. **朴素贝叶斯就是"数数 + 取对数 + 求和"**：先验、类条件词概率、拉普拉斯平滑，一共十几行。
2. **否定处理怎么做**：`NOT_` 前缀把 `good` 和 "被否定的 good" 变成两个不同的特征。
3. **为什么要在对数空间计算**：连乘小概率会下溢，log 把乘法变成加法。
4. **评估不能只看一个数**：脚本打印了逐条预测和混淆矩阵四格，你能亲眼看到 10 条训练样本的模型错在哪里。
5. **小数据 + 简单特征的真实表现**：5 条测试里错了 2 条，而且错因（停用词、OOV、否定处理的副作用）都值得逐一分析。

> 一句话：**这是情感分析的"Hello World"——每一个看似简单的环节，都藏着一个让生产系统翻车的坑。**

⚠️ 讲义 Step 3 的逻辑回归（`train_lr` / `predict_lr`）没有放进本脚本；本脚本只实现了朴素贝叶斯。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TOKEN_RE` / `tokenize` | 正则 + 函数 | 抽取单词（含内部撇号）和 `.!?,;` 五种标点，统一小写 | 分词 |
| `NEGATION_WORDS` / `NEGATION_TERMINATORS` | 集合常量 | 否定词表与"作用域终止符"表 | 否定作用域 |
| `apply_negation(tokens)` | 函数 | 否定词之后、下一个终止符之前的 token 加 `NOT_` 前缀 | 否定作用域 |
| `build_vocab(docs)` | 函数 | 收集所有 token 为一个**集合** | 词表 |
| `train_nb(docs_by_class, vocab, alpha=1.0)` | 函数 | 计算类先验和带平滑的 `P(w|c)` | 多项式 NB 训练 |
| `predict_nb(doc, class_priors, class_word_probs)` | 函数 | 对数先验 + 对数似然求和，取最大类 | NB 推断 |
| `evaluate(y_true, y_pred)` | 函数 | 以 `"+"` 为正类计算 tp/fp/fn/tn 与 P/R/F1 | 评估 |
| `main()` | 函数 | 5 正 5 负训练，5 条测试，打印逐条结果与指标 | 演示入口 |

数据流：`文本 → tokenize → apply_negation → (训练) build_vocab + train_nb → priors, word_probs`；`测试文本 → tokenize → apply_negation → predict_nb → 预测标签 → evaluate`。注意**训练和测试走的是同一套预处理函数**——这是第 01 节强调的"训练/推理一致"。

---

## 3. 逐段精讲

### 3.1 分词：这次保留了标点

```python
TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|[.!?,;]")


def tokenize(text):
    return [t.lower() for t in TOKEN_RE.findall(text)]
```

- 与第 02 节不同，这里**特意保留** `.!?,;` 五种标点：它们是否定作用域的终止符，丢掉了就不知道否定在哪里结束。
- 第一个分支会把 `wasn't`、`didn't` 整体匹配为一个 token——这一点在 3.2 中会引出一个 bug。
- 数字被丢弃（没有数字分支）。对影评来说影响不大，但"1/10"这类评分就丢了。

### 3.2 否定作用域：`NOT_` 前缀

```python
NEGATION_WORDS = {"not", "no", "never", "nor", "none", "nothing", "neither", "n't"}
NEGATION_TERMINATORS = {".", "!", "?", ",", ";"}


def apply_negation(tokens):
    out = []
    negate = False
    for token in tokens:
        if token in NEGATION_TERMINATORS:
            negate = False
            out.append(token)
            continue
        if token in NEGATION_WORDS:
            negate = True
            out.append(token)
            continue
        out.append(f"NOT_{token}" if negate else token)
    return out
```

- 这是一个只有一个布尔状态 `negate` 的**有限状态机**：遇到否定词 → 打开；遇到终止符 → 关闭；其余 token 在打开状态下加前缀。
- 否定词和终止符本身**不加前缀**，原样保留。
- 效果：`good` 与 `NOT_good` 成为两个独立特征，分类器可以给它们相反的权重。讲义称之为"Three lines of preprocessing, measurable accuracy jump"。
- 例：`["not", "good", "at", "all", ".", "but", "funny"]` → `['not', 'NOT_good', 'NOT_at', 'NOT_all', '.', 'but', 'funny']`。
- ⚠️ **一个真实的 bug**：`NEGATION_WORDS` 中的 `"n't"` 永远不会被命中。`tokenize` 会把 `wasn't` 整体切成一个 token，从不单独产生 `n't`（`n't` 是 Penn Treebank 风格 tokenizer 拆缩写的产物）。结果是 `didn't`、`wasn't`、`don't` 这些最常见的否定形式**完全不触发**否定作用域：

  ```text
  apply_negation(tokenize("this movie wasn't good"))
  → ['this', 'movie', "wasn't", 'good']
  ```

  修复：判断时加上 `token.endswith("n't")`（测验 Q9 有完整代码和测试）。
- ⚠️ 作用域是"到下一个标点"，`not good at all` 中的 `at`、`all` 也被加了前缀，制造出一堆稀疏的 `NOT_at`、`NOT_all` 特征；同时也会让训练中只以 `NOT_time` 形式出现过的 `time` 在测试时变成 OOV（见第 6 节）。

### 3.3 词表：用集合

```python
def build_vocab(docs):
    vocab = set()
    for doc in docs:
        for t in doc:
            vocab.add(t)
    return vocab
```

- 朴素贝叶斯不需要"词 → 下标"的映射（它用字典按词名存概率），所以集合就够了。本例词表大小 |V| = **44**（包含 `NOT_worth` 等带前缀的词和标点 `,`）。
- 词表在**训练集**上构建；测试时出现的新词不在其中，会在 `predict_nb` 中被跳过。

### 3.4 `train_nb`：先验 + 拉普拉斯平滑

```python
def train_nb(docs_by_class, vocab, alpha=1.0):
    class_priors = {}
    class_word_probs = {}
    total_docs = sum(len(d) for d in docs_by_class.values())
    for cls, docs in docs_by_class.items():
        class_priors[cls] = len(docs) / total_docs
        counts = Counter()
        for doc in docs:
            for token in doc:
                counts[token] += 1
        total = sum(counts.values()) + alpha * len(vocab)
        class_word_probs[cls] = {w: (counts[w] + alpha) / total for w in vocab}
    return class_priors, class_word_probs
```

- **输入格式** `{"+": [文档, ...], "-": [文档, ...]}`：按类别分组，一目了然；`len(d)` 是该类的**文档数**，`total_docs` 是总文档数。
- **先验** `P(c) = 该类文档数 / 总文档数`，这里正负各 5 条，都是 0.5。
- **类条件词概率**（多项式模型）：

  `P(w|c) = (count(w, c) + α) / (Σ_w' count(w', c) + α·|V|)`

  - `counts[w]` 对没出现过的词返回 0（`Counter` 的特性），所以分子至少是 α；
  - 分母加 `α·|V|` 保证该类所有词的概率加起来等于 1；
  - α = 1 是拉普拉斯平滑。讲义："`alpha=0.01` is common in practice. `alpha=1.0` is the teaching default."
- 本例：正类 26 个 token、负类 25 个 token，所以正类分母 70、负类分母 69。
- 字典推导式为**词表中每个词**都算一个概率，所以 `class_word_probs[cls]` 的键集合就是 `vocab`。
- ⚠️ 这是"多项式"NB：一个词在文档里出现几次就计几次。另一种"伯努利"NB 只看出现与否。

### 3.5 `predict_nb`：对数空间求和

```python
def predict_nb(doc, class_priors, class_word_probs):
    scores = {}
    for cls in class_priors:
        s = math.log(class_priors[cls])
        for token in doc:
            if token in class_word_probs[cls]:
                s += math.log(class_word_probs[cls][token])
        scores[cls] = s
    return max(scores, key=scores.get)
```

- 得分 = `log P(c) + Σ log P(wᵢ|c)`，即 `log[P(c)·∏P(wᵢ|c)]`。用 log 是为了避免连乘下溢；log 单调，不改变 argmax。
- 文档中出现几次的词就加几次（多项式模型的自然结果）。
- `if token in class_word_probs[cls]`：**跳过 OOV**。因为平滑只覆盖训练词表，没见过的词没有概率可查；跳过等价于"这个词对两类的似然比为 1"。
- `max(scores, key=scores.get)`：在字典的**键**中，按值最大者返回——一行实现 argmax。两类得分相同时返回先遍历到的那个类。
- 只返回标签，不返回概率。若要概率，可以对得分做 softmax（`exp(s_c) / Σ exp(s)`），但朴素贝叶斯的概率往往过度自信。

### 3.6 `evaluate`：只算了正类

```python
def evaluate(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == "+" and p == "+")
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == "-" and p == "+")
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == "+" and p == "-")
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == "-" and p == "-")
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}
```

- `sum(1 for ... if ...)` 是"计数满足条件的元素"的惯用写法。
- 每个除法都有 `if 分母 else 0` 保护，避免某一类一次都没预测时除零。
- ⚠️ 这里的 P/R/F1 只针对 `"+"` 类。讲义 Step 5 明确要求报告**每个类别**的 precision / recall 并取 macro 平均——本函数的输出会掩盖负类的表现（见第 6 节，负类 recall 只有 0.333）。测验 Q11 给出了 `macro_report` 的实现。

### 3.7 `main`：训练、预测、打印

```python
    train_pos = [apply_negation(tokenize(t)) for t in positive]
    train_neg = [apply_negation(tokenize(t)) for t in negative]

    vocab = build_vocab(train_pos + train_neg)
    priors, word_probs = train_nb({"+": train_pos, "-": train_neg}, vocab)

    test = [
        ("this movie was not good", "-"),
        ("loved every minute", "+"),
        ("terrible waste of time", "-"),
        ("beautiful and brilliant", "+"),
        ("i did not enjoy this at all", "-"),
    ]

    y_true = [label for _, label in test]
    y_pred = [predict_nb(apply_negation(tokenize(t)), priors, word_probs) for t, _ in test]
    for (text, actual), predicted in zip(test, y_pred):
        mark = "OK" if actual == predicted else "MISS"
        print(f"[{mark}] pred={predicted}  true={actual}  :: {text}")
```

- 训练语料就是讲义 Step 1 的 10 句话；讲义说"Small on purpose"。
- `train_pos + train_neg` 把两个列表拼接后建词表。
- `[label for _, label in test]` 用 `_` 丢掉不需要的文本，只取标签。
- `for (text, actual), predicted in zip(test, y_pred)`：`zip` 的每个元素是 `((text, label), pred)`，用**嵌套解包**一次拆开。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 朴素贝叶斯而非逻辑回归 | 只需计数，无需优化，最容易看懂 | 无法给 bigram 等相关特征合理分配权重；生产基线用 TF-IDF + 逻辑回归（讲义 Use It） |
| `NOT_` 否定作用域 | 没有 bigram 时的廉价否定处理 | 作用域粗糙；依赖 tokenizer 能识别否定词（本代码对 `n't` 缩写失效） |
| 保留标点作为终止符 | 否定作用域需要知道在哪里结束 | 引入了标点 token（如 `,`）进入词表 |
| α = 1 拉普拉斯平滑 | 教学默认，直观 | 实践中常用更小的 α（如 0.01），需调参 |
| 对数空间求和 | 防下溢 | 无 |
| OOV 直接跳过 | 实现简单 | 有信号的新词（如 `waste`）被丢弃；生产中靠更大的数据、subword 特征缓解 |
| 只报告正类指标 | 代码短 | 掩盖负类表现；生产中必须报告每类指标、macro-F1、混淆矩阵 |
| 10 条训练 + 5 条测试 | 演示用 | 结果偶然性极大；真实任务需数万条（IMDb、SST-2、Yelp） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 正则字符类 | `[.!?,;]` | 方括号内的 `.`、`?` 等不需要转义，表示字面字符 |
| 集合常量与成员判断 | `token in NEGATION_WORDS` | 集合的 `in` 平均 O(1) |
| `continue` | 否定词、终止符处理后 `continue` | 跳过本轮剩余代码 |
| 布尔状态变量 | `negate = False / True` | 用一个变量实现简单状态机 |
| 条件表达式 + f-string | `f"NOT_{token}" if negate else token` | 一行完成"条件加前缀" |
| `set()` 与 `add` | `vocab = set(); vocab.add(t)` | 空集合必须写 `set()`，`{}` 是空字典 |
| `collections.Counter` | `counts[token] += 1`；`counts[w]` | 缺失键默认 0，适合计数 |
| 生成器表达式求和 | `sum(len(d) for d in docs_by_class.values())` | 不建中间列表 |
| 字典推导式 | `{w: (counts[w] + alpha) / total for w in vocab}` | 一行建 "词 → 概率" 字典 |
| `dict.items()` / `.values()` | `for cls, docs in docs_by_class.items()` | 同时遍历键值 / 只遍历值 |
| `max` 配合 `key` | `max(scores, key=scores.get)` | 返回值最大的键，即 argmax |
| 计数惯用法 | `sum(1 for t, p in zip(...) if ...)` | 统计满足条件的元素个数 |
| 布尔值求和 | （测验 Q11）`sum(t == p for ...)` | `True` 当作 1 参与求和 |
| `round` | `round(precision, 3)` | 保留 3 位小数 |
| 嵌套解包 | `for (text, actual), predicted in zip(test, y_pred)` | 一次拆开嵌套元组 |
| `_` 占位 | `[label for _, label in test]` | 丢弃不需要的值 |
| 列表拼接 | `train_pos + train_neg` | 返回新列表 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，纯标准库）的完整输出：

```text
[MISS] pred=+  true=-  :: this movie was not good
[OK] pred=+  true=+  :: loved every minute
[MISS] pred=+  true=-  :: terrible waste of time
[OK] pred=+  true=+  :: beautiful and brilliant
[OK] pred=-  true=-  :: i did not enjoy this at all

metrics: {'tp': 2, 'fp': 2, 'tn': 1, 'fn': 0, 'precision': 0.5, 'recall': 1.0, 'f1': 0.667}
```

逐条解读（以下得分均为实测）：

- **`this movie was not good` → 判错**：处理后为 `['this', 'movie', 'was', 'not', 'NOT_good']`。`was`、`NOT_good` 都不在词表（训练语料里根本没有 `good`），只剩 `this`、`movie`（都来自正类句 "absolutely loved this movie"）和 `not`（来自负类）。两个"正面"的中性词压过了一个否定词：正类 −12.05 vs 负类 −12.70。
- **`loved every minute` / `beautiful and brilliant` → 判对**：`loved`、`beautiful`、`brilliant` 都只在正类出现。
- **`terrible waste of time` → 判错**：`waste` 是 OOV；`time` 在训练中只以 `NOT_time`（来自 "not worth your time"）出现，所以也是 OOV；只剩 `terrible`（负类 1 次）和 `of`（正类 2 次）。手算：正类 `log 0.5 + log(1/70) + log(3/70) = −8.092`，负类 `log 0.5 + log(2/69) + log(1/69) = −8.468`，正类胜出。一个**停用词**决定了结果（详见测验 Q10）。
- **`i did not enjoy this at all` → 判对**：处理后 `this`、`at`、`all` 都被加了 `NOT_` 前缀成为 OOV；真正起作用的是 `i`（只在负类 "i want my two hours back" 中出现）和 `not`。判对了，但理由并不"正当"。
- **metrics**：正类 precision 0.5（预测为正的 4 条中只有 2 条对）、recall 1.0（2 条正面全抓到），F1 0.667。但这只是正类的视角；负类实际上 precision 1.0、recall 0.333、F1 0.5，macro-F1 ≈ 0.583，accuracy 0.6。模型明显偏向判正——这一点只有看完整的混淆矩阵或逐类指标才能发现。

额外实验：`apply_negation(tokenize("this movie wasn't good"))` 得到 `['this', 'movie', "wasn't", 'good']`，否定作用域完全没有生效（3.2 中的 bug）。

---

## 7. 动手改一改

1. **（易）修复缩写否定**：给否定判断加上 `token.endswith("n't")`，验证 `wasn't good` 变成 `["wasn't", "NOT_good"]`。
2. **（易）逐类指标**：写 `macro_report`，输出两类各自的 P/R/F1、macro-F1 和混淆矩阵（测验 Q11）。
3. **（中）消融实验**：分别在"有 / 无 `apply_negation`"、"α = 1 / α = 0.01"下重跑，观察 5 条测试的预测与各类得分的变化。
4. **（中）输出概率与解释**：让 `predict_nb` 同时返回 softmax 归一化后的概率，以及对决策贡献最大的 3 个词（`log P(w|+) − log P(w|−)` 绝对值最大者）。
5. **（中）加入 bigram 特征**：把每篇文档的相邻词对拼成 `w1_w2` 加入 token 列表，对比与 `NOT_` 前缀的效果。
6. **（难）逻辑回归对照**：用 NumPy 实现讲义的 `train_lr`（含 L2），在 BoW 特征上训练，与朴素贝叶斯比较；如果环境里有 scikit-learn，再用讲义的 `Pipeline` 跑一遍。

---

## 8. 常见坑

- **组件约定不一致**：否定词表里写 `n't`，但 tokenizer 从不产生 `n't`——各自看都对，拼在一起就失效，而且不会报错。
- **忘了平滑**：类内未出现过的词概率为 0，`math.log(0)` 直接抛 `ValueError: math domain error`。
- **概率直接连乘**：长文档会下溢为 0，所有类别得分相同。
- **只看正类 F1 或 accuracy**：本例正类 F1 = 0.667 看着还行，负类 recall 只有 0.333。
- **以为 OOV 会"按中性处理"就没事**：有信号的新词被丢掉后，决策可能被停用词左右（`terrible waste of time` 就是这样被判错的）。
- **训练和推理预处理不一致**：如果训练时用了 `apply_negation`、推理时忘了，`NOT_xxx` 特征全部失效。本代码在两处都调用了同一个函数，这是正确做法。
