# 测验 · Verification Gates 与观察预算（Verification Gates and the Observation Budget）

> **阶段 19 · 综合项目 · 第 25 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三类失控 | 观察无上限（一次 grep 灌进几十万 token）、陈旧观察（把早期读到的内容当成当前状态）、权限蔓延（模型"发明"工具名、harness 默认放行） |
| 2 | Verification gate 的本质 | 不是模型、不是裁判，而是 `(call, history, ledger)` 的**确定性函数**，返回 ALLOW 或 DENY + 理由；理由可记录、可回放、可审计 |
| 3 | Gate 协议 | 任何有 `name` 和 `evaluate(call, ctx) -> GateDecision` 的对象都是 gate（`typing.Protocol` 结构化类型，无需继承） |
| 4 | 链式短路 | `GateChain` 按顺序评估，遇到第一个 DENY 立即返回；`ChainOutcome.decisions` 只包含实际被评估的 gate |
| 5 | 排序原则 | 按成本升序（哈希查找 → 正则 → 读最近记录 → 汇总账本）且按"爆炸半径"降序（工具不在契约 → 参数不在契约 → 新鲜度 → 预算） |
| 6 | 四个 gate | `WhitelistGate`（工具名白名单）、`RegexGate`（参数拒绝模式）、`RecencyGate`（与上次观察的回合差 ≤ window）、`BudgetGate`（累计观察 token < 上限） |
| 7 | 观察账本 | `ObservationLedger` 只记录**成功**的观察：`(turn, tool, tokens)`；回答 `cumulative()` 与 `per_tool(name)` 两个问题 |
| 8 | 预算是"事前"检查 | 调用前无法知道结果有多大，`BudgetGate` 只看调用前的账本，因此最后一次放行的调用可以把总量推到上限之上（demo 中 322/200） |
| 9 | Token 估算 | `estimate_tokens = max(1, len(text)//4)`，空串为 0；只是占位，讲义："Drop in a real tokenizer in production" |
| 10 | 结构化决策记录 | `GateDecision(allow, gate, reason)` 与 `ChainOutcome.to_dict()` 供可观测性（第 28 课）与评估（第 27 课的拒绝计数）使用 |

### 核心技能（能动手做到）

- [ ] 手算 demo 中每次调用的 token 数、累计值和每个 gate 的判定
- [ ] 解释为什么 gate 链要"便宜的先跑、预算最后跑"，并说出短路对审计记录的影响
- [ ] 找出 `RegexGate` 默认模式的绕过方式（`rm -fr`、`-r -f`、`^/etc/` 锚点问题），并写出更稳健的基于 argv 结构的检查
- [ ] 识别 `RecencyGate` 在空闲超过 window 后"永久拒绝"的死锁问题，并改写为"编辑前必须新鲜读取"类 gate
- [ ] 为观察预算增加"事后截断"（clamp 到剩余预算），让累计值不超过上限
- [ ] 写出针对单个 gate、链短路、端到端循环的单元测试，并给出精确断言

---

## 二、基础自测（选择题）

**Q1.** 运行本节 demo（预算 200，5 次调用）。被 `BudgetGate` 拒绝的是哪一次，拒绝理由中的数字是多少？

- A. 第 3 回合 `read_file README.md`，`165/200`
- B. 第 2 回合 `read_file main.py`，`9/200`
- C. 第 4 回合 `run_tests`，`322/200`
- D. 第 5 回合 `shell`，`336/200`

**Q2.** 讲义把四个 gate 排成 Whitelist → Regex → Recency → Budget。下列哪一项**最完整地**说明了这个顺序？

- A. 按评估成本升序（短路时省掉昂贵的账本汇总），同时按"爆炸半径"降序（越根本的违约越先判）；Budget 放最后，因为它只在其他都通过时才有意义
- B. 按字母顺序排列，便于维护
- C. Budget 最贵，放最后是为了让它永远不被执行
- D. 顺序无关紧要，因为所有 gate 都会被评估，结果取逻辑与

**Q3.** `RecencyGate(window=3)`，账本中最后一条观察在第 1 回合。之后模型在第 6、7、8 回合各发起一次调用（工具都在白名单内、预算充足）。结果是：

- A. 第 6 回合被拒绝，第 7、8 回合因为"已经提醒过"而放行
- B. 三次都放行，因为第一次调用总是通过
- C. 只有第 8 回合被拒绝
- D. 三次都被拒绝，而且之后永远会被拒绝——被拒绝的调用不写账本，`latest_turn()` 永远停在 1

**Q4.** 默认链中的 `RegexGate` 有模式 `^/etc/`。下面哪个调用会被**放行**？

- A. `ToolCall(turn=1, tool="read_file", argv=("/etc/passwd",))`
- B. `ToolCall(turn=1, tool="read_file", argv=("cat", "/etc/shadow"))`
- C. `ToolCall(turn=1, tool="read_file", argv=("sudo-rs",))`
- D. `ToolCall(turn=1, tool="read_file", argv=("rm", "-rf", "/"))`

**Q5.** 账本已记录一条 60 token 的 `read_file` 观察，下一次调用被链拒绝。关于账本，正确的是：

- A. 账本不变：它只记录成功执行的观察；拒绝只体现在 `ChainOutcome` 和 `refused` 计数中
- B. 账本追加一条 `tokens=0` 的拒绝记录
- C. 账本追加一条 tokens 等于拒绝理由长度 // 4 的记录，因为拒绝理由也会给模型看
- D. 账本被清空，下一回合重新计数

**Q6.** 你想加一条规则："单次观察不得超过 8000 token"。最合理的落点是：

- A. 作为第一个 gate，因为它最便宜
- B. 放进 `WhitelistGate`，按工具名限制
- C. 放进 `RecencyGate`，因为它也读账本
- D. 它不能是"调用前"的 gate（结果大小只有运行后才知道），应在 dispatch 之后、写入账本之前做截断或拒收

**Q7.** `estimate_tokens` 对 `"abc"`、`"abcdefgh"`、`"你好世界你好世界"`（8 个汉字）分别返回：

- A. `0`、`2`、`8`
- B. `1`、`2`、`6`（按 UTF-8 字节数 24 再除以 4）
- C. `1`、`2`、`2`
- D. `0`、`2`、`2`

**Q8.** 链放行了 `ghost` 工具，但 `tool_fns` 里没有 `ghost` 的实现。`run_synthetic_loop` 的结果是：

- A. 抛出 `KeyError`
- B. `refused` 加 1，但对应的 `ChainOutcome.allow` 仍为 `True`，审计记录与计数不一致
- C. `allowed` 加 1，账本记录一条空观察
- D. 链会被重新评估一次，第二次返回 DENY

---

## 三、动手 / 代码题

**Q9.** 预算超支。demo 中每个工具输出的长度分别为：`list_dir` 37 字符、`read_file main.py` 627 字符、`read_file README.md` 629 字符、`run_tests` 59 字符。

1. 手算每次放行前 `BudgetGate` 的理由（"N tokens of budget remaining"）和每次观察的 tokens，解释为什么最终累计值是 322 而不是 ≤ 200。
2. `BudgetGate` 的 docstring 说 "the harness re-runs the cumulative check against the new ledger state after recording the observation"，`run_synthetic_loop` 做了吗？
3. 写出一种"事后截断"：观察超过剩余预算时，把文本截短并附上截断说明，使累计值不超过上限。给出改造后 demo 的每次 tokens 与最终累计值。

**Q10.** 默认 `RegexGate` 的模式是 `r"\brm\s+-rf\b"`、`r"\bsudo\b"`、`r"^/etc/"`，匹配对象是 `" ".join(argv) + " " + payload`。

1. 找出至少 4 种能绕过它的危险调用，并说明原因（提示：参数顺序、大小写、`^` 锚点、payload 前面的空格）。
2. 写一个基于 argv 结构（而不是拼接字符串）的 gate，至少挡住你列出的绕过，同时放行 `rm a.txt`、`ls -la`、`pseudocode`。

**Q11.** `RecencyGate` 的 docstring 说 "The intent is to force a fresh read instead of relying on stale state"，但 Q3 显示它会在空闲后永久拒绝所有调用（包括"新鲜读取"本身）。

1. 解释为什么它的判定条件 `call.turn - ledger.latest_turn() > window` 达不到"强制新鲜读取"的目的。
2. 写一个 `FreshReadGate(window)`：`read_file` 一律放行；`edit_file path` 要求在 `window` 回合内读过同一个 `path`，否则拒绝并提示"先重新读取"。给出调用序列 `read a.py@1, edit a.py@2, edit a.py@8, read a.py@9, edit a.py@10, edit b.py@11` 的判定结果。

**Q12.** 测试 `test_loop_trips_budget_on_third_read` 的断言只有 `refused >= 1` 和 `allowed >= 1`：

```python
chain = build_default_chain(budget=80)
calls = [ToolCall(1, "list_dir", ()), ToolCall(2, "read_file", ("a",)), ToolCall(3, "read_file", ("b",))]
tool_fns = {"list_dir": lambda c: "tiny", "read_file": lambda c: "x" * 400, "run_tests": lambda c: "ok"}
```

1. 手算 `allowed`、`refused`、每条观察的 tokens 以及第三次调用的拒绝理由。
2. 把断言改成精确断言。
3. 如果预算改成 102，结果如何变化？为什么说这个测试名字里的 "third read" 并不准确？

---

## 四、面试高频题

**Q13.**（基础必考）为什么 agent harness 需要确定性的 verification gate，而不是让另一个 LLM 当裁判来决定工具调用是否放行？

**Q14.**（原理深挖）gate 链的顺序有什么讲究？短路求值对性能和审计分别有什么影响？

**Q15.**（工程实践）设计一个生产可用的"观察预算"：如何计数、何时检查、超出时怎么办、和上下文窗口管理如何配合？

**Q16.**（场景设计）为一个能执行 shell 的 coding agent 设计 gate 链，至少说出 5 个 gate 及其顺序，并说明它们和 sandbox 的分工。

**Q17.**（追问型）"用正则拒绝列表挡住 `rm -rf` 和 `sudo` 就安全了吗？" 你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：C

实际运行输出：

```text
  [3] turn=4 tool=run_tests -> DENY
        reason: [budget] observation budget exhausted: 322/200 tokens
  [4] turn=5 tool=shell -> DENY
        reason: [whitelist] tool 'shell' not in allow-set [...]
```

前三次观察 tokens 为 9、156、157，累计 322。第 3 回合放行时只剩 35 token 预算（`200 − 165`），但 `BudgetGate` 只检查"调用前是否已用尽"，于是一次读入 157 token，累计冲到 322。第 4 回合 `322 >= 200` 被拒。第 5 回合 `shell` 不在白名单，第一个 gate 就短路，根本轮不到预算 gate，所以 D 的数字不存在。注意讲义说"The third turn trips the budget gate"，实际是第 4 回合（第 4 次调用）触发。

### Q2 — 答案：A

讲义两条理由："You order them by ascending cost so a denied call short-circuits before doing the expensive work" 和 "You also order them by blast radius ... Budget is last because, by definition, it only fires when everything else passed." B 无依据；C 错在 Budget 并非"永远不执行"，每个通过前三关的调用都会执行它；D 错在链是短路的，`decisions` 只包含实际评估过的 gate。

### Q3 — 答案：D

实测结果：`allowed=1, refused=3`，理由依次为 `gap 5/6/7 turns exceeds window 3`。`RecencyGate` 看的是"本次调用回合 − 账本最后一条观察的回合"；被拒绝的调用不会写账本，`latest_turn()` 永远是 1，gap 只会越来越大。这是一个**死锁**：模型无论发起什么调用（包括想"重新读取"的调用）都被拒绝。"第一次调用总是通过"只对空账本成立（B 错）。

### Q4 — 答案：B

匹配对象是 `" ".join(argv) + " " + payload`，`^` 只锚定整个字符串的开头（未开 `re.MULTILINE`）。

- A：拼接后是 `"/etc/passwd "`，开头就是 `/etc/`，被拒。
- B：拼接后是 `"cat /etc/shadow "`，`/etc/` 不在开头，**放行**（实测 `True`）。
- C：`\bsudo\b` 在 `sudo-rs` 中匹配（`-` 是单词边界），被拒——一个误杀的例子。
- D：`rm -rf` 匹配第一个模式，被拒。

同理，payload 永远拼在一个空格之后，`^/etc/` 对 payload **永远**不会命中（实测 payload=`"/etc/x"` 放行）。

### Q5 — 答案：A

`run_synthetic_loop` 中拒绝分支 `refused += 1; continue`，不会调用 `ledger.record`。讲义："Every successful tool call writes one row"。拒绝留下的痕迹在 `decisions`（`ChainOutcome` 列表）和 `refused` 计数中。C 提出了一个真实问题——拒绝理由作为 system message 回给模型时也占上下文——但本节代码没有把它计入账本。

### Q6 — 答案：D

gate 在调用**之前**评估，此时结果尚未产生，不知道大小（`BudgetGate` docstring："A single call cannot in advance know how many tokens its result will be"）。单次输出上限应在 dispatch 之后做：截断到上限并附说明，或拒收并给模型一个"结果过大，请缩小范围"的提示。也可以在调用前做**参数层面**的预防（如强制 `grep` 带 `--max-count`、`read_file` 带行号范围），但那是对参数的约束，不是对输出大小的检查。

### Q7 — 答案：C

实测：`estimate_tokens("abc") = max(1, 3//4) = 1`；`"abcdefgh"` → `8//4 = 2`；8 个汉字 `len()` 是 8 个字符（Python 的 `len` 数的是字符不是字节），`8//4 = 2`。只有空串返回 0（A、D 错）。B 错在 `len` 不按字节计。启示：`len//4` 对英文是粗略平均，对中文会严重**低估**（真实 tokenizer 下 8 个汉字通常需要明显多于 2 个 token），docstring 中的 "conservative" 并不成立。

### Q8 — 答案：B

```python
        fn = tool_fns.get(call.tool)
        if fn is None:
            refused += 1
            continue
```

实测：`allowed=0, refused=1, decisions[0].allow=True`。链说 ALLOW，循环却按拒绝计数，`decisions` 里没有任何 DENY 记录说明原因。审计时会出现"有 1 次拒绝，但找不到拒绝理由"的矛盾。更好的做法是为"无实现"生成一条合成的 `GateDecision(False, "dispatch", "no implementation")`，或在构造链时保证白名单与 `tool_fns` 的键一致。

### Q9 — 参考答案

1. 手算（已运行验证）：

| 回合 | 工具 | 放行前 budget 理由 | 输出长度 | tokens | 累计 |
|------|------|------------------|---------|-------|------|
| 1 | list_dir | `200 tokens of budget remaining` | 37 | 9 | 9 |
| 2 | read_file main.py | `191 tokens ...` | 627 | 156 | 165 |
| 3 | read_file README.md | `35 tokens ...` | 629 | 157 | 322 |
| 4 | run_tests | DENY `322/200` | — | — | 322 |

`BudgetGate` 只判断 `used >= max_tokens`，只要还剩 1 个 token 就放行，放行后结果多大都照单全收。超支量取决于最后一次调用的输出大小，这里超了 61%。（附：`read_file` 的重复串注释说 "sixty bytes long"，实际 `len(...) == 50`。）

2. 没有。循环在 `ledger.record(obs)` 后直接进入下一次调用，下一次调用时 `BudgetGate` 才会看到新状态；docstring 描述的"记录后再检查"并不存在。讲义学习目标 "Refuse a tool call when the cumulative observation budget **would be** exceeded" 也没有被实现——代码是"**已经**超过才拒绝"。

3. 事后截断（已运行验证）：

```python
text = tool_fns[call.tool](call)
remaining = max_tokens - ledger.cumulative()
if estimate_tokens(text) > remaining:
    keep = max(0, remaining * 4 - 40)          # 给截断说明留约 10 token
    text = text[:keep] + f"\n[truncated: {estimate_tokens(text)} tokens, budget left {remaining}]"
obs = Observation(call.turn, call.tool, text, estimate_tokens(text))
```

改造后 demo：tokens 依次 9、156、35，第 4 回合被拒（`200/200`），最终累计正好 **200**。截断说明要告诉模型"内容被截断、还剩多少预算"，否则模型会把半截文件当成完整内容。

### Q10 — 参考答案

1. 绕过（均已实测放行）：
   - `rm -fr /`：标志顺序不同，`-rf` 字面不匹配；
   - `rm -r -f /`、`rm --recursive --force /`：拆开或长选项；
   - `SUDO ls`：正则大小写敏感（真实 shell 中 `SUDO` 通常找不到命令，但说明了模式的脆弱性）；
   - `cat /etc/shadow`、`-n /etc/passwd`：`^/etc/` 只锚定拼接串开头；
   - payload 为 `/etc/x`：payload 前总有一个空格，`^` 永远匹配不上。
   同时还有误杀：`sudo-rs`、`rm -rf.bak` 会被拒绝。
2. 基于 argv 结构的 gate（已实测：上面的绕过全部被拒，`rm a.txt`、`ls -la`、`pseudocode` 放行）：

```python
class ArgvGate:
    name = "argv"
    def evaluate(self, call, ctx):
        argv = list(call.argv)
        if any(a.lower().startswith("sudo") for a in argv):
            return GateDecision(False, self.name, "sudo not allowed")
        if argv and argv[0] == "rm":
            flags = set()
            for a in argv[1:]:
                if a.startswith("--"):
                    flags.add(a)
                elif a.startswith("-"):
                    flags.update("-" + ch for ch in a[1:])   # -fr -> {-f, -r}
            if flags & {"-r", "-R", "--recursive"}:
                return GateDecision(False, self.name, "recursive rm not allowed")
        for a in argv + [call.payload]:
            if re.search(r"(^|\s)/etc/", a):
                return GateDecision(False, self.name, "/etc access")
        return GateDecision(True, self.name, "ok")
```

要点：按 argv 元素逐个解析，把组合短选项拆开；路径检查对每个参数单独做；更根本的是用**命令白名单**而不是拒绝列表，并把路径规范化后与允许的工作目录比较（第 26 课）。

### Q11 — 参考答案

1. 条件比较的是"现在"和"最后一次任何观察"的距离，与"要操作的对象的信息是否陈旧"无关：
   - 模型频繁调用 `list_dir`，却在 40 回合前读过 `a.py`，此时编辑 `a.py` 依然放行——陈旧状态没被拦住；
   - 模型空闲超过 window 后，连"重新读取"都被拒——想刷新状态反而做不到（Q3 的死锁）。
   讲义描述的"older observations are masked"其实是 prompt builder 的职责（在拼上下文时丢弃或折叠旧观察），而不是拒绝调用。
2. 实现（已运行验证）：

```python
@dataclass
class FreshReadGate:
    window: int
    name: str = "fresh-read"
    def evaluate(self, call, ctx):
        if call.tool != "edit_file":
            return GateDecision(True, self.name, "not an edit")
        path = call.argv[0] if call.argv else ""
        reads = [c.turn for c in ctx.history
                 if c.tool == "read_file" and c.argv[:1] == (path,)]
        if not reads:
            return GateDecision(False, self.name, f"edit {path!r} without a prior read")
        gap = call.turn - max(reads)
        if gap > self.window:
            return GateDecision(False, self.name,
                                f"last read of {path!r} is {gap} turns old (> {self.window}); re-read first")
        return GateDecision(True, self.name, f"read {gap} turns ago")
```

结果：`read@1` 放行；`edit@2` 放行；`edit@8` 拒绝（`7 turns old`）；`read@9` 放行；`edit@10` 放行；`edit b.py@11` 拒绝（`without a prior read`）。注意：`ctx.history` 包含被拒绝的调用，严格实现应只看**成功**的读取——可以给 `Observation` 增加 `target` 字段，从账本里查。

### Q12 — 参考答案

1. `"tiny"` → `max(1, 4//4) = 1` token；`"x"*400` → 100 token。第 1 次（预算 80，已用 0）放行，累计 1；第 2 次（已用 1 < 80）放行，累计 101；第 3 次 `101 >= 80` 拒绝，理由 `[budget] observation budget exhausted: 101/80 tokens`。所以 `allowed=2, refused=1`，观察 tokens `[1, 100]`（已实际运行验证）。
2. 精确断言：

```python
self.assertEqual((report.allowed, report.refused), (2, 1))
self.assertEqual([o.tokens for o in report.observations], [1, 100])
self.assertEqual(report.decisions[2].deny_reason,
                 "[budget] observation budget exhausted: 101/80 tokens")
self.assertEqual([d.gate for d in report.decisions[2].decisions],
                 ["whitelist", "regex", "recency", "budget"])
```

3. 预算 102 时第三次调用前已用 101 < 102，放行，累计 201，`refused=0`，原测试会失败。所以"第三次读取被拒"其实是"第二次读取后已超支，第三次读取被拒"；真正的预算越界发生在第二次读取（一次读入 100 token，远超 80 的总预算）。测试名字掩盖了 Q9 的超支问题。

### Q13 — 参考回答要点

- **确定性**：同样的 `(call, ctx)` 永远得到同样的结论，可以回放、可以写单元测试；LLM 裁判同样输入可能不同输出。
- **可审计**：每次拒绝都有 `[gate] reason` 形式的结构化理由，可直接进日志和 trace；讲义："The reason is logged. The model is told."
- **成本与延迟**：哈希查找、正则匹配是微秒级；LLM 裁判每次调用都要一次推理。
- **抗注入**：LLM 裁判本身也读取不可信内容，可能被 prompt injection 说服；确定性规则不会被说服。
- **分工**：确定性 gate 处理"契约内/外"的硬约束；语义层面的判断（这次修改是否合理）可以交给 reviewer agent 等，但不应成为安全边界的唯一一层。
- 常见误区：认为"模型更聪明，所以判断更准"——安全边界要的是可预测，不是聪明。

### Q14 — 参考回答要点

- **成本升序**：Whitelist（O(1) 哈希）→ Regex（O(模式数 × 参数长度)）→ Recency（读最近一条记录）→ Budget（本节实现是对账本求和 O(n)），被拒的调用尽早退出。
- **爆炸半径降序**：先判断"工具是否在契约中"，再判断"参数是否在契约中"，再判断时效与预算。最根本的违约给出最清晰的理由。
- **短路对审计的影响**：`ChainOutcome.decisions` 只包含评估过的 gate。若需要回答"这次调用如果过了白名单，还会被哪些 gate 拦"（例如统计各 gate 的潜在命中率），需要一个"全量评估"模式用于离线分析，线上仍用短路。
- **有副作用的 gate 要小心**：若某个 gate 内部扣减配额，短路会让配额只在部分路径上扣减；gate 应尽量是纯函数。
- 加分点：`BudgetGate` 读整个账本可以优化为维护一个累计计数器；排序也可以按真实命中率和耗时动态调整，但安全相关的 gate 要固定在前面。

### Q15 — 参考回答要点

- **计数**：用目标模型的真实 tokenizer；按工具、按回合、按会话三个维度记账（本节 `per_tool`、`cumulative`）。
- **事前**：根据参数预估输出（`read_file` 的文件大小、`grep` 的匹配数上限），强制工具参数带上限（行范围、`--max-count`）。
- **事后**：单次观察超过阈值就截断并附说明（Q9）；对结构化输出做摘要（只保留失败的测试）；大内容落盘，只把路径和摘要给模型。
- **超出时**：拒绝后续观察类调用，允许"收尾"类调用（如提交、总结）；或触发上下文压缩（compaction）后重置部分预算。
- **与上下文管理配合**：观察预算控制"给模型看了多少"，上下文窗口控制"当前还能放多少"；旧观察可以折叠成摘要，这正是讲义 RecencyGate 想表达但代码没实现的"masking"。
- 常见误区：只设会话总预算，导致一次大输出吃光全部预算（本节 demo 的 322/200）。

### Q16 — 参考回答要点

1. **工具白名单**：只允许 `read_file / list_dir / edit_file / run_tests / shell`。
2. **命令白名单 + argv 解析**：`shell` 的 `argv[0]` 必须在允许集合中（`python`、`pytest`、`git status` 等），解析组合选项（Q10）。
3. **路径 gate**：所有路径参数规范化（`realpath`）后必须位于工作目录内，拒绝 `..` 逃逸和符号链接逃逸。
4. **网络 gate**：拒绝 `curl/wget` 到内网 IP、元数据地址；或默认禁网。
5. **新鲜度 gate**：编辑前必须在 N 回合内读过同一文件（Q11）。
6. **预算 gate**：观察 token、调用次数、墙钟时间。
7. **高风险操作需人工确认**：如 `git push`、删除文件。

顺序：工具白名单 → 命令/参数 → 路径 → 网络 → 新鲜度 → 预算 → 人工确认。分工：gate 是**调用前**的策略判断（可以说"不"并给理由）；sandbox（第 26 课）是**执行时**的隔离（即使 gate 被绕过，进程也只能在受限目录、受限资源中运行）。两者是纵深防御，不能互相替代。

### Q17 — 参考回答要点

- 不安全。拒绝列表天然不完备：`rm -fr`、`rm -r -f`、`find / -delete`、`python -c "import shutil; shutil.rmtree('/')"`、写一个脚本再执行、base64 编码后 `| sh`……正则在字符串层面无法覆盖 shell 的语义。
- 正则还会误杀（`sudo-rs`、`rm -rf.bak`）和漏锚（`^/etc/` 只看开头）。
- 正确思路：
  - **允许列表优于拒绝列表**：只放行明确需要的命令和参数形态；
  - **结构化解析**：用 argv 而不是 shell 字符串，禁止 `shell=True`；
  - **执行隔离**：sandbox、只读挂载、无网络、资源限制、超时（第 26 课）；
  - **最小权限**：agent 进程本身无 root、无敏感凭据。
- 拒绝列表仍有价值：作为便宜的第一道过滤和可读的拒绝理由，但只能是纵深防御的一层。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 20 Agent Harness 的循环契约](../../20-agent-harness-loop-contract/docs/zh.md)：gate 链插在 harness 循环的"模型提出调用"与"执行调用"之间。
- [阶段 19 · 21 带 Schema 校验的工具注册表](../../21-tool-registry-schema-validation/docs/zh.md)：白名单的来源是注册表中的工具集合。
- [阶段 19 · 24 计划—执行控制流程](../../24-plan-execute-control-flow/docs/zh.md)：上一课的步骤预算与重规划预算，本课补上观察预算。
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../../14-agent-engineering/33-instructions-as-executable-constraints/docs/zh.md)：把规则写成可执行的检查。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../../14-agent-engineering/36-scope-contracts/docs/zh.md)：白名单与参数约束就是 scope contract 的代码化。
- [阶段 14 · 38 Verification Gates](../../../14-agent-engineering/38-verification-gates/docs/zh.md)：verification gate 的概念来源。

### 本节被哪些后续内容用到
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：gate 放行后，由 sandbox 在隔离环境中执行。
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../27-eval-harness-fixture-tasks/docs/zh.md)：把拒绝次数作为质量信号。
- [阶段 19 · 28 OTel GenAI Spans 与 Prometheus Metrics](../../28-observability-otel-traces/docs/zh.md)：把 `GateDecision` 写入 span。
- [阶段 19 · 29 基于 Harness 的端到端 Coding Agent](../../29-end-to-end-coding-task-demo/docs/zh.md)：把 gate 链装进完整的 coding agent。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：更广义的预算与成本治理。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../../14-agent-engineering/27-prompt-injection-defense/docs/zh.md)：确定性 gate 是抵御注入的重要一层。

### 延伸关键词
`verification gate` · `short-circuit evaluation` · `allowlist vs denylist` · `observation budget` · `context window management` · `output truncation` · `typing.Protocol` · `defense in depth` · `least privilege` · `tiktoken` · `audit trail`
