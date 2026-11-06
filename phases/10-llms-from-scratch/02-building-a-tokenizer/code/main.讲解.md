# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 02 节 从头开始构建 Tokenizer ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：Python 标准库（`re`、`unicodedata`、`collections`）；可选 `regex`（支持 `\p{L}` 等 Unicode 属性，未安装时回退到 `re`）、可选 `tiktoken`（最后的对比部分）

---

## 1. 这份代码在考察什么

上一节的 BPE 是"玩具"，这一节把它补成一条**生产级流水线**：

1. **Byte-level 编码**：看清中文（3 字节/字）、日文、emoji（4 字节）在字节层面长什么样。
2. **正则预分词**：GPT-2 的切分规则——缩写、前导空格、数字、标点、空白——以及它如何阻止跨词合并。
3. **片段内 BPE 训练**：合并只在预分词得到的片段内部发生。
4. **特殊 token**：固定 ID、精确匹配、绕过 BPE，为 chat template 打基础。
5. **NFKC 规范化**：编码前统一字符形式。
6. **多语言评估**：对比不同语言的 token 数与 fertility（需要 tiktoken）。

> 一句话：**tokenizer 的难点不在 BPE 本身，而在 BPE 周围那一圈"脏活"**——规范化、预分词、特殊 token 一旦写错，往往不报错，只会悄悄地产生坏数据。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GPT2_PATTERN` | 模块级常量 | 预分词正则；优先用 `regex`，否则回退到 `re` | Pre-tokenization |
| `pre_tokenize(text)` | 函数 | 返回正则匹配到的片段列表 | 预分词 |
| `apply_merge(byte_seq, pair, new_id)` | 函数 | 在一个字节序列中执行一次合并 | BPE 合并 |
| `SpecialTokenHandler` | 类 | 注册特殊 token、把文本切成"普通片段 / 特殊 token" | Special tokens |
| `ProductionTokenizer` | 类 | `normalize / train / add_special_token / encode / decode` | 完整流水线 |
| `demo_byte_encoding` | 函数 | 打印多语言文本的字符数与字节数 | Byte-level |
| `demo_pre_tokenization` | 函数 | 打印 4 段文本的预分词结果 | GPT-2 正则 |
| `demo_full_tokenizer` | 函数 | 训练 50 次合并、注册 4 个特殊 token、编码 6 段测试文本 | 端到端 |
| `demo_tiktoken_comparison` | 函数 | 用 `cl100k_base` 统计 6 种"语言"的 token 数与 fertility | 多语言税 |

数据流（`encode`）：`normalize` → `split_with_specials` → 普通片段 `pre_tokenize` → 每个片段转字节并依次 `apply_merge` → 拼接 ID；特殊片段直接查表得到固定 ID。

---

## 3. 逐段精讲

### 3.1 预分词正则与回退

```python
try:
    import regex
    GPT2_PATTERN = regex.compile(
        r"""'(?:[sdmt]|ll|ve|re)| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+"""
    )
except ImportError:
    GPT2_PATTERN = re.compile(
        r"""'(?:[sdmt]|ll|ve|re)| ?[a-zA-Z]+| ?[0-9]+| ?[^\s\w]+|\s+(?!\S)|\s+"""
    )


def pre_tokenize(text):
    return [match.group() for match in GPT2_PATTERN.finditer(text)]
```

逐个分支看（按顺序尝试，先匹配先得）：

| 分支 | 匹配什么 | 例子 |
|------|---------|------|
| `'(?:[sdmt]\|ll\|ve\|re)` | 英文缩写后缀 | `'t`、`'ll`、`'m` |
| ` ?\p{L}+` | 可选一个前导空格 + 连续字母 | `' world'` |
| ` ?\p{N}+` | 可选前导空格 + 连续数字 | `'3'`、`' 100'` |
| ` ?[^\s\p{L}\p{N}]+` | 可选前导空格 + 连续标点/符号 | `' $'`、`'):'` |
| `\s+(?!\S)` | 一串空白，但不吃掉紧挨下一个词的那个空格 | `'  '` |
| `\s+` | 剩余空白（如字符串末尾） | — |

- 三引号原始字符串 `r"""..."""`：既能包含单引号 `'`，又不需要对反斜杠转义。
- `(?:...)` 是**非捕获分组**，只用于把备选项括起来。
- `(?!\S)` 是**负向先行断言**：要求后面"不是非空白"，但不消耗字符。
- ⚠️ **回退分支有严重 bug**：标准库 `re` 不支持 `\p{L}`，于是用 `[a-zA-Z]` 代替字母、用 `[^\s\w]` 代替标点。但 Python 3 的 `\w` 是 Unicode 感知的，包含汉字、`é`、下划线 `_`。这些字符既不是 `[a-zA-Z]`，又被 `[^\s\w]` 排除，**没有任何分支能匹配**，`finditer` 会直接跳过它们——不报错、静默丢字符。本次运行环境恰好没装 `regex`，结果 `"你好世界 Hello World"` 解码后只剩 `" Hello World"`（见第 6 节）。修复方法见测验 Q8：

```python
# 修复版（只用标准库）
GPT2_PATTERN = re.compile(
    r"""'(?:[sdmt]|ll|ve|re)| ?[^\W\d_]+| ?\d+| ?(?:[^\s\w]|_)+|\s+(?!\S)|\s+"""
)
```

### 3.2 `apply_merge`：与上一节相同的合并操作

```python
def apply_merge(byte_seq, pair, new_id):
    merged = []
    i = 0
    while i < len(byte_seq):
        if i < len(byte_seq) - 1 and byte_seq[i] == pair[0] and byte_seq[i + 1] == pair[1]:
            merged.append(new_id)
            i += 2
        else:
            merged.append(byte_seq[i])
            i += 1
    return merged
```

从左到右、不重叠地把 `pair` 替换成 `new_id`。区别在于：这一节它作用于**单个片段**的字节序列，而不是整段文本。

### 3.3 `SpecialTokenHandler`：特殊 token 的精确匹配

```python
    def add_token(self, token_str, token_id):
        self.special_tokens[token_str] = token_id
        escaped = [re.escape(t) for t in sorted(self.special_tokens.keys(), key=len, reverse=True)]
        self.pattern = re.compile("|".join(escaped))

    def split_with_specials(self, text):
        if not self.pattern:
            return [(text, False)]
        parts = []
        last_end = 0
        for match in self.pattern.finditer(text):
            if match.start() > last_end:
                parts.append((text[last_end:match.start()], False))
            parts.append((match.group(), True))
            last_end = match.end()
        if last_end < len(text):
            parts.append((text[last_end:], False))
        return parts
```

- `re.escape`：`<|end|>` 里的 `|` 在正则中是"或"，必须转义成 `\|` 才能按字面匹配。
- `sorted(..., key=len, reverse=True)`：**长的优先**。正则备选是"第一个能匹配的就用"，如果 `<|end|>` 排在 `<|end|>!` 前面，后者永远匹配不到。（实际验证：按长度排序后 `'hi<|end|>!yo<|end|>'` 正确切成 `('<|end|>!', True)` 和 `('<|end|>', True)`。）
- 每次 `add_token` 都重新编译整条正则——注册次数很少，简单优先。
- `split_with_specials` 是经典的"按匹配切分并保留分隔符"写法：用 `last_end` 记录上一次匹配的结束位置，把两次匹配之间的普通文本标记为 `False`，匹配本身标记为 `True`。返回 `(文本, 是否特殊)` 的元组列表。
- ⚠️ 它会在**任何**文本中识别特殊 token。用户输入 `"user says <|end|> ok"` 时，`<|end|>` 也会被编成特殊 ID——这是 prompt injection 的入口。生产实现（如 tiktoken）默认在普通文本里遇到特殊 token 字符串时直接报错，需要调用方显式声明是否允许。

### 3.4 `ProductionTokenizer.train`：片段内 BPE

```python
    def train(self, text, num_merges):
        text = self.normalize(text)
        chunks = pre_tokenize(text)
        chunk_bytes = [list(chunk.encode("utf-8")) for chunk in chunks]

        for i in range(num_merges):
            pairs = Counter()
            for seq in chunk_bytes:
                for j in range(len(seq) - 1):
                    pairs[(seq[j], seq[j + 1])] += 1
            if not pairs:
                break
            best = max(pairs, key=pairs.get)
            new_id = self.next_id
            self.next_id += 1
            self.merges[best] = new_id
            self.vocab[new_id] = self.vocab[best[0]] + self.vocab[best[1]]
            chunk_bytes = [apply_merge(seq, best, new_id) for seq in chunk_bytes]
```

- 与上一节的关键差别：`pairs` 只在**每个片段内部**统计（内层循环 `range(len(seq) - 1)` 不会跨片段），所以合并永远不会跨越片段边界。
- `self.next_id` 统一管理 ID 分配：合并 token 从 256 开始，训练结束后再注册的特殊 token 接着往后排（本次运行为 306–309）。
- ⚠️ 每个片段**每次出现**都单独存一份、单独计数。真实实现会先对片段去重并记录频次（`" the"` 出现 1 万次只存一份、计数 1 万），速度能提升几个数量级。
- ⚠️ 训练时同样调用 `pre_tokenize`，所以回退正则的 bug 也会让训练语料中的中文、下划线等**根本不参与训练**。

### 3.5 `add_special_token`、`encode`、`decode`

```python
    def add_special_token(self, token_str):
        token_id = self.next_id
        self.next_id += 1
        self.special_handler.add_token(token_str, token_id)
        self.vocab[token_id] = token_str.encode("utf-8")
        return token_id

    def encode(self, text):
        text = self.normalize(text)
        parts = self.special_handler.split_with_specials(text)
        all_ids = []
        for part_text, is_special in parts:
            if is_special:
                all_ids.append(self.special_handler.special_tokens[part_text])
            else:
                for chunk in pre_tokenize(part_text):
                    byte_seq = list(chunk.encode("utf-8"))
                    for pair, new_id in self.merges.items():
                        byte_seq = apply_merge(byte_seq, pair, new_id)
                    all_ids.extend(byte_seq)
        return all_ids
```

- 特殊 token 也写进 `vocab`（值是它的 UTF-8 字节），这样 `decode` 能把它还原成字符串。
- `encode` 的顺序：**先规范化 → 再切出特殊 token → 剩余普通文本预分词 → 每个片段按合并表顺序合并**。特殊 token 在预分词之前被切出，所以 BPE 永远碰不到它。
- `all_ids.extend(byte_seq)`：`extend` 把列表中的元素逐个追加；如果误用 `append`，会得到嵌套列表。
- ⚠️ 编码仍是 O(合并数 × 片段长度) 地逐条重放合并，教学够用，生产中会按 rank 合并并缓存高频片段的结果。

```python
    def decode(self, ids):
        byte_parts = []
        for token_id in ids:
            if token_id in self.vocab:
                byte_parts.append(self.vocab[token_id])
        return b"".join(byte_parts).decode("utf-8", errors="replace")
```

- ⚠️ 不认识的 ID 被**静默跳过**。教学代码为了不崩溃这样写；生产中最好抛异常或至少记录日志，否则 ID 越界这类 bug 很难被发现。
- `normalize` 只是一行 `unicodedata.normalize("NFKC", text)`。它让 "ﬁ"→"fi"、"Ａ"→"A"，但这是**有损**变换：对这类输入，往返检查会失败。

### 3.6 演示函数

```python
    for label, text in texts:
        b = list(text.encode("utf-8"))
        print(f"{label:10s}: {len(text):2d} chars -> {len(b):2d} bytes -> {b[:16]}{'...' if len(b) > 16 else ''}")
```

- `{label:10s}` 字符串左对齐占 10 格，`{len(text):2d}` 整数占 2 格，让表格对齐。
- `demo_full_tokenizer` 的训练语料混合了英文句子和 Python 代码片段（`def train(model, data): ...`），测试文本覆盖英文、中英混合、emoji、代码、特殊 token、"句首无空格"六种情况，并对每条做往返检查。
- `demo_tiktoken_comparison` 中 `fertility = len(toks) / max(words, 1)`：`max(words, 1)` 防止除零；但中文、日文没有空格，`split()` 只得到 1 个"词"，所以这两行的 fertility 实际等于"整句 token 数"，不能与英文直接对比（⚠️ 指标在无空格语言上失真）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `try: import regex` 否则回退 `re` | 不强制安装第三方包 | 回退正则会静默丢弃非 ASCII 字母和下划线；生产中应强制依赖 `regex` 或使用修复版正则，并加 `"".join(chunks) == text` 断言 |
| 预分词后片段内 BPE | 阻止跨词合并，token 可解释 | 失去少量跨词压缩机会；SentencePiece 做了相反的选择 |
| 片段不去重 | 代码直观 | 训练慢；生产中按"唯一片段 + 频次"计数 |
| 特殊 token 训练后再追加 ID | 不干扰 BPE，ID 连续 | 真实模型通常预留一段特殊 token ID 区间，便于以后扩展 |
| 特殊 token 按长度降序构造正则 | 处理前缀冲突 | 每次注册重新编译，注册量大时可改为 trie |
| 任意文本中都识别特殊 token | 实现简单 | 有注入风险；生产中区分可信模板与不可信用户内容 |
| `encode` 内做 NFKC | 统一字符形式 | 有损；需保证训练与推理一致 |
| `decode` 跳过未知 ID | 不崩溃 | 掩盖 bug；生产中应报错 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `try/except ImportError` | `try: import regex ... except ImportError:` | 可选依赖：有就用，没有就回退 |
| 原始字符串 + 三引号 | `r"""'(?:[sdmt]\|ll...)"""` | `r` 让反斜杠不转义；三引号允许字符串内含单引号 |
| 正则：`re.compile` / `finditer` / `match.group()` | `GPT2_PATTERN.finditer(text)` | 预编译正则；`finditer` 逐个返回匹配对象，`group()` 取匹配文本 |
| 正则：非捕获分组、先行断言 | `(?:...)`、`(?!\S)` | 分组但不捕获；断言后面不是某字符且不消耗字符 |
| 正则：`match.start()` / `match.end()` | `split_with_specials` | 匹配在原文中的起止位置 |
| `re.escape` | `re.escape(t)` | 把 `\|`、`.` 等元字符转义成字面量 |
| `sorted(key=..., reverse=True)` | `sorted(self.special_tokens.keys(), key=len, reverse=True)` | 按长度从长到短排序 |
| `"\|".join(...)` | `re.compile("\|".join(escaped))` | 把多个模式拼成"或"关系 |
| `unicodedata.normalize` | `unicodedata.normalize("NFKC", text)` | Unicode 规范化 |
| 元组列表 + 解包 | `parts.append((text, False))`、`for part_text, is_special in parts` | 一次传递两个相关值 |
| `list.extend` vs `append` | `all_ids.extend(byte_seq)` | `extend` 逐个追加元素，`append` 追加整个对象 |
| `in` 判断字典键 | `if token_id in self.vocab` | O(1) 查找 |
| `dict.get(key, default)` | `self.vocab.get(token_id, b"<?>")` | 键不存在时返回默认值 |
| 列表推导式 | `[apply_merge(seq, best, new_id) for seq in chunk_bytes]` | 对每个片段执行合并 |
| f-string 宽度与对齐 | `{label:10s}`、`{len(b):2d}`、`{label:<10}`、`{fertility:<10.2f}` | `<` 左对齐，数字表示宽度，`.2f` 两位小数 |
| `max(x, 1)` 防除零 | `len(toks) / max(words, 1)` | 简洁的分母保护 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示 |

---

## 6. 运行结果解读

实际运行环境：Python 3.13，**未安装 `regex` 与 `tiktoken`**（因此走的是 `re` 回退正则，最后的 tiktoken 对比被跳过）。关键输出：

```text
Chinese   :  2 chars ->  6 bytes -> [228, 189, 160, 229, 165, 189]   ← 每个汉字 3 字节
Japanese  :  5 chars -> 15 bytes -> [227, 129, 147, ...]             ← 平假名也是 3 字节
Emoji     :  2 chars ->  8 bytes -> [240, 159, 148, 165, ...]        ← 每个 emoji 4 字节

'Hello, world! Don't stop.'
  -> ['Hello', ',', ' world', '!', ' Don', "'t", ' stop', '.']       ← 句首没有前导空格
'def train(model, data):'
  -> ['def', ' train', '(', 'model', ',', ' data', '):']
'The price is $3.14 per unit.'
  -> ['The', ' price', ' is', ' $', '3', '.', '14', ' per', ' unit', '.']
'  multiple   spaces   here  '
  -> [' ', ' multiple', '  ', ' spaces', '  ', ' here', '  ']         ← \s+(?!\S) 的效果
```

- 讲义 Step 2 的注释写的是 `[' Hello', ...]`，实际是 `'Hello'`——输入以字母开头，可选空格匹配不到任何空格，讲义注释有误。
- `$3.14` 被切成 `' $'`、`'3'`、`'.'`、`'14'`，小数点属于标点类。
- 多空格时，每段空白的最后一个空格总是留给后面的单词。

训练（50 次合并）：

```text
Merge 1: (105, 110) -> 256 = b'in'
Merge 3: (32, 116) -> 258 = b' t'
Merge 7: (261, 108) -> 262 = b'model'
Merge 15: (32, 262) -> 270 = b' model'
Merge 25: (279, 103) -> 280 = b' learning'
Merge 30: (41, 58) -> 285 = b'):'          ← 代码标点也会被合并
Merge 47: (301, 101) -> 302 = b' Machine'
Vocab size: 310
Special tokens: <|begin|>=306, <|end|>=307, <|user|>=308, <|assistant|>=309
```

- 没有任何合并跨越空格中间（所有含空格的 token 都是"前导空格 + 词"），这正是预分词的效果；对比上一节出现的 `b'sat on the '`。
- `'model'`（262）和 `' model'`（270）是两个不同的 token：一个用于 `(model` 这类前面是标点的位置，一个用于句中。

编码测试：

```text
Input:   The quick brown fox.
IDs:     [286, 290, 293, 294, 46]          Tokens: 5 (from 20 bytes, ratio: 0.25)   PASS

Input:   你好世界 Hello World
IDs:     [32, 72, 101, 108, 108, 111, 32, 87, ...]
Decoded:  Hello World                      Round-trip: FAIL   ← 中文被静默丢弃！

Input:   🔥🌍🚀
Tokens:  12 (from 12 bytes, ratio: 1.00)  PASS      ← 没学过 emoji 的合并，逐字节

Input:   def foo(x): return x + 1
Tokens:  18 (from 24 bytes, ratio: 0.75)  PASS      ← 'de'、' fo'、'):'、're'、'rn' 等合并起作用

Input:   <|begin|><|user|>Hello<|end|>
IDs:     [306, 308, 72, 101, 108, 108, 111, 307]   PASS   ← 特殊 token 各占 1 个 ID

Input:   Machine learning is powerful.
IDs:     [77, 97, 99, 104, 256, 101, 280, ...]     PASS   ← 句首 "Machine" 无前导空格，
                                                            用不上 ' Machine'（302）
```

- **最重要的一行是 FAIL**：`"你好世界"` 在回退正则下没有被任何分支匹配，被 `finditer` 跳过，编码结果里根本没有它的字节。如果安装了 `regex`，`\p{L}+` 会匹配汉字，按代码逻辑这一行预期会变成 PASS（12 个中文字节 + 英文部分；本环境没有 `regex`，未实际验证）。这说明讲义"Chinese characters produce 3 bytes each... None of these crash the tokenizer"的结论只在装了 `regex` 时成立。
- emoji 压缩比 1.00：语料里没有 emoji，没有学到相关合并，退化为逐字节——但依然能正确往返，这正是 byte-level 的价值。
- `"Machine learning is powerful."` 再次展示了前导空格敏感性：`' learning'`（280）用上了，但句首 `Machine` 只能拆成 `M a c h in e`。
- tiktoken 未安装，`demo_tiktoken_comparison` 只打印了安装提示（未实际运行该部分）。若安装，会输出 6 种语言的 token 数与 fertility 表；如第 3.6 节所述，中文、日文的 fertility 因 `split()` 无法分词而失真。

---

## 7. 动手改一改

1. 用测验 Q8 的修复版正则替换回退分支，重新运行，确认 `"你好世界 Hello World"` 往返 PASS；并为 `pre_tokenize` 加上断言 `"".join(chunks) == text`。
2. 完成讲义练习 1：用已有的 `get_token_bytes(id)` 打印 ID 256–305 对应的字节，找出哪些 token 来自代码语料。
3. 给 `ProductionTokenizer.encode` 增加参数 `allow_special=False`：为 `False` 时，普通文本中出现的特殊 token 字符串按普通文本编码（或直接抛 `ValueError`），体会 tiktoken 的安全默认值。
4. 训练前先对片段去重：用 `Counter(chunks)` 得到"片段 → 频次"，统计 pair 时乘以频次；对比与原实现学到的合并表是否一致、速度差多少。
5. 完成讲义练习 2：实现"按空白和数字切分、保留前导空格"的 Llama 风格预分词器，在同一语料上比较两种预分词学到的词表。
6. 完成讲义练习 3：实现 Llama 3 chat template（参考测验 Q10），注册 `<|begin_of_text|>`、`<|start_header_id|>`、`<|end_header_id|>`、`<|eot_id|>`，编码一段对话并验证往返。

---

## 8. 常见坑

- **静默丢字符**：`re` 回退正则不认识汉字、`é`、下划线，`finditer` 直接跳过且不报错。任何预分词器都应满足"拼回去等于原文"。
- **特殊 token 正则未转义**：`<|end|>` 中的 `|` 不转义会被当成"或"，匹配到空串或 `<`。
- **特殊 token 注册顺序**：前缀冲突时短的先匹配，长的永远匹配不上；本代码用长度降序规避。
- **规范化导致往返失败**：NFKC 会改变 "ﬁ"、全角字符、上标等，`decode(encode(x)) != x` 是预期行为而非 bug。
- **句首 vs 句中**：`"Hello"` 与 `" Hello"` 是不同的 token 序列，构造 prompt 时多一个/少一个空格都会改变编码。
- **用 `split()` 计算中日文 fertility**：没有空格的语言会被当成 1 个词，数字毫无意义。
