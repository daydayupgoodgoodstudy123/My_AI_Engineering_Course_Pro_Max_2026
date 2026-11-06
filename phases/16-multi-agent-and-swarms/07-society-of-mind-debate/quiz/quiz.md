# 测验 · 心智社会与多 Agent 辩论（Society of Mind and Multi-Agent Debate）

> **阶段 16 · 多智能体与集群 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 心智社会 | Minsky 1986 年的观点：智能是一群专门化部件的社会；Du et al. 2023 把它变成了具体算法 |
| 2 | Du et al. 算法 | N 个 agent 各自作答 → 第 2..R 轮每个 agent 看到其他人第 r−1 轮的答案并更新 → R 轮后多数表决；讲义：在六项推理与事实性任务上胜过 zero-shot CoT 与 reflection |
| 3 | 两个独立旋钮 | 只增加 agent 数（1 轮多数表决）有提升但会平台化；只增加轮数（单 agent 看自己）几乎无用；两者结合才有大幅提升 |
| 4 | 为什么有效 | 暴露于分歧（必须辩护或更新）+ 降低相关误差（self-consistency 的样本来自同一模型，误差相关，会"平均成一个自信的错误"） |
| 5 | 异构辩论 | 不同底座模型（如 Llama + Claude + GPT）进一步去相关；代价是弱模型可能把共识拖向错误（"Should we be going MAD?"） |
| 6 | NLSOM | Zhuge et al. 把社会扩展到 129 个成员，随规模出现专门化与自组织 |
| 7 | 三种失效 | 谄媚级联（都听最自信的）、话题漂移（每轮重新注入问题）、算力爆炸（N×R 次调用、上下文不断变长，单题成本可超过单次 CoT 的 10 倍） |
| 8 | 上线建议 | 轮数上限 3、agent 上限 5、默认异构（至少两种底座模型）、设一个对抗位、记录每一轮 |
| 9 | 共识 ≠ 真理 | 共识度只是"多数答案所占比例"，可以自信地错 |
| 10 | 代码的教训 | 数值版辩论里误差从 1.83 增大到 2.50；原因是顺序更新 bug（后更新者读到本轮新值）与"按自信加权"；修成同步更新后一轮收敛到 42.89（误差 0.89） |

### 核心技能（能动手做到）

- [ ] 写出 Du et al. 的辩论循环，并保证每轮所有 agent 读的是**上一轮**的答案（同步更新）
- [ ] 手算一轮加权平均更新，区分同步更新与顺序更新的结果
- [ ] 同时度量"共识度"和"正确性"，并解释二者为何可以背离
- [ ] 设计 agents-only / rounds-only / both 的消融实验
- [ ] 估算 N 个 agent、R 轮辩论的调用次数与 token 成本（考虑上下文增长）
- [ ] 为一个具体任务配置辩论：agent 数、轮数、是否异构、是否设对抗位、聚合方式

---

## 二、基础自测（选择题）

**Q1.** 关于 Du et al. 2023 多 agent 辩论算法，描述正确的是：

- A. 一个 agent 反复阅读自己上一轮的推理并修改，R 轮后输出
- B. N 个 agent 各自独立采样一次，直接多数表决
- C. N 个 agent 先各自作答；之后每一轮，每个 agent 看到其他 agent 上一轮的答案并给出更新后的答案；R 轮后多数表决
- D. 一个裁判 agent 读取所有人的答案后直接给出最终答案，不需要多轮

**Q2.** 讲义转述的消融实验结论中，"只增加轮数"（单个 agent 看自己之前的推理）的效果是：

- A. 几乎没有帮助——这是 reflection 已知的弱点
- B. 与"只增加 agent 数"效果相同
- C. 是提升的主要来源
- D. 会让准确率显著下降

**Q3.** 讲义认为辩论能突破 self-consistency 饱和的核心原因之一是：

- A. 辩论使用了更大的模型
- B. 辩论减少了总的 token 消耗
- C. 辩论中每个 agent 都能访问互联网
- D. self-consistency 的样本来自同一模型、误差相关；辩论让样本不再独立同分布、让不同观点去相关，降低相关误差

**Q4.** 异构辩论（混用不同底座模型）的主要风险是：

- A. 不同模型无法读懂彼此的输出格式
- B. 能力较弱的模型参与辩论时，可能把共识拖向它的错误答案
- C. 异构辩论只能用于数学题
- D. 会让所有 agent 的答案完全一样

**Q5.** 5 个 agent、5 轮的辩论，按讲义的说法需要多少次 LLM 调用？

- A. 5 次
- B. 10 次
- C. 15 次
- D. 25 次，而且每次调用的上下文还在不断变长

**Q6.** 讲义 Ship It 对辩论给出的默认上限是：

- A. 轮数不限，agent 越多越好
- B. 轮数上限 3、agent 上限 5，并且默认异构、设一个对抗位
- C. 轮数上限 10、agent 上限 129
- D. 只用 1 轮、只用同一个模型

**Q7.** 在本节代码的 `run_debate` 中，第 1 轮里 B 调用 `revise(others)` 时，`others` 中 A 的答案是多少？

```python
for r in range(1, rounds + 1):
    updates = []
    for a in agents:
        others = [o for o in agents if o is not a]
        updates.append((a, others))
    for a, others in updates:
        a.revise(others)
```

- A. 38.00，因为 `updates` 在更新前就收集好了
- B. 42.50，因为 B 只看自己
- C. 约 42.89，因为 `others` 保存的是对象引用，A 在 B 之前已经更新了自己的 `answer`
- D. 不确定，取决于线程调度

**Q8.** 本节代码第 3 轮输出 `agree = 1.00`、`err-vs-truth = 2.48`，而第 0 轮是 `agree = 0.00`、`err = 1.83`。这说明：

- A. 共识度上升并不意味着更接近正确答案——共识可以"自信地错"
- B. 辩论一定会降低误差，这里的输出只是浮点误差
- C. `agreement_score` 的实现有 bug，应该返回 0
- D. 真值 42.0 设置错误

---

## 三、动手 / 代码题

**Q9.** 手算第 1 轮。初始：A=38.0（置信度 0.6）、B=42.5（0.8）、C=51.0（0.4）。`revise` 的规则是"自己与他人的答案按置信度加权平均，然后自己的置信度 ×1.05"。

1. 按**同步更新**（三人都读第 0 轮的值）计算 A、B、C 第 1 轮的新答案。
2. 按代码实际的**顺序更新**（A、B、C 依次更新，后更新者读到先更新者的新答案和新置信度）计算 A、B 的新答案。
3. 两种方式下第 1 轮的 `error_vs_truth` 分别是多少？

**Q10.** 修复 `run_debate`，使其符合讲义算法"each agent is shown the other agents' round r-1 answers"。写出代码，并回答：修复后结果是否还依赖 agent 在列表中的顺序？原代码在 A,B,C / C,B,A / B,A,C 三种顺序下 5 轮后的均值分别是 44.50、40.95、43.53，这说明了什么问题？

**Q11.** 讲义练习 4：用这份代码复现"agents-only / rounds-only / both"的消融。

1. rounds-only：单个 agent 反复 `revise([])`，答案会怎样变化？
2. agents-only：第 0 轮直接聚合。分别用均值和中位数，误差各是多少？
3. both：用修复后的同步辩论，误差是多少？
4. 结合结果解释：为什么在"加权平均"模型里辩论**不可能**得到比所有初始答案都更好的新答案？真实 LLM 辩论的收益来自哪里？

**Q12.** 成本估算。假设问题 100 token，每个回答 300 token；第 r 轮每个 agent 的输入 = 问题 + 前 r−1 轮**所有** agent 的全部回答（完整历史）。

1. 写出总输入 token 与总输出 token 的公式。
2. 计算单 agent 单轮（1×1）、3×3、5×5 的总 token，并算出后两者相对单次调用的倍数。
3. 讲义说"Cost per question can exceed 10× a single CoT call"，你的计算支持这个说法吗？给出两种降低成本的办法。

---

## 四、面试高频题

**Q13.**（基础必考）什么是多 agent 辩论？它和 self-consistency（多次采样投票）有什么区别？为什么能更好？

**Q14.**（原理深挖）讲义说"agent 数"和"轮数"是两个独立的旋钮，而且只有一起用才有大提升。请从"信息"和"误差相关性"的角度解释这一现象。

**Q15.**（工程实践）你要在生产中给一个高价值的事实核查功能加上多 agent 辩论。请给出配置（agent 数、轮数、模型、角色、聚合方式）、成本控制与可观测性方案。

**Q16.**（场景设计）辩论系统上线后发现：几乎每次讨论都在第 2 轮就"全票通过"，但抽检正确率并没有提高。你怎么诊断？可能是哪些失效模式？如何改？

**Q17.**（追问型）"辩论达成共识了，是不是就说明答案对了？什么任务你会明确拒绝使用辩论？"

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义的三步：初始作答；"For round r = 2..R: each agent is shown the other agents' round r-1 answers and asked 'considering these, give your updated answer.'"；"After R rounds, majority-vote the final answers." A 是 self-reflection（单 agent 多轮）；B 是 self-consistency（多 agent 一轮）；D 是裁判式变体（讲义练习 5 提到的 judge-led），不是 Du et al. 的基本算法。

### Q2 — 答案：A

讲义："Round count alone (1 agent seeing its own prior reasoning) barely helps — reflection's known weakness." B 错，讲义说只增加 agent 数"beats single-agent on most tasks, but plateaus"，两者效果不同；C 错，大提升来自两者结合；D 讲义没有这样说。本节代码中 rounds-only（`revise([])`）答案完全不变，是这一结论的极端情形。

### Q3 — 答案：D

讲义 Why it works 第 2 点："In self-consistency, all samples come from the same model, so the errors correlate — you average into a confidently wrong answer. Different models or different seeds decorrelate. Different *debated views* decorrelate further." A、B、C 都不是讲义的论点；B 恰好相反，辩论更贵。

### Q4 — 答案：B

讲义："Downside: a weak model participating in a debate can drag the consensus toward its wrong answer (see 'Should we be going MAD?', arXiv:2311.17371)." A 不是讲义提到的问题（输出都是自然语言）；C、D 都不成立——D 描述的恰恰是同质模型的"单一化"风险，异构正是为了避免它。

### Q5 — 答案：D

讲义 Compute blowup："N agents × R rounds = N·R LLM calls, each with a context that grows. A 5-agent, 5-round debate is 25 calls at growing context." 成本不仅是调用次数相乘，每次调用的输入还随轮数增长（见 Q12）。

### Q6 — 答案：B

讲义 Ship It："Cap rounds at 3"、"Cap agents at 5"、"Heterogeneous by default"、"Adversarial slot"、"Log every round"。C 中的 129 是 NLSOM 研究的规模，不是生产建议；A、D 都与讲义相悖。

### Q7 — 答案：C

`others` 是 agent 对象的列表（引用），不是答案的快照。第二个循环先执行 `A.revise`，A 的 `answer` 变成 `77.2 / 1.8 ≈ 42.889`、置信度变成 0.63；轮到 B 时，`others` 里的 A 对象已经是更新后的状态。输出第 1 轮 B = 44.49 正是用 A 的新值算出来的（见 Q9）。A 是作者的意图，但代码没有实现；D 错，代码是单线程的。

### Q8 — 答案：A

讲义 Key Terms："Consensus — Not epistemic truth — just fraction-on-majority-answer. Can be confidently wrong." 第 3 轮三个答案都在均值 ±0.1 内（44.43、44.52、44.50），共识度满分，但均值 44.48 离真值 42 更远。B 错，误差从 1.83 一路升到 2.50，不是浮点误差；C、D 都没有问题。这也说明本节代码结尾的 Takeaways（"1 round of exchange cuts the error most"）与它自己的输出矛盾。

### Q9 — 参考答案

1. **同步更新**：三人用相同的权重 (0.6, 0.8, 0.4) 和相同的第 0 轮答案，因此结果相同：
   `(0.6×38 + 0.8×42.5 + 0.4×51) / (0.6+0.8+0.4) = (22.8 + 34 + 20.4) / 1.8 = 77.2 / 1.8 ≈ 42.889`。
   A、B、C 都变为 42.889。
2. **顺序更新**：
   - A：同上，42.889；A 的置信度变 `0.6 × 1.05 = 0.63`。
   - B：自己 (0.8, 42.5)、A (0.63, 42.889)、C (0.4, 51)：`(34 + 27.020 + 20.4) / 1.83 = 81.420 / 1.83 ≈ 44.49`。
   - （C 再读 A、B 的新值，得 45.34，与输出一致。）
3. 同步：均值 42.889，误差 **0.889**；顺序（代码实际）：均值 `(42.89 + 44.49 + 45.34) / 3 ≈ 44.24`，误差 **2.24**（与输出一致）。同步更新一轮就比基线（1.83）更好，顺序更新反而更差。

### Q10 — 参考答案

```python
import copy

def run_debate_sync(agents, rounds):
    for a in agents:
        a.initial()
    for r in range(1, rounds + 1):
        snapshot = [copy.deepcopy(a) for a in agents]          # 上一轮的冻结副本
        for i, a in enumerate(agents):
            a.revise([s for j, s in enumerate(snapshot) if j != i])
        print(r, [round(a.answer, 3) for a in agents],
              round(error_vs_truth(agents), 3))
```

实测：第 1 轮起三个 agent 都是 42.889，误差 0.889，之后保持不变。

- 修复后**不再依赖**列表顺序：每个 agent 读到的都是同一份快照。
- 原代码的三种顺序得到 44.50、40.95、43.53，相差 3.5——同一组人、同样的初始答案，只因"谁先发言"不同，结论就不同。这是严重的可复现性问题，在 LLM 辩论中对应"发言顺序偏差"：如果实现上让后发言者看到先发言者本轮的新回答，先发言者会获得不成比例的影响力。讲义的算法明确规定读"第 r−1 轮"，就是为了避免这一点。

### Q11 — 参考答案

1. **rounds-only**：`revise([])` 时权重和值都只有自己，新答案 = 旧答案，永远不变。A、B、C 的误差保持 4.0、0.5、9.0（实测）。没有新信息，"反思"无从发生——对应讲义 "barely helps"。
2. **agents-only**：均值 43.83，误差 1.83；中位数 42.5，误差 0.5（实测）。数值任务中，中位数才是与"多数表决"精神一致、且抗离群值的聚合方式。
3. **both（同步辩论）**：42.889，误差 0.889。在这个玩具模型里，它比均值好，但不如中位数。
4. **为什么不可能更好**：加权平均的结果总是落在初始答案的凸包（最小值与最大值之间）内，且是它们的固定加权组合；辩论只是在"重新分配权重"，不会产生任何初始答案中没有的信息。真实 LLM 辩论的收益来自：agent 阅读他人的**推理过程**后发现自己的错误步骤（暴露于分歧）、引入新的论据、不同模型的错误不相关（去相关）——这些都是"新信息"，加权平均模型模拟不了。所以这份代码只能演示"收敛的动力学"，不能演示"辩论为什么会提高正确率"。

### Q12 — 参考答案

1. 公式（q = 100，a = 300）：
   - 总输入 = `Σ_{r=1..R} N × (q + (r−1) × N × a)`
   - 总输出 = `N × R × a`
2. 计算（已用 Python 验证）：
   - 1×1：输入 100 + 输出 300 = **400**
   - 3×3：输入 9,000 + 输出 2,700 = **11,700**，约 **29 倍**
   - 5×5：输入 77,500 + 输出 7,500 = **85,000**，约 **212 倍**
3. 在"完整历史"的假设下，3×3 已经远超 10 倍，支持讲义"can exceed 10×"的说法（实际倍数取决于回答长度与上下文策略）。降本办法：
   - 每轮只给 agent 看其他人**上一轮**的答案（Du et al. 的设定），而不是全部历史，输入随轮数不再累积；
   - 让 agent 只交换**最终答案 + 简短理由摘要**而非完整推理；
   - 早停：一旦答案（离散任务）达成一致就停止后续轮次；
   - 控制规模：讲义建议轮数 ≤ 3、agent ≤ 5；对低价值问题直接不用辩论；
   - 异构时让便宜模型承担多数席位，强模型做最终裁决。

### Q13 — 参考回答要点

- **辩论**：N 个 agent 先独立作答，之后多轮互相阅读答案（含推理）并更新，最后多数表决。
- **self-consistency**：同一模型独立采样 N 次，直接投票；样本之间没有交流。
- **为什么更好**（讲义两个机制）：
  1. 暴露于分歧：看到不同结论的推理链，必须辩护或更新，下一轮的上下文更丰富；
  2. 去相关：self-consistency 的样本来自同一模型，误差相关，增加样本很快饱和（"平均成一个自信的错误"）；辩论中的观点交互，加上不同种子/不同模型，降低了误差相关性。
- **数据**：讲义：在六项推理与事实性任务上胜过 CoT 与 Self-Reflection；agent 数与轮数两个旋钮都独立有贡献。
- **代价**：N×R 次调用且上下文增长；可能出现谄媚级联。
- 加分点：说明"共识度"和"正确率"是两个指标，评测时必须分开看。

### Q14 — 参考回答要点

- **只加 agent（1 轮投票）**：多了几份独立样本，能抵消一部分随机错误，但如果错误来自模型的系统性偏差（相关误差），投票只会把它放大成多数——所以会平台化。
- **只加轮数（单 agent）**：没有新信息源，模型在自己的推理里打转，倾向于坚持原答案或随机改动——讲义："reflection's known weakness"。本节代码的 `revise([])` 答案完全不变，就是这一点的极端体现。
- **两者结合**：多 agent 提供"不同的信息/推理路径"，多轮提供"利用这些信息的机会"。第一轮交换让每个 agent 看到别人的反例和论据，后续轮次让好的论据传播、坏的论据被淘汰。没有多样性，轮次无物可用；没有轮次，多样性只是被简单投票，无法相互纠错。
- **补充**：异构模型进一步提高多样性（去相关），但弱模型的错误也可能传播。
- 加分点：用本节代码说明"加权平均模型只能重组已有答案"，真实收益需要推理层面的新信息。

### Q15 — 参考回答要点

- **任务适配**：事实核查属于"事实性"任务，讲义指出辩论在 factuality 上有效；但对能直接检索验证的事实，先用检索 + 单 agent（本节 `outputs/skill-debate-configurator.md`：简单事实查找应拒绝辩论，改用 RAG）。
- **配置**：3 个 agent（必要时 5），3 轮以内；至少两种底座模型；一个对抗位（必须提出反方证据）；每个 agent 都有检索工具，回答必须带来源；离散结论（真/假/无法确定）用多数表决，置信度用分布表示。
- **每轮重新注入原问题**：防止话题漂移。
- **成本控制**：每问题 token/金额预算；早停（第 1 轮全体一致且证据充分则不再辩论）；只交换结论 + 理由摘要；按问题价值分级启用。
- **可观测性**：记录每一轮每个 agent 的答案、理由、引用；统计"第 1 轮一致率"、"翻转率"（有多少 agent 在辩论中改变答案、改对还是改错）、最终正确率；发现谄媚级联的信号是"大量 agent 在第 2 轮无新证据地改为跟随最自信者"。
- 加分点：把"无法确定"作为合法输出，避免为了达成共识而强行选择。

### Q16 — 参考回答要点

- **诊断数据**：查看每轮记录——第 2 轮改变答案的 agent 是否引用了新证据？是否总是改为与某个特定 agent（最自信/最先发言/最强模型）一致？第 1 轮的初始答案是否本来就高度一致（同质模型）？
- **可能的失效模式**：
  - **谄媚级联**：agent 跟随最自信者（讲义 Failure modes 第一条；本节代码中"按置信度加权 + 置信度同步上涨"就是它的玩具版）；
  - **同质化/相关误差**：所有 agent 用同一个模型、同样的 prompt，初始答案就带着同样的偏差，"全票通过"只是重复同一个错误；
  - **发言顺序偏差**：实现上后发言者看到先发言者本轮的回答（本节代码的顺序更新 bug），先发言者主导结论；
  - **评测问题**：把"共识率"当成"正确率"来看。
- **改法**：引入对抗位；混用不同底座模型；严格的同步轮次（只看上一轮）并随机化顺序；要求改变立场时必须给出新证据；聚合时加入独立的验证器或检索核对；以抽检正确率而非一致率作为上线指标。

### Q17 — 参考回答要点

- **共识不等于正确**：讲义 Key Terms 明确说共识只是"多数答案所占比例"，"Can be confidently wrong"；本节代码中共识度 1.0 时误差最大。
- **何时拒绝辩论**（本节 skill 的 hard rejects / refusal rules）：
  - 有确定性验证器的任务（编译、跑测试、精确数学）——直接运行验证器；
  - 简单事实查找——用检索增强的单 agent；
  - 纯生成类任务（写诗、创意写作）——辩论会把输出拖向平均、失去个性；
  - 没有预算——辩论成本是单 agent 的 5–15 倍（skill 原文），不设预算不应启用。
- **何时值得**：推理链长、容易出错、错误代价高、且没有廉价验证器的任务（复杂推理、事实性判断、方案评审）。
- 加分点：即使使用辩论，也应保留少数意见与证据，让最终答案可以说"多数认为 X，但有一个 agent 基于证据 Y 认为 Z"。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：辩论是"共享消息池 + 轮询 orchestrator"的一种特例。
- [阶段 11 · 02 Few-Shot, Chain-of-Thought, Tree-of-Thought](../../../11-llm-engineering/02-few-shot-cot/docs/zh.md)：CoT 是辩论要超越的基线。
- [阶段 14 · 03 Reflexion：语言反馈驱动的 Reinforcement Learning](../../../14-agent-engineering/03-reflexion-verbal-rl/docs/zh.md)：单 agent 反思，对应消融中的 "rounds-only"。
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../../14-agent-engineering/05-self-refine-and-critic/docs/zh.md)：自我改进的局限与外部反馈的作用。

### 本节被哪些后续内容用到
- [阶段 16 · 15 投票、自洽性与辩论拓扑](../../15-voting-debate-topology/docs/zh.md)：投票方式与辩论拓扑的系统比较。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：谄媚级联、同质化（monoculture）的深入讨论（讲义中提到的 "Lesson 26" 在本阶段并不存在，相关内容在这一节）。
- [阶段 16 · 08 角色专业化：规划者、Critic、执行者与验证者](../../08-role-specialization/docs/zh.md)：对抗位与 critic 角色。
- [阶段 14 · 25 多 Agent 辩论与协作](../../../14-agent-engineering/25-multi-agent-debate/docs/zh.md)：从 agent 工程角度实现辩论。
- [阶段 18 · 04 RLHF 对迎合行为的放大效应](../../../18-ethics-safety-alignment/04-sycophancy-rlhf-amplification/docs/zh.md)：谄媚行为的来源，解释为什么 agent 容易跟随"自信者"。

### 延伸关键词
`Society of Mind` · `multi-agent debate (Du et al. 2023)` · `self-consistency` · `correlated error` · `heterogeneous debate` · `sycophancy cascade` · `adversarial agent` · `NLSOM` · `majority vote / median` · `synchronous vs sequential update` · `consensus ≠ correctness` · `MAD (Multi-Agent Debate) variants`
