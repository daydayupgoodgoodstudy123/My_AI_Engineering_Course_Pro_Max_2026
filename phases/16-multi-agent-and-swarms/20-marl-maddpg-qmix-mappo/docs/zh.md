<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="marl--maddpg-qmix-mappo"></a>

# 多智能体强化学习（MARL）：MADDPG、QMIX、MAPPO

> 多种-agent 协调,该协调仍然为 LLM-agent 系统在2026年。 **MADDPG** (Lowe等人,2017年NeurIPS,arXiv:1706.02275)介绍了集中培训、分散执行(CTDE): critic 全部见识 agents培训期间的状态和行动;在测试时仅限当地人员 actors 运行,为合作、竞争和混合环境工作。 **QMIX** (Rashid等人,ICML 2018,arXiv:1803.11485)是使用单声波混合网络进行数值分解;每-agent Q 组合成Q `argmax` 清洁分配——在StarCraft 多个Agent 挑战(SMAC)。 **MAPPO** (Yu等人,NeurIPS 2022,arXiv:2103.01955)为 PPO 集中式 value function; “令人惊讶地有效”在粒子世界、SMAC、谷歌研究足球、Hanabi 和微调。 agent 团队必须分散行动。 **2026年合作-MARL基准**。 这个课从一个小网格世界玩具中 建立起来, 在触摸到肌肉记忆之前, 将三个想法放在了这里 LLM-agent training.

**类型:** 学习
**语言:** Python (小调,小调 NumPy- 免费执行)
**先修要求:** 第09阶段(Reinforcement Learning阶段16 -09(帕拉莱尔) Swarm Networks)
**时间:** ~90分钟

<a id="problem"></a>

## 问题

LLM-agent 系统日益培训政策促进agent 协调: 何时推迟, 何时采取行动, 哪个对等点会叫。 告诉你如何训练这种政策的文献是 Multi-Agent Reinforcement Learning 其日期早于 LLM 并且有一套小的占优势的算法

阅读无模式的 MARL 纸张 vocabulary 集中培训,分权执行、价值分解和集中 critics 而不是杂语,

- 独立 RL( 每张 agent 单独学习) agent角度,不好
- 集中式RL(1个) agent 执行限制。
- 中东欧和中欧司是两个方面中最好的:培训掌握全球信息,部署地方政策。

<a id="concept"></a>

## 概念

<a id="three-environments-the-papers-use"></a>

### 纸张使用的三种环境

- **粒子世界(多agent 微粒( emple env) 。** 简单的 2D 物理, 具有合作/竞争性的任务。 MADDPG 的原试验台 。
- **星际控制多功能Agent 挑战(SMAC)。** 合作微观管理,部分观察。QMIX的测试台。分辨动作,连续状态。
- **谷歌研究足球, 花边,MPE。** MAPOPO 基线。

不同的信封有不同的动作/观察类型。 算法相应选择 。

<a id="maddpg-2017--the-ctde-pattern"></a>

### MADDPG(2017年)-CTDE模式

每个 agent `i` 拥有 actor `mu_i(o_i)` 每一个都决定了自己的观察结果 agent 也有一个 critic `Q_i(x, a_1, ..., a_n)` 培训期间看到所有观察和所有行动。 actor 由 policy gradient 反对《公约》 critic的 evaluation.

```
actor update:    grad_theta_i J = E[grad_theta mu_i(o_i) * grad_a_i Q_i(x, a_1..n) at a_i=mu_i(o_i)]
critic update:   TD on Q_i(x, a_1..n) given next-state joint estimate
```

为什么CTDE:在训练时,我们知道每个人的行动;我们用它来减少每一类行动的差异。 critic。在部署时间,每个 agent 只能看见 `o_i` 和电话 `mu_i(o_i)`.

失败模式 : critics 与 N 生长 agents (输入包含所有动作) 不缩放过~ 10 agents 没有任何近似值。

<a id="qmix-2018--value-decomposition"></a>

### QMIX(2018年)-价值分解

仅合作。全球奖励是单体功能的总和,每 -agent Q-values:

```
Q_tot(tau, a) = f(Q_1(tau_1, a_1), ..., Q_n(tau_n, a_n)),   df/dQ_i >= 0
```

单音保证 `argmax_a Q_tot` 可由每个 agent choosing `argmax_{a_i} Q_i` 独立。 **确切的分权执行属性** 训练时混合网络会生成 `Q_tot` 来源于 :agent Qs.

QMIX为什么在SMAC中获胜:StarCraft合作微型管理是同质的 agents当地人对它有顾虑,全球奖励——完全适合价值分解。

失败模式: 单音限制是限制性的; 有些任务有非单调解压缩的奖励结构( 1) agent 扩展(QTRAN,QPLEX)放松。

<a id="mappo-2022--the-overlooked-default"></a>

### MAPPO(2022)——被忽视的默认

Multi-Agent PPO: PPO 集中式 value function. 每个 agent 有自己的政策;所有 agents 份额(或每份)agent) value functions 2022年,根据MADDPG、QMIX, 将MAPAPO基准及其在五个基准上的扩展,发现:

- MAPPO 匹配或节拍 off-policy 粒子世界的MARL方法,SMAC,谷歌研究足球,Hanabi,MPE。
- Minimal hyperparameter 需要调音。
- 稳定的训练;可复制到各种种子。

社区被低估 on-policy 2026年,MAPO是合作MARL的默认基准;任何新方法都必须比它强。

<a id="why-llm-agent-engineers-should-care"></a>

### Why LLM-agent 工程师应该关心

三种直接用途:

1. **路由器训练** 元数据agent 选择哪个子集agent 处理任务。这是一个与 N 分散的子集L 问题agents 还有一个中央路由器 MAPOP符合
2. **角色出现** 基因组化agent 模拟、培训 agents QMIX型价值分解促使建筑的互补性。
3. **Multi-agent 工具使用。** 当 agents 分享工具和竞争预算,通过CTDE培训这些工具,产生尊重资源限制的可部署的地方政策。

实际警告:2026年,大部分生产 LLM-agent systems prompt MAL在具备以下数据时出现:(a) 许多互动数据,(b) 一个明确的奖励信号,以及(c) 投资培训基础设施的意愿。

<a id="ctde-as-a-design-pattern-beyond-rl"></a>

### CTDE 设计模式,超出 RL

即使在没有培训的情况下,CTDE也是一种有用的建筑模式:

- During *design*假设整个团队的可见度
- 在 *runtime*执行分散执行: agent 仅见 `o_i`.

模式迫使你保持每 -agent state 并思考部分 observability 前面有很多生产多功能agent 中央发展教育中心纪律防止了这种情况。

<a id="the-non-stationarity-problem"></a>

### 不稳定问题

当乘以 agents 每一个同时学习 agent环境(包括他人的政策)是非固定的。agent RL 的证明被打破。

- MADDPG: 全局 critic 观察所有动作, 所以它的数值估计是静止的。
- QMIX: 数值分解将学习移动到一个共同-Q空间, 在那里优化性定义明确。
- MAPOPO: 集中式 value function 抑制了与他人政策变化的差异。

在 LLM-agent 系统,非静止状态 表现为"我的 agent 上个月工作过,现在又工作过 agent 上流的改变,我的错误行为。"训练MARL使用CTDE是原则性的解决办法; prompt- 修补速度更快,但耐用性更低

<a id="what-this-lesson-does-not-cover"></a>

### 课程没有包含的内容

培训实际网络是一个阶段的09。 这个课程构建了脚本政策版本, 以显示 CTDE、 价值分解和集中值模式 gradient 更新。 目标是在您取出完整的 MARL 库之前先将图案内部化( PyMARL, MARLIB, RLLIB 多个)agent).

```figure
sw-ctde
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行三次模式演示, 全部在小2 -agent 合作网格世界:

- 环境:2 agents 4x4格斗,一个奖赏 奖励=1 agent 到达贝子;任务结束。
- `IndependentAgents` — 每个 agent 将他人视为环境。基准。
- `MADDPGStyle` 集中管理 critic 计算一个联合值; actor 政策更新。 脚本改进了 。
- `QMIXStyle` 使用单调调制解析器进行价值分解。
- `MAPPOStyle` 集中管理 value function;根据共同基准更新政策。

四个项目都运行相同的片段,报告平均步入目标。 CTDE 变量会比独立基线的路径更短。

Run:

```
python3 code/main.py
```

预期产出:独立 agents 平均采取~ 6 步; CTDE 变量会向 ~ 3.5 步( 4x4 格子的最佳值是 3) 。 尽管有脚本化策略, 模式差异还是显示出来 。

<a id="use-it"></a>

## 实际应用

`outputs/skill-marl-picker.md` 是一种选择一个多功能MARL算法的技能agent 任务:合作对竞争, 单一对异性, 动作空间类型, 比例, 奖励信号 。

<a id="ship-it"></a>

## 交付成果

生产中的最低允许浓度很少。

- **从MAPOPO开始** 2022年的文件将这一点确定为基线;首先复制它可以节省几周追逐更狂热的方法。
- **记录每 agent观察与行动流** 调试 MARL 时没有按-agent traces 简直是无药可救
- **单独的训练代码 与执行代码。** CTDE 是一个学科; 让执行路径只看到 `o_i`.
- **奖励 形成警告。** MARS对奖励设计非常敏感。 agents 学着利用它,进行对抗性测试
- **用于 LLM agents**,考虑 prompt只有当互动数据+奖励信号+基础设施都存在时,才对最低年度报酬水平培训进行投资。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`衡量独立与MAPOP模式之间在步骤到目标方面的差距 agents。6x6电网上的缺口是扩大还是缩小?
2. 实施竞争性变式: agents,一个贝子,只有第一个得到奖励。哪个模式可以处理干净的竞争?MADDPG历史上。
3. 读MADDPG (arXiv: 1706.02275) 第3节 执行准确 critic 以您自己的语言以伪代码符号方式更新规则 。
4. 阅读 MAPO (arXiv: 2103. 01955) 。 为什么作者会争论集中值+ 。 PPO beats off-policy 最低收入水平在基准线上?
5. 将 CTDE 作为一种设计模式应用到假设中 LLM-agent 系统(例如研究) agent + Gammer + 代码器)在设计时无法提供的联合信息是什么?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| MARL | "Multi-Agent RL" | Reinforcement learning 用于多个 -agent systems. |
| CTDE | “集中培训、分散执行” | 利用全球信息进行培训;根据地方政策进行部署。 |
| MADDPG | "Multi-Agent DDPG" | 计算机化电子设备,每agent critic 查看所有观测+动作。 |
| QMIX | 价值分解 | 单调混合 /agent 问题 合作 |
| MAPPO | "Multi-Agent PPO" | PPO 集中管理 value function. 2026 默认基线。 |
| 价值分解 | "单质质数之微" | 以单调函数表示的 Q 组合agent Qs. |
| Non-stationarity | 移动目标 | 每个 agent变换了别人的认知 核心的MARL问题 |
| On-policy / off-policy | "从当前/重播中学习" | PPO 是 on-policy (MAPPO); DDPG 和 Q-learning 是 off-policy. |
| SMAC | "星际飞弹多功能...Agent Challenge" | 合作微观管理基准;QMIX的本土地盘。 |

<a id="further-reading"></a>

## 进一步阅读

- [Lowe等人——多-Agent Actor-Critic 合作竞争环境委员会](https://arxiv.org/abs/1706.02275) MADDPG;2017年NeurIPS
- [Rashid等人-QMIX:单体体 Value Function 深多功能的因数Agent Reinforcement Learning](https://arxiv.org/abs/1803.11485) - QMIX;2018年ICML
- [Yu等人—— 全球化的惊人效果 PPO 多边合作Agent Games](https://arxiv.org/abs/2103.01955) - 地中海行动计划;NeurIPS 2022
- [BAIR博客文章“MAPO”](https://bair.berkeley.edu/blog/2021/07/14/mappo/) - MAPOP结果的可读框架
- [SMAC 仓库](https://github.com/oxwhirl/smac) - 星际飞弹多功能Agent Challenge
