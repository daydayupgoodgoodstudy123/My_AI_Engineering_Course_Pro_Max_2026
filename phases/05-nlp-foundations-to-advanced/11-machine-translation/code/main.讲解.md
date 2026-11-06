# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 11 节 机器翻译 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅 Python 标准库（`math`、`collections.Counter`）；讲义中的 `transformers`（NLLB）、`sacrebleu` 示例不在本文件里

---

## 1. 这份代码在考察什么

讲义的 MT 流水线依赖大模型和 `sacrebleu`，本文件只做一件事：**从零实现两个最常用的翻译自动评估指标**，让你看清它们的数学细节和"脾气"：

1. **BLEU**：截断（clipped）n-gram 精确率 → 1–4 阶几何平均 → 简短惩罚（brevity penalty）。
2. **chrF**：字符级 n-gram（1–6 阶）的精确率与召回率平均后，计算 β=2 的 F 分数。
3. **无平滑句级 BLEU 的脆弱性**：任意一阶精确率为 0，整句分数直接归零。
4. **两个指标的对比**：同样一组例子，BLEU 只会给 100 或 0，chrF 能区分"意思对但措辞不同"和"意思完全错"。

> 一句话：**自己写一遍 BLEU 和 chrF，才知道为什么讲义坚持"永远用 sacrebleu"**——每一个实现细节（分词、大小写、平滑、空格、边界情况）都会改变分数。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tokenize(text)` | 函数 | 小写化，把 `.`、`,` 拆成独立 token，按空白切分 | BLEU 的分词前处理 |
| `ngrams(tokens, n)` | 函数 | 生成词级 n-gram 元组列表 | n-gram |
| `ngram_precision(hyp_tokens, ref_tokens, n)` | 函数 | 截断计数后的 n-gram 精确率 | modified precision |
| `brevity_penalty(hyp_len, ref_len)` | 函数 | 候选比参考短时的惩罚系数 | BP |
| `simple_bleu(hypothesis, reference, max_n)` | 函数 | 无平滑的句级 BLEU | BLEU |
| `simple_bleu_note()` | 函数 | 返回一段说明文字：无平滑的问题 | 平滑的必要性 |
| `chrf(hypothesis, reference, n, beta)` | 函数 | 字符 n-gram 的 F_β 分数 | chrF |
| `main()` | 函数 | 4 组 (候选, 参考) 打印 BLEU 与 chrF 对比表 | 演示入口 |

数据流：`simple_bleu → tokenize → ngram_precision（内部调 ngrams）+ brevity_penalty`；`chrf` 独立实现，不经过 `tokenize`，直接在小写字符串上取字符 n-gram。

---

## 3. 逐段精讲

### 3.1 分词与 n-gram

```python
def tokenize(text):
    return text.lower().replace(".", " .").replace(",", " ,").split()


def ngrams(tokens, n):
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]
```

- `tokenize` 做了三件事：小写、把句号和逗号与前一个词分开（`"courent."` → `"courent ."`）、按空白切分。不拆标点的话，`courent.` 和 `courent` 会被当成不同的词。
- 方法链 `text.lower().replace(...).replace(...).split()`：每个方法返回新字符串，依次处理。
- `ngrams`：滑动窗口取 n 个连续 token，转成 **tuple**——因为列表不可哈希，不能作为 `Counter` 的键；元组可以。
- `range(len(tokens) - n + 1)`：句子比 n 短时范围为空，返回 `[]`（例如单词 `"les"` 没有任何 2-gram）。
- ⚠️ 与 sacrebleu 的差异：sacrebleu 默认**区分大小写**，并使用自己的标准分词器（如 `13a`）处理更多标点；这里只处理 `.` 和 `,`，并统一小写。所以本文件的分数不能与论文数字比较——这正是讲义强调 sacrebleu 的原因。

### 3.2 截断精确率：BLEU 的核心

```python
def ngram_precision(hyp_tokens, ref_tokens, n):
    hyp_counts = Counter(ngrams(hyp_tokens, n))
    ref_counts = Counter(ngrams(ref_tokens, n))
    clipped = 0
    total = 0
    for ngram, count in hyp_counts.items():
        clipped += min(count, ref_counts.get(ngram, 0))
        total += count
    if total == 0:
        return 0.0
    return clipped / total
```

- **为什么要截断**：如果候选是 `the the the the`、参考是 `the cat sat`，不截断时 4 个 `the` 都"命中"，精确率 1.0；截断后每个 n-gram 最多算参考中出现的次数，`min(4, 1) = 1`，精确率 1/4。这叫 modified n-gram precision，防止靠重复高频词刷分。
- `Counter(...)` 统计每个 n-gram 出现次数；`ref_counts.get(ngram, 0)` 查不到就当 0。
- `total == 0` 时返回 0.0：候选比 n 还短（没有任何 n-gram）时，精确率无定义，这里按 0 处理——它会让 `simple_bleu` 直接归零。
- ⚠️ 只支持**单个参考**。标准 BLEU 支持多参考：每个 n-gram 的截断上限取所有参考中的最大计数。

### 3.3 简短惩罚

```python
def brevity_penalty(hyp_len, ref_len):
    if hyp_len >= ref_len:
        return 1.0
    if hyp_len == 0:
        return 0.0
    return math.exp(1 - ref_len / hyp_len)
```

- BLEU 只算精确率，如果没有惩罚，"只输出一个最有把握的词"就能拿到很高的精确率。BP 在候选短于参考时生效：`exp(1 - r/c)`，c 越短惩罚越重。
- 例：候选 1 个词、参考 4 个词，`BP = exp(1 - 4) = exp(-3) ≈ 0.0498`。
- `hyp_len == 0` 单独处理，避免 `ref_len / 0` 抛 `ZeroDivisionError`。
- 候选更长时 BP = 1：BLEU 对"太长"没有直接惩罚，只是多出来的 n-gram 会拉低精确率。

### 3.4 句级 BLEU：几何平均 + 无平滑

```python
def simple_bleu(hypothesis, reference, max_n=4):
    hyp = tokenize(hypothesis)
    ref = tokenize(reference)
    precisions = [ngram_precision(hyp, ref, n) for n in range(1, max_n + 1)]
    if any(p == 0 for p in precisions):
        return 0.0
    log_mean = sum(math.log(p) for p in precisions) / max_n
    bp = brevity_penalty(len(hyp), len(ref))
    return 100 * bp * math.exp(log_mean)
```

- 公式：`BLEU = 100 × BP × exp( (1/4) Σ log p_n )`，即 4 个精确率的**几何平均**。
- 为什么在 log 空间算：`exp(mean(log p))` 等于几何平均，且避免多个小数连乘的精度问题。
- `any(p == 0 for p in precisions)`：只要有一阶为 0，`math.log(0)` 会抛 `ValueError`，所以提前返回 0.0。这也说明几何平均的性质——**任何一项为 0，整体为 0**。
- 后果：对短句或措辞不同的句子，3-gram、4-gram 很容易一个都不命中，BLEU 直接归零。这就是 `simple_bleu_note()` 的内容：生产中 sacrebleu 提供 epsilon、add-k 等平滑方法。
- ⚠️ 这是**句级** BLEU。BLEU 原本是语料级指标：先在所有句子上累加截断计数和长度，再统一计算（测验 Q10 有实现）。

### 3.5 chrF：字符级 F 分数

```python
def chrf(hypothesis, reference, n=6, beta=2):
    def char_ngrams(text, k):
        return [text[i:i + k] for i in range(len(text) - k + 1)]

    hyp = hypothesis.lower()
    ref = reference.lower()
    precisions = []
    recalls = []
    for k in range(1, n + 1):
        hyp_c = Counter(char_ngrams(hyp, k))
        ref_c = Counter(char_ngrams(ref, k))
        match = sum((hyp_c & ref_c).values())
        if sum(hyp_c.values()) == 0 or sum(ref_c.values()) == 0:
            continue
        precisions.append(match / sum(hyp_c.values()))
        recalls.append(match / sum(ref_c.values()))
    if not precisions:
        return 0.0
    p = sum(precisions) / len(precisions)
    r = sum(recalls) / len(recalls)
    if p + r == 0:
        return 0.0
    beta2 = beta * beta
    return 100 * (1 + beta2) * p * r / (beta2 * p + r)
```

- **字符 n-gram**：对字符串切片，`"chats"` 的 2-gram 是 `ch, ha, at, ts`。`char_ngrams` 是定义在 `chrf` 内部的**嵌套函数**，只在这里用。
- **`hyp_c & ref_c`**：`Counter` 的交集运算，对每个键取两边计数的最小值——一行代码完成"截断匹配"。
- **同时算精确率和召回率**：这是和 BLEU 最大的区别。对 1–6 阶分别计算，再取算术平均。
- **F_β**：`(1+β²)·P·R / (β²·P + R)`，`β=2` 让召回更重要——漏译比多译更严重。
- 为什么对形态丰富的语言更友好：`courent`（跑，现在时复数）和 `courir`（跑，不定式）在词级 BLEU 里是完全不同的词，但字符 n-gram 共享 `cour`、`our` 等片段，chrF 能给部分分。
- ⚠️ 两个与 sacrebleu 不同的细节：
  1. **空格参与匹配**：字符串里的空格也被当作字符；sacrebleu 的 chrF 默认去掉空白再取字符 n-gram。
  2. **缺失阶数被跳过**：候选比 k 还短时直接 `continue`，平均时只用存在的阶数。对极短候选（如 `"Les"`）这会让精确率显得"满分"，从而高估分数（测验 Q9：若按 0 计入，`"Les"` 的分数从 14.0 降到 7.0）。

### 3.6 `main()`：四个对照用例

```python
    cases = [
        ("Les chats courent.", "Les chats courent."),
        ("Les chats sont en train de courir.", "Les chats courent."),
        ("Les chiens mangent.", "Les chats courent."),
        ("Les", "Les chats courent."),
    ]
```

四个用例分别代表：完全一致、意思正确但措辞不同（"正在跑"的迂回说法）、句式相同但意思完全错（狗在吃）、严重截断。对照两个指标的反应，能看出它们各自的盲区。

```python
    print(f"{'hypothesis':40s}  {'reference':25s}  {'BLEU':>6}  {'chrF':>6}")
    for hyp, ref in cases:
        b = simple_bleu(hyp, ref)
        c = chrf(hyp, ref)
        print(f"{hyp:40s}  {ref:25s}  {b:6.1f}  {c:6.1f}")
```

- `{hyp:40s}`：字符串左对齐占 40 格；`{b:6.1f}`：浮点数占 6 格、保留 1 位小数（数字默认右对齐）；`{'BLEU':>6}`：表头右对齐，与数字列对齐。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 从零实现、不依赖 sacrebleu | 每一步公式可见，零依赖 | 分数与论文不可比；生产中一律用 `sacrebleu` 并报告其签名 |
| 极简分词（小写 + 拆 `.` `,`） | 足够处理演示句子 | 大小写、其他标点、非拉丁文字都处理不了；sacrebleu 有标准分词器 |
| 句级、无平滑 BLEU | 让"零精确率 → 0 分"的问题直接暴露 | 句级分数方差极大；生产用语料级 BLEU，句级时必须平滑 |
| 只支持单参考 | 代码简洁 | 标准 BLEU 支持多参考，截断上限取各参考最大计数 |
| chrF 保留空格、跳过缺失阶数 | 实现简单 | 与 sacrebleu 默认行为不同，短候选会被高估 |
| `simple_bleu_note()` 用函数返回说明文字 | 把"注意事项"和代码放在一起，打印时一起输出 | 无，属于教学设计 |
| 4 个手工用例 | 覆盖"全对 / 改写 / 全错 / 截断"四类典型情况 | 不代表真实数据分布；评估要在完整测试集上做 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 字符串方法链 | `text.lower().replace(".", " .").split()` | 每个方法返回新字符串，可连续调用 |
| 列表切片 | `tokens[i:i + n]`、`text[i:i + k]` | 取一段子序列；字符串切片得到子串 |
| `tuple(...)` | `tuple(tokens[i:i + n])` | 列表转元组，使其可哈希、能当字典/Counter 的键 |
| `collections.Counter` | `Counter(ngrams(hyp_tokens, n))` | 计数器；`.get(k, 0)`、`.items()`、`.values()` |
| `Counter` 交集 `&` | `hyp_c & ref_c` | 对每个键取最小计数，正好是"截断匹配" |
| `dict.items()` 解包 | `for ngram, count in hyp_counts.items():` | 同时拿键和值 |
| 内置 `min` | `min(count, ref_counts.get(ngram, 0))` | 截断计数 |
| `any` + 生成器 | `any(p == 0 for p in precisions)` | 只要有一个为真就返回 True，且会短路 |
| `math.log` / `math.exp` | `math.exp(1 - ref_len / hyp_len)` | 自然对数与指数；`math.log(0)` 抛 `ValueError` |
| 提前返回（guard clause） | `if total == 0: return 0.0` | 先处理边界情况，主逻辑更清晰 |
| 嵌套函数 | `def char_ngrams(text, k):` 定义在 `chrf` 内 | 只在外层函数内部可见的辅助函数 |
| 括号内的多行字符串拼接 | `return ("simple_bleu above ..." "the score to 0.0. ...")` | 相邻字符串字面量会自动拼接 |
| 列表推导式 | `[ngram_precision(hyp, ref, n) for n in range(1, max_n + 1)]` | 一次算出 1–4 阶精确率 |
| f-string 对齐与格式 | `{hyp:40s}`、`{b:6.1f}`、`{'BLEU':>6}` | 宽度、对齐方向、小数位 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，仅标准库）的完整输出：

```text
hypothesis                                reference                    BLEU    chrF
Les chats courent.                        Les chats courent.          100.0   100.0
Les chats sont en train de courir.        Les chats courent.            0.0    56.3
Les chiens mangent.                       Les chats courent.            0.0    34.8
Les                                       Les chats courent.            0.0    14.0

simple_bleu above has no smoothing: one zero-precision n-gram drops the score to 0.0. This punishes short hypotheses; production uses epsilon / NIST / add-k smoothing via sacrebleu.
BLEU under 1 point is noise. chrF catches morphological partials BLEU misses.
For real work, use sacrebleu (pip install sacrebleu) instead of this teaching version.
```

逐行解读：

- **第 1 行（完全一致）**：所有精确率为 1、BP 为 1，BLEU 100；chrF 也是 100。
- **第 2 行（意思对、措辞不同）**：1–4 阶精确率为 `[0.375, 0.143, 0, 0]`，3-gram 和 4-gram 一个都没命中，BLEU 归零。chrF 给 56.3：`courir` 与 `courent` 共享字符片段 `cour`，加上 `les chats` 完全一致，字符级匹配度不低。
- **第 3 行（意思全错）**：精确率 `[0.5, 0, 0, 0]`，BLEU 同样为 0——**BLEU 无法区分第 2 行和第 3 行**。chrF 给 34.8，低于第 2 行，排序正确，这就是讲义说的"chrF catches morphological partials BLEU misses"。
- **第 4 行（只有一个词）**：2-gram 都不存在，精确率按 0 处理，BLEU 为 0（即使不归零，BP 也只有 `exp(-3) ≈ 0.05`）。chrF 为 14.0：召回很低，但因为缺失的 4–6 阶被跳过，精确率按满分计，所以分数还"不算太低"。
- 末尾三行说明：无平滑的问题、BLEU 差距小于 1 是噪声、真实工作用 sacrebleu。（本环境没有安装 sacrebleu，所以无法在这里直接对比两者的数值。）

---

## 7. 动手改一改

1. **多参考 BLEU**：让 `simple_bleu` 接受参考译文列表，截断上限取各参考中该 n-gram 的最大计数；简短惩罚使用与候选长度最接近的参考长度。
2. **加平滑**：实现"n ≥ 2 时分子分母各加 1"的平滑版本，重新跑 4 个用例，观察第 2、3 行的排序是否合理（参考测验 Q8，会发现一个反直觉的结果）。
3. **语料级 BLEU**：实现 `corpus_bleu(hyps, refs)`，汇总计数后统一计算，与句级平均对比（参考测验 Q10）。
4. **对齐 sacrebleu 的 chrF**：去掉空白字符再取字符 n-gram，并把缺失阶数按 0 计入平均，比较 4 个用例分数的变化。
5. **β 的影响**：把 `chrf` 的 `beta` 改为 1 和 3，观察偏长的第 2 行和偏短的第 4 行分数如何变化，解释原因。
6. **进阶**：在本地装好 `sacrebleu` 后（本节环境未安装），用 `sacrebleu.corpus_bleu` 和 `sacrebleu.corpus_chrf` 跑同样的用例，逐项解释与本实现的差异。

---

## 8. 常见坑

- **自己写 BLEU 然后和论文比**：分词、大小写、平滑、语料级/句级的任何差异都会改变数值；讲义："Rolling your own BLEU computation is how misleading benchmarks happen."
- **用句级 BLEU 评判单条译文**：短句经常为 0，加平滑后又可能把错误译文抬得比正确改写还高。
- **忘记截断**：不做 `min(count, ref_count)` 时，重复词会刷高精确率。
- **把 BLEU 当语义指标**：BLEU 对改写不敏感，上线决策应结合 chrF/COMET 和人工评估。
- **边界情况未定义**：空候选、比 n 还短的候选、全为 0 的精确率——每种实现的处理方式不同，分数也就不同。
