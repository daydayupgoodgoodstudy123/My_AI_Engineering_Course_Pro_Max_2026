# 测验 · Perplexity 与 Calibration（困惑度与校准）（Perplexity and Calibration）

> **阶段 19 · 综合项目 · 第 73 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 困惑度（perplexity） | 每 token 平均负对数似然的指数：`exp(Σ NLL / Σ tokens)`；1 表示每个 token 都以概率 1 预测对，等于词表大小表示均匀分布、什么都没学到 |
| 2 | token 加权聚合 | 先把所有序列的 NLL 总和除以总 token 数，再取指数（micro）；**不是**各序列困惑度的平均 |
| 3 | 符号契约 | 适配器必须给 `−log p`（非负）；给成 `log p` 会得到小于 1 的"不可能"困惑度，代码直接抛 `ValueError` |
| 4 | ECE | 按置信度分到 M 个等宽 bin，`Σ (n_b/N)·|avg_conf_b − acc_b|`；默认 10 个 bin，讲义提到对比时也用 15 |
| 5 | ECE 的偏差 | 受 bin 数和样本量影响；同一 bin 内过度自信与欠自信可以**相互抵消**；所以同时返回 `populated_bins` |
| 6 | Brier 分数 | `mean((p − y)²)`；逐样本平方误差，直接惩罚每个预测的偏差；p 恒为 0.5 时恰好 0.25 |
| 7 | Murphy 分解 | `Brier ≈ reliability − resolution + uncertainty`；分 bin 计算时只是近似，差一个 bin 内方差/协方差项 |
| 8 | 可靠性图（reliability diagram） | 每个 bin 的 (平均置信度, 准确率, 计数) 三元组；对角线即完美校准 |
| 9 | 置信度来源 | 选择题用选项对数似然的 softmax；自由文本用自报概率或平均对数似然的指数；"从哪来是适配器的事" |
| 10 | 校准是模型级报告 | 不是逐任务指标；runner 汇总整个评估的 `(confidence, correct)` 对后一次性算 ECE / Brier |

### 核心技能（能动手做到）

- [ ] 给定若干序列的 NLL 总和与 token 数，手算语料困惑度，并说出它与"序列困惑度平均"的区别
- [ ] 给定 10 个左右的 `(置信度, 是否正确)`，手算 ECE、Brier、可靠性图三元组和 Murphy 分解
- [ ] 构造一个"ECE = 0 但 Brier 不低"的例子，并解释 bin 内抵消
- [ ] 指出 `_bin_indices` 在 0.3、0.6、0.7 等边界值上的浮点误差，并写出修正版本
- [ ] 解释为什么"永远预测基准率"的模型 ECE = 0 却毫无用处（resolution = 0）
- [ ] 用 `python3 -m pytest -q` 运行 23 个测试，并找出测试名与断言不一致的地方

---

## 二、基础自测（选择题）

**Q1.** 两个序列：第一个 10 个 token、每 token NLL = ln 2；第二个 90 个 token、每 token NLL = ln 8。调用 `perplexity([10·ln2, 90·ln8], [10, 90])` 的结果约为：

- A. 5.0
- B. 2.0
- C. 6.96
- D. 8.0

**Q2.** 适配器把 `log p`（负数）而不是 `−log p` 传给 `PerplexityResult.from_token_nll`，会发生什么？

- A. 抛出 `ValueError`，提示可能忘了取负号
- B. 返回一个小于 1 的困惑度
- C. 返回 `NaN`
- D. 自动取绝对值后正常计算

**Q3.** 10 个预测：置信度 0.9 的 4 个（对 3 个）、0.6 的 5 个（对 2 个）、0.2 的 1 个（错）。`expected_calibration_error(..., bins=10)` 返回的 ECE 是：

- A. 0.0
- B. 0.12
- C. 0.228
- D. 0.18

**Q4.** 一个"永远输出 0.5"的预测器，Brier 分数是多少？

- A. `0.5 − 准确率`
- B. 恰好 0.25，与准确率无关
- C. 0
- D. `0.25` 减去一个与准确率有关的修正项

**Q5.** 如果所有预测都是错的（`correct` 全为 0），ECE 等于：

- A. 所有置信度的平均值
- B. 0
- C. 1 减去平均置信度
- D. 0.5

**Q6.** 20 个样本全部落在 `[0.8, 0.9)` 这个 bin：10 个置信度 0.82、实际对 7 个；10 个置信度 0.88、实际全对。关于这组数据，正确的是：

- A. ECE = 0，说明模型在这个区间内完美校准
- B. 不同 bin 之间的过度自信与欠自信会相互抵消，这就是 ECE 为 0 的原因
- C. Brier 分数一定不大于 ECE
- D. ECE = 0，但 0.82 一组过度自信、0.88 一组欠自信，二者在同一 bin 内被平均抵消；Brier（0.119）仍能反映逐样本误差

**Q7.** demo 中的 `synthetic_overconfident(800)`：置信度均匀分布在 [0.7, 1.0)，答对概率为 `0.5 × 置信度`。用 10 个 bin 时 `populated_bins` 是：

- A. 10
- B. 7
- C. 3
- D. 1

**Q8.** 在词表大小为 V 的语言模型上，若模型对每个位置都输出均匀分布，困惑度为：

- A. `ln V`
- B. `V`
- C. 1
- D. `1/V`

---

## 三、动手 / 代码题

**Q9.** 用 Q3 的 10 个样本：

1. 写出 `reliability_diagram(..., bins=10)` 返回的三个数组中**非零**的条目（包括 bin 下标）。注意置信度 0.6 落在哪个 bin。
2. 手算 Brier 分数。
3. 手算 `brier_decomposition` 的 reliability、resolution、uncertainty，验证 `rel − res + unc` 是否等于第 2 问的 Brier，并解释为什么这里恰好相等。

**Q10.** `brier_decomposition` 返回 `brier = reliability − resolution + uncertainty`，测试 `test_decomposition_sums_to_brier` 只要求与 `brier_score` 在小数点后 2 位一致（`places=2`）。

1. 对 Q6 的数据，分解给出的 `brier` 是多少？真实 Brier 是多少？
2. 推导分 bin 时的精确恒等式，说明缺了哪一项，并用 Q6 的数据验证。
3. 讲义说"We compute the score and the decomposition. The runner reports the scalar but logs the decomposition for the dashboard"。`CalibrationReport` 有没有包含分解？

**Q11.** 讲义描述 perplexity 的输入为 "a list of per-token log-probabilities, a list of token counts per sequence"，代码签名是：

```python
def from_token_nll(cls, neg_log_probs: Sequence[float], token_counts: Sequence[int]):
    if len(neg_log_probs) != len(token_counts):
        raise ValueError("neg_log_probs and token_counts must align")
    for nll, n in zip(neg_log_probs, token_counts):
        ...
        total_nll += float(nll)
        total_tokens += int(n)
```

两个序列：序列 A 10 个 token、平均 NLL 1.0；序列 B 30 个 token、平均 NLL 2.0。

1. 正确的调用方式与结果是什么？
2. 如果适配器按讲义字面传入 40 个"逐 token NLL"和 `[10, 30]`，会怎样？
3. 如果适配器传入的是每个序列的**平均** NLL `[1.0, 2.0]`，会得到什么？为什么代码发现不了？
4. "两个序列困惑度的平均值"是多少？为什么不应该这样报告？

**Q12.** 阅读分 bin 函数与输入校验：

```python
def _bin_indices(confidences, n_bins):
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.searchsorted(edges, confidences, side="right") - 1
    idx = np.clip(idx, 0, n_bins - 1)
    return idx

def _validate_probs(confidences, correct):
    ...
    if float(confidences.min()) < 0.0 or float(confidences.max()) > 1.0:
        raise ValueError("confidences must lie in [0, 1]")
```

1. 对 `[0.0, 0.1, 0.2, 0.3, 0.5, 0.6, 0.7, 0.9, 0.95, 1.0]` 预测 `_bin_indices(..., 10)` 的输出。哪些值"放错了 bin"？为什么？
2. 置信度 1.0 为什么没有越界？
3. 输入里有一个 `NaN` 置信度会怎样？
4. 写出修正版本。

---

## 四、面试高频题

**Q13.**（基础必考）什么是困惑度？它和交叉熵是什么关系？为什么两个使用不同 tokenizer 的模型不能直接比较困惑度？

**Q14.**（原理深挖）ECE 怎么计算？它有哪些已知缺陷？Brier 分数、NLL 和 ECE 各自衡量什么，什么时候该看哪个？

**Q15.**（工程实践）对一个 LLM 做选择题评估时，如何得到每道题的"置信度"？自由文本生成任务呢？各有什么坑？

**Q16.**（场景设计）上线后发现模型在置信度 0.9 以上的回答中只有 70% 正确。你会如何诊断和修复？修复后如何确认有效？

**Q17.**（追问型）一个模型的 ECE 为 0，是不是就是好模型？请用 Brier 分解解释"校准"和"有用"的区别。

---

## 五、参考答案与解析

### Q1 — 答案：C

token 加权：`exp((10·ln2 + 90·ln8) / 100) = exp(0.1·0.693 + 0.9·2.079) = exp(1.941) ≈ 6.96`（代码实测 6.964）。A 是两个序列困惑度（2 和 8）的简单平均——这是常见错误，忽略了第二个序列有 9 倍的 token。B、D 分别只看了一个序列。测试 `test_multi_sequence_weighted_correctly` 锁定的就是这种加权方式。

### Q2 — 答案：A

代码逐个检查 `if nll < 0: raise ValueError("neg_log_probs must be non-negative (did you forget the negation?)")`。讲义："an adapter that returns `log p` instead of `-log p` produces a perplexity below one, which is impossible. The function catches that as a contract violation." B 是如果不检查会发生的事；D 是一种危险的"静默修复"，会掩盖适配器 bug。

### Q3 — 答案：D

实测 `(0.18, 3)`。三个 bin：

| bin | 样本数 | 平均置信度 | 准确率 | 加权 gap |
|-----|-------|----------|-------|---------|
| 0.9 那组 | 4 | 0.9 | 0.75 | 0.4 × 0.15 = 0.06 |
| 0.6 那组 | 5 | 0.6 | 0.4 | 0.5 × 0.2 = 0.10 |
| 0.2 那组 | 1 | 0.2 | 0.0 | 0.1 × 0.2 = 0.02 |

合计 0.18。C（0.228）是同一组数据的 Brier 分数，见 Q9。

### Q4 — 答案：B

y 只能是 0 或 1，`(0.5 − 0)² = (0.5 − 1)² = 0.25`，平均值恒为 0.25。测试 `test_uniform_predictor` 验证了这一点。讲义写 "Brier is 0.25 minus a correction term"，这是不准确的——没有任何修正项（D 错）。讲义同一句里 "ECE is 0.5 minus accuracy" 也应写成**绝对值** `|0.5 − 准确率|`（A 只对准确率 ≤ 0.5 成立，而且那是 ECE 不是 Brier）。

### Q5 — 答案：A

每个 bin 的准确率都是 0，gap 就是该 bin 的平均置信度；按 bin 大小加权求和，正好等于全部样本的平均置信度。实测置信度 `[0.9, 0.7, 0.6, 0.95]` 全错时 ECE = 0.7875 = 平均值。讲义 Edge cases："All predictions wrong: ECE is the average confidence."

### Q6 — 答案：D

实测 ECE = 0.0（`populated = 1`），Brier = 0.1194。bin 的平均置信度 = 0.85，准确率 = 17/20 = 0.85，gap 为 0。但局部看：0.82 那组实际准确率 0.7（过度自信），0.88 那组实际 1.0（欠自信）。A 错，ECE = 0 不代表完美校准；B 错在"不同 bin 之间"——ECE 对每个 bin 取**绝对值**后再加，跨 bin 不会抵消（实测一个 bin 过度自信 0.15、另一个欠自信 0.25 时 ECE = 0.20），只有**同一 bin 内**会抵消。讲义说"A model that is overconfident on half the bins and underconfident on the other half can have low ECE"，这个说法不准确，真正的机制是 bin 内平均。C 无此关系。

### Q7 — 答案：C

置信度只落在 [0.7, 1.0)，即 bin 7、8、9 三个。demo 实际输出 `overconfident ece=0.4283 brier=0.4271 populated=3`。平均置信度约 0.85、准确率约 0.42，gap 约 0.43。`populated_bins` 很小提醒我们：ECE 的估计只依赖 3 个 bin，可靠性图上大部分区域是空的。

### Q8 — 答案：B

均匀分布下每个 token 的 NLL = `ln V`，困惑度 = `exp(ln V) = V`。例如 V = 50257 时，平均 NLL = 10.82、困惑度 = 50257。A 是平均 NLL（交叉熵，单位 nats）；C 是完美模型；D 是单个 token 的概率。困惑度可以理解为"模型平均在多少个等可能选项中犹豫"。

### Q9 — 参考答案

1. 实测：

```text
bin_conf  : bin2=0.2, bin5=0.6, bin9=0.9（其余为 0）
bin_acc   : bin2=0.0, bin5=0.4, bin9=0.75
bin_count : bin2=1,   bin5=5,   bin9=4
```

置信度 0.6 本应落在 `[0.6, 0.7)` 即 bin 6，却落在 **bin 5**：`np.linspace(0, 1, 11)[6]` 实际是 `0.6000000000000001`，比 0.6 略大，`searchsorted(side="right")` 于是把 0.6 放到前一个 bin（见 Q12）。在这个例子里该 bin 只有这一组样本，所以不影响 ECE 数值，但会影响可靠性图的横坐标位置。

2. Brier：0.9 组：3 个对 `(0.1)² × 3 = 0.03`，1 个错 `0.81`；0.6 组：2 个对 `(0.4)² × 2 = 0.32`，3 个错 `(0.6)² × 3 = 1.08`；0.2 组：错 `0.04`。合计 `0.03 + 0.81 + 0.32 + 1.08 + 0.04 = 2.28`，除以 10 得 **0.228**（实测 0.228）。

3. 整体准确率 ō = 5/10 = 0.5。
   - reliability = `0.4 × 0.15² + 0.5 × 0.2² + 0.1 × 0.2² = 0.009 + 0.02 + 0.004 = 0.033`
   - resolution = `0.4 × (0.75 − 0.5)² + 0.5 × (0.4 − 0.5)² + 0.1 × (0 − 0.5)² = 0.025 + 0.005 + 0.025 = 0.055`
   - uncertainty = `0.5 × 0.5 = 0.25`
   - `0.033 − 0.055 + 0.25 = 0.228`，与 Brier 完全相等（实测 0.22799999999999998）。

   恰好相等是因为**每个 bin 内所有样本的置信度都相同**，bin 内方差为 0、协方差为 0（见 Q10 的恒等式）。

### Q10 — 参考答案

1. 实测：分解给出 `reliability = 0, resolution = 0, uncertainty = 0.1275, brier = 0.1275`；真实 Brier = **0.1194**，差 0.0081。（对 `synthetic_calibrated(500, seed=21)`，二者分别是 0.15208 和 0.15118，差约 0.0009，所以 `places=2` 的测试能通过。）
2. 对 bin b 中的样本，令 p̄_b、ȳ_b 为 bin 内平均：

```text
Σ_i (p_i − y_i)² = Σ_i (p_i − p̄_b)² + n_b (p̄_b − ȳ_b)² + Σ_i (y_i − ȳ_b)² − 2 Σ_i (p_i − p̄_b)(y_i − ȳ_b)
```

   其中 `Σ_i (y_i − ȳ_b)² = n_b ȳ_b (1 − ȳ_b)`，按 bin 加权求和后等于 `uncertainty − resolution`。于是

```text
Brier = REL − RES + UNC + (1/N) Σ_b [ Σ_i (p_i − p̄_b)² − 2 Σ_i (p_i − p̄_b)(y_i − ȳ_b) ]
```

   代码漏掉了最后一项（bin 内置信度方差 − 2 × bin 内协方差）。Q6 数据：方差项 = 0.03² = 0.0009，协方差项 = 0.0045，修正 = `0.0009 − 2 × 0.0045 = −0.0081`，`0.1275 − 0.0081 = 0.1194`，与真实 Brier 一致（已运行验证）。
3. 没有。`CalibrationReport.from_predictions` 只计算 `ece`、`brier`、`reliability`、`populated_bins`，`brier_decomposition` 只被测试调用，没有接入报告。

### Q11 — 参考答案

1. 代码期望的是**每个序列的 NLL 总和**，与 `token_counts` 一一对应：`perplexity([10 × 1.0, 30 × 2.0], [10, 30])` = `exp(70 / 40) = exp(1.75) ≈ 5.755`（实测 5.7546）。
2. 40 个元素对 2 个计数，长度不一致，抛 `ValueError: neg_log_probs and token_counts must align`（实测）。要按讲义的"逐 token"语义调用，`token_counts` 必须是 40 个 1。讲义的描述与代码契约不一致。
3. `exp((1.0 + 2.0) / 40) = exp(0.075) ≈ 1.078`（实测 1.0779）。这个数字看起来"很好"，但完全错误：分子是 2 个平均值之和，分母却是 40 个 token。代码只检查非负和长度对齐，无法分辨"总和"和"平均"——它们都是非负浮点数。防御办法：在适配器契约里写清楚单位，并做合理性检查（例如困惑度低到不可信时报警，或要求适配器同时返回逐 token 数组）。
4. `(e^1.0 + e^2.0) / 2 = (2.718 + 7.389) / 2 ≈ 5.054`，低于正确的 5.755。简单平均让 10 个 token 的短序列与 30 个 token 的长序列权重相同；而且困惑度是 NLL 的**指数**，对指数取平均再比较没有明确含义。语料困惑度应当是 token 加权的 `exp(总 NLL / 总 token)`。

### Q12 — 参考答案

1. 实测原函数输出 `[0 1 2 2 5 5 6 9 9 9]`。0.3、0.6、0.7 分别被放进 bin 2、5、6，而按 `[0.3, 0.4)` 这类左闭右开区间应是 bin 3、6、7。原因：`np.linspace(0, 1, 11)` 的第 3、6、7 个边界分别是 `0.30000000000000004`、`0.6000000000000001`、`0.7000000000000001`，比十进制的 0.3、0.6、0.7 略大；`searchsorted(side="right")` 返回"第一个大于该值的边界"的位置，减 1 后就落到了前一个 bin。0.1、0.2、0.5、0.9 的边界恰好精确，所以没问题。选择题中常见的整数百分比置信度（0.3、0.6、0.7）恰好受影响。
2. 1.0 等于最后一个边界，`searchsorted(side="right")` 返回 11，减 1 得 10，被 `np.clip(idx, 0, n_bins − 1)` 夹回 9，于是 1.0 落入最后一个 bin `[0.9, 1.0]`。
3. `NaN` 与任何数比较都是 `False`，`min() < 0` 与 `max() > 1` 都不成立（`NaN` 会传播成 `min()` 的结果），**通过了校验**；`searchsorted` 把 `NaN` 排在最后，进入 bin 9；该 bin 的均值变成 `NaN`，最终 ECE = `NaN`（实测 `(nan, 2)`）。
4. 修正版本（已运行验证，输出 `[0 1 2 3 5 6 7 9 9 9]`）：

```python
def _bin_indices(confidences, n_bins):
    idx = np.floor(np.asarray(confidences) * n_bins + 1e-9).astype(int)
    return np.clip(idx, 0, n_bins - 1)

def _validate_probs(confidences, correct):
    ...
    if not np.all(np.isfinite(confidences)):
        raise ValueError("confidences must be finite")
    ...
```

`1e-9` 的小量用于吸收 `0.3 * 10 = 3.0000000000000004` 这类方向不确定的乘法误差（例如某些值乘 10 后可能得到 2.9999999999999996）。注意：修改分 bin 规则会改变 ECE 数值，等于改变了指标定义，新旧结果不可混比。

### Q13 — 参考回答要点

- **定义**：`PPL = exp( −(1/T) Σ_t log p(x_t | x_<t) )`，即每 token 平均负对数似然（交叉熵，nats）的指数。
- **与交叉熵**：交叉熵 H 是"平均每 token 需要多少 nats 的信息"，PPL = e^H；以 2 为底时 PPL = 2^(bits per token)。直观上 PPL 是"模型平均在多少个等可能选项间犹豫"。
- **边界**：完美模型 PPL = 1；均匀分布 PPL = V（Q8）。讲义："a strong 2026 base model on WikiText-103 sits around eight to twelve. A bad one on the same text sits at fifty plus."
- **不能跨 tokenizer 比较**：PPL 是"每 token"的量。同一段文本，词表大的 tokenizer 切出的 token 少、每个 token 信息量大，PPL 天然更高；字节级模型 token 多、PPL 更低。跨 tokenizer 应换成与切分无关的单位，如 bits per byte / bits per character（总 NLL 除以字节数）。
- 加分点：PPL 只衡量"对文本是否觉得合理"，不衡量能否完成任务；另外上下文长度、是否使用滑动窗口都会影响数值，报告时应写清楚。

### Q14 — 参考回答要点

- **计算**：按置信度分 M 个等宽 bin，`ECE = Σ_b (n_b/N)·|conf_b − acc_b|`。
- **缺陷**：
  - 依赖 bin 数：本节 `synthetic_calibrated(800)` 用 10 个 bin 时 ECE ≈ 0.035，15 个 bin 时 ≈ 0.042；
  - 依赖样本量：同一个"真实完美校准"的生成器，100 个样本 ECE ≈ 0.086，10 万个样本 ≈ 0.003——小样本 ECE 主要是噪声；讲义："With ten bins and a hundred predictions, you cannot distinguish 0.02 ECE from random noise."
  - bin 内抵消（Q6）；
  - 等宽 bin 在置信度集中时大部分 bin 为空（Q7 中 3/10）；
  - 只看 top-1 置信度，不看完整分布。
- **改进**：等样本数 bin（adaptive ECE）、多种 bin 数下报告、bootstrap 置信区间、classwise ECE。
- **三者分工**：ECE 只衡量校准；Brier 是**严格适当评分规则**（proper scoring rule），同时奖励校准和区分能力（resolution）；NLL 也是适当评分规则，但对"自信地答错"惩罚极重（置信度 0.99 答错时 −log 0.01 ≈ 4.6）。需要单一可比较的数字时看 Brier/NLL，诊断"自信程度是否可信"时看 ECE + 可靠性图。

### Q15 — 参考回答要点

- **选择题**：把每个选项（或选项字母）作为续写，计算条件对数似然，对选项做 softmax，取被选选项的概率作为置信度。讲义："For multiple-choice tasks the natural confidence is softmax over option log-likelihoods."
  - 坑：长选项的总对数似然天然更低，需要按长度归一化或只对选项字母打分；字母本身有先验偏好（如偏爱 "A"）；chat 模型经过 RLHF 后 token 概率往往校准变差。
- **自由文本**：
  - 序列平均对数似然的指数（`exp(mean log p)`）——讲义提到的方法之一；坑是"流畅但错误"的回答也可能概率很高；
  - 让模型口头报告置信度（verbalized confidence）——坑是数字往往集中在 0.8–0.95；
  - 采样多次看一致性（self-consistency）作为置信度——成本高但通常更可靠。
- **工程**：置信度来源属于适配器契约（讲义："Where it comes from is the adapter's job"），报告中要注明来源；API 模型可能拿不到 logprobs，只能用口头或采样方法。

### Q16 — 参考回答要点

- **诊断**：先收集足够的 `(置信度, 是否正确)` 样本（线上抽样 + 人工标注），画可靠性图、算 ECE/Brier，按任务类型、语言、长度等切片，看过度自信集中在哪里；检查置信度来源是否变了（例如提示词改动、模型升级）。
- **修复**：
  - 后处理校准：temperature scaling（在留出的验证集上拟合一个温度 T，`softmax(logits / T)`，只改置信度不改预测）、Platt scaling、isotonic regression；
  - 若置信度来自口头报告，可以学一个映射表；
  - 对高风险场景设阈值：置信度低于阈值时转人工或拒答。
- **确认**：在**独立的**测试切片上重新计算 ECE、Brier、可靠性图（不能用拟合温度的同一批数据），并用 bootstrap 给出置信区间；上线后持续监控（数据漂移会让校准失效）。讲义 Going further 正是建议"add temperature scaling on a held-out validation slice, recompute ECE, and watch the gap shrink"。
- 常见误区：只看总体 ECE 降低就宣布修复；在测试集上调温度。

### Q17 — 参考回答要点

- 不是。反例：总是输出基准率的模型。实测 10 个样本中 7 个正确，模型对每个样本都输出 0.7：ECE = 0，Brier = 0.21，分解为 `reliability = 0, resolution = 0, uncertainty = 0.21`。它完美校准，但对"哪道题更可能对"毫无区分能力。
- **分解含义**：
  - reliability（越小越好）：每个 bin 的置信度与实际准确率差多少——就是校准；
  - resolution（越大越好）：各 bin 的准确率偏离总体准确率多少——就是区分能力；
  - uncertainty：数据本身的难度 `ō(1 − ō)`，与模型无关。
- **"有用"的模型**：既要 reliability 小，也要 resolution 大。Brier 同时包含二者，所以讲义说"A model that wins on accuracy and loses on Brier is a worse production deployment than ..."。
- 加分点：ECE 只能衡量 reliability；排行榜只报准确率会忽略校准，只报 ECE 会忽略区分能力，最好同时报告准确率、ECE、Brier。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：熵、交叉熵与困惑度的关系。
- [阶段 01 · 06 概率和分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：概率预测与期望。
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：分类评估指标与概率预测的评估。
- [阶段 05 · 16 Transformers 之前的文本生成 — N-gram 语言模型](../../../05-nlp-foundations-to-advanced/16-text-generation-pre-transformer/docs/zh.md)：困惑度在语言模型评估中的经典用法。
- [阶段 19 · 70 任务规范格式](../../70-task-spec-format/docs/zh.md)、[阶段 19 · 71 经典评估指标](../../71-classical-metrics/docs/zh.md)：本节汇总的 `correct` 来自这些任务和指标。

### 本节被哪些后续内容用到
- [阶段 19 · 74 排行榜汇总](../../74-leaderboard-aggregation/docs/zh.md)：多模型报告的组织方式。
- [阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：直接调用 `CalibrationReport` 与 `PerplexityResult`，把 ECE、Brier、困惑度写进模型报告。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：困惑度与 benchmark 在 LLM 评估体系中的位置。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：应用层评估中的置信度与阈值策略。

### 延伸关键词
`cross-entropy` · `bits per byte` · `ECE / MCE` · `adaptive ECE` · `reliability diagram` · `Brier score` · `Murphy decomposition` · `proper scoring rule` · `temperature scaling` · `Platt scaling` · `isotonic regression` · `verbalized confidence`
