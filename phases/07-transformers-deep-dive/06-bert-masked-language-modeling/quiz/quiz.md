# 测验 · BERT——掩码语言建模（BERT — Masked Language Modeling）

> **阶段 07 · Transformers 深入 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | MLM vs 因果 LM | GPT 预测下一个词，BERT 预测被遮住的词；BERT 的 encoder 没有因果 mask，预测时能同时利用左右两侧的上下文 |
| 2 | 15% 选中 | 每个（非特殊）token 以 15% 的概率被选为预测目标，只有这些位置计算 loss |
| 3 | 80/10/10 规则 | 选中的 token：80% 换成 `[MASK]`，10% 换成随机 token，10% 保持不变 |
| 4 | 为什么不全用 `[MASK]` | `[MASK]` 在微调和推理时从不出现；随机/不变两种情况迫使模型对**每个**位置都保持良好的表示，减小预训练与微调的分布差异 |
| 5 | `labels = -100` | PyTorch `CrossEntropyLoss` 的默认 `ignore_index`；未被选中的位置不参与 loss |
| 6 | 特殊 token 不遮 | `[CLS]`、`[SEP]` 等结构性 token 不参与 MLM 选择 |
| 7 | Whole-word masking | 一个词被切成多个 subword 时，要么整词一起遮，要么都不遮，避免靠同一个词的其他碎片"猜"答案 |
| 8 | NSP 被放弃 | 原始 BERT 还训练"下一句预测"；RoBERTa 的消融实验表明去掉它不会更差，之后的编码器基本不再使用 |
| 9 | `[CLS]` / `[SEP]` 与下游用法 | `[CLS]` 的最终向量作句子表示接分类头；`[SEP]` 分隔句对；cross-encoder 把 query 与 doc 拼成一个输入打分 |
| 10 | 2026 年的 encoder | ModernBERT（2024）：RoPE、GeGLU、局部(128)/全局交替注意力、8192 上下文、BPE 分词；仍是分类、检索 embedding、NER、NLI、reranker 的首选 |

### 核心技能（能动手做到）

- [ ] 实现 `create_mlm_batch`，并用 10 万个 token 的统计验证 15% / 80% / 10% / 10% 的比例
- [ ] 解释 `labels` 中 `-100` 的作用，并写出只在有效位置上求平均的交叉熵
- [ ] 找出 `create_mlm_batch` 中随机替换的 `while` 循环在什么词表条件下会死循环，并修复
- [ ] 实现 whole-word masking，读懂 `whole_word_mlm` 演示中 `P / .` 标记的含义
- [ ] 说出 BERT 与 GPT 在注意力 mask、训练目标、下游用法上的区别
- [ ] 为分类 / NER / 检索 / 重排任务分别设计 BERT 的任务头和微调方案

---

## 二、基础自测（选择题）

**Q1.** 对 1000 个普通 token 应用 `mask_prob = 0.15` 的 BERT 掩码，**期望**情况下：被选中的位置数、换成 `[MASK]` 的数量、换成随机 token 的数量、保持不变的数量分别是：

- A. 150、150、0、0
- B. 150、120、15、15
- C. 120、96、12、12
- D. 1000、800、100、100

**Q2.** BERT 不把所有选中的 token 都换成 `[MASK]`，主要原因是：

- A. 换成 `[MASK]` 的计算更慢
- B. `[MASK]` 在微调和推理时从不出现，全用 `[MASK]` 会造成预训练和微调之间的分布偏移；随机和不变两种情况让模型不能只在 `[MASK]` 处"认真工作"
- C. 为了让词表更小
- D. 为了配合 NSP 任务

**Q3.** 关于 `labels` 和 loss，下列说法正确的是：

- A. 所有位置都计算 loss，未选中位置的 label 是原 token
- B. 被选中但"保持不变"的 10% 位置，label 为 `-100`，不计算 loss
- C. 只有被选中的约 15% 位置有 label（包括换成 `[MASK]`、随机、不变三种），其余位置为 `-100`，被 `CrossEntropyLoss` 忽略
- D. 只有被换成 `[MASK]` 的位置计算 loss

**Q4.** BERT 不适合直接用来做开放式文本生成，最根本的原因是：

- A. 参数量太小
- B. 它的 attention 是双向的、训练目标是"已知两侧预测中间"，没有"只根据左侧预测下一个 token"的自回归机制
- C. 它的词表里没有标点符号
- D. 它只能处理英文

**Q5.** 关于 Next Sentence Prediction（NSP），正确的是：

- A. NSP 是 BERT 效果好的主要原因，所有后续模型都保留了它
- B. RoBERTa 的消融实验表明去掉 NSP 不会损害下游效果，之后的编码器基本不再使用 NSP
- C. NSP 用来预测下一个 token
- D. NSP 和 MLM 是同一个任务

**Q6.** 关于 ModernBERT（2024）相对原始 BERT 的改动，下列描述正确的是：

- A. 仍使用可学习的绝对位置 embedding，最大长度 512
- B. 改用 RoPE、GeGLU、局部（窗口 128）与全局交替的注意力，上下文扩展到 8192
- C. 改成了 decoder-only 结构，可以直接生成文本
- D. 重新引入了 NSP 任务

**Q7.** 在 RAG 中，关于 bi-encoder（双塔）和 cross-encoder（交叉编码器），正确的是：

- A. cross-encoder 可以离线为所有文档预先计算向量，所以适合做第一阶段召回
- B. cross-encoder 把 `[CLS] query [SEP] doc [SEP]` 一起输入，query 和 doc 之间有完整的双向注意力，精度更高但每个 (query, doc) 对都要跑一次，通常用于对少量候选重排
- C. bi-encoder 比 cross-encoder 精度更高
- D. 两者都必须使用 decoder-only 模型

---

## 三、动手 / 代码题

**Q8.** 阅读 `create_mlm_batch` 的核心部分：

```python
    for i, t in enumerate(tokens):
        if t in SPECIAL_IDS:
            continue
        if rng.random() >= mask_prob:
            continue
        labels[i] = t
        r = rng.random()
        if r < 0.8:
            input_ids[i] = MASK_ID
        elif r < 0.9:
            rand_id = t
            while rand_id in SPECIAL_IDS or rand_id == t:
                rand_id = rng.randrange(vocab_size)
            input_ids[i] = rand_id
    return input_ids, labels
```

(a) `rand_id = t` 这一行初始化为什么要写成 `t`，而不是 `None` 或 0？
(b) 这个 `while` 循环保证了随机替换的 token 满足什么条件？这与原始 BERT 的做法有什么细微差别？对统计结果有什么影响？
(c) 找出一个会让这段代码**永远不返回**的输入（提示：考虑 `vocab_size` 很小的情况），并给出修复方案。

**Q9.** 运行结果中有这样一段：

```text
=== 80/10/10 distribution over 100k random tokens ===
selected:                   15.03%   (target 15.0%)
  -> replaced with [MASK]:  79.80%   (target 80.0%)
  -> replaced with random:  10.15%   (target 10.0%)
  -> left unchanged:        10.04%   (target 10.0%)
```

(a) `distribution_check` 中 `randomized` 和 `unchanged` 的判定条件分别是什么？为什么"随机"可以用 `t != l` 来判断？
(b) 用 10 万个 token 估计"被选中比例"，标准误差大约是多少？15.03% 与 15% 的偏差算正常吗？
(c) 如果改成原始 BERT 的做法（随机 token 可能恰好等于原 token），用同样的判定条件统计，"random" 和 "unchanged" 两个比例会怎样变化？

**Q10.** `toy_predict` 返回的是一个对词表的**均匀分布**：

```python
def toy_predict(masked_inputs, vocab):
    V = len(vocab)
    return [[1.0 / V for _ in range(V)] for _ in masked_inputs]
```

请写一个纯 Python 函数 `mlm_cross_entropy(probs, labels)`：只在 `label != IGNORE_INDEX` 的位置计算 `-log p(label)` 并求平均。用主程序中的句子、`mask_prob=0.5, seed=42` 的掩码结果和 `toy_predict` 计算 loss，预测结果是多少？这个数字在训练中有什么参考意义？

---

## 四、面试高频题

**Q11.**（基础必考）BERT 和 GPT 的核心区别是什么？请从模型结构、注意力 mask、预训练目标、擅长的下游任务四个方面回答。

**Q12.**（原理深挖）MLM 的 80/10/10 规则是为了解决什么问题？MLM 这个训练目标本身有哪些缺点？后续工作（RoBERTa、Whole-word masking、ELECTRA 等）分别是怎么改进的？

**Q13.**（工程实践）如何用 BERT 做文本分类和 NER？微调时冻结 encoder 只训头、和全量微调有什么区别？给出一组典型的超参数。

**Q14.**（场景设计）设计一个 RAG 系统的"召回 + 重排"链路，bi-encoder 和 cross-encoder 分别用在哪里？为什么 cross-encoder 不能直接用来召回？

**Q15.**（追问型）"现在都 2026 年了，大模型什么都能做，还有必要用 BERT 类 encoder 吗？"请给出你的判断和理由。

---

## 五、参考答案与解析

### Q1 — 答案：B

选中 `1000 × 0.15 = 150` 个；其中 80% → 120 个 `[MASK]`，10% → 15 个随机，10% → 15 个不变。这 150 个位置都有 label。代码实测 10 万个 token：选中 15.03%，其中 `[MASK]` 79.80%、随机 10.15%、不变 10.04%。C 把 80% 误乘到了"选中数"上。

### Q2 — 答案：B

讲义："Because `[MASK]` never appears at inference time … would create a distribution shift between pretraining and fine-tuning." 如果模型只在看到 `[MASK]` 时才需要输出原词，它就可以对其他位置"偷懒"，学到的表示在没有 `[MASK]` 的下游输入上不够好。10% 不变让模型对"看起来正常"的位置也要给出正确预测；10% 随机让模型不能盲目相信当前位置的输入。

### Q3 — 答案：C

代码中只要被选中就写入 `labels[i] = t`，之后才决定替换方式，所以三种情况都有 label（B、D 错）。未被选中的位置为 `IGNORE_INDEX = -100`，PyTorch `CrossEntropyLoss` 的默认 `ignore_index` 正是 -100，这些位置不贡献 loss，也不进入平均的分母（A 错）。

### Q4 — 答案：B

BERT 的每个位置都能看到整个序列（包括右侧），训练目标是"填空"，不存在"给定前缀预测下一个 token"的概率分解，因此没有自然的自回归生成方式（讲义："The encoder has no sensible way to autoregressively produce tokens"）。配套 skill 也明确拒绝用 BERT 做生成任务，建议改用 decoder-only。

### Q5 — 答案：B

讲义："RoBERTa (2019) ablated it … Modern encoders skip it."（讲义原文说 NSP "hurt"；更稳妥的表述是 RoBERTa 发现去掉 NSP 后下游效果持平或略好。）C 描述的是因果语言建模；D 错：NSP 是句对级二分类，MLM 是 token 级预测。

### Q6 — 答案：B

ModernBERT 用 RoPE 替换可学习绝对位置、用 GeGLU 替换 GELU、每隔若干层使用全局注意力、其余层使用 128 窗口的局部注意力，上下文扩到 8192，并原生支持 Flash Attention、改用 BPE 分词器。它仍是 encoder-only 模型（C 错），也不使用 NSP（D 错）。补充：讲义表格写 ModernBERT 用"Pre-norm RMSNorm"，但 ModernBERT 论文原文是"a pre-normalization block with the standard layer normalization"并去掉了 LayerNorm 的 bias，即 pre-norm **LayerNorm**。

### Q7 — 答案：B

cross-encoder 必须把 query 和 doc 放在同一个输入里才能计算，无法离线预计算文档向量，所以不能用于对百万级文档的召回（A 错）；但正因为 query 和 doc 之间有完整的双向 attention，它的相关性判断比 bi-encoder（分别编码再算余弦）更准（C 错）。典型做法：bi-encoder 召回 top-k，cross-encoder 对这 k 个重排。两者都可以基于 BERT 类 encoder（D 错）。

### Q8 — 参考答案

(a) 写成 `rand_id = t` 是为了**保证 `while` 至少执行一次**：初始值本身就满足循环条件 `rand_id == t`，于是一定会去抽一个新值。Python 没有 `do … while` 语法，这是常见的模拟写法。

(b) 循环保证随机 token **既不是特殊 token，也不等于原 token**——所以这 10% 一定是"真的被换掉了"。原始 BERT（以及 HuggingFace 的 `DataCollatorForLanguageModeling`）是从整个词表均匀抽取，可能恰好抽到原 token。影响：在本代码中三类比例严格对应 80/10/10；而按原始做法统计，会有一小部分"随机"位置其实等于原词，被计入"不变"（见 Q9(c)）。

(c) 当词表中除了特殊 token 之外**只有一个**普通 token 时（例如 `vocab_size = 4`，id 0/1/2 是特殊 token，只剩 id 3），任何被选中走"随机"分支的 token 3 都找不到满足条件的替代值，`while` 永远不会结束。已验证：`create_mlm_batch([3] * 50, 4, mask_prob=1.0, rng=random.Random(0))` 在 5 秒超时内没有返回。修复：

```python
def random_replacement(t, vocab_size, rng):
    candidates = [v for v in range(vocab_size) if v not in SPECIAL_IDS and v != t]
    if not candidates:            # 没有可替换的 token，退化为"保持不变"
        return t
    return rng.choice(candidates)
```

或者在函数开头断言 `vocab_size - len(SPECIAL_IDS) >= 2`。真实词表有几万个 token，不会触发，但单元测试里用小词表时很容易踩到。`whole_word_mlm` 里有完全相同的循环，也需要一起修。

### Q9 — 参考答案

(a) 判定条件：
- `masked`：有 label 且输入为 `MASK_ID`；
- `randomized`：有 label、输入不是 `MASK_ID`、且输入 `!=` label；
- `unchanged`：有 label 且输入 `==` label。

能用 `t != l` 判断"随机"，前提是 Q8(b) 的保证——随机替换一定不等于原 token；同时 `distribution_check` 生成的 token 都在 `range(3, vocab_size)`，不会与 `MASK_ID` 混淆。

(b) "是否被选中"是成功概率 0.15 的伯努利试验，比例估计的标准误差为 `√(0.15 × 0.85 / 100000) ≈ 0.113%`。15.03% 与 15% 只差 0.03 个百分点，约 0.3 个标准误差，完全正常。同理，"[MASK] 占比"基于约 15,000 个样本，标准误差约 `√(0.8 × 0.2 / 15000) ≈ 0.33%`，79.80% 也在正常范围内。

(c) 随机 token 从 17 个普通 token 中均匀抽取时，有 1/17 的概率恰好等于原 token，按同样的判定条件会被计入"不变"。所以"random"会降到约 `10% × 16/17 ≈ 9.4%`，"unchanged"升到约 `10% + 10%/17 ≈ 10.6%`。用同一随机种子实测：random 9.44%、unchanged 10.79%（另有抽样波动）。真实词表很大（如 3 万），这个差别可以忽略。

### Q10 — 参考答案

```python
import math

def mlm_cross_entropy(probs, labels):
    total, n = 0.0, 0
    for p_row, lab in zip(probs, labels):
        if lab == IGNORE_INDEX:          # 未被选中的位置不参与
            continue
        total += -math.log(p_row[lab])
        n += 1
    return total / n if n else 0.0
```

结果：`ln(20) ≈ 2.9957`。均匀分布下每个位置 `p(label) = 1/20`，所以不论有几个有效位置，平均 loss 都是 `ln V`。

意义：这是"什么都没学到"的模型的 loss 基线（对应困惑度 `e^{loss} = V = 20`）。真实训练开始时，随机初始化的 MLM 头输出接近均匀，loss 应在 `ln V` 附近（BERT 的 30522 词表约为 10.3）；如果初始 loss 明显偏离这个值，往往说明标签、`ignore_index` 或输出层初始化有 bug。注意分母只数有效位置——若把 `-100` 位置也计入，loss 会被错误地稀释。

### Q11 — 参考回答要点

| 维度 | BERT | GPT |
|------|------|-----|
| 结构 | Transformer encoder 堆叠 | Transformer decoder（无 cross-attention） |
| 注意力 mask | 无因果 mask，双向 | 因果 mask，只看左侧 |
| 预训练目标 | MLM（+ 原始版本的 NSP） | 下一个 token 预测（CLM） |
| 训练信号密度 | 每个序列只有约 15% 位置有 loss | 每个位置都有 loss |
| 擅长任务 | 分类、NER、检索 embedding、NLI、重排 | 生成、对话、代码、推理，以及通过 prompt 完成理解类任务 |
| 输出用法 | `[CLS]` 或 mean-pool 向量接任务头；逐 token 表示做序列标注 | 自回归逐 token 采样 |

- **加分点**：指出两者的 block 骨架几乎相同（第 05 节），区别主要在 mask 和训练目标；"同一句话的差别"（讲义开头）。
- **常见误区**：说 BERT"不能处理长文本是因为双向"——长度限制来自位置编码与 O(N²) 成本，ModernBERT 已扩展到 8K。

### Q12 — 参考回答要点

- **80/10/10 解决的问题**：`[MASK]` 只在预训练出现，造成预训练—微调不一致；让模型在"未被替换"和"被随机替换"的位置也必须给出正确预测，从而对每个 token 都学到有用的上下文表示。
- **MLM 的缺点**：
  1. 训练信号稀疏：每个序列只有约 15% 位置贡献 loss，样本效率低于每个位置都有 loss 的 CLM；
  2. 预训练—微调仍有不一致（80% 的 `[MASK]`）；
  3. 同一序列中多个被遮的位置是**独立**预测的，忽略了它们之间的依赖；
  4. subword 级随机遮盖时，模型可以靠同一个词的其他碎片轻松猜出答案。
- **改进**：
  - RoBERTa：去掉 NSP、动态 masking（每个 epoch 重新随机遮盖）、更多数据和更大 batch；
  - Whole-word masking：整词一起遮（本节 `whole_word_mlm`），span masking 进一步遮连续片段；
  - ELECTRA：用小生成器替换部分 token，主模型对**每个**位置做"是否被替换"的判别（replaced-token detection），讲义引用其结论："beats MLM at matched compute"。
- **加分点**：提到 `labels = -100` 和 `ignore_index` 的工程实现细节。

### Q13 — 参考回答要点

- **文本分类**：取 `[CLS]` 位置的最终向量（或对所有 token 做 mean-pool）→ dropout → 线性层到类别数，交叉熵训练（配套 skill 的 head spec）。
- **NER**：对每个 token 的最终向量接一个线性层输出 BIO 标签，可选加 CRF；注意 subword 与词级标签的对齐（通常只用每个词的第一个 subword 计算 loss，其余设为 -100）。
- **冻结 vs 全量**：
  - 冻结 encoder 只训头（linear probing / 特征提取）：训练快、不易过拟合，适合数据极少或需要多个任务共享同一 backbone 的场景，但效果通常低于全量微调；
  - 全量微调：原始 BERT 论文的标准做法，所有参数一起以小学习率更新，效果最好。⚠️ 讲义 Step 4 写"Only the head trains; the encoder is frozen. This is the pattern every BERT application follows"，这并不准确——全量微调才是最常见的做法；配套 skill 中"<1,000 条标注数据时全量解冻可能过拟合"的提示也说明全量解冻是常态。
  - 折中：只解冻顶部几层，或用 LoRA 等参数高效方法。
- **典型超参**（配套 skill）：AdamW，学习率约 2e-5，warmup 6–10%，3–5 个 epoch，bf16/fp16。
- **加分点**：少数类低于 10% 时做分层评估；关注截断长度和分词器与预训练是否一致。

### Q14 — 参考回答要点

- **链路**：
  1. 离线：用 bi-encoder（如 sentence-transformers 类模型，"Embedding models are fine-tuned BERT"）把所有文档 chunk 编码成向量，建 ANN 索引；
  2. 在线召回：query 编码成向量，ANN 检索 top-k（如 100），可与 BM25 混合；
  3. 重排：cross-encoder 对 (query, chunk) 逐对打分，取 top-n（如 5）送给 LLM。
- **为什么 cross-encoder 不能召回**：它需要 query 与每个文档**一起**前向计算，百万文档意味着每个请求百万次前向，无法离线预计算；bi-encoder 的文档向量与 query 无关，可以预先算好，在线只需一次 query 编码和一次向量检索。
- **为什么 cross-encoder 更准**：query 和 doc 的每个 token 之间都有双向 attention（讲义："exactly what gives cross-encoders their quality edge over biencoders"），而 bi-encoder 把整篇文档压成一个向量，细粒度匹配信息会损失。
- **加分点**：给出延迟预算的估算方式（重排 k 个候选的成本 ≈ k 次 encoder 前向，可批处理）；提到 ColBERT 这类"后期交互"折中方案。

### Q15 — 参考回答要点

- **仍然有必要的场景**（讲义 "Use cases that still pick an encoder in 2026"）：
  - 检索 embedding：双向上下文，embedding 质量高，几乎所有检索栈的基础；
  - 高吞吐分类（情感、意图、内容审核）：一次前向出结果，没有生成开销，模型小、延迟和成本低，易于在 CPU 或边缘部署；
  - NER、token 级标注：天然逐位置输出；
  - NLI、cross-encoder 重排。
- **不该用的场景**：任何生成任务；以及讲义提到的情况——当一个小型 decoder 模型能以相近质量提供更大灵活性时（例如需要同时完成多种指令任务）。
- **判断框架**：看任务是否需要生成、延迟/成本约束、标注数据量、是否需要可预计算的向量。
- **加分点**：提到 ModernBERT 等新一代 encoder 把上下文扩展到 8K 并原生支持 Flash Attention，说明 encoder 路线仍在演进；以及"用 LLM 做标注、蒸馏到 BERT 类小模型上线"的常见工程模式。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 05 完整的 Transformer](../../05-full-transformer/docs/zh.md)：BERT 就是只取 encoder 那一半。
- [阶段 07 · 04 位置编码](../../04-positional-encoding/docs/zh.md)：原始 BERT 用可学习绝对位置，ModernBERT 改用 RoPE。
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../../05-nlp-foundations-to-advanced/02-bag-of-words-tfidf/docs/zh.md)：从稀疏表示到上下文表示的演进。
- [阶段 05 · 19 子词 Tokenization](../../../05-nlp-foundations-to-advanced/19-subword-tokenization/docs/zh.md)：WordPiece / BPE，理解 whole-word masking 的必要性。

### 本节被哪些后续内容用到
- [阶段 07 · 07 GPT — 因果语言建模](../../07-gpt-causal-language-modeling/docs/zh.md)：与 MLM 对照的另一种预训练目标。
- [阶段 07 · 08 T5、BART——Encoder-Decoder 模型](../../08-t5-bart-encoder-decoder/docs/zh.md)：span corruption、去噪自编码等 MLM 的推广。
- [阶段 05 · 22 Embedding 模型 — 2026 年深度剖析](../../../05-nlp-foundations-to-advanced/22-embedding-models-deep-dive/docs/zh.md)："Embedding models are fine-tuned BERT"。
- [阶段 05 · 06 命名实体识别](../../../05-nlp-foundations-to-advanced/06-named-entity-recognition/docs/zh.md)：BERT + token 分类头的典型应用。
- [阶段 11 · 07 Advanced RAG](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：cross-encoder 重排在 RAG 中的位置。
- [阶段 19 · 38 通过替换输出头进行分类器 Fine-Tuning](../../../19-capstone-projects/38-classifier-finetuning/docs/zh.md)：综合项目中的"换头微调"。

### 延伸关键词
`MLM` · `80/10/10` · `ignore_index=-100` · `whole-word masking` · `span masking` · `dynamic masking` · `ELECTRA (RTD)` · `[CLS] pooling / mean pooling` · `cross-encoder vs bi-encoder` · `ModernBERT` · `DeBERTa-v3`
