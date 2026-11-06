# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 73 节 Perplexity 与 Calibration（困惑度与校准） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（测试：`python3 -m pytest -q`） ｜ **依赖**：标准库（`math`、`dataclasses`、`typing`）+ 第三方 `numpy`

---

## 1. 这份代码在考察什么

准确率只回答"答对了多少"。这份代码补上可信评估的另外两半：

1. **困惑度**：模型认为一段留出文本有多"合理"。输入是适配器给出的负对数似然（NLL），代码负责**正确地聚合**（按 token 加权）并守住符号契约。
2. **校准（calibration）**：模型说"90% 确定"时，是否真的有 90% 答对。实现了三件工具：
   - **ECE**：分 bin 后置信度与准确率的加权平均差；
   - **Brier 分数**及其 Murphy 分解（reliability / resolution / uncertainty）；
   - **可靠性图数据**：每个 bin 的平均置信度、准确率、计数。
3. **报告对象**：`CalibrationReport` 与 `PerplexityResult` 两个 dataclass，第 75 课的 runner 直接调用它们把数字写进模型报告。

讲义强调：校准是**模型级报告**，不是逐任务指标；runner 把整个评估中的 `(confidence, correct)` 对攒起来，最后一次性计算。

> 一句话：**把"模型有多自信"和"模型有多准"放到同一张表上，并让这三个数字（perplexity、ECE、Brier）可复现、不会被边界情况弄崩**——同时看清 ECE 的盲区。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PerplexityResult` | dataclass + 类方法 | `from_token_nll` 聚合 NLL，返回困惑度、平均 NLL、总 token 数 | 困惑度 |
| `perplexity` | 函数 | 只取困惑度标量的便捷包装 | 困惑度 |
| `_validate_probs` | 私有函数 | 形状一致、1 维、置信度在 [0,1]、correct 只含 0/1 | 输入契约 |
| `_bin_indices` | 私有函数 | 等宽分 bin，返回每个样本的 bin 下标 | 分 bin |
| `expected_calibration_error` | 函数 | 返回 `(ECE, populated_bins)` | ECE |
| `brier_score` | 函数 | `mean((p − y)²)` | Brier |
| `brier_decomposition` | 函数 | 分 bin 的 reliability / resolution / uncertainty | Murphy 分解 |
| `reliability_diagram` | 函数 | 返回 `(bin_conf, bin_acc, bin_count)` 三个数组 | 可靠性图 |
| `CalibrationReport` | dataclass + 类方法 | 打包 ECE、Brier、populated_bins、可靠性数据、样本数 | 模型级报告 |
| `synthetic_calibrated / overconfident / underconfident` | 函数 | 构造已知校准性质的合成数据 | 测试数据 |
| `synthetic_token_nll` | 函数 | 12 个序列、每 token NLL 在 [1.5, 3.0) | 合成 NLL |
| `demo` | 函数 | 三种合成预测器 + 困惑度 + 可靠性图 | 自检 |

数据流：适配器 → `(neg_log_probs, token_counts)` → `PerplexityResult.from_token_nll` → 困惑度；适配器 + 指标 → `(confidences, correct)` → `_validate_probs` → `_bin_indices` → ECE / 可靠性图 / 分解；`brier_score` 不分 bin → `CalibrationReport`。

---

## 3. 逐段精讲

### 3.1 `PerplexityResult.from_token_nll`：聚合与契约

```python
    @classmethod
    def from_token_nll(cls, neg_log_probs, token_counts) -> "PerplexityResult":
        if len(neg_log_probs) != len(token_counts):
            raise ValueError("neg_log_probs and token_counts must align")
        total_nll = 0.0
        total_tokens = 0
        for nll, n in zip(neg_log_probs, token_counts):
            if nll < 0:
                raise ValueError("neg_log_probs must be non-negative (did you forget the negation?)")
            if n < 0:
                raise ValueError("token_counts must be non-negative")
            total_nll += float(nll)
            total_tokens += int(n)
        if total_tokens == 0:
            return cls(perplexity=float("nan"), avg_neg_log_likelihood=0.0, total_tokens=0)
        avg_nll = total_nll / total_tokens
        return cls(perplexity=math.exp(avg_nll), avg_neg_log_likelihood=avg_nll, total_tokens=total_tokens)
```

- **公式**：`PPL = exp(Σ NLL / Σ tokens)`。这是 token 加权（micro）平均：两个序列 10 和 90 个 token，每 token NLL 分别为 ln 2 和 ln 8 时，困惑度为 6.96，而不是 (2 + 8)/2 = 5。
- **输入语义**：`neg_log_probs[i]` 是**第 i 个序列所有 token 的 NLL 之和**，`token_counts[i]` 是该序列的 token 数，二者长度必须相同。**注意**：讲义写的是 "a list of per-token log-probabilities, a list of token counts per sequence"，按字面传 40 个逐 token 值和 `[10, 30]` 会因长度不一致抛错；若适配器传的是每序列**平均** NLL，代码无法察觉，会得到离谱的低困惑度（测验 Q11：正确 5.755，误传平均值得 1.078）。
- **符号契约**：任何负的 NLL 都被拒绝。讲义："an adapter that returns `log p` instead of `-log p` produces a perplexity below one, which is impossible."
- **零 token**：返回 `NaN` 困惑度而不是抛错，由 runner 决定是否报告。讲义："Perplexity returns `NaN` for the zero-token case."
- **注意**：某个序列 NLL > 0 但 token 数为 0 不会被拒，其 NLL 会被计入分子而不增加分母，悄悄抬高困惑度。
- `@classmethod` + `cls(...)`：替代构造函数（alternative constructor）的惯用写法；返回类型注解写成字符串 `"PerplexityResult"`（前向引用）。

### 3.2 输入校验

```python
def _validate_probs(confidences: np.ndarray, correct: np.ndarray) -> None:
    if confidences.shape != correct.shape:
        raise ValueError("confidences and correct must have the same shape")
    if confidences.ndim != 1:
        raise ValueError("confidences must be 1-D")
    if confidences.size == 0:
        return
    if float(confidences.min()) < 0.0 or float(confidences.max()) > 1.0:
        raise ValueError("confidences must lie in [0, 1]")
    uniq = set(np.unique(correct).tolist())
    if not uniq.issubset({0, 1, 0.0, 1.0, True, False}):
        raise ValueError("correct must be 0/1 or boolean")
```

- 调用方先 `np.asarray(..., dtype=np.float64)`，所以列表、元组、布尔数组都能传进来。
- `np.unique(correct).tolist()` 把 NumPy 标量转成 Python 数，再用集合的 `issubset` 检查。由于 `0 == 0.0 == False`，集合里写这么多元素其实是冗余的，`{0, 1}` 就够了。
- **注意**：**NaN 漏网**：`NaN` 参与比较总是 `False`，`min()` 返回 `NaN`，两个条件都不成立，校验通过；最终 ECE 变成 `NaN`（实测）。修正：加 `np.isfinite` 检查。
- 空输入在范围检查前直接返回，让后续函数可以返回 0 / 零数组。

### 3.3 `_bin_indices`：等宽分 bin

```python
def _bin_indices(confidences: np.ndarray, n_bins: int) -> np.ndarray:
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.searchsorted(edges, confidences, side="right") - 1
    idx = np.clip(idx, 0, n_bins - 1)
    return idx
```

- `np.linspace(0, 1, 11)` 生成 11 个边界，构成 10 个区间 `[0, 0.1), [0.1, 0.2), …, [0.9, 1.0]`。
- `searchsorted(edges, x, side="right")` 返回"第一个**大于** x 的边界"的位置，减 1 就是 x 所在区间的下标，实现左闭右开。
- `np.clip` 把 1.0（结果为 10）夹回 9，让最后一个区间是闭区间。
- 完全向量化：一次调用处理所有样本，没有 Python 循环。
- **注意**：**浮点边界误差**：`linspace` 生成的第 3、6、7 个边界是 `0.30000000000000004`、`0.6000000000000001`、`0.7000000000000001`。于是置信度恰好为 0.3、0.6、0.7 的样本被放进**前一个** bin（实测 `[0.0, 0.1, 0.2, 0.3, 0.5, 0.6, 0.7, 0.9, 0.95, 1.0]` → `[0 1 2 2 5 5 6 9 9 9]`）。对于常给出整十分位置信度的模型（如口头报告 "0.7"），可靠性图会整体错位一格。修正：`np.floor(conf * n_bins + 1e-9)` 再 `clip`（测验 Q12）。

### 3.4 ECE

```python
def expected_calibration_error(confidences, correct, bins: int = 10) -> tuple[float, int]:
    conf = np.asarray(confidences, dtype=np.float64)
    corr = np.asarray(correct, dtype=np.float64)
    _validate_probs(conf, corr)
    if bins <= 0:
        raise ValueError("bins must be positive")
    n = conf.size
    if n == 0:
        return (0.0, 0)
    idx = _bin_indices(conf, bins)
    total_gap = 0.0
    populated = 0
    for b in range(bins):
        mask = idx == b
        size = int(mask.sum())
        if size == 0:
            continue
        populated += 1
        avg_conf = float(conf[mask].mean())
        avg_acc = float(corr[mask].mean())
        total_gap += (size / n) * abs(avg_conf - avg_acc)
    return (float(total_gap), populated)
```

- **公式**：`ECE = Σ_b (n_b / N) · |conf_b − acc_b|`。
- `mask = idx == b` 是布尔数组，`conf[mask]` 用**布尔索引**取出该 bin 的样本；`mask.sum()` 数 True 的个数。
- 空 bin 直接跳过，不计入 `populated`。
- **返回 `populated_bins`**：讲义说 ECE 对 bin 数和样本量有偏，"The implementation returns the number of populated bins along with the ECE so the runner can refuse to report a single number on too few samples."
- 例（测验 Q3）：0.9×4（对 3）、0.6×5（对 2）、0.2×1（错）→ `0.4×0.15 + 0.5×0.2 + 0.1×0.2 = 0.18`，3 个 bin 有数据。
- **注意**：**bin 内抵消**：取绝对值是在 bin 层面做的，同一 bin 里过度自信与欠自信的样本会先平均再比较。实测 20 个样本（0.82 对 7/10，0.88 对 10/10）全在一个 bin，ECE = 0，但 Brier = 0.119。讲义说"overconfident on half the bins and underconfident on the other half can have low ECE"——跨 bin 并不会抵消（实测两个 bin 各偏 0.15 和 0.25 时 ECE = 0.20），真正的盲区是 bin 内。

### 3.5 Brier 分数与 Murphy 分解

```python
def brier_score(confidences, correct) -> float:
    ...
    return float(np.mean((conf - corr) ** 2))
```

- 逐样本平方误差的均值，NumPy **向量化**：`conf - corr` 逐元素相减，`** 2` 逐元素平方。
- 取值范围 [0, 1]：全对且置信度 1 → 0；全错且置信度 1 → 1；恒输出 0.5 → 恰好 0.25（讲义写成 "0.25 minus a correction term" 不准确）。
- 是**严格适当评分规则**：只有报告真实概率才能让期望 Brier 最小，所以不能靠"调整自信程度"作弊。

```python
def brier_decomposition(confidences, correct, bins: int = 10) -> dict:
    ...
    overall = float(corr.mean())
    for b in range(bins):
        ...
        reliability += (size / n) * (avg_conf - avg_acc) ** 2
        resolution += (size / n) * (avg_acc - overall) ** 2
    uncertainty = overall * (1.0 - overall)
    brier = reliability - resolution + uncertainty
```

- **reliability**：bin 置信度与 bin 准确率之差的平方，加权平均——越小越好（就是"校准"）。
- **resolution**：bin 准确率偏离总体准确率的程度——越大越好（就是"区分能力"）。
- **uncertainty**：`ō(1 − ō)`，只由数据决定。
- **注意**：返回的 `brier` 是用分解**重新算出来的**，只在每个 bin 内置信度都相同时才精确等于 `brier_score`。精确恒等式还差一项 `(1/N) Σ_b [Σ(p_i − p̄_b)² − 2 Σ(p_i − p̄_b)(y_i − ȳ_b)]`（测验 Q10 推导）。实测：Q6 数据分解给 0.1275、真实 0.1194；`synthetic_calibrated(500, seed=21)` 分解 0.15208、真实 0.15118。测试只要求 `places=2`，掩盖了差距。
- **注意**：讲义说 runner "logs the decomposition for the dashboard"，但 `CalibrationReport` 并不包含分解，它只在测试中被调用。

### 3.6 可靠性图与报告对象

```python
def reliability_diagram(confidences, correct, bins: int = 10):
    ...
    if conf.size == 0:
        return (np.zeros(bins), np.zeros(bins), np.zeros(bins, dtype=np.int64))
    idx = _bin_indices(conf, bins)
    bin_conf = np.zeros(bins)
    bin_acc = np.zeros(bins)
    bin_count = np.zeros(bins, dtype=np.int64)
    for b in range(bins):
        ...
    return (bin_conf, bin_acc, bin_count)
```

- 三个等长数组；空 bin 的置信度和准确率填 0——画图时要用 `bin_count > 0` 过滤，否则会在原点画出假的点。
- 讲义："We return numpy arrays so downstream code does not have to convert."

```python
@dataclass
class CalibrationReport:
    ece: float
    brier: float
    populated_bins: int
    reliability: tuple
    n_samples: int

    def to_dict(self) -> dict:
        bin_conf, bin_acc, bin_count = self.reliability
        return {..., "reliability": {"bin_conf": bin_conf.tolist(), ...}}

    @classmethod
    def from_predictions(cls, confidences, correct, bins: int = 10) -> "CalibrationReport":
        ece, populated = expected_calibration_error(confidences, correct, bins=bins)
        brier = brier_score(confidences, correct)
        rel = reliability_diagram(confidences, correct, bins=bins)
        return cls(ece=ece, brier=brier, populated_bins=populated, reliability=rel, n_samples=len(confidences))
```

- `to_dict` 用 `.tolist()` 把 NumPy 数组转成 Python 列表，才能 `json.dumps`。
- `from_predictions` 调用三个函数，各自重复做了一遍 `asarray`、校验和分 bin；数据量大时可以合并成一次。
- 讲义里接口写的是 `report.reliability`（三元组）和 `report.populated_bins`，与代码一致；`n_samples` 是代码额外加的。

### 3.7 合成数据与 demo

```python
def synthetic_calibrated(n, seed=0):
    rng = np.random.default_rng(seed)
    confidences = rng.uniform(0.0, 1.0, size=n)
    correct = (rng.uniform(0.0, 1.0, size=n) < confidences).astype(np.int64)

def synthetic_overconfident(n, seed=1):
    confidences = rng.uniform(0.7, 1.0, size=n)
    correct = (rng.uniform(0.0, 1.0, size=n) < confidences * 0.5).astype(np.int64)

def synthetic_underconfident(n, seed=2):
    confidences = rng.uniform(0.0, 0.3, size=n)
    correct = (rng.uniform(0.0, 1.0, size=n) < 0.5 + confidences).astype(np.int64)
```

- 核心技巧：`uniform(0,1) < p` 以概率 p 为真，所以"答对概率"可以被精确控制。
  - calibrated：答对概率 = 置信度，理论 ECE = 0（有限样本下不为 0）；
  - overconfident：答对概率 = 置信度的一半，平均置信度约 0.85、准确率约 0.42；
  - underconfident：置信度只有 0–0.3，答对概率却是 0.5–0.8，平均置信度约 0.15、准确率约 0.65。
- `np.random.default_rng(seed)` 是 NumPy 推荐的新式随机数生成器，每个函数用独立的种子，结果可复现。
- `synthetic_token_nll`：12 个序列、长度 20–59，每序列每 token 的 NLL 在 [1.5, 3.0) 之间，所以困惑度必然落在 `e^1.5 ≈ 4.48` 到 `e^3 ≈ 20.1` 之间，demo 用 `3 < ppl < 25` 做健全性检查。
- demo 的通过条件：calibrated 的 ECE ≤ 0.07，overconfident 的 ECE > 0.1，困惑度在区间内。underconfident 没有断言。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 困惑度按 token 加权 | 语料困惑度的标准定义 | 输入单位（总和 vs 平均）只靠约定，传错无法察觉 |
| 负 NLL 直接抛错 | 把适配器 bug 暴露在最早的位置 | 无 |
| 零 token 返回 NaN | 不让 runner 崩溃，由上层决定 | 下游必须记得检查 NaN |
| 等宽 bin + `searchsorted` | 向量化、与文献惯例一致 | 浮点边界把 0.3/0.6/0.7 放错 bin；可改用 `floor` |
| ECE 同时返回 `populated_bins` | 让 runner 能拒绝"太少样本"的 ECE | 没有给出置信区间；生产可加 bootstrap |
| 默认 10 个 bin、可配 | 讲义："publishing convention (10) and the comparison convention (15)" | 不同 bin 数的 ECE 不可比 |
| Brier 不分 bin | 精确、无超参数 | 单一数字难以诊断，需要配合分解与可靠性图 |
| 分解按 bin 计算 | 便于画面板 | 只是近似，缺 bin 内项；报告中应标注 |
| 可靠性数据返回 NumPy 三元组 | 下游画图/算变体 ECE 无需转换 | 空 bin 填 0，画图需过滤 |
| 合成数据控制答对概率 | 测试有已知的"真值" | 与真实模型分布差异很大 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class PerplexityResult:` | 自动生成构造函数等 |
| `@classmethod` 替代构造函数 | `def from_token_nll(cls, ...)` → `return cls(...)` | 用类方法提供"从别的数据构造"的入口 |
| 字符串形式的前向引用 | `-> "PerplexityResult"` | 在类定义内部引用类自身 |
| `typing.Sequence` | `neg_log_probs: Sequence[float]` | 接受列表、元组、数组等任意序列 |
| `float("nan")` | `perplexity=float("nan")` | 表示"未定义"的浮点值；`math.isnan` 检查 |
| `zip` 并行遍历 | `for nll, n in zip(neg_log_probs, token_counts)` | 两个序列一一配对 |
| `np.asarray(..., dtype=)` | `np.asarray(confidences, dtype=np.float64)` | 转换成指定类型的数组（已是同 dtype 的数组时不复制） |
| `.shape` / `.ndim` / `.size` | `confidences.ndim != 1` | 形状、维数、元素总数 |
| `np.unique` + `.tolist()` + 集合 | `set(np.unique(correct).tolist())` | 去重后转 Python 集合 |
| `set.issubset` | `uniq.issubset({0, 1, ...})` | 子集判断 |
| `np.linspace` | `np.linspace(0.0, 1.0, n_bins + 1)` | 等间距的 n+1 个点（含两端） |
| `np.searchsorted` | `np.searchsorted(edges, x, side="right")` | 在有序数组中找插入位置（向量化） |
| `np.clip` | `np.clip(idx, 0, n_bins - 1)` | 把值夹到区间内 |
| 布尔掩码索引 | `mask = idx == b`；`conf[mask].mean()` | 用布尔数组筛选元素 |
| 向量化运算 | `np.mean((conf - corr) ** 2)` | 逐元素运算，无需显式循环 |
| `np.zeros(..., dtype=np.int64)` | `bin_count = np.zeros(bins, dtype=np.int64)` | 指定整数类型的零数组 |
| `np.random.default_rng` | `rng = np.random.default_rng(seed)`；`rng.uniform(a, b, size=n)`；`rng.integers(20, 60, size=12)` | 新式随机数生成器 |
| 布尔数组转整数 | `(u < p).astype(np.int64)` | True/False → 1/0 |
| 元组解包 | `bin_conf, bin_acc, bin_count = self.reliability` | 一次取出三元组 |
| 函数作为值 | `for label, builder in [("calibrated", synthetic_calibrated), ...]` | 把函数放进列表循环调用 |
| f-string 格式符 | `{label:14s}`、`{report.ece:.4f}`、`{pp.perplexity:.3f}` | 宽度与小数位 |
| `(bin_count > 0).sum()` | demo 最后一行 | 数非空 bin 个数 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + NumPy）：

```text
$ python3 main.py
calibrated     ece=0.0352 brier=0.1766 populated=10
overconfident  ece=0.4283 brier=0.4271 populated=3
underconfident ece=0.4980 brier=0.4704 populated=3
perplexity     value=9.408  avg_nll=2.242  tokens=519
reliability    populated_bins=4
$ echo $?
0
```

逐项解读：

- **calibrated**：ECE 0.035。真实生成过程是完美校准的，非零的 ECE 完全来自有限样本噪声（800 个样本、10 个 bin）。作为参照，同一生成器 100 个样本 ECE 约 0.086，10 万个样本约 0.003；用 15 个 bin 时约 0.042。Brier 0.177 不为 0，因为置信度本身大多不接近 0 或 1——这是 uncertainty 与有限 resolution 的体现（分解：reliability 0.0018、resolution 0.0735、uncertainty 0.2496）。
- **overconfident**：平均置信度约 0.85、准确率约 0.42，ECE 0.43 ≈ 二者之差。只有 3 个 bin 有数据（7、8、9）。Brier 0.427 很高，分解中 reliability 0.185 占主要部分。
- **underconfident**：平均置信度约 0.15、准确率约 0.65，ECE 0.50。注意它的 Brier（0.470）**高于**恒输出 0.5 的预测器（0.25）——测试 `test_underconfident_lower_brier_than_uniform` 的名字暗示的结论与事实相反，而它的断言只检查了 `0 ≤ Brier ≤ 1`。
- **perplexity 9.408**：12 个序列共 519 个 token，平均 NLL 2.242 nats，`e^2.242 ≈ 9.41`，在 4.48–20.1 的理论区间内。
- **reliability populated_bins=4**：输入 `[0.05, 0.15, 0.85, 0.95]` 分别落在 bin 0、1、8、9。
- 退出码 0：三项健全性检查都通过。

---

## 7. 动手改一改

1. **修正分 bin**：把 `_bin_indices` 改为 `np.clip(np.floor(conf * n_bins + 1e-9).astype(int), 0, n_bins - 1)`，验证 0.3、0.6、0.7 落入 bin 3、6、7，并补一个测试锁住这个行为。
2. **拒绝 NaN**：在 `_validate_probs` 中加入 `np.isfinite` 检查，补测试。
3. **精确分解**：在 `brier_decomposition` 中加上 bin 内方差与协方差项，使返回的 `brier` 与 `brier_score` 在 `places=12` 下相等；用测验 Q6 的数据验证（0.1275 → 0.1194）。
4. **自适应 ECE**：实现等样本数分 bin（每个 bin 样本数相同，用 `np.quantile` 找边界），比较 `synthetic_overconfident` 在两种分 bin 下的 ECE 和 populated_bins。
5. **ECE 置信区间**：对 `(confidences, correct)` 做 1000 次 bootstrap，给出 ECE 的 95% 区间，观察 100 个样本与 10000 个样本时区间宽度的差异。
6. **进阶：temperature scaling**：生成一组带 logits 的多分类合成数据，在验证切片上用网格搜索拟合温度 T 使 NLL 最小，在测试切片上比较校准前后的 ECE 与 Brier（讲义 Going further）。

---

## 8. 常见坑

- **把各序列困惑度取平均**：应当按 token 加权（6.96 vs 5.0）。
- **适配器传每序列平均 NLL**：代码无法察觉，困惑度会低得离谱。
- **忘了取负号**：`log p` 是负数，代码会抛错——这是好事，不要用 `abs()` 绕过。
- **跨 tokenizer 比较困惑度**：困惑度是"每 token"的量，应换算成 bits per byte。
- **以为 ECE = 0 就是完美校准**：bin 内抵消、只用一个 bin 的情况下都可能为 0；恒输出基准率的模型 ECE 也为 0。
- **样本太少还报 ECE**：100 个样本时完美校准的生成器也能有 0.086 的 ECE。
- **不同 bin 数的 ECE 混比**：10 bin 与 15 bin 的数值不可直接比较。
- **整十分位置信度落错 bin**：0.3、0.6、0.7 由于浮点边界落入前一个 bin。
- **可靠性图把空 bin 当成 (0, 0) 点画出来**：要用 `bin_count > 0` 过滤。
- **把分解出来的 `brier` 当成真实 Brier**：只是近似。
- **NaN 置信度**：会通过校验并让 ECE 变成 NaN。

---

## 9. 测试在验证什么

测试文件：`tests/test_calibration.py`（`unittest` 风格），导入主要函数、两个报告类和三个合成数据生成器。

运行方式：

```bash
cd code
python3 -m pytest -q            # 或：python3 -m unittest discover tests
```

实际运行结果：`23 passed in 0.08s`。

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `TestPerplexity` | `test_uniform_two_token_alphabet` | 每 token NLL = ln 2 → 困惑度 2（均匀二选一） |
| | `test_perfect_model` | NLL = 0 → 困惑度 1 |
| | `test_zero_tokens_returns_nan` | 空输入 → NaN、`total_tokens = 0` |
| | `test_misaligned_inputs` | 长度不一致抛错 |
| | `test_negative_nll_rejected` | 负 NLL 抛错（符号契约） |
| | `test_multi_sequence_weighted_correctly` | 两序列按 token 加权，而不是平均困惑度 |
| `TestECE` | `test_perfect_calibration_yields_zero` | 置信度 0.05 全错、0.95 全对 → ECE = **0.05**（名字说"yields zero"，断言的是 0.05：每个 bin 都有 0.05 的 gap） |
| | `test_completely_miscalibrated` | 置信度 0.99 全错 → ECE 0.99、只有 1 个 bin |
| | `test_empty_input` / `test_bins_must_be_positive` | 空输入返回 `(0.0, 0)`；`bins = 0` 抛错 |
| | `test_confidence_out_of_range_rejected` / `test_misaligned_lengths` | 置信度 1.5、长度不一致都抛错 |
| | `test_synthetic_overconfident_has_higher_ece` | 过度自信生成器的 ECE 高于校准生成器 |
| `TestBrier` | `test_perfect` / `test_max` / `test_uniform_predictor` | 0、1、0.25 三个特征值 |
| | `test_empty_input` | 空输入返回 0 |
| | `test_decomposition_sums_to_brier` | 分解之和与 Brier 在 2 位小数内一致（容差掩盖了约 0.0009 的近似误差） |
| `TestReliabilityDiagram` | `test_bin_counts_match` | 计数总和等于样本数、数组长度等于 bin 数 |
| | `test_correct_bin_assignment` | 0.05 进 bin 0、0.95 进 bin 9，平均置信度正确 |
| | `test_empty_input_returns_zero_arrays` | 空输入返回长度为 bin 数的零数组 |
| `TestCalibrationReport` | `test_report_roundtrip` | `to_dict` 含 ece、brier、reliability，长度和样本数正确 |
| | `test_underconfident_lower_brier_than_uniform` | 名字说"欠自信的 Brier 低于均匀预测器"，实际只断言 `0 ≤ Brier ≤ 1`；事实上欠自信生成器的 Brier（约 0.47）**高于**均匀预测器（0.25） |

测试没有覆盖的地方：

- 边界值 0.3、0.6、0.7 的分 bin；
- NaN 置信度；
- 分解的精确性（仅 2 位小数）；
- 欠自信生成器 ECE 的数值；
- `correct` 中出现 2 之类的非法值时抛错；
- 某序列 token 数为 0 但 NLL > 0 的情况。
