# 测验 · Tokenizers: BPE, WordPiece, SentencePiece（Tokenizers: BPE, WordPiece, SentencePiece）

> **阶段 10 · 从零构建 LLM · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/bpe.py](../code/bpe.py)、[code/main.py](../code/main.py) ｜ 代码讲解：[code/bpe.讲解.md](../code/bpe.讲解.md)、[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三种粒度的取舍 | 词级会 OOV（出 `[UNK]`）、字符级序列太长，subword（子词）在词表大小与序列长度之间取得平衡，是所有现代 LLM 的选择 |
| 2 | BPE 训练循环 | 从字符/字节出发，统计相邻 pair → 合并最高频的一对 → 记入合并表 → 重复，直到达到目标词表大小 |
| 3 | 合并表就是 tokenizer | 编码时必须**按学到的顺序**依次应用合并；顺序错了，"the" 可能永远拼不出来 |
| 4 | Byte-level BPE | 基础词表就是 256 个字节值，任何 UTF-8 文本都能表示，**永远没有未知 token**；GPT-2/GPT-4/Llama 3 都用它 |
| 5 | WordPiece | 合并标准是 `count(AB) / (count(A)·count(B))`，偏好"共现得出人意料"的 pair；用 `##` 标记词内续接片段；BERT 词表 30,522 |
| 6 | SentencePiece | 直接把原始 Unicode 流（含空格）当输入，不做预分词，语言无关；支持 BPE 与 Unigram 两种模式 |
| 7 | Unigram | 与 BPE 方向相反：从大词表出发，迭代删除对整体似然影响最小的 token（剪枝而非合并） |
| 8 | 词表大小的工程取舍 | 词表越大 → 序列越短、推理越快，但 embedding 矩阵越大：128K×4096 ≈ 524M 参数，32K×4096 ≈ 131M |
| 9 | 多语言税 | 以英文为主训练的 tokenizer 对韩文、中文等每词要 2–3 个 token，等于上下文窗口和费用都"打折"；Llama 3 把词表从 32K 扩到 128K 部分就是为此 |
| 10 | 压缩比 / fertility | 压缩比 = token 数 / 输入字节数，越低越好；fertility = 平均每个词的 token 数，1.0 最理想 |

### 核心技能（能动手做到）

- [ ] 不依赖任何库，从零写出 byte-level BPE 的 `train / encode / decode`，并在任意句子上验证 `decode(encode(s)) == s`
- [ ] 给定一个小语料和词频，手算前 2–3 步 BPE 合并（包括平局时代码会选哪一个）
- [ ] 能解释为什么 `encode` 要按合并表的插入顺序应用合并，并举出"顺序错了结果不同"的例子
- [ ] 把合并标准改成 WordPiece 的似然比打分，在同一语料上对比两者学到的词表
- [ ] 计算任意文本的压缩比和平均每词 token 数，并解释训练语料外的文本（如 "unhappiness"）为什么会退化成逐字节编码
- [ ] 能估算词表大小变化对 embedding 参数量的影响（`V × d`），并说出它对序列长度和推理成本的反向影响

---

## 二、基础自测（选择题）

**Q1.** 语料为 `lower ×5`、`lowest ×2`、`newest ×6`，从字符开始做 BPE，**第一次**合并的是哪一对？

- A. `(e, s)`，计数 8
- B. `(s, t)`，计数 8
- C. `(w, e)`，计数 13
- D. `(l, o)`，计数 7

**Q2.** 对字符序列 `aaabdaaabac` 只做一步合并。BPE（按频次）和 WordPiece（按 `count(AB)/(count(A)·count(B))`）分别会选哪一对？

- A. 两者都选 `(a, a)`
- B. BPE 选 `(a, a)`，WordPiece 选 `(b, d)`
- C. BPE 选 `(a, b)`，WordPiece 选 `(a, a)`
- D. BPE 选 `(a, a)`，WordPiece 选 `(a, c)`

**Q3.** Byte-level BPE 能保证"永远不会出现未知 token"，根本原因是：

- A. 它的词表足够大（10 万以上），覆盖了所有常见词
- B. 它的基础词表是全部 256 个字节值，任何 UTF-8 文本都能拆成字节序列
- C. 它会把未知字符映射到最相似的已知 token
- D. 它的基础词表是全部 Unicode 码点

**Q4.** 隐藏维度 d = 4096 不变，把词表从 32K 扩到 128K，**输入 embedding 矩阵**大约增加多少参数？

- A. 约 96M
- B. 约 393M
- C. 约 524M
- D. 约 4M

**Q5.** 关于 SentencePiece，下列说法正确的是：

- A. 使用前必须先按空格预分词，否则无法处理中文
- B. 把原始 Unicode 字符流（包括空格）直接作为输入，不做预分词，同时支持 BPE 与 Unigram 两种算法
- C. 它只是 Unigram 算法的别名，不支持 BPE
- D. 与 GPT-2 一样，以 256 个字节作为基础词表

**Q6.** Unigram 分词算法与 BPE 在"构建词表的方向"上的区别是：

- A. Unigram 从字符出发逐步合并，BPE 从大词表出发逐步删除
- B. 两者方向相同，只是打分函数不同
- C. Unigram 从一个大词表出发，迭代删除对整体似然影响最小的 token；BPE 从小词表出发不断合并
- D. Unigram 不需要训练，直接用字典

**Q7.** Llama 2 用 32K 词表的 SentencePiece BPE，Llama 3 换成 128,256 词表的 byte-level BPE（tiktoken 系）。讲义认为扩大词表的主要动机是：

- A. 减少 embedding 参数量
- B. 更好地压缩非英语文本（降低"多语言税"），让同样的上下文窗口装下更多内容
- C. 为了重新引入 `[UNK]` token
- D. 让每一步训练的计算量变小

---

## 三、动手 / 代码题

**Q8.** 用 `code/bpe.py` 中的 `BPETokenizer` 执行下面的代码，写出**全部打印输出**，并回答：①第 2 步为什么选 `(256, 97)` 而不是同样出现 2 次的 `(97, 98)`？②为什么 `encode("aaaa")` 的结果不是 `[257, 97]`？

```python
from bpe import BPETokenizer
t = BPETokenizer().train("aaabdaaabac", 3)
print(t.encode("aaaa"))
```

相关源码：

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

**Q9.** 运行 `code/main.py`（50 次合并）后，`"The cat sat on the mat."` 被编码成下面 7 个 token（这里把 id 换成了对应的字节串）：

```text
[b'The ', b'c', b'at', b' sat on the ', b'm', b'at', b'.']
```

已知学到的合并表中有 `258: b'at'`、`265: b' s'`、`272: b'at '`、`284: b' sat on the '`。请回答：

1. 为什么会出现横跨三个单词的 token `' sat on the '`？这在生产级 tokenizer 中通常如何避免？
2. 合并表里明明有 `'at '`（272），为什么 `cat` 后面的 `at` 没有和空格合并成 `'at '`？

**Q10.** 讲义练习 3 要求实现 WordPiece 的合并标准。请写一个函数 `best_pair_wordpiece(tokens)`：输入当前 token 列表，返回使 `count(AB) / (count(A)·count(B))` 最大的相邻 pair；然后说明如何把它接入 `BPETokenizer.train`，以及在 `list("aaabdaaabac")` 上它返回什么。

---

## 四、面试高频题

**Q11.**（基础必考）BPE、WordPiece、Unigram 三种子词算法有什么区别？分别被哪些代表模型使用？

**Q12.**（原理深挖）Byte-level BPE 为什么能彻底消灭 OOV？它带来了哪些副作用（尤其对中文、emoji 和流式输出）？

**Q13.**（工程实践）你要为一个新的 7B 模型选词表大小，32K、128K、200K 怎么选？请从参数量、序列长度、推理成本、多语言几个角度分析。

**Q14.**（场景设计）要训练一个面向"中文 + 英文 + 代码"的模型，你会如何设计和评估它的 tokenizer？

**Q15.**（追问型）为什么 LLM 经常数不清 "strawberry" 里有几个 r、做多位数算术容易出错？这和 tokenizer 有什么关系？有什么缓解办法？

---

## 五、参考答案与解析

### Q1 — 答案：C

`(w,e)` 出现在三个词里：`lower` 5 次 + `lowest` 2 次 + `newest` 6 次 = 13，是最大值。`(e,s)` 和 `(s,t)` 都只来自 `lowest` 与 `newest`（2+6=8）；`(l,o)` 来自 `lower` 与 `lowest`（5+2=7）。BPE 只看**原始频次**，所以先合并 `we`。（注：讲义里先写了"Step 3 合并 (e,s)"又自我更正——合并 `we` 之后 `e` 已被吸收，`(e,s)` 这个 pair 已经不存在，正确的第二步是在并列 8 次的 `(we,s)` 与 `(s,t)` 中选一个。）

### Q2 — 答案：B

字符计数：`a`=7、`b`=2、`c`=1、`d`=1。相邻 pair 计数：`(a,a)`=4、`(a,b)`=2、其余各 1。

- BPE：频次最高的是 `(a,a)`。
- WordPiece 打分：`(a,a)` = 4/(7·7) ≈ 0.08；`(a,b)` = 2/(7·2) ≈ 0.14；`(a,c)` = 1/(7·1) ≈ 0.14；`(b,d)` = 1/(2·1) = **0.5**，最高。

`b` 和 `d` 都很少见，却"恰好总是挨在一起"，这正是 WordPiece 偏好的"出人意料的共现"。D 中 `(a,c)` 被高频的 `a` 拖低了分数。

### Q3 — 答案：B

UTF-8 把任何字符编码成 1–4 个字节，每个字节取值 0–255。只要基础词表包含全部 256 个字节，最坏情况就是"逐字节编码"，不可能出现词表外的输入。A 只是"降低概率"而非"保证"；C 不是 BPE 的机制；D 是字符级 BPE 的做法，Unicode 码点有十几万个，仍可能遇到训练时没见过的字符。

### Q4 — 答案：B

`(128,000 − 32,000) × 4,096 = 393,216,000 ≈ 393M`。讲义中的数字是：128K 词表约 524M、32K 词表约 131M，差约 400M。C 是 128K 词表的**总量**而不是增量。若输出层（LM head）不与 embedding 共享权重，输出层还会再增加同样的量。

### Q5 — 答案：B

SentencePiece 的核心卖点是"不需要预分词"：把空格也当作普通符号处理，因此对中文、日文、泰文这类不用空格分词的语言同样适用。它支持 BPE 与 Unigram 两种模式（Llama 2 用 BPE 模式，T5 用 Unigram 模式）。D 描述的是 GPT-2 式的 byte-level BPE。

### Q6 — 答案：C

BPE 是"自底向上"：从字符/字节出发，不断合并。Unigram 是"自顶向下"：先准备一个很大的候选词表，再反复删除对训练数据整体似然影响最小的 token，直到达到目标大小。A 把方向说反了；B 忽略了方向差异；D 错在 Unigram 同样需要在语料上训练。

### Q7 — 答案：B

讲义明确指出：以英文为主的 tokenizer 对其他语言非常不友好（韩文在 GPT-2 tokenizer 中平均每词 2–3 个 token），Llama 3 将词表扩大 4 倍，让更多 token 分配给非英文脚本，从而在不同语言间实现更公平的压缩。A 恰好相反（embedding 会变大）；D 不对，更大的词表会让 embedding 与输出 softmax 的计算变多，收益来自序列变短。

### Q8 — 参考答案

输出：

```text
Merge 1: (97, 97) -> 256 = b'aa'
Merge 2: (256, 97) -> 257 = b'aaa'
Merge 3: (257, 98) -> 258 = b'aaab'
[256, 256]
```

（已在本地实际运行验证。）

逐步推导：

- 第 1 步：`(97,97)` 即 `(a,a)` 计数 4（注意 `_get_pairs` 统计的是**重叠**出现次数，`aaa` 里有 2 个 `aa`），最大，合并为 256。`_merge_pair` 从左到右、**不重叠**地替换，`aaab` → `[256, a, b]`，序列变为 `256 a b d 256 a b a c`。
- 第 2 步：`(256,97)` 与 `(97,98)` 都是 2 次，并列。`max(pairs, key=pairs.get)` 在并列时返回**第一个遇到的键**，而 `Counter` 保留插入顺序——`(256,97)` 在序列中先出现，所以被选中。这是一种"隐式的平局规则"，换个语料顺序结果就可能不同。
- 第 3 步：序列为 `257 b d 257 b a c`，`(257,98)` 出现 2 次最大。

`encode("aaaa")`：按顺序应用合并。先应用 `(97,97)→256`，从左到右不重叠替换得 `[256, 256]`；再应用 `(256,97)→257` 时序列里已没有单独的 `97`，无法匹配；`(257,98)` 同理。所以结果是 `[256, 256]` 而不是 `[257, 97]`。这说明 BPE 编码是**确定性的贪心过程**，不保证得到"token 数最少"的切分。

### Q9 — 参考答案

1. **跨词 token**：本节代码直接在整段字节流上训练，**没有预分词**，空格只是普通字节 32。语料里 `" sat on the "` 反复出现（"The cat sat on the mat" / "The dog sat on the log"），于是被一步步合并成一个 token。生产级 tokenizer（如 GPT-2 / tiktoken）会先用正则把文本切成"词、数字、标点、空白"等片段（pre-tokenization），**只在片段内部做 BPE**，因此合并永远不会跨越词边界。讲义的 Key Terms 也把 pre-tokenization 定义为"在子词切分前应用的规则：按空白切分、分离数字、处理标点"。
2. **`at ` 没有出现**：编码按合并表顺序执行。处理到 `"cat sat"` 时，先应用 258 得到 `c|at| |s|at`；接着在 265 号合并 `(32,115)` 时，空格已经和后面的 `s` 合并成 `' s'`；等到 272 号 `(at, 空格)` 时，`at` 后面已经没有独立的空格了，所以无法匹配。`' s'` 随后又被 282、283、284 号合并一路吞并成 `' sat on the '`。这再次说明：**合并顺序决定一切**，后学到的合并可能因为前面的合并而"没机会"生效。

### Q10 — 参考答案

```python
from collections import Counter

def best_pair_wordpiece(tokens):
    unit = Counter(tokens)                           # count(A)、count(B)
    pairs = Counter(zip(tokens, tokens[1:]))         # count(AB)
    return max(pairs, key=lambda p: pairs[p] / (unit[p[0]] * unit[p[1]]))

print(best_pair_wordpiece(list("aaabdaaabac")))      # ('b', 'd')
```

接入方式：在 `train` 中把

```python
best_pair = max(pairs, key=pairs.get)
```

替换为 `best_pair = best_pair_wordpiece(tokens)`（或者给 `train` 增加一个 `criterion` 参数在两种打分之间切换），其余合并、记录 `merges`/`vocab` 的逻辑完全不变。若 `tokens` 长度小于 2，`pairs` 为空，`max` 会抛 `ValueError`，因此要保留原代码中 `if not pairs: break` 的判断，放在调用之前。

在 `list("aaabdaaabac")` 上返回 `('b', 'd')`（打分 0.5），而 BPE 选 `('a','a')`。可以观察到：WordPiece 更倾向合并"稀有但固定搭配"的片段，BPE 更倾向合并"高频片段"。

### Q11 — 参考回答要点

- **BPE**：自底向上合并，打分 = pair 频次 `count(A,B)`。代表：GPT-2/3/4、Llama 3（byte-level BPE），Llama 2（SentencePiece 的 BPE 模式）。
- **WordPiece**：同样自底向上合并，但打分是似然比 `count(AB)/(count(A)·count(B))`，偏好"共现超出偶然"的组合；词内续接片段用 `##` 前缀，如 `["un", "##happi", "##ness"]`。代表：BERT（30,522）。
- **Unigram**：自顶向下，从大候选集出发，反复删掉对语料似然影响最小的 token。代表：T5（SentencePiece Unigram，32K）。
- 补充：SentencePiece 是**库/框架**而非单一算法，特点是不做预分词、空格也是普通符号，支持 BPE 与 Unigram。
- 加分点：Unigram 是概率模型，同一个词可以有多种切分并按概率采样（subword regularization），可以作为数据增强；BPE 的编码是确定性的。
- 常见误区：说"RoBERTa 用 WordPiece"——RoBERTa 用的是 byte-level BPE，只有 BERT 本身是 WordPiece。

### Q12 — 参考回答要点

- **为什么没有 OOV**：基础单元是 256 个字节，UTF-8 能把任何字符写成字节序列，最坏退化为逐字节编码。
- **副作用**：
  - 一个汉字在 UTF-8 中占 3 字节，如果训练语料里中文少、相关合并没学到，一个汉字就要 2–3 个 token，序列变长、上下文和费用"打折"（多语言税）。
  - 单个 token 可能只是**半个字符**。单独 `decode` 一个 token 会得到乱码，本节代码用 `errors="replace"` 显示成 `�`。
  - 流式生成时不能每生成一个 token 就直接解码输出，需要缓冲到能组成完整 UTF-8 字符再输出。
  - 字节本身很多不可打印，GPT-2 的实现会把 256 个字节映射到可打印的 Unicode 字符再做合并，以便存储和调试（实现细节，可作加分点）。
- 加分点：SentencePiece 也有"字节回退（byte fallback）"选项，在字符级词表之外用字节兜底，思路相同。

### Q13 — 参考回答要点

- **参数量**：embedding（以及不共享权重时的 LM head）大小是 `V × d`。d=4096 时，32K≈131M、128K≈524M；对 7B 模型而言 128K 词表仍可接受，但对小模型（如 124M 级别）会让 embedding 占掉大半参数。
- **序列长度/推理成本**：词表越大压缩越好，讲义举例同一段英文 32K 词表 100 个 token、128K 词表约 70 个 token，生成时少 30% 的前向步数，KV cache、注意力计算也随之减少。
- **输出层成本**：每一步都要对 V 个 token 计算 logits 和 softmax，V 越大这部分越重。
- **稀有 token 训练不足**：词表越大，长尾 token 在训练中出现次数越少，embedding 学得越差（加分点：曾有"glitch token"现象，即词表里存在但几乎没在训练数据中出现的 token 会引发异常输出）。
- **多语言**：如果目标用户包括非英语人群，更大的词表能显著降低多语言税；趋势是 50K → 100K → 128K → 200K。
- 结论：7B 级多语言/代码模型一般选 100K–150K；纯英文小模型 32K–50K 足够。最终要用目标语料测 fertility 和压缩比，而不是拍脑袋。

### Q14 — 参考回答要点

- **算法**：byte-level BPE（保证不出 OOV），或 SentencePiece + 字节回退。
- **训练语料配比**：tokenizer 的训练数据必须覆盖目标分布。中文、代码要有足够比例，否则合并表里中文常用词、代码关键字和缩进模式学不到。
- **预分词规则**：按词/数字/标点/空白切分；数字按位或按固定长度切分，便于算术（如 cl100k_base 的正则把数字按最多 3 位切开）；对代码保留连续空白，让缩进能合并成少量 token。
- **特殊 token**：`<|endoftext|>`、对话角色标记、`<pad>` 等，ID 固定、永远不被 BPE 拆开。
- **词表大小**：在 100K 左右起步，权衡 embedding 参数与压缩率。
- **评估**：分语言统计 fertility（每词/每字 token 数）、压缩比（token/字节），与 tiktoken、Llama 3 等现成 tokenizer 对比；检查 `decode(encode(x)) == x` 的往返一致性；统计未使用或极少使用的 token。
- 常见误区：直接复用英文 tokenizer 去训练中文模型，导致中文序列长 2–3 倍、训练与推理成本都翻倍。

### Q15 — 参考回答要点

- **原因**：模型看到的是 token ID，而不是字母。"strawberry" 可能被切成 2–3 个子词，模型必须从 embedding 中"记住"每个 token 由哪些字母组成，这种信息并不直接可见。同理，数字被切成长度不一的片段（如 "3.14159265358979" 会被切成好几段），位值对齐不一致，导致逐位进位很困难。
- **与 tokenizer 的关系**：tokenization 把"字符级结构"压缩掉了，换来了更短的序列；这是讲义所说的"tokenization 不是预处理，而是架构"的直接体现。
- **缓解**：
  - 预分词时把数字按单个数字或固定位数切分；
  - 提示模型先把单词逐字母拆开再计数（让它在输出中显式展开字符）；
  - 对算术、计数类任务调用代码解释器等工具；
  - 研究层面也有字节级/字符级模型来避免这类问题，但会付出序列变长的代价。
- 加分点：用 tiktoken 现场演示同一个单词在不同上下文（有无前导空格、大小写）下会被切成不同 token，这也是模型"拼写不稳定"的来源。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 01 文本处理](../../../05-nlp-foundations-to-advanced/01-text-processing/docs/zh.md)：分词、规范化等文本预处理基础。
- [阶段 05 · 04 GloVe、FastText 与子词](../../../05-nlp-foundations-to-advanced/04-glove-fasttext-subword/docs/zh.md)：子词思想最早在词向量中的应用。
- [阶段 05 · 19 子词分词](../../../05-nlp-foundations-to-advanced/19-subword-tokenization/docs/zh.md)：BPE/WordPiece/Unigram 的 NLP 视角介绍。
- Python 基础：`bytes`、`str.encode/decode`、`collections.Counter`。

### 本节被哪些后续内容用到
- [阶段 10 · 02 从头开始构建 Tokenizer](../../02-building-a-tokenizer/docs/zh.md)：在本节基础上加入预分词、特殊 token、序列化等，做成完整可用的 tokenizer。
- [阶段 10 · 03 用于预训练的数据管道](../../03-data-pipelines/docs/zh.md)：用 tokenizer 把海量文本变成训练用的 token 序列。
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：词表大小直接决定 embedding 与 LM head 的形状和参数量。
- [阶段 05 · 18 多语言 NLP](../../../05-nlp-foundations-to-advanced/18-multilingual-nlp/docs/zh.md)：多语言税与跨语言公平性。
- [阶段 11 · 11 缓存与成本](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：API 按 token 计费，tokenizer 决定成本。
- [阶段 19 · 30 从零实现 BPE Tokenizer](../../../19-capstone-projects/30-bpe-tokenizer-from-scratch/docs/zh.md)：综合项目中再实现一次完整的 BPE。

### 延伸关键词
`tiktoken` · `cl100k_base / o200k_base` · `Hugging Face tokenizers` · `pre-tokenization 正则` · `byte fallback` · `subword regularization` · `fertility` · `glitch token` · `special tokens`
