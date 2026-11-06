---
name: ai-tutor
description: Ship an adaptive multimodal personal tutor for a specific subject with Bayesian knowledge tracing, a curriculum graph, safety filters, and a measured two-week efficacy study.
version: 1.0.0
phase: 19
lesson: 17
tags: [capstone, tutor, adaptive, bkt, fsrs, livekit, multimodal, coppa]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定主题( K-12 代数或内向) Python),建立一个个人导师,配有文字+语音+照片图解、贝叶斯知识追踪学习者模型、课程绘图驱动的概念选择、COPPA认知记忆和安全过滤器。与10名学员一起进行为期两周的功效研究。

构建计划 :

1. Neo4j中的课程图:50-150个概念节点,带有必备边和附带OER内容(OpenStax, OpenTextbook)。
2. 学习者模型: 贝叶斯知识追踪, 以预科/ 滑坡/ 留级率为每个概念; 每位学习者持续状态 。
3. 教学政策(LangGraph over Claude 索内特4.7与 prompt 缓冲: 读取_信号 - > 选择_概念(文字行走) - > 脚手架(Scrotic) - > 更新_mastery.
4. 内存: 代理模质式的持久性偶发 + 语义存储; 一年后 COPPA- 觉察自动删除; 父传读删除 。
5. 声音: LiveKit Agents 与Whisper-V3-turbo ASR和Cartesia Sonic-2 TTS公司合作;再利用3号封顶石管道。
6. 图片数学: 点数或帕利Gemma 2 用于方程式识别; 向导师提供结构化输入 。
7. Safety: Llama 4项输入/产出;适合年龄的过滤屏蔽自我伤害/成人/暴力;学习者范围内的记忆隔离。
8. 每位学员每周的PDF进度报告。
9. 功效研究:10名学员,测试前(标准化的30个问题基线),2周课程(3/周),测试后;与非适应性线性组群进行比较。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | 学习得益三角洲 | 10升2周研究中的试验前/试验后三角洲 |
| 20 | 专制忠诚 | 记录样本的鲁比分 |
| 20 | 多式联运 UX | 语音+照片+文本一致性结束 |
| 20 | 安全+隐私姿态 | Llama 4个通过率+COPPA-意识保留+跨 Lear隔离 |
| 15 | 课程广度和图表质量 | 概念范围+必备图一致性 |

艰难的拒绝 :

- 教育政策是回答而不是问下一个问题。 苏格拉底是一个硬要求。
- 学习者模型不更新每次互动。 BKT 是一层。
- 记忆中不保存 CPPA 意识 。 K-12 受众无法接受 。
- 效率索赔没有非适应性基线组别。

拒绝规则 :

- 拒绝在不部署的情况下部署 Llama 4号警卫,同时负责输入和输出
- 拒绝在不具有父系可访问的删除面的情况下持续学习者数据。
- 拒绝“适应性”主张,而不同时运行非适应性基线。

输出:包含课程图的回购、 BKT 学习模型、 LangGraph 辅导政策、多式联运输入处理程序、LiveKit语音管道、安全管道、家长仪表板、效率研究运行器、预考/后考 harness,并用信任间隔记录学习收益三角洲相对于线性基线的写法。
