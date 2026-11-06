# 测验 · 从仿真到现实的迁移（Sim-to-Real Transfer）

> **阶段 09 · 强化学习 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Reality gap | 仿真与真实之间系统性的分布差异：摩擦、镜头畸变、电机延迟/回差/饱和、风尘光照等；是机器人 RL 落地的核心问题 |
| 2 | 为什么要在仿真里训练 | 无限重置、可复现、可并行、不损坏硬件；真机试错又慢又危险又贵 |
| 3 | Domain Randomization（DR） | 训练时随机化所有可能与真机不同的参数（质量、摩擦、PD 增益、传感器噪声、相机、光照…），真机落在训练包络内就能工作；随机化过度会得到"过于保守"的策略 |
| 4 | System Identification（SI） | 用真机数据测量/拟合仿真参数再训练；目标精确，但残余的未建模效应（如电机死区）对策略不可见 |
| 5 | Domain Adaptation | 仿真训练后用少量真实数据适配：Real2Sim2Real（学习残差动力学修正仿真）或观测适配（把真实观测映射成"像仿真的"观测） |
| 6 | 特权学习 / Teacher-Student | 教师在仿真中使用特权信息（真实摩擦、地形高度等）；学生只看真实传感器，靠观测**历史**推断这些隐藏量 |
| 7 | 大规模并行仿真 | Isaac Lab、MuJoCo MJX、Brax 在单 GPU 上跑数千个环境；每个环境不同的随机参数让 DR 几乎"免费" |
| 8 | ADR | Automatic Domain Randomization：随策略变强自动放宽随机化范围的课程学习 |
| 9 | 2026 典型配方 | 并行仿真 + DR → 特权教师 → 只用本体感知的学生 → 可选观测适配 → 零样本部署，失败则用带安全约束的 PPO 做少量真机微调 |
| 10 | 安全与验证 | 部署前做 sim-to-sim（更难的仿真变体）测试；非学习的底层安全护盾（速率/力矩/关节限位）；回滚方案 |

### 核心技能（能动手做到）

- [ ] 运行 `main.py`，读懂"固定 slip 策略 vs DR 策略"在不同真实 slip 下的回报表，并能**批判性地**判断这个例子是否真的证明了 DR 的价值
- [ ] 推导 slip 机制下单步移动的概率分布，并用 `8/(1-p)` 粗略估计期望步数，与实测回报对照
- [ ] 设计一个"最优策略依赖于 slip"的环境（如悬崖格），复现"DR 在支撑集内更稳健、在 slip=0 时更保守"的经典取舍
- [ ] 写出 ADR 课程的伪代码：何时评估、何时放宽范围、如何定义达标阈值
- [ ] 为一个具体机器人任务列出 reality gap 清单、DR 参数与范围、SI 测量步骤、教师/学生信息划分、安全护盾
- [ ] 解释 DR 与监督学习中的数据增强、偏差-方差权衡之间的对应关系

---

## 二、基础自测（选择题）

**Q1.** 关于 Domain Randomization，下列说法**错误**的是：

- A. 训练时随机化质量、摩擦、传感器噪声等参数，让策略见过一个"仿真族"
- B. 不需要真实数据
- C. 随机化范围越宽越好，因为策略见过的情况越多就越稳健
- D. 真实系统落在训练包络内时，策略通常能直接工作

**Q2.** System Identification 的主要弱点是：

- A. 完全不需要访问真机
- B. 只能用于视觉任务
- C. 残余的未建模效应（如电机死区）对策略不可见，部署时仍可能失败
- D. 会让策略过于保守

**Q3.** Teacher-Student（特权学习）中，学生策略的输入通常是：

- A. 与教师相同的特权信息（地形真值、摩擦系数）
- B. 只有真实机器人可获得的观测（如关节编码器、IMU）及其**历史**，从中推断隐藏的物理量
- C. 仿真器的完整内部状态
- D. 人类示范视频

**Q4.** 讲义提到的 "Privileged info leakage" 陷阱指的是：

- A. 教师模型被泄露给竞争对手
- B. 教师依赖了学生从观测历史中**无法推断**的信息做决策，导致学生无论如何也学不会
- C. 学生使用了太多传感器
- D. 仿真参数被写进日志

**Q5.** ADR（Automatic Domain Randomization）的核心思想是：

- A. 用 GAN 自动生成随机纹理
- B. 一开始用窄范围，随着策略表现达标逐步放宽随机化范围的课程
- C. 自动识别真机参数
- D. 只在真机上随机化

**Q6.** 大规模 GPU 并行仿真让 DR "几乎免费"，原因是：

- A. GPU 能自动测量真机参数
- B. 数千个并行环境可以各自使用不同的随机参数，一次 rollout 天然覆盖一个参数分布
- C. 并行仿真不需要物理引擎
- D. PPO 不再需要 advantage

**Q7.** 部署到真机前，讲义建议先做 sim-to-sim 测试，原因是：

- A. 真机比仿真便宜
- B. 如果策略连更难的、未见过的仿真变体都扛不住，它也扛不住真实世界
- C. sim-to-sim 可以替代安全护盾
- D. 这是 PPO 算法的要求

**Q8.** 关于底层安全护盾（safety shield），正确的是：

- A. 有了 DR 就不需要
- B. 应当是非学习的控制器，对速率、力矩、关节范围做硬限制，防止"仿真里能用、真机上也看似能用"的策略损坏硬件
- C. 应当由策略网络自己学习
- D. 只在仿真中启用

---

## 三、动手 / 代码题

**Q9.**（读输出 + 批判）运行本节代码得到：

```text
  slip      fixed-slip policy     DR-trained policy
  0.00      -8.00                 -8.00                 (in-support for DR)
  0.10      -8.78                 -8.78                 (in-support for DR)
  0.20      -10.05                -9.78                 (in-support for DR)
  0.30      -11.35                -11.04                (in-support for DR)
  0.50      -16.72                -15.78                (OOD for DR)
  0.70      -28.73                -28.73                (OOD for DR)

takeaway: DR-trained policy degrades gracefully; fixed-slip policy is brittle out-of-distribution.
```

讲义 Step 4 预期"固定 slip=0 训练的策略在真实 slip > 0 时会灾难性下降"。(a) 这组数据支持这个结论吗？(b) 从环境设计的角度解释为什么两个策略表现几乎一样。(c) 为什么 slip=0.0、0.1、0.7 这几行两列数值**完全相同**？

**Q10.**（推导 + 估算）`step` 中的 slip 机制是：

```python
if rng.random() < slip:
    perp = ("left", "right") if action in ("up", "down") else ("up", "down")
    action = rng.choice(perp)
```

(a) 在网格内部、策略选择 `"right"`、`slip = p` 时，智能体实际向右/上/下移动的概率各是多少？(b) 假设策略总是选择"向右或向下"（朝目标前进），忽略墙的影响，一步让到目标的曼哈顿距离减 1 的概率和加 1 的概率各是多少？(c) 由此粗略估计从 (0,0) 到 (4,4) 的期望步数，并与 Q9 表格中的回报对比。

**Q11.**（改环境，让 DR 真正起作用）把环境改成"悬崖行走"：起点 `(4,0)`，终点 `(4,4)`，`(4,1)`、`(4,2)`、`(4,3)` 是悬崖，掉进去奖励 -20 并结束回合，其余每步 -1。(a) 写出新的 `step` 函数；(b) 预测固定 slip=0 训练的策略和 DR（slip ~ U[0, 0.3]）训练的策略分别会学到什么路线；(c) 预测在真实 slip = 0、0.1~0.3、0.5 时两者谁更好，并与讲义中 DR 的"Upside / Downside"对应起来。

---

## 四、面试高频题

**Q12.**（基础必考）什么是 sim-to-real 的 reality gap？请列出至少 5 个来源，并说明 DR、SI、Domain Adaptation 三类方法各自如何应对、各自的优缺点。

**Q13.**（原理深挖）解释特权学习（teacher-student distillation）的流程。为什么学生需要观测**历史**而不是单帧观测？教师可以使用哪些特权信息、哪些不应该使用？

**Q14.**（原理深挖）从机器学习的角度看，DR 和监督学习中的数据增强、偏差-方差权衡有什么联系？随机化"过度"和"不足"分别对应什么现象？

**Q15.**（场景设计）你要把一个在 Isaac Lab 里训练的四足机器人行走策略部署到真机上，目标是能在草地、碎石、楼梯上行走。请设计完整的 sim-to-real 流程，包括 DR 参数清单、教师/学生划分、部署前验证和安全措施。

**Q16.**（工程实践）策略在仿真中成功率 99%，上真机后 30% 的情况下会抖动后摔倒。你会如何定位问题？列出排查步骤和可能的修复手段。

**Q17.**（追问型）面试官追问："既然大规模并行仿真 + DR 这么有效，为什么还需要 System Identification 和真机微调？DR 范围怎么定才算合理？"

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义 DR 的 Downside："over-randomized training produces a 'universal' but overly cautious policy. Too much noise ≈ too much regularization." Pitfalls 也说："Train on slip ∈ [0, 0.9] and your policy is so risk-averse it never tries the optimal path. Match the expected real-world distribution." skill 文件还建议把"比实测变化范围宽 3 倍以上"的 DR 范围标记为可能过度随机化。A、B、D 都是讲义中 DR 的正确描述。

### Q2 — 答案：C

讲义 SI 的 Downside："residual model error is invisible to the policy; small un-identified effects (e.g., motor deadband) still break deployment." A 错，SI 恰恰需要访问真机；D 是 DR 过度的问题。

### Q3 — 答案：B

讲义："Distill a student that only sees real-sensor observations. The student learns to infer privileged features from history." 讲义的 2026 配方中学生只用本体感知（腿部关节编码器）。

### Q4 — 答案：B

讲义 Pitfalls："A teacher that uses global state for actions, not just observations, can produce a student that cannot catch up. Ensure the teacher's policy is realizable by the student given observation history." 例如教师利用了"前方 5 米处有坑"这种学生传感器根本感知不到的信息，学生就无法模仿。

### Q5 — 答案：B

讲义 Key Terms："Curriculum that widens DR ranges as the policy improves." Pitfalls 也建议用它应对"随机化不足"。A 描述的是视觉 DR 的一种手段。

### Q6 — 答案：B

讲义："DR becomes almost free when each of those 4,096 envs has different randomized parameters." 每次 rollout 就是在参数分布上的一次蒙特卡洛采样，不需要额外的训练轮次。

### Q7 — 答案：B

讲义 Pitfalls："If your policy is not robust to a harder sim variant, it will not be robust to the real world either. Always test on a held-out sim variant before deploying." skill 文件把"zero-shot sim-variant test"列为部署的硬性前提之一。

### Q8 — 答案：B

讲义 Pitfalls："Add rate limits, torque limits, joint limits in a non-learned controller." 护盾必须是可验证、确定性的非学习组件，不能依赖策略自己学会安全。

### Q9 — 参考答案

(a) **不支持。** 两列在所有 slip 下差距都很小（最多约 0.9），slip=0.7 时完全一样。固定 slip 策略并没有"灾难性下降"，DR 策略的优势也在噪声范围内——用种子 1、2、3 各训练一次，slip=0.7 时 DR 策略分别是 -28.73、-28.54、-29.68，而固定策略都是 -28.73，DR 甚至可能更差。所以代码最后打印的 takeaway（"fixed-slip policy is brittle"）是一个**没有被这组数据证明**的结论。

(b) 在这个空旷的网格里，无论 slip 多大，**最优策略都是"只向右或向下走"**：slip 只会随机把你推向垂直方向，没有任何策略能规避它，也没有"更安全的路线"可选。实测两张 Q 表的贪心策略，所有格子的动作都是 `down` 或 `right`——两者都是最优策略，只是在部分格子上选了不同的最短路径。回报随 slip 下降是**物理本身**造成的（见 Q10），不是策略脆弱。DR 只有在"最优行为依赖于未知参数"的环境中才能发挥作用（见 Q11）。

(c) `evaluate` 对两个策略都使用同一个 `random.Random(42)`，而 `step` 每一步调用随机数的次数与动作无关（每步一次 `rng.random()`，发生 slip 时再一次 `rng.choice`），所以两个策略面对的是**完全相同的 slip 事件序列**。slip=0 时两者都走 8 步；在另外几行，两条不同的最短路径（如"先下后右"与"先右后下"）在相同的随机序列下恰好得到相同的总步数。这种"完全相同"是共享随机流的产物，说明评估缺乏独立性，不能当作两者等价的证据——比较时应该用多个评估种子、多个训练种子取均值和置信区间。

### Q10 — 参考答案

(a) 不发生 slip（概率 `1-p`）时向右；发生 slip（概率 `p`）时在 `("up", "down")` 中等概率选一个。所以：右 `1-p`，上 `p/2`，下 `p/2`。

(b) 向右或向下的策略中，"实际向右"或"实际向下"都让距离减 1；只有"实际向上/向左"（向后）让距离加 1。以选择 `right` 为例：前进概率 `(1-p) + p/2 = 1 - p/2`，后退概率 `p/2`（贴墙时后退会变成原地不动，所以真实的后退概率更低）。

(c) 每步的期望净前进 `= (1 - p/2) - p/2 = 1 - p`。曼哈顿距离为 8，期望步数约 `8 / (1 - p)`：

| slip p | 估算步数 `8/(1-p)` | 实测回报（固定 / DR） |
|---|---|---|
| 0.0 | 8.0 | -8.00 / -8.00 |
| 0.1 | 8.9 | -8.78 / -8.78 |
| 0.3 | 11.4 | -11.35 / -11.04 |
| 0.5 | 16.0 | -16.72 / -15.78 |
| 0.7 | 26.7 | -28.73 / -28.73 |

每步奖励 -1，回报 ≈ -步数，估算与实测非常接近（墙会减少后退、而后退后的绕行会增加步数，两者部分抵消）。这说明：**回报下降几乎完全由环境本身的随机性决定**，与策略是否经过 DR 训练关系不大——进一步印证 Q9 的结论。

### Q11 — 参考答案

(a)

```python
START = (GRID - 1, 0)
TERMINAL = (GRID - 1, GRID - 1)
CLIFF = {(GRID - 1, c) for c in range(1, GRID - 1)}

def step(state, action, slip, rng):
    if rng.random() < slip:
        perp = ("left", "right") if action in ("up", "down") else ("up", "down")
        action = rng.choice(perp)
    dr, dc = DELTAS[action]
    r, c = state
    nxt = (min(max(r + dr, 0), GRID - 1), min(max(c + dc, 0), GRID - 1))
    if nxt in CLIFF:
        return nxt, -20.0, True          # 掉崖：大惩罚并结束
    return nxt, -1.0, nxt == TERMINAL
```

训练与评估函数中把起点 `(0, 0)` 改为 `START`；为了让 `train_fixed` 和 `train_dr` 在 `done` 时用 `r` 作目标，原有逻辑无需改动。

(b) 固定 slip=0：没有任何意外，最短路线是"上 1 → 沿悬崖边向右 4 → 下 1"，共 6 步、回报 -6——紧贴悬崖走。DR：训练时见过"向右走时被推下去"，沿悬崖边那一行（第 3 行）的 Q 值会被掉崖的 -20 拉低，于是学会**离悬崖远一点**（多走一两行），回报约 -8。

(c) 实测（3 个训练种子、每个 slip 评估 500 回合）：

| 真实 slip | 固定 slip 策略 | DR 策略 |
|---|---|---|
| 0.0 | -6.00 | -8.00 |
| 0.1 | 约 -10.3 | 约 -10.0 |
| 0.2 | 约 -13.4 | 约 -12.5 |
| 0.3 | 约 -16.4 ~ -16.9 | 约 -15.2 |
| 0.5（OOD） | 约 -21.7 ~ -22.1 | 约 -22.7 ~ -23.2 |

对应讲义：
- slip=0 时 DR 策略多走 2 步——这就是 DR 的 Downside："overly cautious policy"。
- slip 在训练支撑集 [0, 0.3] 内时 DR 稳定更好——这就是 DR 的 Upside。
- slip=0.5 超出支撑集后 DR 也没有优势，甚至略差——DR 不保证对训练范围之外的泛化，所以讲义强调"Match the expected real-world distribution"，skill 文件要求用真实测量来论证 DR 范围。

这个例子比原代码更好地说明了 DR 的价值和代价：**只有当最优行为依赖于未知参数时，DR 才有意义。**

### Q12 — 参考回答要点

- **定义**：仿真分布与真实分布之间的系统性差异（讲义："systematic difference between sim distribution and real distribution"）。
- **来源**：接触/摩擦模型不准；质量与惯量误差；电机延迟、回差、饱和、死区；传感器噪声与偏置（IMU 漂移）；相机畸变、光照、纹理；风、灰尘、地面材质；控制频率与通信延迟。
- **三类方法**：

| 方法 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| DR | 训练时随机化参数，覆盖真机 | 不需要真实数据，一套配方适配多机器人 | 过度随机化 → 保守；随机化错了维度无效 |
| SI | 测量真机参数，让仿真贴近真实 | 训练目标精确、噪声低 | 需要真机；残余未建模误差不可见 |
| Domain Adaptation | 少量真实数据做适配：残差动力学（Real2Sim2Real）或观测映射 | 用很少真实数据直接缩小差距 | 需要真机数据采集；适配模型本身可能出错 |

- **加分点**：讲义总结的工作流——"fit the sim as best you can, randomize what you can't fit, train enormous policies, distill, deploy with a safety shield"，即三者组合使用而非三选一。

### Q13 — 参考回答要点

- **流程**：
  1. 仿真中训练**教师**，输入包含特权信息（讲义列举：真实摩擦、地形高度、IMU 漂移、地形图、机身速度真值），用 RL（如 PPO）训练，容易学好；
  2. 训练**学生**，输入只有真机可获得的观测（关节编码器、IMU 等本体感知），通过模仿教师动作（或匹配教师的潜变量）进行蒸馏；
  3. 部署学生。
- **为什么要历史**：摩擦、负载、地形等物理参数在单帧观测中不可见，但会体现在一段时间的"动作 → 响应"关系里（比如同样的力矩下关节速度变化慢，说明负载重或地面软）。学生用历史（RNN/TCN/Transformer）做隐式的在线系统辨识。
- **特权信息的边界**：可以使用"能从观测历史中推断出来"的量（地面摩擦、身体速度、负载）；不应依赖学生**永远无法推断**的信息（如远处被遮挡的地形细节），否则教师策略对学生不可实现（讲义 "Privileged info leakage"）。
- **加分点**：提到学生常用 DAgger 式在线蒸馏（在学生自己访问的状态上询问教师），避免分布偏移；提到讲义引用的 Miki et al. 2022（ANYmal）。

### Q14 — 参考回答要点

- **DR ≈ 数据增强**：图像分类中随机裁剪、颜色抖动让模型对这些变化不敏感；DR 对物理参数做同样的事，让策略对参数变化不敏感。两者都是用"训练分布的多样性"换"测试分布的鲁棒性"。
- **偏差-方差视角**（讲义前置：阶段 02 · 10）：
  - **随机化不足**：策略过拟合某一个仿真（低偏差于仿真、高方差于参数变化），一到真机就失败——讲义："Train on a thin slice and the policy can't generalize at all."
  - **随机化过度**：相当于正则太强，策略对所有情况都"平均地凑合"，变得保守、欠拟合真实任务——讲义："Too much noise ≈ too much regularization."
- **最优点**：让训练分布覆盖**预期的**真实分布（必要时用 SI 测出的范围再适当放宽），或用 ADR 自动找到合适的宽度。
- **加分点**：用 Q11 的悬崖例子说明"保守的代价"在无扰动时是 2 步、在有扰动时变成收益。

### Q15 — 参考回答要点

参考讲义 "The real-world 2026 recipe (quadruped walking example)"：

1. **Reality gap 清单**（skill 文件第 1 步）：接触与地面材质、电机延迟与饱和、IMU 噪声与漂移、负载变化、控制延迟。
2. **并行仿真 + DR**：在 Isaac Lab 中跑数千个环境，随机化重力方向扰动、摩擦系数、电机增益、负载质量、地形（草地用软接触、碎石用随机高度场、楼梯用程序化生成）、传感器噪声、动作延迟；范围用真机测量值论证，避免超过实测变化的 3 倍。
3. **SI**：测量电机响应曲线、关节摩擦、整机质量与质心，校准仿真的中心值。
4. **教师**：使用特权信息（地形高度图、机身速度真值、摩擦）用 PPO 训练。
5. **学生**：只用本体感知（关节编码器 + IMU）的历史，蒸馏教师策略。
6. **部署前验证**：在未参与训练的仿真变体（更难的地形、未见过的参数组合）上做零样本测试；在真机上先吊装测试、再低速测试。
7. **安全措施**：非学习的力矩/关节/速度限位、跌倒检测与急停、备用控制器、回滚方案（skill 文件："Refuse to deploy without (a) a zero-shot sim-variant test, (b) a safety shield, (c) a rollback plan"）。
8. **失败时**：用带安全约束的 PPO 做几分钟的真机微调（讲义配方第 5 步）。

### Q16 — 参考回答要点

- **定位**：
  1. 记录真机与仿真在**相同指令**下的轨迹，逐项比较：关节响应延迟、力矩饱和、IMU 数据；
  2. 检查控制频率与通信延迟是否与仿真一致（抖动往往来自延迟或增益过高）；
  3. 在仿真中**复现**：加入实测延迟/噪声/死区，看能否重现抖动（sim-to-sim）；
  4. 检查观测预处理（单位、坐标系、归一化、滤波）是否在真机上一致；
  5. 分析失败的 30% 是否集中在某类地面/姿态/电池电量。
- **修复**：
  - 把找到的差异加入 DR（如动作延迟随机化、电机增益随机化）——讲义 Pitfalls："Profile the real robot first"；
  - 对可测量的参数做 SI，修正仿真中心值；
  - 在奖励中加入动作平滑/能耗惩罚，降低高频抖动；
  - 低层加速率限制；
  - 必要时少量真机微调（安全约束下）。
- **常见误区**：盲目扩大所有参数的随机化范围——随机化错误的维度（讲义例子：随机化相机色调而真正的差距是电机延迟）没有帮助，还会让策略更保守。

### Q17 — 参考回答要点

- **为什么还需要 SI**：DR 的随机化范围需要一个"中心"和"宽度"，SI 提供中心值并缩小必要的宽度；范围越贴近真实，策略越不保守。SI 也能发现 DR 遗漏的维度。
- **为什么还需要真机微调**：总有仿真没建模的效应（讲义 SI 部分的电机死区例子），零样本失败时，少量真机数据（在安全约束下）是最直接的补救；Real2Sim2Real 用真实轨迹学习残差动力学，也能反过来改进仿真。
- **DR 范围怎么定**：
  1. 以真机测量的变化范围为基准（skill 文件："Justify each range against real measurements"）；
  2. 适度放宽覆盖测量误差，但超过实测 3 倍要警惕过度随机化（skill 文件的规则）；
  3. 用 ADR 自动放宽到策略能承受的程度；
  4. 用留出的仿真变体和真机小规模测试验证。
- **加分点**：讲义原话"fit the sim as best you can, randomize what you can't fit"——SI 和 DR 是互补关系，不是替代关系。

---

## 六、关联知识点

### 前置知识
- [阶段 09 · 08 近端策略优化（PPO）](../../08-ppo/docs/zh.md)：sim-to-real 中最常用的训练算法，配合大规模并行环境。
- [阶段 09 · 04 时序差分——Q-Learning 与 SARSA](../../04-q-learning-sarsa/docs/zh.md)：本节代码使用的表格 Q-learning。
- [阶段 02 · 10 偏差与方差](../../../02-ml-fundamentals/10-bias-variance/docs/zh.md)：讲义列出的前置；理解"随机化过度/不足"。
- [阶段 01 · 22 随机过程](../../../01-math-foundations/22-stochastic-processes/docs/zh.md)：随机转移与期望步数估计。

### 本节被哪些后续内容用到
- [阶段 09 · 12 游戏强化学习](../../12-rl-for-games/docs/zh.md)：MuZero 的学习模型、仿真/规划与真实环境之间的关系。
- [阶段 04 · 28 世界模型与视频扩散](../../../04-computer-vision/28-world-models-video-diffusion/docs/zh.md)：学习的世界模型作为新一代"仿真器"。
- [阶段 12 · 21 具身 VLA：OpenVLA / π0 / GR00T](../../../12-multimodal-ai/21-embodied-vlas-openvla-pi0-groot/docs/zh.md)：视觉-语言-动作模型在机器人上的部署，同样面临 reality gap。
- [阶段 15 · 14 Kill switch 与金丝雀](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)：与"安全护盾、回滚方案"相通的自主系统安全工程。

### 延伸关键词
`reality gap` · `dynamics randomization` · `ADR` · `Real2Sim2Real` · `residual dynamics` · `privileged learning` · `DAgger` · `Isaac Lab / MuJoCo MJX / Brax` · `safety shield` · `actuator network` · `sim-to-sim validation` · `robust MDP`
