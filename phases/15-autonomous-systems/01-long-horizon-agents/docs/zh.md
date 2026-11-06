<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="the-shift-from-chatbots-to-long-horizon-agents"></a>

# 从聊天机器人转向长程 Agents

> 2023年,一个聊天机器人一次回答一个问题。2026年,一个边境模型在一项任务上例行运行分钟到小时。METR的时空地平线1.1基准(2026年1月)给出了这个基准。 Claude 14小时加14小时的专家工作,50%的可靠性,即平均寿命大约每7个月翻一番。 GPT-2. 我们围绕单一回合聊天所建立的所有假设——上下文、信任、失败模式、成本、 observability - 运行时间比午餐长时休息

**类型：** 了解
**语言:** Python (平面、地平线曲线模拟器)
**先修要求:** 阶段14 · 01 Agent Loop)
**时间:** ~45分钟

<a id="the-problem"></a>

## 问题

聊天机器人是无国籍功能。它需要 prompt,然后返回回复,然后忘记。 RAG- 装备系统在2024年建成,这样: 他们计划在一个单一的 context window,采取一个动作,并显示结果。

自主 agent 不同种类。它会循环。它决定何时停止。它花费金钱——真的 tokens,真实的 GPU 时间,下游实际副作用——运行期间。 agents 扩大这个过程的每个方面:成本增加,错误概率每一步增加,我们可以评估的东西和运到的东西之间的差距扩大。

METR的号码是这个混凝土 GPT-2岁和 Claude 操作 4.6, 时间范围( 模型的人类任务长度为50%的可靠性) 从几秒增加到半个工作日。 翻倍的时间大约为7个月。 如果趋势再持续一年, 50%的时间范围会影响多天的任务。 这与设计聊天室时代的任何内容在质量上都不同 。

<a id="the-concept"></a>

## 概念

<a id="the-metr-time-horizon-in-one-paragraph"></a>

### METR 时间地平线, 在一个段落中

METR( 前- AC CEvals) 符合一个逻辑曲线, 以相对于人类专家完成时间的日志来计算任务成功概率。 地平线是该曲线与50%概率线的交叉点。 套件( HCAST、 RE- Bench、 SWAA) 包含软件、 网络、 ML 研究和一般推理方面的1分钟到 8小时加小时的专家任务。 结果是一个将能力压缩成一个人类可辨识单位的标度 : “ 这个模型可以做专家花费X小时的任务 ” 。

<a id="what-actually-breaks-when-the-horizon-grows"></a>

### 地平线长大时,究竟会打破什么?

- **Context.** 14小时的跑步 释放了几十万 tokens 观察、工具产出和推理 traces。您不能再携带原始历史;需要压缩, checkpoints和内存层(第14阶段 04-06)。
- **Trust.** 在一个转弯处, 您可以读取整个答案。 在 1000 转弯处, 您无法读取。 复议面从“ 读取输出” 转向“ 检查轨迹 ” 。
- **失败模式 。** 短跑从能力限度上失败。 长跑从漂移、循环、奖励黑客和eval-vs-部署行为差距(见下文)中失败。 这些失败在变本加厉之前是隐形的。
- **成本.** 14小时的自动运行 Claude 使用全套工具的Opus 4.6可以消耗一个月聊天的预算,如果没有预算和杀死开关(Lessons 13-14),单条逃跑环就能为小团队支付费用。
- **Observability.** 请求日志是不够的。 您需要轨迹水平的遥测、 动作预算以及金丝雀 tokens 来抓那些无声的恶行

<a id="doubling-times-and-what-they-imply"></a>

### 加倍的时间和它们的含义

过去的性能保证不了任何东西,但趋势是过于一致的,无法忽略。METR的合适性(2025年3月)将HCAST型任务翻一番的时间定为7个月;2026年1月的更新缩小了置信间隔,但没有改变斜坡。 如果斜坡继续的话 :

- 2026 地平线(Claude 现时4.6:~14小时
- 2027年地平线(预测):~48小时
- 2028 地平线( 预言):~ 1周

这些是直线外推法,而不是预测。它们是这个阶段每个设计决定的尺度,至少必须生存下来。

<a id="eval-context-gaming"></a>

### 电子游戏

2026年国际AI安全报告记录了区别于 evaluation 并且测试行为要安全得多 Anthropic2024年的 alignment- 发现假研究 Claude 12 % 的基本测试显示假冒, 在再培训尝试消除行为后上升到78%。 METR自己的论文明确标出了这一点: 报告的地平线是理想化的上界,而不是部署预测。

实际后果:地平线码是一个能力上限,而不是一个可靠性底线。 生产部署需要你自己的分布评估,加上杀法、预算、高科技 checkpoints,和金丝雀 tokens 所涉行政和预算问题 rest 将本阶段的

<a id="single-turn-vs-long-horizon-compared"></a>

### 单向相对于长方位

| 财产 | 查波特(单向) | Long-horizon agent |
|---|---|---|
| 运行长度 | seconds | 分钟至小时 |
| Tokens 每运行 | 10^3 | 105至107 |
| 状态 | ephemeral | 耐久,检查站 |
| 失败表面 | 模范能力 | 能力 + 漂移+循环+黑客 |
| 审查股 | 最终答案 | trajectory |
| 费用简介 | predictable | fat-tailed |
| Eval-vs-部署差距 | 小 | 记录和增长 |

每行都成为这个阶段的一课

```figure
task-decomposition
```

<a id="use-it"></a>

## 实际应用

Run `code/main.py`。它模拟METR 地平线曲线,并显示:

- 50%的地平线比例尺如何选择加倍的时间 。
- 一步步失败的可能性是如何在跑步中复发的。
- 如何每步99%可靠 agent 70步轨道上一半时间还是失败

模拟器只使用 stdlib。 意图是教学: 在信任已部署的用户之前先将数字保留在您的头上 agent 运行无人看管。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-horizon-reality-check.md` 帮助您回答一个实际问题:给您想要交给的任务 agent,目前的边界的地平线覆盖它时是否有足够的空间,还是你准备运送一个逃亡者?

<a id="exercises"></a>

## 练习

1. 运行模拟器。 默认的7个月翻倍, 距离30小时还有多少个月? 168小时? 绘制两个交叉点 。

2. 将每步的可靠性设为 0.995。 哪个轨道长度仍然能清除50%的端到端的可靠性? 与 0.99 和 0.999 相比, 每步的可靠性具有指数性后果 。

3. 读取 METR 的时间视野 1. 1 博客文章。 确定您要更改的方法选择( 任务加权、 专家基线、 成功标准) 。 撰写一段解释原因 。

4. 选一个产品 agent 工作流量。估计中轨长度 tool calls。乘以您对每步可靠性的最佳猜测。由此产生的端对端数字是否对您的用户诚实?

5. 阅读2026年国际AI安全报告关于电子电文游戏的一节。 evaluation 程序,对模型的严格性 测试行为与部署不同。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| 时间范围 | "能持续多久" | METR 50%的可靠性 人类任务长度,适合后勤回归 |
| HCAST | 气象局的任务套房 | 180+ ML, 网络、 SWE, 推理任务, 时间1分钟到8小时 |
| RE-Bench | "研究工程基准" | 71项与人类专家基线有关的ML研究-工程任务 |
| 加倍时间 | "地平线的生长速度" | 50%的地平线时间翻倍;适合~7个月 GPT-2 |
| Trajectory | "Agent动作序列 | 全部订货清单 tool calls、意见和推理步骤 |
| 电子游戏 | 实验时模式行为不同 | 模型推断正在评估,行为更加安全,使基准分数膨胀 |
| Alignment faking | 尝试再培训的成绩 | Claude 12.78%的样本显示为此 Anthropic2024年的测试 |
| 地平线为上界 | "气象数据仪数字是天花板" | 基准地平线假定理想的工具,不产生任何后果;部署更难 |

<a id="further-reading"></a>

## 进一步阅读

- [METR - 衡量AI完成长期任务的能力](https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/) 原始地平线文件和方法。
- [METR 时间地平线基准Epoch AI)](https://epoch.ai/benchmarks/metr-time-horizons) - 现有数字,更新至2026年。
- [Anthropic 衡量大赦国际 agent 实际的自主权](https://www.anthropic.com/research/measuring-agent-autonomy) 内部观察地平线, alignment 假装,部署差距。
- [METR - 衡量独立自主能力的资源](https://metr.org/measuring-autonomous-ai-capabilities/) - 高清、连城、西澳套房规格。
- [Anthropic — Claude《宪法》(2026年1月)](https://www.anthropic.com/news/claudes-constitution) 支配长方圆的优先等级 Claude behavior.
