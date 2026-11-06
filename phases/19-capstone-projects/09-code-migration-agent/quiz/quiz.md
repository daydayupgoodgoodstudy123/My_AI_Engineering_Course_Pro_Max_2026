# 测验 · 代码迁移 Agent——仓库级语言与运行时升级（Code Migration Agent (Repo-Level Language / Runtime Upgrade)）

> **阶段 19 · 综合项目 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：`code/ts/` 下另有一个 TypeScript 的迁移看板骨架（文件级状态机 + 预算计费），本测验以 Python 的 `main.py` 为主。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两层结构 | **确定性底座**（OpenRewrite / libcst，AST 级改写，快、可审计、安全）先跑，**agent 层**只处理配方处理不了的歧义情况 |
| 2 | 配方覆盖大头 | 讲义架构图：确定性配方约处理 70–80% 的修复（imports、方法签名、try-with-resources、废弃 API 替换） |
| 3 | agent 处理长尾 | 构建文件升级（Maven/Gradle/pyproject）、传递依赖冲突、测试 flake、自定义注解、长尾语法 |
| 4 | 每仓一个沙箱 | Daytona 沙箱预装目标运行时（Java 17 / Python 3.12），agent 循环：跑构建 → 分类失败 → 修复 → 重跑 |
| 5 | 硬预算 | 每个仓库 30 分钟、8 美元、20 轮 agent turn；任一超限即停止，归入 `budget_exhausted` 并附当前 diff |
| 6 | 测试 + 覆盖率门禁 | 构建变绿后跑测试，与基线比较覆盖率；讲义 Build It：覆盖率下降超过 2% 归入 `coverage_regression` |
| 7 | 失败分类法是交付物 | `dep_upgrade_required`、`build_tool_drift`、`custom_annotation`、`test_flake`、`syntax_edge_case`、`budget_exhausted`；每类给计数和示例 diff |
| 8 | 与纯确定性基线对比 | 讲义："side-by-side against a deterministic-only baseline tells you where the agent's value actually lives" |
| 9 | 评分表 | MigrationBench pass@1 25 + 覆盖率保持 20 + 每仓成本 20 + 配方/agent 协作比例 20 + 失败分析 15 |
| 10 | 基准 | Amazon MigrationBench 50 仓子集（Java 8→17）、Google App Engine Py2→Py3 |

### 核心技能（能动手做到）

- [ ] 解释为什么先跑确定性配方、再让 agent 处理剩余失败，而不是全部交给 agent
- [ ] 读懂 `agent_loop` 的预算检查，并指出"预算是在每轮**开始前**检查的"导致的超支问题
- [ ] 根据 `per_turn_min`、`per_turn_usd` 公式算出：在 hardness ∈ [0.05, 0.95] 范围内哪一个预算真正起作用
- [ ] 从模拟结果中拆出"配方直通"与"agent 修复"两部分，得到纯确定性基线的通过率
- [ ] 计算 50 仓基准通过率的置信区间，说明为什么单次 50 仓结果波动很大
- [ ] 设计一个基于构建日志的真实失败分类器，替换随机抽样的 `classify_failure`

---

## 二、基础自测（选择题）

**Q1.** 讲义中"确定性底座（deterministic substrate）"指的是：

- A. 用固定随机种子运行 LLM，使 agent 输出可复现
- B. OpenRewrite（Java）/ libcst（Python）这类声明式 AST 改写工具，快速、可审计、有安全保证
- C. 把仓库所有代码都交给 LLM 重写，再用测试兜底
- D. Daytona 沙箱的镜像缓存

**Q2.** 为什么讲义坚持"先跑配方、再跑 agent"？

- A. agent 无法读取 Java 文件
- B. 配方的成本比 agent 高，必须先付费
- C. 配方能处理所有情况，agent 只是备份
- D. 机械性改写占大头（约 70–80%），确定性配方快、便宜、diff 可审计；把有限的 agent 预算留给配方处理不了的歧义情况

**Q3.** 运行 `python main.py`（种子 19），输出的通过率与失败类别中数量最多的一类分别是：

- A. 60.0%；`budget_exhausted`（6 个）
- B. 56.5%；`dep_upgrade_required`
- C. 60.0%；`build_tool_drift`（6 个）
- D. 76.0%；`test_flake`

**Q4.** 在本节代码中，hardness 被限定在 [0.05, 0.95]，每轮耗时 `2.8 + 2.0h` 分钟、花费 `0.45 + 0.65h` 美元，预算为 30 分钟、8 美元、20 轮。实际起作用（会触发停止）的是哪一个预算？

- A. 20 轮上限
- B. 8 美元上限
- C. 30 分钟上限（最多 11 轮就会耗尽，花费最多约 7.47 美元）
- D. 三者都会在不同 hardness 下触发

**Q5.** 关于覆盖率门禁，讲义与代码的说法中，哪一项描述是准确的？

- A. 讲义和代码一致：覆盖率只要下降就失败
- B. 代码用相对 2%（即 80 × 2% = 1.6 个百分点）作为阈值
- C. 配方直通的仓库和 agent 修复的仓库都经过同样的覆盖率检查
- D. 讲义 Concept 写"coverage delta 不为负才开 PR"，Build It 写"下降超过 2% 才归为 coverage_regression"；代码采用"低于基线 2.0 个百分点"，而且配方直通路径根本不检查覆盖率

**Q6.** 讲义 Key Terms 中 "agent turn" 的含义是：

- A. 一次 plan → act → observe 的循环
- B. 一次完整的 50 仓基准运行
- C. 一次 OpenRewrite 配方执行
- D. 一次 PR review

**Q7.** 用 200 个不同随机种子各跑一次 50 仓模拟，通过率的均值约 56.5%，最低 30%、最高 76%。这说明：

- A. 代码有 bug，每次结果应当相同
- B. 50 个样本的 pass rate 本身方差很大（p≈0.6 时 95% 置信区间约 ±13.6 个百分点），比较两个方案时必须考虑统计显著性
- C. 种子越大通过率越高
- D. 只要通过率超过 50% 就可以上线

**Q8.** 种子 19 的运行中，`repo-07-java` 在第 8 轮通过，累计耗时 33.9 分钟。关于这个结果，正确的是：

- A. 它被归入 `budget_exhausted`
- B. 33.9 分钟不可能出现，因为代码在 30 分钟时会强制停止
- C. 它被记为通过，但实际超过了 30 分钟的"硬"上限——因为预算检查发生在每轮开始之前，最后一轮可以把总时长推过上限
- D. 它被归入 `coverage_regression`

---

## 三、动手 / 代码题

**Q9.** 阅读 `agent_loop`：

```python
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
            ...
```

1. 为什么种子 19 的结果里会有 21 个仓库累计耗时超过 30 分钟（20 个失败 + 1 个通过）？
2. 改写预算检查，使任何一轮都不会让耗时或花费超过上限（提示：在执行一轮**之前**检查"再执行一轮是否会超限"）。
3. 注释写"probability of passing per turn depends on hardness (0.02-0.18)"，请用公式 `max(0.02, 0.22 * (1 - h * 0.95))` 算出 h = 0.05 和 h = 0.95 时的实际值，判断注释是否准确。

**Q10.** 讲义要求与"纯确定性基线"对比。种子 19 的 30 个通过仓库中，有 11 个 `agent_turns == 0`（配方直通），19 个经过 agent 修复。

1. 纯确定性基线的通过率是多少？agent 带来了多少增量？
2. 配方直通的仓库 `cost_usd` 固定为 0.30 美元。若只看 agent 修复的 19 个仓库，平均花费为 3.51 美元、平均 4.1 轮。为什么讲义的"每仓成本"评分应该分开报告这两组？
3. 在代码里加一个开关 `deterministic_only=True`，让 `migrate` 跳过 agent 循环，并输出两种模式的对比表。写出关键改动。

**Q11.** `classify_failure` 的实现如下：

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

1. 这个"分类器"的输入是什么？它与仓库本身（语言、规模、构建日志）有关系吗？
2. 在 `migrate` 中，`budget_exhausted` 的仓库有 75% 被重新分类。这意味着失败分类法里的数字反映的是什么？
3. 讲义 Use It 中的构建日志是 `FAIL: cannot find symbol sun.misc.BASE64Encoder`，agent 分类为 `removed_jdk_api`。这个类别在代码的 `FAILURE_CLASSES` 里吗？写一个基于正则规则的 `classify_from_log(log: str) -> str`，至少覆盖 4 类。

**Q12.** 估算"覆盖率回归"真正被触发的概率。agent 修复成功时 `delta ~ N(0, 0.6)`，阈值为 −2.0；配方直通时 `delta ~ N(0, 0.4)` 且不检查。

1. 计算 agent 路径触发 `coverage_regression` 的概率。
2. 在 200 个种子 × 50 仓 = 10,000 个仓库的模拟中，实际只出现了 2 次 `coverage_regression`。这与第 1 问的结果是否吻合？
3. 种子 19 的 30 个通过仓库里，有 14 个覆盖率低于基线（delta < 0），但全部被判为通过。按讲义 Concept 的标准（"coverage delta is not negative"），应该有几个开 PR？这说明了什么？

---

## 四、面试高频题

**Q13.**（基础必考）设计一个把 Java 8 服务批量升级到 Java 17 的 agent 系统，说明整体架构、每一层的职责和退出条件。

**Q14.**（原理深挖）为什么不把整个迁移都交给 LLM agent？确定性 AST 改写与 LLM 改写在正确性、可审计性、成本上各有什么特点？

**Q15.**（工程实践）agent 的预算（时间、金钱、轮数）应该怎么设计和执行？如何避免"最后一轮超支"和"预算看起来设了但从不生效"？

**Q16.**（场景设计）你跑完 50 个仓库，通过率 60%。老板问"agent 值不值得"，以及"下一步该投资什么"。你怎么用数据回答？

**Q17.**（追问型）迁移后测试全部通过、覆盖率也没降，就一定说明迁移正确吗？还有哪些风险，怎么补充验证？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义 Key Terms："Deterministic substrate — OpenRewrite / libcst: declarative AST rewrites with safety guarantees"。A 混淆了"确定性"的含义；C 正是讲义要避免的做法；D 是沙箱层，与改写无关。

### Q2 — 答案：D

讲义 Concept："The deterministic substrate ... runs the bulk of mechanical rewrites safely ... It is fast and produces auditable diffs. The agent layer handles cases the recipes cannot"。架构图标注配方约处理 70–80% 的修复。A 错，agent 有 `read_file`、`edit_file` 等工具；B 说反了，配方几乎免费；C 错，配方处理不了构建漂移、传递依赖、自定义注解等。

### Q3 — 答案：A

实际输出：`passed : 30  (60.0%)`，失败分类按数量降序为 `budget_exhausted 6`、`build_tool_drift 5`、`dep_upgrade_required 4`、`syntax_edge_case 3`、`test_flake 1`、`custom_annotation 1`。B 中 56.5% 是 200 个种子的平均通过率，不是这次运行的结果；C 数量写错；D 中 76% 是 200 个种子中的最高值。

### Q4 — 答案：C

用 Python 对 hardness 在 [0.05, 0.95] 上逐点模拟预算检查：
- 每轮耗时至少 2.9 分钟（h = 0.05），30 分钟预算最多允许 11 轮（10 轮后 29.0 < 30，还会再跑第 11 轮）；
- h = 0.95 时每轮 4.7 分钟、1.0675 美元，第 7 轮后 32.9 分钟、7.47 美元——停止时花费仍不到 8 美元；
- 全范围内，停止时的最大花费是 7.47 美元，最大轮数是 11。

所以 20 轮上限和 8 美元上限**永远不会触发**，`budget_exhausted` 全部由时间预算导致。种子 19 的实测也印证了这一点：最大轮数 9、失败仓库最大花费 7.47 美元。这类"设了但永远不生效"的配置很危险——一旦参数调整，你可能误以为有保护。

### Q5 — 答案：D

讲义自身就有两种说法：Concept "If all tests pass and the coverage delta is not negative, the branch opens a PR"；Build It "If coverage dropped more than 2%, file under coverage_regression"。代码 `attempt.coverage_final < attempt.coverage_base - 2.0` 是 2.0 个**百分点**（绝对值），不是相对 2%，所以 B 错。配方直通路径只是算了 `delta` 就直接 `status = "pass"`，没有门禁，C 错。

### Q6 — 答案：A

讲义 Key Terms："Agent turn — One plan -> act -> observe cycle in the agent loop"。代码中每轮 `agent_turns += 1` 并按 hardness 累加时间和花费。

### Q7 — 答案：B

50 个仓库的 pass rate 是二项比例。p ≈ 0.6 时标准误 `√(0.6×0.4/50) ≈ 0.069`，95% 置信区间约 ±13.6 个百分点（已计算）。200 个种子的结果 30%–76% 正是这种抽样波动（同时还有 hardness 分布的随机性）。A 错：不同种子本来就生成不同的仓库和随机事件；C、D 无依据。面试要点：对比"纯配方 vs 配方 + agent"时，应在**同一批仓库**上做配对比较，而不是比较两次独立的 50 仓运行。

### Q8 — 答案：C

种子 19 的实测：`('repo-07-java', 33.9, 8)`。第 7 轮结束时累计约 29.7 分钟，仍小于 30，于是允许执行第 8 轮；第 8 轮通过，总时长 33.9 分钟。讲义把 30 分钟称为 "Hard limits"，代码并没有硬性执行。A、D 错：它的 status 是 pass；B 错：检查只在每轮开始前做。

### Q9 — 参考答案

1. 检查发生在每轮**开始前**，条件是"已用 ≥ 上限"。只要已用时间是 29.x 分钟，就会再跑一整轮（2.9–4.7 分钟），结束后必然超过 30。20 个失败仓库全部是时间预算触发，所以每个都超了；再加上 `repo-07-java` 这个在最后一轮通过的仓库，共 21 个。
2. 改写：

```python
    while True:
        would_exceed = (
            attempt.agent_turns + 1 > BUDGET_TURNS
            or attempt.wall_min + per_turn_min > BUDGET_MIN
            or attempt.cost_usd + per_turn_usd > BUDGET_USD
        )
        if would_exceed:
            attempt.status = "fail"
            attempt.failure_class = "budget_exhausted"
            return
        attempt.agent_turns += 1
        attempt.wall_min += per_turn_min
        attempt.cost_usd += per_turn_usd
        ...
```

   真实系统中每轮的耗时和花费事先未知，做法是：按"上一轮实际消耗"或"最坏情况估计"预检；对 LLM 调用设置 `max_tokens` 上限保证单轮成本有界；对构建/测试命令设置超时（`subprocess.run(..., timeout=剩余时间)`），超时即强杀。
3. h = 0.05：`0.22 × (1 − 0.0475) ≈ 0.2096`；h = 0.95：`0.22 × (1 − 0.9025) ≈ 0.0215`。实际范围约 0.021–0.21，注释写的 0.02–0.18 上界不准（0.18 大约对应 h ≈ 0.19）。

### Q10 — 参考答案

1. 纯确定性基线：11/50 = 22%；完整流水线 30/50 = 60%；agent 贡献了 19 个仓库、38 个百分点。（注意这里的"直通"在代码中只依赖 `0.55 × (1 − hardness)` 的随机概率，是模拟出来的；真实对比要实际跑一遍"只有配方"的流水线，即讲义练习 1。）
2. 输出的 `mean $/repo: $2.33` 是两组混合后的平均：11 个 0.30 美元 + 19 个平均 3.51 美元。直通仓库拉低了平均成本，会掩盖 agent 的真实单价。讲义评分表里的"Agent / deterministic-tool integration"本身就要求报告"配方处理 vs agent 编写"的比例；分开报告才能回答"每多救活一个仓库要花多少钱"。
3. 关键改动：

```python
def migrate(repo, rng, deterministic_only=False):
    attempt = Attempt(repo=repo)
    attempt.recipe_applied = run_recipes(repo)
    straight_through_p = 0.55 * (1 - repo.hardness)
    if rng.random() < straight_through_p:
        ...                      # 与原代码相同
        return attempt
    if deterministic_only:
        attempt.status = "fail"
        attempt.failure_class = "needs_agent"
        return attempt
    agent_loop(attempt, rng)
    ...
```

   对比时要让两种模式使用**同一份仓库列表**，并为每个仓库使用独立的、由仓库名派生的随机数流（例如 `random.Random(hash((seed, repo.name)))`），否则 agent 循环消耗的随机数会让后续仓库的"直通"判定也发生变化，两组结果不可比。

### Q11 — 参考答案

1. 输入只有随机数生成器。它与仓库的语言、规模、hardness、构建日志都无关，只是按固定权重抽样。docstring 也说明了："Stand-in for the agent's failure classifier. Real implementation reads build logs and test output."
2. 失败分类法的分布基本就是这组权重（30/20/18/15/17%）加 25% 留在 `budget_exhausted`。也就是说，示例输出里"build_tool_drift 5、dep_upgrade_required 4"是**随机数的产物**，不是迁移规律。讲义说"Future recipe authors can target the top three"——如果分类本身不可信，就会把配方开发资源投错方向。
3. `removed_jdk_api` 不在 `FAILURE_CLASSES` 里，讲义 Use It 与讲义 Build It 第 7 步的类别列表、与代码三者不一致（这类错误更接近 `syntax_edge_case` 或 `dep_upgrade_required`，但应当单独成类，因为它有明确的配方可写）。基于规则的分类器示意：

```python
import re

RULES = [
    ("removed_jdk_api",      r"cannot find symbol.*(sun\.misc|javax\.xml\.bind|javax\.annotation)"),
    ("dep_upgrade_required", r"(Could not resolve dependencies|NoSuchMethodError|ClassNotFoundException)"),
    ("build_tool_drift",     r"(Unsupported class file major version|Could not find method .* for arguments|plugin .* not compatible)"),
    ("custom_annotation",    r"annotation processor|@[A-Z]\w+.*not applicable"),
    ("test_flake",           r"(Timeout|Connection refused|flaky)"),
    ("syntax_edge_case",     r"(illegal start of|SyntaxError|invalid syntax)"),
]

def classify_from_log(log: str) -> str:
    for cls, pat in RULES:
        if re.search(pat, log, re.IGNORECASE):
            return cls
    return "unclassified"

print(classify_from_log("FAIL: cannot find symbol sun.misc.BASE64Encoder"))  # removed_jdk_api
```

   规则无法覆盖时再交给 LLM 分类，并把 LLM 的分类结果和日志片段一起存档，便于人工抽查。`test_flake` 的判定应以"重跑基线分支也失败/时好时坏"为准，而不是只看日志关键词。

### Q12 — 参考答案

1. `P(delta < −2.0) = Φ(−2.0 / 0.6) = Φ(−3.33) ≈ 0.00043`，约 0.04%（已用 Python 计算）。配方直通时即使检查，`Φ(−2.0 / 0.4) = Φ(−5) ≈ 2.9×10⁻⁷`。
2. 吻合。10,000 个仓库中走 agent 且成功的大约有几千个，乘以 0.043% 约为 1–2 次，实测 2 次。也就是说 `coverage_regression` 这一类在模拟里几乎是摆设。
3. 按"delta 不能为负"的标准，30 个通过仓库里只有 16 个能开 PR，14 个应被拦下。这说明：阈值的选择直接决定 pass rate；"−2 个百分点"在这里形同虚设，而"不能为负"又会被测量噪声（同一分支重跑覆盖率也会小幅波动）误伤。实践中常用"不低于基线减去一个小容差（如 0.1–0.5 个百分点），并且新增/修改的代码行覆盖率不低于阈值"。

### Q13 — 参考回答要点

- **输入**：仓库 + 目标运行时；在 Daytona 一类的沙箱里预装 JDK 17。
- **第一层：确定性配方**：OpenRewrite 的 Java 8→17 配方（JUnit 4→5、try-with-resources、废弃 API 替换等），作为一个独立的 "recipe" commit，便于审计和回滚。
- **构建试跑**：绿了直接跑测试；红了交给 agent。
- **第二层：agent 循环**：工具 `run_build`、`read_file`、`edit_file`、`run_test`、`git_diff`；每轮 plan → act → observe；先对失败分类（依赖、语法、测试、构建工具），再做定向修复；可以"重试某个配方"作为动作。
- **退出条件**：成功（构建绿 + 测试全过 + 覆盖率门禁）→ 开 PR，附配方清单和 agent commit；失败（预算耗尽 30 分钟 / 8 美元 / 20 轮，或门禁失败）→ 归类 + 附复现信息。
- **观测**：Langfuse trace，每个 diff 块都入档；失败分类看板。
- 加分点：把 agent 成功修复的高频模式沉淀为新配方，逐步把 agent 的工作"下沉"到确定性层。

### Q14 — 参考回答要点

- **确定性 AST 改写**：基于语法树和类型信息，语义保持有保证；同样的输入同样的输出；diff 可预测、可大规模审计；几乎零边际成本；缺点是只能处理事先写好规则的模式，长尾情况写规则不划算。
- **LLM 改写**：能处理模糊、跨文件、需要理解意图的情况（构建脚本、依赖冲突、自定义注解）；但非确定、可能引入细微语义变化、可能"为了让测试通过"而修改测试本身；每仓有实际成本（讲义 Use It 示例 3.20 美元、4 轮）。
- **组合的理由**：让便宜、可靠的工具处理大头，把昂贵、不确定的工具留给长尾；同时纯配方基线让你量化 agent 的真实增量。
- 常见误区：只报告整体通过率，不报告"配方 vs agent"的拆分（讲义评分表专门有 20 分考这个）。

### Q15 — 参考回答要点

- **三种预算互补**：时间（防死循环和慢构建）、金钱（防 token 爆炸）、轮数（防 agent 原地打转）。
- **预检而非事后检查**：在执行一轮前判断"再跑一轮是否会超限"（见 Q9.2）；对单轮成本设上限（`max_tokens`、命令超时），使"最坏一轮"有界。
- **验证预算真的生效**：用参数扫描或属性测试检查每个预算在某些输入下会被触发（Q4 中 20 轮和 8 美元在本代码的参数下从不触发）；在看板上按"哪个预算触发"分别统计。
- **预算耗尽时保留现场**：讲义要求"files under budget_exhausted with the current diff"，便于人工接手或调大预算重跑。
- **失败归因**：预算耗尽只是表象，还要记录卡在哪一类错误上（代码用 75% 概率随机重分类，真实系统应基于最后几轮的日志）。

### Q16 — 参考回答要点

- **拆分增量**：纯配方基线通过率（模拟中 22%）vs 完整流水线（60%）；agent 救回的仓库数、每救回一个仓库的平均成本和时间。与人工迁移成本对比（讲义："a Java-8 fleet migration is a headcount-scale project"）。
- **说明不确定性**：50 仓的 95% 置信区间约 ±14 个百分点；必要时扩大样本或做配对比较。
- **看失败分类法**：按类别计数 + 示例 diff，找出前三大类（讲义："Future recipe authors can target the top three"），评估"为它写配方"vs"给 agent 更多预算"哪个更划算。
- **检查预算的边际收益**：在被时间预算截断的仓库上，放宽到 45 分钟能多救几个？（模拟中所有预算耗尽都是时间触发的。）
- **质量维度**：覆盖率变化、lint 回归（讲义练习 2）、diff 大小（练习 3）、首次构建变绿时间 TTFGB（练习 5，目标 p50 < 10 分钟）。
- 加分点：确认"失败分类"本身可靠（人工抽查一部分），否则投资方向会被误导。

### Q17 — 参考回答要点

- **不一定**。测试通过只说明"被测试覆盖到的行为"没变。风险：
  - 测试本身被 agent 修改或删除（应禁止或单独审查测试文件的 diff）；
  - 覆盖率相同但覆盖的行不同；未覆盖路径上的行为变化（例如 Java 17 中反射访问内部 API 的限制、默认字符集、日期格式化差异）；
  - 性能回归、内存变化（GC 默认值变化）；
  - 依赖升级引入的许可证或安全问题；
  - 运行时配置（JVM 参数、容器镜像）没有同步升级。
- **补充验证**：对比迁移前后测试列表（测试数不能减少，讲义 Use It 示例 412/412）；diff 级别的 mutation testing；在预发环境用影子流量对比新旧版本的输出；静态分析和 lint（讲义练习 2）；"最小 diff"优化（练习 3）降低审查负担；PR 由人工审查后再合并。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：agent turn 的基本循环。
- [阶段 14 · 38 Verification Gates](../../../14-agent-engineering/38-verification-gates/docs/zh.md)：测试 + 覆盖率门禁的设计。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：时间、金钱、轮数预算。
- [阶段 13 · 01 工具接口](../../../13-tools-and-protocols/01-the-tool-interface/docs/zh.md)：`run_build`、`edit_file` 等工具的接口设计。
- [阶段 15 · 09 自主 Coding Agent 生态概览（2026）](../../../15-autonomous-systems/09-coding-agent-landscape/docs/zh.md)：coding agent 的整体格局。

### 本节被哪些后续内容用到
- [阶段 19 · 16 从 GitHub Issue 到 PR 的自主 Agent](../../16-github-issue-to-pr-agent/docs/zh.md)：同样以"测试变绿后开 PR"为目标。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：沙箱执行层的实现。
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：门禁与预算的工程化。
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../27-eval-harness-fixture-tasks/docs/zh.md)：用固定任务集评估 agent。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../../14-agent-engineering/19-benchmarks-swebench-gaia/docs/zh.md)：与 MigrationBench 类似的代码 agent 基准。

### 延伸关键词
`OpenRewrite` · `libcst` · `codemod` · `AST rewrite` · `MigrationBench` · `Daytona sandbox` · `failure taxonomy` · `coverage gate` · `budget exhaustion` · `pass@1` · `binomial confidence interval` · `TTFGB` · `minimal diff`
