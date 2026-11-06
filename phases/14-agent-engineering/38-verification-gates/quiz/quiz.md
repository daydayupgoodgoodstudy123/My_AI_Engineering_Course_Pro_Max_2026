# 测验 · Verification Gates（Verification Gates）

> **阶段 14 · Agent 工程 · 第 38 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | agent 不能给自己判"完成" | 三种典型失败："Looks good"（读自己的 diff 就认定正确）、"Tests passed"（没有运行记录）、"Acceptance met"（把验收标准解释得很宽） |
| 2 | Verification gate 的定义 | 一个基于工作台产物（scope 报告、rule 报告、feedback 记录、diff）的**确定性函数**，只回答一个问题：这个任务真的完成了吗？ |
| 3 | 检查表 | 验收命令都跑了且退出码为 0、没有 forbidden 写入、没有越界写入（block 或 warn）、block 级规则都通过、feedback 里没有 `null` 退出码 |
| 4 | block 与 warn | `warn` 只在结论上加注释；任何 `block` 都使 `passed` 不能为 true |
| 5 | 确定性，不用 LLM 判官 | 同一组产物每次得到同一个结论；LLM 判官属于 reviewer 一侧（第 39 节），负责定性评价而非状态判定 |
| 6 | 一份报告、一个路径 | 每个任务一份 `outputs/verification/<task_id>.json`，CI 与人读同一个文件；多个路径会分叉真相来源 |
| 7 | 无例外拒绝 + 签名 override | block 只能由人类 override，必须记录 `override_reason` 与 `overridden_by`；讲义："the line between an override policy and an override theater" |
| 8 | 纵深防御 | pre-commit hook → CI status check → pre-tool 授权 hook → pre-merge gate，每层都确定性；gate 位于 CI / pre-merge 层 |
| 9 | Hybrid Norm | 可验证奖励（单测、schema、退出码）回答"解决问题没有"；LLM 评分细则回答"可读、安全、合规范吗"；混在一起会让信号坍缩 |
| 10 | 覆盖率下限与 `--strict` | 覆盖率低于下限（默认 80%）或比上次合并下降超过 1 个百分点 → block，防止 agent 悄悄删掉失败的测试；`--strict` 把所有 warn 升级为 block，只在发布分支等场景按分支开启 |

### 核心技能（能动手做到）

- [ ] 读懂 `verify()` 如何把四类检查的 findings 拼接、可选地升级严重度、再得出 `passed`
- [ ] 手算覆盖率检查在边界值（恰好下降 1 个百分点、浮点误差）下的结果
- [ ] 指出 gate 在"产物缺失 / 为空"时是 fail-open 还是 fail-closed，并改为 fail-closed
- [ ] 把第 37 节的 feedback 记录（argv 列表）正确接入本节 gate，处理命令规范化与重试
- [ ] 用 HMAC 为 override 签名并验证，说清 HMAC 能证明什么、不能证明什么
- [ ] 为一个项目设计"哪些检查 block、哪些 warn、何时开启 strict、override 怎么审计"

---

## 二、基础自测（选择题）

**Q1.** 讲义说 verification gate 只回答"一个问题"。这个问题是：

- A. 这段代码写得好不好看？
- B. agent 是否在聊天里说了"完成"？
- C. 这个任务是否真的完成了？（依据 scope、rule、feedback、diff 等产物）
- D. 这个改动是否需要更多测试？

**Q2.** 为什么讲义要求 gate 是确定性的，不使用 LLM 判官？

- A. 同一组产物必须每次得到同一个结论；LLM 判官适合放在 reviewer 一侧做定性评价，而 gate 负责的是状态判定
- B. LLM 太贵，确定性检查更便宜
- C. LLM 无法读取 JSON
- D. 确定性检查一定比 LLM 更准确

**Q3.** 本节 demo 的 T-001：覆盖率从 `previous=0.85` 降到 `current=0.84`，下限 0.80，回归阈值 `COVERAGE_REGRESSION_DELTA=0.01`。实际输出是：

- A. `[block] coverage.regression`，因为 `0.85 − 0.84` 在浮点中等于 `0.010000000000000009`，大于 0.01
- B. 没有任何覆盖率 finding
- C. `[block] coverage.below_floor`
- D. `[warn] coverage.minor_regression`，任务整体 `passed=True`

**Q4.** 用 `python3 code/main.py --strict` 运行，T-001 的结果是：

- A. `passed=True`，strict 只影响 T-002
- B. `passed=False`，因为唯一的 `coverage.minor_regression` 从 warn 被升级成了 block
- C. `passed=True`，strict 只会把 block 降级为 warn
- D. 程序报错退出

**Q5.** 关于 block 级 finding 的 override，讲义的规定是：

- A. agent 在确认问题无害后可以自行 override
- B. 只要在 Slack 里有人同意即可
- C. 只能由人类 override，并记录 `override_reason` 和 `overridden_by`，以签名条目写入审计日志
- D. block 级 finding 任何人都不能 override

**Q6.** 某任务的 feedback 依次有两条记录：验收命令第一次 `exit_code=1`，修复后同一命令重跑 `exit_code=0`。其他产物都干净。按本节 `verify()`，结果是：

- A. `passed=False`，产生 `acceptance.failed`（block），因为代码检查每一条匹配记录，不看先后顺序
- B. `passed=True`，因为最后一次成功了
- C. `passed=False`，产生 `acceptance.missing`
- D. `passed=True`，因为非零退出码只是 warn

**Q7.** 构造 `Artifacts(task_id="T", acceptance_commands=[], feedback=[], scope_report={}, rule_report=[], coverage_report={"current": 0.9, "previous": 0.9})` 交给 `verify()`，结果是：

- A. `passed=False`，因为没有任何验收命令
- B. `passed=False`，因为 rule report 为空
- C. 抛出 `KeyError`，因为 scope_report 缺少键
- D. `passed=True`，findings 为空——什么都没证明，却通过了

**Q8.** 讲义为什么把覆盖率下限（coverage floor）作为一等检查？

- A. 覆盖率越高，模型越便宜
- B. 没有这个检查，agent 可能悄悄删掉失败的测试，而验证报告依然是绿色的
- C. CI 平台要求必须有覆盖率
- D. 覆盖率可以代替验收命令

---

## 三、动手 / 代码题

**Q9.** 把第 37 节 runner 产出的记录直接喂给本节 gate：

```python
feedback = [{"command": ["pytest", "-x", "test_app.py::test_signup_rejects_short_password"], "exit_code": 0}]
```

而 `_acceptance_findings` 是这样比较的：

```python
    commands_run = [str(rec.get("command")) for rec in art.feedback]
    ...
        if cmd not in commands_run:
            findings.append(Finding("acceptance.missing", "block", f"never ran: {cmd}"))
```

1. 结果是什么？为什么？
2. 写一个 `norm(cmd)` 让"字符串命令"和"argv 列表"可以可靠比较，并说明它还能顺带解决什么问题、不能解决什么问题。

**Q10.** 针对 Q6 的问题，重写 `_acceptance_findings`：

- 对每条验收命令，只看**最新**一条匹配记录；
- 最新记录 `exit_code is None` → `feedback.null_exit`；非 0 → `acceptance.failed`；没有 → `acceptance.missing`；
- 写出"先失败后成功""先成功后失败"两种序列的结果。

再思考：原实现对"任何一条 feedback 记录 `exit_code=None` 都 block"（包括与验收无关的探测命令），这是否合理？只看最新记录又会引入什么新风险？

**Q11.** skill 的拒绝规则要求 fail closed："If the rule report does not exist, refuse to skip the rule check"、"If the feedback log does not exist ... missing logs are themselves a block"、"If the project has no acceptance command, refuse to ship the gate"。结合 Q7：

1. 本节代码在哪些"产物缺失/为空"的情况下会 fail open？
2. 写一个 `fail_closed_findings(art)`，并说明 `Artifacts` 的字段类型应如何调整才能区分"缺失"和"为空"。

**Q12.** 阅读 override 相关代码：

```python
def _sign(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_load_override_secret().encode(), canonical, hashlib.sha256).hexdigest()[:32]

def record_override(task_id, finding_code, reason, user_id, head_commit):
    if not all([task_id, finding_code, reason, user_id, head_commit]):
        raise ValueError(...)
    ...
```

在 `VERIFY_DEMO_MODE=1` 下执行 `record_override("T-999", "made.up.code", "because", "agent-self", "deadbee")`，再调用 `verify_signature`。

1. 结果是什么？由此指出这套 override 机制的至少三个缺口（提示：finding 是否存在、严重度、`verify()` 是否读取 override、"签名"证明了谁）。
2. 写一个 `apply_overrides(report, entries, head_commit)`，只让签名有效、task 与 HEAD 都匹配的条目把对应的 block finding 标记为 `overridden`，并重新计算 `passed`。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 verification gate？它和单元测试、和 LLM-as-judge 分别是什么关系？

**Q14.**（原理深挖）为什么讲义坚持"gate 确定性、reviewer 用 LLM"的分工？如果把 LLM 判官放进 gate，会出现哪些具体问题？

**Q15.**（工程实践）请为一个 agent 写代码的仓库设计 gate 的检查表：每项检查的来源产物、严重度、fail-open/fail-closed 策略，以及 `--strict` 的开启条件。

**Q16.**（场景设计）设计 override 流程：谁能 override、记录什么、如何防伪造、如何防止"override 剧场"、如何在之后被审计。

**Q17.**（追问型）agent 在 gate 失败后"学会了"绕过：删掉失败的测试、把验收命令改成 `true`、或删除 feedback 里的失败记录。你怎么防？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义开头："answers a single question: is this task actually complete? If the gate says no, the task is not done, no matter what the chat says."A 是 reviewer（第 39 节）关心的质量问题；B 正是讲义要否定的"相信叙述"；D 是覆盖率检查的一部分，但不是 gate 要回答的核心问题。

### Q2 — 答案：A

讲义："The gate must produce the same verdict for the same artifact set every time. No LLM judges. LLM judges belong on the reviewer side ... where the goal is qualitative evaluation, not status."B 不是讲义的理由；C 错误；D 过度绝对——确定性检查的价值在于可复现、可审计、不可被说服（"The agent cannot bribe it"），而不是在一切问题上更准。

### Q3 — 答案：D

实际输出：`[warn] coverage.minor_regression: coverage dropped 1.00%`，`passed=True`。`0.85 − 0.84` 在浮点中确实是 `0.010000000000000009`，单看 `delta > 0.01` 为真，但代码追加了 `not math.isclose(delta, COVERAGE_REGRESSION_DELTA, rel_tol=1e-9)`，恰好处理了这个浮点边界，所以不算 regression，落入 `elif delta > 0` 的 warn 分支。A 是没有 `isclose` 时会出现的 bug；B 错，下降了就会有 warn；C 错，0.84 ≥ 0.80。实测：`0.85 → 0.839` 才会触发 block。

### Q4 — 答案：B

`--strict` 的实现：

```python
        findings = [Finding(f.code, "block" if f.severity == "warn" else f.severity, f.detail)
                    for f in findings]
```

T-001 唯一的 finding 是 minor_regression（warn），升级后成为 block，`passed=False`（实测：`task T-001 (strict): passed=False findings=1`）。这说明 strict 会让一个正常的、只下降 1 个百分点的任务失败——讲义正因如此说"not the global default, because strict-on-everything corrodes day-to-day flow"。A、C 与代码不符；D 错，程序正常退出（退出码 0）。

### Q5 — 答案：C

讲义："Block-severity findings cannot be overridden by the agent. They can only be overridden by a human, with a recorded `override_reason` and an `overridden_by` user id. The override is a signed change, not an agent decision."生产模式部分还要求写入 `outputs/verification/overrides.jsonl`，含时间戳、finding code、原因、签名用户、当前 HEAD。A 正是要禁止的；B 是讲义批评的"Slack threads"；D 过于绝对，讲义允许人类签名 override。

### Q6 — 答案：A

实测：`retry False [('block', 'acceptance.failed')]`。第二个循环遍历**每一条**记录，只要某条匹配验收命令的记录退出码非 0 就 block，不管后面有没有成功的重试。后果是：正常的"失败 → 修复 → 重跑成功"流程永远过不了 gate，反而诱导 agent 去删除失败记录或换一种写法重跑（让命令字符串不再匹配）。B 是讲义意图下更合理的结果，但不是代码行为（修复见 Q10）；C 错，命令跑过了；D 错，`acceptance.failed` 是 block。

### Q7 — 答案：D

实测：`empty True []`。没有验收命令 → 没有 `acceptance.missing`；feedback 为空 → 没有 null exit；`scope_report.get(...)` 取不到键 → 视为没有越界；rule report 为空列表 → 没有失败规则；覆盖率正常。于是一个什么都没证明的任务通过了 gate。这正是 skill 所说的"A gate that proves nothing is theater"，应当 fail closed（见 Q11）。A、B 是应有的行为但代码没有实现；C 错，代码用的是 `.get()`，不会抛 `KeyError`。

### Q8 — 答案：B

讲义："Without this check, agents quietly delete tests that fail and the verification reports stay green."验收命令只证明"指定的那几个测试通过"，删掉其他失败测试不会影响它们；覆盖率下限与"相对上次合并的回归"能把这类行为暴露出来。A、C 不是理由；D 错，覆盖率衡量的是测试覆盖面，不能证明功能符合验收标准。

### Q9 — 参考答案

1. 结果：`passed=False`，`[block] acceptance.missing`（实测）。`str(["pytest", "-x", "..."])` 得到的是 `"['pytest', '-x', '...']"`，与合同里的字符串 `"pytest -x test_app.py::..."` 永远不相等。第 37 节的 runner 按讲义要求记录"exact argv"（列表），第 38 节的 gate 却按字符串比较，两节课的产物接不上。
2. 规范化：

   ```python
   import shlex

   def norm(cmd):
       return shlex.join(cmd) if isinstance(cmd, list) else shlex.join(shlex.split(str(cmd)))
   ```

   实测：argv 列表与字符串都规范化为 `pytest -x test_app.py::test_signup_rejects_short_password`，能匹配；`"pytest  -x   test_app.py::..."`（多余空格）也能匹配。
   - 能解决：列表 vs 字符串、多余空白、引号写法不同。
   - 不能解决：语义等价但写法不同的命令（`python -m pytest` vs `pytest`、`-x` 参数顺序不同、`cd sub && pytest`）。更稳妥的做法是在合同里给验收命令一个 ID，runner 在记录中带上这个 ID，gate 按 ID 匹配。

### Q10 — 参考答案

```python
def acceptance_findings_v2(art):
    findings = []
    latest = {}
    for rec in art.feedback:                       # 记录按时间顺序，后面的覆盖前面的
        latest[norm(rec.get("command"))] = rec
    for cmd in art.acceptance_commands:
        rec = latest.get(norm(cmd))
        if rec is None:
            findings.append(Finding("acceptance.missing", "block", f"never ran: {cmd}"))
        elif rec.get("exit_code") is None:
            findings.append(Finding("feedback.null_exit", "block", f"missing exit for {cmd}"))
        elif rec.get("exit_code") != 0:
            findings.append(Finding("acceptance.failed", "block", f"latest exit {rec['exit_code']} on {cmd}"))
    return findings
```

实测：先失败后成功 → `[]`（通过）；先成功后失败 → `['acceptance.failed']`（拦截）；argv 列表 → `[]`。

讨论：

- **"任何 null 都 block"**：讲义的检查表确实写了"No `null` exit codes in feedback: block"，原实现与讲义一致；但它会让一次无关的探测（比如 `which foo` 超时）阻塞整个任务。更合理的是：验收命令的 null 一律 block；非验收命令的 null 作为 warn 记录，或要求 agent 对其有后续处理。
- **只看最新的新风险**：agent 可能在最后一次代码修改**之前**跑过测试并通过，之后又改了代码——最新的测试记录已经过期。要求验收记录的时间晚于最后一次文件写入，或记录运行时的 git tree hash 并与最终 diff 对齐。另外应通过 `parent_command_id` 保留失败历史，交给 reviewer 审阅，而不是直接丢弃。

### Q11 — 参考答案

1. fail-open 的情形（均实测或由代码直接可见）：
   - `acceptance_commands=[]` → 没有任何验收检查；
   - `feedback=[]` 且没有验收命令 → 不报任何问题；
   - `rule_report=[]`（或文件不存在被读成空列表）→ 规则检查被跳过；
   - `scope_report={}` 或缺少 `forbidden_writes` 键 → 视为没有越界；
   - 只有覆盖率缺失时是 warn（不是 block）。
2. 参考实现（已运行）：

   ```python
   def fail_closed_findings(art):
       f = []
       if not art.acceptance_commands:
           f.append(Finding("gate.no_acceptance", "block", "no acceptance command: a gate that proves nothing is theater"))
       if art.rule_report is None:
           f.append(Finding("gate.rule_report_missing", "block", "rule_report.json missing"))
       if art.feedback is None:
           f.append(Finding("gate.feedback_missing", "block", "feedback_record.jsonl missing"))
       for key in ("forbidden_writes", "off_scope_writes"):
           if art.scope_report is None or key not in art.scope_report:
               f.append(Finding("gate.scope_report_incomplete", "block", f"scope_report lacks {key}"))
       return f
   ```

   `Artifacts` 的字段要改成 `list[...] | None`、`dict[...] | None`，由 loader 在**文件不存在**时返回 `None`，文件存在但为空时返回 `[]`/`{}`。"没有规则失败"（空列表）和"根本没有规则报告"（None）必须是两种不同的状态——这与第 36 节 `network_egress` 用 `None`/`[]` 区分三态是同一个思路。另外，skill 要求报告中列出所消费的产物路径（"A verification report that omits the artifact paths it consumed" 是 hard reject），本节报告也没有这一项。

### Q12 — 参考答案

1. 实测：`forged override verified: True`。缺口：
   - **不校验 finding 是否存在**：`made.up.code`、`T-999` 都能被签名记录；
   - **不校验严重度**：讲义说 override 针对 block 级 finding，而 demo 恰恰去 override T-002 的 `scope.off_scope`——一个 warn；T-002 仍有 4 条 block，这次 override 对结果毫无影响；
   - **`verify()` 根本不读 override**：`overrides.jsonl` 写了也不改变任何结论，override 只是一份日志；
   - **"签名"证明的是"持有共享密钥"，不是"某个人"**：HMAC 用的是同一个 `VERIFY_OVERRIDE_SECRET`，`user_id` 是调用者自己填的字符串。如果 agent 的运行环境里有这个环境变量，agent 就能以任何人的名义签名（上面的 `agent-self` 就是例子）。真正的"signed by user"需要非对称签名（个人 GPG/SSH 密钥签名的 commit、Sigstore 等）或经过身份认证的审批系统；
   - 签名截断为 32 个十六进制字符（128 位），对防伪仍足够，不是主要问题；`_load_override_secret()` 在每次签名时都会被调用，所以 demo 模式下警告打印了两次。
   - 另外，代码通过"未设置密钥就拒绝"实现了 fail closed，这一点是对的（默认运行时 override demo 被跳过）。
2. 参考实现（已运行）：

   ```python
   def apply_overrides(report, entries, head_commit):
       by_code = {}
       for e in entries:
           if (e.get("task_id") == report.task_id and e.get("head_commit") == head_commit
                   and verify_signature(e)):
               by_code[e["finding_code"]] = e
       new = []
       for f in report.findings:
           if f.severity == "block" and f.code in by_code:
               e = by_code[f.code]
               new.append(Finding(f.code, "overridden", f"{f.detail} | by {e['user_id']}: {e['reason']}"))
           else:
               new.append(f)
       report.findings = new
       report.passed = not any(f.severity == "block" for f in new)
       return report
   ```

   实测：一个只有 `scope.forbidden` 的任务，override 前 `passed=False`；用匹配的 task 与 HEAD 签名 override 后 `passed=True`，finding 被标为 `overridden` 并保留原因；HEAD 变化（`fff0000`）后 override 失效，`passed=False`。绑定 HEAD 是关键：代码改了，旧的豁免就不该继续有效。

### Q13 — 参考回答要点

- **定义**：一个读取工作台产物（scope 报告、rule 报告、feedback 记录、覆盖率、diff）的确定性纯函数，输出一份 `verification_report.json`；block 级 finding 一律拒绝"完成"。
- **与单元测试**：单元测试是 gate 的**输入**之一——gate 不自己跑测试，而是检查验收命令是否在 feedback 里真实运行且退出码为 0。gate 还检查测试之外的东西：越界写入、规则、覆盖率回归。
- **与 LLM-as-judge**：讲义的 Hybrid Norm——可验证奖励回答"解决问题没有"（gate）；LLM 评分细则回答"可读、安全、风格"（reviewer）。gate 通过后才交给 reviewer。
- 加分点：gate 放进版本控制、接入 CI 与合并保护（"The agent cannot bribe it"）；它是 handoff 的前置条件（"No green verdict, no handoff"）。

### Q14 — 参考回答要点

- **可复现**：同样的产物必须得到同样的结论，才能用于合并保护、事后审计、回归对比。LLM 有采样随机性，即使 temperature 为 0，模型版本、提示词变化也会改变结论。
- **不可说服**：LLM 判官会被 diff 里的注释、commit message、甚至 prompt injection（"这个改动已被批准"）影响；确定性检查只看事实。
- **信号不坍缩**：讲义："Mixing them collapses the signal."如果"测试没跑"和"命名不优雅"混在同一个 LLM 打分里，一个 8/10 的分数无法告诉你任务是否完成。
- **成本与延迟**：确定性检查毫秒级，适合每次提交运行。
- **LLM 的正确位置**：reviewer 做定性评审，输出建议或需人类关注的点，但不决定状态。
- 加分点：讲义延伸阅读提到用 Lean 4 等形式化方法作为"确定性 gate 的上限"。

### Q15 — 参考回答要点

| 检查 | 来源产物 | 严重度 | 产物缺失时 |
|------|---------|-------|-----------|
| 每条验收命令都有记录 | feedback JSONL | block | block（fail closed） |
| 验收命令最新记录退出码为 0，且晚于最后一次写入 | feedback + diff/时间戳 | block | block |
| 验收相关记录无 null 退出码 | feedback | block | — |
| 无 forbidden 写入 | scope 报告 | block | block |
| 越界写入 | scope 报告 | 按路径族：docs warn，scripts/migrations block | block |
| block 级规则全部通过 | rule 报告 | block | block |
| 覆盖率 ≥ 下限且不比上次下降 > 1pp | coverage 报告 | block（小幅下降 warn） | 至少 warn，发布分支 block |
| touched files ⊆ allowed | diff + 合同 | warn | — |

- `--strict`：发布分支、阻塞发布的 PR、事故后排查时按分支开启（讲义）；日常分支关闭。
- 报告写到唯一路径 `outputs/verification/<task_id>.json`，并列出消费的产物路径与 HEAD。
- 常见误区：本节代码的报告写在 `code/verification_report_<id>.json`，与讲义"一份报告、一个路径"的约定不符；"产物缺失按空处理"会 fail open。

### Q16 — 参考回答要点

- **谁能 override**：只有人类，且只能针对 block 级 finding；agent 无权调用 override 工具（运行环境里不应有签名凭据）。
- **记录什么**：task_id、finding code、原因、用户、HEAD commit、时间戳、签名（讲义）；最好还有过期时间与关联工单。
- **防伪造**：用个人身份签名（GPG/SSH 签名 commit、Sigstore、或经过 SSO 的审批服务），而不是所有人共享一个 HMAC 密钥；override 文件纳入版本控制（skill："off-the-record overrides defeat the gate"）。
- **防剧场**：override 必须绑定 HEAD（代码变了自动失效）；gate 在结论中显示 `overridden` 而不是把 finding 删掉；统计 override 率，过高说明检查本身需要调整。
- **审计**：reviewer 与定期审计读取 `overrides.jsonl`；本节代码的缺口（不校验 finding 存在、verify 不读 override）要补上（见 Q12）。

### Q17 — 参考回答要点

- **删失败测试**：覆盖率下限 + 相对上次合并的回归检查（讲义的主要动机）；测试文件放进合同的 forbidden 或需审批的路径；统计测试数量的变化。
- **把验收命令改成 `true`**：验收命令来自合同（第 36 节），合同文件本身应在 forbidden 中，agent 不能修改；gate 只认合同里的命令，不认 agent 自报的命令。
- **删除失败记录**：feedback 由 runner 写入，agent 不应有写权限；记录用 `parent_command_id` 成链，重试历史缺环可被检测；JSONL 作为 CI artifact 另存一份。
- **纵深防御**：pre-commit hook、CI、pre-tool 授权 hook、pre-merge gate 各自独立，一层被绕过还有下一层（讲义）。
- **reviewer**：第 39 节的独立 reviewer 会对照合同与 diff 发现"测试变少""断言被削弱"等问题。
- 常见误区：用 prompt 告诉 agent "不要删测试"——这正是本阶段反复否定的做法。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../33-instructions-as-executable-constraints/docs/zh.md)：rule report 的来源。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：scope report 与验收命令的来源。
- [阶段 14 · 37 运行时反馈循环](../../37-runtime-feedback-loops/docs/zh.md)：feedback JSONL 的来源，gate 用它确认验收命令真的跑过。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：可验证的评估信号是 gate 的基础。

### 本节被哪些后续内容用到
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)：gate 通过后交给 reviewer 做定性评审。
- [阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：handoff 前必须有绿色结论，并把结论写入交接包。
- [阶段 14 · 41 在真实代码仓库中使用工作台](../../41-workbench-for-real-repos/docs/zh.md)：在接近真实的项目上运行 gate。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../27-prompt-injection-defense/docs/zh.md)：gate 的"对抗搭档"。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/zh.md)：人类审批与 override 的系统化做法。

### 延伸关键词
`deterministic gate` · `fail closed` · `block / warn` · `--strict` · `coverage floor` · `verifiable rewards` · `LLM-as-judge` · `HMAC vs signature` · `override audit log` · `defense in depth` · `merge protection` · `single source of truth`
