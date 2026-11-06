# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 21 节 METR 时间跨度与外部能力 Evaluation ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

这份不到 150 行的脚本把 METR time horizon 的方法论缩成一个可以手跑的实验：

1. **合成数据**：已知"真值"的 horizon（14 小时）和斜率（1.2），按 logistic 模型随机生成 160 个任务的（专家耗时, 成败）记录——这样我们知道正确答案，可以检验估计方法。
2. **logistic 拟合**：用最朴素的全批量梯度下降拟合 `P(success) = sigmoid(w·ln t + b)`。
3. **反解 horizon**：从 `(w, b)` 解出 P = 0.5 / 0.1 / 0.9 时的专家耗时。
4. **eval-context gaming 模拟**：把一部分失败翻成成功，看 horizon 被"抬高"多少。

对应讲义的 The Time Horizon fit（第 1–4 步）与 Why horizons are upper bounds（eval-context gaming）两部分。

> 一句话：**horizon 不是测出来的，是拟合出来的；拟合的输入一旦被污染（gaming）或样本太少，头条数字就会漂移。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `synth_tasks` | 函数 | 在 0.05–48 小时间按对数均匀抽样专家耗时，按真值 logistic 概率抽成败 | 任务套件 + 运行结果 |
| `sigmoid` | 函数 | 带截断的 logistic 函数，避免 `exp` 溢出 | logistic 曲线 |
| `fit` | 函数 | 全批量梯度下降，最小化平均交叉熵，返回 `(w, b)` | logistic 回归拟合 |
| `horizon_at` | 函数 | 反解 `sigmoid(w·ln t + b) = p`，斜率接近 0 时抛异常 | 读出 horizon |
| `inject_gaming` | 函数 | 以概率 `gaming_rate` 把失败翻成成功 | eval-context gaming |
| `report` | 函数 | 打印 50%/10%/90% 三个 horizon | 多阈值报告 |
| `main` | 函数 | 固定种子 → 生成数据 → clean 拟合 → 三种 gaming 率拟合 → 打印总结 | 实验驱动 |

数据流：`random.seed(3)` → `synth_tasks(14.0, n=160)` → `fit` → `horizon_at` ×3 → 对 `rate ∈ {0.1, 0.2, 0.4}`：`inject_gaming` → `fit` → `horizon_at` → HEADLINE 打印。

---

## 3. 逐段精讲

### 3.1 合成数据：已知答案的"考卷"

```python
def synth_tasks(true_horizon_hours: float, slope: float = 1.2,
                n: int = 120) -> list[tuple[float, bool]]:
    log_h = math.log(true_horizon_hours)
    out = []
    for _ in range(n):
        t = math.exp(random.uniform(math.log(0.05), math.log(48)))
        logit = slope * (log_h - math.log(t))
        p = 1.0 / (1.0 + math.exp(-logit))
        success = random.random() < p
        out.append((t, success))
    return out
```

- **对数均匀抽样**：先在 `[ln 0.05, ln 48]` 上均匀取值再取 `exp`，于是 3 分钟到 48 小时各个数量级的任务数量大致相同。这模仿了 HCAST 这类"从 1 分钟到 8+ 小时"的套件设计；如果在线性尺度上均匀抽样，绝大多数任务都会是十几到几十小时。
- **真值模型**：`P = sigmoid(slope · (ln h − ln t))`。t = h 时 logit = 0，P = 0.5，这就是"50% horizon = h"的定义；t 越大 logit 越负，成功率越低。展开后等价于 `sigmoid(w·ln t + b)`，其中真值 `w = −1.2`、`b = 1.2·ln 14 ≈ 3.167`。
- `success = random.random() < p`：伯努利抽样，以概率 p 记为成功。
- 真值下各长度任务的成功率（实际计算）：15 分钟 0.992、1 小时 0.960、14 小时 0.500、48 小时 0.186。
- ⚠️ 函数默认 `n=120`，但 `main` 传的是 `n=160`。
- ⚠️ 讲义练习 1 说"把任务时间网格减半"，但这里没有网格，时间是随机抽的。

### 3.2 sigmoid 与梯度下降拟合

```python
def sigmoid(x: float) -> float:
    if x > 50:
        return 1.0
    if x < -50:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))
```

- 截断到 ±50：`math.exp(-x)` 在 x 很负（如 −1000）时会抛 `OverflowError`（Python 的 `math.exp` 溢出是异常，不像 NumPy 返回 inf）。`sigmoid(50)` 与 1.0 的差在 1e-22 量级，截断不影响结果。

```python
def fit(tasks, iters: int = 4000, lr: float = 0.05) -> tuple[float, float]:
    w = 0.0
    b = 0.0
    for _ in range(iters):
        dw = 0.0
        db = 0.0
        n = len(tasks)
        for t, s in tasks:
            y = 1.0 if s else 0.0
            p = sigmoid(w * math.log(t) + b)
            err = p - y
            dw += err * math.log(t)
            db += err
        w -= lr * dw / n
        b -= lr * db / n
    return w, b
```

- 这是**一元 logistic 回归**，特征是 `x = ln t`。平均交叉熵损失对参数的梯度有简洁形式：`∂L/∂w = mean((p − y)·x)`、`∂L/∂b = mean(p − y)`，代码中的 `err = p − y` 就是"预测概率减标签"。
- 全批量（每步遍历所有任务）、固定学习率 0.05、从 `(0, 0)` 起步。总计算量 4000 × 160 = 64 万次 sigmoid，实测运行约 0.7 秒。
- **是否收敛**：我们把 `iters` 改成 20000 和 100000 重跑，seed=3 的结果从 `w = −1.3867, b = 3.3621`（h50 = 11.296）变为 `w = −1.4131, b = 3.4288`（h50 = 11.320），之后不再变化。4000 步已足够接近最优。
- `ln t` 的范围约为 [−3.0, 3.87]，没有中心化，因此 w 和 b 的梯度相关性较强，需要较多步数；生产中会用牛顿法 / IRLS（几步就收敛）或直接调 `statsmodels`/`scikit-learn`。
- ⚠️ 没有正则化、没有收敛判据、没有置信区间。数据完全可分时（例如全部成功），最大似然估计不存在，GD 会把参数越推越大。

### 3.3 反解 horizon

```python
def horizon_at(w: float, b: float, p: float) -> float:
    logit = math.log(p / (1 - p))
    eps = 1e-12
    if abs(w) < eps:
        raise ValueError(
            f"horizon undefined: slope w={w} is ~0 "
            f"(b={b}, p={p}, logit={logit})"
        )
    return math.exp((logit - b) / w)
```

- 推导：`sigmoid(w·ln t + b) = p` ⇔ `w·ln t + b = logit(p) = ln(p/(1−p))` ⇔ `t = exp((logit(p) − b)/w)`。
- 三个阈值的 logit：p = 0.5 → 0；p = 0.9 → +2.197；p = 0.1 → −2.197。
- 因为 w < 0，p 越大 t 越小：**90% horizon 最短（保守），10% horizon 最长（乐观）**。讲义 Use It 段写成"10% horizon (conservative), and 90% horizon (optimistic)"，恰好说反了。
- 两个阈值的比值 `h10/h90 = exp(2·ln 9/|w|)`，与 b 无关，只由斜率决定。
- 斜率接近 0 时抛异常而不是返回 `inf/nan`，这是好的防御式写法；但它**没有检查 w 的符号**（见第 8 节），也**不提示外推**。

### 3.4 eval-context gaming 模拟

```python
def inject_gaming(tasks, gaming_rate: float):
    gamed = []
    for t, s in tasks:
        if not s and random.random() < gaming_rate:
            gamed.append((t, True))
        else:
            gamed.append((t, s))
    return gamed
```

- 只翻转**失败**，翻转概率与任务长短无关。但失败本来就集中在长任务上，所以长任务被"抬高"得更多 → 曲线变平（|w| 变小）且右移。seed=3 实测斜率：clean −1.387 → 10% −1.277 → 20% −1.255 → 40% −0.854。
- 返回新列表，不修改原 `tasks`，因此三种 gaming 率都基于同一份 clean 数据（但各自独立抽随机数，不是嵌套关系：20% 翻掉的失败不一定包含 10% 翻掉的那些）。
- 这对应讲义练习 4（"flip ~20% of failed tasks to success"）——代码其实已经实现了。

### 3.5 报告与 HEADLINE

```python
def report(label: str, w: float, b: float) -> None:
    h50 = horizon_at(w, b, 0.50)
    h10 = horizon_at(w, b, 0.10)
    h90 = horizon_at(w, b, 0.90)
    print(f"  {label:<40}  50%={h50:>6.2f} hr  "
          f"10%={h10:>6.2f} hr  90%={h90:>6.2f} hr")
```

```python
    for rate, h in gamed_h50.items():
        delta = h - true_h
        print(f"    gaming rate {rate:>4.0%}   50% horizon ≈ {h:>6.2f} hr "
              f"({delta:+.2f} hr vs ground truth)")
```

- `delta` 以**合成真值 14.0** 为基线。但 clean 拟合本身就是 11.30（抽样误差 −2.70），于是 10% gaming 的 delta 是 −0.75，看起来"比 clean 还更准"，和下方打印的 "gaming pushes the observed 50% horizon further from the synthetic ground truth" 相矛盾。要单独衡量 gaming 的影响，基线应该是同一批数据的 clean 拟合（+1.95 / +3.33 / +33.26 小时）。
- 代码自己也承认 "Exact deltas depend on seed, n, iters, and the chosen true_h"，这句话比结论本身更重要。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 合成数据 + 已知真值 | 能检验估计方法是否正确 | 真实评估没有真值；METR 用真实任务 + 人类基线耗时 |
| 对数均匀抽样耗时 | 各数量级任务均衡，匹配 log 尺度拟合 | 真实套件的长任务往往更少、更贵，长端估计更不稳 |
| 纯标准库梯度下降 | 无依赖、每一步可读 | 收敛慢、无标准误；生产用 IRLS / `statsmodels` 并给出 CI |
| 固定 `seed=3` | 结果可复现 | 单一种子会误导（clean 恰好偏低 2.7 小时）；应多种子或 bootstrap |
| 同时报 50/10/90% | 展示阈值选择的影响 | 10% 阈值已超出数据范围，属于外推；讲义对保守/乐观的标签写反 |
| gaming 均匀翻转失败 | 最简单的"测试中表现更好"模型 | 真实 gaming 与任务类型、监控强度相关；还存在反方向的 sandbagging |
| `horizon_at` 对 w≈0 抛异常 | 让错误"大声"失败 | 未检查 w > 0 与外推；应同时返回"是否外推"标记 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，在较老的 Python 上也能写 `list[tuple[float, bool]]` |
| 类型注解 | `def fit(tasks: list[tuple[float, bool]], iters: int = 4000) -> tuple[float, float]` | 标明参数与返回值类型，只作文档与静态检查，运行时不强制 |
| 带注解的变量 | `gamed_h50: dict[float, float] = {}` | 给局部变量标注类型 |
| 默认参数 | `slope: float = 1.2, n: int = 120` | 调用时可省略 |
| 元组与解包 | `for t, s in tasks:`、`w, b = fit(tasks)` | 每个任务是 `(耗时, 成败)` 二元组 |
| 条件表达式 | `y = 1.0 if s else 0.0` | 一行内的 if/else |
| 增强赋值 | `dw += err * math.log(t)`、`w -= lr * dw / n` | 原地累加/更新 |
| `math` 模块 | `math.log`、`math.exp` | 标量数学函数；`math.exp` 溢出会抛 `OverflowError` |
| `random` 模块 | `random.seed(3)`、`random.uniform(a, b)`、`random.random()` | 全局伪随机数生成器；固定种子保证可复现 |
| 抛出异常 | `raise ValueError(f"horizon undefined: ...")` | 遇到无法定义的结果时主动报错 |
| f-string 格式符 | `{label:<40}`、`{h50:>6.2f}`、`{rate:.0%}`、`{delta:+.2f}` | 左对齐宽 40；右对齐宽 6 保留 2 位；百分比格式（0.1→10%）；强制显示正负号 |
| 字符串乘法 | `"=" * 80` | 生成 80 个等号的分隔线 |
| 字典迭代 | `for rate, h in gamed_h50.items():` | 同时取键和值；字典保持插入顺序 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3，耗时约 0.7 秒）：

```text
Synthetic ground truth: 50% horizon = 14.0 hr
--------------------------------------------------------------------------------
  clean evaluation (no gaming)              50%= 11.30 hr  10%= 55.09 hr  90%=  2.32 hr
  with eval-context gaming rate 10%         50%= 13.25 hr  10%= 74.00 hr  90%=  2.37 hr
  with eval-context gaming rate 20%         50%= 14.63 hr  10%= 84.29 hr  90%=  2.54 hr
  with eval-context gaming rate 40%         50%= 44.56 hr  10%=584.63 hr  90%=  3.40 hr

HEADLINE: horizons are fit to observed success; gaming shifts them
  With seed=3 / n=160 / iters=4000 / true_h=14.0 hr:
    clean fit          50% horizon ≈  11.30 hr (ground truth 14.0)
    gaming rate  10%   50% horizon ≈  13.25 hr (-0.75 hr vs ground truth)
    gaming rate  20%   50% horizon ≈  14.63 hr (+0.63 hr vs ground truth)
    gaming rate  40%   50% horizon ≈  44.56 hr (+30.56 hr vs ground truth)
```

逐项解读：

- **clean 11.30 vs 真值 14.0**：拟合参数 `w = −1.387, b = 3.362`（真值 −1.2, 3.167）。不是 GD 没收敛（多跑 25 倍步数只变到 11.32），而是抽样误差：160 个任务中只有 39 个失败、31 个长于 14 小时。我们额外做了 200 次 bootstrap，95% 区间约 7.96–16.06 小时；换 30 个种子，clean 估计的中位数是 13.79，范围 11.06–35.49。讲义练习 1 让你"确认 50% horizon 与真值相符"——在 seed=3 下，它只是"在置信区间内"。
- **10% 列（55→584 小时）**：数据中最长任务约 46.6 小时，10% horizon 全部在数据范围之外，是外推出来的。gaming 40% 时斜率变平到 −0.854，外推被放大到 584 小时。
- **90% 列（2.32→3.40）**：变化最小。短任务本来就几乎都成功，可翻转的失败很少。这说明 gaming 主要扭曲的是曲线的长端。
- **50% 列的趋势**：相对 clean 基线，gaming 10%/20%/40% 分别把 horizon 抬高 17%、29%、294%。多种子中位数（13.79 → 18.30 → 22.03 → 33.73）也显示单调上升，这才是该演示的结论。
- **HEADLINE 的 delta**：以真值为基线，把抽样误差和 gaming 偏差混在一起（见 3.5）。
- 输出没有打印 `w`，无法直接看到斜率变平；建议在 `report` 中加上 `w`。

---

## 7. 动手改一改

1. **打印斜率并改基线**：让 `report` 同时输出 `w`、`b`；HEADLINE 的 delta 改为相对 clean 拟合计算，并保留"相对真值"作为第二列。
2. **多种子统计**（讲义练习 1 的正确做法）：对 seed 0–29 各跑一次，输出 clean 和各 gaming 率下 50% horizon 的中位数与 5%/95% 分位数。
3. **bootstrap 置信区间**：对 seed=3 的 160 个任务有放回重采样 200 次，给 50% horizon 加上 95% 区间（参考值约 7.96–16.06 小时）。注意把 `iters` 调小、`lr` 调大以控制耗时。
4. **样本量敏感性**：在同一种子下比较 n = 40/80/160/640（参考值 7.91/9.98/11.30/12.72 小时），再试着把时间上限从 48 小时缩到 8 小时（与 HCAST 的上限接近），观察 10% horizon 是否全部变成外推。
5. **sandbagging 模拟**：写 `inject_sandbagging(tasks, rate, min_hours)`，把长于 `min_hours` 的一部分**成功**翻成失败，看 horizon 如何向左偏，体会它为什么会让安全阈值被低估（第 20 节）。
6. **进阶**：把 GD 换成牛顿法（IRLS），比较达到相同精度所需的迭代次数；再按"任务族"分组生成数据（同族任务成功率相关），观察普通 bootstrap 与按族 bootstrap 的区间宽度差异。

---

## 8. 常见坑

- **把 10% horizon 当成保守值**：w < 0 时，p 越高 horizon 越短。保守的是 90%（或 80%）horizon。讲义 Use It 段标签写反了。
- **单种子下比较"离真值多远"**：抽样误差可能比你想测的效应还大。比较 gaming 影响要用同一份数据的 clean 拟合作基线，并多跑几个种子。
- **忽略斜率符号**：数据退化（全部成功、或长任务反而更容易）时会拟合出 w > 0，`horizon_at` 仍会返回一个数字。实测：3 个全成功任务拟合出 `w ≈ +1.82`。
- **报告外推值**：超出最长任务耗时的 horizon（如 584 小时）只是曲线形状的假设。
- **以为 GD 没收敛才偏离真值**：先增加迭代数验证收敛，再归因到样本量。
- **用 `math.exp` 而不截断**：`math.exp(1000)` 会抛 `OverflowError`，这就是 `sigmoid` 里 ±50 截断的作用。
- **把 horizon 当部署可靠性**：这份代码的"成功"是干净的伯努利抽样；真实部署还有工具差距、用户歧义和不可逆后果，讲义明确说 horizon 是上界。
