# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 07 节 词性标注和句法分析 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅 Python 标准库（`math`、`collections.Counter / defaultdict`）

---

## 1. 这份代码在考察什么

这份代码在 6 句手工标注的玩具语料上，从零实现两个经典 POS 标注器，并在 3 个测试句上对比：

1. **最频繁标签基线（MFT）**：每个词取训练集中最常见的标签，未登录词回退到全局最常见标签——任何模型都必须先超过的"地板"。
2. **二元 HMM 的训练**：只靠计数，得到转移表 `P(tag | 前一个 tag)` 和发射表 `P(word | tag)`，用 `<BOS>` / `<EOS>` 标记句子边界。
3. **add-α 平滑**：没见过的事件不能是 0 概率，否则 log 会爆掉、整条路径直接"死亡"。
4. **Viterbi 动态规划**：在标签网格上求概率最大的整条标签序列，并用回溯指针还原路径。
5. **看清 HMM 的局限**：真实输出里 `chased` 被标成了 `AUX`——小数据 + 平滑偏差 + 只看局部，正是讲义说"现代标注器能打败它"的原因。

> 一句话：**用不到 100 行代码，把"计数 → 概率 → 动态规划解码"这条经典 NLP 流水线走一遍**，理解 CRF、BiLSTM-CRF 乃至 seq2seq beam search 的源头。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TRAIN` | 模块级常量（列表） | 6 个 `(tokens, tags)` 训练样本，UD 风格标签 | 标注语料（treebank 的迷你版） |
| `train_mft(examples)` | 函数 | 统计每个词最常见的标签 + 全局默认标签 | 最频繁标签基线 |
| `predict_mft(tokens, word_best, default_tag)` | 函数 | 查表预测，查不到用默认标签 | 基线推理、OOV 回退 |
| `train_hmm(examples, alpha)` | 函数 | 统计转移计数、发射计数、标签集、词表 | HMM 参数的极大似然估计（计数） |
| `log_prob(table, given, key, smooth_denom, alpha)` | 函数 | 计算平滑后的 log 概率 | add-α 平滑、log 空间 |
| `viterbi(tokens, ...)` | 函数 | 动态规划求最优标签序列 | Viterbi 解码 |
| `main()` | 函数 | 训练两个模型，对 3 句测试句打印对比 | 演示入口 |

数据流：`TRAIN → train_mft → predict_mft` 与 `TRAIN → train_hmm → viterbi(内部调用 log_prob)` 两条线并行，最后在 `main()` 里逐句并排打印。

---

## 3. 逐段精讲

### 3.1 训练数据：6 句话、7 个 UD 标签

```python
TRAIN = [
    (["The", "cat", "sat", "on", "the", "mat"], ["DET", "NOUN", "VERB", "ADP", "DET", "NOUN"]),
    (["A", "dog", "ran", "across", "the", "road"], ["DET", "NOUN", "VERB", "ADP", "DET", "NOUN"]),
    (["Cats", "chase", "mice"], ["NOUN", "VERB", "NOUN"]),
    (["Dogs", "bark", "loudly"], ["NOUN", "VERB", "ADV"]),
    (["The", "mat", "is", "red"], ["DET", "NOUN", "AUX", "ADJ"]),
    (["A", "red", "cat", "sat"], ["DET", "ADJ", "NOUN", "VERB"]),
]
```

- 每个样本是"词列表 + 等长标签列表"的元组，这正是 CoNLL 格式树库在内存中的样子。
- 标签用的是 **UD 标签集**（`DET`、`NOUN`、`VERB`、`ADP`、`AUX`、`ADJ`、`ADV`），不是 PTB 的 `DT/NN/VBD`。
- 统计一下会发现分布非常不均：`NOUN` 9 次、`DET` 6 次、`VERB` 5 次、`ADP`/`ADJ` 各 2 次、`AUX`/`ADV` 各 1 次。这种不均衡在 3.6 节会直接导致一个"错得有道理"的结果。
- ⚠️ 刻意的简化：真实的 Brown / PTB 语料有上百万词，这里 6 句只够演示机制，**不能用来评估准确率**。

### 3.2 最频繁标签基线：`train_mft` / `predict_mft`

```python
def train_mft(examples):
    word_tag_counts = defaultdict(Counter)
    all_tags = Counter()
    for tokens, tags in examples:
        for token, tag in zip(tokens, tags):
            word_tag_counts[token.lower()][tag] += 1
            all_tags[tag] += 1
    word_best = {w: c.most_common(1)[0][0] for w, c in word_tag_counts.items()}
    default_tag = all_tags.most_common(1)[0][0]
    return word_best, default_tag


def predict_mft(tokens, word_best, default_tag):
    return [word_best.get(t.lower(), default_tag) for t in tokens]
```

- `defaultdict(Counter)`：第一次访问 `word_tag_counts["cat"]` 时自动创建一个空 `Counter`，省去 `if key not in d` 的判断。结构是"词 → {标签: 次数}"。
- `c.most_common(1)[0][0]`：`most_common(1)` 返回 `[(标签, 次数)]`，取 `[0][0]` 得到标签本身。
- `default_tag`：全局最常见标签，本数据中是 `NOUN`（9 次）。未登录词一律标 `NOUN`——这在真实语料上也是合理的：新词（专有名词、术语）大多是名词。
- `token.lower()`：把 `The` 和 `the` 合并统计，缓解数据稀疏。
- ⚠️ 代价：小写化丢掉了"首字母大写 → 可能是专有名词"的信号。讲义技能卡也提醒，消费 POS 的管线要正确处理大小写变体。
- 讲义数字：在 Brown 语料上这个基线约 85%；它完全不看上下文，所以 `saw`（名词/动词）这种歧义词永远只能标成同一个标签。

### 3.3 HMM 训练：只是数数

```python
def train_hmm(examples, alpha=0.01):
    transitions = defaultdict(Counter)
    emissions = defaultdict(Counter)
    tags = set()
    vocab = set()
    for tokens, ts in examples:
        prev = "<BOS>"
        for token, tag in zip(tokens, ts):
            transitions[prev][tag] += 1
            emissions[tag][token.lower()] += 1
            tags.add(tag)
            vocab.add(token.lower())
            prev = tag
        transitions[prev]["<EOS>"] += 1
    return transitions, emissions, tags, vocab
```

- 对应讲义公式 `P(tags, words) = Π P(tagᵢ | tagᵢ₋₁) · P(wordᵢ | tagᵢ)`：
  - `transitions[prev][tag]`：前一个标签 → 当前标签的次数（转移）；
  - `emissions[tag][word]`：某标签下生成某词的次数（发射）。
- `prev = "<BOS>"`：每句开头用一个虚拟的"句首标签"，这样第一个词也有转移概率 `P(tag₀ | <BOS>)`，不需要单独建一张"初始概率表"。
- `transitions[prev]["<EOS>"] += 1`：记录"以某标签结尾"的次数。
- 训练出的转移表（实际打印验证过）：`NOUN → {VERB: 5, <EOS>: 3, AUX: 1}`、`DET → {NOUN: 5, ADJ: 1}`、`<BOS> → {DET: 4, NOUN: 2}`。模型已经学到了"`DET` 后面接 `NOUN`"——讲义说 MFT → HMM 的提升主要来自这种转移信息。
- ⚠️ 两个小瑕疵：①参数 `alpha` 在 `train_hmm` 里**完全没被使用**（平滑发生在解码时），只是签名上的摆设；②`<EOS>` 被统计了，但 `viterbi` 解码时**没有用到**（见 3.5）。

### 3.4 平滑后的 log 概率：`log_prob`

```python
def log_prob(table, given, key, smooth_denom, alpha):
    return math.log((table[given].get(key, 0) + alpha) / smooth_denom)
```

- 公式：`P(key | given) = (count(given, key) + α) / (count(given) + α·K)`，K 是可能取值的个数。这就是 add-α（α=1 时叫 Laplace）平滑，和朴素贝叶斯里的平滑是同一回事。
- 分母由调用方算好传进来，`viterbi` 中有两种：
  - 发射：`sum(emissions[tag].values()) + alpha * (len(vocab) + 1)`——`+1` 是给"未登录词 UNK"留的一个槽位；
  - 转移：`sum(transitions[prev].values()) + alpha * (len(tags_list) + 1)`——`+1` 是给 `<EOS>` 留的槽位。
- 为什么一定要平滑：没见过的组合计数为 0，`math.log(0)` 直接抛 `ValueError: math domain error`；即使不报错，概率为 0 也会让整条路径被一票否决。
- 为什么用 `.get(key, 0)` 而不是 `table[given][key]`：对 `Counter` 来说两者都返回 0，但 `.get` 语义更清楚（"查不到就当 0"）。注意 `table[given]` 本身仍然会在 `defaultdict` 中**插入一个空条目**——这是 `defaultdict` 的副作用，读操作也会写。
- α 取 0.01（很小）：尽量不扭曲真实计数。但 3.6 节会看到，即便很小的 α，对只出现 1 次的标签影响也很大。

### 3.5 Viterbi：初始化、递推、回溯

```python
def viterbi(tokens, transitions, emissions, tags, vocab, alpha=0.01):
    tags_list = list(tags)
    n = len(tokens)
    V = [[0.0] * len(tags_list) for _ in range(n)]
    back = [[0] * len(tags_list) for _ in range(n)]

    for j, tag in enumerate(tags_list):
        em_denom = sum(emissions[tag].values()) + alpha * (len(vocab) + 1)
        tr_denom = sum(transitions["<BOS>"].values()) + alpha * (len(tags_list) + 1)
        tr = log_prob(transitions, "<BOS>", tag, tr_denom, alpha)
        em = log_prob(emissions, tag, tokens[0].lower(), em_denom, alpha)
        V[0][j] = tr + em
        back[0][j] = 0
```

- `V[i][j]`：前 i+1 个词、且第 i 个词标为 `tags_list[j]` 的所有路径中，**最大**的 log 概率。`back[i][j]`：取得这个最大值时，前一个位置用的是哪个标签（下标）。
- `[[0.0] * T for _ in range(n)]`：必须用列表推导创建二维表。如果写成 `[[0.0] * T] * n`，n 行其实是**同一个列表对象**，改一行全变——经典坑。
- 初始化：`V[0][j] = log P(tag | <BOS>) + log P(w₀ | tag)`。
- `tags_list = list(tags)`：集合转成列表，固定一个下标顺序。集合的迭代顺序受字符串哈希随机化影响，但本数据中没有分数并列，所以结果稳定（换 5 个 `PYTHONHASHSEED` 实测输出一致）。

```python
    for i in range(1, n):
        for j, tag in enumerate(tags_list):
            em_denom = sum(emissions[tag].values()) + alpha * (len(vocab) + 1)
            em = log_prob(emissions, tag, tokens[i].lower(), em_denom, alpha)
            best_prev = 0
            best_score = -1e30
            for k, prev_tag in enumerate(tags_list):
                tr_denom = sum(transitions[prev_tag].values()) + alpha * (len(tags_list) + 1)
                tr = log_prob(transitions, prev_tag, tag, tr_denom, alpha)
                score = V[i - 1][k] + tr + em
                if score > best_score:
                    best_score = score
                    best_prev = k
            V[i][j] = best_score
            back[i][j] = best_prev
```

- 递推式：`V[i][j] = maxₖ ( V[i-1][k] + log P(tag_j | tag_k) ) + log P(wᵢ | tag_j)`。
- 为什么正确（最优子结构）：如果到达 (i, j) 的最优路径经过 (i-1, k*)，那么它的前缀一定也是到达 (i-1, k*) 的最优路径。于是每个格子只需要保留一个最优值，指数级的 `|T|ⁿ` 条路径被压缩为 `n·|T|` 个格子。
- `best_score = -1e30`：log 空间里的"负无穷"初值，保证第一个候选一定会更新它。
- ⚠️ 性能问题：`tr_denom` 在最内层循环里每次都 `sum(...)` 一遍（最多 `|T|+1` 项），使复杂度从标准的 `O(n·|T|²)` 退化为 `O(n·|T|³)`；`em_denom` 也被重复计算。教学代码为了"公式就地可见"牺牲了效率，生产实现应预计算分母和 log 概率表（测验 Q9 给出了改写）。
- `em` 与 `k` 无关，所以放在 `k` 循环之外，这一点写对了。

```python
    last_best = max(range(len(tags_list)), key=lambda j: V[n - 1][j])
    path = [last_best]
    for i in range(n - 1, 0, -1):
        path.append(back[i][path[-1]])
    return [tags_list[j] for j in reversed(path)]
```

- `max(range(T), key=lambda j: V[n-1][j])`：求 argmax 的惯用写法——在下标上取最大，比较依据是 `V[n-1][j]`。
- 回溯：从最后一个位置的最优标签出发，`back[i][当前标签]` 告诉我们前一个位置该用哪个标签，倒着走到位置 0，最后 `reversed` 翻转。
- ⚠️ 两个简化：
  1. 终止时没有加 `log P(<EOS> | tag)`，完整的 HMM 应该把"在此结束"的概率也算进去；
  2. 空输入 `tokens == []` 时 `n - 1 = -1`，`V[-1]` 访问空列表抛 `IndexError`，没有防御。

### 3.6 `main()`：一个"错得有道理"的结果

```python
    test_sentences = [
        "The cat chased the dog".split(),
        "A red mat is here".split(),
        "Dogs bark".split(),
    ]
```

- `str.split()` 按空白切分——第 01 节讲过的最朴素 tokenizer。
- 测试句里有训练集没见过的词：`chased`、`dog`（见过 `dog`）、`here`。重点看 `chased`：MFT 标 `NOUN`（默认标签），HMM 标 `AUX`，正确答案是 `VERB`，两个都错了。

为什么 HMM 选了 `AUX`？比较中间位置的三项因子（α=0.01，词表 18，标签 7 个）：

| 因子 | 标 `VERB` | 标 `AUX` |
|------|----------|---------|
| `P(x \| NOUN)` | 5.01 / 9.08 ≈ 0.552 | 1.01 / 9.08 ≈ 0.111 |
| `P(chased \| x)`，未登录词 | 0.01 / 5.19 ≈ 0.00193 | 0.01 / 1.19 ≈ 0.00840 |
| `P(DET \| x)`，未见过的转移 | 0.01 / 5.08 ≈ 0.00197 | 0.01 / 1.08 ≈ 0.00926 |
| 乘积 | ≈ 2.1e-6 | ≈ 8.7e-6 |

`AUX` 只出现过 1 次，分母小，α 这点"平滑质量"在它身上的占比就大：它对**任何未知事件**都比 `VERB` 慷慨 4～5 倍，两项未知事件叠加，压过了 `NOUN → VERB` 约 5 倍的转移优势。这就是 add-α 平滑对**稀有标签的系统性偏向**。真实系统会：只让开放类标签生成新词、用后缀 `-ed` 等特征估计未知词的发射、或者直接换 CRF / 神经网络。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 6 句手写语料 | 不依赖 NLTK 下载，几毫秒跑完，概率可以手算 | 统计量极不可靠；真实评估用 Brown/PTB/UD 树库并划分训练/测试集 |
| 全部 `.lower()` | 合并大小写变体，缓解稀疏 | 丢失大小写特征；生产中把"是否首字母大写"作为特征保留 |
| 未登录词统一为一个 UNK 槽位 | 实现最简单 | 产生稀有标签偏向；生产中用后缀/词形模型或子词表示 |
| add-α 平滑、α=0.01 | 一行公式、防止 log(0) | 对稀有事件估计粗糙；可用 Good-Turing、Kneser-Ney、或判别式模型 |
| log 空间计算 | 防止长句概率连乘下溢 | 几乎没有代价，是标准做法 |
| 分母在循环里就地计算 | 公式和代码一一对应，便于阅读 | 复杂度退化为 `O(n·\|T\|³)`；生产中预计算 log 概率矩阵并用 NumPy 向量化 |
| 解码不使用 `<EOS>` | 少写几行 | 模型不知道"哪些标签适合结尾"；完整实现应在终止步加入 |
| 不自己写依存分析器 | 讲义明确：从零写 parser 是研究项目 | 依存分析直接用 spaCy / stanza / trankit |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组列表 | `TRAIN = [(["The", ...], ["DET", ...]), ...]` | 用 `(输入, 标签)` 元组组织样本，便于解包 |
| 元组解包 + `for` | `for tokens, tags in examples:` | 每次迭代把元组拆成两个变量 |
| `zip` | `zip(tokens, tags)` | 把词和标签按位置配对 |
| `set` | `tags = set()`、`tags.add(tag)` | 自动去重，用来收集标签集和词表 |
| `collections.Counter` | `all_tags[tag] += 1`、`most_common(1)` | 计数字典，缺失键默认 0；`most_common(k)` 返回前 k 个 `(元素, 次数)` |
| `collections.defaultdict` | `defaultdict(Counter)` | 访问不存在的键时自动用工厂函数创建默认值；注意读也会插入 |
| 字典推导式 | `{w: c.most_common(1)[0][0] for w, c in word_tag_counts.items()}` | 一行构造"词 → 最常见标签"的映射 |
| `dict.get(key, default)` | `word_best.get(t.lower(), default_tag)` | 查不到时返回默认值，不抛 `KeyError` |
| 列表推导式 | `[word_best.get(...) for t in tokens]` | 逐词预测 |
| 二维列表初始化 | `[[0.0] * len(tags_list) for _ in range(n)]` | 每行是独立对象；`_` 表示不使用的循环变量 |
| `enumerate` | `for j, tag in enumerate(tags_list):` | 同时拿下标和元素，下标用于索引 `V`、`back` |
| 倒序 `range` | `range(n - 1, 0, -1)` | 从 n-1 递减到 1（不含 0），用于回溯 |
| `max` + `key` + `lambda` | `max(range(T), key=lambda j: V[n - 1][j])` | 求 argmax 的惯用法 |
| `reversed` | `for j in reversed(path)` | 反向迭代，不复制列表 |
| `math.log` | `math.log((count + alpha) / denom)` | 自然对数；参数必须 > 0 |
| f-string | `f"  mft : {mft}"` | 直接把列表的 `repr` 嵌入字符串 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，仅标准库）的完整输出：

```text
tokens: ['The', 'cat', 'chased', 'the', 'dog']
  mft : ['DET', 'NOUN', 'NOUN', 'DET', 'NOUN']
  hmm : ['DET', 'NOUN', 'AUX', 'DET', 'NOUN']

tokens: ['A', 'red', 'mat', 'is', 'here']
  mft : ['DET', 'ADJ', 'NOUN', 'AUX', 'NOUN']
  hmm : ['DET', 'ADJ', 'NOUN', 'AUX', 'ADJ']

tokens: ['Dogs', 'bark']
  mft : ['NOUN', 'VERB']
  hmm : ['NOUN', 'VERB']
```

逐句解读：

- **句 1**：`The/the/cat/dog` 都在训练集里，两个模型都对。`chased` 是未登录词：MFT 回退到默认标签 `NOUN`（错）；HMM 因为稀有标签偏向（3.6 节）选了 `AUX`（也错，正确是 `VERB`）。这说明讲义"HMM 比基线高约 8 个点"是**大语料上的统计结论**，在 6 句话的数据上并不成立。
- **句 2**：`here` 是未登录词（正确标签是 `ADV`）。MFT 给 `NOUN`；HMM 看到前面是 `AUX`，而训练中 `AUX` 唯一的后继是 `ADJ`（"is red"），转移概率 ≈ 0.935，于是标成 `ADJ`——转移信息在起作用，只是训练数据里没有 "is + 副词" 的例子。
- **句 3**：`Dogs bark` 是训练集原句的前缀，两者都完全正确。
- 稳定性：用 5 个不同的 `PYTHONHASHSEED` 重复运行，HMM 输出一致，说明 `list(set)` 的顺序不影响结果（没有并列分数）。

---

## 7. 动手改一改

1. **加训练句看变化**：在 `TRAIN` 里加一句 `(["The", "dog", "chased", "a", "cat"], ["DET", "NOUN", "VERB", "DET", "NOUN"])`，重新运行，确认 `chased` 变成 `VERB`。
2. **调 α**：把 `viterbi` 的 `alpha` 分别改为 `1.0` 和 `0.0001`，观察句 1 和句 2 的输出如何变化，体会平滑强度对稀有标签的影响。
3. **补上 `<EOS>`**：在 `viterbi` 结尾选 `last_best` 时加上 `log P(<EOS> | tag)`，并让空输入返回 `[]`（参考测验 Q10）。
4. **提速**：预计算 `tr_denom` / `em_denom` 和 log 转移矩阵，把复杂度降到 `O(n·|T|²)`；再用 `time.perf_counter()` 对比 PTB 规模（45 个标签）下的耗时（参考测验 Q9）。
5. **未登录词后缀模型**：对 OOV 词，若以 `-ed`/`-ing` 结尾则只在 `VERB` 上给较高发射概率、以 `-ly` 结尾偏向 `ADV`，看句 1、句 2 是否改善。
6. **对比 spaCy**（需自行安装，非本节必需）：用讲义中的 spaCy 代码解析同样 3 句话，打印 `tag_ / pos_ / dep_ / head`，对照你的 HMM 输出。

---

## 8. 常见坑

- **`[[0.0] * T] * n` 浅拷贝陷阱**：二维表必须用列表推导创建，否则所有行共享同一个列表。
- **忘了平滑就取 log**：任何未见过的转移或词都会让 `math.log(0)` 报错。
- **平滑分母的 K 数错**：发射分母要包含 UNK 的槽位，转移分母要包含 `<EOS>` 的槽位，否则概率之和不为 1；本代码用 `+1` 处理了这两点。
- **`defaultdict` 读操作也会插入键**：`transitions[prev_tag]` 对不存在的标签会悄悄加一个空 `Counter`，在需要遍历表的统计代码里可能出现"多出来的键"。
- **在小数据上评估模型优劣**：6 句话上 HMM 不比 MFT 好，不能据此得出任何结论；准确率对比要在标准树库的独立测试集上做。
- **忽视大小写**：统一小写简单粗暴，但会让专有名词识别变难；生产中应保留大小写特征。
