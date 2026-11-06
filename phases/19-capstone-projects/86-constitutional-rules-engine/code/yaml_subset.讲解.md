# 代码讲解 · yaml_subset.py

> **所属小节**：阶段 19 · 综合项目 · 第 86 节 综合项目 86：宪法式规则引擎 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md) ｜ 引擎与测试：[main.讲解.md](main.讲解.md)
>
> **运行方式**：被 `main.py` 和 `tests.py` 导入，没有 `__main__`；可单独调用 `from yaml_subset import load_yaml, _parse` ｜ **依赖**：标准库 `re`、`typing`；可选第三方 `PyYAML`（安装了就优先使用）

---

## 1. 这份代码在考察什么

规则引擎的宪法写在 YAML 里，但 Python 标准库没有 YAML 解析器。这个模块做了两件事：

1. **优先用 PyYAML**：`load_yaml` 先尝试 `import yaml` 并调用 `yaml.safe_load`；
2. **兜底的手写解析器**：没有 PyYAML 时，用约 140 行代码解析一个 YAML **子集**——两空格缩进的块映射、`- key: value` 形式的块序列、带引号或不带引号的字符串、整数/浮点/布尔/null、行尾注释。

这让课程在"任何标准 Python 环境"都能运行。同时它也是一个很好的**递归下降解析器**教学样例：按缩进把行切成块，映射和序列互相递归。

> 一句话：**用最少的代码读懂 `rules.yml`；但它只是 YAML 的一个子集，遇到子集之外的写法会静默出错**——这正是为什么生产环境应该直接用 `yaml.safe_load`。

需要先说明的事实（已实测）：

- 本机装有 PyYAML 6.0.3，所以默认情况下 `_parse` **完全不会被执行**，包括 `tests.py` 中的 `TestYamlSubset`。
- 用 import 钩子屏蔽 PyYAML 后，`_parse(rules.yml)` 与 `yaml.safe_load(rules.yml)` 的结果**完全相等**，18 个测试全部通过，demo 输出与仓库报告逐字节一致。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `load_yaml` | 公共函数 | 有 PyYAML 用 `safe_load`，否则用 `_parse` | 可选依赖 + 降级 |
| `_strip_comment` | 函数 | 去掉不在引号内的 `#` 及其后内容 | 注释处理 |
| `_indent_of` | 函数 | 行首空格数 | 缩进即结构 |
| `_coerce` | 函数 | 把标量字符串转成 None/bool/int/float/str/空容器 | 类型推断 |
| `_parse` | 函数 | 预处理所有行，从第一行开始解析一个块 | 入口 |
| `_parse_block` | 函数 | 看第一行是否以 `- ` 开头，分派给序列或映射 | 递归下降的分派 |
| `_parse_mapping` | 函数 | 解析同一缩进层的 `key: value` 行，遇到子块递归 | 块映射 |
| `_parse_sequence` | 函数 | 解析同一缩进层的 `- ...` 行，`- key: value` 项转为映射 | 块序列 |

数据流：YAML 文本 → `_parse`（去注释、去空行）→ `_parse_block` → `_parse_mapping` / `_parse_sequence` 互相递归 → `_coerce` 处理每个标量 → Python 的 dict / list / 标量。

---

## 3. 逐段精讲

### 3.1 load_yaml：可选依赖与降级

```python
def load_yaml(text: str) -> Any:
    try:
        import yaml  # type: ignore[import-not-found]
        return yaml.safe_load(text)
    except ModuleNotFoundError:
        return _parse(text)
```

- `import` 写在函数**内部**：每次调用时尝试导入（导入过一次后只是查 `sys.modules`，代价很小）。没装 PyYAML 时抛 `ModuleNotFoundError`，走手写解析器。
- 用的是 `safe_load` 而不是 `load`：`yaml.load` 配合不安全的 Loader 可以通过 `!!python/object` 标签构造任意 Python 对象，宪法文件一旦被篡改就能执行代码。`safe_load` 只构造基本类型——这是正确且重要的选择。
- `# type: ignore[import-not-found]` 是给 mypy 等类型检查器看的注释，告诉它"这个模块可能不存在，不要报错"。
- ⚠️ `try` 块同时包住了 `yaml.safe_load(text)`。如果将来 PyYAML 内部因为某个依赖缺失抛出 `ModuleNotFoundError`，也会被当成"没装 PyYAML"而悄悄换成 `_parse`。更严谨的写法是只把 `import` 放进 `try`。
- ⚠️ **两条路径语义不同**（见第 6 节表格）：同一份 YAML 在装与不装 PyYAML 的机器上可能得到不同结果，而调用方无从得知用的是哪一条。

### 3.2 _strip_comment：引号感知的去注释

```python
def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
    return line
```

- 一个两状态的小**状态机**：记录当前是否在单引号 / 双引号里，只有在引号外遇到 `#` 才截断。这样 `pattern: '\d+#x'` 里的 `#` 不会被误删。
- 已实测的偏差：
  - `explanation: don't leak # secret`：撇号被当成单引号开头，后面的 `#` 处在"引号内"，注释没去掉，结果是 `"don't leak # secret"`；PyYAML 得到 `"don't leak"`。
  - `url: http://x.com/#frag`：YAML 规定 `#` 前面必须有空白才算注释，PyYAML 保留 `#frag`，这里却被截成 `http://x.com/`。
  - 不处理双引号字符串里的转义引号 `\"`。

### 3.3 _indent_of 与 _coerce：缩进和标量

```python
def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))
```

- 只数**空格**。用 Tab 缩进的行缩进为 0（YAML 本身禁止用 Tab 缩进，PyYAML 会报错；这里则把子键当成了同级键：`"a:\n\tb: 1"` 解析成 `{'a': None, 'b': 1}`）。

```python
def _coerce(value: str) -> Any:
    s = value.strip()
    if s == "":
        return None
    if s == "{}":
        return {}
    if s == "[]":
        return []
    if s in ("true", "True"):
        return True
    ...
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        inner = s[1:-1]
        if s[0] == '"':
            inner = inner.encode("utf-8").decode("unicode_escape")
        return inner
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s
```

- 判定顺序：空 → 空容器 → 布尔 → null → 引号字符串 → int → float → 普通字符串。用 `try/except ValueError` 做"能转就转"。
- `{}` 很关键：`rules.yml` 里的 `applies_when: {}` 依赖它变成空字典，引擎再把空字典当作"恒为真"。
- **单引号**：内容原样保留，所以正则写在单引号里最安全（`'\b(i cannot|...)\b'` 中的反斜杠不会被解释）。这也是 `rules.yml` 中所有正则都用单引号的原因。
- **双引号**：用 `unicode_escape` 解码，让 `"\n\nIf this ..."` 里的 `\n` 变成真正的换行——`rules.yml` 的 fix 文本依赖这一点。
- ⚠️ `encode("utf-8").decode("unicode_escape")` 会把**非 ASCII 字符**搞成乱码：`"café"` 先编码成 UTF-8 字节，再被当作 Latin-1 逐字节解码，得到 `cafÃ©`（已实测）。中文 explanation 写在双引号里就会出问题。
- ⚠️ 单引号里 YAML 用 `''` 表示一个 `'`，这里没处理：`'it''s'` 得到 `it''s`。
- ⚠️ 与 YAML 1.1（PyYAML）的类型推断不同：`yes/no/on/off` 在 PyYAML 中是布尔，这里是字符串；`010` 在 PyYAML 中是八进制 8，这里是 10；`1e3` 在 PyYAML 中是字符串，这里是 1000.0。
- ⚠️ 模块文档说支持"inline list values on the right of ':' for simple atoms"，但实际只支持空列表 `[]`；`[1, 2]` 会被当成字符串 `'[1, 2]'`。

### 3.4 _parse 与 _parse_block：入口与分派

```python
def _parse(text: str) -> Any:
    raw_lines = []
    for raw in text.splitlines():
        stripped = _strip_comment(raw).rstrip()
        if stripped.strip() == "":
            continue
        raw_lines.append(stripped)
    if not raw_lines:
        return None
    return _parse_block(raw_lines, 0, _indent_of(raw_lines[0]))[0]


def _parse_block(lines, start, indent):
    if start >= len(lines):
        return None, start
    first = lines[start]
    cur_indent = _indent_of(first)
    if cur_indent < indent:
        return None, start
    stripped = first.lstrip()
    if stripped.startswith("- "):
        return _parse_sequence(lines, start, cur_indent)
    return _parse_mapping(lines, start, cur_indent)
```

- 预处理：去注释、去行尾空白、丢掉空行和纯注释行。之后所有函数都只处理"有内容的行"。
- 所有解析函数都返回 `(值, 下一个未消费的行号)` 这样的**二元组**，调用方据此继续往下读，这是手写递归下降解析器的常见约定。
- `_parse` 只取 `[0]`（值），**不检查是否所有行都被消费了**。剩余的行会被静默丢弃（见 3.5 的例子）。
- `_parse_block` 只看第一行：以 `- ` 开头就是序列，否则是映射。

### 3.5 _parse_mapping：块映射

```python
def _parse_mapping(lines, start, indent):
    out = {}
    i = start
    while i < len(lines):
        line = lines[i]
        cur_indent = _indent_of(line)
        if cur_indent < indent:
            break                        # 缩进变小：本层结束
        if cur_indent > indent:
            i += 1
            continue                     # 缩进变大但没被子块消费：跳过
        stripped = line.lstrip()
        if stripped.startswith("- "):
            break                        # 同层出现序列项：本映射结束
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", stripped)
        if not m:
            raise ValueError(f"malformed line: {line!r}")
        key = m.group(1)
        rest = m.group(2)
        if rest.strip() == "":
            if i + 1 < len(lines) and _indent_of(lines[i + 1]) > indent:
                value, i = _parse_block(lines, i + 1, _indent_of(lines[i + 1]))
                out[key] = value
                continue
            out[key] = None
            i += 1
        else:
            out[key] = _coerce(rest)
            i += 1
    return out, i
```

- 键的正则 `^([A-Za-z_][\w-]*)\s*:\s*(.*)$`：键以字母或下划线开头，后面可以有字母、数字、下划线、短横（所以 `applies_when`、`append_if_missing`、`no-empty-refusal` 都合法）；冒号后的全部内容是 `rest`。数字开头的键或带引号的键会报 `malformed line`。
- **`key:` 后面为空**：看下一行是否缩进更深。是 → 递归解析子块（可能是映射也可能是序列）；否 → 值为 `None`。
- **`key: value`**：交给 `_coerce`。注意 `rest` 里可以再有冒号：`a: hello: world` 得到 `'hello: world'`（PyYAML 会报错）。
- ⚠️ **同缩进序列被丢弃**：YAML 允许这样写

  ```yaml
  items:
  - id: 1
    label: a
  ```

  `items:` 的下一行缩进为 0，不大于 0，于是 `items = None`；接着遇到 `- ` 行就 `break`。返回到 `_parse` 后剩余的行全部丢失，实测结果是 `{'items': None}`，而 PyYAML 得到列表。如果宪法里某条规则的 `any_of:` 用这种写法，`must` 会变成 `{'any_of': None}`，加载时不报错，直到评估时才抛 `TypeError`（见测验 Q10）。
- ⚠️ **多余缩进被跳过**：`cur_indent > indent` 的行直接 `i += 1; continue`。`"a:\n  b: 1\n    c: 2\n  d: 3"` 得到 `{'a': {'b': 1, 'd': 3}}`，`c` 消失；PyYAML 会报语法错误。

### 3.6 _parse_sequence：块序列

```python
def _parse_sequence(lines, start, indent):
    out = []
    i = start
    while i < len(lines):
        ...
        rest = stripped[2:]
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", rest)
        if m:
            child_indent = indent + 2
            synthetic = " " * child_indent + rest
            j = i + 1
            extra_lines = []
            while j < len(lines) and _indent_of(lines[j]) > indent:
                extra_lines.append(lines[j])
                j += 1
            block = [synthetic] + extra_lines
            value, _ = _parse_mapping(block, 0, child_indent)
            out.append(value)
            i = j
        else:
            out.append(_coerce(rest))
            i += 1
    return out, i
```

- 这是整个文件最巧妙的地方：对 `- name: no-empty-refusal` 这样的项，去掉 `- ` 后，在前面补 `indent + 2` 个空格，造出一行**合成行**（synthetic line）`    name: no-empty-refusal`。于是它和后续的 `    severity: medium` 等行缩进一致，可以直接交给 `_parse_mapping` 当作一个普通映射解析。
- 收集"属于这一项"的行：从下一行开始，只要缩进 **大于** 序列的缩进，都算这一项的内容。
- 不是 `key: value` 形式的项（如 `- 42`、`- hello`）用 `_coerce` 作为标量。
- 以 `rules.yml` 为例，`rules:` 下的 `  - name: ...` 缩进为 2，`child_indent = 4`，规则内部的 `    severity:` 等正好是 4，`applies_when` 下的子键是 6、`any_of` 下的项是 8，层层递归。
- ⚠️ 假设项内续行的缩进**恰好**是 `indent + 2`。如果写成 `-   name: x`（短横后多个空格），`stripped[2:]` 以空格开头，键正则匹配失败，整项变成字符串。
- ⚠️ 不支持 `-` 单独占一行、下一行再写映射的写法（会报 `malformed line`）。
- `_parse_sequence` 中 `cur_indent > indent` 的 `- ` 行也被直接跳过，同样是静默行为。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 可选依赖 + 手写兜底 | 课程在没有第三方包的环境也能运行 | 两条路径语义不同；生产直接依赖 PyYAML 或改用 JSON/TOML（`tomllib` 是标准库） |
| 用 `safe_load` | 防止 YAML 标签构造任意对象 | 无；这是正确做法 |
| 只支持 YAML 子集 | 宪法格式刻意避开锚点、flow style、多行块 | 子集外的写法不报错而是静默出错；应在发现不支持的语法时抛异常 |
| 按缩进递归下降 | 代码短、容易理解 | 不检查剩余行、跳过多余缩进，错误被吞掉 |
| 双引号用 `unicode_escape` | 一行代码支持 `\n` 等转义 | 非 ASCII 字符乱码；应只替换有限的转义序列，或 `codecs.decode` 前先处理编码 |
| 合成行技巧解析 `- key: v` | 复用 `_parse_mapping`，不必单独写"序列项映射"的逻辑 | 依赖固定的 2 空格缩进约定 |
| 返回 `(值, 下一行号)` | 递归调用之间传递解析位置 | 顶层调用丢弃了行号，失去"是否解析完"的检查机会 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块文档字符串 | 文件开头的 `"""Minimal YAML subset parser ..."""` | 用 `help(yaml_subset)` 可以看到 |
| 函数内 `import` | `import yaml` 写在 `load_yaml` 里 | 延迟导入，适合可选依赖 |
| `try / except 具体异常` | `except ModuleNotFoundError:`、`except ValueError: pass` | 只捕获预期的异常；`pass` 表示什么也不做、继续往下 |
| `typing.Any` | `def load_yaml(text: str) -> Any` | 返回值类型不确定（dict、list、标量都可能） |
| 元组返回值与解包 | `value, i = _parse_block(...)`、`value, _ = _parse_mapping(...)` | 一次返回多个值；`_` 表示忽略 |
| 元组类型注解 | `-> tuple[dict[str, Any], int]` | 说明返回"一个字典和一个整数" |
| 布尔开关取反 | `in_single = not in_single` | 简单状态机 |
| `enumerate` | `for i, ch in enumerate(line)` | 同时拿到下标和字符 |
| 字符串切片 | `line[:i]`、`s[1:-1]`、`stripped[2:]` | 截取前缀、去掉首尾引号、去掉 `- ` |
| `lstrip(" ")` 与 `lstrip()` | `_indent_of` 与 `first.lstrip()` | 前者只去空格，后者去所有空白（包括 Tab） |
| `in` 判断元组成员 | `s in ("true", "True")` | 比多个 `==` 用 `or` 连接更简洁 |
| `str.encode` / `bytes.decode` | `inner.encode("utf-8").decode("unicode_escape")` | 字符串与字节互转；`unicode_escape` 会解释 `\n` 等转义 |
| `re.match` 与分组 | `m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", stripped)`、`m.group(1)` | 从开头匹配；`group(n)` 取第 n 个括号的内容 |
| f-string 中的 `!r` | `f"malformed line: {line!r}"` | 用 `repr()` 显示，能看到引号和不可见字符 |
| `raise ValueError(...)` | `_parse_mapping` | 主动抛出异常报告格式错误 |
| `while` + 手动下标 | `while i < len(lines): ... i += 1` | 需要跳过多行或回退时比 `for` 灵活 |
| 字符串乘法 | `" " * child_indent` | 生成指定数量的空格 |
| 列表拼接 | `[synthetic] + extra_lines` | 两个列表合并成新列表 |

---

## 6. 运行结果解读

本模块没有入口。下面是在副本中实际运行得到的对比（`_parse` 为手写解析器，`safe_load` 为 PyYAML 6.0.3）：

```text
rules.yml equal: True        ← 课程自带的宪法，两条路径结果完全相同
```

| 输入 | `_parse` | `yaml.safe_load` | 说明 |
|---|---|---|---|
| `items:\n- id: 1\n  label: a\n- id: 2` | `{'items': None}` | `{'items': [{'id': 1, 'label': 'a'}, {'id': 2}]}` | 同缩进序列丢失 |
| `msg: "café"` | `'cafÃ©'` | `'café'` | `unicode_escape` 乱码 |
| `explanation: don't leak # secret` | `"don't leak # secret"` | `"don't leak"` | 撇号干扰注释识别 |
| `url: http://x.com/#frag` | `'http://x.com/'` | `'http://x.com/#frag'` | `#` 前没有空格不算注释 |
| `a:\n  b: 1\n    c: 2\n  d: 3` | `{'a': {'b': 1, 'd': 3}}` | `ScannerError` | 多余缩进被静默跳过 |
| `{"rules": []}` | `ValueError: malformed line` | `{'rules': []}` | 不支持 flow style / JSON |
| `flag: yes` | `'yes'` | `True` | YAML 1.1 布尔 |
| `q: 'it''s'` | `"it''s"` | `"it's"` | 单引号转义 |
| `a: 010` | `10` | `8` | 八进制 |
| `a: 1e3` | `1000.0` | `'1e3'` | 浮点规则不同 |
| `a: [1, 2]` | `'[1, 2]'` | `[1, 2]` | 文档声称支持，实际不支持 |

屏蔽 PyYAML 后运行 `tests.py`：`Ran 18 tests ... OK`；运行 `main.py`：生成的 `rules_report.json` 与仓库中的文件逐字节一致。

解读：对课程自带的 `rules.yml`，手写解析器是对的；但它对 YAML 子集之外的写法**不报错**，而是返回一个"看起来合理"的错误结果。对安全规则文件来说，"静默地少了一条规则"比"加载失败"危险得多。

---

## 7. 动手改一改

1. **让测试真正覆盖 `_parse`**：在 `tests.py` 中新增一个测试类，直接调用 `yaml_subset._parse`（而不是 `load_yaml`），复用 `TestYamlSubset` 的 5 个用例；再加一个断言 `_parse(rules.yml) == yaml.safe_load(rules.yml)`（用 `unittest.skipUnless` 在没有 PyYAML 时跳过）。
2. **支持同缩进序列**：修改 `_parse_mapping`，当 `key:` 后为空且下一行缩进**等于**当前缩进并以 `- ` 开头时，调用 `_parse_sequence`。用第 6 节第一行的例子验证。
3. **拒绝静默丢数据**：在 `_parse` 末尾检查返回的行号是否等于总行数；在 `_parse_mapping` 中把"多余缩进就跳过"改成抛 `ValueError`。
4. **修复 Unicode**：把双引号处理改成只替换 `\n`、`\t`、`\"`、`\\` 几种转义（或用 `json.loads('"' + inner + '"')`），验证 `"café"` 和中文正常。
5. **注释规则对齐 YAML**：只有 `#` 位于行首或前面是空白时才算注释，并正确处理单引号字符串中的 `''`。
6. **进阶**：给 `_parse` 增加最小的 flow style 支持（`[a, b]` 和 `{k: v}` 中的简单标量），让讲义所说的"JSON 文件"在没有 PyYAML 时也能加载。

---

## 8. 常见坑

- **以为测试覆盖了手写解析器**：装了 PyYAML 时，`load_yaml` 根本不走 `_parse`。
- **双引号里写正则**：PyYAML 会把 `"\d"` 当作非法转义报错，手写解析器则保留原样——两条路径行为不同。正则一律用单引号。
- **用 Tab 缩进**：手写解析器把 Tab 缩进的行当成缩进 0，结构全乱。
- **同缩进序列风格**：很多编辑器和格式化工具默认输出这种风格，手写解析器会丢数据。
- **非 ASCII 文本放在双引号里**：会被 `unicode_escape` 解码成乱码。
- **把 `yes/no` 当字符串**：在 PyYAML 中它们是布尔值；规则文件里的枚举值最好加引号。
- **用 `yaml.load` 代替 `yaml.safe_load`**：加载不可信 YAML 时可能执行任意代码。
