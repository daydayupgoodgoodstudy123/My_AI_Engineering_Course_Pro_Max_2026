<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="inference-metrics--ttft-tpot-itl-goodput-p99"></a>

# Inference 指标：TTFT、TPOT、ITL、Goodput、P99

> 4个衡量标准决定是否 inference 正在运行中。 TTFT 是 prefill TPOT(相当于国际交易日志)是每个 token。端到端的延迟时间是 TTFT 加上TPOT 乘以输出长度。 tokens per second 整个舰队的集合。但对于产品来说,重要的是 goodput 满足每个特别业务条款要求的一小部分。 goodput 表示您正在处理 tokens 无法及时到达用户。 Llama-3.1-8B-在TRT上设置LLM 2026年:TTFT 162 ms, 意指TPOT 7.33 ms, 意指E2E 1 093 ms. 总是报告P50, P90, P99 - 绝不是普通的。看这个测量陷阱: GenAI-Perf 将TTFT排除在国际交易日志计算之外, LLMPerf 也包含它; 两个工具在同一运行中对TPOT意见不一致 。

**类型:** 学习
**语言:** Python (stdlib, 玩具百分位计算器和 goodput reporter)
**先修要求:** 阶段17 -04(内部维修发动机)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 定义TTFT、TPOT、ITL、E2E、输送量和 goodput 准确列出每个计量的成分。
- 解释为什么"不值钱"是错的 LLM 服务及如何阅读P50/P90/P99。
- 构建一个 SLO 的多限制( 如 TTFT < 500 ms 和 TPOT < 15 ms 和 E2E < 2 s) , 并计算 goodput 与它相反。
- 列出两个在TPOT上意见不一致的基准工具,

<a id="the-problem"></a>

## 问题

"我们的产量是15,000 tokens per second如果40%的要求在最后两秒之间被否决,用户就放弃了会话。光是完成并不能告诉你产品是否有效。

Inference 有一种多重的潜伏轴 每种都不同 Prefill 计算和比例 prompt 长度。解码是内存和比例 batch size。排队延迟是一个操作问题。网络是一个物理距离问题。您需要每个不同的度量,需要百分位数,并且需要单一的复合词,即“用户是否得到了他们期望的” goodput.

<a id="the-concept"></a>

## 概念

<a id="ttft--time-to-first-token"></a>

### 技术转移 - time to first token

`TTFT = queue_time + network_request + prefill_time`

Prefill 主宰时 prompts 长着呢,在 Llama-3.3-70B H100型FP8,32公里 prompt 纯度为~800毫秒 prefill。 队列时间是正在装入的排程器行为。 网络请求是包括 TLS。TTFT是用户在任何流回之前看到的隐蔽位置。

<a id="tpot--itl--inter-token-latency"></a>

### TPOT/国际交易日志 inter-token latency

多个名字都用一个数量 `TPOT` (time per output token), `ITL` (inter-token latency), `decode latency per token` ——都是一样。这是连续流的间隔时间 tokens 第一次之后,我发现

`TPOT = (decode_forward_time + scheduler_overhead) / tokens_produced`

一样 Llama-3.3-70B H100 堆叠 chunked prefill,TPOT 表示~ 7 ms。 chunked prefill,在很长一段时间 prefill TPOT可以加到50米 看着P99 不是故意的

<a id="e2e-latency"></a>

### E2E 延迟时间

`E2E = TTFT + TPOT * output_tokens + network_response`

用于长期产出( > 500) tokensE2E 以TPOT为主。对于短期产出来说,它具有长期的 prompts, E2E 以TTFT为主。报告输出长度为 E2E。

<a id="throughput"></a>

### 吞吐量

`throughput = total_output_tokens / elapsed_time`

综合度量,说明舰队效率,不说明个人健康要求

<a id="goodput--the-metric-you-actually-care-about"></a>

### Goodput - 你真正关心的量度

`goodput = fraction of requests meeting (TTFT <= a) AND (TPOT <= b) AND (E2E <= c)`

标准规则是一个多限制性条款。 只有当每个限制都有效时, 请求才“ 良好 ” 。 Goodput 占份额。高流量为60% goodput 失败。 低输出为 99% goodput 目标就是目标

2026年,我发现 goodput 用于 MLPerf 的测量 Inference v6.0 提交材料,并在AI平台供应商的内部跟踪中进行。

<a id="why-mean-is-the-wrong-statistic"></a>

### 为何数字错了

LLM 延缓分布是右倾的。prefill 邻居可以载五百 tokens TPOT~7米和20米 tokens 平均TPOT为9毫秒。 P99 TPOT为65毫秒。 用户经常打P99, 这就是为什么他们离开。

总是报告三重数据( P50, P90, P99)。 对于用户经验, P99 是最佳的。

<a id="reference-numbers--llama-31-8b-instruct-on-trt-llm-2026"></a>

### 参考编号 - Llama-3.1-8B-在TRT上设置LLM, 2026

- 平均TTFT:162毫秒
- TPOT: 7.33毫秒
- 平均 E2E:1 093毫秒
- P99 TPOT:视块状大小而变化10-25毫秒prefill configuration.

这些是已公布的 NVIDIA 参考点。 它们会随着模型大小( 70B 显示为3-5x)、 硬件( H100 相对于 B200 ~ 3x) 和 装载而变化 。

<a id="the-measurement-trap"></a>

### 测量陷阱

2026年最常用的两种基准工具在TPOT上意见不一:

- **国家投资管理局**:将TTFT排除在国际交易日志计算之外。 token 2.
- **LLMPerf**:包括TTFT。 token 1.

请求时使用TTFT 500毫秒和100输出 tokens 总计700毫秒解码,GenAI-Perf报告 `ITL = 700/99 = 7.07 ms`, LLMPerf 报告 `ITL = 1200/100 = 12.00 ms`。工具选择会更改数字。

总是说明哪个工具。 总是公布定义 。

<a id="constructing-an-slo"></a>

### 构建 SLO

2026年70B聊天模式的 合理的消费者形象 SLO:

- TTFT P99  800毫秒
- TPOT P99 25毫秒
- E2E P99 3秒, < 300 -token 输出.
- Goodput 目标99%。

企业SLOs 收紧TTFT(200-400毫秒)并放松 E2E。 重点是将其写下来, 测量所有三个, 跟踪 goodput 单一复合体

<a id="how-to-measure"></a>

### 如何衡量

- 运行真实的流量或现实的合成( LLMPerf 与 `--mean-input-tokens 800 --stddev-input-tokens 300 --mean-output-tokens 150`).
- 目标2x 基准运行的峰值同值货币。
- 运行30 -50的迭代, 取取百分位数 合并样本 。
- 以工具名、工具版本、模型、硬件、货币、 prompt distribution.

```figure
throughput-latency
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是一个玩具 goodput 计算器。生成合成延迟分布,应用 SLO, 并计算 goodput。还显示GenAI-Perf 与 LLMPerf TPOT 的差别。 trace.

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-slo-goodput-gate.md`。鉴于工作量和可持续性工作,它制作了CI/CD可用基准配方,供使用 goodput 而不是通过量。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。生成1%尾部钉点的分布。如何 goodput 等P99TPOT从30毫升到15毫升时,就会改变?
2. 卖家引用"15 000吨/秒 Llama 相信它之前先问三个问题
3. 为什么 chunked prefill 保护 P99 TPOT 但不是 TPOT ?
4. 为语音助理构建一个消费者 SLO (第一个) token 哪种衡量标准最能显示用户?
5. 读取 LLMPerf README 和 GENAI- Perf docs 。 找出工具不一致的其他三个标准 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| TTFT | "time to first token" | 队列+网络+ prefill; 由 prefill 长 prompts |
| TPOT | "time per output token" | 内存解码费用 token 第一次之后 |
| ITL | "inter-token latency" | 与大多数工具中的TPOT相同(并非所有——见GenAI-Perf) |
| E2E | "结束到结束" | TTFT + TPOT 组合键 * 输出_伦; 顶端响应端网络 |
| 吞吐量 | "tok/s" | 舰队效率;无延迟度的无用百分位数 |
| Goodput | "SLO-met 速率" | 满足每个 SLO 限制的请求的分数 |
| P99 | "tail" | 最差的100个档次;用户经验衡量标准 |
| SSLO 多重约束 | "关节" | 和所有三个延迟界限;如果有违反,请求将失败 |
| GenAI-Perf 与 LLMPerf 的比重 | "工具陷阱" | 工具对国际交易日志是否包括TTFT存在分歧 |

<a id="further-reading"></a>

## 进一步阅读

- [尼加拉瓜 LLM 基准衡量](https://docs.nvidia.com/nim/benchmarking/llm/latest/metrics.html) · TTFT、ITL、TPOT的明晰定义。
- [任何规模 LLM 基准衡量标准](https://docs.anyscale.com/llm/serving/benchmarking/metrics) 备选定义和衡量方法。
- [本托马利- LLM Inference Metrics](https://bentoml.com/llm/inference-optimization/llm-inference-metrics) 实际部署应用计量。
- [LLMPerf](https://github.com/ray-project/llmperf) - 以雷为基础的开放源基准。
- [GenAI-Perf](https://github.com/triton-inference-server/perf_analyzer/blob/main/genai-perf/README.md) - NVIDIA的基准工具。
- [MLPerf Inference](https://mlcommons.org/benchmarks/inference-datacenter/) 行业接受 goodput- 基准
