---
name: obs-platform-wiring
description: Pick an observability platform (Langfuse, Phoenix, Opik, Datadog) and wire traces + evals + prompt versions into an existing agent.
version: 1.0.0
phase: 14
lesson: 24
tags: [observability, langfuse, phoenix, opik, datadog, tracing]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 agent 运行时间和产品要求,选 observability 平台和脚架 电线。

Decision:

1. Need prompt 管理+会话重播一个地方 - > **Langfuse**.
2. 需要深层的 RAG 相关+漂移/异常探测 - > **Phoenix**.
3. 需要自动化 prompt 优化+PII guardrails -> **Opik**.
4. 已经运行数据犬 - > **Datadog LLM Observability** (原创图来自v1.37+)。
5. 需要无ELV2-无许可证 - > **Langfuse** (麻省理工学院)或 **Opik** (Apache 2.0);避免凤凰城纯粹的开放源码软件分布。

显示 :

1. OTel GenAI仪器(第23页)——这是常见的基底。
2. Platform-specific SDK 或 OTel 出口商配置。
3. LLM- 法官为您域( 事实正确性、 范围、 音量、 拒绝质量) 。
4. Prompt 编辑已连接到 traces (朗弗斯语)或 trace 组合配置( Phoenix) 或实验定义( Opik) 。
5. Guardrails 记录内容: PII 编辑, 秘密清洗。
6. 仪表板:会议健康、故障分类、潜伏分布、每次会议费用。

艰难的拒绝 :

- 运输没有评估,单是追踪就很昂贵。
- 使用自写 LLM- 判断没有外部核查。 CRITIC 模式(Lesson 05):法官需要外部工具来了解事实 grounding.
- 正在将 PII 存储到横跨体中。 总是外部存储 + 引用代号 。

拒绝规则 :

- 如果用户要求“一个平台为一切服务 ” , 拒绝并提供上述决定。 没有哪个平台能主导所有三个轴 。
- 如果产品对每种产品没有接受标准 agent 任务,拒绝装运反射器。 LLM- 法官需要一个标签;一个标签需要产品决定。
- 如果用户想要"不" sampling抓住一切" 拒绝 Trace 卷积,以线性标度; sampling 需要按比例(头或尾)计算。

输出: `instrumentation.py`, `judge.py`, `dashboards.md`, `README.md` 解释平台的选择,卢布, sampling 战略,以及 incident response。结尾处用“下一步读什么”表示30课(由电子产品驱动的发展)或26课(失败-模式分类)。
