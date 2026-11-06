# 测验 · 角色专业化：规划者、Critic、执行者与验证者（Role Specialization — Planner, Critic, Executor, Verifier）

> **阶段 16 · 多智能体与集群 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 提示：本节中文讲义是机器翻译，质量较差（如把 canonical 译成"金刚石"、把 ordering 译成"订购"、把 ChatDev 译成"查塔德夫"，ChatDev 的 arXiv 号也被误写成 `2307.7924`，应为 `2307.07924`）。遇到读不通的句子请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四个经典角色 | Planner 产出结构化计划/spec；Executor 按步产出 artifact；Critic 对照意图做主观评审；Verifier 运行确定性检查给出 pass/fail + 证据 |
| 2 | "不同"而不是"更多" | 讲义："The fix is not more agents — it is *different* agents"。三个同质 coder 只会写出三种口味的平庸代码 |
| 3 | Critic ≠ Verifier | Critic 主观、常由 LLM 担任，会被"看起来合理"的内容骗过；Verifier 客观、由代码决定，只能在运行时暴露的 bug 归它抓 |
| 4 | MetaGPT 的 SOP 模式 | `Code = SOP(Team)`：产品经理 → 架构师 → 项目经理 → 工程师 → QA，每个角色有严格的输入/输出 schema，把团队变成可预测的流水线 |
| 5 | ChatDev 的 communicative dehallucination | 执行者缺细节时**先按名字去问**上游角色，而不是自己编一个看似合理的细节 |
| 6 | Verifier 是承重角色 | 讲义引用 MAST：1642 条多 agent 执行失败中 21.3% 是 verification gap；PwC 在 CrewAI 部署中加入结构化验证循环，准确率 10% → 70%（7×） |
| 7 | All-LLM 反模式 | 每个角色都是 LLM、每个输出都是"looks good to me"——至少要有一个由代码决定 pass/fail 的 verifier |
| 8 | 顺序与预算 | 先跑便宜的 critic（抓设计问题），再跑慢的 verifier（抓 bug）；critic–executor 修订最多 2 轮，之后升级给人 |
| 9 | Verifier 的上限 = 测试的质量 | 本节代码的 verifier 只跑 3 个用例；测试太弱或被执行者"看见"，错误代码同样能通过 |
| 10 | 框架映射 | CrewAI `Agent(role, goal, backstory)`；LangGraph 节点 + 边；AutoGen GroupChat 中的单词名角色；OpenAI Agents SDK 的 handoff |

### 核心技能（能动手做到）

- [ ] 为任意任务写出 3–5 个角色的花名册，并用 dataclass 风格写出每个角色的输入/输出 schema
- [ ] 区分一个检查属于 critic（主观）还是 verifier（确定性），并说出各自能/不能抓到的错误
- [ ] 读懂本节 `critic` 的字符串匹配逻辑，构造出它的**漏报**（错误代码被批准）和**误报**（正确代码被拒）
- [ ] 给本节流水线加上"critic → verifier → 带反馈修订，最多 2 轮，超限升级给人"的循环
- [ ] 说清 `exec` 为什么不是 sandbox，并改用子进程 + 超时实现 verifier
- [ ] 判断一个任务是否存在可行的确定性 verifier，没有时给出替代方案（人工评审、辩论、抽检）

---

## 二、基础自测（选择题）

**Q1.** 关于 critic 与 verifier 的区别，下列说法**正确**的是：

- A. critic 主观、常由 LLM 担任，可能被看似合理的内容骗过；verifier 运行确定性检查（测试、类型检查、schema 校验），给出带证据的 pass/fail
- B. 两者是同一个角色的两种叫法，只保留一个即可
- C. verifier 主要判断代码风格和可读性，critic 负责运行测试
- D. 有了 verifier 就不需要 critic，因为 verifier 能发现所有问题

**Q2.** MetaGPT 用 `Code = SOP(Team)` 概括其做法。下列哪一项最准确地描述了它的核心思想？

- A. 让同一个 LLM 扮演所有角色，靠多轮自我反思提升质量
- B. 把所有 agent 放进一个群聊，自由发言直到达成共识
- C. 用投票从多个独立生成的程序中选出最好的一个
- D. 把软件工程的标准作业流程（SOP）编码进角色 prompt，每个角色（产品经理、架构师、项目经理、工程师、QA）有严格的输入/输出 schema，使团队成为可预测的流水线

**Q3.** ChatDev 提出的 communicative dehallucination 指的是：

- A. 用一个专门的 critic 检测并删除输出中的幻觉
- B. 执行者在需要计划中没有给出的具体细节时，先按名字向相关角色提问，再继续产出，而不是自己编造
- C. 降低采样温度，让模型输出更确定
- D. 在多个 agent 之间投票，少数派的说法视为幻觉

**Q4.** 讲义引用 Cemri 等人的 MAST 研究来说明"verifier 最重要"。讲义给出的数字是：

- A. 1642 条失败中 79% 属于 verification gap
- B. 所有失败中 7% 属于 verification gap
- C. 1642 条多 agent 执行失败中 21.3% 是 verification gap（系统交付了一个没人检查过的答案）
- D. 1642 条失败中 50% 来自 planner 的规划错误

**Q5.** 运行 `code/main.py`，第二个场景（executor 写出 `return a * b`）的实际结果是：

- A. critic 拒绝（`approved=False`），verifier 通过，结果为 "critic blocked ship"
- B. critic 和 verifier 都通过，结果为 "ship it."
- C. critic 拒绝，verifier 也失败，结果为 "critic blocked ship"
- D. critic 批准（`approved=True, notes=[]`），verifier 3 个用例全部失败，结果为 "verifier blocked ship (deterministic catch)."

**Q6.** 如果 executor 返回 `"add_two = lambda a, b: a + b\n"`（功能完全正确），本节代码会怎样？

- A. critic 报告 `missing def statement` 和 `missing return` 并拒绝，verifier 却通过，最终打印 "critic blocked ship (subjective catch)."——这是一次误报
- B. critic 与 verifier 都通过，打印 "ship it."
- C. verifier 找不到可调用对象而失败
- D. `exec` 抛出语法错误

**Q7.** 下面哪一组测试用例**无法**区分正确实现 `a + b` 和错误实现 `a * b`（即 `a * b` 也能全部通过）？

- A. `((1, 2), 3)`、`((0, 0), 0)`
- B. `((10, 20), 30)`
- C. `((2, 2), 4)`、`((0, 0), 0)`
- D. `((-5, 5), 0)`

**Q8.** 讲义 Ship It 清单对 critic 和 verifier 的顺序以及修订循环的建议是：

- A. 先跑 verifier，再跑 critic；修订循环不设上限，直到通过为止
- B. 先跑 critic（便宜，抓设计问题），再跑 verifier（慢，抓 bug）；critic–executor 修订最多 2 轮，之后升级给人
- C. 两者并行跑，以多数票决定是否交付
- D. 只在 critic 拒绝时才跑 verifier

---

## 三、动手 / 代码题

**Q9.** 本节的 critic 是"LLM 模拟"，实际是三条字符串匹配：

```python
def critic(spec: Spec, art: Artifact) -> CriticReport:
    notes: list[str] = []
    if "def" not in art.code:
        notes.append("missing def statement")
    if "return" not in art.code:
        notes.append("missing return")
    if spec.task_name not in art.code:
        notes.append(f"function name does not match spec '{spec.task_name}'")
    approved = not notes
    return CriticReport(approved=approved, notes=notes)
```

1. 构造三段 executor 输出，使 critic **批准**但代码其实有问题（分别对应：语义错误、语法错误、函数名只出现在注释里）。
2. 构造一段功能正确但被 critic **拒绝**的代码。
3. 有一段代码能让 critic 和 verifier **都通过**，但它显然不是"两数之和"。写出它，并说明这暴露了本节设计的什么问题。

**Q10.** 讲义说 verifier "runs the generated code in a sandbox (`exec`)"：

```python
    ns: dict = {}
    try:
        exec(art.code, ns, ns)
    except Exception as e:
        return VerifierReport(passed=False, failures=[f"exec error: {e}"])
```

1. 这里的 `exec` 真的是 sandbox 吗？请举出两类它防不住的问题。
2. 如果 executor 输出 `def add_two(a, b):\n    while True: pass`，会发生什么？
3. 给出一个更稳妥的 verifier 思路（可以写伪代码或关键代码）。

**Q11.** 讲义 Ship It 要求"critic 先、verifier 后"以及"最多 2 轮修订后升级给人"，但 `run_pipeline` 只是顺序执行一次、两份报告都跑完就结束。请写一个 `run_with_revisions(user_wish, executor, max_rounds=2)`：

- executor 签名改为 `executor(spec, feedback)`，能收到上一轮的反馈；
- critic 不通过时不跑 verifier，直接把 notes 作为反馈；
- verifier 失败时把 failures 作为反馈；
- 超过预算返回 `"escalate_to_human"`。

并说明：对"第一次写错、收到反馈后改对"的 executor 和"永远写错"的 executor，各自的返回值是什么。

**Q12.** 讲义练习 1：给 verifier 增加一个静态分析检查——统计 `return` 出现次数，要求恰好为 1。

1. 它能抓住 `return a * b` 吗？
2. 它能抓住什么**运行时测试抓不住**的问题？请给出一个具体例子。
3. 它会产生什么误报？由此说明静态检查适合做 verifier 还是 critic 的辅助信号。

---

## 四、面试高频题

**Q13.**（基础必考）多 agent 系统中常见的 planner / executor / critic / verifier 四个角色分别做什么？critic 和 verifier 为什么不能合并？

**Q14.**（原理深挖）为什么说 verifier 是"承重"角色？只要加了 verifier 就万事大吉吗？请谈谈 verifier 自身的失效方式。

**Q15.**（工程实践）请为一个"自然语言 → SQL 查询"的多 agent 系统设计角色花名册：每个角色的输入/输出 schema、verifier 的确定性检查、communicative dehallucination 的提问规则、修订预算。

**Q16.**（场景设计）讲义练习 5：PwC 的 7× 提升来自验证循环。举出三类"加 verifier 帮不上忙"的任务，并说明这时该怎么办。

**Q17.**（追问型）面试官问："你们的代码 agent 质量不够，我再加 3 个 coder agent 在群聊里讨论可以吗？"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Critic is subjective, opinionated, often LLM-based. Verifier is objective, deterministic, often code-based. They are not the same role." B 错在把两者当成同一角色；C 把职责说反了；D 错，讲义明确说"Use both"：critic 能抓 verifier 难以形式化的"品味/设计"问题（如命名、可维护性、是否偏离意图），verifier 抓只在运行时才出现的 bug。

### Q2 — 答案：D

讲义："MetaGPT encodes software engineering SOPs as role prompts ... Each role has a strict input/output schema ... deterministic SOPs turn a team of LLMs into a predictable pipeline." A 是 Self-Refine/Reflexion 一类单 agent 方法；B 是群聊（第 10 节）；C 是投票/自洽性（第 15 节）。

### Q3 — 答案：B

讲义："when an executor needs a specific detail that was not in the plan, it explicitly asks the designer before continuing. This prevents the classic LLM failure of plausibly inventing the detail." 实现方式是在角色 prompt 中写明"缺信息时先按名字问相关角色"。A 是事后检测，C 只影响随机性、不解决信息缺失，D 是投票机制。

### Q4 — 答案：C

讲义："Cemri et al. (MAST) traced 1642 multi-agent execution failures. 21.3% were verification gaps"。A 混淆了讲义另一句"其余 79% 也常常追溯到某个检查静默失败或从未运行"；B、D 是编造的数字。注意讲义开头说 "every multi-agent failure can be traced to missing or broken verification"，比正文的 21.3% 说得更绝对——正文的表述更严谨：21.3% 是直接的 verification gap，其余失败中**很多**与检查缺失有关，而不是全部。

### Q5 — 答案：D

实际运行输出：

```text
  [critic] approved=True, notes=[]
  [verifier] passed=False, failures=['call (1, 2): expected 3, got 2', 'call (10, 20): expected 30, got 200', 'call (-5, 5): expected 0, got -25']
  RESULT: verifier blocked ship (deterministic catch).
```

`return a * b` 里有 `def`、有 `return`、有 `add_two`，三条字符串规则全部满足，critic 批准；verifier 实际调用函数，`1*2=2≠3`、`10*20=200≠30`、`-5*5=-25≠0`，三个用例全挂。这正是本节的核心演示：**看起来对 ≠ 运行起来对**。

### Q6 — 答案：A

已实际运行验证：critic 返回 `approved=False, notes=['missing def statement', 'missing return']`，verifier 返回 `passed=True`。`run_pipeline` 的分支顺序是"都通过 → ship；verifier 失败 → verifier blocked；否则 critic 拒绝 → critic blocked"，于是打印 "critic blocked ship (subjective catch)."。这是 critic 的**误报**：它检查的是"形式"（有没有 def/return 关键字），而不是"语义"。真实 LLM critic 不会这么死板，但同样会在风格偏好上拒绝正确代码——所以 critic 的拒绝应当是"可申诉的反馈"，不应像 verifier 那样一票否决。B 错在忽略了 critic；C 错，`lambda` 赋值给 `add_two` 后它就是可调用对象；D 错，这是合法 Python。

### Q7 — 答案：C

`2+2 = 2×2 = 4`、`0+0 = 0×0 = 0`，所以 `a * b` 能通过 C 中全部用例（已用代码验证 `passed=True`）。A 中 `(1,2)` 能区分（3 vs 2）；B `10×20=200`；D `-5×5=-25`。这道题说明：**verifier 的强度取决于测试集**。测试要覆盖能区分"常见错误实现"的输入（边界值、负数、不对称输入），否则 verifier 只是在给错误代码盖章。

### Q8 — 答案：B

讲义 Ship It："Run critic first (cheap, catches design issues), verifier second (slow, catches bugs)" 以及 "Max 2 critic-executor revision rounds before escalating to human." A 顺序相反且无预算——无预算的修订循环可能永远不收敛并烧光 token；C 把确定性检查降格成"一票"，失去 verifier 的意义；D 会让 critic 批准的错误代码（如 Q5）直接交付。注意：本节代码**两者总是都跑**、没有修订循环，与清单不一致（见 Q11）。

### Q9 — 参考答案

1. critic 批准但有问题的三个例子（均已运行验证 critic `approved=True`）：
   - 语义错误：`def add_two(a, b):\n    return a - b\n`（verifier 三个用例都失败）；或 `return abs(a) + b`（只有 `(-5, 5)` 用例失败，得到 10）。
   - 语法错误：`def add_two(a, b)\n    return a + b\n`（缺冒号）。critic 只做子串匹配，看不出语法错误；verifier 报 `exec error: expected ':' (<string>, line 1)`。
   - 名字只在注释里：`# add_two\ndef f(a, b):\n    return a + b\n`。`spec.task_name not in art.code` 是**子串**判断，注释里出现就算"匹配"；verifier 报 `no callable 'add_two' produced`。
2. 被拒的正确代码：`add_two = lambda a, b: a + b`（见 Q6），或者用 `functools.partial`、`operator.add` 赋值实现的版本。
3. 两者都通过的"作弊"代码（已验证）：

   ```python
   def add_two(a, b):
       return {(1, 2): 3, (10, 20): 30, (-5, 5): 0}[(a, b)]
   ```

   它只是把测试用例**背了下来**。暴露的问题有两个：
   - **测试泄露给执行者**：`planner` 把 `tests` 放进 `Spec`，而 `executor(spec)` 能读到整个 `Spec`。真实 LLM executor 看到测试后可能"面向测试编程"。生产中应保留一部分**隐藏测试**（hold-out），只给 verifier 用。
   - **测试太少**：3 个固定用例，可以加入随机/属性测试（property-based testing），例如随机生成 1000 对整数检查 `add_two(a, b) == a + b`、交换律 `add_two(a, b) == add_two(b, a)`。

### Q10 — 参考答案

1. **不是 sandbox**。`exec(art.code, ns, ns)` 只是给了一个空的全局命名空间，Python 会自动往里放入 `__builtins__`，生成的代码依然可以 `import os`、读写文件、发网络请求、`os.system(...)`，还能修改解释器状态。讲义把它称为 sandbox 是一种简化说法。两类防不住的问题：①**副作用/越权**（删文件、读环境变量里的 API key、外连网络）；②**资源耗尽**（死循环、超大内存分配、fork 炸弹）。
2. `exec` 只是定义函数，不会卡住；但随后 `fn(*args)` 调用时进入死循环，`verifier` 永远不返回，整个流水线挂死——代码里没有任何超时机制。`except Exception` 也捕获不到"永远不结束"。
3. 更稳妥的思路：把"代码 + 测试驱动脚本"放到**独立子进程**中运行，设置超时，只通过 stdout 回传结构化结果。关键代码（已在本地验证：死循环在 2 秒后返回 `timeout after 2s`，`a * b` 返回 3 条失败，`a + b` 通过）：

   ```python
   import json, subprocess, sys

   def verifier_subprocess(spec, art, timeout=2):
       harness = art.code + (
           "\nimport json\nres=[]\n"
           f"for args, exp in {spec.tests!r}:\n"
           "    try:\n"
           f"        got = {spec.task_name}(*args)\n"
           "        res.append([list(args), exp, repr(got), got == exp])\n"
           "    except Exception as e:\n"
           "        res.append([list(args), exp, 'raised ' + repr(e), False])\n"
           "print(json.dumps(res))\n"
       )
       try:
           p = subprocess.run([sys.executable, "-I", "-c", harness],
                              capture_output=True, text=True, timeout=timeout)
       except subprocess.TimeoutExpired:
           return VerifierReport(False, [f"timeout after {timeout}s"])
       if p.returncode != 0:
           return VerifierReport(False, [p.stderr.strip().splitlines()[-1]])
       res = json.loads(p.stdout)
       fails = [f"call {tuple(a)}: expected {e}, got {g}" for a, e, g, ok in res if not ok]
       return VerifierReport(not fails, fails)
   ```

   子进程只解决了"超时"和"崩溃隔离"，**仍不能阻止恶意代码访问文件和网络**。生产中还要叠加容器/gVisor/Firecracker 等隔离、只读文件系统、禁网、CPU/内存配额（参见阶段 13 · 26 Skill 权限与 Sandboxes）。

### Q11 — 参考答案

```python
def run_with_revisions(user_wish, executor, max_rounds=2):
    spec = planner(user_wish)
    feedback: list[str] = []
    for attempt in range(max_rounds + 1):        # 1 次初稿 + 最多 2 次修订
        art = executor(spec, feedback)
        crep = critic(spec, art)
        if not crep.approved:                     # 便宜的 critic 先跑，不通过就不必跑 verifier
            feedback = crep.notes
            continue
        vrep = verifier(spec, art)
        if vrep.passed:
            return "ship", attempt, art
        feedback = vrep.failures                  # 把具体失败用例作为反馈
    return "escalate_to_human", attempt, art
```

实际运行：

- "第一次写 `a * b`、收到反馈后改成 `a + b`"的 executor → `('ship', 1)`：第 0 轮被 verifier 拦下，第 1 轮通过。
- "永远写 `a * b`"的 executor → `('escalate_to_human', 2)`：共尝试 3 次（初稿 + 2 次修订）后升级。

要点：①反馈要**具体**（失败用例的输入、期望、实际值），否则 executor 无从修改；②预算是硬上限，防止无限循环和成本失控（参见阶段 15 · 13 成本控制）；③critic 的 notes 与 verifier 的 failures 可以合并成一条结构化反馈；④升级给人时要附上全部轮次的 artifact 和报告，方便人工判断。

### Q12 — 参考答案

1. **抓不住**。`def add_two(a, b):\n    return a * b\n` 只有 1 个 `return`，静态检查通过（已运行验证：`(True, 1)`）。语义错误需要运行时测试。
2. 它能抓住**测试没覆盖到的分支**。例如：

   ```python
   def add_two(a, b):
       if a > 100:
           return 0
       return a + b
   ```

   三个测试用例的 `a` 都不超过 100，运行时 verifier `passed=True`；但 `return` 计数为 2，静态检查会把它标出来。更一般地说，静态分析检查的是"代码的所有路径"，运行时测试只检查"被执行到的路径"。
3. 误报：合法的多分支实现（如提前返回的 guard clause）会被拒；`lambda` 版本 `return` 计数为 0 也会被拒（已验证 `(False, 0)`，而 verifier 通过）。结论："`return` 恰好 1 个"不是正确性的必要条件，它更像一条**风格/可疑信号**，适合交给 critic 作为证据，或作为"需要人工看一眼"的 warning，而不应作为一票否决的 verifier。真正适合做 verifier 的静态检查是有明确正确性语义的：类型检查（mypy）、schema 校验、linter 中的错误级规则。

### Q13 — 参考回答要点

- **Planner**：读目标，输出结构化计划/spec（步骤列表、函数签名、验收标准）；工具是检索、文档。
- **Executor**：一次读一个计划步骤，产出 artifact（代码、查询、文档）；工具是真正干活的工具（编译器、shell、API 客户端）。
- **Critic**：对照 planner 的意图审阅 artifact，输出接受/拒绝 + 理由；工具是只读访问、静态分析。
- **Verifier**：对 artifact 运行确定性检查，输出 pass/fail + 证据；工具是测试运行器、类型检查器、schema 校验器。
- **为什么不能合并**：两者抓的错误类型不同。critic 能评价"是否符合意图、设计是否合理"，但会被貌似合理的内容骗过（本节 `a * b` 就骗过了 critic）；verifier 不会被骗，但只能检查能被形式化的性质，且受限于测试质量。合并成一个 LLM 角色会退化为 all-LLM 反模式。
- 加分点：给出 MetaGPT 的五角色对应关系（PM/架构师 ≈ planner，工程师 ≈ executor，QA ≈ verifier）；提到 critic 的拒绝是"建议"，verifier 的失败是"硬门槛"。

### Q14 — 参考回答要点

- **为什么承重**：讲义引用 MAST，21.3% 的失败是"交付了没人检查过的答案"，很多其他失败也是"检查静默失败或从未运行"；PwC 在 CrewAI 中加入结构化验证循环，准确率 10% → 70%。没有 verifier，前面的角色再多也只是"并行猜测"。
- **verifier 自身的失效方式**：
  - 测试太弱：本节 3 个用例，若换成 `(2,2)→4, (0,0)→0`，`a * b` 也能通过（Q7）；
  - 测试泄露/被过拟合：executor 能看到测试就可能硬编码答案（Q9-3）；
  - 检查静默失败：异常被吞、超时被当成通过、verifier 本身没被调用；
  - 环境不一致：verifier 的运行环境与生产不同；
  - 检查的是"代理指标"：通过 schema 校验 ≠ 内容正确（Goodhart 定律）。
- **对策**：隐藏测试 + 属性测试 + 变异测试（故意注入 `a * b` 之类的变异，检查测试集能否杀死它）；verifier 结果必须带证据并记录日志；把"verifier 是否运行"本身纳入监控。
- 常见误区：认为"LLM-as-judge 打分"就是 verifier——它仍然是 critic。

### Q15 — 参考回答要点

- **角色与 schema**（示例）：
  - `Planner(question: str, schema: DBSchema) -> QueryPlan{tables, joins, filters, aggregations, expected_columns}`
  - `Executor(plan: QueryPlan) -> SQLArtifact{sql: str, dialect: str}`
  - `Critic(plan, sql) -> CriticReport{approved, notes}`：检查是否偏离意图、是否有 `SELECT *`、是否缺少 LIMIT、JOIN 条件是否合理
  - `Verifier(sql, plan) -> VerifierReport{passed, evidence}`：确定性检查
- **Verifier 检查**：SQL 解析通过（如 sqlglot 解析）；`EXPLAIN` 成功且无全表扫描超阈值；在**只读副本/沙箱库**上执行，结果列与 `expected_columns` 一致；对有标准答案的评测集比对结果集；禁止 DDL/DML（只允许 SELECT）。
- **communicative dehallucination**：executor 遇到字段名歧义（"收入"是 `revenue` 还是 `gross_amount`）、时间范围不明（"上个月"按哪个时区）时，必须向 planner 发问，planner 再无法确定时向用户澄清——绝不能猜一个列名。
- **预算**：critic–executor 最多 2 轮，verifier 失败最多 2 轮，之后把问题、候选 SQL 和报告交给人。
- 加分点：critic 用便宜模型先过滤，verifier 在执行层面加超时和行数上限；所有轮次记录 trace 以便评估。

### Q16 — 参考回答要点

- **三类 verifier 帮不上忙的任务**：
  1. **纯生成/创意类**：写诗、广告文案、小说——"好不好"没有确定性标准；
  2. **正确性需要真实世界反馈或很长时间才能验证**：投资建议、医疗/法律意见、长期战略规划——验证成本极高或要等结果发生；
  3. **验证与求解同样难或更难**：开放式研究结论、复杂的数学证明草稿（若没有形式化证明器）、需要专家判断的设计评审。
  另外还有"规格本身模糊"的任务：连验收标准都写不出来，自然无法写 verifier。
- **替代方案**：人工评审循环（human-in-the-loop）；多 agent 辩论或异构模型交叉检查（第 07 节）；把任务拆出**可验证的子部分**（文案中的事实、链接、格式、字数可以确定性检查）；用评测集 + LLM-as-judge 做统计意义上的质量监控而非逐条把关。
- 讲义配套的 `skill-role-designer` 也写明：任务没有确定性正确性检查时应拒绝套用该模式，改推荐人工评审或辩论。

### Q17 — 参考回答要点

- 先引讲义："Generic multi-agent systems produce generic output. Three coders in a group chat write three flavors of the same mediocre code." 同质 agent 的错误高度相关，加数量只增加成本，不跨越质量门槛。
- 正确方向是**差异化**：给 critic 不同的工具（静态分析、只读访问），给 verifier 客观的测试套件，让系统内部出现"有依据的纠正"，而不是并行猜测。
- 具体建议：先加一个确定性 verifier（测试、类型检查），再考虑 critic；明确每个角色的 I/O schema；设置修订预算。
- 还要权衡成本与延迟：每加一个 LLM 角色就多一次（或多轮）调用；任务小于 10 分钟人工量时单 agent + 测试往往更好（`skill-role-designer` 的拒绝规则）。
- 加分点：提出用数据说话——在评测集上比较"单 agent + verifier"与"多 coder 群聊"的通过率和 token 成本。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：角色就是"带不同 prompt 和工具的 agent 原语"。
- [阶段 16 · 05 监督者与编排者—工作者模式](../../05-supervisor-orchestrator-pattern/docs/zh.md)：本节的流水线是一种固定顺序的编排。
- [阶段 16 · 07 心智社会与多 Agent 辩论](../../07-society-of-mind-debate/docs/zh.md)：没有确定性 verifier 时的替代方案。
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../../14-agent-engineering/05-self-refine-and-critic/docs/zh.md)：单 agent 的 critic/修订循环。
- [阶段 14 · 02 ReWOO 与 Plan-and-Execute：解耦 Planning](../../../14-agent-engineering/02-rewoo-plan-and-execute/docs/zh.md)：planner 与 executor 的分离。

### 本节被哪些后续内容用到
- [阶段 16 · 10 群聊与发言者选择](../../10-group-chat-speaker-selection/docs/zh.md)：把专业化角色放进群聊，由选择器决定谁发言。
- [阶段 16 · 11 Handoffs 与例程：无状态 Orchestration](../../11-handoffs-and-routines/docs/zh.md)：角色专业化 agent 之间用 handoff 移交控制权。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：MAST 分类与 verification gap 的完整讨论。
- [阶段 14 · 15 基于角色的 Agent 团队：角色、任务与流程](../../../14-agent-engineering/15-crewai-role-based-crews/docs/zh.md)：CrewAI 的 `Agent(role, goal, backstory)`。
- [阶段 14 · 38 Verification Gates](../../../14-agent-engineering/38-verification-gates/docs/zh.md)、[阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../../14-agent-engineering/39-reviewer-agent/docs/zh.md)：verifier 与 critic 在工程中的落地。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../../13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/docs/zh.md)：真正安全地执行生成代码。

### 延伸关键词
`MetaGPT` · `Code = SOP(Team)` · `ChatDev chat chain` · `communicative dehallucination` · `MAST` · `verification gap` · `LLM-as-judge` · `property-based testing` · `mutation testing` · `hidden test set` · `revision budget` · `human escalation` · `CrewAI role/goal/backstory`
