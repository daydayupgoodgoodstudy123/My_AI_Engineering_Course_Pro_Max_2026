# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到高级 · 第 04 节 GloVe、FastText 和 Subword Embeddings ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，瞬间完成） ｜ **依赖**：仅 Python 标准库（`collections.Counter`），不需要 NumPy / fasttext / transformers

---

## 1. 这份代码在考察什么

讲义覆盖了 GloVe、FastText、BPE 三种方法，而这份 `main.py` 只实现了其中**与"子词"相关的两块**（GloVe 的训练代码和 `fasttext_vector` 只在讲义中给出，没有放进脚本）：

1. **FastText 的字符 n-gram**：一个词如何被拆成 3–6 个字符的片段，为什么 `<`、`>` 边界标记很重要，以及 `where` 与 `whereupon` 共享多少片段——这正是 FastText 能处理未登录词（OOV）的根基。
2. **BPE 的训练（`learn_bpe`）**：从字符出发，反复"统计相邻对 → 合并最频繁的一对"，得到一张**有序**的合并表。
3. **BPE 的编码（`apply_bpe`）**：按学习顺序把合并规则应用到新词上，理解"合并顺序决定切分"。
4. **子词 tokenizer 的本质**：任何词都能被切成已知片段，于是"没有 OOV"——这是现代所有 LLM tokenizer 的共同出发点。

> 一句话：**FastText 用"固定规则的片段"、BPE 用"从数据里学出来的片段"，二者都把"词"拆成更小的、可复用的单位。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `char_ngrams(word, n_min=3, n_max=6)` | 函数 | 给词加上 `<…>` 后，取所有长度 3–6 的子串，再加上整词，返回集合 | FastText 子词 |
| `learn_bpe(corpus, k_merges)` | 函数 | 输入 `{词: 词频}`，返回按顺序学到的合并规则列表 `[(a, b), ...]` | BPE 训练 |
| `apply_bpe(word, merges)` | 函数 | 把一个词拆成字符 + `</w>`，按顺序应用合并规则，返回 token 列表 | BPE 编码 |
| `main()` | 函数 | 演示 n-gram 数量与重叠；在 6 词玩具语料上学 10 条合并并切分 4 个测试词 | 演示入口 |

数据流分两条互不相关的线：① `word → char_ngrams → 集合运算（交集）`；② `Counter 语料 → learn_bpe → merges → apply_bpe(新词) → tokens`。

---

## 3. 逐段精讲

### 3.1 `char_ngrams`：FastText 的子词集合

```python
def char_ngrams(word, n_min=3, n_max=6):
    wrapped = f"<{word}>"
    grams = {wrapped}
    for n in range(n_min, n_max + 1):
        for i in range(len(wrapped) - n + 1):
            grams.add(wrapped[i:i + n])
    return grams
```

- **边界标记 `<`、`>`**：让"出现在词首/词尾的片段"与"出现在词中间的片段"区分开。例如 `<wh` 只可能来自以 `wh` 开头的词，`re>` 只可能来自以 `re` 结尾的词——前缀、后缀（往往对应词形变化）因此有了专门的向量。
- **整词本身也是一个元素**：`grams = {wrapped}` 先放入 `<where>`，所以常见词仍有一个"专属向量"，n-gram 只是补充。
- **双重循环**：外层遍历长度 n = 3..6，内层用滑动窗口 `wrapped[i:i+n]` 取所有长度为 n 的子串；`len(wrapped) - n + 1` 是窗口能放下的位置数。
- **用集合（set）**：同一个片段在词中出现多次时只算一次；短词的某个 n-gram 恰好等于整词（如 `char_ngrams("a")` 只有 `{'<a>'}`）时也会自动去重。
- `where` 的结果：`<where>` 长度 7，n=3/4/5/6 分别得到 5/4/3/2 个片段，加上整词共 **15** 个。（讲义正文展示的结果只列了 13 个，漏掉了 `<where` 和 `where>`，以代码运行结果为准。）
- ⚠️ 讲义里的 `fasttext_vector(word, ngram_table)`——把已知 n-gram 的向量求和得到词向量——没有放进本脚本。真实 FastText 还会把海量 n-gram **哈希**到固定数量的桶里以控制内存，这里也没有涉及。

### 3.2 `learn_bpe`（上）：初始化与统计相邻对

```python
def learn_bpe(corpus, k_merges):
    vocab = {}
    for word, freq in corpus.items():
        tokens = tuple(word) + ("</w>",)
        vocab[tokens] = freq

    merges = []
    for _ in range(k_merges):
        pair_freq = Counter()
        for tokens, freq in vocab.items():
            for a, b in zip(tokens, tokens[1:]):
                pair_freq[(a, b)] += freq
        if not pair_freq:
            break
        best = pair_freq.most_common(1)[0][0]
        merges.append(best)
        # ...
```

- **输入是"词 → 词频"**，而不是整段文本：BPE 只在词内部合并，先把语料统计成词频表，可以避免对同一个词重复计算。
- `tuple(word) + ("</w>",)`：把 `"low"` 变成 `('l', 'o', 'w', '</w>')`。用**元组**是因为它要作字典的键（列表不可哈希）。`</w>` 是**词尾标记**，让 `st</w>`（词尾的 st）和词中间的 `st` 成为不同的 token，解码时也能知道词在哪里结束。
- `zip(tokens, tokens[1:])`：把序列和"错开一位的自己"配对，一行得到所有相邻对，如 `('l','o'), ('o','w'), ('w','</w>')`。
- `pair_freq[(a, b)] += freq`：**按词频加权**。`newest` 出现 6 次，它内部的每个相邻对都加 6。
- `Counter.most_common(1)[0][0]`：取频次最高的那一对。若出现并列，`most_common` 的排序是稳定的，会返回**最先被计入**的那一对——所以结果取决于字典的遍历顺序（即语料的插入顺序），是确定性的。
- `if not pair_freq: break`：所有词都已合并成单个 token、再无相邻对时提前退出。本语料最多只能学到 18 条规则（测验 Q11）。

### 3.3 `learn_bpe`（下）：执行合并

```python
        new_vocab = {}
        for tokens, freq in vocab.items():
            new_tokens = []
            i = 0
            while i < len(tokens):
                if i + 1 < len(tokens) and (tokens[i], tokens[i + 1]) == best:
                    new_tokens.append(tokens[i] + tokens[i + 1])
                    i += 2
                else:
                    new_tokens.append(tokens[i])
                    i += 1
            new_vocab[tuple(new_tokens)] = freq
        vocab = new_vocab
    return merges
```

- 用 `while` 而不是 `for`：命中合并时下标要**跳两格**（`i += 2`），否则一个符号可能被重复使用（如 `a a a` 合并 `(a, a)` 时，应得到 `aa a` 而不是重叠匹配）。
- `tokens[i] + tokens[i + 1]`：字符串拼接，新 token 就是两个旧 token 首尾相连，如 `'st' + '</w>' → 'st</w>'`。
- `i + 1 < len(tokens)` 写在 `and` 前面，利用**短路求值**避免越界访问 `tokens[i + 1]`。
- 每一轮都**重建**整个词表（`new_vocab`），时间复杂度大约是"合并次数 × 语料总符号数"。教学足够；生产实现（如 Hugging Face `tokenizers`）会用增量更新相邻对计数等技巧加速。
- 与讲义版本的区别：讲义用 `Counter()` 存 `vocab`，这里用普通字典 `{}`。两者在这里等价，因为不同的词合并后不会变成相同的元组（拼起来的字符串始终是原词 + `</w>`）。

### 3.4 `apply_bpe`：按学习顺序编码新词

```python
def apply_bpe(word, merges):
    tokens = list(word) + ["</w>"]
    for a, b in merges:
        new_tokens = []
        i = 0
        while i < len(tokens):
            if i + 1 < len(tokens) and tokens[i] == a and tokens[i + 1] == b:
                new_tokens.append(a + b)
                i += 2
            else:
                new_tokens.append(tokens[i])
                i += 1
        tokens = new_tokens
    return tokens
```

- 编码就是**重放训练过程**：按合并表的顺序，一条一条地在当前 token 序列上执行合并。
- **顺序至关重要**：`lowest` 一开始就被第 1 条规则 `w+e` 合成了 `l o we s t </w>`，等到第 8 条 `lo+w` 时已经没有单独的 `w` 可用，所以最终是 `['lo', 'west</w>']` 而不是 `['low', 'est</w>']`。
- 对没见过的词（`newish`、`slowest`），只要它由已知字符组成，就一定能切出结果——最坏情况退化成单字符。这就是"子词 tokenizer 没有 OOV"的原因（前提是基础字符都在词表中；字节级 BPE 用 256 个字节保证这一点）。
- ⚠️ 复杂度为 O(合并数 × 词长)：每条规则都要扫描一遍。真实系统有几万条规则，通常改为"反复找出当前序列中**优先级最高**（学得最早）的相邻对并合并"，配合缓存，速度快得多。

### 3.5 `main`：两段演示

```python
def main():
    print("=== FastText n-grams ===")
    for word in ["where", "whereupon"]:
        grams = sorted(char_ngrams(word))
        print(f"{word:12s} {len(grams)} grams, e.g., {grams[:5]}")
    shared = char_ngrams("where") & char_ngrams("whereupon")
    print(f"shared n-grams between where / whereupon: {len(shared)}")
    # ...
    corpus = Counter({
        "low": 5, "lower": 2, "newest": 6, "widest": 3,
        "lowest": 4, "newer": 2,
    })
    merges = learn_bpe(corpus, k_merges=10)
    # ...
    for a, b in merges:
        print(f"  {a!r} + {b!r} -> {a + b!r}")
    # ...
    for test in ["lowest", "slowest", "lower", "newish"]:
        tokens = apply_bpe(test, merges)
        print(f"{test:10s} -> {tokens}")
```

- `sorted(集合)` 返回排好序的列表，便于稳定地打印前 5 个；集合本身无序。
- `&` 是集合**交集**运算，直接得到共享的 n-gram。
- `{a!r}`：f-string 的 `!r` 转换，相当于 `repr(a)`，会给字符串加上引号，`</w>` 等特殊符号一目了然。
- 语料在讲义版本 `{"low", "lower", "newest", "widest"}` 的基础上**多加了 `lowest` 和 `newer`**，这一改动让第一条合并从讲义中的 `e+s` 变成了 `w+e`，切分结果也随之不同（见第 6 节）。
- 4 个测试词各有用意：`lowest`（训练语料里有）、`slowest`（多一个前缀 `s` 的新词）、`lower`（训练语料里有）、`newish`（只共享前缀的新词）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| n-gram 用集合表示 | 去重，便于做交集 / Jaccard | 丢失了 n-gram 的出现次数；FastText 的 n-gram 数量巨大，生产中哈希到固定桶数 |
| 加 `<`、`>` 边界 | 区分前缀、后缀与词中片段 | 片段数略增 |
| BPE 输入为词频表 | 不重复处理同一个词，按频次加权 | 需要先做一次预分词（按空格切词）；SentencePiece 则直接处理原始字符流 |
| `</w>` 词尾标记 | 区分词尾片段，解码时可还原词边界 | GPT-2 改用 `Ġ`（词首空格）标记，思路相同 |
| 每轮重建整个词表 | 实现直观 | 慢；生产实现增量更新相邻对计数 |
| `apply_bpe` 顺序重放所有规则 | 与训练过程一一对应，最易理解 | O(规则数 × 词长)；生产中按优先级合并 + 缓存 |
| 不含 GloVe / FastText 训练 | 保持脚本短小、无第三方依赖 | 这两部分的训练代码见讲义，需 NumPy |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| f-string 拼接 | `f"<{word}>"` | 在词两边加边界符 |
| 集合字面量与 `add` | `grams = {wrapped}`；`grams.add(...)` | 创建集合、添加元素（自动去重） |
| 集合交集 `&` | `char_ngrams("where") & char_ngrams("whereupon")` | 两个集合的公共元素；并集是 `|` |
| 字符串切片 | `wrapped[i:i + n]` | 取从 i 开始、长度为 n 的子串 |
| `range` 含上界的写法 | `range(n_min, n_max + 1)` | `range` 不含终点，所以要 +1 |
| `tuple(...)` 与元组拼接 | `tuple(word) + ("</w>",)` | 字符串转元组；单元素元组必须带逗号 |
| 元组作字典键 | `vocab[tokens] = freq` | 元组可哈希；列表不行 |
| `collections.Counter` | `Counter()`、`pair_freq[(a, b)] += freq`、`most_common(1)` | 计数字典：缺失键默认为 0；`most_common(n)` 返回频次最高的 n 项 |
| `zip` 错位配对 | `zip(tokens, tokens[1:])` | 得到所有相邻元素对 |
| `while` 手动控制下标 | `i += 2` / `i += 1` | 需要"跳过"元素时比 `for` 更灵活 |
| 短路求值 | `i + 1 < len(tokens) and ...` | 前面为假时不再计算后面，避免越界 |
| `_` 占位循环变量 | `for _ in range(k_merges)` | 不使用循环变量时的惯例 |
| `break` 提前退出 | `if not pair_freq: break` | 空 `Counter` 的真值为假 |
| f-string 宽度与 `!r` | `f"{word:12s}"`、`f"{a!r}"` | 左对齐占 12 格；`!r` 输出 `repr`，带引号 |
| `sorted` 集合 | `sorted(char_ngrams(word))` | 把无序集合变成有序列表 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，纯标准库）的完整输出：

```text
=== FastText n-grams ===
where        15 grams, e.g., ['<wh', '<whe', '<wher', '<where', '<where>']
whereupon    31 grams, e.g., ['<wh', '<whe', '<wher', '<where', '<whereupon>']
shared n-grams between where / whereupon: 10

=== BPE on toy corpus ===
learned 10 merges:
  'w' + 'e' -> 'we'
  's' + 't' -> 'st'
  'st' + '</w>' -> 'st</w>'
  'l' + 'o' -> 'lo'
  'we' + 'st</w>' -> 'west</w>'
  'n' + 'e' -> 'ne'
  'ne' + 'west</w>' -> 'newest</w>'
  'lo' + 'w' -> 'low'
  'low' + '</w>' -> 'low</w>'
  'we' + 'r' -> 'wer'

lowest     -> ['lo', 'west</w>']
slowest    -> ['s', 'lo', 'west</w>']
lower      -> ['lo', 'wer', '</w>']
newish     -> ['ne', 'w', 'i', 's', 'h', '</w>']
```

逐段解读：

- **n-gram 数量**：`where` 15 个、`whereupon` 31 个（`<whereupon>` 长度 11，n=3..6 分别 9/8/7/6 个，再加整词）。排序后前 5 个都以 `<` 开头，因为 `<` 的字符编码比字母小。
- **共享 10 个 n-gram**：`<wh`、`<whe`、`<wher`、`<where`、`whe`、`wher`、`where`、`her`、`here`、`ere`。即使 `whereupon` 从未出现在训练语料中，这 10 个片段的向量也足以把它放到 `where` 附近。注意 `where>`、`re>` 等**带词尾标记**的片段不在其中——因为 `whereupon` 不以 `where` 结尾，边界标记在这里起到了区分作用。
- **第 1 条合并 `w+e`**：按词频加权，`we` 出现 14 次（lower 2 + newest 6 + lowest 4 + newer 2），略多于 `es`、`st`、`t</w>` 的 13 次。
- **`newest</w>` 在第 7 步就成为一个整体 token**：`newest` 是语料中最高频的词（6 次），高频词最先被"压缩"成单个 token——这正是 BPE 的压缩本质。
- **`lowest → ['lo', 'west</w>']`**：虽然学到了 `lo+w`，但 `w` 早被第 1 条规则并进了 `we`。合并顺序决定切分（测验 Q9）。
- **`slowest → ['s', 'lo', 'west</w>']`**：新词，多出的 `s` 单独成 token，其余部分复用已学到的片段——没有 OOV。
- **`lower → ['lo', 'wer', '</w>']`**：即使是训练语料中的词，只做 10 次合并也不保证合成一个整体；`wer` 后面的 `</w>` 还没被合并（第 11 条规则才是 `wer+</w>`）。
- **`newish → ['ne', 'w', 'i', 's', 'h', '</w>']`**：只有前缀 `ne` 被识别，`ish` 部分完全没学过，退化为单字符。真实 tokenizer 学了几万条规则，`ish` 这类常见后缀一定会成为 token。

---

## 7. 动手改一改

1. **（易）Jaccard 重叠**（讲义练习 1）：写 `jaccard(w1, w2)`，计算 `playing` / `played`、`cat` / `cats` 的 n-gram 重叠（实测分别为 6/36 ≈ 0.17、3/13 ≈ 0.23）。
2. **（易）去掉边界标记**：把 `wrapped = f"<{word}>"` 改成 `wrapped = word`，再看 `where` 与 `whereupon` 共享多少 n-gram，体会边界标记的作用。
3. **（中）压缩曲线**（讲义练习 2 简化版）：对 `merges[:k]`（k = 0..18）统计整个语料的 token 总数与"字符 / token"比值。
4. **（中）实现 `fasttext_vector`**：给每个 n-gram 随机分配一个 4 维向量，按讲义写出求和函数，验证全部 n-gram 都未知的词返回 `None`。
5. **（中）优先级编码**：把 `apply_bpe` 改写为"建 `{pair: rank}` 字典，反复合并当前序列中 rank 最小的相邻对"，在本语料上验证结果与原实现一致。
6. **（难）对比讲义语料**：用讲义的四词语料 `{"low": 5, "lower": 2, "newest": 6, "widest": 3}` 重跑，确认 `apply_bpe("lowest")` 变成 `['low', 'est</w>']`，并逐步解释是哪一条合并造成了差异。

---

## 8. 常见坑

- **单元素元组忘了逗号**：`("</w>")` 只是一个字符串，`tuple(word) + ("</w>")` 会抛 `TypeError`；必须写 `("</w>",)`。
- **用列表当字典键**：`vocab[list_of_tokens] = freq` 会抛 `TypeError: unhashable type: 'list'`，所以 `learn_bpe` 里用元组。
- **合并时没有跳两格**：写成每次 `i += 1`，同一个符号可能参与两次合并，产生错误的 token。
- **编码时打乱规则顺序**：把 `merges` 当作无序集合使用（例如先应用"更长"的规则），会得到与训练时不一致的切分——BPE 的合并表是**有序**的。
- **只看讲义里的 n-gram 示例**：讲义正文的 `char_ngrams("where")` 少列了两个 6-gram，自己数的时候以 `len(char_ngrams("where")) == 15` 为准。
- **以为训练过的词一定是一个 token**：合并次数有限时，训练语料中的词（如 `lower`）也可能被切成多段。
