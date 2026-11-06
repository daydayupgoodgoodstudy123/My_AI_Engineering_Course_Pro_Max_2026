<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="multi-region-llm-serving-and-kv-cache-locality"></a>

# 多区域 LLM 服务与 KV Cache 局部性

> 圆柱负载平衡对缓存有害 LLM inference。不降落在节点上的请求,只要保留其前缀,就可全额支付 prefill 成本-在P50时约800米 prompt 与 ~80 毫秒的缓存被击中。 在 2026 年, 生产模式是一个缓存识别路由器( NAME OF TRANSLATORS)vLLM 路由器已输入 Rust, llm使用KV卡切事件和前缀-带宽匹配路线的“路由器”。最近的研究(GORGO)将跨区域网络的延迟作为路径目标的一个明确术语。 inference" 提供(贝德罗克跨区域) inference, GKE 多组网关) inference 而不透明,他们处理 availabilityJP摩根和Mayo诊所在2024年11月 22分钟时 运行了我们东一号的故障 LLM 失败是因为团队支持 weights 却忘了 tokenizer 文件或 quantization configs.

**类型：** 了解
**语言:** Python (stdlib, 玩具前缀- cache- awe 路由器模拟器)
**先修要求:** 阶段17 · 04 (vLLM 服务,第17阶段 06年(SGLang RadixAttention)
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么圆柱式负载平衡断段缓存 inference 并量化TTFT处罚。
- 绘制缓存识别路由器图: 输入 (KV-cache 事件)、 算法 (prefix- hash 匹配) 、 断线 (brike- breaker) (KV-cache 事件)GPU utilization).
- 命名32% DR 失败驱动程序 LLMs (missing tokenizer 文件 / quantization 配置)并列出一份三文件的 DR 核对表 。
- 区分跨区域商业供货(Bedrock CRI、GKE多俱乐部网关)和KV-aware路由。

<a id="the-problem"></a>

## 问题

您的服务在东一号, 西二号, 西一号。 您将一个 ALB 放在圆柱形前端。 前缀缓存的点击率下降到8%。 TTFT P50 三倍 。 您的 P50 。 vLLM 日志显示每个请求都全额支付 prefill 成本.

圆环对无国籍者服务最有利。 LLM inference 以设计为目的的 KV cache 将模型所见的一切编码。 运行盲目正在错误的缓存中 。

分开,你的团队有DR计划,你支持模型 weights 给 S3 跨区域。 区域断电; 您尝试失败; 复制拒绝启动 。 您忘了 tokenizer.json, 该 quantization 配置,以及 RoPE 缩放配置是在一个单独的桶里 你没有同步。

Multi-region LLM 服务是一个缓存问题,一个路径问题,以及DR-Hygine问题——而不是一个负载平衡问题。

<a id="the-concept"></a>

## 概念

<a id="cache-aware-routing"></a>

### 缓存提醒路径

请求随同 prompt。 路由器预置前缀(例如,前512页) tokens; 它询问每个复制件“ 您是否已经保存了此前缀 ” 。 复制品在分配和删除区块时会在酒吧/ 子频道上发布 KV 缓存事件 。 路由器会用匹配来选择复制件, 跳到 GPU-没人能打断领带的

**vLLM Router** (Rust2026年生产堆叠:订阅 `kv.cache.block_added` 事件, 保持前缀 Hash 复制索引, 路径为 O(1) 查看。 跌至不匹配时的直线最低 。

**llm-d 路由器**:相同的模式, Kubernetes- 本地。通过控制平面发布事件 API.

**SGLang RadixAttention** 17 ° 06 级为重复型内等值,交叉式路线严格上流。

<a id="numbers"></a>

### Numbers

TTFT P50 开2Ktoken prompt, Llama 3.3 70B FP8, H100:
- 缓存击中( 相同的复制, 前缀常住数) :~ 80 ms 。
- 缓存错误( 冷) prefill:~800毫秒。

10x 差数。 如果您的路由器在复制品中击中了60-80%的前缀缓存, 您将使用 N 复制能力来接近单个复制性能。 如果它击中10%, 您将可以估计天真的缩放 。

<a id="cross-region-has-a-new-constraint--network-latency"></a>

### 跨区域有新的限制——网络延迟

区域间区域工作队:
- 我们 - - - - -我们 -西 - -2:~65米
- 我们 - - - -1 - 欧 - 西 - 1:~75 ms.
- 我们 - - -1 -1 / 东南 -1:~220米。

如果路线从我们东部1号到东南1号的热字前缀 prefill 近乎440米的圆程(800  80 毫秒)。 GORGO (2026) 研究使这一点变得明确—— 最小化 `prefill_time + network_latency` 合并,不 prefill 答案往往是保持区域路径, 但大块的多MB前缀除外 prefill dominates.

<a id="commercial-cross-region-inference-does-not-help-here"></a>

### 跨区域商业 inference"在这里没有帮助

AWS 贝德洛克跨区域 inference 能力压力下自动向其他地区提出路线要求。 availability,而不是 TTFT,并且治疗 inference GKE多组网关是相同的——服务级故障,没有意识 KV cache.

即使使用这些,你仍然需要一个应用程序显示缓存路由器。 他们处理“ 最小一号在火中” 的个案。 缓存路由处理 TTFT 的个案 。

<a id="dr-hygiene--the-32-missing-files-problem"></a>

### DR卫生——32%的失踪档案问题

广泛引用的2026年数据:32% LLM 失败是因为团队支持 weights 但却忘记了:

- `tokenizer.json` 或 `tokenizer.model`
- Quantization 配置( F)`quantize_config.json`, AWQ 比例, GPTQ 零点)
- 特定模型配置(RoPE scaling, attention 面具、聊天模板)
- 引擎配置( F)`vllm_config.yaml`, sampling defaults, LoRA 适配器清单)

修正为三文件的最低 DR 显示器 :

1. 高频模式回购的所有文件(weights + 组合+ tokenizer).
2. 引擎专用配置
3. 部署清单(K8) YAML,Dockerfile,依赖性锁)。

加上:每季度进行一次DR钻头。JPMCA我们东部1钻头在2024年11月只因为练习了剧本,才恢复22分钟。

<a id="data-residency-is-orthogonal"></a>

### 数据居住位置为正弦

欧盟客户 PHI 无法离开欧盟。 如果您的缓存识别路由器向我们发送了来自巴黎的预缀匹配请求, 您已经违反了GDPR , 不论TTFT是否获得收益。 在优化缓存前, 使用居住边界分隔路由器 。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 缓存击中与 TTFT 空格的错位:~ 10x (80 ms 和 800 ms ) 2K prompt).
- 跨区域RTT 美国-欧盟:~75米
- 测试失败:32% 失灵 tokenizer/量配置。
- JPM组织我们东1号失败时间2024年11月:22分钟(30分钟/苏丹解放军)。

```figure
cache-aware-router
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟三种跨区域工作量的路线战略(圆柱、暗礁警报区域、全球暗礁警报),报告缓冲率、TTFT P50/P99和跨区域账单。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-multi-region-router.md`鉴于地区、居住限制和苏丹解放军,设计了路线规划。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。在什么情况下 prompt 跨区域路线是否比本地路径强?
2. 您的缓存点击率从70%下降到12%。 诊断出三种可能的原因和可观察到的可以证实的每个原因 。
3. 设计一个70B AWQ 量化模型的DR 舱单 vLLM 5页 LoRA 适配器,列出每个文件与配置。
4. 问一下贝德洛克是否横跨区域 inference 严格TTFTSLOs的芬特技术就足够了
5. 巴黎来的申请符合我们东边的前缀。 您要选择路线吗? 写入保单 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 缓存提醒路径 | "聪明的LB" | 与 KV 缓存复制的前缀- hash 匹配的路径 |
| KV 缓存事件 | "酒吧的卧底" | 复制发布块添加/避免;路由索引 |
| 前缀散列 | "缓冲键" | 第一个N的大麻 tokens 用作路由器搜索 |
| GORGO | "跨区域路线研究" | arXiv 2602.11688; 网络延迟为明确期限 |
| Cross-region inference | 贝德洛克·克里 | AWS产品; availability 失败, 不是TTFT意识 |
| 记录显示 | 备份列表 | 需要恢复的每一个文件——不仅仅是 weights |
| 数据居住 | “GDPR 边界” | 区域看到用户数据的法律限制 |
| RTT | "往返时间" | 网络潜伏;75毫秒美国-欧盟,220毫秒美国-亚太建筑工程中心 |
| LLM- 深知LB | "卡切 - 击中LB" | 缓存识别路由器作为产品类别 |

<a id="further-reading"></a>

## 进一步阅读

- [本图马利-多云和跨区域 inference](https://bentoml.com/llm/infrastructure-and-operations/multi-cloud-and-cross-region-inference)
- [阿尔西夫-格罗戈(2602.11688)](https://arxiv.org/html/2602.11688v1) - 跨区域KV-cache再利用,使用网络延迟期。
- [天潘-多区域 LLM 服务缓存位置](https://tianpan.co/blog/2026-04-17-multi-region-llm-serving-data-residency-routing)
- [AWS 贝德罗克十字军 Inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) — availability 文档失败 。
- [vLLM 生产堆叠路由器](https://github.com/vllm-project/production-stack) - 隐藏识别路由器源。
