# 测验 · Evaluation：基准、Evals 与 LM Harness（Evaluation: Benchmarks, Evals, LM Harness）

> **阶段 10 · 从零构建 LLM · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Goodhart 定律 | "当一个指标变成目标，它就不再是好指标"；基准被刷分后，分数上升不等于能力上升 |
| 2 | 三类评测 | Benchmark（便宜、可横向比较、易污染易饱和）→ Custom eval（你的任务你的数据，信号最强、构建成本高）→ Human eval（开放任务的金标准，慢且贵，讲义：$0.10–$2.00/次） |
| 3 | 基准失效的三种机制 | 数据污染（训练语料里有考题）、应试训练（优化训练配比以刷分）、饱和（前沿模型都在 85–90%，差距落入噪声） |
| 4 | Perplexity | `PPL = exp(−(1/N) Σ log P(token_i | context))`；PPL = 10 ≈ 每步在 10 个选项里均匀猜；只能在同一测试集、同一分词口径下比较，是健康检查不是最终结论 |
| 5 | 常用打分函数 | Exact match（结构化输出）、token F1（抽取/短答案）、BLEU/ROUGE（翻译/摘要，讲义：与人类一致率约 60%）、LLM-as-judge（开放生成，约 80%） |
| 6 | LLM-as-judge 的偏差 | 位置偏差（偏好第一个）、冗长偏差（偏好长回答）、自我偏好（偏好同家模型）；对策：随机顺序、长度归一、评委与被测模型不同源、结构化 rubric |
| 7 | ELO 评分 | 期望胜率 `E_A = 1 / (1 + 10^((R_B − R_A)/400))`，更新 `R_A += K(S_A − E_A)`；成对比较比绝对打分更稳，Chatbot Arena 以此排名 |
| 8 | 自建 eval 五步 | 精确定义任务 → 造用例（原型 ≥ 50，生产 ≥ 200，含边界/对抗/多语言）→ 定打分 → 一条命令自动跑 → 随版本追踪趋势 |
| 9 | Pass rate vs mean | 通过率衡量"可靠性"，比平均分更能指导上线决策；均值会被少数满分掩盖大量失败 |
| 10 | 评测框架 | lm-evaluation-harness（标准基准，Open LLM Leaderboard 使用）、RAGAS（RAG 的忠实度/相关性）、promptfoo（YAML 配置的 prompt 回归测试） |

### 核心技能（能动手做到）

- [ ] 用 `EvalCase / EvalSuite` 的抽象写一个"输入 → 预测 → 多个 scorer → 汇总"的 eval 框架
- [ ] 写出带规范化（小写、去标点、去冠词）和多重集合计数的 SQuAD 式 token F1，并解释本节 `token_f1` 的两处偏差
- [ ] 手算 ELO 的期望胜率与一次更新后的分数，并说明在线 ELO 的顺序依赖问题
- [ ] 由逐 token 的 log 概率计算 perplexity，并说明它为什么不能跨 tokenizer 比较
- [ ] 识别"指标说它差、其实答对了"的情形（数值/单位/改写），设计更合适的打分组合
- [ ] 为一个具体业务任务设计 eval：用例分层、阈值、回归跟踪与 model diff
- [ ] 说出至少三种数据污染检测方法

---

## 二、基础自测（选择题）

**Q1.** 讲义认为 MMLU 已经难以区分前沿模型，最主要的原因是：

- A. MMLU 只有英文题目
- B. MMLU 的题目全部来自训练集
- C. 前沿模型普遍在 86%–89% 左右，排行榜被压缩到几个百分点内，差距与统计噪声相当；剩余错题可能本身有歧义或标错
- D. MMLU 是开放式问答，无法自动打分

**Q2.** 一段 4 个 token 的文本，模型给出的对数概率（自然对数）为 `[−0.5, −1.0, −1.5, −2.0]`。其 perplexity 约为：

- A. 3.49
- B. 1.25
- C. 0.29
- D. 5.00

**Q3.** 关于 LLM-as-judge，下列说法**错误**的是：

- A. 评分 prompt 的质量往往比评委模型本身更重要，带 rubric 的结构化 prompt 结果更稳定
- B. 评委存在位置偏差、冗长偏差与自我偏好
- C. 成对比较时随机交换两个回答的顺序，可以缓解位置偏差
- D. 只要评委足够强，就可以用被测模型自己当评委，结果不会有偏差

**Q4.** 用本节 `ELOTracker(k=32)`：A 的分数 1700、B 的分数 1500，结果 B 获胜。B 的分数大约变化多少？

- A. +16.0
- B. +24.3
- C. +7.7
- D. +32.0

**Q5.** 本节代码中 `token_f1("Paris, France", "Paris")` 的返回值是：

- A. 0.0
- B. 0.667
- C. 1.0
- D. 0.5

**Q6.** 关于本节的 `llm_judge_simulated`：

```python
overlap = len(pred_words & exp_words) / len(exp_words)
length_penalty = min(1.0, len(prediction) / max(len(expected), 1))
return round(overlap * 0.7 + length_penalty * 0.3, 3)
```

下列说法正确的是：

- A. `length_penalty` 会惩罚冗长的回答，因此它能缓解讲义所说的冗长偏差
- B. `overlap` 是精确率（precision），回答里多余的词会被扣分
- C. 任何回答只要包含参考答案中的一个词就能得满分
- D. 只要回答字符数不短于参考答案，即使完全答错也能白拿 0.3 分；它实际上**奖励**了长度，模拟出了冗长偏差而不是消除它

**Q7.** 按讲义的建议，自建 eval 的测试用例数量应为：

- A. 原型 5 条即可，生产 20 条
- B. 原型至少 50 条，生产 200 条以上，并包含空输入、对抗输入、歧义输入、其他语言等边界情况
- C. 必须达到 MMLU 的规模（约 1.6 万题）才有意义
- D. 数量不重要，只要覆盖 happy path

**Q8.** 讲义说 pass rate "more actionable than mean score"。最贴切的理由是：

- A. pass rate 的计算更快
- B. pass rate 不依赖任何阈值
- C. pass rate 衡量"有多大比例的请求达到可用标准"，直接对应可靠性；均值可能被少量高分拉高，掩盖大量不合格的输出
- D. pass rate 总是比 mean 高，看起来更好

---

## 三、动手 / 代码题

**Q9.** 本节 `token_f1` 的实现：

```python
def token_f1(prediction, expected):
    pred_tokens = set(prediction.lower().split())
    exp_tokens = set(expected.lower().split())
    ...
    common = pred_tokens & exp_tokens
```

文件开头 `from collections import Counter` 却从未被使用。

1. 指出这个实现与 SQuAD 标准 F1 的两处差异，并分别给出一个会算错的例子。
2. 写一个改进版 `token_f1_squad`，并给出它在 `("Paris, France", "Paris")` 与 `("The capital of France is Paris", "Paris")` 上的值。

**Q10.** 下面是 Model B（"verbose, paraphrase"，被称为 "bad"）逐题的实际打分：

| 问题 | Model B 回答 | 参考答案 | F1 | Judge |
|------|------------|---------|----|-------|
| capital of France | Paris is the capital city of France | Paris | 0.25 | 1.0 |
| 2 + 2 | The answer is four | 4 | 0.0 | 0.3 |
| Hamlet | Shakespeare | William Shakespeare | 0.667 | 0.524 |
| PyTorch | Python | Python and C++ | 0.5 | 0.362 |
| boiling point | 212 Fahrenheit | 100 degrees Celsius | 0.0 | 0.221 |
| speed of light | About 300 million m/s | 299792458 meters per second | 0.0 | 0.233 |
| largest planet | The largest planet is Jupiter | Jupiter | 0.333 | 1.0 |
| WW2 end | World War 2 ended in 1945 | 1945 | 0.286 | 1.0 |

1. 从**事实正确性**看，Model B 有几题实际上是对的？它的 exact match 均值是多少？
2. 这说明了讲义"metric choice matters"的哪一层含义？"bad" 这个命名本身有什么问题？
3. 为这类事实问答设计一个更合理的打分组合（至少覆盖：大小写/标点、数字与英文数词、单位换算、部分正确）。

**Q11.** ELO 锦标赛的实际结果：`concise 1666、verbose 1470、random 1364`，共 24 场。

1. 三个分数之和是多少？为什么？
2. 每场比赛的"裁判"是什么？为什么 concise 一场没输？这个排名能说明 concise 模型"更聪明"吗？
3. 在线 ELO 是**顺序相关**的。把用例和配对顺序都反过来跑一遍，结果变为 `concise 1666.4、verbose 1468.6、random 1365.1`（已实测）。说明为什么会不同，以及更稳健的做法。

**Q12.** perplexity 演示的输出（节选）：

```text
  Text: The quick brown fox jumps over the lazy dog in the garden...
    Strong model (quality=0.9): perplexity = 1.13
    Medium model (quality=0.7): perplexity = 1.44
    Weak model (quality=0.4): perplexity = 2.52
```

1. 讲义说 GPT-2 在 WikiText-103 上 PPL 约 30、Llama 3 8B 约 7，而这里"弱模型"也只有 2.52。这些模拟值为什么不现实？
2. 三种 quality 用的是同一个随机种子（由文本的 sha256 决定）。这样做对比较有什么好处？讲义里的版本用 `hash(text)` 做种子，会有什么问题？
3. 两个模型分别用 32K 和 128K 词表的 tokenizer，在同一段文本上 token 级 PPL 分别为 8 和 10，能否得出"前者更好"？如何公平比较？

---

## 四、面试高频题

**Q13.**（基础必考）公开基准、自建 eval、人工评测各有什么优缺点？为什么讲义说"the only eval that matters is YOUR eval"？

**Q14.**（原理深挖）什么是数据污染？它如何影响基准分数？有哪些检测与缓解方法？

**Q15.**（工程实践）你负责一个"从客服邮件中抽取产品名、问题类别、情感"的 LLM 功能。请设计它的 eval 体系，并说明如何接入日常迭代。

**Q16.**（场景设计）你打算用 LLM-as-judge 评估一个开放式写作助手。如何设计评分流程，如何证明评委"可信"？

**Q17.**（追问型）"模型 A 的 perplexity 比模型 B 低，所以 A 更好"——这句话有什么问题？perplexity 在什么场景下有用？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："GPT-4 scored 86.4%. Claude 3 Opus scored 86.8%. Llama 3 405B scored 88.6%. The leaderboard compressed into a 3-point range where differences are statistical noise"，以及 "The remaining 10-15% of questions may be ambiguous, mislabeled, or require obscure domain knowledge."

- A：语言范围不是讲义给出的理由；
- B：污染是问题之一，但"全部来自训练集"是夸大；
- D：MMLU 是四选一的选择题，恰恰很容易自动打分。

### Q2 — 答案：A

平均负对数似然 `(0.5 + 1.0 + 1.5 + 2.0)/4 = 1.25`，`PPL = e^1.25 ≈ 3.49`（已计算验证）。B 是忘了取指数；C 是 `e^−1.25`，符号反了；D 是把负对数似然求和（0.5 + 1.0 + 1.5 + 2.0 = 5.0）却既没有取平均也没有取指数。代码对应：

```python
avg_neg_log_prob = -np.mean(log_probs)
return float(np.exp(avg_neg_log_prob))
```

### Q3 — 答案：D

讲义列出的失败模式之一是 "self-preference (GPT-4 rates GPT-4 outputs higher than equivalent Claude outputs)"，对策是 "use a different judge than the model being evaluated"。A、B、C 都是讲义原意："The scoring prompt matters more than the model"、三种偏差、"randomize order"。

### Q4 — 答案：B

B 的期望得分 `E_B = 1/(1 + 10^((1700 − 1500)/400)) = 1/(1 + 10^0.5) ≈ 0.240`。B 获胜 `S_B = 1`，变化 `32 × (1 − 0.240) ≈ +24.3`（已用 `expected_score(1500, 1700)` 实测为 0.2403）。A 相应 −24.3。

- A（+16）是双方同分时的变化；
- C（+7.7）是"强者 A 获胜"时 A 的增量 `32 × (1 − 0.760)`；
- D（+32）是 K 的上限，只有在期望胜率为 0 时才会出现。

爆冷时分数变化大、符合预期时变化小，这正是 ELO 的设计。

### Q5 — 答案：A

`"paris, france".split()` 得到 `["paris,", "france"]`，`"paris,"` 带着逗号，与 `"paris"` 不相等，交集为空，F1 = 0。第 4 步"Metric Disagreement Analysis"的实际输出中，"Paris, France" 这一行也是 `EM 0.00  F1 0.00`。这是没有去标点造成的；SQuAD 式规范化会去掉标点，此时 precision = 1/2、recall = 1，F1 = 0.667（即 B，是"修好之后"的值）。

### Q6 — 答案：D

`length_penalty = min(1, len(pred)/len(exp))`：回答越长越接近 1，所以它是"长度奖励"而不是惩罚。实测 `"I don't know"` vs `"Paris"` 得 0.300，`"France"` vs `"Paris"` 也得 0.300；Model C（随机词）全部答错，judge 均值仍有 0.182。

- A 说反了；
- B 错：`overlap` 除以的是 `len(exp_words)`，是召回率（recall），多余的词不扣分，所以 "The capital of France is Paris" 得 1.000；
- C 不准确：参考答案有多个词时（如 "William Shakespeare"），只含一个词拿不到满分（"Shakespeare" 得 0.524）。

### Q7 — 答案：B

讲义："Minimum 50 for a prototype eval, 200+ for production ... Include edge cases: empty inputs, adversarial inputs, ambiguous inputs, inputs in other languages." 本节代码只有 8 条用例，只够演示。

### Q8 — 答案：C

讲义 Key Terms："Fraction of eval cases scoring above a threshold -- more actionable than mean score because it measures reliability." 例如 Model B 的 judge 均值 0.580，但只有 37.5% 的用例达到 0.8。A、D 无依据；B 错：pass rate 恰恰依赖阈值（代码中 `threshold=0.8`）。

### Q9 — 参考答案

1. 两处差异：
   - **没有规范化**：只做了小写，没去标点、冠词。`("Paris, France", "Paris")` → 0（见 Q5）。
   - **用 set 而不是多重集合**：重复词被合并。`token_f1("paris paris paris", "paris")` 实测为 **1.0**——预测里把 "paris" 重复了三次，按多重集合计 precision 应为 1/3、F1 = 0.5。SQuAD 官方实现用 `Counter` 求交集：`sum((Counter(p) & Counter(g)).values())`。代码导入了 `Counter` 却没用，很可能就是这一步被省略了。
2. 改进版：

```python
import re, string
from collections import Counter

def normalize(s):
    s = s.lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())

def token_f1_squad(prediction, expected):
    p, g = normalize(prediction).split(), normalize(expected).split()
    if not p or not g:
        return float(p == g)
    common = sum((Counter(p) & Counter(g)).values())
    if common == 0:
        return 0.0
    precision, recall = common / len(p), common / len(g)
    return 2 * precision * recall / (precision + recall)
```

   - `("Paris, France", "Paris")`：规范化后 `["paris", "france"]`，common = 1，P = 0.5，R = 1，**F1 = 0.667**。
   - `("The capital of France is Paris", "Paris")`：去掉 "the" 后 `["capital", "of", "france", "is", "paris"]`，P = 1/5，R = 1，**F1 = 0.333**（原实现是 0.29，因为 "the" 也算进了分母）。

   注意：规范化去标点后 "C++" 会变成 "c"，"m/s" 变成 "ms"；领域任务应按需定制规范化规则。

### Q10 — 参考答案

1. 按事实判断：France（对）、four（对）、Shakespeare（对）、212 Fahrenheit（对，100°C = 212°F）、About 300 million m/s（对，近似值）、Jupiter（对）、1945（对）；"Python" 只答对一半（PyTorch 核心是 C++）。约 **7 题正确、1 题部分正确**，但 exact match 均值为 **0.000**，token F1 均值 0.254。
2. 含义有两层：
   - 同一组输出，换一个指标就能从"全错"变成"大部分对"（judge 均值 0.580），指标决定结论；
   - 更深一层：**参考答案的表面形式本身就是一种偏见**。EM/F1 衡量的是"和参考答案长得多像"，不是"对不对"。把 Model B 命名为 "bad" 恰好是被指标带偏的结论；讲义 Step 6 的说法 "The 'bad' model gives verbose paraphrases" 也承认它只是更啰嗦。真实项目里，这种情况会让你误杀一个更好的模型。
3. 一个可行组合：
   - 先做规范化（大小写、标点、冠词、空白），并把英文数词转成数字（"four" → "4"）；
   - **包含匹配**：规范化后的参考答案是否作为完整短语出现在回答中（"Paris is the capital..." 命中）；
   - **数值答案**：抽取数字和单位，统一单位后按相对误差判定（212°F → 100°C；3×10^8 m/s 与 299,792,458 m/s 相对误差 < 1%）；
   - **多要素答案**（"Python and C++"）：按要素计召回，给部分分；
   - 以上规则覆盖不了的，用带 rubric 的 LLM-as-judge，并在 50–100 条人工标注样本上校准它与人的一致率。

### Q11 — 参考答案

1. `1665.9 + 1470.3 + 1363.8 = 4500.0 = 3 × 1500`。每场比赛 A 增加 `K(S_A − E_A)`，B 增加 `K(S_B − E_B)`，而 `S_A + S_B = 1`、`E_A + E_B = 1`，两者之和恒为 0，总分守恒（零和）。
2. 裁判是 `token_f1(pred, case.expected)`，并带 0.01 的平局阈值。concise 模型的回答**逐字等于参考答案**（实际上是按测试题写死的查表），F1 永远是 1.0，不可能输。这个排名衡量的是"与参考答案的形式一致度"，加上 Q10 的分析，它不能说明 concise 更"聪明"。另一个细节：verbose 与 random 有 3 场平局（比如 "2 + 2"，两者 F1 都是 0）。讲义说这 "exactly the system Chatbot Arena uses"，但 Arena 的裁判是**人类投票**，用 F1 当裁判只是把 Step 1 的结论换了个形式再算一遍。
3. 在线 ELO 每场之后立即更新分数，后续比赛的期望胜率取决于当时的分数，所以**同一组比赛结果按不同顺序处理，最终分数不同**。更稳健的做法：
   - 用 Bradley–Terry 模型对全部比赛结果做最大似然拟合（与顺序无关），再换算到 ELO 刻度；
   - 或多次随机打乱顺序求均值，并用 bootstrap 给出置信区间；
   - 报告排名时附上置信区间，区间重叠就不宣称"谁更强"。

### Q12 — 参考答案

1. 模拟器给每个"词"的概率在 `quality ± 噪声` 附近（strong 时多在 0.82–0.99），等于假设模型对下一个词有 80%–99% 的把握。真实语言模型在开放文本上，平均到每个 token 的概率远低于此，因此真实 PPL 是几到几十。另外这里按空格切"词"，不是按 tokenizer 切 token。这些数字只用来说明"质量越高，PPL 越低"的单调关系，不能与讲义的真实数值对照。
2. 好处：三个"模型"使用完全相同的噪声序列（common random numbers），差异只来自 `quality`，比较更干净；同一文本每次运行结果一致，可复现。讲义版本用 Python 内置 `hash(text)`：从 Python 3.3 起，字符串哈希默认按进程随机加盐（`PYTHONHASHSEED`），每次运行种子不同，结果不可复现。代码改用 `hashlib.sha256` 修正了这一点。副作用是 `np.random.seed` 改动了**全局**随机状态，在大程序里可能干扰别的随机代码；更好的写法是 `rng = np.random.default_rng(seed)`。
3. 不能。token 级 PPL 的"每一步"对应的文本量不同：大词表切出的 token 更少、每个 token 更"大"，单个 token 更难猜，token 级 PPL 天然偏高。公平比较的做法：把总负对数似然除以**字符数或字节数**，得到 bits-per-byte / bits-per-character，或换算成词级 PPL（总 NLL / 词数）；并确保测试集相同、无污染。

### Q13 — 参考回答要点

- **公开基准**（MMLU、HumanEval、SWE-bench、MATH……）：便宜、标准化、可横向比较，适合粗选模型；缺点是会被污染、会被应试优化、会饱和，且与你的任务分布不一致。讲义：HumanEval 只测函数级生成，"says nothing about debugging, refactoring, or explaining code across files"。
- **自建 eval**：输入、期望输出、打分函数都来自你的业务，"the only evaluation that predicts production performance"；缺点是构建与维护成本高。
- **人工评测**：开放式任务的金标准（Chatbot Arena 有 200 万以上投票），缺点是贵（$0.10–$2.00/次）、慢（数小时到数天）、标注员之间也有分歧。
- **组合方式**：基准粗筛 → 自建 eval 做主要决策 → 人工评测仲裁模糊案例（讲义的流程图）。
- 加分点：讲义开头的例子，MMLU 88.7% 的模型一度数不清 "strawberry" 里有几个 r，说明基准分与"实际可靠性"之间有落差。

### Q14 — 参考回答要点

- **定义**：评测题目（或其改写）出现在训练数据中，模型"见过答案"，分数虚高而能力未变。讲义："web-scale scraping makes it nearly impossible to exclude"。
- **影响**：分数上升不可信，尤其在静态、公开、长期不变的基准上；排行榜上的微小差距可能完全来自污染。
- **检测方法**：
  - n-gram 重叠：在训练语料中查找评测题的长 n-gram（如 13-gram）命中率（讲义练习 4）；
  - 改写/扰动测试：把题目换个说法、换选项顺序、改数字，若分数显著下降，说明在背题；
  - 基于似然：对比模型在原题与改写题上的 perplexity，原题异常低是可疑信号；
  - 时间切分：只用模型训练截止日期之后出现的新题评测；
  - canary 字符串：在发布的评测集中埋入唯一标记，检查模型能否复述。
- **缓解**：私有/保留测试集、动态更新的基准、发布时报告去污染流程、以自建 eval 为准。
- 加分点：本节代码的 `demo_model_good` 是"按题目写死答案的查表"，是污染的极端形式——它在本 eval 上拿 100%，换一道新题就只会说 "I don't know"。

### Q15 — 参考回答要点

- **任务定义**：输入一封邮件，输出 JSON `{product, category, sentiment}`；category 是 5–10 个固定类别之一。
- **用例**：先收集 200 条以上真实邮件（脱敏），按 40% 常见 / 40% 边界 / 20% 历史回归分层（参考本节 `outputs/prompt-eval-designer.md`）；边界包括多产品、多类别、空邮件、外语、讽刺语气、超长转发链。
- **打分**：
  - JSON 可解析率与 schema 合规率（硬门槛）；
  - category、sentiment 用 exact match，统计每类的 precision/recall 和混淆矩阵；
  - product 用规范化后的 exact match 或 token F1（允许别名表）；
  - 汇总为 pass rate：三项全对才算通过。
- **自动化与跟踪**：一条命令跑完；结果带 prompt 版本、模型版本、时间戳存档；接入 CI，prompt 或模型变更必须跑 eval；实现 "model diff"（练习 5），列出每条用例是改进、退化还是不变。
- **上线后**：抽样线上请求做人工复核，把新发现的失败加入回归集。
- 常见误区：只报一个平均分；只用合成数据；不给 eval 做版本管理。

### Q16 — 参考回答要点

- **rubric**：按维度（切题、事实、结构、语言）给出分档描述，例如"5 分：完全满足要求且无事实错误……"；要求评委先写理由再打分；输出结构化 JSON。
- **偏差控制**：
  - 成对比较时两种顺序各评一次，不一致视为平局（位置偏差）；
  - 在 rubric 中明确"长度不是加分项"，或对长度做归一化/分层分析（冗长偏差）；
  - 评委模型与被测模型不同家族（自我偏好）；
  - 参考答案可选：有参考时评"一致性"，无参考时评"质量"。
- **证明可信**：抽 100–200 条，让 2–3 名人工标注，计算人与人、人与评委的一致率（如 Cohen's kappa 或 Spearman 相关）；评委与人的一致率接近人与人之间的一致率才可用；定期复检，评委模型升级时重新校准。
- **成本**：讲义给出 GPT-4o-mini 约 $0.01/次；可以先用规则过滤明显失败，再交给评委。
- 常见误区：用 "Rate this response 1-10" 这种模糊 prompt；本节 `llm_judge_simulated` 那种"长度越长分越高"的打分正是要避免的。

### Q17 — 参考回答要点

- **问题 1：口径**。只有在**同一测试集、同一分词方式**下 PPL 才可比；不同 tokenizer 应换算为 bits-per-byte（见 Q12）。
- **问题 2：测的东西不同**。PPL 衡量"预测下一个 token 的能力"，讲义："says nothing about instruction following, reasoning, or factual accuracy"；可以靠擅长常见模式拿到低 PPL，而在罕见但重要的模式上很差。
- **问题 3：对齐后的模型**。SFT/RLHF 之后的聊天模型在通用语料上的 PPL 往往比基座模型高，但实际可用性更好。
- **问题 4：污染**。测试集出现在训练数据中会让 PPL 异常低。
- **适用场景**：预训练过程中的健康检查（loss 与 PPL 曲线）、同一模型不同 checkpoint 的比较、量化前后的退化检测（下一节会用到）、领域语料适配程度的判断。
- 加分点：PPL = `exp(交叉熵)`，PPL 与训练 loss 是同一量的两种表示；阶段 10 · 04 中初始 loss ≈ ln(V) 对应 PPL ≈ V。

---

## 六、关联知识点

### 前置知识
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：准确率、精确率、召回率、F1 等基础指标。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：交叉熵与 perplexity 的关系。
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：训练 loss 与 perplexity 是同一个量。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：常用评测框架的 NLP 视角。

### 本节被哪些后续内容用到
- [阶段 10 · 11 Quantization：让模型装得下](../../11-quantization/docs/zh.md)：用 perplexity 衡量量化带来的质量损失。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：应用层的 eval 与回归测试。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../../14-agent-engineering/19-benchmarks-swebench-gaia/docs/zh.md)、[阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：Agent 场景下的评测。
- [阶段 05 · 28 长上下文 Evaluation](../../../05-nlp-foundations-to-advanced/28-long-context-evaluation/docs/zh.md)：针对长上下文能力的专门基准。
- [阶段 19 · 49 语言模型 Evaluation Harness](../../../19-capstone-projects/49-lm-eval-harness/docs/zh.md)、[阶段 19 · 71 经典评估指标](../../../19-capstone-projects/71-classical-metrics/docs/zh.md)、[阶段 19 · 73 Perplexity 与 Calibration](../../../19-capstone-projects/73-perplexity-calibration/docs/zh.md)、[阶段 19 · 74 排行榜汇总](../../../19-capstone-projects/74-leaderboard-aggregation/docs/zh.md)：综合项目中把本节各部分做成完整工具。

### 延伸关键词
`Goodhart's Law` · `data contamination` · `benchmark saturation` · `perplexity / bits-per-byte` · `SQuAD F1` · `BLEU / ROUGE` · `LLM-as-judge` · `position bias / verbosity bias` · `ELO / Bradley–Terry` · `Chatbot Arena` · `lm-evaluation-harness` · `RAGAS` · `promptfoo` · `pass rate` · `model diff`
