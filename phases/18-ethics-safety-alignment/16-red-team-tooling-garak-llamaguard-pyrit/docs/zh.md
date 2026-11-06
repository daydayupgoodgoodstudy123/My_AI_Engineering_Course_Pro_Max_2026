<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="red-team-tooling--garak-llama-guard-pyrit"></a>

# 红队工具：Garak、Llama Guard、PyRIT

> 三个生产工具架设了2026年的红队堆 Llama 警卫(梅塔)——a Llama-3.1-8B 分类器,对14个刚果解放运动危险类别进行微调;2025年 Llama 4号警卫是12B 本地的多式联运分类员 Llama 4 Scout. Garak(荷兰国际开发署)——公开来源 LLM 使用静态、动态和适应性探测器进行 hallucination, data leakage, prompt injection、毒性,以及 jailbreaks. PyRIT(微软)——与Crescendo、TAP和自定义转换链进行多轮式红队运动,以便进行深层开采。 Llama 3号警卫在Meta的"Llama 3 型群”(arXiv:2407.21783); Llama 3-1B-INT4警卫, 以arXiv: 2411.17713; Garak 探测器结构 github这些工具是红色小组研究(12-15)与部署(17+)之间的2026年生产界面。

**类型：** 构建
**语言:** Python (stdlib, 工具结构模拟器和 Llama 警卫式分类模型)
**先修要求:** 阶段18 12-15(续)jailbreaks 和新闻通讯)
**时间：** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- Describe Llama 3/4警卫在安全堆放的位置:输入分类器、输出分类器或两者兼有。
- 列出14个刚果解放运动危险类别,并列出一个非明显的危险类别(《守则》解释滥用)。
- 描述加拉克探测器的结构:探测器,探测器, harnesses.
- 描述PyRIT的多方向运动结构 以及它如何组成加拉克探测器

<a id="the-problem"></a>

## 问题

12-15号课是攻击的表面,生产部署需要可重复、可缩放 evaluation。三种工具在2026年占主导地位: Llama 警卫(国防分类)、加拉克(扫描仪)、PyRIT(运动指挥员),每个目标都针对不同层次的红队生命周期。

<a id="the-concept"></a>

## 概念

<a id="llama-guard-meta"></a>

### Llama 警卫(梅塔)

Llama 3号警卫是1号 Llama-3.1-8B 模型,为14类刚果解放运动/国际铁路运输联盟的投入/产出分类进行微调:
- 暴力犯罪、非暴力犯罪、与性别有关犯罪、CSAM、诽谤罪
- 专业咨询、隐私、IP、滥杀滥伤武器、仇恨
- 自杀/自残、性内容、选举、代码解释虐待

支持 8 种语言。 用法: 在 LLM 之后(输入节奏) LLM 两种用途产生不同的培训分布—— Llama 3艘护卫舰作为单一的模型 处理这两种情况

Llama 警卫3-1B-INT4(arXiv:2411.17713,440MB,~30) tokens/在移动中 CPU)是量化边缘变量。

Llama 警卫4号(2025年4月)为12B号,原为多式联运,从 Llama 4 Scout. 它以一个摄取文本+图像的分类器取代8B文本和11B前视像。

<a id="garak-nvidia"></a>

### 加拉克语( 荷兰语)

开放源码脆弱性扫描仪。 结构 :
- **Probes.** 攻击发电机 hallucination, data leakage, prompt injection毒性, jailbreaks固定(固定) prompts),动态(生成) prompts),适应性(响应目标产出)。
- **Detectors.** 对照预期的失败模式——有毒、泄漏、监禁——对产出进行评分。
- **Harnesses.** 管理探测-检测对子,运行运动,生成报告。

信托国际协会将加拉克与 Llama- 固定防护罩(Sock shelp)Prompt- 保护86M输入分类器 Llama- 终端至终端屏蔽目标的3-8B导火线输出分类器 evaluation。基于级数的评分(TBSA)取代二进制出入证/失灵,该模型可在第三级严重通过,在同一探针上在第五级严重失灵。

<a id="pyrit-microsoft"></a>

### 微软

Python 风险识别工具包:多轮红队运动。
- **Converters.** 变种 prompt 解说,编码,翻译,角色扮演。
- **Orchestrators.** 运行运动: 加速、 TAP( 支架)、 红队( 海关环) 。
- **Scoring.** LLM- 做裁判或分类

热力喷雾器是加拉克的较重表弟,加拉克运行数千个单轮探测器;热力喷雾器运行深度多轮运动,旨在打破特定的故障模式。

<a id="the-stack"></a>

### 堆叠

Put Llama 模型两侧的守卫。 运行 Garak 夜间回归。 运行 PyRIT 以进行释放前运动。 这是大多数生产部署的 2026 默认配置 。

<a id="evaluation-pitfalls"></a>

### Evaluation pitfalls

- **法官身份** 所有三个工具都可以使用 LLM 法官;法官 calibration 驱动器报告 ASR (Lesson 12) , 请在工具旁边指定法官 。
- **腐烂的假象** 用于对准模型的加拉克探测器年龄。适应性探测器(PAIR型)的年龄比静态探测器要慢。
- **Llama 保护FPR 良性内容。** Early Llama 保护版本的标签过短的政治和LGBT 内容; Llama 卫兵3/4 calibrations 改进了,但没有校准每次部署。

<a id="where-this-fits-in-phase-18"></a>

### 18阶段适合的地方

12-15课是攻击家庭。16课是生产工具。 evaluation 18号课是将这些工具纳入政策结构的边界安全框架。

```figure
al-guard-stack
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 制造一个玩具 Llama 警卫式分类器(关键词+语义) features 14岁以上类别) harness 和一个PyRIT式的多方向转换器链。 您可以对一个模拟目标运行三个工具, 并观察不同的覆盖信号 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-red-team-stack.md`。根据部署描述,它列出三种工具中的哪一种是合适的,每种工具中应配置什么,以及哪些回归速度运行。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`比较 Llama- 保护式分类器的探测率 单转对多转攻击

2. 安装一个新的 Garak 探测器: 以64码编码的有害请求。 测量其检测结果 Llama- 保镖式分类员

3. 扩展 PyRIT 式转换器链, 并使用“ 将转换为法语, 然后是解说” 转换器。 重新测量攻击成功 。

4. Read Llama 3号警卫危险类别清单。 确定两种类型的训练数据将实际产生高假阳性值的开发者合法含量。

5. 比较 Garak 和 PyRIT 的设计原理。 用于每个工具都正确的部署 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Llama Guard | 分类员 | Fine-tuned Llama-3.1-8B/4-12B 安全分类,14个危险类别 |
| Garak | 扫描仪 | NVIDIA 开放源码脆弱性扫描仪;探测器、探测器, harnesses |
| PyRIT | "竞选工具" | 微软多方向红队管弦乐;转换器、管弦乐、评分 |
| Prompt-Guard | "小分类员" | 梅塔86M号 prompt-注射分类器,配有 Llama Guard |
| TBSA | 以分数为基数 | 加拉克的分层出入/失败取代二进制结果 |
| 转换器链 | "句子+编码+..." | 用于制造多步攻击的原始分子 |
| 刚果解放运动危险类别 | 十四个分类 | 工业标准分类学 Llama 警卫目标 |

<a id="further-reading"></a>

## 进一步阅读

- [玛塔 - Llama 警卫3号(在 Llama 3 畜牧纸,ArXiv:2407.21783](https://arxiv.org/abs/2407.21783) - 8B 分类器
- [玛塔 - Llama 警卫3-1B-INT4(arXiv:2411.17713)](https://arxiv.org/abs/2411.17713) 量化移动分类器
- [尼加拉瓜加拉克- GitHub](https://github.com/NVIDIA/garak) - 扫描机复制和文件
- [微软电磁- GitHub](https://github.com/Azure/PyRIT) 运动工具包
