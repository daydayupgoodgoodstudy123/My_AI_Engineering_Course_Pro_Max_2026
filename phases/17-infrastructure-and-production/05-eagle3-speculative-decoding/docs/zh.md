<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="eagle-3-speculative-decoding-in-production"></a>

# 生产环境中的 EAGLE-3 Speculative Decoding

> Speculative decoding 配对一个目标模型快速草稿模式。 tokens;目标在单向前方进行验证;接受 tokens 2026年EAGLE-3是生产级变体,它训练了目标模型隐藏状态的草稿,而不是原始状态的草稿。 tokens,将接受率 alpha 推入0.6-0.8 段的普通聊天中。正确的问题不是“草稿有多快”而是“我的交通中阿尔法是什么?”如果alpha 跌到~ 055以下,那么“什么是Aab” speculative decoding 高通货率净负数,因为每份被拒的草案都需第二个目标 forward pass。这个课教你首先测量阿尔法,然后翻转旗子。

**类型：** 了解
**语言:** Python (stdlib, 玩具接受率模拟器)
**先修要求:** 阶段17 -04(内部维修发动机),阶段10 18(多至Token Prediction)
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 说出三代人的名字 speculative decoding 并解释EAGLE-3对EAGLE-2和经典的草稿模型所作的修改。
- 定义接受率 alpha, 从 Alpha 和 K (草稿长度) 计算预期的加速度, 并指定目标货币的折中值 alpha 。
- 解释一下 speculative decoding 选择进入( 非默认) vLLM 2026年,为什么打开它而不测量阿尔法 是生产反模式。
- 写一个测量计划: 哪个基准,哪个 prompt 分布,哪个货币点, 度量到门。

<a id="the-problem"></a>

## 问题

解码是内存。 H100 运行中 Llama 3.3 70B FP8,各解码 token 读数~140GB/s weights 并发出一个 token. 该 GPU 计算在解码时几乎是空闲的——瓶颈是HBM带宽,而不是matmul通量。

Speculative decoding 利用差距。 产生 K 候选人 tokens 使用廉价的草稿模型, 然后请目标模型在单行中验证所有 K forward pass。 token 有效免费(将目标反正必须提前分批拆为K级)。

传统的草案模式方法使用同一家庭较小的模式(见A/C.5/52/SR.2,第1段)。Llama 3.2 1B 起草工作 Llama 其效果是接受率平庸,但模型分布较小,与目标相去甚远。 EAGLE,然后是EAGLE-2,然后是EAGLE-3直接在目标模型的内部状态上进行光头分析,因此,分配率更接近于目标。这就是为什么α从0.4和草样变为0.6-0.8和EAGLE-3。

渔获量: EAGLE-3 选择加入 vLLM 2026. `speculative_config` 必须有明确的设置。 没有旗帜, 没有加速。 球队在不测量其真实交通量的情况下, 经常看到 tail latency 情况越来越糟,不是更好

<a id="the-concept"></a>

## 概念

<a id="what-speculative-decoding-actually-buys"></a>

### What speculative decoding 买的

没有标注代码, /token 成本是前进的一个目标。 使用标码的长度为 K 和接受阿尔法, 预计 tokens 每个目标前进 `1 + K * alpha`。加速 `(1 + K * alpha) / (1 + epsilon)` epsilon是预置加核查的间接费用。 K=5, Alpha=0.7: `(1 + 5*0.7) / (1 + 0.1) = 4.5 / 1.1 = 4.1x`。真实世界的数字围绕2-3x,因为阿尔法很少在生产流量中高,而以西龙则在高位增长 batch size.

<a id="why-alpha-is-the-only-metric-that-matters"></a>

### 为什么阿尔法是唯一重要的衡量标准

Rejected tokens 而不是消失——他们迫使第一个被拒绝的人 向第二个目标前进 token。在工作负荷中,如果阿尔法跌至0.4,您将支付管理费草案加上核查和再滚动。在高通货(比如256种同时)的情况下,解码批量已经足够大,足以缩小“目标单”和“目标加核查”之间的内存带宽差。在2026年大部分硬件的阿尔法0.55之下,分解码为净负值。

在ShareGPT式的一般聊天中,EAGLE-3号卫星的点击率为0.6-0.8;在具体地区交通(代码、医学、法律)方面,一般数据训练负责人草稿下降至0.4-0.6;针对特定地区的头部草稿训练恢复了阿尔法——与目标微调相比,这是一个轻而易举的训练工作。

<a id="eagle-generations-at-a-glance"></a>

### 几代人一眼就看见

- **经典草稿模型**:同一家庭的小模型。 Alpha 0.3-0.5。基础设施简单,两个模型已装入,每个目标的草稿都运行K前方。
- **EAGLE-1(2024年)**:在目标隐藏状态(最后一层)上培训了单人头部。阿尔法~0.5-0.6,目标顶部的小参数。
- **EGOLE-2 (2025年)**:适应性长度草稿和树本草稿(核实多个 branches ) Alpha ~ 0. 6-0.7。更复杂的排程器草稿。
- **EGOLE-3(2025-2026)**:在多个目标层(而不仅仅是最后层)上培训了领导班,这样更好 alignment. Alpha ~0.6-0.8 通用聊天方式。

<a id="the-2026-production-recipe"></a>

### 2026年生产配方

1. 船舶目标模型平原。测量基准TTFT、国际交易日志、目标货币通量。
2. 通过 EAGLE-3 草稿启用 vLLM `speculative_config`重新运行基准
3. 日志接受率阿尔法 vLLM V1报告此为 `spec_decode_metrics.accepted_tokens_per_request`。除以请求的长度草案,以获得阿尔法。
4. 如果生产流量分布为α < 0.55,则禁用插件编码或培训特定域的EAGLE-3草稿。
5. 在生产货币方面,重新运行。确认P99国际交易日志没有恶化。

<a id="the-production-pitfall-p99-tail"></a>

### 生产陷阱:P99尾

平均的国际交易日志下调, 并进行编码。 如果您不调的话, P99 可能会变得更差。 拒绝的草稿触发双通序列( 草稿+ 校验失败+卷转) 。 在整批中, 这2个版本会连续进行。 查看 P99 国际交易日志, 不是 P50 。

<a id="where-eagle-3-is-already-deployed"></a>

### EAGLE-3已经部署的地方

谷歌已部署 speculative decoding 2025年大赦国际概览(质量相同,反应更快)。 vLLM V1号舰船 `speculative_config` 及其 feature 矩阵标记 speculative decoding 符合 chunked prefill. SGLang 支持EGLE-3作为建议的前置重工作量路径草稿。

<a id="break-even-math-in-one-line"></a>

### 单行中偶数数学

预期的加速 : `S(alpha, K) = (1 + K*alpha) / (1 + verify_overhead)`设置 `S = 1` Alpha 的解析符 : `alpha_breakeven = verify_overhead / K`。用于典型的验证_顶部~0.15和K=5: `alpha_breakeven = 0.03`。但是这是原始解码数学。在高通货率下,验证的间接上升,而已经进行分批解码的内存会通过序列来读取,因此有效阿尔法_实际中,破碎的攀升到~0.45-0.55。

<a id="when-not-to-use-speculative-decoding"></a>

### 不使用时 speculative decoding

- 离线生成批量-1 , 其潜伏无关紧要 。 请使用普通目标 。
- 产出非常短(50岁以下) tokens管理费草案和费用核实占主导地位。
- 专业域没有域训练的草稿头。 Alpha 太低 。
- 假设 feature 组合。 vLLM 您版本的兼容性矩阵: v0.18. 0 马克 speculative decoding 兼容 chunked prefill.

```figure
mx-speculative-tree
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟有和无解码循环 speculative decoding 打印折叠平均字母的宽度, 测量速度和尾部行为。 运行多个组合( 阿尔法、 K) 以查看具体位置 speculative decoding 停止支付。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-eagle3-rollout.md`。根据目标模型、交通分布说明和货币组合目标,它产生一个分阶段的EAGLE-3 rollout 计划-基准基线,启用配置,测量阿尔法,在阿尔法上打开0.55号门,观看P99国际交易日志。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。在 K=5 时, 2x 加速需要什么阿尔法? 对于 3x 加速, 需要什么? 验证的敏感度有多高_overhead?
2. 想象一下生产流量将70%的普通聊天和30%的代码分割开来。 一般聊天击中了Alpha 0. 7, EAGLE-3 的 ShareGPT 培训; 代码击中了 Alpha 0.4。 什么是混合的阿尔法, 以及 spec decode Net- 阳性?
3. 读 vLLM `speculative_config` 文档。列出三种模式(草案模型、EAGLE、N-gram),并检查 features 每一个都与你的 vLLM version.
4. 允许 EAGLE-3 后,国际交易日志的运行率下降了25%,但P99 国际交易日志的运行率上升了15%。
5. 计算EAGLE-3号舱盖的记忆成本 Llama 3.3 70B. 与运行相比如何 Llama 3.2 1B作为经典的草稿?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Speculative decoding | 草稿加核实 | 提议K tokens 使用廉价模型, 验证所有 K 在一个目标前方 |
| 接受率 | 标注接受率 | 草案的分数 tokens 目标所接受的;唯一重要的衡量标准 |
| 长度草稿K | "请问" | 有多少个 tokens 草案按目标提出;典型的4-8 |
| 检查顶部的 Epsilon | "检查管理" | 校验和再滚转的额外费用相对于一个普通目标向前; 批量增长 |
| EAGLE-3 | "最新的爱格丽" | 2025-2026年变体;在多个目标层上进行预科培训;在一般聊天时进行 Alpha 0.6-0.8 |
| `speculative_config` | "vLLM 设置 | 明确选择加入 vLLM V1; 没有默认表示没有加速 |
| N克码 | "N克草稿" | GPU- 使用 N 克搜索的版本 prompt; 块-prefill-compatible |
| 平衡的阿尔法 | "无 -op -alpha" | 以 spec 代码为零加速的 Alpha 显示为零加速; 在生产同值货币时注意此选项 |
| 拒绝的双通 | 补习费 | 草稿拒绝时, 有两个目标向前; 驱动 P99 尾部 |

<a id="further-reading"></a>

## 进一步阅读

- [vLLM — Speculative Decoding docs](https://docs.vllm.ai/en/latest/features/spec_decode/) 权威来源: `speculative_config` 并铺设成块,prefill V1的兼容性
- [vLLM 投机性配置 API](https://docs.vllm.ai/en/latest/api/vllm/config/speculative/) 准确的场景
- [EAGLE 纸张(arXiv:2401.15077)](https://arxiv.org/abs/2401.15077) - EAGLE原草案头版。
- [EAGLE-2 纸(arXiv:2406.16858)](https://arxiv.org/abs/2406.16858) 适应性草和树木。
- [伯克利联合银行](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2025/EECS-2025-224.html) - 效率高 LLM 系统 speculative decoding.
- [本托马利- Speculative Decoding](https://bentoml.com/llm/inference-optimization/speculative-decoding) 生产 rollout checklist.
