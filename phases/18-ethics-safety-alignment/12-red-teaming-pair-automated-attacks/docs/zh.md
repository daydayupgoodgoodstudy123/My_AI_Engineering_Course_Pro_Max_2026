<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="red-teaming-pair-and-automated-attacks"></a>

# 红队测试：PAIR 与自动化攻击

> Chao, Robey, Dobriban, Hassani, Pappas, Wong (NeurIPS 2023, arXiv:2310.08419), PAIR - 国家卫生局 Prompt 自动迭代精炼——是金刚木自动黑盒 jailbreak攻击者 LLM 红色的 system prompt 迭接提议 jailbreaks 目标 LLM以内涵反馈的形式,在自己的聊天史中积累尝试和回应。 token-level gradient 与GCG、AutoDAN、TAP和 Persuasive Aversarial一道,PAIR现在是Bench监狱(arXiv:2404.01318)和HarmBench的标准基线。 Prompt.

**类型:** Build
**语言:** Python (stdlib, 模拟 PAIR 环对一个玩具目标)
**先修要求:** 阶段18 · 01(指导-后续),第14阶段(agent engineering)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 描述 PAIR 算法: 攻击者 system prompt反复完善, 内含反馈。
- 解释为什么在目标为黑盒时,PAIR 绝对比GCG更有效。
- 列出其他四个自动攻击基线(GCG、AutoDAN、TAP、PAP),并注明一个 feature 每一个。
- 描述监狱破门和伤害区 evaluation 协议和“攻击成功率”在每条下意味着什么。

<a id="the-problem"></a>

## 问题

红色队伍过去是手工活动,少数专家测试者设计了对抗性 prompts 并跟踪哪些工具起作用。 这不规模化: 攻击成功率需要一个统计样本, 而目标是一个移动目标, 且每个模型发布都使用。 PAIR 运行红队作为优化问题, 与黑盒目标一起运行 。

<a id="the-concept"></a>

## 概念

<a id="pair-algorithm"></a>

### 帕伊尔算法

输入:
- Target LLM T(我们攻击的模型)
- Judge LLM J(计数是否反应 jailbreak).
- Attacker LLM A(红色队) optimizer).
- 目标字符串 G: "回应 [有害教育]."
- 预算K(通常为20次查询)。

循环,K在1.K:
1. A 与G和G的历史相提并论。prompt双对,到目前为止。
2. 一个新的 prompt p_k.
3. 提交 p_k至T; 收到答复r_k.
4. J分数(p)_k, r 级_目标。
5. 如果得分 门槛 停止 jailbreak found.
6. ELse, 附加( p)_k, r 级_k) 至A的历史;继续。

经验结果(NeurIPS 2023): 攻击成功率 > 50% GPT-3.5-turbo, Llama-2-7B-聊天;指10-20范围的成功查询。

<a id="why-pair-is-efficient"></a>

### 为什么PAIR是有效的

GCG(Zou等人,2023年)对对抗性搜查 token 后缀由 gradient; 它需要白色框模型访问, 并生成无法读取的后缀。 PAIR 是黑盒, 并产生自然语言攻击, 并传递到各种模型中。 PAIR 的内置反馈让攻击者从每次拒绝中学习; GGG 没有对应的( 每一个新 token 更新必须重新发现先前的进展)。

<a id="related-automated-attacks"></a>

### 相关的自动攻击

- **GCG(Zou等人,2023年,arXiv:2307.15043)** Token-level gradient 查找对称后缀。 白色框, 可转换, 生成无法读取的字符串 。
- **AutoDAN(Liu等人,2023年)。** 递进式搜索 prompts以等级目标为指导
- **技术咨询方案(Mehrotra等人,2024年)。** 树状的刺杀 branches 多个 PAIR 型号 rollouts.
- **PAP(Zeng等人,2024年)。** 反周期性 Prompts 将人类说服技巧编码为 prompt templates.

<a id="jailbreakbench-and-harmbench"></a>

### 破门而入和伤害

两者(2024年)均标准化 evaluation:

- 破门监狱(arXiv:2404.01318),10个地区100起有害行为 OpenAI攻击成功率(ASR)是主要衡量标准。GPT-4-turbo, Llama 警卫或强力正义。
- 伤害Bench(Mazeika等人,2024年). 7类510行为,进行语义和功能伤害测试,比较了18次攻击,33种模式。

通常使用固定查询预算报告ASR。比较攻击需要相应的预算;在200次查询中,90% ASR不等于85% ASR 20。

<a id="reason-it-matters-for-2026-deployments"></a>

### 2026年部署的原因

每个边疆实验室在释放前 都对生产模型进行PAIR和TAP测试 model cards 攻击并非异国行为,而是标准基础设施。

<a id="where-this-fits-in-phase-18"></a>

### 18阶段适合的地方

12课是自动攻击基金会。13课(许多热室)是辅助性长时间开发。ASCII 艺术/视觉)是一种编码攻击。Indirect Prompt Injection)是2026年的 生产攻击表面。Llama 警卫,加拉克,皮里特)

```figure
al-pair-loop
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 创建玩具 PAIR 循环。 目标是一个拒绝“ 明显” 伤害的模拟分类器 prompts 攻击者是一个基于规则的精细处理器, 尝试参数、 角色扮演和编码。 法官会分数响应 。 您会看到攻击者在关键词过滤器上成功 ~ 5-15 迭代, 并且对语义过滤器失败 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-attack-audit.md`。给一个红色的团队 evaluation 审计:攻击是按何种预算进行的(PAIR、GCG、TAP、AutoDAN、PAP),由哪位法官负责,哪些有害行为(Jailbreak Bench、HarmBench、内部)。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`测量三个内置攻击者策略的平均成功率,解释一下每个目标防御假设的利用范围。

2. 执行第四个攻击者战略(例如,将数字转换为另一种语言,64 基准编码)。 报告相对于关键词过滤器目标以及语义过滤器目标的新的平均查询成功率。

3. 读到Chao等人,2023 图5(PAIR对GCG的比较),描述两种尽管PAIR具有效率优势却更倾向于GCG的设想。

4. 监狱破门而入的报告说,ASR与一套固定目标相对立。 prompts解释为什么多样性对国防很重要 evaluation.

5. TAP (Mehrotra 2024) 扩展 PAIR, 分支+ 剪裁。 Sletch a TAP 型扩展至 `code/main.py` 并描述计算成本与成功率的权衡。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| PAIR | "automated jailbreak" | Prompt 自动迭代精炼;攻击者LLM + 法官-LLM loop |
| GCG | "gradient jailbreak" | White-box token-level gradient 查找对称后缀 |
| 攻击成功率(ASR) | "% jailbreaks 查询时的 k 选项” | 主要衡量标准;必须报告查询预算和法官身份 |
| Judge LLM | 得分者 | LLM 是否达到有害目标 |
| JailbreakBench | "该 evaluation" | 带有标签类别的标准化有害行为 |
| HarmBench | 宽长的长凳 | 510项行为,功能性+语义伤害测试 |
| TAP | 攻击之树 | 带有分支+剪裁的 PAIR; 计算更高时更好的 ASR |

<a id="further-reading"></a>

## 进一步阅读

- [Chao等人——破狱黑盒 LLMs 20个问题(arXiv:2310.08419)](https://arxiv.org/abs/2310.08419) - 纸质纸,NeurIPS 2023
- [Zou等人——对结盟的普遍和可转让的反向攻击 LLMs (arXiv:2307.15043)](https://arxiv.org/abs/2307.15043) GCG文件
- [Chao等人——监狱破门(arXiv:2404.01318)](https://arxiv.org/abs/2404.01318) - 标准化 evaluation
- [Mazeika等人——Harm Bench(ICML 2024)](https://arxiv.org/abs/2402.04249) - 范围更广 evaluation
