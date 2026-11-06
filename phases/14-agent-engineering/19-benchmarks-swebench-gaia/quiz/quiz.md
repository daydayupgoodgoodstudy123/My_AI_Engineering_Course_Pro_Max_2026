# 测验 · 基准评测：SWE-bench、GAIA、AgentBench（Benchmarks: SWE-bench, GAIA, AgentBench）

> **阶段 14 · Agent 工程 · 第 19 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | SWE-bench 构成 | Jimenez et al.（ICLR 2024 oral）：来自 12 个流行 Python 仓库的 2,294 个真实 GitHub issue；输入是修复前的代码库 + issue 描述，输出是 patch |
| 2 | FAIL_TO_PASS / PASS_TO_PASS | 打 patch 后跑仓库测试：原本失败的 FAIL_TO_PASS 测试必须变为通过，原本通过的 PASS_TO_PASS 测试必须仍然通过 |
| 3 | 为什么用单元测试把关 | 测试是可执行、可复现的判据，不依赖与参考答案的文本相似度或 LLM 评委 |
| 4 | SWE-agent | Yang et al. 2024，发布时 12.5%，关键在 agent-computer interface（模型能理解的编辑与搜索命令） |
| 5 | SWE-bench Verified | OpenAI，2024 年 8 月，人工筛选的 500 题子集，去掉含糊 issue、不可靠测试、修复方式不明确的任务 |
| 6 | 污染（contamination） | 超过 94% 的 issue 早于多数模型的训练截止；SWE-bench+ 发现 32.67% 的成功 patch 存在 issue 文本泄露答案，31.08% 因测试覆盖弱而可疑 |
| 7 | GAIA | Mialon et al.，2023 年 11 月；466 题，300 题保留给私有排行榜；人类 92%、带插件的 GPT-4 15%；三个难度级别，Level 3 需要跨模态的长工具链 |
| 8 | AgentBench | Liu et al.（ICLR 2024）；讲义：8 个环境横跨代码、游戏、网页与开放生成，多轮交互；主要发现是长程推理、决策与指令遵循是开源模型追赶商业模型的瓶颈 |
| 9 | 基准不测什么 | 真实运行成本（token、墙钟时间）、对抗条件下的安全行为、你的领域表现、尾部失败（最差的 1%） |
| 10 | 三种误用 | 只看单一数字、报告 SWE-bench 却不提 Verified / SWE-bench+、把基准当开发目标 |

### 核心技能（能动手做到）

- [ ] 说清 SWE-bench 的评测流程，并解释 FAIL_TO_PASS 与 PASS_TO_PASS 各自防的是什么
- [ ] 读懂 `run_task` 的判定逻辑，构造反例说明"按净变化计数"的漏洞，并改成绝对判据
- [ ] 手算 `gaia_level` 对任意问题的打分，指出关键词计数分类器的误判来源
- [ ] 实现一个简单的 solution-leakage 检查（issue 文本 vs patch 新增行）
- [ ] 从 step / cost 列表计算 P50 / P75 / P95，替代"单一通过率"做报告
- [ ] 为一个具体产品挑选合适的基准组合，并说明还需要哪些自定义评测

---

## 二、基础自测（选择题）

**Q1.** SWE-bench 判定一个 patch "resolved" 的依据是：

- A. patch 少于 200 行
- B. 与参考 patch 的 BLEU 分数超过阈值
- C. 另一个 LLM 评委认为修复合理
- D. 打 patch 后运行仓库测试：FAIL_TO_PASS 测试由失败变为通过，PASS_TO_PASS 测试仍然通过

**Q2.** 关于 SWE-bench Verified，正确的是：

- A. 它把 SWE-bench 扩展到了 Java、Go 等更多语言
- B. OpenAI 于 2024 年 8 月发布的 500 题人工筛选子集，去掉了含糊的 issue、不可靠的测试和修复方式不明确的任务
- C. 它已被证明完全没有污染
- D. 它改用 LLM 评委代替单元测试

**Q3.** SWE-bench+ 对成功 patch 的审计发现：

- A. 32.67% 的成功 patch 存在 issue 文本泄露答案，31.08% 因测试覆盖薄弱而可疑
- B. 没有发现任何污染
- C. 所有成功 patch 都来自模型记忆
- D. 成功 patch 平均超过 1000 行

**Q4.** 关于 GAIA，下列说法正确的是：

- A. 对人类很难、对 AI 很容易
- B. 只包含单轮、纯文本的问答
- C. 466 道题，人类正确率约 92%，带插件的 GPT-4 约 15%；分三个难度级别，Level 3 需要跨模态的长工具链
- D. 专门评测代码修复能力

**Q5.** 讲义总结的 AgentBench 主要发现是：

- A. 开源模型在所有环境上都已超过商业模型
- B. 长程推理、决策与指令遵循是开源 LLM 追赶商业模型的主要瓶颈
- C. 代码环境是唯一有区分度的环境
- D. 多轮交互对结果没有影响

**Q6.** 运行 `code/main.py`，任务 `t003` 的结果是 `FAIL_TO_PASS: 1/1`、`PASS_TO_PASS: 1/2`、`resolved: False`。原因是：

- A. patch 没有修好 counter
- B. multiplier 被改坏了
- C. 任务定义无效，FAIL_TO_PASS 测试在打 patch 前就已通过
- D. patch 把 `flag` 从 `True` 改成了 `False`，打破了原本通过的 "flag stays true" 测试

**Q7.** `gaia_level("Search for the Wikipedia article on ReAct and extract the first author.")` 返回几级？

- A. Level 2：steps = 2（"and" 计 1 再加 1）、modalities = 0、tools = 2（search、extract），总分 4
- B. Level 1：只有一个问题，总分 1
- C. Level 3：包含 Wikipedia 这个外部来源，总分 6
- D. Level 2：steps = 1、modalities = 1、tools = 1，总分 3

**Q8.** 讲义认为下列哪一项是这三个基准**不**能衡量的？

- A. patch 是否让 FAIL_TO_PASS 测试通过
- B. 每个任务的成败
- C. 真实运行成本（token、墙钟时间）、对抗条件下的安全行为、你自己领域的表现以及尾部失败
- D. 多轮交互中的决策能力

---

## 三、动手 / 代码题

**Q9.** 阅读 `run_task` 的判定逻辑：

```python
    ftp_pre = sum(1 for _, check in task.fail_to_pass if check(state))
    ptp_pre = sum(1 for _, check in task.pass_to_pass if check(state))

    new_state = task.patch(dict(state))

    ftp_post = sum(1 for _, check in task.fail_to_pass if check(new_state))
    ptp_post = sum(1 for _, check in task.pass_to_pass if check(new_state))

    ftp_fixed = ftp_post - ftp_pre
    ptp_broke = ptp_pre - ptp_post
    resolved = (ftp_post == len(task.fail_to_pass)) and (ptp_broke == 0)
```

1. 构造一个任务：PASS_TO_PASS 有两个测试 A、B，打 patch 前 A 通过、B 失败；patch 把 A 改坏、把 B 修好，并修好 FAIL_TO_PASS 测试。`run_task` 会判 `resolved` 为什么？为什么这是错的？
2. 再构造两个让 `resolved=True` 的错误情形：一个是 PASS_TO_PASS 测试前后都失败；一个是 FAIL_TO_PASS 测试在打 patch 前就已经通过、patch 什么也没做。
3. 改写为 SWE-bench 式的绝对判据，并在评测前校验任务本身是否有效。`ftp_fixed` 这个变量起作用了吗？

**Q10.** `gaia_level` 用关键词计数估计难度：

```python
def gaia_level(question: str) -> int:
    steps = sum(1 for w in question.lower().split()
                if w in {"then", "after", "finally", "next", "and"}) + 1
    modalities = sum(word in question.lower() for word in
                     ("image", "video", "audio", "pdf", "chart", "graph"))
    tools = sum(word in question.lower() for word in
                ("search", "look up", "find", "visit", "extract"))
```

请手算以下问题的 `(steps, modalities, tools, level)`，并解释每个误判的来源：

1. `"Summarize this paragraph about findings."`
2. `"Salt and pepper and oil and vinegar and lemon?"`
3. `"What year did the author of the most-cited 2017 attention paper, who later founded a startup, get their PhD; then, compute the difference from 2024."`

**Q11.** 讲义练习 3 与 `outputs/skill-benchmark-harness.md` 要求实现 solution-leakage 检查："pattern-match the issue text against the produced patch; flag >=30% overlap"。

1. 写一个 `leakage_ratio(issue_text, diff) -> float`：统计 unified diff 中**新增行**（以 `+` 开头、排除 `+++` 文件头与空行）有多大比例原样出现在 issue 文本里。
2. 对下面的 issue 与 diff，计算比值并判断是否标记。

```text
issue:
counter is off by one. I think the fix is:
    return count + 1
in utils.py
```

```diff
--- a/utils.py
+++ b/utils.py
@@ -1,2 +1,3 @@
 def counter(count):
-    return count
+    # fix off-by-one
+    return count + 1
```

3. 这种"行级精确匹配"会漏掉哪些泄露、又会误报哪些情况？

**Q12.**（计算题）你的 coding agent 在 10 个已解决任务上的步数为 `[3, 5, 4, 12, 7, 6, 25, 4, 5, 8]`，每任务成本（美元）为 `[0.12, 0.20, 0.15, 0.90, 0.33, 0.25, 2.10, 0.14, 0.18, 0.40]`。

1. 用 nearest-rank 方法（第 p 百分位 = 排序后第 ⌈p/100 × n⌉ 个）计算步数与成本的 P50 / P75 / P95，以及平均值。
2. 某模型在完整 SWE-bench 上报告 50%。若只剔除 SWE-bench+ 所说"泄露答案"的那 32.67% 成功 patch，分数约为多少？若再剔除 31.08% 弱测试的成功 patch（假设两类不重叠），又约为多少？这与讲义"50% 可能变成 35%"的说法有什么关系？
3. SWE-bench Verified 占原始 SWE-bench 的比例是多少？GAIA 私有排行榜题目占全部题目的比例是多少？

---

## 四、面试高频题

**Q13.**（基础必考）介绍 SWE-bench 的评测方式。为什么它用 FAIL_TO_PASS 和 PASS_TO_PASS 两组测试把关，而不是比较与参考 patch 的相似度？

**Q14.**（原理深挖）基准污染有哪些形态？SWE-bench Verified 和 SWE-bench+ 分别解决了什么问题？你如何判断一个 SWE-bench 分数是否可信？

**Q15.**（工程实践）请为你们公司的代码库搭建一个 SWE-bench 风格的内部评测 harness，说说关键设计。

**Q16.**（场景设计）你们在做一个"通用研究助理"agent（会搜索网页、读 PDF、做表格计算），另一个团队在做 coding agent。各自应该用哪些基准？还需要补什么评测？

**Q17.**（追问型）候选人说"我们的 agent 在 SWE-bench 上拿了 50%"。作为面试官，你会追问哪些问题？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Evaluator: apply patch, run the repo's test suite. The patch must flip FAIL_TO_PASS tests (previously failing, now passing) without breaking PASS_TO_PASS tests." A、B、C 都不是 SWE-bench 的判据：行数与修复质量无关；文本相似度会惩罚等价但写法不同的正确修复；LLM 评委不可复现。

### Q2 — 答案：B

讲义："OpenAI, Aug 2024. Human-curated 500-task subset. Removes ambiguous issues, unreliable tests, and tasks where the fix was unclear." C 错，讲义明确说 "Verified is cleaner but not contamination-free"；A、D 无依据，Verified 仍是 Python 仓库、仍用测试判定。

### Q3 — 答案：A

讲义："SWE-bench+ found 32.67% of successful patches leaked solutions in the issue text (model saw the fix in the description), and 31.08% were suspicious due to weak test coverage." 其他选项都是夸大或否定。

### Q4 — 答案：C

讲义："466 questions; 300 retained for the private leaderboard"，"conceptually simple for humans (92%) but hard for AI (GPT-4 with plugins: 15%)"，"Three difficulty levels; Level 3 requires long tool chains across modalities." A 说反了；B 错，GAIA 测试多模态、网页与工具使用；D 是 SWE-bench 的定位，讲义特别提醒 "Do not confuse with code-specific benchmarks."

### Q5 — 答案：B

讲义："Primary finding: long-term reasoning, decision-making, and instruction following are the blockers for OSS LLMs catching up to commercial." A 与结论相反；C、D 无依据，AgentBench 的特点恰恰是多环境、多轮。

附注：讲义列出的环境是"code (Bash, DB, KG), games (Alfworld, LTP), web (WebShop, Mind2Web), and open-ended generation"，具名的只有 7 个。按 AgentBench 原论文，8 个环境是 Operating System、Database、Knowledge Graph、Digital Card Game、Lateral Thinking Puzzles、House-Holding（基于 ALFWorld）、Web Shopping、Web Browsing（基于 Mind2Web）——讲义漏了 Digital Card Game，"open-ended generation" 并不是其中的环境。引用时建议以原论文为准。

### Q6 — 答案：D

`t003` 的 patch 是 `{**s, "counter": 2, "flag": False}`：counter 从 1 变 2，满足 "counter > 1"（FAIL_TO_PASS 1/1，A 错）；multiplier 没动（B 错）；但 `flag` 被改成 `False`，"flag stays true" 由通过变为失败，PASS_TO_PASS 只剩 1/2，`ptp_broke = 2 - 1 = 1 ≠ 0`，所以 `resolved=False`。这正是任务描述 "agent overreaches and breaks a passing test"——修了 bug 却引入回归。C 错：打 patch 前 counter = 1，"counter > 1" 是失败的，任务有效。

### Q7 — 答案：A

已实际运行验证（输出 `[Level 2]`）：

- `steps`：按空白切词后只有 `"and"` 在集合里，计 1，再 `+1` 得 2；
- `modalities`：没有 image/video/audio/pdf/chart/graph，0；
- `tools`：子串 `"search"` 与 `"extract"` 命中，2；
- 总分 4，落在 `3..5` 区间 → Level 2。

D 的拆分不对；B、C 的分数都不符合代码逻辑。

### Q8 — 答案：C

讲义 "What these do not measure"：真实运行成本（tokens、wall-clock）、对抗条件下的安全行为、你自己领域的表现（用第 30 节的自定义评测）、尾部失败（"benchmarks average; production operators care about the worst 1%"）。A、B 正是 SWE-bench 测量的；D 是 AgentBench 测量的。

### Q9 — 参考答案

1. 已实际运行验证：设 `state_before = {"a": 1, "b": 0, "c": 0}`，patch 为 `{**s, "a": 0, "b": 1, "c": 1}`，FAIL_TO_PASS = `[c == 1]`，PASS_TO_PASS = `[a == 1, b == 1]`。则 `ptp_pre = 1`、`ptp_post = 1`、`ptp_broke = 0`，结果 `TaskResult(..., ptp_passed=1, ptp_total=2, resolved=True)`。
   这是错的：测试 A 被 patch 打坏了，这是回归；B 的"变好"只是在**数量**上抵消了 A 的损失。按净变化计数会让"破坏一个、修好另一个"的 patch 蒙混过关。
2. 两个已验证的错误情形：
   - PASS_TO_PASS 测试 `a == 1` 在打 patch 前后都失败（`state_before = {"a": 0, "c": 0}`）：`ptp_pre = ptp_post = 0`，`ptp_broke = 0`，`resolved=True`，尽管 PASS_TO_PASS 是 0/1；
   - FAIL_TO_PASS 测试在打 patch 前就已通过（`state_before = {"c": 1}`），patch 是恒等函数 `lambda s: s`：`ftp_post == 1 == len`，`resolved=True`——一个什么都没做的 patch 被判为解决。
3. 绝对判据 + 任务校验（已验证：第 1 小题的反例被判 `resolved=False`，第 2 小题的无效任务在评测前就被拒绝）：

```python
def run_task_strict(task: Task) -> TaskResult:
    state = dict(task.state_before)
    ftp_pre = [check(state) for _, check in task.fail_to_pass]
    ptp_pre = [check(state) for _, check in task.pass_to_pass]
    if any(ftp_pre) or not all(ptp_pre):          # 任务本身必须有效
        raise ValueError(f"{task.tid}: invalid task (FTP must fail and PTP must pass before patch)")
    try:
        new_state = task.patch(dict(state))
    except Exception:
        return TaskResult(task.tid, 0, len(ftp_pre), 0, len(ptp_pre), False)   # patch 崩溃 = 未解决
    ftp_post = [check(new_state) for _, check in task.fail_to_pass]
    ptp_post = [check(new_state) for _, check in task.pass_to_pass]
    return TaskResult(task.tid, sum(ftp_post), len(ftp_post), sum(ptp_post), len(ptp_post),
                      resolved=all(ftp_post) and all(ptp_post))
```

   要点：resolved 必须是"**每一个** FAIL_TO_PASS 通过 且 **每一个** PASS_TO_PASS 通过"的绝对条件；任务有效性（FTP 在修复前失败、PTP 在修复前通过）应在构建数据集时验证——这也是 SWE-bench Verified 去掉"不可靠测试"的意义。原代码中 `ftp_fixed` 被计算后从未使用；另外 patch 抛异常（例如 `KeyError`）会让整个 harness 崩溃，也应该捕获并记为未解决。

### Q10 — 参考答案

（已实际运行验证）

| 问题 | steps | modalities | tools | 总分 | level | 误判原因 |
|------|-------|-----------|-------|------|-------|---------|
| 1 | 1 | 1 | 1 | 3 | 2 | 子串匹配：`"paragraph"` 含 `"graph"`、`"findings"` 含 `"find"`；一个一步就能回答的问题被抬到 Level 2 |
| 2 | 5 | 0 | 0 | 5 | 2 | `"and"` 被当作"步骤连接词"，但这里只是列举；4 个 `and` 让分数虚高 |
| 3 | 1 | 0 | 0 | 1 | 1 | 真正的多跳问题（找论文 → 找作者 → 找创业经历 → 找 PhD 年份 → 计算），但 `"then,"` 带逗号，`split()` 后不等于 `"then"`，没有被计数；也没有出现工具关键词 |

问题根源：

- `steps` 用 `split()` 切词，标点粘在词上导致漏数；而 `modalities`、`tools` 用子串 `in`，又导致误数——两种匹配方式不一致；
- 关键词数量只是表面特征，与真实需要的推理/工具步数没有因果关系。
- 真实 GAIA 的难度级别是题目作者根据解题所需步骤和工具人工标注的，不是从问题文本推断的。这个分类器只适合演示"深度 + 模态 + 工具 → 难度"的直觉（讲义："GAIA: depth + modalities + tools -> difficulty level"）。改进方向：先用正则去掉标点再匹配词边界（`re.findall(r"\b\w+\b", ...)`），或者让 LLM 先把问题分解成子任务，再按子任务数与所需工具种类打分。

### Q11 — 参考答案

1. 参考实现：

```python
def leakage_ratio(issue_text: str, diff: str) -> float:
    added = [line[1:].strip() for line in diff.splitlines()
             if line.startswith("+") and not line.startswith("+++") and line[1:].strip()]
    if not added:
        return 0.0
    issue_lines = {l.strip() for l in issue_text.splitlines() if l.strip()}
    issue_norm = " ".join(issue_text.split())              # 压缩空白，便于行内匹配
    hits = sum(1 for l in added
               if l in issue_lines or " ".join(l.split()) in issue_norm)
    return hits / len(added)
```

2. 新增行有两条：`# fix off-by-one` 和 `return count + 1`。后者原样出现在 issue 中，前者没有，比值 `1/2 = 0.5 ≥ 0.3`，**标记为疑似泄露**（已实际运行验证）。如果 issue 只写 "counter is off by one"，比值为 0。
3. 局限：
   - **漏报**：issue 用自然语言描述修复（"把返回值加一"）、变量名或缩进不同、修复被拆到多行时，精确匹配都抓不到；可以改用 token 级重叠（如新增 token 中出现在 issue 里的比例）或 AST 归一化后比较。
   - **误报**：很短或很通用的行（`return None`、`pass`、`}`）很容易"碰巧"出现在 issue 里；issue 中贴了**出错代码**而 patch 保留了其中部分行，也会被算成泄露。通常要过滤过短的行、只看与删除行不同的新增行，并结合人工复核。
   - SWE-bench+ 的结论来自对成功 patch 的人工审计，自动规则只能做初筛。

### Q12 — 参考答案

（已用 Python 计算）

1. 步数排序后为 `[3, 4, 4, 5, 5, 6, 7, 8, 12, 25]`，n = 10：
   - P50：⌈5⌉ = 第 5 个 → **5**；P75：⌈7.5⌉ = 第 8 个 → **8**；P95：⌈9.5⌉ = 第 10 个 → **25**；平均 **7.9**。
   - 成本排序后 `[0.12, 0.14, 0.15, 0.18, 0.20, 0.25, 0.33, 0.40, 0.90, 2.10]`：P50 **0.20**，P75 **0.40**，P95 **2.10**，平均 **约 0.477**。
   - 解读：平均值被一个 25 步、2.10 美元的长尾任务拉高；P95 是 P50 的 5 倍（步数）和 10 倍（成本）。讲义："SWE-bench 50% tells you less than the P50/P75/P95 cost + step distribution." 注意 n = 10 时 P95 就是最大值，样本太少时百分位非常不稳定。
2. 只剔除泄露：`50% × (1 − 0.3267) ≈ 33.7%`；再剔除弱测试（假设不重叠）：`50% × (1 − 0.3267 − 0.3108) ≈ 18.1%`。讲义"may score 35%"与"只剔除泄露"的量级相符；如果把弱测试也算进去，下降可能更多。真实情况取决于两类是否重叠以及具体模型，这里只是按比例的粗略估算，所以讲义要求 "Always report both"。
3. Verified：`500 / 2294 ≈ 21.8%`；GAIA 私有排行榜：`300 / 466 ≈ 64.4%`。

### Q13 — 参考回答要点

- **流程**：给 agent 修复前的代码库快照 + issue 描述 → agent 产出 patch → 在隔离环境中打 patch → 运行仓库测试套件。
- **两组测试**：
  - FAIL_TO_PASS：修复前失败、参考修复后通过的测试，证明 bug 真的被修好；
  - PASS_TO_PASS：修复前后都应通过的测试，证明没有引入回归。`outputs` 甚至认为 "breaking existing tests is a worse regression than missing the fix"。
- **为什么不用文本相似度**：同一个 bug 有许多等价修法，文本相似度会惩罚正确但写法不同的 patch，又会奖励"看起来像"但跑不通的 patch；测试是可执行、可复现的功能性判据。
- **局限**：测试覆盖弱时，错误 patch 也可能通过（SWE-bench+ 的 31.08%）；测试只能验证被测到的行为。
- 加分点：SWE-agent 的 12.5% 说明 agent-computer interface（编辑、搜索命令的设计）对结果影响巨大，不只是模型能力。

### Q14 — 参考回答要点

- **污染形态**：
  - 训练数据包含基准题目或答案（讲义：超过 94% 的 SWE-bench issue 早于多数模型训练截止）；
  - 任务本身泄露答案：issue 文本里直接写了修复方法（SWE-bench+：32.67%）；
  - 评估器太弱：测试覆盖不足，错误 patch 也能通过（31.08%）。
- **Verified 解决的是"任务质量"**：人工剔除含糊 issue、不可靠测试与修复不明确的任务，让分数更可信；但它不解决训练数据污染（"cleaner but not contamination-free"）。
- **SWE-bench+ 是"审计"**：揭示成功 patch 中有多少是因为泄露或弱测试，提醒分数可能虚高。
- **判断可信度**：是否同时报告 Verified 与审计后的数字；是否给出每任务结果、成本与步数分布；是否在训练截止之后的新任务上验证；任务与测试是否钉在特定 commit 上（`outputs`："If the tests are not pinned to a specific commit, refuse."）。
- 常见误区：把 Verified 的分数当作"无污染"的分数。

### Q15 — 参考回答要点

（对照 `outputs/skill-benchmark-harness.md`）

- **任务定义**：`(tid, description, state_before, fail_to_pass_tests, pass_to_pass_tests, solution)`，从历史 bug 修复 PR 中提取，测试与代码都钉在具体 commit。
- **任务校验**：在修复前 commit 上确认 FTP 失败、PTP 通过；在参考修复上确认全部通过（对应 Q9 的绝对判据）。
- **沙箱执行**：agent 的 patch 是不可信代码，必须在容器/沙箱中运行（`outputs` 硬拒绝："Harness that runs tests without a sandbox."）。
- **记录指标**：FTP/PTP 通过数、步数、token、墙钟时间、成本；报告每任务结果与 P50/P75/P95 分布，而非单一数字。
- **污染检查**：issue 文本与 patch 的重叠 ≥ 30% 时标记（Q11）。
- **CI 集成**：每个 PR 跑一遍，回归 ≥ 5% 时失败；保存历史以便比较。
- 加分点：任务集分为"开发集"与"留出集"，避免把基准当开发目标（讲义的 benchmark-as-development-target）。

### Q16 — 参考回答要点

- **通用研究助理**：GAIA（讲义："GAIA is what you run to measure 'generalist capability'"，使用私有排行榜划分）；关注 Level 3 的跨模态长工具链表现；AgentBench 的网页类环境可作补充。
- **coding agent**：SWE-bench Verified 为主，同时报告原始 SWE-bench 与审计后结果；AgentBench 的 Bash/DB 等环境用于多环境对比。
- **都要补的评测**：
  - 自己领域的任务集（第 30 节的评估驱动开发）——基准不衡量"你的领域"；
  - 成本与延迟分布、尾部失败（最差 1%）；
  - 对抗与安全测试（prompt injection、越权工具调用）；
  - 网页/桌面操作类产品还应看第 20 节的 WebArena、OSWorld。
- 常见误区：用 SWE-bench 分数去证明研究助理的能力，或用 GAIA 分数证明代码能力——讲义特别提醒不要混淆。

### Q17 — 参考回答要点

- 是哪个 SWE-bench？完整版、Verified 还是 Lite？有没有对照 SWE-bench+ 或其他审计？
- 是 pass@1 吗？跑了几次、方差多大？有没有对失败任务重试或人工挑选？
- 每任务的步数、token、成本、墙钟时间分布是怎样的？P95 是多少？
- 失败的 50% 都是什么类型？有没有引入回归（PASS_TO_PASS 失败）的 patch？
- 模型训练截止与任务时间的关系？在截止之后的新 issue 上表现如何？
- agent-computer interface、工具、提示词是否针对该基准专门调过？离开基准后在你们自己的代码库上效果如何？
- 加分点：能指出讲义的三种误用——单一数字、不提 Verified/SWE-bench+、把基准当开发目标——并说明为什么它们会误导决策。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 06 工具使用与 Function Calling](../../06-tool-use-and-function-calling/docs/zh.md)：讲义的先修，所有 agent 基准都建立在工具调用之上。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：步数（step count）指标统计的就是这个循环的迭代次数。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：模型层面的基准与评测框架。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：应用层评测的基本方法。

### 本节被哪些后续内容用到
- [阶段 14 · 20 基准评测：WebArena 与 OSWorld](../../20-benchmarks-webarena-osworld/docs/zh.md)：网页与桌面环境的 agent 基准，评估器从测试变成状态检查。
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../26-failure-modes-agentic/docs/zh.md)：基准中失败任务的分类与分析。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：讲义多次指向的"你自己领域的评测"。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：把 FAIL_TO_PASS / PASS_TO_PASS 思想用在日常 agent 工作流中。
- [阶段 15 · 09 自主 Coding Agent 生态概览（2026）](../../../15-autonomous-systems/09-coding-agent-landscape/docs/zh.md)：SWE-bench 分数在 coding agent 生态中的使用。
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../../19-capstone-projects/27-eval-harness-fixture-tasks/docs/zh.md)：综合项目中实现 fixture 任务评估 harness。

### 延伸关键词
`SWE-bench` · `SWE-bench Verified` · `SWE-bench Lite` · `SWE-bench+` · `FAIL_TO_PASS / PASS_TO_PASS` · `SWE-agent` · `agent-computer interface` · `GAIA` · `AgentBench` · `contamination` · `solution leakage` · `pass@1` · `P50/P95` · `held-out set`
