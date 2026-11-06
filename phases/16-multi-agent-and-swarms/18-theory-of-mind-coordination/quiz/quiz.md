# 测验 · 心智理论与涌现协调（Theory of Mind and Emergent Coordination）

> **阶段 16 · 多智能体与集群 · 第 18 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Theory of Mind（ToM，心智理论） | 对"别人相信什么"建模的能力，按阶数分级：0 阶不建模他人，1 阶"A 相信 X"，2 阶"A 相信 B 相信 X" |
| 2 | Sally-Anne 错误信念测试 | 1985 年的发展心理学实验；讲义："LLMs 能通过直白版本，但叙事变长、场景多次切换或问法间接时会失败" |
| 3 | Li et al. 2023（arXiv:2310.10701） | 合作文字游戏中 LLM agent 出现高阶 ToM，但长程任务因上下文管理和 hallucination 失败 |
| 4 | Riedl 2025（arXiv:2510.05174） | 三个指标：identity-linked differentiation、goal-directed complementarity、higher-order synergy；**只有 ToM prompt 条件**三项都显著高于基线，低能力模型只有"虚假涌现" |
| 5 | Coordination illusion（协调幻觉） | 演示里的"涌现协调"常来自 prompt 里写死的"一起工作"、观察者偏差、事后挑选成功样本 |
| 6 | 最小 ToM agent 结构 | `own_beliefs` + `other_models{agent_id → 归因给他的信念}` + 他人动作历史；行动选择时预测他人下一步再选联合最优 |
| 7 | 长程退化的原因与缓解 | 忘记"哪条信念属于谁"（身份绑定断裂）+ hallucination 写入错误信念；缓解：prompt 中显式结构化 ToM 状态、缩短推理链、外部 ToM 存储 |
| 8 | ToM 在生产中的失效场景 | 对抗环境（好 ToM 反而易被利用）、异构模型团队（ToM 不泛化）、依赖客观事实的任务（ToM 分散注意力） |
| 9 | 可度量的协调信号 | complementarity（动作随时间覆盖不相交子任务）、anticipation（基于对他人未来动作的正确预测而行动）、correction（误读后两轮内纠正） |
| 10 | 本节代码的真实结论 | 1 阶 ToM 的全部收益来自第 0 轮注入的"偏好先验"（prime）；去掉 prime 后两种 agent 的结果**完全相同**——这恰好演示了"协调依赖于条件，不是免费的" |

### 核心技能（能动手做到）

- [ ] 把一句话归类到 0/1/2 阶 ToM，并写出对应的 `other_models` 数据结构（2 阶是嵌套一层）
- [ ] 读懂 `run_trial` 的"同时承诺 → 互相观察 → 统计碰撞 → 按插入顺序结算"流程，并手算 3 agent / 3 box 随机策略的期望碰撞数（17/18）与期望轮数（11/6）
- [ ] 设计"去掉 prime"的对照实验，并解释为什么本代码中 ToM 推理在没有 prime 时完全失效
- [ ] 为一个宣称"涌现协调"的系统设计 control condition、统计检验和 complementarity 指标
- [ ] 往 ToM 状态里注入 hallucination（随机翻转信念），量化性能退化
- [ ] 说出长程任务中 ToM 退化的两种错误类型（身份混淆 vs 内容幻觉）及其工程缓解

---

## 二、基础自测（选择题）

**Q1.** "调度 agent 认为：审核 agent 以为写作 agent 已经完成了初稿。" 这句话体现的是几阶 ToM？

- A. 二阶（second-order）
- B. 一阶（first-order）
- C. 零阶（zeroth-order）
- D. 三阶，因为句子里出现了三个 agent

**Q2.** 关于 LLM 在 Sally-Anne 类错误信念测试上的表现，讲义的结论是：

- A. GPT-4 时代的 LLM 在所有版本上都失败，说明它们没有任何 ToM
- B. 只要模型足够大，无论叙事多长都能稳定通过
- C. LLM 只能通过二阶版本，无法通过一阶版本
- D. 直白提问时能通过；叙事很长、场景多次变化或问法间接时会失败

**Q3.** Riedl 2025 的人群规模实验得出的核心结论是：

- A. 只要 agent 数量足够多，协调就会自发涌现，与 prompt 无关
- B. 只有在 ToM prompt 条件下，三项指标都显著高于基线；大模型不加 ToM prompt 也有一些协调，但效应比显式 prompt 小
- C. ToM prompt 对大模型和小模型的效果完全相同
- D. higher-order synergy 是唯一有意义的指标，其余两项可以忽略

**Q4.** 实际运行本节 `code/main.py`（200 次试验、3 agent、3 box、10 轮预算），输出最接近：

- A. 零阶：完成率约 60%、碰撞率约 35%；一阶 ToM：完成率约 95%、碰撞率约 5%
- B. 零阶：200/200 完成、碰撞 0.00/试验；一阶 ToM：200/200 完成、碰撞 0.96/试验
- C. 零阶：200/200 完成、碰撞 0.96/试验、平均 1.85 轮；一阶 ToM：200/200 完成、碰撞 0.00/试验、平均 1.00 轮
- D. 两者都只有约一半试验能在 10 轮内完成

**Q5.** 在本代码的 3 agent / 3 box 设定下，零阶 agent **永远**不会在 10 轮预算内失败，最根本的原因是：

- A. 零阶 agent 会记住自己上一轮去过的箱子
- B. 随机种子固定为试验编号，恰好没有抽到坏情况
- C. 碰撞时所有相关 agent 都能拿到 token
- D. 每一轮至少有一个被选中的箱子被成功领取，3 个箱子最多 3 轮就领完

**Q6.** 一阶 ToM agent 在第 0 轮被 prime 后（agent-i 观察到其它 agent-j 的"偏好"是 `j % n_boxes`），在 3×3 设定下它第一轮的选择是：

- A. 确定性地选择箱子 i（候选集只剩它自己的编号）
- B. 在三个箱子中均匀随机
- C. 选择编号最小的箱子 0
- D. 选择其它 agent 偏好的箱子，以便"抢先"

**Q7.** 下列哪一项**不是**讲义列出的"协调幻觉"来源？

- A. system prompt 里写了"大家一起协作"，把协调预先写死
- B. 观察者偏差：我们看到了自己预期的模式
- C. 设置了去掉协调 prompt 的 control condition，并在 n ≥ 50 次试验上检验出 p < 0.05 的差异
- D. 事后只挑选成功的运行结果展示

**Q8.** 讲义的三个"可度量协调信号"中，**anticipation（预期）**指的是：

- A. 多轮任务中各 agent 的动作覆盖互不相交的子任务
- B. agent A 在 T+1 轮的动作依赖于对 B 在 T+2 轮动作的预测，而且这个预测后来被证实是对的
- C. A 在 T 轮误读了 B 的信念后，到 T+2 轮能自我纠正
- D. 群体取得了任何子集都无法取得的成果

---

## 三、动手 / 代码题

**Q9.** 代码最后打印："remove the prime (comment out the observe loop) to see how the effect vanishes"。照做后（去掉 `if tom:` 下的预先观察循环），200 次试验的结果是：

```text
noprime  zeroth-order     dups/trial=0.965  avg_turns=1.855
noprime  first-order ToM  dups/trial=0.965  avg_turns=1.855
```

两行**逐位相同**。下面是 ToM 分支的核心代码：

```python
        last_turn_targets = {box for _, box in self.observations[-(len(world.boxes_with_tokens) + 2):]}
        options = [b for b in available if b not in last_turn_targets]
        return rng.choice(options) if options else rng.choice(available)
```

1. 证明：没有 prime 时，`options` 永远等于 `available`，因此 ToM agent 的行为（连同随机数消耗）与零阶 agent 完全一致。
2. 由此说明：这份代码里的"一阶 ToM 收益"本质上来自什么？它与讲义"Agents cannot communicate"的设定是否矛盾？
3. 如何改造任务，使"从他人动作推断意图"真的能产生信息？

**Q10.** 手算零阶 agent（每个未完成的 agent 在剩余箱子中均匀随机选择）在 3 agent / 3 box 下：

1. 第一轮期望碰撞数（代码计法：每个箱子被 n 个 agent 选中记 n−1 次）；
2. 整个试验的期望碰撞数与期望轮数。

并与实际运行的 0.96 / 1.85（200 次）对比。

**Q11.** 讲义练习 1 问"5 agent、5 box 时差距是否还在"。实测（200 次试验，原代码只改参数）：

| 设定 | 零阶 dups/试验 | 零阶平均轮数 | ToM dups/试验 | ToM 平均轮数 |
|------|--------------|------------|--------------|------------|
| 5 agent × 5 box | 1.97 | 2.29 | 0.00 | 1.00 |
| 3 agent × 5 box | 0.555 | 1.53 | 0.635 | 1.57 |
| 5 agent × 3 box | 3.13 | 10.0 | 3.06 | 10.0 |

1. 为什么 5×5 时 ToM 依然是完美的 0.00？
2. 为什么 3 agent × 5 box 时 ToM 反而比零阶**更差**？
3. 为什么 5 agent × 3 box 时两种 agent 的平均轮数都是 10.0？这对 `bench` 的"full-completion"统计意味着什么？

**Q12.** 完成讲义练习 3：往 ToM 状态里注入 hallucination。要求：每个 ToM agent 在每次 `choose_target` 前，以概率 `p` 随机挑一条观察记录，把其中的箱子编号换成随机值。写出实现，并预测 `p = 0 / 0.5 / 1.0` 时碰撞数的趋势。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 Theory of Mind？0 阶、1 阶、2 阶 ToM 在 LLM 多 agent 系统中分别对应什么样的状态结构？举一个必须用到 2 阶 ToM 的协作场景。

**Q14.**（原理深挖）Li et al. 2023 指出 LLM agent 的 ToM 在长程任务中退化。请解释退化的机制，并说明三种缓解手段分别针对哪种错误。

**Q15.**（工程实践）产品经理说"我们的多 agent 系统出现了涌现协调"。你会如何设计实验来验证或证伪这一说法？

**Q16.**（场景设计）你要给三个 LLM 客服 agent（退款、物流、技术支持）加上 ToM 能力，避免它们重复回复同一用户或互相踩踏。请设计 ToM 状态的存储方式、注入方式和效果度量。

**Q17.**（追问型）本节代码里，ToM agent 碰撞数降到 0，是"ToM 推理"的胜利吗？如果面试官追问"这和直接给每个 agent 分配一个固定箱子有什么区别"，你怎么回答？再追问：ToM 能力越强，系统就越安全吗？

---

## 五、参考答案与解析

### Q1 — 答案：A

"调度 agent 认为（1 层）审核 agent 以为（2 层）写作 agent 已完成"：调度 agent 在为"审核 agent 关于写作 agent 状态的信念"建模，即"A believes B believes X"，是二阶 ToM。
- B 一阶只到"审核 agent 以为初稿完成"这一层；
- C 零阶不对他人建模；
- D 错在把"出现几个 agent"当成阶数，阶数看的是信念的嵌套层数，而不是人数。

### Q2 — 答案：D

讲义："GPT-4-era LLMs pass Sally-Anne-style tests when posed plainly. They fail when the narrative is long, the scene changes several times, or the question is phrased indirectly."
- A、B 都是极端化；
- C 颠倒了难度：二阶比一阶更难。

### Q3 — 答案：B

讲义："only under the ToM prompt condition do all three metrics produce signal above baseline... Large models show some coordination without explicit ToM prompting but the effect is smaller than with explicit prompting."
- A 与结论相反（协调依赖 prompt 条件，"not free"）；
- C 错：讲义强调效应依赖模型（"model-dependent"），低能力模型只有虚假涌现；
- D 错：三个指标共同构成判断依据。

### Q4 — 答案：C

实际输出：

```text
  zeroth-order     full-completion=200/200   duplications/trial=0.96  avg_turns=1.85
  first-order ToM  full-completion=200/200   duplications/trial=0.00  avg_turns=1.00
```

- A 是讲义"Expected output"的描述，与代码实际行为不符（见 Q10：在这个设定下完成率不可能低于 100%）；
- B 把两行数据弄反了；
- D 与实际不符。

### Q5 — 答案：D

`run_trial` 的结算逻辑：每个被选中的箱子至少有一个 agent（字典插入顺序第一个）成功领取。因此只要还有 agent 在选，每轮至少消耗一个箱子；3 个箱子最多 3 轮。用 2000 个种子实测，零阶的最大轮数就是 3。
- A 错：零阶分支 `rng.choice(available)` 不看任何历史；
- B 错：这是结构性保证，与种子无关；
- C 错：碰撞时只有一个 agent 能领取，其余浪费一轮。

讲义"零阶在 10 轮内只完成约 60%"在这个任务设计下不可能出现。

### Q6 — 答案：A

agent-0 的观察记录是 `[("agent-1", 1), ("agent-2", 2)]`；窗口 `observations[-(3+2):]` 取到这两条，`last_turn_targets = {1, 2}`，`options = [0]`，所以 `rng.choice([0])` 必然返回 0。实测 10 个不同种子都返回 0。三个 agent 各自确定性地去自己编号的箱子，第一轮就无碰撞完成，这就是 ToM 行"0.00 / 1.00"的来源。
- B 是零阶或没有 prime 时的行为；
- C、D 与代码逻辑不符。

### Q7 — 答案：C

C 正是讲义"Ship It"清单要求的**合格证据**（control condition + 统计检验），而不是幻觉来源。A、B、D 都是讲义"The coordination illusion"一节列出的三个来源：prompt 里写死协调、observer bias、事后挑选成功运行。

### Q8 — 答案：B

讲义："Does agent A's action at turn T+1 depend on a prediction about B's action at T+2 that turned out correct?"
- A 是 complementarity；
- C 是 correction；
- D 是 Riedl 的 higher-order synergy，不属于这三个实操信号。

### Q9 — 参考答案

1. **证明**：设第 t 轮被承诺的箱子集合为 S_t。结算时，S_t 中每个箱子都至少被一个 agent 领取（只要箱子里还有 token，而 agent 只会从 `available` 里选，所以一定有）。因此第 t+1 轮的 `available ∩ S_t = ∅`。更早轮次承诺过的箱子也同样早已被领走。没有 prime 时，`observations` 里**只有**历史承诺，于是 `last_turn_targets ∩ available = ∅`，`options == available`，`rng.choice(options)` 与零阶的 `rng.choice(available)` 用同一个列表、同一个 rng，抽出的值逐位相同。第一轮观察为空，两者也相同。所以结果逐位一致。
2. **收益来源**：全部来自第 0 轮的 prime——每个 agent 被告知其它 agent "偏好" `j % n_boxes`，等价于一次免费的、无噪声的**通信/角色分配**。代码 docstring 自己也写了 "simulating a cheap communication channel"，这与讲义"Agents cannot communicate; they infer intent from each other's actions"的设定矛盾：代码里的 agent 从未真正"从动作中推断意图"。
3. **改造方向**：让"意图"在**被兑现之前**可被观察。例如：
   - 箱子与 agent 之间有距离，走到箱子需要 2–3 轮，每轮公布位置，ToM agent 根据别人的移动方向推断目标并改道；
   - 或者允许"承诺"与"领取"分离：本轮先公开朝向，下一轮才结算；
   - 去掉 prime，然后与零阶做对照；只有这时测到的差异才是"从动作推断意图"带来的。

### Q10 — 参考答案

1. 第一轮：3 个 agent 各自在 3 个箱子中均匀选择，共 27 种结果。碰撞数 = 3 − 不同箱子数。不同箱子数为 3 的有 6 种，为 2 的有 18 种，为 1 的有 3 种：`E = (6×0 + 18×1 + 3×2)/27 = 24/27 = 8/9 ≈ 0.889`。
2. 设 k 个 agent 面对 k 个箱子（本任务中两者始终相等）。递推 `D(k) = E[k − distinct] + E[D(k − distinct)]`、`T(k) = 1 + E[T(k − distinct)]`，`D(0)=T(0)=0`：
   - `D(1)=0, T(1)=1`；
   - `D(2)=1/2, T(2)=3/2`；
   - `D(3)=17/18 ≈ 0.944`，`T(3)=11/6 ≈ 1.833`。
   （用 `fractions.Fraction` 精确枚举验证；有趣的是在算过的 k = 1、2、3、5 上，T(k) 都恰好等于调和数 H_k；5×5 时 T(5)=137/60≈2.283、D(5)≈1.971，与 Q11 表中 2.29 / 1.97 吻合。）

实测 200 次为 0.965 / 1.855（打印为 0.96 / 1.85），2000 次为 0.926 / 1.826，都在理论值附近波动。代码 Takeaways 里写死的 "0.96 duplications" 只是这一组种子的结果，不是从运行中计算的。

### Q11 — 参考答案

1. **5×5 仍完美**：prime 让 agent-i 看到其它 4 个 agent 的偏好 `{0..4} \ {i}`，窗口 `-(5+2)` 足够容纳 4 条，`options = [i]`，依旧是确定性的一人一箱。差距"持续存在"，但原因仍是 prime 等价于角色分配，不是 ToM 推理能力的扩展。
2. **3×5 反而更差**：agent-0 避开 {1,2}，候选 {0,3,4}；agent-1 候选 {1,3,4}；agent-2 候选 {2,3,4}。三个 agent 都有 2/3 概率挤到 {3,4} 上，而零阶在 5 个箱子中均匀选择，碰撞概率反而更低。说明"避开别人偏好"的启发式在箱子多于 agent 时把大家都赶到了同一批"无人认领"的箱子上——这是 **anti-coordination 启发式失效**的好例子。
3. **5×3 都是 10.0**：agent 数多于箱子数，最多只有 3 个 agent 能完成，`all(a.collected ...)` 永远为假，循环跑满 10 轮（后面几轮所有人 `choose_target` 返回 −1，空转）。`bench` 中 `if c == 3` 是写死的 3，这里恰好仍能统计，但若换成 3 agent × 2 box 则"完整完成"永远为 0；更合理的写法是 `c == min(n_agents, n_boxes)`，并在没有可选箱子时提前 `break`。

### Q12 — 参考答案

参考实现（以猴子补丁方式包装原 `choose_target`，已实际运行）：

```python
import random
orig_choose = Agent.choose_target

def make_hallucinating(p_flip: float, n_boxes: int):
    def choose(self, world, rng):
        if self.tom and self.observations and rng.random() < p_flip:
            k = rng.randrange(len(self.observations))
            who, _ = self.observations[k]
            self.observations[k] = (who, rng.randrange(n_boxes))  # 内容幻觉：身份对，箱子错
        return orig_choose(self, world, rng)
    return choose

Agent.choose_target = make_hallucinating(1.0, 3)
```

实测（200 次，3×3，ToM）：

| p_flip | dups/试验 | 平均轮数 |
|--------|----------|---------|
| 0.0 | 0.000 | 1.000 |
| 0.5 | 0.640 | 1.605 |
| 1.0 | 0.890 | 1.790 |

p = 1 时几乎退化到零阶（0.96 / 1.85）。原因：prime 只有 2 条信息，翻错其中一条就会让 agent 的候选集出错（例如 agent-0 以为 agent-1 偏好 0，候选集变成 {1}，直接撞上 agent-1）。这说明**信念越"关键"、冗余越少，单个 hallucination 的破坏越大**；讲义建议的"显式结构化 ToM 状态 + 外部存储"可以对每条信念做来源校验，降低这种破坏。注意这里模拟的是**内容幻觉**（身份对、内容错）；要模拟**身份混淆**，可改为交换两条记录的 agent 名字。

### Q13 — 参考回答要点

- **定义**：对其他 agent 的信念（而非仅其动作）建模的能力；讲义按阶数分级。
- **状态结构**：
  - 0 阶：只有 `own_beliefs`，只基于自己的观察行动；
  - 1 阶：`other_models: {agent_id: beliefs}`，"Alice 相信 X"；
  - 2 阶：`other_models[i]` 里再嵌套 `other_models_of_j`，"Alice 相信 Bob 相信 X"。
- **2 阶场景举例**：协调者要判断"审核 agent 是否知道写作 agent 已更新草稿"，以决定是否需要通知审核 agent 重新拉取；谈判中"对方认为我认为底价是多少"。
- 加分点：说明阶数每加一层，状态规模乘以 agent 数，且 hallucination 会在嵌套中放大；Sally-Anne 是一阶 ToM 的经典测试。

### Q14 — 参考回答要点

- **机制**（讲义）：上下文限制让 agent **忘记哪条信念属于谁**（identity-belief binding 断裂）；hallucination 把**错误信念**写进他人模型；两者叠加产生"我以为他以为 X"的错误并随时间累积。
- **缓解与对应关系**：
  - 显式结构化 ToM 状态（`{agent_id: belief_list}`）→ 主要对付身份绑定断裂；
  - 缩短推理链、减少每轮 ToM 更新次数 → 减少 hallucination 的累积；
  - 外部 ToM 存储、每轮只注入相关部分 → 同时对抗上下文溢出和无关信息干扰。
- 加分点：给出可观测指标——记录每轮 ToM 状态并与真实状态比对，分别统计"身份错误率"和"内容错误率"；对应本节练习 4（10→30 轮的退化曲线）。

### Q15 — 参考回答要点

- **明确主张**：协调具体指什么——分工、预期、互补、共识？（`skill-tom-auditor` 第 1 步）
- **检查 prompt**：system prompt 是否写了"协作""分工"之类的话；若有，主张至少部分是 prompt-dressed。
- **对照组**：去掉协调相关语句的版本，其它完全不变；本节代码的"去掉 prime"就是一个对照组，一跑就发现效应完全消失。
- **指标**：至少一个可度量指标——complementarity（动作不相交程度）、identity-linked differentiation、higher-order synergy；不接受"看起来在协作"。
- **统计检验**：系统 vs 对照在 n ≥ 50 次试验上 p < 0.05，小样本要报告功效。
- **模型能力检查**：换小模型重复；Li 和 Riedl 都表明效应依赖模型能力。
- **失败日志**：记录 ToM 状态，区分身份混淆和内容幻觉。
- 常见误区：只展示成功 demo；只看最终成功率，不看过程中的互补性。

### Q16 — 参考回答要点

- **状态存储**：外部 ToM store（如 KV 或数据库），以 `conversation_id → {agent_id: {believed_user_issue, believed_actions_taken, last_update_turn, source_msg_id}}` 结构保存；每条信念带来源和时间戳，便于校验和过期。
- **注入方式**：每轮只把与当前用户相关的其它 agent 状态，以结构化 JSON 注入 prompt（讲义缓解 1、3）；涉及"别人以为我已处理"时才展开到 2 阶。
- **动作选择**：回复前预测其它 agent 是否会处理同一问题（例如物流 agent 是否已承诺退款时间），冲突时让出或先声明。
- **度量**：重复回复率（两个 agent 就同一问题回复）、互相矛盾的承诺数、用户需要重复描述问题的次数；做 A/B：有 ToM 注入 vs 无；统计显著性。
- **风险**：对抗用户可能利用 agent 间的信念差（"技术支持说可以退款"），需要以客观系统记录为准，ToM 只用于协调，不作为事实依据（讲义"ground-truth-dependent tasks"）。

### Q17 — 参考回答要点

- **不是 ToM 推理的胜利**：Q9 已证明去掉 prime 后 ToM 分支与零阶逐位相同；碰撞为 0 是因为 prime 让每个 agent 确定性地去自己编号的箱子，等价于**事先分配角色**。
- **与固定分配的区别**：在本代码里**没有区别**。真正的 ToM 应该体现在：信息是**推断**出来的、会被更新、能在对方行为偏离预期时纠正（correction）。要证明这一点，需要一个"意图在兑现前可观察"的任务和去掉 prime 的对照组。
- **这本身是讲义的论点**：协调是 prompt/条件依赖的（Riedl："load-bearing"的是 ToM prompt 条件）；本代码中 prime 扮演了 ToM prompt 的角色。
- **ToM 越强越安全吗？** 不是。讲义："Agents with good ToM are easier to manipulate"——你可以建模对方如何建模你，再加以利用；异构团队中 ToM 不能泛化；依赖事实的任务中 ToM 可能分散注意力。
- 加分点：主动指出代码中 `last_turn_targets` 的窗口长度 `len(boxes)+2` 是与 agent 数无关的启发式，以及 3×5 设定下"避让"反而增加碰撞。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 07 心智社会与多 Agent 辩论](../../07-society-of-mind-debate/docs/zh.md)：讲义列出的先修课，多 agent 交互的基本框架。
- [阶段 16 · 17 生成式 Agents 与涌现模拟](../../17-generative-agents-simulation/docs/zh.md)：讲义列出的先修课，"涌现"行为的另一种来源。
- [阶段 16 · 13 共享记忆与黑板模式](../../13-shared-memory-blackboard/docs/zh.md)：外部 ToM 存储可以看作一种结构化共享记忆。
- [阶段 09 · 10 多Agent RL](../../../09-reinforcement-learning/10-multi-agent-rl/docs/zh.md)：多 agent 环境中"他人策略"建模的 RL 视角。

### 本节被哪些后续内容用到
- [阶段 16 · 20 多智能体强化学习（MARL）：MADDPG、QMIX、MAPPO](../../20-marl-maddpg-qmix-mappo/docs/zh.md)：CTDE 中 critic 显式使用他人的观察与动作，是"他人建模"的训练时版本。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：协调失败与级联错误的系统分类。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../24-evaluation-coordination-benchmarks/docs/zh.md)：如何用基准量化"协调"。
- [阶段 18 · 12 红队测试：PAIR 与自动化攻击](../../../18-ethics-safety-alignment/12-red-teaming-pair-automated-attacks/docs/zh.md)：对抗环境中"建模对方"既是攻击手段也是防御对象。

### 延伸关键词
`Theory of Mind` · `false-belief test` · `Sally-Anne` · `recursive belief modeling` · `identity-linked differentiation` · `goal-directed complementarity` · `higher-order synergy` · `coordination illusion` · `control condition` · `anti-coordination game` · `belief hallucination` · `external belief store`
