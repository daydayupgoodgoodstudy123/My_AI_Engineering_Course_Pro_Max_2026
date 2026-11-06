<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="negotiation-and-bargaining"></a>

# 协商与议价

> Agents 谈判资源、价格、任务分配和条件。 2026年的基准范围是明确的:谈判阿雷纳(arXiv:2402.05863)显示 LLMs 可以通过人手操纵(“绝望”)提高收益~20%;“衡量讨价还价能力”(arXiv:2402.15813)显示买方比卖方更难,规模无益—— **OG-Narrator** (确定性报价发电机+ LLM 将交易率从26.67%推到88.88%;大规模自主谈判竞争(arXiv:2503.06416)进行了~180k的谈判,并发现 **chain-of-thought-concealing** agents 隐藏对口人的推理,从而赢得胜利;Bhattacharya等人,2025年哈佛谈判项目衡量标准排名 Llama- 3个最有效力的, Claude- 3号攻击性 GPT课程内容包括合同网络协议(FIPA祖先,02课),以及 LLM- 式样的买方/卖方,运行OG-Narrator式分解,并测量交易率随每个结构选择的变化。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段16 02(FIPA-ACL遗产),阶段16 -09(Parallel) Swarm Networks)
**时间:** ~75分钟

<a id="problem"></a>

## 问题

Two agents 需要商定一个价格。 prompts, 2024-2026 LLMs 以惊人的低利率(在严格参数交易中, irXiv: 2402.15813) 进行交易。 比例不修正 : GPT-4在结构上比在谈判方面还好 GPT-3.5; 比较好 *language* 讨价还价

根本问题是 LLMs 配置两个工作—— 决定报价并描述报价。 OG- Narrator 将这些任务分开: 一个确定报价的提供方计算数字动作; LLM 仅说明。交易率跳至~89%。

这反映了一个古典的多功能agent 发现:将机制与通信层脱钩,胜出。合同网络协议(FIPA,1996年;Smith,1980年)是参考任务市场机制。 LLM 进入叙事槽,你得到一个现代 LLM- 授权任务市场

<a id="concept"></a>

## 概念

<a id="contract-net-in-one-paragraph"></a>

### 合同净额,一个段落

史密斯1980年合同净额协议:a **manager** 广播a **征集建议(参考)**; **bidders** 回应方式 **propose** 包含报价的信息; 经理选择赢家并发送 **accept-proposal** 致赢家和 **reject-proposal** 给失败者。获胜者执行工作。 **refuse** 联邦投资管理局将此编为 `fipa-contract-net` 互动协议。

<a id="why-og-narrator-wins"></a>

### 为什么OG -Narrator赢了

“衡量语言模型的讨价还价能力”(arXiv:2402.15813)指出:

- LLMs 通常违反谈判规则(以非敏感价格报价,无视另一方的ZOPA)。
- 它们固执得很差(接受错误的先出价;象征性地而不是战略性地反价)。
- 光缩放无法修正这些。 较大的模型可以使用类似的战略错误, 使语言更易被使用 。

OG- 纳托尔分解:

```
           ┌──────────────────┐        ┌──────────────────┐
  state  → │ offer generator  │ price → │  LLM narrator    │ → message
           │  (deterministic) │        │  (writes the     │
           │                  │        │   human-style    │
           └──────────────────┘        │   accompaniment) │
                                       └──────────────────┘
```

报价产生者是一种典型的谈判战略:鲁宾斯坦谈判模式、Zeuthen战略,或对价格的简单“tit for-tat”策略。 LLM 叙事。信息包含决定性价格和自然语言框架。

交易率跳跃是因为:
- 价格在谈判区
- 锚是战略的,不是情感的
- 该 LLM 做它擅长的事:写作。

<a id="negotiationarena-findings"></a>

### 谈判结果

arXiv:2402.05863提供了罐头基准。

- LLMs 个人操纵是一种真正的策略。
- Fair/cooperative agents 被对抗性攻击所利用;防御需要明确的反推。
- 对称配对在大约40%的基准情景中都与不公平的结果相趋同。

这不是 "LLMs 谈判者是坏人。LLMs 谈判太像人类,包括可开发的部分。"

<a id="chain-of-thought-concealment"></a>

### Chain-of-thought concealment

大规模自主谈判竞争(arXiv:2503.06416)在很多方面进行了180k次谈判。 LLM 胜者隐瞒了对等者的推理:

- 如果 agent 指纹“我只卖75美元,我的订位价是70美元”, 被一个公开可见的刮痕打印出来,对手读到。
- 获胜者私下计算策略;产出频道只包含报价和最低要求的叙述。

这是2026年经典游戏理论的回响(Aumann 1976年,关于理性和信息):揭示你的私人估值成本回报。 LLMs 不要理会, 并愉快地将保留输入推理 traces 成为对方可见。

工程外卖: 与公共讯息环境分开的私密插件背景。 不可选择 。

<a id="bhattacharya-et-al-2025--model-rankings"></a>

### Bhattacharya等人,2025年——模型排名

关于哈佛谈判项目的标准(原则性谈判、BATNA尊重、利益互惠):

- **Llama-3** 交易效率最高(交易率+回报率)。
- **Claude-3** 是最有侵略性的谈判者(高锚、晚期特许权)。
- **GPT-4** 是最公平的(对口对口的回报差异最小)。

这是2025年的一幕。关键不是哪一种模型在2026年4月获胜,而是不同的基数模型具有持久的谈判风格。 不同式的组合(列松15)将它作为一个多样性来源。

<a id="task-allocation-via-contract-net--llm"></a>

### 通过合同网分配任务+ LLM

现代合同网的重新使用 LLM multi-agent:

1. Manager agent 将任务分解成单位
2. Broadcasts `cfp` 给工人说明任务 agents.
3. 每个工人都回馈了报价: `(price, eta, confidence)` 价格可以 tokens,计算单位,或美元。
4. 经理根据任务挑选获奖者(单一或多个)和获奖者。
5. 被拒绝的工人可自由投标从事其他工作。

其规模远超过100名员工,因为协调是广播和回覆的,而不是同步聊天。 Agent Framework's orchestration 模式,有些 LangGraph implementations.

<a id="llm-stakeholders-interactive-negotiation"></a>

### LLM- 利益攸关方互动谈判

NeurIPS 2024 论文（ https://proceedings.neurips.cc/paper_files/paper/2024/file/984dd3db213db2d1454a163b65b84d08-Paper-Datasets_and_Benchmarks_Track.pdf ）介绍了具有**秘密评分**和**最低接受阈值**的多方可评分博弈。每位利益相关方都有私有效用，LLM 必须从消息中推断这些效用。这将双方讨价还价推广到 N 方联盟形成问题，适用于工作者能力各异的生产任务市场。

<a id="the-narration-vs-mechanism-rule"></a>

### 叙事-vs-memism 规则

2024-2026年谈判的所有基准中,一贯的工程规则是:

> 让 LLM 说吧,别让 LLM 计算出报价

如果要价需要数字(价格、ETA、数量),则从谈判状态中确定产生,并具有 LLM 如果要约需要建议结构(任务分解、角色分配),则让 LLM 起草,但根据发送前的策略和限制检查加以验证。

```figure
a5-og-narrator
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `ContractNetManager`, `ContractNetTask`, `Bid` 经理+投标人,广播小费,收集建议书,授标。
- `og_narrator_bargain(state, rng)` 有机金属-纳托尔买方:确定性Zeuthen式特许权,向中点倾斜。
- `seller_response(state, rng)` 确定性卖方反出价政策(这两种形式的结构性依据)。
- `naive_llm_bargain(state, rng)` - 模拟一个全部LLM 交易商:选取价格,价格差异很大,往往在ZOPA之外。
- 计量:每次测试抽样的交易率超过1000次,并采用新的订货价格。

Run:

```
python3 code/main.py
```

预期产出:天真LLM 交易率~65-75%; OG-Narrator 交易率~85-95%; 15-25点差距是将报价产生与叙述分解的结构优势。 加上合同净额任务市场分配示例,有三个投标人和一个任务。

<a id="use-it"></a>

## 实际应用

`outputs/skill-bargainer-designer.md` 设计谈判协议:谁提出要约(确定性或 LLM),谁在叙述,私人刮痕是如何与公共信息分开的,以及如何监测交易率。

<a id="ship-it"></a>

## 交付成果

生产谈判清单:

- **分开的刮痕** 私人国家从不触及对方的背景,这是不可谈判的。
- **决定性的供货人** 价格、数量、 ETAs: 计算, 不计算 prompt.
- **验证所有收到的报价** 拒绝在协议边界提出的退出ZOPA的报价。
- **弹道弹孔** 最多3-5轮;陷入僵局,升级为调解人。
- **计量交易率和付款差异** 交易率下降是一种症状,往往是 prompt 漂移或对面攻击
- **记录所有被拒绝的建议书** 合同网经理需要理解失败的投标人为什么这样做。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`. 确认OG -Narrator 击败天真LLM 交易率,多少钱?
2. Implement **个人报酬改善** (arXiv:2402.05863)——买方只采用“不愿购买本周”的人,提供生成器,没有变化。交易率或付款率是否改变?
3. Implement chain-of-thought **concealment**:保持一个未传递给对应方的私有抓图字符串。如果意外泄漏(通过互换频道模拟)会怎样?
4. 将合同网扩展至N-投标人拍卖,并保留价格。 当出价都超过储备时,经理如何决定最低价格和最高质量? 你选择哪一种授标规则,为什么?
5. 阅读Bhattacharya等人,2025年哈佛谈判项目指标,采用两种不同形式的交易(侵略性对公平),在对称和不对称配对下衡量收益差异。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 合同净额 | 广告市场 | Smith 1980年,FIPA 1996年,折叠式+建议接受/拒绝。 |
| ZOPA | "可能达成协议的地区" | 买方最大和卖方最高之间的重叠。 外部的报价无法关闭 。 |
| BATNA | "谈判协议的最佳替代方案" | 交易失败了,你就会退缩 设定你的订位价格 |
| OG-Narrator | 提供发电机+旁白 | 分解:决定性的报价; LLM narration. |
| 泽德森战略 | "减低风险特许权" | 古典报价生成者,根据风险限度作出让步。 |
| 鲁宾斯坦谈判 | 交替出价平衡 | 游戏理论模型 无限的和分的讨价还价 |
| 隐藏计算机 | 隐藏你的推理 | ARXiv 中的胜者: 2503. 06416 保留私人刮痕板; 公共频道只显示报价 。 |
| 个人操纵 | 情感姿势 | arXiv:2402.05863: ~20%的收益来自绝望/紧张的人。 |

<a id="further-reading"></a>

## 进一步阅读

- [NegotiationArena](https://arxiv.org/abs/2402.05863) 基准;人造图案和剥削结果
- [衡量语文模式的讨价还价能力](https://arxiv.org/abs/2402.15813) oG-Narrator和买方-买方-买方-买方-非卖方-结果
- [大规模自主谈判竞争](https://arxiv.org/abs/2503.06416) - ~180k谈判; chain-of-thought 隐藏赢
- [LLM- 利益攸关方互动谈判(NeurIPS 2024)](https://proceedings.neurips.cc/paper_files/paper/2024/file/984dd3db213db2d1454a163b65b84d08-Paper-Datasets_and_Benchmarks_Track.pdf) 具有秘密功能的多党可搜索游戏
- [1980年史密斯合同净额协议](https://ieeexplore.ieee.org/document/1675516) 计算机交易的经典机制
