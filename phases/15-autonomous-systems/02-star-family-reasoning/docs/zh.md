<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="star-v-star-quiet-star--self-taught-reasoning"></a>

# STaR、V-STaR、Quiet-STaR：自学推理

> 最小的自我改进循环就位于理论原理之内。 chain of thought,让那些有正确答案的人保持清醒,并精细地调整这些答案。 inference- 时间选择更好。 静静的STaR将理由推到每一个 token三个工作,没有一个是魔法——环能保留任何碰巧达到正确答案的捷径。

**类型：**学习
**语言:** Python (stdlib,靴圈模拟器)
**先修要求:** 阶段13 · 01-03(重新定位和计算),阶段15 · 01(长方位设置)
**时间：** ~60 分钟

<a id="the-problem"></a>

## 问题

教模型理性的简单方法 就是收集人类的推理 traces。这代价昂贵,缓慢,而且与质量如何挂钩 chain-of-thought 人类愿意写作

STaR(自学理性者,Zelikman等人,2022年)问:如果模型根据已知答案写出自己的理论原理和等级呢?

1. 举例说明 trace 加上答案 回答我的问题
2. 如果最后答案正确,请保留 trace.
3. 保持精细的音调 traces.
4. 重复。

它起作用了。 GSM8K 和 CompensenseQA 都得到了改进,没有新的人类说明。 但循环中有一个内在的偏差:任何产生正确答案的理由都保留下来,不管推理本身是否合理。 patches 静默STaR (Zelikman等人,2024年) 将这一想法概括为每-token 内部理由。

<a id="the-concept"></a>

## 概念

<a id="star-bootstrap-on-what-worked"></a>

### STAR: 有关什么有效的靴子

从一个基础模型开始, 推理能力比较弱。 对于每个训练问题, 请对原理和答案进行抽样。 如果答案与标签相符, 请保持三重( 问题、 原理、 答案) 。 精细调整模型在保留设置上的位置 。 重复 。

扭曲很重要。 如果模型永远无法找到问题, 循环无法学习它。 STaR 添加 **rationalization**: 对于模式失败的问题, 请输入正确的答案作为提示并重覆 --prompt 模型可以产生一个引出它的理由。

原始文件的结果(Zelikman等人,2022年):a GPT- JGSM8K的基准模型通过重复的STAR回合(合理化)从5.8%改进到10.7%——绝对约为5个百分点。 GPT-J6B达到72.5%,相当于微调 GPT3 175B(~73%)——大约30x个较大的模型,受过手语说明理由的训练。

<a id="v-star-train-a-verifier-with-dpo"></a>

### V-STaR: 培训核查员 DPO

STaR 丢弃了不正确的原理。 Hosseini等人 (2024年) 观察到这些数据也是: 每对( 原义, “ 正确无误 ” ) 都可以训练校验者。 他们使用直接偏好优化方法来构建一个排行器。 在 STaR 中, 使用直接偏好来匹配正确和错误的解决方案 。 inference 时间,样本N的理由 并选择验证人的首选。

报告的三角洲:GSM8K和MATH上比先前的自我改进基线高出4至17个百分点,大部分收益来自使用核查器 inference- 时间选择,而不是增加发电机 fine-tuning.

<a id="quiet-star-per-token-internal-rationales"></a>

### 静静的STAR: 每 -token 内部理由

Zelikman等人(2024年)问:如果模型能够产生一个简短的内部理由,那么它会有什么效果? token 位置, 不只是问题和答案之间? 静静的STaR 训练模型在每次预测前发出隐藏的“ 想法” token,然后通过学习将思维意识预测与基线预测结合起来 weight.

结果: Mistral 7B获得绝对数 zero-shot 将8K通用标准从5.9%提高到10.9%,将36.3%提高到47.2%,没有具体任务 fine-tuning模型学会了"何时思考"- tokens 获得较长的内部理由;容易得到几乎没有。

<a id="why-all-three-share-a-safety-concern"></a>

### 为什么三个人都关心安全问题

所有三种方法都使用最后答案作为 gradient 信号:通过错误的推理——利用捷径、猜测或使用非普遍化模式——找到正确答案的理由得到积极加强,在分配过程中遇到问题,捷径起作用,在分配之外出现问题,它默默地打破。

V-STaR 的校验程序通过学习排序理由来减轻了影响, 但校验程序在相同的标签组上得到了培训。 它可以学会选择格式化错误的推理而不是诚实的不确定性。 更安全的设计是将STaR 型的数据与 (a) 进程监督的数据结合起来 reward models (奖励中间步骤,而不仅仅是回答)和(b) 暂停使用OOD evaluation 打破了简单的捷径。

<a id="comparison"></a>

### 比较

| 方法 | 培训信号 | Inference 成本 | 数据废物 | 已知失败模式 |
|---|---|---|---|---|
| STaR | 保留( 直截了当, 回答) : | 1个x | 丢弃所有不正确的理由 | 快捷键理由 |
| STaR+合理化 | + 正确回答提示重试 | 1个x | less | 合理的理由可能难以相信 |
| V-STaR | STAR+ 高级 DPO 两个班级的核查员 | Nx(最佳) | minimal | 核查员可以 reinforce 自信的错误 |
| Quiet-STaR | per-token 理由+混合 weight | 1.5-3x | minimal | 仍然有回答条件 gradient |

<a id="where-this-sits-in-the-2026-stack"></a>

### 2026年的堆放点

STaR已经过时。 但2025-2026年,这种模式又到处出现。 关于可核查的数学问题( RL) (RL) 。DeepSeek-R1,Kimi-k1.5,o1,是STaR的回答条件 gradient 信号, 缩放。 process reward models (Lightman等人,2023年; OpenAI“ 我们一步一步地核查” 是进程监督的替代方法。 AlphaEvollve (Lesson 3) 是 STaR 代码, 使用程序评价器而不是标签。 达尔文 Godel Machine (Lesson 4) 是 STaR 。 agent 脚架自己。

理解STaR 使所有这些点击。 这是最小的自我改进循环 。

```figure
reflection-loop
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 在玩具计算任务上运行模拟的 STAR 循环。 您可以查看 :

- 精度如何攀升 超过靴子套子弹。
- 快捷键如何悄悄地进入: 模拟器包括一个“ 懒惰” 的理论类, 它得到40%的时间的正确答案, 但一般化得非常差。 看 STaR 是否保存它们 。
- 验证器( V- StaR 样式) 如何帮助 inference 但不完全切换培训中引入的快捷键 。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-star-loop-reviewer.md` 帮助您在培训前审核一个自学管道。

<a id="exercises"></a>

## 练习

1. 运行模拟器。 将快捷键频率设为零, 然后设定为0. 4。 两次运行之间最后精确度有多大差异, 尽管在培训分布中都击中了 > 90% ?

2. 向模拟器添加缓存 OOD 测试。 从不同的分布中绘制问题, 并评估分布和 OOD 组的套件模式。 量化空白 。

3. 读读静默STaR纸(arXiv:2403.09629),第3节解释“思考的终结” token 与混合的,weight 头部每句三句。

4. 比较STaR 的保存错误过滤器, 以独立地奖励每个理由步骤的受进程监督的替代工具。 确定标签成本差异和可能的质量差异 。

5. 设计一 evaluation 它可以在部署的模型中捕捉快捷键原理。 它不必是完美的—— 它必须打破最简单的快捷键 STAR 环会 reinforce.

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| STaR | "自学的理性" | 精细调整模型产生的正确答案的原理; 重复 |
| Rationalization | "深吸一试" | 输入正确的答案并重写prompt 基本模型失败的原因 |
| V-STaR | "变异体STAR" | DPO- 训练核查员,核查正确和不正确的原理,用于 inference- 时间选择 |
| Quiet-STaR | "每-token rationales" | 生成隐藏的思想 token 位置; 与基线预测相混合 |
| Answer-conditioned gradient | 以结果为基础的信号 | 训练循环奖励最终答案,而不是推理步骤 |
| Process reward model | "标准级核查员" | Reward model 培训有关每一步骤的正确性,而不是结果——与STaR的对比 |
| 快捷键理由 | "正确答案,错误的推理" | 通过非普及模式到达标签的理由;STaR保留这些 |

<a id="further-reading"></a>

## 进一步阅读

- [Zelikman等人(2022年),STaR:有理的诱导理由](https://arxiv.org/abs/2203.14465) - 原始文件。
- [Hosseini等人(2024年)。 V-STaR:自学推理师培训验证员](https://arxiv.org/abs/2402.06457) - 增加 DPO 核查员 inference- 时间选择。
- [Zelikman等人(2024年),静默-STaR:语言模型可以教自己在说话前思考。](https://arxiv.org/abs/2403.09629) — 每-token 内部理由。
- [Lightman等人(2023年)。让我们一步一步地核查](https://arxiv.org/abs/2305.20050) 过程 reward models,则选择 gradient signal.
- [DeepSeek-R1纸(arXiv:2501.12948)](https://arxiv.org/abs/2501.12948) - 核查任务,STaR升级为边境培训。
