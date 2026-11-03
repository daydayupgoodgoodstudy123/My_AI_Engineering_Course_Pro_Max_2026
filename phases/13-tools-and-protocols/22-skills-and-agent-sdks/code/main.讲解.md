# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 22 节 Agent Skills：可移植契约与运行时边界 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）；测试 `python3 -m unittest discover -s code/tests -v` ｜ **依赖**：仅标准库（`json`、`re`、`tempfile`、`dataclasses`、`pathlib`、`typing`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

这份代码是讲义"Build It"部分的实现，包含两个互相独立的小工具：

1. **一个面向标准的 `SKILL.md` 校验器**：`parse_frontmatter` 把 frontmatter 与指令体分开；`validate_skill_text` 检查必填字段、命名规则、目录匹配、长度上限、可选字段形状、body 是否为空，以及"未知字段是不是被显式允许的宿主扩展"。它返回结构化报告（`SkillReport` + 一组 `ValidationIssue`），而不是一个不透明的布尔值。
2. **一个原语选择器**：`TaskShape` 描述任务的六种需求，`select_primitives` 把它们映射到 `AGENTS.md`、Agent Skill、MCP tool、hook、ordinary code、subagent，全都不需要时返回 prompt。

对应讲义的核心概念：

- 便携核心（portable core）与运行时扩展（runtime extension）是两层契约；
- frontmatter 是"可执行元数据"，必须像配置代码一样校验；
- 分类先于打包——"Decide what the artifact is before you decide how to package it"；
- 多个原语可以组合，按职责而不是按产品品牌来选。

> 一句话：**用不到 350 行标准库代码，把"一个 skill 包在进入 agent 目录之前必须满足什么"和"一个需求到底该用哪种原语"变成可测试的规则。** 同时要看清它只实现了一个 YAML 小子集，这正是面试与实战中最容易出错的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CORE_FIELDS` | 常量（集合） | 六个便携核心字段名 | Portable core |
| `NAME_PATTERN` | 编译后的正则 | 小写字母/数字 + 单连字符 | `name` 命名规则 |
| `ValidationIssue` | 冻结 dataclass | 一条问题：`code` + `message` | 结构化证据 |
| `SkillReport` | 冻结 dataclass | 校验结论 + 解析结果 + 问题列表，`to_dict()` 输出 JSON 友好结构 | 结构化报告 |
| `FrontmatterSyntaxError` | 异常类 | 无法安全解释的输入 | 解析失败 |
| `_decode_scalar` | 私有函数 | 解码单个标量：双引号走 JSON、单引号处理 `''` 转义、拒绝 `[ { & * !` | YAML 子集 |
| `parse_frontmatter` | 函数 | 解析顶层标量、`>`/`|` 块标量、一层 `metadata` 映射，返回 `(fields, body)` | 元数据与 body 分离 |
| `validate_skill_text` | 函数 | 依次检查各规则，汇总为 `SkillReport` | 包校验 |
| `TaskShape` | 冻结 dataclass | 六个布尔需求 | 任务分类 |
| `select_primitives` | 函数 | 需求 → 原语元组 | 原语决策 |
| `demo` | 函数 | 三个校验案例 + 五个决策案例，打印 JSON | 演示 |

数据流：`demo` 构造三份 `SKILL.md` 文本（其中一份经由临时目录写盘再读回）→ `validate_skill_text` → `parse_frontmatter` → 逐条规则生成 `ValidationIssue` → `SkillReport.to_dict()`；同时 `TaskShape(...)` → `select_primitives` → 汇总成一个字典 → `json.dumps(indent=2)` 打印。

---

## 3. 逐段精讲

### 3.1 常量：便携核心与命名正则

```python
CORE_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
```

- `CORE_FIELDS` 正是讲义"The portable core"一节列出的 2 个必填 + 4 个可选字段。凡不在这里的字段，都会被视为运行时扩展（见 3.6）。
- `NAME_PATTERN` 的结构：`[a-z0-9]+` 至少一段，后面跟零个或多个 `-段`。因此：不能以连字符开头/结尾、不能连续两个连字符、不能有大写和下划线。数字开头（如 `2fa-helper`）是允许的。
- `re.compile` 预编译一次，后面用 `fullmatch` 反复匹配。

### 3.2 结构化结果：`ValidationIssue` 与 `SkillReport`

```python
@dataclass(frozen=True)
class SkillReport:
    valid: bool
    name: str | None
    description: str | None
    body: str
    core_fields: tuple[str, ...]
    runtime_extensions: tuple[str, ...]
    issues: tuple[ValidationIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["issues"] = [asdict(issue) for issue in self.issues]
        return data
```

- `frozen=True`：报告一旦生成就不可修改，适合当作"证据"传递。
- 用 `tuple` 而不是 `list`：冻结 dataclass 里放可变列表仍然可以被就地修改，`tuple` 才真正不可变。
- `to_dict()` 里 `asdict` 本身已经会递归转换嵌套 dataclass，这里再显式处理 `issues` 一次，结果相同，属于"写明意图"的冗余。
- 讲义："Inspect the issue codes. A package validator should explain how to fix an artifact without guessing on the author's behalf." 所以每条 issue 都有稳定的 `code`（给程序用）和 `message`（给人看）。

### 3.3 `_decode_scalar`：一个刻意很小的 YAML 子集

```python
def _decode_scalar(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise FrontmatterSyntaxError(f"invalid quoted scalar: {error.msg}") from error
        ...
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise FrontmatterSyntaxError("unterminated single-quoted scalar")
        return value[1:-1].replace("''", "'")
    if value[0] in "[{&*!":
        raise FrontmatterSyntaxError("unsupported YAML construct in portable subset")
    return value
```

- **双引号**：借用 `json.loads` 解码，所以 `"quoted é"` 会得到 `quoted é`。这是一个巧妙的近似：YAML 双引号字符串的转义与 JSON 大体一致（但不完全相同，例如 YAML 支持 `\x41`，JSON 不支持）。
- **单引号**：YAML 单引号字符串里用两个单引号表示一个单引号，`'it''s'` → `it's`。
- **拒绝的结构**：`[`（流式序列）、`{`（流式映射）、`&`/`*`（锚点/别名）、`!`（标签）。拒绝 `!` 和锚点有安全意义——自定义标签是很多 YAML 反序列化漏洞的入口。
- **简化之处**：
  - 所有标量都返回字符串。`user-invocable: true` 存成 `"true"` 而不是布尔值；
  - 行内注释不处理：`name: x-skill # comment` 的值是 `x-skill # comment`，会触发 `name-format`；标准 YAML 会把 `# comment` 当注释。
  - 不检查未加引号值里的 `": "`：`description: Use when: deploying` 在这里被接受，但 PyYAML 实测抛 `ScannerError`（见测验 Q7）。

### 3.4 `parse_frontmatter`：逐行状态机

```python
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise FrontmatterSyntaxError("SKILL.md must begin with an exact --- line")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise FrontmatterSyntaxError("frontmatter needs a closing --- line") from error
```

- 第一行必须**恰好**是 `---`（多一个空格、带 BOM 都会失败）；`lines.index("---", 1)` 从第 2 行起找第一个闭合分隔符。
- `splitlines()` 会处理 `\r\n`，所以 Windows 换行的文件可以通过（实测）。

主循环每次处理一个顶层键：

```python
        if line[:1].isspace() or ":" not in line:
            raise FrontmatterSyntaxError(f"malformed top-level line {index + 1}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", key):
            raise FrontmatterSyntaxError(f"invalid field name {key!r}")
        if key in metadata:
            raise FrontmatterSyntaxError(f"duplicate field {key!r}")
```

- 空行与 `#` 开头的整行注释被跳过。
- 顶层行不能以空白开头、必须含冒号；`split(":", 1)` 只按第一个冒号切分。
- 字段名正则不允许下划线：`allowed_tools` 会得到 `invalid field name`，而**不是**"未知扩展字段"（测验 Q12(d)）。
- 重复字段直接报错——标准 YAML 规范也要求映射键唯一，但很多解析器会静默"后者覆盖前者"，这里选择更安全的做法。

块标量与 `metadata` 两个分支：

```python
        value = raw_value.strip()
        if value in {">", "|"}:
            block: list[str] = []
            index += 1
            while index < end and (not lines[index] or lines[index][:1].isspace()):
                block.append(lines[index].lstrip())
                index += 1
            metadata[key] = (" " if value == ">" else "\n").join(block).strip()
            continue
        if key == "metadata" and not value:
            nested: dict[str, str] = {}
            ...
                    nested[nested_key] = _decode_scalar(nested_value)
            ...
            metadata[key] = nested
            continue
        metadata[key] = _decode_scalar(value)
        index += 1
```

- `>`（折叠）用空格连接各行，`|`（字面）用换行连接——这让讲义测试里多行的 `description: >` 被折叠为一句话。
- 续行的判定是"空行或以空白开头"。
- ⚠️ `>-`、`|-`、`>+`、`|+` 这些带 chomping 指示符的写法**不被识别**，会落入 `_decode_scalar(">-")` 得到字符串 `">-"`，随后下一行缩进文本触发 `malformed top-level line`（实测）。
- ⚠️ 每行 `lstrip()` 会丢失相对缩进：`|` 块中多缩进 2 格的行与基准行变得一样（实测 `'line1\nindented\n\nline3'`）。
- `metadata` 只有在**值为空**时才进入嵌套映射分支；`metadata: owner` 会被当成字符串，后面由 `metadata-shape` 报错；`metadata: {}` 因为 `{` 被 `_decode_scalar` 拒绝而成为语法错误。
- 嵌套 `metadata` 的 key 没有做格式校验，`  : v` 会产生一个空字符串键（实测仍 `valid=True`）。第 24 节的实现补上了这一点。
- 变量名小坑：函数内保存所有字段的字典叫 `metadata`，与 frontmatter 中的 `metadata` 字段同名，读代码时容易混淆。

最后：

```python
    body = "\n".join(lines[end + 1 :]).strip()
    return metadata, body
```

body 是闭合分隔符之后的全部内容，去掉首尾空白。只有空白的 body 视为空。

### 3.5 `validate_skill_text`：先解析，后逐条规则

```python
    try:
        fields, body = parse_frontmatter(text)
    except FrontmatterSyntaxError as error:
        issue = ValidationIssue("frontmatter-syntax", str(error))
        return SkillReport(False, None, None, "", (), (), (issue,))
```

- 语法错误时**立即返回**，只有一条 `frontmatter-syntax`。这符合讲义"Validation order matters"：先检查廉价的结构事实，避免后续的次生错误淹没第一个真正的问题。

`name` 的检查是一条 `elif` 链：

```python
    if not name:
        issues.append(ValidationIssue("name-required", ...))
    elif len(name) > 64:
        issues.append(ValidationIssue("name-too-long", ...))
    elif not NAME_PATTERN.fullmatch(name):
        issues.append(ValidationIssue("name-format", ...))
    elif name != directory_name:
        issues.append(ValidationIssue("directory-mismatch", ...))
```

- 每次最多报一个 name 问题，按"缺失 → 过长 → 格式 → 目录不匹配"的顺序。例如 demo 中的 `Incident_Summary` 只报 `name-format`，不会同时报 `directory-mismatch`。
- `directory_name` 由调用方传入——函数本身只处理文本，不访问文件系统，便于测试。

其余规则：

| 规则 | issue code | 条件 |
|---|---|---|
| description 必填 | `description-required` | 缺失或只有空白 |
| description 长度 | `description-too-long` | > 1024 字符 |
| compatibility | `compatibility-empty` / `compatibility-too-long` | 出现时为空 / > 500 字符 |
| metadata 形状 | `metadata-shape` | 不是 `dict[str, str]` |
| allowed-tools 形状 | `allowed-tools-shape` | 出现时为空字符串 |
| body 必填 | `body-required` | body 为空 |
| 宿主扩展 | `unsupported-runtime-field` | 不在 `CORE_FIELDS` 也不在白名单 |

这些检查**相互独立**，都会追加，所以一个包可以同时得到多条 issue（例如缺 description 又缺 body）。

### 3.6 便携核心 vs 运行时扩展

```python
    extension_names = sorted(set(fields) - CORE_FIELDS)
    allowed = set(allowed_runtime_extensions)
    for field in extension_names:
        if field not in allowed:
            issues.append(
                ValidationIssue(
                    "unsupported-runtime-field",
                    f"{field!r} is not part of the portable contract or this host policy",
                )
            )

    return SkillReport(
        valid=not issues,
        ...
        core_fields=tuple(sorted(set(fields) & CORE_FIELDS)),
        runtime_extensions=tuple(extension_names),
        issues=tuple(issues),
    )
```

- 集合差 `set(fields) - CORE_FIELDS` 得到所有非核心字段；集合交 `&` 得到出现过的核心字段。两者都排序，保证输出确定。
- `runtime_extensions` **始终**列出全部非核心字段，不管它们是否被允许——所以同一份文件在"便携模式"下是 `valid=False` + 列出扩展，在"宿主模式"下是 `valid=True` + 列出扩展，两种结论都可区分（讲义练习 3）。
- 这实现了讲义的要求："Treat each extension as an adapter… A runtime may ignore an unknown field, reject it, or preserve it without implementing the behavior." 校验器选择**默认拒绝、显式放行**。
- 简化：白名单只检查字段名，不检查值（`user-invocable: maybe` 也会通过）。真实适配器还应校验扩展字段的取值。

### 3.7 `TaskShape` 与 `select_primitives`

```python
@dataclass(frozen=True)
class TaskShape:
    repeatable_method: bool = False
    repository_default: bool = False
    external_capability: bool = False
    lifecycle_event: bool = False
    deterministic_logic: bool = False
    isolated_delegation: bool = False


def select_primitives(task: TaskShape) -> tuple[str, ...]:
    """Select composable primitives by responsibility, not by product branding."""
    choices: list[str] = []
    if task.repository_default:
        choices.append("AGENTS.md")
    if task.repeatable_method:
        choices.append("Agent Skill")
    ...
    return tuple(choices or ["prompt"])
```

- 六个布尔字段对应讲义"Use It"决策卡的六个问题，全部默认 False。
- 用一串**独立的 `if`**（不是 `elif`），所以多个需求同时成立时会返回多个原语——这就是"组合"。
- `choices or ["prompt"]`：空列表为假，于是退回 prompt。
- 输出顺序是固定的检查顺序（`AGENTS.md` 永远在 `Agent Skill` 之前），不代表优先级。
- 简化：讲义决策卡里 lifecycle 一行写的是"Hook or application code"，代码只返回 `hook`；也没有"一次性指令但又需要外部能力"之类的冲突检测。随包 `SKILL.md` 要求"one sentence explaining each selection"，但函数只返回名字（测验 Q11 补上理由）。

### 3.8 `demo`：三个校验案例 + 五个决策案例

```python
    host_extended_example = portable_example.replace(
        "description:", "user-invocable: true\ndescription:", 1
    )
    invalid_example = portable_example.replace(
        "name: incident-summary", "name: Incident_Summary", 1
    )
    with tempfile.TemporaryDirectory(prefix="lesson-22-") as temp_dir:
        base = Path(temp_dir)
        portable_dir = base / "incident-summary"
        portable_dir.mkdir()
        portable_path = portable_dir / "SKILL.md"
        portable_path.write_text(portable_example, encoding="utf-8")
        portable_report = validate_skill_text(
            portable_path.read_text(encoding="utf-8"), portable_dir.name
        )
```

- 便携案例**真的写到临时目录再读回**，并用 `portable_dir.name` 作为目录名——演示"name 必须匹配目录"的真实来源。另外两个案例直接传字符串。
- `str.replace(old, new, 1)` 的第三个参数限定只替换第一次出现。
- `TemporaryDirectory` 在 `with` 结束时自动删除，所以 demo 不会留下文件。
- 结果字典里 `validation` 与 `validation_cases.portable_core` 内容完全相同，属于为兼容旧输出格式保留的重复。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用标准库、自写 YAML 小子集 | 每条规则都看得见，无需安装依赖 | 与真实 YAML 不一致（`>-` 被拒、`: ` 被放行、注释与布尔值不处理）；生产用 `yaml.safe_load` + schema |
| 语法错误立即返回 | 先报第一个被破坏的不变量，避免次生错误 | 作者一次只看到一个语法问题 |
| `name` 用 `elif` 链 | 一次只报最根本的 name 问题 | 修好格式后才会看到目录不匹配，需要多轮修复 |
| 其他规则独立累积 | 一次给出尽可能多的可修复问题 | 无 |
| 未知字段默认拒绝 + 白名单 | 不把某宿主的约定伪装成标准 | 只校验字段名不校验取值；真实适配器要验证语义 |
| 报告用冻结 dataclass + code | 可序列化、可断言、可在 CI 中复用 | code 与随包 `check_skill.py` 不一致（见测验 Q10），应抽成共享库 |
| `validate_skill_text` 只接收文本 + 目录名 | 纯函数，易测试 | 不检查文件是否 symlink、引用文件是否存在；随包脚本做了前者，后者要到第 24 节 |
| `select_primitives` 用独立 `if` | 允许多原语组合 | 没有理由说明、没有冲突检测 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件第一行 | 注解延迟求值，可在旧版本 Python 中使用 `str \| None` 等新写法 |
| 冻结 dataclass | `@dataclass(frozen=True) class SkillReport` | 自动生成 `__init__`、`__eq__`；实例不可修改 |
| 联合类型注解 | `name: str \| None` | 值可以是字符串或 None |
| 变长元组注解 | `tuple[str, ...]` | 任意长度、元素都是 `str` 的元组 |
| `asdict` | `asdict(self)` | 把 dataclass（含嵌套）递归转成字典 |
| 自定义异常 | `class FrontmatterSyntaxError(ValueError)` | 继承内置异常，调用方可以只捕获这一种 |
| `raise ... from error` | `raise FrontmatterSyntaxError(...) from error` | 保留原始异常链，便于排查 |
| `try / except / else` 风格 | `try: end = lines.index("---", 1) except ValueError` | `list.index` 找不到时抛 `ValueError` |
| 编译正则 + `fullmatch` | `NAME_PATTERN.fullmatch(name)` | 整个字符串都必须匹配，等价于加 `^...$` |
| 非捕获组 | `(?:-[a-z0-9]+)*` | 分组但不保存匹配结果 |
| `str.split(sep, 1)` | `line.split(":", 1)` | 最多切一刀，返回两段 |
| 切片 | `line[:1]`、`value[1:-1]`、`lines[end + 1 :]` | `line[:1]` 在空串上也安全（返回空串），比 `line[0]` 稳 |
| 字符串方法 | `.strip()`、`.lstrip()`、`.startswith()`、`.endswith()`、`.replace(a, b, 1)` | 去空白、判断前后缀、限次替换 |
| 集合运算 | `set(fields) - CORE_FIELDS`、`set(fields) & CORE_FIELDS` | 差集、交集 |
| `Iterable` 参数 + 默认空元组 | `allowed_runtime_extensions: Iterable[str] = ()` | 接受任何可迭代对象；用不可变的 `()` 做默认值，避免可变默认参数陷阱 |
| 生成器表达式 + `all` | `all(isinstance(k, str) and isinstance(v, str) for k, v in metadata.items())` | 所有元素都满足才为 True |
| `or` 返回操作数 | `tuple(choices or ["prompt"])` | 左边为空时取右边 |
| `isinstance` 守卫 | `name = name_value if isinstance(name_value, str) else None` | 条件表达式 + 类型检查 |
| `!r` 格式符 | `f"invalid field name {key!r}"` | 用 `repr()` 显示，字符串会带引号 |
| 三引号多行字符串 | `portable_example = """---\nname: ..."""` | 保留换行 |
| `with` 上下文管理器 | `with tempfile.TemporaryDirectory(prefix="lesson-22-") as temp_dir:` | 退出时自动清理临时目录 |
| `pathlib` | `base / "incident-summary"`、`.mkdir()`、`.write_text(...)`、`.name` | `/` 拼接路径；`.name` 取最后一段 |
| `json.dumps(indent=2)` | `print(json.dumps(result, indent=2))` | 元组会被序列化为 JSON 数组 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 demo，被测试导入时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 code/main.py`，退出码 0），节选：

```text
{
  "validation": {
    "valid": true,
    "name": "incident-summary",
    "description": "Summarize an incident timeline when the user supplies event notes.",
    "body": "# Incident summary\n\nPreserve timestamps and separate observations from inferences.",
    "core_fields": ["description", "metadata", "name"],
    "runtime_extensions": [],
    "issues": []
  },
  "validation_cases": {
    "portable_core": { ...与上面相同... },
    "host_extended": {
      "valid": true,
      ...
      "runtime_extensions": ["user-invocable"],
      "issues": []
    },
    "invalid_package": {
      "valid": false,
      "name": "Incident_Summary",
      ...
      "issues": [
        {"code": "name-format",
         "message": "name must use lowercase letters, digits, and single hyphens"}
      ]
    }
  },
  "decision_examples": {
    "one_off_rewrite": ["prompt"],
    "repeatable_repo_workflow_with_api": ["AGENTS.md", "Agent Skill", "MCP tool"],
    "post_test_automation": ["hook"],
    "schema_normalization": ["ordinary code"],
    "parallel_isolated_research": ["subagent"]
  }
}
```

（实际输出中每个数组元素各占一行，这里为节省篇幅合并。）

逐项解读：

- **portable_core**：`core_fields` 为排序后的 `description, metadata, name`；嵌套的 `metadata: owner: reliability` 被解析成映射，形状检查通过；`runtime_extensions` 为空。
- **host_extended**：同一文本多了 `user-invocable: true`，因为传入了 `allowed_runtime_extensions={"user-invocable"}` 而有效，但 `runtime_extensions` 依然把它列出来——"宿主扩展包"与"便携包"仍可区分。
- **invalid_package**：`Incident_Summary` 含大写和下划线，只报 `name-format`。由于 `elif` 链，即使目录名是 `incident-summary`，也没有额外报 `directory-mismatch`。注意 `name` 字段仍然返回了原值，便于定位。
- **decision_examples**：五个例子与讲义"Use It"决策卡一一对应；第二个例子演示了"一个工作流同时用三个原语"。
- 额外验证：把随包 `outputs/skill-contract-reviewer/SKILL.md` 喂给 `validate_skill_text(text, "skill-contract-reviewer")` 得到 `valid=True`，`core_fields=('description', 'license', 'metadata', 'name')`；用随包脚本 `check_skill.py` 校验同一目录也是 `valid: true`、退出码 0。

---

## 7. 动手改一改

1. **（讲义练习 2）** 为 `compatibility` 写边界测试：500 个字符通过、501 个字符得到 `compatibility-too-long`；再加一条 `compatibility:` 为空时得到 `compatibility-empty`。（前两条现有测试已覆盖，可对照阅读后自己再写一遍。）
2. **支持 chomping 指示符**：让 `>-`、`|-`、`>+`、`|+` 被识别，并用 `textwrap.dedent` 保留 `|` 块的相对缩进；用 PyYAML 的结果做对拍测试（测验 Q9）。
3. **（讲义练习 3）** 再加一个宿主扩展（如 `argument-hint`）到白名单，写测试证明：同一文件在便携模式下 `valid=False`，在宿主模式下 `valid=True`，且两种模式下 `runtime_extensions` 都含该字段。进一步：为白名单增加"取值校验器"，例如 `user-invocable` 只接受 `true`/`false`。
4. **统一两个校验器**：把 `main.py` 与 `outputs/.../check_skill.py` 的规则抽到一个共享函数，统一 issue code（`description-too-long` vs `description-length` 等），并写一组对拍 fixture（测验 Q10）。
5. **（讲义练习 1 + 测验 Q11）** 给 `select_primitives` 增加理由输出，然后用 `TaskShape` 为你团队的五个真实工作流分类，为每个多原语的结果写一句辩护。
6. **进阶（讲义练习 5）**：写一个 `check_tool_references(body, available_tools)`，扫描 body 中形如 `` `mcp__server__tool` `` 的引用，若宿主没有该工具则产出 `missing-tool` issue，并检查 body 是否写了"不可用时停止并报告"的退路句。

---

## 8. 常见坑

- **把 `SKILL.md` 当成整个包**：只拷贝入口文件，`references/` 和 `scripts/` 丢失，包"能解析但不能用"。
- **以为 `valid=True` 等于"可以安全执行"**：结构合法不授予任何文件、网络、密钥或工具权限。
- **在 description 中写未加引号的冒号**：`description: Use when: …` 在本节解析器里通过，在真实 YAML 宿主里加载失败。要么加引号，要么改用 `>` 块。
- **使用 `>-` / `|-`**：本节解析器会报 `malformed top-level line`，不是你的 YAML 写错了，是解析器子集不支持。
- **行内注释**：`name: my-skill # TODO` 会让 `name` 变成 `my-skill # TODO` 并报 `name-format`。
- **字段名写下划线**：`allowed_tools` 是语法错误而不是"未知扩展"，错误信息是 `invalid field name`。
- **以为 `user-invocable: true` 是布尔值**：本解析器把它存成字符串 `"true"`；如果后续代码写 `if fields["user-invocable"]:`，字符串 `"false"` 也为真。
- **修好 name 格式后又冒出新错误**：`elif` 链一次只报一个 name 问题，修完格式后才会看到 `directory-mismatch`。
- **混淆两个"metadata"**：函数内部的局部变量 `metadata` 是"全部字段"，frontmatter 里的 `metadata` 是其中一个字段。

---

## 9. 测试在验证什么

运行方式（在小节目录下）：`python3 -m unittest discover -s code/tests -v`。测试文件开头设置 `sys.dont_write_bytecode = True`，不会生成 `__pycache__`。实际结果：**Ran 19 tests … OK**。

测试辅助函数 `skill_text(name, description)` 生成一个最小合法包，各用例在它基础上用 `str.replace` 注入问题。

| 测试类 / 用例 | 验证的性质 |
|---|---|
| `FrontmatterTests.test_parses_folded_description_and_metadata` | `>` 块被折叠成一行；嵌套 `metadata` 解析为 `{"owner": "platform"}`；body 正确分离 |
| `FrontmatterTests.test_rejects_duplicate_fields` | 重复 `name` → `frontmatter-syntax`（而不是静默覆盖） |
| `FrontmatterTests.test_rejects_malformed_top_level_line` | 无冒号的顶层行 → `frontmatter-syntax` |
| `ValidationTests.test_accepts_valid_core_skill` | 最小合法包 `valid=True` 且无扩展字段 |
| `test_rejects_non_kebab_name` | `Release_Check` → `name-format` |
| `test_rejects_directory_mismatch` | 目录名不同 → `directory-mismatch` |
| `test_requires_description` | 空 description → `description-required` |
| `test_host_extension_requires_explicit_policy` | 同一文本：无白名单 `valid=False`，有白名单 `valid=True` 且 `runtime_extensions == ("user-invocable",)` |
| `test_compatibility_enforces_normative_length` | 500 字符通过、501 字符 → `compatibility-too-long`（即讲义练习 2） |
| `test_metadata_must_be_string_mapping` | `metadata: owner` → `metadata-shape` |
| `test_allowed_tools_must_be_non_empty_string` | `allowed-tools:` 为空 → `allowed-tools-shape` |
| `test_bundled_checker_parses_folded_description` | 用 `importlib.util.spec_from_file_location` 动态加载**随包脚本** `check_skill.py`，验证它也能折叠 `>` 块 |
| `test_bundled_checker_validates_optional_core_fields` | 随包脚本接受 `compatibility`、`metadata`、`allowed-tools` 同时出现 |
| `test_bundled_checker_rejects_malformed_top_level_line` | 随包脚本对坏行报 `frontmatter-syntax` |
| `DecisionModelTests`（5 个） | 空需求 → prompt；三需求 → `("AGENTS.md", "Agent Skill", "MCP tool")`；lifecycle → hook；deterministic → ordinary code；isolated → subagent |

测试没有覆盖、值得补的地方：

- 两个校验器在**同一输入**上结论一致（目前分别测、没对拍，测验 Q10 列出了四个不一致的输入）；
- `>-`、行内注释、`": "` 等与真实 YAML 不一致的写法（至少应有测试固定"明确拒绝"的行为）；
- `name-too-long`、`description-too-long`、`body-required` 三个 code 没有专门用例；
- `select_primitives` 同时开启全部六个需求时的顺序（实测为 `AGENTS.md, Agent Skill, MCP tool, hook, ordinary code, subagent`）。
