# 测验 · 基于 Harness 的端到端 Coding Agent（End-to-End Coding Agent on the Harness）

> **阶段 19 · 综合项目 · 第 29 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/fixture_repo/src/fizz.py](../code/fixture_repo/src/fizz.py)、[code/fixture_repo/tests/test_fizz.py](../code/fixture_repo/tests/test_fizz.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)（fixture 文件的说明已并入其中第 3.10 节）
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 集成才暴露接缝 | 讲义："Compose them and the seams show"——gate 放行但 sandbox 拒绝、eval 记通过但 span 显示被拒、预算只在一处被追踪等问题，只有把组件拼起来才会出现 |
| 2 | Policy seam（策略接缝） | agent 的"大脑"被抽象成 `next_action / observe` 两个方法；本节用确定性状态机代替 LLM，harness 契约不变，换上真模型只需替换 policy |
| 3 | 状态机 | `SURVEY → RUN_TESTS → INSPECT → FIX → VERIFY → HALT`；每个状态对应一次工具调用；首次测试通过则直接 HALT |
| 4 | 每一步的必经之路 | policy 产出 `ToolCall` → `GateChain.evaluate`（白名单 → 正则 → 预算，短路）→ 放行后在 tool span 内执行（read/write 走路径检查，run_tests 走 `Sandbox`）→ 记录 `Observation` 到 ledger → `policy.observe` 推进状态 |
| 5 | 两种预算 | 步数预算 `step_budget`（for 循环上限）与观察 token 预算（`len(text)//4` 估算，`BudgetGate` 在调用前检查、`AgentRun` 在调用后检查） |
| 6 | 纵深防御 | gate chain 看"意图"（工具名、参数文本），sandbox 看"执行"（可执行文件 denylist、路径 jail、超时、输出截断），两层各管一部分 |
| 7 | 可观测性 | 一个 `gen_ai.chat` 父 span + 每个被执行的工具一个 `gen_ai.tool.execution` 子 span；工具 span 驱动 `tools_called_total` 与 `tool_latency_ms` |
| 8 | 验收断言 | 讲义承诺：少于 12 步解决、观察预算不超、合法工具零拒绝、每步有 span、Prometheus 输出含 `tools_called_total{tool="read_file"}` 与 `tool_latency_ms` |
| 9 | Fixture 任务 | `fizz.py` 中 `range(1, n)` 的 off-by-one；3 个 unittest 全部失败；修复为 `range(1, n + 1)` 后全部通过 |
| 10 | 实现与讲义的差距 | 修复是**硬编码**的而非正则识别；被拒绝的调用不产生 span；没有 eval harness 与 `expected/` 目录；步数恰好用完时会误判失败 |

### 核心技能（能动手做到）

- [ ] 画出一次工具调用从 policy 到 gate、sandbox、span、ledger 再回到 policy 的完整路径
- [ ] 跑通 demo，逐行解释 5 个步骤、6 个 span、673 个观察 token 的来源
- [ ] 找出并修复 `AgentRun.run` 中"步数恰好用完时 solved=False"的边界 bug
- [ ] 把硬编码修复改成真正从测试输出中推断补丁的 policy，并让 policy 可注入
- [ ] 识别 harness 的安全缺口（`run_tests` 可执行任意 argv、路径 jail 跳过不含 `/` 的参数、`^/etc/` 正则锚点），并给出加固方案
- [ ] 说明把确定性 policy 换成 LLM 时，harness、评估方式和预算需要做哪些调整

---

## 二、基础自测（选择题）

**Q1.** 运行 demo，agent 实际执行的工具调用序列是：

- A. `list_dir` → `run_tests` → `read_file(src/fizz.py)` → `write_file` → `run_tests`，共 5 步
- B. `read_file(src/fizz.py)` → `write_file` → `run_tests`，共 3 步
- C. `read_file(src/fizz.py)` → `run_tests` → `read_file(tests/test_fizz.py)` → `write_file(src/fizz.py)` → `run_tests`，共 5 步
- D. `run_tests` → `read_file(src/fizz.py)` → `write_file` → `run_tests` → `run_tests`，共 5 步

**Q2.** 讲义说"The deterministic policy detects the bug from the test failure message via a regex"。实际代码中 `INSPECT` 状态是怎样得出修复内容的？

- A. 根本没有分析：`if` 与 `else` 两个分支写入的是同一段硬编码的修复代码；条件里的 `"expected"` 之所以能匹配上，是因为测试方法名（如 `test_n_5_expected_list`）里含有这个词
- B. 用正则解析 `AssertionError: Lists differ` 中两个列表的长度差，再据此生成补丁
- C. 对比 `src/fizz.py` 与 fixture 中的 `expected/` 目录生成 diff
- D. 读取 `tests/test_fizz.py` 的内容，用 AST 推导出正确实现

**Q3.** 当 `GateChain` 拒绝了某次工具调用时，当前实现在 trace 中留下了什么？

- A. 一个 `status=ERROR` 的 `gen_ai.tool.execution` span，带 `exception` event
- B. 一个 `status=OK` 的 tool span，`exit_code` 属性为 `-100`
- C. 一个名为 `gate.refused` 的独立 span
- D. 不产生任何 tool span：只在 `steps` 里追加一条 `allow=False`、`exit_code=-100` 的 `AgentStep`，然后跳出循环，父 `gen_ai.chat` span 仍以 `OK` 结束

**Q4.** demo 输出 `obs_tokens=673/8000`。5 个步骤中，消耗观察 token 最多的是哪一步？

- A. 第 0 步 `SURVEY` 读取 `src/fizz.py`
- B. 第 1 步 `RUN_TESTS`：3 个测试全部失败，unittest 输出了很长的 traceback（约 481 token）
- C. 第 3 步 `FIX` 写文件，因为 payload 计入观察
- D. 第 4 步 `VERIFY`，因为第二次运行测试要重新加载模块

**Q5.** 其他条件不变，把 `AgentRun` 的 `step_budget` 从 12 改成 5（恰好等于所需步数），结果是：

- A. `solved=False`、`halted_reason="step budget exhausted"`——第 5 步 VERIFY 已通过、policy 已进入 HALT，但循环在下一轮检查 HALT 之前就结束了
- B. `solved=True`、`halted_reason="policy reached HALT"`
- C. 抛出 `AssertionError`，因为 FIX 状态没有拿到修复内容
- D. agent 只执行 4 步，跳过 VERIFY

**Q6.** 第 1 步 `RUN_TESTS` 的测试运行退出码为 1。对应的 `gen_ai.tool.execution` span 的状态是什么？

- A. `ERROR`，因为退出码非 0
- B. `UNSET`，因为 span 没有正常结束
- C. 该步不产生 span
- D. `OK`，退出码只作为非标准属性 `exit_code=1` 记录；span 状态只反映 `with` 块内是否有 Python 异常

**Q7.** 使用 `build_default_chain()` 与 `Sandbox` 默认配置，下列哪一次 `run_tests` 调用能**同时通过** gate chain 和 sandbox，真正被执行？

- A. `argv=("rm", "-rf", "src")`
- B. `argv=("rm", "-r", "src")`
- C. `argv=(sys.executable, "-c", "import shutil; shutil.rmtree('src')")`
- D. `argv=("cat", "/etc/passwd")`

**Q8.** 保持 `build_default_chain(budget=8000)` 不变，只把 `AgentRun(observation_budget=300)`。实际运行结果是：

- A. 第一次 `read_file` 前就被 `BudgetGate` 拒绝
- B. 执行完第 2 步（第一次 `run_tests`）后，ledger 已累计 498 token，超过 300，`AgentRun` 以 "observation budget 300 exceeded" 停止，`solved=False`——预算是"事后检查"，会超出
- C. 正常解决，因为 `BudgetGate` 的 8000 优先
- D. 截断第一次 `run_tests` 的输出使其不超过 300 token，然后继续

---

## 三、动手 / 代码题

**Q9.** 阅读 `AgentRun.run` 的循环骨架：

```python
            for step_index in range(self.step_budget):
                if policy.state == "HALT":
                    halted_reason = "policy reached HALT"
                    solved = policy.tests_passed
                    break
                tool, argv, payload = policy.next_action(last_obs)
                ...
                policy.observe(tool, exit_code, text)

            else:
                halted_reason = halted_reason or "step budget exhausted"
```

1. 解释为什么 `step_budget=5` 时会误判为失败（Q5），而 `step_budget=6` 时成功且只用了 5 步。
2. 修改代码，使"第 N 步刚好让 policy 进入 HALT"时也能正确判定。
3. 讲义要求"fewer than 12 steps"，`run_demo` 用的是 `len(report.steps) >= 12` 判错。修复前后，这个断言能否发现 Q5 的问题？

**Q10.** 把 `INSPECT` 改成真正"从测试失败信息推断补丁"：写一个 `propose_fix(test_output: str, source: str) -> str | None`，用正则提取 unittest 的 `Lists differ: [...] != [...]`，若**每一处**失败都是"实际结果比期望恰好少最后一个元素"，就把源码里的 `range(1, n)` 改成 `range(1, n + 1)`；否则返回 `None`（policy 应停止而不是乱改）。再说明：当前 `AgentRun.run` 里写死了 `CodingAgentPolicy(...)`，要让讲义说的 "policy seam" 真正可替换，应该怎样改？

**Q11.** 安全审计。请针对下列三处代码各给出一个能绕过防护的例子，并提出修复：

```python
# (a) build_default_chain
RegexGate.from_strings(items=(r"\brm\s+-rf\b", r"\bsudo\b", r"^/etc/"))

# (b) Sandbox._path_jail
for arg in argv[1:]:
    if not arg or arg.startswith("-"):
        continue
    if "/" not in arg and ".." not in arg:
        continue
    ...

# (c) policy 产出 run_tests 的 argv，WhitelistGate 只检查工具名
return ("run_tests", (python, "-m", "unittest", "tests/test_fizz.py"), "")
```

**Q12.** 讲义的架构图中有 `Refuse → Span ERROR`，验收条件写着 "Every step has a corresponding span in the traces.jsonl"。请指出当前实现在可观测性上的三处缺口（提示：被拒绝的调用、失败的测试、gate 决策），并给出修改后的 `run` 片段要点。

---

## 四、面试高频题

**Q13.**（基础必考）一个 coding agent 的 harness 通常由哪些部件组成？gate chain 和 sandbox 都能拦截危险操作，为什么两者都要？

**Q14.**（原理深挖）本节为什么用确定性 policy 而不是 LLM？把它换成真实 LLM 后，harness 不需要变，但评估和测试方式要怎样变？

**Q15.**（工程实践）agent 的预算（步数、观察 token、墙钟时间、费用）应该在哪里、以什么方式执行？"调用前检查"和"调用后检查"各有什么问题？

**Q16.**（场景设计）要把本节 demo 扩展成能在真实仓库上修 GitHub issue 的 agent，你会如何设计任务输入、工具集、sandbox、评估和回滚？

**Q17.**（追问型）以"测试通过"作为成功标准有什么风险？本节的 harness 能否阻止 agent 直接改测试文件来"通过"？应该怎么防？

---

## 五、参考答案与解析

### Q1 — 答案：C

实际运行输出：

```text
  [0] SURVEY     read_file   argv=['src/fizz.py'] -> ok
  [1] RUN_TESTS  run_tests   argv=['/usr/bin/python3', '-m', 'unittest', 'tests/test_fizz.py'] -> exit=1
  [2] INSPECT    read_file   argv=['tests/test_fizz.py'] -> ok
  [3] FIX        write_file  argv=['src/fizz.py'] -> ok
  [4] VERIFY     run_tests   argv=[...] -> ok
```

A 是讲义的描述（"SURVEY: the agent reads the project listing"），但代码并没有 `list_dir` 工具，SURVEY 直接读 `src/fizz.py`；讲义还说 INSPECT "reads the failing source file"，代码读的却是测试文件。B 跳过了测试与检查；D 顺序错误。

### Q2 — 答案：A

```python
            if "expected" in self.last_test_stderr and "fizz" in self.last_test_stderr.lower():
                self.identified_bug_file = "src/fizz.py"
                self.identified_fix = ("def fizz(n):\n"
                    "    return [i if i % 3 else 'fizz' for i in range(1, n + 1)]\n")
            else:
                self.identified_bug_file = "src/fizz.py"
                self.identified_fix = (... 完全相同 ...)
```

两个分支一模一样，代码里没有任何 `re` 调用用于识别 bug。实测把 `last_test_stderr` 设为 `"totally unrelated"`，得到的修复仍然相同。条件中的 `"expected"` 能命中，只是因为 unittest 的失败输出里包含测试方法名 `test_n_1_expected_single` 等。B 是测验 Q10 要你实现的东西；C 中的 `expected/` 目录讲义提到了，但 fixture 里并不存在；D 也没有实现。

### Q3 — 答案：D

gate 检查发生在 `with self.builder.span("gen_ai.tool.execution", ...)` **之前**；拒绝时直接 `steps.append(AgentStep(..., allow=False, exit_code=DENIED_EXIT, notes="gate refused"))` 并 `break`。实测：把 chain 预算设为 300，第 3 步被 `[budget]` 拒绝，结果只有 3 个 span（2 个 tool + 1 个 chat），被拒的那一步没有 span，chat span 状态仍是 OK。A 是讲义架构图（`Refuse → SpanErr[Span ERROR]`）的设计，代码没有实现；B、C 也不存在。

### Q4 — 答案：B

`estimate_tokens(text) = max(1, len(text) // 4)`。实测 5 步分别为 17、481、143、7、25，合计 673。第一次跑测试时 3 个用例全部失败，每个都有 traceback 与列表 diff，输出最长。A 只有 70 字节的源码（17 token）；C 的观察文本是 `"wrote 74 bytes to src/fizz.py"`（7 token），payload 本身不计入观察；D 测试全部通过，输出只有几行（25 token）。启示：**失败输出往往是观察预算的最大消耗者**，生产中需要截断或摘要测试输出。

### Q5 — 答案：A

实测 `step_budget=5 -> solved=False, halted_reason='step budget exhausted', steps=5`；`step_budget=6 -> solved=True, 'policy reached HALT', steps=5`。原因是 HALT 检查放在每轮循环的**开头**：第 5 步结束时 `policy.observe` 把状态设成 HALT，但 `range(5)` 已经耗尽，没有第 6 轮去检查，于是走进 `for ... else`，`solved` 保持初始值 `False`。B 是期望行为；C、D 不会发生。详见 Q9。

### Q6 — 答案：D

`SpanBuilder.span` 只在 `with` 块内抛出 Python 异常时设 ERROR。`tool_run_tests` 把退出码当作普通返回值，块内无异常，所以 span 是 `OK`，退出码写在 `tool_span.attributes["exit_code"]`。实测 6 个 span 的 `(status, exit_code)` 为 `OK/0, OK/1, OK/0, OK/0, OK/0` 和 chat 的 `OK`。A 是很多人的直觉，但"测试失败"是 agent 预期中的观察结果，是否标为 ERROR 是一个设计选择（见 Q12）；B、C 错。另外 `exit_code` 不在 GenAI 约定内，且没有加命名空间前缀。

### Q7 — 答案：C

逐个验证（已实测 gate 与 sandbox 的判定）：

| argv | gate chain | sandbox | 结果 |
|------|-----------|---------|------|
| `rm -rf src` | 被 `\brm\s+-rf\b` 拒绝 | — | 拦截 |
| `rm -r src` | **放行**（正则只认 `-rf`） | `rm` 在 denylist，拒绝 | 拦截 |
| `python -c "...rmtree('src')"` | 放行（工具名合法，参数里没有黑名单模式） | 放行（python 不在 denylist，参数不含 `/`） | **被执行** |
| `cat /etc/passwd` | 放行（`^/etc/` 只匹配整个字符串开头，而开头是 `cat`） | 路径 jail 拒绝 | 拦截 |

关键在于：`run_tests` 工具接受**任意 argv**，白名单只检查工具名。我们实测让 sandbox 执行 `python -c "import os; print(os.listdir('/etc'))"`，成功读到了根目录外的内容。黑名单永远列不全，正确做法见 Q11。

### Q8 — 答案：B

实测 `observation_budget=300 -> solved=False, 'observation budget 300 exceeded', tokens=498, steps=2`。`AgentRun` 在每次执行**之后**才比较 `ledger.cumulative() > self.observation_budget`，所以第 2 步一次就从 17 涨到 498，超出后才停。A 描述的是 `BudgetGate` 的"事前"检查，但这里 chain 的预算仍是 8000；C 错，两个预算独立，任何一个超了都会停；D 错，代码没有截断逻辑（只有 sandbox 的 32KB 字节截断）。这也揭示了讲义所说的"接缝"问题：两个预算参数分别在 `build_default_chain(budget=...)` 和 `AgentRun(observation_budget=...)` 里设置，`run_demo` 恰好都写了 8000，二者很容易不一致。

### Q9 — 参考答案

1. HALT 的判定只在每轮**开头**做。所需 5 步正好用掉 `range(5)` 的全部迭代，第 5 步的 `observe` 把状态设成 HALT 之后循环自然结束，进入 `else` 分支，`solved` 仍为 `False`。`step_budget=6` 时多出的第 6 轮只用来"发现 HALT"，并不执行工具，所以步数仍是 5。
2. 修复：在 `observe` 之后立即检查。

```python
                policy.observe(tool, exit_code, text)
                if policy.state == "HALT":
                    halted_reason = "policy reached HALT"
                    solved = policy.tests_passed
                    break
            else:
                halted_reason = halted_reason or "step budget exhausted"
```

   循环开头那段检查可以保留（处理 policy 一开始就处于 HALT 的情况），也可以删除。修复后 `step_budget=5` 返回 `solved=True`。
3. 不能。`len(report.steps) >= 12` 只检查"没用太多步"，而 Q5 的问题是"步数够了却误判失败"，它会被前面的 `if not report.solved` 捕获，demo 返回 1 并打印 `agent did not solve fixture: step budget exhausted`。这说明验收断言的错误信息会误导排查：看起来是"没解决"，实际是 runner 的 bug。好的测试应该加一条"`step_budget` 等于最少所需步数时也能成功"的边界用例。

### Q10 — 参考答案

```python
import ast
import re

LISTS_DIFFER = re.compile(r"Lists differ: (\[.*?\]) != (\[.*?\])")

def propose_fix(test_output: str, source: str) -> str | None:
    pairs = LISTS_DIFFER.findall(test_output)
    if not pairs:
        return None
    # 每一处失败都满足：期望去掉最后一个元素 == 实际结果  ->  典型的 off-by-one
    if all(ast.literal_eval(exp)[:-1] == ast.literal_eval(act) for act, exp in pairs):
        fixed, n = re.subn(r"range\(1, n\)", "range(1, n + 1)", source)
        return fixed if n == 1 else None
    return None
```

接入方式：在 `SURVEY` 的 `observe` 中保存 `self.source = text`；在 `INSPECT` 中调用 `propose_fix(self.last_test_stderr, self.source)`，返回 `None` 时直接进入 `HALT`（宁可放弃也不要瞎改）。我们用子类覆盖 `observe` 的方式验证过：agent 仍然 5 步解决，写回的文件为 `range(1, n + 1)`；对 `"Lists differ: [1, 3] != [1, 2]"` 返回 `None`。

注意 unittest 输出是 `Lists differ: <实际> != <期望>`（`assertEqual(fizz(5), expected)` 的第一个参数在左边），三处失败分别是 `[] != [1]`、`[1, 2] != [1, 2, 'fizz']`、`[1, 2, 'fizz', 4] != [1, 2, 'fizz', 4, 5]`，都满足规则。

Policy seam：`AgentRun.run` 里写死了 `policy = CodingAgentPolicy(repo_root=self.repo_root)`，替换 policy 只能改源码或 monkeypatch。应增加一个字段，例如 `policy_factory: Callable[[str], Policy] = CodingAgentPolicy`，并用 `typing.Protocol` 声明 `next_action(last_obs) -> (tool, argv, payload)` 与 `observe(tool, exit_code, text)` 两个方法；LLM policy 只要实现这两个方法即可插入。

### Q11 — 参考答案

- **(a) 正则黑名单**：
  - `rm -r -f src`、`rm --recursive src`、`find . -delete`、`python -c "shutil.rmtree(...)"` 都不匹配 `\brm\s+-rf\b`；
  - `^/etc/` 匹配的是整个 haystack（`" ".join(argv) + " " + payload`）的开头，`cat /etc/passwd` 的开头是 `cat`，匹配不到（已实测放行），只有 argv 第一个元素以 `/etc/` 开头才会被拦；至少应改为 `(^|\s)/etc/`。
  - 修复方向：正则只能当"粗筛"，不能当安全边界。
- **(b) 路径 jail**：不含 `/` 且不含 `..` 的参数一律跳过。仓库内若有一个指向外部的符号链接 `link`（我们实测 `_path_jail(["cat", "link"])` 返回 `None`），`cat link` 就能读到外部文件；另外 `python -c "open('/etc/passwd')"` 中的路径藏在代码字符串里，jail 也看不到。修复：对每个参数都 `realpath` 检查（而不只是带 `/` 的）；更根本的是用 OS 级隔离（容器、chroot、只读挂载、无网络命名空间、seccomp）。
- **(c) `run_tests` 接受任意 argv**：白名单只检查工具名，任何可执行文件和参数都能借 `run_tests` 的名义运行（Q7 的 C）。修复：让 `run_tests` 工具**不接受 argv**，由 harness 固定为 `[sys.executable, "-m", "unittest", "discover", "-s", "tests"]`，或增加 `ArgvGate`，要求 argv 与允许的命令模板逐项精确匹配。原则是**白名单优于黑名单**、能力最小化。

### Q12 — 参考答案

三处缺口：

1. **被拒绝的调用没有 span**：违反"每一步都有 span"，也让 `tools_called_total` 统计不到被拒绝的尝试——而被拒绝的尝试恰恰是安全团队最关心的。
2. **工具失败不体现在 span 状态上**：测试失败、文件不存在（exit 1）、路径越界（`DENIED_EXIT`）的 span 都是 `OK`；`exit_code` 用了无前缀的自定义 key。
3. **gate 决策没有记录**：第 28 课把 ALLOW/DENY 作为 `agent.harness.gate.decision` event 挂在工具 span 上，本节的精简版 `GenAISpan` 连 `events` 字段都删掉了。

修改要点：

```python
                with self.builder.span("gen_ai.tool.execution", parent=chat_span,
                                       attributes={"gen_ai.tool.name": tool,
                                                   "gen_ai.tool.call.id": f"call_{step_index:03d}"}) as tool_span:
                    outcome = self.chain.evaluate(call, ctx)          # gate 判定放进 span 内
                    tool_span.attributes["agent.harness.gate.decision"] = "ALLOW" if outcome.allow else "DENY"
                    if not outcome.allow:
                        tool_span.attributes["agent.harness.gate.reason"] = outcome.deny_reason
                        tool_span.status = "ERROR"                     # 或抛出自定义 GateDenied 异常让 builder 记录
                        ...记录 AgentStep 并设置 halted_reason...
                    else:
                        exit_code, text = dispatch(tool, argv, payload)
                        tool_span.attributes["agent.harness.exit_code"] = exit_code
```

由于 builder 在正常退出时会把状态覆盖为 OK，要么让 builder 只在 `status == UNSET` 时才设 OK，要么拒绝时抛一个自定义异常并在外层捕获。"测试失败是否算 ERROR"可以讨论：它是 agent 预期中的观察，不是 harness 故障，比较好的做法是 span 保持 OK、用 `agent.harness.exit_code` 与单独的 metric 区分；而 `DENIED_EXIT` 与超时应标为 ERROR。

### Q13 — 参考回答要点

- **部件**：agent 循环（policy/模型 ↔ harness）、工具注册与分派、gate chain（白名单、参数审查、预算、人工审批）、sandbox（隔离执行、超时、输出截断、路径限制）、观察 ledger 与预算、可观测性（trace + metric）、eval harness（固定任务 + verifier）。
- **为什么 gate 和 sandbox 都要**：
  - gate 在**执行前**按"意图"判断，能给出可读的拒绝理由并反馈给模型，但只能看到文本，正则/黑名单天然不完整（Q11）；
  - sandbox 在**执行时**按"效果"限制：即使 gate 漏判，进程也逃不出目录、跑不过超时、拿不到网络；
  - 两者是纵深防御（defense in depth），任何一层都不应被当作唯一边界。
- 本节的实测例子：`rm -r src` 被 gate 放行但被 sandbox denylist 拦下；`cat /etc/passwd` 被 gate 放行但被路径 jail 拦下。
- 加分点：讲义开头提到的"gate 说 ALLOW 但 sandbox 拒绝"正是这种分工的体现，harness 需要把两层的结论都写进 trace。

### Q14 — 参考回答要点

- **为什么用确定性 policy**：讲义："A real LLM requires an API key, a network call, and unverifiable stochasticity."——确定性 policy 能离线运行，测试可以断言精确步数，把注意力集中在 harness 上。
- **换成 LLM 后不变的**：工具契约、gate chain、sandbox、ledger、span/metric、验收断言。
- **需要变的**：
  - policy 需要把观察（测试输出、文件内容）组装进 prompt，并解析模型输出的 tool call（JSON schema 校验，见第 21、23 课）；
  - 评估改为统计意义：同一任务多次运行，报告成功率/pass@k、平均步数、token 与费用分布，而不是断言"恰好 5 步"；
  - 测试分层：harness 用确定性 policy 或录制回放（record/replay）做单测，LLM 端到端测试作为定期跑的 eval；
  - 预算更重要：模型可能循环调用工具，需要步数、token、时间、费用多重上限；
  - 安全边界更重要：模型可能被 prompt injection 诱导调用危险命令，gate/sandbox 的漏洞会被真正利用。
- 常见误区：以为 demo 通过就说明 agent 能力强——它只证明 harness 的管道是通的。

### Q15 — 参考回答要点

- **步数预算**：在 runner 循环里执行（本节 `step_budget`），注意边界判定（Q9）。
- **观察 token 预算**：
  - 调用前检查（`BudgetGate`，`used >= max` 则拒绝）：能阻止"再来一次"，但无法预测这次调用会产生多少输出；
  - 调用后检查（`AgentRun`，`> budget` 则停止）：能看到真实消耗，但已经超支（Q8 中一次从 17 跳到 498）；
  - 更好的做法：调用前检查剩余额度，**执行时按剩余额度截断/摘要输出**，调用后记账；预算只在一个地方定义，gate 和 runner 共享（本节两个参数分开设置是隐患）。
- **墙钟时间**：sandbox 对单次进程设超时（本节 10 秒），runner 再设总时长上限。
- **费用**：按 input/output token 与模型单价累计，写入 span（`gen_ai.usage.*`）和 metric，超限时停止并告警。
- 加分点：预算耗尽时要输出"部分结果 + 停止原因"，并在 trace 中可见，而不是静默失败。

### Q16 — 参考回答要点

- **任务输入**：issue 文本 + 仓库快照（commit SHA）+ 可复现的失败测试（没有就先让 agent 写一个复现测试）。
- **工具集**：`list_dir`、`read_file`（带行号、分页）、`search`（grep/符号检索）、`apply_patch`（基于 diff 而非整文件覆盖，减少误伤）、`run_tests`（固定命令模板，可指定测试子集）。
- **sandbox**：每个任务一个容器（只读基础镜像 + 可写工作目录），默认无网络、CPU/内存/时间配额；依赖安装在构建镜像阶段完成。
- **评估**：参考第 27 课的 fixture 任务格式，用"隐藏测试"（agent 看不到）验证，统计成功率、步数、费用；再加人工 review 抽检。
- **回滚**：工作在 git 分支上，每步变更可 `git diff` 审查；失败时丢弃分支；最终产物是 PR 而不是直接推主干（见第 16 课）。
- **观测**：全程 trace，PR 描述里附 trace 链接与测试结果。

### Q17 — 参考回答要点

- **风险**：reward hacking（奖励投机）——agent 可能修改或删除测试、把断言改成恒真、对特定输入硬编码返回值、跳过测试（`skip`），让"测试通过"失去意义。
- **本节能否阻止**：不能。`write_file` 只检查目录在仓库根下，`tests/test_fizz.py` 同样可写；gate chain 不看写入路径。一个"偷懒"的 policy 完全可以改测试来通过 VERIFY。
- **防护**：
  - 写权限最小化：`write_file` 只允许 `src/`，测试目录只读（gate 或 sandbox 挂载层面实现）；
  - 记录测试文件哈希，VERIFY 前校验未被修改；
  - 用 agent 看不到的隐藏测试/保留测试做最终判定（第 27 课 eval harness 的 `expected/` 思路）；
  - 审查 diff：检测对测试文件、断言、`skip` 的改动并告警；
  - 多维度评估：测试通过 + diff 最小化 + 人工抽检。
- 加分点：本节修复是硬编码的，所以"通过"更多证明 harness 管道通畅，而不是 agent 真会定位 bug。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：`GateChain`、`BudgetGate` 与 `ObservationLedger` 的原始版本。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：本节 `Sandbox` 的 denylist、路径 jail、超时与输出截断。
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../27-eval-harness-fixture-tasks/docs/zh.md)：fixture 任务与 `expected/` 目录的格式。
- [阶段 19 · 28 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../28-observability-otel-traces/docs/zh.md)：本节精简版 `SpanBuilder` 与 `prometheus_text` 的来源。
- [阶段 14 · 38 Verification Gates](../../../14-agent-engineering/38-verification-gates/docs/zh.md)、[阶段 14 · 41 在真实代码仓库中使用工作台](../../../14-agent-engineering/41-workbench-for-real-repos/docs/zh.md)、[阶段 14 · 42 交付可复用的 Agent 工作台包](../../../14-agent-engineering/42-agent-workbench-capstone/docs/zh.md)：讲义列出的 Agent 工程前置课。
- [阶段 19 · 20 Agent Harness 的循环契约](../../20-agent-harness-loop-contract/docs/zh.md)：`next_action / observe` 循环契约。

### 本节被哪些后续内容用到
- [阶段 19 · 01 终端原生 Coding Agent](../../01-terminal-native-coding-agent/docs/zh.md)：把确定性 policy 换成真实模型的完整 coding agent。
- [阶段 19 · 16 从 GitHub Issue 到 PR 的自主 Agent](../../16-github-issue-to-pr-agent/docs/zh.md)：在真实仓库上扩展本节流程。
- [阶段 19 · 21 带 Schema 校验的工具注册表](../../21-tool-registry-schema-validation/docs/zh.md)、[阶段 19 · 23 函数调用分派器](../../23-function-call-dispatcher/docs/zh.md)：用注册表与分派器替换本节的 `if tool == ...` 分支。
- [阶段 19 · 24 计划—执行控制流程](../../24-plan-execute-control-flow/docs/zh.md)：更复杂的 policy 结构。

### 延伸关键词
`agent harness` · `policy seam` · `state machine` · `defense in depth` · `allowlist vs denylist` · `path traversal / symlink escape` · `observation budget` · `reward hacking` · `hidden tests` · `pass@k` · `record/replay` · `SWE-bench`
