# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 11 节 结合 HTN 与演化搜索的 Planning ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`、`typing`）；不需要 API key、不需要网络

---

## 1. 这份代码在考察什么

一个文件里放了两个互不相关的小 demo，分别对应讲义里两种"把 LLM 当放大器而不是替代品"的规划范式：

1. **ChatHTN 风格的混合 HTN 规划器**：符号规划器先用 method 库分解复合任务；没有可用 method 时才问"LLM"（这里是脚本化的 `ScriptedLLM`），LLM 的回答经过校验后才被采用，并被缓存以减少下次的 LLM 调用。考察点：operator 的前置条件 / 效果、method 分解、递归规划、"LLM 只提议、符号层负责正确性"。
2. **AlphaEvolve 风格的演化搜索（玩具）**：用确定性的 evaluator 给候选打分，保留最好的、变异、再打分，直到收敛到目标 `3x + 7`。考察点：种群、变异、精英选择，以及"fitness 必须确定、可机器检查"。

> 一句话：**符号层 / evaluator 掌握"对不对、好不好"的最终裁决权，LLM 只负责提出候选**。同时要看清代码的简化：LLM 是脚本、演化只调两个整数，且 HTN 部分有一个"先缓存后验证"的 bug。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Operator` | dataclass | 原子动作：前置条件、添加效果、删除效果；`applicable` / `apply` | HTN operator（STRIPS 风格） |
| `Method` | dataclass | 把某个复合任务分解为子任务序列，带前置条件 | HTN method |
| `ScriptedLLM` | 类 | 按字典返回预设分解，并记录被调用的任务 | ChatHTN 的 LLM fallback（离线替身） |
| `HTNPlanner` | dataclass | `plan` 递归规划；`_expand` 顺序展开子任务并模拟状态；`cached_methods` 缓存 LLM 分解 | ChatHTN 混合循环 + online method learning |
| `htn_demo` | 函数 | 3 个 case：method 命中 / LLM fallback / 缓存命中 | 演示 |
| `evolutionary_demo` | 函数 | 6 个体种群，12 代"保留前 3 → 各变异 3 个 → 取前 6" | AlphaEvolve 循环（玩具） |
| `main` | 函数 | 依次运行两个 demo 并打印结论 | 入口 |

数据流：
- Demo 1：`operators + methods + ScriptedLLM` → `HTNPlanner.plan(goal, state)` →（method / 缓存 / LLM）→ `_expand` 逐步检查前置条件并更新状态 → 计划列表。
- Demo 2：随机种子种群 → `evaluator` 打分排序 → 循环 { 取前 3 → `random_mutation` ×3 → 打分 → 合并排序取前 6 } → 最优个体。

---

## 3. 逐段精讲

### 3.1 `Operator`：前置条件 + 效果

```python
@dataclass
class Operator:
    name: str
    preconditions: tuple[str, ...]
    effects_add: tuple[str, ...]
    effects_remove: tuple[str, ...] = ()

    def applicable(self, state: set[str]) -> bool:
        return all(p in state for p in self.preconditions)

    def apply(self, state: set[str]) -> set[str]:
        new_state = set(state)
        for fact in self.effects_remove:
            new_state.discard(fact)
        for fact in self.effects_add:
            new_state.add(fact)
        return new_state
```

- 状态就是一个**事实集合** `set[str]`，例如 `{"logged_in", "editor_open"}`。这是经典 STRIPS 表示法：前置条件是"必须为真的事实"，效果分为"添加"和"删除"两组。
- `applicable`：所有前置条件都在状态里才可执行。
- `apply` **不修改原状态**，而是复制一份 `set(state)` 再改，返回新集合。这个"不可变风格"非常关键：规划失败时调用方的状态不受影响，所以以后加回溯时不需要手动撤销（见测验 Q10）。
- 先删后加：如果同一个事实既在 remove 又在 add，结果是"存在"。demo 中没有用到 `effects_remove`，所有效果都是单调增加的。

### 3.2 `Method`：分解规则

```python
@dataclass
class Method:
    name: str
    task: str
    preconditions: tuple[str, ...]
    subtasks: tuple[str, ...]
```

- 一个 method 说："当前置条件满足时，复合任务 `task` 可以分解为 `subtasks` 这一串子任务"。子任务可以是 operator 名，也可以是另一个复合任务名（递归分解）。
- method 的前置条件只在**分解时刻**检查；子任务各自的前置条件在展开过程中逐个检查。
- 规划器里 `methods` 的类型是 `dict[str, list[Method]]`：一个任务可以有多个备选 method。

### 3.3 `ScriptedLLM`：LLM 的离线替身

```python
class ScriptedLLM:
    def __init__(self, scripts: dict[str, tuple[str, ...]]) -> None:
        self._scripts = scripts
        self.calls: list[str] = []

    def decompose(self, task: str, state: set[str]) -> tuple[str, ...] | None:
        self.calls.append(task)
        return self._scripts.get(task)
```

- 真实的 ChatHTN 会把"任务 + 当前状态"写成 prompt 发给 LLM，再把自然语言回答解析成子任务列表。这里用字典代替，`state` 参数被**忽略**。
- `self.calls` 记录每次调用，用来在 demo 中证明"缓存命中后没有新的 LLM 调用"。
- 不认识的任务返回 `None`（`dict.get` 的默认值），代表"LLM 也不知道怎么分解"。
- ⚠️ 讲义说代码里有一个 `LLMFallback`，实际类名是 `ScriptedLLM`。

### 3.4 `HTNPlanner.plan`：混合规划的核心

```python
    def plan(self, task: str, state: set[str],
             depth: int = 0, max_depth: int = 12) -> list[str] | None:
        if depth > max_depth:
            return None
        if task in self.operators:
            op = self.operators[task]
            if op.applicable(state):
                return [task]
            return None
        applicable = [m for m in self.methods.get(task, []) if m.applicable(state)]
        if not applicable and task in self.cached_methods:
            subtasks = self.cached_methods[task]
            return self._expand(list(subtasks), state, depth)
        if not applicable:
            suggested = self.llm.decompose(task, state)
            if suggested is None:
                return None
            if not all(s in self.operators or s in self.methods for s in suggested):
                return None
            self.cached_methods[task] = suggested
            return self._expand(list(suggested), state, depth)
        method = applicable[0]
        return self._expand(list(method.subtasks), state, depth)
```

按顺序拆开看（对应讲义 ChatHTN 的 5 步循环）：

| 分支 | 条件 | 行为 | 对应讲义 |
|------|------|------|---------|
| 深度保护 | `depth > max_depth` | 返回 `None` | 防止 method 循环引用导致无限递归 |
| 原子任务 | `task in self.operators` | 可执行就返回 `[task]`，否则 `None` | operator |
| 缓存命中 | 无可用 method 且在缓存中 | 直接展开缓存的分解 | online method learning |
| LLM fallback | 无可用 method 且不在缓存中 | 问 LLM → 名字校验 → **写缓存** → 展开 | 第 2–5 步 |
| method 命中 | 有可用 method | 只取 `applicable[0]` 展开 | 第 1 步 |

几个值得注意的细节：

- **返回值约定**：成功返回原子步骤列表，失败返回 `None`。注意"空计划 `[]`"与"失败 `None`"不同——一个子任务为空的 method 会返回 `[]`，表示"什么都不用做就完成了"。
- **名字校验**只确认每个子任务是已知 operator 或在 `self.methods` 中有键；前置条件由 `_expand` 检查。两层合起来才构成讲义说的"validate against the operator schema"。
- ⚠️ **先缓存后验证（bug）**：`self.cached_methods[task] = suggested` 写在 `_expand` 之前。若展开失败，错误分解已被缓存；下次同一任务直接走缓存分支、再次失败，**再也不会问 LLM**。实测：新 planner 在空状态下请求 `ship_feature_with_migration`，返回 `None`，但缓存里已经留下了那条分解。修复见测验 Q9。
- ⚠️ **没有回溯**：有多个可用 method 时只试第一个；第一个展开失败就直接返回 `None`，既不试第二个 method，也不会回落到 LLM（讲义练习 1）。
- ⚠️ **缓存键只有任务名**：与讲义练习 2 的"task `T` in state pattern `P`"不同，同一任务在任何状态下都复用同一分解。
- 名字校验的一个副作用：只能靠 LLM 分解的复合任务（不在 `self.methods` 里）不能作为另一次 LLM 分解的子任务，会被拒绝。

### 3.5 `_expand`：顺序展开 + 状态模拟

```python
    def _expand(self, subtasks: list[str], state: set[str], depth: int) -> list[str] | None:
        plan: list[str] = []
        current_state = set(state)
        for subtask in subtasks:
            sub_plan = self.plan(subtask, current_state, depth=depth + 1)
            if sub_plan is None:
                return None
            for step in sub_plan:
                op = self.operators.get(step)
                if op is None or not op.applicable(current_state):
                    return None
                current_state = op.apply(current_state)
                plan.append(step)
        return plan
```

- 这是 soundness 真正被保证的地方：每个子任务先递归规划（基于**当前**模拟状态），然后把得到的每个原子步骤**重新检查前置条件**、应用效果、追加到计划。只要有一步不满足，整个展开失败。
- 子任务是复合任务时，递归调用里已经模拟过一遍；外层再重放一遍是冗余的，但能保证"无论子计划从哪儿来（method、缓存、LLM），进入最终计划的每一步都被检查过"。
- 以 case A 为例，状态推演：

| 步骤 | 前置条件 | 执行后状态 |
|------|---------|-----------|
| 初始 | — | `{logged_in}` |
| `open_editor` | `logged_in` | `+ editor_open` |
| `write_tests` | `editor_open` | `+ tests_written` |
| `run_tests` | `tests_written` | `+ tests_passing` |
| `open_pr` | `tests_passing` | `+ pr_open` |

- `plan()` 只返回步骤列表，不返回最终状态；也**没有检查目标条件**（例如结束时是否包含 `pr_open`）。HTN 的目标由任务本身表达，这在 HTN 中是常规做法，但也意味着"计划可执行"不等于"完成了真实意图"（见 3.6）。

### 3.6 `htn_demo`：三个 case

```python
    llm = ScriptedLLM({
        "ship_feature_with_migration": (
            "open_editor", "write_tests", "run_tests", "open_pr",
        ),
    })
```

- **case A**：`ship_change` 有 method `ship_change_m1`（前置 `logged_in`），直接展开，LLM 调用为空。
- **case B**：`ship_feature_with_migration` 没有 method、没有缓存 → 问 LLM → 名字都合法 → 写入缓存 → 展开成功。
- **case C**：同一任务再请求一次，命中缓存，新 LLM 调用为 0。
- ⚠️ 脚本里"带迁移的发布"返回的分解**没有任何迁移步骤**，与 `ship_change` 完全一样。计划在模型内 sound，却没有完成任务名所表达的意图——这正好说明 soundness 只保证"每一步可执行"，不保证"做对了事"。
- ⚠️ 讲义称 trace 会展示"mid-plan LLM fallback"，实际 fallback 发生在**顶层**目标任务上，而不是计划中途的某个子任务上。

### 3.7 `evolutionary_demo`：evaluator、变异与选择

```python
    def evaluator(a: int, b: int) -> float:
        total = 0.0
        for x in range(-5, 6):
            target = 3 * x + 7
            guess = a * x + b
            total += (target - guess) ** 2
        return total
```

- 在 x = −5..5 共 11 个点上计算平方误差之和。它是**确定、快速、可机器检查**的——这正是讲义对 AlphaEvolve evaluator 的硬要求。
- 闭式：`fitness = 110·(3−a)² + 11·(7−b)²`（因为 `Σx = 0`、`Σx² = 110`），已用 Python 在网格上逐点验证。`a` 偏 1 罚 110，`b` 偏 1 只罚 11，所以 `a` 会先收敛。
- ⚠️ 讲义说是最小化 `|f(x) − target|`、"grow expressions"；代码是平方误差、固定线性模板，只调两个整数。

```python
    def random_mutation(a: int, b: int) -> tuple[int, int]:
        da = random.choice((-2, -1, 0, 1, 2))
        db = random.choice((-2, -1, 0, 1, 2))
        return a + da, b + db
```

- 变异算子：每个系数独立加上 {−2..2} 中的一个数。有 1/25 的概率两个都取 0，产生与父代一模一样的"克隆"。
- ⚠️ 讲义说"ensemble mutations"，这里只有一个随机变异算子，没有任何 LLM。在 AlphaEvolve 中，这一步由 LLM ensemble 生成代码修改。

```python
    for gen in range(1, generations + 1):
        survivors = population[:3]
        children: list[tuple[int, int, float]] = []
        for a, b, _ in survivors:
            for _ in range(3):
                na, nb = random_mutation(a, b)
                children.append((na, nb, evaluator(na, nb)))
        population = sorted(survivors + children, key=lambda x: x[2])[:6]
```

- **精英保留（elitism）**：survivors 直接进入下一代，所以最优 fitness 单调不增。
- 每代 evaluator 调用 3 × 3 = 9 次；加上初始种群 6 次，全程共 114 次。
- 种群保留 6 个，但只有前 3 个当父代，第 4–6 名下一代就会被丢弃，实际起作用的种群只有 3。
- 没有去重：克隆和重复个体会挤占名额，实测后期种群里同时出现 2–4 个 `(3, 7)`，多样性下降。
- 没有早停：第 6 代就找到 fitness = 0，仍跑满 12 代。
- `random.seed(0)` 让结果完全可复现。注意它设置的是**全局**随机状态。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 状态 = 事实集合，效果 = add/remove | 最简单的 STRIPS 表示，易于检查前置条件 | 无法表达数值、时间、资源；生产可用 PDDL 或领域专用模型 |
| `apply` 返回新集合 | 规划失败不污染调用方状态 | 状态大时复制有开销；可用持久化数据结构 |
| 脚本化 LLM | 离线可复现，聚焦控制流 | 真实 LLM 需要 prompt、解析、重试；回答可能格式错误 |
| 名字校验 + `_expand` 逐步检查 | 两层校验实现"LLM 只提议" | 名字校验不允许嵌套 LLM 任务；应基于完整 schema 校验 |
| 先写缓存再展开 | 代码短 | 失败分解被永久缓存（bug）；应验证通过后再缓存 |
| 缓存键 = 任务名 | 简单 | 忽略状态差异；应按"任务 + 状态模式"缓存并泛化 |
| 只用 `applicable[0]` | 简单 | 无回溯；应遍历所有 method，再回落到缓存与 LLM |
| 演化只调 `(a, b)` | 闭式可算，几代就收敛 | 不是"程序搜索"；AlphaEvolve 演化的是代码 |
| 随机 ±2 变异 | 不依赖 LLM | 真实系统由 LLM ensemble 生成变异 |
| 精英保留 + 截断选择 | 最优单调不退化 | 易丢失多样性；生产会去重、分岛、保留多样个体 |
| 固定 12 代 | demo 简单 | 应加早停（达到阈值或连续 k 代无改进） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，使 `tuple[str, ...] \| None` 等写法在旧版本中也能用作注解 |
| `@dataclass` | `class Operator`、`class HTNPlanner` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| 带默认值的字段 | `effects_remove: tuple[str, ...] = ()` | 有默认值的字段必须放在无默认值字段之后 |
| `field(default_factory=dict)` | `cached_methods: dict[...] = field(default_factory=dict)` | 可变默认值必须用工厂函数，否则所有实例共享同一个 dict |
| 类型注解 | `tuple[str, ...]`、`dict[str, list[Method]]`、`list[str] \| None` | `...` 表示任意长度的同类型元组；`X \| None` 表示可能为 None |
| `all()` + 生成器表达式 | `all(p in state for p in self.preconditions)` | 全部为真才返回 True；空序列返回 True（无前置条件即可执行） |
| 集合操作 | `set(state)`、`.discard(fact)`、`.add(fact)` | `discard` 删除不存在的元素不会报错（`remove` 会） |
| `dict.get(key, default)` | `self.methods.get(task, [])`、`self._scripts.get(task)` | 键不存在时返回默认值（不写默认值就是 None） |
| 列表推导式 + 条件 | `[m for m in ... if m.applicable(state)]` | 过滤出可用 method |
| 递归 + 关键字参数 | `self.plan(subtask, current_state, depth=depth + 1)` | 通过 `depth` 控制递归深度 |
| 嵌套函数 | `evolutionary_demo` 里的 `evaluator`、`random_mutation` | 只在本函数内使用的辅助函数 |
| `random.seed` / `choice` / `randint` | `random.seed(0)`、`random.choice((-2, ..., 2))` | 固定种子可复现；`randint` 两端都包含 |
| 元组解包与 `_` | `for a, b, _ in survivors` | `_` 表示不需要的值 |
| `sorted(..., key=lambda x: x[2])[:6]` | 选择步骤 | 按第 3 个元素（fitness）升序排序后切片取前 6 |
| f-string 格式符 | `{a:3d}`、`{fit:.2f}`、`{gen:02d}` | 宽度 3 的整数；2 位小数；宽度 2 补零 |
| 字符串乘法 | `"-" * 70` | 打印分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3，`cd code && python3 main.py`，瞬间完成）：

```text
case A: goal=ship_change (method library matches)
  plan: ['open_editor', 'write_tests', 'run_tests', 'open_pr']
  llm calls: []                                   ← method 命中，不问 LLM

case B: goal=ship_feature_with_migration (no method -> LLM fallback)
  plan: ['open_editor', 'write_tests', 'run_tests', 'open_pr']
  llm calls (cumulative): ['ship_feature_with_migration']   ← 第一次问 LLM
  cache hit for next time: {'ship_feature_with_migration': ('open_editor', 'write_tests', 'run_tests', 'open_pr')}

case C: goal=ship_feature_with_migration (cached now -> no LLM call)
  plan: ['open_editor', 'write_tests', 'run_tests', 'open_pr']
  new LLM calls this round: 0  (expect 0)         ← 缓存命中

seed population (a*x + b, target 3x + 7)
  a=  2  b=  3  fitness=286.00                    ← 110·1 + 11·16
  a=  2  b= -1  fitness=814.00                    ← 110·1 + 11·64
  a=  5  b=  1  fitness=836.00                    ← 110·4 + 11·36
  gen 03: best a=  3 b=  4 fitness=99.00
  gen 06: best a=  3 b=  7 fitness=0.00           ← 第 6 代已找到精确解
  gen 09: best a=  3 b=  7 fitness=0.00
  gen 12: best a=  3 b=  7 fitness=0.00

converged on: a=3  b=7  fitness=0.00
expected:     a=3    b=7    fitness=0.00
```

逐项解读：

- **三个 case 的计划完全相同**：因为脚本 LLM 返回的分解和 `ship_change_m1` 一样。区别只在"计划从哪儿来"：method / LLM / 缓存。
- **种子种群**一共 6 个，只打印前 3 个。用闭式可以逐个验算。
- **逐代最优**（用探针脚本打印每一代）：`(2,3) 286 → (3,3) 176 → (3,4) 99 → (3,5) 44 → (3,6) 11 → (3,7) 0`。`a` 第 2 代就到 3（`a` 方向罚分大 10 倍，选择压力集中在它上面），之后 `b` 每代前进 1。
- **evaluator 调用**：全程 114 次，其中到第 6 代找到解时已用 60 次；后面 54 次是白跑的。

额外的探针实验（不修改源码，导入后调用）：

| 实验 | 结果 | 说明 |
|------|------|------|
| 新 planner，空状态请求 `ship_feature_with_migration` | 返回 `None`，但缓存已写入该分解 | "先缓存后验证"的 bug |
| LLM 对 `bad` 返回 `("open_pr",)`，状态 `{"logged_in"}` | 返回 `None`，`bad` 被缓存 | 名字合法但前置条件不满足 |
| LLM 返回未知名字 `("deploy",)` | 返回 `None`，不缓存 | 名字校验拒绝 |
| 之后在 `{"tests_passing"}` 下请求 `bad` | `['open_pr']` | 缓存不看状态，换个状态就"碰巧"成功 |

---

## 7. 动手改一改

1. **修复缓存 bug**：把 `self.cached_methods[task] = suggested` 移到 `_expand` 成功之后，并让缓存展开失败时回落到 LLM。用"空状态请求 `ship_feature_with_migration`"验证缓存为空（参考测验 Q9）。
2. **加回溯（讲义练习 1）**：给 `ship_change` 再加一个 method，使第一个 method 展开失败、第二个成功；改写 `plan()` 依次尝试所有可用 method，再回落到缓存与 LLM（参考测验 Q10）。
3. **状态感知缓存（讲义练习 2）**：缓存键改为 `(task, frozenset(状态中与分解相关的事实))`；查找时检查"模式 ⊆ 当前状态"（参考测验 Q11）。
4. **加目标条件**：给 `plan()` 增加 `goal_facts` 参数，要求最终状态包含它们；给 `ship_feature_with_migration` 增加 `migration_applied` 目标，观察脚本 LLM 的分解被拒绝，然后补一个 `run_migration` operator 修正脚本。
5. **演化加早停与去重**：fitness 为 0 或连续 3 代无改进即停；合并种群时去掉重复的 `(a, b)`。统计 evaluator 调用次数（应从 114 降到 60 左右）。
6. **真正的程序搜索（讲义练习 3）**：把个体换成排序函数的源代码字符串，用 20 个测试用例做 evaluator（通过数为 fitness，抛异常给 0 分），变异用规则化的代码改写（或接入 LLM），报告收敛代数。

---

## 8. 常见坑

- **把 LLM 的分解直接当计划执行**：失去 HTN 的全部保证。LLM 输出必须先做 schema 校验，再逐步检查前置条件。
- **先缓存后验证**：失败结果被"学习"成规则，系统会稳定地重复同一个错误，而且不再给 LLM 纠正的机会。
- **缓存不看状态**：同一任务在不同状态下需要不同分解；缓存命中后仍必须走前置条件检查。
- **以为 sound 就等于完成任务**：计划在模型内可执行，不代表达到了目标（demo 中"带迁移的发布"没有迁移步骤）。需要目标条件或验收检查。
- **深度上限设得太小**：`max_depth=12` 对 demo 足够，但真实领域分解层数较多时会误判为无解；设得太大则 method 循环时浪费时间。
- **evaluator 不确定**：比如测性能时不固定输入、不取中位数，或者用 LLM 打分，演化会追逐噪声。
- **只按 fitness 截断选择**：种群很快被同一个体的克隆占满，在多峰问题上容易陷入局部最优。
- **全局 `random.seed`**：在更大的程序里会影响其他模块的随机数；生产中用 `random.Random(seed)` 的独立实例。
