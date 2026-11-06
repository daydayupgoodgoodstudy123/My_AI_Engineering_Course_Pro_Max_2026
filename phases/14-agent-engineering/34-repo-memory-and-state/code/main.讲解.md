# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 34 节 代码仓库记忆与持久状态 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py` ｜ **依赖**：仅标准库（`json`、`os`、`re`、`tempfile`、`pathlib`、`typing`）；讲义提到 `jsonschema` 为可选，代码并未使用它
>
> **副作用**：在 `code/workdir/` 下写入 `schemas/agent_state.schema.json`、`schemas/task_board.schema.json`、`agent_state.json`、`task_board.json`。每次运行都会用初始内容**重新覆盖**状态与任务板。

---

## 1. 这份代码在考察什么

第 32 节的三文件工作台能跑，但状态文件"什么都能写进去"、写到一半崩溃就会损坏。本节给状态加上两道防线：

1. **Schema-first**：用 JSON Schema 描述 `agent_state.json` 和 `task_board.json` 的形状（必填键、类型、枚举、正则、数组元素类型、`schema_version`），写入前先验证——"a bad write is a refused write"。
2. **原子写入**：同目录临时文件 → 写入 → `fsync` → `os.replace`，任何时刻磁盘上的状态文件都是某个完整版本。

代码还实现了一个只用标准库的**迷你 JSON Schema 验证器**（支持 required / type / enum / pattern / items / properties），这样不装第三方库也能跑。

> 一句话：**状态文件是系统记录，所以写入前要验证、写入时要原子、版本要可迁移。** 但要注意：自写验证器与标准 JSON Schema 有语义差异；`update` 方法与跨文件一致性都没实现。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HERE` / `WORK` | 模块常量 | 输出目录 `code/workdir/` | — |
| `STATE_SCHEMA` | dict 常量 | 状态文件的 JSON Schema | schema-first、`schema_version` |
| `BOARD_SCHEMA` | dict 常量 | 任务板的 JSON Schema | owner/status 枚举、id 正则 |
| `SchemaError` | 异常类 | 验证失败时抛出 | 拒绝坏写入 |
| `_check_type` | 函数 | JSON 类型名 → Python 类型判断 | type 关键字 |
| `validate` | 递归函数 | 按 schema 验证任意值，错误带 JSON 路径 | 迷你验证器 |
| `atomic_write` | 函数 | 临时文件 + fsync + 原子替换 | 原子写入 |
| `StateManager` | 类 | `load`（读 + 验证）、`commit`（验证 + 原子写） | 状态管理器 |
| `main` | 函数 | 写 schema → 提交初始状态 → 读 → 改 → 提交 → 演示坏写入被拒 | 演示 |

数据流：`main` 写出两个 schema 文件 → `StateManager.commit(initial_state)` / `commit(initial_board)` → `load` → 修改 `active_task_id`、`next_action` → `commit` → 打印 → 构造坏状态 `commit` → 捕获 `SchemaError`。

---

## 3. 逐段精讲

### 3.1 两个 schema

```python
STATE_SCHEMA: dict[str, Any] = {
    "$id": "agent_state.schema.json",
    "type": "object",
    "required": ["schema_version", "active_task_id", "touched_files", "next_action"],
    "properties": {
        "schema_version": {"type": "integer", "enum": [1]},
        "active_task_id": {"type": ["string", "null"], "pattern": r"^(T-\d{3,}|)$"},
        "touched_files": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "blockers": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": "string"},
    },
}
```

- `schema_version` 用 `enum: [1]` 锁死：读到版本 2 的文件会直接被拒——这就是讲义"refuses to load a file from a version it cannot migrate"的最简实现（但没有迁移逻辑，见测验 Q10）。
- `active_task_id` 的类型是 `["string", "null"]`，正则 `^(T-\d{3,}|)$` 又允许空串——于是"无任务"有 `None` 和 `""` 两种表示（测验 Q8）。
- 数组字段的 `type: "array"` 自动禁止了 `null`（讲义："Forbidden values (e.g. `null` for arrays)"）。
- `assumptions`、`blockers` 不在 `required` 中：可以缺省，但如果出现就必须是字符串数组。
- `BOARD_SCHEMA` 的 `owner` 枚举 `builder/reviewer/human`、`status` 枚举 `todo/in_progress/done/blocked`，与第 32 节的约定一致，但现在由机器强制。
- 没有表达的约束：任务 id 唯一（JSON Schema 本身也难以表达"数组中对象某字段唯一"）、"活动任务必须在任务板上"（跨文件约束）。

### 3.2 类型判断 `_check_type`

```python
def _check_type(value: Any, types: str | list[str]) -> bool:
    type_list = [types] if isinstance(types, str) else types
    for t in type_list:
        if t == "object" and isinstance(value, dict):
            return True
        ...
        if t == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if t == "null" and value is None:
            return True
    return False
```

- 先把单个类型名统一成列表，支持 `"type": ["string", "null"]` 这种联合类型。
- **`not isinstance(value, bool)` 很关键**：Python 中 `bool` 是 `int` 的子类，`isinstance(True, int)` 为 `True`。不排除的话，`"schema_version": true` 会被当成整数 1，再通过 `enum: [1]`（因为 `True == 1`）。
- 只支持 object / array / string / integer / null 五种；schema 里若写 `"boolean"` 或 `"number"`，这个函数会永远返回 `False`——是一个"静默的子集"。
- 与规范的差异：JSON Schema 把 `1.0` 视为 integer，这里因为 `isinstance(1.0, int)` 为假而拒绝（已用 `jsonschema` 4.26 对照实测）。

### 3.3 递归验证器 `validate`

```python
def validate(value, schema, path="$"):
    if "type" in schema and not _check_type(value, schema["type"]):
        raise SchemaError(f"{path}: expected {schema['type']}, got {type(value).__name__}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path}: {value!r} not in {schema['enum']}")
    if "pattern" in schema and isinstance(value, str) and not re.match(schema["pattern"], value):
        raise SchemaError(...)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise SchemaError(f"{path}: missing required field {key!r}")
        properties = schema.get("properties", {})
        unexpected = sorted(set(value.keys()) - set(properties.keys()))
        if unexpected:
            raise SchemaError(f"{path}: unexpected fields {unexpected}")
        for key, sub in properties.items():
            if key in value:
                validate(value[key], sub, f"{path}.{key}")
    if isinstance(value, list) and "items" in schema:
        for idx, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{idx}]")
```

- **JSON 路径**：`path` 从 `$` 开始，进入对象加 `.key`，进入数组加 `[idx]`，错误信息形如 `$[0].status: 'Done' not in [...]`，能直接定位问题。
- **递归**：对象的每个属性、数组的每个元素都用对应的子 schema 再调用一次 `validate`。
- **第一个错误就抛出**：一次只报一个问题；标准库 `jsonschema` 可以用 `iter_errors` 一次列出全部。
- `pattern` 只对字符串生效（`None` 不检查）；用的是 `re.match`，只锚定开头，`$` 会匹配末尾换行符之前的位置，所以 `"T-001\n"` 也能通过（实测）。要严格请用 `re.fullmatch`。
- ⚠️ **隐式禁止额外字段**：`unexpected` 检查对所有对象生效，相当于处处 `additionalProperties: false`。标准 JSON Schema 默认允许额外字段，所以导出的 `schemas/*.json` 交给 `jsonschema` 验证时，带 `last_run` 的状态会被接受，而本验证器拒绝（实测，测验 Q5）。建议在 schema 中显式写出 `"additionalProperties": false`。

我们用 `jsonschema` 4.26 做了对照实测，结论汇总：

| 输入 | 本节 `validate` | `jsonschema` |
|------|----------------|-------------|
| 合法状态 | 通过 | 通过 |
| 多一个字段 `last_run` | **拒绝** | 通过 |
| `schema_version: 1.0` | **拒绝** | 通过 |
| `schema_version: True` | 拒绝 | 拒绝 |
| `schema_version: 2` | 拒绝 | 拒绝 |
| `touched_files: null` | 拒绝 | 拒绝 |
| 缺 `next_action` | 拒绝 | 拒绝 |
| 缺 `blockers` | 通过 | 通过 |
| `active_task_id: "T-001\n"` | 通过 | 通过 |
| 任务板重复 id | 通过 | 通过 |

### 3.4 原子写入 `atomic_write`

```python
def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
```

| 步骤 | 作用 |
|------|------|
| `mkstemp(dir=path.parent)` | 在**同一目录**（同一文件系统）创建唯一名字的临时文件，返回文件描述符和路径；`prefix` 让临时文件名形如 `agent_state.json.abc123`，便于识别和清理 |
| `os.fdopen(fd, "w")` | 把底层文件描述符包装成 Python 文件对象；`with` 结束时自动关闭 |
| `flush()` | 把 Python 用户态缓冲区交给内核 |
| `os.fsync()` | 让内核把数据真正写到磁盘 |
| `os.replace(tmp, path)` | 原子地用新文件替换旧文件（POSIX 与 Windows 都支持覆盖） |
| `except: unlink; raise` | 失败时删除临时文件，并**重新抛出**异常——不吞错误 |

实测：传入 `None` 作为内容会在 `fh.write` 抛 `TypeError`，原文件保持不变，目录里没有残留临时文件。

需要知道的细节：

- ⚠️ **权限陷阱**：`mkstemp` 以 `0600` 创建文件，替换后 `agent_state.json` 和 `task_board.json` 的权限都是 `-rw-------`，而用 `write_text` 写的 schema 文件是 `-rw-r--r--`（实测 `ls -l`）。其他用户或以不同身份运行的 CI 可能读不到。
- 没有对目录做 `fsync`：断电时"重命名"本身可能尚未持久化。
- `kill -9` 发生在 `replace` 之前会留下临时文件（`except` 不会执行），需要启动时清理。
- 讲义对比的 Hive bug：`write_text()` + 静默吞异常 → 半截文件 + 无信号。本函数两点都避免了。

### 3.5 `StateManager`

```python
class StateManager:
    def __init__(self, state_path, schema):
        self.state_path = state_path
        self.schema = schema

    def load(self):
        raw = json.loads(self.state_path.read_text())
        validate(raw, self.schema)
        return raw

    def commit(self, state):
        validate(state, self.schema)
        atomic_write(self.state_path, json.dumps(state, indent=2) + "\n")
```

- **读也验证**：手工改坏的文件、旧版本文件在 `load` 时就被拒绝，不会被当成正确状态继续使用。
- **先验证后写**：`commit` 中验证失败直接抛 `SchemaError`，`atomic_write` 根本不会被调用，磁盘不受影响。
- 同一个类既管状态又管任务板（`schema` 作为参数传入），体现"管理器与具体 schema 解耦"。
- ⚠️ 讲义与 mission 列出的 `StateManager.update` **不存在**（测验 Q9 给出实现）。
- ⚠️ 没有任何并发控制：两个进程"读-改-写"会丢失更新（测验 Q11 实测：A 的 `app.py` 被 B 覆盖丢失）。

### 3.6 `main`：一次修改 + 一次被拒的坏写入

```python
    mgr.commit(initial_state)
    board_mgr.commit(initial_board)

    state = mgr.load()
    board = board_mgr.load()
    state["active_task_id"] = board[0]["id"]
    state["next_action"] = "read existing /signup handler"
    mgr.commit(state)
    ...
    bad = dict(state)
    bad["active_task_id"] = "T-bogus"
    try:
        mgr.commit(bad)
    except SchemaError as exc:
        print("rejected bad write:", exc)
```

- 每次运行都先 `commit(initial_state)`，所以**不会接续上一次运行**——这与第 32 节"重复运行逐步推进"不同。讲义说"mutates them across two turns"，实际只对状态做了一次修改，任务板没有被修改过。
- 修改后 T-001 成为活动任务，但任务板上 T-001 仍是 `todo`——两份文件各自合法、合起来矛盾（测验 Q7、Q9）。
- `dict(state)` 是**浅拷贝**：顶层键是新的，但 `touched_files` 等列表仍与 `state` 共享。这里只替换了一个字符串值，所以没问题；若写 `bad["touched_files"].append(...)` 就会连 `state` 一起改掉。
- 坏写入被拒后，磁盘上仍是 `T-001`（已检查文件内容）——这就是 mission 的验收标准"A bad write ... is refused, not persisted"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 自写迷你验证器 | 无第三方依赖，便于理解验证原理 | 语义与标准不完全一致（额外字段、`1.0`、只报第一个错误）；生产用 `jsonschema` 库，并在 schema 中显式写 `additionalProperties` |
| schema 写成 Python dict 再导出 JSON | 代码和 schema 一处维护 | 真正的事实来源应是 `schemas/*.json` 文件，代码读取它；否则改 JSON 文件不会生效 |
| `schema_version` 用 enum 锁定 | 未知版本直接拒绝，最简单的 fail loud | 没有迁移路径；需要 `migrate_state.py` |
| 原子写入 | 崩溃不产生半截文件 | 权限变成 0600；未 fsync 目录；不解决并发 |
| 读、写都验证 | 坏数据进不来也出不去 | 每次读写都有验证开销（对小文件可忽略） |
| 每次运行重置初始状态 | 演示结果可复现 | 无法演示跨运行接续；真实管理器应"不存在才初始化" |
| 状态与任务板分开管理 | 职责清晰 | 跨文件不变量无人检查；需要一致性检查或合并为一个事务 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `typing.Any` | `dict[str, Any]` | 表示"任意类型"，用于结构不固定的 JSON |
| 联合类型注解 | `types: str \| list[str]` | 参数可以是字符串或字符串列表 |
| 原始字符串正则 | `r"^(T-\d{3,}\|)$"` | `\d{3,}` 至少 3 位数字；`(A\|)` 表示 A 或空串 |
| 自定义异常 | `class SchemaError(Exception): pass` | 继承 `Exception`，调用方可以只捕获这一类错误 |
| `raise` / `try ... except ... raise` | `atomic_write` | 捕获后清理现场，再用裸 `raise` 原样重新抛出 |
| `isinstance` 与 bool 陷阱 | `isinstance(value, int) and not isinstance(value, bool)` | `bool` 是 `int` 的子类，需要显式排除 |
| 递归函数 + 默认参数 | `def validate(value, schema, path="$")` | 每层递归传入新的路径字符串 |
| 集合差 | `set(value.keys()) - set(properties.keys())` | 找出 schema 中没声明的键 |
| `sorted()` | `sorted(...)` | 让错误信息顺序稳定，便于测试 |
| `enumerate` | `for idx, item in enumerate(value)` | 同时拿到下标和元素 |
| `dict.get(key, default)` | `schema.get("required", [])` | 键不存在时返回默认值 |
| `!r` 与 `__name__` | `f"{value!r}"`、`type(value).__name__` | 显示带引号的值；取类型名字符串 |
| `re.match` | `re.match(schema["pattern"], value)` | 只从开头匹配；完整匹配用 `re.fullmatch` |
| `tempfile.mkstemp` | `fd, tmp_name = tempfile.mkstemp(prefix=..., dir=...)` | 安全地创建唯一临时文件，返回 (文件描述符, 路径) |
| `os.fdopen` + `with` | `with os.fdopen(fd, "w") as fh:` | 把文件描述符变成文件对象，退出时自动关闭 |
| `os.fsync` / `os.replace` | 见 3.4 | 刷盘 / 原子替换 |
| `Path.unlink(missing_ok=True)` | 清理临时文件 | 文件不存在也不报错（3.8+） |
| `mkdir(parents=True, exist_ok=True)` | `path.parent.mkdir(...)` | 递归创建、已存在不报错 |
| 浅拷贝 | `bad = dict(state)` | 只复制顶层；嵌套列表仍共享 |
| `json.dumps(..., indent=2)` | 打印与写盘 | 带缩进的 JSON；`None` 写为 `null` |

---

## 6. 运行结果解读

实际运行（Python 3.13，退出码 0，在临时目录副本中运行）：

```text
state: {
  "schema_version": 1,
  "active_task_id": "T-001",
  "touched_files": [],
  "assumptions": [],
  "blockers": [],
  "next_action": "read existing /signup handler"
}
board: [
  {
    "id": "T-001",
    "goal": "validate /signup payloads",
    "owner": "builder",
    "acceptance": [
      "pytest -x test_app.py::test_signup_rejects_short_password"
    ],
    "status": "todo"
  }
]
rejected bad write: $.active_task_id: 'T-bogus' does not match /^(T-\d{3,}|)$/
```

逐项解读：

- **state**：初始状态经过一次修改后重新从磁盘 `load` 出来并通过验证——证明了"写入 → 读回 → 验证"的往返。
- **board**：`status` 仍是 `todo`，与 state 中的活动任务矛盾（schema 发现不了）。
- **rejected bad write**：错误信息带 JSON 路径 `$.active_task_id`，并给出值与正则；随后检查磁盘文件，`active_task_id` 仍是 `T-001`，坏写入没有落盘。
- **目录内容**（`ls -l` 实测）：`agent_state.json`、`task_board.json` 权限为 `-rw-------`（来自 `mkstemp`），`schemas/` 下两个文件为 `-rw-r--r--`（来自 `write_text`）。
- **额外实验**：两个 agent 交错"读-改-写"同一状态，最终只剩 `blockers: ["db down"]`，另一方追加的 `touched_files: ["app.py"]` 丢失——原子写入不防丢失更新。

---

## 7. 动手改一改

1. **补上 `update`**：实现 `update(**changes)`（读 → 合并 → 验证 → 原子写），并写一个跨文件 `check_consistency(state, board)`；让 `main` 同时把 T-001 改为 `in_progress`（参考测验 Q9）。
2. **讲义练习 3：迁移**：写 `migrate_1_to_2`（`blockers` → `risks`），用 `MIGRATIONS` 字典链式升级，未知版本抛错；`load` 中先迁移再验证（参考测验 Q10）。
3. **对齐标准语义**：在两个 schema 中显式加入 `"additionalProperties": false`，再用 `jsonschema.validate` 跑同一批样例，确认两种验证器结论一致；把 `re.match` 换成 `re.fullmatch`。
4. **讲义练习 1：人工编辑保护**：加 `last_human_touch` 时间戳，`commit` 时若距离上次人工编辑不足 5 秒则拒绝写入。
5. **讲义练习 5：并发**：用 `multiprocessing` 启动两个进程循环 `update` 同一文件，统计丢失的更新数；再加入 `revision` 字段实现乐观并发（不匹配就重读重试），对比结果。
6. **进阶**：实现事件溯源——每次 `commit` 先把变更追加到 `state.events.jsonl`，并能从任一快照 + 事件重放出最新状态；或按讲义练习 4 把后端换成 SQLite，保持 `StateManager` 接口不变。

---

## 8. 常见坑

- **以为原子写入能解决并发**：它只保证文件完整，不保证不丢更新。
- **在 `/tmp` 里写临时文件再改名**：跨文件系统时 `os.replace` 失败（`EXDEV`），或被迫退化为非原子复制。
- **吞掉写入异常**：Hive bug 的根源；失败必须响亮。
- **忘了 `mkstemp` 的 0600 权限**：替换后状态文件对其他用户不可读。
- **`bool` 被当成整数**：类型检查要排除 `bool`。
- **`$` 不是严格的字符串结尾**：Python 中用 `\Z` 或 `re.fullmatch`。
- **以为 schema 能管住一切**：唯一性、跨文件引用、"状态与任务板一致"这类约束需要额外代码检查。
- **自写验证器与标准库语义不一致**：导出的 schema 被其他工具使用时会得出不同结论，应把隐含规则显式写进 schema。
- **浅拷贝后修改嵌套列表**：`dict(state)` 之后改 `bad["touched_files"]` 会连原状态一起改。
