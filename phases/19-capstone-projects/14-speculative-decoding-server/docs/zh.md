<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-14--speculative-decoding-inference-server"></a>

# 综合项目 14：推测解码 Inference 服务端

> Speculative decoding - 廉价的草案 tokens目标模型可以一次验证它们——现在是一种生产准备优化,而不是研究技巧。 vLLM P-EAGLE(AWS 2026)进一步推高了平行的猜测。 SGLang红帽子投机者中心为通用开放模型发布了一致的草稿。 TensorRT-LLM made speculative decoding 2026年的制片厂是 vLLM 或 SGLang 使用EAGLE家庭草稿、FP8或INT4 quantization,然后排队等待 HPA。这个综合项目将使用两个打开模型, 2.5x+ 基线输送, 并附有完整的尾部延缓报告 。

**类型:** Capstone
**语言:** Python (服务),C++/ CUDA (内核检查) YAML (configs)
**先修要求:** 第三阶段(深入学习),第7阶段(transformers第十阶段(LLMs 17阶段(基础设施)
**实施阶段:** P3 ;P7 ;P10 ;P17 ;
**时间:** 30小时

<a id="problem"></a>

## 问题

Speculative decoding EAGLE-3 目标模型隐藏状态预示N tokens 前面; 目标模型在一次通过中验证。 接受率60- 80% 等于 2-3x 端到端输送量 。 vLLM 0.7是本地的结合 SGLang +SpecForge 向您提供训练管道。 红帽子的投机者会发布与该软件一致的草稿。 Llama 3.3 70B, Quen3-Coder-30B MoE, GPT-OSS-120B.

飞行器在运行中,不是模型。 接收率随交通分布而变化( 共享 GPT) vs code 数据) Tail latency 拒绝比没有猜测更糟糕——你必须多次报告第99页 batch sizes,而不仅仅是稳定状态 tokens/秒. 每1M 费用 tokens 与 Anthropic / OpenAI API 才是信誉的杠杆。

<a id="concept"></a>

## 概念

Speculative decoding 有两个层次。 A **draft** 模型(EAGLE-3 头、 ngram 或小目标匹配模型) 提出 k 候选人 tokens 每一步。 **target** 模式在一次中验证所有 k; 任何接受的前缀都取代贪婪的道路。 接受率取决于草稿目标 alignment 和输入分布。

EAGLE-3 击败了大多数交通量的 ngram 草稿。 P- EAGLE 运行了更深的草图的平行猜测。 折中点: 拒绝时的P99 空档值较高, 因为验证通道更大 。 可用的配置必须报告批量尺寸的拖拉度才能在此表面显示 。

部署是 Kubernetes. vLLM 0. 7 运行一个复制 GPU 或 tensor排队等候的HPA自动升级,而不是 CPU. FP8(马林)和INT4(AWQ) 数组保留 GPU H100/H200信封内的内存。端到端报告为:输送量、接受率、第1/8/32批第50/p99页和1美元 tokens.

<a id="architecture"></a>

## 建筑

```
request ingress
    |
    v
vLLM server (0.7) or SGLang (0.4)
    |
    +-- draft: EAGLE-3 heads | P-EAGLE parallel | ngram fallback
    +-- target: Llama 3.3 70B | Qwen3-Coder-30B | GPT-OSS-120B
    |     quantized FP8-Marlin or INT4-AWQ
    |
    v
verify pass: batch k draft tokens through target
    |
    v (accept prefix; resample for rejected suffix)
    v
token stream back to client
    |
    v
Prometheus metrics: throughput, acceptance rate, queue wait, latency p50/p99
    |
    v
HPA on queue-wait metric
```

<a id="stack"></a>

## 堆栈

- Serving: vLLM 0.7 或 0.7 或 SGLang 0.4
- 投机方法:EAGLE-3号头草案、P-EAGLE平行投机、ngram后退
- 培训草案:Specforge(SGLang或红色帽子投机者
- 目标模式: Llama 3.3 70B, Quen3-Coder-30B MoE, GPT-OSS-120B
- Quantization目标日期:8(马林),INT4 AWQ
- Deployment: Kubernetes + NVIDIA 设备插件; 队列等候度量的 HPA
- Eval: 共享GPT、MT-Bench-V2、GSM8K、用于域分布接受度测量的人类Eval
- 参考: 特索拉特-LLM speculative decoding 供应商基线

```figure
cf-spec-decode
```

<a id="build-it"></a>

## 动手实现

1. **目标模型准备。** Pick Llama 3.3 70B. 通过Marlin向FP8进行量化。 vLLM 1xH100 的 0.7 (或 2x) tensor-parallel).

2. **来源草稿。** 从红帽子投机者(或通过斯佩克福格训练一个)中拉出一个对齐的 EAGLE-3 头部草稿。 装入 vLLM投机解码配置 。

3. **基线数字。** 投机前: tokens/在批次1/8/32,p50/p99 延迟, GPU 利用。出版。

4. **启用 Eagle -3 。** Flip 配置; 重运行相同的基准。 报告速度、 接受率, p99 尾延三角形 。

5. **P-EAGLE.** 启用平行猜测; 测量更深的树草与序列 EAGLE-3 。 报告 P- EAGLE 帮助伤害的偏移 。

6. **网路交通** 通过同一个服务器运行 shareGPT 和 HumanEval 和 域性通信。 测量每个分布的接受率。 确定草稿漂移时 。

7. **第二个目标模型。** 在Quen3-Coder-30B上运行同一管线 MoE。草稿更狡猾(MoE 路由噪音 报告

8. **K8s HPA(K8s HPA) , 高尔夫球员。** 在K8下部署,并进行HPA跟踪 `queue_wait_ms`。当加载三重时,显示规模的缩小。

9. **成本比较。** 计算 1美元 tokens 与 Anthropic Claude 索内特4.7和 OpenAI GPT-5.4在同一个评价上,出版

<a id="use-it"></a>

## 实际应用

```
$ curl https://infer.example.com/v1/chat/completions -d '{"messages":[...]}'
[serve]     vLLM 0.7, Llama 3.3 70B FP8, EAGLE-3 active
[decode]    bs=8, accepted_tokens_per_step=3.2, acceptance_rate=0.76
[latency]   first-token 42ms, full-response 980ms (620 tokens)
[cost]      $0.34 per 1M output tokens at sustained throughput
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-inference-server.md` 描述交付品。 speculative decoding,完整基准报告和K8s部署。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | 测量的加速量与基准量 | 2.5x+ 两种模型的匹配质量输送量 |
| 20 | 现实交通的接受率 | 分发接受率报告 |
| 20 | P99 尾延纪律 | 第1/8/32批第99页,有或无投机 |
| 20 | Ops | K8部署,HPA排队等候 rollout smooth |
| 15 | 编写和方法 | 清楚解释什么已经改变,为什么 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 当草案落后于目标的某一版本时,测量接受率下降(例如: Llama 3.3 - > 3.4漂移)建立监测警报。

2. 执行 ngram 倒数: 如果 EAGLE-3 的接受率下降到阈值以下, 则切换到 ngram 草稿。 报告可靠性的提高 。

3. 运行一个受控 MoE 实验:同样的Quen3-Coder-30B,注射路径噪音与不注射。

4. 扩展至 H200 (141 GB). 报告获得的模型大小/ 复制主机以及您能否为未量化的空格服务 Llama 3.3 70B. 环境

5. 基准天线调整和调整LLM speculative decoding 在同一 H100 硬件上。 报告它赢得 vLLM.

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 草案模型 | "Speculator" | 提议采用N型小模型 tokens 目标的核查 |
| EAGLE-3 | "2026年建筑草案" | 接受目标隐藏状态培训的草稿;~75%接受 |
| P-EAGLE | "帕拉勒投机" | 草稿树 branches 在一个目标通过处验证 |
| 录取率 | 击球率 | 起草的分数 tokens 接受时不重标 |
| Quantization | "FP8/INT4" 调制 | Lower-precision weights 以适合更多模型 GPU memory |
| 排队等候 | "HPA 度量" | 请求在等待队列中等待的时间 inference starts |
| 投机者中心 | 统一草案 | EAGLE 红帽神经魔法中心共同开放模型的草稿 |

<a id="further-reading"></a>

## 进一步阅读

- [vLLM EGLE 和 P-EGLE 文件](https://docs.vllm.ai) - 参考书架
- [P-Eagle(AWS 2026)](https://aws.amazon.com/blogs/machine-learning/p-eagle-faster-llm-inference-with-parallel-speculative-decoding-in-vllm/) - 平行 speculative decoding 纸张+整合
- [SGLang SpecForge](https://github.com/sgl-project/SpecForge) 训练负责人编审
- [红帽子投机者](https://github.com/neuralmagic/speculators) 统一式中心
- [TensorRT-LLM speculative decoding](https://nvidia.github.io/TensorRT-LLM/) 供货商备选
- [烟花,服务建筑](https://fireworks.ai/blog) 商业参考
- [EAGLE-3 纸(arXiv:2503.01840)](https://arxiv.org/abs/2503.01840) 方法文件
- [vLLM repository](https://github.com/vllm-project/vllm) 守则和基准
