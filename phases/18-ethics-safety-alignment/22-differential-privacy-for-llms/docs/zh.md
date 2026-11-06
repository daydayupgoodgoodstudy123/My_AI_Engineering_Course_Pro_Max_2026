<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="differential-privacy-for-llms"></a>

# 面向 LLMs 的差分隐私

> DP-SGD仍然是标准——噪音喷射 gradient 更新提供正式(epsilon、delta)保证。 计算、 内存和实用性方面有相当大的管理; parameter- 高效的DP fine-tuning (LoRA +DP-SGD是2025年共同配置(ACM 2025)。 membership inference (Duan等人,2024年)报告,语言模型的成功有限;培训数据提取(Carlini等人,2021年;Nasr等人,2025年)恢复了大量逐字记录。分辨率(arXiv:2503.06808,2025年3月):差距在于测量的大小——插入的罐子相对于“最可提取”的数据。新的金丝雀设计使得基于损失的MIA没有影子模型,并产生了对一个非三重DP审计。 LLM 提供现实DP保证的真实数据培训。 inference 时间通过专家混合 下一位...token 分布; DP合成数据生成(Google Research 2024). 新出现的攻击:通过 LLM 反馈——信心-核心渗漏。

**类型：** 构建
**语言:** Python (stdlib,DP-SGD噪音注射和_____会计师演示)
**先修要求:** 第01阶段 -09(信息理论),第10阶段 -01(大型培训)
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 定义(epsilon, delta) - 不同的隐私, 并声明DP-SGD 配方 。
- 解释2024-2025年的紧张:卡纳里 MIA与训练数据提取 提供了不同的图片。
- 描述 PMixed 和为什么 inference- 时间私人预测是DP培训的替代办法。
- 描述通过不同隐私的翻转 LLM 反馈攻击。

<a id="the-problem"></a>

## 问题

LLMs Carlini等人的记忆。 2021年显示制作语言模型根据要求复制了逐字记录。 DP是正式的辩护: 训练, 使得产出对任何单一的训练例子都不可避免不敏感。 2024-2025年的证据显示, DP- SGD是必要的, 但部署的数值可能与 $% 不符 。 threat model.

<a id="the-concept"></a>

## 概念

<a id="ε-δ-differential-privacy"></a>

### —— 不同的隐私

如果一个实例和任何事件S中存在任何两个数据集,随机算法M就是(, )-DP:
P(M(D)在S) e * P(M(D)')在S)+ 。

解释:产出分布足够接近(由),除概率 外,无法可靠地推断任何个人的贡献。

<a id="dp-sgd"></a>

### DP-SGD

Abadi等人,2016年。 标准配方:
1. 试一下小包
2. 计算每例 gradients.
3. 剪贴每个示例 gradient 至临界点C。
4. 对裁剪后的 gradients 求和，并添加标准差为 σ * C 的高斯噪声。
5. 使用吵闹的金额更新 parameters.

隐私成本由会计师(Moments Descutant,Rényi DP)跟踪。 LLM 文学业差异很大 threat model,数据敏感性和实用目标;没有通用的“安全”默认值。在有些情况下,已公布的例子大致覆盖 % 1 - 10 LLM 培训环境,但这些是说明性——不是建议违约。 低的通常需要更多噪音,并可能增加公用事业损失。

<a id="lora--dp-sgd"></a>

### LoRA +DP-SGD 组合

边境模式的DP-SGD完全禁止。 LoRA (Hu等人,2022年)限制 gradient 更新到一个小适配器, 减少每个示例 gradient storage. LoRA + DP-SGD是2025年通用配置。DP保证适用于适配器;基模式保持不变。

<a id="the-2024-2025-tension"></a>

### 2024-2025年的紧张

两条证据:

- **加那利岛海洋大气管理局(Duan等人,2024年)。** 在训练数据中插入独有的金丝雀, 测量成员是否 --inference 攻击者可以识别他们, 语言模型的成功程度有限, 暗示MIA很难。
- **培训数据提取(Carlini 2021年,Nasr等人,2025年)。** Prompt 使用前缀的模型; 测量它是否从培训中恢复了逐字记录。 报告内容相当含混。 建议MIA在相关意义上是容易的。

2025年3月的决议(arXiv:2503.06808):两种衡量方法不同。 MIA在插入的金丝雀上询问“ e 例为 D ” 。 Explicationon问“ 我还能恢复D 什么呢? ” “最容易提取”的例子对于隐私很重要; 辛巴威报告这个是因为没有优化到可以提取。

新的金丝雀设计。 以损失为基础的MIA, 没有影子模型。 第一次非三重DP审计 LLM 具有现实的DP保证的真实数据。

<a id="alternatives-to-dp-training"></a>

### DP培训的替代办法

- **倾销(arXiv:2403.15638)。** 私人预测 inference 时间 下一位专家的混合token 分布; 每位专家看到一大批训练数据; 汇总为DP增加噪音。 完全避免DP训练 。
- **DP合成数据生成(Google研究,2024年)。** LoRA- 与DP-SGD的配对、合成数据样本、培训一个关于合成数据的下游分类员。

两者都绕开全部DP培训的水电费,而以不同的费用支付。 threat model.

<a id="differential-privacy-reversal-via-llm-feedback"></a>

### 差异隐私翻转 LLM Feedback

2025年袭击的出现。使用经DP培训的模型的信心评分作为标志来重新确定个人。 即使产出不会泄漏,信任分配也可以。

辩护: 不要暴露信任, 或者在暴露前缩短/量化它们。 这是除( , )- DP 培训之外的额外要求 。

<a id="where-this-fits-in-phase-18"></a>

### 18阶段适合的地方

20-21课是偏向/公平,22课是隐私,23课是通过水印的出处。27课涉及监管数据验证层。

```figure
an-dp-clip-noise
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟玩具二进制数据集的 DP-SGD。 您可以扫描噪音乘数 Q 和剪切标准 C 并跟踪 (, ) 预算和准确性成本。 “ 卡纳攻击” 插入一个独特的训练示例, 并测量日志损失测试能否在 DP 之前和之后检测到它 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-dp-audit.md`。鉴于DP对语言模型部署的索赔,它审计了(,)值、所使用的会计、MIA evaluation 协议,以及是否对信任接触矢量进行了评估。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。在 {0.5, 1.0, 2.0} 中扫描 +2. 并报告 (, ) 精确性交易。 标明公用事业崩溃的点 。

2. 执行一个金丝雀插入和日志损失测试。测量DP-SGD前后的检测率, 0. 3= 1. 0。

3. 阅读Nasr等人(2025年)关于培训数据提取的内容。 为什么开采成功不会在中度下崩溃? 这对MIA-as-evaluation?

4. 设计一个使用 PMixED(arXiv:2403.15638) 的部署,完全在 inference 时间。 什么是 threat model 说PMixED在DP -SGD没有?

5. 将 DP Reveral 拼贴在 LLM 反弹攻击 设计一个限制信任区泄漏的反措施 并估计其部署成本

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| DP | "(,) - 不同的隐私" | 正式隐私:在相邻数据集更改下输出分布关闭 |
| DP-SGD | "噪音喷射 SGD" | Gradient clipping + 高斯语噪音增加;标准DP培训 |
| LoRA +DP-SGD 组合 | "高效的私人微调" | 低级适应器DP-SGD;2025标准配置 |
| MIA | "membership inference" | 攻击,确定训练数据中是否有例子 |
| Canary | "插入的水印示例" | 用于衡量DP渗漏情况的独特训练实例 |
| PMixED | "private inference mixture" | Inference- 时间DP 通过专家混合 关于下一个token distributions |
| DP 逆转 | "信心泄漏攻击" | 攻击,用模型的自信作为神谕 来重新识别 |

<a id="further-reading"></a>

## 进一步阅读

- [Abadi等人——DP-SGD(arXiv:1607.00133)](https://arxiv.org/abs/1607.00133) - 标准DP培训算法
- [Carlini等人——提取训练数据(arXiv:2012.07805)](https://arxiv.org/abs/2012.07805) - 银色提取纸
- [Duan等人-Canary MIA关于 LLMs (arXiv:2402.07841,2024) 国家](https://arxiv.org/abs/2402.07841) 有限成功MIA
- [Kowalczyk等人——审计司 LLMs (arXiv:2503.06808,2025年3月)](https://arxiv.org/abs/2503.06808) 解决紧张局势
- [倾斜(arXiv:2403.15638)](https://arxiv.org/abs/2403.15638) — inference- 时间私人预测
