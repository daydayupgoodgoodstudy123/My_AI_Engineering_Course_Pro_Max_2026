---
name: inference-platform-picker
description: Pick an inference platform (Fireworks, Together, Baseten, Modal, Replicate, Anyscale, or custom silicon) given workload, SLA, budget, and operational constraints. Normalize per-token, per-minute, and per-prediction pricing.
version: 1.0.0
phase: 17
lesson: 02
tags: [inference, fireworks, together, baseten, modal, replicate, anyscale, economics]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以工作量概况(模型, tokens每日持续利用,TTFT SLA,爆破系数,遵守, Python 提供平台建议。

显示 :

1. 主平台。 命名平台和特定定价级别( 服务器与专用的量比) 。 合理使用匹配的工作量特性, 比如“ 无烟服务器, 因为TTFT < 500 ms 是 SLA, 交通会爆炸 ” 。
2. 有效成本:将选定的定价模式正常化为美元/美元产出 tokens。与至少两个选项相比,每分钟每分钟的频率会呼唤出来token 或反之亦然。
3. 冷启动计划。 对于无服务器的选取( Fireworks、 Modal、 Replicate), 状态为冷启动时的延迟时间和缓冲( 升温前, 分钟)_工人=1, 现场移民。 对于专用的选取( Baseten, Anyscale), 请跳过此节, 但注意权衡 。
4. 运行者上。 命名第二个平台和您切换的明亮条件( 例如, “ 如果我们关闭需要 HIPA + 专用的企业交易, 移动到 Baseten ” ) GPUs").
5. 网关层。 建议是否在平台前安装一个AI网关( LiteLLM、 Portkey、 Kong AI Gatep) , 将产品从供应商的网关中分离出来 。 默认值: 是, 除非比例低于500 RPS 。

艰难的拒绝 :
- 比较每 -token 拒绝并坚持要求有效的美元/百万 tokens.
- 选择烟花是因为它“最快” 而不比公布的基准 验证TTFT SLA
- 向非延迟工作量推荐自定义硅(Groq、Cerebras、SambaNova),价格高低,仅以互动的SLA为借口。

拒绝规则 :
- 如果工作量要求有一个规范框架(SOC 2 第二类,HIPAA),而客户选择模式或复制,则拒绝——企业的足迹与Baseten或Anys标的一样。
- 如果预期的交通量低于100公里 tokens/ 日, 拒绝推荐每分钟( 巴斯顿、 模式、 任何尺度) 。 经济学不起作用 — 默认为市场( OpenRouter、 DeepInfra) 或管理好的超标 。
- 如果客户想要“最便宜的”,请注明多维成本函数( ) 。token +冷开始+归属+网关+DX)。

产出:一页建议,指向主平台、有效成本、冷却启动计划、跑步、网关姿势。 以显示错误选择的单一度量结束( 冷却启动 P99, /)token 使用率(或利用漂移)
