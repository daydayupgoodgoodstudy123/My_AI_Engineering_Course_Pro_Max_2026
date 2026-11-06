<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="cold-start-mitigation-for-serverless-llms"></a>

# 缓解无服务器 LLMs 的冷启动

> 20 GB 模型图像需要 5 - 10 分钟 ( 7B) 到 20 分钟( 70B) 才能从冷到服务。 在真正的没有服务器的世界, 这不是暖气, 而是停机。 缓解措施在五个层次运行: 先种的节点图像( AWS 上的瓶状, 两卷形的拱门) , 模式 streaming (NVIDIA Run:ai 模型流,原生于 vLLM), GPU 内存快照( 模式) checkpoints,最多10x快速重新启动),热水池(`min_workers=1`),分层装载(服务器的 NVMEDRAMHBM 管道, 10- 200x 延时) 和移动输入的实时迁移 tokens (KB)而不是(KB) KV cache (GB) 模式将冷的开始作为地板发布; Baseten 5-10 默认值, 带有升温前的秒数。 此课教你测量、 预算并堆叠五层 。

**类型:** 学习
**语言:** Python (stdlib,玩具冷启动路径模拟器)
**先修要求:** 阶段17 02 (Inference 平台经济学,第17阶段 ・ 2003 (GPU Autoscaling)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出五个冷启动缓解层,并列出每个层的一个工具或模式。
- 计算总冷启动时间为(节点规定)+(weights 下载)+(weights 装入 HBM) +(引擎启动) 用于 70B 型号 。
- 解释为什么实时迁移传输输入 tokens (KB)没有 KV cache (英)和惩罚是什么(反诉)。
- 列出暖池交易( 空闲付费) GPU 和苏丹解放军的门槛值 `min_workers > 0` 成为强制性的。

<a id="the-problem"></a>

## 问题

您的服务器不存在 LLM 端点为零,早上8点时会堵车。第一个请求等待时间:

1. Karpenter条款a GPU 结点:45 -60
2. 容器拉动了30GB的图像 weights120 -300 号
3. 引擎载荷 weights 进入 HBM: 45 - 120 取决于模型大小和存储速度。
4. vLLM 或 TRT - 系统LLM initializes CUDA graphs, KV cache pool, tokenizer10 -30岁

总计:220-510(大约3-8分钟) token 回来,你的SLA是2,你带一个暖池(暖池)`min_workers=1`问题似乎已经消失,但现在你却为一个空闲的 GPU 24x7. 如果你的服务每件有5种产品, 都有1个热复制品, 那就是5×24×30=3,600 GPU- 不论是否有一个用户打电话,每个月的小时。

冷启动减缓是如何保持服务器的无功能经济学,同时接近始终的延迟。

<a id="the-concept"></a>

## 概念

<a id="layer-1--pre-seeded-node-images-bottlerocket"></a>

### 图层 1 - 预播节点图像 (Bottlerocket)

在 AWS 上, Bottlerocket 的双容量结构将OS 和数据分隔开来。 抓图数据数量, 与您容器图像预拉; 引用您在您的快照 ID `EC2NodeClass`。新的节点启动器 weights 当地NVME系统已经关闭,第2步和第3步的一部分消失了。与卡彭特公司合作。典型的节约:大型模型每冷水开始2-4分钟。

GCP 的等效值: 定制带有预烤容器层的 VM 图像。 在 Azure 上: 以相同模式管理的磁盘快照 。

<a id="layer-2--model-streaming-runai-model-streamer"></a>

### 图层 2 - 模型 streaming (运行: i 模型流)

而非在回答第一个请求之前装入完整文件, 流 weights 进入 GPU 内存层逐层, 并开始处理 transformer 块系居民。 NVIDIA Run:ai 型流船原住于 vLLM 2026. 与S3、GCS和当地NVMe合作。 weight- 大模型大约用一半的时间 重复 I/O 计算设置。

<a id="layer-3--gpu-memory-snapshots-modal"></a>

### 图3 - GPU 内存快照( 模式)

摩尔人拿一个 checkpoint 的 GPU 状态 (:weights, CUDA graphs, KV cache 后再将自动降空为 HBM , 速度比重新初始化快10x。 这是最接近于“ 启动一个温暖的 ” GPU 转折: 照片是每...GPU- 地形学,所以如果卡彭特把你转移到另一个SKU,你就会...checkpoint.

<a id="layer-4--warm-pools-min_workers1"></a>

### 第4层——温池(分钟)_workers=1)

最简单的缓解:保持一个复制随时可以完成。成本是 1 GPU24x7. 小型号的算术很残酷(你每小时支付0.85-1.50美元,以避免30个冷门起点),大型号的算术也很粗糙(每小时支付4美元,避免5分钟冷门起点)。

<a id="layer-5--tiered-loading-serverlessllm"></a>

### 图层 5 - 分层装载(无服务器LLM)

LLLM 服务器将存储视为等级 : NVME( 快速但大) , DRAM( 中等但分层) , HBM( 微小但瞬间) 。 Weights 预装入 DRAM; 按需装入 HBM。 纸张报告冷负载的延迟度比天真的磁盘对HBM的延迟度减少10- 200x。 生产采用较早, 但与 vLLM exist.

<a id="layer-6--live-migration-bonus-pattern"></a>

### 第6层——活迁移(骨型)

当节点无法使用( 点驱逐、 节点排水) 时, 传统模式会冷冻启动另一个复制和排水请求队列。 现场迁移会移动输入 tokens (千字节) , 指已装入模型并重新计算的目标 KV cache 与转移的GB相比,再计算成本更低。 KV cache 适用于分类部署。

<a id="the-warm-pool-math"></a>

### 热池数学

问题不是“温池是/否”, 而是“有多少温暖的复制品,

- 高价值互动路径( 实时聊天、 声音) agent): `min_workers=1-2`.
- 背景批量路径( 夜间分类): 接受比例为零, 5- 10分钟的冷开始可容忍 。
- 平分层 : `min_workers` 每个拥有专门能力的租户。

<a id="measure-before-optimizing"></a>

### 优化前的测量

70B型新节点的冷启动解剖( 说明) :

| 阶段 | 时间 | Mitigation |
|-------|------|-----------|
| 节点条款 | 50s | 瓶式火箭 + 预种子图像,温暖池 |
| 图像拉动 | 180s | 预产数据量(消除) |
| Weights 改为 HBM | 75s | 模型流器( halve); GPU 快速( 消除) |
| 引擎启动 | 20多岁 | Persistent CUDA 图形缓存 |
| 第一个前进 | 3s | 最小的固有延迟 |
| **冷冻** | **328s** | |
| **与缓解措施合计** | **~15s** | 22x 减少 |

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 模式冷开: 2-4(与 GPU snapshots).
- 默认的冷启动: 5- 10; 具有预升温的秒数 。
- 70B号轮起温:3-8分钟
- 运行: ai 模型流:~ 2x weight- 装弹加速
- 无服务器LLM 级装载: 10- 200x 延迟度减少( 纸张编号) 。

```figure
cold-start-pipeline
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 以每个减让方式模拟冷启动路径。 报告冷启动时间、热池成本和平衡请求率,热池本身就高于这一标准。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-cold-start-planner.md`。考虑到SLA、型号大小和交通状况,选择可以堆叠的。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。计算出一个热复制比通过在标准业务单位额外申请的滴水支付冷启动税更便宜的平衡请求率。
2. 您使用一个 13B 模型, P99 TTFT 服务器由 3 组成。 选择能够达到此目标的最低减让堆( 西层) 。
3. 瓶装火箭预播消除图像拉动,但 weights 仍然从快照装入 HBM。 如果速记支持 NVME 读取为 7 GB/ s, 则计算70B 模型的墙上时钟 。
4. 您的无服务器提供者提供 GPU 快速光碟(Modal)和你的团队拒绝,因为“闪光片泄漏 PII ” 。 双方都说,现实的风险是什么,缓解风险是什么(短光片、加密、命名空间隔离)?
5. 设计一个分层的暖池政策: 给付费用户、 试用用户和批量工作量提供多少热效复制品? 显示数学 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 开始冷 | "大暂停" | 从请求到第一次的时间 token 在一个全新的复制品上 |
| 温泉 | "总是最低" | `min_workers >= 1` 以保持至少一个复制 |
| 预种子图像 | "烤焦的AMI" (AMI) | 带容器的节点图像 weights pre-resident |
| Bottlerocket | "AWS节点OS" | AWS 集装箱优化操作系统,并配有双容量快照支持 |
| 模型流器 | "streaming load" | Overlap weights 计算设置的 I/O |
| GPU snapshot | "checkpoint 转到 HBM | 后装入的序列化 GPU 状态; 重新启动时解除序列 |
| 带线装入 | “NVMe + DRAM + HBM” (荷兰语) | 储存层的等级;按需装载 |
| 活移徙 | "move tokens" | 传输输入( KB), 在目的地重新计算 KV |
| `min_workers` | 温室复制品 | 无服务器最小保持保留数 |
| Scale-to-zero | "无全机服务器" | 无所事事时不计费用;接受全额冷启动税 |

<a id="further-reading"></a>

## 进一步阅读

- [模式 - 冷启动性能](https://modal.com/docs/guide/cold-start) 模式公布的基准和 checkpoint architecture.
- [AWS 瓶装火箭](https://github.com/bottlerocket-os/bottlerocket) 预种子数据量快照模式。
- [NVIDIA 运行: i 模型流](https://github.com/run-ai/runai-model-streamer) 重叠 weights 装入时计算设置 。
- [Baseten - 冷开关](https://docs.baseten.co/deployment/autoscaling/cold-starts) 升温前的剧本
- [服务器无端LLM 纸张( USENIX OSDI' 24)](https://www.usenix.org/conference/osdi24/presentation/fu) 分层装载设计。
- [NVIDIA - 分类 LLM Inference 在 Kubernetes](https://developer.nvidia.com/blog/deploying-disaggregated-llm-inference-workloads-on-kubernetes/) 进行分门别类的现场移徙。
