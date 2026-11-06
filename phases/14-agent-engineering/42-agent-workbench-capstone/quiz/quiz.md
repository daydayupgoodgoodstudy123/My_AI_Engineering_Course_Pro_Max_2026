# 测验 · 综合项目：交付可复用的 Agent 工作台包（Capstone: Ship a Reusable Agent Workbench Pack）

> **阶段 14 · Agent 工程 · 第 42 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Workbench pack | 把七个 surface 压缩成一个带版本号、可 `cp -r` 的目录：`AGENTS.md`、`docs/`、`schemas/`、`scripts/`、`bin/install.sh`、`README.md`、`VERSION` |
| 2 | 放进 pack 的三类东西 | schema 是契约（contract）、四个脚本是运行时（runtime）、四份文档是规则与评分标准（rules & rubric） |
| 3 | 留在 pack 外的三类东西 | 具体项目的任务（属于目标仓库的 board）、厂商 SDK 调用（pack 与框架无关）、入职说明文字（pack 与团队 onboarding 并列而非包含） |
| 4 | 安装器四件事 | 讲义：无 `--force` 拒绝覆盖；复制 pack；若存在 `.github/workflows/` 则接入 CI；打印下一步。本节实现只做了 1、2、4，并额外写 `.workbench-version` |
| 5 | `VERSION` 是契约 | 需要迁移的 schema/脚本变更 bump major；讲义 Production 部分补充 minor 需重跑检查器、patch 仅文档；目标仓库记录安装时的版本 |
| 6 | 单一来源、多工具分发 | 讲义：用 `ln -s AGENTS.md CLAUDE.md` 等符号链接让一个源头分发到所有 coding agent；为某个工具 fork pack 是失败模式 |
| 7 | 卸载器不碰用户状态 | 只删 schemas、scripts、docs、`AGENTS.md`（可 `--keep-agents-md`），绝不删 `agent_state.json`、`task_board.json`、`outputs/`；状态文件有未提交改动时拒绝执行 |
| 8 | 组装脚本的幂等性 | `main.py` 每次都用同样的字符串常量覆盖写出，重复运行内容不变（实测与仓库中已提交的 `outputs/` 完全一致） |
| 9 | Gate 必须 fail-closed | 本节打包的 `verify_agent.py` 在缺少 scope contract 时 `acceptance` 为空，直接 `passed: true`——这是"缺证据即放行"的 fail-open 缺陷 |
| 10 | 规则必须有检查函数 | skill 的 Hard reject："Rules without a corresponding check function"；而 pack 的 `agent-rules.md` 中 5 个 `check:` 名在 `scripts/` 里都没有实现 |

### 核心技能（能动手做到）

- [ ] 画出 pack 的目录树，说出每个文件对应哪一节（33–40）的哪个 surface
- [ ] 读懂 `bin/install.sh`：`set -euo pipefail`、`PACK_ROOT` 的求法、`--force` 判断、`cp -r dir/.` 的语义，并在空目录中实际安装一次
- [ ] 用 `run_with_feedback.py -- <命令>` 记录一次命令执行，再用 `verify_agent.py` 跑 gate，解释每条 finding 的来源
- [ ] 找出本 pack 中至少三处"契约不一致"（字段名、版本记录位置、规则无实现）并写出 `lint_pack.py` 检查它们
- [ ] 把 gate 改成 fail-closed：缺 contract、acceptance 为空、只看最新一次运行
- [ ] 设计一个安全的 `uninstall.sh` 与版本升级（major bump）迁移手册

---

## 二、基础自测（选择题）

**Q1.** 按讲义"What stays in, what stays out"，下列哪一项应当**留在 pack 之外**？

- A. `scope_contract.schema.json`
- B. 本项目下周要做的具体任务列表
- C. `scripts/verify_agent.py`
- D. `docs/reviewer-rubric.md`

**Q2.** 某次 pack 更新只修改了 `docs/handoff-protocol.md` 的措辞，没有动 schema 和脚本。按讲义的版本规则，应当：

- A. bump major，因为任何改动都可能影响 agent 行为
- B. bump minor，并重跑检查器
- C. 不需要改版本号
- D. bump patch

**Q3.** 在一个全新的空目录中执行 `bash <pack>/bin/install.sh` 成功后，**不带 `--force`** 再执行一次，实际结果是：

- A. 打印 `AGENTS.md already exists. Pass --force to overwrite.`，退出码 1
- B. 静默覆盖所有文件，退出码 0
- C. 只更新 `.workbench-version`
- D. 先卸载旧 pack 再重新安装

**Q4.** 讲义推荐 pack 支持 Claude Code、Cursor、Copilot 等多种 coding agent 的方式是：

- A. 为每个工具 fork 一份 pack，分别维护
- B. 每个工具各写一份内容不同的说明文件
- C. 单一来源，由安装器创建符号链接（如 `ln -s AGENTS.md CLAUDE.md`）分发到各工具约定的位置
- D. 只支持一个工具，其他工具让用户自己适配

**Q5.** 讲义对 `uninstall.sh` 的要求是：

- A. 删除 pack 带来的一切，包括 `agent_state.json`，保证干净
- B. 删除 `outputs/`，因为里面都是 pack 生成的文件
- C. 只删除 `AGENTS.md`，其他文件保留
- D. 删除 schemas、scripts、docs 与 `AGENTS.md`（可用 `--keep-agents-md` 保留），状态文件有未提交改动时拒绝执行

**Q6.** 在刚安装完 pack、尚未创建任何 scope contract 和 feedback 记录的目标仓库中执行 `python3 scripts/verify_agent.py T-001`，实际输出是：

- A. `"passed": true`、`"findings": []`，退出码 0
- B. `"passed": false`，finding 为 `acceptance.missing`
- C. 抛出 `FileNotFoundError`
- D. argparse 报错，退出码 2

**Q7.** `main.py` 中 `PACK = HERE.parent / "outputs" / "agent-workbench-pack"`。运行 `python3 code/main.py` 后，pack 被写到：

- A. `code/agent-workbench-pack/`
- B. 本节目录下的 `outputs/agent-workbench-pack/`（与 `code/` 并列）
- C. 当前工作目录下的 `agent-workbench-pack/`
- D. 用户主目录下的隐藏目录

**Q8.** 在目标仓库执行 `python3 scripts/run_with_feedback.py python3 -m pytest -q`，实际结果是：

- A. 正常运行 pytest 并把结果追加到 `feedback_record.jsonl`
- B. `-m` 被当作 `--note` 的简写
- C. argparse 报 `unrecognized arguments: -m pytest -q`，退出码 2；需要写成 `run_with_feedback.py -- python3 -m pytest -q`
- D. 命令超时后被记录为 `exit_code: null`

---

## 三、动手 / 代码题

**Q9.** 阅读 pack 中 `verify_agent.py` 的 `run_checks`：

```python
def run_checks(task_id: str) -> dict[str, object]:
    accept = list(_load_json(ROOT / f"outputs/scope/closed/{task_id}.json", {}).get("acceptance_criteria", []))
    feedback = _load_jsonl(ROOT / "feedback_record.jsonl")
    scope_report = _load_json(ROOT / f"outputs/scope/closed/{task_id}.report.json", {})
    rule_report = _load_json(ROOT / "outputs/rule_report.json", [])
    findings = check_acceptance(accept, feedback) + check_scope(scope_report) + check_rules(rule_report)
    return {"task_id": task_id, "passed": not any(f["severity"] == "block" for f in findings), "findings": findings}
```

1. 解释为什么在"什么都没有"的仓库里 gate 会通过（Q6）。
2. 列出这里所有"缺文件 → 默认值 → 放行"的路径。
3. 写出 fail-closed 版本的关键改动。

**Q10.** 在目标仓库里，acceptance command 为 `python3 check.py`。先运行一次失败（exit 1），修好后再运行一次成功（exit 0），两次都经 `run_with_feedback.py` 记录。然后运行 gate，实际结果：

```json
{
  "task_id": "T-001",
  "passed": false,
  "findings": [
    {"code": "acceptance.failed", "severity": "block", "detail": "exit 1 on python3 check.py"}
  ]
}
```

1. 根据 `check_acceptance` 的代码解释原因。
2. 这个行为在什么场景下会造成严重问题？
3. 写出"每条 acceptance 命令只看最新一次记录"的修正版，并说明它还应该按什么维度过滤记录。

**Q11.** 讲义练习 4 要求写 `lint_pack.py`，在 pack 与 `VERSION` 漂移时失败；skill 还要求检查"规则没有对应检查函数"。请：

1. 找出本 pack 中至少三处契约不一致（提示：看 `AGENTS.md` 对 board 字段的称呼、讲义对"版本记录在哪里"的描述、`agent-rules.md` 中的 `check:`）。
2. 写一个 `lint_pack.py`，并预测它在当前 pack 上的输出。

**Q12.** 阅读 `generate_handoff.py` 的 `derive_risks`：

```python
    try:
        total = int(review.get("total", 10))
    except (TypeError, ValueError):
        total = 10
    if total < 7:
        risks.append({"severity": "warn", "detail": f"review total {review.get('total')} below 7"})
```

而 `generate_handoff` 在 `outputs/review/<task>.json` 不存在时传入 `review = {}`。

1. 评审报告缺失时，handoff 的 `open_risks` 会怎样？这和第 40 节"缺字段要让 session-end hook 停下"（pack 的 `handoff-protocol.md`："Missing fields halt the session-end hook"）是否一致？
2. 应该怎么改？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 agent workbench pack？它应该包含什么、不包含什么？为什么一定要带版本号？

**Q14.**（原理深挖）什么是 fail-open 与 fail-closed？为什么 verification gate 必须 fail-closed？请结合本节 `verify_agent.py` 的具体代码说明。

**Q15.**（工程实践）请设计一个生产可用的 pack 安装器（可以是 bash 或 Python）：它要满足哪些性质？讲义提到的 CI 接入、符号链接、版本锁定该如何实现？bash 和 Python 各有什么优劣？

**Q16.**（场景设计）你维护的 pack 要从 1.4.0 升级到 2.0.0：`agent_state.schema.json` 新增必填字段 `pack_version`，`task_board` 的 `acceptance` 改名为 `acceptance_criteria`。团队里有 30 个仓库装了旧版。请给出迁移方案。

**Q17.**（追问型）讲义说"Forking the pack to support one tool over another is a failure mode"。如果某个工具确实需要特殊配置（例如 Cursor 的 rules 格式不同），你怎么在"单一来源"原则下处理？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义 Out 列表第一条："Project-specific tasks. Tasks belong on the target repo's board, not in the pack." A 是 schema（"They are the contract"），C 是四个脚本之一（"They are the runtime"），D 是四份文档之一（"They are the rules and the rubric"），都必须在 pack 里。skill 的 Hard rejects 也写明"A pack containing project-specific tasks"要拒绝。

### Q2 — 答案：D

讲义 Versioning："Schema bumps and script changes that require migrations bump the major. Doc-only changes bump the patch." A 过度保守，会让下游每次都以为需要迁移；B 中的 minor 在讲义 Production 部分的定义是"需要重跑检查器"的改动，纯文档不属于此类；C 错，任何变更都应有版本号，否则无法判断目标仓库的漂移。

### Q3 — 答案：A

实测输出：`AGENTS.md already exists. Pass --force to overwrite.`，退出码 1。对应 `install.sh` 中：

```bash
if [[ -e "$TARGET/AGENTS.md" && "$FORCE" != "--force" ]]; then
    echo "AGENTS.md already exists. Pass --force to overwrite." >&2
    exit 1
fi
```

带 `--force` 时会重新复制并覆盖。B 是不安全的行为；C、D 是代码中不存在的逻辑。注意：它只用 `AGENTS.md` 判断"是否已安装"，目标仓库若原本就有自己的 `docs/agent-rules.md` 而没有 `AGENTS.md`，安装器会直接覆盖它（见讲解第 3.7 节）。

### Q4 — 答案：C

讲义 "Single source for cross-tool distribution"：Nx 的 `nx ai-setup` 从一个配置生成 `AGENTS.md`、`CLAUDE.md`、`.cursor/rules/`、`.github/copilot-instructions.md`；"the installer emits the symlinks (`ln -s AGENTS.md CLAUDE.md`) so a single source of truth fans out to every coding agent. Forking the pack to support one tool over another is a failure mode." A、B 会导致多份内容漂移；D 违背框架无关的原则。注意本节 `install.sh` 并没有实现符号链接。

### Q5 — 答案：D

讲义 "`uninstall.sh` that refuses on non-trivial state"：卸载器删除 schemas、scripts、docs 和 `AGENTS.md`（`--keep-agents-md` 可保留），状态文件有未提交改动时拒绝；"State belongs to the user; the pack does not own it." A、B 都会删除用户数据；C 不完整，会留下过期的脚本。

### Q6 — 答案：A

实测输出：

```json
{
  "task_id": "T-001",
  "passed": true,
  "findings": []
}
```

退出码 0。原因是所有输入文件都不存在时 `_load_json` 返回默认值：`acceptance_criteria` 变成 `[]`，`check_acceptance` 遍历空列表不产生 finding；`feedback`、`scope_report`、`rule_report` 都为空。B 是正确的 fail-closed 行为应有的结果，但代码并非如此；C 错，`_load_json` 对不存在的文件返回默认值而不抛异常；D 错，`task_id` 参数已给出。详见 Q9。

### Q7 — 答案：B

`HERE = Path(__file__).parent` 是 `code/`，`HERE.parent` 是本节目录，所以 pack 写到 `<本节>/outputs/agent-workbench-pack/`，与 `code/`、`docs/` 并列。它和脚本在哪个目录下执行无关（不是 C）。实测打印的路径形如 `outputs/agent-workbench-pack/AGENTS.md`（`relative_to(PACK.parent.parent)`）。注意：在仓库里直接运行会覆盖已提交的 `outputs/` 文件（内容相同，所以 git 不会显示变化）。

### Q8 — 答案：C

实测：

```text
usage: run_with_feedback.py [-h] [--note NOTE] [--timeout TIMEOUT]
                            command [command ...]
run_with_feedback.py: error: unrecognized arguments: -m pytest -q
```

退出码 2。`argparse` 看到以 `-` 开头的 `-m` 会把它当作本程序的选项，而本程序没有定义 `-m`。写成 `run_with_feedback.py -- python3 -m pytest -q`，`--` 之后的内容全部当作位置参数，就能正常记录。B 错，argparse 只对 `--` 开头的长选项做前缀匹配，`-m` 不会被解析成 `--note`。这个坑会让 agent "以为跑了验收命令"，实际一条记录都没写——恰好是本系列要防住的失败。

### Q9 — 参考答案

1. 空仓库中：scope contract 文件不存在 → `_load_json(..., {})` 返回 `{}` → `.get("acceptance_criteria", [])` 为 `[]`；`check_acceptance([], [])` 的两个循环都不执行；`scope_report={}` 没有 `forbidden_writes`；`rule_report=[]` 没有失败规则。findings 为空，`not any(...)` 为 `True`，于是 `passed: true`。
2. fail-open 路径共四条：
   - scope contract 缺失 → 没有验收命令 → 不检查验收；
   - contract 存在但 `acceptance_criteria` 为空列表 → 同上；
   - `<task>.report.json`（scope diff 报告）缺失 → 不检查越界；而 pack 中**没有任何脚本**生成这个文件；
   - `outputs/rule_report.json` 缺失 → 不检查规则；同样没有脚本生成它。
3. fail-closed 改法（已在临时目录实际运行验证：无 contract → `scope.contract_missing`；acceptance 为空 → `acceptance.empty`；均为 block）：

```python
def run_checks(task_id: str) -> dict[str, object]:
    findings: list[dict] = []
    contract_path = ROOT / f"outputs/scope/closed/{task_id}.json"
    report_path = ROOT / f"outputs/scope/closed/{task_id}.report.json"
    rules_path = ROOT / "outputs/rule_report.json"
    for p, code in [(contract_path, "scope.contract_missing"),
                    (report_path, "scope.report_missing"),
                    (rules_path, "rules.report_missing")]:
        if not p.exists():
            findings.append({"code": code, "severity": "block", "detail": f"missing {p.name}"})
    accept = _load_json(contract_path, {}).get("acceptance_criteria", [])
    if contract_path.exists() and not accept:
        findings.append({"code": "acceptance.empty", "severity": "block",
                         "detail": "contract lists no acceptance command"})
    # ... 再接原有的 check_acceptance / check_scope / check_rules
```

原则：**证据缺失本身就是一个 block 级 finding**。gate 的默认答案必须是"不通过"，只有在证据齐全且全部合格时才放行。

### Q10 — 参考答案

1. `check_acceptance` 的第二个循环遍历 `feedback` 中的**每一条**记录：只要某条记录的命令属于验收集合且 `exit_code != 0`，就产生 `acceptance.failed`。`feedback_record.jsonl` 是追加写入（`RECORD.open("a")`）的，失败的第一次运行永远留在日志里，所以后来的成功无法"覆盖"它。
2. 严重场景：正常的 TDD 流程就是"先写测试看它失败，再实现让它通过"——按这个 gate，任何先红后绿的任务都永远过不了；agent 和人只能去手动删日志，而"删除反馈记录"恰恰是审计上最不应该发生的操作。反过来，日志也不按任务区分，上一个任务的失败会挡住下一个任务。
3. 修正版（已实际运行验证：先失败后成功 → `[]`；再追加一次失败 → `acceptance.failed`）：

```python
def check_acceptance_strict(accept, feedback):
    latest = {}
    for r in feedback:                       # 按时间顺序，后来的覆盖先前的
        latest[_normalize_command(r.get("command"))] = r
    findings = []
    for cmd in accept:
        r = latest.get(cmd)
        if r is None:
            findings.append({"code": "acceptance.missing", "severity": "block", "detail": f"never ran: {cmd}"})
        elif r.get("exit_code") is None:
            findings.append({"code": "feedback.null_exit", "severity": "block", "detail": f"missing exit for {cmd}"})
        elif r.get("exit_code") != 0:
            findings.append({"code": "acceptance.failed", "severity": "block", "detail": f"exit {r['exit_code']} on {cmd}"})
    return findings
```

还应按以下维度过滤：**task_id / session_id**（记录里要带上）、**时间**（只看本任务 scope contract 打开之后的记录）、**代码版本**（记录当时的 git commit，只认 HEAD 上的结果，否则"先跑通再改代码"也能骗过 gate）。原代码对非验收命令的 `exit_code is None` 也会 block，这一点可以保留为 warn。

### Q11 — 参考答案

1. 契约不一致（逐条核对过源码）：
   - `AGENTS.md` 写 "Verification command: see `acceptance_criteria` in the active task on the board"，但 `task_board.schema.json` 中字段名是 `acceptance`；`acceptance_criteria` 是 scope contract 的字段名。
   - 讲义 Versioning："The target repo's `agent_state.json` records which pack version it was initialized against"，但 `agent_state.schema.json` 没有任何版本字段（只有 `schema_version: 1`）；安装器实际把版本写在 `.workbench-version`。
   - `agent-rules.md` 的 5 条规则各有 `check:` 名（`state_file_fresh`、`no_out_of_scope_writes`、`tests_pass`、`opened_question_when_unsure`、`new_dependency_approved`），`scripts/` 里没有一个同名函数；`verify_agent.py` 读取的 `outputs/rule_report.json` 也没有脚本生成。这正是 skill 的 Hard reject："Rules without a corresponding check function."（`init_agent.py` 的 `_probe_state` 与 `state_file_fresh` 语义相近，但名字对不上，且只产生 warn。）
   - 其他：pack 带了 JSON Schema，但没有任何脚本用它们校验 `agent_state.json` / `task_board.json`；讲义说安装器会接入 CI，`install.sh` 没有实现；mission 验收要求 "state, board, ... reviewer ... all in place"，pack 里没有 reviewer 脚本，安装后也没有 `agent_state.json` 与 `task_board.json`。
2. 参考实现（核心部分）：

```python
import json, re, sys
from pathlib import Path

def lint(pack: Path) -> list[str]:
    problems = []
    version = (pack / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        problems.append(f"VERSION not semver: {version!r}")
    if f"Pack version: {version}" not in (pack / "AGENTS.md").read_text():
        problems.append("AGENTS.md pack version != VERSION")
    for s in sorted((pack / "schemas").glob("*.json")):
        json.loads(s.read_text())                        # 无效 JSON 直接抛错
    scripts = "\n".join(p.read_text() for p in (pack / "scripts").glob("*.py"))
    for check in re.findall(r"^- check: (\w+)$", (pack / "docs/agent-rules.md").read_text(), re.M):
        if not re.search(rf"def \w*{check}\w*\(", scripts):
            problems.append(f"rule check '{check}' has no implementing function in scripts/")
    board = json.loads((pack / "schemas/task_board.schema.json").read_text())
    if "acceptance_criteria" in (pack / "AGENTS.md").read_text() \
            and "acceptance_criteria" not in board["items"]["properties"]:
        problems.append("AGENTS.md points to board field 'acceptance_criteria' but board schema calls it 'acceptance'")
    return problems

probs = lint(Path(sys.argv[1]))
print("\n".join("FAIL " + p for p in probs))
sys.exit(1 if probs else 0)
```

在当前 pack 上实际运行的输出（退出码 1）：

```text
FAIL rule check 'state_file_fresh' has no implementing function in scripts/
FAIL rule check 'no_out_of_scope_writes' has no implementing function in scripts/
FAIL rule check 'tests_pass' has no implementing function in scripts/
FAIL rule check 'opened_question_when_unsure' has no implementing function in scripts/
FAIL rule check 'new_dependency_approved' has no implementing function in scripts/
FAIL AGENTS.md points to board field 'acceptance_criteria' but board schema calls it 'acceptance'
```

版本相关两项通过（`VERSION` 为 `1.0.0`，`AGENTS.md` 中也是 `Pack version: 1.0.0`）。把 lint 接到 pack 自身仓库的 CI 上，这些漂移在合并前就会被拦下。

### Q12 — 参考答案

1. `review = {}` 时 `review.get("total", 10)` 取默认值 10，`10 < 7` 为假，不添加任何风险。实测：在没有评审报告的情况下生成 handoff，`open_risks` 里只有 gate 的 block，完全没有提到"评审缺失"；`summary` 中虽然显示 `review=None`，但 "Receipts" 一节仍然列出一个并不存在的 `outputs/review/T-001.json` 路径。缺失评审被当成了满分，这与 `handoff-protocol.md` 的 "Missing fields halt the session-end hook" 相矛盾——生成器从不停止，所有缺失字段都被默认值悄悄填上（`next_action` 缺失时写 "needs human" 还算显式，评审缺失则完全无声）。
2. 改法：

```python
    if not review:
        risks.append({"severity": "block", "detail": "review report missing"})
    else:
        try:
            total = int(review["total"])
        except (KeyError, TypeError, ValueError):
            risks.append({"severity": "block", "detail": f"review total unreadable: {review.get('total')!r}"})
        else:
            if total < 7:
                risks.append({"severity": "warn", "detail": f"review total {total} below 7"})
```

并在 `main()` 中：存在 block 级风险或必填字段缺失时返回非零退出码，让 session-end hook 真正停下；"Receipts" 只列出确实存在的文件。原则与 Q9 相同：**默认值不能比真实数据更乐观**。

### Q13 — 参考回答要点

- **定义**：一个带版本号、可整体复制到任意仓库的目录，把七个 workbench surface（instructions、state、scope、feedback、verification、review、handoff）固化成文件。讲义："The pack is the recipe. Each install is a serving."
- **包含**：`AGENTS.md`（短路由）、四份文档（规则、可靠性策略、handoff 协议、评审标准）、三个 schema（state、board、scope contract）、四个脚本（init、feedback runner、gate、handoff 生成器）、安装器、`README.md`、`VERSION`。
- **不包含**：具体项目任务、厂商 SDK 调用、入职说明文字——保证 pack 可移植、框架无关。
- **为什么要版本号**：workbench 散落在文档、聊天记录和脚本里时"每个季度都要重建一次"；有了 `VERSION`，目标仓库能知道自己装的是哪一版、升级时是否需要迁移（major）、是否只需重跑检查（minor）、还是纯文档（patch）。讲义类比 npm、Cargo、`pyproject.toml`。
- 加分点：版本记录要落在目标仓库（`.workbench-version` 或 state 中的字段），并由 lint 校验一致性。

### Q14 — 参考回答要点

- **定义**：fail-open 指检查机制出问题（缺输入、异常、超时）时默认放行；fail-closed 指此时默认拒绝。
- **gate 为什么必须 fail-closed**：gate 的唯一价值是阻止"未经证明的完成"进入主干。agent 最常见的失败恰恰是"没跑命令""跑错命令""证据文件没生成"，fail-open 的 gate 在这些情况下全都放行，等于没有 gate。
- **本节代码中的具体例子**：
  - 缺 scope contract → `acceptance=[]` → `passed: true`（实测，见 Q6/Q9）；
  - 缺 scope 报告、缺规则报告 → 不检查；pack 里也没有生成它们的脚本；
  - `generate_handoff` 中评审缺失被默认为 10 分（Q12）。
- **反方向的问题**：append-only 日志导致"历史失败永远阻塞"（Q10）——这是"过度 closed"，会逼人绕过 gate；正确做法是只看本任务、本版本代码上的最新结果。
- 加分点：fail-closed 需要配套"签名并审计的 override 路径"（pack 的 `reliability-policy.md`："The override path is signed and audited; agents cannot self-override"），否则会被人直接关掉。

### Q15 — 参考回答要点

- **必须满足的性质**：
  1. 幂等：重复执行结果一致；已安装时无 `--force` 拒绝；
  2. 不触碰用户状态：skill Hard reject "An installer that mutates state files"；
  3. 冲突检测：目标仓库已有同名 `docs/*.md`、`scripts/*.py` 时要列出冲突而不是静默覆盖（本节实现只检查 `AGENTS.md`）；
  4. 版本锁：写 `.workbench-version`，升级时比较新旧版本并提示是否需要迁移；
  5. `--dry-run`：先打印将要创建/覆盖的文件（讲义练习 2）；
  6. 输出下一步：填 board、设 acceptance 命令、跑 init。
- **讲义提到但本节未实现的**：
  - CI 接入：检测到 `.github/workflows/` 时写入一个运行 `verify_agent.py` 的 workflow；不存在时按 skill 的规则拒绝并给出手动步骤；
  - 符号链接：`ln -s AGENTS.md CLAUDE.md`，`.github/copilot-instructions.md` 等；Windows 上符号链接需要权限，可退化为复制并由 lint 检查内容一致。
- **bash vs Python**：bash 零依赖、适合简单复制，但错误处理、路径空格、跨平台（Windows）、JSON 处理都不方便；Python 便于实现 dry-run、冲突报告、JSON 校验和单元测试，代价是需要解释器（但 pack 本身的脚本已经依赖 Python 3.10+）。
- 常见误区：安装器"顺手"生成示例 `task_board.json` 里的具体任务——这违背了"任务不进 pack"。

### Q16 — 参考回答要点

- **先定版本语义**：schema 新增必填字段 + 字段改名 → 需要迁移 → bump major（2.0.0）。
- **准备工作**：
  1. 写 `migrate_1_to_2.py`：读取 `agent_state.json`，补 `pack_version`；把 `task_board.json` 中每个任务的 `acceptance` 改名为 `acceptance_criteria`；迁移前备份，迁移后用新 schema 校验；
  2. 同步修改所有读这些字段的脚本、`AGENTS.md`，并让 `lint_pack.py` 检查字段一致性；
  3. 写 CHANGELOG 与迁移手册。
- **推广顺序**（讲义练习 5 "minimizes downtime"）：
  1. 选 1–2 个低风险仓库试点，跑一遍完整任务（init → runner → gate → handoff）；
  2. 迁移前要求每个仓库没有进行中的任务（或先生成 handoff），避免迁移打断会话；
  3. 分批升级，CI 中的 lint 检查 `.workbench-version` 与 pack `VERSION` 一致，未升级的仓库给出明确提示而不是静默失败；
  4. 保留回滚路径：旧版 pack 与备份的状态文件。
- 加分点：过渡期让脚本同时接受新旧字段名（读兼容、写新名），一个 minor 版本后再移除兼容层。

### Q17 — 参考回答要点

- **原则**：内容只有一个来源，差异放在"生成/分发层"，不放在"内容层"。
- **做法**：
  - 公共规则写在 `AGENTS.md` 与 `docs/` 中；
  - 工具特有的格式（如 Cursor 的 `.cursor/rules/*.mdc` 需要 front-matter）由安装器或生成器从同一来源**渲染**出来，而不是手写第二份内容；
  - 只有格式完全相同的才用符号链接（`CLAUDE.md -> AGENTS.md`）；
  - lint 检查各个派生文件与源文件一致，防止有人直接改派生文件。
- **为什么 fork 是失败模式**：fork 后两份规则会各自演化，某个工具上的 agent 遵守的是过期规则；版本号也失去意义。讲义举例 Nx 的 `nx ai-setup` 从一个配置生成六种工具的文件，SkillKit 用 `skillkit install` 分发到 32 个 AI agent。
- 加分点：把工具差异限制在"如何加载规则"，而不是"规则是什么"；如果某条规则只对某个工具成立，说明它可能属于工具配置而非 workbench 规则。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 31 Agent 工作台工程：能力强的模型为什么仍会失败](../../31-agent-workbench-why-models-fail/docs/zh.md)：七个 surface 的定义。
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../33-instructions-as-executable-constraints/docs/zh.md)：`agent-rules.md` 中"规则 + check"的来源。
- [阶段 14 · 34 代码仓库记忆与持久状态](../../34-repo-memory-and-state/docs/zh.md)：`agent_state.schema.json` 与 `task_board.schema.json`。
- [阶段 14 · 35 面向 Agents 的初始化脚本](../../35-initialization-scripts/docs/zh.md)：`init_agent.py`。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：`scope_contract.schema.json`。
- [阶段 14 · 37 运行时反馈循环](../../37-runtime-feedback-loops/docs/zh.md)：`run_with_feedback.py`。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：`verify_agent.py`。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)、[阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：评审标准与 `generate_handoff.py`。

### 本节被哪些后续内容用到
- [阶段 14 · 41 在真实代码仓库中使用工作台](../../41-workbench-for-real-repos/docs/zh.md)：用 before/after benchmark 衡量 pack 带来的改进。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：消费 pack 的 gate 结论做持续评估。
- [阶段 14 · 43 在 Agent 编写代码前界定任务](../../43-frame-the-task-before-code/docs/zh.md)：装好 pack 之后，下一步是把任务本身界定清楚。
- [阶段 14 · 46 把每一次对 Agent 的纠正转化为系统改进](../../46-turn-feedback-into-system/docs/zh.md)：把纠正沉淀进 pack 的规则与检查。

### 延伸关键词
`AGENTS.md` · `drop-in pack` · `semantic versioning` · `idempotent installer` · `fail-closed` · `schema drift` · `lint_pack` · `symlink fan-out` · `SkillKit` · `Nx ai-setup` · `GitHub template repo` · `state ownership`
