# 测验 · 机器翻译（Machine Translation）

> **阶段 05 · NLP 基础到进阶 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 2026 年的 MT 流水线 | 预训练多语言 Transformer encoder-decoder（NLLB-200 / mBART）+ SentencePiece 子词 + beam search + 自动评估 |
| 2 | 三个关键工程选择 | 分词器（跨语言共享词表支撑 NLLB 的零样本语言对）、模型规模（600M 蒸馏版 / 3.3B / 54.5B）、解码（beam 4–5、长度惩罚、术语约束解码） |
| 3 | NLLB 的语言控制 | `src_lang` 告诉 tokenizer 源语言；`forced_bos_token_id` 强制 decoder 第一个 token 为目标语言代码；mBART、M2M-100 约定不同、不能混用 |
| 4 | BLEU | 1–4 gram 的**截断（clipped）精确率**的几何平均 × 简短惩罚（brevity penalty），范围 [0, 100]；差距小于 1 分视为噪声 |
| 5 | chrF | 字符 n-gram 的 F 分数（β=2，偏重召回），对形态丰富的语言更敏感，常与 BLEU 一起报告 |
| 6 | 三层评估体系 | 启发式（BLEU、chrF）→ 学习型（COMET、BLEURT、BERTScore）→ LLM-as-judge（无参考）；上线至少用两类，并用 50–100 条人工标注校准 |
| 7 | 生产中的五种失败 | 幻觉、目标语言错误（off-target）、术语漂移、敬语/正式度不匹配、短输入长度爆炸 |
| 8 | 领域微调 | 几千条高质量平行语料胜过几十万条网页噪声数据；数据质量是最大的生产杠杆 |
| 9 | LLM 翻译 | 在若干语言对、习语和长上下文上已超过专用 MT 模型，代价是每 token 成本和延迟 |

### 核心技能（能动手做到）

- [ ] 从零实现带截断计数的 n-gram 精确率、简短惩罚和句级 BLEU，并手算一个例子
- [ ] 从零实现 chrF，说出本节实现与 sacrebleu 默认行为的至少两点差异（空白字符、缺失阶数的处理）
- [ ] 能解释为什么无平滑的句级 BLEU 经常为 0，并实现一种平滑方法、指出它在短句上的副作用
- [ ] 能区分句级平均 BLEU 与语料级（corpus）BLEU，并实现后者
- [ ] 能写出 NLLB 的调用代码（`src_lang`、`forced_bos_token_id`、`num_beams`），并给输出加上语言识别检查
- [ ] 能按讲义技能卡对一条译文给出"Ship / Ship with review / Do not ship"判断，并列出 5 项人工核查清单

---

## 二、基础自测（选择题）

**Q1.** 关于 BLEU，下列说法**错误**的是：

- A. 它基于 1–4 gram 的精确率，并取几何平均
- B. 译文比参考译文短时会受到简短惩罚（brevity penalty）
- C. 它同时计算 n-gram 召回率，所以过长的译文也会被惩罚
- D. 差距小于 1 BLEU 通常被视为噪声

**Q2.** 参考译文是 `the cat sat`，候选译文是 `the the the the`。按本节代码 `ngram_precision` 的**截断**规则，unigram 精确率是：

- A. 1.0
- B. 0.75
- C. 0.25
- D. 0.0

**Q3.** 使用 NLLB-200 把英文翻译成法文时，下列哪一组设置分工正确？

- A. `src_lang="fra_Latn"`，`forced_bos_token_id` 设为英文代码
- B. `src_lang="eng_Latn"` 告诉 tokenizer 源语言；`forced_bos_token_id` 设为 `fra_Latn` 的 token id，告诉 decoder 生成哪种语言
- C. 只需设置 `num_beams=5`，模型会自动识别目标语言
- D. 与 mBART 的设置方式完全相同，可以直接复用

**Q4.** chrF 中常用 `β = 2`。这意味着：

- A. 精确率的权重是召回率的 2 倍
- B. 召回率比精确率更受重视
- C. 只统计 2-gram
- D. 分数乘以 2

**Q5.** 下列评估方法中，**不需要参考译文**就能打分的是：

- A. BLEU
- B. chrF
- C. COMET-QE 或 LLM-as-judge
- D. 标准 COMET（带参考）

**Q6.** NLLB 在一个冷门语言对上偶尔把要求的法语输出成了西班牙语。讲义推荐的缓解措施是：

- A. 增大 beam 宽度
- B. 核对 `forced_bos_token_id`，并对每条输出做语言识别（language-ID）检查
- C. 换用 chrF 评估
- D. 增大长度惩罚

**Q7.** 新模型在测试集上 BLEU 32.9，旧模型 32.4。产品经理问"新模型是不是更好？"，最合理的回答是：

- A. 是，高了 0.5 分
- B. 差距小于 1 BLEU 基本是噪声，需要结合 chrF/COMET、显著性检验和人工评估再下结论
- C. 不是，BLEU 越低越好
- D. 只要用了 sacrebleu，0.5 分就一定显著

---

## 三、动手 / 代码题

**Q8.** 本节 `main.py` 的实际输出中，第二行是：

```text
hypothesis                                reference                    BLEU    chrF
Les chats sont en train de courir.        Les chats courent.            0.0    56.3
```

(a) 写出 `tokenize` 后的候选与参考 token 序列，计算 1–4 gram 的截断精确率，说明 `simple_bleu` 为什么返回 0.0。
(b) 实现一个"对 n ≥ 2 的精确率做加一平滑（分子分母各加 1）"的 `smoothed_bleu`，算出这一行的分数；再算 `"Les chiens mangent."`（意思完全错）的分数，你发现了什么问题？

**Q9.** 本节 `chrf` 的核心循环：

```python
    for k in range(1, n + 1):
        hyp_c = Counter(char_ngrams(hyp, k))
        ref_c = Counter(char_ngrams(ref, k))
        match = sum((hyp_c & ref_c).values())
        if sum(hyp_c.values()) == 0 or sum(ref_c.values()) == 0:
            continue
        precisions.append(match / sum(hyp_c.values()))
        recalls.append(match / sum(ref_c.values()))
```

(a) `hyp_c & ref_c` 计算的是什么？为什么它就是"截断后的匹配数"？
(b) 对候选 `"Les"`、参考 `"Les chats courent."`，哪些 k 被 `continue` 跳过？输出 14.0 是怎么来的？如果把被跳过的阶数按精确率、召回率都为 0 计入平均，分数会变成多少？哪种做法更合理？
(c) 这个实现的字符串里包含空格。这和 sacrebleu 中 chrF 的默认做法有什么不同？

**Q10.** 讲义说 "Always use `sacrebleu`"，而 sacrebleu 报告的是**语料级** BLEU。请实现 `corpus_bleu(hypotheses, references)`：先在所有句子上累加各阶截断匹配数、n-gram 总数以及候选/参考总长度，再统一计算精确率和简短惩罚。用本节 4 个 case 计算，并与"4 个句级 BLEU 的平均值"比较。

---

## 四、面试高频题

**Q11.**（基础必考）讲一下 BLEU 是怎么计算的。它有哪些缺陷？为什么论文里一定要用 sacrebleu？

**Q12.**（原理深挖）BLEU、chrF、COMET、LLM-as-judge 各自适合什么场景？如果只能选两个上线，你选哪两个，怎么保证它们可信？

**Q13.**（工程实践）你负责的翻译服务"80% 的时候很流畅，20% 的时候静默出错"。请列出你会监控的失败模式，以及每种的检测和缓解手段。

**Q14.**（场景设计）一家 SaaS 公司要把产品 UI 文案（约 5000 条字符串，含 `{name}` 等占位符）本地化成 20 种语言，预算有限。请给出模型选型、流水线和上线门槛。

**Q15.**（追问型）讲义给了一个用 `Trainer` 微调 NLLB 的片段。你能看出它有什么隐患吗？领域微调还要注意什么？

---

## 五、参考答案与解析

### Q1 — 答案：C

BLEU 只算**精确率**（候选中有多少 n-gram 出现在参考里），没有召回；对"太短"的惩罚靠简短惩罚 BP 实现，而过长的译文由于精确率下降会间接受损，但没有专门的召回项。A、B、D 都是讲义的描述。chrF 才是同时计算精确率和召回率的 F 分数。

### Q2 — 答案：C

候选有 4 个 `the`，参考里 `the` 只出现 1 次，截断后匹配数 = `min(4, 1) = 1`，精确率 = 1/4。代码中对应 `clipped += min(count, ref_counts.get(ngram, 0))`。如果不截断，"重复一个高频词"就能拿到 1.0 的精确率——这正是 BLEU 使用"修正（modified）精确率"的原因。

### Q3 — 答案：B

讲义原文："`src_lang` tells the tokenizer which script and segmentation to apply. `forced_bos_token_id` tells the decoder which language to generate." A 把方向弄反了；C 错，NLLB 不会自动推断目标语言；D 错，讲义强调 mBART、M2M-100 用各自的约定，不能互换。

### Q4 — 答案：B

F_β = `(1+β²)·P·R / (β²·P + R)`，β > 1 时召回率更重要（按 van Rijsbergen 的经典解释，F_β 对应"认为召回的重要性是精确率 β 倍"的用户，公式里体现为 β²）。直觉：翻译漏掉内容（低召回）通常比多说几个字符更严重。本节代码中 `beta=2` 就是这个设置；实测把 β 改为 1 后，第二个 case 从 56.3 降到 45.0（候选更长、精确率低，β 越大越宽容）。

### Q5 — 答案：C

BLEU、chrF 和标准 COMET 都需要参考译文。讲义："Reference-free metrics (COMET-QE, BLEURT-QE, LLM-as-judge) let you evaluate translations without a reference"，这对没有参考译文的长尾语言对尤其重要。

### Q6 — 答案：B

这是讲义的 off-target generation：NLLB 在冷门语言对上容易翻成错误的语言。缓解："verify `forced_bos_token_id` and always decode with a language-ID model check on output"。技能卡更明确："Refuse to ship a translation without a language-ID check on output." A、D 不能纠正目标语言；C 只是换个指标。

### Q7 — 答案：B

讲义："differences under 1 BLEU are noise"。正确做法：同时看 chrF/COMET，做配对 bootstrap 等显著性检验，并抽样人工评估。D 错：sacrebleu 只保证**可比性**（分词、参数统一），不保证差异显著。

### Q8 — 参考答案

(a) `tokenize` 把文本小写，并在 `.` 前加空格后切分：

```text
hyp = ['les', 'chats', 'sont', 'en', 'train', 'de', 'courir', '.']   # 8 个
ref = ['les', 'chats', 'courent', '.']                               # 4 个
```

- 1-gram：`les`、`chats`、`.` 命中，3/8 = 0.375
- 2-gram：只有 `(les, chats)` 命中，1/7 ≈ 0.143
- 3-gram：`(les, chats, sont)` 等都不在参考里，0/6 = 0
- 4-gram：0/5 = 0

`simple_bleu` 中 `if any(p == 0 for p in precisions): return 0.0`——几何平均里任何一项为 0，结果就是 0（`log(0)` 无定义，代码提前返回）。这正是 `simple_bleu_note()` 说的"无平滑时，一个零精确率就让分数归零"。简短惩罚为 1（候选更长）。

(b) 参考实现：

```python
import math
from collections import Counter

def smoothed_bleu(hypothesis, reference, max_n=4):
    hyp, ref = tokenize(hypothesis), tokenize(reference)
    log_sum = 0.0
    for n in range(1, max_n + 1):
        hyp_counts = Counter(ngrams(hyp, n))
        ref_counts = Counter(ngrams(ref, n))
        clipped = sum(min(c, ref_counts.get(g, 0)) for g, c in hyp_counts.items())
        total = sum(hyp_counts.values())
        if n > 1:                      # 加一平滑（只对 n >= 2）
            clipped, total = clipped + 1, total + 1
        if clipped == 0 or total == 0:
            return 0.0
        log_sum += math.log(clipped / total)
    bp = brevity_penalty(len(hyp), len(ref))
    return 100 * bp * math.exp(log_sum / max_n)
```

实测结果（复用 `main.py` 的 `tokenize`、`ngrams`、`brevity_penalty`）：

| 候选 | 无平滑 BLEU | 平滑 BLEU | chrF |
|------|-----------|----------|------|
| `Les chats sont en train de courir.`（意思正确的改写） | 0.0 | **21.7** | 56.3 |
| `Les chiens mangent.`（意思完全错） | 0.0 | **38.0** | 34.8 |

问题：平滑后，意思完全错误的句子反而比正确的改写得分更高。原因有二：①BLEU 只看表面 n-gram 重叠，对改写不敏感（讲义："insensitive to paraphrase"）；②加一平滑对短句影响极大——`Les chiens mangent .` 的 4-gram 只有 1 个，平滑后精确率变成 `(0+1)/(1+1) = 0.5`，相当于"白送"了分数。chrF 的排序反而正确。结论：句级 BLEU 很不可靠，平滑方法的选择也会显著改变数值，所以要用 sacrebleu 统一口径，并用 chrF/COMET 交叉验证。

### Q9 — 参考答案

(a) `Counter` 的 `&` 运算对每个键取**两边计数的最小值**（并丢弃 ≤ 0 的键），即 `min(hyp 中次数, ref 中次数)`——与 BLEU 的截断计数完全相同。`sum(...values())` 就是所有字符 n-gram 的截断匹配总数。

(b) 候选 `"les"` 只有 3 个字符，k = 4、5、6 时没有任何字符 n-gram，`sum(hyp_c.values()) == 0`，于是被 `continue` 跳过，只对 k = 1、2、3 取平均：
- k=1：候选 `l、e、s` 全部能在参考中找到，P = 1，R = 3/18
- k=2：`le`、`es` 都命中，P = 1，R = 2/17
- k=3：`les` 命中，P = 1，R = 1/16

平均 P = 1，平均 R ≈ 0.1156，`F₂ = 5·1·0.1156 / (4·1 + 0.1156) ≈ 0.140` → **14.0**。

若把 k = 4–6 按 P = R = 0 计入 6 阶平均，P = 0.5、R ≈ 0.0578，分数降为 **7.0**（已运行验证）。跳过缺失阶数会让极短的候选拿到"满分精确率"，从而**高估**短输出；对一个只翻译出一个词的输出来说，7.0 更符合直觉。不同实现对这一边界情况的处理不同，这也是"自己写指标容易得出不可比数字"的又一例证。

(c) 本实现直接对 `"les chats courent."` 这样含空格的字符串取字符 n-gram，空格也参与匹配。sacrebleu 的 chrF 默认会**去掉空白字符**再提取字符 n-gram（有参数可以选择保留）。实测去掉空格后，第二、三个 case 从 56.3 / 34.8 变为 50.0 / 30.0——数值不同，所以本节结果不能和论文中的 chrF 直接比较。

### Q10 — 参考答案

```python
import math
from collections import Counter

def corpus_bleu(hypotheses, references, max_n=4):
    clipped = [0] * max_n
    totals = [0] * max_n
    hyp_len = ref_len = 0
    for h, r in zip(hypotheses, references):
        ht, rt = tokenize(h), tokenize(r)
        hyp_len += len(ht)
        ref_len += len(rt)
        for n in range(1, max_n + 1):
            hc, rc = Counter(ngrams(ht, n)), Counter(ngrams(rt, n))
            clipped[n - 1] += sum(min(c, rc.get(g, 0)) for g, c in hc.items())
            totals[n - 1] += sum(hc.values())
    if min(clipped) == 0:
        return 0.0
    log_mean = sum(math.log(c / t) for c, t in zip(clipped, totals)) / max_n
    return 100 * brevity_penalty(hyp_len, ref_len) * math.exp(log_mean)
```

实测：4 个 case 的语料级 BLEU = **26.8**；4 个句级 BLEU 的平均值 = (100 + 0 + 0 + 0) / 4 = **25.0**。

区别：
- 句级平均中，任何一句只要某阶精确率为 0 就整句归零，"全对的一句"与"三句 0 分"简单平均；
- 语料级先汇总计数，第 1 句的 3-gram、4-gram 命中弥补了其他句子的空白，几何平均不会因为某一句缺某阶 n-gram 而归零；简短惩罚也按整个语料的总长度计算（这里候选总长 17 > 参考总长 16，BP = 1）。
- 这正是 BLEU 原本的设计：它是**语料级指标**，句级 BLEU 方差很大。sacrebleu 的 `corpus_bleu` 就是这种汇总方式。

### Q11 — 参考回答要点

- **计算**：
  1. 对 n = 1..4，计算截断精确率 `p_n = Σ min(count_hyp(g), count_ref(g)) / Σ count_hyp(g)`；多参考时取各参考中的最大计数；
  2. 几何平均 `exp(Σ log p_n / 4)`；
  3. 简短惩罚 `BP = 1`（c ≥ r）或 `exp(1 - r/c)`（c < r），c、r 为语料级候选/参考长度；
  4. `BLEU = 100 · BP · 几何平均`。
- **缺陷**：
  - 只看表面 n-gram，同义改写、语序合理变化都会被扣分；
  - 没有召回，只靠 BP 粗略约束长度；
  - 句级 BLEU 方差大、常为 0，需要平滑，而平滑方式会显著改变数值（Q8）；
  - 对分词、大小写、标点处理极其敏感。
- **为什么 sacrebleu**：它固定了分词和参数，并输出签名字符串说明配置，使不同论文/实验的分数可比（Post, 2018）；讲义："Rolling your own BLEU computation is how misleading benchmarks happen."
- **加分点**：能说出 30 可用、40 好、50 非常好（讲义的经验刻度），以及差距 < 1 是噪声。

### Q12 — 参考回答要点

- **BLEU / chrF（启发式）**：快、可解释、需要参考；适合回归检测和与历史结果对比。chrF 对形态丰富语言更友好。
- **COMET / BLEURT / BERTScore（学习型）**：在人工评分上训练，比较译文与源文、参考之间的语义；讲义称 COMET 是 2026 年质量优先场景的生产默认。
- **LLM-as-judge（无参考）**：按流畅度、充分性、语气、文化适配打分；适合没有参考的开放内容。讲义提到在 rubric 设计良好时与人工的一致率约 80%。
- **选两个**：通常 chrF（或 BLEU）+ COMET——一个廉价、稳定的回归指标，一个更贴近人类判断的语义指标；无参考场景用 COMET-QE + LLM-as-judge。
- **保证可信**：讲义要求每个指标都先用 50–100 条人工标注样本校准，看相关性和失败案例后再在生产数据上信任它。
- **常见误区**：只看 BLEU 做上线决策；把 LLM-as-judge 当成无需校准的真理。

### Q13 — 参考回答要点

| 失败模式 | 检测 | 缓解（讲义） |
|---------|------|-------------|
| 幻觉（编造源文没有的内容） | 输出长度远超输入、QE 分数低、实体对不上 | 领域术语约束解码；受监管内容人工审核 |
| Off-target（语言错误） | 对每条输出做语言识别 | 核对 `forced_bos_token_id`；语言不符直接拦截 |
| 术语漂移（"Sign up"时而"s'inscrire"时而"créer un compte"） | 用术语表比对 | 术语表约束解码或后编辑词典 |
| 正式度不匹配（tu/vous、日语敬语） | 规则或分类器检测敬语形式 | 支持的模型加正式度前缀；用正式语料微调小模型 |
| 短输入长度爆炸 | 输出/输入长度比异常 | 按源长度比例设置硬性最大长度 |

- **加分点**：按语言对、领域、长度分桶监控；超过 1000 token 的内容分块翻译（技能卡）；对 UI 文案，"一致性比原始质量更重要"。

### Q14 — 参考回答要点

- **选型**：
  - 主流欧洲语言（英→法/德/西）：Marian（Helsinki-NLP），便宜、快；
  - 20 种语言中包含长尾语言：NLLB-200（600M 蒸馏版做开发，3.3B 做生产）或 mBART-50；
  - 对少量高曝光文案（首页、付费墙）可以用 LLM 翻译，利用提示控制语气和术语，接受更高的单条成本。
- **流水线**：
  1. 预处理：把 `{name}` 等占位符替换为不可翻译的标记，翻译后还原并校验数量、顺序一致（技能卡：UI 要检查占位符变量）；
  2. 术语表：产品名、功能名用约束解码或后编辑词典固定；
  3. 解码：beam 4–5，最大长度按源长度比例截断；
  4. 后处理：语言识别检查、占位符校验、长度检查（UI 有像素宽度限制）。
- **评估与门槛**：每种语言抽 50–100 条做人工标注校准 COMET/chrF；按技能卡输出 Ship / Ship with review / Do not ship；没有语言识别检查不得上线。
- **常见误区**：只追求 BLEU；忽视术语一致性和正式度（面向客户的内容通常需要敬语/正式体）。

### Q15 — 参考回答要点

- **片段中的隐患**：
  1. `padding="max_length"` 在预处理阶段就把 labels 补齐到 128，补齐位置是 pad token id 而不是 `-100`；默认的数据整理不会替换它们，于是**模型在 padding 上也计算损失**。常见做法是把 labels 中的 pad id 替换为 `-100`，或改用动态 padding 并使用会把 label 填充为 `-100` 的 seq2seq 数据整理器。
  2. tokenizer 构造时只指定了 `src_lang`；用 `text_target` 编码目标句时，建议同时明确目标语言（例如构造 tokenizer 时传入 `tgt_lang`），保证 labels 带上正确的语言代码，与推理时的 `forced_bos_token_id` 一致。
  3. 示例只有 1 条数据、没有验证集，实际需要划分 held-out 集并在训练前后测 BLEU/chrF/COMET（讲义练习 3）。
- **领域微调还要注意**：
  - 数据质量 > 数量：讲义"几千条高质量胜过几十万条噪声"；做去重、对齐质量过滤、长度比过滤；
  - 学习率小（示例用 3e-5）、epoch 少，防止遗忘通用能力；在通用测试集上也要回归测试；
  - 报告"哪些句子变好、哪些变差"（讲义练习 3），而不只是一个平均分。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 10 Attention 机制](../../10-attention-mechanism/docs/zh.md)：decoder 通过 cross-attention 读取 encoder 输出。
- [阶段 05 · 04 GloVe、FastText 和 Subword Embeddings](../../04-glove-fasttext-subword/docs/zh.md)：子词是多语言共享词表的基础。
- [阶段 05 · 09 序列到序列模型](../../09-sequence-to-sequence/docs/zh.md)：encoder-decoder、beam search、exposure bias。

### 本节被哪些后续内容用到
- [阶段 05 · 12 文本摘要](../../12-text-summarization/docs/zh.md)：同为 seq2seq 生成任务，ROUGE 与 BLEU 是"召回版/精确版"的近亲。
- [阶段 05 · 18 多语言 NLP](../../18-multilingual-nlp/docs/zh.md)：跨语言迁移、低资源语言。
- [阶段 05 · 19 子词 Tokenization](../../19-subword-tokenization/docs/zh.md)：SentencePiece、BPE 的细节。
- [阶段 05 · 20 Structured Outputs & 约束解码](../../20-structured-outputs-constrained-decoding/docs/zh.md)：术语约束解码的通用形式。
- [阶段 05 · 27 LLM Evaluation](../../27-llm-evaluation-frameworks/docs/zh.md)：LLM-as-judge 的系统方法。
- [阶段 07 · 08 T5、BART 与 encoder-decoder](../../../07-transformers-deep-dive/08-t5-bart-encoder-decoder/docs/zh.md)：mBART / NLLB 的底层架构。
- [阶段 11 · 08 LoRA 微调](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：低成本做领域适配。

### 延伸关键词
`sacrebleu 签名` · `modified n-gram precision` · `chrF++` · `COMET / COMET-QE (Unbabel)` · `BLEURT` · `配对 bootstrap 显著性检验` · `fastText lid.176` · `术语约束解码 (lexically constrained decoding)` · `回译 (back-translation)` · `NLLB-200 / mBART-50 / Marian`
