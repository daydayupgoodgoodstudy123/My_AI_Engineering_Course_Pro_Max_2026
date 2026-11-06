# 测验 · 从零实现 BPE Tokenizer（BPE Tokenizer From Scratch）

> **阶段 19 · 综合项目 · 第 30 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Tokenizer 的契约 | 字符串 → 整数 id → 同样的字节；讲义："Get this layer wrong and every loss curve in the training run is measuring the wrong thing" |
| 2 | 字节字母表 | id 0–255 固定对应 256 个原始字节，任何 UTF-8 输入在合并之前就能被表示，永远不需要 unknown token |
| 3 | 词表布局 | `[0, 256)` 字节 → 紧接着是 special token（本节 256 = `<\|endoftext\|>`、257 = `<\|pad\|>`）→ 之后是学到的合并 |
| 4 | 预分词（pretokenize） | 先把语料切成块，合并只在块内发生，避免学出跨词短语；本节用 `\S+\|\s+`，空白串单独成块 |
| 5 | 训练循环 | 按"块 → 频次"计数相邻 pair（按块频次加权）→ 取最高频 pair（平局按 pair 元组排序取最小）→ 全语料替换 → 记录合并；最高频不足 2 次时提前停止 |
| 6 | 合并表即模型 | `merges` 的插入顺序就是 rank；编码时反复应用"当前序列里 rank 最小的合并"，直到无可应用的合并 |
| 7 | 解码 | 每个 id 展开为字节再拼接，最后 UTF-8 解码；单独解码半个多字节字符会得到 `�` |
| 8 | Special token | 只能由 `allow_special=True` 时的字面字符串产生；关闭时同样的字符串按普通字节编码；字节流本身不应产生它们 |
| 9 | 压缩曲线 | 词表越大、编码越短，但会饱和：演示语料上 300→24 个 id、400→17 个 id，目标 600 时词表只能长到 528 |
| 10 | 序列化 | `save/load` 用 JSON 保存 vocab、有序的 merges 列表与 specials；merges 的顺序必须保留 |

### 核心技能（能动手做到）

- [ ] 给定小语料与词频，手算前几步 BPE 合并（含"合并后计数变化"和平局规则）
- [ ] 手动执行编码过程，解释为什么 `"aaaa"` 编码成 `[aa, aa]` 而不是 `[aaa, a]`
- [ ] 读懂 `train / encode / decode / save / load` 的实现，并验证任意 UTF-8 输入（含 emoji、中文）的往返一致性
- [ ] 发现并修复"训练语料包含 special token 字面量时，合并结果与 special token 撞 id"的问题
- [ ] 改写预分词规则（例如 GPT-2 风格的"前导空格并入单词"），比较编码长度
- [ ] 画出词表大小与编码长度的压缩曲线，解释其饱和原因

---

## 二、基础自测（选择题）

**Q1.** 语料为 `"hug "*10 + "pug "*5 + "pun "*12 + "bun "*4 + "hugs "*5`，用本节 `train` 训练。初始 pair 计数中最高的几项是 `ug=20, pu=17, un=16, hu=15`。**前两次**合并依次是：

- A. `ug`，然后 `pu`
- B. `ug`，然后 `un`
- C. `ug`，然后 `hug`
- D. `pu`，然后 `ug`

**Q2.** 语料为 `"ab ba " * 3`，`target_vocab_size=259`（只允许 1 次合并）。`(a, b)` 与 `(b, a)` 各出现 3 次，本节代码会合并哪一对？

- A. `(b, a)`，因为它在语料中最后出现
- B. 两对都合并，因为计数相同
- C. 随机选一对，每次运行可能不同
- D. `(a, b)`：并列时对候选 pair 排序，`(97, 98) < (98, 97)`，取第一个

**Q3.** demo 中 `target=320`，打印 `final vocab size : 320`、`merges learned : 62`。这 320 个 id 的构成是：

- A. 256 个字节 + 2 个 special token + 62 个合并
- B. 320 个合并，字节不计入词表
- C. 256 个字节 + 64 个合并，special token 不占 id
- D. 258 个字节 + 62 个合并

**Q4.** 本节 `_pretokenize("read more than you write, write more\nthe  map")` 的结果，下列哪个说法正确？

- A. 标点被切开：`'write'` 与 `','` 是两个块（与讲义 "splits on whitespace and punctuation" 一致）
- B. 空格会并入后一个单词，得到 `' more'` 这样的块
- C. `'write,'` 是一个块；每段空白（`' '`、`'\n'`、两个空格 `'  '`）各自成为独立的块
- D. 换行符被丢弃，所以解码后无法还原原文

**Q5.** 用 `train(t, "aaa aaa aaa", 300)` 训练，学到的合并依次为 `(a,a)→258`、`(aa,a)→259`。那么 `encode(t, "aaaa")` 的结果是：

- A. `[258, 258]`
- B. `[259, 97]`
- C. `[97, 259]`
- D. `[97, 97, 97, 97]`

**Q6.** 按讲义建议把 demo 的目标词表改到 600，实际结果是：

- A. 词表达到 600，held-out 句子的 id 数随之降到约 10 个
- B. 程序报错，因为目标超过了语料中不同字节的数量
- C. 词表达到 600，但 id 数与 320 时完全相同
- D. 词表只长到 528（270 次合并）就停止——剩下的最高频 pair 不足 2 次；held-out 句子在目标 400 时已降到 17 个 id，之后不再变化

**Q7.** 用 demo 训练好的 tokenizer 执行 `encode(t, "doc one<|endoftext|>doc two")`（`allow_special` 取默认值）。下列说法正确的是：

- A. 输出中包含 id 256，因为 special token 总是优先匹配
- B. 输出不含 256；`<|endoftext|>` 被当作普通字节编码（它和 `one`、`doc` 同在块 `'one<|endoftext|>doc'` 中），解码后仍得到原字符串
- C. 抛出 `ValueError`，因为输入包含保留字符串
- D. `<|endoftext|>` 被静默删除

**Q8.** 编码 `"fox 🦊 says 你好"` 时，emoji 被编成 4 个字节 id `[240, 159, 166, 138]`。`decode(t, [240])` 的返回值是：

- A. 抛出 `UnicodeDecodeError`
- B. `'🦊'`
- C. `'�'`（U+FFFD 替换字符），因为单独一个首字节不是完整的 UTF-8 字符，`decode` 使用了 `errors="replace"`
- D. `'\xf0'`

---

## 三、动手 / 代码题

**Q9.** 讲义写道："The training loop never proposes those ids as merge targets because we keep them out of the pretokenized stream entirely." 请阅读代码：

```python
    def _add_token(self, token_bytes: bytes) -> int:
        if token_bytes in self.inv_vocab:
            return self.inv_vocab[token_bytes]
        ...

    def initialize(self, specials=DEFAULT_SPECIALS) -> None:
        ...
        for s in specials:
            token_id = len(self.vocab)
            self.vocab[token_id] = s.encode("utf-8")
            self.inv_vocab[s.encode("utf-8")] = token_id
            ...

def train(tokenizer, corpus, target_vocab_size, specials=DEFAULT_SPECIALS):
    tokenizer.initialize(specials)
    units = _build_initial_units(corpus)
    ...
        new_id = tokenizer._add_token(tokenizer.vocab[best[0]] + tokenizer.vocab[best[1]])
        tokenizer.merges[best] = new_id
```

1. 若训练语料是 `"hello <|endoftext|> world " * 50`，会发生什么？`encode(t, "see <|endoftext|> here", allow_special=False)` 的输出里会出现 id 256 吗？
2. 讲义的说法与代码是否一致？
3. 给出修复方案（至少两处改动）。

**Q10.** `_encode_chunk` 的实现如下（节选）：

```python
def _encode_chunk(tokenizer, chunk):
    symbols = _word_to_byte_ids(chunk)
    if len(symbols) < 2:
        return symbols
    ranked_merges = {pair: rank for rank, pair in enumerate(tokenizer.merges.keys())}
    while True:
        ...扫描所有相邻 pair，找 rank 最小的一个...
        symbols = symbols[:best_index] + [new_id] + symbols[best_index + 2:]
    return symbols
```

1. 指出两处性能问题，并估计它们的复杂度。
2. 写出优化版本（提示：rank 表只建一次；同一个块的编码结果可以缓存）。
3. 优化前后编码结果是否必须完全相同？如何验证？

**Q11.** 本节预分词把空白单独成块，于是 `" "`（id 32）在 held-out 句子 23 个 id 中占了 8 个。请写一个 GPT-2 风格的预分词正则（只用标准库 `re`）：缩写 `'ll` 等单独成块、可选前导空格并入单词/数字/标点、数字最多 3 位一组、连续空白中最后一个空格留给下一个词。替换 `_pretokenize` 后重新训练（目标 320），比较 held-out 句子 `"the fox is quick and the dog is lazy"` 的 id 数，并验证往返一致性。

**Q12.** 用 demo 语料测得的压缩曲线如下（held-out 句子共 36 字节）：

| `target_vocab_size` | 实际词表 | 合并数 | id 数 |
|---|---|---|---|
| 258 | 258 | 0 | 36 |
| 280 | 280 | 22 | 28 |
| 300 | 300 | 42 | 24 |
| 320 | 320 | 62 | 23 |
| 400 | 400 | 142 | 17 |
| 600 | 528 | 270 | 17 |
| 1000 | 528 | 270 | 17 |

1. 计算 320 与 400 时的压缩比（id 数 / 字节数）与平均每个 token 的字节数。
2. 解释为什么 400 之后 id 数不再下降、为什么 600 和 1000 的词表停在 528。
3. 这条曲线说明"在小语料上训练大词表"有什么问题？

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述 byte-level BPE 的训练与编码过程。为什么用 256 个字节而不是 Unicode 码点作为基础字母表？

**Q14.**（原理深挖）BPE 为什么需要预分词？GPT-2 为什么把前导空格并入单词（`" the"`）？不做预分词或预分词规则不同会带来什么后果？

**Q15.**（工程实践）special token 应该如何管理？如果用户输入里出现字面量 `<|endoftext|>`，tokenizer 默认应该怎么处理？为什么这和安全有关？

**Q16.**（场景设计）要在 100GB 文本上训练一个 10 万词表的 BPE，本节的实现会遇到什么瓶颈？你会怎样优化？

**Q17.**（追问型）编码时为什么要按"rank 最小优先"应用合并，而不是贪心地匹配最长的词表项？它能保证与训练时对同一单词的切分一致吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

关键是"每次合并后都要重新计数"（实测合并序列为 `ug→258, un→259, hug→260, pun→261`）：

- 第 1 步 `ug`（20）：来自 hug 10 + pug 5 + hugs 5。
- 合并后 `pug` 变成 `p ug`，`pu` 只剩 `pun` 中的 12 次；`un` 仍为 pun 12 + bun 4 = 16；`(h, ug)` 为 hug 10 + hugs 5 = 15。所以第 2 步是 `un`（16）。

A 用了过期的计数（17 是合并 `ug` 之前的值）；C 的 `hug`（15）是第 3 步；D 不是最高频。另外注意本节空格 `' '` 单独成块（出现 36 次），但单个字节构成的块里没有 pair，不参与合并。

### Q2 — 答案：D

```python
        max_count = max(pairs.values())
        candidates = sorted(p for p, c in pairs.items() if c == max_count)
        best = candidates[0]
```

候选 pair 是整数元组，按字典序排序：`(97, 98)`（a,b）排在 `(98, 97)`（b,a）前面。实测唯一的合并是 `b'ab' → 258`。这一规则让训练结果只取决于语料内容，与 dict 遍历顺序无关（测试 `test_training_is_deterministic` 验证两次训练的合并表完全一致）。A、C 错在以为与出现顺序或随机性有关；B 错，每步只合并一对。

### Q3 — 答案：A

`initialize` 先放入 256 个字节（id 0–255），再放入 2 个 special token（256、257），之后每次合并新增一个 id：`256 + 2 + 62 = 320`。`vocab_size` 就是 `len(self.vocab)`，包含 special token，所以 `target_vocab_size` 也包含它们。B、C、D 都没有正确计入这三部分。

### Q4 — 答案：C

正则 `\S+|\s+` 只区分"非空白串"与"空白串"。实测结果：`['read', ' ', 'more', ' ', 'than', ' ', 'you', ' ', 'write,', ' ', 'write', ' ', 'more', '\n', 'the', '  ', 'map']`。

- A 是讲义的说法（"splits the corpus on whitespace and punctuation boundaries"），代码并没有切标点，`'write,'` 与 `'write'` 是两个不同的训练单元。
- B 是 GPT-2 风格（见 Q11），本节不是。
- D 错：空白块被保留，解码时直接拼接即可还原原文。

### Q5 — 答案：A

编码过程：初始 `[97, 97, 97, 97]`。所有相邻 pair 都是 `(97, 97)`，rank 0，选**最左边**的一个合并 → `[258, 97, 97]`；此时 `(258, 97)` 的 rank 是 1，`(97, 97)` 的 rank 是 0，rank 0 优先 → `[258, 258]`；`(258, 258)` 不在合并表中，结束。实测输出 `[258, 258]`。B 是"最长匹配"思路的结果，但 BPE 编码按 rank 而不是长度；C、D 不符合流程。这也说明 BPE 编码不保证 token 数最少。

### Q6 — 答案：D

实测：`target=600` 与 `1000` 时 `vocab=528, merges=270`；held-out 句子 id 数从 `target=400` 开始就是 17。停止原因：

```python
        if pairs[best] < 2:
            break
```

演示语料只有 113 种不同的块（18 行 × 6 次重复），合并到一定程度后，每个高频单词都已经变成单个 token，剩下的 pair 只出现 1 次，继续合并没有压缩意义。讲义"change the target vocabulary size in the demo from 300 to 600"（代码实际是 320）并期望看到长度明显下降，在这份语料上 400 以后曲线已经平了。A、C 与实测不符；B 错，不会报错。

### Q7 — 答案：B

`allow_special=False` 时走 `_encode_pretokenized`，`'doc one<|endoftext|>doc two'` 被切成 `'doc'、' '、'one<|endoftext|>doc'、' '、'two'`，特殊字符串只是一串普通字节。测试 `test_special_token_emitted_only_when_allowed` 正是断言这种情况下不出现 EOT id。打开 `allow_special=True` 时，demo 实测输出 `[276, 99, 32, 270, 101, 256, 276, 99, 32, 116, 119, 111]`，其中 256 就是 `<|endoftext|>`。A 只在 `allow_special=True` 时成立；C、D 都不是本节的行为（tiktoken 默认会对这种输入报错，那是另一种设计，见 Q15）。

### Q8 — 答案：C

🦊 的 UTF-8 编码是 `F0 9F A6 8A`（240、159、166、138），演示语料里没有它，所以退化为 4 个单字节 token。`b"\xf0".decode("utf-8", errors="replace")` 得到 `'�'`；4 个字节一起解码才是 `'🦊'`（已实测）。整句往返一致：`decode(encode(s)) == s` 为 True。A 是没有 `errors="replace"` 时的行为；D 是 latin-1 解码的结果。流式输出时必须缓冲到完整字符再显示。

### Q9 — 参考答案

1. 该语料中 `<|endoftext|>` 前后都有空格，`_pretokenize` 把它切成一个独立的块，出现 50 次。训练会一步步把它的 13 个字节合并起来；当某次合并的结果恰好等于 `b"<|endoftext|>"` 时，`_add_token` 发现 `inv_vocab` 里已经有这串字节（initialize 时放进去的 special token），于是**直接返回 256**，`merges[(x, y)] = 256`。实测：合并表中出现 `(b'<|endoftext|>', 256)`；共 20 次合并但词表只增加到 277（有一次合并没有产生新 id）；`encode(t, "see <|endoftext|> here", allow_special=False)` 输出 `[115, 101, 101, 32, 256, 32, ...]`——**关闭 special 时仍然产生了 EOT id**，违背了讲义自己的契约。
2. 不一致。代码并没有把 special token 从训练语料中移除，而且 `_add_token` 对 special token 的字节也做了"去重"。只是演示语料恰好不包含这些字符串，问题没有暴露。真实预训练语料通常就是用 `<|endoftext|>` 拼接文档的，所以这不是假想问题。
3. 修复：
   - 训练前按 special token 切分语料，**丢弃** special 片段，只对普通文本预分词：`parts = re.split("(" + "|".join(map(re.escape, specials)) + ")", corpus)`，过滤掉 special 后再 `_build_initial_units`。
   - special token 不放进 `inv_vocab`（或单独维护），使 `_add_token` 永远不会把合并映射到 special id；即使合并出相同字节，也分配一个新的普通 id。
   - 可选：编码时 `allow_special=False` 若遇到 special 字面量，可以选择报错（tiktoken 的默认做法）而不是静默编码成字节。
   - 加一个回归测试：语料含独立的 `<|endoftext|>`，断言 `allow_special=False` 的输出不含任何 special id。

### Q10 — 参考答案

1. 两处问题：
   - `ranked_merges` 每编码一个块就重建一次，代价 O(M)（M 为合并数）。一段文本有成千上万个块，就要重建成千上万次。
   - 每次只合并一处，然后从头扫描整个序列：长度为 L 的块最多合并 L−1 次，每次扫描 O(L)，加上列表切片拼接 O(L)，单块 O(L²)。对短单词无所谓，对长的无空白串（URL、base64、代码压缩行）会很慢。
2. 优化版本：

```python
from functools import lru_cache

def make_encoder(tokenizer):
    ranks = {pair: r for r, pair in enumerate(tokenizer.merges)}   # 只建一次

    @lru_cache(maxsize=100_000)                                   # 相同块直接复用
    def encode_chunk(chunk: str) -> tuple[int, ...]:
        symbols = list(chunk.encode("utf-8"))
        while len(symbols) >= 2:
            best = min(
                ((ranks.get((a, b), float("inf")), i) for i, (a, b) in enumerate(zip(symbols, symbols[1:]))),
                default=(float("inf"), -1),
            )
            rank, i = best
            if rank == float("inf"):
                break
            symbols[i:i + 2] = [tokenizer.merges[(symbols[i], symbols[i + 1])]]
        return tuple(symbols)

    def encode_fast(text: str) -> list[int]:
        out: list[int] = []
        for chunk in _pretokenize(text):
            out.extend(encode_chunk(chunk))
        return out
    return encode_fast
```

   `min` 对 `(rank, i)` 元组比较：rank 相同取 i 最小，与原实现"严格小于才替换"（即最左优先）一致。生产实现（如 tiktoken）还会用堆或链表把每次合并降到 O(log L)。注意 tokenizer 训练后若再修改 merges，需要重建 encoder（缓存失效问题）。
3. 必须完全相同——这是 tokenizer 的契约，任何优化都不能改变输出。验证方法：在演示语料、测试句子、随机生成的 Unicode 字符串上，断言 `encode_fast(s) == encode(t, s)`；把它写成属性测试（property-based test）。我们用目标 600 训练的 tokenizer，在整段演示语料和 2000 条含 emoji/中文的随机字符串上验证了优化版与原版输出完全一致。演示语料整段编码原本只要约 0.02 秒，小语料上看不出差别，大语料上缓存命中率很高（自然语言中高频词占绝大多数）。

### Q11 — 参考答案

```python
import re

GPT2_LIKE = re.compile(r"""'(?:[sdmt]|ll|ve|re)| ?[^\W\d_]+| ?\d{1,3}| ?[^\s\w]+|\s+(?!\S)|\s+""")
```

- `'(?:[sdmt]|ll|ve|re)`：英文缩写后缀单独成块；
- ` ?[^\W\d_]+`：可选一个前导空格 + 字母串（`[^\W\d_]` 即"是单词字符但不是数字和下划线"，标准库 `re` 不支持 `\p{L}`，用它近似"字母"，对中文也有效）；
- ` ?\d{1,3}`：数字每 3 位一组；
- ` ?[^\s\w]+`：标点等其他符号；
- `\s+(?!\S)`：连续空白中，留下最后一个空格不吃，让它作为下一个词的前导空格；
- `\s+`：兜底（结尾空白）。

实测 `"I'll read 12345 more, then write!  OK"` 切分为 `['I', "'ll", ' read', ' 123', '45', ' more', ',', ' then', ' write', '!', ' ', ' OK']`，原实现为 `["I'll", ' ', 'read', ' ', '12345', ' ', 'more,', ' ', 'then', ' ', 'write!', '  ', 'OK']`。

把 `main._pretokenize` 替换为 `GPT2_LIKE.findall` 后重新训练到 320（训练与编码都会用到 `_pretokenize`，必须同时生效）：held-out 句子从 **23 个 id 降到 18 个**，切分为 `['the', ' f', 'o', 'x', ' is', ' q', 'u', 'ic', 'k', ' a', 'nd', ' the', ' do', 'g', ' is', ' la', 'z', 'y']`，空格不再单独占 token；往返一致性仍为 True（这个正则能覆盖所有字符，`findall` 结果拼回去等于原串）。注意：正则替换后，`'the'`（句首）与 `' the'` 是两个不同的 token，这正是 GPT-2 词表里大量"带空格版本"词条的来源。

### Q12 — 参考答案

1. 320：`23 / 36 ≈ 0.639`，平均每 token `36 / 23 ≈ 1.57` 字节；400：`17 / 36 ≈ 0.472`，平均每 token `36 / 17 ≈ 2.12` 字节。
2. id 不再下降：实测 400 时切分已经是 `['the', ' ', 'fox', ' ', 'is', ' ', 'quick', ' ', 'and', ' ', 'the', ' ', 'dog', ' ', 'is', ' ', 'lazy']`——9 个单词各自成为 1 个 token（它们在演示语料中各出现 12 次以上），再加 8 个单独成块的空格，17 就是这种预分词规则下的**下限**：合并不能跨块，空格永远无法与单词合并。之后新增的合并只服务于语料里的其他词，对这句话没有帮助。停在 528：所有剩余 pair 的最高计数 < 2，`train` 主动 `break`，`target` 再大也没有意义。
3. 小语料上训练大词表会**过拟合语料**：后期合并学到的是只在训练文本中出现的整词甚至整句片段，对新文本没有压缩收益，却占用 embedding 参数（每个 id 一行 embedding）；这些 token 在训练中出现次数极少，embedding 学不好（相关现象常被称为 "glitch token"）。实际做法是用大规模、与目标分布一致的语料训练 tokenizer，并在留出集上测压缩率来决定词表大小。

### Q13 — 参考回答要点

- **训练**：语料预分词 → 每块转成字节 id 序列，统计块频次 → 循环：统计所有相邻 pair（按块频次加权）→ 选最高频（定义好平局规则）→ 在所有块中把该 pair 替换为新 id → 记录 `(a, b) → new_id` 与新 id 的字节串 → 直到达到目标词表大小或没有值得合并的 pair。
- **编码**：预分词 → 每块从字节开始 → 反复应用当前序列中 rank 最小的合并 → 拼接所有块的 id。special token 在预分词之前单独处理。
- **解码**：id → 字节串拼接 → UTF-8 解码。
- **为什么用字节**：UTF-8 下任何字符都是 1–4 个字节，256 个基础符号覆盖一切输入，**没有 OOV**；Unicode 码点有十几万个，作为基础字母表要么词表巨大，要么仍会遇到未见字符。代价是罕见字符（如未见过的汉字、emoji）会被拆成多个字节 token，单个 token 可能不是完整字符。
- 加分点：说明合并表的顺序就是模型的一部分，训练与推理必须共享同一份合并表（讲义："That sharing is the contract"）。

### Q14 — 参考回答要点

- **为什么要预分词**：讲义："Without that split the BPE merge step would happily learn merges that cross word boundaries and the vocabulary fills up with whole common phrases." 跨词 token（如 `" sat on the "`）泛化差、浪费词表，还会让同一个词在不同上下文中切法不同。
- **前导空格**：GPT-2 把空格并入后面的单词，使 `" the"` 成为一个 token，不需要为空格单独花一个 token（Q11 实测 23 → 18）；代价是句首的 `"the"` 与句中的 `" the"` 是两个不同 id，模型需要分别学习。
- **其他规则**：缩写单独切、数字按 1–3 位分组（便于算术、避免奇怪的数字 token）、标点与字母分开、代码中保留缩进空白。
- **规则不同的后果**：词表内容、压缩率、多语言表现都会变；最关键的是**训练与推理必须使用同一套规则**，否则编码结果与训练分布不一致。
- 常见误区：以为预分词只是为了加速训练——它首先是为了得到"好"的词表。

### Q15 — 参考回答要点

- **管理方式**：special token 占用保留 id（本节放在字节块之后）；永远不由普通字节流产生；训练语料中的 special 字面量要先移除（Q9）；编码时只有显式允许才把字面量映射到保留 id。
- **默认行为**：本节默认 `allow_special=False`，把字面量当普通字节编码；tiktoken 的默认行为是对出现在输入中的 special 字面量**直接报错**，要求调用方明确选择 `allowed_special` 或 `disallowed_special=()`。两种都比"静默映射为 special id"安全。
- **为什么和安全有关**：如果用户输入里的 `<|endoftext|>`、对话角色标记（如 `<|im_start|>system`）被映射为真正的控制 token，用户就能伪造文档边界或系统消息，属于 prompt injection / 角色伪造。所以聊天模板中的控制 token 只能由服务端模板代码插入，用户文本一律按普通字节编码。
- 加分点：`<|pad|>` 在训练时要被 loss mask 屏蔽（讲义："The loss mask hides it during training"），否则模型会学习预测 padding。

### Q16 — 参考回答要点

- **瓶颈**：
  - 每次合并都对所有不同块重新统计全部 pair，并重建整个 `units` 字典，复杂度约 O(合并数 × 语料符号数)。我们在 10 万词（5000 个不同词）的合成语料上实测：300 次合并约 2.9 秒，1000 次约 8.8 秒；讲义"一百万词、一万词表几秒完成"的估计偏乐观。
  - 预分词与字节转换都是纯 Python 单线程。
  - 100GB 文本无法一次读入内存。
- **优化**：
  - 先流式扫描语料，只保留"块 → 频次"表（不同块的数量远小于总词数），可多进程分片统计后归约（讲义："count pairs per word in parallel and reduce"）；
  - **增量更新 pair 计数**：维护 `pair → 计数` 与 `pair → 包含它的块` 的索引，合并时只更新受影响块的相邻 pair，用堆取最大值；
  - 过滤只出现一两次的超长块，或对语料采样；
  - 直接使用 Rust 实现的 Hugging Face `tokenizers` 或 SentencePiece。
- 加分点：训练数据配比决定词表偏向（中文、代码比例），要在留出集上按语言统计压缩率。

### Q17 — 参考回答要点

- **为什么按 rank**：BPE 的合并表是一个有先后顺序的"重写规则"序列；训练时先学到的合并在语料里先被应用。编码时按 rank 应用，才能复现训练时的处理顺序，保证确定性；讲义："The ordering by rank is the property that makes encoding deterministic and matches the training behavior on the same input."
- **最长匹配的问题**：贪心最长匹配是 WordPiece 的编码方式；对 BPE 词表用最长匹配，会产生训练中从未出现过的切分（例如 Q5 的 `"aaaa"`：最长匹配得到 `[aaa, a]`，BPE 得到 `[aa, aa]`），模型对这些切分的统计是陌生的。
- **一致性**：对训练语料中出现过的块，按 rank 逐次应用合并（每次合并最左边一处）与训练时"每轮把该 pair 的全部不重叠出现从左到右替换"在绝大多数情况下给出相同结果；特殊的重叠情形（如连续相同字符）也都按"从左到右不重叠"处理。工程上应以"训练语料重新编码等于训练时的最终切分"作为测试来确认——我们对演示语料（目标 600）的 113 种块逐一比较，0 处不一致。
- **平局**：同一 rank 的 pair 在序列中出现多次时，本节取最左边的一处（`rank < best_rank` 严格小于才更新）。
- 加分点：Unigram/SentencePiece 的编码是基于概率的 Viterbi 解码，可以做 subword regularization，与 BPE 的确定性规则不同。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 01 Tokenizers: BPE, WordPiece, SentencePiece](../../../10-llms-from-scratch/01-tokenizers/docs/zh.md)：三种子词算法的原理与取舍。
- [阶段 10 · 02 从头开始构建 Tokenizer](../../../10-llms-from-scratch/02-building-a-tokenizer/docs/zh.md)：预分词、special token、序列化等工程细节。
- [阶段 05 · 19 子词 Tokenization](../../../05-nlp-foundations-to-advanced/19-subword-tokenization/docs/zh.md)：NLP 视角下的 BPE/WordPiece/Unigram。
- [阶段 07 · 07 GPT 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：tokenizer 的输出就是 GPT 的输入。

### 本节被哪些后续内容用到
- [阶段 19 · 31 使用滑动窗口构建分词后的数据集](../../31-tokenized-dataset-sliding-window/docs/zh.md)：把本节的 tokenizer 当作黑盒，构建训练样本。
- [阶段 19 · 32 Token 与位置 Embeddings](../../32-token-positional-embeddings/docs/zh.md)：词表大小决定 embedding 矩阵的行数。
- [阶段 19 · 35 组装 GPT 模型](../../35-gpt-model-assembly/docs/zh.md)：输出层大小等于词表大小。
- [阶段 19 · 43 HDF5 格式的分词语料](../../43-hdf5-tokenized-corpus/docs/zh.md)：大规模语料的离线分词与存储。
- [阶段 10 · 03 用于预训练的数据管道](../../../10-llms-from-scratch/03-data-pipelines/docs/zh.md)：tokenizer 在预训练数据管道中的位置。

### 延伸关键词
`byte-level BPE` · `merge rank` · `pre-tokenization regex` · `tiktoken` · `cl100k_base` · `special tokens / allowed_special` · `prompt injection via control tokens` · `compression ratio` · `glitch token` · `Hugging Face tokenizers` · `SentencePiece` · `Unigram`
