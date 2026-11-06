---
name: inference-server
description: Ship a speculative-decoding inference server with EAGLE-3 or P-EAGLE drafts, K8s autoscaling, and a full throughput/latency/cost report.
version: 1.0.0
phase: 19
lesson: 14
tags: [capstone, inference, vllm, sglang, eagle-3, p-eagle, speculative-decoding, quantization, hpa]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给出两个开放的目标模式(Llama 3.3 70B和Quen3-Coder-30B MoE 或 GPT运输产品,包括 speculative decoding, quantization, 和 Kubernetes autoscaling。公布测量的加速度和尾部延缓度数字。

构建计划 :

1. 部署目标模型 vLLM 0.7 (或) SGLang 0.4)与FP8马林 quantization.
2. 从红帽子投机者(或通过斯佩克福日培训一个)装入一个对齐的 EAGLE-3 草稿。
3. 基准数: tokens和p50/p99的延迟期,第1/8/32批,无任何推测。
4. 启用 EAGLE-3。 重试相同的基准。 报告速度、 接受率, p99 尾延三角形 。
5. 启用 P- EAGLE 平行的猜测; 报告深树能帮助伤害的偏移 。
6. 运行分布基准: 共享 GPT、 人类val、 域数据。 发布接受率流。
7. 在第二个目标模型上重复( )MoE;确定接受草案的路径敏感度。
8. 部署在 Kubernetes 带有 HPA 跟踪 `queue_wait_ms`。当加载三重时,显示规模的缩小。
9. 比较美元/百万 tokens 与 Anthropic Claude 索内特4.7和 OpenAI GPT-5.4在匹配的电子逆向拍卖上

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | 测量的加速量与基准量 | 2.5x+ 两种模型的匹配质量输送量 |
| 20 | 现实交通的接受率 | 分发接受率报告 |
| 20 | P99 尾延纪律 | 第1/8/32批第99页,有或无投机 |
| 20 | Ops | K8 部署, HPA 排队等候, 平滑 rollout,排水管- 第一次升级 |
| 15 | 编写和方法 | 明确得出指标,符合基准 |

艰难的拒绝 :

- 报告稳定状态的通过量,无 tail latency.
- 高级管理局在 CPU 而不是排队等待,会打到 GPU saturation.
- 忽略目标草案版本 alignment. 漂流的草稿比没有猜测要贵。
- 省略主机的成本比较 APIs' prompt- 缓冲折扣

拒绝规则 :

- 拒绝在没有服役的情况下服役 rollout 提升在位,而请求正在飞行中,这是被取消资格的。
- 拒绝报告分布区的总接受率。
- 拒绝要求投机解码,在bs=32时胜出,没有匹配的非投机数字。

输出: 包含 vLLM / SGLang 配置, EAGLE-3 下载脚本草稿, K8 部署表, 队列等候的 HPA 配置, 基准 harness 用于共享 GPT / HumanEval / 域数据, a $/1M tokens 比较表,以及一个写入,命名三个尾部长回归 speculative decoding 引入和减缓(批量加热、 ngram 后退, quantization 都修好了,我还得再多一点
