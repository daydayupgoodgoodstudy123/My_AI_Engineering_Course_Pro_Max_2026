<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="shadow-traffic-canary-rollout-and-progressive-deployment-for-llms"></a>

# 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署

> LLM rollouts 组合软件最难的部署部分: 没有单元测试、 扩散故障模式、 延迟信号。 顺序是 (1) 阴影模式- 重复对候选模型的测试请求, 日志, 与用户零影响比较; 发现明显的分布问题, 但不是一个质量保障; (2) 金丝雀 rollout 递进交通量变化10% 25% 50% 75% 100% 门每步;跟踪潜伏百分位数、成本/要求、错误/拒绝率、输出长度分布、用户反馈率;(3) 在稳定后对不同的替代品进行A/B测试。 GPU 成本是可变的,不是固定的,一个20%更好的模型每通电话费用会更高3倍。 Rollback 速度是决定性的:如果 rollback 需要重新配置, 您太慢了 。 政策使用配置/ 挂牌; 模型使用刻录摘要在注册中 ; rollback =翻转策略+回转阈值+点针旧模型秒。

**类型:** 学习
**语言:** Python (stdlib,玩具金丝雀进场模拟器)
**先修要求:** 阶段17 · 13 (Observability阶段17 21(A/B测试)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 区分阴影模式(零影响比较)、金丝雀(实时流量递进)和A/B(稳定确认的比较)。
- 编号五 LLM- 特定的金丝雀测量(延迟、成本/要求、错误/拒绝、产出长度分布、用户反馈)。
- 解释一下 LLM 非确定性(最多15%)改变“稳定”在 rollout.
- 设计a rollback 路径需要秒( 政策翻转) 而不是小时( 部署) 。

<a id="the-problem"></a>

## 问题

您发运了一个新的模型。 离线电子估价显示3%的精度收益。 您在生产中将其翻转。 在24小时内成本上升40%, 用户缩略图下降率上升8%, 3张客户票报告“ 错误答案 ” 。 您滚回去。 重新配置需要3小时。 您的周末被毁了 。

每一个部分都是可以避免的。 阴影模式在任何用户看到它之前, 就会赶上40%的成本峰值。 加那利在缩略图移动时会停在10% 。 rollback 30秒后就会开始。这个学科填补了"脱机的电子逆向拍卖看起来不错"和"真正的用户是快乐的"之间的空白。

<a id="the-concept"></a>

## 概念

<a id="shadow-mode"></a>

### 阴影模式

候选人收到的请求与生产相同;产出被登录,不返回用户。

- 产出内容(与生产相比差强人意)。
- Token 计数(成本三角洲)。
- Latency.
- 拒绝和错误。

抓取: 成本爆炸、 长度回归、 明显拒绝更改、 硬错误。 不抓取: 高质量的 三角洲用户会察觉到 。 阴影是烟雾测试, 不是质量测试 。

<a id="canary-rollout"></a>

### Canary rollout

车门的交通量逐渐变化。典型的进度:1% 10% 25% 50% 75% 100%。每步有5个门:

1. **延迟度百分位数** 违反:金丝雀的基线为P99 > 1.5x。
2. **每项请求的费用** 折损: > 超过基线20%。
3. **错误/ 拒绝率** 5xx加上明确拒绝,违反:2x基线。
4. **输出长度分布** 违反:分配转移。
5. **用户反馈率** 违反:1.5x基线。

<a id="non-determinism-is-the-new-variance"></a>

### 非决定性是新的差异

同一投入产生非同质产出。

- GPU 燃料元件板非联合性(浮动点降级单因批次而异)。
- 批量大小差异(相同) prompt 共128次,16次
- Sampling (temperature > 0).

测量:在相同情况下,精确度变化幅度最高为15% eval sets. " 稳定 " 在一个 rollout 表示测量值在预期差异范围内,与基线不完全相同。设置噪音层以上的门。

<a id="cost-is-a-variable"></a>

### 成本是一个变量

20%的更好模型每通电话费用可以更高3x。 成本/ 要求是五个大门之一。 运输一个“ 更好的” 模式, 打破单位经济学是一个 rollback case.

<a id="rollback-is-the-weapon"></a>

### Rollback 是武器

- 政策标志(feature 旗帜系统: 在配置中翻转百分比; 需要秒。
- 模型针( 注册摘要) : 被钉住的模型不自动升级 。
- Rollback = 将旗帜 + 固定摘要恢复到以前的顺序。秒,而不是小时。

如果您的堆叠需要重新调用到 rollback拍之前先修补

<a id="tooling"></a>

### Tooling

**Argo Rollouts** / **Flagger** — Kubernetes 渐进式送货控制器。 与 Istio/ Linkerd 加权路由整合 。

**伊斯蒂奥加权路线** 服务级别交通分道扬镳

**KServe / Seldon 核心** — model serving 内置金丝雀

**Feature flags** 启动达克利,旗匠,解开 政策层面的翻转,不重新部署

<a id="metrics-cadence"></a>

### 度量曲线

加那利门每5-15分钟检查一次,视交通量而定。 1%的流量与10 req/min 相加,每个窗口有50-150个数据点,足够低档,但吵得用户反馈。 10%的流量比这多~ 10x。 进步应该暂停足够长的时间,以便在每一步都积累足够的样本。

<a id="the-ab-step-is-optional"></a>

### A/B级是可选的

如果新模式截然不同(不同行为、不同的成本曲线、不同的音调), A/B在金丝雀过关后测试为50%。 如果它只是改进版, 当金丝雀门过关时跳到100% 。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 加那利进步:1% 10% 25% 50% 75% 100%。
- 非确定性上限:相同投入的运行间差异高达15%。
- 五个金丝雀测量标准:延时、成本、错误/拒绝、产出长度、用户反馈。
- 成本门:超过基线的 > 20%是违反。
- Rollback秒,不是小时。

```figure
i4-canary-ramp
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟金丝雀 rollout 与注入回归。 rollout 停止,然后打开门

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-rollout-runbook.md`。根据候选模型、基线和风险承受力,设计“影子”100%计划。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。输入25%的成本回归。在哪个阶段金丝雀停止?
2. 您的新模式有3%的精度脱机,但成本/要求是+18%。它是一艘船舶吗?取决于策略 — — 写两条路径。
3. 设计a rollback 需要60秒以下的终端到终端。列出所需的基础设施 。
4. 非确定性在您的评估中显示 + 7%。 设置金丝雀门, 这样您就不会使用假武器。 您使用什么乘数 ?
5. 影子模式在金丝雀前会达到40%的成本峰值。 写下在阴影中点火的警告规则 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 阴影模式 | "复制到新" | 用于伐木的零影响发送到记录 |
| Canary | "递进交通" | 逐步的用户曝光 rollout 带门 |
| Gates | "rollout checks" | 阻碍进步的尺度阈值 |
| Non-determinism | "LLM variance" | 难以经受的运行到运行差异 |
| 政策标志 | 旗子翻转 rollback" | Config-level rollback,秒而不是小时 |
| 模版针 | "登记摘要" | 无法更改的引用模式版本 |
| Argo Rollouts | "K8进步" | Kubernetes- 本地金丝雀/rollback controller |
| KServe | "inference K8s" | Model serving 与金丝雀原始体 |
| 爱斯蒂奥加权 | "分开" | 服务- 网路分割器 |

<a id="further-reading"></a>

## 进一步阅读

- [天潘——解放国际 Features 无断裂生产](https://tianpan.co/blog/2026-04-09-llm-gradual-rollout-shadow-canary-ab-testing)
- [MarkTechPost——安全部署ML模型](https://www.marktechpost.com/2026/03/21/safely-deploying-ml-models-to-production-four-controlled-strategies-a-b-canary-interleaved-shadow-testing/)
- [APXML-高级 LLM 部署模式](https://apxml.com/courses/mlops-for-large-models-llmops/chapter-4-llm-deployment-serving-optimization/advanced-llm-deployment-patterns)
- [Argo Rollouts docs](https://argo-rollouts.readthedocs.io/)
- [爆破器 docs](https://docs.flagger.app/)
