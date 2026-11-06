# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 17 节 个人 AI 导师——自适应、多模态与记忆 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`math`、`collections`、`dataclasses`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义描述的是一个完整的产品级导师：LangGraph 策略、Neo4j 课程图、语音/拍照输入、Llama Guard 安全层、COPPA 记忆策略、两周效果研究。这些都需要外部服务，`main.py` 只保留了讲义所说的"hard architectural primitive"——**学习者模型如何驱动课程选择**：

1. **Bayesian knowledge tracing（BKT）**：四参数模型，每次作答后更新单个概念的掌握概率。
2. **课程图（DAG）**：11 个代数概念 + 先修边；选择器只挑"先修已掌握、自身未掌握"的概念。
3. **Socratic policy**：根据"是否答对 + 当前掌握度"决定下一步是庆祝推进、巩固、提示还是从先修开始搭脚手架。
4. **模拟效果研究**：10 名模拟学习者，自适应组 vs 轮转基线组，用共同随机数配对，比较 60 轮后的掌握度之和。

> 一句话：**用不到 250 行标准库代码，把"学习者模型 → 选概念 → 教学动作 → 再更新模型"这个闭环跑起来，并做一次（有缺陷的）自适应 vs 线性对照实验。**

另外，`code/ts/` 下有一个 TypeScript 版的 Web API（Hono 路由、拓扑排序、间隔加倍/减半的复习调度），不在本讲解范围内，第 3.8 节只做对比说明。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BKTParams` | dataclass | 存 `p_init / p_learn / p_slip / p_guess` | BKT 四参数 |
| `bkt_update` | 函数 | 贝叶斯后验 + 学习转移 | learner model |
| `Concept` / `ALGEBRA` | dataclass / 常量列表 | 11 个概念及其先修 | curriculum graph |
| `curriculum_map` | 函数 | 列表 → `{name: Concept}` 字典 | 图索引 |
| `LearnerState` | dataclass | 每个概念的掌握度（默认 0.2）+ 作答历史 | 学习者状态 |
| `next_concept` | 函数 | 按列表顺序找第一个可学概念 | select_concept |
| `socratic_policy` | 函数 | 返回 4 种教学动作之一 | Socratic decision head |
| `simulate_answer` | 函数 | `sigmoid(knowledge − difficulty)` 抽样是否答对 | 模拟学生（IRT/Rasch 形式） |
| `run_adaptive` | 函数 | 自适应组：选概念 → 作答 → 定动作 → 更新 | tutor loop |
| `run_baseline` | 函数 | 基线组：按列表轮转出题 | 非自适应基线 |
| `mastery_sum` | 函数 | 所有概念掌握度之和 | 评价指标 |
| `main` | 函数 | 10 人研究 + 一条示例轨迹 | efficacy study |

数据流：`main` 生成能力值 → 对每个学习者复制随机流 → `run_adaptive` / `run_baseline`（内部循环：`next_concept` → `simulate_answer` → `socratic_policy` → `bkt_update`）→ `mastery_sum` → 打印均值与差值 → 再跑一条 20 轮示例轨迹。

---

## 3. 逐段精讲

### 3.1 BKT 参数与更新

```python
@dataclass
class BKTParams:
    p_init: float = 0.2     # prior knowledge
    p_learn: float = 0.12   # learning rate per practice
    p_slip: float = 0.10    # correct despite not knowing
    p_guess: float = 0.15   # correct by guessing despite not knowing


def bkt_update(mastery: float, correct: bool, p: BKTParams) -> float:
    if correct:
        num = mastery * (1 - p.p_slip)
        denom = num + (1 - mastery) * p.p_guess
    else:
        num = mastery * p.p_slip
        denom = num + (1 - mastery) * (1 - p.p_guess)
    posterior = num / max(denom, 1e-6)
    # transition: learn from this interaction
    return posterior + (1 - posterior) * p.p_learn
```

- **第一步，贝叶斯后验**：把"已掌握"看作隐状态，答对/答错是观测。
  - 答对：`P(对|会) = 1 − slip`，`P(对|不会) = guess`；
  - 答错：`P(错|会) = slip`，`P(错|不会) = 1 − guess`。
  - `posterior = 掌握者产生该观测的概率 / 总概率`。
- **第二步，学习转移**：`posterior + (1 − posterior) · p_learn`——本次练习让"不会"的学生有 12% 的概率学会。BKT 经典版本没有遗忘，所以只加不减。
- `max(denom, 1e-6)`：防止除零（例如 `mastery = 0` 且 `p_guess = 0` 时分母为 0）。
- **数值感受**（实际计算）：

| 当前掌握度 | 答对后 | 答错后 |
|-----------|-------|-------|
| 0.20 | 0.648 | 0.145 |
| 0.50 | 0.874 | 0.213 |
| 0.62 | 0.918 | 0.262 |
| 0.85 | 0.975 | 0.472 |

  答对一次的证据非常强（似然比 0.9 / 0.15 = 6），所以 0.2 → 0.648；连续答对两次就到 0.927，超过掌握阈值 0.85。
- 注意：讲义"Use It"示例写 `0.62 -> 0.77`，与上表 0.918 不一致——示例数字只是示意，一次更新的幅度完全由参数决定。
- 注释问题：`p_slip` 的注释 "correct despite not knowing" 写错了，slip 的含义是 **"incorrect despite knowing"**（会了却答错）；公式本身用法正确。
- `p_init` 从未被使用：初值写死在 `LearnerState` 的 `defaultdict(lambda: 0.2)` 里，两处要同步修改。

### 3.2 课程图

```python
@dataclass
class Concept:
    name: str
    prereqs: list[str] = field(default_factory=list)


ALGEBRA = [
    Concept("number_line", []),
    Concept("addition_subtraction", ["number_line"]),
    ...
    Concept("linear_equations", ["isolating_variable_two_step", "combining_like_terms"]),
    Concept("quadratic_basics", ["linear_equations", "multiplication_division"]),
]


def curriculum_map(concepts: list[Concept]) -> dict[str, Concept]:
    return {c.name: c for c in concepts}
```

- 11 个节点，从"数轴"到"二次方程基础"，先修边构成一个 DAG（有向无环图）。讲义要求 50–150 个节点并存在 Neo4j 中，这里是最小化版本。
- `field(default_factory=list)`：dataclass 中可变默认值必须用工厂函数，否则所有实例共享同一个列表。
- **列表本身已按拓扑序书写**（每个概念都排在它所有先修之后），`next_concept` 依赖这一点。代码没有做环检测或拓扑排序；TS 版 `topoOrder` 用 Kahn 算法做了，并在发现未知先修或环时抛错。
- `curriculum_map` 用字典推导式建索引；Python 3.7+ 的字典保持插入顺序，所以 `cmap.values()` 仍是拓扑序。

### 3.3 学习者状态

```python
@dataclass
class LearnerState:
    learner_id: str
    mastery: dict[str, float] = field(default_factory=lambda: defaultdict(lambda: 0.2))
    history: list[tuple[str, bool]] = field(default_factory=list)
```

- `mastery` 是 `defaultdict`：访问没见过的概念时自动返回并**插入** 0.2。因此 `next_concept` 检查先修、`mastery_sum` 求和时都会顺手往字典里塞键——不影响结果，但如果要持久化"学生练过哪些概念"，应改用 `history` 判断或 `dict.get`。
- 类型注解写 `dict[str, float]`，实际对象是 `defaultdict`（`dict` 的子类），类型上是兼容的。
- `history` 记录 `(概念, 是否答对)`，对应讲义的 episodic memory 的极简版。

### 3.4 选择下一个概念

```python
def next_concept(state: LearnerState, cmap: dict[str, Concept],
                 master_threshold: float = 0.85) -> str | None:
    for c in cmap.values():
        if state.mastery[c.name] >= master_threshold:
            continue
        if all(state.mastery[pr] >= master_threshold for pr in c.prereqs):
            return c.name
    return None
```

- 规则：按拓扑序遍历，返回**第一个**"自身 < 0.85 且所有先修 ≥ 0.85"的概念；全部掌握返回 `None`。
- `all(... for pr in c.prereqs)`：生成器表达式 + `all`，空列表时为 `True`（所以 `number_line` 永远满足先修条件）。
- 与讲义的差距：讲义的 `select_concept` 要"picking the highest-priority concept"，这里的"优先级"只是列表顺序，不比较掌握度，也不安排复习。函数头注释写 "(b) low mastery"，实际含义只是"未达阈值"。
- 后果：所有概念掌握后返回 `None`，`run_adaptive` 直接 `break`，剩余轮次被浪费（见第 6 节）。

### 3.5 Socratic policy

```python
def socratic_policy(state: LearnerState, concept: str, correct: bool) -> str:
    m = state.mastery[concept]
    if correct and m > 0.8:
        return "celebrate_and_advance"
    if correct:
        return "reinforce_and_next_question"
    if m > 0.5:
        return "hint"
    return "scaffold_from_prereq"
```

- 四种动作对应讲义的"答对就推进、卡住就提示/搭脚手架"。
- 调用时机：在 `bkt_update` **之前**，所以 `m` 是更新前的掌握度。
- 由于掌握度 ≥ 0.85 的概念不会被选中，`celebrate_and_advance` 只在 `0.8 < m < 0.85` 且答对时出现；而掌握度通常从 0.648 直接跳到 0.927，这个分支几乎不会触发。
- 动作是字符串，没有用 `Enum`；拼写错误不会被发现（`run_adaptive` 里的 `if last_action == "hint"` 写错一个字母就静默失效）。

### 3.6 模拟学生

```python
def simulate_answer(learner_knowledge: float, concept_difficulty: float,
                    rng: random.Random) -> bool:
    import math
    p = 1 / (1 + math.exp(-(learner_knowledge - concept_difficulty)))
    return rng.random() < p
```

- `sigmoid(knowledge − difficulty)` 是 1PL IRT（Rasch 模型）的形式：能力比难度高越多，答对概率越接近 1。
- `rng.random() < p`：以概率 `p` 返回 `True`，是伯努利抽样的标准写法。每次调用**恰好消耗一个随机数**，这是 3.8 节"配对随机流"成立的前提。
- `import math` 写在函数内部：每次调用都会执行 import 语句（模块已缓存，开销很小），但风格上应放到文件顶部。

### 3.7 自适应组与基线组

```python
def run_adaptive(learner_id, inherent_ability, cmap, n_turns, rng):
    state = LearnerState(learner_id=learner_id)
    p = BKTParams()
    last_action: str | None = None
    for _ in range(n_turns):
        concept = next_concept(state, cmap)
        if concept is None:
            break
        difficulty = 0.3 + 0.1 * len(cmap[concept].prereqs)
        if last_action == "scaffold_from_prereq":
            difficulty -= 0.15    # easier retry from prereqs
        elif last_action == "hint":
            difficulty -= 0.08    # mild nudge
        elif last_action == "celebrate_and_advance":
            state.mastery[concept] = min(1.0, state.mastery[concept] + 0.02)
        ek = inherent_ability + state.mastery[concept] * 1.5
        correct = simulate_answer(ek, difficulty, rng)
        last_action = socratic_policy(state, concept, correct)
        state.history.append((concept, correct))
        state.mastery[concept] = bkt_update(state.mastery[concept], correct, p)
    return state
```

- **难度**：`0.3 + 0.1 × 先修数`，取值 0.3（数轴）、0.4、0.5。注意这里用的是"直接先修个数"而非"在图中的深度"，所以 `quadratic_basics`（深度最深）与 `isolating_variable_one_step` 难度相同，都是 0.5。
- **有效知识**：`ek = ability + mastery × 1.5`。关键问题：模拟学生的答对概率依赖**导师的掌握度估计** `state.mastery`——估计高 → 更容易答对 → 估计更高。真实世界中学生的知识与导师的估计是两回事，这里把它们混为一谈（循环论证）。
- **上一轮动作的作用**：`hint`/`scaffold` 降低本轮难度；`celebrate` 直接给本轮概念的掌握度 +0.02。问题有二：
  1. 动作是针对上一轮概念做出的，却作用在本轮概念上；当上一轮概念刚好掌握时，本轮已经换了概念，"庆祝"加错了对象。
  2. 直接修改 `state.mastery` 绕过了 BKT，学习者模型被非观测信息污染。
- `scaffold_from_prereq` 并没有回到先修概念出题，只是让难度 −0.15，名不副实。

```python
def run_baseline(learner_id, inherent_ability, cmap, n_turns, rng):
    ...
    order = list(cmap.keys())
    for i in range(n_turns):
        concept = order[i % len(order)]
        ...
```

- 基线按 `i % 11` 轮转出题，**不看先修**，也不跳过已掌握的概念；60 轮中每个概念练 5–6 次。
- docstring 说"only the policy / concept-selection strategy differs"。严格来说自适应组还多了"提示降难度、庆祝加分"的效果——如果把这些也算作"policy"，说法成立；但它让 delta 混合了两种来源。实际测量：去掉动作效果后 delta 从 +1.36 降到 +1.14。

### 3.8 效果研究主流程

```python
    for i in range(n_learners):
        ability = rng.gauss(0.3, 0.4)
        seed = 100 + i
        r_adapt = random.Random(seed)
        r_base = random.Random()
        r_base.setstate(r_adapt.getstate())
        s1 = run_adaptive(f"adapt_{i}", ability, cmap, n_turns, r_adapt)
        s2 = run_baseline(f"base_{i}", ability, cmap, n_turns, r_base)
        adaptive_gains.append(mastery_sum(s1, cmap))
        baseline_gains.append(mastery_sum(s2, cmap))
```

- `rng.gauss(0.3, 0.4)`：能力值服从均值 0.3、标准差 0.4 的正态分布，可能为负（本次运行最低 −0.631）。
- **共同随机数**：`getstate/setstate` 让两组的随机流完全相同；每轮只抽一个随机数，所以第 t 轮两组面对同一个"运气"。这是讲义"compare against a non-adaptive baseline"在模拟中的公平化手段。
- 指标 `mastery_sum` 是导师模型自己的估计之和（未练过的概念计 0.2），不是独立的后测成绩。变量名叫 `adaptive_gains`，其实存的是"最终水平"而不是"增益"（初始和都是 11 × 0.2 = 2.2，减去它才是 gain，不影响差值）。
- 示例轨迹段标题写 "adaptive learner 0"，但实际是另跑的一个 `ability=0.3`、`Random(7)`、20 轮的演示学习者，与研究里的 learner 0（ability −0.052、seed 100）不是同一个。
- `seen_concepts` 的去重写法 `if c not in [x[0] for x in seen_concepts]` 每次都重建列表，是 O(n²)；用 `dict.fromkeys(c for c, _ in state.history)` 更简洁。记录的 `state.mastery[c]` 是最终值，与"第一次见到时"无关。

**与 TS 版的对比**（只读未运行）：TS 的 `MasteryStore.record` 用 `score = 0.3·score + 0.7·成功率` 的指数平滑，README 称其 "BKT-style"，其实不是 BKT；阈值 0.7（Python 是 0.85）；`scheduleNextDue` 答对间隔加倍、答错减半，README 称 "FSRS-lite"，与 FSRS 的记忆模型无关；但它实现了 Python 版缺少的"到期复习"（`review_overdue`）分支。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 经典四参数 BKT，参数全局共享 | 公式短、可手算 | 生产中按概念用历史数据（EM 等）拟合参数；考虑遗忘、DKT 等变体 |
| 课程图用 Python 列表并人工保证拓扑序 | 零依赖 | 讲义用 Neo4j；至少要做拓扑排序与环检测（TS 版已做） |
| "第一个可学概念"选择器 | 简单、确定性 | 应按优先级（掌握度、到期时间、目标）排序，并在全部掌握后转复习 |
| 动作用字符串表示 | 打印友好 | 用 `Enum` 防拼写错误；动作应作用于对应概念 |
| 模拟学生 `sigmoid(ability + 1.5·mastery − difficulty)` | 无需真实学生即可跑实验 | 学生"真实知识"应与导师估计分离，否则结论循环 |
| 共同随机数配对 | 降低两组比较的方差 | 好做法；还应报告配对差值的置信区间 |
| 指标 = 掌握度估计之和 | 一行代码 | 真实研究必须用独立的前测/后测；讲义要求报告 learning gain 和置信区间 |
| 掌握全部概念后 `break` | 表示"课程结束" | 高能力学生剩余轮次被浪费，导致自适应组在指标上吃亏 |
| 只有文本信号（对/错） | 演示学习者模型 | 讲义要求 correct / partial / stuck 三类信号以及语音、拍照输入 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，让 `str | None` 等写法在旧版本也能作注解使用 |
| `@dataclass` | `class BKTParams:`、`class Concept:` | 自动生成 `__init__`、`__repr__`、`__eq__`；字段带类型注解和默认值 |
| `field(default_factory=...)` | `field(default_factory=list)` | 可变默认值必须用工厂，每个实例得到新的列表/字典 |
| `defaultdict` | `defaultdict(lambda: 0.2)` | 访问不存在的键时调用工厂生成默认值，并**写入**字典 |
| `lambda` 嵌套 | `default_factory=lambda: defaultdict(lambda: 0.2)` | 外层 lambda 是"如何创建字典"，内层是"字典的默认值" |
| 类型注解 | `def next_concept(...) -> str | None`、`list[tuple[str, bool]]` | `X | None` 表示可能为空；内置泛型 `list[...]`、`dict[...]` |
| 字典推导式 | `{c.name: c for c in concepts}` | 一行建索引 |
| 生成器表达式 + `all` | `all(state.mastery[pr] >= t for pr in c.prereqs)` | 惰性逐个判断，遇到 `False` 立即停止；空序列返回 `True` |
| `max(x, 1e-6)` 防除零 | `num / max(denom, 1e-6)` | 数值保护的常见写法 |
| `random.Random` 实例 | `random.Random(seed)`、`rng.gauss(0.3, 0.4)` | 独立随机数生成器，不影响全局 `random` 状态 |
| `getstate` / `setstate` | `r_base.setstate(r_adapt.getstate())` | 复制随机数生成器的内部状态，得到完全相同的序列 |
| 函数内 import | `import math`（在 `simulate_answer` 里） | 合法但不推荐；模块只会真正加载一次 |
| 取模轮转 | `order[i % len(order)]` | 循环遍历列表 |
| 嵌套函数 | `def mean(xs): return sum(xs) / len(xs)`（在 `main` 里） | 局部辅助函数；标准库也有 `statistics.mean` |
| 元组解包遍历 | `for c, ok in state.history:` | 每个元素是 `(概念, 是否答对)` |
| f-string 格式符 | `{delta:+.2f}`、`{c:34s}`、`{m:.2f}` | `+` 强制显示正负号；`34s` 左对齐占 34 格；`.2f` 两位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，不到 1 秒）：

```text
=== 2-week efficacy study (simulated) ===
curriculum: 11 concepts
adaptive mastery sum  mean=9.81
baseline mastery sum  mean=8.45
delta (adaptive - baseline): +1.36 mastery points over 60 turns

=== sample trajectory (adaptive learner 0) ===
  number_line                        mastery=0.93
  addition_subtraction               mastery=0.90
  multiplication_division            mastery=0.93
  negative_numbers                   mastery=0.93
  equality                           mastery=0.93
  isolating_variable_one_step        mastery=0.93
  isolating_variable_two_step        mastery=0.90
  distributive_property              mastery=0.55
```

逐项解读：

- **满分参照**：11 个概念，掌握度之和的上限是 11，初始是 2.2。自适应 9.81 相当于平均每个概念 0.89。
- **大量 0.93**：就是"连续答对两次"的值 0.9269（0.2 → 0.648 → 0.927）。0.90 的两个概念各有一次答错（例如 `addition_subtraction` 的历史是 错、对、对）。
- **示例轨迹**：20 轮里依次练了 8 个概念，最后 4 轮都在 `distributive_property` 上（错、错、错、对），所以停在 0.55。另外 3 个概念（`combining_like_terms`、`linear_equations`、`quadratic_basics`）在 20 轮内还没轮到，`history` 里只有 8 个概念，所以 `[:8]` 恰好全部打印。

把研究拆到每个学习者（额外脚本实测，列为：能力值、自适应、基线、自适应实际轮数）：

```text
0  -0.052   8.99   6.52  60
1   0.190  10.14   9.57  39
2   0.485  10.09  10.84  32   ← 基线更高
3   0.027  10.01   8.62  46
4  -0.066   9.97   7.74  57
5   0.276   9.72   7.58  60
6  -0.631   9.07   5.81  60
7   0.847  10.09  10.76  31   ← 基线更高
8   0.645   9.99   8.64  47
9   0.563  10.04   8.41  45
```

- 能力越低，自适应优势越大（学习者 6：+3.26）：基线会给低能力学生出没打好地基的难题，自适应坚持先修顺序。
- 能力高的学生（2、7）只用 31–32 轮就"学完"，随后 `break`，而基线用满 60 轮，因此反超。
- 扫描轮数：20 轮时 5.69 vs 6.04（自适应落后），30 轮时 7.38 vs 7.03，120 轮时 10.06 vs 10.04（基本持平）。**+1.36 只是 60 轮这一个设定下的数字**。
- 如果掌握全部概念后转入"练最弱概念"的复习模式，60 轮的自适应均值升到约 9.99。

结论：代码确实演示了闭环，但"自适应赢 1.36 分"的结论受轮数、`break` 行为和循环评价指标影响很大，不能当作效果证据——这也正是讲义坚持做真实前测/后测研究的原因。

---

## 7. 动手改一改

1. **修注释与 `p_init`**：把 `p_slip` 注释改成 "incorrect despite knowing"；让 `LearnerState` 的默认掌握度来自 `BKTParams().p_init`，改成 0.1 后重跑，观察均值变化。
2. **复习模式**：把 `next_concept` 改为全部掌握后返回最低掌握度的概念（见测验 Q12），对比 `n_turns = 20 / 60 / 120` 的 delta。
3. **修正动作作用对象**：让 `last_action` 只在"本轮概念 == 上一轮概念"时生效；删掉直接改 `state.mastery` 的 +0.02，改为让 celebrate 下一题难度 +0.05（"挑战题"），比较 delta。
4. **分离真实知识与估计**：为模拟学生加一个隐藏的 `true_known[concept]`（初始按 `p_init` 抽样，每次练习以 `p_learn` 概率变为 True），作答用 `true_known` 而非 `state.mastery`；最后用"每个概念 5 道独立后测题"的正确率作为指标。这对应讲义练习 1。
5. **加入遗忘与间隔复习**：每过一轮，未练习概念的掌握度乘以衰减因子；用类似 TS 版 `scheduleNextDue` 的到期时间决定复习时机。
6. **统计报告**：对 10 对学习者计算配对差值的均值、标准差和 bootstrap 95% 置信区间，再把学习者数扩大到 100，看区间如何收窄。

---

## 8. 常见坑

- **把 slip 和 guess 搞反**：会让答对时掌握度几乎不涨。检查方法：从 0.2 答对一次应明显上升（默认参数到 0.648）。
- **漏掉学习转移**：只做贝叶斯后验，掌握度会偏低，且答错后可能降到接近 0。
- **`defaultdict` 的副作用**：读取也会写入键；用 `len(state.mastery)` 判断"练过几个概念"会得到错误结果。
- **课程列表顺序被打乱**：`next_concept` 依赖拓扑序；如果有人把 `quadratic_basics` 挪到最前面，虽然先修检查会阻止选它，但遍历顺序变了，选择结果也会变。应显式做拓扑排序。
- **用模型估计评价模型**：`mastery_sum` 越高不代表学生学得越好，只代表导师更"相信"学生会了。
- **`break` 吞掉剩余轮次**：比较两组时，两组的"有效练习轮数"不同，比较就不公平。
- **随机流不同步**：如果某个分支额外调用了一次 `rng.random()`（例如加了随机出题），共同随机数配对就失效了；应让不同用途使用不同的 `Random` 实例。
