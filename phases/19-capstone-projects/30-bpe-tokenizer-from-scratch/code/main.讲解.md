# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 30 节 从零实现 BPE Tokenizer ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）或 `cd code && python3 main.py`；测试：`python3 -m pytest code/tests/ -v` ｜ **依赖**：仅标准库（`json`、`re`、`collections.Counter`、`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

这份代码用约 300 行纯 Python 实现了一个**字节级 BPE（Byte-Pair Encoding）tokenizer**，覆盖 tokenizer 的完整生命周期：

1. **词表布局**：id 0–255 是原始字节，256、257 是 special token，之后是学到的合并。
2. **预分词**：用正则把文本切成"非空白串 / 空白串"，合并只在块内进行。
3. **训练**：统计相邻 pair（按块频次加权）→ 选最高频（确定性平局规则）→ 全语料替换 → 记录合并，直到达到目标词表或无可合并。
4. **编码**：对每个块反复应用"rank 最小"的合并。
5. **解码**：id → 字节拼接 → UTF-8。
6. **special token**：`allow_special=True` 时把字面量映射为保留 id。
7. **持久化**：`save / load` 到 JSON，保留合并顺序。

> 一句话：**合并表（以及它的顺序）就是 tokenizer；训练和推理共享它，才能保证"字节进、id 出、id 回到同样的字节"**。同时注意代码与讲义的几处出入：预分词并不切标点、special token 并没有从训练语料中排除（会导致撞 id）、demo 目标是 320 而不是讲义说的 300。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BYTE_ALPHABET_SIZE` / `DEFAULT_SPECIALS` / `WORD_SPLIT_RE` | 常量 | 256 字节、两个 special token、预分词正则 | 词表布局 |
| `BPETokenizer` | dataclass | 保存 `vocab`、`inv_vocab`、`merges`、special 映射；`initialize` 布置字节与 special | tokenizer 状态 |
| `_pretokenize` | 函数 | `\S+\|\s+` 切块 | 预分词 |
| `_word_to_byte_ids` | 函数 | 字符串 → UTF-8 字节 id 列表 | 字节字母表 |
| `_build_initial_units` | 函数 | 语料 → `{字节元组: 出现次数}` | 训练单元去重 |
| `_count_pairs` | 函数 | 按块频次加权统计相邻 pair | pair 频次 |
| `_apply_merge` / `_apply_merge_to_corpus` | 函数 | 在一个块 / 全部块中把 pair 替换为新 id | 合并 |
| `train` | 函数 | 训练主循环 | BPE 训练 |
| `_encode_chunk` / `_encode_pretokenized` / `encode` | 函数 | 按 rank 应用合并；处理 special token | 编码 |
| `decode` | 函数 | id → 字节 → 字符串 | 解码 |
| `save` / `load` | 函数 | JSON 序列化与恢复 | 持久化 |
| `DEMO_CORPUS` / `main` | 常量 / 函数 | 18 行英文 × 6 的演示语料；训练、编码、打印 | 演示 |

数据流：`main` → `train(tokenizer, DEMO_CORPUS, 320)`（`initialize` → `_build_initial_units` → 循环 `_count_pairs` / `_apply_merge_to_corpus`）→ `encode(held_out)`（`_pretokenize` → `_encode_chunk`）→ `decode` → 断言往返一致 → 打印前 8 个合并 → `encode(..., allow_special=True)` 演示 special token。

---

## 3. 逐段精讲

### 3.1 `BPETokenizer` 与 `initialize`：词表布局

```python
@dataclass
class BPETokenizer:
    vocab: dict[int, bytes] = field(default_factory=dict)
    inv_vocab: dict[bytes, int] = field(default_factory=dict)
    merges: dict[tuple[int, int], int] = field(default_factory=dict)
    special_to_id: dict[str, int] = field(default_factory=dict)
    id_to_special: dict[int, str] = field(default_factory=dict)

    def _add_token(self, token_bytes: bytes) -> int:
        if token_bytes in self.inv_vocab:
            return self.inv_vocab[token_bytes]
        token_id = len(self.vocab)
        self.vocab[token_id] = token_bytes
        self.inv_vocab[token_bytes] = token_id
        return token_id
```

- `vocab`：id → 字节串，解码用；`inv_vocab`：字节串 → id，用于去重。
- `merges`：`(左 id, 右 id) → 新 id`。Python 3.7+ 的 dict 保持插入顺序，所以**插入顺序就是 rank**——这是整个编码算法依赖的隐含前提。
- 新 id 取 `len(self.vocab)`，id 连续分配。
- `_add_token` 的"已存在就返回旧 id"有两个后果：
  - 两个不同的 pair 合出相同字节（例如 `ab+c` 与 `a+bc`）时，它们映射到同一个 id，词表不增长；
  - ⚠️ 合并结果若恰好等于某个 special token 的字节，会**返回 special 的 id**（见 3.4 与测验 Q9）。

```python
    def initialize(self, specials: Iterable[str] = DEFAULT_SPECIALS) -> None:
        self.vocab.clear(); ...
        for i in range(BYTE_ALPHABET_SIZE):
            self._add_token(bytes([i]))
        for s in specials:
            token_id = len(self.vocab)
            self.vocab[token_id] = s.encode("utf-8")
            self.inv_vocab[s.encode("utf-8")] = token_id
            self.special_to_id[s] = token_id
            self.id_to_special[token_id] = s
```

- 先清空再重建，因此可重复调用（测试 `test_initialize_is_idempotent`）。
- `bytes([i])` 构造只含一个字节的 bytes 对象（注意 `bytes(5)` 会得到 5 个零字节，必须传列表）。
- special token 紧跟字节块：`<|endoftext|>` = 256，`<|pad|>` = 257。它们的字节串也放进了 `inv_vocab`，这是撞 id 问题的根源。
- `vocab_size` 属性就是 `len(self.vocab)`，包含 special token。

### 3.2 预分词与初始单元

```python
WORD_SPLIT_RE = re.compile(r"\S+|\s+")

def _pretokenize(text: str) -> list[str]:
    return WORD_SPLIT_RE.findall(text)

def _build_initial_units(corpus: str) -> dict[tuple[int, ...], int]:
    chunks = _pretokenize(corpus)
    units: dict[tuple[int, ...], int] = {}
    for chunk in chunks:
        symbols = tuple(_word_to_byte_ids(chunk))
        units[symbols] = units.get(symbols, 0) + 1
    return units
```

- `\S+|\s+` 把文本切成交替的"非空白串"与"空白串"，两者拼起来正好是原文，所以解码只需拼接。
- ⚠️ 讲义说"splits the corpus on whitespace and punctuation boundaries"，但这个正则**不切标点**：`"write,"` 是一个块，和 `"write"` 是两个不同的训练单元。
- 空白单独成块：`' '`、`'\n'`、`'  '` 各是一个块。单字节块没有 pair，永远是 1 个 token——这就是 held-out 句子里 8 个空格各占一个 id 的原因（GPT-2 风格的"前导空格并入单词"见测验 Q11）。
- **按块去重计数**：演示语料 2136 个块只有 113 种不同的块（实测）。训练循环只处理这 113 个元组，再乘以频次，速度因此很快。元组可哈希，可以作字典键；列表不行。

### 3.3 pair 计数与合并

```python
def _count_pairs(corpus_units: dict[tuple[int, ...], int]) -> Counter:
    pairs: Counter = Counter()
    for symbols, count in corpus_units.items():
        for i in range(len(symbols) - 1):
            pairs[(symbols[i], symbols[i + 1])] += count
    return pairs
```

- 每个块里的相邻 pair 按**块频次加权**累加。例如 `"the"` 出现 150 次时，`(t,h)` 一次就加 150。
- 演示语料初始最高频 pair：`th=150, he=114, to=66, ea=66, is=66, er=60, an=60, re=60`（实测）。
- 统计的是**重叠**出现：`aaa` 中 `(a,a)` 计 2 次。

```python
def _apply_merge(symbols, pair, new_id):
    if len(symbols) < 2:
        return symbols
    out: list[int] = []
    i = 0
    a, b = pair
    while i < len(symbols):
        if i < len(symbols) - 1 and symbols[i] == a and symbols[i + 1] == b:
            out.append(new_id)
            i += 2
        else:
            out.append(symbols[i])
            i += 1
    return tuple(out)
```

- 从左到右扫描，匹配到就替换并**跳过 2 个**，所以是**不重叠**替换：`aaa` 合并 `(a,a)` 得到 `[aa, a]`。
- `_apply_merge_to_corpus` 对每个块调用它，并把结果相同的块计数合并（不同块合并后可能变成同一个元组）。

### 3.4 `train`：训练主循环

```python
def train(tokenizer, corpus, target_vocab_size, specials=DEFAULT_SPECIALS) -> None:
    tokenizer.initialize(specials)
    units = _build_initial_units(corpus)
    while tokenizer.vocab_size < target_vocab_size:
        pairs = _count_pairs(units)
        if not pairs:
            break
        max_count = max(pairs.values())
        candidates = sorted(p for p, c in pairs.items() if c == max_count)
        best = candidates[0]
        if pairs[best] < 2:
            break
        new_id = tokenizer._add_token(tokenizer.vocab[best[0]] + tokenizer.vocab[best[1]])
        tokenizer.merges[best] = new_id
        units = _apply_merge_to_corpus(units, best, new_id)
```

逐行要点：

- **停止条件有三个**：词表达到目标；没有任何 pair（所有块都已是单个 token）；最高频 pair 不足 2 次（再合并没有压缩意义）。第三个条件解释了为什么目标 600 时词表只长到 528。
- **平局规则**：取所有最高频 pair，按 `(左 id, 右 id)` 元组排序取第一个。这样结果只取决于语料内容，不受 dict 迭代顺序影响（文档字符串："Ties on pair counts are broken by sorting on the pair itself"）。例：`"ab ba "*3` 中 `(97,98)` 与 `(98,97)` 各 3 次，选 `(97,98)` 即 `ab`。
- 新 token 的字节串 = 左右两个 token 的字节串拼接，所以任何 id 都能递归展开为原始字节。
- **每轮都全量重算**：`_count_pairs` 与 `_apply_merge_to_corpus` 每次都遍历全部不同块，复杂度约 O(合并数 × 语料符号数)。演示语料上目标 600 的训练只要约 0.03 秒；我们在 10 万词（5000 种不同词）的合成语料上实测 1000 次合并约 8.8 秒——讲义"一百万词、一万词表几秒内完成"的说法偏乐观。生产实现会增量更新 pair 计数（只更新受影响块）。
- ⚠️ **special token 没有从语料中排除**：讲义说"we keep them out of the pretokenized stream entirely"，但 `train` 直接对整个 `corpus` 预分词。若语料含有独立的 `<|endoftext|>` 块（例如 `"hello <|endoftext|> world " * 50`），合并最终会产生字节串 `b"<|endoftext|>"`，`_add_token` 返回 256，于是 `merges[...] = 256`。实测此后 `encode(..., allow_special=False)` 也会输出 256，违背了"关闭时按字节编码"的契约。修复见测验 Q9。

### 3.5 `_encode_chunk`：按 rank 应用合并

```python
def _encode_chunk(tokenizer, chunk) -> list[int]:
    symbols: list[int] = _word_to_byte_ids(chunk)
    if len(symbols) < 2:
        return symbols

    ranked_merges = {pair: rank for rank, pair in enumerate(tokenizer.merges.keys())}

    while True:
        best_rank = None
        best_index = -1
        best_pair = None
        for i in range(len(symbols) - 1):
            pair = (symbols[i], symbols[i + 1])
            rank = ranked_merges.get(pair)
            if rank is None:
                continue
            if best_rank is None or rank < best_rank:
                best_rank = rank
                best_index = i
                best_pair = pair
        if best_pair is None:
            break
        new_id = tokenizer.merges[best_pair]
        symbols = symbols[:best_index] + [new_id] + symbols[best_index + 2:]
    return symbols
```

- `enumerate(merges.keys())` 把插入顺序变成 rank：第 0 个学到的合并 rank 为 0。
- 每轮扫描所有相邻 pair，找 rank 最小的；`rank < best_rank` 是严格小于，所以同一 rank 出现多次时取**最左边**的那一处。
- 一次只合并一处，然后重新扫描，直到没有任何 pair 在合并表中。
- 例：合并表 `[(a,a)→258, (aa,a)→259]` 下，`"aaaa"` → `[258, 97, 97]` → `[258, 258]`（rank 0 的 `(a,a)` 优先于 rank 1 的 `(aa,a)`），而不是"最长匹配"的 `[259, 97]`。
- 这种"按 rank"的编码与训练时的处理顺序一致：我们对演示语料（目标 600）的 113 种块逐一比较"训练时的最终切分"与"重新编码"的结果，0 处不一致。
- ⚠️ 性能：`ranked_merges` 在**每个块**上都重建一次（O(合并数)），每个块内是 O(L²)。演示规模下无所谓（整段语料编码约 0.02 秒），大规模时应只建一次 rank 表并缓存块的编码结果（测验 Q10）。

### 3.6 `encode`：special token 处理

```python
def encode(tokenizer, text, allow_special=False) -> list[int]:
    if not allow_special:
        return _encode_pretokenized(tokenizer, text)
    if not tokenizer.special_to_id:
        return _encode_pretokenized(tokenizer, text)

    specials_sorted = sorted(tokenizer.special_to_id.keys(), key=len, reverse=True)
    pattern = "(" + "|".join(re.escape(s) for s in specials_sorted) + ")"
    parts = re.split(pattern, text)

    out: list[int] = []
    for part in parts:
        if part == "":
            continue
        if part in tokenizer.special_to_id:
            out.append(tokenizer.special_to_id[part])
        else:
            out.extend(_encode_pretokenized(tokenizer, part))
    return out
```

- 默认 `allow_special=False`：special 字面量当普通字节处理。
- 允许时先用正则把文本按 special 字符串切开，**再**对普通片段预分词与编码，所以 special token 绝不会参与合并。
- `re.escape`：`<|endoftext|>` 里的 `|` 是正则元字符，必须转义。
- 按长度**降序**排列：当一个 special 是另一个的前缀时（例如 `<|end|>` 与 `<|endoftext|>`），正则的分支按顺序尝试，长的放前面才能匹配完整的那个。
- `re.split` 的模式带**捕获组** `(...)`，分隔符本身也会出现在结果列表中——这正是我们需要的（否则 special token 会被丢掉）。分隔符在开头/结尾时会产生空串，所以要 `if part == ""` 跳过。
- 例：`'doc one<|endoftext|>doc two'` → `['doc one', '<|endoftext|>', 'doc two']` → 实测 ids `[276, 99, 32, 270, 101, 256, 276, 99, 32, 116, 119, 111]`。注意 `one` 被切成 `on` + `e`，因为在训练语料中 `one` 只出现在 "once" 等词里。
- 每次调用都重新构造正则，频繁调用时可缓存。

### 3.7 `decode`

```python
def decode(tokenizer, ids: list[int]) -> str:
    pieces: list[bytes] = []
    for token_id in ids:
        if token_id in tokenizer.id_to_special:
            pieces.append(tokenizer.id_to_special[token_id].encode("utf-8"))
            continue
        if token_id not in tokenizer.vocab:
            raise KeyError(f"unknown token id: {token_id}")
        pieces.append(tokenizer.vocab[token_id])
    return b"".join(pieces).decode("utf-8", errors="replace")
```

- 先拼接**字节**再统一解码：一个多字节字符可能被拆在多个 token 中，逐个 token 解码会出错。
- `errors="replace"`：非法 UTF-8 片段变成 `�`，不抛异常。实测 `decode([240])` 得到 `'�'`，`decode([240, 159, 166, 138])` 得到 `'🦊'`。
- 未知 id 抛 `KeyError`，比静默跳过更安全。
- 对 `encode` 产生的 id 序列，往返总是精确的（encode 不丢任何字节）；"有损"只会发生在手工截断的 id 序列上。
- 注意歧义：`allow_special=False` 编码出的 `<|endoftext|>` 字节与 special id 256 解码出来是同一个字符串，从文本上无法区分。

### 3.8 `save` / `load`

```python
    payload = {
        "vocab": {str(token_id): list(token_bytes) for token_id, token_bytes in tokenizer.vocab.items()},
        "merges": [[list(pair), new_id] for pair, new_id in tokenizer.merges.items()],
        "specials": tokenizer.special_to_id,
    }
```

- JSON 的对象键只能是字符串，所以 id 写成 `str(token_id)`，加载时 `int(...)` 还原。
- `bytes` 不能直接 JSON 序列化，转成整数列表（`list(b"th")` → `[116, 104]`），加载时 `bytes(byte_list)` 还原。
- `merges` 存成**列表**而不是对象，明确保留顺序（rank）；加载时按顺序插入 dict，rank 不变。测试 `test_save_and_load_round_trip` 验证保存前后编码结果一致。
- `load` 没有做任何校验（例如 merges 引用的 id 是否存在、vocab 是否连续），生产中应加版本号与校验。
- `json.dump(..., indent=2)` 便于阅读，但 vocab 的每个字节列表都会被展开成多行，文件较大。

### 3.9 `main`：演示

- `DEMO_CORPUS` 是 18 行格言 × 6 次重复（5562 个字符），重复保证常见 pair 计数足够。
- `_format_byte_token` 把 token 显示成可读形式：空格换成 `·`、换行换成 `\n`；无法按 UTF-8 解码的（半个字符）显示为十六进制。
- `assert roundtrip == held_out`：演示中的硬断言。
- `raise SystemExit(main())`：与 `sys.exit(main())` 等价，以返回值作为退出码。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 字节级字母表 | 任何 UTF-8 输入都能表示，无 OOV | 罕见字符被拆成多个字节 token；单 token 可能不是完整字符 |
| `\S+\|\s+` 预分词 | 简单、能无损拼回原文 | 不切标点；空格独占 token，浪费序列长度；生产用 GPT-2/tiktoken 风格正则 |
| 按块去重计数 | 训练只处理不同块，快很多 | 仍是每轮全量重算；大规模需增量更新 + 堆 |
| 平局按 pair 排序 | 确定性、可复现 | 偏向小字节值，不一定"语言学上"最优（无所谓） |
| 最高频 < 2 时停止 | 避免学无意义的合并 | 实际词表可能小于目标（528 < 600），调用方需检查 `vocab_size` |
| `merges` 用 dict 插入顺序表示 rank | 写法简洁 | 依赖 dict 有序语义；序列化时必须用列表 |
| `_add_token` 按字节去重 | 避免重复条目 | 会与 special token 撞 id；special 应单独管理 |
| special 不从训练语料移除 | 实现简单 | 语料含 special 字面量时契约被破坏（讲义声称已排除） |
| `allow_special` 默认 False | 防止用户文本伪造控制 token | 静默编码为字节；tiktoken 默认直接报错 |
| 编码每块重建 rank 表 | 代码自包含 | 大文本编码慢；应只建一次并缓存 |
| JSON 持久化 | 可读、无依赖 | 文件大、无版本/校验；生产用专门格式（如 tokenizer.json、tiktoken 的 base64 rank 文件） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许 `dict[int, bytes]`、`X \| None` 注解在旧版本运行 |
| `@dataclass` + `field(default_factory=dict)` | `class BPETokenizer` | 每个实例一份独立的字典 |
| `@property` | `def vocab_size(self) -> int` | 以属性方式访问 |
| `bytes` 字面量与构造 | `bytes([i])`、`b"".join(pieces)` | 单字节对象；拼接字节串 |
| `str.encode` / `bytes.decode` | `word.encode("utf-8")`、`.decode("utf-8", errors="replace")` | 文本与字节互转，替换非法序列 |
| `list(bytes)` | `list(word.encode("utf-8"))` | 字节串转整数列表（0–255） |
| 元组作字典键 | `units[symbols] = ...`、`merges[(a, b)]` | 列表不可哈希，元组可以 |
| `collections.Counter` | `pairs[(x, y)] += count` | 缺失键默认 0 的计数字典 |
| `dict.get(k, 0)` | `units.get(symbols, 0) + 1` | 带默认值的读取 |
| 生成器表达式 + `sorted` | `sorted(p for p, c in pairs.items() if c == max_count)` | 过滤后排序，元组按字典序比较 |
| 字典推导式 + `enumerate` | `{pair: rank for rank, pair in enumerate(tokenizer.merges.keys())}` | 把顺序变成 rank |
| 元组解包 | `a, b = pair` | 一次取出两个元素 |
| 列表切片拼接 | `symbols[:best_index] + [new_id] + symbols[best_index + 2:]` | 用新元素替换两个元素 |
| `while True` + `break` | `_encode_chunk` | 直到无可应用的合并 |
| `re.compile` / `findall` / `split` / `escape` | `WORD_SPLIT_RE.findall(text)`、`re.split(pattern, text)` | 预编译、全部匹配、带捕获组切分、转义元字符 |
| `sorted(..., key=len, reverse=True)` | `specials_sorted` | 按长度降序 |
| `Iterable` 类型注解 | `specials: Iterable[str] = DEFAULT_SPECIALS` | 接受任何可迭代对象 |
| `try / except UnicodeDecodeError` | `_format_byte_token` | 解码失败时改用 `hex()` 显示 |
| `with open(...)` + `json.dump/load` | `save` / `load` | 自动关闭文件；JSON 读写 |
| 字符串乘法 | `"""...""" * 6` | 重复 6 次 |
| f-string 格式 | `{rank:>2}`、`{left!s:>8}`、`{held_out!r}` | 右对齐宽度 2/8；`!s` 用 `str()`；`!r` 用 `repr()` |
| `assert` | `assert roundtrip == held_out, "..."` | 演示中的断言 |
| `raise SystemExit(main())` | 文件末尾 | 以返回值为退出码退出 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`cd code && python3 main.py`，退出码 0；结果完全确定，每次相同）：

```text
Vocabulary summary
------------------
target size       : 320
final vocab size  : 320                ← 256 字节 + 2 special + 62 合并
merges learned    : 62
special tokens    : ['<|endoftext|>', '<|pad|>']

Encoding a held-out sentence
----------------------------
input             : 'the fox is quick and the dog is lazy'
encoded ids       : [259, 32, 296, 120, 32, 261, 32, 299, 283, 107, 32, 305, 32, 259, 32, 276, 103, 32, 261, 32, 297, 122, 121]
id count          : 23 (vs 36 raw bytes)
decoded back      : 'the fox is quick and the dog is lazy'

Highest-rank learned merges
---------------------------
  rank  0: (       t,        h) -> th
  rank  1: (      th,        e) -> the
  rank  2: (       e,        a) -> ea
  rank  3: (       i,        s) -> is
  rank  4: (       t,        o) -> to
  rank  5: (       a,        n) -> an
  rank  6: (       e,        r) -> er
  rank  7: (       o,        u) -> ou

Special-token handling
----------------------
input             : 'doc one<|endoftext|>doc two'
encoded ids       : [276, 99, 32, 270, 101, 256, 276, 99, 32, 116, 119, 111]
decoded back      : 'doc one<|endoftext|>doc two'

Demo OK.
```

逐项解读：

- **23 个 id 对应**：`['the', ' ', 'fo', 'x', ' ', 'is', ' ', 'qu', 'ic', 'k', ' ', 'and', ' ', 'the', ' ', 'do', 'g', ' ', 'is', ' ', 'la', 'z', 'y']`。8 个空格各占一个 id（id 32），这是"空白单独成块"的代价。压缩比 23/36 ≈ 0.64。
- **第一个合并是 `th`**：初始计数 `th=150` 最高（`the` 在语料中极其常见），第二个合并 `(th, e)` 立刻得到 `the`（id 259）。
- **rank 2–4 是 `ea`、`is`、`to`**：合并 `th`、`the` 之后，这三个 pair 都是 66 次并列最高，按平局规则比较 pair 元组：`(101,97) < (105,115) < (116,111)`，于是依次是 `ea`、`is`、`to`。注意 `he`（初始 114）没有出现——它几乎全部来自 `the`，合并 `th` 之后就被"吃掉"了，说明每轮都基于**当前**语料重新计数。
- **special 演示**：id 256 出现在中间，两侧的 `doc one` 和 `doc two` 正常编码；解码完全还原。
- **压缩曲线**（另行实测，held-out 句子）：目标 258/280/300/320/400/600 → id 数 36/28/24/23/17/17；目标 600 时词表只长到 528。目标 400 时 9 个单词已各成一个 token，17 = 9 个词 + 8 个空格，是这种预分词下的下限。讲义"从 300 改到 600 观察长度下降"在这份语料上会看到 24 → 17，然后饱和。

---

## 7. 动手改一改

1. **压缩曲线**：按讲义建议把 `target` 改成 300、400、600、1000，记录最终词表大小与 id 数；解释为什么 600 与 1000 结果相同。
2. **修复 special 撞 id**：训练前先按 special 字符串切开语料并丢弃 special 片段；让 `_add_token` 不与 special 去重；添加回归测试（语料 `"hello <|endoftext|> world " * 50`，断言 `allow_special=False` 的编码不含 256）。
3. **真正的 Unicode 测试**：`test_unicode_round_trip` 的文本里其实没有任何非 ASCII 字符。补一条含 emoji 与中文的往返测试（如 `"fox 🦊 says 你好"`），并测试 `decode` 单独一个字节 id 的结果。
4. **GPT-2 风格预分词**：把 `WORD_SPLIT_RE` 换成测验 Q11 的正则，比较 held-out 句子的 id 数（实测 23 → 18），再观察学到的合并里出现 `' the'` 这类带前导空格的 token。
5. **加速编码**：rank 表只建一次 + `functools.lru_cache` 缓存块的编码结果；用随机字符串做"新旧实现输出一致"的对比测试。
6. **进阶**：实现增量训练——维护 `pair → 计数` 和 `pair → 所在块` 索引，合并时只更新受影响的块；在 10 万词语料上对比训练时间（原实现 1000 次合并约 8.8 秒）。

---

## 8. 常见坑

- **用 `bytes(n)` 构造单字节**：`bytes(5)` 是 5 个零字节；要写 `bytes([5])`。
- **逐 token 解码**：多字节字符会被拆开得到 `�`；应先拼接字节再解码，流式输出要缓冲。
- **编码时不按 rank**：用最长匹配或按任意顺序应用合并，会得到训练时从未见过的切分。
- **合并表顺序丢失**：把 merges 存成无序结构（如 JSON 对象后再排序键）会改变 rank。
- **忘记重新计数**：合并后旧的 pair 计数作废（测验 Q1：`pu` 从 17 降到 12）。
- **special token 进入训练语料**：会被当作普通文本学成合并，甚至与保留 id 冲突。
- **`re.split` 不带捕获组**：special token 会从结果中消失。
- **special 字符串前缀重叠时不按长度排序**：可能只匹配到较短的那个。
- **以为目标词表一定能达到**：语料太小时训练会提前停止，下游 embedding 尺寸应以实际 `vocab_size` 为准。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m pytest -q tests`（或 `python3 -m unittest discover tests`）。实际结果：**16 passed in 0.03s**。测试用的 `SMALL_CORPUS` 是 4 句关于 fox/dog 的句子 × 20。

| 测试 | 验证的性质 |
|------|-----------|
| `TestInitialization.test_byte_alphabet_reserved` | 初始化后词表大小 = 256 + 2，且 id i 恰好对应字节 i |
| `test_specials_assigned_above_byte_block` | special token 的 id 都 ≥ 256 |
| `test_initialize_is_idempotent` | 重复 `initialize` 不会让词表变大 |
| `TestTraining.test_training_grows_vocab` | 训练后词表 > 258 且 ≤ 目标，至少学到 1 个合并 |
| `test_training_is_deterministic` | 两次训练的合并表（含顺序）完全一致——依赖平局规则 |
| `test_first_merge_is_a_frequent_pair` | 第一个合并的字节串确实出现在语料中（较弱的断言，并未检查它是最高频） |
| `TestRoundTrip.test_ascii_round_trip` | 新句子往返一致 |
| `test_unicode_round_trip` | 名为 Unicode，但文本 `"the fox says hello to the dog at 7pm"` 全是 ASCII，**并没有测到多字节字符**；讲义声称有 emoji 测试，实际不存在 |
| `test_empty_string_round_trip` | 空串编码为 `[]`，解码为空串 |
| `test_unseen_word_falls_back_to_bytes` | 训练中没见过的 `"zxqv"` 也能往返（退化为字节） |
| `TestCompression.test_encoded_length_at_most_byte_length` | id 数 ≤ 字节数（BPE 不会让序列变长） |
| `test_larger_vocab_compresses_more` | 词表 +60 的编码不长于词表 +8 的编码 |
| `TestSpecialTokens.test_special_tokens_get_dedicated_ids` | 两个 special 都有 id 且双向映射存在 |
| `test_special_token_emitted_only_when_allowed` | 关闭时不出现 EOT id；打开时出现且能往返（讲义提到的"含字面量 `<\|endoftext\|>` 的句子"测试） |
| `test_special_token_does_not_split_inside_word` | 普通文本即使打开 `allow_special` 也不会产生 EOT id |
| `TestPersistence.test_save_and_load_round_trip` | 保存/加载后 vocab、merges、specials 相等，编码结果一致（使用 `TemporaryDirectory`，自动清理） |

测试没有覆盖：语料包含 special 字面量时的撞 id（测验 Q9）、真正的多字节字符、平局规则的具体选择、目标词表达不到时的提前停止、编码与训练切分的一致性。
