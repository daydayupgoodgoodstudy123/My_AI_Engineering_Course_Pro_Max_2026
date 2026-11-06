# 测验 · 综合项目 17：个人 AI 导师——自适应、多模态与记忆（Capstone 17 — Personal AI Tutor (Adaptive, Multimodal, with Memory)）

> **阶段 19 · 综合项目 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四大组件 | tutor policy（苏格拉底式教学策略）、learner model（学习者模型）、curriculum graph（课程图）、memory（情景 + 语义记忆），外加多模态输入与安全层 |
| 2 | Socratic policy | 学习者要答案时先问引导性问题；答对就推进；卡住就给 scaffold（脚手架式提示）。"answer-dump（直接倒答案）"是交付物的硬性否决项 |
| 3 | Bayesian knowledge tracing（BKT） | 四参数：`p_init`（先验掌握）、`p_learn`（每次练习学会的概率）、`p_slip`（会了却答错）、`p_guess`（不会却猜对）；每次作答后先做贝叶斯后验，再做"学习转移" |
| 4 | BKT 更新公式 | 答对：`P(L|对) = m(1−s) / [m(1−s) + (1−m)g]`；答错：`P(L|错) = m·s / [m·s + (1−m)(1−g)]`；之后 `m' = post + (1−post)·p_learn` |
| 5 | 课程图（DAG） | 概念 + 先修边；选下一个概念时要求"自己未掌握、先修全部已掌握"。讲义用 Neo4j 存 50–150 个节点，代码用 11 个节点的 Python 列表 |
| 6 | 间隔重复 | SM-2 或 FSRS 安排复习时间；讲义："FSRS … 2024 spaced-repetition scheduler, better than SM-2"。本节 Python 代码**没有**实现复习与遗忘 |
| 7 | 记忆分层 | episodic（情景）记录每一次交互；mistakes/preferences 被压缩提升到 semantic（语义）记忆；按 learner ID 隔离 |
| 8 | 安全与隐私 | Llama Guard 4 + 适龄过滤器（自残、成人内容、暴力）；COPPA（美国针对 13 岁以下儿童的数据法）意识的保留策略：1 年自动删除、家长可访问/删除 |
| 9 | 效果研究（efficacy study） | 10 名学习者、两周、前测/后测，必须与**非自适应基线**（线性授课）对比，报告 learning gain delta 与置信区间 |
| 10 | 模拟研究的局限 | 代码用"共同随机数"配对两组，但评价指标是模型自己的掌握估计，且模拟学生的答对概率依赖该估计——结论高度依赖设定（20 轮时自适应反而落后） |

### 核心技能（能动手做到）

- [ ] 手算任意掌握度在答对/答错后的 BKT 更新值，并说清 slip 与 guess 的区别
- [ ] 读懂 `next_concept` 的"先修已满足 + 自身未掌握"规则，并改写成按优先级（如最低掌握度）选择
- [ ] 指出 `socratic_policy` 与 `last_action` 机制中"动作作用对象错位"等实现问题
- [ ] 设计一个公平的自适应 vs 基线对照实验（配对、同一学习者模型、只改变一个因素）
- [ ] 为 K-12 场景列出安全与隐私的最低要求（双向 guardrail、ID 作用域、保留与删除）
- [ ] 解释为什么"模型自评的掌握度之和"不是可靠的学习效果指标，并给出替代指标

---

## 二、基础自测（选择题）

**Q1.** 按本节 `BKTParams` 默认值（`p_learn=0.12, p_slip=0.10, p_guess=0.15`），某概念当前掌握度 0.2，学习者**答对**一次，`bkt_update` 返回值约为：

- A. 0.600
- B. 0.320
- C. 0.648
- D. 0.927

**Q2.** 关于 BKT 中 slip 与 guess 的含义，正确的是：

- A. slip：已掌握却答错的概率；guess：未掌握却答对的概率
- B. slip：未掌握却答对的概率；guess：已掌握却答错的概率
- C. slip 与 guess 都表示"答对的概率"，只是适用的题型不同
- D. slip 是学习率，guess 是先验掌握度

**Q3.** 本节 `next_concept(state, cmap)` 选择下一个概念的规则是：

- A. 在所有未掌握概念中选掌握度最低的
- B. 随机选择一个先修已满足的概念
- C. 选择先修数量最多（最难）的未掌握概念
- D. 按 `ALGEBRA` 列表顺序，返回第一个"自身掌握度 < 0.85 且所有先修 ≥ 0.85"的概念；都掌握则返回 `None`

**Q4.** 讲义描述的 Socratic tutor policy，在学习者直接要答案时会：

- A. 立即给出完整答案，然后进入下一个概念
- B. 提出一个引导性问题，把学习者一步步引向答案
- C. 拒绝回答并结束会话
- D. 切换到一个没有先修关系的新概念

**Q5.** 关于讲义中的 episodic 与 semantic 记忆，说法正确的是：

- A. episodic 记录每一次交互；反复出现的错误和偏好被压缩后"提升"到 semantic 记忆
- B. episodic 只存 embedding，semantic 只存原始音频
- C. 两者内容完全相同，只是存在不同数据库里做冗余
- D. episodic 给家长看，semantic 给学习者看

**Q6.** 讲义为 K-12 导师设定的记忆保留策略是：

- A. 永久保存，以便长期个性化
- B. 只受 GDPR 约束，与 COPPA 无关
- C. 保留时长等于模型上下文窗口能容纳的轮数
- D. COPPA 意识：1 年后自动删除，且家长可以访问和删除

**Q7.** `main()` 中两组模拟使用 `r_base.setstate(r_adapt.getstate())`，这样做的目的最准确的描述是：

- A. 让两组学习者的能力值 `ability` 不同，增加多样性
- B. 加快模拟速度
- C. 让两组在第 t 轮消耗同一个均匀随机数（共同随机数），差异主要来自策略而不是种子噪声
- D. 保证自适应组一定优于基线组

**Q8.** 某概念从初始掌握度 0.2 开始，按默认参数，学习者**最少连续答对几次**，`next_concept` 就不再选它（掌握阈值 0.85）？（忽略 `celebrate_and_advance` 的 +0.02）

- A. 1 次
- B. 2 次
- C. 3 次
- D. 5 次

---

## 三、动手 / 代码题

**Q9.** 阅读 `run_adaptive` 中处理"上一轮教学动作"的代码：

```python
    last_action: str | None = None
    for _ in range(n_turns):
        concept = next_concept(state, cmap)
        if concept is None:
            break
        difficulty = 0.3 + 0.1 * len(cmap[concept].prereqs)
        if last_action == "scaffold_from_prereq":
            difficulty -= 0.15
        elif last_action == "hint":
            difficulty -= 0.08
        elif last_action == "celebrate_and_advance":
            state.mastery[concept] = min(1.0, state.mastery[concept] + 0.02)
        ek = inherent_ability + state.mastery[concept] * 1.5
        correct = simulate_answer(ek, difficulty, rng)
        last_action = socratic_policy(state, concept, correct)
        state.history.append((concept, correct))
        state.mastery[concept] = bkt_update(state.mastery[concept], correct, p)
```

结合 `socratic_policy`（`correct and m > 0.8` → celebrate；`correct` → reinforce；`m > 0.5` → hint；否则 scaffold）回答：

1. `celebrate_and_advance` 的 +0.02 加到了哪个概念上？这合理吗？
2. 在掌握阈值 0.85 下，`celebrate_and_advance` 只在什么条件下会出现？为什么它几乎不发生？
3. `scaffold_from_prereq` 名字说"从先修概念开始搭脚手架"，代码实际做了什么？
4. 直接改 `state.mastery` 有什么问题？

**Q10.** 讲义"Use It"示例写道：学习者答对后 `[mastery] addition-subtraction-equality: 0.62 -> 0.77`。

1. 用本节默认参数手算 0.62 答对后的 BKT 结果。
2. 同样从 0.62 出发答错，结果是多少？
3. 讲义示例与代码数值不一致，说明了什么？

**Q11.** 运行代码得到 `adaptive mean=9.81, baseline mean=8.45, delta=+1.36`。但把每个学习者拆开看（能力值、自适应、基线、自适应实际轮数）：

```text
learner 2  ability=0.485  adaptive=10.09  baseline=10.84  adaptive_turns=32
learner 7  ability=0.847  adaptive=10.09  baseline=10.76  adaptive_turns=31
```

并且把 `n_turns` 改成 20 时，`adaptive=5.69 < baseline=6.04`。

1. 为什么高能力学习者的自适应组反而输给了轮转基线？（提示：看 `if concept is None: break`。）
2. 为什么轮数少时自适应会落后？
3. 这个"效果研究"的评价指标 `mastery_sum` 有什么根本问题？
4. 提出至少两项改进，让这个模拟实验更可信。

**Q12.** 改写选择器：实现 `next_concept_v2(state, cmap, threshold=0.85)`——在"先修已满足且未掌握"的候选中选**掌握度最低**的；若全部掌握，则进入复习模式，返回全课程中掌握度最低的概念（不再返回 `None`）。说明这样修改后 60 轮研究的结果会如何变化。

---

## 四、面试高频题

**Q13.**（基础必考）解释 Bayesian knowledge tracing 的四个参数和一次更新的两个步骤。为什么答错一次后掌握度不会降到 0？

**Q14.**（原理深挖）BKT、IRT（项目反应理论）、FSRS 分别在建模什么？本节 `simulate_answer` 用的 `sigmoid(knowledge − difficulty)` 属于哪一类模型？三者在一个导师系统里如何分工？

**Q15.**（工程实践）讲义要求"10 名学习者、两周、前测/后测、与非自适应基线对比"。如果你负责这个效果研究，你会如何设计与报告，才能让"自适应更有效"的结论站得住？

**Q16.**（场景设计）为面向 13 岁以下学生的数学导师设计安全与隐私方案：内容安全、记忆隔离、数据保留、家长权限，以及讲义练习 5 提到的"用语音片段重新注入去读取别人数据"的攻击。

**Q17.**（追问型）LLM 天然倾向于"有问必答"。你如何保证导师真正做到 Socratic（不直接倒答案），又不至于让卡住的学生越来越挫败？如何评估"Socratic fidelity"？

---

## 五、参考答案与解析

### Q1 — 答案：C

答对时：`num = 0.2 × (1 − 0.10) = 0.18`，`denom = 0.18 + 0.8 × 0.15 = 0.30`，后验 `0.18 / 0.30 = 0.600`；再做学习转移：`0.6 + 0.4 × 0.12 = 0.648`（已用代码实际验证）。

- A（0.600）是只做了贝叶斯后验、漏掉了 `p_learn` 转移的结果。
- B（0.320）是把 `p_learn` 直接加到先验上 `0.2 + 0.12` 的错误算法。
- D（0.927）是**连续答对两次**后的值。

### Q2 — 答案：A

slip（失误）：已经掌握却答错；guess（猜中）：没掌握却答对。注意本节代码注释写反了一半：

```python
    p_slip: float = 0.10    # correct despite not knowing
    p_guess: float = 0.15   # correct by guessing despite not knowing
```

`p_slip` 的注释与 `p_guess` 的含义重复了，应为 "incorrect despite knowing"。但公式部分是对的：答对时用 `(1 − p_slip)` 乘掌握者、`p_guess` 乘未掌握者。B 把两者对调；C、D 混淆了参数。

### Q3 — 答案：D

```python
    for c in cmap.values():
        if state.mastery[c.name] >= master_threshold:
            continue
        if all(state.mastery[pr] >= master_threshold for pr in c.prereqs):
            return c.name
    return None
```

字典保持插入顺序，而 `ALGEBRA` 恰好是按拓扑序写的，所以这是"拓扑序上的第一个可学概念"。它**不**比较掌握度高低（A 错），没有随机性（B 错），也不考虑难度（C 错）。讲义说 `select_concept` 应"picking the highest-priority concept"，代码用"列表顺序"代替了优先级。

### Q4 — 答案：B

讲义："when the learner asks for the answer, the policy asks a leading question"。交付物 `outputs/skill-ai-tutor.md` 把"answer-dump instead of asking the next question"列为 hard reject。A 正是被禁止的行为；C、D 都不是讲义描述的策略。

### Q5 — 答案：A

讲义："Every interaction writes to an episodic store. Mistakes and preferences promote to semantic memory." B 把存储内容说反且不符合讲义；C 错在二者粒度不同（原始日志 vs 压缩后的模式）；D 与讲义无关——讲义中家长权限针对的是访问与删除，而非"给谁看哪种记忆"。

### Q6 — 答案：D

讲义："COPPA-aware retention policy: auto-delete after 1 year, parent-accessible."，并在 Key Terms 中解释 COPPA 是"US law restricting data collection from children under 13"。A 违反 COPPA 思路；B 错，K-12 面向美国儿童时 COPPA 是核心约束（讲义架构图写的是"COPPA / GDPR aware"，两者都要考虑）；C 混淆了模型上下文与数据保留。

### Q7 — 答案：C

`r_base` 复制了 `r_adapt` 的内部状态，两条流产生完全相同的随机数序列；两组每轮都只调用一次 `rng.random()`，因此第 t 轮的"运气"相同，这是方差缩减中的 common random numbers（共同随机数）。

- A 错：`ability` 来自另一个 `rng = random.Random(29)`，两组用的是**同一个** `ability`。
- B 错：与速度无关。
- D 错：配对只降低噪声，不保证结果方向。实际运行中学习者 2 和 7 的基线组就更高（见 Q11）。

### Q8 — 答案：B

实际计算：0.2 →（对）0.648 →（对）0.9269 ≥ 0.85。所以两次连续答对就"毕业"。这也解释了运行结果中大量概念的最终掌握度恰好是 `0.93`。A 错，一次只到 0.648；C、D 高估了。这个数字说明默认参数下 BKT"毕业"非常快——真实系统常要求更多次正确作答，或者加入遗忘与复习。

### Q9 — 参考答案

1. **作用对象错位**：`last_action` 是对**上一轮概念**的决定，但 +0.02 加在**本轮** `next_concept` 选出的概念上。上一轮概念若因此达到 0.85，本轮选出的就是一个**新**概念——等于"为 A 概念庆祝，给 B 概念加分"。`hint`/`scaffold` 的难度降低也同理：上一轮概念若还没掌握，本轮通常仍是同一个概念，所以这两者大体对得上；但 celebrate 几乎总是错位。
2. celebrate 需要 `correct and m > 0.8`，其中 `m` 是**更新前**的掌握度；而 `m ≥ 0.85` 的概念已经不会被选中，所以只有 `0.8 < m < 0.85` 时答对才会触发。按 Q8 的计算，掌握度通常从 0.648 直接跳到 0.927，很少落在这个 0.05 宽的窗口里。
3. `scaffold_from_prereq` 只是让下一轮难度 −0.15，并**没有**回到任何先修概念出题，名字与行为不符。一个更贴近讲义的实现是：答错且掌握度低时，选择该概念掌握度最低的先修概念出一道复习题，再回到原概念。
4. 直接改 `state.mastery` 绕过了 BKT：学习者模型应该只根据**观测到的作答**更新，"庆祝"不是证据。这样做会污染掌握度估计，也让 adaptive 组在比较中获得额外加分。正确做法是把教学动作建模为对**模拟学生真实能力**或**答题难度**的影响，而不是改模型的信念。

### Q10 — 参考答案

1. 答对：`num = 0.62 × 0.9 = 0.558`，`denom = 0.558 + 0.38 × 0.15 = 0.615`，后验 ≈ 0.9073；转移后 `0.9073 + 0.0927 × 0.12 ≈ 0.918`（代码实际输出 0.9184）。
2. 答错：`num = 0.62 × 0.1 = 0.062`，`denom = 0.062 + 0.38 × 0.85 = 0.385`，后验 ≈ 0.161；转移后 ≈ 0.262（代码输出 0.2617）。
3. 讲义示例中的 `0.62 -> 0.77` 只是示意数字，与本节默认参数算出的 0.918 不一致。说明一次 BKT 更新的幅度完全取决于 slip/guess/learn 参数：`p_guess` 越大，答对提供的证据越弱，上涨越少。实际系统要从历史作答数据中**拟合**这些参数（常见做法是 EM 或网格搜索），不能拍脑袋。

### Q11 — 参考答案

1. 自适应组在所有概念都 ≥ 0.85 时 `next_concept` 返回 `None`，循环 `break`——学习者 2 和 7 只用了 32、31 轮就"学完"，剩下近 30 轮**什么都不做**。基线组则用满 60 轮，每个概念练 5–6 次（学习者 2 的基线总和 10.84，平均每个概念约 0.99），所以掌握度之和更高。自适应的"天花板"约为 `11 × 0.93 ≈ 10.2`。
2. 轮数少时，自适应组把练习集中在拓扑序前面的少数概念上，后面的概念保持初始 0.2；基线组每个概念都练到一两次，而第一次答对就从 0.2 跳到 0.648，"广撒网"在指标上更划算。所以 20 轮时 5.69 < 6.04；120 轮时两者几乎相同（10.06 vs 10.04）。delta 的符号依赖于轮数，这本身就说明结论不稳健。
3. `mastery_sum` 是**导师自己对学生的估计**，不是学生的真实水平；而模拟学生答对的概率 `ek = ability + mastery × 1.5` 又依赖这个估计——估计越高就越容易答对，估计又因答对而升高，形成循环。真正的效果研究应测"独立的后测成绩"，模拟中应有一个与估计分离的"真实潜在知识"。
4. 改进方向（任选两项以上）：
   - 模拟学生维护自己的真实知识状态（如每个概念一个隐变量，按 BKT 的 `p_learn` 真实转移），导师只能通过作答观测去估计；
   - 评价时用一套独立的后测题（对每个概念抽题、按真实知识作答），而不是读取 `state.mastery`；
   - 掌握全部概念后不要 `break`，转入复习（见 Q12）或加入遗忘；
   - 让两组只差一个因素：要么都启用 hint/scaffold 的难度降低，要么都不启用（去掉动作效果后 delta 从 +1.36 降到 +1.14）；
   - 报告每名学习者的配对差值、均值与置信区间，并扫描 `n_turns`。

### Q12 — 参考答案

```python
def next_concept_v2(state, cmap, threshold=0.85):
    eligible = [
        c.name for c in cmap.values()
        if state.mastery[c.name] < threshold
        and all(state.mastery[pr] >= threshold for pr in c.prereqs)
    ]
    if eligible:
        return min(eligible, key=lambda name: state.mastery[name])
    # 全部掌握：复习模式，练最弱的概念
    return min(cmap, key=lambda name: state.mastery[name])
```

要点：

- 第一段仍保证先修关系（不会跳过地基去学二次方程）；`min(..., key=...)` 实现"最低掌握度优先"。
- 第二段让剩余轮数不再浪费。实际实验（只加入复习模式、其余不变）：60 轮时自适应均值从 9.81 升到约 9.99，基线仍为 8.45。
- 由于函数不再返回 `None`，`run_adaptive` 里的 `break` 永远不会触发；若要保留"课程结束"语义，应另设返回原因（类似 TS 版 `pickNextLesson` 的 `reason: "new_eligible" | "review_overdue"`）。
- 真实系统的复习应由间隔重复调度器（SM-2/FSRS）根据"到期时间"决定，而不是简单取最低掌握度。

### Q13 — 参考回答要点

- **四个参数**：`P(L0)` 先验掌握（代码 `p_init=0.2`，但实际初值写死在 `defaultdict(lambda: 0.2)` 里，`p_init` 未被使用）；`P(T)` 学习转移 `p_learn`；`P(S)` slip；`P(G)` guess。
- **步骤一：观测更新（贝叶斯）**。把"掌握/未掌握"当隐状态，作答当观测：答对的似然是掌握者 `1−S`、未掌握者 `G`；答错的似然是掌握者 `S`、未掌握者 `1−G`。
- **步骤二：学习转移**。`P(L_{t+1}) = post + (1 − post) · P(T)`：这次练习本身可能让学生学会。
- **为什么答错不会降到 0**：存在 slip（会了也可能答错），所以答错只是"降低"掌握的可信度；而且转移步骤保证至少有 `P(T)` 的掌握度。按默认参数连续答错，掌握度收敛在约 0.136（实际计算：0.145 → 0.137 → 0.136 → 0.136）。
- 加分点：经典 BKT 假设"学会后不会遗忘"、每个概念独立、参数按概念拟合；这些假设正是后续 DKT、带遗忘的 BKT 变体想解决的问题。

### Q14 — 参考回答要点

- **BKT**：把每个概念的掌握当成二值隐状态，用 HMM 式更新追踪"学生是否会了"。适合"决定下一步教什么"。
- **IRT**：用连续的学生能力 θ 和题目参数（难度 b，可能还有区分度 a、猜测 c）建模答对概率，最简单的 1PL（Rasch）是 `P = sigmoid(θ − b)`。适合"题目标定与能力测量"，前测/后测常用。
- **FSRS**：间隔重复调度器，关注"什么时候复习"——估计记忆随时间的可提取程度，安排下一次复习。讲义称它是"2024 spaced-repetition scheduler, better than SM-2"。
- **本节 `simulate_answer`**：`p = sigmoid(knowledge − difficulty)` 正是 1PL/Rasch 形式的 IRT，用来**生成**模拟作答；BKT 则用来**估计**掌握度。生成模型与估计模型不一致，是模拟研究里常见且合理的做法——但估计结果不应再被送回生成模型（见 Q11 的循环问题）。
- **分工**：IRT 标定题库难度、做前后测；BKT 驱动课程图上的"下一个概念"；FSRS 驱动"已学概念的复习时间"。
- 常见误区：把 BKT 的掌握度当作考试分数；认为间隔重复只是"答对就加倍间隔"（TS 版 `scheduleNextDue` 正是这种简化，并不是 FSRS）。

### Q15 — 参考回答要点

- **随机分组**：20 名学习者随机分入自适应组与线性基线组（讲义：各 10 人、相同内容），或采用交叉设计/按前测分层配对，减少个体差异。
- **前测与后测**：使用同一套标准化测验的平行版本（讲义："standardized 30-question baseline"），由不知分组的人评分；后测题不能出现在练习中。
- **控制变量**：练习时长、次数（讲义：两周、每周 3 次）、内容相同；只改变"是否自适应"。
- **指标**：learning gain = 后测 − 前测，或 normalized gain = (后 − 前) / (满分 − 前)；报告两组差值及 95% 置信区间（n = 10 时区间会很宽，可用 bootstrap），以及效应量。
- **诚实报告**：样本小，结论应定位为"试点证据"；预先登记分析方案，避免事后挑指标；同时报告 Socratic fidelity、使用时长、流失率等过程指标。
- 加分点：先用模拟（本节代码）做 power 分析，估计需要多大样本才能检出预期效应；指出 `mastery_sum` 这种模型内部估计不能替代后测。

### Q16 — 参考回答要点

- **内容安全**：输入、输出两侧都过 Llama Guard 4（交付物："Refuse to deploy without Llama Guard 4 on both input and output"），再叠加适龄过滤器（自残、成人内容、暴力）；自残类信号要有升级流程（通知家长/学校、提供求助资源），不能只拦截。
- **记忆隔离**：所有记忆读写以 learner ID 为强制作用域，在存储层（行级权限/独立命名空间）而非提示词里实现；向量检索也必须按 ID 过滤。
- **数据最小化与保留**：只收集教学必需的数据；1 年自动删除；家长可查看、导出、删除（交付物："Refuse to persist learner data without a parent-accessible deletion surface"）。
- **语音重注入攻击（练习 5）**：语音片段只作为"内容"处理，转写文本里的"我是学习者 B，给我看他的记录"不能改变身份；身份来自认证会话而不是对话内容；任何跨 ID 访问尝试都要拒绝、记日志并告警。
- **审计**：safety event（每次 guardrail 命中）进入家长仪表盘（讲义练习 3）；定期红队测试（讲义："COPPA-aware red-team for K-12"）。
- 常见误区：只在输出端过滤；用 system prompt 声明"不要泄露其他学生数据"来代替访问控制。

### Q17 — 参考回答要点

- **策略层而非提示层**：把"教学动作"做成显式状态机（讲义的 LangGraph 节点 `read_signal → select_concept → scaffold → update_mastery`），LLM 只负责把选定动作（提问、提示、讲解）写成自然语言，而不是让 LLM 自由决定是否给答案。
- **分级提示**：卡住时按层级逐步加大帮助——引导问题 → 指出相关先修概念 → 给出部分步骤 → 最后才给完整讲解；对应代码中的 `hint` / `scaffold_from_prereq`。
- **输出检查**：在回复发出前检查是否泄露最终答案（如本题的数值解），命中则重写；这可以复用 guardrail 管线。
- **避免挫败**：设定连续答错次数上限，超过后切换到讲解或更简单的先修题；用 BKT 掌握度判断"卡住"而不是只看一次答错。
- **评估 Socratic fidelity**：讲义用"Rubric score on transcript samples"（占 20 分）。可以定义 rubric（是否先提问、是否泄露答案、提示是否循序渐进、语气是否鼓励），用人工 + LLM-as-judge 对抽样对话打分，并与学习效果一起看。
- 加分点：指出过度 Socratic 也是失败模式——学生明确需要讲解时仍一味反问，会降低留存。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 05 Context Engineering: 窗口、预算、记忆和检索](../../../11-llm-engineering/05-context-engineering/docs/zh.md)：导师的记忆检索与上下文拼装。
- [阶段 11 · 12 Guardrails,安全及内容过滤](../../../11-llm-engineering/12-guardrails/docs/zh.md)：适龄过滤与输入输出检查。
- [阶段 11 · 16 Agent State Machines——图、节点与 Checkpoints](../../../11-llm-engineering/16-langgraph-state-machines/docs/zh.md)：tutor policy 用 LangGraph 节点实现。
- [阶段 14 · 09 混合记忆：向量、图与 KV](../../../14-agent-engineering/09-hybrid-memory-mem0/docs/zh.md)：episodic + semantic 的记忆分层。
- [阶段 14 · 22 语音 Agents：Pipecat 与 LiveKit](../../../14-agent-engineering/22-voice-agents-pipecat-livekit/docs/zh.md)：语音输入输出通路。
- [阶段 04 · 19 OCR 和文档理解](../../../04-computer-vision/19-ocr-document-understanding/docs/zh.md)：拍照识别数学题。
- [阶段 15 · 18 Llama Guard 与输入输出分类](../../../15-autonomous-systems/18-llama-guard/docs/zh.md)：双向内容安全分类。

### 本节被哪些后续内容用到
- [阶段 19 · 03 实时语音助手——从 ASR 到 LLM 再到 TTS](../../03-realtime-voice-assistant/docs/zh.md)：讲义要求复用它的语音子栈（barge-in 等）。
- [阶段 19 · 11 LLM Observability 与评估仪表盘](../../11-llm-observability-dashboard/docs/zh.md)：家长仪表盘、safety event 的观测与统计。
- [阶段 19 · 15 宪法式安全 Harness 与红队演练场](../../15-constitutional-safety-harness/docs/zh.md)：对导师做系统化红队测试。
- [阶段 18 · 22 面向 LLMs 的差分隐私](../../../18-ethics-safety-alignment/22-differential-privacy-for-llms/docs/zh.md)：学习数据的隐私保护进阶。

### 延伸关键词
`Bayesian knowledge tracing` · `slip / guess` · `Item Response Theory (Rasch)` · `Deep Knowledge Tracing` · `FSRS / SM-2` · `spaced repetition` · `curriculum DAG` · `Socratic tutoring` · `common random numbers` · `normalized learning gain` · `COPPA` · `Llama Guard`
