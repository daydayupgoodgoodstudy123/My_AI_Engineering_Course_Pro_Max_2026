<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="swarm-optimization-for-llms-pso-aco"></a>

# 面向 LLMs 的 Swarm 优化（PSO、ACO）

> 生物激励优化正在产生 LLM comeback. **LMPSO** (arXiv:2504.09247)使用PSO,其中每个粒子的速度为 prompt 以及该 LLM 生成下一个候选人; 运行良好的结构序列输出( 数学表达式、 程序) 。 **模型 Swarms** (arXiv:2410.11163) 每种治疗 LLM 专家作为PSO粒子 模型weight 多种报告 **13.3%平均收益** 超过12个基线的9个数据集,仅200个实例。 **SwarmPrompt** (2025年国际农业研究训练中心) prompt optimization. **AMRO-S** (arXiv:2603.12933)是ACO启发的多-agent LLM 路线 **4.7x 加速**,可解释路径证据,质量加固的无同步更新,脱钩 inference 学习中学习的教益。 prompt parameter 空间和 ACO 连接 agent 路径,测量为什么这些古典算法适合 LLM 时代,当他们不。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段16 -09(帕拉莱尔) Swarm 网络,第16阶段 14(共识和BFT)
**时间:** ~75分钟

<a id="problem"></a>

## 问题

你有一个 prompt 任务评估上分数62%。 您想要改进它。 幼稚的举动是 gradient- 免费手动调整, 缩放得非常严重。 Reinforcement learning 需要奖励信号,足够 rollouts 来训练 prompts 无法真正实现 prompt 是一个离散的字符串, 不可更改 parameter.

典型的生物激励优化——持续搜索空间的PSO,选择路径的ACO——正是为这一制度设计的: gradient- 免费,以人口为基础,按人均价格计算 evaluation和他们一起对齐 LLMs 用于 gradient- 免费搜索一步,你得到一个惊人的实际 optimizer.

同样的模式适用于 agent *routing* 以多个 -agent 一种ACO式的Pelomon跟踪记录 agent 最擅长的是哪种任务类型, 让路由器利用路径, 并腐烂的pheomones 这样路线就可以重新发现。

<a id="concept"></a>

## 概念

<a id="pso-refresher-kennedy--eberhart-1995"></a>

### 公共支助处进修员(Kennedy & Eberhart 1995年)

Particle Swarm 优化: 连续搜索空间中的粒子群。 每个粒子都有位置 `x_i` 速度 `v_i`。每次重复 :

```
v_i <- w * v_i + c1 * r1 * (p_best_i - x_i) + c2 * r2 * (g_best - x_i)
x_i <- x_i + v_i
evaluate fitness(x_i)
update p_best_i if improved
update g_best if global best
```

Where `p_best` 粒子是自己最好的 `g_best` 是 swarm最好不过了 `w, c1, c2` 惯性+认知+社交 weights, `r1, r2` 随机系数。

<a id="pso-on-llm-outputs--lmpso"></a>

### 支持组织 LLM 产出——长期产出

arXiv:2504.09247 使PSO适应 LLM-generated structured outputs 每个粒子都是候选输出。 速度是 *prompt* 来描述如何将当前输出修改为个人/全球最佳。 LLM 从速度生成新输出 prompt。速度的“内酸”是 prompt 比如说"做小的递增变化"

下述情况中,这一办法效果良好:
- 产出结构化(可区分、可评价)。
- 适配性是自动的( 测试运行、 算术) evaluation).
- 人口数量很小(~10-30颗粒),总数如此之大 LLM 电话可以控制

当健身需要人审查时,它效果不好——每封土地的费用变得令人望而却步。

<a id="model-swarms"></a>

### 模型 Swarms

arXiv:2410.11163 将 PSO 从输出层移到 *模型* 每个"粒子"都是专家 LLM (parameters). 该 swarm 移动 parameters 向集体最好的通过 gradient据报,9个数据集的12个基线平均增加13.3%,每重复仅200例。

关键是 LLM 专家模型已经在附近 parameter 多重(调整 weights, LoRA 低维次空间的PSO是廉价和有效的。

<a id="aco-refresher-dorigo-1992"></a>

### ACO进修机(1992年,多里戈)

蚂蚁殖民地优化:蚂蚁绕过一个图形;每个路径都有pheomone 路径。 weight 使用 pheomone 强度。 完成任务 的 蚂蚁会按照 溶液质量 比例 保存 pheomone 。 Pheromone 会随着时间变坏 。

<a id="amro-s--aco-for-agent-routing"></a>

### AMRO-S - ACO 代表 agent routing

arXiv:2603.12933 使用ACO用于多-agent 路径。 每个任务类型都是“ 目的地 ” ; agent 荷洛蒙斯强化了生产出好产品的路线。

- **解释性路线证据** 荷洛蒙的力量是人类可以读取的信号
- **质量定级的不同步更新 。** 只有在质量检查通过后,才更新 Pheromones, 解开 inference 学习。
- **4.7x 加速** 数上agent 路线基准。

质量门很重要:没有它,快但错 agents 积聚的花粉, 系统锁定在坏路径。

<a id="when-to-use-pso--aco-for-llms"></a>

### 何时使用 PSO / ACO LLMs

**使用 PSO 时 :**
- 搜索空间是连续的, 或地图是连续的 parameters (prompt embeddings, LoRA weights,数字生成 parameters).
- 健身很便宜,而且自动
- 人口可能很少(10-30人)。

**使用 ACO 时 :**
- 你有一个路由或选择路径的问题。
- Decisions reinforce 随着时间的推移(同样的任务类型会回来)。
- 需要解释性的证据才能做出正确的决定

**使用时不使用 :**
- 健身需要人工检查(每次迭代费用太昂贵)。
- 搜索空间是离散和组合的,而PSO并不涵盖(而是使用遗传算法)。
- 实时决定需要严格的延缓(常务组织/奥地利石油公司相对于单行的超时制缓慢地趋同)。

<a id="why-bio-inspired-still-wins"></a>

### 为什么生物灵感仍然在赢得

Gradient- 基础方法需要不同的信号 LLM 输出和路径决定并非微不足道的不同。gradient 方法(加强学习路由器, DPO-style prompt 调音员)工作,但需要昂贵的培训。

支助办和ACO只需要一个 *evaluator* 函数。如果您能够分到候选输出或路径选择,您可以在空间上优化。这样,适用性所在的栏就更低了。

<a id="practical-limits"></a>

### 实际限制

- **人口预算。** N粒子 × T 迭代 × 每年成本。 LLM 电算值~0.02美元/调用,一个20粒的PSO,50次重覆费用~20美元。
- **勘探与开采。** 热敏酮衰减率和PSO惯性交换;过快衰减 忘了解决方案;太慢的固执于早期的局部奥皮马。
- **灾难的漂移。** 如果健身环境发生变化(新数据分布),两种算法可以相互趋同,然后出现差异。

```figure
swarm-stigmergy
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `LMPSO` - 超过数字的 PSO prompt parameters (temperature,顶部_k weights每个粒子的"LLM 生成"被模拟为脚本的健身功能。运行30次迭代的算法并显示 g_最佳趋同。
- `AMRO_S` ACO型路线。 agents,4个任务类型, pheomone 矩阵, 100个路由任务。_类型 +++ agent 显示轨迹形成。
- 比较: 随机路径与 ACO 路径对齐。 测量质量和延迟度 。

Run:

```
python3 code/main.py
```

预期产出:
- 妇女、青年和体育部:g_最佳的健身条件从随机到接近最佳的30倍以上。
- AMRO-S: 光素表稳定在右边 agent 每个任务类型; ACO 路径在质量上随机跳过~30-40%,并降低延迟度( 退缩 ) 。

<a id="use-it"></a>

## 实际应用

`outputs/skill-swarm-optimizer.md` 帮助选择 PSO、 ACO、 遗传算法, 以及 gradient-based optimizers 用于 LLM / agent 优化问题。

<a id="ship-it"></a>

## 交付成果

- **开始小点** 10 -20颗粒, 20 - 50 迭代。 只有趋同曲线显示明显增益时, 才会缩放 。
- **日志的pheomones 或 g_最好再重复一次 换个地方** Debugging swarm optimizers 没有线索是痛苦的。
- **质量门户更新 。** 特别是ACO路线:快速和错误 agents 一定不能累积异丙酮
- **重置衰变 distribution shift.** 当您的变价器分布发生变化时, 旧的pheomones 将变得枯燥; 暂时重置或加倍衰减率 。
- **加上每封电费** 排放成本- 每一销毁量。 PSO 成本为500美元/ 迭代和收益为0.5%, 无法发运 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`观察LMPSO的趋同,人口规模为5、10、20、50。
2. 执行“ 灾难性漂移” 实验: 在迭代30之后, 改变健身功能。 PSO 适应速度有多快? 重新设置是否 `p_best` help?
3. 添加一个质量门到 AMRO- S: 仅以 eval 得分 > 0. 7 运行时的 phelomone 存款。 这如何改变未加标记版本的趋同 ?
4. 读取 LMPSO (arXiv: 2504. 09247) 。 将纸上“ 速度作为 prompt"回到你的数位速度,模拟中丢失了什么,保存了什么?
5. 读读AMRO-S(arXiv:2603.12933)。inference 快速路径” , 并有非同步的 pheomone 更新。 这个系统在持续负荷下是如何改变 的 ?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| PSO | "Particle Swarm Optimization" | 1995年肯尼迪-埃伯哈特省,人口 gradient-free optimizer. |
| ACO | 蚁群最佳化 | 多里戈 1992 , 通过 Pelomon 路径优化路径/ 路程 。 |
| LMPSO | "PSO与 LLM generation" | 轴轴:2504.09247. 速度是 prompt; LLM 产生候选人。 |
| 模型 Swarms | "公关专家 weights" | arXiv:2410.11163. Gradient- 免费更新模型 parameter subspace. |
| AMRO-S | "ACO为 agent routing" | arXiv:2603.12933. 任务类型x的热敏质矩阵 agent. |
| p_最佳/克( 纯度)_best | "个人/全球最佳" | 单质和 swarm- 迄今找到的最好的解决方案 |
| Pheromone | "流传记忆" | 边缘的强势; 随时间变坏; 质量的沉积。 |
| 质量说明更新 | "只学好跑步" | 佩洛蒙的存款以质量检查为条件 |
| 灾难性的漂移 | "Distribution shift" | 适合性环境变化; 老 p_最好的和费洛蒙变得老套。 |

<a id="further-reading"></a>

## 进一步阅读

- [肯尼迪和埃伯哈特——粒子 Swarm Optimization](https://ieeexplore.ieee.org/document/488968) - 1995年的方案支助干事文件
- [Dorigo - 蚁群优化](https://www.aco-metaheuristic.org/about.html) - 1992年奥地利石油公司基金会
- [LMPSO - 语言模型粒子 Swarm Optimization](https://arxiv.org/abs/2504.09247) - 结构化支助支助办公室 LLM 输出
- [模型 Swarms — gradient-free LLM 专家优化](https://arxiv.org/abs/2410.11163) 支助支助处,模式weight subspace
- [AMRO-S - 蚂蚁多管所agent routing](https://arxiv.org/abs/2603.12933) 使用高品质门的光素驱动路径
