<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="planning-with-htn-and-evolutionary-search"></a>

# 结合 HTN 与演化搜索的 Planning

> Symbolic planning 处理计划可以正确无误的个案。 进化代码搜索处理机检功能的个案。 聊天HTN (2025) 和阿尔法· 沃尔沃(2025) 显示每次与 an 匹配时打开的锁 LLM.

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 -02(再培训、规划和执行)
**时间：** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释等级任务网络:任务、方法、操作员、先决条件、效果。
- 描述 ChatHTN 的混合循环- 符号搜索 LLM 后退分解
- 解释阿尔法沃夫的进化循环 为什么它只与方案评估员合作
- 执行玩具HTN计划器 加上玩具进化搜索

<a id="the-problem"></a>

## 问题

REWO(Lesson 02),规划和执行,以及 ReAct 覆盖最多 agent planning有两个案子他们不擅长:

1. **计划有可证实的正确性。** 时间安排、飞行路径、合规工作流程——计划必须能够通过施工实现。 LLM 计划有时会幻觉 一步是不可接受的。
2. **优化机能检查功能。** 矩阵乘法,排期超常,编译员通过——目标不是“一个正确的计划”,而是“最佳计划”。

HTN planning 和阿尔法演变解决了两个不同的问题。 LLMs 用作放大器,而不是替换。

<a id="the-concept"></a>

## 概念

<a id="hierarchical-task-networks"></a>

### 等级任务网络

危险物品处理网是:

- **Tasks** 化合物(待拆解)和原始(可直接执行)。
- **方法** 将复合任务分解为次级任务的方法,并附有先决条件。
- **Operators** - 具有先决条件和效果的原始行动。
- **State** - 一套事实

Planning:如果有目标任务和初始状态,则发现原始操作者分解后,其先决条件按顺序得到满足。

高龄者 LLMs 并且仍然是正确计划的参考

<a id="chathtn-gopalakrishnan-et-al-2025"></a>

### 查塔特恩(Gopalakrishnan等人,2025年)

热气流热解解槽(arXiv:2505.11814) LLM queries:

1. 尝试用现有方法分解当前复合任务 。
2. 如果没有方法,请询问 LLM"你会如何分解 `task` 状态 `s`?"
3. 翻译 LLM 对候选人子任务的反应 。
4. 对照操作器图案验证; 拒绝无效分解 。
5. Recurse.

报纸的核心主张:每个计划都是可以论证的,因为 LLM 仅作为候选分解输入建议, 而不是直接计划编辑。 符号层拥有正确性; LLM 扩展方法库。

在线方法学习( 公开审查) `gwYEDY9j2x`2025年后续)增加一个学习者, LLM- 由回归产生的分解——切割 LLM 查询频率高达75%。

<a id="alphaevolve-novikov-et-al-2025"></a>

### AlphaEvollve(Novikov等人,2025年)

阿尔法电流(arXiv:2506.131,DeepMind,2025年6月)是另一头野兽:由一股力量操纵的进化代码搜索 Gemini 2.0 Flash/共鸣。

Loop:

1. 以种子程序+方案评估员(返回健身分)开始。
2. 组合 LLMs 提议突变
3. 通过评估员运行突变。
4. 保持最好的;再次变异。

已公布的赢家 :

- 与Strassen相比,在56年内对4x4复合矩阵乘法(48个天平乘法)进行了第一次改进。
- 0.7%通过Borg排程计算恢复谷歌。
- 32% FlashAttention 加速前沿工作量。

硬性限制: 健身功能必须是机器检查的。 用于解答的进化搜索无法合并 。

<a id="when-to-use-which"></a>

### 何时使用哪个

| 问题类 | 使用 | 为什么 |
|---------------|-----|-----|
| 安排有严苛限制 | HTN + 聊天时TN | 可证实的音质 |
| 编译优化 | AlphaEvolve | 可机器检查的健身 |
| 多步骤任务执行 | ReAct /再行动 | LLM 循环中,没有正式保证 |
| 测试后代码改进 | AlphaEvolve | 测试是评价员 |
| 政策性自动化 | HTN | 编码政策的先决条件 |

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **无人操作的HTN。** 没有任何先决条件/效果,健康能力声称崩溃。LLM 表示分解"需要模式拒绝无效的移动 。
- **阿尔法演化没有真正的评价员** 问 LLM 如果代码更好的话, 评估员必须确定并且快速。
- **Over-engineering.** Most agent 任务也不需要 ReAct 或再生行动先。

```figure
htn-tree-expand
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行两个玩具:

- 具有操作员、方法、先决条件、效果和 `LLMFallback` 无法匹配复合任务时启动。 "LLM"是一个脚本解构器,所以计划者运行关闭。
- 用于计算程序的斯坦利布进化搜索: 最小输出的成长表达式 `|f(x) - target|` 测试组的,评估员是决定性的

运行：

```
python3 code/main.py
```

该 trace 显示 HTN 计划解密复合任务( 包含一个中位计划) LLM 和进化循环在目标表达式上趋同。

<a id="use-it"></a>

## 实际应用

- **HTN 规划人员** — `pyhop`, `SHOP3`,或建立自己的区域,用于执行特定领域的政策。
- **ChatHTN** - 研究代码;模式(符号+ LLM 任何HTN计划者都可干净地使用端口。
- **AlphaEvolve** 深底纸;模式(组合+评价器)可以复制,正在出现开放源码和类似的开放源码叉。
- **Agent frameworks** 还没有一流的HTN或阿尔法动力飞船 subagent 或者是背景工人 或一个工作坊

<a id="ship-it"></a>

## 交付成果

`outputs/skill-hybrid-planner.md` 生成一个混合式的平板脚架( HTN 或进化式) LLM 明确界定了作用。

<a id="exercises"></a>

## 练习

1. 使用回溯跟踪扩展 HTN 计划程序: 当操作员的后置条件在运行时失效时, 滚回去尝试下一个方法 。
2. 添加a LLM- 方法缓存到 ChatHTN: 当 LLM 分解任务 `T` 状态模式 `P`,然后保存结果。在下次调用时,先重新检查方法库。
3. 将进化搜索评估器转换为真正的测试套件。 演化一种通过20个测试案例的功能; 报告代际趋同情况 。
4. 读取 AlphaEvolve 的评价说明。 为您所关心的域设计一个评价员( NAME OF TRANSLATORS)SQL 查询优化、测试适量最小化、部署 YAML).
5. 组合: 使用 HTN 将复合任务分解为子任务, 然后对每个子任务原始操作员进行进化搜索。 它会闪亮到哪里, 它会超编到哪里?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| HTN | 统治计划家 | 与操作员分解任务、先决条件、效果 |
| 方法 | "强制失效规则" | 将复合任务破解为子任务的方法 |
| Operator | "初始行动" | 附有先决条件和效果的具体步骤 |
| ChatHTN | "LLM + HTN' + 键盘 | 符号规划器询问 LLM 当方法不匹配时 |
| AlphaEvolve | "进化代码搜索" | Ensemble LLMs 变换代码; 选择确定性评价器 |
| 适配功能 | "Evaluator" | 确定性、机器可检查的比产出得分 |
| 在线方法学习 | "Cached LLM decomposition" | 存储+一般化 LLM 计划削减查询费用 |

<a id="further-reading"></a>

## 进一步阅读

- [Gopalakrishnan等人,ChatHTN(阿尔西夫:2505.11814)](https://arxiv.org/abs/2505.11814) - 象征性+ LLM 混合规划员
- [Novikov等人,AlphaEvolle(阿尔西夫:2506.13131)](https://arxiv.org/abs/2506.13131) 进化代码搜索 LLM mutations
- [Anthropic建设有效 Agents](https://www.anthropic.com/research/building-effective-agents) - 什么时候能达到一个规划者对简单的循环
