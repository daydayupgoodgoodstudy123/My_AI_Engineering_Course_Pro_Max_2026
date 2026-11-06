# 测验 · 结果评估器（Result Evaluator）

> **阶段 19 · 综合项目 · 第 53 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要配对检验 | 同一配置换个 seed 指标就会变；用相同 seed 分别跑 candidate 与 baseline，每个 seed 给出一个差值，差值的均值是效应、差值的标准误是噪声下限 |
| 2 | 配对 t 检验公式 | `diffs = a_i − b_i`，`t = mean / sqrt(var(ddof=1) / n)`，`df = n − 1`，双侧 p 值 |
| 3 | 从零算 p 值 | 双侧 p = `I_x(df/2, 1/2)`，`x = df / (df + t²)`；正则化不完全 Beta 函数用 Lentz 连分式求值，不依赖 scipy（实测与 scipy 误差 < 2e-12） |
| 4 | 方向感知的改进量 | `higher_is_better`：`(c − b)/|b|`；`lower_is_better`：`(b − c)/|b|`；改进量带符号，正数总是"变好" |
| 5 | 实际显著性门槛 | `|improvement| < 0.02` 直接判 `noise`，不管 p 值多小——循环不关心用户测不出来的变化 |
| 6 | 统计显著性门槛 | `p_value` 为 `None`（n < 2）或 `> 0.05` 判 `noise` |
| 7 | 判决表顺序 | failed → 改进量门槛 → 显著性门槛 → 按符号判 improved / regressed |
| 8 | 失败短路 | 任何一个 run 的 `terminal != "ok"`（代码里 candidate **和** baseline 都查）直接返回 `failed`，并在 rationale 中列出终止原因 |
| 9 | log 尺度指标 | `scale="log"` 时先取自然对数再算均值、改进量和 t 检验；代码的改进量是"对数值的相对变化"，与讲义示例的"对数差"不是一回事 |
| 10 | 按 seed 配对与纯函数 | 用 `metrics["seed"]` 配对，缺 seed / 重复 seed / 无共同 seed 抛 `PairingError`；`Evaluator` 无共享状态，同样输入永远得到同样的 `Verdict` |

### 核心技能（能动手做到）

- [ ] 给定两组按 seed 对齐的指标，手算配对 t 统计量、自由度，并用 `two_sided_t_p_value` 得到 p 值
- [ ] 说清 `I_x(df/2, 1/2)` 与 t 分布双侧尾概率的关系，以及为什么 `t=0` 时 p 值为 1
- [ ] 按方向规则写出改进量，并对 lower-is-better 指标正确判断符号
- [ ] 走一遍五步判决表，给任意 `(improvement, p_value, n)` 判出 verdict
- [ ] 指出 log 尺度改进量对单位敏感的问题，并改成单位无关的"对数比"
- [ ] 把 `_pair_by_seed` 改成严格模式，或给评估器加上最少 seed 数、置信区间等统计护栏

---

## 二、基础自测（选择题）

**Q1.** 讲义坚持用"配对"检验，而不是直接比较 candidate 和 baseline 各自的一次运行结果。根本原因是：

- A. 配对检验的计算量更小
- B. 同一配置换 seed 就会得到不同指标；让两边共用同一组 seed，每个 seed 的差值消掉了"随机初始化"这部分噪声，剩下的差异才归因于配置改动
- C. runner 每次只能输出一个数字，必须两两配对
- D. 不配对就无法计算均值

**Q2.** 指标 `loss`，`direction="lower_is_better"`、`scale="linear"`。baseline 均值 0.50，candidate 均值 0.70。`_improvement` 返回：

- A. `+0.40`
- B. `+0.20`
- C. `−0.20`
- D. `−0.40`

**Q3.** 测试 `test_small_change_is_noise` 中，candidate 比 baseline 每个 seed 都恰好高 0.001，实测 `p_value = 0.0`（差值方差为 0），改进量约 0.0013。最终 verdict 是：

- A. `"noise"`，因为改进量门槛（0.02）在显著性检验之前判断
- B. `"improved"`，因为 p 值远小于 0.05
- C. `"failed"`，因为方差为 0 属于异常
- D. `"regressed"`

**Q4.** demo 中 `scale="log"`，输出 `candidate_mean=26.425`、`baseline_mean=30.775`、`improvement=0.044622`。可是 `(30.775 − 26.425)/30.775 ≈ 0.1413`。造成差异的原因是：

- A. 代码在算改进量时用了中位数而不是均值
- B. `to_dict` 的四舍五入误差
- C. 改进量是在对数空间算的：`(mean(log b) − mean(log c)) / |mean(log b)|`，即"对数困惑度（≈ loss）的相对下降"；而 `candidate_mean/baseline_mean` 报告的是原始尺度的算术平均
- D. 改进量把 p 值也乘了进去

**Q5.** `paired_t_test` 在什么情况下返回 `p_value = None`？

- A. 差值方差为 0 时
- B. 两边均值相等时
- C. 配对样本数 n < 2 时（没有自由度，无法估计方差）
- D. 指标为 log 尺度时

**Q6.** candidate 全部 `ok`，但 baseline 中有一个 run 的 `terminal="oom"`。`Evaluator.evaluate` 的结果是：

- A. `verdict="failed"`，rationale 为 `runs failed with terminals ['oom']`
- B. 丢掉这个 seed，用剩下的 seed 正常检验
- C. 正常检验，因为讲义判决表第 1 条只检查 candidate
- D. 抛出 `PairingError`

**Q7.** `two_sided_t_p_value(t, df)` 内部调用 `regularised_incomplete_beta(df/2, 0.5, x)`。其中 `x` 等于：

- A. `t / df`
- B. `t² / (df + t²)`
- C. `1 − 1/df`
- D. `df / (df + t²)`

**Q8.** candidate 的 seed 为 `{0, 1, 2}`，baseline 的 seed 为 `{1, 2, 5}`，全部 `ok`。实际运行时会发生什么？

- A. 抛出 `PairingError("seeds do not match")`，与讲义描述一致
- B. 不报错：只用共同的 seed 1、2 配对，seed 0 和 5 被静默丢弃；`candidate_mean` 也只按这两个 seed 计算
- C. 把缺失的一边补 0 后配对
- D. 返回 `verdict="failed"`

---

## 三、动手 / 代码题

**Q9.** log 尺度改进量的实现：

```python
        cand_t = _log_transform(cand_vals, metric_spec.scale)
        base_t = _log_transform(base_vals, metric_spec.scale)
        ...
        improvement = _improvement(cand_mean_t, base_mean_t, metric_spec.direction)

def _improvement(candidate_mean, baseline_mean, direction):
    denom = abs(baseline_mean) if baseline_mean != 0.0 else 1.0
    raw = (candidate_mean - baseline_mean) / denom
    ...
```

1. 讲义说"困惑度从 32 降到 28，即 `log(28) − log(32) = −0.133`，远高于 2% 门槛"。按代码实际计算，这对数字的改进量是多少？
2. 一个 lower-is-better 的 `wall_time` 指标用 `scale="log"`：candidate 为 `[2.0, 2.1, 1.9]`，baseline 为 `[2.5, 2.6, 2.4]`。以秒为单位与以毫秒为单位，代码算出的改进量分别是多少？这说明了什么？
3. 改写 log 尺度的改进量，使它与单位无关，并给出上面两个例子在新定义下的值。

**Q10.** 讲义："If the seeds do not match across the two lists, the evaluator raises a `PairingError`." 但 Q8 显示代码只在"完全没有共同 seed"时报错。

1. 静默丢弃不匹配的 seed 会带来什么风险？（提示：想想哪些 seed 更可能"缺席"。）
2. 给 `_pair_by_seed` 增加 `strict: bool = True` 参数：严格模式下两边 seed 集合不相等就抛 `PairingError`，并在错误信息里列出只出现在一边的 seed。写出代码和一个对应的单元测试。

**Q11.** 手算题。candidate 3 个 seed 的准确率为 `[0.90, 0.95, 0.80]`，baseline 为 `[0.70, 0.72, 0.75]`（higher_is_better，linear）。

1. 写出差值、差值均值、样本方差（ddof=1）、t 统计量和自由度。
2. 改进量是多少？已知 `two_sided_t_p_value` 给出 p ≈ 0.1028，最终 verdict 是什么？
3. 如果只用前两个 seed（n=2），实测改进量 0.3028、p ≈ 0.0443，verdict 变成 `improved`。你如何看待"2 个 seed 就宣布显著改进"？

**Q12.** 给评估器加两道统计护栏：

1. `EvaluatorConfig` 增加 `min_pairs: int = 3`，n 小于它时判 `noise`；
2. 在 `Verdict` 中增加差值均值的 95% 置信区间 `ci_low / ci_high`。不允许引入 scipy，t 分布的临界值请复用 `two_sided_t_p_value` 用二分法求出。写出 `t_critical(df, alpha)` 并说明如何验证它。

---

## 四、面试高频题

**Q13.**（基础必考）配对 t 检验和独立样本 t 检验（如 Welch t 检验）有什么区别？在模型对比实验中各自什么时候用？

**Q14.**（原理深挖）p 值到底表示什么？为什么本节的判决表要在显著性检验之前先卡一个"改进量 ≥ 2%"的门槛？统计显著与实际显著有什么区别？

**Q15.**（工程实践）自动研究循环每天评估上百个假设，每个都用 α = 0.05。这会出现什么问题？你会如何在评估器和编排器层面应对？

**Q16.**（场景设计）你要为一个 LLM 功能做上线前评估：准确率希望上升、延迟和成本不能明显变差。请基于本节的 `MetricSpec / Verdict` 设计一个多指标判决方案。

**Q17.**（追问型）只有 5 个 seed、差值明显不服从正态分布（例如有一个离群 seed），t 检验还可靠吗？有哪些替代方法？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："The same configuration with a different seed gives a different perplexity... The right comparison is paired: the same seeds with the same data... Each seed contributes a difference. The mean of those differences is the effect. The standard error of those differences is the noise floor." 配对的价值在于：同一 seed 下 candidate 和 baseline 共享了"好运 / 坏运"，作差后这部分共同噪声被抵消。

- A 错：配对与否计算量相当，关键是统计效率。
- C 错：runner 输出的是完整指标字典，与是否配对无关。
- D 错：均值随时可算。

### Q2 — 答案：D

`raw = (0.70 − 0.50) / |0.50| = +0.40`，`direction == LOWER` 时返回 `−raw = −0.40`。改进量为负表示 candidate 变差。这正是测试 `test_regressed_lower_is_better` 的情形（0.7 vs 0.5，断言 `improvement < 0` 且 verdict 为 `regressed`）。A 忘了按方向取反；B、C 把相对变化算成了绝对差 0.2。

### Q3 — 答案：A

```python
    def _verdict(self, improvement, p_value, n):
        if abs(improvement) < self._cfg.improvement_threshold:
            return "noise", ...
        if p_value is None:
            return "noise", ...
        if p_value > self._cfg.significance_threshold:
            return "noise", ...
```

实测 rationale：`improvement 0.0013 is below threshold 0.02`。讲义："Below that the verdict is 'noise' regardless of the p value; the loop is not interested in changes the user could not measure." B 忽略了门槛顺序；C 错，方差为 0 时代码返回 `p=0.0`（均值非零）并不报错；D 方向不对。

### Q4 — 答案：C

实测：`mean(log c) = 3.273376`，`mean(log b) = 3.426261`，`(3.426261 − 3.273376)/3.426261 = 0.044622`。log 困惑度就是交叉熵 loss，所以这个数字的含义是"平均 loss 相对下降 4.46%"。若按线性尺度算，改进量为 0.1413（实测）。而报告字段 `candidate_mean / baseline_mean` 用的是原始值 `np.mean(cand_vals)`，所以字段之间看起来"对不上"。A、B、D 均不是代码行为（`to_dict` 只保留 6 位小数，误差极小）。

### Q5 — 答案：C

```python
    if n < 2:
        if n == 0:
            return 0.0, None, 0
        return float(candidate[0] - baseline[0]), None, n
```

n = 1 时 `ddof=1` 的方差分母为 0，无法估计。A 错：方差为 0 时返回 `0.0`（均值非零）或 `1.0`（均值为零）；B 错：均值相等时仍会正常计算 t = 0、p = 1；D 与 n 无关。判决时 `p_value is None` 一律判 `noise`（测试 `test_one_seed_is_noise`）。

### Q6 — 答案：A

```python
        bad = [r for r in [*candidates, *baselines] if r.terminal != "ok"]
        if bad:
            return self._failed_verdict(hypothesis_id, metric_spec, bad)
```

实测：`verdict='failed'`、rationale `runs failed with terminals ['oom']`。注意讲义判决表第 1 条写的是 "If any candidate result has terminal != ok"，代码更严格，把 baseline 也算进去——这是合理的：baseline 失败同样让比较失去意义。C 正是照讲义字面理解的结果，与代码不符；B、D 都不是代码行为。

### Q7 — 答案：D

t 分布的双侧尾概率有恒等式 `P(|T| > |t|) = I_{df/(df+t²)}(df/2, 1/2)`。代码：

```python
    x = df / (df + t_stat * t_stat)
    p = regularised_incomplete_beta(df / 2.0, 0.5, x)
```

检查边界：`t = 0` 时 `x = 1`，`I_1 = 1`，p = 1（测试 `test_t_zero_is_one`）；`|t| → ∞` 时 `x → 0`，p → 0。`t²` 让正负 t 得到相同 p（实测 `t=±2.228, df=10` 都是 0.050012）。B 是 `1 − x`；由对称性 `I_{1−x}(1/2, df/2) = 1 − p`，它对应的是 `P(|T| < |t|)`（且参数顺序也不同），代入本函数会得到错误结果。

### Q8 — 答案：B

```python
    shared = sorted(set(cand_map.keys()) & set(base_map.keys()))
    if not shared:
        raise PairingError("no shared seeds between candidate and baseline")
    return [cand_map[s] for s in shared], [base_map[s] for s in shared]
```

只取交集。实测：`candidate_mean=0.915`（只有 seed 1、2 的 0.91、0.92），`baseline_mean=0.705`，没有任何警告。讲义说 seed 不匹配就抛 `PairingError`、让编排器重跑，代码只实现了"完全不相交"这一种情况，测试 `test_no_shared_seeds_raises` 也只覆盖了它。修法见 Q10。

### Q9 — 参考答案

1. 代码的改进量是 `(log 32 − log 28) / log 32 = 0.1335 / 3.4657 ≈ 0.0385`（已用 Python 计算），不是讲义说的 0.133。结论（超过 2% 门槛）不变，但数值差了约 3.5 倍。讲义描述的是"对数差"，代码实现的是"对数值的相对变化"。
2. 实测：以秒为单位时改进量 **0.2440**，以毫秒为单位时 **0.0286**。同一组实验，只因为换了单位，改进量差了 8.5 倍；如果门槛是 3%，秒制会判"有改进"，毫秒制会判"噪声"。原因：`log(x·1000) = log x + 6.91`，分子（对数差）不变，分母 `|mean(log b)|` 却随单位剧烈变化。同理，困惑度接近 1 时 `log b` 接近 0，改进量会被放大（实测 1.02 → 1.01 的改进量为 0.4975）。
3. 单位无关的定义——直接用对数差（即几何均值之比的对数）：

```python
def _improvement_log(cand_mean_log: float, base_mean_log: float, direction: str) -> float:
    raw = cand_mean_log - base_mean_log          # = log(几何均值之比)，与单位无关
    return -raw if direction == LOWER else raw

# 在 evaluate 中：
if metric_spec.scale == LOG:
    improvement = _improvement_log(cand_mean_t, base_mean_t, metric_spec.direction)
else:
    improvement = _improvement(cand_mean_t, base_mean_t, metric_spec.direction)
```

   新定义下：wall_time 例子无论秒还是毫秒都是 **0.2234**（≈ 几何均值下降 20.0%，因为 `1 − e^{−0.2234} = 0.200`）；讲义例子 32 → 28 为 **0.1335**，与讲义一致；demo 为 **0.1529**。对数差在小变化时约等于相对变化，因此 2% 的门槛仍有直观含义。也可以报告 `1 − exp(−raw)` 这种"几何均值相对变化"，更便于向人解释。修改后需要同步更新测试中对 log 改进量的断言。

### Q10 — 参考答案

1. **风险**：缺席的 seed 往往不是随机的——更可能是"某一边跑崩了 / 超时了 / 被调度器跳过了"的那些。只保留双方都成功的 seed 等于**按结果筛样本**（幸存者偏差），可能系统性地高估某一边。而且 n 被悄悄缩小，统计功效下降，使用者却以为每边都跑满了。讲义的意图是"让编排器重跑"，而不是悄悄降级。
2. 参考实现（已在本地验证）：

```python
def _pair_by_seed(candidates, baselines, metric, strict: bool = True):
    cand_map = _seed_map(candidates, metric, "candidate")   # 把原来两段重复逻辑抽成一个函数
    base_map = _seed_map(baselines, metric, "baseline")
    cand_seeds, base_seeds = set(cand_map), set(base_map)
    if strict and cand_seeds != base_seeds:
        only_c = sorted(cand_seeds - base_seeds)
        only_b = sorted(base_seeds - cand_seeds)
        raise PairingError(
            f"seed sets differ: only in candidate {only_c}, only in baseline {only_b}"
        )
    shared = sorted(cand_seeds & base_seeds)
    if not shared:
        raise PairingError("no shared seeds between candidate and baseline")
    return [cand_map[s] for s in shared], [base_map[s] for s in shared]


def _seed_map(results, metric, side):
    out = {}
    for r in results:
        seed = r.metrics.get("seed")
        if seed is None:
            raise PairingError(f"{side} {r.spec_id} missing seed")
        seed_i = int(seed)
        if seed_i in out:
            raise PairingError(f"duplicate {side} seed {seed_i} (spec {r.spec_id})")
        if metric not in r.metrics:                       # 顺便把 KeyError 变成可读错误
            raise PairingError(f"{side} {r.spec_id} missing metric {metric!r}")
        out[seed_i] = float(r.metrics[metric])
    return out
```

```python
    def test_partial_overlap_raises_in_strict_mode(self) -> None:
        evaluator = Evaluator()
        with self.assertRaises(PairingError) as ctx:
            evaluator.evaluate(
                9, MetricSpec("acc"),
                [res(0, "acc", 0.9), res(1, "acc", 0.91), res(2, "acc", 0.92)],
                [res(1, "acc", 0.70), res(2, "acc", 0.71), res(5, "acc", 0.72)],
            )
        self.assertIn("[0]", str(ctx.exception))
        self.assertIn("[5]", str(ctx.exception))
```

   附带修复：原代码在指标缺失时抛的是裸 `KeyError: 'acc'`（实测），改成 `PairingError` 后编排器只需捕获一种异常。是否允许非严格模式可通过 `EvaluatorConfig` 暴露，默认严格。

### Q11 — 参考答案

1. 差值 `[0.20, 0.23, 0.05]`；均值 `0.16`；样本方差 `((0.04)² + (0.07)² + (−0.11)²)/2 = 0.0186/2 = 0.0093`，标准差 `0.0964`；标准误 `0.0964/√3 = 0.0557`；`t = 0.16 / 0.0557 ≈ 2.874`；`df = 2`。（与 `scipy.stats.ttest_rel` 结果一致。）
2. 改进量 `(mean c − mean b)/|mean b| = (0.8833 − 0.7233)/0.7233 ≈ 0.2212`，远超 2% 门槛；但 p ≈ 0.1028 > 0.05，判 `noise`，rationale 为 `p value 0.1028 exceeds significance threshold 0.05`。df = 2 时 t 分布尾部很厚，双侧 5% 临界值高达 4.303，t = 2.87 不够。
3. n = 2 时 df = 1，95% 临界值为 12.706，只有两个差值几乎完全相同时才会"显著"——这恰恰说明**结论依赖于两个点的偶然接近**，而且无法检查正态性假设。更极端的是：若所有差值完全相等，代码直接给出 `p = 0.0`（方差为 0 分支），哪怕只有 2 个 seed。工程上应规定最少 seed 数（例如 ≥ 5），并同时报告效应量和置信区间（见 Q12），而不是只看 p 值。

### Q12 — 参考答案

```python
@dataclass
class EvaluatorConfig:
    improvement_threshold: float = 0.02
    significance_threshold: float = 0.05
    min_pairs: int = 3


def t_critical(df: int, alpha: float = 0.05) -> float:
    """找 t* 使 two_sided_t_p_value(t*, df) == alpha。p 随 t 单调递减，二分即可。"""
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if two_sided_t_p_value(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def mean_diff_ci(cand: list[float], base: list[float], alpha: float = 0.05) -> tuple[float, float]:
    diffs = np.array(cand) - np.array(base)
    n = len(diffs)
    se = float(diffs.std(ddof=1)) / math.sqrt(n)
    tc = t_critical(n - 1, alpha)
    m = float(diffs.mean())
    return m - tc * se, m + tc * se
```

在 `_verdict` 的显著性判断之前加：

```python
        if n < self._cfg.min_pairs:
            return "noise", f"only {n} paired sample(s); need at least {self._cfg.min_pairs}"
```

**验证 `t_critical`**：用熟知的 t 表值比对（已实测）：df=1 → 12.7062，df=2 → 4.3027，df=7 → 2.3646，df=10 → 2.2281，df=30 → 2.0423，与 `scipy.stats.t.ppf(0.975, df)` 一致到 1e-12 量级。还可以做"往返测试"：`two_sided_t_p_value(t_critical(df), df) ≈ alpha`。

**示例**：Q11 的 3 个 seed，95% CI 为 `[−0.080, 0.400]`，跨过 0，与 p > 0.05 一致；demo 在对数空间的差值 CI 为 `[−0.165, −0.141]`，远离 0。CI 比单个 p 值多告诉你"效应可能有多大"，适合写进 54 节论文的结果表。

### Q13 — 参考回答要点

- **配对 t 检验**：对每个配对单元（这里是 seed）求差，再对差值做单样本 t 检验，`df = n − 1`。前提是两组数据之间有一一对应关系，且同一单元的两次测量正相关（共享 seed、数据顺序）。正相关越强，差值方差越小，检验越灵敏。
- **独立样本 t 检验（Welch）**：两组样本互不对应，用各自的方差估计合并标准误，自由度用 Welch–Satterthwaite 近似，不要求方差相等。
- **怎么选**：
  - 同 seed、同数据划分、同评测集的 A/B 对比 → 配对；
  - 两组 run 来自不同 seed 集合、或者线上两批独立用户 → 独立样本（Welch）；
  - 同一评测集上逐样本对比两个模型 → 配对（可以按样本配对，样本数大得多）。
- 加分点：配对并不总是更灵敏——如果配对单元内没有正相关，配对反而损失自由度。例如 Q11 的数据，配对 p = 0.103，而 Welch p = 0.056（实测）。在本节的场景里，同 seed 共享初始化与数据顺序，通常是强正相关，配对更合适。
- 常见误区：把 seed 打乱后仍用配对检验；或者对"同一评测集上的两个模型"用独立样本检验，白白浪费了配对信息。

### Q14 — 参考回答要点

- **p 值**：在"零假设成立（真实效应为 0）且模型假设成立"的前提下，观察到至少这么极端结果的概率。它**不是**"零假设为真的概率"，也**不是**"效应有多大"。
- **为什么先卡改进量**：
  - n 很大或噪声极小时，微不足道的差异也能非常"显著"（Q3 中 0.001 的差值 p = 0）；
  - 研究循环的资源有限，只关心"用户能感受到"的变化，讲义："the loop is not interested in changes the user could not measure"；
  - 先判改进量还能省掉无意义的检验，并让 rationale 更直观。
- **统计显著 vs 实际显著**：前者回答"这个差异是不是噪声"，后者回答"这个差异值不值得在意"。完整判断需要两者兼备，再加上效应量与置信区间。
- 加分点：2% 门槛是"最小有意义效应（minimum detectable / meaningful effect）"的工程化表达，应在实验开始前确定，并据此估算需要的 seed 数（功效分析）。
- 常见误区：p = 0.049 判有效、p = 0.051 判无效，把阈值当成真理；或者看到不显著就宣称"两者相同"——不显著只代表证据不足。

### Q15 — 参考回答要点

- **问题**：多重比较。即使所有假设都无效，每个检验仍有 5% 的概率误判为显著，100 个假设平均会有约 5 个"假阳性改进"，而循环恰恰会挑最好的结果往下走（赢家诅咒），被选中的往往是噪声最大的那个。
- **评估器层面**：
  - 族错误率控制（Bonferroni：α/m）或更温和的错误发现率控制（Benjamini–Hochberg）；
  - 提高最小改进量门槛、要求更多 seed；
  - 报告置信区间与效应量，而不只是二值结论。
- **编排器层面**：
  - **确认实验**：初筛判 `improved` 的假设，用一组全新的 seed 重跑一次，再判一次（相当于留出验证）；
  - 预先注册：评估指标、方向、阈值在跑实验之前写进 `MetricSpec`，不允许事后换指标；
  - 记录所有被检验的假设（包括失败的），供 54 节论文写作时如实报告。
- 加分点：把"同一假设反复换 knob 直到显著"也视为多重比较（p-hacking）；56 节调度器的探索预算本质上也在控制这一点。

### Q16 — 参考回答要点

- **指标定义**：每个指标一个 `MetricSpec`：`accuracy`（HIGHER，linear）、`latency_p95`（LOWER，log——延迟跨数量级且右偏）、`cost_per_request`（LOWER，linear 或 log）。
- **主指标与护栏指标**：
  - 主指标：accuracy，必须 `improved`；
  - 护栏指标：延迟、成本不能 `regressed`（或回退不超过允许幅度，例如 5%），这需要"非劣效检验"（non-inferiority）：检验"变差幅度是否显著小于容忍度"，而不是检验"是否有差异"。
- **聚合规则**：任一指标 `failed` → 整体 failed；主指标 improved 且所有护栏不 regressed → 上线；否则给出逐项 rationale。
- **配对单元**：同一评测集上按**样本**配对（每条 prompt 在两个版本上各跑一次），样本量远大于 seed 数；对生成随机性再加多 seed。
- **多重比较**：指标多了同样需要校正，或者明确主指标唯一。
- 加分点：注意 log 尺度改进量的单位问题（Q9），延迟用毫秒还是秒不应改变结论；线上阶段再接 [阶段 17 · 21](../../../17-infrastructure-and-production/21-ab-testing-llm-features/docs/zh.md) 的 A/B 测试。

### Q17 — 参考回答要点

- **t 检验的假设**：差值近似正态、各差值独立。n 小时对离群值非常敏感——一个离群 seed 会同时拉偏均值和放大方差。
- **替代方法**：
  - **Wilcoxon 符号秩检验**：只用差值的符号和秩次，不假设正态，对离群值稳健；n 很小时能达到的最小 p 值有限（n = 5 时双侧最小约 0.0625），这本身就提醒"5 个 seed 不够"；
  - **符号检验**：更粗但更稳健；
  - **配对置换检验（permutation test）**：随机翻转每个差值的符号，构造零分布，几乎没有分布假设；
  - **Bootstrap 置信区间**：对差值有放回重采样，得到均值差的 CI；
  - 更换统计量：截尾均值、中位数差。
- **工程上**：先排查离群 seed 是否是故障（OOM 边缘、数据加载错误）；增加 seed 数；把这些方法实现成可选的 `test` 字段，和本节一样保持纯函数、可复现（置换 / bootstrap 也要固定随机种子）。
- 常见误区：直接删除"看起来不对"的 seed 让结果显著——这是数据窥探。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 15 机器学习统计](../../../01-math-foundations/15-statistics-for-ml/docs/zh.md)：假设检验、p 值、t 分布、置信区间的基础。
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：模型对比与评估方法论。
- [阶段 19 · 52 实验执行器](../../52-experiment-runner/docs/zh.md)：本节的输入——`terminal`、`metrics` 以及 `metrics["seed"]` 都来自 runner。
- [阶段 19 · 50 研究假设生成器](../../50-hypothesis-generator/docs/zh.md)：`hypothesis_id` 的来源，`Verdict` 最终挂回假设队列。
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../27-eval-harness-fixture-tasks/docs/zh.md)：Track A 中"可复现评估"的思路。

### 本节被哪些后续内容用到
- [阶段 19 · 54 论文写作器](../../54-paper-writer/docs/zh.md)：把 `Verdict` 写进论文的结果与讨论章节。
- [阶段 19 · 55 Critic 评审循环](../../55-critic-loop/docs/zh.md)：评审者会质疑统计结论是否站得住。
- [阶段 19 · 56 迭代调度器](../../56-iteration-scheduler/docs/zh.md)：根据 verdict 决定继续探索还是停止。
- [阶段 19 · 57 端到端研究演示](../../57-end-to-end-research-demo/docs/zh.md)：把评估器接入完整循环。
- [阶段 17 · 21 对 LLM Features 进行 A/B 测试](../../../17-infrastructure-and-production/21-ab-testing-llm-features/docs/zh.md)：线上实验中的显著性检验与多指标决策。

### 延伸关键词
`paired t-test` · `Welch t-test` · `regularized incomplete beta` · `Lentz continued fraction` · `effect size` · `confidence interval` · `minimum detectable effect` · `power analysis` · `multiple comparisons` · `Benjamini–Hochberg` · `Wilcoxon signed-rank` · `permutation test` · `bootstrap` · `non-inferiority test`
