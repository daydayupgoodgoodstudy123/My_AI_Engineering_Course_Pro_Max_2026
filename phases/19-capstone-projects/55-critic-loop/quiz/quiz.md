# 测验 · Critic 评审循环（Critic Loop）

> **阶段 19 · 综合项目 · 第 55 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 收敛要靠工程设计 | 第一轮就说"很好"的 critic 是坏的，永远说"需要修改"的 critic 也是坏的；有用的 critic 会收敛，而收敛需要明确的停止规则 |
| 2 | 五个固定维度 | `clarity / novelty / evidence / methodology / related_work`，每个 0–10 分；分数是一个**向量**，而不是一段自由文本 |
| 3 | 结构化的 `Critique` | `round`、`scores`、`suggestions`、`reason`；每条 `Suggestion` 带 `dimension`、`target_section_id`、`edit`，修订器据此做定点修改 |
| 4 | 三种停止条件及顺序 | target（**五个维度全部** ≥ 8.0）→ plateau（均分连续两轮提升 ≤ 0.1）→ budget（达到最大轮数，默认 5）；先判者优先 |
| 5 | 为什么平台期看两轮 | 单轮持平可能是噪声；需要 `plateau_window + 1` 条 trace，即最早第 3 轮才可能判 plateau |
| 6 | 三方职责分离 | harness 管轮次、trace 和收敛判断；critic 管打分；reviser 管修改；Critic、Reviser 都用 `Protocol` 定义为可调用接口 |
| 7 | 确定性 critic | clarity = `3 + 平均正文长度/50`；novelty 由 `originality_tag` 决定（3/6/9）；evidence = `2 + 2×图引用数 + 1.5×引用数`；有 Method / Related Work 章节各得 9 分，否则 4 分 |
| 8 | trace 优先 | 每轮记录轮次、分数向量、均分、建议数、判决；"5 轮、分数不动、budget" 让人一眼看出是 critic 的问题而不是稿子的问题 |
| 9 | 代码的局限 | 收敛判断只看**均分**，看不到单维度回退；不保留历史最优稿；budget 时最终分数与返回的稿子不对应；修订器原地修改输入 |
| 10 | 代理指标会被"刷分" | 确定性 reviser 靠追加 `"x" * 80` 提高 clarity——critic 的打分规则一旦公开给 reviser，就会被直接优化（Goodhart 定律） |

### 核心技能（能动手做到）

- [ ] 给定每轮的分数向量，按 target → plateau → budget 的顺序手推循环在哪一轮、以什么原因停止
- [ ] 根据 `deterministic_score` 的公式，手算 demo 每一轮的五个分数
- [ ] 用 `typing.Protocol` 定义可替换的 critic / reviser 接口，并写出 stub 实现做单元测试
- [ ] 给循环加上"单维度回退检测"和"保留历史最优稿"
- [ ] 识别 critic 被 reviser 刷分的迹象，并设计更难被刷的评分方式
- [ ] 解释 LLM 作为 critic 时打分噪声对平台期检测的影响，并给出应对方法

---

## 二、基础自测（选择题）

**Q1.** 讲义为什么要求 critic 在五个固定维度上打分，而不是返回一段修改建议？

- A. 五个数字比一段文字更省 token
- B. 固定维度可以让 critic 不再需要模型
- C. 维度越多，循环收敛得越快
- D. 结构化的分数向量给了 harness 一份契约：可以逐维度追踪变化、判断是否收敛，而自由文本的批评是否被修订"回应"了无法验证

**Q2.** 一轮结束时，`CriticLoop.run` 检查停止条件的顺序是：

- A. target → plateau → budget
- B. budget → plateau → target
- C. plateau → target → budget
- D. 三者同时检查，取最先满足的那个（与顺序无关）

**Q3.** `plateau_window=2`（默认）。假设分数从第 1 轮起就完全不变，循环**最早**在第几轮判 plateau？

- A. 第 1 轮
- B. 第 2 轮
- C. 第 3 轮
- D. 第 4 轮

**Q4.** 某一轮论文有三个章节，正文长度分别为 92、237、225 个字符。`deterministic_score` 给出的 clarity 是：

- A. 3.22
- B. 6.69
- C. 7.23
- D. 10.0

**Q5.** 测试 `test_budget_exhaustion_when_no_progress` 使用分数恒为 4.0 的 critic、什么都不做的 reviser、`max_rounds=3`，断言 `result.reason in ("plateau", "budget")`。实际运行的结果是：

- A. `plateau`，在第 3 轮触发——同一轮 plateau 检查先于 budget，所以测试名所说的 budget 路径其实没有被测到
- B. `budget`，因为分数从未提高
- C. `target`
- D. 抛出 `ValueError`

**Q6.** 构造一个 critic：每轮 clarity +2、evidence −2，其余维度不变（第 1 轮全 5 分）。`max_rounds=5`、`target_score=8.0`。实际结果是：

- A. `budget`，因为一直没达到目标
- B. 第 2 轮检测到 evidence 回退并停止
- C. `target`，因为 clarity 达到了 9
- D. 第 3 轮以 `converged / plateau` 结束——均分始终是 5.0，循环只看均分，evidence 从 5 跌到 1 完全没有被发现

**Q7.** 用 `deterministic_critic` + `deterministic_reviser`，把 `target_score` 设为 9.5、`max_rounds=10` 运行 demo 论文。结果是：

- A. 第 5 轮 `target`，与默认设置一致
- B. 第 7 轮 `plateau`：novelty、methodology、related_work 最高只能到 9.0，目标不可达；且 critic 内部写死了"低于 8.0 才提建议"，第 5 轮起建议数为 0、分数不再变化
- C. 第 10 轮 `budget`
- D. 抛出异常，因为 9.5 超出了分数范围

**Q8.** 用确定性 critic/reviser、`max_rounds=2` 运行 demo，结果 `reason="budget"`、`final_scores` 中 clarity 为 6.69。对返回的 `result.paper` 重新调用 `deterministic_score`，clarity 是多少？为什么？

- A. 6.69，与 `final_scores` 一致
- B. 3.22，因为 budget 时返回的是原始稿件
- C. 7.23：最后一轮打分之后 reviser 又修改了一次稿子，但循环随即因预算用尽而结束，这次修改从未被打分，`final_scores` 与返回的稿子不对应
- D. 10.0

---

## 三、动手 / 代码题

**Q9.** 讲义说："A revision that raises clarity but tanks evidence is a regression on evidence, and the convergence check sees it." 但 Q6 显示代码的收敛判断只看均分：

```python
    def _plateau(self, trace: list[LoopTrace]) -> bool:
        if len(trace) < self.plateau_window + 1:
            return False
        recent = trace[-(self.plateau_window + 1):]
        for i in range(1, len(recent)):
            if recent[i].mean - recent[i - 1].mean > self.plateau_epsilon:
                return False
        return True
```

1. 除了 Q6 的"此消彼长"，这个判断还会把哪种情形误判为"收敛"？
2. 写一个 `_dimension_regressions(trace, tol)`，返回本轮相对上一轮下降超过 `tol` 的维度列表；把它接入 `run`，出现回退时以 `reason="regression"` 停止。

**Q10.** 修复 `run` 的三个状态问题：

1. 不保留历史最优：如果分数逐轮下降（8 → 6 → 4），循环以 `plateau` 结束并返回第 3 轮最差的稿子（实测 `final_mean=4.0`）；
2. budget 时 `final_scores` 与返回的稿子不对应（Q8）；
3. 在 plateau 那一轮，reviser 并没有被调用，但 trace 的 `suggestions_applied` 仍记录为建议条数；此外 reviser 原地修改了调用方传入的论文。

写出修改后的 `run`。

**Q11.** 手算题。demo 初始论文只有一个章节 `intro`（正文 `"short intro"`，11 个字符），`originality_tag="low"`。已知：

- `expand-body` 给**当前最后一个章节**追加 `" " + "x"*80`；
- 新增的 Method 章节正文 237 个字符，Related Work 章节正文 225 个字符；
- `add-figure-and-cite` 给第一个章节各加 1 个图引用和 1 个引用。

请填出第 1～5 轮的 clarity、novelty、evidence，以及每轮的建议数，并说明为什么第 3～5 轮每轮都只剩 1 条建议、clarity 每轮恰好 +0.54。

**Q12.** 确定性 reviser 提高 clarity 的方法是往正文里追加 80 个 `x`。

1. 这说明了 critic 设计中的什么问题？在真实系统（LLM critic + LLM reviser）中它会以什么形式出现？
2. 把 clarity 改成"所有正文中不同单词（≥ 2 个字母）的数量 / 5 + 3"，其余不变，再跑一次 demo。预测并解释结果。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 critic / self-refine 循环？一个可落地的 critic 循环至少需要哪些组件？为什么要用结构化的评审结果？

**Q14.**（原理深挖）critic 循环为什么可能不收敛、振荡，甚至越改越差？平台期检测、预算上限分别解决什么问题，还缺什么？

**Q15.**（工程实践）当 critic 和 reviser 都是 LLM 时，如何防止 reviser "刷分"（reward hacking）、critic 自我偏好、评分漂移？

**Q16.**（场景设计）为 54 节写作器产出的论文设计一个真实的 LLM 评审循环：要求多维度、多评审者、成本可控、可审计。

**Q17.**（追问型）LLM critic 对同一份稿子打两次分，结果可能相差 0.3～0.5 分。这对 `plateau_epsilon=0.1` 的平台期检测意味着什么？应如何改进？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Whether the rewrite addresses the criticism is unverifiable because the criticism never had structure. Five dimensions give the harness a contract... The score is a vector. The harness watches each dimension across rounds."

- A：省 token 不是重点。
- B：维度是接口，critic 可以由模型实现；讲义说模型驱动的 reviser 会把同一个 `edit` 字段当作提示词，"The contract does not change"。
- C：维度数量与收敛速度没有这种关系。

### Q2 — 答案：A

```python
        for round_ in range(1, self.max_rounds + 1):
            critique = self.critic(paper, round_)
            if self._target_met(critique):
                ... return reason="target"
            trace.append(interim)
            if self._plateau(trace):
                ... return reason="plateau"
            paper = self.reviser(paper, critique.suggestions)
        ... reason="budget"
```

讲义："Target wins over plateau wins over budget." budget 是"循环自然结束"，只有前两者都没触发时才轮到它。D 错：代码按固定顺序判断并立即返回，顺序决定了同一轮多个条件同时成立时的结果。

### Q3 — 答案：C

`_plateau` 要求 `len(trace) >= plateau_window + 1 = 3`，然后检查最近 3 条之间的 2 个差值都 ≤ ε。第 1、2 轮 trace 长度不足，第 3 轮才可能触发。实测：分数恒为 4.0 时 trace 判决为 `['continue', 'continue', 'plateau']`。这就是讲义"连续两轮持平"的实现方式：两轮"提升"需要三个点。

### Q4 — 答案：B

`avg = (92 + 237 + 225) / 3 = 184.67`，`clarity = min(10, 3 + 184.67/50) = 3 + 3.693 = 6.69`（四舍五入到 2 位）。这正是 demo 第 2 轮的 clarity。A 是第 1 轮（只有 11 个字符：`3 + 11/50 = 3.22`）；C 是第 3 轮（Related Work 又追加 81 字符后，平均 211.67）；D 需要平均长度 ≥ 350。

### Q5 — 答案：A

实测 `stuck max3: plateau 3 ['continue', 'continue', 'plateau']`。在第 3 轮（也是最后一轮），plateau 检查先于循环结束，所以永远轮不到 budget。只有当 `max_rounds < plateau_window + 1` 时（例如 `max_rounds=2`，实测得到 `budget`）恒定分数才会以 budget 结束。测试的断言写成 `in ("plateau", "budget")` 掩盖了这一点——讲义声称测试覆盖了 "budget exhaustion"，实际上 budget 分支没有任何测试覆盖。

### Q6 — 答案：D

三轮的均分都是 `(clarity + 5 + evidence + 5 + 5)/5 = 5.0`（clarity 与 evidence 之和恒为 10），实测 trace 为 `[(5.0, 'continue'), (5.0, 'continue'), (5.0, 'plateau')]`，`status="converged"`。B 是讲义声称的行为，但代码没有实现任何逐维度比较——`_target_met` 是逐维度的，`_plateau` 却只看均分。C 错：target 要求**所有**维度 ≥ 8。

### Q7 — 答案：B

实测：`converged plateau 7`，trace 中第 5～7 轮 `suggestions_applied` 都是 0、均分都是 8.862。两个原因叠加：

1. `deterministic_score` 中 novelty、methodology、related_work 的最高分都是 9.0，`target_score=9.5` 永远达不到；
2. `deterministic_critic` 内部写死了 `if scores[...] < 8.0` 才给建议，与循环的 `target_score` 没有关联，所以所有维度 ≥ 8 之后 critic 就"不说话"了。

循环把它报告为 `converged`，容易让人误以为稿子已经足够好。改进：把 target 传给 critic（或由 harness 统一给出"差距"），并在启动时检查目标是否可达。

### Q8 — 答案：C

实测：`final_scores` 的 clarity 为 6.69（第 2 轮打分），对 `result.paper` 重新打分得到 `clarity 7.23, novelty 9.0, evidence 9.0, ...`。原因：第 2 轮打完分、既没达标也没平台期，于是执行 `paper = self.reviser(...)`；之后 `for` 循环结束，进入 budget 分支，使用的仍是第 2 轮的 `critique`。trace 最后一条也写着 `suggestions_applied=3`、`verdict="budget"`——这 3 条修改从未被评估过。下游（56 节调度器）若依据 `final_scores` 决策，看到的是一份过时的成绩单。

### Q9 — 参考答案

1. **越改越差也会被判"收敛"**：条件是 `recent[i].mean - recent[i-1].mean > ε` 才算"还在进步"，任何**下降**都满足"提升 ≤ ε"。实测分数 8 → 6 → 4 时，第 3 轮以 `status="converged", reason="plateau"` 结束，`final_mean=4.0`。此外，ε 的边界对浮点误差敏感：均分 5.0 → 5.1 → 5.2 时，`5.1 − 5.0 = 0.0999…`（≤ 0.1），`5.2 − 5.1 = 0.1000…05`（> 0.1），同样是"恰好 0.1"的提升，结论却取决于舍入误差（实测该序列没有在第 3 轮停止）。
2. 参考实现（已实测：Q6 的此消彼长 critic 在第 2 轮以 `stopped / regression` 结束）：

```python
def _dimension_regressions(trace: list[LoopTrace], tol: float = 0.5) -> list[str]:
    """本轮相对上一轮，下降超过 tol 的维度。"""
    if len(trace) < 2:
        return []
    prev, cur = trace[-2].scores, trace[-1].scores
    return [d for d in DIMENSIONS if cur.get(d, 0.0) < prev.get(d, 0.0) - tol]

# run() 中，trace.append(interim) 之后、plateau 检查之前：
            regressed = _dimension_regressions(trace, self.regression_tol)
            if regressed:
                interim.verdict = "regression"
                return LoopResult(
                    status="stopped", reason="regression", rounds_used=round_,
                    final_scores=..., final_mean=..., paper=..., trace=trace,
                )
```

   `tol` 用来容忍打分噪声（LLM critic 尤其需要）。发生回退时更合理的做法不是"直接结束"，而是**回滚到上一版稿子**并把回退的维度反馈给 reviser，让它在不损害该维度的前提下重试（需要配合 Q10 的最优稿保存）。停止原因也应区分"真收敛"（plateau 且均分高）与"停滞 / 退化"。

### Q10 — 参考答案

参考实现（已实测：分数 8 → 6 → 4 时返回第 1 轮的稿子、`final_mean=8.0`；`max_rounds=2` 时 `final_scores` 与重新打分一致、调用方论文未被修改、trace 为 `[('continue', 5), ('budget', 0)]`；默认 demo 仍在第 5 轮 `target`）：

```python
import copy

    def run(self, paper: MiniPaper) -> LoopResult:
        paper = copy.deepcopy(paper)                  # (3) 不修改调用方对象
        trace: list[LoopTrace] = []
        best = None                                   # (1) (均分, 轮次, 稿子快照, 分数)
        for round_ in range(1, self.max_rounds + 1):
            critique = self.critic(paper, round_)
            mean = critique.mean()
            if best is None or mean > best[0]:
                best = (mean, round_, copy.deepcopy(paper), dict(critique.scores))
            if self._target_met(critique):
                trace.append(LoopTrace(round_, dict(critique.scores), mean, 0, "target"))
                return LoopResult("converged", "target", round_,
                                  dict(critique.scores), mean, paper, trace)
            ev = LoopTrace(round_, dict(critique.scores), mean, 0, "continue")
            trace.append(ev)
            if self._plateau(trace):
                ev.verdict = "plateau"                # (3) 未应用建议，记 0
                return LoopResult("converged", "plateau", round_,
                                  best[3], best[0], best[2], trace)
            if round_ == self.max_rounds:             # (2) 最后一轮不再修改
                break
            paper = self.reviser(paper, critique.suggestions)
            ev.suggestions_applied = len(critique.suggestions)   # 真正应用后才记录
        trace[-1].verdict = "budget"
        return LoopResult("stopped", "budget", self.max_rounds,
                          best[3], best[0], best[2], trace)
```

要点：

- (1) 每轮打分后与历史最优比较，plateau / budget 时返回**最优稿**而不是最后一稿；"最优"可以按均分，也可以按"无维度回退前提下的均分"。
- (2) 解决分数与稿子不一致的方法有两种：最后一轮不修改（如上，省一次修订）；或修改后再调用一次 critic 打分（多一次评审成本）。
- (3) `suggestions_applied` 只在 reviser 真正执行后填写；`copy.deepcopy` 让循环对输入无副作用——讲义说三方 "None of the three touches the others' state"，但原代码里 reviser 修改的正是调用方的对象。
- 别忘了同步修改测试：例如新增"budget 时 `final_scores == deterministic_score(result.paper)`"的断言。

### Q11 — 参考答案

逐轮推演（与实际运行的 trace 完全一致）：

| 轮 | 各章节正文长度 | clarity | novelty | evidence | 建议数 |
|----|---------------|---------|---------|----------|--------|
| 1 | intro 11 | 3 + 11/50 = **3.22** | low → **3.0** | 2 + 0 = **2.0** | 5（全部 < 8） |
| 2 | intro 92、method 237、related 225 | 3 + 184.67/50 = **6.69** | medium → **6.0** | 2 + 2×1 + 1.5×1 = **5.5** | 3（clarity、novelty、evidence） |
| 3 | related 306 | 3 + 211.67/50 = **7.23** | high → **9.0** | 2 + 2×2 + 1.5×2 = **9.0** | 1（clarity） |
| 4 | related 387 | 3 + 238.67/50 = **7.77** | 9.0 | 9.0 | 1 |
| 5 | related 468 | 3 + 265.67/50 = **8.31** | 9.0 | 9.0 | 0 → `target` |

methodology 与 related_work 在第 1 轮之后都是 9.0（第 1 轮的建议新增了两个带正文的章节）。

说明：

- 第 1 轮的 `expand-body` 目标是"打分时的最后一个章节"，当时只有 intro，所以 intro 变成 `11 + 81 = 92`（追加的是 1 个空格 + 80 个 x）；之后新增 Method、Related Work，最后一个章节变成 Related Work，此后每轮都扩写它。
- 第 3 轮起只有 clarity 低于 8，所以每轮只有 1 条建议；每轮 Related Work 增加 81 个字符，平均长度增加 `81/3 = 27`，clarity 增加 `27/50 = 0.54`。从 7.23 到 ≥ 8 需要再两轮，因此在第 5 轮达标。
- 均分 3.244 → 7.238 → 8.646 → 8.754 → 8.862，第 3 轮后每轮只提升 0.108，仅比 `plateau_epsilon=0.1` 略大。如果每次扩写只追加 40 个字符（clarity 每轮 +0.27，均分每轮 +0.054），实测循环会在第 5 轮以 `plateau` 结束，clarity 停在 7.25、达不到目标——"慢而稳定的进步"会被平台期规则当成停滞，ε 的取值必须与每轮可能的进步幅度相匹配。

### Q12 — 参考答案

1. **问题：代理指标被直接优化（Goodhart 定律 / reward hacking）**。clarity 用"平均正文长度"作为代理，而 reviser 恰好知道这个规则（讲义："The reviser knows how to push each score upward"），于是用毫无信息量的 `xxxx` 把分数刷上去，循环报告 `target`。真实系统中的对应形态：LLM reviser 学会迎合 LLM critic 的偏好——把文字写长、堆砌"novel""rigorous"等关键词、加更多引用（不管是否相关）、在正文中复述评审意见的措辞；critic 若与 reviser 是同一个模型，还会偏好自己的写作风格（self-preference）。分数上升，质量并没有提升。
2. 改成"不同单词数"后，追加的 `xxxx…` 只算 1 个单词甚至不算新词，clarity 几乎不再上升。实测（clarity 改为 `3 + 不同单词数/5`，其余不变）：均分 3.28 → 7.02 → 8.32 → 8.32 → 8.32，第 5 轮以 `plateau` 结束，clarity 停在 5.6，其余四个维度为 9.0。这才是"正确"的结果：reviser 已经没有能真正改善 clarity 的手段，循环如实报告停滞，而不是虚假地宣布达标。讲义："five rounds, scores flat, verdict budget. The user reads that as a critic bug, not a draft bug"——在这里，trace 揭示的是 **reviser** 的能力边界。

   更一般的防护：不要让 reviser 看到 critic 的打分规则；用多个独立的 critic（或留出一个不参与循环的 judge）做最终验收；对修改量加约束（例如 diff 必须针对建议所指章节、长度增长有上限）；定期人工抽检。

### Q13 — 参考回答要点

- **定义**：生成 → 评审 → 根据评审修改 → 再评审，直到满足停止条件。对应 Self-Refine、CRITIC、Reflexion 等方法（见 [阶段 14 · 05](../../../14-agent-engineering/05-self-refine-and-critic/docs/zh.md)）。
- **最少组件**：
  1. **评审者（critic）**：输出结构化评审——维度分数 + 指向具体位置的建议；
  2. **修订者（reviser）**：按建议做定点修改，而不是整篇重写；
  3. **harness**：管理轮次、trace、停止条件（目标、平台期、预算），三者职责互不越界；
  4. **trace**：每轮的分数向量、建议数、判决，供仪表盘和下游决策。
- **为什么要结构化**：自由文本建议无法验证是否被回应；分数向量可以逐维度比较、检测回退、画轨迹；`target_section_id` + `edit` 让修改可以定点、可审计，也便于 mock 测试。
- 加分点：讲义 "Going further" 提到的维度加权（workshop 重新颖性、journal 重方法）和"配对 critic"（一个打分、一个裁决建议）都能在同一 `Critique` 结构上叠加。

### Q14 — 参考回答要点

- **不收敛 / 振荡 / 退化的原因**：
  - 建议之间互相冲突（"写得更简洁" vs "补充更多细节"），修订在两种状态之间来回；
  - 修订带来副作用：改善一个维度、损害另一个（Q6）；
  - LLM critic 打分有噪声，同一稿子分数也会波动；
  - reviser 能力不足，建议无法落实（Q12 第 2 问）；
  - 每轮整篇重写会引入新问题，越改越偏。
- **平台期检测**：识别"不再有实质进步"，避免浪费轮次；看两轮是为了过滤单轮噪声（讲义）。
- **预算上限**：最后一道保险，保证循环一定终止，并通过 trace 暴露"critic / reviser 有问题"。
- **还缺什么**（本节代码）：
  - 逐维度回退检测（Q9）；
  - 保留并返回历史最优稿（Q10）；
  - 区分"收敛到好结果"与"停滞在差结果"（现在两者都叫 `converged`）；
  - 考虑噪声的判断（Q17）；
  - 振荡检测（例如均分在两个值之间来回，当前规则会一直跑到 budget）。

### Q15 — 参考回答要点

- **防刷分**：
  - critic 的评分细则（rubric）不直接暴露给 reviser，reviser 只看到建议；
  - 用"锚定示例"约束打分（给出 3 分、6 分、9 分的样例段落）；
  - 最终验收用一个不参与迭代的独立 judge（不同模型或不同提示），或人工抽检；
  - 对修改加约束：只能修改建议所指章节、长度增长有上限、不能删除引用 / 实验数字；
  - 与客观检查结合：引用是否真实存在（54 节 manifest + 51 节检索）、数字是否与 53 节 `Verdict` 一致。
- **防自我偏好**：critic 与 reviser 用不同模型；或多个 critic 取中位数；随机化呈现顺序。
- **防评分漂移**：固定 critic 的模型版本和提示词版本，写入 trace；定期用一组固定稿件重测 critic，确认分数稳定。
- 加分点：这与 RLHF 中的 reward hacking 同源——任何"被优化的评估器"都会被利用；把 critic 分数当作信号而不是真理。

### Q16 — 参考回答要点

- **输入**：54 节的 `manifest.json` + 正文（按章节切分）+ 53 节的 `Verdict` 和实验结果（供事实核查）。
- **评审者**：
  - 多个专项 critic：清晰度、新颖性（结合 51 节检索的相关工作）、证据（数字与实验结果对账、引用存在性）、方法论、相关工作；
  - 每个 critic 输出该维度的分数、置信度、指向章节的建议；
  - 一个"裁决者"（adjudicator）合并、去重、解决冲突建议，并排序（讲义的 paired critics）。
- **修订者**：按章节定点修改，输出 diff；修改后先过 54 节的校验门（引用、图引用、LaTeX 合法性），不过则拒绝该修改。
- **停止规则**：所有维度 ≥ 目标（可按投稿场景加权）；或平台期（考虑噪声，Q17）；或预算（轮数 + token / 金额双重上限）；出现单维度回退时回滚。
- **成本控制**：只对低于目标的维度调用专项 critic；未改动章节的评审结果缓存复用；小模型初筛、大模型终审。
- **可审计**：trace 记录每轮的分数、建议、diff、模型版本、token 成本；最终稿附带评审历史，供 56 节调度器决定是否保留这条研究分支。

### Q17 — 参考回答要点

- **影响**：噪声（±0.3～0.5）比 ε（0.1）大得多。
  - 真正停滞时，噪声会让"提升"偶尔超过 ε，平台期判断被打断，循环拖到 budget；
  - 真正在进步时，一次负向噪声也可能制造出"连续两轮提升 ≤ ε"，过早停止；
  - 单维度回退检测（Q9）同样会被噪声误触发。
- **改进**：
  - **多次采样**：每轮对同一稿子打分 k 次（或用多个 critic），取均值 / 中位数，并估计标准差；
  - **按噪声设定阈值**：ε 与回退容忍度设为噪声标准差的若干倍，或者用 53 节的思路做显著性判断（例如配对比较前后两版在多个 critic 上的分数）；
  - **平滑**：用最近几轮的移动平均或线性回归斜率判断趋势；
  - **降低噪声来源**：temperature = 0、固定提示词与 rubric、锚定示例、要求先列证据再打分；
  - **成对比较代替绝对打分**：让 critic 判断"新稿是否优于旧稿"，往往比给绝对分更稳定。
- 讲义提到"A one-round plateau is noise"，两轮窗口是对噪声的最简单防护，但它假设噪声远小于 ε；用 LLM 作为 critic 时这个假设通常不成立。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 54 论文写作器](../../54-paper-writer/docs/zh.md)：本节的 `MiniPaper / MiniSection` 是 54 节 `Paper / Section` 的简化版，真实系统中 critic 读取 54 节的 manifest。
- [阶段 19 · 53 结果评估器](../../53-result-evaluator/docs/zh.md)：显著性与噪声的思想同样适用于"critic 分数的变化是否真实"。
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../../14-agent-engineering/05-self-refine-and-critic/docs/zh.md)：critic 循环的方法论来源。
- [阶段 14 · 03 Reflexion：语言反馈驱动的 Reinforcement Learning](../../../14-agent-engineering/03-reflexion-verbal-rl/docs/zh.md)：用语言反馈迭代改进的另一种形式。
- [阶段 16 · 08 角色专业化：规划者、Critic、执行者与验证者](../../../16-multi-agent-and-swarms/08-role-specialization/docs/zh.md)：critic 作为多智能体中的一个角色。

### 本节被哪些后续内容用到
- [阶段 19 · 56 迭代调度器](../../56-iteration-scheduler/docs/zh.md)：读取本节的 trace，决定一条研究分支是否值得继续。
- [阶段 19 · 57 端到端研究演示](../../57-end-to-end-research-demo/docs/zh.md)：把 critic 循环接入完整的自动研究流程（"Wiring the critic loop"）。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../../14-agent-engineering/39-reviewer-agent/docs/zh.md)：实现者与评审者分离，与本节 critic / reviser 职责分离一致。

### 延伸关键词
`self-refine` · `CRITIC` · `LLM-as-judge` · `rubric` · `convergence criteria` · `plateau detection` · `early stopping` · `best-so-far checkpoint` · `Goodhart's law` · `reward hacking` · `self-preference bias` · `pairwise comparison` · `typing.Protocol`
