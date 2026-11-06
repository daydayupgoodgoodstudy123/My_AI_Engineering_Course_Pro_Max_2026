# 测验 · 综合项目 16：从 GitHub Issue 到 PR 的自主 Agent（Capstone 16 — GitHub Issue-to-PR Autonomous Agent）

> **阶段 19 · 综合项目 · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 异步云端 coding agent | 与交互式 coding agent（综合项目 01）是不同品类：UX 是一个 GitHub 标签，worker 在云沙箱里克隆、测试、改代码、验证、开 PR，没有终端交互 |
| 2 | 端到端链路 | webhook（issue 标签 / PR 评论）→ Lambda 接收 → SQS → dispatcher（预算）→ ECS Fargate 任务 + Daytona/E2B 沙箱 → 环境推断 → agent 循环 → 沙箱内全量 CI + 覆盖率 → 推分支、开 PR |
| 3 | 凭据作用域 | GitHub App 的短时 installation token：issues 读写、pull_requests 写、contents 读写、workflows 只读；不用长期个人 token |
| 4 | 两个不同的安全面 | "禁止直接写 main、禁止 force-push"由**分支保护**强制（App 不在 bypass 名单）；"不改 `.github/workflows`"必须由 worker 对 diff 做路径白名单检查，因为 App 权限不能按路径划分 |
| 5 | 预算 | dispatcher 处按 repo 按天限额（讲义示例：每 repo 每天最多 5 个 PR、每个 PR $20）；agent 循环硬上限：$20、30 分钟、30 轮 |
| 6 | 验证闸门 | 沙箱内全量 CI 必须通过才开 PR；覆盖率下降超过 2% 时**仍开 PR** 但打 `needs-review` 标签；flaky test 要重跑或隔离 |
| 7 | 环境推断 | 识别语言（Python/Node/Go/Rust）与包管理器（uv/pnpm/go mod/cargo），没有 Dockerfile 时即时生成 |
| 8 | 凭据卫生与可观测 | 日志归档前脱敏；PR 正文包含 rationale、diff 摘要、trace URL、成本、轮数；trace 归档不得含未脱敏 token 或 PII |
| 9 | 评测 | 30 个预置 issue，测通过率、PR 质量、成本、延迟，并与 Cursor Background Agents、AWS Remote SWE Agents 对比 |
| 10 | 本节代码的简化与偏差 | 只有 dispatcher、预算账本、状态机与验证闸门的模拟；覆盖率闸门、轮数上限与讲义不一致；token 权限检查是"默认允许" |

### 核心技能（能动手做到）

- [ ] 画出从 webhook 到 PR 的完整链路，说出每一步的失败模式与对应闸门
- [ ] 区分"GitHub App 权限""分支保护""worker 侧 diff 白名单"三者各自能管什么、不能管什么
- [ ] 把 `InstallationToken.can` 改成"默认拒绝 + 显式白名单"，并补上 `.github/workflows` 路径检查
- [ ] 推算本节 `run_agent` 中各个上限是否真的可能触发，并修正检查顺序
- [ ] 实现带日期键、预留/提交/释放语义的预算账本，说明并发 worker 下为什么必须"预留"
- [ ] 按讲义实现验证闸门：CI 红则停止、覆盖率下降超 2% 打 `needs-review`、flaky test 重跑分类

---

## 二、基础自测（选择题）

**Q1.** 讲义中"agent 永远不能 force-push、不能直接写 `main`"是靠什么强制的？

- A. GitHub App 的 `contents: read` 权限
- B. 在 agent 的系统提示词里写"不要 force-push"
- C. 仓库的分支保护规则，且 App 不在 bypass 名单中
- D. 把 `.github/workflows` 设为只读路径权限

**Q2.** 关于覆盖率闸门，讲义与本节代码的行为分别是：

- A. 讲义：覆盖率下降超过 2% 时仍开 PR 但打 `needs-review` 标签；代码：`coverage_delta < -2.0` 直接 FAILED（`coverage_regression`），不开 PR
- B. 两者一致：覆盖率下降超过 2% 都不开 PR
- C. 讲义：覆盖率下降就拒绝；代码：覆盖率下降仍开 PR
- D. 两者都不检查覆盖率

**Q3.** 在本节 `run_agent` 的参数下（`difficulty ∈ [0.3, 0.92]`，`turn_cap=20`，`dollar_cap=20.0`，`minute_cap=30.0`），哪些上限**实际可能**触发？

- A. 三个上限都可能触发
- B. 只有 `dollar_cap`
- C. 只有 `minute_cap`
- D. 只有 `turn_cap`；20 轮内花费最多 $13.28、耗时最多 29.04 分钟，另外两个上限永远到不了

**Q4.** `InstallationToken.mint("acme/widget").can("push:main")` 的返回值是：

- A. `False`，因为 main 分支受保护
- B. `True`，因为 `can` 只拒绝 `force_push` 和以 `write:main` 开头的动作，其余一律放行
- C. 抛出 `KeyError`
- D. `False`，因为 `permissions` 里 contents 不是 `"rw"`

**Q5.** `BudgetLedger` 默认 `daily_dollar_cap=50`、`per_task_dollar_cap=20`。某 repo 今天已花费 $31，新任务预估 $3。`permit` 的结果是：

- A. 拒绝，因为按最坏情况预留 $20：`31 + 20 = 51 > 50`
- B. 放行，因为 `31 + 3 = 34 < 50`
- C. 拒绝，因为单任务预估超过上限
- D. 放行，但会扣减 PR 配额

**Q6.** 讲义为什么要求 worker 使用 GitHub App 的**短时** installation token？

- A. 因为个人 token 无法调用 GitHub API
- B. 因为 installation token 可以绕过分支保护
- C. 因为 installation token 不需要任何权限配置
- D. 它是有细粒度权限、短时间过期的"受限机器人身份"，即使沙箱中的 token 泄露，影响范围和时间窗口都有限

**Q7.** 运行 `main.py`（种子 9，20 个任务）的结果是"PRs opened: 13，failed: 7"。7 次失败的原因是：

- A. 全部是 `turn_cap`
- B. 4 次 flaky test、3 次覆盖率回退
- C. 全部是 dispatcher 拒绝：`acme/widget` 4 次、`acme/service` 3 次达到每天 5 个 PR 的上限
- D. 全部是 token 过期

**Q8.** 交付物 `skill-issue-to-pr.md` 对失败任务的重试有什么规定？

- A. 失败后立即自动重试 3 次
- B. 拒绝自动重试；所有重试都需要人工重新打标签触发
- C. 只有 flaky test 可以自动重试
- D. 失败的任务直接关闭对应 issue

---

## 三、动手 / 代码题

**Q9.** 阅读 `InstallationToken`：

```python
    @classmethod
    def mint(cls, repo: str) -> "InstallationToken":
        return cls(repo=repo,
                   expires_at=time.time() + 3600,
                   permissions={"issues": "rw", "pull_requests": "rw",
                                "contents": "rw", "workflows": "r"})

    def can(self, action: str) -> bool:
        # hard policy: never force-push
        if action == "force_push":
            return False
        if action.startswith("write:main"):
            return False
        return True
```

1. 实测 `can` 对 `"write:.github/workflows/ci.yml"`、`"delete_repo"`、`"admin:settings"`、`"push:main"` 分别返回什么？`permissions` 字段在哪里被用到？
2. 把它改成"默认拒绝"：动作必须能映射到 `permissions` 中的某个权限且级别足够；另写一个 `check_diff_paths(changed_files)`，拒绝任何 `.github/workflows/` 下的改动。
3. 即使 worker 里的 `can` 写对了，为什么讲义仍要求分支保护？

**Q10.** 阅读 `run_agent`：

```python
    per_turn_p = max(0.05, 0.35 * (1 - difficulty))
    per_turn_min = 0.9 + difficulty * 0.6
    per_turn_usd = 0.25 + difficulty * 0.45

    while True:
        run.turns += 1
        run.wall_min += per_turn_min
        run.dollars += per_turn_usd
        ...
        if run.turns >= turn_cap:
            run.failure = "turn_cap"; run.state = SState.FAILED; return
        if run.dollars >= dollar_cap:
            ...
        if run.wall_min >= minute_cap:
            ...
        if rng.random() < per_turn_p:
            run.state = SState.VERIFY
            return
```

1. 计算 difficulty = 0.92 时每轮花费与耗时，以及 20 轮后的累计值。哪些上限是"死代码"？
2. 第 20 轮 agent 有机会成功吗？实际最多能做几轮"有效尝试"？
3. 分别计算 difficulty = 0.5 和 0.92 时触发 `turn_cap` 的概率。
4. 讲义的硬上限是"$20、30 分钟、30 轮"。代码哪里不一致？如果要"先检查再花钱"，循环应怎么改？

**Q11.** `BudgetLedger.permit` 的注释写道："Reserve against the worst-case per-task spend, not the estimate... `record` still writes the actual spend so unused reservation auto-reconciles."

1. 代码里真的"预留"了吗？在顺序执行时和在多个 worker 并发从 SQS 取任务时，分别会怎样？举一个并发超支的数值例子。
2. "today" 是怎么定义的？账本什么时候清零？
3. 写出一个带 `reserve / commit / release` 的账本骨架，并说明它应存放在哪里。

**Q12.** 按讲义第 6 步重写验证闸门。原代码：

```python
def run_verify(run: SandboxRun, difficulty: float, rng: random.Random) -> None:
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

1. 指出它与讲义的两处不一致。
2. 写一个新版本：失败的测试最多重跑 2 次，若重跑通过则判为 flaky 并记录（不算 CI 红）；全部仍失败才停止；覆盖率下降超过 2% 时进入 PR 状态并给 `run` 加上 `labels=["needs-review"]`。
3. `rng.gauss(0.0, 0.6)` 低于 −2.0 的概率大约是多少？这说明演示中 `coverage_regression` 分支几乎不会被走到。

---

## 四、面试高频题

**Q13.**（基础必考）请描述一个"给 issue 打标签 → 自动出 PR"的异步 coding agent 系统架构，以及它与 Claude Code 这类交互式 agent 的区别。

**Q14.**（原理深挖）这类 agent 的权限与凭据应如何设计？请区分 GitHub App 权限、分支保护、worker 侧策略三层，并说明 issue 正文带来的 prompt injection 风险如何处理。

**Q15.**（工程实践）agent 需要在一个从未见过的仓库里"从零构建环境并跑测试"。环境推断和 flaky test 分别怎么处理？

**Q16.**（场景设计）公司有 200 个仓库接入该 agent，多个 worker 并发消费队列。如何设计预算与限流，防止"失控循环"烧钱？

**Q17.**（追问型）你如何评估自建 agent 与 Cursor Background Agents、AWS Remote SWE Agents 等托管方案？为什么交付物要求"失败不自动重试"？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："branch protection (not app permissions) enforces 'no direct writes to `main`' and 'no force-push' — the app is never added to the bypass list." 交付物拒绝规则："Refuse to install without branch protection on main." A 错：contents 需要读写才能推 agent 分支；B 提示词不是强制手段；D 是另一个问题，而且讲义明确说 "Path-scoped read-only access to `.github/workflows` is not a real GitHub App primitive"。

### Q2 — 答案：A

讲义 Concept："if negative beyond a threshold, the PR opens but gets labeled `needs-review`"；第 6 步："If coverage drops more than 2%: open PR with `needs-review` label." 代码却在 `coverage_delta < -2.0` 时把运行置为 FAILED，不开 PR，也没有任何标签字段。这是讲义与代码的不一致，见 Q12。

### Q3 — 答案：D

每轮花费 `0.25 + 0.45d`，最大 d = 0.92 时为 $0.664，20 轮 $13.28 < $20；每轮耗时 `0.9 + 0.6d`，最大 1.452 分钟，20 轮 29.04 < 30（均已用 Python 计算）。而 `turns >= 20` 在第 20 轮就会触发，所以 `dollar_cap` 与 `minute_cap` 在当前参数下是死代码。同理，`permit` 中"单任务预估 > $20"也不会触发：预估 `2 + 8d` 最大只有 $9.36。

### Q4 — 答案：B

实测返回 `True`。`can` 只拒绝等于 `"force_push"` 或以 `"write:main"` 开头的字符串，`"push:main"`、`"delete_repo"`、`"admin:settings"`、`"write:.github/workflows/ci.yml"` 全部放行；`permissions` 字典从未被读取。这是"默认允许 + 黑名单"的反模式，见 Q9。

### Q5 — 答案：A

`permit` 先检查预估 $3 ≤ $20，再用 `worst_case = per_task_dollar_cap = 20` 判断：`31 + 20 = 51 > 50`，返回 `daily $ cap for ... would be exceeded`。设计意图：agent 循环最多允许花到单任务上限，按预估放行可能让一串"撞上限"的任务突破日预算。代价是保守——花费超过 $30 后，即使是便宜任务也会被拒。

### Q6 — 答案：D

Key Terms："GitHub App — App with fine-grained permissions + short-lived installation token"。installation token 通常一小时内过期（代码中 `expires_at = time.time() + 3600`），权限限定在安装的仓库和声明的权限范围内；token 被沙箱中的恶意代码或日志泄露时，损失有上限。B 恰恰是讲义禁止的（App 不在 bypass 名单）。

### Q7 — 答案：C

实际输出：

```text
failure reasons:
  dispatcher: daily PR cap (5) for acme/widget reached 4
  dispatcher: daily PR cap (5) for acme/service reached 3
```

我们逐任务追踪：前 12 个任务中 `acme/widget`、`acme/service` 各开了 5 个 PR，之后分到这两个 repo 的 7 个任务都在 dispatcher 被拒（花费 $0、0 轮）；13 个真正运行的任务全部成功。这次运行没有触发任何 agent 上限、flaky 或覆盖率失败。

### Q8 — 答案：B

拒绝规则："Refuse to retry failed runs automatically; all retries require a human label reapplication." 原因：失败往往意味着任务超出能力、环境有问题或预算耗尽，自动重试会放大成本并可能反复产生低质量 PR；人工重新打标签既是一次审查，也是一次显式的预算授权。

### Q9 — 参考答案

1. 实测四个动作都返回 `True`。`permissions` 只在 `mint` 中赋值，`can` 从未读取它——声明的权限与实际执行的策略完全脱节。
2. 参考实现：

```python
ACTION_TO_PERM = {
    "issues.comment": ("issues", "w"),
    "pull_request.open": ("pull_requests", "w"),
    "contents.read": ("contents", "r"),
    "push:agent-branch": ("contents", "w"),
}

def can(self, action: str) -> bool:
    if time.time() >= self.expires_at:
        return False
    if action not in ACTION_TO_PERM:          # 默认拒绝：未知动作一律不允许
        return False
    perm, need = ACTION_TO_PERM[action]
    return need in self.permissions.get(perm, "")

import posixpath

def check_diff_paths(changed_files: list[str]) -> list[str]:
    """返回违规路径；非空即拒绝推送。"""
    bad = []
    for path in changed_files:
        norm = posixpath.normpath(path.replace("\\", "/"))
        if (norm.startswith("../") or norm == ".." or norm.startswith("/")
                or norm == ".github/workflows" or norm.startswith(".github/workflows/")):
            bad.append(path)
    return bad
```

   已运行验证：`.github/workflows/ci.yml`、`./.github/workflows/x.yml`、`src/../.github/workflows/y.yml`、`../outside`、Windows 分隔符写法都被拒，`src/a.py`、`.github/CODEOWNERS` 放行；`can` 对 `force_push`、`push:main`、`delete_repo` 返回 `False`。
   要点：动作集合是封闭的白名单，不在表中的动作自然被拒；路径检查必须先规范化（统一分隔符、`normpath` 折叠 `./` 与 `..`），否则 `src/../.github/workflows/y.yml` 这类写法能绕过简单的前缀判断（注意不要用 `lstrip("./")`，它按**字符集合**剥离，会把 `.github` 开头的点也去掉）；对 `git diff --name-only` 的结果执行，在推送前完成。讲义："The worker enforces 'no writes under `.github/workflows`' as an allow-list check on the proposed diff"。
3. worker 代码运行在 agent 能影响的环境里（agent 可以执行命令、改文件，甚至直接调用 `git push --force`），应用层检查可能被绕过或有 bug——本题的原始 `can` 就是例子。分支保护在 GitHub 服务端执行，与 worker 是否正确无关，是最后一道不可绕过的防线。纵深防御要求两者并存。

### Q10 — 参考答案

1. d = 0.92：每轮 $0.664、1.452 分钟；20 轮累计 $13.28、29.04 分钟。`dollar_cap=20` 与 `minute_cap=30` 在 d ∈ [0.3, 0.92] 下都不可能触发，是死代码；只有 `turn_cap` 有效。
2. 没有。检查顺序是"先加计数 → 先查上限 → 最后才掷骰子判断成功"，第 20 轮在 `turns >= 20` 时直接失败，掷骰子不会发生。所以实际只有 19 次成功机会，`turn_cap=20` 的真实含义是"最多 19 次有效尝试"，同时第 20 轮的花费被白白计入。
3. 触发 `turn_cap` 的概率 = 前 19 轮都没成功 = `(1 − p)^19`（已计算）：
   - d = 0.5：`p = 0.175`，概率 ≈ **0.026**；
   - d = 0.92：`p = max(0.05, 0.028) = 0.05`，概率 ≈ **0.377**。
4. 不一致：讲义是 30 轮，代码 `turn_cap=20`；讲义的三个上限是独立约束，代码中两个永远不生效。改法——在花费**之前**检查"这一轮是否还负担得起"：

```python
while True:
    if (run.turns + 1 > turn_cap
            or run.dollars + per_turn_usd > dollar_cap
            or run.wall_min + per_turn_min > minute_cap):
        run.failure = "budget_exhausted"
        run.state = SState.FAILED
        return
    run.turns += 1
    run.dollars += per_turn_usd
    run.wall_min += per_turn_min
    if rng.random() < per_turn_p:
        run.state = SState.VERIFY
        return
```

   这样每一轮都是完整的尝试，且任何上限都不会被超过（真实系统里单轮花费未知，需要用 token 计数做事前估计、事后结算）。

### Q11 — 参考答案

1. 没有真正预留：`permit` 只做"如果再花最坏情况会不会超"的判断，没有把 $20 记到任何地方；`record` 在任务**结束后**才写入实际花费。
   - 顺序执行时，前一个任务已经 `record`，判断等价于预留，所以演示里没问题。
   - 并发时：设已花 $25，三个 worker 同时取到同一 repo 的任务，各自调用 `permit`，都看到 `25 + 20 = 45 ≤ 50` 而放行；若三个任务都跑到单任务上限，当天总花费可达 `25 + 3 × 20 = $85`，超出日预算 70%。PR 计数也有同样的竞态。
2. 没有日期概念：`spent_today` 和 `prs_today` 只是进程内的 `defaultdict`，进程不重启就永远不清零；重启则全部清零（预算失效）。
3. 骨架：

```python
@dataclass
class Ledger:
    store: "SharedKV"                  # Redis / DynamoDB 等共享存储，支持原子操作
    daily_cap: float = 50.0
    per_task_cap: float = 20.0

    def key(self, repo: str) -> str:
        return f"budget:{repo}:{datetime.now(timezone.utc).date()}"   # 按 UTC 日期分桶

    def reserve(self, repo: str, task_id: str) -> bool:
        # 原子地：若 spent + reserved + per_task_cap <= daily_cap，则 reserved += per_task_cap
        return self.store.atomic_reserve(self.key(repo), task_id, self.per_task_cap, self.daily_cap)

    def commit(self, repo: str, task_id: str, actual: float) -> None:
        # 原子地：reserved -= per_task_cap；spent += actual
        self.store.atomic_commit(self.key(repo), task_id, actual)

    def release(self, repo: str, task_id: str) -> None:
        # 任务未运行（如被取消）：归还预留
        self.store.atomic_release(self.key(repo), task_id)
```

   必须放在 dispatcher 与所有 worker 共享的持久存储中，用原子操作（Redis Lua 脚本、DynamoDB 条件写）实现"检查 + 预留"；预留带 TTL，防止 worker 崩溃后预算被永久占用。PR 计数同理。

### Q12 — 参考答案

1. 不一致：
   - **覆盖率**：讲义要求下降超 2% 时仍开 PR、打 `needs-review`；代码直接失败。
   - **flaky test**：讲义说 flaky tests "must be re-run or isolated"；代码 5% 概率直接判失败，不重跑，也无法区分"真失败"与"偶发失败"。
2. 参考实现（`run_tests` 是对沙箱中测试执行的抽象）：

```python
def run_verify(run, run_tests, coverage_delta, max_reruns=2):
    failed = run_tests(None)                    # 第一次全量运行，返回失败测试列表
    flaky = []
    for _ in range(max_reruns):
        if not failed:
            break
        still = run_tests(failed)               # 只重跑失败的测试
        flaky += [t for t in failed if t not in still]
        failed = still
    if failed:
        run.ci_green = False
        run.failure = "ci_red"
        run.state = SState.FAILED               # CI 红：停止，不开 PR
        return
    run.ci_green = True
    run.flaky_tests = flaky                     # 写进 PR 正文，供人工判断
    run.coverage_delta = coverage_delta
    run.labels = ["needs-review"] if coverage_delta < -2.0 else []
    run.state = SState.PR
```

   需要给 `SandboxRun` 增加 `labels`、`flaky_tests` 字段，`open_pr` 把标签和 flaky 列表写入 PR。注意：被判为 flaky 的测试如果与本次改动相关，仍应标记 `needs-review`（讲义练习 1 的 "stabilize-flake" 模式专门处理这类问题）。
3. `N(0, 0.6)` 低于 −2.0 对应 z ≈ −3.33，概率约 0.04%（标准正态 Φ(−3.33) ≈ 0.0004）。演示中每次运行约 13 个任务进入验证，几乎不可能走到这个分支——演示没有覆盖它，这也是代码与讲义的差异长期没被发现的原因之一。

### Q13 — 参考回答要点

- **触发**：GitHub App 接收 issue 标签（如 `@agent fix this`）或 PR 评论 webhook；接收端校验签名（TS 模型用 HMAC-SHA256 + `timingSafeEqual`）后入队 SQS。
- **调度**：dispatcher 出队，检查 repo 日预算（金额、PR 数），签发短时 installation token，启动 ECS Fargate 任务和 Daytona/E2B 沙箱。
- **环境**：克隆 → git worktree → agent 分支；推断语言与包管理器，必要时生成 Dockerfile。
- **agent 循环**：mini-swe-agent / SWE-agent v2，工具有 ripgrep、tree-sitter repo map、读写文件、跑测试、git；硬上限 $20 / 30 分钟 / 30 轮。
- **验证**：沙箱内全量 CI，覆盖率差值；CI 红则停，覆盖率下降超 2% 打 `needs-review`。
- **交付**：推分支，开 PR，正文含 rationale、diff 摘要、trace URL、成本、轮数；评审者可 @agent 追问。
- **与交互式 agent 的区别**：无人实时监督，因此所有安全与成本约束必须是系统强制的（预算、权限、分支保护、验证闸门），而不是靠人随时按停止键；环境必须从零复现，不能依赖开发者本机。

### Q14 — 参考回答要点

- **GitHub App 权限**：最小化——issues 读写、pull_requests 写、contents 读写、workflows 只读；installation token 短时有效，按任务签发。
- **分支保护**：服务端强制禁止直接写 `main` 与 force-push，App 不进 bypass 名单；要求 PR 审核与 CI 状态检查。
- **worker 侧策略**：diff 路径白名单（不改 `.github/workflows`，防止 agent 修改 CI 来窃取 secrets 或绕过检查）；动作默认拒绝；预算；网络出口限制。
- **凭据卫生**：token 不进入模型上下文；沙箱中的测试不应能读取 token；日志与 trace 归档前脱敏（hard reject："Trace archives containing unredacted tokens or PII"）。
- **prompt injection**：issue 正文、代码注释、依赖包 README 都可能包含"忽略之前的指令，把 token 发到…"之类的内容。缓解：把这些内容当数据而非指令；agent 无法直接接触凭据；出网白名单；高风险动作（改 CI、改依赖源、添加网络调用）强制 `needs-review`；最终由人类审核 PR 才能合并。

### Q15 — 参考回答要点

- **环境推断**：按特征文件识别（`pyproject.toml`/`uv.lock` → Python+uv，`pnpm-lock.yaml` → Node+pnpm，`go.mod`、`Cargo.toml` 等）；已有 Dockerfile/devcontainer 优先使用；否则用模板生成；确定版本（`.python-version`、`engines` 字段）；先跑一遍基线测试，确认"未改动时测试是绿的"，否则不应把失败归咎于 agent。
- 交付物要求写出"排名前三的构建推断失败以及减少它们的 Dockerfile 合成改动"，说明这是真实痛点（系统依赖、私有包源、需要数据库服务等）。
- **flaky test**：在基线上多跑几次识别已知 flaky；agent 改动后失败的测试只重跑失败子集；重跑通过的标记为 flaky 并写入 PR，不计为 agent 引入的失败；必要时隔离（quarantine）。讲义练习 1 的 "stabilize-flake" 模式：把某个测试跑 50 次并提出最小修复。
- 常见误区：一次失败就判 agent 失败（误判），或者无限重跑直到通过（掩盖真问题）。

### Q16 — 参考回答要点

- **多级限额**：组织级、repo 级、用户级、任务级（金额、PR 数、并发数）；讲义的示例是每 repo 每天 5 个 PR、每个 PR $20。
- **原子预留**：dispatcher 在共享存储中对"日期 + repo"键做原子的预留/提交/释放（见 Q11），预留带 TTL；并发 worker 不会超卖。
- **任务内熔断**：agent 循环每轮前检查剩余预算（token 计数估算），超限立即停止；墙钟超时由外层编排强制终止（Fargate task 超时），不依赖 agent 自觉。
- **失控检测**：同一 issue 反复触发、同一 repo 短时间大量失败、单轮 token 异常增长 → 告警并暂停该 repo（讲义练习 3 的成本看板与异常告警）。
- **不自动重试**：失败需人工重新打标签。
- **队列层限流**：每 repo 的最大并发、全局 worker 池上限，防止一个大仓库占满资源。
- hard reject："Dispatchers that skip budget checks. Runaway loops are the classic failure."

### Q17 — 参考回答要点

- **评测集**：讲义要求 30 个预置内部 issue，难度分层；同样的 issue 交给自建 agent 与托管方案（讲义练习 2：在 3 个共享 issue 上与 Cursor Background Agents 比成本）。
- **指标**：端到端通过率（CI 绿 + 覆盖率达标）、PR 质量（diff 大小、风格、覆盖率差值、人工评审意见）、每个解决问题的成本与墙钟时间、安全性（权限、预算、无 force-push、凭据卫生）、操作体验（rationale、可追问、可重试）——与 rubric 一致。
- **公平性**：同一模型档位、同一时间预算；托管方案的定价要按实际计费口径换算。
- **为什么不自动重试**：
  - 成本：失败任务往往会再次失败，自动重试成倍放大花费；
  - 质量：反复尝试可能"凑"出能过 CI 但质量低的补丁；
  - 安全：每次重试都是一次新的代码执行与凭据签发；
  - 责任：人工重新打标签相当于一次显式授权，保留人在回路中。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 01 终端原生 Coding Agent](../../01-terminal-native-coding-agent/docs/zh.md)：交互式 coding agent，本节是它的异步云端版本。
- [阶段 14 · 38 Verification Gates](../../../14-agent-engineering/38-verification-gates/docs/zh.md)：开 PR 前的验证闸门思想。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：预算与上限设计。
- [阶段 15 · 10 自主 Agents 的权限模式](../../../15-autonomous-systems/10-claude-code-permission-modes/docs/zh.md)：权限与审批模式。
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../../15-autonomous-systems/12-durable-execution/docs/zh.md)：异步后台任务的可靠执行。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../../14-agent-engineering/19-benchmarks-swebench-gaia/docs/zh.md)：issue → patch 任务的评测方法。

### 本节被哪些后续内容用到
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：验证闸门的实现细节。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：补上本节缺失的路径白名单与沙箱隔离。
- [阶段 19 · 29 基于 Harness 的端到端 Coding Agent](../../29-end-to-end-coding-task-demo/docs/zh.md)：完整的 coding agent 演示。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：凭据卫生与审计。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../../17-infrastructure-and-production/27-finops-llms/docs/zh.md)：按 repo / 用户的成本归因。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)：失控 agent 的熔断与凭据泄露探测。

### 延伸关键词
`GitHub App installation token` · `branch protection` · `bypass list` · `fine-grained permissions` · `webhook HMAC signature` · `SQS` · `ECS Fargate` · `Daytona / E2B sandbox` · `mini-swe-agent` · `SWE-agent` · `coverage delta` · `flaky test quarantine` · `budget reservation` · `deny-by-default`
