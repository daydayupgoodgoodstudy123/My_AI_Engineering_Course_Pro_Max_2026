<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-17--personal-ai-tutor-adaptive-multimodal-with-memory"></a>

# 综合项目 17：个人 AI 导师——自适应、多模态与记忆

> Khanmigo(汗学院),Duolingo Max,谷歌学习M/ Gemini 通用的形状是Scrotic政策(绝不只是丢弃答案),一种在每次互动后更新的学习者模式(Bayesian知识追踪风格)、语音+文字+光图输入、课程图检索、空间重复时间安排和适合年龄内容的硬安全过滤。 Python进行为期两周的效能研究,有10名学员参加,并通过内容安全审计。

**类型:** Capstone
**语言:** Python (后端,学习者模型) TypeScript (网络应用程序) SQL (通过 Postgres + Neo4j 绘制的曲线图)
**先修要求:** 第五阶段(无声波),第六阶段(发言),第11阶段(LLM 工程,第12阶段(多式),第14阶段(agents17阶段(基础设施),18阶段(安全)
**实施阶段:** P5;P6;P11;P12;P14;P17;P18
**时间:** 30小时

<a id="problem"></a>

## 问题

适应性辅导过去是一个电子技术研究领域。 到2026年,它已成为一种消费产品。 Khanmigo被部署在美国大多数学校区。 Duolingo Max 袭击了数千万个MAU。 Google的LinningLM / Gemini Qizlet Q-Chat 与答题卡并列。 合成导师用导师为孩子打入病毒。 常见元素是: 多式联运( 类型、 语言、 照片方程式 ) , Scropic 教学法( 先问, 稍后解释 ) , 一种在每次互动后更新的学习模式, 以及严格的适龄安全性 。

您将为特定组别建立其中之一。 测量栏是一个实际的效能研究: 测试前和测试后, 学生有10人, 超过两周。 声音循环必须具有自然感( 综合项目 03 子堆) 。 记忆必须是尊重隐私的。 安全过滤器必须通过 K-12 的 COPPA- 觉察红色队 。

<a id="concept"></a>

## 概念

四个组成部分。 **教学政策** 是一个Scortio环:当学习者问答案时,政策会提出一个引导性的问题;当他们得到正确答案时,就会转向下一个概念;当他们被卡住时,就会给出一个脚手架提示。 **学习者模型** 即Bayesian知识追踪(或一个简单的变量),在每次互动后更新每个课程节点的掌握概率。 **课程图** 是一个带有必要边际概念的Neo4j;政策走在图表中选择下一个概念。 **Memory** 是一个具有过去相互作用、错误和偏好的偶发+语义商店(试样式)。

UX是多式的,输入文本用于输入答案。通过LiveKit + Whisper(重复综合项目 03) 进行语音输入。通过点或帕利杰马 进行图片输入,解决数学问题。 通过卡特西亚音频-2 进行语音输出。安全使用 Llama 4号卫兵加上适龄过滤器(阻断成人内容、暴力、自残)和防腐剂记忆保留政策。

效率研究是可交付的。 10个学习者, 测试前和测试后, 两周。 报告学习获得三角洲和信任间隔。 比较非适应性基线( 与没有辅导政策而线性传递的内容相同 ) 。

<a id="architecture"></a>

## 建筑

```
learner device
  |
  +-- text         -> web app
  +-- voice        -> LiveKit Agents (ASR + TTS)
  +-- photo math   -> dots.ocr / PaliGemma 2
       |
       v
  tutor policy (LangGraph)
       - Socratic decision head
       - next-concept chooser (curriculum graph walk)
       - hint scaffolder
       - mastery update
       |
       v
  learner model (BKT / item-response theory)
       - per-concept mastery probability
       - spaced-repetition scheduler (SM-2 or FSRS)
       |
       v
  memory (agentmemory-style)
       - episodic: every interaction
       - semantic: learned mistakes, preferences
       - retention policy: COPPA / GDPR aware
       |
       v
  curriculum graph (Neo4j)
       - prerequisite edges
       - OER content attached
       |
       v
  safety:
    Llama Guard 4 + age-appropriate filter
    memory access guarded by learner ID scope
```

<a id="stack"></a>

## 堆栈

- 主题选择: K-12 代数或内插 Python (深度选择一个)
- 教学政策 : LangGraph over Claude 索内特 4.7 (与 prompt caching)
- 学习者模型:贝叶斯知识追踪(经典)或用于间隔的FRS
- 课程图:新四j概念+必备边和 OER 内容
- 内存: 代理模式的持久性矢量+偶发性+语义存储
- 声音: LiveKit Agents 1.0 + 卡特西亚音速-2(重复使用3号顶岩堆)
- 图片数学: 点数或帕利Gemma 2 用于方程式识别
- Safety: Llama 卫兵 4+ 适合年龄的自定义过滤器
- 模拟: 产生热点问题,预选/后选 harness,效率研究工具

```figure
cf-tutor-loop
```

<a id="build-it"></a>

## 动手实现

1. **课程图。** 创建50- 150个概念节点的 Neo4j (例如从“ 数字行” 到“ 水方公式” 的 K-12 代数) , 并配有必要的边緣。 随函附上每个节点的 OER 内容( 开放式文本、 OpenStax ) 。

2. **学习模型。** 初始化贝叶斯知识追踪, 使用前科: 猜测、 滑落、 学习率。 每次互动后更新每个概念的掌握能力。 每位学习者都坚持 。

3. **教书政策** LangGraph 带有节点的 : `read_signal` (学习者回答正确吗 / 部分/ 卡住? ) `select_concept` (选取最优先的概念的行走课程图) `scaffold` (Socratic prompt), `update_mastery`.

4. **Memory.** 每一次互动都写到一个小商店。错误和偏好会促进语义记忆。 COPPA 认知保留政策: 一年后自动删除, 父子关系可以访问 。

5. **声音路径** LiveKit Agents 教师政策附属工人。 通过Whiseper-v3-turbo的ASR, 通过Cartesia Sonic-2的TTS, Barge-in 支持(再使用3号顶石机械)。

6. **照片地图路径 。** 上传或捕获图像; 运行点为ocr 或 PaliGemma 2 以识别方程式; 将数据反馈给导师作为结构化输入 。

7. **Safety.** 每个模型输出通过 Llama 4+适龄过滤器(阻断自我伤害、成人内容、暴力),学习者识别码的内存访问;父母访问表面删除。

8. **效率研究。** 10名学员,预考(标准化的30个问题基线),两周辅导互动(3次/周),后考。与10名学员非适应性基准组群相比,内容相同。

9. **每周进度报告。** 每位学员自动生成一份PDF摘要,其中概述所探讨的专题、掌握轨道,并建议下一步。

<a id="use-it"></a>

## 实际应用

```
learner: "I don't understand why 3x + 6 = 12 means x = 2"
[signal]   stuck
[concept]  'isolating variables' (prerequisite: addition-subtraction-equality)
[scaffold] "what number would you subtract from both sides to start?"
learner: "6"
[signal]   correct
[mastery]  addition-subtraction-equality: 0.62 -> 0.77
[concept]  continue 'isolating variables'
[scaffold] "great. now what is 3x / 3 equal to?"
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-ai-tutor.md` 是一个具有多式输入、学习者模型、记忆、安全和测量功效的针对特定主题的适应性辅导员。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | 学习得益三角洲 | 为期两周的10升升机研究中的预试验/试验后三角洲 |
| 20 | 专制忠诚 | 记录样本的鲁比分 |
| 20 | 多式联运 UX | 语音+照片+文本一致性结束 |
| 20 | 安全+隐私姿态 | Llama 警卫4人通过率+ COPPA-意识保留率 |
| 15 | 课程广度和图表质量 | 概念范围+必备图一致性 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 运行效果研究时, 使用和不使用适应性学习者模型( 随机概念顺序) 。 报告三角洲 。 期待适应性以赢得, 但大小是有趣的数字 。

2. 添加一个多式联运探测器:与文本、声音和照片一样的概念问题。 modality 他们更喜欢。

3. 建立一个母仪表板:练习的主题、掌握的轨迹、即将出现的概念、安全事件(任何 guardrail 与COPPA吻合。

4. 添加语言转换模式: 教师接受西班牙语输入并用西班牙语授课。 测量 X 保护范围 。

5. 强调记忆隐私: 校对者A 即使通过语音剪辑重录器也看不到学习者B的数据。 记录尝试访问和警告 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 独裁政策 | "问,不要丢下" | 教官问一个先导的问题,而不是回答 |
| 贝叶斯知识追踪 | "BKT" | 典型学习者模型方程式,用于掌握每个概念的概率 |
| FSRS | "自由空格重复计划" | 2024 空格重复调度器,优于 SM-2 |
| 课程图 | "概念DAG" | 具有先决条件优势的新概念4j |
| 笔记内存 | "对称日志" | 保存供日后检索的每次互动 |
| 语义内存 | 学习模式商店 | 间接偏好引起的错误和偏好 |
| COPPA | "孩子隐私法" | 美国法律限制收集13岁以下儿童的数据 |

<a id="further-reading"></a>

## 进一步阅读

- [Khanmigo(汗学院)](https://www.khanmigo.ai) 参考消费者 K-12 辅导员
- [杜利安戈·马克斯](https://blog.duolingo.com/duolingo-max/) 语文学习辅导
- [Google 学习LM / Gemini 教育委员会](https://blog.google/products-and-platforms/products/education/google-learnlm-gemini-generative-ai/) - 托管参考模型
- [Quizlet Q- hat 键盘](https://quizlet.com) ——备选参考
- [综合导师](https://www.synthesis.com) 启动参考
- [FRS 算法](https://github.com/open-spaced-repetition/fsrs4anki) - 空格重复排程器
- [贝叶斯知识追踪](https://en.wikipedia.org/wiki/Bayesian_knowledge_tracing) 学习者模型经典
- [LiveKit Agents](https://github.com/livekit/agents) - 语音堆叠
