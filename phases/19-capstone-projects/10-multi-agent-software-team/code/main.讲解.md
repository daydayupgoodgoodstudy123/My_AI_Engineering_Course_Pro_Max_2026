# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 10 节 多 Agent 软件工程团队 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`random`、`collections.defaultdict`、`dataclasses`、`enum`）；所有 LLM 调用都是桩函数

---

## 1. 这份代码在考察什么

讲义的综合项目是一个真实的多 agent 软件工厂：architect（Opus 4.7）规划，4 个 coder（Sonnet 4.7）在各自的 `git worktree` + Daytona 沙箱里并行实现，merge coordinator 三方合并，reviewer（GPT-5.4）把关，tester（Gemini 2.5 Pro）验证；在 50 个 SWE-bench Pro issue 上与单 agent 基线对比，并报告"哪些 handoff 坏了、多频繁"。

`main.py` 的 docstring 说它抓住的"最难的架构原语"是：**协调各角色的类型化消息任务板，以及每次角色边界产生的 trace 记录**。具体做了：

1. 用 `Enum` 定义消息类型（A2A 风格的类型化消息）；
2. 用 `Board` 记录所有消息，并按发送方累计 token；
3. 用桩函数模拟 architect / coder / reviewer / tester 的行为（包括按概率注入 bug、reviewer 漏检、测试 flake）；
4. 串起完整流程，统计 handoff 数和 token；
5. 与"单 agent 基线"做 10 次对比，算出 token 放大倍数。

> 一句话：**这份代码让你看到消息如何在角色之间流动、token 记在谁头上**。同时它在反馈路由、修订、子任务分配上有几处明显的简化或 bug，恰好对应讲义所说的"handoff 是失败面"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MsgKind` | Enum | 9 种消息类型 | 类型化消息 / A2A |
| `Msg` | dataclass | 类型、发送方、接收方、payload、token 数 | 一次 handoff |
| `Board` | dataclass | 消息列表 + 按角色的 token 计数；`post`、`inbox` | 任务板 / 黑板 |
| `Subtask` | dataclass | 名字、文件列表、改动行数、是否含 bug | 子任务 |
| `architect_plan` | 函数 | 固定 4 个子任务，30% 概率给其中一个注入 bug | Architect |
| `coder_implement` | 函数 | 随机 15–95 行改动 | Coder |
| `reviewer_check` | 函数 | 有 bug 时 85% 拒绝、15% 误批准 | Reviewer |
| `tester_run` | 函数 | 有 bug 必失败；无 bug 3% flake | Tester |
| `run_team` | 函数 | 编排全流程，返回结果字典 | Orchestrator |
| `single_agent_baseline` | 函数 | 68% 通过、18k–24k token 的随机桩 | 单 agent 基线 |
| `main` | 函数 | 1 次详细运行 + 10 次对比 | 报告 |

数据流：`architect_plan` → `PLAN_REQUEST` + 4 × `SUBTASK` → 4 × `coder_implement` → 4 × `DIFF_READY` → `REVIEW_NEEDED` → `reviewer_check` →（拒绝时：`REVIEW_FEEDBACK` → `DIFF_READY` → `APPROVED`；批准时：`APPROVED`）→ `tester_run` → `TEST_PASSED` / `TEST_FAILED`。

---

## 3. 逐段精讲

### 3.1 类型化消息：`MsgKind` 与 `Msg`

```python
class MsgKind(Enum):
    PLAN_REQUEST = "plan_request"
    SUBTASK = "subtask"
    DIFF_READY = "diff_ready"
    REVIEW_NEEDED = "review_needed"
    REVIEW_FEEDBACK = "review_feedback"
    APPROVED = "approved"
    TEST_NEEDED = "test_needed"
    TEST_PASSED = "test_passed"
    TEST_FAILED = "test_failed"


@dataclass
class Msg:
    kind: MsgKind
    by: str
    to: str
    payload: dict = field(default_factory=dict)
    tokens: int = 0
```

- 用 `Enum` 而不是裸字符串：拼写错误会在访问属性时立即报 `AttributeError`，而不是悄悄产生一种"没人订阅"的消息类型。这就是讲义说的"typed messages"。
- 枚举值是小写字符串，便于序列化到 JSONL（讲义 Build It 第 1 步：任务板是"File-backed JSONL"）。
- 与讲义的类型列表对比：讲义有 `rejected`、`replan_needed`，代码没有；代码有 `REVIEW_FEEDBACK`、`TEST_PASSED/FAILED`（与讲义 Build It 第 5、6 步一致）。`TEST_NEEDED` 定义了但从未使用。
- `Msg.tokens` 是"这条消息的 token 数"，`by` 是发送方——它决定 token 记在谁的账上。

### 3.2 任务板：`Board`

```python
@dataclass
class Board:
    messages: list[Msg] = field(default_factory=list)
    tokens_by_role: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def post(self, m: Msg) -> None:
        self.messages.append(m)
        self.tokens_by_role[m.by] += m.tokens

    def inbox(self, role: str) -> list[Msg]:
        return [m for m in self.messages if m.to == role]
```

- `default_factory=lambda: defaultdict(int)`：`defaultdict(int)` 在键不存在时自动给 0，所以 `+=` 不需要先判断。注解写的是 `dict[str, int]`，`defaultdict` 是 `dict` 的子类，类型上兼容。
- **token 记在发送方**：architect 发了 5 条消息（1 × 4,500 + 4 × 1,200 = 9,300），所以 architect 是最"贵"的角色；而 reviewer 只记了它发出的 1,800，**读合并 diff 的输入 token 没有被计算**。真实系统中输入 token 往往是大头，所以这里会低估放大倍数。
- `inbox` 定义了但**从未被调用**：各角色并没有真正"订阅、消费"任务板上的消息，编排器直接调用各个函数。任务板在这里只是一份**审计日志**，不是讲义所说的"agents subscribe to tags"的消息总线。
- 生产中任务板需要：持久化（文件或 Redis）、消息 ID、认领（claim）与确认（ack）、重试、幂等——讲义 Build It 第 3 步"each claims one subtask from the board"。

### 3.3 角色桩函数

```python
def architect_plan(issue: str, rng: random.Random) -> list[Subtask]:
    subs = [
        Subtask("parser", ["src/parser.py"]),
        Subtask("cache", ["src/cache.py", "src/cache_test.py"]),
        Subtask("api", ["src/api.py"]),
        Subtask("migration", ["src/migrate.py"]),
    ]
    subs[rng.randrange(len(subs))].has_bug = rng.random() < 0.3
    return subs
```

- 计划是固定的 4 个子任务（与讲义 Use It 的 parser、cache、api、migration 一致），`issue` 参数没有被使用。
- 子任务的文件集合互不相交——相当于天然满足讲义练习 3 的"单写者约束"，这也是后面能写"no conflict by construction"的原因。
- bug 注入：先随机挑一个子任务，再以 30% 概率给它标记 `has_bug`。这是讲义练习 1 "injected-bug probe" 的模拟。

```python
def reviewer_check(diffs: list[dict], rng: random.Random) -> tuple[bool, str]:
    buggy = [d for d in diffs if d["has_bug"]]
    if not buggy:
        return True, "lgtm"
    if rng.random() < 0.85:
        return False, f"found bug in {buggy[0]['subtask']}: please revisit"
    return True, "lgtm (FALSE-APPROVE)"


def tester_run(diffs: list[dict], rng: random.Random) -> tuple[bool, str]:
    buggy = [d for d in diffs if d["has_bug"]]
    if buggy:
        return False, f"test fails in {buggy[0]['subtask']} module"
    if rng.random() < 0.03:
        return False, "flaky test"
    return True, "412/412 passing"
```

- reviewer 的"能力"就是一个 85% 的捕获率，即条件 false-approval rate = 15%（讲义练习 1 的目标是 < 5%）。
- 没有 bug 时 reviewer 一定批准：**误拒绝率为 0**，这在真实系统中不成立。
- tester 对任何剩余 bug 都 100% 发现：测试成了完美的安全网，所以 false-approve 只会表现为"测试失败"，不会进入 PR。
- 测试 flake（3%）直接导致整次运行失败，没有重跑机制。

### 3.4 编排：`run_team` 的正常路径

```python
def run_team(issue: str, n_coders: int = 4, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random(0)
    board = Board()

    plan = architect_plan(issue, rng)
    board.post(Msg(MsgKind.PLAN_REQUEST, by="architect", to="board", ..., tokens=4500))

    for i, sub in enumerate(plan[:n_coders]):
        coder = f"coder-{chr(65 + i)}"
        board.post(Msg(MsgKind.SUBTASK, by="architect", to=coder, ..., tokens=1200))

    diffs: list[dict] = []
    for i, sub in enumerate(plan[:n_coders]):
        coder = f"coder-{chr(65 + i)}"
        result = coder_implement(sub, rng)
        diffs.append(result)
        board.post(Msg(MsgKind.DIFF_READY, by=coder, to="merge_coord",
                       payload=result, tokens=3200 + result["lines"] * 30))

    board.post(Msg(MsgKind.REVIEW_NEEDED, by="merge_coord", to="reviewer",
                   payload={"diffs": diffs}, tokens=2000))
```

- `rng = rng or random.Random(0)`：调用方不传随机数生成器时用种子 0 的默认值。注意不能把默认值写成参数默认值 `rng=random.Random(0)`——那样所有调用会共享同一个对象。
- `chr(65 + i)`：65 是 `'A'` 的 ASCII 码，生成 `coder-A`、`coder-B`……
- coder 的 token = `3200 + 行数 × 30`：改动越多，消息越大。
- "coders implement in parallel" 实际是**顺序的 for 循环**，没有墙钟时间模型，讲义评分表的"Parallel speedup"（20 分）无法测量。
- ⚠️ `plan[:n_coders]`：`n_coders < 4` 时多出的子任务被**静默丢弃**——既不分配也不报错。实测 `n_coders=2` 时只实现 parser 和 cache；如果 bug 在 api 或 migration，它根本不会出现在 diffs 里，评审和测试都"通过"。讲义练习 2 要求的是"一个 coder 顺序处理两个子任务"。
- merge 步骤只发了一条 `REVIEW_NEEDED`，注释写"no conflict by construction"——合并协调器的三方合并、LLM 调解都没有实现。

### 3.5 编排：评审拒绝后的修订分支

```python
    approved, comment = reviewer_check(diffs, rng)
    if approved:
        board.post(Msg(MsgKind.APPROVED, by="reviewer", to="tester", ..., tokens=1800))
    else:
        board.post(Msg(MsgKind.REVIEW_FEEDBACK, by="reviewer", to="coder-A",
                       payload={"comment": comment}, tokens=1800))
        board.post(Msg(MsgKind.DIFF_READY, by="coder-A", to="merge_coord",
                       payload={"subtask": "parser", "lines": 52, "has_bug": False},
                       tokens=3100))
        board.post(Msg(MsgKind.APPROVED, by="reviewer", to="tester",
                       payload={"comment": "now lgtm"}, tokens=1500))
        diffs = [{"subtask": d["subtask"], "lines": d["lines"], "has_bug": False}
                 for d in diffs]
```

这是全文件问题最集中的一段：

- ⚠️ **反馈总是发给 coder-A**（注释承认"simplified: first coder"），而不是负责出错子任务的 coder。10 次对比中的 `issue-1` 意见是 "found bug in migration"，migration 属于 coder-D，却由 coder-A 收到并"修复 parser"。讲义 Use It 中 cache 的意见正确地路由给了 coder-B。
- ⚠️ **修订 payload 是写死的**：永远是 parser、52 行、无 bug。
- ⚠️ **一键清零 bug**：列表推导式把所有 diff 的 `has_bug` 都改成 False，与谁修了什么无关。
- ⚠️ **没有重新评审**：reviewer 直接发 `"now lgtm"`，没有再调用 `reviewer_check`。修订一次必然成功，也没有修订次数上限。
- ⚠️ 讲义要求"reviewer 不能批准自己提议的改动"——这里 reviewer 恰恰批准了按自己意见修改后的 diff，规则没有被建模。

### 3.6 测试与返回值

```python
    passed, testmsg = tester_run(diffs, rng)
    if passed:
        board.post(Msg(MsgKind.TEST_PASSED, by="tester", to="pr_opener", ..., tokens=1200))
    else:
        board.post(Msg(MsgKind.TEST_FAILED, by="tester", to="coder-A", ..., tokens=1400))

    return {
        "approved": approved,
        ...
        "handoffs": sum(1 for m in board.messages if m.to != m.by),
    }
```

- 测试失败同样固定发给 coder-A，而且流程到此结束——讲义要求"Failed tests loop back to the coder owning the failing subtask"，这里没有回路。
- ⚠️ `approved` 返回的是**第一次**评审的结果。修订后最终是批准的，但返回 False；于是会出现"approved: False / tested_passed: True"的组合（10 次中的第 2、3、5 次），看起来像是绕过了评审。
- ⚠️ `handoffs` 的条件 `m.to != m.by` 对每条消息都成立，所以它就是消息总数，连 architect 发往 `"board"` 的那条也计入了。
- `to` 字段里出现的 `"board"`、`"merge_coord"`、`"pr_opener"` 不全是讲义的四个角色，`tokens_by_role` 里也因此出现了 `merge_coord`。

### 3.7 基线与对比实验

```python
def single_agent_baseline(issue: str, rng: random.Random) -> dict:
    return {
        "passed": rng.random() < 0.68,
        "total_tokens": 18_000 + rng.randint(0, 6_000),
    }
```

- 基线完全是随机桩：68% 通过、18k–24k token，与 issue 内容、团队的结果都无关。
- `main` 里所谓"matched trials"只是让两者用同一个 `issue-{i}` 名字和同一个 `rng2`，并没有在同一真实任务上对比。团队通过率的理论值 `0.7 × 0.97 + 0.3 × 0.85 × 0.97 ≈ 0.926` 高于基线的 0.68，"多 agent 更好"是写进参数里的。
- 放大倍数 `team_tok_sum / max(1, base_tok_sum)` 对应讲义 Key Terms 的定义；`max(1, ...)` 防止除零。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `Enum` 消息类型 | 类型安全、可序列化 | 应补齐 `rejected`、`replan_needed`；生产用 A2A 等协议定义 schema |
| 任务板只做日志 | 编排逻辑集中、易读 | agent 并未真正订阅；生产要有认领、ack、重试、持久化（JSONL/Redis） |
| token 记在发送方 | 实现简单 | 漏掉读上下文的输入 token，低估放大倍数；生产按每次 LLM 调用的 input/output 记账 |
| 固定 4 个文件不相交的子任务 | "无冲突"成立，免写合并器 | 无法测试 merge coordinator；真实计划需要动态生成并检测文件重叠 |
| 反馈固定发给 coder-A、修订写死 | 让流程能走通 | 路由错误、一键清零 bug、不重新评审；应按 owner 路由、局部修复、重新评审、限制修订轮数 |
| tester 必然发现剩余 bug | 简化 | 掩盖了 false-approve 的真实危害；讲义要单独测 false-approval rate |
| 顺序 for 循环模拟"并行" | 简单 | 无法测并行加速比；可用 `asyncio` 或墙钟模型 |
| 随机桩基线 | 不需要真实 agent | 对比结论只是参数之比；应在同一批 issue 上真实运行两套系统 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `Enum` | `class MsgKind(Enum): PLAN_REQUEST = "plan_request"` | 一组具名常量；`MsgKind.APPROVED.value == "approved"` |
| `@dataclass` + `field(default_factory=...)` | `payload: dict = field(default_factory=dict)` | 可变默认值必须用工厂函数 |
| `lambda` 作工厂 | `field(default_factory=lambda: defaultdict(int))` | 工厂需要参数时用 lambda 包一层 |
| `collections.defaultdict` | `defaultdict(int)` | 缺失的键自动初始化为 `int()` 即 0 |
| 联合类型 + 默认 None | `rng: random.Random | None = None` | 可选参数的标准写法 |
| `or` 提供默认对象 | `rng = rng or random.Random(0)` | 避免可变默认参数陷阱 |
| `random.Random` 方法 | `rng.randrange(len(subs))`、`rng.randint(15, 95)`、`rng.random()` | `randrange` 不含上界，`randint` 含上界 |
| 布尔表达式赋值 | `has_bug = rng.random() < 0.3` | 比较结果直接是 True/False |
| `chr` | `chr(65 + i)` | 码点转字符，65 → `'A'` |
| 切片 | `plan[:n_coders]` | 取前 n 个；超出长度不报错（这正是静默丢任务的原因） |
| `enumerate` | `for i, sub in enumerate(plan[:n_coders])` | 同时取下标和元素 |
| 元组返回 | `return False, f"found bug in ..."` | 调用方用 `approved, comment = ...` 解包 |
| 列表推导式 | `[d for d in diffs if d["has_bug"]]` | 过滤 |
| 字典推导/重建 | `[{"subtask": d["subtask"], ..., "has_bug": False} for d in diffs]` | 构造新字典列表 |
| 生成器 + `sum` | `sum(1 for m in board.messages if m.to != m.by)` | 计数惯用法 |
| `dict(...)` 转换 | `dict(board.tokens_by_role)` | 把 defaultdict 转成普通 dict 返回 |
| f-string 格式符 | `{n:>6,}`、`{x:,.0f}`、`{r:.2f}x`、`{role:14s}` | 右对齐 + 千分位、千分位无小数、两位小数、左对齐 |
| f-string 中的嵌套引号 | `f"found bug in {buggy[0]['subtask']}"` | 外层双引号、内层单引号 |
| `if __name__ == "__main__":` | 文件结尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`）：

```text
=== multi-agent team run ===
approved     : True  (lgtm)
tested passed: True  (412/412 passing)
handoffs     : 12
total tokens : 35,530
tokens by role:
  architect       9,300      ← 4,500 + 4 × 1,200
  coder-C         5,900      ← 3,200 + 90 行 × 30
  coder-B         5,600      ← 80 行
  coder-A         5,360      ← 72 行
  coder-D         4,370      ← 39 行
  merge_coord     2,000
  reviewer        1,800
  tester          1,200

=== 10 matched trials vs single-agent baseline ===
team pass    : 7/10   tokens/run: 34,819
baseline pass: 5/10   tokens/run: 21,705
token amplification: 1.60x
```

逐项解读：

- **第一次运行**：这次没有注入 bug（或注入概率未命中），reviewer 直接批准，测试通过。12 条消息 = 1 + 4 + 4 + 1 + 1 + 1。总 token 35,530 是 8 个"角色"发出的消息之和。
- **10 次对比的逐次明细**（额外的实测脚本复现）：

| 试验 | 评审 | 测试 | 团队 token | handoffs | 基线通过 |
|---|---|---|---|---|---|
| 0 | lgtm | 通过 | 34,120 | 12 | 是 |
| 1 | found bug in **migration** | 通过 | 39,110 | 14 | 是 |
| 2 | found bug in **cache** | 通过 | 37,520 | 14 | 否 |
| 3 | lgtm | 通过 | 33,730 | 12 | 是 |
| 4 | found bug in **migration** | 通过 | 38,660 | 14 | 否 |
| 5 | lgtm | 通过 | 31,930 | 12 | 否 |
| 6 | lgtm | 通过 | 33,550 | 12 | 是 |
| 7 | lgtm | flaky test | 31,890 | 12 | 否 |
| 8 | lgtm | flaky test | 33,390 | 12 | 是 |
| 9 | lgtm (FALSE-APPROVE) | test fails in migration | 34,290 | 12 | 否 |

  - 试验 1、2、4 的 bug 分别在 migration、cache、migration，但反馈都发给了 coder-A；修订后 bug 被"一键清零"，测试全部通过。这三次返回的 `approved` 都是 False。
  - 试验 7、8 是 3% 的 flake 恰好连续出现两次——样本小时的正常波动。
  - 试验 9 是 reviewer 漏检、tester 兜底。
- **团队 7/10 vs 基线 5/10**：理论值分别是 92.6% 和 68%，10 次的结果离理论值都很远。20,000 次实测：团队 0.928、基线 0.675、放大 1.66x、false-approve 发生率 0.044（= 0.3 × 0.15）。
- **放大 1.60x**：远低于讲义"40 轮变 160 轮"的 4x，因为代码只统计消息 token，基线 token 又是随机常数。

---

## 7. 动手改一改

1. **修正返回值**：让 `run_team` 返回 `initial_approved`、`final_approved`、`revisions`，并让 `handoffs` 只统计两端都是角色的消息（排除 `"board"`、`"pr_opener"`）。
2. **按 owner 路由反馈**：建立 `owner = {子任务名: coder}`，评审意见和测试失败都发给负责的 coder；只修复出错的子任务；修复后重新调用 `reviewer_check`，最多 3 轮（参考测验 Q9）。
3. **不丢子任务**（讲义练习 2）：用 `i % n_coders` 轮转分配，加上墙钟模型（同一 coder 串行、不同 coder 并行），输出 `n_coders = 1, 2, 4` 的墙钟与通过率。
4. **让 reviewer 真正有误判**：加入 5% 的误拒绝率；把 tester 的 bug 发现率改为 70%，统计"带 bug 的 PR 被开出"的比例，体会为什么讲义要单独测 false-approval。
5. **按输入输出记账**：给 `Msg` 加 `input_tokens`、`output_tokens`，reviewer 的输入 = 所有 diff 的 token 之和，重新计算放大倍数；再按讲义 Build It 第 7 步的公式算每个子任务的放大倍数（参考测验 Q12）。
6. **进阶**：用 `asyncio` 把 4 个 coder 改成真正的并发任务，任务板改成 `asyncio.Queue`，各角色只通过 `inbox`/队列消费消息，不再由编排器直接调用函数。

---

## 8. 常见坑

- **反馈路由写死**：把意见发给错误的 coder，会出现"别人改了代码、你的 bug 被标记为已修复"的假象。
- **修订后不重新评审**：等于 reviewer 预先批准了一个它没看过的 diff。
- **用切片分配任务**：`plan[:n_coders]` 不会报错，只会悄悄丢掉任务；计划中的子任务集合应与完成的子任务集合做断言比对。
- **返回首次评审结果**：状态字段要区分"初次"与"最终"，否则报表会误导。
- **handoff 计数口径**：`to != by` 在这里恒为真；统计前先定义清楚"什么算跨角色"。
- **只记输出 token**：多 agent 的主要开销是每个角色重复阅读上下文，只记消息大小会严重低估成本。
- **用完美 tester 兜底**：会让 reviewer 的质量问题被掩盖；false-approval 必须单独测。
- **小样本对比**：10 次试验的 7/10 vs 5/10 不能说明任何问题，基线还是随机桩。
