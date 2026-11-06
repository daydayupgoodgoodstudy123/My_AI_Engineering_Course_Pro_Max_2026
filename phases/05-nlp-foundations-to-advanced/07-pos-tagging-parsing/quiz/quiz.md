# 测验 · 词性标注和句法分析（POS Tagging and Syntactic Parsing）

> **阶段 05 · NLP 基础到进阶 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | POS tagging（词性标注） | 给每个 token 打一个语法类别（名词、动词、限定词……）；词形还原（lemmatization）必须先知道词性 |
| 2 | Penn Treebank vs Universal Dependencies | PTB 是英语专用的细粒度标签集（讲义记为 36 个，区分时态、单复数）；UD 只有 17 个粗粒度标签、跨语言通用 |
| 3 | 最频繁标签基线（MFT） | 每个词预测训练集中它最常出现的标签，未登录词用全局最常见标签；是任何正经模型的"地板" |
| 4 | 二元 HMM 标注器 | `P(tags, words) = Π P(tᵢ\|tᵢ₋₁)·P(wᵢ\|tᵢ)`；转移表 + 发射表，用计数加 Laplace/add-α 平滑估计 |
| 5 | Viterbi 解码 | 在标签网格（lattice）上做动态规划，求概率最大的整条标签序列；用 log 概率相加防止下溢 |
| 6 | HMM 的局限与更强模型 | HMM 只看局部（前一个标签 + 当前词），CRF 可加任意特征（后缀、词形、前后词）≈97%，BiLSTM-CRF / transformer ≈98%+；人工标注一致率约 97% 是天花板 |
| 7 | 成分句法 vs 依存句法 | 成分句法输出 NP/VP/PP 嵌套树；依存句法输出 (head, dependent, relation) 三元组，每个词恰有一个 head，跨语言、自由语序更友好 |
| 8 | 转移式 vs 图式依存分析 | 转移式（arc-standard / arc-eager）像 shift-reduce，贪心解码快；图式（Eisner、biaffine）给所有边打分取最大生成树，慢但更准 |
| 9 | 工程落地 | 生产中直接调 spaCy（`tag_` = PTB、`pos_` = UD、`dep_` + `head`），stanza/trankit 覆盖多语言；不要自己造 parser |

### 核心技能（能动手做到）

- [ ] 从零实现最频繁标签基线 `train_mft / predict_mft`，并解释未登录词为何回退到全局最常见标签
- [ ] 从零实现二元 HMM 的计数训练（含 `<BOS>`/`<EOS>`）与 add-α 平滑，能手算某个转移/发射概率
- [ ] 手写 Viterbi（含回溯指针 `back`），并说明其复杂度应为 `O(n·|T|²)`，能指出本节代码因重复求和而退化的地方并优化
- [ ] 能解释本节代码把 `chased` 标成 `AUX` 的原因（add-α 平滑对稀有标签的偏向），并提出改进
- [ ] 用 spaCy 读出一个句子的 `tag_ / pos_ / dep_ / head`，并据此画出依存树
- [ ] 能举出 2025–2026 年 LLM 管线中仍然需要 POS / 依存分析的 3 个以上场景（词形还原、aspect-based 情感、查询分解、结构化输出校验、跨语言迁移）

---

## 二、基础自测（选择题）

**Q1.** 关于 Penn Treebank（PTB）与 Universal Dependencies（UD）标签集，下列说法正确的是：

- A. UD 比 PTB 更细粒度，因此更适合英语单语任务
- B. PTB 区分 `VBD`/`VBZ`、`NN`/`NNS` 等细节；UD 只有 17 个粗粒度标签，且与语言无关
- C. 二者完全等价，只是标签名字不同
- D. UD 只适用于英语，PTB 适用于所有语言

**Q2.** 二元 HMM 标注器的联合概率 `P(tags, words) = Π P(tᵢ|tᵢ₋₁)·P(wᵢ|tᵢ)` 隐含了哪两个独立性假设？

- A. 每个词只依赖于前一个词；每个标签只依赖于当前词
- B. 每个标签只依赖于前一个标签；每个词只依赖于自己的标签
- C. 所有标签彼此独立；所有词彼此独立
- D. 每个标签依赖于整个句子；每个词依赖于所有标签

**Q3.** Viterbi 实现里把概率取 log 后相加，而不是直接把概率相乘，主要原因是：

- A. log 运算比乘法更快
- B. 长句子中几十个小于 1 的概率连乘会下溢为 0，取 log 后变成加法，数值稳定
- C. 取 log 后概率会变成正数，便于比较
- D. 为了让平滑项 `alpha` 生效

**Q4.** "I bought a saw" 和 "I saw the movie" 中 `saw` 的词性不同。下列哪种模型**最容易**利用"后一个词是 `the`"这样的特征来消歧？

- A. 最频繁标签基线
- B. 二元 HMM
- C. 带任意特征（前后词、后缀、词形）的 CRF
- D. 只用发射概率的 unigram 模型

**Q5.** 关于依存句法分析（dependency parsing），下列说法**错误**的是：

- A. 每个词恰好有一个 head（根节点除外）
- B. 每条边是一个 (head, dependent, relation) 三元组
- C. 输出是 NP、VP、PP 等非终结符的嵌套树
- D. 对自由语序语言比成分句法更友好

**Q6.** 下列哪一组分别是"转移式（transition-based）"和"图式（graph-based）"依存分析器的代表？

- A. Eisner 算法；arc-eager
- B. arc-standard / MaltParser；Dozat-Manning biaffine
- C. Viterbi；CRF
- D. spaCy；NLTK `pos_tag`

**Q7.** 某论文报告在 Penn Treebank 上 POS 标注准确率 99.3%。按照讲义的观点，你最应该怀疑：

- A. 模型参数量太小
- B. 人工标注者之间的一致率只有约 97%，远超 98% 很可能是对测试集过拟合或数据泄漏
- C. 用了 UD 标签集而不是 PTB
- D. 没有用 Viterbi 解码

---

## 三、动手 / 代码题

**Q8.** 本节 `main.py` 用如下训练集（节选）训练 MFT 与 HMM：

```python
TRAIN = [
    (["The", "cat", "sat", "on", "the", "mat"], ["DET", "NOUN", "VERB", "ADP", "DET", "NOUN"]),
    (["A", "dog", "ran", "across", "the", "road"], ["DET", "NOUN", "VERB", "ADP", "DET", "NOUN"]),
    (["Cats", "chase", "mice"], ["NOUN", "VERB", "NOUN"]),
    (["Dogs", "bark", "loudly"], ["NOUN", "VERB", "ADV"]),
    (["The", "mat", "is", "red"], ["DET", "NOUN", "AUX", "ADJ"]),
    (["A", "red", "cat", "sat"], ["DET", "ADJ", "NOUN", "VERB"]),
]
```

实际运行后，对 `"The cat chased the dog"` 的输出是：

```text
  mft : ['DET', 'NOUN', 'NOUN', 'DET', 'NOUN']
  hmm : ['DET', 'NOUN', 'AUX', 'DET', 'NOUN']
```

(a) 为什么 MFT 把未登录词 `chased` 标成 `NOUN`？
(b) HMM 明明学到了 `NOUN → VERB` 很常见（9 次 NOUN 转移里有 5 次去 VERB），为什么还是把 `chased` 标成了 `AUX`？请结合代码中的平滑公式定量说明。

**Q9.** 阅读 `viterbi` 的主循环：

```python
    for i in range(1, n):
        for j, tag in enumerate(tags_list):
            em_denom = sum(emissions[tag].values()) + alpha * (len(vocab) + 1)
            em = log_prob(emissions, tag, tokens[i].lower(), em_denom, alpha)
            best_prev = 0
            best_score = -1e30
            for k, prev_tag in enumerate(tags_list):
                tr_denom = sum(transitions[prev_tag].values()) + alpha * (len(tags_list) + 1)
                tr = log_prob(transitions, prev_tag, tag, tr_denom, alpha)
                score = V[i - 1][k] + tr + em
```

(a) 教科书上 Viterbi 的复杂度是 `O(n·|T|²)`。这段代码的实际复杂度是多少？为什么？
(b) 改写成"先预计算所有 log 转移/发射概率，再做 DP"的版本，复杂度降回 `O(n·|T|²)`。

**Q10.** `train_hmm` 里记录了 `transitions[prev]["<EOS>"] += 1`，但 `viterbi` 从未使用 `<EOS>`。另外，`viterbi([] , ...)` 会抛 `IndexError`。请修改 `viterbi` 的结尾部分：(1) 在选择最后一个标签时加上"转移到 `<EOS>`"的 log 概率；(2) 空输入返回 `[]`。

---

## 四、面试高频题

**Q11.**（基础必考）HMM、CRF、BiLSTM-CRF、Transformer 做序列标注（POS/NER）有什么本质区别？为什么 CRF 能用"任意特征"而 HMM 不能？

**Q12.**（原理深挖）请推导 Viterbi 的递推式，说明它和 forward 算法的区别，以及为什么不能用"每个位置独立取 argmax"代替。

**Q13.**（工程实践）LLM 都能直接输出 JSON 了，2026 年还有哪些场景值得跑 spaCy 的 POS + 依存分析？你会怎么选型？

**Q14.**（场景设计）要从 1000 句新闻里用依存分析抽取"主语-谓语-宾语"三元组，用于构建知识图谱。请给出方案、评估方法，以及你预期会失败的句式。

**Q15.**（追问型）HMM 标注器遇到未登录词（OOV）时怎么办？add-α 平滑有什么副作用？工业上怎么改进？

**Q16.**（原理深挖）成分句法和依存句法有什么区别？为什么依存句法在 2010 年代"赢了"？

---

## 五、参考答案与解析

### Q1 — 答案：B

PTB 是英语专用、细粒度的标签集，区分动词时态（`VBD` 过去式、`VBZ` 第三人称单数现在时）和名词单复数/专有名词（`NN`/`NNS`/`NNP`）。UD 只有 17 个粗粒度标签（`NOUN`、`VERB`、`AUX`、`DET`……），设计目标就是跨语言通用，所以是多语言/跨语言工作的默认选择。A 把粗细说反了；C 错在两者粒度不同、并非一一对应；D 把适用范围说反了。spaCy 里 `token.tag_` 是 PTB，`token.pos_` 是 UD。

### Q2 — 答案：B

`P(tᵢ|tᵢ₋₁)` 体现**一阶马尔可夫假设**：当前标签只依赖前一个标签；`P(wᵢ|tᵢ)` 体现**输出独立假设**：当前词只由自己的标签"生成"，与其他词、其他标签无关。正因为这两个假设，HMM 只能看到很局部的信息——这也是 Q4 中它难以利用"下一个词"的原因。A 把词和标签的角色弄反了；C、D 分别是过强和过弱的假设。

### Q3 — 答案：B

每个转移/发射概率都小于 1，一个 50 词的句子要连乘约 100 个小数，浮点数会下溢到 0，导致所有路径分数都是 0、无法比较。取 log 后 `log(ab) = log a + log b`，乘法变加法，且 log 单调递增，argmax 不变。A 不是主要原因；C 错，log 概率是负数；D 与平滑无关。本节代码里 `best_score = -1e30` 就是 log 空间的"负无穷"初值。

### Q4 — 答案：C

CRF 是判别式模型，直接建模 `P(tags | words)`，可以把"后一个词是 `the`""后缀是 `-ed`""首字母大写"等任意重叠特征都加进来，讲义给出 CRF ≈97%。二元 HMM（B）的发射只看当前词、转移只看前一个标签，信息只能通过标签链间接传递，而且 HMM 是生成式模型，加入重叠特征会破坏概率分解。A、D 根本不看上下文。

### Q5 — 答案：C

C 描述的是**成分句法**（constituency parsing）。依存句法的输出是词与词之间带标签的有向边，每个词恰有一个 head（ROOT 除外），边是 (head, dependent, relation) 三元组，如 `cats` 是 `running` 的 `nsubj`。因为不依赖短语的线性连续性，依存句法对自由语序语言更友好。

### Q6 — 答案：B

转移式：arc-standard / arc-eager 像 shift-reduce 解析器，读词、压栈、用 reduce 动作建边，代表实现 MaltParser，神经版本是 Chen & Manning (2014)。图式：给所有 head-dependent 边打分再求最大生成树，代表 Eisner 算法和 Dozat-Manning biaffine。A 把两者说反了；C 是序列标注的解码/模型；D 是工具库。

### Q7 — 答案：B

讲义指出：PTB 上人工标注者一致率约 97%，任务天花板由标注分歧决定，超过 98% 的模型"很可能是在过拟合测试集"。面试中遇到"SOTA 远超人类一致率"的数字，第一反应应是检查数据泄漏、测试集被反复调参使用、标注规范不一致等问题。

### Q8 — 参考答案

(a) MFT 对未登录词返回 `default_tag = all_tags.most_common(1)[0][0]`。训练集里 `NOUN` 出现 9 次，是最多的标签（`DET` 6 次、`VERB` 5 次），所以任何没见过的词都被标成 `NOUN`。

(b) 比较中间位置标 `VERB` 与 `AUX` 时，相关的三项因子是（实际计算值，α = 0.01，词表 18，标签 7 个）：

| 因子 | 标 `VERB` | 标 `AUX` |
|------|----------|---------|
| 转移 `P(x \| NOUN)` | (5+0.01)/(9+0.08) ≈ **0.552** | (1+0.01)/9.08 ≈ 0.111 |
| 发射 `P(chased \| x)`（未登录词） | 0.01/(5+0.19) ≈ 0.00193 | 0.01/(1+0.19) ≈ **0.00840** |
| 转移 `P(DET \| x)`（训练中都没见过） | 0.01/(5+0.08) ≈ 0.00197 | 0.01/(1+0.08) ≈ **0.00926** |
| 乘积 | ≈ 2.09e-6 | ≈ **8.65e-6** |

关键在于发射和后续转移的**分母**：`AUX` 在训练集中只出现 1 次，分母很小，于是 α 这点"平滑质量"在它身上占比更大——未登录词的发射概率是 `VERB` 的约 4.4 倍，没见过的 `AUX → DET` 转移也是 `VERB → DET` 的约 4.7 倍，合起来压过了 `NOUN → VERB` 约 5 倍的转移优势，最终 `AUX` 胜出约 4 倍。

这是 add-α 平滑的经典副作用：**越稀有的标签，对未知事件给出的概率越高**。改进：对未登录词使用基于后缀（`-ed` → 动词过去式）/词形的发射模型；按标签的开放/封闭类区分（`AUX`、`DET` 是封闭类，几乎不会产生新词）；用 Good-Turing / Kneser-Ney 等更合理的平滑；或者干脆换成能用特征的 CRF。同一个句子 MFT 和 HMM 都错了，也提醒我们：**在小数据上 HMM 不一定比基线好**。

### Q9 — 参考答案

(a) 三重循环 `i × j × k` 已经是 `O(n·|T|²)`，但最内层每次都执行 `sum(transitions[prev_tag].values())`，`transitions[prev_tag]` 最多有 `|T|+1` 个键，所以实际是 **`O(n·|T|³)`**；外加每个 `(i, j)` 对 `emissions[tag]` 求和，额外 `O(n·Σ|V_tag|)`。在 7 个标签的玩具数据上感觉不到，换成 PTB 的 45 个标签、上万句语料，就会慢几十倍。

(b) 预计算版本（与原实现在本节数据上输出完全一致，已验证）：

```python
import math

def viterbi_fast(tokens, transitions, emissions, tags, vocab, alpha=0.01):
    tags_list = list(tags)
    T, n = len(tags_list), len(tokens)
    if n == 0:
        return []
    # 1) 预计算分母：每个"给定标签"只求和一次
    tr_den = {p: sum(transitions[p].values()) + alpha * (T + 1)
              for p in ["<BOS>"] + tags_list}
    em_den = {t: sum(emissions[t].values()) + alpha * (len(vocab) + 1)
              for t in tags_list}
    # 2) 预计算 log 转移矩阵 |T|×|T| 和起始向量
    log_start = [math.log((transitions["<BOS>"].get(t, 0) + alpha) / tr_den["<BOS>"])
                 for t in tags_list]
    log_tr = [[math.log((transitions[p].get(t, 0) + alpha) / tr_den[p])
               for t in tags_list] for p in tags_list]

    def log_em(j, word):
        t = tags_list[j]
        return math.log((emissions[t].get(word, 0) + alpha) / em_den[t])

    V = [[log_start[j] + log_em(j, tokens[0].lower()) for j in range(T)]]
    back = [[0] * T]
    for i in range(1, n):
        w = tokens[i].lower()
        row, brow = [], []
        for j in range(T):
            k = max(range(T), key=lambda k: V[i - 1][k] + log_tr[k][j])
            row.append(V[i - 1][k] + log_tr[k][j] + log_em(j, w))
            brow.append(k)
        V.append(row)
        back.append(brow)
    path = [max(range(T), key=lambda j: V[-1][j])]
    for i in range(n - 1, 0, -1):
        path.append(back[i][path[-1]])
    return [tags_list[j] for j in reversed(path)]
```

要点：发射项 `em` 与 `k` 无关，可以放到 `max` 外面；预计算后 DP 部分是严格的 `O(n·|T|²)`。生产实现会进一步用 NumPy 把内层 `max` 向量化成 `(V[i-1][:, None] + log_tr).max(axis=0)`。

### Q10 — 参考答案

```python
    # 函数开头
    if n == 0:
        return []
    # ... 中间 DP 不变 ...

    # 结尾：把"句子在这里结束"的概率也算进去
    final_scores = []
    for j, tag in enumerate(tags_list):
        eos_denom = sum(transitions[tag].values()) + alpha * (len(tags_list) + 1)
        eos = log_prob(transitions, tag, "<EOS>", eos_denom, alpha)
        final_scores.append(V[n - 1][j] + eos)
    last_best = max(range(len(tags_list)), key=lambda j: final_scores[j])
    path = [last_best]
    for i in range(n - 1, 0, -1):
        path.append(back[i][path[-1]])
    return [tags_list[j] for j in reversed(path)]
```

解释：完整的 HMM 联合概率应包含 `P(<EOS> | t_n)`，否则模型不知道"什么标签适合结尾"（例如 `DET` 几乎不会出现在句末）。原代码的分母 `alpha * (len(tags_list) + 1)` 里的 `+1` 其实就是给 `<EOS>` 预留的平滑槽位，只是解码时没用上。在本节 3 个测试句上，加不加 `<EOS>` 结果相同（已验证），但在更大的语料上它会修正"以限定词/介词结尾"之类的错误。空输入时原代码在 `V[n - 1]` 处因 `n - 1 = -1` 而访问空列表，抛 `IndexError`。

### Q11 — 参考回答要点

- **HMM（生成式）**：建模联合分布 `P(tags, words)`，靠马尔可夫 + 输出独立两个假设分解。特征只有"当前词"和"前一个标签"。想加"后缀""下一个词"这类重叠特征，会让 `P(wᵢ|tᵢ)` 的分解不再成立。
- **CRF（判别式）**：直接建模 `P(tags | words)`，是全局归一化的对数线性模型，特征函数可以看整句任意位置（前后词、后缀、大小写、词形），只要求标签之间是链式结构，仍可用 Viterbi 解码。讲义：≈97%。
- **BiLSTM-CRF**：用双向 LSTM 自动学上下文特征，替代手工特征，顶部 CRF 层建模标签转移约束（如 NER 中 `I-PER` 不能跟在 `O` 后）。
- **Transformer**：预训练编码器 + token 分类头，上下文最充分，讲义：≈98%+；今天 POS/NER 基本都是"预训练模型上的 token classification"。
- **加分点**：提到 label bias 问题（MEMM 的局部归一化缺陷，CRF 用全局归一化解决）；指出准确率天花板受约 97% 的标注一致率限制。
- **常见误区**：说"CRF 不需要 Viterbi"——线性链 CRF 推理同样用 Viterbi。

### Q12 — 参考回答要点

- 定义 `V[i][t]` = 前 i 个词、且第 i 个标签为 t 的所有路径中的最大 log 概率。
- 初始化：`V[0][t] = log P(t | <BOS>) + log P(w₀ | t)`。
- 递推：`V[i][t] = maxₖ ( V[i-1][k] + log P(t | k) ) + log P(wᵢ | t)`，同时记 `back[i][t] = argmaxₖ`。
- 终止与回溯：取 `argmaxₜ V[n-1][t]`（完整版再加 `log P(<EOS>|t)`），沿 `back` 倒推出整条路径。复杂度 `O(n·|T|²)`，而穷举是 `O(|T|ⁿ)`。
- **与 forward 的区别**：forward 把 `max` 换成 `logsumexp`（求和），得到 `P(words)` 的边缘概率；Viterbi 求的是最优单条路径。
- **为什么不能逐位 argmax**：逐位取最大会忽略转移约束，可能拼出 `DET DET VERB` 这种整体概率很低的序列；Viterbi 保证全局最优（在模型假设下）。
- **加分点**：最优子结构——到达 (i, t) 的最优路径，其前缀一定是到达 (i-1, k*) 的最优路径；提到 beam search 是 Viterbi 在状态空间太大时的近似（seq2seq 解码就是这个思路）。

### Q13 — 参考回答要点

- **仍然有价值的场景**（讲义列举）：
  1. 词形还原：lemmatizer 需要 POS（`running → run`、`better → good`）；
  2. 结构化抽取/LLM 输出校验：检查主谓一致、必需修饰语等语法约束；
  3. aspect-based 情感：依存关系告诉你哪个形容词修饰哪个名词；
  4. 查询理解："movies directed by Wes Anderson starring Bill Murray" 通过依存树拆成结构化约束；
  5. 跨语言迁移：UD 标签和依存关系与语言无关；
  6. 低算力管线：上不了 transformer 时，POS + 依存 + 词典（gazetteer）能走很远。
- **为什么不全交给 LLM**：成本和延迟（spaCy 小模型 CPU 上每秒处理大量文本）、确定性与可复现、可审计；LLM 输出本身也需要被校验。
- **选型**：英语生产首选 spaCy（`en_core_web_sm/md/lg/trf`，按精度/速度权衡）；多语言、学术级精度选 stanza；追求最高 UD 精度选 trankit；NLTK 适合教学。讲义的技能卡明确："拒绝推荐自己造 parser"。
- **常见误区**：认为大小写无所谓——技能卡提醒，消费 POS 的管线若不处理大小写变体就是脆弱的。

### Q14 — 参考回答要点

- **方案**：spaCy 解析 → 以每个 `VERB`（`dep_ == "ROOT"` 或从句动词）为中心，找 `nsubj` 子节点作主语、`dobj` 作宾语；介词宾语走 `prep → pobj`；把 `compound`、`amod` 子树拼进名词短语，得到完整实体文本。
- **评估**：人工标注 50 条三元组作为金标准（讲义练习的做法），计算 precision / recall；抽样 20 条输出肉眼检查。
- **预期失败**：被动句（`nsubjpass` + `agent`，主宾需对调）；并列结构（"Alice and Bob founded X" 要展开为两条，`conj`）；主语省略或共享（"He came and left"）；PP 附着歧义（"saw the man with the telescope"）；名词-动词歧义词（`saw`、`book`、`can`）。
- **加分点**：结合共指消解把代词替换成实体；与 [关系抽取](../../26-relation-extraction-kg/docs/zh.md) 中的方法对比，规则抽取高精度低召回，适合冷启动。

### Q15 — 参考回答要点

- **OOV 的处理**：本节代码把所有未登录词视为同一个"UNK"事件，发射概率 = `α / (count(tag) + α·(|V|+1))`。
- **副作用**（结合 Q8）：add-α 会让出现次数少的标签对未知词给出**更高**的概率，导致 `chased` 被标成只见过 1 次的 `AUX`；α 太大还会把真实计数"抹平"。
- **工业改进**：
  1. 只让开放类（`NOUN`、`VERB`、`ADJ`、`ADV`、`PROPN`）生成未知词；
  2. 用后缀/前缀/词形特征（`-ing`、`-ed`、`-ly`、首字母大写、含数字）估计 `P(tag | 后缀)`，再用贝叶斯反转为发射概率；
  3. 用 hapax（只出现一次的词）的标签分布近似未知词的标签分布；
  4. 换成 CRF / 神经模型，用子词或字符级表示天然处理 OOV。
- **加分点**：指出大小写处理——本节代码统一 `.lower()`，丢掉了"首字母大写 → 专有名词"这一强信号。

### Q16 — 参考回答要点

- **成分句法**：短语结构树，NP、VP、PP 等非终结符层层嵌套，叶子是词；回答"哪些词组成一个短语"。
- **依存句法**：词与词之间的有向带标签边，每个词一个 head；回答"谁修饰谁、谁是谁的论元"，如 `cats --nsubj--> running`。
- **依存句法胜出的原因**（讲义）：跨语言泛化干净，尤其是自由语序语言；输出直接就是下游需要的"谓词-论元"关系；UD 项目提供了统一的多语言树库。
- **加分点**：成分树可以通过 head 规则转换成依存树；图式算法里，Eisner 算法处理投射（projective）树，Chu-Liu/Edmonds 最大生成树算法可以处理非投射树，后者对语序自由的语言更重要。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 01 文本处理](../../01-text-processing/docs/zh.md)：tokenization 与词形还原，本节回答了"词形还原为什么需要词性"。
- [阶段 02 · 14 朴素贝叶斯](../../../02-ml-fundamentals/14-naive-bayes/docs/zh.md)：计数估计概率 + Laplace 平滑，HMM 的发射表就是同一套思路。
- [阶段 01 · 22 随机过程](../../../01-math-foundations/22-stochastic-processes/docs/zh.md)：马尔可夫链，HMM 的转移部分。

### 本节被哪些后续内容用到
- [阶段 05 · 06 命名实体识别](../../06-named-entity-recognition/docs/zh.md)：同属序列标注，BIO 标签 + CRF/Viterbi 是同一套框架。
- [阶段 05 · 08 文本的 CNNs 和 RNNs](../../08-cnns-rnns-for-text/docs/zh.md)：BiLSTM 自动学上下文特征，引出 BiLSTM-CRF。
- [阶段 05 · 05 情绪分析](../../05-sentiment-analysis/docs/zh.md)：aspect-based 情感需要依存关系定位"哪个形容词修饰哪个名词"。
- [阶段 05 · 13 问答系统](../../13-question-answering/docs/zh.md)：用依存分析分解查询。
- [阶段 05 · 18 多语言 NLP](../../18-multilingual-nlp/docs/zh.md)：UD 标签集的跨语言价值。
- [阶段 05 · 26 关系抽取与知识图谱构建](../../26-relation-extraction-kg/docs/zh.md)：基于依存树的三元组抽取。
- [阶段 05 · 20 Structured Outputs & 约束解码](../../20-structured-outputs-constrained-decoding/docs/zh.md)：对 LLM 生成结果做语法/结构约束校验。

### 延伸关键词
`隐马尔可夫模型 (HMM)` · `forward-backward` · `线性链 CRF` · `label bias` · `MEMM` · `arc-eager / arc-standard` · `biaffine parser` · `Chu-Liu/Edmonds` · `投射性 (projectivity)` · `UD treebanks` · `spaCy / stanza / trankit`
