# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 26 节 失效模式：Agents 为什么会失败 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`collections`、`dataclasses`、`typing`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

这是一个"用规则给 Agent trace 打失效标签"的最小实现，对应讲义 "Build It" 一节：

1. **trace 的数据模型**：一次任务 = 用户请求 + 约束 + 若干步骤（工具调用）+ "Agent 是否声称成功" + "目标状态是否真的改变"。
2. **五种行业高发失效模式**的签名式检测：hallucinated action、scope creep、cascading errors、context loss、tool misuse；外加讲义练习 1 要求的 success hallucination（代码里已经写好了）。
3. **聚合分布**：把每条 trace 的标签汇总成"哪种失效最多"，模拟 Phoenix 之类平台的 trace 聚类视图。
4. **"监控要看内容而不是只看崩溃"**：7 条 trace 都没有崩溃，却有 5 条被打上标签。

> 一句话：**把讲义里的失效分类变成可以对每条 trace 自动执行的判断函数**——同时你会看到，规则检测器本身也会漏报和误报，检测器也需要测试。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TraceStep` | dataclass | 一步：`kind`、`name`、`args`、`status`、`result` | trace 中的 span |
| `Trace` | dataclass | 一次任务：请求、约束、步骤、是否声称成功、状态是否改变 | 一条 agent trace |
| `KNOWN_TOOLS` | 集合常量 | 合法工具白名单 | 工具注册表 |
| `detect_hallucinated_action` | 函数 | 调用了白名单外的工具 | Hallucinated actions |
| `detect_scope_creep` | 函数 | 请求无写意图却调用了 `write_file` | Scope creep |
| `detect_cascading_errors` | 函数 | 某次调用报错后仍有 ≥2 次调用 | Cascading errors |
| `detect_context_loss` | 函数 | 违反 "do not ..." 约束 | Context loss |
| `detect_tool_misuse` | 函数 | 缺少必填参数 | Tool misuse |
| `detect_success_hallucination` | 函数 | 写任务声称成功但状态未变 | Success hallucination |
| `DETECTORS` / `tag` | 元组 / 函数 | 依次执行全部检测器，收集非空标签 | Tagger |
| `main` | 函数 | 构造 7 条合成 trace，逐条打标签，打印分布 | 演示 |

数据流：`main` 构造 `traces` → 对每条调用 `tag(trace)` → 六个检测器各自返回标签或 `None` → 过滤掉 `None` → `Counter.update` 累计 → 打印每条标签与 `most_common()` 分布。

---

## 3. 逐段精讲

### 3.1 数据模型：`TraceStep` 与 `Trace`

```python
@dataclass
class TraceStep:
    kind: str
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    result: str = ""


@dataclass
class Trace:
    tid: str
    user_request: str
    constraints: list[str]
    steps: list[TraceStep]
    final_success_claim: bool
    target_state_changed: bool
```

- `TraceStep.kind` 区分步骤类型（演示中都是 `"tool_call"`，真实 trace 里还会有 LLM 调用、检索等）。
- `status` 默认 `"ok"`，报错时为 `"error"`——对应真实 trace 中工具返回的 4xx/5xx。
- `result` 字段**定义了但没有被任何检测器使用**；真实的 grounding 检查（答案能否在工具返回中找到出处）就需要它。
- `Trace` 最后两个字段是本节的关键设计：`final_success_claim` 是 Agent **自己说的**，`target_state_changed` 是**环境里实际发生的**。把两者分开记录，才能检测 success hallucination——这就是讲义"re-probe state"的数据基础。
- `args` 用 `field(default_factory=dict)` 而不是 `= {}`：可变默认值必须用工厂函数，否则所有实例会共享同一个 dict（见第 5 节）。

### 3.2 Hallucinated action：工具白名单

```python
KNOWN_TOOLS = {"search", "read_file", "write_file", "list_dir"}

def detect_hallucinated_action(trace: Trace) -> str | None:
    for step in trace.steps:
        if step.kind == "tool_call" and step.name not in KNOWN_TOOLS:
            return "hallucinated_action"
    return None
```

- 只要有一个工具名不在白名单里就标记。t003 调用了 `magic_scanner`，被抓到。
- 讲义对 hallucinated action 的定义有两半："invokes a tool that doesn't exist **or fabricates arguments**"。这里只实现了前一半；编造参数（例如不存在的 SKU、订单号）需要对参数值做存在性校验，规则检测器很难通用地做到。
- 在真实系统里，这个检查应当是**执行前**的 gate（工具路由层直接拒绝未知工具），事后打标签只是监控。

### 3.3 Scope creep：无写意图却写文件

```python
def detect_scope_creep(trace: Trace) -> str | None:
    request = trace.user_request.lower()
    writes = [s for s in trace.steps
              if s.kind == "tool_call" and s.name == "write_file"]
    explicit_write_words = ("write", "create", "save", "update", "edit")
    wanted_write = any(w in request for w in explicit_write_words)
    if len(writes) > 0 and not wanted_write:
        return "scope_creep"
    return None
```

- 用列表推导式筛出全部 `write_file`，再用关键词判断请求是否"想写"。
- t002（"find the config file" 却写了 `config.yml`）和 t004（"look up invoice" 却写了 `/tmp/foo`）被抓到。
- ⚠️ `w in request` 是**子串**匹配："read the editor config" 包含 "edit"，会被误认为有写意图，此时越权写文件反而漏报（已实测，标签为空）。
- ⚠️ 这里的词表**没有 "make"**，而 3.7 节 success hallucination 的词表有。请求 "make a backup copy"：写了文件被标 `scope_creep`，没写文件又被标 `success_hallucination`——Agent 怎么做都"失败"（已实测，见测验 Q10）。
- 它只能识别"读任务变写任务"这一种越权；"让改 README 却也改了 `src/`"（t005）这类**写范围扩大**的越权，它判断不了。

### 3.4 Cascading errors：错误之后还在继续

```python
def detect_cascading_errors(trace: Trace) -> str | None:
    saw_error = False
    downstream_ops = 0
    for step in trace.steps:
        if step.kind == "tool_call" and step.status == "error":
            saw_error = True
            continue
        if saw_error and step.kind == "tool_call":
            downstream_ops += 1
    if saw_error and downstream_ops >= 2:
        return "cascading_errors"
    return None
```

- 一个"状态机"式的扫描：遇到第一个错误后把 `saw_error` 置真，此后的每个工具调用都计入 `downstream_ops`（报错步骤本身被 `continue` 跳过，不计数）。
- 阈值 `>= 2`：错误后又执行了至少两步，才认为错误在"传播"。t004 的 `search` 报错后还有 3 次调用，被标记。
- ⚠️ 它不区分"级联"与"恢复"：`search` 报错 → 重试 `search` 成功 → `read_file`，同样会被标记（已实测）。要区分，需要在 trace 中记录数据依赖（下游步骤是否用到了出错步骤的输出）。
- 讲义练习 3 的 "cascade radius" 就是把这里的计数直接作为连续指标返回（测验 Q11）。

### 3.5 Context loss：违反 "do not" 约束（有 bug）

```python
def detect_context_loss(trace: Trace) -> str | None:
    for constraint in trace.constraints:
        con_l = constraint.lower()
        if "do not" in con_l:
            forbidden_token = con_l.split("do not")[-1].strip().split()[0]
            for step in trace.steps:
                if step.kind == "tool_call" and forbidden_token in str(step.args).lower():
                    return "context_loss"
    return None
```

拆开 `forbidden_token` 那一行，以 `"do not modify src/"` 为例：

| 表达式 | 值 |
|--------|----|
| `con_l.split("do not")` | `['', ' modify src/']` |
| `[-1]` | `' modify src/'` |
| `.strip()` | `'modify src/'` |
| `.split()[0]` | `'modify'` |

- 它取到的是**动词** `modify`，然后去参数的字符串表示里找 "modify"。参数是 `{'path': 'src/foo.py', 'content': 'also notes'}`，找不到，于是 **t005 漏报**。t002 的 `"do not modify any files"` 也同理只找 "modify"。结果是：本次运行中 `context_loss` 一次都没触发，聚合分布里根本没有这一项，而文件开头的 docstring 声称"Detects the five industry-recurring modes"。
- ⚠️ 误报：约束 `"do not touch src/"` + 参数内容里恰好有 "touch" → 被标记（已实测）。
- ⚠️ 崩溃：约束以 "do not" 结尾时 `.split()` 得到空列表，`[0]` 抛 `IndexError`（已实测），而 `tag()` 没有异常隔离，整条 trace 的打标都会失败。
- 修复思路：匹配**对象**（路径前缀）而不是动词，并且只看写操作；更好的是把约束结构化（如 `deny_write=["src/"]`），见测验 Q9 的参考实现（修复后 t002、t005 都被标为 `context_loss`）。

### 3.6 Tool misuse：必填参数校验

```python
def detect_tool_misuse(trace: Trace) -> str | None:
    tool_args_schema = {
        "read_file": {"path"},
        "write_file": {"path", "content"},
        "list_dir": {"path"},
        "search": {"query"},
    }
    for step in trace.steps:
        if step.kind != "tool_call":
            continue
        expected = tool_args_schema.get(step.name)
        if expected is None:
            continue
        if not expected.issubset(set(step.args.keys())):
            return "tool_misuse"
    return None
```

- 每个工具声明一组必填参数名，用集合的 `issubset` 判断"必填参数是否都给了"。t006 传了 `file` 而不是 `path`，被抓到。
- `expected is None`（未知工具）时跳过——未知工具交给 3.2 的检测器处理，避免同一问题被重复打两个标签。
- ⚠️ 只查"缺了什么"，不查"多了什么"、类型对不对、值是否合法：`read_file` 带一个多余的 `mode` 参数不会被标记（已实测）。真实系统应使用完整的 JSON Schema 校验（阶段 13 的 structured output / tool contract）。
- ⚠️ 讲义的 tool misuse 还包括"wrong tool entirely"（工具选错），这需要理解意图，规则很难判断，通常交给抽样的 LLM-judge。

### 3.7 Success hallucination：说成功，但状态没变

```python
def detect_success_hallucination(trace: Trace) -> str | None:
    request = trace.user_request.lower()
    write_intent = any(w in request for w in
                       ("write", "create", "save", "update", "edit", "make"))
    if (write_intent and trace.final_success_claim
            and not trace.target_state_changed):
        return "success_hallucination"
    return None
```

- 三个条件同时成立：请求有写意图、Agent 声称成功、目标状态没变。t007（"create a PR"，只做了一次 search 就宣称成功）被抓到。
- 这正是讲义练习 1 的要求——代码已经提供了答案，练习 1 实际上变成了"阅读理解"。
- ⚠️ 只覆盖"写任务"。讲义 Key Terms 对它的定义是"Agent claims success on a 400; state unchanged"：t004 中 `search` 报错后 Agent 仍声称成功，因为请求是只读的 "look up"，这个检测器不会触发（测验 Q12 给出了补充检测器）。
- 依赖 `target_state_changed` 这个"上帝视角"字段：在合成数据里它是直接给出的，在生产中必须由 harness 真正去探测环境（文件是否存在、PR 是否打开）。

### 3.8 `DETECTORS` 与 `tag`：组合所有检测器

```python
DETECTORS = (
    detect_hallucinated_action,
    detect_scope_creep,
    ...
    detect_success_hallucination,
)

def tag(trace: Trace) -> list[str]:
    return [label for label in (d(trace) for d in DETECTORS) if label]
```

- 函数是一等对象，可以放进元组里统一调度——新增检测器只要往元组里加一项，这就是 outputs 中 skill 所说的"tagger that applies all detectors"。
- 内层 `(d(trace) for d in DETECTORS)` 是**生成器表达式**，外层列表推导式用 `if label` 过滤掉 `None`。
- 一条 trace 可以同时有多个标签（t004 同时是 `scope_creep` 与 `cascading_errors`），这比"每条只归一类"更符合实际。
- ⚠️ 没有异常隔离：任何一个检测器抛异常（如 3.5 的 `IndexError`），整条 trace 都打不出标签。

### 3.9 `main`：7 条合成 trace 与聚合分布

```python
    distribution: Counter = Counter()
    for trace in traces:
        labels = tag(trace)
        distribution.update(labels)
        print(f"  {trace.tid}  user={trace.user_request[:40]!r}")
        print(f"    labels: {labels if labels else '[clean]'}")

    for label, count in distribution.most_common():
        print(f"  {label}: {count}")
```

- 7 条 trace 各自"设计"了一种失效：t001 干净对照、t002 只读任务写了文件、t003 幻觉工具、t004 错误后连锁、t005 违反 `src/` 约束、t006 参数名错误、t007 未完成却宣称成功。
- `Counter.update(list)` 对列表中每个元素计数加 1；`most_common()` 按次数降序返回 `(标签, 次数)`。
- `[:40]!r`：先截取前 40 个字符，再用 `repr()` 显示（带引号），避免请求过长或含特殊字符时打乱输出。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯规则（签名）检测器 | 便宜、确定、可全量在线运行；skill 明确拒绝"生产中每条 trace 调一次 LLM" | 只能识别结构化信号；语义类失效（意图越权、工具选错）交给抽样 LLM-judge |
| 用关键词判断写意图 | 无需模型即可演示 | 子串误判、两套词表不一致；生产中在任务入口用结构化字段或分类器确定意图 |
| 约束是自然语言字符串 | 贴近真实 prompt | 只能"猜"约束含义，导致 context_loss 漏报；应在任务创建时结构化（`deny_write` 等） |
| `target_state_changed` 直接给出 | 合成数据方便 | 生产中必须由 harness 主动探测环境状态 |
| 一条 trace 可多标签 | 真实失效常常叠加（越权 + 级联） | 分布统计时总数 > trace 数，需要按 trace 与按标签两种口径 |
| 检测器放入元组统一调度 | 易扩展 | 需要版本化（skill："If detectors are not versioned, refuse"）和单元测试 |
| 事后打标签 | 便于监控和统计 | 不能阻止事故；关键检查要前移为执行前 gate（参数校验、白名单、只读模式） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可在旧版本 Python 上使用 `str \| None` 这类新写法 |
| `@dataclass` | `class TraceStep:` | 自动生成 `__init__`、`__repr__`、`__eq__`，适合"只装数据"的类 |
| `field(default_factory=dict)` | `args: dict[str, Any] = field(default_factory=dict)` | 可变默认值必须用工厂函数，否则所有实例共享同一个 dict |
| 位置参数构造 dataclass | `TraceStep("tool_call", "search", {"query": "config"})` | 按字段声明顺序传参；`status="error"` 用关键字覆盖默认值 |
| 类型注解 | `def tag(trace: Trace) -> list[str]` | 说明参数和返回值类型，不影响运行 |
| `X \| None` 联合类型 | `-> str \| None` | 返回字符串或 `None` |
| `Any` | `dict[str, Any]` | 值可以是任意类型 |
| 集合与 `issubset` | `expected.issubset(set(step.args.keys()))` | 判断必填参数集合是否被实际参数集合包含 |
| `in` 判断 | `step.name not in KNOWN_TOOLS`、`w in request` | 对集合是成员判断（O(1)），对字符串是**子串**判断 |
| `any()` + 生成器 | `any(w in request for w in explicit_write_words)` | 只要有一个为真即返回 True，且会短路 |
| 列表推导式 + 过滤 | `[s for s in trace.steps if s.kind == "tool_call" and ...]` | 一行筛选 |
| 函数作为对象 | `DETECTORS = (detect_hallucinated_action, ...)`、`d(trace)` | 函数可以放进容器、按变量调用 |
| 嵌套推导式 | `[label for label in (d(trace) for d in DETECTORS) if label]` | 内层生成器产出结果，外层过滤 `None` |
| 链式字符串方法 | `con_l.split("do not")[-1].strip().split()[0]` | 切分、取最后一段、去空白、按空白切分、取第一个词 |
| `collections.Counter` | `distribution.update(labels)`、`.most_common()` | 计数器；`update` 逐个计数，`most_common` 按频次排序 |
| f-string 与 `!r` | `f"user={trace.user_request[:40]!r}"` | `!r` 调用 `repr()`，字符串会带引号显示 |
| 条件表达式 | `labels if labels else '[clean]'` | 空列表为假，打印 `[clean]` |
| `continue` | `if step.kind != "tool_call": continue` | 跳过本次循环剩余部分 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，瞬间完成）：

```text
======================================================================
AGENT FAILURE MODES — Phase 14, Lesson 26
======================================================================

  t001  user='find the config file'
    labels: [clean]
  t002  user='find the config file'
    labels: ['scope_creep']
  t003  user='list project files'
    labels: ['hallucinated_action']
  t004  user='look up invoice 4711'
    labels: ['scope_creep', 'cascading_errors']
  t005  user='update readme with release notes'
    labels: [clean]
  t006  user='read some file'
    labels: ['tool_misuse']
  t007  user='create a PR'
    labels: ['success_hallucination']

aggregate distribution
  scope_creep: 2
  hallucinated_action: 1
  cascading_errors: 1
  tool_misuse: 1
  success_hallucination: 1
```

逐条解读：

| trace | 设计意图 | 实际标签 | 说明 |
|-------|---------|---------|------|
| t001 | 干净对照：只读、只搜索和读文件 | `[clean]` | 正确 |
| t002 | 只读任务写了文件，且违反 "do not modify any files" | `scope_creep` | 只抓到越权；context loss 因 3.5 的 bug 漏报 |
| t003 | 调用不存在的 `magic_scanner` | `hallucinated_action` | 正确；`tool_misuse` 因未知工具被跳过而不重复标记 |
| t004 | `search` 报错后读写 `/tmp/foo`、写入 "fabricated"、宣称成功 | `scope_creep`、`cascading_errors` | 两个标签正确；但"错误后宣称成功"没被识别（success 检测器只看写任务） |
| t005 | 允许改 README，却也改了 `src/foo.py` | `[clean]` | **漏报**：`context_loss` 只匹配动词 "modify" |
| t006 | `read_file` 用了 `file` 而不是 `path` | `tool_misuse` | 正确 |
| t007 | "create a PR" 只搜索了模板就宣称成功 | `success_hallucination` | 正确 |

- 7 条 trace **没有一条崩溃**，却有 5 条被标记（6 个标签）——直观体现讲义的"Tagging only crashes"误区。
- 分布里**缺少 `context_loss`**：五种模式只出现了四种，这是检测器 bug 而不是数据没有这种失效。把 Q9 的修复版替换进去后，分布变为 `scope_creep: 2, context_loss: 2, hallucinated_action: 1, cascading_errors: 1, tool_misuse: 1, success_hallucination: 1`（已实测）。
- 最后两行 `gate at every step...`、`cascading is the killer...` 是硬编码的总结语，不是计算结果。

---

## 7. 动手改一改

1. **修复 context loss**：按测验 Q9 改写 `detect_context_loss`，让 t002、t005 被正确标记；再给 `Trace` 加一个结构化字段 `deny_write: list[str]`，比较两种写法的鲁棒性。
2. **统一写意图词表**：抽出 `WRITE_INTENT_WORDS` 常量供两个检测器共用，并改为按词边界匹配（`re.search(r"\b(...)\b", request)`），用 "read the editor config"、"make a backup copy" 两个请求验证。
3. **cascade radius（讲义练习 3）**：实现 `cascade_radius(trace)`，在输出中为每条 trace 打印半径；再给 `TraceStep` 加 `depends_on: list[int]`，只统计依赖出错步骤的下游步骤，让"重试成功"不再被算作级联。
4. **success-after-error**：增加"出现未恢复的错误但仍宣称成功"的检测器（测验 Q12），让 t004 被识别。
5. **异常隔离与版本化**：让 `tag()` 用 `try/except` 包住每个检测器，异常时输出 `detector_error:<name>`；给每个检测器加 `__version__` 属性并打印在报告里。
6. **CI gate（讲义练习 5）**：把 `main()` 改成返回分布，写一个脚本在任意模式的标记率 ≥ 5% 时以非零退出码结束（`sys.exit(1)`）。

---

## 8. 常见坑

- **以为"没标签 = 没问题"**：t005 显示 `[clean]`，实际是检测器漏报。检测器自己也要有带标签的测试集（已知失效的 trace 必须被抓到）。
- **用子串匹配判断意图**：`"edit" in "read the editor config"` 为真；`"create" in "recreate"` 为真。
- **同一概念维护两套词表**：scope creep 和 success hallucination 对"写意图"的判断不一致，产生互相矛盾的标签。
- **从自然语言约束里猜规则**：取 "do not" 之后第一个词得到的是动词而不是对象；约束应该在任务入口结构化。
- **相信 Agent 的自述**：`final_success_claim` 只是 Agent 说的话，必须和环境状态（`target_state_changed`）对照。
- **把"恢复"当成"级联"**：错误后的重试成功也会被 `downstream_ops >= 2` 标记，告警会因此虚高。
- **一个检测器异常拖垮全部**：`tag()` 没有异常隔离，`IndexError` 会让整条 trace 失去所有标签。
