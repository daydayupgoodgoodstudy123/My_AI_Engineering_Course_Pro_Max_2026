# 代码讲解 · bpe.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 01 节 Tokenizers: BPE, WordPiece, SentencePiece ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python bpe.py` ｜ **依赖**：Python 标准库（`collections.Counter`）；`tiktoken` 为可选依赖，未安装时对比部分自动跳过

---

## 1. 这份代码在考察什么

`bpe.py` 是本节最精简的 BPE 实现（同目录的 `main.py` 是带更多演示的完整版）。它要你看清：

1. **BPE 训练的三步循环**：统计相邻 pair → 选频次最高的合并 → 记入合并表，重复 `num_merges` 次。
2. **Byte-level 的基础词表**：从 `text.encode("utf-8")` 的字节出发，初始词表恰好 256 个，因此不会有未知 token。
3. **合并表就是 tokenizer**：`self.merges` 记录"哪对 → 哪个新 id"，编码时按学到的顺序重放。
4. **解码只是查表拼字节**：每个 token id 对应一段字节，拼起来再 UTF-8 解码。
5. **压缩比的含义**：训练语料内的句子压缩得很好，语料外的词（如 "unhappiness"）退化为逐字节编码。

> 一句话：**用 50 行代码复刻 GPT 系列 tokenizer 的核心机制**——tiktoken 与它算法相同，差别只在训练数据量和合并次数。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BPETokenizer.__init__` | 方法 | 初始化合并表 `merges` 与词表 `vocab` | 合并表 = tokenizer |
| `_get_pairs` | 方法 | 统计所有相邻 token 对的出现次数 | pair 频次 |
| `_merge_pair` | 方法 | 把序列中所有指定 pair 替换成新 token | 一次合并 |
| `train` | 方法 | 训练循环，并打印每一步合并 | BPE 训练 |
| `encode` / `decode` | 方法 | 文本 ↔ token id 序列 | 编码 / 解码 |
| `vocab_size` / `get_token_str` | 方法 | 查询词表大小、某个 id 对应的字节 | 词表 |
| `demo_bpe()` | 函数 | 在小语料上训练 30 次合并并编码 4 个句子 | 压缩比演示 |
| `demo_tiktoken()` | 函数 | 若安装了 tiktoken，展示 `cl100k_base` 的切分 | 工业级 BPE 对比 |

数据流：`demo_bpe` → `train`（反复调用 `_get_pairs` + `_merge_pair`）→ `encode`（按序重放 `merges`）→ `decode`（查 `vocab`）。

---

## 3. 逐段精讲

### 3.1 统计相邻 pair

```python
    def _get_pairs(self, tokens):
        pairs = Counter()
        for i in range(len(tokens) - 1):
            pairs[(tokens[i], tokens[i + 1])] += 1
        return pairs
```

- 对长度为 n 的序列，枚举 n−1 个相邻位置，把 `(左, 右)` 元组作为 key 计数。元组可以作字典 key，因为它不可变、可哈希。
- `Counter` 是带默认值 0 的字典，`+= 1` 不需要先判断 key 是否存在。
- ⚠️ 统计的是**重叠**出现次数：`aaa` 会被记为 2 个 `(a,a)`，但真正合并时只能替换 1 次（见 3.2）。这是教学实现的简化，不影响正确性，只会让选择略有偏差。
- ⚠️ 每一轮都重新扫描全序列，复杂度 O(n)，训练总复杂度 O(num_merges × n)。生产实现会维护增量更新的 pair 计数。

### 3.2 执行一次合并

```python
    def _merge_pair(self, tokens, pair, new_token):
        merged = []
        i = 0
        while i < len(tokens):
            if i < len(tokens) - 1 and tokens[i] == pair[0] and tokens[i + 1] == pair[1]:
                merged.append(new_token)
                i += 2
            else:
                merged.append(tokens[i])
                i += 1
        return merged
```

- 用 `while` 而不是 `for`，因为步长不固定：匹配时跳 2 步，否则跳 1 步。
- `i < len(tokens) - 1` 必须放在最前面：利用 `and` 的**短路求值**，防止访问 `tokens[i + 1]` 越界。
- 从左到右、不重叠地替换：`[a, a, a]` 合并 `(a,a)` 得到 `[aa, a]`，而不是 `[a, aa]` 或两个重叠的 `aa`。
- 返回新列表而不是原地修改，逻辑简单、不易出错。

### 3.3 训练循环

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
            merged_str = self.vocab[new_token]
            print(f"Merge {i + 1}: {best_pair} -> {new_token} = {merged_str}")

        return self
```

- `list(text.encode("utf-8"))`：`str.encode` 得到 `bytes`，对 `bytes` 调 `list` 会得到 0–255 的整数列表。这就是 **byte-level** 的起点。
- `{i: bytes([i]) for i in range(256)}`：字典推导式建立 256 个基础 token，`bytes([104])` 就是 `b'h'`。
- `max(pairs, key=pairs.get)`：遍历字典的 key，用 `pairs.get(key)`（即频次）比较大小。**平局时返回最先出现的 key**，而 `Counter` 保持插入顺序，所以平局时"在文本中先出现的 pair 胜出"。
- 新 token 的 id 从 256 开始连续分配：`256 + i`。
- 新 token 的字节内容 = 左右两个 token 的字节拼接，所以 `vocab` 天然支持多级合并（`'he '` = `'h'` + `'e '`）。
- `if not pairs: break`：只有当序列只剩 1 个 token 时 pairs 才为空。
- ⚠️ 没有"最小频次"阈值：即使最高频的 pair 只出现 1 次也会合并，在小语料上容易学到只在训练语料中出现一次的长 token。
- ⚠️ 没有预分词，合并可以跨越单词和空格（运行结果中出现了 `b'sat on the '`）。
- `return self` 让调用方可以链式写 `BPETokenizer().train(...)`。

### 3.4 编码与解码

```python
    def encode(self, text):
        tokens = list(text.encode("utf-8"))
        for pair, new_token in self.merges.items():
            tokens = self._merge_pair(tokens, pair, new_token)
        return tokens

    def decode(self, tokens):
        byte_sequence = b"".join(self.vocab[t] for t in tokens)
        return byte_sequence.decode("utf-8", errors="replace")
```

- `encode` 依赖一个关键事实：Python 3.7+ 的 `dict` **保持插入顺序**，所以 `self.merges.items()` 正好是学到合并的顺序。顺序很重要：`'the '`（259）由 `'t'` + `'he '`（258）合成，必须先有 258 才能合出 259。
- ⚠️ 每条合并都扫一遍序列，编码复杂度 O(合并数 × 文本长度)。tiktoken 等实现会根据合并的"排名"（rank）每次只找当前序列中排名最靠前的 pair 合并，效率高得多。
- `decode` 用生成器表达式把每个 id 的字节拼接起来，再整体解码。
- `errors="replace"`：如果 token 序列在多字节字符中间被截断（比如只解码一个中文字符的前 2 个字节），不会抛异常，而是显示 `�`。

### 3.5 辅助方法与演示

```python
    def get_token_str(self, token_id):
        return self.vocab.get(token_id, b"<?>")
```

- ⚠️ 名字叫 `get_token_str`，返回的却是 `bytes`（`main.py` 里的同类方法 `token_to_str` 才真正解码成 `str`）。
- `demo_bpe()` 用 4 个关于猫、狗、语言处理的句子训练 30 次合并，再编码 4 个测试句，打印编码、解码、token 数和压缩比。
- `demo_tiktoken()` 用 `try/except ImportError` 做可选依赖：没装 tiktoken 时打印提示后 `return`，不影响前面的演示。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 从 UTF-8 字节出发 | 基础词表固定 256，任何文本都能编码，无 OOV | 中文等多字节字符初始就要 3 个 token；生产中靠大量合并弥补 |
| 不做预分词 | 代码最短，直观看到合并过程 | 出现跨词 token；GPT-2/tiktoken 先用正则切分再在片段内 BPE |
| `max` + 插入顺序决定平局 | 实现最简单 | 结果依赖语料顺序；生产实现会定义明确的平局规则 |
| 每轮全量重新统计 pair | 易读 | O(合并数 × n)；生产中增量维护 pair 计数，用 Rust 实现 |
| 编码时按顺序重放所有合并 | 与训练过程一一对应，易验证 | 慢；生产中用 rank 优先队列只处理当前出现的 pair |
| `errors="replace"` 解码 | 单个 token 可能是半个字符，避免崩溃 | 可能悄悄吞掉错误；流式输出时应缓冲到完整字符 |
| 训练时 `print` 每一步合并 | 教学可视化 | 大规模训练时应关闭或改用日志 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `class` 与 `__init__` | `class BPETokenizer: def __init__(self)` | 定义类与构造函数 |
| 以下划线开头的方法名 | `_get_pairs`、`_merge_pair` | 约定俗成的"内部方法"，提示外部不要直接调用（并非强制私有） |
| `bytes` 与 `str` 互转 | `text.encode("utf-8")`、`byte_sequence.decode("utf-8", errors="replace")` | `str` 是字符序列，`bytes` 是 0–255 的整数序列 |
| `bytes([i])` 与 bytes 拼接 | `bytes([i])`、`self.vocab[a] + self.vocab[b]` | 从整数列表构造字节串；`+` 拼接两个字节串 |
| `b"".join(...)` | `b"".join(self.vocab[t] for t in tokens)` | 高效拼接多个字节串 |
| 元组作字典 key | `pairs[(tokens[i], tokens[i + 1])]` | 元组不可变、可哈希 |
| `collections.Counter` | `pairs = Counter()`、`pairs[...] += 1` | 计数专用字典，缺省值为 0 |
| 字典推导式 | `{i: bytes([i]) for i in range(256)}` | 一行构造字典 |
| `max(..., key=...)` | `max(pairs, key=pairs.get)` | 按自定义标准取最大；平局取第一个 |
| `while` + 手动下标 | `_merge_pair` 中的 `i += 2` / `i += 1` | 步长可变的遍历 |
| `and` 短路求值 | `i < len(tokens) - 1 and tokens[i] == ...` | 前面为假就不再计算后面，防止越界 |
| `dict.get(key, default)` | `self.vocab.get(token_id, b"<?>")` | key 不存在时返回默认值而不是报错 |
| 生成器表达式 | `self.vocab[t] for t in tokens` | 不建中间列表 |
| f-string 格式符 | `f"{len(encoded) / raw_bytes:.2f}"` | 保留两位小数 |
| 字符串乘法 | `"=" * 60` | 打印分隔线 |
| `try/except ImportError` | `demo_tiktoken` 中的 `import tiktoken` | 可选依赖，缺失时优雅降级 |
| 函数内 `import` | `import tiktoken` 写在函数里 | 只在需要时导入，缺包也不影响模块其他部分 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示 |

---

## 6. 运行结果解读

实际运行（Python 3.13，未安装 tiktoken）的关键输出：

```text
Merge 1: (101, 32) -> 256 = b'e '          ← 'e' + 空格：英文里大量单词以 e 结尾
Merge 2: (97, 116) -> 257 = b'at'          ← cat/sat/mat/rat/ate
Merge 3: (104, 256) -> 258 = b'he '        ← 在 'e ' 基础上继续合并
Merge 4: (116, 258) -> 259 = b'the '
Merge 6: (84, 258) -> 261 = b'The '        ← 大写 The 与小写 the 是两个不同 token
...
Merge 18: (272, 265) -> 273 = b'sat on the '   ← 没有预分词，跨了 3 个词
Merge 23~28: ' l' → ' lan' → ' lang' → ... → ' languag'   ← 一个字母一个字母"长"出来
Merge 30: (260, 100) -> 285 = b'and'

Vocabulary size: 286                       ← 256 + 30

Original:  The cat sat on the mat.
Encoded:   [261, 269, 273, 109, 257, 46]   ← 'The ' 'cat ' 'sat on the ' 'm' 'at' '.'
Tokens:    6 (from 23 bytes)   Ratio: 0.26

Original:  The frog sat on the log.
Tokens:    9 (from 24 bytes)   Ratio: 0.38 ← "frog" 只出现过一次，没被整体合并

Original:  language processing
Encoded:   [108, 260, 103, 117, 97, 103, 256, 112, ...]
Tokens:    17 (from 19 bytes)  Ratio: 0.89 ← 学到的是带前导空格的 ' languag'，
                                              句首没有空格就用不上！

Original:  unhappiness
Tokens:    11 (from 11 bytes)  Ratio: 1.00 ← 完全没见过，退化为逐字节

tiktoken not installed. Run: pip install tiktoken
```

几点值得注意：

- **第一个合并是 `'e '`**：空格被粘在单词**后面**。GPT-2 的预分词正则会把空格放在单词**前面**（如 `" the"`），这里因为没有预分词，完全由频次决定。
- **"language processing" 压缩很差**：语料里 "language" 总是以 `" language"` 形式出现（前面有空格），合并出的是 `' languag'`。测试句以 "language" 开头、没有前导空格，这些合并全部用不上。这是 tokenization 对**前导空格敏感**的经典现象。
- **压缩比随分布外程度上升**：0.26（训练句）→ 0.38 → 0.89 → 1.00（完全没见过）。
- 未安装 tiktoken，`demo_tiktoken` 只打印了安装提示；若安装，会展示 `cl100k_base` 对 `"3.14159265358979"` 等文本的切分（未实际运行该部分）。

---

## 7. 动手改一改

1. 把 `num_merges` 从 30 改成 10 和 100，观察词表大小与 "The cat sat on the mat." 压缩比的变化；100 次时会不会因为 `pairs` 为空而提前结束？
2. 给 `train` 加一个参数 `min_freq=2`：当最高频 pair 的计数小于它时停止训练，对比学到的合并表。
3. 修正 `get_token_str`，让它返回解码后的 `str`；再写一个 `show(tokens)` 函数，把 id 序列打印成 `['The ', 'cat ', ...]` 这种可读形式。
4. 加入最简单的预分词：先用 `re.findall(r" ?\w+| ?[^\w\s]+|\s+", text)` 切成片段，在每个片段内部统计 pair 和合并，确认不再出现 `'sat on the '` 这种跨词 token。
5. 在 `encode` 里实现基于 rank 的编码：每轮在当前序列中找 `merges` 里 id 最小的 pair 合并，直到没有可合并的 pair；用若干句子验证结果与原 `encode` 一致。
6. 用一段中文（如"自然语言处理"）训练和编码，观察每个汉字初始是 3 个字节 token，以及单独 `decode([某个字节])` 时出现的 `�`。

---

## 8. 常见坑

- **以为 `max` 平局是随机的**：实际上取第一个出现的 key，结果依赖语料顺序。改变语料中句子的顺序，合并表可能不同。
- **编码时打乱合并顺序**：比如用 `set` 存合并或对 `merges` 排序，会导致后面的合并拼不出来，编码结果与训练时不一致。
- **混淆 `str` 长度与字节长度**：压缩比的分母是 `len(text.encode("utf-8"))`，中文一个字是 3 字节，不能用 `len(text)`。
- **单独解码一个 token**：byte-level 的 token 可能只是半个字符，单独解码会出现 `�`，并不代表 tokenizer 有 bug。
- **忽视前导空格**：`"language"` 与 `" language"` 是完全不同的 token 序列，构造 prompt 或统计 token 数时要格外注意。
- **把 `_merge_pair` 的越界判断放在后面**：写成 `tokens[i] == pair[0] and tokens[i + 1] == pair[1] and i < len(tokens) - 1` 会在最后一个位置抛 `IndexError`。
