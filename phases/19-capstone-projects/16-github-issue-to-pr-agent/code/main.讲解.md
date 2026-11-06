# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 16 节 综合项目 16：从 GitHub Issue 到 PR 的自主 Agent ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`time`、`collections`、`dataclasses`、`enum`），不连接 GitHub、不启动沙箱、不调用 LLM

---

## 1. 这份代码在考察什么

讲义的完整系统包括 GitHub App、Lambda webhook 接收、SQS、ECS Fargate、Daytona/E2B 沙箱、mini-swe-agent 循环、沙箱内 CI 与覆盖率闸门、Langfuse trace。`main.py` 的 docstring 说明它只实现其中的"控制面"：

> "The hard architectural primitive is the dispatcher that enforces per-repo budgets, scoped GitHub App credentials, and a sandbox lifecycle that never lets the agent force-push or escape the repo scope. This scaffold implements the dispatcher, budget ledger, sandbox state machine, and verification gates."

对应讲义的核心概念：

1. **按 repo 按天的预算**（金额 + PR 数），在 dispatcher 处、任务开始前执行；
2. **短时、有作用域的 installation token**，以及"永不 force-push"的硬策略；
3. **沙箱状态机** CLONE → INFER → AGENT → VERIFY → PR → DONE/FAILED；
4. **agent 循环的硬上限**（轮数、金额、墙钟时间）；
5. **验证闸门**：CI 必须绿、覆盖率检查。

agent 本身是概率模拟：每轮以一定概率"修好"，难度越高概率越低、每轮越贵越慢。

> 一句话：**用一个可复现的随机模拟把"预算 → 签发凭据 → 状态机 → 上限 → 验证 → 开 PR"这条控制链跑通**。但要注意：token 权限检查是"默认允许"、两个上限永远不会触发、覆盖率闸门与讲义相反、预算没有真正预留——这些正是讲义所说"hard parts"的反面教材。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Task` | dataclass | 一个待处理 issue：id、repo、编号、标题、创建时间 | webhook 入队的任务 |
| `BudgetLedger` | dataclass | `permit` 预算检查、`record` 记账 | 按 repo 按天的预算 |
| `InstallationToken` | dataclass | `mint` 签发 1 小时 token、`can` 动作检查 | GitHub App 凭据 |
| `SState` | Enum | 7 个沙箱状态 | 沙箱生命周期 |
| `SandboxRun` | dataclass | 一次运行的状态、轮数、花费、耗时、CI、覆盖率、失败原因、trace | 运行记录 |
| `run_agent` | 函数 | 逐轮模拟 agent，检查三个上限 | agent 循环 + 硬上限 |
| `run_verify` | 函数 | 5% flaky、高斯覆盖率差值 | 验证闸门 |
| `open_pr` | 函数 | 检查 token 过期与权限后"开 PR" | PR 发布 |
| `dispatch` | 函数 | 难度抽样 → 预算 → 签发 token → 状态机 → 记账 | dispatcher |
| `main` | 函数 | 3 个 repo、20 个任务，打印统计 | 演示 |

数据流：`main` 生成 `Task` → `dispatch`：`ledger.permit` →（拒绝则直接 FAILED）→ `InstallationToken.mint` → `SandboxRun`（CLONE → INFER）→ `run_agent`（AGENT → VERIFY 或 FAILED）→ `run_verify`（→ PR 或 FAILED）→ `open_pr`（→ DONE 或 FAILED）→ `ledger.record` → 汇总打印。

---

## 3. 逐段精讲

### 3.1 `Task`：入队契约

```python
@dataclass
class Task:
    task_id: int
    repo: str
    issue_num: int
    title: str
    created_at: float = field(default_factory=time.time)
```

- 对应讲义第 2 步 webhook 接收器入队 SQS 的消息体。真实消息还应带 issue 正文、触发者、安装 ID、webhook delivery ID（用于去重）。
- `field(default_factory=time.time)`：每次创建时调用 `time.time()`；如果写成 `created_at: float = time.time()`，所有实例会共享模块加载那一刻的时间。
- `title` 与 `created_at` 在后续逻辑中都没有被使用。
- Python 版本没有验证 webhook 签名；同目录的 TS 版本 `verify.ts` 用 HMAC-SHA256 + `timingSafeEqual` 校验 `sha256=...` 签名头，这是接收端的第一道门。

### 3.2 `BudgetLedger`：预算账本

```python
@dataclass
class BudgetLedger:
    daily_dollar_cap: float = 50.0
    daily_pr_cap: int = 5
    per_task_dollar_cap: float = 20.0
    spent_today: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    prs_today: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def permit(self, repo: str, estimated_cost: float) -> tuple[bool, str]:
        if estimated_cost > self.per_task_dollar_cap:
            return False, f"task estimate ${estimated_cost:.2f} > cap ${self.per_task_dollar_cap}"
        worst_case = self.per_task_dollar_cap
        if self.spent_today[repo] + worst_case > self.daily_dollar_cap:
            return False, f"daily $ cap for {repo} would be exceeded"
        if self.prs_today[repo] >= self.daily_pr_cap:
            return False, f"daily PR cap ({self.daily_pr_cap}) for {repo} reached"
        return True, "ok"

    def record(self, repo: str, spent: float, opened_pr: bool) -> None:
        self.spent_today[repo] += spent
        if opened_pr:
            self.prs_today[repo] += 1
```

- 三道检查：单任务预估 ≤ $20；"已花 + 最坏情况 $20" ≤ 日上限 $50；今日 PR 数 < 5。与讲义示例 "max 5 PRs per repo per day, $20 per PR" 一致。
- **按最坏情况判断**：注释解释，agent 循环允许花到单任务上限，若按预估放行，一串"撞上限"的任务可能突破日预算。代价是保守：已花超过 $30 后任何任务都会被拒。
- `record` 在任务结束后写入**实际**花费（失败的任务也要记账，这是对的）；PR 数只在真正开出 PR 时 +1。
- `field(default_factory=lambda: defaultdict(float))`：每个实例一个新的 `defaultdict`，访问不存在的 repo 自动得到 0。注解写的是 `dict[str, float]`，实际类型是它的子类 `defaultdict`。
- ⚠️ **并没有真正"预留"**：`permit` 只做判断、不扣减任何额度。顺序执行时与预留等价；多个 worker 并发时，多个任务会同时看到同样的余额而全部放行（例如已花 $25 时三个并发任务都满足 `25 + 20 ≤ 50`，最坏总花费 $85）。
- ⚠️ **没有"天"的概念**：`spent_today` 永不清零，进程重启则全部归零。生产中应以 `repo + UTC 日期` 为键存放在共享存储，并用原子的 reserve / commit / release（见测验 Q11）。
- ⚠️ 单任务预估 `2 + 8 × difficulty` 最多 $9.36，第一道检查在本演示中永远不会触发。

### 3.3 `InstallationToken`：凭据与动作策略

```python
@dataclass
class InstallationToken:
    repo: str
    expires_at: float
    permissions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def mint(cls, repo: str) -> "InstallationToken":
        return cls(repo=repo,
                   expires_at=time.time() + 3600,
                   permissions={"issues": "rw", "pull_requests": "rw",
                                "contents": "rw", "workflows": "r"})

    def can(self, action: str) -> bool:
        if action == "force_push":
            return False
        if action.startswith("write:main"):
            return False
        return True
```

- `mint`：每个任务签发一个 1 小时有效、绑定单个 repo 的 token，权限与讲义第 1 步一致（issues 读写、PR 写、contents 读写、workflows 只读）。
- 返回类型写成字符串 `"InstallationToken"`（前向引用）；文件已有 `from __future__ import annotations`，不加引号也可以。
- ⚠️ **默认允许**：`can` 只拦截两种字符串，`permissions` 从未被读取。实测 `push:main`、`delete_repo`、`admin:settings`、`write:.github/workflows/ci.yml` 全部返回 `True`。正确的做法是"默认拒绝 + 动作到权限的白名单映射"，并对 diff 做 `.github/workflows/` 路径检查（讲义："The worker enforces 'no writes under `.github/workflows`' as an allow-list check on the proposed diff"）。
- 讲义强调"no force-push / no direct write to main"真正靠的是**分支保护**，而不是这里的 `can`。worker 的检查是纵深防御的一层，不能代替服务端规则。

### 3.4 状态机与运行记录

```python
class SState(Enum):
    CLONE = auto()
    INFER = auto()
    AGENT = auto()
    VERIFY = auto()
    PR = auto()
    DONE = auto()
    FAILED = auto()


@dataclass
class SandboxRun:
    task: Task
    state: SState = SState.CLONE
    turns: int = 0
    dollars: float = 0.0
    wall_min: float = 0.0
    coverage_delta: float = 0.0
    ci_green: bool = False
    pr_opened: bool = False
    failure: str | None = None
    trace: list[str] = field(default_factory=list)
```

- `Enum` + `auto()`：自动分配值，比字符串常量更安全（拼错名字会直接报错）。
- 状态机是**线性**的：每个阶段只会前进到下一阶段或 FAILED，没有回退；真实系统中验证失败后通常回到 AGENT 再试几轮。
- `failure` 存失败原因字符串，`trace` 存文本日志（每轮一条），但 `main` 从不打印 trace——讲义要求 trace 归档并在 PR 正文中给出链接。
- 没有 `labels` 字段，因此无法表达讲义要求的 `needs-review` 标签。

### 3.5 `run_agent`：agent 循环与硬上限

```python
def run_agent(run, difficulty, rng, turn_cap=20, dollar_cap=20.0, minute_cap=30.0) -> None:
    run.state = SState.AGENT
    per_turn_p = max(0.05, 0.35 * (1 - difficulty))
    per_turn_min = 0.9 + difficulty * 0.6
    per_turn_usd = 0.25 + difficulty * 0.45

    while True:
        run.turns += 1
        run.wall_min += per_turn_min
        run.dollars += per_turn_usd
        run.trace.append(f"turn {run.turns}: $={run.dollars:.2f}")

        if run.turns >= turn_cap:
            run.failure = "turn_cap"; run.state = SState.FAILED; return
        if run.dollars >= dollar_cap:
            run.failure = "dollar_cap"; run.state = SState.FAILED; return
        if run.wall_min >= minute_cap:
            run.failure = "minute_cap"; run.state = SState.FAILED; return

        if rng.random() < per_turn_p:
            run.state = SState.VERIFY
            return
```

- 难度模型：每轮成功概率 `0.35 × (1 − d)`（下限 0.05），每轮耗时 `0.9 + 0.6d` 分钟、花费 `0.25 + 0.45d` 美元。难度 `d` 由 dispatcher 在 `[0.3, 0.92]` 均匀抽取。
- 每轮先"花钱花时间"、再查上限、最后掷骰子判断是否修好。
- ⚠️ **两个上限是死代码**：最难时每轮 $0.664、1.452 分钟，20 轮累计 $13.28、29.04 分钟，永远到不了 $20 和 30 分钟；只有 `turn_cap` 会触发。
- ⚠️ **第 20 轮没有成功机会**：上限检查在掷骰子之前，`turn_cap=20` 实际只给 19 次尝试，第 20 轮的花费白白计入。
- ⚠️ 讲义的硬上限是 "$20 cost, 30 min wall-clock, 30 agent turns"，代码轮数上限是 20。
- 触发 `turn_cap` 的概率为 `(1 − p)^19`：d = 0.5 时约 0.026，d = 0.92 时约 0.377（已计算）。
- 改进写法：每轮开始前检查"再做一轮是否会超过任一上限"，超了就停（见测验 Q10）。

### 3.6 `run_verify` 与 `open_pr`

```python
def run_verify(run, difficulty, rng) -> None:
    flake = rng.random() < 0.05
    if flake:
        run.ci_green = False
        run.failure = "flaky_test"
        run.state = SState.FAILED
        return
    run.ci_green = True
    run.coverage_delta = rng.gauss(0.0, 0.6)
    if run.coverage_delta < -2.0:
        run.failure = "coverage_regression"
        run.state = SState.FAILED
        return
    run.state = SState.PR
```

- CI 红 → 不开 PR：符合 hard reject "PRs opened without the full CI having passed in-sandbox"。
- ⚠️ **flaky 不重跑**：讲义说 flaky tests "must be re-run or isolated"，这里 5% 概率直接判失败。
- ⚠️ **覆盖率闸门与讲义相反**：讲义是"下降超 2% 仍开 PR、打 `needs-review`"，代码是直接失败。而且 `N(0, 0.6)` 低于 −2.0 的概率只有约 0.04%，演示中几乎不会走到这个分支。
- `difficulty` 参数没有被使用（难的任务并不更容易让 CI 失败）。

```python
def open_pr(run, token) -> None:
    # Explicit runtime checks -- never use `assert` for a safety gate. `python -O`
    # strips asserts, which would let a denied or expired token still open a PR.
    if time.time() >= token.expires_at:
        run.failure = "token_expired"
        run.state = SState.FAILED
        return
    if not token.can("pull_request.open"):
        run.failure = "policy_denied"
        run.state = SState.FAILED
        return
    run.pr_opened = True
    run.state = SState.DONE
```

- 注释是一条重要的工程经验：**安全检查不要用 `assert`**，`python -O` 会移除所有 `assert` 语句。
- 开 PR 前再次检查 token 过期——长任务（讲义允许 30 分钟）可能用掉 token 的大部分有效期；生产中应在推送前按需刷新 token，而不是让任务失败。
- ⚠️ 由于 `can` 默认允许，`policy_denied` 分支永远不会触发。
- 真实的 `open_pr` 还要推送分支、填写 PR 正文（rationale、diff 摘要、trace URL、成本、轮数）、加标签。

### 3.7 `dispatch` 与 `main`

```python
def dispatch(task, ledger, rng) -> SandboxRun:
    difficulty = rng.uniform(0.3, 0.92)
    estimated = 2.0 + difficulty * 8.0
    allowed, reason = ledger.permit(task.repo, estimated)
    if not allowed:
        run = SandboxRun(task)
        run.failure = f"dispatcher: {reason}"
        run.state = SState.FAILED
        return run

    token = InstallationToken.mint(task.repo)
    run = SandboxRun(task)
    run.trace.append("state: CLONE")
    run.state = SState.INFER
    run.trace.append("state: INFER (dockerfile synthesized)")
    run_agent(run, difficulty, rng)
    if run.state == SState.VERIFY:
        run_verify(run, difficulty, rng)
    if run.state == SState.PR:
        open_pr(run, token)
    ledger.record(task.repo, run.dollars, run.pr_opened)
    return run
```

- **预算在签发 token 之前检查**：被拒的任务既不消耗凭据也不启动沙箱——符合 hard reject "Dispatchers that skip budget checks"。
- 被拒任务不调用 `record`（花费为 0，合理）。
- 用一串 `if run.state == ...` 推进状态机：任何一步失败，后续 `if` 都不成立，自然短路。
- CLONE 与 INFER 只写了 trace，没有任何失败模拟；讲义交付物恰恰要求总结"top three build-inference failures"，环境推断是真实系统中最容易失败的环节之一。
- 难度在 dispatcher 中抽样，现实中 dispatcher 并不知道任务难度；这里是为了让模拟可控。

`main` 用 `random.Random(9)` 在 3 个 repo 上分发 20 个任务，打印开出的 PR 数、失败数、失败原因（按次数降序）、每个 repo 的花费与 PR 数，以及成功任务的平均花费与轮数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 预算在 dispatcher、签发凭据前检查 | 被拒任务零成本 | 需要原子预留与按日分桶的共享存储 |
| 按单任务上限的最坏情况判断日预算 | 防止一串撞上限的任务超支 | 偏保守；且未真正预留，并发下失效 |
| 每任务签发 1 小时 token | 最小化泄露窗口 | 长任务需在推送前刷新 token |
| `can` 黑名单式检查 | 代码短 | 默认允许是反模式；生产用白名单 + diff 路径检查 + 服务端分支保护 |
| 线性状态机 | 易读、易测 | 验证失败无法回到 AGENT 修复；生产常允许有限次回退 |
| 先花费后检查上限 | 写法直观 | 上限会被"超过一轮"、最后一轮无效；应先检查再执行 |
| 概率化 agent | 无需 LLM 即可观察控制面行为 | 不能评估真实通过率与 PR 质量 |
| flaky 即失败、覆盖率回退即失败 | 简化 | 与讲义不一致；应重跑分类、覆盖率回退打 `needs-review` |
| `assert` 改为显式检查 | `python -O` 会移除 assert | 正确做法，值得保留 |
| 固定种子 `random.Random(9)` | 结果可复现 | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许 `str \| None`、`tuple[bool, str]` 等注解 |
| `@dataclass` | `Task`、`BudgetLedger`、`InstallationToken`、`SandboxRun` | 自动生成 `__init__` 等方法 |
| `field(default_factory=...)` | `field(default_factory=time.time)`、`field(default_factory=list)` | 每个实例单独求默认值 |
| `lambda` 作为工厂 | `field(default_factory=lambda: defaultdict(float))` | 需要带参数构造时包一层 lambda |
| `defaultdict` | `defaultdict(float)`、`defaultdict(int)` | 缺失键自动初始化为 0.0 / 0 |
| `@classmethod` + 前向引用 | `def mint(cls, repo) -> "InstallationToken"` | 工厂方法；字符串注解引用尚未定义完的类 |
| `str.startswith` | `action.startswith("write:main")` | 前缀判断（本例中被当作权限检查，很脆弱） |
| `Enum` + `auto()` | `class SState(Enum): CLONE = auto()` | 枚举类型，值自动编号；比较用 `run.state == SState.VERIFY` |
| 可选类型 | `failure: str \| None = None` | 可能为空的字段 |
| `while True` + `return` | `run_agent` 中 | 无限循环，靠内部 return 退出 |
| 原地累加 | `run.turns += 1`、`self.spent_today[repo] += spent` | 修改对象属性 / 字典值 |
| 独立随机数生成器 | `random.Random(9)`、`rng.uniform`、`rng.gauss`、`rng.choice` | 可复现的均匀分布、正态分布、随机选择 |
| 元组返回 + 解包 | `allowed, reason = ledger.permit(...)` | 判定结果与原因一起返回 |
| f-string 格式符 | `${estimated_cost:.2f}`、`{reason:24s}`、`{repo:20s}` | 美元两位小数、左对齐定宽 |
| 生成器 + `sum` | `sum(1 for r in runs if r.pr_opened)` | 计数满足条件的元素 |
| `sorted` + `key` | `sorted(reasons.items(), key=lambda x: -x[1])` | 按次数降序 |
| 显式检查而非 `assert` | `open_pr` 中的注释与 `if` | `python -O` 会删除 assert，安全闸门不能依赖它 |
| 未使用的导入 | `asdict` | 导入了但没用到，可以删掉 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行演示 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，瞬间完成，结果确定）：

```text
=== dispatch result (20 tasks) ===
PRs opened : 13
failed     : 7

failure reasons:
  dispatcher: daily PR cap (5) for acme/widget reached 4
  dispatcher: daily PR cap (5) for acme/service reached 3

budget summary:
  acme/widget          spent=$14.89  PRs=5
  acme/service         spent=$12.35  PRs=5
  acme/library         spent=$14.38  PRs=3

pass set: mean $/PR = $3.20  mean turns = 5.7
```

我们用自写脚本复现同一随机序列，逐任务追踪（节选）：

| 任务 | repo | 结果 | 轮数 | 花费 | 覆盖率差值 |
|-----|------|------|-----|------|-----------|
| 0 | acme/service | DONE | 16 | $8.90 | +1.27 |
| 1 | acme/widget | DONE | 16 | $9.62 | −1.33 |
| 3 | acme/service | DONE | 1 | $0.39 | +1.11 |
| 13 | acme/library | DONE | 16 | $9.76 | +0.68 |
| 12, 14, 15, 18 | acme/widget | dispatcher 拒绝 | 0 | $0 | — |
| 16, 17, 19 | acme/service | dispatcher 拒绝 | 0 | $0 | — |

逐项解读：

- **13 个真正运行的任务全部成功**：没有一个触发轮数上限、flaky 或覆盖率回退。7 次失败**全部**来自 dispatcher 的每日 PR 上限——前 12 个任务里 `acme/widget` 与 `acme/service` 各开满了 5 个 PR。
- **日金额上限从未触发**：花费最多的 `acme/widget` 也只有 $14.89，离"$30 后拒绝"还很远。演示只展示了 PR 数上限这一种预算拦截。
- **平均 $3.20 / PR、5.7 轮**：受少数 16 轮的"难任务"拉高；多数任务 1～5 轮就成功。对比讲义 Use It 示例的 "Turns: 7 Cost: $1.80"，量级相近。
- **覆盖率差值**有正有负（如 −1.33），但都在 −2.0 以内，所以 `coverage_regression` 分支从未执行；按讲义，这些任务即便越过阈值也应开 PR 并打 `needs-review`。
- 额外验证：`InstallationToken.mint(...).can(...)` 对 `push:main`、`delete_repo`、`admin:settings`、`write:.github/workflows/ci.yml` 均返回 `True`，只有 `force_push`、`write:main` 返回 `False`。

---

## 7. 动手改一改

1. **默认拒绝的 token 策略**：按测验 Q9 改写 `can`，并加入 `check_diff_paths`；在 `dispatch` 中模拟 agent 的 diff（随机生成文件列表，偶尔包含 `.github/workflows/ci.yml`），被拒时 FAILED 为 `policy_denied`。
2. **修正 agent 上限**：把 `turn_cap` 改为讲义的 30，改成"先检查再执行"的循环；再把每轮花费调高（如 `0.5 + 1.2d`），确认 `dollar_cap` 与 `minute_cap` 都能被触发，并统计三种失败的比例。
3. **按讲义重写验证闸门**：失败测试重跑 2 次以区分 flaky；覆盖率下降超 2% 时开 PR 并加 `needs-review` 标签（给 `SandboxRun` 增加 `labels`、`flaky_tests` 字段）。
4. **真正的预算预留**：实现带 UTC 日期键的 `reserve / commit / release`；用 `concurrent.futures.ThreadPoolExecutor` 并发分发 20 个任务，对比原实现与新实现在并发下是否超支（原实现需加锁才能观察到确定结果）。
5. **讲义练习 3——成本看板**：按 repo、按用户统计当日花费与 PR 数，花费超过最近 7 天均值 3 倍时打印告警。
6. **讲义练习 4——dry-run 模式**：增加 `mode="dry_run"`，跳过 VERIFY 直接开 draft PR，并在预算中按更低的上限计费；比较两种模式的成本。

---

## 8. 常见坑

- **用黑名单做权限检查**：新动作默认被允许；必须"默认拒绝 + 白名单"。
- **把 worker 侧检查当成唯一防线**：force-push、写 main 必须由分支保护在服务端强制，App 不进 bypass 名单。
- **以为 App 权限能按路径限制**：讲义明确说不能；`.github/workflows` 的保护要靠 worker 检查 diff。
- **先花钱再查上限**：上限会被突破一轮，最后一轮浪费；先检查再执行。
- **上限参数之间不协调**：本代码的金额与时间上限永远到不了，等于没有。设置上限后要验证它们确实可能触发。
- **预算"检查"不等于"预留"**：并发 worker 下必须原子预留。
- **预算没有日期维度**：要么永不清零，要么重启清零。
- **flaky 一次失败就判死**：先重跑分类，再决定。
- **覆盖率回退直接丢弃结果**：讲义要求开 PR 并标记 `needs-review`，把判断交给人。
- **安全闸门用 `assert`**：`python -O` 会删除它们（本文件的注释已提醒）。
- **自动重试失败任务**：交付物拒绝规则要求人工重新打标签。
- **日志里留 token**：hard reject 要求 trace 归档脱敏。
