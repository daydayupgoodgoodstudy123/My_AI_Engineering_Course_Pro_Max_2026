<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="gpu-autoscaling-on-kubernetes--karpenter-kai-scheduler-gang-scheduling"></a>

# Kubernetes 上的 GPU Autoscaling：Karpenter、KAI Scheduler 与成组调度

> 3个层次,而不是1个层次。卡彭特提供动态节点(比集束自动标尺器快1分钟,快40% ) 。 KAI 调度处理帮派日程安排、 感应和排队等事宜 — — 它防止了7 - 8 部分分配陷阱, 7个节点等待并烧在1个缺失的点上 。 GPU应用级自动标尺器(NVIDIA Dynamo Planner, 和 NBLA) llm-d 工作量变换自动标尺) inference- 特定的信号 - 排队深度, KV cache 利用——非 CPU典型的HPA陷阱是 `DCGM_FI_DEV_GPU_UTIL` 是一种按责任周期衡量的方法:100%可以是10项要求或100项。 vLLM pre-allocates KV cache 内存, 所以记忆不会触发缩放。 此课教您如何构建三层, 避免默认的 Karpenter `WhenEmptyOrUnderutilized` 终止运行的政策 GPU 工作中间 -inference.

**类型:** 学习
**语言:** Python (stdlib, 玩具队列深度自动标尺模拟器)
**先修要求:** 阶段17 02 (Inference 平台经济学,第17阶段 -04年(内部服务引擎)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 图表三 autoscaling 层( 节点提供、 帮派列表、 应用程序级别) , 并标明每个层使用的工具 。
- 解释一下 `DCGM_FI_DEV_GPU_UTIL` 错误的 HPA 信号 vLLM 并指定两个替换( 排深, 或 深 ) KV cache utilization).
- 描述帮派时间安排和部分分配失败模式 KAI 调度器防止(8个中有7个) GPUs idle).
- 列出卡彭特合并政策(`WhenEmptyOrUnderutilized`终止运行 GPU 并声明2026年的安全选择。

<a id="the-problem"></a>

## 问题

你们的队伍有一艘 LLM-服务 Kubernetes你和HPA一起设计了 `DCGM_FI_DEV_GPU_UTIL` 以信号为标记。 服务在营业时间里100%的使用率。 HPA 从未升级, 它已经认为您是满的。 您手动添加复制件; TTFT 下降。 HPA 仍然不升级。 信号是对您的欺骗 。

另外,您使用 COB 自动标尺来交换节点。 1M -token prompt 时间是上午2时;分组用3分钟提供节点,请求时间则不在此限。

再说一次,你还用70B型的8 GPUs 横跨两个节点。 组有 7 GPUs 空闲, 1 分布在三个节点上。 集成自动标定器为 缺失的 1 个节点提供一个节点 GPU。七个节点等待4分钟燃烧的钱 Kubernetes 获得最后 GPU up.

三个层次,三个不同的失败模式。 GPU-aware autoscaling 2026年不是"HPA" 它组成节点供应,黑帮安排和应用程序信号 autoscaling.

<a id="the-concept"></a>

## 概念

<a id="layer-1--node-provisioning-karpenter"></a>

### 图层 1 - 节点供给( Karpenter)

Karpenter在~45-60秒内观察待处理的舱和供应节点( Cluster Austomasser 通常需要 90-120秒) GPU 节点),它会按 `NodePool` 限制-如果您的舱需要8 H100s,而且该舱组没有匹配节点,卡彭特条款直接提供一条,而不是扩大现有组。

**合并陷阱**: 卡彭特的默认 `consolidationPolicy: WhenEmptyOrUnderutilized` 危险 GPU 池子。 它会终止运行 GPU 将舱流迁移到更便宜的正确大小的例子。 for inference 工作量意味着将运行中的请求排除在外,并在新节点上重新装入一个 70B 模型。 损失是容量分钟加请求失败。

安全设置 GPU pools:

```yaml
disruption:
  consolidationPolicy: WhenEmpty
  consolidateAfter: 1h
```

让卡彭特在一小时后 巩固真正的空节点 但绝不驱逐一个运行中的工作。

<a id="layer-2--gang-scheduling-kai-scheduler"></a>

### 第2层——帮派时间安排(KAI调度器)

KAI 调度器( 项目“ Karp” 后重新命名) 处理默认 kube- 调度器不包含的 :

**黑帮日程安排** 计划全套或全套 inference 需要 8 个舱 GPUs 要么全部8个开始一起,要么没有。没有这个,你就会得到部分分配陷阱:8个舱中的7个开始,无限期地等待,烧钱。

**地形学意识** -知道是谁 GPUs 共享 NVLink, 并在同一架上, 中间有 Infini Band 。 相应放置 pods 。 A DeepSeek- V3 67B 电磁波 tensor- 平行工作量必须保留在一个NVLink域;KAI排程员尊重这一点。

**等级队列** - 多个团队竞争同一场 GPU A组的产量被B组的训练工作先发制人

KAI 与 kube- 调度器一起被部署作为二级调度器; 您要说明使用它的工作量。 Ray and vLLM 生产堆叠 两者融合。

<a id="layer-3--application-level-signals"></a>

### 图层3——应用级信号

**香港邮政局的陷阱**: `DCGM_FI_DEV_GPU_UTIL` 是一种责任周期衡量标准——它衡量的是是否 GPU 每个人在工作 sampling 间距。 100%的使用可能意味着同时提出10项请求或100项; GPU 工作周期的升迁是盲目地扩大

更差, vLLM 和类似的发动机预分配 KV cache 内存( 最多 `--gpu-memory-utilization`) 内存使用率即使按一个请求也保持在90%左右。基于内存的 HPA 永远不会缩小。

**2026 替换信号**:

- 队列深度(等待请求数) prefill).
- KV cache 使用(区块的分数分配给活动序列)。
- 复制 P99 TTFT(您的 SLA 信号)
- Goodput (要求每秒与所有特别工作组会晤)。

NVIDIA 迪纳摩计划员 llm-d 工作负荷变异自动标尺器消耗这些信号和比例复制。 LLM serving.

<a id="when-to-use-what"></a>

### 何时使用

| 比额表决定 | 工具 |
|----------------|------|
| 添加/删除节点 | Karpenter |
| 调度多GPU jobs | KAI 调度器 |
| 添加/删除复制 | 迪纳摩计划员/ llm-d WVA(或排队深度的自定义 HPA) |
| Choose GPU 类型 | 卡彭特节点pool |
| 优先处理低优先 | KAI 调度队列 |

<a id="disaggregated-prefilldecode-complicates-everything"></a>

### Disaggregated prefill破解一切

如果你运行分解 prefill/解码( 17 ° 17), 您有两个舱级, 不同缩放触发器 : prefill 排队深度的播客, 解码器大小 KV cache pressure. llm- 暴露这些是分开的 `Services` 使用每个功能的HPA。 不要试图将一个 HPA 在两者前面。

<a id="cold-start-matters-here-too"></a>

### 开始冷也很重要

冷启动减缓( 17 ° 10) 是节点供给时间可以被用户看到的地方。 Karpenter 的45- 60 秒加20GB 模型加引擎加内装, 意味着从零要求需要 2 - 5 分钟。 保持一个温暖的池子( 保暖) ( 保暖)`min_workers=1`)用于对 SLO 临界路径,或在应用层使用模式式的检查。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- Karpenter节点提供:~45-60s 相对于 Croup Automasser ~ 90- 120s ()GPU nodes).
- KAI排程器防止部分分配废物——8分之7的陷阱。
- `DCGM_FI_DEV_GPU_UTIL` 作为 HPA 信号: 损坏; 使用队列深度或 KV 利用率 。
- Karpenter `WhenEmptyOrUnderutilized`:终止运行 GPU 选项。 `WhenEmpty + consolidateAfter: 1h` 用于 inference.

```figure
autoscaling
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟一个三层自动标尺在爆炸上 GPU 比较天真的HPA(职责周期)、排队深度HPA和KAI-gang计划的规模。GPU 几分钟,和一个复合得分。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-gpu-autoscaler-plan.md`组合型结构、工作量和 SLO 设计一个三层 autoscaling plan.

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。在工作繁忙的情况下,天真的HPA要求多少次会让排队深度HPA的捕获量下降?
2. 为服务组设计一个卡彭特节点 Llama 3.3 H100 SXM5上的70B FP8 具体说明 `capacity-type`, `disruption.consolidationPolicy`, `consolidateAfter`和一个不留...GPU 工作由这些节点完成。
3. 你的团队报告说,部署被卡在等待中,因为 "GPUs 诊断——卡彭特、库贝排期机还是KAI排程仪?
4. 选择自动分类的信号 prefill 密码和密码都不同,两个都合理
5. 计算成本 `WhenEmptyOrUnderutilized` 24x7生产服务中的综合陷阱,平均每天60次请求发送事件,P99 TTFT > 10秒。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Karpenter | "节点供给者" | Kubernetes 节点自动缩放; 分分钟提供 |
| 集束自动标尺 | "旧的天平" | Kubernetes 节点自动缩放前置; 慢速, 以组为基础 |
| KAI 调度器 | "该 GPU scheduler" | 黑帮 + 地形 + 队列的二级排程器 |
| 黑帮日程安排 | "无所事事" | 原生或推迟全部 N 程序 |
| 地形学意识 | "rack-aware" | 基于 NVLink/ IB/ 架式放置的平台 |
| `DCGM_FI_DEV_GPU_UTIL` | "GPU utilization" | 值日周期衡量标准;不是 LLMs |
| 队列深度 | "等待请求" | 正确 HPA 信号 prefill- 定时缩放 |
| KV cache utilization | "模拟压力" | 用于解码缩放的正确 HPA 信号 |
| Consolidation | 卡尔彭特合并 | 节点终止为更便宜实例类型 |
| `WhenEmpty + 1h` | "安全整合" | 政策不驱逐运行 GPU jobs |

<a id="further-reading"></a>

## 进一步阅读

- [KAI 调度器 GitHub](https://github.com/kai-scheduler/KAI-Scheduler) 设计文件与配置实例。
- [卡彭特干扰控制](https://karpenter.sh/docs/concepts/disruption/) 合并政策语义和 GPU- 安全默认
- [NVIDIA - 分类 LLM Inference 在 Kubernetes](https://developer.nvidia.com/blog/deploying-disaggregated-llm-inference-workloads-on-kubernetes/) - 迪纳摩计划员的缩放信号
- [Ray docs - KAI 光学分类表](https://docs.ray.io/en/latest/cluster/kubernetes/k8s-ecosystem/kai-scheduler.html) Ray的融合模式。
- [AWS EKS 计算 Autoscaling 最佳实践](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-compute.html) 管理好...Kubernetes- 特定的指导。
- [llm-d GitHub](https://github.com/llm-d/llm-d) 工作量变换自动标尺设计。
