# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 74 节 排行榜汇总 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（测试：`python3 -m pytest -q`） ｜ **依赖**：标准库（`json`、`math`、`collections`、`dataclasses`）+ 第三方 `numpy`

---

## 1. 这份代码在考察什么

前几课产出的是"某模型在某任务上得了多少分"。这份代码回答下一个问题：**多个模型、多个异构任务，怎样排出一张站得住脚的排行榜？**

1. **数据契约**：每个 `(model, task)` 一条 `EvalRun`，分数必须已经在 `[0, 1]`，重复即报错。
2. **两种排名口径**：平均分（标题数字）与 win-rate（每任务比输赢），讲义要求两者都报告。
3. **不确定性**：对任务做 bootstrap 重采样，给每个模型的均值加 95% 置信区间；对任意两模型做**配对** bootstrap，判断差异是否显著。
4. **分类别视图**：每个模型在 arithmetic / mcq / code_exec / summary 上的均值。
5. **输出**：JSON 与 Markdown 表，第 75 课会把表贴进 CI 评论。

讲义开篇："Statistical significance on a thousand-prediction leaderboard is the part everyone skips. This lesson does not skip it."

> 一句话：**排行榜上的每个数字都应该带着"它有多可信"一起出现**——同时要看清"均值在不同任务集上不可比""平局怎么算""多重比较"这些代码没有处理的坑。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `EvalRun` | dataclass | 一条 `(model, task)` 记录：指标名、分数、类别、权重（权重未被使用） | 输入形状 |
| `LeaderboardRow` | dataclass | 一行排行榜：均值、CI 上下界、win-rate、完成任务数、类别均值 | 输出形状 |
| `PairwiseDiff` | dataclass | 一对模型的平均差、CI、是否显著 | 两两比较 |
| `_validate_runs` | 私有函数 | 分数在 `[0, 1]`、`(model, task)` 不重复 | 契约检查 |
| `_by_model` / `_by_task` | 私有函数 | 按模型 / 按任务分组 | 数据透视 |
| `bootstrap_mean_ci` | 函数 | 对分数有放回重采样，percentile 区间 | bootstrap CI |
| `bootstrap_pairwise_diff` | 函数 | 对逐任务差值重采样 | 配对 bootstrap |
| `_win_rate` | 私有函数 | 每任务最高分者获胜（平局都算赢） | win-rate |
| `_category_means` | 私有函数 | 按类别求均值 | 分类别视图 |
| `aggregate` | 函数 | 组装 `LeaderboardRow` 列表并按均值降序 | 排行榜 |
| `pairwise_diffs` | 函数 | 所有模型对的配对比较 | 显著性 |
| `render_markdown` / `render_json` | 函数 | 输出表格与 JSON | 报告 |
| `_synthetic_runs` / `demo` | 函数 | 3 模型 × 12 任务的合成数据与演示 | 自检 |

数据流：`list[EvalRun]` → `_validate_runs` → `_by_model` / `_by_task` → 每个模型：均值 + `bootstrap_mean_ci` + `_win_rate` + `_category_means` → `LeaderboardRow` → 排序 → `render_markdown` / `render_json`；另一路：按任务透视 → 每对模型取共同任务 → `bootstrap_pairwise_diff` → `PairwiseDiff`。

---

## 3. 逐段精讲

### 3.1 三个 dataclass

```python
@dataclass
class EvalRun:
    model_id: str
    task_id: str
    metric_name: str
    score: float
    category: str = "general"
    weight: float = 1.0
```

- 讲义中的 `EvalRun` 只有前五个字段，代码多了 `weight` 并给 `category` 默认值 `"general"`。讲义："we leave that hook open through the `weight` field but ignore it in the aggregator."——整个文件没有任何地方读取 `weight`。
- `metric_name` 也只是被保存，不参与任何计算；聚合器"不关心分数是怎么来的"。
- `LeaderboardRow.categories` 用 `field(default_factory=dict)`；`to_dict` 中 `dict(self.categories)` 返回浅拷贝。
- `PairwiseDiff.significant` 是布尔值，直接给 Markdown/JSON 使用。

### 3.2 校验与分组

```python
def _validate_runs(runs: Sequence[EvalRun]) -> None:
    seen: set[tuple[str, str]] = set()
    for r in runs:
        if not (0.0 <= r.score <= 1.0):
            raise ValueError(f"score for {r.model_id}/{r.task_id} not in [0,1]: {r.score}")
        key = (r.model_id, r.task_id)
        if key in seen:
            raise ValueError(f"duplicate run for {r.model_id}/{r.task_id}")
        seen.add(key)
```

- **链式比较** `0.0 <= r.score <= 1.0` 等价于 `0.0 <= r.score and r.score <= 1.0`。`NaN` 与任何数比较都是 `False`，所以 NaN 也会被拒（实测）。
- 讲义："If one task scores in `[0, 1]` and another in `[0, 100]`, the second silently dominates the mean." 实测 `EvalRun("m", "t", "bleu", 28.3)` 抛 `ValueError`。
- 重复的 `(model, task)` 直接报错，而不是"后者覆盖前者"——防止 runner 重跑时悄悄混入两份结果。
- **注意**：学习目标说 "Normalise heterogeneous scores"，但代码只做**范围校验**，没有任何规范化。`[0, 1]` 内不同指标的分布差异（exact match 是 0/1，ROUGE-L 常集中在 0.3–0.5）依然会影响均值（测验 Q12）。

```python
def _by_model(runs) -> dict[str, list[EvalRun]]:
    out: dict[str, list[EvalRun]] = defaultdict(list)
    for r in runs:
        out[r.model_id].append(r)
    return dict(out)
```

- `defaultdict(list)` 访问不存在的键时自动创建空列表；最后 `dict(out)` 转回普通字典，避免调用方误访问时悄悄插入新键。
- 字典保持插入顺序，所以模型的顺序就是它们在 `runs` 中首次出现的顺序。

### 3.3 `bootstrap_mean_ci`：percentile 区间

```python
def bootstrap_mean_ci(scores, b=1000, alpha=0.05, seed=0) -> tuple[float, float]:
    if len(scores) == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    arr = np.asarray(scores, dtype=np.float64)
    n = arr.size
    means = np.empty(b, dtype=np.float64)
    for i in range(b):
        idx = rng.integers(0, n, size=n)
        means[i] = float(arr[idx].mean())
    lo = float(np.percentile(means, 100.0 * (alpha / 2.0)))
    hi = float(np.percentile(means, 100.0 * (1.0 - alpha / 2.0)))
    return (lo, hi)
```

- 对应讲义的流程图：循环 B 次 → 有放回抽 N 个任务 → 求均值 → 排序取 `α/2` 与 `1 − α/2` 分位数。
- `rng.integers(0, n, size=n)` 生成 n 个 `[0, n)` 的随机下标，`arr[idx]` 用**整数数组索引**一次取出重采样后的样本——同一个任务可能被抽中多次，有的一次也没抽到。
- `np.percentile(means, 2.5)` 默认用线性插值。
- 循环可以完全向量化：`idx = rng.integers(0, n, size=(b, n)); means = arr[idx].mean(axis=1)`，速度快很多。
- 区间宽度直观感受（实测）：10 个任务、5 个对 → `(0.2, 0.8)`；100 个任务、50 个对 → `(0.4, 0.6)`。**任务数少时 CI 非常宽**。
- 常数分数得到零宽区间（测试 `test_constant_scores_zero_width_ci`）；空输入返回 `(0.0, 0.0)`，与"均值为 0 且非常确定"无法区分，调用方需注意。
- **注意**：`aggregate` 对每个模型都用**同一个** `seed`，任务数相同时各模型使用完全相同的重采样下标。这不影响每个模型自身 CI 的正确性，但各模型的 CI 误差是相关的。

### 3.4 `bootstrap_pairwise_diff`：配对差

```python
    a = np.asarray(paired_a, dtype=np.float64)
    b_arr = np.asarray(paired_b, dtype=np.float64)
    diffs = a - b_arr
    diff_mean = float(diffs.mean())
    ...
    for i in range(b):
        idx = rng.integers(0, n, size=n)
        boots[i] = float(diffs[idx].mean())
```

- **先做差、再重采样**：同一下标 i 的两个分数来自同一个任务，难度这一共同成分在差值中抵消，方差更小、检验更敏感（测验 Q6、Q17）。
- 参数名 `b` 被用作重采样次数，所以第二个数组只好叫 `b_arr`——`b` 同时作为"模型 B"和"bootstrap 次数"的名字，容易混淆。
- 返回 `(平均差, 下界, 上界)`；`paired_a`、`paired_b` 长度不同直接抛错。

### 3.5 `_win_rate` 与 `_category_means`

```python
def _win_rate(model_id, runs_by_task) -> tuple[float, int]:
    wins = 0
    total = 0
    for task_id, runs in runs_by_task.items():
        scores = {r.model_id: r.score for r in runs}
        if model_id not in scores:
            continue
        total += 1
        best = max(scores.values())
        if math.isclose(scores[model_id], best, abs_tol=1e-12):
            wins += 1
    if total == 0:
        return (0.0, 0)
    return (wins / total, total)
```

- 只统计该模型**有分数**的任务；分母是这些任务的数量。
- `math.isclose(..., abs_tol=1e-12)`：浮点数比较用容差而不是 `==`，避免 0.1 + 0.2 这类误差让本该并列的分数"不相等"。
- **注意**：**平局都算赢**：讲义写 "ties split"，代码中 k 个并列第一的模型各得 1 胜；测试 `test_ties_split_to_winner` 断言两个并列模型都是 1.0，名字与断言也不一致。极端情况下（所有模型在所有任务上都是 0 分）每个模型 win-rate 都是 1.0。平分写法见测验 Q9。
- **注意**：讲义里的示例函数签名是 `win_rate(model_id, runs_by_task, all_models)`，代码没有 `all_models` 参数——任何出现在 `runs` 里的模型都参与比较。
- 返回值是元组 `(win_rate, total)`，`total` 被 `aggregate` 用作 `tasks_completed`。

```python
def _category_means(runs) -> dict[str, float]:
    by_cat: dict[str, list[float]] = defaultdict(list)
    for r in runs:
        by_cat[r.category].append(r.score)
    return {cat: float(np.mean(scores)) for cat, scores in by_cat.items()}
```

- 字典推导式一行生成 `{类别: 均值}`。讲义："It lets the runner spot whether a model is good overall but weak in code, which is information the headline mean hides."

### 3.6 `aggregate`：组装排行榜

```python
def aggregate(runs, b=500, alpha=0.05, seed=0) -> list[LeaderboardRow]:
    if not runs:
        return []
    _validate_runs(runs)
    by_model = _by_model(runs)
    by_task = _by_task(runs)
    rows = []
    for model_id, model_runs in by_model.items():
        scores = [r.score for r in model_runs]
        mean_score = float(np.mean(scores))
        lo, hi = bootstrap_mean_ci(scores, b=b, alpha=alpha, seed=seed)
        wr, completed = _win_rate(model_id, by_task)
        cats = _category_means(model_runs)
        rows.append(LeaderboardRow(..., tasks_completed=completed if completed else len(scores), ...))
    rows.sort(key=lambda r: r.mean_score, reverse=True)
    return rows
```

- 每个模型在**自己的任务集合**上求均值和 CI。**注意**：当不同模型覆盖的任务不同时，均值不可比：实测 `small` 只做了简单题（0.95），排在做了难题的 `big`（0.6）前面（测验 Q10）。表格只显示各自的 `Tasks`，读者看不到总任务数。
- `completed if completed else len(scores)`：只要模型有任何 run，`completed` 就等于其任务数，`else` 分支实际不会走到。
- `rows.sort(key=lambda r: r.mean_score, reverse=True)`：原地排序；Python 的排序是**稳定的**，均值相同的模型保持原来的相对顺序（即首次出现顺序），没有任何"平局打破"规则。
- 讲义说 public 聚合器默认 `b=500`、底层函数默认 `B=1000`，与代码一致；demo 用的是 `b=300`。

### 3.7 `pairwise_diffs`：所有模型对

```python
    model_ids = sorted(by_model.keys())
    common_task_scores: dict[str, dict[str, float]] = defaultdict(dict)
    for r in runs:
        common_task_scores[r.task_id][r.model_id] = r.score
    for i in range(len(model_ids)):
        for j in range(i + 1, len(model_ids)):
            a, b_id = model_ids[i], model_ids[j]
            paired_a, paired_b = [], []
            for task_id, ms in common_task_scores.items():
                if a in ms and b_id in ms:
                    paired_a.append(ms[a])
                    paired_b.append(ms[b_id])
            if not paired_a:
                continue
            diff_mean, lo, hi = bootstrap_pairwise_diff(paired_a, paired_b, b=b, alpha=alpha, seed=seed + i + j)
            significant = lo > 0.0 or hi < 0.0
```

- 先建"任务 → {模型: 分数}"的嵌套字典，再对每对模型只取**共同任务**——这一点比 `aggregate` 的均值更公平。
- `sorted(...)` 让模型对的顺序确定（按名字字母序），`a − b` 的方向也固定：`model_a vs model_b` 的正差值表示 a 更好。
- 双重循环 `j in range(i + 1, ...)` 只遍历上三角，M 个模型得到 `M(M−1)/2` 对。
- **注意**：**种子碰撞**：`seed + i + j` 在 4 个模型时让 `(0,3)` 与 `(1,2)` 都得到种子 `seed + 3`，任务数相同时两对使用完全相同的重采样下标。修正用 `np.random.default_rng([seed, i, j])` 或 `SeedSequence.spawn`。
- **注意**：**没有多重比较校正**：每对都用同一个 α。6 个同分布模型（15 对）的 40 次模拟中，50% 的模拟至少出现一对"显著"（测验 Q11）。
- 没有共同任务的模型对被跳过，而不是报告"无法比较"。

### 3.8 输出

```python
def render_markdown(rows) -> str:
    header = "| Rank | Model | Mean | 95% CI | Win rate | Tasks |"
    sep = "|------|-------|------|--------|----------|-------|"
    out_lines = [header, sep]
    for i, row in enumerate(rows, start=1):
        model_label = row.model_id[:20]
        ci = f"{row.mean_ci_lo:.2f}-{row.mean_ci_hi:.2f}"
        out_lines.append(f"| {i} | {model_label} | {row.mean_score:.2f} | {ci} | {row.win_rate:.2f} | {row.tasks_completed} |")
    return "\n".join(out_lines)
```

- 名次就是传入顺序（`aggregate` 已经排好），平均分相同的模型也会得到不同名次。
- `row.model_id[:20]`：切片截断到 20 个字符；两个前 20 字符相同的模型名会显示成一样。
- 表头写死 "95% CI"，即使调用 `aggregate` 时传了别的 `alpha`。
- **注意**：模型名中的 `|` 不会被转义，实测 `"a|b"` 会让该行多出一列、表格错位。
- `render_json` 用 `json.dumps(..., indent=2)`，`LeaderboardRow.to_dict()` 中全是 Python 原生类型（`float(...)` 已转换），可以直接序列化。

### 3.9 合成数据与 demo

```python
    means = {"model_a": 0.78, "model_b": 0.72, "model_c": 0.55}
    for cat in categories:
        for t in range(3):
            task_id = f"{cat}_{t:02d}"
            for m in models:
                base = means[m]
                if cat == "code_exec":
                    base -= 0.1
                if cat == "summary" and m == "model_c":
                    base += 0.15
                noise = rng.uniform(-0.1, 0.1)
                score = float(np.clip(base + noise, 0.0, 1.0))
```

- 4 类 × 3 任务 = 12 个任务，3 个模型共 36 条 run。所有模型在 code_exec 上统一减 0.1；`model_c` 在 summary 上加 0.15——专门用来演示"分类别均值能暴露的信息"。
- 注意每个模型在每个任务上的噪声**独立**，没有"任务难度"这一共同成分，所以配对 bootstrap 的优势在这组数据上体现得不明显；真实数据中任务难度通常是最大的方差来源。
- `f"{t:02d}"`：两位数补零，任务名形如 `code_exec_00`。
- demo 的退出码只检查"第一名的均值不低于最后一名"——由于已经排序，这个条件恒成立，只要 `rows` 非空就返回 0。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 分数必须已在 `[0, 1]`，否则拒绝 | 修复应在上游指标层 | 范围统一 ≠ 分布可比；生产会按类别先平均或做规范化 |
| 重复 `(model, task)` 报错 | 防止重跑结果悄悄混入 | 需要多次重复运行时要另设字段（如 `seed`） |
| 均值在各自任务集上计算 | 简单 | 覆盖不同时不可比；应只用共同任务或缺失计 0，并显示覆盖率 |
| 同时报告均值与 win-rate | 两种口径可能相反 | win-rate 平局都算赢，与讲义"平分"不符 |
| percentile bootstrap、纯 NumPy | 无需 scipy，易懂 | 小样本覆盖率不足；任务相关时低估方差（应分层 bootstrap） |
| 配对 bootstrap 只用共同任务 | 消除任务难度方差，比较公平 | 没有多重比较校正；种子 `seed+i+j` 会碰撞 |
| 所有模型用同一 seed 做均值 CI | 结果可复现 | 各模型 CI 误差相关 |
| `weight` 字段保留但不用 | 为后续加权留接口 | 读者可能误以为权重已生效 |
| Markdown 表固定 "95% CI"、截断 20 字符 | CI 评论中简洁 | `alpha` 改了表头不变；`\|` 未转义 |
| 默认 `b=500`（聚合）/ `1000`（底层） | demo 和测试快 | 正式报告应取上万次，尤其做多重比较校正时 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 默认值 | `category: str = "general"`、`weight: float = 1.0` | 有默认值的字段必须放在无默认值字段之后 |
| `field(default_factory=dict)` | `categories: dict[str, float] = field(...)` | 可变默认值 |
| 链式比较 | `0.0 <= r.score <= 1.0` | 等价于两个比较用 `and` 连接 |
| 元组作集合元素 | `seen.add((r.model_id, r.task_id))` | 复合键 |
| `collections.defaultdict` | `defaultdict(list)`、`defaultdict(dict)` | 自动创建缺失键的默认值 |
| 嵌套字典赋值 | `common_task_scores[r.task_id][r.model_id] = r.score` | 外层 `defaultdict(dict)` 让两级赋值一步完成 |
| 字典推导式 | `{r.model_id: r.score for r in runs}` | 一行构建字典 |
| 列表推导式 | `[r.score for r in model_runs]` | 一行构建列表 |
| `np.random.default_rng(seed)` | `rng.integers(0, n, size=n)` | 新式随机数生成器；生成随机整数下标 |
| 整数数组索引 | `arr[idx].mean()` | 按下标数组取元素（可重复） |
| `np.empty` | `np.empty(b, dtype=np.float64)` | 分配未初始化的数组，随后逐个填充 |
| `np.percentile` | `np.percentile(means, 2.5)` | 分位数（参数是百分数） |
| `math.isclose` | `math.isclose(a, b, abs_tol=1e-12)` | 浮点数容差比较 |
| 上三角双重循环 | `for i in range(n): for j in range(i + 1, n):` | 枚举所有无序对 |
| `list.sort(key=..., reverse=True)` | `rows.sort(key=lambda r: r.mean_score, reverse=True)` | 原地稳定排序；`lambda` 匿名函数取排序键 |
| `sorted(dict.keys())` | `model_ids = sorted(by_model.keys())` | 返回新的有序列表 |
| `enumerate(..., start=1)` | `for i, row in enumerate(rows, start=1)` | 名次从 1 开始 |
| 字符串切片 | `row.model_id[:20]` | 截断 |
| f-string 格式符 | `{row.mean_score:.2f}`、`{d.diff_mean:+.3f}`、`{t:02d}` | 两位小数、强制显示正负号、补零 |
| `json.dumps(..., indent=2)` | `render_json` | 带缩进的 JSON |
| `typing.Sequence` | `runs: Sequence[EvalRun]` | 接受任意序列 |
| 函数参数默认值 | `def aggregate(runs, b=500, alpha=0.05, seed=0)` | 可选参数 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + NumPy）：

```text
$ python3 main.py
| Rank | Model | Mean | 95% CI | Win rate | Tasks |
|------|-------|------|--------|----------|-------|
| 1 | model_a | 0.77 | 0.73-0.80 | 0.75 | 12 |
| 2 | model_b | 0.70 | 0.66-0.74 | 0.17 | 12 |
| 3 | model_c | 0.57 | 0.53-0.62 | 0.08 | 12 |

Pairwise comparisons (paired bootstrap):
  model_a vs model_b: diff=+0.064 ci=[+0.026,+0.102] significant=yes
  model_a vs model_c: diff=+0.192 ci=[+0.132,+0.249] significant=yes
  model_b vs model_c: diff=+0.128 ci=[+0.058,+0.184] significant=yes
$ echo $?
0
```

逐项解读：

- **均值**：model_a 0.766、model_b 0.703、model_c 0.574，与设定的 0.78 / 0.72 / 0.55 接近（code_exec 统一减 0.1、model_c 的 summary 加 0.15、加上噪声）。
- **95% CI**：每个模型约 ±0.035–0.045。只有 12 个任务，且噪声幅度 ±0.1，所以区间不算窄。
- **win-rate**：model_a 赢了 12 个任务中的 9 个（0.75），model_b 2 个（0.17），model_c 1 个（0.08）。三者之和为 1，说明没有平局。逐任务核对：model_c 唯一的胜场是 `summary_00`（0.737 > 0.689 > 0.651），正是 summary 上 +0.15 的设定在起作用；model_b 赢了 `mcq_02`（0.731 vs 0.725，只差 0.006）和 `code_exec_01`。
- **分类别均值**（JSON 中可见，表格没有显示）：model_a `{arithmetic: 0.829, mcq: 0.768, code_exec: 0.711, summary: 0.757}`；model_c `{arithmetic: 0.581, mcq: 0.546, code_exec: 0.491, summary: 0.68}`——summary 上 model_c 与其他模型差距明显缩小。
- **配对比较**：三对的 CI 都不含 0。注意 model_a 与 model_b 的**均值 CI 重叠**（0.73–0.80 与 0.66–0.74），而配对差 CI [+0.026, +0.102] 不含 0——这并不矛盾，见测验 Q17。
- 退出码 0：`rows` 非空且第一名均值不低于最后一名（排序后恒成立）。

---

## 7. 动手改一改

1. **平局平分**：把 `_win_rate` 改成并列第一的 k 个模型各得 `1/k` 胜（参考测验 Q9），同步修改并重命名 `test_ties_split_to_winner`。
2. **公平均值**：给 `aggregate` 增加 `mode` 参数：`"own"`（当前行为）、`"common"`（只用所有模型共同的任务）、`"missing_zero"`（缺失计 0），并在 `LeaderboardRow` 中加入 `coverage` 字段、在 Markdown 表中显示 `Tasks` 为 `完成数/总数`。
3. **多重比较与种子**：`pairwise_diffs` 增加 `correction="bonferroni"` 选项；把 `seed + i + j` 改为 `np.random.default_rng([seed, i, j])`；用 6 个同分布模型做模拟，比较校正前后"至少一对误判"的比例。
4. **向量化 bootstrap**：用 `rng.integers(0, n, size=(b, n))` 一次生成全部下标，`arr[idx].mean(axis=1)` 求均值，比较 B = 10000 时的速度。
5. **使用 `weight` 与分层 bootstrap**：实现加权均值（`np.average(scores, weights=w)`）；再实现按 `category` 分层重采样（每个类别内部各自有放回抽样），比较 CI 宽度。
6. **进阶：Bradley–Terry / Elo**：把每个任务上的两两胜负当作"比赛"，拟合 Bradley–Terry 强度参数，与均值、win-rate 排名对比。

---

## 8. 常见坑

- **在不同任务集上比较均值**：只做了简单任务的模型会排在前面。
- **以为 `[0, 1]` 校验等于规范化**：不同指标在 `[0, 1]` 内的分布差异依然影响均值。
- **平局处理与讲义不一致**：代码中并列者都算赢，win-rate 之和可能大于 1。
- **用均值 CI 是否重叠判断显著性**：应当看配对差的 CI。
- **任务数太少还谈"显著"**：10 个任务、50% 准确率的 CI 是 0.2–0.8。
- **多对比较不校正**：模型越多，越容易"发现"假的显著差异。
- **B 太小**：尤其在做多重比较校正、需要极端分位数时。
- **忽略任务之间的相关性**：同一家族的任务不是独立样本，独立重采样会让 CI 过窄。
- **以为 `weight` 生效了**：它被完全忽略。
- **模型名含 `|` 或前 20 个字符相同**：Markdown 表错位或无法区分。
- **改了 `alpha` 却看表头**：表头永远写 "95% CI"。

---

## 9. 测试在验证什么

测试文件：`tests/test_leaderboard.py`（`unittest` 风格）。辅助函数 `make_runs(spec)` 把 `{model: [(task, score), ...]}` 展开成 `EvalRun` 列表，所有 run 的类别都是 `"general"`。

运行方式：

```bash
cd code
python3 -m pytest -q            # 或：python3 -m unittest discover tests
```

实际运行结果：`18 passed in 0.16s`。

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `TestAggregate` | `test_empty_input` | 空输入返回空列表 |
| | `test_validate_score_range` | 分数 1.5 抛 `ValueError` |
| | `test_basic_two_model` | 好模型排第一，均值更高 |
| | `test_sorted_by_mean_descending` | 三个模型按均值降序：b、c、a |
| | `test_category_means_returned` | 两个类别各自的均值正确（1.0 与 0.0） |
| | `test_ci_is_within_bounds` | 常数分数 0.5 → CI 上下界都是 0.5 |
| `TestBootstrap` | `test_constant_scores_zero_width_ci` | 常数分数得到零宽区间 |
| | `test_ci_contains_mean` | 区间包含样本均值 |
| | `test_pairwise_diff_zero_for_equal` | 相同分数 → 平均差与区间都为 0 |
| | `test_pairwise_diff_significant` | 0.9 vs 0.1（30 个任务）→ 下界 > 0、平均差 0.8 |
| | `test_pairwise_diff_misaligned` | 长度不一致抛错 |
| | `test_empty_scores_returns_zero_width` | 空输入返回 `(0.0, 0.0)` |
| `TestWinRate` | `test_winner_takes_all` | 每个任务都更高的模型 win-rate = 1.0 |
| | `test_ties_split_to_winner` | 两个并列模型 win-rate **都是 1.0**——名字说"split"，断言的是"都算赢"，与讲义的"ties split"矛盾 |
| `TestPairwiseDiffs` | `test_returns_one_per_pair` | 3 个模型得到 3 对 |
| `TestRender` | `test_markdown_header_present` | 表头与第一行格式 |
| | `test_json_round_trip` | `render_json` 输出可被 `json.loads` 解析 |
| | `test_long_model_id_truncated` | 30 个字符的模型名被截断（不含 25 个连续 x） |

讲义说测试覆盖 "the win-rate edge cases"，实际只有两个 win-rate 测试。没有覆盖的地方：

- 重复 `(model, task)` 报错；
- NaN 分数；
- 模型任务覆盖不一致时的均值与 win-rate；
- `pairwise_diffs` 中没有共同任务的模型对被跳过；
- `significant` 字段在实际数据上的取值；
- `weight` 字段被忽略；
- 模型名包含 `|`。
