# 测验 · Transformers 之前的文本生成 — N-gram 语言模型（Text Generation Before Transformers — N-gram Language Models）

> **阶段 05 · NLP 从基础到进阶 · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Shannon 猜字游戏 | 猜测次数序列是文本的无损重编码；27 个符号的字母表上限 `log2(27) ≈ 4.75` bit/字母，人类借助 100 个字母的上下文只需 0.6–1.3 bit——英语大约四分之三是"被迫的" |
| 2 | 交叉熵与困惑度 | 交叉熵 = 模型平均每个符号需要的 bit（或 nat）数；困惑度 = `2^bits = e^nats`，是"猜完之后还剩多少等可能分支"；均匀猜 27 个符号的困惑度就是 27 |
| 3 | n-gram 模型 | 马尔可夫假设：`P(w_i | 前 n-1 个词) = count(上下文, w) / count(上下文)`；上下文长度就是"玩家的记忆" |
| 4 | 零计数问题 | 训练里没见过的 n-gram 概率为 0，任何含一个未见 n-gram 的句子整体概率为 0、困惑度为无穷，所以必须平滑 |
| 5 | 平滑方法谱系 | Laplace（加一）→ Good-Turing → 插值 → 回退（Katz）→ 绝对折扣 → Kneser-Ney |
| 6 | Kneser-Ney 的关键 | 绝对折扣 + 低阶模型用**接续概率**（一个词跟在多少种不同的词后面），而不是原始频次——"Francisco" 频次高但几乎只跟在 "San" 后面 |
| 7 | 插值 KN 的结构 | `P = max(c - D, 0)/c(prev) + λ(prev)·P_cont(w)`，`λ(prev) = D·|prev 的不同后继|/c(prev)` 正好是折扣释放出来的概率质量，保证归一 |
| 8 | 困惑度的可比性 | 只有在**完全相同的分词**下才可比较；测试集 OOV 率要单独报告，KN 不预留 `<UNK>` 时处理 OOV 很差 |
| 9 | n-gram 今天的位置 | KenLM 做语音 / MT 重打分、端侧输入法补全、教学；训练神经 LM 前先算一个 KN 基线，打不过它就说明管线有问题 |

### 核心技能（能动手做到）

- [ ] 从零写出带 `<s>`/`</s>` 填充的 bigram 计数，以及 Laplace 和插值 Kneser-Ney 两种平滑概率
- [ ] 手算本节语料上 `P_KN(sat | cat)` 与 `P_Laplace(sat | cat)`，并验证对任意上下文 `Σ_w P(w | prev) = 1`
- [ ] 实现困惑度：`exp(-(1/N)·Σ log P)`，知道 `</s>` 要计入 N、`<s>` 不计入
- [ ] 解释本节采样结果中出现 `the the`、`. .` 的原因，并通过调小折扣 / 增加数据改善
- [ ] 给 KN 模型加入 `<UNK>` 机制，对比加入前后含 OOV 测试句的困惑度
- [ ] 实现贪心解码与带温度的采样，说清两者在流畅度和多样性上的取舍

---

## 二、基础自测（选择题）

**Q1.** 一个 trigram（3-gram）语言模型在预测下一个词时，条件是：

- A. 整个句子之前的所有词
- B. 前 2 个词
- C. 前 3 个词
- D. 只看当前词本身的频率

**Q2.** 如果不做任何平滑，在测试集上计算 n-gram 困惑度，最常见的结果是：

- A. 困惑度略高于训练集
- B. 只要有一个测试 n-gram 没在训练中出现过，该句概率为 0，困惑度为无穷大
- C. 困惑度等于词表大小
- D. 困惑度为 1

**Q3.** "Francisco" 在语料中出现很多次，但几乎都跟在 "San" 后面。Kneser-Ney 对它的处理是：

- A. 因为原始频次高，给它很高的低阶概率
- B. 因为它出现的不同上下文很少，给它较低的接续概率，所以新的 "X Francisco" 组合概率低
- C. 直接把它从词表中删除
- D. 把 "San Francisco" 合并成一个词

**Q4.** 一个模型在字母级别平均需要 1 bit/字母，它的困惑度是：

- A. 1
- B. 2
- C. 4.75
- D. 27

**Q5.** Laplace（加一）平滑的主要问题是：

- A. 计算太慢
- B. 词表很大时，给大量未见事件分走过多概率质量，连真实出现过的稀有事件也被压低
- C. 会产生负概率
- D. 无法处理 `</s>`

**Q6.** 团队 A 用词级分词得到困惑度 85，团队 B 用 BPE 子词分词得到困惑度 22。以下结论正确的是：

- A. B 的模型更好
- B. A 的模型更好
- C. 两个数字在不同分词下不可直接比较
- D. 只要测试集是同一批句子就可以比较

**Q7.** 关于 n-gram 模型在 2026 年的用途，讲义中**没有**提到的是：

- A. 用 KenLM 给语音识别 / 机器翻译做低延迟重打分
- B. 端侧键盘的 trigram 自动补全
- C. 作为神经 LM 的困惑度基线
- D. 作为开放域聊天机器人的主生成模型

---

## 三、动手 / 代码题

**Q8.** 本节训练语料共 10 句，`cat` 作为上下文出现 6 次，后面跟过 `sat / ran / chased / watched / slept / .` 共 6 种不同的词；`sat` 前面出现过 `cat / dog / bird` 3 种不同的词；语料中不同的 bigram 类型共 50 个；词表大小 28。请用下面的代码手算 `P_KN(sat | cat)`（D=0.75）和 `P_Laplace(sat | cat)`。

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


def laplace_prob(bigrams, unigrams, vocab_size, prev, w):
    num = bigrams.get((prev, w), 0) + 1
    den = unigrams.get(prev, 0) + vocab_size
    return num / den
```

**Q9.** 运行 `main.py` 的真实输出中，采样结果是这样的：

```text
  seed=1: the under a sat on the dog chased the the hid ran after the .
  seed=7: the cat chased the ran .
  seed=42: the the cat sat dog a bird the . .
```

已知 `the` 作为上下文出现 17 次、有 11 种不同后继；`the` 的接续计数为 8（前面出现过 8 种不同的词）。(1) 计算 `P_KN(the | the)` 并解释为什么会频繁出现 `the the`；(2) 给出至少两种改善方法。

**Q10.** 测试句 `"the zebra sat ."` 中 `zebra` 从未在训练中出现。(1) `P_KN(zebra | the)` 是多少？`perplexity` 函数会怎么处理？(2) 请改写训练和评估流程，加入 `<UNK>` 机制。

**Q11.** `sample_sentence` 是按概率比例采样。请写一个 `decode(prob_fn, vocab, temperature, max_len=15, seed=0)`：`temperature == 0` 时做贪心（每步取 argmax），否则把概率按 `p^(1/T)` 重新加权后采样。并预测在本节 KN 模型上贪心解码的结果。

---

## 四、面试高频题

**Q12.**（基础必考）什么是困惑度？它和交叉熵损失是什么关系？困惑度 100 的直观含义是什么？为什么比较困惑度时必须使用相同的分词？

**Q13.**（原理深挖）详细讲解插值 Kneser-Ney：绝对折扣、`λ`、接续概率各起什么作用？为什么最终概率仍然归一？Modified Kneser-Ney 又改进了什么？

**Q14.**（原理深挖）n-gram 模型相比神经语言模型的根本局限是什么？为什么神经 LM 能"泛化"到没见过的 n-gram？

**Q15.**（工程实践）你训练了一个小型 Transformer LM，验证集困惑度 60。如何用 n-gram 基线判断这个数字是好是坏？你会做哪些一致性检查？

**Q16.**（追问型）讲义说"训练语言模型就是在最小化它玩 Shannon 猜字游戏的得分"，请解释这句话。为什么说语言模型 = 压缩器？

---

## 五、参考答案与解析

### Q1 — 答案：B

n-gram 模型条件于前 `n-1` 个词，trigram 是前 2 个。讲义："trigram 模型玩游戏时只有两个 token 的记忆，Transformer 有 100K 个"。

### Q2 — 答案：B

句子概率是各位置条件概率的乘积，任何一个为 0 整句就为 0，`log 0 = -∞`，困惑度无穷大。讲义举例：即使是 4-gram，留出集里也有很大比例的 4-gram 没在训练中出现过，所以"不平滑就无法在任何真实文本上评估"。本节代码在 `perplexity` 中用 `max(p, 1e-12)` 兜底，只是防止程序崩溃，不是真正的平滑。

### Q3 — 答案：B

KN 的接续概率 = "有多少种不同的词出现在 w 前面"/"不同 bigram 类型总数"。"Francisco" 只跟在 "San" 后面，接续概率很低，所以当它出现在新的上下文里时，回退部分给它的概率也低。这就是 KN 优于"直接用 unigram 频率回退"的地方。

### Q4 — 答案：B

困惑度 = `2^bits`，`2^1 = 2`，相当于每步只剩两个等可能选项。C 是 27 符号均匀分布的熵 `log2(27)`，D 是均匀猜 27 个符号的困惑度。

### Q5 — 答案：B

加一平滑相当于给每个可能的后继都假装见过一次。词表 V 很大时，分母 `c(prev) + V` 被 V 主导，真实观测的计数被稀释。本节小语料上就能看出：`P_Laplace(on → the)` 只有 0.129，而 KN 给出 0.79（`on` 后面 3 次都是 `the`）。

### Q6 — 答案：C

困惑度是"每个 token 的平均不确定性"。分词不同，token 的数量和单位都不同（子词序列通常更长、每个 token 更容易预测），数值不可比。skill 中明确："拒绝报告不同分词系统之间比较的困惑度。"要比较可以换算成**每字符 bit 数**或每词困惑度。即使测试句相同（D），分词不同仍然不可比。

### Q7 — 答案：D

A、B、C 都在讲义"Use It"部分。开放域聊天的主生成模型早已是神经 LM，n-gram 生成的句子"局部通顺、全局不连贯"。

### Q8 — 参考答案

**KN**：

- `count = c(cat, sat) = 1`，`denom = c(cat) = 6`
- `first = max(1 - 0.75, 0) / 6 = 0.25/6 ≈ 0.0417`
- `lam = 0.75 × 6 / 6 = 0.75`（6 种不同后继，每种都被扣了 0.75）
- `continuation(sat) = 3 / 50 = 0.06`
- `P_KN(sat | cat) = 0.0417 + 0.75 × 0.06 = 0.0417 + 0.045 ≈ 0.0867`

**Laplace**：

- `num = 1 + 1 = 2`，`den = c(cat) + V = 6 + 28 = 34`
- `P_Laplace(sat | cat) = 2/34 ≈ 0.0588`

两个结果都已实际运行验证（0.0867 与 0.0588）。注意 KN 中 `λ = 0.75`——`cat` 的 6 个后继都只出现过 1 次，每个被扣掉 75%，于是 75% 的概率质量交给了接续分布。这在小语料上是个大问题（见 Q9）。

### Q9 — 参考答案

(1) `P_KN(the | the)`：`count(the, the) = 0`，所以 `first = 0`；

- `λ(the) = 0.75 × 11 / 17 ≈ 0.485`
- `continuation(the) = 8 / 50 = 0.16`
- `P_KN(the | the) = 0.485 × 0.16 ≈ 0.0776`

作为对比，训练中真实出现过的 `the couch` 只有 `0.25/17 + 0.485 × 1/50 ≈ 0.0244`。也就是说模型认为 `the the` 比 `the couch` 还可能 3 倍！原因：

- 本语料极小，几乎所有 bigram 都只出现 1 次，**D=0.75 的折扣把每个观测到的 bigram 砍掉 75%**，大部分概率质量通过 λ 流向接续分布；
- 接续分布偏爱 `the`（8 种前驱，是全语料最"百搭"的词）和 `.`（10 种前驱），所以采样频繁出现 `the the`、`. .`、句子在奇怪的地方插入 `the`。
- 这正是讲义说的 n-gram 生成"局部看似合理、全局不连贯"，只不过在小语料上连"局部"都保不住。

(2) 改善方法：

- **调小折扣**：D=0.75 是在大语料上经验得出的值。实测本语料 D=0.1 时测试困惑度从 4.42 降到 3.56，seed=7 采样变成 `the cat chased the dog ran ran across the room .`；
- **Modified KN**：按计数分别使用 D1、D2、D3+ 三个折扣（计数为 1 的 bigram 折扣更小），这是讲义 skill 推荐的默认做法；
- **更多数据**：语料够大时大部分常见 bigram 计数远大于 1，0.75 的折扣就微不足道了；
- **更高阶 + 插值**：trigram 能利用更多上下文；
- **解码策略**：降低温度或用 top-k 截断，砍掉低概率尾部（见 Q11）。

### Q10 — 参考答案

(1) `zebra` 不在任何 bigram 中，`count = 0`；`denom = c(the) = 17 > 0`；`continuation(zebra) = 0`（它没出现在任何词后面），所以 `P_KN(zebra | the) = 0`。`perplexity` 用 `math.log(max(p, 1e-12))` 把 0 夹到 `1e-12`，`log(1e-12) ≈ -27.6`，一个位置就贡献了巨大的惩罚：实测 `"the zebra sat ."` 的困惑度约为 **774**（正常测试句只有 3–6）。接下来 `P(sat | zebra)` 因为 `denom = 0` 直接返回 `continuation(sat) = 3/50 = 0.06`。这个 `1e-12` 地板是个"隐藏超参"，不同人设成不同值，困惑度就不可比了。

(2) 加入 `<UNK>`：

```python
from collections import Counter

def build_vocab(train_sentences, min_count=2):
    counts = Counter(w for s in train_sentences for w in s)
    return {w for w, c in counts.items() if c >= min_count}

def map_unk(sentences, vocab):
    return [[w if w in vocab else "<UNK>" for w in s] for s in sentences]

vocab_set = build_vocab(train)                 # 训练中出现 1 次的词替换为 <UNK>
train_unk = map_unk(train, vocab_set)
test_unk = map_unk(test + [tokenize("the zebra sat .")], vocab_set)
bigrams, unigrams, unigram_contexts = train_bigrams(train_unk)
# ... 其余与 main() 相同，在 test_unk 上算困惑度
```

要点：

- 训练时把低频词替换成 `<UNK>`，让模型**学到** `<UNK>` 的上下文分布（`the <UNK>` 有真实计数），测试时 OOV 映射到 `<UNK>` 就有合理的非零概率。实测（`min_count=2`）`"the zebra sat ."` 的困惑度从约 774 降到约 4.5；但注意词表变了，这个数字不能和原模型的困惑度直接比较；
- 评估时要报告 OOV 率，并且所有对比系统使用相同的词表 / `<UNK>` 规则（skill："标注测试集的 OOV 率；KN 在不预留 `<UNK>` 时处理 OOV 很差"）；
- 子词分词（第 19 节）从根本上消除了词级 OOV 问题，这也是现代 LM 的做法。

### Q11 — 参考答案

```python
import random

def decode(prob_fn, vocab, temperature, max_len=15, seed=0):
    rng = random.Random(seed)
    tokens = ["<s>"]
    candidates = [w for w in vocab if w != "<s>"]
    for _ in range(max_len):
        probs = [(w, prob_fn(tokens[-1], w)) for w in candidates]
        if temperature == 0:                      # 贪心
            nxt = max(probs, key=lambda x: x[1])[0]
        else:
            weighted = [(w, p ** (1.0 / temperature)) for w, p in probs if p > 0]
            total = sum(p for _, p in weighted)
            r = rng.random() * total
            acc, nxt = 0.0, weighted[-1][0]
            for w, p in weighted:
                acc += p
                if r <= acc:
                    nxt = w
                    break
        tokens.append(nxt)
        if nxt == "</s>":
            return tokens[1:-1]
    return tokens[1:]
```

本节 KN 模型上贪心解码的结果（已实测）是 `the cat .`：

- `<s>` 之后 `the` 概率最高（10 句里 7 句以 `the` 开头）；
- `the` 之后 `cat` 最高（`the cat` 出现 5 次）；
- `cat` 之后，`.` 的概率（约 0.19）高于 `sat`（0.087），因为 `.` 的接续概率最大（10 种前驱），而 `cat` 的 λ 高达 0.75，回退项占主导；
- `.` 之后 `</s>` 约 0.93。

取舍：温度 → 0 趋向贪心，输出确定、短而"安全"，容易重复或过早结束；温度 = 1 等价于原始采样；温度 > 1 拉平分布，更多样也更容易胡言乱语。

### Q12 — 参考回答要点

- 定义：`PPL = exp(-(1/N)·Σ log P(w_i | context_i))`，即平均负对数似然（交叉熵）的指数。用 log2 时 `PPL = 2^H`，用自然对数时 `PPL = e^H`，两者是同一测量的不同单位。
- 与训练损失的关系：语言模型训练最小化的交叉熵损失就是 `H`，所以"验证集 loss 下降"与"困惑度下降"是一回事，`PPL = exp(loss)`（loss 用 nat 时）。
- 直观含义：困惑度 100 = 模型平均每一步的困惑程度相当于在 100 个词中均匀地猜。均匀猜 27 个符号的困惑度就是 27。
- 必须同分词：N 是 token 数，分词改变 N 和每个 token 的难度；字符级、子词级、词级的困惑度不在同一尺度上。跨分词比较应换算成 bits-per-character / bits-per-byte。
- 常见误区：忘记把 `</s>` 计入 N（模型也要预测"句子结束"）；对 OOV 用不同的地板值，导致结果不可比。

### Q13 — 参考回答要点

- 公式（bigram 插值 KN）：`P_KN(w | v) = max(c(v,w) - D, 0)/c(v) + λ(v)·P_cont(w)`。
- **绝对折扣**：每个观测到的 bigram 计数都减去固定的 D（常用 0.75）。理由：高计数的 bigram 减掉 0.75 几乎无影响，低计数的被打折更多——低计数本来就最不可靠。
- **λ(v) = D·N₁₊(v ·)/c(v)**，其中 `N₁₊(v ·)` 是 v 的不同后继数。它恰好等于从 v 的所有 bigram 中扣下来的总质量，所以 `Σ_w 第一项 = 1 - λ(v)`；而 `Σ_w P_cont(w) = 1`，因此总和 `= 1 - λ + λ·1 = 1`。本节代码中对 `the`、`cat`、`.` 求和都实测为 1.0。
- **接续概率** `P_cont(w) = N₁₊(· w) / N₁₊(· ·)`：w 有多少种不同的前驱 / 不同 bigram 类型总数。它回答"w 作为一个新组合的结尾有多常见"，而不是"w 出现过多少次"——"San Francisco" 的例子。
- **Modified KN**（Chen & Goodman）：对计数为 1、2、≥3 的 n-gram 分别使用不同折扣 D1、D2、D3+，并递归地用于更高阶；它是讲义 skill 中的默认平滑方法，KenLM 的标准做法。
- 加分点：能指出小语料上 D=0.75 过大（本节 `the the` 现象），以及高阶模型递归地以低阶 KN 作为回退分布。

### Q14 — 参考回答要点

- **数据稀疏**：n-gram 的参数是离散计数表，参数量随 n 指数增长，绝大多数长 n-gram 从未见过，只能靠平滑"猜"。
- **没有相似性概念**：`the cat sat` 见过 100 次，对 `the dog sat` 毫无帮助——`cat` 和 `dog` 只是不同的符号（第 15 节 LDA 也是同一问题）。神经 LM 用 embedding 把词映射到连续空间，`cat` 与 `dog` 的向量相近，于是对没见过的组合也能给出合理概率（Bengio 2003 神经概率语言模型的核心动机）。
- **上下文长度固定且很短**：trigram 只有 2 个 token 记忆；增大 n 会使稀疏问题更严重。RNN 理论上无限长，Transformer 可达 100K+ token。
- **结果**：讲义给出的对比是 Brown 语料上调好的 4-gram KN 困惑度约 140，Transformer 约 15–30，差距约 10 倍，"这就是领域转向的原因"。
- 优势仍在：训练只是计数（秒级），推理是查表（微秒级），可解释，模型可以极小——所以在重打分、端侧补全中仍有一席之地。

### Q15 — 参考回答要点

- 在**完全相同的训练数据、相同分词、相同测试集**上训练一个 KN 基线（skill：通用英语 trigram，大语料 4-gram，用 `kenlm` 生产、`nltk.lm` 教学），计算困惑度。
- 判断：讲义："如果你的 Transformer 没有大幅超过 KN，一定是哪里出了问题。"例如 KN 是 120，你的模型 60 也许还行；KN 是 65，你的 60 就说明神经模型几乎没学到东西。
- 一致性检查：
  - 分词一致：两边用同一个 tokenizer，同样处理 `</s>`；
  - 测试集无泄漏：没有和训练集重叠的句子；
  - OOV 处理一致：同样的 `<UNK>` 规则、同样的词表；
  - 损失单位：确认 loss 是 nat 还是 bit，`exp` 还是 `2^`；
  - 是否按 token 平均（而不是按句子平均）；padding token 是否被误计入。
- 加分点：再做一个 unigram / 均匀分布的困惑度作为下界参照（均匀分布的困惑度 = 词表大小）。

### Q16 — 参考回答要点

- Shannon 游戏：遮住下一个字母让人猜，记录猜中所需次数。猜测次数序列可以被一个"相同的猜测者"无损还原成原文，所以它是文本的一种编码；能用更少的符号编码，说明每个符号携带的信息更少——由此给出英语熵的上界（0.6–1.3 bit/字母，远小于 4.75）。
- 语言模型就是一个机械化的猜测者：它给出下一个符号的概率分布，**交叉熵损失 = 用这个模型对真实文本编码时平均每个符号需要的 bit 数**。训练 LM 最小化交叉熵，就是让它在游戏中得分更高。
- LM = 压缩器：用算术编码等熵编码器，配合一个给出 `P(下一个符号)` 的模型，就能把文本压缩到约每符号 `-log2 P` bit；模型预测越准，压缩率越高。所以"更好的语言模型"和"更好的压缩"是同一件事。
- 讲义原话："规则从未改变，只是玩家变强了"——从 trigram 的 2 个 token 记忆到 Transformer 的 100K token。
- 加分点：说清 bit 与 nat 的单位换算（`1 nat = 1/ln2 ≈ 1.44 bit`），以及困惑度 `e^nats = 2^bits`。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 01 文本处理](../../01-text-processing/docs/zh.md)：分词直接决定 n-gram 的单位与困惑度的可比性。
- [阶段 02 · 14 朴素贝叶斯](../../../02-ml-fundamentals/14-naive-bayes/docs/zh.md)：同样是基于计数的概率模型，同样需要 Laplace 平滑。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：熵、交叉熵、bit 与 nat。
- [阶段 01 · 06 概率与分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：条件概率与链式法则。

### 本节被哪些后续内容用到
- [阶段 05 · 08 文本的 CNNs 和 RNNs](../../08-cnns-rnns-for-text/docs/zh.md)：神经语言模型如何突破固定窗口。
- [阶段 05 · 19 子词 Tokenization](../../19-subword-tokenization/docs/zh.md)：子词从根本上解决 OOV，并改变困惑度的计量单位。
- [阶段 07 · 07 GPT 与因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：同一个"预测下一个 token"的游戏，换成了 Transformer 玩家。
- [阶段 10 · 04 预训练 Mini-GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：训练 loss 与困惑度的实际使用。
- [阶段 10 · 10 LLM 评估](../../../10-llms-from-scratch/10-evaluation/docs/zh.md) 与 [阶段 19 · 73 困惑度与校准](../../../19-capstone-projects/73-perplexity-calibration/docs/zh.md)：困惑度在 LLM 评估中的角色。

### 延伸关键词
`马尔可夫假设` · `MLE` · `Good-Turing` · `Katz 回退` · `Modified Kneser-Ney` · `KenLM` · `交叉熵 / bits-per-character` · `温度采样` · `top-k / nucleus 采样` · `<UNK> 与子词` · `Shannon 熵估计`
