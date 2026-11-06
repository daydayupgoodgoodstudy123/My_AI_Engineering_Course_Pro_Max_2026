# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 24 节 Evaluation 与协调基准评测 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

这是一个"benchmark 计分卡生成器"的玩具版，把讲义里"怀疑地阅读 benchmark 声明"的几条原则变成可运行的代码：

1. **MARBLE 式 milestone 指标**：任务失败也能拿到部分里程碑，指标不只是 0/1 的成功率。
2. **污染检查**：把任务分成"训练时见过（seen）"和"留出（held）"两组，比较两组准确率差 Δ；有污染的系统在 seen 上会额外加分。
3. **随机基线与成本**：每个系统都报告相对随机基线的提升，以及每任务成本、每里程碑成本。
4. **六项声明清单**：打印讲义的 checklist。

讲义开头还说本课"runs a topology-vs-metric sweep"，但代码里**没有任何拓扑**（star / chain / tree / graph）相关的模拟；"随机基线"也是写死的常数。

> 一句话：**同一组系统，按"原始准确率"、"留出集准确率"和"每里程碑成本"排名会得出不同结论**——而这份代码自己写死的 Takeaways 恰好又示范了"结论与数据不符"的反面教材。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SystemSim` | dataclass | 一个被测系统的参数：基础准确率、每任务成本、里程碑完成率、污染加成、抖动 | 被测系统 |
| `TaskResult` | dataclass | 单个任务的结果：是否见过、成败、里程碑数、成本 | 单条评测记录 |
| `SYSTEMS` | 列表 | 三个预设系统 A / B / C | 对比对象 |
| `run_task` | 函数 | 模拟一个任务：抖动 → 伯努利成败 → 里程碑 | 单题评测 |
| `random_baseline` | 函数 | 返回常数 0.15 | 随机基线 |
| `run_bench` | 函数 | 跑 40 道 seen + 160 道 held，汇总 6 个指标 | benchmark 运行 |
| `format_scorecard` | 函数 | 打印计分表、污染标记、vs random | 计分卡 |
| `print_claim_scorecard` | 函数 | 打印六项 checklist | 声明审查清单 |
| `main` | 函数 | 依次调用并打印写死的 Takeaways | 入口 |

数据流：`main()` → `format_scorecard()` → 对每个 `SystemSim` 调用 `run_bench(seed=17)` → 内部 200 次 `run_task` → 汇总成字典 → 计算 Δ、污染标记、vs random → 打印一行；再 `print_claim_scorecard()` → 打印 Takeaways。

---

## 3. 逐段精讲

### 3.1 两个 dataclass 与三个系统

```python
@dataclass
class SystemSim:
    name: str
    base_accuracy: float
    cost_per_task: float
    milestone_completion_rate: float
    training_contamination: float = 0.0  # extra accuracy on seen tasks
    variance: float = 0.1

SYSTEMS = [
    SystemSim("system-A", base_accuracy=0.70, cost_per_task=0.30,
              milestone_completion_rate=0.80, training_contamination=0.20),
    SystemSim("system-B", base_accuracy=0.64, cost_per_task=0.12,
              milestone_completion_rate=0.55, training_contamination=0.0),
    SystemSim("system-C", base_accuracy=0.55, cost_per_task=0.25,
              milestone_completion_rate=0.70, training_contamination=0.0),
]
```

- 三个系统的设计意图：A 最准但最贵且有污染（seen 题 +0.20）；B 便宜、准确率中等；C 准确率最低、成本中等。
- 有默认值的字段（`training_contamination`、`variance`）必须排在无默认值字段之后，这是 dataclass 的规则。
- `TaskResult.accuracy` 只取 1.0 或 0.0，名字叫 accuracy 实际是"是否成功"。

### 3.2 `run_task`：抖动、伯努利、部分里程碑

```python
def run_task(system: SystemSim, task_id: str, seen: bool, rng: random.Random) -> TaskResult:
    base = system.base_accuracy
    if seen:
        base += system.training_contamination
    base = max(0.0, min(1.0, base + rng.uniform(-system.variance, system.variance)))
    success = rng.random() < base
    milestones = 4 if success else int(4 * system.milestone_completion_rate * rng.random())
    ...
```

- **污染建模**：见过的题直接把成功率加上 `training_contamination`。A 在 seen 上期望成功率 0.9，在 held 上 0.7。
- `max(0.0, min(1.0, x))` 是把概率截断到 [0, 1] 的惯用写法。
- ⚠️ **`variance` 对期望没有作用**：`U(−v, v)` 的抖动均值为 0，再做一次伯努利抽样，成功概率的期望仍是 `base`（只有截断时例外）。实测 system-C 在 variance = 0 / 0.1 / 0.3 下 500 个种子的平均 held 准确率为 0.5506 / 0.5494 / 0.5455，差异在噪声范围内。它也没有增加结果的方差——单题 0/1 结果的方差只由 p 决定。
- **里程碑**：成功则 4 个满分；失败则 `int(4 × rate × U)`，因为 `rate < 1`、`U < 1`，最多 3 个。期望值（数值计算）：A（rate 0.8）1.125，B（0.55）0.637，C（0.7）0.931。
- ⚠️ 条件表达式 `4 if success else int(...rng.random())` 只在失败时才消耗一个随机数，所以不同系统即使用同一种子，随机数序列也会在第一次成败不同之后错开。

### 3.3 `random_baseline`：名为随机，实为常数

```python
def random_baseline(rng: random.Random) -> float:
    return 0.15  # random routing accuracy on this task family
```

- 接收 `rng` 却不使用；`format_scorecard` 里的 `rng = random.Random(0)` 因此成了死代码。
- 讲义要求"Compares to a random baseline explicitly"——真正的随机基线应在同一任务集上运行一个随机策略、得到带误差的准确率，而不是写一个先验数字。

### 3.4 `run_bench`：六个指标

```python
def run_bench(system: SystemSim, n_seen: int, n_held: int, seed: int = 0) -> dict:
    rng = random.Random(seed)
    ...
    return {
        "name": system.name,
        "accuracy_seen": sum(r.accuracy for r in results_seen) / len(results_seen),
        "accuracy_held": sum(r.accuracy for r in results_held) / len(results_held),
        "milestone_rate_seen": sum(r.milestones for r in results_seen) / (len(results_seen) * 4),
        "milestone_rate_held": sum(r.milestones for r in results_held) / (len(results_held) * 4),
        "cost_per_task": system.cost_per_task,
        "cost_per_milestone_held":
            system.cost_per_task / max(0.01, sum(r.milestones for r in results_held) / len(results_held) / 4),
    }
```

| 指标 | 公式 | 含义 |
|---|---|---|
| `accuracy_seen` / `accuracy_held` | 成功题数 / 题数 | 两组的成功率 |
| `milestone_rate_*` | 里程碑总数 / (题数 × 4) | 平均完成比例，0–1 |
| `cost_per_task` | 直接取参数 | 每题成本（确定值，无噪声） |
| `cost_per_milestone_held` | 每题成本 / held 的 milestone_rate | 见下 |

- `sum(r.accuracy for r in ...)` 是**生成器表达式**，逐个产出值交给 `sum`，不建中间列表。
- `max(0.01, ...)` 防止除零：如果一个里程碑都没完成，分母取 0.01。
- ⚠️ **单位问题**：分母是"完成比例"而不是"每题里程碑数"，所以 `cost_per_milestone_held` 实际是"每完成 4 个里程碑（一整题等价量）的成本"，是真正每里程碑成本的 4 倍。A 表中 0.371，真正每个里程碑约 0.30 / (0.809 × 4) ≈ 0.093。排名不变，但列名 `cost/mil` 会误导。
- ⚠️ 用一个 `seed=17` 跑所有系统，且每个系统只跑一次。按期望值计算，A 与 C 的 cost/mil 都约为 0.382——表中 0.371 vs 0.385 的高下纯属抽样噪声。
- seen 只有 40 题、held 160 题，seen 组的统计误差是瓶颈（见 3.5）。

### 3.5 `format_scorecard`：污染标记与格式化

```python
    rng = random.Random(0)
    rand_baseline = random_baseline(rng)
    for sys in SYSTEMS:
        r = run_bench(sys, n_seen=40, n_held=160, seed=17)
        delta = r["accuracy_seen"] - r["accuracy_held"]
        contam_flag = "*" if delta > 0.1 else " "
        vs_random = r["accuracy_held"] - rand_baseline
        print(f"{r['name']:10s} {r['accuracy_seen']:>10.3f} {r['accuracy_held']:>10.3f} "
              f"{delta:>5.2f}{contam_flag} {r['milestone_rate_held']:>12.3f} "
              f"${r['cost_per_task']:>7.2f} ${r['cost_per_milestone_held']:>9.3f} "
              f"+{vs_random:>10.3f}")
```

- **污染判定**：单向 `delta > 0.1`。逻辑上合理（污染只会让 seen 更好），但阈值没有考虑样本量：
  - 以 p ≈ 0.64、40 vs 160 题计算，Δ 的标准误约 0.085，与阈值 0.1 同量级；
  - 1000 个种子实测：无污染的 B、C 误报率约 12.8% / 12.7%，A 的检出率 94.9%；
  - 本次运行 B 的 Δ = −0.13 就是纯噪声，换个方向就会被冤枉。测验 Q10 给出了两比例 z 检验的替代方案（A：z = 2.25、p = 0.012；B：z = −1.56；C：z = 0）。
- 循环变量名 `sys` 遮蔽了标准库模块名 `sys`（本文件没 import sys，所以不报错，但是坏习惯）。
- ⚠️ `"+{vs_random:>10.3f}"` 把 `+` 写死在格式说明之外：系统低于随机基线时会打印 `+    -0.050`（已验证）。应写成 `{vs_random:>+11.3f}`。
- `vs random` 用 held 准确率减常数 0.15，三个系统都远高于它（+0.40 ~ +0.58）。

### 3.6 `print_claim_scorecard` 与写死的 Takeaways

```python
    for i, item in enumerate(checklist, 1):
        print(f"  [{i}] {item}")
```

- `enumerate(iterable, 1)` 从 1 开始编号。六条清单与讲义"the 2026 checklist"逐条对应。第 1 条写"Pro vs Verified is a 40-point gap"，讲义正文给的数字是约 23% vs 70%+，即 47 个百分点左右，"40+"更准确（skill 文件写的就是"40+ point gap"）。

```python
    print("  system-B is cheapest per milestone; lowest raw accuracy but transparent.")
    print("  system-C sits in the middle but without contamination flag — trustworthy.")
```

- ⚠️ 这两句与实际输出不符：B 的 held 准确率 0.681 排第二，不是最低；C 的 held 准确率最低（0.550）、cost/mil 最高（0.385），并不"居中"。结论是写死的字符串，不随数据变化——评测代码最忌讳这一点。测验 Q9 给了自动生成结论的写法。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用参数化的 `SystemSim` 代替真实系统 | 秒级运行、结果可控，便于展示指标差异 | 只能演示指标计算，不能说明任何真实系统的优劣 |
| 污染 = seen 题加固定分数 | 最直观的污染模型 | 真实污染是部分题目被背下，加成不均匀；检测需要时间切分的新题 |
| seen 40 题 / held 160 题，单一种子 | 输出简短 | Δ 的噪声与阈值同量级，误报率约 13%；应增大样本、多种子、报告置信区间 |
| 硬阈值 Δ > 0.1 | 简单易懂 | 应用两比例检验或 bootstrap 控制误报率 |
| 里程碑：成功 4 个、失败 0–3 个 | 体现"部分功劳" | 真实 milestone 应可客观验证；`cost/mil` 单位需写清 |
| 随机基线写成常数 0.15 | 省事 | 应在同一任务集上实际运行随机策略并给出误差 |
| `variance` 逐题抖动 | 想表达"系统不稳定" | 对期望和方差都几乎没影响；应在 run 级别引入偏移 |
| Takeaways 写死 | 方便教学讲解 | 与数据脱节，参数一改就错；应由结果自动生成 |
| 只有成本，无 token / 墙钟 | 简化 | 讲义要求同时报告 token 成本与墙钟时间 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，可在较旧 Python 中使用 `list[TaskResult]` 等写法 |
| `@dataclass` 与默认值顺序 | `training_contamination: float = 0.0` 放在最后 | 自动生成构造函数；有默认值的字段必须在无默认值字段之后 |
| 关键字参数构造 | `SystemSim("system-A", base_accuracy=0.70, ...)` | 第一个位置参数 + 其余用名字传，可读性好 |
| 变量类型注解 | `results_seen: list[TaskResult] = []` | 标注列表元素类型，方便 IDE 与类型检查器 |
| 行尾注释 | `# extra accuracy on seen tasks` | 解释字段含义 |
| 截断惯用法 | `max(0.0, min(1.0, x))` | 把数值夹在区间内 |
| 条件表达式 | `4 if success else int(...)` | 一行写 if/else；只会求值被选中的分支 |
| 独立随机数生成器 | `random.Random(seed)`、`rng.uniform(a, b)`、`rng.random()` | 可复现，且不干扰全局 `random` |
| 生成器表达式 | `sum(r.accuracy for r in results_seen)` | 惰性产生元素，直接交给 `sum` |
| 字典字面量返回多指标 | `return {"name": ..., "accuracy_seen": ...}` | 用键名访问，比元组更自解释 |
| f-string 格式说明 | `{r['name']:10s}`、`{x:>10.3f}`、`{delta:>5.2f}`、`{x:>7.2f}` | `s` 字符串、`f` 定点小数、`>` 右对齐、数字是宽度与精度 |
| f-string 中的引号 | `f"{r['name']}"` | 外层双引号、内层单引号，避免冲突（Python 3.12 之前不能复用同一种引号） |
| 相邻字符串自动拼接 | `f"..." f"..."` 分两行写 | 括号内相邻的字符串字面量会自动连接 |
| `enumerate(..., 1)` | `for i, item in enumerate(checklist, 1)` | 同时拿到序号和元素，从 1 开始 |
| 字符串乘法 | `"=" * 78` | 生成分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不自动运行（测验中的统计实验就是 import 本模块完成的） |

---

## 6. 运行结果解读

实际运行（Python 3，瞬间完成）：

```text
==============================================================================
BENCHMARK SCORECARD — MARBLE-style milestone + contamination check
  contamination check: accuracy_seen - accuracy_held (delta > 0.1 = suspect)
==============================================================================
system      acc(seen)  acc(held)      Δ   mile(held)   cost/t   cost/mil    vs random
system-A        0.900      0.731  0.17*        0.809 $   0.30 $    0.371 +     0.581
system-B        0.550      0.681 -0.13         0.731 $   0.12 $    0.164 +     0.531
system-C        0.550      0.550  0.00         0.650 $   0.25 $    0.385 +     0.400

  * = contamination flag; held-set accuracy is the canonical number
  random baseline accuracy: 0.150

==============================================================================
CLAIM CHECKLIST — read this before accepting any multi-agent result
==============================================================================
  [1] Which benchmark + split? Pro vs Verified is a 40-point gap for frontier models.
  ...
  [6] Cost disclosure: tokens per task, wall-clock per task?

Takeaways:
  system-A scores highest on seen tasks but has contamination signal (large delta).
  system-B is cheapest per milestone; lowest raw accuracy but transparent.
  system-C sits in the middle but without contamination flag — trustworthy.
  the ranking by 'raw accuracy' vs 'cost per milestone (held)' can differ sharply.
```

逐项解读：

- **system-A**：seen 0.900（期望 0.9）vs held 0.731（期望 0.7），Δ = 0.17 被打上 `*`。按讲义"held-set accuracy is the canonical number"，A 的可信成绩是 0.731，仍是三者最高；95% 置信区间约 [0.662, 0.800]（160 题）。
- **system-B**：held 0.681，95% 置信区间约 [0.609, 0.753]，与 A 的区间重叠——"A 比 B 准"在这个样本量下并不显著。cost/mil 0.164 远低于另两者，因为每题成本只有 0.12。Δ = −0.13 是噪声（标准误约 0.085）。
- **system-C**：held 0.550，三者最低；cost/mil 0.385 三者最高；seen 与 held 恰好都是 0.550，Δ = 0。
- **讲义练习 1 的答案**：每里程碑成本最低的是 B，原始（held）准确率最高的是 A，不一致——这就是最后一句 Takeaway 想说明的道理。
- **Takeaways 第 2、3 句与表格不符**（见 3.6），读者应以表格为准。
- **vs random**：三者都比常数 0.15 高 0.40 以上；但这个基线不是跑出来的，所以这一列提供的信息很有限。

---

## 7. 动手改一改

1. **讲义练习 1**：在 `format_scorecard` 中收集每个系统的结果，自动打印"held 准确率最高"和"cost/mil 最低"的系统，替换写死的 Takeaways（参考测验 Q9）。
2. **修正单位与符号**：把 `cost_per_milestone_held` 改成真正的每里程碑成本（分母不除以 4），列名改为 `cost/ms`；把 `"+{vs_random:>10.3f}"` 改成 `"{vs_random:>+11.3f}"`，再把某个系统的 `base_accuracy` 调到 0.1，确认负号正确显示。
3. **多种子 + 置信区间**：对每个系统跑 30 个种子，报告 held 准确率的均值与 95% 置信区间（或用 bootstrap），观察 A 与 B 是否真的可分。
4. **统计化的污染检查**：用两比例 z 检验替代 `delta > 0.1`，并把 `n_seen` 从 40 改到 400，比较 B、C 的误报率变化（参考测验 Q10）。
5. **真正的随机基线与单 LLM 基线**：加一个 `SystemSim("random", base_accuracy=0.15, cost_per_task=0.0, milestone_completion_rate=0.2)` 和一个"单 LLM"系统（准确率略低、成本低得多），让它们与 A/B/C 同表比较。
6. **进阶：补上讲义说的拓扑扫描**：为 star / chain / tree / graph 定义不同的基础准确率与"每多一个 agent 的协调税"，扫描 agent 数 2–8，画出准确率与成本曲线，观察讲义所说"graph 超过约 4 个 agent 出现协调税"的形状（注意这只是自造模型，数字没有实证意义）。

---

## 8. 常见坑

- **用 seen 准确率排名**：A 的 0.900 含污染加成；排名应以 held 为准。
- **单次运行下结论**：A 与 C 的期望 cost/mil 几乎相同，单次运行却显示 A 更便宜；A 与 B 的准确率置信区间重叠。至少多种子 + 置信区间。
- **硬阈值不看样本量**：Δ 的标准误 ≈ 0.085 时，0.1 的阈值会让无污染系统约 13% 的概率被误判。
- **指标名与单位不符**：`cost/mil` 实为"每 4 个里程碑的成本"。指标定义要写进报告。
- **把 `+` 写死在格式串里**：负数会显示成 `+-0.050` 一类的错误符号。
- **写死结论**：评测脚本的文字结论必须由数据生成，否则参数一改就自相矛盾。
- **把常数当基线**：随机基线、单 LLM 基线都应在同一任务集上实际运行。
- **以为 `variance` 让结果更不稳定**：逐题的零均值抖动经过伯努利抽样后几乎不改变任何统计量。
