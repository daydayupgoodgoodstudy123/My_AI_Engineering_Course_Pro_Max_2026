<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="hardware-specialized-inference-compilation--fp8-and-nvfp4-on-blackwell"></a>

# 针对硬件的 Inference 编译：Blackwell 上的 FP8 与 NVFP4

> Hardware-specialized inference 运输量的可移动性,以及TensorRT-LLM 仅用NVIDIA, 以Blackwell为调制, 是交易回报的最明显的例子。 orchestration半分析推断X 测量每百万12美元 tokens 120B型在Q1-Q2 2026年,H100+0.09/M美元 vLLM 7x经济差距。堆叠是三个浮动点制度,加起来:FP8对 KV cache 和 attention 内核,因为它具有所需的动态范围; NVFP4 (4 位微缩缩放) 控点 weights 和激活; 多个-token 预测(MTP)和分列 prefill/ 解码在顶部添加另外2-3x。 Day-0 模型支持负荷 FP4 weights 2026年工程队的捕获量:LLM 具有开放源码,但具体为荷兰国家人口与健康调查。 CUDA和布莱克威尔专业,所以采用它可以交换输送。在投入之前先计算出模型和硬件的组合。

**类型:** 学习
**语言:** Python (stdlib, 玩具 FP8/NVFP4 内存和成本计算器)
**先修要求:** 阶段17 · 04(内部维修发动机),阶段10 · 13 (Quantization)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么FP8仍然对 KV cache 和 attention 即使在 weights 已在NVFP4中。
- 计算BF16、FP8和NVFP4下一个前沿模型的HBM足迹以及节省经费的来源。
- 命名为 Blackwell 特定 features TRT-LLM 开发(第4号PFP日、第4号MTP日、第3号PFP disaggregated serving全部的原始人。
- 什么时候决定 TRT -LLM值 7x 成本差与 7 的 NVIDIA 锁定值 vLLM 霍伯号

<a id="the-problem"></a>

## 问题

边界 inference 2026年经济学是"有多少 tokens 答案取决于四个堆叠的选择:硬件生成(H100/H200对Blackwell B200/GB200),精度(BF16 + FP8 + NVFP4),服务引擎(FS发动机)。vLLM 与 SGLang 和TRT - 都已经是LLM), 和 orchestration 与Dynamo相比,

和霍伯一起在船上 vLLM,一个 120B MoE 运行量~0.09美元/百万 tokens和TRT公司一起在布莱克威尔LLM + 迪纳摩,同一模型运行量~0.012美元,价格低7x。GPU LLM 程序对着霍伯。 有些是堆叠: FP4 weightsMTP草案,分列 prefill和NVLink 5 全部 MoE 专家交流。

您无法在 NVIDIA 堆放之外复制这个。 这就是权衡—— 经济的可移动性。 理解堆放选择给哪个部分的缺口是这一教训的要点 。

<a id="the-concept"></a>

## 概念

<a id="why-fp8-is-still-the-floor-for-kv-cache"></a>

### 为什么FP8仍然是 KV cache

2026年的一个常见错误:假设NVFP4在所有地方适用,但并不适用。 KV cache 需要 FP8 (8- 位浮动点) , 因为它存储 attention 键和数值的动态范围很广。 KV 量化为 FP4 会造成灾难性的精确性损失——分布的尾部会下降, attention 分数崩溃。 FP8 的指数位给 KV cache 需要的距离。

NVFP4 (2025-2026)适用于 weights 微缩缩放: weights 具有自己的比例系数,这样小块可以跨越不同的动态范围,而没有每个tensor 启动时, FP4 保持,因为激活在一层内是小范围。

典型的 Blackwell 配置 :

- Weights: NVFP4 (4 位微缩缩放)。
- 活动:NVFP4。
- KV cache目标:
- Attention 累计数: FP32 ()softmax stability).

<a id="the-blackwell-specific-primitives-trt-llm-uses"></a>

### 布莱克威尔的原始人TRTLLM 使用

- **日0 FP4 节点 weights**: 模范供应商船舶FP4 weights 直接; TRT- 键LLM 未经培训后转换的负荷。 FP4 没有 AWQ/ GPTQ 级。
- **Multi-token 预测(MTP)**:与EAGLE(17 ° 05)相同,但已纳入技术审查小组 -- --LLM build.
- **Disaggregated serving**: prefill 并分开解码 GPU pools, KV cache 由NVLink或InfiniBand转让的。与Dynamo(17阶段20)相同。
- **通向所有交流的原始元素**: NVLink 5 切开 MoE 专家沟通的延迟 3x对霍普。LLM的 MoE 内核都为此而调整
- **NVFP4 + MXFP8 微缩缩放**: Blackwell 上的硬件加速比例因素处理 Tensor Cores.

<a id="the-numbers-you-should-memorize"></a>

### 数字你应该记住

- HGX B200 通过 TRT-LLM 运行 GPT-OSS-120B，每百万 tokens 的成本为 $0.02。
- 千瓦特/米,千瓦特/千瓦特 tokens 经由迪纳摩(操纵TRT-LLM).
- H100+ 数 vLLM $0.09/M tokens 工作量相当。
- 2.8 短期转拨方案三个月内增加的产量LLM 更新(2026)。
- 11-15x /GPU LLM 布莱克威尔和霍普
- MLPerf Inference v6.0 (2026年4月):Blackwell主导了提交的各项任务。

<a id="what-fp4-actually-costs-in-quality"></a>

### 4级PF4实际在质量上的成本

NVFP4 具有很强的进取性。chain-of-thought,数学,代码元,长上下文),FP4 weights 明显降解。 calibration 团队航运推理模型经常使用FP8 weights + FP4 激活作为一种折中,或始终坚持H200和FP8。

规则: 总是验证您的任务质量 eval set 承诺使用NVFP4之前 weights.

<a id="why-this-is-an-nvidia-lock-decision"></a>

### 为什么这是NVIDIA的锁决定

TRT-LLM 是 C+++ + 键。 CUDA +封闭源内核。 GPU SKU. 没有AMD,没有英特尔,没有ARM。如果你的次策略是多供应商,TRT-LLM 是 TRT 的未启动器 --LLM- 服务级 - 你仍然可以从 vLLM 使用混合硬件。如果您是 NVIDIA 专用,则7x 差值支付锁。

<a id="2026-practical-recipe"></a>

### 2026年实际食谱

用于100万元以上年度 inference 账单,运行在霍伯+ vLLM 将成本主要的工作量移到Blackwell+TRT-LLM + 迪纳摩,保持H100+的试验水平 vLLM 用于模型迭代速度。在生产前对每个NVFP4型号的转换模型进行质量验证。

<a id="the-disaggregation-bonus"></a>

### 分解奖金

TRT-LLM的 disaggregated serving (separate prefill 20. 在Blackwell,乘数堆:FP4 weights × MTP 加速 × 分解位置 × 缓存识别路由。 7x 数假定整个堆栈 。

```figure
pipeline-parallel
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 计算HBM足迹,解码通过量(受备忘录约束的制度)和美元/元-tokens 三个堆叠模型的模型: H100 + BF16 + vLLM, H100 + FP8 + 组合键 vLLM, B200 + NVFP4/FP8 + TRT-LLM。运行它以查看复合效应和每个变化所促成的缺口份额。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-trtllm-blackwell-advisor.md`. 考虑到工作量、型号大小和年度 token 音量,它决定 布莱克威尔+TRT -LLM 堆叠值 NVIDIA 锁定 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。在120B上 MoE 30%的活动率 parameters计算H100 BF16、H100 FP8和B200 NVFP4/FP8上的内存带宽限解码通过量。
2. 客户每年花200万美元在H100+上 vLLM。黑威尔的平衡数字是多少? GPUs 他们需要买一个 重新配给移民到TRT -LLM 12个月后,鉴于7x经济差距?
3. 精确度在 NVFP4 之后下降 3 点 weight 转换。 列出两个回收路径: 一个质量第一( 保留 FP8) weights),成本第一(与内域数据对比)。
4. 读取 MLPerf v6. 0 inference 结果。 哪个任务有最小的黑well -over - hopper差距, 为什么?
5. 计算 NVFP4 上405B型号所需的 HBM weights + FP8 组合键 KV cache ,在 128 k 上下文。 它是否适合一个 GB200 NVL72 节点 ?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| FP8 | 八位浮标 | 8 位浮动点; 用于 KV cache 和 attention 原因是动态范围 |
| NVFP4 | 四位数微 | NVIDIA 的四位微缩缩微缩微缩微缩微缩微缩微缩微缩微缩FP格式; weights 和启动在 Blackwell |
| MXFP8 | "MX 8" (MX 8) (MX 8) (MX 8) (MX 8) | 微缩缩放 FP8 变体; 在 Blackwell 上加速硬件 Tensor Cores |
| 日0 FP4 节点 | "FP4号船 weights" | 示范供应商发布 weights 已在FP4中;没有培训后转换步骤 |
| MTP | "multi-token prediction" | TRT-LLM综合投机-编码草案(第17阶段 -05) |
| Disaggregated serving | "split prefill/decode" | Prefill 并分开解码 GPU 集合; 通过 NVLink/IB 传输的 KV |
| All-to-all | "MoE 专家通讯" | 通信模式路径 tokens 改为专家 GPUs; NVLink 5 切换 3x |
| InferenceX | "SemiAnalysis inference bench" | 2026年行业接受的成本 - 每一个 -token benchmark |

<a id="further-reading"></a>

## 进一步阅读

- [NVIDIA - 黑威尔超高频多频波 Inference v6.0](https://developer.nvidia.com/blog/nvidia-blackwell-ultra-sets-new-inference-records-in-mlperf-debut/) - 2026年4月MLPerf的结果。
- [荷兰 -- -- MoE Inference 布莱克威尔](https://developer.nvidia.com/blog/delivering-massive-performance-leaps-for-mixture-of-experts-inference-on-nvidia-blackwell/) - 5号全对齐 MoE kernels.
- [TensorRT-LLM Overview](https://nvidia.github.io/TensorRT-LLM/overview.html) 正式引擎文件。
- [NVIDIA - 介绍迪纳摩](https://developer.nvidia.com/blog/introducing-nvidia-dynamo-a-low-latency-distributed-inference-framework-for-scaling-reasoning-ai-models/) ——分列 orchestration 技术专栏以上LLM.
- [MLPerf Inference](https://mlcommons.org/benchmarks/inference-datacenter/) 出版布莱克威尔数字的基准套件
