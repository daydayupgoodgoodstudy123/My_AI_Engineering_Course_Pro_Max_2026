# 测验 · Reviewer Agent：将实现者与评分者分开（Reviewer Agent: Separate Builder from Marker）

> **阶段 14 · Agent 工程 · 第 39 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 验收是必要条件，不是充分条件 | gate 说 `passed: true` 后合并，两天后发现修的是 bug 的"错误那一半"；reviewer 问 gate 问不了的问题 |
| 2 | 写代码的 agent 不能给自己打分 | reviewer 是第二个循环：不同的 system prompt、不同的目标、对 builder 产物**只读** |
| 3 | 五维 rubric | problem fit、scope discipline、assumptions、verification quality、handoff readiness，每项 0–2 分，满分 10 |
| 4 | 结论阈值 | 总分 < 7 为 soft fail；< 5 或任一维度为 0 为 hard fail（讲义 Key Terms） |
| 5 | 角色分离而非模型分离 | 同一个模型可以两边都当；纪律在于 prompt、输入、姿态不同，且 reviewer 不能写 diff |
| 6 | reviewer 不改 diff | 报告说"修这里"，由下一轮 builder 修；角色混用会抹掉两者之间的差距 |
| 7 | 与 gate 的分工（Hybrid Norm） | gate 做确定性事实检查；reviewer 做语义判断；不要让 reviewer 重做 gate 已经证明的事 |
| 8 | 专家池 + 协调者 | 讲义引 Cloudflare：30 天 131,246 次评审、最多 7 个专家并行、协调者去重并判定严重度；顶级模型只给协调者 |
| 9 | LLM 判官的四种偏差 | 位置偏差（GPT-4 约 40% 顺序不一致）、冗长偏差（约 15% 的分数膨胀）、自我偏好、权威偏差；需要在设计中缓解 |
| 10 | 校准集 | 10–20 个已知正确结论的历史任务；每次改 prompt 都重跑；与历史一致率 < 80% 时先改 rubric |

### 核心技能（能动手做到）

- [ ] 读懂本节五个打分函数，能对任意输入预测每个维度的分数与最终结论
- [ ] 指出确定性 stub 打分（关键词匹配、只看退出码）会被怎样"刷分"或误判
- [ ] 为 rubric 的每一维写出 0/1/2 的锚点描述，并要求每个分数都引用证据（文件路径或 trace 条目）
- [ ] 实现"gate 未通过就拒绝评审""置信度低于阈值就交给人"的前置/后置条件
- [ ] 实现"两种顺序都评一遍、只计一致的胜出"的位置偏差缓解
- [ ] 设计一个校准集流程，并说明 80% 一致率阈值的用法

---

## 二、基础自测（选择题）

**Q1.** 讲义的开场故事中，verification gate 给出了 `passed: true`，合并两天后却发现修错了问题的一半。这说明：

- A. verification gate 的实现有 bug
- B. 应该把 gate 换成 LLM 判官
- C. 测试越多越好，补测试就能解决
- D. 验收是必要条件而非充分条件；"解决的是不是对的问题"需要另一个角色来判断

**Q2.** 关于"reviewer 是独立角色而非独立模型"，下列说法正确的是：

- A. reviewer 必须使用比 builder 更大的模型，否则没有意义
- B. 同一个模型可以同时担任两个角色；关键是不同的 system prompt、不同的输入，并且 reviewer 对 diff 没有写权限
- C. reviewer 可以直接修复它发现的问题，以节省一轮
- D. reviewer 应复用 builder 的 system prompt，保证上下文一致

**Q3.** 运行 `python3 code/main.py`，T-002 的五项得分为 `0, 1, 1, 2, 1`，总分 5，结论是 `hard_fail`。直接原因是：

- A. `problem_fit` 为 0，触发了"任一维度为 0 即 hard fail"的规则；仅看总分 5 本应是 soft fail
- B. 总分 5 < 7，所以是 hard fail
- C. `verification_quality` 为 2，说明测试作弊
- D. 有越界写入 warn，所以直接 hard fail

**Q4.** T-001（"add input validation to signup"，改了 `app/signup.py` 和 `tests/test_signup.py`）的 `problem_fit` 只得了 1 分。原因是：

- A. 改动的文件太少
- B. `goal` 中没有长度大于 4 的词
- C. 关键词是 `input`、`validation`、`signup`，只有 `signup` 出现在文件路径中，命中 1 个
- D. `problem_fit` 的满分就是 1

**Q5.** 讲义列出的 LLM 判官偏差中，描述正确的是：

- A. 冗长偏差：判官倾向于给更**短**的输出打高分，约 15%
- B. 位置偏差：交换 (A,B) 与 (B,A) 的顺序时，GPT-4 约 40% 的情况下判断不一致
- C. 自我偏好：判官倾向于偏爱**其他**模型家族的输出
- D. 权威偏差：判官会低估引用知名作者的内容

**Q6.** 关于校准集（calibration set），讲义的建议是：

- A. 只需在上线前跑一次
- B. 用 1,000 个以上的合成任务
- C. 校准集用来调 temperature
- D. 10–20 个已知正确结论的历史任务；每次改 prompt 都重跑；与历史记录一致率低于 80% 时，先修改 rubric 再上线 reviewer

**Q7.** 给本节 `review()` 传入一个 gate 没通过的任务：`verdict={"passed": False, "findings": [{"code": "acceptance.missing", "severity": "block"}]}`，其他输入与 T-001 相同。结果是：

- A. 总分 9，`pass`——代码完全不看 `verdict["passed"]`，只看 scope 相关的 finding
- B. `hard_fail`，因为 gate 没通过
- C. 抛出 `KeyError`
- D. 拒绝评审，返回 `refused`

**Q8.** 讲义引用的 Cloudflare AI 代码评审架构是：

- A. 一个大型 reviewer 跑完整的五维 rubric，所有任务用最强模型
- B. 每个仓库一个 reviewer，彼此独立，不去重
- C. 最多 7 个专家 reviewer（安全、性能、代码质量、文档、发布管理、合规、Engineering Codex）并行，由一个 Review Coordinator 去重并判定严重度；顶级模型只给协调者，专家用更便宜的档位
- D. 由人类先评审，再由 LLM 复核

---

## 三、动手 / 代码题

**Q9.** 阅读 `score_problem_fit`：

```python
def score_problem_fit(inputs: ReviewerInputs) -> DimensionScore:
    files = inputs.diff_summary.get("touched", [])
    goal = inputs.goal.lower()
    keywords = [w for w in goal.split() if len(w) > 4]
    hits = sum(any(k in f.lower() for f in files) for k in keywords)
    score = min(2, hits)
    return DimensionScore("problem_fit", score, f"keyword hits across touched files: {hits}")
```

其余输入与 T-001 相同，只改 `touched`：

1. `touched=["docs/input_validation_signup_notes.md"]`（只写了一份笔记）——总分和结论是什么？
2. `touched=["app/auth/register.py"]`（真正的注册逻辑在这里）——总分和结论是什么？
3. 这说明了什么？如果换成 LLM 打分，需要哪些约束才能避免同样的问题？

**Q10.** 阅读 `score_verification`：

```python
def score_verification(inputs: ReviewerInputs) -> DimensionScore:
    exits = [rec.get("exit_code") for rec in inputs.feedback]
    if any(code is None for code in exits):
        return DimensionScore("verification_quality", 0, "feedback log has missing exit codes")
    if all(code == 0 for code in exits) and exits:
        return DimensionScore("verification_quality", 2, "all feedback exit zero")
    return DimensionScore("verification_quality", 1, "mixed exit codes in feedback")
```

1. `feedback=[]` 时得几分？note 是什么？对吗？
2. 讲义对这一维的提问是"Does the acceptance command actually prove the goal, or did it prove a weaker version?"。这个实现回答的是这个问题吗？它和 gate 是什么关系？
3. skill 规定"If the builder produces no verification report, refuse to run the reviewer"。写一个 `review_v2(inputs)`：没有 gate 报告或 gate 未通过时返回 `refused`，否则调用原 `review`。

**Q11.** skill 的 hard reject 要求"Every score must point at a file or trace entry"，讲义练习 3 要求增加 `confidence` 字段并在最低置信度 < 0.6 时拒绝输出报告。请：

1. 扩展维度结构，增加 `evidence: list[str]` 与 `confidence: float`；
2. 写 `finalize(task_id, dims, floor=0.6)`：任一维度缺证据或置信度低于阈值时返回 `needs_human` 并列出问题维度；否则按原规则给结论。
3. 用一组示例（其中 `assumptions` 置信度 0.55、`handoff_readiness` 没有证据）演示输出。

**Q12.** 讲义给出的位置偏差缓解方法是"evaluate both orderings and only count consistent wins"。下面是一个带位置偏差的模拟判官（`q` 代表真实质量）：

```python
def biased_judge(first, second):
    return "first" if first["q"] + 1 >= second["q"] else "second"
```

写 `consistent_compare(a, b, judge)`，并给出 A（q=5）对 B（q=5.5）、A（q=5）对 C（q=8）的结果。解释为什么"只计一致的胜出"能消除位置偏差、代价是什么。

---

## 四、面试高频题

**Q13.**（基础必考）为什么"写代码的 agent 不能给自己的工作打分"？reviewer 与 verification gate 各自负责什么？

**Q14.**（原理深挖）LLM-as-judge 有哪些系统性偏差？每种偏差如何缓解？为什么讲义说这些缓解是"设计要求而不是优化"？

**Q15.**（工程实践）请为你的项目设计一套 reviewer rubric：维度、锚点、证据要求、置信度、结论阈值、校准流程。

**Q16.**（场景设计）公司有数千个仓库，每天上千个 agent 产生的 MR。请设计一个可扩展的评审系统，并说明模型档位、去重、成本、延迟方面的取舍。

**Q17.**（追问型）reviewer 发现证据不足，想让 builder 再跑一个测试（讲义练习 5 的"request more evidence"）。如何设计这个交互才不会陷入无限循环？如果 reviewer 与 builder 的意见长期冲突，谁说了算？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Acceptance is necessary, not sufficient. The reviewer asks the questions acceptance cannot ask: did this solve the right problem?"gate 只能检查确定性的事实（验收是否运行、规则是否通过、scope 是否保持），无法判断"做的是不是对的事"。A 错，gate 按设计正确工作；B 错，讲义明确 gate 不用 LLM，LLM 判断放在 reviewer；C 错，如果验收标准本身证明的是"更弱的版本"，再多测试也是在证明错误的目标。

### Q2 — 答案：B

讲义："You can run the reviewer with the same model as the builder. The discipline is the role separation: different system prompt, different inputs, no write access to the diff. The change in posture is the change in signal."A 错，讲义的"Two-model pairing"只是一种可选的生产模式；C 错，"Mixing roles defeats the gap"；D 错，skill 把"Sharing the builder's system prompt"列为 hard reject（"Same model is fine; same prompt is not"）。

### Q3 — 答案：A

```python
    has_zero = any(d.score == 0 for d in dims)
    if has_zero or total < 5:
        verdict = "hard_fail"
    elif total >= 7:
        verdict = "pass"
    else:
        verdict = "soft_fail"
```

T-002 总分 5，不满足 `total < 5`；若没有 0 分维度，会落到 `soft_fail`。真正触发 hard fail 的是 `problem_fit = 0`（改的是 `docs/api.md`，不含任何关键词）。B 错，`5 < 7` 只决定"不是 pass"；C 错，`verification_quality=2` 只是说明测试退出码为 0；D 错，越界 warn 只让 `scope_discipline` 降为 1。补充：在这套规则下，soft fail 只可能出现在总分 5 或 6 且没有 0 分的情况（穷举 3⁵ 种组合验证）。

### Q4 — 答案：C

`goal.split()` 中长度 > 4 的词是 `['input', 'validation', 'signup']`（实测）。`app/signup.py`、`tests/test_signup.py` 只包含 `signup`，命中 1 个，`min(2, 1) = 1`。正确的改动只拿到 1 分，这正暴露了关键词匹配的粗糙（见 Q9）。A 错，分数与文件数无关；B 错；D 错，满分是 2。

### Q5 — 答案：B

讲义："position bias (GPT-4 ~40% inconsistent on (A,B) vs (B,A) ordering), verbosity bias (~15% score inflation toward longer outputs), self-preference (judges prefer outputs from the same model family), authority (judges over-rate references to known authors)."A 把"更长"说成了"更短"；C 把"同一家族"说成了"其他家族"；D 把"高估"说成了"低估"。对应的缓解：两种顺序都评、只计一致胜出；用明确奖励简洁的 1–4 量表；在不同模型家族间轮换判官；打分前去掉作者名。

### Q6 — 答案：D

讲义："A 10-20 task historical set with known correct verdicts. Run the reviewer over it on every prompt change. If agreement with the historical record falls below 80%, the rubric needs revision before the reviewer ships."A 错，每次改 prompt 都要重跑；B 错，规模是 10–20 个真实历史任务；C 错，校准的对象是 rubric 与 prompt。skill 还规定：已关闭任务少于 3 个时，不得声称 rubric 已校准，应把最初的报告保存为校准集。

### Q7 — 答案：A

实测：`gate failed: 9 pass`；传入 `verdict={}`（根本没有 gate 报告）同样是 9 分 `pass`。`score_scope_discipline` 只在 `verdict["findings"]` 中查找 `scope.forbidden` / `scope.off_scope`，其他维度不看 verdict。这违背了 skill 的拒绝规则"If the builder produces no verification report, refuse to run the reviewer. Acceptance must hold before judgment is worth asking for."B、D 是应有的行为（D 更符合 skill），但代码没有实现；C 错，代码用 `.get` 读取，不会抛错。修复见 Q10。

### Q8 — 答案：C

讲义："Up to seven specialist reviewers (security, performance, code quality, docs, release management, compliance, Engineering Codex) ran in parallel under a Review Coordinator that deduplicated findings and judged severity. Top-tier model reserved exclusively for the coordinator; specialists ran on cheaper tiers."以及数据：30 天 131,246 次评审、48,095 个 MR、5,169 个仓库，评审耗时中位数 3 分 39 秒。A 是讲义说"只适合单仓库"的做法；B 缺少协调者去重；D 不是讲义描述的架构。

### Q9 — 参考答案

实测结果：

| touched | problem_fit | 总分 | 结论 |
|---------|-------------|-----|------|
| `docs/input_validation_signup_notes.md` | 2（3 个关键词全中） | **10** | `pass` |
| `app/auth/register.py` | 0 | 8 | **`hard_fail`** |

1. 只写了一份文件名里带关键词的笔记，拿到满分 10、`pass`。
2. 改对了真正的代码（只是文件名用了同义词 register），因为 `problem_fit = 0` 而被判 `hard_fail`。
3. 结论：
   - **按文件名做关键词匹配，既能被刷分，也会误杀**：它衡量的是"文件名像不像目标"，而不是"改动是否解决了问题"。builder 只要知道规则，就能通过起文件名骗过 reviewer——这正是讲义要把 builder 与 reviewer 分开的原因之一（被评估者不应能左右评估方式）。
   - 讲义也承认这些函数是"stub-grade ... real implementations would call an LLM"，结构可以保留，判断要换掉。
   - 换成 LLM 打分时的约束：rubric 每一档都有锚点描述（如"2 = diff 直接修改了 goal 所述行为，并有测试覆盖该行为；1 = …；0 = …"，skill 的 hard reject："Score from 0 to 2 without anchors collapses to vibes"）；每个分数必须引用证据（diff 中的具体行、feedback 记录）；输入是 goal、合同、**diff 内容**而不只是文件名；reviewer 的 prompt 与 builder 不同；用校准集验证一致率。

### Q10 — 参考答案

1. `feedback=[]` 时，`any(...)` 为 False；`all(...) and exits` 中 `exits` 为空列表，整体为假；落到最后一行，得 **1 分**，note 为 `"mixed exit codes in feedback"`（实测）。这是错误的：没有任何运行记录意味着没有任何验证证据，应得 0 分，且 note 具有误导性。另外，"先失败后重试成功"也会被判 1 分（"mixed"），而这是正常的工作流程。
2. 不是。讲义的问题是"验收命令是否真的证明了目标，还是只证明了一个更弱的版本"——例如目标是"拒绝短密码"，测试却只断言"返回了 4xx"。这需要对照 goal 阅读测试内容。代码只看退出码，**重做了 gate 已经证明过的事**，而讲义明确说"don't ask the reviewer to redo what the gate already proves"。
3. 参考实现（已运行）：

   ```python
   def review_v2(inputs):
       v = inputs.verdict
       if not v or "passed" not in v:
           return {"task_id": inputs.task_id, "verdict": "refused", "reason": "no verification report"}
       if v["passed"] is not True:
           return {"task_id": inputs.task_id, "verdict": "refused", "reason": "gate not green; fix acceptance first"}
       r = review(inputs)
       return {"task_id": r.task_id, "verdict": r.verdict, "total": r.total}
   ```

   实测：`verdict={}` → `refused: no verification report`；`passed=False` → `refused: gate not green`；`passed=True` → `pass, 9`。顺序很重要：先让便宜的确定性 gate 把关，再花 LLM 成本做语义评审。

### Q11 — 参考答案

```python
@dataclass
class Dim:
    name: str
    score: int
    note: str
    evidence: list = field(default_factory=list)   # 例如 "diff:app/signup.py#L10-30"、"feedback_record.jsonl#cid=abc"
    confidence: float = 1.0

def finalize(task_id, dims, floor=0.6):
    missing = [d.name for d in dims if not d.evidence]
    low = [d.name for d in dims if d.confidence < floor]
    if missing or low:
        return {"task_id": task_id, "verdict": "needs_human",
                "missing_evidence": missing, "low_confidence": low}
    total = sum(d.score for d in dims)
    verdict = ("hard_fail" if any(d.score == 0 for d in dims) or total < 5
               else "pass" if total >= 7 else "soft_fail")
    return {"task_id": task_id, "verdict": verdict, "total": total}
```

实测输出（`assumptions` 置信度 0.55、`handoff_readiness` 无证据）：

```text
{'task_id': 'T', 'verdict': 'needs_human', 'missing_evidence': ['handoff_readiness'], 'low_confidence': ['assumptions']}
```

补齐证据、把置信度提到 ≥ 0.7 后：`{'verdict': 'pass', 'total': 9}`。

要点：讲义 Key Terms 的"Confidence floor: Refuse to emit a verdict when the rubric is uncertain"；skill："If the reviewer is asked to score below a minimum confidence, refuse and surface the uncertain dimension to a human."置信度由 LLM 自报时并不可靠，可以用多次采样的一致性、或两个不同家族判官的分歧来估计。

### Q12 — 参考答案

```python
def consistent_compare(a, b, judge):
    r1 = judge(a, b)                       # a 在前
    r2 = judge(b, a)                       # b 在前
    win1 = a if r1 == "first" else b
    win2 = b if r2 == "first" else a
    return win1["id"] if win1 is win2 else "tie"
```

实测：`biased_judge(A, B) == "first"`、`biased_judge(B, A) == "first"`——两种顺序都选"放在前面的那个"，典型的位置偏差；`consistent_compare(A, B) == "tie"`；`consistent_compare(A, C) == "C"`（质量差距足够大，两种顺序都选 C）。

- **为什么有效**：位置偏差在两种顺序下方向相反（总偏向第一个），只有"无论放在哪都赢"的一方才算赢，偏差带来的胜利会互相抵消成平局。
- **代价**：调用次数翻倍；接近的候选更多地被判平局（信号变少）；它只消除位置偏差，对冗长偏差、自我偏好无效，需要配合其他缓解手段（简洁性量表、跨家族判官、去作者名）。

### Q13 — 参考回答要点

- **为什么不能自评**：builder 带着自己的假设和叙述去看 diff，会确认自己的判断（"Looks good"）；它知道自己想做什么，容易把"想做的"当成"做到的"；同一上下文里难以切换到怀疑的姿态。讲义："The gap between builder and reviewer is where most reliability lives."
- **角色分离**：不同 system prompt、不同目标、只读访问 builder 产物；同一模型可以当两个角色。
- **分工**：gate（第 38 节）——确定性事实：验收是否运行且退出 0、规则、scope、覆盖率；reviewer——语义判断：问题是否对、scope 是否有意扩大、假设是否写下、验收是否真的证明了目标、handoff 是否可用。
- 加分点：reviewer 输出的是给人看的报告——"human review starts from a written report instead of a blank page"；reviewer 应在 gate 通过后才运行。

### Q14 — 参考回答要点

| 偏差 | 表现（讲义数据） | 缓解 |
|------|---------------|------|
| 位置偏差 | GPT-4 在交换顺序后约 40% 不一致 | 两种顺序都评，只计一致胜出（Q12） |
| 冗长偏差 | 对更长输出约 15% 的分数膨胀 | 使用明确奖励简洁的 1–4 量表；锚点里写清"冗余扣分" |
| 自我偏好 | 偏爱同一模型家族的输出 | 判官在不同模型家族间轮换；builder 与 reviewer 用不同家族 |
| 权威偏差 | 高估引用知名作者的内容 | 打分前去掉作者名等身份信息 |

- **为什么是设计要求**：这些偏差是系统性的、可复现的，不是偶发噪声；如果不在架构上处理，reviewer 的分数会稳定地偏向某些输出，而校准集也会把偏差"固化"进阈值。
- 加分点：用校准集测量偏差的实际大小；引用"Agent-as-a-Judge"思路——用 agent 评 agent 时，也要给判官工具去验证证据，而不是只读文本。

### Q15 — 参考回答要点

- **维度**：讲义五维 + 一个领域维度（讲义练习 1，如支付系统的"金额与幂等性"），并说明为什么不能被前五维吸收。
- **锚点**：每维 0/1/2 各写一句可判定的描述，例如 handoff readiness：2 = 任务已关闭、`next_action` 明确、无未提交改动；1 = 有 `next_action` 但任务未关闭；0 = 无 `next_action`。
- **证据**：每个分数引用 diff 行、feedback 的 `command_id`、gate 报告路径；没有证据的分数不计。
- **置信度**：每维一个置信度，最低维度 < 0.6 → `needs_human`。
- **阈值**：< 7 soft fail（builder 修）；< 5 或任一维 0 → hard fail（停下交给人）。
- **校准**：10–20 个历史任务；每次 prompt/rubric 改动都重跑；一致率 < 80% 先改 rubric；少于 3 个已关闭任务时不得声称已校准（skill）。
- **报告路径**：`outputs/review/<task_id>.json`，CI 把报告贴到 PR 评论。
- 常见误区：只有分数没有锚点和证据；用 reviewer 重新检查退出码。

### Q16 — 参考回答要点

- **架构**：专家池（安全、性能、代码质量、文档、发布、合规……）并行，每个专家 prompt 小而专；协调者负责去重、合并、判定严重度（讲义 Cloudflare 案例）。
- **模型档位**：专家用便宜档位；只有协调者用顶级模型——"cheap specialists, expensive coordinator"。
- **路由**：根据 diff 涉及的路径决定启用哪些专家（只改文档就不跑性能专家），控制成本与延迟。
- **前置条件**：gate 不绿不评审，避免在注定失败的改动上花钱。
- **延迟目标**：讲义数据显示中位数约 3 分 39 秒，说明并行专家 + 协调者可以做到分钟级。
- **质量保障**：每个专家都有自己的校准集；监控误报率与被人类推翻的比例；偏差缓解（顺序、家族轮换）。
- 常见误区：一个大 reviewer 跑全部 rubric（讲义："works for solo repos"），规模一大就既慢又贵、还容易遗漏专业问题。

### Q17 — 参考回答要点

- **请求更多证据的设计**：
  - reviewer 只能请求**具体**的证据（某条命令、某个测试），并说明它要回答哪个维度；
  - 设置上限：每个任务最多 N 次请求（如 2 次），同一请求不重复；超过上限 → `needs_human`；
  - 指数退避或"每次请求必须带来新的证据"，否则停止；
  - 请求与结果都写入 feedback 记录，用 `parent_command_id` 关联，便于审计。
- **意见冲突谁说了算**：二者都不是最终决定者——人类签字（讲义流程图的终点是"Human Sign-Off"）。reviewer 的 hard fail 会停下并上报给人；builder 不能"说服" reviewer 改分，只能产出新的证据或修改。
- **长期冲突**：说明 rubric、合同或验收标准有问题——把这些案例加入校准集，修订 rubric 或合同模板。
- 常见误区：让 reviewer 直接改代码"省一轮"（违反只读原则），或让 builder 与 reviewer 无限对话直到一致。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：reviewer 的前置条件与输入之一；确定性检查与语义评审的分工。
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../05-self-refine-and-critic/docs/zh.md)：单 agent 自我评审的基线，本节在其基础上做角色分离。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：校准集与评估集的构建方法。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：scope discipline 一维的依据。
- [阶段 14 · 25 多 Agent 辩论与协作](../../25-multi-agent-debate/docs/zh.md)：多个 agent 互相评判的另一种形式。

### 本节被哪些后续内容用到
- [阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：review 报告被打包进 handoff 交接包。
- [阶段 14 · 41 在真实代码仓库中使用工作台](../../41-workbench-for-real-repos/docs/zh.md)：在接近真实的任务上端到端演练 builder/reviewer 分离。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)、[阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../17-claude-agent-sdk/docs/zh.md)：用 handoff / subagent 实现 reviewer 角色。
- [阶段 16 · 11 Handoffs 与例程：无状态 Orchestration](../../../16-multi-agent-and-swarms/11-handoffs-and-routines/docs/zh.md)：多 agent 之间的交接模式。
- [阶段 19 · 55 Critic 评审循环](../../../19-capstone-projects/55-critic-loop/docs/zh.md)：综合项目中的评审循环。

### 延伸关键词
`builder / reviewer separation` · `LLM-as-a-judge` · `rubric anchors` · `position bias` · `verbosity bias` · `self-preference` · `calibration set` · `confidence floor` · `specialist reviewers` · `review coordinator` · `Hybrid Norm` · `Agent-as-a-Judge`
