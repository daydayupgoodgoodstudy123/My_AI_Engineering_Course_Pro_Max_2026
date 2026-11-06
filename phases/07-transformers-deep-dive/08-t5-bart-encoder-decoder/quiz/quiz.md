# 测验 · T5、BART——Encoder-Decoder 模型（T5, BART — Encoder-Decoder Models）

> **阶段 07 · Transformers 深入 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Encoder-decoder 的分工 | 双向 encoder 把源序列编码成 `(N_src, d_model)`；因果 decoder 自回归生成输出，每步通过 cross-attention 读取 encoder 输出 |
| 2 | Cross-attention | Q 来自 decoder，K/V 来自 encoder 输出；这是 encoder 信息进入 decoder 的**唯一**通道 |
| 3 | Encoder 只跑一次 | 生成过程中 encoder 输出不变，可缓存；输入越长，这个"免费加速"越明显 |
| 4 | 训练目标 | 输出侧 shift-by-one，和 GPT 同一个 loss，只是额外以 encoder 输出为条件（teacher forcing） |
| 5 | T5 span corruption | 随机选约 15% 的 token、平均 span 长度 3，用 `<extra_id_N>` 哨兵替换；decoder 只输出被遮住的 span（带哨兵前缀） |
| 6 | BART 多噪声去噪 | token masking / deletion / text infilling / sentence permutation / document rotation；decoder 总是重建**完整**原文，预训练算力比 T5 高 |
| 7 | Text-to-Text 统一框架 | T5 把任务名写进输入文本（如 `translate English to French: ...`），一个模型、一个词表、一个 loss 处理所有任务；Flan-T5 在 1800+ 任务上指令微调 |
| 8 | 解码 | 与 GPT 相同的自回归生成；翻译/摘要输出分布较窄，beam search（宽度 4–5）是标准做法 |
| 9 | 2026 年的选型 | 输入模态与输出不同（语音、图像）或 beam 质量重要时用 encoder-decoder（Whisper、翻译）；对话/推理/代码补全用 decoder-only |

### 核心技能（能动手做到）

- [ ] 从零实现 T5 风格的 `corrupt_spans`，输出 `(corrupted_source, decoder_target)`，并用 `round_trip` 验证可逆
- [ ] 手写一个 span corruption 样例：给定原句和被遮住的位置，写出正确的 source 与 target（包括结尾的收尾哨兵）
- [ ] 实现 BART 的 5 种噪声函数中的至少 3 种，并能说出 text infilling 与 token masking 的区别
- [ ] 画出 encoder-decoder 的前向数据流，标出 cross-attention 中 Q、K、V 的来源和形状
- [ ] 能用 Hugging Face `T5ForConditionalGeneration` + 任务前缀完成一次翻译推理
- [ ] 给定一个新任务（翻译、语音转写、聊天、结构化抽取），能论证选 encoder-decoder 还是 decoder-only

---

## 二、基础自测（选择题）

**Q1.** 在 encoder-decoder 的 cross-attention 中，Q、K、V 分别来自：

- A. Q、K、V 都来自 encoder 输出
- B. Q 来自 encoder 输出，K、V 来自 decoder 隐状态
- C. Q 来自 decoder 隐状态，K、V 来自 encoder 输出
- D. Q、K、V 都来自 decoder 隐状态，只是使用了不同的掩码

**Q2.** 用一个 encoder-decoder 模型把一句 200 token 的英文翻译成 50 token 的法文。生成期间 encoder 需要前向计算几次？

- A. 1 次
- B. 50 次
- C. 200 次
- D. 250 次

**Q3.** 原句为 `The quick brown fox jumps over the lazy dog`，T5 span corruption 把 `brown` 和 `over the lazy` 两个 span 遮住。正确的 source / target 是：

- A. source：`The quick <extra_id_0> fox jumps <extra_id_1> dog`；target：`<extra_id_0> brown <extra_id_1> over the lazy`
- B. source：`The quick <mask> fox jumps <mask> <mask> <mask> dog`；target：完整原句
- C. source：`The quick <extra_id_0> fox jumps <extra_id_1> dog`；target：`The quick brown fox jumps over the lazy dog`
- D. source：完整原句；target：`brown over the lazy`

**Q4.** 关于 T5 与 BART 预训练目标的对比，下列说法**正确**的是：

- A. T5 的 decoder 要重建完整原文，BART 只输出被遮住的片段
- B. BART 的 decoder 总是重建完整原文，所以输出更长、预训练计算量比 T5 更高
- C. 两者都只使用 token masking 一种噪声
- D. BART 是 encoder-only 模型，T5 是 decoder-only 模型

**Q5.** BART 的 text infilling 与普通 token masking 的关键区别是：

- A. text infilling 只遮单个 token
- B. text infilling 用**一个** `<mask>` 替换一整个 span，decoder 还必须推断出这个 span 有多长
- C. text infilling 会把句子顺序打乱
- D. text infilling 直接删除 token，不留任何占位符

**Q6.** 按讲义的判断，下列哪个任务在 2026 年**最典型**地仍然使用 encoder-decoder？

- A. 多轮聊天助手
- B. 代码补全
- C. 语音转文字（如 Whisper）
- D. 数学推理

**Q7.** 讲义总结了 ~2022 年以来 decoder-only 接管原本属于 encoder-decoder 的任务的原因。下列哪一项**不是**讲义给出的原因？

- A. 指令微调后的 decoder-only LLM 可以通过 prompt 泛化到几乎任何任务
- B. 一种架构比两种架构更容易扩规模
- C. RLHF 默认假设的是 decoder
- D. encoder-decoder 模型无法使用 beam search

**Q8.** 为什么 beam search 在翻译、摘要中是标准做法，而在开放式聊天中很少用？

- A. beam search 只能用于 encoder-decoder 模型
- B. 翻译/摘要的输出分布较窄、"正确答案"相对集中，beam 能找到更高概率的整体序列；开放式聊天需要多样性，beam 容易产出平淡、重复的文本
- C. beam search 比 greedy 更快
- D. 聊天模型没有 logits，无法做 beam search

---

## 三、动手 / 代码题

**Q9.** 阅读 `corrupt_spans` 开头两行：

```python
n_mask = max(1, int(round(n * mask_rate)))
n_spans = max(1, int(round(n_mask / mean_span)))
```

(1) 对讲义练习 1 中的 30 个 token 的句子，用默认参数 `mask_rate=0.15, mean_span=3.0`，`n_mask` 和 `n_spans` 分别是多少？（提示：注意 Python 的 `round`。）(2) 对 `main()` 中 25 个 token 的句子、`mask_rate=0.20`，又分别是多少？

**Q10.** `main()` 的实际输出如下（25 个 token，`mask_rate=0.20`）：

```text
corrupted source:
  the quick <extra_id_0> fox jumps over the lazy dog a <extra_id_1> time saves nine language models ...
decoder target:
  <extra_id_0> brown <extra_id_1> stitch in <extra_id_2>
```

(1) 目标是遮 5 个 token，为什么实际只遮了 3 个？请指出代码中导致"实际遮盖率经常低于 `mask_rate`"的两个原因。(2) target 末尾的 `<extra_id_2>` 有什么作用？`round_trip` 里是怎么处理它的？

**Q11.** 讲义说 encoder-decoder"训练时输出侧做 shift-by-one，loss 与 GPT 相同"。请写一个函数 `make_decoder_io(target, start_token="<pad>")`，把 `corrupt_spans` 返回的 `target` 转成 decoder 的输入 `decoder_input` 和监督标签 `labels`（teacher forcing），并用 Q10 的 target 举例说明。

---

## 四、面试高频题

**Q12.**（基础必考）对比 encoder-only（BERT）、decoder-only（GPT）、encoder-decoder（T5/BART）三种架构：注意力掩码、训练目标、典型任务分别是什么？

**Q13.**（原理深挖）详细描述 encoder-decoder 一次生成的计算过程。cross-attention 的计算复杂度是多少？推理时哪些东西可以缓存？

**Q14.**（原理深挖）比较 BERT 的 MLM、T5 的 span corruption、BART 的去噪目标：输入怎么破坏、decoder/输出头预测什么、计算开销如何？

**Q15.**（场景设计）你要做三个产品：①会议录音转写；②英译中的批量文档翻译；③企业内部多轮知识问答助手。分别选什么架构、什么解码策略、什么评测指标？

**Q16.**（追问型）T5 的"把任务名写进输入"和今天 decoder-only 模型的指令微调是什么关系？Flan-T5 证明了什么？

---

## 五、参考答案与解析

### Q1 — 答案：C

Cross-attention 的语义是"decoder 当前在生成的位置（Q）去源序列里查找（K）并读取（V）相关信息"。所以 Q 来自 decoder 的隐状态，K、V 由 encoder 输出经过各自的投影得到。讲义 Key Terms："Decoder's Q × encoder's K/V. The only place encoder information enters the decoder." D 描述的是 decoder 的 masked self-attention。

### Q2 — 答案：A

源序列是固定的，encoder 只需要跑一次，得到 `(200, d_model)` 的表示；decoder 自回归跑 50 步，每一步都 cross-attend 到**同一份** encoder 输出。这就是讲义说的"缓存 encoder 输出是长输入的免费加速"。

### Q3 — 答案：A

T5 约定：每个被遮的 span 在 source 中替换为一个**唯一**哨兵（`<extra_id_0>`、`<extra_id_1>`…），target 只包含"哨兵 + 被遮内容"的交错序列。B 是 BART/BERT 风格的逐 token 掩码；C 的 target 是完整原句，那是 BART 的做法；D 丢了哨兵，decoder 无法知道每段内容属于哪个位置。补充：本节代码（和 T5 原始实现）还会在 target 末尾再追加一个收尾哨兵，如 `<extra_id_2>`。

### Q4 — 答案：B

讲义原文："BART's output is the full sequence, not just the corrupted spans — so pretraining compute is higher than T5." A 恰好说反了；C 错，BART 尝试了五种噪声，最好的是 text infilling + sentence permutation 组合；D 错，二者都是 encoder-decoder。

### Q5 — 答案：B

token masking 是一个 token 换一个 `<mask>`，被遮的长度是已知的；text infilling 把一整个 span 换成**单个** `<mask>`，模型还必须学会"这里缺了几个 token"。本节代码 `text_infill` 的输出 `<mask> brown fox <mask> the lazy ...` 就是两个 2-token 的 span 各被换成一个 `<mask>`。D 描述的是 token deletion；C 是 sentence permutation。

### Q6 — 答案：C

讲义的选型表中，"Speech-to-text: Yes (Whisper)"——输入模态（音频）与输出（文本）不同，由 encoder 专门处理音频特征最自然。聊天/推理是 decoder-only（对话本身就是序列，没有持久"输入"）；代码补全"Usually no"，长上下文的 decoder-only 胜出。

### Q7 — 答案：D

讲义给出的三个原因是 (a) 指令微调的 decoder-only 能通过 prompt 泛化、(b) 一种架构比两种更易扩展、(c) RLHF 假设 decoder。D 是错的：encoder-decoder 的 decoder 同样是自回归的，beam search 正是翻译/摘要中的标准解码方式。

### Q8 — 答案：B

讲义："Beam search (width 4–5) is standard for translation and summarization because the output distribution is narrower than chat." beam 在多条候选里保留整体对数概率最高的前 k 条，对"答案相对唯一"的任务能找到比 greedy 更好的整体序列；但开放式生成中"概率最高的序列"往往是平淡、重复的文本，所以聊天更常用 temperature + top-p/min-p 采样。A、D 都是事实错误；C 错，beam 每步要扩展 k 条候选，比 greedy 更慢。

### Q9 — 参考答案

(1) `30 * 0.15 = 4.5`，而 Python 3 的 `round` 采用**银行家舍入**（四舍六入五取偶），`round(4.5) = 4`，所以 `n_mask = 4`；`n_spans = round(4 / 3) = round(1.33) = 1`。也就是说这个 30 token 的句子只会遮**一个** span。

(2) `25 * 0.20 = 5.0`，`n_mask = 5`；`n_spans = round(5 / 3) = round(1.67) = 2`。

注意讲义 Build It 片段里写的是 `int(n * mask_rate)`（向下取整），而实际代码是 `int(round(n * mask_rate))`；两者在 `n * mask_rate` 小数部分 ≥ 0.5 时结果不同（例如 n=25、rate=0.15：`int(3.75)=3`，`round(3.75)=4`）。

### Q10 — 参考答案

(1) 实际遮盖了 `brown`（1 个）和 `stitch in`（2 个）共 3 个 token。原因：

- **span 个数是固定的**：`n_spans = 2` 在开始就算好了，循环最多选 2 个 span；而每个 span 的长度是独立随机的，2 个 span 加起来不一定能凑满 `n_mask = 5`。剩余的 `remaining` 不会再开新 span。
- **长度采样有向下偏差**：`length = max(1, int(rng.gauss(mean_span, 1.0)))`，`int()` 是向零截断，`int(2.9) = 2`，所以实际平均 span 长度约 2.5，而不是 3。此外 `min(length, remaining, n - start)` 也只会把长度往小截。

在这个 25 token 的句子上用 2000 个不同随机种子统计，平均只遮 4.36 个 token（目标 5 个）。修正方法：①用 `round` 或者按 T5 原始实现的方式先确定总遮盖数，再把它随机划分到各 span；②循环条件改为"直到 `remaining == 0` 或没有可用位置"。

(2) 末尾的 `<extra_id_2>` 是**收尾哨兵**（代码注释 `# closing sentinel`），标记"最后一个 span 到此结束"。`round_trip` 解析 target 时，每遇到一个新哨兵才把**上一个**哨兵收集到的 span 写入字典 `spans`；正因为有收尾哨兵，`<extra_id_1>` 后面的 `stitch in` 才会被写入。收尾哨兵本身之后没有内容，循环结束时也不会被写入（代码注释：`Last sentinel in target has no following span`）。如果去掉收尾哨兵，最后一个 span 会丢失，重建会失败。

### Q11 — 参考答案

```python
def make_decoder_io(target, start_token="<pad>"):
    """Teacher forcing: decoder 输入是右移一位的 target，标签是 target 本身。"""
    decoder_input = [start_token] + target[:-1]
    labels = list(target)
    return decoder_input, labels


target = ["<extra_id_0>", "brown", "<extra_id_1>", "stitch", "in", "<extra_id_2>"]
dec_in, labels = make_decoder_io(target)
for x, y in zip(dec_in, labels):
    print(f"{x:>14} -> {y}")
```

输出：

```text
         <pad> -> <extra_id_0>
  <extra_id_0> -> brown
         brown -> <extra_id_1>
  <extra_id_1> -> stitch
        stitch -> in
            in -> <extra_id_2>
```

解释：decoder 在位置 i 看到的是"起始符 + 真实 target 的前 i 个 token"（teacher forcing），要预测 target 的第 i 个 token；配合 decoder 的因果掩码，一次前向就得到所有位置的预测，loss 与 GPT 完全相同，只是每一层多了 cross-attention 读取 encoder 输出。Hugging Face 的 T5 正是用 pad token 作为 decoder 起始符，传入 `labels` 时模型内部会自动做这个右移（`_shift_right`）。真实训练中 target 末尾还会加 EOS。

### Q12 — 参考回答要点

| 架构 | 注意力掩码 | 训练目标 | 典型任务 |
|------|-----------|---------|---------|
| Encoder-only（BERT） | 双向，无因果掩码 | MLM：预测被遮的 token | 分类、NER、检索 embedding |
| Decoder-only（GPT） | 因果掩码 | next-token prediction | 生成、对话、代码、推理 |
| Encoder-decoder（T5/BART） | encoder 双向；decoder 因果 + cross-attention | 以 encoder 输出为条件的 next-token（span corruption / 去噪预训练） | 翻译、摘要、语音转写 |

- 加分点：说明 encoder-decoder 的源序列部分是双向编码的，对"先完整读入再输出"的任务表示更充分；decoder-only 用一个序列同时承载输入和输出，结构更简单、更容易扩展。
- 常见误区：认为 encoder-only 也能直接生成——它没有定义自回归生成过程（配套 skill 也明确拒绝为生成任务推荐 encoder-only）。

### Q13 — 参考回答要点

- **流程**：①源 token → encoder（N 层双向 self-attention + FFN）→ `(N_src, d_model)`，只算一次；②decoder 从起始符开始，每层依次做 masked self-attention → cross-attention（Q 来自 decoder，K/V 来自 encoder 输出）→ FFN；③最后一层投影到词表得到 logits，采样/beam 得到下一个 token，追加后重复。
- **复杂度**：cross-attention 的分数矩阵是 `N_tgt × N_src`，计算量 O(N_tgt · N_src · d)；decoder 自注意力是 O(N_tgt² · d)；encoder 自注意力是 O(N_src² · d)。
- **可缓存**：①encoder 输出（整个生成期间不变）；②每层 cross-attention 的 K、V（由 encoder 输出投影得到，只需算一次）；③decoder self-attention 的 KV cache（随生成增长，见第 12 节）。
- **加分点**：指出长输入、短输出的任务（摘要、转写）中，encoder 一次性并行编码长输入、decoder 只生成短输出，这种"不对称"正是 encoder-decoder 的效率优势来源。

### Q14 — 参考回答要点

| 目标 | 输入如何破坏 | 预测什么 | 开销 |
|------|------------|---------|------|
| BERT MLM | 约 15% token 换成 `[MASK]`（逐 token） | 只在被遮位置预测原 token（encoder 输出头） | 只有被遮位置有 loss |
| T5 span corruption | 约 15% token，按平均长 3 的 span 换成唯一哨兵 | decoder 只输出"哨兵 + span 内容" | target 很短，讲义称"cheaper signal"；T5 论文消融中与 MLM、prefix-LM 相当 |
| BART 去噪 | masking / deletion / infilling / 句子打乱 / 文档旋转，可组合 | decoder 重建**完整**原文 | target 与原文等长，开销更高 |

- 加分点：解释 span 比单 token 更难——模型要恢复连续多个 token，更接近生成任务；text infilling 还要预测 span 长度。BART 论文中 text infilling + sentence permutation 组合最好。
- 常见误区：把 T5 的哨兵当成和 `[MASK]` 一样的"同一个特殊符号"——T5 每个 span 用不同编号的哨兵，才能在 target 里把内容对应回位置。

### Q15 — 参考回答要点

| 产品 | 架构 | 解码 | 指标 |
|------|------|------|------|
| ①会议录音转写 | encoder-decoder（Whisper 类），以 Whisper 为必须超越的基线 | 低温度 / beam | WER |
| ②批量英译中 | encoder-decoder（或强 decoder-only LLM 对比） | beam search 宽度 4–5 + 长度惩罚 | BLEU（可补充人工评估） |
| ③多轮知识问答 | decoder-only 指令模型（对话本身就是序列） | temperature + top-p/min-p | 任务相关：事实性、EM/F1 |

- 理由要点：语音输入模态不同，encoder 专门处理音频特征；翻译有明确源序列、输出分布窄，beam 有效；对话没有"固定输入"，配套 skill 明确拒绝在输入已经是对话时推荐 encoder-decoder。
- 加分点：主动给出测试集规模、延迟预算；提到 ①② 是批处理任务，可以用较大 beam 换质量，③ 是在线任务，要控制首 token 延迟。

### Q16 — 参考回答要点

- **T5 的做法**：任务名作为文本前缀（`translate English to French: ...`、`summarize: ...`），所有任务都是"文本进、文本出"，单一架构、单一词表、单一 loss。
- **与指令微调的关系**：任务前缀就是最早期、最格式化的"指令"。今天的 decoder-only 指令模型把它推广为自然语言的 system prompt / 用户指令，讲义原话：T5 先把这个模式固定了下来，2026 年它已被指令微调的 decoder-only 模型推广。
- **Flan-T5**：在 1800 多个任务上做指令微调，使 encoder-decoder 在指令遵循上也有竞争力，说明"多任务指令化"本身是关键，而不只取决于架构。
- **加分点**：指出 T5 的 text-to-text 让分类、回归（把数字写成文本）、抽取都能复用同一个生成 loss，这一思想直接影响了后来的 prompt-based 统一建模。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 05 完整的 Transformer](../../05-full-transformer/docs/zh.md)：原始 2017 encoder-decoder 结构与 cross-attention。
- [阶段 07 · 06 BERT——掩码语言建模](../../06-bert-masked-language-modeling/docs/zh.md)：MLM 目标，与 span corruption 对比。
- [阶段 07 · 07 GPT — 因果语言建模](../../07-gpt-causal-language-modeling/docs/zh.md)：shift-by-one loss 与解码策略，decoder 侧完全复用。
- [阶段 05 · 09 序列到序列](../../../05-nlp-foundations-to-advanced/09-sequence-to-sequence/docs/zh.md)：RNN 时代的 seq2seq 与 teacher forcing。

### 本节被哪些后续内容用到
- [阶段 07 · 10 音频 Transformers — Whisper 架构](../../10-audio-transformers-whisper/docs/zh.md)：2026 年最典型的 encoder-decoder。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../12-kv-cache-flash-attention/docs/zh.md)：decoder self-attention 与 cross-attention 的缓存。
- [阶段 05 · 11 机器翻译](../../../05-nlp-foundations-to-advanced/11-machine-translation/docs/zh.md)：beam search 与 BLEU。
- [阶段 05 · 12 文本摘要](../../../05-nlp-foundations-to-advanced/12-text-summarization/docs/zh.md)：BART / PEGASUS 的主战场与 ROUGE。
- [阶段 06 · 05 Whisper 架构与微调](../../../06-speech-and-audio/05-whisper-architecture-finetuning/docs/zh.md)：encoder-decoder 在语音上的工程实践。
- [阶段 10 · 06 指令微调 SFT](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：从 T5 任务前缀到通用指令微调。

### 延伸关键词
`PEGASUS (gap sentence)` · `UL2 / mixture of denoisers` · `prefix-LM` · `relative position bias (T5)` · `length penalty` · `mT5 / mBART` · `decoder_start_token_id`
