<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="voting-self-consistency-and-debate-topology"></a>

# 投票、自洽性与辩论拓扑

> 最廉价的汇总:抽样 agentsWang等人2022年的自定性用一个样本N次数做了这个。agent 扩展它 **heterogeneous** agents 以摆脱单一文化——不同的模式,不同的 prompts,不同的 temperatures多方利益集团(arXiv:2503.01935,ACL 2025)评估了恒星/链/树/图的协调情况并找到了 **用于研究的最好图表**,在~4之前,使用“协调税” agents. AgentVerse (ICLR 2024) 记录了两种新出现的模式——志愿行为和符合性行为,而符合性既是 feature 课程的设置是: 设计一个“模型”的模型, 设计一个“模型 ” ( 调查共识)和一个“风险 ” ( 群思 , 课程24 ) 。 这个课程绘制了地形空间,构建了每个变量,并测量了协调税。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 第16阶段 -07(精神和辩论社会),第16阶段 -14(共识和BFT)
**时间:** ~75分钟

<a id="problem"></a>

## 问题

辩论可以提高准确性(Du等人,ArXiv:2305.14325),也可以降低其准确性。

1. 与谁交谈(地形)的人。
2. 多少发子弹(Du 2023:两发和 agents 独立地处理问题)。
3. 是否 agents 具有多种特性(不同的基数模式打破单一文化)。
4. 是否有对抗性声音( 感官- 曼宁与吸管- 曼宁) 。

5号机的球队 agents 并投票决定一项任务, 通常会倒退或单次 agent。失败不是随机的。它们跟踪着地形学和异质性。这个课是地形图。

<a id="concept"></a>

## 概念

<a id="self-consistency-the-single-model-baseline"></a>

### 自我一致性,单一模式基准

Wang等人,2022年(“自我统一改善”) Chain of Thought ))(在 temperature 大于 0, 多数人投票决定了理性选择答案。 GSM8K的结果: N=40 样本在单一贪婪解码上取得了显著的收益。 自我一致性是单一-agent 用于多-agent voting.

限制: 自 己 一致性使用一个基模式。 错误通过构建来关联。 如果模型有系统性偏差, 所有 N 样本都会共享 。

<a id="multi-agent-vote-the-heterogeneous-extension"></a>

### Multi-agent 选项, 变量扩展

将N样本替换为N *different* agents不同的基准模型(Claude, GPT, Llama),不同的 prompts,不同的工具访问。好处是:与非关联的错误。成本:不同 agents 费用不同;协调后增加间接费用。

不同辩论的2026年卡尼科式名称是 **A-HMAD** 反异体多式Agent 辩论。不是普遍采纳,而是论文使用“不同的模型辩论,减少单一文化崩溃造成的相关错误”这一术语。

<a id="the-four-topologies"></a>

### 四个主题

```
star                chain               tree                graph

    ┌─A─┐           A─B─C─D         ┌──A──┐              A───B
    │   │                           │     │              │ × │
    B   C                           B     C              D───C
    │   │                          / \   / \
    D   E                         D   E F   G           (fully connected)
```

星: 一个中心, 所有其他只和中心交谈。 等同于没有后门的主管- 工人 。
链条:线性, 每一个 agent 前面的输出,像管道一样
树: 等级, 用于等级 agent 系统(列松06)。
图:任何方面。包括完全相连的俱乐部和任意的DAG。

<a id="the-coordination-tax-multiagentbench"></a>

### 协调税(多国邦奇)

多机构区(MARBL,ACL 2025,arXiv:2503.01935)基准星、链、树、任务套件图,包括研究、编码和 planning关键衡量结果:

- **Graph** 信息随处流通; agents 能够互相批评
- **Star** 快速回答事实任务获胜。 枢纽过滤和整合 。
- **Chain** 逐步地赢得输油管(分阶段改进)。
- **协调税** 显示于~ 4 agents 以图示形式显示。 token 成本增长快于质量。

4号agent 上限是经验性的,不是根本性的。 LLM 环境能力:每个 agent环境充斥同行的产出, 以及添加的边际值 agent 等大家看到每个人,N+1就会下降

<a id="multi-agent-debate-strategies-should-we-be-going-mad"></a>

### Multi-Agent 辩论策略 (“我们该去MAD吗? ”)

ARXiv:2311.17371是2023年MAD战略调查。 *结构相似* 独立(独立) sampling + 合计) 使用同一预算时,往往表现不佳,自我一致性差。 agents 辩论结构是对抗性的(第1条)。 agent ) 争论)。

<a id="agentverse-emergent-patterns"></a>

### 代理Verse 紧急模式

AgentVerse（ICLR 2024， https://proceedings.iclr.cc/paper_files/paper/2024/file/578e65cdee35d00c708d4c64bce32971-Paper-Conference.pdf ）记录了多 agent 辩论中即使不做显式设计也会涌现的两种行为：

- **Volunteer.** 一个 agent 提供未迅速的帮助。它能将工作分配给最有能力的人。 agent 用于子任务。
- **Conformity.** 一个 agent 调整其位置以匹配 critic,即使当 critic 这是辩论的类比, 相当于恋童癖(Lesson 14)。

服从是辩论到协议奖励欺凌的原因。 与法官单独交锋会减轻压力。

<a id="heterogeneity-the-actual-knob-that-moves-accuracy"></a>

### 异质性: 移动精度的实际按钮

实践文献中的2024-2026模式:转换您的 N型 agents 直觉是单种的——每个新的独立性错误源都比一个额外的相关样本更值钱。

在极限中,异质性比数字性强。三种不同的模型比一个模型的五倍多,而大多数任务都是有干净地面真相的。

<a id="jury-methods"></a>

### 陪审团方法

锡比尔框架(在明斯克引用)LLM 将“陪审团”正式化——一套专门化的 agents 与简单多数票不同,陪审团有以下作用: agent 交叉质询,一个供货环境,一个分数的可信赖性。 陪审团方法是平方表决(低、单一文化易发)和完整的MAD(昂贵、易达)之间的中点。

<a id="when-vote-with-debate-dominates"></a>

### 以投票方式辩论时占主导地位

- 问题有事实( 事实、 数学、 代码行为) 。 投票趋同是有意义的 。
- Agents 能够访问不同的来源或工具(可获取异质性)。
- 轮数是相互交错的(2-3个典型),有单独的法官或核查员。
- 预算允许 3-5 agents。在图表上的5-7之后,协调税占主导地位。

<a id="when-vote-with-debate-hurts"></a>

### 投票和辩论时受伤

- 问题就是意见形 Agents 找到最自信的答案 而不是最正确的答案
- 所有 agents 单体文化使得共识毫无意义
- 回合没有限制 每次都得遵守
- 任务很简单,只有一个 agent N=5的自定性比较便宜,也比较准确。

```figure
sw-debate-topology
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `run_star(agents, hub, question)` 中心调查每个工人,总数。
- `run_chain(agents, question)` 逐级完善。
- `run_tree(root, children, question)` - 等级与深度2组群。
- `run_graph(agents, question, rounds)` - 全面辩论,交界的回合。
- 脚本异质拨号: agent 拥有 `error_bias` 表明它有系统错误。
- 计量 harness 以 N=3, 5, 7 和报告(准确性, 总计) 运行每个表层_挂牌, 挂钟_simulated).

Run:

```
python3 code/main.py
```

预期产出:表层数 × N  (准确度, tokens。图在研究型任务上以 N=3-5 赢得; 恒星在快速事实任务上获胜; 图表在 N=7 显示协调税(延缩速度快于精确度)。

<a id="use-it"></a>

## 实际应用

`outputs/skill-topology-picker.md` 是一种技能,读取任务描述并推荐一个表层(星/链/树/图),一个N(数字) agents),异质性剖面图(使用基准模型)和圆形。

<a id="ship-it"></a>

## 交付成果

任何组合:

- 以 **N=5时的自理性** 使用一个强大的基准模型,这是廉价的基线。
- 升级至 **N=3的多党投票** 如果准确性很重要的话 测量三角洲
- 升级为 **辩论的表层** 如果任务结构(研究、多步)和捆绑的圆轮是可行的。
- 总是记录少数群体群集。 当少数群体持续右侧时, 您就会有多样性信号 。
- 基准墙时钟和 tokens 与准确性。 “以10x成本提高准确性”是一个商业决定。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。绘制图表表层的坐标-税曲线:准确度与 N, tokens 与N. 曲线的偏移?
2. 实施A-HMAD:3 agents 与A-HMAD相比,14课的单一文化攻击如何?
3. 图表中添加“ 判断” 功能, 不投票, 只分到最后的共识。 这是否改变了新出现的合规行为 ?
4. 读一下 AgentVerse 纸张 (ICLR 2024) 。 确定您执行时最强烈的哪些突发行为。 您能否通过 a 来诱导相反的行为 ? prompt change?
5. 读取多 AgencyBench (arXiv:2503.01935) 第4节(地形实验)。您使用纸张复制“ 绘图- 赢- 研究” 结果 harness.

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Self-consistency | 标本,投票 | 王2022,单型,N temperature>0个样本,多数人投票决定推理路径。 |
| Heterogeneity | "不同的模型" | 不同基础模型或 prompt 家庭 打破了单一文化 |
| MAD | "Multi-agent debate" | 通用术语 agents 换了子弹的批评,见杜2023 |
| A-HMAD | 不同异族的MAD | MAD变式强调不同的模式+对抗性结构。 |
| Topology | "谁说话的人" | 星系,链条,树,图 确定信息流 |
| 协调税 | "减法回归" | 超过~4 agents 成本增长快于质量 |
| 志愿行为 | "未迅速的帮助" | 代理Verse 突发模式: a agent 愿意迈出一步 |
| 合规行为 | "压力下的协议" | 代理Verse 突发模式: a agent 与 critic. |
| Jury | "小型专门面板" | 具有角色的西比尔式合奏( 检查者、 上下文、 得分者) 。 |

<a id="further-reading"></a>

## 进一步阅读

- [王等人——改善自我一致性 Chain of Thought Reasoning](https://arxiv.org/abs/2203.11171) 单一模式基线
- [Du等人——通过多代理人辩论提高事实质量和理由](https://arxiv.org/abs/2305.14325) — 两者 agents 单枪匹马
- [多方商场/市场](https://arxiv.org/abs/2503.01935) 显示最佳研究图表和管道链的地形基准
- [我们该去麦道夫吗?](https://arxiv.org/abs/2311.17371) MAD战略调查;发现MAD常常由于预算平等而失去自我一致性
- [特工Verse(ICLR 2024)](https://proceedings.iclr.cc/paper_files/paper/2024/file/578e65cdee35d00c708d4c64bce32971-Paper-Conference.pdf) 志愿和合规模式
- [马尔波尔转接器](https://github.com/ulab-uiuc/MARBLE) 基准执行情况
