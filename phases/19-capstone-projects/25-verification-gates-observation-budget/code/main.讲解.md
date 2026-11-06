# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 25 节 Verification Gates 与观察预算 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（退出码 0 表示 demo 至少出现一次拒绝）；测试：`python3 -m pytest -q tests` ｜ **依赖**：仅标准库（`json`、`re`、`sys`、`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

这份代码实现了 agent harness 中"模型提出工具调用"与"真正执行工具"之间的那一层：**确定性的 verification gate 链 + 观察账本**。

1. **Gate 协议**：用 `typing.Protocol` 定义"有 `name` 和 `evaluate(call, ctx)` 的东西就是 gate"。
2. **四个具体 gate**（外加一个可选的按工具预算 gate）：白名单、正则拒绝、时效、累计预算。
3. **链式短路**：`GateChain` 按顺序评估，遇到第一个 DENY 就返回；结果 `ChainOutcome` 记录所有被评估过的决定。
4. **观察账本**：每次成功的工具调用写一行 `(turn, tool, tokens)`，回答"总共看了多少"和"某工具看了多少"。
5. **结构化决策**：`GateDecision(allow, gate, reason)` 可以直接序列化给日志、trace、评估系统。
6. **合成循环**：`run_synthetic_loop` 用固定的调用序列模拟 harness，演示预算耗尽与白名单拒绝。

> 一句话：**让 harness 能对工具调用说"不"，而且每一次"不"都有可审计的理由。** 同时要看清：预算是事前检查（会超支）、时效 gate 会死锁、正则拒绝列表容易绕过——这些正是面试追问点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ToolCall` | frozen dataclass | 模型请求：回合、工具名、argv 元组、payload | 调用的线上形状 |
| `Observation` | frozen dataclass | 模型看到的结果：回合、工具、文本、tokens | 观察 |
| `GateDecision` | frozen dataclass | 单个 gate 的判定 | 结构化决策记录 |
| `estimate_tokens` | 函数 | `max(1, len//4)`，空串 0 | token 计数占位 |
| `ObservationLedger` | dataclass | 只追加的观察账本：`cumulative / per_tool / turns_seen / latest_turn / snapshot` | 观察账本 |
| `GateContext` | dataclass | 传给 gate 的上下文：账本、当前回合、历史调用 | gate 输入 |
| `VerificationGate` | Protocol | gate 的结构化接口 | Gate 协议 |
| `WhitelistGate` | dataclass | 工具名必须在允许集合中 | 权限蔓延防护 |
| `RegexGate` | dataclass | argv+payload 拼接后匹配拒绝模式 | 参数约束 |
| `RecencyGate` | dataclass | 本回合与最后一次观察的回合差 ≤ window | 陈旧观察 |
| `BudgetGate` | dataclass | 累计观察 token < 上限 | 观察预算 |
| `PerToolBudgetGate` | dataclass | 单工具累计 token < 各自上限（讲义中的练习，代码已给出） | 按工具预算 |
| `ChainOutcome` | dataclass | 决定列表 + `allow` / `deny_reason` 属性 | 链结果 |
| `GateChain` | dataclass | 有序 gate 元组，短路评估 | 链式短路 |
| `LoopReport` / `run_synthetic_loop` | dataclass / 函数 | 跑一串固定调用，统计放行/拒绝、记录观察 | harness 骨架 |
| `_demo_tools` / `build_default_chain` / `run_demo` | 函数 | 三个假工具、默认四 gate 链、5 次调用的演示 | 演示 |

数据流：`run_demo` → `build_default_chain(200)` + `_demo_tools()` → `run_synthetic_loop`：对每个 `ToolCall` 构造 `GateContext` → `GateChain.evaluate` → DENY 则计数跳过；ALLOW 则调用工具 → `estimate_tokens` → `ledger.record` → 返回 `LoopReport` → 打印逐回合判定与累计 token。

---

## 3. 逐段精讲

### 3.1 线上形状：三个 frozen dataclass

```python
@dataclass(frozen=True)
class ToolCall:
    turn: int
    tool: str
    argv: tuple[str, ...]
    payload: str = ""
```

- `frozen=True`：实例创建后不能修改字段（赋值会抛 `FrozenInstanceError`），而且可哈希。gate 拿到的调用对象不会被别的 gate 偷偷改掉——这对"确定性"很重要。
- `argv` 用 `tuple[str, ...]`（任意长度的字符串元组）而不是 list，同样是为了不可变。
- `Observation.to_dict()` **不包含 `text`**：快照里只记元数据，避免把大段工具输出复制进日志。
- `GateDecision` 的字段顺序是 `(allow, gate, reason)`，代码里多处按位置构造，如 `GateDecision(True, self.name, "tool in allow-set")`。讲义写的是 `(allow, reason, gate_name)`，顺序不同，按位置构造时要以代码为准。

### 3.2 `estimate_tokens`：故意简陋的计数器

```python
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)
```

- 非空文本至少 1 个 token；`"abc"` → 1，`"abcdefgh"` → 2。
- `len()` 数的是**字符**，8 个汉字也只算 2 个 token。对中文、代码中的长标识符，这会显著低估；docstring 说它 "conservative"（保守，即宁可高估），对 CJK 文本并不成立。
- 讲义："The token counter is intentionally a stupid `len(text) // 4` heuristic... Drop in a real tokenizer in production." gate 链只要求计数器"单调、确定"。

### 3.3 `ObservationLedger`

```python
@dataclass
class ObservationLedger:
    rows: list[Observation] = field(default_factory=list)

    def cumulative(self) -> int:
        return sum(row.tokens for row in self.rows)

    def per_tool(self, name: str) -> int:
        return sum(row.tokens for row in self.rows if row.tool == name)

    def latest_turn(self) -> int:
        return self.rows[-1].turn if self.rows else -1
```

- `field(default_factory=list)`：每个账本有自己的空列表。写成 `rows: list = []` 会被 dataclass 直接拒绝（可变默认值报 `ValueError`）。
- `cumulative()` 每次都对全表求和，O(n)。讲义把 Budget 放在链末尾的理由之一就是它"reads the entire ledger"；生产中维护一个累计计数器即可 O(1)。
- `latest_turn()` 取的是**最后追加**的那一行的回合，而不是最大回合；在本循环里两者相同。空账本返回 −1 作为哨兵值。
- 只有成功的观察会被记录（见 3.8）。拒绝理由虽然也会回给模型，但没有计入账本。

### 3.4 `GateContext` 与 `VerificationGate` 协议

```python
@dataclass
class GateContext:
    ledger: ObservationLedger
    current_turn: int
    history: tuple[ToolCall, ...] = ()


class VerificationGate(Protocol):
    name: str

    def evaluate(self, call: ToolCall, ctx: GateContext) -> GateDecision: ...
```

- `Protocol` 是**结构化子类型**（鸭子类型的静态版本）：下面的 gate 类都没有继承 `VerificationGate`，只要有 `name` 属性和签名匹配的 `evaluate` 方法，类型检查器就认为它们符合协议。运行时不做检查（没有 `@runtime_checkable`）。
- docstring 称 `GateContext` 为 "Read-only"，但它不是 frozen，`ledger` 也是可变对象——只是约定。
- `current_turn` 和 `history` 在本文件的所有 gate 中**都没有被使用**（gate 用的是 `call.turn`），它们是留给扩展的（例如测验 Q11 的 `FreshReadGate` 就用到了 `history`）。注意 `history` 包含被拒绝的调用。

### 3.5 `WhitelistGate` 与 `RegexGate`

```python
@dataclass
class WhitelistGate:
    allowed: frozenset[str]
    name: str = "whitelist"

    def evaluate(self, call, ctx):
        if call.tool in self.allowed:
            return GateDecision(True, self.name, "tool in allow-set")
        return GateDecision(False, self.name,
            f"tool {call.tool!r} not in allow-set {sorted(self.allowed)}")
```

- `frozenset` 的成员判断是 O(1) 哈希查找，讲义说它是最便宜的 gate。
- 拒绝理由里列出了整个允许集合，模型可以据此改用正确的工具；但在安全敏感场景下这也暴露了能力清单，可按需裁剪。
- `{call.tool!r}`：`!r` 调用 `repr()`，字符串会带引号，方便看出空格等不可见字符。

```python
@dataclass
class RegexGate:
    refuse_patterns: tuple[re.Pattern[str], ...]
    name: str = "regex"

    @classmethod
    def from_strings(cls, patterns, name="regex"):
        compiled = tuple(re.compile(p) for p in patterns)
        return cls(refuse_patterns=compiled, name=name)

    def evaluate(self, call, ctx):
        haystack = " ".join(call.argv) + " " + call.payload
        for pat in self.refuse_patterns:
            if pat.search(haystack):
                return GateDecision(False, self.name, f"argv matched refuse pattern {pat.pattern!r}")
        return GateDecision(True, self.name, "no refuse pattern matched")
```

- `@classmethod` 作为"备用构造器"：接受字符串、预先编译，避免每次评估都重新编译正则。
- `pat.search` 在任意位置查找（`match` 只从开头）。
- ⚠️ 拼接字符串带来的问题（均已实测）：
  - 默认模式 `^/etc/` 只锚定整个 haystack 的开头：`argv=("cat", "/etc/shadow")` 放行；payload 前面永远有一个空格，所以 `^/etc/` 对 payload **永远**不生效。
  - `\brm\s+-rf\b` 挡不住 `rm -fr`、`rm -r -f`、`rm --recursive --force`。
  - 正则大小写敏感：`SUDO` 不匹配。
  - 同时会误杀：`sudo-rs`、`rm -rf.bak` 被拒（`\b` 把 `-`、`.` 当作单词边界）。
- 在 demo 中，`shell` 调用先被白名单拦下，`RegexGate` **从来没有真正触发过拒绝**；它只在单元测试中被单独验证。

### 3.6 `RecencyGate`

```python
    def evaluate(self, call, ctx):
        last = ctx.ledger.latest_turn()
        if last < 0:
            return GateDecision(True, self.name, "no prior observations")
        gap = call.turn - last
        if gap > self.window:
            return GateDecision(False, self.name,
                f"observation gap {gap} turns exceeds window {self.window}")
        return GateDecision(True, self.name, f"gap {gap} within window {self.window}")
```

- 判定：本次调用回合与最后一次观察回合之差 > window 即拒绝；空账本总是放行。
- ⚠️ **死锁**：被拒绝的调用不写账本，`latest_turn()` 不会更新，gap 只会越来越大。实测 window=3、最后观察在第 1 回合时，第 6、7、8 回合的调用全部被拒，之后也永远被拒——包括模型想"重新读取"的调用。docstring 说 "The intent is to force a fresh read"，实际效果恰好相反。
- 讲义描述的是"模型只看到最近 N 回合的观察，旧的被 mask"——那是 prompt builder 在拼上下文时该做的事，本节代码没有实现 masking。更合理的 gate 是"编辑某文件前必须在 N 回合内读过它"（测验 Q11）。

### 3.7 `BudgetGate` 与 `PerToolBudgetGate`

```python
    def evaluate(self, call, ctx):
        used = ctx.ledger.cumulative()
        if used >= self.max_tokens:
            return GateDecision(False, self.name,
                f"observation budget exhausted: {used}/{self.max_tokens} tokens")
        remaining = self.max_tokens - used
        return GateDecision(True, self.name, f"{remaining} tokens of budget remaining")
```

- **事前检查**：只看调用前的账本，`used >= max_tokens` 才拒绝；等于上限也拒绝（测试 `test_at_budget_denies`）。
- ⚠️ 只要还剩 1 个 token 就放行，放行后输出多大都照收。demo 中第 3 回合只剩 35 token，却读入 157 token，累计 322/200，超支 61%。
- ⚠️ docstring 说 "the harness re-runs the cumulative check against the new ledger state after recording the observation"，但 `run_synthetic_loop` 并没有这样做；讲义学习目标 "Refuse a tool call when the cumulative observation budget **would be** exceeded" 也没实现。修复思路是事后截断（测验 Q9：改造后 demo 累计正好 200）。
- `PerToolBudgetGate` 逻辑相同，按 `ledger.per_tool(call.tool)` 计；`limits.get(call.tool)` 为 `None` 的工具不受限。讲义说这是"你将作为练习编写"的 gate，但代码已经给出，且没有放进默认链。

### 3.8 `ChainOutcome` 与 `GateChain`

```python
@dataclass
class ChainOutcome:
    decisions: list[GateDecision]

    @property
    def allow(self) -> bool:
        return all(d.allow for d in self.decisions)

    @property
    def deny_reason(self) -> str | None:
        for d in self.decisions:
            if not d.allow:
                return f"[{d.gate}] {d.reason}"
        return None


@dataclass
class GateChain:
    gates: tuple[VerificationGate, ...]

    def evaluate(self, call, ctx) -> ChainOutcome:
        decisions = []
        for gate in self.gates:
            decision = gate.evaluate(call, ctx)
            decisions.append(decision)
            if not decision.allow:
                return ChainOutcome(decisions=decisions)
        return ChainOutcome(decisions=decisions)
```

- `@property` 让 `outcome.allow` 像属性一样访问，但每次都由 `decisions` 计算，不会和列表不同步。
- 短路：DENY 时 `decisions` 只含到拒绝为止的 gate。demo 中 `shell` 调用的 `decisions` 只有 1 条（whitelist），而 `run_tests` 的有 4 条（最后一条是 budget DENY）。
- 空链：`all([])` 为 `True`，没有 gate 时一切放行——"默认允许"，要警惕。
- `deny_reason` 的格式 `[gate] reason` 正是 demo 打印和测验里看到的字符串。

### 3.9 `run_synthetic_loop`：harness 骨架

```python
    for call in calls:
        ctx = GateContext(ledger=ledger, current_turn=call.turn, history=tuple(history))
        outcome = chain.evaluate(call, ctx)
        decisions.append(outcome)
        history.append(call)
        if not outcome.allow:
            refused += 1
            continue
        fn = tool_fns.get(call.tool)
        if fn is None:
            refused += 1
            continue
        result = fn(call)
        obs = Observation(turn=call.turn, tool=call.tool, text=result,
                          tokens=estimate_tokens(result))
        ledger.record(obs)
        observations.append(obs)
        allowed += 1
```

- `history=tuple(history)`：每次传入一个不可变快照，gate 无法修改循环的历史列表。
- 所有调用（包括被拒绝的）都进入 `history`。
- ⚠️ 白名单放行但 `tool_fns` 里没有实现的工具：`refused += 1`，但 `decisions` 中对应的 `ChainOutcome.allow` 是 `True`。实测 `allowed=0, refused=1, allow=True`——审计记录里找不到这次"拒绝"的理由。
- ⚠️ 工具函数抛异常不会被捕获，会直接中断整个循环。
- 讲义架构图中的"拒绝作为 system message 回给模型""达到阈值就中止循环"都没有实现：循环只计数，不会中止。

### 3.10 Demo 装配

```python
    def read_file(call: ToolCall) -> str:
        target = call.argv[0] if call.argv else "<missing>"
        return (f"# fake contents of {target}\n"
                + ("line of fake source code that is sixty bytes long " * 12))
```

- 这行"假源码"注释说是 sixty bytes，实际 `len(...) == 50`；`read_file main.py` 输出 627 字符（156 token），`README.md` 629 字符（157 token）。
- `list_dir` 输出 37 字符（9 token）；`run_tests` 输出 `json.dumps(..., indent=2)` 后 59 字符（14 token，但被拒，没有执行）。
- `build_default_chain` 按讲义顺序装配：Whitelist（三个工具）→ Regex（`rm -rf`、`sudo`、`^/etc/`）→ Recency(window=3) → Budget。
- `run_demo` 在没有任何拒绝时返回 1 并打到 stderr，`sys.exit(run_demo())` 把它变成进程退出码——demo 本身也是一个"自检"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 确定性 gate 而非 LLM 裁判 | 可回放、可测试、可审计、抗注入 | 只能表达硬规则；语义判断需另一层（如 reviewer agent） |
| `Protocol` 定义 gate 接口 | 任何对象只要形状对就能放进链，无需继承 | 运行时不检查，写错方法名只能靠测试发现 |
| frozen dataclass 表示调用与决策 | 不可变，gate 之间互不干扰；可直接 `to_dict` | 每次修改需要新建对象 |
| 链式短路、按成本与爆炸半径排序 | 被拒的调用尽早退出，理由最根本 | 审计记录只含部分 gate；离线分析可加"全量评估"模式 |
| `len // 4` 估算 token | 课程重点是管道而不是分词器 | 对中文严重低估；生产用目标模型 tokenizer |
| 预算只做事前检查 | 调用前无法得知输出大小 | 最后一次放行可大幅超支；应加事后截断或按参数预估 |
| 拼接字符串跑正则 | 简单 | 容易绕过也容易误杀；应解析 argv、用命令白名单、配合 sandbox |
| 时效 gate 比较"最后一次任何观察" | 实现简单 | 空闲后永久死锁且挡不住真正的陈旧编辑；应按对象（文件）追踪新鲜度，或在 prompt builder 中 mask |
| 账本只记成功观察 | 账本代表"模型看到的工具输出" | 拒绝理由也占上下文却不计入；可单独记账 |
| 合成循环固定调用序列 | 不依赖模型，便于测试 | 无"拒绝回传模型""阈值中止"逻辑；真实 harness 需要补上 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，`re.Pattern[str]`、`tuple[str, ...]` 等写在注解里不会在运行时求值 |
| `@dataclass(frozen=True)` | `ToolCall`、`Observation`、`GateDecision` | 不可变 dataclass，字段赋值会抛 `FrozenInstanceError`，实例可哈希 |
| `field(default_factory=list)` | `rows: list[Observation] = field(default_factory=list)` | 可变默认值必须用工厂函数 |
| 变长元组类型 | `argv: tuple[str, ...]` | `...` 表示任意长度、元素同类型 |
| `typing.Protocol` | `class VerificationGate(Protocol)` | 结构化子类型：形状匹配即符合接口，无需继承 |
| `...` 作为函数体 | `def evaluate(...) -> GateDecision: ...` | 协议中只声明签名，`...`（Ellipsis）占位 |
| `@classmethod` 备用构造器 | `RegexGate.from_strings(...)` | 第一个参数是类本身 `cls`，返回 `cls(...)` |
| `@property` | `ChainOutcome.allow`、`deny_reason` | 方法当属性访问，值实时计算 |
| `re.compile` / `pattern.search` / `.pattern` | `RegexGate` | 预编译正则；`search` 在任意位置匹配；`.pattern` 取回原始字符串 |
| 原始字符串 | `r"\brm\s+-rf\b"` | 反斜杠不转义，写正则必备；`\b` 是单词边界 |
| `frozenset` | `frozenset({"read_file", ...})` | 不可变集合，O(1) 成员判断 |
| 生成器表达式 + 内置函数 | `sum(row.tokens for row in self.rows)`、`all(d.allow for d in ...)` | 不建中间列表；`all([])` 为 `True` |
| 集合推导 + `sorted` | `sorted({row.turn for row in self.rows})` | 去重后排序 |
| 条件表达式 | `self.rows[-1].turn if self.rows else -1` | 一行 if-else |
| f-string 的 `!r` | `f"tool {call.tool!r} not in ..."` | 用 `repr()` 格式化，字符串带引号 |
| `dict.get` 返回 `None` | `tool_fns.get(call.tool)`、`self.limits.get(call.tool)` | 键不存在不抛异常 |
| `enumerate` + `zip` | `for idx, (call, outcome) in enumerate(zip(calls, report.decisions))` | 同时拿下标和成对元素，括号做元组解包 |
| `print(..., file=sys.stderr)` | `run_demo` | 错误信息写到标准错误 |
| `sys.exit(run_demo())` | 文件末尾 | 用函数返回值作为进程退出码 |
| 嵌套函数返回字典 | `_demo_tools()` 中定义三个函数并返回 `{"read_file": read_file, ...}` | 函数是一等对象，可以放进字典 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，约 0.04 秒，退出码 0）：

```text
VERIFICATION GATE DEMO
turns=5 allowed=3 refused=2

  [0] turn=1 tool=list_dir -> ALLOW
  [1] turn=2 tool=read_file -> ALLOW
  [2] turn=3 tool=read_file -> ALLOW
  [3] turn=4 tool=run_tests -> DENY
        reason: [budget] observation budget exhausted: 322/200 tokens
  [4] turn=5 tool=shell -> DENY
        reason: [whitelist] tool 'shell' not in allow-set ['list_dir', 'read_file', 'run_tests']

cumulative tokens observed: 322
observations recorded: 3
```

逐项解读（每次放行的 budget 理由已用脚本打印核对）：

| 回合 | 工具 | 链评估的 gate | budget 理由 | 观察 tokens | 累计 |
|------|------|-------------|------------|-----------|------|
| 1 | list_dir | 4 个全部通过（recency：`no prior observations`） | `200 tokens of budget remaining` | 9 | 9 |
| 2 | read_file main.py | 4 个通过（recency：`gap 1 within window 3`） | `191 ...` | 156 | 165 |
| 3 | read_file README.md | 4 个通过 | `35 ...` | 157 | 322 |
| 4 | run_tests | 前 3 个通过，budget 拒绝 | `exhausted: 322/200` | — | 322 |
| 5 | shell | whitelist 拒绝，短路 | 未评估 | — | 322 |

- **预算超支**：第 3 回合只剩 35 token 却放行了 157 token 的读取，最终 322/200。讲义说"第三回合触发预算 gate"，实际是第 4 回合（第 4 次调用）被拒。
- **短路**：第 5 回合的 `ChainOutcome.decisions` 只有 1 条；`rm -rf /` 本来也会被 `RegexGate` 拒绝，但轮不到它。
- **退出码**：`refused=2 >= 1`，`run_demo` 返回 0。

测试中的 `test_demo_main_exits_zero` 会再跑一次 demo，所以运行 pytest 时这段输出会再被打印一次（pytest 默认捕获输出，`-s` 时可见）。

---

## 7. 动手改一改

1. 把 `PerToolBudgetGate(limits={"read_file": 150})` 插到 `BudgetGate` 之前，重跑 demo，观察第 3 回合由哪个 gate 拒绝、理由是什么。
2. 实现事后截断：在 `run_synthetic_loop` 中，观察超过剩余预算时截短文本并附 `[truncated ...]` 说明，使累计值不超过上限（参考测验 Q9：结果应为 9、156、35，累计 200）。
3. 修复"无实现工具"的审计不一致：`fn is None` 时向 `decisions[-1]` 追加一条 `GateDecision(False, "dispatch", "no implementation")`，并让 `ChainOutcome.allow` 反映它。
4. 用 argv 结构化解析重写 `RegexGate`（或新增 `ArgvGate`），覆盖 `rm -fr`、`rm -r -f`、`cat /etc/shadow`、payload 中的 `/etc/`，同时不误杀 `sudo-rs` 以外的正常命令（参考测验 Q10）。
5. 把 `RecencyGate` 换成 `FreshReadGate`：编辑前必须在 N 回合内成功读取过同一文件；给 `Observation` 增加 `target` 字段，从账本而不是 `history` 判断"成功读取"。
6. 进阶：给循环增加"连续拒绝 K 次即中止"的阈值，并把每次拒绝理由作为 system message 追加到一个简易 message store，统计这些拒绝消息占用的 token。

---

## 8. 常见坑

- **以为预算是硬上限**：事前检查只能保证"超了之后不再放行"，不能保证"不超"。需要事后截断或按参数预估。
- **正则拼接匹配**：`^` 锚点只对拼接串开头有效；字符串层面的拒绝列表既漏又误杀。
- **时效 gate 用"最后一次任何观察"判断**：空闲后永久死锁，而且挡不住针对具体文件的陈旧编辑。
- **空链默认放行**：`all([])` 为 `True`；构造链时应断言至少有白名单 gate。
- **白名单与工具实现不一致**：链放行但没有实现时，计数和审计记录对不上。
- **`len // 4` 用于中文**：会把中文观察低估数倍，预算形同虚设。
- **gate 里有副作用**：短路会让副作用只在部分路径发生；gate 应是纯函数。
- **测试只断言 `>= 1`**：`test_loop_trips_budget_on_third_read` 把预算改成 102 就会失败，但断言写得太松，看不出超支在第二次读取时就已发生。

---

## 9. 测试在验证什么

运行方式：在 `code/` 目录下执行 `python3 -m pytest -q tests`（或 `python3 -m unittest discover -s tests`）。测试通过 `sys.path.insert` 把 `code/` 加入导入路径。实际运行结果：**21 passed**。

| 测试类 / 测试 | 验证的性质 |
|-------------|-----------|
| `LedgerTests.test_empty_ledger_has_zero_cumulative` | 空账本：累计 0、按工具 0、`latest_turn() == -1` |
| `LedgerTests.test_per_tool_accounting` | 记录 20/30/10 后：累计 60、`read_file` 50、`list_dir` 10、最新回合 3、`turns_seen == [1,2,3]` |
| `TokenEstimatorTests.test_estimator_is_monotonic` | `"ab"` ≤ `"abcd"` < `"abcd"*100`（实际为 1、1、100） |
| `TokenEstimatorTests.test_estimator_zero_on_empty` | 空串返回 0 |
| `WhitelistGateTests`（2 个） | 已知工具放行且 `gate == "whitelist"`；未知工具拒绝且理由含 `not in allow-set` |
| `RegexGateTests`（3 个） | 用测试自己的模式 `rm\s+-rf`、`sudo`：`ls -la` 放行，`rm -rf /`、`sudo apt install` 拒绝。注意没有测试默认链中的 `^/etc/` |
| `RecencyGateTests`（3 个） | 空账本放行；最后观察在第 5 回合、当前第 7 回合（gap 2）放行；第 1 → 第 10 回合（gap 9）拒绝且理由含 `gap` |
| `BudgetGateTests`（3 个） | 用了 40/100 放行；恰好 100/100 拒绝（`>=`）；200/100 拒绝 |
| `PerToolBudgetGateTests`（2 个） | 无限额工具放行；`read_file` 用了 60 > 50 拒绝 |
| `ChainShortCircuitTests.test_chain_short_circuits_on_first_deny` | 白名单拒绝后，后面那个"匹配一切"的正则 gate 不被评估，`decisions` 只有 1 条 |
| `ChainShortCircuitTests.test_chain_allows_when_all_gates_pass` | 默认链（预算 500）对首次 `read_file main.py` 放行，4 个 gate 都被评估 |
| `SyntheticLoopTests.test_loop_trips_budget_on_third_read` | 预算 80 时出现至少 1 次拒绝和 1 次放行（实测 `allowed=2, refused=1`，观察 `[1, 100]`，第三次理由 `101/80`） |
| `SyntheticLoopTests.test_demo_main_exits_zero` | `run_demo()` 返回 0（demo 至少有一次拒绝） |

覆盖空白：
- `RecencyGate` 空闲后的永久拒绝（死锁）没有测试；
- 预算超支量没有测试（只断言"出现过拒绝"）；
- 默认 `RegexGate` 模式的绕过与误杀没有测试；
- "链放行但无工具实现"的计数不一致没有测试；
- `GateContext.history`、`current_turn` 没有任何 gate 使用，也没有测试。
