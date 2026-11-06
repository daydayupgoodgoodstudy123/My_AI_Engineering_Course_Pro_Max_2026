# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 70 节 任务规范格式 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（测试：`python3 -m pytest -q` 或 `python3 -m unittest discover tests`） ｜ **依赖**：仅标准库（`json`、`re`、`dataclasses`、`tempfile` 等）

---

## 1. 这份代码在考察什么

这一节不打分、不调模型、不执行代码，只做一件事：**把评估任务的"合同"写死**。代码围绕四个问题展开：

1. **记录长什么样**：一条任务就是一行 JSON，6 个必填字段 + 2 个可选字段，多一个字段都不行。
2. **哪些取值合法**：category、metric、post-process 三套封闭词表，以及 category 与 metric 的合法组合表。
3. **坏数据怎么处理**：校验器逐行检查，坏行记录一个结构化错误后继续，最后返回 `(合法任务, 错误列表)`。
4. **任务如何变成 prompt、生成如何变成答案**：`render_prompt` 统一渲染 few-shot，`post_process` 用确定性规则从模型输出中抽取答案。

后续 71–75 课都会 `import` 这里的 `TaskSpec`、`render_prompt`、`post_process`（第 75 课直接按路径加载本文件），所以这份代码是整个评估轨道的"地基"。

> 一句话：**先让数据形状不可协商，后面的打分才有意义**。同时要看清代码与讲义在哪些地方不一致——这些不一致恰恰说明"契约必须写成可执行代码 + 测试"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `REQUIRED_FIELDS` / `OPTIONAL_FIELDS` / `ALLOWED_FIELDS` | 常量 | 字段白名单 | 记录形状 |
| `CATEGORIES` / `METRICS` / `POST_PROCESS` | 常量元组 | 三套封闭词表 | closed vocabulary |
| `LEGAL_CATEGORY_METRIC` | 常量字典 | category → 允许的 metric 集合 | 组合约束 |
| `FEW_SHOT_MAX`、`TASK_ID_RE`、`MCQ_TARGET_RE` | 常量 | few-shot 上限 8、ID 字符集、MCQ 单字母 | 字段规则 |
| `ValidationError` | dataclass | 一条错误：行号、task_id、规则、字段、详情 | 结构化错误 |
| `TaskSpec` | dataclass | 通过校验后的强类型任务 | 规范化记录 |
| `_check_required` / `_check_unknown_fields` / `_check_types` / `_check_category_metric` | 私有函数 | 分层检查，返回第一个问题或 `None` | 校验流水线 |
| `_embedded_few_shot` | 私有函数 | 启发式判断 prompt 里是否已内嵌示例 | few-shot 归 runner |
| `validate_task` | 函数 | 单条记录校验，最多返回 1 个错误 | 校验器 |
| `validate_file` | 函数 | 逐行解析 JSONL、校验、查重，返回两个列表 | 校验器 |
| `render_prompt` | 函数 | few-shot + prompt 用空行拼接 | few-shot 渲染 |
| `post_process` | 函数 | 6 条确定性抽取规则 | 答案后处理 |
| `fixture_tasks` / `bad_fixture_tasks` | 函数 | 10 条合法 + 10 条非法夹具 | fixture |
| `write_jsonl` / `load_fixtures` | 函数 | 把夹具写成 `tasks.jsonl` / `tasks_bad.jsonl` | 夹具加载 |
| `demo` | 函数 | 校验两个夹具文件并打印摘要，返回退出码 | 入口 |

数据流：`fixture_tasks()` → `write_jsonl` → `tasks.jsonl` → `validate_file`（`json.loads` → `validate_task` → 查重）→ `list[TaskSpec]` → `render_prompt` → （模型生成，后续课程）→ `post_process` → metric（71/72 课）。

---

## 3. 逐段精讲

### 3.1 常量：把"合同"写成数据

```python
REQUIRED_FIELDS = ("task_id", "category", "prompt", "targets", "metric_name", "post_process")
OPTIONAL_FIELDS = ("few_shot_examples", "metadata")
ALLOWED_FIELDS = set(REQUIRED_FIELDS) | set(OPTIONAL_FIELDS)

CATEGORIES = ("arithmetic", "mcq", "code_exec", "classification", "summary")
METRICS = ("exact_match", "f1", "bleu_4", "rouge_l", "accuracy", "code_exec")
POST_PROCESS = ("none", "strip_whitespace", "lower", "extract_letter",
                "extract_code_block", "extract_first_line")

LEGAL_CATEGORY_METRIC = {
    "arithmetic": {"exact_match", "f1"},
    "mcq": {"exact_match", "accuracy"},
    "code_exec": {"code_exec"},
    "classification": {"exact_match", "accuracy", "f1"},
    "summary": {"exact_match", "f1", "bleu_4", "rouge_l"},
}
```

- 词表用**元组**（不可变），合法组合用 `dict[str, set]`，查找是 O(1)。把规则写成数据而不是一堆 `if`，好处是规则一目了然、改动集中、可以直接被测试引用（测试导入了 `FEW_SHOT_MAX`）。
- `ALLOWED_FIELDS` 用集合并运算 `|` 得到 8 个字段，用于"未知字段一律拒绝"。
- **注意**：讲义说 "a `mcq` task must use `metric_name = exact_match`"，代码允许 `exact_match` 和 `accuracy` 两种；讲义还说 category 约束 "metric and post-process pair"，但代码**没有** category–post_process 表（见 3.4 与测验 Q9）。

```python
FEW_SHOT_MAX = 8
TASK_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
MCQ_TARGET_RE = re.compile(r"^[A-E]$")
```

- 讲义只说 `task_id` "no whitespace"，代码更严格：只允许字母、数字、下划线、连字符，`"a.b"`、`"中文"` 也会被拒。
- MCQ target 必须是**单个大写** `A–E`，所以最多支持 5 个选项。

### 3.2 两个 dataclass：错误与任务

```python
@dataclass
class ValidationError:
    line_number: int
    task_id: str
    rule: str
    field_name: str
    detail: str

    def to_dict(self) -> dict:
        return {"line_number": ..., "task_id": ..., "rule": ..., "field": self.field_name, "detail": ...}
```

- 错误不是一句字符串，而是**五元组**：在哪一行、哪个任务、违反哪条规则、哪个字段、细节。这正是讲义要求的 "the offending line, the violated rule, and the field at fault"。结构化错误可以按 `rule` 聚合统计、可以写进 CI 报告。
- 属性叫 `field_name`、`to_dict` 里输出的键叫 `"field"`——因为 `field` 已经从 `dataclasses` 导入，作属性名会遮蔽它，容易引起混淆。

```python
@dataclass
class TaskSpec:
    ...
    few_shot_examples: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
```

- 可变默认值必须用 `field(default_factory=list)`；直接写 `= []` 在 dataclass 中会报 `ValueError`（防止所有实例共享同一个列表）。
- `to_dict` 中 `list(self.targets)`、`dict(self.metadata)` 是**浅拷贝**，调用方修改返回值不会改到 TaskSpec 本身。

### 3.3 分层检查函数：返回"第一个问题"

```python
def _check_required(record: dict) -> tuple[str, str] | None:
    for f in REQUIRED_FIELDS:
        if f not in record:
            return ("missing_required", f)
    return None
```

- 每个 `_check_*` 的约定相同：发现问题返回一个元组 `(rule, field[, detail])`，没问题返回 `None`。调用方用 `if missing:` 判断。
- 返回类型注解 `tuple[str, str] | None` 依赖文件顶部的 `from __future__ import annotations`（注解延迟求值），在旧版 Python 上也能写这种语法。

`_check_types` 是最长的一个，按字段顺序逐条检查：

```python
    if not isinstance(record["task_id"], str):
        return ("bad_type", "task_id", "must be string")
    if not TASK_ID_RE.match(record["task_id"]):
        return ("bad_value", "task_id", "must match [A-Za-z0-9_-]+")
    if record["category"] not in CATEGORIES:
        ...
    if record["prompt"] != record["prompt"].rstrip():
        return ("bad_value", "prompt", "trailing whitespace not allowed")
    if not isinstance(record["targets"], list) or not record["targets"]:
        return ("bad_type", "targets", "must be non-empty list")
    ...
    if "few_shot_examples" in record:
        if len(record["few_shot_examples"]) > FEW_SHOT_MAX:
            return ("bad_value", "few_shot_examples", f"max {FEW_SHOT_MAX} entries")
        for ex in record["few_shot_examples"]:
            ...
```

- `bad_type`（类型不对）与 `bad_value`（类型对、取值不对）分开，便于统计。
- **尾随空白**禁令：`"Answer: "` 这种结尾空格会让模型倾向于生成不带前导空格的 token，不同 tokenizer 下行为不同；统一禁止可以减少隐性方差。前导空白则不检查。
- 空 targets 被定为 `bad_type` 而不是 `bad_value`，命名上略不一致（测试只检查 `field_name`，不检查 rule）。
- `isinstance(record["targets"], list)` 意味着 JSON 里写成字符串 `"41"` 会被拒——这是故意的，避免把字符串当成字符列表迭代。

### 3.4 category–metric 组合与 MCQ 规则

```python
def _check_category_metric(record: dict) -> tuple[str, str, str] | None:
    cat = record["category"]
    metric = record["metric_name"]
    if metric not in LEGAL_CATEGORY_METRIC[cat]:
        return ("illegal_pair", "metric_name", f"{metric} not allowed for category {cat}")
    if cat == "mcq":
        if len(record["targets"]) != 1:
            return ("bad_value", "targets", "mcq needs exactly one target")
        if not MCQ_TARGET_RE.match(record["targets"][0]):
            return ("bad_value", "targets", "mcq target must be a letter A-E")
    return None
```

- 这个函数能安全地写 `LEGAL_CATEGORY_METRIC[cat]`，是因为它在 `_check_types` **之后**调用，那时 `cat` 一定在 `CATEGORIES` 里。**检查顺序本身就是正确性的一部分**。
- **注意**：只约束了 metric。实测 `mcq + accuracy + none`、`code_exec + code_exec + lower` 都能通过：前者模型说 "The answer is A." 会被原样比较、永远判错；后者把代码小写后 `True` 变 `true`，必然执行失败。测验 Q9 给出了补上 `LEGAL_CATEGORY_POST_PROCESS` 的写法（实测 23 个测试仍全部通过）。

### 3.5 嵌入式 few-shot 启发式

```python
def _embedded_few_shot(prompt: str) -> bool:
    lowered = prompt.lower()
    markers = ("question:", "q:", "example:")
    hits = sum(lowered.count(m) for m in markers)
    return hits > 1
```

- 思路：一个 prompt 里出现两个以上 "Question:/Q:/Example:"，多半是作者把示例直接写进了 prompt。讲义要求 few-shot 必须放在 `few_shot_examples` 里，由 runner 渲染。
- **注意**：`str.count` 是**子串计数**：`"faq:"`、`"iraq:"` 都含有 `"q:"`。实测 `"Read the FAQ: shipping.\nQ: how long?\nA:"` 被判为 `embedded_few_shot`（误报）。而 `Input:/Output:` 风格的内嵌示例完全检测不到（漏报）。
- 注意 `"question:"` 里并不包含 `"q:"`（`q` 后面是 `u`），所以单个 `Question:` 只算 1 次。

### 3.6 `validate_task`：单条记录的流水线

```python
def validate_task(record: dict, line_number: int = 0) -> list[ValidationError]:
    errors: list[ValidationError] = []
    tid = record.get("task_id", "?") if isinstance(record, dict) else "?"
    if not isinstance(record, dict):
        errors.append(ValidationError(line_number, "?", "bad_type", "_root", "not an object"))
        return errors
    missing = _check_required(record)
    if missing:
        errors.append(ValidationError(line_number, str(tid), missing[0], missing[1], "required field"))
        return errors
    ...
    if _embedded_few_shot(record["prompt"]) and not record.get("few_shot_examples"):
        errors.append(ValidationError(..., "embedded_few_shot", "prompt", "..."))
    return errors
```

- 顺序：非对象 → 缺必填 → 未知字段 → 类型/取值 → 组合 → 嵌入式 few-shot。每一步出错就 `return`，所以**一条记录最多一个错误**。好处是后面的检查可以放心假设前面的条件成立（如字段一定存在、类型一定正确）；代价是作者要"改一个、跑一次、再改下一个"。
- `str(tid)`：`task_id` 可能是数字甚至列表（类型检查前），先转成字符串再放进错误对象。
- **注意**：最后一步带了 `and not record.get("few_shot_examples")`：只要作者填了 few-shot 列表，prompt 里再嵌示例也能通过，和讲义"拒绝 prompt 中已有 few-shot 块"的说法不一致（测验 Q12）。

### 3.7 `validate_file`：逐行、容错、查重

```python
    with open(path, "r", encoding="utf-8") as fp:
        for i, raw in enumerate(fp, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(ValidationError(i, "?", "bad_json", "_line", str(exc)))
                continue
            line_errors = validate_task(record, line_number=i)
            if line_errors:
                errors.extend(line_errors)
                continue
            tid = record["task_id"]
            if tid in seen_ids:
                errors.append(ValidationError(i, tid, "duplicate_task_id", "task_id", "already seen"))
                continue
            seen_ids.add(tid)
            validated.append(TaskSpec(...))
```

- 对应讲义的流程图：解析失败 → 记错误继续；校验失败 → 记错误继续；重复 ID → 记错误继续；否则加入合法集合。"A bad line aborts that record, not the run."
- 迭代文件对象是**逐行流式读取**，大文件不会一次性读进内存。
- 行号从 1 开始；空行被跳过但仍占行号，报告里的行号与编辑器里的一致。
- 查重放在 `validate_task` 之后：只有合法记录才进入 `seen_ids`，所以"非法记录 + 同 ID 的合法记录"不会误报重复。
- **注意**：讲义说 "The runner refuses to start if the error list is non-empty unless an explicit `--allow-bad-tasks` flag is set"——这个参数在本文件中不存在，`demo()` 也不解析任何命令行参数。

### 3.8 `render_prompt`：few-shot 渲染

```python
def render_prompt(task: TaskSpec) -> str:
    parts: list[str] = []
    for ex in task.few_shot_examples:
        parts.append(f"{ex['prompt']} {ex['completion']}")
    parts.append(task.prompt)
    return "\n\n".join(parts)
```

- 每个示例是 `prompt + 空格 + completion`，示例之间、示例与正题之间用空行分隔，正题放最后、以 `Answer:` 结尾留给模型续写。
- 实测 `arith_001` 渲染结果为 `"Question: 2 + 2\nAnswer: 4\n\nCompute the result.\nQuestion: 17 + 24\nAnswer:"`，长度 72（demo 输出的 `len=72`）。
- f-string 里用了单引号 `ex['prompt']`，因为外层是双引号；Python 3.12 之前 f-string 内部不能复用同种引号。
- 讲义里的 `render(task)` 版本用 `task.get(...)` 处理字典，代码版本处理的是 `TaskSpec` 对象，二者逻辑相同。

### 3.9 `post_process`：六条确定性规则

```python
CODE_BLOCK_RE = re.compile(r"```(?:[a-zA-Z0-9_]*)\n(.*?)```", re.DOTALL)
LETTER_RE = re.compile(r"(?:^|[^A-Za-z])([A-E])(?:[^A-Za-z]|$)")
LETTER_FALLBACK_RE = re.compile(r"[A-E]")

def post_process(text: str, rule: str) -> str:
    if rule == "none":
        return text
    if rule == "strip_whitespace":
        return text.strip()
    if rule == "lower":
        return text.lower()
    if rule == "extract_letter":
        m = LETTER_RE.search(text)
        if m:
            return m.group(1)
        m2 = LETTER_FALLBACK_RE.search(text)
        return m2.group(0) if m2 else ""
    if rule == "extract_code_block":
        m = CODE_BLOCK_RE.search(text)
        return m.group(1) if m else text
    if rule == "extract_first_line":
        for line in text.splitlines():
            if line.strip():
                return line.strip()
        return ""
    raise ValueError(f"unknown post_process rule: {rule}")
```

逐条看（括号内为实测结果）：

- **`extract_letter`**：先找"两侧都不是英文字母"的独立大写 `A–E`，找不到再退回"第一个 `A–E`"。
  - `"Answer: C is correct"` → `"C"`（`Answer` 里的 `A` 后面紧跟 `n`，被跳过）。讲义写的是 "returns the first character that matches `[A-E]`"，按字面应得 `"A"`，代码比讲义聪明。
  - `"A good choice is C"` → `"A"`（冠词被当成答案）；`"The answer is (b)."` → `""`（不认小写）；`"ABCD"` → `"A"`（fallback 在"猜"）。
- **`extract_code_block`**：匹配 ```` ``` ```` + 可选语言标签 + **换行** + 内容（非贪婪 `.*?`，`re.DOTALL` 让 `.` 跨行）+ ```` ``` ````。
  - 语言标签只允许 `[a-zA-Z0-9_]`：```` ```c++ ```` 或 ```` ```py ```` 后面多一个空格都会匹配失败。
  - 匹配失败时**原样返回整段文本**；而第 72 课的 `extract_code` 在"有反引号但匹配失败"时返回 `None`。两课的同名规则行为不一致。
- **`extract_first_line`**：返回第一个非空行（并去掉两端空白），全空返回 `""`。
- 未知规则抛 `ValueError`——正常情况下校验器已经挡住了未知规则，这里是"防御性编程"。

### 3.10 夹具与 demo

- `fixture_tasks()`：arithmetic、mcq、code_exec、classification、summary 各 2 条。code_exec 的 `targets` 是**断言表达式字符串**（如 `"add(1, 2) == 3"`），第 72 课会在子进程里逐条 `eval`。summary 两条分别用 `rouge_l` 和 `bleu_4`，演示"同一 category 可以用不同 metric"。
- `bad_fixture_tasks()`：10 条，每条只犯一个错，所以错误数 = 记录数。**注意**：讲义说它 "trips every rule"，实际上没有覆盖 `bad_json`、`duplicate_task_id`、`embedded_few_shot`、few-shot 上限、MCQ 非字母 target、`metadata` 类型等规则（部分由单元测试覆盖）。
- `demo()`：在 `tempfile.mkdtemp` 创建的目录里写两个文件、校验、打印前 5 个错误，并演示一次渲染和 `strip_whitespace`。返回码：0 正常；1 合法夹具出错；2 坏夹具错误数不等于记录数。`sys.exit(demo())` 把返回值变成进程退出码，CI 可以直接用。
- **注意**：`mkdtemp` 创建的目录不会被删除，每运行一次就在系统临时目录留下一个 `aie_l70_*` 目录（测试里用的是会自动清理的 `TemporaryDirectory`）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| JSONL，一行一条 | 可流式读取、可 `git diff`、坏行只影响一条 | 不适合嵌套很深的数据；生产也常用 JSONL + 外部 schema 文件 |
| 封闭词表 + 拒绝未知字段 | 下游可以安全分派；防止"悄悄扩展" | 每次扩展都要改代码和测试；生产会给 spec 打版本号 |
| 规则写成常量表 | 集中、可读、可被测试引用 | 规则多了之后可以改用 JSON Schema / Pydantic 声明 |
| 每条记录只报第一个错误 | 后续检查可以假设前置条件成立，代码简单 | 作者要多轮修复；可改为在类型检查之后继续收集独立错误 |
| 查重放在文件级 | 单条记录不知道其他记录 | 多文件/分片时需要全局查重 |
| few-shot 由 runner 渲染 | 所有模型看到相同 prompt | 若某模型需要 chat 模板，需在渲染之后再做模板化 |
| post-process 只允许一条规则 | 确定、可复现、易审计 | 有时需要"先抽代码块再 strip"，只能新增组合规则 |
| 嵌入式 few-shot 用子串计数 | 实现简单 | 误报 `faq:`、漏报 `Input/Output` 风格；应改为行首正则并人工复核 |
| category 只约束 metric | 代码量小 | 与讲义不符，允许 `mcq + none` 这类必然出错的组合 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 注解延迟求值，可以在旧版本里写 `list[str]`、`X \| None` |
| 元组常量 | `CATEGORIES = ("arithmetic", ...)` | 不可变序列，适合做词表；`in` 判断成员 |
| 集合运算 | `set(REQUIRED_FIELDS) \| set(OPTIONAL_FIELDS)` | `\|` 求并集 |
| `re.compile` 与锚点 | `re.compile(r"^[A-Za-z0-9_\-]+$")` | 预编译正则；`^ $` 锚定整串；`r""` 原始字符串避免反斜杠转义 |
| 非捕获组 / 捕获组 | `(?:^\|[^A-Za-z])([A-E])` | `(?:...)` 只分组不捕获；`m.group(1)` 取第一个捕获组 |
| `re.DOTALL` 与非贪婪 | `r"```...\n(.*?)```", re.DOTALL` | 让 `.` 匹配换行；`*?` 尽量少匹配，只取第一个代码块 |
| `@dataclass` | `class TaskSpec:` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=list)` | `few_shot_examples: list[dict] = field(...)` | 可变默认值的正确写法 |
| 类型注解 | `-> tuple[str, str] \| None` | 说明返回"元组或 None"；运行时不强制 |
| `isinstance` | `isinstance(record["targets"], list)` | 运行时类型检查 |
| 条件表达式 | `record.get("task_id", "?") if isinstance(record, dict) else "?"` | 一行内的 if/else |
| `dict.get` 默认值 | `record.get("few_shot_examples", [])` | 键不存在时返回默认值而不是抛 `KeyError` |
| 生成器表达式 | `sum(lowered.count(m) for m in markers)` | 不建中间列表直接求和 |
| `enumerate(..., start=1)` | `for i, raw in enumerate(fp, start=1)` | 同时拿到行号和内容，从 1 开始计数 |
| `with open(...)` | `with open(path, "r", encoding="utf-8") as fp` | 上下文管理器，自动关闭文件；显式指定编码 |
| `try/except` 指定异常 | `except json.JSONDecodeError as exc` | 只捕获 JSON 解析错误，其余异常照常抛出 |
| `continue` | 坏行后 `continue` | 跳过本次循环剩余部分 |
| f-string 与 `!r` | `f"... pp={pp!r}"` | `!r` 调用 `repr()`，能看出字符串里的空白和引号 |
| `raise ValueError` | `raise ValueError(f"unknown post_process rule: {rule}")` | 主动抛出异常表示调用方传错了参数 |
| 函数内 `import` | `demo()` 里 `import tempfile` | 只在需要时导入；作用域仅限函数内 |
| `typing.Iterable` | `def write_jsonl(path, records: Iterable[dict])` | 表示任何可迭代对象（列表、生成器都行） |
| `if __name__ == "__main__"` + `sys.exit` | `sys.exit(demo())` | 直接运行时才执行 demo，并把返回值作为进程退出码 |

---

## 6. 运行结果解读

实际运行（Python 3.13，仅标准库）：

```text
$ python3 main.py
good fixture: validated=10 errors=0
bad fixture: validated=0 errors=10
  {'line_number': 1, 'task_id': '?', 'rule': 'missing_required', 'field': 'task_id', 'detail': 'required field'}
  {'line_number': 2, 'task_id': 'bad space', 'rule': 'bad_value', 'field': 'task_id', 'detail': 'must match [A-Za-z0-9_-]+'}
  {'line_number': 3, 'task_id': 'wrong_cat', 'rule': 'bad_value', 'field': 'category', 'detail': "must be one of ['arithmetic', 'classification', 'code_exec', 'mcq', 'summary']"}
  {'line_number': 4, 'task_id': 'bad_pair', 'rule': 'illegal_pair', 'field': 'metric_name', 'detail': 'bleu_4 not allowed for category mcq'}
  {'line_number': 5, 'task_id': 'no_target', 'rule': 'bad_type', 'field': 'targets', 'detail': 'must be non-empty list'}
sample render len=72 pp='4'
$ echo $?
0
```

逐项解读：

- **`good fixture: validated=10 errors=0`**：10 条合法夹具全部通过，覆盖 5 个 category。
- **`bad fixture: validated=0 errors=10`**：每条坏记录恰好一个错误，这依赖"每条记录只报第一个错误"的设计。demo 只打印前 5 个（`bad_errors[:5]`），后 5 个依次是：`trail_ws`（prompt 尾随空白）、`extra_field`（`unknown_field: rogue`）、`bad_metric`（`perplexity` 不在 METRICS 里）、`mcq_multi`（mcq 只能一个 target）、`bad_pp`（`fancy` 不是合法规则）。
- 第 1 行 `task_id` 为 `'?'`：记录里没有这个字段，`record.get("task_id", "?")` 取到默认值。
- 第 3 行 `detail` 中的列表是 `sorted(CATEGORIES)` 的结果（按字母序），不是定义顺序。
- **`sample render len=72`**：`arith_001` 带一条 few-shot，渲染后的字符串长度为 72（见 3.8）。
- **`pp='4'`**：`post_process("  4  \n", "strip_whitespace")` 去掉了两端空白和换行；`!r` 让引号显示出来。
- 退出码 0：合法夹具无错误，且坏夹具错误数等于记录数。

---

## 7. 动手改一改

1. **补上 category–post_process 约束**：新增 `LEGAL_CATEGORY_POST_PROCESS` 表并在 `_check_category_metric` 中检查（参考测验 Q9），再写一个 "`mcq + none` 必须报 `illegal_pair`" 的测试。
2. **收集全部错误**：把 `validate_task` 改成在类型检查通过后继续执行组合检查与 few-shot 检查，把所有独立错误都收集起来；思考哪些检查必须"短路"（例如字段缺失时无法做类型检查）。
3. **修正嵌入式 few-shot 检测**：改用 `re.findall(r"(?im)^(?:question|q|example)\s*:", prompt)`，让 `"Read the FAQ: ..."` 不再误报，并决定"有 `few_shot_examples` 时是否仍然拒绝"。
4. **实现 `--allow-bad-tasks`**：给文件加 `argparse` 入口，接收 `tasks.jsonl` 路径；错误列表非空时打印错误并以非零码退出，除非传了 `--allow-bad-tasks`。
5. **改进 `extract_letter`**：支持小写、优先识别 "answer is X" 等显式表达、否则取最后一个独立字母（参考测验 Q10），并写测试锁住 `"A good choice is C" → "C"`。
6. **进阶：spec 版本化**：给每条记录或文件头增加 `spec_version`，让校验器按版本加载不同的词表；思考旧版本任务在新版本校验器下应如何迁移。

---

## 8. 常见坑

- **以为讲义描述就是代码行为**：`extract_letter` 并非"第一个 `[A-E]` 字符"；mcq 也允许 `accuracy`；category 不约束 post-process。契约以**代码 + 测试**为准。
- **以为一条记录会报出全部问题**：校验器短路，修完一个错可能冒出下一个。
- **prompt 结尾多一个空格或换行**：`"Answer: "`、`"Answer:\n"` 都会被拒，JSON 编辑器自动加的尾随换行也算。
- **MCQ target 写成小写或完整答案**：`"b"`、`"Mercury"` 都会被 `MCQ_TARGET_RE` 拒绝；只能是单个大写 `A–E`。
- **代码块语言标签后多空格**：```` ```py  ```` 后面有空格时 `extract_code_block` 匹配失败、原样返回整段文本，下游执行会遇到语法错误。
- **few-shot 写进 prompt**：可能被判 `embedded_few_shot`，也可能因为启发式漏报而悄悄通过，导致这条任务的 prompt 与其他任务风格不一致。
- **重复 `task_id` 只在文件内检查**：同一套任务拆成多个文件时，跨文件重复不会被发现。
- **用 `bad_type` / `bad_value` 做统计时注意命名不一致**：空 targets 被记为 `bad_type`。
- **demo 留下临时目录**：多次运行会在 `/tmp` 积累 `aie_l70_*` 目录。

---

## 9. 测试在验证什么

测试文件：`tests/test_spec.py`（`unittest` 风格，pytest 也能运行）。它通过 `sys.path.insert(0, os.path.dirname(HERE))` 把 `code/` 加入导入路径，直接 `from main import ...`。

运行方式：

```bash
cd code
python3 -m pytest -q            # 或：python3 -m unittest discover tests
```

实际运行结果：`23 passed in 0.02s`。

| 测试类 / 测试 | 验证的性质 |
|--------------|-----------|
| `TestValidateTask.test_minimal_good_record` | 只含 6 个必填字段的记录合法（`good_record()` 是 `arithmetic + exact_match + strip_whitespace`） |
| `test_missing_required_fields` | 逐个删掉 6 个必填字段，每次恰好 1 个 `missing_required` 错误，字段名正确 |
| `test_unknown_top_level_field_rejected` | 多一个 `secret` 字段 → `unknown_field` |
| `test_bad_category` | `logic` 不在词表 → 错误字段为 `category` |
| `test_empty_targets_rejected` | `targets=[]` → 错误字段为 `targets` |
| `test_trailing_whitespace_rejected` | `"Q: 1+1\nA: "` 末尾空格 → 错误字段为 `prompt` |
| `test_illegal_category_metric_pair` | `mcq + bleu_4` → `illegal_pair` |
| `test_mcq_target_must_be_letter` | mcq 的 target 为 `"correct"` → 错误字段为 `targets` |
| `test_too_many_few_shot` | 9 条 few-shot（`FEW_SHOT_MAX + 1`）→ 错误字段为 `few_shot_examples` |
| `test_bad_task_id_chars` | `"has space"` → 错误字段为 `task_id` |
| `TestValidateFile.test_good_fixture_passes` | 合法夹具写盘后全部通过、无错误 |
| `test_bad_fixture_all_fail` | 坏夹具 0 条通过、错误数 = 记录数（锁定"每条一个错误"） |
| `test_duplicate_task_id` | 两条相同记录 → 1 条通过、1 个 `duplicate_task_id` |
| `test_malformed_json` | `{not json` 行 → `bad_json`，且不影响下一行合法记录 |
| `TestRender.test_render_with_few_shot` | 渲染结果包含示例与正题、以 `A:` 结尾 |
| `test_render_without_few_shot` | 没有 few-shot 时原样返回 prompt |
| `TestPostProcess.test_none / test_strip / test_lower` | 三条简单规则的行为 |
| `test_extract_letter` | `"Answer: C is right"` → `"C"`；无字母 → `""`（锁定了"跳过单词中的大写字母"） |
| `test_extract_code_block` | 从带 `python` 标签的代码块中取出函数体 |
| `test_extract_first_line` | 跳过开头空行，返回 `"first"` |
| `test_unknown_rule` | 未知规则抛 `ValueError` |

测试没有覆盖的地方（可以作为练习补充）：

- `embedded_few_shot` 规则（包括 `faq:` 误报）；
- `metadata` 非对象、targets 元素非字符串、few-shot 条目缺字段；
- `extract_letter` 的冠词误判和小写；
- `extract_code_block` 匹配失败时"原样返回"的行为；
- 记录本身不是 JSON 对象（例如一行 `[1, 2]`）时的 `_root` 错误。
