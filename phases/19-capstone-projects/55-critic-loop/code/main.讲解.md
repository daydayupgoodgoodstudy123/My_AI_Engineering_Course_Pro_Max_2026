# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 55 节 Critic 评审循环 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下；测试：`python3 -m pytest -q` 或 `python3 -m unittest discover tests`） ｜ **依赖**：仅标准库（`json`、`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

54 节写出了论文初稿，本节让一个 critic（评审者）给初稿打分、提出修改建议，再由 reviser（修订者）执行修改，循环往复直到满足停止条件。讲义开篇点题："A critic that returns 'looks good' the first time is broken. A critic that always returns 'needs work' is broken. The interesting critic is the one that converges, and you have to engineer convergence."

具体考察：

1. **结构化评审**：五个固定维度的分数向量 + 指向章节的建议（`Suggestion`）。
2. **可替换的接口**：`Critic`、`Reviser` 用 `typing.Protocol` 定义，确定性实现和模型实现可以互换。
3. **收敛工程**：target（全部维度达标）→ plateau（连续两轮均分提升 ≤ ε）→ budget（轮数上限）。
4. **trace 优先**：每轮记录分数、均分、建议数和判决，供仪表盘与 56 节调度器使用。
5. **确定性的打分与修订**：用简单的启发式规则模拟 critic 和 reviser，让循环可测试。

> 一句话：**把"让模型自我改进"变成一个有明确终止条件、每一步都可追踪的循环**。同时要看到：这个循环只盯着均分，看不到单维度的回退；而确定性 reviser 靠往正文里填 `x` 就能把分数刷上去——这正是真实 LLM 评审循环最需要警惕的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DIMENSIONS` | 模块常量（元组） | 五个评分维度的名字 | 分数向量 |
| `MiniSection` / `MiniPaper` | dataclass | 54 节 `Section` / `Paper` 的简化版，另加 `originality_tag` 等字段 | 被评审的稿件 |
| `Suggestion` | dataclass | 维度、目标章节、编辑指令 | 结构化建议 |
| `Critique` | dataclass | 轮次、分数、建议、原因；`mean()` 求均分 | 结构化评审 |
| `Critic` / `Reviser` | `Protocol` | 可调用接口：`(paper, round_) -> Critique`、`(paper, suggestions) -> paper` | 依赖注入 |
| `LoopTrace` | dataclass | 每轮一条：轮次、分数、均分、应用的建议数、判决 | trace |
| `LoopResult` | dataclass | 状态、原因、使用轮数、最终分数、稿件、trace | 循环结果 |
| `CriticLoop` | 类 | `_target_met`、`_plateau`、`run` | 收敛控制 |
| `deterministic_score` | 函数 | 按启发式规则给五个维度打分 | 确定性 critic 的核心 |
| `deterministic_critic` | 函数 | 打分 + 对低于 8.0 的维度各给一条建议 | 确定性 critic |
| `deterministic_reviser` | 函数 | 按 `edit` 字段执行 5 种修改，原地修改稿件 | 确定性 reviser |
| `make_deterministic_critic_pair` | 工厂函数 | 返回 `(critic, reviser)` 二元组 | 配套组件 |
| `demo` | 函数 | 单章节初稿，`max_rounds=6` 跑一遍循环 | 演示 |

数据流：初稿 `MiniPaper` → `CriticLoop.run`：每轮 `critic(paper, round)` → `Critique` → 检查 target → 追加 `LoopTrace` → 检查 plateau → `reviser(paper, suggestions)` → 下一轮；循环结束 → budget → `LoopResult` → `to_dict()` → JSON 输出。

---

## 3. 逐段精讲

### 3.1 维度与稿件结构

```python
DIMENSIONS: tuple[str, ...] = (
    "clarity",
    "novelty",
    "evidence",
    "methodology",
    "related_work",
)
```

- 用**元组**而不是列表：维度集合是固定契约，元组不可变，也能防止被意外修改。`tuple[str, ...]` 表示"任意长度的字符串元组"。
- 讲义文字里写作 `related-work`，代码里统一是 `related_work`（下划线，便于作为字典键和 JSON 字段）。

```python
@dataclass
class MiniPaper:
    title: str
    abstract: str
    sections: list[MiniSection] = field(default_factory=list)
    originality_tag: str = "low"
    citation_count_target: int = 4
    figure_count_target: int = 2
```

- docstring 说它 "Mirrors lesson 54 Paper"，但只保留了 critic 需要的字段，并新增了 `originality_tag`（驱动 novelty 打分）。这样本节可以独立运行，不必 import 54 节。
- ⚠️ `citation_count_target`、`figure_count_target` 在整个代码和测试中**从未被使用**（`grep` 只能找到定义处），是遗留的死字段。evidence 的打分并不参考它们。

### 3.2 `Suggestion` 与 `Critique`

```python
@dataclass
class Suggestion:
    dimension: str
    target_section_id: str | None
    edit: str


@dataclass
class Critique:
    round: int
    scores: dict[str, float]
    suggestions: list[Suggestion]
    reason: str

    def mean(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)
```

- 每条建议说明"改善哪个维度、改哪个章节、做什么修改"。`target_section_id` 可以是 `None`，表示全局修改（如提高原创性、新增章节）。
- 讲义："A model-driven reviser would interpret the same field as a prompt. The contract does not change." 确定性 reviser 把 `edit` 当作命令名，模型 reviser 可以把它当作自然语言指令。
- `mean()` 对 `scores` 中**实际存在的键**求平均。如果某个 critic 只返回了部分维度，均分的含义就变了（实测只返回 `{"clarity": 9.0}` 时均分为 9.0，但 `_target_met` 把缺失维度当 0 分）。
- 字段名 `round` 与内置函数 `round()` 同名。在 dataclass 中作为属性没有问题，但在函数参数里会遮蔽内置函数——所以 Protocol 和循环里用的是 `round_`。

### 3.3 `Protocol`：只约定"长什么样"的接口

```python
class Critic(Protocol):
    def __call__(self, paper: MiniPaper, round_: int) -> Critique: ...


class Reviser(Protocol):
    def __call__(self, paper: MiniPaper, suggestions: list[Suggestion]) -> MiniPaper: ...
```

- `typing.Protocol` 是**结构化子类型**（静态鸭子类型）：任何具有相同签名 `__call__` 的对象都"符合"这个协议，不需要显式继承。普通函数天然有 `__call__`，所以 `deterministic_critic` 这个函数就是一个合法的 `Critic`。
- 方法体写 `...`（Ellipsis）表示只声明不实现。
- Protocol 只在类型检查器（如 mypy）中生效，运行时不会检查参数类型。测试中的 `stuck_critic`、`no_op_reviser` 都是临时定义的普通函数，正是利用了这一点。

### 3.4 `LoopTrace` 与 `LoopResult`

```python
@dataclass
class LoopTrace:
    round: int
    scores: dict[str, float]
    mean: float
    suggestions_applied: int
    verdict: str
```

- 与讲义 "The Trace output" 一致：轮次、分数向量、建议数、判决（`continue / target / plateau / budget`）。
- `LoopResult` 带回最终状态（`converged` / `stopped`）、原因、使用轮数、最终分数、稿件和完整 trace；`to_dict()` 不包含稿件本身（稿件不是 JSON 友好的对象）。

### 3.5 `CriticLoop`：收敛控制的核心

```python
    def __init__(self, critic, reviser, max_rounds=5, target_score=8.0,
                 plateau_epsilon=0.1, plateau_window=2) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        if plateau_window < 1:
            raise ValueError("plateau_window must be >= 1")
```

- 默认值与讲义一致：最多 5 轮、目标 8.0、ε = 0.1、窗口 2。构造时就校验参数，避免运行到一半才发现配置非法。

```python
    def _target_met(self, critique: Critique) -> bool:
        return all(critique.scores.get(d, 0.0) >= self.target_score for d in DIMENSIONS)
```

- **全部**维度都要 ≥ 目标。讲义："A high mean with one weak dimension is not enough." 缺失的维度按 0 分处理。

```python
    def _plateau(self, trace: list[LoopTrace]) -> bool:
        if len(trace) < self.plateau_window + 1:
            return False
        recent = trace[-(self.plateau_window + 1):]
        for i in range(1, len(recent)):
            if recent[i].mean - recent[i - 1].mean > self.plateau_epsilon:
                return False
        return True
```

- 取最近 `window + 1` 条 trace（默认 3 条），检查相邻两两之间的**提升**是否都 ≤ ε；只要有一次提升 > ε 就不算平台期。因此最早在第 3 轮才能判 plateau。
- ⚠️ **只看均分**：讲义说"一个修订提升了 clarity 却拖垮了 evidence，会被收敛检查看到"，但这里没有任何逐维度比较。实测"clarity 每轮 +2、evidence 每轮 −2"的 critic，均分恒为 5.0，第 3 轮以 `converged / plateau` 结束（测验 Q6）。
- ⚠️ **下降也算平台期**：条件只排除了"提升 > ε"，任何下降都满足。实测分数 8 → 6 → 4 时第 3 轮判 `plateau`、状态是 `converged`。
- ⚠️ 边界对浮点误差敏感：均分 5.0 → 5.1 → 5.2 时，第一个差值 `0.0999…` ≤ 0.1，第二个 `0.1000…05` > 0.1。

```python
    def run(self, paper: MiniPaper) -> LoopResult:
        trace: list[LoopTrace] = []
        critique: Critique | None = None

        for round_ in range(1, self.max_rounds + 1):
            critique = self.critic(paper, round_)
            applied = len(critique.suggestions)

            if self._target_met(critique):
                trace.append(LoopTrace(..., suggestions_applied=0, verdict="target"))
                return LoopResult(status="converged", reason="target", ...)

            interim = LoopTrace(..., suggestions_applied=applied, verdict="continue")
            trace.append(interim)

            if self._plateau(trace):
                interim.verdict = "plateau"
                return LoopResult(status="converged", reason="plateau", ...)

            paper = self.reviser(paper, critique.suggestions)

        final_scores = dict(critique.scores) if critique is not None else {d: 0.0 for d in DIMENSIONS}
        final_mean = critique.mean() if critique is not None else 0.0
        if trace:
            trace[-1].verdict = "budget"
        return LoopResult(status="stopped", reason="budget", rounds_used=self.max_rounds, ...)
```

逐步说明：

1. **每轮先评审**，再按 target → plateau 的顺序检查，最后才修订——这就是讲义 "Target wins over plateau wins over budget"。
2. **target 分支**：记录一条 `suggestions_applied=0` 的 trace 并返回。注意此时**不再修订**，返回的稿件就是被打分的稿件。
3. **先追加 trace 再判 plateau**：`_plateau` 需要包含本轮在内的历史。判定后直接修改 `interim.verdict`——因为 trace 列表里存的是同一个对象，修改会反映在列表中。
4. **for 循环自然结束**即 budget：把最后一条 trace 的判决改成 `budget`。`critique is not None` 的判断是防御性的（`max_rounds >= 1` 已保证至少评审一次）。
5. `status` 的取值：target 和 plateau 都是 `converged`，budget 是 `stopped`。

⚠️ 三个状态问题（测验 Q8、Q10 实测）：

- **budget 时分数与稿件不对应**：最后一轮评审后仍会调用 reviser 修改稿件，然后循环结束，这次修改从未被打分。`max_rounds=2` 时 `final_scores` 的 clarity 为 6.69，而返回稿件的实际得分是 7.23。
- **plateau 轮的 `suggestions_applied` 不准确**：该轮没有调用 reviser，但 trace 记录的是建议条数。
- **不保留历史最优稿**：分数下降后以 plateau 结束时，返回的是最后（也是最差）的一稿。

另外，reviser 原地修改稿件，调用方传入的 `paper` 在循环结束后已被改变（`result.paper is paper` 为 `True`）。

### 3.6 `deterministic_score`：启发式打分

```python
    body_lens = [len(s.body) for s in paper.sections]
    avg_body = (sum(body_lens) / len(body_lens)) if body_lens else 0.0
    section_titles = {s.title.lower() for s in paper.sections}

    clarity = min(10.0, 3.0 + avg_body / 50.0)
```

| 维度 | 规则 | 取值范围 |
|------|------|---------|
| clarity | `3 + 平均正文长度 / 50`，上限 10 | 3.0 ～ 10.0 |
| novelty | `originality_tag`：high 9 / medium 6 / 其它 3 | 3、6、9 |
| evidence | `2 + 2 × 图引用数 + 1.5 × 引用数`，上限 10 | 2.0 ～ 10.0 |
| methodology | 存在标题以 "method" 开头且有正文的章节 → 9，否则 4 | 4、9 |
| related_work | 存在标题恰为 "related work" 且有正文的章节 → 9，否则 4 | 4、9 |

- 与讲义的描述基本一致；讲义说 evidence "grows when a section's figure_refs is non-empty"，代码同时计入了图引用和引用数。
- `startswith("method")` 让 "Methodology"、"Methods" 也算数（实测 "Methodology" 得 9.0）。
- `has_related` 中先判断 `"related work" in section_titles` 再用 `any(...)` 检查正文——前一个条件是冗余的（后者已经包含标题判断），只是起到短路作用。
- `fig_refs = sum(1 for s in paper.sections for _ in s.figure_refs)` 用嵌套生成器表达式计数，等价于 `sum(len(s.figure_refs) for s in paper.sections)`。
- 所有分数 `round(..., 2)`，保证 JSON 输出整洁、比较稳定。
- ⚠️ 三个维度的上限是 9.0，所以 `target_score > 9.0` 永远不可能达成（测验 Q7）。
- ⚠️ clarity 只看**长度**，这是一个很容易被"刷"的代理指标（见 3.8）。

### 3.7 `deterministic_critic`：对不达标的维度各提一条建议

```python
def deterministic_critic(paper: MiniPaper, round_: int) -> Critique:
    scores = deterministic_score(paper)
    suggestions: list[Suggestion] = []

    def first_section_id(default: str = "intro") -> str:
        return paper.sections[0].id if paper.sections else default

    if scores["clarity"] < 8.0:
        target = paper.sections[-1].id if paper.sections else None
        suggestions.append(Suggestion(dimension="clarity", target_section_id=target, edit="expand-body"))
    if scores["novelty"] < 8.0:
        suggestions.append(Suggestion(dimension="novelty", target_section_id=None, edit="bump-originality"))
    ...
    reason = "fully-met" if not suggestions else f"{len(suggestions)} below target"
    return Critique(round=round_, scores=scores, suggestions=suggestions, reason=reason)
```

| 维度 | 编辑指令 | 目标章节 |
|------|---------|---------|
| clarity | `expand-body` | **最后一个**章节 |
| novelty | `bump-originality` | 无 |
| evidence | `add-figure-and-cite` | 第一个章节（没有章节时默认 `"intro"`） |
| methodology | `add-method-section` | 无 |
| related_work | `add-related-work-section` | 无 |

- 嵌套函数 `first_section_id` 通过**闭包**读取外层的 `paper`。
- ⚠️ 阈值 8.0 是**写死的**，与 `CriticLoop.target_score` 无关。循环目标改成 9.5 时，critic 在所有维度 ≥ 8 后就不再提建议，循环只能以 plateau 结束（实测第 7 轮）。
- 空论文时 clarity 建议的目标是 `None`、evidence 建议的目标是不存在的 `"intro"`，第一轮这两条建议实际上是空操作（实测空论文仍能在第 4 轮达标，因为新增的 Method 章节成了后续建议的目标）。

### 3.8 `deterministic_reviser`：执行修改（以及"刷分"）

```python
def deterministic_reviser(paper: MiniPaper, suggestions: list[Suggestion]) -> MiniPaper:
    fig_counter = 0
    cite_counter = 0
    for s in paper.sections:
        fig_counter += len(s.figure_refs)
        cite_counter += len(s.cites)

    for sug in suggestions:
        if sug.edit == "expand-body":
            for sec in paper.sections:
                if sec.id == sug.target_section_id:
                    sec.body = (sec.body + " " + ("x" * 80)).strip()
                    break
        elif sug.edit == "bump-originality":
            if paper.originality_tag == "low":
                paper.originality_tag = "medium"
            elif paper.originality_tag == "medium":
                paper.originality_tag = "high"
        elif sug.edit == "add-figure-and-cite":
            ...  # 给目标章节追加 f{n} 和 c{n}
        elif sug.edit == "add-method-section":
            ...  # 没有 Method 章节就新增一个（正文 37 + 200 = 237 字符）
        elif sug.edit == "add-related-work-section":
            ...  # 没有 Related Work 章节就新增一个（正文 25 + 200 = 225 字符）
    return paper
```

- 先统计已有的图引用和引用数，新编号从这里继续，保证 `f1, f2, …` 不重复。
- `if / elif` 链按 `edit` 字段分派；未知的 `edit`（如测试里的 `"no-op"`）被静默忽略。
- `bump-originality` 每次只升一级：low → medium → high，所以 novelty 需要两轮才能从 3 升到 9。
- `for ... break`：找到目标章节修改后立即跳出。
- `(sec.body + " " + "x"*80).strip()`：正文为空时去掉开头的空格，所以空正文增加 80 个字符，非空正文增加 81 个字符。
- **docstring 明说 "Returns a mutated paper (same object)"**：原地修改并返回同一个对象。
- ⚠️ **刷分**：`expand-body` 追加的是 80 个 `x`，`add-figure-and-cite` 加的是不存在的图 `f1` 和文献 `c1`，新章节的正文也是 `"x" * 200`。critic 的分数确实上升了，稿件质量却没有任何改善——这是 Goodhart 定律（"当一个指标变成目标，它就不再是好指标"）的教科书示例。讲义坦白 "The reviser knows how to push each score upward"，在演示中这是为了让循环可测；在真实系统中，这正是要防范的 reward hacking（测验 Q12）。

### 3.9 `demo`

```python
def demo() -> dict:
    paper = MiniPaper(
        title="Auto-Research Loop", abstract="abstract",
        sections=[MiniSection(id="intro", title="Introduction", body="short intro")],
        originality_tag="low",
    )
    critic, reviser = make_deterministic_critic_pair()
    loop = CriticLoop(critic=critic, reviser=reviser, max_rounds=6, target_score=8.0)
    result = loop.run(paper)
    return result.to_dict()
```

- 初稿只有一个 11 字符的引言，五个维度都很低，正好展示完整的收敛轨迹。
- `max_rounds=6`（而不是默认 5），给循环留了一轮余量；实际第 5 轮就达标。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 五个固定维度的分数向量 | harness 可以逐维度检查、画轨迹 | 收敛判断实际只用了均分；应加入逐维度回退检测 |
| target 要求全部维度达标 | 避免"均分高但有短板" | 维度上限不同（9.0）时目标可能不可达，需要启动时检查 |
| plateau 看连续两轮 | 过滤单轮噪声 | 下降也被当作"收敛"；ε 远小于 LLM 打分噪声时规则失效 |
| budget 作为最后保险 | 循环一定会终止 | 最后一次修订未被评估，分数与稿件不一致 |
| Critic / Reviser 用 `Protocol` | 确定性实现与模型实现可互换，测试用 stub | 运行时不检查签名 |
| 确定性启发式打分 | 可复现、测试快 | 代理指标容易被刷；真实 critic 需要 rubric、多评审者 |
| reviser 原地修改 | 实现简单 | 调用方对象被改变、无法回滚；应 `deepcopy` 并保存历史最优 |
| critic 阈值写死 8.0 | 简单 | 与循环的 `target_score` 脱节 |
| trace 记录每轮判决 | 讲义的 "trace-first design"，便于诊断 | plateau 轮的 `suggestions_applied` 记录不准确 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 带类型注解的模块常量 | `DIMENSIONS: tuple[str, ...] = (...)` | `...` 表示任意长度 |
| `@dataclass` + `field(default_factory=list)` | `sections: list[MiniSection] = field(default_factory=list)` | 可变默认值 |
| `X \| None` | `target_section_id: str \| None` | 可选值 |
| `typing.Protocol` | `class Critic(Protocol): def __call__(...) -> Critique: ...` | 结构化子类型接口 |
| `...`（Ellipsis） | Protocol 方法体 | 占位，表示只声明 |
| 函数作为对象 | `return deterministic_critic, deterministic_reviser` | 函数可以被返回、存储、传参 |
| 元组解包 | `critic, reviser = make_deterministic_critic_pair()` | 一次接收两个返回值 |
| `all()` + 生成器表达式 | `all(critique.scores.get(d, 0.0) >= self.target_score for d in DIMENSIONS)` | 全部满足才为真 |
| `any()` | `any(s.title.lower().startswith("method") and s.body for s in paper.sections)` | 任一满足即为真 |
| 负索引切片 | `trace[-(self.plateau_window + 1):]` | 取最后 N 个元素 |
| `range(1, n + 1)` | `for round_ in range(1, self.max_rounds + 1):` | 轮次从 1 开始 |
| 避免遮蔽内置名 | `round_` | 内置函数 `round` 已被占用，加下划线区分 |
| `for ... else` 之外的提前 `return` | `run` 中 target / plateau 分支 | 满足条件立即返回结果 |
| 修改列表中的对象 | `interim.verdict = "plateau"`、`trace[-1].verdict = "budget"` | 列表存的是引用，改对象即改列表内容 |
| 集合推导式 | `{s.title.lower() for s in paper.sections}` | 去重的标题集合 |
| 嵌套生成器 | `sum(1 for s in paper.sections for _ in s.figure_refs)` | 两层循环计数 |
| `min()` 封顶 | `min(10.0, 3.0 + avg_body / 50.0)` | 限制最大值 |
| 闭包 | `def first_section_id(default="intro")` 读取外层 `paper` | 内部函数访问外层变量 |
| 字符串乘法 | `"x" * 80` | 重复字符串 |
| `if / elif` 分派 | reviser 中按 `sug.edit` 分支 | 简单的命令分派 |
| 条件表达式 | `"fully-met" if not suggestions else f"{len(suggestions)} below target"` | 一行 if/else |
| `json.dumps(..., indent=2)` | `print(json.dumps(demo(), indent=2))` | 格式化输出 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，输出已整理）：

```text
status: converged    reason: target    rounds_used: 5    final_mean: 8.862

round  clarity  novelty  evidence  methodology  related_work   mean    applied  verdict
  1     3.22     3.0      2.0        4.0          4.0          3.244     5      continue
  2     6.69     6.0      5.5        9.0          9.0          7.238     3      continue
  3     7.23     9.0      9.0        9.0          9.0          8.646     1      continue
  4     7.77     9.0      9.0        9.0          9.0          8.754     1      continue
  5     8.31     9.0      9.0        9.0          9.0          8.862     0      target
```

逐轮解读（数值均已手算核对）：

- **第 1 轮**：只有 11 字符的引言 → clarity `3 + 11/50 = 3.22`；novelty 3、evidence 2、methodology 4、related_work 4，五个维度全部 < 8，产生 5 条建议。reviser 执行：引言追加 81 字符（变成 92）、原创性 low → medium、引言加 `f1`/`c1`、新增 Method（237 字符）和 Related Work（225 字符）章节。
- **第 2 轮**：平均长度 `(92 + 237 + 225)/3 = 184.67` → clarity 6.69；novelty 6；evidence `2 + 2 + 1.5 = 5.5`；methodology 和 related_work 都升到 9。3 条建议：clarity（目标变成最后一个章节 Related Work）、novelty、evidence。
- **第 3 轮**：Related Work 306 字符 → clarity 7.23；novelty 9；evidence `2 + 4 + 3 = 9`。只剩 clarity 一条建议。
- **第 4、5 轮**：每轮 Related Work 再增加 81 字符，clarity 每轮 +0.54（7.77 → 8.31）。第 5 轮全部维度 ≥ 8，判 `target`，trace 中 `suggestions_applied` 记为 0。
- **均分轨迹**：3.244 → 7.238 → 8.646 → 8.754 → 8.862。第 3 轮之后每轮只提升 0.108，仅比 ε = 0.1 略大——如果每次扩写的字符更少，循环就会以 plateau 结束（测验 Q11 给出了实测：每次追加 40 字符时第 5 轮 plateau）。
- **稿件真实状态**：最终 Related Work 有 468 个字符，其中绝大部分是 `x`；引言挂着 `f1, f2` 两个并不存在的图和 `c1, c2` 两条并不存在的文献。分数达标了，内容却毫无改善——确定性 reviser 只是在"喂"确定性 critic。

补充探针（自写脚本）结果：

| 场景 | 结果 |
|------|------|
| 分数恒定、`max_rounds=3`（即测试 `test_budget_exhaustion_when_no_progress`） | `plateau`，第 3 轮；budget 分支没有被触发 |
| 分数恒定、`max_rounds=2` | `budget` |
| clarity +2 / evidence −2 每轮 | 均分恒为 5.0，第 3 轮 `converged / plateau` |
| 分数 8 → 6 → 4 | 第 3 轮 `converged / plateau`，`final_mean=4.0` |
| `target_score=9.5` | 第 7 轮 `plateau`，第 5～7 轮建议数为 0 |
| `max_rounds=2` | `budget`，`final_scores` clarity 6.69，稿件实际 7.23 |
| 空论文（无章节） | 第 4 轮 `target` |

---

## 7. 动手改一改

1. **（入门）** 把 `plateau_epsilon` 改成 0.2，重新跑 demo，观察循环在第几轮、以什么原因停止；再把 `max_rounds` 改成 3，观察 budget 分支和 `final_scores` 的问题。
2. **（入门）** 让 `deterministic_critic` 接收目标分数（例如通过 `functools.partial` 或在 `CriticLoop` 中传入），去掉写死的 8.0；并在 `CriticLoop.__init__` 中检查 `target_score` 是否超过各维度可能的最高分。
3. **（进阶）** 实现测验 Q9 的逐维度回退检测，以 `reason="regression"` 停止；写一个"此消彼长"的 stub critic 作为测试。
4. **（进阶）** 实现测验 Q10：`deepcopy` 输入、保存历史最优稿、最后一轮不再修订、`suggestions_applied` 只在真正修订后记录；补一个真正覆盖 budget 分支的测试（`max_rounds=2`，断言 `final_scores == deterministic_score(result.paper)`）。
5. **（进阶）** 按讲义 "Going further" 实现维度权重：`CriticLoop(weights={"novelty": 2.0, ...})`，plateau 改用加权均分；比较 workshop 权重和 journal 权重下 demo 的收敛轨迹。
6. **（挑战）** 把 clarity 改成更难刷分的指标（例如测验 Q12 的"不同单词数"），观察确定性 reviser 无法再让循环达标；然后写一个"真正改善"的 reviser（例如从一个短语库中追加有意义的句子），让循环重新收敛。体会"critic 定义了 reviser 会去优化什么"。

---

## 8. 常见坑

- **以为 plateau 一定是好事**：分数下降也会被判为 plateau，状态还是 `converged`。
- **只看均分**：单维度回退会被其它维度的提升掩盖。
- **相信 budget 时的 `final_scores`**：最后一次修订没有被评估，分数对应的是上一版稿件。
- **critic 阈值与循环目标不一致**：critic 不再提建议时，循环只能空转到 plateau 或 budget。
- **目标不可达**：某些维度最高只有 9.0，`target_score > 9` 永远不会达成。
- **原地修改输入**：循环结束后调用方手里的稿件已经变了；需要对比修改前后时要先 `deepcopy`。
- **代理指标被刷分**：长度、关键词、引用数量都很容易被"堆"出来；分数上升不等于质量提升。
- **ε 与噪声 / 进步幅度不匹配**：ε 太大会把缓慢的进步判为停滞，ε 小于 LLM 打分噪声时又几乎永远判不出平台期。
- **测试断言过宽**：`assertIn(result.reason, ("plateau", "budget"))` 让 budget 分支实际上没有被测到。

---

## 9. 测试在验证什么

测试文件：`code/tests/test_critic_loop.py`（`unittest` 风格）。除了确定性 critic/reviser，测试还临时定义了 `stuck_critic`、`slow_critic`、`no_op_reviser` 等 stub，直接利用 `Protocol` 的结构化类型来注入。

| 测试类 / 方法 | 验证的性质 |
|--------------|-----------|
| `TestScoring.test_score_keys_match_dimensions` | 打分结果的键恰好是五个维度 |
| `TestScoring.test_score_each_in_zero_ten` | 1000 字符正文 + high 原创性时，每个分数都在 [0, 10] |
| `TestScoring.test_originality_tag_drives_novelty` | novelty 随 low < medium < high 单调上升 |
| `TestCritic.test_critic_emits_suggestions_for_below_target` | 空论文第 1 轮：轮次正确、五个维度齐全、含 novelty 建议 |
| `TestConvergence.test_monotone_improvement_after_one_round` | 修订一轮后均分上升（讲义："the loop reduces the gap"） |
| `TestConvergence.test_target_convergence` | 确定性组合最终以 `converged / target` 结束，所有最终分数 ≥ 8 |
| `TestConvergence.test_budget_exhaustion_when_no_progress` | 分数恒为 4、`max_rounds=3`：原因是 plateau 或 budget，轮数 ≤ 3（实际是 plateau） |
| `TestConvergence.test_plateau_detected_when_mean_stable` | 均分 5.0 → 5.05 → 5.07 → 5.08，第 3 轮判 plateau，最后一条 trace 的判决为 `plateau` |
| `TestTrace.test_trace_shape` | 每条 trace 的判决在四种取值内、分数键齐全、均分为 float |
| `TestReviser.test_revision_applies_targeted_edit` | `expand-body` 让目标章节正文变长 |
| `TestReviser.test_bump_originality_climbs` | 原创性 low → medium → high 逐级提升 |

运行方式与实际结果：

```text
$ cd code && python3 -m pytest -q
...........                                                              [100%]
11 passed in 0.01s
```

值得注意：

- **budget 分支没有被任何测试覆盖**：`test_budget_exhaustion_when_no_progress` 实际走的是 plateau（第 3 轮 plateau 检查先于循环结束），断言写成"二者之一"把这一点掩盖了。讲义声称测试覆盖了 "budget exhaustion when no suggestion improves"。
- 没有测试"单维度回退"——讲义声称收敛检查能看到它，但代码并没有实现，测试也就无从验证。
- 没有测试 `max_rounds < 1`、`plateau_window < 1` 的参数校验，也没有测试 budget 时 `final_scores` 与稿件是否一致。
- 讲义列出的 "suggestion application by the reviser" 只测了 `expand-body` 和 `bump-originality` 两种编辑，另外三种（加图和引用、加 Method、加 Related Work）只在端到端测试中间接覆盖。
