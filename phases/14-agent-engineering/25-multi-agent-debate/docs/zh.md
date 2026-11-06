<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="multi-agent-debate-and-collaboration"></a>

# 多 Agent 辩论与协作

> Du 等人(ICML 2024,“精神学会”)运行了N型模型,独立提出答案,然后在R轮回合中反复批评对方以汇集。提高了事实质量、遵守规则、推理。 粗略的表层比全网格要优于全网格。 token 成本.

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 12(工作流程模式),阶段14 · 05(自备和 CRITIC)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释一下辩论程序:N提议者,R回合,就一个共同的答案汇合在一起。
- 说明为什么辩论会提高事实质量、遵守规则以及推理。
- 解释一下稀有的地形: 不是每个辩论者都得看对方。
- 执行关于脚本的 stdrb 辩论 LLM 具有全尺寸和稀薄的变体; token 成本与准确性。

<a id="the-problem"></a>

## 问题

自定义(Lesson 05)是一种模型,它本身就充满了风险群体思维。 CRITIC 辩论提出了第三种模式:多种情况、交叉批评、分歧意见趋同。

<a id="the-concept"></a>

## 概念

<a id="society-of-minds-du-et-al-icml-2024"></a>

### 思想学会(Du等人,ICML 2024)

- 以N为例,独立提出对同一问题的答复。
- 在R回合中,每个模型阅读其他模型的建议并批评它们。
- 模型根据批评更新了答案。
- R回合后,返回集合的答案。

由于成本原因,原试验使用N=3,R=2。 agents 以及更多关于困难问题的回合(MLU、GSM8K、象棋运动有效性、传记生成)。

跨模式的组合比单一模式的辩论要强: ChatGPT + 单管加在一起 > 。

<a id="sparse-topology"></a>

### 简略的表层

"改善多 -Agent 与粗略交流地形学的辩论(arXiv:2406.11776,2024-2025)显示的全比例辩论并不总是最佳的。 token 每个辩论者只看到一组同侪。

Implications:

- 全部网格N=5,R=3=5×3=15个建议,每份读4个同侪=60个批评意见。
- 星号N=5,R=3(一个中心+4个讲台)=15个提议,只读中心=12个批评行动。

<a id="when-debate-helps"></a>

### 辩论有助于

- **Factuality.** 独立建议书,交叉核对减少 hallucination.
- **Rule-following.** 象棋移动有效性——一个模型错过了一条规则,其他人则抓住它。
- **无限推理。** 答案正确时,多重框窄。

<a id="when-debate-hurts"></a>

### 辩论痛的时候

- **感应度敏感UX** N × R 序列弹是你们可能没有的隐形弹壳。
- **成本敏感比例尺。** 编号 × R tokens 每一个问题。
- **简单的事实调查。** 一次调查比五次辩论便宜。

<a id="2026-practical-instantiations"></a>

### 2026年实际的即时处理

- **Anthropic orchestrator-workers** (第12段)——辩论的一个变式,综合步骤。
- **LangGraph supervisor** (课程13)——中央路由器+专家 agents 能够将辩论作为一个节点进行。
- **OpenAI Agents SDK** (教训16) agents handoff 来回反复评论
- **Multi-agent evals** 双对辩论+评价员-optimizer 用于反射信号

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **趋同崩溃** 所有 agents 集中第一个错误的答案, 以所需的分歧回合来消化。
- **枢纽失败了** 在星体的地形上, 坏的中心会腐蚀每个人。 旋转或使用多个中心 。
- **Prompt homogenization.** 所有 agents 使用相同的 prompt;它们产生相同的答案。使用不同的 prompts 和/或模型。

```figure
debate-converge
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行标准辩论:

- `Debater` 类( 标注) LLM 使用每个辩论者的意见流)。
- `FullMeshDebate` 和 `SparseDebate` runners.
- 三个问题:一个事实问题,一个基于规则的问题,一个推理问题。
- 衡量标准:一致回答, 回合到趋同, 完全批评行动。

运行：

```
python3 code/main.py
```

产出:每项议定书的准确性和成本;很少以较低成本对2/3问题进行完全匹配。

<a id="use-it"></a>

## 实际应用

- **Anthropic orchestrator-workers** 简单2 -3员工辩论
- **LangGraph** 进行有声有色的多轮辩论
- **Custom** 研究或专业正确性保障。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-debate.md` 脚架上装了多个...agent 与可配置的地形、N、R和趋同规则的辩论。

<a id="exercises"></a>

## 练习

1. 执行“被迫分歧”规则:在第一回合中,每个辩论者必须提出一个独特的建议。 衡量对趋同速度的影响。
2. 增加一个信心加权汇总:辩论者返回(回答、信任);聚合 weights 自信地说,这有帮助吗?
3. 交换一号 "agent"为不同的脚本 LLM 不同的意见。异质性能提高准确性吗?
4. Measure token 全部网格和三个问题的成本都很少, 计划成本和准确性。
5. 读读《心灵协会》的论文。把玩具端到N=5,R=3。什么休息?有什么好转?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Debate | "Multi-agent critique" | N 提议者, R 交叉曲解回合, 趋同 |
| 满网格 | "每个人都会读" | 每个辩论者每回合都读每个对等者 |
| 简略的表层 | "有限对等视图" | 辩论者只读到一组对等点 |
| Hub-and-spoke | 星际学 | 一位中央辩论者,N-1发言只读到中心 |
| 收敛性 | "Agreement" | 辩论者就共同答案达成共识 |
| 思想学会 | “Du等人辩论文件” | ICML 2024 多个agent 辩论方法 |

<a id="further-reading"></a>

## 进一步阅读

- [Du等人,精神学会(arXiv:2305.14325)](https://arxiv.org/abs/2305.14325) - 共性多语种agent debate
- [传播方式简陋(arXiv:2406.11776)](https://arxiv.org/abs/2406.11776) 少见的地形结果
- [Anthropic建设有效 Agents](https://www.anthropic.com/research/building-effective-agents) 管弦乐队工作者作为辩论变体
- [Madaan等人,自备(arXiv:2303.17651)](https://arxiv.org/abs/2303.17651) 单一模型自我评论对应方
