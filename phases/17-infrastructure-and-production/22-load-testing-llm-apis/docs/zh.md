<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="load-testing-llm-apis--why-k6-and-locust-lie"></a>

# 对 LLM APIs 进行负载测试：为什么 k6 与 Locust 会产生误导

> 传统的装载测试器不是为 streaming 响应,可变输出长度, token- 等级指标,或 GPU saturation有两个陷阱咬了大部分的队伍。 token- 级别测量运行 tokenization 下方的 Python GIL, 与以高通货制生成请求相竞争; tokenization 积压,然后报告充气 inter-token latency - 你的客户是瓶颈,不是服务器。 prompt- 一致性陷阱:相同 prompts 中,在环状测试 token 分布; 真实流量有变量长度和不同的前缀匹配。 LLMPerf 解决这个问题 `--mean-input-tokens` + `--stddev-input-tokens`2026年的工具映射: LLM- 专业(GenAI-Perf,LLMPerf, 和LLMPerf, ) LLM- 劳克斯, 制导) token- 等级准确性; **k6 v2026.1.0** + **k6 操作员1.0 GA (2025年9月)** — streaming-aware, Kubernetes- 通过测试运行/私人Load区CRDs分发的本地设备,最好用于光学/CD门; saturation; 仅使用 LLM- 休克扩展 streaming。装入模式:稳态、斜坡、钉子(autoscaling 测试,浸泡(模拟泄漏)。

**类型：** 构建
**语言:** Python (斯迪利布,玩具现实 --prompt 发电机+潜伏器收集器)
**先修要求:** 阶段17 · 08 (Inference 计量,第17阶段 -03年(GPU Autoscaling)
**时间：** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释一下两种反模式(GIL陷阱, prompt- 统一陷阱),使通用装载测试器为 LLM APIs.
- 为指定目的选择一个工具: LLMPerf( 基准运行) k6+ streaming 扩展(CI门), 指南(大型合成), GenAI- Perf (NVIDIA 参考)。
- 设计四个装载模式( 固定、 斜坡、 刺钉、 泡泡) 并给每个捕获的失败模式命名 。
- 构建一个现实的 prompt 使用输入的正则+标准德维进行分布 tokens 而不是固定长度。

<a id="the-problem"></a>

## 问题

你考了六年级 LLM 端点是500个同时用户,它保持。你发运了。在生产200个实际用户时,服务下降——P99 TTFT爆炸, GPUs pinned.

发生了两件事 首先,K6发送了500个相同的 prompts -你的请求书 prefix caching 让它看起来你正在处理500个同时的解码。 其次, k6 不跟踪 inter-token latency 在 streaming 眼睛的体验,它会反应,它会看到 HTTP 连接, 不是500 tokens 时间间隔不同

装入测试 LLMs 这也是它自己的纪律

<a id="the-concept"></a>

## 概念

<a id="the-gil-trap-locust"></a>

### GIL 陷阱( 崩溃)

蝗虫用途 Python 运行 tokenization 客户端在 GIL 下。 在高通货率下 tokenizer 请求生成后排队。 已报告 inter-token latency 包括客户端 tokenization 积压。 您认为服务器是慢的; 这是测试 harness.

Fix: LLM- 休克扩展移动 tokenization 使用已编译的语文 harness (k6, LLMPerf 使用 tokenizers.rs).

<a id="the-prompt-uniformity-trap"></a>

### 该 prompt- 一致性陷阱

所有已知的装载测试器都允许您配置一个 prompt。在一万次循环测试中,相同的重复 prompt 每次发送。 服务器每次看到相同的前缀- 前缀缓存点击接近100%, 输送量看起来很好 。

固定: 从 a 样本 prompt 使用 LLMPerf 软件 `--mean-input-tokens 500 --stddev-input-tokens 150` 不同长度、内容不同。

<a id="four-load-patterns"></a>

### 四个装载模式

1. **Steady-state** 固定的RPS30-60分钟。 接头:基线性能回归。
2. **Ramp** 将RPS从0线增加到15分钟以上的目标。
3. **Spike** 3 -10的RPS 突然2分钟后回来 autoscaling 缓冲, 排队 saturation冷启动撞击
4. **Soak** 4 -8小时的稳态状态 记忆泄漏 连接池漂移 observability overflow.

<a id="2026-tool-mapping"></a>

### 2026 工具映射

**LLMPerf** (任何规模) - Python 但 Rust-backed tokenization平均/平均 prompts. Streaming- 注意,最佳的预设性能运行

**国家投资管理局** - NVIDIA的参考文献。 Triton 客户端; 全面的度量覆盖。 注意它的国际交易日志不包括 TTFT; LLMPerf 包含它。 两个工具为同一个服务器生成不同的TPOT 。

**LLM-Locust** 修补 GIL 陷阱的 Luscast 扩展名。 Familiar Locust DSL + streaming metrics.

**guidellm** 大规模合成基准。

**k6 v2026.1.0** + **k6 操作员1.0 GA (2025年9月)**:
- k6 本身( Go, 编译, 没有 GIL) streaming- 清晰的度量
- k6 运算符使用测试运行/ 私人 Loadzone CDD 来进行 Kubernetes- 本地分布式测试
- 最好用于CI/CD门和SLA测试。

**Vegeta** 跑,简单到K6,坚持速度 HTTP saturation. 不 LLM- 了解但适合测试网关/费率限制

**托盘2.43.3库存** - 拥有GIL陷阱 LLM。只有与 LLM- 休克扩展。

<a id="sla-gate-in-ci"></a>

### CI的苏丹解放军大门

运行 K6 公关, 使用:

- 基线RPS各30-50次。
- 门:P50/P95 TTFT,5xx < 5%,临界值下TPOT。
- 突破裂缝

<a id="realistic-prompt-distribution"></a>

### Realistic prompt distribution

利用真实流量样本(如果有的话)或已公布的分布(例如,ShareGPT)构建 prompts 用于聊天, 人类val 代码) 。 将平均值 + stddev 装入 LLMPerf 。 避免与一环-prompt 不论如何

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- k6 操作员1.0 GA:2025年9月。
- k6 v2026.1.0: streaming- 清晰的度量
- 典型的LLMPerf运行:100-1 000次请求,按同价货币X计算。
- 典型的CI门:每份公关30-50次重复。
- 四个模式:稳态,斜坡,刺,泡泡。

```figure
load-pattern-waves
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟现实的负载测试 prompt 设计、测量、测量和展示prompt trap.

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-load-test-plan.md`. 鉴于工作量和苏丹解放军,选用工具和设计四种负荷模式。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`比较统一与现实的分配——差距在哪里?
2. 刻写 CI 门的 k6 脚本: TTFT P95 < 800 ms , 共 100 个, 运行时间为 5 分钟 。
3. 您的浸泡测试显示记忆每小时增加50 MB。 列出三个原因和选择它们的工具 。
4. 斯派克测试从10个RPS到100个RPS。如果卡彭特+ vLLM 生产堆放已经到位(第17阶段 3+18)?
5. GenAI-Perf 报告 TPOT=6ms; LLMPerf 报告 TPOT=1100ms 在同一服务器上。 请解释 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| LLMPerf | "该 LLM harness" | 任何尺度的基准工具, streaming-aware |
| GenAI-Perf | “ NVIDIA 工具” | NVIDIA 参考文献 harness |
| LLM-Locust | "Lobust for uh... 被抛弃... LLMs" | 修补 GIL 陷阱的 Locust 扩展 |
| guidellm | "合成基准" | 大型合成工具 |
| k6 运算符 | "K8s k6" (K8s k6) , 和K8s k6一样 | 以 CRD 为基础的分布式 k6 |
| 吉利码陷阱 | "Python 客户管理费" | Tokenization 报告的延迟度 |
| Prompt- 一致性陷阱 | "single-prompt lie" | 循环相同 prompt 点击缓存, 充气输送 |
| Steady-state | "连续载荷" | 平坦 RPS 分钟 |
| Ramp | "线性起来" | 0个目标持续时间 |
| Spike | "爆破测试" | 突然乘数然后返回 |
| Soak | "长测试" | 泄漏检测时间 |

<a id="further-reading"></a>

## 进一步阅读

- [天潘-负载测试 LLM Applications](https://tianpan.co/blog/2026-03-19-load-testing-llm-applications)
- [PremAI - 装载测试 LLMs 2026](https://blog.premai.io/load-testing-llms-tools-metrics-realistic-traffic-simulation-2026/)
- [NVIDIA NIM - 介绍 LLM Inference Benchmarking](https://docs.nvidia.com/nim/large-language-models/1.0.0/benchmarking.html)
- [真理报 LLM-Locust](https://www.truefoundry.com/blog/llm-locust-a-tool-for-benchmarking-llm-performance)
- [LLMPerf](https://github.com/ray-project/llmperf)
- [k6 运算符](https://github.com/grafana/k6-operator)
