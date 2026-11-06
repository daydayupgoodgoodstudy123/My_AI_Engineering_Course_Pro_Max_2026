# 代码讲解 · main.py（含 rules.yml 与 tests.py）

> **所属小节**：阶段 19 · 综合项目 · 第 86 节 综合项目 86：宪法式规则引擎 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md) ｜ YAML 解析器：[yaml_subset.讲解.md](yaml_subset.讲解.md)
>
> **运行方式**：`cd code && python3 main.py`；测试 `python3 -m unittest tests -v` 或 `python3 -m pytest -q tests.py` ｜ **依赖**：标准库（`difflib`、`json`、`re`、`dataclasses`、`pathlib`、`typing`）+ 同目录 `yaml_subset.py`；可选第三方 `PyYAML`（装了就优先使用）

---

## 1. 这份代码在考察什么

`main.py` 实现了一个**声明式规则引擎**：规则写在 `rules.yml` 里，引擎读取后对模型的候选输出逐条求值，再用每条规则自带的 `fix` 做确定性修复，最后给出修复前后的结构化 diff。

1. **规则 = 名字 + 谓词 + 解释**：讲义开篇："A rule is a name, a predicate, and an explanation. Anything missing one of those three is a vibe, not a rule." 引擎在加载时校验 `name / severity / must / explanation`。
2. **谓词组合**：6 种原子谓词（正则包含/不包含、开头/结尾、词数上下限）+ 3 种组合（`all_of / any_of / not_`），递归求值。
3. **三态结果**：`applies_when` 不满足 → `not_applicable`；否则 `must` 满足 → `pass`，不满足 → `violation`。
4. **修复闭环**：草稿 → 违规 → fixer → 修订稿 → 第二遍评估 → diff。讲义："A rule engine that only blocks is half-built."
5. **与第 85、87 节对接**：severity 用 `low / medium / high`，`EngineReport.max_severity()` 给第 87 节的安全关卡使用。

> 一句话：**把"回复必须遵守的契约"写成可评审的数据，再用一个小解释器去执行它**；同时要看清这个解释器在哪些地方会"静默地做错事"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `rules.yml` | YAML 数据 | 6 条规则组成的宪法 | constitution |
| `HERE / OUTPUTS / DEFAULT_RULES_PATH` | 常量 | 定位代码、输出目录和默认规则文件 | 路径 |
| `SEVERITY_ORDER` | 元组 | `("low", "medium", "high")`（没有 none） | severity |
| `Violation` | dataclass | 规则名、severity、解释、匹配片段 | 违规记录 |
| `RuleResult` | dataclass | 同上 + `status`（pass/violation/not_applicable） | 每条规则的结果 |
| `EngineReport` | dataclass | 原文 + 全部 `RuleResult`；`violations()`、`max_severity()` | 评估报告 |
| `Change` | dataclass | `op` + 一行文本 | diff 条目 |
| `_word_count` | 函数 | `\b\w+\b` 计数 | `max_words / min_words` |
| `_eval_predicate` | 递归函数 | 求值任意谓词树，返回 `(是否满足, 匹配片段)` | 谓词解释器 |
| `Engine` | 类 | 加载并校验规则；`evaluate(text)` | 规则引擎 |
| `Fixer` | 类 | 按规则名应用 `append / prepend / replace_regex` | 确定性修复 |
| `diff` | 函数 | `difflib.SequenceMatcher` 按行比较 | 结构化 diff |
| `_DEMO_DRAFTS` | 列表 | 5 条演示草稿 | fixture |
| `write_report` / `demo` | 函数 | 跑闭环、打印、写 `outputs/rules_report.json` | 演示 |
| `tests.py` | 测试 | 18 个 `unittest` 测试 | 回归保护 |

数据流：`rules.yml` → `load_yaml` → `Engine`（校验）→ `evaluate(draft)` → `violations()` → `Fixer.apply` → `revised` → `evaluate(revised)` → `diff(draft, revised)` → 打印 + JSON 报告。

---

## 3. 逐段精讲

### 3.1 宪法文件 rules.yml

一条完整的规则（`end-with-runnable-or-assumption`）：

```yaml
  - name: end-with-runnable-or-assumption
    severity: medium
    applies_when:
      contains_regex: '```python'
    must:
      any_of:
        - ends_with_regex: '```\s*$'
        - contains_regex: '\bassumption:'
    explanation: "Code responses must end with a closing fence or an explicit assumption."
    fix:
      append_if_missing: "\n\nAssumption: the example inputs are valid and the module is on the import path."
```

6 条规则总览：

| 规则 | severity | applies_when | must | fix |
|---|---|---|---|---|
| `no-empty-refusal` | medium | 含 `i cannot / i will not / i refuse / unable to help` | 含 `try/consider/alternative/instead/suggest` 或 `redirect` | 追加"consider rephrasing ..." |
| `end-with-runnable-or-assumption` | medium | 含 ` ```python ` | 以 ` ``` ` 结尾，或含 `assumption:` | 追加 "Assumption: ..." |
| `no-pii-in-examples` | high | 含单词 `example / sample` | 不含邮箱、不含电话形状 | 替换为 `[example-contact]` |
| `cite-when-asserting-fact` | low | 某行以 `according to / studies show / research finds` 开头 | 含 `(...)` 括号 | 追加 ` (citation pending)` |
| `no-internal-library-leak` | high | `{}`（恒真） | 不含 `internal-only`、`policybot-internal` | 替换为 `[internal]` |
| `bounded-length` | low | `{}`（恒真） | 词数 ≤ 800 | **无** |

要点：

- 所有正则都写在**单引号**里：YAML 单引号不处理反斜杠转义，`\b`、`\s` 原样传给 Python 的 `re`。fix 文本写在**双引号**里，以便 `\n\n` 变成换行。
- 引擎对所有正则统一加 `re.IGNORECASE | re.DOTALL`，所以 `'\b(i cannot|...)\b'` 能匹配 `I cannot`。
- `cite-when-asserting-fact` 用了行内标志 `(?im)`，`m`（MULTILINE）让 `^` 匹配**每一行**的开头。
- ⚠️ 与讲义的差异：讲义示例里 `contains_regex: 'assumption:'`、fix 文本为 "Assumption: example inputs are valid."；代码中是 `'\bassumption:'` 和更长的句子。讲义说 `no-pii-in-examples` 检查"example data"，实际 `applies_when` 只要文本中出现单词 example/sample（包括邮箱域名 `example.com`）就适用。
- ⚠️ fix 文本 "the **example** inputs ..." 本身含有 `example`，修复后会让 `no-pii-in-examples` 变得适用（测验 Q9）。

### 3.2 数据结构

```python
SEVERITY_ORDER = ("low", "medium", "high")

@dataclass
class RuleResult:
    rule_name: str
    severity: str
    status: str
    explanation: str
    matched_span: str | None = None

@dataclass
class EngineReport:
    text: str
    results: list[RuleResult] = field(default_factory=list)

    def violations(self) -> list[Violation]:
        return [Violation(...) for r in self.results if r.status == "violation"]

    def max_severity(self) -> str | None:
        sevs = [v.severity for v in self.violations()]
        if not sevs:
            return None
        return max(sevs, key=lambda s: SEVERITY_ORDER.index(s))
```

- `RuleResult` 记录**每条**规则的结果（包括 pass 和 not_applicable）；`Violation` 只是违规条目的投影，字段少了 `status`。
- `max_severity()` 没有违规时返回 `None`，而不是第 85 节那样的 `"none"`；第 87 节用 `if post.rules_max_severity:` 来区分。
- `severity` 存在每条结果里，是规则本身的严重度，与"违规的程度"无关。
- ⚠️ 讲义 Key Terms 说 violation 带"matched span"，但 `matched_span` 经常是 `None`：`any_of` 失败时返回最后一个子谓词的 span（多半是 None），`contains_regex` 失败时也没有 span。只有 `not_contains_regex` 失败（即找到了不该出现的东西）和词数超限时才有有意义的 span。
- ⚠️ 讲义说 explanation 是"template"，代码里只是静态字符串，没有任何插值。

### 3.3 _eval_predicate：一个递归的小解释器

```python
def _eval_predicate(node: dict[str, Any] | None, text: str) -> tuple[bool, str | None]:
    if node is None or node == {}:
        return True, None
    if "all_of" in node:
        spans = []
        for child in node["all_of"]:
            ok, span = _eval_predicate(child, text)
            if not ok:
                return False, span
            spans.append(span)
        first = next((s for s in spans if s), None)
        return True, first
    if "any_of" in node:
        last_span = None
        for child in node["any_of"]:
            ok, span = _eval_predicate(child, text)
            if ok:
                return True, span
            last_span = span
        return False, last_span
    if "not_" in node:
        ok, span = _eval_predicate(node["not_"], text)
        return (not ok), span
    if "contains_regex" in node:
        m = re.search(node["contains_regex"], text, flags=re.IGNORECASE | re.DOTALL)
        return (m is not None), (m.group(0) if m else None)
    if "not_contains_regex" in node:
        m = re.search(node["not_contains_regex"], text, flags=re.IGNORECASE | re.DOTALL)
        return (m is None), (m.group(0) if m else None)
    if "ends_with_regex" in node:
        m = re.search(node["ends_with_regex"] + r"\Z", text, flags=re.IGNORECASE | re.DOTALL)
        return (m is not None), (m.group(0) if m else None)
    if "starts_with_regex" in node:
        m = re.match(node["starts_with_regex"], text, flags=re.IGNORECASE | re.DOTALL)
        return (m is not None), (m.group(0) if m else None)
    if "max_words" in node:
        wc = _word_count(text)
        return (wc <= int(node["max_words"])), (f"word count {wc}" if wc > int(node["max_words"]) else None)
    if "min_words" in node:
        ...
    raise ValueError(f"unknown predicate: {list(node.keys())}")
```

- **空谓词恒真**：`None`（字段缺失）或 `{}` 都返回 `True`。`no-internal-library-leak` 的 `applies_when: {}` 就是"对所有文本适用"。
- **all_of**：逐个求值，第一个失败就返回 `(False, 该子项的 span)`；全部成功时返回第一个非空 span。
- **any_of**：第一个成功就返回；全部失败返回最后一个 span。
- **not_**：取反，span 原样透传。
- **`ends_with_regex`**：在模式后拼上 `\Z`（字符串绝对结尾），再用 `re.search`。`'```\s*$' + '\Z'` 表示"以 ``` 加可选空白结尾"。
- **`starts_with_regex`**：用 `re.match`，它只从字符串开头匹配。
- **`not_contains_regex`** 的 span 很有用：违规时 span 就是"不该出现却出现了"的内容，例如 `lee@example.com`、`internal-only`。
- 返回 `(bool, span)` 二元组：既给出判断，也给出证据，方便写进 `Violation.matched_span`。

⚠️ 这个解释器有三个"静默"问题（都已实测）：

| 问题 | 例子 | 结果 |
|---|---|---|
| 一个节点里写多个谓词，只有 if 链中第一个生效 | `{"contains_regex": "a", "max_words": 1}` 对 `"a b c d"` | `(True, 'a')`，`max_words` 被忽略 |
| 短路掩盖拼写错误 | `{"any_of": [{"contains_regex": "a"}, {"contains_regx": "b"}]}` 对 `"a"` | `(True, 'a')`，不报错；只有前面的分支失败时才抛 `ValueError` |
| 讲义只说 any_of 短路 | — | 实际 all_of 也短路 |

另外：正则在每次求值时才编译（`re` 模块内部有缓存，性能问题不大），写错的正则也要到运行时才暴露；`IGNORECASE | DOTALL` 是强加的，规则作者无法要求大小写敏感。

### 3.4 _word_count

```python
def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))
```

- `\w+` 是连续的字母/数字/下划线。`internal-only` 算 2 个词，`don't` 也算 2 个词（实测 `"internal-only don't"` 为 4）。
- 中文没有空格，`\w+` 会把一整段中文当成一个"词"，800 词上限对中文基本失效。

### 3.5 Engine：加载、校验、评估

```python
class Engine:
    def __init__(self, rules: list[dict[str, Any]] | None = None, path: Path | None = None) -> None:
        if rules is not None:
            self._rules = rules
        else:
            target = path or DEFAULT_RULES_PATH
            data = load_yaml(target.read_text())
            if not isinstance(data, dict) or "rules" not in data:
                raise ValueError("constitution must be a mapping with a 'rules' key")
            self._rules = data["rules"]
        for r in self._rules:
            if r.get("severity") not in SEVERITY_ORDER:
                raise ValueError(f"rule {r.get('name')} has bad severity {r.get('severity')}")
            if "name" not in r or "explanation" not in r or "must" not in r:
                raise ValueError(f"rule {r.get('name')} missing required field")
```

- 两种构造方式：直接传规则列表（测试中常用），或从文件加载（默认 `code/rules.yml`）。
- 加载时的校验：顶层必须是带 `rules` 键的映射；每条规则的 severity 必须是 low/medium/high；必须有 `name`、`explanation`、`must`。
- ⚠️ 没有校验的东西：谓词名和结构（Q7 中的拼写错误）、正则能否编译、`name` 是否重复、`fix` 的格式、`data["rules"]` 是否为列表（若为 `None` 会在 `for` 处抛 `TypeError`）。生产中应该用 JSON Schema 或 pydantic 在加载时一次性校验。

```python
    def evaluate(self, text: str) -> EngineReport:
        report = EngineReport(text=text)
        for rule in self._rules:
            ...
            applies, _ = _eval_predicate(rule.get("applies_when"), text)
            if not applies:
                report.results.append(RuleResult(..., status="not_applicable", ...))
                continue
            satisfied, span = _eval_predicate(rule["must"], text)
            if satisfied:
                report.results.append(RuleResult(..., status="pass", ...))
            else:
                report.results.append(RuleResult(..., status="violation", ..., matched_span=span))
        return report
```

- 每条规则都会产生一个 `RuleResult`，`not_applicable` 也被显式记录——讲义的设计意图是让团队"看到引擎确实评估过这条规则"。
- ⚠️ 讲义说报告中会显示 `not_applicable`，但 `demo()` 写进 `rules_report.json` 的只有 `draft_violations` 和 `revised_violations`，**`not_applicable` 状态不会出现在报告文件里**；只有在内存中的 `report.results` 里能看到（`tests.py` 的 `test_not_applicable_reported` 就是这么检查的）。
- `rules()` 返回 `list(self._rules)`：浅拷贝，调用方增删列表不影响引擎，但修改其中的字典仍会影响。

### 3.6 Fixer：确定性的局部修复

```python
class Fixer:
    def __init__(self, rules: list[dict[str, Any]]) -> None:
        self._by_name = {str(r["name"]): r for r in rules if "fix" in r}

    def apply(self, text: str, violations: list[Violation]) -> str:
        out = text
        for v in violations:
            spec = self._by_name.get(v.rule_name)
            if not spec:
                continue
            fix = spec.get("fix")
            if not isinstance(fix, dict):
                continue
            if "append_if_missing" in fix:
                suffix = str(fix["append_if_missing"])
                if suffix.strip() and suffix.strip() not in out:
                    out = out.rstrip() + suffix
            elif "prepend_if_missing" in fix:
                prefix = str(fix["prepend_if_missing"])
                if prefix.strip() and prefix.strip() not in out:
                    out = prefix + out.lstrip()
            elif "replace_regex" in fix:
                rr = fix["replace_regex"]
                out = re.sub(str(rr["pattern"]), str(rr["replacement"]), out, flags=re.IGNORECASE)
        return out
```

- 用字典推导式按规则名建索引，只收录有 `fix` 的规则；`bounded-length` 没有 fix，违规后修订稿保持不变，第二遍仍然违规（实测 850 个 `word` 时 `post viol: bounded-length`）。
- 修复按**违规顺序**（即规则在文件中的顺序）依次作用，前一次修复的结果是后一次的输入。
- `append_if_missing`：先 `rstrip()` 去掉原文末尾空白再追加，避免出现多余空行；"if missing" 用 `suffix.strip() not in out` 判断，防止重复追加。
- `prepend_if_missing`：`rules.yml` 中没有规则用到它，测试也没有覆盖。
- `replace_regex`：全局替换，强制 `IGNORECASE`。`no-internal-library-leak` 把 `policybot-internal` 和 `INTERNAL-ONLY` 都换成 `[internal]`。
- 每条规则只能有一种修复（`if / elif` 链），写了多种时只有第一种生效。
- ⚠️ fixer 只看"违规的那条规则"，不考虑对其他规则的影响：给代码回复追加的 "Assumption: the example inputs ..." 会让 `no-pii-in-examples` 变得适用；若代码里有电话形状的常量，第二遍就出现 high 违规（测验 Q9）。
- ⚠️ `cite-when-asserting-fact` 的修复把 ` (citation pending)` 追加到**全文末尾**，而不是 `According to` 那一行，而且只是满足正则，并不是真正的引用（测验 Q11）。

### 3.7 diff：按行的结构化变更

```python
def diff(draft: str, revised: str) -> list[Change]:
    draft_lines = draft.splitlines()
    revised_lines = revised.splitlines()
    sm = difflib.SequenceMatcher(a=draft_lines, b=revised_lines)
    out: list[Change] = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            continue
        if op == "delete":
            for line in draft_lines[a1:a2]:
                out.append(Change(op="remove", text=line))
        elif op == "insert":
            for line in revised_lines[b1:b2]:
                out.append(Change(op="add", text=line))
        elif op == "replace":
            for line in draft_lines[a1:a2]:
                out.append(Change(op="edit-removed", text=line))
            for line in revised_lines[b1:b2]:
                out.append(Change(op="edit-added", text=line))
    return out
```

- `SequenceMatcher` 把两个**行列表**当作序列比较，`get_opcodes()` 返回五元组 `(tag, a1, a2, b1, b2)`，表示"把 `a[a1:a2]` 变成 `b[b1:b2]`"，tag 为 `equal / delete / insert / replace`。
- 映射：`delete → remove`、`insert → add`、`replace → edit-removed + edit-added`。讲义说 op 有 "add, remove, edit"，代码把 edit 拆成两种。
- 追加 `"\n\n..."` 会产生两条 `add`（一个空行、一行文本）；修改一行会产生 `edit-removed` + `edit-added`。所以 demo 打印的 `fixer applied 2 change(s)` 统计的是 **diff 条目数**，不是修复次数。
- 粒度是**行**：只改了一个词，整行都会作为 `edit-removed` / `edit-added` 出现。被替换掉的敏感原文（如 `lee@example.com`）也会出现在 `edit-removed` 里，写日志时要注意。
- `splitlines()` 会忽略末尾换行的差异。

### 3.8 demo 与报告

```python
def demo() -> int:
    engine = Engine()
    fixer = Fixer(engine.rules())
    ...
    for fixture in _DEMO_DRAFTS:
        draft = fixture["draft"]
        report = engine.evaluate(draft)
        violations = report.violations()
        revised = fixer.apply(draft, violations)
        report2 = engine.evaluate(revised)
        post_violations = report2.violations()
        change_list = diff(draft, revised)
        ...
        if change_list:
            print(f"    fixer applied {len(change_list)} change(s)")
        if post_violations:
            print(f"    revised still has {len(post_violations)} violation(s)")
        payload["cases"].append({... "draft_violations": [asdict(v) for v in violations], ...})
    path = write_report(payload)
```

- 每条草稿走完整闭环：评估 → 修复 → 复检 → diff。
- 第二遍仍有违规时**只打印一行**，没有再修一轮、没有升级、也没有拒答；讲义流程图中的 "accepted or escalated" 没有实现。
- ⚠️ 讲义说 demo "runs three draft responses"，实际是 5 条；说"One fixture has a non-applicable rule ... the report shows `not_applicable`"，但报告文件里没有 `not_applicable`（见 3.5）。
- `write_report` 每次覆盖 `outputs/rules_report.json`，内容是确定的（重跑逐字节相同）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 规则写在 YAML 中 | 非工程师可读、可评审、可版本化 | 解析器差异、缩进错误；生产用 `safe_load` + schema 校验 |
| 用"字典里有哪个键"决定谓词类型 | DSL 简洁 | 多个键只生效一个且不报错；应在加载时校验"每个节点恰好一个谓词" |
| `applies_when` + `must` 两段式 | 区分"不适用"与"通过"，便于统计 | 关键词式 applies_when 有误报（`I cannot recommend ...`）和漏报（`I can't`） |
| 全局 `IGNORECASE \| DOTALL` | 规则作者不用操心大小写 | 无法写大小写敏感的规则 |
| 短路求值 | 快 | 掩盖后面分支中的错误 |
| 确定性 fixer | 可复现、可审计、零成本 | 只能局部编辑；会引入新违规；结构性修复需要 LLM 或人工 |
| 修复后复检 | 验证修复有效 | 没有迭代和升级逻辑；应迭代到不动点并在 high 未消除时拒答 |
| 行级 diff | 标准库现成、易读 | 粒度粗；diff 中包含被移除的敏感原文 |
| `max_severity()` 返回 None | 与"无违规"语义一致 | 与第 85 节的 `"none"` 不统一，下游需要分别处理 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 与默认值 | `matched_span: str \| None = None`、`results: list[RuleResult] = field(default_factory=list)` | 有默认值的字段必须放在没有默认值的字段之后 |
| dataclass 中定义方法 | `EngineReport.violations()`、`max_severity()` | dataclass 也是普通类，可以有方法 |
| 联合类型 `X \| None` | `def max_severity(self) -> str \| None` | 可能返回 None |
| 元组返回类型 | `-> tuple[bool, str \| None]` | 同时返回结果和证据 |
| 递归函数 | `_eval_predicate` 调用自身处理子节点 | 树形结构的自然解法 |
| `next(生成器, 默认值)` | `next((s for s in spans if s), None)` | 取第一个满足条件的元素，没有就返回默认值 |
| 条件表达式 | `m.group(0) if m else None` | 一行 if/else |
| `re.search` vs `re.match` | `contains_regex` 用 search，`starts_with_regex` 用 match | search 在任意位置找，match 只从开头匹配 |
| 正则标志按位或 | `flags=re.IGNORECASE \| re.DOTALL` | 组合多个标志；`DOTALL` 让 `.` 匹配换行 |
| 行内正则标志 | `'(?im)^(according to\|...)\b'` | 写在模式开头，`m` 是 MULTILINE |
| `\Z` 锚点 | `node["ends_with_regex"] + r"\Z"` | 字符串绝对结尾（`$` 还能匹配末尾换行之前） |
| `dict.get` | `rule.get("applies_when")`、`self._by_name.get(v.rule_name)` | 键不存在返回 None，不抛 KeyError |
| 字典推导式带过滤 | `{str(r["name"]): r for r in rules if "fix" in r}` | 一步建索引 |
| `isinstance` | `isinstance(data, dict)`、`isinstance(fix, dict)` | 运行时类型检查 |
| `if / elif` 链 | Fixer 的三种修复 | 只执行第一个满足的分支 |
| `str.rstrip()` / `lstrip()` | `out.rstrip() + suffix` | 去掉末尾/开头空白 |
| `difflib.SequenceMatcher` | `sm.get_opcodes()` | 标准库序列比较 |
| 五元组解包 | `for op, a1, a2, b1, b2 in sm.get_opcodes()` | 循环中直接拆开 |
| `with self.assertRaises(...)` | tests.py | 断言代码块会抛出指定异常 |
| f-string 宽度 | `[{v.severity:6}]` | 填充到 6 个字符，打印出 `[high  ]` |
| `Path.read_text` / `write_text` | `target.read_text()` | 一行读写文本文件 |
| `sys.exit(demo())` 与 `__main__` | 文件末尾 | 被第 87 节 import 时不会运行 demo |

---

## 6. 运行结果解读

实际运行（Python 3.13；在本节目录的副本中执行，避免覆盖仓库文件；有 PyYAML 与屏蔽 PyYAML 两种情况下，生成的 `rules_report.json` 都与仓库中的文件逐字节相同）：

```text
Constitutional rules engine demo

  rules loaded: 6

  case: refusal-without-redirect
    violations on draft: 1  max severity: medium
      [medium] no-empty-refusal: Refusals must offer a next step (a suggestion, an alternative, or a redirect).
    fixer applied 2 change(s)

  case: code-without-assumption
    violations on draft: 1  max severity: medium
      [medium] end-with-runnable-or-assumption: Code responses must end with a closing fence or an explicit assumption.
    fixer applied 2 change(s)

  case: pii-in-example
    violations on draft: 1  max severity: high
      [high  ] no-pii-in-examples: Examples must not contain real-looking emails or phone numbers.
    fixer applied 2 change(s)

  case: internal-library-leak
    violations on draft: 1  max severity: high
      [high  ] no-internal-library-leak: Internal library names must not appear in outputs.
    fixer applied 2 change(s)

  case: clean-response
    draft passes all applicable rules

  artifact written to .../outputs/rules_report.json
```

逐项解读：

| 用例 | 违规 | 修订稿 | diff |
|---|---|---|---|
| refusal-without-redirect | `no-empty-refusal`（span None） | 追加"If this is something I cannot help with, consider rephrasing ..." | `add ""`、`add "If this ..."` |
| code-without-assumption | `end-with-runnable-or-assumption`：最后一行是 `Let me know if this works.`，不以 ``` 结尾 | 追加 "Assumption: the example inputs ..." | 两条 `add` |
| pii-in-example | `no-pii-in-examples`，span `lee@example.com` | `Example user: [example-contact]. ...` | `edit-removed` + `edit-added` |
| internal-library-leak | `no-internal-library-leak`，span `internal-only` | `Use the [internal] adapter ...` | `edit-removed` + `edit-added` |
| clean-response | 无 | 不变 | 空 |

- 4 条有违规的用例在第二遍全部清零，所以没有打印 "revised still has ..."。
- "fixer applied 2 change(s)" 四次都是 2：两种修复方式恰好都产生 2 条 diff 记录，与修复次数（每次 1 次）无关。
- 修订后的拒答句子里仍然有 `I cannot`，规则仍适用，但因为加了 `consider`，`must` 满足 → pass。
- `pii-in-example` 的修订稿仍包含 `Example`，规则仍适用，但已无邮箱 → pass。

另外几组边界实测（测验中使用）：

```text
"I can't help with that."                                → 无违规（applies_when 不匹配 can't）
"I cannot recommend this library highly enough."          → no-empty-refusal 违规，并被追加一段无关的"下一步"
"Contact me at lee@example.com for details."              → no-pii-in-examples high（域名里的 example 触发规则）
"Contact me at lee@corp.com for details."                 → 无违规
代码中含 PHONE = '555-123-4567' 的回复                     → 第一遍 medium，修复后第二遍出现 no-pii-in-examples high
"word " * 850                                             → bounded-length low，无 fix，第二遍仍违规
```

---

## 7. 动手改一改

1. **讲义练习 1**：新增规则"当 prompt 提到 safety 时，回复必须包含 'If this is urgent'"。你会发现 `evaluate(text)` 只接收回复文本，看不到 prompt。把签名改成 `evaluate(text, context=None)`，增加原子谓词 `prompt_contains_regex`，并用 `all_of` 组合。
2. **加载时校验**：在 `Engine.__init__` 中递归检查每个谓词节点"恰好有一个已知键"、正则能编译、规则名不重复；为 `{"contains_regex": "a", "max_words": 1}` 和拼写错误的 `contains_regx` 各写一个应抛 `ValueError` 的测试。
3. **修复闭环**：把 demo 中的"修复 + 复检"改成最多 3 轮的迭代，修复无变化时停止，最终 high 仍存在则返回拒答文本并标记 `escalated`（参考测验 Q9 的代码）；用含 `PHONE = '555-123-4567'` 的代码回复验证。
4. **讲义练习 3**：实现 `violation_rates(engine, corpus)`，同时给出"违规/总数"和"违规/适用"两种口径（参考测验 Q12 的结果表）。
5. **讲义练习 2：模板化 fixer**：新增 `template` 修复类型，例如 `{"template": "{text}\n\nNext step: {suggestion}", "slots": {"suggestion": "..."}}`，用它重写 `no-empty-refusal` 的修复。
6. **进阶：报告里写出 `not_applicable`**：让 `rules_report.json` 为每个用例记录全部 `RuleResult`，兑现讲义"the report shows `not_applicable`"的说法；再把 diff 条目中 `edit-removed` 的原文做脱敏。

---

## 8. 常见坑

- **一个映射写两个谓词**：只有一个生效，应写成 `all_of: [...]`。
- **谓词名拼错**：可能因为短路永远不报错，加载时也不报错。
- **正则写在 YAML 双引号里**：反斜杠会被当作转义（PyYAML 对 `"\d"` 直接报错）；正则一律用单引号。
- **`applies_when` 用关键词近似意图**：`example` 会匹配到 `example.com`，`I cannot` 会匹配到 `I cannot recommend`，`can't` 却漏掉。
- **fix 文本触发其他规则**：修复后必须复检，并且要能处理"越修越糟"。
- **把 diff 条目数当成修复次数**：一次追加可能产生两条 `add`。
- **以为 `max_severity()` 返回 `"none"`**：没有违规时返回 `None`。
- **在 `code/` 以外运行**：`from yaml_subset import load_yaml` 与默认规则路径都依赖本目录。
- **以为测试覆盖了手写 YAML 解析器**：装了 PyYAML 就不会走 `_parse`（见 [yaml_subset.讲解.md](yaml_subset.讲解.md)）。

---

## 9. 测试在验证什么

运行方式（在 `code/` 目录下）：

```bash
python3 -m unittest tests -v
# 或
python3 -m pytest -q tests.py
```

实际结果：`Ran 18 tests in 0.063s — OK`；pytest `18 passed in 0.05s`。用 import 钩子屏蔽 PyYAML 后再跑，同样 18 个全部通过。

| 测试类 | 测试 | 验证的性质 |
|---|---|---|
| `TestYamlSubset` | `test_simple_mapping` | `name: alice\nage: 30` → `{"name": "alice", "age": 30}`，整数类型推断 |
| | `test_nested_mapping` | 两层嵌套映射 |
| | `test_sequence_of_mappings` | `- id: 1\n    label: a` 形式的序列项映射 |
| | `test_quoted_string` | 单引号字符串去引号 |
| | `test_strips_comments` | 整行注释与行尾注释都被去掉 |
| `TestEngineLoad` | `test_default_constitution_loads` | 默认 `rules.yml` 能加载且至少 5 条规则（实际 6 条） |
| | `test_bad_severity_rejected` | severity 为 `critical` 时抛 `ValueError` |
| | `test_missing_required_field_rejected` | 缺 `must` / `explanation` 时抛 `ValueError` |
| `TestPredicates` | `test_empty_refusal_flagged` | `I cannot help with that.` 违反 `no-empty-refusal` |
| | `test_clean_response_passes` | 俳句文本没有违规 |
| | `test_internal_library_leak_flagged` | `internal-only` 被发现 |
| | `test_long_response_flagged` | 850 个词违反 `bounded-length` |
| | `test_not_applicable_reported` | 不含拒答词时 `no-empty-refusal` 的状态是 `not_applicable` |
| `TestFixer` | `test_refusal_redirect_appended` | 修复后第二遍不再有 `no-empty-refusal` 违规（验证"修复 + 复检"闭环） |
| | `test_internal_replaced` | 修订稿中不再含 `internal-only` |
| `TestDiff` | `test_add_change_recorded` | 新增一行 → 一条 `add "gamma"` |
| | `test_no_change_for_identical` | 相同文本 → 空列表 |
| | `test_edit_replaces_lines` | 修改一行 → 同时有 `edit-removed` 和 `edit-added` |

值得注意：

- **`TestYamlSubset` 实际测的是 PyYAML**：测试调用 `load_yaml`，装了 PyYAML 时 `_parse` 一行都不执行。讲义说"the lesson tests parse by both code paths"，并不成立。要真正覆盖手写解析器，需要直接调用 `_parse`，或像我们一样用 import 钩子屏蔽 PyYAML。
- `test_missing_required_field_rejected` 只检查"缺字段会报错"，不区分是缺了哪个字段。
- `TestPredicates` 每个测试都通过 `setUp` 重新加载规则文件，测试之间互不影响。

**测试没有覆盖的地方**：

- `end-with-runnable-or-assumption`、`no-pii-in-examples`、`cite-when-asserting-fact` 三条规则的违规与修复；
- `prepend_if_missing` 修复、`starts_with_regex`、`min_words` 谓词、`not_` 组合；
- 修复引入新违规（测验 Q9）、多谓词节点只生效一个、短路掩盖拼写错误；
- `applies_when` 的误报与漏报（`I can't`、`I cannot recommend`、`example.com`）；
- YAML 子集之外的写法（同缩进序列、Unicode、Tab 缩进）；
- `diff` 中的 `remove` 分支，以及 `write_report` 的输出结构。

建议把测验 Q3–Q5、Q9 中的反例补成测试，先用 `@unittest.expectedFailure` 标记已知缺陷，修复后再改为正常断言。
