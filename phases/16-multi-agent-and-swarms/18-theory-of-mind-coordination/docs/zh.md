<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="theory-of-mind-and-emergent-coordination"></a>

# 心智理论与涌现协调

> Li等人(arXiv:2310.10701)表明, LLM agents 合作文字游戏展览 **脑力理论** ——关于另一个问题的理由 agent 相信大约三分之一 agent信仰 - 但失败于长视距 planning 与背景管理和 hallucination. Riedl(arXiv:25 1005174)测量到人口之间的较高级协同效应,发现 **仅** 托姆号...prompt 条件产生与身份挂钩的区别和目标导向的互补性;能力较低 LLMs 显示的只是虚假的出现。也就是说,协调的出现就是 prompt- 有条件的,依赖模型,不是免费的。这个课程只用最低限度的 ToM 意识 agent,与托姆合作,不推动托姆合作,并针对雷德尔2025年议定书采取协调三角洲措施。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段16 -07(思想和辩论学会),阶段16 -17(创举) Agents)
**时间:** ~75分钟

<a id="problem"></a>

## 问题

Multi-agent 协调往往看起来神奇: agents 区分劳动力,互相预测,避免冗余。 prompt engineering - 有人告诉了 agents 改为“坐标”。 prompt,取消协调。

瑞德尔2025年的发现更加严格:在受控制的条件下,只有在以下情况下才出现协调: agents 被激励到理性 **other agents头脑** (托姆),没有托姆 prompt,即使强大的模型也显示协调模式,这种模式在统计控制中无法幸存。agent coordination" features 中 prompt- 依赖性强又弱小

课程将托姆视为一种特殊的能力(基于信仰), agent衡量真正的协调情况 prompt 穿衣服看起来像。

<a id="concept"></a>

## 概念

<a id="what-tom-means"></a>

### 托姆意味着什么

发展心理学:一个3岁的孩子认为任何人的内心世界都与他们相匹配。 一个5岁的孩子理解别人有不同的信仰。一个7岁的人对信仰的看法(“她认为球在杯子里” ) 。 这是第0、第1和第2级托姆。

用于 LLM agents, ToM 命令地图:

- **Zeroth-order:** 没有别人的模范 agent 仅凭自己的意见行事。
- **First-order:** 该 agent 彼此都有个模范 agent信仰,爱丽丝相信X
- **Second-order:** 该 agent 模型的循环信仰。 "爱丽丝相信鲍勃相信X。"

Li等人(2023年)发现,TOM在第一和第二级中出现。 LLM agents 却在漫长的视野和不可靠的交流中堕落

<a id="the-sally-anne-test-in-brief"></a>

### 简而言之,萨莉安的测试

1985年的假信仰测试:莎莉把大理石放进A篮子,离开。安妮把它移到B篮子。萨莉回来时会在哪里看?一个头等兵托姆说(萨利的信仰与现实不同)A篮子。一个没有B篮子的孩子。

GPT-4-era LLMs 直接通过 Sally-Anne 式的测试。 当描述很长, 场景会改变好几次, 或者问题会间接表达, 就会失败 。 这就是2026年的TOM 生产状态 。 LLMs.

<a id="riedls-coordination-measurement"></a>

### 里德尔的协调度量

Riedl(arXiv:25 1005174) 制造了人口规模测试: N agents,合作目标,变量 prompt 措施:

1. **与身份有关的区别。** Do agents 逐步形成稳定的角色区别?
2. **目标导向的互补性。** Do agents行动互为补充(不同的子任务)而不是重复?
3. **更高层次的协同效应。** 统计衡量该组是否取得了无法达到的子集。

结果:仅在托盘下 prompt 条件是所有三个计量都产生基线以上的信号。没有调控信号,则中容量模型的准机率会几乎上升。大型模型显示有些协调,但没有明确的调控信号,但效果小于明显加速。

<a id="the-coordination-illusion"></a>

### 协调的幻觉

缺乏统计控制,演示中的“紧急协调”往往反映:

- Prompt engineering 以你们所协调的盟誓,system prompts 说“一起工作”
- 观察偏差(我们看到我们预期的模式)。
- 成功运行的后热选择 。

市场“紧急协调”的生产系统,如无可衡量的信号,应作为销售处理。

<a id="a-minimal-tom-aware-agent"></a>

### 最小的 ToM 意识 agent

Structure:

```
agent state:
  own_beliefs:    {facts the agent believes}
  other_models:   {other_agent_id -> {beliefs_the_agent_attributes_to_them}}
  actions_last_N: [history of others' actions]

observation update:
  - update own_beliefs from direct observation
  - update other_models[agent_id] from their action + prior beliefs

action selection:
  - enumerate candidate actions
  - for each, predict what each other agent will do next given their modeled beliefs
  - pick action that maximizes joint outcome under those predictions
```

该 `other_models` 属性是 ToM 状态。第一顺序 ToM 只保留一个级别。第二顺序添加 `other_models[i][other_models_of_j]` -我怎么想的 -我以为 agent 我觉得 agent j 相信这一点。

<a id="why-long-horizon-hurts"></a>

### 为什么长长的圆形会痛

Li等人的文件:上下文限制原因 agents 忘记信仰属于谁 Hallucination 以妄言相报,agent 模型。两个都产生"我认为X"错误 随着时间的推移。

该文件和2024-2026年后续报告中的缓解措施:

- **明确 ToM 状态 prompt.** 结构化格式 : `{agent_id: belief_list}`强制检索以维护身份-信仰。
- **更短的推理链。** 每转转减少对托姆的更新 hallucination.
- **外部托盘商店** 维持模型 LLM 上下文; 向每一转仅输入相关部分。

<a id="where-tom-fails-in-production"></a>

### ToM 生产失败的地方

- **反向设置 。** Agents 拥有良好的托姆更容易操作(你可以模仿他们如何塑造你,然后开发)。
- **异质团队。** 当模型不同时,对一个对手有效的托姆模型并不普遍化。
- **地面真相任务。** 托姆是信仰问题;如果正确性取决于事实,托姆可能是分散注意力的问题。

<a id="the-coordination-you-can-actually-measure"></a>

### 协调您可以实际测量

三个实际信号 一个团队的协调是真实的,而不是 prompt-dressed:

1. **随时间推移而相互补充。** 在一个多转弯的任务,做 agents行动包括分任务脱节?
2. **Anticipation.** Does agent A在转弯T+1时的行动取决于对B在T+2时的行动的预测,而预测结果是正确的吗?
3. **Correction.** 当A错误地读错B的信念在转弯T, 是否以转弯T+2来正确?

这些可以测量在记录中的多功能-agent 它们是“协调”说明的实质性版本。

```figure
sw-theory-of-mind
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `ToMAgent` 追踪自己的信仰和彼此agent 信仰模型。
- 合作任务:三项 agents 一定要收集三个 tokens 三个盒子;每个盒子可以有一个 token. Agents 无法沟通;他们推断出对方的行为意图。
- 两种配置: `zeroth_order` (无 ToM) 和 `first_order` (具有一级信仰模式的托姆)
- 测量200多例随机试验:完成率、重复率(两个) agents 以同一方框为目标,平均值转向完成。

Run:

```
python3 code/main.py
```

预期产出:零顺序 agents 重复工作, 速度~ 35%, 在 10 次转动中完成~ 60% 的测试。 第一顺序 ToM agents 重复值为~5%,完成~95%。三角洲是可测量的协调效果。

<a id="use-it"></a>

## 实际应用

`outputs/skill-tom-auditor.md` 是一种审计多功能的技能agent 系统声称"紧急协调" prompt 调味、统计重要性与控制,以及衡量的互补性。

<a id="ship-it"></a>

## 交付成果

协调索偿清单:

- **控制状态** 系统版本, 没有协调 prompt两者都测量。
- **统计测试。** 系统和控制之间的差别在 `p < 0.05` 对你的标准?
- **补充性衡量标准。** 行动与时间脱节,而不仅仅是最终成功。
- **失败记录 。** 当 agents 调子不对, 调子状态是什么样子?
- **模型能力披露。** 如果小模型的效应消失,请说

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。确认一阶托盘将重复率减少~ 7x。当您将比例缩到 5 时,差距是否继续存在 ? agents 和5个箱子?
2. 实施二级托运(TOM)agent 一个B对C的看法模型。它是否比第一阶有所改进?关于什么任务?
3. 注射 a **hallucination** 进入 ToM 状态: 随机翻转每转一个信念。 这会降低第一阶性能多少 ?
4. 读李等人(arXiv:2310.10701),重现“长方位退化”的发现:随着转动从10升至30,你的第一阶TOM性能如何变化?
5. 读 Riedl 2025 (arXiv: 25 1005174)。 在模拟日志上执行更高级的协同统计。 没有 ToM 的效果是否存在 ? prompt condition?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 思想理论 | "理解别人的思想" | 模拟另一个的能力 agent信仰,按顺序( 0, 1, 2+) 排序。 |
| 萨莉安测试 | 虚伪的信仰测试 | 1985年 发展心理学; LLMs 传递普通版本, 失败复杂版本 。 |
| 第一阶调 | "A相信X" (A believe X) | 模仿对方对事实的信仰 |
| 第二阶托姆 | "A相信B相信X" | 递归性模型更深。 |
| 与身份有关的区别 | "稳定的角色随时间推移" | 瑞德尔的衡量标准:角色继续存在,不是随机的。 |
| 目标导向的互补性 | “不联合行动” | Agents 目标为不同的子任务,而不是同一个。 |
| 更高层次的协同效应 | 组超过任何子集 | 瑞德尔的统计测量 真正协调。 |
| 协调幻觉 | "看起来协调" | Prompt- 装得像协调的外表,没有可衡量的信号 |

<a id="further-reading"></a>

## 进一步阅读

- [Li等人——多语言思想理论Agent 通过大语言模式进行协作](https://arxiv.org/abs/2310.10701) 合作游戏中的新兴托姆;长方位失败模式
- [里德尔-多机构协调新机构Agent 语言模式](https://arxiv.org/abs/2510.05174) 人口规模测量;托姆催化是载荷条件
- [黑猩猩有思想理论吗?](https://www.cambridge.org/core/journals/behavioral-and-brain-sciences/article/does-the-chimpanzee-have-a-theory-of-mind/1E96B02CD9850E69AF20F81FA7EB3595) 1978年托姆概念的起源
- [男爵科恩、莱斯利、弗里斯——自闭症儿童是否有思想理论?](https://doi.org/10.1016/0010-0277(85)90022-8) - 萨利-安恩论文(1985年)
