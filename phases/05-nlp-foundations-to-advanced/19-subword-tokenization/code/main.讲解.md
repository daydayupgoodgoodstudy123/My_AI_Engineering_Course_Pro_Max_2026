# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 19 节 子词 Tokenization——BPE、WordPiece、Unigram、SentencePiece ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`re`、`collections.Counter`）

---

## 1. 这份代码在考察什么

这份代码用不到 120 行纯 Python 实现了**字符级 BPE 的训练与编码**，目的是让你亲眼看到"子词词表是怎么一步步长出来的"：

1. **BPE 训练循环**：统计相邻符号对 → 取最频繁的一对 → 合并 → 记录 merge，重复 N 次。
2. **按词频加权**：同一个词出现 3 次，它内部的每个相邻对就计 3 次，所以高频词里的片段会先被合并。
3. **`</w>` 词尾标记**：区分词尾的子串和词中的子串。
4. **merge 列表有序**：编码时严格按训练顺序应用 merge。
5. **泛化到未见过的词**：用 150 次 merge 的模型去切 `tokenizable`、`foxhound` 等训练语料里没有的词，观察它们如何拆成已知片段。

> 一句话：**BPE 的全部"魔法"就是一个按频次贪心合并的循环 + 一份有序的 merge 列表**；tiktoken、HF Tokenizers 只是把它做快了、做成了字节级。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `word_counts(text)` | 函数 | 小写化 + 正则抽取纯字母单词，统计词频 | pre-tokenization（预切分） |
| `init_vocab(counts)` | 函数 | 把每个词拆成字符元组并追加 `</w>` | 初始字符级词表 |
| `pair_counts(vocab)` | 函数 | 统计所有相邻符号对的加权频次 | BPE 的选对依据 |
| `merge_pair(vocab, pair)` | 函数 | 在所有词里把指定的一对合并成新符号 | 一次 merge |
| `train_bpe(text, num_merges)` | 函数 | 训练主循环，返回 merges 和"最终用到的符号集合" | BPE 训练 |
| `encode_bpe(word, merges)` | 函数 | 按顺序把 merges 应用到一个新词上 | BPE 推理/编码 |
| `main()` | 演示入口 | 分别训练 30 / 150 次 merge，打印 merge 与编码结果 | — |

数据流：`text → word_counts → init_vocab → [pair_counts → most_common → merge_pair] × N → merges`；编码时 `word + merges → encode_bpe → 子词列表`。

---

## 3. 逐段精讲

### 3.1 预切分与初始词表

```python
def word_counts(text):
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return Counter(words)


def init_vocab(counts):
    return {tuple(word) + ("</w>",): freq for word, freq in counts.items()}
```

- `re.findall(r"[a-zA-Z]+", ...)` 只抽取连续的英文字母串，数字、标点、非 ASCII 字符全部丢弃。这一步相当于真实 tokenizer 的 **pre-tokenization**：先按某种规则切成"词"，BPE 只在词内部合并，**不会跨词**。
- `Counter(words)` 得到 `{词: 出现次数}`。BPE 不需要逐个处理重复的词，只需带着频次处理每个**不同的词**，这是训练速度的关键。
- `tuple(word) + ("</w>",)`：`"the"` 变成 `('t', 'h', 'e', '</w>')`。用**元组**而不是列表，是因为它要当字典的 key（列表不可哈希）。
- `</w>` 的作用：让 `low</w>`（完整词 low）与 `low`（lower 的前缀）成为不同符号，解码时也能凭它恢复空格。
- ⚠️ 简化：真实 byte-level BPE 的基础符号是 256 个字节，SentencePiece 把空格编码为 `▁`；这里只用小写字母 + `</w>`。本语料第一行恰好是英文全字母句（"the quick brown fox jumps over the lazy dog"），所以 26 个字母都在基础符号里，初始共 27 个符号。

### 3.2 统计相邻对

```python
def pair_counts(vocab):
    pairs = Counter()
    for symbols, freq in vocab.items():
        for a, b in zip(symbols, symbols[1:]):
            pairs[(a, b)] += freq
    return pairs
```

- `zip(symbols, symbols[1:])` 是"取相邻对"的经典写法：`('t','h','e','</w>')` 与 `('h','e','</w>')` 配对得到 `(t,h)`、`(h,e)`、`(e,</w>)`。
- `+= freq` 实现**按词频加权**：`the` 在语料中出现 5 次，`(t,h)` 就一次加 5。
- 在本语料上，初始最高频的几对是 `(e,</w>)`=15、`(s,</w>)`=14、`(n,</w>)`=11——英文大量以 e、s、n 结尾，这就是前三个 merge 的由来。

### 3.3 执行一次合并

```python
def merge_pair(vocab, pair):
    a, b = pair
    merged_symbol = a + b
    new_vocab = {}
    for symbols, freq in vocab.items():
        new_symbols = []
        i = 0
        while i < len(symbols):
            if i < len(symbols) - 1 and symbols[i] == a and symbols[i + 1] == b:
                new_symbols.append(merged_symbol)
                i += 2
            else:
                new_symbols.append(symbols[i])
                i += 1
        new_vocab[tuple(new_symbols)] = freq
    return new_vocab
```

- 从左到右扫描，命中 `(a, b)` 就追加合并后的符号并**跳过两格**（`i += 2`），否则原样追加并前进一格。
- "从左到右、命中即跳过"决定了重叠情况的处理：`('a','a','a')` 合并 `(a,a)` 得到 `('aa','a')`，而不是 `('a','aa')`。
- 为什么用 `while` 而不是 `for`：步长不固定（1 或 2），`for i in range(...)` 无法在循环体里跳过元素。
- 返回**新字典**而不是原地修改，避免"边遍历边修改字典"的错误。
- 新 key 不会冲突：不同的词拼接回去仍是不同的字符串，所以合并后的元组也互不相同。

### 3.4 训练主循环

```python
def train_bpe(text, num_merges):
    counts = word_counts(text)
    if not counts:
        raise ValueError("word_counts: corpus produced no words")
    vocab = init_vocab(counts)
    merges = []
    for _ in range(num_merges):
        pairs = pair_counts(vocab)
        if not pairs:
            break
        best = pairs.most_common(1)[0][0]
        merges.append(best)
        vocab = merge_pair(vocab, best)
    final_tokens = set()
    for symbols in vocab:
        final_tokens.update(symbols)
    return merges, sorted(final_tokens)
```

- `pairs.most_common(1)` 返回 `[((a, b), count)]`，`[0][0]` 取出那一对。
- **平局怎么办**：`most_common` 对相同计数保持插入顺序，也就是"先被统计到的对"获胜。插入顺序取决于词在语料中的首次出现顺序，所以结果是**确定性**的，每次运行都一样。真实实现通常也会定义明确的平局规则，否则不同机器训练出的词表可能不一致。
- `if not pairs: break`：当所有词都被合并成单个符号时，已没有相邻对，提前结束。本语料在第 183 次 merge 后就无对可合并。
- `merges` 是**有序列表**，它就是 BPE 模型本身（再加上基础符号表）。
- ⚠️ 需要特别注意 `final_tokens`：它收集的是"训练语料在**最终切分状态**下用到的符号"，**不是** tokenizer 的真实词表。被合并掉、不再单独出现的中间符号会从中消失，所以 merge 越多它可能越小（merge 到底时等于不同词的个数 52）。真实 BPE 词表 = 基础符号 + 所有 merge 产物，30 次 merge 时是 57，150 次时是 177。`main()` 把它打印成 "vocab size"，读结果时要心里有数。
- ⚠️ 性能简化：每轮都重新统计全部 pair，复杂度 O(merges × 语料符号数)。生产实现会增量更新受影响的 pair 计数。

### 3.5 编码新词

```python
def encode_bpe(word, merges):
    symbols = list(word) + ["</w>"]
    for a, b in merges:
        merged = a + b
        i = 0
        while i < len(symbols) - 1:
            if symbols[i] == a and symbols[i + 1] == b:
                symbols = symbols[:i] + [merged] + symbols[i + 2:]
            else:
                i += 1
    return symbols
```

- 编码 = 把训练时学到的 merge **按顺序重放**一遍。顺序至关重要：若 `(lo, w)` 排在 `(l, o)` 前面，`low` 只会被切成 `lo | w | </w>`。
- 命中后 `i` **不前进**，下一轮比较的是新合并出的符号和它右边的符号。由于 `a + b` 一定比 `a` 长，不会再次匹配 `a`，所以不会死循环。
- 这里用切片重建列表，每次合并 O(n)；对 M 个 merge 各扫一遍，最坏约 O(M·n²)。讲义说生产实现（tiktoken、HF Tokenizers）用 **merge rank 查找 + 优先队列**，复杂度只和词长有关。
- ⚠️ 简化：编码时**不做小写化**，也不处理未知字符。`encode_bpe("Hello", merges)` 中的 `H` 会原样保留成一个训练时从未见过的符号——真实系统要么映射为 `<unk>`，要么像 byte-level BPE 那样退回字节。

### 3.6 演示入口

```python
    merges_small, tokens_small = train_bpe(corpus, num_merges=30)
    merges_big, tokens_big = train_bpe(corpus, num_merges=150)
    # ...
    held_out = ["tokenizable", "unlearnable", "foxhound", "languages"]
    for word in held_out:
        pieces = encode_bpe(word, merges_big)
        tag = "OK" if len(pieces) == 1 else f"split({len(pieces)})"
        print(f"  {word:<14} -> {' | '.join(pieces)}  [{tag}]")
```

- 训练两个规模的模型，对比 merge 数量的影响。
- `held_out` 里的四个词都不在训练语料中，用来观察**泛化**：BPE 能不能用已学到的片段拼出新词。
- `len(pieces) == 1` 才算"OK"，意思是整个词（含 `</w>`）被合成了一个 token。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 字符级 + `</w>` | 输出可读，直观看到合并过程 | 生产用 byte-level（GPT-2）或 `▁` 标记空格（SentencePiece） |
| 正则只取 `[a-zA-Z]+` | 让演示聚焦英文单词 | 丢弃数字、标点、非拉丁文字；生产用更复杂的 pre-tokenization 正则或不做预切分 |
| 按"不同词 + 频次"训练 | 避免重复处理同一个词，速度快 | 生产还会增量更新 pair 计数 |
| `most_common` 默认平局规则 | 简单且确定 | 生产需明确定义平局规则，保证可复现 |
| 返回"最终用到的符号"作为 tokens | 代码短 | 不等于真实词表；应返回"基础符号 ∪ merge 产物" |
| 朴素逐个 merge 编码 | 与"按顺序重放"的定义一一对应 | 生产用 merge rank + 优先队列 + 缓存 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import` / `from ... import` | `import re`、`from collections import Counter` | 导入标准库模块与类 |
| 正则 `re.findall` | `re.findall(r"[a-zA-Z]+", text.lower())` | 返回所有匹配的子串列表；`r"..."` 是原始字符串，反斜杠不转义 |
| 字符串方法 | `text.lower()` | 转小写，返回新字符串 |
| 元组与拼接 | `tuple(word) + ("</w>",)` | `tuple("the")` → `('t','h','e')`；单元素元组必须写逗号 `("</w>",)` |
| 字典推导式 | `{tuple(word) + ("</w>",): freq for word, freq in counts.items()}` | 一行构造字典；元组可以作 key，列表不行 |
| `Counter` | `pairs[(a, b)] += freq`、`pairs.most_common(1)[0][0]` | 不存在的 key 默认为 0，可直接 `+=`；`most_common(k)` 返回前 k 个 `(元素, 次数)` |
| `zip` + 切片取相邻对 | `zip(symbols, symbols[1:])` | 把序列和"错开一位的自己"配对 |
| 元组解包 | `a, b = pair`；`for a, b in merges` | 一次取出多个值 |
| `while` 手动控制下标 | `i += 2` / `i += 1` | 步长不固定时用 `while` |
| 列表切片拼接 | `symbols[:i] + [merged] + symbols[i + 2:]` | 用新列表替换中间两个元素 |
| `set.update` 与 `sorted` | `final_tokens.update(symbols)`、`sorted(final_tokens)` | 批量加入集合并去重；排序后返回列表 |
| `raise ValueError` | `raise ValueError("word_counts: corpus produced no words")` | 输入不合法时主动抛异常，比后面莫名其妙出错更好排查 |
| `_` 占位变量 | `for _ in range(num_merges)` | 只需要循环次数、不需要循环变量 |
| f-string 格式符 | `f"{word:<14}"`、`f"{m[0]!r}"` | `:<14` 左对齐占 14 格；`!r` 调用 `repr()`，字符串会带引号显示 |
| 三引号字符串 | `corpus = """ ... """` | 多行字符串 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被导入时不执行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py` 的输出：

```text
=== BPE, 30 merges ===
vocab size: 55
first 10 merges:
  0: 'e' + '</w>' -> 'e</w>'
  1: 's' + '</w>' -> 's</w>'
  2: 'n' + '</w>' -> 'n</w>'
  3: 't' + 'i' -> 'ti'
  4: 'l' + 'e' -> 'le'
  5: 't' + 'o' -> 'to'
  6: 't' + 'h' -> 'th'
  7: 'th' + 'e</w>' -> 'the</w>'
  8: 'i' + 'n</w>' -> 'in</w>'
  9: 'n' + 'i' -> 'ni'

=== BPE, 150 merges ===
vocab size: 77

=== encoding held-out words (150-merge model) ===
  tokenizable    -> tokeniz | a | ble</w>  [split(3)]
  unlearnable    -> u | n | lear | n | a | ble</w>  [split(6)]
  foxhound       -> fox | h | o | u | n | d</w>  [split(6)]
  languages      -> languag | e | s</w>  [split(3)]

note: with a tiny toy corpus, most held-out words will split.
production vocabularies train on billions of tokens.
```

逐段解读：

- **前三个 merge 都是"字母 + `</w>`"**：初始统计中 `(e,</w>)`=15、`(s,</w>)`=14、`(n,</w>)`=11 最高，说明英文词尾规律（-e、-s、-n）最先被学到。
- **merge 3–6**（`ti`、`le`、`to`、`th`）：来自 `tokenization`、`statistical`、`patterns` 等高频词里的片段。
- **merge 7：`th` + `e</w>` → `the</w>`**：最高频的单词 "the" 在第 8 次 merge 就成了一个完整 token，这正是"常见词保持整 token"。注意它用到了前面产生的 `th` 和 `e</w>`——merge 是层层叠加的。
- **vocab size 55 → 77**：这是"最终切分中出现的符号数"，不是真实词表大小（分别应为 57 和 177，见 3.4 节）。
- **held-out 编码**：
  - `tokenizable → tokeniz | a | ble</w>`：`tokeniz` 来自训练语料里的 `tokenization`，`ble</w>` 来自 `learnable`、`reusable`，新词由已知片段拼成。
  - `languages → languag | e | s</w>`：语料里只有 `language`，学到了 `languag` + `e</w>` → `language</w>`，但没有学到 `es</w>`，于是 `e` 和 `s</w>` 只能各自成 token。
  - `foxhound` 中 `fox` 被识别，`hound` 没见过，退化成单字母。
  - 四个词全部 `split`：玩具语料太小，讲义最后两行也提醒了这一点。

---

## 7. 动手改一改

1. 把 `num_merges` 改成 1000，观察实际执行了多少次 merge（应为 183），以及打印的 vocab size 为什么变成 52。
2. 修改 `train_bpe` 的返回值，使它返回**真实词表**：基础符号 ∪ `{a + b for a, b in merges}`，验证 30 次 merge 时为 57。
3. 写一个 `decode(pieces)`：把子词拼接起来，并把 `</w>` 替换为空格，验证 `decode(encode_bpe(w, merges)).strip() == w` 对训练词和 held-out 词都成立。
4. 把选对规则改成 WordPiece 风格打分 `count(ab) / (count(a)·count(b))`，对比前 5 个 merge（参考测验 Q10）。
5. 用 merge rank 实现 `encode_bpe_fast`，并用 2000 个随机字符串对比它与 `encode_bpe` 的输出是否完全一致（参考测验 Q11）。
6. 进阶：把基础符号从字母改成 UTF-8 字节（`list(word.encode("utf-8"))`），让中文、emoji 也能编码，观察一个汉字和一个 emoji 分别会拆成多少个初始符号。

---

## 8. 常见坑

- **把 merges 当集合**：存成 `set` 或排序后加载会打乱顺序，编码结果悄悄改变（参见测验 Q8）。
- **误读 "vocab size"**：本代码打印的是最终切分中用到的符号数，不是 tokenizer 词表大小。
- **训练与推理的预处理不一致**：训练时 `lower()` 了，`encode_bpe` 却没有；传入大写或带标点的词会出现训练时从未见过的符号。生产中要保证 normalization / pre-tokenization 两边完全一致——这也是讲义里 "tokenizer drift" 的一种形式。
- **非 ASCII 被正则静默丢弃**：中文、带重音的字母在 `word_counts` 里直接消失，不会报错。
- **平局规则不确定**：如果换成"从 set 中取最大值"之类的写法，平局时的选择会依赖哈希顺序，不同进程可能训练出不同词表。
