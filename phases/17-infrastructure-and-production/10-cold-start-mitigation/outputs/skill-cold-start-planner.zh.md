---
name: cold-start-planner
description: Pick and stack cold-start mitigations for serverless LLM deployments. Budget phases (node, image, weights, engine, first forward) and match mitigations to SLA.
version: 1.0.0
phase: 17
lesson: 10
tags: [cold-start, serverless, bottlerocket, model-streamer, gpu-snapshot, warm-pool, serverlessllm]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于模型规模,SLA(TTFT P99)、交通状况(稳定与爆炸)和预算态势,产生了一个冷启动减缓计划。

显示 :

1. 冷启动预算。 拆分原始冷启动路径( 节点提供、 图像拉动, ) weights 改为 HBM, 引擎前置, 向前。 使用 2026 个标称秒来表示标称的模型大小 。
2. 选择层。 选择使总数低于 SLA 的最低层数: 预种子图像( L1) , 模型流器( L2) GPU 快速(L3)、暖池(L4)、分层装载(L5),根据每一层攻击的具体阶段说明理由。
3. 暖池缩放。 `min_workers` 如果在70B+型号上,SLA是TTFT P99 < 60,则不论费用多少,都必须提供热池。
4. 费用估计数。 GPU 选择的暖池的费用和每天预计的冷开关数。
5. 尾板政策。 使用新复制品的第一用户会怎样? 他们被排队到暖重复制品,还是他们支付冷启动税? 列出具体的政策( 比如“ 先在10秒内申请任何热复制品; 切入冷冻 ” ) 。
6. 失败模式。 如果一个温暖的复制品在会话中死亡, 会怎样? 恢复是自动( 实时迁移) , 还是下一个请求是冷淡的开始 ?

艰难的拒绝 :
- 提议"加热池",不计算月成本
- 要求减轻影响,而不设特定阶段,它会攻击(例如,“使用瓶子火箭”,不说它消除180年代的图像拉动)。
- 忽略了每个...GPU- 地形限制 GPU 照片——如果平台迁移 SKU,图片无效。

拒绝规则 :
- 如果SLA是TTFT P99 < 5, 在一个新的70B冷门起伏时没有暖池,则拒绝——数学上不可能以2026年基础设施速度。
- 如果预算禁止暖水池,但苏丹解放军需要30秒以下的冷气启动,请指明平台的具体办法(模式) GPU 照片,Baseten 预升) 拒绝在不同的平台上承诺
- 如果操作员要求使用有爆炸性交通和70B型号的降压到零,则拒绝向SLA承诺——数学没有快照或热水池就无法工作。

产出:一页计划列出阶段、层次、 `min_workers`,每月成本,尾板策略,故障模式。结束于一个警告标准:在最后滚动时段P99冷启动时间。
