# 测验 · 情绪分析（Sentiment Analysis）

> **阶段 05 · NLP 基础到高级 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 情感分析为什么难 | 否定翻转含义、反讽颠倒含义、"Not bad at all" 是正面、emoji 信号强、同一个词在不同领域极性不同（`tight`） |
| 2 | 经典两步法 | **表示**（BoW / TF-IDF / n-gram）+ **分类**（朴素贝叶斯、逻辑回归、SVM 等线性模型） |
| 3 | 多项式朴素贝叶斯 | `argmax_c [log P(c) + Σ log P(wᵢ|c)]`，P(w|c) 由类内词频估计；在对数空间求和防止下溢 |
| 4 | 拉普拉斯平滑 | `P(w|c) = (count(w,c) + α) / (Σcount(c) + α·|V|)`；不平滑时类内没出现过的词概率为 0，log 爆炸 |
| 5 | NB 为什么"笨但有效" | 独立性假设明显错误，但稀疏文本 + 中等数据量下，分类只需要知道"每个词偏向哪一边" |
| 6 | 逻辑回归 + L2 | 判别式模型，每个特征一个可正可负的权重（`not good` 的 bigram 可以得到负权重）；稀疏高维特征必须加 L2 防止记住训练样本 |
| 7 | 否定处理 | 用 bigram（`not_good`），或"否定作用域"：否定词之后、下一个标点之前的词都加 `NOT_` 前缀 |
| 8 | 评估指标 | 分类别的 precision / recall、macro-F1（不平衡时的主指标）、混淆矩阵、逐类读错例；极度不平衡（> 95:5）用 AUROC / AUPRC；别用 micro-F1 / accuracy 糊弄 |
| 9 | 生产基线配置 | `TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, stop_words=None)` + `LogisticRegression`；保留停用词才能保留否定词 |
| 10 | 何时上 Transformer | 反讽、长文中情感转折、方面级情感（aspect-based）、低资源语言；比较模型时必须在**同一流水线**上重跑基线 |

### 核心技能（能动手做到）

- [ ] 从零实现带拉普拉斯平滑的多项式朴素贝叶斯（`train_nb` / `predict_nb`），并能手算某个词在某类下的平滑概率
- [ ] 能手算一条测试句子在两个类别下的对数得分，解释模型为什么判对或判错
- [ ] 实现 `apply_negation` 否定作用域，并修复它对 `didn't`、`wasn't` 这类缩写失效的问题
- [ ] 能为二分类写出**两个类别各自**的 precision / recall / F1、macro-F1 与混淆矩阵，而不只是正类指标
- [ ] 能用 NumPy 从零写出带 L2 的逻辑回归梯度下降，并说明 L2 项在梯度里的位置
- [ ] 能用 scikit-learn `Pipeline` 搭出讲义中的生产基线，并解释三个关键参数各自的作用
- [ ] 能判断一个情感需求（反讽、方面级、多语言）是否超出经典模型的能力范围

---

## 二、基础自测（选择题）

**Q1.** 本节 `main.py` 中，正类训练语料共 26 个 token，词表大小 |V| = 44，α = 1。词 `terrible` 在正类中从未出现，它的平滑概率 `P(terrible | +)` 是：

- A. 0
- B. 1/26
- C. 1/70
- D. 1/44

**Q2.** 朴素贝叶斯预测时把 `log P(w|c)` 相加，而不是把 `P(w|c)` 相乘，主要原因是：

- A. 对数运算更快
- B. 很多个小于 1 的概率连乘会迅速下溢成 0；取对数把乘法变成加法，数值稳定且不改变 argmax
- C. 为了让结果变成正数
- D. 取对数后就不需要平滑了

**Q3.** `apply_negation(["not", "good", "at", "all", ".", "but", "funny"])` 的输出是：

- A. `['not', 'NOT_good', 'at', 'all', '.', 'but', 'funny']`
- B. `['NOT_not', 'NOT_good', 'NOT_at', 'NOT_all', '.', 'NOT_but', 'NOT_funny']`
- C. `['not', 'NOT_good', 'NOT_at', 'NOT_all', '.', 'but', 'funny']`
- D. `['not', 'NOT_good', 'NOT_at', 'NOT_all', 'NOT_.', 'NOT_but', 'NOT_funny']`

**Q4.** 某情感数据集 90% 正面、10% 负面。一个"永远预测正面"的分类器，其 accuracy 和 macro-F1 分别约为：

- A. 0.90 和 0.90
- B. 0.90 和 0.95
- C. 0.90 和 0.47
- D. 0.10 和 0.00

**Q5.** 讲义强调对文本做逻辑回归时 L2 正则"很重要"，最主要的原因是：

- A. L2 能加速矩阵求逆
- B. 文本特征稀疏且维度极高，很多特征只在一两个样本中出现，不加约束时模型会给它们巨大权重、记住训练样本
- C. 没有 L2 无法计算梯度
- D. L2 能把稀疏特征变成稠密特征

**Q6.** 下面哪个 `TfidfVectorizer` 配置最符合讲义给出的情感分析生产基线？

- A. `TfidfVectorizer(stop_words="english")`
- B. `TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, stop_words=None)`
- C. `TfidfVectorizer(ngram_range=(3, 5), max_df=0.1)`
- D. `TfidfVectorizer(ngram_range=(1, 1), stop_words="english", sublinear_tf=False)`

**Q7.** 以下哪个需求，讲义认为经典 TF-IDF + 线性模型**基本做不了**，需要上 Transformer 或结构化输出模型？

- A. 判断一条短评是正面还是负面
- B. 对 "Camera was great but battery was terrible." 分别给出"相机：正面""电池：负面"
- C. 需要在微秒级完成分类
- D. 需要解释是哪些词导致了预测

**Q8.** 你训练了一个新模型，准确率比某论文报告的基线高 3 个点。讲义建议你下一步应该：

- A. 直接写进报告，3 个点很显著
- B. 换一个随机种子再跑一次，取高的那次
- C. 用**你自己的**数据划分、预处理和 tokenizer 重新跑一遍基线，再比较差距
- D. 只比较 F1，不比较 accuracy 就可以了

---

## 三、动手 / 代码题

**Q9.** 本节代码的否定词表是：

```python
TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|[.!?,;]")

NEGATION_WORDS = {"not", "no", "never", "nor", "none", "nothing", "neither", "n't"}
```

(1) 写出 `apply_negation(tokenize("this movie wasn't good"))` 的结果。
(2) 词表里明明写了 `"n't"`，为什么 `wasn't` 后面的 `good` 没有被加上 `NOT_` 前缀？
(3) 给出一个修复方案（代码），并验证 `"I didn't like it, but the ending was good!"` 的处理结果。

**Q10.** 运行 `main.py`，测试句 `"terrible waste of time"`（真实标签为负）被判成了正面：

```text
[MISS] pred=+  true=-  :: terrible waste of time
```

已知：正类 26 个 token、负类 25 个 token、|V| = 44、α = 1，两类先验都是 0.5；训练语料中 `terrible` 只在负类出现 1 次，`of` 只在正类出现 2 次（"one **of** the best films **of** the year"），负类训练句 "not worth your time" 经过否定处理后变成 `['not', 'NOT_worth', 'NOT_your', 'NOT_time']`。

请手算两个类别的对数得分，解释为什么判错，并指出这个例子暴露了哪些问题。

**Q11.** 本节的 `evaluate` 只计算了正类（`"+"`）的 precision / recall / F1。请写一个 `macro_report(y_true, y_pred, labels=("+", "-"))`，输出每个类别的 P / R / F1、macro-F1、accuracy 和混淆矩阵，并给出它在 `main.py` 这次运行结果（`y_true = ['-', '+', '-', '+', '-']`，`y_pred = ['+', '+', '+', '+', '-']`）上的输出。对比 `evaluate` 给出的 `f1: 0.667`，你能得出什么结论？

---

## 四、面试高频题

**Q12.**（基础必考）文本分类中，朴素贝叶斯和逻辑回归有什么区别？分别在什么情况下更好？

**Q13.**（原理深挖）朴素贝叶斯的条件独立假设在文本上显然不成立，为什么它的分类效果还不错？这个错误假设会带来什么副作用？

**Q14.**（工程实践）情感分类上线后，产品经理只看 accuracy。数据是 85% 正面、15% 负面，而业务最关心的是"抓住负面评论"。你会怎么设计评估方案和决策阈值？

**Q15.**（场景设计）为一个电商平台设计评论情感分析系统：日均 100 万条评论，要求 P99 延迟 < 10ms，同时运营希望知道"用户对物流、质量、客服分别是什么态度"。你怎么设计？

**Q16.**（追问型）面试官追问："'Not bad at all' 和 'Oh great, another two-hour wait' 这两句，你的 TF-IDF + 逻辑回归 + 否定处理能判对吗？为什么？"

---

## 五、参考答案与解析

### Q1 — 答案：C

`P(terrible | +) = (0 + 1) / (26 + 1 × 44) = 1/70`。分母要加 `α·|V|`，保证该类下所有词的平滑概率之和仍为 1。A 是不平滑时的结果（log 会变成 -∞）；B 忘了分母加 `α·|V|`；D 把分母写成了词表大小。

### Q2 — 答案：B

一篇几百个词的文档，每个 `P(w|c)` 都在 1e-3 量级，连乘后远小于浮点数能表示的最小正数，结果下溢为 0，所有类别都变成 0、无法比较。log 是单调递增函数，`argmax` 不变，而乘法变加法后数值稳定。D 错：取对数后，零概率会变成 `log(0) = -∞`，更需要平滑。

### Q3 — 答案：C

否定词 `not` 本身原样保留并开启否定状态；之后的 `good`、`at`、`all` 都加上 `NOT_` 前缀；遇到终止符 `.` 时关闭否定状态，`.` 原样保留；`but`、`funny` 不再受影响。与讲义示例一致。注意否定作用域是"到下一个标点为止"，所以 `at`、`all` 这样的无关词也会被加前缀——这是这种粗糙方法的代价。

### Q4 — 答案：C

- accuracy = 90/100 = 0.90；
- 正类：precision = 0.9，recall = 1.0，F1 = 2×0.9×1.0/1.9 ≈ 0.947；
- 负类：一次都没预测，recall = 0，F1 = 0；
- macro-F1 = (0.947 + 0) / 2 ≈ **0.474**（已用 scikit-learn 验证）。

而 micro-F1 在单标签分类中等于 accuracy，也是 0.90——这就是讲义说的"常见 bug"：micro-F1 被多数类主导，看上去很高。macro-F1 让少数类的失败无处可藏。

### Q5 — 答案：B

文本特征维度动辄数万，且大多数特征只在极少数样本中出现。如果某个稀有词恰好只出现在一个正样本里，无约束的逻辑回归会不断增大它的权重来"完美"拟合这个样本——这就是记忆。L2 在损失中加上 `λ·Σw²`，梯度里对应 `+ l2 * w`（见讲义 `train_lr`），持续把权重往 0 拉。讲义建议从 `0.01` 开始调。

### Q6 — 答案：B

讲义 Use It 的三个关键点：`stop_words=None` 保留否定词；`ngram_range=(1, 2)` 让 `not good` 成为特征；`sublinear_tf=True` 抑制重复词。`min_df=2` 去掉只出现一次的噪声词。A、D 会删掉 `not`；C 只用 3–5 元语法、并把出现在 10% 以上文档中的词全部删掉，会丢失大量核心情感词。

### Q7 — 答案：B

这是**方面级情感分析**（aspect-based sentiment）：需要把情感归属到具体的方面（相机、电池）。讲义："You need to attribute sentiment to aspects. Transformers or structured output models only." 句子级的 BoW 分类器只能给整句一个标签。C、D 恰恰是经典模型的优势场景。

### Q8 — 答案：C

讲义 "The reproducibility trap"：论文中的数字依赖特定的数据划分、预处理、tokenizer；用你的流水线和论文的数字比较，得到的差值可能完全来自流水线差异。"Always regenerate the baseline on your pipeline, not the paper's number." B 是典型的"挑种子"作弊；D 不解决流水线不一致的问题。

### Q9 — 参考答案

**(1)** 实测输出：

```text
['this', 'movie', "wasn't", 'good']
```

没有任何 `NOT_` 前缀。

**(2)** tokenizer 的第一个分支 `[A-Za-z]+(?:'[A-Za-z]+)?` 会把 `wasn't` 整体匹配成**一个** token（`wasn` + `'t`），永远不会单独产生 `n't` 这个 token。于是 `NEGATION_WORDS` 中的 `"n't"` 是一个永远不会被命中的"死条目"，而 `wasn't`、`didn't`、`don't`、`isn't` 等最常见的英文否定形式都不在集合里，否定作用域根本不会开启。（`n't` 是 NLTK 等 Penn Treebank 风格 tokenizer 拆分缩写时的产物，与本节的正则 tokenizer 不匹配——这是"组件之间约定不一致"的典型 bug。）

**(3)** 修复思路：判断否定词时，同时识别以 `n't` 结尾的缩写。

```python
def is_negation(token):
    return token in NEGATION_WORDS or token.endswith("n't")

def apply_negation_v2(tokens):
    out, negate = [], False
    for token in tokens:
        if token in NEGATION_TERMINATORS:
            negate = False
            out.append(token)
            continue
        if is_negation(token):
            negate = True
            out.append(token)
            continue
        out.append(f"NOT_{token}" if negate else token)
    return out
```

实测：

```text
apply_negation_v2(tokenize("this movie wasn't good"))
→ ['this', 'movie', "wasn't", 'NOT_good']

apply_negation_v2(tokenize("I didn't like it, but the ending was good!"))
→ ['i', "didn't", 'NOT_like', 'NOT_it', ',', 'but', 'the', 'ending', 'was', 'good', '!']
```

逗号正确地终止了否定作用域，`good` 保持正面。另一种修法是改 tokenizer，把 `wasn't` 拆成 `was` + `n't`（Penn Treebank 风格），让原来的 `"n't"` 条目生效——但要保证训练和推理用同一个 tokenizer。

### Q10 — 参考答案

`tokenize` + `apply_negation` 后测试句为 `['terrible', 'waste', 'of', 'time']`：
- `waste`：不在词表（OOV），`predict_nb` 直接跳过；
- `time`：训练中唯一的 `time` 被否定处理成了 `NOT_time`，所以普通的 `time` 也是 OOV，被跳过；
- 只剩 `terrible` 和 `of` 参与打分。

| 类别 | `log P(c)` | `log P(terrible|c)` | `log P(of|c)` | 合计 |
|------|-----------|---------------------|---------------|------|
| + | `log 0.5 = −0.693` | `log(1/70) = −4.248` | `log(3/70) = −3.150` | **−8.092** |
| − | `log 0.5 = −0.693` | `log(2/69) = −3.541` | `log(1/69) = −4.234` | **−8.468** |

（负类分母 = 25 + 44 = 69；`terrible` 在负类出现 1 次，平滑后为 2/69；`of` 在正类出现 2 次，平滑后为 3/70。两个合计值与实测完全一致。）

正类得分更高，于是判为正面。暴露的问题：
1. **停用词主导决策**：功能词 `of` 碰巧在正类训练句里出现两次，它的"倾向"抵消了 `terrible` 的负面信号。数据量越小，这种偶然性越严重。
2. **OOV 被静默丢弃**：真正有信号的 `waste` 没见过；`time` 因否定处理在训练中只以 `NOT_time` 形式出现。
3. **否定作用域的副作用**：它把一个中性词变成了另一种形式，进一步加剧了数据稀疏。
4. 结论：10 条训练样本只适合演示原理；讲义说真实任务需要数万条样本（IMDb、SST-2、Yelp），"The math is identical."

### Q11 — 参考答案

```python
def macro_report(y_true, y_pred, labels=("+", "-")):
    per_class, f1s = {}, []
    for c in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1s.append(f1)
        per_class[c] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)}
    confusion = {(t, p): sum(1 for a, b in zip(y_true, y_pred) if a == t and b == p)
                 for t in labels for p in labels}
    return {
        "per_class": per_class,
        "macro_f1": round(sum(f1s) / len(f1s), 3),      # 先平均再四舍五入
        "accuracy": round(sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true), 3),
        "confusion": confusion,                           # 键为 (真实, 预测)
    }
```

在本次运行结果上的输出：

```text
per_class: {'+': {'precision': 0.5, 'recall': 1.0, 'f1': 0.667},
            '-': {'precision': 1.0, 'recall': 0.333, 'f1': 0.5}}
macro_f1: 0.583    accuracy: 0.6
confusion: {('+','+'): 2, ('+','-'): 0, ('-','+'): 2, ('-','-'): 1}
```

（macro-F1 = (0.667 + 0.5)/2 ≈ 0.583，已用 `sklearn.metrics.f1_score(average="macro")` 验证。）

结论：`evaluate` 报告的 `f1: 0.667` 只是**正类**的 F1，掩盖了负类 recall 只有 0.333 的事实——3 条负面评论只抓住了 1 条。混淆矩阵一眼就能看出模型"偏向判正"。注意要先平均原始 F1 再四舍五入；如果先把每类 F1 四舍五入再平均，会得到 0.584 这样的舍入误差。

### Q12 — 参考回答要点

- **模型类型**：NB 是**生成式**模型，建模 `P(x|c)P(c)` 再用贝叶斯公式求后验；LR 是**判别式**模型，直接建模 `P(c|x) = σ(w·x + b)`。
- **假设**：NB 假设特征在给定类别下条件独立；LR 不做此假设，相关特征的权重会在训练中相互调整。
- **训练**：NB 只需一次计数，闭式解，极快；LR 需要迭代优化（梯度下降），要调学习率和正则强度。
- **数据量**：小数据时 NB 往往更稳（参数少、收敛快）；数据多时 LR 通常更好（能利用更多信息、校正相关特征）。经典结论来自 Ng & Jordan（2002）对生成式与判别式分类器的比较。
- **否定**：LR 可以给 `not good` 这样的 bigram 学出负权重；讲义的定位是"NB 做基线，LR 做生产"。
- **加分点**：提到 Wang & Manning（2012）的 NBSVM——用 NB 的对数计数比作为特征再训练线性模型，在短文本情感上是很强的基线（讲义延伸阅读："bigrams + Naive Bayes is hard to beat on short text"）。

### Q13 — 参考回答要点

- **为什么有效**：分类只需要 argmax 正确，不需要概率准确。在稀疏文本特征 + 中等数据下，每个词的 `log P(w|+) − log P(w|−)` 给出了它"倾向哪一边"，把这些倾向加起来，方向通常是对的。讲义："the classifier cares about which side each word leans toward more than how much."
- **副作用**：
  1. **概率严重失真（过度自信）**：相关的词（如 `great` 与 `great movie` 的组成词、重复出现的同义词）被当作独立证据重复计数，后验概率常常被推到接近 0 或 1——NB 的输出概率不能直接当置信度使用，需要校准（如 Platt scaling、isotonic regression）。
  2. 无法表达特征间的交互，比如否定对后续词的翻转（需要靠 bigram / `NOT_` 前缀间接补救）。
  3. 对零频词敏感，必须平滑；α 的选择会影响结果（讲义：教学用 1.0，实践常用 0.01）。

### Q14 — 参考回答要点

- **先改指标**：业务关心负面评论，那么**负类**的 recall（抓住多少负面）和 precision（报警有多准）才是核心；主指标用 macro-F1，同时单独汇报负类的 P / R / F1。85:15 时"全判正面"也有 0.85 的 accuracy，accuracy 毫无意义。
- **完整评估方案**（讲义 Step 5）：
  - 每类 precision / recall 与 macro-F1；
  - 混淆矩阵（看清楚错在哪一对类别上）；
  - 每类抽 5 条错例人工阅读；
  - 不平衡极端时看 AUROC / AUPRC，AUPRC 对少数类更敏感。
- **阈值**：逻辑回归输出概率，默认阈值 0.5 未必最优。在验证集上画负类的 PR 曲线，按业务约束选阈值（如"负类 recall ≥ 0.9 的前提下 precision 最高"）。
- **训练侧**：`class_weight="balanced"` 或重采样（讲义练习 2）。
- **上线后**：监控预测分布与人工抽检的负类 recall；讲义指出领域漂移和反讽是上线后最需要关注的两种失败。

### Q15 — 参考回答要点

- **分层设计**：
  1. **整体极性**：TF-IDF（1–2 元语法、保留停用词、`sublinear_tf`）+ 否定处理 + 逻辑回归。线性模型微秒级，轻松满足 P99 < 10ms、日均百万量级；系数可解释。
  2. **方面级情感**（物流 / 质量 / 客服）：经典句子级分类做不了，需要 Transformer 或结构化输出模型（讲义："Transformers or structured output models only"）。由于延迟要求严，可以**离线批处理**：评论入库后异步跑方面级模型，结果供运营报表使用，不放在实时链路上。
- **折中**：如果方面级也要实时，可以先用关键词 / 分类器把句子路由到方面，再在每个方面上做句子级极性——精度有损，但能满足延迟。
- **评估与监控**：macro-F1、混淆矩阵、逐类错例；按商品类目分组监控（领域漂移：`tight` 在服装和音乐中的极性不同）；定期人工标注新样本重训。
- **常见误区**：为了"先进"直接全部上大模型实时推理，延迟和成本都扛不住。

### Q16 — 参考回答要点

- **"Not bad at all"**：
  - 否定作用域会得到 `not, NOT_bad, NOT_at, NOT_all`。如果训练数据中 `NOT_bad` 足够多地出现在正面样本里，模型能学到它偏正面——**能判对，但依赖数据**；
  - bigram 方案中 `not bad` 同理；
  - 纯 unigram BoW 只看到 `not`、`bad` 两个负面词，大概率判错。讲义开篇就把它列为"两个负面词却是正面"的难例。
- **"Oh great, another two-hour wait"（反讽）**：
  - 表面上 `great` 是强正面词，真实情感是负面。反讽依赖语用和常识（"等两小时"是坏事），词袋特征里没有这种信息。讲义的结论非常直接："Sarcasm detection. Classical models fail here. Period."
  - 需要上下文模型（Transformer），并且通常需要专门的反讽标注数据；讲义练习 3 也提醒，第一次尝试的反讽检测器往往只有约 50% 的随机水平。
- **加分点**：主动提出用错例分析量化这类句子在真实流量中的占比，再决定是否值得引入更重的模型。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../02-bag-of-words-tfidf/docs/zh.md)：本节官方前置课；特征表示部分。
- [阶段 02 · 14 朴素贝叶斯](../../../02-ml-fundamentals/14-naive-bayes/docs/zh.md)：本节官方前置课；贝叶斯公式与条件独立假设。
- [阶段 02 · 03 逻辑回归](../../../02-ml-fundamentals/03-logistic-regression/docs/zh.md)：sigmoid、交叉熵、梯度下降。
- [阶段 05 · 01 文本处理](../../01-text-processing/docs/zh.md)：tokenizer 决定了否定词能否被识别（Q9 的 bug 正源于此）。

### 本节被哪些后续内容用到
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md) 与 [阶段 02 · 17 不平衡数据](../../../02-ml-fundamentals/17-imbalanced-data/docs/zh.md)：macro-F1、PR 曲线、类别权重的系统讲解。
- [阶段 05 · 06 命名实体识别](../../06-named-entity-recognition/docs/zh.md)：从"整句一个标签"走向"每个 token 一个标签"。
- [阶段 05 · 08 文本的 CNNs 和 RNNs](../../08-cnns-rnns-for-text/docs/zh.md)：用神经网络捕捉词序，部分解决否定问题。
- [阶段 05 · 21 自然语言推理](../../21-nli-textual-entailment/docs/zh.md)：更细粒度的句子级语义判断。
- [阶段 07 · 06 BERT 与掩码语言建模](../../../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/zh.md)：反讽、方面级情感需要的上下文模型。
- [阶段 11 · 03 结构化输出](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：用 LLM 结构化输出做方面级情感抽取。

### 延伸关键词
`NBSVM` · `Platt scaling / 概率校准` · `class_weight="balanced"` · `PR 曲线与阈值选择` · `aspect-based sentiment analysis (ABSA)` · `SST-2 / IMDb / Yelp polarity` · `sarcasm detection` · `domain drift`
