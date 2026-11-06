# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 21 节 带 Schema 校验的工具注册表 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（演示）；在 `code/` 下 `python -m pytest -q` 或 `python -m unittest discover -s tests`（测试） ｜ **依赖**：仅标准库（`json`、`re`、`dataclasses`、`typing`、`unittest`）

---

## 1. 这份代码在考察什么

第 20 节定下了循环契约，循环里的工具步骤只有 `tool_name` 和 `tool_args`。本节回答"这个工具存在吗、参数形状对吗、该调用哪个函数"：

1. **工具注册表**：名字 → `ToolRecord`（schema、handler、是否幂等、超时），名字有格式要求，重名必须显式 override，保持注册顺序。
2. **JSON Schema 2020-12 子集校验器**：八个关键字（`type`、`properties`、`required`、`enum`、`minLength`、`maxLength`、`pattern`、`items`），纯函数、递归、一次收集所有错误。
3. **schema 形状检查**：注册时就拒绝子集之外的关键字与不合法的关键字取值。
4. **JSON Pointer 错误路径**（RFC 6901）：`/fields/1` 这样的路径让模型能精确定位并在下一轮改正。
5. **严格类型**：不做强转，`bool` 不算 `integer`/`number`。

> 一句话：**在写任何工具之前，先建立"什么调用是合法的"这份契约，并让违约以机器可读的形式被报告出来。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PRIMITIVE_TYPE_MAP` | 常量字典 | JSON 类型名 → Python 类型元组 | 类型映射 |
| `ALLOWED_KEYWORDS` | 常量集合 | 允许出现在 schema 中的关键字白名单 | 子集边界 |
| `ValidationError` | dataclass | `path + keyword + message`，`to_dict()` | 结构化错误 |
| `Ok` | 空 dataclass | 校验通过的标记 | 结果类型 |
| `ToolRecord` | dataclass | 讲义中的六字段工具记录 | 工具记录 |
| `ToolRegistry` | 类 | `register` / `get` / `names` / `validate` | 注册表 |
| `validate_schema_shape` | 函数 | 递归检查 schema 本身是否合法 | 注册期检查 |
| `_path` | 函数 | 拼接并转义 JSON Pointer 段 | RFC 6901 |
| `_type_matches` | 函数 | 带 `bool` 特判的类型判断 | 严格类型 |
| `_walk` | 函数 | 校验入口：type → enum → 按类型分派 | 递归遍历 |
| `_check_string` / `_check_object` / `_check_array` | 函数 | 各类型的关键字检查，递归调用 `_walk` | 关键字语义 |
| `_demo` | 函数 | 注册 `db.get_user`，校验 4 组参数并打印 JSON | 演示 |

数据流：`register(name, schema, handler)` → 名字正则 → 重名检查 → `validate_schema_shape` → 存入 `_records` / `_order`；`validate(name, args)` → `get` → `_walk(schema, args, "", errors)`（递归下降，途中 `_path` 拼路径）→ 有错误返回列表，否则返回 `Ok()`。

---

## 3. 逐段精讲

### 3.1 类型映射与关键字白名单

```python
PRIMITIVE_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
    "null": (type(None),),
}

ALLOWED_KEYWORDS = {
    "type", "properties", "required", "enum",
    "minLength", "maxLength", "pattern", "items", "description",
}
```

- 七种 JSON 类型对应 Python 的 `json.loads` 产物：对象 → `dict`，数组 → `list`，`null` → `None`。`type(None)` 就是 `NoneType`。
- `number` 接受 `int` 和 `float`；`integer` 只接受 `int`，因此 `1.0`（Python `float`）会被拒绝——规范中 `1.0` 算 integer，这是一处有意或无意的偏差。
- 白名单比讲义的八个关键字多了 `description`（给人和模型看的注释）。真实工具 schema 中常见的 `title`、`default`、`examples`、`additionalProperties` 都会让注册失败（实测），从外部导入 schema 时需要先清洗。

### 3.2 结果类型：ValidationError 与 Ok

```python
@dataclass
class ValidationError:
    path: str
    keyword: str
    message: str

    def to_dict(self) -> dict:
        return {"path": self.path, "keyword": self.keyword, "message": self.message}


@dataclass
class Ok:
    pass
```

- `validate` 的返回类型是 `Ok | list[ValidationError]`——一种简化版的 Result 类型。调用方用 `isinstance(result, Ok)` 判断；不要写 `if result:`，因为 `Ok()` 和非空列表都为真。
- 注意 `ValidationError` 只是普通数据类，**不是异常**（没有继承 `Exception`），名字容易让人误会。
- 讲义提到错误里应有 `expected_type: string` 这样的字段，代码只把期望类型写在 `message` 字符串里（`expected integer, got str`），模型需要从文本中解析。

### 3.3 ToolRecord 与注册

```python
class ToolRegistry:
    _NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")

    def register(self, name, schema, handler, description="", idempotent=False,
                 timeout_ms=30_000, override=False) -> ToolRecord:
        if not self._NAME_RE.match(name):
            raise ValueError(f"tool name {name!r} must match {self._NAME_RE.pattern}")
        if name in self._records and not override:
            raise ValueError(f"tool {name!r} already registered; pass override=True to replace")
        validate_schema_shape(schema)
        rec = ToolRecord(...)
        if name not in self._records:
            self._order.append(name)
        self._records[name] = rec
        return rec
```

- **名字规则**：每段以小写字母开头，后接小写字母、数字、下划线，段之间用 `.` 分隔。实测：`a`、`a.b`、`a_1.b2` 合法；`A`、`a-b`、`a..b`、`_a`、`a.` 非法。
- **坑**：`re.match` + `$` 会接受末尾带 `\n` 的名字——`$` 在 Python 中可以匹配"末尾换行符之前"。实测 `"db.get_user\n"` 注册成功。应改用 `fullmatch` 或 `\Z`。
- **检查顺序**：先名字、再重名、再 schema 形状，全部通过才写入；任何一步失败都不会留下半注册状态。
- **override 语义**：`_order` 只在首次注册时追加，替换不会改变顺序，也不会重复。
- `30_000`：数字中的下划线只是分隔符，等于 30000（毫秒）。`idempotent` 与 `timeout_ms` 本节不使用，留给第 23 节分派器做重试与超时决策。
- schema 按**引用**保存，没有深拷贝：注册后外部修改原字典会绕过形状检查（实测把 `type` 改成 `"tuple"` 后 `validate` 抛 `KeyError`）。

```python
    def get(self, name: str) -> ToolRecord:
        if name not in self._records:
            raise KeyError(f"unknown tool {name!r}")
        return self._records[name]

    def names(self) -> list[str]:
        return list(self._order)

    def validate(self, name: str, args: Any) -> Ok | list[ValidationError]:
        rec = self.get(name)
        errors: list[ValidationError] = []
        _walk(rec.schema, args, "", errors)
        if errors:
            return errors
        return Ok()
```

- 讲义的三个读方法：`get` 未知名字抛 `KeyError`（而不是返回 `None`，强迫调用方处理）；`names` 返回副本；`validate` 对未知工具同样抛 `KeyError`——注意它与"参数错误"是两种不同的失败，分派器需要分别处理。
- `errors` 是在递归中被**原地追加**的累加器，所有层级共享同一个列表。

### 3.4 `validate_schema_shape`：在注册时检查 schema

```python
def validate_schema_shape(schema: dict) -> None:
    if not isinstance(schema, dict):
        raise ValueError("schema must be a dict")
    unknown = set(schema.keys()) - ALLOWED_KEYWORDS
    if unknown:
        raise ValueError(f"unsupported schema keywords: {sorted(unknown)}")
    t = schema.get("type")
    if t is not None and t not in PRIMITIVE_TYPE_MAP:
        raise ValueError(f"unsupported type: {t!r}")
    ...
    props = schema.get("properties")
    if props is not None:
        ...
        for pname, psub in props.items():
            ...
            validate_schema_shape(psub)
    items = schema.get("items")
    if items is not None:
        validate_schema_shape(items)
```

- **集合差**：`set(schema.keys()) - ALLOWED_KEYWORDS` 一步找出所有不认识的关键字，`sorted` 让错误消息稳定。
- 对 `minLength`/`maxLength` 的检查用了 `isinstance(min_len, bool) or not isinstance(min_len, int)`——同样是为了排除 `True`（否则 `minLength: True` 会被当成 1）。还检查了 `minLength <= maxLength`。
- 递归检查 `properties` 的每个子 schema 和 `items`，保证整棵树都在子集内。
- 漏检之处：
  - `type` 为列表（如 `["string", "null"]`）时，`t not in PRIMITIVE_TYPE_MAP` 需要哈希，抛的是 `TypeError: unhashable type: 'list'` 而不是清晰的 `ValueError`（实测）。
  - `pattern` 只检查是不是字符串，不检查能否编译；非法正则要到校验参数时才暴露。
  - `required` 中的名字不必出现在 `properties` 里，`enum` 的元素也不检查是否为原始类型。

### 3.5 JSON Pointer 拼接

```python
def _path(prefix: str, segment: str | int) -> str:
    seg = str(segment).replace("~", "~0").replace("/", "~1")
    return f"{prefix}/{seg}"
```

- RFC 6901 的两条转义：`~` → `~0`，`/` → `~1`。**顺序很重要**：先转 `~`，否则 `/` 转出的 `~1` 会再被转成 `~01`。
- 数组下标用 `str(idx)` 变成 `"1"`，所以 `[1, "x", 3]` 的第二个元素路径是 `/1`。
- 根路径：`_walk` 从 `""` 开始，报错时写 `path or "/"`，即根位置显示为 `"/"`。按 RFC 6901，`""` 才是根，`"/"` 指向键为空字符串的成员——实测 `{"": 1}` 的错误路径也是 `"/"`，二者无法区分。

### 3.6 `_type_matches`：bool 的特判

```python
def _type_matches(value: Any, expected: str) -> bool:
    types = PRIMITIVE_TYPE_MAP[expected]
    if expected == "boolean":
        return isinstance(value, bool)
    if expected in ("integer", "number"):
        if isinstance(value, bool):
            return False
        return isinstance(value, types)
    return isinstance(value, types)
```

- Python 中 `bool` 是 `int` 的子类：`isinstance(True, int)` 为 `True`。JSON 里 `true` 和 `1` 是不同类型，所以 integer/number 必须先排除 `bool`。
- `boolean` 分支其实与最后一行等价（`types` 就是 `(bool,)`），单独写出来是为了强调意图。
- 没有排除 `float('nan')`、`inf`：它们不是合法 JSON，但 Python 的 `json.loads` 默认接受 `NaN`，实测 `{"type": "number"}` 对 `nan` 返回 `Ok`。

### 3.7 `_walk`：校验主循环

```python
def _walk(schema: dict, value: Any, path: str, errs: list[ValidationError]) -> None:
    t = schema.get("type")
    if t is not None and not _type_matches(value, t):
        errs.append(ValidationError(path=path or "/", keyword="type",
                                    message=f"expected {t}, got {type(value).__name__}"))
        return
    if "enum" in schema:
        if value not in schema["enum"]:
            errs.append(ValidationError(path=path or "/", keyword="enum",
                                        message=f"value {value!r} not in {schema['enum']!r}"))
            return
    if t == "string":
        _check_string(schema, value, path, errs)
    elif t == "object":
        _check_object(schema, value, path, errs)
    elif t == "array":
        _check_array(schema, value, path, errs)
```

- **短路规则**：类型不对就 `return`——类型都错了，再检查长度、属性只会产生噪声；`enum` 不通过也 `return`。同一字符串上的 `minLength`、`maxLength`、`pattern` 则互不短路，全部报告。
- **按 schema 的 `type` 分派**：没有写 `type` 的 schema 不会进入任何 `_check_*`，于是 `{"minLength": 5}`、`{"properties": {...}}` 这类"无类型 schema"中的关键字被静默忽略（实测均返回 `Ok`）。规范的做法是按**实例的实际类型**决定应用哪些关键字。
- **enum 的相等陷阱**：`value not in schema["enum"]` 用 `==` 比较，`True == 1`、`False == 0`、`1 == 1.0`。有 `type: integer` 时 bool 会先被类型检查拦下；没有 `type` 时 `True` 能通过 `{"enum": [1, 2]}`（实测）。

### 3.8 各类型的关键字检查

```python
def _check_string(schema, value, path, errs):
    if "minLength" in schema and len(value) < schema["minLength"]: ...
    if "maxLength" in schema and len(value) > schema["maxLength"]: ...
    if "pattern" in schema:
        try:
            if not re.search(schema["pattern"], value): ...
        except re.error as exc:
            errs.append(ValidationError(path=path or "/", keyword="pattern",
                                        message=f"invalid regex: {exc}"))
```

- `len(value)` 计的是 Unicode 码点数，与 JSON Schema 规范一致（规范按字符计，而不是 UTF-8 字节或 UTF-16 单元）。
- `re.search` 不自动锚定：`pattern: "abc"` 会匹配 `"xxabcxx"`，这与规范一致，需要锚定时 schema 里自己写 `^...$`。
- Python 正则与讲义所说的 ECMA-262 有差异：例如 `\d` 在 Python 中匹配所有 Unicode 数字（实测接受 `"١٢٣"`）。
- `try/except re.error`：非法正则不会让校验器崩溃，但会被报告成"参数错误"，归因不对；更好的位置是在注册时编译。

```python
def _check_object(schema, value, path, errs):
    required = schema.get("required", [])
    for req_name in required:
        if req_name not in value:
            errs.append(ValidationError(path=_path(path, req_name), keyword="required",
                                        message=f"missing required property {req_name!r}"))
    props = schema.get("properties", {})
    for prop_name, prop_value in value.items():
        if prop_name in props:
            _walk(props[prop_name], prop_value, _path(path, prop_name), errs)


def _check_array(schema, value, path, errs):
    items_schema = schema.get("items")
    if items_schema is None:
        return
    for idx, item in enumerate(value):
        _walk(items_schema, item, _path(path, idx), errs)
```

- **required 的路径**指向"缺失属性本该在的位置"（如 `/id`），而不是父对象。这对模型很友好（直接告诉它缺哪个键），但与 JSON Schema 标准输出格式中"instance location 为父对象"的约定不同。
- 错误顺序：先所有 required 错误，再按**输入字典的键顺序**检查属性。
- 未在 `properties` 中声明的键被直接忽略——没有 `additionalProperties: false`，模型拼错的参数名（如 `idd`）不会被发现。讲义"Going further"把它列为第一个扩展（测验 Q10 给出了实现）。
- `enumerate(value)` 同时拿到下标与元素，下标成为路径的一段。

### 3.9 `_demo`

```python
    registry.register(
        name="db.get_user",
        description="Fetch a user record by id.",
        schema={
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "integer"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["id", "name", "email"]},
                },
            },
        },
        handler=get_user,
        idempotent=True,
    )
```

- 一个典型的工具 schema：对象、一个必需整数、一个可选的"枚举字符串数组"。四组测试参数分别覆盖：全部合法、类型错误、缺少必需字段、数组元素不在枚举中。
- 注意 handler `get_user(id: int)` 的参数名 `id` 遮蔽了内置函数 `id`，在演示里无害，但在真实代码中应避免。
- 注册表从未调用 handler——这正是"校验与执行分离"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只实现八个关键字 | 覆盖讲义所说"九成工具调用"的需要，代码一屏读完 | 不支持 `$ref`、组合关键字、`additionalProperties`、可空类型；生产常用 `jsonschema` 等成熟库 |
| 注册时白名单检查 schema | 不支持的关键字不会被静默忽略 | 外部 schema 中的 `title`/`default` 也被拒，需要预处理 |
| 重名默认拒绝、override 显式 | 防止工具目录悄悄漂移 | 覆盖应留审计日志、带版本 |
| 严格类型、不强转 | 错误早暴露，避免 handler 收到意外类型 | `1.0` 不算 integer 与规范不符，需要在文档中说明 |
| 收集全部错误、类型错误时剪枝 | 模型一轮改完，且不产生级联噪声 | 错误很多时要截断 |
| JSON Pointer 路径 | 机器可读、可精确定位 | 根路径用 `"/"` 与 RFC 6901 不一致 |
| 纯函数校验器 | 可在回放日志上重跑、易测试 | 正则每次重新编译（`re` 有内部缓存，影响不大） |
| 按 schema 的 `type` 分派 | 实现简单 | 无 `type` 的 schema 关键字被忽略；应按实例类型分派 |
| schema 按引用保存 | 省一次拷贝 | 注册后被外部修改会绕过检查；应 `copy.deepcopy` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 带注解的模块常量 | `PRIMITIVE_TYPE_MAP: dict[str, tuple[type, ...]] = {...}` | `tuple[type, ...]` 表示"任意长度、元素都是类型对象的元组" |
| `type(None)` | `"null": (type(None),)` | 取得 `NoneType`，用于 `isinstance` |
| 集合字面量与集合差 | `ALLOWED_KEYWORDS = {...}`、`set(schema.keys()) - ALLOWED_KEYWORDS` | 集合运算一步找出多余元素 |
| 空 dataclass | `@dataclass class Ok: pass` | 作为"成功"的标记类型 |
| 类属性中的预编译正则 | `_NAME_RE = re.compile(r"^...$")` | 所有实例共享；`r"..."` 原始字符串避免反斜杠转义 |
| `re.match` / `re.search` / `fullmatch` | `self._NAME_RE.match(name)`、`re.search(schema["pattern"], value)` | `match` 从开头匹配，`search` 任意位置，`fullmatch` 必须整串匹配 |
| `{x!r}` | `f"tool name {name!r} must match ..."` | 用 `repr()` 显示，字符串带引号、换行显示为 `\n` |
| 数字分隔下划线 | `timeout_ms: int = 30_000` | 提高可读性，值为 30000 |
| 关键字参数与默认值 | `register(self, name, schema, handler, description="", ..., override=False)` | 调用时用 `override=True` 明确意图 |
| 联合返回类型 | `-> Ok | list[ValidationError]` | 调用方用 `isinstance` 区分 |
| `isinstance` 多重判断 | `isinstance(min_len, bool) or not isinstance(min_len, int)` | 排除 `bool` 这个 `int` 子类 |
| 生成器 + `all` | `all(isinstance(x, str) for x in req)` | 检查列表每个元素 |
| 链式 `str.replace` | `str(segment).replace("~", "~0").replace("/", "~1")` | 顺序决定结果 |
| `try / except re.error as exc` | `_check_string` 中 | 捕获正则编译错误 |
| `enumerate` | `for idx, item in enumerate(value)` | 同时得到下标与元素 |
| `dict.get(key, default)` | `schema.get("required", [])` | 键不存在时返回默认值 |
| 可变累加器参数 | `_walk(..., errs)` 中 `errs.append(...)` | 递归各层共享同一个列表，无需返回值 |
| `type(value).__name__` | `f"got {type(value).__name__}"` | 取类型名（`str`、`int`、`bool`） |
| 嵌套函数 | `_demo` 里的 `def get_user(id: int)` | 局部定义的 handler |
| `json.dumps(..., indent=2)` | `_demo` 末尾 | 美化输出 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13），输出（折叠了数组换行）：

```text
{
  "tools": ["db.get_user"],
  "cases": [
    {"args": {"id": 42, "fields": ["id", "name"]}, "ok": true},
    {"args": {"id": "forty-two"}, "ok": false,
     "errors": [{"path": "/id", "keyword": "type", "message": "expected integer, got str"}]},
    {"args": {"fields": ["id"]}, "ok": false,
     "errors": [{"path": "/id", "keyword": "required", "message": "missing required property 'id'"}]},
    {"args": {"id": 1, "fields": ["id", "phone"]}, "ok": false,
     "errors": [{"path": "/fields/1", "keyword": "enum", "message": "value 'phone' not in ['id', 'name', 'email']"}]}
  ]
}
```

逐项解读：

- **case 1**：`id` 是整数，`fields` 每个元素都是字符串且在枚举内 → `ok: true`。
- **case 2**：`"forty-two"` 是 `str`，不做强转 → 类型错误，路径 `/id`。
- **case 3**：缺少 `id` → `required` 错误，路径指向缺失的 `/id`；`fields` 合法，没有额外错误。
- **case 4**：数组下标 1 的 `"phone"` 不在枚举中 → 路径 `/fields/1`，关键字 `enum`。模型可以直接看出"第二个字段名不被支持"。
- 讲义的承诺"precise, json-pointer-shaped error paths"在四个用例里都得到体现。

额外边界实测（临时脚本，不修改源码）：

| 输入 | 结果 | 说明 |
|------|------|------|
| `{"enum": [1, 2]}` ← `True` | `Ok` | `True == 1` |
| `{"type": "integer"}` ← `1.0` | `type` 错误 | 规范中 1.0 是 integer |
| `{"type": "number"}` ← `nan` | `Ok` | NaN 不是合法 JSON |
| `{"minLength": 5}` ← `"ab"` | `Ok` | 无 `type` 时关键字被忽略 |
| `{"type": "object"}` ← `[]` | 路径 `/` | 根位置写作 `/` |
| 属性 `""` ← `1` | 路径 `/` | 与根位置无法区分 |
| 属性 `"a/b"`、`"m~n"` | `/a~1b`、`/m~0n` | 转义正确 |
| `{"pattern": "("}` ← `"x"` | `pattern` 错误 "invalid regex" | schema 的错被报成参数的错 |
| `{"pattern": "^\\d+$"}` ← `"١٢٣"` | `Ok` | Python `\d` 是 Unicode |
| 数组 `[{"id":1},{"id":"2"},{}]` | `/1/id` type、`/2/id` required | 两个错误都被收集 |
| `register("db.get_user\n", ...)` | 成功 | `$` 匹配末尾换行前 |
| `validate_schema_shape({"type": ["string","null"]})` | `TypeError` | 列表不可哈希 |

---

## 7. 动手改一改

1. **修名字正则**：把 `match` 换成 `fullmatch`，并补一条测试断言 `"a\n"` 被拒绝。
2. **注册期编译正则**：在 `validate_schema_shape` 中 `re.compile(pattern)`，失败时 `ValueError`；校验时使用缓存的编译结果。
3. **实现 `additionalProperties: false`**：白名单、形状检查、`_check_object` 三处修改（测验 Q10 有完整代码，实测原 19 个测试仍通过）。
4. **按实例类型分派**：让 `minLength` 等关键字在实例是字符串时就生效，不依赖 `type`；`properties`/`required` 在实例是对象时生效。补测试覆盖"无 type schema"。
5. **修正 enum 与 integer 语义**：enum 比较时区分 `bool` 与数字；`integer` 接受 `float` 且 `is_integer()` 的值（或保持严格并在错误消息里说明）。
6. **支持本地 `$ref`**：允许顶层 `$defs` 和 `{"$ref": "#/$defs/User"}`，注册时解析并检测循环引用——这是讲义"Going further"的第二个扩展。

---

## 8. 常见坑

- **`isinstance(True, int)` 为真**：任何"数字"判断都要先排除 `bool`。
- **`if result:` 判断校验结果**：`Ok()` 与错误列表都为真，必须用 `isinstance(result, Ok)`。
- **JSON Pointer 转义顺序**：先 `~` 后 `/`。
- **`re.match(...$)` 不等于整串匹配**：末尾换行会漏过；用 `fullmatch`。
- **schema 漏写 `type`**：本校验器会静默放行该层的所有约束。
- **把 schema 错误当参数错误**：非法正则在运行时才暴露，模型会反复"修正"本来正确的参数。
- **以为校验通过就安全**：讲义明确说注册表不是安全边界，路径穿越、资源滥用要靠后续的分派器与沙箱。
- **注册后修改 schema 字典**：注册表保存的是引用，修改会直接生效且绕过形状检查。

---

## 9. 测试在验证什么

`tests/test_registry.py` 共 19 个 `unittest` 测试，分 3 组。它通过 `sys.path.insert(0, os.path.dirname(HERE))` 把 `code/` 加入导入路径，可在 `code/` 下用 `python -m pytest -q`、`python -m unittest discover -s tests` 或 `python tests/test_registry.py` 运行。

| 测试 | 验证的性质 |
|------|-----------|
| **TestRegistration** | |
| `test_register_returns_record` | `register` 返回 `ToolRecord`，名字正确，`names()` 为 `["fs.read"]` |
| `test_duplicate_rejected_without_override` | 同名再次注册（未 override）抛 `ValueError` |
| `test_override_replaces` | `override=True` 替换记录（schema 变为 integer），`names()` 不重复 |
| `test_invalid_name_rejected` | `Bad-Name`（大写、连字符）、`1starts-with-digit`（数字开头）被拒 |
| `test_unknown_keyword_rejected` | 含 `oneOf` 的 schema 被 `validate_schema_shape` 拒绝 |
| `test_unknown_type_rejected` | `type: "tuple"` 被拒 |
| `test_get_unknown_raises` | `get` 未知名字抛 `KeyError` |
| **TestValidatorTypes** | |
| `test_string_ok` | 字符串通过 `string` |
| `test_string_wrong_type` | `42` 不通过 `string`，关键字 `type`，路径 `/` |
| `test_integer_vs_boolean` | `True` 不通过 `integer`（bool 特判） |
| `test_number_accepts_int_and_float` | `1` 与 `1.5` 都通过 `number` |
| `test_null_type` | `None` 通过 `null`，`0` 不通过 |
| **TestValidatorKeywords** | |
| `test_min_max_length` | `"abc"` 通过 `[2, 4]`；`"a"` 报 `minLength`；`"abcde"` 报 `maxLength` |
| `test_pattern` | `^[a-z]+$` 接受 `"abc"`、拒绝 `"abc1"` |
| `test_enum` | `"a"` 通过、`"c"` 报 `enum` |
| `test_required_missing` | 空对象缺 `id`，关键字 `required`，路径 `/id` |
| `test_nested_path` | `{"user": {"email": 0}}` 的错误路径为 `/user/email` |
| `test_array_items` | `[1, "x", 3]` 的错误路径为 `/1` |
| `test_multiple_errors_collected` | 空对象缺两个必需属性时返回 2 条错误，路径集合为 `{"/a", "/b"}` |

实际运行结果（`python3 -m pytest -q`）：

```text
...................                                                      [100%]
19 passed in 0.02s
```

测试的盲区：没有覆盖名字末尾换行、`type` 为列表、非法正则、无 `type` 的 schema、`enum` 中的 bool/数字混淆、`~`/`/` 转义、注册后修改 schema 等情形——这些正是第 6 节的边界实测发现问题的地方。另外 `test_register_returns_record` 中的 handler `lambda path: open(path).read()` 只是占位，从未被调用。
