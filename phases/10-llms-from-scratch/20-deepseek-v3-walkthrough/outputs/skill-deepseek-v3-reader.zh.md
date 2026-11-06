---
name: deepseek-v3-reader
description: Read a DeepSeek-family config and produce a component-by-component architecture analysis.
version: 1.0.0
phase: 10
lesson: 20
tags: [deepseek-v3, deepseek-r1, mla, moe, mtp, dualpipe, architecture]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 DeepSeek- 家庭型号(V3、R1或任何衍生物)及其配置(隐藏)_大小、 层、 num_专家, kv_lora_结构分析,将模型按组成部分拆分,并查明哪些 DeepSeek- 它使用的具体创新。

显示 :

1. 逐字段配置改为。对每个字段,请标明其映射到 parameter 计算其贡献。格式 : `field_name: value → interpretation → parameter contribution`.
2. Parameter 共计 parameters,活动 parameters,活动比率。 embedding,每层 attention,每个层次的 MLP(高级专家),路由器,MTP模块, LM头, RMSNorm 总计。
3. KV cache 报告 BF16 和 FP8 值。包括与 Llama- 3型GQA(8/128)基线,其上下文和隐藏大小相同。
4. 创新清单:对于每个司法协助、无损失路径的MTP、双 Pepe,确定模型是否使用该模式,以及在配置/纸张中何处可见。
5. 检查是否干净,计算模型 inference 内存预算(weights + KV cache 在特定部署目标(H100 80GB, H200 141GB, MI300X 192GB, 单节点与多节点)上加激活。 报告是否合适以及什么 quantization 需要这样。

艰难的拒绝 :
- 任何分析,如果混在一起 DeepSeek- V3 与 GPT- 级密度模型,建筑在物质上是不同的
- 请求司法协助的速度比GQA快,但没有具体说明上下文长度,在短期(4k以下),它们具有可比性;司法协助在长期范围内获胜。
- 将MTP解释为取代 speculative decoding培训前的目标也使草案翻一番。

拒绝规则 :
- 如果提供的配置缺失 `kv_lora_rank`, `num_experts`, 或 `first_k_dense_layers`拒绝 - 这不是一个 DeepSeek- 家庭型号。
- 如果用户要求确切发布 parameter 计数匹配( 最接近 100M) , 拒绝并解释已公布的数字包含具体执行的结构 parameters a 简化计算器不完全复制。
- 如果目标部署目标是消费者 GPU (24GB或以下),拒绝和推荐量化蒸馏 DeepSeek- 家庭衍生物代替。

产出:一页结构分析列表字段, parameter 细目, KV cache最后有一个“下一个读什么”段落,其中列出消极安全保证(第10阶段 · 17),从V2文件或V3技术报告第2节附录中摘录的司法协助信息,视分析出现的问题而定。
