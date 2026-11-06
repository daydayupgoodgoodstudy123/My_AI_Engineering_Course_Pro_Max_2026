<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="production-quantization--awq-gptq-gguf-k-quants-fp8-mxfp4nvfp4"></a>

# 生产环境中的 Quantization：AWQ、GPTQ、GGUF K-quants、FP8、MXFP4/NVFP4

> Quantization 格式并不是一个普遍的选择——它是由硬件、服务引擎和工作量组成的。_K_M或Q5级_K_拥有 CPU 和边缘,通过 llama.cpp和Ollama 球赛赢 vLLM 当你需要多 -LoRA 与 Marlin-AWQ 核心相伴的 AWQ 提供~ 741 吨/秒, 以7B 级模型为主, 在 INT4 上是最佳通道@ 1 , 即 2026 个数据中心生产默认值。 FP8 位于Hopper、 Ada 和 Blackwell 的中间地带, 几乎无损且得到广泛支持。 NVFP 4 和 MXFP4 (黑色井微缩缩缩放) 具有攻击性, 需要每个街区验证。 两个陷阱咬入队 : calibration 数据集必须与部署域匹配, KV cache 与 weight quantization AWQ课 "我的模型现在是4GB" 忘记了10 -30GB KV cache 生产中的 batch sizes.

**类型:** 学习
**语言:** Python (格式间对齐的平面、玩具内存和输送量比较)
**先修要求:** 阶段10 · 13 (Quantization · 04(内部维修发动机)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 6个产品名称 quantization 2026年的时尚和甜点
- 选择给定的硬件格式( F)CPU 与 GPU引擎vLLM转盘LLM, llama.cpp),以及工作量(例行对话、推理、多LoRA).
- 计算 weight 内存保存 KV cache 留空用于所选格式。
- 名称 calibration- 数据设置陷阱,会降低域流量的量化模型。

<a id="the-problem"></a>

## 问题

Quantization 减少内存和 HBM 带宽, 这正是解码需要的。 FP16 70B 模式是 140GB weights。量化 weights 型号为35GB-在一个H100中装有空间 KV cache,因为以128个同时序列和 2k 上下文, KV cache 单是20 -30GB

但 quantization 并非自由的。 具有侵略性 quantization 降低质量, 特别是在推理重度任务中。 不同的格式对不同的引擎起作用。 不同的硬件支持不同精度。 2026 格式动物园是真实的, 您无法复制别人的选择 —— 您必须根据您的堆叠选择 。

<a id="the-concept"></a>

## 概念

<a id="the-six-formats"></a>

### 六种格式

| 格式 | 位 | 甜点 | Engines |
|--------|------|-----------|---------|
| GGUF 问题4_K_M/Q5 级_K_M | 4-5 | CPU,边缘,膝上型计算机 | llama. cpp, 欧拉马 |
| GPTQ | 4-8 | Multi-LoRA 在 vLLM | vLLM, TGI , 数字 |
| AWQ | 4 | Datacenter GPU production | vLLM 信息技术和信息技术司 |
| FP8 | 8 | 霍伯/阿达/布莱克韦尔数据中心 | vLLM转盘LLM, SGLang |
| MXFP4 | 4 | 布莱克威尔多用户 | TRT-LLM |
| NVFP4 | 4 | 布莱克威尔多用户 | TRT-LLM |

<a id="gguf--the-cpuedge-default"></a>

### 一般事务人员—— CPU/边缘默认

GGUF 是文件格式, 不是 quantization 方案本身——它捆绑 K 量变量(Q2)_K, 问题3_K_问题4_K_M, 问题5_K_M, 问题6_K, 问题8_在一个容器中。_K_M和Q5 级_K_M是生产默认值——接近BF16质量的4-5位元。 CPU 或边缘服务 llama.cpp是迄今为止最快的 CPU inference engine.

产出罚款 vLLM:~93吨/秒,在 7B - 格式未优化 GPU 内核。 当部署目标为 GGUF 时使用 CPU塞奇,别这样

<a id="gptq--multi-lora-in-vllm"></a>

### GPTQ——多功能-LoRA 在 vLLM

通用职业技术教育标准是培训后课程 quantization 算法 calibration 过,马林内核能快速 GPU (2.6x加速度相对于非马林 GPTQ) ~ 7B 上的 712 吨/秒。

唯一赢家: GPTQ- Int4 支持 LoRA 适配器 vLLM。如果您正在使用一个基数模型加上10-50微调变体(每个变体都作为 LoRA), GPTQ 就是你的路径。 NVFP4 不支持 LoRA 2026年初时

<a id="awq--the-datacenter-gpu-default"></a>

### AWQ - 数据中心 GPU 默认

Activation-aware Weight Quantization。保护~1%的最高级 weights during quantization. Marlin-AWQ内核:10.9x加速速度与天真。~7B7T, 最佳出入口@1, INT4格式。

选择 AWQ 用于新 GPU 服务,除非你需要多 -LoRA 或攻击性Blackwell FP4(NVFP4)。

<a id="fp8--the-reliable-middle"></a>

### FP8——可靠的中间点

8 位浮动点, 近乎无损, 得到广泛支持。 Hopper Tensor 核心加速了本地的 FP8 。 Blackwell 继承了。 FP8 是质量不可谈判( 合理、 医学、 代码) 时的2026 个安全默认值。 内存储蓄是INT4 的一半, 但质量风险要低得多 。

<a id="mxfp4--nvfp4--blackwell-aggressive"></a>

### 4/NVFP4-Blackwell攻击性

微缩缩缩放 FP4。 weights 黑色威尔的进攻性但硬件加速 Tensor 核心。 将每字节减半 token 与FP8相比,17 -07阶段的经济胜利。

Caveats:
- 否 LoRA 支助(2026年初)。
- 推理工作量过重,质量明显下降。
- 校验您的 eval set 每一个模型。

<a id="the-calibration-trap"></a>

### 该 calibration trap

AWQ和GPTQ要求 calibration 数据集——通常是C4或WikitText。对于域模型(代码、医学、法律),在通用网络文本上校准,使算法对哪些 weights 保护。 人类val 上的 Pass@ 1 可以降低几个点 。

修正: 校准内域数据。 数百个域样通常足够。 测试 eval set 船运前

<a id="the-kv-cache-trap"></a>

### 该 KV cache trap

AWQ 缩略语 weights 至 4 位数。 KV cache 单设,留在FP16/FP8。

- Weights:~35GB(140GB的INT4)。
- KV cache 以128 共x 2k 上下文:~20GB。
- 活动:~5GB。
- 总计:~60GB-符合H100 80GB。

基本上,“我用量子计算我的模型到4GB” 完全忘记了其他30-50GB。

Separately, KV cache quantization 选择(FP8 KV或INT8 KV)是不同的选择, attention 准确性直接,不是免费的胜利。

<a id="awq-int4-is-hazardous-for-reasoning"></a>

### AWQINT4 具有推理危险

Chain-of-thought数学,代码和长的外缘——这些都明显受到攻击性的影响。 quantization。AWQINT4 丢失了MATH 的 ~ 3-5 点。对于推理工作量过重,船舶 FP8 或 BF16 , 接受内存成本 。

<a id="2026-picking-guide"></a>

### 2026 选取向导

- CPU/边缘服务:GGUF Q4_K_完成任务
- GPU 服务,例行聊天,没有 LoRA:AWQ。 (美国著名音乐家)
- GPU 服务,多 -LoRA与马林的GPTQ。
- 说明工作量:
- 黑威尔数据中心,验证质量:NVFP4 + FP8 KV。
- 模糊不清:对每个候选人的格式进行1,000个样本的评审。

```figure
gpu-memory-breakdown
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 计算记忆足迹(weights + KV+激活)和六种格式的相对输送量,用于各种模型大小。 KV cache 占主导地位,其中 weight 压缩是付费的, FP8 是安全的选取。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-quantization-picker.md`。考虑到硬件、型号大小、工作量类型和质量容忍度,选择一种格式并产生一种 calibration/验证计划。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。对于一个 70B 模型,在 128 与 2k 上下文同时使用,计算每个格式的 HBM 总计。哪个格式允许您在一个 H100 80GB 上配置?
2. 您有一个 7B 编码模式。 选择格式和理由。 如果您对质量容忍度有错误, 那么恢复路径是什么 ?
3. 计算 calibration- 校准医学域模型的 AWQ 数据组大小。 为什么更多的数据并不总是更好?
4. 读读 Marlin- AWQ 的纸或发布注释。 在三句话中解释为什么 AWQ 在 7B 上击中 741 吨/秒, 而 原始 GPTQ 点击~ 712 。
5. 什么时候可以合并 AWQ weights 使用 FP8 键 KV cache 和保持KV在BF16?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| GGUF | "llama. cpp 格式" | 文件格式捆绑 K 量变量; CPU/边缘默认 |
| Q4_K_M | "Q4KM" ,我说 | 4- 位 K QQant 介质; 生产 GGUF 默认值 |
| GPTQ | 吉奥尿滴Q | 培训后INT4与 calibration; 支持 LoRA 在 vLLM |
| AWQ | "一个w q" | 启动觉察INT4; Marlin 内核; 最佳出入口@ 1 INT4 |
| 马林内核 | "快INT4内核" | Custom CUDA 上层的INT4内核; 10x 加速 |
| FP8 | 八位浮标 | 安全精确默认于 Hopper/Ada/Blackwell |
| MCFP4/NVFP4 号卫星 | 微缩四级 | 黑色井4位方块,每个区块比例因数 |
| Calibration dataset | "热量数据" | 用于选择输入文字 quantization parameters; 必须匹配域 |
| KV cache quantization | "KVINT8" (KVINT8) (KVINT8) (KVINT8) (KVINT8) (KVINT8) (KVINT8) | 单独选择 weights; 影响 attention accuracy |

<a id="further-reading"></a>

## 进一步阅读

- [VRLA 技术公司 LLM Quantization 2026](https://vrlatech.com/llm-quantization-explained-int4-int8-fp8-awq-and-gptq-in-2026/) 比较基准。
- [贾维斯实验室 vLLM Quantization 完整的指南](https://jarvislabs.ai/blog/vllm-quantization-complete-guide-benchmarks) 格式化的输送数字。
- [PremAI - GGUF 诉 AWQ 诉 GPTQ 诉 Bitsandbytes 2026 。](https://blog.premai.io/llm-quantization-guide-gguf-vs-awq-vs-gptq-vs-bitsandbytes-compared-2026/) 格式化的逐个选择。
- [vLLM 医生 Quantization](https://docs.vllm.ai/en/latest/features/quantization/index.html) - 支持的格式和旗帜。
- [AWQ 纸(arXiv:2306.00978)](https://arxiv.org/abs/2306.00978) -原AWQ制剂。
- [GPTQ 纸张(arXiv:2210.17323)](https://arxiv.org/abs/2210.17323) 原始的通用一般分类和标签标准制剂。
