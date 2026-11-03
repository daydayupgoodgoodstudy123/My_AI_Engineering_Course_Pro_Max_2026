# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 27 节 Skill 评估、打包与可移植性 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试：`python3 -m unittest discover -s tests -v`（在 `code/` 目录下） ｜ **依赖**：仅标准库（`hashlib`、`json`、`math`、`re`、`shutil`、`tempfile`、`dataclasses`、`pathlib`、`typing`）；demo 读取 `../outputs/skill-release-gate/` 下的 bundle，不需要网络、不调用任何模型

---

## 1. 这份代码在考察什么

`main.py` 是本 mini-track 的"发布闸门 harness"：给定一个 skill 目录和一组评估输入，逐层判断它能不能发布，并且**保留每一层的结论**，不让某一层的高分掩盖另一层的失败。它对应讲义的六层评估：

| 讲义层级 | 代码中的实现 |
|---------|-------------|
| Layer 1 包结构 | `lint_package`：frontmatter、名称、正文预算、必需段落、运行时扩展白名单、引用、后缀、大小、symlink、秘密、孤儿文件 |
| Layer 2 触发路由 | `TriggerCase` + 路由器 + `classification_metrics` / `repeated_run_observations` / `rates_from_observations` |
| Layer 3 行为与产物 | `ArtifactContract` + `evaluate_artifact` / `compare_artifacts`（baseline vs with-skill） |
| Layer 4 脚本正确性 | `EvidenceCheck` + `evaluate_evidence_checks(..., "script correctness")` |
| Layer 5 安全与权限 | `evaluate_evidence_checks(..., "safety")` |
| Layer 6 打包与可移植性 | `build_manifest` / `verify_manifest`（源与安装副本）+ `HostCapabilities` / `portability_matrix` |

在六层之上还有一套**证据可信度**分级：`fixture_passed`（教学夹具通过）→ `local_evidence_ready`（captured 数据与本地摘要一致）→ `production_ready`（外部 attestation 绑定整个 `evidence_root`）。最终的 `passed` 只跟随 `production_ready`。

> 一句话：**把"skill 做完了吗"拆成十几个可以独立失败的检查，再用摘要与外部信任锚区分"机制演示通过"和"真的可以发布"。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `NAME_PATTERN`、`CORE_FIELDS`、`MAX_*`、`ALLOWED_SUFFIXES`、`SECRET_PATTERNS`、`SHA256_PATTERN` | 常量 | 发布策略的具体数值 | release policy |
| `LintIssue` / `LintReport` | 冻结 dataclass | 结构检查的问题码与结果 | 稳定 issue code |
| `_frontmatter_and_body` | 函数 | 手写的极简 YAML frontmatter 解析 | 安全解析 |
| `_bundle_paths` / `_section_has_content` / `_contains_obvious_secret` | 辅助函数 | 抽取直接引用、检查段落、扫描秘密 | Layer 1 |
| `lint_package` | 函数 | 结构 lint 主体 | Layer 1 |
| `TriggerCase` / `KeywordRouter` | dataclass / 可调用 dataclass | 带标签的触发用例；词法路由模拟器 | Layer 2 |
| `classification_metrics` / `evaluate_triggers` / `trigger_report_from_observations` / `repeated_run_observations` / `rates_from_observations` / `repeated_run_rates` | 函数 | 混淆矩阵、逐用例报告、重复运行 | Layer 2 |
| `ArtifactContract` / `evaluate_artifact` / `compare_artifacts` | dataclass / 函数 | 产物契约与基线对比 | Layer 3 |
| `EvidenceCheck` / `evaluate_evidence_checks` | dataclass / 函数 | 显式的脚本/安全证据 | Layer 4/5 |
| `build_manifest` / `verify_manifest` | 函数 | SHA-256 文件清单与校验 | Layer 6 打包 |
| `PackageRequirements` / `HostCapabilities` / `portability_matrix` | dataclass / 函数 | 能力矩阵 | Layer 6 可移植性 |
| `ReleaseThresholds` | 冻结 dataclass + `__post_init__` | 阈值与校验 | release gate |
| `EvaluationProvenance` / `artifact_digest` / `bytes_digest` / `_canonical_digest` / `evidence_digest` / `host_matrix_digest` / `trigger_results_digest` / `evaluate_provenance` | dataclass / 函数 | 证据来源模式与本地完整性摘要 | local integrity |
| `local_evidence_root` / `build_external_attestation` / `verify_external_attestation` | 函数 | 证据根摘要与外部信任锚 | production readiness |
| `run_release_gate` | 函数 | 串联全部检查，输出分层报告 | release gate |
| `demo` | 函数 | 对交付 bundle 跑一次夹具模式闸门 | 演示 |

数据流：`demo()` → 定义 6 个触发用例、词法路由器、产物契约、3 个宿主、脚本/安全证据 → `build_manifest(source)` → `copytree` 到临时"安装目录" → `run_release_gate(...)`：lint → 触发观测（5 次）→ 指标与重复率 → 产物对比 → 能力矩阵 → 证据检查 → 源/安装 manifest 校验 → provenance → `checks` → `fixture/local/trust/production` → JSON 报告。

---

## 3. 逐段精讲

### 3.1 发布策略常量

```python
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CORE_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
MAX_SKILL_BODY_CHARS = 10_000
MAX_COMPANION_FILE_BYTES = 1_000_000
RESERVED_MANIFEST_PATH = "assets/manifest.json"
ALLOWED_SUFFIXES = {
    "references": frozenset({".md", ".txt", ".json", ".yaml", ".yml"}),
    "scripts": frozenset({".py", ".sh", ".js", ".mjs", ".ts"}),
    "assets": frozenset({".csv", ".gif", ..., ".yml"}),
    "evals": frozenset({".json"}),
}
```

- `NAME_PATTERN`：kebab-case，小写字母数字用单个连字符连接。
- `CORE_FIELDS`：Agent Skills 的核心 frontmatter 字段；其它字段都算"运行时扩展"，必须由包需求显式允许。
- 讲义强调这些数字是"release-policy examples, not universal Agent Skills limits"——10,000 字符正文、1,000,000 字节附属文件都是本课的示例策略。
- `SECRET_PATTERNS` 以 `rb"..."` 定义，直接扫描**字节**（`path.read_bytes()`），避免因编码问题漏扫；且要求值至少 12 个字符，减少误报（比第 26 节的版本更严格）。
- 讲义说"lint report should use stable issue codes. CI can block `E_*` errors while allowing reviewed `W_*` design warnings"。代码的问题码是 `name-format`、`orphan-file` 这类名字，**没有 E_/W_ 前缀，也没有任何警告级别**——每个 issue 都会让 `valid=False`。

### 3.2 `_frontmatter_and_body`：不用 YAML 库的安全解析

```python
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise ValueError("SKILL.md needs exact frontmatter delimiters")
    end = lines.index("---", 1)
    ...
        if line[:1].isspace() or ":" not in line:
            raise ValueError(f"malformed top-level line {index + 1}")
        key, value = line.split(":", 1)
        ...
        if key in fields:
            raise ValueError(f"duplicate frontmatter field {key!r}")
```

- 第一行必须恰好是 `---`，后面必须还有一个 `---`；`lines.index("---", 1)` 从第 2 行开始找结束分隔符。
- 只支持三种值：普通标量（去掉两侧引号）、`metadata:` 下一层缩进的键值对（序列化成排序后的 JSON 字符串）、`>`（折叠，用空格连接）和 `|`（字面量，用换行连接）块。
- **重复字段直接报错**：通用 YAML 库对重复键通常"后者覆盖前者"，而这里把它当成畸形输入——这就是讲义说的"frontmatter parses safely"：不执行任意 YAML 标签，也不接受含糊的输入。
- `split(":", 1)` 只按第一个冒号切，值里可以包含冒号（如 URL）。

### 3.3 引用抽取与段落检查

```python
def _bundle_paths(body: str) -> tuple[str, ...]:
    paths: set[str] = set()
    for code_span in re.findall(r"`([^`]+)`", body):
        for raw_token in code_span.split():
            token = raw_token.strip("()[]{}<>,;:'\"").rstrip(".,;:")
            if any(marker in token for marker in ("references/", "scripts/", "assets/", "evals/")):
                paths.add(token)
    return tuple(sorted(paths))
```

- 只看**反引号代码片段**中的 token：`` `python3 scripts/check.py` `` 会被切成两个 token，`scripts/check.py` 入选。纯文本里写的路径不会被识别。
- 结果排序后返回，保证报告稳定。

```python
def _section_has_content(body: str, title: str) -> bool:
    heading = re.compile(rf"^##\s+{re.escape(title)}\s*#*\s*$", re.IGNORECASE)
    for index, line in enumerate(lines):
        if not heading.fullmatch(line):
            continue
        for candidate in lines[index + 1 :]:
            if re.match(r"^#{1,6}\s+", candidate):
                return False
            if candidate.strip():
                return True
```

- 找到 `## Output contract`（大小写不敏感，允许 `## Title ##` 这种闭合写法）后，向下找第一个非空行：如果先遇到下一个标题，说明段落为空。讲义要求"non-empty `## Output contract` and `## Failure behavior` sections"。

### 3.4 `lint_package`：结构检查主体

```python
    if not root.is_dir() or root.is_symlink():
        return LintReport(False, (), (LintIssue("bundle-directory", "regular bundle directory required"),))
    if not skill_path.is_file() or skill_path.is_symlink():
        return LintReport(False, (), (LintIssue("skill-file", "regular SKILL.md required"),))
```

- 先做**物理树预检**，再读任何内容：根目录不能是 symlink，`SKILL.md` 必须是普通文件。讲义："Resolving the bundle path before preflight erases the root-symlink evidence the check needs."——所以这里对传入的 `root` 直接 `is_symlink()`，不先 `resolve()`。
- 之后依次检查：名称格式与 64 字符上限、名称 == 目录名、description 必填且 ≤ 1024、正文非空且 ≤ 10,000、两个必需段落、非核心字段必须在 `allowed_runtime_extensions` 中。

```python
    references = _bundle_paths(body)
    for reference in references:
        relative = PurePosixPath(reference)
        if (relative.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.parts)
            or len(relative.parts) != 2
            or relative.parts[0] not in {"references", "scripts", "assets", "evals"}):
            issues.append(LintIssue("reference-shape", ...))
            continue
        parent = root / relative.parts[0]
        target = parent / relative.parts[1]
        if parent.is_symlink() or not target.is_file() or target.is_symlink():
            issues.append(LintIssue("reference-missing", ...))
```

- 引用必须恰好是 `<四个目录之一>/<文件名>` 两段，拒绝 `..`、绝对路径、反斜杠；目录和文件都不能是 symlink。

```python
    for path in root.rglob("*"):
        if path.is_symlink():
            issues.append(LintIssue("symlink", ...))
        elif path == skill_path:
            continue
        elif path.is_file():
            relative = path.relative_to(root).as_posix()
            packaged_files.add(relative)
            if len(path.relative_to(root).parts) != 2:
                issues.append(LintIssue("package-depth", ...)); continue
            ...  # file-type / file-size / secret-material
        elif not path.is_dir():
            issues.append(LintIssue("special-file", ...))
    ...
    for orphan in sorted(packaged_files - set(references)):
        issues.append(LintIssue("orphan-file", ...))
```

- 遍历整棵树：symlink、特殊文件（socket、FIFO、设备）直接报错。
- **package-depth**：除 `SKILL.md` 外，所有文件必须恰好在四个目录之一的第一层。
- **orphan-file**：所有打包文件都必须被 SKILL.md 直接引用——这是比讲义更严格的策略（讲义只要求"每个直接引用都能解析"），它保证"包里没有 SKILL.md 不知道的东西"。
- ⚠️ **本仓库副本中这两条规则正好命中**：交付 bundle `outputs/skill-release-gate/` 里多了翻译流程加入的 `SKILL.zh.md`（根目录，深度 1）和 `references/eval-contract.zh.md`（未被引用），导致 `structure` 失败，demo 的 `checks_passed`/`fixture_passed` 都变成 `false`（见第 6 节与测验 Q9）。

### 3.5 触发评估：用例、路由器、指标

```python
@dataclass(frozen=True)
class KeywordRouter:
    terms: tuple[str, ...]
    threshold: int = 2

    def __call__(self, prompt: str, run_index: int = 0) -> bool:
        del run_index
        prompt_terms = set(re.findall(r"[a-z0-9]+", prompt.lower()))
        return len(prompt_terms & set(self.terms)) >= self.threshold
```

- 路由器接口是 `Callable[[str, int], bool]`：输入提示与第几次运行，输出是否触发。真实系统可以把这里替换成"调用宿主并观察它选了哪个 skill"。
- `KeywordRouter` 是讲义说的 **lexical simulator**：只数词表命中数。`del run_index` 显式表示不用运行序号——结果完全确定。
- 局限（已实测）："Do not use the skill package; explain this stack trace" → `True`（不懂否定，误触发）；"Can version 3.1.0 ship?" → `False`（不懂同义表达，漏触发）。

```python
def classification_metrics(expected, predicted):
    tp = sum(want and got for want, got in zip(expected, predicted))
    fp = sum(not want and got for want, got in zip(expected, predicted))
    ...
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {..., "precision": round(precision, 4), "recall": round(recall, 4), ...}
```

- 布尔值求和：`True` 计为 1。分母为 0 时返回 0.0（一种保守约定）。
- 讲义给了 F1 公式，代码**没有计算 F1**。
- ⚠️ 先取整再给闸门比较：19999/25000 = 0.79996 被取整为 0.8，在 `min_recall=0.8` 下判为通过（已实测）。

```python
def trigger_report_from_observations(cases, observations):
    _validate_trigger_cases(cases)
    ...
    expected = [case.expected for case in cases for _ in observations[case.case_id]]
    predicted = [value for case in cases for value in observations[case.case_id]]
    metrics = classification_metrics(expected, predicted)
```

- 观测是 `{case_id: (bool, bool, ...)}`，每个用例可以有多次运行。指标把**每次运行**都当成一个样本：demo 中 3 个正例 × 5 次 = `true_positive: 15`。这会让原始计数虚高（讲义强调原始计数代表证据强度）。
- 每个用例的 `passed` 要求**所有**运行都正确；`predicted` 只取第一次运行，`observed_predictions` 保留全部。
- `_validate_trigger_cases`：用例 id 必须唯一、非空、两侧无空白；提示也不能有两侧空白。测试专门构造了 `"duplicate"` 与 `"duplicate "` 这种"看起来不同其实相同"的 id。

```python
def rates_from_observations(cases, observations):
    return {
        case.case_id: round(
            sum(value == case.expected for value in observations[case.case_id])
            / len(observations[case.case_id]), 4)
        for case in cases
    }
```

- 每个用例的"正确率" `k/n`，对应讲义 `observed_pass_rate = k / n`。闸门取所有用例中的**最小值**与 `min_repeat_rate` 比较——任一用例不稳定都会失败。
- ⚠️ 讲义 Build It 说 `repeated_run_rates(...)` 用于"per-case repeated behavioral outcomes"，而代码里它只作用于**触发**观测；行为层（产物）只有一对产物、没有重复运行。

### 3.6 产物契约与基线对比

```python
def evaluate_artifact(text: str, contract: ArtifactContract) -> dict[str, object]:
    def has_heading(heading: str) -> bool:
        pattern = rf"^#{{1,6}}\s+{re.escape(heading)}\s*#*\s*$"
        return re.search(pattern, text, re.MULTILINE) is not None

    def has_term(term: str) -> bool:
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
        return re.search(pattern, text, re.IGNORECASE) is not None
```

- 标题：任意 1–6 级 Markdown 标题，**整行**等于该文字（`# Decision-making` 不算 `Decision`）。f-string 中 `{{1,6}}` 是转义后的花括号，生成正则 `#{1,6}`。
- 术语：大小写不敏感 + 前后不是单词字符（lookbehind/lookahead），所以 `recall` 不匹配 `Recalling`、`recall-based` 中的 `recall` 却会匹配（`-` 不是 `\w`）。
- ⚠️ 纯词法：`forbidden_terms=("guaranteed portable",)` 会把 "Not guaranteed portable." 判为违规（假阳性），而 "Guaranteed  portable"（两个空格）能绕过（假阴性），均已实测。

```python
def compare_artifacts(baseline, with_skill, contract):
    ...
    "skill_improves_pass_state": not baseline_result["passed"] and skill_result["passed"],
```

- 只有"baseline 失败、with-skill 通过"才算改进。⚠️ 闸门把 `artifact_improvement` 当必过项，意味着 baseline 已经通过契约时 skill **无法发布**——与讲义闸门的 `no_regression_vs_baseline` 语义不同（讲义要求不回退，代码要求必须翻转）。

### 3.7 显式证据：脚本与安全

```python
def evaluate_evidence_checks(cases, layer):
    if not cases:
        raise ValueError(f"{layer} requires at least one explicit check")
    ...
        if type(case.passed) is not bool:
            raise ValueError(...)
        if not isinstance(case.evidence, str) or not case.evidence.strip():
            raise ValueError(...)
    return {"passed": all(case.passed for case in cases), "cases": normalized}
```

- 不允许空列表（防止"零个检查 = 全部通过"的空真）；`type(...) is not bool` 拒绝 `1`、`"true"` 这类"像布尔的值"；每条检查必须附证据文字。
- 这些检查是**声明式**的：harness 不运行脚本测试、也不做安全攻击，只接收结果。正因为结果是外部声明的，后面才需要 provenance 和 attestation 来约束"谁产生的、是否被改过"。

### 3.8 Manifest：构建与校验

```python
def build_manifest(root: Path) -> dict[str, str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("manifest root must be a regular directory")
    manifest: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(...)
        if relative == RESERVED_MANIFEST_PATH:
            ...
            continue
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest[relative] = f"sha256:{digest}"
        elif not path.is_dir():
            raise ValueError(...)
```

- 按 POSIX 路径排序遍历；每个普通文件记 `sha256:<64 位十六进制>`；`assets/manifest.json` 自身跳过（讲义："A file cannot carry a stable hash of its complete current contents inside itself"）。

```python
def verify_manifest(root, expected):
    for raw_path, digest in expected.items():
        relative = PurePosixPath(raw_path)
        if ("\\" in raw_path or relative.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.parts)
            or raw_path != relative.as_posix()):
            issues.append(f"invalid manifest path: {raw_path!r}")
            continue
        if relative.as_posix() == RESERVED_MANIFEST_PATH:
            issues.append(...); continue
        if not SHA256_PATTERN.fullmatch(digest):
            issues.append(...); continue
        normalized[relative.as_posix()] = digest
    actual = build_manifest(root)
    missing = sorted(set(normalized) - set(actual))
    unexpected = sorted(set(actual) - set(normalized))
    mismatched = sorted(p for p in set(normalized) & set(actual) if normalized[p] != actual[p])
```

- 键必须**已经**是规范形式：`raw_path != relative.as_posix()` 抓住 `./SKILL.md`、`a//b` 这种"规范化后会变"的写法——讲义："rejected instead of normalized"。
- 三类差异分别报告：`missing`（清单有、树里没有）、`unexpected`（树里有、清单没有——旧版本残留或注入的文件）、`mismatched`（内容被改）。
- ⚠️ demo 中 manifest 是**运行时从源目录现算**的，所以 `source_manifest` 是同义反复，`installed_tree` 只验证了 `copytree`。交付脚本读取包内事先存好的 `assets/manifest.json`，因此能发现翻译文件属于 `unexpected`。

### 3.9 能力矩阵

```python
def portability_matrix(requirements, hosts):
    for host in hosts:
        ...  # 主机名唯一、非空、无两侧空白
        if not host.loads_core_skill:
            status = "unsupported"
            missing.append("core-skill-loader")
        else:
            if requirements.companion_files and not host.preserves_companion_files:
                missing.append("companion-files")
            if requirements.script_execution and not host.runs_bundled_scripts:
                missing.append("script-execution")
            unsupported_extensions = sorted(set(requirements.runtime_extensions) - set(host.supported_extensions))
            missing.extend(f"extension:{field}" for field in unsupported_extensions)
            status = "native" if not missing else "adapter-required"
```

- 三种状态：`native`、`adapter-required`、`unsupported`，并列出缺失项——把"降级"显式写出来，而不是静默发生。
- 主机名去重同样考虑了 `"same-host"` 与 `"same-host "`：否则两个重复记录就能满足 `min_native_hosts=2`。
- 简化：讲义的四种结果里有"degraded with a documented fallback"，代码没有这一档；闸门只要求"至少 N 个 native 宿主"，没有"必需宿主"概念（讲义的 `required_hosts_without_silent_degradation`）。

### 3.10 阈值、provenance 与本地完整性

```python
@dataclass(frozen=True)
class ReleaseThresholds:
    min_precision: float = 0.8
    min_recall: float = 0.8
    min_repeat_rate: float = 0.9
    min_native_hosts: int = 1

    def __post_init__(self) -> None:
        for field_name in ("min_precision", "min_recall", "min_repeat_rate"):
            value = getattr(self, field_name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0.0 <= value <= 1.0):
                raise ValueError(...)
        if type(self.min_native_hosts) is not int or self.min_native_hosts < 1:
            raise ValueError(...)
```

- `__post_init__` 在 dataclass 构造后执行校验：拒绝 `True`（`bool` 是 `int` 的子类，必须先排除）、NaN/inf、越界值；`min_native_hosts=0` 被拒，防止宿主层"空真通过"。

```python
@dataclass(frozen=True)
class EvaluationProvenance:
    trigger_mode: str = "deterministic-fixture"
    artifact_mode: str = "fixture"
    evidence_mode: str = "deterministic-fixture"
    host_mode: str = "deterministic-fixture"
    artifact_source: str = ""
    ...
    trigger_digest: str = ""
```

- 四类数据各有一个模式：夹具或 captured。`evaluate_provenance` 对未知模式直接抛错（fail closed）；只有 captured 模式下，source 非空且摘要与当前数据一致，对应的 `*Integrity` 才为 `True`。

```python
def _canonical_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return bytes_digest(encoded)
```

- **规范化 JSON 摘要**：键排序、无多余空白、保留非 ASCII 原字符，保证相同的数据结构永远得到相同字节、相同哈希。`trigger_results_digest` 把**每一个原始预测**都放进去——测试证明两组"首值相同、通过率相同但顺序不同"的观测会得到不同摘要（讲义："Bind provenance to every raw per-run prediction"）。

### 3.11 证据根与外部信任锚

```python
def local_evidence_root(cases, observations, baseline_artifact, with_skill_artifact, artifact_contract,
                        script_checks, safety_checks, requirements, hosts, manifest, thresholds, provenance) -> str:
    payload = {
        "triggers": {...}, "artifacts": {...}, "evidence": {...},
        "portability": {...}, "manifest": dict(manifest),
        "thresholds": asdict(thresholds), "provenance": asdict(provenance),
    }
    return _canonical_digest(payload)
```

- 一个 SHA-256 覆盖本次评估的**全部**输入：触发用例与观测、两份产物与契约、证据、能力需求与宿主、manifest（间接覆盖每个文件的内容）、阈值、provenance。任何一处改动都会改变 `evidence_root`。

```python
def verify_external_attestation(evidence_root, attestation_payload, trusted_attestation_digest):
    if attestation_payload is None: issues.append("trusted external attestation was not supplied")
    if trusted_attestation_digest is None: issues.append("trusted attestation SHA-256 was not supplied out of band")
    ...
    actual_digest = bytes_digest(attestation_payload)
    if not SHA256_PATTERN.fullmatch(trusted_attestation_digest): ...
    elif actual_digest != trusted_attestation_digest:
        issues.append("external attestation does not match the trusted SHA-256")
    decoded = json.loads(attestation_payload.decode("utf-8"))
    ...  # attestationVersion 必须是整数 1（拒绝 True），evidenceRoot 必须相等
```

- 两个输入缺一不可：attestation 字节（声明"这次评估的 evidenceRoot 是 X"）和这些字节的可信摘要（**带外**提供）。字节摘要对不上、版本不对（`True` 也被拒，因为用了 `type(...) is not int`）、evidenceRoot 不一致都会失败。
- 这把"信任"锚定在 bundle 之外：能改 bundle 的人能重算所有本地摘要，却无法让带外的可信摘要随之改变。实测：captured 模式下改一条 evidence 并重算 `checks_digest` 后，`local_evidence_ready=True` 但 `trust_anchor_valid=False`（"external attestation evidenceRoot does not match"）。

### 3.12 `run_release_gate`：把一切串起来

```python
    if not cases or not any(case.expected for case in cases) or not any(not case.expected for case in cases):
        raise ValueError("release gate requires positive and near-miss negative trigger cases")
    ...
    if package_root.resolve() == installed_root.resolve():
        installed_manifest = {**installed_manifest, "passed": False,
                              "issues": [*installed_manifest["issues"], "installed tree must be distinct from the source bundle"]}
    ...
    checks = {
        "structure": lint.valid,
        "precision": float(metrics["precision"]) >= thresholds.min_precision,
        "recall": float(metrics["recall"]) >= thresholds.min_recall,
        "repeated_runs": min(rates.values(), default=0.0) >= thresholds.min_repeat_rate,
        "with_skill_artifact": bool(artifacts["with_skill"]["passed"]),
        "artifact_improvement": bool(artifacts["skill_improves_pass_state"]),
        "script_correctness": bool(scripts["passed"]),
        "safety": bool(safety["passed"]),
        "source_manifest": bool(source_manifest["passed"]),
        "installed_tree": bool(installed_manifest["passed"]),
        "native_hosts": native_hosts >= thresholds.min_native_hosts,
    }
    checks_passed = all(checks.values())
    fixture_passed = checks_passed and (所有四种模式都是夹具模式)
    local_evidence_ready = 四个 *Integrity 全为 True
    ...
    production_ready = checks_passed and local_evidence_ready and trust_anchor_valid
    return {"passed": production_ready, ...}
```

- 前置约束：必须同时有正例和负例，否则 precision/recall 无意义；必须至少有一个宿主记录。
- "安装目录不能就是源目录"：否则"安装测试"什么也没测。
- `checks` 是 11 个独立布尔值，报告里全部保留。
- **三层结论**：`fixture_passed` 要求全部为夹具模式；`local_evidence_ready` 要求全部为 captured 且摘要一致——两者互斥；`production_ready` 再加上外部信任锚。`passed` 只等于 `production_ready`。

### 3.13 `demo()`

```python
    package_root = Path(__file__).resolve().parents[1] / "outputs" / "skill-release-gate"
    cases = (
        TriggerCase("positive-package", "evaluate this skill package before release", True),
        ...
        TriggerCase("near-dependency", "install package dependencies", False),
    )
    router = KeywordRouter(("skill", "package", "bundle", "trigger", "portability", "evaluate", "release"), threshold=2)
    ...
    manifest = build_manifest(package_root)
    with tempfile.TemporaryDirectory(prefix="lesson-27-install-") as temp_dir:
        installed_root = Path(temp_dir) / package_root.name
        shutil.copytree(package_root, installed_root)
        report = run_release_gate(..., runs=5, ..., requirements=PackageRequirements(companion_files=True, script_execution=True), ...)
```

- 三个 near miss 各只命中一个词（`release`、`evaluate`、`package`），刚好低于阈值 2；三个正例各命中 2–3 个词。
- 三个宿主分别演示 native / adapter-required / unsupported。
- 未传 `provenance` 和 attestation，所以是纯夹具模式：理论上应得到 `checks_passed=True, fixture_passed=True, passed=False`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手写极简 frontmatter 解析 | 不依赖第三方 YAML、拒绝重复键和含糊格式 | 不支持完整 YAML；生产可用安全加载器 + 显式 schema |
| 孤儿文件与一层深度规则 | 包里不应有 SKILL.md 不知道的文件 | 会拦下翻译、README 等合理附属文件（本副本正是如此） |
| 问题码无 E_/W_ 分级 | 简单 | 讲义建议的"阻断错误 / 可审阅警告"未实现 |
| 词法路由模拟器 | 确定、可解释、离线 | 不能代表真实宿主路由；需接入真实 host |
| 池化重复运行计算指标 | 实现简单 | 原始计数被运行次数放大；应按用例报告 |
| 先 round 再与阈值比较 | 报告美观 | 0.79996 被当成 0.8 通过；比较应用原始值 |
| 产物契约用标题 + 词边界正则 | 确定性、可解释 | 不懂语义与否定；需要人或校准过的 judge |
| "必须从失败翻转为通过"才算改进 | 简单的改进定义 | 阻止"提高效率但结果本就正确"的 skill；讲义要的是"无回退" |
| 声明式脚本/安全证据 | harness 不负责执行 | 结果可被伪造，因此需要 provenance + attestation |
| manifest 排除自身、拒绝非规范键 | 避免自引用哈希与路径歧义 | 真实性仍需签名/注册表 |
| demo 运行时现算 manifest | 演示方便 | 源校验成同义反复；生产应读取发布时固定的 manifest |
| 三种状态的能力矩阵 | 显式降级 | 无"有文档的降级"、无必需宿主概念 |
| evidence root + 带外可信摘要 | 区分"本地一致"和"可信采集" | 需要额外的发布基础设施 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 数字下划线 | `MAX_SKILL_BODY_CHARS = 10_000` | 提高大数字可读性，值不变 |
| `frozenset` | `frozenset({".md", ".txt"})` | 不可变集合，适合作常量 |
| 字节正则 | `re.compile(rb"(?i)\b(?:api[_-]?key...)")` | `rb""` 原始字节串，对 `bytes` 做匹配 |
| `str.split(sep, 1)` | `key, value = line.split(":", 1)` | 只切第一处 |
| `list.index(x, start)` | `lines.index("---", 1)` | 从指定位置开始查找 |
| `str.strip(chars)` | `value.strip("\"'")`、`raw_token.strip("()[]{}<>,;:'\"")` | 去掉两端任意属于该集合的字符 |
| f-string 中的正则花括号 | `rf"^#{{1,6}}\s+{re.escape(heading)}..."` | `{{`/`}}` 输出字面花括号；`re.escape` 转义用户文本 |
| lookbehind / lookahead | `(?<!\w)term(?!\w)` | 断言前后不是单词字符 |
| `PurePosixPath` | `PurePosixPath(reference).parts` | 纯路径运算，不访问文件系统，始终按 `/` 解析 |
| `Path.rglob` | `root.rglob("*")` | 递归遍历所有子项 |
| 可调用 dataclass | `KeywordRouter.__call__` | 实例可以像函数一样调用：`router(prompt, run)` |
| `del` 局部变量 | `del run_index` | 显式表示该参数故意不用 |
| 布尔求和 | `sum(want and got for ...)` | `True` 当 1 计数 |
| 嵌套推导式 | `[case.expected for case in cases for _ in observations[case.case_id]]` | 外层循环在前，内层在后 |
| 字典推导式 | `{case.case_id: tuple(...) for case in cases}` | 构造映射 |
| `type(x) is not bool` | `evaluate_evidence_checks` | 精确类型判断，排除 `1`、`0` 等 |
| `isinstance(value, bool)` 先排除 | `ReleaseThresholds.__post_init__` | `bool` 是 `int` 子类，必须先排除 |
| `__post_init__` | `ReleaseThresholds` | dataclass 构造后的校验钩子 |
| `math.isfinite` | 阈值校验 | 拒绝 NaN 与无穷 |
| `Callable[[str, int], bool]` | `router` 参数 | 函数类型注解 |
| `Mapping` / `Sequence` / `Iterable` | 参数注解 | 只要求只读接口，调用方可传 dict/tuple/list |
| 字典解包合并 | `{**installed_manifest, "passed": False, ...}` | 复制并覆盖部分键 |
| 列表解包 | `[*installed_manifest["issues"], "..."]` | 复制列表并追加 |
| `min(..., default=0.0)` | `min(rates.values(), default=0.0)` | 空序列时返回默认值 |
| `hashlib.sha256(...).hexdigest()` | `build_manifest` | 计算十六进制摘要 |
| `json.dumps(..., separators=(",", ":"), sort_keys=True)` | `_canonical_digest` | 规范化序列化，保证字节稳定 |
| `assert` 作类型收窄 | `assert trusted_attestation_digest is not None` | 告诉类型检查器此处非 None |
| `shutil.copytree` | demo | 递归复制整个目录 |
| 默认参数为不可变实例 | `provenance: EvaluationProvenance = EvaluationProvenance()` | 因为是冻结 dataclass，共享默认实例是安全的 |

---

## 6. 运行结果解读

### 6.1 在本仓库副本中直接运行

`python3 main.py`（Python 3.13，退出码 0）。关键字段（完整 JSON 约 6.3 KB）：

```text
checks_passed        : false      ← 讲义说应为 true
fixture_passed       : false      ← 讲义说应为 true
local_evidence_ready : false
trust_anchor_valid   : false
production_ready     : false
passed               : false
evidence_root        : sha256:74e584c2...3821
checks: structure=false，其余 10 项（precision、recall、repeated_runs、with_skill_artifact、
        artifact_improvement、script_correctness、safety、source_manifest、installed_tree、native_hosts）全部 true
lint.issues:
  package-depth : file is not one level deep: SKILL.zh.md
  orphan-file   : SKILL.md does not directly reference 'SKILL.zh.md'
  orphan-file   : SKILL.md does not directly reference 'references/eval-contract.zh.md'
lint.references: assets/hosts.json, assets/manifest.json, evals/artifacts.json, evals/cases.json,
                 evals/evidence.json, references/eval-contract.md, scripts/evaluate_skill.py
triggers.metrics: TP=15, TN=15, FP=0, FN=0, precision=1.0, recall=1.0, accuracy=1.0
repeated_run_rates: 6 个用例全部 1.0
artifacts: baseline 缺 Decision/Evidence 标题与 precision/recall 术语 → false；with_skill → true；improves=true
portability: native-host=native；metadata-only-host=adapter-required（companion-files、script-execution）；
             prompt-only-host=unsupported（core-skill-loader）
trust_anchor.issues: "trusted external attestation was not supplied",
                     "trusted attestation SHA-256 was not supplied out of band"
```

逐项解读：

- **结构层失败的根因**是 bundle 里多出的两个中文翻译文件（见 3.4）。这不是代码逻辑的错误，而是"发布物被翻译流程修改"——恰好演示了讲义说的"stale files"或"安装树里多出来的文件"会被结构层拦下。
- **其余 10 项全部通过**：说明闸门其余机制正常。
- **TP=15、TN=15**：6 个用例 × 5 次运行的池化计数，实际只有 3 正 3 负（测验 Q10）。
- **重复率全为 1.0**：`KeywordRouter` 是确定性的，重复运行在这里没有信息量。
- **`source_manifest` 与 `installed_tree` 为 true**：因为 manifest 是现算的（3.8），而同一 bundle 用交付脚本的 `--fixture-demo` 跑时，`installedTree.unexpected` 正是这两个翻译文件，退出码 1。
- **信任锚两条 issue**：夹具模式下本来就不提供 attestation，这两条是预期内的。

### 6.2 对照实验：去掉翻译文件的副本

为确认根因，我们把整个小节复制到临时目录，**仅在副本中**删除 `SKILL.zh.md` 与 `references/eval-contract.zh.md` 后重跑：

```text
main.py         : checks_passed=True, fixture_passed=True, local_evidence_ready=False,
                  trust_anchor_valid=False, production_ready=False, passed=False
evaluate_skill.py --fixture-demo : checksPassed=True, fixturePassed=True, productionReady=False, passed=False，退出码 0
unittest        : Ran 51 tests ... OK
```

这与讲义描述完全一致：夹具通过、生产未就绪。原仓库文件未做任何修改。

---

## 7. 动手改一改

1. **讲义练习 5**：先 `build_manifest(source)`，`copytree` 到安装目录后修改其中的 `references/eval-contract.md`，调用 `verify_manifest(installed, manifest)`，确认 `mismatched` 中出现该路径；再新建一个文件，确认它出现在 `unexpected`。
2. **按用例报告指标**：在 `trigger_report_from_observations` 中增加 `case_level_metrics`（每个用例取多数票或"全部正确"），与池化指标并列输出；补上 F1。
3. **修正阈值比较**：让 `classification_metrics` 同时返回未取整的 `precision_raw`/`recall_raw`，闸门使用原始值比较；写测试覆盖 19999/25000 的边界。
4. **无回退语义**：把 `artifact_improvement` 改为"with-skill 通过且 baseline 通过时 with-skill 不能失败"，并允许传入多组 `(baseline, with_skill)` 任务对，逐任务报告回退（讲义练习 2）。
5. **问题分级**：给 `LintIssue` 加 `severity` 字段，把 `orphan-file` 改为 `W_ORPHAN_FILE` 警告、`symlink` 等改为 `E_*` 错误，`valid` 只看错误；讨论翻译文件应当是警告还是错误。
6. **讲义练习 4**：给 `HostCapabilities` 加一项 `runs_lifecycle_hooks`，并在 `portability_matrix` 中引入第四种状态 `degraded`（需要 `fallbacks` 字典里有对应条目），没有文档化回退的缺失能力仍然是 `adapter-required` 或 `unsupported`。

---

## 8. 常见坑

- **把 `checks_passed` 当 `passed`**：前者只说明各层检查通过，`passed` 还需要 captured 证据与外部信任锚。
- **在源目录上做"安装测试"**：代码专门拒绝 `installed_root == package_root`；还要确保 manifest 是发布时固定的，而不是测试时现算的。
- **把可信摘要放进 bundle**：等于没有信任锚。
- **只看池化的 100%**：要看用例数，并把重复运行的一致性单独报告。
- **以为词法契约能判断语义**：否定句、多余空格、同义词都会让结果出错。
- **用 `isinstance(x, int)` 校验整数**：`True` 也会通过；本文件用 `type(x) is int` 或先排除 `bool`。
- **id 或主机名两侧带空格**：`"same-host"` 与 `"same-host "` 看起来不同，实际是同一身份；本文件统一拒绝两侧空白。
- **翻译/文档工具改写发布物**：任何进入 bundle 目录的文件都会被结构层和 manifest 层审查（本副本的 demo 失败就是这样来的）。

---

## 9. 测试在验证什么

运行方式（在 `code/` 目录下）：`python3 -m unittest discover -s tests -v`。测试文件设置了 `sys.dont_write_bytecode = True`，但用 `discover` 运行时 `unittest` 导入测试模块本身仍会生成 `tests/__pycache__`（本次运行后已删除）。

**实际结果**：`Ran 51 tests in 0.389s — FAILED (failures=2)`。失败的两个是：

- `test_shipped_bundle_evaluator_gates_every_taught_layer`：断言交付 bundle 的 `checksPassed` 为真，实际为假；
- `test_relabelled_local_fixtures_need_external_trust_anchor`：在安装副本中重标为 captured 并重建 manifest 后断言 `checksPassed` 为真，实际为假（manifest 重建后包含了翻译文件，`installedTree` 通过，但 `structure` 仍因 `package-depth`/`orphan-file` 失败）。

两者的根因都是 bundle 中的 `SKILL.zh.md` 与 `references/eval-contract.zh.md`；在删除这两个文件的副本中，51 个测试全部通过。

测试分组说明（`make_bundle` 夹具会在临时目录生成一个最小合法包 `release-check`；`load_bundled_evaluator` 用 `importlib` 加载交付脚本 `outputs/skill-release-gate/scripts/evaluate_skill.py`，大量测试要求"课程版 `main.py` 与交付脚本两个 linter 行为一致"）：

| 分组 | 代表测试 | 验证的性质 |
|------|---------|-----------|
| 结构 lint（两个实现一致） | `test_valid_package_passes_structural_lint`、`test_folded_description_is_parsed_during_lint`、`test_directory_name_mismatch_fails_lint`、`test_non_kebab_identity_fails_both_linters`、`test_duplicate_frontmatter_field_fails_both_linters`、`test_malformed_top_level_frontmatter_fails_both_linters`、`test_missing_direct_reference_fails_lint`、`test_orphan_file_fails_lint`、`test_output_and_failure_sections_are_required_by_both_linters`、`test_runtime_extension_requires_explicit_allowlist_in_both_linters`、`test_referenced_obvious_secret_fails_both_linters`、`test_companion_type_and_size_policies_match_both_linters`、`test_body_budget_matches_both_linters` | 合法包通过；折叠 description 能解析；名称/目录不符、非 kebab、重复字段、畸形行、缺引用、孤儿文件、缺必需段落、未允许的扩展字段（允许后通过）、`api_key=` 秘密、`.exe` 后缀、超过 1,000,000 字节、正文超过 10,000 字符都被拒 |
| 物理树预检与路径 | `test_bundled_lint_rejects_symlinked_bundle_directory`、`test_bundled_cli_preserves_and_rejects_symlinked_root`、`test_bundled_preflight_rejects_entry_symlink_before_json_read`、`test_bundled_lint_rejects_traversal_reference`、`test_bundled_lint_rejects_malformed_reference_prefix`、`test_lesson_lint_rejects_complete_traversal_reference`、`test_bundled_lint_flags_symlinked_companion` | 根目录 symlink（CLI 退出码 2）、入口 symlink 在读 JSON 前被拒、`..` 引用、畸形前缀、symlink 附属文件 |
| 触发评估 | `test_precision_and_recall_use_confusion_counts`、`test_trigger_eval_includes_positive_and_near_miss`、`test_repeated_run_rate_is_measured_per_case`、`test_trigger_digest_binds_every_raw_prediction`、`test_trigger_case_ids_are_unique_and_non_empty_at_gate_boundary`、`test_trigger_prompts_reject_blank_and_surrounding_whitespace` | 混淆计数正确（0.5/0.5）；正例 + near miss 全对；逐用例重复率；摘要绑定每个原始预测；id/提示的唯一性与空白规则 |
| 证据与产物 | `test_evidence_ids_reject_blank_and_whitespace_variants`、`test_with_skill_artifact_can_improve_contract_pass`、`test_artifact_assertions_use_exact_boundaries` | 证据 id 规则；with-skill 让契约从失败变通过；`# Decision-making` 不算 `Decision`、`Recalling` 不算 `recall` |
| 可移植性 | `test_portability_matrix_distinguishes_native_adapter_and_unsupported`、`test_duplicate_host_identity_cannot_satisfy_native_host_threshold`、`test_host_gate_cannot_pass_vacuously`、`test_bundled_duplicate_hosts_cannot_meet_native_host_threshold` | 三种状态；重复主机名不能凑数；`min_native_hosts=0` 被拒 |
| 闸门整体 | `test_fixture_gate_passes_checks_without_claiming_production_readiness`、`test_local_provenance_needs_a_trusted_attestation`、`test_release_gate_fails_weak_trigger_precision`、`test_release_gate_blocks_failed_script_and_safety_layers`、`test_release_gate_blocks_installed_tree_drift`、`test_release_gate_rejects_invalid_thresholds_and_case_shape` | 夹具通过但不声称生产就绪；captured + 本地摘要一致仍需 attestation，提供后 `passed=True`；"总是触发"的路由器 precision 不达标；脚本/安全失败阻断；安装树被改后 `mismatched=["scripts/check.py"]`；非法阈值与用例形状 |
| Manifest | `test_manifest_rejects_parent_paths`、`test_manifest_rejects_noncanonical_posix_keys`、`test_reserved_manifest_is_excluded_from_its_own_domain`、`test_bundled_manifest_rejects_unknown_version_and_algorithm`、`test_bundled_manifest_detects_installed_tree_drift` | `../SKILL.md`、`./SKILL.md` 被拒；保留路径不得列入；未知 `manifestVersion`/`algorithm`（如 md5）fail closed；安装后改 reference 被发现 |
| 交付脚本的模式与配置 | `test_bundled_artifact_and_evidence_modes_fail_closed`、`test_bundled_evaluator_rejects_zero_runs`、`test_bundled_configuration_rejects_blank_prompts`、`test_bundled_captured_observations_reject_duplicate_case_ids`、`test_malformed_config_root_is_structured_cli_failure` | 未知模式 fail closed；`runs=0` 被拒；空白提示被拒；captured 观测的重复 id 被拒；`cases.json` 根不是对象时 CLI 以退出码 2 输出结构化错误、无 Traceback |
| 交付 bundle 端到端 | `test_shipped_bundle_evaluator_gates_every_taught_layer`、`test_relabelled_local_fixtures_need_external_trust_anchor` | 交付 bundle 夹具通过但不生产就绪；重标 + 重算摘要可以得到 `localEvidenceReady`，但 attestation 放在 bundle 内会被拒（"outside the bundle"），放在外部且摘要匹配时 CLI 退出码 0、`passed=True`（**这两个测试在本副本中失败，原因见上**） |
