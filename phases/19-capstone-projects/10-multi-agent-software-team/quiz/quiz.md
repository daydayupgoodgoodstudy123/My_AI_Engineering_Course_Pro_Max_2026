# 测验 · 多 Agent 软件工程团队（Multi-Agent Software Engineering Team）

> **阶段 19 · 综合项目 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：`code/ts/` 下另有一个 TypeScript 的协调器/运行时骨架，本测验以 Python 的 `main.py` 为主。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 收敛后的团队形态 | architect 规划 → N 个 coder 在并行 worktree 中实现 → merge coordinator 三方合并 → reviewer 把关 → tester 验证；SWE-AF、MetaGPT、AutoGen 0.4、Devin、Factory Droids 各自独立走到了这个形态 |
| 2 | 为什么要多 agent | 讲义：单个 200k token 的上下文装不下"架构计划 + 4 份并行代码切片 + 评审意见 + 测试输出"；拆角色是在拆上下文 |
| 3 | 失败面在 handoff | 计划太模糊、diff 冲突、reviewer 批准了幻觉修复、tester 与仍在写代码的 coder 竞争——每一次跨角色的消息都是潜在故障点 |
| 4 | 类型化任务板 | 文件（JSONL）或 Redis 上的类型化消息：`plan_request`、`subtask`、`diff_ready`、`review_needed`、`approved`、`rejected`、`replan_needed` 等；agent 按标签订阅 |
| 5 | 并行 worktree | `git worktree add` 给每个 coder 一个独立工作树（再配 Daytona 沙箱），把墙钟时间换成吞吐 |
| 6 | 协调规则 | 计划在 coder 开工后冻结（重新规划是单独事件）；只在文件级重叠时才用 LLM 调解冲突；reviewer 不能批准自己写或自己提议的改动 |
| 7 | Token amplification | 每个角色边界都要加摘要和交接上下文；讲义：单 agent 40 轮可能变成四个角色共 160 轮；评分要看"每美元是否赢"，而不是"能不能工作" |
| 8 | False approval | reviewer 批准了含已知 bug 的 diff；讲义练习 1 通过注入 bug 测量，目标低于 5% |
| 9 | Handoff 记账 | 每条跨角色消息在 Langfuse 里一个 span，记录 payload 大小和模型；失败后归因到具体哪次 handoff，画 handoff-failure 直方图 |
| 10 | 评估 | 50 个 SWE-bench Pro issue，对比单 agent 基线的 pass@1、每解决一个 issue 的花费、并行加速比 |

### 核心技能（能动手做到）

- [ ] 画出本节代码中一次运行的消息序列（谁发给谁、什么类型、多少 token），并数出 handoff 数
- [ ] 手算 `run_team` 的理论通过率（注入 bug 概率、reviewer 捕获率、flake 率），与实测对比
- [ ] 找出 review feedback 被固定路由给 `coder-A`、修复后整份 diff 被"一键清零 bug"的问题并修复
- [ ] 指出 `n_coders < 4` 时子任务被静默丢弃的 bug，并实现"一个 coder 顺序处理多个子任务"（讲义练习 2）
- [ ] 区分讲义中两种 token amplification 定义，并说明本节代码只统计了"消息 token"而没统计"读上下文的 token"
- [ ] 设计一个注入 bug 探针来测 reviewer 的 false-approval rate

---

## 二、基础自测（选择题）

**Q1.** 讲义认为单 agent 编码 harness 在大任务上遇到天花板的主要原因是：

- A. 单个模型的编码能力太弱
- B. 单 agent 无法调用 git
- C. 单 agent 无法运行测试
- D. 一个 200k token 的上下文装不下架构计划、多份并行代码切片、评审意见和测试输出

**Q2.** 运行 `python main.py`，第一次团队运行的 `handoffs` 是 12。这 12 条消息是：

- A. 1 条 `PLAN_REQUEST` + 4 条 `SUBTASK` + 4 条 `DIFF_READY` + 1 条 `REVIEW_NEEDED` + 1 条 `APPROVED` + 1 条 `TEST_PASSED`
- B. 4 个 coder 之间互相发送的 12 条同步消息
- C. 3 轮评审 × 4 个 coder
- D. 只统计了真正跨角色的消息，architect 发给 board 的那条不算

**Q3.** 本节代码中 `tokens_by_role` 的统计口径是：

- A. 每个角色调用 LLM 时的输入 + 输出 token
- B. 每个角色**接收**的消息 token 之和
- C. 每个角色**发出**的消息 token 之和（`self.tokens_by_role[m.by] += m.tokens`），所以 architect 的 9,300 = 4,500 + 4 × 1,200
- D. 每个角色在任务板上的消息条数

**Q4.** 讲义 Key Terms 对 "token amplification" 的定义是：

- A. 每个 coder 的 token / architect 的 token
- B. 多角色总 token / 同一任务单 agent 的 token
- C. reviewer 的 token / tester 的 token
- D. 输出 token / 输入 token

**Q5.** 关于 reviewer 的规则，讲义明确要求：

- A. reviewer 必须与 coder 使用同一个模型，避免风格冲突
- B. reviewer 只看单个 coder 的 diff，不看合并后的 diff
- C. reviewer 不能批准自己写的 diff，也不能批准自己提议的改动
- D. reviewer 的意见一律发给 architect 重新规划

**Q6.** 代码中 `reviewer_check` 在有 bug 时以 85% 概率拒绝，否则误批准；`architect_plan` 以 30% 概率注入 bug。单次运行出现 false-approve 的概率约为：

- A. 15%
- B. 30%
- C. 25.5%
- D. 4.5%

**Q7.** 讲义对"计划变更"的协调规则是：

- A. coder 开工后计划冻结；重新规划作为单独事件处理
- B. 任何 coder 都可以随时修改计划
- C. reviewer 负责在评审时顺便改计划
- D. tester 失败时自动让 architect 重写整个计划并重启所有 coder

**Q8.** 在 10 次"matched trials"中，团队通过 7/10、基线通过 5/10、token 放大 1.60x。下列结论最恰当的是：

- A. 多 agent 团队已被证明比单 agent 强 40%
- B. 团队与基线的通过概率是代码写死的参数（团队理论值约 92.6%、基线 68%），10 次试验样本太小，且两者并非在同一任务上真实对比，不能据此下结论
- C. token 放大 1.60x 说明多 agent 更省钱
- D. 应该把 coder 数增加到 8 个以进一步提高通过率

---

## 三、动手 / 代码题

**Q9.** 阅读 reviewer 拒绝后的分支：

```python
    approved, comment = reviewer_check(diffs, rng)
    if approved:
        board.post(Msg(MsgKind.APPROVED, by="reviewer", to="tester", ...))
    else:
        # route back to coder who owned the subtask (simplified: first coder)
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

在 10 次试验的第 2 次（`issue-1`）中，reviewer 的意见是 `found bug in migration: please revisit`。

1. 这条反馈被发给了谁？谁应该收到它（migration 是第几个子任务、由哪个 coder 负责）？
2. coder-A "修复"后，为什么 migration 的 bug 也消失了？reviewer 有没有再次检查？
3. `run_team` 返回的 `approved` 字段在这次运行中是什么？它和最终"测试通过"放在一起会造成什么误解？
4. 写出修复：按子任务找到负责的 coder、只修复该子任务、修复后重新调用 `reviewer_check`、返回最终批准状态，并限制最多 N 轮修订。

**Q10.** 讲义练习 2 要求"减少到两个 coder，每个 coder 顺序处理两个子任务"。用 `run_team(..., n_coders=2)` 直接运行：

```python
    for i, sub in enumerate(plan[:n_coders]):
        coder = f"coder-{chr(65 + i)}"
        ...
```

1. `n_coders=2` 时 api 和 migration 两个子任务会怎样？如果注入的 bug 恰好在 migration 里，最终测试结果会是什么？
2. 改写 dispatch 和 implement 两段循环，使子任务按轮转（round-robin）分配给 `n_coders` 个 coder。
3. 在你的改写中加入一个简单的墙钟模型：每个子任务耗时 ∝ `lines_changed`，同一个 coder 的子任务串行、不同 coder 并行，输出 `n_coders = 1, 2, 4` 时的总墙钟时间（讲义评分表"Parallel speedup"占 20 分）。

**Q11.** 计算团队的理论通过率，并与实测对比。

1. 根据代码参数（注入 bug 概率 0.3、reviewer 捕获率 0.85、修复后必然无 bug、tester 对剩余 bug 100% 发现、flake 率 0.03），写出单次运行测试通过的概率。
2. 我们用 20,000 次运行实测得到团队通过率 0.928、基线通过率 0.675、团队平均 34,888 token、基线平均 20,987 token、放大 1.66x、false-approve 发生率 0.044。验证你的公式。
3. 代码假设"tester 对剩余 bug 100% 发现"。如果改为 tester 只能发现 70% 的 bug，false-approve 的后果是什么？讲义的 false approval 指标为什么要单独测？

**Q12.** 讲义给出两种 token 放大的算法：Key Terms 中"多角色总 token / 单 agent token"；Build It 第 7 步中按子任务计算 `(coder_tokens + reviewer_tokens + tester_tokens + architect_share) / coder_tokens`。

1. 以第一次团队运行的数据（architect 9,300；coder-A/B/C/D 分别 5,360/5,600/5,900/4,370；merge_coord 2,000；reviewer 1,800；tester 1,200）为例，按第二种定义计算 coder-A 这个子任务的放大倍数（架构师份额按 4 个子任务平均分摊，reviewer、tester、merge_coord 也平均分摊）。
2. 本节代码的 token 只记录"发出的消息大小"。真实系统中 reviewer 读合并 diff、tester 读测试输出都要消耗输入 token。这会让代码算出的放大倍数偏高还是偏低？
3. 讲义说"单 agent 40 轮可能变成四个角色共 160 轮"，即 4x；代码给出 1.60x。为什么两者差这么多？

---

## 四、面试高频题

**Q13.**（基础必考）请设计一个多 agent 软件工程团队：有哪些角色、各自用什么模型和工具、它们之间如何通信、一个 issue 从输入到 PR 的完整流程是什么？

**Q14.**（原理深挖）多 agent 系统最常见的失败点在哪里？请结合"handoff"概念说明至少四种失败模式，以及每种的检测方法。

**Q15.**（工程实践）多个 coder 并行修改同一个仓库，如何隔离、如何合并、如何处理冲突？"单写者约束"（每个子任务只碰不相交的文件集合）有什么利弊？

**Q16.**（场景设计）老板问："多 agent 团队比单个 agent 好吗？"你会设计怎样的实验来回答？需要报告哪些指标？

**Q17.**（追问型）如何测量并降低 reviewer 的 false-approval rate？如果 reviewer 和 coder 是同一个模型家族，会有什么额外风险？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义 Problem："Not because any individual agent is weak, but because a 200k-token context cannot hold an architecture plan plus four parallel codebase slices plus reviewer commentary plus test output." A 恰恰被讲义否定；B、C 与事实不符，单 agent harness 同样能调用 git、跑测试。

### Q2 — 答案：A

`handoffs = sum(1 for m in board.messages if m.to != m.by)`。代码中**每一条**消息的 `to` 都不等于 `by`，所以 handoffs 实际就是消息总数：1 + 4 + 4 + 1 + 1 + 1 = 12。D 错：发往 `"board"` 的 `PLAN_REQUEST` 同样被计入；严格来说它不是"跨角色"的 handoff，这是统计口径上的瑕疵。当 reviewer 拒绝时会多出 `REVIEW_FEEDBACK` 和第二条 `DIFF_READY`，handoffs 为 14（10 次试验中的第 2、3、5 次即如此）。

### Q3 — 答案：C

`Board.post` 中 `self.tokens_by_role[m.by] += m.tokens`，按**发送方**累计。architect 发 1 条 `PLAN_REQUEST`（4,500）和 4 条 `SUBTASK`（各 1,200），合计 9,300；coder 的 token 为 `3200 + lines × 30`，例如 coder-A 的 5,360 对应 72 行。A 错：代码没有区分输入/输出，也没有模拟读上下文的消耗；B 说反了。

### Q4 — 答案：B

讲义 Key Terms："Token amplification — Total tokens across roles / single-agent tokens for the same task"。代码最后一行 `team_tok_sum / max(1, base_tok_sum)` 正是这种定义（1.60x）。讲义 Build It 第 7 步还给出了另一种按子任务的算法，见 Q12。

### Q5 — 答案：C

讲义 Concept："reviewer gatekeeping (the reviewer cannot approve its own changes or changes it proposed)"，Build It 第 5 步："Cannot approve diffs it authored"。A 与讲义的多模型配置相反（讲义 reviewer 用 GPT-5.4、coder 用 Sonnet 4.7）；B 错，讲义 reviewer 读的是"merged diff"；D 错，讲义把评审意见路由回"relevant coder"。本节代码没有实现"不能批准自己提议的改动"这一规则。

### Q6 — 答案：D

`P(有 bug) × P(reviewer 漏检) = 0.3 × 0.15 = 0.045`。20,000 次实测 false-approve 发生率 0.044。A 是"有 bug 条件下"的误批准率（即讲义练习 1 要测的 false-approval rate，目标 < 5%）；C 是 `0.3 × 0.85`，即 reviewer 正确拦截的概率。

### Q7 — 答案：A

讲义 Concept："shared-state synchronization (the plan is frozen once coders start; replans are separate events)"。B、C 会造成共享状态不一致——coder 正在按旧计划写代码时计划被改；D 代价过高，讲义要求失败的测试"loop back to the coder owning the failing subtask"。

### Q8 — 答案：B

- 团队理论通过率：`0.7 × 0.97 + 0.3 × 0.85 × 0.97 ≈ 0.926`；基线是 `rng.random() < 0.68`。两个数都是代码设定的参数，"团队更强"是假设，不是实验结论。
- 10 次的 7/10 vs 5/10 波动很大（团队理论值 92.6%，这次只得到 70%：两次 flaky test、一次 false-approve 被 tester 拦下）。
- "matched trials"并没有让两者在同一个真实任务上运行，基线的 token 是 18,000–24,000 的随机数。
- C 错：放大 1.60x 意味着团队多花 60% 的 token；D 无依据，且 `architect_plan` 固定只有 4 个子任务。

### Q9 — 参考答案

1. 反馈被硬编码发给 `coder-A`（注释也承认"simplified: first coder"）。migration 是 `plan` 的第 4 个子任务（下标 3），按 `chr(65 + i)` 由 **coder-D** 负责。讲义 Use It 中 reviewer 对 cache 的意见正确地"routed to coder-B"。
2. coder-A 发出的修订 `DIFF_READY` 的 payload 固定为 `{"subtask": "parser", "lines": 52, "has_bug": False}`，然后 `diffs` 被整体重建、**所有** `has_bug` 都置为 False——不管 bug 在哪个子任务。reviewer 也没有再调用 `reviewer_check`，直接发出 `"now lgtm"`。在真实系统里这等于"别人改了 parser，你的 migration bug 就算修好了"。
3. `approved` 是**第一次**评审的结果 `False`，而 `tested_passed` 是 True。调用方看到"未批准但测试通过"会以为 PR 绕过了评审；实际上最终是批准了的。应该分别返回 `initial_approved`、`final_approved` 和 `revisions` 数。
4. 修复示意：

```python
    owner = {sub.name: f"coder-{chr(65 + i)}" for i, sub in enumerate(plan)}
    revisions = 0
    approved, comment = reviewer_check(diffs, rng)
    while not approved and revisions < MAX_REVISIONS:
        buggy = next(d for d in diffs if d["has_bug"])
        coder = owner[buggy["subtask"]]
        board.post(Msg(MsgKind.REVIEW_FEEDBACK, by="reviewer", to=coder,
                       payload={"comment": comment, "subtask": buggy["subtask"]}, tokens=1800))
        fixed = {**buggy, "has_bug": rng.random() < 0.2}     # 修复也可能失败
        diffs = [fixed if d["subtask"] == buggy["subtask"] else d for d in diffs]
        board.post(Msg(MsgKind.DIFF_READY, by=coder, to="merge_coord",
                       payload=fixed, tokens=3200 + fixed["lines"] * 30))
        revisions += 1
        approved, comment = reviewer_check(diffs, rng)       # 必须重新评审
    if approved:
        board.post(Msg(MsgKind.APPROVED, by="reviewer", to="tester",
                       payload={"comment": comment}, tokens=1500))
```

   要点：按 owner 路由；只替换出问题的那个子任务；修复后重新评审；有修订上限，超过就以 `rejected` / `replan_needed` 结束。

### Q10 — 参考答案

1. `plan[:n_coders]` 只取前两个子任务（parser、cache），api 和 migration 既没有被分配、也没有被实现，**没有任何报错或记录**。tester 和 reviewer 只看 `diffs`，所以如果 bug 被注入到 migration，它根本不出现在 diffs 里，结果是"测试通过、评审通过"——一个只实现了一半计划的 PR 被判为成功（实测 `n_coders=2` 的 6 次运行全部通过）。
2. 轮转分配：

```python
    assignments = [(f"coder-{chr(65 + i % n_coders)}", sub) for i, sub in enumerate(plan)]
    for coder, sub in assignments:
        board.post(Msg(MsgKind.SUBTASK, by="architect", to=coder,
                       payload={"subtask": sub.name, "files": sub.files}, tokens=1200))
    diffs = []
    for coder, sub in assignments:
        result = coder_implement(sub, rng)
        diffs.append({**result, "coder": coder})
        board.post(Msg(MsgKind.DIFF_READY, by=coder, to="merge_coord",
                       payload=result, tokens=3200 + result["lines"] * 30))
```

3. 墙钟模型：

```python
    busy = defaultdict(float)                      # 每个 coder 的累计耗时
    for d in diffs:
        busy[d["coder"]] += d["lines"] * 0.2       # 假设每行 0.2 分钟
    coding_wall = max(busy.values())               # 并行：取最慢的那个 coder
```

   `n_coders=1` 时墙钟 = 所有子任务之和；`n_coders=4` 时 = 最大的那个子任务。加速比 = 前者 / 后者，上限是子任务数 4（再加上 architect、merge、review、test 这些串行阶段，实际加速比更低——阿姆达尔定律）。

### Q11 — 参考答案

1. `P(pass) = P(无 bug) × 0.97 + P(有 bug) × P(reviewer 捕获) × 0.97 = 0.7 × 0.97 + 0.3 × 0.85 × 0.97 = 0.679 + 0.247 ≈ 0.926`。reviewer 漏检时 tester 必然失败，贡献为 0。
2. 实测 0.928 与 0.926 吻合；基线 0.675 与参数 0.68 吻合；false-approve 0.044 与 0.045 吻合。token：团队每次约 4,500 + 4,800 + 4 × (3,200 + 55 × 30) + 2,000 + 1,800 + 1,200 ≈ 33,700（无修订时），加上约 25% 概率的修订开销（+4,600），约 34,900，与实测 34,888 一致；基线均值 21,000，放大约 1.66x。
3. 代码里 tester 是"完美的安全网"，所以 false-approve 只会表现为"测试失败"，永远不会进入 PR。真实情况下测试覆盖有限，reviewer 误批准的 bug 有相当比例能通过测试、直接合入。这正是讲义要求单独测 false-approval rate（练习 1：注入明显 bug，调 reviewer prompt 直到低于 5%）的原因——不能指望 tester 兜底。若 tester 只能发现 70%，则每次运行把 bug 合入的概率约为 `0.3 × 0.15 × 0.3 ≈ 1.35%`，在 50 个 issue 上大约有 0.7 个带 bug 的 PR。

### Q12 — 参考答案

1. 按子任务平均分摊：architect 9,300 / 4 = 2,325；reviewer 1,800 / 4 = 450；tester 1,200 / 4 = 300；merge_coord 2,000 / 4 = 500。coder-A 子任务的放大倍数 = `(5,360 + 450 + 300 + 2,325 + 500) / 5,360 = 8,935 / 5,360 ≈ 1.67`。（讲义公式中没有列 merge_coord，若不计入则为 `8,435 / 5,360 ≈ 1.57`。注意讲义原文写作 "coder_tokens + reviewer_tokens + tester_tokens + architect_share / coder_tokens"，按运算优先级字面读会只把 architect_share 除以 coder_tokens，应理解为整个和除以 coder_tokens。）
2. 偏低。真实系统中每个角色都要**读**交给它的上下文：reviewer 读合并后的全部 diff、tester 读测试日志、每个 coder 读计划和相关代码。这些输入 token 往往远多于输出。代码只记录"发出的消息大小"，系统性低估了多 agent 的开销。
3. 讲义的 4x 是按**轮数**说的：四个角色各自要重复"读上下文、理解任务"，40 轮变 160 轮。代码的基线 token（18k–24k 随机数）与团队 token（固定参数）之间没有因果关系，1.60x 只是两组常数之比。要得到可信的放大倍数，必须在同一批 issue 上真实运行两套系统并记录每次 LLM 调用的输入和输出 token。

### Q13 — 参考回答要点

- **角色与模型**（讲义配置）：architect（Opus 4.7）读 issue、产出带显式接口（改哪些文件、公开函数、测试影响）的子任务 DAG；N 个 coder（Sonnet 4.7）各自在 `git worktree` + Daytona 沙箱里实现子任务；merge coordinator 做三方合并；reviewer（GPT-5.4）读合并 diff；tester（Gemini 2.5 Pro）在干净沙箱里跑测试。
- **通信**：类型化任务板（JSONL 或 Redis），消息类型 `plan_request`、`subtask`、`diff_ready`、`review_needed`、`approved`、`rejected`、`replan_needed`；讲义提到用 A2A 协议做类型化消息；agent 按标签订阅。
- **流程**：issue → 计划（冻结）→ 并行实现 → 全部完成后合并 → 评审（意见路由到负责的 coder）→ 测试（失败路由到负责失败子任务的 coder）→ 开 PR。
- **记账与观测**：每条跨角色消息一个 Langfuse span，带 payload 大小和模型；按角色统计 token。
- 加分点：说明为什么用不同模型家族做 reviewer（降低"同源盲点"）；说明计划冻结与重规划事件的区别。

### Q14 — 参考回答要点

- **计划太模糊/不可实现**：子任务接口不清，coder 各自理解不同。检测：coder 发起的澄清请求数、`replan_needed` 事件数；子任务接口模板强制填写文件和函数签名。
- **合并冲突**：并行 coder 修改了同一文件或互相依赖的接口。检测：三方合并的冲突数、LLM 调解次数、调解后测试失败率。
- **reviewer 误批准**：批准了含 bug 或幻觉修复的 diff。检测：注入 bug 探针（讲义练习 1）。
- **tester 竞态/flake**：tester 在 coder 还在写的时候就跑测试，或测试本身不稳定。检测：基于"全部 diff_ready 之后才发 test_needed"的屏障；对失败测试在基线分支上重跑以判断 flake。
- **反馈路由错误**：意见发给了错误的 coder（本节代码即如此）。检测：记录每条 feedback 的目标与子任务 owner 是否一致。
- **静默丢任务**：子任务没有被任何 coder 领取（本节 `n_coders < 4` 时即如此）。检测：计划中的子任务集合必须等于 diff_ready 的子任务集合。
- 讲义要求的交付：对每个失败的 issue 指出是哪次 handoff 出问题，画 handoff-failure 直方图。

### Q15 — 参考回答要点

- **隔离**：每个 coder 一个 `git worktree add` 出的独立工作树 + 独立沙箱，互不干扰地编译和跑本地测试；讲义："Parallel worktrees convert wall-clock into throughput"。
- **合并**：全部 coder 完成后，由 merge coordinator 把 N 个分支三方合并到 staging 分支；只有存在文件级重叠时才调用 LLM 调解冲突。
- **冲突处理**：先尝试 git 自动合并；冲突时把双方的子任务描述、diff 和接口约定交给 LLM 生成合并结果，然后**必须重新跑测试**。
- **单写者约束（讲义练习 3）**：要求子任务涉及的文件集合不相交，从根本上消除冲突、去掉 merge coordinator；代价是 architect 的规划负担上升（必须提前精确知道每个子任务要碰哪些文件），有些改动（例如修改一个被多处调用的公共函数）很难拆成不相交的集合。
- 加分点：接口先行——architect 先定义并提交公共接口（类型、函数签名），coder 基于同一个接口版本并行工作，减少语义冲突。

### Q16 — 参考回答要点

- **实验设计**：同一批 50 个 SWE-bench Pro issue，两套系统（多 agent 团队 vs 单个 Sonnet 4.7 在一个 worktree 中），配对比较；多次重复以估计方差；固定模型版本和预算。
- **指标**（对应讲义评分表）：pass@1；并行加速比（墙钟时间）；false-approval rate（注入 bug 探针）；每解决一个 issue 的 token 和美元；合并冲突数与 handoff 失败直方图。
- **关键问题**：讲义："the question is not 'does multi-agent work' but 'does it win per dollar'"。如果团队 pass@1 只高几个百分点但花费高 2–4 倍，要看业务是更在乎速度/成功率还是成本。
- **统计**：50 个样本的通过率置信区间约 ±14 个百分点，配对检验（如 McNemar 检验）比较两组在同一题上的成败。
- 常见误区：用不同任务集或不同随机种子的运行做对比（本节代码的"matched trials"即没有真正匹配）。

### Q17 — 参考回答要点

- **测量**：构造注入 bug 的探针集（讲义练习 1：在函数主体前插入一行 `return None`；还可以注入边界条件错误、错误的异常处理、并发问题），统计 reviewer 批准含 bug diff 的比例；同时测"误拒绝率"，防止 reviewer 变成"什么都拒"。
- **降低**：reviewer prompt 要求逐项检查清单（接口一致性、边界条件、测试是否覆盖改动）；要求 reviewer 引用具体代码行给出理由；让 reviewer 能运行测试或静态分析工具；对高风险改动用两个 reviewer 投票；讲义目标是低于 5%（练习 1）、并比较不同模型做 reviewer 的差异（练习 4）。
- **同源模型风险**：coder 与 reviewer 同家族时，可能共享相同的盲点和偏好（对自己风格的代码更"宽容"），误批准率更高；讲义特意让 reviewer 用 GPT-5.4、coder 用 Sonnet 4.7，并规定 reviewer 不能批准自己写或提议的改动。
- 加分点：reviewer 的评估本身要有 golden set，并随时间监控（模型升级后重新测）。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 05 监督者与编排者—工作者模式](../../../16-multi-agent-and-swarms/05-supervisor-orchestrator-pattern/docs/zh.md)：architect + coder 的编排者—工作者结构。
- [阶段 16 · 08 角色专业化：规划者、Critic、执行者与验证者](../../../16-multi-agent-and-swarms/08-role-specialization/docs/zh.md)：四种角色的划分依据。
- [阶段 16 · 13 共享记忆与黑板模式](../../../16-multi-agent-and-swarms/13-shared-memory-blackboard/docs/zh.md)：任务板本质上是黑板模式。
- [阶段 16 · 12 A2A：Agent 与 Agent 之间的通信协议](../../../16-multi-agent-and-swarms/12-a2a-protocol/docs/zh.md)：类型化的 agent 间消息。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../../14-agent-engineering/39-reviewer-agent/docs/zh.md)：reviewer 与 coder 分离的原因。
- [阶段 14 · 45 通过隔离与合并契约委派 Agent 任务](../../../14-agent-engineering/45-delegate-with-isolation/docs/zh.md)：worktree 隔离与合并契约。

### 本节被哪些后续内容用到
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../../16-multi-agent-and-swarms/23-failure-modes-mast-groupthink/docs/zh.md)：多 agent 失败的分类法。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../../16-multi-agent-and-swarms/24-evaluation-coordination-benchmarks/docs/zh.md)：如何评估多 agent 系统。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../../16-multi-agent-and-swarms/22-production-scaling-queues-checkpoints/docs/zh.md)：任务板在生产中的持久化。
- [阶段 19 · 11 LLM Observability 与评估仪表盘](../../11-llm-observability-dashboard/docs/zh.md)：按角色的 span 与 token 记账。
- [阶段 19 · 16 从 GitHub Issue 到 PR 的自主 Agent](../../16-github-issue-to-pr-agent/docs/zh.md)：单 agent 版本的 issue → PR。

### 延伸关键词
`git worktree` · `task board` · `blackboard pattern` · `A2A protocol` · `three-way merge` · `single-writer constraint` · `token amplification` · `false approval` · `handoff-failure histogram` · `SWE-bench Pro` · `Amdahl's law` · `McNemar test`
