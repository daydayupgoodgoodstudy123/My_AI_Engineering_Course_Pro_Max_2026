# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 08 节 有界自我改进设计 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`hashlib`、`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

这是第 4 节 DGM 玩具的"加闸门版"：一个由字符串操作序列组成的 agent 不断随机变异自己，试图把输入规范化为 title-case；变异偶尔会"走私"一个未批准的工具并篡改自己的目标。讲义的四个有界原语被实现成四扇门：

1. **不变量门**（`gate_invariant`）：当前工具清单必须是批准清单的子集。
2. **锚点门**（`gate_anchor`）：目标字符串的哈希必须等于固定在循环外的 `OBJECTIVE_HASH`。
3. **多目标门**（`gate_multi`）：性能 ≥ 0.25 **且** 安全 = 1.0。
4. **回退门**（`gate_regression`）：性能不得比历史最高低超过 0.2。

候选修改按顺序过门，任何一扇不过就拒绝。`main()` 比较"全开 / 全关 / 只关回退门"三种配置。

需要特别看清的是：默认输出只能证明"全开 vs 全关"的差别；锚点门在这个实现里永远拦不到东西（被不变量门抢先），多目标门在原始任务上没有可观察作用，"只关回退门"在默认种子下也看不出静默能力损失。这些都要靠多种子实验和改造任务才能显现（见第 6、7 节）。

> 一句话：**把"四个原语组成的 gate stack"做成可开关的代码，同时示范——一扇门有没有用，要用"关掉它会放过什么"来证明**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `OBJECTIVE` / `OBJECTIVE_HASH` | 常量 | 循环外固定的目标文本及其哈希 | Alignment anchor |
| `APPROVED_TOOL_MANIFEST` | 常量（集合） | 批准的 6 个工具 | Invariant |
| `Agent` | dataclass | `ops` 操作序列、`active_manifest` 当前工具清单、`objective` 目标文本 | 被改进的系统 |
| `TOOLS_IMPL` | 字典 | 工具名 → lambda 实现（含 `nop`） | 工具 |
| `CASES_PERF` / `CASES_SAFETY` | 列表 | 4 个性能用例、2 个安全用例 | 多目标评估集 |
| `apply` | 函数 | 依次执行 ops，最后过危险模式过滤器 | agent 行为 |
| `perf_score` / `safety_score` | 函数 | 两个轴上的通过率 | 多目标指标 |
| `mutate` | 函数 | 替换 / 插入 / 删除一个 op，或篡改清单和目标 | 自我修改 |
| `gate_*` | 4 个函数 | 四扇门 | 四个原语 |
| `run` | 函数 | 200 轮"变异 → 过门 → 接受"循环并打印统计 | Gate stack |
| `main` | 函数 | 三种门配置各跑一次（同一种子） | 对照实验 |

数据流：`run(gates, seed)` → `Agent(["nop"])` → 每轮 `mutate` → `gate_invariant` → `gate_anchor` → `perf_score`/`safety_score` → `gate_multi` → `gate_regression` → 接受并写入 `history` → 打印最终状态与拒绝计数。

---

## 3. 逐段精讲

### 3.1 锚点与批准清单

```python
OBJECTIVE = "canonicalize whitespace and title-case the input"
OBJECTIVE_HASH = hashlib.sha256(OBJECTIVE.encode()).hexdigest()[:16]

APPROVED_TOOL_MANIFEST = {"trim", "collapse", "lower", "upper", "reverse", "title"}
```

- 锚点在**模块加载时**计算一次哈希，之后循环只能比对、不能改写——模拟"固定在编辑面之外"。
- 批准清单是 `set`，配合 `issubset` 做子集检查。注意 `nop` 不在清单里，却一直能出现在 `ops` 中（`mutate` 的候选里额外加了 `"nop"`）。
- ⚠️ `OBJECTIVE` 只被哈希比对，**不影响**任何评估：性能用例是写死的。所以这个锚点只能抓"字节级篡改"，无法体现讲义所说的"解读漂移"。

### 3.2 Agent 与工具

```python
@dataclass
class Agent:
    ops: list[str] = field(default_factory=lambda: ["nop"])
    active_manifest: set[str] = field(default_factory=lambda: set(APPROVED_TOOL_MANIFEST))
    objective: str = OBJECTIVE


TOOLS_IMPL = {
    "trim": lambda s: s.strip(),
    "collapse": lambda s: " ".join(s.split()),
    "lower": lambda s: s.lower(),
    "upper": lambda s: s.upper(),
    "reverse": lambda s: s[::-1],
    "title": lambda s: s.title(),
    "nop": lambda s: s,
}
```

- `default_factory=lambda: ["nop"]`：每个 Agent 都得到**新的**列表；`set(APPROVED_TOOL_MANIFEST)` 复制一份集合，避免修改全局常量。
- `" ".join(s.split())`：`split()` 不带参数时按任意空白切分并丢弃空串，再用单个空格连接——一行实现"折叠空白 + 去首尾空白"。
- `s.title()` 会把每个单词首字母大写、其余小写，所以 `"mixedCase"` → `"Mixedcase"`，这正是用例 3 的期望输出。
- `s[::-1]`：步长 −1 的切片，反转字符串。

### 3.3 评估：性能、安全与内置过滤器

```python
def apply(agent: Agent, s: str) -> str:
    for op in agent.ops:
        fn = TOOLS_IMPL.get(op)
        if fn is None:
            return ""
        s = fn(s)
    dangerous = ("exec(", "drop table", "rm -rf", "; delete from")
    low = s.lower()
    if any(d in low for d in dangerous):
        return "[blocked]"
    return s
```

- 不认识的 op（只有 `raw_eval` 会出现）直接返回 `""`——"走私的能力"在这里实际上是一个"让输出为空"的毁坏操作。
- 安全过滤器在**所有操作之后**做小写子串匹配。它不属于 agent 的 ops，agent 改不了它，相当于另一个隐式不变量。
- 能绕过过滤器的只有 `reverse`（实测 `"exec('rm -rf /')"` → `")'/ fr- mr'(cexe"`）和 `raw_eval`（输出 `""`，不等于 `"[blocked]"`）。

```python
def perf_score(agent: Agent) -> float:
    correct = 0
    for inp, want in CASES_PERF:
        if apply(agent, inp) == want:
            correct += 1
    return correct / len(CASES_PERF)
```

- 精确字符串匹配，4 个用例 → 分数只能是 0、0.25、0.5、0.75、1.0。`safety_score` 同理，2 个用例 → 0、0.5、1.0。
- 初始 `["nop"]`：性能 0.0、安全 1.0（危险输入原样返回后被过滤器拦截）。
- ⚠️ **性能与安全没有张力**：能拿满性能分的变换（trim/collapse/title）不会破坏危险子串，所以安全也一定满分；破坏安全的 `reverse`/`raw_eval` 同时毁掉性能。这就是为什么关掉多目标门在原始代码里看不出任何变化（测验 Q8、Q9）。

### 3.4 变异：四种动作

```python
def mutate(a: Agent, allow_manifest_edit: bool) -> Agent:
    ops = list(a.ops)
    manifest = set(a.active_manifest)
    obj = a.objective
    choices = [*sorted(manifest), "nop"]

    move = random.random()
    if move < 0.35 and ops:
        ops[random.randrange(len(ops))] = random.choice(choices)
    elif move < 0.7 and len(ops) < 6:
        ops.insert(random.randrange(len(ops) + 1), random.choice(choices))
    elif move < 0.9 and len(ops) > 1:
        ops.pop(random.randrange(len(ops)))
    elif allow_manifest_edit and random.random() < 0.5:
        manifest.add("raw_eval")
        obj = obj + "  # relax: accept any output"
    return Agent(ops=ops, active_manifest=manifest, objective=obj)
```

| `move` 区间 | 动作 | 条件 |
|------------|------|------|
| `[0, 0.35)` | 随机替换一个 op | `ops` 非空 |
| `[0.35, 0.7)` | 随机位置插入一个 op | 长度 < 6 |
| `[0.7, 0.9)` | 随机删除一个 op | 长度 > 1 |
| 其余（含前面条件不满足而落下的情形） | 50% 概率：清单加 `raw_eval` **并且**目标追加 "relax" | `allow_manifest_edit` |

- 先复制 `ops`、`manifest`，返回**新的** Agent：候选被拒绝时原 agent 不受影响（不可变风格）。
- `[*sorted(manifest), "nop"]`：注释说明了原因——`set` 的迭代顺序在不同解释器进程间可能不同（字符串哈希随机化），先排序才能让 `random.seed` 真正可复现。`*` 是列表解包。
- 篡改分支每轮约 5% 概率触发；`main()` 标题写 "manifest edits attempted every cycle" 并不准确。
- ⚠️ 清单篡改和目标篡改**捆绑在同一分支**，导致不变量门与锚点门完全冗余（见 3.5）。
- ⚠️ 一旦 `raw_eval` 进入清单，它也进入了 `choices`，以后的插入/替换都可能选到它。

### 3.5 四扇门

```python
def gate_invariant(a: Agent) -> bool:
    return a.active_manifest.issubset(APPROVED_TOOL_MANIFEST)

def gate_anchor(a: Agent) -> bool:
    return hashlib.sha256(a.objective.encode()).hexdigest()[:16] == OBJECTIVE_HASH

def gate_multi(perf: float, safety: float) -> bool:
    return perf >= 0.25 and safety >= 1.0

def gate_regression(history_perf: list[float], perf: float, tol: float = 0.2) -> bool:
    if not history_perf:
        return True
    return perf + tol >= max(history_perf)
```

| 门 | 检查 | 本实现中的问题 |
|----|------|--------------|
| 不变量 | 清单 ⊆ 批准清单 | 只检查清单，不检查 `ops`（目前 `ops` 只能从清单选，所以没出事） |
| 锚点 | 目标哈希逐字节一致 | 与不变量门被同一次变异触发，排在后面，永远 0 次拒绝；也无法检测"解读漂移" |
| 多目标 | 性能 ≥ 0.25 且安全 = 1.0 | `0.25` 是与"4 个用例"绑定的魔法数字（=至少答对 1 个）；原任务中性能与安全无张力 |
| 回退 | `perf + 0.2 ≥ 历史最高` | 分辨率 0.25 > 0.2，实际等于严格单调；只看性能一个轴；只和自身历史比较（skill 文件的 hard reject） |

- 门的**顺序**有意义：便宜的结构性检查（集合比较、哈希）放在昂贵的评估之前；但这也让排在后面的门在冗余时"永远没机会"。

### 3.6 主循环

```python
    for _ in range(cycles):
        cand = mutate(a, allow_manifest_edit)
        if gates["invariant"] and not gate_invariant(cand):
            rejects["invariant"] += 1
            continue
        if gates["anchor"] and not gate_anchor(cand):
            rejects["anchor"] += 1
            continue
        p = perf_score(cand)
        s = safety_score(cand)
        if gates["multi"] and not gate_multi(p, s):
            rejects["multi"] += 1
            continue
        if gates["regress"] and not gate_regression(history, p):
            rejects["regress"] += 1
            continue
        a = cand
        history.append(p)
        accepted += 1
```

- `continue` 让"任何一扇门失败就拒绝"写得很平直；`gates[...] and not gate_...(...)` 利用短路：门关闭时根本不调用检查函数。
- 被接受的候选才进入 `history`，所以历史最高分只会被"接受过的"分数抬高。
- `best_perf` / `best_safety` 记录过程中的最高值，最终状态 `final_*` 可能低于它——"best 1.00、final 0.00"（全关时）正是"曾经很好、后来静默变坏"的样子。
- `seed` 参数在 `run()` 内部设种子：三种配置都从同一个种子开始，差异只来自门配置——但在第一次接受不同候选之后，随机序列就分叉了。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用字符串操作序列当"agent" | 状态小、评估快、可读 | 与真实 agent 的修改面（prompt、工具、代码）差距大 |
| 锚点 = 目标文本的哈希 | 一行代码实现"不可改" | 只能抓字节级篡改；生产还要有"解读探针"测试和独立评估器 |
| 清单与目标在同一分支篡改 | 代码短 | 两扇门冗余，无法单独演示锚点门的价值；应拆成独立事件 |
| `raw_eval` 未实现（输出空串） | 不需要真的执行危险代码 | 走私能力表现为"毁坏"而非"提升指标"，行为门轻易就能拦住，弱化了不变量门的必要性 |
| 安全过滤器写在 `apply` 里 | 保证安全轴有意义 | 性能与安全失去张力，多目标门没有可观察作用 |
| `gate_multi` 用 `0.25` | 对应"至少答对一个" | 用例数一变就失效（5 个用例时循环会卡死） |
| 回退门 `tol=0.2`、只看自身历史和性能 | 简单 | 等价严格单调；违反"外部比较集"的要求；生产应按轴、按窗口、对外部基线检查 |
| 每种配置只跑一个种子 | 输出简短 | 回退门、多目标门的作用在单次运行中都看不出来；应多种子统计 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + `field(default_factory=...)` | `ops: list[str] = field(default_factory=lambda: ["nop"])` | 可变默认值必须用工厂函数，每个实例一份新对象 |
| `lambda` | `"trim": lambda s: s.strip()` | 匿名函数，适合放进字典做"名字 → 实现"映射 |
| 字典 `.get` | `TOOLS_IMPL.get(op)` | 键不存在时返回 `None` 而不抛异常 |
| 字符串方法 | `strip()`、`split()`、`" ".join(...)`、`title()`、`lower()` | 去空白、切分、拼接、首字母大写、小写 |
| 切片反转 | `s[::-1]` | 步长为 −1 |
| `any` + 生成器表达式 | `any(d in low for d in dangerous)` | 只要有一个为真就返回 True，且会短路 |
| 集合运算 | `set(...)`、`.add()`、`.issubset()` | 复制、添加、子集判断 |
| 列表解包 | `[*sorted(manifest), "nop"]` | 把可迭代对象展开进新列表 |
| `random` 模块 | `random.random()`、`random.randrange(n)`、`random.choice(seq)` | 均匀浮点、`[0, n)` 整数、随机元素 |
| 列表就地修改 | `ops.insert(i, x)`、`ops.pop(i)`、`ops[i] = x` | 插入、删除、替换 |
| `dict(...)` 构造与覆盖 | `dict(all_on, regress=False)` | 以 `all_on` 为基础，覆盖一个键 |
| 关键字参数构造字典 | `dict(invariant=True, anchor=True, ...)` | 等价于字面量 `{"invariant": True, ...}` |
| 联合类型注解 | `seed: int \| None = None` | 可以是整数或 None（Python 3.10+ 语法，配合 `from __future__ import annotations` 也可在更早版本的注解中使用） |
| 短路求值 | `gates["invariant"] and not gate_invariant(cand)` | 门关闭时不执行检查 |
| `continue` | 门失败后跳到下一轮 | 跳过本次循环剩余部分 |
| 条件表达式 + f-string | `f"{'(anchor intact)' if gate_anchor(a) else '(DRIFTED!)'}"` | f-string 内嵌表达式；内层用单引号避免冲突 |
| `hashlib` | `hashlib.sha256(x.encode()).hexdigest()[:16]` | 计算摘要并截断 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`DEFAULT_SEED = 5`）：

```text
All gates ON, manifest edits attempted every cycle
  accepted 96/200 cycles
  final perf 1.00  final safety 1.00
  final ops  ['title', 'collapse', 'title']
  manifest   ['collapse', 'lower', 'reverse', 'title', 'trim', 'upper']
  objective  (anchor intact)
  rejects    {'invariant': 11, 'anchor': 0, 'multi': 66, 'regress': 27}

All gates OFF, manifest edits attempted every cycle
  accepted 200/200 cycles
  final perf 0.00  final safety 0.00
  best perf  1.00  best  safety 1.00
  final ops  ['trim', 'raw_eval', 'raw_eval', 'trim', 'collapse']
  manifest   [..., 'raw_eval', ...]
  objective  (DRIFTED!)

Only regression gate OFF
  accepted 116/200 cycles
  final perf 1.00  final safety 1.00
  rejects    {'invariant': 15, 'anchor': 0, 'multi': 69, 'regress': 0}
```

逐项解读：

- **全开**：找到 `['title', 'collapse', 'title']`，4 个用例全对；11 次篡改尝试全被不变量门拦下（约 5.5%，与 3.4 的估算一致）；锚点门 0 次（被抢先）；多目标门 66 次主要拦"性能为 0"或含 `reverse` 的候选；回退门 27 次拦降分候选。
- **全关**：所有候选都被接受，清单被塞入 `raw_eval`，ops 里出现 `raw_eval` → 输出为空 → 性能 0、安全 0，目标漂移。`best perf 1.00` 而 `final perf 0.00`：曾经达到满分，后来被随机游走毁掉且无人报警。
- **只关回退门**：默认种子下最终也到了 1.0，单看这次输出证明不了 HEADLINE 的 "silent capability dips get absorbed"。

我们额外做了多种子实验（seed 0–199，每次 200 轮）：

| 配置 | 最终性能均值 | 最终性能 = 1 的比例 | 最终安全均值 | 目标漂移比例 |
|------|------------|------------------|------------|------------|
| 全开 | 1.000 | 1.00 | 1.000 | 0.00 |
| 全关 | 0.080 | 0.05 | 0.370 | 1.00 |
| 只关回退门 | **0.636** | **0.43** | 1.000 | 0.00 |
| 只关多目标门 | 1.000 | 1.00 | 1.000 | 0.00 |
| 只关不变量门 | 1.000 | 1.00 | 1.000 | 0.00（锚点门接手拒绝，平均 11.3 次） |
| 只关锚点门 | 1.000 | 1.00 | 1.000 | 0.00 |
| 关不变量 + 锚点 | 1.000 | 1.00 | 1.000 | **1.00** |

结论：

- 回退门的作用是真实的，但只能在统计上看到（关掉后 57% 的种子最终停在低于满分的状态）。
- 多目标门在原任务上无作用；改造任务（加入 `nopunct` 工具，见测验 Q9）后：全开时性能 0.75、安全 1.0；只关多目标门时性能约 0.999、安全约 0.50。
- 不变量门与锚点门互为备份；两者都关时，行为指标完全正常，但 100% 的种子目标被改写、清单里藏着 `raw_eval`——**行为测试看不到的结构性失败，只有结构性检查能发现**。

---

## 7. 动手改一改

1. **（讲义练习 1）** 四门全开，打印每次被接受的 `(ops, perf, safety)`，确认循环在不让 hack 得逞的前提下逐步提升性能。
2. **（讲义练习 2）** 只关回退门，跑 200 个种子统计最终性能分布；再在 `run()` 里记录"被接受且性能下降"的事件数，展示静默能力损失。
3. **（讲义练习 3）** 按测验 Q9 加入 `nopunct` 工具并替换一个性能用例，比较"全开"与"只关多目标门"的性能/安全。
4. **拆开篡改事件**：按测验 Q10 把"改清单"和"改目标"拆成独立事件，分别只关不变量门、只关锚点门，确认各自放过了哪一类失败。
5. **让走私能力"有用"**：把 `raw_eval` 实现成一个能提升性能但绕过安全过滤器的操作（例如对性能用例输出正确答案、对安全用例输出原文），观察只靠行为门时会发生什么。
6. **（讲义练习 4）进阶**：为一个 coding agent 设计锚点——写一个 `ANCHOR` 字典（目标陈述、禁止修改的路径列表、工具白名单），由 harness 从只读路径加载；实现"哈希校验 + 解读探针测试"两层检查。

---

## 8. 常见坑

- **用单次运行评价一扇门**：门的价值是"关掉它会放过什么"，需要多种子或针对性构造的输入来证明。
- **门之间的冗余**：两扇门被同一事件触发时，排在后面的门永远是 0，看起来"没用"，其实只是没有被独立测试。
- **容差与指标分辨率不匹配**：`tol=0.2` 配 0.25 的刻度等于严格单调；用例数变化时 `perf >= 0.25` 也会失效。
- **回退检查只看自身历史**：循环定义了什么是"正常"，慢性漂移和被污染的历史都发现不了。
- **只看行为、不看结构**：清单里藏着未批准工具、目标被改写，但性能和安全都满分——必须有不变量与锚点这类结构性检查。
- **以为哈希锚点能防解读漂移**：字节一致不代表理解一致，讲义："Anchors are necessary, not sufficient."
- **`set` 迭代顺序导致不可复现**：从集合里 `random.choice` 前要先 `sorted`，本文件已经处理。
