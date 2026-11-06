# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 49 节 语言模型 Evaluation Harness ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py [--task-dir DIR] [--out PATH] [--batch-size 4] [--include-per-example] [--seed-fixtures]` ｜ **依赖**：仅 Python 标准库（`ast`、`json`、`re`、`operator`、`dataclasses`、`typing` 等）；`zip(..., strict=True)` 需要 Python 3.10+。
>
> 提示：默认 `--out` 是 `outputs/leaderboard.json`，会覆盖仓库里的文件；练习时建议加 `--out /tmp/xxx.json`。

---

## 1. 这份代码在考察什么

这份代码是一个约 500 行的"迷你版 lm-evaluation-harness"，覆盖讲义里评测系统的全部部件：

1. **任务定义**：一行一个样例的 JSONL（`id`、`prompt`、`targets`、`metric`、`extras`），文件名即任务名。
2. **五个从零写的指标**：exact match、substring contains、multiple choice、ROUGE-L、代码执行。
3. **可替换的模型 adapter**：用 `typing.Protocol` 定义接口，默认是确定性的 `ToyAdapter`。
4. **运行器**：分批调 adapter、逐样例打分、计时、汇总成任务分与总分。
5. **排行榜 JSON**：带 schema 字符串，可选附带每条预测。

另外还藏着一个"安全求值"小练习：`safe_arith_eval` 用 `ast` 只允许算术节点，避免 `eval`。

> 一句话：**评测 = 固定任务 × 固定指标 × 可替换 adapter**，任何一项变了分数都会变，所以三者都要版本化。同时要看清这些指标有多容易被"钻空子"——Toy 拿满分并不说明 harness 好用。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Example` / `TaskResult` / `Leaderboard` | dataclass | 样例、任务结果、排行榜的数据结构 | 任务规范 / 报告 |
| `ModelAdapter` | `Protocol` | 只规定 `generate(prompts)` 与 `name` | adapter 接缝 |
| `ToyAdapter` | 类 | 按 prompt 前缀（`compute:` 等）模式匹配出答案 | 模型桩 |
| `_ARITH_OPS` / `safe_arith_eval` / `_safe_eval` | 字典 + 函数 | 用 AST 白名单计算算术表达式 | 安全求值 |
| `normalize` | 函数 | 去首尾空白、小写、压缩空白 | 答案归一化 |
| `metric_exact_match` / `metric_substring_contains` / `metric_multiple_choice` | 函数 | 三个字符串指标 | 指标 |
| `_tokens` / `_lcs_length` / `metric_rouge_l` | 函数 | 分词、LCS 动态规划、ROUGE-L F1 | 指标 |
| `metric_code_exec` | 函数 | 在"去掉 builtins"的命名空间里 `exec`，比对 IO 对 | 执行型指标 |
| `METRIC_FNS` | 字典 | 指标名 → 统一签名 `(p, t, e)` 的函数 | 按名分发 |
| `load_task_jsonl` / `write_task_jsonl` / `load_all_tasks` | 函数 | JSONL 读写，目录批量加载 | 任务 I/O |
| `run_task` / `run_leaderboard` | 函数 | 分批推理 + 打分 + 计时；宏平均 | 运行器 |
| `write_leaderboard` | 函数 | 写 JSON（可含 per-example） | 排行榜 |
| `build_*_task` / `seed_fixture_tasks` | 函数 | 生成 5 个 fixture 任务 | 测试数据 |
| `parse_args` / `main` | 函数 | CLI；任务目录为空时自动生成 fixture | 入口 |

数据流：`main` → （必要时 `seed_fixture_tasks`）→ `load_all_tasks` 得 `{任务名: [Example]}` → `run_leaderboard` 按任务名排序逐个 `run_task` → 每批 `adapter.generate` → `METRIC_FNS[metric](pred, targets, extras)` → `TaskResult` → 宏平均成 `Leaderboard` → `write_leaderboard` 写 JSON → 打印表格。

---

## 3. 逐段精讲

### 3.1 数据结构与 adapter 协议

```python
@dataclass
class Example:
    id: str
    prompt: str
    targets: List[str]
    metric: str
    extras: Dict[str, object] = field(default_factory=dict)


class ModelAdapter(Protocol):
    def generate(self, prompts: Sequence[str]) -> List[str]:
        ...

    @property
    def name(self) -> str:
        ...
```

- `field(default_factory=dict)`：可变默认值必须用工厂函数，否则所有实例会共享同一个字典。
- `Protocol` 是**结构化类型**（"鸭子类型"的静态版）：`ToyAdapter` 并没有继承 `ModelAdapter`，但它有 `generate` 和 `name`，类型检查器就认为它符合协议；运行时不做任何检查。测试里的 `StubAdapter` 也是这样直接传进去的。
- `targets` 是列表：允许多个可接受答案，指标对多个参考取"任一命中"或"最大值"。

### 3.2 `ToyAdapter`：一个按 fixture 写的"模型"

```python
    def _answer(self, prompt: str) -> str:
        text = prompt.strip()
        if text.startswith("compute:"):
            expr = text[len("compute:"):].strip()
            try:
                return str(safe_arith_eval(expr))
            except Exception:
                return ""
        if text.startswith("summarize:"):
            body = text[len("summarize:"):].strip()
            sentences = re.split(r"(?<=[.!?])\s+", body)
            return sentences[0] if sentences else body
        ...
        if text.startswith("choose:"):
            body = text[len("choose:"):].strip()
            return body.split("|", 1)[0].strip()[:1].upper()
        if text.startswith("write:"):
            body = text[len("write:"):].strip()
            return body
        return text
```

- `compute:` 用安全求值得到数值再 `str()`：`100 / 4` 是真除法，得到 `"25.0"`，所以 fixture 的目标也写成了 `"25.0"`。
- `summarize:` 用**后行断言** `(?<=[.!?])\s+` 在句末标点后的空白处切句，取第一句——这就是经典的 "lead-1" 摘要基线，而 fixture 的参考摘要恰好就是第一句。
- `python:` 按关键词 `double` / `increment` / `square` 返回固定函数源码。
- `choose:` 取第一个选项的字母（永远是 `A`），`write:` 原样回声。
- ⚠️ docstring 说 "The point is not to score well"，但它是对着 fixture 写的，五个任务全部满分。讲义也承认 "a deterministic pattern matcher that returns the right answer for every prompt"。满分只证明打分代码能跑通，不证明任务能区分好坏模型（测验 Q4、Q9：常数 `"A"` 得 0.2，回声得 0.54）。

### 3.3 `safe_arith_eval`：AST 白名单

```python
_ARITH_OPS = {
    ast.Add: operator.add,
    ...
    ast.Pow: operator.pow,
}

def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ARITH_OPS:
        return _ARITH_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ARITH_OPS:
        return _ARITH_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"unsafe node: {ast.dump(node)}")
```

- `ast.parse(expr, mode="eval")` 把字符串解析成表达式树，再**递归**求值；只认数字常量、二元运算、一元运算，函数调用、属性访问、名字一律抛 `ValueError`。测试 `test_arith_eval_rejects_calls` 用 `__import__('os').system('echo')` 验证了这一点。
- 字典的键是**类**（`ast.Add`），用 `type(node.op)` 查表，把 AST 节点映射到 `operator` 模块里的函数。
- 括号不需要特殊处理：解析时已经体现在树的结构里，所以 `(8 - 2) / 3` 得 2.0。
- ⚠️ 允许 `Pow` 带来"计算量炸弹"：我们实测 `7**10**6` 0.22 秒、`7**10**7` 5.4 秒，指数再大就会长时间占满 CPU 和内存；生产中应限制指数大小或给求值加超时。另外 `True` 是 `int` 的子类，`"True + True"` 会被接受并返回 2。

### 3.4 三个字符串指标

```python
def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def metric_exact_match(prediction: str, targets: List[str]) -> float:
    norm_pred = normalize(prediction)
    return 1.0 if any(normalize(t) == norm_pred for t in targets) else 0.0

def metric_substring_contains(prediction: str, targets: List[str]) -> float:
    norm_pred = normalize(prediction)
    return 1.0 if any(normalize(t) in norm_pred for t in targets) else 0.0

def metric_multiple_choice(prediction: str, targets: List[str]) -> float:
    pred = prediction.strip()[:1].upper()
    return 1.0 if pred in {t.strip()[:1].upper() for t in targets} else 0.0
```

- `normalize`：`"  Hello  WORLD "` → `"hello world"`。只处理大小写与空白，不处理标点、数字格式、冠词（SQuAD 风格的归一化还会去标点和 a/an/the）。实测 `"25"` vs `"25.0"`、`"4."` vs `"4"`、`"The answer is 4"` vs `"4"` 都是 0 分。
- `substring_contains` 是"包含即对"：实测空目标 `""` 对任何预测都得 1.0；`"evaluation"` 在 `"reevaluation is hard"` 里也算命中（没有词边界）。
- `multiple_choice` 只看首字符：`"The answer is B"`、`"(B)"` 得 0；`"Apple? no, B"` 对目标 A 反而得 1。测验 Q12 给出了用正则抽取选项字母的改进。
- `any(...)` 配生成器表达式：有一个参考命中就返回 True，且会短路。

### 3.5 ROUGE-L：LCS 动态规划

```python
def _tokens(s: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", s.lower())

def _lcs_length(a: List[str], b: List[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for ai in a:
        cur = [0] * (len(b) + 1)
        for j, bj in enumerate(b):
            if ai == bj:
                cur[j + 1] = prev[j] + 1
            else:
                cur[j + 1] = max(prev[j + 1], cur[j])
        prev = cur
    return prev[-1]
```

- 经典 LCS 递推：`L[i][j] = L[i-1][j-1] + 1`（相等）否则 `max(L[i-1][j], L[i][j-1])`。这里只保留上一行 `prev` 和当前行 `cur`，空间从 `O(mn)` 降到 `O(n)`，时间仍是 `O(mn)`。
- `metric_rouge_l` 对每个参考算 `P = LCS/len(pred)`、`R = LCS/len(ref)`、`F1 = 2PR/(P+R)`，取最大。例：`"the river flows east"` vs `"the river bends slowly"`，LCS = 2，F1 = 0.5。
- LCS 是**子序列**不是子串，允许中间有间隔，但要求顺序一致：`"mammals are cats"` vs `"cats are mammals"` 实测只有 0.333；把参考重复两遍 `"cats are mammals cats are mammals"` 得 0.667（精确率被拉低）。
- ⚠️ `_tokens` 只匹配 `[a-z0-9]+`，**中文、带重音的字母都会被丢掉**。实测两段完全相同的中文 ROUGE-L 为 0.0（而 exact match 为 1.0）。评中文要按字切分或用分词器。
- 源码里有一处冗余：`if lcs == 0: continue` 之后 `prec + rec` 不可能为 0，下面那个判断永远不触发，无害。

### 3.6 `metric_code_exec`：执行型指标与它的"沙箱"

```python
    pairs = extras.get("io_pairs") or []
    if not isinstance(pairs, list) or not pairs:
        return 0.0
    safe_globals = {"__builtins__": {"range": range, "len": len, "min": min, "max": max, "abs": abs, "int": int, "float": float}}
    local: Dict[str, object] = {}
    try:
        exec(prediction, safe_globals, local)
    except Exception:
        return 0.0
    fn = local.get("f")
    if not callable(fn):
        return 0.0
    correct = 0
    for pair in pairs:
        if not (isinstance(pair, list) and len(pair) == 2):
            continue
        x, expected = pair
        try:
            actual = fn(x)
        except Exception:
            continue
        if actual == expected:
            correct += 1
    if not pairs:
        return 0.0
    return correct / len(pairs)
```

- 流程：取 IO 对 → 在受限全局里 `exec` 预测代码（只是**定义**函数）→ 从 `local` 里拿名为 `f` 的可调用对象 → 逐对调用比较 → 返回通过比例（部分分）。
- `exec(code, globals, locals)`：顶层 `def f` 会写进 `locals` 字典，所以用 `local.get("f")` 取函数。
- 去掉 `__import__` 后 `import os` 会失败，测试据此断言"不安全代码得 0 分"。
- ⚠️ **这不是安全边界**。Python 对象内省可以绕开 builtins：`().__class__.__base__.__subclasses__()` → 找到 `os._wrap_close` → `__init__.__globals__` 就是 `os` 模块的全局变量。我们实测这样的预测能调用 `getcwd()` 并拿到 1.0 分。讲义 "you cannot reach the filesystem from a code prediction" 的说法过强。
- ⚠️ **没有超时**：`while True: pass` 会让整个 harness 卡死。测验 Q10 给出了"子进程 + 超时"的改写（并说明它仍不能防文件/网络访问，需要容器级隔离）。
- ⚠️ 末尾 `if not pairs: return 0.0` 是死代码（开头已检查）；格式错误的 IO 对被跳过却仍计入分母（实测 `[[1,2],[3,6],[5]]` 得 0.667）；`targets=["ok"]` 完全没被使用，docstring 却说 targets 是期望结果。

### 3.7 `METRIC_FNS`：统一签名的分发表

```python
METRIC_FNS: Dict[str, Callable[..., float]] = {
    "exact_match": lambda p, t, e: metric_exact_match(p, t),
    ...
    "code_exec": lambda p, t, e: metric_code_exec(p, t, e),
}
```

- 四个指标不需要 `extras`，用 `lambda` 包一层把签名统一成 `(p, t, e)`，运行器就可以不分情况地调用 `metric_fn(out, ex.targets, ex.extras)`。
- 新增指标（讲义练习 1）只需写函数并在这里注册一个名字；JSONL 里写不存在的名字会在 `METRIC_FNS[metric]` 处抛 `KeyError`。

### 3.8 JSONL 读写

```python
        for line_num, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"bad json at {path}:{line_num}: {exc}") from exc
            examples.append(Example(
                id=str(obj.get("id", f"ex-{line_num}")),
                ...
```

- 允许 `#` 注释和空行（标准 JSONL 不允许，这是给人类贡献者的方便）；出错时报出文件与行号，`raise ... from exc` 保留原始异常链。
- 缺 `id` 时用 `ex-<行号>` 兜底；`prompt`、`targets`、`metric` 用 `obj[...]` 直接取，缺失会抛 `KeyError`。
- `write_task_jsonl` 用 `**({"extras": ex.extras} if ex.extras else {})` 只在有 extras 时写入该键——一种"条件字典展开"的写法。
- `load_all_tasks` 用 `sorted(task_dir.glob("*.jsonl"))`，`path.stem` 是去掉扩展名的文件名，作为任务名。

### 3.9 运行器 `run_task` 与 `run_leaderboard`

```python
    for i in range(0, len(examples), batch_size):
        chunk = examples[i:i + batch_size]
        prompts = [ex.prompt for ex in chunk]
        outputs = adapter.generate(prompts)
        if len(outputs) != len(chunk):
            raise ValueError(...)
        for ex, out in zip(chunk, outputs, strict=True):
            score = metric_fn(out, ex.targets, ex.extras)
            correct_sum += score
            total += 1
            per_example.append({...})
    latency_ms = (time.perf_counter() - start) * 1000.0
    score = correct_sum / total if total else 0.0
    correct_int = int(round(correct_sum))
```

- `range(0, n, batch_size)` + 切片是最朴素的分批；最后一批可能不满。讲义建议"限制 batch 大小"以兼容各家 API 的速率限制。
- 先显式检查输出条数，再用 `zip(..., strict=True)`（3.10+，长度不等时抛异常）做双保险——adapter 少返回一条时如果用普通 `zip`，会静默丢样例。
- `latency_ms` 包含了**打分时间**，不只是模型调用时间；对真实 API 来说打分时间可以忽略，但 `code_exec` 很慢时会混进去。
- `correct = int(round(correct_sum))`：对部分分指标，这是"分数之和取整"，不是"完全答对的个数"（测验 Q8）。
- `run_leaderboard` 按任务名排序后逐个跑，总分 `sum(r.score)/len(results)` 是**宏平均**：每个任务权重相同，与样例数无关（测验 Q6）。
- 空任务返回 `metric="none"`、`score=0.0`，但仍参与宏平均，会把总分拉低。

### 3.10 排行榜 JSON 与 `main`

```python
    payload = {
        "schema": board.schema,
        "timestamp": board.timestamp,
        "overall_score": board.overall_score,
        "adapter": adapter_name,
        "tasks": [ {...,  **({"per_example": r.per_example} if include_per_example else {})} for r in board.tasks ],
    }
```

- `schema: "leaderboard.v1"`：格式变化时升版本号，看板可以据此拒绝/兼容旧格式。
- `timestamp` 每次都不同，所以两次运行的 JSON 字节上永远不同；"可复现"指分数可复现，diff 时应忽略这类元数据。
- `main` 中 `if args.seed_fixtures or not args.task_dir.exists() or not list(args.task_dir.glob("*.jsonl"))`：显式要求或目录为空时才生成 fixture，避免覆盖用户自己的任务。adapter 写死为 `ToyAdapter()`，讲义说接真模型时就在这里替换。
- 打印用 `{r.task:>16}` 右对齐、`{r.score:0.3f}` 三位小数。
- ⚠️ 仓库自带的 `outputs/leaderboard.json` 中 `"adapter": "arithmetic"`，而当前代码写出的是 `"toy.v1"`——这份产物应是旧版本代码生成的，与现有代码不一致。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| JSONL 一行一个样例、文件名即任务名 | 好 diff、好追加、人能读 | 没有任务级元数据（版本、哈希）；生产加 YAML 任务配置与 sha256 |
| 指标统一为 `(p, t, e) → [0,1]` | 运行器无需分情况；易于单测 | 无法表达"需要模型对数似然"的指标（选择题的 loglikelihood 评测） |
| `Protocol` 定义 adapter | 不强制继承，测试桩随手写 | 运行时不校验；可用 `runtime_checkable` 或显式检查 |
| `ToyAdapter` 按 fixture 写死答案 | 让每个指标都被执行到 | 满分无信息量；应同时报告常数/回声/lead-1 等基线 |
| 首字符判选择题、子串判生成 | 实现极简 | 易误判、易被钻空子；生产用答案抽取正则或对数似然 |
| `[a-z0-9]+` 分词的 ROUGE-L | 无依赖、可审计 | 中文得 0；生产用按字/分词器切分，或用 `rouge-score` 等库 |
| `exec` + 去掉 builtins | 一行实现"受限执行" | 可被内省逃逸、无超时；生产用子进程 + 容器沙箱 + 资源限制 |
| AST 白名单算术 | 避免 `eval` 执行任意代码 | `Pow` 可构造计算炸弹；需要限制指数或加超时 |
| 宏平均总分 | 小任务不被大任务淹没 | 小任务噪声被放大；要同时报告样例数与置信区间 |
| `latency_ms` 计入打分时间 | 实现简单 | 不能准确反映模型延迟；应分别计时 |
| JSON 带 `schema` 与 `timestamp` | 格式可演进、知道何时跑的 | 缺少任务哈希、代码版本、解码参数（讲义练习 5） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + `field(default_factory=...)` | `extras: Dict[str, object] = field(default_factory=dict)` | 可变默认值必须用工厂，避免实例间共享 |
| `asdict`（已导入） | `from dataclasses import dataclass, field, asdict` | 把 dataclass 转字典；本文件导入了但没用到 |
| `typing.Protocol` | `class ModelAdapter(Protocol)` | 结构化子类型：有相同方法即视为实现 |
| `@property` | `def name(self) -> str` | 在协议里声明一个只读属性 |
| 类属性 | `ToyAdapter.name = "toy.v1"` | 满足协议的 `name` 属性 |
| 字符串切片与 `startswith` | `text[len("compute:"):]` | 去掉前缀（3.9+ 也可用 `str.removeprefix`） |
| 正则后行断言 | `re.split(r"(?<=[.!?])\s+", body)` | 在句末标点**之后**的空白处切分，标点保留在句子里 |
| `re.findall` / `re.sub` | `re.findall(r"[a-z0-9]+", s.lower())` | 抽取所有匹配 / 替换 |
| `ast` 模块 | `ast.parse(expr, mode="eval")`、`isinstance(node, ast.BinOp)` | 把代码解析为语法树并逐节点检查 |
| 类作为字典键 | `_ARITH_OPS[type(node.op)]` | `type()` 取节点类型查表 |
| `operator` 模块 | `operator.add`、`operator.truediv` | 运算符的函数形式 |
| 递归 | `_safe_eval(node.left)` | 树结构的自然处理方式 |
| `any` + 生成器 | `any(normalize(t) == norm_pred for t in targets)` | 有一个为真即返回 True，短路求值 |
| 集合推导式 | `{t.strip()[:1].upper() for t in targets}` | 构造集合，`in` 查询 O(1) |
| `lambda` | `lambda p, t, e: metric_exact_match(p, t)` | 匿名函数，用来统一签名 |
| `Callable[..., float]` | `METRIC_FNS: Dict[str, Callable[..., float]]` | `...` 表示参数不限 |
| `exec(code, globals, locals)` | `exec(prediction, safe_globals, local)` | 动态执行代码；`__builtins__` 键控制可用内置函数 |
| `callable()` | `if not callable(fn)` | 判断对象能否被调用 |
| 元组解包 | `x, expected = pair` | 列表也能解包 |
| `enumerate(f, start=1)` | 逐行读文件并带行号 | 行号从 1 开始 |
| `raise ... from exc` | `raise ValueError(...) from exc` | 保留异常链，便于调试 |
| 字典展开 `**` | `**({"extras": ex.extras} if ex.extras else {})` | 条件地往字典字面量里加键 |
| `zip(..., strict=True)` | `zip(chunk, outputs, strict=True)` | 长度不等时抛 `ValueError`（3.10+） |
| `range(start, stop, step)` + 切片 | `examples[i:i + batch_size]` | 分批 |
| `time.perf_counter()` | 计时 | 单调高精度时钟，适合测耗时 |
| f-string 格式符 | `{i:02d}`、`{r.task:>16}`、`{r.score:0.3f}` | 补零、右对齐、小数位 |
| `argparse` 的 `type=Path` | `p.add_argument("--task-dir", type=Path, ...)` | 参数自动转成 `Path` 对象 |
| `with path.open(...)` | 读写 JSONL | 上下文管理器保证文件关闭 |

---

## 6. 运行结果解读

实际运行（`python3 main.py --out /tmp/.../l49_lb.json`，任务目录已有 5 个 JSONL，故未重新生成 fixture）：

```text
loaded 5 tasks: ['arithmetic', 'code-exec', 'generation', 'multiple-choice', 'summary']
overall_score = 1.000
        arithmetic  metric=       exact_match  score=1.000  (5/5)  latency_ms=0.2
         code-exec  metric=         code_exec  score=1.000  (5/5)  latency_ms=0.1
        generation  metric=substring_contains  score=1.000  (5/5)  latency_ms=0.0
   multiple-choice  metric=   multiple_choice  score=1.000  (5/5)  latency_ms=0.0
           summary  metric=           rouge_l  score=1.000  (5/5)  latency_ms=0.2
wrote /home/claude/work/tmp/b67/l49_lb.json
```

逐项解读：

- **任务按名字排序**：`sorted(task_dir.glob(...))` 与 `sorted(tasks)` 共同决定了顺序，保证每次输出顺序一致。
- **全部 1.000**：讲义 "Overall score is 1.0 with the toy adapter" 吻合。原因见 3.2——Toy 是对着 fixture 写的。
- **latency 只有零点几毫秒**：Toy 是纯 Python 字符串处理；换成真实 API 会是每批数百毫秒到数秒。
- 写出的 JSON 中 `"adapter": "toy.v1"`；仓库里旧的 `outputs/leaderboard.json` 却是 `"arithmetic"`，说明那份是旧代码产物。
- 加 `--include-per-example --batch-size 2` 后，每个任务多出 `per_example` 数组，形如 `{"id": "arith-00", "prompt": "compute: 2 + 2", "prediction": "4", "targets": ["4"], "score": 1.0}`。

用其他 adapter 做的对照（我们额外运行的结果）：

| adapter | arithmetic | code-exec | generation | multiple-choice | summary | 总分 |
|---------|-----------|-----------|-----------|----------------|---------|------|
| `ToyAdapter` | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.00 |
| 永远返回 `"A"` | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.20 |
| 回声（返回 prompt 正文） | 0.0 | 0.0 | 1.0 | 1.0 | 0.698 | 0.54 |
| 测试里的 `StubAdapter`（返回空串） | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00 |

一个"什么都不懂"的回声模型就能拿到 0.54，说明 fixture 只适合验证管线，不适合比较模型。

---

## 7. 动手改一改

1. **基线报告**：把"常数 A""回声""空串"三个 adapter 加进 `main`，排行榜里每个任务同时列出基线分数（测验 Q9）。
2. **（练习 1）** 新增第六个任务 `bleu-lite`：写一个 n-gram 精确率 + 简短惩罚的指标，注册到 `METRIC_FNS`，并写 2 个单元测试。
3. **（练习 2）** 扩展 `code_exec`：用 `contextlib.redirect_stdout` 捕获 `print` 输出，支持 `extras["expected_stdout"]`；再按测验 Q10 改成子进程 + 超时执行。
4. **（练习 3、5）** 在排行榜中为每个任务写入 `sha256`，并实现 `diff_leaderboards(old, new)`（测验 Q11 有已验证的实现），再对 `per_example` 做逐样例 diff。
5. **（练习 4）** 给每个样例的 adapter 调用加超时（例如 `concurrent.futures.ThreadPoolExecutor` 的 `future.result(timeout=...)`），排行榜新增 `timeouts` 列，并把模型调用耗时与打分耗时分开统计。
6. **中文支持**：把 `_tokens` 改成"英文按词、中文按字"，验证两段相同中文的 ROUGE-L 从 0.0 变为 1.0。

---

## 8. 常见坑

- **运行 `main.py` 不加 `--out`**：会覆盖仓库中的 `outputs/leaderboard.json`。
- **把 Toy 的满分当成 harness 有效的证据**：要用基线 adapter 检查任务能否区分模型。
- **答案格式不一致**：`"25"` vs `"25.0"`、`"(B)"` vs `"B"` 都会判错；归一化规则要先定好并版本化。
- **选择题答案分布不均**：本 fixture 全是 A，常数答案即满分。
- **把 `exec` 去掉 builtins 当沙箱**：可以内省逃逸，也没有超时。
- **ROUGE 用于中文**：`[a-z0-9]+` 分词让中文得 0 分。
- **把 `correct` 当完全答对数**：部分分指标下它只是分数和的取整。
- **只看总分**：宏平均下 5 题的任务和 500 题的任务权重一样；要看每任务的 `total` 和置信区间。
- **adapter 返回条数不对**：代码会抛错而不是静默错位——自己写运行器时也要保留这个检查。
- **用 `python -O` 运行**：`assert` 被跳过，同一文件混用 metric 不会被发现。

---

## 9. 测试在验证什么

`test_main.py` 用 `unittest` 编写，`import main as harness`，共 5 组 13 个用例（与讲义 "13 cases" 一致）：

| 测试 | 验证的性质 |
|------|-----------|
| `test_exact_match_normalizes_case_and_whitespace` | `"  Hello  WORLD "` 与 `"hello world"` 相等；`"hello"` 与 `"hi"` 不等 |
| `test_multiple_choice_uses_first_letter` | `"a) the apple"` 首字母 A 命中；`"B"` 对目标 A 不命中 |
| `test_rouge_l_returns_perfect_on_identical_strings` | 完全相同得 1.0 |
| `test_rouge_l_partial_overlap_below_one` | 部分重叠在 (0, 1) 之间（实际值 0.5，测试只检查区间） |
| `test_substring_contains_truthy_when_target_inside` | 包含与不包含两种情况 |
| `test_code_exec_runs_pairs_and_blocks_unsafe` | 正确的 `x * 2` 得 1.0；`import os` 的预测得 0.0 |
| `test_arith_eval_basic_ops` | `1 + 2 * 3 = 7`（优先级由 AST 保证）、`(8 - 2) / 3 = 2.0` |
| `test_arith_eval_rejects_calls` | `__import__('os').system('echo')` 抛 `ValueError` |
| `test_round_trip_jsonl` | 写入再读回，条数、metric、id 一致 |
| `test_load_skips_comments_and_blanks` | `#` 注释与空行被跳过，只读到 1 条 |
| `test_runner_full_score_with_toy_adapter` | 生成 fixture 到临时目录，5 个任务、每个 5 条，分数都 > 0.5，schema 正确 |
| `test_runner_handles_mixed_failure` | 返回空串的 `StubAdapter` 在所有任务上得 0，总分 0 |
| `test_leaderboard_json_contains_schema` | JSON 含 schema 与 adapter 名；默认不含 `per_example`，打开开关后含 |

- 所有涉及文件的测试都用 `tempfile.TemporaryDirectory()`，不会改动仓库中的 `outputs/`。
- `test_runner_full_score_with_toy_adapter` 只要求 `> 0.5`，比讲义说的"全部满分"宽松。

运行方式与实际结果：

```text
$ cd code && python3 -m pytest -q
.............                                                            [100%]
13 passed in 0.03s

$ python3 -m unittest test_main
Ran 13 tests in 0.009s
OK
```

测试没有覆盖、值得补充的地方：

- `code_exec` 的内省逃逸与死循环（现有测试只证明了 `import os` 被挡住）；
- 中文文本的 ROUGE-L；
- `exact_match` 的数值格式差异；
- 选择题非首字母格式（`"(B)"`、`"The answer is B"`）；
- 常数/回声基线不能拿高分（这才是"任务有区分度"的测试）。
