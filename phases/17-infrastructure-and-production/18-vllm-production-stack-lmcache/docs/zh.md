<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="production-serving-stack--kv-offloading-and-cache-aware-routing"></a>

# 生产服务技术栈：KV 卸载与缓存感知路由

> 提供电线、引擎和 observability 变成一个 Kubernetes 和治疗 KV cache 作为一种资源,可以离开 GPU. KV 卸载提取 KV cache 退出 GPU 内存和再利用,贯穿查询和引擎(CPU 磁盘/电子文件) vLLM生产堆放是参考部署; LMCAche 是卸载层。 vLLM 01.1. KV 卸载连接器 (2026年1月) 使此连接器不同步, 可通过连接器插入 API 卸载路径通常隐藏在请求路径之外, 虽然缓存误差和升级可以添加端到端的延迟时间。 LMCAche 即使在没有共享前缀的情况下也是有价值的 。 GPU 使用完 KV 空档后, 请求可恢复 CPU 而不是进行重新计算 prefill· 4个a3高格普-4g 16x H100(80GB HBM)基准: KV cache 超过 HBM, 两者均为本地 CPU 卸载和LMCache可大大改善输送量;在低 KV 足迹下,所有配置都与小的间接费用匹配基线。

**类型:** 学习
**语言:** Python (stdlib,玩具 KV -spill 模拟器)
**先修要求:** 阶段17 -04(内部维修发动机),阶段17 -06(SGLang/RadixAttention)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 图表 vLLM 生产堆积层:路由器、引擎、KV卸载 observability.
- 解释 KV 卸载连接符 API (v0.9.0+)和0.11.0的无同步路径如何隐藏延绳。
- 计算 LMCAche 时 CPU-DRAM帮助(KV > HBM) 相对于s 增加管理费(KV小到足以适应HBM)。
- 本地选择 vLLM CPU 由于部署方面的限制,卸载和LMCache连接器。

<a id="the-problem"></a>

## 问题

你的 vLLM 服务演示 GPUs 100%的HBM, 每当货币攀升时, 都会发生先发制人事件。 请求被逐出, 重新排队, 然后您...prefill 同样的2Ktoken prompt 一分钟内四次 GPU 计算用在多余上 prefills; goodput 远低于原始输送量。

添加更多 GPUs 线性成本。 无法添加更多的 HBM 。 但是, 无法添加 HBM 。 CPU DRAM 便宜, 一个插座有512GB+的悬浮级比 HBM 差, 但“ 暂时温暖” 却罚款 KV cache.

LMCache 提取的精选 KV cache 以 CPU 如此先发制人 DRAM 请求快速恢复, 且在未重新填充每个引擎的情况下, 重复在引擎共享缓存上设置前缀 。

<a id="the-concept"></a>

## 概念

<a id="vllm-production-stack"></a>

### vLLM production-stack

`github.com/vllm-project/production-stack` 是引用 Kubernetes deployment:

- **Router** · 藏匿装置(第17阶段-11阶段)
- **Engines** — vLLM 工人,每 GPU 或按TP/PP组别计算。
- **KV cache offload** - LMCACHE部署或本地连接器。
- **Observability** - 普罗米修斯刮痕,格拉法纳仪表板,奥特 traces.
- **控制飞机** 服务发现,配置,滚动更新。

以赫尔姆图+运算符方式装运。

<a id="the-kv-offloading-connector-api-v090"></a>

### KV 卸载连接器 API (v0.9.0+)

vLLM 引入了连接符 API 可插入的 KV cache 后端。 您的引擎卸载块到连接器; 连接器存储它们( RAM、 磁盘、 对象存储、 LMCAche) 。 请求需要一个块, 连接器将其装入 。

vLLM 0.11.(2026年1月)增加了一条不同步的卸载路径——卸载可在背景中发生,这样引擎在普通情况下不会堵塞它。 KV cache 打击率和系统压力; vLLM自己的笔记指出,自定义内核卸载可以降低低速输送量,而Async排期也发现与 speculative decoding.

<a id="native-cpu-offload-vs-lmcache"></a>

### Native CPU 卸载对 LMCAche

**Native vLLM CPU offload**: 本地引擎。 主机 RAM 中存储 KV 区块。 快速执行, 网络跳不跳。 不交叉引擎 。

**LMCAche 连接器**: 组级。 LMCAche 共享服务器中的存储区块 (CPU 数字记录和记录系统+Ceph/S3级) 任何引擎都可以使用区块。 16xH100基准已公布。

当单个引擎有 HBM 压力时, 选择本地的 。 当多个引擎共享前缀时, 选择 LMCche ()RAG 具有共同特性 system prompts,多租户与共享模板)。

<a id="benchmark-behavior"></a>

### 基准行为

16xH100(80GBHBM)分布在4个a3-highgpu-4g测试中:

- 低 KV 足迹( 短) prompts,低通货率:所有配置都匹配基线, LMCAche 增加了~ 3%-5%的管理费。
- 中度足迹: LMCache 开始帮助引擎的预设再利用。
- KV 超过 HBM: 本地 CPU 卸载和LMCache都大大改善了输送量; LMCache由于跨引擎共享而获得更大的收益。

<a id="when-lmcache-is-decisive"></a>

### 当LMCACHE是决定性的

- 多租户服务地点 system prompts 租户共有。
- RAG 文档在查询中重复。
- 精细调整变体(LoRA) 在同一基地上,KV基底再利用会减少重复工作。
- 工作量繁重:从 CPU 比再... 便宜一点prefill.

<a id="when-not-to-enable"></a>

### 无法启用时

- 微小的HBM压力——你支付间接费用,却没有好处。
- 短环境( < 1K) tokens——转移时间 > re-prefill.
- 单租户、单一 prompt 的工作负载，没有可利用的复用机会。

<a id="integration-with-disaggregated-serving"></a>

### 与 disaggregated serving

阶段17 · 17 disaggregated serving + LMCAche化合物:KV转自 prefill 池子,如果LMCache没有使用,可以解码池地;随后的查询从LMCache中提取。 第17阶段 11个缓存识别路由器可前往当地OR LMCache共享缓存匹配的引擎。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- vLLM 0.9.0: 连接器 API shipped.
- vLLM 0.11. (1月2026日):无同步卸载路径;端到端的延迟影响取决于工作量、KV撞击率和系统压力(不是绝对保证)。
- 16x H100 基准: 当 KV 足迹超过 HBM 时, LMCAche 帮助 。
- 小型的HBM压力: 3%-5%的间接费用没有效益。

```figure
zero-sharding
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟有和没有LMCAche的先发制人工作量。prefills 避免,输送收益, 和平衡的HBM使用。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-vllm-stack-decider.md`工作量的构成和 vLLM 使用,决定本地与LMCache对两者。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。使用HBM的LMCAche开始支付多少?
2. 租户合租6Ktoken system prompt 计算每个租户的LMCAche储蓄。
3. LMCAche 服务器是一个失败点。 设计 HA 策略( 复制、 返回本地) 。
4. LMCAche 仓库在旋转磁盘上到 Ceph。 4K-token KV 70B FP8 (500 MB),读取时间与 re-prefill?
5. 争论 vLLM 0.11. 条无序路径是“自由”—— 高空隐藏在哪里?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Production-stack | 参考部署 | vLLM的 Kubernetes 螺旋图+运算符 |
| Connector API | "KV 后端接口" | vLLM 0.9.0+可插入的 KV 存储界面 |
| Native CPU offload | 本地引擎泄漏 | 将 KV 存储在同一个引擎的主机内存 |
| LMCache | "cluster KV cache" | Cross-engine KV cache 服务器打开 CPU DRAM + 磁盘 |
| 0.11. 0 合成 | "无阻卸货" | 卸载隐藏在引擎流后面 |
| Preemption | "必须腾出空间" | KV cache 自动洗发机满载时 |
| 前缀再利用 | "same system prompt" | 多个查询共享开始; 缓存被击中 |
| 线条 | "磁盘层" | 在缓存级别中保存 DRAM 下的持久存储 |

<a id="further-reading"></a>

## 进一步阅读

- [vLLM 博客 - KV 卸载连接器 (Jan 2026)](https://blog.vllm.ai/2026/01/08/kv-offloading-connector.html)
- [vLLM 生产堆叠 GitHub](https://github.com/vllm-project/production-stack) - 赫尔姆图+运算符。
- [企业规模LMCAche LLM Inference (arXiv:2510.09665)](https://arxiv.org/html/2510.09665v2)
- [LMCache GitHub](https://github.com/LMCache/LMCache) - 连接器实施。
- [vLLM 0.11. 释放说明](https://github.com/vllm-project/vllm/releases) - 路径不同步的细节。
