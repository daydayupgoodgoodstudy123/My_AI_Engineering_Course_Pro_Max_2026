# 测验 · 多 Agent RL（Multi-Agent RL）

> **阶段 09 · 强化学习 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 非平稳性 | 站在任一智能体的视角，其他智能体就是环境的一部分；它们在学习、在变化，环境转移 `P(s'\|s, a_i)` 依赖于不断变化的 `π_{-i}`，单智能体收敛性证明不再成立 |
| 2 | Markov Game | `(S, A_1…A_n, P, R_1…R_n)`：联合动作决定转移，每个智能体有自己的奖励；奖励相同→完全合作，零和→对抗，其余→一般和 |
| 3 | 五大挑战 | 非平稳、信用分配、探索协调、可扩展性（联合动作空间随 n 指数增长）、部分可观测 |
| 4 | 独立学习（IQL / IPPO） | 每个智能体把别人当环境，各学各的；无理论收敛保证，松耦合任务常常够用，紧耦合任务表现差 |
| 5 | CTDE | 集中训练、分散执行：训练时 critic 看全局状态和联合动作，执行时每个策略只看本地观测；MADDPG、COMA、MAPPO、QMIX 都属于此类 |
| 6 | COMA 反事实基线 | "如果我换个动作、别人不变，结果会怎样？"——用边缘化掉自己动作的期望 Q 作 baseline，隔离个人贡献 |
| 7 | QMIX 单调值分解 | `Q_tot = f(Q_1, …, Q_n)` 且 f 对每个 `Q_i` 单调，保证"各自 argmax"等于"联合 argmax"，从而可分散执行 |
| 8 | 自博弈（Self-play） | 同一智能体的两个副本对打，对手是过去的自己；适合零和游戏（AlphaZero、OpenAI Five） |
| 9 | 联盟训练（League play） | 维护历史与当前策略的种群，从中采样对手，并加入专门找弱点的 exploiter；用于存在"石头剪刀布"式策略循环的游戏（AlphaStar） |
| 10 | 联合 Q vs 独立 Q | 联合 Q 拥有正确的全局视角但动作空间是 `\|A\|^n`；独立 Q 动作空间小但面对非平稳 |

### 核心技能（能动手做到）

- [ ] 运行 `main.py`，解释两条学习曲线的差异，并手算出该任务的最优回报 3.0
- [ ] 说出为什么这个任务中"先到的智能体需要等待"、以及它在没有 "stay" 动作时如何等待
- [ ] 计算独立 Q 与联合 Q 的表大小，并推广到 n 个智能体
- [ ] 从联合 Q 表实现"边缘化"的分散执行 `π_i(s) = argmax_{a_i} max_{a_{-i}} Q(s, a)`，并指出它可能导致的协调失败
- [ ] 改写 `step` 实现讲义练习中的"同一回合同时踏上目标"协调任务，并据实验结果讨论 IQL 何时会失效
- [ ] 针对给定场景（合作导航、零和棋类、多人即时战略、拍卖市场）选出 IPPO / MAPPO / QMIX / self-play / league 中合适的方法

---

## 二、基础自测（选择题）

**Q1.** 多智能体场景下，单智能体 Q-learning 的收敛保证失效，最根本的原因是：

- A. 状态空间太大
- B. 从单个智能体的角度看，其他智能体在学习、策略在变，环境变得非平稳
- C. 奖励是负数
- D. 折扣因子必须小于 0.9

**Q2.** 关于 CTDE（集中训练、分散执行），下列说法正确的是：

- A. 训练和执行时每个智能体都能看到全局状态
- B. 训练时 critic 可以使用全局状态与联合动作，执行时每个智能体的策略只依赖本地观测
- C. 执行时需要一个中央控制器统一下发所有动作
- D. CTDE 只能用于对抗场景

**Q3.** QMIX 要求混合函数对每个 `Q_i` **单调**，主要是为了：

- A. 减少参数量
- B. 保证每个智能体各自对 `Q_i` 取 argmax 得到的联合动作，也是 `Q_tot` 的 argmax，从而能分散执行
- C. 让 `Q_tot` 恒为正
- D. 使训练变成 on-policy

**Q4.** COMA 的反事实基线回答的问题是：

- A. "如果所有智能体都换动作，奖励会怎样？"
- B. "如果其他智能体不变、只有我换一个动作，期望回报会怎样？"——以此隔离我的贡献
- C. "环境的最优策略是什么？"
- D. "哪个智能体的 Q 值最大？"

**Q5.** 联盟训练（league play）相比纯自博弈，主要解决的问题是：

- A. 降低显存占用
- B. 纯自博弈可能陷入"石头剪刀布"式的策略循环；维护多样化的对手池可以打破循环
- C. 让训练变成完全合作
- D. 不再需要强化学习

**Q6.** 一个有 n 个智能体、每个智能体 4 个动作的任务，用单个联合 Q 表时，每个状态的动作数是：

- A. 4n
- B. 4
- C. 4ⁿ
- D. n⁴

**Q7.** 独立智能体使用经验回放（experience replay）时，比单智能体更容易出问题，原因是：

- A. 回放缓冲区太小
- B. 旧的 transition 是在其他智能体的"过时策略"下产生的，已经不能代表当前环境
- C. 经验回放只能用于 on-policy 算法
- D. 多智能体无法使用神经网络

**Q8.** 2026 年合作型多智能体任务（如协同导航）中，讲义认为占主导地位的方法是：

- A. 纯独立 Q-learning
- B. MAPPO（带集中式价值函数的 PPO）/ QMIX
- C. 遗传算法
- D. 联盟训练

---

## 三、动手 / 代码题

**Q9.**（读输出 + 手算）本节代码环境为 5×5 网格，两个智能体从 `(0,0)` 和 `(4,0)` 出发，都到达 `(4,4)` 才结束；每步奖励 -1，结束那一步奖励 +10。运行输出的最后部分为：

```text
final greedy evaluation (100 eps):
  independent-Q mean return = 3.00
  joint-Q       mean return = 3.00
```

(a) 证明 3.00 就是最优回报；(b) 智能体 2 只需 4 步就能到达目标，但回合要等智能体 1 走完 8 步才结束。环境里没有"原地不动"这个动作，智能体 2 是怎么"等待"的？

**Q10.**（复杂度分析）代码中两种方法的 Q 表定义为：

```python
Q1 = defaultdict(default_q)          # default_q 返回 {a: 0.0 for a in ACTIONS}
Q2 = defaultdict(default_q)
...
joint_actions = [(a, b) for a in ACTIONS for b in ACTIONS]
Q = defaultdict(lambda: {ja: 0.0 for ja in joint_actions})
```

(a) 状态是两个智能体位置的元组。训练 1500 回合后，实测 `len(Q1) = len(Q)= 624`。为什么是 624 而不是 625？(b) 分别计算独立 Q（两张表合计）与联合 Q 的表项数。(c) 推广到 n 个智能体、每个智能体 25 个位置、4 个动作，两种方法的表项数各是多少？

**Q11.**（扩展）讲义 Step 3 提到：用联合 Q 训练后，可以在执行时"边缘化"实现分散决策：`π_i(s) = argmax_{a_i} max_{a_{-i}} Q(s, a_1, a_2)`。请基于代码中的 `Q`（键是 `(a1, a2)` 元组）写出 `decentralized_actions(Q, s)`，返回 `(a1, a2)`。并说明：当存在**多个**并列最优联合动作时，这种做法可能出什么问题？

**Q12.**（改写环境 + 实验判断）讲义练习 Medium："the goal is reached only when both agents step onto it on the same turn"。请改写 `step` 实现这一规则，并回答：在本节这个 5×5、全局状态可见、确定性转移的设置下，你认为独立 Q-learning 还能收敛吗？如果能，IQL 真正容易失败的是什么样的设置？

---

## 四、面试高频题

**Q13.**（基础必考）什么是多智能体强化学习中的"非平稳性"问题？它为什么会破坏 Q-learning 的收敛性？常见的缓解手段有哪些？

**Q14.**（原理深挖）比较 MADDPG、COMA、MAPPO、QMIX：它们分别如何利用"集中训练"？各自解决了什么问题、有什么局限？

**Q15.**（原理深挖）QMIX 的单调性约束带来了什么好处？它的表达能力有什么限制？请举一个单调分解无法表示的协作情形。

**Q16.**（场景设计）你要为一个城市的 50 辆自动驾驶出租车设计调度/驾驶策略，每辆车只能看到周围局部信息，车辆数量会变化。你会选什么 MARL 方案？请说明训练与执行的信息访问方式、信用分配、评估方法。

**Q17.**（工程实践）你用自博弈训练一个两人对战游戏的 AI，训练曲线显示"对上一版本自己"的胜率稳定在 55%，但上线后被玩家用某种简单套路反复击败。可能的原因是什么？怎么改进训练与评估？

**Q18.**（结合大模型）LLM 多智能体系统（例如多个 agent 协作写代码、辩论）与经典 MARL 有什么异同？讲义说 RL 出现在"轨迹级而非 token 级"，你怎么理解？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："As they learn and change their behavior, the environment becomes non-stationary ... This breaks tabular convergence proofs (Q-learning's guarantee assumes a stationary environment)." A、C、D 都与多智能体特有的问题无关。

### Q2 — 答案：B

讲义："Each agent has its own *policy* π_i that conditions on local observation o_i ... During *training*, a centralized critic Q(s, a_1, …, a_n) conditions on the full global state and joint action." A 混淆了训练与执行；C 是"集中执行"，正是 CTDE 想避免的；D 错，CTDE 在合作场景最常用。

### Q3 — 答案：B

若 `∂Q_tot/∂Q_i ≥ 0`，那么每个智能体把自己的 `Q_i` 推到最大，`Q_tot` 也随之最大，即 `argmax_a Q_tot = (argmax_{a_1} Q_1, …, argmax_{a_n} Q_n)`。这正是讲义 Key Terms 所说的"allows decentralized argmax"。

### Q4 — 答案：B

讲义："ask 'what would my reward have been if I'd taken action a' instead?' — isolates my contribution"；Key Terms："Advantage = my Q minus expected Q marginalizing over my action." 即 `A_i = Q(s, a) - Σ_{a'_i} π_i(a'_i|o_i)·Q(s, (a'_i, a_{-i}))`。

### Q5 — 答案：B

讲义："League play ... Needed when the game admits 'rock-paper-scissors' strategy cycles"；Pitfalls："Pure self-play can get stuck in a dominance cycle. Fix: league play with diverse opponents."

### Q6 — 答案：C

联合动作 `(a_1, …, a_n)` 的组合数是 `4ⁿ`，讲义："The joint action space grows exponentially in n."。代码中 n=2 时就是 `joint_actions` 的 16 个元素。

### Q7 — 答案：B

讲义 Pitfalls："Experience replay with independent agents is worse than single-agent because old transitions were generated by now-obsolete opponents. Fix: relabel or weight by recency."

### Q8 — 答案：B

讲义："MAPPO ... Dominant in 2026 for cooperative MARL"；Use It 表："Cooperative navigation / manipulation | MAPPO / QMIX"。D 是针对复杂多人对抗游戏的方案。

### Q9 — 参考答案

(a) 智能体 1 从 `(0,0)` 到 `(4,4)` 的曼哈顿距离是 8，至少需要 8 步；回合在两者都到达的那一步结束。所以最少 8 步：前 7 步各 -1，第 8 步 +10，回报 `= -7 + 10 = 3`。评估是确定性的 greedy 策略、环境也是确定性的，100 个回合完全一样，所以均值恰好是 3.00。（注意评估用的是未折扣回报；训练时的 γ=0.95 只影响 Q 值。）

(b) `move` 用 `min(max(·, 0), GRID-1)` 把坐标夹在网格内，**撞墙就原地不动**。智能体 2 可以对着墙走来"等待"：比如在 `(4,0)` 时选 `left` 或 `down` 都留在原地，到达 `(4,4)` 后选 `down` 或 `right` 也留在原地。实测独立 Q 的 greedy 轨迹中，智能体 2 在第 1、2、3、5 步分别选了 `left`、`left`、`down`、`down`——全部是撞墙、留在原地，恰好"浪费"掉 8 - 4 = 4 步，之后与智能体 1 同时在第 8 步到达目标。这说明这个任务**并非完全不需要协调**——先到者必须学会等待，只是"等待"的代价恰好容易学。

### Q10 — 参考答案

(a) 只有 `Q[s]` 或 `Q[s_next]` 被访问时才会创建表项。终止状态 `((4,4),(4,4))` 只会作为 `done=True` 时的 `s_next` 出现，而代码在 `done` 分支里直接用 `r` 做目标、`break`，不会访问 `Q[s_next]`；它也永远不会作为当前状态 `s` 出现。所以 25×25=625 个联合状态中只有 624 个被创建（实测值，说明其余状态在训练中都被访问到了）。

(b) 独立 Q：两张表各 `624 × 4 = 2496` 项，合计 4992；联合 Q：`624 × 16 = 9984` 项。

(c) n 个智能体时联合状态数是 `25ⁿ`：
- 独立 Q：n 张表，每张 `25ⁿ × 4` 项，合计 `n·4·25ⁿ`；
- 联合 Q：一张表 `25ⁿ × 4ⁿ = 100ⁿ` 项。

两者的**状态维度**都随 n 指数增长（因为本代码的独立 Q 也以**联合状态**为键，讲义："Each agent runs its own Q-table keyed on joint state"），而联合 Q 的**动作维度**还额外多了 `4ⁿ` 的指数因子。真正可扩展的方法要同时用函数逼近（处理状态）和分解的动作头（讲义 Pitfalls："factored action spaces (one policy output head per agent)"）。

### Q11 — 参考答案

```python
def decentralized_actions(Q, s):
    # 每个智能体只决定自己的动作：假设队友会配合到"最好"的那个动作
    best1 = max(ACTIONS, key=lambda a1: max(Q[s][(a1, a2)] for a2 in ACTIONS))
    best2 = max(ACTIONS, key=lambda a2: max(Q[s][(a1, a2)] for a1 in ACTIONS))
    return best1, best2
```

在本节训练好的联合 Q 上实测，用这个函数执行 greedy 策略同样 8 步到达，回报 3.0。

**并列最优带来的问题**：假设 `Q(s, (up, left)) = Q(s, (left, up)) = 最大值`，而 `(up, up)` 和 `(left, left)` 很差。智能体 1 边缘化后发现 `up` 和 `left` 都能达到最大值，智能体 2 也一样；如果两者按各自的 tie-break 规则分别选了 `up`（期待 `(up, left)`）和 `up`（期待 `(left, up)`），组合起来就是 `(up, up)`——**每个人都"以为"对方会配合，结果协调失败**。这就是**均衡选择（equilibrium selection）/ 协调失败**问题。注意：只让两个智能体用相同的 tie-break 顺序并不够——上例中两者都按 `ACTIONS` 顺序（`up` 在 `left` 前）取第一个最大值，恰好都选 `up`，仍然得到 `(up, up)`。可靠的做法是：两者对**联合动作**做同一个确定性的 argmax（如 `max(joint_actions, key=...)`），再各自取出自己的分量（前提是都能看到同一个全局状态和同一张 Q 表）；或者使用通信、角色约定，或 QMIX 这类保证"个体 argmax = 联合 argmax"的结构。

### Q12 — 参考答案

```python
def step(state, action_pair):
    a1_pos, a2_pos = state
    new1 = move(a1_pos, action_pair[0])
    new2 = move(a2_pos, action_pair[1])
    # 两者必须在同一回合"踏上"目标：上一步都不在目标上，这一步都在目标上
    done = new1 == GOAL and new2 == GOAL and a1_pos != GOAL and a2_pos != GOAL
    reward = 10.0 if done else -1.0
    return (new1, new2), reward, done
```

实测（3000 回合，两个种子）：独立 Q 和联合 Q 的 greedy 评估都仍然达到 3.0。原因是：这里每个智能体的 Q 表以**联合状态**为键、看得到队友的位置；转移是确定性的；ε 只有 0.15，队友的行为基本可预测。最优解本来就是"同时在第 8 步到达"，只需让智能体 2 在目标**外**等待，难度和原任务差不多。

IQL 更容易失败的设置：
- **部分可观测**：每个智能体只看到自己的位置，无法根据队友的进度决定是否等待；
- **需要罕见联合动作才能拿到奖励**：例如两者必须在同一步执行某个特定组合，单个智能体的探索几乎永远碰不到；
- **随机性大 / 探索率高**：队友的随机动作让同一 `(s, a_i)` 的回报方差很大，Q 值被拉低，出现"相对过度泛化"；
- **队友策略变化快**：非平稳性导致 Q 值反复追逐。

这也印证了讲义的判断："fine for loosely-coupled tasks, bad for tightly-coupled ones"——关键在于"耦合有多紧、信息有多少"，而不是任务听上去像不像"协调任务"。

### Q13 — 参考回答要点

- **定义**：在 Markov Game 中，智能体 i 看到的转移 `P(s'|s, a_i) = Σ_{a_{-i}} π_{-i}(a_{-i}|s)·P(s'|s, a_i, a_{-i})` 依赖其他智能体的策略 `π_{-i}`；而 `π_{-i}` 在训练中不断变化，所以从 i 的视角看环境是非平稳的。
- **为什么破坏收敛**：Q-learning 的收敛性证明假设固定的 MDP（转移和奖励分布不变）。目标在变，Q 值就在"追逐移动的靶子"，可能振荡、循环，永不收敛（讲义："agents chase each other in loops"）。
- **缓解手段**：
  1. CTDE：critic 条件在联合动作上，对 critic 来说环境重新变得平稳；
  2. 慢学习率、轮流冻结（freeze-one-at-a-time）；
  3. 经验回放按新旧加权或重标注；
  4. 对手建模（预测其他智能体的策略）；
  5. 自博弈 / 联盟中用历史快照作对手，让对手变化可控。
- **加分点**：区分"非平稳"和"部分可观测"——前者来自其他智能体在学习，后者来自信息缺失，两者常同时出现。

### Q14 — 参考回答要点

| 方法 | 集中式部分 | 解决的问题 | 局限 |
|---|---|---|---|
| MADDPG（Lowe 2017） | 每个智能体一个集中式 critic `Q_i(s, a_1…a_n)` | 连续动作、混合合作/竞争下的非平稳 | 基于 DDPG，调参敏感；critic 输入随 n 增长 |
| COMA（Foerster 2017） | 一个集中式 critic + 反事实基线 | 共享奖励下的信用分配 | 需要对每个智能体枚举其动作，动作多时开销大 |
| MAPPO（Yu 2022） | 集中式价值函数 `V(s)` | 合作任务的稳定策略优化；讲义称其在 2026 年合作 MARL 中占主导 | 需要设计全局状态输入；on-policy 样本效率一般 |
| QMIX（Rashid 2018） | 混合网络 `Q_tot = f(Q_1…Q_n)`，单调 | 值分解 + 分散 argmax | 单调约束限制表达能力（见 Q15） |

加分点：提到 Yu et al. 论文标题 "The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games"，以及讲义 Key Terms 所说 IPPO "often underrated"——先跑 IPPO 作为强基线。

### Q15 — 参考回答要点

- **好处**：单调性保证 `argmax Q_tot` 可以分解成各智能体独立的 argmax（IGM 性质），训练时用 `Q_tot` 的 TD 误差学习，执行时每个智能体只需看自己的 `Q_i`，无需联合动作搜索，计算量线性于 n。
- **限制**：只能表示"任何一个智能体的 `Q_i` 变大都不会让团队变差"的价值函数。当某个智能体的最优动作**取决于**其他智能体选什么时（非单调交互），单调混合无法精确表示。
- **例子**：两人协作搬运，只有两人都选"抬"才得 +10，一人抬一人不抬得 -10（砸到脚），两人都不抬得 0。对智能体 1 来说，"抬"好不好完全取决于队友，单调分解难以同时表示 `(抬,抬)` 最优和"单人抬"很差，往往收敛到保守的 `(不抬, 不抬)`。这类博弈（如 climbing game、penalty game）是值分解方法的经典反例。
- **加分点**：知道后续工作（如更宽松的 IGM 分解方法）在尝试放宽单调约束；实际工程中 MAPPO 往往是更稳妥的选择。

### Q16 — 参考回答要点

- **问题刻画**：合作型（全局目标：总等待时间、总里程）为主，带部分可观测、智能体数量可变。
- **方案**：CTDE 的 MAPPO / 参数共享的 PPO + 注意力。讲义 Use It："Autonomous-vehicle fleets | CTDE MAPPO / PPO with attention | Partial obs; variable team sizes."
  - **执行**：每辆车的策略只用本地观测（周边车辆、订单、路况），**所有车共享参数**，用 agent ID 或角色特征区分；
  - **训练**：集中式 critic 看全局状态（全城订单分布、车辆分布），用注意力或池化处理可变数量的车辆；
  - **信用分配**：全局奖励 + 个体奖励塑形（接单、送达），或用反事实基线衡量单车贡献；
  - **可扩展性**：车辆数很大时考虑平均场 RL（讲义提到 `n → ∞` 时的 mean-field RL）。
- **评估**：固定对手/固定流量场景的回放评估、仿真中的 A/B 对比；skill 文件强调"Flag any MARL pipeline without a fixed-opponent eval"。
- **风险**：协作作弊（讲义："Agents find coordinated exploits the designer did not anticipate"），需要行为约束与安全规则。

### Q17 — 参考回答要点

- **原因**：
  1. **只和最近的自己对打**，学到的是"克制上一版本"的策略，陷入策略循环（讲义 Pitfalls："Pure self-play can get stuck in a dominance cycle"）；
  2. **评估口径有偏**：对自己的胜率不代表对多样化对手的强度（skill 文件："cherry-picked self-play numbers are common"）；
  3. 缺少探索，从未见过玩家的"套路"。
- **改进训练**：维护历史快照对手池并按胜率采样（如优先选择打不过的对手）；引入 exploiter 智能体专门寻找主智能体的弱点（AlphaStar 的联盟思路）；加入人类对局数据做模仿预训练（讲义 Use It："League play + imitation pretraining"）；加大熵正则。
- **改进评估**：固定的基准对手集合（脚本 AI、历史版本、人类回放）、Elo/TrueSkill 评分、专门的"套路"测试集。
- **加分点**：讨论零和 vs 一般和——纯自博弈在对称零和游戏中最有效；一般和或存在循环的游戏应使用联盟。

### Q18 — 参考回答要点

- **相同点**：都面临非平稳（其他 agent 的行为在变）、信用分配（团队结果由谁负责）、通信与角色分工、协作作弊等问题。讲义："Today's LLM-based multi-agent systems essentially communicate in natural language."
- **不同点**：
  - 动作空间是自然语言/工具调用，不是离散小动作集；
  - 大多数 LLM 多智能体系统**不在线训练**，而是靠提示与角色设计；需要优化时，奖励通常来自整段任务结果（代码是否通过测试、辩论是否得出正确答案）；
  - 通信是开放的自然语言，而非学习得到的向量消息。
- **"轨迹级而非 token 级"**：讲义："The RL shows up as preference optimization on *trajectory-level* outputs, not token-level." 对一个多 agent 协作过程，奖励/偏好针对整条交互轨迹（多轮对话、多次工具调用的最终结果）给出，而不是对每个 token 打分；优化的是"规划层"的决策（讲义 Use It："RL loop at the agent-planning layer"）。这与 RLHF 只对完整回答打分的思想一脉相承，只是粒度更粗。
- **加分点**：指出轨迹级奖励让信用分配更难，需要过程奖励、分 agent 的评估或反事实分析；联系阶段 16 的多智能体系统设计。

---

## 六、关联知识点

### 前置知识
- [阶段 09 · 04 时序差分——Q-Learning 与 SARSA](../../04-q-learning-sarsa/docs/zh.md)：本节代码就是两个（或一个联合的）表格 Q-learning。
- [阶段 09 · 06 Policy Gradient — REINFORCE](../../06-policy-gradients-reinforce/docs/zh.md)：COMA、MAPPO 的策略梯度基础。
- [阶段 09 · 07 Actor-Critic — A2C 和 A3C](../../07-actor-critic-a2c-a3c/docs/zh.md)：集中式 critic 就是把 actor-critic 的 critic 输入换成全局信息。
- [阶段 09 · 08 近端策略优化（PPO）](../../08-ppo/docs/zh.md)：IPPO / MAPPO 的单智能体底座。
- [阶段 01 · 22 随机过程](../../../01-math-foundations/22-stochastic-processes/docs/zh.md)：马尔可夫性与平稳性的数学含义。

### 本节被哪些后续内容用到
- [阶段 09 · 12 游戏强化学习](../../12-rl-for-games/docs/zh.md)：AlphaZero 自博弈、AlphaStar 联盟训练的展开。
- [阶段 16 · 01 为什么需要多智能体](../../../16-multi-agent-and-swarms/01-why-multi-agent/docs/zh.md)：LLM 多智能体系统的动机。
- [阶段 16 · 18 心智理论与协调](../../../16-multi-agent-and-swarms/18-theory-of-mind-coordination/docs/zh.md)：对手/队友建模。
- [阶段 16 · 19 群体优化 PSO / ACO](../../../16-multi-agent-and-swarms/19-swarm-optimization-pso-aco/docs/zh.md)：另一类"多智能体"优化思路。
- [阶段 16 · 20 MARL：MADDPG / QMIX / MAPPO](../../../16-multi-agent-and-swarms/20-marl-maddpg-qmix-mappo/docs/zh.md)：本节 CTDE 方法的深入实现。
- [阶段 16 · 16 谈判与议价](../../../16-multi-agent-and-swarms/16-negotiation-bargaining/docs/zh.md)：一般和博弈在 LLM agent 中的体现。

### 延伸关键词
`Markov game / stochastic game` · `Nash equilibrium` · `equilibrium selection` · `relative overgeneralization` · `IGM (Individual-Global-Max)` · `VDN` · `mean-field RL` · `PSRO` · `fictitious play` · `parameter sharing` · `Dec-POMDP`
