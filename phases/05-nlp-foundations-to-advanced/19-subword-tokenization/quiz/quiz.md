# 测验 · 子词 Tokenization——BPE、WordPiece、Unigram、SentencePiece（Subword Tokenization — BPE, WordPiece, Unigram, SentencePiece）

> **阶段 05 · NLP 从基础到进阶 · 第 19 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过 `main.py` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要子词 | 词级词表遇到新词只能输出 `[UNK]`，字符级序列太长；子词让常见词保持整 token、罕见词拆成已知片段 |
| 2 | BPE 训练 | 从字符起步，统计所有相邻对（按词频加权），把最频繁的一对合并成新 token，重复直到达到目标词表大小 |
| 3 | merge 列表有序 | 推理时必须**按训练顺序**依次应用 merge；顺序变了，切分结果就变了 |
| 4 | `</w>` 词尾标记 | 让"词尾的 low"与"词首的 low"成为不同符号，保留位置信息 |
| 5 | Byte-level BPE | 以 256 个字节为基础符号，任何输入都能编码，永不出现 `[UNK]`；GPT-2 词表 = 256 字节 + 50,000 merges + 1 个特殊 token = 50,257 |
| 6 | WordPiece | 也是自底向上合并，但选"最能提升训练语料似然"的对，而不是最频繁的对；BERT 系使用 |
| 7 | Unigram | 方向相反：从超大候选词表出发，每次剪掉"删除后对语料对数似然损失最小"的 token；推理时可以采样多种切分（subword regularization） |
| 8 | SentencePiece vs tiktoken | SentencePiece 是**训练**库（BPE/Unigram，直接吃原始文本，空格编码为 `▁`）；tiktoken 只做**编码**，不能训练 |
| 9 | 生产坑 | tokenizer drift（训练和部署词表不一致）、前导空格、多语言 token 膨胀、emoji 拆成多个 token |
| 10 | 词表大小是规模决策 | 经验值：<1B 参数约 32k，1–10B 约 50–100k，多语言/前沿模型 200k+ |

### 核心技能（能动手做到）

- [ ] 不依赖任何库，从零实现 BPE 训练（`pair_counts` + `merge_pair` 循环）并打印前 10 个 merge
- [ ] 给定一份 merge 列表，手工推演任意单词的 `encode_bpe` 结果，并解释 merge 顺序如何影响输出
- [ ] 能区分"当前训练语料中出现的符号数"和"真正的 tokenizer 词表大小（基础符号 + merges）"
- [ ] 把 BPE 的选对规则改成 WordPiece 风格的打分（`count(ab) / (count(a)·count(b))`），对比两者前几个 merge 的差异
- [ ] 用 merge rank（优先级）重写编码器，并用随机单词验证与朴素版本输出完全一致
- [ ] 能为一个具体场景（单语/多语、模型规模、是否兼容 OpenAI 词表）选出算法、库、词表大小，并给出验证指标（tokens-per-word、压缩率、round-trip 解码一致）

---

## 二、基础自测（选择题）

**Q1.** 关于 BPE 训练中"一次 merge"的描述，正确的是：

- A. 统计所有单词的出现次数，把最常见的整词直接加入词表
- B. 统计所有相邻符号对的出现次数（按单词频率加权），把次数最多的一对合并为一个新符号
- C. 统计所有字符的出现次数，把最罕见的字符删除
- D. 计算每个候选 token 的 unigram 概率，删除概率最低的 token

**Q2.** GPT-2 的词表大小是 50,257。它的构成是：

- A. 50,257 个英文单词
- B. 256 个 Unicode 字符 + 50,001 个 merges
- C. 256 个字节 + 50,000 个 merges + 1 个特殊 token
- D. 50,000 个 WordPiece 子词 + 257 个特殊 token

**Q3.** 关于 Unigram tokenizer，下列说法**错误**的是：

- A. 训练从一个很大的候选词表开始，逐步剪枝到目标大小
- B. 剪枝的标准是：删掉这个 token 后，语料对数似然下降得最少
- C. 推理时同一个词只可能有唯一一种切分，因此无法用于数据增强
- D. T5、ALBERT、XLNet 等模型使用 Unigram

**Q4.** 某语料中 `q` 几乎只出现在 `qu` 里，而 `e`、`s` 到处都是、`es` 也很常见。BPE 和 WordPiece 在第一步最可能分别选择：

- A. BPE 选 `(e, s)`，WordPiece 选 `(q, u)`
- B. 两者都选 `(e, s)`
- C. 两者都选 `(q, u)`
- D. BPE 选 `(q, u)`，WordPiece 选 `(e, s)`

**Q5.** 下列关于 SentencePiece 与 tiktoken 的说法，正确的是：

- A. tiktoken 可以在你的私有语料上训练一个新的 BPE 词表
- B. SentencePiece 必须先用空格做 pre-tokenization 才能训练
- C. SentencePiece 直接在原始 Unicode 文本上训练 BPE 或 Unigram，把空格编码成 `▁`
- D. 两者都只支持 WordPiece 算法

**Q6.** BPE 训练时在每个词末尾加 `</w>`，主要目的是：

- A. 让词表大小翻倍
- B. 区分"出现在词尾的子串"和"出现在词中/词首的同一子串"，使解码时能恢复词边界
- C. 防止 merge 跨越两个单词
- D. 标记句子结束，供语言模型停止生成

**Q7.** 线上服务突然输出乱码，排查发现训练时用的是 tokenizer A，部署镜像里装的是一个"看起来差不多"的 tokenizer B。讲义推荐的预防手段是：

- A. 把词表大小调大
- B. 在 CI 中校验 `tokenizer.json` 的哈希，确保与训练时冻结的版本一致
- C. 改用字符级 tokenizer
- D. 部署前把模型重新训练一遍

---

## 三、动手 / 代码题

**Q8.** 下面是 `main.py` 中的 `encode_bpe`。请写出三行 `print` 的输出，并解释第二、三行为什么不同。

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

print(encode_bpe("lower", [("l", "o"), ("lo", "w"), ("e", "r"), ("er", "</w>")]))
print(encode_bpe("low",   [("l", "o"), ("lo", "w")]))
print(encode_bpe("low",   [("lo", "w"), ("l", "o")]))
```

**Q9.** 运行 `main.py`，30 次 merge 时打印 `vocab size: 55`，150 次时打印 `vocab size: 77`。如果把 `num_merges` 改成 1000，实际只执行了 183 次 merge，打印的 `vocab size` 反而变成 **52**。

1. 为什么 merge 越多，这里的"vocab size"可能**变小**？52 这个数字恰好等于什么？
2. 这个数字是不是真实 tokenizer 的词表大小？如果不是，正确的词表大小（30 次 merge 时）应该是多少？（已知初始基础符号为 26 个字母 + `</w>` = 27 个）

```python
    final_tokens = set()
    for symbols in vocab:
        final_tokens.update(symbols)
    return merges, sorted(final_tokens)
```

**Q10.** 讲义说 WordPiece "选让训练语料似然最大的对"。常见的实现打分为 `score(a,b) = count(ab) / (count(a) · count(b))`。请复用 `main.py` 里的 `word_counts`、`init_vocab`、`pair_counts`、`merge_pair`，写一个 `train_wordpiece_style(text, num_merges)`，只替换"选哪一对"的规则。用 `main.py` 的语料跑 5 次 merge，前几个 merge 和 BPE 的 `('e','</w>')`、`('s','</w>')` 有什么不同？为什么？

**Q11.** `encode_bpe` 对每个 merge 都扫描一遍整个符号列表，并且每次合并都用切片重建列表。

1. 设单词长度为 n、merge 数为 M，它的最坏时间复杂度大约是多少？
2. 讲义提到生产实现用"merge rank 查找"。请写一个 `encode_bpe_fast(word, merges)`：先建 `ranks = {pair: 序号}`，然后反复找当前相邻对中 rank 最小的一对合并，直到没有可合并的对。它和朴素版本的输出会一致吗？为什么？

---

## 四、面试高频题

**Q12.**（基础必考）请对比 BPE、WordPiece、Unigram 三种子词算法：训练方向、选择标准、推理方式、代表模型分别是什么？

**Q13.**（原理深挖）Byte-level BPE 为什么能保证"永远没有 `[UNK]`"？这样做有什么代价？SentencePiece 怎么实现类似的效果？

**Q14.**（工程实践）你负责把一个微调好的开源模型部署上线。和 tokenizer 相关的哪些问题最容易"静默出错"？你会在 CI/上线流程中加哪些检查？

**Q15.**（场景设计）公司要从零预训练一个约 3B 参数、覆盖中英日阿四种语言的模型。请给出 tokenizer 方案：算法、训练库、词表大小、覆盖率设置，以及你会用什么指标验证这个 tokenizer 合格。

**Q16.**（追问型）同一段客服对话，翻译成日语后调用 API 的费用明显比英语高，为什么？如何在上线前准确估算 token 预算？

---

## 五、参考答案与解析

### Q1 — 答案：B

BPE 的核心循环就是 `pair_counts → most_common(1) → merge_pair`：统计相邻符号对（每个词的频率作为权重）、合并最频繁的一对，并把这次 merge 记录到有序列表中。A 是词级词表的做法；C 不是任何一种标准算法；D 描述的是 Unigram 的剪枝。

### Q2 — 答案：C

Byte-level BPE 以 256 个字节为基础符号，GPT-2 在其上学了 50,000 次 merge，再加 1 个特殊 token（`<|endoftext|>`），共 50,257。B 的错误在于基础符号是**字节**而不是 Unicode 字符——这正是"任何输入都可编码"的来源。

### Q3 — 答案：C

Unigram 是**概率模型**，一个词可以有多种切分，各有概率；推理时既可以取最可能的切分，也可以按概率**采样**不同切分，这就是 subword regularization，可用作数据增强。A、B、D 都与讲义一致。

### Q4 — 答案：A

BPE 只看原始频次，`(e, s)` 出现得多就先合并。WordPiece 的打分 `count(ab)/(count(a)·count(b))` 会"惩罚"本身就很常见的子单元：`e`、`s` 各自频次很高，分母大，得分反而低；`q` 几乎只和 `u` 一起出现，`count(qu)` 接近 `count(q)`，得分高。直觉：WordPiece 偏好"组合在一起比各自独立出现更有信息量"的对。第三部分 Q10 会用代码验证这一点。

### Q5 — 答案：C

SentencePiece 不需要 pre-tokenization，把空格当普通字符并编码为 `▁`，因此能直接处理中文、日文这类没有空格分词的语言。A 错：tiktoken 只做编码，不训练；B 错：恰好相反；D 错：SentencePiece 支持 BPE 和 Unigram，tiktoken 是 BPE。

### Q6 — 答案：B

`</w>` 让 "low" 作为完整词（`low</w>`）和 "lower" 的前缀（`low`）成为不同符号；解码时看到 `</w>` 就知道这里是词边界。C 不对：本代码按词分别训练，merge 本来就不会跨词（每个词是独立的元组）。D 混淆了句子级的 EOS 特殊 token。

### Q7 — 答案：B

Tokenizer drift 的危险在于**不报错**：同一个字符串在 A、B 下得到不同的 token ID，模型看到的是"另一种语言"，输出变成垃圾。讲义建议在 CI 中校验 `tokenizer.json` 哈希。A、C、D 都没有解决"版本不一致"这个根因。

### Q8 — 参考答案

输出：

```
['low', 'er</w>']
['low', '</w>']
['lo', 'w', '</w>']
```

推演：
- 第一行：`l o w e r </w>` → 应用 `(l,o)` 得 `lo w e r </w>` → `(lo,w)` 得 `low e r </w>` → `(e,r)` 得 `low er </w>` → `(er,</w>)` 得 `low er</w>`。
- 第二行：先 `(l,o)` 得到 `lo`，再 `(lo,w)` 才有东西可合并，得 `low`。
- 第三行：先尝试 `(lo,w)`，此时还没有 `lo` 这个符号，什么也不发生；再 `(l,o)` 得到 `lo`，但循环已经结束，`(lo,w)` 不会再被应用。

结论：**merge 列表是有序的，推理必须严格按训练顺序应用**。训练时 `(lo,w)` 一定排在 `(l,o)` 之后（必须先有 `lo` 才能统计到 `(lo,w)` 这一对），所以正常训练出的列表不会出现第三行的情况；但如果有人把 merges 存成 `set` 或排序后再加载，就会悄悄得到错误切分。

### Q9 — 参考答案

1. `final_tokens` 收集的是**训练语料在最终切分状态下用到的符号**，而不是"学到过的所有 token"。每次 merge 会产生新符号，但被合并掉的旧符号如果在语料中不再单独出现，就会从这个集合里消失。merge 足够多时，每个训练词都被合并成了一个整体符号（如 `the</w>`、`tokenization</w>`），集合大小就等于**语料中不同单词的个数**——本语料正好 52 个不同的词，所以是 52。此时再也没有相邻对可合并，`pair_counts` 返回空，循环在第 183 次后 `break`。
2. 不是。真实 BPE tokenizer 的词表 = 基础符号 + 每次 merge 新增的符号，单调增长、不会删除（推理时需要靠中间 token 去拼新词）。30 次 merge 时真实词表大小 = 27 + 30 = **57**；150 次时为 27 + 150 = **177**。可以这样改：

```python
vocab_size = len(set(base_symbols) | {a + b for a, b in merges})
```

这里 `base_symbols` 是 `init_vocab` 之后所有出现过的符号。这是本代码为了演示而做的简化，读输出时要注意它的含义。

### Q10 — 参考答案

```python
from collections import Counter
from main import word_counts, init_vocab, pair_counts, merge_pair

def wordpiece_scores(vocab):
    pairs = pair_counts(vocab)
    unit = Counter()
    for symbols, freq in vocab.items():
        for s in symbols:
            unit[s] += freq
    return {p: c / (unit[p[0]] * unit[p[1]]) for p, c in pairs.items()}

def train_wordpiece_style(text, num_merges):
    vocab = init_vocab(word_counts(text))
    merges = []
    for _ in range(num_merges):
        scores = wordpiece_scores(vocab)
        if not scores:
            break
        best = max(scores, key=scores.get)
        merges.append(best)
        vocab = merge_pair(vocab, best)
    return merges
```

在 `main.py` 的语料上，前 5 个 merge 为 `('q','u')`、`('j','u')`、`('ju','m')`、`('jum','p')`、`('z','y')`，而 BPE 的前几个是 `('e','</w>')`、`('s','</w>')`、`('n','</w>')`。

原因：`q`、`j`、`z` 都是低频字母，而且几乎总和固定的邻居一起出现，`count(ab)` 与 `count(a)·count(b)` 的比值很高；`e`、`</w>` 虽然 `e</w>` 出现 15 次，但 `e` 和 `</w>` 各自频次极高，分母巨大，得分很低。这说明两种标准学到的 merge 顺序截然不同。注意：真正的 BERT WordPiece 还使用 `##` 前缀标记"非词首"片段，推理时是"最长匹配优先"，这里只演示训练打分的差异。

### Q11 — 参考答案

1. 外层循环 M 次；每次 `while` 扫描 O(n) 个位置；每次命中合并时切片重建列表又是 O(n)。最坏约 **O(M·n²)**，通常写作 O(M·n)（忽略切片）。对于词表 5 万、单词很长或不按词切分的输入，这个代价很可观——而大多数 merge 根本与当前单词无关，扫描是浪费的。
2. 参考实现：

```python
def encode_bpe_fast(word, merges):
    ranks = {pair: r for r, pair in enumerate(merges)}
    symbols = list(word) + ["</w>"]
    while len(symbols) > 1:
        pairs = [(ranks.get((a, b), float("inf")), i)
                 for i, (a, b) in enumerate(zip(symbols, symbols[1:]))]
        best_rank, i = min(pairs)
        if best_rank == float("inf"):
            break
        symbols = symbols[:i] + [symbols[i] + symbols[i + 1]] + symbols[i + 2:]
    return symbols
```

复杂度只与单词长度有关（每轮 O(n)，最多 n 轮），与 M 无关。

输出与朴素版本一致（可以用随机字符串对比验证）。原因：朴素版本按 rank 从小到大应用 merge；而一次 merge 产生的新符号 `ab` 只会参与 rank **更大**的 merge（因为 `ab` 是在第 k 次 merge 才出现的，涉及它的 merge 一定在 k 之后才可能被统计到）。所以"每次挑当前 rank 最小的对"与"按顺序逐个应用"得到相同结果。GPT-2/tiktoken 一类实现就是这个思路，再配合优先队列与缓存进一步加速。

### Q12 — 参考回答要点

| | BPE | WordPiece | Unigram |
|---|---|---|---|
| 训练方向 | 自底向上：从字符/字节开始合并 | 自底向上合并 | 自顶向下：从大候选集开始剪枝 |
| 选择标准 | 相邻对**频次**最高 | 合并后训练语料**似然**提升最大（常见打分 `count(ab)/(count(a)count(b))`） | 删除后语料**对数似然**损失最小 |
| 推理 | 按 merge 顺序确定性应用 | 确定性（贪心最长匹配） | 概率模型，可取最优切分或采样 |
| 代表模型（讲义） | GPT-2/3/4、Llama、Qwen2、Mistral | BERT、DistilBERT、ELECTRA | T5、mBART、ALBERT、XLNet |

- 加分点：说出 Unigram 的 subword regularization 能做数据增强；说出"算法"和"库"是两个维度——SentencePiece 是库，可训练 BPE 或 Unigram。
- 常见误区：把 SentencePiece 当成一种算法；认为 WordPiece 和 BPE 唯一的区别是 `##` 前缀。

### Q13 — 参考回答要点

- **原理**：任何文本最终都是 UTF-8 字节序列，而 256 个字节值全部是基础符号，最坏情况下每个字节单独成一个 token，所以任何输入都能编码，不存在 OOV。
- **代价**：
  - 训练数据中少见的字符（罕见汉字、阿拉伯文、emoji）会被拆成多个字节 token：一个 CJK 字符 UTF-8 占 3 字节，一个组合 emoji 可能占十几个字节，讲义提到单个 emoji 可能占 5 个 token。序列变长 → 更贵、更占上下文。
  - 单个 token 可能只是半个字符的字节，流式输出时要缓存到构成完整 UTF-8 字符后再显示。
- **SentencePiece 的做法**：在字符级词表之上开启 `byte_fallback`，未覆盖的字符退回到字节 token；`character_coverage` 控制多大比例的字符要被直接收进词表，其余映射为 `<unk>` 或走 byte fallback。
- 加分点：能说出 GPT-2 = 256 + 50,000 + 1；能把"无 UNK"与"多语言 token 膨胀"联系起来。

### Q14 — 参考回答要点

1. **Tokenizer drift**：模型和 tokenizer 版本不一致，ID 错位但不报错。→ 在 CI 中冻结并校验 `tokenizer.json` 的哈希；模型和 tokenizer 一起版本化、一起发布。
2. **空格与特殊 token**：BPE 中 `"hello"` 与 `" hello"` 是不同 token；`add_special_tokens`、`add_prefix_space` 的默认值在不同库/版本间可能不同。→ 讲义建议**显式**指定这些参数，不依赖默认值。
3. **Round-trip 测试**：准备一组覆盖中英文、数字、代码、emoji、特殊空白的样本，断言 `decode(encode(x)) == x`，并与训练环境产出的 token ID 做逐条比对（golden file）。
4. **长度/成本监控**：上线后监控 tokens-per-request 分布，突变往往意味着 tokenizer 或预处理变了。
- 常见误区：只比较词表大小，或只看模型权重的 hash，不看 tokenizer。

### Q15 — 参考回答要点

- **算法 + 库**：讲义 2026 选型表建议多语言模型用 SentencePiece（Unigram），`character_coverage=0.9995`；也可以选 SentencePiece BPE 并开启 `byte_fallback`，保证零 `<unk>`。HF Tokenizers 可以一个库同时完成训练与服务。
- **词表大小**：3B 参数落在讲义 "1–10B → 50–100k" 区间，但多语言会推高需求（讲义：多语言/前沿 200k+）。合理答案是 100k 左右并做实验，重点是给出理由：词表越大，序列越短、推理越便宜，但 embedding/输出层参数越多、罕见 token 训练不足。
- **语料配比**：训练 tokenizer 的语料要对低资源语言**上采样**，否则会出现讲义说的"英文为主的词表把非拉丁文字拆成 5–10 倍 token"。
- **验证指标**（对应讲义 Ship It 的 validation plan）：每种语言分别统计 held-out 集的 tokens-per-word（或 tokens-per-character）、压缩率、OOV/`<unk>` 率、round-trip 解码一致性；各语言之间 token 膨胀比不能差太多。
- 加分点：主动提出把 tokenizer 产物（`tokenizer.json`）冻结并在 CI 中做哈希校验。

### Q16 — 参考回答要点

- **原因**：API 按 token 计费，而 tokenizer 的词表是在以英文为主的语料上训练的。日文、阿拉伯文等在词表中的整片段很少，被拆成更多 token。讲义指出，在 GPT-3.5 时代同样的提示用日语/阿拉伯语可能贵 5–10 倍，`o200k_base` 部分缓解了这一问题。
- **估算方法**：用与目标模型**完全一致**的 tokenizer 计数，例如 OpenAI 系模型用 tiktoken（`o200k_base`），它与线上计费的切分精确一致；按语言分别抽样真实对话，统计 P50/P95 token 数，再乘以价格和调用量；同时为 system prompt、工具 schema、对话历史预留预算。
- 常见误区：用"字符数 ÷ 4"之类的英文经验公式估算所有语言；用 A 模型的 tokenizer 估算 B 模型的费用。
- 加分点：提到 emoji、代码、特殊空白也会让 token 数偏离经验值，预算应基于实测而非估计。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 01 文本处理](../../01-text-processing/docs/zh.md)：传统 tokenization、词干提取，理解"词级切分"的局限。
- [阶段 05 · 04 GloVe、FastText 和 Subword Embeddings](../../04-glove-fasttext-subword/docs/zh.md)：FastText 的字符 n-gram 是子词思想的前身。
- Python 基础：`collections.Counter`、字典、元组。

### 本节被哪些后续内容用到
- [阶段 05 · 18 多语言 NLP](../../18-multilingual-nlp/docs/zh.md)：多语言词表的覆盖率与 token 膨胀问题。
- [阶段 05 · 20 Structured Outputs & 约束解码](../../20-structured-outputs-constrained-decoding/docs/zh.md)：约束解码是在 token 级别做 mask，一个 JSON 关键字可能横跨多个 BPE token。
- [阶段 07 · 06 BERT 与掩码语言建模](../../../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/zh.md)：WordPiece 的典型使用者。
- [阶段 07 · 07 GPT 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：byte-level BPE 的典型使用者。
- [阶段 10 · 01 Tokenizers](../../../10-llms-from-scratch/01-tokenizers/docs/zh.md) 与 [阶段 10 · 02 构建 Tokenizer](../../../10-llms-from-scratch/02-building-a-tokenizer/docs/zh.md)：从零训练 LLM 时的 tokenizer 工程。
- [阶段 11 · 11 缓存与成本](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：token 数直接决定 API 成本。
- [阶段 19 · 30 从零实现 BPE Tokenizer](../../../19-capstone-projects/30-bpe-tokenizer-from-scratch/docs/zh.md)：本节代码的完整工程版。

### 延伸关键词
`byte_fallback` · `character_coverage` · `subword regularization` · `BPE-dropout` · `tiktoken (cl100k_base / o200k_base)` · `HF Tokenizers` · `pre-tokenization` · `tokenizer.json` · `chat template` · `tokens-per-word / 压缩率`
