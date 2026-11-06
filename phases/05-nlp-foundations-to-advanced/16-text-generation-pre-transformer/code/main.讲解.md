# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 16 节 Transformers 之前的文本生成 — N-gram 语言模型 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`collections.Counter / defaultdict`）

---

## 1. 这份代码在考察什么

这是一个**完整但迷你**的 bigram 语言模型：训练（计数）→ 平滑（两种）→ 评估（困惑度）→ 生成（采样），全部不到 120 行：

1. **语言模型 = 计数 + 归一化**：`P(w | prev) = c(prev, w) / c(prev)`，加上 `<s>`/`</s>` 边界符。
2. **两种平滑对比**：Laplace（加一）和插值 Kneser-Ney，在同一个测试集上看困惑度差多少。
3. **Kneser-Ney 的三个部件**：折扣后的主项、由折扣释放出来的权重 `λ`、接续概率 `continuation`。
4. **困惑度的计算细节**：`</s>` 也要计分、对数概率求平均、取指数；以及 `1e-12` 地板这类"隐藏约定"。
5. **按概率采样生成**：轮盘赌采样，观察 n-gram 生成"局部看似通顺、整体不知所云"——在 10 句的小语料上，连局部通顺都很勉强。

> 一句话：**今天的 GPT 仍在玩"预测下一个 token"的同一个游戏**；这份代码让你用最原始的玩家（只记得前 1 个词）把整套流程跑一遍。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tokenize(text)` | 函数 | 小写，把 `.`、`,` 拆成独立 token，按空白切分 | 分词 |
| `train_bigrams(sentences)` | 函数 | 统计 bigram 计数、unigram 计数、每个词的前驱集合 | MLE 计数 |
| `kneser_ney_prob(...)` | 函数 | 插值 KN bigram 概率 | 绝对折扣 + 接续概率 |
| `laplace_prob(...)` | 函数 | 加一平滑 bigram 概率 | Laplace 平滑 |
| `perplexity(prob_fn, sentences)` | 函数 | 平均负对数似然的指数 | 困惑度 |
| `sample_sentence(prob_fn, vocab, max_len, seed)` | 函数 | 从 `<s>` 开始逐词按概率采样直到 `</s>` | 生成 |
| `main()` | 函数 | 10 句训练、2 句测试；打印两种困惑度和 3 个采样句 | — |
| `kn` / `lap`（`main` 内部） | 闭包 | 把一堆统计量"绑定"进去，对外只暴露 `(prev, w)` 接口 | 统一的概率函数接口 |

数据流：`raw` →（`tokenize`）→ `train` → `train_bigrams` 得到三种统计 → `main` 再算出 `context_totals`、`unique_follow`、`total_unique_bigrams` → 封装成 `kn(prev, w)` 与 `lap(prev, w)` → 交给 `perplexity` 和 `sample_sentence`。两个下游函数只依赖"给 `(prev, w)` 返回概率"这一接口，所以可以无缝切换平滑方法。

---

## 3. 逐段精讲

### 3.1 分词：把标点变成 token

```python
def tokenize(text):
    return text.lower().replace(".", " .").replace(",", " ,").split()
```

- 在 `.`、`,` 前面加空格，`split()` 后它们就成了独立 token。句号作为 token 很重要：模型要学会"`.` 之后通常是 `</s>`"。
- ⚠️ 极简规则：`"3.14"` 会被拆成 `3` 和 `.14`，`"It's"` 保持整体，`!`、`?` 不处理。对本节手写的语料足够。

### 3.2 训练：三种统计一次收集

```python
def train_bigrams(sentences):
    bigrams = Counter()
    unigrams = Counter()
    unigram_contexts = defaultdict(set)
    for sentence in sentences:
        padded = ["<s>"] + sentence + ["</s>"]
        for i, w in enumerate(padded):
            unigrams[w] += 1
            if i > 0:
                prev = padded[i - 1]
                bigrams[(prev, w)] += 1
                unigram_contexts[w].add(prev)
    return bigrams, unigrams, unigram_contexts
```

- **填充**：`<s>` 让第一个词也有上下文（`P(the | <s>)` 学到"句子通常以 the 开头"），`</s>` 让模型学会何时结束。bigram 只需要 1 个 `<s>`；trigram 需要 2 个（讲义 Step 1 的 `["<s>"] * (n - 1)`）。
- `bigrams[(prev, w)]`：元组作为字典键，记录 `prev → w` 出现次数。
- `unigrams[w]`：每个 token（含 `<s>`、`</s>`）的出现次数。
- `unigram_contexts[w]`：w **前面出现过哪些不同的词**——这是 KN 接续概率的原料。用 `defaultdict(set)`，第一次访问自动创建空集合；用 `set` 保证同一个前驱只记一次。

### 3.3 Kneser-Ney：三个部件

```python
def kneser_ney_prob(bigrams, unigram_contexts, context_totals, unique_follow, total_unique_bigrams, prev, w, discount=0.75):
    count = bigrams.get((prev, w), 0)
    denom = context_totals.get(prev, 0)
    continuation = len(unigram_contexts.get(w, set())) / max(total_unique_bigrams, 1)
    if denom == 0:
        return continuation or 1e-9
    first = max(count - discount, 0) / denom
    lam = discount * len(unique_follow[prev]) / denom
    return first + lam * continuation
```

公式：`P_KN(w | prev) = max(c(prev,w) - D, 0)/c(prev) + λ(prev)·P_cont(w)`

| 变量 | 含义 | 本语料例子 |
|------|------|-----------|
| `count` | `c(prev, w)` | `c(cat, sat) = 1` |
| `denom` | `c(prev)`，prev 作为上下文的总次数 | `c(cat) = 6` |
| `continuation` | w 的不同前驱数 / 不同 bigram 类型总数 | `sat`：3/50 = 0.06 |
| `first` | 折扣后的主项 | `(1 - 0.75)/6 ≈ 0.042` |
| `lam` | `D × prev 的不同后继数 / c(prev)` | `0.75 × 6/6 = 0.75` |

- **为什么 λ 这样算**：prev 有几种不同后继，就有几个 bigram 各被扣了 D，扣下来的总量正好是 `D × 不同后继数`，除以 `c(prev)` 就是被释放的概率质量。把它按接续分布重新分配，总概率仍为 1（已实测对 `the`、`cat`、`.` 求和均为 1.0）。
- **`max(count - discount, 0)`**：没见过的 bigram 计数为 0，减完是负数，夹到 0。
- **`denom == 0`** 的分支：prev 从未作为上下文出现（例如未登录词），没有可折扣的主项，直接退到接续概率；`continuation or 1e-9` 表示"接续概率为 0 时给一个极小值"。
- `max(total_unique_bigrams, 1)` 防止空语料除零。
- ⚠️ `unique_follow[prev]` 是 `defaultdict`，访问不存在的 prev 会**悄悄插入一个空集合**；这里因为前面已经判断过 `denom == 0` 就返回，实际不会触发，但这是 `defaultdict` 的常见副作用。
- ⚠️ 未登录词 w 在 `denom > 0` 时得到的概率是 **0**（`count = 0`、`continuation = 0`），留给 `perplexity` 的 `1e-12` 地板处理。
- 函数签名有 8 个参数，是为了让它成为"纯函数"（不依赖全局状态）；`main` 再用闭包把前 5 个统计量绑定进去。

### 3.4 Laplace：加一

```python
def laplace_prob(bigrams, unigrams, vocab_size, prev, w):
    num = bigrams.get((prev, w), 0) + 1
    den = unigrams.get(prev, 0) + vocab_size
    return num / den
```

- 分子加 1、分母加 V：假装每个词都在 prev 后面多出现了一次，所以 `Σ_w P = (c(prev) + V)/(c(prev) + V) = 1`。
- 用 `unigrams[prev]` 当分母：除了 `</s>`，每个 token 后面都必然跟一个 token，所以它等于 prev 作为上下文的次数。
- ⚠️ `vocab_size = 28` 包含了 `<s>`，而 `<s>` 永远不会作为"下一个词"出现——Laplace 白白分给它一份质量。影响很小，但说明了"词表定义"本身就是一个需要小心的细节。
- 对比：`P_Laplace(the | on) = (3+1)/(3+28) ≈ 0.129`，而 `on` 后面 3 次都是 `the`，KN 给出 0.79。V 一大，加一平滑就严重稀释真实观测。

### 3.5 困惑度

```python
def perplexity(prob_fn, sentences):
    total_log = 0.0
    total = 0
    for sentence in sentences:
        padded = ["<s>"] + sentence + ["</s>"]
        for i in range(1, len(padded)):
            p = prob_fn(padded[i - 1], padded[i])
            total_log += math.log(max(p, 1e-12))
            total += 1
    return math.exp(-total_log / total)
```

- 对应公式 `PPL = exp(-(1/N)·Σ log P(w_i | w_{i-1}))`。
- `range(1, len(padded))`：从第一个真实词开始，到 `</s>` 结束——**`</s>` 计入 N，`<s>` 不计入**（`<s>` 是给定的，不需要预测）。
- **对数相加而不是概率相乘**：几十个小于 1 的数相乘很快下溢成 0.0，取对数后变成加法，数值稳定。
- `max(p, 1e-12)`：防止 `log(0)` 抛 `ValueError`。⚠️ 这是一个**会显著影响结果的隐藏约定**：含 OOV 的句子 `"the zebra sat ."` 困惑度会被这个地板推到约 774。正规做法是用 `<UNK>`（见测验 Q10）。
- 用自然对数 + `exp`，即 nat 单位；改成 `log2` + `2**` 结果完全相同。

### 3.6 采样生成

```python
def sample_sentence(prob_fn, vocab, max_len=15, seed=0):
    rng = random.Random(seed)
    tokens = ["<s>"]
    for _ in range(max_len):
        probs = [(w, prob_fn(tokens[-1], w)) for w in vocab if w != "<s>"]
        total = sum(p for _, p in probs)
        r = rng.random() * total
        acc = 0.0
        for w, p in probs:
            acc += p
            if r <= acc:
                tokens.append(w)
                break
        if tokens[-1] == "</s>":
            return tokens[1:-1]
    return tokens[1:]
```

- 每一步只看 `tokens[-1]`——这就是 bigram 的"1 个 token 记忆"。
- 排除 `<s>`：句首标记不应在句中被生成。
- **轮盘赌采样**：`r` 落在哪个累积区间就选哪个词；先求 `total` 再乘，等于顺便做了归一化（KN 给 `<s>` 的概率本来就是 0；若换成 Laplace，排除 `<s>` 后总和略小于 1，这样写依然正确）。
- 生成 `</s>` 就停止，返回时去掉首尾标记；达到 `max_len` 仍没结束则返回已生成部分（没有 `</s>`）。
- `random.Random(seed)`：每个 seed 有独立的随机序列，输出可复现。

### 3.7 `main`：用闭包统一接口

```python
    context_totals = Counter()
    unique_follow = defaultdict(set)
    for (prev, w), c in bigrams.items():
        context_totals[prev] += c
        unique_follow[prev].add(w)
    total_unique_bigrams = sum(len(ctx_set) for ctx_set in unigram_contexts.values())

    def kn(prev, w):
        return kneser_ney_prob(bigrams, unigram_contexts, context_totals, unique_follow, total_unique_bigrams, prev, w)

    def lap(prev, w):
        return laplace_prob(bigrams, unigrams, vocab_size, prev, w)
```

- 遍历一次 bigram 表，同时得到 `c(prev)`（`context_totals`）和 prev 的不同后继集合（`unique_follow`）。
- `total_unique_bigrams`：每个词的不同前驱数之和 = 不同 bigram 类型总数（本语料为 50）。
- `kn`、`lap` 是定义在 `main` 内部的**闭包**：它们"记住"了外层的统计量，对外只有 `(prev, w)` 两个参数。这样 `perplexity(kn, test)` 和 `perplexity(lap, test)` 可以用同一份评估代码——典型的**策略模式**。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只做 bigram | 代码最短，KN 公式最清楚 | 上下文只有 1 个词；生产用 3–5 gram（skill：通用英语 trigram，语音重打分 5-gram） |
| 固定折扣 D=0.75 | 讲义 / 经典默认值 | 小语料上过大（见第 6 节）；生产用 Modified KN（按计数 1、2、3+ 分别折扣） |
| 概率函数做成 `(prev, w)` 闭包 | 评估和生成代码与平滑方法解耦 | — |
| `1e-12` 概率地板 | 防止 `log(0)` 崩溃 | 会严重放大 OOV 惩罚、且不同实现不可比；应使用 `<UNK>` 或子词 |
| 每步遍历整个词表采样 | 直观 | O(V) 每步；大词表用预计算的累积分布或别名表 |
| 纯 Python 字典计数 | 零依赖 | 大语料内存爆炸；生产用 KenLM（压缩的 trie / 哈希结构） |
| 教学语料 10 句 | 秒出结果、可手算 | 统计意义很弱，困惑度和采样质量都只能看趋势 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 方法链 | `text.lower().replace(".", " .").replace(",", " ,").split()` | 每个方法返回新字符串，可以连续调用 |
| 列表拼接 | `["<s>"] + sentence + ["</s>"]` | `+` 生成新列表，不修改原列表 |
| 元组作字典键 | `bigrams[(prev, w)] += 1` | 元组不可变、可哈希，可以当键；列表不行 |
| `collections.Counter` | `bigrams = Counter()` | 缺失键默认 0 的计数字典 |
| `collections.defaultdict(set)` | `unigram_contexts[w].add(prev)` | 第一次访问自动创建空集合 |
| `dict.get(key, default)` | `bigrams.get((prev, w), 0)`、`unigram_contexts.get(w, set())` | 不存在时返回默认值，且不插入新键（与 `defaultdict[...]` 不同） |
| 解包遍历字典项 | `for (prev, w), c in bigrams.items()` | 键本身是元组，可以嵌套解包 |
| `or` 返回值 | `return continuation or 1e-9` | `a or b`：a 为假值（如 0.0）时返回 b |
| 默认参数 | `discount=0.75`、`max_len=15, seed=0` | 调用时可省略 |
| 嵌套函数 / 闭包 | `def kn(prev, w): return kneser_ney_prob(...)` | 内部函数捕获外层变量，形成固定了部分参数的新函数 |
| 函数作为参数 | `perplexity(kn, test)` | 函数是一等对象，可以像变量一样传递 |
| 列表推导式 + 条件 | `[(w, prob_fn(tokens[-1], w)) for w in vocab if w != "<s>"]` | 生成 `(词, 概率)` 列表并过滤 |
| 负索引与切片 | `tokens[-1]`、`tokens[1:-1]` | 最后一个元素；去掉首尾 |
| `math.log` / `math.exp` | `math.log(max(p, 1e-12))`、`math.exp(-total_log / total)` | 自然对数与指数 |
| 生成器表达式 | `sum(p for _, p in probs)` | 不建中间列表直接求和 |
| f-string | `f"perplexity (Laplace):     {perplexity(lap, test):.2f}"` | 表达式可以直接写在花括号里 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13，约 0.02 秒）输出：

```text
vocab size: 28
train sentences: 10
test sentences: 2

perplexity (Laplace):     10.29
perplexity (Kneser-Ney):  4.42

=== sampled sentences (Kneser-Ney, 3 seeds) ===
  seed=1: the under a sat on the dog chased the the hid ran after the .
  seed=7: the cat chased the ran .
  seed=42: the the cat sat dog a bird the . .
```

- **vocab size 28**：25 个真实词 + `.` + `<s>` + `</s>`。
- **困惑度 10.29 vs 4.42**：KN 比 Laplace 低约 57%。两句测试句的分项（实测）：`the cat sat on the couch .` 为 KN 3.47 / Laplace 9.27；`the dog watched the mouse .` 为 KN 5.82 / Laplace 11.59。第二句含训练中没见过的 `dog watched`，所以两种方法都更困惑。Laplace 的问题在于每个上下文都要分 28 份"假计数"，真实观测（如 `on → the`）被稀释。
- **采样句子质量很差**：`the the`、`. .`、`the under a sat`……原因是 D=0.75 对这个小语料太大：几乎每个 bigram 只出现 1 次，折扣后只剩 0.25，大部分质量经由 λ 交给接续分布。例如 `λ(the) = 0.75×11/17 ≈ 0.485`，`P_cont(the) = 8/50 = 0.16`，于是 `P(the | the) ≈ 0.078`，比训练中真实出现过的 `the couch`（≈0.024）还高。
- **调小折扣的效果**（已实测）：D=0.1 时测试困惑度降到 3.56，seed=7 生成 `the cat chased the dog ran ran across the room .`，明显更像句子。这说明 0.75 是**大语料上的经验值**，不是普适常数。
- 即使改善之后，句子也只是"局部可读、整体无意义"——这正是讲义说的 n-gram 只有 n-1 个 token 的记忆。

---

## 7. 动手改一改

1. **调折扣**：把 `discount` 改成参数，扫描 0.1 / 0.5 / 0.75 / 0.9，记录测试困惑度和采样句子。
2. **贪心与温度**：实现 `temperature=0` 时取 argmax（结果会是 `the cat .`），以及 `p ** (1/T)` 重加权采样，比较 T=0.5、1、2。
3. **加 `<UNK>`**：训练时把只出现 1 次的词替换为 `<UNK>`，测试时把 OOV 映射到 `<UNK>`，对比 `"the zebra sat ."` 的困惑度（不加约 774，加后约 4.5，但词表变了，不能与原数字直接比较）。
4. **升级到 trigram**：按讲义 Step 1 的 `train_ngram(n=3)` 计数，KN 的低阶回退改用 bigram KN，再看采样质量。
5. **验证归一化**：写一个断言，对词表中每个 prev 检查 `abs(sum(kn(prev, w) for w in vocab) - 1) < 1e-9`。
6. **Shannon 视角**：把困惑度换算成 bits/token（`log2(PPL)`），比较 KN 和 Laplace 每个 token 省下了多少 bit。

---

## 8. 常见坑

- **忘记 `</s>`**：模型学不会结束，困惑度也少算了"预测结束"这一步。
- **概率连乘下溢**：长句子概率乘积会变成 0.0；必须在对数空间累加。
- **`log(0)`**：任何未平滑的零概率都会让 `math.log` 报错或困惑度变成无穷；`1e-12` 地板只是止血，不是平滑。
- **不同分词 / 不同 OOV 处理下比较困惑度**：数字没有可比性。
- **以为 D=0.75 放之四海而皆准**：小语料上过大，大语料上才合适；更好的是 Modified KN。
- **`defaultdict` 的副作用**：用 `d[key]` 读取不存在的键会插入新键，统计"有多少个上下文"时可能被悄悄改变；只读时用 `.get()`。
