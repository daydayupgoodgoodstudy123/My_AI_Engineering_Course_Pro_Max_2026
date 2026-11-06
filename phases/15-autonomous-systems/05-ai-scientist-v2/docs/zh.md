<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="ai-scientist-v2--workshop-level-autonomous-research"></a>

# AI Scientist v2：达到研讨会论文水平的自主研究

> Sakana的AI 科学家 v2(Yamada等人,ArXiv:2504.08066)运行整个研究循环:假设、代码、实验、数字、写作、提交。 这是第一个在2025年国际气候与土地研究中心讲习班上进行纸面通过同行审查的系统。 evaluation (Beel等人)发现42%的实验在编码错误中失败,文献审查经常误将既定概念标为小说。 Sakana自己的文件警告说代码库执行 LLM- 写代码和建议 Docker 两者都是关键

**类型:** 学习
**语言:** Python (Stdlib,研究圈州机玩具)
**先修要求:** 阶段15 · 03(阿尔法发展),阶段15 · 04(DGM)
**时间：** ~60 分钟

<a id="the-problem"></a>

## 问题

研究是一项没有限制的任务。 与阿尔法·埃弗洛夫的算法搜索或DGM基准自译自审不同,研究结果没有机器可检查的正确性标准。 论文由审查者而不是单位测试来判断。 这使得循环更难关闭 — — 如果关闭的话,则更有价值,因为研究是进步生活复合的地方。

AI 科学家 v1 (Sakana, 2024) 以人类版的模板为起点, 关闭了循环。 LLM AI 科学家 v2(Yamada等人,2025年)通过使用固定脚架进行实验,删除模板要求 agentic 树搜索 vision-language model 批评循环。 系统生成想法, 实施实验, 生成数字, 撰写论文, 并重复审查者的反馈 。

同行审议裁决:2025年国际劳工大会研讨会接受了一份 v2 产生的文件(披露)。 evaluation 判决:这个系统远非可靠,两者都是真实的。

<a id="the-concept"></a>

## 概念

<a id="the-architecture"></a>

### 架构

1. **理想的一代人。** 该 LLM 提出以专题和先前文献为条件的研究构想。 v1 使用的模板; v2 使用 agentic 寻找一个假想的空间。
2. **检查新奇。** 文献检索步骤检查该想法是否已经公布。 这是 Beel 等人的 evaluation 发现错误标签——既定方法经常被归类为新颖。
3. **实验计划** 该 agent 起草实验协议并撰写代码。
4. **Execution.** 代码运行于 sandbox。失败被反馈到一个重试循环中。在 Beel 等人的测量中,42%的实验在现阶段没有完成编码错误。
5. **图 数 代 代** 一个 vision-language model 读取生成的数字,并重写以清晰度。 这是 v2 的关键技术添加 。
6. **Writeup.** 该 LLM 起草一份文件,与内部审查员重复。
7. **任择:提交。** 该文件将提交给一个会议地点。

<a id="what-the-workshop-acceptance-result-means"></a>

### 研讨会的接受结果意味着什么

一份 v2 生成的纸在2025年ICLR研讨会上通过了同行评审。 作者向程序委员会披露了该纸的来源。 接受是一个数据点, 而不是要求系统“ 做研究” 的许可 。

重要背景:讲习班文件比主要会议文件低。 同行审议是吵闹的; 少数提交文件在任何特定日期都被接受。 一个成功就是概念证明,而不是可靠性主张。 大自然 2026 纸记录了端对端循环, 并且本身是由人类研究人员共同撰写的; 它不是“ 系统写了一份自然文件 ” 。

<a id="what-the-independent-evaluation-found"></a>

### 独立者 evaluation found

Beel等人(arXiv:2502.14297)经营外部 evaluation标题结论:

- **实验失败。** 42%的实验由于编码错误( 错误导入、 形状不匹配、 未定义变量) 失败。 重试循环捕捉到部分, 而不是全部 。
- **虚构的标签** 文献检索步骤经常将既定概念标为新颖。 hallucination.
- **列报质量差距。** 视觉语言的人物批评了出版级的视觉,掩盖了潜在的实验弱点。

最后一项发现是这一阶段的重要结果。 一个在不进行令人信服的研究的情况下产生令人信服的产出的系统比一个显然失败的系统更危险,而不是更安全。 Evaluation 必须达到相关的索赔要求,而不是停留在数字上。

<a id="the-sandbox-escape-concern"></a>

### 该 sandbox- 脱身问题

萨卡纳自己的仓库README警告:

> 由于软件的性质,它执行 LLM生成代码, 我们无法保证安全。 存在危险包、 不受控制的网络访问和意外过程的生成的风险。 使用您自己的风险并考虑 Docker isolation.

这是在未经核实的领域自治的操作形式。 LLM 写入代码; 代码运行; 代码可以做任何程序允许做的事情。 没有 sandbox 硬限制文件系统、网络和处理动作,任何自导研究 agent 能够将数据排出,燃烧计算,或重写自己。

AlphaEvolve's sandbox 故事比较简单,因为其评估员很紧。 AI 科学家 v2 的循环运行着开放式代码,目标不限。 这就是为什么它需要更紧密的孤立( ) ( )Docker 最低; 偏向于分包/ g Visor),并在每次提交材料离开系统之前对其进行人工审查。

<a id="where-v2-sits-in-the-frontier-stack"></a>

### 边疆堆放 v2 的堆放位置

| 系统 | 目标 | 产出类型 | Evaluator | 已知失败 |
|---|---|---|---|---|
| AlphaEvolve | algorithms | code | 单位+基准 | 受评价员的严格约束 |
| DGM | agent scaffolding | code | SWE-bench | 奖励黑客 |
| AI 科学家 v2 | 研究论文 | 文本+代码+图 | 同行审查(弱) | 实验失败、 标签错误、 抛光遮蔽弱点 |

v2 具有三个最大输出表面的最弱自动评价器, 以及最短的公用文物路径。 操作控制( )sandbox),审查、披露)正在做大部分安全工作。

```figure
mx-research-loop
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 将 v2 循环模拟为状态机器: 想法 + 新建检查 + 号 + 号 = 表示 + 号 + 接受 或 语气 。 每个州都有一个从 Beel 等人的发现中提取的可配置失败概率。 运行 N 循环和计算模拟器 :

- 有多少想法达到了屈服。
- 有多少份呈文会有一个关键的实验缺陷 擦拭的纸皮。
- How retry budgets 质量与产量之间的差额。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-ai-scientist-sandbox-review.md` 是一个研究圈所制作的两关审查清单 agent 趁它离开之前 sandbox.

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 默认 parameters。循环运行的哪一部分产生“干净”纸?什么部分产生带有实验失败缺陷的纸,被擦过的数字?

2. 默认值已经使用 Beel 等人的 42% / 25%。 重运行 `--experiment-failure 0.20 --novelty-mislabel 0.10` 和与 `--experiment-failure 0.60 --novelty-mislabel 0.40`。两个运行之间如何进行光滑但固定的共享转换?

3. 读莎卡娜的AI 科学家 v2 重新读取 README on sandbox 说明两项附加限制(超出 Docker您将申请多天自动运行 。

4. 阅读Beel等人,关于表述质量差距的第4节,设计另外一名评价员,以掌握表面印刷但实验性有缺陷的论文。

5. 提议一项人类审查程序 用于研究agent 显示一个瓶颈和设计。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| AI 科学家 v1 | "萨卡娜的模板研究 agent" | 填充的实验进入固定的脚架 |
| AI 科学家 v2 | "无板研究 agent" | Agentic 使用 VLM 图形评析搜索树 |
| Agentic 树搜索 | "破碎的研究 agent" | 平行扩展多个实验计划; 通过内部处理 critic |
| 愿景语言评论 | "数字上的VLM抛光" | Multimodal model 读取数字,并重写它们以清晰度 |
| 文学检索 | 检查 | 工作前搜索以确认新理念——记录为错误标签 |
| 波兰面具 | 漂亮的纸,破碎的研究 | 演示文稿质量超过实验质量; 隐藏弱点 |
| Sandbox escape | "LLM 代码破解 | Agent- 执行代码, 环形设计师没有的意图 |

<a id="further-reading"></a>

## 进一步阅读

- [Yamada等人(2025年)。](https://arxiv.org/abs/2504.08066) - 纸。
- [萨卡纳博客《大自然》2026年出版物](https://sakana.ai/ai-scientist-nature/) 供应商摘要,带有同行审查背景。
- [Beel等人(2025年)。 evaluation 科学家协会](https://arxiv.org/abs/2502.14297) 外部 evaluation numbers.
- [Sakana AI 科学家 v1 论文](https://arxiv.org/abs/2408.06292) - 模板上的前任。
- [Anthropic 衡量大赦国际 agent autonomy](https://www.anthropic.com/research/measuring-agent-autonomy) 扩大开放式研究的范围 agents.
