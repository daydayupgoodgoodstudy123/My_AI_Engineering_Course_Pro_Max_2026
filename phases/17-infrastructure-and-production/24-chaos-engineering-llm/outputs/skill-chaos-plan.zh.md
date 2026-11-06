---
name: chaos-plan
description: Design an LLM chaos engineering plan — verify prerequisites, build four planes, pick tool, start with three safe experiments, enforce safety-plane gates.
version: 1.0.0
phase: 17
lesson: 24
tags: [chaos-engineering, litmuschaos, chaosmesh, harness, llm-chaos, game-day]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定堆栈( P)Kubernetes /管理下的脆弱妇女、 observability 质量,团队待命成熟度, 产生混乱计划。

显示 :

1. 检查前置设备。 校验 SLI/ SLO 定义, observability wired, rollback 自动、运行簿结构化、待命旋转。如果缺少的话,则拒绝运行生产混乱状态。
2. 四架飞机,每架飞机都列出工具(控制、目标、安全、 observability· 将阶段17指向13 observability.
3. 三个初步实验。 开始用舱号杀死。 然后是供应商 429, 然后内存超载。 每个都带有爆炸- 射线帽, 持续时间, 成功标准 。
4. 安全门。 燃烧速率( > 2x), 爆炸- 辐射线( < 30%的舰队), trace- ID标记,压压窗口。
5. 每周小金丝雀、每月游戏日(跨团队),季度复原力审计。
6. 工具:LitmusChaos(OSS,国家妇女儿童委员会毕业),Chaos Mesh(OSS,国家妇女儿童委员会毕业) sandbox), Harness 混乱(商业AI协助)、AWS FIS/Azure混亂工作室(管理云型)。

艰难的拒绝 :
- 生产混乱,没有五个先决条件。 拒绝将变成真正的事件。
- 实验没有雷射帽,拒绝
- 没有实验 trace识别器在标记 拒绝 无法解除警报

拒绝规则 :
- 如果团队从未成功进行一个实验 进行中,拒绝生产混乱 直到一个绿色的组合。
- 如果事件数量已经很高( > 2/周),则垃圾会增加混乱——先稳定下来。
- 如果团队没有SLO,请在任何实验前要求SLO。

产出:一页计划,附有先决条件检查、四架飞机工具、三个初步试验、安全门、音节。结束时有季度依赖图更新承诺。
