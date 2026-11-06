# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 09 节 代码迁移 Agent——仓库级语言与运行时升级 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`random`、`dataclasses`）；不调用 LLM、不操作真实仓库

---

## 1. 这份代码在考察什么

讲义的综合项目是：用 OpenRewrite/libcst 配方 + LLM agent 把 50 个真实仓库从 Java 8 升到 17（或 Python 2 升到 3），每个仓库一个 Daytona 沙箱，严格预算（30 分钟、8 美元、20 轮），测试 + 覆盖率门禁通过才开 PR，否则归入失败分类法。

`main.py` 是一个**蒙特卡洛模拟**，docstring 说它抓住的"最难的架构原语"是**两层结构**：

1. 先跑确定性配方（快、可审计、安全）；
2. 剩下的失败交给带硬预算的 agent 循环；
3. 失败的仓库经过分类，汇总成失败分类法（taxonomy）看板。

代码里没有任何真实的构建、补丁或 LLM 调用：仓库是随机生成的（只有名字、行数、语言、难度），"通过与否"由与难度相关的概率决定，失败分类由固定权重随机抽样。它模拟的是**控制流和统计口径**，而不是迁移本身。

> 一句话：**看懂"配方 → agent → 门禁 → PR / 分类"的漏斗，以及预算和门禁在代码里是怎样（以及在哪里没有）被执行的**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `FAILURE_CLASSES` | 常量列表 | 7 个失败类别名（只作文档，代码中未引用） | 失败分类法 |
| `Repo` | dataclass | 名字、行数、语言、难度 `hardness ∈ [0,1]` | 被迁移的仓库 |
| `Attempt` | dataclass | 一次迁移尝试的全部状态：配方数、轮数、花费、耗时、状态、失败类、覆盖率 | 迁移记录 / trace |
| `run_recipes` | 函数 | 按行数和难度算出"应用了多少条改写" | 确定性底座 |
| `BUDGET_MIN/USD/TURNS` | 常量 | 30 分钟、8 美元、20 轮 | 硬预算 |
| `agent_loop` | 函数 | 每轮累加耗时与花费，按概率判定通过，通过后检查覆盖率 | agent 循环 + 门禁 |
| `classify_failure` | 函数 | 按权重随机抽一个失败类别 | 失败分类器替身 |
| `migrate` | 函数 | 配方 → 随机"直通" → agent 循环 → 重新分类 | 单仓流水线 |
| `synth_bench` | 函数 | 生成 50 个随机仓库 | MigrationBench 替身 |
| `main` | 函数 | 跑 50 仓，打印通过率、失败分类、通过集指标 | 报告 |

数据流：`random.Random(19)` → `synth_bench` 生成 50 个 `Repo` → 对每个仓库 `migrate`（`run_recipes` → 直通判定 → `agent_loop` → `classify_failure`）→ 汇总 `Attempt` 列表 → 打印。

---

## 3. 逐段精讲

### 3.1 数据模型：`Repo` 与 `Attempt`

```python
@dataclass
class Repo:
    name: str
    loc: int
    lang: str          # "java" | "python"
    hardness: float    # 0..1


@dataclass
class Attempt:
    repo: Repo
    recipe_applied: int = 0
    agent_turns: int = 0
    cost_usd: float = 0.0
    wall_min: float = 0.0
    status: str = "pending"  # "pass" | "fail"
    failure_class: str | None = None
    coverage_base: float = 80.0
    coverage_final: float = 80.0
```

- `Attempt` 就是讲义说的"每个仓库的 trace bundle"的骨架：记录花了多少轮、多少钱、多少时间、结果和原因。
- `str | None`：联合类型注解，表示"可能是字符串，也可能是 None"（成功的仓库没有失败类别）。
- 覆盖率基线固定 80.0，所有仓库都一样。
- `hardness` 是整个模拟的"上帝变量"：它决定配方数、直通概率、每轮成本和每轮通过概率。`lang` 只出现在名字里，不影响任何逻辑；`loc` 只影响配方数。
- `from dataclasses import dataclass, field` 中的 `field` 没有被使用。

### 3.2 确定性配方：`run_recipes`

```python
def run_recipes(repo: Repo) -> int:
    """Returns number of rewrites applied."""
    base = 20 + int(repo.loc / 500)
    return int(base * (1 - 0.2 * repo.hardness))
```

- 每 500 行代码多一条改写，越难的仓库配方命中越少（最多少 20%）。例：`repo-00-python`（34,321 行，h ≈ 0.70）→ `base = 20 + 68 = 88` → `int(88 × 0.86) = 75`。
- ⚠️ 返回值只被存进 `attempt.recipe_applied`，**从未影响结果，也没有打印**。讲义评分表中"配方处理 vs agent 编写的修复比例"占 20 分，但这份代码无法回答它。
- 真实的配方层会产出一个 "recipe" commit（讲义 Build It 第 1 步），并能单独跑一遍构建，形成"纯确定性基线"。

### 3.3 预算常量与 `agent_loop`

```python
BUDGET_MIN = 30.0
BUDGET_USD = 8.0
BUDGET_TURNS = 20


def agent_loop(attempt: Attempt, rng: random.Random) -> None:
    per_turn_min = 2.8 + attempt.repo.hardness * 2.0
    per_turn_usd = 0.45 + attempt.repo.hardness * 0.65
    turn_pass_p = max(0.02, 0.22 * (1 - attempt.repo.hardness * 0.95))

    while True:
        if attempt.agent_turns >= BUDGET_TURNS:
            attempt.status = "fail"
            attempt.failure_class = "budget_exhausted"
            return
        if attempt.wall_min >= BUDGET_MIN or attempt.cost_usd >= BUDGET_USD:
            attempt.status = "fail"
            attempt.failure_class = "budget_exhausted"
            return

        attempt.agent_turns += 1
        attempt.wall_min += per_turn_min
        attempt.cost_usd += per_turn_usd

        if rng.random() < turn_pass_p:
            delta = rng.gauss(0.0, 0.6)
            attempt.coverage_final = attempt.coverage_base + delta
            if attempt.coverage_final < attempt.coverage_base - 2.0:
                attempt.status = "fail"
                attempt.failure_class = "coverage_regression"
                return
            attempt.status = "pass"
            return
```

- 函数返回 `None`，**原地修改** `attempt`（dataclass 是可变对象，按引用传递）。
- 每轮的"耗时、花费、成功概率"都是 hardness 的线性函数。几个具体值（已用 Python 计算）：

| hardness | 每轮分钟 | 每轮美元 | 每轮通过概率 | 时间预算允许的最大轮数 | 预算内通过的概率 |
|---|---|---|---|---|---|
| 0.05 | 2.90 | 0.48 | 0.210 | 11 | 0.925 |
| 0.50 | 3.80 | 0.78 | 0.116 | 8 | 0.625 |
| 0.65 | 4.10 | 0.87 | 0.084 | 8 | 0.505 |
| 0.95 | 4.70 | 1.07 | 0.021 | 7 | 0.141 |

- 每轮通过是独立伯努利试验，所以"预算内通过概率" = `1 − (1 − p)^最大轮数`。这是一个几何分布模型：agent 每轮都像重新掷骰子，没有"从上一轮失败中学习"。
- ⚠️ **预算在每轮开始前检查**，条件是"已用 ≥ 上限"。29 分钟时仍会再跑一整轮，于是最终耗时会超过 30 分钟。种子 19 中 20 个失败仓库全部超时，另有 `repo-07-java` 在第 8 轮通过、累计 33.9 分钟，却被记为通过。讲义把它们称为 "Hard limits"。
- ⚠️ **20 轮与 8 美元上限永远不会触发**：hardness 被 `synth_bench` 限制在 [0.05, 0.95]，每轮至少 2.9 分钟，时间预算最多允许 11 轮；在全范围内停止时花费最多 7.47 美元。所以所有 `budget_exhausted` 都是时间预算触发的。
- ⚠️ 注释写"(0.02-0.18)"，实际范围约 0.021–0.210。
- 覆盖率门禁：`delta ~ N(0, 0.6)`，低于基线 2.0 个百分点才失败，概率 `Φ(−3.33) ≈ 0.04%`。在 10,000 个模拟仓库中只出现 2 次。讲义 Concept 说"coverage delta is not negative"，Build It 说"dropped more than 2%"——讲义自身不一致，代码用的是"2 个百分点"。

### 3.4 失败分类：`classify_failure`

```python
def classify_failure(rng: random.Random) -> str:
    weights = {
        "dep_upgrade_required": 0.30,
        "build_tool_drift": 0.20,
        "custom_annotation": 0.18,
        "test_flake": 0.15,
        "syntax_edge_case": 0.17,
    }
    r = rng.random()
    acc = 0.0
    for cls, w in weights.items():
        acc += w
        if r <= acc:
            return cls
    return "syntax_edge_case"
```

- 这是**轮盘赌采样**（roulette-wheel sampling）：把 [0,1) 按权重切成区间，看随机数落在哪一段。权重之和恰好为 1.0。
- 最后的 `return "syntax_edge_case"` 是兜底：浮点累加可能出现 `0.9999999...`，随机数又恰好比它大时，循环不会返回。
- 标准库有现成的写法：`rng.choices(list(weights), weights=list(weights.values()))[0]`。
- ⚠️ 分类器**不看任何输入**：与仓库语言、规模、日志都无关。失败分类法的分布只是这组权重的抽样结果，不能用来指导"下一个配方该写什么"。
- ⚠️ 讲义 Use It 中出现的 `removed_jdk_api` 类别既不在这里，也不在 `FAILURE_CLASSES`、也不在讲义 Build It 第 7 步的列表中。

### 3.5 单仓流水线：`migrate`

```python
def migrate(repo: Repo, rng: random.Random) -> Attempt:
    attempt = Attempt(repo=repo)
    attempt.recipe_applied = run_recipes(repo)

    straight_through_p = 0.55 * (1 - repo.hardness)
    if rng.random() < straight_through_p:
        delta = rng.gauss(0.0, 0.4)
        attempt.coverage_final = attempt.coverage_base + delta
        attempt.status = "pass"
        attempt.wall_min = 3.0 + rng.random() * 4
        attempt.cost_usd = 0.30
        return attempt

    agent_loop(attempt, rng)

    if attempt.status == "fail" and attempt.failure_class == "budget_exhausted":
        if rng.random() < 0.75:
            attempt.failure_class = classify_failure(rng)
    return attempt
```

- **直通路径**模拟"配方跑完、构建就绿了"：耗时 3–7 分钟、固定 0.30 美元、`agent_turns = 0`。种子 19 中 30 个通过仓库里有 11 个走直通，相当于纯确定性基线 22%。
- ⚠️ 直通路径算了覆盖率 `delta`，但**没有门禁**，直接 `status = "pass"`。种子 19 的 30 个通过仓库中 14 个覆盖率低于基线（delta < 0）。
- **重新分类**：预算耗尽的仓库有 75% 被改成某个"根因"类别，25% 保持 `budget_exhausted`。这模拟了讲义的"每个失败仓库要有一个根因标签"，但根因是随机抽的。
- ⚠️ 所有仓库共用一个 `rng`：agent 循环消耗的随机数个数会影响后面仓库的直通判定。要做"有 agent vs 无 agent"的公平对比，应给每个仓库独立的随机数流。

### 3.6 合成基准：`synth_bench`

```python
def synth_bench(rng: random.Random) -> list[Repo]:
    bench: list[Repo] = []
    for i in range(50):
        lang = "java" if rng.random() < 0.6 else "python"
        hardness = min(0.95, max(0.05, rng.gauss(0.65, 0.18)))
        bench.append(Repo(name=f"repo-{i:02d}-{lang}",
                          loc=rng.randint(800, 40_000),
                          lang=lang,
                          hardness=hardness))
    return bench
```

- 60% Java、40% Python（种子 19 实际 34 个 Java）。
- 难度服从均值 0.65、标准差 0.18 的正态分布，再用 `min(max(...))` **截断**到 [0.05, 0.95]（clamp 写法）。种子 19 的实际均值 0.635，范围 0.22–0.95。
- `f"repo-{i:02d}-{lang}"`：`02d` 表示补零到两位，生成 `repo-07-java`。

### 3.7 `main`：汇总与报告

```python
    passed = [a for a in results if a.status == "pass"]
    failed = [a for a in results if a.status == "fail"]
    ...
    taxonomy: dict[str, int] = {}
    for a in failed:
        taxonomy[a.failure_class or "unknown"] = taxonomy.get(a.failure_class or "unknown", 0) + 1
    for cls, n in sorted(taxonomy.items(), key=lambda x: -x[1]):
        print(f"  {cls:24s} {n}")
```

- `a.failure_class or "unknown"`：`or` 返回第一个"真值"，None 时用 "unknown"。这里等价于 `collections.Counter(a.failure_class or "unknown" for a in failed)`。
- 按数量降序打印；数量相同的类别保持插入顺序（`sorted` 稳定）。
- 通过集指标是**混合平均**：直通仓库（0 轮、0.30 美元）拉低了 `mean $/repo` 和 `mean agent turns`。
- `len(passed) / 50` 把 50 写死；`print(f"=== migration-bench run (50 repos) ===")` 是不含占位符的 f-string。
- 讲义要求的"与纯确定性基线对比""每类通过率"在这里都没有输出。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 hardness 一个变量驱动所有概率 | 模型简单，能产生"难的仓库更贵、更容易失败"的直觉 | 真实失败由具体错误决定；应记录真实构建日志与每轮动作 |
| 每轮独立伯努利通过 | 易于分析（几何分布） | 真实 agent 会从失败中学习，也会陷入循环；需要按轮记录状态 |
| 预算在轮首检查 | 写法最直观 | 最后一轮会超支；生产要预检 + 命令超时 + `max_tokens` 上限 |
| 三个预算常量 | 对应讲义的 30 分钟 / 8 美元 / 20 轮 | 在当前参数下只有时间预算生效；应测试每个预算都可被触发 |
| 覆盖率门禁用 −2.0 个百分点 | 容忍测量噪声 | 几乎永远不触发；直通路径完全跳过门禁 |
| 随机抽样的失败分类 | 无需日志即可产生分类表 | 分类法没有信息量；生产用"规则 + LLM"基于日志分类并人工抽检 |
| 单一共享 `rng` | 一个种子即可复现整次运行 | 无法做配对对比；应按仓库派生独立随机流 |
| 只打印混合平均 | 输出简洁 | 掩盖了 agent 的真实单价；应分组报告直通 / agent |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许在旧版本 Python 中使用 `str | None` 等新注解写法 |
| `@dataclass` + 默认值 | `recipe_applied: int = 0` | 有默认值的字段必须放在无默认值字段之后 |
| 联合类型 | `failure_class: str | None = None` | 等价于 `Optional[str]` |
| 模块级常量 | `BUDGET_MIN = 30.0` | 全大写命名约定表示常量（Python 不强制） |
| `random.Random(seed)` | `rng = random.Random(19)` | 独立的随机数生成器实例，不影响全局 `random` |
| `rng.random()` / `rng.gauss()` / `rng.randint()` | `rng.gauss(0.0, 0.6)`、`rng.randint(800, 40_000)` | [0,1) 均匀、正态、闭区间整数 |
| `while True` + `return` | `agent_loop` | 无限循环，由内部条件 `return` 退出 |
| 原地修改对象 | `attempt.agent_turns += 1` | 函数修改传入的可变对象，调用方可见 |
| 复合赋值 | `acc += w`、`attempt.wall_min += per_turn_min` | `x = x + y` 的简写 |
| `max` / `min` 截断 | `min(0.95, max(0.05, x))` | 把值限制在区间内（clamp） |
| `dict.items()` 遍历 | `for cls, w in weights.items()` | 同时取键和值；dict 保持插入顺序（3.7+） |
| 条件表达式 | `"java" if rng.random() < 0.6 else "python"` | 三元运算 |
| 列表推导式过滤 | `[a for a in results if a.status == "pass"]` | 按条件筛选 |
| `or` 提供默认值 | `a.failure_class or "unknown"` | 左侧为 None/空时取右侧 |
| `sorted` + `lambda` | `sorted(taxonomy.items(), key=lambda x: -x[1])` | 按计数降序 |
| 生成器求和 | `sum(a.cost_usd for a in passed) / len(passed)` | 求平均 |
| f-string 格式符 | `{len(passed):2d}`、`{x:.1%}`、`{mean_cost:.2f}`、`{d:+.2f}`、`{i:02d}`、`{cls:24s}` | 宽度、百分比、小数位、显示正负号、补零、左对齐 |
| 数字下划线 | `40_000` | 便于阅读的数字字面量 |
| `if __name__ == "__main__":` | 文件结尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，固定种子 19，瞬间完成）：

```text
=== migration-bench run (50 repos) ===
passed : 30  (60.0%)
failed : 20

failure taxonomy:
  budget_exhausted         6
  build_tool_drift         5
  dep_upgrade_required     4
  syntax_edge_case         3
  test_flake               1
  custom_annotation        1

pass-set metrics:
  mean $/repo     : $2.33
  mean wall min   : 12.3
  mean agent turns: 2.6
  mean cov delta  : +0.03 points
```

逐项解读（拆分数据来自额外的实测脚本）：

- **通过 30 / 50 = 60%**：其中 11 个配方直通（纯确定性基线 22%），19 个由 agent 救回。200 个不同种子的平均通过率为 56.5%，范围 30%–76%——50 个样本的通过率波动很大，p ≈ 0.6 时 95% 置信区间约 ±13.6 个百分点。
- **失败 20 个，全部由时间预算触发**：最大轮数 9、失败仓库最大花费 7.47 美元，20 轮和 8 美元的上限都没有起作用。其中 75% 左右被随机改标为"根因"，剩下 6 个保留 `budget_exhausted`。
- **没有 `coverage_regression`**：门禁概率约 0.04%，不出现是正常的。
- **`mean $/repo $2.33`**：= (11 × 0.30 + 19 × 3.51) / 30。只看 agent 修复的 19 个仓库，平均 3.51 美元、4.1 轮。讲义 Use It 的示例是 3.20 美元、4 轮，量级一致。
- **`mean wall min 12.3`**：包含 `repo-07-java` 的 33.9 分钟——一个超过"硬上限"仍被计为通过的仓库。
- **`mean cov delta +0.03`**：平均接近 0，但 30 个通过仓库中 14 个是负值；平均值掩盖了个体回归。

---

## 7. 动手改一改

1. **修复超支**：把预算检查改成"再跑一轮是否会超限"（见测验 Q9），确认所有仓库的 `wall_min ≤ 30`，并观察通过率下降多少。
2. **让三个预算都可能生效**：把 `BUDGET_MIN` 改成 60，重跑并统计每个仓库因哪个预算停止（给 `Attempt` 加一个 `stop_reason` 字段）。
3. **纯确定性基线**（讲义练习 1）：给 `migrate` 加 `deterministic_only` 参数，并为每个仓库使用 `random.Random(f"{seed}-{repo.name}")` 派生的独立随机流，输出两种模式在同一批仓库上的对比表和"agent 救回了哪些仓库"。
4. **统一覆盖率门禁**：把门禁抽成函数 `coverage_gate(base, final, tol)`，直通和 agent 两条路径都调用；分别用 `tol = 0`、`0.5`、`2.0` 跑，观察通过率变化。
5. **基于日志的分类器**：为每个失败仓库合成一段假构建日志（按 hardness 选择模板），实现 `classify_from_log`（参考测验 Q11），比较与随机分类的分布差异。
6. **进阶**（讲义练习 5）：记录"首次构建变绿时间（TTFGB）"，输出 p50/p90，判断是否达到讲义"p50 under 10 minutes"的目标。

---

## 8. 常见坑

- **预算"事后检查"**：在轮首检查"已用 ≥ 上限"会让最后一轮超支；硬上限需要预检或超时强杀。
- **设了但从不触发的预算**：参数组合让 20 轮和 8 美元永远到不了，给人"有保护"的错觉；要用测试证明每个预算都能被触发。
- **混合平均**：直通仓库让平均成本和平均轮数看起来很低，应分组报告。
- **覆盖率阈值的口径**：2% 是相对值还是 2 个百分点？讲义两处说法也不一致，必须在代码和报告里写清楚。
- **门禁只在一条路径上**：直通路径跳过覆盖率检查，等于给最容易的仓库开了后门。
- **随机分类当结论**：失败分类法的价值来自真实日志；随机抽样得到的"Top 3"不能指导配方开发。
- **共享随机数流做 A/B**：一个分支多消耗几个随机数，就会改变后续所有仓库的结果，两组不再可比。
- **小样本下下结论**：50 个仓库的通过率误差约 ±14 个百分点，"60% vs 55%"不一定是真实差异。
