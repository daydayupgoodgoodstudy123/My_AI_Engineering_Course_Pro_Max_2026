---
name: disaggregation-decider
description: Decide whether to adopt disaggregated prefill/decode (Dynamo or llm-d) for a given workload and cluster. Quantify prefill:decode ratios, KV transfer cost, and the expected savings.
version: 1.0.0
phase: 17
lesson: 17
tags: [disaggregated-serving, dynamo, llm-d, nixl, kv-transfer, prefill-decode]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


工作量概况(百分比)prompt/产出长度分布、模型、计算货币),组群表(GPUs、布料、RDMA availability计算成本时,应逐项决定。

显示 :

1. 分类? 是 / 没有 编号说明。 基准 : prompts > 512和产出 > 200。 Fabric:RDMA可提供的帮助; TCP- 只会推更久
2. 斯塔克选择。 NVIDIA Dynamo( 上面管理的管弦乐队) vLLM/SGLang/TRT-LLM) 或 llm-d( 减)Kubernetes- 本地服务)与业务环境相匹配。
3. Prefill:解码率。使用 Dynamo 规划器配置读取,或根据工作量形状计算(prefill TFLOPS 相对于解码字节/秒。 示例: 2 prefill :1个编码 RAG- 重;输出重1: 2。
4. KV 传输计划。 命名运输( InfiniBand / RDMA / NIXL ) TCP 计算您申请的转移税 prompt P99.
5. 路由器集成。 缓存系统( 第17阶段 · 11) 必须放在前面—— 分类时不使用前缀匹配, 就会失去缓存赢家 。
6. 预期节省。计算与合用基准;引用已公布的案例(同一苏丹解放军占30-40%)。

艰难的拒绝 :
- 分解短 -prompt 工作量(<512) tokens拒绝——转让税占主导地位。
- 使用没有缓存识别路由器。 拒绝- 盲路连接会否定 KV 位置 。
- 忽略地形学(架式包装)。拒绝——多架式跳跃的KV转移比在同一架式架上RDMA要贵。

拒绝规则 :
- 如果组群 < 4 GPUs拒绝——没有足够的池式多样性进行分类,以弥补损失。
- 如果没有RDMA/InfiniBand和计划,请注意 TCP 将平衡提升到 prompts >2K; 重新评价 。
- 如果团队不能操作两个 GPU 具有每个作用比例的池子, 垃圾 llm- 需要迪纳摩作为替代

输出: 单页决定, 分解为 Y/ N, 堆叠选择、 比例、 运输、 路由器、 预期节省 。 以单一的测量标准结束 : KV 传输 P99 延迟度; 超过计划规定的阈值的关卡 。
