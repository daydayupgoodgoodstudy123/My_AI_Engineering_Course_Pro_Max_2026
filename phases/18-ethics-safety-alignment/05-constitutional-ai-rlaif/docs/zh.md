<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="constitutional-ai-and-rlaif"></a>

# Constitutional AI 与 RLAIF

> Bai等人(arXiv:2212.08073,2022)问道:如果我们用一个阅读了原则清单的AI来取代人类标签?宪法AI有两个阶段——根据宪法进行自我批评和修订,然后根据AI反馈进行RL。 Claude 1个训练后管道,2026年1月21日 Anthropic 发表改写稿 Claude 宪法:对规范性规则的解释性推理,四级优先等级,以及首次正式承认关于模范道德地位的不确定性。

**类型:** 学习
**语言:** Python (stdlib,玩具自缩和翻转循环)
**先修要求:** 第18阶段 · 01(制造GPT),第18阶段 · 02(奖励性黑客)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 描述宪法独立两阶段(评论和修订) SFT宪法在每一条中的作用。
- 解释为什么用人工智能标签取代人类偏好标签不是“更衣者” RLHF 它改变了输油管的失败模式。
- 概述2026年四级优先结构 Claude 以及2023年重写时的变化
- 描述宪法分类,从23.7%计算间接费用(v1)降至~1%(v2/2026)。

<a id="the-problem"></a>

## 问题

RLHF 标签是缓慢的,有偏见的,而且昂贵。你可以用一个明确的原则模式来取代标签。这个替代的首个正式版本是Bai等人的宪法人工智能。它非常有效,每个边疆实验室现在都使用一些AI-feed back 后训练的变体。

抓取: 优先信号现在由您正在训练的同一类模型生成。 标签器中的比喻( 现在: 在原则加上标签模型的解释中) 可以放大而不是减弱。 课程4的偏差论仍然适用; 标签器刚刚移动到循环中 。

<a id="the-concept"></a>

## 概念

<a id="phase-1--supervised-self-critique-and-revision"></a>

### 第一阶段——监督自我批评和修改

以无伤大雅的但无损开始 SFT 模型。 给一个红色的队 prompt模式产生初步反应。第二个模式(或第二回合中的同一模式)从宪法中读取了抽样原则,并对反应进行了批评。第三步是修改回应,以解决批评。订正答复是: SFT target.

宪法是原则清单。Bai等人(2022年)使用了16项原则,包括“更愿意做出最无害和道德的反应 ” “避免传教 ” , “助理应该有帮助、诚实和无害 ” 。 这套原则有意显得小,以保持批评的焦点。 ”

<a id="phase-2--rl-from-ai-feedback-rlaif"></a>

### 第二阶段——AI反馈的RL(RLAIF)

生成一对完成。 “ 反馈模型” 将每个匹配的样本宪法原则。 首选信号是反馈模型的排名。 train a reward model AI 生成的优惠; PPO 其他的都是GPT的管道(第1条)。

"RLAIF" = 偏好信号是 AI 生成的。 rest 输油管的 RLHF-shaped.

<a id="why-this-is-not-just-cheaper-rlhf"></a>

### 为什么这不只是"更衣者" RLHF"

- 标签偏差从标签心理学转向原则解释。 人工智能标签可以比任何人更严格地解释“诚实 ” ; 数据集的严格性是相同的。
- 偏好信号是十分清晰的——你可以读取原则、批评和修改,人类标签是不透明的。
- 失败模式会改变。 交错式下降( AI 标签器没有用户可以使用 ) 。 古德哈特法( Goodhart Law) 仍然存在( 现在的代理是“ 模型对原则设置 X 的解释 ” , 仍然是不完善的测量 ) 。

CAI的2022索赔:经过培训的模式比CAI的 RLHF 模型具有可比数据。它存在于实验室各处。

<a id="the-2026-claude-constitution-rewrite"></a>

### 2026年 Claude 修改宪法

Anthropic 2026年1月21日公布了一项经过重大修订的宪法。

1. 解释性推理对规范性规则的解释性推理。 以前的规则(“ 不产生 CSAM ” ) 扩大到原则+推理 ( “ 因为它伤害儿童, ...... ”) , 并且模型有望被概括化 。
2. 四级优先结构:
   - 第1级:避免灾难性后果(伤亡人数、重要基础设施)。
   - 第2级: 接续 Anthropic指南(操作器重置、平台规则)。
   - 第3级:广义的道德(标准HHH)。
   - 4级: 帮助和坦率。
   冲突自上而下地解决。
3. 第一次大实验室正式承认对模范道德地位的不确定性(与阶段18 · 19 模范福利有关)。
4. CC01.0下释放。其他实验室可以不受限制地使用或改造。

<a id="constitutional-classifiers"></a>

### 宪法分类

平行的工作:培训轻量级人员,他们不改变模式的培训后训练,而是阅读宪法和门型输出。 v1 (2023) 计算间接费用的比例为23.7%. v2(2026) ~1%,是任何成功攻击率最低的。 Anthropic defense Anthropic 已经公开测试。 jailbreak 据报,截至2026年初。

这是一个多层次的防御模式:CAI塑造行为;分类者强制实施变数。 光是这一点是不够的。

<a id="where-cai-fits-in-the-family"></a>

### 家庭内部的CAI

- 人类预科,RM, PPO.
- CAI/RLAIF: AI 源自原则的预言, RM, PPO.
- DPO 家庭:前置(人或人工智能)的闭式损失。
- 自我奖励、自我批评:原则内在化、模式发挥多种作用。

轴线是“偏好信号来自何处”。 CAI 的2022年论文是首次从人类向人工信号的前沿信号。

```figure
constitutional-ai
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟玩具词汇中的 CAI 批评和审校循环。 “ 原则” 标记 tokens 初步反应,批评确定了有害因素 tokens,修改后将替换。在200次重复后,“经过训练的”模式将修订规则内部化。比较基本模式, RLHF- 形玩具,和CAI型玩具 悬置 prompt set.

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-constitution-writer.md`。如果有领域(客户支助、医疗咨询、编码助理、研究工具),则在2026年后起草一部4级宪法 Claude 结构:灾难避免、平台规则、领域道德、帮助。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`比较基本模型的有害 -token 访问率为 CAI 培训版本。 接近零需要多少次修改步骤 ?

2. Read Anthropic2026年宪法(第2条)anthropic.com/news/claudes列出一个第一级和第四级的原则,为什么优先结构对冲突很重要?

3. 设计一个AI 编码助理的章程。 请指定第1级( 灾难性: 未经批准而执行的破坏性命令) , 第2级、 第3级、 第4级, 将每一级保持在3-5项原则 。

4. CAI 将人类标签替换为 AI 标签。 命名一种在 RLAIF 中仍然可能发生的类似相残的失败模式, 并设计一个检测模式 。

5. 阅读宪法分类法 v2 (如果有的话)。 解释为什么~ 1% 计算间接费用是一个质量上不同于23. 7%的安全故事。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 宪法人工智能 | "AI 受原则训练" | 双阶段输油管:自修和再造 SFT,然后从AI反馈中检索到 |
| 罗拉IF | "RLHF 没有人类" | 使用AI标签师提供的优惠; rest 输油管没有变化 |
| Constitution | 原则 | 一份有顺序的自然语言列表, 用于评论/标签模式咨询 |
| Critique-and-revise | "该 SFT loop" | 根据一项原则提出答复 —— 修改 —— 。 SFT target |
| 宪法分类 | "输出门" | 参照宪法和块/行数评价产出的轻量级分类器 |
| 四级优先权 | 冲突解决者 | 2026 Claude 宪法等级:灾难性 > 平台 > 道德 > 有用 |
| 反馈模式 | "人工智能标签" | 读出原则并排出一对结业成绩的模型 |

<a id="further-reading"></a>

## 进一步阅读

- [Bai等人——宪法大赦国际:大赦国际反馈的无害性(arXiv:2212.08073)](https://arxiv.org/abs/2212.08073) 最初的两阶段输油管
- [Anthropic — Claude《宪法》(一九二零二六年)](https://www.anthropic.com/news/claudes-constitution) 2026年四层重写,CC01.0
- [Anthropic - 宪法分类(2024-2026年)](https://www.anthropic.com/research/constitutional-classifiers) -输出门防御,在 v2 中为~1%的顶部
- [Lee等人——《反种族歧视法》对立案 RLHF缩放 Reinforcement Learning 来源:人类反馈(arXiv:2309.00267)](https://arxiv.org/abs/2309.00267) 经验性拉加国际投资协议/ RLHF comparison
- [Kundu等人——《宪法独立法》的具体原则与一般原则(arXiv:2310.13798)](https://arxiv.org/abs/2310.13798) 原状颗粒效应
