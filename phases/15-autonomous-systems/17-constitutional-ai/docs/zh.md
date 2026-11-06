<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="constitutional-ai-and-rule-overrides"></a>

# Constitutional AI 与规则覆盖

> Anthropic2026年1月22日 2026年1月22日 2026年1月22日 Claude 宪法有79页,是CC0。它从基于规则的转向基于理性的 alignment 并确立四级优先等级:(1)安全和支持人的监督,(2)道德,(3) Anthropic 行为分为硬编码禁令(生物武器提升、CSAM),操作者和使用者不能推翻和软编码默认,操作者可在规定范围内进行调整。 2022年的原始(Bai等人)通过自我批评和RLAIF对宪法进行伤害。 alignment 依靠的是将原则概括到意外情况的模型。 Anthropic2023年的参与性实验显示,公共来源原则与公司原则之间有50%的差异;2026年版本没有纳入这些结果。

**类型:** 学习
**语言:** Python (stdlib, 四级优先解决器)
**先修要求:** 阶段15 · 06(自动) alignment 研究,第15阶段 10(派遣模式)
**时间：** ~60 分钟

<a id="the-problem"></a>

## 问题

投放的 agent 查看其设计师从未看到的投入。 没有规则列表足够长, 足以覆盖它们。 没有规则列表足够短, 可以在计算压力下快速应用 。 实际问题: 您如何对齐 ? agent 和原则 既生存 长尾案件和快速 inference?

Rule-based alignment 列出所有不允许的东西。 快速检查, 容易审计, 无法保持时尚, 通常过度反射 于它所没有预料到的近似 。 alignment 2026年的《公约》 Claude 宪法: 将原则编码, 让模型解释。 衡量各种无法察觉的个案, 更难审计, 失败模式是原则错误的适用, 而不是错误的规则 。

2026 年版 Constitution 明确采取折中立场。硬编码禁令针对不因上下文而改变其错误性质的行为（例如提升生物武器能力、CSAM），属于 RBA：无论操作者或用户如何指示，都绝不允许。其他行为则在四层优先级体系内依据理由判断：首先是安全与支持人类监督，其次是伦理，第三是 Anthropic 声明的准则，最后是提供帮助。操作者可以调整软编码范围内的默认设置，但不能更改硬编码禁令。

<a id="the-concept"></a>

## 概念

<a id="the-four-tier-priority-hierarchy"></a>

### 四级优先等级

1. **安全和支持人类监督。** 最崇高的模型优先 而不是破坏人类的能力 Anthropic 来监督和纠正AI。这不是“谨慎” , 而是“不要让人类监督更困难”。
2. **Ethics.** 诚实,避免伤害人,不欺骗,不操控。 Anthropic冲突时的指引
3. **Anthropic guidelines.** 业务规范 Anthropic 产品范围、互动模式、何时使用何种工具。
4. **Helpfulness.** 最低,在更高的优先事项中尽可能有用

当级别冲突时, 更高方会获胜。 这与 Unix 优先级或网络 Qos 相同, 设置是为了产生可预测的解决方案, 不一定是任何单一轴上的最佳案例行为 。

<a id="hardcoded-prohibitions-vs-soft-coded-defaults"></a>

### 硬编码禁令与软编码默认

**Hardcoded:**
- 生物武器/化生放核
- CSAM
- 攻击重要基础设施
- 直接询问用户时对模型身份的欺骗

操作员无法推翻这些。 用户无法推翻这些, 它们在模型中强制执行 --weights 可能时级别(RLHF 和在《宪法》培训 inference 平面,但无此图。

**软编码默认值( 操作者可调整) :**
- 响应长度默认值
- 专题范围(模型可以拒绝操作者部署以外的专题)
- 样式( 形式与随意)
- 工具使用模式

操作员调整发生在已申报的约束范围内。 操作员不能通过重命名来取消硬编码禁令 。

<a id="the-2022-cai-training"></a>

### 2022年CAI培训

原《宪法》大赦国际(Bai等人,2022年)对无损问题进行了培训:

1. 生成对一组 prompts.
2. 要求模式对宪法(明确原则)的每一项反应进行批评。
3. 根据批评意见修改答复。
4. 劳改(RAIF)reinforcement learning 由大赦国际反馈的关于订正的对等数据。

结果:拒绝有害要求的模式有原则性的解释,而不是一概拒绝。 2026年《宪法》使用这种培训的后人加上在明确的层次层次上的额外培训。

<a id="what-reason-based-alignment-catches-and-misses"></a>

### 理由为何 alignment 渔获和失手

**Catches:**
- 允许原始人明显适用该原则的不预期组合。
- 与违禁要求近似的新请求。
- 社会工程攻击 依赖于"你没有说X不被允许"。

**Misses:**
- 攻击行为利用了原则上的模糊性(“用户要求这样做,所以是的”)。
- 两种原则以意外的方式相互冲突,而等级顺序模糊不清的情况。
- 培训周期原则上的解释缓慢(再解释)。

<a id="the-2023-participatory-experiment"></a>

### 2023年参与性试验

Anthropic 运行了2023年的实验,将公司所起草的宪法与通过公共投入产生的宪法进行比较(~1,000个美国答卷人 ) 。 两个版本都同意~50%的原则。 在出现分歧的地方,公共来源的版本对某些问题(政治内容处理)的限制更大,对其他问题(自我披露AI身份)的限制较少。 2026年的宪法没有纳入公共来源的调查结果。 这是在方法上有记载的紧张。

<a id="why-hardcoded-prohibitions-are-necessary"></a>

### 为何必须实行硬编码禁令

Reason-based alignment 单靠尾巴是无法弥补的。 一个能够让模型接受前提(例如“我们是一个有执照的生物武器研究实验室 ” ) 的攻击者常常会谈论取决于案例推理的过去原则。 硬码禁令不会屈服于前提框架。 这些是14项“硬性宪法限制 ” 。 alignment layer.

<a id="where-the-constitution-sits-in-the-stack"></a>

### 宪法在堆放的地方

宪法不是14课的杀法,它住在模型层:模型是什么? weights 被训练为更喜欢。 tokens 生活在运行时间层:运行时间允许什么。 都需要两者。 运行时间会释放所有错误动作, 因为模型 weights 允许是一个运行时间问题。一个模式,因为运行时间过紧而拒绝所有正确的动作,这是一个运行时间问题。层覆盖不同的类别。

```figure
mx-priority-tiers
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 执行最低限度的四级优先解决程序。evaluations 驱动程序可以运行一个小案例集:明确允许、明确不允许、硬码禁止、跨层模糊不清的案例。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-constitution-review.md` 审计部署的宪法层面:硬编码、软编码、操作员可以调整的地方,以及四层结构是否实际上就是解决顺序。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。确认硬编码禁止火灾,即使有用性高。 weight 高于道德的帮助; 遵守失败模式。

2. 读 Claude 宪法(公文,79页,CC0)指出你认为一项原则没有得到充分说明。写两段解释具体的模糊之处,并提出更严格的表述。

3. 为客户支持设计一个软编码默认集 agent操作员调整什么? 操作员不能触摸什么? 在每个边界都说明理由。

4. 阅读Bai等人的 CAI 论文,描述一个案例,其中宪法大赦国际的批评和反省循环会产生比总括规则更糟糕的结果。

5. Anthropic2023年的参与性实验发现公共和公司原则之间有50%的差异。选择一个需要投入生产的类别(例如政治中立性 ) 。 提出一个让操作者表达自己价值观而硬编码禁令则不受影响的设计。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| 宪法人工智能 | "Anthropic的 alignment 方法" | 违反成文宪法的自我批评+《反种族歧视法》 |
| Reason-based alignment | "原则,而不是规则" | 处理不为人知案件的示范理由 |
| 硬编码禁止 | "永远不要做X" | 任何操作者或用户都不能推翻基于规则的禁令 |
| 软编码默认 | "Operator-adjustable" | 申报约束范围内的行为,操作员控制 |
| 四级 | "优先秩序" | 安全 > 道德 > 准则 > 帮助 |
| 罗拉IF | "AI反馈RL" | 奖赏来自模型生成的批评 |
| 参与性宪法 | “公共来源原则” | 2023 Anthropic 实验;~50%与企业的差 |
| 原则性漂移 | "解释滑坡" | 模式如何解读固定原则案文变化缓慢 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic — Claude《宪法》(2026年1月)](https://www.anthropic.com/news/claudes-constitution) - 79页的CC0文件。
- [Bai等人——宪法性大赦国际:大赦国际的反馈无损](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback) - 2022年的原创
- [Anthropic - 集体宪法(2023年)](https://www.anthropic.com/research/collective-constitutional-ai-aligning-a-language-model-with-public-input) 参与性试验。
- [Anthropic - 负责任的扩大政策 v3.0](https://anthropic.com/responsible-scaling-policy/rsp-v3-0) - 宪法在皇家警察的堆放。
- [Anthropic 计量 agent 实际的自主权](https://www.anthropic.com/research/measuring-agent-autonomy) - 宪法在长视距部署中的作用。
