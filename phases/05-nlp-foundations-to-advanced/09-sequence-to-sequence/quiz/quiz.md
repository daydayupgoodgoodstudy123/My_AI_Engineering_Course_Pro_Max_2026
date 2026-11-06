# 测验 · 序列到序列模型（Sequence-to-Sequence Models）

> **阶段 05 · NLP 基础到进阶 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | seq2seq 要解决的问题 | 变长序列 → 变长序列，输入输出词表不同、长度不对齐（翻译、摘要、改写） |
| 2 | Encoder | 一个 RNN 读完源句，`outputs` 是每个位置的隐状态 `[B, L, H]`，最后一步 `hidden` 作为**上下文向量** |
| 3 | Decoder | 另一个 RNN 以上下文向量为初始状态，每步输入上一个 token、输出目标词表上的分布，直到 `<EOS>` 或最大长度 |
| 4 | 上下文向量瓶颈 | 整个源句被压进一个定长向量：长句丢细节、罕见词被模糊、语序调整只能"背"——这正是 attention 要解决的 |
| 5 | Teacher forcing | 训练时 decoder 在第 t 步的输入是**真实的**第 t-1 个 token，稳定训练 |
| 6 | Exposure bias | 训练喂真值、推理喂自己的预测，二者分布不一致；缓解：scheduled sampling、最小风险训练、RL 微调 |
| 7 | 贪心解码 vs beam search | 贪心每步取最大、无法反悔；beam search 保留 top-k 个部分序列，常用宽度 3–5 |
| 8 | 现代形态 | BART、T5、mBART、NLLB 等 Transformer encoder-decoder；整体形状与 2014 年 seq2seq 相同，块内机制不同 |

### 核心技能（能动手做到）

- [ ] 能写出 GRU Encoder / Decoder 的 PyTorch 骨架，并说清 `outputs`、`hidden`、`logits` 的形状
- [ ] 能写出带 teacher forcing 比例的训练循环，并解释 `ignore_index=0`、`teacher_forcing_ratio` 的作用
- [ ] 能用纯 Python 实现贪心解码和 beam search，并构造一个"贪心不是全局最优"的反例
- [ ] 能读懂本节 `main.py` 的瓶颈模拟：指出它的"准确率"是在和随机序列比较、50% 是随机水平
- [ ] 能解释编码器"记住结尾、忘掉开头"与解码器"从开头生成"之间的矛盾，并说出 Sutskever 等人反转源句的动机
- [ ] 能针对翻译/摘要/改写任务，按讲义技能卡给出：预训练 checkpoint、解码策略、上线前必须检查的失败模式

---

## 二、基础自测（选择题）

**Q1.** 讲义中的 `Encoder` 用单层单向 `nn.GRU(embed_dim, hidden_dim, batch_first=True)`，输入 `src` 形状为 `[batch, seq_len]`。`forward` 返回的 `outputs` 与 `hidden` 形状分别是：

- A. `[batch, hidden_dim]` 和 `[batch, seq_len, hidden_dim]`
- B. `[batch, seq_len, hidden_dim]` 和 `[1, batch, hidden_dim]`
- C. `[seq_len, batch, hidden_dim]` 和 `[batch, hidden_dim]`
- D. `[batch, seq_len, embed_dim]` 和 `[1, batch, embed_dim]`

**Q2.** 关于 teacher forcing 与 exposure bias，正确的是：

- A. teacher forcing 是推理时把参考答案喂给 decoder
- B. teacher forcing 让训练更稳定，但训练与推理时 decoder 的输入分布不同，这个差距叫 exposure bias
- C. exposure bias 是指模型对训练集中高频词有偏好
- D. 只要 teacher forcing 比例为 1.0，就不会有 exposure bias

**Q3.** 讲义训练循环中 `nn.CrossEntropyLoss(ignore_index=0)` 的作用是：

- A. 忽略第 0 个 batch
- B. 不对 padding（id 为 0）位置计算损失
- C. 忽略 `<BOS>` token
- D. 让 id 为 0 的词永远不会被预测

**Q4.** 某个解码器第一步：`P(A)=0.5, P(B)=0.4`。若第一步选 A，第二步最好的 token 概率为 0.4；若选 B，第二步最好的 token 概率为 0.9（之后都以概率 1 结束）。下列说法正确的是：

- A. 贪心解码得到的序列概率是 0.36
- B. 贪心解码选 A，序列概率 0.2；宽度为 2 的 beam search 能找到概率 0.36 的 B 开头的序列
- C. beam search 一定能找到全局最优序列
- D. 两者结果相同，因为第一步 A 的概率更高

**Q5.** 讲义推荐的 scheduled sampling 做法是：

- A. 训练开始时 teacher forcing 比例为 0，逐渐升到 1
- B. 训练开始时 teacher forcing 比例为 1.0，逐步退火到约 0.5，让模型练习从自己的错误中恢复
- C. 每个 epoch 随机打乱训练样本顺序
- D. 按计划调整学习率

**Q6.** 下列哪一项**不是**缓解 exposure bias 的方法？

- A. scheduled sampling
- B. 以句子级 BLEU 为目标的最小风险训练（minimum risk training）
- C. 用序列级指标做奖励的强化学习微调
- D. 推理时把 beam 宽度从 4 增加到 10

**Q7.** 本节 `main.py` 的模拟中，序列长度为 80 时输出准确率约 51%。最恰当的解读是：

- A. 模型还能复制一半的 token
- B. 该指标是"真实序列得分是否高于一条随机序列"，51% 约等于抛硬币，说明定长、会遗忘的上下文向量已无法区分真伪
- C. 准确率不可能低于 50%，所以模型其实还不错
- D. 说明需要更多训练 epoch

---

## 三、动手 / 代码题

**Q8.** 阅读 `simulate_copy_accuracy` 的签名和主体：

```python
def simulate_copy_accuracy(seq_len, context_dim=8, epochs=200, n_train=300, seed=0):
    rng = random.Random(seed)
    vocab = list("abcdefghij")
    vocab_size = len(vocab)

    embed = [[rng.gauss(0, 0.3) for _ in range(context_dim)] for _ in range(vocab_size)]
    context = [0.0] * context_dim
    # ... encode / decode_score 定义 ...
    hits = 0
    trials = 100
    for _ in range(trials):
        seq = [rng.choice(vocab) for _ in range(seq_len)]
        c = encode(seq)
        target_score = decode_score(c, seq)

        noise_score = decode_score(c, [rng.choice(vocab) for _ in range(seq_len)])
        if target_score > noise_score:
            hits += 1
    return hits / trials
```

(a) 哪些参数/变量定义了却从未被使用？这说明这段代码"有没有训练"？
(b) 这个函数返回的"accuracy"到底衡量什么？为什么长序列时会趋近 50% 而不是 0%？
(c) 讲义 Step 5 给出的表格（5→98%、10→91%、20→62%、40→23%）能由这段代码复现吗？

**Q9.** 编码器和解码器的打分部分如下：

```python
    def encode(sequence):
        c = [0.0] * context_dim
        decay = 0.85
        for token in sequence:
            idx = vocab.index(token)
            for d in range(context_dim):
                c[d] = c[d] * decay + embed[idx][d]
        return c

    def decode_score(context, target):
        total = 0.0
        recovery = 1.0
        for token in target:
            idx = vocab.index(token)
            score = sum(context[d] * embed[idx][d] for d in range(context_dim))
            normed = math.tanh(score) * recovery
            total += max(0.0, normed)
            recovery *= 0.9
        return total / max(1, len(target))
```

(a) 长度为 L 的序列中，第 1 个 token 的 embedding 在最终 `c` 中的权重是多少？L = 20、40 时分别约为多少？
(b) `decode_score` 中 `recovery` 给哪些位置的 token 最大权重？这和 `encode` "记得最清楚"的位置是否一致？
(c) 如果把 `for token in target:` 改为 `for token in reversed(target):`，你预测长序列的准确率会怎样变化？这和 Sutskever 等人（2014）的什么技巧相呼应？

**Q10.** 讲义只给了 PyTorch 版贪心解码，并说"beam search 保留 top-k 个部分序列"。请用纯 Python 实现 `beam_search(step_fn, beam_width, max_len)`，其中 `step_fn(prefix)` 返回下一个 token 的概率字典；用 Q4 的数据验证：贪心得到概率 0.2 的序列，beam=2 得到 0.36 的序列。

---

## 四、面试高频题

**Q11.**（基础必考）讲一下经典 seq2seq（encoder-decoder）的结构和训练方式。它最大的缺陷是什么？attention 是怎么解决的？

**Q12.**（原理深挖）什么是 teacher forcing 和 exposure bias？有哪些缓解方法？这些问题在今天的 LLM 里还存在吗？

**Q13.**（原理深挖）beam search 的细节：为什么需要长度归一化？`<EOS>` 怎么处理？beam 越宽越好吗？为什么开放式对话的 LLM 很少用 beam search？

**Q14.**（工程实践）要给电商搜索做"query 改写"，手上有 5 万条（原 query, 改写 query）对。你会怎么设计 seq2seq 方案？

**Q15.**（追问型）在没有 attention 的年代，大家用了哪些办法缓解上下文向量瓶颈？为什么"反转源句"有效？

---

## 五、参考答案与解析

### Q1 — 答案：B

`batch_first=True` 只影响 `outputs`（以及输入）的维度顺序：`outputs` 是 `[batch, seq_len, hidden_dim]`，每个输入位置一个隐状态；`hidden` 永远是 `[num_layers × num_directions, batch, hidden_dim]`，单层单向即 `[1, batch, hidden_dim]`，即最后一步的状态（讲义原文）。经典 seq2seq 只用 `hidden` 作上下文向量、丢掉 `outputs`——而 attention 恰恰要用回这些被丢掉的 `outputs`。D 混淆了 embedding 维与隐藏维。

### Q2 — 答案：B

teacher forcing 发生在**训练**时（A 错）：第 t 步输入真实的第 t-1 个 token，避免早期错误连锁放大。推理时没有真值，只能喂模型自己的预测，训练从没见过"自己犯错后的状态"，这个分布差就是 exposure bias（讲义原文："That gap is called exposure bias"）。D 恰好相反：比例为 1.0 时 exposure bias 最严重。C 是另一个概念。

### Q3 — 答案：B

batch 内目标序列长度不同，短的会用 id 0（`padding_idx=0`）补齐；`ignore_index=0` 让这些位置不计入损失，否则模型会被训练去"预测 padding"，并且损失会被 padding 数量稀释。它不影响模型是否能输出 id 0（D），也与 `<BOS>` 无关（C）。

### Q4 — 答案：B

贪心：第一步取 A（0.5），第二步取 0.4，序列概率 `0.5 × 0.4 = 0.2`。beam=2 时第一步同时保留 A、B；第二步候选中 `B→x = 0.4 × 0.9 = 0.36` 最高，最终得到 0.36。这就是讲义说的"贪心一旦选定就无法收回（cannot unsay it）"。C 错：beam search 仍是近似搜索，宽度有限时也可能错过全局最优。Q10 的代码实际运行验证了这两个数字。

### Q5 — 答案：B

讲义原文：从 1.0（完全 teacher forcing）开始，在训练过程中退火到约 0.5，以缩小 exposure bias 差距。先让模型在"有真值扶着"的情况下学会基本映射，再逐步让它面对自己的预测。D 描述的是学习率调度，名字相似但完全不同。

### Q6 — 答案：D

A、B、C 是讲义列出的三种缓解方法，都在**训练阶段**让模型接触自己的输出或序列级目标。增大 beam 宽度只是推理时的搜索策略，不改变模型"没练过从自己的错误中恢复"这一事实；甚至过大的 beam 在实践中常导致输出过短或更平淡。

### Q7 — 答案：B

代码比较的是 `decode_score(c, 真实序列)` 与 `decode_score(c, 随机序列)`，真实序列分高就算命中。完全"失忆"的模型也有 50% 的命中率（抛硬币），所以长序列下趋近 50% 而不是 0%。C 错：有限次试验（100 次）下可以略低于 50%，本节模拟中换 `seed=1` 时 80 长度就是 43%。代码中根本没有训练过程（见 Q8），D 不成立。

### Q8 — 参考答案

(a) `epochs=200`、`n_train=300` 两个参数从未使用，外层的 `context = [0.0] * context_dim` 也没用（`decode_score` 的参数 `context` 会遮蔽它）。代码里也没有任何梯度或参数更新：`embed` 是随机生成后固定不变的。所以这是一个**不训练的解析式模拟**，不是讲义 Step 5 描述的"训练一个 GRU 复制模型"。

(b) 衡量的是：用定长上下文 `c` 给"真实源序列"打的分，是否高于给"一条随机序列"打的分——一个二选一的判别任务，随机水平是 50%。实际运行结果：

```text
 seq_len    accuracy
       5        89%
      10        83%
      20        69%
      40        53%
      80        51%
```

序列越长，早期 token 在 `c` 中的权重越接近 0（见 Q9），真实序列与随机序列的得分越来越像，命中率就退化成抛硬币。

(c) 不能。讲义表格是"复制任务的 token 准确率"，会一路掉到 23%；本代码的指标下限是 50% 左右，数值和含义都不同。两者共同说明的是**趋势**：定长、会遗忘的上下文向量，随长度增加而失效。读代码时要分清"示意性模拟"与"真实实验结果"。

### Q9 — 参考答案

(a) 每读入一个新 token，已有状态都乘以 0.85。第 1 个 token 之后还有 `L-1` 个 token，所以权重是 `0.85^(L-1)`：L=20 时约 `0.85¹⁹ ≈ 0.046`，L=40 时约 `0.85³⁹ ≈ 0.0018`。而最后一个 token 的权重是 1。上下文向量几乎只"记得"结尾。

(b) `recovery` 从 1.0 开始每个位置乘 0.9，所以**目标序列开头**的 token 权重最大。而 `encode` 记得最清楚的是**源序列结尾**。两者恰好错位：解码器最看重的信息，正是编码器忘得最厉害的信息。这也是真实 seq2seq 的困境：decoder 从句首开始生成，但 encoder 的最终状态离句首最远。

(c) 改成 `reversed(target)` 后，解码器把最大权重给了目标的结尾 token，正好对上编码器记得最清楚的部分，长序列的准确率会大幅回升（在本节参数下实测：长度 5/10/20/40/80 分别约 94%/94%/93%/92%/93%，几乎不随长度下降）。这呼应了 Sutskever、Vinyals、Le（2014）的技巧：**把源句反转后再输入编码器**，让源句开头与目标句开头在时间上靠近，制造大量"短距离依赖"，让优化更容易。注意：这个模拟中准确率回升，也暴露了它的指标很宽松——只要最后几个 token 对得上就能区分真伪序列，并不代表整句都被记住了。

### Q10 — 参考答案

```python
import math

TABLE = {
    (): {"A": 0.5, "B": 0.4, "<eos>": 0.1},
    ("A",): {"x": 0.4, "y": 0.3, "<eos>": 0.3},
    ("B",): {"x": 0.9, "y": 0.05, "<eos>": 0.05},
}

def step_fn(prefix):
    return TABLE.get(tuple(prefix), {"<eos>": 1.0})

def greedy(step_fn, max_len=5):
    seq, logp = [], 0.0
    for _ in range(max_len):
        tok, p = max(step_fn(seq).items(), key=lambda kv: kv[1])
        seq.append(tok)
        logp += math.log(p)
        if tok == "<eos>":
            break
    return seq, logp

def beam_search(step_fn, beam_width=2, max_len=5):
    beams = [([], 0.0)]                      # (前缀, 累计 log 概率)
    finished = []
    for _ in range(max_len):
        candidates = []
        for seq, logp in beams:
            for tok, p in step_fn(seq).items():
                candidates.append((seq + [tok], logp + math.log(p)))
        candidates.sort(key=lambda c: c[1], reverse=True)
        beams = []
        for seq, logp in candidates[:beam_width]:
            (finished if seq[-1] == "<eos>" else beams).append((seq, logp))
        if not beams:
            break
    finished.extend(beams)                   # 到达 max_len 仍未结束的也参与比较
    return max(finished, key=lambda c: c[1])

g = greedy(step_fn)
b = beam_search(step_fn, 2)
print("greedy", g[0], round(math.exp(g[1]), 3))   # greedy ['A', 'x', '<eos>'] 0.2
print("beam2 ", b[0], round(math.exp(b[1]), 3))   # beam2  ['B', 'x', '<eos>'] 0.36
```

（已实际运行，输出如注释。）要点：
- 在 log 空间累加，避免长序列概率下溢；
- 每步把所有 `beam × |V|` 个扩展排序，只留 top-k；
- 遇到 `<eos>` 的序列移入 `finished`，不再扩展；
- 简化之处：这里已结束的序列也占用了当步的 beam 名额，且没有做长度归一化（见 Q13）。真实实现（如 Hugging Face 的 `num_beams`）会在 GPU 上批量计算，并处理长度惩罚。

### Q11 — 参考回答要点

- **结构**：Encoder RNN 读入源序列，最终隐状态作为上下文向量；Decoder RNN 以它为初始状态，每步输入上一个 token，输出目标词表上的分布，直到 `<EOS>`。
- **训练**：每个 decoder 步的交叉熵求和，BPTT 同时穿过两个网络；用 teacher forcing 稳定训练。
- **推理**：贪心或 beam search 逐 token 生成。
- **最大缺陷**：上下文向量瓶颈——整个源句压缩进一个定长向量，长句丢细节、罕见词模糊、语序调整只能靠记忆。讲义的复制任务实验中，长度 5 时 98%，长度 40 时降到 23%。
- **attention 的解法**：decoder 每一步都对**全部** encoder `outputs` 计算相关性权重，加权求和得到该步专属的上下文向量；信息不再被一个向量独占，长度不再是硬瓶颈（第 10 节）。
- **加分点**：现代 BART/T5/NLLB 的"encoder + decoder + 逐 token 生成"外形与 2014 年完全一致，只是块内从 RNN 换成了 self-attention + cross-attention。

### Q12 — 参考回答要点

- **teacher forcing**：训练时 decoder 输入真实的上一个 token；好处是稳定、可并行（Transformer 中整个目标序列一次前向）。
- **exposure bias**：推理时输入是模型自己的预测，一旦出错，就进入训练中从未见过的状态，错误累积；讲义技能卡提示其表现为"长输出上的生成漂移"。
- **缓解**（讲义三条）：
  1. scheduled sampling：teacher forcing 比例从 1.0 退火到约 0.5；
  2. 最小风险训练：以句子级 BLEU 等序列指标为目标，而不是 token 级交叉熵；
  3. RL 微调：用序列级指标作奖励，现代 LLM 的 RLHF 就是这一思路的延续。
- **在 LLM 中**：预训练和 SFT 本质上都是 teacher forcing（next-token prediction 喂真值前缀），所以 exposure bias 依然存在；讲义原话："All three still apply to transformer-based generation."
- **常见误区**：认为 beam search 能解决 exposure bias——它只是推理时的搜索策略。

### Q13 — 参考回答要点

- **长度归一化**：序列得分是 log 概率之和，每多一个 token 就多加一个负数，beam search 天然偏爱短序列（过早输出 `<EOS>`）。常见做法是用 `score / length^α`（α 为可调超参，α=0 即不归一化）做长度惩罚/归一化。
- **`<EOS>` 处理**：生成 `<EOS>` 的假设移入已完成列表、不再扩展；当已完成的假设足够多或者活跃假设的最好得分已不可能超过已完成的最好得分时停止。
- **beam 宽度**：讲义建议 3–5（技能卡说翻译/摘要用 4–5）。更宽的 beam 计算量线性增加，收益递减，而且在 NMT 中实践上常观察到过宽反而让译文变短、质量下降。
- **为什么开放式对话不用 beam**：beam search 追求高概率，输出偏平淡、易重复；对话/创作要多样性，用温度采样、top-p 等。讲义技能卡：贪心用于确定性输出，beam 用于质量，带温度的采样用于多样性；面向用户的内容用贪心会"重复和循环"，属于脆弱设计。
- **加分点**：beam search 和第 07 节 Viterbi 的关系——Viterbi 在 HMM 的有限状态上做精确 DP；seq2seq 的状态是连续隐向量、无法合并，只能用 beam 做近似剪枝。

### Q14 — 参考回答要点

- **架构**：预训练 Transformer encoder-decoder 是默认选择（讲义技能卡）；5 万对远低于"从零训练 seq2seq 需要百万级平行数据"的门槛，所以**微调**而不是从零训练。
- **checkpoint**：英文 query 可用 `facebook/bart-base` 或 `google/flan-t5-base`；中文或多语言选对应语言覆盖的模型——要让 checkpoint 匹配任务和语言。
- **数据**：清洗噪声对，去掉"改写 = 原文"的样本或单独保留一部分（教模型"无需改写"）；按 query 去重划分训练/验证集，防止泄漏。
- **解码**：线上用 beam 4 求稳定质量；需要多个候选做召回时用 `num_return_sequences` 或采样生成多样改写。
- **上线前检查**：按讲义技能卡，取 90 分位长度的 20 条输出肉眼检查 exposure bias 导致的漂移；离线看 BLEU/ROUGE + 线上 A/B（召回率、点击率）。
- **常见误区**：直接用未经任务微调的 `bart-base`——它是去噪自编码预训练模型，不经微调通常只会大致"复述"输入，不会按你的意图改写或翻译。

### Q15 — 参考回答要点

- **反转源句**（Sutskever 等 2014）：把源句倒序输入，源句开头的词离 decoder 开始生成的位置最近，引入大量短距离依赖，梯度更容易传播。本节模拟的 Q9(c) 从另一个角度展示了"编码器记得结尾"这一不对称性。
- **双向编码器**：前向 + 后向 RNN 拼接，句首信息也能出现在最终表示中（第 08 节）。
- **更大的隐状态、更深的 LSTM**：增加容量，但定长本质不变；把本节 `main.py` 的 `context_dim` 从 8 改成 64 实测，短序列（长度 5）升到 100%，长度 40 时仍只有 50% 左右——因为瓶颈不仅在维度，还在"逐步遗忘"。
- **每步都把上下文向量喂给 decoder**（Cho et al. 2014 的做法），避免它在 decoder 内部被逐渐冲淡。
- **结论**：这些都是缓解；真正的解法是让 decoder 随时访问所有 encoder 状态——attention（Bahdanau et al. 2014）。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 08 文本的 CNNs 和 RNNs](../../08-cnns-rnns-for-text/docs/zh.md)：GRU/LSTM、梯度消失、"定长上下文向量"问题的预告。
- [阶段 03 · 11 PyTorch 入门](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：`nn.Module`、`nn.GRU`、`CrossEntropyLoss` 的用法。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：逐步交叉熵。

### 本节被哪些后续内容用到
- [阶段 05 · 10 Attention 机制](../../10-attention-mechanism/docs/zh.md)：直接解决本节的上下文向量瓶颈。
- [阶段 05 · 11 机器翻译](../../11-machine-translation/docs/zh.md)：seq2seq 最经典的应用，BLEU/chrF 评估。
- [阶段 05 · 12 文本摘要](../../12-text-summarization/docs/zh.md)：抽象式摘要就是 seq2seq（BART/PEGASUS）。
- [阶段 05 · 16 Transformers 之前的文本生成](../../16-text-generation-pre-transformer/docs/zh.md)：自回归生成与解码策略。
- [阶段 07 · 08 T5、BART 与 encoder-decoder](../../../07-transformers-deep-dive/08-t5-bart-encoder-decoder/docs/zh.md)：本节架构的 Transformer 版本。
- [阶段 10 · 07 RLHF](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)：用序列级奖励微调生成模型，exposure bias 缓解思路的延续。

### 延伸关键词
`BPTT` · `scheduled sampling` · `minimum risk training` · `长度惩罚 (length penalty)` · `nucleus / top-p 采样` · `反转源句 (source reversal)` · `Bahdanau attention` · `BART / T5 / mBART / NLLB` · `HF generate(num_beams=…)`
