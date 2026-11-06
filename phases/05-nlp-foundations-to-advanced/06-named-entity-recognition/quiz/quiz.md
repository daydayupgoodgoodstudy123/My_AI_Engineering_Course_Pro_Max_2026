# 测验 · 命名实体识别（Named Entity Recognition）

> **阶段 05 · NLP 基础到高级 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | NER 是什么 | 从文本中找出实体片段并标注类型（PERSON、ORG、GPE、PRODUCT、DATE…），是简历解析、合规扫描、病历脱敏、搜索理解等抽取流水线的底座 |
| 2 | BIO 标注 | 把"找片段"变成"给每个 token 分类"：`B-X` 开始、`I-X` 延续、`O` 不属于任何实体；多 token 实体串起来：`New/B-GPE York/I-GPE City/I-GPE` |
| 3 | BILOU | 在 BIO 上增加 `L-X`（最后一个）与 `U-X`（单 token 实体），边界更清晰 |
| 4 | 片段 ↔ BIO 互转 | 片段用左闭右开区间 `(start, end, type)`；`spans_to_bio` 与 `bio_to_spans` 应能往返一致 |
| 5 | 规则 + 词典（gazetteer） | 已知实体精度高，新实体覆盖率为零；无法消歧（Apple 公司 vs 苹果），不处理多 token 实体 |
| 6 | 手工特征 | 小写形式、是否全大写 / 首字母大写、是否含数字、后缀、词形（`iPhone → xXxxxx`）、前后词——大小写模式是专有名词的强信号 |
| 7 | 方法演进 | 规则 → HMM（发射 + 转移概率，Viterbi 解码）→ CRF（判别式，可混合任意特征）→ BiLSTM-CRF（特征由网络学习）→ Transformer 微调（准确率最高、算力最贵） |
| 8 | CRF 层的作用 | 对标签之间的转移建模，让 `O → I-ORG` 这类非法序列得分很低，从而保证输出序列合法 |
| 9 | 2026 年的 LLM NER | 零样本 JSON 抽取、多阶段提示、基于检索的动态 few-shot、按实体类型逐个抽取；先用 LLM 零样本做基线，再决定是否收集数据微调 |
| 10 | 评估与失败模式 | 用 `seqeval` 报告**实体级** F1（片段必须完全匹配），token 级指标会虚高；领域迁移、嵌套实体、长实体、稀有类型是四大失败模式 |

### 核心技能（能动手做到）

- [ ] 能手写给定句子的 BIO 与 BILOU 标注，并实现 `spans_to_bio` / `bio_to_spans`，验证往返一致
- [ ] 能预测 `bio_to_spans` 在"孤儿 I 标签"、"类型不一致的 I 标签"、"相邻同类实体"等边界情况下的输出
- [ ] 能实现 `word_shape` 与 `token_features`，并说明每个特征对识别专有名词的作用
- [ ] 能把单 token 词典匹配扩展为**最长匹配**的多 token 词典匹配，输出合法的 BIO 序列
- [ ] 能手算一个预测结果的实体级 precision / recall / F1，并与 token 级准确率对比
- [ ] 能用 sklearn-crfsuite 写出 CRF 的特征函数与训练调用，并解释 `c1`、`c2`、`all_possible_transitions` 的含义
- [ ] 能根据延迟、标注量、领域、合规要求，在规则 / CRF / BiLSTM-CRF / Transformer / LLM 中做出选型

---

## 二、基础自测（选择题）

**Q1.** 句子 `The New York City mayor visited OpenAI .` 中，`New York City` 是 GPE、`OpenAI` 是 ORG。正确的 BIO 标注是：

- A. `O B-GPE B-GPE B-GPE O O B-ORG O`
- B. `O B-GPE I-GPE I-GPE O O B-ORG O`
- C. `O I-GPE I-GPE I-GPE O O I-ORG O`
- D. `B-O B-GPE I-GPE I-GPE B-O B-O B-ORG B-O`

**Q2.** 同一句话改用 BILOU 方案，`New York City` 与 `OpenAI` 应分别标注为：

- A. `B-GPE I-GPE I-GPE` 与 `B-ORG`
- B. `B-GPE I-GPE L-GPE` 与 `U-ORG`
- C. `U-GPE U-GPE U-GPE` 与 `U-ORG`
- D. `B-GPE L-GPE L-GPE` 与 `L-ORG`

**Q3.** 相比 HMM，CRF 用于 NER 的关键优势是：

- A. CRF 不需要 Viterbi 解码
- B. CRF 是判别式模型，可以自由组合任意（甚至相互重叠的）特征，如词形、大小写、前后词
- C. CRF 不需要标注数据
- D. CRF 只建模发射概率，因此更快

**Q4.** 在 sklearn-crfsuite 中设置 `all_possible_transitions=True`，作用是：

- A. 强制模型输出所有可能的标签序列
- B. 为所有标签对（包括训练集中从未出现的转移，如 `O → I-ORG`）都生成转移特征，模型可以给这些非法转移学到负权重，从而在不手写约束的情况下保证 BIO 一致性
- C. 关闭 L1 / L2 正则
- D. 允许一个 token 同时属于多个实体

**Q5.** 对 Q1 的句子，模型预测为 `O B-GPE I-GPE O O O B-ORG O`（只识别出 `New York`）。下列说法正确的是：

- A. token 级准确率 0.875，实体级 F1 也约为 0.875
- B. token 级准确率 0.875，实体级 precision = recall = F1 = 0.5
- C. 实体级 F1 为 0.75，因为 GPE 实体 3 个 token 对了 2 个
- D. 实体级 F1 为 1.0，因为两个实体的类型都对

**Q6.** "Bank of America Tower" 整体是一个 FACILITY，其中 "Bank of America" 又是一个 ORG。标准 BIO 标注无法表示它，原因是：

- A. BIO 不能表示多 token 实体
- B. BIO 每个 token 只有一个标签，无法表达两个相互重叠、类型不同的片段；需要嵌套 NER（多遍标注或基于 span 的模型）
- C. BIO 不能表示 FACILITY 类型
- D. BIO 只能用于英文

**Q7.** 用本节的 `rule_based_ner` 处理 `"I ate an Apple pie in New York".split()`，输出为 `['O', 'O', 'O', 'B-ORG', 'O', 'O', 'O', 'O']`。这暴露了词典方法的哪两个问题？

- A. 速度太慢；需要 GPU
- B. 无法消歧（把食物里的 Apple 标成 ORG）；只做单 token 匹配，漏掉多 token 实体 `New York`
- C. 无法处理标点；无法处理小写
- D. 词典太大；精度太低

**Q8.** 按讲义的建议，下列哪种情况最适合**先**用 LLM 零样本 NER 做基线？

- A. 延迟预算低于 50ms 的在线服务
- B. 已有数万条标注、要求 F1 达到 98% 以上
- C. 一个新领域、几乎没有标注数据、想快速评估可行性的抽取任务
- D. 合规要求必须本地部署、不能使用生成式模型

---

## 三、动手 / 代码题

**Q9.** 本节的 `bio_to_spans` 如下：

```python
def bio_to_spans(tokens, labels):
    spans = []
    current = None
    for i, label in enumerate(labels):
        if label.startswith("B-"):
            if current:
                spans.append(current)
            current = (i, i + 1, label[2:])
        elif label.startswith("I-") and current and current[2] == label[2:]:
            current = (current[0], i + 1, current[2])
        else:
            if current:
                spans.append(current)
                current = None
    if current:
        spans.append(current)
    return spans
```

(1) 不运行代码，写出下面 4 个输入的输出（`tokens` 参数没被使用，可传 `None`）：

```python
bio_to_spans(None, ["O", "I-ORG", "I-ORG"])
bio_to_spans(None, ["B-ORG", "I-PER", "O"])
bio_to_spans(None, ["B-PER", "B-PER"])
bio_to_spans(None, ["B-ORG", "I-ORG", "O", "I-ORG"])
```

(2) 模型输出中出现"孤儿 I 标签"（前面不是同类型的 B/I）时，这个实现采取了什么策略？另一种常见策略是什么？请写出另一种策略的实现。

**Q10.** 用本节的 `spans_to_bio` 处理嵌套实体：

```python
tokens = "Bank of America Tower".split()
bio = spans_to_bio(tokens, [(0, 4, "FAC"), (0, 3, "ORG")])
print(bio, bio_to_spans(tokens, bio))
```

(1) 写出输出，并解释发生了什么。如果把两个 span 的顺序对调，结果又是什么？
(2) 写一个 `spans_to_bio_checked`，在遇到越界或重叠的区间时抛出带说明的 `ValueError`，而不是静默地产生错误标注。

**Q11.** 本节的 `rule_based_ner` 只能做单 token 精确匹配。请实现 `gazetteer_ner(tokens)`：词典的键是 token 元组（如 `("New", "York", "City")`），采用**最长匹配优先**，输出合法的 BIO 标签。用下面的词典验证 `"The New York City mayor met Bank of America in the US ."`：

```python
GAZETTEER = {
    ("New", "York", "City"): "GPE",
    ("New", "York"): "GPE",
    ("Bank", "of", "America"): "ORG",
    ("Apple",): "ORG",
    ("US",): "GPE",
    ("iPhone",): "PRODUCT",
}
```

---

## 四、面试高频题

**Q12.**（基础必考）NER 一般怎么建模成机器学习问题？BIO 和 BILOU 有什么区别？为什么必须用实体级 F1 评估？

**Q13.**（原理深挖）请对比 HMM、CRF、BiLSTM-CRF 和 BERT token classification。为什么 BiLSTM 或 BERT 上面还常常要加一层 CRF？

**Q14.**（工程实践）用 BERT 做 NER 时，WordPiece 会把一个词切成多个子词（如 `iPhone` 可能被切成几段），但标注是按词给的。训练和推理时分别怎么处理这个对齐问题？

**Q15.**（场景设计）你需要从法律合同中抽取"合同方、金额、日期、管辖法律"等字段，目前只有不到 200 条标注样本，后续要求单条处理延迟在 100ms 以内。请给出从 0 到上线的方案。

**Q16.**（追问型）面试官追问："你的 NER 在新闻数据上 F1 有 90，拿到法律合同上直接掉到 60。可能是什么原因？嵌套实体和超长实体你又怎么处理？"

---

## 五、参考答案与解析

### Q1 — 答案：B

多 token 实体以 `B-` 开头、后续 token 用 `I-` 延续；单 token 实体只有 `B-`；不属于任何实体的 token 标 `O`。这正是 `main.py` 往返测试中打印的 `bio`。A 会被解析成三个独立的单 token GPE；C 缺少起始标记（在本节实现中会被整体丢弃，见 Q9）；D 中 `O` 不带前缀。

### Q2 — 答案：B

BILOU：`B` 开始、`I` 中间、`L` 最后一个、`U` 单 token 实体（Unit）、`O` 外部。`New York City` 是三 token 实体：`B-GPE I-GPE L-GPE`；`OpenAI` 是单 token 实体：`U-ORG`。讲义称 BILOU 让边界"更干净"：模型必须显式预测实体在哪里结束、以及是否为单 token 实体。

### Q3 — 答案：B

HMM 是生成式模型，建模 `P(词 | 标签)` 和 `P(标签 | 前一个标签)`，每个位置只能"生成"一个观测，很难加入"首字母大写 + 前一个词是 Mr. + 后缀是 -son"这类相互重叠的特征。CRF 是判别式的，直接建模 `P(标签序列 | 整句)`，特征可以任意设计、任意重叠。两者都需要训练数据，也都用 Viterbi 解码，所以 A、C 错；D 说反了，CRF 同样建模标签转移。

### Q4 — 答案：B

讲义：`all_possible_transitions=True` "lets the model learn illegal sequences (e.g., `I-ORG` after `O`) are unlikely, which is how a CRF enforces BIO consistency without you writing the constraint." 如果只为训练集中出现过的转移生成特征，那些从未出现的非法转移就没有对应的权重，模型也就无法显式地惩罚它们。

### Q5 — 答案：B

- token 级：8 个 token 中只有 `City`（应为 `I-GPE`、预测为 `O`）错了，准确率 7/8 = 0.875；
- 实体级：真实实体 `{(1,4,GPE), (6,7,ORG)}`，预测实体 `{(1,3,GPE), (6,7,ORG)}`。`(1,3,GPE)` 与 `(1,4,GPE)` 边界不同，**不算命中**。TP = 1，precision = 1/2，recall = 1/2，F1 = 0.5。

这就是讲义说的 "Token-level F1 overstates accuracy"：下游系统拿到的是"New York"而不是"New York City"，对业务来说这条抽取就是错的。C 是常见误解——实体级评估不给"部分正确"计分。

### Q6 — 答案：B

BIO 是"每个 token 一个标签"的扁平方案。`Bank` 既要是 FAC 的开头，又要是 ORG 的开头，一个标签装不下。讲义："Standard BIO cannot represent overlapping spans. You need nested NER (multi-pass or span-based models)." A 错：BIO 可以表示多 token 实体，只是不能表示**重叠**的实体。Q10 会展示 `spans_to_bio` 遇到嵌套时如何静默出错。

### Q7 — 答案：B

- `Apple` 在 `ORG_GAZETTEER` 里，不管上下文是不是在说吃的，都会被标成 ORG——讲义："Disambiguation (`Apple` the company vs the fruit) is terrible."
- `rule_based_ner` 逐个 token 判断是否在集合里，`New`、`York` 单独都不在词典中，多 token 实体完全漏掉（Q11 会修复这一点）。

这两点正是"That is why statistical models won"的原因。

### Q8 — 答案：C

讲义的生产建议："start with an LLM zero-shot baseline before you collect training data. Often the F1 is good enough that you never need to fine-tune." 同时列出了经典 NER 仍然胜出的场景：延迟预算低于 50ms（A）、有数千条标注且要求 98%+ F1（B）、本体稳定、合规要求本地部署的非生成式模型（D）。

### Q9 — 参考答案

**(1)** 实测输出：

```text
bio_to_spans(None, ["O", "I-ORG", "I-ORG"])           → []
bio_to_spans(None, ["B-ORG", "I-PER", "O"])           → [(0, 1, 'ORG')]
bio_to_spans(None, ["B-PER", "B-PER"])                → [(0, 1, 'PER'), (1, 2, 'PER')]
bio_to_spans(None, ["B-ORG", "I-ORG", "O", "I-ORG"])  → [(0, 2, 'ORG')]
```

逐条：
- 第 1 个：`I-ORG` 前面没有打开的实体（`current` 为 `None`），走 `else` 分支，什么也不做——两个 `I-ORG` 被**整体丢弃**。
- 第 2 个：`I-PER` 与当前实体类型 ORG 不一致，走 `else` 分支，ORG 实体在位置 1 之前结束，`I-PER` 被丢弃。
- 第 3 个：两个 `B-PER` 表示两个相邻的独立实体——这正是 BIO 中 `B` 存在的意义：没有 `B`，就无法区分"两个相邻的人名"和"一个两 token 的人名"。
- 第 4 个：位置 3 的 `I-ORG` 前面是 `O`，同样被丢弃。

**(2)** 本实现是**严格策略**：只承认以 `B-` 开头的实体，孤儿 `I-` 一律丢弃。另一种常见的**宽松策略**（conlleval / `seqeval` 默认模式就是这样）是：把孤儿 `I-X` 当作一个新实体的开始。

```python
def bio_to_spans_lenient(labels):
    spans, current = [], None
    for i, label in enumerate(labels):
        if label == "O":
            if current:
                spans.append(current)
                current = None
            continue
        prefix, kind = label.split("-", 1)
        if prefix == "I" and current and current[2] == kind:
            current = (current[0], i + 1, kind)
        else:                         # B-X，或"孤儿" I-X：都开启新实体
            if current:
                spans.append(current)
            current = (i, i + 1, kind)
    if current:
        spans.append(current)
    return spans
```

实测：`["O","I-ORG","I-ORG"] → [(1, 3, 'ORG')]`，`["B-ORG","I-PER","O"] → [(0, 1, 'ORG'), (1, 2, 'PER')]`，`["B-ORG","I-ORG","O","I-ORG"] → [(0, 2, 'ORG'), (3, 4, 'ORG')]`。

取舍：严格策略精确率更高、召回更低；宽松策略对 softmax 逐 token 分类器（没有 CRF 约束、经常输出非法序列）更友好。**评估时**解码策略必须和评测工具一致，否则同一个模型会得到不同的 F1。

### Q10 — 参考答案

**(1)** 实测输出：

```text
['B-ORG', 'I-ORG', 'I-ORG', 'I-FAC'] [(0, 3, 'ORG')]
```

`spans_to_bio` 按顺序把每个 span 写进同一个 `labels` 列表，后写的会**覆盖**先写的：先写 FAC 得到 `B-FAC I-FAC I-FAC I-FAC`，再写 ORG 覆盖前三个位置，变成 `B-ORG I-ORG I-ORG I-FAC`。这是一个非法的 BIO 序列（ORG 后面直接跟 `I-FAC`）；`bio_to_spans` 解析时丢弃了孤儿 `I-FAC`，FAC 实体彻底消失，而且没有任何报错。

对调顺序后：先写 ORG，再写 FAC 覆盖全部 4 个位置，得到 `['B-FAC', 'I-FAC', 'I-FAC', 'I-FAC']`，恢复出 `[(0, 4, 'FAC')]`——这次是 ORG 消失。**结果取决于 span 的顺序**，这正是 BIO 无法表示嵌套实体的直观体现。

**(2)**

```python
def spans_to_bio_checked(tokens, spans):
    occupied = [False] * len(tokens)
    for start, end, label in spans:
        if not (0 <= start < end <= len(tokens)):
            raise ValueError(f"非法区间 {(start, end)}")
        if any(occupied[start:end]):
            raise ValueError(f"区间 {(start, end, label)} 与已有实体重叠：BIO 无法表示嵌套实体")
        for i in range(start, end):
            occupied[i] = True
    return spans_to_bio(tokens, spans)
```

实测：对上面的嵌套输入抛出 `ValueError: 区间 (0, 3, 'ORG') 与已有实体重叠：BIO 无法表示嵌套实体`；对 `main.py` 中的 `[(1, 4, "GPE"), (6, 7, "ORG")]` 正常返回 `['O', 'B-GPE', 'I-GPE', 'I-GPE', 'O', 'O', 'B-ORG', 'O']`。在准备训练数据时加上这类校验，可以尽早发现标注中的嵌套与越界问题，而不是让它们悄悄变成错误的训练标签。

### Q11 — 参考答案

```python
MAX_LEN = max(len(k) for k in GAZETTEER)

def gazetteer_ner(tokens):
    labels = ["O"] * len(tokens)
    i = 0
    while i < len(tokens):
        for n in range(min(MAX_LEN, len(tokens) - i), 0, -1):   # 从最长的候选开始试
            key = tuple(tokens[i:i + n])
            if key in GAZETTEER:
                kind = GAZETTEER[key]
                labels[i] = f"B-{kind}"
                for j in range(i + 1, i + n):
                    labels[j] = f"I-{kind}"
                i += n                  # 跳过整个实体，避免重叠匹配
                break
        else:                           # for 循环没有 break：这个位置不是任何实体的开头
            i += 1
    return labels
```

实测：

```text
tokens: The New York City mayor met Bank of America in the US .
labels: ['O', 'B-GPE', 'I-GPE', 'I-GPE', 'O', 'O', 'B-ORG', 'I-ORG', 'I-ORG', 'O', 'O', 'B-GPE', 'O']
spans : [(1, 4, 'GPE'), (6, 9, 'ORG'), (11, 12, 'GPE')]
```

要点：
1. **最长匹配优先**：`New York City` 与 `New York` 都在词典中，从长到短尝试，保证选中 3 个 token 的完整实体。
2. **匹配后跳过整个实体**（`i += n`），保证输出的片段互不重叠，BIO 合法。
3. `for ... else`：`else` 分支只在循环**没有被 `break`** 时执行，正好表达"所有长度都没匹配上"。
4. 用元组作键，查找是 O(1)；每个位置最多尝试 `MAX_LEN` 次，总复杂度 O(n·MAX_LEN)。生产中的百万级词典通常用 Trie 或 Aho-Corasick 自动机做多模式匹配。
5. 仍然存在的问题：消歧（Apple pie）依旧做不到——这需要上下文特征或统计模型。

### Q12 — 参考回答要点

- **建模**：把实体抽取变成**序列标注**：每个 token 预测一个标签，再把标签序列解码成片段。也可以建模成"片段分类"（枚举候选 span 再分类），后者天然支持嵌套。
- **BIO vs BILOU**：BIO 用 `B / I / O`；BILOU 多了 `L`（最后一个）与 `U`（单 token 实体），标签更多、边界信息更显式，有时能带来小幅提升，代价是标签空间变大、每类样本更少。
- **为什么用实体级 F1**：业务需要的是完整、类型正确的片段。只要边界错一个 token 或类型错，这条抽取对下游就没用。token 级指标会把"New York City 只抽出 New York"算作大部分正确，严重高估效果。讲义 Ship It："Use `seqeval`. Always report entity-level F1 (not token-level)."
- **加分点**：按实体类型分别报告 F1（稀有类型往往最差）；说明解码策略（严格 / 宽松）要和评测工具保持一致。

### Q13 — 参考回答要点

| 方法 | 类型 | 特征 | 标签依赖 | 特点 |
|------|------|------|---------|------|
| HMM | 生成式 | 只看当前词（发射概率） | 一阶转移 | 简单，难以加入丰富特征 |
| CRF | 判别式 | 任意手工特征（词形、大小写、前后词、后缀） | 转移特征 | 讲义："classical production workhorse in 2026 for low-resource deployments" |
| BiLSTM-CRF | 判别式 | 网络从词向量学到的上下文特征 | CRF 层 | 双向 LSTM 读整句；收益需要数万条标注才明显 |
| BERT + 分类头 | 判别式 | 预训练 Transformer 的上下文表示 | 通常逐 token 独立预测 | 准确率最高，算力最贵 |

- **为什么还要 CRF 层**：BiLSTM / BERT 的分类头对每个 token **独立**做 softmax，可能输出 `O I-ORG`、`B-PER I-ORG` 这类非法序列。CRF 层在发射分数之上加了一个可学习的转移矩阵，用 Viterbi 解码在整句范围内找**全局最优**的合法序列。讲义："The CRF still enforces tag-sequence consistency; the LSTM replaces hand-crafted features with learned ones."
- **加分点**：BERT 的上下文能力已经很强，加 CRF 的收益通常较小；数据少、标签体系复杂时 CRF 层更有价值。另一种轻量做法是解码时用规则约束（禁止非法转移）。

### Q14 — 参考回答要点

- **问题**：标注以"词"为单位，而 BERT 的输入是子词（WordPiece）。一个词切成多个子词后，标签要对齐。
- **训练时**：用 tokenizer 返回的"子词 → 原词"映射（Hugging Face fast tokenizer 的 `word_ids()`）对齐。常见做法是：每个词的**第一个子词**拿该词的标签，其余子词标为 `-100`（交叉熵损失会忽略）；另一种做法是所有子词都打标签（后续子词的 `B-X` 改为 `I-X`）。特殊 token（`[CLS]`、`[SEP]`、padding）也标 `-100`。
- **推理时**：取每个词第一个子词的预测作为该词的标签；或像讲义中 Hugging Face `pipeline("ner", aggregation_strategy="simple")` 那样，把相邻的同类型 `B-X / I-X` token 合并成一个片段——"Without it, you get token-level labels and have to merge yourself."
- **常见坑**：用慢速 tokenizer 拿不到 `word_ids()`；手写对齐时差一位；训练用"只标第一个子词"、推理却用"所有子词投票"，前后不一致。

### Q15 — 参考回答要点

- **阶段 1：LLM 零样本基线（第 1 周）**：讲义建议先用 LLM 零样本做基线。给出实体类型定义与 JSON schema；对长合同**按实体类型逐个抽取**（讲义："Run one extraction pass per entity type... standard pattern for clinical notes and legal contracts"）；用约 200 条标注做评测集，报告实体级 F1。
- **阶段 2：提升效果**：
  - 动态 few-shot：每次推理从标注集中检索最相似的样本拼进提示（讲义称为 "Dynamic prompting with RAG"）；
  - 多阶段提示：候选抽取 → 解释 → 判断 → 复核；
  - 金额、日期等格式化字段，用正则 / 规则做后校验与标准化。
- **阶段 3：满足 100ms 延迟**：LLM 多次调用很难满足。用 LLM（+ 人工抽检）为大量未标注合同生成"银标"数据，训练一个 CRF 或小型 Transformer（如 `distilbert-base-cased` 微调，讲义练习 3）部署上线；LLM 退居离线复核与难例处理。注意讲义 Ship It："Refuse to recommend fine-tuning a transformer for under 500 labeled examples unless the user already has a pretrained domain model"——所以要先把标注扩充到足够规模。
- **评估与合规**：实体级 F1（`seqeval`）、逐类型 F1；合同若含敏感信息，可能要求本地部署非生成式模型（讲义"classical NER still wins"的第 4 条）。
- **加分点**：主动指出管辖法律条款中可能存在嵌套或超长实体，提前设计标注规范。

### Q16 — 参考回答要点

- **掉分原因——领域迁移**：讲义："CoNLL-trained NER on legal contracts performs worse than a gazetteer. Fine-tune on your domain."
  - 实体类型不同（新闻里的 PER/ORG/LOC vs 合同里的"甲方 / 乙方 / 金额 / 条款"）；
  - 写作风格不同（大写术语、编号、超长名称）；
  - 词表分布不同（法律术语、拉丁短语）。
  - 对策：领域标注 + 微调；领域词典辅助；Ship It 也要求"labels unchanged from CoNLL-2003 + production scale"时必须先审计词典。
- **嵌套实体**：BIO 表示不了（Q6、Q10）。方案：
  - 多遍（multi-pass）：每种类型或每一层单独跑一遍序列标注；
  - span-based 模型：枚举所有候选片段（限制最大长度），对每个片段做分类，天然允许重叠。
- **超长实体**：如 "United States Federal Deposit Insurance Corporation"，逐 token 模型可能在中间断开。对策：讲义建议用 `aggregation_strategy` 或后处理合并；加 CRF 层保证序列一致；用词典对已知长实体做兜底。
- **加分点**：用错例分析区分"边界错"与"类型错"，分别对应不同的改进方向。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../02-bag-of-words-tfidf/docs/zh.md)：本节官方前置课；稀疏特征表示。
- [阶段 05 · 03 词 Embeddings——从零实现 Word2Vec](../../03-word-embeddings-word2vec/docs/zh.md)：本节官方前置课；BiLSTM-CRF 的输入是词向量。
- [阶段 05 · 01 文本处理](../../01-text-processing/docs/zh.md)：tokenization 决定了 token 边界，进而决定实体边界。
- [阶段 05 · 05 情绪分析](../../05-sentiment-analysis/docs/zh.md)：从"整句分类"到本节的"逐 token 分类"。

### 本节被哪些后续内容用到
- [阶段 05 · 07 词性标注和句法分析](../../07-pos-tagging-parsing/docs/zh.md)：同为序列标注，HMM / Viterbi 在那里有完整实现。
- [阶段 05 · 08 文本的 CNNs 和 RNNs](../../08-cnns-rnns-for-text/docs/zh.md)：BiLSTM 的原理。
- [阶段 05 · 24 共指消解](../../24-coreference-resolution/docs/zh.md)、[阶段 05 · 25 实体链接和消歧](../../25-entity-linking/docs/zh.md)：在 NER 的结果上继续做"这些指的是谁 / 链接到知识库中的哪个实体"。
- [阶段 05 · 26 关系抽取与知识图谱构建](../../26-relation-extraction-kg/docs/zh.md)：先抽实体，再抽实体间关系。
- [阶段 05 · 20 Structured Outputs & 约束解码](../../20-structured-outputs-constrained-decoding/docs/zh.md)：LLM 以 JSON 输出抽取结果。
- [阶段 07 · 06 BERT 与掩码语言建模](../../../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/zh.md)：token classification 头的来源。

### 延伸关键词
`seqeval` · `conlleval` · `CoNLL-2003` · `BILOU / BIOES` · `Viterbi` · `sklearn-crfsuite` · `pytorch-crf` · `span-based NER` · `nested NER` · `Aho-Corasick` · `scispaCy / BioBERT` · `word_ids() 标签对齐`
