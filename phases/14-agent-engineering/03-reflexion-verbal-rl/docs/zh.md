<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="reflexion-verbal-reinforcement-learning"></a>

# Reflexion：语言反馈驱动的 Reinforcement Learning

> Gradient- 以《区域法》为基础的区域法庭需要数千次审判和1次 GPU 组合键以修正失败模式。 Reflexion (Shinn等人, NeurIPS 2023) 用自然语言进行: 每次试验失败后, agent 写一个反射,储存在记忆中, 并给下一次的记忆试验设置条件。 这是Letta睡眠时间计算背后的模式, Claude Code's CLAUDE学习, 和亲工作流的学习规则。

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop阶段14 02 (REWOO)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出反射( Reflexion) 的三个组成部分( A)Actor和记忆作用。
- 实施一个二进制反射循环,与二进制评价员、反射缓冲器和新的重试。
- 选择一个任务所需的 标度、 超速和自评反馈来源。
- 解释为什么口头加固会发现错误 gradient- 基地的RL需要数千次试验才能修复

<a id="the-problem"></a>

## 问题

一个 agent 失败任务。 在标准 RL 中, 您将运行数千次测试, 计算 gradients,更新 weights. 昂贵、慢和大部分生产 agents 并非每个失败都有一个培训预算。

反省(Shinn等人,ArXiv:2303.11366)提出了一个不同的问题:如果 agent 刚刚想了一下为什么失败 再试一次 prompt? 否 weight 更新。 gradient。在试验之间保存的只是自然语言。

结果:在ALF世界,它比 ReAct 和其他非调整的基线。在热锅QA上,它会改善 ReAct。在代码生成时,它设定了当时的艺术状态。 gradient step.

<a id="the-concept"></a>

## 概念

<a id="the-three-components"></a>

### 三个组成部分

```
Actor         : generates a trajectory (ReAct-style loop)
Evaluator     : scores the trajectory — binary, heuristic, or self-eval
Self-Reflector: writes a natural-language reflection on the failure
```

加上一个数据结构:

```
Episodic memory: list of prior reflections, prepended to the next trial's prompt
```

一次审判 Actor。 如果分数低, 自我反省器会产生反射( “ 我选择错误的工具是因为我误读了问题为 X 询问 Y ) 。 反射会进入偶发记忆中。 下一次尝试开始, 但看到反射 。

<a id="three-evaluator-types"></a>

### 三种评价人员类型

1. **Scalar** 外部二元信号。 ALFWorld 成功或失败。 人类的测试通过或失败。 最简单、 最高信号 。
2. **Heuristic** ——预定义的失败签名。“如果 agent 连续两次产生同样的动作,标记为卡住。 “如果轨道超过50步,则标记为无效。”
3. **Self-evaluated** — 该 LLM 选择自己的轨道。 需要时没有地面真相。 信号薄弱; 配对工具基础的核查( Lesson 05-) CRITIC).

2026年的默认是一个组合: 可用时加弧, 不可用时自增, 安全性轨道的超常性 。

<a id="why-this-generalizes"></a>

### 为什么这样概括

反射不是新的算法,而是命名的模式。几乎每个生产都“自我愈合” agent 运行一些变量 :

- Letta的睡眠时间计算 (Lesson 08): agent 反省过去的对话,写给记忆区。
- Claude Code's `CLAUDE.md` /“保存记忆”模式:作为学习记录,预选到今后会议。
- pro-workflow's `/learn-rule` 命令:更正被作为明确规则记录。
- LangGraph反射节点:一个分数输出的节点,必要时可以进行精细化。

自然语言是丰富多彩的媒介,

<a id="when-it-works-and-when-it-does-not"></a>

### 当它工作,当它不工作

反射在下列情况下有效:

- 明显有失败信号( 测试失败、 工具错误、 回答错误) 。
- 任务类可以复制( 同样的问题可以再次提出 ) 。
- 反思在轨迹上仍有改进的余地(足够的行动预算)。

反射在下列情况下无济于事:

- 该 agent 第一次尝试已经成功。
- 失败是外部的(网络被关闭,工具被打破)——对“网络被摧毁”的反思无助于未来的运行。
- 反射变成了迷信——储存着关于一次性的片断的叙述。

2026年的陷阱:记忆腐烂。 反射累积; 有些过时或错误; 随着偶发缓冲增长, 重新运行的速度会放慢 。 缓解: 定期压缩( Lesson 06) , 反射时 TTL , 或者单独进行睡眠清理 。 agent (Letta).

```figure
react-trace
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行玩具拼图上的反射: 生成一个三元素列表, 以相加到目标上。 the Actor 发布候选人名单; 评价员核对总和; 自译自审者写了一条关于错误的线。 反射会变成下一次试验的附带记忆。

Components:

- `Actor` 一种有文字的政策,当它看到反省时会有所改进。
- `Evaluator.binary()` - 目标金额的通过/失败。
- `SelfReflector` 产生一个失败的单线诊断。
- `EpisodicMemory` 与 TTL 语义的连接列表 。

运行：

```
python3 code/main.py
```

该 trace 试验1失败, 存储反射, 试验2看到反射, 改进但仍失败, 试验3成功。 与基线运行( 没有反射)相比, 它停留在试验1的回答上 。

<a id="use-it"></a>

## 实际应用

LangGraph 船舶反射作为节点模式。 Claude Code's `/memory` 命令和赞成工作流程 `/learn-rule` 将偶发缓冲外部化为 markdown 文件。 Letta的睡眠时间计算运行自反光器在停机时进行, 所以主机 agent 保持隐蔽 OpenAI Agents SDK 不直接运载反射; 您按习惯构建它 Guardrail 以记分和内存拒绝轨迹 `Session` 生存的横贯运行。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-reflexion-buffer.md` 创建并保持一个包含反射捕捉、 TTL 和重复的偶发缓冲。 鉴于任务类别和失败, 它释放出一个实际上有助于下一次试验的反射( 不是通用的“ 更小心” ) 。

<a id="exercises"></a>

## 练习

1. 从二进制到卡路里评价器,它返回距离测量仪(离目标有多远)。它会更快地聚合吗?
2. 将10个测试的TTL添加到反射中。 旧的反射会伤害还是帮助呢 ?
3. 执行超常评估器: 如果重复同样的动作, 试验将标记为卡住。 这如何与自我反射器互动 ?
4. 使用对称式进行反射 Actor 忽略反射。什么是最低反射 prompt engineering 强迫 Actor 来注意他们?
5. 阅读关于阿尔夫世界的反射论文第4节。从概念上将成功率提高130%:关键三角洲与香草是什么呢? ReAct?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Reflexion | "Self-correction" | Shinn等人,2023年- Actor,评价员,自我反省器加上偶发记忆 |
| 口头增援 | "学习没有 gradients" | 自然语言的反射预设 下一次审判 prompt |
| 笔记内存 | "工作式反射" | 一个任务类的先前反射的弯曲缓冲 |
| 斯卡路评价员 | "胜利信号" | 地面真相的通过/失败或数字分数 |
| 超能力评估员 | "以父子为基础的探测器" | 预定义的失败签名( 如卡住行、 太多步) |
| Self-evaluator | "LLM- 独立审判 trace" | 低信号回落,当没有地面真相时——同时进行基于工具的核查 |
| 内存腐烂 | 虚幻的反射 | 含有过时条目的缓冲填充; 使用压缩/ TTL 修正 |
| 睡眠时间反思 | 自我反省,自相矛盾 | 将自我反射器从热道上运行到最原始 agent 动作快点 |

<a id="further-reading"></a>

## 进一步阅读

- [Shinn等人,反省:语言 Agents 用波纹 Reinforcement Learning (arXiv:2303.11366)](https://arxiv.org/abs/2303.11366) - 银色纸
- [丽塔, 睡觉时间计算](https://www.letta.com/blog/sleep-time-compute) 生产中同步反射
- [Anthropic有效 context engineering 大赦国际 agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 管理偶发缓冲,作为背景的一部分
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) 反射节点模式
