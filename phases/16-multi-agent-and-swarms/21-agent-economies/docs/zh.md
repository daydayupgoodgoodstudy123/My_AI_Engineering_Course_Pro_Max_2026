<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="agent-economies-token-incentives-reputation"></a>

# Agent 经济体系、Token 激励与声誉

> 长视距自动 agents 需要经济机构。 **5层堆叠** 是: **DePIN** (物理计算) **Identity** (W3CDS+声誉资本) **Cognition** (RAG + MCP) → **Settlement** (账户抽象) **Governance** (Agentic 生产 agent- 奖励网络包括: **Bittensor** (TAO子网奖励特定任务模式) **获取. i/ ASI 联盟** (ASI-1 微型) LLM + FET 组合键 token), 和 **Gonka** (transformer学术工作:AAMAS 2025年分散的拉马斯使用 **阴影值信用归属** 以至于报酬捐躯者, agents谷歌研究“大型语言模型的机械设计”提议 **token auctions** 以单调总和下第二价支付。 此课构建了一个最小值的 agent 市场,将Shapley价值信用归属应用到一个多agent 输油管,然后用第二价 token 拍卖,所以游戏理论机器 具体地降落。

**类型:** 学习
**语言:** Python (stdlib)
**先修要求:** 阶段16 16(谈判和谈判),阶段16 -09(Parallel) Swarm Networks)
**时间:** ~75分钟

<a id="problem"></a>

## 问题

Multi-agent 系统变得复杂 agents 传统机制 — — 平等分割、最后贡献者- 全部接受 — — 是不公平的或可玩游戏的。 通过Shapley 价值联盟式的回报通过建筑是公平的,但计算成本却很高。 2025-2026年的文献推崇了有用的近似值:Shapley sampling单调集成拍卖,以及从确认的贡献中积累的连锁声誉。

除了信贷归属,该领域已转向实际经济 agents: Bittensor TAO 奖励采矿计算精细调整子网特有模型, Fetch.ai/ ASI 奖励 ASI-1 Mini LLM 使用 FET 工具 tokens, Gonka 重新配置 transformer 向具有生产力的人工智能任务证明工作。 Agents 这个问题是如何调整奖励办法的。

课上讲解 agent 经济作为一个具体问题的家庭——信贷归属、机制设计和声誉——并以最低的数学来建立,这样思想就坚挺。

<a id="concept"></a>

## 概念

<a id="the-5-layer-agent-economy-stack"></a>

### 5层 agent- 经济堆叠

1. **DepIN(物理计算)** 出租的分散基础设施 GPU存储器、带宽 下网、 网络、 Akash 。 agent-specific; agents 使用现有工具.
2. **Identity.** W3C 分散标识符(IDs)给每个 agent 独立于任何平台的耐久身份。 名声归实于事实。 The the ident understand understand any popherate. Agent 网络协议(ANP) 用作发现层。
3. **Cognition.** 该 agent逻辑循环 : LLM + RAG + MCP。这是其他阶段的建设。
4. **Settlement.** 账户抽象(ERC-4337) agents 自己用自己的余额来支付煤气,不用持有乙烷。 Agents 能够支付服务费,或相互支付,或计算。
5. **Governance.** Agentic DAO: 人所在的治理结构 *和* agents 投票决定改变程序 投票权与声誉挂钩

并非每个生产系统都使用所有五种。 毕滕索使用1、2部分3部分4部分,无5种。 OpenAI agents 除3外,书架是参考地图,不是要求。

<a id="bittensor-fetchai-gonka--what-runs"></a>

### 毕多尔,费奇,强卡,什么运行

**毕滕索尔(TAO)。** 子网是专门的任务(语言模型、图像生成、预报)。矿工们提交模型输出。验证者排位;定额评分分配 TAO 奖赏。每个子网都有自己的 evaluation经济教训:为特定任务产出质量支付费用,而不是计算。

**获取. i/ ASI 联盟。** ASI-1 微型 LLM 在 Fetch. ai 的网络上运行; 用户支付 FET tokens 用于 inference. 该 agents- 说来话长: agent 获取时可以要求另一个任务,并支付FET。

**Gonka.** Transformer 工作证明:“工作”是指 forward passes 排 定 的 会 议 transformer矿工通过跑来赚钱 inference 具有资源效益的《人民工作报》,而不是基于散列的《人民工作报》。

这三个都是2026年4月时的产级。 报酬分配不同。 比唐索奖比亚网验证器还高; 获取由付款用户衡量的奖励工具; Gonka 奖赏可以核实 inference work.

<a id="shapley-value-credit-attribution"></a>

### 阴影值信用归属

Three agents 产出得分0.8 谁出什么价?

损耗值:满足四个轴的独有信用分配(效率、对称性、直线性、无效)。 agent `i`:

```
shapley(i) = (1/N!) * sum over all orderings O of (v(S_i_O ∪ {i}) - v(S_i_O))
```

where `S_i_O` 是一套 agents 之前 `i` 命令 `O`在实践中:列出所有变化,记录每个变化的边际贡献。 agent 每一个变形,平均。

N=3 类 agentsN=10, 3.6M-所以在实践中,你抽样点菜而不是列举。

<a id="second-price-auction-for-aggregation"></a>

### 合并的第二次价格拍卖

Google Research (“大型语言模型的机械设计”)提出第二价 token 拍卖以汇总 LLM 设置: N agents 每一个建议完成; 每个都有被选中的私人价值。 拍卖人选择最高价值的投标书并支付 *second-highest* 在单调组合下(价值取决于选择的是哪一种投标书,而不是多少投标),这是真实的—— agents 出名的真价实

为什么这很重要 LLM 系统:您可以将完成任务外包给多个 agents 价格不同;拍卖选择最佳+公平支付, agents 没有什么动机来误导我

<a id="reputation-capital"></a>

### 名声资本

确定为实实在在的声誉分数从确认的捐款中累积。

```
rep(i, t+1) = alpha * rep(i, t) + (1 - alpha) * contribution_quality(i, t)
```

带有衰变系数 `alpha` 接近于 1. 声望:

- 用于选择路径( 将硬任务发送到高复位) 便宜 agents").
- 伪造成本很高(累积时间,必须完成)。
- 可削减:不进行核查的捐款减去。

<a id="aamas-2025-decentralized-lamas"></a>

### 2025年分散的拉马斯

拉马斯(AAMAS 2025)提案将身份、Shapley价值信用归属和简单的拍卖机制结合起来。 关键债权:分散信用归属步骤可以审计,并且不受单点操纵。

<a id="where-the-economics-falls-apart"></a>

### 经济崩溃的地方

- **操纵价格和神器** 如果信用函数可以被玩弄, agents 每一个机制都需要一个对抗性测试
- **茜玻袭击** 一个接线员变假 agents 以扩大他们的贡献。 这样做缓慢,但并没有停止; 降低声誉的代价就是降低声誉。
- **核查费用。** 信用归属与核查者一样公平。 LLM),它可以被游戏;如果费用昂贵(人类面板),则系统不会扩大规模。
- **监管的悬崖。** Agent 2026年,Bittensor、Phet和Gonka在一些管辖区内都合法地在灰色地带运作。

<a id="when-agent-economies-make-sense"></a>

### 当 agent 经济是有道理的

- **与多种操作员开放网络。** 没有一个团队控制全部 agents.
- **可核查产出。** 未经核实,信用归属就是一个猜测。
- **长视距工作流程。** 一次完成的任务不会从声誉积累中受益。
- **支付现款在法律上是可行的** 属于你们管辖的

在封闭的公司系统中,经济学让位于更简单的分配(管理人员分配工作,衡量标准是内部的 ) 。 经济学文献主要适用于开放网络。

```figure
swarm-auction
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `shapley(value_fn, agents)` 精确的毛细图,以小N计数计算。
- `second_price_auction(bids)` 诚实的机制;赢家的薪酬最高。
- `Reputation` 以指数衰减和砍刀 来赢得名声
- 演示1: 3 agents 合作,准确的 Shapley属性信用。
- 演示2: 5 agents 投标工作档;二次价格拍卖取胜者+付款。
- 3:100轮任务任务分派到 agents 具有多种代表; 代表加权路径会随机跳动。

Run:

```
python3 code/main.py
```

预期产出:每个阴影值 agent; 拍卖结果显示真实出价平衡; 代表加权路径显示在随机后质量收益10-20% warmup.

<a id="use-it"></a>

## 实际应用

`outputs/skill-economy-designer.md` 设计一个最小的 agent 经济:身份层的选择、信贷归属机制、支付机制、声誉规则。

<a id="ship-it"></a>

## 交付成果

运行 agent 2026年经济:

- **以名声开始,不是 tokens.** 光靠名声是廉价的,而且很宝贵; tokens 增加了法律和经济的复杂性。
- **事先确认一下** 无法独立验证的信用发放。 自报的质量会累积 Sybil 游戏 。
- **长得像,不是长得像** 样本 100-1 000 订单; 精确的查点不标尺 。
- **船舱腐蚀因素和底部声誉。** 无界衰变会抹去合法贡献者;过慢的衰变会给人带来腐烂的高复数 agents.
- **对抗性审计机制。** 在打开网络前运行红色队的场景。 每个机制都有游戏理论; 您想要找到漏洞, 而不是攻击者 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。确认阴影值和总值(效率轴)。 value function; Shapley分配是否在预期方向上发生变化?
2. 执行 Shapley *sampling* (Monte Carlo K 的精确度如何影响近似性?
3. 在拍卖前采取联盟制步骤: agents 合并成团队,并作为一个单位投标。哪个联盟组成?结果比个人投标好吗?
4. 读读 Google 机制设计文章。 确定一个假设, 如果被违反, 将打破真实性。 在 IP 中, 这个失败模式看起来像什么 ? LLM setting?
5. 阅读《2025年美国排雷行动标准》分散版拉马斯纸。 agents 精确计算需要多长时间? sampling 一百张?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| DePIN | "分散的有形基础设施" | Token- 激励计算/储存/带宽。 |
| DID | "分散的标识符" | 便携式身份证的 W3C 规格 。 Agent 声誉与事实相关,而不是与平台相关。 |
| ERC-4337 | 会计抽象 | 能够赞助天然气的合同账户,使能 agent payments. |
| 阴影值 | 公平信用归属 | 独特的分配满足效率,对称,线性,无效。 |
| 二价拍卖 | "Vickrey拍卖" | 真实的机制: 赢家支付第二高的出价。 单调组合兼容 。 |
| 名声资本 | 累积质量评分 | 确实从已确认的捐款中得分;随着时间的推移,情况逐渐恶化。 |
| Agentic DAO | "Agents +人类统治" | 与 DAO 连接 agent 选民是头等阶级, 投票权与声誉挂钩。 |
| 技术评估/财务培训/ GPU credits | "Token denominations" | 毕登索TAO,费城,各种Depint tokens. |

<a id="further-reading"></a>

## 进一步阅读

- [该 Agent Economy](https://arxiv.org/abs/2602.14219) - 2026年5层调查 agent- 经济堆叠
- [Google研究——大型语言模型的机制设计](https://research.google/blog/mechanism-design-for-large-language-models/) — token 单调聚合拍卖
- [AAS 2025年——权力下放的LAMAS](https://www.ifaamas.org/Proceedings/aamas2025/pdfs/p2896.pdf) - 价值价值的信贷归属
- [毕滕索·托尔文档](https://docs.bittensor.com/) - 子网结构和奖励分配
- [获取. i/ ASI 联盟](https://fetch.ai/) -ASI-1迷你号 LLM 和训练 token
- [W3C 分散标识符(IDs)规格](https://www.w3.org/TR/did-core/) 身份基础
