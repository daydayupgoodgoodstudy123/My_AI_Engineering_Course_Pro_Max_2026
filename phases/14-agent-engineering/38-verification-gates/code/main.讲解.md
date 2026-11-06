# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 38 节 Verification Gates ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py [--strict] [--floor 0.8]`；要演示签名 override 需加环境变量 `VERIFY_DEMO_MODE=1`（或设置 `VERIFY_OVERRIDE_SECRET`） ｜ **依赖**：仅标准库（`argparse`、`hmac`、`hashlib`、`json`、`math`、`os`、`sys`、`time`、`dataclasses`、`pathlib`）；运行时会在 `code/` 下写 `verification_report_T-00x.json`，演示 override 时还会追加 `overrides.jsonl`

---

## 1. 这份代码在考察什么

这份代码实现了讲义中的 verification gate：一个**确定性**的函数，读取任务的各类产物，给出"任务是否真的完成"的结论。对应讲义的概念：

1. **把多种产物合成一个结论**：验收命令记录（feedback）、scope 报告、rule 报告、覆盖率报告 → findings → `passed`。
2. **block / warn 两级严重度**：任何 block 都让 `passed=False`；warn 只是注释。
3. **覆盖率下限与回归检查**（生产模式）：低于 80% 或比上次下降超过 1 个百分点 → block。
4. **`--strict` 模式**：把所有 warn 升级为 block。
5. **签名 override**：用 HMAC-SHA256 给 override 条目签名，并在没有密钥时 fail closed。
6. **不用 LLM**：整个 gate 里没有任何模型调用。

> 一句话：**agent 说"完成了"不算数，gate 读完产物说"完成了"才算数**。阅读时也要留意它在"产物缺失时 fail open"、"重试被判失败"、"与第 37 节记录格式不兼容"、"override 写了却不生效"等地方的简化。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `COVERAGE_FLOOR_DEFAULT` / `COVERAGE_REGRESSION_DELTA` | 常量 | 0.80 / 0.01 | 覆盖率下限、回归阈值 |
| `_load_override_secret` | 函数 | 读密钥；无密钥且非 demo 模式时抛错 | fail closed |
| `Finding` | dataclass | 一条检查结果 | finding |
| `Artifacts` | dataclass | gate 的全部输入 | 工作台产物 |
| `VerdictReport` | dataclass | gate 的输出 | `verification_report.json` |
| `_acceptance_findings` | 函数 | 验收命令是否运行、是否退出 0；任何 null 退出码 | 验收检查 |
| `_scope_findings` | 函数 | forbidden → block，越界 → warn | scope 检查 |
| `_rule_findings` | 函数 | 每条未通过的规则 → block | rule 检查 |
| `_coverage_findings` | 函数 | 下限、回归、缺失 | 覆盖率检查 |
| `verify` | 函数 | 拼接 findings、可选 strict、计算 `passed` | gate 主函数 |
| `_sign` / `record_override` / `verify_signature` | 函数 | HMAC 签名、追加 override、验签 | 签名 override |
| `main` | 函数 | 解析参数、跑三个场景、写报告、演示 override | demo |

数据流：`argparse` → 三个 `Artifacts` → `verify()`（acceptance + scope + rule + coverage → strict 升级 → `passed`）→ 写 `verification_report_<task>.json` 并打印 → `record_override` 演示（无密钥时跳过）。

---

## 3. 逐段精讲

### 3.1 密钥加载：fail closed

```python
_OVERRIDE_SECRET_ENV = "VERIFY_OVERRIDE_SECRET"
_DEMO_MODE_ENV = "VERIFY_DEMO_MODE"

def _load_override_secret() -> str:
    secret = os.environ.get(_OVERRIDE_SECRET_ENV)
    if secret:
        return secret
    if os.environ.get(_DEMO_MODE_ENV) == "1":
        print(f"WARNING: ... using insecure demo secret. ...", file=sys.stderr)
        return "demo-override-secret-do-not-ship"
    raise RuntimeError(f"refused to start: {_OVERRIDE_SECRET_ENV} is unset. ...")
```

- 三种情况：有密钥用密钥；显式开启 demo 模式才用硬编码的演示密钥，并向 stderr 大声警告；否则**拒绝**。这就是 fail closed：配置缺失时选择"不工作"而不是"用一个不安全的默认值继续工作"。
- 警告写到 `sys.stderr`，不会混进标准输出（CI 中通常单独显示）。
- 每次 `_sign` 都会调用一次这个函数，所以 demo 模式下警告会打印两次（一次签名、一次验签），实测如此。

### 3.2 输入与输出的数据结构

```python
@dataclass
class Artifacts:
    task_id: str
    acceptance_commands: list[str]
    feedback: list[dict[str, object]]
    scope_report: dict[str, object]
    rule_report: list[dict[str, object]]
    coverage_report: dict[str, float] | None = None  # {"current": 0.84, "previous": 0.85}
    head_commit: str = ""
```

- `feedback` 期望每条记录至少有 `command` 与 `exit_code` 两个键——它是第 37 节 JSONL 的简化版。
- `scope_report` 期望有 `forbidden_writes`、`off_scope_writes` 两个键——对应第 36 节的 `ScopeReport`。
- `rule_report` 是 `[{"slug": ..., "passed": ...}]`——对应第 33 节的规则报告。
- ⚠️ 讲义说 gate 还读取 **diff**（检查表最后一行"Touched files match `scope.allowed_files`"），代码中没有 diff 输入，这一项未实现。
- ⚠️ 除 `coverage_report` 外，其他字段都不能为 `None`，于是"产物不存在"只能用空列表/空字典表示，和"产物存在但为空"无法区分（见 3.7）。
- `VerdictReport` 中 `passed` 是计算出来的；`coverage`、`head_commit` 原样带进报告，便于审计。

### 3.3 验收检查

```python
def _acceptance_findings(art: Artifacts) -> list[Finding]:
    findings: list[Finding] = []
    commands_run = [str(rec.get("command")) for rec in art.feedback]
    accept_set = set(art.acceptance_commands)
    for cmd in art.acceptance_commands:
        if cmd not in commands_run:
            findings.append(Finding("acceptance.missing", "block", f"never ran: {cmd}"))
    for rec in art.feedback:
        cmd_str = str(rec.get("command"))
        if rec.get("exit_code") is None:
            findings.append(Finding("feedback.null_exit", "block", f"missing exit for {cmd_str}"))
        elif rec.get("exit_code") != 0 and cmd_str in accept_set:
            findings.append(Finding("acceptance.failed", "block", f"acceptance exit {rec.get('exit_code')} on {cmd_str}"))
    return findings
```

对应讲义检查表的前两行和"No `null` exit codes"：

| 情况 | finding |
|------|---------|
| 验收命令在 feedback 中找不到 | `acceptance.missing`（block） |
| **任何**记录 `exit_code is None` | `feedback.null_exit`（block） |
| 验收命令的某条记录退出码非 0 | `acceptance.failed`（block） |

- `set(...)` 让 `cmd_str in accept_set` 是 O(1) 查找。
- ⚠️ **与第 37 节不兼容**：第 37 节记录的 `command` 是 argv **列表**，`str(["pytest", "-x", ...])` 得到 `"['pytest', '-x', ...]"`，与合同里的字符串永远不相等，结果恒为 `acceptance.missing`（实测）。需要 `shlex.join` 之类的规范化，或者给验收命令一个 ID。
- ⚠️ **重试被判失败**：第二个循环看**每一条**记录。"第一次失败、修复后重跑成功"会因为第一条记录而被 block（实测 `retry False [('block', 'acceptance.failed')]`）。应只看每条验收命令的**最新**记录，并要求它晚于最后一次代码修改。
- ⚠️ `null_exit` 对所有记录生效，包括与验收无关的探测命令；这与讲义检查表一致，但实践中偏严。

### 3.4 Scope 与 rule 检查

```python
def _scope_findings(art: Artifacts) -> list[Finding]:
    findings: list[Finding] = []
    if art.scope_report.get("forbidden_writes"):
        findings.append(Finding("scope.forbidden", "block", ...))
    if art.scope_report.get("off_scope_writes"):
        findings.append(Finding("scope.off_scope", "warn", ...))
    return findings


def _rule_findings(art: Artifacts) -> list[Finding]:
    return [Finding("rule.failed", "block", f"rule failed: {row.get('slug')}")
            for row in art.rule_report if not row.get("passed")]
```

- 讲义说越界写入"block or warn"，代码选了 warn；第 36 节的 violation budget 没有在这里体现。
- `.get(...)`：键不存在返回 `None`（假值），于是 scope 报告缺键会被当作"没有越界"——fail open。
- `_rule_findings` 用带条件的列表推导式一次生成所有失败规则的 finding；`not row.get("passed")` 让缺少 `passed` 键的行也算失败（这一点是 fail closed）。
- ⚠️ 讲义说"All block-severity rules pass"，但代码把**所有**未通过的规则都当作 block，并不区分规则自身的严重度。

### 3.5 覆盖率检查

```python
def _coverage_findings(art: Artifacts, floor: float) -> list[Finding]:
    findings: list[Finding] = []
    if not art.coverage_report:
        findings.append(Finding("coverage.missing", "warn", "no coverage_report.json; cannot enforce floor"))
        return findings
    current = float(art.coverage_report.get("current", 0.0))
    previous = float(art.coverage_report.get("previous", current))
    if current < floor:
        findings.append(Finding("coverage.below_floor", "block", ...))
    delta = previous - current
    if delta > COVERAGE_REGRESSION_DELTA and not math.isclose(delta, COVERAGE_REGRESSION_DELTA, rel_tol=1e-9):
        findings.append(Finding("coverage.regression", "block", ...))
    elif delta > 0 and not math.isclose(delta, 0.0, abs_tol=1e-12):
        findings.append(Finding("coverage.minor_regression", "warn", ...))
    return findings
```

- 缺失（`None` 或空字典 `{}`）→ warn，然后**提前返回**。
- `previous` 缺省等于 `current`，即"没有历史就不算回归"。
- **浮点边界**：`0.85 - 0.84 == 0.010000000000000009`，严格大于 0.01。代码用 `math.isclose(..., rel_tol=1e-9)` 把"恰好 1 个百分点"排除在 block 之外。实测边界：

| previous → current | 结果 |
|-------------------|------|
| 0.85 → 0.84 | `coverage.minor_regression`（warn） |
| 0.81 → 0.80 | `coverage.minor_regression`（warn） |
| 0.85 → 0.839 | `coverage.regression`（block） |
| 0.80 → 0.80 | 无 |
| 0.85 → 0.62（T-002） | `below_floor` + `regression`（两个 block） |

- `math.isclose(delta, 0.0, abs_tol=1e-12)`：与 0 比较时**必须**用 `abs_tol`，因为相对误差对 0 没有意义。
- ⚠️ `--floor` 没有校验：误传 `--floor 80`（以为是百分比）会让任何覆盖率都低于下限（实测 0.95 也报 `below_floor`）。
- 讲义："The gate fails if measured coverage drops below the floor or below the previous merge's floor by more than 1 percentage point."代码与之一致。

### 3.6 `verify`：拼接、升级、判定

```python
def verify(art: Artifacts, strict: bool = False, coverage_floor: float = COVERAGE_FLOOR_DEFAULT) -> VerdictReport:
    findings = (
        _acceptance_findings(art)
        + _scope_findings(art)
        + _rule_findings(art)
        + _coverage_findings(art, coverage_floor)
    )
    if strict:
        findings = [Finding(f.code, "block" if f.severity == "warn" else f.severity, f.detail)
                    for f in findings]
    blocking = [f for f in findings if f.severity == "block"]
    return VerdictReport(task_id=art.task_id, passed=not blocking, strict=strict, findings=findings,
                         coverage=art.coverage_report, head_commit=art.head_commit)
```

- 四个子函数各返回一个列表，用 `+` 拼接，顺序固定 → 输出确定。
- strict 模式构造**新的** `Finding` 对象而不是修改原对象，避免副作用。
- `passed=not blocking`：空列表为假，`not []` 为 `True`。
- 这是一个纯函数：不读文件、不读时间、不调用网络，同样的 `Artifacts` 永远得到同样的报告——讲义"Deterministic, not probabilistic"。
- ⚠️ 讲义签名是 `verify(task_id, artifacts)`，代码是 `verify(art, strict, coverage_floor)`（`task_id` 在 `art` 里）。
- ⚠️ 结论里没有考虑任何 override（见 3.8）。

### 3.7 fail open 还是 fail closed？

把各个产物"缺失或为空"时的行为汇总（均实测或由代码可见）：

| 情况 | 本代码 | skill 要求 |
|------|-------|-----------|
| 没有验收命令 | 不检查，可能通过 | 拒绝上线 gate |
| feedback 为空 | 只有验收命令存在时才报 missing | 缺失日志本身就是 block |
| rule report 为空/缺失 | 视为全部通过 | fail closed |
| scope report 缺键 | 视为没有越界 | — |
| 覆盖率缺失 | warn | — |

`Artifacts(task_id="T", acceptance_commands=[], feedback=[], scope_report={}, rule_report=[], coverage_report={"current": 0.9, "previous": 0.9})` 的结论是 `passed=True`、findings 为空——一个什么都没证明的任务通过了 gate。

### 3.8 签名 override

```python
def _sign(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_load_override_secret().encode(), canonical, hashlib.sha256).hexdigest()[:32]
```

- **规范化（canonicalization）**：`sort_keys=True` 固定键顺序，`separators=(",", ":")` 去掉空格，保证同一个字典总是序列化成同一个字节串，签名才可复现。
- HMAC-SHA256：用共享密钥对消息做带密钥的哈希；不知道密钥就无法伪造。截断为 32 个十六进制字符（128 位）。

```python
def record_override(task_id, finding_code, reason, user_id, head_commit):
    if not all([task_id, finding_code, reason, user_id, head_commit]):
        raise ValueError("override requires task_id, finding_code, reason, user_id, head_commit")
    payload = {..., "ts": time.time()}
    payload["signature"] = _sign({k: v for k, v in payload.items() if k != "signature"})
    with OVERRIDES_PATH.open("a") as fh:
        fh.write(json.dumps(payload) + "\n")
    return payload


def verify_signature(entry: dict[str, object]) -> bool:
    expected = entry.get("signature")
    payload = {k: v for k, v in entry.items() if k != "signature"}
    return hmac.compare_digest(_sign(payload), str(expected))
```

- `all([...])`：五个字段都非空才允许记录。
- 签名时排除 `signature` 字段本身；验签时同样排除后重新计算再比较。
- `hmac.compare_digest`：**常数时间**比较，防止通过比较耗时推测签名（时序攻击）。普通 `==` 在第一个不同字符处就返回。
- 实测：篡改 `reason` 后 `verify_signature` 返回 `False`。
- ⚠️ 缺口（详见测验 Q12）：
  - 不校验 `finding_code` 是否真实存在、是否为 block——`record_override("T-999", "made.up.code", ...)` 照样签名成功、验签为 `True`；
  - demo override 的是 T-002 的 `scope.off_scope`（一个 warn），而 T-002 还有 4 条 block，这次 override 对结论毫无影响；
  - `verify()` 从不读取 `overrides.jsonl`，override 只是日志，不改变结论；
  - HMAC 证明的是"持有共享密钥"，`user_id` 是调用方自填的；agent 环境里若有这个密钥，就能以任何人的名义签名；
  - `overrides.jsonl` 写在 `code/` 下，讲义要求 `outputs/verification/overrides.jsonl` 且纳入版本控制。

### 3.9 `main()`：三个场景

```python
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="promote every warn to block")
    ap.add_argument("--floor", type=float, default=COVERAGE_FLOOR_DEFAULT)
    args = ap.parse_args()
```

| 场景 | 设计意图 | 输入要点 |
|------|---------|---------|
| T-001 | clean pass | 验收跑过且退出 0，覆盖率 0.85 → 0.84 |
| T-002 | scope creep | 写了 `scripts/release.sh`（forbidden）和 `README.md`（越界），规则失败，覆盖率 0.80 → 0.62 |
| T-003 | missing acceptance | feedback 为空，规则 `done/tests-pass` 失败，无覆盖率报告 |

- 报告写到 `HERE / f"verification_report_{art.task_id}.json"`，即 `code/` 目录。⚠️ 讲义要求唯一路径 `outputs/verification/<task_id>.json`（"Multiple gates with different paths fork the source of truth"），mission 的验收标准也写的是 `outputs/verification/`；skill 还要求报告列出所消费的产物路径，代码都没有做到。
- override 演示包在 `try/except RuntimeError` 中：默认没有密钥时打印"override demo skipped"，脚本仍然退出 0。
- mission 把签名 override 列为 out of scope（"The exercise prompts extend the gate that way"），但代码已经实现了；讲义练习 1、2（覆盖率下限、`--strict`）也已在代码中实现。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯函数 `verify`、无 LLM | 确定性、可复现、不可被说服 | 无法判断质量与风格，交给 reviewer |
| findings 列表 + 严重度 | 结论可解释、可审计 | 规则自身的严重度没有被区分 |
| 越界写入定为 warn | 避免 gate 过严被关闭 | 与第 36 节的预算/路径族严重度没有打通 |
| `isclose` 处理 1pp 边界 | 避免浮点误差让恰好 1pp 的下降变成 block | 更稳妥的是用整数基点（basis points）存覆盖率 |
| 覆盖率缺失只 warn | 不强迫所有项目都有覆盖率 | 发布分支应 block；strict 会自动升级 |
| `--strict` 构造新 Finding | 无副作用 | 会让正常的小幅波动也失败，只应在发布分支开启 |
| 无密钥时拒绝 override | fail closed | — |
| HMAC 共享密钥签名 | 标准库即可实现、可防篡改 | 不能证明是哪个人；生产用个人签名或审批系统 |
| 报告写在 `code/` | demo 简单 | 应写唯一路径 `outputs/verification/<task_id>.json` 并列出输入产物 |
| 产物缺失按空处理 | 代码简单 | fail open；应区分 `None` 与空并 fail closed |
| 验收比较用 `str(command)` | 简单 | 与第 37 节 argv 记录不兼容；应规范化或用 ID |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `argparse` | `ap.add_argument("--strict", action="store_true")`、`type=float, default=...` | 命令行参数解析；`store_true` 表示出现即为 True |
| `os.environ.get` | `os.environ.get(_OVERRIDE_SECRET_ENV)` | 读环境变量，不存在返回 `None` |
| `print(..., file=sys.stderr)` | 警告信息 | 输出到标准错误 |
| `raise RuntimeError(...)` / `except RuntimeError as exc` | `_load_override_secret`、`main` 末尾 | 抛出并捕获异常 |
| `raise ValueError` | `record_override` 参数校验 | 参数不合法时的惯用异常 |
| `@dataclass` + `field(default_factory=list)` | `VerdictReport.findings` | 可变默认值用工厂 |
| 类型注解 `dict[str, object]`、`dict[str, float] \| None` | `Artifacts` 字段 | 描述数据形状，运行时不强制 |
| `dict.get(key, default)` | `art.coverage_report.get("previous", current)` | 键不存在时返回默认值 |
| 列表拼接 | `_acceptance_findings(art) + _scope_findings(art) + ...` | `+` 连接列表 |
| 带条件的列表推导式 | `[Finding(...) for row in art.rule_report if not row.get("passed")]` | 过滤 + 映射 |
| 条件表达式 | `"block" if f.severity == "warn" else f.severity` | 三元表达式 |
| `not []` | `passed=not blocking` | 空列表为假 |
| `math.isclose` | `math.isclose(delta, 0.01, rel_tol=1e-9)`、`abs_tol=1e-12` | 浮点比较；与 0 比较要用 `abs_tol` |
| f-string 百分比格式 | `f"{current:.2%}"`、`f"{floor:.0%}"` | 0.62 → `62.00%`；0.8 → `80%` |
| 字典推导式 | `{k: v for k, v in payload.items() if k != "signature"}` | 去掉某个键 |
| `all([...])` | `all([task_id, finding_code, reason, user_id, head_commit])` | 全部为真才为真 |
| `json.dumps(sort_keys=True, separators=(",", ":"))` | `_sign` | 规范化序列化 |
| `hmac.new(...).hexdigest()` | `_sign` | HMAC-SHA256，输出十六进制字符串 |
| `hmac.compare_digest` | `verify_signature` | 常数时间比较 |
| 字符串切片 | `.hexdigest()[:32]` | 取前 32 个字符 |
| `with path.open("a")` | 追加 `overrides.jsonl` | 追加模式 |
| `asdict` | `[asdict(f) for f in report.findings]` | dataclass → dict |
| 模块级"私有"命名 | `_load_override_secret`、`_sign` | 前导下划线表示内部使用的约定 |

---

## 6. 运行结果解读

默认运行（Python 3.13，在临时目录副本中执行，未设置任何环境变量，退出码 0）：

```text
task T-001: passed=True findings=1
  [warn] coverage.minor_regression: coverage dropped 1.00%

task T-002: passed=False findings=5
  [block] scope.forbidden: forbidden writes: ['scripts/release.sh']
  [warn] scope.off_scope: off-scope writes: ['README.md']
  [block] rule.failed: rule failed: forbidden/no-release-script-edits
  [block] coverage.below_floor: coverage 62.00% below floor 80%
  [block] coverage.regression: coverage dropped 18.00% (prev 80.00% -> 62.00%)

task T-003: passed=False findings=3
  [block] acceptance.missing: never ran: pytest -x test_app.py::test_signup_rejects_short_password
  [block] rule.failed: rule failed: done/tests-pass
  [warn] coverage.missing: no coverage_report.json; cannot enforce floor

override demo skipped: refused to start: VERIFY_OVERRIDE_SECRET is unset. Set the env var, or pass VERIFY_DEMO_MODE=1 to run the lesson demo only.
```

逐项解读：

- **T-001**：唯一的 finding 是 1 个百分点的覆盖率下降（`isclose` 让它停在 warn），`passed=True`——clean pass。
- **T-002**：scope creep 场景。forbidden 写入、规则失败、覆盖率低于下限、下降 18 个百分点，共 4 条 block；README 越界是 warn。注意：第 36 节中 `README.md` 属于文档软路径（info），这里的 demo 数据把它放进了 `off_scope_writes`，两节课的数据约定并不一致。
- **T-003**：feedback 为空 → 验收命令从未运行；没有覆盖率报告 → warn。
- **override**：没有密钥，fail closed，演示被跳过。

`--strict` 运行：三个任务全部 `passed=False`。T-001 的 `minor_regression` 被升级为 block；T-002 的 `scope.off_scope`、T-003 的 `coverage.missing` 也变成 block。

`VERIFY_DEMO_MODE=1` 运行：前面的输出相同，末尾多出：

```text
WARNING: VERIFY_OVERRIDE_SECRET unset and VERIFY_DEMO_MODE=1; using insecure demo secret. ...   ← 签名时
WARNING: VERIFY_OVERRIDE_SECRET unset and VERIFY_DEMO_MODE=1; using insecure demo secret. ...   ← 验签时
override recorded: signature=5b82636f9a9968f5ec267648b66ebc1e verified=True
```

签名值包含时间戳 `ts`，每次运行不同。`overrides.jsonl` 新增一行，但 T-002 的报告不会因此改变。

补充实验（均实测）：

| 输入 | 结论 |
|------|------|
| feedback 的 `command` 是 argv 列表（第 37 节格式） | `acceptance.missing`（block） |
| 验收命令先失败后成功 | `acceptance.failed`（block） |
| 所有产物为空、无验收命令 | `passed=True`，无 finding |
| 一条无关探测命令 `exit_code=None` | `feedback.null_exit`（block） |
| 伪造 `record_override("T-999", "made.up.code", ...)` | 验签 `True` |

---

## 7. 动手改一改

1. **命令规范化与重试**：用 `shlex.join` 规范化命令，只看每条验收命令的最新记录（参考测验 Q9、Q10）；再要求验收记录的时间晚于"最后一次写文件"的时间。
2. **fail closed**：把 `Artifacts` 的字段改成可为 `None`，实现 `fail_closed_findings`（参考测验 Q11），让"没有验收命令""没有 rule report"都成为 block。
3. **让 override 生效**：实现 `apply_overrides(report, entries, head_commit)`，只接受签名有效、task 与 HEAD 匹配、且针对 block 级 finding 的条目；在报告中保留 `overridden` 状态而不是删除 finding（参考测验 Q12）。
4. **一份报告、一个路径**：报告写到 `outputs/verification/<task_id>.json`，并加入 `inputs` 字段列出消费的产物路径与它们的哈希。
5. **讲义练习 3**：在 JSON 之外生成 Markdown 摘要，只包含结论、block 列表、override、HEAD、产物路径；说明为什么 warn 的细节可以折叠。
6. **讲义练习 4（思考题）**：实现 `time_since_last_human_touch`——人类在 60 秒内编辑过的文件不计越界。讨论它如何被滥用（agent 伪造"人类编辑"的时间戳），以及时间戳应由谁记录。

---

## 8. 常见坑

- **把"空"当"通过"**：没有验收命令、没有规则报告、scope 报告缺键都会让 gate 静默通过。缺失必须 fail closed。
- **字符串比较命令**：argv 列表与字符串、多余空格、等价写法都会造成误判；用规范化或命令 ID。
- **重试历史与结论混淆**：所有失败记录都 block 会逼 agent 删除记录；只看最新记录又可能用到过期的结果。需要"最新 + 晚于最后一次修改 + 保留链条给 reviewer"。
- **浮点比较阈值**：`0.85 - 0.84 > 0.01` 为真；用 `math.isclose` 或整数基点。与 0 比较时 `rel_tol` 无效，要用 `abs_tol`。
- **`--floor` 的单位**：0.8 而不是 80。
- **把 HMAC 当成个人签名**：共享密钥只能证明"有人持有密钥"。
- **写了 override 却不生效**：override 日志必须被 gate 读取并反映在结论中，否则只是"override 剧场"的另一种形式。
- **strict 当默认**：会让日常小波动全部失败，团队很快会绕开 gate。
- **在课程目录直接运行**：会在 `code/` 下生成报告和 `overrides.jsonl`。
