# 测验 · 经典评估指标（Classical Metrics）

> **阶段 19 · 综合项目 · 第 71 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | tokenizer 是契约 | 所有指标统一用 `re.findall(r"\w+", text.lower())`；换 tokenizer 就等于换了 benchmark |
| 2 | exact match | `strip()` 后逐字比较，**区分大小写**；任一 target 命中即 1.0；数据集分数取平均 |
| 3 | token 级 F1 | 预测与参考的 token **多重集交集** / 预测长度 = P，/ 参考长度 = R，F1 = 2PR/(P+R)；多 target 取最大值（SQuAD 风格） |
| 4 | 修正 n-gram 精确率 | 候选 n-gram 计数被裁剪到参考中该 n-gram 的出现次数，防止重复同一个词刷分 |
| 5 | BLEU-4 | n = 1..4 修正精确率的几何平均 × brevity penalty；BP = 1（c ≥ r）否则 `exp(1 − r/c)` |
| 6 | 平滑 | 本节对**所有** n（含 unigram）的分子分母各加 1，避免 `log 0`；副作用是完全不相关的候选也有正分 |
| 7 | sentence vs corpus BLEU | `bleu4` 是句级；`corpus_bleu` 先汇总所有句子的计数和长度再算一次，**不等于**句级 BLEU 的平均 |
| 8 | ROUGE-L | 基于最长公共子序列（LCS）：P = LCS/候选长，R = LCS/参考长，F-beta 组合；保留词序但不要求连续；O(n·m) DP |
| 9 | 统一分派 | `score(metric_name, prediction, targets)` 返回 `[0, 1]` 的浮点数，runner 不按指标名分支 |
| 10 | 经典指标的局限 | 只奖励表面重叠、不懂语义；是"必要的地板"，模型类指标（BLEURT、BERTScore）在其上叠加 |

### 核心技能（能动手做到）

- [ ] 手算任意一对短句的 token F1、修正 n-gram 精确率、BP、BLEU-4 与 ROUGE-L
- [ ] 解释为什么 `"the the the the"` 的 unigram 精确率是 2/4 而不是 4/4
- [ ] 写出 LCS 的 DP 递推式并说明 ROUGE-L 为什么对词序敏感、F1 为什么不敏感
- [ ] 区分句级 BLEU 平均与 corpus BLEU，并能说出二者差多少的原因
- [ ] 指出 tokenizer、大小写、平滑方式对分数的影响，并能把本实现与 NLTK 的平滑做对比
- [ ] 用 `python3 -m pytest -q` 运行 42 个测试，并能为新的边界情况补测试

---

## 二、基础自测（选择题）

**Q1.** `tokenize("Don't stop_me now! 3.14")` 的结果是：

- A. `["don't", "stop_me", "now", "3.14"]`
- B. `["don", "t", "stop", "me", "now", "3", "14"]`
- C. `["don", "t", "stop_me", "now", "3", "14"]`
- D. `["Don", "t", "stop_me", "now", "3.14"]`

**Q2.** `f1_score("the cat sat", "a cat sat on the mat")` 的值约为：

- A. 0.667
- B. 0.5
- C. 0.75
- D. 1.0

**Q3.** 候选为 `"the the the the"`、参考为 `"the cat sat on the mat"`，`_modified_precision(cand, ref, 1)` 返回 `(clipped, total)`：

- A. `(4, 4)`
- B. `(1, 4)`
- C. `(2, 6)`
- D. `(2, 4)`

**Q4.** 用本节的 `bleu4` 计算 `"apple banana cherry date"` 对 `"the cat sat on the mat"`（没有任何共同词），结果约为：

- A. 0.0
- B. 0.183
- C. 0.302
- D. 0.607

**Q5.** `rouge_l("c b a", "a b c d")` 的值约为：

- A. 0.857
- B. 0.5
- C. 0.286
- D. 0.0

**Q6.** 关于 `exact_match("Paris", ["paris"])` 与 `f1_score("Paris", "paris")`，正确的是：

- A. 前者 0.0，后者 1.0
- B. 两者都是 1.0
- C. 两者都是 0.0
- D. 前者 1.0，后者 0.0

**Q7.** 候选 3 个 token、参考 6 个 token 时，brevity penalty 为：

- A. 0.5
- B. 1.0
- C. 0.607
- D. 0.368

**Q8.** 调用 `score("perplexity", "x", [])` 的结果是：

- A. 抛出 `ValueError: unknown metric_name`
- B. 返回 `0.0`
- C. 返回 `nan`
- D. 抛出 `KeyError`

---

## 三、动手 / 代码题

**Q9.** 手算 `bleu4("the runner won the race", "the runner crossed the finish line first")`：写出 n = 1..4 的 `(clipped, total)`、平滑后的 p_n、几何平均、BP 和最终 BLEU。然后解释：demo 中 `corpus_bleu` 对两个样本（第一句与参考完全相同）给出 0.5854，而两个句级 BLEU 的平均是多少？为什么不相等？

**Q10.** 讲义说平滑规则是 "the one Lin and Och called method 1: add one to both numerator and denominator of every n-gram precision"。代码是：

```python
    for n in range(1, max_n + 1):
        clipped, total = _modified_precision(cand, ref, n)
        smoothed_num = clipped + 1
        smoothed_den = total + 1
        log_p_sum += math.log(smoothed_num / smoothed_den)
```

1. 这种写法对 unigram 也加 1，会带来什么后果？用 Q4 的例子说明。
2. 当候选长度小于 n（例如 3 个词的候选没有 4-gram）时，p_4 等于多少？这对短候选意味着什么？
3. 改写成 Lin & Och（NLTK 中称为 `method2`）的做法：unigram 不平滑、n ≥ 2 时分子分母各加 1（分母为 0 时按 1 处理），并给出 `"the the the the"`、`"apple banana cherry date"`、`"the cat sat"` 三个候选（参考同上）的新旧分数。

**Q11.** 讲义承认 "Production setups will care about CJK, contractions, and code identifiers"。

1. 用当前 `tokenize` 计算 `f1_score("我爱北京", "我爱上海")`，结果是多少？为什么？
2. 写一个 `tokenize_cjk`：中日韩统一表意文字（`一-鿿`）逐字切分，其他按 `\w+` 切分，并重新计算上面的 F1。
3. 修改 tokenizer 后，旧的分数还能和新分数比较吗？

**Q12.** 阅读分派函数：

```python
METRIC_TABLE = {
    "exact_match": "scalar", "accuracy": "scalar",
    "f1": "per_target_max", "bleu_4": "per_target_max", "rouge_l": "per_target_max",
}

def score(metric_name, prediction, targets):
    if not targets:
        return 0.0
    if metric_name == "exact_match":
        return exact_match(prediction, targets)
    ...
    raise ValueError(f"unknown metric_name: {metric_name}")
```

1. 找出两个问题（提示：一个和检查顺序有关，一个和 `METRIC_TABLE` 有关）。
2. 用"函数表"重写 `score`，使未知指标无论 targets 是否为空都抛错，并真正用上 scalar / per_target_max 的区分。

---

## 四、面试高频题

**Q13.**（基础必考）请完整讲一遍 BLEU-4 的计算：修正 n-gram 精确率、为什么要裁剪、为什么用几何平均、brevity penalty 解决什么问题、为什么需要平滑。

**Q14.**（原理深挖）BLEU、ROUGE-L、token F1 分别衡量什么？为什么机器翻译传统上用 BLEU、摘要用 ROUGE？三者对词序的敏感性有何不同？

**Q15.**（工程实践）两篇论文在同一数据集上报告的 BLEU 相差好几分，甚至一篇写 28.3、一篇写 0.283。可能的原因有哪些？工程上如何让 BLEU 可复现？

**Q16.**（场景设计）你要为公司内部的 LLM 评估套件选指标，任务包括：数学题、选择题、抽取式问答、新闻摘要、客服回复改写。每类任务你选什么指标？经典指标在哪些任务上会失灵，你如何补救？

**Q17.**（追问型）为什么 corpus BLEU 不等于句级 BLEU 的平均？在排行榜上应该报哪一个？如果要给 BLEU 做置信区间，该怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：C

`text.lower()` 先转小写，`\w+` 匹配连续的"字母、数字、下划线"（Unicode 意义下）。撇号 `'` 和小数点 `.` 都不是 `\w`，所以 `don't` → `don`、`t`，`3.14` → `3`、`14`；下划线属于 `\w`，`stop_me` 保持为一个 token（B 错）。A 保留了撇号和小数点；D 没有转小写。实际运行输出与 C 一致。

### Q2 — 答案：A

预测 tokens `{the, cat, sat}`，参考 `{a, cat, sat, on, the, mat}`。交集 3 个（the、cat、sat），P = 3/3 = 1，R = 3/6 = 0.5，F1 = 2·1·0.5/1.5 = 0.667。这正是 demo 的第 3 行 `-> 0.6667`。B 是 recall；D 是 precision。

### Q3 — 答案：D

候选 unigram `("the",)` 出现 4 次，参考里 `the` 出现 2 次，裁剪为 `min(4, 2) = 2`；total 是候选 unigram 总数 4。注意分母是**候选**长度而不是参考长度（C 错）。测试 `test_modified_precision_clips` 用的是参考 `"the cat sat"`（只有 1 个 the），所以那里是 `(1, 4)`（B 是那个测试的答案，但不是本题）。

### Q4 — 答案：B

实测 0.1833。所有 n 的 clipped 都是 0，但平滑后 p_1 = 1/5、p_2 = 1/4、p_3 = 1/3、p_4 = 1/2，几何平均 `(1/120)^(1/4) ≈ 0.302`（C 是没乘 BP 的值），BP = `exp(1 − 6/4) ≈ 0.607`（D），相乘 ≈ 0.183。**一个与参考毫无共同词的候选拿到了 0.18 分**，这是 unigram 也做加一平滑的副作用（见 Q10）。标准 Lin & Och 平滑或 NLTK `method2` 下结果为 0（A）。

### Q5 — 答案：C

`c b a` 与 `a b c d` 的 LCS 长度为 1（任意一个字母都行，不可能同时保持两个字母的顺序）。P = 1/3，R = 1/4，F1 = 2·(1/12)/(7/12) = 2/7 ≈ 0.286。A 是 `rouge_l("a b c", "a b c d")` 的值（LCS = 3，P = 1，R = 0.75）。测试 `test_word_order_matters` 正是比较这两个值，说明 ROUGE-L 对词序敏感；而 token F1 对这两个候选给出相同的分数。

### Q6 — 答案：A

`exact_match` 只做 `strip()`，不做大小写归一化，`"Paris" != "paris"` → 0.0。`f1_score` 走 `tokenize`，先 `lower()`，两边都是 `["paris"]` → 1.0。同一个回答在不同指标下"规范化程度"不同，这正是讲义强调"tokenizer/规范化是契约"的原因；exact match 的大小写处理应交给第 70 课的 `post_process`（如 `lower`）。

### Q7 — 答案：D

`exp(1 − r/c) = exp(1 − 6/3) = exp(−1) ≈ 0.368`。实测 `bleu4("the cat sat", "the cat sat on the mat") = 0.3679`，恰好等于 BP——因为 3 个词的候选 p_1 = p_2 = p_3 = 1，而 p_4 的分子分母都是 0+1，也等于 1。C 是 c = 4、r = 6 时的 BP。

### Q8 — 答案：B

`score` 第一行 `if not targets: return 0.0` 在判断 metric 名之前就返回了，所以未知指标 + 空 targets 被静默当成 0 分，而不是抛错。只有 targets 非空时才会走到最后的 `raise ValueError`（测试 `test_unknown_metric_raises` 传的是 `["y"]`）。这是一个检查顺序问题，见 Q12。

### Q9 — 参考答案

候选 tokens：`the runner won the race`（c = 5）；参考：`the runner crossed the finish line first`（r = 7）。实际运行 `_modified_precision` 得到：

| n | (clipped, total) | 平滑后 p_n |
|---|-----------------|-----------|
| 1 | (3, 5)：the×2（参考也有 2 个 the）、runner | 4/6 = 0.667 |
| 2 | (1, 4)：只有 "the runner" | 2/5 = 0.400 |
| 3 | (0, 3) | 1/4 = 0.250 |
| 4 | (0, 2) | 1/3 = 0.333 |

几何平均 = `(0.667 × 0.4 × 0.25 × 0.333)^(1/4) = 0.02222^(0.25) ≈ 0.3861`；BP = `exp(1 − 7/5) = exp(−0.4) ≈ 0.6703`；BLEU ≈ **0.2588**（与代码计算一致）。

两个句级 BLEU 的平均 = `(1.0 + 0.2588) / 2 ≈ 0.6294`，而 `corpus_bleu = 0.5854`。不相等的原因：corpus BLEU 先把两句的 clipped/total **计数相加**、长度相加，再算一次 p_n 和 BP。第一句贡献了大量完全匹配的 n-gram，但第二句的 3-gram、4-gram 全部未命中，相加后 p_3、p_4 被拉低；并且 BP 用总长度 c = 11、r = 13 计算，而不是逐句计算再平均。几何平均和 BP 都是非线性的，"先平均再取指标"与"先取指标再平均"自然不同。

### Q10 — 参考答案

1. **unigram 加一的后果**：clipped = 0 时 p_1 = 1/(c+1) 而不是 0，几何平均永远大于 0。Q4 中毫无共同词的候选拿到 0.183，而部分正确的 `"the the the the"` 也只有 0.241——"完全错"和"部分对"之间的差距被压缩，指标区分度下降。
2. **候选短于 n**：`_modified_precision` 返回 `(0, 0)`，平滑后 p_n = (0+1)/(0+1) = **1**。也就是说，短候选在高阶 n-gram 上"缺考反而拿满分"。`"the cat sat"` 的 p_4 = 1，最终 BLEU 完全由 BP 决定（0.368）；单词 `"yes"` 对 `"yes"` 也得到 BLEU = 1.0。
3. 参考实现（已运行验证，结果与 NLTK 3.10 的 `SmoothingFunction().method2` 逐位一致）：

```python
def bleu4_lin_och(prediction, reference, max_n=4):
    cand, ref = tokenize(prediction), tokenize(reference)
    if not cand:
        return 0.0
    log_p = 0.0
    for n in range(1, max_n + 1):
        clipped, total = _modified_precision(cand, ref, n)
        if n == 1:
            if clipped == 0:
                return 0.0                      # unigram 不平滑：一个词都没对就是 0
            p = clipped / total
        else:
            p = (clipped + 1) / (max(total, 1) + 1)   # 分母为 0 时按 1 处理
        log_p += math.log(p)
    return _brevity_penalty(len(cand), len(ref)) * math.exp(log_p / max_n)
```

| 候选（参考 `the cat sat on the mat`） | 原实现 | Lin & Och / NLTK method2 |
|------|------|------|
| `the the the the` | 0.2412 | 0.2304 |
| `apple banana cherry date` | 0.1833 | 0.0000 |
| `the cat sat` | 0.3679 | 0.3093（p_4 = 1/2 而非 1） |
| `the cat sat on the mat` | 1.0000 | 1.0000 |

补充：讲义把这种平滑称为 Lin and Och 的 "method 1"；在 Chen & Cherry (2014) 的编号（也是 NLTK 采用的编号）中，"分子分母各加 1"是 **method 2**，且只作用于 n ≥ 2；method 1 是给 0 计数加一个很小的 epsilon。

### Q11 — 参考答案

1. 结果 **0.0**。`\w` 在 Unicode 模式下包含汉字，而中文没有空格，`"我爱北京"` 整体是**一个** token，`"我爱上海"` 是另一个 token，交集为空。只要中文句子不完全相同，F1、BLEU、ROUGE-L 都接近 0——指标对中文"失明"。
2. 参考实现（已运行验证）：

```python
CJK_RE = re.compile(r"[一-鿿]|[^\W一-鿿]+")

def tokenize_cjk(text):
    return CJK_RE.findall(text.lower())

tokenize_cjk("我爱北京 Hello_World 42")   # ['我', '爱', '北', '京', 'hello_world', '42']
```

`[^\W一-鿿]+` 表示"是 `\w` 但不是汉字"的连续字符。用它计算 F1：交集 {我, 爱}，P = R = 2/4，F1 = **0.5**。生产中更常见的做法是用分词器（如 jieba）或直接用模型 tokenizer，但"逐字"已经比"整句一个 token"好得多。
3. 不能直接比较。讲义："If you swap tokenizers, you are running a different benchmark." 换 tokenizer 后必须对所有模型重新打分，并在报告里写明 tokenizer 版本。

### Q12 — 参考答案

1. 问题：
   - **检查顺序**：`if not targets: return 0.0` 放在最前面，未知指标在空 targets 时静默返回 0（Q8）。typo 写成 `"rouge-l"` 的任务如果 targets 也是空的，就会悄悄得 0 分而不报错。（第 70 课校验器保证 targets 非空，所以在完整管线中不太会触发，但函数本身的契约是不严谨的。）
   - **`METRIC_TABLE` 是死代码**：定义了却从未使用，分派仍是一串 `if`；讲义说的 "one dispatch table" 并未真正实现。另外 `code_exec` 不在表中，交给第 72 课处理，调用 `score("code_exec", ...)` 会抛错。
2. 参考实现（已运行验证）：

```python
SCALAR = {"exact_match": exact_match, "accuracy": accuracy}
PER_TARGET = {"f1": f1_score, "bleu_4": bleu4, "rouge_l": rouge_l}

def score_v2(metric_name, prediction, targets):
    if metric_name in SCALAR:
        return SCALAR[metric_name](prediction, targets) if targets else 0.0
    if metric_name in PER_TARGET:
        fn = PER_TARGET[metric_name]
        return max((fn(prediction, t) for t in targets), default=0.0)
    raise ValueError(f"unknown metric_name: {metric_name}")
```

验证：`score_v2("f1", "the cat", ["a horse", "the cat"]) == 1.0`；`score_v2("rouge_l", "x", []) == 0.0`；`score_v2("perplexity", "x", [])` 抛 `ValueError`。`max(..., default=0.0)` 处理空序列，避免 `max()` 对空生成器报错。加新指标只需往表里加一项，第 72 课可以把 `code_exec` 注册进来。

### Q13 — 参考回答要点

- **修正 n-gram 精确率**：对 n = 1..4，统计候选的 n-gram，每个 n-gram 的计数裁剪到参考中该 n-gram 的（多参考时取最大）出现次数，再除以候选 n-gram 总数。
- **为什么裁剪**：否则 `"the the the the"` 的 unigram 精确率是 100%。裁剪后为 2/4（参考有 2 个 the）。
- **为什么几何平均**：四个精确率数量级不同（高阶 n-gram 更难命中），几何平均（log 的算术平均）对任何一个很低的 p_n 都敏感，能同时要求"词对"和"顺序/短语对"。
- **brevity penalty**：精确率天然偏爱短输出（只输出一个很有把握的词就能拿高精确率）。BP = 1（c ≥ r），否则 `exp(1 − r/c)`；BLEU 本身没有 recall，用 BP 粗略补偿。
- **平滑**：短句或句级 BLEU 中高阶 n-gram 常常 0 命中，`log 0` 让整体为 0；平滑（加一、epsilon 等）避免这种"一票否决"。
- 加分点：说出原始 BLEU 是 **corpus 级**设计的，句级 BLEU 必须平滑；以及本节实现对 unigram 也加一的副作用。

### Q14 — 参考回答要点

- **BLEU**：精确率导向（候选中有多少 n-gram 出现在参考中）+ BP；关心"说的话对不对"，翻译中参考与候选长度接近，适用。
- **ROUGE-L**：基于 LCS，同时有 P 和 R，常以 recall 为主（ROUGE 全称 Recall-Oriented Understudy for Gisting Evaluation）；摘要关心"参考中的要点覆盖了多少"，所以用 ROUGE。本节 `rouge_l` 用 F-beta，beta = 1 时对称；beta 越大越偏向 recall（实测 beta = 2 时 `"the cat sat"` 的分数从 0.667 降到 0.556，因为 recall 只有 0.5）。
- **token F1**：词袋多重集交集，完全不看顺序；SQuAD 式抽取问答的标准指标，答案短、顺序不重要。
- **词序敏感性**：F1 不敏感（实测 `"mat the on sat cat the"` 对 `"the cat sat on the mat"` 的 F1 = 1.0）；ROUGE-L 部分敏感（同一例子 0.5，只要求相对顺序）；BLEU 通过高阶 n-gram 敏感（同一例子 0.302）。
- 加分点：三者都只看表面重叠，同义改写会被惩罚；讲义："They reward surface overlap and miss meaning."

### Q15 — 参考回答要点

- **量纲**：一篇用 0–100，一篇用 0–1（讲义原例 28.3 vs 0.283）。
- **tokenization**：是否小写、是否切分标点、中文是否分字、用 Moses tokenizer 还是 `\w+`。讲义："ROUGE-L scores that differ by ten points across two libraries because one truncates to lowercase and the other does not."
- **平滑方法**：无平滑 / epsilon / 加一，是否对 unigram 平滑（Q10 中同一候选 0.183 vs 0）。
- **句级平均 vs corpus 级**（Q9：0.6294 vs 0.5854）。
- **参考数量**：多参考时裁剪取最大值、BP 选最接近的参考长度。
- **预处理**：参考是否 detokenize，是否去掉了特殊符号。
- **可复现做法**：固定一个实现并在报告里写明全部配置（类似 sacreBLEU 输出的"签名"字符串：tokenizer、大小写、平滑、参考数、版本）；指标代码与测试一起版本化；对比时所有模型用同一份打分代码重新计算，不从论文里抄数字。

### Q16 — 参考回答要点

- **数学题**：后处理抽取最终数字 + exact match（或数值容差比较）；BLEU/F1 毫无意义。
- **选择题**：`extract_letter` + exact match / accuracy；同时记录置信度做校准（第 73 课）。
- **抽取式问答**：exact match + token F1（SQuAD 风格），多个可接受答案取最大值。
- **新闻摘要**：ROUGE-L（以及 ROUGE-1/2）做地板；再叠加模型类指标（BERTScore）或 LLM-as-judge 评忠实度，抽样人工评估。
- **客服回复改写**：参考答案只是"许多正确答案之一"，BLEU/ROUGE 会严重惩罚合理改写；更适合 LLM-as-judge + 规则检查（是否包含必需信息、语气、长度），经典指标只做回归监控。
- **失灵场景**：同义改写、数字/否定词的一字之差（"可以" vs "不可以" 的 F1 很高但意思相反）、中文分词问题、答案格式差异。
- 补救：更强的 post-process、多参考、模型类指标、人工抽检；对每个指标写测试锁定行为。

### Q17 — 参考回答要点

- **为什么不等**：corpus BLEU 是对**汇总计数**做一次非线性运算（几何平均 + BP），句级平均是对每句非线性运算后再求算术平均。长句贡献更多 n-gram，在 corpus BLEU 中权重更大；BP 只在总长度层面计算，单句过短可以被其他句子的长度"抵消"。
- **报哪个**：BLEU 的原始定义和翻译领域惯例是 corpus BLEU；句级 BLEU 主要用于逐样本分析或作为训练信号，必须平滑。本节 `score` 返回的是句级 BLEU，第 74 课再按任务取平均——这其实是"句级平均"，应在报告里写清楚。
- **置信区间**：对测试集样本做 bootstrap 重采样（有放回抽取 N 个句子），每次重新计算 corpus BLEU，取 2.5% 与 97.5% 分位数；比较两个系统时用**配对** bootstrap（同一组重采样索引上计算两系统的差）。第 74 课的 `bootstrap_pairwise_diff` 就是这种思路，只不过它对每任务分数取平均。
- 加分点：说明为什么不能对 corpus BLEU 直接套用"均值 ± 1.96·标准误"公式——它不是样本均值。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 70 任务规范格式](../../70-task-spec-format/docs/zh.md)：`metric_name` 封闭词表、`targets` 列表与 post-process 规则，本节的 `score` 按它分派。
- [阶段 05 · 01 文本处理 — Tokenization、词干提取、词形还原](../../../05-nlp-foundations-to-advanced/01-text-processing/docs/zh.md)：tokenization 的选择如何影响下游。
- [阶段 05 · 11 机器翻译](../../../05-nlp-foundations-to-advanced/11-machine-translation/docs/zh.md)：BLEU 的来源与使用场景。
- [阶段 05 · 12 文本摘要](../../../05-nlp-foundations-to-advanced/12-text-summarization/docs/zh.md)：ROUGE 的来源与使用场景。
- [阶段 05 · 13 问答系统](../../../05-nlp-foundations-to-advanced/13-question-answering/docs/zh.md)：SQuAD 式 exact match 与 token F1。
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：precision、recall、F1 的基本定义。

### 本节被哪些后续内容用到
- [阶段 19 · 72 代码执行评估指标](../../72-code-exec-metric/docs/zh.md)：把 `code_exec` 接入同一个分派模式。
- [阶段 19 · 74 排行榜汇总](../../74-leaderboard-aggregation/docs/zh.md)：消费本节输出的 `[0, 1]` 分数并做 bootstrap。
- [阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：直接调用本节的 `score`。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：在经典指标之上叠加模型类指标。
- [阶段 19 · 68 RAG Evaluation](../../68-rag-eval-precision-recall/docs/zh.md)：检索场景下的 precision/recall 家族指标。

### 延伸关键词
`sacreBLEU` · `chrF` · `METEOR` · `ROUGE-1 / ROUGE-2` · `BERTScore` · `BLEURT` · `Chen & Cherry smoothing` · `corpus vs sentence BLEU` · `SQuAD EM/F1` · `LCS` · `paired bootstrap`
