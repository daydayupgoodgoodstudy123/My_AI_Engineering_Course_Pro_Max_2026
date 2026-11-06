<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="model-system-and-dataset-cards"></a>

# 模型卡、系统卡与数据集卡

> 三种文件格式构成AI透明。 Model Cards (Mitchell等人,2019年)——模型的营养标签:训练数据、定量分类分析、道德考虑、警告;只有0.3%的Hugging Face model cards 数据集数据表(Gebru等人,2018年,CACM)——动机、组成、收集过程、标签、分发、维护;电子数据表类比;数据卡(Pushkarna等人,Google 2022)——模块层细节(星球、远洋、微科)作为不同读者的边界对象。 LLMs (CardGen, Liu等人,2024); 模型卡细节与高频下载量增加高达29%有关(Liang等人,2024); 可核实证明(Laminator, Duddu等人,2024); 碳/水的可持续性报告增加(Jouneaux等人,2025年7月); 欧盟/标准化组织监管卡的出现;系统卡(Sidhpurwala,2024年;Meta系统级透明度;“信任蓝皮”ARXiv:2509.20394)——包括安全能力的国际航空协会端至端文件, prompt- 注射防护,数据过滤检测, alignment 与人类价值观。

**类型:** Build
**语言:** Python (stdlib, 模型卡+数据表+系统卡生成器)
**先修要求:** 阶段18 18(安全框架),阶段18 24(管制)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 描述最初的Mitchell等人(2019年) model card 以及Gebru等人2018年数据表。
- 描述数据卡的远程镜/半镜/微型图层。
- 描述系统卡及其端到端覆盖范围。
- 说明三项2024-2025年的发展(自动生成、可核查的证明、可持续性报告)。

<a id="the-problem"></a>

## 问题

监管框架(课程24)和实验室安全政策(课程18)都需要文件。model cards)至特定数据集(数据表)至特定系统(系统卡)。每个系统卡处理不同的透明度范围。2024-2025年自动化和可核查的验证工作解决长期存在的采用问题。

<a id="the-concept"></a>

## 概念

<a id="model-cards-mitchell-et-al-2019"></a>

### Model Cards (Mitchell等人,2019年)

Sections:
- 模型细节。
- 预定用途。
- 因素(与人口或环境有关的因素) evaluation).
- Metrics.
- Evaluation data.
- 训练数据.
- 定量分析(按因素分列)。
- 道德考虑
- 穴居和建议。

收养问题:Oreamuno等人,2023年对Hugging Face的审计 model cards 发现只有0.3%的文件道德考量。

<a id="datasheets-for-datasets-gebru-et-al-2018"></a>

### 数据集数据表(Gebru等人,2018年)

电子数据表类比。 节数 :
- 动机( 为什么数据集创建 )
- 构成(其中的内容)。
- 收集过程(如何组装)。
- 标签(如果适用)。
- 用途(有意、禁止、风险)。
- Distribution.
- Maintenance.

发表于CACM 2021。数据表是上游文件; model card 取决于数据表是否准确。

<a id="data-cards-pushkarna-et-al-google-2022"></a>

### 数据卡(Pushkarna等人,谷歌2022)

模块层细节。 三个缩放级别 :
- **Telescopic.** 非专家高级别摘要。
- **Periscopic.** 多边法律工作者中期概览。
- **Microscopic.** Detailed feature- 审计人员的文件级别。

边界目标设置:不同的读者从同一文档中提取不同的信息。

<a id="system-cards"></a>

### 系统卡

范围:端到端的AI系统,包括模型+安全堆叠+部署环境。
- 安全能力。
- Prompt-注射保护
- 数据过滤检测
- Alignment 符合人类的价值观
- Incident response.

Sidhpurwala 2024和Meta系统一级的透明度工作。 “信托蓝图”(arXiv:2509.20394)正式确定系统卡是该系统的部署层的补充。 Model Cards.

<a id="2024-2025-developments"></a>

### 2024-2025年的事态发展

- **CardGen(Liu等人,2024年)。** 通过自动生成模型卡 LLMs;报告标准米切尔2019字段的客观性高于许多人手卡。
- **下载相关(Liang等人,2024年)。** Detailed model cards 与高频下载率高达29%相关——采用压力现在由市场驱动,而不仅仅是合规驱动。
- **Laminator(Duddu等人,2024年)。** 通过硬件TEE/加密签名的可核实证明——允许 model card 而不是仅仅提出索偿要求。
- **可持续性(Jouneaux等人,2025年7月)。** 碳、水和计算能源足迹的附加;新出现的标准化组织标准。
- **管理卡。** 《欧盟国际税务法》(第24条)《国际税务合作局业务透明度守则》一章要求 model cards 作为一种合规的文物。

<a id="where-this-fits-in-phase-18"></a>

### 18阶段适合的地方

24-25课是监管和CVE层次。 26课是文献层。 27课是培训-数据管理,这是数据表的上游。 evaluations 以卡片中引用。

```figure
an-card-scopes
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 生成最小值 model card,数据表和玩具部署系统卡。每个系统都遵循金刚石部分结构。您可以检查格式并比较三个范围。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-card-audit.md`。如果有的话 model card,数据表或系统卡,它审计部分覆盖范围、数字分类以及是否存在可核实的证明。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。检查生成的卡片,确定薄弱的区块(仅指持有人),并具体说明哪些证据可以加强这些区块。

2. 延长 model card 并按两个人口群体进行量化分类分析(Lesson 20)。

3. 阅读Oreamuno等人,2023年,收养率为0.3%。 model card 说明如何增加采用道德考虑。

4. Laminator (Duddu等人,2024年) 使用TEEs 进行可核实的证明。 设计一个带有加密证明的模型卡字段 evaluation 并描述验证者的作用。

5. 写入系统卡( 系统卡, 不 Model Card) 用于您过去的项目或假设部署。确定第三方审计员的最高价值部分。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Model Card | "米切尔卡" | Mitchell等人2019年ML模型标准文件 |
| Datasheet | "格布鲁数据表" | Gebru等人2018年数据集标准文档 |
| 数据卡 | 普什卡纳牌 | Google 2022模块化数据层文档 |
| 系统卡 | 调用卡 | 端到端 AI 系统文档,包括安全堆叠 |
| 边界物体 | "不同的读者,一个医生" | 数据卡设置:同一文件为不同受众服务 |
| 可核实的证明 | "拉米纳证明" | 与文件索赔所附的密码或技术、环境和环境证明 |
| 可持续性领域 | "碳/水足迹" | 2025年环境核算新增加额 |

<a id="further-reading"></a>

## 进一步阅读

- [米切尔等人- Model Cards 用于报告模型的计算机设备(arXiv:1810.093993, FAT)* 2019)](https://arxiv.org/abs/1810.03993) - model card
- [Gebru等人——数据集数据表(CACM 2021,arXiv:1803.09010)](https://arxiv.org/abs/1803.09010) 数据表纸
- [Pushkarna等人——数据卡(Google 2022)](https://arxiv.org/abs/2204.01075) - 分层数据文件
- [Sidhpurwala等人——信托蓝图(arXiv:2509.20394)](https://arxiv.org/abs/2509.20394) - 系统卡正式化
