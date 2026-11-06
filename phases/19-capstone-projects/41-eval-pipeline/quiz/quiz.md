# 测验 · 完整 Evaluation 流程（Capstone Lesson 41: Full Evaluation Pipeline）

> **阶段 19 · 综合项目 · 第 41 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 单一指标不够 | perplexity 衡量"拟合语言分布"，exact-match 衡量"逐字正确"，token F1 容忍改写，LLM-as-judge 衡量定性质量；每个指标都有其它指标弥补的盲区 |
| 2 | eval 的统一接口 | 每个 eval 都是 `(model, tok, dataset) -> EvalResult`，结果带 `name`、`metric`、`n_examples`、逐样本 `records` 和 `extras` |
| 3 | 困惑度的正确计数 | `ppl = exp(Σ NLL / Σ 有效 token 数)`；分母只数非 pad 的**目标**位置，先求和最后再除，而不是平均每条/每批的 ppl |
| 4 | next-token 对齐 | 位置 `i` 的 logits 预测位置 `i+1` 的 token：`pred = logits[:, :-1]`、`target = ids[:, 1:]`、`mask = attn[:, 1:]`；错位不会报错，只会让数字失去意义 |
| 5 | exact-match 归一化 | 小写 → 去首尾空白 → 折叠连续空格 → 去掉结尾的 `.!?`；`"Paris."`、`"  paris  "` 都算对 |
| 6 | token F1 | 词袋多重集交集：`P = 交集/len(pred)`、`R = 交集/len(ref)`、`F1 = 2PR/(P+R)`；两边都空 = 1，只有一边空 = 0 |
| 7 | mock LLM-as-judge | 确定性打分：归一化后完全相等 5 分，F1 ≥ 0.8 → 4，[0.5, 0.8) → 3，[0.2, 0.5) → 2，否则 1；接口 `(instruction, prediction, reference) -> JudgeVerdict`，换真模型只改一个函数 |
| 8 | 归一化到 [0, 1] | perplexity → `1/(1+ln ppl)`（ppl=1 → 1，ppl=e → 0.5）；EM、F1 原样截断；judge ÷ 5 |
| 9 | 加权聚合 | 默认权重 0.2 / 0.3 / 0.3 / 0.2；只出现部分 eval 时权重按出现的项重新归一化；权重是**产品决策** |
| 10 | 报告的三层结构 | 顶层 aggregate → 四个分项 → 逐样本明细；JSON 用稳定键，便于 CI 画趋势线、定位回归 |

### 核心技能（能动手做到）

- [ ] 用 PyTorch 写出带 padding 掩码、正确错位的 held-out 困惑度计算，并说明为什么"先累加再相除"
- [ ] 手算任意两句话的 exact-match 与 token F1（包括标点、重复词、空串等边界情况）
- [ ] 按 rubric 手推 mock judge 给出的 1–5 分，并能把 `judge_fn` 换成任意同签名函数
- [ ] 手算 `normalise_metric` 与加权 aggregate，解释为什么随机模型的 aggregate 也不为 0
- [ ] 读懂 `generate_greedy` 的停止条件，说清本次运行中生成为何会在 `"5."` 之后停下
- [ ] 识别本节 demo 的"训练集即评测集"问题，并改造出真正 held-out 的评测切分

---

## 二、基础自测（选择题）

**Q1.** `perplexity_eval` 先把所有非 pad 位置的 NLL 累加、再除以总 token 数，最后取 `exp`。为什么不直接对每条序列（或每个 batch）算出 ppl 再求平均？

- A. 因为困惑度对 batch 数据没有定义
- B. 两种做法在数学上完全等价，只是写法不同
- C. 因为 pad 位置必须参与平均才能保证数值稳定
- D. 平均每条/每批 ppl 会给短序列与长序列同样的权重，并且 `exp` 是凸函数，先 `exp` 再平均会系统性偏高；只有"按 token 累加"才符合教科书定义

**Q2.** 在 `perplexity_eval` 中，已经有 `pred = logits[:, :-1, :]` 与 `target = ids[:, 1:]`。用来排除 pad 目标的掩码应当是：

- A. `attn[:, 1:]`
- B. `attn[:, :-1]`
- C. `attn`（不切片）
- D. 不需要掩码，`F.cross_entropy` 会自动忽略 `PAD_ID`

**Q3.** `normalise_for_em("  The   Sky.. ")` 的返回值是：

- A. `"the sky.."`
- B. `"The Sky"`
- C. `"the sky"`
- D. `"the  sky"`

**Q4.** `token_f1_score("the sky was", "the sky is blue")` 的值最接近：

- A. 0.500
- B. 0.571
- C. 0.667
- D. 0.400

**Q5.** 用本节的 `mock_judge` 给下面这对打分：prediction = `"Paris"`，reference = `"the capital of france is paris."`。得分是：

- A. 1
- B. 3
- C. 4
- D. 5

**Q6.** 关于 `normalise_metric("perplexity", ppl) = 1 / (1 + log(max(ppl, 1)))`，下列说法正确的是：

- A. ppl = 1 时归一化值为 0
- B. ppl 越大，归一化值越大
- C. 这里的 `log` 是以 10 为底的对数
- D. ppl ≈ 2.718 时归一化值为 0.5；本次运行 ppl = 11.315 时约为 0.292

**Q7.** 只把 `EvalResult(name="exact_match", metric=0.5)` 和 `EvalResult(name="token_f1", metric=0.5)` 两项传给 `aggregate()`（使用默认权重），得到的 `aggregate` 是：

- A. 0.3（缺失的两项按 0 分计入）
- B. 抛出 `ValueError`，因为四项必须齐全
- C. 0.5
- D. 0.6

**Q8.** 本次实际运行 demo 得到 `exact_match = 0.150`（20 题对 3 题）。查看 `report.json` 的逐样本记录后，下列判断最准确的是：

- A. 模型学会了回答首都类问题
- B. 命中的 3 题都是算术题：模型对所有 `Compute ...` 几乎都输出 `"5."` 或 `"4."`，恰好撞上答案 5、5、4；而且这些题本身就在训练集里
- C. EM = 0.15 说明模型答案中 15% 的 token 是正确的
- D. 命中的 3 题说明模型具备了真正的泛化能力，因为 EM 评测集是 held-out 的

---

## 三、动手 / 代码题

**Q9.** 阅读 `generate_greedy` 的停止逻辑：

```python
        next_id = int(logits[0, -1, :].argmax().item())
        if next_id == tok.PAD_ID or next_id == tok.INST_ID or next_id == tok.RESP_ID:
            break
        ids.append(next_id)
        out_chars.append(next_id)
        if (
            len(out_chars) >= 2
            and out_chars[-1] in sentence_ends
            and out_chars[-2] in sentence_ends
        ):
            break
```

1. 这段代码有哪几种停止生成的方式？"遇到一个句号就停"是其中之一吗？
2. 本次运行中 `Compute 2 + 3.` 的输出是 `"5."`，长度远小于 `max_new_tokens=48`。实际是哪个条件让它停下的？为什么训练后的模型会这样？
3. 这种"停止"是被设计出来的吗？如果想让模型可靠地停止，训练数据应当怎么改？

**Q10.** 讲义把 perplexity 称为 "held-out perplexity"，架构图里也写着 "held-out fixtures"。但 `train_small` 的训练数据是：

```python
    for text in LM_CORPUS:
        pairs.append(tok.encode_text(text, cfg.max_len))
    for inst, ref in EM_PAIRS:
        ids, _ = tok.encode_pair(inst, ref, cfg.max_len)
        pairs.append(ids)
```

而 `run_demo` 评测时用的是 `perplexity_eval(model, tok, LM_CORPUS, ...)` 和 `exact_match_eval(model, tok, EM_PAIRS)`。

1. 指出问题所在，说明它会让哪两个指标偏乐观。
2. 用同一个训练好的模型，在两句从未见过的句子上测得 ppl = 26.60，而在 `LM_CORPUS` 上是 11.315。这个差距说明什么？
3. 给出一个修改 `run_demo` 的方案，让四个 eval 都真正 held-out。

**Q11.** 讲义说 token F1 "matches the SQuAD evaluation reference"。但本节 `tokenize_text` 只做小写和空白切分，**不去标点、不去冠词**。

1. 计算本节实现下 `token_f1_score("the capital of france is paris.", "The capital of France is Paris")` 的值。
2. 写一个 SQuAD 风格的 `squad_normalise(text)`（小写、去标点、去 `a/an/the`、折叠空白），并给出上面这对以及 `("Paris", "the capital of france is paris.")` 在新规则下的 F1。
3. 这对 mock judge 的打分会产生什么影响？

**Q12.** 用默认权重手算：完全**未训练**的模型（`torch.manual_seed(0)` 初始化）实测 `ppl = 318.15`、`EM = 0`、`F1 = 0`、`judge = 1.0`，aggregate 是多少？为什么它不是 0？请提出一种让"最差模型 ≈ 0 分"的归一化改法，并计算本次训练后模型（ppl 11.315、EM 0.15、F1 0.02、judge 1.0）在改法下的 aggregate。

---

## 四、面试高频题

**Q13.**（基础必考）为什么评估一个语言模型不能只看一个指标？perplexity、exact-match、token F1、LLM-as-judge 各衡量什么，各自的盲点是什么？

**Q14.**（原理深挖）计算困惑度时有哪些常见陷阱？为什么两个使用不同 tokenizer 的模型，其困惑度不能直接比较？

**Q15.**（工程实践）把本节的 mock judge 换成真实的前沿模型做 LLM-as-judge，你要处理哪些问题才能让分数可信？

**Q16.**（场景设计）你要把这条 eval pipeline 接入训练团队的 CI，用于每次 checkpoint 的回归检测。你会怎么设计数据、报告和告警规则？

**Q17.**（追问型）aggregate 是四个指标的加权平均。这种"单一总分"有什么问题？权重应该怎么定？有没有替代方案？

---

## 五、参考答案与解析

### Q1 — 答案：D

正确定义是 `ppl = exp(Σ_所有有效位置 NLL / 有效位置总数)`。若先算每条序列的 ppl 再平均：一是不同长度序列被等权，短序列（方差更大）被过度加权；二是 `exp` 是凸函数，由 Jensen 不等式，`mean(exp(nll_i)) ≥ exp(mean(nll_i))`，结果系统性偏高。本次实际运行：按 token 累加得 **11.315**；逐条 ppl 的算术平均为 **11.416**；逐条平均 NLL 再取 exp 为 11.217——三个数都不同。

- A 错：困惑度对任意 token 集合都有定义。
- B 错：只有所有序列长度相同、且先平均 NLL 时才等价。
- C 错：pad 位置必须**排除**，计入会让分母变大、ppl 看起来更好（讲义："Padding tokens have to be excluded from the denominator or perplexity will look better than it is"）。

### Q2 — 答案：A

掩码必须与**目标**位置对齐。`target = ids[:, 1:]`，所以目标是否为 pad 由 `attn[:, 1:]` 决定，代码注释也写着 `# exclude pad targets`。

- B 错：`attn[:, :-1]` 对齐的是**输入**位置，最后一个真实 token 预测 pad 的位置会被错误计入，而第一个 pad 目标会被漏掉。
- C 错：形状对不上（长 1）。
- D 错：`F.cross_entropy` 只会忽略 `ignore_index`（默认 -100），不知道 `PAD_ID = 258`；本节代码用 `reduction="none"` 后乘掩码手动排除。另一种等价写法是把 pad 目标改成 `-100`。

### Q3 — 答案：C

`normalise` 依次做：`lower()` → `strip()` 得 `"the   sky.."` → 反复把两个空格替换成一个得 `"the sky.."`；`strip_trailing_punctuation` 用 `while` 循环去掉**所有**结尾的 `.!?`，得 `"the sky"`。

- A 漏了去结尾标点；B 漏了小写和空白处理；D 漏了折叠空白。
- 补充：`normalise` 只折叠**空格**，不处理 `\t`、`\n`。实测 `exact_match_score("carbon\ndioxide", "carbon dioxide") == 0`，与讲义"collapse internal whitespace runs"不完全一致。

### Q4 — 答案：B

pred 词元 `[the, sky, was]`（3 个），ref `[the, sky, is, blue]`（4 个），交集 `{the, sky}` = 2。`P = 2/3`、`R = 2/4 = 0.5`、`F1 = 2·(2/3)·0.5 / (2/3 + 0.5) = 0.5714`。这正是测试 `test_partial_overlap_is_between_zero_and_one` 断言的值。

- A 是 recall；C 是 precision；D 无对应计算。

### Q5 — 答案：A

1. 归一化后 `"paris"` ≠ `"the capital of france is paris"`，不是 5 分。
2. 计算 token F1：pred 词元 `[paris]`，ref 词元 `[the, capital, of, france, is, paris.]`——注意 ref 最后一个词元是带句点的 `"paris."`，`tokenize_text` 不去标点，所以交集为 0，F1 = 0 → **1 分**（rationale 为 `low token overlap (F1=0.00)`，已实际运行验证）。

即使去掉句点，F1 = `2·1·(1/6)/(1+1/6) ≈ 0.286`，也只有 2 分。一个**内容完全正确的简短答案**被判为最差或次差，这暴露了"基于词重叠的 mock judge"的根本局限：它衡量的是表面重叠，不是语义正确性。B、C、D 都高估了词重叠。

### Q6 — 答案：D

`math.log` 是自然对数。ppl = e 时 `1/(1+1) = 0.5`；ppl = 11.315 时 `ln 11.315 ≈ 2.426`，`1/3.426 ≈ 0.292`，与 `EVAL REPORT` 表中的 `0.292` 一致。

- A 错：ppl = 1 时 `ln 1 = 0`，归一化值为 **1**（最好）。
- B 错：方向相反，ppl 越大越接近 0，单调递减。
- C 错：Python 的 `math.log(x)` 默认以 e 为底。

### Q7 — 答案：C

`aggregate` 只对**实际出现的** eval 取权重：`total_w = 0.3 + 0.3 = 0.6`，归一化后各 0.5，aggregate = `0.5·0.5 + 0.5·0.5 = 0.5`。测试 `test_aggregate_handles_subset_of_evals` 就验证了这一点。

- A 错：缺失项不参与计算，不会按 0 计。
- B 错：不要求四项齐全。只有当名字不在 `normalise_metric` 已知集合中时才会抛 `ValueError: unknown metric name`（实测传入 `"bleu"` 会报错）。
- D 错：无对应计算。

### Q8 — 答案：B

实际 `report.json` 中，命中的 3 题是 `Compute 2 + 3.` → `"5."`、`Compute 9 - 4.` → `"5."`、`Compute 20 / 5.` → `"4."`；其余 `Compute 7 + 8.`、`Compute 6 * 3.` 也输出 `"5."`，于是答错。EM 归一化会去掉结尾句点，所以 `"5."` 与 `"5"` 匹配。这是"常数猜测碰巧命中"，不是学会了算术。另外 `EM_PAIRS` 就在 `train_small` 的训练数据里，EM 测的是训练集。

- A 错：首都题的预测是 `'pr it 5 4e ite cal ithe 3atithe '` 这类乱码。
- C 错：EM 是"整串完全匹配的样本比例"，与 token 无关。
- D 错：EM 评测集并非 held-out（见 Q10）。

### Q9 — 参考答案

1. 共有四种停止方式：
   - 生成的 `next_id` 是三个特殊 token 之一（`PAD_ID`、`INST_ID`、`RESP_ID`）；
   - **连续两个**字符都是 `.!?`（例如 `".."`、`"?!"`）；
   - `len(ids) >= model.max_len`（上下文用满）；
   - 循环跑满 `max_new_tokens = 48`。
   单个句号**不会**触发停止——条件要求 `out_chars[-1]` 和 `out_chars[-2]` 都是句末标点。
2. 实测：生成 `"5."` 之后，模型 argmax 给出的是 **`RESP_ID = 257`**，命中第一个条件而停止（逐步调试已验证，`What is the capital of Japan?` 也是在 `"... 2."` 之后因预测 257 停下）。原因在训练数据：每条 EM 训练样本都是 `[INST] 指令文本 [RESP] 答案`，而**所有指令都以 `.` 或 `?` 结尾**，紧接着就是 `RESP`。模型学到了"句号/问号之后是 `RESP`"这一高频模式，于是在生成中写出句号后就预测 `RESP`。
3. 这是**偶然**的，不是设计出来的：讲义和代码都没有 EOS token，答案后面什么也没有，模型从未学过"答案结束"。可靠做法：
   - 在词表中加一个 `EOS`（例如用空闲的 ID 259，当前 `VOCAB = 260` 恰好空出一个），训练时在每个答案后追加 `EOS`，生成时遇 `EOS` 停止；
   - 训练 SFT 数据时只对答案部分算 loss（`encode_pair` 已返回 `resp_start`，`IGNORE_INDEX = -100` 已定义但未被使用），避免模型把精力花在拟合指令上。

### Q10 — 参考答案

1. **训练集即评测集**：`LM_CORPUS` 和 `EM_PAIRS` 同时用于训练与评测。perplexity 测的是对训练文本的拟合程度，EM 测的是对训练答案的记忆程度，两者都偏乐观。（`F1_PAIRS` 与 `JUDGE_SET` 没参与训练，所以这两项接近最差分——这本身也说明模型没有泛化。）讲义第 41 课图中的 "held-out fixtures" 与代码不符。
2. 实测：同一个模型在两句新句子（`"the cat sat quietly on the warm mat by the door."`、`"machine learning models need careful evaluation on new data."`）上 ppl = **26.60**，是训练语料 11.315 的约 2.35 倍。差距就是"泛化缺口"（generalization gap）：在训练数据上报告的困惑度不能代表模型对新文本的建模能力。
3. 修改方案（示意）：

```python
rng = random.Random(cfg.seed)
lm = LM_CORPUS[:]; rng.shuffle(lm)
lm_train, lm_eval = lm[:15], lm[15:]          # 75/25 切分
em = EM_PAIRS[:];  rng.shuffle(em)
em_train, em_eval = em[:14], em[14:]

losses = train_small(model, tok, cfg, lm_texts=lm_train, em_pairs=em_train)  # 给 train_small 加参数
ppl_res = perplexity_eval(model, tok, lm_eval, cfg.max_len)
em_res  = exact_match_eval(model, tok, em_eval)
```

   要点：切分要用固定种子以保证可复现；报告里写明训练/评测各多少条；生产中还要做 **去污染（decontamination）**，例如用 n-gram 重叠检查评测样本是否出现在预训练语料中。

### Q11 — 参考答案

1. 本节实现：pred 词元 `[the, capital, of, france, is, paris.]`，ref 词元 `[the, capital, of, france, is, paris]`，`"paris."` ≠ `"paris"`，交集 5，`P = R = 5/6`，**F1 = 0.8333**（已运行验证）。一个句点就让 F1 掉了 1/6。

2. 参考实现：

```python
import re, string

def squad_normalise(text: str) -> str:
    s = text.lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))   # 去标点
    s = re.sub(r"\b(a|an|the)\b", " ", s)                              # 去冠词
    return " ".join(s.split())                                         # 折叠所有空白
```

   新规则下（已运行验证）：
   - `("the capital of france is paris.", "The capital of France is Paris")` → 两边都是 `"capital of france is paris"`，**F1 = 1.0**；
   - `("Paris", "the capital of france is paris.")` → pred `[paris]`、ref `[capital, of, france, is, paris]`，`P = 1`、`R = 0.2`，**F1 = 0.333**（原实现为 0）。

3. 对 mock judge 的影响：judge 内部调用 `token_f1_score`，所以 Q5 那个"简短但正确"的答案会从 1 分升到 2 分（F1 落在 [0.2, 0.5)）；而 `JUDGE_SET` 中所有带句点的参考答案，与不带句点的预测之间的重叠都会上升。结论：**归一化规则是指标定义的一部分**，改动它会改变所有历史分数，因此要版本化，不能悄悄修改。

### Q12 — 参考答案

**未训练模型的 aggregate**：

| 项 | 原始值 | 归一化 | 权重 | 贡献 |
|----|--------|--------|------|------|
| perplexity | 318.15 | `1/(1+ln 318.15) = 0.148` | 0.2 | 0.0296 |
| exact_match | 0 | 0 | 0.3 | 0 |
| token_f1 | 0 | 0 | 0.3 | 0 |
| judge | 1.0 | `1/5 = 0.2` | 0.2 | 0.04 |
| **合计** | | | | **0.0696** |

（已实际运行验证：0.06957。）

**为什么不是 0**：
- judge 的最低分是 1 而不是 0，`÷5` 后最差也有 0.2，这个"地板"白送 0.04；
- perplexity 的归一化只在 ppl → ∞ 时才趋于 0，而一个随机模型的 ppl 是几百量级，仍能得到约 0.15。

**改法**：
- judge 用 `(score − 1) / 4`，1 分 → 0、5 分 → 1；
- perplexity 用"相对均匀猜测"的归一化：`max(0, 1 − ln(ppl) / ln(V))`，V 为词表大小（这里 260）。均匀分布的 ppl = V 时为 0、ppl = 1 时为 1。

改法下（已计算）：
- 未训练模型：perplexity 项 `1 − ln 318.15 / ln 260 ≈ −0.036` 截断为 0，judge 项 0，aggregate = **0.0**；
- 训练后模型：perplexity 项 `1 − 2.426/5.561 ≈ 0.564`，aggregate = `0.2·0.564 + 0.3·0.15 + 0.3·0.02 + 0` ≈ **0.164**（原公式为 0.149；只改 judge 而不改 perplexity 时为 0.109）。

额外发现：`run_demo` 在 `aggregate <= 0` 时返回 1 作为失败信号，但由于 judge 的地板，aggregate 不可能 ≤ 0（至少 0.04），这个检查实际上永远不会触发。

### Q13 — 参考回答要点

- **perplexity**：衡量模型对语言分布的拟合（讲义："says how well the model fits the language distribution but says nothing about whether it answers questions"）。盲点：不反映指令遵循与答案正确性；依赖 tokenizer；不适合比较经过 RLHF/SFT 的对话模型。
- **exact-match**：衡量短答案是否逐字正确。盲点：惩罚正确的改写（"Paris" vs "The capital is Paris"），对长答案几乎总是 0。
- **token F1**：词袋重叠，容忍改写与词序。盲点：被"词汇重叠但内容错误"欺骗（讲义："is fooled by lexical overlap with wrong content"），例如 "the sun moves from west to east" 与参考答案重叠很高但事实相反；对否定词不敏感。
- **LLM-as-judge**：能评估流畅度、有用性、推理质量等定性维度。盲点：昂贵、随机，有位置偏差、长度偏差、自我偏好等。
- 结论：每个指标覆盖一个其它指标遗漏的维度；报告要并排展示，审阅者才能看到模型在哪些维度上做了取舍（例如 EM 低但 judge 高 → 多为改写型正确答案）。
- 加分点：本次运行中 F1 = 0.02 与 judge = 1.0 一致地显示模型完全没有泛化到未训练过的 F1/judge 集，而 EM = 0.15 来自训练集 + 常数猜测——**多指标交叉对照才能看穿单一数字**。

### Q14 — 参考回答要点

- **常见陷阱**：
  1. **padding 计入分母**：会让 ppl 偏低（看起来更好）。
  2. **off-by-one**：logits 位置 `i` 预测 token `i+1`；错位后 loss 照样能算、甚至照样能训练，但指标毫无意义。
  3. **平均方式**：应当 `exp(Σ NLL / Σ tokens)`，而不是平均每批/每条 ppl（Jensen 不等式使后者偏高，本次 11.416 vs 11.315）。
  4. **首 token 无法被预测**：没有 BOS 时每条序列的第一个 token 不计分。本次 20 条语料共 1,149 字节，实际计分 1,129 个位置。
  5. **截断与上下文长度**：长文档被截断会丢掉位置；滑动窗口评估时要注意 stride，否则重复计数或上下文不足。
  6. **训练集上测 ppl**：不是 held-out，见 Q10。
- **跨 tokenizer 不可比**：ppl 是"每个 token"的平均不确定性。词表不同，同一段文本切出的 token 数不同（字节级 vs BPE 可差数倍），每个 token 承载的信息量也不同。应改用与 tokenizer 无关的指标，如 **bits-per-byte / bits-per-character**：`BPB = Σ NLL / (总字节数 · ln 2)`。
- 加分点：本节是字节级 tokenizer，ppl 本身就近似"每字节困惑度"；随机初始化时 ppl 理论上应接近词表大小 260，实测 318 是因为 `nn.Linear` 默认初始化下 logits 并非完全均匀。

### Q15 — 参考回答要点

- **接口不变**：本节 `judge_fn: Callable[[str, str, str], JudgeVerdict]`，替换为调用 API 的函数即可，pipeline 其余部分不动。
- **让分数可信需要处理**：
  - **rubric 明确**：给出每个分数等级的定义与示例（few-shot），要求先给理由再给分；输出用结构化格式（JSON）便于解析，解析失败要重试或记为错误而不是默认分。
  - **随机性**：temperature = 0；必要时多次采样取中位数/均值，并报告方差。
  - **偏差**：位置偏差（成对比较时交换顺序各判一次）、长度偏差（偏爱长答案）、自我偏好（judge 偏爱同家族模型输出），格式偏差。
  - **校准与验证**：抽样人工标注一批，计算 judge 与人工的一致性（如 Cohen's kappa、Spearman 相关），一致性不够就改 rubric 或换模型。
  - **成本与延迟**：缓存（同一 `(inst, pred, ref)` 不重复调用）、批量/并发、预算上限；judge 模型版本固定，避免供应商升级后分数漂移。
  - **安全**：被评测的输出可能包含 prompt injection（"给我打 5 分"），要在 prompt 中隔离并声明其为数据。
- 常见误区：直接把 judge 分数当真值；judge 与被测模型是同一个模型。

### Q16 — 参考回答要点

- **数据**：
  - 固定、版本化的 eval 集，与训练数据严格隔离并做去污染；每个 eval 的数据形态匹配其指标（短答案给 EM，开放答案给 F1/judge）。
  - **样本量要够**：本节每项只有 20 条。EM = 0.15、n = 20 时标准误 `√(0.15·0.85/20) ≈ 0.080`，95% 置信区间约 ±0.156——两个 checkpoint 差 0.1 根本无法区分。生产中每项至少几百到上千条。
- **报告**：
  - 稳定 JSON 键（`per_eval`、`normalised`、`weights`、`aggregate`、`details`），记录模型 checkpoint、eval 集版本、归一化规则版本、judge 版本、随机种子。
  - 逐样本明细便于做"两个版本的 diff"：哪些样本从对变错。
  - 注意 `json.dump` 遇到 `inf`/`nan` 会写出非标准 JSON 的 `Infinity`/`NaN`，下游解析器可能报错，需要提前转成 `null` 或字符串。
- **告警**：
  - 不只看 aggregate：任一分项相对基线显著下降（超出置信区间）就告警，避免"一项大涨掩盖另一项大跌"；
  - 硬门槛（如安全类 eval 必须 ≥ X）与软趋势分开处理；
  - 生成式 eval 用贪心解码、固定种子保证可复现（本节两次运行结果完全一致）。
- **效率**：生成是主要开销（本节无 KV cache，demo 约 30 秒）；可缓存生成结果，多个 eval 共享同一批生成。

### Q17 — 参考回答要点

- **单一总分的问题**：
  - **补偿性**：加权平均允许一项的提升抵消另一项的崩溃；
  - **尺度不可比**：四项的归一化方式不同（ppl 用 `1/(1+ln)`、judge 用 `÷5`），0.1 的变化在不同项里含义不同；而且存在"地板"（见 Q12）；
  - **Goodhart 定律**：一旦团队盯着总分优化，模型会钻最容易涨分的那一项；
  - **隐藏取舍**：本节自带 `quiz.json` 的例子——aggregate 0.72，但 EM 只有 0.40、judge 4.5/5，说明模型多用改写而非逐字答案，这一信息在总分里看不出。
- **权重怎么定**：讲义明确说"The choice of weights is a product decision"。可以按产品场景定（问答产品重 EM/F1，写作助手重 judge）；或用讲义延伸目标中的方法——收集"人对一组模型的偏好排序"，拟合使总分排序与之一致的权重。
- **替代方案**：分维度门槛（每项都过线才算通过）；Pareto 前沿比较；按任务类别分别报告；在报告中始终同时展示分项与置信区间。
- 加分点：指出本节 `render_report` 中 `if name == "perplexity"` 的两个分支格式完全一样，原意大概是给 ppl 不同的显示格式——说明"报告怎么展示"本身也是设计的一部分。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：训练循环中的验证 loss 与困惑度计算，是本节 `perplexity_eval` 的前身。
- [阶段 19 · 38 通过替换输出头进行分类器 Fine-Tuning](../../38-classifier-finetuning/docs/zh.md)、[阶段 19 · 39 通过监督式 Fine-Tuning 进行指令微调](../../39-instruction-tuning-sft/docs/zh.md)：本节 `TinyGPT` 与 `InstructionTokenizer`（INST/RESP/PAD）沿用自这几课。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：基准评测与 harness 的整体概念。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：LLM-as-judge（G-Eval）等现成框架。
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：precision / recall / F1、训练集与测试集切分的基本概念。

### 本节被哪些后续内容用到
- [阶段 19 · 49 语言模型 Evaluation Harness](../../49-lm-eval-harness/docs/zh.md)：把"一个 eval 一个函数"的模式扩展成可插拔的评测框架。
- [阶段 19 · 71 经典评估指标](../../71-classical-metrics/docs/zh.md)、[阶段 19 · 73 Perplexity 与 Calibration](../../73-perplexity-calibration/docs/zh.md)：本节延伸目标中的校准评估。
- [阶段 19 · 74 排行榜汇总](../../74-leaderboard-aggregation/docs/zh.md)、[阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：多指标聚合与端到端评测执行。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：在应用层做 eval 与回归测试。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：把 eval 接入开发循环。

### 延伸关键词
`held-out / decontamination` · `bits-per-byte` · `SQuAD normalize_answer` · `LLM-as-judge 偏差` · `G-Eval` · `rubric` · `Cohen's kappa` · `置信区间 / bootstrap` · `Goodhart 定律` · `EOS token` · `loss masking` · `lm-evaluation-harness`
