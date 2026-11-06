# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 02 节 ReWOO 与 Plan-and-Execute：解耦 Planning ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`re`、`dataclasses`、`typing`）；无需 API key、无需网络

---

## 1. 这份代码在考察什么

这份约 200 行的代码用"脚本化的 Planner 和 Solver + 真实执行的 Worker"复现 ReWOO（Xu 等，arXiv:2305.18323）的三段式结构：

1. **计划 DAG 的表示**：`PlanStep(id, tool, args)`，参数里的 `#E1`、`#E2` 既是占位符，也隐式定义了依赖边。
2. **依赖解析**：`topological` 用正则找出每个节点引用的前序节点，排出可执行顺序，并在有环或悬空引用时报错。
3. **引用替换**：`resolve_references` 在分派前把 `#E1` 换成前序 worker 的输出——讲义"substituted with prior worker output at dispatch time"。
4. **Solver 汇总**：把问题、计划和证据组合成最终答案。
5. **token 直觉**：`run_rewoo` 与 `run_react_mock` 用字符数粗略对比"一次规划"与"每步携带全部历史"的成本差异。

> 一句话：**先把整张计划画出来，再按依赖把证据一块块填进去，最后一次性作答**。代码只演示了 ReWOO 的骨架，"并行执行""Solver 优雅降级""计划校验"都还没有实现，这些恰恰是练习和面试的重点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PlanStep` / `Plan` | dataclass | 计划节点（id、工具名、参数）与节点列表 | 计划 DAG |
| `ToolRegistry` | 类 | 注册工具、按名分派，异常转成 `error:` 字符串 | Worker 的执行后端 |
| `REFERENCE_RE` | 编译好的正则 | 匹配 `#E(\d+)` | 证据引用 |
| `resolve_references` | 函数 | 把字符串里的 `#Ek` 替换成 `evidence["Ek"]` | 分派时替换 |
| `topological` | 函数 | 依据引用关系排序；无进展时抛 `RuntimeError` | DAG 执行器 |
| `run_workers` | 函数 | 按拓扑序逐个执行节点，收集 `evidence` | Workers |
| `ScriptedPlanner` | 类 | 无视问题，直接返回预设计划 | Planner（被脚本替代） |
| `ScriptedSolver` | 类 | `template.format(**evidence)` | Solver（被脚本替代） |
| `fake_search` / `rounded_million` | 函数（工具） | 关键字匹配的假搜索；从文本中提取数字并四舍五入到百万 | 示例工具 |
| `ReWOORun` | dataclass | 一次运行的问题、计划、证据、答案和三段字符数 | 运行记录 |
| `run_rewoo` | 函数 | Planner → Workers → Solver，并统计字符数 | ReWOO 主流程 |
| `run_react_mock` | 函数 | 模拟 ReAct 每步携带全部历史的字符数 | 对照组 |
| `main` | 函数 | 组装 demo，打印计划、证据、答案和字符对比 | 入口 |

数据流：`main` 注册工具、写好 3 节点计划 → `run_rewoo`：`planner.plan_for` → `run_workers`（`topological` 排序 → 每个节点 `resolve_references` → `dispatch`）→ `solver.solve` → 打印；再用 `run_react_mock` 跑同样三步，对比字符数。

---

## 3. 逐段精讲

### 3.1 计划的数据结构

```python
@dataclass
class PlanStep:
    id: str
    tool: str
    args: dict[str, Any]


@dataclass
class Plan:
    steps: list[PlanStep]
```

- 一个节点 = "用哪个工具、传什么参数、我叫什么名字"。依赖关系**没有单独的字段**，而是藏在参数字符串里的 `#Ek` 中。这与 ReWOO 论文的计划格式一致（`#E1 = Search[...]`），好处是 LLM 生成起来很自然，坏处是依赖关系要靠正则去"猜"。
- 配套 skill 文件建议节点再带一个可选的 `parallel_group` 标签，方便执行器做并行。
- ⚠️ id 必须写成 `E<数字>` 的形式：`topological` 用 `f"E{r}"` 拼出依赖的 id，若节点 id 叫 `S1`，引用 `#E1` 永远解析不到（实测抛出 `RuntimeError`）。

### 3.2 `ToolRegistry`：与第 01 节几乎相同

```python
    def dispatch(self, name: str, args: dict[str, Any]) -> str:
        fn = self._tools.get(name)
        if fn is None:
            return f"error: unknown tool {name!r}"
        try:
            return fn(**args)
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"
```

- 与第 01 节相比，去掉了单独的 `except TypeError` 分支，所有异常统一格式化。
- 未知工具同样**不抛异常**，而是返回错误字符串——在 ReWOO 中这有一个副作用：错误字符串会被当作证据，通过引用流进下游节点（见 3.4 与测验 Q10）。

### 3.3 引用替换：`resolve_references`

```python
REFERENCE_RE = re.compile(r"#E(\d+)")


def resolve_references(value: Any, evidence: dict[str, str]) -> Any:
    if not isinstance(value, str):
        return value
    return REFERENCE_RE.sub(lambda m: evidence.get(f"E{m.group(1)}", m.group(0)),
                            value)
```

- `re.compile` 预编译正则；`(\d+)` 是捕获组，`m.group(1)` 取到数字，`m.group(0)` 是整段匹配 `#E1`。
- `re.sub` 的替换参数可以是**函数**：每找到一处匹配就调用一次 lambda，返回值作为替换文本。
- `evidence.get(..., m.group(0))`：找不到证据时保留原文 `#E1`，不会抛 `KeyError`。正常流程下不会走到这里，因为 `topological` 已经保证依赖先执行。
- `#E(\d+)` 是贪婪匹配，`#E12` 会被解析为 12，而不是 1 后面跟着 "2"。
- ⚠️ 只处理**顶层字符串**参数：参数是 `{"items": ["#E1"]}` 时，`topological` 通过 `str(step.args)` 能"看到"这个依赖，但 `resolve_references` 收到的是列表，原样返回。实测工具收到的是字面量 `['#E1']`。生产实现应递归遍历 dict/list。

### 3.4 `topological` 与 `run_workers`

```python
def topological(plan: Plan) -> list[PlanStep]:
    resolved: list[PlanStep] = []
    known: set[str] = set()
    pending = list(plan.steps)
    while pending:
        progress = False
        rest: list[PlanStep] = []
        for step in pending:
            refs = REFERENCE_RE.findall(str(step.args))
            if all(f"E{r}" in known for r in refs):
                resolved.append(step)
                known.add(step.id)
                progress = True
            else:
                rest.append(step)
        if not progress:
            raise RuntimeError("cyclic plan or unresolved reference")
        pending = rest
    return resolved
```

- 思路：反复扫描待处理节点，凡是"所有依赖都已就绪"的就放行；一整轮没有任何进展，说明存在环或引用了不存在的节点。这是 Kahn 算法的朴素版本，最坏 O(n²)，对几十个节点的计划足够。
- `REFERENCE_RE.findall(str(step.args))`：把整个参数字典转成字符串再找引用，简单粗暴但能覆盖嵌套结构。
- `all(...)` 对空列表返回 `True`，所以没有引用的节点第一轮就会放行。
- ⚠️ **一轮不等于一层**：`known.add(step.id)` 在 `for` 循环内即时生效。计划 `E1`、`E2(#E1)`、`E3` 的第一轮就会把三个节点全部放行（实测返回 `['E1', 'E2', 'E3']`）。串行执行时没问题，但如果想"按轮并行"，E2 会在 E1 完成前启动。讲义练习 1 要求的并行，需要先把节点**按层分组**（测验 Q9 给出了 `levels` 实现）。
- ⚠️ 只检查引用，不检查工具是否存在、参数是否合法；也没有指出"是哪条边"导致失败。

```python
def run_workers(plan: Plan, tools: ToolRegistry) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for step in topological(plan):
        bound_args = {k: resolve_references(v, evidence) for k, v in step.args.items()}
        evidence[step.id] = tools.dispatch(step.tool, bound_args)
    return evidence
```

- 字典推导式生成"绑定后的参数"，原始计划中的 `step.args` 不被修改——计划保持可审计、可重放。
- `evidence` 的插入顺序就是执行顺序（Python 3.7+ 字典保持插入顺序）。
- ⚠️ 串行执行；失败节点的错误字符串照样写进 `evidence`，下游节点会拿它当输入（实测 `E1 -> error: unknown tool 'serch'`，`E2` 收到的查询变成 `population of error: unknown tool 'serch'`）。

### 3.5 脚本化的 Planner 与 Solver

```python
class ScriptedPlanner:
    def plan_for(self, question: str) -> Plan:
        return self.plan


class ScriptedSolver:
    def solve(self, question: str, plan: Plan, evidence: dict[str, str]) -> str:
        return self.template.format(**evidence)
```

- 两者都只保留了**接口形状**：`plan_for(question)` 与 `solve(question, plan, evidence)`。换成真实 LLM 时，Planner 的 prompt 包含问题 + 工具目录 + 计划格式示例；Solver 的 prompt 包含问题 + 计划 + 证据。
- `self.template.format(**evidence)`：把 `{"E1": "Paris", ...}` 解包成关键字参数填入模板 `"... {E1} ... {E3}."`。多余的键（E2）被忽略；模板里写了不存在的键会抛 `KeyError`（实测 `{E4}` → `KeyError: 'E4'`）。
- ⚠️ 讲义说 Solver 能"看到错误、优雅降级"，但这个脚本 Solver 会把错误字符串原样拼进答案（实测：`The capital of France is error: unknown tool 'serch'; rounded population is unknown.`）。
- ⚠️ 讲义"动手实现"一节列出的组件名是 `Planner`、`Worker`、`Solver`，代码中实际是 `ScriptedPlanner`、`run_workers`（函数，没有 `Worker` 类）、`ScriptedSolver`。

### 3.6 两个示例工具

```python
def fake_search(query: str) -> str:
    if "capital of france" in query.lower():
        return "Paris"
    if "population of paris" in query.lower():
        return "11.2 million metro"
    ...
    return f"no result for {query!r}"


def rounded_million(text: str) -> str:
    m = re.search(r"([0-9]+\.?[0-9]*)", text)
    if not m:
        return "unknown"
    return f"{round(float(m.group(1)))} million"
```

- `fake_search` 用小写子串匹配模拟搜索，查不到时返回 `no result for ...`（不是 `error:` 前缀，下游无法区分"没结果"和"有结果"）。
- `rounded_million` 取文本中**第一个**数字，四舍五入后加上 "million"。实测的几个问题（详见测验 Q11）：
  - `"1,634,567 people"` → `1 million`：正则遇到逗号就停，且不区分"原始人数"与"百万"单位；
  - `"2.5 million"` → `2 million`：Python 的 `round` 是银行家舍入（`round(2.5) == 2`，`round(3.5) == 4`）；
  - `"error: 404 not found"` → `404 million`：把上游错误当成数据。
- ⚠️ 讲义说 demo 是"两步计划：(1) 查首都，(2) 查人口，然后求解"，但代码实际是**三步**（多了 `E3: round_million`）；讲义问题是 "rounded to millions?"，代码里是 "rounded?"。

### 3.7 `run_rewoo` 与 `run_react_mock`：字符数对比

```python
def run_rewoo(question, planner, tools, solver) -> ReWOORun:
    plan = planner.plan_for(question)
    planner_chars = len(question) + sum(len(s.tool) + len(str(s.args))
                                        for s in plan.steps)
    evidence = run_workers(plan, tools)
    worker_chars = sum(len(str(s.args)) + len(v) for s, v in zip(plan.steps,
                                                                 evidence.values()))
    answer = solver.solve(question, plan, evidence)
    solver_chars = len(question) + worker_chars + len(answer)
    ...
```

- `planner_chars`：问题 + 计划文本（近似 Planner 的输入输出）。demo 中 `57 + (6+30) + (6+30) + (13+15) = 157`。
- `worker_chars`：每个节点的参数 + 证据。`30+30+15 + 5+18+10 = 108`。
- `solver_chars`：问题 + 全部证据 + 答案 = `57 + 108 + 65 = 230`。
- `zip(plan.steps, evidence.values())` 把计划顺序与执行顺序配对；两者顺序可能不同，但因为只是求长度总和，结果不受影响（实测把计划倒序书写，`worker_chars` 仍为 108）。
- ⚠️ 统计口径的问题：`worker_chars` 在 `solver_chars` 中被重复计入；ReWOO 的 worker 多为纯工具执行，本不消耗 LLM token；两边都没计 system prompt 和 few-shot 示例（这部分在 ReAct 中每步重复）。

```python
def run_react_mock(question, tools, trajectory) -> int:
    prompt_chars = len(question)
    total = 0
    history_chars = 0
    for name, args in trajectory:
        total += prompt_chars + history_chars + len(name) + len(str(args))
        obs = tools.dispatch(name, args)
        history_chars += len(name) + len(str(args)) + len(obs) + 40
    total += prompt_chars + history_chars
    return total
```

- 第 i 步计入"问题 + 之前全部历史 + 本步动作"，执行后把"动作 + 观察 + 40（近似 thought 与格式开销）"加入历史；最后再加一次"写最终答案"的调用。
- 这正是讲义"Token usage grows quadratically with depth"的模拟：`history_chars` 线性增长，`total` 是它的累加，二次增长。

### 3.8 `main`

- 注册 `search` 与 `round_million` 两个工具，写死 3 节点计划和答案模板。
- 打印 PLAN、EVIDENCE、FINAL 三段，再打印 `react total / rewoo total / ratio`。
- ReAct 对照组的轨迹是手写的，第二步直接写成 `"population of Paris"`——相当于假设 ReAct 的模型读到了第一步结果；ReWOO 一侧则由引用替换得到同样的查询。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 依赖藏在 `#Ek` 字符串中 | 与论文格式一致，LLM 易生成 | 依赖靠正则推断；生产中常让 Planner 输出 JSON，显式列出 `depends_on`，并做 schema 校验 |
| 朴素的"反复扫描"拓扑排序 | 代码短、易读 | 一轮≠一层，不能直接用于并行；报错不指明失败的边 |
| 串行执行 worker | 简单、确定 | 浪费了 ReWOO 可并行的优势；生产用线程池/asyncio 按层并发 |
| 错误字符串直接进 evidence | 循环永不崩溃 | 错误被下游当数据传播；应标记失败并跳过下游，或触发 replanner |
| 脚本化 Planner / Solver | 离线可运行 | 演示不了 Planner 的质量问题和 Solver 的降级；生产中二者都是 LLM 调用 |
| 字符数代替 token | 无需 tokenizer | 只能看趋势；真实评估应用 provider 返回的 usage 统计 |
| 只替换顶层字符串参数 | 实现简单 | 嵌套参数中的引用不会被替换；需递归处理 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可在注解中使用 `dict[str, Any]` 等新写法 |
| `@dataclass` + `field(default_factory=dict)` | `class ReWOORun` | 可变默认值（字典）必须用工厂函数 |
| 正则预编译 | `REFERENCE_RE = re.compile(r"#E(\d+)")` | 原始字符串 `r"..."` 避免反斜杠转义；编译一次多次使用 |
| `re.sub` 传函数 | `REFERENCE_RE.sub(lambda m: ..., value)` | 每个匹配调用一次函数，用返回值替换 |
| 捕获组 | `m.group(0)`、`m.group(1)` | 0 是整段匹配，1 是第一个括号里的内容 |
| `re.findall` | `REFERENCE_RE.findall(str(step.args))` | 有捕获组时返回捕获内容的列表，如 `['1']` |
| `re.search` | `re.search(r"([0-9]+\.?[0-9]*)", text)` | 找到第一个匹配，没有则返回 `None` |
| `isinstance` | `if not isinstance(value, str)` | 类型判断，非字符串原样返回 |
| `all()` 与空列表 | `all(f"E{r}" in known for r in refs)` | 生成器表达式；空列表时为 `True` |
| `set` 成员判断 | `known.add(step.id)`、`... in known` | 集合查找 O(1) |
| `while` + 标志位 | `progress = False ... if not progress: raise` | 检测"一整轮没有进展" |
| `raise RuntimeError(...)` | `topological` 中 | 主动抛出异常终止执行 |
| 字典推导式 | `{k: resolve_references(v, evidence) for k, v in step.args.items()}` | 逐个键值对变换生成新字典 |
| `str.format(**dict)` | `self.template.format(**evidence)` | 字典解包为关键字参数填入 `{E1}` 等占位符 |
| `sum` + 生成器 | `sum(len(s.tool) + len(str(s.args)) for s in plan.steps)` | 不建中间列表直接求和 |
| `zip` | `zip(plan.steps, evidence.values())` | 两个序列按位置配对 |
| 元组列表参数 | `trajectory: list[tuple[str, dict[str, Any]]]` | 每个元素是 `(工具名, 参数)`，循环中直接解包 `for name, args in trajectory` |
| `max(x, 1)` 防除零 | `react_chars / max(rewoo_chars, 1)` | 分母至少为 1 |
| f-string 格式符 | `{react_chars / max(rewoo_chars, 1):.2f}` | 保留两位小数 |
| `round()` 银行家舍入 | `round(float(m.group(1)))` | `round(2.5) == 2`，需要四舍五入时用 `decimal.ROUND_HALF_UP` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`cd code && python3 main.py`）：

```text
======================================================================
REWOO — Planner, Workers, Solver (Phase 14, Lesson 02)
======================================================================

PLAN
  E1: search({'query': 'capital of France'})
  E2: search({'query': 'population of #E1'})
  E3: round_million({'text': '#E2'})

EVIDENCE
  E1 -> Paris
  E2 -> 11.2 million metro
  E3 -> 11 million

FINAL: The capital of France is Paris; rounded population is 11 million.

TOKEN INTUITION (chars, approximate)
  react total  : 873
  rewoo total  : 495
  ratio        : 1.76x

paper claim: ~5x fewer tokens on HotpotQA. toy approximates the shape.
```

逐项解读：

- **PLAN 打印的是原始计划**：`#E1`、`#E2` 还是占位符——计划在执行前就完整可见，这是 ReWOO "可审计"的好处，也是执行前做校验的时机。
- **EVIDENCE**：E2 的查询在分派时被替换为 `population of Paris`，所以得到 `11.2 million metro`；E3 拿到 `11.2 million metro`，提取出 11.2 并四舍五入为 `11 million`。
- **FINAL**：模板只用了 `{E1}` 和 `{E3}`，E2 被忽略。
- **react total 873**：三步分别计入 93、176、277，最后的作答调用计入 327（逐步推算见测验 Q12）。
- **rewoo total 495** = planner 157 + worker 108 + solver 230。
- **ratio 1.76x**：只有 3 步，二次增长还没显现。用同一代码把步数扩大（每步都是 `search("capital of France")`），实测比值为：n=1 → 1.03，n=3 → 1.83，n=10 → 4.41，n=30 → 11.66。"5 倍"取决于任务深度，而不是常数。

额外实验（临时脚本调用本文件中的函数）：

| 实验 | 结果 |
|------|------|
| 计划按 E3、E2、E1 倒序书写 | `topological` 仍排出 `['E1','E2','E3']`，答案不变 |
| `E1` 引用自身 `#E1` / 引用不存在的 `#E9` | 均抛 `RuntimeError: cyclic plan or unresolved reference` |
| 参数为 `{"items": ["#E1"]}` | 工具收到字面量 `['#E1']`，引用未被替换 |
| E1 工具名写成 `serch` | 错误字符串传到 E2、E3，最终答案中出现 `error: unknown tool 'serch'` |
| 6 节点 DAG 串行 vs 按层并行（search 各 0.2 秒） | 0.80 秒 vs 0.41 秒，结果一致 |

---

## 7. 动手改一改

1. **（热身）计划校验器**：写 `validate(plan, tools)`，检查节点 id 唯一、工具存在、每个 `#Ek` 都有对应节点、可拓扑排序，并返回具体错误列表（如 `E1: unknown tool 'serch'`）。在 `run_rewoo` 中先校验再执行。
2. **（讲义练习 1）按层并行**：实现 `levels(plan)` 并用 `ThreadPoolExecutor` 并发执行同一层节点；给工具加 `time.sleep` 测量 6 节点、4 层 DAG 的加速比（参考测验 Q9）。
3. **（讲义练习 2）失败隔离 + replanner**：失败节点的下游标记为 `skipped`；任一节点失败时调用一个 `ScriptedReplanner`，用备用工具重写失败节点及其下游，再继续执行。体会"加一个看得到 observation 的 replanner，ReWOO 就变成了 Plan-and-Execute"。
4. **修好 `rounded_million`**：支持千分位逗号、区分"人数"与"百万"、用 `ROUND_HALF_UP`，遇到 `error` 前缀直接返回错误（参考测验 Q11）。
5. **真实 token 统计**：把字符数换成近似 token 数（例如按 4 字符 ≈ 1 token，或接入一个 tokenizer），同时给两边加上相同长度的 system prompt（如 500 字符），重新比较 n = 3、10、30 时的比值，观察"每步重复 system prompt"对 ReAct 的影响。
6. **（进阶，讲义练习 5）序列化计划**：把 DAG 改成 Plan-and-Act 风格的线性步骤列表，每一步可以引用"上一步结果"。比较两种表示在并行性、可读性、LLM 生成难度上的取舍。

---

## 8. 常见坑

- **把 `topological` 的一轮当成一层去并行**：`known` 在轮内即时更新，同一轮里可能包含有依赖关系的节点。
- **节点 id 不按 `E<数字>` 命名**：引用解析依赖 `f"E{r}"` 的拼接，换个命名就全部报"unresolved reference"。
- **嵌套参数里的引用不被替换**：`resolve_references` 只处理顶层字符串。
- **错误字符串当证据传播**：下游工具会把 `error: ...` 当正常文本处理，甚至从中解析出数字（`404 million`）。
- **`round` 的银行家舍入**：`round(2.5) == 2`，金额和统计数字要用 `decimal`。
- **模板占位符拼错**：`ScriptedSolver` 的模板引用不存在的键会抛 `KeyError`，而缺证据时又不会提示。
- **把 toy 比值当结论**：字符数比值随步数和常数变化很大，不能用来验证或否定论文的 5 倍。
- **对短任务硬上 ReWOO**：单步任务两者几乎没有差别（n=1 时比值 1.03），反而多了一次 Planner 调用和一套校验逻辑。
