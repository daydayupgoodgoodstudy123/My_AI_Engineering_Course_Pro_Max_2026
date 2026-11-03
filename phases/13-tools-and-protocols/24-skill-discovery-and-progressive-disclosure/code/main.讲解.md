# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 24 节 Skill Discovery（技能发现）与 Progressive Disclosure（渐进披露） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）；测试 `python3 -m unittest discover -s code/tests -v` ｜ **依赖**：仅标准库（`json`、`re`、`tempfile`、`dataclasses`、`pathlib`、`typing`），无需网络

---

## 1. 这份代码在考察什么

这份代码实现了一个**确定性的技能发现与披露引擎**，对应讲义的两条主线：

1. **发现（discovery）**：在宿主声明的多个 scope 根目录下，只看直接子目录、只读 frontmatter，校验身份字段；按宿主给出的优先级解决同名冲突；在条目数、描述长度、序列化字符数三重预算下发布模型可见的目录。
2. **披露（disclosure）**：选中后才加载 `SKILL.md` body（Level 2）；只有经过路径校验的包内文件才能作为 reference 读取（Level 3），并受大小上限约束。

它把讲义的几个关键主张落成代码：

- "Discovery is a compiler pipeline"：候选 → 校验 → 冲突 → 预算 → 目录，每步都有明确的数据结构；
- "Scope is runtime policy"：优先级是调用方传入的元组，不从目录名推断；
- "Catalog budget and active context are different budgets"：`catalog_chars` 只算目录，body 与 reference 另有上限；
- "Resource paths are a trust boundary"：拒绝绝对路径、`..`、反斜杠、symlink、深层链。

> 一句话：**让"200 个技能里模型能看到什么、看到多少、选中后又能读到什么"变成可复现、可审计的规则。** 同时要注意它在"结构化失败"上做得不够——一个坏包会让整个 scope 失败。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `FRONTMATTER_LIMIT` / `NAME_PATTERN` | 常量 | frontmatter 最多读 8,192 字节；kebab-case 名称正则 | 有界读取、命名规则 |
| `Scope` | 冻结 dataclass | scope 名 + 根目录 | 安装位置 |
| `SkillCandidate` | 冻结 dataclass | 已读 frontmatter、尚未进入目录的候选 | 候选 |
| `CatalogBudget` | 冻结 dataclass | `max_entries=50`、`max_description_chars=240`、`max_catalog_chars=8_000` | 目录预算 |
| `CatalogEntry` | 冻结 dataclass | 模型可见的一条：name、description、scope、directory | Level 1 |
| `Collision` | 冻结 dataclass | 同名冲突的胜者与被遮蔽者 | 冲突诊断 |
| `Catalog` | 冻结 dataclass | entries、collisions、omitted、`catalog_chars`、`report_chars`；`model_dict()` / `to_dict()` | 目录与诊断报告 |
| `DiscoveryError` / `CollisionError` / `ReferencePathError` | 异常类 | 三类失败 | 结构化失败 |
| `_frontmatter` | 私有函数 | 流式读取 frontmatter（不读 body），解析小 YAML 子集 | 只读元数据 |
| `discover_scope` | 函数 | 枚举直接子目录、校验、生成候选 | 浅层发现 |
| `resolve_collisions` | 函数 | 按优先级选胜者，同级重复报错 | 冲突策略 |
| `_shorten` | 私有函数 | 截断描述并加 `…` | 描述预算 |
| `build_catalog` | 函数 | 冲突 → 排序 → 条目数截断 → 字符预算淘汰 → 报告长度不动点 | 目录发布 |
| `_candidate_for` | 私有函数 | 由目录条目找回候选 | 身份映射 |
| `load_skill_body` | 函数 | 读取 body，限制字符数 | Level 2 |
| `validate_reference` | 函数 | 引用路径的包内约束 | 路径信任边界 |
| `load_reference` | 函数 | 校验后读取 reference，限制字符数 | Level 3 |
| `_write_skill` / `demo` | 函数 | 在临时目录造三个技能并演示全流程 | 演示 |

数据流：`demo` 在临时目录建 project / user 两个 scope → `discover_scope` ×2 → `build_catalog`（内部 `resolve_collisions`、`_shorten`、预算淘汰）→ 取 `evidence-report` 条目 → `load_skill_body`（Level 2）→ `load_reference("references/format.md")`（Level 3）→ 打印目录诊断与三级字符数。

---

## 3. 逐段精讲

### 3.1 数据结构：候选、条目、报告

```python
@dataclass(frozen=True)
class CatalogBudget:
    max_entries: int = 50
    max_description_chars: int = 240
    max_catalog_chars: int = 8_000


@dataclass(frozen=True)
class Catalog:
    entries: tuple[CatalogEntry, ...]
    collisions: tuple[Collision, ...]
    omitted: tuple[str, ...]
    catalog_chars: int
    report_chars: int

    def model_dict(self) -> dict[str, object]:
        return {"entries": [asdict(entry) for entry in self.entries]}

    def to_dict(self) -> dict[str, object]:
        return {"entries": ..., "collisions": ..., "omitted": ..., "catalog_chars": ..., "report_chars": ...}
```

- **两个视图**：`model_dict()` 是"发给模型的"，只有 entries；`to_dict()` 是"给人和日志的"，额外包含 collisions、omitted 和两个长度。这正是讲义"Preserve the rejected or shadowed candidates in diagnostics even when they are absent from the model catalog"。
- `SkillCandidate` 保存 `directory` 与 `skill_path` 两个 `Path`；`CatalogEntry.directory` 是字符串（便于 JSON 序列化）。
- `max_catalog_chars=8_000` 的默认值对应讲义所说 Codex 在上下文窗口未知时的回退值——这是对某个宿主策略的模仿，不是标准。
- ⚠️ `CatalogEntry` 里带**绝对目录路径**，它也会进入模型目录并占用预算（demo 中每条约 45 字符的路径）。讲义"Discovery is a compiler pipeline"一节说"Do not publish raw paths directly to the model"，而讲义的条目示例里又有 `"source"` 字段；比较稳妥的理解是 source 属于内部身份，模型可见部分可以只放 name、description（必要时加 scope）。

### 3.2 `_frontmatter`：只读元数据、有界读取

```python
def _frontmatter(path: Path) -> dict[str, str]:
    lines: list[str] = []
    consumed = 0
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            consumed += len(raw_line.encode("utf-8"))
            if consumed > FRONTMATTER_LIMIT:
                raise DiscoveryError(f"frontmatter window exceeded for {path}")
            lines.append(raw_line.rstrip("\r\n"))
            if len(lines) > 1 and lines[-1] == "---":
                break
    if not lines or lines[0] != "---" or lines[-1] != "---":
        raise DiscoveryError(f"invalid frontmatter delimiters in {path}")
```

- **逐行流式读取**，遇到第二个 `---` 立刻停止：body 一个字节都不读——这就是 `discover_scope` docstring 说的"instruction bodies stay unloaded"。
- 按 **UTF-8 字节**累计（不是字符），超过 8,192 字节就拒绝：防止有人把一个巨大文件伪装成技能拖慢发现。
- `rstrip("\r\n")` 兼容 Windows 换行。
- 之后的解析逻辑与第 22 节 `parse_frontmatter` 基本一致（顶层行必须含冒号、字段名正则、重复字段报错、`>`/`|` 块标量），差异：

| 差异 | 第 22 节 | 本节 |
|---|---|---|
| 失败类型 | `FrontmatterSyntaxError` → issue | `DiscoveryError`（直接抛出） |
| 标量解码 | `_decode_scalar`（JSON 双引号、`''` 转义、拒绝 `[{&*!`） | `value.strip("\"'")`，更宽松 |
| `metadata` 嵌套键 | 不校验键名 | 键名也要匹配 `[A-Za-z][A-Za-z0-9-]*` 且不得重复 |
| `metadata` 的存储 | 字典 | `json.dumps(nested, sort_keys=True)` 字符串（让返回类型统一为 `dict[str, str]`） |
| 必填检查 | 由 `validate_skill_text` 生成 issue | 缺 name 或 description 直接抛错 |

- ⚠️ `strip("\"'")` 会同时剥掉两种引号，`'abc"` 也会变成 `abc`；`>-` 等 chomping 指示符同样不支持（与第 22 节相同）。讲义"Why the lab does not parse arbitrary YAML"明确承认这是教学约束，生产要用安全 YAML 解析器 + schema。

### 3.3 `discover_scope`：浅层发现

```python
def discover_scope(scope: Scope) -> tuple[SkillCandidate, ...]:
    """Read only direct child frontmatter; instruction bodies stay unloaded."""
    if not scope.root.exists():
        return ()
    candidates: list[SkillCandidate] = []
    for directory in sorted(scope.root.iterdir(), key=lambda item: item.name):
        skill_path = directory / "SKILL.md"
        if not directory.is_dir() or directory.is_symlink():
            continue
        if skill_path.is_symlink():
            raise DiscoveryError(f"symlinked SKILL.md is not allowed: {skill_path}")
        if not skill_path.is_file():
            continue
        fields = _frontmatter(skill_path)
        if len(fields["name"]) > 64 or not NAME_PATTERN.fullmatch(fields["name"]):
            raise DiscoveryError(...)
        if len(fields["description"]) > 1024:
            raise DiscoveryError(...)
        if fields["name"] != directory.name:
            raise DiscoveryError(...)
        candidates.append(SkillCandidate(..., directory=directory.resolve(), skill_path=skill_path.resolve()))
    return tuple(candidates)
```

- **不存在的根**返回空元组而不是报错：未配置的 scope（如没有 user 目录）是正常情况。
- `sorted(..., key=lambda item: item.name)`：`iterdir()` 的顺序依赖文件系统，排序后结果确定。
- **只看直接子目录**：讲义 "Why discovery is shallow"——保持包边界，避免把已安装技能内部的示例、夹具里的 `SKILL.md` 当成独立技能。
- **symlink 策略**：symlink 目录被**静默跳过**；真实目录里的 symlink `SKILL.md` 则**报错**。两种处理不一致，且前者不留痕（讲义："State whether symlinked packages are allowed"——拒绝也应可见）。讲义也提到 Codex 支持 symlink 技能目录，所以这是本实验宿主的选择。
- ⚠️ **fail-fast**：任何一个包出问题都 `raise`，整个 scope 的候选全部丢失（实测：一个目录名为 `Bad`、`name: bad` 的包让同目录的 `alpha`、`zeta` 都发现不了）。这与讲义"Each stage should produce structured data and structured failures… Which candidates were rejected, and why?"不符；随包脚本 `outputs/skill-catalog-builder/scripts/build_catalog.py` 采用的是收集 `errors` 并继续的方式（测验 Q10 给出改造）。

### 3.4 `resolve_collisions`：显式优先级 + 同级报错

```python
    rank = {scope: index for index, scope in enumerate(precedence)}
    grouped: dict[str, list[SkillCandidate]] = {}
    for candidate in candidates:
        if candidate.scope not in rank:
            raise CollisionError(f"scope {candidate.scope!r} is missing from host policy")
        grouped.setdefault(candidate.name, []).append(candidate)

    for name in sorted(grouped):
        options = sorted(
            grouped[name], key=lambda item: (rank[item.scope], str(item.directory))
        )
        top_rank = rank[options[0].scope]
        tied = [option for option in options if rank[option.scope] == top_rank]
        if len(tied) > 1:
            raise CollisionError(f"ambiguous {name!r} at equal precedence: {paths}")
        winners.append(options[0])
        if len(options) > 1:
            collisions.append(Collision(name=name, winner_scope=options[0].scope,
                                        shadowed_scopes=tuple(o.scope for o in options[1:])))
```

- `precedence` 是**从高到低**的 scope 元组，`enumerate` 把它变成 rank（0 最高）。测试 `test_precedence_is_policy_not_fixed_standard` 证明把元组反过来，胜者也随之改变——优先级是策略，不是标准。
- 候选的 scope 不在策略里 → 报错，而不是给一个默认 rank。
- `setdefault` 按名字分组；排序键里的 `str(item.directory)` 只是让顺序与错误信息稳定，**不**用来打破平局——同 rank 的重复直接 `CollisionError`，对应随包 SKILL.md："Never choose an equal-precedence duplicate by incidental filesystem order."
- 只检查**最高 rank** 的平局；如果两个低优先级候选同名同级，但已被更高优先级的候选遮蔽，就不会报错（它们都进 `shadowed_scopes`）。
- 采用的是讲义四种策略中的"Highest-precedence scope wins"（同级时退化为"Reject duplicates"）。

### 3.5 `_shorten` 与 `build_catalog`：三重预算

```python
def _shorten(text: str, limit: int) -> str:
    if limit < 1:
        return ""
    if len(text) <= limit:
        return text
    if limit == 1:
        return "…"
    return text[: limit - 1].rstrip() + "…"
```

- 结果长度 ≤ `limit`：留一个字符给省略号 `…`（U+2026，单个字符）。`rstrip()` 去掉截断处的尾随空格，所以结果可能比 `limit` 短（实测 `_shorten("Use for reports.", 5) == "Use…"`，4 个字符）。

```python
    winners, collisions = resolve_collisions(candidates, precedence)
    rank = {scope: index for index, scope in enumerate(precedence)}
    ordered = sorted(winners, key=lambda item: (rank[item.scope], item.name))
    entries = [CatalogEntry(..., description=_shorten(candidate.description, budget.max_description_chars), ...)
               for candidate in ordered[: budget.max_entries]]
    omitted = [candidate.name for candidate in ordered[budget.max_entries :]]

    def model_size(current_entries: list[CatalogEntry]) -> int:
        payload = {"entries": [asdict(entry) for entry in current_entries]}
        return len(json.dumps(payload, sort_keys=True, separators=(",", ":")))

    used = model_size(entries)
    while used > budget.max_catalog_chars and entries:
        removed = entries.pop()
        omitted.insert(0, removed.name)
        used = model_size(entries)
    if used > budget.max_catalog_chars:
        raise ValueError("model-facing catalog exceeds max_catalog_chars")
```

预算按三层依次施加：

1. **描述长度**：每条描述截到 `max_description_chars`；
2. **条目数**：按 `(scope rank, name)` 排序后取前 `max_entries`，其余进 `omitted`；
3. **序列化字符数**：精确测量**发给模型的那份 JSON**（`sort_keys=True` + 紧凑分隔符），超了就从**末尾**弹出，直到放得下。被弹出的名字 `insert(0, ...)` 插到 `omitted` 前面，保持 `omitted` 整体按原顺序。

细节：

- 空目录 `{"entries":[]}` 本身占 14 个字符，因此 `max_catalog_chars < 14` 时即使全部淘汰也放不下，抛 `ValueError`。
- 淘汰规则是"固定顺序、从尾部删"：低优先级 scope 与字母序靠后的技能先被省略——确定且可审计，但与任务相关性无关。超预算时不会进一步缩短描述，而是直接省略整条。
- ⚠️ `json.dumps` 默认 `ensure_ascii=True`，非 ASCII 字符被转义为 `\uXXXX`（6 个字符）。实测 18 个汉字的描述在序列化中占 110 个字符（`ensure_ascii=False` 时为 20）。中文描述的技能在预算里被放大约 6 倍。
- 函数开头 `min(...) < 1` 拒绝非正预算。

最后一段计算报告自身的长度：

```python
    report_chars = 0
    while True:
        report = Catalog(tuple(entries), collisions, tuple(omitted), used, report_chars)
        measured = len(json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":")))
        if measured == report_chars:
            return report
        report_chars = measured
```

- 报告里包含 `report_chars` 字段，而这个字段的数字位数又影响报告长度——这是一个**自引用**问题，代码用"不动点迭代"解决：先假设 0，测出长度 L1，再把 L1 填进去重测……直到测量值等于填入值。因为长度只随数字位数单调增长，迭代很快收敛（通常两三轮）。
- 测试 `test_catalog_budget_covers_exact_model_facing_entries` 断言 `catalog_chars` 与 `report_chars` 都与真实序列化长度**完全相等**。
- 测试 `test_diagnostics_do_not_evict_model_visible_entries` 证明：增加 user scope 的同名候选只会让诊断报告变长（collisions 增加），**不会**挤占模型可见目录——两种预算被正确分开。

### 3.6 `load_skill_body`：Level 2 激活

```python
def load_skill_body(entry, candidates, max_chars: int = 12_000) -> str:
    candidate = _candidate_for(entry, candidates)
    text = candidate.skill_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    end = lines.index("---", 1)
    body = "\n".join(lines[end + 1 :]).strip()
    if len(body) > max_chars:
        raise DiscoveryError(f"skill body exceeds {max_chars} characters")
    return body
```

- `_candidate_for` 要求 name **和** directory 都匹配，避免同名不同来源的技能被混淆。
- 只有在选中之后才调用，与目录构建分离（测试 `test_body_load_is_separate_from_catalog_construction` 验证目录里没有 body 的标记文本）。
- ⚠️ 这里用 `read_text` 读入**整个文件**再判断长度；没有复用 `_frontmatter` 的字节上限；也没有校验文件在发现之后是否被修改（无哈希）。讲义建议记录 `skill.resource.loaded` 一类的加载事件，本实现没有记录。

### 3.7 `validate_reference`：路径信任边界

```python
def validate_reference(skill_directory: Path, reference: str) -> Path:
    """Allow a direct file or one subdirectory, never traversal or deep chains."""
    if not isinstance(reference, str):
        raise ReferencePathError("reference must be a string")
    if "\\" in reference:
        raise ReferencePathError("references must use portable forward slashes")
    relative = PurePosixPath(reference)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ReferencePathError("reference must be a clean relative path")
    if len(relative.parts) > 2:
        raise ReferencePathError("reference may be at most one directory deep")
    root = skill_directory.resolve()
    unresolved = root
    for part in relative.parts:
        unresolved = unresolved / part
        if unresolved.is_symlink():
            raise ReferencePathError("reference path cannot contain symlinks")
    target = unresolved.resolve()
    if target == root or root not in target.parents:
        raise ReferencePathError("reference escapes the skill directory")
    if not target.is_file():
        raise ReferencePathError("reference must resolve to a regular file")
    return target
```

逐层防御：

| 检查 | 拦住什么 |
|---|---|
| `isinstance(reference, str)` | `None`、数字、列表等（测试 `test_rejects_non_string_reference_with_domain_error`），统一抛领域异常而不是 `TypeError` |
| 反斜杠 | Windows 风格路径、`..\\` 穿越 |
| `PurePosixPath` + `is_absolute` + `..` | `/etc/passwd`、`../secret.md`、`references/../SKILL.md` |
| `len(parts) > 2` | `references/archive/format.md` 这类深层链（讲义"keep the reference graph shallow"） |
| 逐段 `is_symlink()` | 包内 symlink，**即使指向包内**也拒绝（测试 `test_rejects_internal_symlink_reference`） |
| `resolve()` + `root in target.parents` | 用文件系统语义确认在包根之内——讲义"Literal string-prefix checks are not enough" |
| `is_file()` | 目录、不存在的文件 |

- `PurePosixPath` 在构造时会规范化：`"references/./format.md"` 与 `"references//format.md"` 的 `parts` 都是 `('references', 'format.md')`，`"."` 与 `""` 的 `parts` 是空元组。因此 `{"", "."}` 两项检查实际上永远命中不了，只有 `".."` 起作用（实测 `references/./format.md`、`./SKILL.md` 都能通过）。
- 空引用或 `.` 会走到 `target == root`，被报"reference escapes the skill directory"——结论正确但措辞有误导性。
- 包根下的 `SKILL.md` 本身也能被当作 reference 读取。
- 剩余风险：校验与读取之间存在 TOCTOU 窗口；"Path containment does not establish content trust"（讲义）——内容可信问题留给第 26 节。

### 3.8 `load_reference` 与 `demo`

```python
def load_reference(entry, reference, max_chars: int = 12_000) -> str:
    target = validate_reference(Path(entry.directory), reference)
    content = target.read_text(encoding="utf-8")
    if len(content) > max_chars:
        raise ReferencePathError(f"reference exceeds {max_chars} characters")
    return content
```

- 先校验路径，再读取，再按**字符数**检查上限。与 3.6 相同的问题：先完整读入再判断。讲义练习 3 要求"字节上限 + 恰好等于/超出 1 字节"的边界测试（测验 Q11 给出 `read(max_bytes + 1)` 的写法）。

`demo` 的场景：

- user scope：`evidence-report`（通用版）、`meeting-brief`；
- project scope：`evidence-report`（项目版）；
- 预算 `CatalogBudget(max_entries=10, max_catalog_chars=2_000)`，宽松到不会淘汰；
- 激活 project 版 `evidence-report`，读 `references/format.md`。
- 讲义说 demo 会"builds a catalog under a deliberately small budget … and attempts both a valid reference read and a traversal escape"，但 `demo()` 中**并没有**任何穿越尝试（这只在测试 `test_rejects_traversal_reference` 中出现），而 2,000 字符的预算对两条目也谈不上"刻意偏小"，没有触发任何淘汰——讲义与代码不一致。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只读 frontmatter、字节上限 8 KB | 发现阶段不加载 body，防大文件拖慢 | 无 |
| 浅层发现 | 保持包边界，不误发布夹具 | 嵌套组织的技能库需要显式配置多个根 |
| 坏包直接抛 `DiscoveryError` | 实现简单，问题不会被忽略 | 一个坏包让整个 scope 失效；应收集拒绝原因继续（随包脚本已如此） |
| symlink 目录静默跳过、symlink `SKILL.md` 报错 | 不跟随 symlink 就不会逃出信任根 | 行为不一致、前者无记录；应显式声明并记录 |
| 优先级由调用方传入 | "Scope is runtime policy" | 调用方必须维护策略并测试 |
| 同级重复抛错 | 不按偶然的文件系统顺序选择 | 整个目录构建失败；可改为记入错误、跳过该名字 |
| 按 `(rank, name)` 排序后从尾部淘汰 | 确定、可复现、可审计 | 与任务相关性无关，字母序靠后者天然吃亏 |
| 精确测量序列化 JSON | 预算与真实发送内容一致 | `ensure_ascii=True` 让非 ASCII 描述膨胀约 6 倍；字符 ≠ token |
| 目录条目带绝对路径 | 便于把条目映射回候选 | 泄露本地路径、占用预算；可改为内部 id |
| `report_chars` 不动点迭代 | 报告长度包含自身，仍要精确 | 代码略绕，但收敛快 |
| 引用只允许一级、逐段拒 symlink | 可达性可测试、无逃逸 | 合法的包内 symlink 也被拒；嵌套资料要扁平化 |
| 读取后再判断大小 | 代码简单 | 大文件先被完整读入；应限量读取 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 冻结 dataclass + 默认值 | `class CatalogBudget: max_entries: int = 50` | 不可变配置对象 |
| `asdict` | `asdict(entry)` | dataclass → 字典，便于 `json.dumps` |
| 多个自定义异常 | `class DiscoveryError(ValueError)`、`CollisionError`、`ReferencePathError` | 调用方可以分别捕获不同阶段的失败 |
| `with open` 逐行迭代 | `for raw_line in handle:` | 流式读取，不把整个文件读入内存 |
| `str.encode` 计字节 | `len(raw_line.encode("utf-8"))` | 字节数 ≠ 字符数 |
| `rstrip("\r\n")` | `raw_line.rstrip("\r\n")` | 去掉行尾换行（参数是字符集合） |
| `strip` 字符集合 | `value.strip("\"'")` | 去掉两端所有 `"` 和 `'` |
| `sorted(key=lambda ...)` | `sorted(scope.root.iterdir(), key=lambda item: item.name)` | 按指定键排序 |
| 元组作排序键 | `key=lambda item: (rank[item.scope], item.name)` | 先比第一项，相同再比第二项 |
| `enumerate` + 字典推导式 | `{scope: index for index, scope in enumerate(precedence)}` | 生成"值 → 下标"映射 |
| `dict.setdefault` | `grouped.setdefault(candidate.name, []).append(candidate)` | 键不存在时先放一个空列表 |
| 解包到元组 | `candidates = (*discover_scope(...), *discover_scope(...))` | 把两个元组拼成一个 |
| 多返回值 | `return tuple(winners), tuple(collisions)` / `winners, collisions = ...` | 返回元组再解包 |
| 列表切片 | `ordered[: budget.max_entries]`、`ordered[budget.max_entries :]` | 前 N 个 / 其余 |
| `list.pop()` / `insert(0, x)` | `entries.pop()`、`omitted.insert(0, removed.name)` | 删最后一个 / 插到最前 |
| 嵌套函数（闭包） | `def model_size(current_entries)` 定义在 `build_catalog` 里 | 只在本函数内使用的辅助函数 |
| `while True` + `return` | `report_chars` 不动点迭代 | 满足条件时从循环中直接返回 |
| `json.dumps` 参数 | `sort_keys=True, separators=(",", ":")` | 键排序保证确定性；紧凑分隔符去掉空格 |
| `pathlib` | `Path.resolve()`、`.is_symlink()`、`.is_file()`、`.iterdir()`、`.parents` | 面向对象的路径操作；`target.parents` 是所有祖先目录 |
| `PurePosixPath` | `PurePosixPath(reference).parts` | 只做字符串层面的路径解析，不访问磁盘，按 POSIX 规则 |
| `raise ... from` 与 `KeyError` | `raise KeyError(f"catalog entry {entry.name!r} has no matching candidate")` | 找不到映射时抛出明确错误 |
| `next` 带生成器 | `next(entry for entry in catalog.entries if entry.name == "evidence-report")` | 取第一个匹配项（找不到会抛 `StopIteration`） |
| `tempfile.TemporaryDirectory` | `with tempfile.TemporaryDirectory(prefix="lesson-24-") as temp_dir:` | 自动清理的临时目录 |
| `mkdir(parents=True)` | `(directory / "references").mkdir(parents=True)` | 连同父目录一起创建 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 code/main.py`，退出码 0；临时目录名每次不同）：

```text
{
  "catalog": {
    "catalog_chars": 357,
    "collisions": [
      {"name": "evidence-report", "shadowed_scopes": ["user"], "winner_scope": "project"}
    ],
    "entries": [
      {"description": "Create this project's evidence report when an audit completes.",
       "directory": "/tmp/lesson-24-4ged6ffu/project/evidence-report",
       "name": "evidence-report", "scope": "project"},
      {"description": "Prepare a meeting brief from supplied notes.",
       "directory": "/tmp/lesson-24-4ged6ffu/user/meeting-brief",
       "name": "meeting-brief", "scope": "user"}
    ],
    "omitted": [],
    "report_chars": 503
  },
  "disclosure": {
    "level_1_catalog_chars": 357,
    "level_2_body_chars": 70,
    "level_3_reference_chars": 46
  }
}
```

（实际输出每个键独占一行，这里为节省篇幅合并；`sort_keys=True` 使键按字母序排列。）

逐项解读：

- **entries**：project 版 `evidence-report` 胜出（描述是"this project's … when an audit completes"），user 的 `meeting-brief` 没有冲突直接进入。排序键 `(rank, name)` 使 project 条目排在前面。
- **collisions**：记录了被遮蔽的 user 版本——模型看不到它，但诊断报告看得到。
- **omitted 为空**：两条目远小于 2,000 字符的预算。
- **catalog_chars = 357 / report_chars = 503**：前者只算模型可见的 entries；后者多了 collisions、omitted 和两个长度字段，差额 146 字符。两个条目的 directory 合计约 90 字符，占模型目录的四分之一左右——这就是"目录里放绝对路径"的成本。具体数字随临时目录名长度略有变化。
- **三级字符数**：Level 1 是 357（全部目录），Level 2 是 70（`# Project evidence report\n\nRead ...` 这一段 body），Level 3 是 46（`format.md` 的内容）。对应讲义练习 6 "report Level 1, Level 2, and Level 3 byte counts separately"——注意这里是**字符**数，不是字节数。

---

## 7. 动手改一改

1. **（讲义练习 1）** 增加 `plugin` scope，放在 user 与 built-in 之间（`precedence=("project", "user", "plugin", "builtin")`），写测试证明三方同名时 project 胜出、`shadowed_scopes == ("user", "plugin")`。
2. **结构化拒绝**：把 `discover_scope` 改成返回 `(candidates, rejected)`，把坏包和 symlink 目录都记录下来；`build_catalog` 的报告里加 `rejected` 字段（测验 Q10）。
3. **（讲义练习 3、5）** 给 `load_reference` 加字节上限（`read(max_bytes + 1)`）与 SHA-256 清单校验，写"恰好等于上限通过、超 1 字节失败、内容被改拒绝"三个测试（测验 Q11）。
4. **（讲义练习 2）** 把冲突策略改成"按来源限定名"：两个 `evidence-report` 都进目录，名字分别为 `project:evidence-report`、`user:evidence-report`，并比较 `catalog_chars` 的变化。
5. **修预算偏差**：把 `model_size` 改为 `ensure_ascii=False`，并从模型可见条目中去掉 `directory`（保留在内部映射里），对比同一组技能在两种计量下能放进多少条。
6. **（讲义练习 6）** 记录加载事件：每次 `load_skill_body` / `load_reference` 追加 `{"event": "skill.resource.loaded", "skill", "resource", "reason", "bytes"}`，`reason` 由调用方传入；在 demo 结尾打印事件列表。

---

## 8. 常见坑

- **一个坏包拖垮整个 scope**：`discover_scope` 是 fail-fast 的；在共享目录里放一个命名不规范的包，所有技能都"消失"了。
- **symlink 的两种待遇**：symlink 目录被静默跳过，symlink `SKILL.md` 则报错。用 symlink 管理技能的人会困惑"为什么没被发现"。
- **把字符当 token**：`catalog_chars` 是 JSON 字符数，而且非 ASCII 被转义放大；不要把它当作模型 token 预算。
- **以为预算超了会缩短描述**：本实现只做固定长度截断，超预算时直接省略整条（从排序末尾开始）。
- **截断吃掉触发边界**：240 字符的描述上限会截掉描述后半部分——讲义建议的"能力 + 触发边界"两分句结构中，后一句往往更重要。
- **同级重复让目录构建整体失败**：`CollisionError` 会向上抛出，`build_catalog` 不会部分成功。
- **以为 `"."` 检查有效**：`PurePosixPath` 已经把 `.` 和空段规范化掉了；真正的防线是 `..` 检查和 `resolve()` 后的祖先判断。
- **用字符串前缀判断包含关系**：`str(target).startswith(str(root))` 会被 `/skills/reporter-evil` 绕过；本实现用 `root in target.parents` 是正确做法。
- **路径合法就信任内容**：包内文件仍可能含恶意指令，见第 26 节。

---

## 9. 测试在验证什么

运行方式（在小节目录下）：`python3 -m unittest discover -s code/tests -v`。测试设置 `sys.dont_write_bytecode = True`，每个用例在 `setUp` 中新建临时目录、`tearDown` 中清理。实际结果：**Ran 23 tests … OK**。

辅助函数 `write_skill(root, directory, description)` 生成带 `BODY-MARKER` 的 body 和内容为 `FORMAT-MARKER` 的 `references/format.md`，便于断言"某段内容有没有被加载"。

| 用例 | 验证的性质 |
|---|---|
| `test_discovers_only_direct_skill_directories` | 没有 `SKILL.md` 的子目录被忽略 |
| `test_discovers_folded_description_content` | `>` 块被折叠为一句；`metadata` 嵌套不影响发现 |
| `test_rejects_frontmatter_name_directory_mismatch` | name 与目录名不同 → `DiscoveryError` |
| `test_rejects_invalid_or_duplicate_identity_fields` | `Bad_Name` 格式错误、重复 `name` 字段都被拒 |
| `test_rejects_malformed_top_level_frontmatter` | 无冒号顶层行 → "malformed top-level" |
| `test_rejects_symlinked_skill_file` | `SKILL.md` 是 symlink → `DiscoveryError` |
| `test_host_precedence_selects_project_candidate` | project 优先时 project 胜出，`shadowed_scopes == ("user",)` |
| `test_precedence_is_policy_not_fixed_standard` | 反转优先级元组后 user 胜出 |
| `test_equal_precedence_collision_is_not_silently_overwritten` | 两个 `project` 根下的同名技能 → `CollisionError` |
| `test_catalog_honors_entry_budget` | `max_entries=1` 时只保留 `alpha`，`omitted == ("beta",)` |
| `test_catalog_truncates_description_to_declared_budget` | 30 字符描述截到 10 字符并以 `…` 结尾 |
| `test_catalog_budget_covers_exact_model_facing_entries` | `catalog_chars`、`report_chars` 与真实序列化长度**精确相等**，且 ≤ 700 |
| `test_diagnostics_do_not_evict_model_visible_entries` | 加入被遮蔽的 user 候选后，模型目录不变、`catalog_chars` 不变，只有 `report_chars` 增加 |
| `test_body_load_is_separate_from_catalog_construction` | 目录里没有 `BODY-MARKER`，激活后才有 |
| `test_accepts_one_level_reference` | `references/format.md` 通过 |
| `test_rejects_traversal_reference` | `../secret.md` 被拒 |
| `test_rejects_non_string_reference_with_domain_error` | `None`、`1`、`[]`、`{}` 都抛 `ReferencePathError("must be a string")` |
| `test_rejects_deep_reference_chain` | 两级子目录被拒 |
| `test_rejects_internal_symlink_reference` | 指向包内文件的 symlink 也被拒 |
| `test_reference_load_obeys_size_budget` | `max_chars=3` 时读取失败 |
| `test_bundled_catalog_reports_equal_precedence_duplicate` | 动态加载**随包脚本** `build_catalog.py`：同级重复记入 `errors`、`valid=False`（而不是抛异常） |
| `test_bundled_catalog_shorten_handles_boundary_limits` | 随包脚本的 `shorten` 在 −1、0、1 时分别返回 `""`、`""`、`"…"` |
| `test_bundled_catalog_rejects_malformed_top_level_frontmatter` | 随包脚本对坏行记入错误 |

测试没有覆盖、值得补的地方：

- 一个坏包与若干好包共存时的行为（当前会整体失败，测试没有把这种行为固定下来或改为部分成功）；
- symlink **目录**被跳过的行为；
- `max_catalog_chars` 触发淘汰（现有用例里只有条目数触发）以及淘汰顺序；
- 非 ASCII 描述的预算计量；
- `load_skill_body` 的大小上限；
- `references/./x`、`./SKILL.md` 这类"被规范化后通过"的路径。
