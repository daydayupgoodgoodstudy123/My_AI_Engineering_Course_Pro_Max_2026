# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 01 节 Tokenizers: BPE, WordPiece, SentencePiece ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：Python 标准库（`collections.Counter`）；`tiktoken` 为可选依赖（STEP 4 使用，未安装时自动跳过）

---

## 1. 这份代码在考察什么

`main.py` 按讲义 "Build It" 的 5 个步骤组织，是本节的完整演示脚本：

1. **字符级 tokenizer 作为基线**：`ord/chr` 直接映射，零训练、零 OOV，但序列最长。
2. **Byte-level BPE 的训练、编码、解码**：与 `bpe.py` 相同的核心算法（细节见 [bpe.讲解.md](bpe.讲解.md)），语料更大、合并 50 次。
3. **往返一致性（roundtrip）**：`decode(encode(s)) == s` 是任何 tokenizer 的第一条正确性检验。
4. **量化评估 tokenizer**：压缩比（token/字节）、平均每词 token 数、最常用 token、未使用 token 数。
5. **与工业级实现对比**：同样是 BPE，tiktoken 的 `cl100k_base` 在约 10 万次合并、海量语料上训练，压缩效果天差地别。

> 一句话：**先造一个能用的 tokenizer，再学会"给 tokenizer 打分"**——面试和工作中真正常用的是后者。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CharTokenizer` | 类 | 字符 ↔ Unicode 码点 | 字符级基线 |
| `BPETokenizer` | 类 | 字节级 BPE：`train / encode / decode / vocab_size / token_to_str` | BPE、合并表 |
| `compression_ratio(tokenizer, text)` | 函数 | token 数 / UTF-8 字节数 | 压缩比 |
| `vocabulary_stats(tokenizer, texts)` | 函数 | 打印词表大小、每词 token 数、Top-10 token、未使用 token 数 | fertility、Zipf 分布 |
| `demo_char_tokenizer` | 函数 | STEP 1：演示字符级编码 | — |
| `demo_bpe_training` | 函数 | STEP 2：在 8 句语料上训练 50 次合并，返回 `(tokenizer, corpus)` | BPE 训练 |
| `demo_encode_decode` | 函数 | STEP 3：编码 5 个句子，打印压缩比与往返结果 | roundtrip |
| `demo_tiktoken_comparison` | 函数 | STEP 4：与 `cl100k_base` 对比 token 数 | 工业级 BPE |
| `demo_vocabulary_analysis` | 函数 | STEP 5：在语料与 3 个新句子上统计词表使用情况 | 词表分析 |

数据流：`demo_bpe_training` 产出训练好的 `tokenizer` 与 `corpus`，依次传给 STEP 3、4、5 复用，避免重复训练。

---

## 3. 逐段精讲

### 3.1 字符级 tokenizer：最朴素的基线

```python
class CharTokenizer:
    def encode(self, text):
        return [ord(c) for c in text]

    def decode(self, tokens):
        return "".join(chr(t) for t in tokens)
```

- `ord('h') = 104`，`chr(104) = 'h'`，一一对应，天然可逆。
- 它没有 `__init__`，也不需要训练——"词表"就是整个 Unicode 码点空间。
- 优点：永远不会 OOV。缺点：一个字符一个 token，序列最长，模型要自己学会 "t"+"h"+"e" 是 "the"，浪费注意力容量。
- 注意它与 byte-level 的区别：`ord('中')` 是一个 token（20013），而 byte-level 会先把 "中" 拆成 3 个 UTF-8 字节。

### 3.2 `BPETokenizer`：与 bpe.py 相同的核心

```python
    def train(self, text, num_merges):
        tokens = list(text.encode("utf-8"))
        self.vocab = {i: bytes([i]) for i in range(256)}

        for i in range(num_merges):
            pairs = self._get_pairs(tokens)
            if not pairs:
                break
            best_pair = max(pairs, key=pairs.get)
            new_token = 256 + i
            tokens = self._merge_pair(tokens, best_pair, new_token)
            self.merges[best_pair] = new_token
            self.vocab[new_token] = self.vocab[best_pair[0]] + self.vocab[best_pair[1]]

        return self
```

与 `bpe.py` 的差别只有两处：

- 训练时**不打印**每一步合并（50 次合并刷屏没有意义）。
- 辅助方法改为 `token_to_str`，真正把字节解码成字符串用于展示：

```python
    def token_to_str(self, token_id):
        return self.vocab.get(token_id, b"<?>").decode("utf-8", errors="replace")
```

`_get_pairs`、`_merge_pair`、`encode`、`decode` 的逐行分析见 [bpe.讲解.md](bpe.讲解.md) 第 3 节。这里只强调一个容易被问到的点：`encode` 依赖 `dict` 的插入顺序重放合并，**顺序就是 tokenizer 的一部分**。

### 3.3 压缩比：衡量 tokenizer 的第一指标

```python
def compression_ratio(tokenizer, text):
    encoded = tokenizer.encode(text)
    raw_bytes = len(text.encode("utf-8"))
    return len(encoded) / raw_bytes
```

- 分母是 **UTF-8 字节数**而不是字符数，这样字节级 tokenizer 的"最差情况"恰好是 1.0（一个字节一个 token），便于横向比较。
- 数值越低越好：0.25 意味着平均 4 个字节合成 1 个 token。
- 讲义的定义："Tokens produced divided by input bytes -- lower means better compression and faster inference"。

### 3.4 `vocabulary_stats`：给词表做体检

```python
def vocabulary_stats(tokenizer, texts):
    total_tokens = 0
    total_words = 0
    token_usage = Counter()

    for text in texts:
        encoded = tokenizer.encode(text)
        total_tokens += len(encoded)
        total_words += len(text.split())
        for t in encoded:
            token_usage[t] += 1

    avg_tokens_per_word = total_tokens / total_words if total_words > 0 else 0
    # ...
    for token_id, count in token_usage.most_common(10):
        display = tokenizer.token_to_str(token_id)
        print(f"  {token_id:4d}: '{display}' x{count}")

    unused = tokenizer.vocab_size() - len(token_usage)
    print(f"\nUnused tokens: {unused} out of {tokenizer.vocab_size()}")
```

- **平均每词 token 数**就是讲义里的 fertility：`len(text.split())` 按空白数词，1.0 最理想。
- `if total_words > 0 else 0` 是**条件表达式**，防止空输入时除以 0。
- `Counter.most_common(10)` 返回出现次数最多的 10 个 `(token, 次数)`，用来观察 Zipf 分布（少数 token 占据大部分使用量）。
- `{token_id:4d}`：整数右对齐、宽度 4，让输出成列。
- ⚠️ "Unused tokens" = 词表大小 − 实际用到的不同 token 数。这里的词表包含 **256 个基础字节**，其中大多数（控制字符、非 ASCII 字节等）在英文文本里根本不会出现，所以这个数字主要反映"基础字节没用上"，不能直接解读为"合并学浪费了"。想看合并 token 的利用率，应只统计 id ≥ 256 的部分。

### 3.5 STEP 2：训练

```python
    tokenizer = BPETokenizer()
    tokenizer.train(corpus, num_merges=50)

    print(f"\nVocabulary size after training: {tokenizer.vocab_size()}")
    print(f"Number of merges learned: {len(tokenizer.merges)}")
```

- 词表大小 = 256 + 实际合并次数。`len(tokenizer.merges)` 与合并次数相等的前提是：每次选出的 `best_pair` 都不重复。这在 BPE 中成立，因为一个 pair 合并后就从序列中消失了。

### 3.6 STEP 3：编码、解码与往返检查

```python
    for sentence in test_sentences:
        encoded = tokenizer.encode(sentence)
        decoded = tokenizer.decode(encoded)
        raw_bytes = len(sentence.encode("utf-8"))
        ratio = len(encoded) / raw_bytes
        roundtrip = "PASS" if decoded == sentence else "FAIL"
        print(f"\n  '{sentence}'")
        print(f"  Encoded: {encoded[:15]}{'...' if len(encoded) > 15 else ''}")
```

- `encoded[:15]` 只显示前 15 个 id，太长时补上 `...`——f-string 里可以嵌套条件表达式。
- 测试句覆盖了三种情况：训练语料原句（"The cat sat on the mat."）、语料中的词换个组合（"tokenization pipeline"）、完全没见过的词（"unhappiness"）。
- 字节级 BPE 的往返一定是 PASS：编码只是把字节分组，解码把组拼回去，信息不丢失。

### 3.7 STEP 4：与 tiktoken 对比

```python
    try:
        import tiktoken
    except ImportError:
        print("  tiktoken not installed. Run: pip install tiktoken")
        return

    enc = tiktoken.get_encoding("cl100k_base")
    # ...
        tk_pieces = [enc.decode([t]) for t in tk_tokens]
        # ...
        ratio = len(our_tokens) / len(tk_tokens) if len(tk_tokens) > 0 else 0
        print(f"  Ours / tiktoken: {ratio:.1f}x")
```

- `cl100k_base` 是 GPT-3.5/GPT-4 使用的编码（约 10 万词表）。
- `enc.decode([t])` 逐个解码 token，看每个 token 对应的文本片段。
- 对比文本特意包含代码（`def fibonacci...`）和德语长复合词（`Geschwindigkeitsbegrenzung`），这两类是小语料 tokenizer 最吃亏的地方。
- "Ours / tiktoken" 大于 1 表示我们的 tokenizer 需要更多 token。

### 3.8 STEP 5：词表分析与主入口

```python
    test_texts = [
        corpus,
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is a subset of artificial intelligence.",
        "Python is the most popular language for data science.",
    ]

    vocabulary_stats(tokenizer, test_texts)

    print(f"\nCompression ratios:")
    for text in test_texts[:3]:
        preview = text[:50] + "..." if len(text) > 50 else text
```

- 把训练语料本身也放进来，可以对比"语料内"与"语料外"的压缩比。
- `preview = text[:50] + "..." if len(text) > 50 else text`：条件表达式优先级低于 `+`，等价于 `(text[:50] + "...") if ... else text`。

```python
if __name__ == "__main__":
    demo_char_tokenizer()
    tokenizer, corpus = demo_bpe_training()
    demo_encode_decode(tokenizer)
    demo_tiktoken_comparison(tokenizer)
    demo_vocabulary_analysis(tokenizer, corpus)
```

- `tokenizer, corpus = demo_bpe_training()`：函数返回元组，直接解包成两个变量。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 先实现字符级基线 | 有对照才能体会 BPE 的压缩价值 | 字符级在实际 LLM 中几乎不用 |
| 压缩比以字节为分母 | 字节级 tokenizer 最差为 1.0，便于跨语言比较 | 也可报告"每词 token 数"、"每字符 token 数" |
| 训练一次、多步复用 | 节省时间，保证各步用同一个 tokenizer | 生产中会把合并表持久化到文件（下一节内容） |
| tiktoken 设为可选依赖 | 核心演示只需标准库 | 对比部分在无网络/无包环境下无法展示 |
| 用 `split()` 粗略数词 | 简单 | 对中文等无空格语言失效，需要按字符或专门分词器统计 |
| 未使用 token 数包含基础字节 | 代码简单 | 指标被 256 个基础字节稀释；应单独统计合并 token |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `ord` / `chr` | `[ord(c) for c in text]`、`chr(t)` | 字符 ↔ Unicode 码点 |
| 列表推导式 | `[ord(c) for c in text]` | 一行生成列表 |
| `"".join(...)` | `"".join(chr(t) for t in tokens)` | 把多个字符串拼成一个 |
| `str.encode` / `bytes.decode` | `text.encode("utf-8")`、`.decode("utf-8", errors="replace")` | 字符串与字节互转，`errors="replace"` 遇到非法字节用 `�` 代替 |
| `collections.Counter` | `token_usage = Counter()`、`.most_common(10)` | 计数与取 Top-K |
| 字典推导式 | `{i: bytes([i]) for i in range(256)}` | 一行构造字典 |
| `max(..., key=...)` | `max(pairs, key=pairs.get)` | 按值取最大的 key |
| 条件表达式 | `"PASS" if decoded == sentence else "FAIL"` | 三元表达式，一行写 if/else |
| 切片 | `encoded[:15]`、`text[:50]`、`test_texts[:3]` | 取前 N 个元素 |
| f-string 嵌套表达式 | `f"{encoded[:15]}{'...' if len(encoded) > 15 else ''}"` | 花括号里可以写任意表达式 |
| f-string 格式符 | `{token_id:4d}`、`{ratio:.2f}`、`{ratio:.1f}x` | 宽度 4 的整数；保留 2/1 位小数 |
| `str.split()` | `len(text.split())` | 无参数时按任意空白切分并忽略多余空白 |
| 元组返回与解包 | `return tokenizer, corpus` / `tokenizer, corpus = demo_bpe_training()` | 函数一次返回多个值 |
| `try/except ImportError` + 提前 `return` | `demo_tiktoken_comparison` | 可选依赖优雅降级 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示 |

---

## 6. 运行结果解读

实际运行（Python 3.13，未安装 tiktoken）的关键输出：

```text
STEP 1: Character-Level Tokenizer
  'hello' -> [104, 101, 108, 108, 111]            Tokens: 5
  'Hello, world!' -> [72, 101, 108, ..., 33]      Tokens: 13
  'GPT-4' -> [71, 80, 84, 45, 52]                 Tokens: 5   ← 字符数 = token 数

STEP 2: BPE Training
Vocabulary size after training: 306              ← 256 + 50
Number of merges learned: 50

STEP 3: Encode and Decode
  'The cat sat on the mat.'      Tokens: 7 (from 23 bytes)  ratio 0.30  PASS
  'Natural language processing'  Tokens: 16 (from 27 bytes) ratio 0.59  PASS
  'tokenization pipeline'        Tokens: 12 (from 21 bytes) ratio 0.57  PASS
  'unhappiness'                  Tokens: 10 (from 11 bytes) ratio 0.91  PASS
  'The dog ate the frog.'        Tokens: 8 (from 21 bytes)  ratio 0.38  PASS

STEP 4: Compare with tiktoken
  tiktoken not installed. Run: pip install tiktoken

STEP 5: Vocabulary Analysis
Vocabulary size: 306
Avg tokens per word: 3.21
Total unique tokens used: 73
Top 10 most used tokens:
    32: ' ' x20
    97: 'a' x16
   114: 'r' x14
   ...                                         ← Top-10 全是单字节
Unused tokens: 233 out of 306

Compression ratios:
  0.50 -- 'The cat sat on the mat. The cat ate the rat. The d...'
  0.75 -- 'The quick brown fox jumps over the lazy dog.'
  0.80 -- 'Machine learning is a subset of artificial intelli...'
```

逐项解读：

- **"The cat sat on the mat." 只要 7 个 token**：额外查看切分结果是 `['The ', 'c', 'at', ' sat on the ', 'm', 'at', '.']`。跨越三个单词的 `' sat on the '` 说明没有预分词；而 `cat` 后面的空格被先学到的 `' s'` 合并"抢走"了，所以没形成 `'at '`（详见测验 Q9）。
- **"unhappiness" 比 bpe.py 中好一点（10 vs 11）**：这次语料里有 "pipeline"、"into"、"integers" 等词，学到了 `'in'` 合并（262 号），`happiness` 中 `ness` 前的 `in` 被合并了；其余仍是逐字节。
- **Avg tokens per word = 3.21**：远高于讲义表格中 GPT-4 的约 1.2。50 次合并的小词表在新句子上几乎是字节级编码。
- **Top-10 全是单字节**：新句子（quick brown fox、Machine learning…）大量使用没被合并的字母，空格最频繁。
- **Unused tokens 233/306**：用到的 73 个 token 中，额外统计可知训练语料用到了 37 个合并 token；未使用的 233 个里绝大部分是从未出现的基础字节，所以这个指标要谨慎解读（见 3.4）。
- **压缩比 0.50 → 0.75 → 0.80**：语料内文本最好，越"陌生"的文本越接近 1.0。这就是讲义说的"在训练语料上压缩比好，分布外文本退化为字符级"。
- STEP 4 因未安装 tiktoken 被跳过（未实际运行该部分）；若安装，可以预期 tiktoken 在这些句子上的 token 数显著更少，尤其是代码与德语长词。

---

## 7. 动手改一改

1. 在 `vocabulary_stats` 中只统计 id ≥ 256 的合并 token，打印"合并 token 使用率 = 用到的合并 token 数 / 50"。
2. 给 `CharTokenizer` 和 `BPETokenizer` 都加上"每字符 token 数"统计，对比 `"自然语言处理"` 在两者下的 token 数，体会 byte-level 对中文的"初始惩罚"（每字 3 个字节）。
3. 完成讲义练习 1：在 `train` 中每次合并后打印 `self.vocab[new_token]`，观察 `'he '` → `'The '`、`' l'` → `' languag'` 这类"逐字母生长"的过程。
4. 完成讲义练习 2：加入 `<pad>`、`<eos>`、`<unk>` 三个特殊 token，ID 固定为 0、1、2，其余 token 整体后移 3 位；确认 `encode/decode` 仍能往返。
5. 写一个 `fertility_by_language(tokenizer, samples: dict)`，对英文、西班牙文、中文各几句话计算平均每词（中文按字）token 数，量化"多语言税"。
6. 进阶：把 `num_merges` 做成命令行参数（用 `argparse`），画出"合并次数 vs 训练语料压缩比"的曲线，观察收益递减。

---

## 8. 常见坑

- **只看训练语料上的压缩比**：训练语料上的数字会非常好看，评估 tokenizer 必须用分布外文本。
- **用 `len(text)` 当分母**：多字节语言下会严重低估 token/字节比，跨语言比较时失真。
- **误读 "Unused tokens"**：它包含大量从未出现的基础字节，不等于"合并学了没用"。
- **`split()` 统计中文词数**：中文没有空格，`len(text.split())` 往往只有 1，平均每词 token 数会大得离谱。
- **以为字符级 tokenizer 与 byte-level 一样**：前者以 Unicode 码点为单位（词表可达十几万），后者以字节为单位（基础词表恒为 256）。
- **在没装 tiktoken 时以为 STEP 4 失败了**：脚本只是打印提示并跳过，其余步骤正常运行。
