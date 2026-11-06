# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 71 节 经典评估指标 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（测试：`python3 -m pytest -q`） ｜ **依赖**：标准库（`re`、`math`、`collections.Counter`）+ 第三方 `numpy`

---

## 1. 这份代码在考察什么

这份代码从第一性原理实现五个"至今仍撑起大多数 LLM 评测数字"的经典指标：

1. **exact match / accuracy**：逐字比较，任务级 0 或 1。
2. **token 级 F1**：词袋多重集交集上的 precision、recall 与调和平均。
3. **BLEU-4**：修正（裁剪）n-gram 精确率、四阶几何平均、brevity penalty、加一平滑；另有 corpus 级版本。
4. **ROUGE-L**：最长公共子序列（LCS）动态规划 + F-beta。
5. **统一分派**：`score(metric_name, prediction, targets)`，对接第 70 课的 `metric_name` 字段，返回 `[0, 1]`。

讲义反复强调的核心观点是：**tokenizer 和平滑方式是指标定义的一部分**，"你自己写一遍，然后指着那一行说：tokenizer 在这里决定、平滑在这里施加"。所以读这份代码时要特别留意每个"看似细节"的选择，它们都会直接改变分数。

> 一句话：**把论文里的一个数字还原成几十行可审计的计数与除法**——同时弄清楚它和 NLTK 等常见实现在哪里不同。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TOKEN_RE` / `tokenize` | 常量 + 函数 | 小写后取 `\w+` 连续片段 | tokenizer 契约 |
| `exact_match` | 函数 | `strip()` 后逐字比较，任一 target 命中即 1.0 | exact match |
| `accuracy` | 函数 | 直接调用 `exact_match` | accuracy |
| `f1_score` | 函数 | `Counter` 交集计算 P/R/F1，处理空输入 | token F1 |
| `_ngram_counts` | 私有函数 | 统计 n-gram（元组）计数 | n-gram |
| `_modified_precision` | 私有函数 | 裁剪后的命中数与候选 n-gram 总数 | 修正精确率 |
| `_brevity_penalty` | 私有函数 | `exp(1 − r/c)` 或 1 | BP |
| `bleu4` | 函数 | 句级 BLEU-4（加一平滑） | BLEU |
| `lcs_length` | 函数 | NumPy 表格 DP 求 LCS 长度 | LCS |
| `rouge_l` | 函数 | LCS → P/R → F-beta | ROUGE-L |
| `METRIC_TABLE` | 常量字典 | 指标 → scalar / per_target_max（**未被使用**） | 分派表 |
| `score` | 函数 | 按 `metric_name` 分派，多 target 取最大 | 统一接口 |
| `corpus_mean` | 函数 | 数据集平均分 | 聚合 |
| `corpus_bleu` | 函数 | 汇总计数后的 corpus 级 BLEU | corpus BLEU |
| `_reference_examples` / `demo` | 函数 | 8 个参考向量 + corpus BLEU 演示 | 自检 |

数据流：`prediction, targets` → `score` → `tokenize`（两侧）→ 计数 / DP → 指标值 ∈ [0, 1] → `corpus_mean`（数据集层面，第 74 课再做 bootstrap）。

---

## 3. 逐段精讲

### 3.1 tokenizer：一切的起点

```python
TOKEN_RE = re.compile(r"\w+", re.UNICODE)

def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())
```

- 先 `lower()`，再找所有"字母/数字/下划线"的连续片段，标点全部丢弃。实测：`tokenize("Don't stop_me now! 3.14")` → `['don', 't', 'stop_me', 'now', '3', '14']`。
- Python 3 的 `str` 正则默认就是 Unicode 模式，`re.UNICODE` 只是显式写明。`\w` 包括汉字、带重音字母（`café` 是一个 token）。
- **注意**：中文没有空格，`"我爱北京"` 整句是**一个** token，导致中文句子之间的 F1/BLEU/ROUGE 几乎总是 0（实测 `f1_score("我爱北京", "我爱上海") == 0.0`）。讲义承认这是"deliberate simplification"。
- **注意**：`3.14` 被切成 `3`、`14`，`"3.14"` 和 `"14 3"` 的 F1 相同。

### 3.2 exact match 与 accuracy

```python
def exact_match(prediction: str, targets: list[str]) -> float:
    if not targets:
        return 0.0
    pred = prediction.strip()
    return 1.0 if any(pred == t.strip() for t in targets) else 0.0

def accuracy(prediction: str, targets: list[str]) -> float:
    return exact_match(prediction, targets)
```

- 只去两端空白，**不**转小写、**不**走 tokenizer。`exact_match("Paris", ["paris"]) == 0.0`，而 `f1_score("Paris", "paris") == 1.0`。大小写归一应由第 70 课的 `post_process`（`lower`）负责。
- `any(...)` 搭配生成器表达式：找到第一个命中就短路返回。
- `accuracy` 只是别名。讲义说 accuracy 是"对单个**规范化** target 的 exact match"，代码里没有额外规范化；保留单独的函数只是为了让分派表能按名字区分。

### 3.3 token F1：多重集交集

```python
def f1_score(prediction: str, target: str) -> float:
    pred_tokens = tokenize(prediction)
    tgt_tokens = tokenize(target)
    if not pred_tokens and not tgt_tokens:
        return 1.0
    if not pred_tokens or not tgt_tokens:
        return 0.0
    pred_counts = Counter(pred_tokens)
    tgt_counts = Counter(tgt_tokens)
    overlap = sum((pred_counts & tgt_counts).values())
    if overlap == 0:
        return 0.0
    precision = overlap / sum(pred_counts.values())
    recall = overlap / sum(tgt_counts.values())
    return 2.0 * precision * recall / (precision + recall)
```

- `Counter & Counter` 是**多重集交集**：每个键取两边计数的最小值。`"cat cat cat"` 对 `"cat"`：交集 1，P = 1/3，R = 1，F1 = 0.5；反过来 P = 1，R = 1/3，F1 同样是 0.5（测试 `test_repeated_token_counts_once_per_overlap` 只断言二者相等）。
- 空/空 = 1.0（约定为完美匹配）；一边为空 = 0.0。
- `overlap == 0` 时提前返回，避免 `precision + recall == 0` 的除零。
- 例：`"the cat sat"` 对 `"a cat sat on the mat"`：交集 3，P = 1，R = 0.5，F1 = 0.667（demo 第 3 行）。

### 3.4 n-gram 计数与修正精确率

```python
def _ngram_counts(tokens: list[str], n: int) -> Counter:
    if n <= 0:
        raise ValueError("n must be positive")
    if len(tokens) < n:
        return Counter()
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))

def _modified_precision(cand_tokens, ref_tokens, n) -> tuple[int, int]:
    cand_ngrams = _ngram_counts(cand_tokens, n)
    if not cand_ngrams:
        return (0, 0)
    ref_ngrams = _ngram_counts(ref_tokens, n)
    clipped = 0
    for gram, count in cand_ngrams.items():
        clipped += min(count, ref_ngrams.get(gram, 0))
    total = sum(cand_ngrams.values())
    return (clipped, total)
```

- n-gram 用**元组**表示（列表不可哈希，不能做 `Counter` 的键）。长度为 L 的序列有 `L − n + 1` 个 n-gram。
- **裁剪**：`min(count, ref_count)`。`"the the the the"` 对 `"the cat sat on the mat"`：unigram `(2, 4)`、bigram `(0, 3)`、trigram `(0, 2)`、4-gram `(0, 1)`（实测）。
- 返回原始计数 `(clipped, total)` 而不是比值，这样 `corpus_bleu` 可以先跨句子求和再相除。
- 只支持**单参考**；标准 BLEU 的多参考要对每个 n-gram 取所有参考中的最大计数。本节的"多 target"是在 `score` 里对每个 target 分别算 BLEU 再取最大值，两者不等价。

### 3.5 brevity penalty 与 BLEU-4

```python
def _brevity_penalty(cand_len: int, ref_len: int) -> float:
    if cand_len == 0:
        return 0.0
    if cand_len >= ref_len:
        return 1.0
    return math.exp(1.0 - ref_len / cand_len)

def bleu4(prediction: str, reference: str, max_n: int = 4) -> float:
    cand = tokenize(prediction)
    ref = tokenize(reference)
    if not cand:
        return 0.0
    log_p_sum = 0.0
    for n in range(1, max_n + 1):
        clipped, total = _modified_precision(cand, ref, n)
        smoothed_num = clipped + 1
        smoothed_den = total + 1
        log_p_sum += math.log(smoothed_num / smoothed_den)
    geo_mean = math.exp(log_p_sum / max_n)
    bp = _brevity_penalty(len(cand), len(ref))
    return float(bp * geo_mean)
```

- **几何平均在 log 空间算**：`exp(Σ log p_n / 4)`，避免小数连乘下溢，形式上也更清楚。
- **BP**：候选不短于参考时为 1；否则 `exp(1 − r/c)`。c = 3、r = 6 → `e^{-1} ≈ 0.368`。BP 弥补了 BLEU 只有精确率、没有召回率的缺陷——否则只输出一个最有把握的词就能拿高分。
- **注意**：**平滑作用于所有 n，包括 unigram**：
  - 完全不相关的候选也有正分：`"apple banana cherry date"` → 0.1833（实测）。NLTK 的 `method2`（即 Lin & Och 2004 的加一平滑）只对 n ≥ 2 加一，同一例子得 0。
  - 候选短于 n 时 `(0, 0)` 被平滑成 `1/1 = 1`：`"the cat sat"` 的 p_4 = 1，BLEU 完全由 BP 决定（0.3679）；NLTK 里该项为 `(0+1)/(1+1) = 0.5`，结果 0.3093。
  - 讲义把这种平滑称为 Lin and Och 的 "method 1"；按 Chen & Cherry (2014)/NLTK 的编号它是 method 2，method 1 是 epsilon 平滑。
- **注意**：讲义写 "The formulation we use is corpus-level BLEU-4"，但 `bleu4`（也是 `score("bleu_4", ...)` 实际调用的函数）是**句级**的；corpus 级在单独的 `corpus_bleu` 里。
- 完全相同的句子：每个 p_n = (k+1)/(k+1) = 1，BP = 1，BLEU = 1.0（demo 第 5 行）。

### 3.6 LCS 与 ROUGE-L

```python
def lcs_length(a: list[str], b: list[str]) -> int:
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 0
    dp = np.zeros((n + 1, m + 1), dtype=np.int32)
    for i in range(n):
        ai = a[i]
        row_prev = dp[i]
        row_curr = dp[i + 1]
        for j in range(m):
            if ai == b[j]:
                row_curr[j + 1] = row_prev[j] + 1
            else:
                row_curr[j + 1] = max(row_curr[j], row_prev[j + 1])
    return int(dp[n, m])
```

- 递推式：`dp[i+1][j+1] = dp[i][j] + 1`（当前两个 token 相同），否则 `max(dp[i+1][j], dp[i][j+1])`。`dp[i][j]` 表示 `a[:i]` 与 `b[:j]` 的 LCS 长度，表格多一行一列作为空前缀的边界。
- `row_prev = dp[i]`、`row_curr = dp[i + 1]` 取到的是 NumPy **视图**（view），写 `row_curr[j + 1]` 会直接改 `dp`。这比每次写 `dp[i+1, j+1]` 少一次二维索引，是个小优化。
- 时间 O(n·m)，空间 O(n·m)；只需长度时可以只保留两行，空间降到 O(m)。
- 例：`lcs_length(list("ABCBDAB"), list("BDCABA")) == 4`（经典教材例子，实测）。

```python
def rouge_l(prediction: str, reference: str, beta: float = 1.0) -> float:
    ...
    lcs = lcs_length(cand, ref)
    precision = lcs / len(cand)
    recall = lcs / len(ref)
    beta_sq = beta * beta
    denom = recall + beta_sq * precision
    return float((1 + beta_sq) * precision * recall / denom)
```

- F-beta：`(1 + β²)·P·R / (R + β²·P)`。β = 1 时就是 F1；β 越大越偏向 recall（实测 β = 2 时 `"the cat sat"` 对 6 词参考从 0.667 降到 0.556，因为 recall 只有 0.5）。
- LCS 只要求**相对顺序一致**、不要求连续：`"a b c"` 对 `"a b c d"` 得 0.857，`"c b a"` 得 0.286。这是 ROUGE-L 与词袋 F1 的本质区别。
- `if precision == 0.0 and recall == 0.0` 与 `if denom == 0` 两个分支在 `lcs > 0` 之后不可能触发，属于防御性代码。

### 3.7 分派：`score`

```python
METRIC_TABLE = {"exact_match": "scalar", "accuracy": "scalar",
                "f1": "per_target_max", "bleu_4": "per_target_max", "rouge_l": "per_target_max"}

def score(metric_name: str, prediction: str, targets: list[str]) -> float:
    if not targets:
        return 0.0
    if metric_name == "exact_match":
        return exact_match(prediction, targets)
    if metric_name == "accuracy":
        return accuracy(prediction, targets)
    if metric_name == "f1":
        return max(f1_score(prediction, t) for t in targets)
    if metric_name == "bleu_4":
        return max(bleu4(prediction, t) for t in targets)
    if metric_name == "rouge_l":
        return max(rouge_l(prediction, t) for t in targets)
    raise ValueError(f"unknown metric_name: {metric_name}")
```

- 两类指标：exact_match/accuracy 本身就接受 target 列表（"任一命中"）；F1/BLEU/ROUGE-L 对每个 target 单独算分再**取最大值**（"与最接近的参考比较"）。
- **注意**：空 targets 的检查放在最前面：`score("perplexity", "x", [])` 返回 0.0 而不是报错（实测）。
- **注意**：`METRIC_TABLE` 定义了但从未被引用；讲义说的 "one dispatch table" 实际上是一串 `if`。
- `code_exec` 不在这里，由第 72 课处理；第 75 课的 runner 先判断 `metric_name == "code_exec"`，否则才调用这里的 `score`。

### 3.8 corpus 级聚合

```python
def corpus_bleu(predictions, references, max_n=4) -> float:
    ...
    for cand_text, ref_text in zip(predictions, references):
        cand, ref = tokenize(cand_text), tokenize(ref_text)
        total_cand_len += len(cand)
        total_ref_len += len(ref)
        for n in range(1, max_n + 1):
            clipped, total = _modified_precision(cand, ref, n)
            clipped_sums[n - 1] += clipped
            total_sums[n - 1] += total
    ...
    bp = _brevity_penalty(total_cand_len, total_ref_len)
```

- 与句级的区别：先把所有句子的 clipped/total 和长度**分别求和**，最后只算一次 p_n 和 BP。这是 BLEU 原始论文的定义方式。
- demo：第一句完全匹配、第二句部分匹配，`corpus_bleu = 0.5854`；而两句句级 BLEU 分别是 1.0 和 0.2588，平均 0.6294（测验 Q9）。作为对照，NLTK 默认（无平滑）的 corpus BLEU 是 0.5483，`method2` 平滑后是 0.5827——同一组数据，因平滑不同而相差约 4 个点。
- `corpus_mean` 只是 `np.mean` 的薄包装，空列表返回 0.0。

### 3.9 参考向量与 demo

- `_reference_examples()` 给出 8 个例子，三种断言方式：`expected`（精确到 1e-9）、`expected_approx`（容差 0.05）、`expected_lt`（上界）。
- `demo()` 逐个计算、打印，任何一个不符合就把退出码设为 1，然后额外打印 corpus BLEU。
- **注意**：讲义说 "The tests ... pin the reference vectors"，但测试文件并没有导入 `_reference_examples`，参考向量只在 demo 里被检查；讲义还说 BLEU 和 ROUGE-L "include detailed comments on the smoothing rule and the LCS recurrence"，实际代码中没有注释。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 所有指标共用 `\w+` 小写 tokenizer | 一个契约，结果可解释 | 中文整句一个 token、缩写被拆；生产按语言选分词器，或用 sacreBLEU 的标准 tokenizer |
| exact match 不转小写 | 规范化交给 post-process，职责单一 | 若任务忘了配 `lower`，大小写不同即判错 |
| F1 用 `Counter` 交集 | 多重集语义天然正确，代码短 | 不看词序；同义词不算命中 |
| BLEU 所有 n 都加一平滑 | 永远不出现 `log 0`，代码最简单 | 无关候选得正分、短候选高阶项满分；与 NLTK/sacreBLEU 数值不同 |
| `score` 用句级 BLEU | 每个任务一个分数，便于第 74 课聚合 | 句级平均 ≠ corpus BLEU；报告需注明 |
| 多 target 取最大值 | 与 SQuAD 惯例一致 | BLEU 的标准多参考裁剪不是这样做的 |
| LCS 用 NumPy 表 | 可读，可以打印整张表观察 | 纯 Python 双重循环，长文本较慢；可只保留两行 |
| 指标返回 `[0, 1]` | 下游聚合不用关心量纲 | 论文常用 0–100，比较时要换算 |
| 分派用 if 链 | 直观 | `METRIC_TABLE` 成了死代码；改为函数表更易扩展 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `re.findall` | `TOKEN_RE.findall(text.lower())` | 返回所有不重叠匹配组成的列表 |
| `\w` 与 Unicode | `r"\w+"`、`re.UNICODE` | Python 3 中 `\w` 默认包含各国文字字母和数字 |
| `collections.Counter` | `Counter(pred_tokens)` | 计数字典；缺失键返回 0 |
| `Counter` 交集 `&` | `pred_counts & tgt_counts` | 逐键取最小计数（多重集交集） |
| `.values()` 求和 | `sum((a & b).values())` | 总计数 |
| 元组作字典键 | `tuple(tokens[i:i + n])` | 列表不可哈希，元组可以 |
| 切片 | `tokens[i:i + n]` | 取 `[i, i+n)` 区间 |
| 生成器表达式 + `any` | `any(pred == t.strip() for t in targets)` | 惰性求值，命中即停 |
| 生成器表达式 + `max` | `max(f1_score(prediction, t) for t in targets)` | 对空序列会抛 `ValueError`，可加 `default=` |
| 条件表达式 | `1.0 if any(...) else 0.0` | 一行 if/else |
| 列表乘法初始化 | `clipped_sums = [0] * max_n` | 创建长度为 `max_n` 的全 0 列表（不可变元素才安全） |
| `zip` | `for cand_text, ref_text in zip(predictions, references)` | 并行遍历两个序列 |
| `math.log` / `math.exp` | `math.exp(log_p_sum / max_n)` | 在 log 空间计算几何平均 |
| `np.zeros(..., dtype=np.int32)` | `dp = np.zeros((n + 1, m + 1), ...)` | 指定整数类型的二维表 |
| NumPy 视图 | `row_curr = dp[i + 1]` | 取一行得到视图，修改会写回原数组 |
| `int(...)` / `float(...)` | `int(dp[n, m])`、`float(bp * geo_mean)` | 把 NumPy 标量转成 Python 原生类型，便于 JSON 序列化 |
| 默认参数 | `def bleu4(prediction, reference, max_n=4)`、`beta: float = 1.0` | 可选参数 |
| 字典字面量 + 字符串键 | `{"metric": "f1", "expected_approx": 0.667}` | 用不同的键表达不同的断言方式 |
| `in` 判断键 | `if "expected" in ex:` | 检查字典是否含某键 |
| f-string 格式符 | `{ex['metric']:10s}`、`{ex['pred']!r:30s}`、`{actual:.4f}` | 宽度 10 的字符串、先 `repr` 再占 30 宽、4 位小数 |
| `if __name__ == "__main__"` | `sys.exit(demo())` | 直接运行时执行 demo 并返回退出码 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + NumPy）：

```text
$ python3 main.py
metric demos (using example vectors):
  exact_match pred='41'                           -> 1.0000 expected=1.0
  exact_match pred='42'                           -> 0.0000 expected=0.0
  f1         pred='the cat sat'                  -> 0.6667 approx=0.667
  f1         pred=''                             -> 0.0000 expected=0.0
  bleu_4     pred='the cat sat on the mat'       -> 1.0000 approx=1.0
  bleu_4     pred='the the the the'              -> 0.2412 < 0.5
  rouge_l    pred='the cat sat'                  -> 0.6667 approx=0.667
  accuracy   pred='positive'                     -> 1.0000 expected=1.0
  corpus_bleu over 2 examples -> 0.5854
$ echo $?
0
```

逐项解读：

- **exact_match 41/42**：完全相同得 1，否则 0。
- **f1 `the cat sat`**：P = 1、R = 0.5 → 0.6667。
- **f1 空预测**：参考非空、预测为空 → 0。
- **bleu_4 完全相同**：每个 p_n 都是 (k+1)/(k+1) = 1，BP = 1 → 1.0。
- **bleu_4 `the the the the` = 0.2412**：p = [3/5, 1/4, 1/3, 1/2]（clipped+1 / total+1），几何平均 `0.025^(1/4) ≈ 0.398`，BP = `exp(1 − 6/4) ≈ 0.607`，相乘 0.2412。裁剪把"重复刷词"压到了 0.5 以下；NLTK `method2` 下是 0.2304。
- **rouge_l `the cat sat`**：LCS = 3，P = 1、R = 0.5 → 0.6667。在这个例子上它与 F1 恰好相同，因为候选是参考的前缀，顺序完全一致。
- **accuracy**：与 exact match 相同。
- **corpus_bleu = 0.5854**：两句计数汇总后计算（候选总长 11、参考总长 13，BP = `exp(1 − 13/11) ≈ 0.834`）；而句级平均是 0.6294，见 3.8。
- 退出码 0：8 个参考向量全部在容差内。

---

## 7. 动手改一改

1. **修正平滑**：把 `bleu4` 改成 unigram 不平滑、n ≥ 2 加一（分母为 0 时按 1 处理），验证 `"apple banana cherry date"` 得 0、`"the cat sat"` 得 0.3093，与 NLTK `method2` 对齐（参考测验 Q10）。
2. **多参考 BLEU**：给 `_modified_precision` 增加 `refs: list[list[str]]`，裁剪时取所有参考中的最大计数，BP 选与候选长度最接近的参考长度；比较它与"对每个参考分别算 BLEU 取最大"的差别。
3. **中文 tokenizer**：实现逐字切分的 `tokenize_cjk`，让 `f1_score("我爱北京", "我爱上海")` 从 0 变成 0.5；思考为什么换 tokenizer 后所有历史分数都要重算。
4. **函数表分派**：用 `{"exact_match": ..., "f1": ...}` 字典替换 `score` 中的 if 链，让未知指标在任何情况下都抛错，并真正用上 scalar/per_target_max 的区分（参考测验 Q12）。
5. **ROUGE-N 与空间优化**：实现 ROUGE-1、ROUGE-2（基于 n-gram 召回），并把 `lcs_length` 改成只保留两行的 O(m) 空间版本，用测试确认结果不变。
6. **进阶：bootstrap 置信区间**：对一组 `(prediction, reference)` 有放回重采样 1000 次，每次计算 `corpus_bleu`，输出 95% 分位区间（为第 74 课热身）。

---

## 8. 常见坑

- **以为 BLEU 对无关输出给 0 分**：本实现对 unigram 也平滑，无关候选约 0.18。
- **混淆句级 BLEU 平均与 corpus BLEU**：同一组数据可以差好几个点（0.6294 vs 0.5854）。
- **只换了 tokenizer 就和旧结果比较**：tokenizer 是指标定义的一部分。
- **exact match 忘了规范化**：大小写、尾部句号（`"41."`）都会让 exact match 判错，而 F1 不受影响。
- **中文用 `\w+` 切分**：整句成一个 token，所有重叠类指标失效。
- **以为 F1 能衡量顺序**：`"mat the on sat cat the"` 对 `"the cat sat on the mat"` 的 F1 是 1.0，ROUGE-L 只有 0.5、BLEU 0.302。
- **`max()` 遇到空序列报错**：`score` 依赖开头的 `if not targets` 保护；自己重写时记得 `default=`。
- **量纲混用**：本节输出 0–1，论文常报 0–100；第 74 课的聚合器会拒绝超出 `[0, 1]` 的分数。
- **把平滑方法名照搬讲义**：讲义说的 "Lin and Och method 1" 在 NLTK 里叫 `method2`，并且不对 unigram 生效。

---

## 9. 测试在验证什么

测试文件：`tests/test_metrics.py`（`unittest` 风格）。通过 `sys.path.insert` 把 `code/` 加入路径后直接导入 `main` 中的公开函数和若干私有函数（`_brevity_penalty`、`_modified_precision`、`_ngram_counts`）。

运行方式：

```bash
cd code
python3 -m pytest -q            # 或：python3 -m unittest discover tests
```

实际运行结果：`42 passed in 0.08s`。

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `TestTokenize` | `test_basic_tokenize` / `test_empty` / `test_numbers_kept` | 小写、去标点；空串得空列表；数字保留为 token |
| `TestExactMatch` | `test_hit` / `test_miss` / `test_strips_whitespace` | 命中 1、不命中 0、两端空白被忽略 |
| | `test_multi_target_any_hit` / `test_empty_targets` / `test_accuracy_alias` | 任一 target 命中即可；空 targets 得 0；accuracy 与 exact match 一致 |
| `TestF1` | `test_identical` / `test_disjoint` / `test_partial` | 1.0、0.0、介于 0.4–0.7（实际 0.667） |
| | `test_empty_prediction` / `test_empty_target` / `test_both_empty` | 空输入的三种约定：0、0、1 |
| | `test_repeated_token_counts_once_per_overlap` | `"cat cat cat"` vs `"cat"` 与反向结果相同（都是 0.5）；名字说"只算一次"，实际断言的是对称性 |
| `TestNgram` | `test_unigram` / `test_4gram_short_text` / `test_modified_precision_clips` | n-gram 计数正确；序列短于 n 返回空；裁剪生效 `(1, 4)` |
| `TestBLEU` | `test_perfect_match` / `test_no_match` | 完全相同 ≈ 1；无关候选 < 0.3（实际 0.183——注意它**不是** 0，这个上界恰好容纳了平滑的副作用） |
| | `test_repetition_penalised` | 重复词 < 0.5 |
| | `test_brevity_penalty` / `test_brevity_penalty_function` | 短候选分数更低；BP 在 c ≥ r 时为 1、c = 5 r = 10 时为 `exp(−1)`、c = 0 时为 0 |
| | `test_empty_candidate` / `test_corpus_bleu` | 空候选得 0；两句完全相同的 corpus BLEU > 0.5 |
| `TestRougeL` | `test_lcs_basic` / `test_lcs_empty` | LCS 计算与空序列 |
| | `test_perfect` / `test_disjoint` / `test_partial` | 1.0、0.0、介于 0.6–0.85 |
| | `test_word_order_matters` | 顺序一致的候选分数更高（0.857 > 0.286） |
| `TestDispatcher` | 5 个 `test_dispatch_*` | 每个指标名都能正确分派 |
| | `test_unknown_metric_raises` | 未知指标（targets 非空）抛 `ValueError` |
| | `test_multi_target_takes_max` / `test_empty_targets_returns_zero` | 多 target 取最大；空 targets 返回 0 |
| `TestCorpus` | `test_corpus_mean` / `test_corpus_mean_empty` | 平均值与空列表 |

测试没有覆盖、值得补充的地方：

- 未知指标 + 空 targets（当前静默返回 0）；
- BLEU 与外部实现（如 NLTK）的数值对齐；
- 候选短于 4 个 token 时 p_4 = 1 的行为；
- 中文输入、大小写对 exact match 的影响；
- `rouge_l` 的 `beta ≠ 1` 分支；
- `corpus_bleu` 输入长度不一致时抛 `ValueError`。
