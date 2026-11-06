# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 53 节 结果评估器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下；测试：`python3 -m pytest -q` 或 `python3 -m unittest discover tests`） ｜ **依赖**：标准库（`math`、`json`、`dataclasses`）+ `numpy`（第三方，只用于求均值、方差和数组相减）；不依赖 scipy

---

## 1. 这份代码在考察什么

52 节的 runner 产出了数字，本节要回答："这些数字代表**改进、退步，还是噪声**？"它把一组 candidate 运行和一组 baseline 运行（按 seed 对齐）变成一行结论 `Verdict`。

具体考察：

1. **配对 t 检验**：同 seed 作差，用差值的均值和标准误构造 t 统计量。
2. **从零计算 p 值**：用正则化不完全 Beta 函数 + Lentz 连分式求 t 分布双侧尾概率，不调用 `scipy.stats`。
3. **方向感知的改进量**：accuracy 越大越好、loss 越小越好，统一成"正数 = 变好"。
4. **log 尺度归一化**：困惑度等指数型指标先取对数。
5. **判决表**：failed → 改进量门槛 → 显著性门槛 → improved / regressed。
6. **纯函数**：没有共享状态，同样输入永远同样输出。

> 一句话：**把"统计显著"和"实际显著"两道门串起来，给每个假设一个可追溯的判决**。同时要看到它在 log 尺度改进量、seed 配对上与讲义的出入——这些都是真实评估系统里容易埋雷的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HIGHER / LOWER / LOG / LINEAR` | 模块常量 | 方向与尺度的字符串取值 | 指标元数据 |
| `ExperimentResultLike` | dataclass | 只含 `spec_id / terminal / metrics` 的"结果替身" | 与 52 节解耦 |
| `MetricSpec` | dataclass | 指标名、方向、尺度，`validate()` 校验取值 | 指标规格 |
| `Verdict` | dataclass | 判决记录，`to_dict()` 四舍五入后输出 | 判决结果 |
| `PairingError` | 异常类 | 无法按 seed 配对时抛出 | 配对契约 |
| `_lentz_betacf` | 函数 | 不完全 Beta 函数的连分式（修正 Lentz 算法） | 数值计算 |
| `regularised_incomplete_beta` | 函数 | `I_x(a, b)`，含端点和对称性切换 | 特殊函数 |
| `two_sided_t_p_value` | 函数 | `p = I_{df/(df+t²)}(df/2, 1/2)` | t 分布尾概率 |
| `paired_t_test` | 函数 | 返回 `(mean_diff, p_value, n)` | 配对 t 检验 |
| `_pair_by_seed` | 函数 | 按 `metrics["seed"]` 对齐两组结果 | 配对 |
| `_improvement` | 函数 | 方向感知的相对改进量 | 改进量 |
| `_log_transform` | 函数 | log 尺度时取自然对数，非正数报错 | 尺度归一化 |
| `EvaluatorConfig` | dataclass | 改进量门槛 0.02、显著性门槛 0.05 | 阈值配置 |
| `Evaluator` | 类 | `evaluate` 主流程、`_failed_verdict`、`_verdict` 判决表 | 判决路径 |
| `_demo` | 函数 | 8 个 seed 的困惑度对比，打印 JSON | 演示 |

数据流：`candidates, baselines` → 失败短路检查 → `_pair_by_seed` 得到两列数值 → `_log_transform` → `paired_t_test`（→ `two_sided_t_p_value` → `regularised_incomplete_beta` → `_lentz_betacf`）‖ `_improvement` → `_verdict` → `Verdict`。

---

## 3. 逐段精讲

### 3.1 数据结构：结果替身、指标规格、判决

```python
@dataclass
class ExperimentResultLike:
    spec_id: str
    terminal: str
    metrics: dict
```

- 评估器只依赖 52 节 `ExperimentResult` 的三个字段。用一个"子集结构"而不是直接 import 52 节的类，测试可以直接构造对象，两个模块不互相依赖——这就是**鸭子类型**（duck typing）：真实的 `ExperimentResult` 也有这三个属性，同样能传进来。

```python
@dataclass
class MetricSpec:
    name: str
    direction: str = HIGHER
    scale: str = LINEAR

    def validate(self) -> None:
        if self.direction not in (HIGHER, LOWER):
            raise ValueError(f"unknown direction {self.direction!r}")
        ...
```

- 方向和尺度用字符串常量而不是 `Enum`，序列化成 JSON 更直接；代价是拼写错误要靠 `validate()` 在运行时发现。`{...!r}` 用 `repr` 打印，字符串会带引号，错误信息更清楚。
- `Verdict` 字段与讲义 "The Verdict shape" 一致；`to_dict()` 把浮点数四舍五入到 6 位。⚠️ demo 的真实 p 值是 `1.24e-8`，四舍五入后显示为 `0.0`，rationale 里也是 `p=0.0000`——p 值很小时应改用科学计数法显示。

### 3.2 Lentz 连分式与不完全 Beta 函数

```python
def regularised_incomplete_beta(a: float, b: float, x: float) -> float:
    if x < 0.0 or x > 1.0:
        raise ValueError("x out of [0, 1]")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log(1.0 - x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _lentz_betacf(a, b, x) / a
    return 1.0 - bt * _lentz_betacf(b, a, 1.0 - x) / b
```

- 正则化不完全 Beta 函数 `I_x(a, b) = B(x; a, b) / B(a, b)`，取值在 [0, 1]，是 Beta 分布的累积分布函数。
- **前置因子** `bt = x^a (1−x)^b / B(a, b)`：在**对数空间**里用 `math.lgamma`（Gamma 函数的对数）计算再取 `exp`，避免 `Γ(a)` 在 a 较大时溢出。
- **对称性切换**：`x < (a+1)/(a+b+2)` 时连分式收敛快，直接算；否则利用 `I_x(a, b) = 1 − I_{1−x}(b, a)` 换到收敛快的一侧。这是《Numerical Recipes》里的标准做法。
- 端点 0 和 1 单独处理，避免 `math.log(0)` 报错（测试 `test_endpoints`）。

```python
def _lentz_betacf(a, b, x, max_iter=200, eps=1e-12):
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    ...
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))        # 偶数项系数
        d = 1.0 + aa * d; ...; c = 1.0 + aa / c; ...
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))   # 奇数项系数
        ...
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    return h
```

- 连分式 `1/(1+ d1/(1+ d2/(1+ ...)))` 的系数分奇偶两种，每轮循环处理一对。
- **修正 Lentz 算法**：不从尾部往回算，而是维护两个比值 `c`、`d`，每一步把 `h` 乘上 `c·d`，当乘子 `delta` 足够接近 1 时停止。
- `if abs(d) < eps: d = eps`：防止除以 0 的保护（Lentz 算法的"修正"之处）。
- ⚠️ 迭代 200 次仍未收敛时**静默返回**当前值，不报警。对本节的 df 范围没有问题（我们实测 df 从 1 到 1000、t 从 0.01 到 50，与 `scipy.stats.t.sf` 的最大绝对误差为 1.8e-12），但极端参数下应至少记录一条警告。

### 3.3 双侧 p 值与配对 t 检验

```python
def two_sided_t_p_value(t_stat: float, df: int) -> float:
    if df <= 0:
        return 1.0
    x = df / (df + t_stat * t_stat)
    p = regularised_incomplete_beta(df / 2.0, 0.5, x)
    return max(0.0, min(1.0, p))
```

- 恒等式：自由度为 df 的 t 分布，`P(|T| > |t|) = I_{df/(df+t²)}(df/2, 1/2)`。`t²` 使正负 t 结果相同。
- `t = 0` → `x = 1` → p = 1；`|t|` 越大 → `x` 越小 → p 越小（测试 `test_p_decreases_with_t`）。
- `max(0, min(1, p))` 把浮点误差夹回合法区间。
- 参考值：`t = 2.228, df = 10` 时 p = 0.050012（实测，与 t 表中 df=10 的 95% 临界值 2.228 对应）。

```python
def paired_t_test(candidate, baseline):
    if len(candidate) != len(baseline):
        raise PairingError("candidate and baseline lengths disagree")
    n = len(candidate)
    if n < 2:
        if n == 0:
            return 0.0, None, 0
        return float(candidate[0] - baseline[0]), None, n
    diffs = np.array(candidate) - np.array(baseline)
    mean_diff = float(diffs.mean())
    var_diff = float(diffs.var(ddof=1))
    if var_diff == 0.0:
        return mean_diff, (0.0 if mean_diff != 0.0 else 1.0), n
    t_stat = mean_diff / math.sqrt(var_diff / n)
    p = two_sided_t_p_value(t_stat, n - 1)
    return mean_diff, p, n
```

- 与讲义伪代码一一对应：`diffs → mean → variance(n−1) → t → df = n−1 → p`。
- `ddof=1`：样本方差除以 `n − 1`（无偏估计）。NumPy 的 `var` 默认 `ddof=0`，这里必须显式写。
- `n < 2` 返回 `None`：没有自由度，无法估计方差。
- **方差为 0 的特判**：所有差值完全相同时 t 为无穷大，代码直接给 p = 0（均值非零）或 p = 1（全为 0）。⚠️ 这意味着即使只有 2 个 seed，只要差值恰好相等就"极其显著"；而浮点误差又可能让"本该相等"的差值方差变成 1e-33 这类极小值（实测 `[0.1+0.2, 0.3]` 对 `[0, 0]` 得到 p ≈ 8.3e-17），二者结论一致，但都缺乏统计意义。生产中应配合最少样本数（测验 Q12）。

### 3.4 按 seed 配对

```python
def _pair_by_seed(candidates, baselines, metric):
    cand_map: dict[int, float] = {}
    for r in candidates:
        seed = r.metrics.get("seed")
        if seed is None:
            raise PairingError(f"candidate {r.spec_id} missing seed")
        seed_i = int(seed)
        if seed_i in cand_map:
            raise PairingError(f"duplicate candidate seed {seed_i} (spec {r.spec_id})")
        cand_map[seed_i] = float(r.metrics[metric])
    ...  # baseline 同样处理
    shared = sorted(set(cand_map.keys()) & set(base_map.keys()))
    if not shared:
        raise PairingError("no shared seeds between candidate and baseline")
    return [cand_map[s] for s in shared], [base_map[s] for s in shared]
```

- seed 从 `metrics["seed"]` 读取——52 节的 `sparsity_experiment.py` 正是把 `__seed` 回显到最终指标里，两节在这里对接。
- 三种错误：缺 seed、重复 seed、没有共同 seed。`sorted(...)` 让配对顺序确定。
- ⚠️ **与讲义不符**：讲义说 "If the seeds do not match across the two lists, the evaluator raises a `PairingError`"，代码只在**交集为空**时报错，部分不匹配的 seed 被静默丢弃（实测 `{0,1,2}` vs `{1,2,5}` 正常返回，只用 seed 1、2）。被丢弃的往往是失败或被跳过的 run，存在幸存者偏差。
- ⚠️ 指标键不存在时 `r.metrics[metric]` 抛的是裸 `KeyError`（实测 `KeyError: 'acc'`），不是 `PairingError`。
- candidate 和 baseline 两段循环几乎完全重复，可以抽成一个函数（测验 Q10 给出了重构版本）。

### 3.5 改进量与 log 变换

```python
def _improvement(candidate_mean: float, baseline_mean: float, direction: str) -> float:
    denom = abs(baseline_mean) if baseline_mean != 0.0 else 1.0
    raw = (candidate_mean - baseline_mean) / denom
    if direction == LOWER:
        return -raw
    return raw
```

- 与讲义公式等价：lower-is-better 时 `(b − c)/|b| = −(c − b)/|b|`。
- 分母取绝对值：baseline 为负数时符号仍正确。
- baseline 恰为 0 时分母取 1，退化为**绝对差**——单位与其它情况不一致；baseline 很接近 0 时改进量会爆炸（实测 baseline 1e-9、candidate 0.1 时改进量为 1e8）。

```python
def _log_transform(values, scale):
    if scale != LOG:
        return list(values)
    out = []
    for v in values:
        if v <= 0.0:
            raise ValueError(f"log scale metric must be positive, got {v}")
        out.append(math.log(v))
    return out
```

- 非正数直接报错（测试 `test_log_requires_positive_metric`），而不是悄悄返回 NaN。
- ⚠️ **log 尺度改进量的定义与讲义不同**。在 `evaluate` 中，`_improvement` 被施加在**对数值的均值**上，即 `(mean log b − mean log c) / |mean log b|`——"对数值的相对变化"。讲义的说法是"困惑度 32 → 28 即 `log 28 − log 32 = −0.133`"，那是"对数差"。实测这对数字按代码算是 **0.0385**。更严重的是，代码的定义**依赖单位**：同一组耗时数据，秒制改进量 0.244、毫秒制 0.0286（测验 Q9）。用对数差作为改进量则与单位无关。

### 3.6 `Evaluator.evaluate`：主流程

```python
    def evaluate(self, hypothesis_id, metric_spec, candidates, baselines) -> Verdict:
        metric_spec.validate()
        bad = [r for r in [*candidates, *baselines] if r.terminal != "ok"]
        if bad:
            return self._failed_verdict(hypothesis_id, metric_spec, bad)
        cand_vals, base_vals = _pair_by_seed(candidates, baselines, metric_spec.name)
        cand_t = _log_transform(cand_vals, metric_spec.scale)
        base_t = _log_transform(base_vals, metric_spec.scale)
        mean_diff, p_value, n = paired_t_test(cand_t, base_t)
        cand_mean = float(np.mean(cand_vals))
        base_mean = float(np.mean(base_vals))
        cand_mean_t = float(np.mean(cand_t))
        base_mean_t = float(np.mean(base_t))
        improvement = _improvement(cand_mean_t, base_mean_t, metric_spec.direction)
        verdict, rationale = self._verdict(improvement, p_value, n)
        return Verdict(...)
```

- **先验证、再短路**：`[*candidates, *baselines]` 用解包把两个列表拼起来，只要有一个非 `ok` 就返回 `failed`。讲义判决表写的是 "any candidate result"，代码连 baseline 也检查——更严格，也更合理。
- **失败短路发生在配对之前**：失败 run 的指标可能缺失，先短路可以避免 `KeyError`。
- t 检验和改进量都用**变换后**的值（`cand_t`、`base_t`），而 `Verdict.candidate_mean / baseline_mean` 报告的是**原始值**的算术均值。所以 demo 中 `(30.775 − 26.425)/30.775 = 0.141` 与 `improvement = 0.0446` 对不上——阅读者需要知道这两组字段处在不同的尺度上。
- `mean_diff` 计算出来但没有放进 `Verdict`，其实它（以及置信区间）对下游写论文很有用。
- 整个方法只读 `self._cfg`，不修改任何状态——这就是讲义 "Keep every step pure" 的含义。

### 3.7 `_failed_verdict` 与 `_verdict`：判决表

```python
    def _failed_verdict(self, hypothesis_id, metric_spec, bad):
        terminals = sorted({r.terminal for r in bad})
        rationale = f"runs failed with terminals {terminals}"
        return Verdict(..., candidate_mean=0.0, baseline_mean=0.0, improvement=0.0,
                       p_value=None, ..., verdict="failed", rationale=rationale)
```

- `{r.terminal for r in bad}` 是**集合推导式**，去重后再 `sorted`，rationale 稳定可复现，例如 `runs failed with terminals ['oom']`。
- 均值、改进量填 0.0 只是占位，读 `failed` 判决时不应使用这些字段。

```python
    def _verdict(self, improvement, p_value, n):
        if abs(improvement) < self._cfg.improvement_threshold:
            return "noise", f"improvement {improvement:.4f} is below threshold ..."
        if p_value is None:
            return "noise", f"only {n} paired sample(s); cannot run significance test"
        if p_value > self._cfg.significance_threshold:
            return "noise", f"p value {p_value:.4f} exceeds significance threshold ..."
        if improvement > 0:
            return "improved", f"improvement {improvement:.4f} significant at p={p_value:.4f}"
        return "regressed", f"regression {improvement:.4f} significant at p={p_value:.4f}"
```

- 严格对应讲义的 5 步判决表（第 1 步 failed 在 `evaluate` 里处理）。
- 边界：`|improvement|` 恰等于 0.02 时**不算**噪声（`<` 而非 `<=`）；p 恰等于 0.05 时**算**显著（`>` 而非 `>=`）。
- 返回 `(verdict, rationale)` 元组，rationale 是一句人话，编排器可以直接记日志。

### 3.8 `_demo`

```python
    candidates = [result(s, 28.0 - 0.5 * s + (s % 3) * 0.2) for s in range(8)]
    baselines = [result(s, 32.0 - 0.4 * s + (s % 3) * 0.2) for s in range(8)]
    metric_spec = MetricSpec(name="perplexity", direction=LOWER, scale=LOG)
```

- 嵌套函数 `result(seed, perplexity)` 构造带 `seed / perplexity / final_loss` 的结果。
- 两组共享 `(s % 3) * 0.2` 这一项——模拟"同一 seed 下的共同噪声"，配对作差后被消掉（线性尺度下完全消掉，对数尺度下近似消掉）。
- candidate 为 `[28.0, 27.7, 27.4, 26.5, 26.2, 25.9, 25.0, 24.7]`，baseline 为 `[32.0, 31.8, 31.6, 30.8, 30.6, 30.4, 29.6, 29.4]`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 从零实现 t 分布 p 值 | 依赖少、每一步可读（讲义："There is no `scipy.stats`"） | 维护成本高、边界情况（不收敛）静默；生产直接用 `scipy.stats.ttest_rel` |
| 配对 t 检验 | 同 seed 作差消除共同噪声，灵敏度高 | 依赖正态假设，小样本对离群值敏感；可选 Wilcoxon / 置换检验 / bootstrap |
| 改进量门槛先于显著性门槛 | 只关心"值得在意"的变化 | 2% 是全局常数，不同指标的合理门槛不同；可放进 `MetricSpec` |
| log 尺度用对数值的相对变化 | 实现上复用 `_improvement` | 依赖单位、与讲义示例不一致；应改用对数差（测验 Q9） |
| 只取共同 seed | 宽容部分缺失 | 与讲义"不匹配即报错"不符，存在幸存者偏差；应默认严格 |
| 任一 run 非 ok 即 failed | 不从坏数据中得出结论 | 一个偶发失败就让整个假设作废；可允许重跑后再评 |
| 方差为 0 时 p = 0 | 避免除以 0 | 极少样本也会"极其显著"；需配合最少 seed 数 |
| 纯函数、无共享状态 | 可复现、易测试 | 无 |
| 结果替身 `ExperimentResultLike` | 与 52 节解耦，测试轻量 | 字段约定靠文档维护，最好用 `Protocol` 明确接口 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可写 `float \| None` |
| 模块级常量 | `HIGHER = "higher_is_better"` | 全大写表示常量（约定，不强制） |
| `@dataclass` 与默认值 | `direction: str = HIGHER` | 自动生成构造函数 |
| 自定义异常 | `class PairingError(ValueError):` | 继承内置异常，调用方可用 `except ValueError` 统一捕获 |
| `!r` 转换 | `f"unknown direction {self.direction!r}"` | 用 `repr()` 显示，字符串带引号 |
| f-string 格式符 | `{improvement:.4f}`、`{p_value:.4f}` | 保留 4 位小数 |
| `math.lgamma / log / exp / sqrt` | `math.lgamma(a + b)` | 标准库数学函数；`lgamma` 是 log Γ |
| 链式比较之外的区间检查 | `if x < 0.0 or x > 1.0:` | 也可写成 `not (0.0 <= x <= 1.0)` |
| `range(1, n + 1)` | `for m in range(1, max_iter + 1):` | 从 1 开始计数 |
| 增强赋值 | `h *= d * c` | 等价于 `h = h * (d * c)` |
| 元组返回与解包 | `mean_diff, p_value, n = paired_t_test(...)` | 一次返回多个值 |
| 条件表达式 | `(0.0 if mean_diff != 0.0 else 1.0)` | 一行 if/else |
| 嵌套条件表达式 | `None if self.p_value is None else round(self.p_value, 6)` | 处理可选值 |
| NumPy 数组运算 | `np.array(candidate) - np.array(baseline)` | 逐元素相减 |
| `ddof` 参数 | `diffs.var(ddof=1)` | 样本方差（除以 n−1） |
| 字典的 `get` | `r.metrics.get("seed")` | 键不存在返回 `None` |
| 集合交集 | `set(cand_map.keys()) & set(base_map.keys())` | 两边共有的 seed |
| 列表推导式 | `[cand_map[s] for s in shared]` | 按 seed 顺序取值 |
| 集合推导式 | `{r.terminal for r in bad}` | 自动去重 |
| 解包拼接列表 | `[*candidates, *baselines]` | 把两个列表展开合并 |
| `x or default` | `self._cfg = config or EvaluatorConfig()` | `config` 为 `None` 时用默认配置 |
| 嵌套函数 | `_demo` 里的 `def result(seed, perplexity)` | 只在局部使用的小工厂函数 |
| `json.dumps(..., indent=2)` | `_demo` 末尾 | 格式化输出 JSON |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`）：

```text
{
  "hypothesis_id": 1,
  "metric": "perplexity",
  "direction": "lower_is_better",
  "scale": "log",
  "candidate_mean": 26.425,        ← 原始困惑度的算术均值
  "baseline_mean": 30.775,
  "improvement": 0.044622,         ← 对数空间的相对变化，不是 (30.775-26.425)/30.775=0.141
  "p_value": 0.0,                  ← 真实值 1.24e-08，被 round(…, 6) 舍成 0
  "significance_threshold": 0.05,
  "improvement_threshold": 0.02,
  "verdict": "improved",
  "rationale": "improvement 0.0446 significant at p=0.0000"
}
```

逐项解读（数值均已用 Python 复核）：

- **改进量 0.044622**：`mean(log c) = 3.273376`，`mean(log b) = 3.426261`，`(3.426261 − 3.273376)/3.426261 = 0.044622`。因为 log 困惑度就是 loss，它的含义是"平均 loss 相对下降约 4.5%"。线性尺度下同一数据的改进量是 0.1413；若用单位无关的对数差，则是 0.1529（≈ 几何均值下降 14.2%）。
- **p 值**：对数差值为 `[−0.1335, −0.1380, −0.1426, −0.1504, −0.1552, −0.1602, −0.1689, −0.1742]`，均值 −0.1529、非常稳定，t = −29.78、df = 7，p = 1.24e-8。与 `scipy.stats.ttest_rel` 完全一致（误差约 1e-22），说明手写的不完全 Beta 函数实现正确。
- **verdict = improved**：改进量 0.0446 ≥ 0.02，p < 0.05，且改进量为正。
- **显示问题**：`p_value: 0.0` 和 `p=0.0000` 都是舍入造成的，并不代表"不可能是噪声"。

补充探针（自写脚本）结果：

| 场景 | 结果 |
|------|------|
| 测试 `test_log_transform_changes_threshold_outcome` 的数据 | linear：改进量 0.1236，log：0.0380，两者都 `improved`——测试名说"改变了门槛结论"，实际断言的只是改进量不同 |
| seed `{0,1,2}` vs `{1,2,5}` | 不报错，只用 seed 1、2，`candidate_mean=0.915` |
| baseline 中有一个 `oom` | `failed`，`runs failed with terminals ['oom']` |
| 3 个 seed：`[0.90,0.95,0.80]` vs `[0.70,0.72,0.75]` | 改进量 0.2212，p = 0.1028 → `noise` |
| 只取前 2 个 seed | 改进量 0.3028，p = 0.0443 → `improved` |
| 某个结果缺少指标键 | 抛 `KeyError: 'acc'` |

---

## 7. 动手改一改

1. **（入门）** 把 `EvaluatorConfig(improvement_threshold=0.05)` 传给 demo，观察 verdict 从 `improved` 变成 `noise`；再试试 `scale=LINEAR`，看同一阈值下结论如何。
2. **（入门）** 修改 `Verdict.to_dict`：p 值小于 1e-4 时用 `f"{p:.2e}"` 格式输出，避免出现 `0.0`；rationale 同理。
3. **（进阶）** 实现测验 Q9 的修复：log 尺度改进量改为对数差，并写测试断言"秒与毫秒单位下改进量相同"。
4. **（进阶）** 实现测验 Q10 的严格配对，再把 `mean_diff` 与 95% 置信区间加入 `Verdict`（复用测验 Q12 的 `t_critical` 二分法）。
5. **（进阶）** 增加 `test="wilcoxon"` 选项：实现 Wilcoxon 符号秩检验（小样本可直接枚举全部 2ⁿ 种符号组合求精确 p 值），对比它与 t 检验在含一个离群 seed 时的表现。
6. **（挑战）** 写一个 `evaluate_many(hypotheses)`，对一批假设的 p 值做 Benjamini–Hochberg 校正，只在校正后仍显著时判 `improved`；用 100 个"无效假设"（candidate 与 baseline 同分布、随机噪声）模拟，比较校正前后误报的数量。

---

## 8. 常见坑

- **忘记 `ddof=1`**：NumPy 的 `var` 默认除以 n，会低估方差、夸大显著性。
- **只看 p 值**：p 值小不等于效应大；本节先卡 2% 改进量门槛正是为此。
- **混淆字段的尺度**：`candidate_mean / baseline_mean` 是原始值，`improvement` 在 log 尺度下是对数空间的量，两者不能直接互推。
- **log 尺度的单位陷阱**：代码的改进量随单位变化（秒 vs 毫秒差 8.5 倍）；指标值接近 1（log 接近 0）时改进量会被放大。
- **以为 seed 不匹配会报错**：只有完全没有交集才会报错，部分缺失会被静默丢弃。
- **只有两三个 seed 就下结论**：df 很小时临界值很大，偶然接近的差值、或方差恰为 0 的情况会产生误导性的"显著"。
- **对失败 run 补 0 再比较**：本节的做法是直接判 `failed`，不要试图"修补"失败数据。
- **把 `PairingError` 当成唯一异常**：缺指标键时抛的是 `KeyError`，非正数做 log 时抛 `ValueError`，调用方需要都处理。

---

## 9. 测试在验证什么

测试文件：`code/tests/test_evaluator.py`（`unittest` 风格）。辅助函数 `res(seed, metric_name, value, terminal="ok")` 构造只含 `seed` 和一个指标的 `ExperimentResultLike`。

| 测试类 / 方法 | 验证的性质 |
|--------------|-----------|
| `TestIncompleteBeta.test_symmetry` | `I_x(a,b) + I_{1−x}(b,a) = 1`（a=2.5, b=3.5, x=0.4），检验对称性切换逻辑 |
| `TestIncompleteBeta.test_endpoints` | `x=0` 返回 0、`x=1` 返回 1 |
| `TestTwoSidedPValue.test_t_zero_is_one` | t = 0 时 p = 1 |
| `TestTwoSidedPValue.test_p_decreases_with_t` | t 越大 p 越小（单调性） |
| `TestTwoSidedPValue.test_known_reference` | t = 2.228、df = 10 时 p ≈ 0.05（与 t 表对照，精确到 2 位） |
| `TestTwoSidedPValue.test_t_large_p_small` | t = 10、df = 5 时 p < 0.01 |
| `TestPairedTTest.test_clear_improvement` | 差值恒为 −1 时均值差 −1、n = 5、p < 0.05（走的是方差为 0 分支，p = 0） |
| `TestPairedTTest.test_zero_variance` | 方差为 0 且均值非零时 p = 0 |
| `TestPairedTTest.test_low_n_returns_none` | n = 1 和 n = 0 时 p 为 `None` |
| `TestPairedTTest.test_length_mismatch_raises` | 长度不一致抛 `PairingError` |
| `TestImprovedRegressedNoise.test_improved_higher_is_better` | 准确率 0.85 vs 0.70：`improved`、改进量 > 0.1、p < 0.05 |
| `TestImprovedRegressedNoise.test_regressed_lower_is_better` | loss 0.7 vs 0.5：`regressed`、改进量 < 0 |
| `TestImprovedRegressedNoise.test_small_change_is_noise` | 差 0.001：改进量低于门槛 → `noise`（即使 p = 0） |
| `TestImprovedRegressedNoise.test_one_seed_is_noise` | 只有 1 个 seed：`noise` 且 p 为 `None` |
| `TestFailedTerminal.test_any_crash_returns_failed` | 一个 candidate `timeout` → `failed`，rationale 含 `timeout` |
| `TestLogScale.test_log_transform_changes_threshold_outcome` | 线性与 log 尺度都判 `improved`，但改进量不同（0.1236 vs 0.0380） |
| `TestLogScale.test_log_requires_positive_metric` | log 尺度遇到负数抛 `ValueError` |
| `TestPairing.test_no_shared_seeds_raises` | seed 完全不相交抛 `PairingError` |

运行方式与实际结果：

```text
$ cd code && python3 -m pytest -q
..................                                                       [100%]
18 passed in 0.08s
```

值得注意的几点：

- `test_clear_improvement` 名义上测"明显改进"，但差值全部相等，实际走的是方差为 0 的特判分支，并没有经过不完全 Beta 函数；`test_known_reference` 才真正检验了 p 值计算。
- `test_log_transform_changes_threshold_outcome` 的名字暗示"log 变换改变了门槛结论"，但两种尺度的结论相同，断言的只是改进量数值不同。
- 讲义说测试覆盖 "the pairing error"，实际只覆盖了"完全无交集"一种情况；部分不匹配、重复 seed、缺 seed、缺指标键都没有测试。
- 没有测试 baseline 失败的情形（代码会判 `failed`，与讲义"只看 candidate"的描述不同）。
