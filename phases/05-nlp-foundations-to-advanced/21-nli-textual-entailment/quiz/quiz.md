# 测验 · 自然语言 Inference — 文本蕴涵（Natural Language Inference — Textual Entailment）

> **阶段 05 · NLP 从基础到进阶 · 第 21 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过 `main.py` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | NLI 任务定义 | 给定前提 `t` 和假设 `h`，三分类：entailment（蕴涵）/ contradiction（矛盾）/ neutral（中立） |
| 2 | "自然"而非"逻辑" | 以典型人类读者的推断为准："John walked his dog" 蕴涵 "John has a dog"，严格一阶逻辑却需要额外公理 |
| 3 | 一个任务，三种生产用途 | 幻觉检测（源文档 vs 摘要论断）、Grounded QA（检索段落 vs 答案）、零样本分类（文档 vs "This is about {label}"） |
| 4 | 数据集 | SNLI（57 万，图片描述做前提）、MultiNLI（43.3 万，10 种体裁，事实上的标准训练集）、ANLI（对抗构造）、DocNLI/ConTRoL（文档级前提） |
| 5 | 模型结构 | Transformer encoder 读 `[CLS] premise [SEP] hypothesis [SEP]`，`[CLS]` 表示接 3 分类 softmax |
| 6 | 零样本分类 | 把每个候选标签写成假设，取蕴涵概率最高的；HF `zero-shot-classification` pipeline 的原理 |
| 7 | RAG faithfulness | 把答案拆成原子论断，逐条用 NLI 检查是否被检索上下文蕴涵，报告蕴涵比例（RAGAS faithfulness 的核心） |
| 8 | 捷径与偏差 | hypothesis-only 捷径（否定词与矛盾相关）、词汇重叠/子序列启发式在 HANS/ANLI 上失效 |
| 9 | 长度与领域 | 句子级模型在文档级前提上掉 20+ F1；法律/医学/科学需要领域 NLI 模型 |

### 核心技能（能动手做到）

- [ ] 读懂并复现一个"词汇重叠 + 否定检测"的玩具 NLI 分类器，能手算任意句对的 overlap 和预测标签
- [ ] 能构造让词汇重叠启发式失败的对抗样本（语序互换、子序列、双重否定、同义改写）
- [ ] 能实现 hypothesis-only baseline，并用它判断一个 NLI 数据集是否存在标注捷径
- [ ] 能实现"拆论断 → 逐条 NLI → 蕴涵比例"的 faithfulness 打分函数，并说出它会漏掉哪类幻觉
- [ ] 能用 HF `pipeline("zero-shot-classification")` 做零样本分类，并对 `hypothesis_template` 做 A/B 对比
- [ ] 能为"幻觉检测 / 零样本分类 / 文档级推断 / 多语言"选出讲义推荐的 NLI checkpoint，并给出阈值与评估方案

---

## 二、基础自测（选择题）

**Q1.** 前提："The cat is on the mat."，假设："The cat is hungry."。正确的 NLI 标签是：

- A. entailment
- B. contradiction
- C. neutral
- D. 无法定义，因为 NLI 只处理逻辑命题

**Q2.** 讲义强调 NLI 是"natural"而非严格逻辑推断。下列哪个例子最能体现这一点？

- A. "The cat is on the mat" 矛盾于 "There is no cat"
- B. "John walked his dog" 蕴涵 "John has a dog"
- C. "The cat is on the mat" 与 "The cat is hungry" 中立
- D. "Birds were singing" 与 "The room was silent" 中立

**Q3.** 用 NLI 模型做零样本主题分类，正确的做法是：

- A. 把文档和所有标签拼成一个长句，让模型直接输出标签名
- B. 把每个候选标签写成假设（如 "This text is about sports."），分别计算蕴涵概率，取最大者
- C. 计算文档与标签名的余弦相似度
- D. 先在少量标注数据上微调 NLI 模型

**Q4.** 用 NLI 检查 RAG 答案的 faithfulness 时，前提和假设分别应该是：

- A. 前提 = 用户问题，假设 = 生成答案
- B. 前提 = 生成答案，假设 = 检索上下文
- C. 前提 = 检索上下文，假设 = 从答案中拆出的每条原子论断
- D. 前提 = 用户问题，假设 = 检索上下文

**Q5.** 研究发现，在 SNLI 上只看假设、完全不看前提，也能达到远高于随机的准确率。这说明：

- A. 前提信息对 NLI 没有用
- B. 数据集存在标注捷径（如 "not"、"nobody"、"never" 与 contradiction 强相关），模型可能没真正学会推理
- C. SNLI 的标签是随机生成的
- D. 应该只用假设训练 NLI 模型以提高效率

**Q6.** 一个在 MNLI 上准确率 90%+ 的模型，在 HANS 上大面积失败。HANS 主要考察的是：

- A. 多语言能力
- B. 文档级长前提
- C. 模型是否依赖"词汇重叠/子序列即蕴涵"之类的启发式
- D. 领域迁移到医学文本

**Q7.** 你要判断一份 20 页合同是否蕴涵"乙方有权单方解约"。直接把整份合同和这句话喂给一个只在句子级 MNLI 上训练的模型，最主要的风险是：

- A. 模型会输出四个标签
- B. 句子级模型在文档长度前提上性能明显下降（讲义：掉 20+ F1），且法律领域与 MNLI 分布不匹配
- C. tokenizer 无法处理中文
- D. 没有风险，NLI 与长度无关

---

## 三、动手 / 代码题

**Q8.** 阅读 `main.py` 的 `predict_nli`，不运行代码，预测下列 4 个句对的输出标签（以及 overlap 值），并指出哪些是错的、错在哪里。

```python
def predict_nli(premise, hypothesis):
    p_tokens = tokenize(premise)
    h_tokens = tokenize(hypothesis)

    overlap = lexical_overlap(p_tokens, h_tokens)
    p_neg = has_negation(p_tokens)
    h_neg = has_negation(h_tokens)

    if overlap >= 0.5 and p_neg != h_neg:
        return "contradiction", overlap
    if overlap >= 0.5:
        return "entailment", overlap
    if overlap > 0 and p_neg != h_neg:
        return "contradiction", overlap
    return "neutral", overlap
```

| # | premise | hypothesis |
|---|---------|-----------|
| a | The doctor saw the lawyer. | The lawyer saw the doctor. |
| b | The doctor near the actor danced. | The actor danced. |
| c | The cat is on the mat. | The cat is hungry. |
| d | The movie was not bad. | The movie was not good. |

（提示：`STOP` 包含 `the`、`is`、`was`、`on` 等；`NEGATIONS` 包含 `not`。）

**Q9.** `main.py` 在 12 个例子上准确率 10/12（83.3%）。请实现一个 **hypothesis-only baseline**：只看假设，含否定词就预测 `contradiction`，否则预测 `entailment`。它在同样 12 个例子上的准确率是多少？这个结果说明了什么？

**Q10.** 两个错例之一是 `("The stock market rallied today.", "Stocks went up today.")`，预测为 neutral（overlap 0.25）。

1. 解释为什么 overlap 只有 0.25。
2. 在 `content_words` 之后加一个极简的词形归一化（去掉词尾 `s`，只对长度大于 3 的词生效），写出修改，并说明准确率会变成多少、哪个例子仍然错、为什么。
3. 为什么不能把这个归一化放在 `tokenize` 里、在过滤停用词之前做？

**Q11.** 讲义 Step 3 描述了 RAGAS 风格的 faithfulness：把答案拆成原子论断，逐条检查是否被上下文蕴涵，报告蕴涵比例。请复用 `predict_nli` 写 `faithfulness(answer, context)`（按句号拆分论断即可），并用下面的上下文测试三个答案。哪个答案的得分暴露了词汇重叠方法的致命缺陷？

```python
ctx = "The Eiffel Tower is in Paris. It was completed in 1889."
answers = [
    "The Eiffel Tower is in Paris. It was completed in 1889. It is the tallest building in Europe.",
    "The Eiffel Tower was completed in 1989.",
    "The Eiffel Tower is not in Paris.",
]
```

---

## 四、面试高频题

**Q12.**（基础必考）什么是 NLI？三个标签分别是什么含义？主流模型是怎么实现的？

**Q13.**（原理深挖）HF 的 `zero-shot-classification` 是怎么用 NLI 模型做分类的？它有哪些局限？什么时候应该换成微调分类器或 LLM？

**Q14.**（工程实践）如何用 NLI 给 RAG 系统做幻觉/faithfulness 检测？请说明流程、阈值怎么定、有哪些已知盲区。

**Q15.**（追问型）一个 NLI 模型在 MNLI 上 90%+，上线后在业务数据上却经常把"词都对得上但意思相反"的句子判为蕴涵。可能的原因是什么？你会怎么诊断和缓解？

**Q16.**（场景设计）你有 10,000 篇新闻、没有任何标签，需要在两天内按主题分类上线。请设计方案，并说明怎样证明它"能用"。

---

## 五、参考答案与解析

### Q1 — 答案：C

前提只说猫在垫子上，既不能推出猫饿了，也不能推出猫不饿，所以是 neutral。这是讲义 "The Concept" 里的原例。D 错：NLI 本来就处理自然语言，不要求逻辑命题形式。

### Q2 — 答案：B

"遛狗"推出"有狗"依赖常识（遛的是自己的狗），在严格一阶逻辑中需要把"拥有关系"公理化才能成立；NLI 以典型读者的推断为准，直接判为 entailment。A、C、D 都是常规例子，不涉及"自然推断 vs 逻辑推断"的差异。

### Q3 — 答案：B

零样本分类把标签"语言化"为假设，对每个标签跑一次 NLI，取蕴涵概率最大的标签。不需要训练数据、不需要微调（D 错）。A 不是 NLI 的输入形式；C 是 embedding 相似度方法，不是 NLI。

### Q4 — 答案：C

faithfulness 问的是"答案是否被上下文支持"，所以上下文是前提、答案论断是假设。拆成原子论断是因为一个答案往往同时包含正确和错误的信息，整体判断会被稀释。B 把方向弄反了：蕴涵关系不对称。

### Q5 — 答案：B

这是著名的 hypothesis-only 现象：标注者写矛盾句时倾向于加否定词，写蕴涵句时倾向于概括，导致假设本身就"泄露"了标签。讲义把它作为检测标签泄漏的强 baseline。它不说明前提没用（A），只说明数据有偏差。

### Q6 — 答案：C

HANS 专门构造"词全部重叠但不蕴涵"的样本（如语序互换、子序列），检验模型是否依赖词汇重叠/子序列启发式。讲义："The subsequence heuristic passes SNLI but fails HANS/ANLI."

### Q7 — 答案：B

两个问题叠加：①长度——句子级模型在文档级前提上会掉 20+ F1，且编码器有输入长度上限；②领域——MNLI 是通用英语，法律文本需要领域模型。讲义的 skill 也明确要求"拒绝在文档长度前提上使用句子级 NLI 模型"。

### Q8 — 参考答案

| # | 内容词（前提 → 假设） | overlap | 否定 | 预测 | 正确标签 | 对错 |
|---|---|---|---|---|---|---|
| a | {doctor, saw, lawyer} → [lawyer, saw, doctor] | 1.00 | 无 / 无 | entailment | neutral | ✘ |
| b | {doctor, near, actor, danced} → [actor, danced] | 1.00 | 无 / 无 | entailment | neutral（跳舞的是医生） | ✘ |
| c | {cat, mat} → [cat, hungry] | 0.50 | 无 / 无 | entailment | neutral | ✘ |
| d | {movie, bad} → [movie, good] | 0.50 | 有 / 有 | entailment | 至少不是 entailment | ✘ |

错误分析：
- a、b 正是讲义说的 **词汇重叠 / 子序列启发式**：集合重叠忽略了语序和句法角色（谁对谁做了什么），也就是 HANS 构造的陷阱。
- c 连讲义自己的 neutral 示例都判错了：一半的内容词重叠就被当成蕴涵，阈值 0.5 太粗。
- d 两边都有否定，`p_neg != h_neg` 为 False，否定检测失效；而 `bad`/`good` 的反义关系完全不在模型视野里。
- 相反，讲义练习里的 `("I did not eat the cake.", "I ate the cake.")` 会被判为 contradiction（overlap 0.5，否定不一致）——这个陷阱恰好被否定规则接住了。

### Q9 — 参考答案

```python
def hypothesis_only(hypothesis):
    return "contradiction" if has_negation(tokenize(hypothesis)) else "entailment"

acc = sum(hypothesis_only(h) == gold for _, h, gold in examples)
print(acc, "/", len(examples))   # 9 / 12
```

结果是 **9/12 = 75%**：4 个矛盾样本的假设全部含否定词（no、no、not、never），5 个蕴涵样本都不含否定词，全部猜对；只有 3 个 neutral 猜错。

说明：
1. 这个小数据集本身就有讲义说的**标注捷径**——否定词几乎等价于 contradiction。
2. 完整模型的 83.3% 只比"不看前提"的 75% 高 8.3 个点，大部分准确率来自捷径而非"推理"。
3. 工程启示：评估任何 NLI 模型/数据集前，先跑 hypothesis-only baseline；它越高，说明测试集越不能反映真实推理能力，需要补充对抗子集（ANLI、HANS 风格样本）。这也正是讲义 skill 中 "Evaluation: hypothesis-only baseline, adversarial subset" 的用意。

### Q10 — 参考答案

1. 假设的内容词为 `stocks, went, up, today`（4 个），前提内容词为 `{stock, market, rallied, today}`。只有 `today` 精确匹配：`stocks ≠ stock`（单复数），`went up` 与 `rallied` 是同义改写。overlap = 1/4 = 0.25 < 0.5，又无否定 → neutral。

2. 修改：

```python
def normalize(t):
    return t[:-1] if t.endswith("s") and len(t) > 3 else t

def content_words(tokens):
    return [normalize(t) for t in tokens if t not in STOP and t not in NEGATIONS]
```

此时假设变为 `stock, went, up, today`，overlap = 2/4 = 0.5 → entailment，修复成功。其余例子标签不变，准确率变为 **11/12**。仍然错的是 `("The chef served a tasty meal.", "The chef prepared food.")`：`served/prepared`、`meal/food` 是语义相关而非词形变化，只有 `chef` 匹配（1/3）。这类改写只有 embedding 或 transformer 模型才能捕捉。

3. 因为停用词表是按原形写的：即使有"长度大于 3"的限制，`does` 也会变成 `doe`、`this` 变成 `thi`；如果去掉长度限制，`was → wa`、`has → ha` 也会出现。这些变形后的词不在 `STOP` 里，过滤失效，功能词混进内容词，overlap 被拉偏。先过滤再归一化，才能保证停用词表仍然有效。（`is → i` 恰好仍在 `STOP` 里，只是巧合。）

### Q11 — 参考答案

```python
import re
from main import predict_nli

def split_claims(answer):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]

def faithfulness(answer, context):
    claims = split_claims(answer)
    if not claims:
        return 0.0, []
    results = [(c, predict_nli(context, c)[0]) for c in claims]
    score = sum(1 for _, lab in results if lab == "entailment") / len(claims)
    return score, results
```

实测结果：

| 答案 | 逐条判定 | 得分 |
|---|---|---|
| 1 | in Paris → entailment；completed in 1889 → entailment；tallest building in Europe → neutral | 0.67 |
| 2 | completed in **1989** → entailment | **1.00** |
| 3 | is **not** in Paris → contradiction | 0.00 |

答案 2 暴露了致命缺陷：`1989` 与 `1889` 只差一个数字，但 `eiffel, tower, completed` 都重叠（3/4 = 0.75），被判为蕴涵，faithfulness 满分。**数字、日期、实体替换类的幻觉**恰恰是 RAG 中最常见、危害最大的幻觉，词汇重叠完全检测不到。真实系统要用 DeBERTa 等 NLI 模型，并对数字/实体做专门校验。

另外注意：上下文作为一个整体当前提，所以第二句 `It was completed in 1889.` 中的代词 `It` 能借助同一前提中的 "Eiffel Tower" 被理解；如果按句切分上下文再逐句比对，就会丢失这种跨句信息（参见第 24 节共指消解）。

### Q12 — 参考回答要点

- **定义**：给定前提 t 和假设 h，判断典型人类读者读完 t 后会认为 h 为真（entailment）、为假（contradiction）还是无法判断（neutral）。旧称 RTE（Recognizing Textual Entailment）。
- **"自然"**：以常识推断为准而非形式逻辑。
- **实现**：cross-encoder 结构——BERT/RoBERTa/DeBERTa 读入 `[CLS] premise [SEP] hypothesis [SEP]`，`[CLS]` 向量接三分类 softmax，用交叉熵在 MNLI 等数据上训练；讲义称 DeBERTa-v3 是 2026 年的主力，在 MNLI-matched 上约 91%。
- **数据**：SNLI、MultiNLI、ANLI、DocNLI。
- 加分点：说出 NLI 是"不对称"的（t 蕴涵 h 不代表 h 蕴涵 t）；能讲出三大生产用途（幻觉检测、grounded QA、零样本分类）。

### Q13 — 参考回答要点

- **机制**：对每个候选标签构造假设（模板默认形如 "This example is …"，可通过 `hypothesis_template` 自定义），文档作前提，跑 N 次 NLI，取蕴涵概率最大的标签；多标签场景可对每个标签独立判断蕴涵是否超过阈值。
- **局限**：
  1. **模板敏感**：讲义指出模板不同，准确率能差 10 个点以上，需要在小验证集上调。
  2. **成本随标签数线性增长**：N 个标签就是 N 次 cross-encoder 前向。
  3. **领域/长度不匹配**：长文档、专业领域效果下降。
  4. **标签语义模糊**："politics" 与 "economy" 等标签边界不清时容易混淆。
- **何时换方案**：有几百条以上标注数据、标签稳定 → 微调小分类器更准更便宜；标签需要复杂说明或推理 → LLM；标签非常多 → 先 embedding 召回候选再用 NLI 精排。
- 加分点：讲义 skill 要求"没有 100 条标注样本做 sanity check 就不上线零样本分类"。

### Q14 — 参考回答要点

- **流程**：①把答案拆成原子论断（可以用 LLM 或规则）；②每条论断作假设、检索上下文作前提跑 NLI；③统计被蕴涵论断的比例作为 faithfulness；④对不被蕴涵的论断标红或触发重新生成。
- **阈值**：讲义示例用蕴涵概率 > 0.5，生产中应在人工标注的小集合上画 PR 曲线，按"漏报幻觉 vs 误杀正确答案"的业务代价选阈值，并关注模型校准。
- **盲区**：
  - 上下文太长 → 句子级模型退化；需要分段取最大蕴涵或用 DocNLI 类模型。
  - 数字、日期、实体替换等细粒度错误（见 Q11）。
  - 论断拆分质量直接决定结果；代词指代不清会导致误判（需要共指消解）。
  - NLI 只检查"是否被上下文支持"，不检查上下文本身是否正确、检索是否召回完整。
- **常见误区**：认为 NLI 能"消除"幻觉。讲义 skill 原话：它能减少幻觉，不能消除。需要配合检索召回指标和人工抽检。

### Q15 — 参考回答要点

- **原因**：模型学到了数据集捷径——词汇重叠 ≈ 蕴涵、否定词 ≈ 矛盾。MNLI 测试集与训练集有同样的偏差，所以分数高；业务数据中"词对得上但语序/角色/数字不同"的句子就会被误判。这正是 HANS、ANLI 揭示的问题。
- **诊断**：
  1. 跑 hypothesis-only baseline，看数据是否有泄漏；
  2. 构造对抗子集：语序互换、子序列、双重否定、数字替换、反义词；
  3. 按错误类型做混淆矩阵分析。
- **缓解**：
  - 换用在 ANLI、WANLI、LingNLI 等更难数据上训练过的 checkpoint（讲义推荐 `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`）；
  - 用业务数据中的困难样本继续微调；
  - 对数字/实体等关键字段加规则校验。
- 加分点：提到"高 in-distribution 准确率 ≠ 学会了推理"，评估必须包含对抗子集。

### Q16 — 参考回答要点

1. **定标签与模板**：和业务方确定 5–15 个互斥主题；为每个主题写清晰的自然语言假设；准备 2–3 个模板候选（如 "This text is about {label}." / "The topic is {label}." / "{label}"）。
2. **快速标注 sanity set**：人工标 100–200 条（讲义 skill 的下限是 100 条），用来选模板、选模型、定阈值。
3. **模型**：讲义选型表——轻量零样本用 `facebook/bart-large-mnli`，通用 NLI 用 `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`，多语言用 `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli`。
4. **处理长文**：新闻通常取标题 + 导语即可，避免长前提退化。
5. **"其他"类**：最高蕴涵概率低于阈值时归入"其他/待人工"，不强行分类。
6. **证明能用**：在 sanity set 上报告准确率/宏 F1 与每类混淆矩阵；抽检低置信样本；上线后持续收集人工纠正，积累到几百条后训练一个专用分类器替换零样本方案（更快更准）。
- 加分点：说明 N 个标签意味着 N 次前向，1 万篇 × 10 标签 = 10 万次 cross-encoder 推理，要估算 GPU 时间；可以先用 embedding 粗筛候选标签。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 05 情绪分析](../../05-sentiment-analysis/docs/zh.md)：文本分类的基本流程。
- [阶段 05 · 13 问答系统](../../13-question-answering/docs/zh.md)：检索段落 + 答案生成，NLI 用来验证答案是否有据可依。
- [阶段 07 · 06 BERT 与掩码语言建模](../../../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/zh.md)：`[CLS] A [SEP] B [SEP]` 句对输入格式的来源。

### 本节被哪些后续内容用到
- [阶段 05 · 12 文本摘要](../../12-text-summarization/docs/zh.md)：摘要幻觉检测是 NLI 的典型应用。
- [阶段 05 · 22 Embedding 模型深度剖析](../../22-embedding-models-deep-dive/docs/zh.md)：NLI 数据曾是训练句向量模型的重要监督来源；cross-encoder 与 bi-encoder 的对比。
- [阶段 05 · 24 共指消解](../../24-coreference-resolution/docs/zh.md)：拆论断前先消解代词，faithfulness 判断才可靠。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../27-llm-evaluation-frameworks/docs/zh.md)：faithfulness 指标内部的 NLI 层。
- [阶段 19 · 66 Cross-Encoder 重排序](../../../19-capstone-projects/66-reranker-cross-encoder/docs/zh.md)：与 NLI 相同的句对 cross-encoder 结构。
- [阶段 19 · 68 RAG 评估：Precision/Recall](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md)：在 RAG 项目中落地评估。

### 延伸关键词
`RTE` · `SNLI / MultiNLI / ANLI / WANLI` · `HANS` · `hypothesis-only bias` · `annotation artifacts` · `cross-encoder` · `DeBERTa-v3` · `zero-shot-classification` · `hypothesis_template` · `RAGAS faithfulness` · `SummaC` · `DocNLI`
