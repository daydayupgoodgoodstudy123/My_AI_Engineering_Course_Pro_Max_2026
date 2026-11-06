<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="moderation-systems--openai-perspective-llama-guard"></a>

# 内容审核系统：OpenAI、Perspective、Llama Guard

> 生产节制系统可实施 " 12-16 " 课中确定的安全政策。 OpenAI Moderation API: `omni-moderation-latest` (2024年) 以 GPT- 4o 将文本+图像一次性分类;多语种测试集比先前版本高42%;响应方案返回13种布尔语——骚扰、骚扰/威胁、仇恨/威胁、非法、非法/暴力、自我伤害/故意、自残/自制、性、性/未成年人、暴力、暴力/制图;多数开发者免费。 Llama 卫兵3/4(第16条):14个刚果解放运动危险,《解释滥用法》,8种语言(v3),多图像(v4)。 API (谷歌吉格锯):毒性评分 LLM- 调节波;主要是具有重毒性/侮辱/侮辱变异的单体分泌毒性;内容调节研究基线;损坏:Azure内容主持人于2024年2月退役,代之以Azure AI内容安全。

**类型:** Build
**语言:** Python (三层调制) harness)
**先修要求:** 阶段18 16 (Llama 警卫/加拉克/皮里特)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 描述 OpenAI Moderation API分类学及其与 Llama 3号警卫的刚果解放运动准备就绪
- 描述三个中度层模式( 输入、 输出、 自定义) , 并列出每个模式的失败模式 。
- 描述视角 API以预知身份...LLM- 时间越长的基线,为什么它仍然用于研究。
- 说明Azure折旧时间表。

<a id="the-problem"></a>

## 问题

12-16课描述了攻击和防御工具。29课涵盖了在用户触碰产品的表面操作防御的部署的节制系统。三层模式是2026年默认配置。

<a id="the-concept"></a>

## 概念

<a id="openai-moderation-api"></a>

### OpenAI Moderation API

`omni-moderation-latest` (2024). 建筑在 GPT-4o. 将文本+图像分类为一次性。 大多数开发者免费使用 。

类别(答复方案中的13种布尔):
- 骚扰、骚扰/威胁
- 仇恨、仇恨/威胁
- 自我伤害、自我伤害/故意、自我伤害/指示
- 性、性/未成年人
- 暴力/历史
- 非法、非法/暴力

适用于 `violence`, `self-harm`, 和 `sexual` 但没有 `sexual/minors`; 该 rest 仅文本。

代码 harness 在 `code/main.py` 我们崩溃了 `/threatening`, `/intent`, `/instructions`, 和 `/graphic` 制作代码应该使用完整的13类计划。

多语种测试组比上一代中度端点高42%。 每一类分数; 应用程序设定阈值。

<a id="llama-guard-34"></a>

### Llama 卫兵3/4

14个刚果解放运动危险类别(与 OpenAI13种响应- 系统布伦。 支持 8 种语言 (v3) 。 Llama 警卫4号(2025年4月)是本地多式联运,12B号。

该 OpenAI 和 Llama 警卫分类重叠,但有分歧。 OpenAI 具有“非法”这一宽泛类别; Llama 警卫队有“暴力犯罪”和“非暴力犯罪”分别。

<a id="perspective-api-google-jigsaw"></a>

### Perspective API (谷歌吉格锯)

毒性评分系统 LLM类别:毒性, 毒性_毒性、不道德、不道德、不道德、不道德、不道德、不道德_单分主要分数(TOXICITY)与子分数变量。

广泛用作内容调适研究基线,因为 API 稳定,有记录,并有多年 calibration 数据。 LLM- 相邻的使用案例, Llama 警卫或 OpenAI 调节通常更合适。

<a id="the-three-layer-pattern"></a>

### 三层模式

1. **输入节制。** 分类用户的 prompt 代代前。 拒绝标记。 延迟: 一次分类程序呼叫 。
2. **产出节制。** 交付前对模型输出进行分类。 如果标记, 则替换为拒绝 。 延迟度: 一代又一代的分类者调用 。
3. **习惯性温和。** 特定域的规则(regex、允许列表、商业政策) 。 运行于输入或输出 。

这三个层次是按设计顺序排列的:输入节制必须在生成之前完成,产出节制则在生成之后运行。 平行主义适用于一个层次内——运行多个分类器(例如,如果有的话,可以使用一种方法来计算的话 ) 。 OpenAI 调制+ Llama 在同一文本中, 守护 + 视野 隐藏每个分类标签的延迟。 作为可选的优化, 占位符响应 (“ 片刻, 检查... ”) 可以显示, 而输入节奏则完成且显示 。 token-1 streaming 旗帜行为是可配置的:拒绝、消毒、升级为人类审查。

<a id="failure-modes"></a>

### 失效模式

- **仅输入。** 不获取输出 hallucinations (Lesson 12-14 编码攻击绕行输入分类器)
- **仅输出 。** 允许任何输入到达模型; 增加成本; 向攻击者展示内部推理。
- **仅定制 。** 类别不健全;正反面是易碎的。

层是默认的,带和扣

<a id="azure-deprecation"></a>

### 分率折旧

分层内容主持人:2024年2月被折旧,2027年2月退休。 LLM- 以阿祖为基地,并与阿祖结合 OpenAI迁移是2024-2027年阿祖尔部署的实地项目。

<a id="where-this-fits-in-phase-18"></a>

### 18阶段适合的地方

第16课涉及红队的中度工具,第29课涉及已部署的中度工具,第30课以目前的两用能力证据结束。

```figure
an-moderation-layers
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 构建三层调和 harness:输入管理器(关键词+类别评分),输出管理器(输出的分类相同),自定义管理器(域规则)。您可以运行输入并观察哪个层可以捕捉到什么。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-moderation-stack.md`。如果使用,它建议采用适度的堆叠配置:输入时对输入进行分类,产出时按输出进行分类,对边框案件进行定制,并指定哪个法官。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。运行一个良性、边缘性和有害输入,贯穿所有三个层次。报告每个层次的火势。

2. 延长 harness 与透视-API将临界值与类别值作比较。

3. 读 OpenAI Moderation API 医生和医生 Llama 卫兵3类名单,每个地图 OpenAI 最接近的类别 Llama 警卫类别。 识别三个不干净的地图类别 。

4. 为代码助理的部署设计一个调控堆叠(例如, GitHub 确定最相关和最不相关的类别,并提出习惯规则。

5. 2027年2月,Azure内容主持人退休。计划向Azure AI内容安全系统迁移。确定移徙中风险最高的因素。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| OpenAI Moderation | "omni-moderation-latest" | GPT- 4o 13类(文本)分类,部分提供多式联运支助 |
| Perspective API | "谷歌吉格锯毒性" | Pre-LLM- 毒性时间过长的评分基准 |
| Llama Guard | "MLCommons 14 - 类" | Meta的危险分类器(v3:8B文本,8Langs;v4:12B多式联运) |
| 输入节制 | "预产期过滤器" | 用户分类器 prompt 模式调用前 |
| 输出中度 | "后代过滤器" | 交付前对模型输出进行分类 |
| 自定义中度 | "主规则" | 具体部署规则(regex、许可名单、政策) |
| 层调度 | "所有三个层" | 标准生产部署模式 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI Moderation API docs](https://platform.openai.com/docs/api-reference/moderations) - 全新调和终点
- [紫拉玛+ Llama Guard](https://github.com/meta-llama/PurpleLlama) — Llama 警卫补给
- [谷歌切锯视角 API](https://perspectiveapi.com/) 毒性评分
- [自动交换分解码内容安全](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/) 替换阿祖尔
