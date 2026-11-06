# 测验 · Evaluation 与协调基准评测（Evaluation and Coordination Benchmarks）

> **阶段 16 · 多智能体与集群 · 第 24 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | MultiAgentBench / MARBLE（ACL 2025） | 在 research / coding / planning 任务上比较 star、chain、tree、graph 四种拓扑，用 milestone KPI 记录部分进展 |
| 2 | MARBLE 的结论 | graph 适合 research（任意两两互评），chain 适合逐步精修的 coding，star 适合快速事实汇总；graph 超过约 4 个 agent 出现协调税；cognitive planning 使里程碑达成率提高约 3% |
| 3 | COMMA | 多模态、信息不对称的协调任务；讲义："frontier models including GPT-4o struggle to beat a random baseline" |
| 4 | MedAgentBoard | 四类医疗任务对比多 agent / 单 LLM / 规则系统；多 agent 多数类别**不占优**，只在子任务清晰可分时有帮助 |
| 5 | AgentArch | 企业场景下把 tools、memory、orchestration 分层叠加，分别度量每一层的贡献 |
| 6 | SWE-bench Pro | 41 个仓库、1865 题；讲义：前沿模型 Pro 约 23%、Verified 70%+，差距被视为污染信号；带 agent 团队脚手架的报告分数更高（如 Opus 4.7 64.3%，讲义注明尚无一手来源） |
| 7 | 读 benchmark 声明的六项清单 | 哪个 benchmark 哪个 split、污染检查、基线（单 LLM / 随机 / 先前工作）、统计显著性、任务多样性、成本披露 |
| 8 | 所有 benchmark 都测不好的四件事 | 长程协调、对抗韧性、部署后漂移、按成本归一化的性能 → 需要自建内部 benchmark |
| 9 | 污染检查的做法 | 比较"见过的题"与"留出题"的准确率差 Δ；本节代码以 Δ > 0.1 为可疑，但样本小时噪声与阈值同量级 |
| 10 | 成本与随机基线 | 每个比较都要带随机基线和成本；"90% 的方案花 20 倍成本是商业决策，不是能力声明" |

### 核心技能（能动手做到）

- [ ] 说出五个 benchmark 各自测什么、核心发现是什么、什么场景下该用哪个
- [ ] 用六项清单给任意一条多 agent benchmark 声明打分，并指出最致命的缺陷
- [ ] 读懂 `run_bench` 的指标计算，解释 seen / held 准确率、milestone rate、cost/milestone 的含义与单位
- [ ] 判断一个 Δ（seen − held）是信号还是噪声：算标准误、做两比例 z 检验、估算需要的样本量
- [ ] 发现并修正代码里"硬编码结论与实际输出不符""格式化符号写死"等问题
- [ ] 设计一个包含随机基线、单 LLM 基线、成本与置信区间的内部 benchmark 报告

---

## 二、基础自测（选择题）

**Q1.** 按讲义转述的 MultiAgentBench（MARBLE）结果，**research** 场景下表现最好的协调拓扑是：

- A. Graph（支持任意两两互评）
- B. Star（中心汇总）
- C. Chain（逐步精修）
- D. Tree（层级分解）

**Q2.** 关于 SWE-bench Pro，下列描述与讲义一致的是：

- A. 500 道题，全部来自 Python 仓库，是 Verified 的子集
- B. 2294 道题，前沿模型得分与 Verified 基本持平
- C. 41 个仓库、1865 道题，覆盖业务应用、B2B 服务和开发者工具；前沿模型约 23%，而 Verified 上 70%+
- D. 只评估多模态协调任务

**Q3.** 本节代码判定"疑似污染"（打 `*`）的条件是：

- A. `accuracy_held < random_baseline`
- B. `accuracy_seen > 0.9`
- C. `abs(accuracy_seen - accuracy_held) > 0.1`
- D. `accuracy_seen - accuracy_held > 0.1`

**Q4.** COMMA benchmark 报告的"令人不适"的结果是：

- A. 多 agent 系统在所有医疗任务上都不如规则系统
- B. 包括 GPT-4o 在内的前沿模型在多模态、信息不对称的 agent 协作中难以超过随机基线
- C. graph 拓扑超过 4 个 agent 后性能翻倍
- D. benchmark 被训练数据污染，分数虚高

**Q5.** 讲义练习 1：运行代码后，留出集上 cost-per-milestone 最低的系统与留出集原始准确率最高的系统分别是：

- A. 都是 system-A
- B. system-C 与 system-A
- C. system-B 与 system-A
- D. system-B 与 system-B

**Q6.** MedAgentBoard 的结论最准确的表述是：

- A. 多 agent 在多数类别上并不优于单 LLM；任务分解只在子任务清晰可分时有帮助，协调开销超过专业化收益时反而有害
- B. 多 agent 在所有四类医疗任务上都显著优于单 LLM
- C. 规则系统在所有类别上都最好
- D. 多 agent 只在报告生成任务上占优

**Q7.** `SystemSim` 的 `variance` 参数会让每个任务的成功概率在 `base ± variance` 内均匀抖动，再做一次伯努利抽样。它对**期望准确率**的影响是：

- A. variance 越大，期望准确率越高
- B. variance 越大，期望准确率越低，降幅约等于 variance
- C. 会使准确率的期望变为 `base × (1 − variance)`
- D. 在不触发 [0, 1] 截断时几乎没有影响：均值为 0 的抖动经过伯努利抽样后期望仍是 `base`

**Q8.** 按 `outputs/skill-benchmark-reader.md`，下列哪条声明属于**直接拒绝（hard reject）**？

- A. 在 MARBLE 上跑了 200 次，报告了 95% 置信区间和每任务 token 成本
- B. "我们在 SWE-bench 上达到 72%"，没有说明是 Verified 还是 Pro
- C. 与单 LLM 基线和随机基线都做了比较，但只覆盖一个任务领域
- D. 论文是 arXiv 预印本，尚未同行评审

---

## 三、动手 / 代码题

**Q9.** 代码末尾的 Takeaways 是写死的字符串：

```python
    print("  system-A scores highest on seen tasks but has contamination signal (large delta).")
    print("  system-B is cheapest per milestone; lowest raw accuracy but transparent.")
    print("  system-C sits in the middle but without contamination flag — trustworthy.")
```

而实际运行的计分表是：

```text
system      acc(seen)  acc(held)      Δ   mile(held)   cost/t   cost/mil    vs random
system-A        0.900      0.731  0.17*        0.809 $   0.30 $    0.371 +     0.581
system-B        0.550      0.681 -0.13         0.731 $   0.12 $    0.164 +     0.531
system-C        0.550      0.550  0.00         0.650 $   0.25 $    0.385 +     0.400
```

1. 逐句核对三条 Takeaways，哪些与输出不符？
2. 为什么"写死结论"在评测代码里尤其危险？请把 Takeaways 改成根据 `run_bench` 的结果自动生成。

**Q10.** system-B 根本没有污染（`training_contamination=0.0`），却出现了 Δ = −0.13；system-A 的 Δ = +0.17。

1. 以 B 的真实准确率 0.64、seen 40 题、held 160 题估算 Δ 的标准误。−0.13 是否可能纯属噪声？
2. 用 1000 个种子重跑 `run_bench`，无污染的 B、C 被误判为污染（Δ > 0.1）的比例约是多少？A 被正确标记的比例约是多少？
3. 写一个单侧两比例 z 检验替代"Δ > 0.1"的硬阈值，并给出 A、B、C 的 z 值与 p 值。
4. 若两组各取 n 题、准确率约 0.65，大约需要多大的 n 才能可靠识别 0.1 的污染差？

**Q11.** 阅读指标计算：

```python
        "milestone_rate_held": sum(r.milestones for r in results_held) / (len(results_held) * 4),
        "cost_per_milestone_held":
            system.cost_per_task / max(0.01, sum(r.milestones for r in results_held) / len(results_held) / 4),
```

以及

```python
def random_baseline(rng: random.Random) -> float:
    return 0.15  # random routing accuracy on this task family
...
              f"+{vs_random:>10.3f}")
```

1. `cost_per_milestone_held` 的真实单位是什么？system-A 真正的"每个里程碑成本"是多少？
2. 失败时的部分里程碑 `int(4 * rate * rng.random())` 最多是几？system-A（rate = 0.8）失败时的期望部分里程碑数是多少？由此算出 A 与 C 的**期望** cost/mil，你会发现什么？
3. `random_baseline` 和打印 `vs random` 的方式各有什么问题？

**Q12.** 按 `outputs/skill-benchmark-reader.md` 的规则写一个 `grade_claim(claim: dict) -> tuple[str, list[str]]`：六项检查（split、污染、基线、统计、任务多样性、成本），0/1/2/≥3 个弱项分别对应 A/B/C/D；split 未知、无基线、N < 20 直接 F；arXiv 预印本降一级。用它给"在 SWE-bench Verified 上 500 次试验、有置信区间、12 类任务、对比了单 LLM，但 benchmark 早于训练截止、未报告成本"的声明打分。

---

## 四、面试高频题

**Q13.**（基础必考）有人说"我们的多 agent 系统比单 agent 强 15%"。你会追问哪些问题？

**Q14.**（原理深挖）什么是 benchmark 污染（contamination）？SWE-bench Verified 与 Pro 的差距说明了什么？有哪些设计 benchmark 的手段能抵抗污染？

**Q15.**（工程实践）为什么讲义强调每个比较都要带"随机基线"和"成本"？COMMA 与 MedAgentBoard 的结果对多 agent 系统的立项有什么启示？

**Q16.**（场景设计）请为公司内部的多 agent 客服系统设计一个内部 benchmark：任务集、指标、基线、统计方法、更新节奏。

**Q17.**（追问型）milestone（部分完成度）指标有什么好处？它会不会被"刷分"？怎样设计才不会误导？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："**Graph** topology best for research scenarios; supports any-to-any critique." 其余：chain 最适合逐步精修的 coding，star 最适合快速事实汇总，讲义没有说 tree 在哪个场景最优。注意讲义同时提醒 graph 在约 4 个 agent 以上会出现 coordination tax。

### Q2 — 答案：C

讲义："1865 problems across 41 repositories spanning business apps, B2B services, and developer tools… Frontier models score ~23% on Pro vs 70%+ on Verified." A、B 的题量与讲义不符，A 中"Verified 的子集"、B 中"与 Verified 基本持平"也都与讲义描述的定位（独立设计的抗污染 reality check、分数差距 40+ 个百分点）相反；D 描述的是 COMMA。

### Q3 — 答案：D

```python
        delta = r["accuracy_seen"] - r["accuracy_held"]
        contam_flag = "*" if delta > 0.1 else " "
```

只看**单向**差（见过的题更好）。C 是双向绝对值，若用它 system-B 的 −0.13 也会被标记；A、B 是无关条件。单向判断在逻辑上合理（污染只会让见过的题更好），但 B 的 −0.13 本身说明噪声已经和阈值同量级（见 Q10）。

### Q4 — 答案：B

讲义："frontier models including GPT-4o struggle to beat a **random baseline** on agent-agent collaboration in COMMA"，并解读为"多模态协调训练不足、评估不足"。A 混淆了 MedAgentBoard；C 与 MARBLE 的"协调税"相反；D 是 SWE-bench Verified 的问题。

### Q5 — 答案：C

实际输出：cost/mil 为 A 0.371、B **0.164**、C 0.385；held 准确率为 A **0.731**、B 0.681、C 0.550。所以最便宜的是 B，最准的是 A，二者不一致——这正是练习 1 想让你看到的："the ranking by 'raw accuracy' vs 'cost per milestone (held)' can differ sharply"。注意要用 **held** 准确率比较；若用 seen 准确率，A 的 0.900 含污染加成。

### Q6 — 答案：A

讲义："multi-agent does NOT dominate single-LLM on most categories… task decomposition helps when the subtasks are clearly separable (diagnosis + treatment); it hurts when coordination overhead exceeds specialization gain (report generation)." D 说反了（报告生成恰恰是受损的例子）；B、C 与讲义不符。

### Q7 — 答案：D

`success = rng.random() < base + e`，其中 `e ~ U(−v, v)`。对固定的 e，成功概率是 `base + e`；对 e 取期望得 `base + E[e] = base`。只有当 `base ± v` 超出 [0, 1] 被截断时才会改变期望。实测 system-C 在 variance = 0 / 0.1 / 0.3 时 500 个种子的平均 held 准确率为 0.5506 / 0.5494 / 0.5455，差异在随机误差范围内。也就是说这个参数名不副实：它并没有增加结果的方差（伯努利结果的方差只由 p 决定），想模拟"系统表现不稳定"需要让同一系统在不同 run 之间整体偏移，而不是逐题抖动。

### Q8 — 答案：B

skill 文件 Hard rejects 第一条："Claims citing 'SWE-bench' without specifying Verified vs Pro. The 40+ point gap makes this ambiguous reporting unacceptable." A 是合格声明；C 只是"任务多样性"一项弱点，会降级但不拒绝；D 按 Refusal rules 是"降一个字母等级"，不是拒绝。

### Q9 — 参考答案

1. 核对：
   - 第 1 句"A 在 seen 上最高且有污染信号"——**相符**（0.900，Δ 0.17*）。
   - 第 2 句"B 每里程碑最便宜"相符（0.164）；但"lowest raw accuracy"**不符**：B 的 held 准确率 0.681 排第二，seen 准确率 0.550 与 C 并列最低，最低的 held 准确率属于 C（0.550）。
   - 第 3 句"C sits in the middle… trustworthy"**不符**：C 的 held 准确率最低（0.550）、cost/mil 最高（0.385），在两个维度上都垫底；"无污染标记"只说明没检测到污染，不说明它"可信地优秀"。
2. 危险在于：参数、种子或代码一改，表格变了而结论不变，读者会把过时的结论当成数据支持的结论——这正是本节要批判的"benchmark 声明不可信"的缩影。自动生成示例：

```python
def takeaways(rows: list[dict]) -> list[str]:
    best_acc = max(rows, key=lambda r: r["accuracy_held"])
    cheapest = min(rows, key=lambda r: r["cost_per_milestone_held"])
    flagged = [r["name"] for r in rows
               if r["accuracy_seen"] - r["accuracy_held"] > 0.1]
    out = [f"highest held accuracy: {best_acc['name']} ({best_acc['accuracy_held']:.3f})",
           f"cheapest per milestone (held): {cheapest['name']} (${cheapest['cost_per_milestone_held']:.3f})",
           f"contamination flagged: {', '.join(flagged) or 'none'}"]
    if best_acc is not cheapest:
        out.append("accuracy ranking and cost ranking disagree")
    return out
```

前提是把 `format_scorecard` 里每个系统的 `r` 收集到列表 `rows` 中返回。

### Q10 — 参考答案

1. `SE(Δ) = sqrt(p(1−p)/40 + p(1−p)/160)`，p = 0.64 时约 **0.085**（已计算）。−0.13 约为 −1.5 个标准误，完全可能是噪声。反过来，如果噪声方向相反，B 就会被打上污染标记。
2. 1000 个种子实测：B 的误报率 **12.8%**，C 为 **12.7%**；A 的检出率 **94.9%**（A 的 Δ 均值 0.201、标准差 0.061）。也就是说无污染系统大约每 8 次就有 1 次被冤枉。
3. 参考实现（已运行）：

```python
import math

def two_prop_z(p1, n1, p2, n2):
    p = (p1 * n1 + p2 * n2) / (n1 + n2)                # 合并比例
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se
    pval = 0.5 * math.erfc(z / math.sqrt(2))           # 单侧 H1: seen > held
    return z, pval
```

   结果：A `z = 2.25, p = 0.012`；B `z = −1.56, p = 0.94`；C `z = 0.00, p = 0.50`。在 α = 0.05 下只有 A 显著，结论与硬阈值一致，但现在有了可解释的误报率控制。
4. 两组各 n 题时 `SE ≈ sqrt(0.65 × 0.35 × 2/n)`。按 α = 0.05（双侧）、power = 0.8，最小可检测差约为 2.8 × SE：n = 100 时约 0.19，n = 200 时约 0.13，n = 300 时约 0.11，n = 400 时约 0.094。所以要可靠识别 0.1 的差，每组大约需要 **400 题**；本代码的 seen 只有 40 题，是最大的瓶颈。

### Q11 — 参考答案

1. 分母 `Σmilestones / N / 4` 是"每题平均完成的里程碑比例"，所以结果是"每完成**一整题等价量（4 个里程碑）**的成本"，是真正每里程碑成本的 4 倍。A：0.30 / (0.809 × 4) ≈ **$0.093 / 里程碑**，而表中显示 0.371。排名不受影响，但列名 `cost/mil` 会误导读者。
2. `rate < 1` 且 `rng.random() < 1`，所以 `4 × rate × U < 4`，`int` 后最多为 3——失败的题永远拿不到满分里程碑，设计合理。A：`4 × 0.8 × U` 落在 [0, 3.2)，取整后 0、1、2 各占 1/3.2，3 占 0.2/3.2，期望 = (0 + 1 + 2)/3.2 + 3 × 0.2/3.2 = **1.125**。期望 milestone rate = 0.70 + 0.30 × 1.125/4 ≈ 0.784，期望 cost/mil = 0.30/0.784 ≈ 0.382；C 的对应值为 0.55 + 0.45 × 0.931/4 ≈ 0.655，0.25/0.655 ≈ 0.382。**A 与 C 的期望 cost/mil 几乎相同**，表中 0.371 vs 0.385 的差别纯属抽样噪声。这又是一个"单次运行的排名不可靠"的例子。
3. 问题：
   - `random_baseline` 接收 `rng` 却不用，直接返回常数 0.15。讲义说"Compares to a random baseline explicitly"，但这里没有任何随机策略被真正运行；随机基线本身也应在同一任务集上跑出来，并带上误差。`format_scorecard` 中的 `rng = random.Random(0)` 因此成了死代码。
   - `f"+{vs_random:>10.3f}"` 把加号写死在格式串外。若某系统低于随机基线，会打印成 `+    -0.050`（已验证），恰恰在最需要警示的时候给出错误符号。应改为 `f"{vs_random:>+11.3f}"`，由格式说明符 `+` 自动输出正负号。

### Q12 — 参考答案

```python
def grade_claim(claim: dict) -> tuple[str, list[str]]:
    weak = []
    if not claim.get("split"):
        weak.append("split unknown")
    if not claim.get("post_cutoff", False):
        weak.append("contamination risk")
    if not claim.get("baselines"):                   # "vs 未调优的自身"不算基线
        weak.append("no baseline")
    n = claim.get("n_trials", 0)
    if not claim.get("has_ci") or n < 50:
        weak.append("weak statistics")
    if claim.get("n_tasks", 1) <= 1:
        weak.append("single task")
    if not claim.get("cost_reported"):
        weak.append("no cost")
    if (not claim.get("split")) or (not claim.get("baselines")) or n < 20:
        grade = "F"
    else:
        grade = {0: "A", 1: "B", 2: "C"}.get(len(weak), "D")
    if claim.get("preprint") and grade != "F":
        grade = chr(min(ord(grade) + 1, ord("D")))   # 预印本降一级
    return grade, weak
```

题中声明：`split="Verified"`、`post_cutoff=False`、`baselines=["single-LLM"]`、`n_trials=500`、`has_ci=True`、`n_tasks=12`、`cost_reported=False`，运行结果 `('C', ['contamination risk', 'no cost'])`；若是预印本则为 `D`（已运行验证）。

说明：skill 文件中"F：no statistics"与"N < 50 统计支撑不足"的边界没有写死，这里把"N < 20 或无基线或 split 未知"作为一票否决、把"无 CI 或 N < 50"作为一项弱点，是一种合理解读；评分规则本身也应该写进报告，否则等级不可复现。另外，讲义特别强调 Verified 已被部分污染，所以即使 split 已知，Verified 上的声明也几乎必然吃到"contamination risk"这一项。

### Q13 — 参考回答要点

按讲义六项清单追问：

- **哪个 benchmark、哪个 split**：是公开 benchmark 还是自建？SWE-bench 是 Verified 还是 Pro？
- **污染**：benchmark 发布时间是否晚于所用模型的训练截止？
- **基线**：15% 是相对谁？单 LLM（同模型、同 token 预算）、随机基线、先前的多 agent 工作。"相对未调优的同一系统"只是消融，不是基线。
- **统计**：跑了多少次、多少题？置信区间或标准误？前沿模型方差大，单次运行会误导。
- **任务多样性**：一个任务还是多个领域？
- **成本**：每任务 token、墙钟时间、美元成本。多 agent 往往消耗数倍 token，"15% 提升 + 5 倍成本"是商业决策。
- 加分点：追问"同 token 预算下的单 agent（例如多次采样 + 自洽投票）"能否达到同样效果——很多多 agent 增益来自"花了更多推理计算"而非"协调"；引用 MedAgentBoard"多 agent 多数类别不占优"的结论。

### Q14 — 参考回答要点

- **定义**：benchmark 发布后，题目、答案或讨论进入了后续模型的训练语料，模型"背过答案"，分数虚高，不再反映泛化能力。讲义："SWE-bench Verified became partially contaminated in training corpora by mid-2025."
- **Verified vs Pro**：讲义给出前沿模型 Pro 约 23% vs Verified 70%+，并把差距称为污染信号。严谨地说，这个差距同时包含"Pro 题目更难、仓库更多样"的因素，不能全部归于污染；但"Verified 上的高分不再是能力证据"这一结论成立。
- **抗污染手段**：
  - 使用训练截止后才产生的新题（时间切分），并持续滚动更新；
  - 保留私有 held-out 集，只通过评测服务提交、不公开答案；
  - 引入许可限制或非公开仓库的代码，降低被爬取进语料的概率；
  - 在评测时做"见过 vs 未见过"对照（本节代码的 seen/held Δ）。
- 加分点：本节代码演示了污染检测的统计陷阱——40 题的 seen 集误报率约 13%（见 Q10）。

### Q15 — 参考回答要点

- **随机基线**：确认任务本身是否"可解"、指标是否有区分度。讲义："If you cannot beat random by a large margin on a coordination task, the task may be ill-posed." COMMA 中前沿模型都难以超过随机，说明当前多模态协调能力不足，宣称"有效"之前必须先过这道线。
- **成本**：多 agent 天然消耗更多 token 和时间，准确率提升必须对照成本；讲义列出的"所有 benchmark 都测不好"的一项就是按成本归一化的性能。
- **立项启示**：
  - MedAgentBoard：多 agent 不一定胜过单 LLM，先建立强单 LLM 基线，只有当子任务清晰可分时再拆分；
  - COMMA：多模态/信息不对称协调是薄弱区，相关立项要先做可行性测量；
  - AgentArch：逐层（tools → memory → orchestration）测增益，不为测不出价值的层买单；
  - MARBLE：拓扑要匹配任务，graph 超过约 4 个 agent 会出现协调税。
- 常见误区：只报准确率不报成本；拿"未调优的自己"当基线。

### Q16 — 参考回答要点

- **任务集**：从生产日志按意图分层采样（退款、物流、账号、投诉、多轮升级等），覆盖长尾；人工标注标准答案与里程碑（识别意图 → 查订单 → 给出政策 → 完成操作）；单独保留一份从不用于调参的 held-out 集。
- **指标**：端到端解决率、里程碑达成率、违规率（越权承诺、泄露隐私）、转人工率、每会话 token 成本、P95 延迟；对开放回答用 rubric + 抽样人工复核。
- **基线**：单 LLM（同模型、同 token 预算）、现有规则/FAQ 系统、随机或"总是转人工"基线、上一版本系统。
- **统计**：每个配置跑多次，报告均值与 95% 置信区间；版本对比用配对检验（同一题上比较）；预先算样本量（参考 Q10，0.1 的差需要每组数百题）。
- **更新节奏**：讲义建议每季度重建 benchmark，跟随生产分布漂移；每次版本发布做回归；防止"对内部 benchmark 过拟合"——保留一部分从不公开给开发者的隐藏题。
- 加分点：把 benchmark 接入 CI，失败预算超标阻止发布；与阶段 17 的 A/B 测试结合，用线上指标验证离线结论。

### Q17 — 参考回答要点

- **好处**：长程任务的最终成功率往往很低、区分度差；里程碑给出"部分功劳"，能区分"差一点成功"和"完全没开始"，并定位系统卡在哪一步（MARBLE 正是用 milestone KPI 做拓扑比较）。
- **刷分风险**：系统可能学会快速完成容易的早期里程碑而不追求最终结果；里程碑定义若与最终价值不一致，会出现 Goodhart 效应。本节代码还展示了一个计量问题：`cost/mil` 实际是"每 4 个里程碑的成本"，单位标注不清同样会误导。
- **设计建议**：始终把最终成功率与里程碑率并列报告；里程碑应可客观验证（例如"测试通过"而不是"模型说已完成"）；对里程碑加权，越接近最终目标权重越高；在 held-out 集上计算；同时报告每个里程碑的通过率分布，而不仅仅是平均值。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 15 投票、自洽性与辩论拓扑](../../15-voting-debate-topology/docs/zh.md)：star / chain / tree / graph 等拓扑的来源，MARBLE 比较的正是这些结构。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：评测之前先知道系统会怎样失败。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../../14-agent-engineering/19-benchmarks-swebench-gaia/docs/zh.md)：单 agent 视角下的 SWE-bench 与其他 benchmark。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：评测集、指标与 LLM-as-judge 的基础。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：把评测作为开发循环的一部分。

### 本节被哪些后续内容用到
- [阶段 16 · 25 案例研究与 2026 年前沿进展](../../25-case-studies-2026-sota/docs/zh.md)：用本节清单去读真实系统的 benchmark 声明。
- [阶段 17 · 21 对 LLM Features 进行 A/B 测试](../../../17-infrastructure-and-production/21-ab-testing-llm-features/docs/zh.md)：离线 benchmark 之后的线上验证与显著性检验。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../../17-infrastructure-and-production/27-finops-llms/docs/zh.md)：把"成本披露"落实为单位经济学。
- [阶段 14 · 20 基准评测：WebArena 与 OSWorld](../../../14-agent-engineering/20-benchmarks-webarena-osworld/docs/zh.md)：其他长程 agent benchmark 的设计。

### 延伸关键词
`MultiAgentBench / MARBLE` · `milestone KPI` · `COMMA` · `MedAgentBoard` · `AgentArch` · `SWE-bench Pro / Verified` · `contamination` · `held-out split` · `random baseline` · `two-proportion z-test` · `confidence interval` · `cost-normalized accuracy` · `WMAC`
