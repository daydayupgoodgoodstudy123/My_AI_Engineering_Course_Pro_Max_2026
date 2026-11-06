# 测验 · 将 Agent 指令作为可执行约束（Agent Instructions as Executable Constraints）

> **阶段 14 · Agent 工程 · 第 33 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（规则文件：[code/agent-rules.md](../code/agent-rules.md)） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 愿望 vs 约束 | 讲义："Instructions written as prose are wishes. Instructions written as constraints are tests." 没有 check 的规则（"be careful"）要么删、要么升级 |
| 2 | 路由与规则分离 | `AGENTS.md` 只做路由；规则放在 `docs/agent-rules.md`，每条规则有名字、类别、check |
| 3 | 五个类别 | startup（开工前必须成立）、forbidden（绝不能发生）、definition of done（什么证明完成）、uncertainty（不确定时怎么做）、approval（什么需要人批准）；放不进去的规则通常应拆成两条 |
| 4 | 规则机器可读 | 每条规则 = slug + category + 一行描述 + `check` 字段（指向检查器中的函数名）；加规则就是加 check |
| 5 | 规则对 diff 友好 | 一条规则一个标题；过期规则直接删除而不是注释掉 |
| 6 | 规则 vs 框架 guardrail | guardrail（OpenAI Agents SDK guardrails、LangGraph interrupts）在运行时执行；规则集是人可读、可审查的契约，证明运行时在做正确的事；两者都要 |
| 7 | 渐进式披露 | 三层：router（每次读，约 50 行内）→ rules（启动时读）→ topic docs（任务涉及时才读）；可达性测试：任何规则离 router 不超过两跳；失效链接本身就是 startup 违规 |
| 8 | severity 分级 | `block` / `warn` / `info`；检查器报告全部，运行时只在 `block` 上拒绝；写规则时就定级，避免截止日期前悄悄降级 |
| 9 | 规则过期 | 每条规则带 `expires_at`（默认 90 天）；连续 60 天零违规发出警告，季度复审时保留、降级或删除；讲义引用 Cloudflare 数据：有过期机制的规则集保持在每仓库 30 条以内 |
| 10 | Markdown 为源、JSON 为缓存 | `agent-rules.md` 人写可审；`agent-rules.lock.json` 由 pre-commit hook 生成，供热路径读取，类似 `package.json` / `package-lock.json` |

### 核心技能（能动手做到）

- [ ] 把一段散文式的 `AGENTS.md` 按五个类别改写成带 check 的规则，并统计其中"可操作"与"愿望式"的比例
- [ ] 读懂 `parse_rules` 的正则切分逻辑，并找出它会静默丢规则、误取描述的输入
- [ ] 为 `RuleChecker` 新增一个 check，并说明它需要 `TurnTrace` 记录哪些字段
- [ ] 给规则加 `severity` 字段，让报告给出聚合严重度，并在 `block` 失败时让 CI 失败
- [ ] 实现规则过期/静默检测，输出需要复审的规则清单
- [ ] 解释 deterministic check（确定性检查）为什么不能依赖 LLM 调用

---

## 二、基础自测（选择题）

**Q1.** 讲义区分 "operational rule" 与 "aspirational rule"。下列说法正确的是：

- A. operational rule 带一个工作台能在运行时执行的 check；aspirational rule（如 "be careful"）没有 check，应删除或升级
- B. aspirational rule 更重要，因为它表达了团队价值观
- C. 两者唯一的区别是写在不同的文件里
- D. operational rule 必须由 LLM 判断是否满足

**Q2.** 规则 "Adding a runtime dependency requires explicit human approval" 属于五个类别中的哪一个？

- A. forbidden
- B. startup
- C. approval
- D. definition_of_done

**Q3.** 运行 `python3 code/main.py`，`bad trace` 一栏中有几条规则显示 `FAIL`？

- A. 2 条（与讲义"violates two rules"一致）
- B. 3 条
- C. 0 条
- D. 5 条

**Q4.** 如果 `agent-rules.md` 中某条规则的 `check:` 拼错成了 `state_fil_fresh`（`RuleChecker` 没有这个方法），`score()` 会：

- A. 抛出 `AttributeError`，程序终止
- B. 把这条规则记为 `passed: False`，但不说明原因
- C. 把这条规则记为 `passed: True`
- D. 直接跳过这条规则，报告里不出现

**Q5.** 关于 severity 分级，讲义的描述是：

- A. 只有 `warn` 会被报告，`info` 和 `block` 都不报告
- B. 三种级别都会让运行时拒绝执行
- C. 检查器报告全部三种级别，运行时只在 `block` 失败时拒绝；覆盖 `block` 需要操作员并写入审计日志
- D. severity 应该在出事之后再补，避免过早定级

**Q6.** "Markdown-as-source, JSON-as-cache" 模式指的是：

- A. `agent-rules.md` 是人写的源文件，`agent-rules.lock.json` 由 pre-commit hook 重新生成，检查器在热路径上读 JSON
- B. 规则只写在 JSON 里，Markdown 只用于展示
- C. 每一轮都重新解析 Markdown，JSON 用来备份聊天记录
- D. JSON 是源，Markdown 由 JSON 自动生成

**Q7.** 讲义中保证渐进式披露"不失真"的**可达性测试**是：

- A. router 必须包含所有规则的全文
- B. 每个 topic doc 都要在每个会话开始时加载
- C. router 不得超过 10 行
- D. 从 router 出发至多两跳就能到达任何规则，因此 router 必须用路径链接每个 topic doc，而不是用散文描述

**Q8.** `RuleChecker.no_release_script_edits` 的实现是 `return "scripts/release.sh" not in trace.edited_files`。若 `edited_files=["./scripts/release.sh"]`，返回值是：

- A. `False`，检查器正确拦截
- B. `True`——路径没有规范化，同一个文件换个写法就绕过了 forbidden 规则
- C. 抛出 `TypeError`
- D. 取决于当前工作目录

---

## 三、动手 / 代码题

**Q9.** `parse_rules` 的实现：

```python
def parse_rules() -> list[Rule]:
    text = RULES_PATH.read_text()
    rules: list[Rule] = []
    for block in re.split(r"\n## ", text)[1:]:
        head, *rest = block.split("\n", 1)
        slug = head.strip()
        body = rest[0] if rest else ""
        cat_match = re.search(r"-\s*category:\s*(\S+)", body)
        check_match = re.search(r"-\s*check:\s*(\S+)", body)
        non_empty = [ln.strip() for ln in body.splitlines() if ln.strip()]
        desc = non_empty[-1] if non_empty else ""
        if not cat_match or not check_match:
            continue
        rules.append(Rule(slug=slug, category=cat_match.group(1),
                          check=check_match.group(1), description=desc))
    return rules
```

1. 对下列四种输入，分别说出解析结果有什么问题：
   - (a) 文件直接以 `## a/b` 开头（没有 `# Agent Rules` 标题行）；
   - (b) 某条规则只有 `- category: startup` 和一行 `Be careful.`，没有 `check`；
   - (c) 描述写在字段前面：`## a/b` / `Description first` / `- category: startup` / `- check: x`；
   - (d) 描述跨两行。
2. 重写一个"严格"版本：缺 `check`、类别不在五类之内时抛出异常；正确处理 (a)(c)(d)。

**Q10.** 讲义练习 2 + 3，以及 mission 中的"aggregate severity"要求：

1. 给规则加 `severity`（`block` / `warn` / `info`，默认 `block`），在报告里给出聚合严重度（有 block 失败 → `block`，否则有 warn 失败 → `warn`……全过 → `pass`）。
2. 让脚本在聚合结果为 `block` 时以非零退出码结束，以便接入 CI。
3. 若把 `uncertainty/open-question-note` 设为 `warn`，一个只违反这条规则的 trace，聚合结果是什么？

**Q11.** 讲义说 demo "violates two rules"，mission 也写着 "`rule_report.json` catches the two intentional violations"，但实际 `bad_trace` 五条全挂。

1. 列出 `bad_trace` 的每个字段分别触发了哪条规则失败。
2. 构造一个**恰好违反两条规则**（forbidden 与 approval）的 `TurnTrace`，并给出各规则结果。
3. 修复 Q8 中的路径绕过问题。

**Q12.** 讲义练习 4：规则过期。每条规则带 `expires_at`；连续 60 天零违规发出警告。给定历史报告列表 `[(日期, slug, passed), ...]`，写一个 `expiry_findings(rules, history, today)`，返回需要复审的规则及原因。今天是 2026-10-12，规则 a 于 2026-09-01 过期；规则 b 在 2026-10-01 失败过一次；规则 c 最后一次失败在 2026-07-01、此后只有通过记录。哪些规则会被列出？

---

## 四、面试高频题

**Q13.**（基础必考）什么叫"把指令写成可执行约束"？请举例说明五个类别，以及一条好的规则需要哪些字段。

**Q14.**（原理深挖）既然 OpenAI Agents SDK 有 guardrails、LangGraph 有 interrupts，为什么还需要一份 Markdown 规则集？规则的 check 为什么必须是确定性的、不能调用 LLM？

**Q15.**（工程实践）规则集上线一个季度后，通常会退化成什么样？请给出让规则集"长期健康"的机制。

**Q16.**（场景设计）下面是某团队的 `AGENTS.md` 片段，请把它改写成五类规则，并指出哪些行是愿望式的：

```text
- Be careful with production.
- Always test thoroughly before finishing.
- Ask if unsure.
- Don't touch the billing module unless needed.
- Follow our Python style guide.
- Remember to read the state file first.
```

**Q17.**（追问型）`AGENTS.md` 一年后膨胀到两千行，有人提议"把它删短一点就好"。你同意吗？你会怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义 Key Terms："Operational rule — A rule the workbench can check at runtime"；"Aspirational rule — 'Be careful' — A rule with no check; either delete or upgrade"。

- B 与讲义相反：愿望式规则恰恰是 agent "never knew where the line was" 的原因；
- C 错：区别在于有没有 check，而不是放在哪；
- D 错：配套 skill 的硬拒绝条款之一就是 "Checks that require LLM calls"，check 必须确定且便宜。

### Q2 — 答案：C

approval 类回答的问题是"What requires human approval?"，讲义例子正是 "any new dependency, any prod write"。代码中对应的规则是 `approval/new-dependency`，check 为 `new_dependency_approved`：没有新增依赖时通过；有新增依赖时，每个依赖都必须出现在 `trace.approvals` 中。

- A forbidden 是"绝不能发生"，而新增依赖是"可以发生，但要批准"；
- B、D 分别回答"开工前"和"完成证明"。

### Q3 — 答案：D

实际运行输出：

```text
bad trace:
  startup/state-file-fresh                   FAIL
  forbidden/no-release-script-edits          FAIL
  done/tests-pass                            FAIL
  uncertainty/open-question-note             FAIL
  approval/new-dependency                    FAIL
```

`bad_trace` 的每个字段都被设成了违规值（详见 Q11），所以五条全挂。讲义（"A demo agent run that violates two rules"）和 mission（"catches the two intentional violations"）的描述与代码不一致。

### Q4 — 答案：B

```python
check_fn = getattr(checker, rule.check, None)
passed = bool(check_fn(trace)) if check_fn else False
```

`getattr` 带默认值 `None`，找不到方法不会抛异常；接着 `if check_fn else False` 把它记为失败。已实测：`[{'slug': 's', 'category': 'startup', 'passed': False}]`。

这是 **fail closed**（未知即失败）的正确方向，但报告里无法区分"规则真的被违反"和"check 名写错了"——审查者会误以为 agent 犯了错。改进：报告中增加 `"error": "unknown check state_fil_fresh"`，或者在解析阶段就校验每个 `check` 都存在于 `RuleChecker` 上，启动即报错。

### Q5 — 答案：C

讲义："Every rule carries `severity`: `block`, `warn`, or `info`. The checker reports all three; the runtime only refuses on `block`." 并且 verification gate（第 38 节）会把任何对 `block` 规则的覆盖签名写入 `overrides.jsonl` 审计日志。Key Terms 中 block 的定义是"Violation halts the run; cannot be silenced without an operator"。

D 与讲义相反："Most teams overstate severity early then quietly weaken it under deadline pressure; tagging at write time forces the calibration up front."

### Q6 — 答案：A

讲义："`agent-rules.md` is the authored file; `agent-rules.lock.json` is a cache the checker reads in the hot path. The lock is regenerated by a pre-commit hook. Markdown diffs are reviewable; JSON parsing stays out of every turn." 好处是：人审 Markdown 的 diff，机器读解析好的 JSON，每一轮都不用重新解析 Markdown。D 把源与缓存的方向说反了。注意：本节代码**没有**实现 lock 文件，每次运行都直接解析 Markdown。

### Q7 — 答案：D

讲义："The reachability test: an agent should reach any rule in at most two hops from the router, so the router must link every topic doc by path, not describe it in prose." 另一个是 freshness test：router 短到每次 PR 审查者都会重读一遍。讲义还强调 "A pointer that no longer resolves is a worse failure than a missing rule, so a broken link in the router is itself a startup-check violation."

- A 违背"给地图而不是百科全书"的原则；
- B 违背"topic docs 只在任务涉及时加载"；
- C 的 10 行不是讲义数字（讲义给的是 router "under ~50 lines"）。

### Q8 — 答案：B

`in` 做的是字符串精确匹配，`"./scripts/release.sh" != "scripts/release.sh"`，所以返回 `True`（已实测）。同理，绝对路径、`scripts//release.sh`、大小写不同（在大小写不敏感的文件系统上）都能绕过。forbidden 规则是安全边界，比较前必须规范化路径（见 Q11 第 3 问）。

### Q9 — 参考答案

1. 逐项实测结果：
   - (a) `re.split(r"\n## ", text)[1:]` 依赖"`## ` 前面有换行"，并丢掉第一个片段。文件以 `## a/b` 开头时，第一条规则落在被丢弃的 `[0]` 里——**静默丢失**。
   - (b) 缺 `check` 时 `continue`，规则被**静默跳过**，报告中完全看不到。愿望式规则悄悄消失，而不是被拒绝（skill 硬拒绝："Rules without a `check` field"）。
   - (c) `desc = non_empty[-1]` 取最后一个非空行，结果描述变成了 `- check: x`。
   - (d) 只保留最后一行描述，第一行丢失。
   - 另外：`category` 的值没有校验，写成 `style` 也照样接受；`###` 子标题之后的文字会被当成描述。
2. 严格版本（已运行验证）：

```python
CATEGORIES = {"startup", "forbidden", "definition_of_done", "uncertainty", "approval"}

def parse_rules_strict(text: str) -> list[Rule]:
    rules = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:      # (a) 行首匹配，文件开头也算
        head, _, body = block.partition("\n")
        fields = dict(re.findall(r"^-\s*(\w+):\s*(\S+)\s*$", body, flags=re.M))
        desc_lines = [ln.strip() for ln in body.splitlines()
                      if ln.strip() and not re.match(r"^-\s*\w+:", ln.strip())]   # (c) 排除字段行
        slug = head.strip()
        if "check" not in fields:                                # (b) 拒绝而非跳过
            raise ValueError(f"{slug}: missing check (aspirational rule?)")
        if fields.get("category") not in CATEGORIES:
            raise ValueError(f"{slug}: bad category {fields.get('category')!r}")
        rules.append(Rule(slug, fields["category"], fields["check"],
                          " ".join(desc_lines)))                 # (d) 多行拼接
    return rules
```

   `re.M`（MULTILINE）让 `^` 匹配每一行的开头。对 (c) 的输入，结果为 `description='Description first more'`（当描述后面还有一行 `more` 时）。还可以再加一步：`for r in rules: assert hasattr(RuleChecker, r.check)`，把 Q4 的问题前移到启动时。

### Q10 — 参考答案

```python
SEVERITIES = ("block", "warn", "info")          # 从重到轻

@dataclass
class Rule:
    slug: str
    category: str
    check: str
    description: str
    severity: str = "block"                     # 默认最严格：漏写 severity 不会变成放水

def aggregate(results):
    failed = [r for r in results if not r["passed"]]
    for s in SEVERITIES:
        if any(r["severity"] == s for r in failed):
            return s
    return "pass"

# main() 末尾
overall = aggregate(bad)
report = {"bad": bad, "good": good, "aggregate_bad": overall, ...}
REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
if overall == "block":
    raise SystemExit(1)                         # CI 据此失败
```

- 解析时从 `- severity: warn` 读取（Q9 的 `fields` 字典里取 `fields.get("severity", "block")`，并校验取值）。`score()` 把 `rule.severity` 带进每条结果。
- 默认值取 `block` 是"fail closed"：忘写 severity 的规则按最严格处理。
- 第 3 问：已实测，只违反 `warn` 级规则的 trace（`read_state_file=True, confidence=0.4, asked_for_help=False, tests_exit_code=0`，无越界、无新依赖），聚合结果是 `warn`，不会让 CI 失败；原 `bad_trace` 的聚合结果是 `block`。
- 注意：演示脚本里 `bad_trace` 本来就是"故意违规"的样例，接入 CI 时应检查**最近一次真实运行**的 trace（讲义练习 3："fail the build if a block-severity rule fails on the latest agent run"），否则这个 demo 每次都会让构建失败。

### Q11 — 参考答案

1. 字段 → 失败的规则：

| 字段 | 值 | 失败的规则 |
|------|----|-----------|
| `read_state_file` | `False` | `startup/state-file-fresh` |
| `edited_files` | 含 `scripts/release.sh` | `forbidden/no-release-script-edits` |
| `tests_exit_code` | `1` | `done/tests-pass` |
| `confidence` / `asked_for_help` | `0.4` / `False` | `uncertainty/open-question-note`（< 0.7 且没求助） |
| `added_dependencies` / `approvals` | `["fastapi"]` / `[]` | `approval/new-dependency` |

2. 恰好违反两条：

```python
two_violations = TurnTrace(
    read_state_file=True,
    edited_files=["app.py", "scripts/release.sh"],   # forbidden
    confidence=0.9,
    asked_for_help=False,
    tests_exit_code=0,
    added_dependencies=["fastapi"],                   # approval（approvals 为空）
)
```

   实测结果：`state-file-fresh True`、`no-release-script-edits False`、`tests-pass True`、`open-question-note True`、`new-dependency False`。

3. 路径规范化：

```python
import posixpath

FORBIDDEN = {"scripts/release.sh"}

def _norm(p: str) -> str:
    return posixpath.normpath(p.replace("\\", "/")).lstrip("/")

def no_release_script_edits(self, trace):
    return not any(_norm(f) in FORBIDDEN for f in trace.edited_files)
```

   `posixpath.normpath("./scripts/release.sh")` 得到 `scripts/release.sh`。更稳妥的做法是把路径解析成相对仓库根的真实路径（`Path(repo_root, f).resolve().relative_to(repo_root)`），连符号链接也一起处理。

### Q12 — 参考答案

```python
from datetime import date

def expiry_findings(rules, history, today, quiet_days=60):
    out = []
    for r in rules:
        fails = [d for d, slug, ok in history if slug == r["slug"] and not ok]
        last_fail = max(fails) if fails else None
        if today >= r["expires_at"]:
            out.append((r["slug"], "expired: justify / weaken to info / delete"))
        elif last_fail is None or (today - last_fail).days >= quiet_days:
            out.append((r["slug"], f"no failures in {quiet_days}+ days: review"))
    return out
```

实测输出：`[('a', 'expired: ...'), ('c', 'no failures in 60+ days: review')]`。

- a：已过 `expires_at`，必须复审；
- b：11 天前刚失败过，说明规则仍在"干活"，不列出；
- c：最后一次失败在 103 天前，此后只有通过记录，符合"连续 60 天零违规"，列出复审。

注意：新建不足 60 天的规则没有失败记录也会被误报，实际实现应加 `created_at` 并跳过太新的规则。复审的三种结局正是讲义说的："either justifies keeping it, weakens it to `info`, or deletes it"。

### Q13 — 参考回答要点

- **定义**：每条指令都对应一个工作台可以在运行时检查、审查者可以事后验证的 check；没有 check 的指令只是愿望。
- **五类及例子**（讲义）：startup（"state file exists and is fresh"）、forbidden（"do not edit `scripts/release.sh`"）、definition of done（"pytest exits 0 and acceptance line passes"）、uncertainty（"open a question note instead of guessing"）、approval（"any new dependency, any prod write"）。放不进五类的规则通常应拆成两条。
- **字段**：slug（如 `forbidden/no-release-script-edits`）、category、一行描述、check 函数名；生产中再加 severity、expires_at、来源事故 id（skill："attach the incident id"）。
- **check 的输入**：一个 `TurnTrace`，至少记录 `read_state_file`、`edited_files`、`tests_exit_code`（skill 的最低要求）。
- **加分点**：规则一条一个标题、diff 友好；过时规则删除而不是注释掉。

### Q14 — 参考回答要点

- **分工**：guardrail/interrupt 是**运行时**执行面，在一轮中途拦截；规则集是**契约**面，人可读、可审查、可版本化。讲义："the runtime catches violations during a turn, the rule set proves the runtime is doing the right thing."
- **可移植**：规则是 "just markdown plus function names"，同一份规则可以注册成 Agents SDK 的 input/output guardrail、LangGraph 的 interrupt，或在 CI 里重跑以发现"静默漂移"。
- **为什么 check 必须确定**：
  - 每一轮都要跑，必须便宜、快；
  - 结果要可复现，否则同一个 trace 今天过、明天不过，无法审计；
  - LLM 判断本身可能被 prompt injection 影响，安全边界不能依赖它；
  - 讲义延伸阅读把 Lean 4 类型检查列为"规则即检查"的上限，方向是"更形式化"，而不是"更模糊"。
- **加分点**：需要语义判断的事情（如"代码是否优雅"）交给 reviewer（第 39 节），不要塞进规则检查器。

### Q15 — 参考回答要点

- **典型退化**：每次事故加一条规则，没有任何机制删除；严重度在截止日期前被悄悄调低；大量规则从不触发；文件膨胀到 agent 只读得完第一屏。
- **机制**：
  1. **写时定 severity**（block/warn/info），覆盖 block 需要操作员并写审计日志（`overrides.jsonl`）；
  2. **过期**：`expires_at` 默认 90 天，60 天零违规发警告，季度复审决定保留/降级/删除；讲义引用 Cloudflare 生产数据（2026 年 4 月，30 天内 5,169 个仓库的 131,246 次评审运行）：有显式过期的规则集保持在每仓库 30 条以内，没有的增长到 80 条以上且大多从不触发；
  3. **Markdown 为源、lock JSON 为缓存**，pre-commit hook 重新生成；
  4. **规则文件上限**：skill 规定超过 200 行就按类别拆分；
  5. 规则附带来源事故 id，复审时能判断是否还需要。
- **加分点**：把"规则数量""从不触发的规则比例"作为工作台健康指标。

### Q16 — 参考回答要点

| 原句 | 处理 | 改写后的规则（类别 / check） |
|------|------|---------------------------|
| Be careful with production. | 愿望式 → 升级 | approval/prod-write：任何生产写操作需人工批准；check：`prod_writes ⊆ approvals` |
| Always test thoroughly before finishing. | 愿望式 → 升级 | definition_of_done/tests-pass：验收命令退出 0；check：`tests_exit_code == 0` |
| Ask if unsure. | 愿望式 → 升级 | uncertainty/open-question-note：置信度低于阈值时必须写 question note；check：`confidence >= 0.7 or asked_for_help` |
| Don't touch the billing module unless needed. | "unless needed" 不可检查 → 拆分 | forbidden/no-billing-edits（`billing/**` 不得出现在 edited_files）+ approval/billing-change（确需修改时走审批） |
| Follow our Python style guide. | 不可验证的风格规则 | definition_of_done/lint-clean：配上具体命令，例如 `ruff check .` 退出 0（第 32 节："pair every style rule with the exact lint command"） |
| Remember to read the state file first. | 已经接近可操作 | startup/state-file-read：check：`read_state_file`（更严格：第一个 tool call 之前读取） |

- 六行里五行原本是愿望式或不可检查的，只有最后一行接近可操作——这正是练习 5 想让你统计的比例。skill 要求：愿望式超过 50% 时要先把这个发现告诉项目方，"The rule set will look thin; that is correct."
- 加分点：给每条规则加 severity（billing 与 prod 用 block，风格用 warn）。

### Q17 — 参考回答要点

- **不完全同意**：讲义："The fix is not a shorter file. It is a layered one." 单纯删短会丢掉真正有用的规则。
- **分层**：
  - router（`AGENTS.md`，约 50 行内）：仓库是什么、去哪里找、5 条硬规则，只有指针；
  - `docs/agent-rules.md`：完整规则集，启动时读，每个类别一屏；
  - `docs/architecture.md`、`testing.md`、`deploy.md`：任务涉及时才读，deploy 还挂在审批规则后面。
- **两个测试**：可达性（任何规则至多两跳、按路径链接）；新鲜度（router 短到每次 PR 都会被重读）。失效链接本身是 startup 违规，应由 lint 检查。
- **配套机制**：把散文改写成带 check 的规则；加 severity 与过期；删除而不是注释掉过期规则。
- **注意口径差异**：本节讲义给 router 的预算是"under ~50 lines"，而第 32 节的 skill 与练习用的是 80 行上限——两者都是经验值，团队应选一个并用 lint 强制执行。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 32 最小 Agent 工作台](../../32-minimal-agent-workbench/docs/zh.md)：本节的规则文件就是第 32 节 `AGENTS.md` 里指向的 `docs/agent-rules.md`。
- [阶段 14 · 31 Agent 工作台工程：能力强的模型为什么仍会失败](../../31-agent-workbench-why-models-fail/docs/zh.md)：Instructions surface = policy + function metadata。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)：运行时 guardrail 如何实现这些规则。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：LangGraph interrupt 与人在回路。

### 本节被哪些后续内容用到
- [阶段 14 · 34 代码仓库记忆与持久状态](../../34-repo-memory-and-state/docs/zh.md)：startup 规则检查的"状态文件新鲜"依赖它。
- [阶段 14 · 35 面向 Agents 的初始化脚本](../../35-initialization-scripts/docs/zh.md)：把 startup 类规则做成会话开始前自动执行的脚本。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：把 forbidden 类扩展成每个任务的 scope 合约。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：消费 `rule_report.json`，签名记录 block 规则的覆盖。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)：审查者依据规则集打分。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../27-prompt-injection-defense/docs/zh.md)：为什么安全边界不能依赖 LLM 判断。

### 延伸关键词
`operational vs aspirational rule` · `deterministic check` · `fail closed` · `severity: block / warn / info` · `rule expiry` · `lock file` · `pre-commit hook` · `progressive disclosure` · `guardrails` · `interrupts` · `policy as code` · `path normalization`
