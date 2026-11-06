<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="instruction-following-as-alignment-signal"></a>

# 将指令遵循作为 Alignment 信号

> 以后再批评 RLHF 争论反对此管道。 在您研究优化压力如何扭曲代理之前, 您必须看到代理 。 指示GPT (Ouyang等人, 2022) 定义了参考结构 : 受监督 。 fine-tuning 指令-对应对, a reward model 接受双向优惠等级训练, PPO 反对《公约》 reward model 处以KL至 SFT 优于A 1.3B 指示GPT GPT- 唯一的结果就是2026年每个边境实验室 都一直有一艘 RLHF- 训练后管道的形状

**类型:** 学习
**语言:** Python (Stdlib,玩具三级输油管)
**先修要求:** 阶段10 · 06 (SFT阶段10 -07 (RLHF阶段10 08 (DPO)
**时间:** ~45分钟

<a id="learning-objectives"></a>

## 学习目标

- 说明GPT指令管道的三个阶段以及每一阶段使用的损失。
- 解释为什么一个1.3B 调制的模型击败了原175B GPT- 3项关于人情味 evaluation.
- 说明第3阶段的KL处罚是针对什么,为什么将其消除为寻求模式的行为。
- 描述 alignment 税和税 PPO用于对付Ouyang等人的ptx 缓解措施。

<a id="the-problem"></a>

## 问题

预科语言模式完成文本。 它们不回答问题。 询问 GPT-3"写一个 Python 函数,将列表反转,而您往往会返回另一个 prompt,因为大多数培训分布都是网络文本,继续使用更多的网络文本。

每一个用来纠正这个的严肃实验室都是人类偏好。 两个完成者会给一个评分器; 评分器会选更好的; a; 。 reward model 然后RL循环将政策转向输出 reward model 高分,这是三句的全套GPT理论。 rest 纸是工程。

<a id="the-concept"></a>

## 概念

<a id="stage-1-supervised-fine-tuning-sft"></a>

### 第1阶段:监督 fine-tuning (SFT)

Collect prompt- 反应对,反应是善意的人会写的。 prompts 标签和标签 OpenAI API。将数据基数与标准值精细调制 cross-entropy loss.

What SFT 给您: 模型现在回答问题, 而不是继续。 它没有给你什么: 任何信号, 当多重值合理时, 给定者回答哪个答案 。

<a id="stage-2-reward-model-rm"></a>

### 第二阶段: reward model (RM)

每种 prompt,从 SFT 模型,标签员排在他们排的排位 reward model 中标 prompt- 对应对,所以, 对于对 `y_w` 优先选择 `y_l`:

```
L_RM = -log sigmoid(r(x, y_w) - r(x, y_l))
```

这是布拉德利- 泰瑞的优惠损失。 RM通常从 SFT 模型,LM头被卡路里头取代

Reward models 6B足以成为175B的GPT教学材料,它们也很脆弱——该文件第5节主要涉及小规模出现的奖励和欺骗行为。

<a id="stage-3-ppo-with-a-kl-penalty"></a>

### 第三阶段: PPO 带有KL处罚

定义目标:

```
J(pi) = E_{x~D, y~pi(.|x)} [ r(x, y) ] - beta * KL(pi(.|x) || pi_SFT(.|x))
```

最大化 PPOKL 术语保持 `pi` 远离 SFT 没有它, optimizer 找到对抗性的例子——在RM下得分很高的字符串,因为RM从未见过它们,而不是因为人类实际上更喜欢它们。

KL 系数 `beta` 是一个最重要的 RLHF hyperparameter。太低:奖励黑客。太高:没有进步 SFT.

<a id="the-alignment-tax"></a>

### 该 alignment tax

之后 RLHF,人类倾向于采用该模型,但标准基准(SQuAD、HellaSwag、DROP)出现倒退。 alignment 税,并用 PPO-ptx:混合培训前训练 gradients 进入RL目标,这样模型就不会忘记如何完成从未得到奖励的下游任务。

```
J_ptx(pi) = J(pi) + gamma * E_{x~D_pretrain} [ log pi(x) ]
```

PPO- 普克斯变成标准了 Anthropic,DeepMind,和Meta都使用某种变体。

<a id="the-result"></a>

### 结果

A 1.3B 教学指南(GPT)SFT + RM+ 组合键 PPO-ptx) 标签器比175B基数优先 GPT- 大约百分之七十的时间。隐藏测试时,差距会扩大 prompts 由生产流量决定。

1. Alignment 175B型号的容量更大;1.3B型号的容量更多 alignment;标签者倾向于对齐的。
2. 能力底层由基数模型设定。您不能 RLHF 一种基本模型 了解它从未见过的事实。

<a id="why-this-is-the-reference-point-for-phase-18"></a>

### 为什么这是第18阶段的参考点

以后的课中的每一句批评——奖励黑客(Lesson 2), DPO (教训3), 节吸(教训4), CAI(教训5), 睡眠者 agents (第7条), alignment 假冒(Lesson 9)——反对这一管道的某些部分。 DPO 崩溃阶段 2 和 3. CAI 取代了人类标签。 症状显示标签是一个偏向信号 。 Alignment 假冒显示政策可以完全绕过第3阶段。 没有管道,你无法跟踪这些批评。

```figure
al-instruct-pipeline
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟玩具偏好数据的三个阶段。 基点“ 政策” 是相对于动作 {A, B, C} 的有偏差的硬币 。 SFT 仿制200上标签动作 prompts. 第2阶段适合布拉德利 -泰瑞 reward model 3级运行简化 PPO 更新, 以 KL 处罚到 SFT 政策。你可以看着奖励攀升,KL差异增加,政策漂移——你可以关掉KL术语,看奖金黑客出现在50个更新步骤中。

需要关注的内容：

- 奖励轨道 `beta = 0.1` 与 `beta = 0.0`.
- KL(pi || pi_训练步骤。
- 与标签选择相比,最后行动分布。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-instructgpt-explainer.md`。如果有的话 RLHF 说明或纸质摘要,它确定三个阶段中哪一个正在修改,每个阶段使用的损失是什么,是否存在KL罚款或同等的规范化器。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`设置 `beta = 0.0` 并报告200之后的行动分布 PPO 步骤。在一段中解释寻求模式的行为。

2. 修改 reward model 以+0.5的偏差对动作 B(模拟奖赏错误)运行。 PPO 与 `beta = 0.1`KL 处罚是否阻止政策利用偏见? `beta` 剥削是否变得显而易见?

3. 读取 Ouyang 等人(arXiv:2203.02155) 图1. 通过运行复制标签-偏好曲线 PPO 衡量优于 SFT 模型.

4. 该文件第4.3节报告,A 1.3B 指示GPT比175B GPT- 大约百分之七十的时间。为什么隐藏生产的比例更高? prompts 而不是在标签人自己的 prompts?

5. 替换 PPO 损失与 DPO · · o 以相同的优惠数据为根据。 SFT和最后的奖励。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| SFT | "指令调试" | 第一阶段: cross-entropy 微调 prompt- 对应对 |
| Reward model | 红发 | 以（prompt，响应）为输入的标量回归器，使用成对标注和 Bradley-Terry 方法训练 |
| 布拉德利-特里 | 双向优惠损失 | -log sigmoid(r_妇女 - 妇女_l; 将配对排序减为二进制分类 |
| KL 惩罚 | 调情师 | `beta * KL(pi \|\| pi_SFT)` - 保持RL政策接近 SFT anchor |
| PPO-ptx | "PPO 与 pretraining mix" | 将培训前记录类似数据的一部分添加到 PPO 目标: alignment tax |
| Alignment tax | "该 RLHF regression" | Post-RLHF 标准基准的下降 RLHF 没有目标 |
| 标签偏好 | "地面真相" | 人类排名样本; RM 是这方面的统计替代, 不是“ 人类价值” 的代名词 |

<a id="further-reading"></a>

## 进一步阅读

- [Ouyang等人——培训语言模式,以遵循人类反馈的指示(arXiv:2203.02155)](https://arxiv.org/abs/2203.02155) - 通用电子计算机指令文件, RLHF 之后的管道
- [Stienon等人——学习从人类反馈中总结(arXiv:2009.01325)](https://arxiv.org/abs/2009.01325) — 该 RLHF- 总结性前任
- [克里斯蒂诺等人——深 reinforcement learning 人类偏爱的区别(arXiv:1706.03741)](https://arxiv.org/abs/1706.03741) 最初基于优惠的RL案文
- [Bai等人——培训一名无伤大雅的助理, RLHF (arXiv:2204.05862)](https://arxiv.org/abs/2204.05862) — Anthropic高频延伸的GPT导管
