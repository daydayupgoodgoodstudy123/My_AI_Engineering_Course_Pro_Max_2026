# 测验 · 排行榜汇总（Leaderboard Aggregation）

> **阶段 19 · 综合项目 · 第 74 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 输入形状 | 每个 `(model, task)` 一条 `EvalRun`，`score` 必须已在 `[0, 1]`；同一对出现两次直接报错 |
| 2 | 拒绝而非修补 | 分数超出 `[0, 1]`（例如 BLEU 28.3）或为 NaN 时拒绝整次聚合；讲义："The fix lives upstream" |
| 3 | 平均分 | 每个模型对自己跑过的任务取算术平均；是排行榜的标题数字，但对离群值和任务构成敏感 |
| 4 | win-rate | 每个任务上得分最高者获胜，胜场 / 有分数的任务数；对量纲和离群值不敏感，但丢掉了差距大小 |
| 5 | 平局 | 代码中所有并列第一的模型**都**记 1 胜（不是讲义所说的"平分"） |
| 6 | bootstrap 均值 CI | 对任务有放回重采样 B 次，取 `α/2` 与 `1 − α/2` 分位数（percentile 法）；纯 NumPy |
| 7 | 配对 bootstrap | 对**共同任务**上的逐任务差 `score_A − score_B` 重采样；CI 不含 0 即"显著" |
| 8 | 分类别均值 | `categories` 字段给出每个类别的均值，暴露"总体强、某类弱"的情况 |
| 9 | 输出 | `LeaderboardRow` 列表 → JSON（`render_json`）与 Markdown 表（`render_markdown`，模型名截断到 20 字符） |
| 10 | 没做的事 | 不做任务加权（`weight` 字段被忽略）、不做多重比较校正、不做分层 bootstrap |

### 核心技能（能动手做到）

- [ ] 给定一张"模型 × 任务"分数表，手算每个模型的均值、win-rate 和类别均值
- [ ] 解释 percentile bootstrap 的每一步，并估计"10 个任务、准确率 50%"时 CI 有多宽
- [ ] 说清"两个均值 CI 重叠"与"配对差 CI 不含 0"为什么可以同时成立
- [ ] 改写 `_win_rate` 实现平局平分，改写聚合让不同任务覆盖的模型可以公平比较
- [ ] 在 `pairwise_diffs` 中加入 Bonferroni 校正，并说明为什么还需要增大 B
- [ ] 用 `python3 -m pytest -q` 运行 18 个测试，并指出测试名与讲义不一致的地方

---

## 二、基础自测（选择题）

**Q1.** 两个模型 `a`、`b` 在唯一的任务 `t1` 上都得 0.5。`aggregate` 给出的 win-rate 是：

- A. 都是 0.5
- B. 都是 1.0
- C. 先出现的模型 1.0，另一个 0.0
- D. 都是 0.0

**Q2.** 某个 summary 任务的 BLEU 以 0–100 计，传入 `EvalRun("m", "t", "bleu_4", 28.3)`。`aggregate` 会：

- A. 自动除以 100
- B. 截断到 1.0
- C. 正常计入，使该模型均值被这一项主导
- D. 抛出 `ValueError`

**Q3.** 模型 `big` 跑了 `easy1`（0.9）和 `hard1`（0.3）；模型 `small` 只跑了 `easy1`（0.95）。`aggregate` 的排序与 win-rate 是：

- A. `small` 第一（均值 0.95，win-rate 1.0），`big` 第二（均值 0.6，win-rate 0.5）
- B. `big` 第一，因为它完成了更多任务
- C. 抛错，因为两个模型的任务集合不同
- D. 两者并列

**Q4.** 10 个任务，5 个得 1、5 个得 0。`bootstrap_mean_ci(scores, b=1000)` 返回的 95% 区间约为：

- A. `(0.5, 0.5)`
- B. `(0.4, 0.6)`
- C. `(0.2, 0.8)`
- D. `(0.0, 1.0)`

**Q5.** `pairwise_diffs` 判定 `significant=True` 的条件是：

- A. 配对差的 bootstrap 区间不包含 0（`lo > 0` 或 `hi < 0`）
- B. 平均差 `diff_mean > 0`
- C. 配对 t 检验 p < 0.05
- D. 区间宽度小于 0.1

**Q6.** 为什么比较两个模型时用**配对** bootstrap（对逐任务差重采样），而不是分别重采样再比较？

- A. 配对 bootstrap 运行得更快
- B. 配对 bootstrap 不需要随机数种子
- C. 两个模型跑的是同一批任务，任务难度对两者的影响在差值中相互抵消，方差更小、检验更敏感
- D. 分别重采样会让分数超出 `[0, 1]`

**Q7.** 10 个任务：`steady` 每题 0.7；`spiky` 前 6 题 0.72、后 4 题 0.3。均值排名与 win-rate 排名分别是：

- A. 两种都是 `steady` 第一
- B. 两种都是 `spiky` 第一
- C. 均值 `spiky` 第一，win-rate `steady` 第一
- D. 均值 `steady` 第一（0.70 vs 0.552），win-rate `spiky` 第一（0.6 vs 0.4）

**Q8.** `EvalRun(..., weight=2.0)` 中的 `weight` 字段对聚合结果的影响是：

- A. 该任务在均值中计两次
- B. 没有任何影响
- C. 只影响 win-rate
- D. 抛出异常，因为权重必须为 1

---

## 三、动手 / 代码题

**Q9.**（平局平分）讲义说 "For each task, the model with the highest score wins (ties split)"，代码却是：

```python
        best = max(scores.values())
        if math.isclose(scores[model_id], best, abs_tol=1e-12):
            wins += 1
```

1. 当前实现下，k 个模型在某任务上并列第一时，所有模型的 win-rate 之和会怎样？
2. 改写 `_win_rate` 实现平局平分，并计算：`a`、`b` 在 `t1` 上都是 0.5，在 `t2` 上分别是 0.9、0.1 时两者的 win-rate。
3. 测试 `test_ties_split_to_winner` 断言两个模型都是 1.0。你的修改会让它失败吗？应当怎么处理？

**Q10.**（任务覆盖不一致）沿用 Q3 的 `big`/`small` 例子。

1. 解释为什么当前排名不公平。
2. 给出两种修正：(a) 只在所有模型都有分数的"共同任务"上计算均值；(b) 缺失任务计 0 分。分别计算两个模型的均值。
3. 你会在排行榜上加哪一列让读者看到这个问题？

**Q11.**（多重比较与种子）

1. 6 个**完全相同**的模型（每个任务的分数 = 同一个基础分 + 独立噪声）两两比较，共有多少对？若每对都在 α = 0.05 下检验且相互独立，至少一对被误判为"显著"的概率约为多少？
2. 给 `pairwise_diffs` 加上 Bonferroni 校正（`alpha / 对数`）。为什么同时需要增大 bootstrap 次数 B？
3. 代码用 `seed + i + j` 给每一对设种子。模型数为 4 时，哪些对会拿到相同的种子？这有什么影响？如何修正？

**Q12.**（规范化）学习目标第二条是 "Normalise heterogeneous scores so that pass rates and BLEU values do not over-influence the aggregate"，但代码只做了 `[0, 1]` 校验。

1. 为什么"都在 `[0, 1]`"仍不足以让不同指标"同等重要"？举例说明。
2. 实现"每个任务内按模型做 min-max 规范化，再取均值"，对 Q7 的 `steady`/`spiky` 计算结果。
3. 这种规范化有什么副作用？

---

## 四、面试高频题

**Q13.**（基础必考）要把多个异构 benchmark（准确率、pass@1、ROUGE、BLEU……）汇总成一个排行榜，你会用什么聚合方式？平均分、win-rate、平均排名各有什么优缺点？

**Q14.**（原理深挖）解释 bootstrap 置信区间的原理。percentile 法的步骤是什么？在评估中应该对"什么"重采样？有哪些前提和局限？

**Q15.**（工程实践）demo 中 3 个模型、12 个任务，三对比较全部"显著"。你会如何向团队解释这个结果的可信度？还需要补充什么分析？

**Q16.**（场景设计）为公司设计一个模型发布前的内部排行榜与发布门槛：新模型满足什么条件才能替换线上模型？

**Q17.**（追问型）demo 中 `model_a` 的均值 CI 是 0.73–0.80，`model_b` 是 0.66–0.74，两个区间重叠；但配对差 `a − b` 的 CI 是 [+0.026, +0.102]，判定显著。这矛盾吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

`_win_rate` 对每个任务求最高分，只要自己的分数与最高分"足够接近"（`math.isclose(..., abs_tol=1e-12)`）就记一胜。两个模型都等于最高分，都记 1 胜，win-rate 都是 1/1 = 1.0。测试 `test_ties_split_to_winner` 正是断言两者都为 1.0。讲义说 "ties split"（平分），与代码和测试都不一致；按平分应为 A。

### Q2 — 答案：D

`_validate_runs` 检查 `0.0 <= r.score <= 1.0`，不满足就抛 `ValueError: score for m/t not in [0,1]: 28.3`（实测）。讲义："The aggregator validates that every input score sits in `[0, 1]` and refuses the run otherwise. The fix lives upstream." C 是不校验时会发生的事——这正是校验的动机。NaN 同样会被拒绝（`0 <= nan` 为 False）。

### Q3 — 答案：A

实测：`small` 均值 0.95、win-rate 1.0、Tasks 1；`big` 均值 0.6、win-rate 0.5、Tasks 2。每个模型只对**自己跑过的**任务取平均，`small` 躲过了难题 `hard1`，于是排名第一——即便在两者都做过的 `easy1` 上，`small` 也只是略胜。代码不会因任务集合不同而报错（C 错），也不会因任务多而加分（B 错）。修正方法见 Q10。

### Q4 — 答案：C

实测 `(0.2, 0.8)`。每次重采样 10 个任务，"1 的个数"服从近似 Binomial(10, 0.5)，2.5% 和 97.5% 分位数约为 2 和 8。同样 50% 的准确率在 100 个任务上 CI 为 `(0.4, 0.6)`（B）。这说明**任务数少时，排行榜上 ±0.3 的差距都可能只是噪声**。A 是常数分数时的零宽区间。

### Q5 — 答案：A

`significant = lo > 0.0 or hi < 0.0`。讲义："The user reads off whether the interval excludes zero. If it does, the difference is significant at level alpha." B 忽略了不确定性；C 是另一种检验，代码中没有；D 与显著性无关。

### Q6 — 答案：C

任务难度差异往往远大于模型差异：难题上大家都低、易题上大家都高。逐任务做差后，难度这一共同成分被消掉，差值的方差小得多，同样的数据能检测出更小的差异。讲义 Going further："If model A and B both ran the same hundred tasks, the appropriate test is the paired bootstrap on task-by-task differences, which we implement." A、B、D 都不是原因。

### Q7 — 答案：D

实测：`steady` 均值 0.70、win-rate 0.4；`spiky` 均值 0.552、win-rate 0.6。`spiky` 在 6 个任务上以 0.02 的微弱优势获胜，在另外 4 个任务上大比分落后。win-rate 只数"赢了几场"，不看赢多少；均值看总量。讲义："It is less sensitive to outliers and to scale differences but loses information." 两种排名可以相反，所以讲义要求"The harness reports both"。

### Q8 — 答案：B

`EvalRun` 定义了 `weight: float = 1.0`，但 `aggregate`、`_win_rate`、`_category_means`、`pairwise_diffs` 都没有读取它。讲义："Production leaderboards weight tasks; we leave that hook open through the `weight` field but ignore it in the aggregator."

### Q9 — 参考答案

1. 每个并列第一的模型都加 1 胜，所以该任务对"所有模型 win-rate 之和"的贡献是 k 而不是 1。极端情况下所有模型在所有任务上都并列（例如全部 0 分或全部满分），每个模型 win-rate 都是 1.0，排行榜上看不出任何区别。
2. 参考实现（已运行验证）：

```python
def _win_rate(model_id, runs_by_task):
    wins, total = 0.0, 0
    for task_id, runs in runs_by_task.items():
        scores = {r.model_id: r.score for r in runs}
        if model_id not in scores:
            continue
        total += 1
        best = max(scores.values())
        winners = [m for m, s in scores.items() if math.isclose(s, best, abs_tol=1e-12)]
        if model_id in winners:
            wins += 1.0 / len(winners)
    return (wins / total, total) if total else (0.0, 0)
```

   结果：`a` 为 `(0.5 + 1) / 2 = 0.75`，`b` 为 `(0.5 + 0) / 2 = 0.25`，二者之和为 1。在 demo 数据上新旧实现结果相同（0.75、0.167、0.083），因为连续随机分数几乎不会并列。
3. 会失败（期望 1.0，实际 0.5）。测试锁定的是"代码当前行为"，而讲义描述的是"设计意图"，二者冲突时要先决定哪个是契约：如果采用平分，就修改测试（并把名字改准确，例如 `test_ties_split_evenly`），同时在变更记录里说明 win-rate 定义变了、历史排行榜不可直接比较。

### Q10 — 参考答案

1. 均值是在**不同的任务集合**上算的。`small` 没有做难题，它的 0.95 和 `big` 的 0.6 不是同一把尺子量出来的。这在真实排行榜中很常见：某些模型跑不了代码任务、某些任务因超时缺失。
2. 实测：

| 方式 | big | small |
|------|-----|-------|
| 当前（各自任务均值） | 0.6 | 0.95 |
| (a) 只用共同任务 `{easy1}` | 0.9 | 0.95 |
| (b) 缺失计 0 分 | 0.6 | 0.475 |

   (a) 公平但丢弃数据，共同任务可能很少；(b) 惩罚没跑的任务，适合"缺失 = 失败"（如超时）的场景，但不适合"没有资格参加"的场景。两者都比当前做法更诚实，选择哪种要在报告里写明。
3. 加一列**覆盖率**（coverage = 该模型有分数的任务数 / 全部任务数，这里 `small` 为 0.5），或在 `tasks_completed` 旁边显示总任务数（如 `1/2`）；覆盖率不足的模型单独标注或不参与排名。当前 `Tasks` 列只显示自己完成的数量，读者看不出缺了什么。

### Q11 — 参考答案

1. `C(6, 2) = 15` 对。若相互独立，至少一对误判的概率为 `1 − 0.95^15 ≈ 0.54`。我们用本节 `pairwise_diffs` 做了 40 次模拟（每次 30 个任务、6 个同分布模型）：**50%** 的模拟至少出现一对"显著"，与理论值相近（各对并不独立，且 percentile bootstrap 在 30 个任务上略偏乐观）。
2. 校正：`pairwise_diffs(runs, alpha=0.05 / n_pairs)`。同样 40 次模拟下，至少一对误判的比例降到 12.5%（仍高于 5%，见下一点）。需要增大 B 的原因：α/15 ≈ 0.0033，双侧各取 0.17% 分位数。B = 300 时这只对应约 0.5 个样本，分位数完全由最极端的一两个值决定，非常不稳定；一般要让 `B × α/2` 至少有几十个样本，即 B 取上万。也可以改用 Holm 等更不保守的校正方法。
3. 4 个模型时的种子：(0,1)→1、(0,2)→2、(0,3)→3、(1,2)→3、(1,3)→4、(2,3)→5，`(0,3)` 与 `(1,2)` 共用种子 3。由于每对的任务数相同，两对会使用**完全相同的重采样下标**，二者的 bootstrap 误差相关，不再是独立的估计（单对结果本身仍然有效）。修正：用 `np.random.default_rng([seed, i, j])` 或 `SeedSequence(seed).spawn(n_pairs)` 为每对生成独立的流；或者干脆让所有对共享一套重采样下标（这样做的好处是不同对之间可比），但要有意为之，而不是偶然碰撞。

### Q12 — 参考答案

1. `[0, 1]` 只统一了**取值范围**，没有统一**分布**。例如 exact match 只取 0 或 1，模型之间差距可以达到 0.5；ROUGE-L 通常集中在 0.3–0.5，模型之间只差 0.02。直接平均时，离散指标的方差主导了排名；把 BLEU 从 0–100 除以 100 后，它的数值天然比准确率小一截，同样贡献更少。讲义的目标是"不让 pass rate 和 BLEU 过度影响总分"，仅靠范围校验做不到。
2. 参考做法（已运行验证）：对每个任务，取所有模型在该任务上的最小值与最大值，`(s − lo) / (hi − lo)`，全部相等时记 0.5；再按模型取平均。`steady`/`spiky` 的结果：前 6 题 `spiky` 为 1、`steady` 为 0，后 4 题相反 → `spiky` 0.6、`steady` 0.4，排名翻转，与 win-rate 一致。
3. 副作用：
   - 结果依赖于**参赛模型集合**：新加入一个很弱或很强的模型，会改变其他模型的规范化分数，甚至改变它们之间的排名；
   - 两个模型时退化为 win-rate，丢失差距信息；
   - 微小的差距（0.72 vs 0.70）被放大成 1 vs 0。
   替代方案：按任务 z-score（同样依赖模型集合）、以固定的参考模型或人类基线为锚点规范化、或报告平均排名。无论哪种，都要在报告中写明方法。

### Q13 — 参考回答要点

- **平均分**：直观、利用了差距大小；但对离群任务、任务数量构成、指标尺度都敏感；不同模型任务覆盖不一致时不可比（Q10）。
- **win-rate**：每任务比输赢，对尺度和离群值鲁棒；但丢掉差距大小（Q7 中 0.02 的胜利与 0.4 的失利同等计算），平局处理需要约定（Q9），模型越多单个模型越难赢。
- **平均排名**：每任务对模型排名后取平均，鲁棒、可处理异构指标；同样丢弃差距，且受参赛者影响。
- **规范化后平均**：min-max / z-score / 相对基线，缓解尺度问题但依赖参赛集合（Q12）。
- **实践建议**：同时报告均值（带 CI）和 win-rate（讲义："The harness reports both"），并给出分类别均值；任务按类别先平均再跨类别平均，避免某类任务数量过多主导总分；所有方法写进报告。

### Q14 — 参考回答要点

- **原理**：用样本的经验分布近似总体分布。有放回地从 N 个观测中抽 N 个，计算统计量（均值），重复 B 次，得到统计量的抽样分布近似。
- **percentile 法步骤**（对应 `bootstrap_mean_ci`）：
  1. `idx = rng.integers(0, n, size=n)` 有放回抽下标；
  2. 计算 `arr[idx].mean()`；
  3. 重复 B 次；
  4. 取 `α/2` 与 `1 − α/2` 分位数作为区间。
- **对什么重采样**：评估中的"随机性来源"——通常是任务/样本（本节对任务重采样，回答"换一批同分布的任务，分数会变多少"）。如果关心生成随机性，还要对采样种子做重复。
- **前提与局限**：观测独立同分布；样本量不能太小（10 个任务时区间极宽，见 Q4）；percentile 法在小样本、偏态时覆盖率不足，可用 BCa 等改进；任务之间存在相关（同一家族的数学题）时，独立重采样会低估方差，应做分层/簇 bootstrap（讲义 Going further 提到的 hierarchical bootstrap）；分数有界（0/1）时区间可能贴边。
- 加分点：比较两个模型时使用配对 bootstrap；多对比较时注意多重比较问题。

### Q15 — 参考回答要点

- **事实**：配对差 CI 都不含 0（`a−b` [+0.026, +0.102]、`a−c` [+0.132, +0.249]、`b−c` [+0.058, +0.184]）。
- **需要提醒的局限**：
  - 只有 12 个任务，且是合成数据；bootstrap 在 12 个样本上的 CI 本身不稳定；
  - 任务分 4 个类别、每类 3 个，类别内部相关，独立重采样会低估方差（讲义："math problems are not independent from each other"）；
  - 3 对比较没有做多重比较校正（3 对时 Bonferroni 的 α 为 0.0167）；
  - B = 300 偏小；
  - 每个任务只有一个分数，没有反映生成随机性（同一模型重跑一次分数可能不同）。
- **补充分析**：按类别做分层 bootstrap；增大 B 并换几个种子看结论是否稳定；扩大任务集；报告效应量（差值多大）而不只是"显著与否"；看分类别结果（demo 中 `model_c` 在 summary 上 0.68，接近 `model_b` 的 0.726，说明差距并不均匀）。

### Q16 — 参考回答要点

- **排行榜内容**：每个模型的均值 + 95% CI、win-rate、分类别均值、覆盖率、关键安全/校准指标（第 73 课的 ECE、Brier）；固定的任务集版本、指标实现版本、提示模板版本。
- **发布门槛示例**：
  - 与线上模型在同一任务集上做配对 bootstrap，总体差值 CI 下界 ≥ 0（或 ≥ −ε 的非劣效界）；
  - 每个关键类别（安全、代码、核心业务任务）都不出现显著退化（逐类别配对检验，做多重比较校正）；
  - 校准、延迟、成本等非准确率指标不超出阈值；
  - 覆盖率 100%，没有缺失任务。
- **流程**：评估结果写入 JSON 归档，CI 中自动生成 Markdown 表贴到 PR/发布评论（讲义："a markdown table the runner in lesson 75 can paste into a CI comment"）；门槛不达标需要人工签字豁免。
- 常见误区：只看总体均值；把"差异不显著"当作"两者相同"（应当用非劣效检验）。

### Q17 — 参考回答要点

- 不矛盾。两个**边缘**（各自独立的）CI 重叠，不代表差值不显著。边缘 CI 的宽度包含了"任务难度"带来的方差，而这部分方差对两个模型是**共同**的；配对差把它消掉了，所以差值的 CI 窄得多（本例约 ±0.04，而单个均值 CI 宽约 0.07–0.08）。
- 经验法则：两个 95% CI 不重叠可以推出差异显著，反过来不成立；即使是独立样本，两个 CI 有一定重叠时差异也可能显著。
- 正确做法：比较两个模型就直接对差值做推断（配对 bootstrap），不要靠目测两个均值 CI 是否重叠。
- 加分点：说明这也是 Markdown 表只列边缘 CI 时容易误导读者的原因，应在表下附上配对比较结果（demo 正是这样打印的）。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 15 机器学习统计](../../../01-math-foundations/15-statistics-for-ml/docs/zh.md)：置信区间、假设检验、重采样的统计基础。
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：模型比较与评估指标。
- [阶段 19 · 71 经典评估指标](../../71-classical-metrics/docs/zh.md)：每个任务分数的来源，保证落在 `[0, 1]`。
- [阶段 19 · 72 代码执行评估指标](../../72-code-exec-metric/docs/zh.md)：`code_exec` 分数与 pass@k。
- [阶段 19 · 73 Perplexity 与 Calibration（困惑度与校准）](../../73-perplexity-calibration/docs/zh.md)：多模型报告的另一组数字（ECE、Brier）。

### 本节被哪些后续内容用到
- [阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：把 runner 的结果转成 `EvalRun`，调用 `aggregate` 与 `pairwise_diffs` 生成最终报告与 Markdown 表。
- [阶段 06 · 17 音频 Evaluation — WER、MOS、UTMOS、MMAU、FAD 和开放排行榜](../../../06-speech-and-audio/17-audio-evaluation-metrics/docs/zh.md)：其他领域的公开排行榜实践。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../../16-multi-agent-and-swarms/24-evaluation-coordination-benchmarks/docs/zh.md)：多智能体场景下的基准汇总。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：排行榜在 LLM 评估体系中的位置与陷阱。

### 延伸关键词
`percentile bootstrap` · `BCa interval` · `paired bootstrap` · `hierarchical / cluster bootstrap` · `win rate` · `mean rank` · `Bonferroni / Holm` · `non-inferiority test` · `SeedSequence` · `Elo / Bradley-Terry` · `HELM` · `Open LLM Leaderboard`
