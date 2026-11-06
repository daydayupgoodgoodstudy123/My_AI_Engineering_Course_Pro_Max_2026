# 测验 · "递归"多出了什么：从自我精炼到 RSI（What "Recursive" Adds: From Self-Refinement to RSI）

> **阶段 20 · 递归自我改进 · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四个历史节点 | Good 1965 提出智能爆炸但无机制无速率；Schmidhuber 2003 的 Gödel machine 用证明把关自我改写、精确但不可行；Chalmers 2010 / Bostrom 2014 给出比例论题与起飞速度词汇；Chollet 2017 的怀疑论：智能是情境性的，环境是瓶颈 |
| 2 | 形状 (a) 自我精炼 | `S_{n+1} = f(S_n)`，f 固定，收敛到不动点 `S* = f(S*)`；增益缩小是因为目标逼近改进器的天花板 |
| 3 | 形状 (b) 自我训练 | 配方固定、目标开放、收益递减 `g_n = g_0/(1+n)^β`；可能没有硬天花板，但增益只降不升，循环内无法改 β |
| 4 | 形状 (c) 递归自我改进 | 改进器本身被修改，增益是状态：`g_{n+1} = r·g_n`；r < 1 收敛到 `C_0 + g_0/(1−r)`，r = 1 线性，r > 1 加速 |
| 5 | 只有 (c) 配得上"递归" | 被应用的函数是上一次应用的输出；但递归 ≠ 爆炸，r < 1 时照样收敛 |
| 6 | identity check | (a) 取 `k = 1 − r`、天花板 `C_0 + g_0/(1−r)` 与 (c, r<1) 序列逐位相同——曲线分不出是否递归，只有修改日志能 |
| 7 | 三个 2026 年梯级 | Liu 等（Alibaba）L1–L5 五条判据；Duan 等五个自主阶段（执行→策略→经验获取→环境适应→递归元改进）与 HCI；Chen 等两个轴（改进对象 × 闭环程度）与验证层级 |
| 8 | 五个可观察属性 | 自主提出/应用/验证（P/A/V）；被修改的是否是改进器（none / operators / code）；领域（single / multi / open）；是否迁移；验证器类型 |
| 9 | 10 个系统的落点 | L2：人类在环微调；L3：STaR、AlphaZero、AlphaEvolve、SEAL、ADAS；L4：Promptbreeder（边界）、DGM、Hyperagents、AIDE²；L5：无 |
| 10 | 为什么治理要按梯级定义 | RSP / PF / FSF 的阈值都是关于"谁提出、谁应用、谁验证、机制是否在范围内"的陈述；按印象分级会在分数跳变（L3 特征）时误触发，却漏掉机制修改（L4 特征） |

### 核心技能（能动手做到）

- [ ] 写出三种循环形状的递推式，并说明哪一种才是"递归"的、为什么
- [ ] 手算形状 (c) 在 r < 1 时的天花板（如 r = 0.9 → 4.0×）和 r > 1 时达到 10× 的轮数（如 r = 1.2 → 第 11 轮）
- [ ] 解释 identity check 的代数，并说出它对"从曲线判断 RSI"的否定意义
- [ ] 用五个属性给一个具名系统定 Liu 级别和 Chen 格子，并写出触发的规则
- [ ] 识别三类边界：有迁移无自指（L3）、自指但固定基准（L4）、浅自指（operators-only）
- [ ] 按 `outputs/skill-rsi-level-classifier.md` 从论文方法部分摘证据分级，并在证据不说明"谁应用修改"时拒绝分级

---

## 二、基础自测（选择题）

**Q1.** 按讲义，一个自我改进循环在什么条件下才算"递归"？

- A. 连续若干轮 benchmark 分数都在上升
- B. 被修改的对象是产生下一次改进的机制本身
- C. 整个过程不需要人类逐条审阅输出
- D. 训练数据由系统自己的输出生成

**Q2.** 形状 (c) 取 `C_0 = 1`、`g_0 = 0.3`、`r = 0.8`，极限是多少？

- A. 2.5×，与 `k = 0.2` 的固定改进器天花板相同
- B. 4.0×，因为增益每轮减半
- C. 1.3×，只有第一轮增益落地
- D. 没有极限，递归循环必然无界

**Q3.** `main.py` 的 identity check 打印 `max |delta| = 0.000000`。它对分级意味着什么？

- A. 亚临界递归就是自我精炼，可以不区分
- B. 需要噪声才能区分两种形状，所以 `--noise` 必须大于 0
- C. 能力曲线无法揭示改进器是否被修改，梯级必须从修改日志读
- D. 天花板相同时固定改进器在 30 轮内总是领先

**Q4.** 一个系统能自主给自己的训练 harness 提补丁，但每个补丁都要工程师审核合并。Liu 等的梯级把它放在哪？

- A. L4，因为被修改的是改进机制
- B. L3，因为 harness 是操作组件且循环会验证
- C. L5，因为 harness 补丁能泛化到所有任务
- D. L2，因为人类仍负责验证和应用实质性修改

**Q5.** ADAS 发现的 agent 能跨领域、跨模型迁移，分级器却把它留在 L3。原因是：

- A. 发现的 agent 能迁移，但搜索它们的元 agent 从未被修改
- B. 它的验证器是 LLM 裁判，判据规定裁判验证的系统封顶 L3
- C. 它需要人类给档案库播种，所以是 Assisted
- D. 它只在单一 benchmark 上评测，不满足有界 RSI

**Q6.** 下列关于三个 2026 年梯级的说法，哪一项**不正确**？

- A. Liu 等把自指（L4）放在泛化（L5）之前
- B. Duan 等把环境适应（阶段 4）放在递归元改进（阶段 5）之前
- C. Chen 等的验证层级是 formal → execution → judge → self，并报告自我改进强度按此递减
- D. 三个梯级度量的是同一件事，讲义的交叉表是作者们的官方对应

**Q7.** 默认运行里 r = 1.0 的确定性结果是"第 30 轮恰好 10×"。加上 `--noise 0.1`（σ = 0.1 的乘法噪声、500 次试验）后，最接近实测的是：

- A. 几乎 100% 的试验仍在第 30 轮达到 10×
- B. 约 37%–42% 的试验在 30 轮内达到 10×，中位轮次约 25–26
- C. 0% 达到，因为噪声让增益序列整体变负
- D. 约 50% 达到，因为噪声均值为 0 所以恰好一半

**Q8.** 讲义说治理阈值应"按梯级而不是按印象"定义，理由是：

- A. 梯级比 benchmark 分数更容易向公众解释，不需要维护评测集
- B. 分数跳变是 L3 特征、机制修改是 L4 特征；按梯级定义的阈值在后者发生时触发，即使分数几乎没动
- C. 按梯级定义可以让实验室自报级别，省去外部评估
- D. 梯级由论文自述决定，实验室可直接采用作者的级别

---

## 三、动手 / 代码题

**Q9.** 讲义练习 1：运行 `python3 main.py --cycles 40 --returns 0.9 --noise 0`。

1. r = 0.9 这列第 40 轮的值是多少？天花板是多少？用 `C_n = C_0 + g_0 (1 − r^n)/(1 − r)` 手算核对。
2. 同一次运行里 r = 1.0 在第 40 轮到多少？第几轮到 10×？为什么把 `--cycles` 从 30 改到 40 不改变 r = 1.2 的 10× 轮数？
3. 形状 (b) 在第 40 轮是多少？和第 30 轮（2.20×）比只多了多少？这说明 β = 1 的"没有天花板"在实践中意味着什么？

**Q10.** 讲义练习 2：运行 `python3 main.py --returns 1.0 --noise 0.1 --trials 500`（默认 seed 7），再运行 `--seed 3` 的同参数版本。

1. 两次分别有多少试验达到 10×？中位轮次是多少？
2. 噪声 `ε ~ N(0, 0.1)` 均值为 0，为什么中位数仍被拖低？写出 `g_n` 的表达式并用 `E[log(1+ε)] < 0` 解释。
3. 为什么达到 10× 的试验的中位轮次（25–26）反而**早于**无噪声的 30？

**Q11.** 讲义练习 3：把 Self-Rewarding LMs（Yuan 等 2024，同一模型既是 actor 又是 judge）加入 `SYSTEMS`。

1. 写出这一行 `SystemProfile(...)`，并说明每个属性的取值理由。
2. 规则会给它什么级别？Chen 格子是什么？
3. HEADLINE 里 "Verifiers: 9 of 10 … 0 by self-assessment alone" 会变成什么？

**Q12.** `alibaba_level` 的规则是有序的。

1. 把"机制被修改但人类应用"的分支移到"机制是否修改"之后，会让哪个系统的级别改变？为什么这是错的？
2. 写一个 `SystemProfile`，让规则给出 L5；再说明 10 个具名系统里为什么没有一个满足。
3. 给 `Mechanism.OPERATORS` 加"深度限定"（归 L3 并备注），`tests/test_main.py` 里哪条测试会失败？应该怎么改测试、怎么改讲义的表？

---

## 四、面试高频题

**Q13.**（基础必考）什么是递归自我改进？它和自我精炼（Self-Refine）、自我训练（STaR）的循环结构有什么区别？用递推式回答。

**Q14.**（原理深挖）为什么一个"递归"的循环在 r < 1 时会收敛？identity check 证明了什么、又没有证明什么？

**Q15.**（工程实践）给你一篇声称"自我改进"的论文，你如何在 20 分钟内给它定级？哪些情况你会拒绝定级？

**Q16.**（原理深挖）Liu 等的 L1–L5、Duan 等的五个阶段、Chen 等的两个轴各自在度量什么？它们在哪一点上真正有分歧？

**Q17.**（追问型）Promptbreeder 按五条判据是 L4，但很多人不认为它是 RSI。你会怎么处理这个边界？这对治理阈值的设计有什么启示？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Only (c) deserves the word 'recursive': the function being applied is the output of a previous application." A（分数上升）、C（无人在环）、D（自生成数据）在形状 (a)、(b) 里同样会出现，都不是递归的定义。

### Q2 — 答案：A

`g_n = 0.3 × 0.8^n` 是几何级数，和为 `0.3 / (1 − 0.8) = 1.5`，极限 `1 + 1.5 = 2.5`。讲义："shape (a) with k = 1 − r and C_ceil = C_0 + g_0 / (1 − r) produces the identical sequence to shape (c) with that r"。B 的 4.0× 是 r = 0.9 的天花板；D 与"递归在 r < 1 时照样收敛"相反。

### Q3 — 答案：C

讲义："The capability curve cannot tell you whether a loop is recursive; only the edit log can." A 混淆了"曲线相同"和"结构相同"；B 反了——噪声让两条曲线不同只是偶然，不能作为判据；D 与"逐位相同"矛盾。

### Q4 — 答案：D

Liu 等的 L2 定义："the system proposes changes or diagnostics; humans validate and apply"。机制被修改不足以到 L4，除非系统自己应用和验证。代码里 `alibaba_level` 先检查 `applies and validates` 再检查 `mechanism`，测试 `test_boundary_editing_mechanism_but_human_applies_is_not_L4` 就守这条边界。

### Q5 — 答案：A

讲义："ADAS transfers across domains and models but never touches its meta agent: generality without self-reference is L3." B 的"裁判封顶 L3"不是判据之一（ADAS 的验证器也是 benchmark 执行）；C 的播种不是逐轮人类应用；D 的事实错误——ADAS 跨多个领域。

### Q6 — 答案：D

讲义明说交叉表"is this lesson's reading, not the authors'; the ladders measure different things"。A、B 是讲义指出的"one real disagreement"；C 是 Chen 等的验证层级及其结论。

### Q7 — 答案：B

实测：seed 7 → 41.8%（209/500），中位 25.0；seed 3 → 37.0%（185/500），中位 26.0。原因见 Q10。A 忽略了噪声继承；C 的"整体变负"不可能，增益截断于 0；D 把"均值为 0"误当"中位数为 0"。

### Q8 — 答案：B

讲义："Classified on vibes, a threshold fires on benchmark jumps (an L3 trait) and misses a mechanism edit that gained two points (an L4 trait). Classified on attributes, it is auditable." A、C、D 都是讲义反对的做法——skill 文件明确拒绝"从论文标题或自述定级"和"仅凭新闻稿分级"。

### Q9 — 参考答案

1. 实测 r = 0.9 列第 40 轮 **3.96×**，天花板 **4.00×**。手算：`1 + 0.3 (1 − 0.9^40)/0.1 = 1 + 3 (1 − 0.0148) = 3.956`。
2. r = 1.0 第 40 轮 **13.00×**（`1 + 0.3 × 40`），第 30 轮到 10×。r = 1.2 的 10× 轮数由 `1.2^n ≥ 7` 决定，与模拟多少轮无关，仍是第 11 轮（第 40 轮已到 2204.16×）。
3. 形状 (b) 第 40 轮 **2.28×**，比第 30 轮只多 0.08×。调和级数发散但极慢：要到 10× 需要 `H_n = 30`，n 约 e^30——"没有天花板"在任何可实施的轮数内与有天花板无异。

### Q10 — 参考答案

1. seed 7：**209/500 = 41.8%**，中位 **25.0**；seed 3：**185/500 = 37.0%**，中位 **26.0**。
2. 在 (c) 里 `g_n = g_0 · r^n · Π_{i<n}(1 + ε_i)`（噪声被继承）。取对数后是和，`E[log(1+ε)] ≈ −σ²/2 = −0.005 < 0`，30 轮累计约 −0.15，所以乘积的**中位数**约 `e^{−0.15} ≈ 0.86`，多数试验的增益序列整体偏低；少数试验大幅偏高把均值拉回 1（Jensen 不等式）。能力是增益之和，中位数随之低于 10。
3. 条件中位数的选择效应：能在 30 轮内达到 10× 的恰是那些早期修改"走运"的试验（乘积 > 1），它们自然比确定性情形更早到达；没达到的试验不计入中位数。

### Q11 — 参考答案

1. 例如：

```python
SystemProfile("Self-Rewarding LM", 2024, True, True, True, Mechanism.NONE, Domain.SINGLE, False,
              Verifier.SELF, Target.POLICY, "L06"),
```

理由：它自主生成回复、自评打分、用 DPO 更新（P/A/V 都是 Y）；迭代 DPO 的配方固定，没有修改改进机制（`NONE`）；只在指令遵循 benchmark 上评测（`SINGLE`，无迁移）；验证器是**模型自己**当裁判，按 Chen 等的层级是最弱的 `SELF`（若坚持它是"LLM-as-judge"，也只能是 `JUDGE`，绝不是 `EXECUTION`）；改进对象是权重（`POLICY`）。

2. 规则：proposes ✓ → applies & validates ✓ → mechanism NONE → **L3**。Chen 格子：`policy x closed-in-task`。有人会主张裁判随模型变化构成"评估器被改进"（Chen 轴一的 evaluator），这正是讲义说的"interesting boundary"——第 06 节展开。
3. 变成 "Verifiers: 9 of 11 systems are checked by formal or execution-grade signals, 1 by self-assessment alone, 1 by humans."，梯级句变成 "4 of 11 … most populated rung is L3 … with 6"。

### Q12 — 参考答案

1. 改变的是 **Human-in-loop FT**（它 `mechanism=NONE`，不受影响）之外的假想系统——10 个具名系统里没有"机制被修改且人类应用"的案例，所以表格不变；但测试 `test_boundary_…` 里 `profile(mechanism=CODE, applies=False)` 会从 L2 变成 L4。这是错的，因为 Liu 等的 L2 定义就是"humans validate and apply"，人类在环优先于机制是否被修改。
2. 例如 `profile(mechanism=Mechanism.CODE, domain=Domain.OPEN, transfers=True)` → L5。10 个系统里 DGM、Hyperagents、AIDE² 有自指也有迁移，但领域是 `SINGLE`/`MULTI`（固定 benchmark），不是开放演化的任务域；ADAS 有迁移无自指。讲义："self-reference without an open domain is L4, so none of the ten is L5."
3. `test_boundary_editing_mechanism_but_human_applies_is_not_L4` 里 `alibaba_level(profile(mechanism=Mechanism.OPERATORS))` 断言 L4 会失败，`test_named_systems_land_on_expected_rungs` 不受影响（它没断言 Promptbreeder）。改法：把断言改成 L3 并检查备注含 "would be L4"；讲义表里 Promptbreeder 改为 "L3 (operators-only)"，HEADLINE 的 "4 of 10 reach L4" 会自动变成 3。

### Q13 — 参考回答要点

- **三条递推**：(a) `S_{n+1} = f(S_n)`，f 固定 → 收敛到不动点；(b) `C_{n+1} = C_n + g_0/(1+n)^β`，配方固定、增益按时间表递减；(c) `C_{n+1} = C_n + g_n`、`g_{n+1} = h(g_n)`，改进器本身被修改，增益是状态。
- **递归的定义**：被应用的函数是上一次应用的输出。Self-Refine 的批评者不变（a）；STaR 的"生成-过滤-微调"配方不变（b）；DGM 修改的是会修改代码的 agent 本身（c）。
- 加分点：说出 r 的三种情形（r<1 收敛、r=1 线性、r>1 加速），并指出"递归 ≠ 爆炸"。

### Q14 — 参考回答要点

- **收敛**：`g_n = g_0 r^n`，几何级数在 r < 1 时和有限，极限 `C_0 + g_0/(1−r)`。直观：每次修改改进器带来的"改进能力增量"按比例缩水，总量有界。
- **identity check 证明了**：取 `k = 1 − r`、相同天花板，固定改进器与亚临界递归的序列逐位相同（代码实测误差 4.4e-16）。因此**仅凭能力曲线不能判断循环是否递归**。
- **没有证明**：两种循环在结构上等价——它们对扰动的响应不同（(c) 的噪声被继承，(a) 的不被），对"编辑谁"的治理含义也不同。讲义的结论是"梯级要从修改日志读"，不是"两者无区别"。
- 加分点：把 r 与第 02 节的回报率、Burtsev 的 R_AI 联系起来。

### Q15 — 参考回答要点

按 `outputs/skill-rsi-level-classifier.md`：

1. 从方法部分摘五个属性的证据：谁提出、谁应用（两轮之间有没有人）、谁验证（用什么信号）、被修改的是不是改进器（none / operators / code）、领域与迁移实验。
2. 套有序规则给 Liu 级别并写出触发的那条；给 Chen 格子（改进对象 × 闭环程度）。
3. 写验证器所在层级与"验证器错了会怎样"（DGM 接受了伪造日志；自我奖励的裁判饱和）。
4. 标边界：浅自指、有迁移无自指、固定基准上的自指。
5. 一句治理后果：哪个阈值家族会关心。

**拒绝**：来源不说明两轮之间谁应用修改；只有演示视频或博客、没有方法部分；只凭新闻稿给实验室内部系统定级。**硬性否决**：从曲线、分数增量或标题里的"recursive"定级；人类在应用环节却判 L4/L5；没有域外迁移实验却判 L5；把隐藏的 LLM 裁判写成 execution。

### Q16 — 参考回答要点

- **Liu 等**：度量"系统接管了改进过程的哪几步"（提出/应用/验证）以及"机制是否在修改范围内、领域是否开放"，可从论文方法部分核验。
- **Duan 等**：度量"AI 从人类手里接过改进过程的哪一层决策"（执行→策略→经验获取→环境适应→元改进），并用 HCI 度量相对 benchmark 入场年前沿的剩余空间。
- **Chen 等**：不排梯级，而是两个轴（改进什么 × 闭环程度）加验证层级，关心的是"改进信号靠什么替代人类判断"。
- **真正的分歧**：Liu 把自指（L4）排在泛化（L5）前；Duan 把环境适应（4）排在元改进（5）前——这是关于"哪个更难"的判断。讲义的分级器选 Liu 的顺序，因为其判据可核验。
- 加分点：指出三者在一点上一致——都按"修改什么、谁应用"定义，而不是按能力曲线。

### Q17 — 参考回答要点

- **事实**：Promptbreeder 演化的是"用来演化任务提示的变异提示"，按"修改改进机制"的字面是自指；但搜索代码、LLM 权重都固定。代码把它编码为 `Mechanism.OPERATORS`，规则判 L4 并打备注 "operators-only self-reference (shallow)"。
- **处理方式**：不要悄悄改规则让结果"好看"，而是让边界**可见**——三档 `Mechanism`、备注、HEADLINE 里的 "Boundary case" 句。若要加深度限定，在规则里显式写出并同步测试和讲义表（Q12.3）。
- **治理启示**：阈值要写成可核验的属性（谁应用、机制是否可编辑、验证器类型），并对边界给出明确裁决规则；否则实验室可以靠"我们只是演化了提示"把 L4 系统说成 L3，或靠"我们的 agent 会改自己的提示"把 L3 说成 RSI。阶段 15 · 07 的暂停规范和第 21 节的 RSP / PF / FSF 阈值都依赖这种可核验性。
- 常见误区：用 benchmark 增幅来裁决边界（identity check 已否定）；或认为边界案例说明梯级无用——恰恰相反，边界是规则需要显式化的地方。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 07 递归自我改进：能力与 Alignment 的权衡](../../../15-autonomous-systems/07-recursive-self-improvement/docs/zh.md)：RSI 的初步定义、能力 vs alignment 竞赛与暂停规范。
- [阶段 15 · 04 Darwin Gödel Machine](../../../15-autonomous-systems/04-darwin-godel-machine/docs/zh.md)：本节 L4 的代表系统，以及"伪造测试日志"的验证器失效案例。
- [阶段 15 · 03 AlphaEvolve](../../../15-autonomous-systems/03-alphaevolve-evolutionary-coding/docs/zh.md)：固定演化循环 + 可执行评估器的 L3 典型。
- [阶段 15 · 02 STaR 家族](../../../15-autonomous-systems/02-star-family-reasoning/docs/zh.md)：形状 (b) 自我训练的原型。
- [阶段 14 · 01 Agent 循环](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：循环结构的基本词汇。
- [阶段 14 · 05 Self-Refine 与 Critic](../../../14-agent-engineering/05-self-refine-and-critic/docs/zh.md)：形状 (a) 自我精炼的原型。

### 本节被哪些后续内容用到
- [阶段 20 · 02 起飞的数学](../../02-intelligence-explosion-math/docs/zh.md)：形状 (c) 的 r 在实践中由什么决定（回报率、再生数、天花板）。
- [阶段 20 · 05 STaR、ReST-EM 与拒绝采样循环](../../05-self-training-generate-filter-train/docs/zh.md)：形状 (b) 的细节。
- [阶段 20 · 09 会改写自己的脚手架](../../09-self-improving-scaffolds-stop-promptbreeder-adas/docs/zh.md)：Promptbreeder 与 ADAS 的边界。
- [阶段 20 · 10 自我修改的 Agents](../../10-self-modifying-agents-dgm-hgm-hyperagents/docs/zh.md)：DGM、Hyperagents 的 L4 细节。
- [阶段 20 · 11 自动化 AI 研究](../../11-automating-ai-research-aide2/docs/zh.md)：AIDE² 的双层结构。
- 阶段 20 · 21 研发自动化的治理（见[本阶段课程列表](../../README.zh.md)）：按梯级定义的阈值。
- 阶段 20 · 23 RSI 的开放问题（见[本阶段课程列表](../../README.zh.md)）：梯级没有回答的问题。
- [阶段 15 · 08 有界自我改进设计](../../../15-autonomous-systems/08-bounded-self-improvement/docs/zh.md)：L4 系统的四个安全原语。
- [阶段 18 · 02 奖励投机与 Goodhart](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：验证器层级为什么重要。
- [阶段 18 · 18 前沿安全框架](../../../18-ethics-safety-alignment/18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：RSP / PF / FSF 的阈值原文。

### 延伸关键词
`recursive self-improvement` · `self-refinement` · `self-training` · `fixed point` · `meta-gain r` · `geometric series ceiling` · `identity check` · `Gödel machine` · `intelligence explosion` · `L1–L5 ladder` · `loop closure` · `verification hierarchy` · `Headroom-Closed Index` · `operators-only self-reference`
