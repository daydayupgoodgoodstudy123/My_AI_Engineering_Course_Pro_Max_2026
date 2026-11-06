<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="disaggregated-prefilldecode--nvidia-dynamo-and-llm-d"></a>

# Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d

> Prefill 进行计算;解码为内存。同时运行 GPU 将资源分成不同的集合和转移 KV cache 或 位于NIXL(RDMA/InfiniBand或 TCP NVIDIA Dynamo(2025年德国技术合作公司宣布,1.0 GA) vLLM/SGLang/TRT-LLM 规划员+ SLA规划员自动匹配 prefillNVIDIA公布这个球场的产量收益——开发商.nvidia.com (2025-06)显示,在使用该球场方面有~6倍的改进。 DeepSeek-R1 MoE 和Dymona产品页(Developer.nvidia.com,未注明日期)广告,最多50x MoE GB300 NVL72 + Dynamo 与 Hopper 的比重。 “ 30x” 数字是全堆黑威尔+ Dymoon+ 的群落集合 DeepSeek-R1报告;我们没有发现一个主要来源确切地说30x,所以把它当作指示要求。 llm-d(红帽子+AWS)是 Kubernetes-native: prefill / 解码/路由器作为具有每个功能的HPA的独立服务。 llm-d 0.5 增加等级KV卸载,缓存识别 LoRA 路径、 UCCL 网络、 比例为零。 经济学: 内部对多个客户披露的扩展显示,$2M 类的节省率为30-40% inference 支出(即每年600-800K美元),从合用同一地点的服务转为按固定的苏丹解放军标准与迪纳摩分解;具体的数字为2M_600-800K美元,是内部综合数据,而不是一个已公布的案例研究——用它作为按重量顺序排列的锚,而不是参考引用。 prompts (<512 tokens,产出的短) 无法证明转移成本的合理性。

**类型:** 学习
**语言:** Python (stdlib, 玩具分解Vs 位置相同的模拟器)
**先修要求:** 阶段17 -04(内部维修发动机),阶段17 -08(Inference Metrics)
**时间：** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释一下 prefill 解码法和解码法是不同的 GPU 将废物分配到同一地点,并量化其数量。
- 分类结构图 : prefill 游泳池,解码池, KV通过 NIXL,路由器传输。
- 分解不回报时指定条件( 短时间) prompts产出(简称:产出)
- 将NVIDIA Dynamo(堆放在上方)从 llm-d( 减)Kubernetes- 与每个操作环境相匹配。

<a id="the-problem"></a>

## 问题

你在 8 张 H100 上运行 Llama 3.3 70B。在混合工作负载下（较长的 prompts、较短的输出），解码期间 GPUs 闲置，因为大部分计算都用于 prefill。在另一种工作负载下（较短的 prompts、较长的输出），情况恰好相反。将 prefill 与解码部署在同一组资源上，意味着两者都需要过量配置。

预算影响:占预算的20-40% GPU 时间浪费在错误的资源上。 您正在购买 H100 计算来运行内存解码, 或者购买 H100 HBM 带宽来运行内存解码 prefill两者都是昂贵的浪费。

分类拆分 prefill 并解码到不同的池子上 大小为每个人的瓶颈。 KV cache 转自 prefill 游泳池通过高带宽连接解码池

<a id="the-concept"></a>

## 概念

<a id="why-the-bottlenecks-differ"></a>

### 为什么瓶颈不同

**Prefill** - 运行 transformer 覆盖到全部输入 prompt 矩阵乘法占主导; 计算。 H100 FP8 给出 ~ 2000 TFLOPS 的有用输出。 批量效率是好的, 一个前方进程 。 tokens.

**Decode** - 产生一个 token 一次读完 weights 每一次循环。 内存带宽 。 HBM3 给出~ 3 TB/ s。 批量效率只有在高通货率下才能好。 weights 读一下批量的阿莫蒂兹

把它们放在一起: 你买 GPUs 两者都优化。 H100 两种方法都好,但成本都一样。 在规模上,您想要 prefill H100/计算重度;在H200/内存重度或具有攻击性的冲洗池 quantization.

<a id="the-architecture"></a>

### 架构

```
            ┌──────────────┐
  Request → │    Router    │ ───────────────────────┐
            └──────┬───────┘                        │
                   │                                │
                   ▼ (prompt only)                  │
            ┌──────────────┐    KV cache    ┌───────▼──────┐
            │ Prefill pool │ ─── NIXL ────► │ Decode pool  │
            │  (compute)   │                │  (memory)    │
            └──────────────┘                └──────┬───────┘
                                                   │ tokens
                                                   ▼
                                                 Client
```

NIXL 是 NVIDIA 的节点间传输。 使用 RDMA/ InfiniBand 时可用, TCP 转移潜伏是真实的——通常为20-80毫秒。 KV cache 4K - 4K - 4K - 4K - 4K - 4Ktoken prompt 70B FP8. 这就是为什么短 prompts 不可分解: 转移税超过储蓄。

<a id="dynamo-vs-llm-d"></a>

### 迪纳摩对战 llm-d

**尼加拉瓜迪纳摩** (2025年德国技术合作公司宣布,1.0GA):
- 以上座位 vLLM, SGLang转盘LLM 做一个管弦乐队
- 规划员配置员衡量工作量,SLA规划员自动配置 prefill:解码率。
- Rust core, Python extensibility.
- 产出收益:荷兰人口与健康研究所报告 DeepSeek-R1 MoE 2025-06年,关于中长期制度(Developer.nvidia.com)的GB200 NVL72+Dynamo;关于全黑威尔+Dymona+的“30x”的社区报告 DeepSeek-R1堆叠缺乏单一的主要源,应作为方向性处理。
- GB300 NVL72 + 迪纳摩:最多50x MoE 德纳摩产品页面上的吞吐量与霍伯(Developer.nvidia.com,未注明日期)。

**llm-d** (红帽子+AWS, Kubernetes-native):
- Prefill / 独立解码/路由器 Kubernetes Services.
- 具有队列深度的每个功能 HPA ()prefill/ KV利用(编码)信号。
- `topologyConstraint packDomain: rack` packs prefill+ + 在同一架子上为高频宽的 KV 传输解码 cliques。
- llm-d 0.5 (2026): 级KV卸载,缓冲装置 LoRA 路线,UCCL网络, 比例为零。

如果您想要管理好的堆叠比对管弦乐, 请使用 Dynamo 。 使用 llm- 如果你想的话 Kubernetes- 原始的原始生物,并致力于国家森林理事会的生态系统。

<a id="economics"></a>

### Economics

内部复合(没有一份已公布的案例研究——按重量顺序排列的锚)

- $2M/year inference 花在同地服务上
- 切换成Dymona的分类
- 同样的申请数量,同样的P99潜伏式苏丹解放军。
- 报告的节余:每年600K-800K美元(减少30-40%)。
- 没有新的硬件。

我们综合了多客户披露的这一数字,而不是一个可同比的案例研究;最接近的数据点是Baseten的2x速度快的TTFT/61%的通过量,包括Dynamo KV路由(基准线,2025-10年)和VAST+CoreWeave预测的60-130%以上。 tokens以40-60%的KV点击率(Vastdata.com,2025-12)为单位的美元,每个池子的正确规模都产生节余; prefill- 工作量繁重(RAG 使用8K+前缀)的受益大于平衡。

<a id="when-not-to-disaggregate"></a>

### 不分类时

- Prompts < 512 tokens 产出 < 200 tokens:转让税占收益的主导地位。
- 小型组群( < 4) GPUs: 池内多样性不够。
- 小队不能两队行动 GPU 以每个功能缩放方式游泳的池子:
- 没有 RDMA 布料 : TCP 转让税比较重。

<a id="the-router-integrates-with-phase-17--11"></a>

### 路由器与第17阶段结合

分解路由器是KV-cache-aware(第17阶段 11) 。 请求在预置其前缀的解码池上的土地,如果与该源码不匹配,则会流动 prefill 解码。点击率和分解化合物——隐藏识别路由器决定是否是新的 prefill 连需要都行

<a id="moe-on-blackwell-is-where-the-real-numbers-are"></a>

### MoE 黑威尔的真数字

GB300 NVL72+迪纳摩显示50x MoE 荷伯基线的排气量 MoE 专家路线计算重 prefill 解码时记忆力过大(专家缓存),所以分类是双赢。 model serving 是 MoE- 占优势(占优势)DeepSeek-V3,未来 GPT-5种变体)。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

基准数字的变动——荷兰人口与健康调查 inference 堆叠日志每季度更新结果。 引用前重新检查 。

- DeepSeek- R1,在GB200 NVL72+Dynamo:~6x 吞吐量与中等延缓制的基线(Developer.nvidia.com,2025-06);社区对全黑威尔+Dynamo堆的“30x”索赔是没有单一主要来源的方向总合。
- GB300 NVL72 + 迪纳摩:最多50x MoE 吞吐量对霍伯(开发者.nvidia.com,未注明日期)。
- 储蓄支柱(内部综合,不是一个案例研究):每年在固定的苏丹解放军每年支出2M美元,但有600-800K美元。
- 分解阈值 : prompts >512 tokens +产出 > 200 tokens.
- 通过NIXL的KV传输: 20-80毫秒,4K-prompt 70B FP8号,KV

```figure
prefill-decode-split
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟合用同一位置 disaggregated serving报告完成量、每项请求的费用以及 prompt- 长交叉

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-disaggregation-decider.md`鉴于工作量和组群,决定是否分列。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。在什么情况下 prompt 分解比合用同一地点要长吗 ?
2. 设计 prefill 用于 RAG 具有P99前缀长度8K的服务,输出300。
3. 迪纳摩对战 llm-d: 选一个纯的...Kubernetes 店铺没有 Python 运行时间偏好 。
4. 计算KV传输费用:4K prefill 70B FP8 =~ 500 MB KV.在RDMA 100 GB/s, 传输= 5 ms. TCP 10GB/s=50毫秒。 与你的SLA有什么关系?
5. MoE 专家路径改变 KV 访问模式。 分类如何运行 : MoE 激活不同的专家 token?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Disaggregated serving | "split prefill/decode" | Separate GPU 每个阶段的集合 |
| NIXL | "荷兰铁路运输公司" | 迪纳摩的KV中间节转移(RDMA/TCP) |
| 尼加拉瓜迪纳摩 | 指挥者 | 堆叠比对的协调员 vLLM/SGLang/TRT-LLM |
| llm-d | "Kubernetes native" | 红帽子 + AWS K8 分解堆栈 |
| 规划器配置程序 | 迪纳摩自动配置 | 衡量工作量,配置集合比率 |
| 苏丹解放军规划员 | "德纳摩政策" | Auto-rate-matches prefill: 解码以满足 SLOs |
| `packDomain: rack` | "llm- 地表学" | Pack prefill+Docode 在同一架上快速 KV |
| UCCL | "团结的团体" | llm-d 0.5级网络,以至零 |
| MoE 专家路线 | "专家/ token" | DeepSeek-V3 模式;分类帮助 |

<a id="further-reading"></a>

## 进一步阅读

- [NVIDIA - 介绍迪纳摩](https://developer.nvidia.com/blog/introducing-nvidia-dynamo-a-low-latency-distributed-inference-framework-for-scaling-reasoning-ai-models/)
- [NVIDIA - 分类 LLM Inference 在 Kubernetes](https://developer.nvidia.com/blog/deploying-disaggregated-llm-inference-workloads-on-kubernetes/)
- [TensorRT-LLM Disaggregated Serving blog](https://nvidia.github.io/TensorRT-LLM/blogs/tech_blog/blog5_Disaggregated_Serving_in_TensorRT-LLM.html)
- [llm-d GitHub](https://github.com/llm-d/llm-d)
- [llm- d 0.5 发号说明](https://github.com/llm-d/llm-d/releases)
