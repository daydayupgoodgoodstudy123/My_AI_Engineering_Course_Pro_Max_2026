# 测验 · AI Scientist v2：达到研讨会论文水平的自主研究（AI Scientist v2 — Workshop-Level Autonomous Research）

> **阶段 15 · 自主系统 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | AI Scientist v2 是什么 | 讲义：Sakana，Yamada et al. 2025；跑完整研究循环：假设 → 代码 → 实验 → 图表 → 论文 → 投稿 |
| 2 | v1 → v2 | v1 依赖人写的模板，LLM 只在固定脚手架里填实验；v2 用 agentic tree search + 视觉语言模型（VLM）图表评审，去掉了模板 |
| 3 | 七个阶段 | 想法生成 → 新颖性检查（文献检索）→ 实验计划 → 沙箱执行（失败反馈重试）→ VLM 改图 → 写作 + 内部审稿 → （可选）投稿 |
| 4 | 研讨会接收的含义 | 讲义：一篇 v2 生成的论文通过了 ICLR 2025 workshop 同行评审（已向程序委员会披露）；workshop 门槛低于主会、评审有噪声，一次成功是概念验证而非可靠性证明 |
| 5 | Beel et al. 独立评估 | 讲义：42% 的实验因编码错误失败；文献检索经常把已有概念标成"新颖"；VLM 打磨出的出版级图表掩盖了实验缺陷 |
| 6 | Presentation-quality gap（polish masking） | "漂亮论文、破损研究"：输出令人信服但研究不令人信服，比明显失败更危险；评估必须深入到底层主张而不是停在图表 |
| 7 | 沙箱风险 | Sakana README 警告：执行 LLM 生成的代码，可能有危险包、不受控联网、意外进程；讲义：至少 Docker，最好 seccomp / gVisor，每篇投稿离开系统前人工审查 |
| 8 | 三个系统的 evaluator 强弱 | AlphaEvolve：单测 + benchmark；DGM：SWE-bench；AI Scientist v2：同行评审（弱）。v2 的自动 evaluator 最弱、输出面最宽、离公开产物最近 |
| 9 | 运营控制承担了大部分安全工作 | 沙箱、审查、披露——当 evaluator 弱时，安全主要靠流程而不是指标 |
| 10 | 产量 vs 质量 | 重试预算提高"投稿数"，但在本节模拟器中多出来的投稿全部带有残留缺陷 |

### 核心技能（能动手做到）

- [ ] 写出 v2 循环的状态机，并为每个阶段标注已知失败模式
- [ ] 手算 `main.py` 中投稿率、各阶段放弃数、"clean"占比的期望值，并解释单个 seed 的偏差
- [ ] 识别模拟器中 `polish_masks_weakness` 参数完全不影响结果、内部审稿人与质量无关这两个建模缺陷
- [ ] 改造模拟器：让审稿人能以一定概率识别缺陷、让 polish 降低识别率，并量化产量与质量的权衡
- [ ] 为多日运行的研究 agent 设计沙箱（Docker 之外至少两项限制）和可扩展的人工审查流程
- [ ] 用 `outputs/skill-ai-scientist-sandbox-review.md` 的两道闸门审查一个研究产出

---

## 二、基础自测（选择题）

**Q1.** 讲义认为"研究"比 AlphaEvolve 的算法搜索、DGM 的 benchmark 自我修改更难形成闭环，根本原因是：

- A. 研究需要的算力更多
- B. 研究代码通常无法编译
- C. 研究结果没有机器可检验的正确性标准，论文由审稿人而不是单元测试来评判
- D. 研究领域没有现成的大语言模型

**Q2.** AI Scientist v1 与 v2 的关键区别是：

- A. v1 从人写的模板出发，LLM 在固定脚手架里填实验；v2 用 agentic tree search 和视觉语言模型图表评审循环，去掉了模板要求
- B. v1 能投稿，v2 不能
- C. v2 不再执行代码，只写论文
- D. v1 使用 VLM 改图，v2 去掉了这一步

**Q3.** 在 Beel et al. 的三个发现中，讲义认为对本阶段"最重要"的是 presentation-quality gap，理由是：

- A. 它出现的频率最高
- B. 它最容易修复
- C. 它只影响图表的美观程度，不影响结论
- D. 一个能产出令人信服的输出、却没做出令人信服研究的系统，比明显失败的系统更危险；评估必须深入到底层主张

**Q4.** 关于"v2 生成的论文被 ICLR 2025 workshop 接收"，讲义的立场是：

- A. 这证明系统已经能独立做研究，可以替代研究人员
- B. 这是一个数据点和概念验证：workshop 门槛低于主会、评审有噪声、作者向程序委员会做了披露；它不是可靠性声明
- C. 这篇论文是在没有披露的情况下被接收的
- D. 这说明 Nature 2026 的论文也完全由系统独立撰写

**Q5.** 讲义对 AI Scientist v2 的隔离要求是：

- A. 不需要隔离，因为 Sakana 已保证代码安全
- B. 只要禁止联网即可
- C. 至少 Docker，最好 seccomp / gVisor，并且每篇投稿离开系统之前都要人工审查
- D. 只需要在投稿前做一次拼写检查

**Q6.** 按 `main.py` 默认配置（`experiment_failure=0.42`、`retry_recovery=0.55`、`writeup_success=0.85`、`internal_review_accept=0.50`），单次试验最终投稿的**期望**概率最接近：

- A. 34.5%
- B. 30.5%
- C. 58.0%
- D. 50.0%

**Q7.** `run_one` 中有这样一段：

```python
    polished_hides_weakness = (
        has_experiment_flaw and random.random() < cfg.polish_masks_weakness
    )
```

关于参数 `polish_masks_weakness`，下列说法正确的是：

- A. 它越大，"polished-but-flawed" 的数量越多
- B. 它越大，投稿数越少
- C. 它只在乐观场景中生效
- D. 变量 `polished_hides_weakness` 计算出来后再也没被使用，所以这个参数对任何输出都没有影响（把它设为 0 或 1，结果逐字相同）

**Q8.** 保持其他默认参数不变，把 `retry_recovery` 从 0 提高到 0.9。根据代码的建模选择（重试恢复的实验仍带残留缺陷），下列哪个趋势正确？

- A. 投稿数增加，clean 论文数也成比例增加
- B. 投稿数增加（约 24.7% → 40.7%），clean 论文数基本不变（约 18.5%），投稿中有缺陷的比例从约 25% 升到约 55%
- C. 投稿数不变，clean 比例上升
- D. 投稿数减少，因为重试更耗时

---

## 三、动手 / 代码题

**Q9.**（手算期望）对默认配置：

1. 推导"在实验阶段放弃""在写作阶段放弃""在内部审稿阶段放弃""投稿"的期望比例。
2. 推导投稿中"clean"（无新颖性缺陷且无实验缺陷）的期望占比。
3. 实际运行（seed 42）输出：投稿 305、实验阶段放弃 215、写作阶段 111、内部审稿 369、clean 占投稿 56.7%。与期望对比，说明差异是否需要担心。

**Q10.**（讲义练习 1 与模拟器的落差）讲义练习 1 问："What fraction produce a paper with an experiment-failure flaw the figure critique polished over?"

1. 说明当前代码为什么回答不了这个问题（至少指出两点）。
2. 修改 `run_one`：让内部审稿人在看到缺陷时以概率 `catch` 拒稿，但如果 polish 掩盖了实验缺陷，则审稿人看不到该缺陷。写出关键代码。

**Q11.**（审稿人的价值）当前内部审稿人以固定 50% 概率接收，与论文质量无关。假设改成"有缺陷的论文以概率 `catch` 被拒，然后无论好坏再以 50% 概率接收"，其余参数默认。我们模拟了 20 万次：

| catch | 投稿率 | 投稿中有缺陷的比例 |
|-------|-------|-----------------|
| 0.0 | 34.3% | 46.3% |
| 0.5 | 26.5% | 29.9% |
| 0.8 | 21.7% | 14.6% |

请解释：(1) 为什么 `catch = 0` 时有缺陷比例与"审稿前"相同；(2) 这张表说明的产量—质量权衡；(3) 在真实系统中，提高 `catch` 的手段有哪些？

**Q12.**（参数含义的歧义）讲义说"42% of experiments failed from coding errors ... The retry loop caught some, not all"，代码把 0.42 当作**重试前**的失败率，再用 55% 的恢复率，最终只有 `0.42 × 0.45 = 18.9%` 被放弃。如果 42% 其实是**重试后**仍然失败的比例，应该如何重新参数化？重新计算投稿率和投稿中有缺陷的比例。

---

## 四、面试高频题

**Q13.**（基础必考）请描述 AI Scientist v2 的工作流程，并指出每个阶段已知的失败模式。

**Q14.**（原理深挖）为什么同样是"生成器 + 评估器 + 循环"，AlphaEvolve 能产出可靠成果，而 AI Scientist v2 的产出需要大量人工把关？"evaluator 弱"具体弱在哪里？

**Q15.**（工程实践）你要在公司内部运行一个可以连续几天自主做实验的研究 agent。除了 Docker 之外，你还会施加哪些限制？如何审计它"有没有越界"？

**Q16.**（场景设计）研究 agent 每天产出 50 篇论文草稿，团队只有 3 位研究员。请设计一个比"博士逐篇精读"更可扩展的人工审查流程。

**Q17.**（追问型）有人说："AI Scientist 写的论文都通过同行评审了，说明它已经能做研究了。" 你如何回应？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："a research result does not have a machine-checkable correctness criterion. A paper is judged by reviewers, not unit tests. That makes the loop harder to close." A、B、D 都不是讲义给出的理由。对比表中 v2 的 evaluator 一栏写的是 "peer review (weak)"。

### Q2 — 答案：A

讲义："AI Scientist v1 (Sakana, 2024) closed the loop by starting from human-authored templates ... AI Scientist v2 removes the template requirement by using agentic tree search with a vision-language model critique loop." B 错：讲义未说 v1 不能投稿；C 错：v2 仍执行代码（也因此需要沙箱）；D 说反了，VLM 改图是 v2 的关键新增。

### Q3 — 答案：D

讲义："A system that produces convincing outputs without doing convincing research is more dangerous, not safer, than one that fails obviously. Evaluation must reach the underlying claims, not stop at the figure." A、B 讲义没有这样说；C 正好相反——它的危害在于掩盖了结论层面的缺陷。

### Q4 — 答案：B

讲义："The acceptance is a data point; it is not a license to claim the system 'does research.' ... workshop papers are a lower bar than main-conference papers. Peer review is noisy ... One success is a proof of concept, not a reliability claim." 关于 Nature 2026 论文，讲义明确说它"was itself co-authored by human researchers; it is not 'the system wrote a Nature paper.'" 所以 A、C、D 都错。

### Q5 — 答案：C

讲义："That is why it needs stronger isolation (Docker minimum; seccomp / gVisor preferred) and a manual review of every submission before it leaves the system." A 与 README 的警告相反（"we cannot guarantee safety"）；B 只覆盖了网络，没有覆盖文件系统和进程；D 无关。

### Q6 — 答案：A

- 通过实验阶段：`1 − 0.42 × (1 − 0.55) = 1 − 0.189 = 0.811`
- 写作成功：× 0.85
- 内部审稿接收：× 0.50
- 投稿概率 = `0.811 × 0.85 × 0.5 ≈ 0.3447`

B（30.5%）是 seed 42 单次 1000 次试验的实际输出，与期望相差约 4 个点，属于采样噪声（30 个 seed 的平均值为 34.5%）。C 是通过实验阶段的比例（不含重试）`1 − 0.42`；D 只算了审稿一步。

### Q7 — 答案：D

`polished_hides_weakness` 在后面的代码中没有出现在任何 `Outcome` 字段或判断里。由于 `random.random()` 在 `has_experiment_flaw` 为真时无论参数取何值都会被调用一次，随机流也不受参数影响——实测把 `polish_masks_weakness` 设为 0.0、0.7、1.0，30 个 seed 的统计结果完全一致。所谓 "polished-but-flawed" 其实是"所有有缺陷的投稿"（`has_experiment_flaw or has_novelty_flaw`），与 polish 无关。这是本节代码最大的建模缺陷：它声称演示 polish masking，却根本没有建模 polish 的作用。

### Q8 — 答案：B

30 个 seed 平均（与解析值一致）：

| retry_recovery | 投稿率 | clean（占全部试验） | 投稿中有缺陷的比例 |
|---------------|-------|------------------|-----------------|
| 0.0 | 24.7% | 18.5% | 25% |
| 0.55 | 34.5% | 18.5% | 46% |
| 0.9 | 40.7% | 18.5% | 55% |

clean 的期望 = `(1 − 0.42) × 0.85 × 0.5 × (1 − 0.25) ≈ 18.5%`，与 `retry_recovery` 无关——只有一开始就没失败的实验才可能 clean。代码注释说明了这个建模选择："a retry-recovered experiment still carries a residual flaw"。这正是讲义 "How retry budgets trade off quality vs yield" 的含义：**重试只增加产量，不增加好论文**。A、C、D 都与数据不符。

### Q9 — 参考答案

1. 期望比例（每次试验）：

| 结局 | 公式 | 期望 | seed 42 实际（/1000） |
|------|------|------|-------------------|
| 实验阶段放弃 | `0.42 × 0.45` | 18.9% | 215 |
| 写作阶段放弃 | `0.811 × 0.15` | 12.2% | 111 |
| 内部审稿放弃 | `0.811 × 0.85 × 0.5` | 34.5% | 369 |
| 投稿 | `0.811 × 0.85 × 0.5` | 34.5% | 305 |

2. 投稿中 clean 的占比：投稿与否与缺陷无关（写作成功率、审稿接收率都不看缺陷），所以只需在"通过实验阶段"的条件下计算：
   - 无实验缺陷的条件概率 `= 0.58 / 0.811 ≈ 0.715`；
   - 再乘无新颖性缺陷 `0.75`：`0.715 × 0.75 ≈ 0.536`。
   期望 clean 占投稿的 53.6%，有缺陷的占 46.4%。

3. 1000 次试验中，比例 p ≈ 0.345 的标准差约 `√(0.345 × 0.655 / 1000) ≈ 1.5%`。投稿 30.5% 偏离约 2.6 个标准差，内部审稿放弃 369 偏离约 1.6 个标准差——单个 seed 偏差稍大，但 30 个 seed 平均投稿率 34.5%、clean 占投稿 52.8%，与期望一致。结论：**单 seed 的具体数字不应过度解读**；做"参数 A vs 参数 B"的对比时要多 seed 平均或直接用解析式。另外，乐观场景与基线共用同一随机流，改变基线参数会连带改变乐观场景的输出。

### Q10 — 参考答案

1. 回答不了的原因：
   - `polished_hides_weakness` 计算后未被使用，polish 对结局没有任何影响（Q7）；
   - "polished-but-flawed" 实际定义为"有任何缺陷的投稿"，包括只有新颖性缺陷、与图表无关的论文；
   - 内部审稿人以固定 50% 概率接收，根本不看缺陷，所以"polish 骗过审稿人"这件事在模型中不存在——无论有没有 polish，缺陷论文都同样容易通过。
2. 修改示意：

```python
@dataclass
class LoopConfig:
    ...
    reviewer_catch: float = 0.6     # 审稿人看到缺陷时拒稿的概率

def run_one(cfg):
    ...
    polished_hides_weakness = (
        has_experiment_flaw and random.random() < cfg.polish_masks_weakness
    )
    ...
    # 审稿人能"看见"的缺陷：未被 polish 掩盖的实验缺陷 + 新颖性缺陷
    visible_flaw = (has_experiment_flaw and not polished_hides_weakness) or has_novelty_flaw
    if visible_flaw and random.random() < cfg.reviewer_catch:
        return Outcome(False, has_novelty_flaw, has_experiment_flaw,
                       False, False, "internal_review")
    if random.random() > cfg.internal_review_accept:
        return Outcome(False, ..., abandoned_stage="internal_review")

    polished_ok = not has_experiment_flaw and not has_novelty_flaw
    polished_but_flawed = has_experiment_flaw and polished_hides_weakness   # 名副其实
    ...
```

   改完后 `polish_masks_weakness` 越大，带实验缺陷却通过审稿的论文越多，"polished-but-flawed"才真正回答练习 1 的问题。

### Q11 — 参考答案

1. `catch = 0` 时，审稿结果与论文质量统计独立，接收与否只是抛硬币，投稿集合是"审稿前集合"的随机子样本，所以缺陷比例不变（46.3% ≈ 解析值 46.4%）。一个与质量无关的过滤器只减少产量、不提高质量——这就是讲义 "peer review (weak)" 在模拟器里的极端形式。
2. 权衡：`catch` 从 0 提到 0.8，投稿率从 34.3% 降到 21.7%（少了约 37%），但缺陷比例从 46.3% 降到 14.6%。被拒掉的绝大部分是有缺陷的论文，clean 论文数基本不受影响。对一个"把论文送出系统"的流水线来说，这几乎总是划算的。
3. 提高 `catch` 的手段（对应 skill 文件的 Research gate）：
   - **读代码而不是读论文**：核对每个声称的实验都真实运行、数字可复现；
   - **图表溯源**：每张图都能追溯到一次有日志的实验运行，否则拒绝（hard reject）；
   - **失败如实报告**：检查失败实验是否被事后包装成"负面结果"；
   - **新颖性由领域专家核验**；
   - **自动化辅助**：重新运行实验脚本比对数字、检测可疑的数据处理（如只报最好 seed）。

### Q12 — 参考答案

若 42% 是"重试后仍失败"的最终比例，应满足 `experiment_failure × (1 − retry_recovery) = 0.42`。保持 `retry_recovery = 0.55`，则 `experiment_failure = 0.42 / 0.45 ≈ 0.933`（命令行 `--experiment-failure 0.933`）。

重新计算（解析值）：

- 通过实验阶段：`1 − 0.42 = 0.58`
- 投稿率：`0.58 × 0.85 × 0.5 ≈ 24.7%`
- 投稿中 clean：`(1 − 0.933) / 0.58 × 0.75 ≈ 8.6%`，即**约 91% 的投稿有缺陷**

与默认参数（投稿 34.5%、有缺陷 46%）相比，结论差别巨大。教训：
- 引用外部研究数字时要确认它的口径（重试前还是重试后、按实验计还是按论文计）；
- 讲义只说 "The retry loop caught some, not all"，没有给出口径，代码作者选择了较乐观的解读；
- 同理，默认的 `novelty_mislabel = 0.25` 在讲义的 Beel 段落中只描述为 "frequently"，没有给出具体数字（练习 2 称其为 Beel 的数字），使用前应查原文核实。

### Q13 — 参考回答要点

| 阶段 | 做什么 | 已知失败（讲义） |
|------|-------|----------------|
| 想法生成 | 基于主题和文献提出想法（v2 用 agentic search） | — |
| 新颖性检查 | 文献检索判断是否已发表 | 经常把已有方法标成"新颖"（研究版幻觉） |
| 实验计划 | 写实验方案和代码 | — |
| 执行 | 沙箱运行，失败进入重试 | 42% 实验因编码错误失败（错误 import、形状不匹配、未定义变量），重试只修好一部分 |
| 图表 | VLM 读图并改写 | 出版级图表掩盖实验缺陷 |
| 写作 | 起草论文，内部审稿迭代 | 内部审稿人弱 |
| 投稿 | 可选 | 必须披露 + 人工审查 |

- 加分点：指出沙箱风险（执行任意 LLM 代码），以及"v2 的 evaluator 最弱、输出面最宽、离公开产物最近"。

### Q14 — 参考回答要点

- **AlphaEvolve 的 evaluator**：快、确定、难作弊（逐位比对、真实计时、历史负载回放），能直接否定 LLM 的错误声明。
- **AI Scientist v2 的 evaluator 弱在**：
  - 主要信号是 LLM 内部审稿和人类同行评审，都是对**文本与图表**的判断，而不是对实验正确性的检验；
  - 评审有噪声、门槛不一（workshop < 主会）；
  - 可被"包装"优化：图表越漂亮、写作越流畅越容易通过，与研究是否可靠只弱相关（presentation-quality gap）；
  - 新颖性判断依赖文献检索，本身就会出错；
  - 反馈周期长、样本少，无法像 benchmark 那样大量迭代。
- **结论**：当 evaluator 弱时，讲义："The operational controls (sandbox, review, disclosure) are doing most of the safety work."
- 加分点：联系第 3 节 skill 文件的 hard reject——"Any loop where the evaluator is an LLM judge without machine-checkable ground truth"。

### Q15 — 参考回答要点

- **Docker 之外的限制**：
  - 系统调用过滤（seccomp）或用户态内核（gVisor）；
  - 网络出口白名单（只允许包镜像、数据集源），默认拒绝；禁止访问内网与云元数据地址；
  - 文件系统：只读挂载代码与数据，唯一可写目录是工作区；不挂载任何凭据；
  - 资源配额：CPU/GPU/内存/磁盘/进程数（cgroups），以及总运行时长和 token/金额预算（第 13 节）；
  - 依赖安装受控：只允许从内部镜像安装、锁定版本，防止"危险包"；
  - 定期 checkpoint 与 kill switch（第 14、16 节）。
- **审计"有没有越界"**（skill 文件 Sandbox gate）：列出所有网络调用及目标，标记未预批准的；清点工作目录之外写入的文件；确认整个运行期间隔离都有效；确认没有子进程脱离监管。任一项失败即阻止导出并上报。
- 加分点：执行日志不完整本身就是拒绝理由（hard reject "execution logs are missing or incomplete"）。

### Q16 — 参考回答要点

- **瓶颈**：专家时间。应把专家时间留给"自动检查无法判断"的部分。
- **分层流程**：
  1. **自动闸门（零人力）**：沙箱审计、日志完整性、每张图可溯源、实验可一键复现且数字一致、失败实验是否如实报告；不通过直接淘汰。
  2. **自动风险打分**：统计异常（只报单 seed、效应量离谱）、新颖性声明强度、与已知文献的相似度；按风险排序。
  3. **轻量人工初筛**：研究员每篇只看"主张 + 关键实验代码 + 主图数据"15 分钟，决定淘汰/深审。
  4. **深度审查**：只对少数候选做完整复现和领域专家的新颖性核验。
  5. **抽样复核**：随机抽取被自动闸门放行或淘汰的样本做全量审查，校准各层的漏检率。
- **配套**：默认"不发布"，发布需要具名负责人（skill 文件第 5 条）；对外发布必须披露 agent 作者身份与审查人。
- 加分点：给出 KPI——每篇平均人工分钟数、各层通过率、抽样复核发现的漏检率。

### Q17 — 参考回答要点

- **事实层面**：讲义说是"一篇"论文通过了 **workshop** 的评审，且作者做了披露；workshop 门槛低于主会，同行评审本身噪声大。
- **统计层面**：一次成功是概念验证，不是可靠性。独立评估显示 42% 的实验因编码错误失败、新颖性经常误判。如果系统一天能产出大量论文，偶尔有一篇通过评审并不说明平均质量。
- **评估层面**：同行评审主要评文本与图表，恰好是 v2 最擅长打磨的部分（presentation-quality gap）；"通过评审"与"结论可靠"之间有差距。
- **Nature 2026**：讲义特别说明那篇论文由人类研究者共同撰写，不是"系统写了一篇 Nature 论文"。
- **建设性回应**：它证明了"端到端研究循环能跑通"，下一步应关注可复现率、错误率、人工审查成本等可靠性指标。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 03 AlphaEvolve：演化式 Coding Agents](../../03-alphaevolve-evolutionary-coding/docs/zh.md)：强 evaluator 的对照组。
- [阶段 15 · 04 Darwin Godel Machine：开放式自我修改 Agents](../../04-darwin-godel-machine/docs/zh.md)：benchmark evaluator 与 reward hacking。
- [阶段 14 · 04 Tree of Thoughts 与 LATS：审慎搜索](../../../14-agent-engineering/04-tree-of-thoughts-lats/docs/zh.md)：v2 使用的 agentic tree search 的基础。
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../../14-agent-engineering/05-self-refine-and-critic/docs/zh.md)：内部审稿/VLM 评审属于"批评—修改"循环。

### 本节被哪些后续内容用到
- [阶段 15 · 06 自动化 Alignment 研究（Anthropic AAR）](../../06-automated-alignment-research/docs/zh.md)：把研究 agent 用于 alignment 研究。
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../12-durable-execution/docs/zh.md)、[阶段 15 · 13 行动预算、迭代上限与成本控制](../../13-cost-governors/docs/zh.md)：多日运行的工程控制。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../15-propose-then-commit/docs/zh.md)：投稿前的人工闸门。
- [阶段 19 · 05 综合项目 05：自主研究 Agent——AI-Scientist 级系统](../../../19-capstone-projects/05-autonomous-research-agent/docs/zh.md)：亲手搭建一个类似系统。
- [阶段 19 · 52 实验执行器](../../../19-capstone-projects/52-experiment-runner/docs/zh.md)、[阶段 19 · 55 Critic 评审循环](../../../19-capstone-projects/55-critic-loop/docs/zh.md)：研究循环中各组件的实现。

### 延伸关键词
`AI Scientist v2` · `agentic tree search` · `VLM figure critique` · `novelty check` · `presentation-quality gap` · `polish masking` · `sandbox escape` · `Docker / seccomp / gVisor` · `egress allowlist` · `reproducibility audit` · `disclosure` · `yield vs quality`
