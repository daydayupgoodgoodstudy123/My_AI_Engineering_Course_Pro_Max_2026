# 测验 · 问答系统（Question Answering Systems）

> **阶段 05 · NLP 从基础到进阶 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三种 QA 架构 | 抽取式（给定段落找答案 span）、开放域 / 检索增强（先检索再回答）、生成式 / 闭卷（LLM 凭参数记忆作答）；2026 年主流是三者混合 |
| 2 | 抽取式 QA 的建模方式 | 问题和段落一起送进 BERT 类编码器，两个 head 分别预测答案起点、终点 token 的位置，损失是对合法位置的交叉熵；输出必然是原文片段，所以"不会编造"，但也无法回答段落里没有的内容 |
| 3 | SQuAD 1.1 vs 2.0 | SQuAD 2.0 加入了**无法回答**的问题，模型要学会预测"无答案"（null）；HF `question-answering` pipeline 默认仍返回最高分 span，需要 `handle_impossible_answer=True` 才会返回空答案 |
| 4 | RAG = retriever + reader | 检索器找 top-k 段落，阅读器（抽取式或生成式）基于段落作答；两者可分别训练、分别评估，中间常加 reranker |
| 5 | 闭卷生成的幻觉规律 | 对常识表现好，对冷门 / 新近事实表现差；幻觉率与该事实在预训练语料中的出现频率**负相关** |
| 6 | 接地（grounding）提示词 | 明确要求"只依据上下文回答，不够就说 I don't know"，讲义称可比朴素提示降低 40–60% 的幻觉率 |
| 7 | EM 与 token F1 | EM：归一化（小写、去标点、去冠词）后完全相等才得 1；F1：按 token 重叠给部分分；两者都不理解语义，会低估改写（paraphrase） |
| 8 | 生产评估四件套 | 答案准确率（LLM / 人工评判）、引用准确率、拒答校准（false confidence rate）、**检索召回率**（reader 无法弥补没被检索到的段落） |
| 9 | RAGAS 四个维度 | Faithfulness（基于 NLI 蕴涵，主幻觉指标）、Answer relevance、Context precision、Context recall；无需人工标准答案，可直接跑在线上流量 |

### 核心技能（能动手做到）

- [ ] 不依赖任何库，手写 SQuAD 风格的 `normalize`、`exact_match`、`token_f1`，并解释 `"June 29th, 2007"` 为何 EM=0、F1=0.67
- [ ] 用 `Counter & Counter` 正确计算带重复 token 的重叠数，说明为什么不能用 `set` 交集
- [ ] 手算本节 `toy_bm25_score` 的打分，解释为什么 demo 里 iPod 段落排在 iPhone 段落之前，并给出至少一种修复（停用词 / IDF）
- [ ] 用 `transformers.pipeline("question-answering")` 跑通抽取式 QA，知道何时需要 `handle_impossible_answer=True`、为什么要检查 `score`
- [ ] 写出一个"检索 → 拼上下文 → 接地提示 → 拒答"的最小 RAG 流程，并给出基于检索分数的拒答阈值策略
- [ ] 为一个 RAG 系统设计评估方案：先测检索召回，再测 reader，并能说出 RAGAS 四个指标各自诊断什么问题

---

## 二、基础自测（选择题）

**Q1.** 关于抽取式 QA（如 SQuAD 上训练的 RoBERTa），下列说法**正确**的是：

- A. 模型逐 token 生成答案，因此可能产生段落中没有的词
- B. 模型预测答案在段落中的起点和终点位置，输出一定是原文的连续片段
- C. 模型只需要读入段落，不需要读入问题
- D. 只要用 SQuAD 1.1 训练，模型就能可靠地识别"段落里没有答案"的情况

**Q2.** 使用 `deepset/roberta-base-squad2` 的 HF `question-answering` pipeline，在**不传额外参数**的情况下，遇到段落中确实不含答案的问题，最可能的行为是：

- A. 自动返回空字符串 `""`
- B. 抛出异常提示无答案
- C. 仍然返回得分最高的某个 span，需要自己看 `score` 判断
- D. 返回整个段落

**Q3.** 一个 RAG 系统的回答准确率很低。工程上**第一步**最应该测什么？

- A. 换一个更大的 LLM 作为 reader
- B. 检索召回率：正确段落是否出现在 top-k 里
- C. 把 temperature 调到 0
- D. 增加提示词里的示例数量

**Q4.** 预测 `"29 June 2007"`，参考答案 `"June 29, 2007"`。按本节代码的 SQuAD 风格指标，结果是：

- A. EM=1，F1=1.00
- B. EM=0，F1=0.67
- C. EM=0，F1=1.00
- D. EM=0，F1=0.00

**Q5.** RAGAS 中哪个指标**最直接**地衡量"回答里的每个论断是否都能从检索到的上下文推出"？

- A. Context precision
- B. Context recall
- C. Answer relevance
- D. Faithfulness

**Q6.** 下面哪种场景**最适合**继续使用抽取式 QA，而不是"RAG + 生成式 LLM"？

- A. 面向大众的开放域闲聊问答
- B. 法律检索 / 合规审计，要求答案必须是权威语料的原文引用
- C. 多轮对话中的追问
- D. 需要综合多段材料写一段总结性回答

**Q7.** 关于闭卷（closed-book）生成式 QA，下列说法**错误**的是：

- A. 推理时不需要检索，延迟最低
- B. 对预训练语料中出现频率高的常识，通常回答得不错
- C. 对冷门或训练截止后才发生的事实，容易一本正经地编造
- D. 因为模型参数足够大，它在受监管领域可以替代检索直接作答

---

## 三、动手 / 代码题

**Q8.** 本节代码的玩具检索在 demo 问题上给出了下面的结果（真实运行输出）：

```text
  query: When was the first iPhone released?
  top score: 2.353  refuse: False
    2.353  The first iPod was released in 2001.
    2.000  Apple Inc. released the first iPhone on June 29, 2007.
```

打分函数如下：

```python
def toy_bm25_score(query, doc):
    q_tokens = set(tokenize(query))
    d_tokens = tokenize(doc)
    d_counts = Counter(d_tokens)
    score = 0.0
    for qt in q_tokens:
        if qt in d_counts:
            score += d_counts[qt] / (1 + len(d_tokens) / 10)
    return score
```

(1) 手算两个分数是怎么来的；(2) 解释为什么错误的 iPod 段落排第一；(3) 给出修复方案并说明修复后排序。

**Q9.** 下面三次调用分别返回什么？为什么 `token_f1` 要用 `Counter(...) & Counter(...)` 而不是集合交集？

```python
token_f1("June June 2007", "June 29, 2007")
token_f1("the", "June")
token_f1("", "")
```

**Q10.** `refusal_from_score(top_score, threshold=0.3)` 在 demo 里返回 `refuse: False`。讲义练习说的是"top 检索分数低于 0.3 **余弦**就拒答"。请指出把同一个 0.3 直接套在 `toy_bm25_score` 上的问题，并写一个更合理的拒答函数（可以自选策略）。

**Q11.** SQuAD 的开发集里，一个问题通常有多个人工标注的参考答案。请写一个 `squad_score(pred, golds)`，返回该问题的 EM 和 F1（复用本节的 `exact_match`、`token_f1`）。

---

## 四、面试高频题

**Q12.**（基础必考）对比抽取式 QA、RAG、闭卷生成式 QA：各自原理、优缺点、适用场景。为什么说 2026 年的 AI 助手是三者的混合？

**Q13.**（原理深挖）BERT 类模型做 SQuAD 2.0 时，start/end 两个 head 怎么训练？推理时如何选出最终 span？"无答案"是怎么建模的？段落超过最大长度怎么办？

**Q14.**（工程实践）你的 RAG 问答上线后，用户反馈"经常答错"。请给出一套系统化的排查和评估方法。

**Q15.**（场景设计）为一家银行设计内部合规问答助手（几十万份制度文件，答案必须可追溯，答不了宁可拒答）。说说架构、检索、reader、拒答和评估。

**Q16.**（追问型）EM / F1 已经被用了很多年，为什么生产环境还要引入 LLM-as-judge 和 RAGAS？它们又各自有什么风险？

---

## 五、参考答案与解析

### Q1 — 答案：B

抽取式 QA 把问题和段落**一起**编码，训练两个 head 输出每个位置作为起点 / 终点的分数，答案是段落中的连续 span，所以"按构造不会幻觉"。A 描述的是生成式；C 错在必须同时读问题；D 错在 SQuAD 1.1 每个问题都有答案，模型没学过"无答案"，这正是 SQuAD 2.0 要解决的问题。

### Q2 — 答案：C

讲义特别强调：即使模型在 SQuAD 2.0 上训练过，pipeline **默认仍返回最高分 span**，不会自动给空答案。只有传 `handle_impossible_answer=True`，且 null 分数超过所有 span 分数时，才返回空答案。无论哪种方式都应检查 `score` 字段。

### Q3 — 答案：B

"reader 无法修复一个缺失的段落"。如果正确段落根本没进 top-k，换多大的 LLM 都没用（A），调 temperature（C）、加示例（D）同理。所以先测 retrieval recall@k，它是 reader 准确率的上界。

### Q4 — 答案：C

归一化后预测为 `29 june 2007`、参考为 `june 29 2007`，字符串不同 ⇒ EM=0。token F1 只看**多重集合重叠**，不看顺序：三个 token 全部重叠，P=R=1 ⇒ F1=1.00。这说明 token F1 对词序不敏感。B 是 `"June 29th, 2007"` 的结果（`29th ≠ 29`）。

### Q5 — 答案：D

Faithfulness 用 NLI 蕴涵检查答案中的每个论断能否从检索上下文推出，是讲义所说的"主要幻觉指标"。Context precision 衡量检索结果里有多少是相关的（噪声）；Context recall 衡量检索集合是否包含所需全部信息；Answer relevance 衡量回答是否切题。

### Q6 — 答案：B

讲义："抽取式 QA 在需要逐字引用的场景仍在使用：法律检索、监管合规、审计工具"，并且"高事实性、受监管领域：在权威语料上做抽取式，永远不要单独用生成式"。A、C、D 更适合 RAG + LLM。

### Q7 — 答案：D

A、B、C 都是讲义对闭卷生成的描述（最快、常识好、冷门 / 新事实糟糕）。D 错：参数规模再大也无法保证事实正确与可追溯，讲义的 skill 明确要求"对监管或合规敏感问题拒绝闭卷 LLM 回答"。

### Q8 — 参考答案

(1) 手算（`tokenize` 会小写并只保留 `[a-z0-9]+`）：

| 段落 | token 数 | 命中的查询词 | 长度惩罚 `1 + len/10` | 分数 |
|------|---------|-------------|----------------------|------|
| iPod：`the first ipod was released in 2001` | 7 | the, first, was, released（4 个，各出现 1 次） | 1.7 | 4 / 1.7 = **2.353** |
| iPhone：`apple inc released the first iphone on june 29 2007` | 10 | released, the, first, iphone（4 个） | 2.0 | 4 / 2.0 = **2.000** |

(2) 原因：两段命中的查询词**数量一样多**（都是 4 个），但该函数①**没有 IDF**，`the`、`was` 这种虚词和真正有区分度的 `iphone` 权重一样；②**没有停用词过滤**，`was` 恰好只在 iPod 段落出现；③长度归一化让较短的 iPod 段落得分更高。于是错误段落胜出。这是"词面匹配 + 无权重"的典型失败，也是真正的 BM25 要引入 IDF 和饱和项的原因（下一节第 14 节）。

(3) 修复：去停用词 + 加 IDF。

```python
import math
from collections import Counter

STOP = {"when", "was", "the", "a", "an", "is", "in", "of", "on", "by", "as"}

def better_score(query, doc, corpus=CORPUS):
    N = len(corpus)
    doc_sets = [set(tokenize(d)) for d in corpus]
    d_tokens = tokenize(doc)
    d_counts = Counter(d_tokens)
    score = 0.0
    for qt in set(tokenize(query)) - STOP:
        if qt in d_counts:
            df = sum(1 for s in doc_sets if qt in s)
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1)
            score += idf * d_counts[qt] / (1 + len(d_tokens) / 10)
    return score
```

实际运行结果：iPhone 段落 1.040 > iPod 段落 0.815 > Macworld 段落 0.365 > Android 0.0，排序正确。

> 注意：只加 IDF、不去停用词**仍然排错**。在只有 4 篇文档的小语料里，`was` 只出现在 1 篇中，IDF 反而最高（≈1.20），会继续把 iPod 段落推上去——小语料上的 IDF 统计噪声很大，这也是一个面试可聊的点。

### Q9 — 参考答案

```text
0.6666666666666666
0.0
1.0
```

- `"June June 2007"`：预测 token `[june, june, 2007]`，参考 `[june, 29, 2007]`。`Counter & Counter` 取每个 token 的**最小计数**：`june: min(2,1)=1`、`2007: 1`，重叠 = 2；P = 2/3，R = 2/3，F1 = 0.67。
  - 若改用"预测里有几个 token 出现在参考里"（`sum(t in g for t in p)`）的写法，会数出 3 个，P = R = 1，F1 被虚高成 1.0——重复词被重复计分。
  - 若改用 `set` 交集，则在**两边都有重复**时会少算：`token_f1("June June", "June June 2007")` 正确值是 0.8（重叠 2），用 set 只算出重叠 1，F1 变成 0.4。
  - `Counter &` 是**多重集合交集**，两种错误都能避免——这也是 SQuAD 官方评测脚本的做法。
- `"the"` vs `"June"`：`normalize("the")` 去掉冠词后为空串 ⇒ 预测 token 为空、参考不空 ⇒ 返回 0.0。
- 两边都为空 ⇒ 视为完全匹配，返回 1.0（对应 SQuAD 2.0 里"无答案"问题预测"无答案"的情况）。

### Q10 — 参考答案

问题：阈值的意义取决于**分数的量纲**。余弦相似度落在 [-1, 1]，0.3 有意义；而 `toy_bm25_score` 是"命中词数 / 长度惩罚"的累加，范围随查询长度、文档长度变化，没有上界。对 20 个 token 左右的短文档，只要命中一个 `the` 就有 `1/(1+2.0) ≈ 0.33` 以上的分数，于是几乎永远不会拒答——demo 里 top score 2.353，远高于 0.3，而它恰恰是错误段落。

更合理的做法（任选其一或组合）：

```python
def refuse(results, min_score=0.3, min_margin=0.2):
    """results: [(score, doc), ...] 已按分数降序。
    分数需先归一化到可比较的区间（如余弦，或按查询自身的最大可能得分归一化）。"""
    if not results:
        return True
    top = results[0][0]
    second = results[1][0] if len(results) > 1 else 0.0
    if top < min_score:          # 绝对阈值：最相关的也不够相关
        return True
    if top - second < min_margin:  # 相对间隔：前两名难分高下，说明检索不确定
        return True
    return False
```

要点：①阈值必须在**同一量纲**下、在留出集上调（讲义练习 2）；②BM25 类分数可用"除以查询自身的满分"或 min-max 归一化；③也可以用 reranker（交叉编码器）的分数或 reader 的 null score 作为拒答依据；④最终用 false confidence rate 评估拒答校准。

### Q11 — 参考答案

```python
def squad_score(pred, golds):
    em = max(exact_match(pred, g) for g in golds)
    f1 = max(token_f1(pred, g) for g in golds)
    return em, f1

print(squad_score("2007", ["June 29, 2007", "2007"]))  # (1.0, 1.0)
```

SQuAD 的做法是对每个参考答案分别打分、**取最大值**，再对整个数据集求平均。原因：同一事实有多种合法写法（"June 29, 2007" / "2007"），取 max 可以减少因标注写法不同造成的误判。EM 与 F1 各自独立取 max。

### Q12 — 参考回答要点

| 维度 | 抽取式 | RAG（检索 + reader） | 闭卷生成式 |
|------|--------|--------------------|-----------|
| 输入 | 问题 + 已知含答案的段落 | 问题 + 语料库 | 只有问题 |
| 原理 | 预测 start/end 位置 | 检索 top-k → 抽取或生成 | LLM 从参数记忆中生成 |
| 优点 | 不编造、可逐字引用 | 可接地、知识可更新、可引用 | 最快、覆盖常识 |
| 缺点 | 需要已知段落、答案必须是原文片段 | 受检索质量上限约束、链路长 | 冷门 / 新事实幻觉严重、不可追溯 |
| 典型场景 | 法律 / 审计逐字引用 | 企业知识库、文档问答 | 通识问答、草稿生成 |

- 混合的原因：用检索保证事实来源（解决闭卷幻觉），用 LLM 生成保证表达灵活（解决抽取式只能截取原文），必要时在高风险场景回退到抽取式引用。
- 加分点：提到检索器与 reader 可以分开训练和评估；提到 reranker；提到对话式 QA 要在每一轮都结合历史做检索。

### Q13 — 参考回答要点

- 输入：`[CLS] question [SEP] passage [SEP]`，编码器输出每个 token 的向量 `hᵢ`。
- 两个 head：本质是两个向量 `S`、`E`（一个线性层），`start_logitᵢ = S·hᵢ`、`end_logitᵢ = E·hᵢ`，分别在段落位置上做 softmax，用真实起点 / 终点做交叉熵，总损失为两者之和（或平均）。
- 推理：枚举 `i ≤ j` 且长度不超过上限的组合，取 `start_logitᵢ + end_logitⱼ` 最大的 span，并映射回原文字符偏移。
- 无答案（SQuAD 2.0）：常见做法是把答案位置设为 `[CLS]`，得到 null 分数 `start_logit_CLS + end_logit_CLS`；当 null 分数比最佳非空 span 高出某个阈值时输出"无答案"。阈值一般在开发集上调。
- 长段落：按最大长度切成有**重叠**的窗口（stride），每个窗口分别预测，再跨窗口取最高分 span。
- 常见误区：以为 SQuAD 2.0 训练过的模型"自动会拒答"——在 HF pipeline 里默认并不会，需要 `handle_impossible_answer=True` 并检查 `score`。

### Q14 — 参考回答要点

按链路**自底向上**拆解，逐级定位：

1. **建评估集**：从线上日志抽样真实问题，标注"应命中的段落"和参考答案，覆盖可答 / 不可答两类。
2. **测检索**：recall@k、MRR / nDCG。召回不够 ⇒ 优化切块、加 BM25 做混合检索、换 embedding 模型、加 reranker（第 14 节）。
3. **测 reader**：在"保证正确段落已在上下文中"的条件下测答案准确率，排除检索因素；看是不是提示词没要求接地、上下文太长被淹没、模型能力不足。
4. **测幻觉与引用**：RAGAS faithfulness、引用准确率（引用的段落是否真的支持答案，可用字符串匹配快速检查）。
5. **测拒答校准**：答不了时是否说"I don't know"，统计 false confidence rate。
6. **上线监控**：RAGAS 四个指标是 reference-free 的，可直接跑在线上流量上，对回归告警。

- 加分点：明确说出"reader 准确率 ≤ 检索召回率"这一上界关系；区分"没检索到"和"检索到了却没用好"两类错误，各自改法完全不同。
- 常见误区：一上来换更大的 LLM 或改提示词，没有先确认正确段落是否进了上下文。

### Q15 — 参考回答要点

- **架构**：RAG + 可追溯引用；高风险问题（如条款原文）走抽取式 reader 给出逐字引用；**禁止**闭卷回答。
- **检索**：混合检索（BM25 抓条款编号、专有名词等精确词，dense 抓语义改写），RRF 融合，再用 cross-encoder reranker 精排；带元数据过滤（生效日期、部门、版本）。
- **Reader**：接地提示词——"只依据上下文回答，不足则说不知道，并标注引用的段落编号"；或用抽取式模型直接输出原文 span。
- **拒答**：检索分数阈值（在留出集上调）+ reranker 分数 + reader 的置信度 / null score，多道闸门；拒答时给出"建议咨询的部门 / 文件"。
- **评估**：检索召回基线（没有它就不能评估 reader）、答案准确率（人工或 LLM 评判）、引用准确率、拒答校准；上线后用 RAGAS faithfulness 监控幻觉。
- **多跳问题**：如"A 制度第 3 条与 B 制度冲突时以谁为准"，需要多跳检索，单纯 top-k 不够，应标记出来专门处理。

### Q16 — 参考回答要点

- EM / F1 的局限：只看字面，不懂语义。`"June 29th, 2007"` 与 `"June 29, 2007"` 意思相同但 EM=0；`"29 June 2007"` 词序不同 F1 却满分；生成式回答一句完整句子时，F1 会因多出的词被大幅压低。开放式问题根本没有唯一参考答案。
- LLM-as-judge：能判断语义等价，适合开放式问题；风险是评委模型自身有偏差（偏好长答案、偏好与自己风格相近的答案）、结果不稳定，需要用人工标注做校准抽检。
- RAGAS：reference-free，可以评估线上真实流量，且把问题拆成检索侧（context precision / recall）和生成侧（faithfulness / answer relevance），便于定位；风险是指标本身依赖 NLI 或 LLM 打分，也会出错，不能把分数当成绝对真相。
- 加分点：生产中通常"EM/F1 做回归基线 + LLM judge 做语义判断 + 人工小样本校准"三者结合。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 10 Attention 机制](../../10-attention-mechanism/docs/zh.md)：抽取式 QA 中问题与段落的交互依赖 attention。
- [阶段 05 · 11 机器翻译](../../11-machine-translation/docs/zh.md)：讲义列出的前置课，编码器-解码器与预训练模型的使用方式。
- [阶段 05 · 02 词袋与 TF-IDF](../../02-bag-of-words-tfidf/docs/zh.md)：理解本节玩具检索为什么缺了 IDF 会排错。

### 本节被哪些后续内容用到
- [阶段 05 · 14 信息检索与搜索](../../14-information-retrieval-search/docs/zh.md)：RAG 的检索半边——BM25、dense、混合检索、RRF、reranker。
- [阶段 05 · 21 自然语言推理](../../21-nli-textual-entailment/docs/zh.md)：RAGAS faithfulness 背后的 NLI 蕴涵判断。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../23-chunking-strategies-rag/docs/zh.md)：切块方式直接决定检索召回。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../27-llm-evaluation-frameworks/docs/zh.md)：本节评估部分的系统展开。
- [阶段 07 · 06 BERT 与掩码语言模型](../../../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/zh.md)：抽取式 reader 的骨干模型。
- [阶段 11 · 06 RAG](../../../11-llm-engineering/06-rag/docs/zh.md) 与 [阶段 11 · 07 高级 RAG](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：工程化的 RAG 流水线。
- [阶段 19 · 68 RAG 评估：精确率与召回率](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md)、[阶段 19 · 69 端到端 RAG 系统](../../../19-capstone-projects/69-end-to-end-rag-system/docs/zh.md)：综合项目。

### 延伸关键词
`SQuAD 2.0` · `Natural Questions` · `HotpotQA（多跳）` · `DPR 稠密段落检索` · `doc stride 滑窗` · `null score 阈值` · `Fusion-in-Decoder` · `引用生成（citation）` · `RAGAS` · `LLM-as-judge`
